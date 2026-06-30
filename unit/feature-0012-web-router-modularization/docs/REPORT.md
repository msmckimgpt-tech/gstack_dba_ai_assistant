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
- 총 변경 횟수: 17

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
