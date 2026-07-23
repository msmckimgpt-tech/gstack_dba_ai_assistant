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
maturity: substantial
ai_generated: true
feature_id: feature-0024-conversation-folders
linked_unit: unit/feature-0024-conversation-folders
created: 2026-07-23
sources:
  - ../../unit/feature-0024-conversation-folders/docs/FUNCTION.md
---

# Feature — 대화 폴더 (프로젝트 워크스페이스)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0024-conversation-folders/docs/FUNCTION|unit/feature-0024-conversation-folders/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

좌측 대화 목록에 재귀 **폴더(프로젝트)** 를 도입 — 대화를 폴더로 조직·이동하고, 폴더별
커스텀 지침을 그 폴더의 대화에 발화 시 자동 주입한다. 폴더는 계정별 개인 오버레이(엄격 per-user 격리).

## 2. 상태

- **단계**: substantial (Phase 1+2a 라이브 완결 · Phase 2b[폴더 파일·datasource 자동 스코프] 이연)
- **마지막 갱신**: 2026-07-23
- **AI 작업자**: claude (feature-0024 cycle)

## 3. 책임 경계

- 입력: 폴더 CRUD/배정/이동/삭제/restore 요청(요청자 계정), 폴더 지침·런타임 max-depth 설정.
- 출력: 요청자 스코프 폴더 트리 + 대화 목록 `folder_id`, 폴더 지침이 주입된 시스템 프롬프트.
- side-effect: `conversation_folders`/`folder_conversation_map`(계정 소유) upsert·soft-delete(폴더 레코드만), `WebAuditEvents` 기록. 폴더 삭제해도 대화는 부모/root 로 승격 보관(하드삭제 없음).
- 보안 경계: 폴더는 **엄격 per-user(owner-scope) 격리** — `folder.list.own`/`folder.manage.own` own-only(`folder.*.any` 폐지), 크로스-계정 노출 차단(Critical §12.3)·restore IDOR(HIGH) 봉인. 폴더 지침 주입은 항상 요청자 자기 폴더 기준(신규 특권 없음). 정합 정본 = SECURITY.md §26.

## 4. 관련 정본

- [[../../unit/feature-0024-conversation-folders/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0024-conversation-folders/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0024-conversation-folders/docs/REVIEW|REVIEW.md]] — 적대적 보안 리뷰(REV-20260723T060000 SHIP-WITH-FIXES · REV-20260723T170000 privacy tightening)
- [[../../unit/feature-0024-conversation-folders/docs/ANCHOR|ANCHOR.md]] — 방향성 앵커

## 5. 관련 노트

- [[../Architecture/Module-Map|Module Map]] — 사이드바·폴더 라우터·스토어 위치
- 코드 거주: feature-0003(라우터·RBAC·사이드바 UI), feature-0002(스키마·alembic 0044·폴더 지침 주입)
- 상호작용: feature-0009(그룹/멤버 ACL — 공유 대화 계정별 배정), feature-0018(런타임 설정 — max-depth)

## 6. Open questions / 미해결

- Phase 2b: 폴더 **파일**(폴더-소유 첨부 ask-time 주입·첨부 IDOR 스코프 확장) + datasource/product **자동 스코프 핀** 배선.
- 공유 폴더(폴더 트리 자체를 타 계정과 공유) 도입 여부 — v1 은 폴더=개인 조직 오버레이.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0024-conversation-folders/docs/MODIFY.md` 에.

- 2026-07-23: 초안 작성 (대화 폴더 Phase 1+2a 라이브 완결 색인 — 재귀 폴더·계정별 격리·폴더 지침 주입).
