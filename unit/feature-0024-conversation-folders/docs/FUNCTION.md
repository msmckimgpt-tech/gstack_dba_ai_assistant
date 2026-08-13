---
doc_type: FUNCTION
feature_id: feature-0024-conversation-folders
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function — 대화 폴더 (프로젝트 워크스페이스)

## 1. Summary
좌측 대화 목록에 **폴더(프로젝트)** 구조를 도입한다. 사용자는 대화를 폴더로 조직(이동/제외)하고, 폴더를 재귀적으로 중첩하며(깊이 상한은 런타임 설정), 폴더를 삭제해도 대화는 보관된다. 나아가 폴더 단위로 **커스텀 프롬프트(지침)**와 **미리 첨부된 파일**을 얹어 ChatGPT/Claude 의 "프로젝트"처럼 폴더 내 대화가 공통 컨텍스트를 상속한다. 이 제품이 사내 DB 질의 AI 라는 특성에 맞춰, 폴더에 **기본 데이터소스·스키마 스코프**와 **타임존/ENUM/화폐 규약** 같은 반복 규칙을 지침으로 핀할 수 있다.

정본 코드 거주: 스키마·마이그레이션·컨텍스트 조립 = feature-0002-agent-core, 라우터·권한·UI = feature-0003-agent-web-ui (cross-cut docs-only feature — feature-0019 선례). 대화 정본 스토어 = PostgreSQL `agent_kb.agent_runtime`.

## 2. Goal
- REQ-20260723-folder-organize: 대화를 폴더로 **이동/제외**한다. 배정은 **계정별 독립**(소유자·공유 멤버 각자 자기 폴더 트리에 그 대화를 배치). 이동은 이후 대화 컨텍스트만 바꾸고 과거 응답은 불변.
- REQ-20260723-folder-delete-keep: 폴더를 **삭제하면 대화는 보관**(대화의 폴더 배정만 해제/승격, soft-archive 아님). 폴더 삭제는 Trash+undo(우발 손실 방지), 하위 대화/서브폴더는 부모(또는 root)로 승격.
- REQ-20260723-folder-recursive: 폴더 **재귀 중첩**. 최대 깊이는 **런타임 설정값**(WebRuntimeSettings, 기본 4)으로 조절. **grandfathering**: 설정을 낮춰도 이미 깊어진 폴더는 소급 강제·평탄화하지 않고 그대로 보존한다. 상한은 **create/move 시점에만** 강제하되 "더 깊어지는 경우"만 차단(같거나 얕아지는 이동은 항상 허용). 순환 방지.
- REQ-20260723-folder-knowledge: 폴더 단위 **커스텀 프롬프트** + **미리 첨부된 파일**. 요청 시 **요청자의 폴더 기준**으로 시스템 프롬프트·첨부 컨텍스트에 주입(per-asker, ask-time). 폴더 소유자=요청자라 IDOR 안전.
- REQ-20260723-folder-query-scope: (DQA 특화) 폴더에 **기본 데이터소스/제품·스키마 스코프**·규약 지침을 핀 → 폴더 내 대화가 상속(반복 마찰 차단).
- REQ-20260813-folder-dnd-shared-group: **다른 계정이 공유한 그룹 대화도 사이드바 drag&drop 으로
  폴더별 이동**(사용자 요청 2026-08-13). REQ-organize 의 "계정별 배정" 을 드래그 입력 수단까지
  완성하는 것 — 대상 판정은 `내 대화 + is_member 그룹 대화`(= 폴더 파티션과 동일 predicate). 관리자
  `.any` 열람 "타 계정 대화" 는 폴더 파티션 대상이 아니므로 제외(개인 오버레이 경계 유지).
- REQ-20260723-folder-rbac: 폴더 조작 권한을 RBAC 카탈로그에 등록. **폴더는 엄격한 개인(per-user) 오버레이**이므로 `folder.list.own`/`folder.manage.own` **own 권한만** 둔다(2026-07-23 프라이버시 수정 — `folder.*.any` 크로스-계정 권한은 폴더 노출 벡터라 폐지). 폴더는 어떤 권한으로도 타 계정에 노출·관리되지 않는다.

