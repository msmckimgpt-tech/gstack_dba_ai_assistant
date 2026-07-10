"""feature-0002 insight-table-grouping — 동일구조 테이블 그룹화 단위 테스트.

사용자 결정(2026-07-03): insight-worker 가 날짜/번호 suffix 만 다른 동일구조 샤드
(daily_league_ranking_1_20250727, _20250726 …)를 각각 개별 LLM 분석하던 낭비를 제거한다.
그룹 키 = (base_stem, column-fingerprint) — 대표 1개만 LLM, 형제는 LLM 없이 전파.

본 파일은 그룹화 결정의 **순수 로직**(테이블명 stem 추출·그룹 서명·KV 상속 키)을 회귀 가드한다.
발행/전파(_publish_table_insight)는 기존 발행 경로를 verbatim 재사용하므로 여기서는 대상 아님
(test_task0305 fingerprint 계열과 동형 — 실 DB 없이 pure fn + in-memory KV monkeypatch).
"""
from __future__ import annotations

import json


# ── base stem 추출 ───────────────────────────────────────────────────────────
def test_base_stem_strips_date_suffix():
    """후행 날짜(YYYYMMDD)와 그 앞 번호 파티션을 반복 제거해 base stem 을 얻는다."""
    import modules.insight as insight

    assert insight._table_base_stem("daily_league_ranking_1_20250727") == "daily_league_ranking"
    assert insight._table_base_stem("daily_league_ranking_1_20250726") == "daily_league_ranking"
    assert insight._table_base_stem("DayuPoint_20260211") == "DayuPoint"
    assert insight._table_base_stem("Stat_ActiveUser_Again_20120918") == "Stat_ActiveUser_Again"


def test_base_stem_strips_backup_then_date():
    """백업 마커(_bk)를 먼저 벗기고 이어서 날짜를 벗긴다(반복 strip)."""
    import modules.insight as insight

    assert insight._table_base_stem("DayuPoint_20230801_bk") == "DayuPoint"
    assert insight._table_base_stem("orders_20240101_backup") == "orders"


def test_base_stem_preserves_plain_and_undated_names():
    """suffix 없는 이름은 원본 그대로 — 그룹 오합침 방지."""
    import modules.insight as insight

    assert insight._table_base_stem("orders") == "orders"
    assert insight._table_base_stem("Stat_ActiveUser_Again") == "Stat_ActiveUser_Again"
    assert insight._table_base_stem("Stat_ActiveUser") == "Stat_ActiveUser"


def test_base_stem_keeps_min_two_chars():
    """base 가 2글자 미만이 되는 strip 은 하지 않는다(t1 은 그대로 → 병합 안 됨)."""
    import modules.insight as insight

    assert insight._table_base_stem("t1") == "t1"
    assert insight._table_base_stem("ab") == "ab"
    # 순수 숫자열 이름은 strip 대상이 start<2 라 원본 유지.
    assert insight._table_base_stem("20250727") == "20250727"


def test_base_stem_blank():
    import modules.insight as insight

    assert insight._table_base_stem("") == ""
    assert insight._table_base_stem(None) == ""


# ── 그룹 서명 (base_stem, fingerprint) ───────────────────────────────────────
def test_group_sig_requires_fp_and_stem():
    """fp 부재 또는 stem<2 이면 None(그룹 제외 — pure LLM 경로)."""
    import modules.insight as insight

    fps = {"orders_20240101": "FP1", "no_fp_table": "", "x1": "FP2"}
    assert insight._table_group_sig("orders_20240101", fps) == ("orders", "FP1")
    assert insight._table_group_sig("no_fp_table", fps) is None          # fp 없음
    assert insight._table_group_sig("missing", fps) is None              # fp 맵에 없음


def test_build_groups_same_structure_grouped():
    """동일 fp + 동일 base_stem 날짜 샤드들이 한 그룹으로 묶인다(정렬된 멤버)."""
    import modules.insight as insight

    fps = {
        "daily_league_ranking_1_20250727": "A",
        "daily_league_ranking_1_20250726": "A",
        "daily_league_ranking_1_20250725": "A",
    }
    sig_of, members_of = insight._build_table_groups(list(fps), fps)
    sig = ("daily_league_ranking", "A")
    assert sig_of["daily_league_ranking_1_20250727"] == sig
    assert members_of[sig] == [
        "daily_league_ranking_1_20250725",
        "daily_league_ranking_1_20250726",
        "daily_league_ranking_1_20250727",
    ]


def test_build_groups_different_fingerprint_not_merged():
    """같은 이름-family 라도 구조(fp)가 다르면 별개 그룹 — 구조 가드."""
    import modules.insight as insight

    fps = {"tbl_20250101": "A", "tbl_20250102": "B"}
    sig_of, members_of = insight._build_table_groups(list(fps), fps)
    assert sig_of["tbl_20250101"] == ("tbl", "A")
    assert sig_of["tbl_20250102"] == ("tbl", "B")
    assert members_of[("tbl", "A")] == ["tbl_20250101"]
    assert members_of[("tbl", "B")] == ["tbl_20250102"]


