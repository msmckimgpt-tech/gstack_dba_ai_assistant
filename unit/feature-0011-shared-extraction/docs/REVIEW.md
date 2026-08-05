---
doc_type: REVIEW
feature_id: feature-0011-shared-extraction
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260624-0001 [SUBAGENT:shared-extraction-p5a-step1]
- Related Change: CHG-20260624-0001 (shared/ 플러밍 + model_catalog 첫 추출, P5a Step 1)
- Reason: model_catalog 을 modules/ → shared/ 로 이동하고 import 4사이트를 재배선. db.py 추출 전
  저결합 모듈로 플러밍을 test-gated 로 증명하는 안전 sequencing (big-bang 금지).
- §18.8 Adversarial Panel: general-purpose 적대적 리뷰어 1인. 7개 결함 가설(놓친 import 사이트·
  컨테이너 경로 깨짐·eager import 체인·Dockerfile COPY·Makefile shadowing·baseline 회귀·wildcard)을
  worktree Read/Grep + **빌드 이미지 실런타임 검증**으로 공격.
  - **결과: BLOCKING 0 / NIT 2.**
  - 실측 핵심: web `uvicorn web.app:app` 실부팅 "Application startup complete"(유일 에러 = DB 호스트
    부재, import 무관) · agent/memory-init/insight-worker/ask-worker 전부 `python /app/agent_core.py`
    import OK · 놓친 import 사이트 0(절대·상대·bare·동적·문자열 전수) · `modules/__init__`→llm→
    shared.model_catalog eager 체인 무결 · `make test` 1077 passed/2 failed(2 실패는 clean main
    에서도 동일 재현 = baseline, 본 변경 무관) · Makefile `/work` top-level shadowing 0.
- Alternatives Considered: db.py 우선 추출(Alt-A, 최고위험 → 반려, ANCHOR §2) · shared 없이 유지
  (Alt-B → 소유권/빌드분리 상충) · 별도 패키지화(Alt-C → 오버헤드 과대).
- Risks: 라이브 web/agent 인접이나 import 경로만 변경(런타임 동작 불변)·단일 commit revert 가능·
  배포 시 healthz/smoke 로 재확인.
- NIT 처리:
  - NIT-1 (호스트 `__pycache__`/README/docs 가 `COPY shared` 로 이미지 유입): **수용**. 기존
    `COPY modules /app/modules` 와 동일 패턴이고 `__pycache__` 는 gitignored 라 클린 체크아웃 빌드는
    무영향. Python 이 `.pyc` 를 mtime 으로 재검증해 기능 무해(패널 실측). repo-wide `.dockerignore`
    도입은 본 Step 1 범위 밖 → 별도 hygiene 후속(TASK-0011-10 인근).
  - NIT-2 (shared/README.md 자기참조 stale): **수정**. README 에 "model_catalog 첫 승격" + import/path
    규칙 반영. shared/docs/{MODIFY,REPORT}.md 의 area-level 추적은 feature MODIFY 가 정본이라 미변경(수용).
- Open Questions: 없음 (Step 2 db.py shim 은 후속 cycle).
- Human Approval Needed: PR 생성·deploy confirm (외부영향). P5a/P5b 진행 자체는 2026-06-24 사용자 승인.

## REV-20260624-0002 [SUBAGENT:config-alias-step2]
- Related Change: CHG-20260624-0002 (config → shared/config + 모듈 alias shim, P5a Step 2)
- Reason: config(L0 foundation, fan-in 25)를 shared/ 로 추출. db 의 `from .config import *` 강결합
  선행 해소(/plan-eng-review 순서 재설계, decision 5cc24689). 모듈 alias(sys.modules 치환)로
  271+ 심볼·monkeypatch·wildcard·db 재노출 체인을 동일 객체로 완전 보존.
- 설계 전환: enumeration shim(import * + 명시 9 public + 8 underscore) → **annotated assignment**
  심볼(`_ACTIVE_DEFAULT_DB: ContextVar`)을 AST 스캔이 놓쳐(ast.Assign 만 보고 ast.AnnAssign 누락)
  `test_mssql_security_boundary` 10건 회귀 → **모듈 alias** 로 전환해 완전성 보장.
