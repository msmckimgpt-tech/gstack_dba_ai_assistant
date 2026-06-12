"""db.py per-datasource circuit breaker + bounded connect timeout — TASK: ds-connect-isolation.

실 DB 연결 없이 monkeypatch 로 동작. 격리 계약 + 적대 리뷰(REV-20260612 B1/M1/M4/m1) 흡수 검증:
1. _dataplane_connect_timeout: 연결 수립 상한이 쿼리 예산(AGENT_TIMEOUT_SEC)과 분리.
2. _is_connect_breaker_failure: 연결 수립 실패만 카운트(1205 deadlock·인증 1045 제외, 2003 포함).
3. breaker open: 연속 FAIL_THRESHOLD **요청** 실패 시 그 datasource 만 open → 이후 fast-fail.
4. **M1 — 요청당 1회 카운트**: connect_with_retry 의 내부 retry(N attempts)가 breaker 를 1요청에
   threshold 까지 밀어올리지 않음(증폭 차단). THRESHOLD 는 '실패한 요청 수'.
5. **B1 — 단일 half-open trial**: 쿨다운 경과 후 동시 다수 요청 중 **정확히 1개**만 실제 connect
   (thundering herd 차단). 나머지는 fast-fail.
6. half-open trial 성공 close / 실패 re-open + stale 토큰 회수(stuck-open 방지).
7. per-scope_key 격리: X open 이 Y 연결에 무영향.
8. control-plane(datasource=None / key=None) breaker 미적용(동작 0 변경).
9. **m1** — breaker 부기(record) 예외가 connect 결과를 삼키지 않음.
10. connect() data-plane bounded timeout 전달 + DatasourceCircuitOpen no-retry.
"""

from __future__ import annotations

import threading
import time
from unittest import mock

import pytest
from mysql.connector.errors import OperationalError

from modules import db


def _conn_exc():
    """연결 수립(can't connect) 에러 — errno 2003. breaker 카운트 대상."""
    return OperationalError(errno=2003, msg="Can't connect to MySQL server")


def _auth_exc():
    """인증 에러 — errno 1045. fast-fail, breaker 미카운트(retry 도 안 함)."""
    return OperationalError(errno=1045, msg="Access denied for user")


def _deadlock_exc():
    """deadlock — errno 1205. retry 대상이나 연결 수립과 무관 → breaker 미카운트(M4)."""
    return OperationalError(errno=1205, msg="Lock wait timeout / deadlock found")


@pytest.fixture(autouse=True)
def _isolate_breaker(monkeypatch):
    db._reset_breaker_state()
    monkeypatch.setattr(db, "AGENT_DB_BREAKER_ENABLED", True)
    monkeypatch.setattr(db, "AGENT_DB_BREAKER_FAIL_THRESHOLD", 3)
    monkeypatch.setattr(db, "AGENT_DB_BREAKER_COOLDOWN_SEC", 30)
    monkeypatch.setattr(db, "AGENT_DB_CONNECT_TIMEOUT_SEC", 10)
    monkeypatch.setattr(db, "AGENT_DB_CONNECT_RETRIES", 3)
    # backoff 제거(테스트 속도).
    monkeypatch.setattr(db.time, "sleep", lambda *_a, **_k: None)
    yield
    db._reset_breaker_state()


_DS = {"engine": "mysql", "host": "10.0.0.5", "port": 3306, "user": "ro", "password": "p"}


def _key():
    return db._breaker_key(_DS)


# ── 1. bounded connect timeout 분리 ──────────────────────────────────────────
def test_dataplane_connect_timeout_uses_dedicated_value(monkeypatch):
    monkeypatch.setattr(db, "AGENT_DB_CONNECT_TIMEOUT_SEC", 10)
    monkeypatch.setattr(db, "AGENT_TIMEOUT_SEC", 300)
    assert db._dataplane_connect_timeout() == 10


def test_dataplane_connect_timeout_falls_back_when_zero(monkeypatch):
    monkeypatch.setattr(db, "AGENT_DB_CONNECT_TIMEOUT_SEC", 0)
    monkeypatch.setattr(db, "AGENT_TIMEOUT_SEC", 300)
    assert db._dataplane_connect_timeout() == 300


