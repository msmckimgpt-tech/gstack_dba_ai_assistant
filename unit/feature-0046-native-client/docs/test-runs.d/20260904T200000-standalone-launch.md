---
run_at: 2026-09-04T20:10:00+09:00
session: standalone-launch (ai/claude/feature-0046-standalone-launch)
scope: 인자 없는 실행 · 단일 인스턴스(Windows msvcrt) · 동봉 배포 주소 · 창 다시 열기
verdict: PASS (Windows 전용 분기 실측 포함) / 앱 창 라이브는 배포 후
---

### Run (2026-09-04) — Windows 전용 분기 실측 — **Environment: Windows (WSL interop, 창 없음)**

리눅스 테스트는 `fcntl` 갈래만 구동한다. **`msvcrt` 갈래는 그 축에서 한 번도 실행되지 않으므로**
실제 Windows 파이썬(3.14.0)으로 직접 구동했다. 화면을 띄우지 않는 경로만 골랐다 — 사용자의
작업과 겹치지 않게(사용자 지시).

| 항목 | 결과 |
|---|---|
| 잠금 획득 | `True` |
| 같은 프로세스의 두 번째 획득 | **거절** |
| **다른 프로세스**의 획득 | **거절** (핸들 단위가 아니라 OS 잠금임을 확인) |
| 놓은 뒤 재획득 | `True` (크래시 뒤 영영 못 뜨는 상태가 아니다) |
| 설치 폴더의 동봉 주소 | `https://112.185.196.20` |
| `startup_base` 해석 | `https://112.185.196.20` |
| 창 다시 열기 요청 소비 | 1회만 (`True` → `False`) |

빌드: `DQAConnect-Setup-1.0.0.exe` 21,084,054 bytes ·
sha256 `677cce2668c99eb1b3a43b09f3300a056532ad979a13fdf38c544034f07b868e` ·
`service.json` = `{"base": "https://112.185.196.20"}` 가 앱 폴더에 동봉됨을 확인.

### Run (2026-09-04) — 앱 창 라이브 — **Environment: Windows-browser (배포 후로 이연)**

- 이 경로는 **웹의 `client-bridge.js` 새 판이 배포된 뒤에만** 완주한다. 구판 화면은 `connect` 에
  봉투를 싣지 않으므로, 인자 없이 켠 창은 `no_token` 으로 정직하게 거절당한다(설계대로).
- 계획: 배포 → 재설치 → **시작 메뉴 아이콘만** 실행 → 앱 창 → [연결 준비] → 목록 → 연결 →
  창 닫고 아이콘 재실행 시 창 복귀.
