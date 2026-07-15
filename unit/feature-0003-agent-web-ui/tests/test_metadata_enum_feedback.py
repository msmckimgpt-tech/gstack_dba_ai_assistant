"""ENUM 코드사전 대화 자율수집(0039) — web 경계(RBAC/audit/직렬화) 회귀 테스트.

검토 큐(enum_feedback) web 층을 DB 없이 monkeypatch/fake 로 검증한다. 적재/승급/거부 정본은
feature-0002 modules.kb_glossary(test_kb_enum_feedback.py) — 여기서는 web 경계(권한 kb.enum.curate,
audit, 직렬화, source 노출)만 본다. test_metadata_glossary_autoreg.py 의 용어사전 web 테스트와 동형.

검증 대상:
  P     kb.enum.curate 권한이 catalog(group=kb) + admin seed 에 존재.
  FQ403 검토 큐 list/promote/reject — kb.enum.curate 미보유 → 403.
  FQL   검토 큐 list — 직렬화 + pending_count.
  FP    promote — promote_enum_feedback 호출 + audit(enum.feedback.promote). None → 404.
  FR    reject — reject_enum_feedback 호출 + audit(enum.feedback.reject).
  SRC   ENUM 목록 — source 필드 직렬화(자동등록 배지용).
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
    monkeypatch.setattr(app, "_connect_memory", lambda: _MemConn())
    import shared.datasources as _dsr
    monkeypatch.setattr(_dsr, "all_datasources",
                        lambda conn: {"default": {"key": "default", "engine": "mysql", "scope_key": "default"}})
    acct = {"id": 1, "username": "curator", "permissions": dict(perms)}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


# ── P: 권한 카탈로그/시드 ─────────────────────────────────────────────────────
def test_enum_curate_permission_in_catalog():
    assert "kb.enum.curate" in app.PERMISSION_CODES
    defn = app.PERMISSION_DEFINITION_MAP["kb.enum.curate"]
    assert defn["group"] == "kb"


def test_enum_curate_in_admin_seed():
    admin = next((r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin"), None)
    assert admin is not None
    perms = admin.get("permissions")
    assert perms == set(app.PERMISSION_CODES) or "kb.enum.curate" in perms


# ── FQ403: 권한 게이트 ────────────────────────────────────────────────────────
def test_enum_feedback_list_requires_curate(client, as_account):
    as_account(perms={"console.access": True})   # kb.enum.curate 없음 → require_permission 403
    resp = client.get("/api/admin/metadata/enum-feedback?status=pending")
    assert resp.status_code == 403


# ── FQL: 검토 큐 list ─────────────────────────────────────────────────────────
def test_enum_feedback_list_serializes(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    monkeypatch.setattr(_dbmod, "_pg_connect_ro", lambda: _PgConn())
    ts = datetime.datetime(2026, 7, 7, 10, 0, 0)
    # row: (id, scope_key, schema_name, table_name, column_name, code, suggested_label,
    #       confidence, status, source_run_id, conversation_id, promoted_enum_id, approved_by,
    #       created_at, updated_at)
    rows = [(5, "common", "public", "orders", "status", "P", "결제대기", 0.7, "pending",
             "run1", "c1", None, None, ts, ts)]
    monkeypatch.setattr(_kg, "list_enum_feedback", lambda conn, **k: rows)
    monkeypatch.setattr(_kg, "count_enum_feedback", lambda conn, status="pending": 3)
    resp = admin_metadata.admin_list_enum_feedback(_FakeRequest(query={"status": "pending"}), account=acct)
    assert resp.status_code == 200
    out = _body(resp)
    assert out["count"] == 1 and out["pending_count"] == 3
    it = out["items"][0]
    assert it["id"] == 5 and it["code"] == "P" and it["suggested_label"] == "결제대기"
    assert it["table_name"] == "orders" and it["column_name"] == "status" and it["status"] == "pending"
    assert abs(it["confidence"] - 0.7) < 1e-6


def test_enum_feedback_list_rejects_bad_status(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    resp = admin_metadata.admin_list_enum_feedback(_FakeRequest(query={"status": "bogus"}), account=acct)
    assert resp.status_code == 400


# ── FP: promote ──────────────────────────────────────────────────────────────
def test_enum_feedback_promote(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "promote_enum_feedback", lambda conn, fid, **k: 321)
    events = _audit_capture(monkeypatch)
    resp = admin_metadata.admin_promote_enum_feedback(5, _FakeRequest(), account=acct)
    assert resp.status_code == 200
    assert _body(resp)["enum_id"] == 321
    assert pg.committed is True
    assert any(e.get("action") == "enum.feedback.promote" for e in events)


def test_enum_feedback_promote_404(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "promote_enum_feedback", lambda conn, fid, **k: None)
    _audit_capture(monkeypatch)
    resp = admin_metadata.admin_promote_enum_feedback(99, _FakeRequest(), account=acct)
    assert resp.status_code == 404


# ── FR: reject ───────────────────────────────────────────────────────────────
def test_enum_feedback_reject(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "reject_enum_feedback", lambda conn, fid: 1)
    events = _audit_capture(monkeypatch)
    resp = admin_metadata.admin_reject_enum_feedback(5, _FakeRequest(), account=acct)
    assert resp.status_code == 200
    assert any(e.get("action") == "enum.feedback.reject" for e in events)


# ── FB: bulk-promote (구조 묶음 단위 '전체 승인/일부 해제 후 등록') ────────────
def test_enum_feedback_bulk_promote(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "bulk_promote_enum_feedback",
                        lambda conn, ids, **k: [{"feedback_id": i, "enum_id": 100 + i} for i in ids])
    events = _audit_capture(monkeypatch)
    # 중복 4 는 정규화(dedup)되어 requested=[3,4].
    resp = asyncio.run(admin_metadata.admin_bulk_promote_enum_feedback(
        _FakeRequest(payload={"feedback_ids": [3, 4, 4]}), account=acct))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["promoted_count"] == 2 and body["skipped_ids"] == []
    assert pg.committed is True
    ev = next((e for e in events if e.get("action") == "enum.feedback.bulk_promote"), None)
    assert ev is not None and ev["change_json"]["requested"] == [3, 4]


def test_enum_feedback_bulk_promote_reports_skips(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "bulk_promote_enum_feedback",
                        lambda conn, ids, **k: [{"feedback_id": 3, "enum_id": 103},
                                                {"feedback_id": 4, "enum_id": None}])
    _audit_capture(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_bulk_promote_enum_feedback(
        _FakeRequest(payload={"feedback_ids": [3, 4]}), account=acct))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["promoted_count"] == 1 and body["skipped_ids"] == [4]


def test_enum_feedback_bulk_promote_empty_400(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    resp = asyncio.run(admin_metadata.admin_bulk_promote_enum_feedback(
        _FakeRequest(payload={"feedback_ids": []}), account=acct))
    assert resp.status_code == 400


def test_enum_feedback_bulk_promote_bad_type_400(monkeypatch):
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    resp = asyncio.run(admin_metadata.admin_bulk_promote_enum_feedback(
        _FakeRequest(payload={"feedback_ids": ["x"]}), account=acct))
    assert resp.status_code == 400


def test_enum_feedback_bulk_promote_cap_400(monkeypatch):
    # 원본 배열 길이(dedup 전)부터 cap — 초대형 배열 선-DoS 차단(파싱/DB 이전 400).
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    resp = asyncio.run(admin_metadata.admin_bulk_promote_enum_feedback(
        _FakeRequest(payload={"feedback_ids": list(range(1, 202))}), account=acct))  # 201 > 200
    assert resp.status_code == 400


def test_enum_feedback_bulk_promote_sorts_ids(monkeypatch):
    # deadlock 회피 — 요청이 뒤섞여도 dedup 후 정렬된 결정적 lock 순서로 승급.
    acct = _env(monkeypatch, perms={"kb.enum.curate": True})
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    captured = {}

    def _fake_bulk(conn, ids, **k):
        captured["ids"] = list(ids)
        return [{"feedback_id": i, "enum_id": 100 + i} for i in ids]

    monkeypatch.setattr(_kg, "bulk_promote_enum_feedback", _fake_bulk)
    _audit_capture(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_bulk_promote_enum_feedback(
        _FakeRequest(payload={"feedback_ids": [9, 3, 7, 3]}), account=acct))
    assert resp.status_code == 200
    assert captured["ids"] == [3, 7, 9]   # dedup + 정렬
    assert pg.committed is True


def test_enum_feedback_bulk_promote_requires_curate(client, as_account):
    as_account(perms={"console.access": True})   # kb.enum.curate 없음 → 403
    resp = client.post("/api/admin/metadata/enum-feedback/bulk-promote", json={"feedback_ids": [1]})
    assert resp.status_code == 403


# ── SRC: ENUM 목록 source 직렬화(자동등록 배지) ───────────────────────────────
def test_enum_list_includes_source(monkeypatch):
    acct = _env(monkeypatch, perms={"metadata.enum.manage": True, "metadata.enum.read": True, "metadata.enum.create": True, "metadata.enum.update": True, "metadata.enum.delete": True})
    monkeypatch.setattr(_dbmod, "_pg_connect_ro", lambda: _PgConn())
    ts = datetime.datetime(2026, 7, 7, 10, 0, 0)
    # row: (id, scope_key, schema_name, table_name, column_name, code, label, source, created_at, updated_at)
    rows = [(9, "common", "public", "orders", "status", "P", "결제대기", "auto", ts, ts)]
    monkeypatch.setattr(_kg, "list_enum_admin", lambda conn, scope_key, **k: rows)
    resp = admin_metadata.admin_list_enums(_FakeRequest(query={"scope_key": "common"}), account=acct)
    assert resp.status_code == 200
    it = _body(resp)["items"][0]
    assert it["source"] == "auto" and it["code"] == "P" and it["label"] == "결제대기"
