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
  - [x] **Phase 2 batch 3 (P2_MULTI_CLOSE 10 핸들러)**: use_conversation, history, history_dates, delete_conversation, delete_conversations, cancel_request, finalize_request, get_file, ask_status, me_get_system_prompt. 래퍼 try 없이 early-return 마다 산재한 conn.close() 를 전부 제거(get_conn teardown 이 close) + auth 블록 제거 + 시그니처 Depends(dedent 불요). batch3 workflow(44 agents) 변형별 분류+적대검증: 10 확정(P2)·12 보류. ask_status 는 terminal `finally: conn.close()` 하이브리드(수작업), history/history_dates 는 multi-line sig(변환기 보강). history_dates 동반 테스트(test_history_calendar_pg_routing T1/T3) TestClient 전환. make test progress 1238·0 fail, `_require_account` 64→54.
  - [x] **Phase 2 batch 4 (history_anchor)**: P2_MULTI_CLOSE 마이그(multi-line sig, 6 산재 close 제거) + 동반 테스트 T2(test_history_anchor_returns_pg_id) TestClient 전환. batch3 의 HIGH refute 는 마이그 위험이 아니라 T2 전환 누락이 유일 사유였음(렌즈 확인) → T2 전환으로 해소. 누적 cat-A **35**. make test 1238·0 fail, `_require_account` 54→53.
  - [~] Phase 2 **cat-A 잔여 11 = 아키텍처적 이연**(router-extraction 단계 처리): (a) **pre-auth gate 10** — conn 생성 *이전* 404/400 early-return. `Depends(get_current_account)` hoisting 시 401 우선순위 역전 + `conn=Depends(get_conn)` 는 게이트 이전에 conn 을 eager-open(미설정/잘못된 입력에도 DB 연결 — 부수효과 회귀). 게이트가 본문 첫 게이트인 구조라 DI seam 으로 byte-동치 불가. (b) **ask_result** — auth conn 을 long-poll 루프(최대 60s) *이전*에 닫는데, get_conn 은 요청 종료까지 보유 → 60s idle conn 점유(풀 고갈). long-poll/SSE 는 get_conn 설계와 근본 비호환. → 둘 다 inline 유지, 라우터 추출 시 재구조화..
  - [x] **Phase 3 cat-B batch 1 (require+인라인 perm, 6 핸들러)**: new_conversation·admin_me·admin_permissions·admin_list_available_databases(REQUIRE_PERMISSION → `account=Depends(require_permission("perm", message=원본 403))`, perm-블록 hoist·제거) + conversations·admin_list_products(ACCOUNT_ONLY → `account=Depends(get_current_account)`, perm 검사 본문 유지). cat-B workflow(REV-20260630-0003, 67 agents)이 clean-AND 23 분석+2렌즈 적대검증 → 15 확정. 그중 sole-in-block conn.close() 없는 6개만 batch1 적용(403 메시지 verbatim 추출로 byte-보존). make test 1238·0 fail, `_require_account` account-anchor 53→47.
  - [x] **Phase 3 cat-B batch 2 (WRAP-style RP 5 핸들러)**: public_share_fork, upload_product_icon, delete_product_icon, verify_audit_chain, admin_health_attachment_grants. 외곽 try/finally:conn.close() WRAP 구조 → 변환기 WRAP 경로(try/finally 제거+dedent+perm hoist). 403 메시지 verbatim 보존. delete_product_icon 동반 테스트 TestClient 전환. 누적 cat-B 11. make test 1238·0 fail.
  - [x] **Phase 3 cat-B batch 3 (sole-in-block conn.close 4 핸들러)**: admin_llm_usage·admin_get_dashboard_prefs(RP, WRAP/FB-finally) + admin_list_datasources·admin_datasource_databases(AO, 본문 try/finally:conn.close). 변환기에 `strip_conn_finally` pass 추가(본문 try/finally·defensive try/except-pass 제거+dedent). **cat-B workflow 확정 15 전부 완료**(누적 cat-B 15). make test 1238·0 fail.
  - [x] **Phase 3 cat-B batch 4 (no-flag 10 핸들러)**: cat-B 잔여 워크플로(REV-20260630-0006, 49 agents) no-flag 17 → 14 확정 중 동반 테스트 전환 불요 10 적용. RP 5(admin_accounts·admin_roles·admin_list_quotas·admin_set_role_quota·admin_set_account_quota — OR-of-negations 다중 perm → require_permission 다중 hoist) + AO 5(duplicate_conversation·remove_conversation_member·revoke_share·admin_get_system_prompt[scope분기]·list_profile_audit_events). 변환기 or-chain 다중 perm 인식 + 주석 adjacency 보강. 누적 cat-B 25. make test 1238·0 fail.
  - [x] **Phase 3 cat-B batch 5 (testconv 4 핸들러)**: admin_test_datasource·admin_product_db_insights·admin_usage_conversations(AO — 동반 테스트 직접호출에 actor|account/conn 명시 인자 주입) + admin_archived_conversations(RP — perm 이 require_permission 의존성으로 이동, test_p1 을 TestClient+as_account 전환). **cat-B 잔여 workflow 확정 14 전부 완료**(누적 cat-B 29). make test 1238·0 fail.
  - [x] **Phase 3 cat-C (`_require_permission` 헬퍼 3 핸들러)**: admin_list/approve/reject_sample_feedback → `account=Depends(require_permission("kb.sample.curate"))`(고정 메시지라 message= 생략, conn=Depends 불요). 전용 변환기 `cata_c_transform.py`(RPH). 동반 테스트 7 call(3 TestClient 403 + 4 명시 account happy) 전환. make test 1238·0 fail. 누적 cat-B/C 32.
  - [x] **Phase 3 final migratable (admin_overview RP + admin_products_insight_coverage AO)**: cat-B workflow 가 동반 테스트 전환 필요로 보류했던 2건 회수(테스트 전환: overview 7 call[happy 6 명시 actor + perm-gate 1 TestClient], insight_coverage 5 call[전부 명시 account]). **DI seam byte-동치 가능 핸들러 전부 완료(누적 69).** make test 1238·0 fail.
  - [~] **Final 이전 잔여 = 아키텍처 이연 확정(router-extraction 단계 처리, DI seam byte-동치 불가):** (a) fail-soft 3 — progress·suggestions(conn/auth/perm 실패를 200 으로 흡수 → get_current_account 의 401/500 raise 와 비동치), public_share_view(_optional_account 본문중간 LastSeenAt eager 부수효과). (b) preauth/longpoll/txn ~43 — conn 이전 404/400 early-return(admin CRUD 대부분), long-poll conn-hold, autocommit 토글(admin_create/update/delete_product). cat-A preauth 와 동일 사유.
