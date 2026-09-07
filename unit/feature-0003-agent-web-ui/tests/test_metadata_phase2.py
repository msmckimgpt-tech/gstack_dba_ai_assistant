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
    # metadata-product-scope: 허용 scope 원천이 datasource → **제품 카탈로그**로 바뀌었다.
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    from routers import admin_metadata as _am
    catalog = [{"scope_key": k, "product_id": i + 1, "product_key": k, "name": k,
                "sort_order": 100, "datasources": [], "databases": []}
               for i, k in enumerate(s for s in scopes if s != "common")]
    monkeypatch.setattr(_am, "_product_scope_catalog", lambda conn=None: catalog)


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


def test_sample_embed_unavailable_on_embed_failure(monkeypatch):
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
    assert r.status_code == 200 and _body(r)["embedding_status"] == "unavailable"
    assert captured.get("embedding") is None, "실패 → None, 문자 검색과 신선도는 별개"


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

def test_bootstrap_unknown_scope_404(monkeypatch):
    """metadata-product-scope: 축이 제품이므로 미등록/비활성 제품 스코프는 404, scope 미지정은 400."""
    _allow_scopes(monkeypatch, scopes=("common", "default"))
    acct = _admin(monkeypatch)
    r = admin_metadata.admin_bootstrap_schemas(
        _FakeRequest(query={"scope_key": "product.ghost"}), account=acct)
    assert r.status_code == 404
    r2 = asyncio.run(admin_metadata.admin_bootstrap(
        _FakeRequest({"scope_key": "product.ghost", "schema": "dbo"}), account=acct))
    assert r2.status_code == 404
    r3 = admin_metadata.admin_bootstrap_schemas(_FakeRequest(query={}), account=acct)
    assert r3.status_code == 400


def test_bootstrap_common_rejected(monkeypatch):
    """'공용' 스코프는 특정 제품에 매이지 않아 골격 대상이 아니다(404 — 축이 제품)."""
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    r = admin_metadata.admin_bootstrap_schemas(_FakeRequest(query={"scope_key": "common"}), account=acct)
    assert r.status_code == 404


def _allow_datasources(monkeypatch, ds_keys=("default",)):
    """부트스트랩 폴백 경로(접근DB 미선언 제품)용 — datasource 레지스트리 fake."""
    import shared.datasources as _dsr
    ds_map = {k: {"key": k, "engine": "mysql", "scope_key": k} for k in ds_keys}
    monkeypatch.setattr(_dsr, "all_datasources", lambda conn: ds_map)


def _allow_product_with_databases(monkeypatch, scope_key, databases, ds_key="default",
                                  databases_ok=True):
    """제품 카탈로그 fake — 접근DB(WebProductDatabases) 선언 포함. databases_ok=False 는 카탈로그
    읽기 실패(경계 판정 불가) 상태 — 소비처가 fail-closed 인지 검증할 때 쓴다."""
    from routers import admin_metadata as _am
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(_am, "_product_scope_catalog", lambda conn=None: [{
        "scope_key": scope_key, "product_id": 1, "product_key": scope_key.split(".")[-1],
        "name": "제품", "sort_order": 1,
        "datasources": [{"key": ds_key, "is_primary": True}],
        "databases": [{"schema": d, "datasource_key": ds_key} for d in databases],
        "databases_ok": databases_ok,
    }])


def test_bootstrap_schemas_from_product_databases(monkeypatch):
    """metadata-product-scope — 골격 후보는 그 **제품의 접근DB**로 한정되고, 라이브 introspection
    없이 즉답한다(서버 전체 스키마 나열 금지 = 제품 경계 밖 DB 미노출)."""
    _allow_product_with_databases(monkeypatch, "product.cc_qa", ["cc_data_main", "CC_GAMEDB"])
    acct = _admin(monkeypatch)
    import shared.db as _db
    monkeypatch.setattr(_db, "connect", lambda **k: (_ for _ in ()).throw(
        AssertionError("접근DB 선언 제품은 라이브 introspection 을 하지 않아야 한다")))

    r = admin_metadata.admin_bootstrap_schemas(
        _FakeRequest(query={"scope_key": "product.cc_qa"}), account=acct)
    assert r.status_code == 200
    out = _body(r)
    assert out["schemas"] == ["cc_data_main", "CC_GAMEDB"]
    assert out["source"] == "product-databases" and out["scope_key"] == "product.cc_qa"


