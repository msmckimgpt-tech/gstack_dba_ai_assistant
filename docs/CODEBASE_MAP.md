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
> 핸들러 전량이 `unit/feature-0003-agent-web-ui/src/routers/` 로 추출됨 — **41개 파일**(route-module 30 + `_` 접두 공유헬퍼 10 + `__init__` registrar, 2026-09-10 실측). (분할 완결 시점 HEAD `f7ad45d7`, 2026-07-13 = 당시 28개)

> **AI 탐색 진입점 (재귀 4계층)**: 바꾸려는 것이 route/handler 라면 아래 순서로 좁혀 내려간다.
> **L0 INDEX** → [`docs/ROUTEMAP.md`](ROUTEMAP.md) (method+path → **router 파일:handler** → auth → RBAC 권한; 자동 생성 정본, 270 route). ·
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
├── shared/                 # 공통 모듈 패키지 (feature-0002·0003 공유, `ls shared/*.py` 실측 20): __init__·model_catalog·config·db·conn_health·datasources·runtime_settings·perf_counters·hangul_qwerty·llm_budget·llm_gate·resource_budget·share_window·bridge_tasks·attachment_write·self_review·bridge_consent·bridge_caps·dqa_identity·attachment_path (뒤 5종 2026-09-01~09-08 신설) (feature-0011 추출 + 0018/0026 외 후속 feature 편입)
├── tests/integration/      # 통합 테스트
└── unit/                   # 기능 단위
    ├── _template/
    ├── feature-0001-platform-runtime/
    ├── feature-0002-agent-core/
    ├── feature-0003-agent-web-ui/
    │   └── src/
    │       ├── app.py           # 4,000줄 (feature-0012 P5b 완결 시점 3,722 · -81%) — DI seam·인증보조·audit·보안게이트·lifecycle·FastAPI app·config·rebind·register_all 만 잔류
    │       ├── ui_release.py    # 완료 metadata 검증; /api/ui-release → static/ui-refresh.js → app/deploy-refresh.js
    │       ├── web_context.py   # leaf helper (app-internal 의존 0인 순수 컨텍스트 조각, 단방향 추출)
    │       ├── routers/         # 도메인 APIRouter 패키지 — 41 파일 (§4a 참조)
    │       │   ├── __init__.py            # register_all(app): non-`_`·router 보유 모듈 자동발견 → (INCLUDE_ORDER,name)순 include
    │       │   ├── <30 route-module>.py   # 각 파일이 `router = APIRouter()` + `@router` 핸들러 보유 (도메인별)
    │       │   └── _<shared helper>.py    # _attachment_diff·_audit_infra·_bootstrap_schema·_connect_funnel·_connect_steps·_console_jobs·_console_llm·_conv_store·_folder_store·_prompt_context (register_all 제외)
    │       └── static/          # 프론트 자산 — ?v= 는 전부 `?v=dev` placeholder(빌드가 content-hash 주입, §13.1)
    │           ├── admin.js     # 관리 콘솔(4,943줄, type=module) — 13 pane 도메인. 그래프는 graph/ 로 분리
    │           ├── app.js       # 작업 화면(9,085줄) · css/ 8분할 · share.js/css · share-client-context.js · index/admin/share.html
    │           ├── app/        # 작업 화면 도메인 모듈(auth·profile·sidebar·messages·composer·progress·connect-modal·next-target·conv-status
    │           │               #   + attach-diff = 첨부 버전 diff 비교 모달, 2026-08-06
    │           │               #   + side-panels = 우측 오버레이 패널 단독 열림 등록부, 2026-09-01
    │           │               #   + client-bridge = DQA 클라이언트 로컬 브리지의 웹측 짝(feature-0046))
    │           ├── admin/      # 관리 콘솔 도메인 모듈 12
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
| `shared/attachment_write.py` | assistant 답변의 첨부 쓰기 블록(`attachment-edit`/`attachment-new`) 후처리 **단일 정본** — materialize → 도구 전달분 바인딩 → strip → 미전달 고지 → content 갱신. 저장 가드가 두 벌로 갈리는 것을 막는다 (feature-0043, 2026-08-28 · SECURITY §49) | feature-0002 (`modules/ask.py` ask-worker)·feature-0003 (`routers/conversations.py` inproc 및 `routers/ai_tools.py` 브리지 경로) |
| `shared/attachment_path.py` | 폴더 첨부의 **상대 경로 정규화 + 디렉토리 트리 렌더 단일 정본** — 브라우저가 보내는 `webkitRelativePath` 는 사용자 입력이므로 traversal(`..`)·절대경로·드라이브 접두·제어문자를 제거하고 깊이 32·길이 1024·세그먼트 255 상한을 건 뒤(`normalize_relative_path`) 저장하며, 위험하면 **거절이 아니라 폴더 정보 폐기(None)** — 파일 자체는 올라간다. 사람 표시와 LLM 프롬프트의 `## DIRECTORY STRUCTURE OF ATTACHED FOLDERS` 블록이 **같은 함수**(`render_directory_tree`)로 트리를 그린다 (feature-0003 · REQ-20260908-attach-folder-tree, 2026-09-08) | feature-0003 (업로드·목록 경로)·feature-0002 (`_build_attachment_context_section` 프롬프트 블록) |
| `shared/runtime_settings.py` | 관리 콘솔 `시스템 > 설정` 런타임 설정 레지스트리 + resolver + 프로세스 간 전파 스냅샷 (feature-0018) | feature-0002·0003 |
| `shared/llm_budget.py` | 백그라운드 LLM 토큰 예산 — rolling 집계·게이트 (feature-0032) | feature-0002·0003 |
| `shared/llm_gate.py` | 서버 보유 계정 LLM 호출 **fail-closed 게이트 단일 정본** (feature-0043 · SECURITY §49) | feature-0002 (`modules/llm`·`agent_core`)·feature-0003 |
| `shared/bridge_tasks.py` | 웹 브리지 대기 작업(`WebAiTasks`) **상태 술어 단일 정본** — 집을 수 있는가/취소됐는가. **+ 콘솔·배경 작업 카탈로그와 위임 판정 정본으로 확장(2026-09-02)** — `JOB_SPECS`·`console_job_perms`·`visible_console_job_kinds`·`normalize_console_job_prefs`·`pick_console_job_model`·`resolve_console_job_request`·`runner_capabilities_for_session` 를 여기 두어 적재 게이트·대기 목록 필터·claim 최종 방어 **세 겹이 같은 술어**를 쓰게 한다 (feature-0043, 2026-08-28 → 2026-09-02) | feature-0003 (`routers/ai_tools.py`·`routers/conversations.py`·`routers/profile.py`·`routers/ai_ops.py`·`routers/admin_console.py`·`routers/_console_jobs.py`·`routers/_console_llm.py`·`src/oauth_store.py`) |
| `shared/resource_budget.py` | 공유 자원 예산·격리 + 워커 자원 계측 (feature-0025 T0) | feature-0002 워커 루프 |
| `shared/share_window.py` | 공유(그룹) 대화 첨부 참조 스코프 **판정 정본** — 그룹 여부 + 공유창 window 게이트 (feature-0009 · SECURITY §47) | feature-0002 (`agent_core`)·feature-0003 |
| `shared/hangul_qwerty.py` | 한글 ↔ QWERTY 자판 상호 변환 **서버측 정본** (프론트 정본 `static/hangul-qwerty.js` 와 매핑표 동치 · 회귀 잠금 테스트 2종) | feature-0002·0003 (SQL LIKE 검색 경로) |
| `shared/self_review.py` | 외부 AI **자가 검증(5축) 계약 정본** — 축·심각도·출력 형식은 서버가 정해 `claim_request` 응답에 지시문 전문으로 실어 보낸다(러너에 박으면 축 하나 고칠 때마다 전 사용자가 재설치해야 하고, 낡은 러너가 같은 컬럼에 다른 의미를 쓴다) (feature-0043, 2026-09-01) | feature-0003 (`routers/ai_tools.py`·`routers/ai_ops.py`) |
| `shared/bridge_consent.py` | **배경 배치 동의**(인사이트 요약·클러스터 라벨) 단일 정본 — 러너 CLI 플래그 `--batch` 였던 동의를 계정 단위 웹 토글로 옮기고 하트비트 응답으로 러너 `features` 신고에 반영 (feature-0043, 2026-09-01) | feature-0003 (`routers/ai_tools.py`·`routers/oauth_as.py`) |
| `shared/bridge_caps.py` | 러너 **능력 신고의 리비전 지문 + 계정·런타임별 baseline 원장** 순수 정본 — 「목록이 바뀌었는가」를 값 하나로 판정한다(문구 파싱·전체 비교는 서버·프런트 두 벌 판정이 되고 갈리는 순간 느슨한 쪽이 진실이 된다). DB 접근·JSON 컬럼 I/O 는 두지 않는다(`oauth_store` 소유 — `bridge_tasks` 와 같은 규율) (feature-0043, 2026-09-02) | feature-0003 (`routers/ai_tools.py`·`routers/oauth_as.py`·`src/oauth_store.py`) |
| `shared/dqa_identity.py` | 개인 머신 클라이언트 **명칭 단일 정본** — `APP_NAME`(설치·패키징 층의 제품명) · `DISPLAY_NAME`(창·트레이·대화상자에 뜨는 이름 = «DQA», 사용자 결정 2026-09-04 — 보이는 이름만 바꿔 기존 설치본 업그레이드 경로를 가르지 않는다) · `SCHEME`(URL 스킴 = 머신 전역 네임스페이스 = 레지스트리 키) · `APP_ID`(역-DNS) 4축 + `MCP_SERVER_KEY` + 딥링크 조립 `scheme_url()`. 문자열만 갖고 import 부작용이 없다(러너·설치 스크립트는 stdlib-only 계약이라 import 대신 `feature-0043/tests/test_name_ssot.py` 가 대조). 옛 이름 `mysql-ai-bridge` 는 `LEGACY_*` 로 정리 대상만 고정 (feature-0043, 2026-09-03) | feature-0003 (`routers/oauth_as.py`·`routers/ai_tools.py`)·feature-0046 클라이언트·러너/설치 스크립트(대조) |

