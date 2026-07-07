"""feature-0016 graph-funcproc-uxfix 단위 테스트 (REQ-20260703, ADR-016·017).

DB/AGE 불요 — fake cursor/conn 으로 SQL·Cypher 문자열과 파라미터를 캡처해 검증한다.
  ① routines.parse_referenced_tables / introspect_and_store (정의 파싱 + upsert 형태)
  ① metadata_graph.sync_routine (Routine MERGE + HAS_ROUTINE + ROUTINE_USES + key 네임스페이스)
  ③ node_analysis parent-table 승격 (_fetch_context parent 메타 → _score_candidates same-depth →
     _enqueue_neighbors depth 유지)
  ⑤ enqueue_analysis user_prompt 저장 + _load_anchor 지침 토큰 합류 + 마이그 창 폴백

실행: python3 -m pytest unit/feature-0002-agent-core/tests/test_graph_funcproc_uxfix.py -q
"""
import json

import pytest

from modules import node_analysis as na
from modules import routines as rt
from modules import metadata_graph as mg


# ── fakes ─────────────────────────────────────────────────────────────────────
class FakeCur:
    """execute 를 (sql, params) 로 기록하고, marker 매칭 행을 돌려주는 범용 fake cursor."""

    def __init__(self, rows_by_marker=None):
        self.executed = []
        self._rows = []
        self.rows_by_marker = list(rows_by_marker or [])

    def execute(self, sql, params=None):
        self.executed.append((str(sql), params))
        self._rows = []
        for marker, rows in self.rows_by_marker:
            if marker in str(sql):
                self._rows = list(rows)
                break

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def close(self):
        pass


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, cur):
        self._cur = cur
        self.autocommit = True

    def cursor(self):
        return self._cur

    def transaction(self):
        return _Tx()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _sqls(cur):
    return [s for s, _ in cur.executed]


# ── ① routines: 정의 파싱 ─────────────────────────────────────────────────────
TABLES = ["Achievement", "AchievementReward", "T_PurchaseLog", "Users"]


def test_parse_refs_read_write_kinds():
    body = """
    CREATE PROCEDURE usp_GiveReward AS
    BEGIN
      SELECT * FROM dbo.Achievement a JOIN AchievementReward r ON a.Id = r.AchvId;
      INSERT INTO T_PurchaseLog (UserId) VALUES (1);
      UPDATE Users SET Cash = Cash - 10;
    END"""
    refs = {r["fqn"]: r["kind"] for r in rt.parse_referenced_tables(body, TABLES)}
    assert refs["Achievement"] == "read"
    assert refs["AchievementReward"] == "read"
    assert refs["T_PurchaseLog"] == "write"
    assert refs["Users"] == "write"


def test_parse_refs_write_wins_over_read():
    body = "SELECT * FROM Users; DELETE FROM Users WHERE 1=0;"
    refs = rt.parse_referenced_tables(body, TABLES)
    assert refs == [{"fqn": "Users", "kind": "write"}]


def test_parse_refs_excludes_temp_vars_self_and_unknown():
    body = ("SELECT * FROM #tmp; SELECT * FROM @tv; SELECT * FROM UnknownTable; "
            "SELECT * FROM usp_Self; SELECT * FROM [dk_game].[dbo].[Achievement];")
    refs = rt.parse_referenced_tables(body, TABLES, self_name="usp_Self")
    # 임시(#)·변수(@)·미존재·자기자신 제외. §56 계약 변경: 3-part qualified 식별자는 미상 qualifier
    # 레거시 폴백(④)으로 leaf-로컬 귀속 — external_tables 를 주면 실재검증 크로스/오귀속차단이 적용된다
    # (test_routine_sync_crossdb.py 에서 잠금).
    assert refs == [{"fqn": "Achievement", "kind": "read"}]


def test_parse_refs_empty_inputs():
    assert rt.parse_referenced_tables("", TABLES) == []
    assert rt.parse_referenced_tables("SELECT 1", []) == []


def test_parse_refs_ignores_comments():
    """§18.8 패널(MINOR): 주석(-- / /* */) 안의 FROM 은 유령 참조를 만들지 않는다."""
    body = "-- FROM Achievement\n/* JOIN Users */\nSELECT * FROM T_PurchaseLog"
    refs = rt.parse_referenced_tables(body, TABLES)
    assert refs == [{"fqn": "T_PurchaseLog", "kind": "read"}]


