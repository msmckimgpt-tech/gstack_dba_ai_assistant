---
doc_type: MODIFY
feature_id: feature-0011-shared-extraction
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260624-0001
- Date: 2026-06-24
- Related Requirement: REQ-001, REQ-002, REQ-003 (P5a Step 1 — shared/ 플러밍 + model_catalog 첫 추출)
- Summary: repo 루트 `shared/` 를 Python 패키지로 확립하고, 저결합 공통 모듈 `model_catalog`
  을 `modules/` → `shared/` 로 이동(history 보존). 두 feature(agent-core·web)와 격리 테스트
  컨테이너가 `from shared.model_catalog` 로 import 하도록 import 사이트·Dockerfile·Makefile 배선.
  db.py 같은 고결합 모듈을 옮기기 전에 저위험 모듈로 플러밍을 test-gated 로 증명하는 안전 sequencing.
- Files (cross-feature changeset — feature-0011 cycle 가 0002/0003/루트를 편집):
  - `shared/__init__.py` (신규 — 패키지 골격)
  - `shared/model_catalog.py` (← `unit/feature-0002-agent-core/src/modules/model_catalog.py`, git mv)
  - `unit/feature-0002-agent-core/src/agent_core.py` (import: modules→shared)
  - `unit/feature-0002-agent-core/src/modules/llm.py` (상대 import `from .model_catalog`→`from shared.model_catalog`)
  - `unit/feature-0002-agent-core/tests/test_prompt_gen_max_tokens.py` (import: modules→shared)
  - `unit/feature-0003-agent-web-ui/src/app.py` (import: modules→shared)
  - `unit/feature-0002-agent-core/src/Dockerfile` (`COPY shared /app/shared`)
  - `Makefile` (test/eval/kb-retrieval-eval PYTHONPATH 에 `/work` 추가 — shared 의 부모)
- Impact: 런타임 동작 불변(동일 심볼·동일 함수). import 경로만 변경. 컨테이너(/app)·테스트(/work)
  양쪽에서 해석 검증. `make test` 회귀 0(기존 baseline 실패 2건 test_product_delete_block_conv
  은 본 변경 무관·main 165906b 에서도 동일 실패).
- Rollback Notes: 단일 commit revert 로 model_catalog 가 modules/ 로 복귀. 이미지 재빌드만 필요
  (스키마/데이터 변경 없음). 라이브 web-1 은 재배포 전까지 무영향.

## CHG-20260624-0002
- Date: 2026-06-24
- Related Requirement: P5a Step 2 — config 추출 (순서 재설계: /plan-eng-review decision 5cc24689,
  config-first 위상정렬. config 는 L0 foundation: 내부의존 0·fan-in 25, db 의 `from .config import *` 강결합 선행 해소).
- Summary: 정본 `modules/config.py`(1187줄)를 `shared/config.py` 로 이동(git mv, history 보존)하고,
  `modules/config.py` 를 **모듈 alias shim** 으로 교체 — `sys.modules[__name__] = shared.config` 로
  `modules.config` 와 `shared.config` 를 *동일 객체* 화. 사이트 재배선 0(모든 import 형태가 alias 로 자동 보존).
  **설계 전환 기록**: 처음엔 `from shared.config import *` + 명시 re-export(__all__ 밖 public 9 + underscore 8)
  shim 을 썼으나, config 의 **annotated assignment** 심볼(`_ACTIVE_DEFAULT_DB: ContextVar`)을 enumeration 이
  놓쳐 `test_mssql_security_boundary` 10건 회귀 발생 → 271+ 심볼·monkeypatch 를 완전 보존하는 alias 로 전환.
- Files (cross-feature changeset):
  - `shared/config.py` (← `unit/feature-0002-agent-core/src/modules/config.py`, git mv)
  - `unit/feature-0002-agent-core/src/modules/config.py` (alias shim 신규 본문)
- Impact: 런타임 동작 불변(alias = 동일 객체). 16개 wildcard importer·다수 모듈객체 접근(`cfg.X`)·
  monkeypatch·db 경유 재노출 체인(`from modules.db import AGENT_KB_PG_PORT`) 전부 보존. `make test` 회귀 0
  (baseline 2건만). /app alias 완전성 smoke PASS(`modules.config is shared.config`, annotated 심볼 접근, db 체인).
