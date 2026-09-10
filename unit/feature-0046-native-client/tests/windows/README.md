# 실 Windows 실측 스크립트 (pytest 가 아니다)

이 폴더는 **리눅스 CI 가 원리적으로 구동할 수 없는 층**을 실제 Windows 에서 돌린다.
`client/tray.py` 의 `Win32Backend` 와 `client/core.py` 의 창 숨김 인자는 Win32 호출이라,
리눅스에서는 한 줄도 실행되지 않는다 — 그 층을 여기서 구동하지 않으면 **테스트가 있다**와
**검사된다**가 갈린다.

> ⚠ **파일명이 `verify_*.py` 인 것은 의도다.** pytest 기본 수집 패턴(`test_*.py`)에 걸리지
> 않아야 리눅스 CI 가 이것을 import 하려다 실패하지 않는다.

## 왜 이것을 커밋하는가

이 검증을 세션 안에서 즉석으로 만들고 버리면, 다음 작업자는 같은 자리에서 같은 실패를
다시 만난다(AGENTS.md §16.7 G14-d — 「그 자리에서 발명한 검증은 절차에 배선한다」).
아래 두 결함은 **실제로 이 스크립트들이 잡았고, 리눅스 테스트 171건은 전부 통과 중이었다**:

1. `ExtractIconW` 에 argtypes 를 안 걸어 x64 모듈 핸들이 `OverflowError` → **아이콘 등록 자체가 실패**.
2. `AppendMenuW` 에 `MF_DEFAULT` 를 넘김 → **조용히 무시**되어 기본 항목(굵게)이 사라짐.
   (정답은 `SetMenuDefaultItem`.)

## 실행

