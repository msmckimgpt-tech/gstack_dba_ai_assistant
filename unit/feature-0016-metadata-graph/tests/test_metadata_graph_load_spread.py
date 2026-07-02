"""feature-0016 insight-load-spread: sync_graph batched/incremental 회귀 (mock, DB 불요, pytest 전용).

sync_graph 가
  (a) since 지정 시 각 관계형 SELECT 에 updated_at 증분 필터를 붙이고(변경분만 MERGE),
  (b) owned 연결에서 _SYNC_MERGE_BATCH 마다 batched commit 하며 finally 에서 autocommit 을 복원하고,
  (c) synced_at(다음 워터마크로 쓸 이번 sync 서버시각)을 반환하는지
검증한다. autocommit 개별-커밋 시 8K 규모 5.7만 WAL fsync 폭주를 유발하던 것을 batched/증분으로 평탄화.
"""
import os
import sys

_MODULES = os.environ.get("MG_MODULES_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "..", "feature-0002-agent-core", "src", "modules")
sys.path.insert(0, os.path.abspath(_MODULES))

import metadata_graph as mg  # noqa: E402


class _Cur:
    """SQL 을 기록하고, SELECT now()/table_descriptions/cypher 를 흉내내는 mock 커서."""

    def __init__(self, store):
        self._store = store
        self._rows = []

    def execute(self, sql, params=None):
        self._store["sqls"].append(sql)
        s = sql.strip().lower()
        if s.startswith("select now()"):
            self._rows = [["2026-07-03T00:00:00+00:00"]]
        elif "from table_descriptions" in s:
            self._rows = list(self._store.get("table_rows", []))
        elif "ag_catalog.cypher" in s:
            self._rows = [["ok"]]            # _merge_vertex/_merge_edge 의 RETURN
        elif s.startswith("select"):
            self._rows = []                  # 그 외 관계형 SSOT 조회는 빈 결과(투영 대상 0)
        else:
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _Conn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True

    def cursor(self):
        return _Cur(self._store)

    def commit(self):
        self._store["commits"] += 1

    def rollback(self):
        self._store["rollbacks"] += 1

    def close(self):
        pass


def _mk(monkeypatch, table_rows=None):
    store = {"sqls": [], "commits": 0, "rollbacks": 0, "table_rows": table_rows or []}
    conn = _Conn(store)
    monkeypatch.setattr(mg, "_rw_conn", lambda c: (conn, True))
    monkeypatch.setattr(mg, "_ensure_graph_indexes", lambda cur: None)
    return store, conn


def test_sync_graph_since_adds_incremental_filter(monkeypatch):
    store, _ = _mk(monkeypatch)
    rep = mg.sync_graph(since="2026-07-01T00:00:00Z")
    joined = " || ".join(store["sqls"])
    assert "updated_at > %s" in joined                       # 증분 필터가 SELECT 에 붙음
    assert rep["since"] == "2026-07-01T00:00:00Z"
    assert rep["synced_at"] == "2026-07-03T00:00:00+00:00"   # 다음 워터마크 반환


def test_sync_graph_full_has_no_incremental_filter(monkeypatch):
    store, _ = _mk(monkeypatch)
    mg.sync_graph(since=None)
    joined = " || ".join(store["sqls"])
    assert "updated_at > %s" not in joined                   # full 은 증분 필터 없음(전량)


def test_sync_graph_owned_commits_and_restores_autocommit(monkeypatch):
    store, conn = _mk(monkeypatch)
    mg.sync_graph()
    assert store["commits"] >= 1        # 최종 force 커밋(batched 트랜잭션 경계)
    assert store["rollbacks"] == 0
    assert conn.autocommit is True      # finally 에서 autocommit 복원(연결 close 안전)


def test_sync_graph_batched_commits_by_size(monkeypatch):
    monkeypatch.setattr(mg, "_SYNC_MERGE_BATCH", 1)          # 1 MERGE 마다 커밋
    rows = [("s", "sch", "t1", "d", "manual"), ("s", "sch", "t2", "d", "manual")]
    store, _ = _mk(monkeypatch, table_rows=rows)
    rep = mg.sync_graph()
    assert rep["tables"] == 2
    assert store["commits"] >= 2        # 2 테이블 × batch1 → 중간 커밋 발생(개별-커밋 아님, 묶음)


class _FailCur(_Cur):
    """table_descriptions SELECT(내부 try 밖)에서 예외를 던져 sync_graph 최상위 except→rollback 유도."""

    def execute(self, sql, params=None):
        super().execute(sql, params)
        if "from table_descriptions" in sql.strip().lower():
            raise RuntimeError("boom during table_descriptions read")


class _FailConn(_Conn):
    def cursor(self):
        return _FailCur(self._store)


def test_sync_graph_rollback_on_error_restores_autocommit(monkeypatch):
    store = {"sqls": [], "commits": 0, "rollbacks": 0, "table_rows": []}
    conn = _FailConn(store)
    monkeypatch.setattr(mg, "_rw_conn", lambda c: (conn, True))
    monkeypatch.setattr(mg, "_ensure_graph_indexes", lambda cur: None)
    rep = mg.sync_graph()
    assert rep["errors"] >= 1            # 예외가 telemetry 로 집계(비차단 반환)
    assert store["rollbacks"] >= 1       # owned 배치 트랜잭션 롤백
    assert conn.autocommit is True       # finally 에서 autocommit 복원(연결 close 안전)


# ── watermark round-trip (agent_runtime.kv) ────────────────────────────────
class _KvCur:
    def __init__(self, store):
        self._store = store
        self._row = None

    def execute(self, sql, params):
        s = sql.strip().lower()
        if s.startswith("insert into agent_runtime.kv"):
            self._store[(params[0], params[1])] = params[2]        # (conv, key) → value
        elif s.startswith("select value from agent_runtime.kv"):
            v = self._store.get((params[0], params[1]))
            self._row = [v] if v is not None else None

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _KvConn:
    def __init__(self, store):
        self._store = store

    def cursor(self):
        return _KvCur(self._store)

    def close(self):
        pass


def test_watermark_set_get_roundtrip_and_scope_isolation(monkeypatch):
    kv = {}
    monkeypatch.setattr(mg, "_rw_conn", lambda c: (_KvConn(kv), True))
    monkeypatch.setattr(mg, "_ro_conn", lambda c: (_KvConn(kv), True))
    assert mg.get_sync_watermark("scopeA") is None                 # 최초 None → full 폴백
    mg.set_sync_watermark("2026-07-03T00:00:00+00:00", scope_key="scopeA")
    assert mg.get_sync_watermark("scopeA") == "2026-07-03T00:00:00+00:00"
    assert mg.get_sync_watermark("scopeB") is None                 # scope 별 격리
    mg.set_sync_watermark("2026-07-03T01:00:00+00:00")             # 전체(__all__) scope
    assert mg.get_sync_watermark() == "2026-07-03T01:00:00+00:00"
