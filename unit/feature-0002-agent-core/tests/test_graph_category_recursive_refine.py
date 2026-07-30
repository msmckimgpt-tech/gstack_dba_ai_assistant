"""feature-0016 §55 (graph-category-recursive-refine) 단위 테스트 — DB/AGE 불요(monkeypatch·fake).

검증 축:
  C(재귀 정합): thin 판정 · refine payload 헬퍼 · back-refine 재-pending(캡·카운터) ·
    _enqueue_neighbors anchor_key 상속 · _load_anchor per-seed · suggested_links 가드.
  B(크로스-DB): infer_cross_datasource 일반화(intra-DS 크로스 스키마 · reverse-dup · per-mode min_sim) ·
    MSSQL 3-part 프로브(dbo 가드) · fetch_probe_candidates 한끝 OR-매칭.
  D(백필): 미처리(hash NULL) 우선 정렬.
"""
import json

from modules import node_analysis as na
from modules import relationships as R


# ── fakes ─────────────────────────────────────────────────────────────────────
class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or {}          # substring -> fetch 결과(list=fetchall, tuple=fetchone)
        self.executed = []
        self._last = None
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))
        self._last = None
        for pat, row in self.rows.items():
            if pat in sql:
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


class TxConn:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur

    def transaction(self):
        import contextlib
        return contextlib.nullcontext()

    def close(self):
        pass


def _mk_analysis(summary="s" * 200, rel="r", usage="u", caveats=""):
    return json.dumps({"summary": summary, "relationships": rel, "usage": usage, "caveats": caveats},
                      ensure_ascii=False)


# ── C: thin 판정 + refine 헬퍼 ────────────────────────────────────────────────
def test_analysis_is_thin_cases():
    assert na._analysis_is_thin(None, 120) is True                       # 빈 분석문
    assert na._analysis_is_thin(_mk_analysis(summary="짧음"), 120) is True   # summary 임계 미만
    assert na._analysis_is_thin(_mk_analysis(rel="", usage=""), 120) is True  # 관계·활용 공란
    assert na._analysis_is_thin(_mk_analysis(), 120) is False            # 충실 분석
    assert na._analysis_is_thin("not-json{", 120) is False               # 파싱 불가 — 보수(무한 재분석 방지)


def test_parse_analysis_trims_fields():
    obj = na._parse_analysis(_mk_analysis(summary="x" * 900))
    assert obj and len(obj["summary"]) == 700 and obj["relationships"] == "r"
    assert na._parse_analysis("broken{") is None and na._parse_analysis("") is None


def test_latest_done_analysis_excludes_current_job():
    cur = FakeCursor(rows={"FROM node_analysis_jobs": (_mk_analysis(summary="prev"),)})
    obj = na._latest_done_analysis(cur, "ds1", "ds1:app.T", exclude_id=7)
    assert obj and obj["summary"] == "prev"
    sql, params = cur.executed[-1]
    assert "status='done'" in sql and params[2] == 7


def test_related_findings_from_run_neighbors():
    rows = [("N1", "Table", _mk_analysis(summary="n1요약")), ("N2", "Column", _mk_analysis(summary="n2요약", rel=""))]
    cur = FakeCursor(rows={"FROM node_analysis_jobs": rows})
    ctx = {"neighbor_meta": {"ds1:app.N1": {}, "ds1:app.N2": {}}}
    rf = na._related_findings(cur, "run1", ctx, exclude_key="ds1:app.T")
    assert [x["name"] for x in rf] == ["N1", "N2"] and rf[0]["summary"] == "n1요약"


# ── C: back-refine — thin done 재-pending(pass_no+1) + 캡 + 카운터 ────────────
class BackrefineCursor(FakeCursor):
    def __init__(self, done_rows, used=0):
        super().__init__()
        self._done = done_rows
        self._used = used
        self.updates = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))
        if "COUNT(*)" in sql and "pass_no > 0" in sql:
            self._last = (self._used,)
        elif "SELECT id, analysis" in sql:
            self._last = self._done
        elif "SET status='pending', pass_no = pass_no + 1" in sql:
            self.updates.append(params)
            self._last = None
        else:
            self._last = None


