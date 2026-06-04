---
doc_type: TEST
feature_id: feature-0008-windows-browser-testing
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope
- 검증: win-browser.py 드라이버(브리지 감지·시나리오 엔진), 브리지 진단(doctor),
  보안 강화(allow_origins 비-와일드카드, profile per-user, relay vEthernet 한정),
  verify-completion check #13 의 web 변경 게이팅 로직.
- 환경 분류는 AGENTS.md §15.4.1 / `unit/_template/docs/TEST.md` §1 참조.
- 실 검증 완료(2026-06-04): 무권한 auto-relay 로 실제 Windows Chrome CDP wire end-to-end +
  웹 UI 로드 + 로그인 기능 e2e (§3 Run 003/004).

## 2. Test Cases
### TEST-0001 — 시나리오 엔진 dispatch
- Purpose: `_run_step` 가 goto/click/type/eval/assert_text/assert_visible/screenshot/unknown 을 정확히 처리하는지.
- Preconditions: fake page stub (Playwright 불요).
- Steps: `pytest unit/feature-0008-windows-browser-testing/tests`.
- Expected Result: 10 케이스 전부 PASS (assert_text 성공/실패, assert_visible 실패, screenshot 파일 생성, endpoint 후보에 relay 포함, forced override 등).

### TEST-0002 — doctor 브리지 진단
- Purpose: chrome/playwright/win_host 감지 + 브리지 미구성 시 actionable next_steps.
- Preconditions: WSL2, Windows Chrome 설치.
- Steps: `python3 bin/win-browser.py doctor`.
- Expected Result: chrome 경로·win_host·playwright=installed 보고, 브리지 없으면 setup(A/B) 안내.

### TEST-0003 — 보안 강화 (회귀 방지)
- Purpose: allow_origins 가 `*` 아님, profile 이 per-user(%LOCALAPPDATA%), launch flag 에 `--remote-debugging-address=0.0.0.0` 부재.
- Preconditions: 없음 (정적/단위).
- Steps: allow_origins()/profile_path() 호출 + launch flag 검사.
- Expected Result: origins = loopback+relay 구체값, profile = `C:\Users\...\AppData\Local\win-browser-cdp`.

