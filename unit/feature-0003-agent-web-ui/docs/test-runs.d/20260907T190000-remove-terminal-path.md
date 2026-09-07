---
run_at: 2026-09-07T19:00:00+09:00
session: remove-terminal-path (ai/claude/feature-0043-remove-terminal-path)
scope: 「연결 준비」·터미널·AI 지시문 전면 제거
verdict: PASS (행위 하네스 2종 + 컨테이너 회귀) / 라이브는 배포 후
---

### Run (2026-09-07) — **Environment: node 행위 하네스 (되살림)**

⚠ **두 하네스는 2026-09-04 이후 한 번도 돌지 않고 있었다.** `client-bridge.js` 가 생기면서
상대 import 가 해소되지 못했다:

| 하네스 | 적재 방식 | 죽던 이유 | 겉보기 |
|---|---|---|---|
| `verify_connect_modal_autoclose.mjs` | `data:` URL | `ERR_INVALID_URL` (기준 경로 없음) | 예외로 죽음 |
| `verify_launch_runner_behavior.mjs` | 임시 사본 1개 | `ERR_MODULE_NOT_FOUND` (이웃 부재) | **인자 없으면 usage 찍고 exit 0** |

후자는 「안 돌았다」와 「통과했다」가 겉으로 같았다. 문서에는 「25/0 PASS」가 남아 있었다.

수정: 전자는 스텁을 **전수 처리**로(남은 상대 import 가 있으면 그 자리에서 죽는다),
후자는 **이웃을 실재하게** 만들어(같은 모양의 트리 + `package.json {"type":"module"}`).
정본 소스는 여전히 한 글자도 바꾸지 않는다.

- `verify_connect_modal_autoclose.mjs` — **40 passed, 0 failed**
- `verify_launch_runner_behavior.mjs` — **PASS (18 checks)**

### ⚠ 하네스를 고치며 헛짚은 둘 (제품 결함으로 오인할 뻔)

1. **F2 실패**를 「내 변경의 회귀」로 읽었다. 실제 원인은 내가 `last_os` 를 기본 상태에 넣어
   **로그인 진입 자동 실행**이 이 하네스에서 처음으로 켜진 것이었다 — 그 대기가 창을 닫았고,
   그것은 제품의 옳은 동작이다. 페이지당 1회라는 실제 시점에 맞춰 먼저 소진시켜 격리했다.
2. **L17** 이 「버튼도 못 누른 채」 통과할 뻔했다. 앞 시나리오 응답에서 `last_os` 를 빠뜨려
   실행 자격이 꺼졌고, 그러면 클릭이 **아무 일도 하지 않는다**(status 가 빈 문자열).
   빈 화면을 「설치 안내를 하지 않았다」로 읽으면 통과다 — 실패 상세를 찍어 보고서야 갈렸다.

### 제품 결함 1건 (하네스가 짚었다)

창을 여는 순간 상태 조회가 한 번도 끝나지 않았으면 `_offerLaunch` 가 「이력 없음」으로 읽고
물러나, 그 창에는 [내 AI 실행] 이 **영영 안 나타난다**(다시 열기 전까지). 자격을 알게 된
자리(`refreshConnState`)에서 한 번 더 주도록 고쳤다(`test_the_offer_is_retried_once_eligibility_becomes_known`).

### Run (2026-09-07) — **Environment: 컨테이너 회귀 `make test`**

- 1차: **12 FAILED**. 전부 이 변경이 지운 것을 잠그고 있던 **전제 잠금**이었다(위 표 + 아래 4건).
  하나씩 뒤집었다 — 그 중 넷은 다른 feature 소유였다(`feature-0041` 토큰 경고·TTL 단위,
  `test_ai_assisted_setup_codex` 비결정성 고지, `test_session_revoke_parity` 표시 갱신 자리).
  ⚠ 남의 feature 테스트를 손댈 때는 **원래 걱정을 옮겼다**: 「보여주면서 경고하지 않는다」를
  「보여주지 않는다」로, 「AI 경로에 고지가 있다」를 「경로를 되살리면 고지도 함께」로.
- 그 밖에 `test_route_parity_p5b`(267→269)가 적색이었으나 **내 변경과 무관**했다 —
  병렬 세션의 업데이트 채널이 라우트 2개를 더하며 골든을 재생성하지 않은 것이고,
  재베이스 시점의 main 에서 이미 고쳐져 있었다(내 재생성은 no-op 이 됐다).
- 2차: **EXIT=0 / FAILED 0 / 100%** · ruff clean.

### Run (2026-09-07) — 라이브 — **Environment: Windows-browser (배포 후로 이연)**

- 계획: 배포 → 앱 창과 일반 브라우저 양쪽에서 ① 명령·지시문·「연결 준비」가 보이지 않는지
  ② 앱 창에서 패널이 그대로 동작하는지 ③ 브라우저에서 [내 AI 실행]/[DQA 앱 받기] 가
  조건대로 나타나는지.