def test_bootstrap_schemas_happy(monkeypatch):
    """접근DB 미선언 제품 → 제품의 primary datasource 를 introspect 하는 폴백 경로."""
    _allow_product_with_databases(monkeypatch, "product.legacy", [], ds_key="default")
    _allow_datasources(monkeypatch, ("default",))
    acct = _admin(monkeypatch)
    import shared.db as _db
    import modules.schema as _schema
    import shared.config as _cfg
    calls = []  # finally 의 reset(None) 까지 모든 호출 기록 — dialect 활성화→리셋 순서 확인.
    monkeypatch.setattr(_cfg, "set_active_datasource",
                        lambda key, engine=None, default_db=None: calls.append({"key": key, "engine": engine}))
    monkeypatch.setattr(_db, "connect", lambda **k: _BenignConn())
    monkeypatch.setattr(_schema, "load_known_schemas", lambda conn: ["dbo", "sales"])

    r = admin_metadata.admin_bootstrap_schemas(
        _FakeRequest(query={"scope_key": "product.legacy"}), account=acct)
    assert r.status_code == 200
    out = _body(r)
    assert out["schemas"] == ["dbo", "sales"] and out["datasource"] == "default"
    assert out["source"] == "introspect"
    # 첫 호출이 dialect 활성화(introspection 전) — engine 전달 + key=ds. 마지막은 reset(None).
    assert calls[0]["key"] == "default" and calls[0]["engine"] == "mysql"
    assert calls[-1]["key"] is None, "요청 컨텍스트 dialect 리셋"


# ── BSQLI: bootstrap schema_name SQL 인젝션 거부 (REV B1 BLOCKER 회귀) ────────────────

def test_bootstrap_schema_sqli_rejected(monkeypatch):
    """REV B1(BLOCKER) 회귀 — schema_name 이 dialect.describe_schema_tables 의 f-string SQL 에
    도달하기 전 _safe_ident + load_known_schemas allowlist 로 차단된다. 인젝션 페이로드 → 404 +
    골격 수집(_bootstrap_collect_skeleton) 미도달. 정상 schema 는 통과."""
    _allow_product_with_databases(monkeypatch, "product.legacy", [], ds_key="default")
    _allow_datasources(monkeypatch, ("default",))
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
    r = asyncio.run(admin_metadata.admin_bootstrap(
        _FakeRequest({"scope_key": "product.legacy", "schema": payload}), account=acct))
    assert r.status_code == 404, "인젝션 schema 는 allowlist 미포함 → 404"
    assert hit["n"] == 0, "골격 수집(describe_schema_tables 실행)에 도달하면 안 됨"
    # 정상 schema(allowlist 포함)는 통과 — 골격 수집 1회 호출.
    r2 = asyncio.run(admin_metadata.admin_bootstrap(
        _FakeRequest({"scope_key": "product.legacy", "schema": "dbo"}), account=acct))
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
def test_valid_scope_keys_uses_product_axis(monkeypatch):
    """metadata-product-scope — admin write 가 허용/저장하는 scope_key 는 **제품 스코프**
    (`product.<ProductKey>`)다. datasource 라벨/해시는 더 이상 허용 축이 아니다.

    배경(라이브 실측): 축이 양방향으로 어긋나 있었다 — 1제품↔N데이터소스(KR_LIVE 7개 DS)에서는
    등록분이 그 중 1개 DS 질의에서만 주입되고, 1데이터소스↔N제품(mssql-qa-idc 를 5개 제품 공유)
    에서는 타 제품 메타데이터가 혼입됐다. 본 테스트가 축 회귀(=datasource 축 복귀)를 잡는다."""
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    from routers import admin_metadata as _am
    monkeypatch.setattr(_am, "_list_products", None, raising=False)
    # 제품 2개(공유 datasource 포함) — 카탈로그는 제품 축만 노출한다.
    monkeypatch.setattr(app, "_list_products", lambda conn: [
        {"id": 111, "product_key": "FH_QA", "name": "출조낚시왕 - QA", "sort_order": 10,
         "datasources": [{"datasource_key": "mssql-qa-idc", "is_primary": True}]},
        {"id": 113, "product_key": "CC_QA", "name": "콜오브카오스 - QA", "sort_order": 20,
         "datasources": [{"datasource_key": "mssql-qa-idc", "is_primary": True}]},
    ])

    valid = app._metadata_valid_scope_keys()
    assert "product.fh_qa" in valid and "product.cc_qa" in valid, "제품 스코프가 허용 축"
    assert "mssql-qa-idc" not in valid, "datasource 라벨은 더 이상 허용 축이 아니다"
    assert "common" in valid, "'common' 공용 scope 는 항상 허용"

    # _metadata_check_scope 도 제품 스코프는 통과, datasource 라벨은 거부(400).
    norm, err = app._metadata_check_scope("product.fh_qa")
    assert err is None and norm == "product.fh_qa"
    _norm2, err2 = app._metadata_check_scope("mssql-qa-idc")
    assert err2 is not None and getattr(err2, "status_code", None) == 400