- [~] TASK-0012-8 helper→web_context 이동 + APIRouter 추출(도메인 1개/커밋) + route-parity 골든 갱신
  - [x] **Final 시작**: Final-planning workflow(8 agents) — NS-BOUND=0 도메인은 web_context 선행 없이 router 추출 가능 확정. route-parity 인프라 갱신(Starlette 1.x `_IncludedRouter` nest → `_walk_routes` 재귀). **keywords router 추출**(src/routers/keywords.py, 4 stub) — make test 전체 통과·route-parity 179 골든 불변·byte-동치.
  - [x] **router 추출 #2 (media, 3 DI 핸들러)**: serve_avatar/serve_product_icon/serve_role_icon → src/routers/media.py(`from app import get_current_account, get_conn, _serve_image_object`, 순환 안전). 실 DI 핸들러 추출 + 골든 순서 갱신(set 불변 179, [45,48,53]→[172-174] 끝 이동, var-vs-concrete shadow 위험 없음) 파이프라인 증명. make test 전체 통과·route drift 0·byte-동치(CHG/REV-0011).
  - [x] **router 추출 #3 (static_pages, 4 무인증 핸들러)**: index/admin_index/share_page/healthz → src/routers/static_pages.py. **test-coupling 보존 패턴**: `import app`+호출시 `app.X` 동적 속성 접근(monkeypatched 헬퍼·test 의 app.FileResponse 가로채기 보존). NS-BOUND=0 분류가 놓친 test_html_no_cache 커플링(app.<handler> 직접참조+app.FileResponse patch)을 make test 가 즉시 적발 → router app.FileResponse 동적참조 + 테스트 호출 위치 전환으로 byte-동치 해소. 골든 [5-8]→[168-171] set 불변. make test 전체 통과·route drift 0(CHG/REV-0012).
  - [x] **router 추출 #4 (admin_conversations, 1 RP 핸들러)**: admin_archived_conversations(`GET /api/admin/conversations/archived`) → src/routers/admin_conversations.py(`from app import require_permission, get_conn, _json_error, _ARCHIVED_CONV_LIMIT`). **concrete-route 끝-이동 var-shadow 역전 점검**(선행 var 캡처: `/{var}` 형제 0 + 광역 `/api/admin/{a}/{b}` 매처 0). 동반 테스트 TestClient perm-gate 403 GREEN=런타임 증명. 골든 [127]→[171]. make test 전체 통과·route drift 0(CHG/REV-0013).
  - [x] **router 추출 #5 (admin_usage, MIXED 2 핸들러)**: admin_llm_usage(`GET /api/admin/usage` RP ~164줄) + admin_usage_conversations(`GET /api/admin/usage/conversations` AO 2-perm) → src/routers/admin_usage.py. **대형 핸들러 verbatim 스크립트 추출(라인슬라이스+화이트리스트 정규식 rewrite) + uniform `import app`+`app.X` 동적참조**(helper-monkeypatch `_query_usage_conversations`·`_usage_account_ids_for_role` 보존). test 직접호출 3 전환(헬퍼 단위테스트·profile 무변). 골든 끝-이동. make test 전체 통과·route drift 0(CHG/REV-0014).
  - [x] **web_context.py 추출 시작 — 증분 #1 (leaf-first)**: ultracode workflow(10 agents, 3 전략 적대판정) → Strategy B 확정. `_sanitize_session_id`+`_hash_session_token`(stdlib-only leaf) → src/web_context.py(신규, from app import 금지=단방향 edge). app.py 상단 re-import rebind(8 호출부+monkeypatch 보존). make test 전체 통과·route drift 0·byte-동치(CHG/REV-0015). A(re-export shim)·C(full-move) 는 적대 stress `broken`(순환import/추출가치0)으로 기각.
  - [x] **web_context 추출 증분 #2 (proxy/client-IP cluster)**: `_TrustedNetwork`·`_parse_trusted_proxies`·`WEB_TRUSTED_PROXIES`·`_is_trusted_proxy`·`_get_client_ip` → web_context.py. AGENT_MODE 결합은 동일 env-read mirror 로 app-free 유지(시그니처 불변), startup-validation 블록 app 잔류, WEB_TRUSTED_PROXIES 계산 위치 이동(둘 다 startup-time fail-loud 보존). make test 전체 통과·route drift 0·byte-동치. docker rebind-identity 7/7·순환 없음(CHG/REV-0016).
  - [x] web_context 추출 후속: **inc3**(SESSION_COOKIE+`_resolve_permission_catalog`+PERMISSION_*/`_METADATA_MANUAL_IMPLIES`, -562줄) + **inc4**(`OVERRIDE_*`·`_empty_permission_map`·`_normalize_override_value`·`_apply_permission_overrides`·`_fetch_account_rows`·`_load_role_permission_codes`·`_load_account_override_values`·`_decorate_account_rows` 폐포, -167줄) — ITEM-10 batch1(2026-07-11). 이동 폐포가 web_context 안에서 닫힘(app 의존 0). 그 후 `_account_has_permission`(11×)·`_require_account`(51×)·`_connect_memory`(62×) = **23-테스트 retarget 영역**(workflow 적대검증 후 진행 권장).
  - [ ] router 추출 잔여: conversations(MIXED, 엔탱글먼트 경계 — AO 10 + INLINE 7, web_context 와 함께 처리 권장). **추출 전 grep `app.<handler>` 직접참조 + `app.<global>` monkeypatch + concrete-route 면 var-매처 선행 점검(0012/0013/0014 학습).** 이연 핸들러 ~46 router 화.
- [~] TASK-0012-9 ship: 브라우저 로그인 QA(win-browser.py) + §18.8 패널 + 배포
  - [x] **origin/main 100-commit 통합 머지**(배포 선결): main app.py +720 additive 신규 9 라우트, auth helper 무변(auth-orthogonal) → app.py auto-merge, route_snapshot 만 충돌→골든 재생성(179→188). make test 전체 통과·route-parity 188(CHG/REV-0017).
  - [x] **§18.8 ship-gate 적대 패널**(ultracode workflow, 14 agents): **판정 GO, ship-blocking 0**. 확정 6(low 1+info 5) 전부 non-blocking. make test 575 passed/0 fail·route-parity 188·byte-동치 계약 무손상·web_context INVARIANT 유지 직접 재현. low finding(WEB_TRUSTED_PROXIES fail-loud 순서 주석) 정정(CHG/REV-0018).
  - [ ] **브라우저 로그인 QA**(win-browser.py bridge OK): 미인증 401 verbatim·로그인 세션쿠키·RBAC 403(admin_usage/admin_conversations)·추출 라우트 14 실호출·conn실패 500. **라이브 자격증명 필요(사용자 confirm).**
  - [x] **PR #485 생성 + CI test PASS + main 머지**(merge commit 24dd588). 이후 main 재전진 재머지.
  - [x] **배포 hotfix**: 프로덕션 배포 중 blue-green healthz 게이트가 컨테이너 로드 import 실패(web_context ModuleNotFoundError, test PYTHONPATH vs uvicorn web.app 패키지 불일치) 적발 → app.py sys.path append + app alias 수정. 컨테이너 실기동+make test 검증(CHG/REV-20260701-0001). web-b OLD 서빙 유지로 프로덕션 무영향.
  - [ ] **프로덕션 재배포**(hotfix 반영 후 bin/deploy-web.sh) + edge healthz 200 + 인증 smoke + 브라우저 QA(자격증명).
