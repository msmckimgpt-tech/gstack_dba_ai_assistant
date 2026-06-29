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

## REV-20260629-0004 [AGENT-TEAM:p5b-phase1-di-seam-adversarial-panel]
- Related Change: CHG-20260629-0003 (DI seam Phase 1 — 테스트 인프라 + 파일럿 + §18.8 이월 보정)
- 패널 구성: §18.8 적대적 검증 — 5개 독립 lens(byte-equivalence / get_conn-none-yield / test-false-confidence /
  cross-suite-contamination / exception-middleware) 병렬 반증(refute) + finding 별 독립 skeptic 적대 검증
  (Workflow `p5b-phase1-di-seam-adversarial-panel`, 27 agents, 5 lens → 22 findings → finding별 검증 → 확정 11).

**평결: 적발 후 보정 → ACCEPT.** BLOCKING 0. 확정 11건(HIGH 2 + MEDIUM 4 + LOW 5). HIGH 2건은 **실 회귀/테스트
공백**으로 판명되어 즉시 보정했고, MEDIUM/LOW 는 보정 또는 근거 있는 수용 처리. 보정 후 make test 1236 passed/2 skip/0 fail.

### 무엇을 적대 검토했나
Phase 1 diff(app.py get_conn/get_current_account/get_optional_account/require_permission/get_llm_health 5함수 +
신규 conftest.py + test_di_seam_p5b.py)의 "behavior-neutral(파일럿 응답 byte-동치) + deps conn-failure 동치 +
신규 테스트가 동치를 실제 검증하며 기존 1205 스위트 무오염" 주장을 반증 시도. 축: 응답 byte-동치(authed/미인증/
conn실패/auth-raise) / get_conn None-yield 안전 / 테스트 헛통과 / 신규 conftest 의 cross-suite 오염 / 예외핸들러·미들웨어·권한의미.

### 적발 → 보정 (HIGH, 실 결함)
- **HIGH-1 (byte-equivalence, 5 finding 수렴)**: legacy get_llm_health 는 `_get_authenticated_account` 를 직접
  (except 없이) 호출 → **conn-open + 인증쿼리 raise → 500 전파**. 최초 Phase 1 구현은 인증을 get_optional_account
  (모든 예외 except→None)에 위임 → 같은 경로가 **200 cheap-read 로 변형**(라이브 인증/DB 장애를 health 가 정상으로 은폐).
  **근본 사실: legacy get_llm_health 는 get_optional_account-shaped 가 아니다**(conn-acquire-fail 만 fail-soft, auth-query-raise 는 fail-loud).
  → **보정**: 파일럿을 `Depends(get_conn)` + inline `_get_authenticated_account` 로 재전환(None→200·미인증→200·
  auth-raise→500·인증→probe legacy byte-동치). 회귀 가드 `test_llm_health_auth_query_raises_propagates_500` 추가
  (Starlette generic 500 plain-text "Internal Server Error" 셰이프 단언 — 패널의 `{"detail"}` 표기는 부정확, 실제는 plain text).
- **HIGH-2 (test-false-confidence)**: `_get_authenticated_account(conn, request)` 인자 순서(app.py docstring 이 footgun
  명시)를 검증하는 테스트가 0 — swap 해도 전 테스트 통과(라이브선 conn.cookies AttributeError→500). shipped 코드는
  올바른 순서이나 회귀 가드 부재. → **보정**: get_current_account/get_optional_account 에 duck-typed 인자순서 가드
  테스트 2건 추가(위치1=conn[.cookies 없음]/위치2=request[.cookies 보유] 단언).

### 적발 → 보정/수용 (MEDIUM/LOW)
- **MEDIUM #6 (auth deps 라우트 e2e 커버리지 0)**: get_current_account/require_permission 가 라우트에서 소비될 때의
  401/403/500 계약이 end-to-end 미검증(Phase 1 은 파일럿 1개라 내재적). → **보정**: throwaway mini-app(FastAPI +
  _AuthError 핸들러 등록 + Depends(dep) 라우트)로 401/403/500/200 계약을 production 라우트 무변경(route-parity 무영향)으로
  end-to-end 고정(6 테스트). Phase 2 마이그 계약을 선검증.
- **LOW #9 (autouse clear)**: dependency_overrides 전체 clear → 단일소비자 전제 smell. → **보정**: snapshot/restore 로 교체.
- **LOW #8/#11 (conn 보유시간)**: 파일럿이 get_conn 계약상 conn 을 요청 teardown(probe 최대 8s 포함)까지 보유 —
  관측 응답 불변. **수용**: §1.1 이 sanction 한 shared get_conn design tradeoff. probe 는 TTL-skip 으로 대부분 즉시
  반환해 실보유 희박. docstring 에 명시. 문제화 시 후속 special-case 가능.
- **LOW #10 (stale .pyc)**: make test 의 worktree bind-mount 에서 stale .pyc 가 핸들러 미등록처럼 보일 환경성 취약성.
  코드 결함 아님. **수용**: 컨테이너는 --rm 신규 기동 + pip 신규 설치, 소스 mtime 갱신 시 재컴파일. 문제화 시 PYTHONDONTWRITEBYTECODE.

