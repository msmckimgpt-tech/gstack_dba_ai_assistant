"""TASK-0273: 대화 삭제 → soft-archive(보관) 전환 회귀 테스트.

요구사항:
  - "삭제" 는 hard-delete 가 아니라 보관(archived_at 마킹) — 데이터·첨부 보존.
  - 보관 대화는 (1) 소유자 목록에서 숨김 (2) 새 메시지 진행 차단 (3) admin 조회·fork 참조 가능.

검증(`make test` agent 이미지, DB 없이 monkeypatch):
  A1  _archive_conversation — UPDATE archived_at = NOW() ... WHERE archived_at IS NULL (재보관 방지).
  A2  _delete_conversation_impl — 정상 대화는 hard-delete(delete_conversation_records) 안 하고 archive 호출 → status='archived'.
  A3  _delete_conversation_impl — 권한 없으면 forbidden(아무 변경 없음).
  B1  _conversation_block_info — archived_at set 이면 (True, 보관 사유), blocked·archived 모두 NULL 이면 (False,"").
  L1  _list_conversations(MySQL) SQL 에 archived_at IS NULL 필터 존재(보관 대화 목록 숨김).
  P1  admin_archived_conversations — conversation.archive.read.any 없으면 403.
  R1  신규 권한 conversation.archive.read.any 가 카탈로그(PERMISSION_CODES)에 존재 + admin seed 자동 보유.
"""
from __future__ import annotations

import json

import app


class _Cursor:
    def __init__(self, store):
        self._store = store
        self._rows = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self._store.setdefault("executed", []).append((s, params))
        self._rows = []
        if "update agentcoreconversations" in s and "archived_at = now()" in s:
            assert "archived_at is null" in s, "재보관 방지 가드(archived_at IS NULL) 필요"
            self.rowcount = int(self._store.get("archive_rowcount", 1))
            self._store["archive_params"] = params
        elif "select blocked_at, blocked_reason, archived_at from agentcoreconversations" in s:
            self._rows = list(self._store.get("block_info_rows", []))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _Conn:
    def __init__(self, store):
        self._store = store

    def cursor(self, *a, **k):
        return _Cursor(self._store)

    def commit(self):
        self._store["committed"] = True

    def close(self):
        pass


class _Req:
    def __init__(self, qp=None):
        self.query_params = qp or {}


def _body(resp):
    return json.loads(resp.body)


def _mysql_env(monkeypatch):
    # PG 경로 회피 → MySQL 폴백 단위 검증.
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "mysql")


# ── A1: _archive_conversation UPDATE ─────────────────────────────────────────

def test_a1_archive_updates_with_guard(monkeypatch):
    _mysql_env(monkeypatch)
    store: dict = {}
    conn = _Conn(store)
    ok = app._archive_conversation(conn, "conv-1", 7)
    assert ok is True
    # archived_at = NOW() + archived_by + archived_at IS NULL 가드
    sqls = [s for (s, _p) in store["executed"]]
    assert any("update agentcoreconversations" in s and "archived_at = now()" in s and "archived_at is null" in s for s in sqls)
    assert store["archive_params"] == (7, "conv-1")
    assert store.get("committed") is True


# ── A2/A3: _delete_conversation_impl → archive ───────────────────────────────

def test_a2_delete_impl_archives_not_hard_delete(monkeypatch):
    _mysql_env(monkeypatch)
    store: dict = {}
    conn = _Conn(store)
    # 접근 권한 통과 + 처리중 아님 + cleanup/clear no-op
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(app, "cleanup_pending_delete_conversations", lambda c: None)
    monkeypatch.setattr(app, "is_processing_conversation", lambda c, cid: False)
    monkeypatch.setattr(app, "_clear_accounts_current_conversation", lambda c, cid: None)
    hard_called = {"n": 0}
    monkeypatch.setattr(app, "delete_conversation_records", lambda c, cid: hard_called.__setitem__("n", hard_called["n"] + 1))

    res = app._delete_conversation_impl(conn, {"id": 7}, "conv-1")
    assert res["status"] == "archived", res
    assert hard_called["n"] == 0, "보관은 hard-delete(delete_conversation_records) 를 호출하면 안 됨"
    # archive UPDATE 가 실행됨
    assert any("archived_at = now()" in s for (s, _p) in store["executed"])


def test_a3_delete_impl_forbidden(monkeypatch):
    _mysql_env(monkeypatch)
    store: dict = {}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: False)
    res = app._delete_conversation_impl(conn, {"id": 7}, "conv-1")
    assert res["status"] == "failed" and res["reason"] == "forbidden"
    assert not store.get("executed"), "권한 거부 시 어떤 SQL 도 실행하면 안 됨"


# ── B1: _conversation_block_info archived ────────────────────────────────────

def test_b1_block_info_archived(monkeypatch):
    _mysql_env(monkeypatch)
    # archived_at set (blocked_at NULL) → (True, 보관 사유)
    store = {"block_info_rows": [(None, None, "2026-06-15T00:00:00")]}
    is_b, reason = app._conversation_block_info("conv-1", conn=_Conn(store))
    assert is_b is True and "보관" in reason

    # blocked_at set → blocked 사유 우선
    store2 = {"block_info_rows": [("2026-06-15", "참조 제품 삭제", None)]}
    is_b2, reason2 = app._conversation_block_info("conv-1", conn=_Conn(store2))
    assert is_b2 is True and "제품" in reason2

    # 둘 다 NULL → 미차단
    store3 = {"block_info_rows": [(None, None, None)]}
    is_b3, reason3 = app._conversation_block_info("conv-1", conn=_Conn(store3))
    assert is_b3 is False and reason3 == ""


# ── L1: 목록 쿼리 archived_at IS NULL 필터 (정적) ────────────────────────────

def test_l1_list_query_has_archived_filter():
    # _list_conversations(MySQL 경로) 소스에 archived_at IS NULL 필터가 포함되는지 정적 확인.
    import inspect
    src = inspect.getsource(app._list_conversations)
    assert "c.archived_at IS NULL" in src, "MySQL 목록 쿼리에 보관 숨김 필터 누락"
    src_pg = inspect.getsource(app._list_conversations_pg)
    assert "c.archived_at IS NULL" in src_pg, "PG 목록 쿼리에 보관 숨김 필터 누락"


# ── P1: admin 보관 조회 권한 게이트 ──────────────────────────────────────────

def test_p1_admin_archived_requires_perm(monkeypatch):
    actor = {"id": 1, "permissions": {"console.access": True}}  # archive.read.any 없음
    monkeypatch.setattr(app, "_connect_memory", lambda: _Conn({}))
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (actor, None))
    resp = app.admin_archived_conversations(_Req())
    assert resp.status_code == 403


# ── R1: 신규 권한 카탈로그 등록 + admin seed ─────────────────────────────────

def test_r1_archive_perm_in_catalog():
    assert "conversation.archive.read.any" in app.PERMISSION_CODES
    # admin seed 는 set(PERMISSION_CODES) 자동 부여 → 신규 권한 포함.
    admin_role = next((r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin"), None)
    assert admin_role is not None
    assert "conversation.archive.read.any" in admin_role["permissions"]