def test_backrefine_repends_thin_only_and_counts():
    done = [(11, _mk_analysis(summary="짧")), (12, _mk_analysis()), (13, None)]
    cur = BackrefineCursor(done)
    ctx = {"neighbor_meta": {"k1": {}, "k2": {}, "k3": {}}}
    n = na._backrefine_neighbors(TxConn(cur), cur, "run1", 99, ctx)
    assert n == 2                       # thin(11)+빈분석(13)만 — 충실(12) 제외
    assert [p[0] for p in cur.updates] == [11, 13]
    enq = [e for e in cur.executed if "SET enqueued = enqueued +" in e[0]]
    assert enq and enq[0][1] == (2, "run1")   # 재작업 단위 — done ≤ enqueued 단조 유지


def test_backrefine_respects_refine_max_cap(monkeypatch):
    monkeypatch.setattr(na._cfg, "AGENT_NODE_ANALYSIS_REFINE_MAX", 1, raising=False)
    done = [(11, _mk_analysis(summary="짧")), (13, _mk_analysis(summary="더짧"))]
    cur = BackrefineCursor(done)
    n = na._backrefine_neighbors(TxConn(cur), cur, "run1", 99, {"neighbor_meta": {"k1": {}, "k2": {}}})
    assert n == 1 and len(cur.updates) == 1


def test_backrefine_zero_when_cap_used(monkeypatch):
    monkeypatch.setattr(na._cfg, "AGENT_NODE_ANALYSIS_REFINE_MAX", 5, raising=False)
    cur = BackrefineCursor([(11, _mk_analysis(summary="짧"))], used=5)
    n = na._backrefine_neighbors(TxConn(cur), cur, "run1", 99, {"neighbor_meta": {"k1": {}}})
    assert n == 0 and not cur.updates


# ── C: _enqueue_neighbors anchor_key 상속 ─────────────────────────────────────
def test_enqueue_neighbors_inherits_anchor_key(monkeypatch):
    monkeypatch.setitem(na._REFINE_COLS, "ok", True)
    monkeypatch.setattr(na, "_score_candidates", lambda ctx, d, anchor: [
        (0.9, {"key": "ds1:app.N1", "label": "Table", "name": "N1", "fqn": "app.N1"}, False)])
    cur = FakeCursor(rows={"FROM node_analysis_runs": (2, 48, 4),
                           "INSERT INTO node_analysis_jobs": [(1,)]})
    n = na._enqueue_neighbors(TxConn(cur), cur, "run1", "ds1", {}, 0, {}, anchor_key="ds1:app.SEED")
    assert n == 1
    ins = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]][0]
    assert "anchor_key" in ins[0] and ins[1][-1] == "ds1:app.SEED"


def test_enqueue_neighbors_legacy_without_anchor(monkeypatch):
    monkeypatch.setitem(na._REFINE_COLS, "ok", False)
    monkeypatch.setattr(na, "_score_candidates", lambda ctx, d, anchor: [
        (0.9, {"key": "ds1:app.N1", "label": "Table", "name": "N1", "fqn": "app.N1"}, False)])
    cur = FakeCursor(rows={"FROM node_analysis_runs": (2, 48, 4),
                           "INSERT INTO node_analysis_jobs": [(1,)]})
    n = na._enqueue_neighbors(TxConn(cur), cur, "run1", "ds1", {}, 0, {}, anchor_key="ds1:app.SEED")
    assert n == 1
    ins = [e for e in cur.executed if "INSERT INTO node_analysis_jobs" in e[0]][0]
    assert "anchor_key" not in ins[0]


# ── C: _load_anchor per-seed(자기 노드 재사용·prompt 상속) ─────────────────────
def test_load_anchor_per_seed_with_self_node(monkeypatch):
    cur = FakeCursor(rows={"FROM node_analysis_runs": ("ds1:sch", "Schema", "sch", "지침어휘")})
    c = TxConn(cur)
    monkeypatch.setattr(na, "_fetch_context", lambda key, conn: {"root": {}})
    cache = {}
    seed_node = {"label": "Table", "name": "Achievement", "fqn": "app.Achievement",
                 "description": "업적 정의"}
    a = na._load_anchor(c, cur, "run1", cache, anchor_key="ds1:app.Achievement", self_node=seed_node)
    assert a["key"] == "ds1:app.Achievement" and a["label"] == "Table"
    assert "achievement" in a["tokens"]
    assert a.get("prompt") == "지침어휘"           # run user_prompt 상속(§55 — per-seed 앵커에도 합류)
    # 캐시: run-root 와 seed 가 분리 키
    assert "run1" in cache and "run1|ds1:app.Achievement" in cache


