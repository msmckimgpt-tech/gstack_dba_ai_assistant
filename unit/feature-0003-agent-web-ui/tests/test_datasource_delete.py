"""TASK-0220 — 데이터소스 삭제 회귀 테스트.

근본 원인: _ds_write_common 이 DELETE 요청(바디 없음)에서도 request.json() 을 호출해
JSON 파싱 예외 → 400 "invalid json" 반환 → 삭제 불가.

수정: request.body() 로 먼저 바이트 확인 후 빈 바디면 {} 반환.

검증:
  S1  _ds_write_common — 빈 바디(DELETE 패턴) 시 error=None, data={} 반환.
  S2  admin_delete_datasource — 바인딩 없는 datasource 삭제 성공(200, deleted=True).
  S3  admin_delete_datasource — datasource 미존재 시 404.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json

import app
from routers import admin_datasources  # feature-0012 P5b


# ── Fakes ─────────────────────────────────────────────────────────────────────

class _FakeRequest:
    """DELETE 요청 시뮬레이션 — 빈 바디, query_params 지원."""

    def __init__(self, query_params=None):
        self.query_params = query_params or {}

    async def body(self):
        return b""

    async def json(self):
        raise ValueError("body() 가 비어 있으면 json() 은 호출되지 않아야 합니다")


class _TrackingCursor:
    """execute 호출을 기록하고 시나리오별 결과를 반환한다."""

    def __init__(self, scenario: str):
        self._scenario = scenario
        self.executed: list[str] = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        self._last = (sql, params)

    def fetchone(self):
        if "SELECT Id FROM WebDatasources" in (self._last[0] if hasattr(self, "_last") else ""):
            return (1,) if self._scenario == "found" else None
        return None

    def fetchall(self):
        return []  # 바인딩된 제품 없음

    def close(self):
        pass


class _TrackingConn:
    def __init__(self, scenario: str = "found"):
        self._scenario = scenario
        self.committed = False

    def cursor(self, *a, **k):
        return _TrackingCursor(self._scenario)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


def _build_actor():
    # TASK-0288: datasource CRUD 는 datasource.manage 전용 권한 필요(_ds_write_common).
    return {"id": 1, "permissions": {"console.access": True, "console.manage": True, "datasource.manage": True}}


def _patch_common(monkeypatch, conn):
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda req, c: (_build_actor(), None))
    monkeypatch.setattr(app, "record_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(app, "_build_actor_from_request", lambda *a, **kw: _build_actor())


# ── S1: 빈 바디 시 _ds_write_common 이 정상 반환 ─────────────────────────────

def test_ds_write_common_empty_body_no_error(monkeypatch):
    """DELETE 요청의 빈 바디 — _ds_write_common 이 error=None, data={} 반환."""
    conn = _TrackingConn()
    _patch_common(monkeypatch, conn)

    req = _FakeRequest()
    result_conn, actor, data, err = asyncio.run(app._ds_write_common(req))

    assert err is None, f"error 여야 하지 않음: {getattr(err, 'body', err)}"
    assert data == {}
    assert actor is not None


# ── S2: 삭제 성공 (datasource 존재, 바인딩 없음) ─────────────────────────────

def test_delete_datasource_success(monkeypatch):
    """datasource 존재 + 바인딩 없음 → deleted=True."""
    conn = _TrackingConn(scenario="found")
    _patch_common(monkeypatch, conn)

    req = _FakeRequest()

    class _RouteReq(_FakeRequest):
        path_params = {"key": "mysql-abcdef123456"}

    resp = asyncio.run(admin_datasources.admin_delete_datasource("mysql-abcdef123456", _RouteReq()))
    body = json.loads(resp.body)
    assert body.get("deleted") is True
    assert conn.committed


# ── S3: datasource 미존재 시 404 ─────────────────────────────────────────────

def test_delete_datasource_not_found(monkeypatch):
    """WebDatasources 에 해당 키 없음 → 404."""
    conn = _TrackingConn(scenario="not_found")
    _patch_common(monkeypatch, conn)

    req = _FakeRequest()
    resp = asyncio.run(admin_datasources.admin_delete_datasource("mysql-abcdef123456", req))
    assert resp.status_code == 404
