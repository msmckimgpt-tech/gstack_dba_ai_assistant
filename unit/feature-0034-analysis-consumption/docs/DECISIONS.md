---
doc_type: DECISIONS
feature_id: feature-0034-analysis-consumption
status: active
edit_policy: append-only
source_of_truth: true
---

# Decisions (feature-local ADR)

## ADR-0034-01 — 소비 배선을 L3 보다 먼저 한다
- **결정:** ROADMAP 순서(ITEM-08 L3 → ITEM-09 소비)를 뒤집어 ITEM-09 를 먼저 구현한다.
- **근거:** L2 요약이 이미 쌓이기 시작했는데 답변 경로가 읽지 않아 여전히 콘솔 열람에만 갇혀
  있다(RI-5). L3 는 L2 위에 층을 하나 더 쌓는 일이라, 소비 경로 없이 만들면 **또 하나의 미사용
  자산**이 된다. 만든 것을 쓰는 경로를 먼저 잇는다.
- **사용자 승인:** 2026-07-30 ("자율적으로 완수까지").

## ADR-0034-02 — 라벨로 조회한다 (cluster_id 아님)
- **결정:** `rag_objects` ↔ `cluster_summaries` 연결 키를 `semantic_cluster_label` 로 한다.
- **근거:** `semantic_cluster_id` 는 pass 마다 MDS 배치 순서로 재부여되어 churn 한다. 요약이
  캐시 적중하면 저장된 id 가 낡아 **엉뚱한 묶음의 요약이 붙는다**. 라벨은 스키마 내 유일화돼
  있고(`_disambiguate_labels`) 양쪽 저장소에 모두 존재한다.

## ADR-0034-03 — 2단계 조회로 schema 격리를 지킨다
- **결정:** 1단계에서 매칭 테이블의 `(scope, effective_schema, label)` 를 얻고, 2단계에서 그
  조합으로 요약을 조회한다.
- **근거:** `cluster_summaries` 식별자는 `(scope_key, schema_name, …)` 이고 그 `schema_name` 은
  **effective schema** 다. schema 를 빼고 조회하면 같은 datasource 의 다른 스키마가 같은 라벨을
  가질 때 엉뚱한 요약이 붙고(codex P1), `rag_objects.schema_name` 을 그대로 쓰면 MSSQL(리터럴
  `dbo`)에서 한 건도 안 맞는다. 유도 규칙을 SQL 로 재현하는 것보다 파이썬 계산이 정확하다.
- **드리프트 방어:** `effective_schema` 는 복제 구현이므로 테스트가 원본과의 일치를 단정한다.

## ADR-0034-04 — 매칭에 ILIKE 를 쓰지 않는다
- **결정:** `strpos(lower(질문), lower(테이블명)) > 0`.
- **근거:** `ILIKE '%' || table_name || '%'` 는 테이블명의 `_` 를 "임의의 1문자"로 해석한다.
  `backup_log_trade` 가 `backup-log-trade` 에도 매칭돼 **질문에 없는 테이블의 요약이 붙는다**.

## ADR-0034-05 — 근거 수를 요약과 함께 싣는다
- **결정:** `(멤버 N개 중 M개 상세분석 근거)` 또는 `(상세분석 근거 없음 — 이름·구조 기반 추정)`.
- **근거:** 라이브 요약의 85%가 근거 0이다. 근거를 숨기면 LLM 이 추정을 실측 결론으로 오독하고
  그 오독이 사용자 답변에 실린다. 프롬프트에도 "근거 없음은 단정하지 말라"를 명시한다 —
  표기만 하고 의미를 알려주지 않으면 무용지물이다.

## ADR-0034-06 — 세션 SET + RESET (SET LOCAL 아님)
- **결정:** `SET statement_timeout` 후 finally 에서 `RESET`.
- **근거:** `SET LOCAL` 은 트랜잭션 안에서만 유효한데 RO 연결은 autocommit 이라 **상한이 걸리지
  않는다**(codex P1). 세션 레벨로 걸되, 호출측이 준 커넥션에 설정이 누출되지 않도록 RESET 이
  반드시 짝을 이룬다.

## ADR-0034-07 — 사전 계산분만 주입한다
- **결정:** 요약이 없으면 섹션을 생략한다. 런타임 합성하지 않는다.
- **근거:** 답변 경로에 LLM 호출을 추가하면 feature-0027 이 확보한 체감 지연 개선을 통째로
  잠식한다. 없는 요약은 다음 클러스터 pass 가 만든다.
