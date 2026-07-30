"""feature-0032-llm-token-budget — 백그라운드 LLM 토큰 예산 단위 테스트.

검증 축:
  A(사용자 보호): 사용자 요청 경로(대화 답변·자가검증·제목·분류)는 예산에서 제외되고 절대
    차단되지 않는다. 예산으로 사용자를 막으면 비용 통제가 아니라 서비스 장애다.
  B(fail-open): 상한 0·조회 실패는 허용. 계량 장애가 기능 정지로 번지지 않는다.
  C(게이트 배선): 백그라운드 진입점 3곳이 소진 시 skip 사유를 정직하게 돌려준다.
  D(캐시): TTL 안에서는 PG 를 다시 때리지 않는다.
"""
import pytest

from shared import llm_budget as lb


@pytest.fixture(autouse=True)
def _clear_cache():
    lb.invalidate()
    yield
    lb.invalidate()


class _Cur:
    def __init__(self, value=0):
        self.value = value
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return (self.value,)

    def close(self):
        pass


class _Conn:
    def __init__(self, value=0):
        self.cur = _Cur(value)
        self.cursor_calls = 0

    def cursor(self):
        self.cursor_calls += 1
        return self.cur


# ── A: 사용자 요청 경로 보호 ─────────────────────────────────────────────────
def test_user_facing_tasks_are_excluded_from_the_query():
    """예산 집계 SQL 이 사용자 경로 task 를 실제로 제외하는지 — 상수 선언만으로는 부족하다."""
    conn = _Conn(123)
    lb._query_spent(conn)
    sql, params = conn.cur.calls[0]
    assert "llm_usage" in sql and "task" in sql
    excluded = set(params[1])
    assert {"agent", "redteam", "topic", "classify"} <= excluded


def test_user_facing_task_set_matches_documented_contract():
    """대화 답변·자가검증·제목·원본전환 분류는 사람이 기다리는 호출이다."""
    assert "agent" in lb.USER_FACING_TASKS       # 대화 답변
    assert "redteam" in lb.USER_FACING_TASKS     # 답변 자가검증
    assert "topic" in lb.USER_FACING_TASKS       # 대화 제목
    assert "classify" in lb.USER_FACING_TASKS    # 원본 전환 분류
    # 백그라운드 작업은 절대 제외 목록에 없어야 한다(있으면 예산이 헐거워진다).
    for bg in ("node_analysis", "cluster_label", "table_insight", "glossary_suggest",
               "enum_suggest", "account_insight", "schema_insight"):
        assert bg not in lb.USER_FACING_TASKS


def test_blacklist_shape_counts_unknown_tasks_as_background(monkeypatch):
    """새 백그라운드 task 가 생겨도 자동으로 예산 안에 들어온다(보수적인 방향으로 틀린다)."""
    conn = _Conn(0)
    lb._query_spent(conn)
    _sql, params = conn.cur.calls[0]
    assert "brand_new_bg_task" not in set(params[1])


# ── B: fail-open ────────────────────────────────────────────────────────────
def test_cap_zero_means_unlimited(monkeypatch):
    monkeypatch.setattr(lb, "cap", lambda: 0)
    called = []
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: called.append(1) or 10 ** 12)
    assert lb.allowed() is True
    assert called == [], "무제한이면 소비 조회조차 하지 않는다"


def test_unmeasurable_spend_is_allowed(monkeypatch):
    """조회 실패(-1)면 허용 — 계량 장애가 백그라운드 정지로 번지면 안 된다."""
    monkeypatch.setattr(lb, "cap", lambda: 1000)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: -1)
    assert lb.allowed() is True


def test_query_failure_returns_sentinel(monkeypatch):
    class _Boom:
        def cursor(self):
            raise RuntimeError("pg down")

    assert lb._query_spent(_Boom()) == -1


def test_gate_blocks_only_when_over_cap(monkeypatch):
    monkeypatch.setattr(lb, "cap", lambda: 1000)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 999)
    assert lb.allowed() is True
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 1000)
    assert lb.allowed() is False


