---
doc_type: FEATURE_DECISIONS
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-001
- Status:
- Date:
- Context:
- Decision:
- Consequences:
- Supersedes:
- Superseded By:

## ADR-ME-0002 (대화 바인딩 fail-closed)
- Status: Accepted
- Date: 2026-07-22
- Context: 2026-07-22 "편집·재요청 답변 타 대화 누출" 신고 진단 중 발견(신고 자체는 오진 — 실누출
  없음 확정). `_run_agent_core` 는 `cid = conversation_id or _get_conversation_id(conv_file)` 로,
  conversation_id 가 falsy 면 프로세스 전역 env(`AGENT_CONVERSATION_ID`)·호스트 공유 파일
  (`/shared/conversation_id`)로 폴백. 정상 경로(worker enqueue 가드·web 핸들러)는 항상 명시하지만,
  회귀·신규 caller 가 account_id 를 넘기며 conversation_id 를 비우면 동시 요청·세션 간 대화가 공유
  상태로 섞이는 cross-conversation 누출 표면이 된다.
- Decision: 웹/ask 경로(`account_id is not None`)에서 conversation_id 가 falsy 면 전역/공유 폴백을
  쓰지 않고 **fail-closed**(LLM/DB 작업 이전 조기 return + error 로그). CLI/console/eval
  (`account_id=None`)은 파일 폴백 유지.
- Alternatives: (a) 폴백 유지+로그만 — 누출 표면 존치, 기각. (b) 전역 env·공유 파일 제거 — CLI 정당
  사용까지 깨짐, over-reach. account_id 게이트가 최소 침습·정확.
- Consequences: 정상 경로 무영향(항상 conversation_id 명시 — never-fires 가드). 회귀 시 조용한 누출
  대신 명시적 실패. INV-6. 검증=test_conv_bind_failclosed.py(4건).
- Related: 브랜치 체인 산란 방지(footgun B)는 병렬 세션 PR #874/#875 'branch-chain-race'가 별도 봉인
  (runtime_backend `branch_run_active`/`branch_chain_*`) — 본 ADR 범위 밖(중복 회피).