# ── 2. connect-stage 분류 (M4) ───────────────────────────────────────────────
def test_is_connect_breaker_failure_classification():
    assert db._is_connect_breaker_failure(_conn_exc()) is True          # 2003 connect
    assert db._is_connect_breaker_failure(_deadlock_exc()) is False     # 1205 deadlock 제외
    assert db._is_connect_breaker_failure(_auth_exc()) is False         # 1045 인증 제외
    assert db._is_connect_breaker_failure(db.DatasourceCircuitOpen("k", 1.0)) is False
    assert db._is_connect_breaker_failure(RuntimeError("connection refused")) is True
    assert db._is_connect_breaker_failure(RuntimeError("syntax error")) is False


# ── breaker 키 ───────────────────────────────────────────────────────────────
def test_breaker_key_uses_scope_key():
    k = db._breaker_key(_DS)
    assert k and k.startswith("mysql-")
    # 라벨이 달라도 같은 좌표면 같은 키(엔드포인트 격리, 라벨 rename 불변).
    assert db._breaker_key({**_DS, "key": "a"}) == db._breaker_key({**_DS, "key": "b"})


def test_breaker_key_none_for_control_plane():
    assert db._breaker_key(None) is None
    assert db._breaker_key({}) is None


# ── 3·4. connect_with_retry: 요청당 1회 카운트 → THRESHOLD 요청 후 open (M1) ──
def test_breaker_opens_after_threshold_requests_not_attempts(monkeypatch):
    connect_calls = {"n": 0}

    def _fake_connect(database=None, autocommit=True, datasource=None):
        connect_calls["n"] += 1
        raise _conn_exc()

    monkeypatch.setattr(db, "connect", _fake_connect)
    # 각 connect_with_retry 콜 = attempts(3)회 connect 시도, breaker 실패는 1회만 기록.
    for i in range(3):
        with pytest.raises(OperationalError):
            db.connect_with_retry(datasource=_DS, attempts=3)
    # 3요청 × 3시도 = 9회 connect, breaker fails=3 → open.
    assert connect_calls["n"] == 9
    st = db._BREAKER_STATE[_key()]
    assert st["fails"] == 3 and st["opened_at"] is not None

    # 4번째 요청 → admit 이 즉시 fast-fail(연결 시도 0).
    with pytest.raises(db.DatasourceCircuitOpen):
        db.connect_with_retry(datasource=_DS, attempts=3)
    assert connect_calls["n"] == 9  # connect 추가 호출 없음(블로킹 회피)


def test_single_request_does_not_open_breaker(monkeypatch):
    """M1 증폭 차단 — 1요청(내부 3 retry)이 breaker 를 즉시 open 시키지 않음."""
    monkeypatch.setattr(db, "connect", lambda **_k: (_ for _ in ()).throw(_conn_exc()))
    with pytest.raises(OperationalError):
        db.connect_with_retry(datasource=_DS, attempts=3)
    assert db._BREAKER_STATE[_key()]["fails"] == 1  # 3 아님


def test_deadlock_does_not_open_breaker(monkeypatch):
    """1205 deadlock 은 retry 되지만 breaker 미카운트(M4)."""
    monkeypatch.setattr(db, "connect", lambda **_k: (_ for _ in ()).throw(_deadlock_exc()))
    for _ in range(5):
        with pytest.raises(OperationalError):
            db.connect_with_retry(datasource=_DS, attempts=2)
    assert _key() not in db._BREAKER_STATE  # 열리지 않음


def test_auth_error_does_not_open_breaker(monkeypatch):
    """1045 인증 오류 — fast-fail(retry 안 함) + breaker 미카운트."""
    calls = {"n": 0}

    def _fake(database=None, autocommit=True, datasource=None):
        calls["n"] += 1
        raise _auth_exc()

    monkeypatch.setattr(db, "connect", _fake)
    for _ in range(5):
        with pytest.raises(OperationalError):
            db.connect_with_retry(datasource=_DS, attempts=3)
    assert calls["n"] == 5  # retry 0(요청당 1시도) — fast-fail
    assert _key() not in db._BREAKER_STATE


# ── 7. per-key 격리 ──────────────────────────────────────────────────────────
def test_breaker_isolation_per_scope_key(monkeypatch):
    ds_bad = {**_DS, "host": "10.0.0.1"}
    ds_good = {**_DS, "host": "10.0.0.2"}

    def _fake(database=None, autocommit=True, datasource=None):
        if datasource and datasource.get("host") == "10.0.0.1":
            raise _conn_exc()
        return mock.sentinel.good_conn

    monkeypatch.setattr(db, "connect", _fake)
    for _ in range(3):
        with pytest.raises(OperationalError):
            db.connect_with_retry(datasource=ds_bad, attempts=1)
    # bad open.
    with pytest.raises(db.DatasourceCircuitOpen):
        db.connect_with_retry(datasource=ds_bad, attempts=1)
    # good 무영향.
    assert db.connect_with_retry(datasource=ds_good, attempts=1) is mock.sentinel.good_conn