def test_load_anchor_empty_key_returns_run_root(monkeypatch):
    cur = FakeCursor(rows={"FROM node_analysis_runs": ("ds1:app.T", "Table", "T", None)})
    monkeypatch.setattr(na, "_fetch_context", lambda key, conn: {"root": {"description": ""}})
    cache = {}
    a = na._load_anchor(TxConn(cur), cur, "run1", cache)
    assert a["key"] == "ds1:app.T"


# ── C: suggested_links — 컨텍스트 화이트리스트·root 연루·컬럼 실재·캡 ────────────
def _links_ctx():
    root = {"label": "Table", "key": "ds1:app.Achievement", "name": "Achievement", "fqn": "app.Achievement"}
    ctx = {
        "neighbors": [
            {"label": "Table", "key": "ds1:app.ItemMaster", "name": "ItemMaster", "fqn": "app.ItemMaster"},
            {"label": "Column", "key": "ds1:app.Achievement.ItemID", "name": "ItemID", "fqn": "app.Achievement.ItemID"},
        ],
        "columns": [{"name": "ItemID"}, {"name": "UniqueID"}],
    }
    return root, ctx


def test_suggested_links_ingests_valid_and_rejects_hallucination(monkeypatch):
    calls = []
    from modules import relationships as _rel
    monkeypatch.setattr(_rel, "upsert_relationship",
                        lambda conn, scope, **kw: calls.append((scope, kw)) or True)
    root, ctx = _links_ctx()
    obj = {"suggested_links": [
        {"from_table": "Achievement", "from_column": "ItemID", "to_table": "ItemMaster", "to_column": "ItemID"},
        {"from_table": "Achievement", "from_column": "NoSuchCol", "to_table": "ItemMaster", "to_column": "ItemID"},  # root 컬럼 실재 실패
        {"from_table": "GhostTable", "from_column": "a", "to_table": "ItemMaster", "to_column": "b"},               # 컨텍스트 밖(환각)
        {"from_table": "ItemMaster", "from_column": "x", "to_table": "ItemMaster", "to_column": "x"},               # self
    ]}
    n = na._ingest_suggested_links(TxConn(FakeCursor()), "ds1", root, ctx, obj)
    assert n == 1 and len(calls) == 1
    scope, kw = calls[0]
    assert scope == "ds1" and kw["source"] == "llm_insight"
    assert kw["src_table"] == "Achievement" and kw["tgt_table"] == "ItemMaster"
    assert kw["src_schema"] == "app" and kw["tgt_schema"] == "app"


def test_suggested_links_requires_root_involvement(monkeypatch):
    from modules import relationships as _rel
    calls = []
    monkeypatch.setattr(_rel, "upsert_relationship", lambda conn, scope, **kw: calls.append(kw) or True)
    root, ctx = _links_ctx()
    ctx["neighbors"].append({"label": "Table", "key": "ds1:app.Other", "name": "Other", "fqn": "app.Other"})
    obj = {"suggested_links": [
        {"from_table": "ItemMaster", "from_column": "a", "to_table": "Other", "to_column": "b"}]}  # 제3자 간 — root 미연루
    assert na._ingest_suggested_links(TxConn(FakeCursor()), "ds1", root, ctx, obj) == 0 and not calls


def test_suggested_links_cap(monkeypatch):
    from modules import relationships as _rel
    calls = []
    monkeypatch.setattr(_rel, "upsert_relationship", lambda conn, scope, **kw: calls.append(kw) or True)
    monkeypatch.setattr(na._cfg, "AGENT_NODE_ANALYSIS_SUGGEST_LINKS_MAX", 2, raising=False)
    root, ctx = _links_ctx()
    link = {"from_table": "Achievement", "from_column": "ItemID", "to_table": "ItemMaster", "to_column": "ItemID"}
    obj = {"suggested_links": [dict(link, to_column=f"c{i}") for i in range(6)]}
    assert na._ingest_suggested_links(TxConn(FakeCursor()), "ds1", root, ctx, obj) == 2 and len(calls) == 2


def test_suggested_links_non_table_root_skipped(monkeypatch):
    root = {"label": "Column", "key": "ds1:app.T.c", "name": "c", "fqn": "app.T.c"}
    assert na._ingest_suggested_links(TxConn(FakeCursor()), "ds1", root, {"neighbors": []},
                                      {"suggested_links": [{"from_table": "T", "from_column": "c",
                                                            "to_table": "U", "to_column": "d"}]}) == 0


