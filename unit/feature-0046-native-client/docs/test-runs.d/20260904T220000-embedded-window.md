---
run_at: 2026-09-04T22:00:00+09:00
session: embedded-window (ai/claude/feature-0046-embedded-window)
scope: 앱 창을 프로그램이 직접 그린다 (WebView2 내장) · 보이는 이름 DQA 하나
verdict: PASS (내장 창 라이브 실측 포함) / 연결 완주는 배포 후
---

### Run (2026-09-04) — 직전 주기(#1575)의 이연 항목 해소 — **Environment: Windows-browser**

`20260904T200000-standalone-launch.md` 가 「배포 + 설치본 재빌드 후」로 이연한 항목이다.

- 배포 `4c4dc8a5` 확인(라이브 `livez` · 서빙되는 `client-bridge.js` 에 `_connectLaunch` 실재).
- 새 설치본으로 재설치 후 **인자 없이** `DQAConnect.exe` 실행 → 브리지가 `127.0.0.1:3100` 에
  뜨고 창 목록에 **「DQA — Database Query Assistant」** 실재. **딥링크 없이 아이콘만으로
  서비스가 열린다** — 사용자 제보의 그 지점이 닫혔다.
- 무중단: 배포 창에서 엣지 `no upstreams available` **0건**.

### Run (2026-09-04) — 내장 창 — **Environment: Windows (실제 실행, 창 확인)**

| 항목 | 결과 |
|---|---|
| 동결본 자가진단(`--selftest`) | `frozen: True · webview_import: True · runtime_present: True · available: True · tkinter: True` |
| 창 제목 | `DQA` |
| 창의 주인 | **DQAConnect.exe 자신**(`MainWindowTitle` 이 그 PID 에 붙는다) |
| 새 크로미움 앱 창 | 0개 (측정 시 보인 1개는 **직전 주기 검증의 잔재**, 생성시각 18:34 로 확인 후 정리) |
| 브리지 포트 | 같은 프로세스가 보유(`Get-NetTCPConnection -OwningProcess`) |
| 두 번째 실행 | 종료코드 0 · 인스턴스 **1개** (한 벌 더 뜨지 않는다) |

⚠ 자가진단은 **빌드가 부른다.** 파일이 담겼는지 보는 검사로는 「담기긴 했는데 임포트가 깨진」
상태를 못 본다 — 이 저장소는 그 구분을 못 해서 한 번도 실행된 적 없는 exe 를 배포한 적이 있다.

### Run (2026-09-04) — 앱 창에서 연결 완주 — **Environment: Windows-browser (배포 후로 이연)**

- 이번 cycle 의 웹 문구 변경(`client-bridge.js`·`index.html`·`ai-connect.*`)은 이미지에
  **baked** 되어 배포 후에만 라이브에 반영된다.
- 계획: 배포 → 설치본 재빌드·재설치 → 아이콘 실행 → 내장 창에서 로그인 → [연결 준비] →
  목록 → [이 서비스에 연결] → `ai:ok` → 창 닫고 아이콘 재실행 시 창 복귀.
