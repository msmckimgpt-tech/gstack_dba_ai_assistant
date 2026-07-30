---
run_at: 2026-07-29T20:10:00+09:00
session: ai/claude/feature-0003-enqpre-run-handoff
scope: enqueue sentinel → 실제 run 승계 (요청 직후 '시작 중…' 박제 해소) — pre-commit + 라이브 BEFORE 재현
verdict: PASS (정적 + JS 행위검증 + 컨테이너 스위트 + 라이브 결함 재현 확증) / AFTER 대조는 배포 직후
---

### Run (2026-07-29 20:10) — progress-enqpre-handoff pre-commit — **Environment: node + container(agent image) + Windows-browser(BEFORE 재현)**

#### 1. 라이브 BEFORE — **결함 재현으로 진단 확증** (배포 전 서빙본 = 수정 전 코드)

실 Windows Chrome/150 relay(전용 새 탭, 타 세션 `/admin` 탭 무접촉)로 실 사용자 경로 전송
("연결된 데이터소스의 테이블 목록을 조회해서 3개만 보여주세요.") 후, `/api/progress` 왕복과 화면을
시계열 관측했다.

| 시점 | 프론트 추적 id(`state.progressRunId`) | 서버 응답 `run_id` | 서버 `steps` | **프론트 `progressSteps`** | 화면 단계 |
|---|---|---|---|---|---|
| t+3s | `enqpre-8b2e6bff96e84d2…` | `20260730064650-0348e…` | 3 | **0** | 시작 중… |
| t+10s | `enqpre-8b2e6bff96e84d2…` | `20260730064650-0348e…` | 3 | **0** | 시작 중… |
| t+20s | `enqpre-8b2e6bff96e84d2…` | `20260730064650-0348e…` | 6 | **0** | 시작 중… |
| t+35s | `enqpre-8b2e6bff96e84d2…` | `20260730064650-0348e…` | 7 | **0** | 시작 중… |

- 프론트는 매 폴에서 `client_run_id=enqpre-…`(sentinel)을 보내고, 서버는 실제 run
  `20260730064650-0348e…` + `status=processing` + **실제 steps 3→6→7** 을 정확히 돌려준다.
- 그런데 `progressSteps` 는 **끝까지 0** — `applyProgressPayload` 의 foreign-run 가드가 매 응답을
  early-return 으로 버린다. 상태 라벨만 첫 응답에서 '처리 중' 으로 굳고, 경과시간(별도 타이머)만
  3→35초로 흐른다. **사용자 재보고 스크린샷과 정확히 동일한 상태**다.
- 증적: `artifacts/shared/pb0008-enqpre-handoff-before.png`.

이 관측이 진단을 확증한다 — 문제는 "서버가 단계를 안 준다" 가 아니라 **"프론트가 받은 단계를
버린다"** 이며, 버리는 이유는 sentinel 을 추적 id 로 채택했기 때문이다.

#### 2. 신규 행위검증 — `verify_enqpre_run_handoff.mjs`

`applyProgressPayload` / `resetProgressTracking` / `startProgressPolling` 을 소스에서 추출해 가짜
state 로 **실제 구동**한다(정적 문자열 tautology 회피). **27 passed / 0 failed**.

| 그룹 | 단언 요지 |
|---|---|
| C1 | sentinel 은 `progressRunId`·`pendingBubble.runId` 로 채택하지 않고, 상태 표시는 정상 반영 |
| **C2** | **sentinel → 실제 run 승계 시 채택 + steps 반영 + `after_step` 전진** (수정 전 회귀 지점) |
| C3 | 실제 run 추적 중 **다른 실제 run** 의 processing 은 여전히 무시(그룹 foreign-run 불변식 보존) |
| C4 | 다른 run 의 terminal(done)은 가드에 막히지 않음(종료 해소 경로 보존) |
| C5 | 2중 방어 — 이미 sentinel 추적 중이어도 실제 run 승계를 막지 않음 |
| C6 | `resetProgressTracking` 채택 규약 양방향 · sentinel 은 진행 중 추적을 reset 하지 않음 |
| 정적 | 서버 계약 접두어 고정 · 가드 예외 · choke-point · `loadHistory` 복원/판정 경유 |

**회귀 가드 유효성 실증**: 같은 스크립트를 **수정 전 `app.js`**(git stash)에 대고 실행 → **18건 FAIL**
(`[C2]` 4건 전부 포함). 수정 후 0 FAIL.

#### 3. 기존 스위트 회귀

| 스위트 | 결과 |
|---|---|
| `verify_progress_poll_resilience.mjs` (선행 cycle) | 45 PASS / 0 FAIL |
| `verify_run_detect_poll.mjs` | 35 PASS / 0 FAIL |
| `verify_model_persist.mjs` | 49 PASS / 0 FAIL |
| `verify_diff_lineno_leak.mjs` · `verify_share_participants.mjs` · `verify_runtime_transparency.mjs` · `verify_mentions.mjs` | 전부 PASS |
| `verify_metadata_scope_single_ds.mjs` | 10 PASS / 5 FAIL — **main baseline 동일**(무관한 사전 결함) |

