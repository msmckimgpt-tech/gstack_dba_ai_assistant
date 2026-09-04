---
run_at: 2026-09-04T11:40:00+09:00
session: ai/claude/feature-0046-tray-background
scope: unit/feature-0046-native-client — 트레이 상주 + 자식 콘솔 창 제거
verdict: PASS
---

# Run — TASK-20260904T100000 트레이 상주 + AI 호출 백그라운드화

## 1. 단위 (Linux, 헤드리스)

```
python3 -m pytest unit/feature-0046-native-client/tests/ -q
```
- **177 passed** (신규 40건 포함). Environment: `CLI` — 서버·화면 계약이 아니라 로직 검증.

## 2. 뮤테이션 역검증 — 21/21 KILL · NOOP 0

「테스트가 정말 결함을 잡는가」. 각 뮤턴트는 **적용 여부를 diff 로 확인한 뒤** 스위트를 돌렸다
(적용되지 않은 뮤턴트를 KILL 로 세면 그 수치는 자기충족이다).

| # | 뮤턴트 | 결과 |
|---|---|---|
| M1~M3 | `_run`·`check_connection`·`spawn_runner` 에서 창 숨김 인자 제거 | KILL |
| M4 | `hidden_child_kwargs` 를 늘 빈 dict 로 | KILL (5건 FAILED) |
| M5 | `Tray.start` 가 실패를 성공으로 보고 | KILL |
| M6 | `dispatch` 가 비활성 항목도 실행 | KILL |
| M7 | 툴팁 상한 제거 | KILL |
| M8 | 콜백 예외를 그대로 전파(메시지 루프 사망) | KILL |
| M9 | `activate_default` 가 기본 항목 판정 무시 | KILL |
| M10 | 트레이 없이도 창을 숨김(프로그램 분실) | KILL |
| M11 | 닫을 때마다 풍선 알림 | KILL |
| M12 | 「연결됨」 안내 문구를 트레이 유무와 무관하게 고정 | KILL |
| M13 | 트레이 [종료] 가 러너를 남김 | KILL |
| M14 | 트레이 콜백이 GUI 를 직접 조작(스레드 침범) | KILL |
| M15 | 연결 단일 실행 게이트 제거(러너 둘) | KILL |
| M16 | 종료 중에도 러너를 띄움 | KILL |
| M17 | spawn/종료 경합에서 되돌리지 않음 | KILL |
| M18 | 트레이 생존 판정을 존재 판정으로 강등 | KILL |
| M19 | 선택을 상태 객체 대신 **라벨**로 전달(WSL 자리 소실) | KILL |
| M20 | 연결 게이트 미해제(다시 연결 영구 불가) | KILL |
| M21 | `Tray.alive` 가 backend 생존을 무시 | KILL |

⚠ **NOOP 2건을 실제로 만났다** — 적대 리뷰 수정으로 소스가 바뀌어 앞선 뮤턴트의 치환 패턴이
어긋났고, 그때 스위트는 **그냥 통과**했다. 적용되지 않은 뮤턴트를 KILL 로 세면 그 수치는
자기충족이다. 패턴을 고쳐 다시 돌려 21/21·NOOP 0 을 얻었다.

## 3. 실 Windows 실측 — Environment: **Windows-native** (WSL interop → `pythonw.exe` 3.14.7)

⚠ **부모는 콘솔이 없어야 한다.** 배포본(`--windowed`)의 조건이고, 콘솔 있는 부모로 돌리면
자식이 그것을 물려받아 **재현하려는 결함이 사라진다**. 각 스크립트가 `parent_has_console == 0`
을 판정 조건에 포함한다. 재현 절차·판정표는 `tests/windows/README.md`.

### 3-1. `verify_console.py` — 기전 (대조군 vs 처방군)

| 값 | 결과 |
|---|---|
| `parent_has_console` | `0` (콘솔 없는 부모 — 배포본 조건 성립) |
| 대조군(가드 없음) 자식 콘솔 핸들 | **`2430520`**(핸들 값은 실행마다 다르다) — 새 콘솔이 할당됐다 (결함 재현) |
| 처방군(현재 코드) 자식 콘솔 핸들 | **`0`** — 콘솔이 만들어지지 않는다 |

Verdict: **PASS**

### 3-2. `verify_flicker.py` — 제품 경로에서 실제로 창이 뜨는가

`core.wsl_available()` + `core.wsl_which("claude")` 가 도는 동안 바탕화면의
`ConsoleWindowClass` 창 수를 5ms 간격 폴링해 **최대치**를 관측했다.
(AI 를 부르는 경로는 제외 — 사용자의 AI 사용량을 쓴다.)

