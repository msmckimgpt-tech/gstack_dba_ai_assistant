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

## Run 2 — 배포 후 라이브 실측 (`00981307`, 2026-09-09 12:22~12:27 KST)

- Scenario: 프로필 > 프롬프트 > 내 프롬프트 > [자동 작성] → 위임 결과가 입력란에 채워진다
- Environment: DQA-client
- Result: PASS
- Verdict: PASS
- 증거: [화면 캡처](evidence/20260909-prompt-autogen-live.png)

### 어떻게 쟀나 (러너를 실제로 띄웠다)

이전 Run 이 NOT-RUN 이었던 이유는 「듣고 있는 러너가 없다」였다(마지막 하트비트 9시간 전,
임계 90초). 이번에는 **검증용 러너를 직접 기동**해 그 전제를 만들었다.

1. 검증 계정(`bootstrap_admin`)으로 로그인 → `POST /api/ai/connect/token` 으로 `mat_` 발급.
   비밀번호는 도구가 `.env` 에서 읽었고 세션·토큰 값은 어디에도 출력하지 않았다.
2. 정본 러너 기동: `python3 -m agent.lifecycle --no-batch --no-self-review`
   (`BRIDGE_AI=codex`, 사설 CA 번들 지정). `--no-batch`·`--no-self-review` 는 검증에 불필요한
   개인 계정 AI 호출을 줄이려는 것이다.
   - ⚠ **단일 파일 러너(`bridge_runner.py`)로는 이 검증이 성립하지 않는다** — 그 파일에는
     하트비트 전송이 없어(`grep heartbeat` → 0) `runner_profile_for_account` 가 `listening=False`
     를 돌려주고 위임 자체가 일어나지 않는다. 정본은 `src/agent/` 모듈군이다.
3. 러너 로그: `run.ready runtime=codex` → 하트비트 도달(서버가 `hb.stale_build` 로 응답).

### 서버 왕복 (API 축)

| 단계 | 관측 |
|---|---|
| `GET /api/auth/me/system-prompt/generate/stream` | **HTTP 200 · `content-type: application/json`** — SSE 가 아니라 위임 봉투 |
| 응답 본문 | `{"bridge_pending":true,"task_id":"j_RYBoLCKXVvgtQNK4","poll_url":"/api/profile/ai-jobs/j_RYBoLCKXVvgtQNK4",…}` — **poll_url 이 신설 프로필 경로** |
| 폴링(화면과 같은 순서) | `working` ×5 → **`done`** · `degraded=false` · `result` **655자** |
| 결과 내용 | 실제 개인 프롬프트(응답 형식·관심 주제 지침). `payload={"scope":"account","scope_id":1}` |

### 화면 (DQA 클라이언트 · 실제 브라우저 조작)

`openProfileBtn` 클릭 → '프롬프트' 탭 → **[자동 작성] 실제 클릭** 후 화면 상태를 시계열로 관측했다.

| 시점 | 버튼 | 안내(`#promptMeta`) | 입력란 |
|---|---|---|---|
| before | 자동 작성 | (저장된 프롬프트 없음) | 0자 |
| +1.5s | 생성 중… (disabled) | **"시스템 프롬프트 자동작성을(를) 연결된 본인 AI 에 맡겼습니다. 완료되면 여기에 채워집니다."** | 0자 |
| +3s ~ +20s | 생성 중… | **"연결된 AI 가 처리 중…"** | 0자 |
| 완료 | **자동 작성**(복원·활성) | **"연결된 AI 가 작성했습니다 (559자). 검토 후 '저장'을 누르세요."** (경고 아님) | **559자** |

러너 로그가 같은 왕복을 반대편에서 확인해 준다:
`task.dispatch runtime=codex model=gpt-5.6-luna kind=job prompt_chars=1946` →
`task.submit.ok dur_ms=24438 answer_chars=559`.

**이 두 안내 문구(위임 맡김 · 처리 중)가 이번 수정으로 생긴 것이다.** 수정 전에는 같은 자리에서
「준비 중…」에 멈춘 채 버튼만 복원됐다(2026-09-08 라이브 상태 = 하네스 뮤턴트 M2 가 재현한 것).

### 검증 후 원상복구

미저장 상태였던 입력란을 비우고 프로필 드로어를 닫았다(사용자 데이터 미변경 — '저장'을 누르지
않았으므로 `WebSystemPrompts` 에 쓰기 없음). 검증용 러너 종료, 검증용 로그인 세션 로그아웃
(세션 결합 토큰이 함께 무효화된다), 로컬 토큰·쿠키 파일 삭제. 사용자 브라우저 세션과 실행 중인
앱은 종료하지 않았다.

## Environment: windows-browser

- Result: NOT-RUN
- Reason: PB-0009(DQA 클라이언트)가 주 검증 경로이고 이번 변경에 브라우저 전용 호환 분기가 없다.
  보조 호환 검증을 대체 증거로 승격하지 않는다.
