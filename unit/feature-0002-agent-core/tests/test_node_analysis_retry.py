"""analysis-retry-resilience (2026-07-30, 사용자 리포트) 단위 테스트 — 네트워크 단절 회복성.

사용자 리포트: "그래프 뷰에서 AI 능동 분석이 (주기적인 네트워크 단절) 중단될 경우 … 네트워크가 다시
연결되더라도 아무런 작업이 이루어지지 않습니다."

종전 결함: `llm_node_analysis` 가 네트워크 오류·타임아웃·429·빈 응답을 전부 `None` 으로 평탄화하고,
`process_pending` 이 그 `None` 을 즉시 terminal `status='failed'` 로 굳혔다. lease 회수는 `running`
만 대상이라 복구 후 되살아날 행이 없었다.

검증 축 (DB/LLM 불요 — fake·monkeypatch):
  llm.classify_node_analysis_failure
    - 네트워크/타임아웃 예외 = transient(재시도 가치) · bad_model/context_length = permanent
    - 빈 응답·JSON 파싱 실패 = transient(게이트웨이가 5xx 를 빈 본문으로 뭉개는 실측 경로)
    - 클라이언트 미구성 = permanent(사람이 설정을 고쳐야 하므로 예산을 태우지 않는다)
  node_analysis.process_pending
    - 일시 실패는 **pending 되돌림 + attempts+1 + backoff 예약**이고 `runs.failed` 를 올리지 않는다
      (= run 이 running 을 유지해 복구 후 스스로 이어간다 — 본 cycle 의 핵심 계약)
    - 재시도 상한 도달분과 permanent 는 종전대로 terminal `failed` + `runs.failed+1`
    - claim 에 due 게이트(`next_attempt_at`)가 붙고, **0049 미적용 창에서는 붙지 않으며** 종전
      terminal 경로로 폴백한다(마이그레이션 창 무회귀)
    - 대기 잡을 가진 running run 의 `updated_at` 을 매 틱 갱신한다(backoff 대기 중 run 이 lease 를
      넘겨 stale 로 오판돼 **중복 run** 이 생기는 것을 막는 load-bearing 갱신)
    - 회로차단: 연속 일시 실패가 임계에 도달하면 다음 틱 claim 이 canary 1건으로 축소되고,
      성공 1건으로 즉시 정상 배치로 복귀한다
  node_analysis.retry_failed_jobs
    - dry_run 집계 / 실제 회수는 단일 CTE(attempts=0 리셋 + runs.failed 차감 + status='running' 복원)
    - 회수 대상 판정 LIKE 는 **파라미터로** 전달된다(SQL 리터럴 `%` 는 psycopg 포맷과 충돌 — 회귀 가드)
    - 0049 미적용이면 ok=False(조용한 no-op 금지)
  node_analysis.get_run_status
    - retry_waiting / next_attempt_at / retryable_failed 노출, 집계 실패 시 0·None 폴백(폴링 404 없음)
"""
import datetime as _dt

import pytest

from modules import llm
from modules import node_analysis as na


class FakeCursor:
    """패턴 → fetchone/fetchall 응답 매핑 fake (기존 node_analysis 테스트 규약과 동형)."""

    def __init__(self, rows=None):
        self.rows = rows or {}
        self.executed = []
        self.rowcount = 1
        self._last = None
        self.fail_on = None
        # 컬럼 부재(마이그레이션 미적용) 시뮬레이션용 — probe 가 permanent 로 판정하는 문구를 담는다.
        self.fail_exc = None

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.executed.append((flat, params))
        self._last = None
        if self.fail_on and self.fail_on(flat, params):
            raise (self.fail_exc or RuntimeError("simulated failure"))
        for pat, row in self.rows.items():
            if pat in flat:
                self._last = row() if callable(row) else row
                break

    def fetchone(self):
        return self._last

    def fetchall(self):
        if self._last is None:
            return []
        return self._last if isinstance(self._last, list) else [self._last]

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur

    def close(self):
        pass


