---
doc_type: CODEBASE_MAP
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
---

<!-- freshness: feature-0012 완결(PR #736) + ITEM-09 static/graph 편입 · HEAD f7ad45d7 · 2026-07-13 -->

# Codebase Map

저장소의 파일 구조와 주요 진입점을 AI가 빠르게 참조할 수 있도록 요약한다.
기능 추가/삭제, 파일 구조 변경 시 갱신한다.

> **Freshness**: feature-0012 (web-router-modularization) 완결 반영 — `app.py` 19,650→3,722줄(-81%),
> 핸들러 전량이 `unit/feature-0003-agent-web-ui/src/routers/` 로 추출됨 — **35개 파일**(route-module 29 + `_` 접두 공유헬퍼 5 + `__init__` registrar, 2026-08-25 실측). (분할 완결 시점 HEAD `f7ad45d7`, 2026-07-13 = 당시 28개)

> **AI 탐색 진입점 (재귀 4계층)**: 바꾸려는 것이 route/handler 라면 아래 순서로 좁혀 내려간다.
> **L0 INDEX** → [`docs/ROUTEMAP.md`](ROUTEMAP.md) (method+path → **router 파일:handler** → auth → RBAC 권한; 자동 생성 정본, 200 route). ·
> **L1~L3 MODULE/SYMBOL/TRAVERSE** → `docs/CODE_NAVIGATION.md` (모듈 purpose·endpoints·imports·callees, handler signature, down=callees/up=callers grep). ·
> **TASK 카드** → `docs/CODE_TASKS.md` (Match keywords / Entry region / Reference regions / Recurse-via literal grep / Invariants / Verify).
> 이 CODEBASE_MAP 은 그 위의 L−1 (파일·1줄 책임·링크) 지도다 — route 표는 여기서 복제하지 않고 ROUTEMAP 으로 위임한다.

## 1. Directory Tree

```
repo/
├── AGENTS.md              # AI 운영 정책 정본
├── CONTRIBUTING.md         # 기여 및 커밋 규칙
├── CLAUDE.md               # AGENTS.md 참조 shim
├── MCP_DESIGN.md           # MCP 서비스 설계 참고 문서
├── README.md
├── Makefile                # 주요 빌드/실행 진입점
├── docker-compose.yml      # 서비스 오케스트레이션
├── .env / .env.example     # 런타임 환경변수
├── .aiignore               # AI 컨텍스트 제외 패턴
├── bin/                     # 저장소 수준 도구
│   └── gen-routemap.py     # ROUTEMAP.md 자동 생성기 (register_all INCLUDE_ORDER + @router 정적 스캔; `--check` drift 검사)
├── docs/                   # 프로젝트 수준 문서
│   ├── AGENTS.md(상위)·CONVENTIONS·DECISIONS·PROJECT·SECURITY·STATUS
│   ├── ARCHITECTURE.md
│   ├── LEARNINGS.md
│   ├── ROUTEMAP.md         # route → router:handler → auth 인덱스 (L0, 자동 생성)
│   └── CODEBASE_MAP.md     # 이 문서
├── playbooks/              # PB-0001 ~ PB-0006, PB-0008
├── shared/                 # 공통 모듈 패키지 (feature-0002·0003 공유, `ls shared/*.py` 실측 15): __init__·model_catalog·config·db·conn_health·datasources·runtime_settings·perf_counters·hangul_qwerty·llm_budget·llm_gate·resource_budget·share_window·bridge_tasks·attachment_write (feature-0011 추출 + 0018/0026 외 후속 feature 편입)
├── tests/integration/      # 통합 테스트
└── unit/                   # 기능 단위
    ├── _template/
    ├── feature-0001-platform-runtime/
    ├── feature-0002-agent-core/
    ├── feature-0003-agent-web-ui/
    │   └── src/
    │       ├── app.py           # 4,000줄 (feature-0012 P5b 완결 시점 3,722 · -81%) — DI seam·인증보조·audit·보안게이트·lifecycle·FastAPI app·config·rebind·register_all 만 잔류
    │       ├── web_context.py   # leaf helper (app-internal 의존 0인 순수 컨텍스트 조각, 단방향 추출)
    │       ├── routers/         # 도메인 APIRouter 패키지 — 35 파일 (§4a 참조)
    │       │   ├── __init__.py            # register_all(app): non-`_`·router 보유 모듈 자동발견 → (INCLUDE_ORDER,name)순 include
    │       │   ├── <29 route-module>.py   # 각 파일이 `router = APIRouter()` + `@router` 핸들러 보유 (도메인별)
    │       │   └── _<shared helper>.py    # _audit_infra·_bootstrap_schema·_conv_store·_folder_store·_prompt_context (register_all 제외)
    │       └── static/          # 프론트 자산 — ?v= 는 전부 `?v=dev` placeholder(빌드가 content-hash 주입, §13.1)
    │           ├── admin.js     # 관리 콘솔(4,831줄, type=module) — 13 pane 도메인. 그래프는 graph/ 로 분리
    │           ├── app.js       # 작업 화면(8,562줄) · css/ 7분할 · share.js/css · index/admin/share.html
    │           ├── app/        # 작업 화면 도메인 모듈(auth·profile·sidebar·messages·composer·progress
    │           │               #   + attach-diff = 첨부 버전 diff 비교 모달, 2026-08-06)
    │           ├── admin/      # 관리 콘솔 도메인 모듈 9
    │           ├── modal-dismiss.js  # 배경 dismiss 저장소 단일 primitive(양 ESM 번들 공유)
    │           └── graph/       # 그래프 뷰 ES 모듈 (ITEM-09 batch3, 2026-07-12) — CODE_NAVIGATION §8 참조
    │               ├── graph.js           # barrel — 공개 4심볼 re-export (admin.js 는 이 경로만 import)
    │               ├── graph-state.js     # `_metaGraph` 상태 + 배치 상수 · graph-roleviz.js(역할 표식)
    │               ├── graph-core.js      # init·load·G6 build/apply·LOD·anim (2,178줄)
    │               ├── graph-ctxmenu.js   # 우클릭·상세/관계 패널 (2,237줄) · graph-util/rellayout/simgroups.js
    │               ├── graph.css          # 그래프 전용 CSS (admin.html 만 link)
    │               └── MAPPING.md         # 좌표 재적용 체인(구 admin.js/graph.js 라인 → 모듈) + 경계 계약
    ├── feature-0004-browser-automation/
    ├── feature-0005-qa-mcp/
    ├── feature-0006-lan-proxy-access/
    ├── feature-0007-bedrock-llm-provider/
    ├── feature-0008-windows-browser-testing/
    ├── feature-0009-group-conversation/
    ├── feature-0010-google-drive-integration/
    ├── feature-0011-shared-extraction/
    ├── feature-0012-web-router-modularization/   # app.py → routers/ 분할 리팩터 (본 갱신의 출처)
    ├── feature-0013-relationship-diagrams/
    ├── feature-0014-zero-downtime-deploy/
    ├── feature-0015-zd-hygiene-backup/
    ├── feature-0016-metadata-graph/
    ├── feature-0016-zd-pg-pause-caddy/
    └── feature-0017-deploy-build-gate/
```

## 2. Key Entry Points

| File | Role | Notes |
|------|------|-------|
| `Makefile` | 실행/운영 진입점 | `make start`, `make stop`, `make status`, `make build`, `make web`, `make browser-up`, `make mcp-test` |
| `docker-compose.yml` | 서비스 오케스트레이션 | `mysql`, `postgres`(+replica·pgbouncer), `agent`, `memory-init`, `insight-worker`, `ask-worker`, `ops-scheduler`(정기 운영 잡 — feature-0039), `web-a`/`web-b`+`caddy`, `bedrock-gateway`, `minio`, `mcp`(선택) |
| `.env` | 런타임 환경변수 (정본) | 포트, 모델, DB 자격증명 — 원본 `mysql_ai`의 운영 의미를 보존 |
| `.env.example` | 예시 템플릿 | 민감값 제거된 샘플. 런타임은 읽지 않음 |
| `AGENTS.md` | AI 운영 정책 정본 | 섹션 §1~§17 + Part A~G 구조 |
| `MCP_DESIGN.md` | MCP 서비스 설계 | `feature-0005-qa-mcp`와 연동되는 설계 참고 |
| `README.md` | 사람용 개요 | 구조와 시작 절차 |
| `unit/feature-0003-agent-web-ui/src/app.py` | Web API 조립 루트 (FastAPI) | DI seam·인증·audit·lifecycle 만 잔류; route 핸들러는 `routers/` 로 이동 (§4a) |
| `docs/ROUTEMAP.md` | route 인덱스 (L0) | 어떤 route 가 어느 router 파일:handler 인지 — AI 탐색 첫 관문 |

## 3. Shared Module Index

`shared/` 는 feature-0002(agent-core)·feature-0003(web-ui)·격리 컨테이너가 공유하는 Python 패키지다
(feature-0011 P5a 점진 추출, Step 1~5 완료). 컨테이너는 Dockerfile `COPY shared /app/shared`, 테스트는
Makefile PYTHONPATH 의 `/work` 로 import. `from shared.<mod> import ...` 형식. **alias shim 없이 정본 단일 경로**
(추출 초기엔 `modules/X`=`shared.X` alias shim 으로 비파괴 추출했으나 Step 5 에서 소비처를 `shared.*` 로 마이그레이션 후 shim 전부 제거).

| Module | Purpose | Used By |
|--------|---------|---------|
| `shared/__init__.py` | 패키지 골격 | (패키지 마커) |
| `shared/model_catalog.py` | LLM 모델 카탈로그 (순수 stdlib) | feature-0002·0003 |
| `shared/config.py` | 설정·환경변수·플래그 (L0 foundation, fan-in 25; 16+ 모듈이 wildcard 재노출) | feature-0002·0003·컨테이너 |
| `shared/db.py` | DB 연결/풀/PG 라우팅 (repo 최다결합, fan-in 17; `_pg_connect`·`_POOL_REGISTRY` 등 underscore 심볼) | feature-0002·0003·컨테이너·healthcheck |
| `shared/perf_counters.py` | 요청-스코프 DB conn 카운터 (ContextVar, 컨텍스트 밖 no-op — feature-0026) | feature-0002·0003 (db 가 incr, web 미들웨어가 activate) |
| `shared/conn_health.py` | per-datasource 연결 health 모니터 (TCP liveness, circuit) | feature-0002·0003 (db·datasources 와 lazy 상호참조) |
| `shared/datasources.py` | datasource 레지스트리 (DB+`.env` 병합, 자격증명 복호) | feature-0002·0003 (cred_crypto back-dep — 아직 modules/) |
| `shared/attachment_write.py` | assistant 답변의 첨부 쓰기 블록(`attachment-edit`/`attachment-new`) 후처리 **단일 정본** — materialize → 도구 전달분 바인딩 → strip → 미전달 고지 → content 갱신. 저장 가드가 두 벌로 갈리는 것을 막는다 (feature-0043, 2026-08-28 · SECURITY §49) | feature-0002 (`modules/ask.py` ask-worker)·feature-0003 (`routers/conversations.py` 브리지 경로) |

> 아직 추출되지 않은 cross-feature 공통 후보(cred_crypto·memory·llm 등)는 feature-0002 `modules/` 에 잔존(후속 step). 신규 공용 모듈 추가는 PB-0002 참조.
> **web_context.py 는 shared/ 아님** — feature-0003 web 전용 leaf helper 다 (§4a). 여러 feature 가 아닌 web-ui 내부만 소비한다.

## 4. Feature File Index

| Feature | 역할 | 주요 소스 |
|---------|------|-----------|
| `feature-0001-platform-runtime` | 플랫폼 런타임/공통 자산 | (scaffold — `src/README.md`, `tests/README.md`) |
| `feature-0002-agent-core` | Agent 핵심 로직 | `src/agent_core.py` (라이브 진입점 = in-process tool-calling 루프), `src/modules/*` (config/llm/knowledge/sql_ops 등), `tests/test_llm_api.py` |
| `feature-0003-agent-web-ui` | Agent Web UI | `src/app.py` (4,000줄 조립 루트, 2026-08-25 실측) + `src/routers/*` (35 파일, 도메인별 APIRouter) + `src/web_context.py` (leaf helper). route 인덱스 → [`docs/ROUTEMAP.md`](ROUTEMAP.md). 상세 → §4a |
| `feature-0004-browser-automation` | 브라우저 자동화 | `src/app.py`, `src/ctl.py` |
| `feature-0005-qa-mcp` | QA 및 MCP 테스트 | `src/mcp_tests.py` |
| `feature-0006-lan-proxy-access` | LAN/프록시 접근 | (scaffold — `src/README.md`, `tests/README.md`) |
| `feature-0007-bedrock-llm-provider` | AWS Bedrock(Seoul `ap-northeast-2`) LLM provider 통합 — 사용자별 API Vault 폐기(ADR-0022) | litellm gateway 구성(`src/config/litellm_config.yaml`), `.env.bedrock` |
| `feature-0008-windows-browser-testing` | 실제 Windows 브라우저(CDP) 자동 구동 검증 워크플로 + Playwright MCP (PB-0008, 웹/UI 완료 게이트) | `bin/win-browser.py`, `bin/playwright-mcp.sh`, `.mcp.json` |
| `feature-0009-group-conversation` | 그룹 대화(멤버 roster·보관 이동·나가기·공유 참여 owner 게이트·kick/ban) — **cross-cut** | 코드 거주: feature-0002(`modules/group_members`)·feature-0003(`src/routers/conversations.py`) |
| `feature-0010-google-drive-integration` | 계정별 Google Drive 연동 토대(OAuth 토큰 암호화 + MCP seam) — 연동 미수행/비활성 scaffold | `src/gdrive_mcp_seam.py` (feature-0002 `modules/cred_crypto` 의존), web 노출 → `src/routers/integrations.py` |
| `feature-0011-shared-extraction` | 공통 모듈 `shared/` 점진 추출 리팩터(P5a Step 1~5 완료 — model_catalog·config·db·conn_health·datasources, 4 alias shim 제거) | `shared/*` + feature-0002·0003 import 재배선 (§3 참조) |
| `feature-0012-web-router-modularization` | **web `app.py` 모놀리스 → 도메인 APIRouter 분할** (P5b Final; app.py 19,650→3,722줄 -81%, 핸들러 전량 `routers/` 28 파일로 추출) | `unit/feature-0003-agent-web-ui/src/routers/*` + `web_context.py`, `docs/ROUTEMAP.md`, `bin/gen-routemap.py`. 상세 → §4a |
| `feature-0013-relationship-diagrams` | 관계 다이어그램 | (feature dir — `docs/`·`src/`) |
| `feature-0014-zero-downtime-deploy` | 무중단 배포 | (feature dir) |
| `feature-0015-zd-hygiene-backup` | 무중단 위생/백업 | (feature dir) |
| `feature-0016-metadata-graph` / `feature-0016-zd-pg-pause-caddy` | 메타데이터 그래프 · PG-pause/Caddy 무중단 | (feature dir 2개) |
| `feature-0017-deploy-build-gate` | 배포 빌드 게이트 | (feature dir) |
| `feature-0039-ops-scheduler` | **운영 정기 잡 인-컨테이너 스케줄러** — 백업·복원 리허설·AGE 그래프 sync 를 호스트 root crontab 에서 `ops-scheduler` 서비스로 이관(docker 소켓 의존 제거) | 코드 거주: feature-0002 `src/scripts/ops_scheduler.py`·`ops_backup.sh`·`ops_restore_rehearsal.sh`·`ops_graph_sync.sh`·`healthcheck_ops_scheduler.py` + repo-level `docker-compose.yml`(`ops-scheduler`)·`bin/{backup,restore-rehearsal,metadata-graph-sync}.sh`(수동 래퍼) |
| `_template` | 신규 feature 템플릿 | `docs/AGENTS.md`, `docs/TASK.md`, `docs/FUNCTION.md`, `docs/REPORT.md`, 등 |

각 feature는 `docs/`(AGENTS, FUNCTION, TASK, TEST, REPORT, MODIFY, REVIEW), `src/`, `tests/` 구조를 따른다.

## 4a. Web Router Topology (feature-0012)

feature-0012 는 `unit/feature-0003-agent-web-ui/src/app.py` 모놀리스(19,650줄)를 도메인 APIRouter 로 분할했다.
결과 계층은 **app.py (조립 루트) → routers/*.py (도메인) → web_context.py (leaf) → 공유 헬퍼**다.
route 단위 색인(method+path → handler → auth → RBAC)은 **[`docs/ROUTEMAP.md`](ROUTEMAP.md) 가 정본**이며 여기서 200행 표를 복제하지 않는다.

### 계층별 책임

| 계층 | 파일 | 책임 (1줄) |
|------|------|-----------|
| 조립 루트 | `src/app.py` (4,000줄, 2026-08-25 실측) | DI seam(`get_conn`/`get_current_account`/`require_permission`)·인증보조(`_AuthError`/`_auth_error_handler`/`_json_error`/`_require_account`)·audit(`record_audit_event`, setattr 패치-단일점)·보안게이트(`_ssrf_check_host`/`_enforce_audit_prod_gate`)·lifecycle(`@app.on_event` startup/shutdown)·FastAPI app+미들웨어·config 상수·꼬리 rebind 블록·`register_all(app)` |
| 도메인 router (29) | `src/routers/<domain>.py` | 각 파일이 `router = APIRouter()` + `@router.<method>` 핸들러 보유. 도메인 = static_pages·auth·conversations·share·system·profile·integrations·attachments·media·keywords·ai_ops + admin_*(console·usage·conversations·quotas·sample_feedback·metadata·audits·accounts·roles·datasources·products·settings·reasoning·perf — perf=HTTP 성능 스냅샷 조회(feature-0026)). 정확한 목록·INCLUDE_ORDER → ROUTEMAP.md |
| leaf helper | `src/web_context.py` (3,751줄, 2026-08-25 실측) | app-internal 의존이 전혀 없는 순수 컨텍스트 조립 조각. **단방향 추출**(app→web_context 만, 역참조 없음). routers(auth·share 등)와 app 이 소비 |
| 공유 헬퍼 (5, `_` 접두) | `src/routers/_audit_infra.py`·`_bootstrap_schema.py`·`_conv_store.py`·`_folder_store.py`·`_prompt_context.py` | 라우트 아님 → `register_all` 자동등록 제외(`_` 접두 필터). `_audit_infra`=감사 인프라(단, `record_audit_event` 는 app 잔류)·`_bootstrap_schema`=웹 테이블/시드 부트스트랩·`_conv_store`=대화 저장소(share/conversations 공유)·`_prompt_context`=프롬프트 컨텍스트 조립(admin_roles/admin_products/auth/conversations 4도메인 공유)·`_folder_store`=대화 폴더 PG 스토어(feature-0024) |
| 등록기 | `src/routers/__init__.py` | `register_all(app)` — non-`_`·`router` 보유 모듈 자동발견 후 `(INCLUDE_ORDER, name)` 순 include. 신규 라우터 = `router` 심볼 가진 파일 추가만(꼬리 배선 편집 불필요) |

> 파일 수 = 29 route-module + `__init__.py` + 5 `_` 접두 공유헬퍼 = **35 파일** (2026-08-25 실측) (task 표기 "6 공유모듈" = `__init__` + 5 underscore). feature-0026 이 `admin_perf.py`(INCLUDE_ORDER=250)와 leaf 계측 모듈 `src/perf_metrics.py`(HTTP 타이밍 집계·미들웨어)를 추가. feature-0014 가 leaf `src/static_cache.py`(정적 자산 캐시 무결성 — 빌드 스탬프 `static/.asset-stamp` 와 요청 `?v=` 가 일치할 때만 `immutable`, 불일치는 `no-store`; `app.py` 의 `/static` mount 를 감싸는 순수 ASGI 래퍼)를 추가. feature-0045 가 leaf `src/bridge_drain.py`(브리지 배포 연속성 — 개인 AI 의 대기·도구 호출을 **따로** 세는 in-flight 카운터 + lame-duck 드레인 미들웨어; 드레인 중 신규 도구 호출은 `503 X-Bridge-Draining` 으로 돌려보내되 제출·첨부 읽기는 받는다)를 추가하고, `routers/system.py` 에 배포 제어 창구 `/internal/bridge-{drain,activity,reclaim}`(loopback 전용)을 두었다.

### 배선 규약 (7)

1. **app.X 동적 참조** — 라우터/공유모듈은 `import app` 후 **호출 시점에 `app.X` 속성 접근**한다 (`from app import X` 금지). monkeypatch·DI override 가 관통된다.
2. **꼬리 rebind** — `app.py` 맨 끝(L3175 `register_all` 호출 직후 ~ L3722)에서 `from routers.X import _foo` 로 **이동된 심볼을 app 네임스페이스에 재부착**한다(67개 import 블록). = 심볼 → 소유 라우터 **역인덱스**로도 읽힌다.
3. **register_all + INCLUDE_ORDER** — 자동발견·정렬 include (위 등록기 참조).
4. **DI seam (app 정본 잔류)** — `get_conn`(fail-soft None yield), `get_current_account`(500/401), `require_permission`(정적 AND-게이트) 는 app 에 남는다.
5. **web_context 단방향 추출** — leaf helper 만 `web_context.py` 로 (§계층별 참조).
6. **keep-in-app 패치 단일점** — `record_audit_event`(setattr 12×), `_connect_memory`, `_account_can_access_conversation` 는 app 잔류.
7. **ITEM-11 DI-rework** — 실제 conn leak 핸들러 13개는 account+conn DI 로 전환, 나머지 37개는 keep-inline 정당(style/txn/특수).

### Navigation seams (AI 탐색 진입점)

- **route decorator grep** — `@router.<method>("<literal path>")` 경로 리터럴 grep 으로 handler 직행.
- **모듈 헤더 docstring** — 각 `routers/<domain>.py` 최상단 docstring 이 도메인+범위 선언.
- **`routers/__init__.py` INCLUDE_ORDER docstring** — 등록 순서·자동발견 규약.
- **`app.py` 꼬리 rebind 블록** — 심볼 → 소유 라우터 역인덱스.
- **문서** — [`docs/ROUTEMAP.md`](ROUTEMAP.md)(L0 route 인덱스), `feature-0003 docs/FUNCTION.md`(함수 카탈로그)·`MODIFY.md`(변경 로그)·`ANCHOR.md`.
- **골든** — `unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json`(205 route parity 스냅샷; 분할 전후 route 표 동치 검증).

## 5. External Interfaces

| Interface | Type | Used By |
|-----------|------|---------|
| MySQL 8.0 (container `mysql`) | 런타임 DB | agent, memory-init, insight-worker |
| LLM API (외부) | HTTPS | `feature-0002-agent-core` (`test_llm_api.py` 포함) |
| MCP 프로토콜 | IPC/stdio | `feature-0005-qa-mcp` |
| 브라우저 (로컬/헤드리스) | Automation | `feature-0004-browser-automation` |
| GitHub (원격) | git/HTTPS | `CONTRIBUTING.md` 의 PR 흐름 사용 |
| `../../artifacts/` | 런타임 산출물 | 모든 feature 실행 결과 — Git 외부 |

## 6. Automation Assets

자동화 워크플로 (`ai-*`, `policy-contract`, `selfhosted-runtime-smoke`, `owner-agent-report`) 와 `automation-contract.json` 은 2026-05-15 폐기되어 더 이상 사용하지 않는다. GitHub 흐름은 일반적인 PR 머지 (`gh pr create` + 사람 리뷰 + `gh pr merge`) 로 일원화한다.

**정기 운영 잡 (feature-0039)**: 백업(매일 03:00) · 복원 리허설(일 03:30) · AGE 그래프 sync(매 30분 증분 / 04:17 전량)는 호스트 crontab 이 아니라 `ops-scheduler` 컨테이너가 실행한다. 스케줄 정본은 `docker-compose.yml` 의 `OPS_SCHED_*` 환경변수이며, 잡 로직은 이미지 안 `/app/scripts/ops_*.sh` 다. `bin/{backup,restore-rehearsal,metadata-graph-sync}.sh` 는 수동 1회 실행용 래퍼로 남는다. `bin/install-*-cron.sh` 2종은 제거 전용(deprecated).

`bin/gen-routemap.py` 는 예외 — `routers/__init__.register_all` INCLUDE_ORDER + `@router` 데코레이터를 정적 스캔해 `docs/ROUTEMAP.md` 를 재생성한다(`--check` 로 drift 검사). route 추가/삭제·이동 후 재실행한다.

## 7. Known Gaps (미배선 설계 / 의도적 보류)

코드에 존재하나 라이브에 **가동되지 않는** 설계 — 후속 결정/배선 대상. 추출·리팩터 시 dedup-merge 하지 말고 보존한다.

| Gap | 위치 | 상태 | 비고 |
|-----|------|------|------|
| **GDPR legal-erasure (#4)** | feature-0002 `src/modules/attachment_reconciliation.py` (TASK-0094 D6 4-state + legal pseudonym, Phase 10 의존) | **미배선(unwired)** | 라이브 web(feature-0003)판 reconciliation 에는 legal-erasure 경로가 가동되지 않는다. 코드 보존(삭제·병합 금지). wiring 은 **별도 compliance 결정** 사항. (feature-0011 ANCHOR §3 동반 메모 출처) |
