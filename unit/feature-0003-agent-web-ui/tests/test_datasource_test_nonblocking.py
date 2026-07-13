"""TASK-0253 — datasource 연결 테스트(/test) 엔드포인트의 이벤트 루프 비블로킹 회귀 테스트.

배경(라이브 UX 버그): 관리 콘솔 ↻ 새로고침이 N개 datasource 의 /test 를 동시 호출하면 배지가
수 초간 "확인 중…"에 묶였다. 원인은 `admin_test_datasource` 가 `async def` 인데 내부에서 동기
블로킹 `_db.probe_datasource()`(도달 불가 시 connection_timeout 까지 점유)를 직접 호출 → 그동안
**이벤트 루프 전체가 멈춰** 동시 요청이 직렬화된 것. TASK-0253 은 probe 를 `asyncio.to_thread`
로 스레드풀에 넘겨 루프를 비운다(프로젝트 기존 /api/ask 패턴과 동일).

검증 대상:
  T1  정상 — to_thread 경유라도 probe 결과(ok/elapsed_ms/error)가 그대로 응답에 실린다.
  T1b conn-tristate: 응답에 3단계 status 분류(빠른성공=healthy / 느린성공=unstable / 실패=down).
  T2  실패 — probe 실패 시 ok=False + errno 전달(자격증명 비유출 계약 유지).
  T3  비블로킹 핵심 — 느린(블로킹) probe 를 N개 **동시** 호출해도 이벤트 루프가 막히지 않아
       전체 소요가 직렬 합산이 아닌 ~1건 수준(가장 느린 1개)이다.

`make test`(agent 이미지, --no-deps)에서 DB/네트워크 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json
import time

import pytest

import app
from routers import admin_datasources  # feature-0012 P5b


@pytest.fixture(autouse=True)
def _reset_ds_test_throttle():
    """ds-conn-test: /test 쿨다운은 모듈 전역 상태(_ds_test_last_at) — 여러 테스트가 같은 key+actor 를
    재사용하므로 테스트 간 리셋해 쿨다운 누수(2번째 호출부터 429)를 막는다."""
    admin_datasources._ds_test_last_at.clear()
    yield
    admin_datasources._ds_test_last_at.clear()


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
    monkeypatch.setattr("shared.datasources.resolve",
                        lambda conn, key: {"engine": "mysql", "host": "h", "port": 3306,
                                           "user": "u", "password": "p"})
    monkeypatch.setattr(app, "_ssrf_check_host", lambda host: (True, "", host))
    monkeypatch.setattr("shared.db.probe_datasource", probe)


# ── T1: 정상 결과 전달 ──────────────────────────────────────────────────────────
def test_probe_ok_passthrough(monkeypatch):
    _install(monkeypatch, probe=lambda ds, *, timeout=None: (True, 12.3, ""))
    resp = asyncio.run(admin_datasources.admin_test_datasource("mysql-abc", _FakeRequest(), actor={"id": 1}, conn=_BenignConn()))
    assert resp.status_code == 200
    b = _body(resp)
    assert b["ok"] is True
    assert b["elapsed_ms"] == 12.3
    assert b["error"] == ""
    assert b["status"] == "healthy"  # conn-tristate: 12.3ms < SLOW(1000) → 정상


# ── T1b: conn-tristate — 느린 성공은 unstable(불안정) ───────────────────────────
def test_probe_slow_marks_unstable(monkeypatch):
    """연결은 성공(1745ms)했지만 SLOW(1000ms) 이상이면 status=unstable(빨강 '연결 불안정')."""
    _install(monkeypatch, probe=lambda ds, *, timeout=None: (True, 1745.0, ""))
    resp = asyncio.run(admin_datasources.admin_test_datasource("mysql-slow", _FakeRequest(), actor={"id": 1}, conn=_BenignConn()))
    b = _body(resp)
    assert b["ok"] is True
    assert b["elapsed_ms"] == 1745.0
    assert b["status"] == "unstable"


# ── T2: 실패 결과 + errno 전달(자격증명 비유출) ─────────────────────────────────
def test_probe_failure_errno(monkeypatch):
    _install(monkeypatch, probe=lambda ds, *, timeout=None: (False, 8000.0, "errno=2003"))
    resp = asyncio.run(admin_datasources.admin_test_datasource("mysql-abc", _FakeRequest(), actor={"id": 1}, conn=_BenignConn()))
    b = _body(resp)
    assert b["ok"] is False
    assert b["error"] == "errno=2003"
    assert b["status"] == "down"  # conn-tristate: 단발 테스트 실패 = 끊김
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
            admin_datasources.admin_test_datasource(f"mysql-{i}", _FakeRequest(), actor={"id": 1}, conn=_BenignConn()) for i in range(N)
        ])
        return results, time.monotonic() - start

    results, elapsed = asyncio.run(_run_all())
    assert all(r.status_code == 200 for r in results)
    assert all(_body(r)["ok"] for r in results)
    # 직렬이면 N*SLEEP=1.5s. to_thread 병렬이면 ~SLEEP. 넉넉히 절반(0.75s) 미만이면 비블로킹 입증.
    assert elapsed < (SLEEP * N) * 0.5, f"동시 probe 가 직렬화됨(elapsed={elapsed:.2f}s) — 이벤트 루프 블로킹 의심"


# ── T4: ds-conn-test 쿨다운(429) — per-(account,key) 반복 테스트 부하 방지 ──────────────
def test_conn_test_cooldown_throttles_repeat(monkeypatch):
    """같은 (account,key) 재테스트가 쿨다운 내면 probe 없이 429(throttled). 다른 account/key 는 독립."""
    _install(monkeypatch, probe=lambda ds, *, timeout=None: (True, 5.0, ""))
    r1 = asyncio.run(admin_datasources.admin_test_datasource("mysql-cd", _FakeRequest(), actor={"id": 7}, conn=_BenignConn()))
    assert r1.status_code == 200 and _body(r1)["ok"] is True
    # 즉시 재호출 — 쿨다운(기본 3s) 내 → 429.
    r2 = asyncio.run(admin_datasources.admin_test_datasource("mysql-cd", _FakeRequest(), actor={"id": 7}, conn=_BenignConn()))
    assert r2.status_code == 429
    b = _body(r2)
    assert b["throttled"] is True and b["ok"] is False and b["status"] == "unknown"
    assert isinstance(b["retry_after_ms"], int) and b["retry_after_ms"] >= 1
    assert "password" not in b and "host" not in b  # 자격증명 비유출 계약 유지
    # 다른 account(8) 는 독립 — 쿨다운 무관하게 통과.
    r3 = asyncio.run(admin_datasources.admin_test_datasource("mysql-cd", _FakeRequest(), actor={"id": 8}, conn=_BenignConn()))
    assert r3.status_code == 200
    # 다른 key 도 독립.
    r4 = asyncio.run(admin_datasources.admin_test_datasource("mysql-cd2", _FakeRequest(), actor={"id": 7}, conn=_BenignConn()))
    assert r4.status_code == 200


# ── T5: 미등록 key(404)·SSRF 차단은 throttle 대상 아님(무-probe 경로, NIT-3) ──────────────
def test_conn_test_404_not_throttled(monkeypatch):
    """resolve 실패(404) 는 probe 를 돌리지 않으므로 쿨다운을 소진하지 않는다 — 반복해도 404(429 아님)."""
    _install(monkeypatch, probe=lambda ds, *, timeout=None: (True, 5.0, ""))
    monkeypatch.setattr("shared.datasources.resolve", lambda conn, key: None)
    r1 = asyncio.run(admin_datasources.admin_test_datasource("nope", _FakeRequest(), actor={"id": 9}, conn=_BenignConn()))
    assert r1.status_code == 404
    r2 = asyncio.run(admin_datasources.admin_test_datasource("nope", _FakeRequest(), actor={"id": 9}, conn=_BenignConn()))
    assert r2.status_code == 404   # 여전히 404 — throttle 이 resolve 이후라 404 를 마스킹하지 않음
