---
run_at: 2026-09-07T16:00:00+09:00
session: asset-stamp-reach (ai/claude/feature-0003-asset-stamp-reach)
scope: 스탬프 없는 모듈 참조 → 배포 미도달
verdict: PASS (전수 census + 역검증) / 라이브 재실측은 배포 후
---

### Run (2026-09-07) — 라이브 — **Environment: 실 Windows 설치본(DQAConnect.exe) + WebView2 CDP**

결함을 **찾은** 실측이다. 직전 주기(자동 연결)를 앱 창에서 재현하려 했더니 동작하지 않았다.

| 물음 | 수단 | 값 |
|---|---|---|
| 서버가 무엇을 서빙하나 | `fetch('/static/app/client-bridge.js', {cache:'no-store'})` | **새 코드** (9172자, `ambiguousPlatforms` 있음) |
| 페이지가 무엇을 적재했나 | `await import('/static/app/client-bridge.js')` | **구 코드** (`exports = bridgeCall, clientBridge, initClientPanel`) |
| 문서 리소스 항목 | `performance.getEntriesByType('resource')` | `client-bridge.js` (쿼리 없음), decoded **10721B** vs 새 파일 12971B |
| 전체 참조 중 무스탬프 | 소스 census | **1/103** (`./client-bridge.js`) |

⚠ **`fetch` 만 봤으면 「정상」으로 읽혔다.** 갈라낸 것은 모듈 맵에서 인스턴스를 꺼낸 쪽이다.

### Run (2026-09-07) — 라이브 — **Environment: 실 Windows 설치본 (직전 주기 TASK-20260907T060000 의 나머지 두 축)**

같은 세션에서 함께 잰 값이라 여기 남긴다 — 이 두 축은 **클라이언트 쪽 변경**이라 스탬프
결함의 영향을 받지 않았다(설치본을 새로 빌드해 설치했다).

| 축 | 수단 | 결과 |
|---|---|---|
| 확인 창이 뜨지 않는가 | 연결 실행 중 최상위 창 열거(`MainWindowTitle`) | ✅ DQAConnect 는 「DQA」 본창 하나뿐 |
| 연결이 되는가 | 패널에서 `codex (WSL)` 선택 → 연결 | ✅ 「내 AI가 연결되었습니다」 |
| 끝난 뒤 알리는가 | 화면 캡처(주 모니터 작업영역 우하단) | ✅ `DQAConnect.exe` / **DQA** / 「codex (WSL) 로 연결했습니다…」 |

| 자동 연결(중복 플랫폼) | 사용자 머신은 `claude` 가 둘(Windows·WSL) | ✅ 자동 연결 안 함 — 「어느 것으로 연결할지 골라 주세요」 |

⚠ **자동 연결의 «고유 플랫폼» 분기는 이 시점에 실패했고**, 그 원인이 본 주기의 결함이다.

### 관측된 flake (본 변경과 무관, 정직 표기)

전체 회귀 1회차에서 `test_shutdown_finalizer.py::test_shutdown_finalizer_marks_this_process_processing`
1건 실패. 로그가 원인을 그대로 말한다 — `shutdown finalize: 시간 예산 초과`
(`app.py:567` 의 8초 soft cap). 그 시각 같은 머신에서 PyInstaller 빌드·두 번째 클라이언트
인스턴스·컨테이너 빌드가 함께 돌고 있었다. **격리 재실행 5 passed(RC=0)** 로 flake 를 확인했고,
전체 회귀도 다시 돌렸다. 벽시계 상한에 매인 테스트라 부하에 취약하다 — 본 변경이 만든 것이
아니며, 별건으로 남긴다.

### Run (2026-09-07) — **Environment: host python (census + 역검증)**

