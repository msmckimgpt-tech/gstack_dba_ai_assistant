"""feature-0016 content-cluster-cohesion (2026-07-30) 단위 테스트 — DB/AGE/LLM 불요(monkeypatch·fake).

사용자 리포트: "컨텐츠 클러스터가 너무 세분화 · 세분화에 따른 노드 위치 후처리가 빈약 · 배치가 실제
관계보다 라벨 이름 순 나열 · 상세 패널이 갱신되지 않아 부정합".

본 파일이 잠그는 축(백엔드):
  C1 응집 병합: τ-상승 재분할(divisive)이 남긴 인접 조각을 centroid 코사인 ≥ MERGE_SIM 으로 되돌린다.
     — 단방향 압력만 있던 종전 구조가 "한 컨텐츠 → 여러 밴드" 를 고착시킨 것의 근본 해소.
  C2 라벨충돌 병합: 같은 LLM 라벨 형제는 분할이 의미 없다는 증거 → 병합. cap 초과 시 라벨 구별 표기.
  C3 배치 순서: centroid **MDS 2-D serpentine**(행-균형 boustrophedon) — 1-D 체인 대체. 결정론.
  C4 MIN_SIZE 기본값 3 (2멤버 밴드 = 헤더가 내용보다 큰 노이즈).
  C5 pass 통합: 병합이 실제로 cluster id 를 합치고 rep 카운터로 관측된다.

프론트(패널↔캔버스 SSOT · be: 밴드 관계 seriation)는 브라우저 자산이라 PB-0008 라이브 검증 +
`unit/feature-0003-agent-web-ui/tests/test_graph_content_cluster_cohesion.py`(정적 계약 검사)가 담당한다.
"""
import pytest

from modules import semantic_cluster as sc

from test_semantic_cluster_content import _cfgattr, _pass_env, _updates


def _unit(v):
    import math
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


# ── C1: centroid 응집 병합 ────────────────────────────────────────────────────
def test_merge_components_by_centroid_rejoins_oversplit():
    """τ-상승 재분할이 쪼갠 인접 조각(centroid cos ≥ MERGE_SIM)을 다시 합친다."""
    pytest.importorskip("numpy")
    embs = [_unit([1, 0, 0]), _unit([0.99, 0.14, 0]), _unit([0.98, 0.2, 0]),
            _unit([1, 0.02, 0]), _unit([0.995, 0.1, 0]),
            _unit([0, 1, 0]), _unit([0.1, 0.99, 0]), _unit([0.05, 0.998, 0])]
    comps = [[0, 1, 2], [3, 4], [5, 6, 7]]          # 앞 둘은 같은 컨텐츠의 조각
    keyof = (lambda m: min("t%02d" % i for i in m))
    merged, n = sc._merge_components_by_centroid(embs, comps, 0.90, 80, key_of=keyof)
    assert n == 1
    assert sorted(sorted(m) for m in merged) == [[0, 1, 2, 3, 4], [5, 6, 7]]


def test_merge_components_respects_cap_and_threshold():
    """cap 초과 병합 금지(재분할↔병합 flap 차단) · 임계 미만은 무병합."""
    pytest.importorskip("numpy")
    embs = [_unit([1, 0]), _unit([0.999, 0.02]), _unit([1, 0.01]), _unit([0.998, 0.03])]
    comps = [[0, 1], [2, 3]]
    keyof = (lambda m: min("t%02d" % i for i in m))
    # cap=3 → 2+2=4 > 3 이라 병합 금지(임계는 충족).
    kept, n = sc._merge_components_by_centroid(embs, comps, 0.90, 3, key_of=keyof)
    assert n == 0 and [sorted(m) for m in kept] == [[0, 1], [2, 3]]
    # 임계 1.01(> 1) → 어떤 쌍도 충족 불가.
    kept2, n2 = sc._merge_components_by_centroid(embs, comps, 1.01, 80, key_of=keyof)
    assert n2 == 0 and [sorted(m) for m in kept2] == [[0, 1], [2, 3]]