> 아직 추출되지 않은 cross-feature 공통 후보(cred_crypto·memory·llm 등)는 feature-0002 `modules/` 에 잔존(후속 step). 신규 공용 모듈 추가는 PB-0002 참조.
> **web_context.py 는 shared/ 아님** — feature-0003 web 전용 leaf helper 다 (§4a). 여러 feature 가 아닌 web-ui 내부만 소비한다.

## 4. Feature File Index

| Feature | 역할 | 주요 소스 |
|---------|------|-----------|
| `feature-0001-platform-runtime` | 플랫폼 런타임/공통 자산 | (scaffold — `src/README.md`, `tests/README.md`) |
| `feature-0002-agent-core` | Agent 핵심 로직 | `src/agent_core.py` (라이브 진입점 = in-process tool-calling 루프), `src/modules/*` (config/llm/knowledge/sql_ops 등), `tests/test_llm_api.py` |
| `feature-0003-agent-web-ui` | Agent Web UI | `src/app.py` (4,000줄 조립 루트, 2026-08-25 실측) + `src/routers/*` (41 파일, 도메인별 APIRouter) + `src/web_context.py` (leaf helper). route 인덱스 → [`docs/ROUTEMAP.md`](ROUTEMAP.md). 상세 → §4a |
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
| `feature-0043-external-llm-bridge` | **서버 계정 LLM 차단 + 웹 대화 pull 브리지** — 추론 주체를 개인 머신 AI 로 반전 | `src/agent/`(**러너 정본 21 모듈** — 2026-09-02 분할 18 + 자기 갱신 `selfupdate.py` 1 + 대화 세션 `sessions.py` 1 + `__init__.py` 1 (`ls src/agent/*.py` 실측 2026-09-09; 정본 FUNCTION.md §「18 모듈」은 `__init__`·`selfupdate` 제외 표기), `__init__.py` 의 `_EMIT_ORDER` 가 번들 순서 정본) · `src/bridge_runner.py`(표준 라이브러리 전용 수동 보조 러너) · `src/bridge_setup.sh`/`src/bridge_setup.ps1`(결정론적 원클릭 진입점, 2026-08-28 신설) · 빌드 `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py`(패키지→단일 파일; 배포본 `src/bridge_agent.py`·`feature-0003/src/static/agent/*` 는 **생성물이라 커밋 대상 아님**) + 코드 거주: `shared/llm_gate.py`·`shared/bridge_tasks.py`·feature-0003 `routers/ai_tools.py` |
| `feature-0046-native-client` | **Windows 네이티브 클라이언트** — 터미널 없이 자기 AI 를 연결(설치 마법사 + 런타임 동봉 · 로그인 대행) | `src/dqa_connect.py`(진입점 — 패키지 밖·절대 임포트: PyInstaller 가 진입 파일을 `__package__` 없는 최상위 스크립트로 돌린다) · `src/client/branding.py`(AppUserModelID·창/고정 아이콘의 안정 재실행 경로·투명 `assets/dqa.svg` 정본에서 PNG/ICO 생성) · `src/client/core.py`(감지·로그인 대행·무결성 대조·러너 기동, GUI 무의존) · `src/client/discovery.py`(**AI 플랫폼별 탐색·연결 상태 원장** — 위치 재사용, 실행 권한이 없는 위치는 사유와 함께 목록에 남기고 자동 연결에서 제외, 2026-09-08) · `src/client/supervisor.py`(**소유한 자식 프로세스 감독** — 출력 배수·종료 감지·유한 재시도. `core.spawn_runner` 가 생성하고 `bridge.py`/`gui.py` 가 제어한다, 2026-09-08) · `src/client/gui.py`(tkinter 껍데기 — `print()` 금지, `tell()` messagebox; [X]=트레이로 숨김·연결 단일 실행 게이트·선택은 GUI 스레드에서 확정) · `src/client/tray.py`(**알림 영역 상주** — stdlib `ctypes`+`Shell_NotifyIconW`, 순수 로직 `Tray` / Win32 `Win32Backend` 2층. 서드파티 0, 아이콘은 `ExtractIconW` 로 exe 내부 것 사용. 실 Windows 검증은 `tests/windows/`) · `src/client/window.py`(**WebView2 내장 앱 창** — 2026-09-04 부터 기본 껍데기. `webview.start()` 가 주 스레드를 점유하므로 브리지·트레이·폴링은 워커 스레드) · `src/client/appwindow.py`(브라우저 앱 모드 `--app=` 폴백 — Windows 가 기록한 https 기본 핸들러에서 실행 파일을 읽어 로그인 세션을 따라간다) · `src/client/bridge.py`(**서비스 페이지가 부르는 로컬 브리지** — `127.0.0.1` 임의 포트 · 실행마다 새 nonce · origin 고정 · 프로세스를 띄우는 동작은 네이티브 확인창. 웹측 짝은 feature-0003 `static/app/client-bridge.js`) · `src/scripts/build_client.py`(PyInstaller `--onedir --windowed` + 임베더블 CPython 동봉 + `verify_runtime_runs_runner()`) · `src/installer/DQAConnect.iss`(Inno Setup per-user · 시작메뉴 · 제거 · `dqa-connect://` 스킴 등록 · **버전은 `/DAppVersion=` 으로 주입** · `/RELAUNCH` 무음 재기동) · **`src/client/version.py`**(배포 버전 **정본** `CLIENT_VERSION` + 수치 비교 — 문자열 비교면 `1.10.0 < 1.9.0` 이 되어 열 번째 릴리스가 낡은 것으로 읽힌다) · **`src/client/updater.py`**(업데이트 수신 — 고정 경로 + TOFU 고정 서버 + 사내 CA, 크기·sha256·ZIP·상한 검사, 확인 후 앱 내부 적용. 러너 `feature-0043/src/agent/selfupdate.py` 규율 이식) · **`src/scripts/publish_release.py`**(빌드 산출물을 호스트 `artifacts/client-release/` 로 반입 · `--activate` 롤백 · `--prune` 정리 · `--check` 는 **서버 모듈을 그대로 불러** 재확인) + 명칭 정본 `shared/dqa_identity.py` |
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
| 도메인 router (30) | `src/routers/<domain>.py` | 각 파일이 `router = APIRouter()` + `@router.<method>` 핸들러 보유. 도메인 = static_pages·auth·conversations·share·system·profile·integrations·attachments·media·keywords·ai_ops + admin_*(console·usage·conversations·quotas·sample_feedback·metadata·audits·accounts·roles·datasources·products·settings·reasoning·perf — perf=HTTP 성능 스냅샷 조회(feature-0026)). 정확한 목록·INCLUDE_ORDER → ROUTEMAP.md |
| leaf helper | `src/web_context.py` (3,751줄, 2026-08-25 실측) | app-internal 의존이 전혀 없는 순수 컨텍스트 조립 조각. **단방향 추출**(app→web_context 만, 역참조 없음). routers(auth·share 등)와 app 이 소비 |
| 공유 헬퍼 (10, `_` 접두) | `src/routers/_attachment_diff.py`·`_audit_infra.py`·`_bootstrap_schema.py`·`_connect_funnel.py`·`_connect_steps.py`·`_console_jobs.py`·`_console_llm.py`·`_conv_store.py`·`_folder_store.py`·`_prompt_context.py` | 라우트 아님 → `register_all` 자동등록 제외(`_` 접두 필터). `_audit_infra`=감사 인프라(단, `record_audit_event` 는 app 잔류)·`_bootstrap_schema`=웹 테이블/시드 부트스트랩·`_conv_store`=대화 저장소(share/conversations 공유)·`_prompt_context`=프롬프트 컨텍스트 조립(admin_roles/admin_products/auth/conversations 4도메인 공유)·`_folder_store`=대화 폴더 PG 스토어(feature-0024)·`_console_jobs`=콘솔 작업 프롬프트 조립 + 개인 AI 산출물의 기존 저장경로 반영(feature-0043)·`_console_llm`=관리 콘솔 LLM 상태 판정 단일 정본(feature-0043) |
| 등록기 | `src/routers/__init__.py` | `register_all(app)` — non-`_`·`router` 보유 모듈 자동발견 후 `(INCLUDE_ORDER, name)` 순 include. 신규 라우터 = `router` 심볼 가진 파일 추가만(꼬리 배선 편집 불필요) |

