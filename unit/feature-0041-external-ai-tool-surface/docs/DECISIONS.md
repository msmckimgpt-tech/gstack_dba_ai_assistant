---
doc_type: FEATURE_DECISIONS
feature_id: feature-0041-external-ai-tool-surface
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

## ADR-002 — AC-7 대화 적재를 구현한다 (답변 본문 보존)
- Status: Accepted
- Date: 2026-08-14
- Context: AC-7(원 질문·최종 답변의 서비스 측 적재 + 저장 시점 datamark)이 `[x]` 로 표기돼
  있었으나 실측 결과 미구현이었다(CHG-20260814-0024). `submit_answer` 는 상태만 갱신하고
  답변 본문을 저장하지 않아, 2026-08-12 사용자 요구("외부 AI 세션의 대화 기록 또한 우리 쪽에
  남겨야 합니다")의 답변 축이 비어 있었다. 이미 제출된 2건은 소급 복구 불가.
- Decision: **구현한다 — 별도 cycle** (사용자 결정 2026-08-14). 현재 수준(질문·도구 이력·
  바이트 수)으로 요구를 축소하지 않는다.
- Consequences: 저장 대상(전용 컬럼 vs `messages` 적재)·datamark 시점·기존 task 소급 처리를
  설계 단계에서 정해야 한다. 외부 입력 본문을 영속화하므로 §14 각인·인젝션 경계가 저장 경로
  까지 확장되며, 위험 등급은 Critical 로 취급한다(신규 저장면 + 신뢰 밖 콘텐츠).
- Supersedes: —
- Superseded By: —

## ADR-003 — `dbauth` 분석 task 에 정정 메모를 붙이지 않는다
- Status: Accepted
- Date: 2026-08-14
- Context: 08-14 스코프 결함 수정(`956ae5e1`)으로 같은 제품의 datasource 가 메모리 DB 쪽
  MySQL 에서 MSSQL 로 교체되어, 그 전에 제출된 `dbauth` 분석(`t_tLqaVEPlZ-DIxie6`)의 대상 DB 는
  현재 스코프에서 도달하지 않는다. "정정 메모를 붙일지" 가 열려 있었다.
- Decision: **그대로 둔다** (사용자 결정 2026-08-14). 붙일 실체가 없다는 점이 근거다 —
  ADR-002 의 발견대로 답변 본문이 우리 쪽에 저장돼 있지 않고, `WebAiTasks` 에 메모 컬럼도 없다.
  기록 삭제도 하지 않는다(그 시점의 사실이다).
- Consequences: 그 시점 이전 답변의 "대상 datasource 가 이후 교체됨" 맥락은 정본 문서
  (REPORT §3.5 · 본 ADR)에만 남는다. ADR-002 구현 시 적재 레코드에 datasource 식별자를
  포함하면 같은 부류의 혼동이 구조적으로 예방되므로, 그 설계에서 함께 고려한다.
- Supersedes: —
- Superseded By: —
