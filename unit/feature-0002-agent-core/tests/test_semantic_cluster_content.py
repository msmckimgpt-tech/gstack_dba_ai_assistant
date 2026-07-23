"""feature-0016 content-cluster (TASK 20260713T1059) 단위 테스트 — DB/AGE/LLM 불요(monkeypatch·fake).

검증 축:
  RC1(fail-loud): numpy 부재 시 _cluster_edges 가 silent [] 대신 1회 WARNING.
  RC2(DB 단위 분할): run_semantic_cluster_pass 가 effective schema 별로 클러스터링 —
    스키마별 N 가드 국소화(초과 스키마만 skip·기존 배정 보존), pass-전역 cluster id 유일.
  RC3(루틴 편입): 루틴 시그니처 빌더 · 백필(변경감지 멱등·0040 미적용 soft-skip) ·
    테이블+루틴 합동 id 공간 · sync_routine 클러스터 투영(_UNSET 보존).
  RC4(분석문 시그니처): analysis 줄은 비어있지 않을 때만 append(미분석 해시 불변) ·
    node_analysis JSON(str/dict) 파싱.
  RC5(LLM 라벨): kv 캐시 적중 시 LLM 무호출 · 미스 시 배치 호출+캐시 적재 · fail-soft affix 폴백 ·
    라벨 위생(_valid_label) · 멤버셋 해시 순서 불변.
"""
import sys

import pytest

from modules import semantic_cluster as sc


# ── fakes ─────────────────────────────────────────────────────────────────────
class FakeCursor:
    """substring 패턴 → fetch 결과 매핑. raise_on 패턴은 execute 시 예외."""

    def __init__(self, rows=None, raise_on=None):
        self.rows = rows or {}
        self.raise_on = raise_on or {}
        self.executed = []
        self._last = None

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

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _updates(cur, table):
    return [(q, p) for (q, p) in cur.executed
            if q.startswith(f"UPDATE {table} SET semantic_cluster_id")]


# ── RC4: 시그니처 빌더 ────────────────────────────────────────────────────────
def test_table_signature_no_analysis_is_legacy_stable():
    # analysis 미보유 객체의 시그니처는 종전 포맷과 byte-동일 → 해시 불변(재임베딩 무발생).
    legacy = ("table: gamedb.t_user\n"
              "description: 유저\n"
              "role: account domain: game\n"
              "columns: id, name")
    got = sc.build_table_signature_text("gamedb", "t_user", "유저", ["id", "name"],
                                        "account", "game", analysis="")
    assert got == legacy


def test_table_signature_analysis_appended_and_capped():
    long = "가" * 1000
    got = sc.build_table_signature_text("g", "t", "", [], "", "", analysis=long)
    assert got.endswith("analysis: " + "가" * sc._ANALYSIS_SIG_MAX)
    assert "analysis:" not in sc.build_table_signature_text("g", "t", "", [], "", "", analysis="  ")


def test_routine_signature_shape_and_analysis():
    touches = [{"fqn": "cc_data_main.dt_MonsterSpawn", "kind": "read"},
               {"fqn": "cc_data_main.log_spawn", "kind": "write"}, {"fqn": ""}]
    got = sc.build_routine_signature_text("cc_data_main", "sp_GetMonsterSpawn", "procedure",
                                          "IN idx int", "int", touches, analysis="몬스터 스폰 조회")
    assert got.splitlines()[0] == "routine: cc_data_main.sp_GetMonsterSpawn()"
    assert "type: procedure" in got and "params: IN idx int" in got and "returns: int" in got
    assert "touches: read cc_data_main.dt_MonsterSpawn, write cc_data_main.log_spawn" in got
    assert got.endswith("analysis: 몬스터 스폰 조회")
    # analysis 부재 → 줄 자체가 없음(해시 안정)
    assert "analysis:" not in sc.build_routine_signature_text("g", "r", "function", "", "", [])


