---
doc_type: FUNCTION
feature_id: feature-0011-shared-extraction
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
feature-0002(agent-core)·feature-0003(web-ui) 두 feature 와 격리 컨테이너가 공유하는
공통 코드를 repo 루트 `shared/` Python 패키지로 **점진 추출**한다(big-bang 금지, 모듈 1개/step,
각 step `make test` 회귀 0 게이트). 위상정렬 순서: model_catalog(Step 1, 저결합 플러밍 증명) →
config(Step 2, L0 foundation) → db(Step 3, L1 최다결합) → conn_health·datasources(Step 4, L1
cross-feature). Step 2 부터는 고결합 모듈을 **모듈 alias shim**(`sys.modules[__name__]=shared.X`)으로
옮겨 `modules.X` 와 `shared.X` 를 동일 객체화 → 소비처 재배선 0 으로 비파괴 추출.
**Step 5(점진 마이그레이션, 완료)**: 비파괴 추출이 끝난 모듈의 소비처를 정본 `shared.*` 경로로 수렴시키고 alias shim 을
제거(per-module sub-step 5a/5b/5c). 5a(conn_health·datasources)·5b(config)·5c(db) 전부 완료 →
**4개 alias shim 전부 제거, config·db·conn_health·datasources 는 shim 없이 `shared.*` 단일 경로로만 존재**
(model_catalog 는 Step 1 부터 직접). shared/ 점진 추출 구조 완성.

## 2. Goal
- REQ-001: repo 루트 `shared/` 를 import 가능한 Python 패키지로 확립(`__init__.py`).
- REQ-002: 저결합 공통 모듈 1개를 `modules/` → `shared/` 로 이동하고 모든 import 사이트를 재배선.
- REQ-003: 컨테이너(Dockerfile)와 `make test`/eval(PYTHONPATH)이 `shared` 를 양 feature 에서
  import 가능하게 배선하고, `make test` 회귀 0 으로 증명.

## 3. In Scope (누적 — Step 1~4 완료)
- `shared/__init__.py` 패키지 골격 (Step 1).
- `modules/` → `shared/` git mv(history 보존) + 추출 방식:
  - `model_catalog.py` (Step 1, full 이동 + import 4사이트 재배선).
  - `config.py` (Step 2, 모듈 alias shim — L0 foundation, fan-in 25).
  - `db.py` (Step 3, 모듈 alias shim — L1 최다결합, fan-in 17).
  - `conn_health.py`·`datasources.py` (Step 4, 모듈 alias shim — L1 cross-feature).
- Step 4 back-dep 정리: `shared/db.py` 의 lazy `from modules import datasources/conn_health` →
  `from shared import …`. `shared/datasources.py` 는 `from modules import cred_crypto` back-dep 유지
  (cred_crypto 미추출 — 후속 step).
- **Step 5a 마이그레이션**: conn_health·datasources 소비처(60 ref/18 파일 — 정적+dynamic/string)를 `from shared
  import …`/`shared.*` 로 전환하고 `modules/conn_health.py`·`modules/datasources.py` alias shim 2개 제거.
- **Step 5b 마이그레이션**: config 소비처(~150 ref/53 파일 — 정적+`from .config import *` wildcard+dynamic)를
  `from shared import config`/`from shared.config import …`/`shared.config` 로 전환하고 `modules/config.py` alias shim 제거.
  modules/__init__ 의 eager `from . import config`·wildcard `from .config import *` 도 shared 로 전환(재노출 체인 보존).
- **Step 5c 마이그레이션**: db 소비처(219 ref/52 파일 — app.py 112 + underscore 심볼 + dynamic + **bin/kb-pg-healthcheck.sh
  .sh-embedded python**)를 `shared.db` 로 전환하고 `modules/db.py` alias shim 제거. modules/__init__ eager+wildcard
  재노출 체인 보존. → **4개 alias shim 전부 제거, shared/ 추출 완성.**
