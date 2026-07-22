---
doc_type: ANCHOR
feature_id: feature-0023-conversation-api-access
created_at: 2026-07-22T02:41:07Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0023 conversation-api-access

## §1. 외부 관점 요약
이 제품은 사람이 브라우저로 로그인해 쓰는 사내 AI assistant다. 그런데 여기 와서
"외부 AI(에이전트/자동화)가 이 assistant 를 프로그램으로 호출하게 하자"는 요구가
생겼다. 처음 코드를 여는 사람은 "인증이 100% 세션 쿠키뿐인데 봇이 어떻게 붙지?"라고
의문을 가진다. 답: 쿠키 로그인은 사람용(브루트포스 잠금·TOTP·세션 만료)이라 봇에
부적합하므로, 대화 API(`/api/ask` 등) 전용으로 **Bearer API 토큰** 인증 경로를 별도로
추가한다. 관리 콘솔은 이 경로에서 원천 차단(스코프 `conversation.*`)한다.

## §2. 대안 분기
- **Alt-A: 기존 로그인 쿠키를 봇이 재사용.** 페르소나: "지금 당장 되기만 하면 되는"
  빠른 통합 팀. 안 고른 이유: 코드 변경 0이지만 쿠키 수명·세션 만료 관리 부담,
  로그인 시도 제한이 사람용이라 봇 재시도에 취약, TOTP 켜지면 불가, 개별 통합만
  골라 revoke 불가, 감사에서 봇/사람 구분 약함. 프로그래매틱 용도의 안전 경계 부재.
- **Alt-B: 관리 콘솔에 토큰 관리 UI 신설.** 페르소나: 셀프서비스 발급을 원하는 운영
  팀. 안 고른 이유: 사용자가 명시적으로 "관리 콘솔 제외"를 요구. 발급을 CLI
  부트스트랩 스크립트로 두어 콘솔 표면을 늘리지 않는다(스코프 최소화).
- **Alt-C: 별도 API gateway/BFF 신설.** 페르소나: 마이크로서비스 성숙 조직. 안 고른
  이유: 대화 엔드포인트가 이미 REST(`/api/ask`)로 존재하고 RBAC/quota/audit 가
  갖춰져 있어, 인증 진입점 1곳에 Bearer fallback 만 얹는 게 blast-radius 최소.

## §3. 가정된 사용 시나리오
6개월 후, 사내 다른 팀이 자동화 워크플로(예: n8n, 혹은 Claude Code MCP 클라이언트)에서
"이 DB 질문을 assistant 에게 물어보고 답을 받아 후속 처리"를 하려 한다. 그들은 관리자에게
저권한 서비스 계정 + API 토큰 1개를 발급받아 MCP 서버 env 에 넣는다. 그러면 자기
AI 클라이언트에서 `ask("...질문...")` tool 을 호출하면 assistant 답변이 돌아온다.
관리 콘솔·타 계정 대화·datasource 관리에는 이 토큰으로 절대 접근할 수 없다(스코프 차단).

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님)