def test_fetch_analysis_text_parses_str_and_dict():
    js = '{"summary": "요약.", "usage": "활용.", "caveats": ""}'
    cur = FakeCursor(rows={"FROM node_analysis_jobs": [(js,)]})
    assert sc._fetch_analysis_text(cur, "common", "ds", "ds:a.t") == "요약. 활용."
    # §18.8 패널 n4(라이브 확증): jobs.scope_key 는 datasource — 양쪽 scope 를 ANY 로 조회해야 한다.
    q, params = cur.executed[-1]
    assert "scope_key = ANY(" in q and sorted(params[0]) == ["common", "ds"]
    cur2 = FakeCursor(rows={"FROM node_analysis_jobs": [({"summary": "S"},)]})
    assert sc._fetch_analysis_text(cur2, "common", "ds", "ds:a.t") == "S"
    assert sc._fetch_analysis_text(FakeCursor(), "common", "ds", "ds:a.t") == ""
    assert sc._fetch_analysis_text(FakeCursor(), "", "", "ds:a.t") == ""


# ── RC5: 라벨 위생·캐시·fail-soft ────────────────────────────────────────────
def test_member_set_hash_order_invariant():
    assert sc._member_set_hash(["b", "a"]) == sc._member_set_hash(["a", "b"])
    assert sc._member_set_hash(["a"]) != sc._member_set_hash(["a", "b"])


def test_valid_label_hygiene():
    assert sc._valid_label("  몬스터   스폰\n기록 ") == "몬스터 스폰 기록"
    assert sc._valid_label("가" * 100) == "가" * sc._LABEL_MAX_CHARS
    assert sc._valid_label("x") == ""
    assert sc._valid_label(None) == ""


def _label_clusters():
    return [{"idx": 0, "keys": ["k1", "k2"], "names": ["dt_MonsterSpawn", "sp_GetMonsterSpawn()"],
             "summaries": ["몬스터 스폰 설정"]}]


def test_llm_labels_cache_hit_skips_llm(monkeypatch):
    from modules import llm as llm_mod
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_LABEL_LLM", True, raising=False)
    monkeypatch.setattr(llm_mod, "llm_cluster_label",
                        lambda payload: pytest.fail("cache hit 인데 LLM 호출됨"))
    cur = FakeCursor(rows={"FROM agent_runtime.kv WHERE": ("몬스터 스폰",)})
    out = sc._llm_content_labels(cur, "ds1", "cc_data_main", _label_clusters())
    assert out == {0: "몬스터 스폰"}


def test_llm_labels_miss_calls_and_caches(monkeypatch):
    from modules import llm as llm_mod
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_LABEL_LLM", True, raising=False)
    calls = []
    monkeypatch.setattr(llm_mod, "llm_cluster_label",
                        lambda payload: calls.append(payload) or {"labels": [{"idx": 0, "label": "몬스터 스폰"}]})
    cur = FakeCursor()   # kv miss
    out = sc._llm_content_labels(cur, "ds1", "cc_data_main", _label_clusters())
    assert out == {0: "몬스터 스폰"} and len(calls) == 1
    assert calls[0]["clusters"][0]["members"] == ["dt_MonsterSpawn", "sp_GetMonsterSpawn()"]
    inserts = [q for (q, p) in cur.executed if "INSERT INTO agent_runtime.kv" in q]
    assert inserts, "라벨이 kv 캐시에 적재돼야 다음 pass 재호출이 없다"


def test_llm_labels_fail_soft(monkeypatch):
    from modules import llm as llm_mod
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_LABEL_LLM", True, raising=False)
    monkeypatch.setattr(llm_mod, "llm_cluster_label", lambda payload: None)
    out = sc._llm_content_labels(FakeCursor(), "ds1", "db", _label_clusters())
    assert out == {}   # caller 가 affix 폴백


def test_llm_labels_gate_off(monkeypatch):
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_LABEL_LLM", False, raising=False)
    out = sc._llm_content_labels(FakeCursor(), "ds1", "db", _label_clusters())
    assert out == {}


def _cfgattr():
    from shared import config as _c
    return _c


# ── RC1: numpy 부재 fail-loud ────────────────────────────────────────────────
def test_cluster_edges_numpy_missing_warns_once(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "numpy", None)   # import numpy → ImportError
    monkeypatch.setattr(sc, "_NUMPY_WARNED", {"done": False})
    import logging
    with caplog.at_level(logging.WARNING, logger="semantic_cluster"):
        assert sc._cluster_edges([[1.0, 0.0], [1.0, 0.0]]) == []
        assert sc._cluster_edges([[1.0, 0.0], [1.0, 0.0]]) == []
    warns = [r for r in caplog.records if "numpy 미설치" in r.getMessage()]
    assert len(warns) == 1


