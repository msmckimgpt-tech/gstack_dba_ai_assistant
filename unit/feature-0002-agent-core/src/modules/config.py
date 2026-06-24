"""modules.config — feature-0011 P5a Step 2: shared/config.py 의 모듈 alias shim.

config 는 P5a 위상정렬상 L0 foundation(내부의존 0·fan-in 25). 정본을 shared/config.py 로
이동하고, 기존 import 경로를 100% 무파손 보존하기 위해 `modules.config` 를 `shared.config` 의
**모듈 alias** 로 만든다 (sys.modules 치환).

왜 enumeration 재노출이 아니라 alias 인가:
  - config 는 `import modules.config as cfg; cfg.X` 모듈객체로 다수 접근되고, 테스트는
    `_c._ACTIVE_DEFAULT_DB.set(...)` / `_c.FLAG = ...` 로 monkeypatch 한다. 심볼을 다른
    namespace 로 복사하면 (a) 271+ 심볼(public·underscore·annotated assignment 포함)을
    하나라도 빠뜨리면 AttributeError, (b) scalar monkeypatch 가 정본에 반영 안 됨.
  - alias 는 `modules.config` 와 `shared.config` 를 *동일 모듈 객체* 로 만들어 두 문제를
    원천 제거한다 — 모든 심볼 자동 노출 + monkeypatch 가 정본과 같은 객체에 적용.

보존되는 경로: `from modules.config import X` · `from .config import *`(16개 내부 모듈) ·
`import modules.config as cfg; cfg.X` · monkeypatch · db 의 `from .config import *` 경유
재노출 체인(`from modules.db import AGENT_KB_PG_PORT` 등). 후속 step 에서 importer 가
shared.config 로 마이그레이션되면 본 shim 제거 예정.
"""
import sys

import shared.config as _shared_config

# `modules.config` 를 `shared.config` 와 동일 객체로 치환 — 완전 alias.
sys.modules[__name__] = _shared_config
