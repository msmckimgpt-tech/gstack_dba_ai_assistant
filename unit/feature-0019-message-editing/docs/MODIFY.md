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

## CHG-20260713-0003 (마이그레이션 게이트 fix — MAX_MIGRATION 마커 갱신)
- 변경: `alembic/versions/MAX_MIGRATION.txt` 0040 → 0041_message_branching.
- 사유: CI Migration gate(`bin/migrate-lint.sh --heads`, parallel-work ITEM-02)가 head(0041)와
  MAX_MIGRATION 마커(0040) 불일치를 적발 → PR #766 CI red. 신규 마이그레이션 추가 시 이 마커도
  함께 갱신해야 함(verify-completion·make test 는 검사 안 하는 CI 전용 게이트). 코드/스키마 무변경.
- 검증: migrate-lint --self-test PASS + --heads PASS(head 0041 단일·번호중복 0·MAX_MIGRATION 일치).

## CHG-20260714-0004 (Phase 1 checkpoint 3 — 엔드포인트 + 프론트, 편집 기능 활성화)
- feature-0003-agent-web-ui:
  - `routers/conversations.py`: `post_edit_message`(POST …/messages/{mid}/edit, simple/reanswer)·
    `post_branch_switch`(POST …/branch/switch) 신규.
  - `routers/_conv_store.py`: 브랜치 오케스트레이션 블록(9 함수) + `_get_history` 브랜치 필터/버전 메타.
  - `app.py`: 브랜치 헬퍼 7종 import(app.* 노출).
  - `static/app.js`: 편집/페이징 로직(`_canEditMessage`·`_startInlineEdit`·`_pageBranch`·
    `_buildBranchPager`·`_submitMessageEdit`·`_switchBranch`) + renderMessages user 컨트롤.
  - `static/styles.css`: 편집 박스·버전 페이저·편집됨 배지 스타일.
  - `tests/route_snapshot_p5b.json`: route-parity golden 갱신(신규 2 route, 205→207).
  - `docs/ROUTEMAP.md`: 재생성(202 routes, 신규 2 등재).
- 성격: 편집 기능을 실제 활성화(has_branches true 경로 생성). 비분기 대화는 여전히 기존 경로(무회귀).
- 검증: ROUTEMAP·codenav 게이트 PASS + make test import OK(브랜치 15 + route-parity PASS) + §18.8 보안 리뷰.
- 결정: DEC-6(edit 재사용 = fix-with-ai 재dispatch 패턴)·DEC-7(Phase 1 그룹 편집 차단, 서버 authz + UI 게이트).

## CHG-20260714-0005 (POST-DEPLOY hotfix — 브랜치 로더 파라미터 타입추론)
- 변경: `runtime_backend._PG_LOAD_CORE_MESSAGES_BRANCH` 의 nullable 파라미터에 명시 캐스팅
  (`active_leaf_id::bigint`, `floor_ca/ceil_ca/joined_ca::timestamptz`) + 회귀 가드 테스트.
- 사유: 비-windowed 브랜치 대화(1:1 편집)는 floor/ceil/joined 가 전부 None → psycopg 가 untyped
  NULL 전송 → `$n IS NULL` 에서 PG "could not determine data type of parameter $3" → CORE recall
  로더 전체 실패(MySQL fallback 도 실패). WINDOWED 쿼리는 windowed 시에만 호출돼 항상 non-None 이라
  무사했으나, 브랜치 쿼리는 비-windowed 에서도 호출돼 노출됨.
- 적발: **PB-0008 라이브 reanswer** (ask-worker 로그 진단). 단위테스트는 mock cursor 라 SQL 유효성
  미검증(gap) → visual_verification_scope: always 정책의 가치 실증.
- 검증: psql PREPARE 로 캐스팅이 untyped NULL 해소 확인 + 회귀 가드 단언 16 PASS. PB-0008 재검증 예정.

