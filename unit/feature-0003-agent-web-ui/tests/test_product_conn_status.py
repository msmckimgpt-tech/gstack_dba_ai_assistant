"""TASK-0261 — 대화 화면 제품 드롭업의 datasource 네트워크 상태 배지.

배경: 대화 화면 제품 선택 드롭업의 dot 은 지금까지 모드(auto 회색/pinned 파랑)만
표시했고 datasource 연결 상태를 반영하지 못했다. `_attach_product_conn_status` 가
conn_health 모니터(TASK-0250)의 사전계산 상태를 제품의 datasource 바인딩에 매핑해
per-binding `conn_status` + product 레벨 `conn_status_overall`(최악 상태)을 첨부한다.

검증 대상(`make test` agent 이미지, DB/네트워크 없이 monkeypatch):
  C1  단일 healthy 바인딩 → overall=healthy, 각 바인딩에 conn_status 첨부.
  C2  멀티 바인딩 최악상태 집계 — 하나라도 unstable → overall=unstable.
  C2c conn-tristate: down 이 최악(down > unstable > unknown > healthy) — 하나라도 down → overall=down.
  C3  unknown(미모니터) 섞임 — unstable > unknown > healthy 우선순위.
  C4  바인딩 없는 제품(기본 단일 MySQL) → overall=None(드롭업 모드색 유지).
  C5  좌표/비밀번호 비노출 — conn_status 에 status/elapsed_ms/checked_at 만.
  C6  graceful — conn_health 미가용/resolve 실패 시 status=unknown(예외 전파 없음).
"""
from __future__ import annotations

import app


def _make_products():
    return [
        {"id": 1, "name": "P1", "product_key": "p1",
         "datasources": [{"datasource_key": "ds_healthy", "is_primary": True, "sort_order": 0}]},
        {"id": 2, "name": "P2", "product_key": "p2",
         "datasources": [
             {"datasource_key": "ds_healthy", "is_primary": True, "sort_order": 0},
             {"datasource_key": "ds_unstable", "is_primary": False, "sort_order": 1},
         ]},
        {"id": 3, "name": "P3", "product_key": "p3",
         "datasources": [
             {"datasource_key": "ds_healthy", "is_primary": True, "sort_order": 0},
             {"datasource_key": "ds_unknown", "is_primary": False, "sort_order": 1},
         ]},
        {"id": 4, "name": "P4-default", "product_key": "p4", "datasources": []},
    ]


def _install_fakes(monkeypatch, *, health=None, raise_health=False, raise_resolve=False):
    """conn_health.snapshot 과 datasources.resolve/scope_key 를 가짜로 주입.

    `_attach_product_conn_status` 는 `from modules import conn_health/datasources` 로
    실제 모듈 객체를 잡으므로, sys.modules 교체가 아니라 **실제 모듈의 함수 속성을
    monkeypatch.setattr** 로 바꾼다(전체 테스트 동시 실행 시 import 캐시 충돌 방지).

    scope_key 규약: ds dict 의 'scope_key' 필드를 그대로 반환(실제 datasources.scope_key 와 동형).
    resolve(conn, key): 등록 키 → {'key':key, 'scope_key': 'sk_'+suffix} (미등록 키는 None).
    """
    import importlib
    ch = importlib.import_module("modules.conn_health")
    dsr = importlib.import_module("modules.datasources")

    if raise_health:
        def _snap():
            raise RuntimeError("monitor down")
    else:
        def _snap():
            return dict(health or {})
    monkeypatch.setattr(ch, "snapshot", _snap)

    _registry = {
        "ds_healthy": {"key": "ds_healthy", "scope_key": "sk_healthy"},
        "ds_unstable": {"key": "ds_unstable", "scope_key": "sk_unstable"},
        "ds_unknown": {"key": "ds_unknown", "scope_key": "sk_unknown"},
    }

    def _resolve(conn, key):
        if raise_resolve:
            raise RuntimeError("resolve boom")
        return _registry.get(str(key or "").strip().lower())

    def _scope_key(ds):
        return ds.get("scope_key") if ds else None

    monkeypatch.setattr(dsr, "resolve", _resolve)
    monkeypatch.setattr(dsr, "scope_key", _scope_key)


def test_c1_single_healthy(monkeypatch):
    _install_fakes(monkeypatch, health={
        "sk_healthy": {"status": "healthy", "last_elapsed_ms": 12.3, "checked_at": 100.0},
    })
    products = _make_products()
    app._attach_product_conn_status(None, products)
    p1 = products[0]
    assert p1["conn_status_overall"] == "healthy"
    assert p1["datasources"][0]["conn_status"]["status"] == "healthy"
    assert p1["datasources"][0]["conn_status"]["elapsed_ms"] == 12.3


