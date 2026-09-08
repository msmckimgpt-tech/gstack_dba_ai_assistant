---
run_at: 2026-09-08T15:40:00+09:00
session: ai/claude-corp/feature-0003-share-client-entry
scope: 공유 링크의 참여·fork 진입을 DQA 앱으로 일원화 — 열람 경로 불변
verdict: 자동검증 PASS / DQA-client 실측 NOT-RUN (아래 Run 별 Result 참조)
---

⚠ 이 파일의 수치는 **적대 검증 3라운드 조치 후 · main `cdd414e3` 병합 후** 값이다. 1라운드 시점 기록(jsdom 30 · 클라이언트
536)은 이후 조치로 늘어났고, 그때 적었던 「이번 CSS 는 새 기하를 만들지 않았다」는 **실측이
반증했다**(적대 리뷰 qa-C1 이 그 어긋남을 지적). 재현되지 않는 숫자와 반증된 주장이 남으면
`NOT-RUN` 을 정직하게 적어 얻은 신뢰를 그 옆 문장이 깎는다.

### Run 1 — 공유 화면 액션 분기 동작 (jsdom)

Environment: node-jsdom
Result: PASS
Scenario: 실제 `share.html` 을 jsdom 에 올리고 배포되는 `share.js` 를 그대로 실행해,
평범한 브라우저 / 앱 창 안 / 미로그인 / 참여·fork 불가 / 설치기 부재 / 서버 조립 실패 /
이미-멤버 / 비-Windows 3종 / 버전 페이징 재렌더 / 진입 클릭 / 브리지 좌표 경로 표, 그리고
**2차원 표** — ③b(열화 4분기 × 미로그인·로그인 후) · Ⓓ(검증 후 보관 · 이동 후 좌표 계승 ·
대조군) · ⑤d(busy 경합) 에서 **어느 버튼이 실제로 보이고 무엇이 저장되는지** 측정.
Evidence: `node unit/feature-0003-agent-web-ui/tests/verify_share_client_entry.mjs`
→ **108 passed, 0 failed**

- ⚠ **하네스 자체의 결함을 먼저 잡았다.** 첫 작성본은 `runScripts: "outside-only"` 라
  `share.js` 가 **한 줄도 실행되지 않았는데** 「버튼이 안 보인다」류 단정이 전부 통과했다 —
  초기 HTML 이 이미 `hidden` 이기 때문이다. ⓪번 양성 대조군이 그 형태를 봉인한다.
- ⚠ **표를 2차원으로 만든 것이 이번 라운드의 핵심이다.** 종전에는 축 하나를 고정하고
  다른 축만 훑어(`AUTHED` 고정 × 플랫폼 훑기, 단일 페이지 적재 × pathname 훑기) 두 축이
  교차하는 칸이 통째로 비어 있었고, 3R 이 잡은 HIGH 2건은 **정확히 그 빈칸에 살았다** —
  81건 전건 통과 속에서.
- ⚠ jsdom 은 실 렌더가 아니다 — 레이아웃·정렬·간격 등 **픽셀-클래스는 Run 4 가 잰다**.

### Run 2 — 계약: 서버 조립·SSOT·스크립트 순서·익명 응답 shape (pytest)

Environment: pytest
Result: PASS
Scenario: 서버가 정본(`dqa_identity.app_open_url`)으로 조립 · 토큰 미포함 · 받기 URL 은
실물 판정 정본 위임 · 조립 실패가 열람을 막지 않음 · **공유 화면 자산 전체**에 스킴 리터럴
부재(디렉터리 순회) · 스크립트 순서·defer·스탬프 · 좌표 규약 미복제 · 익명 응답 최상위 키
집합 고정(AST) · 보관 게이트가 allow-list 인지.
Evidence: `python3 -m pytest unit/feature-0003-agent-web-ui/tests/{test_share_client_entry,test_share_bar_layout}.py -q`
→ **26 passed**

### Run 3 — 클라이언트: 딥링크 수용·목적지 전달·창 이동 (pytest)