- §18.8 Adversarial Panel: Workflow `config-alias-adversarial-verify` (ultracode 다중렌즈). 6 에이전트
  중 4 렌즈 완료 + 2(monkeypatch-isolation·completeness-critic)는 **세션 한도로 미완**(아래 보완).
  - **결과: BLOCKING 1 (수정) / NIT 3 (수용).**
  - 완료 렌즈: symbol-completeness=SAFE · sys.modules-hazard=SAFE · build-layout=SAFE · live-redeploy=**DEFECT_BLOCKING**.
  - **BLOCKING (live-redeploy lens) — 수정 완료**: `git mv` 가 modules/config.py 를 rename(삭제)으로
    기록했는데 새 shim 은 **untracked(`??`)** → index commit 시 committed tree 에 modules/config.py
    부재 → 재배포 시 `import modules`(web.app·agent_core·워커 전부 startup)에서 `from . import config`
    ImportError 로 전 서비스 crash. make test·/app smoke 는 **working tree**(shim 존재)로 돌아 가렸음.
    AGENTS.md §16 가 `git add -A` 금지라 명시 staging 필수. → **`git add modules/config.py` 후
    `git ls-tree $(git write-tree)` 에 blob 존재 확인 + committed-tree 등가 레이아웃에서 `import modules`
    실증(modules.config is shared.config=True, _ACTIVE_DEFAULT_DB 접근)** 으로 해소.
  - **미완 2 렌즈 보완**: monkeypatch-isolation 은 make test 의 `test_mssql_security_boundary`(70 tests,
    `_c._ACTIVE_DEFAULT_DB.set()`·setattr monkeypatch 집약) green 으로 경험적 커버됨. completeness-critic
    미실행 — 4 렌즈가 핵심 표면(심볼·alias 관용구·라이브·빌드) + git 상태를 커버, BLOCKING 적발로 가치 입증.
  - NIT 처리: (1) shim 의 `import shared.config` 가 shared 부모를 path 에 요구 — **Step 1 기존 조건**,
    make test/컨테이너가 제공(수용). (2) sys.modules['shared.config'] 삭제+재import 시 이론적 split-brain —
    repo 전체에 그런 코드 0건(유일 reload 인 test_llm_env_naming 은 alias 일관 동작), **도달 불가**(수용).
    (3) __pycache__ 이미지 유입 — Step 1 동일 NIT, gitignored·무해(수용).
- Risks: config 는 최대 fan-in foundation 이나 alias = 동일 객체라 런타임 동작 불변. 단일 commit revert 가능.
- Human Approval Needed: PR 생성·deploy confirm (외부영향). deploy_scope:included 로 머지 후 자동 배포.

## REV-20260624-0003 [SUBAGENT:db-alias-step3]
- Related Change: CHG-20260624-0003 (db → shared/db + 모듈 alias shim, P5a Step 3)
- Reason: db(repo 최다결합, fan-in 17)를 shared/ 로 추출. config-first(Step 2) 덕에 db 의
  `from .config import *` 가 shared.config 로 해소. config 와 동일 alias 패턴으로 모듈객체접근·
  underscore·AnnAssign(`_POOL_REGISTRY`)·__all__·monkeypatch·config 재노출 체인 완전 보존.
- lazy back-dep: shared/db.py 의 `from . import datasources/conn_health`(lazy) → `from modules import`
  재배선(두 모듈 아직 modules/, Step 4 정리). db↔conn_health 상호 lazy 는 alias 로 db 단일객체 유지.
- §18.8 Adversarial Panel: Workflow `db-alias-adversarial-verify` (집중 3렌즈, 신규 위험면 표적). 전부 완료.
  - **결과: BLOCKING 0 / NIT 1.**
  - lazy-backdep-runtime-cycle = **SAFE**(런타임 db↔conn_health↔datasources lazy cycle 무한루프/부분초기화 없음 실측).
  - alias-completeness-config-reexport = **SAFE**(30 심볼·__all__·underscore·AnnAssign·db→config 재노출 체인 보존).
  - live-redeploy-git-tree = **DEFECT_NIT**: **Step 2 untracked-shim BLOCKING 클래스 재공격 → clean 확인**
    (선제 staging 으로 staged delta = `A shared/db.py` + `M modules/db.py` 정확, committed-tree import 실증).
    NIT = 패널 에이전트의 smoke 스크립트 leftover(`probe*.py`, untracked·Dockerfile 미COPY·미스테이징 — 배포/커밋 무위험) → **정리 완료**(수용).
- Risks: db 는 foundational 이나 alias = 동일 객체라 런타임 동작 불변. lazy back-dep 은 함수내부(import-time cycle 0). 단일 commit revert 가능.
- Human Approval Needed: PR 생성·deploy confirm. deploy_scope:included 로 머지 후 자동 배포.

