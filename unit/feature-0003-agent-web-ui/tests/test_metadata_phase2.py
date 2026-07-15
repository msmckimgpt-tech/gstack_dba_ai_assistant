"""TASK-20260624-item11-metadata-phase2 (ROADMAP dba-ai-nl2sql ITEM-11 Phase 2) — 회귀/보안 테스트.

메타데이터 거버넌스 Phase 2(테이블/컬럼 설명 사전 · 샘플 admin · 스키마 부트스트랩)의 web 층
(feature-0003)을 DB 없이 monkeypatch/fake 로 검증한다. CRUD 정본은 feature-0002 modules.kb_metadata /
modules.sample_queries — 여기서는 web 경계(RBAC/audit/scope/입력검증/cross-DB conn 분리/임베딩 하이브리드 C)만
검증한다. MVP-1 tests/test_metadata_glossary_enum.py 의 fake 패턴을 복제한다.

검증 대상:
  T403  tables   — kb.ingest.manual 미보유 → 403 (코어 미호출).
  C403  columns  — kb.ingest.manual 미보유 → 403 (코어 미호출).
  S403  samples  — kb.sample.curate 미보유 → 403 (코어 미호출).
  B403  bootstrap— kb.ingest.manual 미보유 → 403.
  SV    scope 검증 — 미허용/빈 scope_key → 400 (코어 미호출).
  TC/CC create — upsert 호출(scope/필드) + commit + audit.
  TU/CU update — affected=0 → 404 / affected>0 → 200+audit.
  TD    delete  — 멱등(affected=0 → 200, audit 미기록).
  IV    입력 cap — 필수필드 누락/cap 초과 → 400.
  SWC   샘플 weight clamp — 1~1000 범위 강제.
  SNL   샘플 nl 중복(UNIQUE) → 409.
  SEMB  샘플 임베딩 분기 — nl 변경 동기 성공('active') / 실패('stale') / nl 미변경(touch 안 함).
  BDS   bootstrap DS 검증 — 미존재 datasource → 404.
  INJ   주입 단위 — load_table_column_descriptions substring 매칭·scope·datamark.

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import asyncio
import datetime
import json

import app
from routers import admin_metadata
import shared.db as _dbmod
import modules.kb_metadata as _km
import modules.sample_queries as _sq


# ── Fakes (MVP-1 복제) ──────────────────────────────────────────────────────────

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
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        return None


class _BenignConn:
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
        self.closed = False
        self.autocommit = False

    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _body(resp):
    return json.loads(resp.body)


def _audit_capture(monkeypatch):
    events: list[dict] = []

    def _fake(conn, **kwargs):
        events.append(dict(kwargs))

    monkeypatch.setattr(app, "record_audit_event", _fake)
    monkeypatch.setattr(app, "_build_actor_from_request",
                        lambda request, account, actor_type="account": {"actor_type": actor_type})
    return events


def _allow_scopes(monkeypatch, scopes=("common", "default")):
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    import shared.datasources as _dsr
    # scope-key-unify: _metadata_valid_scope_keys 는 dict 키(라벨)가 아니라 _dsr.scope_key(ds)(해시 축)를
    # 허용한다. fake ds 는 scope_key 필드를 그 scope 이름으로 채워 해당 scope 가 valid 가 되게 한다
    # (real _dsr.scope_key 는 scope_key 필드 우선 — write/read 축 일치 검증용).
    ds_map = {k: {"key": k, "engine": "mysql", "scope_key": k} for k in scopes if k != "common"}
    monkeypatch.setattr(_dsr, "all_datasources", lambda conn: ds_map)


def _admin(monkeypatch):
    """kb.ingest.manual + kb.sample.curate 둘 다 보유(Phase 2 happy path)."""
    acct = {"id": 1, "username": "admin",
            "permissions": {"kb.ingest.manual": True, "metadata.glossary.read": True, "metadata.glossary.create": True, "metadata.glossary.update": True, "metadata.glossary.delete": True, "metadata.enum.read": True, "metadata.enum.create": True, "metadata.enum.update": True, "metadata.enum.delete": True, "metadata.table.read": True, "metadata.table.create": True, "metadata.table.update": True, "metadata.table.delete": True, "metadata.column.read": True, "metadata.column.create": True, "metadata.column.update": True, "metadata.column.delete": True, "kb.sample.curate": True}}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


def _nobody(monkeypatch):
    acct = {"id": 9, "username": "op", "permissions": {"console.access": True}}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


def _pg(monkeypatch):
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    return pg


# ── T403/C403: tables/columns RBAC 403 (코어 미호출) ───────────────────────────────

def test_tables_endpoints_require_permission(monkeypatch, client, as_account):
    as_account(perms={"console.access": True})  # kb.ingest.manual 없음 → require_permission 403
    called = {"hit": False}
    for fn in ("list_table_desc_admin", "upsert_table_desc", "update_table_desc", "delete_table_desc"):
        monkeypatch.setattr(_km, fn, lambda *a, **k: called.__setitem__("hit", True) or [])

    assert client.get("/api/admin/metadata/tables?scope_key=common").status_code == 403
    assert client.post("/api/admin/metadata/tables", json={"scope_key": "common", "table_name": "t", "description": "d"}).status_code == 403
    assert client.put("/api/admin/metadata/tables/1", json={"scope_key": "common", "description": "d"}).status_code == 403
    assert client.delete("/api/admin/metadata/tables/1?scope_key=common").status_code == 403
    assert called["hit"] is False


def test_columns_endpoints_require_permission(monkeypatch, client, as_account):
    as_account(perms={"console.access": True})  # kb.ingest.manual 없음 → require_permission 403
    called = {"hit": False}
    for fn in ("list_column_desc_admin", "upsert_column_desc", "update_column_desc", "delete_column_desc"):
        monkeypatch.setattr(_km, fn, lambda *a, **k: called.__setitem__("hit", True) or [])

    body = {"scope_key": "common", "table_name": "t", "column_name": "c", "description": "d"}
    assert client.get("/api/admin/metadata/columns?scope_key=common").status_code == 403
    assert client.post("/api/admin/metadata/columns", json=body).status_code == 403
    assert client.put("/api/admin/metadata/columns/1", json={"scope_key": "common", "description": "d"}).status_code == 403
    assert client.delete("/api/admin/metadata/columns/1?scope_key=common").status_code == 403
    assert called["hit"] is False


# ── S403: samples RBAC 403 (kb.sample.curate) ──────────────────────────────────────

def test_samples_endpoints_require_curate(monkeypatch, client, as_account):
    as_account(perms={"console.access": True})  # kb.sample.curate 없음 → require_permission 403
    called = {"hit": False}
    for fn in ("list_samples_admin", "update_sample", "delete_sample"):
        monkeypatch.setattr(_sq, fn, lambda *a, **k: called.__setitem__("hit", True) or [])

    assert client.get("/api/admin/metadata/samples?scope_key=common").status_code == 403
    assert client.put("/api/admin/metadata/samples/1", json={"scope_key": "common", "weight": 50}).status_code == 403
    assert client.delete("/api/admin/metadata/samples/1?scope_key=common").status_code == 403
    assert called["hit"] is False


def test_samples_curate_only_not_ingest(client, as_account):
    """kb.ingest.manual 만 있고 kb.sample.curate 없으면 샘플 엔드포인트 403 (권한 분리 확인)."""
    as_account(perms={"kb.ingest.manual": True, "metadata.glossary.read": True, "metadata.glossary.create": True, "metadata.glossary.update": True, "metadata.glossary.delete": True, "metadata.enum.read": True, "metadata.enum.create": True, "metadata.enum.update": True, "metadata.enum.delete": True, "metadata.table.read": True, "metadata.table.create": True, "metadata.table.update": True, "metadata.table.delete": True, "metadata.column.read": True, "metadata.column.create": True, "metadata.column.update": True, "metadata.column.delete": True})  # curate 없음 → require_permission("kb.sample.curate") 403
    assert client.get("/api/admin/metadata/samples?scope_key=common").status_code == 403


# ── B403: bootstrap RBAC ───────────────────────────────────────────────────────────

def test_bootstrap_requires_permission(client, as_account):
    as_account(perms={"console.access": True})  # kb.ingest.manual 없음 → require_permission 403
    assert client.get("/api/admin/metadata/bootstrap/schemas?datasource=default").status_code == 403
    assert client.post("/api/admin/metadata/bootstrap", json={"datasource": "default", "schema": "dbo"}).status_code == 403


# ── SV: scope 검증 (코어 미호출) ──────────────────────────────────────────────────

def test_scope_rejects_unknown_and_empty(monkeypatch):
    _allow_scopes(monkeypatch, scopes=("common",))  # default 미허용
    acct = _admin(monkeypatch)
    called = {"hit": False}
    monkeypatch.setattr(_km, "upsert_table_desc", lambda *a, **k: called.__setitem__("hit", True))

    r1 = asyncio.run(admin_metadata.admin_create_table_desc(_FakeRequest({"scope_key": "nope", "table_name": "t", "description": "d"}), account=acct))
    assert r1.status_code == 400
    r2 = asyncio.run(admin_metadata.admin_create_table_desc(_FakeRequest({"scope_key": "", "table_name": "t", "description": "d"}), account=acct))
    assert r2.status_code == 400
    assert called["hit"] is False


# ── TC/CC: create → upsert + commit + audit ────────────────────────────────────────

def test_table_create_calls_core_and_audits(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _pg(monkeypatch)
    captured = {}

    def _fake(conn, scope_key, table_name, description, schema_name="", source="manual", created_by=None):
        captured.update({"conn": conn, "scope_key": scope_key, "table_name": table_name,
                         "description": description, "schema_name": schema_name, "source": source})

    monkeypatch.setattr(_km, "upsert_table_desc", _fake)
    events = _audit_capture(monkeypatch)

    resp = asyncio.run(admin_metadata.admin_create_table_desc(_FakeRequest({
        "scope_key": "default", "schema_name": "  sales  ", "table_name": "  orders  ",
        "description": "  주문 마스터  "}), account=acct))
    assert resp.status_code == 200
    assert captured["conn"] is pg
    assert captured["scope_key"] == "default" and captured["table_name"] == "orders"
    assert captured["schema_name"] == "sales" and captured["description"] == "주문 마스터"
    assert captured["source"] == "manual"
    assert pg.committed is True
    assert any(e.get("action") == "table_desc.create" for e in events)
    assert all(e.get("resource_type") == "kb_metadata" for e in events)


def test_table_create_bootstrap_source(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    captured = {}
    monkeypatch.setattr(_km, "upsert_table_desc",
                        lambda conn, scope_key, table_name, description, schema_name="", source="manual", created_by=None: captured.update({"source": source}))
    _audit_capture(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_create_table_desc(_FakeRequest({
        "scope_key": "default", "table_name": "t", "description": "d", "source": "bootstrap"}), account=acct))
    assert resp.status_code == 200 and captured["source"] == "bootstrap"


def test_column_create_calls_core(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _pg(monkeypatch)
    captured = {}

    def _fake(conn, scope_key, table_name, column_name, description, schema_name="", source="manual", created_by=None, ordinal=None):
        captured.update({"table_name": table_name, "column_name": column_name,
                         "description": description, "schema_name": schema_name})

    monkeypatch.setattr(_km, "upsert_column_desc", _fake)
    events = _audit_capture(monkeypatch)
    resp = asyncio.run(admin_metadata.admin_create_column_desc(_FakeRequest({
        "scope_key": "default", "table_name": "orders", "column_name": "status",
        "description": "주문 상태"}), account=acct))  # schema_name 생략
    assert resp.status_code == 200
    assert captured["column_name"] == "status" and captured["schema_name"] == ""
    assert pg.committed is True
    assert any(e.get("action") == "column_desc.create" for e in events)


# ── TU/CU: update affected → 200/404 ───────────────────────────────────────────────

def test_table_update_affected_then_404(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _pg(monkeypatch)
    events = _audit_capture(monkeypatch)

    monkeypatch.setattr(_km, "update_table_desc", lambda *a, **k: 1)
    r = asyncio.run(admin_metadata.admin_update_table_desc(7, _FakeRequest({"scope_key": "common", "description": "d"}), account=acct))
    assert r.status_code == 200 and pg.committed is True
    upd = [e for e in events if e.get("action") == "table_desc.update"]
    # _metadata_audit 가 resource_id 를 str 화해 record_audit_event 로 넘긴다(MVP-1 동형).
    assert len(upd) == 1 and upd[0]["resource_id"] == "7"

    monkeypatch.setattr(_km, "update_table_desc", lambda *a, **k: 0)
    r2 = asyncio.run(admin_metadata.admin_update_table_desc(8, _FakeRequest({"scope_key": "common", "description": "d"}), account=acct))
    assert r2.status_code == 404


def test_column_update_404(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    monkeypatch.setattr(_km, "update_column_desc", lambda *a, **k: 0)
    r = asyncio.run(admin_metadata.admin_update_column_desc(5, _FakeRequest({"scope_key": "common", "description": "d"}), account=acct))
    assert r.status_code == 404


def test_table_update_partial_schema_rejected(monkeypatch):
    """table_name 없이 schema_name 만 수정 → 400."""
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    monkeypatch.setattr(_km, "update_table_desc", lambda *a, **k: 1)
    r = asyncio.run(admin_metadata.admin_update_table_desc(1, _FakeRequest({"scope_key": "common", "description": "d", "schema_name": "s"}), account=acct))
    assert r.status_code == 400


# ── TD: delete 멱등 ─────────────────────────────────────────────────────────────────

def test_table_delete_idempotent_audit(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    events = _audit_capture(monkeypatch)

    monkeypatch.setattr(_km, "delete_table_desc", lambda *a, **k: 1)
    r = admin_metadata.admin_delete_table_desc(3, _FakeRequest(query={"scope_key": "common"}), account=acct)
    assert r.status_code == 200 and _body(r)["deleted"] == 1
    assert any(e.get("action") == "table_desc.delete" for e in events)

    events.clear()
    monkeypatch.setattr(_km, "delete_table_desc", lambda *a, **k: 0)
    r2 = admin_metadata.admin_delete_table_desc(3, _FakeRequest(query={"scope_key": "common"}), account=acct)
    assert r2.status_code == 200 and _body(r2)["deleted"] == 0
    assert not events, "미삭제(affected=0) 시 audit 미기록"


# ── IV: 입력 cap ────────────────────────────────────────────────────────────────────

def test_input_validation_caps(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    monkeypatch.setattr(_km, "upsert_table_desc", lambda *a, **k: None)

    # 필수필드 누락(table_name) → 400
    r = asyncio.run(admin_metadata.admin_create_table_desc(_FakeRequest({"scope_key": "common", "description": "d"}), account=acct))
    assert r.status_code == 400
    # description cap=4000 초과 → 400
    r2 = asyncio.run(admin_metadata.admin_create_table_desc(_FakeRequest({"scope_key": "common", "table_name": "t", "description": "x" * 4001}), account=acct))
    assert r2.status_code == 400


# ── SWC: 샘플 weight clamp ──────────────────────────────────────────────────────────

def test_sample_weight_clamp(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    _audit_capture(monkeypatch)
    captured = {}
    monkeypatch.setattr(_sq, "update_sample",
                        lambda conn, sid, scope_key, **kw: (captured.update(kw) or 1))

    asyncio.run(admin_metadata.admin_update_sample(1, _FakeRequest({"scope_key": "common", "weight": 999999}), account=acct))
    assert captured["weight"] == 1000, "상한 1000 clamp"
    captured.clear()
    asyncio.run(admin_metadata.admin_update_sample(1, _FakeRequest({"scope_key": "common", "weight": -5}), account=acct))
    assert captured["weight"] == 1, "하한 1 clamp"


def test_sample_update_no_fields_400(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    called = {"hit": False}
    monkeypatch.setattr(_sq, "update_sample", lambda *a, **k: called.__setitem__("hit", True) or 1)
    r = asyncio.run(admin_metadata.admin_update_sample(1, _FakeRequest({"scope_key": "common"}), account=acct))
    assert r.status_code == 400 and called["hit"] is False


# ── SNL: 샘플 nl 중복 409 ───────────────────────────────────────────────────────────

class UniqueViolation(Exception):
    """코어가 던지는 UNIQUE 충돌 예외 시뮬레이트 — app.py 가 __class__.__name__ 으로 409 분기."""


def test_sample_nl_duplicate_409(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    _audit_capture(monkeypatch)

    def _raise(*a, **k):
        raise UniqueViolation("dup")

    monkeypatch.setattr(_sq, "update_sample", _raise)
    # 임베딩 동기 시도(nl 변경) — 벡터 반환되게 fake
    import modules.kb_retrieval as _kr
    monkeypatch.setattr(_kr, "_embed_query_vector", lambda t: [0.1] * 1024)
    r = asyncio.run(admin_metadata.admin_update_sample(1, _FakeRequest({"scope_key": "common", "nl_question": "중복 질문"}), account=acct))
    assert r.status_code == 409


# ── SEMB: 샘플 임베딩 하이브리드 C 분기 ─────────────────────────────────────────────

def test_sample_embed_active_on_nl_change(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    _audit_capture(monkeypatch)
    captured = {}
    monkeypatch.setattr(_sq, "update_sample",
                        lambda conn, sid, scope_key, **kw: (captured.update(kw) or 1))
    import modules.kb_retrieval as _kr
    monkeypatch.setattr(_kr, "_embed_query_vector", lambda t: [0.2] * 1024)  # 동기 성공

    r = asyncio.run(admin_metadata.admin_update_sample(1, _FakeRequest({"scope_key": "common", "nl_question": "활성 사용자 수"}), account=acct))
    assert r.status_code == 200 and _body(r)["embedding_status"] == "active"
    assert captured.get("embedding") and len(captured["embedding"]) == 1024


def test_sample_embed_stale_on_embed_failure(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    _audit_capture(monkeypatch)
    captured = {}
    monkeypatch.setattr(_sq, "update_sample",
                        lambda conn, sid, scope_key, **kw: (captured.update(kw) or 1))
    import modules.kb_retrieval as _kr
    monkeypatch.setattr(_kr, "_embed_query_vector", lambda t: None)  # 임베딩 실패

    r = asyncio.run(admin_metadata.admin_update_sample(1, _FakeRequest({"scope_key": "common", "nl_question": "신규 질문"}), account=acct))
    assert r.status_code == 200 and _body(r)["embedding_status"] == "stale"
    assert captured.get("embedding") is None, "실패 → None → 코어가 status='stale'"


def test_sample_embed_untouched_when_nl_unchanged(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    _pg(monkeypatch)
    _audit_capture(monkeypatch)
    captured = {}
    monkeypatch.setattr(_sq, "update_sample",
                        lambda conn, sid, scope_key, **kw: (captured.update({"kw": dict(kw)}) or 1))
    import modules.kb_retrieval as _kr
    embed_calls = {"n": 0}
    monkeypatch.setattr(_kr, "_embed_query_vector", lambda t: embed_calls.__setitem__("n", embed_calls["n"] + 1) or [0.0] * 1024)

    r = asyncio.run(admin_metadata.admin_update_sample(1, _FakeRequest({"scope_key": "common", "weight": 200}), account=acct))
    assert r.status_code == 200 and _body(r)["embedding_status"] is None
    assert "embedding" not in captured["kw"], "nl 미변경 → embedding touch 안 함"
    assert embed_calls["n"] == 0, "nl 미변경 → 임베딩 호출 안 함"


# ── BDS: bootstrap datasource 검증 ──────────────────────────────────────────────────

def test_bootstrap_unknown_datasource_404(monkeypatch):
    _allow_scopes(monkeypatch, scopes=("common", "default"))
    acct = _admin(monkeypatch)
    r = admin_metadata.admin_bootstrap_schemas(_FakeRequest(query={"datasource": "ghost"}), account=acct)
    assert r.status_code == 404
    r2 = asyncio.run(admin_metadata.admin_bootstrap(_FakeRequest({"datasource": "ghost", "schema": "dbo"}), account=acct))
    assert r2.status_code == 404


def test_bootstrap_common_rejected(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    r = admin_metadata.admin_bootstrap_schemas(_FakeRequest(query={"datasource": "common"}), account=acct)
    assert r.status_code == 400


def test_bootstrap_schemas_happy(monkeypatch):
    _allow_scopes(monkeypatch, scopes=("common", "default"))
    acct = _admin(monkeypatch)
    import shared.db as _db
    import modules.schema as _schema
    import shared.config as _cfg
    calls = []  # finally 의 reset(None) 까지 모든 호출 기록 — dialect 활성화→리셋 순서 확인.
    monkeypatch.setattr(_cfg, "set_active_datasource",
                        lambda key, engine=None, default_db=None: calls.append({"key": key, "engine": engine}))
    monkeypatch.setattr(_db, "connect", lambda **k: _BenignConn())
    monkeypatch.setattr(_schema, "load_known_schemas", lambda conn: ["dbo", "sales"])

    r = admin_metadata.admin_bootstrap_schemas(_FakeRequest(query={"datasource": "default"}), account=acct)
    assert r.status_code == 200
    out = _body(r)
    assert out["schemas"] == ["dbo", "sales"] and out["datasource"] == "default"
    # 첫 호출이 dialect 활성화(introspection 전) — engine 전달 + key=ds. 마지막은 reset(None).
    assert calls[0]["key"] == "default" and calls[0]["engine"] == "mysql"
    assert calls[-1]["key"] is None, "요청 컨텍스트 dialect 리셋"


# ── BSQLI: bootstrap schema_name SQL 인젝션 거부 (REV B1 BLOCKER 회귀) ────────────────

def test_bootstrap_schema_sqli_rejected(monkeypatch):
    """REV B1(BLOCKER) 회귀 — schema_name 이 dialect.describe_schema_tables 의 f-string SQL 에
    도달하기 전 _safe_ident + load_known_schemas allowlist 로 차단된다. 인젝션 페이로드 → 404 +
    골격 수집(_bootstrap_collect_skeleton) 미도달. 정상 schema 는 통과."""
    _allow_scopes(monkeypatch, scopes=("common", "default"))
    acct = _admin(monkeypatch)
    import shared.db as _db
    import modules.schema as _schema
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "set_active_datasource", lambda *a, **k: None)
    monkeypatch.setattr(_db, "connect", lambda **k: _BenignConn())
    monkeypatch.setattr(_schema, "load_known_schemas", lambda conn: ["dbo", "sales"])
    hit = {"n": 0}

    def _fake_collect(conn, _dialects, schema_name):
        hit["n"] += 1
        return []

    monkeypatch.setattr(app, "_bootstrap_collect_skeleton", _fake_collect)
    # 인젝션 페이로드(UNION/주석/따옴표) — allowlist 미포함 → 404, describe_schema_tables 미도달.
    payload = "dbo' UNION SELECT table_name FROM information_schema.tables --"
    r = asyncio.run(admin_metadata.admin_bootstrap(_FakeRequest({"datasource": "default", "schema": payload}), account=acct))
    assert r.status_code == 404, "인젝션 schema 는 allowlist 미포함 → 404"
    assert hit["n"] == 0, "골격 수집(describe_schema_tables 실행)에 도달하면 안 됨"
    # 정상 schema(allowlist 포함)는 통과 — 골격 수집 1회 호출.
    r2 = asyncio.run(admin_metadata.admin_bootstrap(_FakeRequest({"datasource": "default", "schema": "dbo"}), account=acct))
    assert r2.status_code == 200 and hit["n"] == 1


# ── INJ: 주입 단위 (load_table_column_descriptions) ─────────────────────────────────

class _InjCursor:
    def __init__(self, tables, cols):
        self._tables = tables
        self._cols = cols
        self._mode = None

    def execute(self, sql, params=None):
        self._mode = "tables" if "FROM table_descriptions" in sql else "cols"

    def fetchall(self):
        return self._tables if self._mode == "tables" else self._cols

    def close(self):
        return None


class _InjConn:
    def __init__(self, tables, cols):
        self._tables = tables
        self._cols = cols

    def cursor(self, *a, **k):
        return _InjCursor(self._tables, self._cols)


def test_injection_substring_match_and_scope(monkeypatch):
    # tables: (schema, table, description), cols: (table, column, description)
    tables = [("sales", "orders", "주문 마스터"), ("sales", "customers", "고객")]
    cols = [("orders", "status", "주문 상태코드"), ("orders", "amount", "금액")]
    conn = _InjConn(tables, cols)
    # scope 명시 → get_active_datasource 미사용 경로(BLOCKER 회피 확인은 default None→active 분기에서)
    out = _km.load_table_column_descriptions("orders 테이블의 status 를 보여줘", scope_key="default", conn=conn)
    assert "orders" in out and "주문 마스터" in out
    assert "status" in out and "주문 상태코드" in out
    # 질문에 등장하지 않는 customers/amount 는 미포함(substring 매칭).
    assert "customers" not in out and "amount" not in out


def test_injection_empty_when_no_match(monkeypatch):
    conn = _InjConn([("s", "orders", "d")], [("orders", "status", "d")])
    out = _km.load_table_column_descriptions("전혀 무관한 질문", scope_key="default", conn=conn)
    assert out == ""


def test_injection_section_wrapped_by_datamark(monkeypatch):
    """_build_knowledge_context 가 load 결과를 datamark 펜스로 감싸 주입한다(섹션 헤더 포함)."""
    import agent_core as _ac
    monkeypatch.setattr(_ac, "_load_schema_list", lambda conn: "")
    monkeypatch.setattr(_ac, "_load_relevant_table_insights", lambda conn, msg: "")
    import modules.kb_glossary as _kg
    monkeypatch.setattr(_kg, "load_glossary_enum_context", lambda *a, **k: "")
    monkeypatch.setattr(_km, "load_table_column_descriptions", lambda *a, **k: "테이블 설명:\n- sales.orders — 주문")
    # 샘플/회상 경로는 무력화(섹션 격리).
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "AGENT_SAMPLE_QUERIES_ENABLED", False, raising=False)

    ctx = _ac._build_knowledge_context(_BenignConn(), "orders 분석", [])
    assert "TABLE & COLUMN DESCRIPTIONS" in ctx
    assert "주문" in ctx


# ── scope-key-unify 회귀(死data 방지): admin write 의 허용 scope = 해시 축(read 와 동일) ──────────────
def test_valid_scope_keys_uses_hash_axis_not_label(monkeypatch):
    """死data 회귀 가드 — admin write 가 허용/저장하는 scope_key 는 datasource **안정 scope_key**
    (_dsr.scope_key = compute_scope_key 해시; .env 레거시는 라벨 폴백)이지, datasource 라벨(dict 키)이
    아니다. 질의 시점 read(get_active_datasource = agent_core 가 _ds['scope_key'] 채택)와 **동일 축**이라야
    DB-등록 ds 의 ds-scoped 설명/샘플이 읽힌다. 과거(라벨 저장)엔 라벨≠해시 로 영영 안 읽히는 死data 였다.
    이 테스트는 WebDatasources 경로(라벨≠해시)를 모사해 그 회귀를 잡는다(기존 27 케이스는 .env 동형 fake)."""
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    import shared.datasources as _dsr
    # DB-등록 ds 모사: 라벨(dict 키/key) 'prod_mysql' 과 안정 해시 scope_key 'mysql-deadbeef0001' 이 다름.
    ds_map = {"prod_mysql": {"key": "prod_mysql", "engine": "mysql", "host": "db.internal",
                             "port": 3306, "scope_key": "mysql-deadbeef0001", "_source": "db"}}
    monkeypatch.setattr(_dsr, "all_datasources", lambda conn: ds_map)

    valid = app._metadata_valid_scope_keys()
    assert "mysql-deadbeef0001" in valid, "read 와 동일한 해시 축이 허용돼야 한다(死data 해소)"
    assert "prod_mysql" not in valid, "라벨(과거 死data 축)은 더 이상 허용하지 않는다"
    assert "common" in valid, "'common' 공용 scope 는 항상 허용"

    # _metadata_check_scope 도 해시는 통과(200), 라벨은 거부(400)해야 한다.
    norm, err = app._metadata_check_scope("mysql-deadbeef0001")
    assert err is None and norm == "mysql-deadbeef0001"
    _norm2, err2 = app._metadata_check_scope("prod_mysql")
    assert err2 is not None and getattr(err2, "status_code", None) == 400


def test_valid_scope_keys_env_legacy_uses_label_not_hash(monkeypatch):
    """死data **역방향** 회귀 가드 — .env 레거시 datasource(scope_key 필드 부재 + host 보유)에서 admin write 의
    허용 scope 는 **라벨**이어야 한다. 질의 시점 read(agent_core.set_active_datasource = `_ds.get('scope_key')
    or _ds.get('key')`)가 필드 부재 시 라벨로 떨어지므로, write 도 동일해야 일치한다. write 를 `_dsr.scope_key`
    (host 보유 .env 에서 해시 *계산*)로 잡으면 write(해시)≠read(라벨) 死data 가 역으로 재발 → 이 테스트가 잡는다."""
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    import shared.datasources as _dsr
    # .env 레거시 모사: scope_key 필드 없음 + host 보유(.env 는 host 필수). dict 키 = 라벨.
    ds_map = {"reporting": {"key": "reporting", "engine": "mysql", "host": "rep.internal", "port": 3306}}
    monkeypatch.setattr(_dsr, "all_datasources", lambda conn: ds_map)

    valid = app._metadata_valid_scope_keys()
    assert "reporting" in valid, ".env 레거시는 라벨로 허용(read 와 동일 축)"
    # _dsr.scope_key 가 계산했을 해시는 허용 집합에 없어야 한다(역방향 死data 방지).
    import hashlib
    hashed = "mysql-" + hashlib.sha256(b"mysql:rep.internal:3306").hexdigest()[:12]
    assert hashed not in valid, "write 가 _dsr.scope_key(해시)로 새면 read(라벨)와 어긋나 死data 역재발"
    assert "common" in valid
    # read 동치 확인: write 허용 라벨 == read 가 잡는 활성 scope(scope_key or key).
    _ds = ds_map["reporting"]
    assert (_ds.get("scope_key") or _ds.get("key")) == "reporting"


# ── §58: 스키마 골격 가져오기 — MSSQL 저장 라벨 lower 계약 ─────────────────────
def test_bootstrap_skeleton_mssql_schema_label_lowercased(monkeypatch):
    """§58: MSSQL 골격 저장 schema_name(=DB명 라벨)은 normalize_db_label lower 계약(TASK-0220·
    §56 RC5 와 단일 계약) — 원본 케이스 저장 시 cadence(lower) 축과 케이스-변형 이중 적재(라이브
    실측 'AccountDB' 33행·AGE 중복 스키마 카드). 테이블명 케이스·질의용 원본 db_name 은 보존."""
    from modules import schema as schema_mod

    class _Dialect:
        def system_schemas(self):
            return ["sys", "information_schema"]

        def describe_schema_tables(self, s):
            return f"TABLES::{s}"

        def describe_columns(self, s, t):
            return f"COLS::{s}::{t}"

    class _Dialects:
        def active(self):
            return _Dialect()

    class _Cur:
        def __init__(self):
            self.sql = ""

        def execute(self, sql, *a):
            self.sql = str(sql)

        def fetchall(self):
            if self.sql.startswith("TABLES::"):
                return [("FH_CHAR",)]
            if self.sql.startswith("COLS::"):
                return [("Id", "int")]
            return []

        def close(self):
            pass

    class _Conn:
        def cursor(self):
            return _Cur()

    executed = []

    class _RecCur(_Cur):
        def execute(self, sql, *a):
            super().execute(sql, *a)
            executed.append(self.sql)

    class _RecConn:
        def cursor(self):
            return _RecCur()

    # 혼합 케이스 SQL 스키마로 질의 원본 케이스 유지까지 잠금(적대 리뷰 MINOR — lower 확대 적용 회귀 방지).
    monkeypatch.setattr(schema_mod, "load_known_schemas", lambda conn: ["Sales"])
    out = app._bootstrap_collect_skeleton_mssql(_RecConn(), _Dialects(), "FHGame1")
    assert out and all(r["schema_name"] == "fhgame1" for r in out)
    assert out[0]["table_name"] == "FH_CHAR"   # 테이블명 케이스는 보존(라벨 축만 정규화)
    assert any(s == "TABLES::Sales" for s in executed)          # 질의 스키마 식별자 원본 케이스
    assert any(s.startswith("COLS::Sales::") for s in executed)


def test_metadata_introspect_table_grounding_case_insensitive(monkeypatch):
    """§58 적대 리뷰 MAJOR 회귀 잠금: 저장 라벨이 lower 가 된 뒤에도 MSSQL grounding allowlist 가
    case-insensitive 로 매치되고 **연결은 서버 원본 케이스**로 수행된다(무음 grounding 파괴 방지)."""
    from modules import schema as schema_mod
    import shared.db as sdb

    class _Dialect:
        def system_databases(self):
            return ["master", "tempdb", "model", "msdb"]

        def system_schemas(self):
            return ["sys", "information_schema"]

        def describe_columns(self, s, t):
            return f"COLS::{s}::{t}"

    class _Dialects:
        def active(self):
            return _Dialect()

    class _Cur:
        def __init__(self):
            self.sql = ""

        def execute(self, sql, *a):
            self.sql = str(sql)

        def fetchall(self):
            return [("Id", "int")] if self.sql.startswith("COLS::") else []

        def close(self):
            pass

    class _Conn:
        def cursor(self):
            return _Cur()

        def close(self):
            pass

    connected = {}

    from modules import dialects as dialects_mod
    monkeypatch.setattr(app, "_bootstrap_resolve_datasource",
                        lambda key: ({"key": key, "engine": "mssql"}, "mssql-abc", None))
    monkeypatch.setattr(app, "_bootstrap_activate_dialect", lambda ds, sk: "mssql")
    monkeypatch.setattr(dialects_mod, "active", lambda: _Dialect())
    monkeypatch.setattr(sdb, "list_server_databases", lambda ds, timeout=None: ["FHGame1"])

    def _fake_connect(datasource=None, database=None, autocommit=True):
        connected["database"] = database
        return _Conn()

    monkeypatch.setattr(sdb, "connect", _fake_connect)
    monkeypatch.setattr(schema_mod, "load_known_schemas", lambda conn: ["dbo"])
    got = app._metadata_introspect_table("mssql-qa", "fhgame1", "FH_CHAR")   # lower 라벨 입력
    assert got and got["columns"] and got["columns"][0]["column_name"] == "Id"
    assert connected["database"] == "FHGame1"   # 연결은 서버 원본 케이스