def test_build_groups_different_stem_same_fp_not_merged():
    """구조(fp)가 우연히 같아도 이름-family(base_stem)가 다르면 병합 안 함 — 도메인 오합침 방지."""
    import modules.insight as insight

    fps = {"daily_ranking_20250101": "SAME", "payment_log_20250101": "SAME"}
    sig_of, members_of = insight._build_table_groups(list(fps), fps)
    assert sig_of["daily_ranking_20250101"] == ("daily_ranking", "SAME")
    assert sig_of["payment_log_20250101"] == ("payment_log", "SAME")
    assert len(members_of) == 2


def test_build_groups_skips_missing_fp():
    """fp 없는 테이블은 sig_of/members_of 에서 제외(그룹 참여 안 함)."""
    import modules.insight as insight

    fps = {"a_20250101": "A", "b_no_fp": ""}
    sig_of, members_of = insight._build_table_groups(["a_20250101", "b_no_fp"], fps)
    assert "b_no_fp" not in sig_of
    assert ("b_no_fp", "") not in members_of


# ── 그룹 인사이트 KV 상속 키 ─────────────────────────────────────────────────
def test_group_insight_kv_key_stable_and_fp_scoped():
    """같은 sig 는 같은 키, fp 가 바뀌면 키가 바뀐다(구조 변경 시 자기 무효화)."""
    import modules.insight as insight

    k1 = insight._group_insight_kv_key(("daily_league_ranking", "FP_OLD"))
    k1b = insight._group_insight_kv_key(("daily_league_ranking", "FP_OLD"))
    k2 = insight._group_insight_kv_key(("daily_league_ranking", "FP_NEW"))
    assert k1 == k1b
    assert k1 != k2
    assert k1.startswith("table_group_insight:")


def test_group_insight_kv_roundtrip(monkeypatch):
    """대표 분석 dict 를 KV 에 저장하면 다음 cycle 이 그대로 상속(LLM 없이)."""
    import modules.insight as insight

    store: dict = {}

    def _fake_save(conn, conv, key, value):
        store[(conv, key)] = value

    def _fake_load(conn, conv, key):
        return store.get((conv, key))

    monkeypatch.setattr(insight, "save_memory_kv", _fake_save)
    monkeypatch.setattr(insight, "load_memory_kv", _fake_load)

    sig = ("daily_league_ranking", "A")
    insight_dict = {"domain": "랭킹", "summary": "일별 리그 랭킹", "usage": "조회", "key_columns": ["rank"]}
    insight._save_group_insight_kv(object(), sig, insight_dict)
    loaded = insight._load_group_insight_kv(object(), sig)
    assert loaded == insight_dict
    # 저장된 값은 JSON 직렬화 — 한글 보존(ensure_ascii=False).
    raw = store[(insight.GLOBAL_CONVERSATION_ID, insight._group_insight_kv_key(sig))]
    assert json.loads(raw)["summary"] == "일별 리그 랭킹"


def test_group_insight_kv_missing_returns_none(monkeypatch):
    """저장된 적 없는 그룹은 None → 대표 LLM 분석 경로로 폴백."""
    import modules.insight as insight

    monkeypatch.setattr(insight, "load_memory_kv", lambda conn, conv, key: None)
    assert insight._load_group_insight_kv(object(), ("x_ranking", "A")) is None
    # sig None(그룹 아님)도 None.
    assert insight._load_group_insight_kv(object(), None) is None


def test_save_group_insight_kv_ignores_non_dict(monkeypatch):
    """비-dict/None sig 저장은 무시(no-op) — 방어."""
    import modules.insight as insight

    called = {"n": 0}

    def _fake_save(conn, conv, key, value):
        called["n"] += 1

    monkeypatch.setattr(insight, "save_memory_kv", _fake_save)
    insight._save_group_insight_kv(object(), ("s", "fp"), "not-a-dict")
    insight._save_group_insight_kv(object(), None, {"a": 1})
    assert called["n"] == 0


# ── 리뷰 P2: malformed key_columns 로 인한 스캔 abort 방어 ─────────────────────
def test_format_table_insight_survives_non_sequence_key_columns():
    """LLM 이 key_columns 를 int/str 등 비-시퀀스로 반환해도 TypeError 없이 렌더 — 스캔 abort/wedge 차단."""
    import modules.utils as u

    # int → 무시(list 화), col_names 폴백으로 key columns 채움. crash 안 함.
    out = u._format_table_insight_text("s", "daily_x_20250101",
                                       {"summary": "S", "key_columns": 5}, col_names=["a", "b"])
    assert "S" in out and "TypeError" not in out
    # str → 문자단위 순회 금지(시퀀스 미인정) → 폴백.
    out2 = u._format_table_insight_text("s", "t", {"summary": "S2", "key_columns": "abc"},
                                        col_names=["c1"])
    assert "S2" in out2
    # None → 기존 동작(빈 key_cols).
    assert isinstance(u._format_table_insight_text("s", "t", {"summary": "S3", "key_columns": None}), str)


def test_format_schema_insight_survives_non_sequence_key_columns():
    """스키마 인사이트 포매터도 동일 방어(insight-worker 스키마 스캔 경로)."""
    import modules.utils as u

    out = u._format_schema_insight_text("s", {"summary": "SCH", "key_columns": 7})
    assert "SCH" in out
