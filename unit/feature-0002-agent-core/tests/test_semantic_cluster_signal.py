"""feature-0016 cluster-signal-repair (2026-07-30) — 클러스터 유사도 지표 복구 단위 테스트.

사용자 리포트: "동일한 의미가 다른 이름으로 구성(메일 시스템 ↔ 우편 시스템)" · "각 클러스터 간 관계에
비해 거리가 먼 항목(경매 기록 ↔ 경매 시스템)".

라이브 실측이 밝힌 근인: 테이블 시그니처가 `description/role/columns` 전부 공백이라(columns 원천
`column_descriptions` 는 17,191 중 528개=3% 커버) 임베딩이 **이름+boilerplate** 만 봤다 →
  · 무관한 테이블 클러스터 쌍 centroid 0.915 (= 바닥값, 신호 아님 → MERGE_SIM 0.90 오병합 위험)
  · 같은 컨텐츠의 테이블↔루틴 0.69 (양식이 달라서) → 두 클러스터로 갈려 독립 라벨 = 유의어

본 파일이 잠그는 축:
  S1 시그니처 = 컨텐츠 전면·양식 중립(빈 필드 미방출·종류 접두 제거·이름은 마지막 세그먼트).
  S2 구조적 컨텐츠 주입(used_by/related)이 실제로 어휘를 싣는다.
  S3 적응형 병합 하한 — 전 쌍이 고르게 높은(신호 없는) 분포에서 병합이 억제된다.
  S4 양식 교차 브릿지 — 루틴 클러스터가 자기가 만지는 테이블 클러스터로 병합된다(RC3 의도 실구현).
"""
import pytest

from modules import semantic_cluster as sc


# ── S1·S2: 시그니처 형태 ──────────────────────────────────────────────────────
def test_table_signature_omits_empty_fields_and_kind_prefix():
    """빈 필드는 줄 자체를 내지 않고, `table:` 종류 접두도 없다(양식 boilerplate 제거)."""
    sig = sc.build_table_signature_text("cc_pyron", "UT_Mail", "", [], "", "", analysis="")
    assert sig == "cc_pyron.UT_Mail"
    assert "table:" not in sig and "description:" not in sig and "columns:" not in sig


def test_table_signature_injects_structural_content():
    """used_by(이 테이블을 만지는 루틴명)·related(FK 상대명)가 어휘로 실린다 — 라이브의 유일한 실 신호."""
    sig = sc.build_table_signature_text(
        "cc_pyron", "UT_Mail", "", [], "", "Game Data",
        used_by=["cc_pyron.sp_GetMailList", "cc_pyron.sp_DeleteMail"],
        related=["cc_pyron.DT_Letter"])
    assert "used by: sp_GetMailList, sp_DeleteMail" in sig
    assert "related: DT_Letter" in sig
    assert "cc_pyron.sp_GetMailList" not in sig, "스키마 접두는 전 멤버 공유 boilerplate → 미포함"


def test_table_signature_caps_are_deterministic():
    ub = [f"s.sp_R{i:03d}" for i in range(100)]
    a = sc.build_table_signature_text("s", "T", "", [], "", "", used_by=ub)
    b = sc.build_table_signature_text("s", "T", "", [], "", "", used_by=ub)
    assert a == b
    assert a.count(",") + 1 <= sc._USED_BY_SIG_MAX + 1


def test_routine_signature_shares_table_vocabulary_space():
    """루틴도 종류 접두 없이, touches 는 **테이블명만** — 테이블쪽 `used by:` 와 대칭."""
    sig = sc.build_routine_signature_text(
        "cc_pyron", "sp_GetMailList", "procedure", "IN @CharacterID int", "",
        [{"fqn": "cc_pyron.UT_Mail", "kind": "read"}, {"fqn": "cc_pyron.UT_MailItem", "kind": "write"}])
    assert sig.startswith("cc_pyron.sp_GetMailList")
    assert "routine:" not in sig and "type:" not in sig
    assert "touches: read UT_Mail, write UT_MailItem" in sig


def test_routine_signature_omits_empty_params_returns():
    sig = sc.build_routine_signature_text("s", "sp_X", "procedure", "", "", [])
    assert sig == "s.sp_X"


def test_sig_name_tokens_last_segment_and_paren_strip():
    assert sc._sig_name_tokens("db.dbo.T_User") == "T_User"
    assert sc._sig_name_tokens("cc.sp_Get()") == "sp_Get"
    assert sc._sig_name_tokens("") == "" and sc._sig_name_tokens(None) == ""


