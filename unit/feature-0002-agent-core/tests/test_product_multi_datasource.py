"""TASK-0228 (멀티 datasource 1:N): 제품 1개 ↔ 여러 datasource 참조 회귀·격리 테스트.

핵심 합격선:
  1. 단일 바인딩(0~1 datasource)은 기존 단일 경로와 동작 0 변경 — `_resolve_product_datasources` 가 []
     반환(라우터 미생성) → 기존 `_resolve_product_datasource` 가 처리.
  2. ≥2 바인딩이면 라우터가 datasource 별 (연결, allowlist, engine) 을 격리 활성화한다.
  3. **격리 불변식**: datasource A 컨텍스트에서는 A 의 allowlist/engine 만 보이고 B 가 안 보인다
     (교차노출 차단). 미바인딩 라벨 요청은 거부(엉뚱한 datasource silent 라우팅 금지).

실 DB 없이 mock + fake conn 으로 검증 (conftest·test_multi_datasource 패턴).
"""
from unittest import mock

import pytest

from modules import config as cfg
from modules import tools as tools_mod


DS_A = {"key": "dsa", "engine": "mysql", "host": "ha", "port": 3306, "user": "ro_a",
        "password": "p", "default_db": None, "scope_key": "mysql-aaaa", "_source": "db"}
DS_B = {"key": "dsb", "engine": "mssql", "host": "hb", "port": 1433, "user": "ro_b",
        "password": "p", "default_db": None, "scope_key": "mssql-bbbb", "_source": "db"}


# ──────────────────────────────────────────────────────────────────────────
# Fake conn: 라우팅된 SQL 의 첫 토큰으로 응답을 분기하는 최소 stub
# ──────────────────────────────────────────────────────────────────────────
class _FakeCursor:
    def __init__(self, store):
        self._store = store
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self._store["last_sql"] = s
        self._rows = []
        # WebProductDatasources: 제품의 datasource 키 목록
        if "from webproductdatasources" in s and "schemaname" not in s:
            self._rows = self._store.get("bindings", [])
        # WebProducts.DatasourceKey 단일(폴백)
        elif "datasourcekey from webproducts" in s:
            self._rows = self._store.get("primary_row", [])
        # WebProductDatabases: 접근가능 스키마(차원)
        elif "schemaname from webproductdatabases" in s:
            dsk = (params or [None, ""])[-1] if params else ""
            self._rows = self._store.get("dbs", {}).get(str(dsk).lower(), [])
        else:
            self._rows = []

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass


class _FakeConn:
    def __init__(self, store):
        self._store = store

    def cursor(self, *a, **k):
        return _FakeCursor(self._store)


def _ac():
    import agent_core
    return agent_core


# ──────────────────────────────────────────────────────────────────────────
# 1. _resolve_product_datasources: 0~1 바인딩 → [] (단일 경로 유지)
# ──────────────────────────────────────────────────────────────────────────
def test_multi_resolve_flag_off_returns_empty():
    ac = _ac()
    store = {"bindings": [("dsa", 1, 0), ("dsb", 0, 10)]}
    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", False):
        assert ac._resolve_product_datasources(_FakeConn(store), 5) == []


def test_multi_resolve_single_binding_returns_empty():
    """단일 바인딩은 [] — 기존 단일 datasource 경로가 처리(동작 0 변경)."""
    ac = _ac()
    store = {"bindings": [("dsa", 1, 0)]}
    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True):
        assert ac._resolve_product_datasources(_FakeConn(store), 5) == []


def test_multi_resolve_two_bindings_returns_list():
    ac = _ac()
    store = {
        "bindings": [("dsa", 1, 0), ("dsb", 0, 10)],
        "dbs": {"dsa": [("appdb",)], "dsb": [("salesdb",)]},
    }

    def _fake_resolve(_conn, key):
        return {"dsa": dict(DS_A), "dsb": dict(DS_B)}.get(key)

    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch("modules.datasources.resolve", side_effect=_fake_resolve):
        out = ac._resolve_product_datasources(_FakeConn(store), 5)
    assert len(out) == 2
    labels = [d["_label"] for d in out]
    assert labels == ["dsa", "dsb"]              # primary(dsa) 먼저
    assert out[0]["_is_primary"] is True
    assert out[1]["_is_primary"] is False
    # 각 datasource 의 allowlist 가 자기 DB 만(격리)
    assert out[0]["_allow_schemas"] == ["appdb"]
    assert out[1]["_allow_schemas"] == ["salesdb"]


