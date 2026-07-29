"""데이터플레인 연결 liveness·재연결 (FR-dataplane-conn-stale-no-reconnect).

재현한 사고: run 시작에 수립한 데이터플레인 연결이 그 run 의 모든 tool 호출에 재사용되는데,
(a) 첫 tool 까지 LLM 추론이 수 분 걸려 유휴 절단, (b) 쿼리 타임아웃이 세션을 죽임 — 두 경로
어느 쪽이든 죽고 나면 남은 tool 이 전부 드라이버 문구(`Not connected to any MS SQL server`)로
실패해 run 이 통째로 무너졌다(라이브 실측: 유휴 60~120초에 절단, 대조 datasource 는 생존).

합격선:
  1. 유휴 임계를 넘긴 죽은 연결은 사용 직전 **같은 좌표로** 재연결된다.
  2. 임계 안이면 ping 왕복이 0 이다(정상 경로 오버헤드 없음).
  3. 재연결은 **호출측이 준 콜백 하나**로만 이뤄진다 — 다른 datasource/DB 로 폴백하지 않는다.
  4. 재연결 실패는 삼키지 않고 전파(fail-closed)한다.
  5. 죽은 연결 오류 문구는 "쿼리를 좁혀라" 가 아니라 "연결이 끊겼다·그대로 재시도" 로 나간다.
실 DB 없이 double 로 검증(test_multi_datasource 패턴).
"""
import pytest

from modules import tools as T


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, *a, **kw):
        self._conn.executed.append(sql)
        if self._conn.dead:
            raise RuntimeError("Not connected to any MS SQL server")

    def fetchall(self):
        return [(1,)]

    def close(self):
        pass


class _FakeConn:
    """pymssql/mysql.connector 공통 최소 계약(cursor/execute/fetchall/close)."""

    def __init__(self, name: str, dead: bool = False):
        self.name = name
        self.dead = dead
        self.executed: list[str] = []
        self.closed = False

    def cursor(self):
        if self.dead:
            raise RuntimeError("Not connected to any MS SQL server")
        return _FakeCursor(self)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_ping_threshold(monkeypatch):
    """임계는 테스트마다 명시 — 운영 기본값(30s)에 결과가 흔들리지 않게."""
    import shared.config as cfg
    monkeypatch.setattr(cfg, "AGENT_DS_CONN_PING_IDLE_SEC", 30.0, raising=False)


# ── 1. 유휴 후 죽은 연결 → 같은 좌표로 재연결 ────────────────────────────────
def test_dead_conn_after_idle_is_reconnected():
    dead = _FakeConn("old", dead=True)
    fresh = _FakeConn("new")
    calls = []

    def _reconnect():
        calls.append(1)
        return fresh

    # 최초 사용(_agent_last_used_at 미설정) → 반드시 ping. 사고의 (a) 지점.
    got, reconnected = T._ensure_live_conn(dead, _reconnect, label="ds-a")

    assert reconnected is True
    assert got is fresh
    assert calls == [1]          # 재연결 정확히 1회
    assert dead.closed is True   # 죽은 소켓 회수


def test_live_conn_after_idle_is_kept():
    live = _FakeConn("live")
    got, reconnected = T._ensure_live_conn(live, lambda: pytest.fail("재연결 금지"))
    assert reconnected is False
    assert got is live
    assert live.executed == ["SELECT 1"]   # ping 1회만


# ── 2. 임계 안이면 ping 자체를 안 한다(정상 경로 오버헤드 0) ──────────────────
def test_recent_use_skips_ping_entirely():
    live = _FakeConn("live")
    T._mark_conn_used(live)   # 방금 성공 사용

    got, reconnected = T._ensure_live_conn(live, lambda: pytest.fail("재연결 금지"))

    assert got is live
    assert reconnected is False
    assert live.executed == []   # 왕복 0


def test_zero_threshold_always_pings(monkeypatch):
    import shared.config as cfg
    monkeypatch.setattr(cfg, "AGENT_DS_CONN_PING_IDLE_SEC", 0.0, raising=False)
    live = _FakeConn("live")
    T._mark_conn_used(live)

    T._ensure_live_conn(live, lambda: pytest.fail("재연결 금지"))

    assert live.executed == ["SELECT 1"]


# ── 3. 콜백 미주입이면 동작 0 변경(레거시 호출·테스트 double) ──────────────────
def test_no_reconnect_fn_is_noop():
    dead = _FakeConn("old", dead=True)
    got, reconnected = T._ensure_live_conn(dead, None)
    assert got is dead
    assert reconnected is False
    assert dead.closed is False


