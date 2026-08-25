---
doc_type: CODE_NAVIGATION
source_of_truth: true
lifecycle: active
edit_policy: rewrite
ai_read_priority: 4
---
# CODE_NAVIGATION — AI worker 재귀 탐색 가이드 (L1~L3)

<!-- L1~L3 companion to docs/ROUTEMAP.md (L0 INDEX). 손유지(hand-maintained). freshness: 2026-07-13 · source_commit: f7ad45d7 -->
> **이 문서가 답하는 것**: "바꿀 코드를 어떻게 *찾고*, 지금 보는 게 *뭘 하는지* 어떻게 *알고*, 인접 코드로 어떻게 *건너가나*."
> **정본 아님(reference)**: 사실의 정본은 코드(`routers/`·`app.py`)와 [ROUTEMAP.md](./ROUTEMAP.md)(L0, 자동 생성). 본 문서는 그 위를 걷는 *지도*다 — 링크가 아니라 **이름과 grep 명령**을 준다(matklad codemap 원칙).
> **대상 코드**: `unit/feature-0003-agent-web-ui/src/` — app.py(19,650→**3,722줄**, -81%)의 핸들러 전량이 `routers/` 35개 파일로 추출됨(2026-08-24 실측 — 29 route-module `@router` + 5 언더스코어 공유모듈 + `__init__` registrar — feature-0026 이 `admin_perf.py`(HTTP 성능 스냅샷, INCLUDE_ORDER=250)·leaf 계측 `src/perf_metrics.py` 추가; feature-0014 가 leaf `src/static_cache.py` — `/static` mount 를 감싸 "요청 `?v=` == 빌드 스탬프" 일 때만 immutable 을 부여하는 ASGI 래퍼 — 추가). leaf helper 는 `src/web_context.py`.

> **grep 실행 위치**: 이하 모든 grep 은 **코드 루트 `unit/feature-0003-agent-web-ui/src/`** 에서 실행한다(여기서 `routers/`·`app.py`·`web_context.py` 가 형제, 테스트는 `../tests/`). 정규식 앵커 없이 **리터럴 grep** 만 쓴다.

---

## 1. 어떻게 읽나 — 두 질문

**Q1. "X 하는 코드가 어디 있나?"** → [ROUTEMAP.md](./ROUTEMAP.md) 에서 `method + path` 를 찾아 **router 파일:handler** 로 직행. auth 열이 권한 게이트를 미리 선고한다. 경로를 모르면 도메인 키워드로 라우터 색인(ROUTEMAP 상단 표)을 훑는다. 경로 리터럴을 안다면 바로:
```
grep -rn "/api/new_conversation" routers/
```

**Q2. "지금 보는 게 뭘 하나?"** → 두 개의 docstring 을 읽는다(코드를 다시 읽지 말 것):
- **모듈 헤더 docstring** (파일 최상단) = 도메인·prefix·DI 계약. 예: `conversations.py` → "대화 조작: 생성·전환·이력·삭제·취소·완료·상태 … uniform `import app`+`app.X` 동적참조".
- **핸들러 docstring / 시그니처** = 이 함수 하나가 하는 일 + `Depends(...)` 로 드러난 auth/perm/conn seam.

> 이름으로 좁히고(name), grep 으로 확정한다(resolve via grep). 링크 클릭이 아니라 grep 이 이동 수단이다.

---

## 2. 4계층 재귀 탐색 (L0 → L3)

키워드/경로에서 시작해 아래로(callee) 위로(caller) 재귀한다. 각 계층은 **hop 예산**을 쓴다 — 필요한 만큼만 내려가고, 답을 얻으면 멈춘다(LocAgent SearchEntity→TraverseGraph→RetrieveEntity).

