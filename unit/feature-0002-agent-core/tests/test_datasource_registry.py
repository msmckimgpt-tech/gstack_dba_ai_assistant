"""TASK-0205 — DB 기반 datasource 레지스트리 보안 합격선 회귀 테스트 (REV-0205).

cred_crypto envelope + AAD 바인딩, 레지스트리 DB우선·.env격리(M5), B1 effective default_db,
키부재 fail-closed. (CRUD API·SSRF·UI 는 라이브 검증.)
"""
from __future__ import annotations

import base64
import contextvars
import importlib
import os

import pytest


def _fresh_kek(monkeypatch):
    monkeypatch.setenv("AGENT_DATASOURCE_KEK_V1", base64.b64encode(os.urandom(32)).decode())


# ── cred_crypto: envelope + AAD ──────────────────────────────────────────────
def test_envelope_roundtrip_and_aad_bind(monkeypatch):
    _fresh_kek(monkeypatch)
    from modules import cred_crypto as cc
    assert cc.enc_available()
    dek = cc.generate_dek()
    assert cc.unwrap_dek(cc.wrap_dek(dek, 1), 1) == dek          # DEK envelope
    tok = cc.encrypt_password(dek, "p@ss:wd#1", "winsql")
    assert cc.decrypt_password(dek, tok, "winsql") == "p@ss:wd#1"  # password roundtrip
    with pytest.raises(cc.CredCryptoError):                        # AAD=다른 키 → 복호 차단
        cc.decrypt_password(dek, tok, "otherkey")


def test_enc_unavailable_without_kek(monkeypatch):
    for k in list(os.environ):
        if k.startswith("AGENT_DATASOURCE_KEK_V"):
            monkeypatch.delenv(k, raising=False)
    from modules import cred_crypto as cc
    assert cc.enc_available() is False
    assert cc.current_kek_version() is None


def test_wrong_kek_version_fails_closed(monkeypatch):
    _fresh_kek(monkeypatch)
    from modules import cred_crypto as cc
    dek = cc.generate_dek()
    wrapped = cc.wrap_dek(dek, 1)
    with pytest.raises(cc.CredCryptoError):
        cc.unwrap_dek(wrapped, 2)  # v2 KEK 부재 → fail-closed(로테이션 시 구키 보관 필요)


# ── 레지스트리: DB 우선 + .env 격리(M5) ──────────────────────────────────────
class _StubCursor:
    def __init__(self, rows_by_sql):
        self._rows = rows_by_sql
        self._last = None
    def execute(self, sql, params=None):
        self._last = sql
    def fetchone(self):
        # WebDatasources 조회면 stub 행, 아니면 None
        if self._last and "FROM WebDatasources" in self._last:
            return self._rows.get("ds_one")
        return None
    def fetchall(self):
        if self._last and "FROM WebDatasources" in self._last:
            return self._rows.get("ds_all", [])
        return []
    def close(self):
        pass


class _StubConn:
    def __init__(self, rows_by_sql=None):
        self._rows = rows_by_sql or {}
    def cursor(self):
        return _StubCursor(self._rows)


def test_resolve_env_fallback_when_no_db(monkeypatch):
    """DB 에 키 없음 → .env DATASOURCES 폴백(레거시 호환)."""
    from modules import datasources as dsr
    from modules import config as cfg
    monkeypatch.setattr(cfg, "DATASOURCES", {"winsql": {"key": "winsql", "engine": "mssql", "host": "h"}})
    out = dsr.resolve(_StubConn(), "winsql")
    assert out and out["key"] == "winsql" and out["engine"] == "mssql"


def test_resolve_db_isolation_when_kek_absent(monkeypatch):
    """M5: KEK 부재로 DB datasource 복호 불가해도 .env datasource(winsql)는 정상 resolve."""
    for k in list(os.environ):
        if k.startswith("AGENT_DATASOURCE_KEK_V"):
            monkeypatch.delenv(k, raising=False)
    from modules import datasources as dsr
    from modules import config as cfg
    monkeypatch.setattr(cfg, "DATASOURCES", {"winsql": {"key": "winsql", "engine": "mssql", "host": "h"}})
    # DB 에 다른 키(암호화됨)가 있어도 KEK 없어 skip — winsql(.env)는 영향 없음
    assert dsr.resolve(_StubConn(), "winsql")["key"] == "winsql"
    assert dsr.resolve(_StubConn(), "nonexist") is None


