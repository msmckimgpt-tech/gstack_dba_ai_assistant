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

## CHG-20260722T054238-conv-bind-failclosed (대화 바인딩 fail-closed 예방 하드닝)
- **배경**: 2026-07-22 HANDOFF "편집·재요청 답변 타 대화 누출" 신고 진단 결과 **실누출·재답변 실패
  없음(오진)** 확정(라이브 DB forensics + PB-0008 통제 재현 — 편집·재답변 UX·동시 in-flight 격리
  PASS, 상세 REPORT §). 조사 중 발견한 잠재 결함 중 **브랜치 체인 산란(footgun B)은 병렬 세션이
  PR #874/#875 'branch-chain-race'로 이미 main 랜딩**(runtime_backend `branch_run_active`/
  `branch_chain_*`) → 중복이라 본 cycle 미포함. 남은 **fail-closed 대화 바인딩(footgun A)만** 봉인.
- **변경**: `feature-0002 agent_core._run_agent_core` — 웹/ask 경로(`account_id` 지정)에서
  `conversation_id` 가 falsy 면 `_get_conversation_id()` 의 프로세스 전역 env(`AGENT_CONVERSATION_ID`)·
  호스트 공유 파일(`/shared/conversation_id`) 폴백을 쓰지 않고 **fail-closed**(LLM/DB 작업 이전 조기
  return + error 로그). CLI/console/eval(`account_id=None`)은 파일 폴백 유지(정당 — 단일 사용자 로컬).
- **불변식**: INV-6(fail-closed 대화 바인딩) 추가. INV-1(비분기 byte-identical) 무관·보존.
- **성격**: route/handler/RBAC/웹자산 무변경(가드 1개). never-fires 방어(정상 경로 미발동). Major(코어 격리).
- **검증**: 신규 `tests/test_conv_bind_failclosed.py` 4건(웹 None/빈문자열 차단·전역폴백 미호출·CLI
  미발동·명시 cid 통과) PASS. §18.8 적대적 리뷰 = REV-20260722T054238-conv-bind-failclosed(claim
  footgun A HOLDS — 모든 caller 안전, SHIP).

## CHG-20260724T064140-reanswer-model-select (요청사항 수정 재답변 model·추론강도 선택 반영)
- **배경**: 사용자 신고(2026-07-24) — 요청사항 수정 전 model+추론강도를 sonnet+매우높음으로 변경했으나
  재답변이 haiku+일반으로 동작. 근본원인 = reanswer 재dispatch 가 정상 `/api/ask` 와 달리 선택된
  model·reasoning 을 전달하지 않아 `ask()` 가 `API_DEFAULT_MODEL`(claude-haiku-4) + 모델 config 기본
  추론(override 없음)으로 폴백.
- **변경**:
  - feature-0003 `static/app.js` `_submitMessageEdit`: mode==="reanswer" 일 때 body 에
    `model=_composerCurrentModel()` + `reasoning_level=_composerCurrentReasoningLevel()` 추가(정상 ask
    askBody 와 동일 helper·동일 fallback chain). simple 수정은 재답변 없어 미포함 유지.
  - feature-0003 `routers/conversations.py` `post_edit_message`: reanswer 분기의 `ask_body` 에 편집
    요청 body 의 `model`(비어있지 않을 때)·`reasoning_level`(None/"" 아닐 때)을 forward. 부재 시 미포함
    → `ask()` 가 기존대로 기본값 폴백(구 클라이언트 하위호환). 형식·allowlist·reasoning 정규화는 `ask()`
    가 재검증(부재 필드를 기본값으로 강제 대입하지 않음 — reasoning override 계약 §ask 2649-2653 보존).
  - feature-0003 `routers/conversations.py` `post_edit_message`(하드닝, §18.8 적대 리뷰 MINOR
    in-cycle 수정): reanswer 재dispatch 가 `ask()` 의 **non-2xx JSONResponse**(400 — forward model
    allowlist 위반·429 쿼터)를 반환하면, 예외 경로와 동일하게 `_branch_restore_state` 로 편집 직전
    브랜치 상태 복원(기존은 `except Exception` 에만 복원 → active_leaf 가 M.parent 에 고착·tail 은닉).
    model forward 가 model-400 도달 경로를 신설했으므로 footgun 확장 방지. status>=400 은 ask() 계약상
    저장-전 게이트 실패와 1:1 대응(저장-후 실패는 200+error) → 저장된 재답변 오복원 없음.
