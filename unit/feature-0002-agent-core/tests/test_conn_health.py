"""connection health 모니터 + db 게이트 통합 — TASK: conn-health-monitor.

실 DB/네트워크 없이 socket.create_connection + db.probe_datasource 를 monkeypatch 해 동작. 검증:
1. 적응형 timeout: TCP 선검사 base(100ms) / DB probe 1s→×2→max / unstable recheck backoff.
2. SSRF 차단: 메타데이터/loopback/link-local 차단, 정상 IP 허용.
3. 상태 전이: 성공→healthy(reset), 실패→unstable(backoff next_due).
4. gate: unstable→fast-fail / 모니터 가동 시 unstable 신뢰 / 모니터 정지+stale→unknown 강등.
5. record_foreground_result: ok→healthy / 연결실패→unstable.
6. snapshot: 좌표/비번 비노출.
7. db.connect_with_retry: unstable→connect 미호출 fast-fail / healthy 성공 피드백 / control-plane 미적용.
8. 모니터: TCP+DB 2단 probe 로 healthy 판정, prune, start/stop(daemon).
"""

from __future__ import annotations

import socket
import time
from unittest import mock

import pytest

from modules import conn_health as ch
from modules import db


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
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTHY_RECHECK_SEC", 30)
    monkeypatch.setattr(ch, "AGENT_CONN_UNSTABLE_RECHECK_SEC", 2)
    monkeypatch.setattr(ch, "AGENT_CONN_UNSTABLE_RECHECK_MAX_SEC", 60)
    monkeypatch.setattr(ch, "AGENT_CONN_STALE_GRACE_SEC", 60)
    yield
    ch.stop_monitor()
    ch._reset_state()


# ── 1. 적응형 timeout ────────────────────────────────────────────────────────
def test_tcp_timeout_is_base():
    assert ch._tcp_timeout_sec() == pytest.approx(0.1)  # 100ms 고정


def test_driver_timeout_adaptive():
    assert ch._driver_timeout_sec(0) == 1       # base 1s
    assert ch._driver_timeout_sec(1) == 2
    assert ch._driver_timeout_sec(2) == 4
    assert ch._driver_timeout_sec(20) == 10      # cap 10s


def test_unstable_recheck_backoff():
    assert ch._unstable_recheck_sec(1) == pytest.approx(2.0)   # base
    assert ch._unstable_recheck_sec(2) == pytest.approx(4.0)
    assert ch._unstable_recheck_sec(20) == pytest.approx(60.0)  # cap


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
def test_apply_result_transitions():
    key = _key()
    ch._apply_result(key, _DS, False, 12.0, "timeout", "probe-tcp")
    e = ch._STATE[key]
    assert e["status"] == ch.UNSTABLE and e["fails"] == 1
    assert e["next_due"] > time.time()  # backoff 예약
    ch._apply_result(key, _DS, False, 12.0, "timeout", "probe-tcp")
    assert ch._STATE[key]["fails"] == 2
    ch._apply_result(key, _DS, True, 3.0, "", "probe-db")
    e = ch._STATE[key]
    assert e["status"] == ch.HEALTHY and e["fails"] == 0


# ── 4. gate ──────────────────────────────────────────────────────────────────
def _set_unstable(checked_at):
    ch._STATE[_key()] = {"status": ch.UNSTABLE, "checked_at": checked_at, "fails": 3,
                         "host": "h", "port": 3306, "engine": "mysql", "label": "ds-a",
                         "next_due": 0, "last_elapsed_ms": None, "last_error": "x", "source": "probe-tcp"}


def test_gate_fast_fail_when_unstable_fresh():
    _set_unstable(time.time())
    assert ch.should_fast_fail(_key()) is True


def test_gate_healthy_allows():
    ch._STATE[_key()] = {"status": ch.HEALTHY, "checked_at": time.time(), "fails": 0,
                         "host": "h", "port": 3306, "engine": "mysql", "label": "ds-a",
                         "next_due": 0, "last_elapsed_ms": 1, "last_error": "", "source": "probe-db"}
    assert ch.should_fast_fail(_key()) is False


def test_gate_stale_allows_when_monitor_down():
    _set_unstable(time.time() - 9999)  # 모니터 미가동(fixture stop) + stale → unknown 강등.
    assert ch.should_fast_fail(_key()) is False


def test_gate_trusts_unstable_when_monitor_running(monkeypatch):
    _set_unstable(time.time() - 9999)  # stale 이어도 모니터 가동 중이면 신뢰(복구는 background).
    monkeypatch.setattr(ch, "monitor_running", lambda: True)
    assert ch.should_fast_fail(_key()) is True


