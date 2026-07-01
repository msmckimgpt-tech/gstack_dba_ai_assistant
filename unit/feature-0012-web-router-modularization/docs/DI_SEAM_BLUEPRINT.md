---
doc_type: DESIGN_BLUEPRINT
scope: feature
status: active
lifecycle: working
source_of_truth: true
feature_id: feature-0012-web-router-modularization
phase: P5b
created: 2026-06-29
sources:
  - FUNCTION.md
  - ../../feature-0003-agent-web-ui/src/app.py
---

# feature-0012 P5b — Auth DI Seam 설계 + 마이그레이션 worklist (확정본)

대상: `unit/feature-0003-agent-web-ui/src/app.py` (29,570줄 모놀리스, FastAPI, APIRouter 0 / `Depends()` 0).
목표: FastAPI DI(`get_current_account` / `get_optional_account` / `require_permission(perm)`) 도입 → 응답 셰이프(`{"error":msg}`+status) **1:1 보존** → 테스트를 `TestClient`+`dependency_overrides` 로 전환 → 이후 helper 를 `web_context` 로 이동해 라우터 추출.
원칙: **가산적(additive) → 증분 마이그 → 추출**. 매 Phase 가 `make test` green + route-parity 통과로 committable.

> 본 청사진은 6축 병렬 매핑 + 적대적 완전성 비평(verdict: needs-revision, BLOCKING 2 + HIGH/MEDIUM 5) 의 결함을 **직접 grep 검증 후 보정**한 확정본이다. 보정 항목은 각 절의 **[보정]** 표기.

---

## 0. 검증된 사실 (grep 확인 2026-06-29)

- 인증 helper: `_account_has_permission@1616`, `_get_authenticated_account@2184(conn,request)→dict|None`, `_require_account@10232(request,conn)→(account,error)`, `_optional_account@10239`, `_require_permission@10251(request,conn,permission)`.
- `_json_error@10228 = JSONResponse({"error":msg}, status)`. **exception handler / HTTPException 사용 0건**.
- 호출 사이트: `_require_account` 118, `_account_has_permission` 120, `_require_permission` 7(정의1+콜러6), `_optional_account` 2, `_get_authenticated_account` 7.
- **[보정 HIGH-1]** 테스트 패치 표면 = `_require_account` 참조 **23파일**(22 아님), `_account_has_permission` **11파일**(9 아님).
- **[보정 BLOCKING-1]** `_json_error(...,403)` **129건, 고유 메시지 60종**. generic "권한이 없습니다."는 **9건뿐**. 최다: "관리 콘솔 수정 권한이 필요합니다."(15), "요청을 수행할 수 없습니다."(13), "관리 콘솔 접근 권한이 필요합니다."(12), "제품 관리 권한이 필요합니다."(6), "감사 로그 조회 권한이 필요합니다."(6).
- `_connect_memory` = `_open_memory_connection()` raw 연결(**풀 없음**, autocommit=True).
- 테스트 전형: `resp = asyncio.run(app.handler("arg", _FakeRequest({...}))); assert resp.status_code==403`, `monkeypatch.setattr(app,"_require_account",...)`. **HTTP 아닌 직접 함수호출** → `dependency_overrides` 미적용 → TestClient 전환 필수.

---

## 1. 설계 결정

### 1.1 conn 처리: **shared `get_conn` yield 의존성** (1택)
근거: `_connect_memory` 무풀 + 핸들러 대다수가 인증 conn=쿼리 conn 재사용. 자체 단명 conn 방식은 인증 요청마다 연결 1→2(TCP+SET SESSION 2x) = 성능 퇴행.
```python
def get_conn():
    conn = _connect_memory()
    try:
        yield conn
    finally:
        try: conn.close()
        except Exception: pass
```
`get_current_account` 가 `Depends(get_conn)` 공유 → FastAPI use_cache 로 인증 conn = 핸들러 conn 동일 객체.

**[보정 BLOCKING-2]** 트랜잭션 토글 route handler 정확 목록 = **memory conn** `autocommit=False` 토글: `admin_create_product@22071` / `admin_update_product@22190` / `admin_delete_product@22353` / `_ds_write_common@14056`. **제외**: `_autonomous_generate_product_prompt@21195`(route 아닌 내부함수 — DI 무관), 모든 `_pg_connect(autocommit=False)`(별개 pg conn, get_conn 무영향). 확인: 22071/22190/22353 은 본문 finally 에서 `autocommit=True` **복원**하므로 teardown `if not conn.autocommit: conn.rollback()` 안전망은 정상경로 **미발화**(무해). 단 이들은 bulk 변환 금지 — **전용 Phase 에서 개별 마이그**(autocommit 토글+commit+복원 본문 그대로 보존).

