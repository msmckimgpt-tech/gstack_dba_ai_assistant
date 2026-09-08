---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0003-agent-web-ui
agent: security,ux
timestamp: 2026-09-08T14:10:00+09:00
trigger: 1R BLOCK 조치의 성립 검증 + 조치가 만든 새 결함
verdict: security BLOCK · ux CONCERN (2라운드)
round: 2
---

# 2라운드 — 조치 재검증

1R 조치를 **넣었다** 는 것과 **성립한다** 는 것은 다르므로 같은 두 축으로 재검증했다.
결과: 1R 지적은 대체로 성립했으나 **조치 중 셋이 뚫렸거나 새 마찰을 만들었다.**

## security — BLOCK

### 1. Blocking issues

- **B1 [HIGH] X1 조치가 성립하지 않는다 — 같은 페이지가 `/static/share.html` 로도 익명 서빙된다.**
  - Evidence: 라이브 `curl -sk -o /dev/null -w '%{http_code}' https://localhost/static/share.html`
    → **200**(`/static/index.html` 도 200). node 하네스에서 `pathname="/static/share.html"` +
    `?client_port=1&client_nonce=EVIL` → `sessionStorage["dqa.bridge"]` 가 **심겼다**.
    대조군 `/share/tok` 은 정상적으로 저장 없음.
  - Location: `unit/feature-0003-agent-web-ui/src/static/app/client-bridge.js:50`
  - Reason: 판정을 «페이지가 무엇인가» 가 아니라 «URL 이 어떻게 생겼는가» 로 했다.
    `StaticFiles(directory=STATIC_DIR)` 가 정적 디렉토리 전체를 익명 서빙하므로 공격자는
    링크 한 줄만 바꿔 X1 이 기술한 결과를 그대로 얻는다 — **1R 이 「닫았다」고 단언한 방어가
    실제로는 서 있지 않았다.**
  - Action: 정규식의 **극성을 뒤집어** 보관 허용 표면을 열거(allow-list)하고 나머지는 전부 열화.
  - **조치 완료**: `_PERSIST_SURFACES = new Set(["/", "/index.html"])`. 경로 표
    (`/share/…` · `/static/share.html` · `/static/index.html` · `/ai/connect` · `/admin` ·
    `/anything/else`)를 실엔진 하네스로 잠갔다.

- **B2 [MEDIUM] `os.fchmod` 가 배포 플랫폼(Windows)에서 no-op — 조치가 그곳에서 무효.**
  - Evidence: 실 Windows CPython 3.14 에서 동일 시퀀스 실행 → 예외 없이 성공, `S_IMODE` = **`0o666`**.
    Linux 에서는 `0o600`. 즉 리눅스에서만 초록인 불변식이었다. 덧붙여 `os.fchmod` 는 Windows
    3.13+ 에만 있어, 그 이하 인터프리터에서는 `AttributeError` → 호출부의 `except OSError` 를
    빠져나가 **두 번째 실행이 죽는다**.
  - Location: `unit/feature-0046-native-client/src/client/core.py:829`
  - Reason: 「방어를 넣었다 ≠ 방어가 성립한다」에 정확히 걸린다. docstring 이 단언한 「소유자만
    읽을 수 있게」가 배포본에서 거짓이었다.
  - Action: POSIX 에서만 호출(`getattr` 방어)하고, Windows 에서는 `%USERPROFILE%` ACL 이
    실제 보호라는 사실을 **정직하게 적는다**.
  - **조치 완료**.

- **B3 [MEDIUM] 목적지 쓰기 실패가 요청 자체를 삼킨다 — 파일을 둘로 가른 이유를 구현이 배반.**
  - Evidence: `os.fdopen` 이 던지게 하고 `request_show` 호출 → 홈에 남은 파일 **0개**(`show.req`
    조차 없음), 상주 앱은 창을 열지 않는다. 실 Windows 에서는 fd 를 닫기 전에 지우려 해
    `.show-*.tmp` 가 `PermissionError [WinError 32]` 로 남고 fd 가 누수됐다.
  - Location: `unit/feature-0046-native-client/src/client/core.py:793`
  - Reason: 선택적 값(목적지)의 실패가 필수 값(신호)의 소실이 됐다 — 이 함수의 docstring 이
    파일을 가른 근거로 든 바로 그 시나리오다.
  - Action: `_write_private` 를 자체 `try` 로 감싸 신호는 반드시 쓰이게, 정리는 `close → unlink`.
  - **조치 완료** (실측: 목적지 실패 시 `take_show_request()` 가 `"/"` 반환, 잔재 0).

### 2. Cross-domain concerns

