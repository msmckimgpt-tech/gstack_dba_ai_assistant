"""node_analysis 앵커-상대 관련도 게이팅 순수함수 단위 테스트 (feature-0016 node-analysis-anchor).

DB/AGE 불요 — 토큰화·관련도 채점·후보 게이팅은 전부 순수 함수다. 검증 핵심(사용자 요청 2026-07-01):
  - 재귀가 "원래 분석 대상(루트=anchor)" 기준으로 이루어진다(허브 노드 인접성 아님).
  - 루트 직속 하위 컬럼은 기본 분석(게이트 면제, 최상위 우선순위).
  - 일반 허브 컬럼(예 UniqueID)을 확장할 때 무관/교차-제품 이웃은 재귀에서 탈락(낮은 우선순위).
  - 단순 컬럼명 일치(일반어)·상위객체 무연관은 관련도로 인정 안 함.

실행: conftest.py 가 src 를 path 에 넣어 `from modules import node_analysis` 가능.
"""
from modules import node_analysis as na


# ── 토큰화 ────────────────────────────────────────────────────────────────────
def test_split_tokens_camel_and_snake():
    assert set(na._split_tokens("AchievementUniqueID")) >= {"achievement", "unique", "id"}
    assert set(na._split_tokens("dk_data_release")) >= {"dk", "data", "release"}


def test_meaningful_tokens_drops_generic():
    # UniqueID/CreatedAt 등은 전부 일반어 → 식별력 토큰 없음.
    assert na._meaningful_tokens("UniqueID") == set()
    assert na._meaningful_tokens("CreatedAt") == set()
    # 도메인 명칭은 살아남는다.
    assert "achievement" in na._meaningful_tokens("AchievementReward")


# ── anchor 구성 ───────────────────────────────────────────────────────────────
def _achievement_anchor():
    return na._build_anchor("dk_data_release:dbo.Achievement", "Table", "Achievement",
                            "게임 업적/도전과제 정의 테이블")


def test_build_anchor_fields():
    a = _achievement_anchor()
    assert a["scope"] == "dk_data_release"
    assert a["table_fqn"] == "dbo.Achievement"
    assert "achievement" in a["tokens"]


# ── _relevance 채점 ───────────────────────────────────────────────────────────
def test_relevance_same_table_column_high():
    a = _achievement_anchor()
    n = {"label": "Column", "key": "dk_data_release:dbo.Achievement.RewardItemId",
         "name": "RewardItemId", "fqn": "dbo.Achievement.RewardItemId"}
    # 루트 테이블 서브트리(같은 테이블) → 강한 관련.
    assert na._relevance(n, {"kind": "column"}, a) >= 0.6


def test_relevance_cross_scope_generic_column_filtered():
    a = _achievement_anchor()
    # 다른 제품(scope)의 일반명 컬럼 UniqueID — 단순 명칭 공유. 관련도 매우 낮아야(재귀 탈락).
    n = {"label": "Column", "key": "other_product:dbo.Payment.UniqueID",
         "name": "UniqueID", "fqn": "dbo.Payment.UniqueID"}
    rel = na._relevance(n, {"kind": "reference"}, a)
    assert rel < na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN_DEEP, rel


def test_relevance_name_related_table_passes():
    a = _achievement_anchor()
    n = {"label": "Table", "key": "dk_data_release:dbo.AchievementReward",
         "name": "AchievementReward", "fqn": "dbo.AchievementReward"}
    rel = na._relevance(n, {"kind": "reference"}, a)
    assert rel >= na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN, rel


def test_relevance_same_scope_unrelated_below_deep_threshold():
    a = _achievement_anchor()
    # 같은 제품이지만 무관한 테이블(이름/설명 무겹침) → deep 임계 미만(2-hop 확장 탈락).
    n = {"label": "Table", "key": "dk_data_release:dbo.LoginLog",
         "name": "LoginLog", "fqn": "dbo.LoginLog"}
    rel = na._relevance(n, {"kind": "reference"}, a)
    assert rel < na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN_DEEP, rel


