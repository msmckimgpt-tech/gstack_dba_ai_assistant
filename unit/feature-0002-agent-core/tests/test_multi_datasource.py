"""멀티 datasource P1 (DESIGN-multi-datasource.md Stage 1) 회귀·라우팅 테스트.

합격선: "기존 단일 MySQL 동작 0 변경" (flag OFF 또는 datasource 미바인딩 시).
실 DB 없이 mock.patch 로 검증 (conftest·test_db_pool 패턴).
"""
import os
from unittest import mock

import pytest

from modules import config as cfg
from modules import db


# ──────────────────────────────────────────────────────────────────────────
# 1. config: DS_<KEY>_* named credential 파싱
# ──────────────────────────────────────────────────────────────────────────
def _parse_with_env(env: dict) -> dict:
    """깨끗한 env 로 _parse_datasources 를 실행 (기존 DS_* 누출 방지)."""
    base = {k: v for k, v in os.environ.items() if not k.startswith("DS_") and k != "AGENT_DATASOURCE_KEYS"}
    base.update(env)
    with mock.patch.dict(os.environ, base, clear=True):
        return cfg._parse_datasources()


def test_parse_datasources_basic():
    ds = _parse_with_env({
        "AGENT_DATASOURCE_KEYS": "prod,bi",
        "DS_PROD_HOST": "db1", "DS_PROD_USER": "ro_prod", "DS_PROD_PASSWORD": "s1",
        "DS_PROD_DEFAULT_DB": "appdb",
        "DS_BI_HOST": "db2", "DS_BI_PORT": "3307", "DS_BI_USER": "ro_bi",
    })
    assert set(ds.keys()) == {"prod", "bi"}
    assert ds["prod"]["host"] == "db1"
    assert ds["prod"]["user"] == "ro_prod"
    assert ds["prod"]["default_db"] == "appdb"
    assert ds["prod"]["engine"] == "mysql"
    assert ds["bi"]["port"] == 3307  # explicit
    assert ds["bi"]["user"] == "ro_bi"  # 명시 RO 유저 (root 폴백 없음)


def test_parse_datasources_incomplete_key_ignored():
    # HOST 또는 USER 없는 키는 제외 (부분/광권한 자격증명으로 connect 시도 방지, N-2)
    ds = _parse_with_env({
        "AGENT_DATASOURCE_KEYS": "prod,nohost,nouser",
        "DS_PROD_HOST": "db1", "DS_PROD_USER": "ro_prod",
        "DS_NOHOST_USER": "x",        # HOST 없음 → 제외
        "DS_NOUSER_HOST": "db9",      # USER 없음 → 제외 (root 폴백 금지, N-2)
    })
    assert set(ds.keys()) == {"prod"}


def test_parse_datasources_empty():
    assert _parse_with_env({}) == {}


def test_datasource_public_masks_password():
    pub = cfg.datasource_public({"key": "k", "host": "h", "password": "secret"})
    assert "password" not in pub
    assert pub["host"] == "h"


# ──────────────────────────────────────────────────────────────────────────
# 2. db.connect: datasource 좌표 라우팅 + flag 게이트
# ──────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _clear_pool():
    db._POOL_REGISTRY.clear()
    yield
    db._POOL_REGISTRY.clear()


def _capture_connect():
    """db.mysql.connector.connect 를 가로채 마지막 params 를 캡처."""
    captured = {}

    def fake(**params):
        captured.clear()
        captured.update(params)
        return mock.MagicMock(name="conn")

    return captured, fake


DS = {"host": "ds-host", "port": 3309, "user": "ro_ds", "password": "pw", "default_db": "salesdb"}


def test_connect_datasource_flag_on_uses_coords():
    captured, fake = _capture_connect()
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(db.mysql.connector, "connect", side_effect=fake):
        db.connect(datasource=DS)
    assert captured["host"] == "ds-host"
    assert captured["port"] == 3309
    assert captured["user"] == "ro_ds"
    assert captured["password"] == "pw"
    # M-1: default_db 를 암묵 기본 스키마로 적용하지 않음 (미접두 쿼리 allowlist 우회 차단).
    # database 미지정 → 연결에 기본 스키마 없음 → schema-prefixed 쿼리 강제.
    assert "database" not in captured


