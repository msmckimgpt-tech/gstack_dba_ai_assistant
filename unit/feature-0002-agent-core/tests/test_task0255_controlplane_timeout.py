"""TASK-0255 R3 — control-plane connect timeout bounded.

control-plane(datasource=None) MySQL 연결 + KB Postgres 연결의 connection_timeout 을 쿼리 예산
(AGENT_TIMEOUT_SEC=운영 300s)에서 분리해 bounded(_controlplane_connect_timeout, 기본 10s)로 묶었는지 검증.
data-plane(_dataplane_connect_timeout) 회귀 가드 포함. 실 DB 없이 connect monkeypatch.
"""
from __future__ import annotations

from shared import db


def test_controlplane_timeout_default(monkeypatch):
    monkeypatch.setattr(db, "AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC", 10, raising=False)
    assert db._controlplane_connect_timeout() == 10


def test_controlplane_timeout_override(monkeypatch):
    monkeypatch.setattr(db, "AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC", 5, raising=False)
    assert db._controlplane_connect_timeout() == 5


def test_controlplane_timeout_zero_falls_back_to_10_not_300(monkeypatch):
    # 0/미설정이면 10s 폴백 — data-plane 과 달리 AGENT_TIMEOUT_SEC(운영 300) 로 회귀하지 않는다(R3 핵심).
    monkeypatch.setattr(db, "AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC", 0, raising=False)
    monkeypatch.setattr(db, "AGENT_TIMEOUT_SEC", 300, raising=False)
    assert db._controlplane_connect_timeout() == 10


def test_controlplane_mysql_connect_uses_bounded_timeout(monkeypatch):
    captured: dict = {}

    def _fake_connect(**params):
        captured.update(params)
        return object()

    monkeypatch.setattr("mysql.connector.connect", _fake_connect)
    monkeypatch.setattr(db, "AGENT_DB_POOL_ENABLED", False, raising=False)
    monkeypatch.setattr(db, "AGENT_TIMEOUT_SEC", 300, raising=False)
    monkeypatch.setattr(db, "AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC", 10, raising=False)
    monkeypatch.setattr(db, "REPLICA_DB_ENABLED", False, raising=False)
    monkeypatch.setattr(db, "AGENT_DATA_DB_USER", "", raising=False)
    # control-plane: datasource=None, database=MEMORY_DB → else(root) 라우팅
    db.connect(database=db.MEMORY_DB, autocommit=True, datasource=None)
    assert captured.get("connection_timeout") == 10  # 300 아님(R3 bounded)


def test_dataplane_connect_timeout_unchanged(monkeypatch):
    # 회귀 가드: data-plane(datasource!=None, flag ON)은 여전히 _dataplane_connect_timeout() 적용.
    captured: dict = {}

    def _fake_connect(**params):
        captured.update(params)
        return object()

    monkeypatch.setattr("mysql.connector.connect", _fake_connect)
    monkeypatch.setattr(db, "AGENT_DB_POOL_ENABLED", False, raising=False)
    monkeypatch.setattr(db, "AGENT_MULTI_DATASOURCE_ENABLED", True, raising=False)
    monkeypatch.setattr(db, "AGENT_DB_CONNECT_TIMEOUT_SEC", 7, raising=False)
    ds = {"engine": "mysql", "host": "10.1.1.1", "port": 3306, "user": "ro", "password": "p", "key": "ds-x"}
    db.connect(database=None, autocommit=True, datasource=ds)
    assert captured.get("connection_timeout") == 7  # _dataplane_connect_timeout()


def test_pg_connect_uses_bounded_timeout(monkeypatch):
    captured: dict = {}

    class _FakePsy:
        @staticmethod
        def connect(conninfo):
            captured["conninfo"] = conninfo

            class _C:
                autocommit = False

            return _C()

    monkeypatch.setattr(db, "_psycopg", _FakePsy, raising=False)
    monkeypatch.setattr(db, "AGENT_KB_PG_ENABLED", True, raising=False)
    monkeypatch.setattr(db, "AGENT_KB_PG_HOST", "127.0.0.1", raising=False)
    monkeypatch.setattr(db, "AGENT_KB_PG_PORT", 5432, raising=False)
    monkeypatch.setattr(db, "AGENT_KB_PG_DB", "agent_kb", raising=False)
    monkeypatch.setattr(db, "AGENT_KB_PG_USER", "u", raising=False)
    monkeypatch.setattr(db, "AGENT_KB_PG_PASSWORD", "p", raising=False)
    monkeypatch.setattr(db, "AGENT_KB_PG_SSLMODE", "disable", raising=False)
    monkeypatch.setattr(db, "AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC", 10, raising=False)
    db._pg_connect()
    assert "connect_timeout=10" in captured["conninfo"]
