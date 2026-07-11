---
doc_type: MODIFY
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260625-0001
- Date: 2026-06-25
- Related Requirement: P5b(ITEM-P5b) 착수 선행물 — route-parity 안전망 + 의존성 audit (TASK-0012-2/3).
  plan-eng-review(Critical, APPROVE-WITH-CONDITIONS) + §12 승인의 조건 충족.
- Summary: feature-0012 추적 cycle 생성 + app.py router 분할(P5b) 회귀 안전망 구축. (1) `app.routes`
  정적 스냅샷 테스트 + 골든(179 route), (2) handler→전역/helper 의존성 audit(web_context 경계). **실제 router
  추출은 미포함**(브라우저 QA env 필요, 후속).
- Files (cross-cut — 추적은 feature-0012, 코드는 feature-0003):
  - `unit/feature-0003-agent-web-ui/tests/test_route_parity_p5b.py` (신규 — route-parity 안전망)
  - `unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json` (신규 — 골든 179 route)
  - `unit/feature-0012-web-router-modularization/docs/*` (신규 — ANCHOR/FUNCTION/TASK/REPORT/MODIFY/REVIEW/TEST)
- Impact: 런타임 무영향(테스트 1건 추가 + doc). make test 회귀 0. 안전망이 향후 router 추출의 경로·메서드·
  순서 drift 를 기계적으로 적발(plan-eng-review T1 격차 해소: 60 테스트 중 HTTP-route 레벨 ~0). **배포 불요**
  (테스트/doc 만, 이미지 무관).
- Rollback Notes: 단일 commit revert(테스트/doc only). 런타임/이미지 무변경.

## CHG-20260629-0002
- Date: 2026-06-29
- Related Requirement: P5b DI seam 선행(TASK-0012-4/5). web_context 직추출이 테스트 monkeypatch 커플링
  (테스트가 `app._require_account` 등 module-global 을 패치 + 핸들러를 HTTP 아닌 직접 함수호출 → `dependency_overrides`
  미적용)에 막힘 → 사용자 결정 A(DI 전면). FastAPI DI seam 을 추출 전에 선도입.
- Summary: (1) **설계** — 6축 매핑 Workflow + 적대적 완전성 비평(verdict needs-revision: BLOCKING 2 = 403 메시지
  60종 site-specific(`require_permission(message=)`로 보존) / 트랜잭션 핸들러 22071·22190·22353·14056 오분류; HIGH/MED 5)
  → grep 사실검증 후 `DI_SEAM_BLUEPRINT.md`(정본 설계) 작성. (2) **Phase 0(가산적 토대)** — app.py 에 `_AuthError`
  + `@app.exception_handler`({"error":msg} 셰이프 보존, HTTPException {"detail"} 회귀 차단), `get_conn`(yield
  의존성 + autocommit 미복원 시 rollback 안전망), `get_current_account`(401)/`get_optional_account`(no-raise)/
  `require_permission(*perms, message=, status_code=)`(403). 기존 helper 전부 유지, **미사용 → behavior-neutral**.
- Files (cross-cut — 추적은 feature-0012, 코드는 feature-0003):
  - `unit/feature-0003-agent-web-ui/src/app.py` (L29 import 에 `Depends` 추가; L10269~10341 auth DI seam 블록 신규)
  - `unit/feature-0012-web-router-modularization/docs/DI_SEAM_BLUEPRINT.md` (신규 — 정본 설계 + worklist)
  - `unit/feature-0012-web-router-modularization/docs/{TASK,REPORT,MODIFY}.md` (갱신)
- Impact: behavior-neutral(deps 미사용). route-parity 179 불변, `_AuthError` handler 등록 확인, **make test
  1205 passed / 2 skipped / 0 fail**. 배포 불요(런타임 경로 변화 없음, 라우터 추출/QA 는 Final).
- Rollback Notes: 단일 commit revert(app.py seam 블록 + import 1줄 + docs). 런타임/이미지 무변경.

## CHG-20260629-0003
- Date: 2026-06-29
- Related Requirement: P5b DI seam Phase 1(TASK-0012-6) — 테스트 인프라 + 첫 소비자(파일럿) 전환 +
  §18.8 이월(REV-20260629-0003) 보정. DI_SEAM_BLUEPRINT §2 Phase 1 / §4.2.
