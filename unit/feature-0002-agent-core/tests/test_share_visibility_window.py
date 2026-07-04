"""share-visibility-window — recall 가시성 해석 · never-widen 각인 · owner-answer 태그 회귀.

`make test`(agent 이미지, --no-deps)에서 DB 없이 순수 함수/모의 커서로 실행된다.
검증 대상(SECURITY.md §21 정본):
  - agent_core._resolve_recall_visibility: fail-closed(PG 오류=DENY, pre-mig/owner/full/비멤버=None-필터없음).
  - agent_core._answer_recall_tag: owner-answer display-tag 규칙.
  - group_members.stamp_member_visibility: never-widen(신규=그대로, full 멤버 불변, windowed=교집합, owner 스킵).
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import agent_core  # noqa: E402
from modules import group_members, runtime_backend  # noqa: E402


# ── _answer_recall_tag ───────────────────────────────────────────────────────

def test_answer_tag_unrestricted_is_empty():
    assert agent_core._answer_recall_tag(None, has_restricted=False) == {}
    assert agent_core._answer_recall_tag({"floor_ca": _dt.datetime(2026, 1, 1)}, has_restricted=False) == {}


def test_answer_tag_bounded_sets_floor():
    fc = _dt.datetime(2026, 7, 4, 1, 2, 3)
    tag = agent_core._answer_recall_tag({"floor_ca": fc, "ceil_ca": None}, has_restricted=True)
    assert tag == {"recall_floor_created_at": fc.isoformat()}


def test_answer_tag_owner_full_is_recall_full():
    # restricted 대화의 owner/full(None visibility) → 전체 문맥 → 모든 bounded 뷰어에게 은닉.
    assert agent_core._answer_recall_tag(None, has_restricted=True) == {"recall_full": True}


def test_answer_tag_deny_is_empty_recall():
    assert agent_core._answer_recall_tag("DENY", has_restricted=True) == {"recall_empty": True}


def test_answer_tag_bounded_ceiling_only_no_floor_is_empty():
    # ceiling 만 있고 floor 없음 → 그린 문맥에 하단 은닉 없음.
    assert agent_core._answer_recall_tag({"floor_ca": None, "ceil_ca": _dt.datetime(2026, 1, 1)}, has_restricted=True) == {}


# ── _resolve_recall_visibility (monkeypatched runtime backend) ────────────────

def _patch_backend(monkeypatch, *, backend="postgres", res=None):
    monkeypatch.setattr(runtime_backend, "AGENT_RUNTIME_READ_BACKEND", backend, raising=False)
    monkeypatch.setattr(runtime_backend, "_read_runtime_pg", lambda *a, **k: res, raising=False)


def test_resolve_non_pg_is_none_no_restriction(monkeypatch):
    _patch_backend(monkeypatch, backend="mysql")
    assert agent_core._resolve_recall_visibility("c1", 7) == (None, False)


def test_resolve_pg_error_is_deny_failclosed(monkeypatch):
    _patch_backend(monkeypatch, res=None)  # _read_runtime_pg None = PG 오류/무연결
    assert agent_core._resolve_recall_visibility("c1", 7) == ("DENY", True)


def test_resolve_schema_missing_is_none(monkeypatch):
    _patch_backend(monkeypatch, res={"schema_missing": True})
    assert agent_core._resolve_recall_visibility("c1", 7) == (None, False)


def test_resolve_unrestricted_is_none(monkeypatch):
    _patch_backend(monkeypatch, res={"has_restricted": False, "role": None})
    assert agent_core._resolve_recall_visibility("c1", 7) == (None, False)


def test_resolve_owner_is_none_but_restricted(monkeypatch):
    _patch_backend(monkeypatch, res={"has_restricted": True, "role": "owner",
                                     "floor_ca": None, "ceil_ca": None, "joined_ca": None})
    assert agent_core._resolve_recall_visibility("c1", 7) == (None, True)


def test_resolve_full_member_is_none_but_restricted(monkeypatch):
    _patch_backend(monkeypatch, res={"has_restricted": True, "role": "member",
                                     "floor_ca": None, "ceil_ca": None, "joined_ca": None})
    assert agent_core._resolve_recall_visibility("c1", 7) == (None, True)


def test_resolve_bounded_member_returns_window(monkeypatch):
    fc = _dt.datetime(2026, 7, 4)
    jc = _dt.datetime(2026, 7, 4, 12)
    _patch_backend(monkeypatch, res={"has_restricted": True, "role": "member",
                                     "floor_ca": fc, "ceil_ca": None, "joined_ca": jc})
    vis, restricted = agent_core._resolve_recall_visibility("c1", 7)
    assert restricted is True
    assert vis == {"floor_ca": fc, "ceil_ca": None, "joined_ca": jc}


# ── group_members.stamp_member_visibility (fake pg_conn) ──────────────────────

class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return self.conn.existing_row


class _FakeConn:
    def __init__(self, existing_row):
        self.existing_row = existing_row
        self.executed = []
        self.committed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True


def _updates(conn):
    return [(sql, p) for (sql, p) in conn.executed if "UPDATE agent_runtime.conversation_members" in sql]


def _marks(conn):
    return [(sql, p) for (sql, p) in conn.executed if "has_restricted_members = true" in sql]


def test_stamp_new_member_takes_exact_window():
    conn = _FakeConn(("member", None, None, None, None))  # add_member 직후(윈도우 NULL)
    fc, cc = _dt.datetime(2026, 1, 1), _dt.datetime(2026, 2, 1)
    group_members.stamp_member_visibility(
        conn, "c1", 9, is_new_member=True,
        floor_id=100, ceiling_id=200, floor_created_at=fc, ceiling_created_at=cc,
    )
    ups = _updates(conn)
    assert len(ups) == 1
    p = ups[0][1]
    assert p["floor_id"] == 100 and p["ceiling_id"] == 200
    assert p["floor_ca"] == fc and p["ceiling_ca"] == cc
    assert _marks(conn)  # has_restricted_members = true set
    assert conn.committed


def test_stamp_existing_full_member_not_narrowed():
    # 기존 full 멤버(floor/ceil NULL)가 windowed 링크로 재참여 → 좁히지 않음(UPDATE 없음).
    conn = _FakeConn(("member", None, None, None, None))
    group_members.stamp_member_visibility(
        conn, "c1", 9, is_new_member=False,
        floor_id=100, ceiling_id=200, floor_created_at=_dt.datetime(2026, 1, 1), ceiling_created_at=None,
    )
    assert _updates(conn) == []


def test_stamp_existing_windowed_member_intersects_never_widens():
    # 기존 [100,200] 멤버가 더 넓은 [50,250] 링크로 재참여 → 교집합 [100,200] 유지(확대 금지).
    fc0, cc0 = _dt.datetime(2026, 1, 10), _dt.datetime(2026, 1, 20)
    conn = _FakeConn(("member", 100, 200, fc0, cc0))
    group_members.stamp_member_visibility(
        conn, "c1", 9, is_new_member=False,
        floor_id=50, ceiling_id=250,
        floor_created_at=_dt.datetime(2026, 1, 5), ceiling_created_at=_dt.datetime(2026, 1, 25),
    )
    ups = _updates(conn)
    assert len(ups) == 1
    p = ups[0][1]
    assert p["floor_id"] == 100 and p["ceiling_id"] == 200       # never widened
    assert p["floor_ca"] == fc0 and p["ceiling_ca"] == cc0       # 기존 스냅샷 보존(id 승자 따라감)


def test_stamp_owner_is_skipped():
    conn = _FakeConn(("owner", None, None, None, None))
    group_members.stamp_member_visibility(
        conn, "c1", 1, is_new_member=True,
        floor_id=100, ceiling_id=200, floor_created_at=_dt.datetime(2026, 1, 1), ceiling_created_at=None,
    )
    assert _updates(conn) == []  # 소유자는 각인 안 함


def test_windowed_core_query_has_created_at_predicate():
    # LLM recall windowed 쿼리가 created_at 범위 + joined 라이브-tail union 을 포함하는지.
    q = runtime_backend._PG_LOAD_CORE_MESSAGES_WINDOWED
    assert "created_at >= %(floor_ca)s" in q
    assert "created_at <= %(ceil_ca)s" in q
    assert "created_at >= %(joined_ca)s" in q
