"""feature-0036-analysis-verification — 분석문 사실성 판정 단위 테스트.

**이 파일의 절반은 하나의 명제를 지킨다**: 판정 실패는 "검증됨"이 아니다.
fail-open 이 확인 도장으로 둔갑하면 이 층은 있는 것보다 나쁘다 — 아무도 확인하지 않은 서술에
도장이 찍히고, 그 도장을 근거로 위층(요약·답변)이 더 확신하게 된다.

검증 축:
  A(정직성): LLM 실패·계약 위반 응답·증거 부재·저장 실패 → 전부 **행 없음**(미검증).
  B(대상 선정): 분석문 + 증거 둘 다 있고 미판정인 것만. 깊은 증거 우선.
  C(비용): pass 상한 · 1건 1콜 · 토큰 예산 배치별 재확인 · LLM 슬롯 게이트.
  D(격리): savepoint · 예외가 워커로 전파되지 않음.
"""
import json

import pytest

from modules import analysis_verify as av


def _analysis(summary="계정별 아이템 보유 현황을 담는 테이블이다.", **kw):
    obj = {"summary": summary, "relationships": "계정 테이블과 연결된다.",
           "usage": "보유 현황 조회에 쓴다.", "caveats": ""}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


class _Cur:
    def __init__(self, targets=None, tstat=None, cstats=None):
        self.calls = []
        self._targets = targets if targets is not None else [
            ("ds1", "ds1:app.items", "items", _analysis(), "app", "items", 1, None)]
        self._tstat = tstat if tstat is not None else (1000, 5, ["id"], ["id"], 1, 0, 100)
        self._cstats = cstats if cstats is not None else [
            ("id", "int", False, 100, 0.0, 1.0, 999.0, None, None, True)]
        self._last = None
        self._last_all = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "SAVEPOINT" in sql.upper():
            return
        if "FROM node_analysis_jobs" in sql:
            self._last_all = self._targets
        elif "FROM metadata_table_stats" in sql:
            self._last = self._tstat
        elif "FROM metadata_column_stats" in sql:
            self._last_all = self._cstats
        else:
            self._last, self._last_all = None, []

    def fetchone(self):
        return self._last

    def fetchall(self):
        return self._last_all

    def close(self):
        pass


class _Conn:
    def __init__(self, **kw):
        self.cur = _Cur(**kw)

    def cursor(self):
        return self.cur


def _run(monkeypatch, conn, llm_result, *, budget_ok=True):
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_verify_analysis",
                        lambda payload, scope_key=None: llm_result, raising=False)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: budget_ok)
    stored = []
    monkeypatch.setattr(av, "store_verdict",
                        lambda *a: (stored.append(a), True)[1])
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 5)
    rep = av.run_verification_pass(conn)
    return rep, stored


# ── A: 정직성 — 실패는 절대 "검증됨"이 아니다 ────────────────────────────────
def test_llm_failure_records_nothing(monkeypatch):
    """LLM 이 None 을 돌려주면 미검증이다. supported 로도 unverifiable 로도 기록하지 않는다."""
    rep, stored = _run(monkeypatch, _Conn(), None)
    assert rep["checked"] == 0 and stored == []


def test_contract_violating_verdict_records_nothing(monkeypatch):
    """판정자가 계약을 벗어난 문자열을 돌려주면 그것은 판정이 아니다 — 보정하지 않는다."""
    for bad in ({"verdict": "ok"}, {"verdict": ""}, {"verdict": "maybe"},
                {"no_verdict": 1}, "not a dict", None):
        rep, stored = _run(monkeypatch, _Conn(), bad)
        assert rep["checked"] == 0 and stored == [], bad


def test_verdict_without_reason_is_rejected(monkeypatch):
    """근거 없는 판정은 판정이 아니다 — 사람이 재확인할 방법이 없는 확인 도장이다(codex P1)."""
    for bad in ({"verdict": "supported"}, {"verdict": "supported", "reason": ""},
                {"verdict": "contradicted", "reason": "  "}):
        rep, stored = _run(monkeypatch, _Conn(), bad)
        assert rep["checked"] == 0 and stored == [], bad


def test_normalize_rejects_unknown_verdict():
    assert av.normalize_verdict({"verdict": "maybe"}) == (None, "")
    assert av.normalize_verdict({"verdict": "supported"}) == (None, "")   # reason 필수
    assert av.normalize_verdict({}) == (None, "")
    assert av.normalize_verdict(None) == (None, "")


def test_normalize_accepts_only_declared_verdicts():
    for v in av.VERDICTS:
        got, _r = av.normalize_verdict({"verdict": v, "reason": "판정 근거 문장"})
        assert got == v
    assert set(av.VERDICTS) == {"supported", "contradicted", "unverifiable"}


