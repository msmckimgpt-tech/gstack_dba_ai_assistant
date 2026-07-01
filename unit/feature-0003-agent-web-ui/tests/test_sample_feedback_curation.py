"""TASK-20260623T090440-sample-feedback-curation (ROADMAP dba-ai-nl2sql ITEM-03) — 회귀/보안 테스트.

피드백 → 샘플쿼리 KB 환류 flywheel 의 web 층(feature-0003)을 DB 없이 monkeypatch/fake 로 검증한다.
적재/승급 로직 정본은 feature-0002 modules.sample_feedback — 여기서는 web 경계(RBAC/audit/scope/
cross-DB conn 분리)만 검증한다.

검증 대상:
  R1  kb.sample.curate 권한이 PERMISSION_DEFINITIONS(group=kb) + PERMISSION_CODES 에 존재.
  R2  admin seed(=set(PERMISSION_CODES)) 에 포함 / operator·sales·pending 미포함(least-privilege).
  S1  GET  /api/admin/sample-feedback — kb.sample.curate 미보유 → 403.
  S2  POST /approve — kb.sample.curate 미보유 → 403 (승급 코어 미호출).
  S3  POST /reject  — kb.sample.curate 미보유 → 403.
  U1  POST /conversations/{cid}/sample-feedback — 대화 접근 불가 → 404 (적재 미호출).
  U2  사용자 피드백 적재 경로 — record_feedback 호출 인자(vote/scope/cid) + audit 기록 검증.
  A1  approve 승급 경로 — promote_feedback 호출 + sample_id 반환 + audit(action=sample.feedback.approve).
  A2  approve 가 sample_id=None(👎/비-pending) → 409 + audit 미기록.
  A3  reject 경로 — reject_feedback 호출 + audit(action=sample.feedback.reject).
  L1  list 경로 — list_pending_feedback rows → items 직렬화(마스킹된 generated_sql 그대로 노출).
  SC1 scope 도출 — pinned product → _resolve_product_insight_scope.scope, 미고정/실패 → 'common'.

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import asyncio
import datetime
import json

import app
from routers import conversations  # feature-0012 P5b
from routers import admin_sample_feedback
import shared.db as _dbmod
import modules.sample_feedback as _sfb


# ── Fakes ──────────────────────────────────────────────────────────────────────

class _FakeRequest:
    def __init__(self, payload=None):
        self._payload = payload if payload is not None else {}
        self.query_params = {}
        self.headers = {}
        self.client = None

    async def body(self):
        return json.dumps(self._payload).encode("utf-8") if self._payload else b""

    async def json(self):
        return self._payload


class _BenignCursor:
    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        return None


class _BenignConn:
    """memory(MySQL) conn 대용 — auth/audit 경로의 무해 conn."""

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


class _RecordingPgCursor:
    def __init__(self, lastval=None):
        self._lastval = lastval

    def execute(self, sql, params=None):
        self._last_sql = sql

    def fetchone(self):
        # post_sample_feedback 가 lastval() 으로 id 회수.
        return (self._lastval,) if self._lastval is not None else None

    def fetchall(self):
        return []

    def close(self):
        return None


class _RecordingPgConn:
    """PG(agent_kb) conn 대용 — record_feedback/promote/reject 가 받는 conn."""

    def __init__(self, lastval=None):
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.autocommit = False
        self._lastval = lastval

    def cursor(self, *a, **k):
        return _RecordingPgCursor(self._lastval)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _body(resp):
    return json.loads(resp.body)


def _audit_capture(monkeypatch):
    """record_audit_event 호출을 캡처해 list 로 반환."""
    events: list[dict] = []

    def _fake(conn, **kwargs):
        events.append(dict(kwargs))

    monkeypatch.setattr(app, "record_audit_event", _fake)
    monkeypatch.setattr(app, "_build_actor_from_request", lambda request, account, actor_type="account": {"actor_type": actor_type})
    return events


# ── R1/R2: RBAC 카탈로그/시드 ─────────────────────────────────────────────────────

def test_curate_permission_in_catalog():
    assert "kb.sample.curate" in app.PERMISSION_CODES
    defn = app.PERMISSION_DEFINITION_MAP["kb.sample.curate"]
    assert defn["group"] == "kb"


def test_curate_in_admin_seed_not_in_stock_roles():
    admin = next(r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin")
    assert "kb.sample.curate" in set(admin["permissions"]), "admin seed=set(PERMISSION_CODES) → 보유"
    for key in ("operator", "sales", "pending"):
        role = next((r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == key), None)
        if role is not None:
            assert "kb.sample.curate" not in set(role["permissions"]), f"{key} 는 검수 권한 미보유(least-privilege)"


# ── S1/S2/S3: admin endpoint 권한 게이트 403 (코어 미호출) ───────────────────────────

def test_list_requires_permission(monkeypatch, client, as_account):
    # P5b DI seam Phase 3: admin_list_sample_feedback 가 account=Depends(require_permission("kb.sample.curate"))
    # 로 마이그됨 → perm 검사가 의존성으로 이동(직접호출 우회). TestClient + as_account(perm 없음)로 403 보존.
    as_account(perms={"console.access": True})  # kb.sample.curate 없음
    called = {"list": False}
    monkeypatch.setattr(_sfb, "list_pending_feedback", lambda *a, **k: called.__setitem__("list", True) or [])
    resp = client.get("/api/admin/sample-feedback")
    assert resp.status_code == 403
    assert called["list"] is False, "권한 거부 시 코어 list 미호출"


def test_approve_requires_permission(monkeypatch, client, as_account):
    # P5b DI seam Phase 3: require_permission DI 로 이동 → TestClient + as_account(perm 없음)로 403 보존.
    as_account(perms={"console.access": True})
    called = {"promote": False}
    monkeypatch.setattr(_sfb, "promote_feedback", lambda *a, **k: called.__setitem__("promote", True) or 1)
    resp = client.post("/api/admin/sample-feedback/7/approve", json={})
    assert resp.status_code == 403
    assert called["promote"] is False, "권한 거부 시 승급 코어 미호출(보안 핵심)"


def test_reject_requires_permission(monkeypatch, client, as_account):
    # P5b DI seam Phase 3: require_permission DI 로 이동 → TestClient + as_account(perm 없음)로 403 보존.
    as_account(perms={"console.access": True})
    called = {"reject": False}
    monkeypatch.setattr(_sfb, "reject_feedback", lambda *a, **k: called.__setitem__("reject", True))
    resp = client.post("/api/admin/sample-feedback/7/reject", json={})
    assert resp.status_code == 403
    assert called["reject"] is False


# ── U1: 사용자 피드백 — 대화 접근 불가 → 404 (적재 미호출) ───────────────────────────

def test_user_feedback_access_denied(monkeypatch):
    acct = {"id": 5, "username": "u", "permissions": {"conversation.read.own": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: False)
    called = {"record": False}
    monkeypatch.setattr(_sfb, "record_feedback", lambda *a, **k: called.__setitem__("record", True))
    resp = asyncio.run(conversations.post_sample_feedback("conv-x", _FakeRequest({"vote": "up", "nl_question": "q"})))
    assert resp.status_code == 404
    assert called["record"] is False, "접근 거부 시 적재 미호출"


# ── U2: 사용자 피드백 적재 경로 + audit ──────────────────────────────────────────────

def test_user_feedback_record_and_audit(monkeypatch):
    acct = {"id": 5, "username": "tester", "permissions": {"conversation.read.own": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(app, "_conversation_scope_key", lambda conn, cid: "mysql-deadbeef")
    pg = _RecordingPgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    captured = {}

    def _fake_record(conn, scope_key, nl_question, generated_sql, **kw):
        captured.update({"conn": conn, "scope_key": scope_key, "nl_question": nl_question,
                         "generated_sql": generated_sql, **kw})
        return 42  # UPSERT … RETURNING id (lastval() 미사용 — DO UPDATE 경로 부정확)

    monkeypatch.setattr(_sfb, "record_feedback", _fake_record)
    events = _audit_capture(monkeypatch)

    resp = asyncio.run(conversations.post_sample_feedback("conv-1", _FakeRequest({
        "vote": "down", "suggested": True, "nl_question": "  매출 상위 10  ",
        "generated_sql": "SELECT 1", "message_id": 77, "message_id_space": "core",
    })))
    assert resp.status_code == 200
    out = _body(resp)
    assert out["ok"] is True
    assert out["feedback_id"] == 42
    # 적재 인자 검증 — vote/scope/cid/created_by/message_id/message_id_space 가 코어로 전달.
    assert captured["conn"] is pg, "PG(agent_kb) conn 으로 적재"
    assert captured["scope_key"] == "mysql-deadbeef"
    assert captured["nl_question"] == "매출 상위 10"
    assert captured["vote"] == "down"
    assert captured["suggested"] is True
    assert captured["conversation_id"] == "conv-1"
    assert captured["created_by"] == "tester"
    assert captured["message_id"] == 77, "답변 식별자(message_id) 가 코어로 전달 — 고유 피드백 키"
    assert captured["message_id_space"] == "core", "id_space 가 코어로 전달 — 두 id 공간 구분(H5(b))"
    assert pg.committed is True
    # best-effort audit — action=sample.feedback.submit.
    assert any(e.get("action") == "sample.feedback.submit" for e in events)


def test_user_feedback_requires_nl_question(monkeypatch):
    acct = {"id": 5, "username": "u", "permissions": {}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    # nl_question 누락 → 400 (conn/access 검사 전 조기 차단).
    resp = asyncio.run(conversations.post_sample_feedback("conv-1", _FakeRequest({"vote": "up"})))
    assert resp.status_code == 400


# ── A1: approve 승급 경로 + audit ────────────────────────────────────────────────

def test_approve_promotes_and_audits(monkeypatch):
    admin = {"id": 1, "username": "admin", "permissions": {"kb.sample.curate": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    pg = _RecordingPgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    captured = {}

    def _fake_promote(conn, feedback_id, **kw):
        captured.update({"conn": conn, "feedback_id": feedback_id, **kw})
        return 777  # 승급된 sample_queries.id

    monkeypatch.setattr(_sfb, "promote_feedback", _fake_promote)
    events = _audit_capture(monkeypatch)

    # P5b DI: account=Depends(require_permission) 마이그 → happy 경로는 account 명시 주입(require_permission 우회, 동작만 검증; perm-gate 는 별도 403 테스트).
    resp = asyncio.run(admin_sample_feedback.admin_approve_sample_feedback(13, _FakeRequest({"weight": 90, "domain": "sales"}), account=admin))
    assert resp.status_code == 200
    out = _body(resp)
    assert out["ok"] is True
    assert out["sample_id"] == 777
    assert captured["conn"] is pg, "승급은 PG(agent_kb) conn"
    assert captured["feedback_id"] == 13
    assert captured["approved_by"] == "admin"
    assert captured["weight"] == 90
    assert captured["domain"] == "sales"
    assert pg.committed is True
    # audit — action=sample.feedback.approve, memory conn(별도) 사용.
    approve_events = [e for e in events if e.get("action") == "sample.feedback.approve"]
    assert len(approve_events) == 1
    assert approve_events[0]["resource_type"] == "sample_feedback"
    assert approve_events[0]["resource_id"] == "13"


# ── A2: approve sample_id=None(👎/비-pending) → 409 + audit 미기록 ──────────────────

def test_approve_none_returns_409_no_audit(monkeypatch):
    admin = {"id": 1, "username": "admin", "permissions": {"kb.sample.curate": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    pg = _RecordingPgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_sfb, "promote_feedback", lambda *a, **k: None)  # 👎 또는 비-pending
    events = _audit_capture(monkeypatch)

    resp = asyncio.run(admin_sample_feedback.admin_approve_sample_feedback(99, _FakeRequest({}), account=admin))
    assert resp.status_code == 409
    assert not any(e.get("action") == "sample.feedback.approve" for e in events), "비-승급 시 audit 미기록"


# ── A3: reject 경로 + audit ──────────────────────────────────────────────────────

def test_reject_rejects_and_audits(monkeypatch):
    admin = {"id": 1, "username": "admin", "permissions": {"kb.sample.curate": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    pg = _RecordingPgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    captured = {}

    def _fake_reject(conn, feedback_id):
        captured.update({"conn": conn, "feedback_id": feedback_id})

    monkeypatch.setattr(_sfb, "reject_feedback", _fake_reject)
    events = _audit_capture(monkeypatch)

    resp = asyncio.run(admin_sample_feedback.admin_reject_sample_feedback(21, _FakeRequest({}), account=admin))
    assert resp.status_code == 200
    assert captured["conn"] is pg
    assert captured["feedback_id"] == 21
    assert pg.committed is True
    reject_events = [e for e in events if e.get("action") == "sample.feedback.reject"]
    assert len(reject_events) == 1
    assert reject_events[0]["resource_id"] == "21"


# ── L1: list 경로 — rows → items 직렬화 ──────────────────────────────────────────

def test_list_serializes_pending_rows(monkeypatch):
    admin = {"id": 1, "username": "admin", "permissions": {"kb.sample.curate": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    monkeypatch.setattr(_dbmod, "_pg_connect_ro", lambda autocommit=True: _RecordingPgConn())
    ts = datetime.datetime(2026, 6, 23, 10, 0, 0)
    # row: (id, scope_key, conversation_id, nl_question, generated_sql, vote, suggested, created_at)
    rows = [
        (1, "common", "conv-a", "질문1", "SELECT * FROM t WHERE email='***'", "up", True, ts),
        (2, "mysql-abc", None, "질문2", "", "down", False, ts),
    ]
    monkeypatch.setattr(_sfb, "list_pending_feedback", lambda conn, scope_key=None, limit=50: rows)

    resp = admin_sample_feedback.admin_list_sample_feedback(_FakeRequest(), account=admin)
    assert resp.status_code == 200
    out = _body(resp)
    assert out["count"] == 2
    it0 = out["items"][0]
    assert it0["id"] == 1 and it0["scope_key"] == "common" and it0["vote"] == "up"
    assert it0["suggested"] is True
    assert it0["generated_sql"] == "SELECT * FROM t WHERE email='***'"  # 적재 시 마스킹된 값 그대로
    assert it0["created_at"].startswith("2026-06-23")
    assert out["items"][1]["conversation_id"] is None


# ── SC1: scope 도출 — pinned product / 미고정·실패 폴백 ────────────────────────────

def test_scope_key_pinned_product(monkeypatch):
    conn = _BenignConn()
    monkeypatch.setattr(app, "_load_conversation_product",
                        lambda c, cid: {"product_mode": "pinned", "product_id": 3})
    monkeypatch.setattr(app, "_list_products",
                        lambda c, include_inactive=False: [{"id": 3, "product_key": "KR", "name": "KR"}])
    monkeypatch.setattr(app, "_resolve_product_insight_scope",
                        lambda c, product: {"ok": True, "scope": "mysql-cafe1234"})
    assert app._conversation_scope_key(conn, "conv-1") == "mysql-cafe1234"


def test_scope_key_auto_mode_falls_back_to_common(monkeypatch):
    conn = _BenignConn()
    monkeypatch.setattr(app, "_load_conversation_product",
                        lambda c, cid: {"product_mode": "auto", "product_id": None})
    assert app._conversation_scope_key(conn, "conv-1") == "common"


def test_scope_key_resolution_failure_falls_back_to_common(monkeypatch):
    conn = _BenignConn()
    monkeypatch.setattr(app, "_load_conversation_product",
                        lambda c, cid: {"product_mode": "pinned", "product_id": 3})
    monkeypatch.setattr(app, "_list_products",
                        lambda c, include_inactive=False: [{"id": 3, "product_key": "KR"}])
    monkeypatch.setattr(app, "_resolve_product_insight_scope",
                        lambda c, product: {"ok": False, "reason": "미바인딩", "scope": None})
    assert app._conversation_scope_key(conn, "conv-1") == "common"
