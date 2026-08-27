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
- [x] TASK-0011 Playwright MCP / Claude for Chrome 검토 (조사 2건) — Playwright MCP 채택, Claude for Chrome 미채택
- [x] TASK-0012 Playwright MCP 적용 (bin/playwright-mcp.sh + .mcp.json) + MCP→relay→Chrome e2e 스모크 PASS + 문서

## 4. In Progress
- 없음

## 5. Blocked
- 없음

## 6. Done
- 드라이버 + 브리지 setup + 워크플로 게이트 + 검증 + 패널 반영 + 문서

## 7. Next Action
- verify-completion --pre-commit PASS → commit → PR 병합. 후속: 인증 성공 흐름·Edge·A/B 모드 실측, check #13 strict 격상, (선택) Playwright CLI 모드 토큰 비교.

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

## TASK-20260828T103000-verify-session — PB-0008 검증용 로그인 세션

**배경**: 드라이버가 전용 격리 프로필로 브라우저를 띄우는데 그 프로필에 세션이 없어, PB-0008 이
도달할 수 있는 화면이 **로그인 폼뿐**이었다. 웹/UI cycle 두 건(feature-0043 브리지 스크롤,
그 증적 cycle)이 연속으로 "로그인 세션 부재" 를 사유로 화면 실측을 미수행 처리했다 —
완료 게이트 check #13 이 형식만 남는 상태.

**위험도**: Minor (§12.3) — 기존 자격증명 재사용, 계정·권한·인증 코드 변경 0, 검증 도구 한정.

### 2.1 Implementation Plan
- `bin/win-browser.py`: `session-check` / `session-login` / `session-logout` 3 서브커맨드 +
  `_drive_new_page`(자기 탭 전용) + `_read_env_keys`/`_session_credentials`(비밀 미출력).
- `playbooks/PB-0008-…md`: Prerequisites + Step 3.5 + Validation 체크 추가.
- `Makefile`: `feature-0008` tests 를 pytest 경로에 편입(그 전까지 CI 미실행이라 새 계약이
  회귀 감지 대상이 아니었다).
- 완료 판정: 라이브에서 `session-login` → `session-check` 가
  `authenticated:true, username:bootstrap_admin` 이고, 그 세션으로 직전 cycle 이 남긴
  **미수행 항목(로그인 후 스크롤 실측)을 실제로 닫는다**.

### 7. Completion Checklist
- [x] AC 6건 구현
- [x] 자동 테스트 통과 (신규 14건 + 뮤테이션 5종 KILL)
- [x] 라이브 실증 — 세션 발급·멱등 재호출·로그인 후 화면 실측
- [x] FUNCTION.md §4 범위 전환 명시
- [x] MODIFY.md / REVIEW.md / REPORT.md / TEST.md 기록
- [x] PB-0008 플레이북 갱신
- [x] BLOCKED 없음

## 9. Requested Scope (요청 범위) — TASK-20260828T103000-verify-session

사용자 요청: "검증용 로그인 세션을 이어서 진행해주세요" (2026-08-28)

- [x] 검증용 로그인 세션 확보 — 산출물: `win-browser.py session-login` (라이브 발급·멱등 확인)
- [x] 세션 상태 확인 수단 — 산출물: `session-check` (`--require-auth` exit code 게이트)
- [x] 세션 해제 수단 — 산출물: `session-logout` (미해제 시 `logout_ineffective` + exit 1)
- [x] 계정은 `bootstrap_admin` 재사용(사용자 결정) — 산출물: `.env` 기존 키 사용, 새 비밀·계정 0
- [x] PB-0008 절차에 편입 — 산출물: 플레이북 Prerequisites · Step 3.5 · Validation
- [x] win-browser host 오탐 보정(사용자가 함께 처리 선택) — 산출물: 병렬 세션이 main 에 선반영,
      중복 구현 없이 `doctor ok:true` 실측으로 확인
- [x] (부수) 직전 cycle 이 세션 부재로 미수행 처리한 로그인 후 스크롤 실측 — 산출물:
      feature-0003 `test-runs.d/REV-20260827T160500-…md` §6 (scrollTop 20/20 불변)