# ── RC2·RC3: DB 단위 분할 + 합동 클러스터 ────────────────────────────────────
def _pass_env(monkeypatch, rag_rows, routine_rows, routine_exc=None):
    raise_on = {}
    if routine_exc is not None:
        raise_on["FROM routine_objects r JOIN texts"] = routine_exc
    # analysis-freshness(2026-07-23): 두 SELECT 가 signature_text_hash 를 추가 반환(라벨 캐시 키
    # 신선도 합성) — 기존 fixture 튜플(rag 7·routine 6)은 sig 자리를 자동 패딩(테스트 표기 최소화).
    rag_rows = [tuple(r) + (f"sig{r[0]}",) if len(r) == 7 else tuple(r) for r in (rag_rows or [])]
    routine_rows = [tuple(r) + (f"sig{r[0]}",) if len(r) == 6 else tuple(r) for r in (routine_rows or [])]
    cur = FakeCursor(rows={
        "FROM rag_objects o JOIN texts": rag_rows,
        "FROM routine_objects r JOIN texts": routine_rows,
    }, raise_on=raise_on)
    monkeypatch.setattr(sc, "_rw_conn", lambda conn: (FakeConn(cur), False))
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_LABEL_LLM", False, raising=False)
    monkeypatch.setattr(sc, "_ROUTINE_COLS_WARNED", {"done": False})
    # analysis-freshness: 변경분 AGE targeted 투영 캡처(실 cypher 미실행) — cur.projected 로 검증.
    from modules import metadata_graph as _mg
    cur.projected = []
    monkeypatch.setattr(_mg, "project_cluster_props",
                        lambda changes, conn=None: cur.projected.extend(changes) or len(changes))
    return cur


def test_pass_per_schema_split_joint_ids(monkeypatch):
    pytest.importorskip("numpy")
    e_a, e_b = [1.0, 0.0], [0.0, 1.0]
    rag = [
        # (id, object_key, table_name, embedding, cur_cid, cur_lab, schema_name)
        (1, "ds1:aaa.dbo.t1", "t1", e_a, None, None, "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", [0.999, 0.01], None, None, "dbo"),
        (3, "ds1:bbb.t3", "t3", e_b, None, None, "bbb"),
        (4, "ds1:bbb.t4", "t4", [0.01, 0.999], None, None, "bbb"),
    ]
    routines = [
        # (id, schema_name, routine_name, embedding, cur_cid, cur_lab)
        (11, "aaa", "sp_r1", [0.998, 0.02], None, None),
    ]
    cur = _pass_env(monkeypatch, rag, routines)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None
    # h1 회귀 잠금: routine fetch 는 scope 필터 없이 ds 만 — routine_objects.scope_key 는
    # datasource_key(라이브 실측)라 'common' 필터는 루틴 전량 미합류를 만든다.
    rq = [q for (q, p) in cur.executed if "FROM routine_objects r JOIN texts" in q][0]
    assert "r.scope_key" not in rq and "r.datasource_key = %s" in rq
    assert rep["schemas"] == 2 and rep["clusters"] == 2 and rep["skipped_schemas"] == 0
    ups_t = {p[2]: (p[0], p[1]) for (q, p) in _updates(cur, "rag_objects")}
    ups_r = {p[2]: (p[0], p[1]) for (q, p) in _updates(cur, "routine_objects")}
    # aaa: 테이블 t1·t2 + 루틴 sp_r1 이 **같은 cid**(합동 id 공간). id 는 스키마-로컬 순번(m5) —
    # 프론트 그룹 키가 스키마 네임스페이스라 스키마 간 동일 값(0)이어도 무해.
    assert ups_t[1][0] == ups_t[2][0] == ups_r[11][0] == 0
    assert ups_t[3][0] == ups_t[4][0] == 0


def test_pass_schema_n_guard_localized(monkeypatch):
    pytest.importorskip("numpy")
    # aaa=3 items > maxn=2 → 그 스키마만 skip(기존 배정 보존·UPDATE 0), bbb=2 는 정상 클러스터.
    rag = [
        (1, "ds1:aaa.dbo.t1", "t1", [1.0, 0.0], 7, "old", "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", [1.0, 0.0], 7, "old", "dbo"),
        (3, "ds1:aaa.dbo.t3", "t3", [1.0, 0.0], None, None, "dbo"),
        (4, "ds1:bbb.t4", "t4", [0.0, 1.0], None, None, "bbb"),
        (5, "ds1:bbb.t5", "t5", [0.0, 1.0], None, None, "bbb"),
    ]
    cur = _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_FULLMATRIX_MAX_N", 2, raising=False)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["skipped_schemas"] == 1 and rep["clusters"] == 1
    ups = {p[2] for (q, p) in _updates(cur, "rag_objects")}
    assert ups == {4, 5}, "skip 스키마(aaa) 행은 기존 배정 보존 — UPDATE 대상 아님"


