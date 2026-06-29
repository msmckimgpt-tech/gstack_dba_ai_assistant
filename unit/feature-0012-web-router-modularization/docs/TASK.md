---
doc_type: TASK
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in_progress (DI seam Phase 2 진행 — cat-A 단순 require 클러스터 마이그. batch 1: 19 핸들러 byte-동치 전환 완료; batch 2+ 후속)
- Owner: AI / Human
- Priority: high (Critical 등급 — 라이브 web app 모놀리스 분할)
- Last Updated: 2026-06-29

## 2. Implementation Plan

### 2.1 Plan
- **목표**: app.py(29.5K/179 route) → 도메인 `APIRouter` 점진 분할(behavior-neutral).
- **핵심 선행 발견(2026-06-29)**: web_context 직추출은 테스트 monkeypatch 커플링(테스트가 `app._require_account` 등 module-global 을 패치하고 핸들러를 **HTTP 아닌 직접 함수호출**)에 막힌다. 추출 전 **FastAPI DI seam(`Depends(get_current_account)` + `dependency_overrides`)** 도입이 선행돼야 한다. → 사용자 결정 **A(DI 전면)** 확정. 정본 설계 = `DI_SEAM_BLUEPRINT.md`.
- **접근(개정)**: 가산적 DI seam 토대 → 클러스터별 핸들러+테스트 동반 마이그(238 인라인 인증 사이트) → helper→web_context 이동 → 도메인 router 1개/커밋 → route-parity + make test + 브라우저 QA.
- **브라우저 QA**: PB-0008 `bin/win-browser.py` 로 실 Windows Chrome 검증 **가능**(이전 "WSL 불가" 가정은 오류 — 2026-06-29 검증). 머지 전 로그인 플로우 QA 필수.
- **위험도**: Critical (라이브 web, 179 route, 라이브 인증). 안전망(route-parity)·롤백(클러스터/commit)·적대적 401/403 회귀 스위트·브라우저 QA 로 관리.

<!-- §12 APPROVED: P5b plan-eng-review(Critical, APPROVE-WITH-CONDITIONS) + 사용자 §12 승인 2026-06-25. 조건: (1)route-level 안전망 先, (2)의존성 audit. 2026-06-29: DI-seam-first 로 접근 개정(A 결정), DI_SEAM_BLUEPRINT.md = 정본 설계(적대적 비평 BLOCKING 2+HIGH/MED 5 보정 반영). -->

## 3. Task Queue
- [x] TASK-0012-1 P5b plan-eng-review(Critical) + §12 승인
- [x] TASK-0012-2 **안전망**: route-parity 스냅샷 테스트(`test_route_parity_p5b.py` + 골든 179 route) + make test green
- [x] TASK-0012-3 **의존성 audit**: 전역 98·핵심 helper `_require_account`(118 호출)·첫 타깃 keywords 의존 → web_context 경계(REPORT §audit)
- [x] TASK-0012-4 **DI seam 설계**: 6축 매핑 Workflow + 적대적 비평(BLOCKING 2+HIGH/MED 5) + grep 검증 → `DI_SEAM_BLUEPRINT.md`(정본)
- [x] TASK-0012-5 **DI seam Phase 0(가산적 토대)**: `get_conn`/`get_current_account`/`get_optional_account`/`require_permission`/`_AuthError`+handler — make test green(1205 passed/2 skip/0 fail), route-parity 179 불변, behavior-neutral
- [x] TASK-0012-6 **DI seam Phase 1(테스트 인프라 + 파일럿)**: `conftest.py`(TestClient+`as_account` fixture) + 파일럿 `GET /api/llm/health`(`Depends(get_conn)`+inline auth, byte-동치) + §18.8 이월 보정(get_conn None-yield→required 500/optional None, require_permission 빈 perms 가드) + 회귀 스위트 31(401/403/500/인자순서/auth-raise→500/mini-app deps 계약). §18.8 적대 패널(27 agents, REV-0004): HIGH-1(파일럿 get_optional_account 위임이 auth-raise 500→200 변형) + HIGH-2(인자순서 가드 부재) 적발·보정. make test 1236 passed/2 skip/0 fail, route-parity 179 불변
- [~] TASK-0012-7 DI seam Phase 2..7: 클러스터별 핸들러+테스트 동반 마이그(A 단순→B 인라인perm→C/E1 require_permission→F optional→D 동적→트랜잭션4+E2)
  - [x] **Phase 2 batch 1 (cat-A 단순 require, 19 핸들러)**: gdrive_status/disconnect, serve_avatar/role_icon/product_icon, delete_my_avatar, upload_my_avatar, auth_totp_setup/confirm/disable, list_audit_events/actors/resources, list_conversation_members/bans, ban/unban_conversation_member, delete_attachment, join_conversation_via_share → `account=Depends(get_current_account), conn=Depends(get_conn)`. ultracode workflow(72 agents) 분석+2렌즈 적대검증으로 byte-동치 확정. make test GREEN(progress-chars 1238 baseline 동일·0 fail), route-parity 179 불변, ruff clean.
  - [x] **Phase 2 batch 2 (보류 5 핸들러 마무리)**: mark_conversation_read, list_conversation_attachments, profile_llm_usage, list_conversation_shares, profile_usage_conversations. 적대검증 보류 3건(REV-0006)은 런타임 byte-동치였고 자동 edit-spec 의 orphan-try 결함만 문제 → 구조 변환기(body try+finally 동시 제거·dedent)로 올바르게 전환. list_conversation_shares 는 flush-left SQL heredoc(문자열 verbatim 보존), profile_usage_conversations 는 동반 테스트(`test_usage_conversations::test_p1`) TestClient(`as_account`) 전환 동반. make test progress-chars 1238 동일·0 fail, `_require_account` 88→64.
  - [ ] Phase 2 batch 3+: 잔여 22 cat-A(pre-auth gate 7 → account-only DI variant; multi-close 13 → 산재 conn.close 제거; ask_result 복수conn·gdrive_connect/callback 404 게이트 등 edge) + 전체 cat-A 재survey
  - [ ] Phase 3..7: cat B/C/D/E/F/트랜잭션 클러스터