- [~] TASK-0012-11 (자율 순차) 잔존 라우트 도메인 추출 — 모놀리스 축소
  - [x] **router 추출 #6 conversations(10 완전-DI 핸들러)**: new_conversation·use_conversation·history·history_anchor·history_dates·delete_conversation(s)·cancel_request·finalize_request·ask_status → routers/conversations.py. AST 경계 + app.X + stdlib import. app.py 29,111→28,610줄. make test 통과·route-parity 188(CHG/REV-20260701-0002).
  - [x] **router 추출 #7 admin_quotas(3)+admin_sample_feedback(3)**: 완전-DI RP → routers/. app.X(non-_ record_audit_event 포함)+stdlib import+test 전환(getsource/hasattr/직접호출). app.py 28,610→28,350. make test 통과(CHG/REV-20260701-0003).
  - [x] **router 추출 #8(batch 3) admin_console(5)**: admin_me·permissions·databases·overview·health → routers/admin_console.py. app.X+from-datetime+test 전환. app.py→28,410, 골든 192(CHG/REV-20260701-0004).
  - [x] **router 추출 #9(batch 4) share(2)+system(2)**: revoke_share·join_conversation_via_share + get_llm_health·get_file → routers/. 소스텍스트 contract 테스트(app.py read_text/ast.parse) → routers 포함 검색. app.py→28,221. **완전-DI 라우트 전부 추출(11 router, CHG/REV-20260701-0005)**.
  - [~] **inline-heavy DI 전환 재개(추출 선행) — admin/metadata 도메인**:
    - [x] **admin/metadata 33 핸들러 DI 전환**(byte-동치, CHG/REV-20260701-0006): 도메인 인라인 auth helper(`_metadata_resolve_account`/`_samples_resolve_account`/`_metadata_resolve_account_perm(request,"<lit>")`) → `Depends(require_permission("<perm>"))`. perm: kb.ingest.manual 27 + kb.glossary.curate 3 + kb.sample.curate 3. 결정적 AST 변환기. **핵심발견: txn(autocommit 17)은 독립 `_pg_connect`(PostgreSQL)라 get_conn memory conn(MySQL) 무관 → txn 이연 사유 미적용.** 이연 1(`admin_metadata_suggest`: pre-auth 404 gate + 동적 perm). 동반 테스트 4파일 전환(happy 49 account= 주입 / 403 gate 9 TestClient). §18.8 패널(4 agents) GO·ship-blocking 0. make test 1313·0 fail·route-parity 192 불변.
    - [x] **admin/metadata router 추출**(34 핸들러 → routers/admin_metadata.py 1447줄, CHG/REV-20260701-0007): tokenize 결정적 변환기(whitelist 32 app-symbol → `app.X` 접두, `@app`→`@router`), 헬퍼는 app.py 잔류(monkeypatch 보존). 테스트 재참조 65(`app.X`→`admin_metadata.X`)+import. 골든 순서 재생성(set-neutral 192). **app.py 28,224→26,734(~1,490↓, 단일 도메인 최대).** make test 1313·0 fail. 학습: mod_syms 는 튜플-대입 상수(`_SAMPLE_WEIGHT_MIN/_MAX`)까지 수집(누락→NameError, make test 적발).
    - [x] **admin/metadata 마일스톤 배포·라이브 검증**(main 0b91b1b, PR #506, CHG/REV-20260701-0008): CI PASS → 머지 → blue-green 배포(soak 통과) → 라이브 smoke(healthz 0b91b1b·추출 라우트 401 verbatim). deploy-backed 완료.
    - [~] **전략 전환 — 전체추출(DI 전환 불요)**: 잔여 10 도메인 분류 workflow(11 agents) 결과 CLEAN-DI 5·ALREADY-DI 36·PUBLIC 7·DEFER 50. **핸들러 추출은 DI 전환 전제 아님**(monkeypatch 는 `app.X` 동적참조로 보존) → DEFER 도 인라인 auth 유지로 byte-identical 추출. 도메인 전체추출로 라우트 split 회피.
      - [x] **batch1 6 도메인 35 핸들러 전체추출**(CHG/REV-20260701-0009): profile 4·integrations 4·attachments 4·admin_audits 7·admin_accounts 8·admin_roles 8 → routers/. 범용 추출기(완전 mod_syms·동적 import·self-healing) + reref(커플링 6유형). **app.py 26,734→24,648(~2,086↓)**, 12→18 router. make test 1313·0 fail.
      - [x] **batch2 datasources 6 + auth 18 전체추출**(CHG/REV-20260701-0010): routers/{admin_datasources,auth}.py. datasources CLEAN-DI 3·auth PUBLIC 7·DEFER 인라인 유지. 커플링 7유형(신규: source-text 호출식 count). **app.py 24,648→23,536(~1,112↓)**, 20 router. make test 1313·0 fail.
      - [x] **batch3 conversations 17(append) + products 22 전체추출**(CHG/REV-20260701-0011): conversations sub-resource → 기존 routers/conversations.py append(추출기 --append 신규), products → routers/admin_products.py. DEFER/txn/streaming 인라인 유지. 커플링 8유형(신규: getsource 컨텍스트-substring). **app.py 23,536→20,542(~2,994↓)**, 21 router. make test 1313·0 fail. **잔여 app.py 라우트 16(session 시작 148 대비 89% 추출)**.
      - [x] **batch4 잔여 16 라우트 그룹 append**(CHG/REV-20260701-0012): conversations(ask+5)·share(public 2)·admin_console(system-prompts/dashboard 4)·system(livez/readyz/session/vault 4). cross-call `ask`(9번째 커플링) 처리. **app.py 20,542→18,917(~1,625↓). 잔여 @app 라우트 0 — 148 route 핸들러 전량 21 router 추출 완료.** make test 1313·0 fail.
      - [x] **batch4 bare-name 회귀 수정**(CHG/REV-20260702-0013): 추출된 핸들러가 bare app-global/import 참조를 `app.` 로 한정 안 해 런타임 `NameError`→라이브 500 3종(제품 DB 피커·상태 폴링·취소/즉시답변). `ruff --select F821` 전수 감사로 6심볼/10개소 확정 → `app.` 한정. ruff F821 clean(22 router)·45 테스트·§18.8 SUBAGENT 패널 PASS·배포 후 500→200. **추출 게이트에 F821 추가 권장(byte-neutral 게이트가 미커버 NameError 놓침).**
      - [x] **route-parity 골든 stale 해소**(CHG/REV-20260702-0014): feature-0016 #514 가 `GET /api/admin/metadata/graph/analyze/status` 추가하며 골든 미갱신 → CI red(192 vs 193). `_build_table()` 재생성(정밀 diff 로 +1 legit route 확정). `test_route_parity_p5b` PASS. test fixture 전용(runtime 무변경). **route 추가 feature 의 골든 동반갱신 책임.**
  - [x] **route-handler 모듈화 완주** — app.py = 헬퍼 라이브러리 + DI seam + include_router. (완전 thin-app: web_context 헬퍼 추출 = 별도 workstream, 원래 블로커.)
      - [ ] (향후 정제) DEFER preauth 핸들러 byte-동치 DI-rework(pre-auth gate → pre-auth dependency).
- [ ] TASK-0012-10 프론트(admin.js/app.js/styles.css) 분할 + CONVENTIONS code-modularity 규약 [별건]

## 4. In Progress
- TASK-0012-7 DI seam Phase 2 batch 1 완료(cat A 단순 require 19/~95). batch 2 진행 예정: SQL-heredoc 핸들러(list_conversation_shares) 수작업 dedent, 동반 테스트 직접호출(profile_usage_conversations) TestClient 전환, 적대검증 보류 3건 orphan-try edit 수정 후 재마이그, cat-A 잔여 클러스터.

## 5. Blocked
- 없음. (브라우저 QA env "WSL 불가" 가정은 2026-06-29 오류로 판명 — PB-0008 `bin/win-browser.py` 로 실 Windows Chrome QA 가능. 머지 전 로그인 플로우 QA 는 Final 게이트.)

## 6. Done
- **batch4 bare-name 회귀 수정(CHG/REV-20260702-0013, 라이브 500 3종)**: 전체추출(batch1~4)이 app.py 핸들러를 router 모듈로 옮기며 bare app-global/import 참조를 `app.` 로 한정하지 않아 런타임 `NameError`→500(제품 DB 피커·대화 상태 폴링·취소/즉시답변). graph-panel-perms 배포(91541447) 후 라이브 브라우저 검증 중 발견 → `ruff --select F821 routers/` 전수 감사로 6심볼/10개소 확정(브라우저 관측 2 + 감사 추가 4). `app.` 한정. ruff F821 clean(22 router)·py_compile·45 테스트 PASS·§18.8 SUBAGENT 패널 VERDICT PASS(정확성·완전성·회귀·부작용 4축 refute 실패). 배포 후 라이브 500→200. **교훈: 라우터 전체추출은 name-resolution 상 byte-neutral 아님 — 추출 게이트에 `ruff --select F821` 추가 권장. route-parity 골든 192 vs 실 193 stale 은 별도 미완.**
- P5b plan-eng-review: APPROVE-WITH-CONDITIONS (REVIEW REV-0012-0001). §12 승인.
- 안전망: `test_route_parity_p5b.py` — `app.routes` 정적 열람으로 경로·메서드·**순서**·count 를 골든(179 route)과 비교, drift 시 fail. `--no-deps` 동작. make test 회귀 0.
- 의존성 audit: 핵심 = `_require_account`(118)·`_require_permission`(7)·`_account_has_permission`(120)·`_optional_account`(2)·`_json_error` + 전역.
- **DI seam 설계(TASK-0012-4)**: 사용자 결정 A(DI 전면). 적대적 비평이 BLOCKING 2(403 메시지 60종 site-specific → `require_permission(message=)` / 트랜잭션 핸들러 22071/22190/22353/14056 오분류) + HIGH/MED 5 적발 → grep 검증 후 `DI_SEAM_BLUEPRINT.md` 보정 반영.
- **DI seam Phase 0(TASK-0012-5)**: app.py L10269~ 에 가산적 토대(`_AuthError`+`@app.exception_handler` 로 `{"error":msg}` 셰이프 보존, `get_conn` yield 의존성+autocommit rollback 안전망, `get_current_account`/`get_optional_account`/`require_permission(*perms,message=)`). 미사용 → behavior-neutral. 검증: py_compile / route-parity 179 / `_AuthError` handler 등록 / **make test 1205 passed·2 skip·0 fail**. 커밋 06d88a8, push 완료.
- **DI seam Phase 1(TASK-0012-6)**: §18.8 이월 보정(get_conn `_connect_memory` 실패 → **None yield**; required→`_AuthError("db connection failed",500)`(memory conn uniform, grep 확인) / optional→None; require_permission 빈 perms ValueError 가드) + `conftest.py`(TestClient + `make_account`/`as_account`/`as_anonymous` fixture + autouse snapshot/restore + `client_capture_errors`) + 파일럿 `GET /api/llm/health` → `Depends(get_conn)`+inline `_get_authenticated_account`(byte-동치) + `test_di_seam_p5b.py` 31 테스트. **§18.8 적대 패널(REV-20260629-0004, 27 agents/5 lens)**: HIGH-1(파일럿 최초 get_optional_account 위임이 auth-raise 500→200 변형) + HIGH-2(인자순서 가드 부재) 적발 → 파일럿 byte-동치 재전환 + 인자순서/mini-app 가드 보정. 검증: **make test 1236 passed·2 skip·0 fail**, ruff clean, route-parity 179 불변.
- **DI seam Phase 2 batch 1(TASK-0012-7, cat-A 19 핸들러)**: auth-first 단순 require 핸들러 19개를 `account=Depends(get_current_account), conn=Depends(get_conn)` 로 전환(부록 원자단위 ①인라인conn ②수동close ③`_require_account`+if error 삭제 ④시그니처). 대상: gdrive_status/disconnect, serve_avatar/role_icon/product_icon, delete_my_avatar, upload_my_avatar, auth_totp_setup/confirm/disable, list_audit_events/actors/resources, list_conversation_members/bans, ban/unban_conversation_member, delete_attachment, join_conversation_via_share. **ultracode workflow(REV-20260629-0006, 72 agents)**: 24 후보 분석 + 핸들러별 2렌즈(순서/conn수명/트랜잭션 + 에러셰이프/응답/account/부수효과) 적대검증 → 21 확정(전부 NONE)·3 보류(orphan-try edit 결함). 19 적용(list_conversation_shares 는 SQL-heredoc dedent 로 batch 2 이월, profile_usage_conversations 는 동반 테스트 전환 동반 필요로 batch 2 이월). 동반 테스트는 getsource/AST 도메인-문자열 단언이라 전환 불요(auth seam 무관 확인). 검증: 구조 변환기 + py_compile + sanity(시그니처/잔류 보일러플레이트/conn 사용) + **make test progress-chars 1238 = baseline 동일·0 fail**, route-parity 179 불변, ruff clean. `_require_account` 호출 118→99(-19). 응답 셰이프 byte-동치(미인증 401 / conn실패 500 / 본문 동일).
- **DI seam Phase 3 final migratable(TASK-0012-7, admin_overview RP + admin_products_insight_coverage AO)**: cat-B workflow 보류분(동반 테스트 전환 필요) 2건 회수. overview 7 call(happy 6 명시 actor/conn + perm-gate 1 TestClient), insight_coverage 5 call(AO 전부 명시 account/conn). **DI seam byte-동치 가능 핸들러 전부 완료(누적 69).** 잔여 ~46 = 아키텍처 이연(fail-soft 3 progress/suggestions/public_share_view + preauth/longpoll/txn 43) → router-extraction. make test 1238·0 fail.
- **DI seam Phase 3 cat-C(TASK-0012-7, _require_permission 헬퍼 3)**: admin_list/approve/reject_sample_feedback → require_permission("kb.sample.curate")(고정 메시지 동치, message= 생략, conn=Depends 불요 — body 가 audit mconn 자체 재오픈). 전용 변환기 cata_c_transform.py(RPH). 동반 테스트 7 call 전환(perm-gate 3 TestClient + happy 4 명시 account). 누적 cat-B/C 32. make test 1238·0 fail. cat-F public_share_view 는 _optional_account 본문중간 LastSeenAt eager 부수효과로 이연.
- **DI seam Phase 3 cat-B batch 5(TASK-0012-7, testconv 4)**: 누적 cat-B 29. AO 3(admin_test_datasource·admin_product_db_insights·admin_usage_conversations) 동반 테스트 직접호출에 actor|account/conn 명시 인자 주입(body perm 검사 보존); RP 1(admin_archived_conversations) test_p1 을 TestClient+as_account 전환(require_permission 우회 회피). cat-B 잔여 workflow 확정 14 전부 완료. make test 1238·0 fail.
- **DI seam Phase 3 cat-B batch 4(TASK-0012-7, no-flag 10)**: 누적 cat-B 25. 잔여 워크플로(REV-0006, 49 agents) no-flag 17→14 확정 중 동반 테스트 전환 불요 10. RP 5(OR-of-negations 다중 perm→require_permission 다중 hoist, 메시지 verbatim) + AO 5(복수 perm/action-분기→account-only). 변환기 or-chain 인식+주석 adjacency 보강. make test 1238·0 fail.
- **DI seam Phase 3 cat-B batch 3(TASK-0012-7, sole-in-block conn.close 4)**: admin_llm_usage·admin_get_dashboard_prefs(RP WRAP/FB-finally) + admin_list_datasources·admin_datasource_databases(AO 본문 try/finally:conn.close). 변환기 `strip_conn_finally` pass 신규(본문 try/finally·defensive try/except-pass 제거+dedent, matching-try 역추적). cat-B workflow 확정 15 전부 완료(누적 cat-B 15). make test 1238·0 fail.
- **DI seam Phase 3 cat-B batch 2(TASK-0012-7, WRAP-style RP 5 핸들러)**: public_share_fork, upload_product_icon, delete_product_icon, verify_audit_chain, admin_health_attachment_grants. REV-0003 확정분 중 외곽 try/finally:conn.close() WRAP 구조 → 변환기 WRAP 경로로 try/finally 제거+본문 dedent+require_permission hoist+산재 close 제거. 403 메시지 verbatim 보존. delete_product_icon 직접호출 테스트→TestClient(as_account). 누적 cat-B 11. make test 1238·0 fail.
- **DI seam Phase 3 cat-B batch 1(TASK-0012-7, require+인라인 perm 6 핸들러)**: cat-B 진입. RP 4(new_conversation, admin_me, admin_permissions, admin_list_available_databases) → `require_permission("perm", message=원본)` 로 perm-게이트 hoist(403 메시지를 제거되는 perm-블록의 `_json_error` 에서 **verbatim 추출**해 sig 에 삽입, byte-보존). AO 2(conversations, admin_list_products) → `get_current_account` + perm 검사 본문 유지(복수 perm/다른 메시지). cat-B workflow(REV-20260630-0003, 67 agents) clean-AND 23 분석+적대검증 → 15 확정 중 sole-in-block conn.close() 없는 6 적용(나머지 9 는 본문 finally:conn.close() try/finally 제거 필요로 batch2). make test 1238·0 fail, route-parity 179, account-anchor 53→47.
- **DI seam Phase 2 batch 4(TASK-0012-7, history_anchor + cat-A 마무리)**: 누적 cat-A 35. history_anchor(P2) 마이그 + T2 테스트 전환으로 batch3 HIGH refute 해소(근본원인=T2 전환 누락, 마이그 자체는 byte-동치). cat-A 잔여 11(pre-auth gate 10 + ask_result long-poll)은 DI seam 으로 byte-동치 불가 → router-extraction 이연 확정. make test 1238·0 fail.
- **DI seam Phase 2 batch 3(TASK-0012-7, P2_MULTI_CLOSE 10 핸들러)**: 누적 cat-A 34. batch3 workflow(REV-20260630-0001, 44 agents)이 잔여 22 후보를 3패턴(P1 pre-auth gate / P2 multi-close / P3 edge)으로 분류+2렌즈 적대검증 → 10 확정(전부 P2, auth-first·산재 conn.close)·12 보류. 마이그: 산재 conn.close() 전부 제거(get_conn teardown) + auth 블록 제거 + 시그니처 Depends, body dedent 불요(래퍼 try 부재). 전용 변환기(`cata_p2_transform.py`) + ask_status terminal-finally 수작업 + history/history_dates multi-line sig. history_dates 동반 테스트(T1/T3) TestClient 전환. make test progress 1238·0 fail, route-parity 179, `_require_account` exact 64→54.
- **DI seam Phase 2 batch 2(TASK-0012-7, 보류 5 핸들러)**: mark_conversation_read, list_conversation_attachments, profile_llm_usage, list_conversation_shares, profile_usage_conversations 전환(누적 cat-A 24). REV-0006 적대 패널이 5건 모두 runtime byte-동치 확인했고, 3 held 는 자동 edit-spec 의 orphan-`try:`(finally 만 제거) 결함뿐 → 구조 변환기가 body `try:`+`finally:` 동시 제거·dedent 로 올바르게 전환(py_compile OK). nested-finally(`finally: try: conn.close() except: pass`) 변종 + flush-left SQL heredoc(문자열 verbatim 보존) 처리. profile_usage_conversations 동반 테스트(`test_usage_conversations::test_p1_profile_ignores_role_account`) 직접호출→TestClient(`as_account`) 전환. make test progress-chars 1238 동일·0 fail, route-parity 179, ruff clean, `_require_account` 88→64.

## 7. Next Action
- TASK-0012-7 Phase 2 batch 4: 보류 12 처리. (1) **pre-auth gate 10**(post_group_chat_message, upload_conversation_attachment, get_attachment_metadata/download/versions, gdrive_connect/callback, me_put_system_prompt, get_audit_event, progress): conn 생성 이전 early-return(404/400)이 있어 Depends(get_current_account) hoisting 시 401 우선순위 역전 → §1.6 account-only variant(게이트는 본문 유지, 인증만 게이트 뒤) 또는 게이트를 의존성으로 승격. (2) **ask_result**(P3, 복수 _connect_memory) edge. (3) **history_anchor**(적대 HIGH refute — 한 렌즈가 반증, 재조사 후 결정). 이후 전체 cat-A 재survey → Phase 3(cat B 인라인 perm).
- (이전) TASK-0012-7 Phase 2 batch 2: (a) list_conversation_shares — body 의 flush-left SQL heredoc 때문에 일괄 4-space dedent 불가 → 수작업 마이그(SQL 문자열 보존). (b) profile_usage_conversations — 동반 테스트(`test_usage_conversations.py::test_p1_profile_ignores_role_account`)가 `app.profile_usage_conversations(_Req(...))` 직접 호출 + monkeypatch → TestClient(`as_account`) 전환 동반. (c) 적대검증 보류 3건(mark_conversation_read/list_conversation_attachments/profile_llm_usage) — 외곽 `try:`/`finally:conn.close()` 1쌍 구조라 변환기의 orphan-try 회피용 수작업 edit. (d) cat-A 잔여(~75) batch 화.
- 변환 도구: `scratchpad/cata_transform.py`(보수적 — 정확 패턴만, SQL-heredoc·inline-close·복수conn 은 skip). batch 마다 make test progress-chars baseline 대조 + route-parity 179 게이트.
- 주의(파일럿 교훈): conn-acquire-fail 과 auth-query-raise 의 legacy 의미가 사이트별로 다를 수 있음(fail-soft vs fail-loud) — pre-auth gate(conn 생성 이전 early return) 있는 핸들러는 cat-A 부적격(401 우선순위 역전), account-only DI variant 필요.

## 8. Completion Checklist (Final 시작 = route-parity 인프라 + keywords router 추출)
- [x] Final-planning workflow(8 agents, 적대검증) — NS-BOUND=0 도메인 web_context 선행 불요 + 추출 순서 확정
- [x] route-parity 인프라: Starlette 1.x `_IncludedRouter` nest 대응 `_walk_routes` 재귀(전 라우트 열거 유지, 골든 179 불변)
- [x] keywords router 추출(src/routers/{__init__,keywords}.py) + app.include_router(순환 안전). 경로/메서드/순서/응답 byte-동치(원본 422/410 보존 검증)
- [x] make test 전체 통과·0 fail, route-parity 골든 불변, ruff clean, py_compile OK
- [x] TASK/REPORT/MODIFY/REVIEW 반영, BLOCKED 없음
- [ ] verify-completion PASS(9 checks) → Git 커밋 (Final #1)
- [ ] Git 원격 동기화: ai/* push. PR/머지·배포는 Final 완료 후.

## 20260710T2358-item05-router-autoreg — 라우터 자동 등록: app.py 꼬리 배선 경합 제거 (parallel-work-structure ITEM-05)

> 신규 최상위 섹션 헤더 timestamp 형식 = AGENTS.md §13.1 2026-07-10 개정(ADR-20260710T231146) 적용.

- [x] `routers/__init__.py` — `register_all(app)`: pkgutil.iter_modules 순회로 각 모듈 `router` 심볼 수집, (INCLUDE_ORDER, 모듈명) 정렬 일괄 include. 미지정 신규 모듈은 맨 뒤 파일명 순.
- [x] 23개 라우터 모듈 전부에 `INCLUDE_ORDER = 10..230`(10 간격) — 현행 include 순서 스냅샷 고정(guards: 순서 변경 금지).
- [x] app.py 꼬리 include 블록(19,641–19,717 — import 23 + include 23줄)을 `_register_all_routers(app)` 1줄로 대체. app.py 19,717→19,650줄. **이후 라우터 신설은 app.py diff 0**(병렬 배선 경합 원천 제거 — F-008).
- [x] acceptance (a) 라우트 테이블 스냅샷 in-order 205 route **byte-동치**(전=후, mysql-ai-web:current 이미지 실증) (b) `ruff --select F821` routers/+app.py clean (c) A/B pytest(feature-0003 스위트, main vs worktree) 양쪽 rc=0 — route-parity 골든 포함 회귀 0 (d) 더미 라우터 파일 추가만으로 라우트 노출(app.py 무편집) 확인 후 제거.
- [ ] 배포(§6.1 자동): 머지 후 web 재빌드(`bin/deploy-web.sh`) + healthz/스모크.

## 20260711T1001-item10-webctx-batch1 — web_context 추출 batch1: inc3 권한 카탈로그 + inc4 계정 행 빌더 (parallel-work-structure ITEM-10)

- [x] inc3: SESSION_COOKIE · PERMISSION_DEFINITIONS/CODES/DEFINITION_MAP · _METADATA_MANUAL_IMPLIES · _resolve_permission_catalog → web_context.py (-562줄, byte-동치 이동 + 상단 rebind)
- [x] inc4: OVERRIDE_ALLOW/DENY/INHERIT · _empty_permission_map · _normalize_override_value · _apply_permission_overrides · _fetch_account_rows · _load_role_permission_codes · _load_account_override_values · _decorate_account_rows → web_context.py (-167줄, 폐포 완결)
- [x] app.py 19,650 → 18,931줄 (web_context 90→858). INVARIANT 유지: web_context 는 `from app import` 0(단방향).
- [x] 게이트: 라우트 스냅샷 205 in-order **byte-동치**(main 대비) · ruff F821 clean · py_compile · feature-0003 전 스위트 pytest rc=0
- [x] 소스-계약 테스트 1건 위치 갱신(test_group_conversation_s2 APP_ALL 에 web_context.py 포함 — batch4 ROUTERS 포함과 동일 계보)
- [ ] 후속 batch: SEED_ROLE_DEFINITIONS·_seed_role_* → 도메인 클러스터 위상순 → 23-테스트 retarget 영역(_account_has_permission·_require_account·_connect_memory)은 적대검증 후

## 20260711T1030-item10-webctx-batch2 — web_context 추출 batch2: 검증 정규식·인증 파라미터·seed 롤 (parallel-work-structure ITEM-10)

- [x] ANSI_RE·CONTROL_RE·MODEL_RE·USERNAME_RE·ROLE_KEY_RE(검증 정규식 leaf) → web_context.py
- [x] SEED_ROLE_DEFINITIONS(-75줄) · _seed_role_definition · _seed_role_codes(RBAC seed 클러스터) → web_context.py
- [x] PASSWORD_HASH_ITERATIONS · AUTH_SESSION_DAYS(인증 파라미터) → web_context.py
- [x] app.py 18,931 → 18,854줄 (web_context 858→961). INVARIANT 유지.
- [x] 게이트: 라우트 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0
- [ ] 후속 batch: 도메인 클러스터 위상순 + 23-테스트 retarget 영역(적대검증 후)

## 20260711T1100-item10-webctx-batch3 — web_context 추출 batch3: 세션쿠키·패스워드·TOTP 인증 클러스터 (parallel-work-structure ITEM-10)

- [x] 세션쿠키: _get_session_id·_request_is_https·_set/_clear_session_cookie → web_context.py
- [x] 패스워드: _sanitize/_is_valid_username·_is_valid_password·_hash/_verify_password·_b64decode → web_context.py
- [x] TOTP: _TOTP_* 상수 6 + _totp_* 함수 14(2FA 전체 — dek/encrypt/decrypt 의 modules/shared 참조는 함수-지역 lazy import 로 동반 이동, 순환 불가 방향) → web_context.py
- [x] app.py 18,854 → 18,569줄 (web_context 961→1,293). 상단 import 보강(base64/hmac/json/secrets).
- [x] 게이트: 스냅샷 byte-동치 · F821 clean(중간 14건 적발→import 보강·_b64decode 동반 이동으로 해소) · py_compile · 전 스위트 pytest rc=0
- [x] §18.8 패널(auth dispatch — 인증 코어 인접): 아래 REVIEW 참조

## 20260711T1110-item10-webctx-batch4 — web_context 추출 batch4: 세션 경로·출력 정규화·미디어 URL 빌더 (parallel-work-structure ITEM-10)

- [x] SESSION_DIR(+mkdir — import 시점 선행으로 무해)·INTERNAL_MEMORY_PREFIXES·PLACEHOLDER_TOPICS → web_context.py
- [x] 출력/메시지: _strip_ansi·_normalize_output·_should_mark_internal_message·_is_internal_message·_unwrap_followup_user_request → web_context.py
- [x] 미디어/경로: _avatar/_product_icon/_role_icon_url_for·_account_conv_file·_conv_file → web_context.py
- [x] app.py 18,569 → 18,475줄 (web_context 1,293→1,418). monkeypatch 소비 0 사전 census.
- [x] 게이트: 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0
- [ ] batch5+: retarget 영역(_connect_memory 68×·_require_account 52× 등) — 적대 분석 subagent 진행 중, 판정표 기반 진행

## 20260711T1125-item10-webctx-batch5 — web_context 추출 batch5: 계정 로더·id 맵·RBAC seed 부트스트랩 (parallel-work-structure ITEM-10)

- [x] 대화 id IO(_read/_write_conversation_id) · 권한/역할 id 맵(_permission_id_map/_role_id_map) · 계정 로더(_load_account_by_id/_load_account_by_username — 폐포가 wc 내 _fetch/_decorate 로 닫힘) · _issue_auth_session · _is_safe_model_name → web_context.py
- [x] RBAC seed 부트스트랩 7함수(_create_role_with_permissions·_ensure_permission_catalog·_ensure_default_signup_role·_ensure_seed_roles·_cleanup_deprecated_role_permissions·_prune_orphaned_permission_catalog·_ensure_seed_products) + SEED_PRODUCT_DEFINITIONS → web_context.py
- [x] 제외(경계 확정): _product_permission_code+_ensure_product_access_permissions(패치 1×+내부 호출 쌍 — 관통 위험), _is_allowed_api_model/_model_supports_temperature(shared.model_catalog 래퍼), 프롬프트-seed 쌍(_load/_upsert_system_prompt 의존)
- [x] app.py 18,475 → 18,009줄 (web_context 1,418→1,938). 누적 19,650→18,009(-1,641).
- [x] **교훈**: 라인-휴리스틱 경계(block_range)가 flush-left SQL heredoc 에서 함수를 절단(전 스위트 5,733 F821 로 즉발) → **AST end_lineno 가 이동 경계의 정본**(이동 텍스트·잔여 파일 각각 ast.parse 게이트 동반). 이후 batch 는 AST 추출기 고정.
- [x] 게이트: 스냅샷 byte-동치 · F821 clean(datetime import 1건 보강) · py_compile · 전 스위트 pytest rc=0

## 20260711T1240-item10-webctx-batch6 — web_context 추출 batch6(A+B+C): retarget 영역 적대 분석 기반 (parallel-work-structure ITEM-10)

- [x] **적대 분석(improve-fit-reviewer, AST 호출그래프+패치 census 전수)**: 심볼별 SAFE-MOVE/KEEP 판정표 확보 — **KEEP 3종 확정**(_connect_memory 68×·_require_account 52×·_account_can_access_conversation 8× — 패치-단일점 보존, app.py 종국 역할=runtime hub·DI seam) + **이동 영구 금지 목록 9종** web_context 헤더 명문화.
- [x] Batch A(121줄): 계정/권한 read-model 7함수(_legacy_permission_codes_from_row·_account_permissions·_account_has_permission·_account_has_any_permission·_role_payload·_serialize_account·_strip_quota_fields_if_unpermitted) — retarget 0 전수 검증.
- [x] Batch B(116줄): 제품 접근 4함수(_account_has_product_access·_filter_products_for_account_access·_product_permission_code·_coerce_default_product_id).
- [x] Batch C(74줄): _get_authenticated_account·_build_actor_from_request(폐포 전부 wc 기이동분).
- [x] app.py 18,009 → 17,724줄 (web_context 1,938→2,281). 누적 19,650→17,724(-1,926).
- [x] 게이트: 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0
- [ ] **후속 지렛대(판정표 §4)**: web_context 추가 이동은 한계(-350줄 규모) — ≤1,000 목표의 실질 경로는 **대형 호출자(_ds_write_common·_collect_*_prompt_context·_metadata_* 등 수천 줄)의 routers/ 도메인 모듈 이동**(app.X 동적참조 = 패치-단일점 자동 보존, ITEM-05 자동 등록 완비).

## 8b. (이전) Completion Checklist (DI seam Phase 3 final migratable = admin_overview + admin_products_insight_coverage)
- [x] 2 핸들러 회수(RP overview + AO insight_coverage) — DI seam byte-동치 가능 핸들러 전부 완료(누적 69)
- [x] behavior-neutral — make test progress-chars 1238(baseline 동일)·0 fail, route-parity 179 불변, ruff clean, py_compile OK
- [x] §18.8 — REV-20260630-0009: 종합 잔여 survey + REV-0006 확정분 회수. fail-soft 3 + preauth/longpoll/txn 43 이연 확정(코드 정독 byte-동치 불가)
- [x] 동반 테스트 전환 — overview 7 call(happy 6 명시 actor + perm-gate 1 TestClient), insight_coverage 5 call(명시 account). 미전환 직접호출 0
- [x] Final 이전 잔여 = 아키텍처 이연 전부 문서화(MODIFY CHG-0009 / REVIEW REV-0009)
- [x] TASK/REPORT/MODIFY/REVIEW 반영, BLOCKED 없음
- [ ] verify-completion PASS(9 checks) → Git 커밋
- [ ] Git 원격 동기화: ai/* push (§16.3). PR/머지·라우터 추출·배포는 Final.

## 20260711T1207-docs-archive — MODIFY/REVIEW §5.5 아카이빙 (사용자 지시 2026-07-11)
- [x] MODIFY 45→15건·REVIEW 46→15건 이관, 무손실 md5, 링크+REPORT 압축(§5.5). 선례 3건 동일 계보 — 이로써 §5.5 20건-초과 문서 전량 해소.

## 20260711T1215-item10-routers-p1 — routers/ 이동 파일럿: _ds_write_common (parallel-work-structure ITEM-10, 판정표 §4 경로)

- [x] `_ds_write_common`(async, 26줄) → routers/admin_datasources.py — app 전역 4종(_require_account·_connect_memory·_account_has_permission·_json_error, 전부 KEEP 목록)은 **app.X 동적 참조**로 전환(패치-단일점 자동 보존) · 도메인 내 호출 3곳 로컬화 · 직접호출 테스트(test_datasource_delete:100)의 `app._ds_write_common` 는 app 꼬리 rebind 로 무변경 보존(register_all 이후 — 순환 안전)
- [x] 게이트: 스냅샷 205 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0 — **routers-이동 패턴 확립**(다음: _collect_*_prompt_context·_metadata_* 대형 클러스터 동일 패턴)

## 20260711T1519-item10-routers-p2 — _metadata_* 20종 → routers/admin_metadata (parallel-work-structure ITEM-10)

- [x] _metadata_* 헬퍼 20종(453줄, L16231-17087 산재) → routers/admin_metadata.py — 파일럿(routers-p1) 패턴: app-전역 13종 app.X 동적 프리픽스 · 도메인 내 소비(23+21+20+16+12…) 로컬화 · **패치되는 _metadata_llm_complete 호출부만 app.X 유지**(setattr 패치 관통 보존) · 테스트 직접참조 4종+app 내부 잔존 호출자(_glossary_feedback_iso)는 꼬리 rebind
- [x] app.py 17,704 → 17,294줄(누적 19,650→17,294, -2,356)
- [x] 게이트: 스냅샷 205 byte-동치 · F821 clean · py_compile · 전 스위트 pytest

## 20260711T1523-item10-routers-p3 — 프롬프트 컨텍스트 조립 8종 → routers/_prompt_context (parallel-work-structure ITEM-10)
- [x] _collect_* 5 + _assemble_* 3 (864줄) → routers/_prompt_context.py — 소비 4개 도메인 분산이라 비-라우트 공용 모듈(`_` 접두 = register_all 자동 제외). app-전역 18종 app.X · **패치 4종(setattr: _assemble_ 3종+_collect_conversation_signals_pg)의 클러스터-내부 호출도 app.X**(관통 보존) · 꼬리 rebind 8종.
- [x] app.py 17,294 → 16,449줄(누적 19,650→16,449, **-3,201**)
- [x] 게이트: 스냅샷 205 byte-동치 · F821 clean · py_compile · 전 스위트 pytest

## 20260711T1530-item10-routers-p4 — _conv_* 11종 → routers/_conv_store (parallel-work-structure ITEM-10)
- [x] 대화 저장소 헬퍼 11종(469줄) → routers/_conv_store.py(share/conversations 공용 — register_all 제외 모듈). 패치 0(census)·app-전역 3종 app.X·꼬리 rebind(직접참조 1·app 내부 호출자 8 보존). app.py 16,449→16,005(누적 **-3,645**).
- [x] 게이트: 스냅샷 205 byte-동치 · F821 · py_compile · 전 스위트 pytest rc=0

## 20260711T1537-item10-routers-p5 — 대화 조회 4종(1,010줄) → routers/_conv_store (parallel-work-structure ITEM-10)
- [x] _list_conversations(_pg)·_get_history·_get_agent_core_history → _conv_store.py append(도메인 응집). census: 패치 0·직접참조 2(rebind)·내부 호출자 2(rebind)·app-전역 21종 app.X(KEEP 계열 포함 — 관통 보존). app.py 16,005→15,003(누적 **-4,647**).
- [x] 게이트: 스냅샷 205 byte-동치 · F821(os import 1건 보강) · py_compile · 전 스위트 pytest rc=0(소스-계약 1건 APP→APP_ALL 위치 갱신 — batch1/membership 계보, 계약 내용 무변경)

## 20260711T1607-item10-routers-p6 — fork·steps·첨부편집 6종(824줄) → routers/_conv_store (parallel-work-structure ITEM-10)
- [x] _fork_conversation_impl·_copy_conversation_attachments·_load_steps_for_run/_message·_load_step_meta·_materialize_assistant_attachment_edits → _conv_store append. census 패치 0·app-전역 34종 app.X·꼬리 rebind. app.py 15,003→14,191(누적 **-5,459**).
- [x] 게이트: 스냅샷 205 byte-동치 · F821(Request/hashlib import 보강) · py_compile · 전 스위트 pytest rc=0

## 20260711T1618-item10-routers-p7 — 감사 인프라 17종(697줄) → routers/_audit_infra (parallel-work-structure ITEM-10)
- [x] _audit_* 16 + build_audit_change_json → _audit_infra.py 신설(전 라우터 공용 — register_all 제외). **record_audit_event 는 app 잔류**(setattr 12× 패치-단일점) — 이동분의 호출은 전부 app.record_audit_event 동적. census 패치 0(이동분). app.py 14,191→13,531(누적 **-6,119 / -31%**).
- [x] 게이트: 스냅샷 205 byte-동치 · F821 · py_compile · 전 스위트 pytest rc=0

## 20260711T1953-item10-routers-p8 — 부트스트랩 스키마 3종(822줄) → routers/_bootstrap_schema (parallel-work-structure ITEM-10)
- [x] _ensure_web_tables(오케스트레이터 436)·_seed_main_mysql_datasource(239)·_ensure_web_product_datasources_schema(147) → _bootstrap_schema.py 신설. census 패치/getsource 0. `global _WEB_TABLES_READY` 는 app 속성 대입으로 등가 변환(신규 패턴 — global-쓰기 결합 해소). 호출 기계(_bootstrap_memory_runtime 계열)는 app 잔류(KEEP). app.py 13,531→12,718(누적 **-6,932 / -35%**).
- [x] 게이트: 스냅샷 205 byte-동치 · F821 · py_compile · 전 스위트 pytest rc=0
- [x] 사고 기록: 1차 실행이 cwd 오인으로 repo 메인 체크아웃을 변형(F0) → 즉시 git checkout 원복 후 worktree 재실행(잔여 오염 0 — git status 대조).

## 20260711T1957-item10-routers-p9 — 제품 인사이트 2종 + 첨부 백그라운드 2종(608줄) 이동 (parallel-work-structure ITEM-10)
- [x] _compute_product_db_insights·_compute_product_insight_coverage → admin_products.py(단일 도메인 소유 — coverage 는 setattr 1× 이나 클러스터 내부 호출 0 = 관통 표면 없음, app 내부 호출자 _auto_prompt_sweep_once 는 rebind) · _ingest_attachment_background·_prepare_vision_inline_images → _conv_store.py. app.py 12,718→12,123(누적 **-7,527 / -38%**).
- [x] 게이트: 스냅샷 205 byte-동치 · F821(uuid 보강) · py_compile · 전 스위트 pytest rc=0
