"""부하게이트 자기교정 봉인 — LIMIT 상한 보정 + 실행계획 진단 코칭 (conv-audit).

friction: `FR-loadgate-blind-coaching` — 라이브 대화(2026-07-31)에서 부하게이트가 한 대화에서
6연속 차단해 추론이 정체됐다. 실측으로 두 근본이 갈렸다:

  RC-1 (L2 거부 피드백): 차단 메시지가 EXPLAIN 이 이미 아는 "왜 무거운가"(접근형태·미사용
        인덱스·스캔 파티션)를 버리고 정적 일반론만 돌려줘, 모델이 **이미 한 조언**을 다시 받고
        같은 형태를 재제출 → 재작성 루프.
  RC-2 (L5 추정): `EXPLAIN.rows` 는 LIMIT 을 반영하지 않는 스캔 상한인데 이를 "예상 처리 행수"로
        써서, 실제 n행만 읽는 순수 `LIMIT n` 조회를 heavy 로 오판(실측 `SELECT * FROM t LIMIT 5`
        → 13,903,018 추정 → 차단).

실 DB 없이 EXPLAIN 결과를 주입해 두 봉인을 검증한다. **부하 회귀 방지가 핵심 계약**이므로
"보정이 적용되지 않아야 하는" 형태(WHERE/집계/정렬/조인/서브쿼리)를 오탐 테스트로 고정한다.
"""
from __future__ import annotations

import types

import modules.dialects as dialects
import modules.tools as tools
import shared.config as cfg
import modules.sql_guard as sql_guard


_EXPLAIN_COLS = ["id", "select_type", "table", "partitions", "type", "possible_keys",
                 "key", "key_len", "ref", "rows", "filtered", "Extra"]


def _plan(rows=13_903_018, *, table="t", select_type="SIMPLE", atype="ALL", key=None,
          possible_keys=None, partitions=None, filtered=100.0, extra=None):
    """단일 테이블 EXPLAIN 한 행(라이브 실측 형태와 동일한 컬럼 구성)."""
    return (1, select_type, table, partitions, atype, possible_keys, key, None, None,
            rows, filtered, extra)


def _run_returning(*plan_rows):
    return lambda stmt: [("rows", _EXPLAIN_COLS, list(plan_rows))]


def _mysql():
    return dialects.MySQLDialect()


# ── RC-2: 순수 LIMIT 조회 상한 보정 ────────────────────────────────────────
def test_pure_limit_query_capped_to_limit():
    """라이브 오판 재현: `SELECT * FROM t LIMIT 5` 는 13.9M 이 아니라 5행."""
    est, facts = _mysql().estimate_load(_run_returning(_plan()), "SELECT * FROM `log_v2`.`t` LIMIT 5")
    assert est == 5
    assert facts["limit_capped_from"] == 13_903_018


def test_pure_limit_offset_forms_capped():
    d = _mysql()
    run = _run_returning(_plan())
    assert d.estimate_load(run, "SELECT * FROM t LIMIT 10 OFFSET 20")[0] == 30
    assert d.estimate_load(run, "SELECT * FROM t LIMIT 20, 10")[0] == 30  # offset 20, count 10
    assert d.estimate_load(run, "SELECT * FROM t LIMIT 1;")[0] == 1       # trailing 세미콜론


def test_limit_cap_never_raises_estimate():
    """보정은 하향 전용 — 이미 가벼운 추정치를 LIMIT 값으로 끌어올리지 않는다."""
    est, facts = _mysql().estimate_load(_run_returning(_plan(rows=3)), "SELECT * FROM t LIMIT 500")
    assert est == 3 and "limit_capped_from" not in facts


# ── RC-2 오탐 방지(부하 회귀 방지): 조기 종료가 보장되지 않는 형태는 보정 없음 ──
def test_where_clause_not_capped():
    """WHERE 는 조건에 맞는 행을 찾기까지 스캔이 이어질 수 있다 → 상한 보장 없음."""
    est, _ = _mysql().estimate_load(
        _run_returning(_plan(filtered=50.0)),
        "SELECT SequenceID FROM t WHERE SequenceID IN (1,2,3) LIMIT 10")
    assert est == 6_951_509  # 13,903,018 × 50% — 보정 미적용