def test_relevance_trusted_but_unrelated_same_scope_excluded():
    """M1: 같은 제품 + 신뢰 REFERENCES 라도 **내용(도메인) 연관 0** 이면 재귀 제외(구조/신뢰만으론 불통과)."""
    a = _achievement_anchor()
    # dbo.LoginLog.SessionId — Achievement 와 이름/설명/테이블 무겹침. 신뢰 엣지로만 연결.
    n = {"label": "Column", "key": "dk_data_release:dbo.LoginLog.SessionId",
         "name": "SessionId", "fqn": "dbo.LoginLog.SessionId"}
    assert na._relevance(n, {"kind": "reference", "status": "trusted", "weight": 0.95}, a) == 0.0


def test_relevance_trusted_boosts_only_when_related():
    """신뢰 부스터는 이미 연관 있는 노드만 강화 — 연관 노드는 신뢰 시 더 높게."""
    a = _achievement_anchor()
    n = {"label": "Table", "key": "dk_data_release:dbo.AchievementReward",
         "name": "AchievementReward", "fqn": "dbo.AchievementReward"}
    base = na._relevance(n, {"kind": "reference"}, a)
    boosted = na._relevance(n, {"kind": "reference", "status": "trusted"}, a)
    assert boosted > base >= na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN


def test_relevance_korean_compound_partial_overlap():
    """M4: 한글 합성어 부분 연관 — 업적(anchor) ⊂ 업적보상(neighbor) 인정."""
    a = na._build_anchor("dk_data_release:dbo.업적", "Table", "업적", "게임 업적 정의")
    n = {"label": "Table", "key": "dk_data_release:dbo.업적보상",
         "name": "업적보상", "fqn": "dbo.업적보상"}
    assert na._relevance(n, {"kind": "reference"}, a) >= na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN


def test_relevance_korean_latin_mixed_token_split():
    """한글↔라틴 경계 분리: 업적Achievement → {업적, achievement}."""
    toks = na._meaningful_tokens("업적Achievement")
    assert "업적" in toks and "achievement" in toks


def test_relevance_glossary_term_same_scope_passes():
    """관련 용어(GlossaryTerm)는 그 자체가 도메인 개념 앵커 → content 인정, 통과."""
    a = _achievement_anchor()
    n = {"label": "GlossaryTerm", "key": "dk_data_release:도전과제", "name": "도전과제", "fqn": "도전과제"}
    assert na._relevance(n, {"kind": "term"}, a) >= na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN


def test_relevance_desc_overlap_contributes():
    """설명 내용 겹침이 관련도에 기여(이름 무겹침이라도 상위객체 컨텐츠 연관)."""
    a = _achievement_anchor()   # desc_tokens 에 '업적'/'도전과제'
    n = {"label": "Table", "key": "dk_data_release:dbo.RewardBox", "name": "RewardBox",
         "fqn": "dbo.RewardBox", "description": "업적 도전과제 보상 상자 정의"}
    rel = na._relevance(n, {"kind": "reference"}, a)
    assert rel >= na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN


def test_deep_threshold_scales_with_depth():
    """M3: 이웃 depth 가 깊을수록 임계 상향 — 얕은 통과 노드가 더 깊은 확장에선 탈락할 수 있음."""
    a = _achievement_anchor()
    # 관련도 ~0.38 인 노드(AchievementReward, 이름겹침 0.30 + scope 0.08).
    related = {"label": "Table", "key": "dk_data_release:dbo.AchievementReward",
               "name": "AchievementReward", "fqn": "dbo.AchievementReward"}
    ctx = {"neighbors": [related], "neighbor_meta": {related["key"]: {"kind": "reference"}}}
    # depth1(→ neighbor depth2, 임계 0.34): 통과.
    assert [n["key"] for _, n, _s in na._score_candidates(ctx, cur_depth=1, anchor=a)] == [related["key"]]
    # depth4(→ neighbor depth5, 임계 0.34+0.06*3=0.52): 0.38 < 0.52 → 탈락.
    assert na._score_candidates(ctx, cur_depth=4, anchor=a) == []


