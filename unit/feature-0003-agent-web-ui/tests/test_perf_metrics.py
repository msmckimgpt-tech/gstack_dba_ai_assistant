"""feature-0026 (M1) — HTTP per-route 타이밍 계측(perf_metrics) 계약 테스트.

검증:
1. record/snapshot 집계 수학 — count/error/avg/p50·p95(버킷 상한)/db_per_req.
2. slow ring — SLOW_SAMPLE_MS 이상만 채집, maxlen 유계.
3. PerfTimingMiddleware e2e — 최소 FastAPI 앱에서 route template 단위 집계 +
   요청 중 shared.perf_counters.incr 가 요청-스코프로 귀속.
4. fail-open — record 예외가 요청/집계를 죽이지 않음.

app.py 를 import 하지 않는다(무거운 부트스트랩 회피) — perf_metrics 는 독립 모듈.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import perf_metrics as pm
from shared import perf_counters


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setenv("WEB_PERF_LOG_INTERVAL_SEC", "0")  # flush 데몬 미기동
    with pm._LOCK:
        pm._STATS.clear()
    pm._SLOW_RING.clear()
    yield


def test_record_aggregates_and_percentiles():
    pm.record("GET", "/api/x", 200, 12.5, {"mysql_conns": 1, "pg_conns": 3, "pg_ro_conns": 0})
    pm.record("GET", "/api/x", 200, 300.0, {"mysql_conns": 1, "pg_conns": 1, "pg_ro_conns": 1})
    pm.record("GET", "/api/x", 502, 1500.0, None)
    snap = pm.snapshot()
    row = snap["routes"][0]
    assert row["route"] == "/api/x"
    assert row["count"] == 3
    assert row["error_count"] == 1
    # 버킷 상한 percentile: p50 ≤ 500 버킷, p95 ≤ 2500 버킷 (실값 1500 의 상한)
    assert row["p50_ms_le"] <= 500
    assert 1500 <= row["p95_ms_le"] <= 2500
    assert row["max_ms"] == 1500.0
    assert row["db_per_req"]["pg_conns"] == round(4 / 3, 2)


def test_slow_ring_threshold_and_bound():
    pm.record("GET", "/fast", 200, 10.0, None)
    assert len(pm._SLOW_RING) == 0
    for _ in range(pm._SLOW_RING.maxlen + 10):
        pm.record("GET", "/slow", 200, float(pm.SLOW_SAMPLE_MS), None)
    assert len(pm._SLOW_RING) == pm._SLOW_RING.maxlen  # maxlen 유계 (§18.8 sec C2: 200)


def test_middleware_records_route_template_and_counters():
    app = FastAPI()

    @app.get("/items/{item_id}")
    def read_item(item_id: int):
        # 핸들러 안 DB 커넥션 시뮬레이션 — 요청-스코프 카운터로 귀속돼야 한다.
        perf_counters.incr("pg_conns")
        perf_counters.incr("pg_conns")
        perf_counters.incr("mysql_conns")
        return {"id": item_id}

    app.add_middleware(pm.PerfTimingMiddleware)
    client = TestClient(app)
    assert client.get("/items/7").status_code == 200
    snap = pm.snapshot()
    row = next(r for r in snap["routes"] if r["route"] == "/items/{item_id}")
    assert row["count"] == 1
    assert row["db_per_req"]["pg_conns"] == 2.0
    assert row["db_per_req"]["mysql_conns"] == 1.0
    # 요청 종료 후 컨텍스트 해제 — 밖에서는 no-op
    perf_counters.incr("pg_conns")
    assert perf_counters.current() is None


def test_middleware_unmatched_path_grouped():
    app = FastAPI()
    app.add_middleware(pm.PerfTimingMiddleware)
    client = TestClient(app)
    assert client.get("/no/such/route-abc").status_code == 404
    assert client.get("/no/such/route-def").status_code == 404
    snap = pm.snapshot()
    row = next(r for r in snap["routes"] if r["route"] == "(unmatched)")
    assert row["count"] == 2  # 원시 경로 카디널리티 폭주 없이 묶임


def test_record_fail_open(monkeypatch):
    # 내부 예외가 전파되지 않는다 (계측 실패 = 조용한 누락).
    monkeypatch.setattr(pm, "_bucket_index", lambda ms: (_ for _ in ()).throw(RuntimeError("boom")))
    pm.record("GET", "/x", 200, 1.0, None)  # 예외 미전파면 성공


def test_saturated_bucket_stays_finite_and_json_safe():
    # §18.8 F-1 회귀 잠금: 마지막 버킷(>600s)에 떨어져도 percentile 은 유한값 —
    # JSONResponse(allow_nan=False) 직렬화가 500 으로 죽지 않는다.
    import json as _json
    for _ in range(10):
        pm.record("POST", "/api/ask", 200, 900_000.0, None)  # 15분 long-poll wall
    snap = pm.snapshot()
    row = next(r for r in snap["routes"] if r["route"] == "/api/ask")
    assert row["p50_ms_le"] == float(pm.BUCKET_BOUNDS_MS[-1])
    assert row["p95_ms_le"] == float(pm.BUCKET_BOUNDS_MS[-1])
    _json.dumps(snap, allow_nan=False)  # ValueError 없이 직렬화돼야 한다


def test_static_mount_grouped_separately_from_unmatched():
    # §18.8 C-1: Mount(/static)는 route 미세팅 — "(unmatched)" 와 분리 집계.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.add_middleware(pm.PerfTimingMiddleware)
    client = TestClient(app)
    client.get("/static/app.js")   # mount 없이도 prefix 그룹으로 묶여야 한다
    client.get("/nope")
    snap = pm.snapshot()
    routes = {r["route"] for r in snap["routes"]}
    assert "/static/*" in routes and "(unmatched)" in routes


def test_status_zero_counted_as_aborted():
    # §18.8 C-2: status 미기록 완료는 error 가 아닌 aborted 로 분리(5xx 과소집계 가시화).
    pm.record("GET", "/api/y", 0, 5.0, None)
    row = next(r for r in pm.snapshot()["routes"] if r["route"] == "/api/y")
    assert row["aborted_count"] == 1 and row["error_count"] == 0


def test_unhandled_exception_counted_as_error():
    # §18.8 qa B1 회귀 잠금: unhandled 예외 500 은 ServerErrorMiddleware(미들웨어 바깥)가
    # 응답을 만들어 send 를 통과하지 않는다 — 예외 경로에서 500 으로 계상돼야 한다.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()

    @app.get("/boom")
    def boom():
        raise RuntimeError("x")

    app.add_middleware(pm.PerfTimingMiddleware)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/boom").status_code == 500
    row = next(r for r in pm.snapshot()["routes"] if r["route"] == "/boom")
    assert row["error_count"] == 1 and row["aborted_count"] == 0


# ── §18.8 qa C2: 신규 admin route RBAC 게이트 잠금 (인접 admin 라우터 관례) ──
def test_admin_perf_requires_permission(client, as_account):
    as_account(perms={"console.access": True})  # console.aiops.read 없음
    assert client.get("/api/admin/perf/http").status_code == 403


def test_admin_perf_ok_with_permission(client, as_account):
    as_account(perms={"console.access": True, "console.aiops.read": True})
    resp = client.get("/api/admin/perf/http")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and "routes" in body and "bucket_bounds_ms" in body


def test_method_whitelist_and_stats_cap():
    # §18.8 sec C1: 원문 method 토큰은 "(other)" 로 정규화, 키 공간은 하드 상한에서 overflow 로 접힘.
    pm.record("FROB", "/api/z", 200, 1.0, None)
    assert any(r["method"] == "(other)" and r["route"] == "/api/z" for r in pm.snapshot(top=200)["routes"])
    with pm._LOCK:
        pm._STATS.clear()
    for i in range(pm._STATS_MAX_KEYS + 5):
        pm.record("GET", f"/r{i}", 200, 1.0, None)
    with pm._LOCK:
        assert len(pm._STATS) <= pm._STATS_MAX_KEYS + 1
        assert pm._OVERFLOW_KEY in pm._STATS
