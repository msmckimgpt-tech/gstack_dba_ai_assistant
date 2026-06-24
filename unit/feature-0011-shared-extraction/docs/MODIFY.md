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