# ── D: 캐시 ─────────────────────────────────────────────────────────────────
def test_spend_is_cached_within_ttl(monkeypatch):
    hits = []

    def _q(conn=None):
        hits.append(1)
        return 42

    monkeypatch.setattr(lb, "_query_spent", _q)
    assert lb.spent() == 42
    assert lb.spent() == 42
    assert len(hits) == 1, "TTL 안에서는 PG 를 다시 때리지 않는다"
    assert lb.spent(refresh=True) == 42
    assert len(hits) == 2


def test_unmeasurable_result_is_not_cached(monkeypatch):
    """-1 을 캐시하면 일시 장애가 TTL 동안 굳는다."""
    seq = [-1, 7]
    monkeypatch.setattr(lb, "_query_spent", lambda conn=None: seq.pop(0))
    assert lb.spent() == -1
    assert lb.spent() == 7


# ── snapshot 계약 ───────────────────────────────────────────────────────────
def test_snapshot_reports_exhaustion(monkeypatch):
    monkeypatch.setattr(lb, "cap", lambda: 100)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 100)
    snap = lb.snapshot()
    assert snap["exhausted"] is True and snap["remaining"] == 0
    assert snap["used_ratio"] == 1.0 and snap["enabled"] is True


def test_snapshot_when_unmeasurable(monkeypatch):
    monkeypatch.setattr(lb, "cap", lambda: 100)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: -1)
    snap = lb.snapshot()
    assert snap["measurable"] is False and snap["exhausted"] is False
    assert "remaining" not in snap   # 판정 불가를 0 으로 위장하지 않는다


def test_snapshot_window_is_rolling_24h():
    assert lb._WINDOW_SEC == 24 * 3600


# ── C: 게이트 배선 ──────────────────────────────────────────────────────────
def test_semantic_cluster_defers_on_exhausted_budget(monkeypatch):
    from modules import semantic_cluster as sc
    import shared.resource_budget as rb
    monkeypatch.setattr(rb, "background_enabled", lambda: True)
    monkeypatch.setattr(lb, "cap", lambda: 100)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 100)
    called = []
    monkeypatch.setattr(sc, "_run_cluster_maintenance_inner", lambda conn=None: called.append(1))
    out = sc.run_cluster_maintenance()
    assert out.get("skipped") == "llm_token_budget"
    assert called == [], "예산 소진 시 본체가 실행되면 안 된다"


def test_product_classify_defers_on_exhausted_budget(monkeypatch):
    from modules import product_classify as pc
    import shared.resource_budget as rb
    monkeypatch.setattr(rb, "background_enabled", lambda: True)
    monkeypatch.setattr(lb, "cap", lambda: 100)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 100)
    called = []
    monkeypatch.setattr(pc, "_run_classify_pass_inner", lambda *a, **k: called.append(1))
    out = pc.run_classify_pass()
    assert out.get("skipped") == "llm_token_budget"
    assert called == []


def test_gates_pass_through_when_budget_available(monkeypatch):
    """상한 이내면 종전대로 본체가 돈다(배포 시 동작 동일)."""
    from modules import semantic_cluster as sc
    import shared.resource_budget as rb
    monkeypatch.setattr(rb, "background_enabled", lambda: True)
    monkeypatch.setattr(lb, "cap", lambda: 10 ** 9)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 1)
    called = []
    monkeypatch.setattr(sc, "_run_cluster_maintenance_inner",
                        lambda conn=None: called.append(1) or {"ok": True})
    out = sc.run_cluster_maintenance()
    assert called == [1] and out == {"ok": True}


