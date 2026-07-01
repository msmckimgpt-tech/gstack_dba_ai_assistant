"""TASK-0295 — 작업 화면 제품 목록 product.access RBAC 게이트 회귀 테스트.

역할(role)에 특정 제품 접근 권한이 없으면 작업 화면 대화창 picker 에서 해당 제품이
제외되어야 한다 (mutation 경로 8곳의 403 enforcement 와 표시 정합 — 요청이 차단되는
제품을 목록에서도 숨김). 관리 콘솔 제품 목록(`_list_products(include_inactive=True)`)
에는 적용하지 않는다 (product.read/manage 축으로 별도 게이트 — TASK-0288 2축 분리).

검증 대상 (순수 함수 — DB 불필요, `make test` agent 컨테이너에서 `import app` 로 실행):
  T1  접근 권한 보유 제품만 남는다 (KR 권한만 → KR 만, MY/JP 제외).
  T2  account=None → 빈 목록.
  T3  모든 권한 회수 → 빈 목록 (각 제품 권한 없음 = 전부 제외).
  T4  product_key 대소문자 무관 (대문자 ProductKey ↔ 소문자 권한 코드).
  T5  product_key 없는 행 방어적 제외.
  T6  _coerce_default_product_id: default 가 접근 목록 안 → 그대로 유지.
  T7  _coerce_default_product_id: default 가 접근 목록 밖 → 첫 접근 가능 제품으로 보정.
  T8  _coerce_default_product_id: 빈 목록 → 0(없음).
  T9  정적: _filter_products_for_account_access 호출이 정확히 2곳(작업화면 전용),
        admin _list_products(include_inactive=True) 경로엔 미적용.
"""
from __future__ import annotations

from pathlib import Path

import app

APP_PY = Path(__file__).resolve().parents[1] / "src" / "app.py"


def _acct(*granted_keys: str) -> dict:
    """granted_keys(ProductKey, 대문자 허용)에 대한 product.access.<key> 만 부여한 mock 계정."""
    perms = {app._product_permission_code(k): True for k in granted_keys}
    return {"permissions": perms}


def _products(*keys: str) -> list[dict]:
    return [
        {"id": i + 1, "product_key": k, "name": f"제품-{k}", "is_active": True}
        for i, k in enumerate(keys)
    ]


def test_t1_only_accessible_products_remain():
    products = _products("KR", "MY", "JP")
    acct = _acct("KR")  # KR 만 접근 권한
    out = app._filter_products_for_account_access(acct, products)
    assert [p["product_key"] for p in out] == ["KR"]


def test_t2_none_account_empty():
    assert app._filter_products_for_account_access(None, _products("KR")) == []


def test_t3_all_revoked_empty():
    products = _products("KR", "MY")
    acct = _acct()  # 권한 0건 — 전 제품 회수
    assert app._filter_products_for_account_access(acct, products) == []


def test_t4_product_key_case_insensitive():
    # ProductKey 는 대문자, 권한 코드는 소문자 (_product_permission_code 가 lower 변환).
    products = _products("KR")
    acct = _acct("KR")
    out = app._filter_products_for_account_access(acct, products)
    assert len(out) == 1
    assert app._product_permission_code("KR") == "product.access.kr"


def test_t5_missing_product_key_excluded():
    products = [{"id": 1, "name": "키없음"}]  # product_key 부재 — 방어적 제외
    acct = _acct("KR")
    assert app._filter_products_for_account_access(acct, products) == []


def test_t6_coerce_default_in_accessible_kept():
    products = _products("KR", "MY")  # id 1, 2
    assert app._coerce_default_product_id(2, products) == 2


def test_t7_coerce_default_out_of_accessible_falls_back_first():
    products = _products("KR", "MY")  # id 1, 2
    assert app._coerce_default_product_id(99, products) == 1  # 접근 목록 밖 → 첫 제품


def test_t8_coerce_default_empty_zero():
    assert app._coerce_default_product_id(5, []) == 0
    assert app._coerce_default_product_id(None, []) == 0


def test_t9_filter_only_on_workspace_paths():
    """_filter_products_for_account_access 는 작업 화면 2곳에서만 호출되고
    admin _list_products(include_inactive=True) 경로엔 미적용이어야 한다."""
    # feature-0012 P5b: 핸들러 일부가 routers/ 로 추출됨(auth_me 등) → app.py + routers 합산 검색.
    _ROUTERS = APP_PY.parent / "routers"
    src = APP_PY.read_text(encoding="utf-8") + "".join(
        p.read_text(encoding="utf-8") for p in sorted(_ROUTERS.glob("*.py"))
    )
    call_count = src.count("_filter_products_for_account_access(account, products)")
    assert call_count == 2, f"작업화면 필터 호출이 정확히 2곳이어야 함 (실제 {call_count})"
    # admin 경로는 include_inactive=True — 필터 미적용
    assert "_list_products(conn, include_inactive=True)" in src
