"""node-analysis-completeness (2026-07-23, 사용자 리포트 mysql-local/log_v2) 단위 테스트.

검증 축 — DB/AGE/datasource 불요(monkeypatch·fake):
  RC1(컬럼 인벤토리 lazy introspection):
    - 누락분-only insert(§18.8 M1·M2·m4) — 부분 큐레이션 테이블은 나머지만 채워지고 기존 행
      (설명·source) 은 어떤 경로로도 불변(ON CONFLICT DO NOTHING), 완비 테이블은 write 0.
    - datasource 해석은 MEMORY_DB 연결 + scope_key 계산(.env 레거시 포함) — §18.8 B1 회귀 잠금
      (all_datasources 만 fake, _resolve_datasource_by_scope 본문 관통).
    - cap<=0/멀티 datasource OFF(§18.8 m2) 비활성 · 프로세스 내 dedup · 키 파싱 실패/예외 → 0(fail-soft).
    - engine 별 INFORMATION_SCHEMA 디스패치(MySQL=인스턴스 전역 TABLE_SCHEMA 필터,
      MSSQL=DB 재연결 + 테이블명 매칭).
  RC2 보조(project_cluster_props): 변경 정점 targeted MATCH…SET — int 리터럴·null clear·
    미지원 label skip·fail-soft·SAVEPOINT 행 격리(§18.8 m1).
"""
import pytest

from modules import node_analysis as na
from modules import metadata_graph as mg


class FakeCursor:
    def __init__(self, rows=None, raise_on=None):
        self.rows = rows or {}
        self.raise_on = raise_on or {}
        self.executed = []
        self._last = None
        self.rowcount = 1   # INSERT … DO NOTHING 기본 = 신규 삽입(충돌 시나리오는 테스트가 0 으로 조정)

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.executed.append((flat, params))
        for pat, exc in self.raise_on.items():
            if pat in flat:
                raise exc
        self._last = None
        for pat, row in self.rows.items():
            if pat in flat:
                self._last = row
                break

    def fetchone(self):
        if isinstance(self._last, list):
            return self._last[0] if self._last else None
        return self._last

    def fetchall(self):
        if self._last is None:
            return []
        return self._last if isinstance(self._last, list) else [self._last]

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cur = cursor
        self.closed = False

    def cursor(self):
        return self._cur

    def close(self):
        self.closed = True


