"""feature-0016 graph-hop-budget — 이웃 깊이(depth) 예산 계약 테스트.

배경(라이브 실측 2026-07-28): `neighborhood` 의 노드 상한 `_NEIGHBOR_NODE_CAP`(300)이 hop 경계보다
먼저 걸려, 컬럼 투영 테이블 40개 표본에서 **2-hop 절단 50% · "3-hop 결과가 2-hop 과 완전 동일" 50%**
였다(= 3-hop 선택이 무의미). 원인은 2-hop 이 계층 엣지(HAS_*)를 따라가 "같은 스키마의 형제" 수백 개로
예산을 소진한 것 + 절단 순서가 vertex 라벨 알파벳 순(Table 이 맨 뒤 = 가장 먼저 탈락)이었던 것.

본 스위트가 고정하는 계약:
  ① 1-hop 은 전 엣지 라벨을 따라간다(앵커의 컬럼·소속 스키마·직결 루틴 = 상세 패널 원천).
  ② 2-hop 이상은 관계 엣지(_REL_ELABELS)만 따라간다 — 계층 엣지는 SQL 에서 제외된다.
  ③ 관계로 새로 들어온 Column 의 소속 Table 은 보강되되(렌더 정합), 다음 프론티어에는 들어가지 않는다.
  ④ cap 절단 시 관계 이웃 → 라벨 우선순위(Table > Column > Routine …) 순으로 남는다(결정론).
  ⑤ 절단 신호는 truncated(기존 계약) + truncated_hop + omitted_nodes 로 보고된다.

DB/AGE 불요 — fake cursor 로 SQL 문자열과 응답 행을 제어한다.
실행: python3 -m pytest unit/feature-0002-agent-core/tests/test_graph_hop_budget.py -q
"""
import json

from modules import metadata_graph as mg


# ── fakes ─────────────────────────────────────────────────────────────────────
class NbrFake:
    """neighborhood 의 쿼리 종류를 문자열로 식별해 시나리오 행을 돌려주는 fake cursor.

    edges_by_hop: hop(0-based) → [(start_gid, end_gid, etype), ...]
    verts:        gid → (label, key)
    parents:      child_col_gid → parent_table_gid  (HAS_COLUMN 역참조 보강용)
    """

    def __init__(self, start, verts, edges_by_hop, parents=None):
        self.start = start                  # (gid, label, key)
        self.verts = dict(verts)
        self.edges_by_hop = list(edges_by_hop)
        self.parents = dict(parents or {})
        self.log = []
        self._rows = []
        self._hop = -1

    # -- helpers
    def _props(self, gid):
        lbl, key = self.verts[gid]
        return json.dumps({"key": key, "name": key.split(".")[-1]})

    def _gids_in(self, sql):
        import re
        return [int(g) for g in re.findall(r"'(\d+)'::ag_catalog\.graphid", sql)]

    # -- cursor protocol
    def execute(self, sql, params=None):
        s = str(sql)
        self.log.append(s)
        if "to_regclass" in s:
            n = s.count("to_regclass")
            self._rows = [tuple(["reg"] * n)]
            return
        # 앵커 조회. **`WHERE properties @>` 로 좁힌다** — 엣지 수집 SQL 도 broken 후순위 정렬 키(R3-d)에
        #   `properties @> '{"status": "broken"}'` 를 포함하므로, 느슨한 부분문자열 판정은 엣지 쿼리를
        #   앵커 조회로 오인해 스위트 전체를 무너뜨린다(실제 발생).
        if "WHERE properties @> " in s:
            gid, lbl, key = self.start
            self._rows = [(str(gid), json.dumps({"key": key, "name": key}), lbl)]
            return
        if "start_id = ANY" in s and "OR end_id = ANY" in s:   # (2) 엣지 수집
            self._hop += 1
            hits = self.edges_by_hop[self._hop] if self._hop < len(self.edges_by_hop) else []
            # 이번 hop 의 SQL 에 실제로 포함된 엣지 라벨만 통과 — 계층 엣지 제외 계약을 fake 가 존중한다.
            # 항목은 (a, b, et) 또는 (a, b, et, props_dict) — 후자는 status:broken 등 엣지 속성 시나리오.
            rows = []
            for h in hits:
                a, b, et = h[0], h[1], h[2]
                pr = h[3] if len(h) > 3 else None
                if f'metadata_kb."{et}"' not in s:
                    continue
                rows.append((str(a), str(b), json.dumps(pr) if pr else None, et))
            self._rows = rows
            return
        if "DISTINCT start_id" in s:                   # (3b) 부모 gid 역참조
            kids = self._gids_in(s)
            self._rows = [(str(self.parents[k]),) for k in kids if k in self.parents]
            return
        if s.startswith("SELECT start_id::text, end_id::text"):   # (3b) 보강 HAS_COLUMN 엣지
            kids = self._gids_in(s)
            self._rows = [(str(self.parents[k]), str(k)) for k in kids if k in self.parents]
            return
        if "AS gid" in s and "id = ANY" in s:          # (3) 이웃 해소
            want = set(self._gids_in(s))
            rows = []
            for g in sorted(want):
                if g not in self.verts:
                    continue
                lbl = self.verts[g][0]
                if f'metadata_kb."{lbl}"' not in s:
                    continue
                rows.append((str(g), self._props(g), lbl))
            self._rows = rows
            return
        if s.startswith("SELECT id::text, properties::text"):     # (3b) 보강 Table 해소
            want = self._gids_in(s)
            self._rows = [(str(g), self._props(g)) for g in want if g in self.verts]
            return
        self._rows = []

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def close(self):
        pass