### L0 — INDEX (route/keyword → module)
[ROUTEMAP.md](./ROUTEMAP.md) 가 L0. `method + path` → **router:handler**, 그리고 auth 열(권한). 도메인만 알면 상단 라우터 색인(INCLUDE_ORDER 순 23행)에서 담당 파일을 고른다.
```
grep -rn "def admin_llm_usage" routers/          # handler → 파일 확정
```

### L1 — MODULE (router 파일: 목적·엔드포인트·상류·하류)
파일을 열고 **헤더 docstring** 으로 도메인·prefix·DI 계약을 잡는다.
- **엔드포인트 목록**(이 파일이 무엇을 노출하나):
  ```
  grep -n "@router." routers/conversations.py
  ```
- **상류(imports, 무엇에 의존하나)** — 파일 상단 `import app` + `from shared...` + `from web_context import ...`:
  ```
  grep -n "import" routers/conversations.py
  ```
- **하류(callees, 무엇을 부르나)** — 핸들러가 부르는 공유 심볼은 대부분 `app.X` 동적참조:
  ```
  grep -n "app\." routers/conversations.py
  ```

### L2 — SYMBOL (handler 시그니처 + docstring)
핸들러 한 개를 정조준. **시그니처의 `Depends(...)` 가 seam 을 전부 드러낸다**:
- `Depends(app.require_permission("conversation.create"))` → 정적 perm AND 게이트(auth+RBAC).
- `Depends(app.get_current_account)` → 인증만(OR/동적 perm 은 본문 검사).
- `Depends(app.get_conn)` → 요청-스코프 memory conn(fail-soft).
```
grep -n "async def new_conversation" routers/conversations.py   # 시그니처
```
본문의 `app.X(...)` 호출 = 이 핸들러의 **callees** → L3 로.

### L3 — TRAVERSE (양방향 재귀)

**DOWN (callees — 무엇을 부르나):**
| callee 유형 | 어디로 | 찾는 법 (src/ 에서) |
|---|---|---|
| leaf helper | `web_context.py` | `grep -n "def _get_client_ip" web_context.py` |
| 대화 store | `routers/_conv_store.py` | `grep -rn "def _share_load_active" routers/` |
| 스키마 부트스트랩 | `routers/_bootstrap_schema.py` | `grep -rn "def _ensure_web_tables" routers/` |
| 감사 인프라 | `routers/_audit_infra.py` | `grep -rn "def _audit_admin_mutation" routers/` |
| 프롬프트 컨텍스트 | `routers/_prompt_context.py` | `grep -rn "def _collect_account_prompt_context" routers/` |
| **keep-in-app** (app 잔류) | `app.py` | `grep -n "def record_audit_event" app.py` |

> 핸들러가 `app._share_load_active(...)` 라 써도 함수는 `routers/_conv_store.py` 에 산다. `app.X` 는 **꼬리 rebind**(§4)가 재부착한 것 — 정의는 소유 라우터에 있다. `def <심볼>` grep 이 진짜 집을 알려준다.

**UP (callers — 누가 부르나):**
- **심볼 → 소유 라우터(역인덱스)**: app.py 꼬리 rebind 블록에서 심볼을 grep → 바로 위 `from routers.<module> import (` 헤더가 소유자. 한 방에:
  ```
  grep -n "_share_load_active" app.py        # → rebind tuple 줄 (from routers._conv_store import ...)
  grep -rn "def _share_load_active" routers/  # → routers/_conv_store.py:2892 (소유 확정)
  ```
- **app 심볼의 전 소비처**(라우터 + 테스트가 어디서 이걸 쓰나):
  ```
  grep -rn "record_audit_event" routers/ ../tests/
  ```

---

## 3. 핵심 seam 치트시트