def test_datasource_allow_schemas_failclosed_on_missing_column():
    """REV-0228 MAJOR-2: 차원 컬럼 부재/조회 실패 시 [] (fail-closed) — 전체 목록 broadcast 금지."""
    ac = _ac()

    class _BoomCursor:
        def execute(self, sql, params=None):
            raise RuntimeError("Unknown column 'DatasourceKey'")
        def close(self):
            pass

    class _BoomConn:
        def cursor(self, *a, **k):
            return _BoomCursor()

    # 예외(컬럼 부재) → [] 반환(차원 무필터 전체 목록 폴백 금지 = 교차노출 차단).
    assert ac._datasource_allow_schemas(_BoomConn(), 5, "dsa") == []


def test_multi_resolve_skips_unregistered_key_but_needs_two():
    """미등록 키는 skip — skip 후 ≥2 못 채우면 [](단일 폴백)."""
    ac = _ac()
    store = {"bindings": [("dsa", 1, 0), ("ghost", 0, 10)], "dbs": {"dsa": [("appdb",)]}}

    def _fake_resolve(_conn, key):
        return dict(DS_A) if key == "dsa" else None  # ghost 미등록

    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch("modules.datasources.resolve", side_effect=_fake_resolve):
        out = ac._resolve_product_datasources(_FakeConn(store), 5)
    assert out == []  # 1개만 살아남음 → 단일 경로로 폴백


# ──────────────────────────────────────────────────────────────────────────
# 2. DatasourceRouter: 라벨 해석·연결 lazy·컨텍스트 격리
# ──────────────────────────────────────────────────────────────────────────
def _mk_router(connect_calls):
    a = dict(DS_A); a.update({"_label": "dsa", "_allow_schemas": ["appdb"], "_is_primary": True})
    b = dict(DS_B); b.update({"_label": "dsb", "_allow_schemas": ["salesdb"], "_is_primary": False})

    def _connect(ds):
        connect_calls.append(ds["_label"])
        return mock.MagicMock(name=f"conn-{ds['_label']}")

    return tools_mod._DatasourceRouter([a, b], _connect)


def test_router_resolve_label_defaults_to_primary():
    r = _mk_router([])
    assert r.resolve_label(None) == "dsa"
    assert r.resolve_label("dsb") == "dsb"
    assert r.resolve_label("nope") == "dsa"   # 미바인딩 → primary 폴백
    assert r.labels() == ["dsa", "dsb"]


def test_router_lazy_connection():
    calls = []
    r = _mk_router(calls)
    assert calls == []                  # 아직 연결 안 함
    r.conn_for("dsa")
    assert calls == ["dsa"]
    r.conn_for("dsa")                   # 캐시 — 재연결 안 함
    assert calls == ["dsa"]
    r.conn_for("dsb")
    assert calls == ["dsa", "dsb"]


def test_router_activate_isolates_allowlist_and_engine():
    """격리 불변식: A 활성 시 A 의 allowlist/engine 만, B 활성 시 B 의 것만."""
    r = _mk_router([])
    try:
        r.activate("dsa")
        assert tools_mod._ACTIVE_SCHEMA_ALLOWLIST.get() == {"appdb"}
        assert cfg.get_active_datasource_engine() == "mysql"
        r.activate("dsb")
        assert tools_mod._ACTIVE_SCHEMA_ALLOWLIST.get() == {"salesdb"}
        assert cfg.get_active_datasource_engine() == "mssql"
        # A 로 되돌리면 다시 A 만(B 누출 없음)
        r.activate("dsa")
        assert tools_mod._ACTIVE_SCHEMA_ALLOWLIST.get() == {"appdb"}
    finally:
        tools_mod.clear_active_schema_allowlist()
        cfg.set_active_datasource(None)


def test_router_describe_hides_credentials():
    r = _mk_router([])
    desc = r.describe()
    assert {d["label"] for d in desc} == {"dsa", "dsb"}
    flat = repr(desc)
    assert "password" not in flat and "ro_a" not in flat and "ha" not in flat  # 좌표/비번 비노출