- **C1 F1 의 «세 겹» 중 3겹(브라우저)은 독립 방어가 아니다.** 흡수 파라미터를 하나 끼우면
  (`?client_port=1&x=?client_port=REAL&client_nonce=REAL`) 개수가 각각 1 이 되어 **공격자 포트 +
  진짜 nonce** 조합이 통과한다(실행 재현). 1·2겹이 막고 있어 실익은 없지만, 대등한 겹으로
  적어 두면 다음 사람이 앞의 둘을 걷어낼 때 남는 것이 뚫리는 휴리스틱 하나다.
  - **조치 완료**: 개수 대신 **모양**을 본다(포트 `^\d{1,5}$` · nonce `^[A-Za-z0-9._~-]{8,128}$` ·
    좌표가 쿼리의 마지막 두 개). 주석에서 이 겹을 «독립 방어» 가 아니라 «조립 규약 위반 탐지»
    로 격하했다. 우회 4종을 하네스로 잠갔다.
- **C2 `base` 축은 pin 이 없으면 무경고로 열린다** — 설치 직후 클라이언트에서 남이 만든
  `open?base=https://evil…` 이 확인창 없이 DQA 브랜드 창에 남의 origin 을 띄운다. 더 강한
  근거(`bundled_service_base`)가 무인 실행 분기에만 걸려 있던 비대칭.
  - **조치 완료**: 딥링크 분기에도 동봉값 대조. 정상 사용(base = 동봉값)에서는 뜨지 않음을
    양성 대조군으로 잠갔다.
- **C3 익명 표면이 「미서명 exe 실행 + 스킴 클릭」을 정상 경험으로 가르친다.** 위험 비교 축이
  1회 페이로드 크기뿐이고 **노출 빈도·주체**가 빠졌다 — `start` 는 계정 소유자가 셋업 때 한 번,
  `open` 은 링크 수신자가 대화마다 누른다.
  - **부분 조치 / 이연**: 미서명 실행 유도를 `docs/SECURITY.md` §7 행에 위험으로 명시했다.
    「브라우저 로그인 경로 되살리기」는 **이연** — 비-Windows 는 이미 열화로 웹 버튼을 보고,
    로그인만 되살려도 그 화면에 참여·fork 버튼이 없어 여전히 막다른 길이라 실익이 없다.
    스킴 하이재킹 근본 해소(소유권 검증·일회성 nonce 교환)는 `dqa_identity` docstring 이
    이미 별도 cycle 로 지정해 둔 축이다.
- **C4 REVIEW 서술이 옛 동작을 기술** — **조치 완료**(정정 + 정정 사실 자체를 기록).

### 3. Challenge to current spec (요지)

- **(1) F2 는 «Unix 의 위협» 을 «Unix 전용 API» 로 «Windows 전용 제품» 에 고쳤다.** 그리고 같은
  Windows 에서 **정말로 새는 싱크는 손대지 않았다** — `open_app_window` 가 `--app=<url>` 로
  `/share/<token>` 을 브라우저 **프로세스 명령줄**에 싣고, `--user-data-dir` 를 주지 않으므로
  토큰이 **기본 프로필 방문 기록**에 남는다(동기화 대상).
  → **이연**(아래 §이연 참조).
- **(2) F4 게이트 미추가는 결론은 옳고 근거가 틀렸다.** 진짜 근거는 「같은 상대가 `server.json`
  으로 이미 다음 실행의 origin 을 지배할 수 있어 한계효용이 0」이다. 부기: mtime 정리는 시계가
  앞서면 무력(실측), `read_text` 는 심볼릭 링크를 따라간다.
  → 근거를 이 문서에 기록. 시계·symlink 는 **이연**.
- **(3) C8 이 소스 문자열·들여쓰기로 센다** → **조치 완료**(AST 판독 + `**` 전개 부재 단정).
- **(4) 「앱 안인가」 판정이 공격자 제어 가능하다는 점이 기록돼 있지 않다** → **조치 완료**
  (코드 주석 + `docs/SECURITY.md`).

## ux — CONCERN

1R 7건은 **모두 성립**(직접 실행 확인). 다만 조치 셋이 새 마찰을 만들었다.

- **F1 [MED] 여백 동기화가 인쇄를 깨뜨렸다** — 인라인 `padding-bottom` 이 `@media print` 를
  이겨, 바가 `display:none` 인 지면에 95~157px 공백이 남는다(실측). → **조치 완료**
  (`padding: 0 !important` + `matchMedia("print")` 가드, 실측 print padding = 0).