def test_resolve_none_conn_uses_env(monkeypatch):
    from modules import datasources as dsr
    from modules import config as cfg
    monkeypatch.setattr(cfg, "DATASOURCES", {"prod": {"key": "prod", "engine": "mysql"}})
    assert dsr.resolve(None, "prod")["engine"] == "mysql"
    assert dsr.resolve(None, "ghost") is None


# ── B1: effective default_db ContextVar ──────────────────────────────────────
def test_b1_effective_default_db_injected():
    from modules import config as cfg

    def check():
        cfg.set_active_datasource("winsql", engine="mssql", default_db="GameLog_151")
        assert cfg.get_active_default_db() == "gamelog_151"   # 소문자 정규화
        cfg.set_active_datasource(None)
        assert cfg.get_active_default_db() is None
    contextvars.copy_context().run(check)


def test_b1_guard_reads_effective_not_static(monkeypatch):
    """TASK-0206 DB-단위: cross-DB 가드는 **product allowlist(DB명)** 를 catalog 허용집합으로 읽는다 —
    정적 DATASOURCES 의 default_db 가 아니다. (B1 단일-DB pin 모드 폐기 — DB-allowlist 가 대체.)"""
    from modules import config as cfg
    from modules import tools

    def check():
        cfg.set_active_datasource("winsql", engine="mssql", default_db="gamelog_151")
        tools.set_active_schema_allowlist(["gamelog_151"])  # 제품 허용 DB(catalog)
        # 정적 DATASOURCES 의 default_db 는 dk_data_release(allowlist 와 무관) — 가드는 allowlist 를 본다.
        monkeypatch.setattr(cfg, "DATASOURCES", {"winsql": {"key": "winsql", "default_db": "dk_data_release"}})
        # 허용 DB(gamelog_151) 의 3-part 는 통과
        err = tools._freeform_sql_access_error("SELECT * FROM gamelog_151.dbo.tbl")
        assert err is None, err
        # 정적 default_db(dk_data_release)는 allowlist 밖 → 차단(가드가 정적값을 허용하지 않음을 증명)
        err2 = tools._freeform_sql_access_error("SELECT * FROM dk_data_release.dbo.tbl")
        assert err2 is not None and "dk_data_release" in err2
    contextvars.copy_context().run(check)


def test_scope_key_is_endpoint_hash_and_label_agnostic():
    """TASK-0219: scope_key(=fact/RAG 스코핑 식별자)는 엔드포인트(engine+host+port) 해시 —
    DatasourceKey 라벨과 독립(라벨 rename 에도 불변). web `_generate_datasource_key` 와 동일 공식."""
    import hashlib
    from modules import datasources as dsr

    # web app.py `_generate_datasource_key` 공식과 비트-동일해야 레지스트리 자동키와 정합.
    def web_formula(engine, host, port):
        raw = f"{engine.strip().lower()}:{host.strip().lower()}:{int(port)}"
        return f"{engine.strip().lower()[:10]}-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    assert dsr.compute_scope_key("mysql", "mysql", 3306) == web_formula("mysql", "mysql", 3306)
    assert dsr.compute_scope_key("mssql", "172.28.64.1", 14330) == web_formula("mssql", "172.28.64.1", 14330)

    # 라벨이 달라도(=mysql_local vs main_mysql) 같은 엔드포인트면 같은 scope_key.
    ds_a = {"key": "mysql_local", "engine": "mysql", "host": "mysql", "port": 3306}
    ds_b = {"key": "main_mysql", "engine": "mysql", "host": "mysql", "port": 3306}
    assert dsr.scope_key(ds_a) == dsr.scope_key(ds_b)
    assert dsr.scope_key(ds_a) == dsr.compute_scope_key("mysql", "mysql", 3306)

    # 미리 채운 scope_key 우선 + None(기본 단일 MySQL)
    assert dsr.scope_key({"scope_key": "mssql-abc123", "key": "x"}) == "mssql-abc123"
    assert dsr.scope_key(None) is None
    # host 부재(.env 레거시 dict) → 라벨 폴백
    assert dsr.scope_key({"key": "legacy"}) == "legacy"