# ──────────────────────────────────────────────────────────────────────────
# 3. execute_tool 라우팅: datasource 인자로 대상 선택 + 미바인딩 라벨 거부
# ──────────────────────────────────────────────────────────────────────────
def test_execute_tool_routes_to_selected_datasource():
    calls = []
    r = _mk_router(calls)
    seen = {}

    def _handler(conn, args):
        # 활성 allowlist 를 캡처(라우팅 검증)
        seen["allow"] = set(tools_mod._ACTIVE_SCHEMA_ALLOWLIST.get() or set())
        seen["engine"] = cfg.get_active_datasource_engine()
        return "ok"

    tok = tools_mod.set_active_ds_router(r)
    try:
        with mock.patch.dict(tools_mod._TOOL_HANDLERS, {"execute_sql": _handler}, clear=False):
            out = tools_mod.execute_tool(None, "execute_sql", {"sql": "SELECT 1", "datasource": "dsb"})
        assert out == "ok"
        assert seen["allow"] == {"salesdb"}    # dsb 의 allowlist 로 라우팅됨
        assert seen["engine"] == "mssql"
    finally:
        tools_mod.reset_active_ds_router(tok)
        tools_mod.clear_active_schema_allowlist()
        cfg.set_active_datasource(None)


def test_execute_tool_rejects_unbound_datasource_label():
    r = _mk_router([])
    tok = tools_mod.set_active_ds_router(r)
    try:
        with mock.patch.dict(tools_mod._TOOL_HANDLERS, {"execute_sql": lambda c, a: "ok"}, clear=False):
            out = tools_mod.execute_tool(None, "execute_sql", {"sql": "SELECT 1", "datasource": "ghost"})
        assert "바인딩된 데이터소스가 아닙니다" in out  # 엉뚱한 라우팅 차단
    finally:
        tools_mod.reset_active_ds_router(tok)
        cfg.set_active_datasource(None)


def test_execute_tool_default_to_primary_when_unspecified():
    r = _mk_router([])
    seen = {}

    def _handler(conn, args):
        seen["allow"] = set(tools_mod._ACTIVE_SCHEMA_ALLOWLIST.get() or set())
        return "ok"

    tok = tools_mod.set_active_ds_router(r)
    try:
        with mock.patch.dict(tools_mod._TOOL_HANDLERS, {"execute_sql": _handler}, clear=False):
            tools_mod.execute_tool(None, "execute_sql", {"sql": "SELECT 1"})  # datasource 미지정
        assert seen["allow"] == {"appdb"}     # primary(dsa)
    finally:
        tools_mod.reset_active_ds_router(tok)
        tools_mod.clear_active_schema_allowlist()
        cfg.set_active_datasource(None)


def test_execute_tool_no_router_is_unchanged():
    """라우터 미등록(단일 datasource)이면 종전대로 인자 conn 으로 실행 — datasource 인자도 무시."""
    seen = {}

    def _handler(conn, args):
        seen["conn"] = conn
        seen["args"] = dict(args)
        return "ok"

    sentinel = object()
    with mock.patch.dict(tools_mod._TOOL_HANDLERS, {"execute_sql": _handler}, clear=False):
        out = tools_mod.execute_tool(sentinel, "execute_sql", {"sql": "SELECT 1"})
    assert out == "ok"
    assert seen["conn"] is sentinel


# ──────────────────────────────────────────────────────────────────────────
# 4. build_tool_definitions_for_datasources: datasource enum 주입
# ──────────────────────────────────────────────────────────────────────────
def test_build_tool_defs_injects_datasource_enum():
    base = [{"type": "function", "function": {"name": "execute_sql", "parameters": {
        "type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}}}]
    out = tools_mod.build_tool_definitions_for_datasources(base, ["dsa", "dsb"])
    props = out[0]["function"]["parameters"]["properties"]
    assert "datasource" in props
    assert props["datasource"]["enum"] == ["dsa", "dsb"]
    # 원본 불변(깊은 복사)
    assert "datasource" not in base[0]["function"]["parameters"]["properties"]


def test_build_tool_defs_single_datasource_noop():
    base = [{"type": "function", "function": {"name": "execute_sql", "parameters": {
        "type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}}}]
    assert tools_mod.build_tool_definitions_for_datasources(base, ["dsa"]) is base
    assert tools_mod.build_tool_definitions_for_datasources(base, []) is base