def test_aggregate_not_capped():
    """전역 집계는 LIMIT 1 이어도 대상 전체를 읽는다(사용자가 지목한 'LIMIT 1인데 차단' 케이스)."""
    est, _ = _mysql().estimate_load(
        _run_returning(_plan(atype="index", key="LogType", extra="Using index")),
        "SELECT COUNT(*), MAX(SequenceID) FROM t LIMIT 1")
    assert est == 13_903_018


def test_order_by_filesort_not_capped():
    est, _ = _mysql().estimate_load(
        _run_returning(_plan(atype="index", key="LogType", extra="Using index; Using filesort")),
        "SELECT SequenceID FROM t ORDER BY SequenceID DESC LIMIT 1")
    assert est == 13_903_018


def test_join_multi_plan_rows_not_capped():
    est, _ = _mysql().estimate_load(
        _run_returning(_plan(rows=2000, table="a"), _plan(rows=3000, table="b", atype="ref")),
        "SELECT a.x FROM a JOIN b ON a.id=b.id LIMIT 5")
    assert est == 6_000_000  # 골든 곱 산식 유지


def test_subquery_and_cte_not_capped():
    d = _mysql()
    run = _run_returning(_plan())
    assert d.estimate_load(run, "SELECT * FROM (SELECT x FROM t) s LIMIT 5")[0] == 13_903_018
    assert d.estimate_load(run, "WITH c AS (SELECT 1) SELECT * FROM t LIMIT 5")[0] == 13_903_018


def test_derived_select_type_not_capped():
    """plan row 가 1개여도 select_type 이 SIMPLE 이 아니면 조기 종료를 단정할 수 없다."""
    est, _ = _mysql().estimate_load(
        _run_returning(_plan(select_type="DERIVED")), "SELECT * FROM t LIMIT 5")
    assert est == 13_903_018


def test_limit_literal_in_string_not_treated_as_limit():
    """`SELECT 'LIMIT 1' FROM t` 는 상한이 없다 — 문 끝 LIMIT 만 인정."""
    est, _ = _mysql().estimate_load(_run_returning(_plan()), "SELECT 'LIMIT 1' AS c FROM t")
    assert est == 13_903_018


def test_estimate_load_rows_delegates_and_fails_open():
    """골든: 기존 진입점은 동일 값을 주고, EXPLAIN 실패는 None(fail-open)."""
    d = _mysql()
    assert d.estimate_load_rows(_run_returning(_plan(rows=1234)), "SELECT * FROM t") == 1234

    def _boom(stmt):
        raise RuntimeError("explain failed")
    assert d.estimate_load_rows(_boom, "SELECT 1") is None
    assert d.estimate_load(_boom, "SELECT 1") == (None, {})


def test_plan_facts_extracted():
    _, facts = _mysql().estimate_load(
        _run_returning(_plan(atype="ALL", possible_keys=None, partitions="p1,p2,p3")),
        "SELECT * FROM t WHERE x=1")
    worst = facts["worst"]
    assert worst["type"] == "ALL" and worst["key"] is None and worst["parts"] == 3


# ── RC-1: 차단 메시지가 실행계획 진단을 싣는다 ─────────────────────────────
def _facts(**kw):
    return {"plan_rows": [dict(kw)], "worst": dict(kw)}


def test_coach_names_missing_index_and_partitions():
    out = tools._heavy_query_coach(
        "SELECT SequenceID FROM t WHERE SequenceID IN (1,2)", 13_903_018, 1_000_000,
        _facts(table="tf_log_05_item", type="ALL", key=None, possible_keys=None, parts=26), seen=1)
    assert "실행계획" in out and "tf_log_05_item" in out
    assert "인덱스 미사용" in out and "스캔 파티션=26개" in out
    assert "get_table_indexes" in out and "describe_table" in out


def test_coach_tells_aggregate_cannot_be_rewritten_lighter():
    """전역 집계에 '컬럼을 줄여라/LIMIT 을 붙여라' 는 무의미 — 그 사실을 말해야 루프가 끊긴다."""
    out = tools._heavy_query_coach(
        "SELECT COUNT(*), AVG(x) FROM t", 13_903_018, 1_000_000,
        _facts(table="t", type="index", key="LogType", possible_keys=None, parts=26), seen=1)
    assert "전역 집계" in out and "approx_rows" in out and "search_tables" in out