class FakeConn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _edge_sqls(fake):
    return [s for s in fake.log if "start_id = ANY" in s and "OR end_id = ANY" in s]


# ── 상수 계약 ─────────────────────────────────────────────────────────────────
def test_rel_and_hier_labels_partition_edge_whitelist():
    """관계/계층 분류가 엣지 화이트리스트를 겹침 없이 덮는다 — 어느 쪽에도 없는 라벨은 2-hop 에서 조용히 사라진다."""
    assert mg._REL_ELABELS & mg._HIER_ELABELS == set()
    assert (mg._REL_ELABELS | mg._HIER_ELABELS) == set(mg._ELABELS)


def test_label_priority_covers_all_vertex_labels_and_ranks_table_first():
    """절단 우선순위가 전 vertex 라벨을 덮고, Table 이 Routine 보다 앞선다(알파벳 순 절단의 역전)."""
    assert set(mg._NEIGHBOR_LABEL_PRIORITY) == set(mg._VLABELS)
    rank = {l: i for i, l in enumerate(mg._NEIGHBOR_LABEL_PRIORITY)}
    assert rank["Table"] < rank["Routine"]
    assert rank["Column"] < rank["Routine"]


# ── ① / ② hop 별 엣지 라벨 ────────────────────────────────────────────────────
def test_hop1_follows_all_edge_labels():
    """1-hop 은 계층 엣지를 포함해 전 라벨을 따라간다(앵커 직결 정보 보존)."""
    fake = NbrFake(start=(1, "Table", "ds:db.orders"),
                   verts={1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.id")},
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")]])
    out = mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake))
    sqls = _edge_sqls(fake)
    assert len(sqls) == 1
    for et in mg._HIER_ELABELS | mg._REL_ELABELS:
        assert f'metadata_kb."{et}"' in sqls[0]
    assert {n["key"] for n in out["nodes"]} == {"ds:db.orders", "ds:db.orders.id"}
    assert out["truncated"] is False and out["truncated_hop"] is None


