---
run_at: 2026-09-04T19:30:00+09:00
session: ai/claude/feature-0046-close-to-tray
scope: 닫기 = 트레이로 · 종료 = 아이콘 우클릭 [종료] (3 껍데기 공통 계약)
verdict: PASS (일부 미수행 명시)
---

# Run — 「닫기는 트레이로, 종료는 우클릭 [종료]」

## 1. 단위 — 399 passed (+16, 기준선 383)

새 단정은 **소스 검사가 아니라 구동**이다. 종전에 있던 소스-텍스트 단정 2건
(`"shell.allow_hide = tray is not None"` · `"br.resident = tray is not None"`)은 **정확히
그 defective 형태를 잠그고 있었다** — 문자열이 남아 있으면 통과하므로, 배선이 존재 판정으로
굳어 있어도 초록이었다. 구동 단정으로 바꿨다(§16.7 G11-a).

## 2. 뮤테이션 — 16/16 KILL · SURVIVED 0

| # | 뮤턴트 | 결과 |
|---|---|---|
| M1 | 닫기 게이트 무력화 (`if False`) | KILL |
| M2 | `can_hide` 기본값을 «숨겨도 됨» 으로 | KILL |
| M3 | 숨김 후 안내 호출 제거 | KILL |
| M4 | 판정 예외를 «숨겨도 됨» 으로 | KILL |
| M5 | `hide` 실패를 성공으로 | KILL |
| M6 | `_tray_alive` 를 존재 판정으로 | KILL |
| M7 | 안내 1회 계약 제거 (매번 발화) | KILL |
| M8 | 죽은 아이콘에도 안내 | KILL |
| M9 | 내장 껍데기 게이트를 존재 판정으로 | KILL |
| M10 | 내장 껍데기 안내 배선 제거 | KILL |
| M11 | 내장 상주 판정을 존재로 | KILL |
| M12 | 브라우저 상주 판정을 존재로 | KILL |
| M13 | probe 부재를 «유지됨» 으로 | KILL |
| M14 | probe 예외를 «유지됨» 으로 | KILL |
| M15 | tkinter 판을 존재 판정으로 | KILL |

## 3. 실 Windows 실측 — `tests/windows/verify_embedded_close.py` (신설)

**Environment: Windows-native (pythonw.exe 3.14 · WebView2 · 실 트레이)**
— 웹 브라우저 시각검증(PB-0008)이 아니라 **네이티브 창·알림 영역 층**의 실측이다. 이 층은
리눅스에서 한 줄도 돌지 않는다.

### 3-a. `hide` 모드 — 3회 연속 PASS (결정적)

| 단계 | 실측값 |
|---|---|
| 트레이 아이콘 실재 | `started=True alive=True err=None` |
| 내장 창 가시 | `class=WindowsForms10.Window.8.app.0.aec740_r46_ad1` |
| [X](WM_CLOSE) → 숨음 | `is_window=True visible=False last_error=None` |
| 안내 1회 | `on_hidden=1 balloons=1` · 문구에 「오른쪽 클릭」 포함 |
| 두 번째 닫기 | `on_hidden=2 balloons=1` (반복 없음) |
| 아이콘에서 복귀 | `visible=True` |
| 아이콘 사망 후 판정 | `alive=False` · `can_hide()=False` |
| **아이콘 사망 후 닫기** | `is_window=False` — **창이 실제로 파괴된다** |

### 3-b. `quit` 모드 — PASS (사용자 요청 2번째 항목)

`menu=[(1024,'창 열기'),(1026,'연결 끊기'),(1028,'종료')]` · [종료] dispatch →
`dispatched=True is_window=False` · `run()` 반환.

### 3-c. tkinter 폴백 회귀 — `verify_gui.py` 6단계 PASS

`_tray_live` 를 공유 seam 으로 바꾸고 문구를 상수로 수렴한 뒤에도 종전 계약 그대로.

### ⚠ 이 실행이 **하네스 결함 두 건**을 먼저 잡았다 (기록 가치)