| 구간 | 콘솔 창 수 peak |
|---|---|
| baseline | 1 |
| 대조군(가드 끔) | **2** — 창이 하나 새로 떴다 |
| 처방군(현재 코드) | **1** — 새 창 없음 |

Verdict: **PASS** — 사용자가 신고한 「켜지고 꺼지는 창」을 재현하고 제거한 것을 직접 관측.

### 3-3. `verify_tray.py` — 알림 영역 아이콘 (7단계 전부 ok)

`available()` / `Shell_NotifyIconW(NIM_ADD)` + 메시지 루프 기동(`hwnd=4786346`) /
`WM_COMMAND` → 해당 항목 실행 / 더블클릭 → 기본 항목 실행 / `NIM_MODIFY`(툴팁)+풍선 후
루프 생존 / **메뉴 조립 실검**(5항목·라벨·ID `1024/1026/1028`·기본 항목 정확히 1개) /
`stop()` → `NIM_DELETE` + 루프 종료. Verdict: **PASS**

### 3-4. `verify_gui.py` — 실 `ClientApp`(tkinter) + 트레이 종단간 (6단계 전부 ok)

트레이 실기동 / 창 보임 / **[X] → 창은 숨고 프로세스는 삶**(`state=withdrawn`,
`exists=1`, `tray_alive=True`) / **아이콘 기본 동작 → 창 복귀**(트레이 스레드 → 큐 →
GUI 스레드 경계 통과) / 두 번째 닫기도 숨김(풍선은 1회) / **[종료] → 창 파괴 + 아이콘 제거**.
Verdict: **PASS**

## 4. 실측이 적발한 결함 2건 (리눅스 테스트는 그동안 전부 통과 중이었다)

1. **ctypes argtypes 누락** — `ExtractIconW` 의 x64 모듈 핸들에서
   `OverflowError: int too long to convert` → 아이콘 등록 자체 실패(`hwnd=0`).
2. **`MF_DEFAULT` 를 `AppendMenuW` 에 전달** — 유효 플래그가 아니라 **조용히 무시**되어
   기본 항목이 사라짐(`GetMenuState` 로 5항목 전부 `default=False` 확인). →
   `SetMenuDefaultItem` 으로 교체.

둘 다 **오류도 경고도 없이 기능만 사라지는** 형태라 정적 검사·리눅스 테스트로는 잡히지 않는다.

### 3-5. `verify_frozen_icon.py` — **동결 exe** 의 아이콘 추출

`build_client.py --skip-installer` 로 실제 배포 형식(onedir + 임베더블 CPython 동봉)을 빌드해
(exit 0 · `DQAConnect.exe` 2,284,758 B · sha256 `4349667c…` · 러너 모듈 임포트 검증 통과),
그 산출물에 `ExtractIconW` 를 걸었다.

| 값 | 결과 |
|---|---|
| `icon_count` | **1** — exe 에 아이콘 리소스가 실재 |
| `hicon` | **`607652473`**(≠ 0, ≠ 1) — 유효 핸들 |

Verdict: **PASS** — 배포본의 트레이 아이콘은 기본 아이콘 폴백이 아니라 **앱 아이콘**이다.
⚠ 앱을 **실행하지는 않았다** — 실행하면 탐지가 돌아 사용자의 AI 사용량을 쓴다.

부수 확인: 빌드 로그가 CP949 콘솔에서 한글이 깨져 나오는데도 **종료 코드는 0** 이었다 —
`_make_stdio_lossy()`(§P0-I)가 의도대로 동작한다.

## 5. 미수행 (과장하지 않는다)
- **실 서버 연결 왕복 중의 트레이 상태 전이** — 유효 토큰이 필요하다. `_on_connected`·`_stop`
  의 툴팁·메뉴 라벨 전이는 단위 테스트로만 고정했다.
- **탐색기 재시작(`TaskbarCreated`) 후 아이콘 재등록** — 코드 경로는 있으나 미실측
  (탐색기를 죽이는 것은 이 머신의 사용자 세션에 영향을 주므로 하지 않았다).
- **동결 exe 를 «실행» 한 트레이 검증** — 실행하면 탐지가 돌아 사용자의 AI 사용량을 쓴다.
  동결 축에서 확인한 것은 **아이콘 추출** 하나이고, 나머지(등록·라우팅·메뉴·정리)는 같은
  코드를 소스 상태 Windows 파이썬으로 구동해 확인했다.
