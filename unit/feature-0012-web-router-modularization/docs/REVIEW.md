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

## REV-20260629-0007 [AGENT-TEAM:p5b-phase2-cata-batch2-deferred-completion]
- Related Change: CHG-20260629-0006 (Phase 2 batch 2 — REV-0006 보류 5 핸들러 마무리)
- §18.8 Adversarial Panel: **AGENT-TEAM (REV-20260629-0006 워크플로 재사용 + edit-spec 수정 검증).**
  본 5 핸들러의 byte-동치 적대검증은 REV-20260629-0006(72 agents, 2렌즈) 에서 이미 완료됨 — 5건 모두 verdict SAFE(렌즈 B 불변식 PASS). batch 1 에 포함 못 한 사유는 *런타임 안전성*이 아니라 *자동 생성 edit-spec 의 구조 결함*:
  - mark_conversation_read / list_conversation_attachments / profile_llm_usage: 외곽 `try:` 를 남긴 채 `finally:` 만 제거하는 spec → orphan-try SyntaxError(워크플로 BLOCKING/HIGH 반증, py_compile 재현). 본 cycle 에서 구조 변환기(body try+finally 동시 제거·dedent)로 정확히 재처리 → py_compile OK.
  - list_conversation_shares: flush-left SQL heredoc 으로 일괄 dedent 불가 → 변환기 verbatim 보존 + SQL 공백 byte-exact 원복.
  - profile_usage_conversations: 동반 테스트 직접호출 → TestClient 전환 동반.
- 결정적 검증(byte-동치 재확인): make test **progress-chars 1238 = baseline 동일**(전환된 test_p1 포함·0 FAIL/ERROR·exit 0), route-parity 179 불변, ruff clean, py_compile OK. sanity(시그니처 Depends/잔류 _require_account·conn.close·_connect_memory 0/conn 사용) PASS. `_require_account` exact-anchor 88→64(누적 -24, batch1 19 + batch2 5).
- 보류→해소 입증: 워크플로의 "verdict SAFE but edit-spec refuted" 분리가 정확했음 — 런타임 동치는 옳고 edit 처방만 결함이었으며, 구조 변환기로 처방을 교정하니 동일 동치가 make test 로 확정됨.
- NIT/수용: profile_llm_usage/profile_usage_conversations 의 `conn` param 본문 미사용(auth 전용, body 는 PG) — get_conn use_cache 로 get_current_account 와 공유, ruff 비차단. 수용.

## REV-20260630-0001 [AGENT-TEAM:p5b-phase2-cata-batch3-multiclose-panel]
- Related Change: CHG-20260630-0001 (Phase 2 batch 3 — P2_MULTI_CLOSE 10 핸들러)
- §18.8 Adversarial Panel: **AGENT-TEAM (ultracode workflow `p5b-phase2-cata-batch3-plan`, 44 agents / 1.42M tokens).**
  잔여 22 cat-A 후보를 핸들러별 정밀 분석(실제 코드 + DI seam 정독) → 3패턴 분류(P1 pre-auth gate / P2 multi-close / P3 edge) + strategy 결정 → 핸들러별 **2렌즈 적대 반증**(렌즈A 순서/컴파일/conn수명 — pre-auth gate 로 인한 401 우선순위 역전·orphan-try·산재 close 누락·복수 conn; 렌즈B 에러셰이프/응답/account/부수효과). 불확실 시 refuted=true.
- 결과: **10 확정(P2_MULTI_CLOSE, CATA_MULTICLOSE)** / **12 보류**.
  - 확정 10: use_conversation, history, history_dates, delete_conversation, delete_conversations, cancel_request, finalize_request, get_file, ask_status, me_get_system_prompt. 일부 LOW verdict 있었으나 **실결함 아님**(렌즈가 명시: "실행 영향 없는 prose 산술 오류" 등 — refuted=false).
  - 보류 12: pre-auth gate 10(P1, KEEP_INLINE_DEFER — conn 이전 404/400 early-return 이 Depends auth hoisting 시 401 보다 먼저 나가던 순서를 역전시킴 → cat-A 부적격), ask_result(P3 EDGE — 복수 _connect_memory 재취득), history_anchor(P2 분류는 정확하나 한 렌즈 HIGH refute → 보수적 보류, batch 4 재조사).
- 적용 정확성(자동 edit-spec 불신, 구조 변환기 사용): P2 전용 변환기(`cata_p2_transform.py`)가 산재 conn.close() 전부 제거 + auth 블록 제거 + Depends 삽입(dedent 불요). 단 ask_status 는 terminal `finally: conn.close()` 하이브리드 — conn.close 가 finally 유일 내용이라 변환기로 제거 시 빈 finally(IndentationError, py_compile 재현) → 수작업으로 try/finally 제거+본문 승격. history/history_dates multi-line sig → 변환기 sig_insert multi-line 보강. sole-in-block close 사전 스캔으로 ask_status 만 격리해 수작업한 것이 정확.
- 결정적 검증: make test **progress-chars 1238 = baseline 동일**(전환 T1/T3 포함·0 FAIL/ERROR·exit 0), route-parity 179 불변, ruff clean, py_compile OK. sanity(시그니처 Depends/잔류 _require_account·conn.close·_connect_memory 0) PASS. `_require_account` exact-anchor 64→54. 잔류 직접호출 0(grep) 확인.
- 동반 테스트: history_dates 의 T1(PG 라우팅)/T3(legacy MySQL) 직접호출 → TestClient(as_account) 전환, conn=mem 유지로 mem.cursor_calls 가드 보존. T2(history_anchor 미마이그) 직접호출 유지. 나머지 9 무영향.

## REV-20260630-0002 [AGENT-TEAM:p5b-phase2-batch4-history_anchor-refute-resolution]
- Related Change: CHG-20260630-0002 (Phase 2 batch 4 — history_anchor + cat-A 마무리)
- §18.8 Adversarial Panel: **AGENT-TEAM (REV-20260630-0001 batch3 워크플로 재사용 + HIGH refute 근본원인 해소).**
  history_anchor 는 batch3 워크플로(44 agents)에서 P2_MULTI_CLOSE 로 정분류됐고 한 렌즈가 byte-동치/컴파일/순서 보존을 모두 확인했다. **HIGH refute 의 유일 사유는 마이그 위험이 아니라 동반 테스트 T2(test_history_anchor_returns_pg_id)의 TestClient 전환이 edit_plan 에서 누락(needs_conversion 미지정)된 것** — 렌즈가 "핸들러 마이그 자체는 OK, 다만 T2 가 직접호출이라 마이그 후 Depends 마커가 기본값으로 새어 false-confidence(우연 통과) 상태로 남고 §18.8 검증을 못 한다"고 명시(BLOCKING 아님 = hard-fail 아님, 그래서 HIGH).
- 해소: history_anchor 를 P2 변환기로 마이그(multi-line sig + 6 산재 close 제거, sole-in-block 없음 확인) + **T2 를 `client.get`+`as_account` override 로 전환**(conn=mem 유지로 cursor_calls/HH24:MI SQL 가드 보존). refute 의 근본원인(테스트 전환 누락) 직접 제거.
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. sanity(시그니처 Depends/잔류 0/pg.close 보존) PASS. `_require_account` exact 54→53.
- cat-A 잔여 11 이연 판정(아키텍처): pre-auth gate 10(401 우선순위 역전 + conn eager-open 부수효과), ask_result(long-poll 60s conn-hold) — DI seam 으로 byte-동치 불가, router-extraction 단계 재구조화. 워크플로 KEEP_INLINE_DEFER/EDGE_DEFER 판정이 정확했음을 코드 정독으로 재확인.

## REV-20260630-0003 [AGENT-TEAM:p5b-phase3-catb-batch1-require-permission-panel]
- Related Change: CHG-20260630-0003 (Phase 3 cat-B batch 1 — require+perm 6 핸들러)
- §18.8 Adversarial Panel: **AGENT-TEAM (ultracode workflow `p5b-phase3-catb-plan`, 67 agents / 2.22M tokens).**
  clean-AND cat-B 23 후보를 핸들러별 분석(perm 코드·각 실패 메시지 정확 인용·status·AND/OR·resource-의존·perm-before-resource) → migratability(REQUIRE_PERMISSION/ACCOUNT_ONLY/DEFER) 결정 → 2렌즈 적대검증(렌즈A 메시지 byte-보존[BLOCKING-1]·perm-before-resource 순서·동적 catalog·AND/OR 의미; 렌즈B 401≺403 순서·셰이프·orphan-try·동반 테스트 needs_conversion). 결과 15 확정 / 8 보류.
