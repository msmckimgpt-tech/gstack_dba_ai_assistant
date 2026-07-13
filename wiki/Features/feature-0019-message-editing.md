---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: in-progress
ai_generated: true
feature_id: feature-0019-message-editing
linked_unit: unit/feature-0019-message-editing
sources:
  - ../../unit/feature-0019-message-editing/docs/FUNCTION.md
  - ../../unit/feature-0019-message-editing/docs/DESIGN.md
---

# Feature — 메시지 편집 (Message Editing)

> Feature 의 사람용 입구. 정본은 [[../../unit/feature-0019-message-editing/docs/FUNCTION|FUNCTION.md]]·
> [[../../unit/feature-0019-message-editing/docs/DESIGN|DESIGN.md]].

## 1. 한 줄 요약
사용자가 자신이 보낸 메시지를 수정할 수 있게 한다 — 1:1 대화는 [단순 수정 / 요청사항 수정(ChatGPT식
분기 재답변·`< n/m >` 페이징)], 공유(그룹) 대화는 단순 수정만(@assistant 호출 메시지 잠금).

## 2. 상태
- Phase 1(1:1) 백엔드 기반 완료(마이그 0041·active-path recall 로더·쓰기 체이닝, 단위 11 PASS).
- 남은 Phase 1: 엔드포인트(edit/branch-switch/history)·프론트·통합테스트·PB-0008.
- Phase 2(그룹 단순수정·@assistant 잠금): 후속.

## 3. 책임 경계
- 코드 거주: feature-0002(core_messages 브랜치 트리·recall 로더·쓰기), feature-0003(엔드포인트·프론트).
- append-only 대화 모델 위에 **대화 내부 브랜치 트리**(parent_message_id + active_leaf +
  has_branches 게이트)를 얹음. fork(별 conversation deep-copy)는 미사용 — cut-point 패턴만 이식.

## 4. 관련 정본
- [[../../unit/feature-0019-message-editing/docs/DESIGN|DESIGN.md]] (브랜치 모델·로더 전략·fork 검토)
- [[../../unit/feature-0019-message-editing/docs/ANCHOR|ANCHOR.md]] (INV-1~5)
- 연관: feature-0009(그룹/공유 window)·feature-0003(fork/share)·SECURITY §21(공유창 격리)

## 5. 관련 노트
- 첨부 버전 체인(RootAttachmentId/VersionNumber/SupersededAt) house-pattern 을 메시지 버전에 대응.

## 6. Open questions / 미해결
- simple 편집 이력 보존 방식(DESIGN D1) — 착수 중 확정.
- 그룹 window + 브랜치 동시 상호작용(Phase 2, 현재 그룹은 브랜치 없음이라 무관).

## 7. 변경 이력 (이 카드)
- 2026-07-13: 신규(Phase 1 checkpoint 1 동반).