# ── S3: 적응형 병합 하한 ──────────────────────────────────────────────────────
def _unit(v):
    import math
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def test_adaptive_floor_suppresses_merge_on_flat_high_distribution():
    """라이브 결함 재현: 전 쌍이 고르게 높으면(boilerplate 바닥) 절대 임계를 넘어도 병합하지 않는다.

    종전(절대 임계 단독)에는 0.915 쌍이 MERGE_SIM 0.90 을 넘어 **무관한 컨텐츠**가 병합됐다."""
    pytest.importorskip("numpy")
    import math
    # 4개 클러스터를 좁은 각도 안에 균일 배치 → 전 쌍 코사인이 0.90~0.95 로 평탄(median 도 높다).
    embs, comps = [], []
    for k, deg in enumerate([0.0, 12.0, 24.0, 36.0]):
        embs.append(_unit([math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0]))
        comps.append([k])
    keyof = (lambda m: min("t%02d" % i for i in m))
    kept, n = sc._merge_components_by_centroid(embs, comps, 0.90, 80, key_of=keyof)
    assert n == 0, "평탄-고 분포는 신호가 없으므로 병합 억제(적응형 하한)"
    assert len(kept) == 4


def test_adaptive_floor_still_merges_a_distinct_outlier_pair():
    """진짜 이웃 한 쌍만 튀는 분포에서는 종전처럼 병합된다(적응형이 기능을 죽이지 않음)."""
    pytest.importorskip("numpy")
    embs = [_unit([1, 0, 0]), _unit([0.999, 0.02, 0]),      # 이 둘만 매우 가깝다
            _unit([0, 1, 0]), _unit([0, 0, 1])]
    comps = [[0], [1], [2], [3]]
    keyof = (lambda m: min("t%02d" % i for i in m))
    kept, n = sc._merge_components_by_centroid(embs, comps, 0.90, 80, key_of=keyof)
    assert n == 1 and sorted(sorted(c) for c in kept) == [[0, 1], [2], [3]]


def test_merge_margin_zero_restores_absolute_only():
    """MERGE_MARGIN=0 이면 종전(절대 임계 단독) 동작 — 롤백 경로 보장."""
    pytest.importorskip("numpy")
    import math
    from shared import config as _c
    embs, comps = [], []
    for k, deg in enumerate([0.0, 12.0, 24.0, 36.0]):
        embs.append(_unit([math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0]))
        comps.append([k])
    old = getattr(_c, "AGENT_METADATA_CLUSTER_MERGE_MARGIN", 0.04)
    try:
        _c.AGENT_METADATA_CLUSTER_MERGE_MARGIN = 0.0
        kept, n = sc._merge_components_by_centroid(embs, comps, 0.90, 80,
                                                   key_of=lambda m: min("t%02d" % i for i in m))
        assert n >= 1, "절대 임계 단독이면 0.90 초과 쌍이 병합된다(종전 동작)"
    finally:
        _c.AGENT_METADATA_CLUSTER_MERGE_MARGIN = old


# ── S4: 양식 교차 브릿지 ──────────────────────────────────────────────────────
def _items(spec):
    """spec: [(kind, name, refs)] → items 리스트(브릿지가 읽는 필드만)."""
    out = []
    for kind, name, refs in spec:
        out.append({"kind": kind, "name": name, "key": f"ds:s.{name}",
                    "refs": [{"fqn": f"s.{r}", "kind": "read"} for r in (refs or [])]})
    return out


def test_bridge_merges_routine_cluster_into_touched_table_cluster():
    """사용자 리포트 직접 해소: 메일 루틴 클러스터가 메일 테이블 클러스터로 병합된다(→ 라벨 1개)."""
    items = _items([
        ("table", "UT_Mail", None), ("table", "UT_MailItem", None), ("table", "DT_Letter", None),
        ("routine", "sp_GetMailList", ["UT_Mail", "UT_MailItem"]),
        ("routine", "sp_DeleteMail", ["UT_Mail", "DT_Letter"]),
        ("routine", "sp_ReturnMail", ["UT_MailItem", "DT_Letter"]),
    ])
    comps = [[0, 1, 2], [3, 4, 5]]        # 테이블 클러스터 / 루틴 클러스터
    out, n = sc._bridge_routine_clusters(items, comps, 80, min_frac=0.5)
    assert n == 1
    assert [sorted(c) for c in out] == [[0, 1, 2, 3, 4, 5]]


