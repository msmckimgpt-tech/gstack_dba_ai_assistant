---
run_at: 2026-09-09T14:20:00+09:00
session: ai/claude-corp/feature-0046-client-125-share-entry
scope: DQA Connect 1.2.5 — 공유 링크 목적지 수용을 담은 설치본 빌드·게시·실측
verdict: 자동검증 PASS / 격리 동결본 실측 PASS / **설치본 종단은 NOT-RUN** (Run 6)
---

이 릴리스는 **제품 로직을 바꾸지 않는다.** 2026-09-08 에 머지된 딥링크 목적지 수용
(`safe_app_path` · `parse_scheme_url` 의 `path` · `ConnectPlan.path` · `Shell.navigate` ·
`request_show(home, path)`)이 **설치본에 실려 나가게** 하는 것이 전부다. 그 코드가 머지된
시각(2026-09-08 20:07 KST)은 종전 최신 릴리스 1.2.4 의 게시 시각(같은 날 15:33 KST)보다
**4시간 34분 늦다** — 즉 1.2.4 설치본에는 그 코드가 **없었다**.

### Run 1 — 클라이언트 전체 회귀 (pytest)

Environment: pytest
Result: PASS
Build: 소스 트리 `CLIENT_VERSION=1.2.5` · 서버 revision `59fd70f6`
Scenario: 버전 상수·설치기 정의 변경이 릴리스 채널 계약(파일명 정규식·매니페스트·업데이트
판정)과 패키징 계약을 깨지 않는가.
Evidence: `python3 -m pytest unit/feature-0046-native-client/tests -q`
→ **590 passed, 1 skipped, 0 failed** (31.6s)

⚠ **이 변경은 「상수 1줄」이 아니었다.** `test_iss_version_matches_the_canon` 이
`src/installer/DQAConnect.iss` 의 `#define AppVersion` 폴백이 1.2.4 에 머문 것을 잡았다.
빌드는 `/DAppVersion=` 로 정본을 주입하므로 **이번 산출물은 옳았지만**, 폴백이 갈린 채
누군가 손으로 ISCC 를 부르면 파일명과 프로그램이 말하는 버전이 어긋난 설치기가 나온다.

⚠ `test_bridge_security.py::test_read_only_actions_stay_quiet` 는 이 세션의 **전체 실행 1회**
에서 적색이었고(출력 미보존) 곧이은 단독 실행은 초록이었다. 그 뒤 적대 리뷰어가 전체 5회 ·
단독 5회를 돌려 **전부 초록**이었고, 나도 이후 전체 실행에서 재현하지 못했다. 표본 1/12 에
실패 출력도 없으므로 **flake 로 «분류»하지 않는다** — 관측 사실만 남긴다(적대 리뷰 LOW-1).
보안 스위트의 적색을 앞으로 이 문장으로 넘기지 말 것: 다시 붉어지면 출력을 보존해 원인을 본다.

### Run 2 — 동결본에 그 코드가 실렸는가 (바이너리 대조)

Environment: build-artifact
Result: PASS
Build: 동결본 `dist/DQAConnect/DQAConnect.exe` (1.2.5, 6,035,998 B) · 서버 revision `59fd70f6`
Scenario: 「소스에 있다」와 「나갈 파일에 있다」는 다른 문장이다. 빌드 산출물
`dist/DQAConnect/DQAConnect.exe` 안에서 신규 코드의 문자열 상수를 직접 찾는다.
Evidence: PYZ 는 모듈별 zlib 압축이라 평문 매치는 **0** 이다(그것만 보면 「없다」로 오판한다).
압축 스트림을 복원해 훑은 결과 — `show.path` **1개 스트림**, `safe_app_path` **2개
스트림**(`client/core` · `client/gui`). 재현: [scan_frozen.py](../artifacts/20260909-client-125/scan_frozen.py)
(⚠ 「복원한 스트림 개수」는 경계 추정 휴리스틱에 딸린 값 — 이 스캐너로 594, 다른 휴리스틱으로
621. 판정은 개수가 아니라 **매치가 든 스트림의 유무**다.)
⚠ 대상은 **설치기가 담는 앱 폴더**의 exe 다. `DQAConnect-Setup-1.2.5.exe` 자체는 Inno 의 LZMA2
라 같은 스캐너로 0건이며, 앱 폴더 → 설치기의 연결은 빌드 로그의 사실이지 측정이 아니다.
동결본 자가진단
`{frozen: true, webview_import: true, runtime_present: true, available: true, tkinter: true}`.
[build.json](../artifacts/20260909-client-125/build.json)

### Run 3 — 릴리스 채널 도달성 (live-https)

