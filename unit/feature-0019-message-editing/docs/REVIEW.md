---
doc_type: REVIEW
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260713-0001 [SKIPPED: Phase 1 백엔드 scaffold — dormant·라이브 무영향, 적대 패널은 엔드포인트 라이브 시점 이연]
- Related Change: CHG-20260713-0001 (마이그 0041·recall 로더 active-path·쓰기 체이닝, 백엔드 기반).
- Reason: 본 checkpoint 는 순수 additive scaffold — `has_branches` DEFAULT false 이고 이를 true 로
  만드는 경로(편집 엔드포인트)가 아직 없어 **신규 브랜치 로직은 전부 dormant**(라이브 동작 무변경).
  비분기 대화는 로더·INSERT 모두 byte-identical(INV-1/AC-ME-2, 단위 11 PASS + 회귀 0). 활성 보안
  표면(edit IDOR·@assistant 잠금·공유 window 합성)은 엔드포인트가 배선되는 **Phase 1 완료 시점**에
  비로소 라이브화된다.
- Deferred to Phase 1 완료: §18.8 적대적 보안 패널(security subagent) — edit authz IDOR / 그룹
  @assistant 편집 잠금 / windowed 멤버 recall active-path 합성(가려진 구간 fail-closed) / 브랜치
  전환 권한. ANCHOR §4 외부 검증 로그에 결과 append 예정.
- Risks (현 checkpoint): 코어 로더 blast radius(모든 ask 문맥 진입점) → has_branches 게이트
  fast-path + 단위 회귀 테스트로 가드(비분기 항등성 단언). 잔여 위험 낮음(dormant).
- Human Approval: 설계·착수 승인 완료(2026-07-13, /_template:entry PLAN-APPROVED). 배포는 Phase 1
  완료·PB-0008 이후 별도.

## REV-20260713-0002 [SKIPPED: 표시 store 쓰기 정합 — dormant scaffold, 정상 append byte-identical]
- Related Change: CHG-20260713-0002 (display 브랜치 쓰기 대칭·core_message_id 링크·display 헬퍼).
- Reason: checkpoint 1 과 동일 — dormant(has_branches DEFAULT false). 정상 append 는 core_message_id
  미스레딩으로 byte-identical(hot-path call-site 무변경). 단위 15 PASS + 회귀 0(55). 활성 보안 표면은
  엔드포인트 라이브(Phase 1 완료) 시점에 발생 → §18.8 적대 패널 그때 수행(REV-0001 과 통합).
- Risks: display 쓰기 choke-point(memory.save_memory_message) 변경 → 미분기 항등 단위테스트로 가드.
- Human Approval: PLAN-APPROVED 유효(2026-07-13). 배포 별도.

## REV-20260714-0003 [SUBAGENT:message-edit-security] SHIP-WITH-FIXES
- Related Change: CHG-20260714-0004 (편집/브랜치 HTTP 엔드포인트 + 오케스트레이션, Phase 1 활성화).
- Scope: `post_edit_message`·`post_branch_switch`·`_branch_*` 헬퍼 10종·`_get_history` 브랜치 필터.
- 적대적 보안 리뷰(security subagent) — IDOR/authz/SQL 인젝션/데이터 누출/원자성 항목별 판정.
- **결함 없음 확인**: IDOR(cross-conversation mid/target 주입 — `_branch_get_display_message` 가
  `WHERE conversation_id AND id` 로 스코프, owner 게이트) · branch/switch authz · SQL 인젝션(전 값
  파라미터화, `_branch_leaf_of` table 하드코딩) · `_get_history` 콘텐츠 누출(window ∧ active-branch
  합성, 브랜치 대화 core fallback 차단).
- **MAJOR #1 [FIXED]** display→core 매핑: created_at 근접매칭이 동일-초 tie 시 무관 core 메시지를
  덮어써 display/core 발산 → **결정적 서수(ordinal) 매핑**으로 교체(`_branch_map_display_user_to_core`,
  1:1 user 메시지 strict 1:1 → exact). commit 51c79f→본 cycle.
- **MAJOR #2 [FIXED]** reanswer 2단계 비원자성: `/api/ask` 재dispatch raise 시 active_leaf 가 M.parent
  고착 → 대화 tail 소실 → **편집 직전 상태 캡처(`_branch_reanswer_setup` 반환) + 실패 시 보상 복원
  (`_branch_restore_state`)**. 엔드포인트 try/except 배선.
