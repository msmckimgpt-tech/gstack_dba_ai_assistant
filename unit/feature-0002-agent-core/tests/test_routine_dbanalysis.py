"""feature-0016 routine-dbanalysis(§53) 단위 테스트 — DB/AGE 불요(monkeypatch·fake conn).

검증 핵심:
  - enqueue_schema_analysis: dry_run 집계 / only_missing 필터 / cap / noop / reused / 시드 INSERT
    (depth=1 · node_budget=planned — 재귀 0 의 이중 캡 전제).
  - routine_backfill: MySQL 시스템 스키마 제외, MSSQL 시스템 DB 제외, 복수 ROUTINE_SCHEMA 공유
    label 의 prune=False(§53 prune-safety), per-ds 오류 loud 리포트.
"""
from modules import node_analysis as na
from modules import routine_backfill as rb


# ── fakes ─────────────────────────────────────────────────────────────────────
class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.executed = []
        self._last = None

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))
        self._last = None
        for pat, row in self.rows.items():
            if pat in sql:
                self._last = row
                break

    def fetchone(self):
        return self._last

    def fetchall(self):
        return self._last or []

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _tables(n):
    return [{"key": f"ds1:app.T{i}", "name": f"T{i}", "fqn": f"app.T{i}"} for i in range(n)]


def _patch_common(monkeypatch, tables, done_keys=(), cursor=None):
    from modules import metadata_graph as mg
    monkeypatch.setattr(mg, "schema_table_keys", lambda scope, schema, limit=2000, conn=None: tables)
    monkeypatch.setattr(na, "get_scope_analysis_status", lambda scope: {"done_keys": list(done_keys)})
    cur = cursor or FakeCursor()
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    return cur


# ── enqueue_schema_analysis ──────────────────────────────────────────────────
def test_schema_analysis_dry_run_counts(monkeypatch):
    _patch_common(monkeypatch, _tables(10), done_keys=["ds1:app.T0", "ds1:app.T1"])
    res = na.enqueue_schema_analysis("ds1", "ds1:app", dry_run=True)
    assert res["ok"] and res["status"] == "dry_run"
    assert res["total_tables"] == 10 and res["missing"] == 8 and res["planned"] == 8
    assert res["capped"] is False


def test_schema_analysis_noop_when_all_done(monkeypatch):
    keys = [t["key"] for t in _tables(3)]
    cur = _patch_common(monkeypatch, _tables(3), done_keys=keys)
    res = na.enqueue_schema_analysis("ds1", "ds1:app")
    assert res["ok"] and res["status"] == "noop" and res["planned"] == 0
    # running 재사용 SELECT 는 허용(§18.8 dry_run-reused 선행 검사) — run/잡 INSERT 만 없어야 함.
    assert not [e for e in cur.executed if "INSERT" in e[0]]


def test_schema_analysis_cap(monkeypatch):
    _patch_common(monkeypatch, _tables(30))
    monkeypatch.setattr(na._cfg, "AGENT_NODE_ANALYSIS_SCHEMA_CAP", 5, raising=False)
    res = na.enqueue_schema_analysis("ds1", "ds1:app", dry_run=True)
    assert res["planned"] == 5 and res["capped"] is True and res["missing"] == 30


def test_schema_analysis_seeds_depth1_budget_planned(monkeypatch):
    cur = _patch_common(monkeypatch, _tables(4))
    res = na.enqueue_schema_analysis("ds1", "ds1:app", requested_by="tester")
    assert res["ok"] and res["status"] == "running" and res["planned"] == 4
    run_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_runs" in e[0]]
    job_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]]
    assert len(run_sqls) == 1 and len(job_sqls) == 4
    params = run_sqls[0][1]
    # (run_id, scope, root_key, 'Schema', name, depth_budget, node_budget, enqueued, requested_by, up)
    assert params[3] == "Schema" and params[5] == 1 and params[6] == 4 and params[7] == 4
    for sql, jp in job_sqls:
        assert "'Table'" in sql and ",1,1.0,'pending'" in sql.replace(" ", "")
        assert jp[2].startswith("ds1:app.T")


def test_schema_analysis_reused_running(monkeypatch):
    cur = FakeCursor(rows={"FROM node_analysis_runs": ("run-x", 7, 3, 1)})
    _patch_common(monkeypatch, _tables(4), cursor=cur)
    res = na.enqueue_schema_analysis("ds1", "ds1:app")
    assert res["ok"] and res["reused"] is True and res["run_id"] == "run-x"
    assert res["progress"] == {"enqueued": 7, "done": 3, "failed": 1}


def test_schema_analysis_rejects_bad_key(monkeypatch):
    res = na.enqueue_schema_analysis("ds1", "no-colon-key")
    assert not res["ok"]


def test_schema_analysis_dry_run_detects_running(monkeypatch):
    """§18.8 MINOR 회귀 잠금: 진행 중 run 이 있으면 dry_run 도 reused 를 반환해
    프론트 confirm(허위 승인)을 건너뛰게 한다."""
    cur = FakeCursor(rows={"FROM node_analysis_runs": ("run-y", 5, 2, 0)})
    _patch_common(monkeypatch, _tables(4), cursor=cur)
    res = na.enqueue_schema_analysis("ds1", "ds1:app", dry_run=True)
    assert res["ok"] and res["reused"] is True and res["run_id"] == "run-y"
    assert not [e for e in cur.executed if "INSERT" in e[0]]   # dry_run — run 미생성


