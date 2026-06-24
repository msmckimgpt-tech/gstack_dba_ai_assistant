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
저결합 공통 코드를 repo 루트 `shared/` Python 패키지로 점진 추출한다. 첫 단계(P5a Step 1)는
db.py 같은 고결합 모듈을 옮기기 전에 **저결합 모듈 하나(`model_catalog`)로 shared/ 플러밍을
test-gated 로 증명**하는 것이다.

## 2. Goal
- REQ-001: repo 루트 `shared/` 를 import 가능한 Python 패키지로 확립(`__init__.py`).
- REQ-002: 저결합 공통 모듈 1개를 `modules/` → `shared/` 로 이동하고 모든 import 사이트를 재배선.
- REQ-003: 컨테이너(Dockerfile)와 `make test`/eval(PYTHONPATH)이 `shared` 를 양 feature 에서
  import 가능하게 배선하고, `make test` 회귀 0 으로 증명.

## 3. In Scope
- `shared/__init__.py` 패키지 골격.
- `model_catalog.py` 를 `modules/` → `shared/` 로 git mv(history 보존).
- import 재배선: `from modules.model_catalog`/`from .model_catalog` → `from shared.model_catalog`
  (agent_core.py·app.py·modules/llm.py·tests/test_prompt_gen_max_tokens.py).
- Dockerfile: `COPY shared /app/shared`.
- Makefile: test/eval/kb-retrieval-eval PYTHONPATH 에 `/work`(shared 의 부모) 추가.

## 4. Out of Scope
- db.py 추출 + shim (P5a Step 2).
- import 점진 마이그레이션 + shim 제거 (Step 3).
- config/memory/llm 등 추가 공통 모듈 (Step 4).
- feature 단위 Dockerfile 분리 (Step 5).
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
- shared.model_catalog (본 cycle 신규).

## 11. Acceptance Criteria
- AC-0001: `from shared.model_catalog import ...` 가 두 feature 와 컨테이너(/app)에서 해석된다.
- AC-0002: `make test` 가 본 변경 도입 전후로 **동일한 결과**(회귀 0; 기존 baseline 실패만 잔존)를 낸다.
- AC-0003: live 코드에 `from modules.model_catalog`/`from .model_catalog` 잔여 0.

## 12. Observability
- `make test` 통과/실패 카운트(회귀 판정 기준).
- 프로덕션 import smoke: 컨테이너 `/app` 에서 `from shared.model_catalog` + `import modules.llm` 성공.

## 13. Pre-approved Changes
- P5a Step 1 (본 cycle): 사용자 승인(P5a/P5b 진행, 2026-06-24).
