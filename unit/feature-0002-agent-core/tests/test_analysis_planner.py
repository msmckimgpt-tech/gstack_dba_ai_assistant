"""feature-0035-analysis-planner — 결정적 우선순위 선정 단위 테스트.

검증 축:
  A(결정성): 같은 입력 → 같은 순서. tie-break 가 없으면 tick 마다 다른 테이블이 뽑혀 어떤
    테이블은 영영 분석되지 않고 어떤 테이블은 반복 시드된다.
  B(신호): 대화 조인 이력이 관계 차수보다 강하다. 미분석만 대상.
  C(스키마 축): `object_key` prefix 로 맞춘다 — MSSQL 은 schema_name 이 'dbo' 라 DB 차원이 소실.
    LIKE 대신 strpos(식별자의 `_` 가 와일드카드로 해석되면 다른 스키마가 섞인다).
  D(안전): 큐잉을 자체 구현하지 않고 검증된 경로를 쓴다. 전 구간 fail-soft.
"""
import pathlib

import pytest

from modules import analysis_planner as ap

_INSIGHT = pathlib.Path(__file__).resolve().parents[1] / "src" / "modules" / "insight.py"


class _Cur:
    def __init__(self, tables=None, signals=None):
        self.calls = []
        self._tables = tables if tables is not None else [("t_alpha",), ("t_beta",)]
        self._signals = signals if signals is not None else []
        self._last = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "FROM rag_objects" in sql:
            self._last = self._tables
        elif "table_relationships" in sql:
            self._last = self._signals
        else:
            self._last = []

    def fetchall(self):
        return self._last

    def close(self):
        pass


# ── A: 결정성 ───────────────────────────────────────────────────────────────
def test_ranking_is_deterministic_on_ties():
    """동점은 이름 오름차순으로 가른다 — tie-break 가 없으면 같은 상황에서 매번 다른 테이블이
    뽑혀 커버리지가 고르게 차지 않는다."""
    tables = ["zeta", "alpha", "mid"]
    first = ap.rank_targets(tables, {}, 3)
    second = ap.rank_targets(list(reversed(tables)), {}, 3)
    assert first == second == [("alpha", 0), ("mid", 0), ("zeta", 0)]


def test_ranking_respects_limit():
    assert len(ap.rank_targets([f"t{i}" for i in range(10)], {}, 3)) == 3
    assert ap.rank_targets(["a"], {}, 0) == []


def test_ranking_handles_empty_input():
    assert ap.rank_targets([], {}, 5) == []
    assert ap.rank_targets(None, {}, 5) == []


# ── B: 신호 ─────────────────────────────────────────────────────────────────
def test_conversation_history_outweighs_degree():
    """사람이 실제 질문에서 조인해 쓴 테이블이 가장 중요하다 — 단순 허브보다 우선한다."""
    signals = {"hub": (30, 0), "used": (1, 1)}
    ranked = ap.rank_targets(["hub", "used"], signals, 2)
    assert ranked[0][0] == "used", "대화 이력이 차수에 밀렸다"


def test_degree_orders_when_no_conversation_history():
    signals = {"big": (10, 0), "small": (2, 0)}
    assert ap.rank_targets(["small", "big"], signals, 2)[0][0] == "big"


def test_score_is_case_insensitive():
    """`table_relationships` 는 lower() 로 집계하고 `rag_objects.table_name` 은 원형이다."""
    assert ap.score("CharacterItem", {"characteritem": (4, 1)}) > 0


def test_unknown_table_scores_zero():
    assert ap.score("unknown", {"other": (5, 5)}) == 0


def test_signals_count_both_directions():
    """참조하는 쪽도 참조당하는 쪽도 그만큼 맥락에 얽혀 있다."""
    cur = _Cur(signals=[("a", 3, 1)])
    out = ap.relationship_signals(cur, "ds1")
    sql, _p = cur.calls[0]
    assert "source_table" in sql and "target_table" in sql and "UNION ALL" in sql
    assert out["a"] == (3, 1)


def test_conversation_edges_are_counted_separately():
    cur = _Cur(signals=[])
    ap.relationship_signals(cur, "ds1")
    sql, _p = cur.calls[0]
    assert "FILTER (WHERE src = 'conversation')" in sql


# ── C: 스키마 축 ────────────────────────────────────────────────────────────
def test_candidate_query_uses_object_key_prefix_not_schema_name():
    """MSSQL 은 `rag_objects.schema_name` 이 리터럴 'dbo' 라 DB 차원이 소실된다 —
    그것으로 필터하면 한 건도 안 맞는다."""
    cur = _Cur()
    ap.unanalyzed_tables(cur, "ds1", "mydb")
    sql, params = cur.calls[0]
    assert "object_key" in sql and "schema_name" not in sql
    assert "ds1:mydb." in params


def test_candidate_query_avoids_like_wildcards():
    """식별자에 `_` 가 흔한데(`dk_data_release`) LIKE 는 그것을 '임의의 1문자'로 해석해
    다른 스키마의 테이블이 섞인다."""
    cur = _Cur()
    ap.unanalyzed_tables(cur, "dk_ds", "dk_data_release")
    sql, _p = cur.calls[0]
    assert "strpos(o.object_key" in sql and "LIKE" not in sql.upper()


