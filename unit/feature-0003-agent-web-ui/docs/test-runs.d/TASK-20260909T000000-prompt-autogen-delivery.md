# TASK-20260909T000000 — '자동 작성' 위임 결과 도달 (UI 검증 원장)

정본 원장: [feature-0043 Run](../../../feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260909T000000-prompt-autogen-delivery.md).
이 파일은 본 feature 의 **웹 자산 변경에 대한 시각검증 기록**(PB-0009 · AGENTS.md §15.4.1·§16.6)이다.

## 변경된 UI 자산

- `src/static/console-job-poll.js` (신설) · `src/static/admin/llm-state.js` (re-export)
- `src/static/app.js` (프로필 '내 프롬프트' 자동 작성) · `src/static/admin.js` (역할·제품 프롬프트)
- `src/static/release-notes-data.js` (2026-09-09 릴리즈 항목)

## Run 1 — 커밋 전 (배포 이전)

- Scenario: 프로필 > 프롬프트 > 내 프롬프트 > [자동 작성] → 위임 결과가 입력란에 채워진다
- Environment: DQA-client
- Result: NOT-RUN
- Reason: 아직 배포되지 않은 변경이라 앱이 받는 자산에 이 코드가 없다. 또한 위임이 실제로
  일어나려면 그 계정의 개인 AI 러너가 연결돼 있어야 하는데, 러너 (재)기동에는 사람이 웹에서
  발급하는 `mat_` 토큰이 필요해 AI 단독으로 넘을 수 없다. 배포 후 Run 2 에서 재측정한다.
- 대체 하위 검증 (이 시점에 실제로 수행한 것):
  - jsdom 행위 하네스 `tests/verify_prompt_autogen_delivery.mjs` — **15 passed, 0 failed**.
    정본 `app.js::generateAccountPrompt` 를 그대로 꺼내 **진짜** `console-job-poll.js` 와 함께
    구동하고, 서버 응답만 흉내 냈다. 위임 봉투 → 폴링 → textarea 도달 · 실패 시 본문 미덮음 ·
    종전 SSE 무회귀 · 403 즉시 종료 · abort 보존을 각각 관측.
  - 뮤턴트 역검증 2종 KILL(위임 분기 제거 = 원래 결함 재현 시 S1 FAIL). 하네스가 이 결함을
    실제로 잡는다는 대조군.
  - 이 하위 검증은 **DOM 시뮬레이션**이며 실제 클라이언트 렌더·입력 경험을 대체하지 않는다.

## Run 2 — 배포 후 (라이브, `00981307`)

- Scenario: 프로필 > 프롬프트 > 내 프롬프트 > [자동 작성] → 위임 결과가 입력란에 채워진다
- Environment: DQA-client
- Result: NOT-RUN
- Reason: 위임이 실제로 일어나려면 그 계정의 개인 AI 러너가 연결돼 있어야 한다. 러너 (재)기동에는
  사람이 웹에서 발급하는 `mat_` 토큰이 필요해(러너가 저장하지 않는다) AI 단독으로 넘을 수 없다.
  또한 기존 사용자 앱을 검증 편의로 종료하지 않는다(FIRST_REQUEST 사용자 결정). 러너가 연결된
  상태에서 [자동 작성] 을 한 번 눌러 주시면 그 자리에서 확인된다.
- 수행한 하위 검증 (배포 후 실측, 러너 없이 가능한 축):
  - `GET /static/app.js?v=3f19ce1d878b` (505,813 B) — `looksDelegatedEnvelope` 2 · `bridge_pending` 3 ·
    `console-job-poll.js` import 1. **배포가 브라우저가 받는 자산에 실제로 도달했다.**
  - `GET /static/console-job-poll.js?v=3f19ce1d878b` → **200 · 9,445 B**(`awaitDelegatedResult` ·
    `api/profile/ai-jobs` · `body.degraded === true`).
  - `GET /static/admin.js?v=3f19ce1d878b` → `looksDelegatedEnvelope` 3 · `admin/llm-state.js` re-export 도달.
  - `GET /api/profile/ai-jobs/j_LIVEPROBE` → **401**(라우트 등록 + 로그인만 요구) vs 없는 경로 **404**(대조군).
  - 이 축들은 **도달·배선**을 증명하며 사용자 화면의 실제 렌더·입력 경험을 대체하지 않는다.

## Environment: windows-browser

- Result: NOT-RUN
- Reason: PB-0009(DQA 클라이언트)가 주 검증 경로이고 이번 변경에 브라우저 전용 호환 분기가 없다.
  보조 호환 검증을 대체 증거로 승격하지 않는다.