def test_hop2_excludes_hierarchy_edges():
    """2-hop 이상의 엣지 SQL 에서 계층 엣지(HAS_*)가 제외된다 — 형제 폭발 차단의 핵심 계약."""
    fake = NbrFake(start=(1, "Table", "ds:db.orders"),
                   verts={1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust"),
                          3: ("Column", "ds:db.customers.id"), 4: ("Table", "ds:db.customers")},
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")], [(2, 3, "REFERENCES")]],
                   parents={3: 4})
    mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    sqls = _edge_sqls(fake)
    assert len(sqls) == 2, sqls
    for et in mg._HIER_ELABELS:
        assert f'metadata_kb."{et}"' not in sqls[1], et
    for et in mg._REL_ELABELS:
        assert f'metadata_kb."{et}"' in sqls[1], et


# ── ③ 관계 이웃 Column 의 부모 Table 보강 ──────────────────────────────────────
def test_hop2_backfills_parent_table_of_related_column():
    """REFERENCES 로 들어온 컬럼의 소속 Table 이 보강된다 — 없으면 프론트가 그 컬럼을 렌더에서 드롭한다."""
    fake = NbrFake(start=(1, "Table", "ds:db.orders"),
                   verts={1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust"),
                          3: ("Column", "ds:db.customers.id"), 4: ("Table", "ds:db.customers")},
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")], [(2, 3, "REFERENCES")]],
                   parents={3: 4})
    out = mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    keys = {n["key"] for n in out["nodes"]}
    assert "ds:db.customers" in keys, keys          # 부모 테이블 보강
    assert "ds:db.customers.id" in keys
    types = {(e["source"], e["target"], e["type"]) for e in out["edges"]}
    assert ("ds:db.orders.cust", "ds:db.customers.id", "REFERENCES") in types
    assert ("ds:db.customers", "ds:db.customers.id", "HAS_COLUMN") in types   # 소속 엣지도 실린다


def test_backfilled_parent_is_not_expanded_next_hop():
    """보강된 부모 Table 은 다음 프론티어에 들어가지 않는다 — 넣으면 그 테이블의 형제가 다시 폭발한다."""
    fake = NbrFake(start=(1, "Table", "ds:db.orders"),
                   verts={1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust"),
                          3: ("Column", "ds:db.customers.id"), 4: ("Table", "ds:db.customers")},
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")], [(2, 3, "REFERENCES")], []],
                   parents={3: 4})
    mg.neighborhood("ds:db.orders", depth=3, conn=FakeConn(fake))
    sqls = _edge_sqls(fake)
    assert len(sqls) == 3, sqls
    # 3번째 hop 프론티어는 (2-hop 에 들어온) 컬럼 3 만 — 보강 부모 4 는 없다.
    assert "'3'::ag_catalog.graphid" in sqls[2]
    assert "'4'::ag_catalog.graphid" not in sqls[2]


# ── ④ 절단 우선순위 · ⑤ 절단 신호 ────────────────────────────────────────────
def test_cap_truncation_keeps_relation_neighbors_and_reports_signals(monkeypatch):
    """cap 절단 시 관계 이웃이 먼저 남고, truncated/truncated_hop/omitted_nodes 가 보고된다."""
    monkeypatch.setattr(mg, "_NEIGHBOR_NODE_CAP", 3)   # 앵커 + 이웃 2개까지만
    verts = {1: ("Table", "ds:db.orders")}
    edges = []
    # 계층 이웃(Column) 5개 — 라벨 우선순위는 Column 이 Routine 보다 앞이지만 관계 이웃보다는 뒤.
    for g in range(10, 15):
        verts[g] = ("Column", f"ds:db.orders.c{g}")
        edges.append((1, g, "HAS_COLUMN"))
    # 관계 이웃(Routine) 2개 — 라벨 순위는 낮지만 **관계** 라 우선 남아야 한다.
    for g in (20, 21):
        verts[g] = ("Routine", f"ds:db.sp_{g}")
        edges.append((g, 1, "ROUTINE_USES"))
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts, edges_by_hop=[edges])
    out = mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake))
    keys = {n["key"] for n in out["nodes"]}
    assert len(out["nodes"]) == 3
    assert keys == {"ds:db.orders", "ds:db.sp_20", "ds:db.sp_21"}, keys
    assert out["truncated"] is True
    assert out["truncated_hop"] == 1
    assert out["omitted_nodes"] >= 5