def test_node_analysis_tick_defers_on_exhausted_budget(monkeypatch):
    """노드 분석 tick 은 claim 전에 예산을 본다 — 잡을 집어온 뒤 막으면 attempts 만 소모된다.

    회귀 방지: 초기 구현이 아직 열리지 않은 PG 연결 변수를 참조해 NameError 를 냈다."""
    from modules import node_analysis as na
    import shared.resource_budget as rb
    monkeypatch.setattr(na, "_cfg_enabled", lambda: True)
    monkeypatch.setattr(rb, "background_enabled", lambda: True)
    monkeypatch.setattr(lb, "cap", lambda: 100)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 100)
    called = []
    monkeypatch.setattr(na, "_rw_conn", lambda conn: called.append(1) or (None, False))
    rep = na._process_pending_inner()
    assert rep.get("skipped") == "llm_token_budget"
    assert called == [], "예산 소진인데 PG 연결을 열고 claim 을 시도했다"


def test_node_analysis_tick_proceeds_when_budget_available(monkeypatch):
    from modules import node_analysis as na
    import shared.resource_budget as rb
    monkeypatch.setattr(na, "_cfg_enabled", lambda: True)
    monkeypatch.setattr(rb, "background_enabled", lambda: True)
    monkeypatch.setattr(lb, "cap", lambda: 10 ** 9)
    monkeypatch.setattr(lb, "spent", lambda conn=None, **k: 1)
    reached = []
    monkeypatch.setattr(na, "_rw_conn", lambda conn: reached.append(1) or (None, False))
    rep = na._process_pending_inner()
    assert rep.get("skipped") != "llm_token_budget"
    assert reached == [1], "예산 여유가 있으면 종전대로 claim 경로까지 간다"


# ── 동시성 (codex P1 회귀 방지) ──────────────────────────────────────────────
def test_slow_query_cannot_overwrite_a_newer_result(monkeypatch):
    """느린 조회가 나중에 끝나며 더 최신인 값을 과거 값으로 덮어쓰면, 최대 TTL 동안 예산 초과를
    허용한다. single-flight 로 동시 조회 자체를 막아 이 race 를 구조적으로 제거한다."""
    import threading

    started = threading.Event()
    release = threading.Event()
    order = []

    def _slow(conn=None):
        order.append("slow-start")
        started.set()
        release.wait(2.0)
        order.append("slow-end")
        return 10_000_000        # 낡은(작은) 값

    monkeypatch.setattr(lb, "_query_spent", _slow)
    t = threading.Thread(target=lambda: lb.spent(refresh=True))
    t.start()
    assert started.wait(2.0)

    # 조회가 진행 중인 동안 들어온 호출은 자기 조회를 새로 내지 않는다.
    monkeypatch.setattr(lb, "_query_spent",
                        lambda conn=None: order.append("second-query") or 20_000_000)
    lb.spent()
    assert "second-query" not in order, "조회 중에 또 조회가 나가면 덮어쓰기 race 가 생긴다"

    release.set()
    t.join(3.0)


def test_inflight_callers_get_cached_value_not_block(monkeypatch):
    """조회 중 호출은 블로킹하지 않고 직전 캐시를 쓴다 — 게이트가 워커를 붙잡으면 안 된다."""
    import threading
    monkeypatch.setattr(lb, "_query_spent", lambda conn=None: 555)
    assert lb.spent() == 555            # 캐시 적재

    held = threading.Event()
    done = threading.Event()

    def _hold(conn=None):
        held.set()
        done.wait(2.0)
        return 999

    monkeypatch.setattr(lb, "_query_spent", _hold)
    t = threading.Thread(target=lambda: lb.spent(refresh=True))
    t.start()
    assert held.wait(2.0)
    assert lb.spent(refresh=True) == 555, "조회 중이면 직전 캐시로 즉시 답한다"
    done.set()
    t.join(3.0)


def test_snapshot_skips_query_when_unlimited(monkeypatch):
    """상한 0 이면 소비를 조회하지 않는다 — PG 장애가 콘솔 지연으로 번지지 않게(codex P2)."""
    monkeypatch.setattr(lb, "cap", lambda: 0)
    hits = []
    monkeypatch.setattr(lb, "_query_spent", lambda conn=None: hits.append(1) or 1)
    snap = lb.snapshot()
    assert hits == [] and snap["enabled"] is False and snap["exhausted"] is False
