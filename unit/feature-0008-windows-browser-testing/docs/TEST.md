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
- 제외: 실제 Windows 브라우저로의 CDP wire end-to-end — 1회 브리지 setup(관리자
  portproxy 또는 mirrored)이 구성된 환경에서만 가능 (§4 참조).

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

### TEST-0004 — check #13 web 게이팅 (실 Windows 브라우저)
- Purpose: 웹/UI 변경 시 TEST.md §3 Windows-browser Run 누락 경고, 비웹 변경은 PASS, 템플릿 메뉴 라인 false-PASS 방지.
- Preconditions: 브리지 setup 완료 + 웹앱 기동.
- Steps: PB-0008 절차로 `launch` → `run --scenario` → 스크린샷 → §3 기록.
- Expected Result: 실제 Windows 브라우저에서 시나리오 실행, `bridge_endpoint`=relay|mirrored, 스크린샷 생성. (후속 — §4)

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

<!-- 후속: 브리지 1회 setup 후 TEST-0004 의 Windows-browser Run 을 여기에 추가. -->

## 4. Untested Areas
- **실제 Windows 브라우저 CDP wire end-to-end (TEST-0004)**: host 에 Linux chromium 공유
  라이브러리가 없어 로컬 CDP 타겟을 띄울 수 없었고, NAT relay 는 관리자 권한(netsh
  portproxy)이 필요해 본 cycle 에서 미수행. 커버 계획: 사용자가 `bin/WIN-BROWSER-SETUP.md`
  의 옵션 A(관리자 1회) 또는 B(mirrored)로 브리지를 구성한 뒤 PB-0008 절차로 실 검증 →
  본 feature 의 첫 Windows-browser Run 으로 §3 기록. connect_over_cdp/launch flag 는
  spike + 단위 테스트로 부분 검증됨.