def test_merge_components_deterministic_and_singleton_safe():
    pytest.importorskip("numpy")
    embs = [_unit([1, 0]), _unit([0.99, 0.1]), _unit([0, 1])]
    comps = [[0], [1], [2]]
    keyof = (lambda m: min("t%02d" % i for i in m))
    a = sc._merge_components_by_centroid(embs, comps, 0.90, 80, key_of=keyof)
    b = sc._merge_components_by_centroid(embs, comps, 0.90, 80, key_of=keyof)
    assert [sorted(m) for m in a[0]] == [sorted(m) for m in b[0]] and a[1] == b[1]
    # 컴포넌트 1개 → no-op
    assert sc._merge_components_by_centroid(embs, [[0, 1, 2]], 0.5, 80, key_of=keyof) == ([[0, 1, 2]], 0)


def test_merge_components_numpy_missing_is_noop(monkeypatch):
    import sys as _sys
    monkeypatch.setitem(_sys.modules, "numpy", None)
    comps = [[0, 1], [2, 3]]
    out, n = sc._merge_components_by_centroid([[1.0], [1.0], [1.0], [1.0]], comps, 0.5, 80)
    assert n == 0 and out == comps


# ── C2: 라벨충돌 병합 + 구별 표기 ─────────────────────────────────────────────
def test_merge_clusters_by_label_joins_same_label_siblings():
    """라이브 증상 회귀 잠금: '길드 게시판' ×2 처럼 같은 라벨 형제는 병합한다."""
    valid = [("k0", [0, 1]), ("k2", [2, 3]), ("k4", [4, 5])]
    labels = ["길드 게시판", "길드 게시판", "몬스터 스폰"]
    out, out_lab, n = sc._merge_clusters_by_label(valid, labels, 80, lambda m: "k%s" % min(m))
    assert n == 1
    assert [sorted(m) for (_k, m) in out] == [[0, 1, 2, 3], [4, 5]]
    assert out_lab == ["길드 게시판", "몬스터 스폰"]


def test_merge_clusters_by_label_cap_blocked_then_disambiguated():
    """cap 초과로 병합이 막히면 분리 유지 + 라벨에 구별 근거(이름 스템)를 노출한다."""
    valid = [("k0", [0, 1]), ("k2", [2, 3])]
    labels = ["길드 게시판", "길드 게시판"]
    out, out_lab, n = sc._merge_clusters_by_label(valid, labels, 3, lambda m: "k%s" % min(m))
    assert n == 0 and out_lab == labels
    dis = sc._disambiguate_labels(out_lab, [["dt_guildboard", "dt_guildboardlog"],
                                            ["ut_guildpost", "ut_guildpostlog"]])
    assert dis[0] != dis[1] and dis[0].startswith("길드 게시판 · ") and dis[1].startswith("길드 게시판 · ")


def test_disambiguate_labels_leaves_unique_labels_untouched():
    labels = ["몬스터 스폰", "길드 게시판"]
    assert sc._disambiguate_labels(labels, [["m1", "m2"], ["g1", "g2"]]) == labels


def test_disambiguate_labels_falls_back_to_ordinal_without_affix():
    """공통 스템이 없으면 순번으로라도 구별한다(같은 라벨 밴드 2개가 그대로 보이는 것 방지)."""
    labels = ["기타", "기타"]
    out = sc._disambiguate_labels(labels, [["a"], ["b"]])
    assert out[0] != out[1]


# ── C3: MDS 2-D serpentine 배치 순서 ─────────────────────────────────────────
def test_mds_2d_shape_and_small_input():
    pytest.importorskip("numpy")
    cents = sc._cluster_centroids([_unit([1, 0, 0]), _unit([0, 1, 0]), _unit([0, 0, 1]),
                                   _unit([1, 1, 0])], [[0], [1], [2], [3]])
    coords = sc._mds_2d(cents)
    assert len(coords) == 4 and all(len(p) == 2 for p in coords)
    assert sc._mds_2d(cents[:2]) == []          # n<3 → 미적격


def test_mds_2d_is_deterministic_sign_normalized():
    pytest.importorskip("numpy")
    cents = sc._cluster_centroids([_unit([1, 0, 0]), _unit([0.9, 0.4, 0]), _unit([0, 1, 0]),
                                   _unit([0, 0, 1])], [[0], [1], [2], [3]])
    assert sc._mds_2d(cents) == sc._mds_2d(cents)