Environment: live-https
Result: PASS
Build: 채널 광고본 1.2.5 (`909d246b…d905d7`) · 서버 revision `59fd70f6`
Scenario: 채널이 1.2.5 를 광고하고, **그 주소에서 실제로 받아지는 바이트**가 매니페스트와
같은가. 내린 버전은 도달 불가인가.
Evidence:
- `GET /api/ai/client/latest` → `1.2.5` · `DQAConnect-Setup-1.2.5.exe` · size `26,051,359` ·
  sha256 `909d246b…d905d7` · path `/client/DQAConnect-Setup-1.2.5.exe`
- `GET /client/DQAConnect-Setup-1.2.5.exe` → **200**, 26,051,359 bytes 수신,
  sha256 **일치**(Windows 빌드 산출물과도 일치).
- `GET /client/DQAConnect-Setup-1.2.4.exe` → **404**. 파손이 아니라 설계다 —
  `client_download` 는 「이름이 규약에 맞는가」가 아니라 「**지금 광고 중인 그것인가**」로
  판정한다(철회가 곧 도달 불가).
- `version.is_newer("1.2.5", "1.2.4") = True` · `("1.2.4","1.2.5") = False` ·
  `("1.2.5","1.2.5") = False` · `("1.2.10","1.2.5") = True`(문자열 아닌 **수치** 비교) ·
  `("1.2.5","1.10.0") = False`.
[published.json](../artifacts/20260909-client-125/published.json)

### Run 4 — 출하 동결본의 목적지 이동 (격리 실행 · **설치본 아님**)

Environment: DQA-client-isolated
Result: PASS
Build: 격리 동결본 1.2.5 `dist/DQAConnect/DQAConnect.exe`
(`607e8831…3378c4`, 6,035,998 B — **설치기가 담는 앱 폴더의 exe**, 설치본 아님) ·
서버 revision `59fd70f6`
Scenario: **출하되는 그 동결본**을 격리된 `%USERPROFILE%` 로 띄워, 앱이 **어느 URL 로
이동하는가** 를 잰다. ① 꺼진 상태에서 목적지가 실린 실행 → 그 대화 ② 상주 중 같은 실행 →
떠 있던 창이 그 대화로 **이동**(같은 브리지 좌표로 확인) ③ 부적격 경로 → 목적지 폐기
④ 양성 대조 ⑤ **정본 조립기가 만든 실제 딥링크**(`dqa-connect://open?…`) ⑥ 상주 중 부적격.

⚠ **`Environment` 를 `DQA-client` 로 적지 않는다** (적대 리뷰 HIGH-4). PB-0009 는 격리
개발본을 설치본·라이브 검증과 **구분**하라고 못박는다. 앞선 판은 산문으로만 구분하고 기계가
읽는 토큰은 「설치본 실측 PASS」와 같았다 — 그 어긋남 자체가 이 프로젝트가 반복해 만든
「초록인데 안 본 것」 이다. 설치본 시나리오는 아래 Run 6 에 `NOT-RUN` 으로 따로 있다.

Evidence — 두 하네스로 나눠 쟀다:
- ①~④ 로컬 프로브 서버(`127.0.0.1:8971`)를 base 로 두고 **앱이 요청한 URL** 을 기록:
  [probe.log](../artifacts/20260909-client-125/probe.log) ·
  [probe_server.py](../artifacts/20260909-client-125/probe_server.py)
- ⑤⑥ **라이브 서비스**(`https://112.185.196.20`)를 base 로 두고 caddy 접근로그에서 확인:
  [caddy-scheme-probe.json](../artifacts/20260909-client-125/caddy-scheme-probe.json)

| # | 입력 | 경로 | 앱이 실제 요청한 것 | 판정 |
|---|---|---|---|---|
| ① 꺼진 상태 | `--path` | `/c/DEST-ONE` | `GET /c/DEST-ONE?client_port=32828&client_nonce=z4Sd…` | 그 대화 |
| ② 상주 중 | `--path` | `/c/DEST-TWO` | `GET /c/DEST-TWO?client_port=32828&client_nonce=z4Sd…` | **같은 포트·nonce** — 떠 있던 창이 이동 |
| ③a 질의 밀반입 | `--path` | `/c/SMUGGLE?client_port=1&client_nonce=STOLEN…` | `GET /?client_port=34172&…` | 루트 + **앱 자기 좌표** |
| ③b protocol-relative | `--path` | `//127.0.0.1:8971/c/PROTOREL` | `GET /?client_port=34227&…` | 루트 |
| ③c 상위 이동 | `--path` | `/c/../../probe-escape` | `GET /?client_port=34253&…` | 루트 |
| ④ 양성 대조 | `--path` | `/c/CONTROL-OK` | `GET /c/CONTROL-OK?client_port=34271&…` | 수용 |
| ⑤ **정본 딥링크** | 스킴 URL 1칸 | `/c/SCHEME-PROBE-2a11df59` | `GET /c/SCHEME-PROBE-2a11df59?…` (404 — 없는 대화, 정상) | 그 대화 |
| ⑥a 상주 + 부적격 | 스킴 URL 1칸 | `/c/RESIDENT-BAD-…?client_port=1&client_nonce=STOLEN…` | **요청 0건** — 목적지 폐기, 창만 앞으로 | 거부 |
| ⑥b 상주 + 양성대조 | 스킴 URL 1칸 | `/c/RESIDENT-OK-eb5f76af` | `GET /c/RESIDENT-OK-eb5f76af?…` (404) | 수용 |

