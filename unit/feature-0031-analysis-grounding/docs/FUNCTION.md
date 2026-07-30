---
doc_type: FUNCTION
feature_id: feature-0031-analysis-grounding
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function: 노드 분석 접지 — 통계 증거층(L0) + 분석 payload 주입(L1)

## 개요

그래프 뷰 'AI 능동 분석'(feature-0002 `node_analysis`)의 LLM 입력에는 지금까지 **데이터 실측이
전혀 없다** — 노드 이름·설명·이웃 관계만 주어지고, 프롬프트가 "이름 규칙에서 가장 그럴듯한 의미를
추론하고 단정하라"고 지시한다. 본 기능은 운영 DB 에서 **통계만**(원시 샘플값 배제) 수집해
`agent_kb` 에 적재하고, 그 통계를 분석 payload 의 `evidence` 블록으로 주입한다.

LLM 호출 수는 늘지 않는다 — 같은 콜에 더 나은 입력을 준다.

## 1. 증거 수집 (L0)

### 1.1 수집 항목

| 대상 | 항목 | 수집원 |
|---|---|---|
| 테이블 | 근사 row count · 컬럼 수 · PK 컬럼 · 인덱스 컬럼 · FK 진출/진입 수 | 카탈로그 |
| 컬럼 | 데이터 타입 · NULL 허용 · 문자 길이 상한 | 카탈로그 |
| 컬럼(표본) | distinct 추정 · null 비율 · 숫자 min/max · 시각 min/max · 문자열 길이 min/avg/max · 패턴 클래스 | 표본 `SELECT` |
| 키 후보 | UNIQUE 성립(distinct ≈ sampled_rows) | 위 산출물의 결정적 판정 |

### 1.2 원시 샘플값 배제 (설계 불변식)

- 컬럼 **값 자체를 저장하지도 주입하지도 않는다**. 저장되는 것은 집계값뿐이다.
- **문자열 컬럼의 min/max 값도 저장하지 않는다** — 문자열 극단값은 사실상 원시 샘플 1건이며
  이름·이메일·주소 컬럼에서는 곧 PII 다. 대신 길이 분포(min/avg/max)와 **패턴 클래스**를 남긴다.
- 패턴 클래스 `value_pattern` ∈ `digits` | `hex` | `uuid` | `email_like` | `mixed` | `empty`
  — 값이 아니라 형태 분류다. `email_like` 는 개인정보 의심 신호로 caveats 근거가 된다.
- 숫자·시각 타입만 min/max 를 남긴다(범위 파악 가치가 크고 개인 식별성이 낮다).

### 1.3 수집 단계 (Stage)

```
Stage 0  카탈로그만        : information_schema / sys — 사용자 테이블 read 0
Stage 1  경량 표본         : 테이블당 LIMIT 100 표본 위 집계
Stage 2  표준 표본         : LIMIT 1,000
Stage 3  정밀              : 전수 집계 — 명시 승격만
```

승격 규칙(적응형이되 보수적):
- **하루 최대 1단계**만 올린다.
- **시간창 상한** — 주간(업무시간)에는 Stage 1 을 넘지 않고, 야간에만 Stage 2 이상을 허용한다.
- **Stage 3 은 운영자 승인**(설정 knob) 없이는 도달하지 않는다.
- AIMD 류 자동 증감은 쓰지 않는다 — 우리가 운영 DB 의 지배적 부하원이 아니고 신호 지연이 커서
  발진 위험이 있다(`RESEARCH.md` §4.9).

### 1.4 부하 제어

- 모든 수집은 `ds` 자원 예산 게이트(feature-0025 T0b) 위에서 실행되고, 거절되면 **다음 주기로
  이월**한다(fail-soft — 수집 실패가 분석을 막지 않는다).
- `COUNT(*)` 전수 스캔 금지 — row count 는 카탈로그 근사치를 쓴다.
- 쿼리 타임아웃 강제. 실패는 `metadata_table_stats.error` 에 남기고 다음 주기 재시도.
- 전역 kill-switch `AGENT_BACKGROUND_ANALYSIS_ENABLED` 하위에서만 동작한다.

## 2. 저장

`agent_kb` 스키마에 additive 신규 2 테이블(alembic, downgrade 가역):

- `metadata_table_stats` — PK `(scope_key, schema_name, table_name)`
- `metadata_column_stats` — PK `(scope_key, schema_name, table_name, column_name)`

⚠ 이 통계는 `semantic_cluster` 의 RC4 시그니처에 **넣지 않는다**. 넣으면 통계가 갱신될 때마다
전량 재임베딩·재클러스터가 유발된다. 증거 변경은 L2 요약 캐시 키로만 전파한다(ITEM-07).

## 3. 분석 payload 주입 (L1)

`_build_payload` 가 `evidence` 블록을 추가한다:

```json
"evidence": {
  "row_count_est": 120000,
  "collected_at": "2026-07-30", "stage": 1, "sampled_rows": 100,
  "pk_columns": ["stage_id", "item_id"],
  "columns": [
    {"name": "item_id", "type": "int", "nullable": false,
     "distinct_est": 100, "null_ratio": 0.0, "min": 1, "max": 9871, "unique_in_sample": true},
    {"name": "expire_at", "type": "datetime", "nullable": true, "null_ratio": 0.87},
    {"name": "note", "type": "varchar", "len_avg": 12.4, "pattern": "mixed"}
  ]
}
```

- 증거가 없으면 `evidence` 키 자체를 넣지 않는다(현행 payload 와 byte-동치).
- 컬럼 수는 payload cap 을 따른다(토큰 보호).

## 4. 프롬프트 계약 변경

- `NODE_ANALYSIS_PROMPT` 의 "이름 규칙에서 추론" 지시를 **"증거가 있으면 증거 우선, 없을 때만
  이름 규칙"** 으로 개정한다.
- `evidence` 를 untrusted-data 규칙 대상에 명시한다(수집값도 데이터이지 지시가 아니다).
- caveats 규칙(자기-불평 금지, ADR-034)은 유지하되, 이제 **증거 기반 위험**(개인정보 의심 패턴,
  null 비율 이상, 미검증 관계)을 쓸 실제 근거가 생긴다.

## 5. thin 판정 재정의

현행 `_analysis_is_thin` 은 summary 120자 미만을 thin 으로 본다. 그런데 프롬프트 계약이 "한국어
1~2문장"(≈50~100자)이라 **정상 분석 대부분이 thin 으로 잡힌다**. 지금은 `REFINE_MAX=30`/run 캡이
폭주를 막고 있을 뿐이며, 캡을 올리면 대량 재분석이 터진다.

→ 길이 임계 대신 **항목 충족도**로 판정한다: `summary`/`relationships`/`usage` 가 각각 실질
내용인지(공란·"연결 정보 없음"·상투구 아님) + Table 노드면 `role` 이 유효 분류인지.
`AGENT_NODE_ANALYSIS_THIN_CHARS` 는 하위호환 하한(극단적으로 짧은 문장 방어)으로만 남긴다.