def test_grid_serpentine_order_boustrophedon_on_grid():
    """3×3 격자 → 행 단위 좌→우, 홀수 행 역방향(행 끝과 다음 행 시작이 인접)."""
    pts = [(x, y) for y in range(3) for x in range(3)]
    order = sc._grid_serpentine_order(pts, [1] * 9, ["k%d" % i for i in range(9)])
    assert order == [0, 1, 2, 5, 4, 3, 6, 7, 8]


def test_grid_serpentine_order_balances_rows_by_member_count():
    """행 경계는 **멤버 수 누적** 기준 — 밴드 폭 ∝ 멤버 수라 프론트 shelf-pack 행 랩과 정합."""
    pts = [(0, 0), (1, 0), (0, 1), (1, 1)]
    order = sc._grid_serpentine_order(pts, [10, 1, 1, 1], ["a", "b", "c", "d"])
    assert sorted(order) == [0, 1, 2, 3]
    assert order[0] == 0, "큰 밴드가 첫 행을 열고 그 행은 조기 종료된다"


def test_grid_serpentine_order_identity_on_small_or_missing_coords():
    assert sc._grid_serpentine_order([(0, 0), (1, 1)], [1, 1], ["a", "b"]) == [0, 1]
    assert sc._grid_serpentine_order([], [1, 1, 1], ["a", "b", "c"]) == [0, 1, 2]


def test_cluster_order_falls_back_to_chain_when_grid_off():
    """게이트 OFF → 기존 1-D greedy 체인(_seriate_by_centroid)과 동일 산출(회귀 경로 보존)."""
    pytest.importorskip("numpy")
    cents = sc._cluster_centroids([[1.0, 0.0], [0.95, 0.31], [0.0, 1.0]], [[0], [1], [2]])
    sizes, keys = [2, 2, 3], ["a", "b", "c"]
    assert sc._cluster_order(cents, sizes, keys, grid=False) == sc._seriate_by_centroid(cents, sizes, keys)


def test_cluster_order_grid_uses_mds_when_available():
    pytest.importorskip("numpy")
    cents = sc._cluster_centroids([_unit([1, 0, 0]), _unit([0.9, 0.4, 0]), _unit([0, 1, 0]),
                                   _unit([0, 0, 1])], [[0], [1], [2], [3]])
    sizes, keys = [1, 1, 1, 1], ["a", "b", "c", "d"]
    grid = sc._cluster_order(cents, sizes, keys, grid=True)
    assert sorted(grid) == [0, 1, 2, 3]
    coords = sc._mds_2d(cents)
    assert grid == sc._grid_serpentine_order(coords, sizes, keys)


# ── C4: 기본값 ────────────────────────────────────────────────────────────────
def test_min_size_default_is_three():
    """2멤버 밴드는 헤더가 내용보다 큰 노이즈 — 기본 하한을 3 으로 올린 결정을 잠근다."""
    import os
    if os.getenv("AGENT_METADATA_CLUSTER_MIN_SIZE"):
        pytest.skip("환경변수 override 존재 — 기본값 검증 대상 아님")
    from shared import config as _c
    assert _c.AGENT_METADATA_CLUSTER_MIN_SIZE == 3


def test_merge_defaults_present_and_ordered():
    """MERGE_MAX_SIZE > MAX_SIZE 여야 재분할↔병합 왕복(flap)이 생기지 않는다."""
    from shared import config as _c
    assert 0.0 < _c.AGENT_METADATA_CLUSTER_MERGE_SIM <= 1.0
    assert _c.AGENT_METADATA_CLUSTER_MERGE_MAX_SIZE > _c.AGENT_METADATA_CLUSTER_MAX_SIZE
    assert _c.AGENT_METADATA_CLUSTER_GRID_ORDER is True