def test_score_candidates_child_tiebreak_by_ordinal_deterministic():
    """M5: 동점(하위 컬럼 1.0)은 ordinal→name 결정적 정렬 → 예산 절단 재현성."""
    a = _achievement_anchor()
    c2 = {"label": "Column", "key": "dk_data_release:dbo.Achievement.B", "name": "B",
          "fqn": "dbo.Achievement.B", "ordinal": 2}
    c1 = {"label": "Column", "key": "dk_data_release:dbo.Achievement.A", "name": "A",
          "fqn": "dbo.Achievement.A", "ordinal": 1}
    ctx = {"neighbors": [c2, c1],
           "neighbor_meta": {c2["key"]: {"kind": "column", "child": True},
                             c1["key"]: {"kind": "column", "child": True}}}
    ordered = [n["key"] for _, n, _s in na._score_candidates(ctx, cur_depth=0, anchor=a)]
    assert ordered == [c1["key"], c2["key"]]   # ordinal 1 먼저


def test_relevance_schema_hub_zero():
    a = _achievement_anchor()
    n = {"label": "Schema", "key": "dk_data_release:dbo", "name": "dbo", "fqn": "dbo"}
    assert na._relevance(n, {"kind": "structural"}, a) == 0.0


def test_relevance_broken_edge_zero():
    a = _achievement_anchor()
    n = {"label": "Column", "key": "dk_data_release:dbo.AchievementReward.ItemId",
         "name": "ItemId", "fqn": "dbo.AchievementReward.ItemId"}
    assert na._relevance(n, {"kind": "reference", "status": "broken"}, a) == 0.0


# ── _score_candidates 게이팅 ──────────────────────────────────────────────────
def test_root_depth0_child_columns_always_pass_incl_generic():
    """depth 0: 루트 직속 컬럼은 일반명(UniqueID)이라도 무조건 통과(=하위 컬럼 기본 분석) + 최상위 우선순위."""
    a = _achievement_anchor()
    generic_child = {"label": "Column", "key": "dk_data_release:dbo.Achievement.UniqueID",
                     "name": "UniqueID", "fqn": "dbo.Achievement.UniqueID"}
    named_child = {"label": "Column", "key": "dk_data_release:dbo.Achievement.RewardItemId",
                   "name": "RewardItemId", "fqn": "dbo.Achievement.RewardItemId"}
    schema = {"label": "Schema", "key": "dk_data_release:dbo", "name": "dbo", "fqn": "dbo"}
    ctx = {
        "neighbors": [generic_child, named_child, schema],
        "neighbor_meta": {
            generic_child["key"]: {"kind": "column", "child": True},
            named_child["key"]: {"kind": "column", "child": True},
            schema["key"]: {"kind": "structural", "child": False},
        },
    }
    kept = na._score_candidates(ctx, cur_depth=0, anchor=a)
    keys = [n["key"] for _, n, _s in kept]
    assert generic_child["key"] in keys       # 일반명이라도 루트 하위 컬럼 → 분석
    assert named_child["key"] in keys
    assert schema["key"] not in keys           # Schema 허브는 확장 제외
    # child 컬럼은 relevance 1.0(최상위).
    rels = {n["key"]: rel for rel, n, _s in kept}
    assert rels[generic_child["key"]] == 1.0


