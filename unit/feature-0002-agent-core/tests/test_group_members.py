"""group_members 멤버십 헬퍼 단위 테스트 — feature-0009-group-conversation (S1).

실 PG 없이(make test 는 --no-deps) FakeConn 으로 SQL 계약 + 반환 파싱 + 멱등성/검증을
회귀 고정한다. 핵심 불변식:
  - backfill 은 ON CONFLICT DO NOTHING (멱등) + owner_account_id IS NOT NULL 만.
  - add_member 는 ON CONFLICT DO UPDATE (role 갱신) + role 화이트리스트 검증.
  - 모든 SQL 은 agent_runtime. schema-qualified (ADR-0027).
"""
from __future__ import annotations

import pytest

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
def test_all_sql_is_agent_runtime_schema_qualified():
    for name in (
        "_PG_BACKFILL_MEMBERS",
        "_PG_LIST_MEMBER_ACCOUNT_IDS",
        "_PG_MEMBER_ROLE",
        "_PG_ADD_MEMBER",
        "_PG_REMOVE_MEMBER",
    ):
        sql = getattr(gm, name)
        assert "agent_runtime.conversation_members" in sql, name


# ── backfill: 멱등 + owner 한정 ───────────────────────────────────────────
def test_backfill_is_idempotent_and_owner_scoped():
    sql = gm._PG_BACKFILL_MEMBERS.upper()
    assert "ON CONFLICT (CONVERSATION_ID, ACCOUNT_ID) DO NOTHING" in sql
    assert "OWNER_ACCOUNT_ID IS NOT NULL" in sql
    assert "'OWNER'" in sql


def test_backfill_returns_inserted_count_and_commits():
    conn = FakeConn(rowcount=5)
    inserted = gm.backfill_conversation_members(conn)
    assert inserted == 5
    assert conn.commits == 1
    assert "INSERT INTO agent_runtime.conversation_members" in conn.last_sql()


def test_backfill_negative_rowcount_coerced_to_zero():
    conn = FakeConn(rowcount=-1)  # 일부 드라이버가 -1 반환
    assert gm.backfill_conversation_members(conn) == 0


# ── read helpers ──────────────────────────────────────────────────────────
def test_list_member_account_ids_parses_ints_in_order():
    conn = FakeConn(all_results=[[(10,), (22,), (7,)]])
    assert gm.list_member_account_ids(conn, "conv-1") == [10, 22, 7]
    assert conn.last_params() == {"conversation_id": "conv-1"}


def test_account_member_role_returns_role_or_none():
    conn = FakeConn(one_results=[("owner",), None])
    assert gm.account_member_role(conn, "conv-1", 10) == "owner"
    assert gm.account_member_role(conn, "conv-1", 99) is None


def test_is_member_true_false():
    conn = FakeConn(one_results=[("member",), None])
    assert gm.is_member(conn, "conv-1", 10) is True
    assert gm.is_member(conn, "conv-1", 99) is False


# ── add/remove ────────────────────────────────────────────────────────────
def test_add_member_rejects_invalid_role():
    conn = FakeConn()
    with pytest.raises(ValueError):
        gm.add_member(conn, "conv-1", 10, role="admin")
    assert conn.executed == []  # 검증 실패 시 SQL 실행 안 함


def test_add_member_upserts_role_and_commits():
    conn = FakeConn()
    gm.add_member(conn, "conv-1", 10, role="member", invited_by_account_id=3)
    assert "ON CONFLICT (conversation_id, account_id) DO UPDATE" in conn.last_sql()
    assert conn.last_params() == {
        "conversation_id": "conv-1",
        # gc-join-ambiguous-param-fix: 서브쿼리 비교용 별도 키(값은 동일).
        "conversation_id_lookup": "conv-1",
        "account_id": 10,
        "role": "member",
        "invited_by_account_id": 3,
    }
    assert conn.commits == 1


# ── gc-join-ambiguous-param-fix 회귀 고정 ──────────────────────────────────
# 회귀: _PG_ADD_MEMBER 가 INSERT VALUES(varchar 컬럼)와 서브쿼리(`WHERE ... = `, text
# 추론) 양쪽에서 동일 named param `%(conversation_id)s` 를 재사용하면, psycopg3 가 둘을
# 같은 $1 로 합쳐 보내 "AmbiguousParameter: text versus character varying" 로 INSERT
# 전체가 실패 → 공유 대화 join 불가. 두 위치는 반드시 서로 다른 named param 이어야 한다.
def test_add_member_subquery_uses_distinct_param_name():
    sql = gm._PG_ADD_MEMBER
    # last_read 서브쿼리(회귀 원천)가 존재하고 core_messages 를 조회한다.
    assert "agent_runtime.core_messages" in sql
    assert "last_read_message_id" in sql
    # INSERT VALUES 의 conversation_id 와 서브쿼리 비교는 서로 다른 placeholder.
    assert "%(conversation_id_lookup)s" in sql
    # `%(conversation_id)s` 는 정확히 1회(INSERT VALUES)만 — 서브쿼리는 _lookup 을 쓴다.
    # ('%(conversation_id_lookup)s' 와 겹세지 않도록 정규식으로 정확히 매칭.)
    import re
    exact = re.findall(r"%\(conversation_id\)s", sql)
    assert len(exact) == 1, f"conversation_id placeholder 는 1회여야 함(서브쿼리는 _lookup): {len(exact)}"
    lookup = re.findall(r"%\(conversation_id_lookup\)s", sql)
    assert len(lookup) == 1, f"conversation_id_lookup placeholder 는 1회여야 함: {len(lookup)}"


def test_add_member_lookup_param_equals_conversation_id():
    conn = FakeConn()
    gm.add_member(conn, "conv-xyz", 10, role="member")
    params = conn.last_params()
    # 두 키 모두 동일 conversation_id 값(서브쿼리가 같은 대화를 조회).
    assert params["conversation_id"] == "conv-xyz"
    assert params["conversation_id_lookup"] == "conv-xyz"


def test_remove_member_returns_rowcount():
    conn = FakeConn(rowcount=1)
    assert gm.remove_member(conn, "conv-1", 10) == 1
    conn2 = FakeConn(rowcount=0)
    assert gm.remove_member(conn2, "conv-1", 99) == 0
