"""feature-0016 routine-dbanalysis(§53) 단위 테스트 — DB/AGE 불요(monkeypatch·fake conn).

검증 핵심:
  - enqueue_schema_analysis: dry_run 집계 / only_missing 필터 / cap / noop / reused / 시드 INSERT
    (depth=1 · node_budget=planned — 재귀 0 의 이중 캡 전제).
  - routine_backfill: MySQL 시스템 스키마 제외, MSSQL 시스템 DB 제외, 복수 ROUTINE_SCHEMA 공유
    label 의 prune=False(§53 prune-safety), per-ds 오류 loud 리포트.
"""
import pytest

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


def _routines(n):
    return [{"key": f"ds1:app.spR{i}()", "name": f"spR{i}", "fqn": f"app.spR{i}()"} for i in range(n)]


def _patch_common(monkeypatch, tables, done_keys=(), cursor=None, routines=None):
    # feature-0043: 이 파일의 대상은 **게이트 뒤의 적재 로직**이다. 게이트가 닫힌 채로 두면
    # 모든 테스트가 "차단됨" 한 줄에서 끝나 정작 검사하려던 계약을 아무도 보지 않게 된다
    # (vacuous pass). 여기서 명시적으로 열고, 게이트 자체의 계약은 아래 전용 테스트가 본다.
    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "1")
    from modules import metadata_graph as mg
    monkeypatch.setattr(mg, "schema_table_keys", lambda scope, schema, limit=2000, conn=None: tables)
    # graph-navfilter(§54④): Routine 시드 열거 — 기본 [](테이블-only, 0034 미적용 저하와 동형).
    monkeypatch.setattr(mg, "schema_routine_keys", lambda scope, schema, limit=2000, conn=None: (routines or []))
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


def test_schema_analysis_seeds_depth0_anchor_expanded_budget(monkeypatch):
    """§55(REQ-20260706 ③): 시드 depth=0 + anchor_key=자기 자신 + 예산 planned×EXPAND_FACTOR —
    스키마 단위 분석의 재귀 전개 활성(구 재귀 0 계약 대체; legacy 창은 아래 폴백 테스트)."""
    monkeypatch.setitem(na._REFINE_COLS, "ok", True)
    cur = _patch_common(monkeypatch, _tables(4))
    res = na.enqueue_schema_analysis("ds1", "ds1:app", requested_by="tester")
    assert res["ok"] and res["status"] == "running" and res["planned"] == 4
    run_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_runs" in e[0]]
    job_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]]
    assert len(run_sqls) == 1 and len(job_sqls) == 4
    params = run_sqls[0][1]
    # (run_id, scope, root_key, 'Schema', name, depth_budget, node_budget, enqueued, requested_by, up)
    assert params[3] == "Schema" and params[5] == 2   # depth = AGENT_NODE_ANALYSIS_SCHEMA_DEPTH(2)
    assert params[6] == 48 and params[7] == 4         # budget = 4×12(factor) / enqueued = planned
    for sql, jp in job_sqls:
        # §54④: node_label 은 리터럴 'Table' 이 아니라 파라미터(jp[3]) — Routine 혼합 시드 지원.
        assert ",0,1.0,'pending'" in sql.replace(" ", "")   # §55: depth=0(직계 컬럼 게이트 면제 편입)
        assert "anchor_key" in sql
        assert jp[2].startswith("ds1:app.T") and jp[3] == "Table"
        assert jp[6] == jp[2]   # per-seed 앵커 — anchor_key == 자기 key


def test_schema_analysis_legacy_window_seeds_depth1_budget_planned(monkeypatch):
    """§55 마이그레이션 창(alembic 0038 미적용) 폴백 — 구 계약 그대로: depth=1 시드·node_budget=planned
    (재귀 0)·anchor_key 미포함. 구 워커 ON CONFLICT (run_id,node_key) 와 mixed-version 안전."""
    monkeypatch.setitem(na._REFINE_COLS, "ok", False)
    cur = _patch_common(monkeypatch, _tables(4))
    res = na.enqueue_schema_analysis("ds1", "ds1:app", requested_by="tester")
    assert res["ok"] and res["status"] == "running" and res["planned"] == 4
    run_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_runs" in e[0]]
    job_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]]
    params = run_sqls[0][1]
    assert params[5] == 1 and params[6] == 4 and params[7] == 4
    for sql, jp in job_sqls:
        assert ",1,1.0,'pending'" in sql.replace(" ", "")
        assert "anchor_key" not in sql and len(jp) == 6


