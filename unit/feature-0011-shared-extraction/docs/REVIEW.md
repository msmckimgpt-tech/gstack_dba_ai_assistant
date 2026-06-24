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