> 파일 수 = 30 route-module + `__init__.py` + 10 `_` 접두 공유헬퍼 = **41 파일** (2026-09-10 실측) (task 표기 "8 공유모듈" 은 underscore 7 시점 값 — 현재는 `__init__` + 10 underscore = 11). feature-0026 이 `admin_perf.py`(INCLUDE_ORDER=250)와 leaf 계측 모듈 `src/perf_metrics.py`(HTTP 타이밍 집계·미들웨어)를 추가. feature-0014 가 leaf `src/static_cache.py`(정적 자산 캐시 무결성 — 빌드 스탬프 `static/.asset-stamp` 와 요청 `?v=` 가 일치할 때만 `immutable`, 불일치는 `no-store`; `app.py` 의 `/static` mount 를 감싸는 순수 ASGI 래퍼)를 추가. feature-0045 가 leaf `src/bridge_drain.py`(브리지 배포 연속성 — 개인 AI 의 대기·도구 호출을 **따로** 세는 in-flight 카운터 + lame-duck 드레인 미들웨어; 드레인 중 신규 도구 호출은 `503 X-Bridge-Draining` 으로 돌려보내되 제출·첨부 읽기는 받는다)를 추가하고, `routers/system.py` 에 배포 제어 창구 `/internal/bridge-{drain,activity,reclaim}`(loopback 전용)을 두었다.

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


