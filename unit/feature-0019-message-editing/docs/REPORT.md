---
doc_type: REPORT
feature_id: feature-0019-message-editing
status: in-progress
edit_policy: append
source_of_truth: true
---

# Report — 메시지 편집

## 2026-07-13 — Phase 1 백엔드 기반 (checkpoint 1)

**완료 (검증됨):**
- 설계·governance: FUNCTION(REQ-ME-R1~R5, AC-ME-1~9)·DESIGN(브랜치 트리·fork 재사용 검토·
  로더 전략)·ANCHOR(INV-1~5)·TASK(PLAN-APPROVED). 사용자 승인 2026-07-13.
- **마이그레이션 0041** (`20260713_0041_message_branching.py`) + `agent_runtime_schema.sql`:
  core_messages/messages 에 `parent_message_id`/`edit_root_message_id`/`edit_version`,
  core_conversations 에 `has_branches`(DEFAULT false 게이트)·`active_leaf_message_id`. 전부
  additive·constant-default → live-safe(rewrite 없음). PG-first(MySQL parity 생략 — windowed
  recall·has_restricted_members 선례 동형, MODIFY.md 참조).
- **코어 recall 로더** (`runtime_backend.py`·`agent_core._load_conversation_messages`):
  `has_branches` 게이트 → active-path recursive CTE(`_PG_LOAD_CORE_MESSAGES_BRANCH`, window 술어
  합성). **비분기 대화는 기존 쿼리 그대로(INV-1/AC-ME-2 byte-identical)**. 첫 메시지 편집
  전이(active_leaf=None)는 CTE anchor 없음=empty prior history(정확).
- **쓰기 경로**: `save_core_message` 브랜치 컬럼 additive(`_PG_INSERT_CORE_MESSAGE_BRANCH`,
  미분기는 기존 INSERT 그대로) + `_save_message` active_leaf 체이닝·전진 + 브랜치 헬퍼
  (`load_branch_state`/`enable_branches`(parent backfill)/`set_active_leaf`/`max_core_message_id`).
- **단위테스트** `test_message_branching.py` — 11 PASS: 비분기 항등성(로더·INSERT 라우팅)·
  active-path CTE·window 합성·null-leaf 엣지·게이트 상태 파싱·pre-migration fail-safe.

**reanswer 흐름 확정(설계)**: 사용자 메시지는 워커(agent_core:3664)가 저장하므로, reanswer 는
`fix-with-ai` 처럼 active_leaf=M.parent 로 두고 `/api/ask` 재dispatch → 새 user 메시지가 M 의
sibling(같은 parent)으로 체인 + 재답변. 형제 버전 그룹핑 = 공유 parent_message_id(별도 태깅 불요).

**남은 Phase 1 (다음 pass):**
- 엔드포인트(feature-0003 conversations.py): `POST /messages/{mid}/edit`(simple/reanswer)·
  `POST /branch/switch`·`GET /api/history` 확장(version_count) + 표시 store(messages) 브랜치
  헬퍼·edit authz(본인 발신·1:1·@assistant 잠금 IDOR).
- 프론트(app.js/index.html/styles.css): 편집 UI + `< n/m >` 페이징 + renderMessages 브랜치 렌더.
- 통합 테스트 + 적대적 보안 리뷰(§18.8) + verify-completion + PB-0008 시각검증 + 배포.

**위험/무회귀 근거**: 본 checkpoint 는 has_branches=false 기본 → 모든 신규 경로 dormant
(엔드포인트 부재로 has_branches 를 true 로 만드는 경로 없음). 라이브 무영향(순수 additive scaffold).

## 2026-07-13 — Phase 1 백엔드 기반 (checkpoint 2: 표시 store 쓰기 정합)

**완료 (검증됨):** 두 store(core/display) 브랜치 쓰기 대칭 완성.
- 마이그 0041 확장: `messages.core_message_id`(브랜치-헤드→core 링크, 브랜치 전환 좌표) +
  `core_conversations.active_display_leaf_message_id`(display 전용 활성 leaf). additive.
- 표시 store 쓰기(`memory.save_memory_message` + PG backend): 브랜치 대화면 `active_display_leaf`
  체이닝·전진, 미분기는 기존 INSERT(+RETURNING id) 그대로. `_PG_INSERT_MEMORY_MESSAGE_BRANCH`·
  헬퍼(`load_display_branch_state`/`set_active_display_leaf`) + `enable_branches` 가 display leaf 도 확정.
- **hot-path 무-스레딩 설계**: 정상 append 는 core_message_id 미스레딩(byte-identical) — 편집된
  원본 M 의 display→core 매핑은 user 메시지 created_at 매칭(1:1 신뢰), 브랜치-헤드 sibling 만
  엔드포인트가 exact 링크 저장. → `_mirror_message`·5 call-site 무변경(회귀 표면 최소).
- 단위테스트 +4 (표시 store 쓰기 라우팅·core 링크·display 상태) — 누계 15 PASS, 회귀 0(55 PASS).

**남은 Phase 1**: 엔드포인트(edit/branch-switch/history active-path)·프론트·통합·PB-0008.
여전히 dormant(has_branches 활성 경로 없음) — 라이브 무영향.

## 2026-07-14 — Phase 1 오케스트레이션·UI (checkpoint 3: 엔드포인트 + 프론트)