- Rollback Notes: 단일 commit revert 로 config 가 modules/ 로 복귀. 이미지 재빌드만(스키마/데이터 무변경).

## CHG-20260624-0003
- Date: 2026-06-24
- Related Requirement: P5a Step 3 — db 추출 (config-first 위상정렬상 L1; config(Step 2) 이동으로
  db 의 `from .config import *` 강결합이 shared/config 로 해소됨).
- Summary: 정본 `modules/db.py`(967줄, repo 최다결합 모듈)를 `shared/db.py` 로 git mv 하고,
  `modules/db.py` 를 **모듈 alias shim**(`sys.modules[__name__] = shared.db`)으로 교체 — config 와
  동일 패턴. db 의 모듈객체 접근(`from . import db as _db`)·underscore 심볼(`_pg_connect` 등 9+)·
  AnnAssign(`_POOL_REGISTRY`)·__all__(15)·`from .db import *`·monkeypatch·config 재노출 체인을 동일
  객체로 완전 보존. 사이트 재배선 0.
- lazy back-dep 처리: shared/db.py 의 `from .config import *`(line 21)는 shared.config 로 해석(무변경).
  단 lazy `from . import datasources`(116)·`from . import conn_health`(402)는 두 모듈이 아직 modules/
  라 `from modules import ...` 로 재배선(전이적 back-dep, 함수내부 lazy 라 import-time cycle 없음).
  db↔conn_health 상호 lazy 참조는 alias 로 db 단일객체 유지. Step 4 에서 두 모듈 이동 시 `from shared import` 로 정리.
- Files (cross-feature changeset):
  - `shared/db.py` (← `unit/feature-0002-agent-core/src/modules/db.py`, git mv + lazy back-dep 2줄 재배선)
  - `unit/feature-0002-agent-core/src/modules/db.py` (alias shim 신규 본문)
- Impact: 런타임 동작 불변(alias = 동일 객체). fan-in 17(내부 14+외부 3) 전부 보존. `make test` 회귀 0
  (baseline 2건만, db-heavy 테스트 conn_health·multi_datasource·controlplane_timeout pass). /app db alias
  완전성 smoke PASS(modules.db is shared.db, _POOL_REGISTRY·_pg_* 접근, AGENT_KB_PG_PORT 재노출, conn_health/datasources import).
  committed-tree import 실증(modules/db.py shim + shared/db.py 둘 다 tree 에 — Step 2 untracked-shim BLOCKING 선제 차단).
- Rollback Notes: 단일 commit revert 로 db 가 modules/ 로 복귀. 이미지 재빌드만(스키마/데이터 무변경).

## CHG-20260625-0004
- Date: 2026-06-25
- Related Requirement: P5a Step 4 — L1 cross-feature 공통 모듈 conn_health·datasources 추출 +
  db 의 lazy back-dep `from modules import` → `from shared import` 정리 (TASK-0011-8).
- Summary: 정본 `modules/conn_health.py`(474줄)·`modules/datasources.py`(282줄)를 `shared/` 로
  git mv(history 보존)하고, 두 `modules/` 경로를 **모듈 alias shim**(`sys.modules[__name__] = shared.X`)
  으로 교체 — config·db(Step 2/3)와 동일 패턴. 사이트 재배선 0(`from modules import …`·`from . import …`·
  `import modules.X`·`importlib.import_module("modules.X")` 모든 형태가 alias 로 자동 보존). conn_health 의
  백그라운드 모니터 상태(`_STATE`/`_MONITOR`)·datasources 의 `_DEK_CACHE`/`_CONFLICT_WARNED` 단일 인스턴스 보존.
