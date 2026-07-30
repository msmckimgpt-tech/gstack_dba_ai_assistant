---
doc_type: MODIFY
feature_id: feature-0032-llm-token-budget
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260730T071120 백그라운드 LLM 토큰 예산 신규 (Major, cross-cut)

- **무엇:** 사람이 요청하지 않은 자동 LLM 지출에 rolling 24시간 토큰 상한을 도입한다. 상한 도달
  시 새 백그라운드 작업이 다음 주기로 밀리고, 콘솔에 현황·경고가 뜬다. 사용자 요청 경로는
  집계·차단 양쪽에서 제외한다.
- **왜:** `TODOS.md` P3 의 종결 근거("100% edge → 과금 없음")가 실측에서 반전됐다 —
  7일 Anthropic 8,654콜/55,567,176 토큰 vs edge 25콜. 자동 지출에 상한이 없던 상태였다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `shared/llm_budget.py` | **신규** — rolling 24h 집계 · 사용자 경로 제외 · 60초 캐시 · fail-open · snapshot |
| `shared/config.py` | `AGENT_BACKGROUND_LLM_TOKEN_CAP_24H` 기본 20,000,000 |
| `shared/runtime_settings.py` | `_PERF_SPECS` 에 상한 knob(`apply_mode: live`) |
| `node_analysis.py` | `_process_pending_inner` claim 전 게이트 → `skipped="llm_token_budget"` |
| `semantic_cluster.py` | `run_cluster_maintenance` 래퍼 게이트 |
| `product_classify.py` | `run_classify_pass` 래퍼 게이트 |
| `routers/ai_ops.py` | 응답에 `llm_token_budget` + attention 2단계(80% watch / 도달 degraded) |
| `static/admin.js` | 'AI 운영 현황' 에 예산 막대·비율·면제 안내 렌더 |
| `tests/test_llm_token_budget.py` | **신규** — 사용자 보호·fail-open·게이트·캐시·snapshot |
| `tests/test_llm_budget_pane.py` | **신규** — 렌더 배선 단정(T0b 오보 재발 방지) |
| `tests/test_worker_parallelism.py` | `PERF_KEYS` +1 |
| `TODOS.md` | P3 항목 전제 반전 기록(옛 disposition 보존 + 반전 사실 병기) |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 사용자 답변이 예산에 막힘 | `USER_FACING_TASKS` 를 집계·게이트 양쪽에서 제외. 제외가 실제 SQL 에 반영되는지 테스트가 파라미터를 직접 검사 |
| 계량 장애 → 백그라운드 정지 | fail-open 3중(상한 0·조회 실패·모듈 부재). 콘솔은 "조회 불가"를 "상한 없음"과 다른 문구로 표시 |
| 배포 즉시 차단 발생 | 기본 상한이 24h 실측(685만)의 약 3배(2,000만) — 정상 운영 무영향 |
| 게이트 커버리지 오해 | 96%(3개 진입점)라는 사실을 코드 주석·FUNCTION·콘솔 설명에 명시 |
| PG 부하 | `ix_llm_usage_created` 인덱스 사용 + 60초 캐시(테이블 71,480행/16MB) |

### 배포 scope
워커 + web. `make deploy-all`.

### 교차 참조
- `shared/docs/MODIFY.md` — `llm_budget` 신규, `config`·`runtime_settings` 확장
- `docs/improvements/analysis-orchestration/ROADMAP.md` — ITEM-12(T2 진입 게이트)
- `unit/feature-0007-bedrock-llm-provider/docs/FUNCTION.md` — provider fallback 체인(계정 구분 근거)