- Dockerfile: `COPY shared /app/shared` (Step 1, 이후 wholesale 라 추가 배선 불요).
- Makefile: test/eval/kb-retrieval-eval PYTHONPATH 에 `/work`(shared 의 부모) 추가 (Step 1).

## 4. Out of Scope (후속 step / 별도 cycle)
- cred_crypto·memory·llm 등 추가 공통 모듈 추출 (후속 step).
- feature 단위 Dockerfile 분리 (Step 6) + 브라우저 QA.
- app.py router 분할 (P5b, 별도 Critical cycle).
- attachment_reconciliation GDPR legal-erasure wiring (별도 compliance 결정).

## 5. Inputs
- 빌드: docker build context = repo 루트(`shared/` 포함).
- 테스트: `make test` (격리 agent 이미지, `--no-deps`, PYTHONPATH=두 src + `/work`).

## 6. Outputs
- `/app/shared/model_catalog.py` (컨테이너), `shared/model_catalog.py` (repo).
- 두 feature·컨테이너에서 `from shared.model_catalog import ...` 해석 성공.

## 7. Main Flow
1. shared/ 패키지 골격 생성.
2. 저결합 모듈 git mv → shared/.
3. 전 import 사이트(절대+상대) 재배선.
4. Dockerfile COPY + Makefile PYTHONPATH 배선.
5. `make test` green 게이트(회귀 0) + 프로덕션(/app) import smoke.

## 8. Edge Cases
- `modules/` 내부 상대 import(`from .model_catalog`): `modules/__init__` 가 eager import 하므로
  누락 시 `from modules import X` 전체가 무너진다 → 전수 재배선 필수.
- `from shared.X` 는 shared 의 **부모**가 path 에 있어야 한다(패키지 자신을 path 에 넣으면
  `import shared` 가 안 풀린다). 컨테이너=/app, 테스트=/work.
- `python script.py` 호출(eval runner)은 CWD 를 path 에 안 올리므로 PYTHONPATH 에 `/work` 명시 필요.

## 9. Error Handling
- import 실패는 빌드/테스트 단계에서 fail-loud(런타임 도달 전 차단).
- 롤백: 단일 commit revert 로 model_catalog 가 modules/ 로 복귀(이미지 태그 보존).

## 10. Dependencies
### 내부 기능 의존성
- feature-0002-agent-core (modules/ 원본), feature-0003-agent-web-ui (app.py import 측).

### 외부 의존성
- 없음 (model_catalog 은 순수 stdlib: os, typing).

### shared 모듈 의존성
- shared.model_catalog (Step 1) · shared.config (Step 2) · shared.db (Step 3) ·
  shared.conn_health · shared.datasources (Step 4).
- back-dep: shared.datasources → modules.cred_crypto (cred_crypto 미추출, stdlib-only·cycle 없음).
- 내부 lazy 상호참조: db ↔ datasources ↔ conn_health (전부 함수내부 lazy → import-time cycle 0).

## 11. Acceptance Criteria
- AC-0001: `from shared.model_catalog import ...` 가 두 feature 와 컨테이너(/app)에서 해석된다.
- AC-0002: `make test` 가 본 변경 도입 전후로 **동일한 결과**(회귀 0; 기존 baseline 실패만 잔존)를 낸다.
- AC-0003: live 코드에 `from modules.model_catalog`/`from .model_catalog` 잔여 0.

## 12. Observability
- `make test` 통과/실패 카운트(회귀 판정 기준).
- 프로덕션 import smoke: 컨테이너 `/app` 에서 `from shared.model_catalog` + `import modules.llm` 성공.

## 13. Pre-approved Changes
- P5a Step 1~4 (model_catalog·config·db·conn_health/datasources): 사용자 승인(P5a/P5b 진행, 2026-06-24 PLAN-APPROVED).
- deploy_scope: included (프로젝트 전역 standing — 머지 후 자동 배포 + 첫 배포 1줄 표면화).