def _cfg():
    from shared import config as _c
    return _c


_SCOPE = "ds-prod"
_RUN = "run-abc"
_NODE = f"{_SCOPE}:log_v2.player_log"

# claim RETURNING 1행 (refine 컬럼 사용 경로):
#   id, run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, anchor_key, pass_no, analysis
_CLAIMED = [(11, _RUN, _SCOPE, _NODE, "Table", "player_log", "log_v2.player_log", 0, _NODE, 0, None)]


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_ENABLED", True, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_MAX_ATTEMPTS", 4, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_RETRY_BASE_SEC", 60, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_RETRY_MAX_SEC", 600, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_CIRCUIT_FAILS", 3, raising=False)
    # 컬럼 probe 캐시: refine(0038)·retry(0049) 모두 적용된 정상 상태를 기본값으로.
    monkeypatch.setattr(na, "_REFINE_COLS", {"ok": True, "warned": False})
    monkeypatch.setattr(na, "_RETRY_COLS", {"ok": True, "warned": False})
    monkeypatch.setattr(na, "_CIRCUIT", {"fails": 0})
    # 회로차단의 보조 신호(provider health)는 이 테스트 대상이 아니므로 항상 정상으로 고정.
    #   (PG 미가용 환경에서 read_provider_health 가 restricted 를 반환하면 claim 축소가 오작동한다.)
    monkeypatch.setattr(na, "_circuit_open",
                        lambda cfg: bool(cfg.get("circuit_fails")) and na._CIRCUIT["fails"] >= cfg["circuit_fails"])


def _patch_pipeline(monkeypatch, *, llm_result=None, llm_exc=None, sink=None):
    """process_pending 의 그래프·LLM 주변부를 fake 로 대체하고, LLM 결과/실패만 주입한다."""
    monkeypatch.setattr(na, "_ensure_table_columns", lambda c, key: 0)
    monkeypatch.setattr(na, "_fetch_context", lambda key, conn: {
        "root": {"label": "Table", "name": "player_log", "fqn": "log_v2.player_log", "key": key},
        "neighbors": [],
    })
    monkeypatch.setattr(na, "_load_anchor", lambda *a, **k: {"key": _NODE, "prompt": ""})
    monkeypatch.setattr(na, "_build_payload", lambda root, ctx: {"label": "Table", "name": "player_log"})
    monkeypatch.setattr(na, "_latest_done_analysis", lambda *a, **k: None)
    monkeypatch.setattr(na, "_enqueue_neighbors", lambda *a, **k: 0)
    monkeypatch.setattr(na, "_ingest_suggested_links", lambda *a, **k: 0)
    monkeypatch.setattr(na, "_backrefine_neighbors", lambda *a, **k: 0)

    def _fake_llm(payload, *, scope_key=None, error_sink=None):
        if llm_exc is not None:
            raise llm_exc
        if llm_result is None and isinstance(error_sink, dict) and sink:
            error_sink.update(sink)
        return llm_result

    monkeypatch.setattr(na._llm if hasattr(na, "_llm") else llm, "llm_node_analysis", _fake_llm, raising=False)
    monkeypatch.setattr(llm, "llm_node_analysis", _fake_llm)


def _run_tick(monkeypatch, cur, **kw):
    _patch_pipeline(monkeypatch, **kw)
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    return na.process_pending(max_nodes=10)


def _sql_of(cur, needle):
    return [(s, p) for s, p in cur.executed if needle in s]


def _claim_cursor(rows_extra=None):
    rows = {
        "UPDATE node_analysis_jobs SET status='running'": _CLAIMED,
        # run finalize 판정: 남은 잡이 있다고 응답해 마감되지 않게 한다.
        "SELECT COUNT(*) FROM node_analysis_jobs": (1,),
    }
    rows.update(rows_extra or {})
    return FakeCursor(rows)