# ── C5: pass 통합 ────────────────────────────────────────────────────────────
def test_pass_merges_oversplit_into_single_cluster(monkeypatch):
    """MAX_SIZE 로 강제 재분할된 동질 그룹이 응집 병합으로 **하나의 밴드**로 되돌아온다.

    구성: 6개 테이블이 서로 cos ≥ 0.999(동질). MAX_SIZE=3 → 재분할이 3+3 으로 쪼갠다.
    병합(MERGE_SIM 0.90, MERGE_MAX_SIZE 80)이 다시 합쳐 clusters == 1 · merged_centroid == 1.
    """
    pytest.importorskip("numpy")
    import math

    def v(deg):
        return [math.cos(math.radians(deg)), math.sin(math.radians(deg))]

    # 두 하위군 A(0.0/0.5/1.0°) · B(20.0/20.5/21.0°). 교차 cos ≥ base τ(0.82) 라 base 에서 단일
    # blob → cap=3 초과 → τ-상승 재분할이 0.96 에서 3+3 으로 쪼갠다. 두 조각의 centroid cos ≈
    # cos(20°) ≈ 0.94 ≥ MERGE_SIM(0.90) 이므로 응집 병합이 되돌린다(과세분화 해소의 정확한 경로).
    rag = [(i + 1, "ds1:aaa.dbo.t%d" % (i + 1), "t%d" % (i + 1), v(d), None, None, "dbo")
           for i, d in enumerate([0.0, 0.5, 1.0, 20.0, 20.5, 21.0])]
    cur = _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MAX_SIZE", 3, raising=False)
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MERGE_SIM", 0.90, raising=False)
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MERGE_MAX_SIZE", 80, raising=False)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None
    assert rep["clusters"] == 1, "동질 그룹이 재분할 상태로 남으면 사용자가 보는 밴드가 과세분화된다"
    assert rep["merged_centroid"] >= 1
    ids = {p[2]: p[0] for (q, p) in _updates(cur, "rag_objects")}
    assert len(set(ids.values())) == 1


def test_pass_merge_gate_off_preserves_split(monkeypatch):
    """MERGE_SIM 을 1 초과로 올리면 병합 무발동 — 종전(재분할 상태) 동작이 그대로 재현된다."""
    pytest.importorskip("numpy")
    import math

    def v(deg):
        return [math.cos(math.radians(deg)), math.sin(math.radians(deg))]

    # 두 하위군 A(0.0/0.5/1.0°) · B(20.0/20.5/21.0°). 교차 cos ≥ base τ(0.82) 라 base 에서 단일
    # blob → cap=3 초과 → τ-상승 재분할이 0.96 에서 3+3 으로 쪼갠다. 두 조각의 centroid cos ≈
    # cos(20°) ≈ 0.94 ≥ MERGE_SIM(0.90) 이므로 응집 병합이 되돌린다(과세분화 해소의 정확한 경로).
    rag = [(i + 1, "ds1:aaa.dbo.t%d" % (i + 1), "t%d" % (i + 1), v(d), None, None, "dbo")
           for i, d in enumerate([0.0, 0.5, 1.0, 20.0, 20.5, 21.0])]
    cur = _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MAX_SIZE", 3, raising=False)
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MERGE_SIM", 1.01, raising=False)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["clusters"] == 2 and rep["merged_centroid"] == 0


def test_pass_min_size_drops_two_member_bands(monkeypatch):
    """MIN_SIZE=3 이면 2멤버 후보는 밴드가 되지 않는다(NULL → 프론트 affix 폴백 경로)."""
    pytest.importorskip("numpy")
    rag = [
        (1, "ds1:aaa.dbo.t1", "t1", [1.0, 0.0], None, None, "dbo"),
        (2, "ds1:aaa.dbo.t2", "t2", [0.999, 0.01], None, None, "dbo"),
        (3, "ds1:aaa.dbo.t3", "t3", [0.0, 1.0], None, None, "dbo"),
        (4, "ds1:aaa.dbo.t4", "t4", [0.01, 0.999], None, None, "dbo"),
    ]
    _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MIN_SIZE", 3, raising=False)
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_ATTACH_SIM", 0.99, raising=False)
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["clusters"] == 0


def test_pass_label_collision_merges_and_pins_cache(monkeypatch):
    """같은 LLM 라벨을 받은 두 밴드가 병합되고, 병합 멤버셋 키로 라벨 캐시가 pin 된다."""
    pytest.importorskip("numpy")
    import math

    def v(deg):
        return [math.cos(math.radians(deg)), math.sin(math.radians(deg))]

    # 두 그룹(0°대 / 32°대): 교차 cos ≈ 0.85 < MERGE_SIM 이라 centroid 병합은 무발동 →
    # 라벨 충돌(둘 다 "길드 게시판") 경로만 발동하는 구성.
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
    monkeypatch.setattr(sc, "_llm_content_labels",
                        lambda cur_, dsk, eff, clusters, fetch_summaries=None:
                        {cl["idx"]: "길드 게시판" for cl in clusters})
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None
    assert rep["merged_label"] == 1 and rep["clusters"] == 1
    ids = {p[2]: (p[0], p[1]) for (q, p) in _updates(cur, "rag_objects")}
    assert len({cid for (cid, _lab) in ids.values()}) == 1
    assert all(lab == "길드 게시판" for (_cid, lab) in ids.values())
    # kv pin: 병합 멤버셋 해시 키로 라벨이 적재돼 다음 pass 는 LLM 재호출 0.
    pins = [p for (q, p) in cur.executed if "INSERT INTO agent_runtime.kv" in q]
    assert any(p and str(p[1]).startswith("label:") and p[2] == "길드 게시판" for p in pins)