def test_hub_column_depth1_filters_unrelated_fanout():
    """depth 1: 일반 허브 컬럼(UniqueID) 확장 시 무관/교차-제품 이웃은 탈락, 관련 이웃만 관련도순 유지.

    이것이 사용자가 관찰한 'UniqueID 를 기준으로 다시 탐색' 증상의 핵심 차단 지점.
    """
    a = _achievement_anchor()
    cross = {"label": "Column", "key": "other_product:dbo.Payment.UniqueID",
             "name": "UniqueID", "fqn": "dbo.Payment.UniqueID"}
    unrelated = {"label": "Column", "key": "dk_data_release:dbo.LoginLog.UniqueID",
                 "name": "UniqueID", "fqn": "dbo.LoginLog.UniqueID"}
    related = {"label": "Table", "key": "dk_data_release:dbo.AchievementReward",
               "name": "AchievementReward", "fqn": "dbo.AchievementReward"}
    ctx = {
        "neighbors": [cross, unrelated, related],
        "neighbor_meta": {
            cross["key"]: {"kind": "reference"},
            unrelated["key"]: {"kind": "reference"},
            related["key"]: {"kind": "reference"},
        },
    }
    kept = na._score_candidates(ctx, cur_depth=1, anchor=a)
    keys = [n["key"] for _, n, _s in kept]
    assert related["key"] in keys              # Achievement 연관 → 재귀 유지
    assert cross["key"] not in keys            # 교차-제품 일반명 → 탈락
    assert unrelated["key"] not in keys        # 같은 제품이라도 무관 일반명 → 탈락
    assert keys == [related["key"]]            # 관련도순, 관련 이웃만


def test_score_candidates_null_anchor_conservative():
    """앵커 로드 실패(anchor=None) → 하위 컬럼만 통과, 나머지 fan-out 억제(안전 저하)."""
    child = {"label": "Column", "key": "dk_data_release:dbo.Achievement.RewardId",
             "name": "RewardId", "fqn": "dbo.Achievement.RewardId"}
    other = {"label": "Table", "key": "dk_data_release:dbo.AchievementReward",
             "name": "AchievementReward", "fqn": "dbo.AchievementReward"}
    ctx = {
        "neighbors": [child, other],
        "neighbor_meta": {child["key"]: {"kind": "column", "child": True},
                          other["key"]: {"kind": "reference"}},
    }
    kept = na._score_candidates(ctx, cur_depth=0, anchor=None)
    keys = [n["key"] for _, n, _s in kept]
    assert child["key"] in keys
    assert other["key"] not in keys


# ── 재검증(2라운드) 반영 회귀 ────────────────────────────────────────────────
def test_korean_generic_desc_only_overlap_excluded():
    """MAJOR(2라운드): 한글 일반어(게임/정의/테이블)만 겹치는 무관 노드는 desc booster 로도 통과 못 함."""
    a = _achievement_anchor()   # desc '게임 업적/도전과제 정의 테이블'
    # 무기(weapon)는 Achievement 와 도메인 무관. 공유는 게임/정의/테이블 = 전부 한글 일반어.
    n = {"label": "Table", "key": "dk_data_release:dbo.WeaponMaster", "name": "WeaponMaster",
         "fqn": "dbo.WeaponMaster", "description": "게임 무기 정의 테이블"}
    assert na._relevance(n, {"kind": "reference"}, a) < na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN


def test_korean_generic_tokens_stripped():
    assert na._meaningful_tokens("게임 정의 테이블 상태 코드") == set()
    assert "업적" in na._meaningful_tokens("업적 정의")


def test_hangul_partial_overlap_medial_rejected():
    """MINOR(2라운드): 중간삽입 부분문자열은 오연관 → 접두/접미만 인정."""
    a = na._build_anchor("dk_data_release:dbo.업적", "Table", "업적", "")
    # 기업적자(corporate deficit) 안에 업적 이 중간삽입 — 무관.
    medial = {"label": "Table", "key": "dk_data_release:dbo.기업적자", "name": "기업적자", "fqn": "dbo.기업적자"}
    assert na._relevance(medial, {"kind": "reference"}, a) == 0.0
    # 업적보상(prefix) 은 인정.
    prefix = {"label": "Table", "key": "dk_data_release:dbo.업적보상", "name": "업적보상", "fqn": "dbo.업적보상"}
    assert na._relevance(prefix, {"kind": "reference"}, a) >= na._cfg.AGENT_NODE_ANALYSIS_RELEVANCE_MIN