def test_pass_routine_cols_missing_soft(monkeypatch):
    pytest.importorskip("numpy")
    rag = [
        (1, "ds1:aaa.dbo.t1", "t1", [1.0, 0.0], None, None, "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", [1.0, 0.0], None, None, "dbo"),
    ]
    cur = _pass_env(monkeypatch, rag, [], routine_exc=RuntimeError("column does not exist"))
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["clusters"] == 1   # 테이블만으로 계속(0040 미적용 창)
    assert _updates(cur, "routine_objects") == []


# ── RC3: 루틴 시그니처 백필 ──────────────────────────────────────────────────
def _backfill_env(monkeypatch, routine_rows, routine_exc=None):
    raise_on = {}
    if routine_exc is not None:
        raise_on["FROM routine_objects WHERE routine_name"] = routine_exc
    cur = FakeCursor(rows={
        "FROM rag_objects WHERE object_type": [],
        "COUNT(*) FROM rag_objects": (0,),
        "FROM routine_objects WHERE routine_name <> '' ORDER BY": routine_rows,
        "COUNT(*) FROM routine_objects": (0,),
    }, raise_on=raise_on)
    monkeypatch.setattr(sc, "_rw_conn", lambda conn: (FakeConn(cur), False))
    stored = []
    monkeypatch.setattr(sc, "_text_store_insert", lambda _cur, text: stored.append(text) or "h")
    monkeypatch.setattr(sc, "_ROUTINE_COLS_WARNED", {"done": False})
    return cur, stored


def test_routine_backfill_upserts_and_idempotent(monkeypatch):
    refs = '[{"fqn": "aaa.t1", "kind": "read"}]'
    rows = [
        # (id, scope, ds, schema, name, rtype, params, returns, refs, cur_hash)
        (11, "common", "ds1", "aaa", "sp_r1", "procedure", "IN a int", "", refs, None),
    ]
    cur, stored = _backfill_env(monkeypatch, rows)
    rep = sc.run_signature_backfill_pass(max_rows=10)
    assert rep["routine_processed"] == 1 and rep["routine_changed"] == 1 and rep["routine_failed"] == 0
    assert len(stored) == 1 and "touches: read aaa.t1" in stored[0]
    ups = [q for (q, p) in cur.executed if q.startswith("UPDATE routine_objects SET signature_text_hash")]
    assert len(ups) == 1
    # 멱등: 저장된 해시와 동일하면 no-op
    sig = stored[0]
    from modules.utils import _text_hash
    rows2 = [rows[0][:9] + (_text_hash(sig.strip()),)]
    cur2, stored2 = _backfill_env(monkeypatch, rows2)
    rep2 = sc.run_signature_backfill_pass(max_rows=10)
    assert rep2["routine_changed"] == 0 and stored2 == []


def test_routine_backfill_missing_cols_soft(monkeypatch):
    cur, stored = _backfill_env(monkeypatch, [], routine_exc=RuntimeError("column does not exist"))
    rep = sc.run_signature_backfill_pass(max_rows=10)
    assert rep["routine_processed"] == 0 and rep["error"] is None and stored == []


# ── RC3: sync_routine 클러스터 투영(_UNSET 보존) ─────────────────────────────
def test_sync_routine_cluster_projection(monkeypatch):
    from modules import metadata_graph as mg
    merged = []
    monkeypatch.setattr(mg, "_merge_vertex", lambda cur, label, key, props: merged.append((label, key, props)))
    monkeypatch.setattr(mg, "_merge_edge", lambda *a, **k: None)
    monkeypatch.setattr(mg, "_cypher", lambda *a, **k: [])
    mg.sync_routine(None, "ds1", "aaa", "sp_r1", "procedure", "", [],
                    cluster_id=3, cluster_label="몬스터 스폰")
    rp = [p for (l, k, p) in merged if l == "Routine"][0]
    assert rp["semantic_cluster_id"] == 3 and rp["semantic_cluster_label"] == "몬스터 스폰"
    merged.clear()
    mg.sync_routine(None, "ds1", "aaa", "sp_r1", "procedure", "", [],
                    cluster_id=None, cluster_label=None)
    rp = [p for (l, k, p) in merged if l == "Routine"][0]
    assert rp["semantic_cluster_id"] is None and "semantic_cluster_label" in rp   # None → = null clear
    merged.clear()
    mg.sync_routine(None, "ds1", "aaa", "sp_r1")   # _UNSET → 속성 미전달(보존)
    rp = [p for (l, k, p) in merged if l == "Routine"][0]
    assert "semantic_cluster_id" not in rp and "semantic_cluster_label" not in rp