- batch1 적용 6 (sole-in-block conn.close() 부재): RP 4 + AO 2. 검증 사항:
  - **403 메시지 byte-보존**: RP 시그니처의 message= 를 워크플로 전사가 아니라 *실제 제거되는 perm-블록의 `_json_error` 문자열 리터럴에서 정규식 verbatim 추출* — 전사 오류 위험 0. admin_me/admin_permissions/admin_list_available_databases="관리 콘솔 접근 권한이 필요합니다.", new_conversation=기본값("권한이 없습니다.") 라 message= 생략. 확정 def 시그니처로 일치 확인.
  - **순서**: require_permission 이 get_current_account(→get_conn) 의존 → 401 이 403 보다 선행 자동 보존; perm-게이트가 인증 직후·resource 로딩 전(perm_before_resource=true)이라 hoist 가 순서 불변. new_conversation 2차 resource-의존 검사(_account_has_product_access)는 본문 유지(메시지 "요청을 수행할 수 없습니다." byte-보존).
  - **AO**: conversations/admin_list_products 는 복수 perm/다른 메시지라 account-only + 본문 검사 유지(require_permission 단일 메시지로 뭉치면 메시지 회귀). 변수명 actor 자동 감지.
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. sanity(시그니처 Depends/require_permission/잔류 _require_account·conn.close 0/RP perm 본문 제거·AO perm 본문 유지) PASS. account-anchor 53→47. 직접호출 동반 테스트 0(grep).
- batch2 분리(9, sole-in-block conn.close): public_share_fork·upload/delete_product_icon·admin_llm_usage·admin_get_dashboard_prefs·verify_audit_chain·admin_health_attachment_grants(본문 finally:conn.close 또는 try:conn.close try/except-pass) — 마이그 자체는 byte-correct(워크플로 확정)이나 conn.close 가 블록 유일 내용이라 단순 제거 시 빈 블록 → try/finally(또는 try/except) 제거+dedent 가 추가 필요. + admin_list_datasources·admin_datasource_databases(AO, 본문 finally:conn.close). 워크플로 보류 8(동반 테스트 전환 누락 5·action분기·fail-soft)도 batch2+.

## REV-20260630-0004 [AGENT-TEAM:p5b-phase3-catb-batch2-wrap-panel]
- Related Change: CHG-20260630-0004 (Phase 3 cat-B batch 2 — WRAP-style RP 5 핸들러)
- §18.8 Adversarial Panel: **AGENT-TEAM (REV-20260630-0003 cat-B workflow, 67 agents) 재사용.** 본 5 핸들러는 REV-0003 에서 REQUIRE_PERMISSION 으로 확정·byte-동치 적대검증 완료된 것들이며, batch1 에 못 넣은 사유는 *런타임 위험이 아니라* 외곽 try/finally:conn.close() WRAP 구조라 변환기 WRAP 경로(try/finally 제거+dedent)가 필요했기 때문.
- 적용: WRAP 경로로 외곽 try/finally 제거 + 본문 dedent + perm-게이트 hoist(require_permission) + 산재 conn.close 제거. 403 메시지는 제거되는 perm-블록 `_json_error` 에서 verbatim 추출(byte-보존): public_share_fork="요청을 수행할 수 없습니다.", upload/delete_product_icon="제품 관리 권한이 필요합니다 (product.manage).", verify_audit_chain="감사 무결성 검증 권한이 필요합니다."(var=actor), admin_health_attachment_grants="요청을 수행할 수 없습니다.". 확정 def 시그니처로 메시지 일치 확인.
- 동반 테스트: delete_product_icon 직접호출+_require_account 패치(test_avatar_icon_upload::test_a1_product_icon_delete_requires_manage) → TestClient(client.delete + as_account(perms={"console.access":True}))로 전환. require_permission 미override 라 실제 _account_has_permission 검사를 타 403 보존. 나머지 4 직접호출 0.
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. sanity(require_permission sig/잔류 _require_account·conn.close 0) PASS. 직접호출 0(grep).
- batch3 잔여 4: admin_llm_usage·admin_get_dashboard_prefs(본문 `try: conn.close() except: pass` → try/except 제거), admin_list_datasources·admin_datasource_databases(AO 본문 finally:conn.close → try/finally 제거+dedent). + 워크플로 보류 8.

## REV-20260630-0005 [AGENT-TEAM:p5b-phase3-catb-batch3-sole-in-block-panel]
- Related Change: CHG-20260630-0005 (Phase 3 cat-B batch 3 — sole-in-block conn.close 4 핸들러, cat-B 확정 15 완결)
- §18.8 Adversarial Panel: **AGENT-TEAM (REV-20260630-0003 cat-B workflow, 67 agents) 재사용.** 4 핸들러는 REV-0003 에서 확정·byte-동치 적대검증 완료분이며, batch1/2 미적용 사유는 *런타임 위험이 아니라* 본문 sole-in-block conn.close(빈 블록 IndentationError 위험) 처리가 필요했기 때문.
- 적용: (1) admin_llm_usage·admin_get_dashboard_prefs 는 외곽 finally 가 FB-form(`finally: try: conn.close() except: pass`) — WRAP 경로가 FB 인식·제거(이전 스캔의 "after try:" 오분류 정정). (2) admin_list_datasources·admin_datasource_databases 는 본문 try/finally:conn.close wrapper — 변환기 신규 `strip_conn_finally`(matching-try 역추적+try/finally 제거+try-body dedent, FA/FB 지원, cur/pg.close 미대상) 로 처리. RP 메시지 verbatim 보존, AO perm 검사 본문 유지(conn body 사용 유지).
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. sanity(시그니처 Depends/require_permission|get_current_account/잔류 _require_account·conn.close 0) PASS. 직접호출 0(grep). **cat-B workflow 확정 15 전부 완료.**
- 잔여 cat-B: workflow 보류 8(동반 테스트 전환 누락 5: admin_test_datasource·admin_product_db_insights·admin_usage_conversations·admin_archived_conversations·admin_overview — 마이그 byte-correct 이나 직접호출 테스트 전환 필요; action-분기 admin_get_system_prompt; fail-soft suggestions; admin_products_insight_coverage) + AND pre-auth gate/multi(인벤토리상 ~18) + OR·BRANCH 23. → cat C/D/E/F/트랜잭션.

## REV-20260630-0006 [AGENT-TEAM:p5b-phase3-catb-batch4-orchain-panel]
- Related Change: CHG-20260630-0006 (Phase 3 cat-B batch 4 — no-flag 10 핸들러)
- §18.8 Adversarial Panel: **AGENT-TEAM (ultracode workflow `p5b-phase3-catb-plan` 재실행, 49 agents / 1.63M tokens).** cat-B 잔여 no-flag 17 후보 분석+2렌즈 적대검증 → 14 확정/3 보류. batch4 = 확정 14 중 동반 테스트 직접호출 전환 불요 10.
- 확정 분류·검증: RP 5(OR-of-negations AND 게이트 → require_permission 다중 perm hoist, 메시지 verbatim) + AO 5(복수 perm/다른 메시지/OR/action-분기 → account-only + 본문 검사 유지). admin_accounts/roles 메시지("관리 콘솔 조회 권한이 필요합니다."/"역할 조회 권한이 필요합니다."), quota 3종 메시지 verbatim 보존. admin_get_system_prompt 는 scope별 4종 perm 분기라 AO(본문 유지).
- 변환기 보강: (1) RP perm-블록 검출에 OR-of-negations 다중 perm 인식(`if not ahp(a) or not ahp(b):` → require_permission("a","b")), (2) auth-perm adjacency 에 주석 허용(quota 핸들러의 TASK 설명 주석). 메시지·status 는 코드에서 verbatim 추출(전사 의존 0).
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. sanity(시그니처 Depends/require_permission|get_current_account/잔류 _require_account·conn.close 0) PASS. 직접호출 0(grep).
- batch5 분리(4, 동반 테스트 전환 필요): admin_test_datasource(concurrency 테스트)·admin_product_db_insights·admin_usage_conversations(AO)·admin_archived_conversations(RP). 보류 3: suggestions(fail-soft 비-cat-B)·admin_products_insight_coverage·admin_overview(적대 보류 — batch5+ 재검토).

