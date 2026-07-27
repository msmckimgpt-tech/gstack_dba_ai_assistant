---
doc_type: TASK
feature_id: feature-0019-message-editing
task_id: TASK-20260713T-message-editing
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task — 메시지 편집 (Message Editing)

## 1. Current Status
- State: in-progress (Phase 1 — 1:1 편집 착수)
- Owner: AI (claude) / Human (설계 승인 완료 2026-07-13)
- Priority: high
- Risk: **Major** (bordering Critical — 코어 recall 로더 변경 + 마이그레이션 + append-only
  불변식 확장. 파괴적 데이터·인증은 아니나 blast radius 큼)
- Last Updated: 2026-07-13

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - feature-0002-agent-core: `alembic/versions/*_message_branching.py`(신규),
    `src/scripts/agent_runtime_schema.sql`, `src/modules/runtime_backend.py`(로더/writer),
    `src/agent_core.py`(`_load_conversation_messages` active-path).
  - feature-0003-agent-web-ui: `src/routers/conversations.py`(edit/branch-switch/history),
    `src/routers/_conv_store.py`(브랜치 헬퍼), `src/routers/_bootstrap_schema.py`(MySQL parity),
    `src/static/{app.js,index.html,styles.css}`(편집 UI·페이징).
  - tests: `unit/feature-0002-agent-core/tests/test_message_branching*.py`(신규).
- **접근 방법:** DESIGN.md §2~§5. 대화 내부 브랜치 트리(parent_message_id + active_leaf) +
  `has_branches` 게이트 fast-path(비분기 회귀 0) + active-path recursive CTE(window 합성).
  fork 는 재사용 안 하되 cut-point·게이트 패턴 이식.
- **위험도:** Major

<!-- PLAN-APPROVED by ms.mckim.gpt (사용자) on 2026-07-13 (via /_template:entry AskUserQuestion:
     ChatGPT식 분기 / 그룹=공유·1:1=일반 / 2-phase / "Phase 1 착수" 승인) -->