def test_bridge_requires_two_distinct_tables():
    """단일 우발 참조로는 병합하지 않는다(서로 다른 테이블 2개 이상 매칭 필요)."""
    items = _items([("table", "UT_Mail", None), ("table", "UT_MailItem", None),
                    ("routine", "sp_Ping", ["UT_Mail"]), ("routine", "sp_Ping2", ["UT_Mail"])])
    out, n = sc._bridge_routine_clusters(items, [[0, 1], [2, 3]], 80, min_frac=0.5)
    assert n == 0 and [sorted(c) for c in out] == [[0, 1], [2, 3]]


def test_bridge_respects_min_frac_when_references_are_split():
    """참조가 두 테이블 클러스터로 갈리면(과반 없음) 병합하지 않는다."""
    items = _items([
        ("table", "UT_Mail", None), ("table", "UT_MailItem", None),
        ("table", "UT_Auction", None), ("table", "UT_AuctionBid", None),
        ("routine", "sp_A", ["UT_Mail", "UT_MailItem"]),
        ("routine", "sp_B", ["UT_Auction", "UT_AuctionBid"]),
    ])
    out, n = sc._bridge_routine_clusters(items, [[0, 1], [2, 3], [4, 5]], 80, min_frac=0.75)
    assert n == 0, "50/50 분할은 min_frac 0.75 미달 → 보류"


def test_bridge_respects_max_size_and_is_deterministic():
    items = _items([("table", "T1", None), ("table", "T2", None),
                    ("routine", "sp_1", ["T1", "T2"]), ("routine", "sp_2", ["T1", "T2"])])
    out, n = sc._bridge_routine_clusters(items, [[0, 1], [2, 3]], 3, min_frac=0.5)
    assert n == 0, "2+2=4 > cap 3 → 보류"
    a = sc._bridge_routine_clusters(items, [[0, 1], [2, 3]], 80, min_frac=0.5)
    b = sc._bridge_routine_clusters(items, [[0, 1], [2, 3]], 80, min_frac=0.5)
    assert [sorted(c) for c in a[0]] == [sorted(c) for c in b[0]] and a[1] == b[1]


def test_bridge_noop_without_table_clusters_or_refs():
    items = _items([("routine", "sp_1", ["X"]), ("routine", "sp_2", ["Y"])])
    out, n = sc._bridge_routine_clusters(items, [[0], [1]], 80, min_frac=0.5)
    assert n == 0 and len(out) == 2
    assert sc._bridge_routine_clusters([], [[0]], 80)[1] == 0


def test_signal_repair_config_defaults():
    from shared import config as _c
    assert _c.AGENT_METADATA_CLUSTER_MERGE_MARGIN > 0, "적응형 하한 기본 활성"
    assert 0 < _c.AGENT_METADATA_CLUSTER_BRIDGE_MIN_FRAC <= 1.0


