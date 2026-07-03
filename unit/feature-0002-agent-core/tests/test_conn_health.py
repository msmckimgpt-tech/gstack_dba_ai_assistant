"""connection health 모니터 + db 게이트 통합 — conn-health-monitor + conn-tristate.

실 DB/네트워크 없이 socket.create_connection + db.probe_datasource 를 monkeypatch 해 동작. 검증:
1. 적응형 timeout: TCP 선검사=AGENT_CONN_TCP_TIMEOUT_MS(현실화) / DB probe base=SLOW×3→×2→cap.
1b. classify: 3단계 분류(성공+빠름=healthy / 성공+느림=unstable / 1회실패=unstable / 연속실패=down).
2. SSRF 차단: 메타데이터/loopback/link-local 차단, 정상 IP 허용.
3. 상태 전이: 빠른성공→healthy / 느린성공→unstable / 1회실패→unstable / 연속실패→down / 복구→healthy.
4. gate(conn-tristate): **down 일 때만** fast-fail / unstable·healthy 는 허용 / 모니터정지+stale→강등.
5. record_foreground_result: ok→healthy / 연결실패→unstable.
6. snapshot: 좌표/비번 비노출.
7. db.connect_with_retry: down→connect 미호출 fast-fail / unstable→연결 시도(차단 안 함) / control-plane 미적용.
8. 모니터: TCP+DB 2단 probe — 빠른성공→healthy / 느린성공→unstable / DB down→unstable|down / prune.
"""

from __future__ import annotations

import socket
import time
from unittest import mock

import pytest

from shared import conn_health as ch
from shared import db


_DS = {"engine": "mysql", "host": "10.9.9.9", "port": 3306, "user": "ro", "password": "p", "key": "ds-a"}


def _key():
    return ch._scope_key_of(_DS)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    ch.stop_monitor()
    ch._reset_state()
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_ENABLED", True)
    monkeypatch.setattr(ch, "AGENT_CONN_PROBE_TIMEOUT_MS_BASE", 100)
    monkeypatch.setattr(ch, "AGENT_CONN_PROBE_TIMEOUT_MS_MAX", 10000)
    monkeypatch.setattr(ch, "AGENT_CONN_TCP_TIMEOUT_MS", 5000)       # conn-tristate: TCP 선검사(콜드/원거리 RTT 흡수, TASK-0290)
    monkeypatch.setattr(ch, "AGENT_CONN_SLOW_MS", 1000)             # conn-tristate: 느림 임계
    monkeypatch.setattr(ch, "AGENT_CONN_DOWN_AFTER_FAILS", 2)       # conn-tristate: 끊김 판정 임계
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTHY_RECHECK_SEC", 30)
    monkeypatch.setattr(ch, "AGENT_CONN_UNSTABLE_RECHECK_SEC", 2)
    monkeypatch.setattr(ch, "AGENT_CONN_UNSTABLE_RECHECK_MAX_SEC", 60)
    monkeypatch.setattr(ch, "AGENT_CONN_STALE_GRACE_SEC", 60)
    yield
    ch.stop_monitor()
    ch._reset_state()


# ── 1. 적응형 timeout ────────────────────────────────────────────────────────
def test_tcp_timeout_uses_env():
    # conn-tristate: TCP 선검사 timeout 은 구 100ms(BASE)가 아니라 AGENT_CONN_TCP_TIMEOUT_MS(현실화, 기본 5000ms).
    assert ch._tcp_timeout_sec() == pytest.approx(5.0)  # 5000ms (TASK-0290: 콜드/원거리 RTT spike 흡수)


def test_driver_timeout_adaptive():
    # conn-tristate: base = ceil(SLOW×3/1000) = 3 (SLOW=1000) → ×2 backoff → cap 10s.
    assert ch._driver_timeout_sec(0) == 3
    assert ch._driver_timeout_sec(1) == 6
    assert ch._driver_timeout_sec(2) == 10   # 12 → cap 10
    assert ch._driver_timeout_sec(20) == 10  # cap