## REV-20260630-0007 [AGENT-TEAM:p5b-phase3-catb-batch5-testconv-panel]
- Related Change: CHG-20260630-0007 (Phase 3 cat-B batch 5 — testconv 4 핸들러)
- §18.8 Adversarial Panel: **AGENT-TEAM (REV-20260630-0006 cat-B 잔여 workflow, 49 agents) 재사용.** 4 핸들러는 REV-0006 확정·byte-동치 검증분이며 batch4 미적용 사유는 동반 테스트가 핸들러 직접호출이라 전환 필요(needs_conversion=true).
- 적용 + 테스트 전환 패턴(핵심: RP vs AO 차이):
  - AO 3(admin_test_datasource[actor]·admin_product_db_insights·admin_usage_conversations): perm 검사 본문 유지 → 동반 테스트 직접호출에 `actor|account={...}, conn=<fake>` 명시 주입(Depends 기본값 직접 전달). body perm 검사가 그 account 로 실행되어 403/404/400/200 보존. admin_test_datasource concurrency 테스트(asyncio.gather)는 TestClient(sync) 부적합 → 직접 coroutine 호출 유지 + 명시 인자.
  - RP 1(admin_archived_conversations): perm 이 require_permission 의존성으로 이동 → 직접호출+명시 account 는 require_permission 을 *우회*해 403 재현 불가 → test_p1 을 TestClient(client.get+as_account(perms={"console.access":True}))로 전환. require_permission 이 실제 검사를 타 403 보존.
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. 잔류 직접호출 0(grep). **cat-B 잔여 workflow 확정 14 전부 완료(누적 cat-B 29).**
- 보류 3(재검토): suggestions(fail-soft), admin_products_insight_coverage·admin_overview(적대 보류). cat-B preauth/longpoll ~32 = cat-A preauth 와 동일 아키텍처 이연.

## REV-20260630-0008 [AGENT-TEAM:p5b-phase3-catc-rph-self-review]
- Related Change: CHG-20260630-0008 (Phase 3 cat-C — _require_permission 헬퍼 3 핸들러)
- §18.8 Adversarial Panel: **SELF+구조 검증(SUBAGENT 미dispatch — cat-C 3 핸들러는 동일·단순 패턴이고 byte-동치 논리가 결정적, 직접 코드 정독+gate 로 충분).** _require_permission(request,conn,perm) = _require_account → if not _account_has_permission(account,perm): _json_error("권한이 없습니다.",403). require_permission(perm) DI 의 dep = get_current_account → _account_has_permission 검사 → _AuthError(기본 "권한이 없습니다.",403). **메시지·status·셰이프 1:1**(기본 메시지 일치라 message= 생략). 401(미인증)이 403(perm) 선행도 require_permission→get_current_account 의존 체인으로 자동 보존.
- 검증 포인트: (1) cat-C 의 인증-전용 try/finally(body 미포함)는 auth conn 을 즉시 닫고 본문은 자체 mconn(audit)·pg(작업) 사용 → conn=Depends 불요(auth conn held-until-teardown 회피, 추가 idle conn 0). 본문의 conn 참조는 전부 주석(코드 NameError 없음, grep 확인). account 는 sig 에서 공급(record_audit_event actor). (2) 동반 테스트 RP(require_permission 의존성) 특성상 perm-gate 403 은 TestClient 필수(직접호출 우회), happy 는 명시 account 우회 — core-미호출 단언(promote/reject False) 은 require_permission 이 body 이전 403 이라 보존.
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. sanity(require_permission sig/잔류 _require_permission·conn.close 0) PASS.
- cat-F(public_share_view) 이연 판정: _optional_account 본문-중간 호출의 LastSeenAt eager-resolution 부수효과 차이 → 보안 민감 익명 엔드포인트라 router-extraction 이연(보수적).

## REV-20260630-0009 [AGENT-TEAM:p5b-phase3-final-migratable-recovery]
- Related Change: CHG-20260630-0009 (cat-B 보류분 회수 2 핸들러 — Final 이전 migratable 완결)
- §18.8 Adversarial Panel: **AGENT-TEAM (REV-20260630-0006 확정분 재사용 + 종합 잔여 survey).** admin_overview·admin_products_insight_coverage 는 REV-0006 에서 byte-correct 확정됐으나 동반 테스트 전환 누락(needs_conversion)으로 보류된 것. 본 cycle 에서 테스트 전환으로 회수.
- 종합 survey(결정적): 남은 *모든* 인증-route 핸들러를 버킷 분류(MIGRATABLE vs DEFER). 결과 MIGRATABLE 5 중 2(admin_overview·admin_products_insight_coverage) 회수, 3(progress·suggestions·public_share_view) 은 개별 코드 정독으로 **이연 확정**: progress/suggestions 는 conn/auth/perm 실패를 *fail-soft 200*({"items":[]}/empty)로 흡수 → get_current_account(미인증 401·conn 실패 500 raise)로 전환 시 **fail-soft→error 회귀**(비동치); public_share_view 는 _optional_account 가 share-load·404/410 게이트 *뒤* 호출이라 get_optional_account hoisting 시 LastSeenAt 세션 부수효과 eager 화. 셋 다 DI seam 으로 byte-동치 불가 → router-extraction 이연.
- 테스트 전환 검증: admin_overview(RP) happy 6=명시 actor/conn(위젯 게이팅 본문 _account_has_permission 보존), perm-gate 1=TestClient(require_permission 403); admin_products_insight_coverage(AO) 5=명시 account/conn(본문 perm 검사가 account 로 실행, 403 포함). _install acct 반환 보강.
- 결정적 검증: make test progress-chars 1238 = baseline 동일·0 FAIL/ERROR·exit 0, route-parity 179 불변, ruff clean, py_compile OK. 미전환 직접호출 0(grep).
- **결론: DI seam 으로 byte-동치 가능한 모든 핸들러(69) 전환 완료.** 잔여 ~46(fail-soft 3 + preauth/longpoll/txn 43)은 아키텍처 이연 — Final(router-extraction) 단계에서 구조 재편과 함께 처리.

## REV-20260630-0010 [AGENT-TEAM:p5b-final-router-pipeline-keywords]
- Related Change: CHG-20260630-0010 (Final 시작 — route-parity 인프라 + keywords router)
- §18.8 Adversarial Panel: **AGENT-TEAM (Final-planning workflow `p5b-final-execution-plan`, 8 agents / 0.46M tokens, 4축 분석+적대검증).** 검증된 핵심: (1) closure 축 HIGH refute → _get_authenticated_account 등 heavily-patched helper 는 web_context 이동 시 cross-binding 함정 → NS-BOUND 도메인은 web_context 이연. (2) **NS-BOUND=0 도메인은 web_context 선행 없이 router 추출 가능**(인증=dependency_overrides 객체키 cross-module 안전, MIXED 의 _account_has_permission 은 account 순수함수). (3) 첫 후보 media+keywords 검증. (4) route-parity 3-tier + include_router 순서/골든 게이팅.
- 실측 발견(워크플로 미예측, 본 cycle 적발): **Starlette 1.3.1 include_router 는 flatten 아닌 `_IncludedRouter` nest**(path=None, .original_router.routes). route-parity 의 flat 열거가 nested 라우트를 못 봐 count drift(179→176) 발생 → `_build_table` 재귀(`_walk_routes`)로 해소. keywords 의 `*_args,**_kwargs` GET/POST 는 원본도 422(FastAPI 가 phantom query param 요구)임을 clean app.py 대조로 확인 → 410 은 dead code, 추출 byte-동치.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0, route-parity 골든 179 불변(recursion 으로 set/order 동일), ruff clean, py_compile OK. 런타임 라우팅 동일(GET /api/keywords 422·categories 410 보존). 순환 import 안전(app 정의 후 include).
- 다음: NS-BOUND=0 도메인 순차 추출(media→static→admin-conversations→admin-usage→conversations MIXED), 그 후 web_context 추출(NS-BOUND 도메인용)→브라우저 QA→배포(confirm).