# ── 4. 재연결 실패는 전파(fail-closed — 다른 좌표 폴백 없음) ──────────────────
def test_reconnect_failure_propagates():
    dead = _FakeConn("old", dead=True)

    def _boom():
        raise RuntimeError("circuit open")

    with pytest.raises(RuntimeError, match="circuit open"):
        T._ensure_live_conn(dead, _boom)


# ── 5. 라우터: 캐시된 죽은 연결을 갱신하고, 좌표는 그 label 것만 쓴다 ──────────
def test_router_conn_for_replaces_dead_cached_conn():
    ds_a = {"key": "ds-a", "_label": "a", "engine": "mssql"}
    ds_b = {"key": "ds-b", "_label": "b", "engine": "mysql"}
    made: list[str] = []

    def _connect(ds_dict):
        made.append(ds_dict["key"])
        return _FakeConn(ds_dict["key"])

    router = T._DatasourceRouter([ds_a, ds_b], _connect)
    first = router.conn_for("a")
    assert made == ["ds-a"]

    first.dead = True                 # 유휴/타임아웃으로 사망
    T._mark_conn_suspect(first)       # execute_tool 이 끊김 오류를 보고 남기는 표시
    second = router.conn_for("a")

    assert second is not first
    assert made == ["ds-a", "ds-a"]   # **같은 좌표로만** 재연결 (ds-b 로 새지 않음)
    assert router.conn_for("a") is second   # 캐시 갱신 — 매 호출 churn 없음


# ── 6. 단일 경로 holder: 소유권 이전으로 다음 호출도 새 연결을 받는다 ──────────
def test_dataplane_holder_reconnects_and_owns():
    dead = _FakeConn("old", dead=True)
    fresh = _FakeConn("new")
    holder = T._DataplaneConn(dead, lambda: fresh, label="default")
    T._mark_conn_suspect(dead)      # 끊김 관측(= 사고 (b): 타임아웃 직후 4초 뒤 다음 도구)

    assert holder.conn() is fresh
    assert holder.conn() is fresh   # 두 번째 호출은 재연결 없이 그대로

    holder.close()
    assert fresh.closed is True     # 살아있는 쪽이 회수된다(옛 객체 아님)


def test_holder_first_use_after_long_idle_pings(monkeypatch):
    """사고 (a): run 시작에 연결, 첫 도구까지 수 분 유휴 → 사용 직전 ping 으로 잡힌다."""
    import shared.config as cfg
    monkeypatch.setattr(cfg, "AGENT_DS_CONN_PING_IDLE_SEC", 30.0, raising=False)
    dead = _FakeConn("old", dead=True)
    fresh = _FakeConn("new")
    holder = T._DataplaneConn(dead, lambda: fresh, label="default")
    # 수립 직후 mark 된 시각을 232초 전으로 되돌린다(실측 gap).
    import time as _t
    dead._agent_last_used_at = _t.monotonic() - 232.0

    assert holder.conn() is fresh


def test_suspect_beats_idle_threshold():
    """사고 (b): 임계(30s) 안이어도 끊김이 관측됐으면 반드시 ping — 실측 재호출 간격은 4초였다."""
    dead = _FakeConn("old", dead=True)
    T._mark_conn_used(dead)          # 방금 사용 → 평소라면 ping 생략
    T._mark_conn_suspect(dead)       # 그러나 끊김 관측
    assert T._conn_needs_ping(dead) is True


def test_note_conn_outcome_marks_suspect_on_error_text():
    """핸들러가 예외를 삼키고 오류 **문구**로 돌려주는 경로도 끊김을 놓치지 않는다."""
    conn = _FakeConn("c")
    T._mark_conn_used(conn)
    T._note_conn_outcome(conn, "루틴 정의 조회 오류: Not connected to any MS SQL server")
    assert T._conn_needs_ping(conn) is True


def test_note_conn_outcome_keeps_normal_result():
    conn = _FakeConn("c")
    T._note_conn_outcome(conn, "## `db`.`dbo`.`T` 구조\n| column | type |")
    assert T._conn_needs_ping(conn) is False


# ── 7. 죽은 연결 오류 문구 — "쿼리를 좁혀라" 오도 금지 ────────────────────────
@pytest.mark.parametrize("text", [
    "Not connected to any MS SQL server",
    "DB-Lib error message 20047: DBPROCESS is dead or not enabled",
    "Adaptive Server connection timed out",
    "MySQL server has gone away",
    "Lost connection to MySQL server during query",
    "MySQL Connection not available",
])
def test_dead_conn_signatures_detected(text):
    assert T.is_dead_conn_error(text) is True


def test_non_dead_conn_error_not_detected():
    assert T.is_dead_conn_error("Unknown column 'x' in 'field list'") is False


