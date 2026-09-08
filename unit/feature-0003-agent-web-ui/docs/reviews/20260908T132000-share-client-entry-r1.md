---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0003-agent-web-ui
agent: security,ux,qa
timestamp: 2026-09-08T13:20:00+09:00
trigger: UI/button/page/layout(공유 화면 액션 바) + token/session(딥링크·스킴·익명 응답) — §18.8
verdict: BLOCK (1라운드)
round: 1
---

# 1라운드 — 적대 검증 패널

세 reviewer 를 병렬로 돌렸다(security · ux · qa). 아래는 **판정과 지적 요지**이며, 각 항목의
Evidence·Location·Reason·Action 원문은 세션 전사에 있고 여기에는 조치 대조에 필요한 만큼을
보존한다. 2라운드 재검증은 `…-r2.md`.

## security — BLOCK

### 1. Blocking issues

- **F1 [HIGH] 쿼리 스머글링 → 브리지 좌표 오염 → 세션 베어러 유출.**
  - Evidence: `safe_app_path("/share/abc?client_port=1337&client_nonce=EVIL")` 가 입력을 **그대로
    반환**(실행 재현). 그 값이 `panel_url` 의 `f"{base}{path}?{q}"` 에 들어가
    `…/share/abc?client_port=1337&client_nonce=EVIL?client_port=51234&client_nonce=REAL` 이 되고,
    `URLSearchParams.get()` 은 **첫 값**을 취하므로 공격자 값이 이긴다. 이어 `bridgeCall` 이
    `http://127.0.0.1:1337/…` 로 나가고 `doConnect` 가 세션 결속 베어러를 그 포트로 POST 한다.
    `#` 변종은 진짜 좌표를 프래그먼트로 밀어내 앱 창이 자기를 앱 밖으로 판정하게 만든다.
  - Location: `shared/dqa_identity.py:149`
  - Reason: docstring 이 열거한 차단 목록은 «다른 origin 으로 새는가» 축만 본다. 그러나 이 값의
    실제 싱크는 origin 이 아니라 **쿼리가 합류하는 지점**이고, 거기에 로컬 브리지 자격이 있다.
  - Action: 정본·사본 양쪽에서 `?`·`#` 거부 + `panel_url` 을 강제 덮어쓰기 조립으로 + 브라우저
    측에서 좌표 중복을 조작 신호로 폐기.

- **F2 [HIGH] `show.path` 가 공유 토큰 전문을 world-readable 로 디스크에 남긴다.**
  - Evidence: 실행 확인 — 모드 `0o664`(umask 022 에서 `0o644`), 내용은 `/share/<token>` 전문.
    `docs/SECURITY.md:325` 는 «share token = `token_prefix[:8]` 만 저장, full token X» 를 못박고,
    `dqa_identity.scheme_url` docstring 도 «디스크에 쓰지 않는다» 를 스킴 설계 근거로 든다.
    이 홈에 들어오는 **첫 비밀 보유 파일**이다.
  - Location: `unit/feature-0046-native-client/src/client/core.py:791`
  - Reason: 그 토큰은 익명 열람 권한을 그대로 주는 베어러다. 평문·기본 퍼미션으로 남기면
    「링크를 받은 사람만 본다」가 「그 머신의 아무 로컬 계정이나 본다」로 바뀐다.
  - Action: `O_EXCL|O_NOFOLLOW` + `0o600` 생성(또는 불투명 핸들), 소비 실패 경로에서도 정리.

- **F3 [MEDIUM] `parse_scheme_url` 이 액션을 구분하지 않아 「open 은 토큰을 싣지 않는다」가
  수용 측에서 집행되지 않는다.**
  - Evidence: 실행 확인 — `open?…&token=mat_ATTACKER` 가 `{'token': 'mat_ATTACKER', …}` 로
    수용된다. 그 값은 `plan.token` 이 되고, 패널이 봉투를 못 준 회차에는 `bridge._plan_for` 의
    폴백이 그것을 그대로 쓴다. 신설 테스트는 *서버가 만든 URL* 에 토큰이 없다는 것만 본다.
  - Location: `unit/feature-0046-native-client/src/client/core.py:880`
  - Reason: 동사를 만들면서 파서에 동사 개념을 넣지 않으면 문서·테스트의 분리는 조립 측 관례일
    뿐이다. 그리고 이번 변경은 «남이 보낸 링크를 받은 사람» 에게 스킴 클릭을 정상 동작으로
    학습시키므로 위험을 정확히 그 방향으로 키운다.
  - Action: host(`open`/`start`)로 키 집합을 좁히고, 테스트를 「파서가 버린다」로 강화.

- **F4 [MEDIUM] `show.path` 가 `server.json` 이 받은 방어 없이 nonce 싱크에 도달한다.**
  - Evidence: `server.json` 에는 «동봉값과 다르면 묻는다» 확인창이 있으나(`gui.py:711-720`)
    `show.path` 에는 게이트가 없다 — 읽은 값이 곧바로 `shell.navigate(panel_url(…, dest))` 로
    들어간다. 쓰기가 비원자적이고 심볼릭 링크를 따라간다. 또 목적지→신호 쓰기 창에 폴러가
    끼어들면 고아 정리가 **방금 쓴 목적지를 지운다**.
  - Location: `unit/feature-0046-native-client/src/client/core.py:759`
  - Reason: 등급이 `server.json` 과 같지 않고 **더 나쁘다** — 상주 중 0.5초 안에 소비되고,
    확인이 없으며, 도달하는 싱크가 라이브 nonce 를 포함한 URL 이다.
  - Action: 원자 교체 + `O_NOFOLLOW`·`0o600`, 고아 정리를 mtime 기반으로, 그리고 nonce 가
    스머글링 대상이 되지 않게 조립을 고칠 것.

