---
doc_type: FUNCTION
feature_id: feature-0019-message-editing
task_id: TASK-20260713T-message-editing
status: in-progress
edit_policy: rewrite
source_of_truth: true
---

# Function — 메시지 편집 (Message Editing)

## 1. Summary
사용자가 대화(1:1 및 그룹/공유)에서 **자신이 보낸 메시지를 수정**할 수 있게 한다.
현재 이 앱의 대화 모델은 append-only(메시지 편집 없음, feature-0003 DESIGN-fork-reference §7)
이며, 본 기능은 그 불변식 위에 **대화 내부 브랜치 트리**를 도입해 ChatGPT식 편집·재답변·
버전 페이징을 구현한다.

- **일반(1:1) 대화**: [단순 메시지 수정 / 요청사항 수정] 중 선택.
  - *단순 수정* = 제자리 내용 변경(재답변 없음, "편집됨" 배지).
  - *요청사항 수정* = 편집 지점에서 새 브랜치를 만들어 재답변. 이전 답변도 조회 가능,
    ChatGPT식 `< 현재/전체 >` 페이징으로 브랜치 전환(하위 출력 정합 갱신).
- **공유(그룹) 대화**: **단순 수정만**. `@assistant` 를 호출한 메시지는 편집 불가.

## 2. Goal
- REQ-ME-R1 (1:1 단순 수정): 1:1 대화에서 본인 메시지 제자리 수정 — 재답변 없이 내용만
  갱신, 편집 이력 보존("편집됨" 표식).
- REQ-ME-R2 (1:1 요청사항 수정 = ChatGPT 분기): 편집 지점에서 형제 버전 + 새 브랜치 생성
  → 재답변. 이전 브랜치(옛 사용자 메시지·답변·하위)는 보존되어 페이징으로 조회 가능.
  `< n/m >` 페이징으로 브랜치 전환 시 그 지점 이후 화면·LLM 문맥이 정합하게 전환된다.
- REQ-ME-R3 (그룹/공유 단순 수정): 그룹 대화에서 본인 메시지 단순 수정만 허용. 브랜치·재답변
  없음. `@assistant` 를 호출한(호출을 유발한) 메시지는 편집 잠금.
- REQ-ME-R4 (권한/보안): 본인이 발신한 메시지만 편집 가능(`sender_account_id == actor`,
  IDOR 게이트). 공유 window([from,to] 가시성)와 정합. 편집·브랜치 전환은 `WebAuditEvents`
  감사 기록.
- REQ-ME-R5 (recall 정합·무회귀): 편집·브랜치는 LLM 문맥 recall 과 정합 — recall 은 **활성
  브랜치 경로만** 로드한다. **분기 없는 대화(거의 전부)는 기존 로더와 byte-identical**
  (`has_branches` 게이트 fast-path, `has_restricted_members` 패턴 답습).

## 3. In Scope
- `agent_runtime.core_messages` / `messages`(표시 store) 브랜치 컬럼 + `core_conversations`
  게이트 플래그·active_leaf 컬럼 (마이그레이션 1개, 비파괴 additive).
- 코어 recall 로더(`_load_conversation_messages`)의 active-path 확장.
- 편집(`POST /api/conversations/{cid}/messages/{mid}/edit`) + 브랜치 전환
  (`POST /api/conversations/{cid}/branch/switch`) 엔드포인트.
- `GET /api/history` 확장(활성 경로 + 버전 메타).
- 프론트 편집 UI + `< n/m >` 페이징 렌더.

## 4. Out of Scope
- 그룹 대화의 브랜치/재답변(공유는 단순 수정만 — 설계 제약).
- assistant 메시지 자체의 사용자 편집(assistant 답변은 편집 대상 아님 — 재답변으로만 변경).
- 공유 링크(`/share/{token}`) read-only 뷰어에서의 편집(발화 지점 아님).
- 편집 이력의 무제한 보존 정책·GC(후속 — 초기엔 전부 보존).

## 5. Inputs
- 편집 요청: `{conversation_id, message_id, mode: simple|reanswer, new_content}`.
- 브랜치 전환: `{conversation_id, message_id | target_leaf_id, version_number}`.
- 세션 actor(account_id, 위조 불가 claim) — 편집 권한 게이트.

## 6. Outputs
- 편집/브랜치 결과 dict(프론트 부분 갱신용) — `/api/ask` result 형태 재사용(reanswer).
- 상태 변경: core_messages/messages 브랜치 행 + core_conversations.active_leaf_message_id.
- 감사: `WebAuditEvents`(edit / branch.switch high-signal user action).

## 7. Main Flow
정본 = [DESIGN.md](./DESIGN.md). 요지:
1. 편집 요청 → authz(본인 발신 + 대화 접근 + 모드별 잠금 규칙).
2. simple → 제자리 버전 승격(내용 갱신, 편집 배지). reanswer → 형제 버전 + 새 브랜치 →
   `/api/ask` 재dispatch → active_leaf 갱신.
3. 이후 recall/history 는 active_leaf 기준 활성 경로만 로드.

## 8. Acceptance Criteria
- AC-ME-1 (마이그레이션 비파괴): core_messages 에 `parent_message_id`,
  `edit_root_message_id`, `edit_version`; core_conversations 에 `has_branches`(DEFAULT false),
  `active_leaf_message_id` 가 idempotent 추가. 기존 행 영향 0(전부 NULL/false). MySQL parity ALTER 동반.
- AC-ME-2 (비분기 항등성 = 회귀 0): `has_branches=false` 대화의 recall/history 결과가 변경 전과
  byte-identical. 단위테스트로 단언.
- AC-ME-3 (1:1 단순 수정): 본인 user 메시지 제자리 수정 → 내용 갱신 + "편집됨" 표식, 재답변
  없음, 하위 메시지 불변.
- AC-ME-4 (1:1 요청사항 수정 분기): 편집 → 형제 버전 + 새 브랜치 + 재답변. 옛 브랜치 보존.
  `has_branches=true` set, active_leaf=새 leaf.
- AC-ME-5 (페이징 정합): `< n/m >` 전환 시 active_leaf 갱신 → 그 지점 이후 화면·recall 이
  선택 브랜치로 정합 전환.
- AC-ME-6 (그룹 단순수정·@assistant 잠금): 그룹 대화에서 본인 메시지 단순수정 허용, @assistant
  호출 메시지 편집 시 4xx 거부. 타인 메시지 편집 4xx(IDOR).
- AC-ME-7 (공유 window 정합·fail-closed): windowed 멤버 recall 은 active-path 필터와 window
  필터가 **합성**되어 가려진 구간이 새지 않는다. PG 오류 시 fail-closed(빈 history).
- AC-ME-8 (감사): edit·branch.switch 가 `WebAuditEvents` 에 기록된다(§9 audit).
- AC-ME-9 (시각검증): PB-0008 실 Windows 브라우저에서 편집·재답변·페이징 시각검증
  (visual_verification_scope: always).
- AC-ME-10 (branch-hardening, 2026-07-22): 답변 persist·전송 대상 대화는 **요청 conversation_id 와
  일치**해야 하며(웹/ask 경로 conversation_id 미지정 시 fail-closed — 전역/공유 폴백 금지, INV-6),
  한 run 의 브랜치 append 부모 체인은 생성 중 브랜치 전환에 오염되지 않는다(run-scoped leaf, INV-7).
  비분기 대화는 무영향(AC-ME-2/INV-1). 회귀 테스트=`tests/test_branch_hardening.py`.