def test_pass_label_collision_cap_blocked_disambiguates(monkeypatch):
    """cap 이 병합을 막으면 두 밴드가 남되 **라벨이 서로 달라진다**(같은 라벨 중복 노출 방지)."""
    pytest.importorskip("numpy")
    import math

    def v(deg):
        return [math.cos(math.radians(deg)), math.sin(math.radians(deg))]

    rag = [
        (1, "ds1:aaa.dbo.dt_guildboard", "dt_guildboard", v(0.0), None, None, "dbo"),
        (2, "ds1:aaa.dbo.dt_guildboardlog", "dt_guildboardlog", v(0.5), None, None, "dbo"),
        (3, "ds1:aaa.dbo.dt_guildboardacl", "dt_guildboardacl", v(1.0), None, None, "dbo"),
        (4, "ds1:aaa.dbo.ut_guildpost", "ut_guildpost", v(32.0), None, None, "dbo"),
        (5, "ds1:aaa.dbo.ut_guildpostlog", "ut_guildpostlog", v(32.5), None, None, "dbo"),
        (6, "ds1:aaa.dbo.ut_guildpostacl", "ut_guildpostacl", v(33.0), None, None, "dbo"),
    ]
    cur = _pass_env(monkeypatch, rag, [])
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MAX_SIZE", 3, raising=False)
    monkeypatch.setattr(_cfgattr(), "AGENT_METADATA_CLUSTER_MERGE_MAX_SIZE", 3, raising=False)
    monkeypatch.setattr(sc, "_llm_content_labels",
                        lambda cur_, dsk, eff, clusters, fetch_summaries=None:
                        {cl["idx"]: "길드 게시판" for cl in clusters})
    rep = sc.run_semantic_cluster_pass("common", "ds1")
    assert rep["error"] is None and rep["clusters"] == 2 and rep["merged_label"] == 0
    labs = {p[1] for (q, p) in _updates(cur, "rag_objects")}
    assert len(labs) == 2, "cap 초과 잔여는 라벨 구별 표기로 사용자에게 분할 근거를 노출한다"
    assert all(str(lab).startswith("길드 게시판 · ") for lab in labs)