def test_shared_datasource_products_get_distinct_scopes(monkeypatch):
    """공유 datasource 회귀 가드 — 한 datasource 를 N개 제품이 쓰면 제품마다 **다른** scope 를 받아야
    한다(종전 datasource 축에서는 같은 scope 라 서로의 메타데이터가 섞였다)."""
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_list_products", lambda conn: [
        {"id": 1, "product_key": "A", "name": "A", "sort_order": 1,
         "datasources": [{"datasource_key": "shared-ds", "is_primary": True}]},
        {"id": 2, "product_key": "B", "name": "B", "sort_order": 2,
         "datasources": [{"datasource_key": "shared-ds", "is_primary": True}]},
    ])
    from routers import admin_metadata as _am
    catalog = _am._product_scope_catalog()
    keys = [e["scope_key"] for e in catalog]
    assert keys == ["product.a", "product.b"], keys
    assert len(set(keys)) == 2, "공유 datasource 라도 제품별로 scope 가 분리돼야 한다"


def test_scope_database_units_limited_to_product_databases(monkeypatch):
    """부트스트랩 골격 후보는 그 **제품의 접근DB**(WebProductDatabases)로 한정된다 — 서버 전체
    스키마를 나열하던 종전 datasource 축은 제품 경계 밖 DB 까지 콘솔에 노출했다."""
    from routers import admin_metadata as _am
    monkeypatch.setattr(_am, "_product_scope_catalog", lambda conn=None: [
        {"scope_key": "product.cc_qa", "product_id": 113, "product_key": "CC_QA", "name": "CC",
         "sort_order": 1, "datasources": [{"key": "mssql-qa-idc", "is_primary": True}],
         "databases": [{"schema": "cc_data_main", "datasource_key": "mssql-qa-idc"},
                       {"schema": "CC_GAMEDB", "datasource_key": "mssql-qa-idc"}]},
    ])
    units = _am._scope_database_units("product.cc_qa")
    assert [u["schema"] for u in units] == ["cc_data_main", "CC_GAMEDB"]
    # 물리 연결은 (제품, 접근DB) 바인딩에서 서버가 해소한다 — 프론트는 datasource 를 모른다.
    assert _am._scope_datasource_for_schema("product.cc_qa", "cc_data_main") == "mssql-qa-idc"
    # 제품 경계 강제(codex review P1): 접근DB 선언 제품에서 allowlist 밖 schema 는 primary 로
    # 폴백하지 않는다 — 폴백하면 임의 schema 로 그 제품 경계 밖 DB 를 introspect·저장할 수 있다.
    assert _am._scope_datasource_for_schema("product.cc_qa", "unknown_db") == ""
    # 'common' 은 특정 제품이 아니므로 골격 대상 없음.
    assert _am._scope_database_units("common") == []