## REV-20260625-0004 [SUBAGENT:conn-health-datasources-alias-step4]
- Related Change: CHG-20260625-0004 (conn_health·datasources → shared/ + 모듈 alias shim + db back-dep 정리, P5a Step 4)
- Reason: L1 cross-feature 공통 모듈 conn_health(474)·datasources(282)를 shared/ 로 추출. config·db
  (Step 2/3)와 동일 alias 패턴으로 모듈객체접근·underscore·모듈상태(모니터/_DEK_CACHE)·monkeypatch 완전 보존.
  db 의 lazy back-dep `from modules import` → `from shared import` 정리(두 모듈 이동 완료). datasources 의
  cred_crypto 는 범위 밖이라 `from modules import cred_crypto` back-dep 유지(stdlib-only → cycle 없음).
- §18.8 Adversarial Panel: general-purpose 적대적 리뷰어 3렌즈(병렬, 신규 위험면 표적 — "통과 아니라 결함 적발").
  - **결과: BLOCKING 0 / NIT 0.**
  - **import-cycle/runtime = SAFE**: 신규 import-time cycle 0. 모든 back-dep 함수내부 lazy 확인(col 0 검증).
    유일 top-level cross-pkg edge(`shared/datasources.py:19 from modules import cred_crypto`)는 cred_crypto
    가 stdlib만 의존 + `modules/__init__` eager 16모듈 어느 것도 datasources/conn_health top-level import 없음
    → 부분초기화 cycle 불가. 실제 agent 이미지에서 최악 import 순서(shared.datasources/conn_health/db 단독
    선import) 실행 OK. **`conn_health._scope_key_of(ds) == db._breaker_key(ds)` 키 계약 보존 실측**.
  - **alias-completeness = SAFE**: 모든 소비처(`from modules import`/`from . import`/`import modules.X`/
    `importlib.import_module`) alias 해석 확인. 모듈상태 단일 인스턴스 실측(`sch._STATE is mch._STATE`,
    `sds._DEK_CACHE is mds._DEK_CACHE` = True — 모니터 중복/DEK 캐시 분열 없음). monkeypatch 타깃 동일 객체
    착지. `modules/__init__` 가 두 모듈 재노출/star-export 0(enumeration fragility 비해당). 111 테스트 green.
  - **deploy/build = SAFE**: 단일 Dockerfile(`unit/feature-0002-agent-core/src/Dockerfile`)이 `COPY modules`+
    `COPY shared` 둘 다 `/app` 하위 → web/agent/insight-worker/ask-worker 전 서비스에서 shared↔modules 양방향
    coupling(`shared.datasources`의 `from modules import cred_crypto`, shim 의 `import shared.X`) 해석.
    build/deploy/CI/Makefile 에 옛 경로(`modules/{conn_health,datasources}.py`) 참조 0. Step 2/3 동일 wholesale
    `COPY shared` 라 추가 빌드 배선 불필요. `/shared` 런타임 볼륨 ≠ `/app/shared` 패키지(충돌 없음).
- committed-tree 무결성: staged delta = `A shared/{conn_health,datasources}.py` + `M shared/db.py` +
  `M modules/{conn_health,datasources}.py`(shim), `git status` clean(untracked/unstaged 0) → committed tree =
  smoke 통과한 working tree. Step 2 untracked-shim BLOCKING 클래스 선제 차단.
- Alternatives Considered: cred_crypto 동반 추출(범위 확장 → Resume≠Re-scope 반려, 락된 플랜=conn_health/datasources만).
  enumeration shim(config Step 2 의 annotated-symbol 누락 교훈 → alias 우선).
- Risks: 라이브 db 인접(연결 health 게이트 경로)이나 alias = 동일 객체라 런타임 동작 불변. lazy back-dep
  함수내부(import-time cycle 0). 단일 commit revert 가능. 배포 시 healthz/smoke 로 재확인.
- Human Approval Needed: P5a Step 4 는 P5a PLAN-APPROVED(2026-06-24) 범위. PR 생성·deploy 는 외부영향이나
  deploy_scope:included 로 머지 후 자동 배포(첫 배포 직전 1줄 표면화).

