"""TASK-0248: 제품 삭제 시 참조 대화 차단(blocked) 회귀 테스트.

요구사항:
  - `관리 콘솔 > 제품` 삭제는 참조 대화가 있어도 거부하지 않고 허용한다(과거 400 가드 제거).
  - 그 제품을 pinned 한 대화는 blocked 로 전환된다 — 이력 열람·공유(읽기 전용)는 가능하되
    `/api/ask` 로 더 이상 진행(새 메시지)할 수 없다.

검증:
  D1  admin_delete_product — 참조 대화 N개여도 삭제 성공 + UPDATE 차단 + blocked_conversations=N.
  D2  admin_delete_product — 참조 대화 0개면 blocked_conversations=0 (UPDATE 는 0 rowcount).
  D3  admin_delete_product — product.manage 권한 없으면 403 (차단/삭제 미수행).
  B1  _conversation_block_info — blocked_at 이 set 이면 (True, reason), NULL 이면 (False, "").
  B2  _block_conversations_for_product — WHERE product_id AND blocked_at IS NULL UPDATE + rowcount.
  A1  /api/ask — 기존 대화가 blocked 면 403 + 사유 (slot 획득 전 조기 차단).

env AGENT_RUNTIME_READ_BACKEND 를 postgres 가 아닌 값으로 두어 MySQL 폴백 경로를 단위 검증한다.
`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json

import app


# ── Fakes ───────────────────────────────────────────────────────────────────
class _Cursor:
    """SQL 패턴으로 응답을 분기하는 stub. executed 로 호출 SQL 추적, rowcount 노출."""

    def __init__(self, store):
        self._store = store
        self._rows = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self._store.setdefault("executed", []).append(s)
        self._store["last_params"] = params
        self._rows = []
        if "select isdefault from webproducts where id" in s:
            # TASK-0302: 핸들러가 삭제 전 제품 존재/기본여부를 먼저 확인한다(미존재 404, 기본 409).
            # 기존 테스트 시나리오 유지 — 미설정 시 비-기본 제품이 존재하는 것으로 응답.
            if self._store.get("product_missing"):
                self._rows = []
            else:
                self._rows = [(int(self._store.get("is_default", 0)),)]
        elif "count(*) from agentcoreconversations" in s:
            assert "blocked_at is null" in s, "차단 대상 COUNT 는 미차단 대화만 세어야 함"
            self._rows = [(int(self._store.get("referencing", 0)),)]
        elif "select id from webpermissions" in s:
            self._rows = [(int(p),) for p in self._store.get("dyn_perm_ids", [])]
        elif s.startswith("update agentcoreconversations") and "blocked_at = now()" in s:
            assert "blocked_at is null" in s, "재차단 방지 가드(blocked_at IS NULL) 필요"
            self.rowcount = int(self._store.get("block_rowcount", self._store.get("referencing", 0)))
            self._store["block_update_params"] = params
        elif "select blocked_at, blocked_reason, archived_at from agentcoreconversations" in s:
            # TASK-0273: _conversation_block_info SQL 이 archived_at 컬럼을 추가로 SELECT.
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
        self.committed = False
        self.autocommit = True

    def cursor(self, *a, **k):
        return _Cursor(self._store)

    def commit(self):
        self.committed = True

    def rollback(self):
        self._store["rolled_back"] = True

    def close(self):
        pass


class _Req:
    def __init__(self, body=None):
        self._body = body or {}

    async def body(self):
        return json.dumps(self._body).encode()

    async def json(self):
        return self._body


def _actor():
    return {"id": 1, "permissions": {"product.manage": True}}


def _patch_delete(monkeypatch, conn, *, has_perm=True):
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)  # MySQL 폴백 경로
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda req, c: (_actor(), None))
    monkeypatch.setattr(app, "_account_has_permission", lambda actor, perm: has_perm)
    monkeypatch.setattr(app, "record_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(app, "_build_actor_from_request", lambda *a, **kw: _actor())


# ── D1: 참조 대화가 있어도 삭제 성공 + 차단 ──────────────────────────────────
def test_delete_product_allows_and_blocks_referencing(monkeypatch):
    store = {"referencing": 3, "dyn_perm_ids": []}
    conn = _Conn(store)
    _patch_delete(monkeypatch, conn)
    resp = app.admin_delete_product(5, _Req())
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["ok"] is True
    assert body["product_id"] == 5
    assert body["blocked_conversations"] == 3  # 참조 3건 → 3건 차단
    assert conn.committed
    # WebProducts 삭제 + 차단 UPDATE 둘 다 수행됐는지.
    joined = " || ".join(store["executed"])
    assert "delete from webproducts where id" in joined
    assert "update agentcoreconversations" in joined


# ── D2: 참조 대화 0개 → 차단 0 ────────────────────────────────────────────────
def test_delete_product_no_referencing(monkeypatch):
    store = {"referencing": 0, "dyn_perm_ids": []}
    conn = _Conn(store)
    _patch_delete(monkeypatch, conn)
    resp = app.admin_delete_product(7, _Req())
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["blocked_conversations"] == 0


# ── D3: 권한 없으면 403 (삭제/차단 미수행) ────────────────────────────────────
def test_delete_product_requires_permission(monkeypatch):
    store = {"referencing": 2}
    conn = _Conn(store)
    _patch_delete(monkeypatch, conn, has_perm=False)
    resp = app.admin_delete_product(5, _Req())
    assert resp.status_code == 403
    assert "update agentcoreconversations" not in " || ".join(store.get("executed", []))


# ── B1: _conversation_block_info ──────────────────────────────────────────────
def test_block_info_reads_flag(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)
    store = {"block_info_rows": [("2026-06-12T00:00:00", "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.", None)]}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    is_blocked, reason = app._conversation_block_info("conv-1", conn=conn)
    assert is_blocked is True
    assert "삭제" in reason


def test_block_info_not_blocked(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)
    store = {"block_info_rows": [(None, None, None)]}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    is_blocked, reason = app._conversation_block_info("conv-1", conn=conn)
    assert is_blocked is False
    assert reason == ""


# ── B2: _block_conversations_for_product ──────────────────────────────────────
def test_block_conversations_for_product_sql(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)
    store = {"block_rowcount": 4}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    affected = app._block_conversations_for_product(9, "사유 X")
    assert affected == 4
    # reason, product_id 순서로 바인딩됐는지.
    assert store["block_update_params"] == ("사유 X", 9)


# ── A1: /api/ask 가 차단된 대화를 403 으로 거부 ───────────────────────────────
def test_ask_rejects_blocked_conversation(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)
    store = {}
    conn = _Conn(store)
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda req, c: (_actor(), None))
    monkeypatch.setattr(app, "_is_safe_model_name", lambda m: True)
    monkeypatch.setattr(app, "_is_allowed_api_model", lambda m: True)
    monkeypatch.setattr(app, "_conversation_exists", lambda cid, conn=None: True)
    monkeypatch.setattr(app, "_account_has_permission", lambda actor, perm: True)
    monkeypatch.setattr(app, "_conversation_owned_by_account", lambda c, cid, aid: True)
    monkeypatch.setattr(
        app, "_conversation_block_info",
        lambda cid, conn=None: (True, "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다."),
    )
    body = {"message": "안녕", "model": "claude-haiku-4-5-20251001", "conversation_id": "conv-1"}
    resp = asyncio.run(app.ask(_Req(body)))
    assert resp.status_code == 403
    assert "삭제" in json.loads(resp.body)["error"]
