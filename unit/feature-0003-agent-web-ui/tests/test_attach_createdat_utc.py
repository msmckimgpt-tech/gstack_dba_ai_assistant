"""REQ-20260814-attach-createdat-utc — 첨부 CreatedAt 의 UTC 정합 계약.

배경(라이브 실측 2026-08-14): `WebConversationAttachments.CreatedAt` 이 `DEFAULT CURRENT_TIMESTAMP(6)`
라 세션 TZ(`time_zone=SYSTEM` = KST)의 **로컬 시각**을 담았다. 같은 테이블의 SupersededAt/DeletedAt 은
코드가 `UTC_TIMESTAMP(6)` 로 넣고 메시지 저장도 UTC 라 축이 갈렸다 — `CreatedAt > SupersededAt` 97건 ·
`CreatedAt > DeletedAt` 137건의 **논리적 모순 행**이 실제로 쌓였다.

**이 backfill 의 재실행은 데이터를 더 망가뜨린다**(차감이 누적된다). §18.8 적대 리뷰가 세 경로를
짚었고([P1] 동시 startup 경쟁 · 상한을 ALTER 뒤에 읽는 창 · 저장소별 완료 상태 부재), 그 셋이 여기서
고정하는 계약의 중심이다.
"""
from __future__ import annotations

import web_context


class _Cur:
    def __init__(self, conn):
        self._conn = conn
        self.rowcount = 0
        self._result = None

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        self._conn.sink.append((s, params))
        if s in self._conn.fail_on or any(f in s for f in self._conn.fail_on):
            raise RuntimeError("forced failure")
        # 선점(claim)은 INSERT IGNORE 의 rowcount 로 판정된다.
        if "INSERT IGNORE INTO WebSchemaMigrations" in s:
            key = (params or (None,))[0]
            self.rowcount = 0 if key in self._conn.taken else 1
            self._conn.taken.add(key)
            return
        self.rowcount = 0
        for frag, val in self._conn.scripted.items():
            if frag in s:
                self._result = val
                return
        self._result = None

    def fetchone(self):
        return self._result

    def close(self):
        pass


class _Conn:
    """execute 를 기록하는 fake. `taken` 에 든 마커 키는 이미 선점된 것으로 취급."""

    def __init__(self, *, offset=32400, max_id=1149, taken=None, fail_on=()):
        self.sink: list = []
        self.taken: set = set(taken or ())
        self.fail_on = tuple(fail_on)
        self.scripted = {
            "TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), NOW())": (offset,),
            "COALESCE(MAX(Id), 0) FROM WebConversationAttachments": (max_id,),
        }

    def cursor(self, *a, **k):
        return _Cur(self)

    def commit(self):
        pass


def _sqls(conn) -> list[str]:
    return [s for s, _ in conn.sink]


def _has(conn, frag) -> bool:
    return any(frag in s for s in _sqls(conn))


_MYSQL_KEY = web_context._ATTACH_CREATEDAT_UTC_MIGRATION_KEY
_PG_KEY = web_context._ATTACH_CREATEDAT_UTC_PG_MIGRATION_KEY


# ── 선점(claim) — 동시 startup 경쟁 차단 ───────────────────────────────────

def test_claim_is_atomic_insert_not_select_check():
    """선점은 INSERT 의 원자성으로 한다 — SELECT 확인은 다중 replica 에서 이중 실행을 못 막는다.

    §18.8 [P1]: web-a/web-b 가 동시에 '마커 없음' 을 보면 **둘 다** 차감한 뒤 INSERT IGNORE 에
    도달한다. 두 번째 INSERT 가 무시돼도 두 번째 9시간 차감은 이미 끝난 뒤다.
    """
    conn = _Conn()
    assert web_context._claim_migration_once(conn, "k") is True
    assert _has(conn, "INSERT IGNORE INTO WebSchemaMigrations")
    # 같은 키를 다시 잡으려 하면 실패(이미 선점됨)
    assert web_context._claim_migration_once(conn, "k") is False


def test_second_replica_does_not_run_update():
    """이미 선점된 마이그레이션은 UPDATE 를 실행하지 않는다."""
    conn = _Conn(taken={_MYSQL_KEY, _PG_KEY})
    web_context._backfill_attachment_created_at_utc_v1(conn)
    assert not _has(conn, "UPDATE WebConversationAttachments")
    assert not _has(conn, "ALTER COLUMN CreatedAt SET DEFAULT")


def test_claim_failure_means_no_work():
    """선점 자체가 실패(DB 오류)하면 수행하지 않는다 — 확인 없는 실행은 재차감 위험."""
    conn = _Conn(fail_on=("INSERT IGNORE INTO WebSchemaMigrations",))
    web_context._backfill_attachment_created_at_utc_v1(conn)
    assert not _has(conn, "UPDATE WebConversationAttachments")


def test_failed_backfill_releases_the_claim():
    """작업이 실패하면 선점을 **반납**한다 — 반납하지 않으면 영영 재시도되지 않는다."""
    conn = _Conn(fail_on=("ALTER COLUMN CreatedAt SET DEFAULT",))
    web_context._backfill_attachment_created_at_utc_v1(conn)
    assert _has(conn, "DELETE FROM WebSchemaMigrations")
    assert not _has(conn, "UPDATE WebConversationAttachments")


