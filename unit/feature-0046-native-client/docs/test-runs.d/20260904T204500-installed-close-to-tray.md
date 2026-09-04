---
run_at: 2026-09-04T20:45:00+09:00
session: ai/claude/feature-0046-close-to-tray-live
scope: 설치본 종단간 — 「[X] 로 닫으면 남고, 트레이 [종료] 로 끝난다」
verdict: PASS
---

### Run (2026-09-04 20:45) — **Environment: Windows-native (설치본 실행)**

`main` `a8f58f46`(PR #1581 머지) 기준 재빌드 → 덮어 설치 → **실행해서 확인**.

- 빌드: `DQAConnect-Setup-1.0.0.exe` 25,692,215 bytes ·
  sha256 `bee0c780025b0c91cb4830309361749a37ca7ebdecb89bd791d3d31a1ef9b9fc`
- 동결본 자가진단: `{'frozen': True, 'webview_import': True, 'runtime_present': True,
  'available': True, 'tkinter': True}`
- 설치: `/VERYSILENT` exit 0 · 설치 폴더 `DQAConnect.exe` 20:36 빌드 ·
  시작 메뉴 `DQA\{DQA.lnk, DQA 제거.lnk}` 둘뿐(옛 이름 잔재 없음 — 직전 cycle 의 정리 유지)

| 단계 | 실측값 | 판정 |
|---|---|---|
| 설치본 실행 → 창 + 트레이 아이콘 | `app=1644744` · `tray=3217494`(`DQAConnectTrayWindow`) · `tasklist` **1건** | PASS |
| **창 [X]** (WM_CLOSE) | `visible=False` · `tasklist` **여전히 1건** | PASS |
| **트레이 [종료]** | `tasklist` **0건** | PASS |

이 세 줄이 `TASK.md` §9 의 [다의어] 블록에 적어 둔 **관측 가능한 값 그대로**다 —
「창 [X] 를 누른 뒤 `tasklist | findstr DQAConnect` 가 여전히 1건이고, 아이콘 우클릭 →
[종료] 뒤에는 0건이다」.

### 어떻게 쟀는가 (합성 클릭이 아니다)

종료는 트레이 창(`DQAConnectTrayWindow`)에 **`WM_COMMAND`(id `0x0404` = 메뉴 5번째 항목
[종료])** 를 보냈다 — 우클릭 팝업에서 항목을 고르면 Windows 가 보내는 **바로 그 메시지**이고,
`Tray.dispatch` 를 같은 경로로 탄다. 합성 마우스 입력으로 팝업을 여닫는 방식은 이 저장소가
이미 실패를 기록한 방법이라(`tests/windows/README.md` 함정 #1) 쓰지 않았다.

### 사용자 AI 사용량을 쓰지 않았다

앱 창만 열고 **연결 모달을 열지 않았다.** `discover`(실제로 AI 에 질문을 던진다)는
`initClientPanel` 에서 도는데 그것은 모달이 부른다 — 창만 여는 경로는 그 앞에서 멈춘다.

### 재고 (남은 것)

- 풍선 알림이 **화면에 그려졌는지**는 이 확인이 재지 못한다(프로세스 생존·창 가시성만 관측).
  발화 자체는 `verify_embedded_close.py` 가 `hide` 모드에서 `balloons=1` 로 확인했다.
- 이 확인 스크립트는 설치본 대상 **1회성**이라 `tests/windows/` 에 커밋하지 않았다 —
  거기 스크립트들은 소스 트리를 복사해 도는 계약이고, 이것은 설치 경로에 묶인다.
  반복이 필요해지면 그때 계약을 맞춰 편입한다.
