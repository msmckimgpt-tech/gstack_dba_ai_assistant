---
doc_type: TASK
feature_id: feature-0008-windows-browser-testing
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: review
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-06-04

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - `bin/win-browser.py` (신규 — CDP 드라이버)
  - `bin/win-browser-setup.ps1`, `bin/WIN-BROWSER-SETUP.md` (신규 — 1회 브리지 setup)
  - `unit/_template/docs/TEST.md` (환경 분류 도입)
  - `playbooks/PB-0008-windows-browser-verification.md`, `playbooks/README.md`
  - `AGENTS.md` (§10.5 / §15.4.1 / §16.1 / §16.2)
  - `bin/verify-completion.sh` (check #13, WARN-only)
  - `CLAUDE.md` (skill routing 명확화)
  - `unit/feature-0008-windows-browser-testing/**` (docs/src/tests)
  - `docs/STATUS.md`, `docs/DECISIONS.md`, `wiki/Features/feature-0008-windows-browser-testing.md`
- **접근 방법:** WSL 의 AI 가 Playwright `connect_over_cdp` 로 실제 Windows Chrome 을
  자동 구동. NAT 모드 한계(CDP=127.0.0.1 바인딩)는 vEthernet 한정 portproxy relay
  또는 mirrored networking 으로 해소. 워크플로 게이트(환경 분류 + 정책 + WARN-only
  검증)로 "웹/UI 완료 = Windows 브라우저 검증" 을 강제. 보안(CDP LAN 노출)은 검증
  패널 반영해 vEthernet 바인딩 + 구체 origin + per-user 프로필로 차단.
- **위험도:** Major (프로세스/거버넌스 + 신규 도구, 다파일, 비파괴·가역). §7.1 Plan-Review-Execute 적용.

<!-- 사용자 결정: arg-given dispatch 로 "AI 자동 구동 중심" 방향 승인 (2026-06-04). -->

## 3. Task Queue
- [x] TASK-0001 요구사항 정리 (CLI/WSL 제외, Windows 브라우저 AI 자동 구동)
- [x] TASK-0002 브리지 아키텍처 spike (CDP=127.0.0.1 확인, relay 필요 확정)
- [x] TASK-0003 win-browser.py 드라이버 구현 (doctor/launch/run/...)
- [x] TASK-0004 단위 테스트 + 실측 검증 (엔진 10/10, doctor, allow_origins/profile)
- [x] TASK-0005 워크플로/정책 (TEST.md 분류 · PB-0008 · AGENTS §15.4.1 · check #13)
- [x] TASK-0006 §18.8 검증 패널 (security + qa) 반영 (must-fix F1/F2/F4/F5 + check#13 false-pos/jinja)
- [x] TASK-0007 문서 정리 (feature docs · STATUS · DECISIONS ADR · wiki card)
- [x] TASK-0008 무권한 auto-relay 내장 (launch 자동 relay, admin 불요) + ignore-cert + 단일 emit
- [x] TASK-0009 실제 Windows 브라우저 e2e 검증 완수 (DQA 로드 + 로그인 기능, TEST.md §3 Run 003/004)
- [x] TASK-0010 SETUP.md/PB-0008 무권한 relay 반영 + feature docs 갱신

## 4. In Progress
- 없음

## 5. Blocked
- 없음

## 6. Done
- 드라이버 + 브리지 setup + 워크플로 게이트 + 검증 + 패널 반영 + 문서

## 7. Next Action
- verify-completion --pre-commit PASS → commit → PR 병합. 후속: Playwright MCP 통합 검토(사용자 요청), 인증 성공 흐름·Edge·A/B 모드 실측, check #13 strict 격상.

## 8. Completion Checklist
- [x] 모든 REQ의 AC가 구현되었다
- [x] 단위 테스트(unit test)가 통과한다 (10/10, AGENTS.md §8.2 단계 1)
- [x] 전체/통합 테스트(integration test): 실 CDP wire 는 브리지 1회 setup 후 — 사유·계획 TEST.md §4 기록 (host chromium 미설치로 로컬 CDP 타겟 불가)
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다
- [x] REVIEW.md에 판단 근거가 기록되었다 (검증 패널 2건)
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] TEST.md에 테스트 결과가 기록되었다
- [x] BLOCKED 항목이 없거나 사람에게 전달되었다
- [x] STATUS.md에 기능 상태가 갱신되었다
- [x] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
