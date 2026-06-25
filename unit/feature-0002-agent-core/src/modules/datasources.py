"""modules.datasources — feature-0011 P5a Step 4: shared/datasources.py 의 모듈 alias shim.

datasources 는 P5a 위상정렬 L1(config 직접 의존 + db·conn_health 는 lazy, cred_crypto 는 back-dep).
정본을 shared/datasources.py 로 이동(config·db 선이동 덕에 `from . import config`/lazy `from . import db`
는 shared.*; cred_crypto 는 아직 modules/ 라 `from modules import cred_crypto` back-dep — cred_crypto 는
stdlib 만 의존해 cycle 없음). config·db·conn_health(Step 2~4)와 동일하게 `modules.datasources` 를
`shared.datasources` 의 **모듈 alias** 로 만든다 (sys.modules 치환).

왜 alias 인가 (config·db 와 동일 사유):
  - datasources 는 `from modules import datasources`(app·agent_core·insight·ask·tests) /
    `import modules.datasources as dsr`(tests) 로 모듈객체 접근되고, `scope_key`·`resolve` 등 다수
    심볼과 `_DEK_CACHE`/`_CONFLICT_WARNED` 등 underscore 모듈 상태가 외부에서 참조·monkeypatch 된다.
  - alias 는 `modules.datasources` 와 `shared.datasources` 를 *동일 모듈 객체* 로 만들어 모든 심볼
    자동 노출 + DEK 캐시 단일 상태를 양 import 경로에서 동일 객체로 보존한다.

db↔datasources 상호참조: shared/db.py 가 lazy `from shared import datasources`(Step 4 정리),
datasources 가 lazy `from . import db`(=shared.db) — 둘 다 함수 내부라 import-time cycle 없음.
후속 step 에서 importer 가 shared.datasources 로 마이그레이션되면 본 shim 제거.
"""
import sys

import shared.datasources as _shared_datasources

# `modules.datasources` 를 `shared.datasources` 와 동일 객체로 치환 — 완전 alias.
sys.modules[__name__] = _shared_datasources
