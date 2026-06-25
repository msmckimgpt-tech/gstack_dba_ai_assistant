"""group_members 차단(ban) 헬퍼 단위 테스트 — feature-0009 member-kick-ban.

실 PG 없이 FakeConn 으로 SQL 계약 + 반환 파싱 + 멱등성을 회귀 고정한다. 핵심 불변식:
  - ban_member 는 ON CONFLICT DO UPDATE (재차단 시 banned_at/by/reason 갱신, 멱등).
  - reason 은 512자 cap, None 허용.
  - unban_member 는 rowcount 반환(0=차단 아니었음).
  - is_banned 는 row 존재 여부 + 빈 cid/account_id 단락.
  - list_bans 는 banned_at isoformat + dict 직렬화.
  - 모든 SQL 은 agent_runtime.conversation_member_bans schema-qualified (ADR-0027).
"""
from __future__ import annotations

import datetime

import modules.group_members as gm


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return self.conn.one_results.pop(0) if self.conn.one_results else None

    def fetchall(self):
        return self.conn.all_results.pop(0) if self.conn.all_results else []

    @property
    def rowcount(self):
        return self.conn.rowcount


class FakeConn:
    def __init__(self, one_results=None, all_results=None, rowcount=0):
        self.executed = []
        self.one_results = list(one_results or [])
        self.all_results = list(all_results or [])
        self.rowcount = rowcount
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def last_sql(self):
        return self.executed[-1][0]

    def last_params(self):
        return self.executed[-1][1]


# ── schema-qualified 불변식 (ADR-0027) ────────────────────────────────────
def test_ban_sql_is_agent_runtime_schema_qualified():
    for name in ("_PG_BAN_MEMBER", "_PG_UNBAN_MEMBER", "_PG_IS_BANNED", "_PG_LIST_BANS"):
        sql = getattr(gm, name)
        assert "agent_runtime.conversation_member_bans" in sql, name


# ── ban_member: 멱등 upsert + 파라미터 + reason cap ──────────────────────────
def test_ban_member_upserts_and_commits():
    conn = FakeConn()
    gm.ban_member(conn, "conv-1", 10, banned_by_account_id=3, reason="spam")
    sql = conn.last_sql()
    assert "INSERT INTO agent_runtime.conversation_member_bans" in sql
    assert "ON CONFLICT (conversation_id, account_id) DO UPDATE" in sql
    p = conn.last_params()
    assert p["conversation_id"] == "conv-1"
    assert p["account_id"] == 10
    assert p["banned_by_account_id"] == 3
    assert p["reason"] == "spam"
    assert conn.commits == 1


def test_ban_member_reason_none_and_capped():
    conn = FakeConn()
    gm.ban_member(conn, "conv-1", 10, banned_by_account_id=None, reason=None)
    assert conn.last_params()["reason"] is None
    assert conn.last_params()["banned_by_account_id"] is None
    conn2 = FakeConn()
    gm.ban_member(conn2, "conv-1", 10, reason="x" * 1000)
    assert len(conn2.last_params()["reason"]) == 512  # 512자 cap


# ── unban_member: rowcount ──────────────────────────────────────────────────
def test_unban_member_returns_rowcount():
    conn = FakeConn(rowcount=1)
    assert gm.unban_member(conn, "conv-1", 10) == 1
    assert "DELETE FROM agent_runtime.conversation_member_bans" in conn.last_sql()
    assert conn.commits == 1
    conn2 = FakeConn(rowcount=0)
    assert gm.unban_member(conn2, "conv-1", 99) == 0  # 차단 아니었음


# ── is_banned: row 유무 + 빈 인자 단락 ──────────────────────────────────────
def test_is_banned_true_false():
    conn = FakeConn(one_results=[(1,), None])
    assert gm.is_banned(conn, "conv-1", 10) is True
    assert gm.is_banned(conn, "conv-1", 99) is False


def test_is_banned_short_circuits_on_empty():
    conn = FakeConn()
    assert gm.is_banned(conn, "", 10) is False
    assert gm.is_banned(conn, "conv-1", 0) is False
    assert conn.executed == []  # 빈 인자면 SQL 미실행


# ── list_bans: isoformat + dict 직렬화 ──────────────────────────────────────
def test_list_bans_serializes_rows():
    ts = datetime.datetime(2026, 6, 25, 1, 2, 3)
    conn = FakeConn(all_results=[[(10, ts, 3, "spam"), (22, ts, None, None)]])
    out = gm.list_bans(conn, "conv-1")
    assert out[0] == {
        "account_id": 10,
        "banned_at": ts.isoformat(),
        "banned_by_account_id": 3,
        "reason": "spam",
    }
    assert out[1]["account_id"] == 22
    assert out[1]["banned_by_account_id"] is None
    assert out[1]["reason"] is None
    assert conn.last_params() == {"conversation_id": "conv-1"}


def test_list_bans_orders_by_banned_at_desc():
    assert "ORDER BY banned_at DESC" in gm._PG_LIST_BANS