def test_label_priority_breaks_ties_within_same_tier(monkeypatch):
    """같은 등급(계층 이웃) 안에서는 라벨 우선순위대로 남는다 — Table 이 Routine 보다 먼저."""
    monkeypatch.setattr(mg, "_NEIGHBOR_NODE_CAP", 3)
    verts = {1: ("Schema", "ds:db")}
    edges = []
    for g in (30, 31):
        verts[g] = ("Routine", f"ds:db.sp_{g}")
        edges.append((1, g, "HAS_ROUTINE"))
    for g in (40, 41):
        verts[g] = ("Table", f"ds:db.t{g}")
        edges.append((1, g, "HAS_TABLE"))
    fake = NbrFake(start=(1, "Schema", "ds:db"), verts=verts, edges_by_hop=[edges])
    out = mg.neighborhood("ds:db", depth=1, conn=FakeConn(fake))
    keys = {n["key"] for n in out["nodes"]}
    assert keys == {"ds:db", "ds:db.t40", "ds:db.t41"}, keys
    assert out["truncated"] is True and out["truncated_hop"] == 1


def test_no_relation_neighbor_makes_hop2_equal_hop1():
    """확장할 관계가 없으면 2-hop 결과가 1-hop 과 같다 — 프론트가 이 사실을 사용자에게 알린다(정직)."""
    fake1 = NbrFake(start=(1, "Table", "ds:db.orders"),
                    verts={1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.id")},
                    edges_by_hop=[[(1, 2, "HAS_COLUMN")], []])
    fake2 = NbrFake(start=(1, "Table", "ds:db.orders"),
                    verts={1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.id")},
                    edges_by_hop=[[(1, 2, "HAS_COLUMN")], []])
    a = mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake1))
    b = mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake2))
    assert {n["key"] for n in a["nodes"]} == {n["key"] for n in b["nodes"]}
    assert len(a["edges"]) == len(b["edges"])
    assert b["truncated"] is False


# ── 적대 리뷰(codex, 2026-07-28) 흡수분 ───────────────────────────────────────
def test_parent_backfill_reserve_survives_hierarchy_neighbor_flood(monkeypatch):
    """[P1] 계층 이웃이 예산을 다 먹어도 관계 컬럼의 **부모 Table** 은 남는다.

    부모가 없으면 프론트(`colsByTable`)가 그 컬럼을 렌더에서 드롭해, HB.3 이 없애려던 실패
    ("참조로 이어지는 테이블이 화면에 없다")가 cap 상황에서만 되살아난다. 예약 예산이 그 우선순위
    역전을 막는지 — 즉 관계 컬럼이 들어왔으면 그 부모도 반드시 함께 들어오는지 — 를 고정한다.
    """
    monkeypatch.setattr(mg, "_NEIGHBOR_NODE_CAP", 12)
    monkeypatch.setattr(mg, "_PARENT_BACKFILL_RESERVE", 4)
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust")}
    hop0 = [(1, 2, "HAS_COLUMN")]
    # hop1: 관계(REFERENCES)로 들어오는 타 테이블 컬럼 1개 + 계층 이웃 홍수 20개.
    verts[3] = ("Column", "ds:db.customers.id")
    verts[99] = ("Table", "ds:db.customers")          # 3 의 부모 — 보강 대상
    hop1 = [(2, 3, "REFERENCES")]
    for g in range(50, 70):                            # 계층 이웃 홍수(Routine)
        verts[g] = ("Routine", f"ds:db.sp_{g}")
        hop1.append((g, 1, "ROUTINE_USES"))
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[hop0, hop1], parents={3: 99})
    out = mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    keys = {n["key"] for n in out["nodes"]}
    assert "ds:db.customers.id" in keys, keys          # 참조 대상 컬럼
    assert "ds:db.customers" in keys, keys             # ← 그 부모가 예약 예산으로 살아남는다
    assert len(out["nodes"]) <= mg._NEIGHBOR_NODE_CAP
    # 부모↔자식 HAS_COLUMN 엣지도 실려야 프론트가 소속을 안다.
    assert any(e["type"] == "HAS_COLUMN" and e["target"] == "ds:db.customers.id"
               for e in out["edges"]), out["edges"]