WSL 에서 Windows 파이썬을 직접 부른다. **`pythonw.exe`(콘솔 없음)로 돌려야 한다** —
`python.exe` 로 돌리면 부모에게 콘솔이 있어 자식이 그것을 물려받고, **재현하려는 결함이
사라진다**(#1·#4 가 그 조건을 판정에 포함한다).

```bash
WINTMP='/mnt/c/Users/<user>/AppData/Local/Temp/dqa-tray-verify'
mkdir -p "$WINTMP/client"
cp unit/feature-0046-native-client/src/client/*.py "$WINTMP/client/"
cp unit/feature-0046-native-client/tests/windows/verify_*.py "$WINTMP/"
PW='/mnt/c/Users/<user>/AppData/Local/Programs/Python/Python314/pythonw.exe'
"$PW" 'C:\Users\<user>\AppData\Local\Temp\dqa-tray-verify\verify_console.py'
cat "$WINTMP/result_console.json"
```

결과는 스크립트 옆의 `result_*.json` 에 떨어진다(`pythonw` 는 표준출력이 없다).

| 스크립트 | 무엇을 재는가 | 판정 |
|---|---|---|
| `verify_console.py` | 콘솔 없는 부모가 콘솔 앱 자식을 띄울 때 **새 콘솔이 할당되는가** (대조군 vs 처방군) | 대조군 ≠ 0 · 처방군 = 0 |
| `verify_flicker.py` | **제품 경로**(`wsl_available`·`wsl_which`)가 도는 동안 바탕화면의 `ConsoleWindowClass` 창 수 | 대조군 > baseline · 처방군 = baseline |
| `verify_tray.py` | 아이콘 등록 · `WM_COMMAND` 라우팅 · 더블클릭 기본 동작 · 툴팁/풍선 · 메뉴 조립 · 팝업 표시 · 정리 | 7단계 전부 ok |
| `verify_gui.py` | 실 `ClientApp` 로 「닫기→숨음→연결유지→아이콘에서 복귀→종료」 | 6단계 전부 ok |
| `verify_frozen_icon.py <exe>` | **동결 exe** 에서 `ExtractIconW` 가 앱 아이콘을 내는가 | `hicon ∉ {0,1}` (그 둘이면 기본 아이콘 폴백 — 치명 아님) |
| `verify_embedded_close.py hide` | **주 경로(내장 WebView2 창)**: [X] → 숨음 · 안내 1회 · 아이콘에서 복귀 · **아이콘 사망 후 닫기 = 파괴** | 8단계 전부 ok |
| `verify_embedded_close.py quit` | 트레이 우클릭 **[종료]** 가 프로세스를 실제로 끝내는가 | 6단계 전부 ok |

> ⚠ `verify_embedded_close.py` 는 `window.py` 와 **pywebview·pythonnet** 이 필요하다. 복사할 때
> `src/client/*.py` 전부를 넣고(그 안에 `window.py` 가 있다), 창은 `about:blank` 를 띄운다 —
> 서비스 페이지를 열면 패널이 `discover` 를 자동 호출해 **사용자의 AI 사용량을 쓴다**.
> 한 프로세스에서 `webview.start()` 는 1회뿐이라 **모드를 인자로 받아 두 번** 돌린다.

## 함정 (하네스 쪽에서 실제로 겪었다)

- **합성 입력으로 팝업 메뉴를 닫으려 하지 마라.** `keybd_event(ESC)` 는 전경 잠금 때문에
  다른 창으로 가고, 그 사이 메뉴에서 **엉뚱한 항목이 선택**된다(관측: `hits=['quit']`).
  메뉴 창(`#32768`)을 찾아 **그 창에 직접** `WM_KEYDOWN ESC` 를 보낸다.
- **파괴된 tkinter root 는 `winfo_exists()` 가 0 을 내지 않고 예외를 던진다.** 안 잡으면
  하네스가 죽고, 제품이 옳게 동작한 것이 「검증 실패」로 보인다.
- **제목으로 창을 특정하지 마라 (2026-09-04).** 트레이도 **같은 제목**의 창을 만든다
  (`Tray.title` 이 `CreateWindowExW` 의 창 이름으로 들어간다 — 0×0 비가시 메시지 수신용).
  `FindWindowW(None, 제목)` 은 그것을 먼저 집는다. 클래스로 걸러도 부족했다 — 같은 제목의
  WinForms 창이 **2개**인 실행이 있었고, 그래서 같은 코드가 한 번 PASS 하고 한 번 FAIL 했다.
  **소유자에게 물어라**: `webview.platforms.winforms.BrowserView.instances[uid].Handle`.
- **데몬 워커는 주 스레드가 끝나면 그 자리에서 잘린다 (2026-09-04).** `shell.run()` 이 돌아온
  뒤 결과를 쓰면 **마지막 단정이 결과 파일에 아예 없다** — 「측정하지 않음」이 「측정해서 통과」
  와 구별되지 않는다. `join(timeout)` 으로 닫는다.

- `verify_gui.py` 는 `discover_runtime` 을 비워 **사용자의 AI 사용량을 쓰지 않는다.**
  가용성 실증(`verify_answers`)은 실제로 AI 에 질문을 던지므로, 배선 검증에 그것을 섞지 않는다.
- **동결 exe 는 «실행하지 않고» 검사한다.** 실행하면 탐지가 돌아 사용자의 AI 사용량을 쓴다.
  그래서 `verify_frozen_icon.py` 는 앱을 띄우지 않고 산출물 파일에 Win32 호출만 건다.

## 동결 exe 를 만들어 검사하려면

```bash
WB='/mnt/c/Users/<user>/AppData/Local/Temp/dqa-build'
mkdir -p "$WB" && cp -r unit/feature-0046-native-client/src "$WB/"
'/mnt/c/.../Python314/python.exe' 'C:\Users\<user>\AppData\Local\Temp\dqa-build\src\scripts\build_client.py' --skip-installer
```

⚠ 이 빌드 로그는 CP949 콘솔에서 **한글이 깨져 보이지만 종료 코드는 0** 이다 — `build_client.py`
의 `_make_stdio_lossy()`(§P0-I)가 의도한 동작이다. 「깨짐 = 실패」로 읽지 않는다.


## 브랜드 아이콘 검증

`verify_brand_icon.py --src <src> --app <DQAConnect.exe> --setup <Setup.exe> --out <결과 폴더> --surface native|webview`를 Windows 빌드 Python으로 두 번, 각각 별도 프로세스·결과 폴더에서 실행한다(`pefile`은 PyInstaller 의존성). EXE/Setup의 9개 RT_ICON payload와 원본 ICO를 바이트 대조하고, 동봉 자산을 대조한다. 이후 실제 트레이·Tk·WebView2(`about:blank`)의 아이콘을 PNG로 저장하여 동일 크기 ICO 프레임과 픽셀 대조한다. AI 감지·로그인·질의를 실행하지 않는다.

핸들은 `c_ssize_t`→`.NET Int64`→`IntPtr`로 옮긴다(x64 부호 확장 보존). 기대값은 .NET의 자동 프레임 선택에 의존하지 않고 ICO 내 동일 크기 프레임 하나만 분리해 읽는다. Tk의 앱 기본 아이콘은 `WM_GETICON` 또는 창 클래스의 `GCLP_HICON`에서 얻는다.

WebView2 창 아이콘은 `shown` 이벤트 후 검사한다. `about:blank`의 페이지 로드 이벤트를 창 생성 증거로 기다리지 않는다.

## DQA 1.2.0 AI 연결 검증

`verify_connect_native.py <staging>`은 Windows에서 빌드한 실제 `dist/DQAConnect/DQAConnect.exe`를 두 번 실행한다. 첫 실행에서 Codex 자동 연결과 Claude 중복 위치 선택을 확인하고, 같은 격리 프로필로 다시 실행해 선택 재사용과 플랫폼별 완료 toast를 확인한다. 이 드라이버는 Windows `python.exe`로 실행하며 JSON 결과를 남긴다.

- staging에는 `src/`, 제품 `static/`, `dist/DQAConnect/`, `rootCA.crt`, `fake-bin/`을 둔다. `FakeAI.cs`를 claude.exe/codex.exe/wsl.exe로 빌드해 공식 CLI 응답을 대역 처리한다.
- 실제 DQA의 WebView2·로컬 Bridge·동봉 Python·감독 프로세스·배포 러너·서버 heartbeat/receipt 왕복을 실행한다. 서비스 로그인/API, app.js toast와 초기화 호출, 벤더 CLI 응답은 fixture다.
- 기존 사용자 앱을 종료하지 않는다. 정확히 staging exe 경로와 일치하는 프로세스 트리만 회차 전후 정리한다. 프로필은 실행마다 새로 만들고 그 안의 두 회차에서만 공유한다.
- 결과: `native-evidence/native-results.json`. 이 호스트의 네이티브 픽셀 캡처는 빈 면이라 유효 증거로 저장하지 않는다. 캡처 불가는 실제 앱 요소/브리지 검증 결과와 별개다.
- `verify_connect_visual.py`는 일반 Windows Chrome/CDP로 같은 제품 자산을 렌더하는 보조 검증이다. DQA 창·로그인·브리지 검증을 대신하지 않는다.

이번 실행 지문과 검증 경계는 [실행 원장](../../docs/test-runs.d/20260908T123400-connect-discovery.md)을 따른다.

## 텍스트 선택·복사 검증

`verify_text_interaction.py <staging> [control]`은 staging의 `src/client`와 `static/css`를 이용해 실제 제품 Shell/WebView2를 실행한다. `control`은 이전 선택/단축키 설정을 재현한다. 답변·Markdown·원문 코드 fixture의 실제 드래그, Ctrl+C/V, Windows Clipboard와 입력창 동일성, 읽기 전용 본문을 확인한다. 사용자 클립보드는 출력하지 않고 종료 시 복원한다. 키 입력은 해당 WebView2의 CDP에만 전달한다.

현재 호스트에서 CDP는 브라우저 기본 검색 UI에 입력을 전달하지 못한다. 따라서 Ctrl+F/F3/Shift+F3/Escape 실측은 NOT-RUN, 전체 판정은 PARTIAL이다. 설정값 True 또는 접근성 트리 변화만으로 검색 PASS를 쓰지 않는다. 검색 UI를 확인하려면 실제 앱 소유 창에 전달된 native 입력과 검색어/일치번호/닫힘 증거가 필요하다. 서비스 인증/API·실제 사용자 대화는 이 fixture 범위가 아니다.

## 설치파일 없이 앱 내부 갱신

`verify_inapp_update.py --first <격리 AppId 최초 설치기> --second <다음 버전 Update ZIP> --root <새 dqa-inapp 경로> --cert <localhost 인증서> --key <키> --spki <지문> [--notes <실제 release-notes-data.js/release-notes.js/profile CSS를 release-notes.css로 복사한 폴더>]`.

최초 설치는 테스트 전용 AppId·프로토콜·메뉴 그룹으로 컴파일해야 한다. 실제 사용자 설치기를 시험 경로에 실행하면 같은 제거 레지스트리를 변경하므로 허용하지 않는다. 갱신 대상은 Setup이 아닌 ZIP이다. 실제 설치본의 로컬 브리지에서 확인/적용하고 자기 확인창의 Yes만 누른다. 현재 app/runner PID·작성 문구·페이지·쿠키 및 다음 실행 버전을 확인한다. 실패 경계는 설치 mutex·잘못된 해시·포인터 공유 잠금이다. 서버 페이지/러너는 대역이며 실제 AI 제공자 질의·사용자 로그인은 이 검증에 포함되지 않는다.

## ChatGPT 데스크톱 위치 검증

`verify_connect_native.py <stage> --desktop`은 PATH에 codex가 없는 별도 프로필에 `fixtures/codex.exe`를 앱 표준 해시 폴더로 준비한다. fake-bin에는 claude.exe와 wsl.exe만 둔다. fixture Codex는 version/login/exec 및 liveness 요청에 `{"alive":true}`를 응답해야 한다. 실제 동결 DQA/WebView2에서 최초 연결과 프로필 재실행의 desktop 경로·라벨·heartbeat를 검증한다. 실제 사용자 계정의 제공자 응답 검증과는 구분한다.
