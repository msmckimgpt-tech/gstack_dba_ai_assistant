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