def test_pass_giant_blob_adaptive_split(monkeypatch):
    """라이브 프로브 적발 회귀 잠금: base τ 에서 스키마 전체가 한 blob 이면 τ-상승 재분할로 쪼갠다."""
    pytest.importorskip("numpy")
    import math
    def v(deg):
        return [math.cos(math.radians(deg)), math.sin(math.radians(deg))]
    # 그룹 A(0°±1°) 와 그룹 B(32°±1°): 교차 코사인 ~0.84~0.86 ≥ base τ(0.82) → base 에서 단일 blob,
    # τ 상승(0.86+)에서 교차 엣지 소멸 → 3+3 분리. 그룹 내부 ~0.9999 는 ceiling 까지 유지.
    rag = [
        (1, "ds1:aaa.dbo.t1", "t1", v(0.0), None, None, "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", v(0.5), None, None, "dbo"),
        (3, "ds1:aaa.dbo.t3", "t3", v(1.0), None, None, "dbo"),
        (4, "ds1:aaa.dbo.t4", "t4", v(32.0), None, None, "dbo"),
        (5, "ds1:aaa.dbo.t5", "t5", v(32.5), None, None, "dbo"),
        (6, "ds1:aaa.dbo.t6", "t6", v(33.0), None, None, "dbo"),
    ]
    cur = _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MAX_SIZE", 3, raising=False)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["clusters"] == 2
    ups = {p[2]: p[0] for (q, p) in _updates(cur, "rag_objects")}
    assert ups[1] == ups[2] == ups[3] and ups[4] == ups[5] == ups[6] and ups[1] != ups[4]


def test_cluster_edges_mutual_knn_blocks_hub_chain():
    """mutual-kNN: 허브 j 가 i 를 top-k 에 안 담으면 i→j 단방향은 엣지가 아니다(연쇄 차단)."""
    pytest.importorskip("numpy")
    import math
    # 허브 h(0°) 주변에 8개 근접(±2°) + 원거리 x(35°): x 의 top-k 엔 h 가 있지만
    # h 의 top-k(max_deg=2 로 축소)는 근접 이웃만 — x-h 엣지 없음.
    embs = [[math.cos(math.radians(d)), math.sin(math.radians(d))] for d in (0, 1, -1, 35)]
    old = _cfgattr().AGENT_METADATA_CLUSTER_MAX_DEGREE
    try:
        _cfgattr().AGENT_METADATA_CLUSTER_MAX_DEGREE = 2
        edges = set(sc._cluster_edges(embs, tau=0.80))
    finally:
        _cfgattr().AGENT_METADATA_CLUSTER_MAX_DEGREE = old
    assert (0, 3) not in edges and (3, 0) not in edges   # 단방향(비상호) 차단
    assert (0, 1) in edges and (0, 2) in edges           # 상호 근접은 유지