## 3. Task Queue (Phase 1 — 1:1)
- [x] TASK-P1-0 요구·설계 정립(FUNCTION·DESIGN·ANCHOR, PLAN-APPROVED)
- [x] TASK-P1-1 마이그레이션 0041(core/display 브랜치 컬럼 + schema.sql) — **merged PR #766**
- [x] TASK-P1-2 코어 recall 로더 active-path CTE(has_branches 게이트 + window 합성) — merged
- [x] TASK-P1-3 쓰기 경로(core save_core_message/_save_message + display save_memory_message 체이닝) — merged
- [x] TASK-P1-4 엔드포인트 edit(simple/reanswer) + branch/switch + /api/history active-path+버전 메타
- [x] TASK-P1-5 프론트 편집 UI(수정 버튼·인라인 모드 선택) + `< n/m >` 페이징 + renderMessages 브랜치 렌더
- [x] TASK-P1-6 단위테스트(비분기 항등성·active-path·window 합성 — 백엔드 15 PASS) + ROUTEMAP/codenav 게이트
- [x] TASK-P1-7 verify-completion + 적대적 보안 리뷰(§18.8 SHIP-WITH-FIXES, 2 MAJOR 수정) + **PB-0008 라이브 PASS**
- [x] TASK-P1-8 배포(web+워커 e5f18b61, 마이그 0041 적용) + POST-DEPLOY hotfix(파라미터 캐스팅 PR #774) + 재검증 PASS

**→ Phase 1 (1:1 편집) 완결** (PR #766+#772+#774 merged·라이브 배포·PB-0008 통과).

## 4. In Progress
- Phase 2 그룹/공유 단순편집.

## 5. Blocked
- 없음

## 6. Phase 2 (그룹/공유) Task Queue
- [x] TASK-P2-1 엔드포인트 그룹 편집 허용(simple만) + @assistant 잠금 + per-message sender IDOR
- [x] TASK-P2-2 프론트 _canEditMessage 그룹 지원(본인 발신·비-@assistant) + 인라인 재답변 버튼 그룹 미노출
- [x] TASK-P2-3 서수 매핑 그룹 이벤트(__event__) 제외 — SEC #5
- [ ] TASK-P2-4 §18.8 그룹 편집 보안 리뷰 + verify + 배포 + PB-0008(그룹 대화 단순수정·잠금·미노출)

## 7. 예방적 하드닝 (TASK-20260722T054238-conv-bind-failclosed — HANDOFF 누출신고 진단 후속)
2026-07-22 "편집·재요청 답변 타 대화 누출" 신고: DB forensics + PB-0008 통제 재현으로 **실누출·재답변
실패 없음(오진)** 확정(UX·동시 in-flight 격리 PASS). 조사 중 발견한 잠재 결함 중 브랜치 체인 산란
(footgun B)은 병렬 세션이 PR #874/#875 'branch-chain-race'로 이미 랜딩 → 중복 철회. 남은 fail-closed
대화 바인딩(footgun A)만 봉인. 상세=REPORT §, MODIFY CHG-20260722T054238, DECISIONS ADR-ME-0002.
- [x] TASK-H1 진단 — 라이브 DB forensics(누출 시그니처 0, 계정 매핑 정정 1=bootstrap_admin/10=admin) + PB-0008 통제 재현 PASS
- [x] TASK-H2 footgun A — 웹/ask 경로 conversation_id falsy fail-closed(전역/공유 대화 폴백 차단, INV-6)
- [x] TASK-H3 회귀 테스트(test_conv_bind_failclosed.py 4건) + §18.8 적대적 리뷰(SHIP) + verify-completion
- [x] TASK-H4 footgun B 중복 확인(#874/#875 이미 랜딩) → 철회
- [ ] TASK-H5 PR·무중단 배포(web-a/b + ask/insight-worker 재빌드) + post-deploy 검증

## 20260724T0641-reanswer-model-select (요청사항 수정 재답변이 선택한 model·추론강도 무시 회귀 수정)
2026-07-24 사용자 신고: assistant 요청사항을 수정하기 전 model + 추론 강도를 변경(sonnet + 매우높음)
했으나, 재답변(요청사항 수정)이 **haiku + 일반 추론**으로 동작. 근본원인 = reanswer 재dispatch 경로가
정상 `/api/ask` 와 달리 선택된 model·reasoning 을 싣지 않아 `ask()` 가 `API_DEFAULT_MODEL`
(claude-haiku-4) + 모델 config 기본 추론으로 폴백. 수정 = 정상 ask 와 대칭으로 프론트가 현재 선택한
model + reasoning_level 을 edit body 에 실어 보내고 backend 가 reanswer ask_body 로 forward.
상세=REPORT §2026-07-24, MODIFY CHG-20260724T064140.
- Risk: **Minor** (동작 수정·additive·기존 검증된 ask 경로 재사용, 인증/스키마/파괴 없음. 웹 UI 동작 변경이라 완료 게이트에 PB-0008 포함)
- [x] TASK-RM-1 프론트 `_submitMessageEdit` — reanswer 모드에 `model=_composerCurrentModel()` + `reasoning_level=_composerCurrentReasoningLevel()` 추가(정상 ask 와 동일 helper, simple 은 미포함 유지)
- [x] TASK-RM-2 백엔드 `post_edit_message` — 편집 body 의 model/reasoning_level 을 reanswer ask_body 로 forward(존재 시만·부재 시 기존 기본 폴백 하위호환, ask() 가 형식·allowlist·정규화 재검증)
- [x] TASK-RM-3 단위테스트 `test_message_editing_reanswer_model.py` **6 PASS**(F1 forward·F2 부재 미포함·F3 명시 normal·F4 non-2xx→브랜치 복원·F5 2xx→미복원·S1 simple 미dispatch)
- [x] TASK-RM-3b §18.8 적대 리뷰(security+correctness) = SHIP·MINOR(non-2xx 보상 복원) in-cycle 하드닝(REV-20260724T064140)
- [ ] TASK-RM-4 make test 회귀 0 + verify-completion --pre-commit(CHECK#9 REVIEW·#13 시각검증 포함 통과)
- [ ] TASK-RM-5 commit·push·main 병합·무중단 배포 + POST-DEPLOY PB-0008(sonnet+매우높음 선택→요청사항 수정 재답변→AI 운영 계측에서 resolved model=sonnet·추론예산 상향 확인)

## 20260727T1030-share-edit-usable (공유 대화 메시지 텍스트 수정 상호작용 미동작 — 편집 창 축소 + ☰ 가림)
2026-07-27 사용자 신고: "공유 대화에서 사용자의 메세지 텍스트 수정에 대한 상호작용이 진행되지 않음".
PB-0008 라이브 실측(win-browser relay, bootstrap_admin)으로 **API·authz·저장 경로는 전부 정상**임을
먼저 반증(그룹 편집 200·내용 반영·edited 배지)한 뒤, 실사용 불가의 근본원인 2건을 계측으로 확정:
- **R1 편집 창 축소**: 말풍선 폭은 content 기반이라 `_startInlineEdit` 의 `innerHTML=""` 순간 원문 폭이
  소실되어 편집 창이 `.message-edit-box` min-width(240px)로 쪼그라든다 — **공유 대화 661px→272px**
  (textarea 240px·3행)에서 **377자**를 편집(1:1 은 484→303px). 게다가 `ta.rows` 가 개행 수만 세어
  줄바꿈 없는 장문이 rows=2 로 고정. 공유 대화는 **단순 수정 전용**(INV-4)이라 재답변 우회로도 없다.
- **R2 ☰ 메뉴 가림**: user 말풍선에 `.message-actions` 컨테이너가 2개(☰ 메뉴 + '수정') 생성되어 동일
  absolute 좌표(bottom:-28px; right:0)에 겹치고, 나중에 붙은 '수정'(40px)이 ☰(30px)를 완전히 덮어
  **☰ 메뉴가 영구 클릭 불가**(hit-test: ☰ 중심점 → `.message-edit-trigger` 반환). 공유 대화에서
  '여기부터/여기까지 공유'·분기·샘플 등록 진입이 함께 막힌다.
- Risk: **Minor** (프론트 정적 자산 전용 — app.js/styles.css. 인증·인가·스키마·백엔드 무변경, 비파괴.
  웹 UI 변경이라 완료 게이트에 PB-0008 포함, `visual_verification_scope: always`)
- [x] TASK-SE-1 라이브 실측 진단(PB-0008) — 정상 경로 반증 + R1/R2 계측 확정
- [x] TASK-SE-2 R1 수정 — `_startInlineEdit` 이 편집 행에 `is-editing` 부여 + CSS 가 편집 중 행/말풍선을
      로그 폭으로 stretch(`.message-edit-box` width:100%) + `ta.rows` wrap 추정(문자수/60) 반영
- [x] TASK-SE-3 R2 수정 — 편집 버튼을 기존 `.message-actions` 에 합류(`:scope >` 조회 후 insertBefore),
      부재 시에만 신규 컨테이너 생성(중복 absolute 컨테이너 제거)
- [x] TASK-SE-4 회귀 테스트 `test_share_edit_usable.py` 5건(F1 is-editing·F2 rows wrap·F3 컨테이너 합류·
      F4 CSS stretch·F5 edit-box width)
- [x] TASK-SE-5 make test 회귀 0(잔여 4 = pre-existing local-env) + §18.8 리뷰(codex 0.145.0, REV-20260727T103000 SHIP-WITH-FIXES · P2 1건 in-cycle 수정) + verify-completion --pre-commit **PASS**
- [x] TASK-SE-6 commit·push·PR #950·CI SUCCESS·머지(main **bb66ef16**)·`make deploy-web-only` 무중단
      롤링(soak 통과) + **POST-DEPLOY PB-0008 PASS**(13 step ok:true — actionContainers 1·☰/수정 각각
      hit-test 도달·textarea **886px**(240→)·height 165(60→)·rows 7(2→)·취소 원복). test-runs.d
      fragment POST-DEPLOY 섹션 + evidence/share-edit-usable-postdeploy.png