| 찾는 것 | 명령 / 위치 (src/ 에서) |
|---|---|
| **route 핸들러 위치** | [ROUTEMAP.md](./ROUTEMAP.md) `path→router:handler`, 또는 `grep -rn "/api/…경로리터럴…" routers/` |
| **app 심볼의 소유 파일** | app.py 꼬리 rebind: `grep -n "<심볼>" app.py` → `from routers.<module> import` 블록. 확정: `grep -rn "def <심볼>" routers/` |
| **심볼 소비처(전량)** | `grep -rn "<심볼>" routers/ ../tests/` |
| **라우터 등록 순서** | `grep -rn "INCLUDE_ORDER" routers/` → 값으로 정렬 = include 순서 (ROUTEMAP L0 와 동일) |
| **auth 검사 위치** | ROUTEMAP `auth`·`권한(RBAC)` 열 → 핸들러 시그니처 `Depends(...)` |
| **leaf helper** | `grep -n "def <심볼>" web_context.py` |
| **DI seam 정의** | `app.py`: `get_conn`(L1459)·`get_current_account`(L1492)·`require_permission`(L1523) |

---

## 4. 규약 요지 (7 conventions)

1. **app.X 동적참조** — 라우터/공유모듈은 `import app` 후 **호출 시점에 `app.X` 속성접근**. `from app import X` **금지**(값 스냅샷이 되어 monkeypatch·DI override 를 관통 못 함). 동적참조라야 테스트 setattr 와 Depends override 가 뚫린다.
2. **꼬리 rebind** — app.py 맨 끝(L3181~3722)에서 `from routers.X import _foo` 로 이동 심볼을 app 네임스페이스에 재부착. = **심볼 → 소유 라우터 역인덱스**이자, 기존 `app._foo` 호출부·테스트 참조 보존 seam.
3. **register_all + INCLUDE_ORDER** — `routers/__init__.register_all(app)` 이 non-언더스코어 · `router` 보유 모듈을 자동발견해 `(INCLUDE_ORDER, name)` 순으로 include. **신규 라우터 = `router` 심볼 파일 추가만**(app.py 꼬리 배선 편집 불필요, 병렬 경합 제거).
4. **DI seam (app 정본 잔류)** — `get_conn`(fail-soft `None` yield) · `get_current_account`(500/401) · `require_permission`(정적 perm AND 게이트, 무인자 호출은 import 시점 ValueError). 이 셋은 app.py 에 남고 라우터는 `app.X` 로 참조.
5. **web_context 단방향 추출** — app-internal 의존 0 인 leaf helper 만 `src/web_context.py` 로. **`from app import` 절대 금지**(app→web_context 단방향 edge, 순환 불가). app.py 가 다시 re-import 해 전역 rebind → 기존 호출부·monkeypatch 보존.
6. **keep-in-app 패치-단일점** — `record_audit_event`(setattr 12×) · `_connect_memory` · `_account_can_access_conversation` 는 **app.py 잔류**. 라우터는 `app.record_audit_event(...)` 로 부른다(패치 지점 1곳 유지).
7. **ITEM-11 DI 분기** — 실제 conn leak 핸들러 13개만 account+conn DI 로 전환, 나머지 37개는 keep-inline 정당(style/txn/특수). 인증 헬퍼 3형태: `_require_account`(DI 전환 가능) · `_get_authenticated_account`(conn-only DI, 세션 부수효과) · keep-inline 37(본문 인라인 검사 유지).

---

## 5. 불변식 — 건드리지 말 것

- **keep-in-app 4종은 app.py 에 남긴다**: `record_audit_event` · `_connect_memory` · `_account_can_access_conversation` · DI seam(`get_conn`/`get_current_account`/`require_permission`). 라우터로 옮기지 말 것 — 패치-단일점과 순환 안전이 깨진다. 라우터는 항상 `app.X` 로 호출한다.
- **route parity 205 골든**: 추출/이동이 라우트 *등록*을 바꾸면 `../tests/route_snapshot_p5b.json` 대조에서 `make test` 가 실패한다. 경로·메서드·핸들러 이름을 보존하라(byte-동치).
- **INCLUDE_ORDER 변경 금지**: 각 모듈의 `INCLUDE_ORDER` 상수는 2026-07-10 스냅샷 순서를 고정하는 guard. 값을 흔들면 include 순서(=미들웨어/라우트 우선순위)가 바뀐다. 신규 라우터는 **새 값**을 부여(기존 값 재배치 금지).
- **`from app import` 금지**: 반드시 `import app` + `app.X` 동적참조. `from web_context import` 는 leaf 에 한해 허용(단방향).
- 변경 후 항상 재생성 검사: `python3 bin/gen-routemap.py --check` (ROUTEMAP drift), 그리고 `make test`.

