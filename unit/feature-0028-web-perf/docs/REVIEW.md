---
doc_type: REVIEW
feature_id: feature-0028-web-perf
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260728T040500-ai-root-web-perf-p1 설계 판단 근거
- Related TASK: feature-0028-web-perf / Timestamp: 2026-07-28T04:05:00Z
- **왜 to_thread 인가**: uvicorn 워커가 replica 당 1개라 async 본문의 blocking DB 가 그
  replica 전체를 멈춘다. 핸들러를 sync 로 강등하면 long-poll 이 threadpool 슬롯(40)을
  장시간 점유하므로, async 유지 + DB 구간만 스레드 위임이 정답.
- **번들 폴백 유지 이유**: PG 미가용·비-PG 백엔드에서 스냅샷이 죽으면 long-poll 이
  영구 timeout 된다. 신규 경로는 항상 "실패 시 종전 경로" 계약.
- **행 소비 로직을 공유 추출한 이유**: 번들이 자체 파싱을 구현하면 `_is_internal_message`·
  step 보강 규칙이 두 곳에서 갈라진다(silent drift). 한 함수를 두 경로가 호출.
- **카탈로그 캐시가 안전한 이유**: 캐시 대상은 코드 목록이지 부여/집행이 아니다. product
  CRUD 무효화 + TTL 상한 + 복사본 반환(호출측 변형 격리).
- **풀은 왜 기본 OFF**: web 전 요청 blast radius. feature-0026 의 `db_per_req` 로 라이브
  효과를 관측한 뒤 켜는 것이 안전(토글만으로 즉시 revert).
- 사전 승인: deploy_scope: included. PB-0008 비대상(백엔드 경로·정적 자산 무변경).

## REV-20260728T133000-ai-root-web-perf-p1 [AGENT-TEAM: SHIP-WITH-FIXES]
- **Related Change:** feature-0028 web 계층 성능 (CHG-20260728T040500).
- **Panel:** §18.8 2-렌즈 적대 리뷰 — ①backend/concurrency ②qa/regression skeptic.
- **Trigger:** performance/latency/caching + API/endpoint keyword matched.
- **Verdict:** backend **BLOCK** → 전 결함 in-cycle 수정 후 SHIP. **Timestamp:** 2026-07-28T13:30:00Z

### 수용·수정한 결함
- **[backend B-1, 치명]** `_latest_assistant_from_rows(bundle...)` 호출이 인자 3개 중 1개만
  전달 — 라이브 PG 백엔드에서 **모든 스냅샷이 TypeError**(`/api/ask_status`·`/api/ask_result`
  500, `/api/ask` attach 는 terminal 미검출로 답변 미전달). **FIX:** `(conn, conversation_id,
  rows)` 정정. **역검증 완료** — 버그를 되돌리면 신규 differential 테스트 3건이 실패함을 실증.
- **[backend B-2]** 신규 테스트가 컴포넌트 단위·소스 잠금뿐이라 합성 함수의 동치 주장(AC-2)을
  구조적으로 검증 못 함(그래서 B-1 을 놓침). **FIX:** `_build_ask_status_snapshot` 을 번들
  경로 vs 폴백 경로로 각각 실행해 **dict 전체 동등**을 assert 하는 differential 테스트 4건
  (terminal+answer / processing-fresh / processing-stale / run_id 없음).
- **[backend B-3]** ANCHOR·FUNCTION(둘 다 source_of_truth)의 "캐시는 부여·집행과 무관" 주장이
  거짓 — 카탈로그는 `_decorate_account_rows`→`_apply_permission_overrides` 에서 effective
  permission map 을 게이트한다. **FIX:** 두 문서 정정 — 게이트함을 명시하되 **fail-closed**
  (신규 코드는 TTL 동안 거부로 읽힘, 상승 불가)·상한은 **replica 별 TTL** 로 서술.
- **[backend C-1]** "PG 연결 4~5→1" 과장(답변 meta 보강 경로가 자체 연결). **FIX:** AC/MODIFY 를
  "주 조회 3종 단일 왕복 → 요청당 2~3" 으로 정정.