- 전수 census: `src/static/**/*.js` 48파일 · 상대 참조 **103건** — 전건 `?v=` 보유. PASS
- 양성 대조군: 스탬프 없는 참조를 실제로 집어내는지 — PASS
- **역검증**: 수정을 원복하니 census 가 그 한 줄을 지목하며 실패
  (`app/connect-modal.js → ./client-bridge.js`). 가드가 이 결함을 잡는다.

### Run (2026-09-07) — 라이브 — **Environment: Windows-browser (배포 후로 이연)**

- 계획: 배포 → 앱 창 재적재 → `import()` 로 신규 export 존재 확인 → 고유 플랫폼 프로필에서
  자동 연결이 실제로 나가는지(브리지 `connect` 호출) 관측.

### Run (2026-09-07) — **Environment: 컨테이너 회귀 `make test`**

- 1차: `test_shutdown_finalizer_marks_this_process_processing` **FAIL** (1건). 재실행 **EXIT=0 / FAILED 0**.
- 원인은 이 변경과 무관한 **벽시계 flake** 다. `_finalize_inflight_runs_on_shutdown()` 은
  `deadline = monotonic() + 8.0` 을 **connect 시도 앞에서** 잡는다 — 주석은 「connect 단계는
  별도」라고 말하지만 실제로는 connect 와 스케줄 지연이 같은 예산을 먹는다. 1차 실행 시각에
  이 머신은 Windows 클라이언트 빌드·배포를 동시에 돌리고 있었고, 로그도 「시간 예산 초과」였다.
- ⚠ **고치지 않았다.** 코드가 자기 주석과 어긋나는 것은 사실이지만 이 주기의 원인이 아니고,
  종료 예산 의미를 바꾸는 변경이다. 별건으로 남긴다.

### Run (2026-09-07, 배포 f62a8b10 이후) — 라이브 — **Environment: 실 Windows 설치본 + WebView2 CDP**

**도달 확인** — 페이지가 적재한 모듈을 다시 꺼내 봤다:

    await import('/static/app/client-bridge.js')
    → exports = [ambiguousPlatforms, bridgeCall, clientBridge, initClientPanel, primaryRuntime]
    리소스: app/client-bridge.js?v=251cebfc26a8   ← 스탬프가 붙었다

수정 전 같은 관측은 `[bridgeCall, clientBridge, initClientPanel]` 이었다. 같은 수단으로
같은 자리를 재서 갈렸으므로, 이 변경이 그 갈림의 원인이다.

**직전 주기(자동 연결)의 두 분기를 실기기에서 확인** — 같은 설치본, 프로필만 다르다:

| 프로필 | 발견된 런타임 | 기대 | 관측 |
|---|---|---|---|
| 고유 플랫폼 | `claude (WSL)` · `codex (WSL)` | 자동 연결 | ✅ 사용자가 아무것도 고르지 않았는데 `connect {"id":"claude (WSL)"}` 가 나갔다(고정 순서대로) |
| 중복 플랫폼(사용자 실기기) | `claude`(Win) · `claude (WSL)` · `codex (WSL)` | **묻는다** | ✅ `connect` 없음 + 「같은 AI 가 여러 자리에 있습니다 — 어느 것으로 연결할지 골라 주세요.」 |

⚠ 고유 플랫폼 관측은 **격리 프로필**(임시 `USERPROFILE`)로 만들었다 — 그 프로필에는 Windows
`claude.exe` 가 보이지 않아 중복이 사라진다. 사용자 머신을 건드리지 않고 다른 분기를 만드는
유일한 방법이었다. 그 프로필에는 서버 로그인 세션이 없어 연결 자체는 「연결 정보를 받지
못했습니다」로 끝났다 — **측정 대상은 「묻지 않고 자동으로 시도했는가」** 이고 그것은 참이다.
정리: 격리 인스턴스·임시 프로필·CDP relay 를 모두 제거하고 사용자 클라이언트는 **디버그 포트
없이** 다시 띄웠다(기존 연결 유지 — 러너는 살아 있다).