- **② 가 결정적이다.** 포트·nonce 가 ① 과 같다 — 새 프로세스가 자기 창을 연 것이 아니라
  **먼저 떠 있던 창**이 목적지로 이동했다는 뜻이다(`nonce` 는 `secrets.token_urlsafe(24)` 로
  인스턴스마다 새로 만들고 저장하지 않으며, 포트는 임시 포트다 — ③④ 는 실제로 34172·34227·
  34253·34271 로 전부 달랐다).
- **③a 는 보안 단정이다.** 밀반입된 `client_port=1&client_nonce=STOLEN…` 이 **한 글자도**
  최종 URL 에 남지 않았고 앱은 자기 브리지 좌표를 붙였다(1R F1 방어가 동결본에서 성립).
- **⑤ 는 §16.6 요구를 닫는다.** ①~④ 는 내가 조립한 `--path` 인자였다 — 상류가 실제로 만드는
  것은 스킴 URL 이고, 그 경로는 `parse_scheme_url`(1R-F3 의 토큰 배제 분기)과 `safe_app_path`
  를 **한 번 더** 지난다. 그래서 **서버가 쓰는 그 함수**(`shared/dqa_identity.app_open_url`)로
  링크를 만들어 OS 스킴 핸들러가 넘기는 것과 같은 **argv 한 칸**으로 던졌다(적대 리뷰 MED-1).
- **⑥ 은 상주 경로의 세 번째 검증 지점**(`show.path` 를 되읽는 `take_show_request`)을 잰다.
  ③ 은 전부 새 프로세스(포트가 다 달랐다)라 이 갈래를 건드리지 않았다(적대 리뷰 MED-4).
  ⑥a 의 「요청 0건」은 ⑥b 양성 대조가 **같은 상주 인스턴스에서 30초 뒤 성공**했으므로
  「앱이 죽어 있었다」와 구분된다.
- ④⑥b 양성 대조가 없으면 ③⑥a 의 「요청이 없다」가 「앱이 안 떴다」와 구분되지 않는다.
- ⚠ 스킴 URL 을 **프로브 origin** 으로 던진 첫 시도는 「이 프로그램에 들어 있는 주소와 다른
  곳을 열려고 합니다」 확인창에서 멈췄다 — 2R-C2 방어(동봉값 대조를 딥링크에도 건다)가
  동결본에서 성립한다는 뜻이다. ⑤⑥ 은 그래서 **동봉값과 같은** 라이브 base 로 쟀다.
- ⚠ **probe.log 의 `# CASE SMUGGLE` 이 두 번 찍혀 있고 그 사이 16분간 요청이 없다**
  (적대 리뷰 MED-2). 첫 시도는 앱을 **UNC 경로**(`\\wsl.localhost\…`)에서 띄웠는데 냉시동이
  ~45초 걸렸고, 그 하네스를 감싼 `timeout` 이 순회 도중 부모 PowerShell 을 끊었다 — 앱이
  이동에 도달하기 전이다. 그래서 앱 폴더를 로컬 디스크로 복사해 다시 쟀고(냉시동 ~14초),
  표의 ③a 는 **그 재실행** 값이다. 첫 시도는 측정이 아니라 **미실행**이다.

확인하지 **않은** 것 (이 Run 을 넘겨 읽지 말 것):
- **설치본**이 아니다 — 설치기가 담는 그 폴더를 그대로 띄웠다. Inno 설치 후 실행은 Run 6.
- **OS 스킴 핸들러 발사**를 재지 않았다. 등록은 읽기로 확인했다 —
  `HKCU\Software\Classes\dqa-connect` → `URL:DQA`,
  `…\shell\open\command` = `"…\DQA Connect\DQAConnect.exe" "%1"`. ⑤⑥ 은 그 명령이 만드는
  **argv 모양**을 재현한 것이고, 핸들러가 실제로 발사되는 것을 본 것은 아니다. 그 명령이 지금
  가리키는 것은 사용자의 **1.2.4** 다.
- **브라우저 공유 화면의 버튼 클릭**부터의 종단 경로.
- **창이 실제로 앞으로 나왔는지**. 잰 것은 `navigate`(gui.py:1040)가 만든 HTTP 요청이고,
  바로 다음 줄 `show()`(1041)가 실패하거나 창이 최소화된 채여도 로그는 똑같다(적대 리뷰 MED-3).
  캡처를 남기지 않았다.