---

## 6. TASK 카드 (탐색→수정 캡슐)

한 작업 = 한 카드. 아래 6줄이 재귀 탐색을 한 화면에 압축한다(구체 카드 모음은 [CODE_TASKS.md](./CODE_TASKS.md) — 없으면 본 템플릿을 인라인 사용):
```
### TASK: <한 줄 제목>
- Match keywords : <도메인/기능 키워드>              # L0 진입
- Entry region   : routers/<file>.py:<handler>       # L1~L2, 바꿀 곳
- Reference regions : <함께 볼 file:심볼> …          # 인접 컨텍스트
- Recurse via    : grep -rn "<리터럴>" routers/ ../tests/   # L3 확장(리터럴 grep)
- Invariants     : route_snapshot 205 / INCLUDE_ORDER 고정 / keep-in-app / no `from app import`
- Verify         : python3 bin/gen-routemap.py --check && make test
```

---

## 7. 연결 문서

| 문서 | 계층 | 역할 |
|---|---|---|
| [ROUTEMAP.md](./ROUTEMAP.md) | **L0** | route→router:handler→auth→RBAC 인덱스(자동 생성, `bin/gen-routemap.py`) |
| **CODE_NAVIGATION.md** (본 문서) | **L1~L3** | 재귀 탐색·seam·불변식·TASK 카드 |
| [CODEBASE_MAP.md](./CODEBASE_MAP.md) | — | 리포 파일 구조·feature 경계 |
| [../unit/feature-0003-agent-web-ui/docs/FUNCTION.md](../unit/feature-0003-agent-web-ui/docs/FUNCTION.md) | — | 함수 카탈로그(사전) |
| [../unit/feature-0003-agent-web-ui/docs/MODIFY.md](../unit/feature-0003-agent-web-ui/docs/MODIFY.md) · [ANCHOR.md](../unit/feature-0003-agent-web-ui/docs/ANCHOR.md) | — | 변경 로그 · 위치 앵커 |
| `../unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json` | — | 205 route parity 골든(추출 회귀 gate) |

## 8. 프론트 static 계층 (admin.js · app.js · graph/ — ITEM-09, 2026-07-12)

백엔드(L0=ROUTEMAP)와 달리 프론트는 자동 인덱스가 없다 — 이 § 가 L0/L1 대체 진입면이다.
코드 루트: `unit/feature-0003-agent-web-ui/src/static/` (이하 grep 도 여기서, 리터럴만).

**Q. "그래프 뷰의 X 를 바꾸려면 어느 모듈?"** — 아래 표에서 직행. 함수 위치는 언제나
`grep -rn "function _metaXxx" graph/` 가 정본(모듈 헤더에 원 graph.js 라인 구간 명시).