- **[backend C-2]** 무효화는 처리 replica 한정. **FIX:** AC-3·ANCHOR 에 명시.
- **[backend C-3/C-4]** 풀 활성 전 선결조건(pool_size vs long-hold 동시성, `_pool_key` 에
  timeout 부재로 인한 web 쿼리 타임아웃 소실 가능). **FIX:** AC-4 에 선결 2건 명문화(기본 OFF 유지).
- **[backend C-6]** 신규 env 3종이 `.env.example` 미등재(§14 위반) + 스크래치 테스트 파일 잔류.
  **FIX:** `.env.example` 3종 주석과 함께 등재, 스크래치 파일 삭제.

### 패널이 결함 없음으로 확증한 것
kv 쿼리 동치(+번들 실패 시 폴백이 오히려 안전)·step_count run_id 게이트·tz 정규화 동치
(CHG-20260527-0001 회귀 무재발)·`_is_internal_message` dict→str 사전 직렬화·MySQL 폴백 격리·
캐시 race 안전(무효화 순서·복사본 반환)·세션 throttle race 무해(중복 UPDATE 뿐, LastSeenAt 은
어디서도 SELECT 안 함)·§9.7 감사 IP 무영향·무효화 훅 배치(런타임 `WebPermissions` 변경 경로
누락 0)·**A1 threadpool 분리 확증**(to_thread 는 loop 기본 executor, sync 핸들러의 anyio
CapacityLimiter(40) 와 disjoint — starvation 없음, 순 이득).
- **Human Approval Needed:** no (Minor~Major·가역·응답/인가 불변·deploy_scope: included).

### qa 렌즈 추가 결함 흡수 (같은 패널, 독립 확인)
- **[qa B1]** backend B-1 과 동일 결함을 독립 재현(라이브 `.env` PG 백엔드 실증) — 수정 동일.
  추가로 **번들 소비 구간 예외 폴백**을 붙여 "신규 경로 실패 시 종전 경로" 계약을 실제로 성립시킴.
- **[qa C1, 신규]** `_display_status_from_step_at` 이 원본의 문자열 폴백을 버려, 드라이버/캐스팅
  변화로 non-datetime 이 오면 **살아있는 run 이 stale_error 로 오종결**(CHG-20260527-0001 거울상).
  **FIX:** `_parse_kv_timestamp(str(...))` 폴백 복원.
- **[qa B3, 채택안 변경]** 카탈로그 캐시가 인가 집행 맵의 키 우주를 좁힘(실증: stale 시 부여된
  `product.access.*` 가 effective 에서 탈락). **FIX:** 집행 경로 `use_cache=False` 로 **캐시 제외** —
  인가 정확성 무거래. B 의 핫패스 이득은 세션 UPDATE 1회 제거로 한정(문서 정직 정정).
- **[qa C3]** `_WEB_DB_POOL_ENABLED is False` 단언은 배포 설정 의존 — 운영에서 켜면 CI 적색.
  **FIX:** 파싱 규칙 검증으로 대체.
- **[qa C4]** `/api/progress` 는 미변경인데 측정 기준에 포함(충족 불가). **FIX:** 기준 삭제.
- **[qa C5]** 번들 실패가 무로그 → 상시 폴백해도 개선 주장 검증 불가. **FIX:** warning 2종 추가.
- **[qa C6]** 카탈로그 캐시 전역 누수(향후 순서 의존 flake). **FIX:** autouse fixture 전후 무효화.
- **[qa C7]** throttle 타임스탬프를 due 판정 시 기록 → 실패한 UPDATE 가 재시도 안 됨.
  **FIX:** `_session_touch_done` 분리(성공 후 기록) + 테스트.
- **[qa 도전 수용]** "신규 N건 PASS = 계약 불변" 서사 반례(10/10 PASS 상태로 엔드포인트 500).
  이번 cycle 은 **역검증**(버그 되돌려 테스트가 실패함을 실증)을 도입해 보완 — REPORT 에 기록.
- **[qa 확증]** 기존 스위트 실행(feature-0003 959 passed / 7 fail=main 동일 baseline),
  동치성 실증(수정 시뮬레이션 후 dict 전 필드 일치), threadpool 분리(A1 순이득) 재확인.
