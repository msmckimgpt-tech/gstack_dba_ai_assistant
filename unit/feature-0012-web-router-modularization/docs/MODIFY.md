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