# ── §18.8 패널 M1: 분석-신선 표적 백필(도달성) ────────────────────────────────
def test_backfill_analysis_fresh_targeted_pick_and_touch(monkeypatch):
    """백로그 0 이어도 최신 done 분석이 행보다 새 행은 표적 합류하고, 시그니처 불변이면 touch 로
    조건을 해소한다(top-N 창 밖 영구 미갱신 — 패널 M1 회귀 잠금)."""
    from modules.utils import _text_hash
    # 시그니처 불변 케이스: 현재 해시가 (분석 "" 기준) 계산 해시와 동일하도록 구성.
    sig_same = sc.build_table_signature_text("aaa", "t1", "", [], "", "", analysis="")
    row_same = (21, "common", "ds1", "dbo", "t1", "ds1:aaa.dbo.t1", _text_hash(sig_same.strip()), "", "")
    row_stale = (22, "common", "ds1", "dbo", "t2", "ds1:aaa.dbo.t2", "OLDHASH", "", "")
    cur = FakeCursor(rows={
        "FROM rag_objects WHERE object_type": [],                       # 주 백로그 0
        "split_part(replace(o.object_key": [row_same, row_stale],      # M1 표적 선별
        "COUNT(*) FROM rag_objects": (0,),
        "FROM routine_objects WHERE routine_name <> '' ORDER BY": [],
        "COUNT(*) FROM routine_objects": (0,),
    })
    monkeypatch.setattr(sc, "_rw_conn", lambda conn: (FakeConn(cur), False))
    stored = []
    monkeypatch.setattr(sc, "_text_store_insert", lambda _cur, text: stored.append(text) or "h")
    rep = sc.run_signature_backfill_pass(max_rows=10)
    assert rep["analysis_fresh"] == 2 and rep["processed"] == 2 and rep["changed"] == 1
    touches = [(q, p) for (q, p) in cur.executed
               if q.startswith("UPDATE rag_objects SET updated_at = now()")]
    assert len(touches) == 1 and touches[0][1] == (21,)   # 불변 행은 touch 만(재선별 차단)
    hash_ups = [(q, p) for (q, p) in cur.executed
                if q.startswith("UPDATE rag_objects SET signature_text_hash")]
    assert len(hash_ups) == 1 and "updated_at = now()" in hash_ups[0][0] and hash_ups[0][1][1] == 22


# ── p2: centroid seriation + soft-attach ─────────────────────────────────────
def test_seriate_by_centroid_neighbor_chain():
    pytest.importorskip("numpy")
    # A=[1,0], B=[0.95,0.31](A와 근접), C=[0,1](원거리). 크기 최대 C 시작 → 최근접 B? cos(C,B)=0.31 > cos(C,A)=0 → C,B,A.
    cents = sc._cluster_centroids([[1.0, 0.0], [0.95, 0.31], [0.0, 1.0]], [[0], [1], [2]])
    order = sc._seriate_by_centroid(cents, [2, 2, 3], ["a", "b", "c"])
    assert order == [2, 1, 0]
    # 2개 이하 → 항등
    assert sc._seriate_by_centroid(cents[:2], [1, 1], ["a", "b"]) == [0, 1]


def test_pass_soft_attach_leftovers(monkeypatch):
    """p2 RC-A: 코어 미배정 잔여가 centroid 코사인 ≥ ATTACH_SIM 이면 최근접 클러스터에 편입(라벨 상속),
    미달은 NULL — 'dt_c' 류 가짜 affix 가족으로 흐르던 잔여를 컨텐츠 기반으로 흡수."""
    pytest.importorskip("numpy")
    rag = [
        (1, "ds1:aaa.dbo.t1", "t1", [1.0, 0.0], None, None, "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", [0.999, 0.01], None, None, "dbo"),
        # near: cos 0.80 — base τ(0.82) 미만이라 코어 비편입(mutual-kNN 엣지 없음), attach(0.78) 이상 → 편입.
        (3, "ds1:aaa.dbo.near", "near", [0.8, 0.6], None, None, "dbo"),
        (4, "ds1:aaa.dbo.far", "far", [0.0, 1.0], None, None, "dbo"),       # cos 0 → NULL 유지
    ]
    cur = _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_ATTACH_SIM", 0.78, raising=False)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["clusters"] == 1 and rep["attached"] == 1
    ups = {p[2]: (p[0], p[1]) for (q, p) in _updates(cur, "rag_objects")}
    assert ups[3][0] == ups[1][0] and ups[3][1] == ups[1][1]   # 편입 + 라벨 상속
    assert 4 not in ups   # far 는 NULL 유지(신규 배정 없음 → UPDATE 없음)