def test_reserve_not_applied_when_no_relation_column(monkeypatch):
    """예약은 관계 Column 이 실제로 들어올 때만 — 없으면 예산을 온전히 계층 이웃에 쓴다(무의미한 축소 방지)."""
    monkeypatch.setattr(mg, "_NEIGHBOR_NODE_CAP", 6)
    monkeypatch.setattr(mg, "_PARENT_BACKFILL_RESERVE", 4)
    verts = {1: ("Schema", "ds:db")}
    hop0 = []
    for g in range(40, 50):
        verts[g] = ("Table", f"ds:db.t{g}")
        hop0.append((1, g, "HAS_TABLE"))
    fake = NbrFake(start=(1, "Schema", "ds:db"), verts=verts, edges_by_hop=[hop0, []])
    out = mg.neighborhood("ds:db", depth=2, conn=FakeConn(fake))
    # 관계 Column 이 없으므로 예약 없이 cap 전량(앵커 + 5)을 채운다.
    assert len(out["nodes"]) == 6, [n["key"] for n in out["nodes"]]


def test_reserve_scales_down_to_actual_parent_need(monkeypatch):
    """예약량은 관계 Column 후보 수를 상한으로 비례 축소된다 — 부모 1개면 예산 1칸만 뗀다(낭비 방지)."""
    monkeypatch.setattr(mg, "_NEIGHBOR_NODE_CAP", 10)
    monkeypatch.setattr(mg, "_PARENT_BACKFILL_RESERVE", 60)   # 후보 수보다 훨씬 큰 예약값
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust"),
             3: ("Column", "ds:db.customers.id"), 99: ("Table", "ds:db.customers")}
    hop1 = [(2, 3, "REFERENCES")]
    for g in range(50, 60):
        verts[g] = ("Routine", f"ds:db.sp_{g}")
        hop1.append((g, 1, "ROUTINE_USES"))
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")], hop1], parents={3: 99})
    out = mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    keys = {n["key"] for n in out["nodes"]}
    assert "ds:db.customers" in keys and "ds:db.customers.id" in keys, keys
    # 예약이 60 이 아니라 1(관계 Column 후보 1개)로 축소돼, 남은 예산이 Routine 으로 채워진다.
    assert sum(1 for k in keys if ".sp_" in k) >= 6, keys
    assert len(out["nodes"]) <= mg._NEIGHBOR_NODE_CAP


def test_edge_fetch_cap_saturation_is_reported_as_truncated(monkeypatch):
    """[P2] 엣지 UNION 의 전역 LIMIT 포화도 절단으로 신고한다.

    이 LIMIT 은 우선순위 정렬 **이전** 에 잘리므로 뒤쪽 REFERENCES/ROUTINE_USES 가 조용히 탈락한다.
    종전엔 노드 cap 도달만 truncated 로 봐서 **부분 그래프를 truncated=false 로 반환**했고, 그러면
    프론트의 "아래 직접 연결 목록은 전량" 고지가 거짓이 된다.
    """
    monkeypatch.setattr(mg, "_EDGE_FETCH_CAP", 3)      # cap+1(=4)행이 오면 포화로 간주
    verts = {1: ("Table", "ds:db.orders")}
    hop0 = []
    for g in (11, 12, 13, 14):
        verts[g] = ("Column", f"ds:db.orders.c{g}")
        hop0.append((1, g, "HAS_COLUMN"))
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts, edges_by_hop=[hop0, []])
    out = mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake))
    assert out["truncated"] is True, out                # 노드 cap 은 여유(300)인데도 절단 신고
    assert out["truncated_hop"] == 1
    assert f"LIMIT {mg._EDGE_FETCH_CAP + 1}" in _edge_sqls(fake)[0]


