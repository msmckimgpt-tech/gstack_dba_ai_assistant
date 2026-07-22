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

## REV-20260722T051126-branch-hardening [SUBAGENT:branch-hardening-security] SHIP
- Scope: 예방적 하드닝 diff — footgun A(대화 바인딩 fail-closed, `agent_core._run_agent_core`) +
  footgun B(run-scoped active-leaf, `_save_message`/`memory.save_memory_message`/`shared/config`
  contextvar). 2026-07-22 HANDOFF 누출신고 진단 후속(신고 결함=오진, 실누출 없음 확정 — 본 리뷰는
  예방 하드닝 대상).
- 적대적 검증 6축 전건 HOLDS(REFUTE 실패 = 안전):
  1. footgun A fail-closed 가 모든 caller 안전 — web inproc(conv_id 항상 비어있지 않음)·worker
     (enqueue 400 가드 선행)·eval/CLI(account_id=None → 가드 skip, 파일 폴백 유지). LLM/DB 작업 이전 배치.
  2. **run-local reset 전 경로 보장(핵심)** — 모든 caller 가 `run_agent` 래퍼 경유(직접
     `_run_agent_core` 호출 없음; web 의 `_run_agent_core` 는 `run_agent` alias), 래퍼 finally
     reset 이 예외·early-return 포함 항상 실행, 모든 message-save 는 시작 reset 이후. stale leaf 도달 불가.
  3. INV-1 — 비분기(has_branches=false)는 블록 미진입 → byte-identical(테스트 실증).
  4. core/display 별도 contextvar — 교차 사용 없음.
  5. 동시성 — inproc `to_thread` = `copy_context()` per-run 격리, worker 직렬 + 이중 reset.
  6. 신규 버그 없음(int 강제·fail-soft 무해).
- **지적사항(수정 불요, 정직 기록)**:
  - (LOW, **기존·범위 외**) `set_active_leaf`/`set_active_display_leaf` **포인터** write-race 잔존:
    본 수정은 생성 중 브랜치 전환 시 실행 답변의 *부모 체인* 산란은 봉인했으나, DB active_leaf
    *포인터* 자체는 여전히 run 이 last-writer 로 덮어써(전환 후 포인터가 run 브랜치를 가리킬 수 있음).
    footgun B 이전에도 존재한 한계이며 부모-체인 정합만 개선. **후속 항목**(별도 triage, 필요 시
    포인터 CAS/버전 가드) — 사용자-대면 질문→답변 경로엔 무영향.
  - (INFO) footgun-A early-return result 는 conversation_id 빈값·run_id 없음 — worker 경로 미발화·
    비정상 conv 해석 실패 시에만 발화하는 clean error 라 무해.
- 검증: test_branch_hardening.py 9 PASS + 전체 회귀 2206 passed/2 skipped/0 failed.
- Human Approval: [1] 예방적 하드닝 진행 승인(2026-07-22). PR·배포는 별도 confirm 대기.