def test_parse_refs_alias_update_promoted_to_write():
    """§18.8 패널(MINOR): MSSQL alias-UPDATE — 실제 write 대상 테이블이 read 로 남지 않는다."""
    body = "UPDATE a SET Cash = 0 FROM Users a WHERE a.Id = 1"
    refs = {r["fqn"]: r["kind"] for r in rt.parse_referenced_tables(body, TABLES)}
    assert refs["Users"] == "write"


def test_introspect_and_store_upserts_with_store_schema_label():
    # 데이터소스 fake: ROUTINES 1행(프로시저) + PARAMETERS 2행(반환형 pos0 + 파라미터 pos1).
    ds_cur = FakeCur(rows_by_marker=[
        ("information_schema.ROUTINES", [("usp_GiveReward", "PROCEDURE", "SELECT * FROM Achievement")]),
        ("information_schema.PARAMETERS", [("usp_GiveReward", 0, None, None, "int"),
                                           ("usp_GiveReward", 1, "IN", "p_user", "int")]),
    ])
    ds_conn = FakeConn(ds_cur)
    kb_cur = FakeCur()
    kb_conn = FakeConn(kb_cur)
    n = rt.introspect_and_store(ds_conn, "dbo", TABLES, kb_conn=kb_conn,
                                scope_key="mssql-x", datasource_key="mssql-x",
                                store_schema="dk_game_release")
    assert n == 1
    ins = [(s, p) for s, p in kb_cur.executed if "INSERT INTO routine_objects" in s]
    assert len(ins) == 1
    sql, params = ins[0]
    assert "ON CONFLICT (scope_key, schema_name, routine_name, routine_type)" in sql
    # 스키마-slot 규약(ADR-007): 저장 라벨 = store_schema, 참조 fqn 도 라벨 접두.
    assert params[2] == "dk_game_release"
    assert params[3] == "usp_GiveReward" and params[4] == "procedure"
    assert "IN p_user int" in params[5]
    assert params[6] == "int"   # 반환형 = PARAMETERS ORDINAL_POSITION=0 (교차-방언 공통)
    refs = json.loads(params[8])
    assert refs == [{"fqn": "dk_game_release.Achievement", "kind": "read"}]


# ── ① metadata_graph.sync_routine: Cypher MERGE 형태 ──────────────────────────
def test_sync_routine_merges_routine_and_uses_edges():
    cur = FakeCur()
    mg.sync_routine(cur, "mssql-x", "dk_game_release", "usp_GiveReward", "procedure",
                    params="IN p_user int",
                    refs=[{"fqn": "dk_game_release.Achievement", "kind": "read"}])
    sqls = _sqls(cur)
    joined = "\n".join(sqls)
    # key 네임스페이스: `schema.name()` — 동명 테이블 키와 충돌하지 않는다(ADR-013).
    assert "MERGE (n:Routine {key: 'mssql-x:dk_game_release.usp_GiveReward()'})" in joined
    assert "routine_type = 'procedure'" in joined
    assert ":HAS_ROUTINE" in joined
    assert ":ROUTINE_USES" in joined
    assert "relation_type = 'read'" in joined
    # 참조 Table 앵커링(고아 방지).
    assert "MERGE (n:Table {key: 'mssql-x:dk_game_release.Achievement'})" in joined
    # §18.8 패널(MAJOR): 정의 변경으로 사라진 참조의 stale ROUTINE_USES 회수(delete-then-merge).
    assert "DELETE u" in joined and joined.index("DELETE u") < joined.index("MERGE (a)-[r:ROUTINE_USES]")


def test_routine_labels_whitelisted():
    assert "Routine" in mg._VLABELS
    assert {"HAS_ROUTINE", "ROUTINE_USES"} <= mg._ELABELS
    assert {"routine_type", "params"} <= mg._PROP_KEYS


# ── ③ parent-table 승격 ───────────────────────────────────────────────────────
def _anchor():
    return na._build_anchor("dk:dbo.Achievement", "Table", "Achievement", "업적 정의")