def test_schema_analysis_fail_loud_on_status_aggregation_failure(monkeypatch):
    """§18.8 MINOR 회귀 잠금: 상태 집계 실패(None) 시 done=∅ 로 전량 재시드(silent 중복
    LLM 비용)하지 않고 fail-loud."""
    from modules import metadata_graph as mg
    monkeypatch.setattr(mg, "schema_table_keys", lambda scope, schema, limit=2000, conn=None: _tables(5))
    monkeypatch.setattr(na, "get_scope_analysis_status", lambda scope: None)
    cur = FakeCursor()
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    res = na.enqueue_schema_analysis("ds1", "ds1:app")
    assert not res["ok"] and "집계 실패" in res["reason"]
    assert not cur.executed


class _UPromptFailCursor(FakeCursor):
    """user_prompt 컬럼 부재(마이그레이션 창) 시뮬레이터 — user_prompt 포함 INSERT 만 1회 실패."""
    def execute(self, sql, params=None):
        if "INSERT INTO node_analysis_runs" in sql and "user_prompt" in sql:
            self.executed.append((" ".join(sql.split()), params))
            raise RuntimeError('column "user_prompt" does not exist')
        super().execute(sql, params)


def test_schema_analysis_uprompt_fallback_insert(monkeypatch):
    """§18.8 회귀 잠금: user_prompt 컬럼 부재 시 9-param 폴백 INSERT 로 run 이 생성된다."""
    cur = _UPromptFailCursor()
    _patch_common(monkeypatch, _tables(3), cursor=cur)
    res = na.enqueue_schema_analysis("ds1", "ds1:app", requested_by="tester", user_prompt="설명해줘")
    assert res["ok"] and res["status"] == "running"
    run_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_runs" in e[0]]
    assert len(run_sqls) == 2   # user_prompt 시도 → 폴백
    assert "user_prompt" not in run_sqls[1][0] and len(run_sqls[1][1]) == 9
    assert len([e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]]) == 3


class _TxConn(FakeConn):
    def transaction(self):
        import contextlib
        return contextlib.nullcontext()


def test_worker_expansion_zero_when_budget_exhausted(monkeypatch):
    """AC-4 워커 레벨 회귀 잠금: enqueued == node_budget 인 run(스키마 시드 run 의 불변식)에서
    _enqueue_neighbors 가 후보(same-depth 승격 포함)가 있어도 0 삽입 — 재귀 0 은 budget 캡 단독 성립."""
    monkeypatch.setattr(na, "_score_candidates", lambda ctx, d, anchor: [
        (0.9, {"key": "ds1:app.N1", "label": "Table", "name": "N1", "fqn": "app.N1"}, False),
        (0.8, {"key": "ds1:app.N2", "label": "Table", "name": "N2", "fqn": "app.N2"}, True),   # same-depth 승격
    ])
    cur = FakeCursor(rows={"FROM node_analysis_runs": (1, 4, 4)})   # depth_budget, node_budget, enqueued
    inserted = na._enqueue_neighbors(_TxConn(cur), cur, "run-z", "ds1", {}, 1, {})
    assert inserted == 0
    assert not [e for e in cur.executed if "INSERT" in e[0]]


# ── routine_backfill ─────────────────────────────────────────────────────────
class _BFCursor:
    """information_schema 응답 시뮬레이터."""
    def __init__(self, routine_schemas, tables):
        self._rs = routine_schemas
        self._tb = tables
        self._last = []

    def execute(self, sql, params=None):
        if "ROUTINES" in sql:
            self._last = [(s,) for s in self._rs]
        elif "TABLES" in sql:
            self._last = [(t,) for t in self._tb]
        else:
            self._last = []

    def fetchall(self):
        return self._last

    def close(self):
        pass


class _BFConn:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _patch_backfill(monkeypatch, ds_map, conns, dbs=None, store_calls=None, connect_calls=None):
    import shared.db as sdb
    import shared.config as scfg
    from shared import datasources as dsm
    from modules import routines as rt
    from modules import metadata_graph as mg
    calls = store_calls if store_calls is not None else []
    # 안전 가드(멀티 ds 플래그) 통과 — 테스트는 fake connect 라 실 연결 없음.
    monkeypatch.setattr(scfg, "AGENT_MULTI_DATASOURCE_ENABLED", True, raising=False)

    def fake_connect(database=None, autocommit=True, datasource=None):
        if connect_calls is not None:
            connect_calls.append({"database": database, "datasource": datasource})
        if datasource is None:
            return _BFConn(_BFCursor([], []))   # mem_conn
        return conns[(datasource["key"], database)]

    monkeypatch.setattr(sdb, "connect", fake_connect)
    monkeypatch.setattr(sdb, "list_server_databases", lambda ds, timeout=None: list(dbs or []))
    monkeypatch.setattr(dsm, "all_datasources", lambda mem: ds_map)
    monkeypatch.setattr(rt, "introspect_and_store",
                        lambda conn, schema, tables, **kw: calls.append((schema, kw)) or 3)
    monkeypatch.setattr(mg, "sync_graph", lambda scope_key=None, **kw: {"ok": True})
    return calls


