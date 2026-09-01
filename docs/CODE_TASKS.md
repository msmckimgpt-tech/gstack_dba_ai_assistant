---
doc_type: CODE_TASKS
source_of_truth: true
lifecycle: active
edit_policy: rewrite
ai_read_priority: 5
---
# CODE_TASKS — TASK 카드 카탈로그 (변경유형 → 코드영역 → 재귀 실행)

<!-- feature-0012 P5b Final 성과 위에 구축한 AI-navigation 카탈로그.
     app.py 19,650 → 3,722 줄(-81%, P5b 완결 시점). 핸들러 전량이 routers/ 로 추출됨 — 37개 파일(route-module 29 + 언더스코어 공유모듈 7 + `__init__`, 2026-09-01 재실측).
     source: routers/*.py + docs/ROUTEMAP.md + static/graph/ 실측(2026-07-13; routers 카운트는 2026-08-25 재실측). freshness 는 ROUTEMAP source_commit 로 검증. -->

> **이 문서의 용도**: "무엇을 바꾸려는가"(변경유형)를 입력으로, **어느 파일:심볼에서 시작해 →
> 어떤 순서로 참조하고 → 무슨 grep 으로 호출자/피호출자를 재귀 확장하고 → 무엇을 불변으로 지키고 →
> 어떻게 검증하는가**를 기계적으로 지시하는 TASK 카드 모음. 각 카드는 self-contained: 카드 하나를
> 끝까지 따르면 변경이 완결된다.
>
> **먼저 읽을 인덱스**: 구체 route 를 바꾼다면 [`ROUTEMAP.md`](ROUTEMAP.md)(L0 INDEX, method+path →
> router 파일:handler → auth) 에서 좌표를 확정한 뒤 여기로 온다. ROUTEMAP 은 `python3 bin/gen-routemap.py`
> 자동생성(정본=`@router` 데코레이터 + `register_all` INCLUDE_ORDER).

---

## 재귀 탐색 4계층 (모든 카드의 공통 골격)

카드의 "Recurse via" 는 이 계층을 literal grep 으로 오르내리는 지시다. **코드를 붙여넣지 말고 file:line
참조로 이동**(hop budget: 한 번에 한 계층).

| 계층 | 무엇 | 진입 방법 | durable anchor |
|---|---|---|---|
| **L0 INDEX** | route/기능 → 모듈 | `ROUTEMAP.md` 표에서 method+path 검색 | 없으면 → `grep -rn '"/api/부분경로"' routers/` |
| **L1 MODULE** | 모듈 목적·엔드포인트·의존 | 파일 첫 docstring(도메인+범위) + `INCLUDE_ORDER` | `head -6 routers/<mod>.py` |
| **L2 SYMBOL** | 핸들러 시그니처·권한 | `grep -n 'def <handler>' routers/<mod>.py` | 시그니처의 `Depends(...)` 가 auth 선고지 |
| **L3 TRAVERSE** | ↓피호출자 / ↑호출자 | ↓ `grep -n 'app\._' routers/<mod>.py` · ↑ `grep -rn '<symbol>' src/ tests/ static/` | app.py 꼬리 rebind = 심볼→소유모듈 역인덱스 |

---

## 공통 규약 (전 카드 불변식 — 위반 = behavior 회귀)

1. **app.X 동적참조** — 라우터는 `import app` 후 **호출시점** `app.get_current_account` / `app._json_error`
   식으로 접근한다. `from app import X` 는 **금지**(monkeypatch·`dependency_overrides` 관통이 깨진다).
   실측: 25개 라우터가 `import app`, 예외 3개(`admin_conversations`·`media` 등)만 `from app import
   require_permission, get_conn` — **DI seam 객체 한정**(`dependency_overrides` 는 객체 동일성으로 매칭되므로
   그 3심볼은 bound-import 가 안전, 나머지 헬퍼는 여전히 dynamic).
2. **꼬리 rebind = 역인덱스** — `app.py` 맨 끝 `register_all(app)` **직후** L3175~3722 에서
   `from routers.<mod> import _foo` 로 이동 심볼을 app 네임스페이스에 재부착한다. "이 심볼 어느 모듈?"
   은 이 블록을 grep 하면 즉답: `grep -n '<symbol>' app.py` → `from routers.<owner> import`.
3. **register_all + INCLUDE_ORDER** — `routers/__init__.register_all(app)` 이 **비-언더스코어 + `router`
   보유** 모듈을 자동발견해 `(INCLUDE_ORDER, name)` 순 include. **신규 라우터 = `router` 심볼 파일 추가만**
   (app.py 꼬리 편집 불필요 — 병렬 배선 경합 제거). 언더스코어 접두(`_conv_store` 등 5개) = register_all 제외.
4. **DI seam (app 정본 잔류)** — `get_conn`(fail-soft: `_connect_memory` 실패 → `None` yield, finally
   에서 rollback+close), `get_current_account`(conn None→500 `"db connection failed"`, 미인증→401),
   `require_permission(*perms, message=...)`(정적 AND 게이트, 무인자→ValueError). 이동 금지.
5. **web_context 단방향 추출** — leaf helper(app 의존 0, stdlib-only)는 `src/web_context.py` 로 가고
   app 이 `from web_context import` 로 재부착. `web_context` 는 **절대 `from app import` 안 함**(순환 불가 보장).
6. **keep-in-app 패치단일점** — `record_audit_event`(setattr 12× 패치점)·`_connect_memory`·
   `_account_can_access_conversation` 는 app 잔류(이동하면 monkeypatch 사이트가 깨진다).
7. **ITEM-11 DI-rework** — 실제 conn-leak 핸들러 **13개**만 account+conn DI 전환, 나머지 **37개**는
   keep-inline 정당(txn 토글·fail-soft·pre-auth gate·streaming).

---

## 영역 지도 (routers/ 37파일, 2026-09-01 실측)

- **29 route-module** (`@router` + `INCLUDE_ORDER`, register_all 자동등록): `ROUTEMAP.md` 인덱스 표 참조.
- **8 언더스코어 공유모듈** (register_all 제외, 꼬리 rebind 로 재부착):
  - `routers/__init__.py` — `register_all` 자동등록 기계.
  - `routers/_conv_store.py` — 대화 저장소 공용 데이터 계층(share + conversations 소비).
  - `routers/_prompt_context.py` — 프롬프트 컨텍스트 조립(admin_roles·admin_products·auth·conversations 소비).
  - `routers/_audit_infra.py` — 감사 인프라 헬퍼(전 라우터 소비).
  - `routers/_bootstrap_schema.py` — 웹 테이블/시드 부트스트랩(startup 기계가 호출, DDL idempotent).
  - `routers/_folder_store.py` — 대화 폴더 PG 스토어(feature-0024, `conversation_folders`·`folder_conversation_map`).
  - `routers/_console_jobs.py` — 콘솔 작업의 프롬프트 조립 + 개인 AI 산출물의 기존 저장경로 반영(feature-0043, 2026-08-31 신설).
  - `routers/_console_llm.py` — 관리 콘솔 LLM 상태 판정 단일 정본(feature-0043, 2026-08-31 신설).
- **공유 컨텍스트**: `src/web_context.py`(leaf, stdlib-only) · `shared/db.py`(repo-root, PG `_pg_connect`) ·
  `unit/feature-0003-agent-web-ui/src/modules/`(attachment mirror·group_members 등).
- **app.py 잔류(4,000줄, 2026-08-25 실측)**: DI seam · 인증보조(`_AuthError`/`_auth_error_handler`/`_json_error`/`_require_account`)
  · audit(`record_audit_event`) · 보안게이트(`_ssrf_check_host`/`_enforce_audit_prod_gate`) ·
  lifecycle(`@app.on_event` `_start_*`/`_reconcile_*`) · FastAPI app+미들웨어 · config 상수 · rebind 블록 · register_all.

---

# TASK 카드

## TASK 1 — 새 endpoint 추가 (기존 도메인)

**Match keywords**: 새 API·엔드포인트 추가·"이 도메인에 route 하나 더"·GET/POST/... 신규 경로.

**Entry region**: `routers/<domain>.py` — 도메인 소유 라우터에 `@router.<method>("/api/...")` + 핸들러 함수 추가.
도메인은 `ROUTEMAP.md` 인덱스 표(담당 도메인 열)에서 확정.

**Reference regions (ordered)**:
1. `docs/ROUTEMAP.md` — 대상 도메인 섹션에서 소유 파일·INCLUDE_ORDER·기존 경로 네이밍 확인(중복 경로 회피).
2. 같은 파일의 **인접 핸들러** — 시그니처 템플릿 복사. 실측 3형:
   - 인증만: `def h(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn))`
     (예 `routers/conversations.py:108 use_conversation`).
   - 정적 권한: `account=Depends(app.require_permission("perm.code", message="…"))`
     (예 `routers/admin_usage.py:126 admin_llm_usage`).
   - 무인증: 파라미터에 auth dep 없음(예 `routers/static_pages.py index`).
3. `app.py` DI seam — `def get_conn`(≈L1459)·`def get_current_account`(≈L1492)·`def require_permission`(≈L1523)
   로 계약 확인(라인은 grep 재확정: `grep -n 'def get_conn\|def get_current_account\|def require_permission' app.py`).
4. `tests/conftest.py` — `client` + `as_account`/`as_anonymous` 픽스처로 신규 route 테스트 작성.

**Recurse via (literal grep)**:
- 피호출자(필요 헬퍼 발굴): `grep -n 'app\._' routers/<domain>.py` (그 도메인이 이미 쓰는 app.* 헬퍼 목록) ·
  `grep -rn 'def <helper>' src/web_context.py src/routers/_*.py`.
- 호출자(프론트 배선): `grep -rn '/api/새/경로' unit/feature-0003-agent-web-ui/src/static/`.

**Invariants**: 규약 §1(app.X dynamic) · §3(app.py 꼬리 편집 **불필요** — register_all 이 기존 router 를 이미
등록) · RBAC 는 시그니처 `Depends` 에서 선언 · 응답 셰이프 `JSONResponse({"error":msg}, status)` 유지.

**Verify**:
- `python3 bin/gen-routemap.py` (ROUTEMAP 에 새 행 등장 확인).
- 의도적 route 추가 → route parity 골든 갱신: `tests/test_route_parity_p5b.py::_build_table()` 출력으로
  `tests/route_snapshot_p5b.json` 덮어쓰기(먼저 `make test` 로 diff 확인 후 의도 검증).
- `make test` (신규 핸들러 테스트 + route parity + 205 route 골든).

---

## TASK 2 — 새 도메인 라우터

**Match keywords**: 새 도메인·모듈 신설·"이건 기존 파일에 안 맞아"·독립 라우터.

**Entry region**: 신규 `routers/<new>.py` 생성. 최소 골격:
```
"""<도메인 라벨 — ROUTEMAP 인덱스에 그대로 노출될 첫 문장>."""
from __future__ import annotations
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import app

INCLUDE_ORDER = <미사용 값>   # 등록 순서 고정
router = APIRouter()
```
`register_all` 이 **자동발견** → app.py·`__init__.py` 편집 불필요.

**Reference regions (ordered)**:
1. `routers/admin_settings.py` (INCLUDE_ORDER=230, 3-route 최소 라우터) — 최신 신규 라우터 템플릿.
2. `routers/__init__.py` `register_all` — 자동발견 규칙(비-언더스코어 + `router` 심볼 + INCLUDE_ORDER 정렬) 확인.
3. `docs/ROUTEMAP.md` 인덱스 표 — INCLUDE_ORDER 충돌 회피(현행 10~230, 신규는 240 등 gap 사용).

**Recurse via (literal grep)**:
- 충돌 회피: `grep -rn 'INCLUDE_ORDER' unit/feature-0003-agent-web-ui/src/routers/` (사용 중인 순서 census).
- 등록 규칙 확인: `grep -n 'router = APIRouter\|def register_all' routers/__init__.py routers/<new>.py`.

**Invariants**: 파일명 **비-언더스코어**(언더스코어면 register_all 제외됨) · `router` 심볼 필수 · `INCLUDE_ORDER`
유일 · docstring 첫 문장 = ROUTEMAP 도메인 라벨 · 규약 §1(`import app` dynamic). `__init__.py` docstring 의
"23개 include 순서 스냅샷"은 신규 추가 시 count 가 늘어남 → route parity 골든 동반 갱신으로 흡수.

**Verify**:
- `python3 bin/gen-routemap.py` (인덱스에 새 섹션 + INCLUDE_ORDER 행 등장).
- route parity 골든 갱신(새 route 추가분) → `tests/route_snapshot_p5b.json` 업데이트.
- `make test` (register_all 이 예외 없이 include, parity 통과).

---

## TASK 3 — 핸들러 auth/권한 변경

**Match keywords**: 권한 코드 바꿈·403 게이트 추가/제거·인증 필수화·RBAC 조정.

**Entry region**: `routers/<domain>.py` 대상 핸들러 **시그니처**의 `Depends(...)` 항(=auth 선고지).

**Reference regions (ordered)**:
1. `docs/ROUTEMAP.md` auth 열 + 권한(RBAC) 열 — 현재 게이트 확인(변경 전 baseline).
2. `app.py` `def require_permission`(≈L1523, 정적 perm AND 게이트) · `def get_current_account`(≈L1492).
3. 같은/타 파일에서 **목표 게이트를 이미 쓰는 인접 핸들러** — 형태 복사(정적 AND vs body 검사).

**Recurse via (literal grep)**:
- OR/동적 권한 판정: `grep -n '_account_has_permission' routers/<domain>.py` (본문 분기형인지 확인).
- 권한 코드 카탈로그: `grep -rn '"<perm.code>"' src/ static/ docs/SECURITY.md`(코드 존재·프론트 표기 교차).

**Invariants**:
- 정적 **AND** (모든 perm 필요) → `account=Depends(app.require_permission("p1","p2", message="원본 403 메시지"))`.
- **OR / 동적 catalog / 분기** → `account=Depends(app.get_current_account)` + 본문 `app._account_has_permission(account, p)`
  (정적 `PERMISSION_CODES` iterate 금지).
- 403 body 문자열 **byte-보존**(60종 메시지 회귀 방지) · `require_permission()` 무인자 = ValueError(footgun guard).

**Verify**:
- runtime snapshot: `tests/conftest.py` `client` + `as_account`(권한 있는/없는 계정) → 200/403, `as_anonymous` → 401.
- `python3 bin/gen-routemap.py` (auth·권한 열 갱신 반영).
- `make test`.

---

## TASK 4 — 인라인 auth → DI 전환 (ITEM-11 형)

**Match keywords**: conn leak·`_connect_memory` 수동·`conn.close()` 산재·DI 정리·ITEM-11.

**Entry region**: `routers/<domain>.py` 에서 아래 안티패턴을 가진 핸들러:
```
conn = app._connect_memory()            # 수동 획득
account, error = app._require_account(request, conn)
if error: conn.close(); return error    # 매 분기 close
```

**Transform**: 시그니처를 `account=Depends(app.get_current_account), conn=Depends(app.get_conn)` 로 바꾸고
본문의 `_connect_memory`/`_require_account`/**모든 `conn.close()`** 제거(`get_conn` finally 가 rollback+close 담당).

**Reference regions (ordered)**:
1. **keep-inline 반례**: `routers/conversations.py:2284 ask` — 매 검증분기마다 `conn.close()` 수동 호출
   + pre-auth 검증 → **전환 금지** 유형.
2. **DI-변환 정답**: `routers/conversations.py:108 use_conversation` — `Depends(app.get_current_account)` +
   `Depends(app.get_conn)`, 본문 close 없음.
3. `app.py` `def get_conn`(≈L1459) — fail-soft(`None` yield) + finally(autocommit 아니면 rollback → close) 계약.

**Recurse via (literal grep)**:
- 후보 발굴: `grep -rn 'app\._connect_memory()' routers/` ∩ `grep -rn 'app\._require_account' routers/` ∩
  `grep -rn 'conn\.close()' routers/<domain>.py`.
- 테스트 템플릿: `ls tests/test_item11_batch*` (byte-equivalence 테스트 13개 baseline).

**Invariants (keep-inline 판정 — 하나라도 참이면 전환 금지)**:
- `try/finally` 로 감싼 트랜잭션 토글(`autocommit=False` + 본문 commit).
- fail-soft optional(미인증도 200, `get_optional_account` 계열).
- pre-auth gate(인증 전에 입력 검증 후 조기 return).
- streaming/long-poll 응답.
전환 시 **byte-동치** 필수: `conn is None → get_current_account 가 500 "db connection failed"`(legacy 121 사이트 uniform 과 동일).

**Verify**:
- `tests/test_item11_batchN_*.py` byte-equivalence(client + as_account, 응답 body/status 1:1).
- route parity **불변**(경로/순서 안 바뀜) · `make test` · `tests/test_di_seam_p5b.py`.

---

## TASK 5 — app.py 잔류 헬퍼 수정 / 이동

**Match keywords**: app.py 함수 고침·헬퍼 이동·"이거 라우터로 빼도 되나"·순환 import 우려.

**Entry region**: `app.py` 대상 심볼(`grep -n 'def <symbol>' app.py`). 대표:
`record_audit_event`(≈L983)·`_connect_memory`(≈L1143)·`_account_can_access_conversation`(≈L1232)·
`_ssrf_check_host`(≈L1777)·DI seam(≈L1459~1546).

**keep-in-app 판정 (이동 금지 조건)**:
- 패치단일점: `record_audit_event`(setattr 12×) · `_connect_memory` · `_account_can_access_conversation`.
- DI seam(`get_conn`/`get_current_account`/`require_permission`): `dependency_overrides` 객체동일성 → 잔류.
- 인증보조(`_AuthError`/`_auth_error_handler`/`_json_error`/`_require_account`) · 보안게이트 · `@app.on_event` lifecycle.

**이동 대상이면 목적지**:
- leaf(app 의존 0, stdlib-only) → `src/web_context.py` + 꼬리 rebind `from web_context import <symbol>`.
- 도메인-공유 → `routers/_<shared>.py`(예 `_conv_store`) + 꼬리 rebind `from routers._<shared> import <symbol>`.

**Reference regions (ordered)**:
1. `app.py` 꼬리 rebind 블록(L3175~3722) — 이동 시 재부착 지점(심볼→소유모듈 역인덱스 유지).
2. `src/web_context.py` 헤더 INVARIANT — "절대 `from app import` 안 함" 규칙(leaf 자격 판정).
3. `docs/MODIFY.md` — 변경 append-only 로그(CHG-<ts> 엔트리).

**Recurse via (literal grep)**:
- 소비처 census(이동 전 필수): `grep -rn '\b<symbol>\b' src/ tests/`.
- app.X 접근점: `grep -rn 'app\.<symbol>\|from app import.*<symbol>' routers/ tests/`.
- 패치 사이트: `grep -rn 'monkeypatch.setattr(app, *"<symbol>"' tests/` (>0 이면 keep-in-app 강력 신호).

**Invariants**: 이동 시 꼬리 rebind 로 `app.<symbol>` 이 여전히 resolve(dynamic ref + monkeypatch 보존) ·
`web_context` stdlib-only 유지 · 패치단일점 헬퍼는 이동 금지.

**Verify**: `grep -rn 'app\.<symbol>' src/ tests/` 소비처가 여전히 resolve(rebind 확인) · `make test`
(`test_di_seam_p5b`·`test_item11_*`·`test_audit_*` 등 seam 회귀 게이트).

---

## TASK 6 — route → 어느 파일? (역탐색)

**Match keywords**: "이 URL 핸들러 어디"·경로만 알고 파일 모름·역인덱스.

**Entry region**: `docs/ROUTEMAP.md` 전체 route 표에서 method + path 검색 → **router 파일 : handler** 직행.

**Reference regions (ordered)**:
1. `docs/ROUTEMAP.md` (L0 INDEX) — 1차 조회.
2. 없으면(신규·미생성 인덱스): `grep -rn '"/api/부분경로"' unit/feature-0003-agent-web-ui/src/routers/`.
3. 심볼만 알 때(경로 모름): `grep -n '<symbol>' app.py` → 꼬리 rebind 의 `from routers.<owner> import` 로 소유모듈 역추적.

**Recurse via (literal grep)**:
- 데코레이터: `grep -rn '@router\.\(get\|post\|put\|patch\|delete\).*경로조각' routers/`.
- handler 정의: `grep -rn 'def <handler>' routers/`.

**Invariants**: ROUTEMAP 은 **자동생성**(수기 편집 금지) — freshness 는 헤더 `source_commit` 스탬프로 판단.
SSOT 는 `@router` 데코레이터 + `register_all` INCLUDE_ORDER.

**Verify**: `python3 bin/gen-routemap.py --check` (재생성 결과가 커밋본과 다르면 exit 3 = drift 경보).

---

## TASK 7 — DB / 모델 변경 추적

**Match keywords**: 테이블 추가·컬럼 변경·스키마·마이그레이션·PG vs MySQL.

**Entry region**: 핸들러 → 데이터 계층 피호출자. 계층별 진입:
- **웹 MySQL 테이블(`WebXxx`)**: `routers/_bootstrap_schema.py` 의 `_ensure_*_schema` (startup 기계가 호출하는
  **idempotent DDL** — 웹 UI 는 alembic 미사용).
- **PG `agent_runtime` 테이블**(`core_conversations` 등): `shared/db.py` `_pg_connect` +
  `unit/feature-0002-agent-core/alembic/versions/` (PG 정본은 alembic 마이그).
- **대화 저장소 공용 계층**: `routers/_conv_store.py` (share + conversations 소비).

**Reference regions (ordered)**:
1. `routers/_bootstrap_schema.py` — `_ensure_web_tables` 외 `_ensure_*` 오케스트레이션(웹 테이블 신설/변경점).
2. `shared/db.py` — PG 연결 진입 `_pg_connect`.
3. `unit/feature-0002-agent-core/alembic/` — PG 스키마 마이그(alembic.ini + versions/).
4. `src/modules/` — attachment_pg_mirror·group_members 등 특화 데이터 접근.

**Recurse via (literal grep)**:
- 테이블 사용처: `grep -rn '\bWeb<Table>\b' src/routers/ src/routers/_bootstrap_schema.py`.
- PG 경로: `grep -rn '_pg_connect\|agent_runtime\.' src/routers/ shared/db.py`.
- 마이그 대상: `grep -rn '<table_or_column>' unit/feature-0002-agent-core/alembic/versions/`.

**Invariants**: 웹 `WebXxx` 테이블은 `_ensure_*`(idempotent DDL)로만 생성(alembic 금지) · PG core 테이블은
alembic versions/ 로만 변경 · `_conv_store` 는 share/conversations 공용 → 한쪽만 보고 바꾸지 말 것(양쪽 소비 census).

**Verify**: `make test` (스키마 의존 테스트: `test_attachment_pg_cutover`·`test_history_calendar_pg_routing` 등) ·
PG 마이그는 alembic upgrade(agent-core) 파이프라인.

---

## TASK 8 — 그래프 뷰(UI) 변경 (static/graph 모듈)

**Match keywords**: 그래프·지식그래프·G6·노드/엣지·줌 LOD·우클릭 메뉴·상세/관계 패널·역할 칩·클러스터 배치·미니맵.

**Entry region**: `unit/feature-0003-agent-web-ui/src/static/graph/` — 모듈 선택은
[CODE_NAVIGATION.md §8](CODE_NAVIGATION.md) 표(변경 유형→모듈). 요약: 상태/상수=`graph-state.js` ·
역할 표식=`graph-roleviz.js` · 배치=`graph-rellayout.js`/`graph-simgroups.js` ·
init/로드/build/LOD/anim=`graph-core.js` · 우클릭/패널=`graph-ctxmenu.js` · CSS=`graph.css`.

**Reference regions (ordered)**:
1. 함수 위치: `grep -rn "function _metaXxx" unit/feature-0003-agent-web-ui/src/static/graph/` (라인 산술 금지 — 함수명이 durable anchor).
2. 경계 계약·좌표 재적용: `static/graph/MAPPING.md` (barrel 공개 4심볼·순환 import 규약·구 좌표 체인).
3. 백엔드 API 를 함께 바꾸면: `docs/ROUTEMAP.md` 에서 `/api/admin/metadata/*`(admin_metadata.py) 좌표 확정 후 TASK 1/3 병행. **그래프 데이터의 실체는 cross-feature** — `unit/feature-0002-agent-core/src/modules/metadata_graph.py`(조회 `search_nodes`·`neighborhood`, PG 동기화)가 정본이고 admin_metadata.py 는 `_mg` alias 로 위임한다(`from modules import metadata_graph as _mg`).

**Recurse via (literal grep)**:
- ↓피호출자(모듈 간): 모듈 상단 `import {...} from "./graph-xxx.js?v=dev"` 가 의존 선언 — `grep -n '^import' graph/<mod>.js`.
- ↑호출자: `grep -rn '<symbol>' unit/feature-0003-agent-web-ui/src/static/` (admin.js tab-switch 소비는 barrel 경유만).
- DOM 배선: `grep -n 'metadataGraph\|graphScopeSelect' unit/feature-0003-agent-web-ui/src/static/admin.html`.

**Invariants**: ① barrel(`graph/graph.js`) 경로·공개 4심볼 불변(admin.js 는 barrel 만 import) ② `?v=dev` placeholder 수기 bump 금지(빌드 주입 — §13.1) ③ top-level 즉시실행에서 cross-module 호출 금지(순환 import 는 호출시점 전제) ④ 상태 신규 추가는 const 객체 프로퍼티로(cross-module 재할당 불가) ⑤ G6/mermaid 는 UMD bridge.

**Verify**: `node --check graph/<mod>.js` + PB-0008 실 Windows 브라우저(로드·스코프·검색·줌·클릭·우클릭, 콘솔 에러 0 — `bin/win-browser.py`, 기록은 `docs/test-runs.d/` fragment).

---

## TASK 9 — 정적 자산 캐싱 / 캐시버스터(`?v=`) 변경

**Match keywords**: 캐시버스터·`?v=`·asset stamp·`Cache-Control`·immutable·no-store·배포 후 구버전 렌더·하드 리프레시.

**Entry region**: 판정 주체는 **upstream** 이다 — `unit/feature-0003-agent-web-ui/src/static_cache.py`
(`decide_cache_control` 정책표 + `StaticCacheHeadersMiddleware` ASGI 래퍼). 배선은
`src/app.py` 의 `app.mount("/static", …)`. 스탬프 생성은
`unit/feature-0002-agent-core/src/scripts/inject_asset_stamp.py`(→ `<static>/.asset-stamp` 사이드카),
빌드 훅은 `unit/feature-0002-agent-core/src/Dockerfile` 의 `RUN … inject_asset_stamp.py --root /app/web/static`.

**Reference regions (ordered)**:
1. 정책표·근거: `src/static_cache.py` 모듈 docstring (롤링 창 오염 시나리오 4단계 + 표).
2. 엣지 계약: `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — **`/static` 에 `Cache-Control` 을 강제하는 규칙을 두지 않는다**(제거 사유가 주석으로 고정됨).
3. 배포 게이트: `bin/deploy-web.sh` 의 `asset_stamp_verify`(baked 이미지에 `?v=dev` 잔존 시 ABORT) + `post_deploy_checklist` [3].
4. 근거 기록: `unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md` AC-ASCI-1~5.

**Recurse via (literal grep)**:
- 정책 소비자: `grep -rn "static_cache\|decide_cache_control\|StaticCacheHeadersMiddleware" unit/feature-0003-agent-web-ui/src/`
- 스탬프 생산자·소비자: `grep -rn "asset-stamp\|STAMP_SIDECAR\|inject_asset_stamp" unit/ bin/`
- 엣지 규칙 부활 감시: `grep -n "Cache-Control" unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`

**Invariants**:
① **immutable 은 요청 `?v=` 가 이 replica 의 빌드 스탬프와 일치할 때만** — 불일치는 `no-store`
(롤링 창의 버전 스큐 응답이 캐시에 굳는 것을 구조적으로 차단; 2026-07-28 라이브 사고 근거).
② 엣지가 `/static` 에 `Cache-Control` 을 강제하지 않는다(강제하면 ①이 무력화 — 테스트가 FAIL).
③ 사이드카는 content-hash 입력에서 **제외**(자기 참조 시 멱등성이 깨져 롤아웃마다 전 캐시 무효화).
④ `vendor/**` 의 `?v=` 는 라이브러리 pin(별개 버전 축) — 빌드 스탬프와 비교하지 않는다.
⑤ 전 구간 fail-open — 스탬프 부재·판정 예외는 헤더 미설정으로 통과(실패 방향 = 캐싱 상실이지 오염 아님).
⑥ 소스의 `?v=dev` placeholder 수기 bump 금지(빌드 주입 — §13.1 v3.35.1).

**Verify**: `unit/feature-0003-agent-web-ui/tests/test_static_cache_integrity.py` +
`unit/feature-0002-agent-core/tests/test_inject_asset_stamp_sidecar.py`(격리 + **실 injector→실 static
트리→실 StaticFiles 통합** — mount path 규약 같은 접합부 결함은 통합 케이스만 잡는다) ·
`caddy validate --adapter caddyfile` · 배포 후 결정론 헤더 프로브
(`curl -skI '<host>/static/admin.js?v=<현/구 스탬프>'` → `immutable` / `no-store`+`x-asset-stamp: mismatch`).

---

## TASK 10 — 배포 중 브리지(개인 AI) 연결이 끊긴다 / 드레인·게이트 변경

**Match keywords**: 배포하면 AI 연결이 끊긴다·`wait_for_request` 가 끊긴다·드레인·lame-duck·
`bridge_inflight`·`X-Bridge-Draining`·pre-drain 이 안 기다린다·MCP replica·점유가 안 풀린다.

**Entry region**: 관측·드레인 판정의 정본은 `unit/feature-0003-agent-web-ui/src/bridge_drain.py`
(대기 `waiting()` / 작업 `tool_call()` 를 **따로** 세고, `BridgeInflightMiddleware` 가 드레인 중
신규 도구 호출을 `503 X-Bridge-Draining` 으로 돌려보낸다 — 단 제출·첨부 읽기는 `DRAIN_EXEMPT_PATHS`
로 면제). 배선은 `src/app.py` 의 `app.add_middleware(bridge_drain.BridgeInflightMiddleware)`.
제어 창구는 `src/routers/system.py` 의 `/internal/bridge-{drain,activity,reclaim}`(loopback 전용).

**Reference regions (ordered)**:
1. 설계 근거(대기는 비우고 작업은 기다린다): `src/bridge_drain.py` 모듈 docstring + 미들웨어 docstring.
2. 게이트: `bin/deploy-web.sh` 의 `predrain`(브리지 축 대기) · `replica_drain_probe` ·
   `replica_release_drain` · `clear_stale_drain` · `on_exit_cleanup`(드레인 누수 차단) ·
   `rollout_mcp_phase`/`rollout_mcp_replicas`(엣지 전환 **앞**) · `reclaim_bridge_claims`.
3. 워커·gateway 축: `bin/lib/quiesce.sh` 의 `bridge_active_total`(fresh 만) · `server_llm_blocked`.
4. 엣지 계약: `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — `/api/ai/mcp*` 2 upstream
   LB(`lb_policy ip_hash`, active health 없음) + `/internal/*` 404.
5. 근거 기록: `unit/feature-0045-zd-bridge-continuity/docs/{FUNCTION,ANCHOR,DECISIONS}.md`.

**Recurse via (literal grep)**:
- 드레인 소비자: `grep -rn "bridge_drain\|_drain\." unit/feature-0003-agent-web-ui/src/`
- 스파인 seam: `grep -n "PREDRAIN_\|DRAINED_SVC\|MCP_REPLICAS\|bridge" bin/deploy-web.sh`
- 러너 쪽: `grep -n "draining\|_RECONNECT_BACKOFF\|_DRAINING_RETRY_FLOOR" unit/feature-0043-external-llm-bridge/src/bridge_agent.py`

**Verify**: `unit/feature-0045-zd-bridge-continuity/tests/`(60건 — 드레인 상태기계·게이트 실행·
토폴로지·내부 창구) · `caddy validate --adapter caddyfile` · 배포 로그의 `bridge_continuity_summary`
("끊김 0" 또는 강행/미확인 사유).

---

## 부록 — grep 쿡북 (durable anchors)

라인 번호는 app.py 재생성마다 drift 하므로 **grep 문자열이 정본 anchor**다.

| 찾는 것 | 명령 |
|---|---|
| DI seam 정의 | `grep -n 'def get_conn\|def get_current_account\|def require_permission' src/app.py` |
| 꼬리 rebind (심볼→모듈) | `grep -n '<symbol>' src/app.py` → `from routers.<owner> import` |
| register_all 자동발견 규칙 | `grep -n 'def register_all\|startswith("_")\|INCLUDE_ORDER' src/routers/__init__.py` |
| INCLUDE_ORDER census | `grep -rn 'INCLUDE_ORDER' src/routers/` |
| 라우터가 쓰는 app.* 헬퍼 | `grep -n 'app\._\|app\.get_\|app\.require_' src/routers/<mod>.py` |
| 정적 권한 게이트 | `grep -rn 'Depends(app.require_permission' src/routers/` |
| 인라인 auth (ITEM-11 후보) | `grep -rn 'app\._require_account\|app\._connect_memory()' src/routers/` |
| monkeypatch 사이트(이동 금지 신호) | `grep -rn 'monkeypatch.setattr(app' tests/` |
| route 역탐색 | `grep -rn '"/api/부분경로"' src/routers/` |
| ROUTEMAP drift 게이트 | `python3 bin/gen-routemap.py --check` |
| 전체 검증 | `make test` (agent 컨테이너 pytest + ruff, `--no-deps`) |