## CHG-20260714-0006 (Phase 2 — 그룹/공유 단순편집)
- feature-0003 conversations.py: post_edit_message 그룹 편집 허용 — 그룹은 simple 강제 +
  @assistant 호출 메시지 잠금(mentions.message_invokes_assistant) + per-message sender IDOR
  (meta_json.sender_account_id == actor, 미상 시 owner fail-closed). 1:1 은 기존 owner 검사.
- feature-0003 static/app.js: _canEditMessage 그룹 지원(본인 발신 msgIsOwn + @assistant 미호출) +
  _startInlineEdit 재답변 버튼 그룹 미노출(단순 수정 전용).
- feature-0003 _conv_store.py: _branch_map_display_user_to_core core count 에서 __event__(그룹 join
  알림, core role='user' / display role='system' 비대칭) 제외 — 서수 매핑 오손상 방지(SEC #5).
- 성격: 그룹 단순편집 활성화(AC-ME-6). route 무변경(로직만). 1:1 무회귀.
- 검증: make test 회귀 0(4 pre-existing local-env) + AST OK. §18.8 보안 = REV-0005.

## CHG-20260722T-branch-hardening (예방적 하드닝 — cross-conversation 누출 표면 봉인 + 브랜치 체인 격리)
- **배경**: 2026-07-22 "메시지 편집·재요청 답변이 타 사용자 대화로 누출" 신고(HANDOFF)를 진단.
  라이브 DB forensics(agent_kb.agent_runtime) + PB-0008 통제 재현 결과 **실제 누출·재답변 실패는
  없음**을 확정(오진 — 동시 in-flight 두 대화의 전역 message-id 교차 배열을 ID-순 DB 스캔에서 누출로
  오독). 계정 매핑도 반대(계정1=bootstrap_admin, 계정10=admin). 다만 조사 중 발견한 **실재 잠재
  결함 2건**을 예방적으로 봉인. **이번 신고 원인 아님 — defense-in-depth.**
- **footgun A (fail-closed 대화 바인딩)** — `feature-0002 agent_core._run_agent_core`: 웹/ask 경로
  (`account_id` 지정)에서 `conversation_id` 가 falsy 면 `_get_conversation_id()` 가 프로세스 전역
  env(`AGENT_CONVERSATION_ID`)·호스트 공유 파일(`/shared/conversation_id`)로 폴백하던 것을 fail-closed
  로 차단(LLM/DB 작업 이전 조기 가드). CLI/console/eval(`account_id=None`)은 파일 폴백 유지(정당).
- **footgun B (run-scoped active-leaf)** — `feature-0002 agent_core._save_message`(core) +
  `feature-0002 modules/memory.save_memory_message`(display): 브랜치 대화(`has_branches=true`)의 한
  run 이 여러 메시지를 순차 append 할 때 매 append 가 DB `active_leaf` 를 재조회하던 것을, run 첫
  append 만 DB 를 쓰고 이후는 **run-local last-leaf**(신규 `shared/config` contextvar
  `_RUN_ACTIVE_LEAF_CORE/_DISPLAY`)로 체인해 생성 중 브랜치 페이징 전환이 부모 체인을 산란시키지
  못하게 격리. run 시작(`reset_run_active_leaf()`)+`run_agent` finally 이중 리셋(스레드 재사용 bleed 방지).
- **불변식(ANCHOR §3)**: INV-1(비분기 byte-identical) 보존 — 위 블록은 `has_branches=true` 에서만
  진입. 신규 INV-6(fail-closed 대화 바인딩)·INV-7(run-scoped 브랜치 체인) 추가.
- **성격**: route/handler/RBAC 무변경(로직·contextvar만). 웹 자산(HTML/CSS/JS) 무변경 → PB-0008
  게이트 비대상(진단 단계 PB-0008 은 별도 수행·PASS). Major(코어 write 경로·격리).
- **검증**: 신규 `tests/test_branch_hardening.py` 9건 + 기존 `test_message_branching.py` 전건 +
  전체 회귀 스위트(feature-0002+0003) **2206 passed / 2 skipped / 0 failed**. §18.8 적대적 리뷰 = REV-20260722T051126-branch-hardening.