def test_coach_escalates_confirm_heavy_on_repeat():
    common = ("SELECT COUNT(*) FROM t", 13_903_018, 1_000_000,
              _facts(table="t", type="index", key="LogType", possible_keys=None, parts=None))
    first = tools._heavy_query_coach(*common, seen=1)
    repeat = tools._heavy_query_coach(*common, seen=3)
    assert "최후수단" in first
    assert "최후수단" not in repeat and "3회 차단" in repeat
    assert "confirm_heavy=true" in first and "confirm_heavy=true" in repeat


def test_coach_falls_back_to_static_advice_without_facts():
    """엔진이 계획 사실을 주지 않으면(MSSQL 등) 기존 일반론 — 골든 문구 유지."""
    out = tools._heavy_query_coach("SELECT * FROM dbo.big", 5_000_000, 1_000_000, {}, seen=1)
    assert "재구성" in out and "실행하지 않았습니다" in out and "최후수단" in out


def test_heavy_block_seen_scoped_by_run():
    tools._HEAVY_BLOCK_SEEN.clear()
    assert tools._heavy_block_seen("run-a") == 1
    assert tools._heavy_block_seen("run-a") == 2
    assert tools._heavy_block_seen("run-b") == 1          # run 간 격리
    assert tools._heavy_block_seen("") == 1               # run 식별 불가 → 누적 안 함
    assert tools._heavy_block_seen("") == 1
    tools._HEAVY_BLOCK_SEEN.clear()


# ── 통합: gate 경로에서 마찰이 실제로 사라지는가 ───────────────────────────
def _stub_gate(monkeypatch, plan_rows):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    monkeypatch.setattr(sql_guard, "validate_sql_for_sandbox",
                        lambda sql, forbidden_schemas=None, dialect="mysql":
                        types.SimpleNamespace(ok=True, error_reason=""))
    monkeypatch.setattr(tools, "_freeform_sql_access_error", lambda sql: None)
    monkeypatch.setattr(tools, "_whitelist_violation", lambda refs: None)
    monkeypatch.setattr(tools, "_extract_sql_schema_refs", lambda sql: set())
    monkeypatch.setattr(tools, "_apply_query_cap", lambda conn: None)
    monkeypatch.setattr(tools, "save_csv", lambda *a, **k: "/tmp/x.csv")

    def _raw(conn, stmt):
        if stmt.strip().upper().startswith("EXPLAIN"):
            return [("rows", _EXPLAIN_COLS, list(plan_rows))], 0.01
        return [("rows", ["c"], [(1,)])], 0.5
    monkeypatch.setattr(tools, "_raw_execute_sql", _raw)


def test_gate_lets_pure_limit_sample_through(monkeypatch):
    """마찰 재현→해소: 표본 조회가 더는 13.9M 오판으로 막히지 않는다."""
    tools._HEAVY_BLOCK_SEEN.clear()
    _stub_gate(monkeypatch, [_plan()])
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM `log_v2`.`t` LIMIT 5"})
    assert "무거운 쿼리" not in out and "실행 시간" in out


def test_gate_still_blocks_real_full_scan_with_diagnosis(monkeypatch):
    """정당 차단은 유지하되, 이제 '왜' 와 '다음에 무엇을' 을 함께 준다."""
    tools._HEAVY_BLOCK_SEEN.clear()
    _stub_gate(monkeypatch, [_plan(atype="ALL", key=None, partitions="p1,p2", filtered=50.0)])
    out = tools._tool_execute_sql(None, {"sql": "SELECT x FROM t WHERE y IN (1,2) LIMIT 10"})
    assert "무거운 쿼리" in out and "실행 시간" not in out
    assert "인덱스 미사용" in out and "스캔 파티션=2개" in out


# ── §18.8 codex 적대 리뷰 흡수분 — 역검증(결함 재현이 다시 통과하지 않는지) ──
def test_comment_only_limit_not_capped():
    """[P1] `-- LIMIT 5` / `# LIMIT 5` 는 MySQL 에 LIMIT 이 아니다 — 상한으로 오인하면 **전체 스캔이
    게이트를 통과**한다(재현 확인). 상한은 주석 제거본에서만 인정한다."""
    d, run = _mysql(), _run_returning(_plan())
    assert d.estimate_load(run, "SELECT * FROM huge -- LIMIT 5")[0] == 13_903_018
    assert d.estimate_load(run, "SELECT * FROM huge # LIMIT 5")[0] == 13_903_018
    assert d.estimate_load(run, "SELECT * FROM huge /* LIMIT 5 */")[0] == 13_903_018