# ── B: infer 일반화 — intra-DS 크로스 스키마 후보 ──────────────────────────────
class XdsCursor:
    """rag_objects 임베딩 base + kNN 매칭 + column_descriptions 응답 시뮬레이터."""
    def __init__(self, base, knn, cols):
        self._base, self._knn, self._cols = base, knn, cols
        self._last = []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append(" ".join(sql.split()))
        if "ORDER BY o.updated_at" in sql:
            self._last = self._base
        elif "t2.embedding <=>" in sql:
            self._last = self._knn
        elif "FROM column_descriptions" in sql:
            key = (params[0], params[1], params[2])
            self._last = [(c,) for c in self._cols.get(key, [])]
        else:
            self._last = []

    def fetchall(self):
        return self._last

    def close(self):
        pass


def _xds_env(monkeypatch, knn):
    base = [("common", "ds1", "gamedb", "Item", "ds1:gamedb.Item", "[0.1]")]
    cols = {("common", "gamedb", "Item"): ["itemid", "name"],
            ("common", "logdb", "ItemLog"): ["itemid", "ts"],
            ("common2", "otherdb", "Item"): ["itemid"]}
    cur = XdsCursor(base, knn, cols)
    monkeypatch.setattr(R, "_ro_conn", lambda conn: (TxConn(cur), False))
    import modules.semantic_cluster as sc
    monkeypatch.setattr(sc, "_effective_schema", lambda dsk, okey, sch: sch)
    return cur


def test_infer_xschema_intra_ds_candidates(monkeypatch):
    """같은 ds 다른 스키마(DB) — include_xschema 로 발굴, src_ds==tgt_ds(프로브 편입)."""
    knn = [("common", "ds1", "logdb", "ItemLog", "ds1:logdb.ItemLog", 0.88)]
    _xds_env(monkeypatch, knn)
    out = R.infer_cross_datasource_relationships(include_xds=False, include_xschema=True)
    assert len(out) == 1
    e = out[0]
    assert e["src_ds"] == e["tgt_ds"] == "ds1"
    assert e["src_schema"] == "gamedb" and e["tgt_schema"] == "logdb"
    assert e["src_column"] == e["tgt_column"] == "itemid"


def test_infer_xschema_same_schema_excluded(monkeypatch):
    """같은 DB(스키마) 내부 쌍은 제외 — per-schema 명명 추론의 영역."""
    knn = [("common", "ds1", "gamedb", "Item2", "ds1:gamedb.Item2", 0.95)]
    _xds_env(monkeypatch, knn)
    assert R.infer_cross_datasource_relationships(include_xds=False, include_xschema=True) == []


def test_infer_xschema_min_sim_gate(monkeypatch):
    knn = [("common", "ds1", "logdb", "ItemLog", "ds1:logdb.ItemLog", 0.80)]   # < 0.86
    _xds_env(monkeypatch, knn)
    assert R.infer_cross_datasource_relationships(include_xds=False, include_xschema=True) == []


def test_infer_xds_disabled_skips_cross_datasource(monkeypatch):
    knn = [("common2", "ds2", "otherdb", "Item", "ds2:otherdb.Item", 0.95)]
    _xds_env(monkeypatch, knn)
    assert R.infer_cross_datasource_relationships(include_xds=False, include_xschema=True) == []
    out = R.infer_cross_datasource_relationships(include_xds=True, include_xschema=False)
    assert len(out) == 1 and out[0]["tgt_ds"] == "ds2"


def test_infer_xschema_reverse_dup_canonical(monkeypatch):
    """(schema,table) 사전순 큰 쪽에서 발화한 쌍은 제외 — A→B·B→A 중복 방지."""
    base = [("common", "ds1", "logdb", "ItemLog", "ds1:logdb.ItemLog", "[0.1]")]
    knn = [("common", "ds1", "gamedb", "Item", "ds1:gamedb.Item", 0.9)]   # gamedb < logdb → 역방향
    cols = {("common", "logdb", "ItemLog"): ["itemid"], ("common", "gamedb", "Item"): ["itemid"]}
    cur = XdsCursor(base, knn, cols)
    monkeypatch.setattr(R, "_ro_conn", lambda conn: (TxConn(cur), False))
    import modules.semantic_cluster as sc
    monkeypatch.setattr(sc, "_effective_schema", lambda dsk, okey, sch: sch)
    assert R.infer_cross_datasource_relationships(include_xds=False, include_xschema=True) == []


