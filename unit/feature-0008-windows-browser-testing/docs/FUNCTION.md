---
doc_type: FUNCTION
feature_id: feature-0008-windows-browser-testing
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
AI 작업자가 WSL 안에서 **실제 Windows 브라우저**(Chrome/Edge)를 CDP(Chrome DevTools
Protocol)로 자동 구동하여 웹/UI 를 검증하게 하는 테스트 워크플로 + 도구. 기존
검증이 CLI(curl) 또는 WSL 내부 headless 브라우저에 머물러 실제 사용자(Windows)
화면과 괴리가 발생하던 문제를 해소한다. 드라이버(`bin/win-browser.py`), 1회 브리지
setup(`bin/win-browser-setup.ps1` / mirrored), 검증 절차(PB-0008), 완료 게이트
(AGENTS.md §15.4.1 + TEST.md 환경 분류 + verify-completion check #13)로 구성된다.

## 2. Goal
- REQ-0001: 웹/UI 검증을 CLI·WSL 환경이 아닌 실제 Windows 브라우저에서 수행할 수 있게 한다.
- REQ-0002: 그 검증을 AI 가 자동 구동(조작·스크린샷)할 수 있게 한다 (사용자 요청: "AI 자동 구동 중심").
- REQ-0003: 웹/UI 변경의 "완료" 선언이 Windows 브라우저 검증 없이는 통과되지 않도록 워크플로에 게이트를 둔다.

## 3. In Scope
- WSL → 실제 Windows Chrome/Edge CDP 브리지 (mirrored / NAT+portproxy relay / **무권한 userspace relay** 자동 감지·기동).
- Playwright `connect_over_cdp` 기반 드라이버: doctor/launch/down/relay-start/relay-stop + goto/click/type/eval/text/screenshot + 시나리오 일괄 실행(`run`).
- **Playwright MCP 통합** (`bin/playwright-mcp.sh` + `.mcp.json`): 같은 relay 에 attach 해 Claude Code 에 native in-loop 브라우저 도구 제공 (대화형). Claude for Chrome 은 검토 후 미채택(MCP/API 부재).
- 환경 분류(CLI / WSL-headless / Windows-browser)와 완료 게이트(정책 + WARN-only 검증).
- 브리지 setup 스크립트 + 가이드 (무권한 auto-relay 기본, portproxy/mirrored 대안).

## 4. Out of Scope
- gstack `/browse`·feature-0004 headless 서비스 대체 (보조 수단으로 공존 — 빠른 탐색용).
- Windows 외 OS (macOS/Linux 데스크톱) 브라우저 구동.
- 인증된 세션 자동화(쿠키 임포트 등) — 전용 격리 프로필 사용이 원칙.
- check #13 의 strict(MUST) 격상 — 후속 cycle (v1 은 WARN-only).

## 5. Inputs
- 검증 대상 URL (기본 `http://localhost:18080`, docker 웹 서비스).
- 시나리오 JSON (steps: goto/click/type/eval/assert/screenshot ...).
- 환경변수: `WIN_BROWSER_CDP_PORT`/`RELAY_PORT`/`PROFILE`/`CHROME`/`ALLOW_ORIGINS`/`SHOT_DIR`/`CDP_ENDPOINT`/`TIMEOUT_MS`.

## 6. Outputs
- 1줄 JSON 결과 (stdout) — `ok`, endpoint, step 별 결과.
- 스크린샷 파일 (실제 Windows 브라우저 렌더링).
- TEST.md §3 Run 기록 (`Environment: Windows-browser`).

## 7. Main Flow
1. `doctor` — 브리지/chrome/playwright 진단, 미비 시 1회 setup 안내.
2. `launch` — 실제 Windows Chrome 기동(전용 프로필, idempotent), CDP up 대기.
3. 드라이버가 감지된 endpoint 로 `connect_over_cdp`.
4. goto/click/type/... 또는 `run --scenario` 로 조작 + 스크린샷.
5. 결과를 TEST.md §3 에 `Environment: Windows-browser` 로 기록, `down` 으로 정리.

## 8. Edge Cases
- 브리지 미구성(NAT relay 없음) → `launch` 가 `bridge_unreachable` + doctor 안내.
- playwright 미설치 → 명확한 에러 + `pip install playwright` 안내.
- Chrome 미설치/비표준 경로 → `WIN_BROWSER_CHROME` 안내.
- 사용자 일반 브라우저 보존 → `down` 은 전용 프로필 인스턴스만 종료.

## 9. Error Handling
- 모든 실패는 1줄 JSON `{"ok": false, "error": ...}` 로 표면화 (재시도/안내 포함).
- 게이트(check #13)는 v1 WARN-only — 절대 PR block 하지 않음.

## 10. Dependencies
### 내부 기능 의존성
- feature-0003-agent-web-ui (검증 대상 웹 UI)
- feature-0004-browser-automation (headless 보조)

### 외부 의존성
- playwright (python) — `connect_over_cdp` (브라우저 다운로드 불요)
- Windows Chrome/Edge, WSL2 (mirrored 또는 portproxy)

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-0001: `doctor` 가 브리지/chrome/playwright 상태를 정확히 진단하고 미비 시 setup 을 안내한다. (검증: 실측 — chrome·win_host·playwright 감지 확인)
- AC-0002: 시나리오 엔진이 goto/click/type/eval/assert/screenshot 을 정확히 dispatch 한다. (검증: 단위 테스트 10/10 PASS)
- AC-0003: 브리지는 CDP 를 LAN 에 노출하지 않는다 (relay = vEthernet 한정, origins 구체화). (검증: setup.ps1 vEthernet 바인딩 + allow_origins 비-와일드카드)
- AC-0004: 웹/UI 파일 변경 시 TEST.md §3 Windows-browser Run 누락을 check #13 이 경고한다 (비웹 cycle 은 PASS). (검증: 본 cycle 자체 PASS)

## 12. Observability
- `doctor` JSON (ok/issues/next_steps).
- `run` 결과 JSON (step 별 ok/error + screenshot 경로).
- 스크린샷 증거 (`shot_dir`).

## 13. Pre-approved Changes
- 없음