def test_schema_analysis_reused_running(monkeypatch):
    cur = FakeCursor(rows={"FROM node_analysis_runs": ("run-x", 7, 3, 1)})
    _patch_common(monkeypatch, _tables(4), cursor=cur)
    res = na.enqueue_schema_analysis("ds1", "ds1:app")
    assert res["ok"] and res["reused"] is True and res["run_id"] == "run-x"
    assert res["progress"] == {"enqueued": 7, "done": 3, "failed": 1}


def test_schema_analysis_rejects_bad_key(monkeypatch):
    res = na.enqueue_schema_analysis("ds1", "no-colon-key")
    assert not res["ok"]


# ── §54④: 스키마 시드에 Routine 포함 ─────────────────────────────────────────
def test_schema_analysis_mixed_dry_run_counts(monkeypatch):
    """테이블 5+루틴 3, done=테이블2+루틴1 → total_tables=5, total_routines=3, missing=5."""
    done = ["ds1:app.T0", "ds1:app.T1", "ds1:app.spR0()"]
    _patch_common(monkeypatch, _tables(5), done_keys=done, routines=_routines(3))
    res = na.enqueue_schema_analysis("ds1", "ds1:app", dry_run=True)
    assert res["ok"] and res["total_tables"] == 5 and res["total_routines"] == 3
    assert res["missing"] == 5 and res["planned"] == 5 and res["capped"] is False


def test_schema_analysis_seeds_routine_label(monkeypatch):
    """루틴 잡은 node_label='Routine' 파라미터로 시드 — §55: 예산 planned×factor(재귀 전개), 시드 순서 불변."""
    monkeypatch.setitem(na._REFINE_COLS, "ok", True)
    cur = _patch_common(monkeypatch, _tables(2), routines=_routines(2))
    res = na.enqueue_schema_analysis("ds1", "ds1:app")
    assert res["ok"] and res["planned"] == 4
    run_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_runs" in e[0]]
    job_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]]
    assert run_sqls[0][1][6] == 48   # §55: node_budget = (테이블2+루틴2)×EXPAND_FACTOR(12)
    labels = [jp[3] for _, jp in job_sqls]
    assert labels == ["Table", "Table", "Routine", "Routine"]   # 테이블 우선 순서(결정적)
    rkeys = [jp[2] for _, jp in job_sqls if jp[3] == "Routine"]
    assert all(k.endswith("()") for k in rkeys)   # sync_routine 키 규약(`()` 접미) 그대로 시드


def test_schema_analysis_cap_prefers_tables(monkeypatch):
    """cap 절단 시 테이블 우선 — cap=4 에 테이블3+루틴3 → 테이블 3 전부 + 루틴 1."""
    cur = _patch_common(monkeypatch, _tables(3), routines=_routines(3))
    monkeypatch.setattr(na._cfg, "AGENT_NODE_ANALYSIS_SCHEMA_CAP", 4, raising=False)
    res = na.enqueue_schema_analysis("ds1", "ds1:app")
    assert res["planned"] == 4 and res["capped"] is True and res["missing"] == 6
    job_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]]
    labels = [jp[3] for _, jp in job_sqls]
    assert labels == ["Table", "Table", "Table", "Routine"]


def test_schema_analysis_degrades_to_tables_only(monkeypatch):
    """schema_routine_keys 가 [](라벨 부재/실패) → 기존 테이블-only 동작과 동일(비차단 저하)."""
    cur = _patch_common(monkeypatch, _tables(3), routines=[])
    res = na.enqueue_schema_analysis("ds1", "ds1:app")
    assert res["ok"] and res["planned"] == 3 and res["total_routines"] == 0
    job_sqls = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]]
    assert all(jp[3] == "Table" for _, jp in job_sqls)


def test_build_payload_routine_fields():
    """Routine payload 에 routine_type/params 투영(프롬프트 계약) — 타 라벨은 미포함."""
    node_r = {"label": "Routine", "key": "ds1:app.spX()", "name": "spX", "fqn": "app.spX()",
              "routine_type": "procedure", "params": "IN a int, OUT b varchar"}
    p = na._build_payload(node_r, {})
    assert p["routine_type"] == "procedure" and p["params"] == "IN a int, OUT b varchar"
    node_t = {"label": "Table", "key": "ds1:app.T", "name": "T", "fqn": "app.T"}
    pt = na._build_payload(node_t, {})
    assert "routine_type" not in pt and "params" not in pt