- **MINOR [FIXED]**: (B) 브랜치 필터/버전 메타를 `not _conversation_is_group` 로 게이트(그룹 승격 시
  비활성 버전 id 노출·타 멤버 은닉 방지) · (C) branch/switch rate-limit 추가 · (관찰) `_branch_leaf_of`
  table allowlist assert.
- **MINOR-A [수용]**: authorship 미검증은 `is_group` 영구 플래그(join 시 set·해제 불가) + 편집 PG-write
  가 PG-down 시 함께 실패 → 실전 악용 창 없음. 정본 = 소유 게이트.
- 재검증: AST OK · app import OK · route-parity(207) + 브랜치 15 = 16 PASS.
- Human Approval: PLAN-APPROVED(2026-07-13). 배포는 마이그 0041 적용 + PB-0008 후.

## REV-20260714-0004 [SKIPPED: SQL 캐스팅 hotfix — 보안 표면 무변경, PB-0008 실검증]
- Related Change: CHG-20260714-0005 (브랜치 로더 파라미터 명시 캐스팅).
- Reason: 순수 SQL 파라미터 타입 캐스팅(로직·authz·데이터 흐름·쿼리 결과 집합 무변경 — 캐스팅은
  동일 값의 타입만 명시). 신규 보안 표면 없음. §18.8 편집 보안 패널(REV-0003)의 범위 무영향.
  실검증은 PB-0008 라이브 reanswer(적발 경로와 동일).
- Human Approval: PLAN-APPROVED(2026-07-13) 유효. deploy_scope: included.

