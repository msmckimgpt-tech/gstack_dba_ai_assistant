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