# ── S5: §18.8 codex 적대 검증 in-cycle 흡수 ──────────────────────────────────
class _Cur:
    """build_used_by_index 전용 최소 fake — SAVEPOINT/RELEASE 무시, 1개 SELECT 결과 반환."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.rows


def test_used_by_index_single_scan_and_cross_schema_excluded():
    """codex P1/P2: (ds, eff) 당 1회 스캔으로 역인덱스 + **다른 DB 동명 테이블 배제**."""
    rows = [
        ("sp_GetMailList", [{"fqn": "cc_pyron.UT_Mail", "kind": "read"},
                            {"fqn": "other_db.UT_Mail", "kind": "read"}]),
        ("sp_DeleteMail", [{"fqn": "UT_Mail", "kind": "write"}]),           # 스키마 세그먼트 없음 → 허용
        ("sp_Auction", [{"fqn": "cc_pyron.UT_Auction", "kind": "read"}]),
    ]
    idx = sc.build_used_by_index(_Cur(rows), "ds1", "cc_pyron")
    assert idx["ut_mail"] == ["sp_GetMailList", "sp_DeleteMail"]
    assert idx["ut_auction"] == ["sp_Auction"]
    # other_db.UT_Mail 은 배제됐으므로 sp_GetMailList 가 중복 계수되지 않았다
    assert idx["ut_mail"].count("sp_GetMailList") == 1


def test_used_by_index_json_string_and_cap():
    import json as _j
    rows = [(f"sp_{i:03d}", _j.dumps([{"fqn": "s.T", "kind": "read"}])) for i in range(60)]
    idx = sc.build_used_by_index(_Cur(rows), "ds1", "s")
    assert len(idx["t"]) == sc._USED_BY_SIG_MAX, "상한 적용"
    assert idx["t"] == sorted(idx["t"]), "정렬 결정론"


def test_used_by_index_malformed_is_soft():
    assert sc.build_used_by_index(_Cur([("sp_x", "not-json")]), "d", "s") == {}
    assert sc.build_used_by_index(_Cur([("sp_x", None)]), "d", "s") == {}


def test_bridge_redirects_through_merged_chain():
    """codex P2: 대상 테이블 comp 가 이미 병합됐으면 skip 이 아니라 **대표로 redirect**."""
    items = _items([
        ("table", "T1", None), ("table", "T2", None),          # comp0
        ("table", "T3", None), ("table", "T4", None),          # comp1
        ("routine", "spA", ["T1", "T2"]), ("routine", "spA2", ["T1", "T2"]),   # comp2 → comp0
        ("routine", "spB", ["T1", "T2"]), ("routine", "spB2", ["T2", "T1"]),   # comp3 → comp0(체인)
    ])
    out, n = sc._bridge_routine_clusters(items, [[0, 1], [2, 3], [4, 5], [6, 7]], 80, min_frac=0.5)
    assert n == 2, "두 루틴 comp 모두 병합돼야 한다(둘째가 skip 되면 안 된다)"
    big = max(out, key=len)
    assert sorted(big) == [0, 1, 4, 5, 6, 7]


def test_bridge_excludes_cross_schema_refs():
    """codex P2: 다른 DB 의 동명 테이블 참조로는 브릿지가 성립하지 않는다."""
    items = _items([("table", "T_Order", None), ("table", "T_OrderItem", None),
                    ("routine", "sp_X", None), ("routine", "sp_Y", None)])
    for it in items:
        it["schema"] = "db_a"
    # 참조를 전부 다른 DB 로 지정
    items[2]["refs"] = [{"fqn": "db_b.T_Order", "kind": "read"}, {"fqn": "db_b.T_OrderItem", "kind": "read"}]
    items[3]["refs"] = [{"fqn": "db_b.T_Order", "kind": "read"}, {"fqn": "db_b.T_OrderItem", "kind": "read"}]
    out, n = sc._bridge_routine_clusters(items, [[0, 1], [2, 3]], 80, min_frac=0.5)
    assert n == 0 and [sorted(c) for c in out] == [[0, 1], [2, 3]]


def test_embedding_drain_pending_vetoes_both_triggers():
    """codex P1: 드레인 중이면 시간 cadence 로도 재클러스터하지 않는다(밴드·라벨 flap 차단)."""
    class C:
        def __init__(self, pending):
            self.pending = pending

        def execute(self, sql, params=None):
            pass

        def fetchone(self):
            return (1,) if self.pending else None
    assert sc._embedding_drain_pending(C(True), "common", "ds1") is True
    assert sc._embedding_drain_pending(C(False), "common", "ds1") is False

    class Boom:
        def execute(self, *a, **k):
            raise RuntimeError("no table")

        def fetchone(self):
            return None
    assert sc._embedding_drain_pending(Boom(), "c", "d") is False, "예외 → 가드 없이 진행(fail-soft)"


# ── S6: sig-backfill-sweep — 전수 재계산 정체 결함 회귀 잠금 ──────────────────
def _order_clause(src, marker):
    """소스에서 백필 ORDER BY 절을 추출(계약 검사 — 라이브 정체의 유일한 기계적 방어선)."""
    i = src.index(marker)
    return src[i:i + 400]


def test_backfill_order_is_ascending_for_full_sweep():
    """라이브 정체 회귀 잠금: `updated_at DESC` 는 **포맷 전수 재계산에서 영구 정체**를 만든다.

    그 상황에선 hash NULL 행이 없어 1순위가 무력하고, 변환이 `updated_at=now()` 를 전진시키므로
    DESC 는 방금 변환한 행을 다시 맨 앞에 놓아 같은 500행을 무한 재선택한다(실측 2026-07-30:
    루틴 507→545 = +38 정지, 잔여 30,490 도달 불가). ASC 면 변환분이 큐 뒤로 가 단조 sweep 된다."""
    import inspect
    src = inspect.getsource(sc)
    for marker in ("FROM rag_objects WHERE object_type = %s", "FROM routine_objects WHERE routine_name <> ''"):
        assert marker in src
    # 두 백필 경로 모두 ASC
    assert src.count("updated_at ASC NULLS FIRST LIMIT %s") == 2, "테이블·루틴 양 경로 ASC"
    assert "updated_at DESC NULLS LAST LIMIT %s" not in src, "DESC 정체 패턴 잔존 금지"


def test_sig_batch_cap_raised_for_full_sweep():
    """임베딩 용량(실측 51,000건/h)이 남는데 백필 캡이 제한 지점이었다 — 캡 상향을 잠근다."""
    from shared import config as _c
    assert _c.AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS >= 2000