### TEST-0004 — 실제 Windows 브라우저 e2e (DQA 웹 UI)
- Purpose: 실제 Windows Chrome 을 CDP 자동 구동해 웹앱을 로드·조작하고 기능을 검증.
- Preconditions: 웹앱 기동(https://localhost:18080) + Windows python(무권한 relay).
- Steps: PB-0008 절차로 `launch` → `run --scenario` → 스크린샷 → §3 기록.
- Expected Result: `bridge_mode=relay`, 웹 UI 로드(200, "DQA"), 로그인 e2e 인증실패 경로 동작, 스크린샷 생성. (§3 Run 003/004 — PASS)

### TEST-0005 — 무권한 auto-relay turnkey
- Purpose: admin/WSL재시작 없이 `launch` 한 번으로 Chrome+relay 브리지 성립.
- Preconditions: Windows python 설치.
- Steps: `down` → `launch --url …` → `"bridge_mode"`/`"relay"` 확인.
- Expected Result: `bridge_mode=relay`, relay note "… no-admin", endpoint http://<vEthernet>:9223. (§3 Run 003 — PASS)

### TEST-0006 — Playwright MCP attach (in-loop 도구)
- Purpose: `@playwright/mcp` 가 무권한 relay 경유로 실제 Windows Chrome 에 attach 해 MCP 도구로 구동되는지.
- Preconditions: 브리지 기동 + node/npx + `bin/playwright-mcp.sh`.
- Steps: `win-browser.py launch` → MCP 서버에 JSON-RPC initialize + `browser_navigate` 호출.
- Expected Result: serverInfo Playwright, browser_navigate 가 실제 Chrome 을 https://localhost:18080 로 이동 + Page Title "DQA…" 반환. (§3 Run 005 — PASS)

## 3. Test Run History
<!-- append-only: 새 실행 결과를 아래에 추가한다. 기존 결과를 수정하거나 삭제하지 않는다. -->

### Run 2026-06-04-001
- Date: 2026-06-04
- Environment: CLI
- Runner: AI
- Bridge: n/a
- Evidence: pytest 출력 (10 passed)
- Result Summary: 시나리오 엔진 단위 테스트 10/10 PASS (TEST-0001).
- Pass/Fail: PASS
- Notes: fake page stub 기반. connect_over_cdp 자체는 표준 Playwright API.

### Run 2026-06-04-002
- Date: 2026-06-04
- Environment: CLI
- Runner: AI
- Bridge: n/a
- Evidence: doctor JSON (chrome=True, playwright=installed, win_host=172.28.64.1), allow_origins/profile 출력
- Result Summary: doctor 진단 정확(TEST-0002) + 보안 강화 회귀 확인(TEST-0003) — origins 비-와일드카드, profile per-user.
- Pass/Fail: PASS
- Notes: 브리지 미구성 상태에서 next_steps(A/B) 정상 안내. spike 에서 Windows Chrome 기동 + CDP 127.0.0.1 바인딩 확인됨.

### Run 2026-06-04-003 — 첫 실제 Windows-browser 검증 (smoke)
- Date: 2026-06-04
- Environment: **Windows-browser**
- Runner: AI (claude)
- Bridge: relay (무권한 userspace, `launch` 자동 기동) @ http://172.28.64.1:9223, Chrome/148.0.7778.217
- Evidence: `artifacts/shared/out/win-browser/01_login.png`
- Result Summary: `launch --url https://localhost:18080/` → 실제 Windows Chrome 가 웹앱 로드. eval 결과 title="DQA — Database Query Assistant", url=https://localhost:18080/, form+12 inputs+38 buttons. status 200. self-signed 는 `--ignore-certificate-errors` 로 통과.
- Pass/Fail: PASS
- Notes: admin·WSL재시작 없이 무권한 relay(Windows python)로 브리지 성립 — TEST-0005 충족. screenshot 시각 확인됨(로그인 카드 정상 렌더).

### Run 2026-06-04-004 — 로그인 기능 e2e (인증 실패 경로, 비파괴)
- Date: 2026-06-04
- Environment: **Windows-browser**
- Runner: AI (claude)
- Bridge: relay (무권한 userspace) @ http://172.28.64.1:9223
- Evidence: `artifacts/shared/out/win-browser/02_after_attempt.png`
- Result Summary: 시나리오 10 step 전부 PASS. `#loginUsername`/`#loginPassword` 실제 키보드 입력 반영(eval `qa_invalid_user|pwlen=23`) → `#loginForm button[type=submit]` 클릭 → 백엔드 인증 거부 → 화면에 빨간 **"로그인에 실패했습니다."** 표시 + stillOnLogin=true. 풀스택(실 Windows 브라우저 → WSL web → 백엔드 auth → UI 에러) 동작 확인.
- Pass/Fail: PASS
- Notes: 비파괴(오입력 → 실패). 스크린샷 시각 확인. CLI(curl)/WSL-headless 로는 못 보던 실제 사용자 화면을 AI 가 직접 검증.

### Run 2026-06-04-005 — Playwright MCP → relay → 실제 Windows Chrome (in-loop)
- Date: 2026-06-04
- Environment: **Windows-browser** (via Playwright MCP)
- Runner: AI (claude)
- Bridge: relay (무권한 userspace) @ http://172.28.64.1:9223
- Evidence: MCP JSON-RPC stdout — serverInfo `Playwright`, browser_navigate 결과 "Page URL: https://localhost:18080/ · Page Title: DQA — Database Query Assistant"
- Result Summary: `bin/playwright-mcp.sh` 가 relay endpoint 자동 해석 → `npx @playwright/mcp@latest --cdp-endpoint=…` 기동 → initialize + `browser_navigate` 가 실제 Windows Chrome 을 DQA 로 이동. MCP 도구가 실 브라우저 구동 확인 (TEST-0006).
- Pass/Fail: PASS
- Notes: wrapper 조립/endpoint 해석은 stub-npx 로 별도 검증. MCP = 대화형 in-loop, win-browser.py = 게이트 증거 — 같은 브리지 공존.

## 4. Untested Areas
- 인증 성공 후 흐름(대화 생성/쿼리 실행) — 유효 자격증명 필요, 본 검증 범위 외(비파괴 원칙).
- Edge(msedge) 경로, mirrored networking 모드(B), 영속 portproxy(A) — 본 cycle 은 무권한 relay(옵션 0)만 실 검증. A/B 는 코드/문서상 지원하나 미실측.
- 다른 머신/계정에서의 Windows python 자동 탐지 견고성(여러 설치본/스토어 stub 혼재 시).