- back-dep 정리(Step 4 핵심 과업):
  - `shared/db.py` 의 lazy `from modules import datasources`(116)·`from modules import conn_health`(402)
    → `from shared import …`(두 모듈 이동 완료 → 정본 경로로 정리). 함수내부 lazy 라 import-time cycle 없음.
  - `shared/conn_health.py` 의 `from .config import *`·lazy `from . import datasources/db`, `shared/datasources.py`
    의 `from . import config`·lazy `from . import db` 는 `.`=shared 로 자동 해석(무편집).
  - `shared/datasources.py` 의 top-level `from . import cred_crypto` → `from modules import cred_crypto`:
    cred_crypto 는 Step 4 범위 밖(아직 modules/)이라 shared→modules **back-dep** 유지. cred_crypto 는
    stdlib(base64/os/cryptography)만 의존(datasources/db 미참조) → import-time cycle 없음. 후속 step 정리.
- Files (cross-feature changeset — feature-0011 cycle 가 0002 modules/·루트 shared/ 편집):
  - `shared/conn_health.py` (← `unit/feature-0002-agent-core/src/modules/conn_health.py`, git mv)
  - `shared/datasources.py` (← `unit/feature-0002-agent-core/src/modules/datasources.py`, git mv + cred_crypto back-dep 1줄)
  - `shared/db.py` (lazy back-dep 2줄 `from modules`→`from shared`)
  - `unit/feature-0002-agent-core/src/modules/conn_health.py` (alias shim 신규 본문)
  - `unit/feature-0002-agent-core/src/modules/datasources.py` (alias shim 신규 본문)
- Impact: 런타임 동작 불변(alias = 동일 객체). conn_health 30+ 소비처(app.py·insight·ask·agent_core·tests)·
  datasources 40+ 소비처 전부 보존. `make test` **회귀 0**(전체 green, 2 skip, F/E 0 — Step 3 시점 baseline
  2건은 main CI-fix 로 해소됨). /app alias 완전성 smoke PASS(`modules.conn_health is shared.conn_health`·
  `modules.datasources is shared.datasources`·db back-dep→shared·cred_crypto back-dep→modules·단일상태·config 체인).
  committed-tree 무결성 확인(shim 2개 staged: `M modules/{conn_health,datasources}.py` — untracked-shim BLOCKING 선제 차단).
- Rollback Notes: 단일 commit revert 로 두 모듈이 modules/ 로 복귀(db back-dep 도 동반 복원). 이미지 재빌드만
  (스키마/데이터 무변경). 라이브는 재배포 전까지 무영향.

## CHG-20260625-0005
- Date: 2026-06-25
- Related Requirement: P5a Step 5a — conn_health·datasources 소비처를 modules.* alias → shared.* 정본 경로로
  점진 마이그레이션 + 두 alias shim 제거 (TASK-0011-9 부분; Step 5 의 첫 sub-step).
- Summary: Step 4 에서 alias shim 으로 비파괴 추출했던 conn_health·datasources 의 **모든 소비처(60 ref, 18 파일)**
  를 `from modules import …`·`from . import …`(modules 내부 상대형)·`import modules.X`·dynamic(importlib/
  mock.patch/monkeypatch string) 전 형태에서 `from shared import …`/`shared.*` 로 일괄 마이그레이션하고,
  `modules/conn_health.py`·`modules/datasources.py` alias shim 2개를 **삭제**. 정본 단일 경로(shared.*)로 수렴 —
  Step 6(feature 단위 Dockerfile 분리)의 전제(소비처가 더는 modules.{conn_health,datasources} 에 의존 안 함).
- 마이그레이션 surface (18 파일, 60 ref):
  - 프로덕션: app.py(26 = conn_health 6 + datasources 20), agent_core.py(2), modules/ask.py(3 상대형),
    modules/insight.py(4 상대형), gdrive_mcp_seam.py(1), scripts/rekey_datasource_facts.py(1).
  - 테스트(12 파일): 정적 import + **dynamic 문자열 타깃**(`importlib.import_module("modules.conn_health/datasources")`,
    `mock.patch("modules.datasources.resolve")`, `monkeypatch.setattr("modules.datasources.resolve")`)까지 전수.
  - config·db·model_catalog 등 **타 모듈 참조는 미변경**(그들의 shim 유지 — 5b/5c 범위).