# ── 대상 선정 ──────────────────────────────────────────────────────────────

def test_bound_is_read_before_the_default_switch():
    """**[P1]** 상한은 DEFAULT 전환 **이전에** 확정한다.

    ALTER 뒤에 `MAX(Id)` 를 읽으면 그 사이 들어온 **이미 UTC 인** 행이 상한 안에 들어와 또 차감된다.
    순서를 뒤집으면 남는 위험은 "그 창의 로컬 행이 미보정으로 남는 것" 뿐이라 방향이 안전하다.
    """
    conn = _Conn()
    web_context._backfill_attachment_created_at_utc_v1(conn)
    sqls = _sqls(conn)
    max_i = next(i for i, s in enumerate(sqls) if "COALESCE(MAX(Id), 0)" in s)
    alter_i = next(i for i, s in enumerate(sqls) if "ALTER COLUMN CreatedAt SET DEFAULT" in s)
    assert max_i < alter_i, "상한을 ALTER 뒤에 읽으면 신규 UTC 행이 차감된다"


def test_update_is_bounded_and_uses_server_offset():
    """보정은 Id 상한 이하로만, 오프셋은 서버에서 구한 값으로."""
    conn = _Conn(offset=19800, max_id=77)  # +05:30 배포 가정
    web_context._backfill_attachment_created_at_utc_v1(conn)
    upd = [(s, p) for s, p in conn.sink if "UPDATE WebConversationAttachments" in s]
    assert len(upd) == 1
    sql, params = upd[0]
    assert "WHERE Id <= %s" in sql
    assert params == (19800, 77), "9시간 하드코딩이면 TZ 다른 배포에서 조용히 틀린다"


def test_utc_server_switches_default_but_skips_update():
    """이미 UTC 서버(offset=0)면 0을 빼려고 전 행을 건드리지 않는다. DEFAULT 전환은 그대로 수행."""
    conn = _Conn(offset=0)
    web_context._backfill_attachment_created_at_utc_v1(conn)
    assert _has(conn, "ALTER COLUMN CreatedAt SET DEFAULT")
    assert not _has(conn, "UPDATE WebConversationAttachments")


def test_empty_table_skips_update():
    conn = _Conn(max_id=0)
    web_context._backfill_attachment_created_at_utc_v1(conn)
    assert not _has(conn, "UPDATE WebConversationAttachments")


# ── 저장소별 완료 상태 ─────────────────────────────────────────────────────

def test_mysql_and_pg_have_separate_claims():
    """**[P1]** MySQL 과 PG 는 한 트랜잭션이 아니므로 마커를 분리한다.

    하나의 마커로 둘을 대표하면 "MySQL 성공 + PG 실패" 가 PG 를 영구 미보정으로 두거나(마커 기록)
    MySQL 을 재차감한다(마커 미기록). 둘 다 틀리다.
    """
    assert _MYSQL_KEY != _PG_KEY
    conn = _Conn()
    web_context._backfill_attachment_created_at_utc_v1(conn)
    claimed = [p[0] for s, p in conn.sink if "INSERT IGNORE INTO WebSchemaMigrations" in s]
    assert _MYSQL_KEY in claimed and _PG_KEY in claimed


def test_pg_claim_skipped_when_nothing_to_correct():
    """보정할 것이 없으면(offset=0) PG 선점도 하지 않는다 — 빈 작업에 마커를 소모하지 않는다."""
    conn = _Conn(offset=0)
    web_context._backfill_attachment_created_at_utc_v1(conn)
    claimed = [p[0] for s, p in conn.sink if "INSERT IGNORE INTO WebSchemaMigrations" in s]
    assert _PG_KEY not in claimed


# ── 전송 계약 (표시 회귀 방지) ─────────────────────────────────────────────

def test_api_marks_created_at_as_utc():
    """**[P2]** 저장 축을 옮겼으면 전송 표기도 옮겨야 한다.

    오프셋 없는 문자열을 브라우저 `new Date()` 가 로컬로 읽어 9시간 이르게 표시하던 회귀를 막는다.
    """
    import datetime as _dt

    import app
    naive = _dt.datetime(2026, 8, 13, 9, 20, 0)
    assert app._iso_utc_z(naive) == "2026-08-13T09:20:00Z"
    aware = _dt.datetime(2026, 8, 13, 9, 20, 0, tzinfo=_dt.timezone.utc)
    assert app._iso_utc_z(aware).endswith("+00:00"), "이미 오프셋이 있으면 Z 를 덧붙이지 않는다"
    assert app._iso_utc_z(None) is None
    assert app._iso_utc_z("not-a-datetime") is None


def test_schema_ddl_carries_utc_default():
    """스키마 보장 경로에도 같은 DEFAULT 가 있어야 한다(fresh install 정합)."""
    import inspect

    from routers import _bootstrap_schema

    src = inspect.getsource(_bootstrap_schema._ensure_attachment_version_schema)
    assert "ALTER COLUMN CreatedAt SET DEFAULT (UTC_TIMESTAMP(6))" in src