# ── 실패 분류 ────────────────────────────────────────────────────────────────
def test_classify_network_exception_is_transient():
    info = llm.classify_node_analysis_failure(ConnectionError("Connection reset by peer"))
    assert info["kind"] == llm.FAILURE_TRANSIENT


def test_classify_timeout_is_transient():
    info = llm.classify_node_analysis_failure(TimeoutError("Request timed out"))
    assert info["kind"] == llm.FAILURE_TRANSIENT


def test_classify_empty_response_is_transient():
    info = llm.classify_node_analysis_failure(empty=True)
    assert info["kind"] == llm.FAILURE_TRANSIENT
    assert info["tag"] == "empty_response"


def test_classify_missing_client_is_permanent():
    info = llm.classify_node_analysis_failure(no_client=True)
    assert info["kind"] == llm.FAILURE_PERMANENT
    assert info["tag"] == "no_client"


def test_classify_request_level_error_is_permanent(monkeypatch):
    """bad_model/context_length 처럼 재호출해도 같은 실패는 재시도하지 않는다(예산 보호)."""
    from modules import llm_provider_health as health
    monkeypatch.setattr(health, "classify_llm_provider_error",
                        lambda exc, provider=None: {"kind": "bad_model", "error_tag": "400 bad_model"})
    info = llm.classify_node_analysis_failure(RuntimeError("unknown model"))
    assert info["kind"] == llm.FAILURE_PERMANENT
    assert info["tag"] == "bad_model"


def test_classify_throttle_is_transient(monkeypatch):
    """429/5xx/자격만료는 외부요인 — 시간이 지나면 회복하므로 transient(상한이 무한 재시도를 막는다)."""
    from modules import llm_provider_health as health
    monkeypatch.setattr(health, "classify_llm_provider_error",
                        lambda exc, provider=None: {"kind": "throttled", "error_tag": "429 throttled"})
    info = llm.classify_node_analysis_failure(RuntimeError("Too many requests"))
    assert info["kind"] == llm.FAILURE_TRANSIENT


def test_llm_node_analysis_fills_error_sink_on_missing_client(monkeypatch):
    """error_sink 계약: 실패 원인을 호출측에 전달하되 반환 계약(None)은 불변."""
    monkeypatch.setattr(llm, "_get_llm_client", lambda **kw: None)
    sink: dict = {}
    assert llm.llm_node_analysis({"name": "t"}, error_sink=sink) is None
    assert sink.get("kind") == llm.FAILURE_PERMANENT


# ── 일시 실패 = pending 되돌림 (핵심 계약) ────────────────────────────────────
def test_transient_failure_requeues_instead_of_terminal(monkeypatch):
    cur = _claim_cursor({
        "SET attempts = attempts + 1": ("pending", 1, _dt.datetime(2026, 7, 30, 11, 5)),
    })
    rep = _run_tick(monkeypatch, cur, llm_result=None,
                    sink={"kind": llm.FAILURE_TRANSIENT, "tag": "APIConnectionError"})

    # 잡은 pending 으로 되돌아가고 backoff 가 예약된다.
    upd = _sql_of(cur, "SET attempts = attempts + 1")
    assert upd, "일시 실패는 attempts 를 올리며 재시도 상태로 되돌려야 한다"
    sql = upd[0][0]
    assert "ELSE 'pending' END" in sql
    assert "next_attempt_at" in sql and "make_interval" in sql
    # runs.failed 는 올리지 않는다 — run 이 running 을 유지해야 복구 후 스스로 이어간다.
    assert not _sql_of(cur, "SET failed = failed + 1"), "일시 실패에 terminal 카운터를 올리면 안 된다"
    assert rep["retry_pending"] == 1
    assert rep["failed"] == 0