# ── 5. B1 — 단일 half-open trial (thundering herd 차단) ──────────────────────
def test_half_open_single_trial_under_concurrency(monkeypatch):
    key = _key()
    # 쿨다운 경과한 open 상태로 강제.
    db._BREAKER_STATE[key] = {
        "fails": 3, "opened_at": time.time() - (db.AGENT_DB_BREAKER_COOLDOWN_SEC + 1),
        "half_open_at": None,
    }
    connect_calls = {"n": 0}
    lock = threading.Lock()

    def _fake_connect(database=None, autocommit=True, datasource=None):
        with lock:
            connect_calls["n"] += 1
        time.sleep(0.05)  # race window 확대
        raise _conn_exc()

    # 주의: 위 fixture 가 time.sleep 을 noop 으로 패치 → 여기선 실제 sleep 복원.
    monkeypatch.setattr(db.time, "sleep", time.sleep)
    monkeypatch.setattr(db, "connect", _fake_connect)

    results: list[str] = []
    rlock = threading.Lock()

    def _worker():
        try:
            db.connect_with_retry(datasource=_DS, attempts=1)
            tag = "ok"
        except db.DatasourceCircuitOpen:
            tag = "fast_fail"
        except OperationalError:
            tag = "trial_fail"
        with rlock:
            results.append(tag)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 정확히 1개 스레드만 실제 connect 시도(단일 trial), 나머지 7개는 fast-fail.
    assert connect_calls["n"] == 1, results
    assert results.count("trial_fail") == 1
    assert results.count("fast_fail") == 7


def test_half_open_stale_token_reclaimed():
    """trial 보유 스레드 사망(토큰 잔존) → trial_timeout 경과 후 새 trial 허용(stuck-open 방지)."""
    key = _key()
    now = time.time()
    db._BREAKER_STATE[key] = {
        "fails": 3, "opened_at": now - (db.AGENT_DB_BREAKER_COOLDOWN_SEC + 1),
        "half_open_at": now - (db._breaker_trial_timeout() + 1),  # 오래된 토큰
    }
    # admit 이 stale 토큰을 회수하고 새 trial 승인(raise 없음).
    db._breaker_admit(key)
    assert db._BREAKER_STATE[key]["half_open_at"] is not None


def test_half_open_success_closes(monkeypatch):
    key = _key()
    db._BREAKER_STATE[key] = {
        "fails": 3, "opened_at": time.time() - (db.AGENT_DB_BREAKER_COOLDOWN_SEC + 1),
        "half_open_at": None,
    }
    monkeypatch.setattr(db, "connect", lambda **_k: mock.sentinel.recovered)
    assert db.connect_with_retry(datasource=_DS, attempts=1) is mock.sentinel.recovered
    assert key not in db._BREAKER_STATE  # close


def test_half_open_failure_reopens(monkeypatch):
    key = _key()
    db._BREAKER_STATE[key] = {
        "fails": 3, "opened_at": time.time() - (db.AGENT_DB_BREAKER_COOLDOWN_SEC + 1),
        "half_open_at": None,
    }
    monkeypatch.setattr(db, "connect", lambda **_k: (_ for _ in ()).throw(_conn_exc()))
    with pytest.raises(OperationalError):
        db.connect_with_retry(datasource=_DS, attempts=1)
    # 즉시 다시 fast-fail(re-open, 쿨다운 리셋).
    with pytest.raises(db.DatasourceCircuitOpen):
        db.connect_with_retry(datasource=_DS, attempts=1)