def test_c2_multi_worst_unstable(monkeypatch):
    _install_fakes(monkeypatch, health={
        "sk_healthy": {"status": "healthy", "last_elapsed_ms": 5, "checked_at": 1.0},
        "sk_unstable": {"status": "unstable", "last_elapsed_ms": 99, "checked_at": 2.0},
    })
    products = _make_products()
    app._attach_product_conn_status(None, products)
    p2 = products[1]
    # 하나라도 unstable → overall=unstable (최악 상태).
    assert p2["conn_status_overall"] == "unstable"
    statuses = {b["datasource_key"]: b["conn_status"]["status"] for b in p2["datasources"]}
    assert statuses == {"ds_healthy": "healthy", "ds_unstable": "unstable"}


def test_c3_unknown_priority(monkeypatch):
    # ds_unknown 은 snapshot 에 없음 → unknown. healthy + unknown → overall=unknown(>healthy).
    _install_fakes(monkeypatch, health={
        "sk_healthy": {"status": "healthy", "last_elapsed_ms": 5, "checked_at": 1.0},
    })
    products = _make_products()
    app._attach_product_conn_status(None, products)
    p3 = products[2]
    assert p3["conn_status_overall"] == "unknown"


def test_c4_no_binding_overall_none(monkeypatch):
    _install_fakes(monkeypatch, health={})
    products = _make_products()
    app._attach_product_conn_status(None, products)
    p4 = products[3]
    assert p4["conn_status_overall"] is None  # 드롭업이 모드색 유지


def test_c5_no_coordinate_leak(monkeypatch):
    _install_fakes(monkeypatch, health={
        "sk_healthy": {
            "status": "healthy", "last_elapsed_ms": 7, "checked_at": 3.0,
            # 가짜 좌표/비밀번호 — 절대 conn_status 로 새지 않아야 함
            "host": "10.1.2.3", "port": 3306, "password": "SECRET", "user": "ro",
        },
    })
    products = _make_products()
    app._attach_product_conn_status(None, products)
    cs = products[0]["datasources"][0]["conn_status"]
    assert set(cs.keys()) == {"status", "elapsed_ms", "checked_at"}
    assert "host" not in cs and "password" not in cs and "user" not in cs


def test_c6_graceful_health_unavailable(monkeypatch):
    # conn_health.snapshot 이 예외를 던져도 전파되지 않고 모두 unknown.
    _install_fakes(monkeypatch, raise_health=True)
    products = _make_products()
    app._attach_product_conn_status(None, products)  # 예외 없어야 함
    assert products[0]["conn_status_overall"] == "unknown"
    assert products[0]["datasources"][0]["conn_status"]["status"] == "unknown"


def test_c6b_graceful_resolve_failure(monkeypatch):
    _install_fakes(monkeypatch, health={"sk_healthy": {"status": "healthy"}}, raise_resolve=True)
    products = _make_products()
    app._attach_product_conn_status(None, products)  # 예외 없어야 함
    assert products[0]["conn_status_overall"] == "unknown"


def test_c2c_down_is_worst(monkeypatch):
    # conn-tristate: down(끊김)이 최악 — healthy + down → overall=down.
    _install_fakes(monkeypatch, health={
        "sk_healthy": {"status": "healthy", "last_elapsed_ms": 5, "checked_at": 1.0},
        "sk_unstable": {"status": "down", "last_elapsed_ms": None, "checked_at": 2.0},
    })
    products = _make_products()
    app._attach_product_conn_status(None, products)
    p2 = products[1]
    assert p2["conn_status_overall"] == "down"
    statuses = {b["datasource_key"]: b["conn_status"]["status"] for b in p2["datasources"]}
    assert statuses == {"ds_healthy": "healthy", "ds_unstable": "down"}


def test_c2d_down_over_unstable(monkeypatch):
    # down 과 unstable 공존 → down(더 심각). 심각도 순위 down > unstable.
    _install_fakes(monkeypatch, health={
        "sk_healthy": {"status": "unstable", "last_elapsed_ms": 1745, "checked_at": 1.0},
        "sk_unstable": {"status": "down", "last_elapsed_ms": None, "checked_at": 2.0},
    })
    products = _make_products()
    app._attach_product_conn_status(None, products)
    assert products[1]["conn_status_overall"] == "down"


def test_c7_empty_products_noop(monkeypatch):
    _install_fakes(monkeypatch, health={})
    app._attach_product_conn_status(None, [])  # 빈 목록 — 예외 없이 무동작
