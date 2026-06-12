"""TASK-0253 — datasource 연결 테스트(/test) 엔드포인트의 이벤트 루프 비블로킹 회귀 테스트.

배경(라이브 UX 버그): 관리 콘솔 ↻ 새로고침이 N개 datasource 의 /test 를 동시 호출하면 배지가
수 초간 "확인 중…"에 묶였다. 원인은 `admin_test_datasource` 가 `async def` 인데 내부에서 동기
블로킹 `_db.probe_datasource()`(도달 불가 시 connection_timeout 까지 점유)를 직접 호출 → 그동안
**이벤트 루프 전체가 멈춰** 동시 요청이 직렬화된 것. TASK-0253 은 probe 를 `asyncio.to_thread`
로 스레드풀에 넘겨 루프를 비운다(프로젝트 기존 /api/ask 패턴과 동일).

검증 대상:
  T1  정상 — to_thread 경유라도 probe 결과(ok/elapsed_ms/error)가 그대로 응답에 실린다.
  T2  실패 — probe 실패 시 ok=False + errno 전달(자격증명 비유출 계약 유지).
  T3  비블로킹 핵심 — 느린(블로킹) probe 를 N개 **동시** 호출해도 이벤트 루프가 막히지 않아
       전체 소요가 직렬 합산이 아닌 ~1건 수준(가장 느린 1개)이다.

`make test`(agent 이미지, --no-deps)에서 DB/네트워크 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json
import time

import app


class _FakeRequest:
    def __init__(self):
        self.query_params = {}
        self.headers = {}
        self.client = None

    async def body(self):
        return b""

    async def json(self):
        return {}


class _BenignCursor:
    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        return None


class _BenignConn:
    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        return None

    def close(self):
        return None


def _body(resp):
    return json.loads(resp.body)


def _install(monkeypatch, *, probe):
    """엔드포인트 의존성 monkeypatch. probe: probe_datasource 대체(동기 함수)."""
    acct = {"id": 1, "permissions": {"console.access": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    monkeypatch.setattr(app, "_account_has_permission", lambda account, perm: True)
    # resolve 는 좌표 dict 반환(host 포함). SSRF 는 통과 + pin=host.
    monkeypatch.setattr("modules.datasources.resolve",
                        lambda conn, key: {"engine": "mysql", "host": "h", "port": 3306,
                                           "user": "u", "password": "p"})
    monkeypatch.setattr(app, "_ssrf_check_host", lambda host: (True, "", host))
    monkeypatch.setattr("modules.db.probe_datasource", probe)


# ── T1: 정상 결과 전달 ──────────────────────────────────────────────────────────
def test_probe_ok_passthrough(monkeypatch):
    _install(monkeypatch, probe=lambda ds, *, timeout=None: (True, 12.3, ""))
    resp = asyncio.run(app.admin_test_datasource("mysql-abc", _FakeRequest()))
    assert resp.status_code == 200
    b = _body(resp)
    assert b["ok"] is True
    assert b["elapsed_ms"] == 12.3
    assert b["error"] == ""


# ── T2: 실패 결과 + errno 전달(자격증명 비유출) ─────────────────────────────────
def test_probe_failure_errno(monkeypatch):
    _install(monkeypatch, probe=lambda ds, *, timeout=None: (False, 8000.0, "errno=2003"))
    resp = asyncio.run(app.admin_test_datasource("mysql-abc", _FakeRequest()))
    b = _body(resp)
    assert b["ok"] is False
    assert b["error"] == "errno=2003"
    # 응답 본문에 자격증명/좌표 키가 새지 않는다(errno 만 노출 계약).
    assert "password" not in b and "host" not in b and "user" not in b


# ── T3: 비블로킹 — 느린 probe N개 동시 호출이 직렬화되지 않는다 ────────────────────
def test_concurrent_probes_do_not_block_event_loop(monkeypatch):
    """블로킹 probe(0.3s sleep)를 5개 동시 호출. to_thread 라면 ~0.3s, 루프 블로킹이면 ~1.5s."""
    SLEEP = 0.3
    N = 5

    def _slow_probe(ds, *, timeout=None):
        time.sleep(SLEEP)  # 동기 블로킹(실 probe 의 connection_timeout 점유 모사)
        return (True, SLEEP * 1000.0, "")

    _install(monkeypatch, probe=_slow_probe)

    async def _run_all():
        start = time.monotonic()
        results = await asyncio.gather(*[
            app.admin_test_datasource(f"mysql-{i}", _FakeRequest()) for i in range(N)
        ])
        return results, time.monotonic() - start

    results, elapsed = asyncio.run(_run_all())
    assert all(r.status_code == 200 for r in results)
    assert all(_body(r)["ok"] for r in results)
    # 직렬이면 N*SLEEP=1.5s. to_thread 병렬이면 ~SLEEP. 넉넉히 절반(0.75s) 미만이면 비블로킹 입증.
    assert elapsed < (SLEEP * N) * 0.5, f"동시 probe 가 직렬화됨(elapsed={elapsed:.2f}s) — 이벤트 루프 블로킹 의심"
