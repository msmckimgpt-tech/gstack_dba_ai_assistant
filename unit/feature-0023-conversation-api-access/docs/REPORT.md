---
doc_type: REPORT
feature_id: feature-0023-conversation-api-access
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
외부 AI 프로그래매틱 접근용 **Bearer API 토큰 인증** + **Conversation API MCP 서버**를
추가했다. 세션 쿠키(사람용)와 별개로 저권한 서비스 계정에 귀속된 장수명 토큰으로
`/api/ask` 등 `conversation.*` 엔드포인트를 호출할 수 있고, scope allowlist
(`conversation.,product.access.`)가 관리/콘솔 엔드포인트를 원천 차단한다. 토큰을 보유한
MCP 서버가 대화를 4개 tool(ask/new_conversation/list_conversations/get_history)로 노출한다.

## 2. Progress
- Planned: 라이브 e2e 검증(토큰 발급→ask 왕복), STATUS.md 갱신.
- In Progress: 컨테이너 make test, verify-completion, 배포.
- Done: Phase 1(스키마·Bearer 인증·scope 강제·발급 CLI·단위 로직) + Phase 2(MCP 서버·런처·등록) 코드.

## 3. Recent Changes
- WebApiTokens 스키마 + fast/slow path 등록 (해시 저장, scope, 만료, revoke, LastUsedAt).
- `_get_authenticated_account` Bearer fallback + `_get_account_by_api_token`(fail-closed).
- `_account_permissions` scope 교집합(단일 choke-point) — 관리 네임스페이스 effective=False.
- `bin/api-token-issue.sh` 발급/폐기/조회 CLI + WebAuditEvents 기록.
- MCP 서버 `conversation_mcp_server.py` + `bin/conversation-mcp.sh`(gated) + `.mcp.json` 등록.
- 총 변경 횟수: 1 (CHG-20260722-0001)

## 4. Open Issues
- 라이브 e2e(실토큰 ask 왕복)는 배포 후 수행.

## 5. Test Status
- 자동 테스트: host pure-logic 24 assertion PASS(scope/파싱/인증 게이트). 정식 pytest
  `test_api_token_auth.py` 는 컨테이너 make test 에서 실행(conftest 가 app import 필요).
- MCP smoke: tool 4종 등록 PASS, 런처 gated(비활성 no-op/누락 fail-loud) PASS.
- 미검증 항목: 라이브 토큰→/api/ask 왕복, 스코프-밖 admin 403 라이브.

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 배포 후 운영자가 저권한 서비스 계정 지정 + 토큰 발급(bin/api-token-issue.sh) 필요.
- 인증 신설(Critical) — Plan 승인 완료(2026-07-22). §18.8 적대적 보안 리뷰 반영.

## 8. Suggested Improvements
- 셀프서비스 토큰 발급 웹 엔드포인트(scope 제한) 후속 검토.
- 토큰 사용량 per-token rate limit(현재는 서비스 계정 quota 상속).
