---
doc_type: MODIFY
feature_id: feature-0037-domain-synthesis
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260731T133000 도메인 합성(L3) lazy 신규 (Minor)

- **무엇:** 스키마 단위 도메인 개요를 **요청된 것만** 합성해 `domain_summaries` 에 적재하고,
  대화 grounding 에 함께 주입한다.
- **왜:** 클러스터 요약 1,006건이 120개 스키마에 흩어져 있어 "이 DB 가 어떤 도메인인가"를
  알려면 여전히 평균 8개를 읽어야 했다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `alembic/versions/20260731_0053_domain_summaries.py` | **신규** — 요청/생성 분리 컬럼·partial index·GRANT |
| `src/modules/domain_synthesis.py` | **신규** — 요청·대기조회·입력조립·합성·저장 |
| `src/modules/llm.py` | `DOMAIN_SUMMARY_PROMPT` + `llm_domain_summary` |
| `src/modules/cluster_context.py` | 도메인 요약 주입 + 없으면 요청(별도 RW 연결) |
| `src/modules/insight.py` | advisory lock 아래에서 합성 pass |
| `shared/config.py` · `shared/runtime_settings.py` | knob 2종(live) |
| `tests/test_domain_synthesis.py` | **신규** 30건 |
| `tests/test_worker_parallelism.py` | `PERF_KEYS` +2 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 사전 전량 생성 퇴화 | `requested_at IS NOT NULL` 조건 — 요청 없으면 합성 0 |
| 답변 지연 | 요약 있으면 RO 조회 1회, 없으면 UPSERT 1회. LLM 0 |
| 재생성 누락 | 해시에 카운트 포함 + cap 전 전체 집합으로 계산 |
| 중복 합성 | advisory lock 아래에서만 실행 |
| 조회 성능 | 미생성분을 partial index 로 먼저 조회 |
| RO 연결 쓰기 실패 | 요청은 별도 RW 연결 |

### 배포 scope
워커 + web. `make deploy-all`.