def test_transient_failure_backoff_is_capped(monkeypatch):
    """backoff = BASE × 2^attempts 이며 MAX 로 캡(LEASE 미만 유지 — dedup stale 오판 방지)."""
    cur = _claim_cursor({"SET attempts = attempts + 1": ("pending", 1, None)})
    _run_tick(monkeypatch, cur, llm_result=None, sink={"kind": llm.FAILURE_TRANSIENT, "tag": "t"})
    _sql, params = _sql_of(cur, "SET attempts = attempts + 1")[0]
    assert 60 in params and 600 in params, f"BASE/MAX 파라미터가 전달되지 않았다: {params}"
    assert 600 < int(getattr(_cfg(), "AGENT_NODE_ANALYSIS_LEASE_SEC", 900))


def test_transient_exhausted_becomes_terminal(monkeypatch):
    """상한 도달(RETURNING status='failed')이면 terminal 로 종결하고 카운터를 올린다."""
    cur = _claim_cursor({"SET attempts = attempts + 1": ("failed", 4, None)})
    rep = _run_tick(monkeypatch, cur, llm_result=None,
                    sink={"kind": llm.FAILURE_TRANSIENT, "tag": "t"})
    assert _sql_of(cur, "SET failed = failed + 1"), "상한 도달분은 terminal 로 계상해야 한다"
    assert rep["failed"] == 1 and rep["retry_pending"] == 0


def test_permanent_failure_is_terminal_without_retry(monkeypatch):
    cur = _claim_cursor()
    rep = _run_tick(monkeypatch, cur, llm_result=None,
                    sink={"kind": llm.FAILURE_PERMANENT, "tag": "bad_model"})
    assert not _sql_of(cur, "ELSE 'pending' END"), "영구 실패를 재시도 큐에 넣으면 예산이 샌다"
    term = _sql_of(cur, "status='failed'")
    assert term and any("error_kind" in s for s, _ in term)
    assert rep["failed"] == 1 and rep["retry_pending"] == 0


def test_exception_path_is_classified_and_requeued(monkeypatch):
    """LLM 호출이 예외로 죽는 경로(단절의 전형)도 분류해 재시도로 되돌린다."""
    cur = _claim_cursor({"SET attempts = attempts + 1": ("pending", 1, None)})
    rep = _run_tick(monkeypatch, cur, llm_exc=ConnectionError("connection refused"))
    assert rep["retry_pending"] == 1 and rep["failed"] == 0


# ── claim 게이트 · 마이그레이션 창 ───────────────────────────────────────────
def test_claim_gates_on_next_attempt_at(monkeypatch):
    cur = _claim_cursor({"SET attempts = attempts + 1": ("pending", 1, None)})
    _run_tick(monkeypatch, cur, llm_result={"summary": "ok"})
    claim = _sql_of(cur, "UPDATE node_analysis_jobs SET status='running'")[0][0]
    assert "next_attempt_at IS NULL OR next_attempt_at <= now()" in claim


def _legacy_cursor(rows_extra=None):
    """0049 미적용 창을 **실제 컬럼 부재로** 시뮬레이션 — probe 가 permanent 로 판정해 legacy 로 폴백한다.
    (캐시 dict 를 직접 조작하면 재-probe 계약(P2-1)을 우회해 검증이 헐거워진다.)"""
    cur = _claim_cursor(rows_extra) if rows_extra is not None else _claim_cursor()
    cur.fail_on = lambda sql, params: "SELECT attempts, next_attempt_at, error_kind" in sql
    cur.fail_exc = RuntimeError('UndefinedColumn: column "attempts" does not exist')
    return cur