- Files: 18 consumer files (M) + `unit/feature-0002-agent-core/src/modules/conn_health.py`·`datasources.py` (D, shim 삭제).
  `shared/{conn_health,datasources}.py` 의 `from .` 상대 import 는 `.`=shared 로 정본 해석(무편집).
- Impact: 런타임 동작 불변(shared.X 는 직전 alias 가 가리키던 동일 객체). `make test` **회귀 0**(전체 green, 2 skip,
  F/E 0). **residual grep 0**(라이브 modules.conn_health/datasources 참조 0). /app smoke: shared.* import OK ·
  modules.{conn_health,datasources}→ModuleNotFoundError(shim 제거 확인) · modules.{config,db} shim 유지 ·
  db back-dep · cred_crypto OK. §18.8 3렌즈(missed-ref/correctness/deploy) BLOCKING 0/NIT 0(실 이미지 배포 레이아웃 import 실증).
- Rollback Notes: 단일 commit revert 로 18 파일 import 복원 + 2 shim 재생성. 이미지 재빌드만(스키마/데이터 무변경).

## CHG-20260625-0006
- Date: 2026-06-25
- Related Requirement: P5a Step 5b — config 소비처를 modules.config alias → shared.config 정본 경로로
  점진 마이그레이션 + modules/config.py alias shim 제거 (TASK-0011-9 부분; Step 5 의 두 번째 sub-step).
- Summary: config 는 L0 foundation(fan-in 25; 16+ 모듈이 `from .config import *` 로 재노출;
  `modules/__init__.py` eager-import). 모든 소비처(**~150 ref, 53 파일**)를 `from modules import config`·
  `from modules.config import X`·`import modules.config`·`from . import config`·`from .config import *`·
  dynamic(`sys.modules["modules.config"]`·mock.patch·importlib) 전 형태에서 `from shared import config`/
  `from shared.config import …`/`shared.config` 로 일괄 마이그레이션하고, `modules/config.py` alias shim 을 **삭제**.
  modules/__init__.py 의 eager `from . import config`→`from shared import config`, `from .config import *`→
  `from shared.config import *` (재노출 체인·`_all_modules` 리스트 보존 — `config` 이름이 shared.config 로 재바인딩).
- 마이그레이션 방식: subagent workflow 28파일 + 세션한도(2pm reset)로 미완된 26파일 중 21파일 결정적 스크립트
  (정규식 `modules.config`→`shared.config`, `from modules import config`→`from shared import config`)로 보완.
  나머지(tools.py 등)는 config 참조 0. config·conn_health·datasources 외 타 모듈(db/memory/render/utils 등)은 미변경.
