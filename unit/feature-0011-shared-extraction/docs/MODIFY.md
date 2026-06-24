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