## REV-20260625-0005 [SUBAGENT:conn-health-datasources-migration-step5a]
- Related Change: CHG-20260625-0005 (conn_health·datasources 소비처 shared.* 마이그레이션 + shim 2개 제거, P5a Step 5a)
- Reason: alias shim 비파괴 추출(Step 4) 이후 소비처를 정본 shared.* 로 수렴 + shim 제거 → 단일 import 경로 확립
  (Step 6 Dockerfile 분리 전제). shim 제거로 alias 안전망이 사라져 누락 참조(특히 dynamic/string)는 즉시 런타임 깨짐 → 적대 검증 집중.
- §18.8 Adversarial Panel: Workflow `step5a-adversarial-panel` (3렌즈 병렬, high effort, 실 이미지 실행 검증 — "통과 아니라 결함 적발").
  - **결과: BLOCKING 0 / NIT 0.**
  - **missed-ref hunt = SAFE**: 프로덕션 코드에 dynamic/computed import(importlib/__import__/sys.modules/pkgutil/
    getattr)로 conn_health/datasources 도달 경로 0. string-literal 모듈 해석 0(app.py 의 'datasources' 문자열은
    JSON key/탭 id/dict key). modules/__init__ 의 고정 _all_modules 에 두 모듈 부재(항상 lazy). 실 agent 이미지에서
    shared.* import OK · modules.{conn_health,datasources}→ModuleNotFoundError · 전 소비처 import OK · lazy
    cross-module body(conn_health._scope_key_of→shared.datasources, db→shared.conn_health/datasources) 해석.
  - **migration correctness = SAFE**: `git diff | grep '^+.*from shared import' | grep -v 'conn_health|datasources'`
    = EMPTY(타 모듈 오마이그레이션 0; shared.memory/render 부재라 오류 시 즉시 crash — 안 남). alias 이름 대칭,
    함수-local 들여쓰기 보존(lazy→eager 승격 0), 중복/shadow import 0.
  - **deploy/runtime = SAFE**: 단일 agent 이미지가 COPY shared+modules 를 /app 하위, WORKDIR /app → 5개 서비스
    (agent/memory-init/insight-worker/ask-worker/web) 전부 sys.path 해석. 워크트리에서 이미지 빌드 후 **배포 레이아웃
    (소스 마운트 없음·PYTHONPATH 무설정·cwd=/app)** 에서 실행: import agent_core·web.app·scripts.rekey_datasource_facts·
    modules.ask·modules.insight OK, modules.{conn_health,datasources}→ModuleNotFoundError 확인.
    (informational: gdrive-mcp 서비스는 scaffold stub(echo+exit 0, 미baked/미import) → 마이그레이션의 프로덕션 런타임 경로 없음.)
- residual: 라이브 modules.conn_health/datasources 참조 0(deterministic grep). 잔존 = shared/ 내부 정본 상대 import
  (=shared.*, 정상) + modules/db.py 의 stale 주석 1줄(db shim, 5c 에서 제거).
- Alternatives Considered: Step 5 전체(config·db 포함 ~370 ref) big-bang(반려 — "점진" 위반·미커버 프로덕션 경로 깨짐 위험);
  per-module sub-step(채택 — 5a=conn_health/datasources, 5b=config, 5c=db, 각 독립 검증·shim 1개씩 제거).
- Risks: app.py(라이브 web) 등 다수 소비처 편집이나 동일 객체 수렴이라 동작 불변. shim 제거로 안전망 소거됐으나
  3렌즈 실이미지 검증으로 누락 0 확인. 단일 commit revert 가능. 배포 시 healthz/smoke 재확인.
- Human Approval Needed: P5a PLAN-APPROVED(2026-06-24) 범위. PR 생성·deploy 는 외부영향이나 deploy_scope:included
  로 머지 후 자동 배포(첫 배포 직전 1줄 표면화).

## REV-20260625-0006 [SUBAGENT:config-migration-step5b]
- Related Change: CHG-20260625-0006 (config 소비처 shared.config 마이그레이션 + modules/config shim 제거, P5a Step 5b)
- Reason: L0 foundation config(fan-in 25, 16+ 모듈 wildcard 재노출, __init__ eager) 소비처를 정본 shared.config 로
  수렴 + shim 제거 → 단일 import 경로. shim 제거로 alias 안전망 소거, foundation 이라 누락 시 전역 파급 → 적대 검증 집중.
