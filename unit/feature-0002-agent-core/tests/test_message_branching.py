"""feature-0019 message-editing — 코어 recall 로더/쓰기 primitive 브랜치 라우팅 회귀 테스트.

가장 큰 blast radius(모든 ask 의 문맥 진입점 `load_core_messages` + 쓰기 choke-point
`save_core_message`)를 DB 없이 fake cursor 로 가드한다. 핵심 불변식:

  INV-1 (AC-ME-2): 분기 없는 대화(active_leaf_id=None) 는 기존 쿼리 그대로 —
    비-windowed → _PG_LOAD_CORE_MESSAGES, windowed → _PG_LOAD_CORE_MESSAGES_WINDOWED.
    브랜치 인자 없는 정상 append 는 _PG_INSERT_CORE_MESSAGE(byte-identical, 회귀 0).
  브랜치 활성(active_leaf_id 지정) → active-path CTE(_PG_LOAD_CORE_MESSAGES_BRANCH),
    window 술어 params 합성. 브랜치 append → _PG_INSERT_CORE_MESSAGE_BRANCH.

`make test`(agent 이미지)에서 DB 없이 실행된다.
"""
from __future__ import annotations

from modules import runtime_backend as rb


class _FakeCursor:
    def __init__(self, fetchone=None, fetchall=None, raise_on_execute=None):
        self.executed: list[str] = []
        self.params: list = []
        self._fetchone = fetchone
        self._fetchall = fetchall or []
        self._raise = raise_on_execute

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append(sql)
        self.params.append(params)
        if self._raise is not None:
            raise self._raise
        return None

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return list(self._fetchall)


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def _backend():
    return rb.PgRuntimeBackend()


# ─────────────────────────────────────────────────────────────────────────────
# load_core_messages — 쿼리 라우팅 (INV-1 항등성)
# ─────────────────────────────────────────────────────────────────────────────

def test_load_core_messages_nonbranched_nonwindowed_uses_existing_query():
    cur = _FakeCursor(fetchall=[("user", "hi", None, None, None, None)])
    _backend().load_core_messages(_FakeConn(cur), conversation_id="c1", limit=50)
    assert cur.executed == [rb._PG_LOAD_CORE_MESSAGES]  # 기존 쿼리 그대로 (회귀 0)


def test_load_core_messages_windowed_uses_windowed_query():
    cur = _FakeCursor(fetchall=[])
    _backend().load_core_messages(
        _FakeConn(cur), conversation_id="c1", limit=50, floor_ca="2026-01-01"
    )
    assert cur.executed == [rb._PG_LOAD_CORE_MESSAGES_WINDOWED]


def test_load_core_messages_branch_uses_active_path_cte():
    cur = _FakeCursor(fetchall=[])
    _backend().load_core_messages(
        _FakeConn(cur), conversation_id="c1", limit=50, use_branch=True, active_leaf_id=42
    )
    assert cur.executed == [rb._PG_LOAD_CORE_MESSAGES_BRANCH]
    assert cur.params[0]["active_leaf_id"] == 42
    # window 술어 params 가 (비-windowed 여도) 합성돼 있어야 CTE 가 실행됨
    assert "floor_ca" in cur.params[0] and "ceil_ca" in cur.params[0]


def test_load_core_messages_branch_null_leaf_still_uses_cte_empty_anchor():
    # 첫 메시지 편집 전이 window: has_branches=true 이나 active_leaf=None → CTE(anchor 없음=empty).
    cur = _FakeCursor(fetchall=[])
    _backend().load_core_messages(
        _FakeConn(cur), conversation_id="c1", limit=50, use_branch=True, active_leaf_id=None
    )
    assert cur.executed == [rb._PG_LOAD_CORE_MESSAGES_BRANCH]
    assert cur.params[0]["active_leaf_id"] is None


def test_load_core_messages_branch_composes_window_predicates():
    cur = _FakeCursor(fetchall=[])
    _backend().load_core_messages(
        _FakeConn(cur), conversation_id="c1", limit=50, use_branch=True,
        active_leaf_id=42, floor_ca="2026-01-01", ceil_ca="2026-02-01", joined_ca="2026-01-15",
    )
    assert cur.executed == [rb._PG_LOAD_CORE_MESSAGES_BRANCH]
    p = cur.params[0]
    assert p["floor_ca"] == "2026-01-01" and p["ceil_ca"] == "2026-02-01" and p["joined_ca"] == "2026-01-15"