### 1.2 `get_current_account` (필수 인증, 미인증→401)
```python
def get_current_account(request: Request, conn = Depends(get_conn)) -> dict:
    account = _get_authenticated_account(conn, request)   # (conn, request) 순서 주의
    if not account:
        raise _AuthError("로그인이 필요합니다.", 401)
    return account
```
부수효과(WebAuthSessions LastSeenAt/RemoteAddr/UserAgent UPDATE) 보존 위해 반드시 `_get_authenticated_account` 직접 호출. account dict = `_fetch_account_rows` SELECT 키 + `permissions:dict[str,bool]`(동적 catalog 포함)/`permission_overrides`. **정적 PERMISSION_CODES iterate 금지** — `.get(perm)` 만.

### 1.3 `get_optional_account` (anonymous 허용, 절대 raise 금지)
```python
def get_optional_account(request: Request, conn = Depends(get_conn)) -> dict | None:
    try:
        return _get_authenticated_account(conn, request)
    except Exception:
        return None
```
**[보정 MEDIUM-1]** try/except 가 LastSeen UPDATE 까지 감싼다 → "조회 성공+UPDATE 예외→익명 강등" 은 기존 `_optional_account` 의 fail-soft 동작이며 **byte-for-byte 보존**(회귀 아님). fail-soft 200 핸들러(llm_health/get_session/auth_me)도 이 의존성으로 분류(401 금지).

### 1.4 `require_permission` (정적 perm 팩토리) — **[보정 BLOCKING-1] message 인자 필수**
```python
def require_permission(*perms, message="권한이 없습니다.", status_code=403):
    def dep(account = Depends(get_current_account)):
        for p in perms:
            if not _account_has_permission(account, p):   # account['permissions'].get(p)
                raise _AuthError(message, status_code)
        return account
    return dep
```
- generic 메시지는 9건뿐 → **각 마이그 사이트는 원본 `_json_error` 의 정확한 메시지를 `message=` 로 전달**(60종 byte 보존). 메시지가 정확히 "권한이 없습니다." 인 사이트만 기본값 사용.
- get_current_account 의존 → 401 이 403 보다 선행(우선순위 보존). **AND 의미만**. OR/분기/동적 → §1.6.

### 1.5 `_AuthError` + exception handler (응답셰이프 보존, 최우선 함정)
```python
class _AuthError(Exception):
    def __init__(self, message, status_code):
        self.message = message; self.status_code = status_code

@app.exception_handler(_AuthError)
async def _auth_error_handler(request, exc):
    return JSONResponse({"error": exc.message}, status_code=exc.status_code)
```
`HTTPException` 사용 시 body `{"detail":...}` 로 키 회귀 → 금지. handler 등록 + 의존성 도입 **동일 PR(Phase 0)**. CORS/TrustedHost 미들웨어 순서 불변, `@app.exception_handler` 반환 JSONResponse 는 ExceptionMiddleware→CORSMiddleware 정상 통과.

### 1.6 동적 perm / OR / 분기 → account-only DI + 본문 검사
require_permission 으로 못 옮기는 3종(의미 역전 방지): ① 동적 perm(`_metadata_resolve_account_perm@27664`, 라우트 27933) ② OR(19874 `console.access|account.read`) ③ 분기(24450 action별). → `account=Depends(get_current_account)` 만 끌어올리고 권한검사는 본문에 `if not _account_has_permission(...): raise _AuthError(<원본 메시지>,403)` 유지.

---

## 2. 단계별 순서 (committable 증분)

매 게이트: `make test` green + `pytest test_route_parity_p5b.py`(경로/메서드/순서 골든, 라우터 미분할이라 Phase 0..N 불변).