def test_normalize_tolerates_case_and_whitespace():
    """LLM 응답의 대소문자·공백 변동은 계약 위반이 아니다 — 정규화해 받는다.
    (반면 열거에 없는 문자열은 보정하지 않고 거부한다.)"""
    assert av.normalize_verdict({"verdict": " SUPPORTED ", "reason": "근거 문장"})[0] == "supported"


def test_missing_evidence_records_nothing(monkeypatch):
    """증거가 없으면 대조할 것이 없다 — 판정하지 않는다(통과시키지 않는다)."""
    monkeypatch.setattr(av, "load_evidence", lambda *a: {})
    rep, stored = _run(monkeypatch, _Conn(), {"verdict": "supported", "reason": "r"})
    assert rep["checked"] == 0 and stored == []


def test_unparsable_analysis_records_nothing(monkeypatch):
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", "not-json{", "app", "t", 1, None)])
    rep, stored = _run(monkeypatch, conn, {"verdict": "supported", "reason": "r"})
    assert rep["checked"] == 0 and stored == []


def test_store_failure_is_not_counted(monkeypatch):
    """저장이 실패하면 판정이 남지 않았으므로 checked 로 세지 않는다."""
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_verify_analysis",
                        lambda p, scope_key=None: {"verdict": "supported", "reason": "r"},
                        raising=False)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    monkeypatch.setattr(av, "store_verdict", lambda *a: False)
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 5)
    assert av.run_verification_pass(_Conn())["checked"] == 0


def test_verdict_check_constraint_matches_module_contract():
    """DB CHECK 제약과 모듈 상수가 어긋나면 저장이 조용히 실패한다."""
    import pathlib
    mig = (pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
           / "20260731_0052_analysis_verdicts.py").read_text(encoding="utf-8")
    for v in av.VERDICTS:
        assert f"'{v}'" in mig


# ── 판정 결과 기록 ──────────────────────────────────────────────────────────
def test_supported_and_contradicted_are_recorded(monkeypatch):
    for v in ("supported", "contradicted", "unverifiable"):
        rep, stored = _run(monkeypatch, _Conn(), {"verdict": v, "reason": "근거 문장"})
        assert rep["checked"] == 1 and rep[v] == 1
        # store_verdict(cur, scope, node, hash, verdict, reason, stage, model)
        assert stored[0][4] == v and stored[0][5] == "근거 문장"


def test_analysis_hash_changes_with_content():
    """분석문이 갱신되면 해시가 달라져 자연히 미검증으로 돌아간다."""
    a, b = _analysis(), _analysis(summary="다른 요약")
    assert av.analysis_hash(a) != av.analysis_hash(b)
    assert av.analysis_hash(a) == av.analysis_hash(a)
    assert av.analysis_hash("") == ""


def test_analysis_hash_ignores_whitespace_noise():
    assert av.analysis_hash('{"a":  1}') == av.analysis_hash('{"a": 1}')


# ── B: 대상 선정 ────────────────────────────────────────────────────────────
def test_targets_require_both_analysis_and_evidence():
    cur = _Cur()
    av.pending_targets(cur, 5)
    sql, _p = [c for c in cur.calls if "node_analysis_jobs" in c[0]][0]
    assert "JOIN metadata_table_stats" in sql
    assert "status = 'done'" in sql and "analysis IS NOT NULL" in sql


def test_targets_carry_previous_verdict_hash():
    """'판정 행이 있으면 제외'가 아니라 **이전 판정의 해시를 가져와** 비교한다 — 전자는
    분석문이 갱신돼도 재판정하지 않아 문서의 계약과 정반대가 된다(codex P1)."""
    cur = _Cur()
    av.pending_targets(cur, 5)
    sql, _p = [c for c in cur.calls if "node_analysis_jobs" in c[0]][0]
    assert "LEFT JOIN node_analysis_verdicts" in sql and "v.analysis_hash" in sql


def test_targets_exclude_failed_evidence():
    """수집이 실패한 증거로 판정하면 잘못된 모순 판정이 나온다."""
    cur = _Cur()
    av.pending_targets(cur, 5)
    sql, _p = [c for c in cur.calls if "node_analysis_jobs" in c[0]][0]
    assert "m.error IS NULL" in sql


def test_targets_prefer_deeper_evidence():
    cur = _Cur()
    av.pending_targets(cur, 5)
    sql, _p = [c for c in cur.calls if "node_analysis_jobs" in c[0]][0]
    assert "ORDER BY m.stage DESC" in sql


def test_targets_short_circuit_on_zero_limit():
    cur = _Cur()
    assert av.pending_targets(cur, 0) == []
    assert cur.calls == []


