---
doc_type: FUNCTION
feature_id: feature-0028-web-perf
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

# 1. Summary
feature-0026 전수 성능 조사가 지목한 **web 계층 병목**(S0-1 이벤트 루프 stall·요청당 DB
연결 다발·인증 5왕복)을 제거한다. 응답 shape·인가 경계·기능 동작은 불변 — 같은 결과를
더 적은 연결·더 짧은 블로킹으로 낸다.

## 2. Goal
- REQ-20260728-web-perf: web 요청 처리 오버헤드 제거 (사용자 지시 2026-07-28 "web-perf slice 진행").
  - AC-20260728T040000-web-perf-1 (**A1**): `/api/ask_result` long-poll 의 스냅샷 조회가
    `asyncio.to_thread` 워커 스레드에서 실행된다 — async 본문의 blocking DB 호출로 인한
    이벤트 루프 정지(uvicorn 워커 replica 당 1개) 제거.
  - AC-20260728T040000-web-perf-2 (**A2**): 스냅샷의 **주 조회 3종**(kv + step count/max +
    latest assistant)이 **단일 연결·단일 왕복 번들**로 수행된다 — 호출당 PG 연결 4~5 → **2~3**
    (§18.8 backend C-1 정정: 답변 meta 보강 경로 `_load_step_meta`/`_load_steps_for_message`
    가 자체 연결을 여는 잔여분. 그 축소는 후속).
    PG 미가용/비-PG 백엔드는 종전 개별 로더로 폴백(shape·의미 불변).
  - AC-20260728T040000-web-perf-3 (**B**): 세션 활동 기록(LastSeenAt/RemoteAddr/UserAgent
    **UPDATE**)이 최소 간격 throttle(기본 60s) 뒤로 — 요청당 **쓰기 1회 제거**가 B 의 주
    이득이다. 동적 권한 카탈로그 TTL 캐시는 **인가 집행 경로에서 제외**하고(§18.8 B-3/qa B3 —
    stale 카탈로그가 effective 맵의 키 우주를 좁혀 replica 별 비결정적 403 을 만들 수 있음)
    admin 조회 경로(roles/accounts/console)에만 적용한다. 즉 **인증 핫패스의 SELECT 5 는
    그대로**이고, 줄어드는 것은 UPDATE 1 이다(과대 주장 정정). 세션
    LastSeenAt/RemoteAddr/UserAgent 갱신은 최소 간격 throttle(기본 60s,
    `WEB_SESSION_TOUCH_MIN_SEC`). 둘 다 0 이면 종전 동작.
  - AC-20260728T040000-web-perf-4 (**C**): web memory MySQL 연결이 opt-in 풀
    (`WEB_DB_POOL_ENABLED=1`)을 경유한다 — 기본 OFF, 풀 소진/실패 시 direct connect 폴백.
    **활성 전 선결(§18.8 backend C-3/C-4)**: ① `AGENT_DB_POOL_SIZE`(기본 8)를 long-hold
    요청(`/api/ask` attach 는 대기 동안 conn 점유) 동시성 대비 산정 — 미달 시 매 대여가
    `db_pool_exhausted` WARNING + direct connect 로 떨어져 이득 0·로그 폭주.
    ② `shared.db._pool_key` 는 (host,port,user,database) 라 read/write timeout 이 키에
    없다 — `AGENT_DB_POOL_ENABLED=1` 과 동시 사용 시 web 의 쿼리 타임아웃이 소실될 수
    있으므로 둘을 함께 켜지 않거나 키/풀명을 분리한 뒤 활성한다.

## 3. In Scope
- `routers/conversations.py` ask_result 폴 루프, `routers/_conv_store.py`
  (`_ask_snapshot_pg_bundle`·`_display_status_from_step_at`·`_latest_assistant_from_rows`·
  `_open_memory_connection` 풀 분기), `web_context.py`(카탈로그 캐시·세션 throttle),
  `routers/admin_products.py`(무효화 훅 4), `app.py`(심볼 rebind).

## 4. Out of Scope
- 사이드바 배지 전용 엔드포인트·`/api/progress` 접근검사 3연타 병합·uvicorn --workers
  (후속 slice). 정적 자산 압축/캐시는 feature-0027 에서 완료.
- 폴링→SSE/LISTEN-NOTIFY 전환(설계 변경 규모 — 별도 initiative).

## 6. Outputs
- 동일 JSON 응답 shape. 관측: `GET /api/admin/perf/http` 의 `db_per_req`(feature-0026)로
  **`/api/ask_result`** 의 요청당 PG 연결 감소를 대조한다. **`/api/progress` 는 본 cycle 이
  손대지 않았으므로 측정 기준에서 제외**(§18.8 qa C4 — 과대 기준 삭제). 번들 상시 실패는
  web 로그 `ask_snapshot_bundle_failed`/`..._consume_failed` 로 관측(qa C5).

## 8. Edge Cases
- 번들 실패/비-PG → 개별 로더 폴백. 카탈로그 캐시는 **복사본** 반환(호출측 변형 격리).
- 세션 throttle 은 세션별 독립 + 키 상한(4096) 초과 시 전체 비움(메모리 유계).
- 풀 경로 예외 → direct connect. `SET SESSION` 2문은 대여마다 유지(세션 상태 일관).

## 9. Non-functional
- **인가 정확성은 거래하지 않는다**: 카탈로그 캐시를 집행 경로에서 뺐으므로 effective
  permission map 은 종전과 동일하게 매 요청 실조회로 산출된다(§18.8 B-3 해소). 캐시가 남은
  admin 조회 경로는 신규 코드가 최대 TTL·replica 별로 늦게 보일 수 있다(표시 지연, fail-closed).
- LastSeenAt 은 최대 throttle 간격만큼 지연 기록 — UPDATE **성공 후** 기록이라 실패는 다음
  요청에서 재시도된다(qa C7). §9.7 감사 IP 는 WebAuditEvents 별 경로라 계약 유지.

## 10. Dependencies
- feature-0026 계측(전/후 측정 수단). deploy_scope: included (전역).