def test_unstable_recheck_backoff():
    assert ch._unstable_recheck_sec(1) == pytest.approx(2.0)   # base
    assert ch._unstable_recheck_sec(2) == pytest.approx(4.0)
    assert ch._unstable_recheck_sec(20) == pytest.approx(60.0)  # cap


# ── 1b. classify (3단계 단일 분류) ───────────────────────────────────────────
def test_classify_three_states():
    assert ch.classify(True, 500.0, 0) == ch.HEALTHY     # 성공 + 빠름(< SLOW)
    assert ch.classify(True, 1745.0, 0) == ch.UNSTABLE   # 성공 + 느림(>= SLOW) → 불안정
    assert ch.classify(True, 1000.0, 0) == ch.UNSTABLE   # 경계(== SLOW)는 불안정
    assert ch.classify(True, None, 0) == ch.HEALTHY      # elapsed 미측정 → 성공은 healthy
    assert ch.classify(False, None, 1) == ch.UNSTABLE    # 1회 실패 < DOWN_AFTER_FAILS → blip
    assert ch.classify(False, None, 2) == ch.DOWN        # 연속 실패 >= 임계 → 끊김
    assert ch.classify(False, None, 9) == ch.DOWN


# ── 2. SSRF 차단 ─────────────────────────────────────────────────────────────
def _patch_resolve(monkeypatch, ip):
    monkeypatch.setattr(ch.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (ip, 0))])


def test_blocked_target_metadata_and_local(monkeypatch):
    for ip in ("169.254.169.254", "127.0.0.1", "169.254.10.10", "::1"):
        _patch_resolve(monkeypatch, ip)
        assert ch._is_blocked_target("evil.example") is True, ip


