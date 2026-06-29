---
doc_type: REPORT
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
P5b(app.py 모놀리스 router 분할, Critical) 착수. plan-eng-review(APPROVE-WITH-CONDITIONS) + §12 승인 후,
조건이던 **2개 must-fix 선행물**을 완료: (1) route-parity 안전망 테스트, (2) 의존성 audit. 실제 router 추출은
브라우저 QA(PB-0008) env 가 필요해 후속 세션으로 이월. make test 회귀 0.

## 2. Progress
- Done: plan-eng-review + §12 승인 · route-parity 안전망(`test_route_parity_p5b.py` + 골든 179 route) · 의존성 audit.
- Planned(후속, 브라우저 QA env): web_context.py 추출 → keywords router → … → admin sub-split · 프론트 분할.
- In Progress: 없음.

## 3. Recent Changes
- CHG-20260625-0001: feature-0012 scaffold + route-parity 안전망 테스트/골든 + 의존성 audit (P5b 선행물).
- 총 변경 횟수: 1

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
- 자동: `make test` 회귀 0(전체 green). 신규 `test_route_parity_p5b.py` 포함(골든 179 route 일치 확인).
- 안전망 동작: `app.routes` 정적 열람 → count/set(path+method)/order 비교. TestClient 미사용(startup·DB 불요, `--no-deps` OK).
- 미검증(후속): 실제 router 추출 시 브라우저 QA(PB-0008) — 현 WSL env 불가.

## 6. Blocked Items
- router 추출(TASK-0012-4~7): 완료 게이트 브라우저 QA env 필요(Windows). 안전망/audit 은 무관하게 완료.

## 7. Human Attention Needed
- router 추출 실행 시 브라우저 QA env 세션 + 단위별 §12 재확인(Critical).