- **Phase 0 — 가산적 토대(순수 추가)**: `get_conn`/`get_current_account`/`get_optional_account`/`require_permission`/`_AuthError`+handler 정의. 기존 helper 전부 유지(미사용). 게이트: make test 무변화. 롤백 100% 안전.
- **Phase 1 — 테스트 인프라 + 파일럿**: `conftest.py`(TestClient 픽스처 + `as_account(perms={...})` 헬퍼) + 대표 핸들러 1개(파일럿: `get_llm_health@10760`) DI 전환 + 테스트 TestClient 전환. `_connect_memory` monkeypatch 유지. 게이트: 파일럿 401/403/happy + make test + route-parity.
  - **[§18.8 패널 이월 — 첫 소비자 전 필수]** (REV-20260629-0003):
    - **(HIGH)** `get_conn` 의 `_connect_memory()` 실패를 try/except 로 감싸 legacy 와 동치인 curated 500 을 내도록 보정. legacy 핸들러는 conn 획득 실패 시 `_json_error("db connection failed", 500)` 반환 → get_conn 도 동일 셰이프(예: `raise _AuthError("db connection failed", 500)`). **단, conn-failure 메시지가 사이트별로 다른지 먼저 grep 분석**(403 메시지 60종 선례) — 다르면 메시지 보존 전략 결정.
    - **(LOW)** `require_permission()` 무인자 호출 가드(빈 perms → 인증만 통과하는 footgun) — `if not perms: raise ValueError(...)`.
    - **(검증)** `_AuthError` 실제 raise / deps wire 후 응답 셰이프 동치(401 `{error}` vs `_json_error`, 422 ordering)를 별도 golden/회귀 테스트(§4.2)로 재검증. route-parity 는 exception-handler 등록 변화를 구조상 미탐지.
- **Phase 2 — (A) 단순 require**(~95, 가장 기계적). PR당 15-25 핸들러.
- **Phase 3 — (B) require+인라인 perm**. AND→`require_permission(...,message=원본)`, OR/분기→account-only+본문.
- **Phase 4 — (C) `_require_permission` 6콜러 + (E1) 단명-conn 인증 헬퍼** → require_permission 승격.
- **Phase 5 — (F) optional 2 + fail-soft 200** → get_optional_account.
- **Phase 6 — (D) 동적 perm + (G) 재dispatch**. **(G1) `_ask_core` 추출 선행**(post_fix_with_ai→ask 재dispatch TypeError 방지).
- **Phase 7 — 트랜잭션 토글 4핸들러(22071/22190/22353/14056) 개별 + (E2) `_ds_write_common`/`_db_rule_gate` 열린-conn 계약 해체**. 최후순위.
- **Final — helper→web_context 이동 + APIRouter 추출(include_router) + route-parity 골든 갱신(diff 리뷰) + 브라우저 로그인 QA + §18.8 패널 + 배포**.

---

## 3. worklist

### 3.1 핸들러 (카테고리)
| Cat | 설명 | 개수 | 대표 | 레시피 |
|-----|------|------|------|--------|
| A | 단순 require+동일 conn | ~95 | 15657,17430,18031,19727,24584,29011 | helper삭제→`account=Depends(get_current_account),conn=Depends(get_conn)` |
| B | require+인라인 `_account_has_permission` | ~60 | 13345,13627(AND),19874(OR),24450(분기) | AND→`require_permission(...,message=원본)`; OR/분기→account-only+본문 |
| C | `_require_permission` 정적 | 6 | 26189,26247,26327,26414(kb.ingest.manual),27272 | `Depends(require_permission('kb.sample.curate',message=원본))` |
| D | 동적 perm | 1 | 27672(라우트27933) | account-only+본문 |
| E1 | 단명-conn 인증헬퍼(account만) | 21 | `_metadata_resolve_account@26407`(19콜러) 등 | require_permission 승격, PG conn 무영향 |
| E2 | 열린 conn 반환 헬퍼 | 9 | `_ds_write_common@13948`,`_db_rule_gate@23053` | 계약 해체, 최후순위 Phase 7 |
| F | optional | 2 | 15875,18906 | `Depends(get_optional_account)`+None분기 |
| 트랜잭션 | memory conn autocommit 토글 | 4 | 22071,22190,22353,14056 | **개별 마이그**, commit/복원 본문 보존, Phase 7 |
| G1 | 내부 재dispatch | 1 | 15570→ask | `_ask_core` 추출 선행 |
| SSE | 사전게이트 스트림 | 3 | 24311,24356,24418 | 시그니처 require_permission, StreamingResponse 미수정 |