- §18.8 Adversarial Panel: Workflow `step5b-config-adversarial-panel` (3렌즈 병렬, high effort, **실 이미지 baked-layout 빌드·실행**).
  - **결과: BLOCKING 0 / NIT 0.**
  - **missed-ref hunt = SAFE**: 프로덕션 dynamic config 해석(importlib/__import__/getattr/sys.modules/pkgutil) 0.
    `import modules` 후 config 상수(OPENAI_MODEL·DB_HOST·GLOBAL_CONVERSATION_ID·DATASOURCES·set/get_active_datasource)
    hasattr PASS — wildcard 재노출 체인 무결. `modules.config is shared.config`(attr 바인딩) True. 단일 상태(set_active_datasource
    mutation 이 모든 alias 에 반영·리셋) — split-brain 없음. (note: `import modules.config` 서브모듈 형태는 이제
    ModuleNotFoundError — 그 형태 caller 0 확인, dormant.)
  - **migration correctness = SAFE**: `git diff HEAD | grep '+from shared import' | grep -v 'config|conn_health|datasources|model_catalog'` = EMPTY(타 모듈 오마이그 0; shared.memory/render 부재라 오류 시 즉시 crash — 안 남).
    14개 `from .config import *`→`from shared.config import *` 순수 path swap. multi-line import 블록(agent_core·account_recall·
    ask·kb_retrieval·llm) 심볼 리스트 무변경. alias 1:1 보존. __init__ `_all_modules=[config,...]` 리스트 무결.
  - **deploy/runtime = SAFE**: 워크트리에서 agent 이미지 빌드 후 **baked layout(마운트 없음·PYTHONPATH 무설정·WORKDIR /app)**:
    `from shared import config` OK · `import modules.config`→ModuleNotFoundError(shim 제거) · import modules/agent_core/web.app OK ·
    config 상수 8개 modules 재노출 identity match · 6개 worker/healthcheck 스크립트 import OK. Dockerfile COPY shared /app/shared 확인.
- residual: 라이브 modules.config 참조 0(deterministic grep). 잔존 = shared/ 내부 정본 상대 import(=shared.config, 정상)
  + modules/db.py 의 stale 주석 2줄(db shim, 5c 에서 제거).
- 마이그 실행 노트: subagent workflow 28파일 완료 후 26 에이전트가 API 세션한도(2pm KST reset)로 실패 → 미완 파일을
  결정적 정규식 스크립트(main-loop)로 보완(21파일/82 ref), 동일 검증 게이트 통과. 패널은 한도 reset 후 정상 실행.
- Alternatives Considered: enumeration shim(annotated-symbol 누락 fragile — config Step 2 교훈) → 본 step 은 alias 가 아니라
  소비처를 정본으로 옮기는 마이그라 무관. big-bang(반려, 5a REV 참조).
- Risks: foundation·다수 소비처(app.py 라이브 web 포함)이나 동일 객체 수렴이라 동작 불변. shim 제거 안전망 소거됐으나
  3렌즈 baked-layout 실증 + make test green 으로 누락 0 확인. 단일 commit revert 가능. 배포 시 healthz/smoke 재확인.
- Human Approval Needed: P5a PLAN-APPROVED(2026-06-24) 범위. deploy_scope:included 로 머지 후 자동 배포(첫 배포 1줄 표면화).

## REV-20260625-0007 [SUBAGENT:db-migration-step5c]
- Related Change: CHG-20260625-0007 (db 소비처 shared.db 마이그레이션 + modules/db shim 제거, P5a Step 5c — 마지막 sub-step)
- Reason: db(repo 최다결합 fan-in 17) 소비처를 정본 shared.db 로 수렴 + 마지막 alias shim 제거 → 4개 shim
  (config·db·conn_health·datasources) 전부 제거, shared/ 점진 추출 구조 완성. db underscore 심볼·모듈객체 접근·
  __init__ 재노출 광범위라 적대 검증 집중.