def test_build_payload_routine_touches_returns():
    """§69 P2: Routine payload 에 touches(read/write, 테이블명 dedup)+returns 투영.
    ctx 의 routine_touches/routine_returns 를 프롬프트 계약 필드로 옮긴다 — Table 은 미포함."""
    node_r = {"label": "Routine", "key": "ds1:app.spX()", "name": "spX", "fqn": "app.spX()",
              "routine_type": "procedure"}
    ctx = {"routine_returns": "int",
           "routine_touches": [{"table": "Orders", "access": "write"},
                               {"table": "Users", "access": "read"},
                               {"table": "Orders", "access": "read"},  # 중복 테이블 — dedup(첫 access 유지)
                               {"table": "", "access": "read"}]}       # 빈 테이블명 — skip
    p = na._build_payload(node_r, ctx)
    assert p["returns"] == "int"
    assert p["touches"] == [{"table": "Orders", "access": "write"},
                            {"table": "Users", "access": "read"}]
    # returns/touches 는 Routine 전용 — Table 은 동일 ctx 라도 미투영.
    node_t = {"label": "Table", "key": "ds1:app.T", "name": "T", "fqn": "app.T"}
    pt = na._build_payload(node_t, ctx)
    assert "returns" not in pt and "touches" not in pt
    # 빈 returns 는 키 자체 생략(비차단 부가정보).
    p2 = na._build_payload(node_r, {"routine_returns": "  ", "routine_touches": []})
    assert "returns" not in p2 and "touches" not in p2


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
    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "1")   # 대상은 게이트 뒤의 집계 계약
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


def _patch_backfill(monkeypatch, ds_map, conns, dbs=None, store_calls=None, connect_calls=None,
                    purge_calls=None):
    import shared.db as sdb
    import shared.config as scfg
    from shared import datasources as dsm
    from modules import routines as rt
    from modules import metadata_graph as mg
    calls = store_calls if store_calls is not None else []
    # 안전 가드(멀티 ds 플래그) 통과 — 테스트는 fake connect 라 실 연결 없음.
    monkeypatch.setattr(scfg, "AGENT_MULTI_DATASOURCE_ENABLED", True, raising=False)
    # §56 RC5: 케이스-변형 label purge 는 KB 연결을 여는 실함수라 hermetic 하게 차단 + 호출 캡처.
    monkeypatch.setattr(rt, "purge_case_variant_labels",
                        lambda scope_key, store_label, kb_conn=None:
                        (purge_calls.append((scope_key, store_label))
                         if purge_calls is not None else None) or 0)

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


# ── feature-0043 게이트: **큐에 넣기 전에** 판정 ───────────────────────────────
# 소스 검사(test_ux_parity)와 별개로 **실제 반환값**을 본다. 배선만 맞고 조건이 뒤집혀 있으면
# 소스 검사는 통과하고 운영에서만 터진다.
#
# TASK-20260901T190000 로 판정 대상이 바뀌었다: 종전 「서버 계정 LLM 이 닫혔으면 거절」은
# 라이브에서 그래프 'AI 능동 분석' 을 통째로 막았고 사용자가 그것을 제보했다. 새 계약은
# 「**둘 중 하나라도**(서버 LLM · 연결된 개인 AI) 있으면 진행」이다. 지켜야 할 것은 그대로 —
# *큐에 넣어 놓고 한참 뒤 알 수 없는 실패로 끝내지 않는다.*
@pytest.mark.parametrize("call", [
    lambda: na.enqueue_analysis("ds1", "ds1:app.T0"),
    lambda: na.enqueue_schema_analysis("ds1", "ds1:app"),
])
def test_enqueue_refuses_when_there_is_nowhere_to_run(monkeypatch, call):
    """서버 LLM 닫힘 + 위임할 러너 없음 → 적재 전에 거절."""
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(na, "delegation_possible", lambda who: False)
    res = call()
    assert res["ok"] is False
    # 사용자가 **스스로 할 수 있는 일**을 안내한다("운영자에게 문의" 로 끝내지 않는다) —
    # 종전 문구는 그 사람이 아무것도 못 하고 기다리게 만들었다.
    assert "내 AI 연결" in str(res.get("reason") or "")


@pytest.mark.parametrize("call", [
    lambda: na.enqueue_analysis("ds1", "ds1:app.T0"),
    lambda: na.enqueue_schema_analysis("ds1", "ds1:app"),
])
def test_enqueue_proceeds_when_a_personal_ai_is_connected(monkeypatch, call):
    """연결된 개인 AI 가 있으면 **게이트가 막지 않는다** — 제보된 결함이 고쳐진 지점.

    적재 자체는 PG 가 없어 실패하지만, 그 사유가 **게이트 문구가 아니어야** 한다.
    (게이트가 아직 막고 있으면 여기서 '내 AI 연결' 안내가 되돌아온다.)
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(na, "delegation_possible", lambda who: True)
    res = call()
    assert "내 AI 연결" not in str(res.get("reason") or ""), (
        "연결된 AI 가 있는데도 게이트가 막고 있다 — 사용자 제보의 그 상태다")