# ── B: MSSQL 3-part 프로브 + dbo 가드 ─────────────────────────────────────────
def test_dialect_mssql_probe_three_part_cross_db():
    from modules import dialects as D
    sql = D.get("mssql").probe_relationship_overlap("accountdb", "T1", "uid", "gamedb", "T2", "uid", 10)
    assert "[accountdb].[dbo].[T1]" in sql and "[gamedb].[dbo].[T2]" in sql


def test_dialect_mssql_probe_dbo_slot_stays_two_part():
    """레거시 slot='dbo'(실 스키마) — 3-part `[dbo].[dbo].[T]` 오조립 금지(실관계 오파단 방지)."""
    from modules import dialects as D
    sql = D.get("mssql").probe_relationship_overlap("dbo", "T1", "c", "", "T2", "d", 10)
    assert "[dbo].[T1]" in sql and "[dbo].[dbo]." not in sql


def test_fetch_probe_candidates_cross_db_resolved_slots_only(monkeypatch):
    """§55(+패널 BLOCKING fix): 크로스 DB 확장은 **양 slot 확정** 행에만 — ''(레거시) 포함 행은 종전
    AND 의미론(반대쪽 확정 slot 이 현재 DB 일 때만 fetch)을 유지해, ('',DBX) 행이 무관 catalog 에서
    성공-프로브 matched=0 negative 로 실관계를 오파단하지 않게 한다."""
    cur = FakeCursor(rows={"FROM table_relationships": [(1, "accountdb", "T1", "uid", "gamedb", "T2", "uid")]})
    monkeypatch.setattr(R, "_ro_conn", lambda conn: (TxConn(cur), False))
    rows = R.fetch_probe_candidates(None, "ds1", 10, db_scope="accountdb")
    assert rows and rows[0][1] == "accountdb" and rows[0][4] == "gamedb"
    sql = [e for e in cur.executed if "FROM table_relationships" in e[0]][0][0]
    # 4-분기 필터: ('','') wildcard / ''+현재DB 앵커 ×2 / 양 slot 확정 + 한끝 현재DB(크로스 DB 신규 경로)
    assert "source_schema = '' AND target_schema = ''" in sql
    assert "source_schema = '' AND lower(target_schema) = lower(%s)" in sql
    assert "target_schema = '' AND lower(source_schema) = lower(%s)" in sql
    assert "source_schema <> '' AND target_schema <> ''" in sql
    _, params = [e for e in cur.executed if "FROM table_relationships" in e[0]][0]
    assert params.count("accountdb") == 4   # db_scope 4회 바인딩(분기별)


# ── D: 시그니처 백필 — 미처리(hash NULL) 우선 정렬 ─────────────────────────────
def test_signature_backfill_orders_null_first(monkeypatch):
    from modules import semantic_cluster as SC
    cur = FakeCursor(rows={"FROM rag_objects": []})
    monkeypatch.setattr(SC, "_rw_conn", lambda conn: (TxConn(cur), False))
    SC.run_signature_backfill_pass(max_rows=100)
    sel = [e for e in cur.executed if "SELECT id, scope_key" in e[0]][0][0]
    assert "signature_text_hash IS NULL OR signature_text_hash = ''" in sel
    # sig-backfill-sweep(2026-07-30): 1순위 "미처리 우선"은 유지, 2순위는 **ASC** 로 뒤집혔다.
    #   `DESC` 는 시그니처 포맷 전수 재계산에서 방금 변환한 행을 다시 맨 앞에 놓아 영구 정체를
    #   만들었다(라이브 실측: 루틴 +38 정지). 상세는 semantic_cluster 백필 주석 · TASK sig-backfill-sweep.
    assert "DESC, updated_at ASC" in sel.replace("NULLS FIRST", "").replace("  ", " ")


# ── §18.8 패널 반영 수정분 회귀 잠금 ──────────────────────────────────────────
def test_refine_cols_probe_transient_error_not_cached(monkeypatch):
    """패널 MINOR fix: transient probe 실패는 미캐시(다음 호출 재-probe) — 컬럼 부재만 영구 False."""
    monkeypatch.setitem(na._REFINE_COLS, "ok", None)
    monkeypatch.setitem(na._REFINE_COLS, "warned", False)

    class _Boom:
        def execute(self, sql, params=None):
            raise RuntimeError("connection reset by peer")

        def fetchall(self):
            return []

    assert na._refine_cols_ok(_Boom()) is False
    assert na._REFINE_COLS["ok"] is None      # 미캐시 — 재-probe 가능
    ok_cur = FakeCursor()
    assert na._refine_cols_ok(ok_cur) is True  # 복구 후 정상 판정
    # 컬럼 부재는 영구 캐시
    monkeypatch.setitem(na._REFINE_COLS, "ok", None)

    class _NoCol:
        def execute(self, sql, params=None):
            raise RuntimeError('column "anchor_key" does not exist')

        def fetchall(self):
            return []

    assert na._refine_cols_ok(_NoCol()) is False
    assert na._REFINE_COLS["ok"] is False