## 러너 갱신·감독 진입점 (2026-09-08)

- `unit/feature-0043-external-llm-bridge/src/agent/selfupdate.py::install_agent_file`: 같은 디렉터리 원자 교체 및 sidecar 락. `events.py::_read_running_source`, `lifecycle.py::try_self_update`: 실행 세대와 재기동.
- `unit/feature-0046-native-client/src/client/supervisor.py::RunnerSupervisor`: 소유한 자식의 출력 배수·종료 감지·유한 재시도. `core.py::spawn_runner`에서 생성하고 `bridge.py`/`gui.py`가 제어한다.
- `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py`: 단일 파일 및 실행 소스 SHA-256 스탬프 생성.
- 회귀: feature-0043 `tests/test_runner_update_processes.py`, feature-0046 `tests/test_runner_supervisor.py`, Windows `tests/windows/verify_runner_recovery.py`.

## 외부 AI 도구 catalog (2026-09-08)

외부 도구 계약은 `unit/feature-0003-agent-web-ui/src/external_tool_catalog.py`의 build_catalog/render_guidance가 소유한다. routers/ai_tools.py의 명시적 allowlist와 core Schema를 합쳐 HTTP/MCP/러너에 현재 목록을 전달한다.


배포의 Caddy 관측 경로: `bin/lib/caddy-probe.sh` → Docker archive 파일 조회 / 현재 이미지·network namespace의 격리 init probe. `bin/deploy-web.sh`의 TLS 사전 점검·edge gate·reconcile에서 소비한다.