def test_bootstrap_rejects_schema_outside_product_databases(monkeypatch):
    """제품 경계 강제 회귀 가드(codex review P1) — 접근DB allowlist 밖 schema 는 404, 실제
    introspection(_bootstrap_collect_skeleton)에 도달하지 않는다."""
    _allow_product_with_databases(monkeypatch, "product.cc_qa", ["cc_data_main"], ds_key="default")
    _allow_datasources(monkeypatch, ("default",))
    acct = _admin(monkeypatch)
    import shared.db as _db
    import modules.schema as _schema
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "set_active_datasource", lambda *a, **k: None)
    monkeypatch.setattr(_db, "connect", lambda **k: _BenignConn())
    monkeypatch.setattr(_schema, "load_known_schemas", lambda conn: ["cc_data_main", "other_product_db"])
    hit = {"n": 0}
    monkeypatch.setattr(app, "_bootstrap_collect_skeleton",
                        lambda conn, _d, schema_name: (hit.__setitem__("n", hit["n"] + 1), [])[1])

    # allowlist 밖 — 서버 전체 스키마엔 있지만 이 제품의 접근DB 가 아니다.
    r = asyncio.run(admin_metadata.admin_bootstrap(
        _FakeRequest({"scope_key": "product.cc_qa", "schema": "other_product_db"}), account=acct))
    assert r.status_code == 404
    assert hit["n"] == 0, "제품 경계 밖 DB 는 introspection 에 도달하면 안 된다"

    # allowlist 안 — 정상 통과.
    r2 = asyncio.run(admin_metadata.admin_bootstrap(
        _FakeRequest({"scope_key": "product.cc_qa", "schema": "cc_data_main"}), account=acct))
    assert r2.status_code == 200 and hit["n"] == 1


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


def test_bootstrap_fails_closed_when_product_db_catalog_unavailable(monkeypatch):
    """접근DB 카탈로그 읽기 실패는 '접근DB 없음'과 구별돼 fail-closed 여야 한다(codex review P1).

    동일시하면 transient DB 오류만으로 경계가 무력화되고 서버 전체 DB 로 폴백한다."""
    _allow_product_with_databases(monkeypatch, "product.cc_qa", ["cc_data_main"],
                                  ds_key="default", databases_ok=False)
    _allow_datasources(monkeypatch, ("default",))
    acct = _admin(monkeypatch)
    import shared.db as _db
    monkeypatch.setattr(_db, "connect", lambda **k: (_ for _ in ()).throw(
        AssertionError("카탈로그 미가용 시 라이브 introspection 에 도달하면 안 된다")))

    r = admin_metadata.admin_bootstrap_schemas(
        _FakeRequest(query={"scope_key": "product.cc_qa"}), account=acct)
    assert r.status_code == 503
    r2 = asyncio.run(admin_metadata.admin_bootstrap(
        _FakeRequest({"scope_key": "product.cc_qa", "schema": "cc_data_main"}), account=acct))
    assert r2.status_code == 503


def test_bootstrap_ignores_caller_datasource_override(monkeypatch):
    """호출자 지정 `datasource` override 제거 회귀 가드(codex review P1) — override 를 실어도
    제품 경계 해소를 우회하지 못한다(경계 밖 schema 는 404)."""
    _allow_product_with_databases(monkeypatch, "product.cc_qa", ["cc_data_main"], ds_key="default")
    _allow_datasources(monkeypatch, ("default", "other-ds"))
    acct = _admin(monkeypatch)
    import shared.db as _db
    import modules.schema as _schema
    import shared.config as _cfg
    monkeypatch.setattr(_cfg, "set_active_datasource", lambda *a, **k: None)
    monkeypatch.setattr(_db, "connect", lambda **k: _BenignConn())
    monkeypatch.setattr(_schema, "load_known_schemas", lambda conn: ["cc_data_main", "foreign_db"])
    hit = {"n": 0}
    monkeypatch.setattr(app, "_bootstrap_collect_skeleton",
                        lambda conn, _d, schema_name: (hit.__setitem__("n", hit["n"] + 1), [])[1])

    r = asyncio.run(admin_metadata.admin_bootstrap(_FakeRequest(
        {"scope_key": "product.cc_qa", "schema": "foreign_db", "datasource": "other-ds"}), account=acct))
    assert r.status_code == 404, "override 로 제품 경계를 우회할 수 없어야 한다"
    assert hit["n"] == 0