def test_suggested_links_ambiguous_alias_dropped(monkeypatch):
    """패널 MINOR fix: 동명 테이블(다른 DB/scope) alias 는 모호 — 비활성(오귀속 candidate 차단)."""
    from modules import relationships as _rel
    calls = []
    monkeypatch.setattr(_rel, "upsert_relationship", lambda conn, scope, **kw: calls.append(kw) or True)
    root = {"label": "Table", "key": "ds1:app.Achievement", "name": "Achievement", "fqn": "app.Achievement"}
    ctx = {
        "neighbors": [
            {"label": "Table", "key": "ds1:app.ItemMaster", "name": "ItemMaster", "fqn": "app.ItemMaster"},
            {"label": "Table", "key": "ds1:log.ItemMaster", "name": "ItemMaster", "fqn": "log.ItemMaster"},  # 동명 충돌
        ],
        "columns": [{"name": "ItemID"}],
    }
    obj = {"suggested_links": [
        {"from_table": "Achievement", "from_column": "ItemID", "to_table": "ItemMaster", "to_column": "ItemID"}]}
    assert na._ingest_suggested_links(TxConn(FakeCursor()), "ds1", root, ctx, obj) == 0 and not calls
    # 정확 fqn 표기는 계속 유효
    obj2 = {"suggested_links": [
        {"from_table": "Achievement", "from_column": "ItemID", "to_table": "log.ItemMaster", "to_column": "ItemID"}]}
    assert na._ingest_suggested_links(TxConn(FakeCursor()), "ds1", root, ctx, obj2) == 1


def test_infer_xschema_overfetch_and_pair_cap(monkeypatch):
    """패널 MAJOR fix(recall): xschema 포함 시 초과-fetch(knn_k×5 cap 60) — 같은-DB 시블링이 top-k 를
    점유해도 경계 후보가 발굴된다. 같은-DB skip 은 pair 캡을 소모하지 않는다."""
    base = [("common", "ds1", "gamedb", "Item", "ds1:gamedb.Item", "[0.1]")]
    # 같은 DB 시블링 12개(고유사) + 다른 DB 1개(뒤쪽 순위)
    knn = [("common", "ds1", "gamedb", f"Item_{i}", f"ds1:gamedb.Item_{i}", 0.99) for i in range(12)]
    knn.append(("common", "ds1", "logdb", "ItemLog", "ds1:logdb.ItemLog", 0.9))
    cols = {("common", "gamedb", "Item"): ["itemid"], ("common", "logdb", "ItemLog"): ["itemid"]}
    cur = XdsCursor(base, knn, cols)
    monkeypatch.setattr(R, "_ro_conn", lambda conn: (TxConn(cur), False))
    import modules.semantic_cluster as sc
    monkeypatch.setattr(sc, "_effective_schema", lambda dsk, okey, sch: sch)
    out = R.infer_cross_datasource_relationships(include_xds=False, include_xschema=True)
    assert len(out) == 1 and out[0]["tgt_schema"] == "logdb"   # 13위 이웃도 발굴(초과-fetch)
    knn_sql = [s for s in cur.executed if "t2.embedding <=>" in s][0]
    assert "NOT (o2.datasource_key" in knn_sql   # xschema 모드 = self 만 제외 + 초과-fetch


def test_infer_xds_only_keeps_sql_boundary(monkeypatch):
    """패널 MAJOR fix: xds 단독 모드는 종전 SQL 경계(`datasource_key <>`) 유지 — top-k 전 슬롯 cross-ds 보장."""
    knn = [("common2", "ds2", "otherdb", "Item", "ds2:otherdb.Item", 0.95)]
    cur = _xds_env(monkeypatch, knn)
    out = R.infer_cross_datasource_relationships(include_xds=True, include_xschema=False)
    assert len(out) == 1
    knn_sql = [s for s in cur.executed if "t2.embedding <=>" in s][0]
    assert "o2.datasource_key <> %s" in knn_sql and "NOT (o2.datasource_key" not in knn_sql
