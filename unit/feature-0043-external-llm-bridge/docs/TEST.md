---
doc_type: TEST
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. 테스트 전략

이 feature 가 방어해야 하는 것은 두 가지이고, 둘 다 "함수가 잘 동작한다" 로는 부족하다.

1. **차단이 기본값이고, 그 차단이 실제 호출 경로 위에 있다.** 게이트 함수만 검사하면 아무도 그것을
   부르지 않는 배선 끊김을 놓친다. 그래서 `_get_llm_client()` 가 `None` 을 반환할 때
   **게이트를 경유했다는 사실**까지 단정한다 — 자격증명 부재로 우연히 `None` 인 것과 구분되지 않으면
   vacuous pass 다. 역방향(게이트를 열면 차단 경로를 타지 않는다)도 함께 본다.
2. **무설치 계약이 코드로 강제된다.** 러너의 import 를 AST 로 전수 검사한다(문자열 스캔은 주석 속
   설명과 실제 import 를 구분하지 못한다).

## 2. 테스트 케이스

| ID | 대상 | 검증 | AC |
|---|---|---|---|
| TEST-20260826T135206-gate-default | `server_llm_enabled()` | env 부재 시 False. truthy 6종 True / non-truthy 6종 False | AC-1 |
| TEST-20260826T135206-gate-wiring-1 | `_get_llm_client()` | 계정 alias 14종 전건 `None` **+ 게이트 경유 단정** | AC-1 |
| TEST-20260826T135206-gate-wiring-2 | `_get_llm_client()` | 게이트 개방 시 차단 경로 미경유 (뮤테이션 역검증) | AC-1 |
| TEST-20260826T135206-gate-wiring-3 | `agent_core._run_agent_core` | 게이트 호출 + 사유 전달 + **클라이언트 생성부보다 앞** | AC-1 |
| TEST-20260826T135206-honest-fail | `note_server_llm_blocked()` | 로그 기록 · caller별 throttle · 사용자 문구에 내부 식별자 부재 | AC-8 |
| TEST-20260826T135206-config-lock | `litellm_config.yaml` | 활성 `ANTHROPIC_API_KEY` 참조 0 · 활성 chat alias 0 · YAML 유효 · 되돌리기 문서화 | AC-2 |
| TEST-20260826T135206-embedding-kept | `litellm_config.yaml` | `titan-embed` 활성 유지 (부수 피해 방지) | AC-7 |
| TEST-20260826T135206-runner-stdlib | `bridge_runner.py` | AST import 전수 → `sys.stdlib_module_names` 밖 0건 · `mcp` 부재 · TLS 검증 무력화 스위치 부재 | AC-9 |
| TEST-20260826T135206-alias-transition | 기존 alias 계약 3파일 | 전환 상태에서 대체 계약 단정, 되돌리면 원 계약 복원 | — |
| TEST-20260828T070000-cancel-single-source | `shared/bridge_tasks.py` · 두 라우터 | 취소 술어가 shared 에만 정의 · 라우터는 참조만 · 웹 라우터에 취소 SQL ≤1벌 | AC-59 |
| TEST-20260828T070000-cancel-two-branches | `cancel_bridge_tasks` | 미점유 DELETE / 점유 `canceled` · lease 판정 경유 · 계정 스코프 · 대상 미지정 시 no-op | AC-60 |
| TEST-20260828T070000-cancel-wiring | `cancel_request` | 브리지 취소 호출 + 말풍선 갱신 + **서버 run 취소보다 앞**(그쪽 실패가 이쪽을 삼키지 않게) | AC-58 |
| TEST-20260828T070000-cancel-failure-surfaced | `cancelCurrentRun` | `bridge_cancel_failed` 반영 + 감시 정리(`abandonBridgeTasks`) | AC-58 |
| TEST-20260828T070000-supersede | `_enqueue_web_bridge_task` | 이전 대기 대체 · `exclude_task_id` · **적재 성공 뒤** 실행 · 결과 전파 | AC-62 |
| TEST-20260828T070000-supersede-frontend | `handleBridgePending` | 대체 task 감시를 **새 폴러보다 먼저** 끊는다 | AC-62 |
| TEST-20260828T070000-cancel-channel | `wait_for_request` | 취소로도 즉시 반환 · `canceled_task_ids` · 점유자 스코프 · **명시 도구 7종 불변** | AC-63 |
| TEST-20260828T070000-submit-409 | `submit_answer` | 취소된 task 409 · 판정이 각인·저장 **앞** | AC-61 |
| TEST-20260828T070000-stream-counted | `bridge_stream` | `_counted_stream` 경유(배포 pre-drain 계량) · SSE 헤더 · 버퍼링 차단 | AC-64 |
| TEST-20260828T070000-stream-bounded | `bridge_stream` | 55초 서버 고정 상한 · `reconnect` 프레임 · 클라이언트가 대기시간 지정 불가 | AC-64 |
| TEST-20260828T070000-stream-auth-first | `bridge_stream` | 인증·소유 확인이 스트림 오픈 **앞**(그 뒤면 401/403 불가) · 계정 스코프 · 끊김 감지 | AC-64 |
| TEST-20260828T070000-stream-transient | `_bridge_stream_snapshot` | DB 장애를 '취소됨'(None)으로 오인하지 않는다 | AC-64 |
| TEST-20260828T070000-live-steps | `_bridge_live_steps` | 원장 출처 · `reason_text` 부재(지어내지 않음) · 진행도구 필터 공유 | AC-64 |
| TEST-20260828T070000-phase-order | `_bridge_phase` | `canceled` 가 `working` 보다 앞(아니면 취소가 영원히 '처리 중') · 5종 · 두 소비처 공용 | AC-64 |
| TEST-20260828T070000-stop-button | `renderComposer` · sendBtn 핸들러 | 브리지 대기 중 중단 버튼 노출 · 렌더와 클릭이 **같은 술어** | AC-58 |
| TEST-20260828T070000-no-send-block | `_bridgePendingHere` · `sendPrompt` | 브리지 대기를 in-flight 로 승격하지 않는다(대기 중 새 질문이 막히지 않게) | AC-58 |
| TEST-20260828T070000-runner-parallel | `bridge_agent.py` | 기본 동시 처리 · 세마포어 상한 · **자리 확보가 서버 질의보다 앞**(tight loop 방지) | AC-65 |
| TEST-20260828T070000-runner-cancel | `bridge_agent.py` | 취소 원장 락 보호 · `Popen`+kill · 실행 중·제출 직전 2회 확인 · 취소≠실패 구분 | AC-65 |
| TEST-20260828T070000-runner-claim-site | `handle_one` | 점유는 대기 루프에서(워커로 미루면 같은 task 반복 수신) | AC-65 |
| TEST-20260828T070000-runner-once | `main` | `--once` 가 워커 완료를 기다린다(daemon 스레드 조기 종료 방지) | AC-65 |
| TEST-20260828T070000-fallback | `_pollBridgeAnswer` | SSE 실패 시 폴링 폴백 · 두 경로가 같은 렌더·4xx 판정 | AC-64 |