- **F2 [MED] 상시 설명이 클릭의 «유일한 피드백» 을 삼켰다** — 출현 이벤트가 텍스트 교체로
  격하. 같은 바의 다른 세 액션은 전부 버튼 안에서 말한다. → **조치 완료**(버튼 상태 + 회귀).
- **F3 [MED] 이미 멤버 화면이 모순된 제안을 나란히 세운다** — 「대화로 이동」 옆에 「앱에서
  참여」와 「참여는 앱에서 한다」가 공존. → **조치 완료**(그 갈래는 `can_fork` 만, 라벨·설명에서
  «참여» 제거, 가시 컨트롤 집합을 하네스가 단정).
- **F4 [MED] T9 가 항진명제라 예산을 고정하지 못한다** — `pad >= fh` 는 구현(`pad = ceil(fh)+12`)의
  되풀이라 바가 500px 여도 초록. 실제로 320×568 에서 **31% 점유**. → **조치 완료**
  (절대 예산 25% + 실기기 높이 + 좁은 폭에서 받기 링크를 안내문 안으로 → 23%).
- **C1 「Windows」 표기가 다운로드 결정 시점에 사라진다** → 이후 추가된 **비-Windows 열화**로
  자연 해소(그 기기에서는 앱 진입·받기가 아예 뜨지 않는다). 리뷰 스냅샷 시차.
- **C2 `build_page` 의 스크립트 제거 목록이 stale** — `defer`·`type="module"` 을 놓쳐 replace 가
  무동작이었고, 무해했던 이유가 `about:blank` 라는 **우연**이었다. → **조치 완료**(정규식 +
  제거 성립 단정).
- **§3 비지원 플랫폼** → 비-Windows 열화로 해소(리뷰 이후 조치).
- **§3(2) 열화 발동이 관측 불가** → **이연**(아래).

## 이 라운드가 스스로 잡은 것 (리뷰어 지적 밖)

- **경계 테스트를 상수에서 계산했더니 항진명제가 됐다.** `MAX_APP_PATH-1`/`MAX_APP_PATH` 로
  적으면 상수를 64 로 좁혀도 표가 함께 움직여 전건 초록이다(실측). → 상한 **값 자체**를
  단정하는 테스트를 별도로 추가(뮤턴트로 적색 확인).
- **`hint.textContent` 대입이 안으로 접힌 받기 링크를 삭제했다.** F4 조치가 만든 실제 버그 —
  자식 span 슬롯으로 분리하고 하네스가 링크 생존을 단정한다.
- **하네스 두 곳의 테스트 nonce 가 실제 규격 밖이었다**(`n-abc`·`n-test`). C1 모양 검사가 그것을
  거부해 드러났다 — 하네스가 제품과 다른 것을 재고 있었다는 뜻이라 실 규격
  (`secrets.token_urlsafe(24)` = 32자)으로 맞췄다.

## 이연 (닫지 않고 기록만 — 근거 포함)

1. **브라우저 명령줄·방문 기록의 공유 토큰** (2R §3-1). `--app=<url>` 구조는 P0-V(앱 창이 곧
   제품)의 성질이고, 이번 cycle 이 그 자리에 `/share/<token>` 을 실으면서 노출이 생겼다.
   해소하려면 목적지 전달을 URL 이 아닌 채널(브리지 IPC)로 옮겨야 하며 그것은 앱 창 구조 변경이다.
2. **스킴 하이재킹의 노출 빈도 증가** (2R C3). 근본 해소는 스킴 소유권 검증·일회성 nonce 교환이고
   `dqa_identity` docstring 이 이미 별도 cycle 로 지정했다.
3. **`server.json` 이 인증되지 않는다** (2R §3-2). `show.path` 게이트 논의가 도달한 **진짜 남은
   질문**. 이 cycle 이 만든 것이 아니고 범위가 클라이언트 신뢰 모델 전체다.
4. **mtime 기반 고아 정리는 시계 전진에 무력 · `read_text` 는 symlink 추종** (2R §3-2 부기).
5. **열화 모드가 관측되지 않는다** (2R ux §3-2). 프런트가 어느 모드로 그렸는지 로그·속성에
   남지 않아 「왜 저 사람 화면엔 웹 버튼이 보이나」를 재현 없이 판별할 수 없다.
6. **`/static/*.html` 이 같은 문서를 두 pathname 으로 노출** (2R B1 부수). allow-list 로 이번
   위험은 닫혔지만, 마운트 자체 정리는 다른 페이지에도 영향이 있어 별도 판단.
7. **`static/ai-connect.js` 의 좌표 규약 세 번째 사본** (1R §8.1 기록).
8. **`verify_side_panel_exclusive.mjs` C3 2건 선재 실패** — jsdom 설치로 드러났고 `main` 동일.
