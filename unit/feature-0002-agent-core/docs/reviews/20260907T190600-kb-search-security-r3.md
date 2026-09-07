# Security R3 — 구획 테스트 정합

- Source: subagent:kb_boundary_review
- Related TASK: TASK-20260907T181510-kb-external-search
- Input: §18.11 four-field bundle, no tools.

## 1. Blocking issues

없습니다. 제공된 변경은 기존 오탐 방지 보호를 약화하지 않습니다.

## 2. Cross-domain concerns

`test_injection_false_positive.py:225`의 AST 검사는 `claim_request` 안에서 다음 대응과 호출 개수를 고정합니다.

- `question` → `wrap_principal_request`
- `history` → `wrap_conversation_history`
- `kb_context` → `wrap_tool_output`

질문이나 이력을 `wrap_tool_output`으로 추가 포장하면 목록 비교가 실패합니다. 기존 호출 존재 검사도 유지하므로, 새 KB 포장만 허용하면서 보호 대상을 더 구체적으로 검사합니다.

## 3. Challenge to current spec

이 검사는 직접적인 `_guard` 호출의 정적 계약을 검증합니다. 최종 응답에 올바른 값이 실리는지는 기존 런타임 테스트가 담당해야 하며, 제공된 bundle에서는 해당 검증이 유지됐습니다. 실패 suite 재실행 결과만 완료 기록에 반영하면 됩니다.

## 4. Verdict

**PASS** — 제품 코드 변경 없이 새 KB 구획과 기존 질문·이력 구획을 구별하도록 테스트를 정합화했습니다.

**Human Approval Needed: no**

## Orchestrator follow-through

최종 assertion은 원본 코드의 질문 앞 session_canary도 포함한 f-string AST를 기대한다.
질문 포장을 바꾼 것이 아니라 테스트의 기대값을 원래 입력식과 정확히 맞췄다. 후속 suite19 PASS.