# ── C6: §18.8 codex 적대 검증 in-cycle 흡수 ──────────────────────────────────
def test_merge_blocks_bridge_chaining_complete_linkage():
    """codex P2-4 회귀 잠금: A~B·B~C 는 가깝고 A~C 는 먼 bridge 에서 3조각이 한 밴드로 연쇄되지 않는다.

    누적 centroid 만 보면 병합할수록 중간 지점으로 이동해 임계를 계속 만족하고, 서로 다른 의미군이
    MERGE_MAX_SIZE 까지 합쳐진다(단일연결 chaining). complete linkage(원본 조각 전 교차쌍 ≥ sim)는
    A~C 가 임계 미만인 순간 병합을 멈춘다."""
    pytest.importorskip("numpy")
    import math

    def v(deg):
        return [math.cos(math.radians(deg)), math.sin(math.radians(deg))]

    # A(0°) · B(20°) · C(40°): cos(20°)=0.940 ≥ 0.90 이지만 cos(40°)=0.766 < 0.90.
    embs = [v(0.0), v(0.5), v(20.0), v(20.5), v(40.0), v(40.5)]
    comps = [[0, 1], [2, 3], [4, 5]]
    keyof = (lambda m: min("t%02d" % i for i in m))
    merged, n = sc._merge_components_by_centroid(embs, comps, 0.90, 80, key_of=keyof)
    # cluster-signal-repair(2026-07-30) 이후: complete linkage **에 더해** 적응형 하한이 함께 막는다.
    #   이 fixture 는 3쌍 중 2쌍(A-B·B-C)이 0.94 로 같아 median 이 0.94 → floor 0.98 → 병합 0건.
    #   "0.94 가 이 분포에서 distinctive 하지 않다" 는 판정이 맞다(어느 쌍을 고를지 임의가 된다).
    #   ⭐ 불변식(본 테스트의 목적)은 그대로: **A 와 C 가 같은 밴드에 절대 들어가지 않는다.**
    assert n == 0, "적응형 하한 + complete linkage 이중 차단"
    assert sorted(len(m) for m in merged) == [2, 2, 2]
    # 순수 complete-linkage 동작은 적응형 하한을 끈 상태로 별도 확인(로직 커버리지 유지).
    from shared import config as _c
    _old = getattr(_c, "AGENT_METADATA_CLUSTER_MERGE_MARGIN", 0.04)
    try:
        _c.AGENT_METADATA_CLUSTER_MERGE_MARGIN = 0.0
        m2, n2 = sc._merge_components_by_centroid(embs, comps, 0.90, 80, key_of=keyof)
        assert n2 == 1 and sorted(len(m) for m in m2) == [2, 4], (n2, [sorted(x) for x in m2])
        for m in m2:
            assert not ({0, 1} & set(m) and {4, 5} & set(m)), m
    finally:
        _c.AGENT_METADATA_CLUSTER_MERGE_MARGIN = _old
    # 어떤 밴드도 A 와 C 를 동시에 담지 않는다(의미군 혼입 금지).
    for m in merged:
        assert not ({0, 1} & set(m) and {4, 5} & set(m)), m


def test_mds_2d_rejects_degenerate_eigenspace():
    """codex P1-1 회귀 잠금: 상위 두 고유값이 동률이면 eigenspace 회전이 미결정 → 2-D 부적격([])."""
    pytest.importorskip("numpy")
    # 3차원 정규직교 centroid 3개 = 완전 대칭 → 상위 두 고유값 동률.
    cents = sc._cluster_centroids([_unit([1, 0, 0]), _unit([0, 1, 0]), _unit([0, 0, 1])],
                                  [[0], [1], [2]])
    assert sc._mds_2d(cents) == []


def test_cluster_order_falls_back_when_mds_ineligible():
    """2-D 부적격이면 grid=True 여도 결정론적 1-D 체인으로 폴백한다(무좌표 배치 금지)."""
    pytest.importorskip("numpy")
    cents = sc._cluster_centroids([_unit([1, 0, 0]), _unit([0, 1, 0]), _unit([0, 0, 1])],
                                  [[0], [1], [2]])
    sizes, keys = [3, 2, 2], ["a", "b", "c"]
    assert sc._cluster_order(cents, sizes, keys, grid=True) == sc._seriate_by_centroid(cents, sizes, keys)


def test_grid_serpentine_preserves_row_count_with_huge_first_band():
    """codex P2-6 회귀 잠금: 거대 밴드가 첫 행을 열어도 의도한 행 수가 유지된다.

    고정 target(total/rows)에서는 잔여 무게가 target 에 못 미쳐 나머지가 한 행에 몰리고 실제 행 수가
    rows 보다 적어졌다(sizes [100,1×8] · rows 3 → 2행). 행마다 '남은 무게/남은 행' 으로 재계산한다."""
    n = 9
    pts = [(i % 3, i // 3) for i in range(n)]
    sizes = [100] + [1] * (n - 1)
    keys = ["k%d" % i for i in range(n)]
    order = sc._grid_serpentine_order(pts, sizes, keys)
    assert sorted(order) == list(range(n))
    # 행 수 복원 검증: 같은 분할 로직을 재구성해 band 수를 센다(순서만 보고는 행 경계를 알 수 없다).
    #   serpentine 은 홀수 행을 역방향으로 내므로, 인접 원소의 x 좌표가 단조에서 꺾이는 지점이 행 경계다.
    xs = [pts[j][0] for j in order]
    turns = sum(1 for i in range(1, len(xs) - 1)
                if (xs[i] - xs[i - 1]) * (xs[i + 1] - xs[i]) < 0)
    assert turns >= 1, ("행이 2개 이상 생성돼야 serpentine 꺾임이 있다", xs)
