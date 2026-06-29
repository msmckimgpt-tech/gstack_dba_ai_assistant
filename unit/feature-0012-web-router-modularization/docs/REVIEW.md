---
doc_type: REVIEW
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260625-0001 [SKIPPED:test-only-route-parity-safety-net]
- Related Change: CHG-20260625-0001 (route-parity 안전망 + 의존성 audit, P5b 선행물)
- §18.8 Adversarial Panel: **SKIPPED — test-only/비핵심경로.** 본 cycle 의 코드 변경은 **추가 테스트 1건**
  (`test_route_parity_p5b.py`, `app.routes` 정적 열람)과 골든 JSON·doc 뿐. 프로덕션 src·런타임·이미지 무변경
  → 적대 패널 표적(import 깨짐·런타임·배포 회귀) 부재. (실제 router 추출 시점에는 추출 단위마다 §18.8 패널 +
  브라우저 QA 적용 — 후속.)
- 검증(결정적): 안전망 테스트가 현재 app(179 route)과 골든 일치 시 통과(make test 회귀 0), 인위적 경로/메서드/
  순서 drift 시 fail 하도록 set·order 비교 구현. TestClient 미사용(startup 훅·DB 발화 회피, `--no-deps` 동작) 확인.

## REV-20260625-0002 [SUBAGENT:p5b-plan-eng-review-critical]
- Related Change: P5b 실행 계획(plan-review gate, ROADMAP ITEM-P5b "plan-review(Critical)" 충족)
- 검토: plan-eng-review(eng-manager mode). 대상 = app.py(29.5K/178 route/0 APIRouter) 도메인 router 점진 분할 계획.
- **VERDICT: APPROVE-WITH-CONDITIONS.** 접근(점진 strangler·FastAPI APIRouter built-in[Layer1]·router당 commit
  reversible·behavior-neutral)은 견고.
  - **must-fix 2 (실행 전)**: (T1) route-level 테스트 격차 — 60 테스트 중 HTTP-route 레벨 ~0 → route-parity 안전망
    선구축(본 cycle 완료). (A1) 의존성 audit — `Depends()`=0+전역 98 → web_context 경계 확정(본 cycle 완료).
  - **A2**: route 등록 순서 민감(`{var}` vs 구체경로 충돌) → 안전망이 order diff 포함.
  - **A3**: startup 훅 9(deprecated) + lifespan 은 app 잔류, on_event→lifespan 은 scope 밖.
  - 결정: web_context 모듈(DI 보류)·첫 타깃 keywords·admin 최후 sub-split·프론트 별건·route-parity HARD 게이트.
- 전문: 계획+리뷰리포트 = 본 cycle 작업 산출(scratchpad P5b-PLAN.md 의 GSTACK REVIEW REPORT). 
- Human Approval: §12 승인 획득(2026-06-25). router 추출 실행은 브라우저 QA env + 단위별 재확인.

## REV-20260629-0003 [AGENT-TEAM:p5b-phase0-di-seam-adversarial-panel]
- Related Change: CHG-20260629-0002 (DI seam Phase 0 — 가산적 토대)
- 패널 구성: §18.8 적대적 검증 — 3개 독립 lens(behavior-neutrality / 동치성 / 엣지·회귀) 병렬 반증(refute) + 의장 합성(Workflow `p5b-phase0-adversarial-panel`, 4 agents).

**평결: ACCEPT** — 3개 lens 전원 `refuted_neutrality=false`(중립성·동치성 반증 실패), 의장 독립 검증으로 확정.

### 무엇을 적대 검토했나
Phase 0 diff(app.py L29 `Depends` import + L10269~10341 seam: `_AuthError` 클래스, `@app.exception_handler` 등록, `get_conn`/`get_current_account`/`get_optional_account`/`require_permission`)의 "관측가능 런타임 변화 0(가산적)" 주장을 반증 시도. 축: import-time 부수효과 / exception handler 의 기존 요청·CORS·TrustedHost 간섭 / 신규 deps↔legacy helper 동치 / get_conn teardown / route·OpenAPI 불변 / 401·403 응답 byte-동치.

### 왜 통과인가 (결정적 근거)
- **신규 deps = dead code**: 어떤 route 핸들러도 미사용(dependant graph walk=[]). 인가 호출 6건은 별개 legacy `_require_permission` — grep 확인.
- **_AuthError 도달 불가**: raise 사이트는 미사용 deps 내부뿐. `_AuthError.__mro__` 에 기존 예외 미포함 → Starlette MRO lookup 이 HTTPException/RequestValidationError 에 기존 핸들러 그대로 반환. 등록 핸들러 1개.
- **import-time 무부수효과**: get_conn 은 generator(본문 미실행), `Depends()` 마커는 연결 미개방. app=FastAPI@706 선정의로 forward ref 정합.
- **검증 정합**: route-parity 골든 179 불변, OpenAPI 143 paths 불변, make test 1205 passed/2 skip/0 fail. 라이브 TestClient: TrustedHost 400·standard 404 셰이프 무변.
- **동치성(활성화 대비)**: get_current_account=`_get_authenticated_account(conn,request)` 동일 인자순서→falsy→`_AuthError(401)`→핸들러 `{"error":msg}` = legacy `_json_error` byte-동일. get_optional_account=try/except→None fail-soft 동일(LastSeen 부수효과 보존). require_permission=401 선행 후 `_account_has_permission`(.get, 동적 catalog) 검사.

### 결함 (latent — Phase 0 중립성 반증 아님, **Phase 1 first-class 이월**)
- **HIGH(latent)**: get_conn 이 `_connect_memory()` 실패를 try/except 로 감싸지 않음. legacy 핸들러는 conn 획득 실패 시 `_json_error("db connection failed", 500)`(다수 사이트). 소비자가 get_conn 으로 전환하면 DI resolution 중 raise 가 _auth_error_handler 를 우회 → Starlette generic 500(`{"detail":"Internal Server Error"}`) 회귀. **Phase 0 미사용이라 무영향. Phase 1 첫 소비자 전환 전 반드시 해소**(conn-failure 메시지 다양성 분석 동반 — 마이그 작업).
- **LOW(footgun)**: `require_permission()` 무인자 호출 시 인증만 통과 → 마이그 시 빈 perms assert/lint 가드 권고.

### 이월 (Phase 1 착수 전/중)
1. get_conn `_connect_memory()` 실패 → curated 500 동치 정합(HIGH, 첫 소비자 전 필수).
2. `_AuthError` 실제 raise / deps wire 시 응답 셰이프 동치(401 `{error}` vs `_json_error`, 422 ordering) 별도 golden/회귀 테스트.
3. require_permission 빈 perms 가드(LOW).
4. 마이그 전환 사이트마다 dependency_overrides 단위테스트로 401/403 body byte-동치 + LastSeen UPDATE 부수효과 보존 검증.