# ── C: 비용 ─────────────────────────────────────────────────────────────────
def test_pass_cap_limits_calls(monkeypatch):
    targets = [("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None)
               for i in range(10)]
    import modules.llm as _llm
    calls = []
    monkeypatch.setattr(_llm, "llm_verify_analysis",
                        lambda p, scope_key=None: calls.append(1) or {
                            "verdict": "supported", "reason": "근거 문장"},
                        raising=False)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    monkeypatch.setattr(av, "store_verdict", lambda *a: True)
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 3)
    rep = av.run_verification_pass(_Conn(targets=targets))
    assert rep["checked"] == 3 and len(calls) == 3


def test_token_budget_blocks_the_pass(monkeypatch):
    rep, stored = _run(monkeypatch, _Conn(), {"verdict": "supported", "reason": "근거"},
                       budget_ok=False)
    assert rep["skipped"] == "llm_token_budget" and stored == []


def test_token_budget_is_rechecked_per_item(monkeypatch):
    """긴 pass 도중 예산이 소진되면 그 자리에서 멈춘다 — 1건 1콜이라 누적이 빠르다."""
    seen = {"n": 0}

    def _allowed(conn=None):
        seen["n"] += 1
        return seen["n"] <= 2          # 진입 1회 + 첫 항목 1회만 허용

    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", _allowed)
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_verify_analysis",
                        lambda p, scope_key=None: {"verdict": "supported", "reason": "근거"},
                        raising=False)
    monkeypatch.setattr(av, "store_verdict", lambda *a: True)
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 5)
    targets = [("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None)
               for i in range(5)]
    rep = av.run_verification_pass(_Conn(targets=targets))
    assert rep["checked"] == 1, "예산 소진 후에도 계속 판정했다"


def test_disabled_switch_skips(monkeypatch):
    monkeypatch.setattr(av, "enabled", lambda: False)
    assert av.run_verification_pass(_Conn())["skipped"] == "disabled"


def test_zero_cap_skips(monkeypatch):
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 0)
    assert av.run_verification_pass(_Conn())["skipped"] == "cap_zero"


def test_defaults_off_when_config_unreadable(monkeypatch):
    import shared.runtime_settings as rts
    monkeypatch.setattr(rts, "get_int", lambda k: (_ for _ in ()).throw(RuntimeError("no cfg")))
    import shared.config as cfg
    monkeypatch.delattr(cfg, "AGENT_ANALYSIS_VERIFY_ENABLED", raising=False)
    assert av.enabled() is False


# ── D: 격리 ─────────────────────────────────────────────────────────────────
def test_queries_use_savepoint():
    """워커와 같은 커넥션을 쓴다 — 신규 테이블 부재 시 트랜잭션이 abort 되면 분석이 함께 죽는다
    (feature-0031·0033 에서 두 번 겪은 결함)."""
    cur = _Cur()
    av.pending_targets(cur, 5)
    assert any("SAVEPOINT" in c[0].upper() for c in cur.calls)
    cur2 = _Cur()
    av.load_evidence(cur2, "ds1", "app", "t", 1)
    assert any("SAVEPOINT" in c[0].upper() for c in cur2.calls)


def test_pass_absorbs_exceptions(monkeypatch):
    class _Boom(_Conn):
        def cursor(self):
            raise RuntimeError("pg down")

    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 5)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    rep = av.run_verification_pass(_Boom())      # 예외 없이 반환
    assert rep["checked"] == 0


def test_evidence_query_failure_returns_empty():
    class _Boom(_Cur):
        def execute(self, sql, params=None):
            if "metadata_table_stats" in sql:
                raise RuntimeError("no table")
            super().execute(sql, params)

    assert av.load_evidence(_Boom(), "ds1", "app", "t", 1) == {}


# ── 배선 ────────────────────────────────────────────────────────────────────
def test_insight_runs_the_verification_pass():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules"
           / "insight.py").read_text(encoding="utf-8")
    assert "run_verification_pass" in src
    idx = src.index("run_verification_pass")
    assert "except Exception" in src[idx:idx + 400]