def test_pass_attach_cap_guard(monkeypatch):
    """§18.8 p2 패널 MAJOR-1 회귀 잠금: attach 는 클러스터별 코어+attached < cap 동안만 —
    유사도 내림차순 배정, cap 도달 후보는 NULL 유지(거대 밴드 재생성 차단)."""
    pytest.importorskip("numpy")
    # 4D: 코어 [1,0,0,0]×2. 잔여 3개는 코어와 cos 0.81/0.80/0.79(τ 0.82 미만·attach 0.78 이상),
    # 서로는 cos≈0.63(상호 코어 미형성 — 2D 로는 불가능한 구성이라 4D 사용).
    rag = [
        (1, "ds1:aaa.dbo.t1", "t1", [1.0, 0.0, 0.0, 0.0], None, None, "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", [0.999, 0.01, 0.0, 0.0], None, None, "dbo"),
        (3, "ds1:aaa.dbo.l1", "l1", [0.81, 0.5864, 0.0, 0.0], None, None, "dbo"),
        (4, "ds1:aaa.dbo.l2", "l2", [0.80, 0.0, 0.6, 0.0], None, None, "dbo"),
        (5, "ds1:aaa.dbo.l3", "l3", [0.79, 0.0, 0.0, 0.6131], None, None, "dbo"),
    ]
    cur = _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_ATTACH_SIM", 0.78, raising=False)
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MAX_SIZE", 3, raising=False)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["clusters"] == 1
    assert rep["attached"] == 1, "room=cap(3)-core(2)=1 — 최고 유사도 l1 만 편입"
    ups = {p[2] for (q, p) in _updates(cur, "rag_objects")}
    assert 3 in ups and 4 not in ups and 5 not in ups


# ── cluster-label-target(2026-07-14): llm_usage.target 사용자 식별자 기록 ─────
def test_ds_display_label_resolves_and_falls_back():
    cur = FakeCursor(rows={"FROM agent_runtime.datasource_health": ("mssql-qa-idc",)})
    assert sc._ds_display_label(cur, "mssql-06656002eda6") == "mssql-qa-idc"
    assert sc._ds_display_label(FakeCursor(), "mssql-06656002eda6") == "mssql-06656002eda6"   # 스냅샷 부재 → key


def test_llm_labels_payload_uses_display_label(monkeypatch):
    """'AI 운영 현황' target 해시 노출(사용자 리포트) 회귀 잠금 — payload.datasource = 사용자 식별자,
    kv 캐시 키는 여전히 해시 ns(캐시 무효화 없음)."""
    from modules import llm as llm_mod
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_LABEL_LLM", True, raising=False)
    calls = []
    monkeypatch.setattr(llm_mod, "llm_cluster_label",
                        lambda payload: calls.append(payload) or {"labels": [{"idx": 0, "label": "몬스터 스폰"}]})
    cur = FakeCursor(rows={"FROM agent_runtime.datasource_health": ("mssql-qa-idc",)})
    out = sc._llm_content_labels(cur, "mssql-06656002eda6", "cc_data_main", _label_clusters())
    assert out == {0: "몬스터 스폰"} and calls[0]["datasource"] == "mssql-qa-idc"
    ns = sc._label_ns_hash("mssql-06656002eda6", "cc_data_main")
    inserts = [p for (q, p) in cur.executed if "INSERT INTO agent_runtime.kv" in q]
    assert inserts and inserts[0][1].startswith(f"label:{ns}:")   # 캐시 키는 해시 ns 불변


# ── analysis-freshness(2026-07-23, 사용자 리포트 log_v2): 분석 완료 → 클러스터 신선도 ──
def test_llm_labels_cache_key_uses_signature_hash(monkeypatch):
    """라벨 캐시 키에 멤버 시그니처 해시 합성 — 멤버셋 불변 + 분석문(시그니처) 갱신이면 캐시 미스
    → 재라벨. cache_keys 미전달 caller 는 종전 멤버셋 키(하위호환)."""
    from modules import llm as llm_mod
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_LABEL_LLM", True, raising=False)
    monkeypatch.setattr(llm_mod, "llm_cluster_label",
                        lambda payload: {"labels": [{"idx": 0, "label": "새 라벨"}]})
    ns = sc._label_ns_hash("ds1", "db")
    base = {"idx": 0, "keys": ["k1", "k2"], "names": ["t1", "t2"], "summaries": []}
    cur1 = FakeCursor()
    sc._llm_content_labels(cur1, "ds1", "db", [dict(base, cache_keys=["k1#aaaa", "k2#bbbb"])])
    key1 = [p[1] for (q, p) in cur1.executed if "SELECT value FROM agent_runtime.kv" in q][0]
    cur2 = FakeCursor()
    sc._llm_content_labels(cur2, "ds1", "db", [dict(base, cache_keys=["k1#aaaa", "k2#cccc"])])
    key2 = [p[1] for (q, p) in cur2.executed if "SELECT value FROM agent_runtime.kv" in q][0]
    assert key1 != key2 and key1.startswith(f"label:{ns}:") and key2.startswith(f"label:{ns}:")
    # 하위호환: cache_keys 부재 → 멤버셋 키(순서 불변)
    cur3 = FakeCursor()
    sc._llm_content_labels(cur3, "ds1", "db", [dict(base)])
    key3 = [p[1] for (q, p) in cur3.executed if "SELECT value FROM agent_runtime.kv" in q][0]
    assert key3 == f"label:{ns}:{sc._member_set_hash(base['keys'])}"


