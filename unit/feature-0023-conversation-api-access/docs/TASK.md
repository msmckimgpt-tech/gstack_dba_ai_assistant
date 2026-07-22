---
doc_type: TASK
feature_id: feature-0023-conversation-api-access
status: active
edit_policy: append
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-22

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py` — `_ensure_web_api_tokens_schema` 신규
  - `unit/feature-0003-agent-web-ui/src/web_context.py` — `_get_authenticated_account` Bearer fallback + 토큰 helper
  - `unit/feature-0003-agent-web-ui/src/app.py` — `_account_has_permission` 토큰 scope 교집합 게이트
  - `bin/api-token-issue.sh` (+ python helper) — 발급/폐기 CLI
  - `bin/conversation-mcp.sh` + MCP 서버 python 모듈 — 대화 tool 래퍼
  - `unit/feature-0023-conversation-api-access/src/*` — MCP 서버 코드 거주
  - 테스트: `unit/feature-0003-agent-web-ui/tests/` (토큰 인증) + feature-0023 tests
- **접근 방법:** 세션 쿠키 인증 진입점에 Bearer fallback 만 얹어 blast-radius 최소화.
  토큰은 해시 저장·scope 한정(`conversation.*`)·저권한 서비스 계정 귀속으로 심층방어.
  발급은 콘솔 밖 CLI. MCP 서버는 토큰을 env 로 받아 REST 를 tool 로 래핑. additive·fail-closed.
- **위험도:** Critical (인증/인가 신설 — SECURITY §3)

<!-- PLAN-APPROVED by user on 2026-07-22 (entry persona arg-given dispatch, Phase 1+2 전체 승인) -->

## 3. Task Queue
- [x] TASK-0001: 설계 확정 + feature 문서(FUNCTION/ANCHOR/TASK) 기입
- [x] TASK-0002: `WebApiTokens` 스키마 (`_ensure_web_api_tokens_schema` 멱등, fast/slow path)
- [x] TASK-0003: Bearer 토큰 인증 경로 (`_get_account_by_api_token` + 쿠키 fallback + `LastUsedAt`)
- [x] TASK-0004: 스코프 강제 (`_account_permissions` allowlist 교집합 + **절대 denylist**)
- [x] TASK-0005: 발급/폐기 CLI (`bin/api-token-issue.sh`) + audit + scope 검증 + privileged 경고
- [x] TASK-0006: 단위 테스트 (컨테이너 17 passed — 파싱/scope/denylist/fail-closed/인증)
- [x] TASK-0007: §18.8 적대적 보안 리뷰 (HIGH-1/HIGH-2 적발→수정, REV-20260722-0002)
- [x] TASK-0008: MCP 서버 (`conversation_mcp_server.py` + `bin/conversation-mcp.sh` gated, tool 4종)
- [x] TASK-0009: MCP smoke(tool 등록·gated) + `.mcp.json` 등록 + example env + gitignore
- [x] TASK-0010: verify-completion + STATUS.md + commit/push + cycle-final + 배포 + 라이브 e2e
  (배포 66a48870 soak PASS · 라이브 e2e: 토큰→/api/ask 200 · admin 엔드포인트 403 · 무토큰 401)
- [x] TASK-0011: 발급 CLI 서비스명 hotfix (web→web-a/web-b 자동감지, CHG-20260722-0002)

## 4. In Progress
- TASK-0010 (verify-completion → 배포)

## 5. Blocked
- 없음

## 6. Done
- TASK-0001~0009 (Phase 1 인증·CLI·테스트·보안리뷰 + Phase 2 MCP).

## 7. Next Action
- verify-completion → commit → cycle-final → 배포 → 라이브 e2e(토큰 발급→/api/ask 왕복).

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (AGENTS.md §8.2 단계 1)
- [ ] 전체/통합 테스트(integration test)가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다 (§18.8 적대적 보안 리뷰 포함)
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
