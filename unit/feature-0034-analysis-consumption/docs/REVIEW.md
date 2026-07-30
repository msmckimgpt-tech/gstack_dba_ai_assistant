---
doc_type: REVIEW
feature_id: feature-0034-analysis-consumption
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260730T091500-cluster-grounding [CODEX: 반영 완료]

- **Related Change:** feature-0034 L2 요약의 대화 grounding 주입 (CHG-20260730T090500).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독).
- **반증 요청 가설:** ① 답변 지연 증가 ② 실패의 답변 차단 ③ 프롬프트 인젝션 ④ 잘못된 요약
  주입(라벨 조인 정확성·scope 누수·정렬) ⑤ 근거 표기 누락·오도 ⑥ SQL 정확성(ILIKE 이스케이프).

### 자체 사전 점검에서 잡은 것

| # | 결함 | 조치 |
|---|---|---|
| S1 | `cursor()` 가 try **밖**이라 커넥션이 죽으면 예외가 **답변 경로로 전파** | try 안으로. 테스트가 잡아냈다 — feature-0031 의 `connect` 배치와 같은 계열을 또 반복했다 |
| S2 | `ILIKE '%'||table_name||'%'` 가 테이블명의 `_` 를 와일드카드로 해석 | `strpos` 순수 부분문자열 검사로 교체 |
| S3 | `DISTINCT ON` 은 ORDER BY 첫 컬럼이 label 이어야 해 LIMIT 이 **라벨 알파벳 순**으로 잘림 | 2단계 조회로 재구성하며 해소(근거순 정렬 후 LIMIT) |

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **schema 격리 누수** — `cluster_summaries` 식별자는 `(scope, schema, …)` 인데 조회가 `scope + label` 만 봤다. 같은 datasource 의 다른 스키마가 같은 라벨을 가지면 **엉뚱한 요약이 주입**된다 | **유효(P1)** | 2단계 조회로 재구성: 1단계에서 `(scope, effective_schema, label)` 을 유도하고 2단계에서 그 3중 키로 조회. `effective_schema` 는 `semantic_cluster._effective_schema` 복제이며 **테스트가 원본과의 일치를 단정**(드리프트 방어) |
| C2 | **`SET LOCAL statement_timeout` 이 무효** — RO 연결은 autocommit 이라 트랜잭션이 없다. 예외를 삼키고 본 쿼리를 계속 실행하므로 1.5초 상한이 보장되지 않는다 | **유효(P1)** | 세션 레벨 `SET` + finally `RESET`(호출측 커넥션 누출 방지). 테스트가 SET/RESET 짝을 단정 |
| C3 | ILIKE 와일드카드 오매칭 | **유효(P1)** | S2 에서 이미 수정(리뷰는 staged blob 기준이라 미반영 상태를 봤다) |
| C4 | `DISTINCT ON` 정렬·LIMIT 불일치 | **유효(P2)** | S3 에서 이미 수정 |
| — | 프롬프트 인젝션 | **반증됨** | datamark 실제 적용 확인 |
| — | ANY 바인딩 | **반증됨** | 파라미터 바인딩, 문자열 삽입 경로 없음 |
| — | 일반 DB/커서/연결 실패 | **반증됨** | 예외를 빈 결과로 평탄화, close 보호 |

### Verdict

SHIP — P1 3건·P2 1건 전부 수정(2건은 리뷰 전 자체 발견분과 동일 판정). 인젝션·바인딩·실패 처리
가설은 코드 근거로 반증.

### 스스로 짚는 점

S1(`cursor()` 배치)은 feature-0031 에서 `connect()` 를 try 안으로 옮기며 배운 것과 **정확히 같은
계열**이다. "자원 획득을 try 밖에 두면 그 실패가 호출측으로 샌다"는 규칙을 세 번째 반복하고 있다.
FUNCTION.md §5 에 명시했고, 이번엔 테스트가 먼저 잡았다는 점이 다르다.

### 남긴 리스크

- 매칭은 질문이 **테이블명을 문자열로 언급**할 때만 작동한다. 도메인 어휘로만 묻는 질문
  ("결제 관련 구조 알려줘")은 걸리지 않는다 — 의미 검색 확장은 별 슬라이스(임베딩 왕복 비용 판단 필요).
- 라이브 요약의 85%가 근거 0이라, 주입되는 요약 대부분이 추정이다. 커버리지 개선(ITEM-11)이
  이 층의 품질에 직결된다.
