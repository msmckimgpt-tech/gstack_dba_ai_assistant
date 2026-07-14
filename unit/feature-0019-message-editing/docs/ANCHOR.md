---
doc_type: ANCHOR
feature_id: feature-0019-message-editing
created_at: 2026-07-13T00:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0019-message-editing 메시지 편집

## §1. 외부 관점 요약
"왜 편집을 append-only 위에 브랜치로 얹지, 그냥 메시지 내용을 UPDATE 하면 안 되나?" →
LLM 문맥 recall 이 대화 전체를 native 메시지로 주입하고(§14 datamark 대상 아님), 재답변은
"이전 답변도 조회 가능"(사용자 요구) 해야 하므로 편집 이력을 파괴하면 안 된다. ChatGPT 처럼
브랜치를 남기고 페이징하는 것이 유일하게 정합하다. "왜 그룹은 재답변 안 되나?" → 공유 대화의
답변은 여러 멤버가 공유한 근거라 변조 불가여야 하고, `@assistant` 호출 메시지 편집은 공유
답변의 전제를 바꾸므로 잠금(사용자 명시 제약).

## §2. 대안 분기
- **Alt-A: fork-per-edit(편집마다 새 대화로 fork).** 안 고른 이유: 별 conversation_id 로 분할 →
  사이드바 오염 + deep-copy 비용 + "한 대화 인라인 페이징" UX 불일치. fork 의 cut-point·게이트
  개념만 이식(DESIGN §1).
- **Alt-B: in-place content UPDATE(이력 없음).** 안 고른 이유: "이전 답변 조회" 불가 + recall
  정합 깨짐. 사용자 요구(페이징·이전 답변 조회) 위배.
- **Alt-C: 마지막 턴만 재답변(중간 편집 금지).** 안 고른 이유: 사용자가 "ChatGPT식 완전 분기"
  명시 선택(어느 메시지든). active-path 모델이 중간 편집을 자연 지원.

## §3. 불변식 (변경 시 재검토 필수)
- INV-1: **비분기 대화(`has_branches=false`)의 recall/history 는 변경 전과 byte-identical.**
  (게이트 fast-path — `has_restricted_members` 패턴. 위반 시 전 대화 회귀.)
- INV-2: 편집은 **본인 발신 메시지만**(`sender_account_id == actor` claim). IDOR 게이트.
- INV-3: 공유 window 술어는 active-path CTE 에 **항상 합성** — 가려진 구간은 물리 배제(fail-closed).
- INV-4: 그룹 대화에서 `@assistant` 호출(유발) 메시지는 **편집 잠금**. 그룹은 브랜치/재답변 없음.
- INV-5: 두 store(core_messages/messages)의 브랜치 포인터는 **각 store 내부 id 로 저장**
  (cross-store 시각 cut 불필요 — fork F1 회피). bridge 는 created_at 유지.

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — §18.8 적대적 보안 리뷰(REV-20260714-0003 [SUBAGENT] SHIP-WITH-FIXES)·PB-0008 시각검증 기록은 REVIEW.md/TEST.md. 본 §4 는 major 외부 검증 챌린지 전용, feature-0009 §4 규약 답습.)