def test_dead_conn_error_text_is_actionable():
    msg = T._dataplane_error_text(RuntimeError("Not connected to any MS SQL server"))
    assert "연결이 끊겨" in msg
    assert "그대로 다시 시도" in msg
    # 쿼리 축소 유도 금지(사고의 2차 오도) — 언급하더라도 "필요 없다" 는 부정형이어야 한다.
    assert "좁히거나 대상을 바꿀 필요 없습니다" in msg
    assert "단정하지 마세요" in msg   # 부재 단정 방지(허위 부재 재생산 차단)


def test_other_error_text_preserved():
    msg = T._dataplane_error_text(RuntimeError("Unknown column 'x'"))
    assert msg == "Unknown column 'x'"


# ── 8. end-to-end: agent_core 등록 → execute_tool → 핸들러 → 다음 tool ────────
#    (§18.8 QA MAJOR — 헬퍼 직접 호출만으로는 실제 배선 계약이 검증되지 않는다.)
@pytest.fixture
def _tool(monkeypatch):
    """execute_tool 배선을 그대로 타되 핸들러만 통제 — 라우터는 비활성(단일 경로)."""
    seen: list = []

    def _handler(conn, args):
        seen.append(conn)
        return args["_result"]() if callable(args.get("_result")) else args.get("_result", "ok")

    monkeypatch.setitem(T._TOOL_HANDLERS, "_probe", _handler)
    monkeypatch.setattr(T, "_ACTIVE_DS_ROUTER", T.contextvars.ContextVar("r", default=None))
    return seen


def test_execute_tool_uses_holder_and_reconnects_on_next_call(_tool, monkeypatch):
    """사고 (b) 전체 사슬: 첫 도구가 끊김 오류 → 다음 도구가 자동 재연결로 복구."""
    dead = _FakeConn("old")
    fresh = _FakeConn("new")
    holder = T._DataplaneConn(dead, lambda: fresh, label="ds")
    token = T.set_active_dataplane_conn(holder)
    try:
        # 1) 첫 도구 — 핸들러가 예외를 삼키고 끊김 **문구**로 반환(실제 per-DB graceful 경로 형태).
        out1 = T.execute_tool(dead, "_probe", {
            "_result": "루틴 정의 조회 오류: Not connected to any MS SQL server"})
        assert "Not connected" in out1
        assert _tool[0] is dead

        # 2) 이제 연결이 실제로 죽는다(서버가 세션 종료).
        dead.dead = True

        # 3) 다음 도구 — 임계(30초) 안이지만 suspect 표시 덕에 ping→재연결되어 **복구**된다.
        out2 = T.execute_tool(dead, "_probe", {"_result": "## 구조\n| column |"})
        assert out2.startswith("## 구조")
        assert _tool[1] is fresh          # 새 연결로 실행됐다
    finally:
        T.reset_active_dataplane_conn(token)


def test_execute_tool_ignores_stale_holder_from_other_run(_tool):
    """§18.8 security: 이전 run 의 holder 가 잔류해도 다른 연결의 도구를 가로채지 않는다."""
    other_run_conn = _FakeConn("run-a")
    stale = T._DataplaneConn(other_run_conn, lambda: pytest.fail("재연결 금지"), label="ds-a")
    token = T.set_active_dataplane_conn(stale)
    try:
        my_conn = _FakeConn("run-b")
        T.execute_tool(my_conn, "_probe", {"_result": "ok"})
        assert _tool[0] is my_conn        # 전달받은 연결로 실행 — stale holder 무시
    finally:
        T.reset_active_dataplane_conn(token)


def test_execute_tool_without_holder_is_unchanged(_tool):
    """holder 미등록(레거시·테스트) → 전달 conn 그대로, ping 도 재연결도 없음(동작 0 변경)."""
    conn = _FakeConn("plain")
    T.execute_tool(conn, "_probe", {"_result": "ok"})
    assert _tool[0] is conn
    assert conn.executed == []


def test_reconnect_reapplies_session_query_cap(monkeypatch):
    """§18.8 backend: 재연결로 새 세션이 열리면 sticky 하던 쿼리 시간 상한을 즉시 재적용한다."""
    import shared.config as cfg
    monkeypatch.setattr(cfg, "AGENT_QUERY_MAX_EXECUTION_MS", 1234, raising=False)
    dead = _FakeConn("old", dead=True)
    fresh = _FakeConn("new")

    got, reconnected = T._ensure_live_conn(dead, lambda: fresh)

    assert reconnected is True and got is fresh
    assert any("max_execution_time = 1234" in s for s in fresh.executed)