- [ ] TASK-0012-8 helper→web_context 이동 + APIRouter 추출(도메인 1개/커밋) + route-parity 골든 갱신
- [ ] TASK-0012-9 브라우저 로그인 QA(win-browser.py) + §18.8 패널 + 배포
- [ ] TASK-0012-10 프론트(admin.js/app.js/styles.css) 분할 + CONVENTIONS code-modularity 규약 [별건]

## 4. In Progress
- TASK-0012-7 DI seam Phase 2 batch 1 완료(cat A 단순 require 19/~95). batch 2 진행 예정: SQL-heredoc 핸들러(list_conversation_shares) 수작업 dedent, 동반 테스트 직접호출(profile_usage_conversations) TestClient 전환, 적대검증 보류 3건 orphan-try edit 수정 후 재마이그, cat-A 잔여 클러스터.

## 5. Blocked
- 없음. (브라우저 QA env "WSL 불가" 가정은 2026-06-29 오류로 판명 — PB-0008 `bin/win-browser.py` 로 실 Windows Chrome QA 가능. 머지 전 로그인 플로우 QA 는 Final 게이트.)

## 6. Done
- P5b plan-eng-review: APPROVE-WITH-CONDITIONS (REVIEW REV-0012-0001). §12 승인.
- 안전망: `test_route_parity_p5b.py` — `app.routes` 정적 열람으로 경로·메서드·**순서**·count 를 골든(179 route)과 비교, drift 시 fail. `--no-deps` 동작. make test 회귀 0.
- 의존성 audit: 핵심 = `_require_account`(118)·`_require_permission`(7)·`_account_has_permission`(120)·`_optional_account`(2)·`_json_error` + 전역.
- **DI seam 설계(TASK-0012-4)**: 사용자 결정 A(DI 전면). 적대적 비평이 BLOCKING 2(403 메시지 60종 site-specific → `require_permission(message=)` / 트랜잭션 핸들러 22071/22190/22353/14056 오분류) + HIGH/MED 5 적발 → grep 검증 후 `DI_SEAM_BLUEPRINT.md` 보정 반영.
- **DI seam Phase 0(TASK-0012-5)**: app.py L10269~ 에 가산적 토대(`_AuthError`+`@app.exception_handler` 로 `{"error":msg}` 셰이프 보존, `get_conn` yield 의존성+autocommit rollback 안전망, `get_current_account`/`get_optional_account`/`require_permission(*perms,message=)`). 미사용 → behavior-neutral. 검증: py_compile / route-parity 179 / `_AuthError` handler 등록 / **make test 1205 passed·2 skip·0 fail**. 커밋 06d88a8, push 완료.
- **DI seam Phase 1(TASK-0012-6)**: §18.8 이월 보정(get_conn `_connect_memory` 실패 → **None yield**; required→`_AuthError("db connection failed",500)`(memory conn uniform, grep 확인) / optional→None; require_permission 빈 perms ValueError 가드) + `conftest.py`(TestClient + `make_account`/`as_account`/`as_anonymous` fixture + autouse snapshot/restore + `client_capture_errors`) + 파일럿 `GET /api/llm/health` → `Depends(get_conn)`+inline `_get_authenticated_account`(byte-동치) + `test_di_seam_p5b.py` 31 테스트. **§18.8 적대 패널(REV-20260629-0004, 27 agents/5 lens)**: HIGH-1(파일럿 최초 get_optional_account 위임이 auth-raise 500→200 변형) + HIGH-2(인자순서 가드 부재) 적발 → 파일럿 byte-동치 재전환 + 인자순서/mini-app 가드 보정. 검증: **make test 1236 passed·2 skip·0 fail**, ruff clean, route-parity 179 불변.
- **DI seam Phase 2 batch 1(TASK-0012-7, cat-A 19 핸들러)**: auth-first 단순 require 핸들러 19개를 `account=Depends(get_current_account), conn=Depends(get_conn)` 로 전환(부록 원자단위 ①인라인conn ②수동close ③`_require_account`+if error 삭제 ④시그니처). 대상: gdrive_status/disconnect, serve_avatar/role_icon/product_icon, delete_my_avatar, upload_my_avatar, auth_totp_setup/confirm/disable, list_audit_events/actors/resources, list_conversation_members/bans, ban/unban_conversation_member, delete_attachment, join_conversation_via_share. **ultracode workflow(REV-20260629-0006, 72 agents)**: 24 후보 분석 + 핸들러별 2렌즈(순서/conn수명/트랜잭션 + 에러셰이프/응답/account/부수효과) 적대검증 → 21 확정(전부 NONE)·3 보류(orphan-try edit 결함). 19 적용(list_conversation_shares 는 SQL-heredoc dedent 로 batch 2 이월, profile_usage_conversations 는 동반 테스트 전환 동반 필요로 batch 2 이월). 동반 테스트는 getsource/AST 도메인-문자열 단언이라 전환 불요(auth seam 무관 확인). 검증: 구조 변환기 + py_compile + sanity(시그니처/잔류 보일러플레이트/conn 사용) + **make test progress-chars 1238 = baseline 동일·0 fail**, route-parity 179 불변, ruff clean. `_require_account` 호출 118→99(-19). 응답 셰이프 byte-동치(미인증 401 / conn실패 500 / 본문 동일).
- **DI seam Phase 2 batch 2(TASK-0012-7, 보류 5 핸들러)**: mark_conversation_read, list_conversation_attachments, profile_llm_usage, list_conversation_shares, profile_usage_conversations 전환(누적 cat-A 24). REV-0006 적대 패널이 5건 모두 runtime byte-동치 확인했고, 3 held 는 자동 edit-spec 의 orphan-`try:`(finally 만 제거) 결함뿐 → 구조 변환기가 body `try:`+`finally:` 동시 제거·dedent 로 올바르게 전환(py_compile OK). nested-finally(`finally: try: conn.close() except: pass`) 변종 + flush-left SQL heredoc(문자열 verbatim 보존) 처리. profile_usage_conversations 동반 테스트(`test_usage_conversations::test_p1_profile_ignores_role_account`) 직접호출→TestClient(`as_account`) 전환. make test progress-chars 1238 동일·0 fail, route-parity 179, ruff clean, `_require_account` 88→64.