Environment: pytest
Result: PASS
Scenario: 정본↔사본 **경로표 대조**(`//evil` · 역슬래시 · `..` · 제어문자 · `?`·`#` ·
길이 경계 양측 · 표기 변종) · 상한 **값 자체** · 왕복 · `open` 의 토큰 배제 · `panel_url`
스머글 방어 · 딥링크 base 동봉값 대조 · 구버전 degrade · 목적지가 **창까지** 도달
(navigate→show 순서, 실제 호출) · `Shell.navigate` 세 갈래 · 파일 권한·경합 · 세 껍데기 비대칭.
Evidence: `python3 -m pytest unit/feature-0046-native-client/tests -q` → **585 passed**

### Run 4 — 하단 고정 바 레이아웃 (headless chromium)

Environment: headless-chromium
Result: PASS
Scenario: 실 `share.html` + 실 `share.css` 를 chromium 에 올려 액션 배치·기본 높이·hover 확장·
transition·타겟 크기, 그리고 **T9: 앱 진입이 켜지고 안내가 뜬 상태**에서 1280×800 · 768×1024 ·
375×667 · 320×568 네 뷰포트의 ① 여백이 바를 덮는가 ② 바가 화면의 25% 를 넘지 않는가
③ **T10: 인쇄 매체에서 그 여백이 0 인가**.
Evidence: `PLAYWRIGHT_BROWSERS_PATH=… python3 tests/headless/verify_share_bar_layout.py`
→ **20 passed, 0 failed** (320×568 에서 footer 129.5px = 23%, print padding 0px)

- ⚠ **이 Run 이 1라운드에는 없었다.** 전용 하네스가 이미 있었는데 돌리지 않았고, 돌려 보니
  기본 상태(안내 숨김)만 재는 사각지대가 있었다 — 그 상태로는 8/8 초록인데 실제 배포 상태는
  데스크톱 hover 82.5px > 80px, 375px 180.1px > 96px, 320px **198.1px > 96px** 로 예산을
  넘고 있었다(초과분은 `position: fixed` 바에 영구히 가려진 대화 말미가 된다).
- ⚠ T9 의 첫 판은 **항진명제**였다 — `pad >= fh` 인데 구현이 `pad = ceil(fh)+12` 라 바가
  500px 여도 초록이다. **절대 예산(T9-b)** 을 별도 축으로 두어 그것을 닫았다.
- 인쇄 매체는 이제 **T10 이 4폭 전부에서 가드**한다 — 일회성 실측이 아니라 회귀로 고정했다
  (뮤턴트로 `!important` 를 떼면 4건 전부 적색).
- ⚠ 이 하네스는 커밋된 증적 PNG 를 덮어쓰지 않는다 — 갱신은 `--evidence` 를 명시할 때만.

### Run 5 — 실제 DQA 클라이언트

Environment: DQA-client
Result: NOT-RUN
Scenario: 브라우저에서 공유 링크 → `[DQA 앱에서 참여 · fork]` → 앱이 **그 대화**를 열고
(신규 실행·상주 중 두 경우), 앱 창 안에서는 직접 실행 버튼(참여·fork)이 돌아온다.
Reason: 이 cycle 의 산출물이 실제 앱 화면에 도달하려면 ① 서버·정적 자산 배포와
② **클라이언트 재배포**(딥링크 `path` 수용은 설치본 코드다)가 모두 필요하다. 설치기 빌드는
PyInstaller 크로스컴파일 불가로 **Windows 에서만** 만들어지므로, 이 WSL 세션에서 변경이
반영된 앱을 띄울 수 없다. 기존 사용자의 앱·연결 세션을 검증 편의로 종료하거나 재설치하지
않는다(PB-0009 실행 3항).
Alternative: Run 1~4. 커버리지의 **경계를 정직하게 적는다** — 표시 분기(jsdom 108, 2차원 표) ·
계약(pytest 26) · 목적지 전달과 창 이동의 **로직 축**(클라이언트 전건, 가짜 shell 로
navigate→show 순서까지) · 레이아웃·인쇄 실 렌더(chromium 20). 확인되지 **않은** 것: 실 WebView2 의 `load_url`
동작, 트레이 상주 중 창 이동의 체감, OS 스킴 핸들러 등록·발사, SmartScreen 경로.
Next: 1.1.2 설치기 빌드·게시 후 위 Scenario 를 실측하고 같은 `Environment: DQA-client` ·
같은 Scenario 로 Run 을 추가한다. 그때까지 이 시나리오는 PASS 가 아니다.