### 왜 최종 통과인가 (결정적 근거)
- 파일럿 4경로(authed=probe / 미인증=200 / conn실패=200 / auth-raise=500) + deps 계약(401/403/500) 모두 회귀
  테스트로 legacy byte-동치 고정. route-parity 179 불변, make test 1236 passed/2 skip/0 fail, ruff clean.
- get_conn None-yield 는 required(→500)·optional(→None) 양 소비자에서 byte-동치 검증, teardown(None 시 close 미시도) 안전.
- 신규 conftest 는 autouse snapshot/restore 로 production app overrides 격리, mini-app 은 로컬 인스턴스라 기존 스위트 무오염(make test 1205→1236 회귀 0).

## REV-20260629-0005 [SKIPPED:doc-tail-bookkeeping]
- Related Change: CHG-20260629-0004 (Phase 1 완료 기록 보강 — TASK.md Completion Checklist 2줄 [x] 마킹)
- §18.8 Adversarial Panel: **SKIPPED — doc-only/bookkeeping.** 본 변경은 이미 커밋·검증된 Phase 1(ca66ee9,
  make test 1236 passed)의 완료 사실을 TASK.md 에 사후 기록할 뿐. 프로덕션 src·런타임·이미지·테스트 무변경
  → 적대 패널 표적(import 깨짐·런타임·배포·byte-동치 회귀) 부재. Phase 1 코드 자체의 적대 검증은
  REV-20260629-0004(AGENT-TEAM, 27 agents/5 lens, HIGH 2 적발·보정)에서 이미 완료.
- 검증(결정적): TASK.md 2줄 diff 만(`[ ]`→`[x]` + 커밋 해시·push 범위 기재). git diff 로 doc-only 확인,
  코드 changeset 0. route-parity·make test 무영향.

## REV-20260629-0006 [AGENT-TEAM:p5b-phase2-cata-batch1-adversarial-panel]
- Related Change: CHG-20260629-0005 (Phase 2 batch 1 — cat-A 단순 require 19 핸들러 DI 전환)
- §18.8 Adversarial Panel: **AGENT-TEAM (ultracode workflow `p5b-phase2-cata-plan`, 72 agents / 2.37M tokens).**
  파이프라인: cat-A 후보 24개 → 핸들러별 정밀 분석(실제 app.py 코드 + DI seam + blueprint 정독, 마이그 spec·동반 테스트 식별)
  → 핸들러별 **2렌즈 적대 반증**(렌즈A=순서/conn수명/트랜잭션 — pre-auth gate 로 인한 401 우선순위 역전·close 후 conn 재사용·autocommit 토글 적발; 렌즈B=에러셰이프/응답/account/부수효과 — _AuthError 셰이프 동치·HTTPException 회귀·비-JSON 응답·account dict 충족·set_cookie/redirect 보존). "통과가 아니라 결함 적발", 불확실 시 refuted=true(보수적).
- 결과: **21 확정(양 렌즈 모두 refuted=false, severity NONE)** / **3 보류**.
  - 보류 BLOCKING×2(mark_conversation_read L15372, profile_llm_usage L28735): 런타임은 byte-동치이나 자동 생성 edit-spec 이 외곽 `try:` 를 남겨(finally 만 제거) `SyntaxError: expected except/finally` 유발 — py_compile 재현 확인. → batch 2 수작업 edit 로 재처리.
  - 보류 HIGH×1(list_conversation_attachments L17128): 런타임 동치(렌즈B PASS)이나 동일 try/finally 구조 edit 결함. → batch 2.
- 적용: 확정 21 중 19 적용. 제외 2 — list_conversation_shares(본문 flush-left SQL heredoc 으로 일괄 dedent 불가, batch 2 수작업), profile_usage_conversations(동반 테스트 직접호출 전환 동반, batch 2). 자동 edit-spec 의 try/finally 구조 누락 위험은 **신뢰하지 않고** 보수적 구조 변환기(`cata_transform.py`: 정확 패턴만 변환·SQL heredoc/inline-close/복수 conn skip) + py_compile + sanity 검사(시그니처/잔류 보일러플레이트/conn 사용)로 대체.
- 검증(결정적): make test **progress-chars 1238 = baseline 동일**(테스트 수 불변·skip 동일·0 FAIL/ERROR, exit 0), route-parity 179 불변(Depends 추가는 경로/메서드/순서 불변), ruff clean(serve_avatar/role_icon 의 login-gate-only unused account-arg 는 비차단), py_compile OK, `_require_account` 호출 118→99(-19, 정확). 동반 테스트(getsource/AST 도메인-문자열 단언)는 auth/conn 패턴 미참조 확인 → 무영향.
- NIT/수용: serve_avatar/serve_role_icon 의 `account` param 본문 미사용(login-gate 전용) — FastAPI 표준 패턴, ruff 비차단. 수용.
