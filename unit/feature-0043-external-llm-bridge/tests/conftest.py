"""feature-0043 tests — import path 통일.

이 feature 의 게이트는 `shared/` 에 살지만 배선 검사 대상은 feature-0002(`modules.llm`,
`agent_core`) 안에 있다. 각 테스트가 개별로 `sys.path.insert` 하면 dual import path 로
`sys.modules` 가 오염되므로(feature-0002 conftest 와 동형 규약) 여기서 한 번만 추가한다.

⚠ **feature-0003 의 `src` 는 여기에 넣지 않는다.** 두 feature 모두 최상위 `modules` 패키지를
갖고 있어 path 에 함께 올리면 먼저 온 쪽이 다른 쪽을 통째로 가린다(`modules.memory`
ModuleNotFoundError). 배포본에서도 같은 충돌면이 있다(`/app/web/modules` vs `/app/modules`).
웹 라우터를 겨냥한 테스트는 `unit/feature-0003-agent-web-ui/tests/` 에 둔다.
"""

import os
import sys

_HERE = os.path.dirname(__file__)
_UNIT_DIR = os.path.normpath(os.path.join(_HERE, "..", ".."))

_src = os.path.normpath(os.path.join(_UNIT_DIR, "feature-0002-agent-core", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

# config.py 가 import 시점에 읽는 최소 env (테스트 환경 — 값 자체는 쓰이지 않는다).
os.environ.setdefault("DB_USER", "root")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("AGENT_MEMORY_DB", "agent_memory")
