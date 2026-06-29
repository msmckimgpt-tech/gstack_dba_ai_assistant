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
- In Progress: DI seam **Phase 2 batch 1 완료(cat A 19/~95)** — ultracode workflow(72 agents) 2렌즈 적대검증으로 byte-동치 확정 후 19 핸들러 전환, make test progress 1238(baseline 동일)·route-parity 179. batch 2(SQL-heredoc·테스트전환·orphan-try 수정·cat-A 잔여) 진행 예정.
- Planned: Phase 2 잔여 → Phase 3..7 클러스터별 마이그 → helper→web_context 이동 → APIRouter 추출 → 브라우저 로그인 QA+§18.8+배포 → 프론트 분할.

## 3. Recent Changes
- CHG-20260625-0001: feature-0012 scaffold + route-parity 안전망 테스트/골든 + 의존성 audit (P5b 선행물, PR #456).
- CHG-20260629-0002: DI seam 설계(DI_SEAM_BLUEPRINT.md) + Phase 0 가산적 토대(app.py auth DI 의존성 5종 + 예외 핸들러). behavior-neutral, make test green.
- CHG-20260629-0003: DI seam Phase 1 — get_conn None-yield 보정(required 500/optional None) + require_permission 빈 perms 가드 + conftest(TestClient/`as_account`) + 파일럿 get_llm_health DI 전환(byte-동치) + 회귀 스위트 31 + §18.8 적대 패널(REV-0004) HIGH 2 적발·보정. make test 1236 green.
- CHG-20260629-0004: Phase 1 완료 기록 보강(doc-tail bookkeeping, 커밋 ca66ee9 closure).
- CHG-20260629-0005: DI seam Phase 2 batch 1 — cat-A 단순 require 19 핸들러 DI 전환(byte-동치). ultracode workflow 적대검증(REV-0006, 72 agents, 21 확정/3 보류). make test progress 1238(baseline 동일), route-parity 179, `_require_account` 118→99.
- 총 변경 횟수: 5

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