def test_legacy_window_keeps_previous_behaviour(monkeypatch):
    """0049 미적용 창: due 게이트를 붙이지 않고, 일시 실패도 종전처럼 terminal 로 기록한다."""
    monkeypatch.setattr(na, "_RETRY_COLS", {"ok": None, "warned": False, "checked_at": 0.0})
    cur = _legacy_cursor()
    rep = _run_tick(monkeypatch, cur, llm_result=None,
                    sink={"kind": llm.FAILURE_TRANSIENT, "tag": "t"})
    claim = _sql_of(cur, "UPDATE node_analysis_jobs SET status='running'")[0][0]
    assert "next_attempt_at" not in claim
    assert not _sql_of(cur, "SET attempts = attempts + 1")
    assert rep["failed"] == 1


def test_stale_reclaim_clears_backoff(monkeypatch):
    """lease 회수는 즉시 재처리 의도 — 남은 backoff 예약을 비워야 due 게이트에 다시 막히지 않는다."""
    cur = _claim_cursor({"SET attempts = attempts + 1": ("pending", 1, None)})
    _run_tick(monkeypatch, cur, llm_result={"summary": "ok"})
    reclaim = [s for s, _ in cur.executed if "status='pending', next_attempt_at=NULL" in s
               and "status='running' AND updated_at <" in s]
    assert reclaim, "stale reclaim 이 next_attempt_at 을 비우지 않으면 회수가 무력해진다"


# ── run liveness (dedup stale 오판 방지) ─────────────────────────────────────
def test_active_run_heartbeat_is_issued(monkeypatch):
    cur = _claim_cursor({"SET attempts = attempts + 1": ("pending", 1, None)})
    _run_tick(monkeypatch, cur, llm_result={"summary": "ok"})
    hb = [s for s, _ in cur.executed
          if "UPDATE node_analysis_runs r SET updated_at = now()" in s]
    assert hb, "대기 잡을 가진 running run 의 liveness 를 갱신하지 않으면 중복 run 이 생긴다"
    assert "status IN ('pending','running')" in hb[0]


# ── 회로차단 ────────────────────────────────────────────────────────────────
def test_circuit_shrinks_batch_to_canary(monkeypatch):
    """연속 일시 실패가 임계면 다음 틱 claim 은 canary 1건 — 단절 창에 큐를 태우지 않는다."""
    na._CIRCUIT["fails"] = 3
    cur = _claim_cursor({"SET attempts = attempts + 1": ("pending", 1, None)})
    _run_tick(monkeypatch, cur, llm_result=None, sink={"kind": llm.FAILURE_TRANSIENT, "tag": "t"})
    _sql, params = _sql_of(cur, "UPDATE node_analysis_jobs SET status='running'")[0]
    assert params[-1] == 1, f"회로차단 중 claim LIMIT 이 축소되지 않았다: {params}"


def test_success_resets_circuit_and_retry_marks(monkeypatch):
    na._CIRCUIT["fails"] = 5
    cur = _claim_cursor()
    rep = _run_tick(monkeypatch, cur, llm_result={"summary": "요약", "relationships": "", "usage": "",
                                                  "caveats": "", "role": "log"})
    assert rep["done"] == 1
    assert na._CIRCUIT["fails"] == 0, "성공 1건이면 즉시 정상 배치로 복귀해야 한다"
    assert _sql_of(cur, "SET error_kind=NULL, next_attempt_at=NULL"), "성공 시 재시도 흔적을 정리해야 한다"


def test_transient_failure_counts_up_circuit(monkeypatch):
    cur = _claim_cursor({"SET attempts = attempts + 1": ("pending", 1, None)})
    _run_tick(monkeypatch, cur, llm_result=None, sink={"kind": llm.FAILURE_TRANSIENT, "tag": "t"})
    assert na._CIRCUIT["fails"] == 1


# ── 굳은 실패 회수 ──────────────────────────────────────────────────────────
def test_retry_failed_jobs_dry_run_counts_only(monkeypatch):
    cur = FakeCursor({"SELECT count(*), count(DISTINCT run_id)": (130, 2)})
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    res = na.retry_failed_jobs(scope_key=_SCOPE, dry_run=True)
    assert res["ok"] and res["dry_run"] and res["retried"] == 130 and res["runs"] == 2
    assert not _sql_of(cur, "UPDATE node_analysis_jobs j SET status='pending'")


