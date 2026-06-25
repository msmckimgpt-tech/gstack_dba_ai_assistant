"""modules.conn_health — feature-0011 P5a Step 4: shared/conn_health.py 의 모듈 alias shim.

conn_health 는 P5a 위상정렬 L1(config 직접 의존 + datasources·db 는 lazy 상호참조). 정본을
shared/conn_health.py 로 이동(config-first·db 선이동 덕에 shared/conn_health 의 `from .config import *`
는 shared.config, lazy `from . import datasources/db` 는 shared.* 로 해석). config·db(Step 2/3)와
동일하게 `modules.conn_health` 를 `shared.conn_health` 의 **모듈 alias** 로 만든다 (sys.modules 치환).

왜 alias 인가 (config·db 와 동일 사유):
  - conn_health 는 `from . import conn_health`(insight·ask) / `from modules import conn_health`(app·tests) /
    `import modules.conn_health as ch`(tests) 로 모듈객체 접근되고, `_scope_key_of` 등 underscore 심볼과
    `should_fast_fail`·`record_foreground_result`·`start_monitor` 등 다수 심볼이 외부에서 참조된다.
  - alias 는 `modules.conn_health` 와 `shared.conn_health` 를 *동일 모듈 객체* 로 만들어 모든 심볼
    자동 노출 + 백그라운드 모니터 단일 상태(_targets/snapshot)를 양 import 경로에서 동일 객체로 보존한다.

db↔conn_health 상호참조: shared/db.py 가 lazy `from shared import conn_health`(Step 4 정리), conn_health 가
lazy `from . import db`(=shared.db) — 둘 다 함수 내부라 import-time cycle 없음. 후속 step 에서 importer 가
shared.conn_health 로 마이그레이션되면 본 shim 제거.
"""
import sys

import shared.conn_health as _shared_conn_health

# `modules.conn_health` 를 `shared.conn_health` 와 동일 객체로 치환 — 완전 alias.
sys.modules[__name__] = _shared_conn_health