def test_connect_datasource_explicit_db_overrides_default():
    captured, fake = _capture_connect()
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(db.mysql.connector, "connect", side_effect=fake):
        db.connect(database="other_db", datasource=DS)
    assert captured["host"] == "ds-host"
    assert captured["database"] == "other_db"  # 명시 database 우선


def test_connect_flag_off_ignores_datasource_regression():
    """flag OFF + datasource 주어져도 무시 → 기존 DB_HOST 경로 (동작 0 변경)."""
    captured, fake = _capture_connect()
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", False), \
         mock.patch.object(db.mysql.connector, "connect", side_effect=fake):
        db.connect(database="appdb", datasource=DS)
    assert captured["host"] == db.DB_HOST  # ds 무시
    assert captured["host"] != "ds-host"


def test_connect_no_datasource_existing_path():
    """datasource 미지정 → 기존 라우팅 그대로 (data-plane RO 또는 root)."""
    captured, fake = _capture_connect()
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(db.mysql.connector, "connect", side_effect=fake):
        db.connect(database="appdb")
    assert captured["host"] == db.DB_HOST


def test_connect_datasource_pool_key_distinct():
    """datasource 좌표는 _pool_key 가 host/user/db 로 분리하므로 기본 풀과 다른 키."""
    base = db._pool_key({"host": db.DB_HOST, "port": db.DB_PORT, "user": db.DB_USER, "database": "appdb"})
    ds_key = db._pool_key({"host": "ds-host", "port": 3309, "user": "ro_ds", "database": "salesdb"})
    assert base != ds_key


# ──────────────────────────────────────────────────────────────────────────
# 2b. db.probe_datasource: 관리자 연결테스트 (P2, flag 무관, password 비유출)
# ──────────────────────────────────────────────────────────────────────────
def test_probe_datasource_ok():
    captured, fake = _capture_connect()
    # flag OFF 라도 probe 는 연결(명시 관리자 테스트)
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", False), \
         mock.patch.object(db.mysql.connector, "connect", side_effect=fake):
        ok, ms, err = db.probe_datasource(DS)
    assert ok is True
    assert err == ""
    assert ms >= 0
    # probe 는 host/port/user/password 연결성만 — database(default_db) 미설정
    assert captured["host"] == "ds-host" and captured["user"] == "ro_ds"
    assert "database" not in captured


def test_probe_datasource_failure_no_credential_leak():
    class _Err(Exception):
        errno = 1045  # access denied

    def boom(**p):
        raise _Err("Access denied for user 'ro_ds'@'1.2.3.4' (using password: YES)")

    with mock.patch.object(db.mysql.connector, "connect", side_effect=boom):
        ok, ms, err = db.probe_datasource(DS)
    assert ok is False
    # password/host/user 가 에러에 새지 않고 errno 만
    assert err == "errno=1045"
    assert "ro_ds" not in err and "password" not in err.lower()


# ──────────────────────────────────────────────────────────────────────────
# 3. agent_core: product → datasource 해석 (security: authz 는 web, 여기선 매핑만)
# ──────────────────────────────────────────────────────────────────────────
class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def execute(self, *a, **k):
        pass

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def cursor(self):
        return _FakeCursor(self._row)


def _agent_core():
    import agent_core
    return agent_core


def test_resolve_datasource_flag_off_returns_none():
    ac = _agent_core()
    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", False):
        assert ac._resolve_product_datasource(_FakeConn(("prod",)), 5) is None


def test_resolve_datasource_no_product_returns_none():
    ac = _agent_core()
    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True):
        assert ac._resolve_product_datasource(_FakeConn(("prod",)), None) is None
        assert ac._resolve_product_datasource(_FakeConn(("prod",)), 0) is None


def test_resolve_datasource_unregistered_key_fails_closed():
    ac = _agent_core()
    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(ac.cfg, "DATASOURCES", {}):
        # M-2: product 에 명시 바인딩 키가 있으나 .env 미등록 → fail-closed(raise), 운영 DB 폴백 금지
        with pytest.raises(ac.DatasourceResolutionError):
            ac._resolve_product_datasource(_FakeConn(("ghost",)), 5)