- Files: 53 consumer files (M — modules/* 17, scripts 6, tests 19, eval 7, agent_core.py, feature-0003 app.py 등)
  + `unit/feature-0002-agent-core/src/modules/config.py` (D, shim 삭제). `shared/{db,conn_health,datasources}.py`
  의 `from .config import *`/`from . import config` 는 `.`=shared 로 정본 해석(무편집).
- Impact: 런타임 동작 불변(shared.config 는 직전 alias 가 가리키던 동일 객체 — 단일 상태, split-brain 없음). `make test`
  **회귀 0**(전체 green, 2 skip, F/E 0). **residual grep 0**(라이브 modules.config 참조 0). deploy-layout smoke:
  `from shared import config` OK · `import modules.config`→ModuleNotFoundError(shim 제거) · modules 패키지+__init__
  eager 체인 OK · db/memory shim 유지 · agent_core/web app import OK · config 재노출 체인(`from modules import GLOBAL_CONVERSATION_ID`·`from modules.db import AGENT_KB_PG_PORT`) OK. §18.8 3렌즈(missed-ref/correctness/deploy,
  실 이미지 baked-layout 빌드·실행) BLOCKING 0/NIT 0.
- Rollback Notes: 단일 commit revert 로 53 파일 import 복원 + config shim 재생성. 이미지 재빌드만(스키마/데이터 무변경).

## CHG-20260625-0007
- Date: 2026-06-25
- Related Requirement: P5a Step 5c — db 소비처를 modules.db alias → shared.db 정본 경로로 마이그레이션 +
  modules/db.py alias shim 제거 (TASK-0011-9 부분; Step 5 의 마지막 sub-step). **4개 alias shim(config·db·
  conn_health·datasources) 전부 제거 완료 → shared/ 점진 추출 구조 완성.**
- Summary: db(repo 최다결합, fan-in 17; `_pg_connect`/`_pg_connect_ro`/`_POOL_REGISTRY` 등 underscore 9+;
  modules/__init__ eager)의 **모든 소비처(219 ref/52 파일 — app.py 112 포함)**를 `from modules import db`·
  `from modules.db import X`·`import modules.db`·`from .db import *`·dynamic(`sys.modules["modules.db"]`·
  `monkeypatch.setattr("modules.db._pg_connect")`)·**+ bin/kb-pg-healthcheck.sh 의 docker-exec embedded python**
  에서 `shared.db` 로 마이그레이션하고 `modules/db.py` shim 삭제. modules/__init__ eager+wildcard 재노출 체인 보존
  (db 이름 shared.db 재바인딩; underscore 심볼 __all__ 재노출 유지).
- Files: 52 .py consumer files (M) + `bin/kb-pg-healthcheck.sh` (M — .sh-embedded python) +
  `unit/feature-0002-agent-core/src/modules/db.py` (D, 마지막 shim). shared/db.py 정본 +
  shared/{conn_health,datasources}.py 의 lazy `from . import db`(=shared.db) 무편집.
- Impact: 런타임 동작 불변(shared.db = 직전 alias 동일 객체). `make test` **회귀 0**(전체 green). **residual grep 0
  (전 파일 — .py + .sh + config/yml)**. baked-layout smoke: `from shared import db` OK · `import modules.db`→
  ModuleNotFoundError · modules 재노출(AGENT_KB_PG_PORT·underscore) OK · cross-module lazy(db↔conn_health/datasources) OK.
  §18.8 3렌즈(실 이미지 baked-layout 빌드·실행): **BLOCKING 1 발견·수정**(kb-pg-healthcheck.sh:121 .sh-embedded
  `from modules.db import` — .py-only 마이그가 놓침 → shared.db 로 수정·전파일 재grep 0) / correctness NIT 0 / deploy SAFE.
- Rollback Notes: 단일 commit revert 로 52파일+healthcheck import 복원 + db shim 재생성. 이미지 재빌드만(스키마/데이터 무변경).

## CHG-20260625-0008
- Date: 2026-06-25
- Related Requirement: TASK-0011-11 (동반 저위험 doc) — docs/CODEBASE_MAP.md stale 정정 + #4 GDPR legal-erasure gap 명시.
- Summary: CODEBASE_MAP 이 feature-0001~0006 까지만 반영하고 shared/ 를 "예약 영역"으로 기술하던 stale 상태를
  현행화. (1) §1 디렉토리 트리: feature-0007~0011 추가, shared/ 설명을 실제 6모듈로, playbooks PB-0008 추가.
  (2) §3 Shared Module Index: 예약-영역 1행을 실제 모듈 6행(__init__·model_catalog·config·db·conn_health·datasources)
  + 추출/배선/shim-제거 맥락으로 교체. (3) §4 Feature File Index: feature-0007~0011 역할·주요소스 5행 추가.
  (4) §7 Known Gaps 신설: #4 GDPR legal-erasure gap(feature-0002 attachment_reconciliation 미배선) 명시 —
  코드 보존·dedup 금지·wiring 은 별도 compliance 결정(feature-0011 ANCHOR §3 동반 메모 출처).
- Files: `docs/CODEBASE_MAP.md` (M, 프로젝트 doc — 본 cycle 유일 코드외 변경) + feature-0011 docs(MODIFY/REVIEW/TASK/REPORT).
- Impact: 문서 전용(런타임/이미지 무영향, 배포 불요). CODEBASE_MAP 가 현행 11개 feature + shared/ 6모듈 + GDPR gap 을 반영.
- Rollback Notes: 단일 commit revert(doc only).