def test_legacy_access_db_row_without_datasource_key_resolves(monkeypatch):
    """레거시 접근DB 행(DatasourceKey 빈값)도 제품 primary 로 해소된다(codex review P1).

    `_list_product_databases` 는 DatasourceKey 컬럼 미이전 스키마에서 그 필드가 빈 행을 낸다.
    거부하면 목록엔 뜨는데 골격/grounding 만 죽는다. 단 경계는 여전히 schema 멤버십이 정한다."""
    from routers import admin_metadata as _am
    monkeypatch.setattr(_am, "_product_scope_catalog", lambda conn=None: [{
        "scope_key": "product.legacy", "product_id": 1, "product_key": "legacy", "name": "L",
        "sort_order": 1, "datasources": [{"key": "primary-ds", "is_primary": True}],
        "databases": [{"schema": "legacy_db", "datasource_key": ""}],
        "databases_ok": True,
    }])
    assert _am._scope_datasource_for_schema("product.legacy", "legacy_db") == "primary-ds"
    # allowlist 밖은 여전히 거부(폴백이 경계를 뚫지 않는다).
    assert _am._scope_datasource_for_schema("product.legacy", "other_db") == ""


def test_catalog_datasources_falls_back_to_legacy_single_binding():
    """카탈로그가 레거시 단일 바인딩(WebProducts.DatasourceKey)도 반드시 노출한다(codex review P1).

    비면 `_scope_primary_datasource` 가 빈 값을 내 정상 제품의 부트스트랩이 통째로 막힌다."""
    from routers import admin_metadata as _am
    assert _am._catalog_datasources({"datasources": [], "datasource_key": "legacy-ds"}) == [
        {"key": "legacy-ds", "is_primary": True}]
    # 1:N 바인딩이 있으면 그쪽이 우선.
    assert _am._catalog_datasources({
        "datasources": [{"datasource_key": "A", "is_primary": True}], "datasource_key": "legacy-ds",
    }) == [{"key": "a", "is_primary": True}]
    assert _am._catalog_datasources({}) == []


def test_bootstrap_mssql_database_allowlist_case_insensitive(monkeypatch):
    """MSSQL 접근DB 는 §58 lower 계약으로 저장되고 서버 catalog 는 원본 케이스다 — 케이스-정확
    비교면 정상 DB 가 404 로 거부된다(codex review P2). 연결은 원본 케이스로 이뤄져야 한다."""
    _allow_product_with_databases(monkeypatch, "product.fh_qa", ["fhgame1"], ds_key="mssql-ds")
    acct = _admin(monkeypatch)
    import shared.db as _db
    import shared.config as _cfg
    import shared.datasources as _dsr
    monkeypatch.setattr(_dsr, "all_datasources",
                        lambda conn: {"mssql-ds": {"key": "mssql-ds", "engine": "mssql", "scope_key": "mssql-ds"}})
    monkeypatch.setattr(_cfg, "set_active_datasource", lambda *a, **k: None)
    monkeypatch.setattr(_db, "list_server_databases", lambda ds: ["FHGame1", "master"])
    seen = {}
    monkeypatch.setattr(_db, "connect", lambda **k: (seen.update(k), _BenignConn())[1])
    monkeypatch.setattr(app, "_bootstrap_collect_skeleton_mssql",
                        lambda conn, _d, db_name: (seen.update({"collect_db": db_name}), [])[1])

    r = asyncio.run(admin_metadata.admin_bootstrap(
        _FakeRequest({"scope_key": "product.fh_qa", "schema": "fhgame1"}), account=acct))
    assert r.status_code == 200, "lower 저장 라벨이 원본-케이스 catalog 와 매칭돼야 한다"
    assert seen.get("database") == "FHGame1", "연결은 서버 원본 케이스로"
    assert seen.get("collect_db") == "FHGame1"