def test_retry_failed_jobs_restores_run_counters(monkeypatch):
    cur = FakeCursor({"WITH tgt AS": [( "run-1", 43), ("run-2", 87)]})
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    res = na.retry_failed_jobs(scope_key=_SCOPE)
    assert res["ok"] and res["retried"] == 130 and res["runs"] == 2
    sql = _sql_of(cur, "WITH tgt AS")[0][0]
    assert "attempts=0" in sql and "next_attempt_at=NULL" in sql
    assert "failed = GREATEST(0, r.failed - agg.n)" in sql
    assert "status='running'" in sql, "종결된 run 을 되살리지 않으면 진행 패널 완료율이 어긋난다"


def test_retry_target_predicate_uses_bound_parameters(monkeypatch):
    """LIKE 패턴을 SQL 리터럴로 박으면 psycopg 가 `%` 를 포맷 지시자로 읽어 죽는다(회귀 가드)."""
    cur = FakeCursor({"WITH tgt AS": []})
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    na.retry_failed_jobs(run_id=_RUN)
    sql, params = _sql_of(cur, "WITH tgt AS")[0]
    assert "'transient%'" not in sql and "'LLM %'" not in sql
    assert "transient%" in params and "LLM %" in params


def test_retry_excludes_manual_cleanup_and_permanent(monkeypatch):
    """'verification-cleanup(취소)'·permanent 는 회수 대상이 아니다 — 판정식이 그 둘을 배제한다."""
    assert "error_kind LIKE %s" in na._RETRYABLE_FAILED_SQL
    assert na._RETRYABLE_FAILED_ARGS == ("transient%", "LLM %")
    assert "verification" not in na._RETRYABLE_FAILED_SQL


def test_retry_failed_jobs_requires_migration(monkeypatch):
    cur = FakeCursor()
    cur.fail_on = lambda sql, params: "SELECT attempts, next_attempt_at, error_kind" in sql
    cur.fail_exc = RuntimeError('UndefinedColumn: column "attempts" does not exist')
    monkeypatch.setattr(na, "_RETRY_COLS", {"ok": None, "warned": False, "checked_at": 0.0})
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    res = na.retry_failed_jobs(run_id=_RUN)
    assert res["ok"] is False and "0049" in str(res.get("reason"))
    assert not _sql_of(cur, "WITH tgt AS"), "마이그레이션 미적용에서 회수 SQL 을 쏘면 안 된다"


# ── 진행 상태 노출 ──────────────────────────────────────────────────────────
def test_get_run_status_exposes_retry_fields(monkeypatch):
    at = _dt.datetime(2026, 7, 30, 11, 30)
    cur = FakeCursor({
        "SELECT run_id, scope_key, root_key": (_RUN, _SCOPE, _NODE, "player_log", 2, 150,
                                               "running", 10, 4, 1, "Table"),
        "SELECT node_key, status, role": [(_NODE, "done", "log")],
        "SELECT node_key, node_label, node_name": [(_NODE, "Table", "player_log",
                                                    "log_v2.player_log", "done", 0, 1.0, "log")],
        "count(*) FILTER (WHERE status='pending'": (3, at, 5),
    })
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    st = na.get_run_status(_RUN)
    assert st["retry_waiting"] == 3
    assert st["next_attempt_at"] == at.isoformat()
    assert st["retryable_failed"] == 5