## REV-20260714-0005 [SUBAGENT:message-edit-p2-group-security] SHIP-WITH-FIXES
- Related Change: CHG-20260714-0006 (그룹/공유 단순편집).
- 적대적 보안 리뷰(security subagent — 사용량 한도로 조기 종료, 핵심 결함 지목 후 메인이 완결).
- **MAJOR [FIXED] 서수 매핑 그룹 비대칭(SEC #5)**: 그룹 join 알림이 core_messages 엔 role='user'+
  name='__event__', display 엔 role='system' 으로 저장 → role='user' 집합 불일치 → display→core
  서수 매핑이 무관 메시지 오선택·손상. 전수 조사로 __event__ 가 유일 비대칭임 확인 → core count
  에서 __event__ 제외(수정). (subagent 가 "다른 이벤트 타입 확인" 리드 제공 → 메인이 전수 검증.)
- **결함 없음 확인(메인 완결)**:
  - sender IDOR: 그룹은 meta_json.sender_account_id == actor 검증, sender 미상 시 owner fail-closed.
  - @assistant 잠금: 원본 content 로 message_invokes_assistant 판정 → 공유 답변 유발 메시지 편집 차단.
    simple 편집은 재답변 없음이라 편집으로 assistant 재호출·답변 변조 불가.
  - window 정합: sender 검증이 "본인 발신"만 허용 → 편집 대상은 항상 편집자 window 내(본인이 보낸
    메시지) → 가려진 구간 편집 불가. 콘텐츠 누출·window 우회 없음.
  - mode 강제: 그룹에서 reanswer/branch 차단(mode!='simple' → 400), 그룹 판정·disp 로드 후 순서 정합.
- Human Approval: PLAN-APPROVED(2026-07-13). deploy_scope: included.

## REV-20260722T054238-conv-bind-failclosed [SUBAGENT:branch-hardening-security] SHIP
- Related Change: CHG-20260722T054238-conv-bind-failclosed (fail-closed 대화 바인딩, footgun A).
- Scope: `agent_core._run_agent_core` fail-closed 가드(웹/ask 경로 conversation_id falsy → 전역/공유
  대화 폴백 차단). 2026-07-22 HANDOFF 누출신고 진단 후속(신고=오진, 실누출 없음 확정).
- 적대적 검증(§18.8): footgun A claim **HOLDS** — 모든 caller 안전:
  - web inproc(conv_id 항상 비어있지 않음: 기존 conv=request_conversation_id, 신규 conv=create_if_missing
    실 id, conversation.create 403 선행) · worker(enqueue 400 가드 선행) · eval/CLI(account_id=None →
    가드 skip, 파일 폴백 유지). 가드는 LLM 클라이언트·DB 연결 이전 배치 — side-effect 없음.
  - 정상 경로 미발동(never-fires) · 회귀 시 조용한 누출 대신 clean error.
- Verdict: **SHIP**(신규 결함 0). footgun B(브랜치 체인)는 PR #874/#875 로 이미 랜딩 → 본 리뷰 범위 밖.
- 검증: test_conv_bind_failclosed.py 4 PASS.
- Human Approval: [1] 예방적 하드닝 진행 + PR·무중단 배포 승인(2026-07-22, AskUserQuestion).

## REV-20260724T064140-reanswer-model-select [SUBAGENT:reanswer-model-security] SHIP
- Related Change: CHG-20260724T064140-reanswer-model-select (요청사항 수정 재답변이 선택 model·추론강도 반영).
- Scope: `static/app.js` `_submitMessageEdit`(reanswer 시 model+reasoning_level 전송) +
  `routers/conversations.py` `post_edit_message`(ask_body forward + non-2xx 보상 복원 확장).
- 적대적 검증(§18.8, security+correctness 렌즈): **신규 결함 0 (blocker/major 없음)** — verdict SHIP.
  - **보안 CLEAN**: forward 된 model/reasoning 은 편집 엔드포인트가 소비하지 않고 원문만 ask_body 에
    실어 재dispatch. `ask()` 가 정상 `/api/ask` 와 **동일 검증**을 재수행 — `_is_safe_model_name`
    (regex ≤64) + `_is_allowed_api_model`(로컬 모델 거부·allowlist) → 위반 시 **400 조기 차단**,
    `normalize_reasoning_level` 로 enum clamp. 스코프 복제로 인증 컨텍스트 동일(IDOR·권한 재검사).
    reanswer 는 `conversation.ask` 필요 = 이미 정상 ask 로 임의 allowlist 모델 사용 가능 → **권한
    상승·allowlist 우회·injection 없음**(재답변 = 정상 ask 의 부분집합).
  - **정확성 CLEAN**: `_composerCurrentModel()`/`_composerCurrentReasoningLevel()` 은 빈값 반환 안 함
    (fallback 종단 sonnet-4/normal). 부재→미forward→기본 폴백(하위호환). 정상 askBody 와 대칭.
  - **회귀 CLEAN**: forward 는 `if mode=="simple": return` 이후에만 도달, 프론트도 reanswer 에서만
    필드 설정. 그룹/공유는 non-simple 400 차단 → 무영향. simple 경로 byte-identical.
- **MINOR [FIXED in-cycle] 재답변 non-2xx 보상 복원 확장**: `_branch_reanswer_setup` 이 active_leaf 를
  M.parent 로 **커밋 이동**한 뒤 dispatch. 기존 코드는 `except Exception` 에서만 `_branch_restore_state`
  호출 → `ask()` 가 검증실패(400)·쿼터(429)를 **예외 아닌 non-2xx JSONResponse** 로 반환하면 복원 스킵
  → active_leaf 가 M.parent 에 고착(tail 은닉, **데이터 손실 아님·복원 가능**). 429 는 pre-existing 이나
  본 변경의 **model forward 가 model-400 도달 경로를 신설** → footgun 확장 방지 위해 `status>=400` 이면
  예외 경로와 동일 보상 복원하도록 확장(ask() 계약상 저장-후 실패는 200+error 라 status>=400 은 저장-전
  게이트 실패와 1:1 대응 → 저장된 재답변 오복원 없음). 리뷰어 제안 옵션 1 채택.
- **Human Approval**: PLAN-APPROVED(2026-07-13, feature-0019 상위) 유효 범위 내 Minor 후속. deploy_scope: included.
- 검증: `test_message_editing_reanswer_model.py` **6 PASS**(F1 forward·F2 부재 미포함·F3 명시 normal·F4
  non-2xx 복원·F5 2xx 미복원·S1 simple 미dispatch) + py_compile/node --check OK. POST-DEPLOY PB-0008.

## REV-20260727T103000-share-edit-usable [CODEX:share-edit-usable] SHIP-WITH-FIXES
- Related Change: CHG-20260727T103000-share-edit-usable (공유 대화 메시지 텍스트 수정 상호작용 회복).
- Source: `codex review --uncommitted` (codex-cli 0.145.0, gpt-5.6-terra, reasoning xhigh) — §18.8.1
  경량 경로. **경로 선택 근거(정직 표기)**: 본 세션은 사용자 환경 지시로 Agent(subagent) 호출이
  비활성이라 §18.8 표준 panel(ux/design) dispatch 불가 → 사용자 결정(2026-07-27 AskUserQuestion:
  "codex 업데이트 후 다시 시도")에 따라 codex 를 0.142.5→0.145.0 업그레이드 후 재실행(0.142.5 에서는
  ChatGPT 계정 모델 미지원 400 으로 2회 실패). check #9 accepted verdict (§18.4·§18.9).
- Scope: `static/app.js`(`_startInlineEdit` 폭 훅·rows 보정 / `renderMessages` 편집 버튼 컨테이너 합류)
  + `static/styles.css`(편집 중 행·말풍선 stretch) + `tests/test_share_edit_usable.py`(신규 5) +
  `unit/feature-0019-message-editing/src/scenario.share-edit-usable.json`(PB-0008) + 문서.
- Trigger: UI/버튼/레이아웃 keyword matched (§18.8 dispatch — UI·화면·레이아웃).
- Timestamp: 2026-07-27T10:30:00+09:00
- Verdict: **SHIP-WITH-FIXES** — P1(GATE) **0건**, P2 **1건 in-cycle 수정**.
- **P2 [FIXED in-cycle] POST-DEPLOY 시나리오의 false-green 위험**: `scenario.share-edit-usable.json`
  의 `eval` step 들이 수집값을 **출력만** 하고 실패를 단언하지 않아, 대상 대화가 삭제·미오픈이거나
  액션 컨테이너가 다시 2개가 되거나 textarea 폭이 240px 로 회귀해도 `win-browser.py run` 이
  `ok:true` 로 끝난다(게다가 진단 잔재로 `stop_on_fail:false` 가 붙어 있어 실패 step 도 흐름을 멈추지
  않음) → **UI 회귀를 PASS 로 기록**. 수정: (a) 모든 step 의 `stop_on_fail` override 제거(기본 true),
  (b) 대상 확정 step 이 `conv.id` 불일치·`is_group=false`·user 메시지 0·'수정' 버튼 0 에서 throw,
  (c) AC1 이 `.message-actions` 컨테이너 ≠1 / '수정'·☰ hit-test 미도달에서 throw, (d) AC2 가
  `is-editing` 미부여 / textarea ≤300px(baseline 240px 수준) / 로그 폭의 60% 미만 / rows<3 에서
  throw, (e) AC3 가 취소 후 `is-editing`·편집 박스 잔존에서 throw. 검증 시나리오가 실제 게이트로 동작.
- **보안·인가 CLEAN**: 백엔드·route·RBAC·스키마·마이그레이션 **무변경**. 편집 authz(본인 발신 IDOR·
  `conversation.ask`·그룹 mode 제한·@assistant 잠금)는 `post_edit_message` 서버 게이트가 정본이며
  본 변경은 그 게이트를 건드리지 않는다(프론트 표시 계층만). `_canEditMessage` 게이트 로직 불변 —
  버튼의 **배치 위치**만 기존 액션 컨테이너로 옮겼다(노출 조건 동일).
- **회귀 CLEAN**: `is-editing`/`message-bubble-editing` 클래스는 말풍선 재생성(renderMessages·
  refreshWorkspace) 시 자동 소멸 — 취소·저장 양 경로 모두 재렌더라 잔존 없음(AC3 가 단언). CSS 는
  `.is-other-message`(0,3,0) 대비 동일 특이도 + 후행 선언으로 승리(파일 말미 편집 블록에 배치).
  기존 액션 컨테이너가 없는 말풍선(공유 권한 없는 참가자 등)은 종전대로 신규 컨테이너 생성 — 분기
  양쪽 모두 커버.
- **잔여 관찰(비차단)**: rows 의 wrap 추정(문자수/60)은 근사치로, 실제 wrap 은 폭·글꼴에 따라 다르다.
  과대 추정 시 상한 18행에서 clamp 되고 textarea 는 `resize: vertical` 이라 사용자가 조절 가능 —
  실사용 저해 없음(정확한 auto-grow 는 별도 개선 여지, §8.1 후속 후보).
- **Human Approval Needed**: no — Minor(§12.3, 프론트 표시·기하 전용). 상위 PLAN-APPROVED
  (2026-07-13 feature-0019) 유효 범위 내 결함 수정. deploy_scope: included(FIRST_REQUEST.md 전역).
- 검증: `tests/test_share_edit_usable.py` **5 PASS** + `node --check app.js` OK + `make test` 회귀 0
  (잔여 4 = TEST.md 기록된 pre-existing local-env) + PRE 라이브 A/B 실측(textarea 240px→886px) +
  POST-DEPLOY PB-0008(assert 내장 시나리오).
