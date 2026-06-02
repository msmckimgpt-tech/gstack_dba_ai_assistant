"""db.py opt-in MySQL 커넥션 풀 단위 검증 — TASK-0144.

실 MySQL 연결 없이 monkeypatch 로 동작. 검증 항목:
1. 풀 키 설계: (host,port,user,database) 시그니처별 분리, password 제외.
2. AGENT_DB_POOL_ENABLED False(기본) → 풀 미사용, direct mysql.connector.connect 호출.
3. AGENT_DB_POOL_ENABLED True → 풀에서 get_connection() 대여.
4. 폴백: 풀 소진(PoolError) → direct connect 로 폴백 (raise 안 함).
5. 폴백: 풀 생성 실패 → direct connect 로 폴백.
6. user 라우팅(root vs agent_ro) 이 별도 풀 키가 됨.
"""

from __future__ import annotations

from unittest import mock

import pytest
from mysql.connector.errors import PoolError

from modules import db


@pytest.fixture(autouse=True)
def _clear_pool_registry():
    db._POOL_REGISTRY.clear()
    yield
    db._POOL_REGISTRY.clear()


def test_pool_key_signature():
    """풀 키 = (host,port,user,database) — password 제외, database 분리."""
    base = {"host": "mysql", "port": 3306, "user": "root", "password": "secret", "database": "agent_memory"}
    k1 = db._pool_key(base)
    # password 가 달라도 같은 키 (password 는 (host,user) 종속).
    k2 = db._pool_key({**base, "password": "other"})
    assert k1 == k2
    # database 가 다르면 다른 키.
    k3 = db._pool_key({**base, "database": "customer_db"})
    assert k1 != k3
    # user 가 다르면(root vs agent_ro) 다른 키.
    k4 = db._pool_key({**base, "user": "agent_ro"})
    assert k1 != k4
    # host(replica) 가 다르면 다른 키.
    k5 = db._pool_key({**base, "host": "mysql-replica"})
    assert k1 != k5
    # database=None 은 빈 문자열로 구분.
    k6 = db._pool_key({"host": "mysql", "port": 3306, "user": "root"})
    assert k6.endswith("|")


def test_pool_disabled_uses_direct_connect():
    """기본 OFF — 풀 경로 안 타고 mysql.connector.connect 직접 호출 (동작 무변경)."""
    sentinel = object()
    with mock.patch.object(db, "AGENT_DB_POOL_ENABLED", False), \
         mock.patch.object(db.mysql.connector, "connect", return_value=sentinel) as m_connect, \
         mock.patch.object(db, "_get_or_create_pool") as m_pool:
        conn = db.connect(database="agent_memory")
    assert conn is sentinel
    m_connect.assert_called_once()
    m_pool.assert_not_called()


def test_pool_enabled_borrows_from_pool():
    """opt-in True — 풀에서 get_connection() 으로 대여."""
    pooled = object()
    fake_pool = mock.Mock()
    fake_pool.get_connection.return_value = pooled
    with mock.patch.object(db, "AGENT_DB_POOL_ENABLED", True), \
         mock.patch.object(db, "_get_or_create_pool", return_value=fake_pool), \
         mock.patch.object(db.mysql.connector, "connect") as m_connect:
        conn = db.connect(database="agent_memory")
    assert conn is pooled
    fake_pool.get_connection.assert_called_once()
    m_connect.assert_not_called()


def test_pool_exhausted_falls_back_to_direct():
    """풀 소진(PoolError) → direct connect 폴백, raise 안 함."""
    direct = object()
    fake_pool = mock.Mock()
    fake_pool.get_connection.side_effect = PoolError("pool exhausted")
    with mock.patch.object(db, "AGENT_DB_POOL_ENABLED", True), \
         mock.patch.object(db, "_get_or_create_pool", return_value=fake_pool), \
         mock.patch.object(db.mysql.connector, "connect", return_value=direct) as m_connect:
        conn = db.connect(database="agent_memory")
    assert conn is direct
    m_connect.assert_called_once()


def test_pool_create_failure_falls_back_to_direct():
    """풀 생성 실패(_get_or_create_pool None) → direct connect 폴백."""
    direct = object()
    with mock.patch.object(db, "AGENT_DB_POOL_ENABLED", True), \
         mock.patch.object(db, "_get_or_create_pool", return_value=None), \
         mock.patch.object(db.mysql.connector, "connect", return_value=direct) as m_connect:
        conn = db.connect(database="agent_memory")
    assert conn is direct
    m_connect.assert_called_once()


def test_get_or_create_pool_caches_and_falls_back_on_construct_error():
    """풀 생성 실패 시 None 반환(폴백 신호), 성공 시 레지스트리 캐시."""
    params = {"host": "mysql", "port": 3306, "user": "root", "password": "x", "database": "agent_memory"}
    # 생성 실패 → None.
    with mock.patch.object(db.mysql.connector.pooling, "MySQLConnectionPool", side_effect=RuntimeError("no db")):
        assert db._get_or_create_pool(params) is None
    assert db._pool_key(params) not in db._POOL_REGISTRY
    # 생성 성공 → 캐시되고 재호출 시 동일 객체 (lazy single-create).
    fake_pool = object()
    with mock.patch.object(db.mysql.connector.pooling, "MySQLConnectionPool", return_value=fake_pool) as m_ctor:
        first = db._get_or_create_pool(params)
        second = db._get_or_create_pool(params)
    assert first is fake_pool and second is fake_pool
    m_ctor.assert_called_once()
