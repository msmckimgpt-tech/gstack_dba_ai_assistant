---
doc_type: FUNCTION
feature_id: feature-0034-analysis-consumption
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function: 분석 산출물의 대화 소비 — L2 요약 grounding 주입 (ITEM-09)

## 개요

질문이 언급한 테이블이 속한 **묶음(의미 클러스터)의 요약** 1~2건을 답변 컨텍스트에 주입한다.
개별 테이블 설명이 "이 테이블이 무엇인가"라면, 이것은 **"이 테이블이 속한 묶음이 함께 무엇을
하는가"** 다.

진단에서 잡힌 RI-5 를 메운다: 노드 분석 1만여 건과 클러스터 요약이 쌓였는데 **답변 경로가 그것을
읽지 않았다**(`kb_retrieval`·`knowledge` 에서 참조 0). 분석의 가치가 콘솔 열람에만 갇혀 있었다.

## 1. 주입 위치

`agent_core._build_knowledge_context` — 다른 grounding 소스(테이블·컬럼 설명, 테이블 관계,
few-shot 예시)와 같은 자리, 같은 패턴(`_kt_mark` 계측 + `_datamark_untrusted`).

섹션명 `TABLE GROUP SUMMARIES`. 매칭 0건이면 섹션 자체를 생략한다.

## 2. 매칭 — 2단계

**1단계** `rag_objects` 에서 질문에 등장한 테이블을 찾는다.
- 매칭 = **질문 문자열 안에 테이블명이 등장하는가**(`load_relationship_context` 와 동형).
- `strpos` 를 쓴다. `ILIKE` 는 테이블명의 `_`(예 `backup_log_trade`)를 "임의의 1문자"
  와일드카드로 해석해 `backup-log-trade` 같은 문자열에도 걸린다.
- 테이블명 4자 미만 제외(`id`·`log` 가 질문 아무 데나 걸리는 오탐 차단).
- 행 상한 200.

**2단계** 그 테이블들의 `(scope, effective_schema, label)` 로 `cluster_summaries` 를 조회한다.

### 왜 라벨로 조회하나
`cluster_summaries` 는 `member_set_hash` 로 키가 잡혀 있고 `rag_objects` 는
`semantic_cluster_id` 만 갖는데, **그 id 는 pass 마다 재부여되어 churn 한다**. 요약이 캐시
적중하면 저장된 id 가 낡아 엉뚱한 묶음의 요약이 붙는다. `semantic_cluster_label` 은
`_disambiguate_labels` 로 스키마 내 유일하게 만들어지고 양쪽 저장소에 모두 있다.

### 왜 2단계로 나누나 (schema 격리)
`cluster_summaries.schema_name` 은 **effective schema** 다 — MSSQL 은 `rag_objects.schema_name`
이 리터럴 `dbo` 라 DB 차원이 소실되고 클러스터링은 `object_key` 의 DB명을 쓴다. 즉
`schema_name` 을 그대로 조인하면 MSSQL 에서 한 건도 안 맞고, schema 를 아예 빼면 **같은
datasource 의 다른 스키마가 같은 라벨을 가질 때 엉뚱한 요약이 붙는다**. 유도 규칙을 SQL 로
재현하는 것보다 파이썬에서 계산해 2단계로 조회하는 편이 정확하고 읽기 쉽다.

`effective_schema()` 는 `semantic_cluster._effective_schema` 의 복제이며(답변 경로에서 무거운
클러스터링 모듈을 import 하지 않기 위해), **테스트가 두 구현의 일치를 단정**해 드리프트를 잡는다.

## 3. 근거 표기 — 정직성 장치

각 요약 앞에 근거를 붙인다:

```
- [게임 로그 기록] (멤버 48개 중 40개 상세분석 근거) 이 묶음은 …
- [로그 아카이브] (멤버 42개 · 상세분석 근거 없음(이름·구조 기반 추정)) 백업과 …
```

라이브 실측상 요약의 **85%가 상세분석 근거 0**(이름·구조 추정)이다. 근거를 숨기고 요약만 주면
LLM 이 추정을 실측 결론으로 오독하고 그 오독이 사용자 답변에 실린다. 프롬프트도 *"'상세분석
근거 없음'은 이름·구조에서 추정한 것이므로 사실로 단정하지 말고, 확인이 필요하면 실제 스키마·
데이터를 조회해 검증하라"* 고 명시한다.

## 4. 지연

- **사전 계산분만** 쓴다. 런타임 합성 없음 — feature-0027 이 확보한 체감 지연 개선을 잠식하지 않게.
- 쿼리 2회(둘 다 가벼움) + `statement_timeout` 1.5초.
  `SET LOCAL` 이 아니라 세션 `SET` 을 쓰고 `RESET` 으로 짝을 맞춘다 — RO 연결은 autocommit 이라
  `SET LOCAL` 이 무효이고, 호출측 커넥션에 설정이 누출되면 안 된다.
- `_kt_mark("cluster_summary_ms")` 로 단계별 지연에 계측된다(feature-0026 M3 계약).

## 5. fail-soft

연결 실패·테이블 부재·타임아웃·조회 예외 → 빈 문자열(섹션 생략). `cursor()` 획득도 try 안에서
한다 — 밖에 두면 커넥션이 죽었을 때 예외가 답변 경로로 전파된다. 답변을 막는 것보다 요약 없이
답하는 편이 언제나 낫다.

## 6. 스위치

`AGENT_CLUSTER_SUMMARY_GROUNDING`(콘솔 live, 기본 1). 0 이면 주입이 멈추고 답변은 종전
grounding 으로 진행한다. 비활성 시 연결조차 열지 않는다.