#### 4. 컨테이너 스위트

`COMPOSE_PROJECT_NAME=repo make test` → **FAILED 0건**, ruff PASS(exit 0). 본 변경은 프론트 JS
1파일 + 문서라 Python 무접촉.

#### 5. **Environment: Windows-browser** — AFTER 대조는 배포 직후

위 §1 이 **같은 브리지로 수행한 실 Windows 브라우저 Run** 이며, 수정 전 상태를 결정적으로 고정했다.
수정본의 AFTER 대조(같은 시나리오에서 `tracked` 가 실제 run 으로 전환되고 `frontSteps` 가 서버
`steps` 를 따라가는지)는 `deploy_scope: included` 에 따라 **배포 직후 같은 cycle 안에서** 수행하고
본 fragment 에 POST-DEPLOY Run 으로 append 한다.

---

### POST-DEPLOY Run (2026-07-30 16:05) — **Environment: Windows-browser** — verdict: **PASS**

배포본 `6a8f7f5a`(web 롤링 + soak 통과) · 서빙 `app.js` 에 수정 반영 실측(`ENQUEUE_SENTINEL_RUN_PREFIX`
/`_adoptRunId` 17건, 엣지 스탬프 `?v=9900653f0c72`) · 실 Windows Chrome/150 relay, 전용 새 탭
(타 세션 탭 무접촉) · **BEFORE 와 동일 시나리오**(새 대화 → "연결된 데이터소스의 테이블 목록을
조회해서 3개만 보여주세요.").

#### BEFORE / AFTER 대조

| 시점 | BEFORE 추적 id | BEFORE 프론트 steps | AFTER 추적 id | AFTER 프론트 steps | AFTER 화면 단계 |
|---|---|---|---|---|---|
| t+3s | `enqpre-8b2e6bff…` | **0** (서버 3) | `''` (sentinel 미채택) | 0 | 시작 중… |
| t+10s | `enqpre-8b2e6bff…` | **0** (서버 3) | `''` | 0 | 시작 중… |
| t+20s | `enqpre-8b2e6bff…` | **0** (서버 6) | **`20260730070324-ffbd546c`** | **3** | **AI 가 질문을 분석하고 답변을 추론하는 중** |
| t+35s | `enqpre-8b2e6bff…` | **0** (서버 7) | 동일(불변) | **6** | **답변을 자가 검증하는 중 (red-team 리뷰)** |

- **AC-EPH-1 PASS**: sentinel 구간(t+3s·t+10s)에 추적 id 가 빈 문자열로 유지된다.
- **AC-EPH-2 PASS**: 워커 claim 후 실제 run `20260730070324-ffbd546c` 를 채택하고, 프론트 steps 가
  서버 `step_count` 를 **그대로 따라간다**(3 → 6). BEFORE 는 서버가 3→6→7 을 보내는데 끝까지 0 이었다.
- **대화 전환·새로고침 없이** 갱신됐다 — 사용자 보고의 핵심 조건이 해소됐다.
- 실 화면(스크린샷 `artifacts/shared/pb0008-enqpre-handoff-after.png`): 상태 **'처리 중'** ·
  단계 **'답변을 자가 검증하는 중 (red-team 리뷰)'** · **'6단계 보기'** 버튼 노출 · 35초.
  BEFORE 스크린샷(`…-before.png`)의 같은 위치는 '시작 중…' + 단계 버튼 없음이었다.

#### 관측 부기(정직)

- t+3s~t+10s 의 상태 라벨이 BEFORE '처리 중' → AFTER '시작 중' 으로 바뀌었다. sentinel 을 추적 id 로
  채택하지 않으면서 그 구간의 `displayStatus` 갱신도 서버 응답에 따라가므로(새 대화라 KV 가 아직
  비어 첫 응답이 빈 status), **큐 대기 구간이 '시작 중' 으로 정직하게** 표시된다. 실행이 시작되면
  즉시 '처리 중' + 실제 단계로 넘어간다(t+20s). BEFORE 의 '처리 중' 은 sentinel 응답을 반영한
  것이었고 그 뒤로 **영구 고착**됐으므로, 표시 정직성·기능 모두 개선이다.
- 그룹 동시 전송 창의 foreign 오귀속(codex P1-1)은 라이브에서 재현하지 않았다 — 두 계정 동시 전송을
  1~2초 창에 맞춰야 하고, 현재 동작은 C7·C8 이 단위 수준에서 고정한다. 근본 해결(서버 `run_is_mine`)
  은 후속 과제(REVIEW 참조).