def test_backfill_mysql_filters_system_schemas(monkeypatch):
    ds = {"m1": {"key": "m1", "engine": "mysql"}}
    conns = {("m1", None): _BFConn(_BFCursor(["appdb", "sys", "mysql"], ["t1", "t2"]))}
    calls = _patch_backfill(monkeypatch, ds, conns)
    rep = rb.run()
    assert [c[0] for c in calls] == ["appdb"]
    assert calls[0][1]["scope_key"] == "m1" and calls[0][1]["datasource_key"] == "m1"
    assert calls[0][1]["store_schema"] == "appdb" and calls[0][1]["prune"] is True
    assert rep["datasources"]["m1"]["stored"] == 3 and not rep["errors"]


def test_backfill_mssql_multi_schema_prune_off(monkeypatch):
    ds = {"s1": {"key": "s1", "engine": "mssql"}}
    conns = {("s1", "gamedb"): _BFConn(_BFCursor(["dbo", "audit"], ["t1"]))}
    calls = _patch_backfill(monkeypatch, ds, conns, dbs=["gamedb", "master", "tempdb"])
    rep = rb.run()
    # 시스템 DB 제외 + label(gamedb) 공유 스키마 2개 → 둘 다 prune=False
    assert sorted(c[0] for c in calls) == ["audit", "dbo"]
    for _, kw in calls:
        assert kw["store_schema"] == "gamedb" and kw["prune"] is False
    assert rep["datasources"]["s1"]["stored"] == 6


def test_backfill_error_is_loud_and_continues(monkeypatch):
    ds = {"bad": {"key": "bad", "engine": "mysql"}, "ok": {"key": "ok", "engine": "mysql"}}

    class Boom(_BFConn):
        def cursor(self):
            raise RuntimeError("conn dead")

    conns = {("bad", None): Boom(None), ("ok", None): _BFConn(_BFCursor(["db1"], ["t"]))}
    calls = _patch_backfill(monkeypatch, ds, conns)
    rep = rb.run()
    assert any("bad" in e for e in rep["errors"])
    assert [c[0] for c in calls] == ["db1"]   # 다른 ds 는 계속 진행


def test_backfill_registry_lookup_uses_memory_db(monkeypatch):
    """§18.8 BLOCKING 회귀 잠금: 레지스트리(WebDatasources) 조회 연결은 반드시 MEMORY_DB 지정 —
    DB 미지정 connect() 는 default DB 미선택이라 _all_db_datasources 가 조용히 {} 를 반환해
    DB 등록 datasource 전량이 silent 누락된다."""
    import shared.config as scfg
    ds = {"m1": {"key": "m1", "engine": "mysql"}}
    conns = {("m1", None): _BFConn(_BFCursor(["db1"], ["t"]))}
    cc = []
    _patch_backfill(monkeypatch, ds, conns, connect_calls=cc)
    rb.run()
    mem_calls = [c for c in cc if c["datasource"] is None]
    assert mem_calls and mem_calls[0]["database"] == scfg.MEMORY_DB


def test_backfill_skips_insight_disabled_unless_forced(monkeypatch):
    """§18.8 MINOR 회귀 잠금: insight_enabled=False(운영자 토글) ds 는 worker parity 로 순회
    제외 — --include-disabled 시에만 포함."""
    ds = {"off": {"key": "off", "engine": "mysql", "insight_enabled": False},
          "on": {"key": "on", "engine": "mysql"}}
    conns = {("off", None): _BFConn(_BFCursor(["db_off"], ["t"])),
             ("on", None): _BFConn(_BFCursor(["db_on"], ["t"]))}
    calls = _patch_backfill(monkeypatch, ds, conns)
    rep = rb.run()
    assert [c[0] for c in calls] == ["db_on"]
    assert "skipped" in rep["datasources"]["off"] and not rep["errors"]
    calls2 = _patch_backfill(monkeypatch, ds, conns)
    rb.run(include_disabled=True)
    assert sorted(c[0] for c in calls2) == ["db_off", "db_on"]


def test_backfill_scope_filter_and_dry_run(monkeypatch):
    ds = {"m1": {"key": "m1", "engine": "mysql"}, "m2": {"key": "m2", "engine": "mysql"}}
    conns = {("m1", None): _BFConn(_BFCursor(["db1"], ["t"])),
             ("m2", None): _BFConn(_BFCursor(["db2"], ["t"]))}
    calls = _patch_backfill(monkeypatch, ds, conns)
    rep = rb.run(scope_filter="m1", dry_run=True)
    assert not calls   # dry-run 은 저장 없음
    assert list(rep["datasources"].keys()) == ["m1"]
    assert rep["datasources"]["m1"]["schemas"] == {"db1": "(dry-run)"}