def test_resolve_datasource_valid_key_returns_coords():
    ac = _agent_core()
    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(ac.cfg, "DATASOURCES", {"prod": DS}):
        out = ac._resolve_product_datasource(_FakeConn(("PROD",)), 5)  # 대소문자 무관
        assert out == DS


def test_resolve_datasource_null_binding_returns_none():
    ac = _agent_core()
    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(ac.cfg, "DATASOURCES", {"prod": DS}):
        # product 의 DatasourceKey 가 NULL → 기본 DB
        assert ac._resolve_product_datasource(_FakeConn((None,)), 5) is None


def test_resolve_datasource_read_failure_failsafe():
    ac = _agent_core()

    class _Boom:
        def cursor(self):
            raise RuntimeError("db down")

    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(ac.cfg, "DATASOURCES", {"prod": DS}):
        # 읽기 실패해도 예외 전파 없이 기본 DB (fail-safe)
        assert ac._resolve_product_datasource(_Boom(), 5) is None


# ──────────────────────────────────────────────────────────────────────────
# 4. P3: insight fact 키 datasource 스코프 (Codex-3 교차노출 차단)
# ──────────────────────────────────────────────────────────────────────────
import re as _re


def _sql_like_match(value: str, pattern: str) -> bool:
    """SQL LIKE 시맨틱 모사 (% → .*, _ → .). 누출 검증용."""
    rx = "^" + "".join(".*" if c == "%" else ("." if c == "_" else _re.escape(c)) for c in pattern) + "$"
    return _re.match(rx, value) is not None


def test_ds_fact_key_roundtrip_default_and_ds():
    # 기본(None): 무접두
    assert cfg.ds_fact_key("table_insight", "db.t", ds_key=None) == "table_insight:db.t"
    assert cfg.ds_strip_prefix("table_insight", "table_insight:db.t", ds_key=None) == "db.t"
    # datasource: ds 접두
    k = cfg.ds_fact_key("table_insight", "db.t", ds_key="prod")
    assert k == "table_insight:ds:prod:db.t"
    assert cfg.ds_strip_prefix("table_insight", k, ds_key="prod") == "db.t"


def test_ds_grounding_like_no_cross_datasource_leak():
    """핵심 보안: grounding LIKE 패턴이 다른 datasource 의 fact 키를 절대 매치하지 않는다."""
    default_key = "table_insight:dblog.users"
    prod_key = "table_insight:ds:prod:appdb.orders"
    bi_key = "table_insight:ds:bi:sales.daily"

    # 기본 대화(ds=None): like=table_insight:%, not_like=table_insight:ds:%
    like, nlike = cfg.ds_fact_like("table_insight", ds_key=None)
    def visible(key):
        return _sql_like_match(key, like) and not (nlike and _sql_like_match(key, nlike))
    assert visible(default_key) is True       # 기본 키는 보임
    assert visible(prod_key) is False         # prod datasource 키 비노출 (Codex-3)
    assert visible(bi_key) is False           # bi datasource 키 비노출

    # prod 대화(ds=prod): like=table_insight:ds:prod:%, not_like=None
    like_p, nlike_p = cfg.ds_fact_like("table_insight", ds_key="prod")
    assert nlike_p is None
    def visible_p(key):
        return _sql_like_match(key, like_p)
    assert visible_p(prod_key) is True        # 자기 datasource 키만 보임
    assert visible_p(default_key) is False    # 기본 키 비노출
    assert visible_p(bi_key) is False         # 다른 datasource(bi) 키 비노출


def test_ds_fact_like_contextvar_threads_default():
    cfg.set_active_datasource(None)
    try:
        assert cfg.ds_fact_key("schema_fp", "sales") == "schema_fp:sales"
        cfg.set_active_datasource("bi")
        assert cfg.ds_fact_key("schema_fp", "sales") == "schema_fp:ds:bi:sales"
        like, nlike = cfg.ds_fact_like("schema_insight")
        assert like == "schema_insight:ds:bi:%" and nlike is None
    finally:
        cfg.set_active_datasource(None)


def test_ds_scope_name_scan_cursor():
    assert cfg.ds_scope_name("schema_instance_scan_at", ds_key=None) == "schema_instance_scan_at"
    assert cfg.ds_scope_name("schema_instance_scan_at", ds_key="prod") == "schema_instance_scan_at:ds:prod"