def _cfg():
    from shared import config as _c
    return _c


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(na, "_COLS_ENSURED", set())
    monkeypatch.setattr(na, "_DS_CACHE", {"at": 0.0, "map": {}})
    monkeypatch.setattr(_cfg(), "AGENT_MULTI_DATASOURCE_ENABLED", True, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP", 200, raising=False)


def _inserts(cur):
    return [(q, p) for (q, p) in cur.executed if q.startswith("INSERT INTO column_descriptions")]


# ── RC1: _ensure_table_columns — 누락분-only ─────────────────────────────────
def test_ensure_columns_fills_only_missing_keeps_curation(monkeypatch):
    """부분 큐레이션(수동 1컬럼) 테이블 — 누락 컬럼만 insert, 기존 행 무변경(§18.8 M1·m4)."""
    cur = FakeCursor(rows={"SELECT column_name FROM column_descriptions": [("ColA",)]})
    monkeypatch.setattr(na, "_resolve_datasource_by_scope", lambda scope: {"engine": "mysql"})
    monkeypatch.setattr(na, "_introspect_table_columns",
                        lambda ds, schema, table, cap: [("ColA", 1, "큐레이션과 다른 코멘트"),
                                                        ("ColB", 2, "")])
    merges = []
    monkeypatch.setattr(mg, "_set_age_path", lambda c: None)
    monkeypatch.setattr(mg, "sync_column",
                        lambda c, scope, schema, table, col, description="", source="", ordinal=None:
                        merges.append((scope, schema, table, col, description, ordinal)))
    got = na._ensure_table_columns(FakeConn(cur), "ds1:log_v2.tf_log")
    assert got == 1
    ins = _inserts(cur)
    assert len(ins) == 1 and ins[0][1][3] == "ColB"          # 누락분만 insert
    assert "DO NOTHING" in ins[0][0] and "DO UPDATE" not in ins[0][0]   # 큐레이션 절대 불변
    assert merges == [("ds1", "log_v2", "tf_log", "ColB", "", 2)]       # 그래프 MERGE 도 신규분만


def test_ensure_columns_complete_table_writes_nothing(monkeypatch):
    cur = FakeCursor(rows={"SELECT column_name FROM column_descriptions": [("cola",), ("COLB",)]})
    monkeypatch.setattr(na, "_resolve_datasource_by_scope", lambda scope: {"engine": "mysql"})
    monkeypatch.setattr(na, "_introspect_table_columns",
                        lambda ds, schema, table, cap: [("ColA", 1, ""), ("ColB", 2, "")])   # casefold 매칭
    monkeypatch.setattr(mg, "sync_column",
                        lambda *a, **k: pytest.fail("완비 테이블 — 그래프 MERGE 없어야 함"))
    assert na._ensure_table_columns(FakeConn(cur), "ds1:log_v2.tf_log") == 0
    assert _inserts(cur) == []


def test_ensure_columns_conflict_row_not_merged(monkeypatch):
    """race(게이트-insert 사이 큐레이션 저장) — DO NOTHING rowcount 0 이면 그래프 MERGE 도 제외."""
    cur = FakeCursor()
    cur.rowcount = 0
    monkeypatch.setattr(na, "_resolve_datasource_by_scope", lambda scope: {"engine": "mysql"})
    monkeypatch.setattr(na, "_introspect_table_columns", lambda ds, s, t, cap: [("C", 1, "")])
    monkeypatch.setattr(mg, "sync_column",
                        lambda *a, **k: pytest.fail("insert 0 — 그래프 MERGE 없어야 함"))
    assert na._ensure_table_columns(FakeConn(cur), "ds1:log_v2.tf_log") == 0


def test_ensure_columns_gates_dedup_disable_multids_badkey(monkeypatch):
    monkeypatch.setattr(na, "_resolve_datasource_by_scope", lambda scope: {"engine": "mysql"})
    calls = []
    monkeypatch.setattr(na, "_introspect_table_columns",
                        lambda ds, s, t, cap: calls.append(1) or [])
    conn = FakeConn(FakeCursor())
    assert na._ensure_table_columns(conn, "ds1:log_v2.tf_log") == 0    # introspection 0건
    assert na._ensure_table_columns(conn, "ds1:log_v2.tf_log") == 0    # 프로세스 dedup — 재시도 없음
    assert len(calls) == 1
    # cap<=0 → 비활성
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP", 0, raising=False)
    assert na._ensure_table_columns(conn, "ds1:log_v2.other") == 0
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP", 200, raising=False)
    # 멀티 datasource OFF → 비활성(§18.8 m2 — 레거시 DB_HOST 오염 차단)
    monkeypatch.setattr(_cfg(), "AGENT_MULTI_DATASOURCE_ENABLED", False, raising=False)
    assert na._ensure_table_columns(conn, "ds1:log_v2.other2") == 0
    assert len(calls) == 1
    monkeypatch.setattr(_cfg(), "AGENT_MULTI_DATASOURCE_ENABLED", True, raising=False)
    # 키 파싱 실패(스키마 세그먼트 없음/scope 없음)
    assert na._ensure_table_columns(conn, "ds1:tableonly") == 0
    assert na._ensure_table_columns(conn, "no-colon-key") == 0


def test_ensure_columns_failure_is_soft(monkeypatch):
    monkeypatch.setattr(na, "_resolve_datasource_by_scope", lambda scope: {"engine": "mysql"})
    monkeypatch.setattr(na, "_introspect_table_columns", lambda ds, s, t, cap: [("C", 1, "")])
    cur = FakeCursor(raise_on={"SELECT column_name FROM column_descriptions": RuntimeError("pg down")})
    assert na._ensure_table_columns(FakeConn(cur), "ds1:log_v2.tf_log") == 0


# ── RC1: datasource 해석 (§18.8 B1 회귀 잠금 — resolve 본문 관통) ─────────────
def test_resolve_datasource_uses_memory_db_and_computed_scope(monkeypatch):
    """connect 는 MEMORY_DB 명시(§18.8 B1 — 무지정 connect 는 레지스트리 조회가 조용히 {})·
    scope 키는 coords 계산(.env 레거시 dict 는 scope_key 필드 미보유)."""
    from shared import db as _db
    from shared import datasources as _dsm
    opened = []
    monkeypatch.setattr(_db, "connect",
                        lambda database=None, autocommit=True, datasource=None:
                        opened.append(database) or FakeConn(FakeCursor()))
    legacy = {"key": "mysql-local", "engine": "mysql", "host": "10.0.0.5", "port": 3306}
    registry = {"key": "mssql-qa", "engine": "mssql", "host": "10.0.0.9", "port": 1433,
                "scope_key": "mssql-precomputed"}
    monkeypatch.setattr(_dsm, "all_datasources",
                        lambda mem: {"mysql-local": legacy, "mssql-qa": registry})
    want = _dsm.compute_scope_key("mysql", "10.0.0.5", 3306)
    got = na._resolve_datasource_by_scope(want)
    assert opened == [_cfg().MEMORY_DB]
    assert got is legacy                                            # .env 레거시 — 계산 scope 로 해석
    assert na._resolve_datasource_by_scope("mssql-precomputed") is registry   # 사전계산 scope 우선(TTL 캐시)


def test_resolve_datasource_failure_returns_none(monkeypatch):
    from shared import db as _db
    monkeypatch.setattr(_db, "connect", lambda **k: (_ for _ in ()).throw(RuntimeError("mem down")))
    assert na._resolve_datasource_by_scope("ds1") is None


# ── RC1: introspection engine 디스패치 ───────────────────────────────────────
def test_introspect_dispatch_mysql_vs_mssql(monkeypatch):
    from shared import db as _db
    opened = []

    def _fake_connect(database=None, autocommit=True, datasource=None):
        opened.append((database, (datasource or {}).get("engine")))
        return FakeConn(FakeCursor(rows={
            "FROM information_schema.columns": [("a", 1, "c")],
            "FROM INFORMATION_SCHEMA.COLUMNS": [("b", 2, "")],
        }))

    monkeypatch.setattr(_db, "connect", _fake_connect)
    got_my = na._introspect_table_columns({"engine": "mysql"}, "log_v2", "t", 10)
    assert got_my == [("a", 1, "c")] and opened[-1] == (None, "mysql")   # MySQL: 재연결 DB 불필요
    got_ms = na._introspect_table_columns({"engine": "mssql"}, "dk_data", "t", 10)
    assert got_ms == [("b", 2, "")] and opened[-1] == ("dk_data", "mssql")   # MSSQL: catalog 재연결
    # cap 절단
    monkeypatch.setattr(_db, "connect", lambda database=None, autocommit=True, datasource=None:
                        FakeConn(FakeCursor(rows={"FROM information_schema.columns":
                                                  [(f"c{i}", i, "") for i in range(1, 6)]})))
    assert len(na._introspect_table_columns({"engine": "mysql"}, "s", "t", 3)) == 3


# ── RC2 보조: project_cluster_props ──────────────────────────────────────────
def test_project_cluster_props_targeted_set(monkeypatch):
    cur = FakeCursor()
    monkeypatch.setattr(mg, "_rw_conn", lambda conn: (FakeConn(cur), False))
    n = mg.project_cluster_props([
        {"label": "Table", "key": "ds1:aaa.t1", "cid": 0, "lab": "게임 운영 기록"},
        {"label": "Routine", "key": "ds1:aaa.sp_r1()", "cid": None, "lab": None},
        {"label": "Schema", "key": "ds1:aaa", "cid": 1, "lab": "x"},   # 미지원 label — skip
        {"label": "Table", "key": "", "cid": 1, "lab": "x"},           # key 없음 — skip
    ])
    assert n == 2
    stmts = [q for (q, p) in cur.executed if "MATCH (t:" in q]
    assert len(stmts) == 2
    assert "MATCH (t:Table {key: 'ds1:aaa.t1'})" in stmts[0]
    assert "t.semantic_cluster_id = 0" in stmts[0] and "게임 운영 기록" in stmts[0]
    # 이탈(None) → 명시적 null clear(stale phantom 방지)
    assert "MATCH (t:Routine {key: 'ds1:aaa.sp_r1()'})" in stmts[1]
    assert "t.semantic_cluster_id = null" in stmts[1] and "t.semantic_cluster_label = null" in stmts[1]


def test_project_cluster_props_row_isolated_savepoint(monkeypatch):
    """§18.8 m1: 한 행 실패는 SAVEPOINT 롤백으로 격리 — 나머지 행 계속 + caller tx 미오염."""
    cur = FakeCursor(raise_on={"MATCH (t:Table {key: 'ds1:bad'})": RuntimeError("age err")})
    monkeypatch.setattr(mg, "_rw_conn", lambda conn: (FakeConn(cur), False))
    n = mg.project_cluster_props([
        {"label": "Table", "key": "ds1:bad", "cid": 1, "lab": "x"},
        {"label": "Table", "key": "ds1:aaa.t1", "cid": 2, "lab": "y"},
    ])
    assert n == 1
    flats = [q for (q, p) in cur.executed]
    assert any(q.startswith("ROLLBACK TO SAVEPOINT mg_proj_cluster") for q in flats)
    assert any("MATCH (t:Table {key: 'ds1:aaa.t1'})" in q for q in flats)   # 후속 행 계속


def test_project_cluster_props_failsoft(monkeypatch):
    monkeypatch.setattr(mg, "_rw_conn", lambda conn: (None, False))
    assert mg.project_cluster_props([{"label": "Table", "key": "k", "cid": 1, "lab": "x"}]) == 0
