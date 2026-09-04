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

## 두 가지 함정 (하네스 쪽에서 실제로 겪었다)

- **합성 입력으로 팝업 메뉴를 닫으려 하지 마라.** `keybd_event(ESC)` 는 전경 잠금 때문에
  다른 창으로 가고, 그 사이 메뉴에서 **엉뚱한 항목이 선택**된다(관측: `hits=['quit']`).
  메뉴 창(`#32768`)을 찾아 **그 창에 직접** `WM_KEYDOWN ESC` 를 보낸다.
- **파괴된 tkinter root 는 `winfo_exists()` 가 0 을 내지 않고 예외를 던진다.** 안 잡으면
  하네스가 죽고, 제품이 옳게 동작한 것이 「검증 실패」로 보인다.

- `verify_gui.py` 는 `discover_runtime` 을 비워 **사용자의 AI 사용량을 쓰지 않는다.**
  가용성 실증(`verify_answers`)은 실제로 AI 에 질문을 던지므로, 배선 검증에 그것을 섞지 않는다.
