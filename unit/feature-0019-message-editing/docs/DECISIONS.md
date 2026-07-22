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

## ADR-ME-0002 (footgun A — 답변 대화 바인딩 fail-closed)
- Status: Accepted
- Date: 2026-07-22
- Context: 2026-07-22 "편집·재요청 답변 타 대화 누출" 신고 진단 중 발견. `_run_agent_core` 는
  `cid = conversation_id or _get_conversation_id(conv_file)` 로, conversation_id 가 falsy 면
  프로세스 전역 env(`AGENT_CONVERSATION_ID`)·호스트 공유 파일(`/shared/conversation_id`)로 폴백.
  정상 경로(worker enqueue 가드·web 핸들러)는 항상 conversation_id 를 명시하지만, 회귀·신규 caller 가
  account_id 를 넘기며 conversation_id 를 비우면 동시 요청·세션 간 대화가 공유 상태로 뒤섞이는
  cross-conversation 누출 표면이 된다. (이번 신고 자체는 이 경로가 원인 아님 — 실제 누출 없음 확정.)
- Decision: 웹/ask 경로(`account_id is not None`)에서 conversation_id 가 falsy 면 전역/공유 폴백을
  쓰지 않고 **fail-closed**(LLM/DB 작업 이전 조기 return + error 로그). CLI/console/eval
  (`account_id=None`)은 파일 폴백 유지(단일 사용자 로컬 컨텍스트 — 공유 상태 아님).
- Alternatives: (a) 폴백 유지+로그만 — 누출 표면 존치, 기각. (b) 전역 env·공유 파일 자체 제거 —
  CLI 정당 사용까지 깨짐, over-reach. account_id 게이트가 최소 침습·정확.
- Consequences: 정상 경로 무영향(항상 conversation_id 명시). 회귀 시 조용한 누출 대신 명시적 실패.
  INV-6. 검증=test_branch_hardening.py(웹 None/빈문자열 차단·전역폴백 미호출·CLI 미발동).

## ADR-ME-0003 (footgun B — run-scoped active-leaf 브랜치 체인 격리)
- Status: Accepted
- Date: 2026-07-22
- Context: 브랜치 대화(`has_branches=true`)의 한 run 이 user+assistant/tool 다수 메시지를 순차
  append 할 때, `_save_message`(core)·`save_memory_message`(display) 가 매 append 마다 DB
  `active_leaf` 를 재조회해 부모로 삼는다. 이 재조회들 사이에 다른 조작(브랜치 페이징 전환)이
  active_leaf 를 바꾸면, 실행 중 답변의 `parent_message_id` 체인이 타 브랜치 leaf 로 산란한다
  (라이브 conv 79da15cb 의 5188→5107·5190→5138 관측). 사용자-대면 질문→답변 경로엔 무영향이나
  브랜치 트리 내부 정합성 결함.
- Decision: run 시작 시 run-local last-leaf(신규 `shared/config` contextvar `_RUN_ACTIVE_LEAF_CORE`/
  `_RUN_ACTIVE_LEAF_DISPLAY`)를 초기화하고, run 첫 append 만 DB active_leaf 를 부모로 쓰고 이후는
  run-local 값을 부모로 체인(+ DB active_leaf 도 정본 전진). 생성 중 브랜치 전환이 DB active_leaf 를
  바꿔도 실행 중 답변 체인은 run 내부에서 일관. run 시작+`run_agent` finally 이중 리셋으로 worker
  스레드 재사용 bleed 방지.
- Alternatives: (a) set_active_leaf 를 monotonic-forward 로 — 정당한 브랜치 전환(역방향)까지 막음,
  기각. (b) 단일 UPDATE...RETURNING atomic advance — 재조회 사이 전환은 여전히 침투, 미해결.
  contextvar run-local 이 정확·최소.
- Consequences: 비분기 대화(`has_branches=false`)는 이 블록 미진입 → 완전 무영향(INV-1 보존).
  core/display 별도 id 공간 → 별도 contextvar(교차 오염 없음). INV-7. 검증=test_branch_hardening.py
  (run-local 격리·reset·비분기 무영향·명시 parent 우회·display·독립 6건).