| TEST-20260828T150000-hb-extends | `oauth_store.heartbeat` | 유효 토큰 → 연장 UPDATE 1회 · `LastHeartbeatAt` 기록 · 응답에 주기/수명 | AC-66 |
| TEST-20260828T150000-hb-no-resurrect | `oauth_store.heartbeat` | 로그아웃·세션만료·토큰폐기·토큰만료·refresh **5종 전건** UPDATE 미발행 | AC-66 |
| TEST-20260828T150000-hb-no-inversion | `oauth_store.heartbeat` | `GREATEST`(만료 앞당김 금지) · `LEAST(…, s.ExpiresAt)`(세션 초과 금지) · 대상 토큰 1행 | AC-66 |
| TEST-20260828T150000-hb-predicate | `account_is_heartbeating` | 살아있음 술어 + 최근성 동시 요구 · 창 경계 양측 · 계정 0 은 조회조차 안 함 | AC-67 |
| TEST-20260828T150000-hb-single-predicate | `oauth_store` | 두 판정이 `_LIVE_TOKEN_PREDICATE` 하나를 공유(복제본 금지) | AC-67 |
| TEST-20260828T150000-listening-2axis | `account_is_listening` | 하트비트 축이 원장보다 **먼저**(일하는 중 오판 방지) · 원장 폴백 유지 | AC-67 |
| TEST-20260828T150000-endpoint | `/api/ai/bridge_heartbeat` | 같은 토큰 해석기 경유 · 도구 목록 밖 · 원장 미기록 · 기록 실패가 연결을 끊지 않음 | AC-66 |
| TEST-20260828T150000-runner-thread | `start_heartbeat` | 가짜 Api 로 **실제 루프 구동** · 실패(0·401) 후 생존 · 주기 하한 · daemon · `main` 배선 | AC-68 |
| TEST-20260828T150000-session-slide | `web_context` | 활동 시 만료 슬라이딩 · 절대 상한 ≥ 무활동 창 · throttle 유지 · CreatedAt NULL 방어 | AC-69 |
| TEST-20260828T150000-shutdown | `shutdown_after_drain` · `ActiveTasks` | 유휴 즉시 종료 / 진행 중 대기 후 종료 / 유예 초과 시 취소 · 유예는 절대시각 · 401 배선 · 등록 경합 방지 | AC-70 |
| TEST-20260828T150000-schema | `_ensure_bridge_heartbeat_schema` | 컬럼 보장이 fast/slow 양 경로 · ALTER 실패가 catchup 을 세우지 않음 | AC-66 |

## 3. Run 기록

Run 기록은 `docs/test-runs.d/` 의 항목당 1파일로 작성한다 (AGENTS.md §5.3 fragment 규약).