- §18.8 Adversarial Panel: Workflow `step5c-db-adversarial-panel` (3렌즈 high effort, **실 이미지 baked-layout 빌드·실행**).
  - **결과: BLOCKING 1 (발견·수정·재검증) / NIT 0 / deploy SAFE.**
  - **missed-ref hunt = DEFECT_BLOCKING → 수정 완료**: `bin/kb-pg-healthcheck.sh:121` 의
    `docker exec ... python -c 'from modules.db import _pg_connect, _pg_available'` (라이브 agent 컨테이너 PG 헬스 smoke).
    Step 5c 마이그가 **.py-only** 라 .sh-embedded python 참조를 놓침 → db shim 삭제로 ModuleNotFoundError 위험.
    **`from shared.db import` 로 수정 후 전 파일(.py+.sh+config/yml) 재grep 0 확인.** (.py 런타임/테스트/모듈객체/
    underscore 심볼(_pg_connect 등)·__init__ 재노출 체인은 실 이미지에서 전부 PASS.)
  - migration correctness = SAFE(NIT 0): collateral 0(`git diff HEAD` 추가 shared. 라인 전부 db; shared.memory/utils
    부재라 오마이그 시 즉시 crash — 안 남), app.py 112 add==112 remove 전부 shared.db swap, 12× `sys.modules['modules.db']`
    →`['shared.db']` 등 string 타깃 정합(7개 고위험 테스트 실 이미지 pytest PASS), alias/placement 보존, __init__ 재노출 무결.
  - deploy/runtime = SAFE: 워크트리 agent 이미지 빌드 후 baked-layout(마운트 없음·WORKDIR /app·PYTHONPATH 무설정):
    `from shared import db`·shared.db underscore 심볼·`import modules`(AGENT_KB_PG_PORT 재노출)·agent_core·web.app·
    attachment_pg_mirror._pg()·healthcheck 스크립트·cross-module lazy(db↔conn_health/datasources) 전부 해석.
    `import modules.db`→ModuleNotFoundError 확인.
- 교훈(재발 방지): 모듈 마이그레이션 sweep 은 .py 뿐 아니라 **.sh/.yml 등에 embedded 된 python(`docker exec ... python -c`)**
  도 포함해야 함. 본 cycle 에서 db 만 .sh 참조 보유(config/conn_health/datasources 는 .sh 참조 0 — 패널·grep 확인).
- residual: 전 파일 live `modules.{config,db,conn_health,datasources}` 참조 0(.md docs 만 historical 잔존).
- Risks: 최다결합이나 동일 객체 수렴이라 동작 불변. shim 4개 전부 제거로 안전망 소거됐으나 3렌즈 baked-layout 실증
  + make test green + BLOCKING 수정·재검증. 단일 commit revert 가능. 배포 시 healthz/smoke 재확인.
- Human Approval Needed: P5a PLAN-APPROVED(2026-06-24) 범위. deploy_scope:included 로 머지 후 자동 배포(첫 배포 1줄 표면화).

## REV-20260625-0008 [SKIPPED:doc-only-codebase-map]
- Related Change: CHG-20260625-0008 (TASK-0011-11 — CODEBASE_MAP stale 정정 + #4 GDPR gap 명시)
- §18.8 Adversarial Panel: **SKIPPED — doc-only, 비핵심경로**. 변경은 `docs/CODEBASE_MAP.md`(프로젝트 참조 문서)
  + feature-0011 docs 뿐, src/런타임/이미지 무영향. 적대 패널의 표적(import 깨짐·런타임·배포)이 부재.
- 검증(결정적, main-loop): 추가한 사실의 정확성을 소스로 교차확인 — feature-0007~0011 역할은 docs/STATUS.md 표 +
  각 feature FUNCTION.md §1 과 일치; shared/ 6모듈은 `ls shared/*.py` 실측; PB-0008 은 `playbooks/` 실측;
  GDPR gap 문구는 feature-0011 ANCHOR §3 동반 메모와 일치. CODEBASE_MAP 내부 표 구조 보존(중복 행 없음).
- Risks: 없음(doc-only, 배포 불요). 잘못된 기술 시 revert 1 commit.
- Human Approval Needed: 없음(저위험 doc; PR 생성만 외부노출).
## REV-20260805T153000-p5a-closeout [SKIPPED:policy-decision-record] — P5a 종결 판단 근거 (doc+주석·동작 0)

- 사용자 위임("현재까지의 개발 및 대화 내역을 먼저 검토하여 작업 방향을 결정") 에 따른 이력-검토 결정:
  #4 는 적대 리뷰 42-에이전트 판정·ANCHOR §3·CODEBASE_MAP §7 의 기존 결론(보존)을 채택,
  #5 는 shared/ 추출 완성(선행 충족) 후에도 6주간 배포 스파인 안정화 실적(0014/0020/0039)이
  분리 리스크를 상회 → 불채택. 정본 ADR-20260805T153000. 코드 변경은 주석 라벨 1파일뿐
  (py_compile PASS·런타임 0) — 패널은 [SKIPPED] + 본 근거 기록으로 갈음.
