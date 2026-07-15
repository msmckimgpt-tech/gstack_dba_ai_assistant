"""TASK-20260624-item11-metadata-glossary-enum (ROADMAP dba-ai-nl2sql ITEM-11 MVP-1) — 회귀/보안 테스트.

메타데이터 거버넌스(용어사전/ENUM 코드사전) CRUD 의 web 층(feature-0003)을 DB 없이 monkeypatch/fake
로 검증한다. CRUD 정본은 feature-0002 modules.kb_glossary — 여기서는 web 경계(RBAC/audit/scope/입력검증/
cross-DB conn 분리)만 검증한다.

검증 대상:
  R1   kb.ingest.manual 권한이 PERMISSION_DEFINITIONS(group=kb) + PERMISSION_CODES 에 존재.
  R2   admin seed(=set(PERMISSION_CODES)) 에 포함 / operator·sales·pending 미포함(least-privilege).
  G403 GET/POST/PUT/DELETE glossary — kb.ingest.manual 미보유 → 403 (코어 미호출).
  E403 GET/POST/PUT/DELETE enums   — kb.ingest.manual 미보유 → 403 (코어 미호출).
  GC   glossary 생성 — upsert_glossary_term 호출(scope/term/definition) + commit + audit(glossary.term.create).
  GU   glossary 수정 — update_glossary_term affected>0 → 200 + audit. affected=0 → 404.
  GD   glossary 삭제(멱등) — affected>0 → 200+audit, affected=0 → 200(audit 미기록).
  EC   enum 생성 — upsert_enum_entry 호출(schema 선택) + commit + audit(enum.entry.create).
  EU   enum 수정 — affected=0 → 404.
  SV   scope 검증 — 미허용 scope_key → 400 (코어 미호출). 빈 scope_key → 400.
  IV   입력 검증 — 필수필드 누락 → 400. 길이 cap 초과 → 400.
  LST  list 직렬화 — rows → items(id 포함) + scope_key 반향.

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


# ── Fakes ──────────────────────────────────────────────────────────────────────

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
    """memory(MySQL) conn 대용 — auth/audit/scope-allow 경로의 무해 conn."""

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
    """PG(agent_kb) conn 대용 — kb_glossary CRUD 가 받는 conn."""

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
    """_metadata_valid_scope_keys 가 부르는 datasources.all_datasources 를 fake — 허용 scope 집합 고정.

    scope-key-unify: valid scope 는 dict 키(라벨)가 아니라 _dsr.scope_key(ds)(해시 축)다. fake ds 의
    scope_key 필드를 scope 이름으로 채워 그 scope 가 허용되게 한다(real _dsr.scope_key 는 scope_key 우선).
    """
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    import shared.datasources as _dsr
    ds_map = {k: {"key": k, "engine": "mysql", "scope_key": k} for k in scopes if k != "common"}
    monkeypatch.setattr(_dsr, "all_datasources", lambda conn: ds_map)


def _admin(monkeypatch):
    acct = {"id": 1, "username": "admin", "permissions": {"kb.ingest.manual": True, "metadata.glossary.read": True, "metadata.glossary.create": True, "metadata.glossary.update": True, "metadata.glossary.delete": True, "metadata.enum.read": True, "metadata.enum.create": True, "metadata.enum.update": True, "metadata.enum.delete": True, "metadata.table.read": True, "metadata.table.create": True, "metadata.table.update": True, "metadata.table.delete": True, "metadata.column.read": True, "metadata.column.create": True, "metadata.column.update": True, "metadata.column.delete": True}}
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


def _nobody(monkeypatch):
    acct = {"id": 9, "username": "op", "permissions": {"console.access": True}}  # kb.ingest.manual 없음
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    return acct


# ── R1/R2: RBAC 카탈로그/시드 ─────────────────────────────────────────────────────

def test_permission_in_catalog():
    assert "kb.ingest.manual" in app.PERMISSION_CODES
    defn = app.PERMISSION_DEFINITION_MAP["kb.ingest.manual"]
    assert defn["group"] == "kb"


def test_permission_in_admin_seed_not_in_stock_roles():
    admin = next(r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin")
    assert "kb.ingest.manual" in set(admin["permissions"]), "admin seed=set(PERMISSION_CODES) → 보유"
    for key in ("operator", "sales", "pending"):
        role = next((r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == key), None)
        if role is not None:
            assert "kb.ingest.manual" not in set(role["permissions"]), f"{key} 는 미보유(least-privilege)"


# ── G403/E403: 권한 게이트 403 (코어 미호출) ───────────────────────────────────────

def test_glossary_endpoints_require_permission(monkeypatch, client, as_account):
    as_account(perms={"console.access": True})  # kb.ingest.manual 없음 → require_permission 403
    called = {"hit": False}
    for fn in ("list_glossary_admin", "upsert_glossary_term", "update_glossary_term", "delete_glossary_term"):
        monkeypatch.setattr(_kg, fn, lambda *a, **k: called.__setitem__("hit", True) or [])

    assert client.get("/api/admin/metadata/glossary?scope_key=common").status_code == 403
    assert client.post("/api/admin/metadata/glossary", json={"scope_key": "common", "term": "t", "definition": "d"}).status_code == 403
    assert client.put("/api/admin/metadata/glossary/1", json={"scope_key": "common", "term": "t", "definition": "d"}).status_code == 403
    assert client.delete("/api/admin/metadata/glossary/1?scope_key=common").status_code == 403
    assert called["hit"] is False, "권한 거부 시 코어 미호출(보안 핵심)"


def test_enum_endpoints_require_permission(monkeypatch, client, as_account):
    as_account(perms={"console.access": True})  # kb.ingest.manual 없음 → require_permission 403
    called = {"hit": False}
    for fn in ("list_enum_admin", "upsert_enum_entry", "update_enum_entry", "delete_enum_entry"):
        monkeypatch.setattr(_kg, fn, lambda *a, **k: called.__setitem__("hit", True) or [])

    enum_body = {"scope_key": "common", "table_name": "t", "column_name": "c", "code": "1", "label": "l"}
    assert client.get("/api/admin/metadata/enums?scope_key=common").status_code == 403
    assert client.post("/api/admin/metadata/enums", json=enum_body).status_code == 403
    assert client.put("/api/admin/metadata/enums/1", json=enum_body).status_code == 403
    assert client.delete("/api/admin/metadata/enums/1?scope_key=common").status_code == 403
    assert called["hit"] is False


# ── GC: glossary 생성 ─────────────────────────────────────────────────────────────

def test_glossary_create_calls_core_and_audits(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    captured = {}
    # 0021: upsert_glossary_term 시그니처에 role_key/source 추가(기본 '*'/'manual').
    monkeypatch.setattr(_kg, "upsert_glossary_term",
                        lambda conn, scope_key, term, definition, role_key="*", source="manual": captured.update(
                            {"conn": conn, "scope_key": scope_key, "term": term, "definition": definition,
                             "role_key": role_key, "source": source}))
    events = _audit_capture(monkeypatch)

    resp = asyncio.run(admin_metadata.admin_create_glossary(_FakeRequest({
        "scope_key": "default", "term": "  활성 사용자  ", "definition": "  최근 30일 로그인  "}), account=acct))
    assert resp.status_code == 200
    assert captured["conn"] is pg, "PG(agent_kb) conn 으로 적재"
    assert captured["scope_key"] == "default"
    assert captured["term"] == "활성 사용자"
    assert captured["definition"] == "최근 30일 로그인"
    assert captured["role_key"] == "*"   # role_key 미지정 → 공용 기본
    assert pg.committed is True
    assert any(e.get("action") == "glossary.term.create" for e in events)
    assert all(e.get("resource_type") == "kb_metadata" for e in events)


# ── GU: glossary 수정 (affected → 200 / 404) ───────────────────────────────────────

def test_glossary_update_affected_then_404(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    events = _audit_capture(monkeypatch)

    monkeypatch.setattr(_kg, "update_glossary_term", lambda *a, **k: 1)
    resp = asyncio.run(admin_metadata.admin_update_glossary(7, _FakeRequest({"scope_key": "common", "term": "t", "definition": "d"}), account=acct))
    assert resp.status_code == 200
    assert pg.committed is True
    upd = [e for e in events if e.get("action") == "glossary.term.update"]
    assert len(upd) == 1 and upd[0]["resource_id"] == "7"

    monkeypatch.setattr(_kg, "update_glossary_term", lambda *a, **k: 0)
    resp2 = asyncio.run(admin_metadata.admin_update_glossary(8, _FakeRequest({"scope_key": "common", "term": "t", "definition": "d"}), account=acct))
    assert resp2.status_code == 404


# ── GD: glossary 삭제(멱등) ────────────────────────────────────────────────────────

def test_glossary_delete_idempotent_audit(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    events = _audit_capture(monkeypatch)

    monkeypatch.setattr(_kg, "delete_glossary_term", lambda *a, **k: 1)
    resp = admin_metadata.admin_delete_glossary(3, _FakeRequest(query={"scope_key": "common"}), account=acct)
    assert resp.status_code == 200 and _body(resp)["deleted"] == 1
    assert any(e.get("action") == "glossary.term.delete" for e in events)

    events.clear()
    monkeypatch.setattr(_kg, "delete_glossary_term", lambda *a, **k: 0)  # 이미 없음
    resp2 = admin_metadata.admin_delete_glossary(3, _FakeRequest(query={"scope_key": "common"}), account=acct)
    assert resp2.status_code == 200 and _body(resp2)["deleted"] == 0, "멱등 — 이미 없어도 성공"
    assert not events, "미삭제(affected=0) 시 audit 미기록"


# ── EC: enum 생성 (schema 선택) ────────────────────────────────────────────────────

def test_enum_create_calls_core(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    captured = {}

    def _fake_upsert(conn, scope_key, table_name, column_name, code, label, schema_name=""):
        captured.update({"conn": conn, "scope_key": scope_key, "table_name": table_name,
                         "column_name": column_name, "code": code, "label": label, "schema_name": schema_name})

    monkeypatch.setattr(_kg, "upsert_enum_entry", _fake_upsert)
    events = _audit_capture(monkeypatch)

    resp = asyncio.run(admin_metadata.admin_create_enum(_FakeRequest({
        "scope_key": "default", "table_name": "orders", "column_name": "status",
        "code": "1", "label": "결제완료"}), account=acct))  # schema_name 생략(선택)
    assert resp.status_code == 200
    assert captured["table_name"] == "orders" and captured["code"] == "1"
    assert captured["schema_name"] == ""  # 선택 — 빈 문자열
    assert pg.committed is True
    assert any(e.get("action") == "enum.entry.create" for e in events)


def test_enum_update_404_when_not_found(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    pg = _PgConn()
    monkeypatch.setattr(_dbmod, "_pg_connect", lambda autocommit=True: pg)
    monkeypatch.setattr(_kg, "update_enum_entry", lambda *a, **k: 0)
    resp = asyncio.run(admin_metadata.admin_update_enum(5, _FakeRequest({
        "scope_key": "common", "table_name": "t", "column_name": "c", "code": "1", "label": "l"}), account=acct))
    assert resp.status_code == 404


# ── SV: scope 검증 ────────────────────────────────────────────────────────────────

def test_scope_rejects_unknown_and_empty(monkeypatch):
    _allow_scopes(monkeypatch, scopes=("common",))  # default 미허용
    acct = _admin(monkeypatch)
    called = {"hit": False}
    monkeypatch.setattr(_kg, "upsert_glossary_term", lambda *a, **k: called.__setitem__("hit", True))

    # 미허용 scope → 400
    resp = asyncio.run(admin_metadata.admin_create_glossary(_FakeRequest({"scope_key": "nope", "term": "t", "definition": "d"}), account=acct))
    assert resp.status_code == 400
    # 빈 scope → 400
    resp2 = asyncio.run(admin_metadata.admin_create_glossary(_FakeRequest({"scope_key": "", "term": "t", "definition": "d"}), account=acct))
    assert resp2.status_code == 400
    assert called["hit"] is False, "scope 거부 시 코어 미호출"


# ── IV: 입력 검증 ─────────────────────────────────────────────────────────────────

def test_input_validation(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    monkeypatch.setattr(_kg, "upsert_glossary_term", lambda *a, **k: None)

    # 필수필드 누락(term) → 400
    resp = asyncio.run(admin_metadata.admin_create_glossary(_FakeRequest({"scope_key": "common", "definition": "d"}), account=acct))
    assert resp.status_code == 400
    # 길이 cap 초과(term cap=200) → 400
    long_term = "x" * 201
    resp2 = asyncio.run(admin_metadata.admin_create_glossary(_FakeRequest({"scope_key": "common", "term": long_term, "definition": "d"}), account=acct))
    assert resp2.status_code == 400


# ── LST: list 직렬화 ──────────────────────────────────────────────────────────────

def test_glossary_list_serializes(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    monkeypatch.setattr(_dbmod, "_pg_connect_ro", lambda: _PgConn())
    ts = datetime.datetime(2026, 6, 24, 10, 0, 0)
    # 0021 row: (id, scope_key, role_key, term, definition, source, created_at, updated_at)
    rows = [(1, "common", "*", "용어A", "정의A", "manual", ts, ts),
            (2, "common", "sales", "용어B", "정의B", "auto", ts, ts)]
    monkeypatch.setattr(_kg, "list_glossary_admin", lambda conn, scope_key, **k: rows)

    resp = admin_metadata.admin_list_glossary(_FakeRequest(query={"scope_key": "common"}), account=acct)
    assert resp.status_code == 200
    out = _body(resp)
    assert out["count"] == 2 and out["scope_key"] == "common"
    assert out["items"][0]["id"] == 1 and out["items"][0]["term"] == "용어A"
    assert out["items"][0]["role_key"] == "*" and out["items"][0]["source"] == "manual"
    assert out["items"][1]["role_key"] == "sales" and out["items"][1]["source"] == "auto"
    assert out["items"][0]["updated_at"].startswith("2026-06-24")


def test_enum_list_serializes(monkeypatch):
    _allow_scopes(monkeypatch)
    acct = _admin(monkeypatch)
    monkeypatch.setattr(_dbmod, "_pg_connect_ro", lambda: _PgConn())
    ts = datetime.datetime(2026, 6, 24, 10, 0, 0)
    # row: (id, scope_key, schema_name, table_name, column_name, code, label, source, created_at, updated_at)
    #   0039: source 컬럼 추가(자동수집 되돌리기 구분·자동등록 배지). list_enum_admin 행이 10-tuple 로 확장.
    rows = [(10, "default", "", "orders", "status", "1", "결제완료", "manual", ts, ts)]
    monkeypatch.setattr(_kg, "list_enum_admin", lambda conn, scope_key, **k: rows)

    resp = admin_metadata.admin_list_enums(_FakeRequest(query={"scope_key": "default"}), account=acct)
    assert resp.status_code == 200
    out = _body(resp)
    assert out["count"] == 1
    it = out["items"][0]
    assert it["id"] == 10 and it["table_name"] == "orders" and it["code"] == "1" and it["label"] == "결제완료"
    assert it["source"] == "manual"
