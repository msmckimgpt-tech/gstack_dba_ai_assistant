"""FR-schema-name-case-drift (B, ingestion 정규화) — 제품 접근DB 저장 시 서버 실제 case 로 정규화.

admin.js 가 MySQL 스키마명을 `.toLowerCase()` 로 보내도(또는 수기 소문자 입력), write path
(`admin_update_product_databases`)가 datasource 서버의 실제 case(`list_server_databases`)로 정규화해
저장한다 → case-sensitive MySQL 에서 assistant 조회 0행 되는 drift 를 write 시점에 봉인. degrade-safe.
"""
from __future__ import annotations

import app as appmod
from shared import datasources as _dsr
from shared import db as _db

_URL = "/api/admin/products/3/databases"


class _Cur:
    def __init__(self, store):
        self._store = store
        self._last = ""

    def execute(self, sql, params=None):
        self._last = sql

    def fetchone(self):
        s = self._last
        if "FROM WebProducts" in s:
            return (3, "mysql-x")           # product row (Id, DatasourceKey)
        if "FROM WebDatasources" in s:
            return ("mysql", 22)            # engine, id
        if "FROM WebProductDatasources" in s:
            return (1,)                     # binding ok
        if "information_schema.COLUMNS" in s or "information_schema.columns" in s.lower():
            return (1,)                     # DatasourceId / Source 컬럼 존재
        return (0,)

    def fetchall(self):
        return []                           # before-state schemas 없음

    def close(self):
        pass


class _Conn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True

    def cursor(self, *a, **k):
        return _Cur(self._store)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _override_conn():
    store: dict = {}
    def _gen():
        conn = _Conn(store)
        try:
            yield conn
        finally:
            conn.close()
    appmod.app.dependency_overrides[appmod.get_conn] = _gen


def test_write_path_normalizes_to_server_case(client, as_account, monkeypatch):
    _override_conn()
    as_account(perms={"product.update": True})
    # datasource 해소 → mysql, 서버 실제 case DB 목록.
    monkeypatch.setattr(_dsr, "resolve", lambda conn, key: {"engine": "mysql", "host": "10.0.0.9", "port": 3306})
    monkeypatch.setattr(appmod, "_ssrf_check_host", lambda host: (True, "", host))
    monkeypatch.setattr(_db, "list_server_databases", lambda ds: ["DEV_1_1_1_20", "account_db"])
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)

    r = client.put(_URL, json={"datasource_key": "mysql-x",
                               "databases": [{"schema_name": "dev_1_1_1_20", "sort_order": 10},
                                             {"schema_name": "account_db", "sort_order": 20}]})
    assert r.status_code == 200, r.text
    stored = {d["schema_name"] for d in r.json()["databases"]}
    assert "DEV_1_1_1_20" in stored          # 소문자 입력 → 서버 실제 case 로 정규화 저장
    assert "dev_1_1_1_20" not in stored
    assert "account_db" in stored            # 이미 실제 case


def test_write_path_degrade_safe_on_ds_failure(client, as_account, monkeypatch):
    _override_conn()
    as_account(perms={"product.update": True})
    monkeypatch.setattr(_dsr, "resolve", lambda conn, key: {"engine": "mysql", "host": "10.0.0.9", "port": 3306})
    monkeypatch.setattr(appmod, "_ssrf_check_host", lambda host: (True, "", host))
    # 서버 목록 조회 실패 → 입력 case 유지(저장 차단 안 함).
    def _boom(ds): raise RuntimeError("datasource down")
    monkeypatch.setattr(_db, "list_server_databases", _boom)
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)

    r = client.put(_URL, json={"datasource_key": "mysql-x",
                               "databases": [{"schema_name": "dev_1_1_1_20", "sort_order": 10}]})
    assert r.status_code == 200, r.text
    stored = {d["schema_name"] for d in r.json()["databases"]}
    assert "dev_1_1_1_20" in stored          # degrade-safe: 입력 case 유지
