"""modules.db — feature-0011 P5a Step 3: shared/db.py 의 모듈 alias shim.

db 는 P5a 위상정렬 L1(config 만 직접 의존; datasources·conn_health 는 lazy). 정본을
shared/db.py 로 이동(config-first 덕에 shared/db 의 `from .config import *` 가 shared.config 로
해석). config(Step 2)와 동일하게 `modules.db` 를 `shared.db` 의 **모듈 alias** 로 만든다
(sys.modules 치환).

왜 alias 인가 (config 와 동일 사유):
  - db 는 `from . import db as _db`(insight·datasources·conn_health) / `import modules.db as _dbmod`
    (tests) 로 모듈객체 접근되고, `_pg_connect`·`_pg_connect_ro`·`_pg_available`·`_pg_check_kb_invalidation`
    등 underscore 심볼 9+개가 외부 import 된다. AnnAssign(`_POOL_REGISTRY`)도 있어 enumeration 은 fragile.
  - alias 는 `modules.db` 와 `shared.db` 를 동일 객체로 만들어 30개 top-level 심볼·__all__(15)·
    `from .db import *`(__init__)·monkeypatch·db 가 `from .config import *` 로 재노출하는 config 심볼
    (`from modules.db import AGENT_KB_PG_PORT`)을 전부 무파손 보존한다.

전이적 back-dep: shared/db.py 의 lazy `from modules import datasources/conn_health`(아직 modules/) 는
함수 내부라 import-time cycle 없음. db↔conn_health 상호참조는 alias 로 db 단일객체 유지. Step 4 에서
datasources·conn_health 가 shared 로 이동하면 정리. 후속 step 에서 importer 가 shared.db 로
마이그레이션되면 본 shim 제거.
"""
import sys

import shared.db as _shared_db

# `modules.db` 를 `shared.db` 와 동일 객체로 치환 — 완전 alias.
sys.modules[__name__] = _shared_db
