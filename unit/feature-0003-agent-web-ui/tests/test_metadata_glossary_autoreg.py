"""용어사전 대화 자율등록(0021) — web 경계(RBAC/audit/검증) 회귀 테스트.

검토 큐(glossary_feedback)·역할 차원(role_key)·유사어 참조(glossary_relations) 의 web 층을 DB 없이
monkeypatch/fake 로 검증한다. 적재/승급/거부/관계 정본은 feature-0002 modules.kb_glossary — 여기서는
web 경계(권한 kb.glossary.curate / kb.ingest.manual, audit, 입력검증, role_key 검증)만 본다.

검증 대상:
  P     kb.glossary.curate 권한이 catalog(group=kb) + admin seed 에 존재.
  RV    role_key 검증 — 허용 역할/'*' 통과, 미허용 역할 → 400.
  FQ403 검토 큐 list/promote/reject — kb.glossary.curate 미보유 → 403.
  FQL   검토 큐 list — 직렬화 + pending_count.
  FP    promote — promote_glossary_feedback 호출 + audit(glossary.feedback.promote). None → 404.
  FR    reject — reject_glossary_feedback 호출 + audit(glossary.feedback.reject).
  REL   relations — add(자기참조/잘못된 type → 400) + list + delete + audit.
`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import asyncio
import datetime
import json

import app
from routers import admin_metadata
import shared.db as _dbmod
import modules.kb_glossary as _kg


class _FakeRequest:
    def __init__(self, payload=None, query=None):
        self._payload = payload if payload is not None else {}
        self.query_params = query or {}
        self.headers = {}
        self.client = None
        self.cookies = {}

    async def body(self):
        return json.dumps(self._payload).encode("utf-8") if self._payload else b""

    async def json(self):
        return self._payload


class _BenignCursor:
    def execute(self, sql, params=None):
        self._sql = sql

    def fetchone(self):
        return None

    def fetchall(self):
        # role_key 검증(_metadata_valid_role_keys) 의 'SELECT RoleKey FROM WebRoles' 응답.
        if "WebRoles" in getattr(self, "_sql", ""):
            return [("operator",), ("sales",), ("admin",), ("pending",)]
        return []

    def close(self):
        return None


class _MemConn:
    def __init__(self):
        self.committed = False

    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        return None

    def close(self):
        return None


class _PgConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        return None


def _body(resp):
    return json.loads(resp.body)


def _audit_capture(monkeypatch):
    events: list[dict] = []
    monkeypatch.setattr(app, "record_audit_event", lambda conn, **kw: events.append(dict(kw)))
    monkeypatch.setattr(app, "_build_actor_from_request",
                        lambda request, account, actor_type="account": {"actor_type": actor_type})
    return events


def _env(monkeypatch, *, perms):
    """_connect_memory + datasources + 계정(perms) fake. role_key 검증용 WebRoles 행도 _MemConn 이 제공."""
    monkeypatch.setattr(app, "_connect_memory", lambda: _MemConn())
    import shared.datasources as _dsr
    monkeypatch.setattr(_dsr, "all_datasources",
                        lambda conn: {"default": {"key": "default", "engine": "mysql", "scope_key": "default"}})
    acct = {"id": 1, "username": "curator", "permissions": dict(perms)}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


# ── P: 권한 카탈로그/시드 ─────────────────────────────────────────────────────
def test_glossary_curate_permission_in_catalog():
    assert "kb.glossary.curate" in app.PERMISSION_CODES
    defn = app.PERMISSION_DEFINITION_MAP["kb.glossary.curate"]
    assert defn["group"] == "kb"


def test_glossary_curate_in_admin_seed():
    admin = next((r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin"), None)
    assert admin is not None
    perms = admin.get("permissions")
    assert perms == set(app.PERMISSION_CODES) or "kb.glossary.curate" in perms


# ── RV: role_key 검증 ─────────────────────────────────────────────────────────
def test_create_glossary_with_role(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.ingest.manual": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    captured = {}
    monkeypatch.setattr(_kg, "upsert_glossary_term",
                        lambda conn, scope_key, term, definition, role_key="*", source="manual":
                        captured.update({"role_key": role_key, "term": term}))
    _audit_capture(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_create_glossary(_FakeRequest(
        {"scope_key": "common", "role_key": "Operator", "term": "리드", "definition": "영업 잠재고객"}), account=acct))
    assert resp.status_code == 200
    assert captured["role_key"] == "operator"   # 정규화


def test_create_glossary_invalid_role_400(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.ingest.manual": True})
    called = {"n": 0}
    monkeypatch.setattr(_kg, "upsert_glossary_term", lambda *a, **k: called.update(n=called["n"] + 1))
    resp = asyncio.run(admin_metadata.admin_create_glossary(_FakeRequest(
        {"scope_key": "common", "role_key": "ghost", "term": "x", "definition": "y"}), account=acct))
    assert resp.status_code == 400
    assert called["n"] == 0   # 코어 미호출


# ── FQ403: 권한 게이트 ────────────────────────────────────────────────────────
def test_feedback_list_requires_curate(client, as_account):
    as_account(perms={"console.access": True})   # kb.glossary.curate 없음 → require_permission 403
    resp = client.get("/api/admin/metadata/glossary-feedback?status=pending")
    assert resp.status_code == 403


# ── FQL: 검토 큐 list ─────────────────────────────────────────────────────────
def test_feedback_list_serializes(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.glossary.curate": True})
    monkeypatch.setattr(_dbmod, "_pg_connect_ro", lambda: _PgConn())
    ts = datetime.datetime(2026, 6, 29, 10, 0, 0)
    # row: (id, scope_key, role_key, term, suggested_definition, confidence, status,
    #       source_run_id, conversation_id, promoted_glossary_id, approved_by, created_at, updated_at)
    rows = [(5, "common", "*", "리드", "영업 잠재고객", 0.7, "pending", "run1", "c1", None, None, ts, ts)]
    monkeypatch.setattr(_kg, "list_glossary_feedback", lambda conn, **k: rows)
    monkeypatch.setattr(_kg, "count_glossary_feedback", lambda conn, status="pending": 3)
    resp = admin_metadata.admin_list_glossary_feedback(_FakeRequest(query={"status": "pending"}), account=acct)
    assert resp.status_code == 200
    out = _body(resp)
    assert out["count"] == 1 and out["pending_count"] == 3
    it = out["items"][0]
    assert it["id"] == 5 and it["term"] == "리드" and it["status"] == "pending"
    assert it["role_key"] == "*" and abs(it["confidence"] - 0.7) < 1e-6


# ── FP: promote ──────────────────────────────────────────────────────────────
def test_feedback_promote(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.glossary.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "promote_glossary_feedback", lambda conn, fid, **k: 321)
    events = _audit_capture(monkeypatch)
    resp = admin_metadata.admin_promote_glossary_feedback(5, _FakeRequest(), account=acct)
    assert resp.status_code == 200
    assert _body(resp)["glossary_id"] == 321
    assert pg.committed is True
    assert any(e.get("action") == "glossary.feedback.promote" for e in events)


def test_feedback_promote_404(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.glossary.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "promote_glossary_feedback", lambda conn, fid, **k: None)
    _audit_capture(monkeypatch)
    resp = admin_metadata.admin_promote_glossary_feedback(99, _FakeRequest(), account=acct)
    assert resp.status_code == 404


# ── FR: reject ───────────────────────────────────────────────────────────────
def test_feedback_reject(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.glossary.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "reject_glossary_feedback", lambda conn, fid: 1)
    events = _audit_capture(monkeypatch)
    resp = admin_metadata.admin_reject_glossary_feedback(5, _FakeRequest(), account=acct)
    assert resp.status_code == 200
    assert any(e.get("action") == "glossary.feedback.reject" for e in events)


# ── REL: 유사어 관계 ─────────────────────────────────────────────────────────
def test_relation_add(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.ingest.manual": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "get_glossary_term", lambda conn, tid, **k: (tid, "common", "*", "t", "d", "manual"))
    captured = {}
    monkeypatch.setattr(_kg, "add_glossary_relation",
                        lambda conn, f, t, rt, created_by=None: captured.update({"f": f, "t": t, "rt": rt}))
    events = _audit_capture(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_add_glossary_relation(1, _FakeRequest({"to_id": 2, "relation_type": "synonym"}), account=acct))
    assert resp.status_code == 200
    assert captured == {"f": 1, "t": 2, "rt": "synonym"}
    assert any(e.get("action") == "glossary.relation.create" for e in events)


def test_relation_self_reference_400(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.ingest.manual": True})
    resp = asyncio.run(admin_metadata.admin_add_glossary_relation(1, _FakeRequest({"to_id": 1}), account=acct))
    assert resp.status_code == 400


def test_relation_bad_type_400(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.ingest.manual": True})
    resp = asyncio.run(admin_metadata.admin_add_glossary_relation(1, _FakeRequest({"to_id": 2, "relation_type": "bogus"}), account=acct))
    assert resp.status_code == 400


def test_relation_delete(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.ingest.manual": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "delete_glossary_relation", lambda conn, rid: 1)
    events = _audit_capture(monkeypatch)
    resp = admin_metadata.admin_delete_glossary_relation(7, _FakeRequest(), account=acct)
    assert resp.status_code == 200
    assert any(e.get("action") == "glossary.relation.delete" for e in events)
