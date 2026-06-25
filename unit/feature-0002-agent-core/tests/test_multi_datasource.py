"""멀티 datasource P1 (DESIGN-multi-datasource.md Stage 1) 회귀·라우팅 테스트.

합격선: "기존 단일 MySQL 동작 0 변경" (flag OFF 또는 datasource 미바인딩 시).
실 DB 없이 mock.patch 로 검증 (conftest·test_db_pool 패턴).
"""
import os
from unittest import mock

import pytest

from shared import config as cfg
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
    """re-gate(4차) BLOCKER5: 바인딩 조회 실패는 fail-**closed** — 기본 DB(None) 폴백이 아니라
    DatasourceResolutionError 를 raise 한다(데이터 계정 GRANT 전체 DB 로 fail-open 차단)."""
    ac = _agent_core()

    class _Boom:
        def cursor(self):
            raise RuntimeError("db down")

    with mock.patch.object(ac.cfg, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(ac.cfg, "DATASOURCES", {"prod": DS}):
        with pytest.raises(ac.DatasourceResolutionError):
            ac._resolve_product_datasource(_Boom(), 5)


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


def test_ask_worker_grounding_scoped_by_endpoint_hash_not_label():
    """TASK-0221: ask-worker grounding(_load_schema_list/_load_relevant_table_insights via
    run_agent → set_active_datasource(scope_key))이 **라벨이 아닌 엔드포인트 해시**로 PG insight 를
    스코프함을 검증 — DatasourceKey 라벨을 rename 해도 ask-worker 가 같은 PG insight 를 계속 활용."""
    from shared import datasources as dsr

    # 같은 엔드포인트, 다른 라벨 → 같은 scope_key(해시) → 같은 grounding 스코프
    ds_a = {"key": "mssql_local", "engine": "mssql", "host": "h", "port": 1433}
    ds_b = {"key": "renamed_later", "engine": "mssql", "host": "h", "port": 1433}
    sk = dsr.scope_key(ds_a)
    assert sk == dsr.scope_key(ds_b), "라벨 rename 시 scope_key(해시)가 바뀌면 ask-worker insight 고아"

    # ask-worker 는 set_active_datasource(sk) 후 _load_schema_list 가 ds_fact_like(sk) 로 PG fact 매치.
    like, nlike = cfg.ds_fact_like("table_insight", ds_key=sk)
    assert like == f"table_insight:ds:{sk}:%" and nlike is None
    assert _sql_like_match(f"table_insight:ds:{sk}:dbo.t", like)          # 자기 ds insight 활용
    assert not _sql_like_match("table_insight:ds:other-endpoint:x.y", like)  # 타 ds 비노출
    assert not _sql_like_match("table_insight:dblog.users", like)            # 기본(no-ds) 비노출


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


# ──────────────────────────────────────────────────────────────────────────
# 5. Stage 2 P4: MSSQL 드라이버 engine 디스패치 (pymssql)
# ──────────────────────────────────────────────────────────────────────────
MSSQL_DS = {"engine": "mssql", "host": "sql-host", "port": 1433, "user": "ro_sql", "password": "pw"}


def test_connect_engine_dispatch_mssql_uses_pymssql():
    captured = {}
    fake_pymssql = mock.MagicMock()
    fake_pymssql.connect.side_effect = lambda **k: captured.update(k) or mock.MagicMock()
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(db, "_pymssql", fake_pymssql):
        db.connect(datasource=MSSQL_DS)
    assert fake_pymssql.connect.called
    assert captured["server"] == "sql-host"
    assert captured["port"] == "1433"
    assert captured["user"] == "ro_sql"
    # TASK-0213: default_db 미설정 MSSQL 은 로그인 기본 DB(master) 대신 **중립 tempdb** 로 연결한다
    # ('기본 참조 DB' 폐지 — 업무 쿼리는 3-part, 무자격은 업무데이터 없는 tempdb 로 해석돼 누출 0).
    assert captured.get("database", "") == "tempdb"


def test_connect_engine_dispatch_mysql_unaffected():
    """engine=mysql(또는 미지정) datasource 는 기존 mysql.connector 경로."""
    captured, fake = _capture_connect()
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(db.mysql.connector, "connect", side_effect=fake):
        db.connect(datasource=DS)  # DS 에 engine 키 없음 → mysql
    assert captured["host"] == "ds-host"  # mysql.connector 경로


def test_connect_mssql_not_installed_raises():
    with mock.patch.object(db, "AGENT_MULTI_DATASOURCE_ENABLED", True), \
         mock.patch.object(db, "_pymssql", None):
        with pytest.raises(RuntimeError):
            db.connect(datasource=MSSQL_DS)


def test_probe_datasource_mssql_engine():
    fake_pymssql = mock.MagicMock()
    fake_pymssql.connect.return_value = mock.MagicMock()
    with mock.patch.object(db, "_pymssql", fake_pymssql):
        ok, ms, err = db.probe_datasource(MSSQL_DS)
    assert ok is True and err == ""
    assert fake_pymssql.connect.called


def test_collect_cursor_result_cross_engine():
    """description 기반 결과 수집 — mysql.connector·pymssql 공통."""
    # result set 있음 (description set, with_rows 없음 = pymssql 스타일)
    cur = mock.MagicMock(spec=["description", "fetchall", "rowcount"])
    cur.description = [("a", None), ("b", None)]
    cur.fetchall.return_value = [(1, 2), (3, 4)]
    out = db._collect_cursor_result(cur)
    assert out == [("rows", ["a", "b"], [(1, 2), (3, 4)])]
    # result set 없음 (description None) → rowcount
    cur2 = mock.MagicMock(spec=["description", "rowcount"])
    cur2.description = None
    cur2.rowcount = 5
    out2 = db._collect_cursor_result(cur2)
    assert out2 == [("rowcount", 5, None)]


# ──────────────────────────────────────────────────────────────────────────
# 6. Stage 2 P5: Dialect 어댑터 (MySQL 골든 회귀 + MSSQL T-SQL)
# ──────────────────────────────────────────────────────────────────────────
from modules import dialects as _dia


def test_mysql_dialect_golden_unchanged():
    """MySQLDialect 는 P5 이전 SQL 을 그대로 산출 (골든 회귀 0)."""
    my = _dia.get("mysql")
    assert my.sample("s", "t", 5) == "SELECT * FROM `s`.`t` LIMIT 5"
    assert my.list_indexes("s", "t") == "SHOW INDEX FROM `s`.`t`"
    # 부하추정/실행계획은 EXPLAIN {sql} 발행 (TASK-0298: explain() 문자열 → estimate_load_rows/explain_plan 콜백).
    _cap: list = []
    my.explain_plan(lambda s: _cap.append(s) or [("rows", [], [])], "SELECT 1 FROM x")
    assert _cap == ["EXPLAIN SELECT 1 FROM x"]
    assert my.quote_qualified("s", "t") == "`s`.`t`"
    assert my.list_schema_names() == "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME"
    # 핵심 introspection 이 information_schema 기반(MySQL)
    assert "information_schema.SCHEMATA" in my.list_schemas_with_counts()
    assert "information_schema.TABLES" in my.describe_schema_tables("s")
    assert "information_schema.COLUMNS" in my.describe_columns("s", "t")


def test_mssql_dialect_tsql():
    ms = _dia.get("mssql")
    assert ms.name == "mssql" and ms.sqlglot == "tsql"
    assert ms.quote_qualified("s", "t") == "[s].[t]"
    assert ms.sample("s", "t", 5) == "SELECT TOP 5 * FROM [s].[t]"
    # sys.* 카탈로그 사용 (information_schema 플레이버 아님)
    assert "sys.schemas" in ms.list_schemas_with_counts()
    assert "sys.tables" in ms.describe_schema_tables("s")
    assert "sys.indexes" in ms.list_indexes("s", "t")
    # EXPLAIN 구문은 없으나 SET SHOWPLAN_ALL 로 사전 부하추정 지원 (TASK-0298).
    assert ms.supports_load_estimate is True
    assert ms.gate_fail_closed_on_estimate_error is True  # 추정 실패 시 gate fail-closed
    _cap: list = []
    ms.explain_plan(lambda s: _cap.append(s) or [("rows", [], [])], "SELECT 1")
    assert any("SHOWPLAN_ALL ON" in c.upper() for c in _cap)
    assert any("SHOWPLAN_ALL OFF" in c.upper() for c in _cap)


def test_mssql_describe_columns_same_column_order():
    """MSSQL describe_columns 가 MySQL 과 동일한 7 컬럼 순서 (tools.py row[i] 파싱 호환)."""
    ms = _dia.get("mssql")
    sql = ms.describe_columns("s", "t").upper()
    # 7개 별칭이 MySQL 순서대로
    order = ["COLUMN_NAME", "COLUMN_TYPE", "IS_NULLABLE", "COLUMN_KEY",
             "COLUMN_DEFAULT", "EXTRA", "COLUMN_COMMENT"]
    positions = [sql.find(a) for a in order]
    assert all(p > 0 for p in positions)
    assert positions == sorted(positions)  # 순서 유지


def test_dialect_active_via_contextvar():
    cfg.set_active_datasource(None)
    try:
        assert _dia.active().name == "mysql"
        cfg.set_active_datasource("prod", engine="mssql")
        assert _dia.active().name == "mssql"
        cfg.set_active_datasource("prod2", engine="mysql")
        assert _dia.active().name == "mysql"
    finally:
        cfg.set_active_datasource(None)


def test_mssql_list_indexes_position_mapping():
    """MSSQL list_indexes SELECT 가 SHOW INDEX 소비 위치(row[1]non_unique/[2]key/[3]seq/[4]col/[6]card)와 정렬."""
    sql = _dia.get("mssql").list_indexes("s", "t").upper()
    aliases = ["TABLE_", "NON_UNIQUE", "KEY_NAME", "SEQ_IN_INDEX", "COLUMN_NAME", "COLLATION", "CARDINALITY"]
    pos = [sql.find(a) for a in aliases]
    assert all(p > 0 for p in pos) and pos == sorted(pos)


def test_run_agent_finally_clears_datasource_on_exception():
    """P5 M1: run_agent 의 finally 가 예외에도 datasource·engine ContextVar 를 해제(스레드 stale 방지)."""
    ac = _agent_core()
    cfg.set_active_datasource("stale", engine="mssql")  # 직전 run 의 잔여 시뮬레이션
    with mock.patch.object(ac, "_run_agent_core", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            ac.run_agent("hi")
    assert cfg.get_active_datasource() is None
    assert cfg.get_active_datasource_engine() == "mysql"


# ──────────────────────────────────────────────────────────────────────────
# P7: insight 컬럼 핑거프린트 dialect projection
# ──────────────────────────────────────────────────────────────────────────
def test_fingerprint_projection_mysql_golden():
    """MySQL projection 은 기존 insight.py 컬럼 그대로(COLUMN_TYPE/COLUMN_KEY) — 골든."""
    p = _dia.get("mysql").fingerprint_column_projection()
    assert p == "COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY"


def test_fingerprint_projection_mssql_no_mysql_only_columns():
    """MSSQL projection 은 SQL Server 에 없는 COLUMN_TYPE/COLUMN_KEY 를 **소스 컬럼**으로 안 쓴다."""
    import re as _re
    p = _dia.get("mssql").fingerprint_column_projection()
    up = p.upper()
    assert "CHARACTER_MAXIMUM_LENGTH" in up        # 타입 상세 대체
    assert up.startswith("COLUMN_NAME")
    assert "DATA_TYPE" in up and "IS_NULLABLE" in up
    assert "INFORMATION_SCHEMA.COLUMNS" not in up   # FROM 은 insight.py 가 소유
    # COLUMN_TYPE/COLUMN_KEY 는 오직 별칭(`AS COLUMN_TYPE`)으로만 등장해야 — 소스 컬럼 참조면 SQL Server invalid.
    for col in ("COLUMN_TYPE", "COLUMN_KEY"):
        for m in _re.finditer(col, up):
            assert up[:m.start()].rstrip().endswith("AS"), f"{col} 가 소스 컬럼으로 참조됨"


def test_fingerprint_projection_active_switches_by_engine():
    """active() projection 이 활성 엔진에 따라 분기."""
    def check():
        cfg.set_active_datasource(None)  # mysql
        assert "COLUMN_TYPE" in _dia.active().fingerprint_column_projection()
        cfg.set_active_datasource("ds", engine="mssql")
        assert "CHARACTER_MAXIMUM_LENGTH" in _dia.active().fingerprint_column_projection()
    import contextvars
    contextvars.copy_context().run(check)