## REV-20260630-0011 [AGENT-TEAM:p5b-final-router-media-self-review]
- Related Change: CHG-20260630-0011 (Final router 추출 #2 — media 3 DI 핸들러)
- §18.8 Adversarial Panel: **SELF+구조+route-parity 결정적 검증(SUBAGENT 미dispatch — keywords(REV-0010)에서 추출 파이프라인 적대검증 완료, media 는 동일 패턴의 실 DI 핸들러 적용이고 byte-동치가 결정적: 3 핸들러 모두 동일 형태(cursor→SELECT ObjectKey→_serve_image_object), 공유 의존 3종(get_current_account/get_conn/_serve_image_object)뿐).**
- 검증 포인트: (1) **byte-동치**: router 핸들러는 원본 app.py 의 serve_avatar/serve_product_icon/serve_role_icon 와 SQL·테이블·컬럼·fallback_404 메시지 동일. DI 시그니처도 원본(이미 cat-A 전환됨)과 동일 — 추출은 위치 이동만, 로직 무변. (2) **순환 import 안전**: media.py 의 `from app import ...` 는 app.py 가 3 심볼 모두 정의(get_current_account L10228+, _serve_image_object 정의부) 후 맨 끝 include_router 시점에 실행 → partial-module import 성공(keywords 와 동일 입증). (3) **route-parity 매칭 안전**: 골든 재생성으로 set 불변 확인(removed/added 0). 순서 변경([45,48,53]→[172-174])은 media {var} 라우트를 *끝으로* 이동 — concrete 경쟁자 0 + 가장 늦게 매칭 → shadow 신규 발생 불가(끝 이동은 매칭 안전성을 *높임*). keywords(/api/keywords/*) 와도 prefix 무중첩.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0·"All checks passed!", route-parity 179(골든=현재 set·order 일치), ruff clean, py_compile OK(app.py + media.py). docker 골든 재생성 claude-corp 소유(pycache 권한 이슈 없음).
- 다음: static_pages(4 무인증 — NS-BOUND=0 최단순)→admin-conversations(1)→admin-usage(5 MIXED account 순수함수)→conversations(MIXED). 그 후 NS-BOUND 도메인용 web_context 추출→브라우저 QA→배포(confirm).

## REV-20260630-0012 [AGENT-TEAM:p5b-final-router-static-pages-self-review]
- Related Change: CHG-20260630-0012 (Final router 추출 #3 — static_pages 4 핸들러 + test-coupling 해소)
- §18.8 Adversarial Panel: **SELF+구조+route-parity+test-coupling 결정적 검증(SUBAGENT 미dispatch — keywords/media 에서 추출 파이프라인 적대검증 완료, static_pages 는 무인증 단순 핸들러이고 byte-동치가 결정적. 단 NS-BOUND 분류 위반(test-coupling)이 make test 로 즉시 적발돼 보수적으로 해소).**
- 적발·해소(중요): Final-planning workflow 의 NS-BOUND=0 분류가 `test_html_no_cache.py` 의 **핸들러 직접참조 + app.FileResponse monkeypatch** 커플링을 놓침. make test 가 `AttributeError: module 'app' has no attribute 'index'` 로 즉시 적발 → (1) router 를 `app.FileResponse`(import-time 복사 아닌 동적 속성) 호출로 작성해 monkeypatch 가로채기 계약 보존, (2) 테스트 호출 위치만 routers.static_pages 로 전환(assert·검증 의미 불변). **byte-동치 보존하며 해소 — 핸들러 로직/헤더/파일명 무변.**
- 검증 포인트: (1) **byte-동치**: 4 핸들러 모두 원본 로직·헤더(_HTML_NO_CACHE={"Cache-Control":"no-cache"})·status·SQL("SELECT 1"·heartbeat read)·503/200 분기 동일. healthz 의 _connect_memory/load_memory_kv 를 app.X 동적 참조로 해 monkeypatch 호환(현 스위트는 healthz 미호출이나 방어적). (2) **순환 import 안전**: `import app` 은 app 완성 후 맨 끝 include 시점 실행. (3) **route-parity 매칭 안전**: set 불변, static_pages [5-8]→[168-171] 끝 이동. {var} 라우트 `/share/{token}` 유일(share-prefix 단독·끝=가장 늦게 매칭) → shadow 신규 불가. (4) **test 전환 정합**: monkeypatch app.FileResponse → router 가 app.FileResponse 호출 → 가로채기 유효, captured 3건·no-cache·파일명 assert 그대로 통과.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0·"All checks passed!"(test_html_no_cache GREEN), route-parity 179(골든=현재), ruff clean, py_compile OK.
- 학습 반영: NS-BOUND 분류는 **app.<handler> 직접참조 테스트 + app.<global> monkeypatch** 도 점검 대상. 다음 도메인부터 추출 전 `grep -rn 'app\.<handler>'` 선행. app.X 동적 참조 규약이 이런 커플링의 일반 해법.
- 다음: admin-conversations(1)→admin-usage(5 MIXED account 순수함수)→conversations(MIXED). 그 후 web_context 추출→브라우저 QA→배포(confirm).

## REV-20260630-0013 [AGENT-TEAM:p5b-final-router-admin-conv-self-review]
- Related Change: CHG-20260630-0013 (Final router 추출 #4 — admin_archived_conversations RP)
- §18.8 Adversarial Panel: **SELF+구조+route-parity+런타임(TestClient) 결정적 검증.** keywords/media/static_pages 에서 추출 파이프라인 적대검증 완료. 본건은 단일 RP 핸들러 위치 이동(로직 무변, 이미 cat-B b5 에서 DI 전환됨)이라 byte-동치 결정적.
- 검증 포인트: (1) **byte-동치**: PG 정본(agent_runtime.core_conversations)·MySQL 폴백·계정 메타 enrich·q/limit(≤500)·503/200 분기 원본과 1:1. require_permission 메시지 verbatim 보존. (2) **DI override 정합**: require_permission/get_conn 을 `from app import` 로 동일 객체 바인딩 → as_account 의 dependency_overrides(객체키) 가 router 핸들러에도 적용(media 입증 패턴). (3) **var-shadow 역전 점검(concrete 끝-이동 신규 리스크)**: archived 는 4-segment 전부 literal concrete. 끝 이동 시 *선행 var 라우트가 가로채면* 역전이나, `/api/admin/conversations/{var}` 형제 0 + `/api/admin/{a}/{b}` 광역 매처 0(grep) → 캡처 불가. (4) **런타임 증명**: test_p1_admin_archived 가 TestClient 로 실제 경로 호출(perm-gate 403) → GREEN = 라우팅·DI 정상.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0·"All checks passed!", route-parity 179(골든=현재), ruff clean, py_compile OK.
- 학습 강화: **concrete 라우트 끝-이동은 "선행 var 캡처" 점검 필수**(var 라우트 끝-이동의 "후행 shadow" 와 대칭). 둘 다 `/<prefix>* + 광역 {a}/{b} 매처` grep 으로 커버.
- 다음: admin-usage(5 MIXED — account 순수함수 인라인 perm)→conversations(MIXED)→web_context(NS-BOUND)→브라우저 QA→배포(confirm).

## REV-20260630-0014 [AGENT-TEAM:p5b-final-router-admin-usage-self-review]
- Related Change: CHG-20260630-0014 (Final router 추출 #5 — admin_usage 2 핸들러, verbatim+uniform app.X)
- §18.8 Adversarial Panel: **SELF+구조+route-parity+런타임(TestClient/직접호출) 결정적 검증.** 추출 파이프라인은 #1-4 에서 적대검증 완료. 본건 신규 리스크 2가지를 집중 검증: (a) 대형 핸들러 verbatim 정합, (b) helper-monkeypatch 보존.
- 검증 포인트: (1) **verbatim 정합**: 스크립트가 app.py 라인 슬라이스를 그대로 추출(assert 로 첫/끝 줄 검증) 후 정규식 rewrite 만 적용 → 본문 로직·SQL(date_trunc 화이트리스트·interval 캐스트·by_model/account/role/day 집계)·403 메시지·503 분기 byte 보존. rewrite 부작용 점검: `app.` 접두는 word-boundary lookbehind `(?<![\w.])` 로 method/속성/문자열 오염 0, `_pg_connect`(shared.db) bare 유지 확인, 이중접두 `app.app.` 0(grep). (2) **helper-monkeypatch 보존**: uniform `app.X` 동적참조 → test 의 `monkeypatch.setattr(app,"_query_usage_conversations"/"_usage_account_ids_for_role")` 가 router 핸들러에도 적용. (3) **DI override 정합**: `Depends(app.get_current_account/get_conn)` = app 정본 동일 객체 → as_account override 적용(media 입증). (4) **test 전환 정합**: AO 직접호출(account/conn 명시)이 Depends 기본값 우회 → 본문 perm 검사가 actor dict 로 실행(real _account_has_permission), 403 ×2·시스템역할 빈목록 ×1 보존. (5) **var-shadow**: admin/usage* 2 concrete·var 형제 0·1-seg `/api/admin/{var}` matcher 0.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0·"All checks passed!"(test_usage_conversations 전체 GREEN: Q1-Q4 헬퍼 + A1/A2 admin + P1 profile), route-parity 179(골든=현재), ruff clean, py_compile OK.
- 학습: 대형/다-helper 핸들러는 **verbatim 슬라이스+화이트리스트 정규식 rewrite** 가 수기 전사보다 안전. helper-monkeypatch 도메인은 **uniform app.X** 가 일반 해법(static_pages 의 app.FileResponse 와 동일 원리 확장).
- 다음: conversations(MIXED) → NS-BOUND 도메인 web_context 추출 → 브라우저 QA → 배포(confirm).

## REV-20260630-0015 [AGENT-TEAM:p5b-web-context-strategy-workflow]
- Related Change: CHG-20260630-0015 (web_context 추출 시작 — leaf-first 증분 #1)
- §18.8 Adversarial Panel: **ultracode Workflow `p5b-web-context-strategy`(10 agents / 0.60M tokens): 3 전략 설계(parallel) → 전략별 2 lens 적대 stress(test-breakage / binding-circular, "안 깨진다" 반증 목적) → 1 합성(effort high).** 판정 결과 A·C `broken`, B `safe`(양 렌즈). 합성이 현 worktree 실측(web_context.py 부재·app.py web_context import 0)으로 stress 에이전트들이 본 "contamination"(transient concurrent-session noise)을 기각하고 B 채택 확정.
- 검증 포인트: (1) **behavior-neutral**: 2 함수 본문 byte 그대로 이동(re.sub session-id sanitize, sha256 token hash). app.py re-import 가 모듈 전역에 rebind → 8 호출부(L1218/2170/2185/2202/2221/5671/18706/18713) + 미래 monkeypatch 보존. (2) **순환 import 불가**: web_context 가 app-internal 심볼 0 참조(stdlib re/hashlib only) → 단방향 edge. docstring 의 "from app import" 언급은 INVARIANT 설명 텍스트일 뿐 실제 import 문 0(grep `^\s*from app import` 검증). (3) **무파손 근거**: 두 심볼 테스트 monkeypatch/직접참조 0(Explore 매핑 + 본 cycle 재확인). DI override 키(get_current_account/get_optional_account)·hotspot(_connect_memory/_require_account)와 무관.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0·"All checks passed!", route-parity 179, py_compile OK(web_context.py+app.py). docker 런타임: `import app, web_context` 동시 성공(순환 없음) + `app._X is web_context._X`(rebind 동일객체) + 함수 동작 확인.
- 학습: 과거 실패한 web_context 직추출의 안전 재개법 = **0-monkeypatch·app-free leaf 부터 물리 이동**(단방향 edge 보장) + app re-import rebind(호출부·monkeypatch 보존). hotspot(_require_account 51×·_connect_memory 62×·_account_has_permission 11×)은 23-테스트 retarget 동반이라 최후. workflow 적대 stress 가 A(순환)·C(양방향 cycle 인위) 의 치명 결함을 사전 적발.
- 다음: inc2 _get_client_ip+proxy companions(0 test ref, 안전) → inc3 SESSION_COOKIE+_resolve_permission_catalog → inc4 _fetch/_decorate_account_rows → (그 후 23-테스트 retarget 영역).

## REV-20260630-0016 [AGENT-TEAM:p5b-web-context-inc2-self-review]
- Related Change: CHG-20260630-0016 (web_context 증분 #2 — proxy/client-IP cluster)
- §18.8 Adversarial Panel: **SELF+구조+docker 런타임 결정적 검증.** 추출 전략은 REV-0015 workflow 적대판정(Strategy B safe)에서 확립. 본 증분의 신규 리스크 = AGENT_MODE 결합(app-internal 참조) + WEB_TRUSTED_PROXIES startup-time 계산 위치 이동.
- 검증 포인트: (1) **app-free 단방향 edge**: web_context 에 실제 `from app import`/`import app` 0(grep `^\s*from app import`). AGENT_MODE 결합은 app L82 와 **동일 표현식**(`os.getenv("AGENT_MODE","").strip().lower()`)의 env-mirror 로 해소 — 함수 시그니처 불변, 동일 env → 동일 값. (2) **byte-동치**: 5 함수 본문 그대로. _parse_trusted_proxies 의 prod/staging RuntimeError + dev/test stderr warning 보존. WEB_TRUSTED_PROXIES 계산이 app L1172→web_context import(app 상단) 로 이동했으나 **둘 다 module-load startup-time, fail-loud 동작 동일**(invalid-CIDR raise 시점만 약간 앞당겨짐, 관측 동치). (3) **back-ref 0**: _is_trusted_proxy 가 읽는 WEB_TRUSTED_PROXIES 를 함께 이동해 web_context 가 canonical → web_context→app 역참조 없음. (4) **startup-validation 잔류**: ENABLE_WEB_TLS_PROXY 블록(app, 3 refs) 은 재import된 WEB_TRUSTED_PROXIES + app AGENT_MODE 로 정상 동작. (5) **rebind**: app 의 _get_client_ip 호출부 7곳(L2153/2218/5662/15799/18356/18450 등) bare-name → app rebind 로 resolve.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0·"All checks passed!", route-parity 179, py_compile OK. docker 런타임: rebind-identity 7/7(2 inc1 + 5 inc2) + import app/web_context 동시 성공(순환 없음) + WEB_TRUSTED_PROXIES=(172.18.0.0/16)(env 계산 정상) + _get_client_ip("1.2.3.4")→"1.2.3.4".
- 학습: app-internal 전역 결합(AGENT_MODE) 은 **동일 env-read 표현식 mirror** 로 app-free 유지 가능(시그니처 불변 byte-faithful). 모듈상수가 startup 부수효과(fail-loud) 를 가지면 계산 위치 이동의 timing/관측 동치 명시.
- 다음: inc3 SESSION_COOKIE+_resolve_permission_catalog(+PERMISSION_*) → inc4 _fetch/_decorate_account_rows(0 test ref 안전 영역) → 그 후 23-테스트 retarget 영역.

## REV-20260630-0017 [AGENT-TEAM:p5b-main-integration-self-review]
- Related Change: CHG-20260630-0017 (origin/main 100-commit 통합)
- §18.8 Adversarial Panel: **SELF+구조+make test 결정적 검증.** drift 성격 사전 분석(main app.py 변경 = additive 신규 라우트, auth helper 무변)으로 의미 충돌 위험 배제 → auto-merge 안전성 확인.
- 검증 포인트: (1) **충돌 성격**: 양쪽 수정 3파일 중 app.py·test_sample_feedback 는 auto-merge(영역 분리), route_snapshot 만 충돌(골든이라 재생성으로 해소). (2) **머지 정합**: py_compile OK, 내 web_context re-import + 5 include_router 생존, main 신규 라우트(livez/readyz/glossary-feedback/graph) 존재, **중복 라우트 데코 0**(머지 오류 없음), 추출 핸들러 app.py 재등장 0(deletion 보존). (3) **route-parity**: 179→188(+9 main), 골든 재생성=현재 일치. (4) main 이 _require_account/_get_authenticated_account/_account_has_permission/_sanitize_session_id/_get_client_ip/DI seam 무변(grep) → 내 refactor 와 semantic 충돌 0.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0·"All checks passed!", route-parity 188(골든=현재), py_compile OK.
- 다음: 브라우저 로그인 QA(win-browser bridge OK) + RBAC smoke → §18.8 패널 → PR/머지 → 배포(confirm).

## REV-20260630-0018 [AGENT-TEAM:p5b-final-1808-ship-panel]
- Related Change: CHG-20260630-0018 (§18.8 ship-gate 패널 후속 주석 정정) + 머지(CHG-0017) ship 판정
- §18.8 Adversarial Panel: **ultracode Workflow `p5b-final-1808-panel`(14 agents / 0.63M tokens): 5 차원 리뷰(byte-동치/route-shadowing/web_context-edge/auth-rbac-e2e/merge-integration) → 차원별 적대 검증(REFUTE 시도) → 합성 ship 판정.** **판정: GO. ship-blocking 0건.** 확정 결함 6(low 1 + info 5).
- 검증 요약(워크트리 직접 재현): make test **575 passed/0 fail**(agent 이미지+worktree 마운트), route-parity **188**(=내 179+main 9), byte-동치 계약 문자열 무손상("로그인이 필요합니다." 401 / "db connection failed" 500 verbatim), web_context INVARIANT 유지(단독 import 시 app not in sys.modules·acyclic), include_router app 맨 끝(L29090-94), 7 심볼 재정의/shadow 0, 머지 중복 라우트/함수 0.
- 확정 결함(전부 non-blocking): [low] WEB_TRUSTED_PROXIES fail-loud 순서(이중-오설정 첫 에러만 상이, 둘 다 abort·S8 무회귀) → 주석 정정(CHG-0018). [info×5] 주석 line-number·검증노트(결함 아님).
- route-shadowing 차원: 14 추출 라우트 끝-이동 + main 신규 9 라우트 상호작용 점검 → shadow 신규 0. auth-rbac-e2e: DI 전환 핸들러 401/403/500 우선순위·dependency_overrides 경로 보존, 이연 pre-auth gate 핸들러 app.py 잔류 정상. merge-integration: main 신규 9 라우트 온전·중복 0.
- 브라우저 QA 필수 시나리오(패널 권고): 미인증 401 verbatim·로그인 세션쿠키·RBAC 403(admin_usage/admin_conversations)·추출 라우트 14 실호출(media 이미지·static_pages /healthz·/share)·conn실패 500. 배포 후 healthz(edge 200=router include 라이브 증명)+soak+rollback 인지.
- 결정적 검증: §18.8 GO + make test 575/0 + route-parity 188 + py_compile OK. ship 진행 가능.

## REV-20260701-0001 [AGENT-TEAM:p5b-deploy-import-hotfix-self-review]
- Related Change: CHG-20260701-0001 (컨테이너 로드 import 실패 hotfix)
- §18.8 Adversarial Panel: **SELF+컨테이너 실기동 검증.** 배포 healthz 게이트가 web-a crash-loop(ModuleNotFoundError: web_context)를 적발 → 근본원인(test PYTHONPATH top-level vs 컨테이너 web.app 패키지 로드 불일치) 진단 → 수정 → **실제 uvicorn web.app:app 로 재현·검증**(단순 make test 재실행이 아니라, 놓친 환경 자체를 재현).
- 진단 경로(결정적): (1) web-a 로그 = app.py:63 `from web_context import` ModuleNotFoundError. (2) 컨테이너 uvicorn = WORKDIR /app, sys.path[0]='' → /app 만 → top-level web_context/routers 불가. (3) 1차 수정 insert(0,/app/web) → 새 실패 `modules.memory` ModuleNotFoundError → /app/web/modules(web) 가 /app/modules(core) 를 shadow 발견. (4) 최종 수정 append(/app/web) → core modules('' 우선) 보존 + web_context/routers(append) resolve + app alias(routers from app import 중복 방지).
- 검증(컨테이너 실기동, mysql-ai-web:24dd588 + 수정 app.py 마운트): `uvicorn web.app:app` → Application startup complete(import 해소). healthz git_commit=24dd588(추출 static_pages router 동작). /api/session 200(미인증). /api/avatars/1(media)·/api/admin/usage(admin_usage) → 라우팅 정상 + DI conn-fail 500 "db connection failed" byte-동치. (503/500 은 테스트 컨테이너 DB 미연결 탓, 실배포는 .env+DB로 정상.)
- 회귀: make test 575 passed/0 fail·route drift 0·route-parity 188(테스트 환경 무영향 — append 는 이미-on-path 라 guard skip, alias 는 test 에서 no-op). py_compile OK.
- 학습(중요): **추출 모듈은 컨테이너 로드 방식(web.app 패키지)으로도 import 검증 필요.** make test/§18.8 이 top-level PYTHONPATH 만 써서 이 클래스를 놓침 → blue-green healthz 게이트가 최종 안전망(프로덕션 무영향 abort). CI 에 web.app-스타일 import smoke 추가가 근본 대책.

## REV-20260701-0002 [AGENT-TEAM:p5b-conversations-router-self-review]
- Related Change: CHG-20260701-0002 (conversations 도메인 10 핸들러 추출)
- §18.8 Adversarial Panel: **SELF+구조+make test 결정적 검증.** 추출 파이프라인은 REV-0010~0014 에서 적대검증 완료. 본건 신규 리스크 = (a) AST 경계 정확성, (b) app.X rewrite 오탐, (c) stdlib import 누락.
- 검증: (1) **경계**: 초기 regex line-range 가 multi-line sig 를 오판(history L17437-17444 로 잘림 → SyntaxError) → AST(decorator_list[0].lineno..end_lineno) 로 정확 재추출(10 핸들러 512줄). (2) **rewrite 안전**: whitelist=블록토큰∩app심볼722−핸들러명−키워드/파라미터 = `_`헬퍼17+DI seam3. `app.app.`/`app.progress`(로컬 충돌) 0 assert. `_`헬퍼는 app.X 동적참조라 monkeypatch 보존. (3) **stdlib 누락 적발·보강**: make test 가 `NameError: os`(history_anchor/dates 의 os.environ) 적발 → os·logging import 추가(app.X 는 app-심볼만 커버하는 한계 = 학습). (4) **동반 테스트**: test_history_calendar_pg_routing(T1/T2/T3) 는 TestClient+as_account(DI override)+monkeypatch app._connect_memory/_require_account → 전부 GREEN(app.X 동적참조 + DI override 정합).
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0, route-parity 188(set 불변·골든 재생성), py_compile OK. **app.py 29,111→28,610(~500↓).**
- 학습: 추출 3원칙 = app-심볼 app.X 동적참조 + 핸들러-사용 stdlib 명시 import + AST 경계. make test 가 stdlib 누락/monkeypatch-miss 안전망.
- 다음(순차): 완전-DI 잔여 도메인(admin_quotas 3·admin_sample_feedback 3 — test 커플링 전환 필요) → admin console singles → 그 후 inline-heavy(admin/metadata 30 등, DI 전환 선행).

## REV-20260701-0003 [AGENT-TEAM:p5b-quotas-samplefeedback-self-review]
- Related Change: CHG-20260701-0003 (admin_quotas + admin_sample_feedback 추출)
- §18.8 Adversarial Panel: **SELF+make test 반복 검증(3 라운드).** 파이프라인 적대검증 기존 완료. 본건 신규 리스크 = (a) non-_ app 헬퍼 누락, (b) 다양한 test 참조 스타일.
- 검증: (1) **non-_ 헬퍼 누락 적발**: 1차 make test 가 `NameError: record_audit_event`(admin_sample_feedback) → app.X whitelist 를 `_`한정에서 확장(app top-level def ∩ 호출 − builtins − `_`처리분)해 record_audit_event 접두. admin_quotas 는 non-_ 누락 0. (2) **test 참조 스타일 전수**: quota 는 getsource(app.admin_set_role/account_quota) 2 + `for fn: hasattr(app,fn)` 루프 1 + `_import_app()` 헬퍼(→ module-level import 필요); feedback 은 asyncio.run(app.admin_*(...)) 직접호출 4. 2·3차 라운드로 hasattr→admin_quotas + import 위치(app=_import_app() 뒤) 교정. (3) byte-동치: 핸들러 본문 AST 슬라이스 그대로 + app.X/stdlib import 만.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0, route-parity 188, py_compile OK. **app.py 28,610→28,350(~260↓).**
- 학습(파이프라인 보강): 추출 whitelist=`_`헬퍼+DI+**non-_ app 함수(record_audit_event류)**; test 전환=getsource/hasattr/직접호출/import-헬퍼 전수 점검. make test 가 최종 안전망(3 라운드 적발·교정).
- 다음: admin console singles(admin_me·permissions·databases·overview·health) 등 완전-DI 잔여 → inline-heavy(DI 전환 선행).

## REV-20260701-0004 [AGENT-TEAM:p5b-admin-console-self-review]
- Related Change: CHG-20260701-0004 (admin_console 5 핸들러 추출, batch 3)
- §18.8 Adversarial Panel: **SELF+make test 결정적 검증.** 파이프라인 3원칙(AST 경계·app.X 동적참조·stdlib 명시 import) 기확립. 본건 검증: (1) datetime from-import(admin_health datetime.utcnow=클래스), (2) main 신규 라우트로 골든 set 변경 흡수.
- 검증: (1) AST 경계 5 핸들러 155줄. (2) app.X: `_`헬퍼/상수 19(_DASHBOARD_WIDGETS·_dash_widget_*·_serialize_account·_json_error 등)+DI seam, non-_ 함수 0. `app.app.` 0. (3) stdlib: logging + `from datetime import datetime`(module import 아님 — datetime.utcnow 는 클래스 메서드). (4) 골든 188→192: 재생성 시 removed=[] 확인(admin_console 5 라우트 set-보존) + added=[graph/analyze ×4]=main feature-0016(내 추출 무관) → 골든 흡수. (5) 테스트 전환: getsource(admin_me)+직접호출(admin_overview ×6) → admin_console.X + import.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0, route-parity 192, py_compile OK. **app.py 28,559→28,410.**
- 다음: 완전-DI 잔여(api/share 2·api/llm 1·api/file 1 misc) → inline-heavy(DI 전환 선행: admin/metadata 30·admin/products 17·api/auth 12·conversations MIXED 7).

## REV-20260701-0005 [AGENT-TEAM:p5b-share-system-self-review]
- Related Change: CHG-20260701-0005 (share+system 추출, batch 4 — 완전-DI 완료)
- §18.8 Adversarial Panel: **SELF+make test 결정적 검증(2 라운드).** 파이프라인 기확립. 본건 신규 = 소스텍스트 contract 테스트(4번째 커플링).
- 검증: (1) AST 경계 4 핸들러. app.X(app 헬퍼+DI seam), get_llm_health 의 _get_authenticated_account inline→app.X. (2) **소스텍스트 contract 적발**: 1차 make test 가 test_group_conversation_s2(`@app.post("/api/share/{token}/join")` in app.py 텍스트) + test_member_ban(`_func_src` AST가 app.py 만 파싱) 실패 → app.py+routers 통합 검색으로 전환. `app.<handler>` grep 은 이 유형 못 잡음(read_text/ast.parse). (3) route set 불변 192(share/system 추출 set-neutral). (4) var-shadow: /api/share/* 2 라우트 전부 추출(app.py 잔여 share 형제 0), get_llm_health·get_file concrete.
- 결정적 검증: make test 전체 0 FAIL/ERROR·exit 0·route drift 0, route-parity 192, py_compile OK. **app.py 28,410→28,221. 완전-DI 라우트 전부 추출(11 router / ~39 라우트).**
- 학습: 커플링 4유형(직접호출·monkeypatch·getsource·소스텍스트 contract) 전수 점검. 다음 = inline-heavy(DI 전환 선행 — admin/metadata 30 등 cat-A/B/C 마이그 재개).

## REV-20260701-0006 [AGENT-TEAM:p5b-admin-metadata-di-adversarial]
- Related Change: CHG-20260701-0006 (admin/metadata 33 핸들러 DI seam byte-동치 전환)
- §18.8 Adversarial Panel: **ultracode Workflow(4 agents: 3 슬라이스 refute + 1 synthesize), "통과 아닌 결함 적발" 렌즈.** 판정 **byte-equivalent, ship_blocking=false**. (슬라이스 3=samples/test-mig 는 StructuredOutput 재시도 초과로 기술적 실패했으나 synthesize 가 git diff 로 samples 3 포함 33 전수 독립 재검증해 커버.)
- 검증 재현(각 슬라이스 Bash 로 app.py·테스트 실물 확인): (1) **git diff HEAD 로 33 핸들러 전수 = 정확히 3줄 auth 블록만 제거 + `account=Depends(require_permission("..."))` param 만 추가** — 부수 코드 삭제 0, docstring/첫 본문 문장 온전(대형 docstring graph/bootstrap 포함). (2) **perm 매핑 33/33 정확**: kb.ingest.manual 27(legacy `_metadata_resolve_account` 하드코딩 일치)·kb.glossary.curate 3(`_metadata_resolve_account_perm` 인자)·kb.sample.curate 3(`_samples_resolve_account`). 오매핑 0. (3) **auth 응답 byte-동치**: `_json_error`=`_auth_error_handler`=JSONResponse({"error":msg},status), 500 "db connection failed"/401 "로그인이 필요합니다."/403 "권한이 없습니다." 메시지·코드 일치; legacy `_require_permission`→`_require_account`(401)→`_account_has_permission`(403) 경로가 DI `get_current_account`→require_permission 팩토리와 동일 헬퍼 경유. (4) **pre-auth gate 없음**(변환 33): 유일 429(bootstrap_describe)는 body 내부 RBAC-후 검사·순서 보존; `admin_metadata_suggest` 미전환(pre-auth 404 gate + 동적 perm) = 정확한 이연. (5) **txn 독립**: audit=`_connect_memory`(MySQL) vs CRUD=`_pg_connect`(PostgreSQL) 별개 DB → DI get_conn memory conn 무간섭. (6) 테스트 74 passed 재현, 403 게이트가 `called["hit"] is False`(코어 미호출) assert 로 auth-before-body 기계 검증, route_parity(path+method+order) 통과.
- 수용(비차단): **LOW test-adequacy gap** — perm-string 스왑 mutation 이 스위트 통과(403 테스트는 console.access 만 부여, happy-path 직접호출은 require_permission 우회, graph 5핸들러 behavior 커버리지 0) → 코드리뷰 perm 정확성 독립 확인으로 상쇄. **INFO conn-lifetime** — DI 가 memory conn 을 teardown 까지 유지(legacy 는 body 전 close) → 응답 byte 무영향(handler body 는 별도 _pg_connect).
- 결정적 검증: make test 1313 passed·0 fail·route-parity 192 불변·py_compile OK. behavior-neutral(추출 아님).
- 학습: 도메인 전용 auth helper 도 auth+정적 perm 이면 require_permission clean 전환. txn 이연은 conn 정체성(어느 DB) 확인 필수. 다음 = admin/metadata router 추출(34 핸들러, app.X 동적참조 + suggest inline 유지).

## REV-20260701-0007 [SKIPPED:mechanical byte-neutral extraction — make test route-parity + static prefix-완전성 게이트; §18.8 byte-동치는 DI 전환(REV-0006)에서 수행]
- Related Change: CHG-20260701-0007 (admin/metadata 34 핸들러 → routers/admin_metadata.py 추출)
- 검증 성격: 추출은 라우트 경로·메서드·응답 불변 mechanical move(핸들러 코드 자체 무변경, `app.X` 참조 접두만). auth byte-동치(auth-sensitive)는 선행 DI 전환 REV-0006 §18.8 패널에서 검증 완료. 본 추출은 **route-parity(경로+메서드+순서) + make test 전체 + static prefix-완전성 검사**가 결함 게이트.
- 결정적 검증: (1) route-parity 골든 docker `_build_table` 재생성 = **set-neutral(added/removed 0), total 192 불변, 순서만 갱신**(34 metadata 라우트 include 순서상 끝 이동). (2) make test **1313 passed·0 fail·route drift 0**. (3) **make test 안전망이 추출 결함 1건 실적 적발**: `_SAMPLE_WEIGHT_MIN/_MAX`(튜플-대입 모듈상수) whitelist 누락 → NameError → 완전 mod_syms static 재검사(튜플/AnnAssign/import 타깃 포함)로 전수 0 확인 후 보정. (4) py_compile app.py+router OK. (5) 커플링 4유형 사전 grep: type1(직접호출)=재참조 완료, type2/3/4(monkeypatch·getsource·소스텍스트 contract)=metadata 핸들러 해당 0 확인. (6) 헬퍼 monkeypatch 보존: `_metadata_*`/`_connect_memory`/`record_audit_event` app.py 잔류 → router `app.X` 동적참조로 테스트 monkeypatch 계약 유지.
- app.py 28,224→26,734(~1,490↓, 단일 도메인 최대). routers 12개 / metadata 34 라우트 추출.
- 학습: whitelist mod_syms 는 튜플-대입 타깃까지 수집 필수(누락 시 router NameError, make test 적발). 추출 후 완전 mod_syms static 재검사를 골든 재생성 전 수행 = 조기 적발.
- 후속 배포: 컨테이너 로드(uvicorn web.app:app)에서 router import 는 기존 11 router 와 동일 `routers.<d>` 경로(신규 top-level 모듈 아님)라 web_context류 위험 없음 — 배포 blue-green healthz 게이트가 최종 안전망.
- **배포·라이브 검증 완료(main 0b91b1b, PR #506)**: blue-green soak 통과·healthz git_commit=0b91b1b·추출 admin_metadata 라우트 미인증 401 verbatim(`{"error":"로그인이 필요합니다."}`) — DI seam byte-동치 + 컨테이너 로드 import 프로덕션 확인. deploy_scope: included(전역 standing) 근거 자동 배포.

## REV-20260701-0008 [SKIPPED:deploy-record — 라이브 smoke 검증이 게이트; §18.8 byte-동치는 CHG-0006 REV-0006 에서 수행]
- Related Change: CHG-20260701-0008 (admin/metadata 마일스톤 배포·라이브 검증)
- 검증 성격: 코드 무변경 배포 기록. byte-동치 §18.8 은 DI 전환(REV-0006)에서, 추출 route-parity 는 REV-0007 에서 완료. 본 항목은 **프로덕션 라이브 smoke** 가 게이트.
- 결정적 검증: (1) CI test PASS(36s). (2) blue-green 배포 soak 90s 통과·롤백 없음. (3) 라이브 edge healthz git_commit=0b91b1b·status=ok(배포 커밋 일치). (4) 추출 admin_metadata 라우트 미인증 **401 verbatim** = DI seam(require_permission→get_current_account→_AuthError 401) 프로덕션 byte-동치 + 컨테이너 로드 router import 정상(web_context류 ModuleNotFoundError 없음 — healthz 게이트 통과가 입증). (5) insight/ask-worker GIT_COMMIT WARN = 별건(웹 배포 무관).
- 결론: admin/metadata 도메인 deploy-backed 완료.

## REV-20260701-0009 [SKIPPED:mechanical byte-neutral 전체추출 — make test route-parity + 커플링 6유형 grep + static missing-prefix 게이트]
- Related Change: CHG-20260701-0009 (6 도메인 35 핸들러 전체추출)
- 검증 성격: 추출은 라우트 경로/메서드/응답 불변 mechanical move(핸들러 코드 무변경, DEFER 는 인라인 auth 그대로, `app.X` 참조 접두만). auth 로직 변경 0(§18.8 byte-동치 불요). 게이트 = route-parity(경로+메서드+순서) + make test 전체 + static prefix-완전성 + 커플링 6유형 전수.
- 결정적 검증: (1) route-parity 골든 docker `_build_table` 재생성 = **set-neutral(added/removed 0), total 192 불변**. (2) make test **1313 passed·0 fail·route drift 0**. (3) **make test 안전망이 미포착 커플링 4건 실적 적발·수정**: `hasattr(app,"handler")` 3(→모듈), `app.app.routes` flat 순회 1(→재귀 walk). (4) 6 신규 router 가 docker(uvicorn web.app 컨테이너 로드)에서 정상 import(골든 재생성이 app 로드 성공으로 입증). (5) 추출기 self-healing missing-prefix static 재검사 clean, py_compile app.py+6 router OK.
- 커플링 6유형 확립(추출 전 grep): (1)`app.<h>(` 직접호출 (2)`monkeypatch.setattr(app,...)` (3)`getsource(app.<h>)` (4)소스텍스트 `read_text/ast.parse`+핸들러명 (5)`hasattr/getattr(app,"<h>")` 문자열-인자 (6)`app.app.routes` flat 순회. profile·integrations 는 커플링 0(TestClient+snapshot), 나머지 4 도메인은 getsource/hasattr/route-check 재참조.
- app.py 26,734→24,648(~2,086↓). 12→18 router. DEFER 핸들러(preauth) 인라인 auth 보존 = byte-identical.
- 학습: 핸들러 추출은 DI 전환 불요(monkeypatch 는 `app.X` 동적참조로 보존). DEFER byte-동치 DI-rework 는 향후 정제(현 목표=모듈화, 전체추출이 최단).

## REV-20260701-0010 [SKIPPED:mechanical byte-neutral 전체추출 — make test route-parity + 커플링 7유형 게이트]
- Related Change: CHG-20260701-0010 (datasources 6 + auth 18 전체추출)
- 검증 성격: mechanical route-preserving move(auth 로직 무변경, PUBLIC/DEFER 인라인 그대로). 게이트 = route-parity + make test + 커플링 전수.
- 결정적 검증: (1) 골든 재생성 set-neutral 192. (2) make test **1313 passed·0 fail·route drift 0**(2회 반복 — 1차 hasattr 루프 2 + source-text 호출식 count 1 적발, 2차 GREEN). (3) datasources CLEAN-DI 3(`_ds_write_common`)·auth PUBLIC 7(signup/login/oauth)·DEFER 5 전부 인라인 auth 보존 = byte-identical. (4) 2 신규 router docker 컨테이너 로드 정상(골든 재생성 app 로드 성공). (5) py_compile+static missing-prefix clean.
- 커플링 7유형 확립: 기존 6 + **(7) source-text 호출식 count**(helper 호출식을 app.py 소스에서 count — 추출 이동 시 변동, app.py+routers 합산 수정). auth_me 필터 호출이 auth.py 로 이동해 count 2→1 적발.
- app.py 24,648→23,536(~1,112↓). 18→20 router.
- 학습: 커플링 스캔은 핸들러명 grep 만으론 부족 — helper 호출식 count 형 source-text 검사(핸들러명 무참조)는 make test 가 최종 안전망. reref import guard 정확 매칭 필수.

## REV-20260701-0011 [SKIPPED:mechanical byte-neutral 전체추출 — make test route-parity + 커플링 8유형 게이트]
- Related Change: CHG-20260701-0011 (conversations 17 append + products 22 전체추출)
- 검증 성격: mechanical route-preserving move(auth 로직 무변경, DEFER/txn/streaming 인라인 그대로). conversations 는 기존 router append.
- 결정적 검증: (1) 골든 재생성 set-neutral 192. (2) make test **1313 passed·0 fail·route drift 0**(2회 — 1차 source-text contract 6 적발[test_group_conversation_s2 APP→APP_ALL·test_share_joinable_owner_guard getsource substring], 2차 GREEN). (3) products txn(admin_create/update/delete_product)·streaming(prompt/generate/stream)·pre-auth 전부 인라인 보존 byte-identical. (4) --append: 기존 conversations.py(10) + 신규 17 = 27 핸들러, NEW 블록 missing-prefix clean, 골든 재생성 app 로드 성공(컨테이너 import 정상). (5) py_compile OK.
- 커플링 8유형 확립: 기존 7 + **(8) getsource 컨텍스트-substring**(helper 앞 단어 포함 substring 이 `app.` 접두로 깨짐 — 단일 심볼명은 생존). test_share_joinable_owner_guard 의 `not _conversation_owned_by_account` 적발.
- app.py 23,536→20,542(~2,994↓, 단일 배치 최대). 20→21 router. **잔여 app.py 라우트 16(session 시작 148 대비 −132, 89% 추출)**.
- 학습: --append 모드로 도메인 재통합(conversations sub-resource 를 lifecycle router 로). source-text getsource 는 helper-접두에 취약 — make test 가 안전망.

## REV-20260701-0012 [SKIPPED:mechanical byte-neutral 전체추출 완주 — make test route-parity + 커플링 9유형 게이트]
- Related Change: CHG-20260701-0012 (잔여 16 라우트 append — 라우트 핸들러 전량 추출 완료)
- 검증 성격: mechanical route-preserving move. DEFER(long-poll/fail-soft/opt) 인라인 그대로. cross-call `ask` 는 내부 caller/monkeypatch 대상 모듈 전환.
- 결정적 검증: (1) 골든 set-neutral 192. (2) make test **1313 passed·0 fail·route drift 0**. (3) **잔여 @app 라우트 0**(148 전량 추출) — python AST 확인. (4) cross-call `ask`: 내부 caller(conversations.py post_fix_with_ai) `app.ask`→bare `ask`(동일 모듈), monkeypatch/hasattr/getsource `app.ask`→`conversations.ask`, post_fix_with_ai 가 bare `ask` 호출 → `conversations.ask` module global → monkeypatch 정합(make test 입증). (5) 4 router append(conversations/share/admin_console/system) 컨테이너 로드 정상(골든 재생성 app 로드 성공).
- 커플링 9유형: 기존 8 + **(9) cross-call 핸들러**(route 이자 내부 함수). `ask`(POST /api/ask, fix-with-ai 가 내부 호출) 유일.
- app.py 20,542→18,917(~1,625↓). **148 route 핸들러 전량 21 router 추출 — app.py = 헬퍼 라이브러리 + DI seam + include_router.**
- 잔여 아키텍처: app.py ~18.9k = **헬퍼**(web_context 미이동 — 원래 monkeypatch 블로커, 별도 workstream). route-handler 모듈화는 완주. 완전 thin-app 은 web_context 헬퍼 추출 필요(DI seam 선행).