- Summary:
  (1) **§18.8 이월 보정** — get_conn 이 `_connect_memory()` 실패 시 **None 을 yield**(raise 금지) →
  소비 의존성 분기: get_current_account None→`_AuthError("db connection failed",500)`(legacy required-auth
  121 사이트 uniform byte-동치), get_optional_account None→None(graceful). require_permission 무인자 호출
  ValueError 가드(footgun). conn-failure 메시지 grep 분석 결과 memory conn 은 uniform "db connection failed"
  (PG 저장소 연결 실패는 별개 conn → 무관)임을 확인해 per-site 전략 불요.
  (2) **테스트 인프라** — `tests/conftest.py` 신규: TestClient 픽스처(base_url=localhost TrustedHost 통과 +
  lifespan 미발화로 --no-deps DB 회피) + `make_account`/`as_account`/`as_anonymous` fixture(permissions 명시,
  §3.2 보정 MEDIUM-2) + autouse override **snapshot/restore** 격리 + `client_capture_errors`(미처리예외 500 검증).
  (3) **파일럿** — `GET /api/llm/health` 를 `Depends(get_conn)` + inline `_get_authenticated_account` 로 전환.
  (적대 패널 HIGH-1) get_optional_account 위임은 인증쿼리 예외를 삼켜 legacy 의 'conn-open+auth-raise→500 전파'
  를 200 으로 바꾸므로 inline 유지 — None→200·미인증→200·auth-raise→500·인증→probe 모두 legacy byte-동치.
  (4) **회귀 스위트** — `tests/test_di_seam_p5b.py` 신규(31 테스트): get_conn/deps 단위(401/403/500/None) +
  `_get_authenticated_account(conn,request)` 인자순서 가드(패널 HIGH-2) + `_auth_error_handler` 셰이프({"error"}+
  "detail" 부재) + 파일럿 end-to-end(authed/force/미인증/conn실패/**auth-raise→500**) + auth deps 라우트 소비
  계약을 throwaway mini-app 으로 end-to-end 검증(패널 MEDIUM #6, route-parity 무영향).
- Files (cross-cut — 추적은 feature-0012, 코드는 feature-0003):
  - `unit/feature-0003-agent-web-ui/src/app.py` (get_conn/get_current_account/get_optional_account/
    require_permission/get_llm_health 5함수 수정 — DI seam 보정 + 파일럿 전환)
  - `unit/feature-0003-agent-web-ui/tests/conftest.py` (신규 — DI seam 테스트 인프라)
  - `unit/feature-0003-agent-web-ui/tests/test_di_seam_p5b.py` (신규 — DI seam 회귀 스위트 31 테스트)
  - `unit/feature-0012-web-router-modularization/docs/{TASK,REPORT,MODIFY,REVIEW}.md` (갱신)
- Impact: behavior-neutral(관측 응답 byte-동치 — 파일럿 4경로 + deps 계약 적대 검증). route-parity 179 불변,
  **make test 1236 passed / 2 skipped / 0 fail**, ruff clean. 배포 불요(런타임 응답 무변경; 라우터 추출/배포는 Final).
  잔여 수용(LOW): 파일럿 conn 보유시간이 요청 teardown 까지(§1.1 sanction; probe TTL-skip 으로 실발생 희박),
  make test bind-mount stale-.pyc(환경성).
- Rollback Notes: 단일 commit revert(app.py 5함수 + conftest/test 신규 2파일 + docs). 런타임/이미지 무변경.

## CHG-20260629-0004
- Date: 2026-06-29
- Related Requirement: P5b DI seam Phase 1(TASK-0012-6) 완료 기록 보강 — bookkeeping 전용.
- Summary:
  CHG-20260629-0003(Phase 1) 커밋 **ca66ee9** 직후 작성된 TASK.md Completion Checklist tail 2줄
  (`verify-completion PASS(9 checks) → 커밋 ca66ee9` / `ai/* push 완료 06d88a8..ca66ee9, PR·머지는
  milestone 보류`)이 미커밋으로 남아 있던 것을 cross-session resume 으로 closure. 커밋 해시는 commit
  이후에야 확정되므로 ca66ee9 본 커밋에 포함될 수 없던 post-commit 기록물.
- Files (cross-cut — 추적은 feature-0012):
  - `unit/feature-0012-web-router-modularization/docs/TASK.md` (§8 Completion Checklist 2줄 [x] 마킹)
- Impact: doc-only. 코드·런타임·이미지·테스트 무변경. route-parity·make test 영향 0.
- Rollback Notes: 단일 commit revert(TASK.md 2줄). 코드 무관.

## CHG-20260629-0005
- Date: 2026-06-29
- Related Requirement: P5b DI seam Phase 2 batch 1(TASK-0012-7) — cat-A 단순 require 핸들러 19개 DI 전환. DI_SEAM_BLUEPRINT §2 Phase 2 / §3.1 cat A / 부록 마이그 원자단위.
- Summary:
  auth-first 단순 require 핸들러 19개를 부록 원자단위(①인라인 conn 생성 try/except 삭제 ②수동 conn.close()/try-finally 삭제 ③`account, error = _require_account(request, conn)`+`if error: return error` 삭제 ④시그니처에 `account=Depends(get_current_account), conn=Depends(get_conn)` 추가)로 byte-동치 전환. conn 은 get_conn use_cache 공유로 인증 conn=핸들러 conn 동일 객체 유지.
  대상(19): gdrive_status, gdrive_disconnect, serve_avatar, serve_role_icon, serve_product_icon, delete_my_avatar, upload_my_avatar, auth_totp_setup, auth_totp_confirm, auth_totp_disable, list_audit_events, list_audit_actors, list_audit_resources, list_conversation_members, list_conversation_bans, ban_conversation_member, unban_conversation_member, delete_attachment, join_conversation_via_share.
  적대검증(REV-20260629-0006, ultracode workflow 72 agents): 24 cat-A 후보를 핸들러별 분석 + 2렌즈(렌즈A 순서/conn수명/트랜잭션, 렌즈B 에러셰이프/응답/account/부수효과) 적대 반증 → 21 확정(전부 NONE)·3 보류. byte-동치 불변식: 미인증→401 {"error":"로그인이 필요합니다."}, conn실패→500 {"error":"db connection failed"}, 본문 응답 1:1 보존(get_current_account 가 _AuthError→_auth_error_handler 로 _json_error 셰이프 동치, _get_authenticated_account 직접 호출로 LastSeenAt 부수효과 보존). serve_avatar/serve_role_icon 은 account 를 login-gate 로만 사용(본문 미참조) — Depends 가 401 게이트 유지하므로 동치.
  보류 2건 이월: list_conversation_shares(본문 flush-left SQL heredoc → 일괄 dedent 불가, batch 2 수작업), profile_usage_conversations(동반 테스트 직접호출 → batch 2 TestClient 전환 동반). 적대검증 보류 3건(mark_conversation_read/list_conversation_attachments/profile_llm_usage)은 런타임 동치이나 자동 edit-spec 의 orphan-try 결함 → batch 2 수작업.
- Files (cross-cut — 추적은 feature-0012, 코드는 feature-0003):
  - `unit/feature-0003-agent-web-ui/src/app.py` (19 핸들러 시그니처+본문 — auth/conn 보일러플레이트 제거, body dedent)
  - `unit/feature-0012-web-router-modularization/docs/{TASK,REPORT,MODIFY,REVIEW}.md` (갱신)
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean(unused account-arg 비차단), py_compile OK. `_require_account` 호출 118→99(-19). 런타임 응답 무변경 — 배포 불요(라우터 추출/배포는 Final).
- Rollback Notes: 단일 commit revert(app.py 19 핸들러 + docs). 런타임/이미지 무변경. DI seam 토대(Phase 0/1)는 불변.

## CHG-20260629-0006
- Date: 2026-06-29
- Related Requirement: P5b DI seam Phase 2 batch 2(TASK-0012-7) — REV-0006 보류 5 핸들러 마무리. 누적 cat-A 24.
- Summary:
  REV-20260629-0006(워크플로) 에서 batch 1 으로 적용 못 한 5 핸들러를 byte-동치 전환:
  mark_conversation_read, list_conversation_attachments, profile_llm_usage, list_conversation_shares, profile_usage_conversations.
  (a) 적대검증 보류 3건(mark_conversation_read/list_conversation_attachments/profile_llm_usage): 워크플로 verdict 는 runtime SAFE 였고, 반증은 오직 자동 생성 edit-spec 이 외곽 `try:` 를 남긴 채 `finally:` 만 제거해 orphan-try SyntaxError 를 내는 결함(py_compile 재현). → 구조 변환기(`cata_transform.py`)가 body `try:` 와 짝 `finally:` 를 함께 제거하고 본문을 dedent 하여 올바르게 전환. profile_llm_usage 는 `finally: try: conn.close() except: pass` nested 변종 — 변환기에 해당 형태 추가.
  (b) list_conversation_shares: 본문에 flush-left SQL heredoc(`"""\nSELECT...\n"""`) → 변환기 dedent 가 문자열 내용을 건드리지 않도록 보정(verbatim) + SQL 정렬 공백 원복(byte-exact). conn 은 _account_can_access_conversation 와 공유.
  (c) profile_usage_conversations: nested-finally 변종 전환 + 동반 테스트(`tests/test_usage_conversations.py::test_p1_profile_ignores_role_account`)가 핸들러를 직접 함수호출(`app.profile_usage_conversations(_Req(...))`) + `_require_account` monkeypatch 했으므로 → TestClient(`client.get` + `as_account(id=42)` override) 로 전환(DI 핸들러는 직접호출 불가). conn 은 auth 전용(body 는 PG) — get_conn 페이크.
- Files (cross-cut — 추적은 feature-0012, 코드는 feature-0003):
  - `unit/feature-0003-agent-web-ui/src/app.py` (5 핸들러 시그니처+본문)
  - `unit/feature-0003-agent-web-ui/tests/test_usage_conversations.py` (test_p1 TestClient 전환)
  - `unit/feature-0012-web-router-modularization/docs/{TASK,REPORT,MODIFY,REVIEW}.md`
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. `_require_account` 호출 99→80(전체 `_require_account(` 기준; exact-anchor 88→64). 누적 cat-A 24 핸들러 DI 전환. 배포 불요.
- Rollback Notes: 단일 commit revert(app.py 5 핸들러 + test 1 + docs). DI seam 토대·batch 1 불변.

## CHG-20260630-0001
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 2 batch 3(TASK-0012-7) — P2_MULTI_CLOSE 10 핸들러. 누적 cat-A 34. DI_SEAM_BLUEPRINT §2 Phase 2 / §3.1 cat A.
- Summary:
  batch3 workflow(REV-20260630-0001, 44 agents)이 잔여 22 cat-A 후보를 3패턴으로 분류+2렌즈 적대검증 → 10 확정(전부 P2_MULTI_CLOSE)·12 보류. P2 = auth-first 이나 본문에 try/finally 래퍼 없이 early-return 마다 conn.close() 가 산재한 형태.
  전환 10(use_conversation, history, history_dates, delete_conversation, delete_conversations, cancel_request, finalize_request, get_file, ask_status, me_get_system_prompt): conn-acquire 삭제 + `account,error=_require_account`+if-error 블록 삭제 + **산재한 모든 conn.close() 삭제**(get_conn finally-teardown 이 close) + 시그니처 `account=Depends(get_current_account), conn=Depends(get_conn)`. body dedent 불요(래퍼 try 부재).
  특이: ask_status 는 산재 close + terminal `try: snapshot=_build_ask_status_snapshot finally: conn.close()` 하이브리드 → conn.close 가 finally 유일 내용이라 단순 제거 시 빈 finally(IndentationError) → 수작업으로 try/finally 제거+본문 승격. history/history_dates 는 multi-line signature → 전용 변환기(`cata_p2_transform.py`) 의 sig_insert 를 multi-line 지원으로 보강.
  동반 테스트: history_dates 의 test_history_calendar_pg_routing T1(PG 라우팅)/T3(legacy MySQL)이 `app.history_dates(_DummyRequest(), ...)` 직접호출 + `_require_account` 패치 → TestClient(`client.get` + `as_account()` override) 전환. get_conn→_connect_memory(mem) 로 conn=mem 유지해 mem.cursor_calls 가드 보존. T2(history_anchor, 미마이그)는 직접호출 유지. 나머지 9 핸들러는 route-snapshot/getsource 단언으로 무영향(잔류 직접호출 0 확인).
- Files (cross-cut — 추적은 feature-0012, 코드는 feature-0003):
  - `unit/feature-0003-agent-web-ui/src/app.py` (10 핸들러)
  - `unit/feature-0003-agent-web-ui/tests/test_history_calendar_pg_routing.py` (T1/T3 TestClient 전환)
  - `unit/feature-0012-web-router-modularization/docs/{TASK,REPORT,MODIFY,REVIEW}.md`
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. `_require_account` exact-anchor 64→54(누적 -34). 배포 불요.
- 보류 12(batch 4+): pre-auth gate 10(P1 — conn 이전 404/400 early-return, Depends hoisting 시 401 우선순위 역전 → account-only variant 필요), ask_result(P3 복수 conn), history_anchor(적대 HIGH refute — 재조사).
- Rollback Notes: 단일 commit revert(app.py 10 핸들러 + test 1 + docs). DI seam 토대·batch 1/2 불변.

## CHG-20260630-0002
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 2 batch 4(TASK-0012-7) — history_anchor + Phase 2 cat-A 마무리. 누적 cat-A 35.
- Summary:
  history_anchor(P2_MULTI_CLOSE) 마이그: multi-line sig 에 Depends 삽입 + conn-acquire/auth 블록 삭제 + 산재 6 conn.close() 삭제(PG 분기의 pg.close() 는 보존). batch3 에서 history_anchor 가 보류된 유일 사유는 적대 HIGH refute 였는데, 재조사 결과 **마이그 자체는 byte-동치**(렌즈가 명시)이고 refute 는 동반 테스트 T2(test_history_anchor_returns_pg_id) 의 TestClient 전환이 누락된 것이 원인 → T2 를 직접호출에서 `client.get`+`as_account` override 로 전환해 해소(conn=mem 유지로 cursor_calls 가드 보존).
  **Phase 2 cat-A 잔여 11 = 아키텍처적 이연 확정**(router-extraction 단계 처리, DI seam 으로 byte-동치 불가):
  - pre-auth gate 10(post_group_chat_message, upload_conversation_attachment, get_attachment_metadata/download/versions, gdrive_connect/callback, me_put_system_prompt, get_audit_event, progress): conn 생성 *이전* 404/400 early-return 이 본문 첫 게이트. `Depends(get_current_account)` 는 401 을 그 게이트보다 먼저 내보내 우선순위 역전; `conn=Depends(get_conn)` 는 게이트 이전에 conn 을 eager-open 해 미설정/잘못된 입력에도 DB 연결(부수효과 회귀).
  - ask_result(long-poll): auth conn 을 long-poll 루프(최대 60s) *이전* 에 `conn.close()` 하는데 get_conn 은 요청 종료까지 conn 을 보유 → 60s idle conn 점유(풀 고갈). long-poll/SSE 핸들러는 get_conn(held-until-teardown) 설계와 근본 비호환.
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(history_anchor) + `tests/test_history_calendar_pg_routing.py`(T2 전환) + docs.
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. `_require_account` exact-anchor 54→53. 배포 불요.
- Rollback Notes: 단일 commit revert(app.py history_anchor + test T2 + docs).

## CHG-20260630-0003
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 3 cat-B batch 1(TASK-0012-7) — require+인라인 perm 6 핸들러. DI_SEAM_BLUEPRINT §1.4(require_permission), §1.6(account-only), §0(403 메시지 byte-보존).
- Summary:
  cat-B(인증 + 인라인 permission 검사) 진입. cat-B workflow(REV-20260630-0003, 67 agents)이 clean-AND 23 후보를 분석+2렌즈 적대검증 → 15 확정(REQUIRE_PERMISSION/ACCOUNT_ONLY)·8 보류. 확정 15 중 **본문에 sole-in-block conn.close()(finally/try 의 유일 내용)가 없는 6개만** batch1 적용(나머지 9 는 try/finally 제거+dedent 가 추가로 필요해 batch2 분리 — 빈 블록 IndentationError 회피).
  - **REQUIRE_PERMISSION 4**(new_conversation, admin_me, admin_permissions, admin_list_available_databases): 인증 직후 단일 정적 perm 게이트를 `account=Depends(require_permission("<perm>"[, message="<원본 403 메시지>"]))` 로 hoist. **403 메시지는 워크플로 전사가 아니라 제거되는 perm-블록의 `_json_error(...)` 에서 정규식으로 verbatim 추출**해 sig 에 삽입(byte-보존 보장); 메시지가 정확히 기본값 "권한이 없습니다." 면 message= 생략(new_conversation). require_permission 이 get_current_account 의존 → 미인증 401·conn실패 500·401≺403 순서 자동 보존. new_conversation 의 2차 검사(_account_has_product_access, resource-의존·다른 메시지)는 본문 유지.
  - **ACCOUNT_ONLY 2**(conversations, admin_list_products): 복수 perm/다른 메시지라 require_permission(단일 메시지) hoist 불가 → `account=Depends(get_current_account)` + perm 검사 전부 본문 유지(메시지 byte-보존). admin_list_products 는 변수명 `actor`(변환기 자동 감지).
  - 공통: conn-acquire/auth 블록 제거 + 산재 conn.close() 제거(get_conn teardown). 전용 변환기 `cata_b_transform.py`(변수명·스타일 자동 감지, 메시지 verbatim 추출).
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(6 핸들러) + docs. 동반 테스트 변경 0(6개 모두 HTTP-레벨/route-snapshot/source-assertion — 직접호출/패치 없음, grep 확인).
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. `_require_account` account-anchor 53→47. 배포 불요.
- Rollback Notes: 단일 commit revert(app.py 6 핸들러 + docs). DI seam 토대·이전 batch 불변.

## CHG-20260630-0004
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 3 cat-B batch 2(TASK-0012-7) — WRAP-style RP 5 핸들러. 누적 cat-B 11.
- Summary:
  cat-B 확정 15 중 WRAP-style(인증+perm 검사가 외곽 `try: ... finally: conn.close()` 안에 있는) 5 핸들러를 require_permission 으로 전환: public_share_fork, upload_product_icon, delete_product_icon, verify_audit_chain, admin_health_attachment_grants (전부 REQUIRE_PERMISSION). 변환기 WRAP 경로가 외곽 try/finally 제거 + 본문 dedent + perm-블록 hoist + 산재 conn.close 제거를 동시 처리. 403 메시지 verbatim 추출 byte-보존(예: "제품 관리 권한이 필요합니다 (product.manage).", "감사 무결성 검증 권한이 필요합니다.", "요청을 수행할 수 없습니다."). verify_audit_chain 변수명 `actor` 자동 감지.
  동반 테스트: delete_product_icon 의 test_avatar_icon_upload.py::test_a1_product_icon_delete_requires_manage 가 `app.delete_product_icon(7, _Req())` 직접호출 + `_require_account` 패치 → TestClient(`client.delete("/api/admin/products/7/icon")` + `as_account(perms={"console.access": True})`)로 전환. require_permission 은 override 안 하고 실제 _account_has_permission 검사를 타므로 product.manage 없는 계정 → 403 검증 보존. 나머지 4 는 직접호출 없음(grep 확인).
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(5 핸들러) + `tests/test_avatar_icon_upload.py`(test_a1 전환) + docs.
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. 배포 불요.
- 잔여 cat-B 확정 4(batch3): admin_llm_usage·admin_get_dashboard_prefs(본문 `try: conn.close() except: pass` defensive-close → try/except 제거 필요) + admin_list_datasources·admin_datasource_databases(AO, 본문 finally:conn.close).
- Rollback Notes: 단일 commit revert(app.py 5 + test 1 + docs). 이전 batch 불변.

## CHG-20260630-0005
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 3 cat-B batch 3(TASK-0012-7) — sole-in-block conn.close 처리. cat-B 확정 15 완결(누적 cat-B 15).
- Summary:
  cat-B 확정 15 중 본문에 sole-in-block conn.close()(제거 시 빈 블록) 가 있어 batch1/2 에서 미룬 4 핸들러 전환:
  - **admin_llm_usage, admin_get_dashboard_prefs**(RP, WRAP/FB): 외곽 try 의 finally 가 `finally: try: conn.close() except Exception: pass`(FB form) — 변환기 WRAP 경로가 FB 를 인식해 통째 제거+dedent+require_permission hoist. (이전 over-conservative 스캔이 "after try:" 로 오분류해 배제했던 것; FB 는 WRAP 이 정상 처리.)
  - **admin_list_datasources, admin_datasource_databases**(AO): 본문에 `try: <body, conn 사용> finally: conn.close()` wrapper. 변환기에 신규 `strip_conn_finally` pass 추가(본문의 finally:conn.close[FA/FB] wrapper 의 matching `try:` 를 역추적해 try+finally 제거하고 try-body 4-dedent; defensive `try: conn.close() except: pass` 통째 제거; cur.close/pg.close 는 미대상). AO 라 perm 검사(console.access + datasource.read|manage)는 본문 유지, conn 은 body 가 계속 사용(_dsr.all_datasources/resolve, cur, _list_product_datasources)하므로 conn=Depends(get_conn) 유지.
  변수명 actor 자동 감지. RP 메시지 verbatim 보존("LLM 사용량 조회 권한이 필요합니다 (운영자 전용).", "관리 콘솔 접근 권한이 필요합니다.").
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(4 핸들러) + docs. 동반 테스트 변경 0(4개 직접호출 없음, grep 확인).
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. 배포 불요. **cat-B workflow 확정 15 전부 마이그 완료.**
- Rollback Notes: 단일 commit revert(app.py 4 + docs). 이전 batch 불변.

## CHG-20260630-0006
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 3 cat-B batch 4(TASK-0012-7) — cat-B 잔여 no-flag 중 동반 테스트 전환 불요 10 핸들러. 누적 cat-B 25.
- Summary:
  cat-B 잔여 워크플로(REV-20260630-0006, 67 agents)가 no-flag 17 후보 → 14 확정/3 보류(suggestions fail-soft·admin_products_insight_coverage·admin_overview). 확정 14 중 동반 테스트 직접호출 전환이 불요한 10 적용:
  - **RP 5**(admin_accounts, admin_roles, admin_list_quotas, admin_set_role_quota, admin_set_account_quota): perm 게이트가 **OR-of-negations 형**(`if not ahp(a) or not ahp(b) [or not ahp(c)]:` = AND 의미·단일 메시지) → `require_permission("a","b"[,"c"], message="<원본>")` 로 다중 perm hoist. 변환기에 or-chain 다중 perm 인식 + 메시지 verbatim 추출 추가. admin_set_role/account_quota 는 auth-perm 사이 주석 허용(adjacency 완화).
  - **AO 5**(duplicate_conversation, remove_conversation_member, revoke_share, admin_get_system_prompt, list_profile_audit_events): 복수 perm/다른 메시지/OR/action-분기(admin_get_system_prompt: scope 별 perm 분기) → `account|actor=Depends(get_current_account)` + perm 검사 본문 유지.
  변수명 account/actor 자동 감지, WRAP/P2 스타일·sole-in-block close(strip_conn_finally) 자동 처리.
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(10 핸들러) + docs. 동반 테스트 변경 0(10개 직접호출 없음, grep 확인).
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. 배포 불요.
- batch5 분리(4, 동반 테스트 직접호출 전환 필요): admin_test_datasource·admin_product_db_insights·admin_usage_conversations(AO)·admin_archived_conversations(RP).
- Rollback Notes: 단일 commit revert(app.py 10 + docs). 이전 batch 불변.

## CHG-20260630-0007
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 3 cat-B batch 5(TASK-0012-7) — 동반 테스트 전환 동반 4 핸들러. cat-B 잔여 workflow 확정 14 완결(누적 cat-B 29).
- Summary:
  cat-B 잔여 workflow(REV-20260630-0006) 확정 14 중 동반 테스트가 핸들러 직접호출이라 전환이 필요했던 4 적용:
  - **AO 3**(admin_test_datasource[var=actor], admin_product_db_insights, admin_usage_conversations): perm 검사 본문 유지. 동반 테스트(직접 함수호출 + `_require_account`/`_account_has_permission` 패치)는 **호출에 `actor|account={...}, conn=<fake>` 명시 인자 주입**으로 전환(Depends 기본값을 직접 전달, body perm 검사가 그 account 로 실행 → 403/404/400/200 보존). admin_test_datasource 는 concurrency 테스트(asyncio.gather 병렬)라 TestClient(sync) 대신 직접 coroutine 호출 유지가 정합 — 명시 인자 방식이 적합.
  - **RP 1**(admin_archived_conversations): perm 이 require_permission 의존성으로 이동 → 직접호출은 perm 검사를 *우회*하므로 명시 인자로는 403 재현 불가. 동반 테스트(test_p1_admin_archived_requires_perm, 403 perm-gate)를 **TestClient(client.get + as_account(perms={"console.access":True}))** 로 전환 → require_permission 이 실제 _account_has_permission 검사를 타 403 보존.
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(4 핸들러) + tests/{test_datasource_test_nonblocking(4 calls), test_db_insights(4 calls), test_usage_conversations(3 calls), test_conversation_archive(1, TestClient)} + docs.
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. **cat-B 잔여 workflow 확정 14 전부 완료.** 배포 불요.
- 보류 3(batch6+ 재검토): suggestions(fail-soft 비-cat-B), admin_products_insight_coverage·admin_overview(적대 보류). cat-B preauth/longpoll ~32 = 아키텍처 이연(router-extraction).
- Rollback Notes: 단일 commit revert(app.py 4 + tests 4 + docs). 이전 batch 불변.

## CHG-20260630-0008
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 3 cat-C(TASK-0012-7) — `_require_permission` 헬퍼(RPH) 3 핸들러. DI_SEAM_BLUEPRINT §3.1 cat C.
- Summary:
  cat-C(인증+단일 perm 을 `account,error=_require_permission(request,conn,"<perm>")` 헬퍼로 처리) 3 핸들러 전환: admin_list_sample_feedback, admin_approve_sample_feedback, admin_reject_sample_feedback (전부 perm `kb.sample.curate`). `_require_permission` 은 perm-fail 시 *고정 메시지 "권한이 없습니다."* 반환 → require_permission DI 기본 메시지와 동치 → `account=Depends(require_permission("kb.sample.curate"))` 로 hoist(message= 생략). **conn=Depends(get_conn) 미추가** — 본문은 auth conn 미사용(audit 는 본문이 자체 `mconn=_connect_memory()` 재오픈, PG 작업은 _pg_connect). 전용 변환기 `cata_c_transform.py`(RPH 모드): CONN_ACQUIRE + 인증-전용 try/finally:conn.close() 블록 제거, 본문(뒤) dedent 불요.
  동반 테스트(test_sample_feedback_curation.py): perm-gate 403 3건(test_list/approve/reject_requires_permission)은 require_permission 이 의존성으로 이동해 직접호출 우회 → **TestClient+as_account(perms 없이)** 전환(core 미호출 단언 보존); happy 4건(promote/none-409/reject/list-serialize)은 직접호출에 **`account=admin` 명시 인자** 추가(require_permission 우회, 동작만 검증).
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(3 핸들러) + tests/test_sample_feedback_curation.py(7 call: 3 TestClient + 4 명시 account) + docs.
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. 배포 불요.
- cat-F 이연: public_share_view 는 `_optional_account` 가 본문 중간(share-load·404/410 게이트 *뒤*) 호출 → get_optional_account hoisting 시 LastSeenAt 세션 부수효과가 eager 화(로그인 viewer×무효 share 에서 legacy 미갱신 vs DI 갱신). 보안 민감 익명 엔드포인트라 router-extraction 단계로 이연.
- Rollback Notes: 단일 commit revert(app.py 3 + test 1 + docs). 이전 batch 불변.

## CHG-20260630-0009
- Date: 2026-06-30
- Related Requirement: P5b DI seam Phase 3 — cat-B workflow 보류분 중 동반 테스트 전환으로 회수된 2 핸들러. **Final 이전 migratable 세트 완결.**
- Summary:
  cat-B 잔여 workflow(REV-0006)가 "마이그 byte-correct 이나 동반 테스트 전환 필요"로 보류했던 admin_overview(RP)·admin_products_insight_coverage(AO) 전환:
  - **admin_overview**(RP): 단일 정적 perm console.access → `actor=Depends(require_permission("console.access", message="관리 콘솔 접근 권한이 필요합니다."))`. 동반 테스트(test_dashboard_overview.py 7 call): happy 6은 직접호출에 `actor/conn=_BenignConn()` 명시 주입(위젯 게이팅은 본문 _account_has_permission 그대로), perm-gate 403 1은 TestClient+as_account(console.access 없음 → require_permission 403).
  - **admin_products_insight_coverage**(AO): 복수 perm 다른 메시지(console.access/product.read|manage) → `account=Depends(get_current_account)` + 본문 검사 유지. 동반 테스트(test_insight_coverage_endpoint.py 5 call): AO 라 전부 직접호출에 `account/conn` 명시(_install 이 acct 반환하도록 보강; perm-gate 403도 body 검사가 account=nobody 로 실행).
- Files: app.py(2 핸들러) + tests/{test_dashboard_overview(7), test_insight_coverage_endpoint(_install+5)} + docs.
- Impact: behavior-neutral. make test progress-chars 1238 = baseline 동일·0 fail, route-parity 179 불변, ruff clean, py_compile OK. 배포 불요.
- **Final 이전 migratable 핸들러 전부 완료(누적 69).** 잔여 미전환 = 아키텍처 이연(router-extraction 단계): (1) fail-soft 3(progress·suggestions — conn/auth 실패를 200 으로 흡수해 get_current_account 의 500 raise 와 비동치; public_share_view — _optional_account 본문중간 LastSeenAt eager 부수효과). (2) preauth/longpoll/txn ~43(conn 이전 404/400 early-return·long-poll conn-hold·autocommit 토글) = cat-A preauth 와 동일 사유.
- Rollback Notes: 단일 commit revert(app.py 2 + tests 2 + docs). 이전 batch 불변.

## CHG-20260630-0010
- Date: 2026-06-30
- Related Requirement: P5b **Final 시작** — APIRouter 분할 파이프라인 확립(route-parity 인프라 + 첫 도메인 router). DI_SEAM_BLUEPRINT §2 Final.
- Summary:
  Final-planning workflow(8 agents, 적대검증) 결과 **NS-BOUND=0 도메인(인증=DI override 또는 무인증, app.* monkeypatch 의존 테스트 없음)은 web_context cascade 선행 없이 즉시 router 추출 가능**함을 확정. 첫 증분으로 (1) route-parity 인프라 적응 + (2) keywords 도메인 router 추출:
  - **route-parity 인프라**: Starlette 1.3.1 의 `include_router` 는 라우트를 app.routes 에 flatten 하지 않고 `_IncludedRouter`(path=None, 하위는 `.original_router.routes`) 컨테이너로 nest 한다. `test_route_parity_p5b.py::_build_table` 을 `_walk_routes` 재귀로 갱신 — 컨테이너(path 없음+methods 없음+routes/original_router.routes 보유)를 등록 위치에서 전개해 평탄 골든과 1:1 대조. 모든 라우트 여전히 열거(안전망 강화, 약화 아님).
  - **keywords router**: src/routers/{__init__,keywords}.py 신규. 4 stub(/api/keywords GET·POST, /api/keywords/{id} DELETE, /api/keywords/categories GET, 전부 410 stub·인증 0)을 APIRouter 로 이동, `from app import _json_error`(순환 안전: app 이 모든 정의 후 맨 끝 include_router). app.py 는 stub 제거 + `app.include_router(_keywords_router)`. 경로/메서드/순서/응답 byte-동치(원본 `*_args,**_kwargs` 시그니처의 GET·POST=422, categories·delete=410 동작 보존 — 검증: clean app.py 대조).
- Files: src/app.py(keywords stub 제거 + include_router), src/routers/__init__.py(신규), src/routers/keywords.py(신규), tests/test_route_parity_p5b.py(_walk_routes 재귀) + docs.
- Impact: behavior-neutral. make test 전체 통과·0 fail, route-parity 179 골든 불변(recursion 으로 set·order 동일), ruff clean, py_compile OK. 배포 불요(런타임 라우팅 동일).
- 후속(검증된 안전 순서): media(3 DI)→static_pages→admin-conversations→admin-usage(MIXED)→conversations(MIXED). NS-BOUND 도메인(admin/metadata wrapper 등)은 web_context 추출 선행.
- Rollback Notes: revert(app.py + routers/ 삭제 + route-parity 복원). 라우팅 동일이라 무위험.

## CHG-20260630-0011
- Date: 2026-06-30
- Related Requirement: P5b Final — NS-BOUND=0 도메인 router 추출 #2(media). **DI 핸들러 추출 + 골든 순서 갱신** 파이프라인 증명(keywords 는 stub·last-position 이라 골든 불변, media 는 실 DI 핸들러·mid→end 이동).
- Summary:
  media 도메인 3 핸들러(serve_avatar `/api/avatars/{account_id}`·serve_product_icon `/api/products/{product_id}/icon`·serve_role_icon `/api/roles/{role_id}/icon`, 전부 cat-A DI 전환 완료 — `Depends(get_current_account)`+`get_conn` 로그인 게이트)를 `src/routers/media.py` 로 이동:
  - **router**: `from app import get_current_account, get_conn, _serve_image_object`(순환 안전: app 이 모든 정의 후 맨 끝 include). 각 핸들러 원본 SQL(`SELECT {Avatar|Icon}ObjectKey FROM Web{Accounts|Products|Roles} WHERE Id=%s`)+`_serve_image_object(...,fallback_404=)` byte-동치 보존(cursor try/finally:close 포함).
  - **app.py**: 3 핸들러 본문 제거 + 맨 끝 `from routers.media import router as _media_router`+`app.include_router(_media_router)`(keywords include 앞에 배치).
  - **route-parity 골든 갱신**: media 3 라우트가 원본 위치 [45,48,53]→include 순서상 [172,173,174](끝, keywords 앞)로 이동. **set 불변(removed/added 0, 179→179)·순서만 변경**. var-vs-concrete 검토: avatars/{id}·products/{id}/icon·roles/{id}/icon 은 경쟁 concrete 라우트 0 + 끝으로 이동=가장 늦게 매칭이라 shadow 위험 없음 → 매칭 안전. route_snapshot_p5b.json 재생성(docker `_build_table`, 22±22 라인).
- Files: src/app.py(media 3 제거 + include_router), src/routers/media.py(신규), tests/route_snapshot_p5b.json(골든 순서 갱신) + docs.
- Impact: behavior-neutral. make test 전체 통과·0 fail, route-parity 179(골든=현재 일치), ruff clean, py_compile OK. 배포 불요(런타임 라우팅 동일).
- 후속: static_pages(4 무인증)→admin-conversations(1)→admin-usage(5 MIXED)→conversations(MIXED). NS-BOUND 도메인은 web_context 추출 선행.
- Rollback Notes: revert(app.py media 복원 + routers/media.py 삭제 + 골든 복원). 라우팅 동일이라 무위험.

## CHG-20260630-0012
- Date: 2026-06-30
- Related Requirement: P5b Final — NS-BOUND=0 도메인 router 추출 #3(static_pages). 무인증 정적 페이지 + 헬스 프로브 4 핸들러. **test-coupling(직접 핸들러 참조 + app.전역 monkeypatch) 보존 패턴 확립.**
- Summary:
  static_pages 도메인 4 핸들러(index `/`·admin_index `/admin`·share_page `/share/{token}`·healthz `/healthz`, 전부 무인증)를 `src/routers/static_pages.py` 로 추출:
  - **import 규약**: `import app` 후 app-소스 심볼은 전부 **호출 시 `app.X` 속성 접근**(STATIC_DIR·_HTML_NO_CACHE·FileResponse·_connect_memory·load_memory_kv). import-time 복사(`from app import`)가 아닌 동적 참조라 heavily-monkeypatched 헬퍼(_connect_memory 62×) + test 의 `app.FileResponse` 가로채기 계약 모두 보존. 순환 안전(app 정의 후 맨 끝 include). stdlib(os/logging/datetime/timezone)·fastapi(FileResponse/JSONResponse) 는 직접 import.
  - **app.py**: 4 핸들러 본문 제거(자리표시 주석) + 맨 끝 `app.include_router(_static_pages_router)`(media/keywords 앞). _HTML_NO_CACHE 상수는 app.py 유지(router 가 app._HTML_NO_CACHE 참조).
  - **test 전환(test-coupling 해소)**: `test_html_no_cache.py::test_html_routes_set_no_cache` 는 `app.index/admin_index/share_page` 를 **직접 호출** + `monkeypatch.setattr(app,"FileResponse",_Fake)` 가로채기. → Final-planning 의 NS-BOUND=0 분류가 놓친 test-coupling. router 가 `app.FileResponse` 동적 참조하므로 monkeypatch 는 그대로 유효 → 테스트는 **호출 위치만** `from routers import static_pages` + `static_pages.index()` 로 전환(검증 의미·assert 불변).
  - **route-parity 골든 갱신**: static_pages 4 라우트가 원본 위치 [5,6,7,8]→include 순서상 [168,169,170,171]로 이동. set 불변(179→179). var-vs-concrete: {var} 는 `/share/{token}` 하나뿐(share-prefix 유일·경쟁 concrete 0·끝 이동=가장 늦게 매칭) + 나머지 3(`/`·`/admin`·`/healthz`) concrete → shadow 위험 없음.
- Files: src/app.py(4 핸들러 제거 + include_router), src/routers/static_pages.py(신규), tests/test_html_no_cache.py(호출 위치 전환), tests/route_snapshot_p5b.json(골든 순서) + docs.
- Impact: behavior-neutral. make test 전체 통과·0 fail(test_html_no_cache 포함), route-parity 179, ruff clean, py_compile OK. 배포 불요(런타임 라우팅·헤더·status 동일).
- 후속: admin-conversations(1)→admin-usage(5 MIXED)→conversations(MIXED). **NS-BOUND 분류는 핸들러 직접참조 테스트도 점검 필요(이번 학습) — 추출 전 grep 으로 app.<handler> 참조 확인.**
- Rollback Notes: revert(app.py 4 복원 + routers/static_pages.py 삭제 + 테스트·골든 복원). 라우팅 동일이라 무위험.

## CHG-20260630-0013
- Date: 2026-06-30
- Related Requirement: P5b Final — NS-BOUND=0 도메인 router 추출 #4(admin_conversations). 보관 대화 감사 1 RP 핸들러. **concrete-route 끝-이동 시 var-shadow 역전 점검 패턴 확립.**
- Summary:
  admin_archived_conversations(`GET /api/admin/conversations/archived`, require_permission("conversation.archive.read.any") RP)를 `src/routers/admin_conversations.py` 로 추출:
  - **import**: DI seam(require_permission/get_conn)은 `from app import`(객체 동일성이 dependency_overrides 정합에 필요 — media 와 동일). _json_error/_ARCHIVED_CONV_LIMIT 은 monkeypatch 대상 아님(setattr grep 0). _pg_connect 는 본문 내 shared.db import 유지. 원본 PG/MySQL 이중 경로·계정 enrich·SQL·503/200 byte-동치.
  - **app.py**: 핸들러 제거 + include_router(_admin_conversations_router) (static_pages 뒤·media 앞).
  - **var-shadow 점검(중요)**: archived 는 concrete 라 끝-이동 시 *선행 var 라우트가 캡처*하면 역전 가능. 점검 결과 `/api/admin/conversations*` 라우트는 archived **단독**(`/{var}` 형제 없음) + `/api/admin/{a}/{b}` 류 광역 매처 0 → 캡처 불가. 골든 [127]→[171]. 추가 런타임 증명: 동반 테스트 test_p1_admin_archived(`client.get` perm-gate 403)가 make test 에서 GREEN(잘못된 핸들러로 라우팅됐다면 실패).
- Files: src/app.py(핸들러 제거 + include_router), src/routers/admin_conversations.py(신규), tests/route_snapshot_p5b.json(골든 순서) + docs.
- Impact: behavior-neutral. make test 전체 통과·0 fail(test_conversation_archive 포함), route-parity 179, ruff clean, py_compile OK. 배포 불요.
- 후속: admin-usage(5 MIXED: admin_usage_conversations 등 account 순수함수 인라인 perm)→conversations(MIXED). NS-BOUND 도메인은 web_context 선행.
- Rollback Notes: revert(app.py 핸들러 복원 + routers/admin_conversations.py 삭제 + 골든 복원). 라우팅 동일.

## CHG-20260630-0014
- Date: 2026-06-30
- Related Requirement: P5b Final — NS-BOUND=0 도메인 router 추출 #5(admin_usage, MIXED 2 핸들러). **대형 핸들러 verbatim 스크립트 추출 + uniform `app.X` 동적참조(helper-monkeypatch 보존) 패턴 확립.**
- Summary:
  admin_usage 도메인 2 핸들러 → `src/routers/admin_usage.py`:
  - **admin_llm_usage**(`GET /api/admin/usage`, RP console.usage.read, ~164줄 대형) + **admin_usage_conversations**(`GET /api/admin/usage/conversations`, AO get_current_account + 본문 2-perm `_account_has_permission` 검사).
  - **추출 방식**: 대형 핸들러 수기 전사 오류 방지 위해 **verbatim 스크립트 추출**(app.py 라인 슬라이스 → 정규식 rewrite). rewrite: `@app.get`→`@router.get`, 시그니처 `Depends(app.X)`, app-helper 8종(`_estimate_llm_cost_usd`·`_json_error`·`_aggregate_usage_by_role`·`_account_has_permission`·`_enrich_usage_conv_owner_meta`·`_parse_usage_conv_params`·`_query_usage_conversations`·`_usage_account_ids_for_role`) + 상수 `_USAGE_GRAN` 에 `app.` 접두(word-boundary lookbehind, 이중접두 0). `_pg_connect`(shared.db)는 bare 유지.
  - **uniform `import app`+`app.X` 규약(이유)**: 동반 테스트 test_usage_conversations 가 `app._query_usage_conversations`·`app._usage_account_ids_for_role` 를 monkeypatch → router 가 import-time 복사 아닌 `app.X` 동적참조여야 가로채기 유효. DI seam 도 `Depends(app.require_permission/get_conn/get_current_account)` — app 정본과 동일 객체라 dependency_overrides 정합.
  - **test 전환**: admin 직접호출 3건(`app.admin_usage_conversations(_Req(), account=actor, conn=_Conn())` perm-gate 403 ×2 + 시스템역할 빈목록 ×1) → `from routers import admin_usage` + `admin_usage.admin_usage_conversations(...)`. 헬퍼 단위테스트(Q1-Q4 `app._query_usage_conversations`, 헬퍼는 app.py 잔류)·profile 핸들러(미추출) 무변.
  - **route-parity**: set 불변(179). admin/usage* 2 concrete(var 형제 0) + `/api/admin/{var}` 1-seg matcher 0 → shadow 없음. 골든 끝-이동 재생성.
- Files: src/app.py(2 핸들러 제거 + include_router), src/routers/admin_usage.py(신규 207줄), tests/test_usage_conversations.py(import + 직접호출 3 전환), tests/route_snapshot_p5b.json(골든) + docs.
- Impact: behavior-neutral. make test 전체 통과·0 fail(test_usage_conversations 전체 GREEN), route-parity 179, ruff clean, py_compile OK. 배포 불요.
- 후속: conversations(MIXED). NS-BOUND 도메인(admin/metadata wrapper 등)은 web_context 선행.
- Rollback Notes: revert(app.py 2 핸들러 복원 + routers/admin_usage.py 삭제 + 테스트·골든 복원). 라우팅 동일.

## CHG-20260630-0015
- Date: 2026-06-30
- Related Requirement: P5b Final — **web_context.py 추출 시작(원래 막혔던 핵심 리팩터)**. TASK-0012-8 helper→web_context 이동. leaf-first 안전 증분 #1.
- Summary:
  과거 web_context 직추출은 helper cross-call 네임스페이스 재해석(monkeypatch 빗나감)으로 실패했었다. ultracode workflow(p5b-web-context-strategy, 10 agents: 3 전략 설계 + 6 적대 stress(test-breakage/binding-circular 렌즈) + 1 합성)로 3 전략을 판정 → **Strategy B(clean-leaf-move) 채택**:
  - **A(re-export shim)**: 양 렌즈 `broken` — web_context 가 late-defined DI 심볼(get_conn L10284 등)을 from app import 하면 partial-module ImportError + 추출가치 0.
  - **C(full move+_connect_memory)**: `broken` — web_context 가 app 을 import 해 app↔web_context 양방향 cycle 인위 생성; _connect_memory 는 62× monkeypatch hotspot(최후 이동 대상).
  - **B**: 양 렌즈 `safe` — app-internal callee 0 인 순수 stdlib leaf 만 이동 → web_context 가 `from app import`-free → 단방향 app→web_context edge → 순환 불가 + 테스트 참조 0 → 무파손.
  - **실행(증분 #1)**: `_sanitize_session_id`(re) + `_hash_session_token`(hashlib) 2 leaf 를 `src/web_context.py`(신규, stdlib-only, INVARIANT: from app import 금지)로 물리 이동. app.py 는 상단(L57)에서 `from web_context import _sanitize_session_id, _hash_session_token` 재가져와 모듈 전역 rebind → app 내 8 호출부(bare name) + 테스트 `monkeypatch.setattr(app,...)` 모두 보존(behavior-neutral). ruff select=["E9","F63","F7","F82"] 라 F401/E402 미검사(noqa 불요).
- Files: src/web_context.py(신규), src/app.py(2 def 제거 + 상단 re-import) + docs.
- Impact: behavior-neutral. make test 전체 통과·0 fail·route drift 0·"All checks passed!", route-parity 179, py_compile OK. docker 에서 `app._sanitize_session_id is web_context._sanitize_session_id`(rebind 동일객체) + 순환 import 없음 검증. 배포 불요.
- 후속 시퀀스(합성 권고, 안전 영역=테스트 0변경): inc2 `_get_client_ip`+proxy companions(_is_trusted_proxy/_parse_trusted_proxies/_TrustedNetwork/WEB_TRUSTED_PROXIES) → inc3 SESSION_COOKIE+_resolve_permission_catalog+PERMISSION_* 상수(web_context 가 canonical 홈, app re-import) → inc4 _fetch_account_rows/_decorate_account_rows. 그 후부터 _account_has_permission(11×)·_require_account(51×)·_connect_memory(62×) = 23-테스트 retarget 필요 영역.
- Rollback Notes: revert(web_context.py 삭제 + app.py 2 def 복원 + re-import 제거). 단방향 edge라 무위험.

## CHG-20260630-0016
- Date: 2026-06-30
- Related Requirement: P5b Final — web_context 추출 증분 #2(proxy/client-IP leaf cluster). TASK-0012-8.
- Summary:
  합성 권고 안전-시퀀스 inc2: proxy/client-IP 5종을 `src/web_context.py` 로 이동:
  - `_TrustedNetwork`(type alias) · `_parse_trusted_proxies` · `WEB_TRUSTED_PROXIES`(모듈상수) · `_is_trusted_proxy` · `_get_client_ip`.
  - **AGENT_MODE 결합 해소(app-free 유지)**: `_parse_trusted_proxies` 가 prod/staging invalid-CIDR fail-loud 에 app 전역 `AGENT_MODE` 를 참조 → web_context 에 동일 표현식 env-mirror `AGENT_MODE = os.getenv("AGENT_MODE","").strip().lower()`(app L82 동일) 보유. 함수 시그니처 불변(byte-faithful). `_is_trusted_proxy` 가 읽는 `WEB_TRUSTED_PROXIES` 도 함께 이동 → web_context 가 canonical(단방향 edge 유지, back-ref 0).
  - **startup-validation 블록은 app 잔류**: `if not WEB_TRUSTED_PROXIES and ENABLE_WEB_TLS_PROXY=1 → prod/staging RuntimeError`(L1150 부근)은 app startup 로직이라 app 에 유지, 재import된 WEB_TRUSTED_PROXIES + app 의 AGENT_MODE 참조.
  - app.py 상단 re-import 에 5종 추가(rebind). WEB_TRUSTED_PROXIES 계산 시점이 app L1172 → web_context import(app 상단 re-import) 로 이동 — 둘 다 startup-time, prod/staging fail-loud 보존.
- Files: src/web_context.py(5종 + AGENT_MODE env-mirror + ipaddress/os/sys/fastapi.Request import 추가), src/app.py(5종 제거 + re-import 확장, startup-block 잔류) + docs.
- Impact: behavior-neutral. make test 전체 통과·0 fail·route drift 0, route-parity 179, py_compile OK. docker: rebind-identity 7/7 + 순환 없음 + WEB_TRUSTED_PROXIES(172.18.0.0/16 env 계산) + _get_client_ip 동작 확인. 테스트 참조 0(검증). 배포 불요.
- 관측 차이(무시 가능): _parse_trusted_proxies 의 warning print 는 file=sys.stderr 동일. logger 미사용(print). startup RuntimeError 메시지·timing 동일.
- 후속: inc3 SESSION_COOKIE+_resolve_permission_catalog+PERMISSION_* → inc4 _fetch/_decorate_account_rows. 그 후 _account_has_permission(11×)/_require_account(51×)/_connect_memory(62×)=23-테스트 retarget 영역.
- Rollback Notes: revert(web_context.py 5종+AGENT_MODE 제거 + app.py 5종 복원 + re-import 축소). 단방향 edge라 무위험.

## CHG-20260630-0017
- Date: 2026-06-30
- Related Requirement: P5b Final ship 준비 — origin/main(100 commits drift) 통합. 배포 선결(내 브랜치만 배포 시 main 신규 기능 롤백 위험).
- Summary:
  feature-0012 가 origin/main 대비 100 behind / 21 ahead 로 큰 base drift. main 은 머지베이스 이후 app.py 를 +720/-65 변경했으나 **전부 additive(신규 라우트 9: /livez·/readyz·glossary-feedback CRUD·glossary relations·metadata graph 등) — 내가 DI 전환/추출/web_context 이동한 auth helper 는 전혀 건드리지 않음**(grep 확인, auth-orthogonal). `git merge origin/main`:
  - app.py: **충돌 없이 auto-merge**(main 추가 영역 ↔ 내 편집 영역 분리). 검증: py_compile OK + 내 마커(web_context re-import + include_router ×5) 생존 + main 신규 라우트 4종 존재 + **중복 라우트 데코 0** + 추출 핸들러 app.py 재등장 0.
  - test_sample_feedback_curation.py: auto-merge(make test 통과로 정합 확인).
  - route_snapshot_p5b.json: 유일 충돌(양쪽 수정) → 머지된 앱에서 골든 재생성(179 → **188**, main 신규 9 반영)으로 해소.
- Files: 머지 커밋(app.py·test_sample_feedback_curation.py auto-merge + route_snapshot 재생성 + main 100 commits) + docs.
- Impact: behavior-neutral(내 리팩터 측). make test 전체 통과·0 fail·route drift 0·route-parity 188. main 신규 기능 + 내 분할 공존.
- Rollback Notes: 머지 커밋 revert(`git revert -m 1`) 또는 머지 전 21-commit 상태로 reset.

## CHG-20260630-0018
- Date: 2026-06-30
- Related Requirement: P5b Final §18.8 ship-gate 패널(REV-0017 GO) 후속 — 확정 low/info finding 정정(주석 정확도). 동작 무변.
- Summary:
  §18.8 적대 패널(14 agents, ship 판정 GO·blocking 0)이 확정한 비차단 finding 정정:
  - **[low] WEB_TRUSTED_PROXIES fail-loud 순서 주석 정정**: web_context 추출로 WEB_TRUSTED_PROXIES invalid-CIDR RuntimeError 가 import 시점(app L61, audit-prod gate 보다 앞)에 발화 — main 에서는 audit gate 뒤(L1225)였음. prod+audit-off+invalid-CIDR 이중-오설정 시 *먼저 발화하는 에러*만 다름(둘 다 fail-loud·보안 동일, S8 테스트 무회귀). 단방향 edge 유지상 WEB_TRUSTED_PROXIES 가 web_context import 계산되는 것은 클린 추출의 불가피한 귀결(app 으로 옮기면 back-ref). → app.py L60/L1210·web_context 의 "원래 startup-time 과 동일" 문구를 "import 시점(audit gate 보다 앞) 계산, 이중-오설정 시 첫 에러만 상이" 로 정정.
  - **[info] stale line-number**: web_context.py:22 "app.py(L82)" → 실제 L91 정정.
- Files: src/app.py(주석 3곳), src/web_context.py(주석 1곳) + docs. **코드 라인 변경 0(주석-only, diff 검증).**
- Impact: behavior-neutral(주석만). py_compile OK. make test 는 §18.8 가 동일 코드 상태(머지본)로 575 passed/0 fail·route-parity 188 검증 완료. 배포 불요(주석).
- Rollback Notes: revert(주석 복원). 무위험.

## CHG-20260701-0001
- Date: 2026-07-01
- Related Requirement: P5b Final 배포 hotfix — 컨테이너 로드(uvicorn web.app:app) 시 추출 모듈 import 실패 수정. **blue-green healthz 게이트가 배포 중 적발(web-b OLD 서빙 유지 → 프로덕션 무영향).**
- Summary:
  프로덕션 배포 시 web-a(신이미지)가 crash-loop: `/app/web/app.py:63 from web_context import → ModuleNotFoundError`. 근본 원인 = **테스트 하네스와 컨테이너의 모듈 로드 방식 불일치**:
  - 컨테이너: `uvicorn web.app:app`(WORKDIR /app, sys.path[0]='' → /app). app.py = 모듈 `web.app`, sys.path 에 /app 만 → 내가 추출한 top-level import(`from web_context import`·`from routers.X import`·routers 의 `from app import`)가 전부 실패(/app/web 미포함).
  - 테스트: `make test`(PYTHONPATH=.../src) → app·web_context·routers 전부 top-level → 통과. **→ make test·§18.8 패널이 이 클래스를 못 잡음(둘 다 test PYTHONPATH 사용).**
  - 이 저장소는 **modules 패키지가 둘**: `modules.X`=feature-0002 core(/app/modules, memory·render 등), `web.modules.X`=feature-0003 web(/app/web/modules, attachment_pg_mirror·storage_minio 등; app.py 가 이미 `from web.modules import` 로 사용). 즉 컨테이너는 app 을 `web` 패키지로 로드하는 게 정본 컨벤션.
  - **수정(app.py 상단, load-style 무관 robust)**: 본 파일 디렉토리를 sys.path 에 **append**(insert(0) 아님 — /app/web/modules[web] 가 /app/modules[core] 를 shadow 해 `modules.memory` 깨짐; append 라 ''=/app 의 core modules 우선) + 현재 모듈을 `app` 으로 `sys.modules.setdefault` alias(web.app 인스턴스를 routers 의 `from app import` 가 그대로 참조 → 모듈 중복 로드/재실행 방지). `from web.modules import` 무영향.
- Files: src/app.py(상단 sys.path append + app alias 블록) + docs.
- Impact: 컨테이너 실기동 검증(mysql-ai-web:24dd588 + 수정 app.py 마운트, `uvicorn web.app:app`): Application startup complete·healthz git_commit=24dd588·/api/session 200 authenticated:false·추출 라우트(/api/avatars/1 media·/api/admin/usage admin_usage) 정상 라우팅+DI seam 500 byte-동치. make test 575 passed/0 fail·route drift 0·route-parity 188. py_compile OK.
- 후속(test-gap): make test/CI 에 **컨테이너-스타일 로드(web.app 패키지) import smoke** 추가 권장(현 하네스가 못 잡는 클래스). 배포 healthz 게이트가 최종 안전망.
- Rollback Notes: revert(app.py 상단 블록). 배포는 web-b OLD 유지로 무영향이었음.

## CHG-20260701-0002
- Date: 2026-07-01
- Related Requirement: P5b Final router 추출 #6 — conversations 도메인(대화 조작 10 핸들러). 모놀리스 축소 재개(사용자 "자율 우선순위 순차 진행").
- Summary:
  잔존 169 라우트 분류(스크립트) → 완전-DI(inline=0) 도메인이 즉시 추출 1순위 확정. 그중 **동반 테스트 직접참조 0**인 conversation-operations 10 핸들러(new_conversation RP + use_conversation·history·history_anchor·history_dates·delete_conversation·delete_conversations·cancel_request·finalize_request·ask_status AO) → `src/routers/conversations.py`(신규 550줄):
  - **AST 기반 경계 추출**: 초기 정규식 line-range 는 multi-line 시그니처(history 등 def 가 8줄)를 못 잡아 SyntaxError → `ast.FunctionDef.decorator_list[0].lineno..end_lineno` 로 정확 추출(512 src 줄).
  - **rewrite whitelist 도출**: 블록 토큰 ∩ app top-level 심볼(722) − 핸들러명 − 키워드/파라미터 → `_`헬퍼 17 + DI seam 3(get_conn·get_current_account·require_permission) 을 `app.X` 동적참조로. `progress`(로컬 변수 충돌 위험) 등 non-_ 제외.
  - **stdlib import 보강(학습)**: 추출 핸들러가 `os`·`logging` 사용(app.py top-level 이라 있었음, app.X 는 app-심볼만 커버) → router 에 명시 import. make test 가 `NameError: os` 로 적발 → 보강.
  - app.py: 10 블록 제거(placeholder) + include_router(_conversations_router).
- Files: src/routers/conversations.py(신규), src/app.py(10 핸들러 제거 + include_router), tests/route_snapshot_p5b.json(골든 끝-이동) + docs.
- Impact: **app.py 29,111 → 28,610 줄(~500 감소).** make test 전체 통과·0 fail·route drift 0, route-parity 188(set 불변), py_compile OK. behavior-neutral(byte-동치, byte 그대로 슬라이스 + app.X/stdlib import 만).
- 학습: 추출 router 는 (1) app-심볼=app.X 동적참조(monkeypatch 보존), (2) **핸들러가 쓰는 stdlib=명시 import 필요**, (3) 경계는 AST(multi-line sig). make test 가 stdlib 누락 안전망.
- Rollback Notes: revert(conversations.py 삭제 + app.py 10 복원 + include_router/골든 복원).

## CHG-20260701-0003
- Date: 2026-07-01
- Related Requirement: P5b Final router 추출 #7 — admin_quotas(3) + admin_sample_feedback(3) 완전-DI RP 도메인.
- Summary:
  완전-DI 도메인 2개 추출(AST 경계): admin_quotas(admin_list_quotas·admin_set_role_quota·admin_set_account_quota → src/routers/admin_quotas.py) + admin_sample_feedback(admin_list/approve/reject_sample_feedback → src/routers/admin_sample_feedback.py).
  - app.X rewrite: `_`헬퍼 + DI seam + **non-_ app 헬퍼(record_audit_event)** 접두(← 학습: `_`만 접두하면 record_audit_event 같은 non-_ 헬퍼 누락 → NameError; make test 적발). stdlib(logging) 명시 import.
  - 동반 테스트 전환: test_llm_usage_quota.py(getsource 2 + hasattr 루프 1 → admin_quotas.X; `_import_app()` 헬퍼 패턴이라 module-level `from routers import admin_quotas` 추가), test_sample_feedback_curation.py(직접호출 4 → admin_sample_feedback.X + import).
- Files: src/routers/{admin_quotas,admin_sample_feedback}.py(신규), src/app.py(6 핸들러 제거 + include_router), tests/{test_llm_usage_quota,test_sample_feedback_curation}.py(전환), tests/route_snapshot_p5b.json(골든) + docs.
- Impact: **app.py 28,610 → 28,350 줄(~260↓).** make test 전체 통과·0 fail·route drift 0, route-parity 188(set 불변), py_compile OK. behavior-neutral.
- 학습: app.X whitelist 는 **non-_ app 함수(record_audit_event 등)도 포함** 필요(도출 시 `_`한정하면 누락). 테스트 전환은 getsource/hasattr/직접호출/`_import_app` 헬퍼 등 모든 참조 스타일 처리. make test 가 누락 안전망.
- Rollback Notes: revert(2 router 삭제 + app.py 6 복원 + 테스트·골든 복원).

## CHG-20260701-0004
- Date: 2026-07-01
- Related Requirement: P5b Final router 추출 #8(batch 3) — admin_console 도메인 5 완전-DI 핸들러.
- Summary:
  관리 콘솔 메타 5 핸들러(admin_me·admin_permissions·admin_list_available_databases·admin_overview·admin_health_attachment_grants, require_permission RP) → `src/routers/admin_console.py`(AST 경계). app.X rewrite(`_`헬퍼/상수 19 + DI seam; non-_ 함수 없음), stdlib `import logging`+`from datetime import datetime`(admin_health 의 datetime.utcnow — 클래스라 from-import). 동반 테스트: test_llm_usage_quota(getsource app.admin_me→admin_console) + test_dashboard_overview(직접호출 6 app.admin_overview→admin_console + import).
  - 골든 188→**192**: main feature-0016 이 graph/analyze 4 라우트 추가(내 추출 무관, removed=[]로 admin_console 5 라우트 set-보존) → 골든 재생성으로 흡수.
- Files: src/routers/admin_console.py(신규), src/app.py(5 제거 + include_router), tests/{test_llm_usage_quota,test_dashboard_overview}.py(전환), tests/route_snapshot_p5b.json(골든 192) + docs.
- Impact: **app.py 28,559→28,410 줄.** make test 전체 통과·0 fail·route drift 0, route-parity 192, py_compile OK. behavior-neutral.
- 학습: datetime 은 사용 형태 확인 필요(datetime.utcnow=클래스→`from datetime import datetime`, module 아님). main 신규 라우트로 골든 set 변경 시 무조건 재생성(내 추출은 removed=[] 로 set-neutral 확인 후).
- Rollback: revert(admin_console.py 삭제 + app.py 5 복원 + 테스트·골든 복원).

## CHG-20260701-0005
- Date: 2026-07-01
- Related Requirement: P5b Final router 추출 #9(batch 4) — 완전-DI misc(share 2 + system 2). **완전-DI 라우트 전부 추출 마일스톤.**
- Summary:
  마지막 완전-DI 도메인 추출(AST 경계): share.py(revoke_share·join_conversation_via_share) + system.py(get_llm_health·get_file). app.X 동적참조(app 헬퍼 + DI seam), stdlib(logging)·from datetime import 필요분. get_llm_health 은 DI 파일럿(본문 _get_authenticated_account inline 유지 → app._get_authenticated_account).
  - **소스텍스트 contract 테스트 전환(4번째 커플링 유형 학습)**: test_member_ban_endpoints(`_func_src` AST 파싱이 app.py 만 → app.py + src/routers/*.py 검색) + test_group_conversation_s2(`@app.post(...)` in APP 텍스트 → APP_ALL=app.py+routers 통합 + `@router.post` 허용). `app.<handler>` grep 이 못 잡는 유형(app.py 소스를 read_text/ast.parse 해 핸들러명 검색).
- Files: src/routers/{share,system}.py(신규), src/app.py(4 제거 + include_router), tests/{test_member_ban_endpoints,test_group_conversation_s2}.py(소스텍스트 검색을 routers 포함으로), tests/route_snapshot_p5b.json(골든 192 불변·재생성) + docs.
- Impact: **app.py 28,410→28,221 줄.** make test 전체 통과·0 fail·route drift 0, route-parity 192, py_compile OK. behavior-neutral. **완전-DI(inline=0) 라우트 전부 추출 완료(11 router).**
- 학습: 추출 커플링 4유형 = (1) `app.<handler>` 직접호출, (2) `monkeypatch.setattr(app,...)`, (3) `getsource(app.<handler>)` attribute, (4) **app.py 소스 read_text/ast.parse 후 핸들러명 검색(contract 테스트)**. 추출 전 grep: `app\.<handler>` + 핸들러명이 등장하는 소스-읽기 테스트.
- Rollback: revert(share.py·system.py 삭제 + app.py 4 복원 + 테스트·골든 복원).

## CHG-20260701-0006
- Date: 2026-07-01
- Related Requirement: P5b inline-heavy DI 전환 재개 — **admin/metadata 도메인 33 핸들러** DI seam byte-동치 전환(추출 선행). 원래 블로커(monkeypatch 커플링)의 핵심 잔여.
- Summary:
  admin/metadata 33 핸들러의 도메인 전용 인라인 auth helper(`_metadata_resolve_account`/`_samples_resolve_account`/`_metadata_resolve_account_perm(request,"<lit>")`) → `account=Depends(require_permission("<perm>"))` byte-동치 전환. perm 매핑: kb.ingest.manual 27(glossary/enum/relations/tables/columns/graph/bootstrap) + kb.glossary.curate 3(glossary-feedback) + kb.sample.curate 3(samples). **결정적 AST 변환기**(`metadata_di_transform.py`): 첫 본문 auth-resolve 3줄(account,error=.../if error:/return error) 제거 + 시그니처 param 주입.
  - **핵심 발견**: admin/metadata 의 txn(autocommit 토글 17)은 **독립 `_pg_connect(autocommit=False)`**(PostgreSQL) — get_conn 의 memory conn(MySQL)과 별개 DB/드라이버라 무간섭 → **txn 이연 사유 미적용**(원래 이연 대상으로 분류됐으나 실측 clean). auth 는 memory conn(short-lived) 경유로 legacy 와 동일 `_get_authenticated_account` 세션 부수효과.
  - **이연 1**: `admin_metadata_suggest`(`/{sub}/suggest`) — auth 이전 pre-auth 404 gate(sub 미인식) + 동적 perm(`_METADATA_SUBTAB_PERM_SERVER`) → DI hoisting 시 404→401/403 순서 역전 → 인라인 유지(정확한 이연).
  - 동반 테스트 전환(4파일: test_metadata_{glossary_enum,phase2,glossary_autoreg,ai_autocomplete}.py): happy/val 직접호출 49개에 `account=acct` 명시 주입 + helper(`_admin`/`_env`) 반환 캡처 38개(결정적 AST+paren-match 변환기, 멀티바이트 안전) / 403 perm-gate 9개 → TestClient(`as_account(perms=...)` + 실 require_permission 검사)로 수기 전환.
- Files: src/app.py(33 핸들러 시그니처+auth 블록), tests/test_metadata_{glossary_enum,phase2,glossary_autoreg,ai_autocomplete}.py(전환) + docs.
- Impact: **behavior-neutral(추출 아님 — 핸들러 app.py 잔류, 라우트 불변).** make test 전체 통과·**1313 passed·0 fail**(baseline 1238→1313 = base-merge 로 흡수한 feature-0016 신규 테스트; 내 편집은 테스트 수 불변), route-parity 192 불변(Depends param 추가는 라우트 등록/순서 무영향), py_compile OK. §18.8 적대 패널(REV-0006) GO·ship-blocking 0.
- 학습: 도메인 전용 auth helper(`_X_resolve_account`)도 auth+단일정적 perm 이면 require_permission 로 clean 전환 가능. **txn 이연은 conn 정체성 확인 필수**(독립 PG conn 은 get_conn 무관 → 이연 불요). 동반 테스트: happy RP 직접호출은 `account=` 명시 주입(body 가 perm 재검사 안 함)로 byte-동치, 403 게이트만 TestClient 필수.
- Rollback: revert(app.py 33 핸들러 auth 블록 복원 + 시그니처 원복 + 4 테스트 파일 복원).

## CHG-20260701-0007
- Date: 2026-07-01
- Related Requirement: P5b router 추출 #10 — **admin/metadata 도메인 34 핸들러 → routers/admin_metadata.py**. inline-heavy 도메인 첫 추출(DI 전환 CHG-0006 선행).
- Summary:
  admin/metadata 34 핸들러(DI 전환 33 + 이연 1 `admin_metadata_suggest` inline 유지)를 AST 경계로 `src/routers/admin_metadata.py`(신규, 1447줄) 추출. **tokenize 기반 결정적 변환기**(`metadata_extract.py`): whitelist app-symbol(32) → `app.X` 접두(문자열/속성/정의 안전), `@app.<m>`→`@router.<m>`. 핸들러가 `_metadata_*` 헬퍼와 교차 배치돼 있어 핸들러 함수만 개별 추출(헬퍼는 app.py 잔류, `app.X` 참조로 monkeypatch 보존). app.py 맨 끝 `from routers.admin_metadata import router; include_router`(순환 안전).
  - 동반 테스트 재참조(4파일): `app.<handler>(` → `admin_metadata.<handler>(` 65개(happy 49 + suggest/bootstrap_describe 16) + `from routers import admin_metadata` import. 403-gate 9는 TestClient(route 사용)라 무변경.
  - **make test 안전망 적발·교정**: `_SAMPLE_WEIGHT_MIN`/`_MAX`(app.py `= 1, 1000` **튜플 대입** 모듈 상수)를 whitelist 도출(mod_syms=`ast.Name` 타깃만)이 놓침 → NameError → **완전 mod_syms(튜플/AnnAssign/import 타깃 포함) static 재검사**로 전수 확인 후 `app.` 접두 보정.
- Files: src/routers/admin_metadata.py(신규 1447줄), src/app.py(34 제거 + include_router), tests/test_metadata_{glossary_enum,phase2,glossary_autoreg,ai_autocomplete}.py(재참조), tests/route_snapshot_p5b.json(골든 순서 재생성·set-neutral 192) + docs.
- Impact: **app.py 28,224→26,734 줄(~1,490↓ — 단일 도메인 최대 감소).** make test 전체 통과·**1313 passed·0 fail**·route drift 0, route-parity 192(set 불변·순서만 갱신, docker `_build_table` 재생성), py_compile OK. byte-neutral(라우트 경로·메서드·응답 불변).
- 학습: **whitelist 도출 시 mod_syms 는 튜플-대입(`A, B = ...`)·AnnAssign·import 타깃까지 수집 필수** — `ast.Name` 타깃만 하면 튜플-상수 누락 → 추출 router NameError(make test 안전망 적발). 추출 후 **완전 mod_syms 로 router bare-ref static 재검사**를 골든 재생성 전에 수행하면 조기 적발.
- Rollback: revert(admin_metadata.py 삭제 + app.py 34 복원 + 4 테스트 재참조 원복 + 골든 복원).

## CHG-20260701-0008
- Date: 2026-07-01
- Related Requirement: P5b admin/metadata 마일스톤(CHG-0006 DI 전환 + CHG-0007 추출) **프로덕션 배포·라이브 검증**(deploy-backed 완료 기준).
- Summary:
  PR #506(CHG-0006/0007 2 커밋 + origin/main 재머지) CI test PASS → main 머지(0b91b1b) → `sudo -E bin/deploy-web.sh` blue-green 무중단 롤링(web-a·web-b 순차 recreate, healthz-gated commit-match, soak 90s 통과). deploy_scope: included(FIRST_REQUEST.md 전역 standing) 근거 자동 배포.
  - 라이브 검증(edge 112.185.196.20): healthz git_commit=0b91b1b·status=ok / 추출 admin_metadata 라우트 `/api/admin/metadata/glossary`·`/samples` 미인증 **401 `{"error":"로그인이 필요합니다."}` verbatim** — DI seam byte-동치 + 컨테이너 로드(uvicorn web.app:app) router import 프로덕션 확인(web_context류 ModuleNotFoundError 없음).
- Files: docs(MODIFY/REVIEW/REPORT/TASK) — 배포 기록(코드 무변경).
- Impact: admin/metadata 도메인 deploy-backed 완료. insight/ask-worker GIT_COMMIT WARN 은 별건(웹 무관).
- Rollback: `sudo -E bin/deploy-web.sh --rollback`(이전 색 유지, 이미 안정).

## CHG-20260701-0009
- Date: 2026-07-01
- Related Requirement: P5b router 추출 batch — **6 도메인 35 핸들러 전체추출**(profile·integrations·attachments·admin_audits·admin_accounts·admin_roles). inline-heavy 도메인 대량 추출.
- **전략 전환(핵심 발견)**: **핸들러 router 추출은 DI 전환을 요구하지 않는다.** 원래 블로커(테스트 monkeypatch 커플링)는 *helper* 를 web_context 로 옮길 때만 발생(cross-call 네임스페이스 이탈); *핸들러* 추출은 `import app`+`app.X` 동적참조라 `app._require_account` 등 monkeypatch 계약이 그대로 보존됨(admin_metadata_suggest 선례). → **DEFER 핸들러(pre-auth gate 등)도 인라인 auth 유지로 byte-identical 추출 가능**("이연=구조 재편 후 추출"의 구조 재편 = router 이동 자체). 잔여 10 도메인 분류 workflow(11 agents): CLEAN-DI 5·ALREADY-DI 36·PUBLIC 7·DEFER 50(preauth 42·longpoll 4·txn 3·failsoft 1). 전체추출로 도메인 라우트 split(var-vs-concrete 순서 위험) 회피.
- Summary:
  6 도메인 전 핸들러(ALREADY-DI + PUBLIC + DEFER-inline)를 **범용 tokenize 추출기**(`extract_router.py`)로 router 이동. 개선: (1) 완전 mod_syms(튜플/AnnAssign/import 타깃), (2) **import 심볼 제외 + app.py import_map 으로 router 로컬 import 동적 생성**(fastapi/stdlib/typing), (3) self-healing missing-prefix static 재검사. profile(4)·integrations(4, RedirectResponse/OAuth)·attachments(4)·admin_audits(7)·admin_accounts(8)·admin_roles(8).
  - 동반 테스트 재참조(범용 `reref_tests.py`, `app.<handler>`→`<module>.<handler>` call·getsource·attribute 전부 + module-level import): test_audit_tamper_evidence·test_login_attempt_limit·test_llm_usage_quota·test_avatar_icon_upload·test_two_factor_auth. **추가 커플링 2유형 make test 적발·수정**: (a) `hasattr(app,"handler")` 문자열-인자 3건 → `hasattr(<module>,...)`, (b) `app.app.routes` flat 순회(중첩 include_router 라우트 미포착) → 재귀 walk(test_task0284 route-registered), (c) source-text regex `def download_attachment...@app\.`(app.py) → routers/attachments.py + `@router\.`.
- Files: src/routers/{profile,integrations,attachments,admin_audits,admin_accounts,admin_roles}.py(신규 6), src/app.py(35 제거 + include_router 6), tests/(6 파일 reref+import+coupling fix), tests/route_snapshot_p5b.json(골든 순서 재생성·set-neutral 192) + docs.
- Impact: **app.py 26,734→24,648 줄(~2,086↓).** 12→18 router. make test 전체 통과·1313 passed·0 fail·route drift 0, route-parity 192(set 불변), py_compile OK. byte-neutral(라우트 경로/메서드/응답 불변, DEFER 핸들러 인라인 auth 그대로).
- 학습: 추출 커플링 유형 확장 → (1)직접호출 (2)monkeypatch (3)getsource attribute (4)소스텍스트 read_text/ast.parse (5)**`hasattr/getattr(app,"handler")` 문자열-인자** (6)**`app.app.routes` flat 순회(중첩 라우트)**. 추출 전 grep: `app\.<h>`·`hasattr\(app,"<h>"`·`app.app.routes`. **DI 전환은 추출의 전제가 아님** — 모듈화(app.py 축소)가 목표면 전체추출(인라인 유지)이 최단.
- Rollback: revert(6 router 삭제 + app.py 35 복원 + 테스트 원복 + 골든 복원).

## CHG-20260701-0010
- Date: 2026-07-01
- Related Requirement: P5b 전체추출 batch2 — admin/datasources(6) + api/auth(18) 24 핸들러.
- Summary:
  admin/datasources 6(CLEAN-DI 3 `_ds_write_common` 인라인 유지 + ALREADY-DI 3) → routers/admin_datasources.py. api/auth 18(PUBLIC 7 signup/login/oauth + ALREADY-DI 6 avatar/totp + DEFER 5) → routers/auth.py. 전체추출(인라인 auth 보존, byte-identical).
  - 동반 테스트 reref: datasources 4파일(admin_update/delete/test_datasource 직접호출) + auth 3파일(test_oauth_google_foundation 8 직접호출, test_two_factor_auth·test_login_attempt_limit getsource). **커플링 추가 적발·수정**: hasattr 루프 2(`for fn in (...): hasattr(app,fn)`→auth), **source-text 호출식 count**(test_product_list_rbac 가 `_filter_products_for_account_access(account, products)` 를 app.py 소스에서 2회 count — auth_me 가 auth.py 로 이동해 1로 감소 → app.py+routers 합산 검색으로 수정; 핸들러명 아닌 호출식이라 커플링 스캔 미포착).
  - reref 도구 guard 정밀화: `f" {module}"` generic substring 오탐(module="auth") → `^from routers import ...\b{module}\b` 정확 매칭.
- Files: src/routers/{admin_datasources,auth}.py(신규), src/app.py(24 제거 + include_router 2), tests/(8 파일 reref+coupling fix), tests/route_snapshot_p5b.json(골든 set-neutral 192) + docs.
- Impact: **app.py 24,648→23,536 줄(~1,112↓).** 18→20 router. make test 1313·0 fail·route drift 0, route-parity 192, byte-neutral(PUBLIC/DEFER 인라인 그대로).
- 학습: 커플링 7유형 = 기존 6 + **(7) source-text 호출식 count**(핸들러명 아닌 helper 호출식을 app.py 소스에서 count → 추출로 이동 시 count 변동, app.py+routers 합산으로 수정). reref import guard 는 정확 매칭 필수(generic substring 금지).
- Rollback: revert(2 router 삭제 + app.py 24 복원 + 테스트 원복 + 골든 복원).

## CHG-20260701-0011
- Date: 2026-07-01
- Related Requirement: P5b 전체추출 batch3 — api/conversations 17(→기존 conversations.py **append**) + admin/products 22(신규) = 39 핸들러. **잔여 도메인 대부분 추출 완료**.
- Summary:
  api/conversations 17 sub-resource 핸들러(members/share/attachments/messages/product/sample-feedback/fix-with-ai 등, ALREADY-DI 10 + DEFER 7 인라인) → **기존 routers/conversations.py 에 append**(추출기 --append 모드 신규: 기존 import 에 부족분 병합·핸들러 뒤 추가·include_router 기존 유지·NEW 블록만 missing-prefix 검사). admin/products 22(CLEAN-DI 1 + ALREADY-DI 5 + DEFER 16 txn/streaming/pre-auth 인라인) → routers/admin_products.py(신규).
  - 동반 테스트 reref: conversations 7파일(direct-call post_sample_feedback/post_fix_with_ai + getsource create_conversation_share/list_conversation_shares/list_conversation_attachments/mark_conversation_read) + products 5파일(direct-call). **source-text contract 2 make test 적발·수정**: (a) test_group_conversation_s2 `@app.get(".../members")` in APP(app.py만) → member 핸들러 이동으로 APP_ALL(app.py+routers)+`@router` 허용, (b) **test_share_joinable_owner_guard getsource substring `joinable and not _conversation_owned_by_account`** → 추출로 helper 가 `app._conversation_owned_by_account` 접두되어 substring(앞 단어 `not ` 포함) 불일치 → `not app._conversation_owned_by_account` 로 갱신.
  - 추출기 개선: missing-prefix 에서 IMPORTED 심볼 제외(로컬 import 로 커버), --append 시 NEW 블록만 검사(기존 router F821 은 별건).
- Files: src/routers/conversations.py(+17 append), src/routers/admin_products.py(신규), src/app.py(39 제거 + include_router 1[products; conversations 기존]), tests/(13 파일 reref+source-text fix), tests/route_snapshot_p5b.json(골든 set-neutral 192) + docs.
- Impact: **app.py 23,536→20,542 줄(~2,994↓).** 20→21 router(conversations append). make test 1313·0 fail·route drift 0, route-parity 192, byte-neutral. **잔여 app.py 라우트 16(session 시작 148 대비)**.
- 학습: getsource substring 검사는 **helper 앞 컨텍스트(`not X`, `= X`) 포함 시 app. 접두로 깨짐**(단일 심볼명은 부분문자열로 생존) → 추출 시 그런 substring 은 `app.` 접두형으로 갱신. --append 는 기존 router import 병합 + include_router 미추가. 커플링 8유형(신규 8=getsource 컨텍스트-substring).
- Rollback: revert(conversations 17 append 제거 + admin_products 삭제 + app.py 39 복원 + 테스트 원복 + 골든).

## CHG-20260701-0012
- Date: 2026-07-01
- Related Requirement: P5b 전체추출 batch4 — 잔여 16 라우트(misc/deferred/cross-call). **app.py 라우트 핸들러 전량(148) 추출 완료.**
- Summary:
  잔여 16 핸들러를 기존 router 에 그룹 append: conversations(ask·fork_conversation·clear_memory·progress·ask_result·suggestions 6) + share(public_share_view·public_share_fork 2) + admin_console(admin_get/put_system_prompt·admin_get/put_dashboard_prefs 4) + system(livez·readyz·get_session·get_api_vault_options 4). DEFER(ask_result long-poll·progress/suggestions fail-soft·public_share_view opt) 인라인 유지 byte-identical.
  - **cross-call 핸들러 `ask` 처리(9번째 커플링 유형)**: `ask` 는 route 이자 내부 함수(conversations.py:1397 post_fix_with_ai 가 `app.ask(internal_req)` 호출 + test monkeypatch). conversations.py 로 append → 내부 caller `app.ask`→`ask`(동일 모듈 bare), 테스트 `monkeypatch.setattr(app,"ask")`→`conversations` + `hasattr(app,"ask")`→`conversations` + getsource/직접호출 reref.
  - 동반 테스트 reref: suggestions/ask(conversations) + public_share_*(share) 등 6파일.
- Files: src/routers/{conversations,share,admin_console,system}.py(append), src/app.py(16 제거), tests/(6 reref+cross-call fix), tests/route_snapshot_p5b.json(골든 set-neutral 192) + docs.
- Impact: **app.py 20,542→18,917 줄(~1,625↓).** **잔여 @app 라우트 0 — 148 route 핸들러 전량 21 router 로 추출 완료.** app.py = 헬퍼 라이브러리 + DI seam + 미들웨어 + include_router(조립부). make test 1313·0 fail·route drift 0, route-parity 192, byte-neutral.
- 학습: 커플링 9유형 = 기존 8 + **(9) cross-call 핸들러**(route 이자 내부 함수 — 추출 시 내부 caller 참조 `app.X`→동일모듈 bare + monkeypatch/hasattr 대상 모듈 전환). app.py 잔여(~18.9k)=헬퍼(web_context 미이동, 원래 블로커 — 별도 workstream).
- Rollback: revert(4 router append 제거 + app.py 16 복원 + ask cross-call 원복 + 테스트·골든).

## CHG-20260702-0013
- Date: 2026-07-02
- Related Requirement: batch4 전체추출(CHG-20260701-0012)의 **bare-name 회귀 수정** — 라우터 모듈이 app-모듈 전역/import 심볼을 `app.` 로 한정하지 않아 런타임 `NameError` → 라이브 500 3종.
- Summary:
  P5b batch4 가 app.py 핸들러를 router 모듈로 추출하며, 원래 app.py 네임스페이스에서 해소되던 bare 참조(`MEMORY_DB`, `load_memory_kv` 등)를 `app.` 으로 한정하지 않았다. router 모듈은 `import app` 만 하므로 해당 bare name 이 미해소 → 핸들러 실행 시 `NameError` → 500. CHG-0012 의 "byte-neutral" 주장은 name-resolution 관점에서 부정확(모듈 경계 이동 시 bare app-global 은 비-byte-neutral). 6심볼/10개소를 `app.<name>` 으로 한정.
  - `admin_console.py:78` `MEMORY_DB` → `app.MEMORY_DB` (`GET /api/admin/databases/available` — 제품 DB 화이트리스트 피커).
  - `admin_quotas.py:52` `LLM_QUOTA_ENFORCE` → `app.LLM_QUOTA_ENFORCE` (`GET /api/admin/quotas`).
  - `conversations.py` `load_memory_kv`×5(186·188·194·478·534) + `mark_cancel_requested`(480) + `set_run_status`(503) + `mark_finalize_requested`(535) → 전부 `app.` 한정 (`/api/history` 상태 bubble · `/api/cancel` · `/api/finalize`).
  - 발견 경위: graph-panel-perms(91541447) 배포 후 라이브 브라우저 검증 중 admin 콘솔 500 관측 → `ruff check --select F821 routers/` 전수 감사로 6심볼 확정(브라우저로는 2심볼만 관측, 감사로 LLM_QUOTA_ENFORCE·mark_cancel_requested·set_run_status·mark_finalize_requested 추가 색출).
- Files: src/routers/{admin_console,admin_quotas,conversations}.py (10개소 `app.` 접두만).
- Impact: 라이브 admin console 500 3종 해소(제품 DB 피커·대화 상태 폴링·취소/즉시답변). 순수 name-qualification — `app.X` 는 app.py 가 정의(MEMORY_DB L99·LLM_QUOTA_ENFORCE L758)/import(L48–59 from modules.memory)한 **동일 객체**라 동작 무변경. route 무추가(route-parity 불변).
- 검증: ruff F821 clean(22 router 전체), py_compile PASS, 관련 45 테스트 PASS(quota/history/finalize/conn-status/usage), §18.8 SUBAGENT 패널 VERDICT PASS(정확성·완전성·회귀·부작용 4축 refute 실패), 배포 후 라이브 3엔드포인트 500→200.
- 학습: **라우터 전체추출은 name-resolution 상 byte-neutral 이 아니다** — 추출된 핸들러의 bare app-global/import 참조는 `app.` 한정 필수. batch1~4 의 "byte-neutral" 게이트(make test route-parity)는 *hit 되지 않은* 핸들러의 NameError 를 놓쳤다(테스트 미커버 경로). 향후 추출 시 `ruff --select F821` 를 추출 게이트에 추가 권장. (route-parity 골든 192 vs 실 193 stale 도 같은 batch4 미완 — 별도.)
- Rollback: revert 3파일 `app.` 접두 제거(bare 복원).

## CHG-20260702-0014
- Date: 2026-07-02
- Related Requirement: route-parity 골든 stale 해소(CI red `test_route_parity_p5b` 192→193). batch4(CHG-0012)가 골든을 192 로 set-neutral 했으나, 이후 feature-0016 `24445e94`(#514, "관리콘솔 메타데이터 그래프 뷰 출력 3건 수정")가 `GET /api/admin/metadata/graph/analyze/status` route 를 **추가하면서 골든을 갱신하지 않아** 실 193 vs 골든 192 drift → CI 상시 red.
- Summary:
  route-parity 안전망(`test_route_parity_p5b`)의 골든 스냅샷을 `_build_table()` 출력으로 재생성(테스트 docstring 의 sanctioned 갱신 방법). 정밀 diff 로 drift 원인을 **정확히 1개 route 추가**로 확정(제거·중복·재정렬 0): `GET /api/admin/metadata/graph/analyze/status`(`admin_metadata.py:1013` 정의, `admin.js:3974` 그래프 뷰 AI 분석 상태 폴링에 실사용 — 정당한 엔드포인트). 골든 `total_routes 192→193`, `api_routes 191→192`, analyze/status 블록 in-order 삽입.
- Files: src/../tests/route_snapshot_p5b.json (골든만).
- Impact: CI `test_route_parity_p5b` green 회복(→ 이후 PR 이 route-parity red 위로 머지하지 않음). **runtime 무변경** — 골든은 test fixture 이고 web 이미지(Dockerfile 은 src 만 COPY, tests/ 미포함)에 미반영 → web 재배포는 runtime no-op.
- 검증: 재생성 후 `test_route_parity_p5b` PASS(총 193/api 192). git diff 가 count 2줄 + analyze/status 블록만 변경(9 ins/2 del) 임을 확인 — 다른 route 미변경(오갱신·masking 없음).
- 학습: 의도적 route 추가 시 골든 갱신은 **route 추가 feature 의 책임**(여기선 #514 누락). route-parity 게이트가 이를 잡았으나, 추출-batch 들이 골든을 set-neutral 로 유지하는 사이 타 feature 의 route 추가와 겹쳐 blame 이 흐려졌다. 향후 route 추가 PR 은 골든 동반 갱신 필수(CI 가 강제).
- Rollback: revert route_snapshot_p5b.json(192 복원 — CI red 재발).

## CHG-20260710T235820-item05-router-autoreg (라우터 자동 등록 — app.py 꼬리 배선 경합 제거, parallel-work-structure ITEM-05)
- Date: 2026-07-10
- Related Requirement: ROADMAP parallel-work-structure ITEM-05 (F-008 — include_router 23개가 app.py 꼬리 19,641–19,717 에 밀집, 라우터 신설마다 같은 블록 편집 → 병렬 배선 경합).
- Summary: `routers/__init__.py` 에 `register_all(app)` 구현(pkgutil.iter_modules 순회 → 각 모듈 `router` 심볼 수집 → (INCLUDE_ORDER, 모듈명) 정렬 일괄 include). 23개 라우터 모듈 전부에 `INCLUDE_ORDER = 10..230`(현행 include 순서 스냅샷 고정, 10 간격). app.py 꼬리 블록(import 23+include 23+개별 주석, 3,846 bytes)을 `_register_all_routers(app)` 1줄 호출로 대체 — app.py 19,717→19,650줄. 이후 라우터 신설은 `routers/` 파일 추가만으로 등록(app.py diff 0).
- Files: `unit/feature-0003-agent-web-ui/src/routers/__init__.py`(register_all) · 23개 라우터 모듈(INCLUDE_ORDER 1줄씩) · `unit/feature-0003-agent-web-ui/src/app.py`(꼬리 치환). cross-feature: 코드 거주 feature-0003, 정본 docs 는 본 feature-0012(§0 primary 규약).
- Impact: 라우팅 표면 무변경(byte-동치 검증 아래). 배포 scope: web 이미지 재빌드(코드 baked) — §6.1 자동 배포.
- 검증: (a) 라우트 테이블 in-order 스냅샷 205 route **byte-동치**(전=후, mysql-ai-web:current, `_walk_routes` 식 재귀 열거) (b) `ruff --select F821` routers/ 22모듈+app.py clean (c) A/B pytest(main vs worktree, feature-0003 전 스위트) 양쪽 rc=0 — route-parity 골든 포함 회귀 0 (d) 더미 라우터(`zz_dummy_probe.py`, INCLUDE_ORDER=990) 추가만으로 라우트 노출 확인 후 제거.
- Rollback: app.py 꼬리를 명시 import/include 23쌍으로 복원 + INCLUDE_ORDER 제거(단일 커밋 revert).

## CHG-20260711T100116-item10-webctx-batch1 (web_context 추출 batch1 — inc3 권한 카탈로그 + inc4 계정 행 빌더, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Related Requirement: ROADMAP parallel-work-structure ITEM-10 (F-007-2 — app.py ~19.6k 헬퍼·전역이 전 웹 작업의 공유 착지점).
- Summary: leaf-first 증분(inc1/inc2 계보) 계속 — inc3(SESSION_COOKIE + PERMISSION_DEFINITIONS/CODES/DEFINITION_MAP + _METADATA_MANUAL_IMPLIES + _resolve_permission_catalog, 562줄) · inc4(OVERRIDE_* 상수 + _empty_permission_map + _normalize_override_value + _apply_permission_overrides + _fetch_account_rows + _load_role_permission_codes + _load_account_override_values + _decorate_account_rows, 167줄)를 web_context.py 로 byte-동치 이동. 호출 폐포가 web_context 안에서 닫힘(app 의존 0 — INVARIANT `from app import` 금지 유지). app.py 상단 re-import rebind 로 app 내 호출부·routers `app.X` 동적참조·테스트 monkeypatch/getsource 전부 보존. app.py 19,650→18,931줄.
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(블록 제거+rebind import) · `src/web_context.py`(+768줄) · `tests/test_group_conversation_s2.py`(APP_ALL 에 web_context.py 포함 — 소스-계약 위치 무관 고정).
- 검증: 라우트 스냅샷 205 in-order byte-동치(main 대비, _walk_routes 재귀) · ruff F821 clean(src 전체) · py_compile · feature-0003 전 스위트 pytest rc=0(소스-계약 1건 위치 갱신 후 전건 GREEN). 배포 scope: web 재빌드(item 완료 시 §6.1 — 중간 batch 도 머지-가능 유지).
- Rollback: 단일 커밋 revert(이동+rebind 원자).

## CHG-20260711T103000-item10-webctx-batch2 (web_context 추출 batch2 — 검증 정규식·인증 파라미터·seed 롤, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: batch1(CHG-20260711T100116) 계속 — 검증 정규식 5종(ANSI/CONTROL/MODEL/USERNAME/ROLE_KEY_RE) + SEED_ROLE_DEFINITIONS/_seed_role_definition/_seed_role_codes(RBAC seed) + PASSWORD_HASH_ITERATIONS/AUTH_SESSION_DAYS(인증 파라미터)를 web_context.py 로 byte-동치 이동(상단 rebind). 전부 순수 leaf(monkeypatch 소비 0 — 사전 grep). app.py 18,931→18,854줄.
- Files: src/app.py · src/web_context.py.
- 검증: 라우트 스냅샷 byte-동치 · ruff F821 clean · py_compile · feature-0003 전 스위트 rc=0(테스트 무변경 — app.SEED_ROLE_DEFINITIONS 등 읽기 소비는 rebind 보존).
- Rollback: 단일 커밋 revert.

## CHG-20260711T110000-item10-webctx-batch3 (web_context 추출 batch3 — 세션쿠키·패스워드·TOTP, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: 인증 leaf 클러스터를 web_context.py 로 byte-동치 이동 — 세션쿠키 4(_get_session_id/_request_is_https/_set/_clear_session_cookie) · 패스워드 6(_sanitize/_is_valid_username·_is_valid_password·_hash/_verify_password·_b64decode) · TOTP 상수 6+함수 14(_totp_dek 계열의 `modules.cred_crypto`/`shared.datasources` 는 함수-지역 lazy import 동반 이동 — top-level app-free INVARIANT 유지, 역방향 참조 없어 순환 불가). web_context 상단 import 보강(base64/hmac/json/secrets). app.py 18,854→18,569줄(누적 19,650→18,569, -1,081).
- Files: src/app.py · src/web_context.py.
- 검증: 스냅샷 byte-동치 · ruff F821 clean(중간 스캔이 14건 적발 → import 보강+_b64decode 동반 이동으로 해소 — F821 게이트가 name-resolution 회귀를 실제 차단한 사례) · py_compile · 전 스위트 pytest rc=0(test_two_factor_auth 포함) · monkeypatch 소비 0(사전 census: 상위는 _connect_memory 68·_require_account 52 등 — 본 batch 비대상).
- Rollback: 단일 커밋 revert.

## CHG-20260711T111000-item10-webctx-batch4 (web_context 추출 batch4 — 세션 경로·출력 정규화·미디어 URL, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: 순수 leaf 3군 이동 — ① SESSION_DIR(+mkdir)·INTERNAL_MEMORY_PREFIXES·PLACEHOLDER_TOPICS ② 출력 정규화/내부메시지 판정 5함수(_strip_ansi/_normalize_output/_should_mark_internal_message/_is_internal_message/_unwrap_followup_user_request — 내부 호출쌍 동반 이동) ③ 미디어 URL·대화파일 경로 5함수(_avatar/_product_icon/_role_icon_url_for·_account_conv_file·_conv_file). web_context 에 pathlib.Path 추가. app.py 18,569→18,475줄(누적 -1,175).
- 검증: 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0 · monkeypatch 0(사전 census — SESSION_DIR 테스트 참조 0, routers _conv_file 소비 4 는 app.X 동적).
- Rollback: 단일 커밋 revert.

## CHG-20260711T112500-item10-webctx-batch5 (web_context 추출 batch5 — 계정 로더·id 맵·RBAC seed, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: 16블록 513줄 이동 — 대화 id IO 2·권한/역할 id 맵 2·계정 로더 2·_issue_auth_session·_is_safe_model_name + RBAC seed 부트스트랩 7함수+SEED_PRODUCT_DEFINITIONS. 패치-관통 위험 쌍(_product_permission_code/_ensure_product_access_permissions)·shared 래퍼 2종·프롬프트-seed 쌍은 의도 제외(AST 폐포 스캔+패치 census 로 경계 확정). app.py 18,475→18,009줄(누적 -1,641). web_context 에 logging·datetime 계열 import 보강.
- 사고·교훈: 1차 시도의 라인-휴리스틱 경계가 flush-left SQL heredoc(seed 함수 다수)에서 함수를 절단 — py_compile/F821(5,733)이 즉발 차단, git checkout 후 **AST end_lineno 추출기로 재작업**(이동 텍스트·잔여 app.py·신규 wc 3중 ast.parse 게이트 내장). 이동 경계는 이후 batch 부터 AST 가 정본.
- 검증: 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0.
- Rollback: 단일 커밋 revert.