- **`show.path` 의 파일 권한이 동결본에서도 0600 인지**(POSIX 한정 방어, F2). 소스 수준
  검증만 있다.
- 이 릴리스는 목적지 수용만 나르는 것이 아니다 — 2026-09-08 의 F1·F2·F3·B3·C2 조치가 함께
  실린다. 그중 F2 는 1.2.4 까지의 모든 설치본이 공유 토큰을 널리 읽히게 쓰던 것이다.
- 사용자의 실행 중 앱(PID 29732, `…\Programs\DQA Connect\`)은 **종료·재설치하지 않았다**
  (PB-0009 실행 3항). 이 세션이 만든 격리 홈·프로브 서버·로컬 사본은 정리했다.

### Run 5 — 릴리스노트 렌더링 (node-jsdom)

Environment: node-jsdom
Result: PASS
Build: `release-notes-data.js` + `release-notes.js` 현재 트리 · 서버 revision `59fd70f6`
Scenario: 1.2.5 항목을 넣은 뒤에도 공유 렌더러가 그룹 수·접힘 기본값·일자 정렬·필터·
XSS 안전을 그대로 지키는가, 그리고 그 항목이 실제 DOM 에 나오는가.
Evidence: `node unit/feature-0003-agent-web-ui/tests/verify_release_notes.mjs`
→ **34 passed, 0 failed**. 추가로 같은 jsdom 위에서 렌더한 DOM 의 textContent 에
「공유 링크에서 앱으로 들어가면 이제 「그 대화」 가 열립니다」 · 「DQA 앱 1.2.5 를 올렸습니다」 ·
「알림 영역 아이콘 > [업데이트 확인]」 세 문장이 **실제로 나온다**(항목 512개 렌더). 구조적 봉인
`tests/test_updater.py::test_the_release_notes_carry_an_item_for_the_current_version`
(뮤턴트: 항목의 버전을 1.2.4 로 바꾸면 적색).

### Run 6 — 설치본 종단 경로

Environment: DQA-client
Result: NOT-RUN
Build: 채널 광고본 1.2.5 (`909d246b…d905d7`) · 사용자 설치본은 **1.2.4** (PID 29732)
Scenario: 브라우저 공유 화면에서 `[DQA 앱에서 참여 · fork]` → OS 스킴 핸들러 → **설치된**
1.2.5 앱이 그 대화를 연다. 새 릴리스노트 항목이 앱 창의 프로필 탭에서 실제로 보인다.
Reason: 성립하려면 사용자 머신에 1.2.5 를 **설치**해야 한다. 서명 없는 설치기라 무음 적용은
기본 꺼짐이고(사용자 결정 2026-09-07), 무엇보다 이 시각 사용자의 앱은 **대화 작업 중**이다
(브리지 로그 13:54 작업 디스패치). 검증 편의로 기존 앱·연결 세션을 종료하거나 재설치하지
않는다(PB-0009 실행 3항).
Alternative: Run 1~5. 클라이언트 축(목적지 이동·상주 중 이동·부적격 degrade·정본 딥링크)은
**출하되는 그 동결본**으로 실측했고, 채널 도달성은 라이브에서 바이트 단위로 대조했다.
Next: 사용자가 알림 영역 [업데이트 확인] 에서 1.2.5 를 수락한 뒤, 같은 `Environment` ·
같은 Scenario 로 Run 을 추가한다. 그때까지 이 시나리오는 PASS 가 아니다.

### CI 게이트 부재 (판정에 영향)

이 PR(#1659)에는 **체크가 하나도 등록되지 않았다** — `gh pr view … statusCheckRollup` = `[]`,
`mergeStateStatus` = `CLEAN`. 워크플로가 skip 된 것이 아니라 **저장소 전체에서 돌지 않는다**:
`gh run list` 의 마지막 `CI` 실행은 2026-09-07T02:15Z 이고 **4초 만에 failure** 다(이 저장소가
전에 겪은 Actions 결제 중단의 그 신호 — step 0개 + 수초 + BlobNotFound). 오늘 머지된
#1652~#1655 도 같다.

그래서 **컨테이너 pytest 전체(`make test`)가 이 변경에 대해 돌지 않았다.** worktree 에서는
feature-0003 의 conftest 가 `app` 을 임포트하지 못해 그쪽 pytest 도 로컬로 돌릴 수 없다.
이번 diff 의 feature-0003 몫은 **정적 자산 1개**(`release-notes-data.js`)이고 그것은 실 렌더러
jsdom 34건 + 렌더 DOM 대조로 쟀다. 네이티브 595건은 로컬에서 전부 돌렸다.
CI 가 돌아오면 이 커밋 범위를 다시 통과시켜 확인한다.