통합 경계(2026-09-09): replica TLS 확인은 PR #1656의 `bin/deploy-web.sh:edge_peer_live`가 호스트 nsenter/dig/curl로 실제 DNS·CA·SNI를 확인한다. `caddy_probe`의 격리 init 컨테이너는 admin HTTP GET에 사용한다.

## 클라이언트 앱 내부 갱신 (2026-09-10)

- `unit/feature-0046-native-client/src/client/update_package.py::{extract_payload,apply_package}`: Windows 경로·압축 제한, 설치기와 공통 mutex, 새 슬롯 실행 검사 후 포인터 활성화. 현재 앱/러너는 계속 실행한다.
- `unit/feature-0046-native-client/src/client/installation.py`: 활성/준비된 버전 판정과 이전 슬롯 진입 전달.
- `unit/feature-0046-native-client/src/scripts/build_client.py::build_update_package`: 최초 설치 Setup과 같은 완성 앱의 Update ZIP 생성.
- `unit/feature-0046-native-client/src/scripts/publish_release.py::{publish,activate,prune}`: 채널 잠금, 불변 파일, Setup/ZIP 동반 게시·철회·정리.
- `unit/feature-0003-agent-web-ui/src/routers/client_release.py::{current_release,client_download}`: 검증된 현재 채널의 Setup과 ZIP만 서빙.
