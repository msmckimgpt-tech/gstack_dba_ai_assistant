"""TASK-0222/0224 — 데이터소스 시드 엔드포인트-멱등 + 고아 self-heal 회귀 테스트.

근본 원인: DatasourceKey 가 admin rename 가능한 단순 라벨이 되면서(TASK-0216/0219),
`_seed_main_mysql_datasource` 가 해시 라벨 부재 = "미시드"로 오판해, 운영자가 데이터 MySQL
datasource 를 다른 라벨(mysql_local)로 rename 하면 매 web 부팅마다 해시 라벨의 고아 중복
datasource 를 재INSERT 했다(운영자 rename 무력화).

수정:
  - TASK-0222: 같은 엔드포인트(engine=mysql, host=DB_HOST, port=DB_PORT)의 다른 라벨이 있으면
    그것을 canonical 채택 → 중복 INSERT skip(멱등성=엔드포인트).
  - TASK-0224: 해시 라벨이 **시드 자동생성 고아**(UpdatedByAccountId IS NULL + 제품 0)로 존재하면
    능동 정리(self-heal). **운영자가 콘솔로 미리 세팅한 datasource(UpdatedByAccountId 有)는
    제품 미연결이어도 절대 삭제하지 않는다** — 시드 INSERT=NULL, admin_create=actor.id 로 구분.

검증:
  S1  라벨 존재 + 해시 부재 → INSERT 안 함, 라벨 채택.
  S2  콜드(아무 것도 없음) → 해시 라벨로 정상 INSERT.
  S3  라벨 + 해시 시드-고아(NULL·제품0) → 해시 DELETE(self-heal) + 라벨 채택, INSERT 안 함.
  S4  라벨 + 해시에 제품 바인딩(>0) → 해시 보존(DELETE·채택 안 함).
  S5  라벨 + 해시가 **운영자 생성**(UpdatedByAccountId 有·제품0) → **해시 보존**(self-heal 미적용,
      운영자 미리세팅 datasource 누락 방지) + INSERT 안 함.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import app


class _SeedCursor:
    """시드 SQL 흐름 시뮬레이션. 시나리오 상태(label/hash/account/bound)로 fetchone 응답."""

    def __init__(self, *, label_exists, hash_exists, hash_account=None, hash_bound=0):
        self._label_exists = label_exists      # 같은 엔드포인트의 다른 라벨(mysql_local) 존재?
        self._hash_exists = hash_exists        # 해시 라벨 존재?
        self._hash_account = hash_account      # 해시 라벨 UpdatedByAccountId (None=시드생성, int=운영자생성)
        self._hash_bound = hash_bound          # 해시 라벨에 바인딩된 제품 수
        self._hash = app._generate_datasource_key("mysql", app.DB_HOST, int(app.DB_PORT))
        self.executed: list = []
        self._last = ("", None)

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        self._last = (sql, params or ())

    def fetchone(self):
        sql, params = self._last
        p0 = params[0] if params else None
        if "SELECT PasswordEnc, EncryptionVersion" in sql:
            return (b"enc", 1) if (p0 == self._hash and self._hash_exists) else None
        if "WHERE Engine='mysql' AND LOWER(Host)=LOWER(" in sql:
            return ("mysql_local",) if self._label_exists else None
        if sql.startswith("SELECT UpdatedByAccountId FROM WebDatasources WHERE DatasourceKey="):
            return (self._hash_account,) if (p0 == self._hash and self._hash_exists) else None
        if "SELECT COUNT(*) FROM WebProducts" in sql:
            return (self._hash_bound,)
        if "SELECT Host, DbUser, IsActive, Engine, Port" in sql:
            if p0 == "mysql_local" and self._label_exists:
                return (app.DB_HOST, "agent_ro", 1, "mysql", int(app.DB_PORT))
            if p0 == self._hash and self._hash_exists:
                return (app.DB_HOST, "agent_ro", 1, "mysql", int(app.DB_PORT))
            return None
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
    import modules.cred_crypto as cc
    import shared.datasources as dsr
    monkeypatch.setattr(cc, "enc_available", lambda: True, raising=True)
    monkeypatch.setattr(cc, "encrypt_password", lambda dek, pw, key: b"enc", raising=True)
    monkeypatch.setattr(cc, "decrypt_password", lambda dek, enc, key: "pw", raising=True)
    monkeypatch.setattr(dsr, "ensure_dek", lambda conn: (1, b"0" * 32), raising=True)


def _run(monkeypatch, **kw):
    _patch_seed_env(monkeypatch)
    cur = _SeedCursor(**kw)
    app._seed_main_mysql_datasource(_SeedConn(cur))
    inserts = [(s, p) for (s, p) in cur.executed if "INSERT INTO WebDatasources" in s]
    deletes = [(s, p) for (s, p) in cur.executed if "DELETE FROM WebDatasources" in s]
    migrates = [p for (s, p) in cur.executed if "UPDATE WebProducts SET DatasourceKey=" in s and "IS NULL" in s]
    return cur, inserts, deletes, migrates


def test_s1_label_exists_no_hash_skips_insert(monkeypatch):
    """S1: 라벨 존재 + 해시 부재 → INSERT 안 함, 라벨 채택."""
    cur, inserts, deletes, migrates = _run(monkeypatch, label_exists=True, hash_exists=False)
    assert not inserts, f"라벨 존재 시 INSERT 발생(중복 재생성 회귀): {inserts}"
    assert migrates and migrates[0][0] == "mysql_local", f"채택 라벨로 마이그 안 됨: {migrates}"


def test_s2_endpoint_cold_inserts(monkeypatch):
    """S2: 콜드 → 해시 라벨로 정상 INSERT(기존 동작 보존)."""
    cur, inserts, deletes, migrates = _run(monkeypatch, label_exists=False, hash_exists=False)
    assert inserts, "콜드 엔드포인트에서 시드 INSERT 누락(기존 동작 회귀)"


def test_s3_seed_orphan_hash_self_healed(monkeypatch):
    """S3: 라벨 + 시드-고아 해시(NULL account·제품0) → 해시 DELETE(self-heal) + 라벨 채택."""
    cur, inserts, deletes, migrates = _run(
        monkeypatch, label_exists=True, hash_exists=True, hash_account=None, hash_bound=0
    )
    _hash = app._generate_datasource_key("mysql", app.DB_HOST, int(app.DB_PORT))
    assert deletes and deletes[0][1] and deletes[0][1][0] == _hash, f"시드-고아 self-heal DELETE 누락: {deletes}"
    assert not inserts, f"self-heal 후 INSERT 발생: {inserts}"
    assert migrates and migrates[0][0] == "mysql_local"


def test_s4_bound_hash_preserved(monkeypatch):
    """S4: 라벨 + 해시에 제품 바인딩(>0) → 해시 보존(DELETE·채택 안 함)."""
    cur, inserts, deletes, migrates = _run(
        monkeypatch, label_exists=True, hash_exists=True, hash_account=None, hash_bound=3
    )
    assert not deletes, f"제품 바인딩된 해시키 삭제(운영 연속성 위반): {deletes}"
    assert not inserts, f"해시 존재 시 INSERT 발생: {inserts}"


def test_s5_operator_preset_hash_preserved(monkeypatch):
    """S5(사용자 제기 엣지): 라벨 + 해시가 **운영자 생성**(UpdatedByAccountId 有·제품 0) →
    self-heal 미적용, 운영자가 미리 세팅한 datasource 절대 삭제 안 함."""
    cur, inserts, deletes, migrates = _run(
        monkeypatch, label_exists=True, hash_exists=True, hash_account=42, hash_bound=0
    )
    assert not deletes, f"운영자 미리세팅 datasource 가 self-heal 로 삭제됨(누락 위반): {deletes}"
    assert not inserts, f"해시 존재 시 INSERT 발생: {inserts}"