- **성격**: 동작 수정(선택 반영)·additive + never-fires 보상 복원 하드닝. route/RBAC/스키마/마이그레이션
  무변경. 정상 ask 경로와 대칭. 1:1 reanswer 만 영향(그룹/공유는 simple 전용 — 무영향). Minor(§12.3).
- **검증**: 신규 `tests/test_message_editing_reanswer_model.py` 6건(F1 model+reasoning forward·F2 부재 시
  미포함·F3 명시 'normal' forward·F4 non-2xx→브랜치 복원·F5 2xx→미복원·S1 simple 미dispatch) PASS +
  py_compile/node --check OK + make test 회귀 0. §18.8 적대 리뷰=REV-20260724T064140(SHIP). POST-DEPLOY PB-0008.

## CHG-20260727T103000-share-edit-usable (공유 대화 메시지 텍스트 수정 상호작용 회복)
- **일시**: 2026-07-27 10:30 KST · **branch**: `ai/claude/feature-0019-share-edit-fix`
- **신고**: "공유 대화에서 사용자의 메세지 텍스트 수정에 대한 상호작용이 진행되지 않음".
- **진단(PB-0008 라이브 실측, win-browser relay · bootstrap_admin)**: 먼저 정상 경로를 **반증** —
  그룹(공유) 대화 owner 의 '수정' 버튼 렌더·인라인 편집 UI·`POST /messages/{mid}/edit` (mode=simple)
  200·내용 반영·`(편집됨)` 배지까지 전부 동작(백엔드 authz·IDOR·@assistant 잠금 게이트도 프로브로 통과
  확인: 그룹+reanswer → 400 "그룹 대화는 단순 수정만"). 실사용 불가의 원인은 **UI 기하** 2건이었다.
  - **R1**: 말풍선 폭이 content 기반이라 `_startInlineEdit` 의 `bubbleEl.innerHTML=""` 순간 원문 폭이
    소실 → 편집 창이 `.message-edit-box` min-width(240px)로 축소. 실측 **공유 661px→272px**
    (textarea 240×60px, 내용 377자) / 1:1 484→303px. `ta.rows` 도 개행 수만 세어 장문이 rows=2.
    공유 대화는 단순 수정 전용(INV-4)이라 재답변 우회로가 없어 체감 "수정 불가".
  - **R2**: user 말풍선에 `.message-actions` 가 2개 생성(☰ 메뉴 + '수정') → 동일 absolute 좌표
    (bottom:-28px; right:0)에 겹쳐 '수정'(40px)이 ☰(30px)를 완전히 덮음. hit-test 로 ☰ 중심점이
    `.message-edit-trigger` 를 반환함을 실증 → ☰ 메뉴(여기부터/여기까지 공유·분기·샘플) 클릭 불가.
- **변경**:
  - feature-0003 `static/app.js` `_startInlineEdit`: ① 편집 행 `article.message` 에 `is-editing`
    클래스 부여(폭 stretch 훅, 말풍선 클래스와 동일하게 재렌더 시 자동 소멸) ② `ta.rows` 를 개행 수와
    wrap 추정(문자수/60) 중 큰 값으로 산정(하한 3·상한 18).
  - feature-0003 `static/app.js` `renderMessages` user 편집 어포던스: 기존 `:scope > .message-actions`
    가 있으면 그 컨테이너에 `insertBefore` 로 합류(수정 좌·☰ 우), 없을 때만 신규 컨테이너 생성.
  - feature-0003 `static/styles.css`: `.message.is-user.is-editing`/`.is-assistant.is-editing`
    `align-self: stretch; width:100%` (`.is-other-message` 특이도 0,3,0 을 후행 선언으로 승) +
    `.message.is-editing .message-bubble.message-bubble-editing { width:100% }` +
    `.message-edit-box { width:100% }`.
- **성격**: 프론트 정적 자산 전용(display/기하). 백엔드·route·RBAC·스키마·마이그레이션 **무변경**,
  비파괴·additive. 1:1 편집 UI 도 동일 혜택(폭 확장·rows 보정)이며 동작 계약은 불변. Minor(§12.3).
- **검증**: 신규 `tests/test_share_edit_usable.py` 5건(F1 is-editing 부여·F2 rows wrap 추정·F3 액션
  컨테이너 합류·F4 CSS stretch·F5 edit-box width) + `node --check` OK + make test 회귀 0 +
  POST-DEPLOY PB-0008 라이브 시각검증(공유 대화 편집 폭·☰ 클릭 가능).
