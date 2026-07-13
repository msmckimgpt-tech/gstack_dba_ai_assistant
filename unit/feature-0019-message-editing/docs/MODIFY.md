---
doc_type: MODIFY
feature_id: feature-0019-message-editing
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log — 메시지 편집 (cross-cut 코드 거주 0002/0003)

## 2026-07-13 Phase 1 checkpoint 1 (백엔드 기반)

### feature-0002-agent-core
- `alembic/versions/20260713_0041_message_branching.py` (신규): 브랜치 컬럼 additive 마이그레이션.
- `src/scripts/agent_runtime_schema.sql`: core_messages/messages/core_conversations 브랜치 컬럼
  멱등 ALTER + 인덱스(self-heal).
- `src/modules/runtime_backend.py`:
  - 쿼리 상수 추가: `_PG_LOAD_BRANCH_STATE`·`_PG_LOAD_CORE_MESSAGES_BRANCH`(active-path CTE)·
    `_PG_INSERT_CORE_MESSAGE_BRANCH`·`_PG_SET_ACTIVE_LEAF`·`_PG_ENABLE_BRANCHES`·
    `_PG_BACKFILL_CORE_PARENTS`·`_PG_BACKFILL_MSG_PARENTS`·`_PG_MAX_CORE_MESSAGE_ID`.
  - PgRuntimeBackend: `load_branch_state`·`set_active_leaf`·`enable_branches`·`max_core_message_id`
    메서드 추가; `load_core_messages`(use_branch 게이트)·`save_core_message`(브랜치 컬럼) 확장.
- `src/agent_core.py`: `_load_conversation_messages`(has_branches → use_branch active-path)·
  `_save_message`(active_leaf 체이닝·전진, parent_message_id 인자) 확장.
- `tests/test_message_branching.py` (신규): 11 유닛(비분기 항등성·active-path·window 합성).

### feature-0003-agent-web-ui
- (남은 pass) `routers/conversations.py`·`routers/_conv_store.py`·`routers/_bootstrap_schema.py`·
  `static/{app.js,index.html,styles.css}`.

## 설계 결정 기록

- **DEC-1 (PG-first, MySQL parity 생략)**: 브랜치는 windowed recall 처럼 PG 전용 인프라. 선례
  `has_restricted_members`·`recall_floor_created_at`(둘 다 core_messages/core_conversations 의
  PG-only 컬럼, MySQL AgentCore* 에 미미러)를 답습. 근거: (a) AGENT_RUNTIME_READ_BACKEND=postgres
  가 정본, (b) active-path 로직이 PG CTE 전용, (c) Phase 1 은 1:1(본인 데이터)이라 MySQL fallback
  이 옛 브랜치를 노출해도 cross-account 누출 아님(graceful degradation). Phase 2(그룹)는 브랜치
  없음이라 무관.
- **DEC-2 (브랜치 = 대화 내부 트리, fork 아님)**: DESIGN §1. fork 의 cut-point·게이트 플래그
  패턴만 이식, deep-copy·별 conversation_id 는 미채용.
- **DEC-3 (형제 버전 그룹핑 = 공유 parent_message_id)**: 편집된 user 메시지들은 같은 parent 를
  공유하므로 별도 edit_root 태깅 없이도 페이징 그룹 식별 가능. edit_root/edit_version 은
  정렬·명시 표식용(첨부 house-pattern 대칭).

## CHG-20260713-0001 (Phase 1 checkpoint 1 — 백엔드 기반)
- 변경: 위 feature-0002 목록(마이그 0041·schema.sql·runtime_backend·agent_core·test_message_branching).
- 성격: additive·dormant scaffold(has_branches DEFAULT false → 신규 경로 비활성, 라이브 무영향).
- 검증: 단위 11 PASS + 기존 runtime/dual-write/convo-search 회귀 0(54 PASS). 상세 TEST.md Run 2026-07-13.
- 결정: DEC-1(PG-first)·DEC-2(브랜치=대화 내부 트리, fork 아님)·DEC-3(형제=공유 parent).

## CHG-20260713-0002 (Phase 1 checkpoint 2 — 표시 store 쓰기 정합)
- 변경: 마이그 0041 확장(messages.core_message_id·core_conversations.active_display_leaf_message_id) +
  memory.save_memory_message/PG backend 브랜치 체이닝 + display 헬퍼(load_display_branch_state·
  set_active_display_leaf) + enable_branches display leaf 확정 + 단위테스트 +4.
- 성격: additive·dormant. 정상 append byte-identical(core_message_id 미스레딩), hot-path call-site 무변경.
- 검증: 누계 15 PASS, 회귀 0(55 PASS).
- 결정: DEC-4(두 store dual active_leaf + core_message_id 링크 좌표, DESIGN §2.3)·DEC-5(display→core
  매핑은 user 메시지 created_at 1:1 매칭 — 정상 append 무-스레딩).