def test_edge_fetch_cap_not_saturated_stays_untruncated():
    """LIMIT 미포화면 절단 신고하지 않는다 — P2 수정이 거짓 양성을 만들지 않는지(대조군)."""
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.id")}
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")], []])
    out = mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake))
    assert out["truncated"] is False and out["truncated_hop"] is None


def test_broken_edges_do_not_claim_relation_priority(monkeypatch):
    """[R2-a] `broken` 엣지의 끝점은 관계 우선권을 받지 않는다.

    broken 엣지는 (4) 엣지 빌드에서 버려지므로, 그 끝점에 tier 0 을 주면 **표시도 안 되는 이웃이 cap 을
    먹고 유효 이웃을 밀어낸다**(sync 창 사이 stale). 예산 배정이 실제 표시분과 일치해야 한다.
    """
    monkeypatch.setattr(mg, "_NEIGHBOR_NODE_CAP", 3)
    verts = {1: ("Table", "ds:db.orders")}
    edges = []
    # broken REFERENCES 로 이어진 Routine 2개 — 관계 라벨이지만 버려질 엣지다.
    for g in (20, 21):
        verts[g] = ("Routine", f"ds:db.brk_{g}")
        edges.append((g, 1, "ROUTINE_USES", {"status": "broken"}))
    # 정상 계층 이웃 Table 2개 — broken 이 우선권을 빼앗지 않으면 이쪽이 남아야 한다.
    for g in (40, 41):
        verts[g] = ("Table", f"ds:db.t{g}")
        edges.append((1, g, "HAS_TABLE", None))
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts, edges_by_hop=[edges])
    out = mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake))
    keys = {n["key"] for n in out["nodes"]}
    assert keys == {"ds:db.orders", "ds:db.t40", "ds:db.t41"}, keys


def test_edge_fetch_limit_is_deterministic_relation_first():
    """[R2-b] 엣지 fetch LIMIT 이 `ORDER BY prio, s, e` 로 잘린다 — 포화해도 관계 엣지가 먼저 남고 재현 가능."""
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.id")}
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")], []])
    mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake))
    sql = _edge_sqls(fake)[0]
    # 적대리뷰 R3-d: broken 후순위(brk)가 prio 다음 정렬 키 — cap 적용 *이전* 에 밀린다.
    # R4-b: brk 가 prio **앞** — 안 그러면 broken 관계행(prio0,brk1)이 유효 계층행(prio1,brk0)을 앞지른다.
    assert "ORDER BY u.brk, u.prio, u.s, u.e" in sql, sql
    # 적대리뷰 R3-a: 포화 판정을 위해 cap+1 을 fetch 한다(정확히 cap 개면 절단이 아니다).
    assert f"LIMIT {mg._EDGE_FETCH_CAP + 1}" in sql, sql
    # 관계 엣지는 prio 0, 계층 엣지는 prio 1 리터럴로 실린다.
    assert "0 AS prio" in sql and "1 AS prio" in sql, sql
    assert "broken" in sql and "AS brk" in sql, sql


def test_expanded_hops_reports_per_hop_gain():
    """[R2-c] hop 별 신규 노드 수를 보고한다 — 2-hop 이 0 이면 그 깊이가 결과를 못 바꿨다는 사실이 드러난다."""
    # 앵커에 직접 REFERENCES 1건이 있으나 그 상대는 leaf → 2-hop 실적 0.
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust"),
             3: ("Column", "ds:db.customers.id"), 99: ("Table", "ds:db.customers")}
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[[(1, 2, "HAS_COLUMN"), (2, 3, "REFERENCES")], []],
                   parents={3: 99})
    out = mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    assert out["expanded_hops"], out
    assert out["expanded_hops"][0] > 0            # 1-hop 은 늘렸다
    assert sum(out["expanded_hops"][1:]) == 0     # 2-hop 이후는 못 늘렸다 → 프론트가 힌트를 띄운다