| 모듈 | 역할(변경 유형 매칭) | 주요 심볼 |
|---|---|---|
| `graph/graph.js` | **barrel** — 공개 4심볼 re-export. admin.js 는 이 경로만 import. **경로·심볼 변경 금지** | `_metaShowGraph`·`_metaGraphLoadRoots`·`_metaRoleLegendTips`·`_metaGraph` |
| `graph/graph-state.js` | 그래프 상태·결정론적 배치 상수 | `_metaGraph`(전 모듈이 프로퍼티 변이)·`_MET*` 상수·`_metaNatSort` |
| `graph/graph-roleviz.js` | 테이블 역할 분류 시각 표식(칩·아이콘·범례) | `_META_ROLE`·`_metaRole*`·`_metaGraphZAssert` |
| `graph/graph-util.js` | 논블로킹 유틸(rAF 양보) | perf-bg 계열 |
| `graph/graph-rellayout.js` | 관계 기반 배치 pre-pass(barycenter) | rel-layout 계열 |
| `graph/graph-simgroups.js` | 유사 속성 그룹(affix family) | `_metaSim*` |
| `graph/graph-core.js` | init·데이터 로드·G6 build/apply·줌 LOD·anim·미니맵·검색 input 배선 | `_metaInitGraph`·`_metaG6Build/Apply`·`_metaShowGraph` |
| `graph/graph-ctxmenu.js` | 우클릭 상호작용·상세/관계 패널·**검색 엔진**(매칭·정렬·프루닝) | `_metaCtx`·`_metaGraphCtx*`·`_metaGraphShow*`·`_metaGraphSearch`·`_metaRelevance` |
| `graph/graph.css` | 그래프 전용 CSS(admin.html 만 link) | `.admin-meta-graph-*`·`.amg*` |

**규약(위반 = 런타임 파손)** — 상세·좌표 재적용은 [graph/MAPPING.md](../unit/feature-0003-agent-web-ui/src/static/graph/MAPPING.md) 가 정본:
1. 모듈 간/admin 순환 import = ES live-binding + 호출시점 사용 전제 — top-level 즉시실행에서 cross-module 심볼 호출 금지.
2. 상태는 전부 `const` 객체(프로퍼티 변이만) — cross-module 재할당(let) 불가.
3. `?v=` 는 소스에서 `?v=dev` 고정(HTML + ES import specifier) — 빌드가 content-hash 주입(§13.1). **수기 bump 금지**(이중 인스턴스화 유발).
4. G6/mermaid 는 UMD 전역 bridge(`const G6 = window.G6;`) — 필요 모듈 상단에 개별 선언.

**admin.js(4,831줄)** — 13 pane 도메인 동거. pane 경계 = admin.html `data-admin-pane` 속성이 자연 색인: `grep -n 'data-admin-pane' admin.html`. 공유 코어(`adminState`·`apiFetch`·`can`·`showToast`·pending 스테이징)는 상단 밴드. 전면 분할은 C-12 defer(충돌 실측 트리거). **pane → entry 함수 표**(블라인드 내비게이션 실측 2026-07-13 — "파일:함수" 확정까지 문서로 커버):

| pane (`data-admin-pane`) | entry 함수 (`grep -n "function <이름>" admin.js` 정본) |
|---|---|
| dashboard | `renderDashboard` · `loadDashboardOverview` |
| accounts / roles | `renderAccountList` · `renderRoleList` (로드 공통 `loadAdminData`) |
| products | `renderProductList` · `loadProductInsightCoverage` |
| datasources | `renderDatasourcesPane` |
| audits | `loadAuditList` · `renderAuditList` · `renderAuditDetail` |
| usage | `loadUsage` |
| archives | `loadArchivedConversations` · `renderArchiveList` |
| ai-ops | `loadAiOps` · `renderAiOps` |
| metadata | `loadMetadata` · `renderMetadataList` · `loadFeedbackQueue` |
| graph | `_metaShowGraph`(barrel — 위 표) · 스코프 드롭다운은 **admin.js** `_metaPopulateScopeSelect`(graph/ 아님 주의) |
| settings | `renderRuntimeTimeouts` · `renderModelThinkingBudgets` |

**app.js(8,562줄)** — 작업 화면(채팅·composer·첨부·공유·프로필). C-12 defer 동일. fetch 라인에서 엔클로징 함수 역산: `awk 'NR<=<라인>' app.js | grep -n "^function\|^async function" | tail -1`.
