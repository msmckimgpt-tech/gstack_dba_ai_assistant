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
import inspect
import json
import os
import re

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
            ("ds1", "ds1:app.items", "items", _analysis(), "app", "items", 1, None, None)]
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
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", "not-json{", "app", "t", 1, None, None)])
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


def _target_sql(limit=5):
    """대상 조회 SQL 과 파라미터. (파이썬 주석은 SQL 문자열에 섞이지 않는다.)"""
    cur = _Cur()
    av.pending_targets(cur, limit)
    return [c for c in cur.calls if "node_analysis_jobs" in c[0]][0]


def test_targets_prefer_deeper_evidence():
    """증거가 깊은 것 우선 — **바깥 정렬의 2차 키**로 위치까지 고정한다.

    위치를 고정하지 않으면 stage 가 3차·4차로 밀려도 통과한다(적대 패널 지적: 종전 단정은
    1차 키를 고정했는데 이번 변경으로 그 강도가 사라져 있었다)."""
    sql, _p = _target_sql()
    assert "ORDER BY t.verdict_at ASC NULLS FIRST, t.stage DESC" in sql


def test_targets_take_only_the_latest_analysis_per_node():
    """**노드당 최신 분석문 1건**만 대상이다 — 이것이 없으면 판정이 무한 순환한다.

    `node_analysis_jobs` 에는 같은 노드에 대해 여러 분석 run 의 done 행이 쌓이는데, 저장은
    `store_verdict` 가 노드당 1행만 유지한다. 두 정책이 어긋나면 A세대 저장 → B세대 미판정 →
    B세대 저장(A행 삭제) → A세대 미판정 … 이 영원히 반복된다. 라이브에서 이 순환이 7일간
    7,896콜(배경 LLM 호출의 62.8%)을 태우고 판정 행은 91개로 고정돼 있었다."""
    sql, _p = _target_sql()
    # ⚠ 주석을 걷어낸 뒤 본다 — `/* DISTINCT ON (...) */` 로 주석화하는 변이가 종전 단정을
    #   그대로 통과했다(적대 패널 실측: 그 변이는 라이브에서 100행/92노드 = 중복 8행 복귀).
    bare = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    assert "SELECT DISTINCT ON (j.scope_key, j.node_key)" in bare
    inner = bare[bare.index("DISTINCT ON"):]
    assert "ORDER BY j.scope_key, j.node_key, j.id DESC" in inner


def test_latest_generation_is_chosen_by_id_not_updated_at():
    """노드별 "최신"의 기준은 `id`(삽입 순)다 — `updated_at` 이 아니다.

    `node_analysis_jobs` 의 모든 UPDATE 가 updated_at 트리거를 발화시켜, 과거 run 행이 재분석
    행보다 "최신"으로 역전된다(role backfill 등). 이 저장소는 그 결함을 이미 겪고 `id DESC` 를
    정본 규칙으로 삼았다(`node_analysis.get_node_analysis` · `_latest_done_analysis`). 기준이
    갈리면 판정 대상과 상세 패널이 서로 다른 문장을 가리키고, **사용자가 볼 수 없는 텍스트에
    확인 도장**이 찍힌다 — 라이브 실측(2026-08-05)에서 두 기준이 갈리는 노드가 13개였고 전부
    분석문 텍스트가 달랐다."""
    sql, _p = _target_sql()
    bare = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    inner = bare[bare.index("DISTINCT ON"):bare.rindex(") t ")]
    assert "j.id DESC" in inner
    assert "updated_at" not in inner, "updated_at 은 신뢰할 수 없는 최신 기준이다"


def test_targets_round_robin_by_oldest_verdict():
    """판정이 오래된 것부터(미판정은 맨 앞) — 완충 구간이 전체보다 작아도 모두 순회된다.

    "미판정 우선"만 두면 **갱신된 분석문의 재판정이 굶는다**: 미판정 집합 전체 뒤로, 다시 자기보다
    깊은 stage 전체 뒤로 두 겹 강등되기 때문이다(적대 패널 지적). 대상이 2,052 노드로 늘고 완충이
    100이면 순위 100 밖의 갱신은 영영 판정되지 않아 ADR-0036-04 계약이 조용히 죽는다.
    판정하면 verdict_at 이 now() 로 갱신돼 큐 뒤로 가므로 같은 노드가 선두를 물지 않는다."""
    sql, _p = _target_sql()
    assert "ORDER BY t.verdict_at ASC NULLS FIRST" in sql


def test_targets_buffer_exceeds_cap():
    """완충 배수(limit*5)는 처리량을 지탱하는 유일한 장치다 — 윈도우 대부분이 skip 경로다.

    (라이브 실측: 윈도우 92행 중 89행이 '이미 판정됨' skip.) 배수를 1로 되돌리는 변이가 종전
    테스트를 통과했다 — 어떤 테스트도 params 를 보지 않았기 때문이다."""
    _sql, params = _target_sql(limit=7)
    assert params == (35,)


def test_target_columns_match_unpacking_order():
    """바깥 SELECT 의 **컬럼 순서**와 호출측 언팩 순서가 일치해야 한다.

    한 줄에서 두 컬럼을 맞바꾸는 변이(`stage` ↔ `analysis_hash`)가 종전 테스트를 전부 통과했다 —
    mock 커서가 하드코딩 8-튜플을 돌려주므로 순서 정합을 대조하는 곳이 없었다. 그 변이가 나가면
    `judged_hash` 에 stage(0/1)가 들어가 해시 비교가 **절대 성립하지 않고**, 매 pass 전량 재판정 =
    이번에 닫은 순환이 그대로 복구된다."""
    sql, _p = _target_sql()
    outer = re.match(r"SELECT (.+?) FROM \(", sql)
    assert outer, sql[:120]
    cols = [c.strip().split(".")[-1] for c in outer.group(1).split(",")]

    src = inspect.getsource(av.run_verification_pass)
    unpack = re.search(r"for \(([^)]+)\) in rows:", src)
    assert unpack, "언팩 구문을 찾지 못했다"
    names = [v.strip() for v in unpack.group(1).replace("\n", " ").split(",")]

    # 컬럼명 ↔ 변수명 (이름이 다른 것은 여기 한 곳에서만 매핑한다)
    alias = {"analysis_hash": "judged_hash", "judged_stage": "judged_stage"}
    assert [alias.get(c, c) for c in cols] == names


def test_targets_short_circuit_on_zero_limit():
    cur = _Cur()
    assert av.pending_targets(cur, 0) == []
    assert cur.calls == []


# ── C: 비용 ─────────────────────────────────────────────────────────────────
def test_pass_cap_limits_calls(monkeypatch):
    targets = [("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None, None)
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
    targets = [("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None, None)
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
    # 윈도우는 넉넉히 — 호출부 주석이 길어졌다고 "예외 흡수가 사라졌다"로 읽히면 거짓 실패다.
    assert "except Exception" in src[idx:idx + 1200]


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
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", a, "app", "t", 1, av.analysis_hash(a), 1)])
    rep, stored = _run(monkeypatch, conn, {"verdict": "supported", "reason": "근거"})
    assert rep["checked"] == 0 and stored == []


def test_updated_analysis_is_rejudged(monkeypatch):
    """분석문이 갱신되면 옛 판정은 그 문장에 대한 것이 아니다 — 재판정해야 한다.
    '판정 행이 있으면 제외'로 두면 문서에 적은 계약과 **정반대**로 동작한다(codex P1)."""
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", _analysis(), "app", "t", 1, "OLDHASH", 1)])
    rep, stored = _run(monkeypatch, conn, {"verdict": "contradicted", "reason": "근거"})
    assert rep["checked"] == 1 and stored


def test_rejudged_is_counted_separately(monkeypatch):
    """'많이 도는 것'과 '같은 걸 또 도는 것'은 다르다 — telemetry 가 그 둘을 구분해야
    운영 화면에서 순환을 알아볼 수 있다(2026-08-05 회귀는 이 구분이 없어 늦게 발견됐다)."""
    fresh = _Conn(targets=[("ds1", "ds1:app.t", "t", _analysis(), "app", "t", 1, None, None)])
    rep, _stored = _run(monkeypatch, fresh, {"verdict": "supported", "reason": "근거"})
    assert rep["checked"] == 1 and rep["rejudged"] == 0

    stale = _Conn(targets=[("ds1", "ds1:app.t", "t", _analysis(), "app", "t", 1, "OLDHASH", 1)])
    rep2, _s2 = _run(monkeypatch, stale, {"verdict": "supported", "reason": "근거"})
    assert rep2["checked"] == 1 and rep2["rejudged"] == 1


def test_rejudged_is_not_counted_when_store_fails(monkeypatch):
    """저장이 실패하면 판정이 남지 않았다 — 재판정으로도 세지 않는다.

    증가 지점을 `if store_verdict(...)` 밖으로 옮기는 변이가 종전 테스트를 통과했다."""
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_verify_analysis",
                        lambda p, scope_key=None: {"verdict": "supported", "reason": "근거"},
                        raising=False)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    monkeypatch.setattr(av, "store_verdict", lambda *a: False)
    monkeypatch.setattr(av, "enabled", lambda: True)
    monkeypatch.setattr(av, "max_per_pass", lambda: 5)
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", _analysis(), "app", "t", 1, "OLDHASH", 1)])
    rep = av.run_verification_pass(conn)
    assert rep["checked"] == 0 and rep["rejudged"] == 0
    assert rep["attempted"] == 1, "콜은 태웠으므로 attempted 에는 남아야 한다"


def test_rejudged_is_not_counted_for_same_hash_skip(monkeypatch):
    """이미 판정된 같은 분석문은 콜도 재판정도 아니다.

    증가 지점을 같은-해시 skip 앞으로 옮기는 변이가 종전 테스트를 통과했다 — 그러면 정상 운영에서
    `rejudged` 가 상시 포화돼 "cap 을 채우면 순환" 이라는 판정 기준이 영구 오작동한다."""
    a = _analysis()
    conn = _Conn(targets=[("ds1", "ds1:app.t", "t", a, "app", "t", 1, av.analysis_hash(a), 1)])
    rep, _stored = _run(monkeypatch, conn, {"verdict": "supported", "reason": "근거"})
    assert rep["rejudged"] == 0 and rep["attempted"] == 0


def test_attempted_counts_calls_even_when_the_verdict_is_rejected(monkeypatch):
    """LLM 을 태웠으면 센다 — 저장 성공만 세면 "판정에 실패하며 예산만 먹는" pass 가 무음이 된다.

    이 격차(attempted ≫ checked)는 자기증폭한다: 실패 노드는 미판정으로 남아 큐 선두
    (verdict_at NULLS FIRST)를 계속 물기 때문이다."""
    conn = _Conn(targets=[("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None, None)
                          for i in range(3)])
    rep, stored = _run(monkeypatch, conn, {"verdict": "supported"})   # reason 없음 → 판정 거부
    assert rep["checked"] == 0 and stored == []
    assert rep["attempted"] == 3


def test_consecutive_failures_stop_the_pass(monkeypatch):
    """판정자가 특정 입력에서 계약 위반 응답을 반복하면 한 pass 예산을 그 노드들이 통째로 먹는다.

    연속 실패 상한에서 멈춰 다음 pass 로 넘긴다(대상 순서가 바뀌어 다른 노드가 앞에 설 기회를 준다)."""
    monkeypatch.setattr(av, "max_per_pass", lambda: 50)
    conn = _Conn(targets=[("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None, None)
                          for i in range(50)])
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_verify_analysis", lambda p, scope_key=None: None, raising=False)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    monkeypatch.setattr(av, "enabled", lambda: True)
    rep = av.run_verification_pass(conn)
    assert rep["attempted"] == av._MAX_CONSECUTIVE_FAILURES
    assert rep["checked"] == 0


def test_verify_telemetry_reaches_the_operator_payload():
    """계측은 **allow-list 에 등재돼야** 운영자에게 도달한다.

    `scan_report["analysis_verify"]` 는 dict 라 `_telemetry_sweep` 의 스칼라 필터가 통째로 버린다.
    같은 실패(계측을 만들었는데 payload 에 안 실어 무음)가 이 워커에서 이미 두 번 있었고, 그
    주석이 insight.py 에 남아 있다 — 이 단정이 세 번째를 막는다."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules"
           / "insight.py").read_text(encoding="utf-8")
    for key in ("analysis_verify_checked", "analysis_verify_attempted",
                "analysis_verify_rejudged"):
        assert key in src, f"{key} 가 payload allow-list 에 없다 — 계측이 도달하지 않는다"
    # checked 만 보고 기록하면 "콜만 태우고 저장 0" 인 pass 가 통째로 사라진다.
    assert '_av_rep.get("checked") or _av_rep.get("attempted")' in src


def test_verification_pass_runs_under_the_advisory_lock():
    """판정 pass 에는 행 단위 claim 이 없다 — lock 없이 돌면 워커 수만큼 LLM 콜이 중복된다.

    그리고 그 중복은 전부 `judged_hash IS NULL` 을 같이 읽으므로 `rejudged` 에도 잡히지 않는다
    (관측 사각). 같은 이유로 `domain_synthesis` 도 lock 안에 있다."""
    import ast
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules"
           / "insight.py").read_text(encoding="utf-8")
    # 위치 비교가 아니라 **AST 포함관계**로 본다 — 단순 인덱스 비교는 lock 블록이 끝난 뒤의 호출도
    # 통과시킨다(같은 파일에 `if lock_acquired:` 가 앞서 나오기만 하면 된다).
    guarded = [
        ast.unparse(n)
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.If) and ast.unparse(n.test).strip() == "lock_acquired"
    ]
    assert any("run_verification_pass()" in g for g in guarded), \
        "판정 pass 가 advisory lock 밖에서 돈다"


@pytest.mark.skipif(os.environ.get("AGENT_KB_PG_INTEGRATION_TEST") != "1",
                    reason="실 Postgres 접속 필요 — AGENT_KB_PG_INTEGRATION_TEST=1 로 활성화")
def test_target_query_executes_on_live_postgres():
    """쿼리가 **SQL 로서 유효한지** 실 PG 로 확인하고, 노드당 1행인지 단정한다.

    단위 테스트는 mock 커서라 SQL 을 파싱조차 하지 않는다 — 서브쿼리 select 목록에서 한 항목만
    지워도(바깥 ORDER BY 가 그것을 참조) 런타임 `column does not exist` 가 나는데, `pending_targets`
    의 fail-soft 가 그것을 삼켜 `skipped="no_targets"` 로 위장한다: **기능이 영구히 죽은 채
    텔레메트리는 건강해 보인다.** 이 테스트가 그 창을 닫는다.

    실행: `AGENT_KB_PG_INTEGRATION_TEST=1` + agent_kb 접속 가능 환경(워커 컨테이너).
    """
    from shared import db as _db
    conn = _db._pg_connect()
    assert conn is not None
    cur = conn.cursor()
    try:
        rows = av.pending_targets(cur, 20)
        keys = [(r[0], r[1]) for r in rows]
        assert len(keys) == len(set(keys)), "같은 노드가 두 번 대상이 됐다 — 순환이 살아 있다"
        for r in rows:
            assert isinstance(r[6], (int, type(None))), "stage 자리에 다른 컬럼이 왔다"
    finally:
        cur.close()
        conn.close()


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
    targets = [("ds1", f"ds1:app.t{i}", f"t{i}", _analysis(), "app", f"t{i}", 1, None, None)
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


def test_deeper_evidence_triggers_rejudgement(monkeypatch):
    """분석문이 그대로여도 **증거가 깊어졌으면** 다시 판정한다.

    판정은 (분석문, 증거) 두 입력의 함수인데 해시는 분석문만 고정한다. 증거는 테이블당 1행이
    제자리 갱신되므로, 해시만 보면 stage 0(표본 0행·컬럼 통계 전무)에서 내린 판정이 stage 1
    수집 후에도 "대조했다"는 얼굴로 남는다 — 적대 패널 실측으로 라이브 판정 95건 중 82건이
    그 상태였다."""
    a = _analysis()
    h = av.analysis_hash(a)
    # 같은 해시 + 더 깊어진 증거(judged 0 < current 1) → 재판정
    deeper = _Conn(targets=[("ds1", "ds1:app.t", "t", a, "app", "t", 1, h, 0)])
    rep, stored = _run(monkeypatch, deeper, {"verdict": "supported", "reason": "근거"})
    assert rep["checked"] == 1 and stored, "증거가 깊어졌는데 재판정하지 않았다"

    # 같은 해시 + 같은 깊이 → skip(비용만 드는 재판정 금지)
    same = _Conn(targets=[("ds1", "ds1:app.t", "t", a, "app", "t", 1, h, 1)])
    rep2, stored2 = _run(monkeypatch, same, {"verdict": "supported", "reason": "근거"})
    assert rep2["checked"] == 0 and stored2 == []


def test_savepoint_is_skipped_on_autocommit_connections():
    """autocommit 에서 SAVEPOINT 는 항상 실패하고 **PG 서버 로그에 ERROR 를 남긴다**.

    노드 상세는 클릭마다 이 경로를 타므로 그 노이즈가 실제 오류를 덮는다. autocommit 이면
    오염될 트랜잭션이 없으니 시도 자체를 건너뛴다(방어 효과 동일)."""
    class _AutoCur(_Cur):
        class _C:
            autocommit = True
        connection = _C()

    cur = _AutoCur()
    with av._savepoint(cur):
        pass
    assert not any("SAVEPOINT" in c[0].upper() for c in cur.calls), \
        "autocommit 인데 SAVEPOINT 를 발행했다"
