---
doc_type: REPORT
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
P5b(app.py 모놀리스 router 분할, Critical). plan-eng-review(APPROVE-WITH-CONDITIONS)+§12 승인 → route-parity 안전망+의존성 audit 완료(PR #456 머지). **2026-06-29**: web_context 직추출이 테스트 monkeypatch 커플링에 막힘을 확인 → 사용자 결정 **A(DI 전면)** → FastAPI DI seam 선행. **Phase 0(가산적 토대)** 구현·검증·커밋(06d88a8). **Phase 1(테스트 인프라 + 파일럿)** 완료: §18.8 이월 보정(get_conn None-yield 분기) + `conftest.py`(TestClient/`as_account` fixture) + 파일럿 `GET /api/llm/health` DI 전환(byte-동치) + 회귀 스위트 31. §18.8 적대 패널(27 agents/5 lens, REV-0004)이 HIGH 2건(파일럿 get_optional_account 위임의 auth-raise 500→200 변형 / 인자순서 가드 부재) 적발 → 보정. make test 1236 passed/2 skip/0 fail.

## 2. Progress
- Done: plan-eng-review+§12 · route-parity 안전망(골든 179) · 의존성 audit · **DI seam 설계(DI_SEAM_BLUEPRINT.md)** · **Phase 0(deps+_AuthError handler+get_conn, behavior-neutral, 커밋 06d88a8)** · **Phase 1(conftest TestClient/`as_account` + 파일럿 get_llm_health DI 전환 byte-동치 + get_conn None-yield 보정 + require_permission 빈 perms 가드 + 회귀 스위트 31 + §18.8 적대 패널 HIGH 2 보정)**.
- In Progress: DI seam **Phase 2 cat-A(35) + Phase 3 cat-B(29)+cat-C(3)+final(2) = 69 핸들러 — DI seam byte-동치 가능 핸들러 전부 완료.** cat-A b1-4 + cat-B b1-5 + cat-C + admin_overview/admin_products_insight_coverage. 잔여 ~46 = 아키텍처 이연(fail-soft 3 + preauth/longpoll/txn 43) → Final(router-extraction). **Final 이전 작업 완결.** ultracode workflow 5회(232 agents) 2렌즈 적대검증. make test 1238·route-parity 179. 변환기 `cata_b_transform.py`(변수명/스타일 자동·메시지 verbatim·strip_conn_finally·or-chain 다중 perm). 테스트 전환 패턴: AO 직접호출=명시 actor/conn 인자, RP=TestClient+as_account. **Final 진행중: router 추출 #1 keywords(4 stub, CHG-0010) + #2 media(3 DI, CHG-0011) 완료 — APIRouter 분할 파이프라인(순환 안전 import + route-parity recursion + 골든 순서 게이팅) 확립·증명. 다음: static_pages(4 무인증)→admin-conversations(1)→admin-usage(5 MIXED)→conversations 순차 NS-BOUND=0 추출 → NS-BOUND 도메인용 web_context 추출 → 브라우저 QA → 배포(confirm).**
- 이연(아키텍처, router-extraction 단계): cat-A pre-auth gate 10(401 우선순위 역전·conn eager-open) + ask_result(long-poll 60s conn-hold).
- Planned: Phase 3(cat B)~7 → helper→web_context 이동 → APIRouter 추출 → 브라우저 로그인 QA+§18.8+배포 → 프론트 분할.

## 3. Recent Changes
- CHG-20260625-0001: feature-0012 scaffold + route-parity 안전망 테스트/골든 + 의존성 audit (P5b 선행물, PR #456).
- CHG-20260629-0002: DI seam 설계(DI_SEAM_BLUEPRINT.md) + Phase 0 가산적 토대(app.py auth DI 의존성 5종 + 예외 핸들러). behavior-neutral, make test green.
- CHG-20260629-0003: DI seam Phase 1 — get_conn None-yield 보정(required 500/optional None) + require_permission 빈 perms 가드 + conftest(TestClient/`as_account`) + 파일럿 get_llm_health DI 전환(byte-동치) + 회귀 스위트 31 + §18.8 적대 패널(REV-0004) HIGH 2 적발·보정. make test 1236 green.
- CHG-20260629-0004: Phase 1 완료 기록 보강(doc-tail bookkeeping, 커밋 ca66ee9 closure).
- CHG-20260629-0005: DI seam Phase 2 batch 1 — cat-A 단순 require 19 핸들러 DI 전환(byte-동치). ultracode workflow 적대검증(REV-0006, 72 agents, 21 확정/3 보류). make test progress 1238(baseline 동일), route-parity 179, `_require_account` 118→99.
- CHG-20260629-0006: DI seam Phase 2 batch 2 — REV-0006 보류 5 핸들러 마무리(누적 cat-A 24). orphan-try edit-spec 결함을 구조 변환기로 교정 + SQL-heredoc verbatim + profile_usage_conversations 동반 테스트 TestClient 전환. make test progress 1238, route-parity 179, exact-anchor _require_account 88→64.
- CHG-20260630-0001: DI seam Phase 2 batch 3 — P2_MULTI_CLOSE 10 핸들러(누적 cat-A 34). batch3 workflow(REV-20260630-0001, 44 agents) 22 후보 3패턴 분류+적대검증 → 10 확정/12 보류. 산재 conn.close 제거형, ask_status terminal-finally 수작업, history_dates 동반 테스트 전환. make test progress 1238, route-parity 179, exact-anchor _require_account 64→54.
- CHG-20260630-0002: DI seam Phase 2 batch 4 — history_anchor(누적 cat-A 35) + cat-A 마무리. batch3 HIGH refute 해소(근본원인=T2 전환 누락). cat-A 잔여 11(pre-auth gate 10 + ask_result) 아키텍처 이연 확정. make test 1238, exact-anchor _require_account 54→53.
- CHG-20260630-0003: DI seam Phase 3 cat-B batch 1 — require+인라인 perm 6 핸들러(RP 4 require_permission + AO 2 account-only). cat-B workflow(REV-20260630-0003, 67 agents) clean-AND 23 → 15 확정 중 sole-in-block 없는 6 적용. 403 메시지 verbatim 추출 byte-보존. make test 1238, account-anchor 53→47.
- CHG-20260630-0004: DI seam Phase 3 cat-B batch 2 — WRAP-style RP 5 핸들러(public_share_fork·upload/delete_product_icon·verify_audit_chain·admin_health_attachment_grants). 외곽 try/finally:conn.close 제거+dedent+require_permission hoist. delete_product_icon 동반 테스트 전환. 누적 cat-B 11. make test 1238.
- CHG-20260630-0005: DI seam Phase 3 cat-B batch 3 — sole-in-block conn.close 4 핸들러(admin_llm_usage·admin_get_dashboard_prefs RP WRAP/FB + admin_list_datasources·admin_datasource_databases AO 본문 try/finally). 변환기 strip_conn_finally pass 신규. cat-B 확정 15 완결. make test 1238.
- CHG-20260630-0006: DI seam Phase 3 cat-B batch 4 — no-flag 10 핸들러(RP 5 OR-of-negations require_permission 다중 hoist + AO 5). cat-B 잔여 workflow(REV-0006, 49 agents) no-flag 17→14 확정. 변환기 or-chain 다중 perm 인식+주석 adjacency. 누적 cat-B 25. make test 1238.
- CHG-20260630-0007: DI seam Phase 3 cat-B batch 5 — testconv 4 핸들러(AO 3 명시 actor/conn 인자 + RP 1 TestClient 전환). cat-B 잔여 workflow 확정 14 완결. 동반 테스트 4파일(12 call) 전환. 누적 cat-B 29. make test 1238.
- CHG-20260630-0008: DI seam Phase 3 cat-C — _require_permission 헬퍼 3 핸들러(admin_list/approve/reject_sample_feedback) → require_permission("kb.sample.curate"). 변환기 cata_c_transform.py(RPH). 동반 테스트 7 call 전환. cat-F public_share_view 이연. 누적 cat-B/C 32. make test 1238.
- CHG-20260630-0009: DI seam Phase 3 final migratable — admin_overview(RP)·admin_products_insight_coverage(AO) 회수(동반 테스트 12 call 전환). DI seam byte-동치 가능 핸들러 전부 완료(누적 69). 잔여 ~46 아키텍처 이연(fail-soft 3 + preauth/longpoll/txn 43) 문서화. make test 1238. **Final 이전 완결.**
- CHG-20260630-0010: P5b **Final 시작** — Final-planning workflow(8 agents)로 NS-BOUND=0 도메인 web_context 선행 불요 확정 + route-parity 인프라 갱신(Starlette 1.x _IncludedRouter nest → _walk_routes 재귀) + keywords 도메인 router 추출(src/routers/). make test 전체 통과, route-parity 179 골든 불변, byte-동치. APIRouter 분할 파이프라인 확립.
- CHG-20260630-0011: P5b Final router 추출 #2 — media 도메인 3 DI 핸들러(serve_avatar·serve_product_icon·serve_role_icon) → src/routers/media.py. **실 DI 핸들러 추출 + 골든 순서 갱신** 파이프라인 증명(keywords stub·last-position 과 달리 mid→end 이동). route-parity set 불변(179)·순서만 [45,48,53]→[172-174], var-vs-concrete shadow 위험 없음(끝 이동=가장 늦게 매칭). make test 전체 통과·route drift 0·byte-동치.
- CHG-20260630-0012: P5b Final router 추출 #3 — static_pages 도메인 4 무인증 핸들러(index·admin_index·share_page·healthz) → src/routers/static_pages.py. **test-coupling 보존 패턴 확립**: `import app`+호출시 `app.X` 동적 속성 접근(STATIC_DIR·_HTML_NO_CACHE·FileResponse·_connect_memory·load_memory_kv) → heavily-monkeypatched 헬퍼 + test 의 app.FileResponse 가로채기 계약 보존. Final-planning NS-BOUND=0 분류가 놓친 test_html_no_cache 커플링(핸들러 직접참조+app.FileResponse patch)을 make test 가 즉시 적발 → router app.FileResponse 동적참조 + 테스트 호출 위치 전환으로 byte-동치 해소. 골든 [5-8]→[168-171]. make test 전체 통과·route drift 0.
- CHG-20260630-0013: P5b Final router 추출 #4 — admin_conversations 도메인 1 RP 핸들러(admin_archived_conversations `GET /api/admin/conversations/archived`) → src/routers/admin_conversations.py. **concrete-route 끝-이동 var-shadow 역전 점검 패턴**: archived concrete 4-seg → 선행 var 캡처 점검(`/api/admin/conversations/{var}` 형제 0 + 광역 `/api/admin/{a}/{b}` 매처 0). 동반 테스트 TestClient(perm-gate 403) GREEN=런타임 라우팅 증명. 골든 [127]→[171]. make test 전체 통과·route drift 0·byte-동치.
- CHG-20260630-0014: P5b Final router 추출 #5 — admin_usage 도메인 MIXED 2 핸들러(admin_llm_usage `GET /api/admin/usage` RP ~164줄 + admin_usage_conversations `GET /api/admin/usage/conversations` AO 2-perm) → src/routers/admin_usage.py. **대형 핸들러 verbatim 스크립트 추출(라인슬라이스+화이트리스트 정규식 rewrite) + uniform `import app`+`app.X` 동적참조**(helper-monkeypatch `_query_usage_conversations`·`_usage_account_ids_for_role` 보존). test 직접호출 3 전환(헬퍼 단위테스트·profile 핸들러 무변). 골든 끝-이동. make test 전체 통과·route drift 0·byte-동치.
- CHG-20260630-0015: P5b Final **web_context.py 추출 시작(원래 막혔던 핵심 리팩터)** — ultracode workflow(10 agents, 3 전략 적대판정)로 Strategy B(clean-leaf-move) 확정(A re-export shim·C full-move 는 양 렌즈 `broken`: 순환import/추출가치0). 증분 #1: `_sanitize_session_id`+`_hash_session_token`(stdlib-only leaf, app-internal callee 0) → src/web_context.py(신규, INVARIANT: from app import 금지=단방향 edge). app.py 상단 re-import rebind → 8 호출부+monkeypatch 보존. make test 전체 통과·route drift 0·byte-동치.
- CHG-20260630-0016: P5b Final web_context 추출 증분 #2 — proxy/client-IP 5종(`_TrustedNetwork`·`_parse_trusted_proxies`·`WEB_TRUSTED_PROXIES`·`_is_trusted_proxy`·`_get_client_ip`) → web_context.py. **AGENT_MODE 결합 해소**: 동일 env-read 표현식 mirror 로 app-free 유지(시그니처 불변). startup-validation 블록(ENABLE_WEB_TLS_PROXY)은 app 잔류(재import WEB_TRUSTED_PROXIES 참조). WEB_TRUSTED_PROXIES 계산 위치 이동(둘 다 startup-time, fail-loud 보존). make test 전체 통과·route drift 0·byte-동치. docker rebind-identity 7/7·순환 없음. 후속: inc3 SESSION_COOKIE/_resolve_permission_catalog→inc4 _fetch/_decorate_account_rows(안전) → _account_has_permission/_require_account/_connect_memory(23-테스트 retarget 영역).
- CHG-20260630-0017: origin/main 100-commit 통합 머지(배포 선결). main app.py +720 additive 신규 9 라우트·auth helper 무변(auth-orthogonal)→app.py auto-merge, route_snapshot 충돌→골든 재생성(179→188). make test 전체 통과·route-parity 188.
- CHG-20260630-0018: §18.8 ship-gate 패널(GO·blocking 0) 후속 주석 정정(WEB_TRUSTED_PROXIES fail-loud 순서 low + stale line-num). 코드 무변(주석-only).
- CHG-20260701-0001: 배포 hotfix — 컨테이너 로드(uvicorn web.app:app) 시 추출 모듈 import 실패(ModuleNotFoundError: web_context) 수정. app.py 상단 sys.path append(insert 금지=modules shadow) + app alias. blue-green healthz 게이트가 배포 중 적발(web-b OLD 서빙→프로덕션 무영향). 컨테이너 실기동 검증+make test 575 pass. test-gap: make test/§18.8 이 top-level PYTHONPATH 만 써서 놓침.
- CHG-20260701-0002: Final router 추출 #6 conversations 도메인 10 핸들러(대화 조작, 완전-DI) → routers/conversations.py. AST 경계 추출 + app.X rewrite + stdlib import 보강. **app.py 29,111→28,610줄(~500↓)**, route-parity 188, make test 통과.
- CHG-20260701-0003: Final router 추출 #7 admin_quotas(3)+admin_sample_feedback(3) 완전-DI RP → routers/. app.X(non-_ record_audit_event 포함)+stdlib+test 전환. **app.py 28,610→28,350(~260↓)**, route-parity 188, make test 통과.
- CHG-20260701-0004: Final router 추출 #8(batch 3) admin_console 5 완전-DI(me·permissions·databases·overview·health) → routers/admin_console.py. app.X+from-datetime import+test 전환. **app.py 28,559→28,410**, 골든 192(main graph 4 흡수), make test 통과.
- CHG-20260701-0005: Final router 추출 #9(batch 4) share(2)+system(2) 완전-DI → routers/. 소스텍스트 contract 테스트 전환(4번째 커플링 유형). **app.py 28,410→28,221, 완전-DI 라우트 전부 추출(11 router)**, route-parity 192, make test 통과.
- CHG-20260701-0006: **inline-heavy DI 전환 재개 — admin/metadata 33 핸들러** byte-동치 전환(추출 선행). 도메인 auth helper(`_metadata_resolve_account`류)→`Depends(require_permission("<perm>"))`, perm kb.ingest.manual 27/kb.glossary.curate 3/kb.sample.curate 3. **핵심발견: txn(autocommit)은 독립 `_pg_connect`(PostgreSQL)라 get_conn(MySQL) 무관 → txn 이연 불요.** 이연 1(admin_metadata_suggest: pre-auth 404 gate + 동적 perm). 동반 테스트 4파일(happy 49 account= 주입/403 gate 9 TestClient). §18.8 패널(REV-0006) GO. **behavior-neutral(추출 아님, 핸들러 app.py 잔류)**, make test 1313·0 fail, route-parity 192 불변.
- CHG-20260701-0007: **router 추출 #10 admin/metadata 34 핸들러** → routers/admin_metadata.py(1447줄). inline-heavy 도메인 첫 추출(DI 전환 CHG-0006 선행). tokenize 변환기(whitelist app.X 접두), 테스트 재참조 65+import, 골든 재생성 set-neutral 192. **app.py 28,224→26,734(~1,490↓, 단일 도메인 최대).** make test 1313·0 fail. 학습: mod_syms 튜플-대입 상수 누락→make test NameError 적발→완전 static 재검사.
- 총 변경 횟수: 31

## 4. Dependency Audit (§ web_context 경계 — TASK-0012-3)
plan-eng-review 가 요구한 "handler→전역/helper 매핑" 의 핵심 결과. app.py 는 `Depends()`=0(DI 미사용)이라
handler 가 module-level 전역·helper 를 직접 참조 → router 추출 시 **web_context.py 로 선추출해 양쪽 import** 해야.

**핵심 공통 helper (추출 1순위 — 모든/대부분 router 필요):**
- `_require_account()` — **118 호출**. 인증/account 해석의 linchpin. web_context 필수.
- `_admin_mutation()` — 18. admin 변이 가드. · `_require_permission()` — 7. 권한 체크. · `_admin()` — 7.
- `_json_error()` — 표준 에러 응답. · `_audit_row_to_dict()` — 감사 로그 helper. · db 연결/close helper.

**module-level 전역: 98개** — 대부분 `_`-prefix 상수(`_ARCHIVED_CONV_LIMIT`·`_AUDIT_*`·`_ATTACHMENT_*`·
`_AVATAR_MAX_BYTES` 등 config), 소수 실상태(`_ACTIVE_REQUESTS_LOCK`·`_COLLATION_AUDIT_DONE`·`app`). 상수는
web_context(또는 shared.config 승격)로, 실상태(lock 등)는 단일 인스턴스 보장 필요(추출 시 분열 주의).

**첫 타깃 keywords**(L29476-29492, 4 endpoint 연속 CRUD): 의존 = `_require_account`·`_json_error`·db·
`_audit_row_to_dict` + keywords 도메인 함수. 저결합 → 패턴 증명에 적합.

**경계 권장**: web_context.py = {auth/authz helper 5종 + `_json_error` + `_audit_row_to_dict` + db helper + 상수}.
DI(Depends) 도입은 보류(별건). admin(92)은 추출 최후, sub-domain(users/datasource/metadata/products/audits…)으로.

## 5. Test Status
- 자동: `make test` green — **1236 passed / 2 skipped / 0 fail** (Phase 1 후, 전체 스위트; Phase 0 의 1205 + 신규 31). ruff 통과.
- route-parity: 골든 179 route 불변(Depends 추가/파일럿 전환은 경로/메서드/순서 무영향). `_AuthError` exception handler 등록 production app TestClient 로 end-to-end 확인.
- 신규 회귀 스위트(`test_di_seam_p5b.py` 31): get_conn None-yield / get_current(401·500)·get_optional(no-raise)·require_permission(403·빈가드) 단위 + `_get_authenticated_account(conn,request)` 인자순서 가드 + `_auth_error_handler` 셰이프({"error"}+detail 부재) + 파일럿 end-to-end(authed/force/미인증/conn실패/**auth-raise→500**) + auth deps 라우트 소비 계약(mini-app, route-parity 무영향).
- Phase 1 = behavior-neutral(파일럿 응답 byte-동치). 이후 클러스터 마이그마다 make test+route-parity+401/403/500 회귀 게이트.
- Final 게이트: 브라우저 로그인 QA(PB-0008 `bin/win-browser.py`, 가용 확인) + 라이브 RBAC smoke 4종.

## 6. Blocked Items
- 없음.

## 7. Human Attention Needed
- 다-cycle Critical 라이브-인증 리팩터. helper→web_context 이동/라우터 추출(Final) 머지 전 브라우저 로그인 QA 필수. 클러스터 마이그는 각 게이트(make test+route-parity) 통과 시 자동 진행.
