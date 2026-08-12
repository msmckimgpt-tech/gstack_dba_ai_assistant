"""feature-0041 — authz seam 계약 테스트.

핵심 불변식 하나를 여러 각도에서 못박는다: **스코프는 호출자 주장이 아니라 계정 권한에서
나온다.** 외부 AI 가 `product_id`·`datasource` 를 인자로 넣을 수 있으므로, 그 인자가 권한
집합과 교차검증되지 않으면 표면 전체가 fail-open 이 된다.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import tool_authz as az  # noqa: E402


class _FakeApp:
    """app 모듈의 제품 필터 seam 만 흉내낸다."""

    def __init__(self, products, *, filtered=None, raises=False, default_id=0):
        self._products = products
        self._filtered = products if filtered is None else filtered
        self._raises = raises
        self._default_id = default_id

    def _list_products(self, conn, include_inactive=False):
        if self._raises:
            raise RuntimeError("db down")
        return self._products

    def _filter_products_for_account_access(self, account, products):
        return self._filtered

    def _get_default_product_id(self, conn):
        return self._default_id

    def _coerce_default_product_id(self, pid, products):
        ids = {int(p["id"]) for p in products}
        return pid if pid in ids else (min(ids) if ids else 0)


_P1 = {"id": 1, "product_key": "alpha", "name": "Alpha"}
_P2 = {"id": 2, "product_key": "beta", "name": "Beta"}


def test_allowed_products_uses_account_filter():
    app = _FakeApp([_P1, _P2], filtered=[_P2])
    assert az.allowed_products(app, {"id": 7}, None) == [_P2]


def test_scope_unavailable_is_denied_not_empty():
    """권한 판정 실패를 빈 목록으로 접으면 fail-open 과 구별이 안 된다."""
    app = _FakeApp([], raises=True)
    with pytest.raises(az.ScopeDenied) as exc:
        az.allowed_products(app, {"id": 7}, None)
    assert exc.value.code == "scope_unavailable"


def test_resolve_product_rejects_out_of_scope_id():
    app = _FakeApp([_P1, _P2], filtered=[_P1])
    with pytest.raises(az.ScopeDenied) as exc:
        az.resolve_product(app, {"id": 7}, None, 2)      # 존재하지만 이 계정엔 미허용
    assert exc.value.code == "product_forbidden"


def test_resolve_product_hides_existence_of_forbidden_product():
    """'없는 제품' 과 '권한 없는 제품' 이 같은 문구여야 존재 여부가 새지 않는다."""
    app = _FakeApp([_P1], filtered=[_P1])
    forbidden = pytest.raises(az.ScopeDenied)
    with forbidden as a:
        az.resolve_product(app, {"id": 7}, None, 2)      # 실재하지 않음
    with pytest.raises(az.ScopeDenied) as b:
        az.resolve_product(app, {"id": 7}, None, 999)    # 실재하지 않음
    assert a.value.code == b.value.code == "product_forbidden"


def test_resolve_product_defaults_within_allowed_set():
    app = _FakeApp([_P1, _P2], filtered=[_P2], default_id=1)   # 기본값이 미허용 제품
    chosen = az.resolve_product(app, {"id": 7}, None, None)
    assert int(chosen["id"]) == 2                              # 허용 집합으로 보정


def test_resolve_product_denies_when_no_access():
    app = _FakeApp([_P1], filtered=[])
    with pytest.raises(az.ScopeDenied) as exc:
        az.resolve_product(app, {"id": 7}, None, None)
    assert exc.value.code == "no_product_access"


def test_bad_product_id_is_denied():
    app = _FakeApp([_P1], filtered=[_P1])
    with pytest.raises(az.ScopeDenied) as exc:
        az.resolve_product(app, {"id": 7}, None, "not-a-number")
    assert exc.value.code == "bad_product_id"


def test_datasource_cross_check():
    az.assert_datasource_allowed("", ["kr_live"])          # 미지정 통과(primary)
    az.assert_datasource_allowed("KR_LIVE", ["kr_live"])   # 대소문자 무시
    with pytest.raises(az.ScopeDenied) as exc:
        az.assert_datasource_allowed("secret_ds", ["kr_live"])
    assert exc.value.code == "datasource_forbidden"


def test_datasource_cross_check_denies_when_no_bindings():
    with pytest.raises(az.ScopeDenied):
        az.assert_datasource_allowed("anything", [])


# ── ContextVar 누수 방지 (교차 계정 유출의 실제 경로) ──────────────────────────

class _FakeTools:
    def __init__(self):
        self.current = None
        self.reset_calls = 0

    class _Router:
        def __init__(self, ds_list, connect):
            self.ds_list = ds_list
            self.closed = False

        def close_all(self):
            self.closed = True

    def _DatasourceRouter(self, ds_list, connect):   # noqa: N802 — 원 모듈 이름 미러
        return self._Router(ds_list, connect)

    def set_active_ds_router(self, router):
        self.current = router
        return ("token", router)

    def reset_active_ds_router(self, token):
        self.reset_calls += 1
        self.current = None


class _FakeCore:
    def __init__(self, ds_list):
        self._ds_list = ds_list

    def _resolve_product_datasources(self, mem_conn, product_id):
        return self._ds_list

    def connect_with_retry(self, **kwargs):
        return object()


def test_scoped_execution_resets_contextvar_on_success():
    tools, core = _FakeTools(), _FakeCore([{"_label": "a"}, {"_label": "b"}])
    with az.scoped_execution(core, tools, None, 1) as router:
        assert tools.current is router is not None
    assert tools.current is None and tools.reset_calls == 1


def test_scoped_execution_resets_contextvar_on_exception():
    """★ 누수하면 다음 요청이 이전 요청 스코프로 tool 을 돈다 — 교차 계정 유출."""
    tools, core = _FakeTools(), _FakeCore([{"_label": "a"}, {"_label": "b"}])
    with pytest.raises(RuntimeError):
        with az.scoped_execution(core, tools, None, 1):
            raise RuntimeError("handler blew up")
    assert tools.current is None and tools.reset_calls == 1


def test_scoped_execution_closes_router_connections():
    tools, core = _FakeTools(), _FakeCore([{"_label": "a"}, {"_label": "b"}])
    with az.scoped_execution(core, tools, None, 1) as router:
        captured = router
    assert captured.closed is True


def test_scoped_execution_single_datasource_yields_none():
    tools, core = _FakeTools(), _FakeCore([])
    with az.scoped_execution(core, tools, None, 1) as router:
        assert router is None
    assert tools.reset_calls == 0        # 걸지 않았으면 되돌릴 것도 없다


def test_allowed_datasource_labels_lowercases_and_skips_blank():
    core = _FakeCore([{"_label": "KR_Live"}, {"_label": ""}, {"nope": 1}])
    assert az.allowed_datasource_labels(core, None, 1) == ["kr_live"]