def test_fetch_context_records_parent_for_column_node(monkeypatch):
    """Column 노드의 HAS_COLUMN(부모→자신) 이웃이 parent 메타로 기록된다."""
    def fake_neighborhood(node_key, depth=1, conn=None):
        return {
            "nodes": [
                {"key": "dk:dbo.Item.ItemId", "label": "Column", "name": "ItemId", "fqn": "dbo.Item.ItemId"},
                {"key": "dk:dbo.Item", "label": "Table", "name": "Item", "fqn": "dbo.Item"},
            ],
            "edges": [
                {"source": "dk:dbo.Item", "target": "dk:dbo.Item.ItemId", "type": "HAS_COLUMN"},
            ],
        }
    monkeypatch.setattr(mg, "neighborhood", fake_neighborhood)
    ctx = na._fetch_context("dk:dbo.Item.ItemId", None)
    meta = ctx["neighbor_meta"].get("dk:dbo.Item")
    assert meta and meta.get("parent") is True


def test_score_candidates_promotes_parent_table_same_depth():
    """참조 컬럼(깊은 depth)의 소속 테이블 — 이름 무연관이라도 승격(rel 0.5) + same_depth 플래그."""
    a = _anchor()
    parent = {"label": "Table", "key": "dk:dbo.ItemMaster", "name": "ItemMaster", "fqn": "dbo.ItemMaster"}
    ctx = {"neighbors": [parent], "neighbor_meta": {parent["key"]: {"kind": "parent_table", "parent": True}}}
    kept = na._score_candidates(ctx, cur_depth=2, anchor=a)
    assert len(kept) == 1
    rel, node, same_depth = kept[0]
    assert node["key"] == parent["key"]
    assert same_depth is True
    assert rel >= 0.5 - 1e-9


def test_score_candidates_parent_depth0_not_same_depth():
    """§18.8 패널(BLOCKING 수정): 루트가 Column 일 때(cur_depth=0) 부모 테이블은 depth 0 승격 금지 —
    depth-0 '하위 컬럼 무조건 통과' 규칙이 승격 테이블에 재발화해 sibling flood 가 나던 결함 봉인."""
    a = na._build_anchor("dk:dbo.Item.ItemId", "Column", "ItemId", "")
    parent = {"label": "Table", "key": "dk:dbo.Item", "name": "Item", "fqn": "dbo.Item"}
    ctx = {"neighbors": [parent], "neighbor_meta": {parent["key"]: {"kind": "parent_table", "parent": True}}}
    kept = na._score_candidates(ctx, cur_depth=0, anchor=a)
    assert len(kept) == 1
    assert kept[0][2] is False   # same_depth 금지 → depth 1 로 enqueue(부모는 분석되되 flood 차단)


def test_score_candidates_parent_cross_scope_attenuated():
    a = _anchor()
    parent = {"label": "Table", "key": "other:dbo.ItemMaster", "name": "ItemMaster", "fqn": "dbo.ItemMaster"}
    ctx = {"neighbors": [parent], "neighbor_meta": {parent["key"]: {"kind": "parent_table", "parent": True}}}
    kept = na._score_candidates(ctx, cur_depth=2, anchor=a)
    assert len(kept) == 1
    rel = kept[0][0]
    assert rel < 0.5   # 교차 제품 감쇠(CROSS_SCOPE_FACTOR)


def test_enqueue_neighbors_parent_keeps_depth_within_budget():
    """depth_budget 마지막 층의 컬럼도 소속 테이블은 same-depth 로 enqueue 된다(예산 초과 아님)."""
    a = _anchor()
    parent = {"label": "Table", "key": "dk:dbo.ItemMaster", "name": "ItemMaster", "fqn": "dbo.ItemMaster"}
    far = {"label": "Column", "key": "dk:dbo.AchievementReward.RewardId", "name": "RewardId",
           "fqn": "dbo.AchievementReward.RewardId"}
    ctx = {"neighbors": [parent, far],
           "neighbor_meta": {parent["key"]: {"kind": "parent_table", "parent": True},
                             far["key"]: {"kind": "reference"}}}
    cur = FakeCur(rows_by_marker=[
        ("FROM node_analysis_runs", [(2, 150, 5)]),          # depth_budget=2, node_budget=150, enqueued=5
        ("INSERT INTO node_analysis_jobs", [(101,)]),        # RETURNING id
    ])
    c = FakeConn(cur)
    inserted = na._enqueue_neighbors(c, cur, "run1", "dk", ctx, cur_depth=2, anchor=a)
    ins = [(s, p) for s, p in cur.executed if "INSERT INTO node_analysis_jobs" in s]
    # cur_depth=2 == depth_budget: 일반 이웃(depth 3)은 예산 초과로 미삽입, parent 는 depth 2 로 삽입.
    assert inserted == 1
    assert len(ins) == 1
    assert ins[0][1][6] == 2          # depth 파라미터(7번째) == cur_depth 유지
    assert ins[0][1][2] == parent["key"]


