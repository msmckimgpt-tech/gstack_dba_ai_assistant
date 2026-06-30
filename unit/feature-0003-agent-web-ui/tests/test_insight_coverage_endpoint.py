"""TASK-0253 — 제품 insight 완료율 엔드포인트의 단건(?product_id=) head-of-line 제거 회귀 테스트.

배경(라이브 UX 버그): 관리 콘솔 제품 화면 진입 시 좌측 제품 목록·우측 완료율이 전부 "분석 측정 중…"
으로 묶였다가 **가장 느린 제품의 라이브 DB 조회가 끝나야 한꺼번에** 갱신됐다. 원인은 (a) 프론트가
전체 제품을 한 번의 `/insight-coverage` 호출로 받고 전역 로딩 플래그로 묶은 점, (b) 백엔드가 모든
제품을 직렬 계산한 점. TASK-0253 은 프론트를 **제품별 단건 병렬 호출**로 바꾸고(백엔드 def 핸들러는
Starlette 스레드풀에서 자동 병렬 실행), 백엔드 단건 경로는 **대상 제품만 계산 후 즉시 break** 한다.

검증 대상:
  E1  ?product_id=N → 응답 coverage 에 N 만 포함(타 제품 제외).
  E2  ?product_id=N → 무관 제품의 _compute_product_insight_coverage 는 **호출되지 않는다**
       (단건이 느린 타 제품 계산을 기다리지 않음 = head-of-line 제거의 핵심).
  E3  product_id 미지정 → 전 제품 계산(기존 일괄 동작 무회귀).
  E4  console.access 미보유 403.
  E5  잘못된 product_id(비정수) 400.

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import json

import app


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


class _FakeRequest:
    def __init__(self, query=None):
        self.query_params = dict(query or {})
        self.headers = {}
        self.client = None


def _body(resp):
    return json.loads(resp.body)


def _install(monkeypatch, products, *, computed_log=None):
    """엔드포인트 의존성 monkeypatch. computed_log 가 주어지면 계산된 pid 를 기록(호출 추적)."""
    # TASK-0288: 제품 구성 조회(insight-coverage)는 product.read|manage 게이트.
    acct = {"id": 1, "permissions": {"console.access": True, "product.read": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    monkeypatch.setattr(app, "_list_products", lambda conn, include_inactive=False: list(products))
    # 캐시 우회 — 항상 compute 경로를 타도록(호출 추적이 의미를 갖게).
    monkeypatch.setattr(app, "_insight_cov_cache_get", lambda key: None)
    monkeypatch.setattr(app, "_insight_cov_cache_put", lambda key, val: None)

    def _compute(conn, p):
        pid = int(p["id"])
        if computed_log is not None:
            computed_log.append(pid)
        return {"measurable": True, "pct": 100.0, "total_objects": 1,
                "analyzed_objects": 1, "per_db": [], "engine": "mysql"}
    monkeypatch.setattr(app, "_compute_product_insight_coverage", _compute)
    return acct  # P5b DI: 직접호출 시 account 명시 주입용(AO — body perm 검사가 이 account 로 실행)


# ── E1: 단건 응답에 대상 제품만 ─────────────────────────────────────────────────
def test_single_product_returns_only_target(monkeypatch):
    products = [{"id": 1, "datasource_key": "ds-a"},
                {"id": 2, "datasource_key": "ds-b"},
                {"id": 3, "datasource_key": "ds-c"}]
    acct = _install(monkeypatch, products)
    resp = app.admin_products_insight_coverage(_FakeRequest({"product_id": "2"}), account=acct, conn=_BenignConn())
    assert resp.status_code == 200
    cov = _body(resp)["coverage"]
    assert set(cov.keys()) == {"2"}


# ── E2: 단건이 무관 제품을 계산하지 않음 (head-of-line 제거 핵심) ──────────────────
def test_single_product_skips_other_products_compute(monkeypatch):
    products = [{"id": 1, "datasource_key": "ds-a"},
                {"id": 2, "datasource_key": "ds-b"},
                {"id": 3, "datasource_key": "ds-c"}]
    log: list[int] = []
    acct = _install(monkeypatch, products, computed_log=log)
    app.admin_products_insight_coverage(_FakeRequest({"product_id": "2"}), account=acct, conn=_BenignConn())
    # 오직 대상 제품(2)만 계산 — 느릴 수 있는 1·3 은 건드리지 않는다.
    assert log == [2]


# ── E3: 미지정 시 전 제품 계산(무회귀) ─────────────────────────────────────────
def test_no_product_id_computes_all(monkeypatch):
    products = [{"id": 1, "datasource_key": "ds-a"},
                {"id": 2, "datasource_key": "ds-b"},
                {"id": 3, "datasource_key": "ds-c"}]
    log: list[int] = []
    acct = _install(monkeypatch, products, computed_log=log)
    resp = app.admin_products_insight_coverage(_FakeRequest(), account=acct, conn=_BenignConn())
    cov = _body(resp)["coverage"]
    assert set(cov.keys()) == {"1", "2", "3"}
    assert sorted(log) == [1, 2, 3]


# ── E4: 권한 게이트 ────────────────────────────────────────────────────────────
def test_requires_console_access(monkeypatch):
    nobody = {"id": 9, "permissions": {}}
    # P5b DI: AO 라 본문 perm 검사가 account 로 실행 → 직접호출에 account=nobody 명시 주입(console.access 없음 → 403).
    resp = app.admin_products_insight_coverage(_FakeRequest(), account=nobody, conn=_BenignConn())
    assert resp.status_code == 403


# ── E5: 잘못된 product_id ──────────────────────────────────────────────────────
def test_invalid_product_id_400(monkeypatch):
    acct = _install(monkeypatch, [{"id": 1, "datasource_key": "ds-a"}])
    resp = app.admin_products_insight_coverage(_FakeRequest({"product_id": "abc"}), account=acct, conn=_BenignConn())
    assert resp.status_code == 400