def test_gate_disabled(monkeypatch):
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_ENABLED", False)
    _set_unstable(time.time())
    assert ch.should_fast_fail(_key()) is False


# ── 5. foreground feedback ───────────────────────────────────────────────────
def test_record_foreground_result():
    ch.record_foreground_result(_DS, ok=False, err="errno=2003")
    assert ch._STATE[_key()]["status"] == ch.UNSTABLE
    ch.record_foreground_result(_DS, ok=True)
    assert ch._STATE[_key()]["status"] == ch.HEALTHY


# ── 6. snapshot 비노출 ───────────────────────────────────────────────────────
def test_snapshot_hides_coordinates():
    ch.record_foreground_result(_DS, ok=True, elapsed_ms=3.2)
    entry = ch.snapshot()[_key()]
    assert set(entry.keys()) == {"label", "engine", "status", "last_elapsed_ms", "checked_at", "last_error", "fails"}
    assert "10.9.9.9" not in str(entry) and "password" not in entry and "p" != entry.get("label")


# ── 7. db.connect_with_retry 통합 ────────────────────────────────────────────
def test_connect_fast_fails_when_unstable(monkeypatch):
    _set_unstable(time.time())
    m_connect = mock.Mock()
    monkeypatch.setattr(db, "connect", m_connect)
    with pytest.raises(db.DatasourceCircuitOpen):
        db.connect_with_retry(datasource=_DS, attempts=3)
    m_connect.assert_not_called()


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
    assert ch._STATE[_key()]["status"] == ch.UNSTABLE


def test_connect_auth_failure_not_unstable(monkeypatch):
    from mysql.connector.errors import OperationalError
    monkeypatch.setattr(db, "connect",
                        lambda **_k: (_ for _ in ()).throw(OperationalError(errno=1045, msg="Access denied")))
    with pytest.raises(OperationalError):
        db.connect_with_retry(datasource=_DS, attempts=3)
    assert _key() not in ch._STATE or ch._STATE[_key()]["status"] != ch.UNSTABLE


def test_control_plane_no_gate(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda **_k: mock.sentinel.mem)
    assert db.connect_with_retry(database="agent_memory", attempts=1) is mock.sentinel.mem
    assert not ch._STATE


# ── 8. 모니터: TCP+DB 2단 probe ──────────────────────────────────────────────
def test_monitor_two_stage_probe_marks_healthy(monkeypatch):
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_TICK_SEC", 1)
    monkeypatch.setattr(ch.socket, "create_connection", lambda *a, **k: mock.Mock())  # TCP ok
    monkeypatch.setattr(ch.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.9.9.9", 0))])
    monkeypatch.setattr(db, "probe_datasource", lambda ds, timeout=None: (True, 2.0, ""))  # DB ok
    ch.start_monitor(lambda: [_DS])
    try:
        deadline = time.time() + 3.0
        while time.time() < deadline:
            e = ch._STATE.get(_key())
            if e and e["status"] == ch.HEALTHY:
                break
            time.sleep(0.05)
        assert ch.monitor_running() is True
        assert ch._STATE[_key()]["status"] == ch.HEALTHY
    finally:
        ch.stop_monitor()
    assert ch.monitor_running() is False


def test_monitor_tcp_open_db_down_marks_unstable(monkeypatch):
    """B1 회귀 — TCP 는 열렸지만 실제 DB 연결 실패면 unstable(TCP-only 오판 방지)."""
    monkeypatch.setattr(ch, "AGENT_CONN_HEALTH_TICK_SEC", 1)
    monkeypatch.setattr(ch.socket, "create_connection", lambda *a, **k: mock.Mock())  # TCP ok
    monkeypatch.setattr(ch.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.9.9.9", 0))])
    monkeypatch.setattr(db, "probe_datasource", lambda ds, timeout=None: (False, 8000.0, "errno=1040"))  # DB down
    ch.start_monitor(lambda: [_DS])
    try:
        deadline = time.time() + 3.0
        while time.time() < deadline:
            e = ch._STATE.get(_key())
            if e and e["status"] == ch.UNSTABLE:
                break
            time.sleep(0.05)
        assert ch._STATE[_key()]["status"] == ch.UNSTABLE  # TCP ok 였어도 DB down → unstable
    finally:
        ch.stop_monitor()


def test_prune_removes_deregistered():
    ch._STATE["mysql-gone"] = {"status": ch.HEALTHY, "checked_at": 0, "fails": 0,
                               "host": "h", "port": 3306, "engine": "mysql", "label": "gone",
                               "next_due": 0, "last_elapsed_ms": None, "last_error": "", "source": "probe-db"}
    ch.register(_DS)
    ch._prune_state({_key()})
    assert "mysql-gone" not in ch._STATE and _key() in ch._STATE