## 7. Next Action
- TASK-0012-7 Phase 2 batch 2: (a) list_conversation_shares — body 의 flush-left SQL heredoc 때문에 일괄 4-space dedent 불가 → 수작업 마이그(SQL 문자열 보존). (b) profile_usage_conversations — 동반 테스트(`test_usage_conversations.py::test_p1_profile_ignores_role_account`)가 `app.profile_usage_conversations(_Req(...))` 직접 호출 + monkeypatch → TestClient(`as_account`) 전환 동반. (c) 적대검증 보류 3건(mark_conversation_read/list_conversation_attachments/profile_llm_usage) — 외곽 `try:`/`finally:conn.close()` 1쌍 구조라 변환기의 orphan-try 회피용 수작업 edit. (d) cat-A 잔여(~75) batch 화.
- 변환 도구: `scratchpad/cata_transform.py`(보수적 — 정확 패턴만, SQL-heredoc·inline-close·복수conn 은 skip). batch 마다 make test progress-chars baseline 대조 + route-parity 179 게이트.
- 주의(파일럿 교훈): conn-acquire-fail 과 auth-query-raise 의 legacy 의미가 사이트별로 다를 수 있음(fail-soft vs fail-loud) — pre-auth gate(conn 생성 이전 early return) 있는 핸들러는 cat-A 부적격(401 우선순위 역전), account-only DI variant 필요.

## 8. Completion Checklist (DI seam Phase 2 batch 2 = TASK-0012-7 보류 5)
- [x] 보류 5 핸들러(mark_conversation_read/list_conversation_attachments/profile_llm_usage/list_conversation_shares/profile_usage_conversations) byte-동치 전환 — 누적 cat-A 24
- [x] behavior-neutral — make test progress-chars 1238(baseline 동일)·0 fail, route-parity 179 불변, ruff clean, py_compile OK, `_require_account` 88→64
- [x] §18.8 적대 패널 — REV-20260629-0006(workflow)이 5건 모두 runtime byte-동치 검증 완료(3 held=edit-spec only). REV-20260629-0007 에 edit-spec 수정·SQL verbatim·테스트 전환 기록
- [x] 동반 테스트 전환 — profile_usage_conversations 직접호출→TestClient(as_account); 나머지 getsource/AST 도메인 단언 무영향
- [x] TASK/REPORT/MODIFY/REVIEW 반영, BLOCKED 없음
- [ ] verify-completion PASS(9 checks) → Git 커밋 (Phase 2 batch 2)
- [ ] Git 원격 동기화: ai/* push (§16.3). PR/머지는 milestone 까지 보류.