def test_prompt_prefers_contradiction_over_rubber_stamp():
    """확인 도장을 남발하는 판정자는 없는 것보다 나쁘다 — 프롬프트가 그 기울기를 말해야 한다."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules"
           / "llm.py").read_text(encoding="utf-8")
    idx = src.index("ANALYSIS_VERIFY_PROMPT")
    body = src[idx:idx + 4000]
    assert "rubber-stamp" in body
    assert "do not invent conflicts" in body
    assert "SAMPLE" in body      # 표본을 전역 제약으로 오해하지 말라는 지시


# ── codex P1 회귀 방지 ───────────────────────────────────────────────────────
def test_already_judged_same_analysis_is_skipped(monkeypatch):
    """같은 분석문 버전을 다시 판정하면 비용만 든다."""
    a = _analysis()
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", a, "app", "t", 1, av.analysis_hash(a))])
    rep, stored = _run(monkeypatch, conn, {"verdict": "supported", "reason": "근거"})
    assert rep["checked"] == 0 and stored == []


def test_updated_analysis_is_rejudged(monkeypatch):
    """분석문이 갱신되면 옛 판정은 그 문장에 대한 것이 아니다 — 재판정해야 한다.
    '판정 행이 있으면 제외'로 두면 문서에 적은 계약과 **정반대**로 동작한다(codex P1)."""
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", _analysis(), "app", "t", 1, "OLDHASH")])
    rep, stored = _run(monkeypatch, conn, {"verdict": "contradicted", "reason": "근거"})
    assert rep["checked"] == 1 and stored


def test_target_query_carries_previous_hash():
    cur = _Cur()
    av.pending_targets(cur, 5)
    sql, _p = [c for c in cur.calls if "node_analysis_jobs" in c[0]][0]
    assert "v.analysis_hash" in sql and "LEFT JOIN node_analysis_verdicts" in sql


def test_evidence_query_filters_failed_collection():
    """대상 조회와 evidence 재조회 사이에 수집 실패가 기록되면 실패한 통계로 판정하게 된다."""
    cur = _Cur()
    av.load_evidence(cur, "ds1", "app", "t", 1)
    sql, _p = [c for c in cur.calls if "metadata_table_stats" in c[0]][0]
    assert "error IS NULL" in sql


def test_store_keeps_one_row_per_node():
    """분석 갱신마다 행이 쌓이면 무한 증식이고 LEFT JOIN 도 행을 늘린다."""
    cur = _Cur()
    av.store_verdict(cur, "ds1", "ds1:app.t", "H1", "supported", "근거", 1, "m")
    sqls = [c[0] for c in cur.calls]
    assert any(s.startswith("DELETE FROM node_analysis_verdicts") for s in sqls)
    assert any("analysis_hash <> " in s for s in sqls)


def test_caller_limit_cannot_exceed_configured_cap(monkeypatch):
    """인자로 상한을 우회하면 콘솔 knob 이 거짓 컨트롤이 된다."""
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 2)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    import modules.llm as _llm
    calls = []
    monkeypatch.setattr(_llm, "llm_verify_analysis",
                        lambda p, scope_key=None: calls.append(1) or {
                            "verdict": "supported", "reason": "근거"}, raising=False)
    monkeypatch.setattr(av, "store_verdict", lambda *a: True)
    targets = [("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None)
               for i in range(10)]
    rep = av.run_verification_pass(_Conn(targets=targets), limit=99)
    assert rep["checked"] == 2 and len(calls) == 2


def test_budget_module_absence_stops_the_pass():
    """예산을 못 읽으면 **중단한다** — 이 모듈의 원칙 '모르면 하지 않는다'는 지출에도 적용된다.

    다른 fail-soft 와 방향이 반대인 이유: 계량 장애로 기능이 멈추는 것보다, 상한을 모른 채
    자동 지출을 계속하는 쪽이 위험하다. (import 차단은 `from shared import X` 가 패키지 속성을
    보기 때문에 런타임으로 재현하기 어려워, 분기 자체를 소스로 단정한다.)"""
    import inspect
    src = inspect.getsource(av.run_verification_pass)
    assert 'rep["skipped"] = "budget_unavailable"' in src
    # llm_budget · resource_budget 두 축 모두 부재 시 중단이어야 한다.
    assert src.count('"budget_unavailable"') >= 2
    assert "_lb = None" not in src and "_rb = None" not in src


def test_pass_opens_its_own_connection_when_none_given(monkeypatch):
    """insight tick 스코프에는 agent_kb 커넥션이 없다 — 인자 없이 불려도 동작해야 한다
    (초기 구현은 정의되지 않은 변수를 넘겨 배선이 통째로 죽어 있었다, codex P1)."""
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 5)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    import shared.db as db
    opened = []
    conn = _Conn()
    monkeypatch.setattr(db, "_pg_connect", lambda: opened.append(1) or conn)
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_verify_analysis",
                        lambda p, scope_key=None: {"verdict": "supported", "reason": "근거"},
                        raising=False)
    monkeypatch.setattr(av, "store_verdict", lambda *a: True)
    rep = av.run_verification_pass()
    assert opened == [1] and rep["checked"] == 1


def test_insight_calls_pass_without_undefined_variable():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules"
           / "insight.py").read_text(encoding="utf-8")
    assert "run_verification_pass()" in src
