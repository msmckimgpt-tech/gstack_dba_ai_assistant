---
doc_type: MODIFY
feature_id: feature-0028-web-perf
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260728T040500-ai-root-web-perf-p1 web 계층 성능 (A1/A2/B/C)
- 일시: 2026-07-28 / 작업자: AI (claude, branch ai/root/web-perf-p1)
- 근거: feature-0026 전수 조사 S0-1(long-poll 이 이벤트 루프 정지 + 초당 ~10 PG 연결)·
  S1-1(인증 요청당 5 SELECT + 1 UPDATE)·S0-3(요청당 MySQL 핸드셰이크).
- **A1** `routers/conversations.py` — ask_result 폴 루프의 동기 DB 구간을 `_poll_once`
  헬퍼로 분리해 `await asyncio.to_thread(...)` 로 실행(이벤트 루프 stall 제거).
- **A2** `routers/_conv_store.py` — `_ask_snapshot_pg_bundle`(kv + steps count/max +
  latest assistant 를 단일 연결·단일 왕복 — 요청당 4~5 → 2~3, 잔여는 meta 보강 경로) 신설 + `_build_ask_status_snapshot` 이 이를
  우선 사용(실패/비-PG 는 종전 개별 로더 폴백). 의미 동치 보장을 위해
  `_latest_assistant_from_rows`(행 소비 로직 공유 추출)·`_display_status_from_step_at`
  (step 시각 인자형 stale 판정, tz-aware UTC 정규화 포함) 추출.
- **B** `web_context.py` — 동적 권한 카탈로그 TTL 캐시(`WEB_PERM_CATALOG_TTL_SEC`, 기본 30s,
  복사본 반환) + `invalidate_permission_catalog_cache()`; `routers/admin_products.py` 의
  product CRUD commit 4곳에서 무효화. 세션 활동 기록 throttle
  (`WEB_SESSION_TOUCH_MIN_SEC`, 기본 60s, 세션별·키 상한 4096).
- **C** `routers/_conv_store.py` `_open_memory_connection` — `WEB_DB_POOL_ENABLED=1` 시
  `shared.db._pooled_connect` 경유(기본 OFF, 실패 시 direct connect 폴백).
- `app.py` — 신규 `_conv_store`/`web_context` 심볼 rebind(프로젝트 app.X 동적참조 규약).
- 테스트: `tests/test_web_perf_p1.py` 신규 10(번들 단일연결·폴백·stale 규칙 동치·
  to_thread 소스 잠금·캐시 히트/무효화/복사본·throttle·풀 기본 OFF).