def test_edge_fetch_exactly_at_cap_is_not_truncated(monkeypatch):
    """[R3-a] 정확히 cap 개면 절단이 아니다 — 경계 거짓 양성 제거(생략된 행이 있다는 증거가 없다)."""
    monkeypatch.setattr(mg, "_EDGE_FETCH_CAP", 3)
    verts = {1: ("Table", "ds:db.orders")}
    hop0 = []
    for g in (11, 12, 13):                              # 정확히 3행 = cap
        verts[g] = ("Column", f"ds:db.orders.c{g}")
        hop0.append((1, g, "HAS_COLUMN"))
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts, edges_by_hop=[hop0])
    out = mg.neighborhood("ds:db.orders", depth=1, conn=FakeConn(fake))
    assert out["truncated"] is False, out
    assert len(out["nodes"]) == 4                        # 앵커 + 컬럼 3 = 전량


def test_parent_backfill_queries_are_ordered_for_determinism():
    """[R3-c] 부모 보강 두 쿼리가 graphid 순으로 정렬된다 — 예약 초과 시 어느 부모가 남는지 재현 가능."""
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust"),
             3: ("Column", "ds:db.customers.id"), 99: ("Table", "ds:db.customers")}
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")], [(2, 3, "REFERENCES")]], parents={3: 99})
    mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    gid_q = [q for q in fake.log if "DISTINCT start_id" in q]
    tbl_q = [q for q in fake.log if q.startswith("SELECT id::text, properties::text")]
    assert gid_q and "ORDER BY start_id::text" in gid_q[0], gid_q
    assert tbl_q and "ORDER BY id" in tbl_q[0], tbl_q


def test_expanded_hop_edges_reports_edge_only_gain():
    """[R3-b] 노드가 안 늘어도 엣지가 늘면 실적으로 보고된다 — 프론트가 "동일" 로 오단정하지 않게."""
    # hop1 에서 이미 발견된 노드(2,3) 사이에 REFERENCES 가 추가된다 — 신규 노드 0, 신규 엣지 1.
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.a"), 3: ("Column", "ds:db.orders.b")}
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[[(1, 2, "HAS_COLUMN"), (1, 3, "HAS_COLUMN")], [(2, 3, "REFERENCES")]])
    out = mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    assert out["expanded_hops"][1] == 0, out["expanded_hops"]
    assert out["expanded_hop_edges"][1] >= 1, out["expanded_hop_edges"]


def test_broken_reached_column_is_not_parent_backfilled():
    """[R4-a] broken 관계로 도달한 Column 은 부모 보강 대상이 아니다.

    곧 버려질 엣지 때문에 무관한 부모 Table + 합성 HAS_COLUMN 이 2-hop 그래프에 등장하면, 사용자는
    존재하지 않는 연결을 보게 되고 "관계 없음" 힌트도 부당하게 억제된다.
    """
    verts = {1: ("Table", "ds:db.orders"), 2: ("Column", "ds:db.orders.cust"),
             3: ("Column", "ds:db.customers.id"), 99: ("Table", "ds:db.customers")}
    fake = NbrFake(start=(1, "Table", "ds:db.orders"), verts=verts,
                   edges_by_hop=[[(1, 2, "HAS_COLUMN")],
                                 [(2, 3, "REFERENCES", {"status": "broken"})]],
                   parents={3: 99})
    out = mg.neighborhood("ds:db.orders", depth=2, conn=FakeConn(fake))
    keys = {n["key"] for n in out["nodes"]}
    assert "ds:db.customers" not in keys, keys          # 부모가 보강되지 않는다
    assert not any(e["type"] == "HAS_COLUMN" and e["target"] == "ds:db.customers.id"
                   for e in out["edges"]), out["edges"]
    # broken 관계는 확장 실적으로도 계산되지 않아야 "관계 없음" 힌트가 살아난다.
    assert sum(out["expanded_hop_edges"][1:]) == 0, out["expanded_hop_edges"]
