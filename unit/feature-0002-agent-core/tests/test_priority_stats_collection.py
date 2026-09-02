"""2026-09-01 — L0 통계 증거층이 LLM 게이트에 딸려 죽지 않는다.

## 이 테스트가 잠그는 사고 (라이브 실측)

`metadata_stats`(feature-0031 L0 증거층)는 설계상 **LLM 무관**이다 — 운영 DB 에서 카탈로그·표본
통계만 읽는다. 그런데 유일한 호출부가 `node_analysis._build_payload` 였고, 그 앞의
`enqueue_change_analysis` 가 feature-0043 게이트로 early-return 하면서 **큐에 잡이 안 들어가 →
분석이 안 돌고 → 증거 수집도 통째로 멈췄다.**

    metadata_table_stats  243행 · metadata_column_stats 2,252행 — 전환일(2026-08-26) 이후 신규 0
    table_relationships   15,264행 — 같은 기간 719건 갱신   ← 대조군(LLM 무관 + 직접 호출)

즉 **LLM 과 무관한 기능이 호출 위치 하나 때문에 LLM 게이트에 딸려 죽었다**(§16.7 G8-a — 결정의
적용면은 호출 경로 전체다). 수집을 planner 선정(LLM 무관)에 붙여 게이트와 분리한다.
"""
from __future__ import annotations

import sys
import types

import pytest

from modules import insight as I


class _PG:
    def close(self):
        pass


@pytest.fixture
def stats_env(monkeypatch):
    """`metadata_stats` · `node_analysis` · `shared.db` 를 대역으로 — 라이브 무접촉."""
    seen = {"ensure": [], "enabled": True, "ds": {"key": "ds1"}}

    ms = types.ModuleType("modules.metadata_stats")
    ms.enabled = lambda: seen["enabled"]
    ms.ensure_stats = lambda ds, c, scope, schema, table: seen["ensure"].append(
        (scope, schema, table))
    na = types.ModuleType("modules.node_analysis")
    na._resolve_datasource_by_scope = lambda scope: seen["ds"]

    import modules as pkg

    for name, mod in (("metadata_stats", ms), ("node_analysis", na)):
        monkeypatch.setitem(sys.modules, f"modules.{name}", mod)
        monkeypatch.setattr(pkg, name, mod, raising=False)

    real_db = sys.modules.get("shared.db")
    db = types.ModuleType("shared.db")
    db._pg_connect = lambda **kw: _PG()
    if real_db is not None:
        for n in dir(real_db):
            if not hasattr(db, n):
                setattr(db, n, getattr(real_db, n))
    monkeypatch.setitem(sys.modules, "shared.db", db)
    import shared as _sh

    monkeypatch.setattr(_sh, "db", db, raising=False)
    return seen


def test_collects_stats_for_each_priority_target(stats_env):
    """planner 가 고른 각 테이블에 대해 증거 수집을 시도한다 — 게이트와 무관하게."""
    report = {}
    n = I._collect_priority_stats(
        "ds1", ["ds1:dbAuth.T_Account", "ds1:dbAuth.T_Order"], report)
    assert n == 2
    assert stats_env["ensure"] == [("ds1", "dbAuth", "T_Account"),
                                   ("ds1", "dbAuth", "T_Order")]
    # 계측 — 이 값이 0 으로 굳으면 증거층이 다시 멈춘 것이다(재발 신호).
    assert report["stats_collect_attempted"] == 2


def test_malformed_node_keys_are_skipped_not_fatal(stats_env):
    """planner 규약(`<ds>:<schema>.<table>`)을 벗어난 키는 건너뛰되 나머지는 처리한다."""
    n = I._collect_priority_stats(
        "ds1", ["구분자없음", "ds1:스키마만", "ds1:dbAuth.T_Ok", "ds1:.빈스키마"], {})
    assert n == 1
    assert stats_env["ensure"] == [("ds1", "dbAuth", "T_Ok")]


def test_disabled_stats_knob_collects_nothing(stats_env):
    stats_env["enabled"] = False
    assert I._collect_priority_stats("ds1", ["ds1:s.t"], {}) == 0
    assert stats_env["ensure"] == []


def test_unresolvable_datasource_collects_nothing(stats_env):
    """datasource 를 못 찾으면 아무것도 하지 않는다 — 어디서 읽을지 모른 채 수집하지 않는다."""
    stats_env["ds"] = None
    assert I._collect_priority_stats("ds1", ["ds1:s.t"], {}) == 0
    assert stats_env["ensure"] == []


def test_collection_failure_is_soft(monkeypatch, stats_env):
    """수집 실패가 상위 사이클을 막지 않는다 — 증거는 보조물이고 사이클이 본체다."""
    import modules as pkg

    def _boom(*a, **k):
        raise RuntimeError("ds down")

    pkg.metadata_stats.ensure_stats = _boom
    # 예외를 흡수하고 0 또는 부분 수를 돌려준다(raise 하지 않는다).
    assert I._collect_priority_stats("ds1", ["ds1:s.t"], {}) == 0