def test_leading_comment_still_capped():
    """반대로 정상 주석이 붙은 순수 LIMIT 은 계속 보정된다(과보수 방지)."""
    est, _ = _mysql().estimate_load(
        _run_returning(_plan()), "/* 표본 확인 */ SELECT * FROM t LIMIT 5")
    assert est == 5


def test_comment_strip_cannot_erase_blockers():
    """주석 제거가 문자열 리터럴을 잘라 WHERE 를 지워도, blocker 는 **원본에서도** 검사되어 살아남는다."""
    est, _ = _mysql().estimate_load(
        _run_returning(_plan()), "SELECT '/*' , x FROM t WHERE '*/' = a LIMIT 5")
    assert est == 13_903_018


def test_sql_calc_found_rows_and_distinctrow_not_capped():
    """[P1] `SQL_CALC_FOUND_ROWS` 는 LIMIT 뒤에도 전체 행수를 계산한다(조기 종료 없음).
    `DISTINCTROW`·`STRAIGHT_JOIN` 은 `_` 때문에 `\\bdistinct\\b`/`\\bjoin\\b` 에 안 걸린다."""
    d, run = _mysql(), _run_returning(_plan())
    assert d.estimate_load(run, "SELECT SQL_CALC_FOUND_ROWS * FROM huge LIMIT 5")[0] == 13_903_018
    assert d.estimate_load(run, "SELECT DISTINCTROW a FROM huge LIMIT 5")[0] == 13_903_018
    assert d.estimate_load(run, "SELECT SQL_BIG_RESULT a FROM huge LIMIT 5")[0] == 13_903_018


def test_limit_zero_is_zero_rows():
    """[P3] `LIMIT 0` 은 offset 과 무관하게 즉시 빈 결과 — 처리 행수 0."""
    d, run = _mysql(), _run_returning(_plan())
    assert d.estimate_load(run, "SELECT * FROM t LIMIT 0")[0] == 0
    assert d.estimate_load(run, "SELECT * FROM t LIMIT 1000001, 0")[0] == 0


def test_worst_plan_row_chosen_by_effective_rows():
    """[P2] 코칭 대상은 실효 행수(rows×filtered) 최대 — raw rows 로 고르면 진짜 풀스캔을 숨긴다."""
    _, facts = _mysql().estimate_load(
        _run_returning(
            _plan(rows=10_000_000, table="a", atype="range", key="idx", filtered=0.01),
            _plan(rows=900_000, table="b", atype="ALL", key=None, filtered=100.0)),
        "SELECT * FROM a JOIN b ON a.id=b.id")
    assert facts["worst"]["table"] == "b"   # 실효 900,000 > 1,000


def test_coach_never_invents_plan_facts_it_does_not_have():
    """[P2 원 우려 보존] facts 가 없으면(MSSQL) **계획에서 유도한** 문구를 지어내면 안 된다.
    접근형태·인덱스·파티션은 계획을 봐야 알 수 있고, 없는데 말하면 거짓 진단이다."""
    out = tools._heavy_query_coach("SELECT a FROM dbo.big WHERE x=1", 5_000_000, 1_000_000, {}, seen=1)
    for plan_only in ("실행계획", "접근형태", "사용 인덱스", "스캔 파티션"):
        assert plan_only not in out, f"계획 사실 없이 '{plan_only}' 를 말한다"
    assert "재구성" in out and "최후수단" in out       # 비집계 → 기존 정적 문구 유지


def test_coach_gives_aggregate_advice_even_without_plan_facts():
    """★ 2026-08-14 계약 변경. 집계 판정은 **SQL 형태**만 보므로 계획 사실이 필요 없다.

    예전엔 이 조언이 `if worst:` 안에 있어서, 계획을 주지 않는 엔진(MSSQL)에서는 `COUNT(*)`
    쿼리가 "서버측 집계(COUNT/SUM)를 쓰세요" 라는 **이미 한 일을 시키는** 일반론만 받았다.
    외부 AI 가 그걸 받고 구간 2분할로 우회했는데 **총 스캔량은 동일**했다 — 게이트가 부하를
    못 줄이고 마찰만 만들었다(라이브 제보).
    """
    out = tools._heavy_query_coach("SELECT COUNT(*) FROM dbo.big", 5_000_000, 1_000_000, {}, seen=1)
    assert "전역 집계" in out, "집계 쿼리에 집계 조언을 안 준다"
    assert "approx_rows" in out, "이미 손에 있는 근사치를 안 알려준다"
    assert "총 스캔량을 줄이지 않습니다" in out, "분할 우회가 무의미하다는 사실을 안 알린다"
    # 계획 사실은 여전히 지어내지 않는다.
    assert "실행계획" not in out and "접근형태" not in out
    # 이미 COUNT 인 쿼리에 "서버측 집계를 쓰세요" 라고 답하지 않는다.
    assert "서버측 집계(COUNT/SUM/GROUP BY)" not in out