def test_get_run_status_degrades_when_retry_columns_absent(monkeypatch):
    """0049 미적용 창에서도 폴링은 200 이어야 한다(과거 role 컬럼 부재가 404 를 만든 전례)."""
    cur = FakeCursor({
        "SELECT run_id, scope_key, root_key": (_RUN, _SCOPE, _NODE, "player_log", 2, 150,
                                               "running", 10, 4, 1, "Table"),
        "SELECT node_key, status, role": [(_NODE, "done", "log")],
        "SELECT node_key, node_label, node_name": [(_NODE, "Table", "player_log",
                                                    "log_v2.player_log", "done", 0, 1.0, "log")],
    })
    cur.fail_on = lambda sql, params: "count(*) FILTER (WHERE status='pending'" in sql
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    st = na.get_run_status(_RUN)
    assert st is not None and st["run_id"] == _RUN
    assert st["retry_waiting"] == 0 and st["next_attempt_at"] is None and st["retryable_failed"] == 0


# ── codex 적대 리뷰 반영분 (P2, 2026-07-30) ─────────────────────────────────
def test_retry_columns_absence_is_rechecked(monkeypatch):
    """P2-1: 0049 미적용 판정을 **영구 캐시하지 않는다** — 워커가 마이그레이션 전에 기동된 롤링 배포
    창에서 영구 캐시면 마이그레이션 완료 후에도 재시도가 silent 비활성으로 남는다."""
    monkeypatch.setattr(na, "_RETRY_COLS", {"ok": False, "warned": True, "checked_at": 1000.0})
    cur = FakeCursor()

    # 재검사 간격 이내 = 재-probe 하지 않는다(쿼리 낭비 방지).
    monkeypatch.setattr(na.time, "time", lambda: 1000.0 + 10)
    assert na._retry_cols_ok(cur) is False
    assert not [s for s, _ in cur.executed if "SELECT attempts" in s]

    # 간격 경과 후에는 재-probe 하고, 컬럼이 생겼으면 True 로 회복된다.
    monkeypatch.setattr(na.time, "time", lambda: 1000.0 + na._RETRY_COLS_RECHECK_SEC + 1)
    assert na._retry_cols_ok(cur) is True
    assert [s for s, _ in cur.executed if "SELECT attempts" in s]


def test_retry_columns_success_is_cached_permanently(monkeypatch):
    """반대 방향: True 는 재-probe 하지 않는다(컬럼이 사라지는 일은 없다 — 쿼리 낭비 차단)."""
    monkeypatch.setattr(na, "_RETRY_COLS", {"ok": True, "warned": False, "checked_at": 0.0})
    cur = FakeCursor()
    assert na._retry_cols_ok(cur) is True
    assert not cur.executed


def test_dry_run_reports_this_run_and_eligible(monkeypatch):
    """P2-2: 실제 실행은 LIMIT 으로 잘리므로 dry-run 도 **이번 실행량**을 보고해야 한다."""
    cur = FakeCursor({"SELECT count(*), count(DISTINCT run_id)": (130, 2)})
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    res = na.retry_failed_jobs(scope_key=_SCOPE, limit=50, dry_run=True)
    assert res["retried"] == 50, "이번 실행량은 limit 으로 잘린 값"
    assert res["eligible"] == 130 and res["capped"] is True


def test_dry_run_uncapped_reports_equal_counts(monkeypatch):
    cur = FakeCursor({"SELECT count(*), count(DISTINCT run_id)": (12, 1)})
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))
    res = na.retry_failed_jobs(scope_key=_SCOPE, limit=500, dry_run=True)
    assert res["retried"] == 12 and res["eligible"] == 12 and res["capped"] is False


def test_parse_failure_has_distinct_tag():
    """P2-3: 파싱 실패를 빈 응답과 태그로 분리 — 결정적 포맷 오류가 예산을 태우는지 관측 가능하게."""
    parsed = llm.classify_node_analysis_failure(parse_failed=True)
    empty = llm.classify_node_analysis_failure(empty=True)
    assert parsed["tag"] == "json_extract_failed" and empty["tag"] == "empty_response"
    assert parsed["kind"] == empty["kind"] == llm.FAILURE_TRANSIENT
