"""pytest conftest — KB Postgres unit test 의 import path 통일.

outside-voice REV-20260520-0008 Critical (Test isolation) 흡수: 본 모듈이 module-level
에서 `unit/feature-0002-agent-core/src` path 를 sys.path 에 1회 추가. 각 test 가
별도 sys.path.insert 호출 안 함 → dual import path / sys.modules contamination 회피.
"""

import os
import sys

# `src/modules/*` 를 `modules.*` 로 import 할 수 있도록 path 추가.
_SRC_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# config.py 가 .env 의존성 보이도록 dummy env (test 환경).
os.environ.setdefault("DB_USER", "root")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("AGENT_MEMORY_DB", "agent_memory")
