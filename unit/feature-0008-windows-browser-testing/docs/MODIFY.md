---
doc_type: MODIFY
feature_id: feature-0008-windows-browser-testing
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260604-0001
- Date: 2026-06-04
- Related Requirement: REQ-0001, REQ-0002, REQ-0003 (FUNCTION.md §2)
- Summary: WSL→실제 Windows 브라우저 CDP 자동 구동 테스트 워크플로 신규 도입.
  드라이버(`bin/win-browser.py`: doctor/launch/down/goto/click/type/eval/text/screenshot/run),
  1회 브리지 setup(`bin/win-browser-setup.ps1` vEthernet 한정 relay + `bin/WIN-BROWSER-SETUP.md`),
  환경 분류(`unit/_template/docs/TEST.md`), 검증 절차(PB-0008), 완료 게이트
  (AGENTS.md §10.5/§15.4.1/§16.1/§16.2 + verify-completion check #13 WARN-only),
  CLAUDE.md skill routing 명확화. §18.8 검증 패널(security+qa) must-fix 반영.
- Files:
  - 신규: bin/win-browser.py, bin/win-browser-setup.ps1, bin/WIN-BROWSER-SETUP.md
  - 신규: playbooks/PB-0008-windows-browser-verification.md
  - 신규: unit/feature-0008-windows-browser-testing/** (docs, src/scenario.example.json, tests/test_scenario_engine.py)
  - 신규: wiki/Features/feature-0008-windows-browser-testing.md
  - 수정: AGENTS.md(§10.5, §15.4.1, §16.1, §16.2), unit/_template/docs/TEST.md, bin/verify-completion.sh(check #13), playbooks/README.md, CLAUDE.md, docs/STATUS.md, docs/DECISIONS.md
- Impact: 웹/UI 변경의 완료 검증 정본 환경이 실제 Windows 브라우저로 이동. 기존
  feature 동작/스키마/런타임 변경 없음(테스트·거버넌스 계층). check #13 은 WARN-only 라
  기존 cycle 을 block 하지 않음.
- Rollback Notes: 비파괴·가역. 되돌리려면 본 cycle 의 신규 파일 삭제 + AGENTS.md/TEST.md/
  verify-completion.sh/CLAUDE.md/STATUS.md/DECISIONS.md 의 해당 변경 revert. 런타임 의존
  없음(브리지 setup 미적용 시에도 기존 워크플로 그대로 동작, check #13 은 WARN 만).

## CHG-20260604-0002
- Date: 2026-06-04
- Related Requirement: REQ-0002 (AI 자동 구동), 실 환경 검증 완수 (사용자 후속 요청)
- Summary: **무권한(admin 불요) auto-relay 내장 + 실제 Windows 브라우저 첫 e2e 검증 완수.**
  지난 cycle 의 교훈(relay=admin netsh, mirrored=WSL재시작 → 둘 다 마찰)을 해소: `launch` 가
  Windows python 으로 userspace TCP relay(vEthernet IP:9223 → 127.0.0.1:9222)를 자동 기동
  하여 admin·WSL재시작 없이 브리지를 성립한다. self-signed 로컬 dev 대응 `--ignore-certificate-errors`
  (기본 on). 실제 Windows Chrome 148 로 DQA 웹 UI 로드 + 로그인 기능 e2e(인증 실패 경로) 검증
  완료 (TEST.md §3 Run 003/004, artifacts 스크린샷).
- Files:
  - 수정: `bin/win-browser.py` — find_win_python/relay_start/relay_stop/wait_for_bridge 추가, `launch` 무권한 relay 자동기동 + `--ignore-certificate-errors` + 단일 emit(_navigate_silent), `down` relay 동반 종료, `relay-start`/`relay-stop` 서브커맨드, doctor win_python 진단.
  - 수정: `bin/WIN-BROWSER-SETUP.md`(옵션 0 무권한 relay 권장), `playbooks/PB-0008-…`(브리지 자동), feature docs(TEST/REPORT/TASK).
- Impact: 브리지 진입장벽 제거(admin 불요). 보안 posture 동일 — relay 는 vEthernet IP 에만
  바인딩(LAN 노출 없음, F1 정합). 기존 런타임/스키마/RBAC 무변경.
- Rollback Notes: 비파괴·가역. relay 자동기동은 `WIN_BROWSER_NO_RELAY=1` 로 비활성, ignore-cert 는
  `WIN_BROWSER_IGNORE_CERT=0` 로 비활성. 되돌리려면 본 CHG 의 win-browser.py 변경 revert.

## CHG-20260604-0003
- Date: 2026-06-04
- Related Requirement: 사용자 후속 요청 — "구현 환경에 적합한 구성요소(Playwright MCP / Browser Agent for Claude) 검토 후 적합하면 적용".
- Summary: **Playwright MCP(`@playwright/mcp`)를 무권한 relay 에 attach 해 Claude Code(VSCode/CLI)에
  native in-loop 브라우저 도구 제공.** 검토 결과 Playwright MCP 채택(CDP attach 지원, a11y 스냅샷
  토큰 효율, node/npx) / **Claude for Chrome 미채택**(Chrome 확장·MCP/API 부재·수동 UI → 프로그래매틱
  dev 워크플로 부적합). MCP 서버 → relay → 실제 Windows Chrome e2e 스모크 PASS (initialize +
  browser_navigate → Page Title "DQA — Database Query Assistant").
- Files:
  - 신규: `bin/playwright-mcp.sh`(relay endpoint 자동 해석 + npx @playwright/mcp exec, 옵션 autolaunch),
    `repo/.mcp.json`(project-scope playwright 서버; CLAUDE_PROJECT_DIR 기반 경로; 첫 사용 시 승인).
  - 수정: `bin/WIN-BROWSER-SETUP.md`(Playwright MCP 섹션 + Claude for Chrome 미채택 사유), `CLAUDE.md`
    (skill routing), `playbooks/PB-0008`(대화형 옵션), feature docs.
- Impact: 대화형 UI 탐색이 모델 루프에서 first-class(MCP 도구)로 가능 — win-browser.py(브리지/시나리오/게이트)와
  역할 분담·공존. 보안 posture 동일(같은 vEthernet 한정 relay 에 attach, RBAC/스키마/시크릿 무변경).
  MCP 서버는 project `.mcp.json` 라 첫 사용 시 사용자 승인 필요(자동 활성 아님).
- Rollback Notes: 비파괴. `.mcp.json` 삭제(또는 `claude mcp remove playwright`) + `bin/playwright-mcp.sh`
  제거로 원복. win-browser.py 등 기존 경로 무영향.

## CHG-20260828T103000-verify-session — PB-0008 검증용 로그인 세션 3 서브커맨드

- `bin/win-browser.py`: `session-check`/`session-login`/`session-logout` 추가.
  `_drive_new_page`(자기 탭에서만 동작 후 닫음) · `_read_env_keys`(요청 키만 파싱) ·
  `_session_credentials`(문제 코드 반환) · `_SESSION_STATE_JS`(`/api/session` → `user.username`
  · `user.role.key`). 환경변수 `WIN_BROWSER_ORIGIN` / `WIN_BROWSER_SESSION_ENV` 문서화.
- `playbooks/PB-0008-windows-browser-verification.md`: Prerequisites 에 세션 항목,
  Step 3.5 신설(멱등·무재시도·host 쿠키 경계·origin 허용목록·logout blast-radius),
  Validation 체크 1줄 추가, 폐기된 `:18080` 진입점 정정.
- `Makefile`: pytest 경로에 `unit/feature-0008-windows-browser-testing/tests` 편입.
- `unit/feature-0008-windows-browser-testing/tests/test_verify_session.py` (신규 40건):
  **가짜 page 더블로 명령을 실제 구동**해 관측 가능한 사실만 단언한다 — 제출 횟수·입력 대상·
  출력 스트림·exit code. 소스 문자열 검사는 쓰지 않는다(아래 리뷰 조치 참조).
- **적대 리뷰(subagent) 조치 — 판정 BLOCK → 전건 수정**:
  - [P1] `--origin` 무검증: 검사 없이 `page.fill("#loginPassword", pw)` 로 이어지고 브라우저는
    `--ignore-certificate-errors` 로 뜬다 → 주입된 지시 하나로 관리자 자격증명이 공격자 호스트에
    타이핑될 수 있었다. `_session_origin_denied` fail-closed 게이트(loopback + `.env` 선언 host)
    + `--allow-remote-origin` 명시 escape.
  - [P1] 테스트가 `ast`/문자열 검사라 계약을 **하나도** 잠그지 못함(리뷰가 뮤턴트 5종을 **동시에**
    적용하고도 26건 전건 통과시킴) → 가짜 page 더블 기반 동작 검증으로 전면 교체.
  - [P2] `already` 경로가 차단 플래그 누락(99% 호출이 그 경로) → 플래그 동반.
  - [P2] `is_locked` 가 구조적 vacuous(`/api/session` 의 `user` 는 인증 시에만 채워짐) → 제거.
  - [P2] `login_failed` 가 서버 거부와 무응답을 뭉침 → `login_rejected` / `login_no_response` 분리
    (무응답에 "자격증명 확인" 안내를 붙이면 그 안내가 곧 재시도를 부른다).
  - [P2] `session-check` 가 프로브 실패와 미인증을 뭉치고 exit 0 → `session_probe_failed` +
    `--require-auth`(exit code 게이트).
  - [P2] `session-logout` 이 미해제여도 `ok:true` → `logout_ineffective` + exit 1. AI 연결(`mat_`)
    토큰까지 폐기되는 blast-radius 를 플레이북에 명시.
  - [P2] `.env` 인라인 주석 미절단(잘못된 비밀번호 → 매 호출 실패 1회 기록) → 인용 없는 값만 ` #`
    절단(인용 값은 보존). 읽기 실패를 `password_not_set` 으로 오진 → `env_file_unreadable` 신설.
  - [P2] `_connect` 가 만든 빈 탭 누수 → 회수. `DEBUG=pw:protocol` 시 평문 유출 → fail-closed.
  - [P2] 플레이북 stale 진입점(`:18080` 폐기됨) · "origin=쿠키 경계"(실제는 **host**) → 정정.
- Verification: **신규 40건 PASS** · **뮤테이션 8종 전건 KILL** — 적대 리뷰가 초안 스위트를
  무력화한 5종(`eprint(pw)` / 대기루프 밖 재제출 / exit 0 고정 / 멱등 분기 사망 /
  `HANDLERS["session-logout"]`→login 오배선) **전부 포함** + 신규 가드 3종(origin·DEBUG·logout ok).
- 라이브 실증: `logout → check(--require-auth → exit 1) → login → check(exit 0)` 왕복 ·
  `--origin https://attacker.example` 거부(exit 1) · 멱등 재호출(`already:true`) ·
  **직전 cycle 이 미수행으로 남긴 로그인 후 스크롤 실측을 이 세션으로 완료**.
- Timestamp: 2026-08-28T11:20:00+09:00