def test_half_open_noncounted_failure_releases_trial_token(monkeypatch):
    """REV 잔여 흡수 — half-open trial 이 비-연결 실패(인증 1045)로 끝나면 토큰을 풀어
    건강한 datasource 가 trial_timeout 동안 fast-fail 로 막히지 않게 한다(다음 요청=새 trial)."""
    key = _key()
    db._BREAKER_STATE[key] = {
        "fails": 3, "opened_at": time.time() - (db.AGENT_DB_BREAKER_COOLDOWN_SEC + 1),
        "half_open_at": None,
    }
    connect_calls = {"n": 0}

    def _auth_then_ok(database=None, autocommit=True, datasource=None):
        connect_calls["n"] += 1
        if connect_calls["n"] == 1:
            raise _auth_exc()        # 첫 trial: 비-연결 실패
        return mock.sentinel.ok      # 다음 trial: 성공

    monkeypatch.setattr(db, "connect", _auth_then_ok)
    # 첫 요청(trial) — 인증 실패로 raise. 토큰 해제됨(re-open 아님).
    with pytest.raises(OperationalError):
        db.connect_with_retry(datasource=_DS, attempts=1)
    assert db._BREAKER_STATE[key]["half_open_at"] is None
    # 다음 요청 — fast-fail 이 아니라 새 trial 승인 → 성공 → close.
    assert db.connect_with_retry(datasource=_DS, attempts=1) is mock.sentinel.ok
    assert key not in db._BREAKER_STATE
    assert connect_calls["n"] == 2  # 두 요청 모두 실제 trial(fast-fail 아님)


# ── 8. control-plane 미적용 ──────────────────────────────────────────────────
def test_control_plane_no_breaker(monkeypatch):
    calls = {"n": 0}

    def _fake(database=None, autocommit=True, datasource=None):
        calls["n"] += 1
        raise _conn_exc()

    monkeypatch.setattr(db, "connect", _fake)
    # datasource=None → key=None → breaker 미적용(매 요청 실제 시도).
    for _ in range(5):
        with pytest.raises(OperationalError):
            db.connect_with_retry(database="agent_memory", attempts=2)
    assert not db._BREAKER_STATE  # breaker 상태 흔적 없음


def test_breaker_disabled_never_opens(monkeypatch):
    monkeypatch.setattr(db, "AGENT_DB_BREAKER_ENABLED", False)
    monkeypatch.setattr(db, "connect", lambda **_k: (_ for _ in ()).throw(_conn_exc()))
    for _ in range(6):
        with pytest.raises(OperationalError):
            db.connect_with_retry(datasource=_DS, attempts=1)
    assert not db._BREAKER_STATE


# ── 9. m1 — 부기 예외가 connect 결과를 삼키지 않음 ──────────────────────────
def test_breaker_bookkeeping_exception_does_not_mask_conn(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda **_k: mock.sentinel.ok)

    def _boom(*_a, **_k):
        raise RuntimeError("breaker dict 손상")

    monkeypatch.setattr(db, "_breaker_record_success", _boom)
    # record_success 가 터져도 conn 은 정상 반환(_breaker_safe 격리).
    assert db.connect_with_retry(datasource=_DS, attempts=1) is mock.sentinel.ok


# ── 10. no-retry + bounded timeout 통합 ──────────────────────────────────────
def test_should_retry_false_for_circuit_open():
    assert db._should_retry_db_error(db.DatasourceCircuitOpen("k", 1.0)) is False
    assert db._should_retry_db_error(_conn_exc()) is True


def test_circuit_open_admit_raises_before_any_attempt(monkeypatch):
    key = _key()
    db._BREAKER_STATE[key] = {"fails": 3, "opened_at": time.time(), "half_open_at": None}
    m_connect = mock.Mock()
    monkeypatch.setattr(db, "connect", m_connect)
    with pytest.raises(db.DatasourceCircuitOpen):
        db.connect_with_retry(datasource=_DS, attempts=3)
    m_connect.assert_not_called()  # 시도 0


def test_connect_dataplane_passes_bounded_timeout(monkeypatch):
    monkeypatch.setattr(db, "AGENT_MULTI_DATASOURCE_ENABLED", True)
    monkeypatch.setattr(db, "AGENT_DB_POOL_ENABLED", False)
    monkeypatch.setattr(db, "AGENT_DB_CONNECT_TIMEOUT_SEC", 7)
    monkeypatch.setattr(db, "AGENT_TIMEOUT_SEC", 300)
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(db.mysql.connector, "connect", _capture)
    db.connect(datasource=_DS)
    assert captured["connection_timeout"] == 7  # 쿼리 예산 300 아닌 분리값


def test_circuit_open_message_hides_coordinates():
    exc = db.DatasourceCircuitOpen("mysql-deadbeef", 12.0)
    msg = str(exc)
    assert "차단" in msg
    assert "mysql-deadbeef" not in msg  # scope_key/좌표 비노출
    assert exc.scope_key == "mysql-deadbeef"
