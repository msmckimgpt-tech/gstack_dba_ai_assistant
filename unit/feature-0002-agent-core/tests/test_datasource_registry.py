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
    """tools cross-DB 가드가 effective default_db(override 반영)를 읽는다 — 정적 dict 아님."""
    from modules import config as cfg
    from modules import tools

    def check():
        cfg.set_active_datasource("winsql", engine="mssql", default_db="gamelog_151")  # product override
        tools.set_active_schema_allowlist(["dbo"])
        # 정적 DATASOURCES 의 default_db 와 다른 override → 가드는 override(gamelog_151)를 허용 catalog 로
        monkeypatch.setattr(cfg, "DATASOURCES", {"winsql": {"key": "winsql", "default_db": "dk_data_release"}})
        # gamelog_151.dbo.t 는 effective(gamelog_151)와 일치 → cross 아님(통과 단계)
        err = tools._freeform_sql_access_error("SELECT * FROM gamelog_151.dbo.tbl")
        assert err is None or "교차" not in err
        # dk_data_release(정적값) 참조는 effective(gamelog_151)와 불일치 → cross-DB 차단
        err2 = tools._freeform_sql_access_error("SELECT * FROM dk_data_release.dbo.tbl")
        assert err2 is not None and "교차" in err2
    contextvars.copy_context().run(check)
