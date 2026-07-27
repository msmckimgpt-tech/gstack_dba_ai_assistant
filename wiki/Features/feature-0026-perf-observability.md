---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: active
ai_generated: true
feature_id: feature-0026-perf-observability
linked_unit: unit/feature-0026-perf-observability
sources:
  - ../../unit/feature-0026-perf-observability/docs/FUNCTION.md
---

# Feature — 성능 관측 인프라 (perf observability)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0026-perf-observability/docs/FUNCTION|unit/feature-0026-perf-observability/docs/FUNCTION.md]].

## 1. 한 줄 요약

성능 병목을 **정량 측정**하기 위한 additive·fail-open 계측 — web HTTP per-route 지연+요청당
DB 커넥션(`/api/admin/perf/http`), 워커 LLM latency 백필, 답변 파이프라인 단계 분해
(redteam/post-answer/grounding), graph-sync duration, 전신호 집계 CLI(`bin/perf-snapshot.sh`),
Caddy access log. **동작 변경 0 — 측정만 추가** (개선은 측정치 기반 후속 cycle).

## 2. 상태

- **active** (2026-07-27 신규 — 전수 성능 조사에서 확인된 계측 사각 B1~B9 중 6개 해소).
- 코드 거주: feature-0002(llm/agent_core/insight/metadata_graph)·feature-0003(perf_metrics·admin_perf)·
  feature-0006(Caddyfile log)·shared(perf_counters)·repo-level bin.

## 3. 책임 경계

- **함:** HTTP 타이밍 미들웨어(순수 ASGI)·요청-스코프 conn 카운터·LLM latency 전 task 기록·
  duration_breakdown additive 키(redteam_ms/init_detail)·KV last_post_answer_ms·sync/insight
  payload 확장·perf-snapshot 집계·edge access log.
- **안 함(이연):** 병목 개선 자체(버퍼풀·풀링·gzip·폴링 개선), 관측 UI 표면, Prometheus 류
  외부 스택, DB 스키마 변경.

## 4. 관련 정본

- 기능 계약: [[../../unit/feature-0026-perf-observability/docs/FUNCTION|FUNCTION.md]] (AC-1~6)
- 계획·병목 지도 요약: [[../../unit/feature-0026-perf-observability/docs/TASK|TASK.md]] §2.1
- 방향 앵커: [[../../unit/feature-0026-perf-observability/docs/ANCHOR|ANCHOR.md]]
- 리뷰: [[../../unit/feature-0026-perf-observability/docs/REVIEW|REVIEW.md]]

## 5. 관련 노트

- feature-0025 worker-parallelism (병렬 knob 튜닝의 전제 계측 — 워커 LLM p95 가 이제 측정됨).
- feature-0016 metadata-graph (§82 pgbouncer 풀 소진 사건 — SHOW POOLS 감시가 스냅샷에 포함).
- 2026-07-27 전수 성능 조사: 답변 141s = LLM 62% + redteam 33%, AGE cypher 지배, RO 경로
  pgbouncer 우회, MySQL buffer pool 128MB (개선 후보 원장은 unit REPORT §8).

## 6. Open questions / 미해결

- replica pg_stat_statements preload(운영 env — 배포 단계 적용 여부), post-answer 구간의
  표시 duration 편입 여부(후속 UX 결정), 개선 cycle 우선순위 확정.

## 7. 변경 이력 (이 카드)

- 2026-07-27: 신규 생성 (feature-0026 구현 동반).