def test_hangul_partial_overlap_opposite_meaning_rejected():
    """회원(member) ⊄ 비회원구매(non-member) — 중간삽입 반대의미 오매칭 차단."""
    a = na._build_anchor("dk_data_release:dbo.회원", "Table", "회원", "")
    n = {"label": "Table", "key": "dk_data_release:dbo.비회원구매", "name": "비회원구매", "fqn": "dbo.비회원구매"}
    assert na._relevance(n, {"kind": "reference"}, a) == 0.0


def test_trusted_related_passes_at_depth1_via_booster():
    """신뢰 부스터는 이미 연관 있는 FK 대상을 depth1 에서 통과시킨다(_score_candidates 경로)."""
    a = _achievement_anchor()
    related = {"label": "Table", "key": "dk_data_release:dbo.AchievementReward",
               "name": "AchievementReward", "fqn": "dbo.AchievementReward"}
    ctx = {"neighbors": [related],
           "neighbor_meta": {related["key"]: {"kind": "reference", "status": "trusted"}}}
    kept = na._score_candidates(ctx, cur_depth=1, anchor=a)
    assert [n["key"] for _, n, _s in kept] == [related["key"]]


def test_trusted_unrelated_excluded_at_depth1_tradeoff():
    """의도된 precision 트레이드오프: 신뢰 FK 라도 내용 무연관이면 depth1 에서 제외(사용자 요구)."""
    a = _achievement_anchor()
    unrel = {"label": "Column", "key": "dk_data_release:dbo.LoginLog.SessionId",
             "name": "SessionId", "fqn": "dbo.LoginLog.SessionId"}
    ctx = {"neighbors": [unrel],
           "neighbor_meta": {unrel["key"]: {"kind": "reference", "status": "trusted", "weight": 0.95}}}
    assert na._score_candidates(ctx, cur_depth=1, anchor=a) == []


def test_depth_ramp_boundary_nd3_pinned():
    """M3 ramp 상수 회귀 고정: rel~0.38 노드가 neighbor_depth 3(임계 0.40)에서 탈락."""
    a = _achievement_anchor()
    related = {"label": "Table", "key": "dk_data_release:dbo.AchievementReward",
               "name": "AchievementReward", "fqn": "dbo.AchievementReward"}
    ctx = {"neighbors": [related], "neighbor_meta": {related["key"]: {"kind": "reference"}}}
    assert [n["key"] for _, n, _s in na._score_candidates(ctx, cur_depth=1, anchor=a)] == [related["key"]]  # nd2=0.34
    assert na._score_candidates(ctx, cur_depth=2, anchor=a) == []   # nd3=0.40 > 0.38


def test_tiebreak_same_name_distinct_key_deterministic():
    """M5(2라운드): 동명·동점·ordinal 무 → key 로 전순서 결정(입력순 비의존)."""
    a = _achievement_anchor()
    n1 = {"label": "Table", "key": "dk_data_release:s1.AchievementReward",
          "name": "AchievementReward", "fqn": "s1.AchievementReward"}
    n2 = {"label": "Table", "key": "dk_data_release:s2.AchievementReward",
          "name": "AchievementReward", "fqn": "s2.AchievementReward"}
    mk = lambda order: {"neighbors": order,
                        "neighbor_meta": {n1["key"]: {"kind": "reference"},
                                          n2["key"]: {"kind": "reference"}}}
    a1 = [n["key"] for _, n, _s in na._score_candidates(mk([n1, n2]), cur_depth=1, anchor=a)]
    a2 = [n["key"] for _, n, _s in na._score_candidates(mk([n2, n1]), cur_depth=1, anchor=a)]
    assert a1 == a2 == [n1["key"], n2["key"]]   # 입력 순서 뒤집어도 동일(key 오름차순)


if __name__ == "__main__":   # standalone 실행(pytest 미사용 환경)
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fail = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            fail += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - fail}/{len(fns)} passed")
    sys.exit(1 if fail else 0)