백엔드 기반(PR #766 merged) 위에 **편집 기능을 활성화**하는 HTTP 엔드포인트 + 프론트 UI 완성.
본 슬라이스로 has_branches 가 실제로 true 가 되는 경로가 생김(더 이상 dormant 아님).

**완료:**
- **엔드포인트**(feature-0003 `conversations.py`):
  - `POST /api/conversations/{cid}/messages/{mid}/edit` {mode, new_content} — simple(제자리 갱신+
    '편집됨') / reanswer(브랜치 setup → `/api/ask` 재dispatch, fix-with-ai 패턴). authz = 대화접근 +
    ask 권한 + 본인 소유(IDOR) + user 메시지 + 그룹 차단(Phase 2) + rate-limit + audit.
  - `POST /api/conversations/{cid}/branch/switch` {message_id} — 버전 페이징(양 store active_leaf 이동).
  - `GET /api/history` 확장 — has_branches 게이트로 활성 경로만 필터 + 버전 메타(version_number/
    version_count/sibling_ids) 부착. 비분기는 기존 경로(무회귀). 브랜치 대화 core fallback 차단(누출 방지).
- **브랜치 오케스트레이션 헬퍼**(`_conv_store.py`): `_branch_get_display_message`·`_branch_map_display_
  user_to_core`(링크 or created_at 매칭)·`_branch_reanswer_setup`(enable+active_leaf=M.parent)·
  `_branch_simple_edit`·`_branch_switch`(하향 CTE leaf)·`_branch_active_display_ids`·`_branch_version_groups`.
- **프론트**(`app.js`/`styles.css`): user 말풍선 '수정' 버튼(hover) → 인라인 편집 UI([단순 수정 /
  요청사항 수정 / 취소]) · `< n / m >` 버전 페이저(상시, prev/next → branch/switch) · '(편집됨)' 배지.
  `_canEditMessage` 게이트(1:1 본인 대화) — 그룹 미노출.
- **검증**: 신규 2 route ROUTEMAP·codenav 게이트 PASS + route-parity golden 갱신(207 routes) +
  make test 컨테이너 import OK(브랜치 15 + route-parity PASS). 잔여 4 실패는 pre-existing local-env
  (routine_dbanalysis·runtime_settings×2·item11_batch8 — backend-only cycle 에서도 실패, CI 통과 실증).
- §18.8 적대적 보안 리뷰(security subagent) — 결과는 REVIEW.md.

**남은 Phase 1**: 배포(마이그 0041 적용 + agent/insight-worker/web 재빌드) + PB-0008 라이브 시각검증.

## 2026-07-24 — 요청사항 수정 재답변 model·추론강도 선택 반영 (reanswer-model-select)

**신고**: 사용자가 assistant 요청사항을 수정하기 전 사용할 model + 추론 강도를 sonnet + 매우높음으로
변경해 재요청했으나, 실제로는 **haiku + 일반 추론**으로 동작.

**근본원인**: 재답변(요청사항 수정) 경로가 정상 `/api/ask` 와 비대칭. 프론트 `_submitMessageEdit` 은
`{mode, new_content}` 만 전송하고, backend `post_edit_message` 의 reanswer `ask_body` 도
`{message, conversation_id}` 만 구성 → 재dispatch 된 `ask()` 가 `model = data.get("model") or
API_DEFAULT_MODEL`(=`claude-haiku-4`), `reasoning_level = normalize(None)`(override 없음 = 모델 config
기본)로 폴백. 정상 ask 는 `state.selectedModel`(fallback chain) + `_composerCurrentReasoningLevel()`
을 실어 보내므로 선택이 반영되던 것과 대조.

**수정 (2 hunk, 정상 ask 와 대칭·additive)**:
- 프론트 `app.js` `_submitMessageEdit`: reanswer 모드에 `model=_composerCurrentModel()` +
  `reasoning_level=_composerCurrentReasoningLevel()` 추가(정상 askBody 와 동일 helper). 추론 선택기 변경은
  로컬(localStorage)만 반영되고 즉시 backend POST 하지 않으므로, KV 의존 대신 현재 선택을 명시 전송해
  faithful. simple 수정은 재답변이 없어 미포함 유지.
- 백엔드 `conversations.py` `post_edit_message`: reanswer `ask_body` 에 편집 body 의 model(비어있지
  않을 때)·reasoning_level(None/"" 아닐 때) forward. 부재 시 미포함 → `ask()` 기본 폴백 하위호환. 형식/
  allowlist/reasoning 정규화·override 계약은 전적으로 `ask()` 책임(부재 필드 강제 대입 금지 — 구
  클라이언트 sonnet config 강등 회귀 방지 계약 보존).

**검증**: 신규 단위테스트 `test_message_editing_reanswer_model.py` 4건 —
- F1 model+reasoning 제공 → ask_body 로 forward.
- F2 부재(구 클라이언트) → ask_body 미포함(기본 폴백 보존).
- F3 명시 'normal'(일반) → forward(빈값/None 만 미포함).
- S1 simple 수정 → ask 미dispatch.
+ make test 회귀 0. POST-DEPLOY PB-0008(sonnet+매우높음 선택→요청사항 수정 재답변→AI 운영 계측
resolved model=sonnet·추론예산 상향 확인).

**Risk**: Minor — 동작 수정·additive, 기존 검증된 ask 경로 재사용. 인증/스키마/파괴 없음. 1:1 reanswer
만 영향(그룹/공유 simple 전용 무영향). 웹 UI 동작 변경이라 완료 게이트에 PB-0008 포함.