def test_candidate_query_excludes_already_analyzed():
    cur = _Cur()
    ap.unanalyzed_tables(cur, "ds1", "mydb")
    sql, _p = cur.calls[0]
    assert "NOT EXISTS" in sql and "status = 'done'" in sql


def test_candidate_query_is_capped():
    cur = _Cur()
    ap.unanalyzed_tables(cur, "ds1", "mydb")
    _sql, params = cur.calls[0]
    assert ap._CANDIDATE_CAP in params


def test_selected_keys_match_the_node_key_format():
    """반환 키는 `enqueue_change_analysis` 가 받는 시드 키와 같은 형식이어야 한다."""
    cur = _Cur(tables=[("Orders",)], signals=[("orders", 2, 1)])
    keys = ap.select_priority_targets(cur, "ds1", "mydb", 5)
    assert keys == ["ds1:mydb.Orders"]


def test_selection_prioritises_by_signal(monkeypatch):
    cur = _Cur(tables=[("hub",), ("used",), ("cold",)],
               signals=[("hub", 30, 0), ("used", 1, 1)])
    keys = ap.select_priority_targets(cur, "ds1", "mydb", 3)
    assert keys[0].endswith(".used") and keys[-1].endswith(".cold")


# ── D: 안전 ─────────────────────────────────────────────────────────────────
def test_selection_is_failsoft_on_query_error():
    class _Boom(_Cur):
        def execute(self, sql, params=None):
            raise RuntimeError("pg down")

    assert ap.select_priority_targets(_Boom(), "ds1", "mydb", 5) == []


def test_selection_short_circuits_on_bad_input():
    cur = _Cur()
    assert ap.select_priority_targets(cur, "", "mydb", 5) == []
    assert ap.select_priority_targets(cur, "ds1", "", 5) == []
    assert ap.select_priority_targets(cur, "ds1", "mydb", 0) == []
    assert cur.calls == []


def test_no_candidates_skips_signal_query():
    cur = _Cur(tables=[])
    assert ap.select_priority_targets(cur, "ds1", "mydb", 5) == []
    assert not any("table_relationships" in c[0] for c in cur.calls)


def test_disabled_switch_defaults_off_without_config(monkeypatch):
    """설정을 읽을 수 없으면 비활성 — 자동 LLM 지출은 모르면 하지 않는 쪽이 안전하다."""
    monkeypatch.setattr(ap, "enabled", ap.enabled)
    import shared.runtime_settings as rts
    monkeypatch.setattr(rts, "get_int", lambda k: (_ for _ in ()).throw(RuntimeError("no cfg")))
    import shared.config as cfg
    monkeypatch.delattr(cfg, "AGENT_ANALYSIS_COVERAGE_SEEDS", raising=False)
    assert ap.enabled() is False


def test_seed_limit_is_zero_when_unreadable(monkeypatch):
    import shared.runtime_settings as rts
    monkeypatch.setattr(rts, "get_int", lambda k: (_ for _ in ()).throw(RuntimeError("no cfg")))
    import shared.config as cfg
    monkeypatch.delattr(cfg, "AGENT_ANALYSIS_COVERAGE_SEED_CAP", raising=False)
    assert ap.seed_limit() == 0


# ── D: 배선 (큐잉을 재구현하지 않는다) ───────────────────────────────────────
def test_insight_seeds_through_the_verified_queue_path():
    """자체 큐잉을 만들면 자격·cap·쿨다운·busy 가드가 두 벌이 되어 서로를 모른다."""
    src = _INSIGHT.read_text(encoding="utf-8")
    idx = src.index("def _seed_coverage_targets")
    body = src[idx:idx + 2500]
    assert "enqueue_change_analysis" in body
    assert 'reason="coverage_priority"' in body


def test_insight_seeds_only_when_no_structural_change():
    """구조 변경이 더 급하다 — 같은 사이클에 둘 다 시드하면 자동 run 이 겹친다."""
    src = _INSIGHT.read_text(encoding="utf-8")
    idx = src.index("_seed_coverage_targets(scope_key")
    assert "else:" in src[max(0, idx - 700):idx]


def test_insight_coverage_seed_is_failsoft():
    src = _INSIGHT.read_text(encoding="utf-8")
    idx = src.index("def _seed_coverage_targets")
    body = src[idx:idx + 2500]
    assert "except Exception" in body


def test_insight_closes_its_readonly_connection():
    src = _INSIGHT.read_text(encoding="utf-8")
    idx = src.index("def _seed_coverage_targets")
    body = src[idx:idx + 2500]
    assert "conn.close()" in body and "cur.close()" in body


# ── codex 리뷰 회귀 방지 ─────────────────────────────────────────────────────
def test_candidate_query_deduplicates():
    """`rag_objects` 유니크 키에 conversation_id 가 포함돼 같은 테이블이 여러 행일 수 있다.
    중복을 두면 상한 3이 "Orders, Orders, Orders" 가 되어 **한 테이블만** 시드된다(codex P1)."""
    cur = _Cur()
    ap.unanalyzed_tables(cur, "ds1", "mydb")
    sql, _p = cur.calls[0]
    assert "SELECT DISTINCT" in sql