### 3.2 테스트 (23 `_require_account` + 11 `_account_has_permission`)
공통: `_connect_memory` monkeypatch **전 파일 유지**(DB seam 미절단). `asyncio.run`/`_FakeRequest` 제거(query_params→`params=`, body→`json=`, path→URL 인라인).
- **[보정 MEDIUM-2]** conftest `as_account(perms={...})` 표준화. **`{"Id":1}` 축약 금지** — 권한 관련 테스트는 `permissions: dict[str,bool]` 명시(403 테스트=해당 perm False, happy=True). "최소변경(권고 B)" 철회.
- **[보정 MEDIUM-3]** **테스트 함수 단위 전환**: route handler 를 직접 `asyncio.run` 하는 함수만 TestClient 화. 헬퍼(`_ds_write_common` 등) 직접호출 함수는 Phase 7 까지 보존(같은 파일 내 혼재 주의: test_datasource_delete, test_metadata_phase2 sync/async).
- 누락 보완 파일: test_avatar_icon_upload, test_conversation_archive, test_usage_conversations. 각 Phase 게이트에서 `grep -l` 로 "이 클러스터 핸들러를 패치하는 테스트가 전부 동반 전환됐나" 기계 검증.

### 3.3 엣지 (개별)
post_fix→ask(`_ask_core` 선행), _ds_write_common/_db_rule_gate(계약해체), admin_metadata_suggest(account-only), public_share_view(optional None), csv export@28794(account만, conn 본문), 트랜잭션 4핸들러, WebSocket 0, 배경스레드(account 사전해결), 프로덕션 monkeypatch 0.

---

## 4. 검증 전략 (적대적)
- **4.1 route-parity**: 매 게이트. Depends 추가는 경로/순서 불변. Final 만 골든 갱신(경로집합 동일+순서검수).
- **4.2 401/403 회귀 스위트(Phase 1 신규)**: 카테고리별 대표 + status 정확 + body **글자단위(사이트별 골든 메시지)** + **`detail` 키 부재 단언**(HTTPException 회귀탐지) + 401 선행 + optional no-raise 200 + CORS 헤더 + Set-Cookie 부재.
- **4.3 부수효과 동치**: **[보정 HIGH-2]** LastSeenAt UPDATE 는 override 미적용 **전용 통합테스트**(실 conn+실 쿠키+실 `_get_authenticated_account`)로 커버(override 시 미발화). 동적 catalog code acct 로 require_permission 통과 확인(정적 drop 탐지).
- **4.4 라이브 RBAC smoke**: **[보정 HIGH-2]** 기존 라이브 HTTP smoke 4종(`test_auth_me_rbac`/`test_admin_me_rbac`/`test_kb_ingest_rbac`/`test_search_rbac`, urllib 기반)을 Final QA 게이트 명시 자산으로 등재 — `_AuthError`→handler 셰이프의 전체 미들웨어(TrustedHost/CORS) 통과 검증(TestClient 는 일부 우회). `test_kb_ingest_rbac` 타깃 `/api/admin/attachments/kb-ingest` 는 현 리비전 부재(stale) → 현존 엔드포인트로 갱신 또는 폐기.
- **4.5 브라우저 로그인 QA(Final, win-browser.py)**: 로그인→쿠키→인증페이지 / 무권한 admin→403+UI / 로그아웃→401 / public share 익명.

## 5. 위험 (요약)
HTTPException 셰이프(R1, _AuthError+detail부재단언) · handler 미등록 500(R2, 동일PR) · post_fix→ask TypeError(R3, _ask_core 선행) · conn 이중/누락 close(R4, 원자단위) · perm 의미역전(R5, OR/분기/동적 account-only) · LastSeenAt 누락(R6) · 동적 catalog drop(R7, .get만) · optional raise(R8) · route-parity 골든(R11) · **403 메시지 회귀(R14, message= 전달 + 사이트별 골든)** · **트랜잭션 미커밋유실(R13, 개별 마이그+복원 보존)**.

### 부록: 마이그 원자단위
핸들러 1개 = ① 인라인 conn 생성 삭제 ② 모든 수동 close 삭제 ③ `_require_account`+`if error` 삭제 ④ `account=Depends(...), conn=Depends(get_conn)` 추가 ⑤ 동반 테스트(함수 단위) TestClient 전환. **부분 적용 금지**.