def test_pass_projects_changed_cluster_props(monkeypatch):
    """변경분 AGE targeted 투영 — Table 은 <ds>:<eff_schema>.<table>(MSSQL dbo 제거 동형),
    Routine 은 items.key 그대로. 무변경 행은 투영 대상 아님."""
    pytest.importorskip("numpy")
    rag = [
        (1, "ds1:aaa.dbo.t1", "t1", [1.0, 0.0], None, None, "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", [0.999, 0.01], None, None, "dbo"),
    ]
    routines = [(11, "aaa", "sp_r1", [0.998, 0.02], None, None)]
    cur = _pass_env(monkeypatch, rag, routines)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["updated"] == 3
    got = {(c["label"], c["key"]) for c in cur.projected}
    assert got == {("Table", "ds1:aaa.t1"), ("Table", "ds1:aaa.t2"), ("Routine", "ds1:aaa.sp_r1()")}
    assert all(c["cid"] == 0 and c["lab"] for c in cur.projected)


def test_fresh_embeddings_since_mark_due_and_guards():
    """mark 이후 새 임베딩 → due. 진행 중 run(lease 이내) → 유예. 신선 임베딩 없음/예외 → False."""
    fresh = FakeCursor(rows={"FROM agent_runtime.kv v": (1,)})   # 신선 임베딩 존재( run 없음 → fetchone None)
    # 첫 execute(kv+EXISTS) → (1,), 둘째 execute(node_analysis_runs) → rows 미매칭 → None
    assert sc._fresh_embeddings_since_mark(fresh, "common", "ds1", "cluster_at:common:ds1") is True
    stale = FakeCursor()   # kv 미매칭 → fetchone None
    assert sc._fresh_embeddings_since_mark(stale, "common", "ds1", "k") is False
    running = FakeCursor(rows={"FROM agent_runtime.kv v": (1,),
                               "FROM node_analysis_runs WHERE scope_key = ANY": (1,)})
    assert sc._fresh_embeddings_since_mark(running, "common", "ds1", "k") is False
    # §18.8 M3: 임베딩 드레인(미임베딩 시그니처 잔존) 중 유예 — 부분-멤버셋 재클러스터 churn 차단.
    draining = FakeCursor(rows={"FROM agent_runtime.kv v": (1,), "t.embedding IS NULL": (1,)})
    assert sc._fresh_embeddings_since_mark(draining, "common", "ds1", "k") is False
    boom = FakeCursor(raise_on={"FROM agent_runtime.kv v": RuntimeError("pg down")})
    assert sc._fresh_embeddings_since_mark(boom, "common", "ds1", "k") is False


def test_maintenance_freshness_triggers_recluster(monkeypatch):
    """cadence 미도래여도 신선 임베딩이면 재클러스터 — run_cluster_maintenance due 판정 통합."""
    calls = []
    monkeypatch.setattr(sc, "run_signature_backfill_pass", lambda max_rows=None, conn=None: {"changed": 0})
    monkeypatch.setattr(sc, "list_cluster_scopes", lambda conn=None: [("common", "ds1")])
    monkeypatch.setattr(sc, "_cadence_due", lambda cur, key, sec: False)          # 시간 cadence 미도래
    monkeypatch.setattr(sc, "_fresh_embeddings_since_mark", lambda cur, s, d, k: True)
    monkeypatch.setattr(sc, "run_semantic_cluster_pass",
                        lambda scope, dsk, conn=None: calls.append((scope, dsk)) or {"updated": 1, "clusters": 1})
    cur = FakeCursor()
    monkeypatch.setattr(sc, "_rw_conn", lambda conn: (FakeConn(cur), False))
    rep = sc.run_cluster_maintenance()
    assert calls == [("common", "ds1")] and rep["updated"] == 1
