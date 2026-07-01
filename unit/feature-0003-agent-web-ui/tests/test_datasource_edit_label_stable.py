"""TASK-0234 — 데이터소스 수정 시 라벨 안정성 회귀 테스트.

근본 원인: `admin_update_datasource`(PATCH)가 키 미지정 편집 시 DatasourceKey 를 엔드포인트
해시로 재계산(`new_k = ... else hash_new_k`)해, 라벨을 바꾸지 않고 다른 필드(insight 토글·
host/port·password)만 수정해도 **친화 라벨이 매 편집마다 엔드포인트 해시로 되돌아갔다**
(admin.js 는 라벨 변경 시에만 key 전송 → 일반 편집은 data.key 부재 → 해시 default 적용).

수정: 라벨은 explicit rename(body.key) 시에만 변경, 그 외엔 현재 라벨 유지(엔드포인트 신원은
라벨이 아닌 compute_scope_key 로 추적, TASK-0219).

검증:
  S1  키 미지정 편집(insight 토글) → 라벨 유지(key_changed=False, UPDATE 에 DatasourceKey 없음).
  S2  explicit key 제공 → rename(key_changed=True, DatasourceKey 갱신).
  S3  host 변경 + 키 미지정 → 라벨 유지(해시 리버트 안 됨) ← 회귀의 핵심.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json

import app
from routers import admin_datasources  # feature-0012 P5b


class _FakeReq:
    def __init__(self, body):
        self._raw = json.dumps(body).encode()

    async def body(self):
        return self._raw

    async def json(self):
        return json.loads(self._raw)


class _EditCursor:
    def __init__(self, existing):
        self._existing = existing  # (Engine, Host, Port, PasswordEnc, EncryptionVersion)
        self.executed = []
        self._last = ("", ())

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        self._last = (sql, params or ())

    def fetchone(self):
        sql, _ = self._last
        if "SELECT Engine, Host, Port, PasswordEnc, EncryptionVersion" in sql:
            return self._existing
        if sql.startswith("SELECT 1 FROM WebDatasources WHERE DatasourceKey="):
            return None  # rename 대상 키 미존재(중복 아님)
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _EditConn:
    def __init__(self, cur):
        self._cur = cur
        self.committed = False

    def cursor(self, *a, **k):
        return self._cur

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


def _patch(monkeypatch, conn):
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda req, c: ({"id": 10}, None))
    monkeypatch.setattr(app, "_account_has_permission", lambda a, p: True)
    monkeypatch.setattr(app, "record_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(app, "_build_actor_from_request", lambda *a, **kw: {"id": 10})


def _update_sql(cur):
    return [s for (s, p) in cur.executed if s.startswith("UPDATE WebDatasources SET")]


def _set_clause(update_sql):
    """UPDATE 의 SET 절만(WHERE 이전) — WHERE DatasourceKey=%s 의 오탐 방지."""
    return update_sql.split("WHERE")[0]


def test_s1_edit_without_key_keeps_label(monkeypatch):
    """S1: 키 미지정 편집(insight 토글) → 라벨 유지, 해시 리버트 없음."""
    cur = _EditCursor(("mssql", "172.28.64.1", 14330, None, 1))
    conn = _EditConn(cur)
    _patch(monkeypatch, conn)
    resp = asyncio.run(admin_datasources.admin_update_datasource("mssql_local", _FakeReq({"insight_enabled": True})))
    body = json.loads(resp.body)
    assert body.get("key_changed") is False, f"라벨이 바뀜(해시 리버트 회귀): {body}"
    assert body.get("key") == "mssql_local", f"라벨 미유지: {body}"
    upd = _update_sql(cur)
    assert upd and "DatasourceKey=" not in _set_clause(upd[0]), f"UPDATE SET 이 DatasourceKey 변경(해시 리버트): {upd}"


def test_s2_edit_explicit_key_renames(monkeypatch):
    """S2: explicit key 제공 → rename."""
    cur = _EditCursor(("mssql", "172.28.64.1", 14330, None, 1))
    conn = _EditConn(cur)
    _patch(monkeypatch, conn)
    resp = asyncio.run(admin_datasources.admin_update_datasource("mssql_local", _FakeReq({"key": "mssql_renamed"})))
    body = json.loads(resp.body)
    assert body.get("key_changed") is True, f"explicit rename 미반영: {body}"
    assert body.get("key") == "mssql_renamed", f"rename 결과 키 오류: {body}"
    upd = _update_sql(cur)
    assert upd and "DatasourceKey=" in _set_clause(upd[0]), f"rename UPDATE 누락: {upd}"


def test_s3_edit_host_change_keeps_label(monkeypatch):
    """S3(핵심): host 변경 + 키 미지정 → 라벨 유지(엔드포인트 바뀌어도 해시 리버트 안 됨)."""
    cur = _EditCursor(("mssql", "172.28.64.1", 14330, None, 1))
    conn = _EditConn(cur)
    _patch(monkeypatch, conn)
    monkeypatch.setattr(app, "_ssrf_check_host", lambda h: (True, "", None))
    resp = asyncio.run(admin_datasources.admin_update_datasource("mssql_local", _FakeReq({"host": "10.0.0.5"})))
    body = json.loads(resp.body)
    assert body.get("key_changed") is False, f"host 변경 시 라벨이 해시로 리버트됨(회귀): {body}"
    assert body.get("key") == "mssql_local", f"라벨 미유지: {body}"
    upd = _update_sql(cur)
    assert upd and "DatasourceKey=" not in _set_clause(upd[0]) and "Host=" in _set_clause(upd[0]), f"host 변경 UPDATE 이상: {upd}"
