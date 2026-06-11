"""TASK-0222 — 데이터소스 시드 엔드포인트-멱등 회귀 테스트.

근본 원인: DatasourceKey 가 admin rename 가능한 단순 라벨이 되면서(TASK-0216/0219),
`_seed_main_mysql_datasource` 가 해시 라벨 부재 = "미시드"로 오판해, 운영자가 데이터 MySQL
datasource 를 다른 라벨(예: mysql_local)로 rename 하면 매 web 부팅마다 해시 라벨의 고아 중복
datasource 를 재INSERT 했다(운영자 rename 무력화).

수정: 해시 라벨 부재 시 같은 엔드포인트(engine=mysql, host=DB_HOST, port=DB_PORT)의 활성
datasource 를 canonical 로 채택 → 중복 INSERT skip(멱등성=엔드포인트 기준).

검증:
  S1  같은 엔드포인트 라벨(mysql_local) 존재 + 해시 라벨 부재 → INSERT 안 함, 기존 라벨 채택.
  S2  엔드포인트에 아무 datasource 없음(콜드) → 해시 라벨로 정상 INSERT(기존 동작 보존).

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import app


class _SeedCursor:
    """시드 SQL 흐름을 시나리오별로 시뮬레이션. execute 기록 → INSERT 발생 여부 검증."""

    def __init__(self, endpoint_label):
        # endpoint_label: 같은 엔드포인트에 이미 있는 datasource 라벨(None = 콜드, 아무것도 없음).
        self._endpoint_label = endpoint_label
        self.executed: list = []
        self._last = ("", None)

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        self._last = (sql, params)

    def fetchone(self):
        sql, params = self._last
        # 레거시 main_mysql 조회 → 없음
        if "SELECT PasswordEnc, EncryptionVersion" in sql:
            return None
        # 해시 라벨 존재 검사(SELECT 1 ... AND IsActive=1) → 항상 부재(rename 시나리오)
        if sql.startswith("SELECT 1 FROM WebDatasources WHERE DatasourceKey="):
            return None
        # 엔드포인트 조회(TASK-0222) → 시나리오의 기존 라벨(또는 None)
        if "WHERE Engine='mysql' AND LOWER(Host)=LOWER(" in sql:
            return (self._endpoint_label,) if self._endpoint_label else None
        # canonical 라벨의 행 조회(Host,DbUser,IsActive,Engine,Port)
        if "SELECT Host, DbUser, IsActive, Engine, Port" in sql:
            if self._endpoint_label:
                return (app.DB_HOST, "agent_ro", 1, "mysql", int(app.DB_PORT))
            return None  # 콜드 → 미존재 → INSERT 경로
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _SeedConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass


def _patch_seed_env(monkeypatch):
    monkeypatch.setenv("AGENT_DATA_DB_USER", "agent_ro")
    monkeypatch.setenv("AGENT_DATA_DB_PASSWORD", "pw")
    # 암호화 가용 + DEK 확보(INSERT 경로에서만 사용).
    import modules.cred_crypto as cc
    import modules.datasources as dsr
    monkeypatch.setattr(cc, "enc_available", lambda: True, raising=True)
    monkeypatch.setattr(cc, "encrypt_password", lambda dek, pw, key: b"enc", raising=True)
    monkeypatch.setattr(dsr, "ensure_dek", lambda conn: (1, b"0" * 32), raising=True)


def test_seed_skips_insert_when_same_endpoint_label_exists(monkeypatch):
    """S1: 운영자가 rename 한 mysql_local 이 같은 엔드포인트에 존재 → 해시 라벨 중복 INSERT 안 함."""
    _patch_seed_env(monkeypatch)
    cur = _SeedCursor(endpoint_label="mysql_local")
    app._seed_main_mysql_datasource(_SeedConn(cur))
    inserts = [s for (s, _p) in cur.executed if "INSERT INTO WebDatasources" in s]
    assert not inserts, f"같은 엔드포인트 라벨 존재 시 INSERT 발생(중복 재생성 회귀): {inserts}"
    # 채택된 기존 라벨로 NULL 제품 바인딩(엔드포인트 일치 → migrate_ok).
    migrates = [p for (s, p) in cur.executed if "UPDATE WebProducts SET DatasourceKey=" in s and "IS NULL" in s]
    assert migrates and migrates[0][0] == "mysql_local", f"채택 라벨로 마이그 안 됨: {migrates}"


def test_seed_inserts_when_endpoint_cold(monkeypatch):
    """S2: 엔드포인트에 아무 datasource 없음(콜드) → 해시 라벨로 정상 INSERT(기존 동작 보존)."""
    _patch_seed_env(monkeypatch)
    cur = _SeedCursor(endpoint_label=None)
    app._seed_main_mysql_datasource(_SeedConn(cur))
    inserts = [s for (s, _p) in cur.executed if "INSERT INTO WebDatasources" in s]
    assert inserts, "콜드 엔드포인트에서 시드 INSERT 가 누락됨(기존 동작 회귀)"
