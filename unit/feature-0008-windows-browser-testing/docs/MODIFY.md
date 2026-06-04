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