## 3. In Scope
- PG `agent_runtime` 신규 테이블 `conversation_folders`(계정 소유·재귀 self-FK·지침·스코프 핀) + `folder_conversation_map`(계정별 대화↔폴더 배정) + alembic 0044 + GRANT + `agent_runtime_schema.sql` parity.
- 폴더 CRUD 라우트, 대화 배정/이동, 폴더 삭제(대화 보관·승격), 재귀 조회(WITH RECURSIVE + depth cap).
- 대화 목록 payload 에 요청자 스코프 `folder_id` 추가(순수 additive), 사이드바 재귀 폴더 렌더(app.js:3022 seam) + 드래그/우클릭 이동 + breadcrumb.
- 드래그 대상 판정 단일화 — `isFolderScopedConversation`(owner || is_member) 하나를 **폴더 파티션과 draggable 게이트가 공유**해, "폴더에 보이는데 끌 수 없다" 류 표시-집행 불일치를 구조로 차단(2026-08-13 folder-dnd-shared-group).
- 폴더 프롬프트: `conversation_folders.instructions` → `compose_system_prompt` 주입(요청자 폴더 기준).
- 폴더 파일: 폴더-소유 첨부를 요청자 폴더 기준으로 ask-time 컨텍스트 주입(첨부 스코프 게이트를 conv→요청자-폴더 확장, 폴더 소유=요청자 안전).
- 런타임 max-depth 설정(WebRuntimeSettings) + admin UI.
- RBAC `folder.*`(list/create/rename/delete/move .own·.any) 4지점 등록.

## 4. Out of Scope
- **Phase 2b (후속 증분)**: 폴더 **파일**(폴더-소유 첨부 저장 + ask-time 요청자-폴더 주입 + 첨부 IDOR 스코프 확장) 및 **datasource/product 자동 스코프 핀**(폴더 컬럼은 스키마에 이미 존재 — 향후 배선). 첨부 스코프 IDOR 확장은 별도 저장·보안 표면이 크므로 전용 적대 리뷰와 함께 별도 증분. Phase 2a 는 폴더 **지침(프롬프트)** ask-time 주입만 포함.
- feature-0022 scratch 작업공간의 폴더별 승격(지속 cross-source JOIN) — 별도 후속(D3=A 첨부 seed 채택, scratch 승격은 v2+).
- 공유 폴더 자체(폴더 트리를 타 계정과 공유) — v1 은 폴더=개인 조직 오버레이. 공유 대화는 각 멤버가 자기 폴더에 배치(REQ-organize)하되 폴더 구조 자체는 공유 안 함.
- 저장 쿼리를 폴더 1급 자산으로(확장 ⑧) — 후속.
- 대용량 폴더 지식 RAG(확장 ⑥) — 후속. v1 은 소량 전량 주입(head-5-rows/inline cap 재사용).
- 공유 링크(익명) 응답에 폴더 노출 — 금지(누출면).

## 5. Inputs
- 폴더 CRUD: `{name, parent_folder_id?, instructions?, datasource_id?, product_id?}`.
- 대화 배정: `PATCH /api/conversations/{cid}/folder {folder_id|null}` (요청자 계정 스코프).
- 런타임 설정: `folder_max_depth`(WebRuntimeSettings).
- ask-time: 요청자 account_id + 대화 cid → 요청자 폴더 resolve.

## 6. Outputs
- 폴더 트리(재귀), 대화 목록 item 에 `folder_id`(요청자 스코프).
- 폴더 지침·파일이 반영된 LLM 시스템 프롬프트/컨텍스트.
- 상태 변경: `conversation_folders`, `folder_conversation_map` rows.

## 7. Main Flow
1. 폴더 생성(계정 소유, parent depth 검증) → row.
2. 대화 배정: `folder_conversation_map(account_id, conversation_id, folder_id)` upsert(계정별).
3. 사이드바: 요청자 배정 기준 폴더 파티션 → 폴더 하위에 기존 날짜 트리 중첩 렌더.
4. ask: 요청자 폴더 resolve → 폴더 instructions + 폴더 파일을 컨텍스트 주입.
5. 폴더 삭제: 하위 승격 + map 정리(대화 보존) + Trash/undo.

