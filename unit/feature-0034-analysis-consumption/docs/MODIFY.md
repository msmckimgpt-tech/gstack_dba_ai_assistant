---
doc_type: MODIFY
feature_id: feature-0034-analysis-consumption
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260730T090500 L2 요약의 대화 grounding 주입 (Major, 답변 경로)

- **무엇:** 질문이 언급한 테이블이 속한 묶음의 요약 1~2건을 답변 컨텍스트에 주입한다.
  근거 수(`analyzed_count/member_count`)를 함께 싣고, 근거 없는 요약은 "추정"으로 표기한다.
- **왜:** RI-5 — 분석 1만여 건과 클러스터 요약이 쌓였는데 답변 경로가 읽지 않아 콘솔 열람에만
  갇혀 있었다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `src/modules/cluster_context.py` | **신규** — 2단계 매칭·조회·렌더·스위치·fail-soft |
| `src/agent_core.py` | `_build_knowledge_context` 에 `TABLE GROUP SUMMARIES` 섹션 주입 + `cluster_summary_ms` 계측 |
| `shared/config.py` · `shared/runtime_settings.py` | `AGENT_CLUSTER_SUMMARY_GROUNDING`(live) |
| `tests/test_cluster_grounding.py` | **신규** 28건 |
| `tests/test_worker_parallelism.py` | `PERF_KEYS` +1 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 답변 지연 증가 | 사전 계산분만(런타임 합성 0) · 가벼운 쿼리 2회 · statement_timeout 1.5s(SET+RESET) · 매칭 0건이면 2단계 생략 · `cluster_summary_ms` 계측 |
| 실패가 답변을 막음 | 전 구간 fail-soft. `cursor()` 획득도 try 안 |
| 프롬프트 인젝션 | `_datamark_untrusted` + "지시 아님" 헤더 |
| 엉뚱한 요약 주입 | 라벨 조회(cluster_id churn 회피) + `(scope, effective_schema, label)` 3중 격리 + strpos(ILIKE 와일드카드 회피) |
| 추정을 실측으로 오독 | 근거 수 병기 + 프롬프트의 "단정하지 말라" 지시 |

### 배포 scope
web + 워커(ask-worker 가 답변을 처리). `make deploy-all`.

### 교차 참조
- `unit/feature-0033-analysis-synthesis/docs/FUNCTION.md` — 주입 대상 요약의 생성
- `docs/improvements/analysis-orchestration/ROADMAP.md` — ITEM-09
