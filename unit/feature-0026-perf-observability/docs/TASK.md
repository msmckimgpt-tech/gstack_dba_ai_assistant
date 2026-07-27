---
doc_type: TASK
feature_id: feature-0026-perf-observability
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_date: 2026-07-27
feature_status_note: 성능 관측 인프라 신규 — HTTP per-route 타이밍·요청당 DB conn 카운터(admin_perf)·워커 LLM latency 백필(13 sites)·답변 파이프라인 단계 계측(redteam/post-answer/grounding)·graph-sync duration·perf-snapshot CLI·Caddy access log (전수 성능 조사 기반, 측정 전용·사용자 가시 동작 변경 0·§18.8 3렌즈 패널 흡수)
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude, /_template:entry 자율 dispatch)
- Priority: high
- Last Updated: 2026-07-27

## 2. Implementation Plan

### 2.1 Plan (§7.1 — 2026-07-27 전수 성능 조사 기반)

**배경 (측정으로 확인된 병목 지도 요약, 라이브 7일)**: 답변 1건 평균 141s = agent LLM
87.8s(62%) + redteam 파이프라인 46.4s(33%) + 잔여 ~7s. AGE cypher 590만 회/12.5d 가
PG 부하 지배. RO 핫패스는 pgbouncer 우회 replica 직결 + 커넥션 풀 0(요청당 수십 회
connect). MySQL buffer pool 128MB(기본값)/데이터 48GB. 계측 사각: HTTP per-route 축
전무·워커 LLM latency NULL·redteam/post-answer/grounding 분해 부재·pgbouncer 풀 사용률
무관측. 본 cycle 은 **측정 인프라만** 구축한다 (개선은 후속).

- **영향받는 파일 / symbol:**
  - `shared/perf_counters.py` (신규) — `activate/deactivate/incr/current` 요청-스코프 카운터.
  - `shared/db.py` — `_pg_connect`/`_pg_connect_ro` 성공 직후 `perf_counters.incr` 1줄씩.
  - `unit/feature-0003-agent-web-ui/src/perf_metrics.py` (신규) — `PerfTimingMiddleware`,
    `record()`, `snapshot()`, 버킷 히스토그램 p50/p95, slow ring, 주기 로그 flush.
  - `unit/feature-0003-agent-web-ui/src/app.py` — 미들웨어 등록 1곳 + `_connect_memory` 카운터 1줄.
  - `unit/feature-0003-agent-web-ui/src/routers/admin_perf.py` (신규) — `GET /api/admin/perf/http`
    (`Depends(app.require_permission("console.aiops.read"))`, INCLUDE_ORDER=250, read-only).
  - `unit/feature-0002-agent-core/src/modules/llm.py` — `_record_llm_usage` 호출부 13곳에
    perf_counter_ns 왕복 측정 추가 (validate/summary/classify/topic/glossary_suggest/enum_suggest/
    sql_fix/schema_insight/table_insight/account_insight/node_analysis/product_classify/cluster_label).
  - `unit/feature-0002-agent-core/src/agent_core.py` — `_build_knowledge_context` 단계 타이머
    (ContextVar `_KNOWLEDGE_TIMINGS`), redteam 구간 `_rt_ms`, post-answer 구간 `_pa_ms`
    (KV `last_post_answer_ms`), `_ans_breakdown["redteam_ms"/"init_detail"]` additive 키.
  - `unit/feature-0002-agent-core/src/modules/metadata_graph.py` — `sync_graph` rep `duration_ms`.
  - `unit/feature-0002-agent-core/src/modules/insight.py` — cycle payload 에 node_analysis
    (claimed/done/failed) + relationships_probe_* 카운터 포함, should_log 확장.
  - `bin/perf-snapshot.sh` (신규) — 전 신호 집계 CLI → `artifacts/perf/<ts>/`.
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — `log` 지시어 (stdout JSON).
  - 테스트: `unit/feature-0003-agent-web-ui/tests/test_perf_metrics.py` (신규),
    `unit/feature-0002-agent-core/tests/test_llm_latency_backfill.py` (신규).
- **접근 방법:** 전부 additive·fail-open. 동작 변경 0 (측정값 기록만). 신규 권한·스키마·
  UI 표면 0. 미들웨어는 순수 ASGI(BaseHTTPMiddleware 회피 — 오버헤드/스트리밍 간섭 최소).
  route 식별은 응답 후 `scope["route"].path` (미매칭 = `(unmatched)` 그룹 — 카디널리티 유계).
- **완료 판정 기준:** FUNCTION.md AC-1~6 (각 항목 라이브 검증 포함 — §16.3 deploy-backed).
- **위험도:** Minor (비파괴 additive 계측·내부 API 1개·기존 권한 재사용·스키마 변경 0).
  단 라이브 핫패스 관통 코드이므로 §18.8 panel (backend/qa/security) 실행.

## 3. Task Queue
- [x] TASK-20260727T091000-perf-obs-survey 전수 성능 조사 (4 병렬 탐색 + 라이브 관측) — 병목 지도 확정
- [x] TASK-20260727T091001-perf-obs-m1 M1 web HTTP 타이밍 미들웨어 + admin_perf 라우터
- [x] TASK-20260727T091002-perf-obs-m2 M2 워커 LLM latency 백필 (13 sites)
- [x] TASK-20260727T091003-perf-obs-m3 M3 답변 파이프라인 단계 계측 (redteam/post-answer/grounding)
- [x] TASK-20260727T091004-perf-obs-m4 M4 graph sync duration + insight payload 확장
- [x] TASK-20260727T091005-perf-obs-m5 M5 bin/perf-snapshot.sh
- [x] TASK-20260727T091006-perf-obs-m6 M6 Caddy access log
- [ ] TASK-20260727T091007-perf-obs-verify 테스트 + make test + 문서 재정합 + §18.8 panel
- [ ] TASK-20260727T091008-perf-obs-deploy 배포 + replica pg_stat_statements + 라이브 실측
  - 배포 검증 체크(§18.8 C-5): Caddy 버전 확인 + access log 에 Authorization/Cookie 가
    REDACTED 인지 docker logs 실측 1회 (미충족 시 log 필드 제한 hotfix)

## 4. Blocked
(없음)

## 7. Completion Checklist
- [x] 모든 REQ 의 AC 가 구현되었다 (AC-1~6 — 라이브 검증 항목은 배포 단계)
- [x] 자동 테스트가 통과한다 (make test — 신규 9 PASS·회귀 0·환경성 baseline 문서화)
- [x] UI 표면 없음 — PB-0008 비대상 사유: 정적/템플릿/HTML 변경 0, JSON API 만 (§15.4.1 예외 명시)
- [x] FUNCTION.md 가 현재 동작과 일치한다
- [x] MODIFY/REVIEW/REPORT/TEST 갱신
- [ ] verify-completion --pre-commit PASS
- [ ] 커밋 + push + PR + 머지 + 배포 (deploy_scope: included) + 라이브 재배포 검증