def test_blocked_target_allows_normal(monkeypatch):
    _patch_resolve(monkeypatch, "10.9.9.9")   # 사설은 허용(운영 정책)
    assert ch._is_blocked_target("db.internal") is False
    _patch_resolve(monkeypatch, "203.0.113.5")
    assert ch._is_blocked_target("db.public") is False
    # 해석 실패 → fail-closed.
    monkeypatch.setattr(ch.socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert ch._is_blocked_target("nope") is True


# ── 3. 상태 전이 ─────────────────────────────────────────────────────────────
def test_apply_result_fast_success_marks_healthy():
    key = _key()
    ch._apply_result(key, _DS, True, 12.0, "", "probe-db")
    e = ch._STATE[key]
    assert e["status"] == ch.HEALTHY and e["fails"] == 0


def test_apply_result_slow_success_marks_unstable():
    # conn-tristate 핵심: 연결은 성공(1745ms)했지만 SLOW(1000ms) 이상 → unstable(빨강), down 아님.
    key = _key()
    ch._apply_result(key, _DS, True, 1745.0, "", "probe-db")
    e = ch._STATE[key]
    assert e["status"] == ch.UNSTABLE and e["fails"] == 0
    assert e["last_elapsed_ms"] == pytest.approx(1745.0)


def test_apply_result_consecutive_fails_marks_down():
    key = _key()
    ch._apply_result(key, _DS, False, 0.0, "timeout", "probe-tcp")
    assert ch._STATE[key]["status"] == ch.UNSTABLE and ch._STATE[key]["fails"] == 1  # 1회=blip
    ch._apply_result(key, _DS, False, 0.0, "timeout", "probe-tcp")
    assert ch._STATE[key]["status"] == ch.DOWN and ch._STATE[key]["fails"] == 2       # 연속=끊김
    # 복구 — 성공하면 fails 리셋 + healthy.
    ch._apply_result(key, _DS, True, 5.0, "", "probe-db")
    e = ch._STATE[key]
    assert e["status"] == ch.HEALTHY and e["fails"] == 0


# ── 4. gate(conn-tristate: down 일 때만 fast-fail) ───────────────────────────
def _set_status(status, checked_at, fails=3):
    ch._STATE[_key()] = {"status": status, "checked_at": checked_at, "fails": fails,
                         "host": "h", "port": 3306, "engine": "mysql", "label": "ds-a",
                         "next_due": 0, "last_elapsed_ms": None, "last_error": "x", "source": "probe-tcp"}


def test_gate_fast_fail_only_when_down():
    _set_status(ch.DOWN, time.time())
    assert ch.should_fast_fail(_key()) is True


def test_gate_unstable_does_not_fast_fail():
    # Q2(연결되면 허용): 느림/간헐(unstable)은 차단하지 않고 실제 연결을 시도하게 둔다.
    _set_status(ch.UNSTABLE, time.time())
    assert ch.should_fast_fail(_key()) is False


def test_gate_healthy_allows():
    _set_status(ch.HEALTHY, time.time(), fails=0)
    assert ch.should_fast_fail(_key()) is False


def test_gate_stale_down_allows_when_monitor_down():
    _set_status(ch.DOWN, time.time() - 9999)  # 모니터 미가동(fixture stop) + stale → unknown 강등.
    assert ch.should_fast_fail(_key()) is False


def test_gate_trusts_down_when_monitor_running(monkeypatch):
    _set_status(ch.DOWN, time.time() - 9999)  # stale 이어도 모니터 가동 중이면 신뢰(복구는 background).
    monkeypatch.setattr(ch, "monitor_running", lambda: True)
    assert ch.should_fast_fail(_key()) is True


def test_gate_disabled(monkeypatch):
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_ENABLED", False)
    _set_status(ch.DOWN, time.time())
    assert ch.should_fast_fail(_key()) is False


# ── 5. foreground feedback ───────────────────────────────────────────────────
def test_record_foreground_result():
    ch.record_foreground_result(_DS, ok=False, err="errno=2003")
    assert ch._STATE[_key()]["status"] == ch.UNSTABLE  # 1회 실패 = blip
    ch.record_foreground_result(_DS, ok=True)
    assert ch._STATE[_key()]["status"] == ch.HEALTHY


# ── 6. snapshot 비노출 ───────────────────────────────────────────────────────
def test_snapshot_hides_coordinates():
    ch.record_foreground_result(_DS, ok=True, elapsed_ms=3.2)
    entry = ch.snapshot()[_key()]
    # ds-avg-latency: 평균 응답시간(avg_elapsed_ms) + 표본 수(sample_count)를 노출 집합에 추가.
    # 좌표/비번은 여전히 비노출 — 신규 키는 timing aggregate 만이라 누출 불변식 유지.
    assert set(entry.keys()) == {"label", "engine", "status", "last_elapsed_ms", "avg_elapsed_ms",
                                 "sample_count", "checked_at", "last_error", "fails"}
    assert "10.9.9.9" not in str(entry) and "password" not in entry and "p" != entry.get("label")


# ── 6b. 평균 연결 응답 시간(ds-avg-latency) ──────────────────────────────────
def test_avg_elapsed_accumulates_over_probe_db():
    """성공 background DB probe elapsed 가 window 산술평균으로 누적된다."""
    key = _key()
    for ms in (10.0, 20.0, 30.0):
        ch._apply_result(key, _DS, True, ms, "", "probe-db")
    e = ch._STATE[key]
    assert e["avg_elapsed_ms"] == pytest.approx(20.0)   # (10+20+30)/3
    snap = ch.snapshot()[key]
    assert snap["avg_elapsed_ms"] == pytest.approx(20.0)
    assert snap["sample_count"] == 3
    assert snap["last_elapsed_ms"] == pytest.approx(30.0)  # 순간값은 마지막 probe


def test_avg_window_is_bounded(monkeypatch):
    """window(AGENT_CONN_AVG_WINDOW) 초과 시 가장 오래된 표본이 밀려나 최근 N개만 평균."""
    monkeypatch.setattr(ch, "AGENT_CONN_AVG_WINDOW", 3)
    key = _key()
    for ms in (100.0, 100.0, 100.0, 40.0, 40.0, 40.0):  # 마지막 3개(40)만 남아야 함
        ch._apply_result(key, _DS, True, ms, "", "probe-db")
    assert ch._STATE[key]["avg_elapsed_ms"] == pytest.approx(40.0)
    assert ch.snapshot()[key]["sample_count"] == 3


def test_avg_excludes_failures_and_foreground():
    """실패 probe·foreground 성공(elapsed 미측정)은 응답시간 표본에서 제외된다."""
    key = _key()
    ch._apply_result(key, _DS, False, 8000.0, "timeout", "probe-tcp")   # 실패 — 제외
    ch.record_foreground_result(_DS, ok=True)                            # foreground(0.0) — 제외
    assert ch._STATE[key]["avg_elapsed_ms"] is None
    assert ch.snapshot()[key]["sample_count"] == 0
    ch._apply_result(key, _DS, True, 50.0, "", "probe-db")               # 진짜 성공 probe — 포함
    assert ch._STATE[key]["avg_elapsed_ms"] == pytest.approx(50.0)
    assert ch.snapshot()[key]["sample_count"] == 1


def test_avg_includes_slow_success():
    """느린 성공(unstable)도 응답시간은 유효 — 표본에 포함된다."""
    key = _key()
    ch._apply_result(key, _DS, True, 1745.0, "", "probe-db")   # 성공이지만 SLOW 이상 → unstable
    e = ch._STATE[key]
    assert e["status"] == ch.UNSTABLE
    assert e["avg_elapsed_ms"] == pytest.approx(1745.0)


def test_prune_removes_samples():
    """prune 시 상태뿐 아니라 응답시간 표본(_SAMPLES)도 정리된다(메모리 누수 방지)."""
    key = _key()
    ch._apply_result(key, _DS, True, 10.0, "", "probe-db")
    assert key in ch._SAMPLES
    ch._prune_state(set())          # keep 없음 → 전부 prune
    assert key not in ch._SAMPLES and key not in ch._STATE


# ── 7. db.connect_with_retry 통합 ────────────────────────────────────────────
def test_connect_fast_fails_when_down(monkeypatch):
    _set_status(ch.DOWN, time.time())
    m_connect = mock.Mock()
    monkeypatch.setattr(db, "connect", m_connect)
    with pytest.raises(db.DatasourceCircuitOpen):
        db.connect_with_retry(datasource=_DS, attempts=3)
    m_connect.assert_not_called()


def test_connect_does_not_fast_fail_when_unstable(monkeypatch):
    # conn-tristate Q2: unstable(느림)은 fast-fail 하지 않고 실제 연결을 시도 → 성공 시 healthy 복구.
    _set_status(ch.UNSTABLE, time.time())
    monkeypatch.setattr(db, "connect", lambda **_k: mock.sentinel.conn)
    assert db.connect_with_retry(datasource=_DS, attempts=1) is mock.sentinel.conn
    assert ch._STATE[_key()]["status"] == ch.HEALTHY


def test_connect_healthy_feeds_back(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda **_k: mock.sentinel.conn)
    assert db.connect_with_retry(datasource=_DS, attempts=1) is mock.sentinel.conn
    assert ch._STATE[_key()]["status"] == ch.HEALTHY


def test_connect_failure_marks_unstable(monkeypatch):
    from mysql.connector.errors import OperationalError
    monkeypatch.setattr(db, "connect",
                        lambda **_k: (_ for _ in ()).throw(OperationalError(errno=2003, msg="Can't connect")))
    monkeypatch.setattr(db.time, "sleep", lambda *_a, **_k: None)
    with pytest.raises(OperationalError):
        db.connect_with_retry(datasource=_DS, attempts=2)
    # 모든 시도 소진 후 1회 unstable 피드백(fails=1 → blip).
    assert ch._STATE[_key()]["status"] == ch.UNSTABLE


def test_connect_auth_failure_not_unstable(monkeypatch):
    from mysql.connector.errors import OperationalError
    monkeypatch.setattr(db, "connect",
                        lambda **_k: (_ for _ in ()).throw(OperationalError(errno=1045, msg="Access denied")))
    with pytest.raises(OperationalError):
        db.connect_with_retry(datasource=_DS, attempts=3)
    assert _key() not in ch._STATE or ch._STATE[_key()]["status"] not in (ch.UNSTABLE, ch.DOWN)


def test_control_plane_no_gate(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda **_k: mock.sentinel.mem)
    assert db.connect_with_retry(database="agent_memory", attempts=1) is mock.sentinel.mem
    assert not ch._STATE


# ── 8. 모니터: TCP+DB 2단 probe ──────────────────────────────────────────────
def _wait_status(target, deadline_sec=3.0):
    deadline = time.time() + deadline_sec
    while time.time() < deadline:
        e = ch._STATE.get(_key())
        if e and e["status"] in (target if isinstance(target, tuple) else (target,)):
            return e["status"]
        time.sleep(0.05)
    return (ch._STATE.get(_key()) or {}).get("status")


def test_monitor_two_stage_probe_marks_healthy(monkeypatch):
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_TICK_SEC", 1)
    monkeypatch.setattr(ch.socket, "create_connection", lambda *a, **k: mock.Mock())  # TCP ok
    monkeypatch.setattr(ch.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.9.9.9", 0))])
    monkeypatch.setattr(db, "probe_datasource", lambda ds, timeout=None: (True, 2.0, ""))  # DB ok, 빠름
    ch.start_monitor(lambda: [_DS])
    try:
        assert _wait_status(ch.HEALTHY) == ch.HEALTHY
        assert ch.monitor_running() is True
    finally:
        ch.stop_monitor()
    assert ch.monitor_running() is False


def test_monitor_slow_connect_marks_unstable(monkeypatch):
    """conn-tristate: TCP+DB 연결은 성공이지만 elapsed >= SLOW → unstable(느림), healthy 아님."""
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_TICK_SEC", 1)
    monkeypatch.setattr(ch.socket, "create_connection", lambda *a, **k: mock.Mock())  # TCP ok
    monkeypatch.setattr(ch.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.9.9.9", 0))])
    monkeypatch.setattr(db, "probe_datasource", lambda ds, timeout=None: (True, 1745.0, ""))  # 연결됨 but 느림
    ch.start_monitor(lambda: [_DS])
    try:
        assert _wait_status(ch.UNSTABLE) == ch.UNSTABLE
        assert ch._STATE[_key()]["last_elapsed_ms"] == pytest.approx(1745.0)
    finally:
        ch.stop_monitor()


def test_monitor_tcp_open_db_down_marks_unstable_or_down(monkeypatch):
    """B1 회귀 — TCP 는 열렸지만 실제 DB 연결 실패면 정상(healthy) 아님(unstable→연속 시 down)."""
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_TICK_SEC", 1)
    monkeypatch.setattr(ch.socket, "create_connection", lambda *a, **k: mock.Mock())  # TCP ok
    monkeypatch.setattr(ch.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.9.9.9", 0))])
    monkeypatch.setattr(db, "probe_datasource", lambda ds, timeout=None: (False, 8000.0, "errno=1040"))  # DB down
    ch.start_monitor(lambda: [_DS])
    try:
        st = _wait_status((ch.UNSTABLE, ch.DOWN))
        assert st in (ch.UNSTABLE, ch.DOWN)  # TCP ok 였어도 DB down → healthy 아님
    finally:
        ch.stop_monitor()


def test_prune_removes_deregistered():
    ch._STATE["mysql-gone"] = {"status": ch.HEALTHY, "checked_at": 0, "fails": 0,
                               "host": "h", "port": 3306, "engine": "mysql", "label": "gone",
                               "next_due": 0, "last_elapsed_ms": None, "last_error": "", "source": "probe-db"}
    ch.register(_DS)
    ch._prune_state({_key()})
    assert "mysql-gone" not in ch._STATE and _key() in ch._STATE