# ── ⑤ user_prompt ────────────────────────────────────────────────────────────
def test_enqueue_analysis_stores_user_prompt():
    cur = FakeCur(rows_by_marker=[
        ("SELECT run_id, enqueued, done, failed FROM node_analysis_runs", []),   # 재사용 run 없음
    ])
    c = FakeConn(cur)
    res = na.enqueue_analysis("dk", "dk:dbo.Achievement", user_prompt="  결제 흐름 관점에서 분석  ",
                              conn=c)
    assert res.get("ok") is True
    run_ins = [(s, p) for s, p in cur.executed if "INSERT INTO node_analysis_runs" in s]
    assert run_ins and "user_prompt" in run_ins[0][0]
    assert run_ins[0][1][-1] == "결제 흐름 관점에서 분석"   # strip + 마지막 파라미터


# ── graphux7(#4): 중복 큐잉 방어 — 진행 중 run 재사용 시 진행 카운트(progress) 반환 ──────────
def test_enqueue_analysis_reused_returns_progress():
    """이미 running run 이 있으면 재큐잉하지 않고 reused=True + progress{enqueued,done,failed} 반환."""
    cur = FakeCur(rows_by_marker=[
        # 재사용 run 존재 — (run_id, enqueued, done, failed)
        ("SELECT run_id, enqueued, done, failed FROM node_analysis_runs", [("run-existing", 8, 3, 1)]),
    ])
    c = FakeConn(cur)
    res = na.enqueue_analysis("dk", "dk:dbo.Achievement", conn=c)
    assert res.get("ok") is True
    assert res.get("reused") is True
    assert res.get("run_id") == "run-existing"
    assert res.get("progress") == {"enqueued": 8, "done": 3, "failed": 1}
    # 재사용 경로는 새 run 을 INSERT 하지 않는다(중복 큐잉 방어).
    assert not [s for s, _ in cur.executed if "INSERT INTO node_analysis_runs" in s]


def test_load_anchor_merges_prompt_tokens():
    cur = FakeCur(rows_by_marker=[
        ("FROM node_analysis_runs WHERE run_id", [("dk:dbo.Achievement", "Table", "Achievement",
                                                   "결제 환불 흐름 위주로")]),
    ])
    c = FakeConn(cur)
    cache = {}
    anchor = na._load_anchor(c, cur, "run1", cache)
    assert anchor is not None
    assert anchor.get("prompt") == "결제 환불 흐름 위주로"
    assert "결제" in anchor["tokens"] and "환불" in anchor["tokens"]
    assert "achievement" in anchor["tokens"]   # 기존 앵커 토큰 보존


def test_enqueue_analysis_user_prompt_column_fallback():
    """마이그레이션 창(0034 미적용): user_prompt INSERT 실패 시 legacy INSERT 로 run 은 생성된다."""
    class FallbackCur(FakeCur):
        def execute(self, sql, params=None):
            if "user_prompt" in str(sql) and "INSERT INTO node_analysis_runs" in str(sql):
                self.executed.append((str(sql), params))
                raise RuntimeError("UndefinedColumn: user_prompt")
            return super().execute(sql, params)

    cur = FallbackCur(rows_by_marker=[("SELECT run_id, enqueued, done, failed FROM node_analysis_runs", [])])
    c = FakeConn(cur)
    na._UPROMPT_COL_WARNED["done"] = False
    res = na.enqueue_analysis("dk", "dk:dbo.Achievement", user_prompt="지침", conn=c)
    assert res.get("ok") is True
    legacy = [s for s, _ in cur.executed
              if "INSERT INTO node_analysis_runs" in s and "user_prompt" not in s]
    assert legacy, "legacy INSERT 폴백이 실행되어야 한다"


def test_relevance_routine_use_counts_as_content():
    """ROUTINE_USES 이웃(함수·프로시저)은 content 신호로 인정 — 재귀·분석 대상이 될 수 있다."""
    a = _anchor()
    n = {"label": "Routine", "key": "dk:dbo.usp_NoNameOverlap()", "name": "usp_NoNameOverlap",
         "fqn": "dbo.usp_NoNameOverlap()"}
    rel = na._relevance(n, {"kind": "routine_use"}, a)
    assert rel >= na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN
