---
run_at: 2026-09-08T12:55:00+09:00
session: ai/claude-corp/feature-0003-share-client-entry
scope: 딥링크가 목적지 페이지(`path`)까지 나르고, 앱 창이 그 자리를 연다
verdict: 자동검증 PASS / DQA-client 실측 NOT-RUN (아래 Run 별 Result 참조)
---

웹 쪽 계약과 그 검증 정본은 feature-0003 이 소유한다 —
[TASK-20260908T125500-share-client-entry](../../../feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260908T125500-share-client-entry.md).
이 파일은 **클라이언트 쪽 변경**(`client/{core,gui,window}.py`)의 Run 을 기록한다.

### Run 1 — 딥링크 수용·경로 검증·목적지 전달 (pytest)

Environment: pytest
Result: PASS
Scenario: ① 정본(`shared/dqa_identity`)과 사본(`client/core`)이 **같은 경로표**에 같은 답을
낸다(`//evil` protocol-relative · 역슬래시 · `..` · 제어문자 · 길이 초과 거부). ② 서버가
조립한 `dqa-connect://open?…` 을 클라이언트가 그대로 되읽는다(왕복). ③ 그 링크에 토큰이
없다. ④ `path` 를 모르는 구버전도 `base` 를 읽어 루트를 연다(degrade). ⑤ 목적지가 `plan`
까지 도달한다. ⑥ 이미 실행 중 인스턴스로 목적지가 전달되고, 고아·stale 목적지는 다음
요청에 실리지 않는다.
Evidence: `python3 -m pytest unit/feature-0046-native-client/tests -q` → **585 passed**
(`test_wsl_and_scheme.py` · `test_standalone_launch.py` · `test_embedded_window.py` 신규분 포함)

⚠ **적대 검증이 이 Run 의 커버리지를 두 번 정정했다.**
- 1R: 「목적지 전달의 로직 축은 전부 확인」이라는 주장이 **내장 창 갈래에 대해서는 거짓**이었다 —
  `_watch_show_requests` 의 navigate 배선을 통째로 지워도 561건이 전건 초록이었다(뮤턴트 실증).
  가짜 shell 로 `navigate → show` 순서를 재는 테스트를 추가해 닫았다.
- 2R: `os.fchmod` 로 파일을 좁힌 것이 **실 Windows 에서 no-op**(0o666)임이 실측됐다. POSIX
  한정으로 바꾸고, Windows 에서 이 파일을 지키는 것은 `%USERPROFILE%` ACL 이라는 사실을
  docstring 에 정직하게 적었다. 목적지 쓰기 실패가 요청 자체를 삼키던 것도 함께 고쳤다.
- 경계 표를 상수에서 계산했더니 **항진명제**가 되어(상수를 64 로 좁혀도 전건 초록) 상한 값
  자체를 단정하는 테스트를 별도로 두었다.

### Run 2 — 실제 DQA 클라이언트 (창 이동·상주 중 도달)

Environment: DQA-client
Result: NOT-RUN
Scenario: ① 앱이 꺼진 상태에서 공유 화면의 진입 버튼 → 앱이 뜨고 **그 대화**가 열린다.
② 앱이 알림 영역에 상주하는 상태에서 같은 버튼 → 떠 있는 창이 그 대화로 **옮겨진 뒤**
보인다(`Shell.navigate` → `show`). ③ 부적격 경로가 실린 링크 → 앱은 뜨고 루트가 열린다.
Reason: 이 변경은 **설치본 코드**(`client/*.py`)라 반영하려면 설치기를 새로 빌드해야 하는데,
PyInstaller 는 크로스컴파일을 하지 않아 **Windows 에서만** 만들어진다. 이 WSL 세션에서는
변경이 반영된 앱을 띄울 수 없다. 기존 사용자의 앱·연결 세션을 검증 편의로 종료하거나
재설치하지 않는다(PB-0009 실행 3항).
Alternative: 위 Run 1 (536 PASS — 경로 판정·왕복·목적지 전달의 **로직 축**은 전부 실행으로
확인). 한계 — `Shell.navigate` 의 실제 WebView2 `load_url` 동작, 트레이 상주 중의 창 이동
체감, 스킴 핸들러 등록 경로는 실 Windows 에서만 확인된다.
Next: 1.1.2 설치기 빌드·게시 후 위 세 시나리오를 실측하고 같은 `Environment: DQA-client` ·
같은 Scenario 로 Run 을 추가한다. 그때까지 이 시나리오는 PASS 가 아니다.

### Run 3 — 후속: 1.2.5 로 출하 후 실측 (격리 동결본)

Environment: DQA-client
Result: PASS
Build: 격리 동결본 1.2.5 `dist/DQAConnect/`(설치본 아님) · 서버 revision `59fd70f6`
Scenario: **출하되는 동결본**(1.2.5 `dist/DQAConnect/`)을 격리 `%USERPROFILE%` 로 띄워
① 꺼진 상태에서 **목적지가 실린 실행**(스킴 핸들러가 넘기는 것과 같은 argv) → 그 대화가
열린다 ② 상주 중 같은 실행 → 떠 있던 창이 그 대화로 옮겨진다(포트·nonce 동일로 확인)
③ 부적격 경로(질의 밀반입 · protocol-relative · `..`) → 루트가 열린다 ④ 양성 대조.
Evidence: [TASK-20260909T120000-client-125-share-entry Run 4](TASK-20260909T120000-client-125-share-entry.md)
— 프로브 로그로 **앱이 실제 요청한 URL** 을 측정.

⚠ 이 Run 은 위 **Run 2 의 Scenario 를 대체하지 않는다.** Run 2 는 「공유 화면의 진입 버튼」
부터 시작하는 종단 경로이고, 여기서 잰 것은 그 뒤의 **클라이언트 축**이다. 아직 재지 않은
연결 고리 둘: **설치본**(Inno 설치 후 실행)과 **OS 스킴 핸들러 발사**. 등록은 읽기로 확인했으나
(`HKCU\Software\Classes\dqa-connect\shell\open\command` = 설치본 + `"%1"`) 그 명령이 지금
가리키는 것은 사용자의 **1.2.4** 다. 1.2.5 는 채널에 올라갔고, 무음 적용은 기본 꺼짐
(서명 없는 설치기라 사용자 결정 2026-09-07) — 사용자가 [업데이트 확인] 에서 수락한 뒤에야
그 두 고리를 잴 수 있다.