def test_report_counter_is_registered_in_cycle_template():
    """사이클 payload 템플릿에 카운터가 **초기화**돼 있어야 0 도 관측된다.

    초기화가 없으면 수집이 0건인 사이클에서 키 자체가 사라져, 「증거층이 멈췄다」와
    「이 사이클엔 대상이 없었다」가 payload 에서 구별되지 않는다(§16.7 G9).
    """
    import inspect

    src = inspect.getsource(I.run_insight_cycle)
    assert '"stats_collect_attempted": 0' in src


# ── 배선 검사 — 헬퍼가 맞아도 **부르지 않으면 아무 일도 안 일어난다** ──────────────
#
# ⚠ 위 테스트들은 `_collect_priority_stats` 를 **직접** 부른다. 그래서 `_seed_coverage_targets`
#   에서 그 호출을 지우는 뮤턴트가 **살아남았다**(2026-09-01 실증) — 그리고 그 뮤턴트가 바로
#   이 cycle 이 고치는 결함(증거 수집이 어디에도 배선되지 않은 상태) 그 자체다.
def test_seed_path_collects_stats_even_when_enqueue_is_gated(monkeypatch):
    """게이트가 enqueue 를 막아도 **증거 수집은 일어난다** — 이 cycle 의 핵심 계약.

    `enqueue_change_analysis` 는 feature-0043 게이트로 `{"ok": False, ...}` 를 돌려준다.
    그 앞에서 수집이 끝나야 하고, 수집 결과가 enqueue 결과에 좌우되면 안 된다.
    """
    import types as _t

    seen = {"stats": [], "enqueued": 0}

    planner = _t.ModuleType("modules.analysis_planner")
    planner.enabled = lambda: True
    planner.seed_limit = lambda: 3
    planner.cycle_limit = lambda: 9
    planner.select_priority_targets = lambda cur, sk, sl, lim: ["ds1:dbAuth.T_A", "ds1:dbAuth.T_B"]

    na = _t.ModuleType("modules.node_analysis")

    def _enqueue(*a, **k):
        seen["enqueued"] += 1
        # 게이트 닫힘 시 실제 반환 형태.
        return {"ok": False, "reason": "그래프 뷰 AI 능동 분석은(는) 서버 계정 AI 를 쓰던 기능이라…"}

    na.enqueue_change_analysis = _enqueue

    import modules as pkg

    for name, mod in (("analysis_planner", planner), ("node_analysis", na)):
        monkeypatch.setitem(sys.modules, f"modules.{name}", mod)
        monkeypatch.setattr(pkg, name, mod, raising=False)

    class _Cur:
        def close(self):
            pass

    class _RO:
        def cursor(self):
            return _Cur()

        def close(self):
            pass

    real_db = sys.modules.get("shared.db")
    db = _t.ModuleType("shared.db")
    db._pg_connect_ro = lambda *a, **k: _RO()
    if real_db is not None:
        for n in dir(real_db):
            if not hasattr(db, n):
                setattr(db, n, getattr(real_db, n))
    monkeypatch.setitem(sys.modules, "shared.db", db)
    import shared as _sh

    monkeypatch.setattr(_sh, "db", db, raising=False)

    monkeypatch.setattr(I, "_collect_priority_stats",
                        lambda scope, targets, report: seen["stats"].append(list(targets)) or len(targets))

    I._seed_coverage_targets("ds1", "ds1:dbAuth", "dbAuth", {})

    assert seen["stats"] == [["ds1:dbAuth.T_A", "ds1:dbAuth.T_B"]], (
        "선정된 대상에 대해 증거 수집이 호출되지 않았다 — 증거층이 게이트 뒤에 갇힌 상태")
    assert seen["enqueued"] == 1, "게이트된 enqueue 는 여전히 시도돼야 한다(정직한 사유 로그)"


def test_partial_progress_is_counted_when_collection_blows_up(monkeypatch, stats_env):
    """중간에 터져도 **그때까지 시도한 수는 계측에 남는다**.

    계측을 성공 경로에만 두면 부분 실패가 「아예 안 돌았다」로 보이고, 이 cycle 이 심어 둔
    재발 신호(0 으로 굳음)가 오히려 거짓 경보를 낸다(§16.7 G9).
    """
    import modules as pkg

    calls = {"n": 0}

    def _flaky(ds, c, scope, schema, table):
        calls["n"] += 1
        if calls["n"] >= 3:
            raise RuntimeError("ds gone mid-collection")

    monkeypatch.setattr(pkg.metadata_stats, "ensure_stats", _flaky)
    report = {}
    n = I._collect_priority_stats("ds1", ["ds1:s.a", "ds1:s.b", "ds1:s.c", "ds1:s.d"], report)
    assert n == 2, "터지기 전 2건은 실제로 수집했다"
    assert report.get("stats_collect_attempted") == 2, "부분 진행이 계측에서 사라졌다"
