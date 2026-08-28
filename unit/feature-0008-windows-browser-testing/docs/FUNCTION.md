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
- 외부 사이트 쿠키 임포트(사용자 개인 브라우저 프로필 재사용) — 격리 프로필 원칙 유지.

> **범위 전환 (2026-08-28, 사용자 결정)**: 종전 §4 는 "인증된 세션 자동화" 전체를 범위 밖으로
> 두고 "전용 격리 프로필 사용이 원칙" 이라 적었다. 그런데 그 원칙 때문에 **격리 프로필에
> 세션이 없어** PB-0008 이 도달할 수 있는 화면이 로그인 폼뿐이었고, 웹/UI cycle 두 건이 연속
> 으로 화면 실측을 미수행 처리했다(2026-08-27~28) — 완료 게이트가 형식만 남는다. 그래서
> **자기 프로필 안에서의 세션 발급은 In Scope 로 전환**한다(§3 `session-*`). 여전히 범위 밖인
> 것은 *사용자 개인 브라우저의 쿠키를 가져오는 것* 이며, 격리 원칙 자체는 유지된다.
- check #13 의 strict(MUST) 격상 — 후속 cycle (v1 은 WARN-only).

## 5. Inputs
- 검증 대상 URL (기본 `http://localhost:18080`, docker 웹 서비스).
- 시나리오 JSON (steps: goto/click/type/eval/assert/screenshot ...).
- 환경변수: `WIN_BROWSER_CDP_PORT`/`RELAY_PORT`/`PROFILE`/`CHROME`/`ALLOW_ORIGINS`/`SHOT_DIR`/`CDP_ENDPOINT`/`TIMEOUT_MS`/**`ORIGIN`**/**`SESSION_ENV`**.
- 검증용 자격증명: `.env` 의 `WEB_BOOTSTRAP_ADMIN_USERNAME`/`WEB_BOOTSTRAP_ADMIN_PASSWORD` (기존 키 재사용 — 새 비밀 추가 0, 사용자 결정 2026-08-28).

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

### 검증용 로그인 세션 (REQ-20260828-verify-session)

전용 격리 프로필에 로그인 세션을 발급해, PB-0008 이 **로그인 폼 너머**를 검증할 수 있게 한다.

- AC-20260828T103000-verify-session-1: `session-login` 은 `.env` 의 `WEB_BOOTSTRAP_ADMIN_*` 로 **실제 로그인 폼**
  (`#loginUsername`/`#loginPassword`/`#loginForm`)을 채워 세션을 만든다. 성공 시
  `{"ok":true,"authenticated":true,"username":"bootstrap_admin","role":"admin"}`.
- AC-20260828T103000-verify-session-2: **멱등** — 이미 인증돼 있으면 폼을 건드리기 전에 `"already": true` 로 반환한다.
  매 검증 앞단에서 무조건 호출해도 실패 카운터를 흔들지 않는다.
- AC-20260828T103000-verify-session-3: **인증 실패에 재시도하지 않는다.** 대기 루프는 성공/실패 확정만 기다리며 그 안에서
  폼을 다시 채우거나 제출하지 않는다. 실패 시 서버 문구(`#loginError`)를 `server_message` 로
  올리고 종료한다 — 연속 실패는 계정 잠금(`LOGIN_MAX_FAILED_ATTEMPTS`)과 IP throttle 을 부른다.
- AC-20260828T103000-verify-session-4: **비밀번호는 보고·argv 어디에도 실리지 않는다.** `pw` 는 자격증명 획득과
  `page.fill("#loginPassword", …)` **1곳** 밖에서 쓰이지 않는다(부분식·f-string 포함 금지).
- AC-20260828T103000-verify-session-5: 세션 동작은 **자기 탭**에서만 한다(§16.6 세션 격리) — `ctx.new_page()` 로 열고
  끝나면 닫는다. 쿠키는 프로필에 남아 이후 검증이 이어받는다.
- AC-20260828T103000-verify-session-6: `session-check` 는 상태만 보고하고(`--require-auth` 시 미인증이면 exit 1),
  `session-logout` 은 세션을 해제한다(해제되지 않았으면 `logout_ineffective` + exit 1).
  **쿠키 경계는 host** 이므로(포트·스킴 무관) 검증 시나리오와 같은 host 를 써야 한다.
- AC-20260828T103000-verify-session-7 (적대 리뷰 [P1]): 비밀번호는 **loopback + `.env` 의 `WEB_ALLOWED_HOSTS`/
  `WEB_PUBLIC_HOST`** 로만 전송된다. 그 밖의 origin 은 페이지를 열기도 전에
  `origin_not_allowed` 로 거부되며, 넓히려면 `--allow-remote-origin` 을 사람이 명시해야 한다.
  근거: `--origin` 은 검사 없이 `page.fill("#loginPassword", …)` 로 이어지고 브라우저는
  `--ignore-certificate-errors` 로 뜬다 — 이 저장소의 AI 는 대화·MCP 로 신뢰할 수 없는 입력을
  읽으므로, 주입된 지시 하나로 관리자 자격증명이 공격자 호스트에 그대로 타이핑될 수 있었다.
- AC-20260828T103000-verify-session-8: `DEBUG` 에 playwright protocol 추적이 켜져 있으면(`pw:protocol`) 진행을
  **거부**한다 — `Input.insertText` 로 평문 비밀번호가 stderr 에 실린다.
- AC-20260828T103000-verify-session-9: 실패는 구분해서 보고한다 — `login_rejected`(서버가 거부) ·
  `login_no_response`(응답·오류표시 모두 없음) · `totp_required` · `origin_not_allowed` ·
  `env_file_missing`/`env_file_unreadable`/`password_not_set`. 특히 무응답을 "자격증명 확인"
  으로 안내하지 않는다 — 그 안내가 곧 no-retry 계약이 막으려던 재시도를 부른다.
- 잔여 위험(수용): 검증 프로필은 영속이라 Chrome 이 자격증명 상태를 남길 수 있다. 프로필은
  per-user `%LOCALAPPDATA%`(ACL 보호)이며 **자격증명과 같은 민감도로 취급**한다.
  `session-logout` 은 그 로그인 세션에서 발급된 AI 연결(`mat_`) 토큰도 함께 폐기한다.

- AC-20260828T220000-windows-browser-testing: 세션 명령(`session-login`·`session-check`)이
  **브라우저를 종료시키지 않는다** — `launch` → 세션 발급 → `goto` 가 한 흐름으로 이어진다.
  드라이버가 치우는 탭은 **자기가 만든 것뿐**이고, 그것이 마지막 탭이면 남긴다.