## 8. Edge Cases
- 순환 참조(parent 체인에 자기 포함) → 거부.
- depth cap 초과 **신규** 이동/생성 → 거부(설정값 기준). 단 grandfathering: 이미 상한 초과인 기존 폴더는 보존, create=`parent_depth+1 > cap` 거부, move=결과 절대깊이가 상한 초과 **AND** 기존보다 깊어질 때만 거부(같음/얕아짐은 허용).
- 공유 대화를 멤버가 자기 폴더에 배정 → 소유자 뷰 불변(계정별 격리).
- 폴더 삭제 시 하위 서브폴더/대화 승격.
- 접근 불가 대화를 폴더에 배정 시도 → `_account_can_access_conversation` 게이트 거부.
- 폴더 파일 다수 → 토큰 예산(첨부 cap 재사용).

## 9. Error Handling
- IDOR: 폴더 소유/대화 접근 게이트 실패 → 403.
- depth/순환 위반 → 422(사유 명시).
- 배정 대상 대화 미접근 → 403.
- 롤백: 마이그레이션 expand-safe, 폴더 삭제는 Trash(가역).

## 10. Dependencies
### 내부 기능 의존성
- feature-0002-agent-core (PG 스키마·alembic·compose_system_prompt·첨부 주입)
- feature-0003-agent-web-ui (라우터·RBAC·사이드바 app.js)
- feature-0018 (WebRuntimeSettings — max-depth 런타임 설정)
- feature-0009-group-conversation (그룹/멤버 ACL 상호작용)
- feature-0003 conv-date-tree (재귀 사이드바 렌더러 renderDateNode 재사용)

### 외부 의존성
- PostgreSQL `agent_kb.agent_runtime`, MinIO(폴더 파일), alembic/migrate-lint.

### shared 모듈 의존성
- shared/db (_pg_connect), shared/runtime_settings.

## 11. Acceptance Criteria
- AC-20260723T054724-folder-organize-1: 대화를 폴더로 이동/제외하면 요청자 사이드바에 즉시 반영되고, 같은 대화가 다른 멤버 뷰에는 그들 배정대로 독립 표시(계정별 격리).
- AC-20260723T054724-folder-delete-keep-1: 폴더 삭제 후 그 폴더의 대화가 모두 root(또는 부모)로 승격되어 목록에 남는다(archive 아님). undo 로 복구.
- AC-20260723T054724-folder-recursive-1: max-depth 설정값까지 중첩 가능, 초과 생성/이동은 거부. 순환 배정 거부.
- AC-20260723T054724-folder-knowledge-1: 폴더 지침·파일이 폴더 내 대화의 assistant 응답 컨텍스트에 요청자 기준으로 주입됨(라이브 실측).
- AC-20260723T054724-folder-idor-1: 타 계정 폴더/미접근 대화 배정·조회 시도가 403 으로 차단(§18.8 적대 검증).
- AC-20260813T181200-folder-dnd-shared-group-1: 다른 계정이 소유한 그룹 대화(내가 멤버)를 사이드바에서 **드래그해 폴더로 이동**할 수 있고, 폴더 안 항목을 root 드롭 존으로 드래그해 뺄 수 있다(`folder.manage.own` 보유 시).
- AC-20260813T181200-folder-dnd-shared-group-2: 그 이동은 요청자 계정 스코프에만 반영된다 — 소유자·타 멤버의 사이드바 위치·폴더 표시는 불변(라이브 크로스-계정 실측).

## 12. Observability
- 폴더 CRUD/배정 audit 로그, depth-cap/순환 거부 카운트.
- ask-time 폴더 컨텍스트 주입 여부 계측(시스템 프롬프트 블록).

## 13. Pre-approved Changes
- 사용자 결정(2026-07-23 AskUserQuestion): D1=런타임 설정 조절 가능 재귀, D2=계정별 배정(소유자 기본 + 멤버 각자 이동), D4=Phase 1+2 통합. deploy_scope: included(전역).
