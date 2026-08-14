"""feature-0041 — authz seam 계약 테스트.

핵심 불변식 하나를 여러 각도에서 못박는다: **스코프는 호출자 주장이 아니라 계정 권한에서
나온다.** 외부 AI 가 `product_id`·`datasource` 를 인자로 넣을 수 있으므로, 그 인자가 권한
집합과 교차검증되지 않으면 표면 전체가 fail-open 이 된다.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "feature-0003-agent-web-ui", "src"))

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

    # 2026-08-14: 스코프는 라우터뿐 아니라 **스키마 allowlist** 까지다.
    def set_active_schema_allowlist(self, schemas):
        self.allowlist = list(schemas) if schemas is not None else None
        self.allow_calls = getattr(self, "allow_calls", 0) + 1

    def clear_active_schema_allowlist(self):
        self.allowlist = "cleared"
        self.clear_calls = getattr(self, "clear_calls", 0) + 1


class _FakeCore:
    def __init__(self, ds_list, single=None):
        self._ds_list = ds_list
        self._single = single if single is not None else {"key": "ds-single"}

    def _resolve_product_datasources(self, mem_conn, product_id):
        return self._ds_list

    def connect_with_retry(self, **kwargs):
        return _FakeConn()

    def _resolve_product_datasource(self, mem_conn, product_id):
        return self._single


class _FakeConn:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeScopeApp:
    """scoped_execution 이 쓰는 seam(제품 → 허용 스키마)만 흉내낸다.
    위 `_FakeApp`(제품 필터)과 다른 축이라 이름을 나눈다 — 같은 이름으로 덮으면
    앞의 테스트가 통째로 죽는다."""

    def __init__(self, allowed):
        self._allowed = allowed

    def _product_allowed_schemas(self, mem_conn, product_id):
        return self._allowed


def test_scoped_execution_resets_contextvar_on_success():
    tools, core = _FakeTools(), _FakeCore([{"_label": "a"}, {"_label": "b"}])
    with az.scoped_execution(core, tools, None, 1, app_mod=_FakeScopeApp(["s1"])) as ds_conn:
        assert ds_conn is None, "라우터 경로는 연결을 라우터가 소유하므로 None 을 준다"
        assert tools.current is not None
        assert tools.allowlist == ["s1"], "스키마 allowlist 가 안 걸렸다"
    assert tools.current is None and tools.reset_calls == 1
    assert tools.allowlist == "cleared", "allowlist 가 누수됐다 — 다음 요청이 이 스코프로 돈다"


def test_scoped_execution_resets_contextvar_on_exception():
    """★ 누수하면 다음 요청이 이전 요청 스코프로 tool 을 돈다 — 교차 계정 유출."""
    tools, core = _FakeTools(), _FakeCore([{"_label": "a"}, {"_label": "b"}])
    with pytest.raises(RuntimeError):
        with az.scoped_execution(core, tools, None, 1, app_mod=_FakeScopeApp(["s1"])):
            raise RuntimeError("handler blew up")
    assert tools.current is None and tools.reset_calls == 1
    assert tools.allowlist == "cleared"


def test_scoped_execution_closes_router_connections():
    tools, core = _FakeTools(), _FakeCore([{"_label": "a"}, {"_label": "b"}])
    with az.scoped_execution(core, tools, None, 1, app_mod=_FakeScopeApp(["s1"])):
        captured = tools.current
    assert captured.closed is True


def test_scoped_execution_single_datasource_connects_to_the_product_datasource():
    """★ 2026-08-14 — 이전엔 여기서 `None` 을 돌려주고 "호출측이 알아서" 로 넘겼다.
    호출측은 **메모리 DB 연결**을 그대로 넘겼고, 구조 조회가 내부 서버를 향해
    다른 대화의 첨부 샌드박스(`agent_attachment_*`)까지 목록에 나왔다.
    대부분의 제품이 단일 바인딩이라 이건 예외가 아니라 기본 경로였다."""
    tools, core = _FakeTools(), _FakeCore([], single={"key": "mssql-dk-dev"})
    with az.scoped_execution(core, tools, None, 1, app_mod=_FakeScopeApp(["dbauth"])) as ds_conn:
        assert ds_conn is not None, "메모리 DB 연결로 폴백하면 내부 스키마가 노출된다"
        assert isinstance(ds_conn, _FakeConn)
        assert tools.allowlist == ["dbauth"], "단일 경로에 allowlist 가 안 걸린다"
        captured = ds_conn
    assert captured.closed is True, "datasource 연결이 새고 있다"
    assert tools.allowlist == "cleared"


def test_scoped_execution_refuses_when_product_has_no_datasource():
    """★ 바인딩이 없으면 **데이터에 닿을 수 없다.** memory DB 로 폴백하면 그게 곧 유출이다."""
    tools, core = _FakeTools(), _FakeCore([], single=None)
    core._single = None
    with pytest.raises(az.ScopeDenied) as exc:
        with az.scoped_execution(core, tools, None, 1, app_mod=_FakeScopeApp([])):
            pass
    assert exc.value.code == "datasource_unbound"
    assert tools.allowlist == "cleared", "거절 경로에서도 allowlist 를 되돌려야 한다"


def test_allowlist_is_never_none_even_when_resolution_fails():
    """★ `set_active_schema_allowlist(None)` 은 tools 에서 **무제한**으로 읽힌다.
    해석 실패를 None 으로 흘리면 fail-open 이 된다."""
    class _BrokenApp:
        def _product_allowed_schemas(self, mem_conn, product_id):
            raise RuntimeError("메모리 DB 조회 실패")

    tools, core = _FakeTools(), _FakeCore([], single={"key": "x"})
    with az.scoped_execution(core, tools, None, 1, app_mod=_BrokenApp()):
        assert tools.allowlist == [], "해석 실패가 무제한으로 흘렀다"


def test_allowed_datasource_labels_lowercases_and_skips_blank():
    core = _FakeCore([{"_label": "KR_Live"}, {"_label": ""}, {"nope": 1}])
    assert az.allowed_datasource_labels(core, None, 1) == ["kr_live"]


def test_active_datasource_contextvar_is_actually_reset():
    """★ `set_active_datasource` 는 **토큰을 반환하지 않는다**(setter). 반환값을 token 으로
    받아 `if token is not None` 으로 되돌리면 **절대 되돌아가지 않는다** — ContextVar 가
    스레드에 남아 다음 요청이 이전 datasource 스코프로 돈다(교차 스코프 유출).
    실제로 무관한 테스트가 깨지며 드러났다."""
    from shared import config as cfg

    before = cfg.get_active_datasource()
    tools, core = _FakeTools(), _FakeCore([], single={"key": "ds-x", "scope_key": "mysql-abc",
                                                      "engine": "mysql"})
    with az.scoped_execution(core, tools, None, 1, app_mod=_FakeScopeApp(["s"])):
        assert cfg.get_active_datasource() == "mysql-abc", "스코프 안에서 안 걸렸다"
    assert cfg.get_active_datasource() == before, "ContextVar 가 누수됐다"


def test_active_datasource_is_reset_on_exception_too():
    from shared import config as cfg

    before = cfg.get_active_datasource()
    tools, core = _FakeTools(), _FakeCore([], single={"key": "ds-x", "scope_key": "mysql-abc"})
    with pytest.raises(RuntimeError):
        with az.scoped_execution(core, tools, None, 1, app_mod=_FakeScopeApp(["s"])):
            raise RuntimeError("boom")
    assert cfg.get_active_datasource() == before