1. **제목으로 창을 특정한 것이 비결정적이었다.** 트레이도 같은 제목의 창을 만든다
   (`Tray.title` → `CreateWindowExW` 의 창 이름, 0×0 비가시). 초판은 그것을 집어
   「보이지 않는 창」으로 FAIL 했고, 클래스로 걸러도 **같은 제목의 WinForms 창이 2개**인
   실행이 있었다(run 3 의 `same_title_windows` 진단이 남겼다). 같은 코드가 한 번 PASS 하고
   한 번 FAIL 하는 하네스는 제품 결함보다 나쁘다 — 어느 쪽이 틀렸는지 말해 주지 않는다.
   → **pywebview 가 들고 있는 Form 핸들**(`BrowserView.instances[uid].Handle`)을 직접 쓴다.
2. **데몬 워커가 주 스레드 종료에 잘렸다.** `shell.run()` 이 돌아오면 주 스레드가 끝나고
   워커가 그 자리에서 죽어, **마지막 단정이 결과 파일에 아예 없었다** — 「측정하지 않은 것」이
   「측정해서 통과한 것」과 구별되지 않는 형태다. `join(timeout)` 으로 닫았다.

그리고 이 두 진단을 가능하게 한 것이 제품에 새로 넣은 **`Shell.last_error`** 다. 그 필드가
없던 초판에서는 「닫기가 종료가 됐다」만 보이고 원인이 어디에도 없었다.

## 4. codex 적대 리뷰 2라운드 — 1라운드 수정이 만든 결함을 되돌렸다

| 라운드 | P1 | P2 | 처리 |
|---|---|---|---|
| 1 | 0 | 1 (브라우저 껍데기만 첫-닫기 안내 없음) | 무신호를 「닫힘」으로 읽어 안내 추가 |
| 2 | 0 | 1 (**그 추정이 틀린다**) | **되돌림** + 결정을 테스트 2건으로 잠금 |

2라운드 지적을 코드로 확인했다: 패널의 20초 ping 은 `initClientPanel` **안에서** 시작한다
(`client-bridge.js` L178, L96 조기 반환 뒤). 연결 모달을 열지 않은 사용자는 ping 을 **아예**
보내지 않으므로, 무신호는 「닫혔다」의 증거가 아니다. 그 상태에서 안내를 내면 **창이 열려
있는데** 「알림 영역에 있습니다」를 말한다 — 이 cycle 이 없애려던 §P0-R 그 자체다.

수렴 판정(§18.8 계약): 마지막 라운드 **P1 0**, P2 는 접근 되돌림으로 소멸. 라운드 상한 미도달.

## 5. 미수행 (과장하지 않는다)

- ⛔ **풍선이 화면에 그려졌는지는 재지 못했다.** 잰 것은 안내 콜백이 불렸고
  `Shell_NotifyIconW(NIM_MODIFY)` 가 예외 없이 나갔다는 사실까지다. 문구 자체는 단위
  테스트가 상수로 잠근다(`test_the_notice_names_the_way_to_actually_quit`).
- ⛔ **패널 문구의 주기 갱신 — 미착수(별도 cycle).** 브리지는 이제 매번 새로 판정하지만
  `client-bridge.js` 는 패널 초기화에서 `resident` 를 **1회만** 묻는다. `static/**` 을 건드리면
  check #13 시각검증 hard gate 가 걸리고, 그 패널을 실제로 띄우면 `discover` 가 자동으로 돌아
  **사용자의 AI 사용량을 쓴다**(`initClientPanel` → `refresh()` → `verify_answers`).
- ⛔ **브라우저 껍데기의 첫-닫기 안내 — 의도적 부재.** 닫힘 이벤트가 없어 낼 근거가 없다.
  그 껍데기의 패널 문구(`client-bridge.js` `_paintResidency`)는 「알림 영역에 남아 있습니다」
  까지만 말하고 **종료 경로를 말하지 않는다** — 한 줄 카피 수정이지만 `static/**` 이라
  check #13 이 걸리므로 상주-문구 갱신과 같은 cycle 로 묶는다.
- ⛔ **설치본 재배포 미수행** — 이 변경은 소스이고, 사용자 머신의 `DQAConnect.exe` 는
  2026-09-04 17:38 빌드다. 재빌드·재설치 전에는 화면에서 이 동작을 볼 수 없다.