def test_coach_does_not_advertise_confirm_when_policy_ignores_it():
    """[P2] `TRUST_LLM=false` 인데 "호출하면 실행합니다" 라고 하면 통하지 않는 탈출구를 반복 시도한다
    — 이 cycle 이 없애려던 바로 그 루프."""
    out = tools._heavy_query_coach(
        "SELECT COUNT(*) FROM t", 13_903_018, 1_000_000,
        _facts(table="t", type="index", key="LogType", possible_keys=None, parts=None),
        seen=3, trust_llm_confirm=False)
    assert "confirm_heavy=true` 로 다시 호출" not in out and "최후수단" not in out
    assert "무시됩니다" in out


def test_heavy_block_seen_scoped_by_target_table():
    """[P2] 대상별 카운트 — 다른 테이블의 첫 쿼리가 남의 차단 횟수를 물려받지 않는다."""
    tools._HEAVY_BLOCK_SEEN.clear()
    assert tools._heavy_block_seen("run-a", "t1") == 1
    assert tools._heavy_block_seen("run-a", "t1") == 2
    assert tools._heavy_block_seen("run-a", "t2") == 1   # 다른 대상 → 승격 안 됨
    assert tools._heavy_block_seen("run-b", "t1") == 1   # 다른 run → 격리
    tools._HEAVY_BLOCK_SEEN.clear()


def test_gate_escalation_is_per_target(monkeypatch):
    """통합: 같은 run 이라도 대상이 다르면 두 번째 차단이 confirm 승격을 받지 않는다."""
    tools._HEAVY_BLOCK_SEEN.clear()
    monkeypatch.setattr(cfg, "CURRENT_RUN_ID", "run-x", raising=False)
    _stub_gate(monkeypatch, [_plan(table="alpha", atype="ALL", key=None)])
    first = tools._tool_execute_sql(None, {"sql": "SELECT x FROM alpha WHERE y=1"})
    assert "최후수단" in first
    _stub_gate(monkeypatch, [_plan(table="beta", atype="ALL", key=None)])
    other = tools._tool_execute_sql(None, {"sql": "SELECT x FROM beta WHERE y=1"})
    assert "최후수단" in other and "2회 차단" not in other
    _stub_gate(monkeypatch, [_plan(table="alpha", atype="ALL", key=None)])
    again = tools._tool_execute_sql(None, {"sql": "SELECT z FROM alpha WHERE y=2"})
    assert "2회 차단" in again
    tools._HEAVY_BLOCK_SEEN.clear()


def test_warn_mode_also_drops_false_heavy_note(monkeypatch):
    """[P3 정정] warn 모드도 같은 추정기를 쓰므로 순수 LIMIT 의 **허위** 비용 경고가 사라진다 —
    의도된 동작이다(오판을 경고로 남기는 것이 목적이 아님). 진짜 무거운 쿼리의 경고는 유지."""
    tools._HEAVY_BLOCK_SEEN.clear()
    _stub_gate(monkeypatch, [_plan()])
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "warn", raising=False)
    light = tools._tool_execute_sql(None, {"sql": "SELECT * FROM t LIMIT 5"})
    assert "실행 시간" in light and "무거운 쿼리" not in light
    heavy = tools._tool_execute_sql(None, {"sql": "SELECT COUNT(*) FROM t"})
    assert "실행 시간" in heavy and "무거운 쿼리" in heavy   # warn = 실행 + 경고 prepend


def test_off_mode_never_estimates(monkeypatch):
    """off 골든: 새 진입점도 호출되지 않는다(EXPLAIN 오버헤드 0)."""
    tools._HEAVY_BLOCK_SEEN.clear()
    _stub_gate(monkeypatch, [_plan()])
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "off", raising=False)
    called = []
    monkeypatch.setattr(tools, "_estimate_explain_load",
                        lambda conn, sql: (called.append(sql), (13_903_018, {}))[1])
    out = tools._tool_execute_sql(None, {"sql": "SELECT COUNT(*) FROM t"})
    assert "실행 시간" in out and called == []