### 2. Cross-domain concerns

- **X1 브리지 좌표 캡처가 익명·외부 배포용 공유 페이지에서 실행되게 됐다.**
  - Evidence: 변경 전 `client-bridge.js` 를 import 하는 곳은 인증 앱 하나였다. 이제 공유 화면이
    그 모듈을 쓰므로 최상위 IIFE 가 `/share/{token}` 에서도 돈다 →
    `…/share/<tok>?client_port=1&client_nonce=EVIL` 한 줄로 `sessionStorage["dqa.bridge"]` 가
    심기고 `replaceState` 가 흔적을 지운다. 피해자가 같은 탭에서 앱 루트로 이동하면 그 좌표로
    자동 연결이 토큰을 보낸다.
  - Location: `unit/feature-0003-agent-web-ui/src/static/share-client-context.js:20`
  - Reason: 캡처가 살던 곳은 «로그인해야 도달하는 앱 루트» 였다. 이번 변경이 그것을 «모르는
    사람에게 링크로 건네는 것이 정상 사용인 페이지» 로 옮겼다 — 공격 비용이 «앱 루트로 유인»
    에서 «링크 하나» 로 낮아진다.
  - Action: 공유 페이지는 좌표를 캡처하지 않고 읽기만 하도록 분리.

- **X2 익명 응답이 두 필드 늘었는데 SECURITY.md §7 표·회귀 가드가 따라오지 않았다.**
  - Evidence: `share.py` 가 `client` 블록을 추가했으나 `docs/SECURITY.md` 는 이번 diff 에서
    수정되지 않았고, `test_anonymous_surface_hardening.py` 에 이 엔드포인트가 없다.
  - Location: `unit/feature-0003-agent-web-ui/src/routers/share.py:464`
  - Reason: 실제 유출은 작다(origin·토큰은 요청자가 이미 보유). 문제는 **규율 이탈**이다 —
    표에 없으면 다음 cycle 이 이 블록에 필드를 얹을 때 심사가 걸리지 않는다.
  - Action: §7 표 등재 + 익명 응답 최상위 키 집합 고정 테스트.

### 3. Challenge to current spec

「앱 안인가」를 **링크 발신자가 켤 수 있는 신호**로 판정한 것이 문제다. 같은 값 하나가
(a) 버튼 표시라는 화장품 축과 (b) 로컬 권한 호출의 자격 라우팅 축을 동시에 지배해, 게이트
우회와 자격 오염이 **같은 입력**이 된다. 「프런트 감춤은 인가 통제가 아니다」는 여전히 옳지만
그 문장이 보증하는 것은 「우회해도 아무 일 없다」이지 「우회 **수단**이 무해하다」가 아니다.

## ux — BLOCK

- **[HIGH] `download_url` 없는 회차는 «앱 전용» 이 아니라 완전한 막다른 길.** 그 분기의 안내는
  「앱이 설치되어 있는지 확인해 주세요」뿐이고 받기 버튼은 숨겨져 있으며, 로그인 링크 제거로
  이 페이지의 제품 진입 링크가 **0개**가 됐다. 그리고 이 분기는 예외가 아니다 —
  `_client_download_url` 자신이 리눅스 도커 파이프라인에서는 그 자리가 안 채워진다고 적는다.
  코드는 «우리 쪽 장애»(app_link 부재)에는 열화하면서 **사용자 쪽 결손**에는 아무 열화도 주지
  않는 비대칭을 갖는다. (Location: `static/share.js:282`)
- **[MEDIUM] `already_member` 의 «대화로 이동» 이 앱 뒤로 옮겨졌다.** 그 클릭은 join 도 fork 도
  아닌 순수 웹 이동(`/?conversation=`)이고, 서버는 already_member 에게 `can_join=False` 를 주므로
  앱에서 할 「참여」도 없다. (Location: `static/share.js:212`)
- **[MEDIUM] 하단 고정 바 높이 예산 초과.** `.share-app-hint { flex: 1 1 100% }` 가 행을 하나
  추가하는데 `.share-container` 여백은 상수(80/96px)다. 전용 실브라우저 하네스
  (`tests/headless/verify_share_bar_layout.py`)가 있는데 이번 변경에서 **돌리지 않았다**.
  (Location: `static/share.css:112`)
- **[CONCERN]** 이 화면은 「DQA 앱」을 처음 듣는 사람이 가장 많은 자리인데 설명이 툴팁에만 있다
  (터치 기기 도달 불가) · `inClientApp` 이 모듈 하나에 전량 의존해 실패 시 앱 창이 자기를 앱
  밖으로 판정하고 무한 왕복한다 · 안내가 재클릭을 권하는데 브라우저 셸 등급은 클릭마다 창이
  하나씩 는다 · `--share-muted` 는 **정의되지 않은 변수**다 · live region 이 `display:none`
  상태에서 텍스트를 채워 스크린리더에 통지되지 않는다.
- **[§3]** 앱을 거치게 한 두 동작 중 **어느 것도 앱의 능력을 필요로 하지 않는다** — 순 편익 0에
  데스크톱 설치를 부과한다. 그 비용이 유독 비싼 자리(익명 수신자)라는 점이 문제를 키운다.
  또한 macOS·Linux 수신자에게 안내는 **존재하지 않는 설치물**을 가리킨다.

## qa — (1라운드 진행 중 결과 미도착)

이 파일은 도착한 두 판정으로 조치를 시작한 시점의 기록이다. qa 판정은 도착 시 `…-r2.md` 와
함께 반영한다.