### 적대 검증 (§18.8) — 세 라운드 모두 결함을 잡았다

1R 은 세 reviewer 전원 BLOCK, 2R 은 조치 중 셋이 뚫렸거나 새 마찰을 만든 것을, 3R 은 **2R
조치가 만든 HIGH 2건**을 잡았다. 3R 의 요지는 그 둘이 **세 스위트가 전건 초록인 상태에서**
실행으로 재현됐다는 것이다 — 초록은 커버리지의 증거가 아니다.
판정·지적·조치 대조: [r1](../reviews/20260908T132000-share-client-entry-r1.md) ·
[r2](../reviews/20260908T141000-share-client-entry-r2.md) ·
[r3](../reviews/20260908T150000-share-client-entry-r3.md).
각 조치는 **뮤턴트로 봉인을 확인**했다(구현을 훼손하면 해당 테스트가 적색).

### 선재 실패 구분 (판정 = main 대비 차집합)

- 전체 pytest 의 실패 20건은 이 worktree 와 **main(`repo/`) 양쪽에서 동일**하다 — 로컬 환경
  의존이며 이번 변경과 무관하다(`mssql_auth_cooldown` 5 · `scratch` 6 ·
  `share_redaction_invariant` 7 · `side_panel_exclusive` 1 · 기타 1).
- 반대로 **main 에만 있던 실패 1건**(`test_route_parity_p5b`)은 이 cycle 이 ROUTEMAP 을
  재생성해 **해소**됐다.
- `verify_side_panel_exclusive.mjs` C3 2건은 이 cycle 을 위해 jsdom 을 설치하면서 **처음으로
  실행되어** 드러난 선재 결함이다(`main` 동일). 그 게이트는 도구가 **없을 때** 「CI gap 문서화」
  경로로 통과하도록 설계돼 있어, jsdom 없는 환경에서는 영원히 보이지 않는다(§16.7 G15).

### Run 6 — 라이브 배포 후 도달성 (post-deploy)

Environment: live-https
Result: PASS (도달성·서빙 내용 한정 — 아래 «확인하지 않은 것» 참조)
Scenario: 머지·배포한 코드가 **실제로 서빙되는가**.
Evidence (2026-09-08, `https://localhost`):
- `GET /healthz` → `{"status":"ok","git_commit":"fd2d5f1c","mysql_ok":true,"pg_ok":true}`
  — 내 머지 커밋이 라이브에서 돌고 있다.
- `GET /static/share-client-context.js` → **200** (신규 어댑터가 서빙된다).
- `GET /share/<probe>` 의 스탬프 → `share-client-context.js?v=ce592373034d` ·
  `share.js?v=ce592373034d` — `?v=dev` placeholder 가 아니라 **빌드가 주입한 content-hash** 다
  (스탬프 없는 모듈 참조로 배포가 브라우저에 도달하지 못하던 결함 클래스의 재발 아님).
- 서빙되는 `share.js` 에 `appPlatformSupported`·`_adoptIfTheBridgeAcceptsIt` 2건,
  `app/client-bridge.js` 에 `_PERSIST_SURFACES` 2건 — **이번 배선이 실제 서빙 파일에 있다.**

⚠ **확인하지 않은 것 (도달성 ≠ 사용자 흐름).**
- 서버 응답의 `client:{app_link, download_url}` 블록은 **라이브에서 미확인**이다 — 확인하려면
  실제 공유 링크를 만들어야 하고 그것은 운영 데이터에 잔재를 남긴다. 코드 경로는 Run 2 가
  AST·위임 대조로, 조립 정본은 Run 3 이 왕복으로 검증했다.
- 화면에서 어느 버튼이 보이는지, 앱이 그 대화를 여는지는 **Run 5(DQA-client, NOT-RUN)** 의 몫이며
  **클라이언트 재배포 뒤**다. 지금 배포된 것은 서버·정적 자산뿐이므로, 구버전 앱은 딥링크의
  `path` 를 몰라 서비스 루트를 연다(파손이 아니라 의도된 degrade).
- 대화 스모크는 `scope=web` 이라 미수행이다(배포 로그가 그렇게 기록한다) — 이 변경은 대화
  런타임을 건드리지 않지만, 그 사실을 «대화 동작 PASS» 로 합산하지 않는다.