# ─────────────────────────────────────────────────────────────────────────────
# load_branch_state — 게이트 상태 파싱 + fail-safe 기본값
# ─────────────────────────────────────────────────────────────────────────────

def test_load_branch_state_parses_row():
    cur = _FakeCursor(fetchone=(True, 99))
    out = _backend().load_branch_state(_FakeConn(cur), conversation_id="c1")
    assert out == {"has_branches": True, "active_leaf_id": 99}


def test_load_branch_state_missing_row_defaults_nonbranched():
    cur = _FakeCursor(fetchone=None)
    out = _backend().load_branch_state(_FakeConn(cur), conversation_id="c1")
    assert out == {"has_branches": False, "active_leaf_id": None}


def test_load_branch_state_premigration_column_absent_defaults_nonbranched():
    exc = Exception("undefined column")
    exc.sqlstate = "42703"  # UndefinedColumn (pre-migration)
    cur = _FakeCursor(raise_on_execute=exc)
    out = _backend().load_branch_state(_FakeConn(cur), conversation_id="c1")
    assert out == {"has_branches": False, "active_leaf_id": None}


# ─────────────────────────────────────────────────────────────────────────────
# save_core_message — INSERT 라우팅 (INV-1 항등성)
# ─────────────────────────────────────────────────────────────────────────────

def test_save_core_message_nonbranch_uses_existing_insert():
    cur = _FakeCursor(fetchone=(7,))
    new_id = _backend().save_core_message(
        _FakeConn(cur), conversation_id="c1", role="user", content="hi"
    )
    assert new_id == 7
    assert cur.executed == [rb._PG_INSERT_CORE_MESSAGE]  # byte-identical 경로


def test_save_core_message_with_parent_uses_branch_insert():
    cur = _FakeCursor(fetchone=(8,))
    new_id = _backend().save_core_message(
        _FakeConn(cur), conversation_id="c1", role="assistant", content="a",
        parent_message_id=42,
    )
    assert new_id == 8
    assert cur.executed == [rb._PG_INSERT_CORE_MESSAGE_BRANCH]
    assert cur.params[0]["parent_message_id"] == 42


def test_save_core_message_with_edit_version_uses_branch_insert():
    cur = _FakeCursor(fetchone=(9,))
    _backend().save_core_message(
        _FakeConn(cur), conversation_id="c1", role="user", content="edited",
        edit_root_message_id=5, edit_version=2,
    )
    assert cur.executed == [rb._PG_INSERT_CORE_MESSAGE_BRANCH]
    assert cur.params[0]["edit_root_message_id"] == 5 and cur.params[0]["edit_version"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 표시 store(messages) 쓰기 라우팅 (INV-1 항등성 + 브랜치)
# ─────────────────────────────────────────────────────────────────────────────

def test_save_memory_message_nonbranch_uses_existing_insert():
    cur = _FakeCursor(fetchone=(11,))
    new_id = _backend().save_memory_message(
        _FakeConn(cur), conversation_id="c1", role="user", content="hi"
    )
    assert new_id == 11
    assert cur.executed == [rb._PG_INSERT_MEMORY_MESSAGE]  # byte-identical 경로 + RETURNING id


def test_save_memory_message_with_parent_uses_branch_insert():
    cur = _FakeCursor(fetchone=(12,))
    _backend().save_memory_message(
        _FakeConn(cur), conversation_id="c1", role="assistant", content="a", parent_message_id=7
    )
    assert cur.executed == [rb._PG_INSERT_MEMORY_MESSAGE_BRANCH]
    assert cur.params[0]["parent_message_id"] == 7


def test_save_memory_message_with_core_link_uses_branch_insert():
    cur = _FakeCursor(fetchone=(13,))
    _backend().save_memory_message(
        _FakeConn(cur), conversation_id="c1", role="user", content="edited",
        edit_root_message_id=3, edit_version=2, core_message_id=99,
    )
    assert cur.executed == [rb._PG_INSERT_MEMORY_MESSAGE_BRANCH]
    assert cur.params[0]["core_message_id"] == 99 and cur.params[0]["edit_version"] == 2


def test_load_display_branch_state_parses_and_defaults():
    cur = _FakeCursor(fetchone=(True, 88))
    assert _backend().load_display_branch_state(_FakeConn(cur), conversation_id="c1") == {
        "has_branches": True, "active_leaf_id": 88
    }
    cur2 = _FakeCursor(fetchone=None)
    assert _backend().load_display_branch_state(_FakeConn(cur2), conversation_id="c1") == {
        "has_branches": False, "active_leaf_id": None
    }