def test_insight_applies_a_cycle_wide_cap():
    """스키마 루프 안에서 시드하므로 큐잉 경로의 스키마 단위 cap·쿨다운만으로는 총량이
    스키마 수만큼 곱해진다(codex). 사이클 전역 상한이 잔여를 계산해 넘겨야 한다."""
    src = _INSIGHT.read_text(encoding="utf-8")
    idx = src.index("def _seed_coverage_targets")
    body = src[idx:idx + 3000]
    assert "cycle_limit()" in body
    assert "coverage_seeded" in body and "remaining" in body


def test_cycle_limit_is_zero_when_unreadable(monkeypatch):
    import shared.runtime_settings as rts
    monkeypatch.setattr(rts, "get_int", lambda k: (_ for _ in ()).throw(RuntimeError("no cfg")))
    import shared.config as cfg
    monkeypatch.delattr(cfg, "AGENT_ANALYSIS_COVERAGE_CYCLE_CAP", raising=False)
    assert ap.cycle_limit() == 0


def test_cycle_cap_default_bounds_per_schema_cap():
    """사이클 상한은 스키마당 상한보다 커야 의미가 있고, 무한이면 안 된다."""
    from shared import config as cfg
    assert cfg.AGENT_ANALYSIS_COVERAGE_CYCLE_CAP >= cfg.AGENT_ANALYSIS_COVERAGE_SEED_CAP
    assert cfg.AGENT_ANALYSIS_COVERAGE_CYCLE_CAP > 0


# ── 파티션 계열 축약 (라이브 실측 후속) ──────────────────────────────────────
def test_partition_base_strips_date_suffix():
    assert ap.partition_base("daily_league_ranking_20240425") == "daily_league_ranking"
    assert ap.partition_base("stat_202404") == "stat"


def test_partition_base_strips_only_one_suffix():
    """반복 제거를 하면 `foo_2024_2025` 가 `foo` 까지 깎여 **독립 테이블 `foo_2024`·`foo_2025`
    가 한 계열로 합쳐진다**(codex P1). 잘못 합치면 실제 테이블이 영영 분석되지 않으므로,
    덜 깎아 계열이 잘게 나뉘는 쪽이 안전한 실패 방향이다."""
    assert ap.partition_base("daily_league_ranking_1_20240425") == "daily_league_ranking_1"
    assert ap.partition_base("foo_2024_2025") == "foo_2024"


def test_collapse_representative_is_highest_scoring():
    """계열 안에 대화 조인 이력이 있는 파티션이 있으면 그것이 대표여야 한다 — 사전순으로
    고르면 **그 신호가 통째로 버려진다**(codex P1)."""
    tables = ["log_202401", "log_202402", "log_202403"]
    signals = {"log_202402": (1, 1)}          # 대화 이력 보유
    assert ap.collapse_partitions(tables, signals) == ["log_202402"]


def test_collapse_representative_falls_back_to_name_order_on_tie():
    tables = ["log_202403", "log_202401", "log_202402"]
    assert ap.collapse_partitions(tables, {}) == ["log_202401"]


def test_partition_base_keeps_legitimate_names():
    """3자리 이하 숫자는 정당한 이름일 수 있다 — 건드리지 않는다."""
    for name in ("item2", "log_01", "tf_log_05_item", "characteritem", "t_586"):
        assert ap.partition_base(name) == name, name


def test_collapse_keeps_one_representative_per_series():
    """라이브 실측: 어떤 datasource 는 테이블의 93%가 날짜 접미 파티션이다. 축약이 없으면
    같은 구조의 파티션 수백 개를 반복 분석하며 토큰만 태운다."""
    tables = [f"daily_rank_2024{d:02d}" for d in range(1, 13)] + ["members", "guild"]
    out = ap.collapse_partitions(tables)
    assert sorted(out) == ["daily_rank_202401", "guild", "members"]


def test_collapse_is_deterministic():
    tables = ["log_20240301", "log_20240102", "log_20240205"]
    assert ap.collapse_partitions(tables) == ap.collapse_partitions(list(reversed(tables)))
    assert ap.collapse_partitions(tables) == ["log_20240102"]


def test_collapse_handles_empty_and_none():
    assert ap.collapse_partitions([]) == []
    assert ap.collapse_partitions(None) == []


def test_selection_collapses_partitions_before_ranking():
    """선정 경로가 실제로 축약을 거치는지 — 함수만 있고 배선이 없으면 무용지물이다."""
    rows = [(f"daily_rank_2024{d:02d}",) for d in range(1, 13)] + [("members",)]
    cur = _Cur(tables=rows, signals=[])
    keys = ap.select_priority_targets(cur, "ds1", "mydb", 5)
    names = [k.split(".")[-1] for k in keys]
    assert len([n for n in names if n.startswith("daily_rank")]) == 1, names
    assert "members" in names
