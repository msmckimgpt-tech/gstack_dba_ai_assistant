---
run_at: 2026-07-29T17:50:00+09:00
session: ai/claude/feature-0003-pending-bubble-stall
scope: 진행 폴링 영구 정지 → 자가 회복(F1 백오프 · F2/F3 watchdog · F4/F5 재무장) — pre-commit
verdict: PASS (정적 + JS 행위검증 + 컨테이너 스위트) / PB-0008 라이브는 배포 직후
---

### Run (2026-07-29 17:50) — progress-poll-resilience pre-commit — **Environment: node + container(agent image)**

#### 1. 신규 행위검증 — `verify_progress_poll_resilience.mjs`

`pollProgress` / `detectNewRun` 을 소스에서 추출해 가짜 state·fetch·timer 로 **실제 구동**한다
(정적 문자열 검사 tautology 회피). **45 passed / 0 failed**.

| 그룹 | 단언 요지 |
|---|---|
| F1-persist | 6연속 실패에도 매 회차 재스케줄(영구 중단 없음) · errorCount 누적 · in-flight 누수 0 |
| F1-backoff | 8s → 16s → 32s 지수 증가 · 상한 60s 초과 0 · 상한 포화 |
| F1-recover | 성공 시 errorCount 리셋 · 처리 중이면 ACTIVE(1.2s) 복귀 |
| F1-hidden | 숨김 탭도 재스케줄 + 숨김 최소 주기(10s) 보장 |
| F2-dormant | 폴러 생존 시 handoff 0 · 재스케줄만 · fetch 안 함(baseline 미확정) |
| **F2-watchdog** (codex P1) | **폴러 사망 + `progressRunId` 잔존 → 내 run 으로 폴러 재기동**(`reset:false`) · **foreign run 을 받는 감지 fetch 0회** · loadHistory 미호출 · 감지기 재스케줄 유지 |
| F2-watchdog-b | 추적 run 부재 + pending 말풍선만 + 서버 processing → loadHistory 로 회복(폴링 재기동 없음) |
| F2-newrun / F2-idle | 기존 realtime-progress-propagation 계약 보존(새 run 동기화 · 완료 상태 무동작) |
| F3 / 타이머 / F4 / F5 | processing 분기 watchdog 무장 · 소진 tick 참조 정리 · 재가시 판정(display_status·pendingBubble) · online 훅 |
| P2-abort (codex P2) | `stopRunDetectPolling` 이 감지 fetch abort · 참조 해제 · controller 를 state 에 게시 · finally 는 자기 controller 만 정리 |

**회귀 가드 유효성 실증**: 같은 스크립트를 **수정 전 `app.js`** 에 대고 실행 → **12건 FAIL**
(`[F1-persist]` · `[F1-backoff] 2·3회차/포화` · `[F2-watchdog]` 2건 · 정적 배선 6건). 수정 후 0 FAIL.

**codex 적대 리뷰가 잡은 회귀 1건(P1)이 이 표에 반영돼 있다** — 초안의 watchdog 은 폴러 사망 시
무조건 `loadHistory` 로 넘겼는데, 감지 fetch 가 `client_run_id` 를 싣지 않아 그룹 대화에서 남의
run 을 받고 폴링이 그쪽으로 갈아타 **내 run 의 terminal 을 영영 못 받는** 경로가 열렸다. 지금은
`progressRunId` 가 있으면 fetch 없이 그 run 의 폴러만 재기동한다(Case 6, payload 를 `r2-foreign`
으로 두고 handoff·fetch 0 을 단언).

#### 2. 기존 스위트 계약 갱신 — `verify_run_detect_poll.mjs`

main baseline 28 PASS → 본 worktree **35 PASS / 0 FAIL**(S4 폴러 생존 기준 · **S4b** foreign-run
보존 · **S4c** 추적 run 부재 시 loadHistory · S6 in-flight 기준 · 정적 배선 3건).

수정 직후 이 스위트가 6건 FAIL 했는데, 그 단언들이 **옛 결함을 고정**하고 있었다 —
"processing 분기가 감지기를 정지", "pendingBubble 존재 → dormant", "progressRunId 존재 → dormant".
이것들이 곧 회복 타이머 소멸의 직접 원인이라 그대로 두면 회귀 가드가 아니라 결함 보호막이 된다.
dormant 의 **본래 의도(중복 fetch 방지)** 는 폴러 생존 기준으로 보존하고, "폴러 사망 → watchdog
회복"(S4b)을 신설했다.

#### 3. feature-0003 mjs 스위트 전량 — main 대조

worktree/main 양쪽 실행 후 결과 대조 — **신규 실패 0**. 잔여 FAIL 은 main 과 동일한 baseline:
jsdom 미설치(11건) · ERR_MODULE_NOT_FOUND(4건) · 타 세션 cache-buster 미bump 검사(6건).

#### 4. 컨테이너 스위트

`COMPOSE_PROJECT_NAME=repo make test` — 본 변경은 **프론트 JS 2파일 + 문서**라 Python 무접촉.
main baseline 대비 신규 실패 0 확인.

#### 5. **Environment: Windows-browser** — pre-commit 시점 미수행(사유 명시), POST-DEPLOY 수행

**미수행 사유(정직)**: 본 변경은 *클라이언트 폴링이 끊긴 뒤 스스로 회복하는가* 를 보는 것이라,
검증 대상 코드가 **브라우저에 서빙되고 있어야** 의미가 있다. 배포 전 라이브(web-a/web-b)는 수정
이전 `app.js` 를 서빙하므로 지금 PB-0008 을 돌리면 "고장이 재현된다" 만 확인하게 된다. 라이브 주입
QA 는 병렬 세션 다수가 같은 라이브를 공유하는 현 상황에서 타 세션 오염 위험이 있어 채택하지 않는다
(선례: graph-routine-colref cycle 의 즉시 원복 판단).

따라서 `deploy_scope: included` 에 따라 **배포 직후 같은 cycle 안에서** 아래 시나리오로 수행하고
그 결과를 본 fragment 에 POST-DEPLOY Run 으로 append 한다.

#### 6. POST-DEPLOY PB-0008 시나리오 (`visual_verification_scope: always`)

1. 요청 전송 → 말풍선이 '처리 중' 으로 진입하고 step/경과시간이 갱신됨
2. 폴링 구간에 네트워크 오프라인 3회 이상 유도 → **대화 전환 없이** 온라인 복귀 후 말풍선이
   스스로 갱신(F1 백오프 재시도 또는 F5 online 훅)
3. 폴러 강제 사망(오프라인 유지 후 온라인) 상태에서 watchdog 이 `loadHistory` 로 화면 회복
4. 정상 경로 무회귀 — 처리 중 `/api/progress` 중복 호출 없음(감지기 dormant), 완료 시 답변 표시
