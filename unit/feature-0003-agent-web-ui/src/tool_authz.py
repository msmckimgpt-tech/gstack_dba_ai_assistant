"""feature-0041 — 외부 도구 표면의 authz seam (스코프 해석 · 교차검증 · 라우터 수립).

## 왜 별도 모듈인가

내부 에이전트 경로에서 데이터소스 스코프는 **agent_core 가 run 시작에 정하고** tool 은
ContextVar(`modules/tools._ACTIVE_DS_ROUTER`)로 읽는다. 즉 tool 은 "누가 호출했는가" 를 모르고
**호출자가 이미 스코프를 정했다고 신뢰**한다. 내부에서는 그 신뢰가 성립한다 — 호출자가 우리
코드니까.

외부 표면에서는 성립하지 않는다. 외부 AI 가 `datasource`·`product_id` 를 **인자로** 넣기 때문에,
"인자를 그대로 믿고 라우터를 만드는" 순간 스코프가 사용자 권한이 아니라 **호출자 주장**으로
결정된다. 그래서 이 모듈이 그 사이에 선다:

    토큰 → 계정 → (계정 RBAC 로 필터된) 허용 제품 → 요청 product_id 교차검증 → 라우터

**tools.py 는 고치지 않는다.** 라우터가 이미 `router.labels()` 밖 라벨을 거절하므로
(`execute_tool` 의 미바인딩 라벨 분기), 라우터를 **계정 권한으로만** 구성하면 그 거절이 곧
authz 집행이 된다. 내부 경로는 이 모듈을 거치지 않으므로 **동작 0 변경**이다.

## fail-closed

권한 조회가 실패하면 빈 스코프를 주는 게 아니라 **예외를 올린다**(`ScopeDenied`). 조회 실패를
"허용 제품 없음" 으로 접으면 호출측이 그것을 403 이 아니라 "빈 결과" 로 렌더할 여지가 생기고,
그 순간 fail-open 과 구별이 안 된다.
"""
from __future__ import annotations

import contextlib
from typing import Any, Iterator


class ScopeDenied(Exception):
    """요청 스코프가 계정 권한 밖이거나 권한 판정 자체가 불가능. 호출측은 403 으로 옮긴다."""

    def __init__(self, message: str, *, code: str = "scope_denied") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def allowed_products(app_mod: Any, account: dict[str, Any], conn) -> list[dict[str, Any]]:
    """이 계정이 접근 가능한 제품 목록.

    `/api/session`·`/api/ai/capabilities` 와 **같은 필터 함수**(`_filter_products_for_account_access`)
    를 쓴다 — 표시와 집행이 갈라지면 외부 AI 는 "목록에 있는데 403" 을 만나고, 그 불일치는
    권한 버그와 구별되지 않는다(feature-0023 이 세운 표시-집행 정합 원칙).

    Raises:
        ScopeDenied: 제품 목록 조회 자체가 실패(권한 판정 불가 → fail-closed).
    """
    try:
        products = app_mod._list_products(conn, include_inactive=False)
        return list(app_mod._filter_products_for_account_access(account, products) or [])
    except Exception as exc:  # noqa: BLE001 — 판정 불가는 거부지 빈 목록이 아니다
        raise ScopeDenied(f"제품 권한을 판정할 수 없습니다: {exc}", code="scope_unavailable") from exc


def resolve_product(app_mod: Any, account: dict[str, Any], conn,
                    requested_product_id: Any) -> dict[str, Any]:
    """요청 product_id 를 계정 허용 집합과 **교차검증**해 확정 제품을 반환한다.

    `requested_product_id` 가 비어 있으면 계정의 기본 제품으로 보정한다(기본값도 허용 집합
    안에서만 고른다 — `_coerce_default_product_id` 동형).

    Raises:
        ScopeDenied: 허용 집합이 비었거나, 요청 제품이 그 안에 없음.
    """
    products = allowed_products(app_mod, account, conn)
    if not products:
        raise ScopeDenied("이 계정에 접근 가능한 제품이 없습니다.", code="no_product_access")

    by_id = {int(p.get("id") or 0): p for p in products}

    if requested_product_id in (None, "", 0, "0"):
        try:
            default_pid = int(app_mod._coerce_default_product_id(
                app_mod._get_default_product_id(conn), products) or 0)
        except Exception:
            default_pid = 0
        chosen = by_id.get(default_pid) or products[0]
        return chosen

    try:
        pid = int(requested_product_id)
    except (TypeError, ValueError):
        raise ScopeDenied(f"product_id 가 올바르지 않습니다: {requested_product_id!r}",
                          code="bad_product_id") from None

    if pid not in by_id:
        # 존재 여부를 흘리지 않는다 — "없는 제품" 과 "권한 없는 제품" 을 같은 문구로 돌린다.
        raise ScopeDenied(f"product_id={pid} 에 접근할 수 없습니다.", code="product_forbidden")
    return by_id[pid]


def allowed_datasource_labels(agent_core_mod: Any, mem_conn, product_id: int) -> list[str]:
    """확정 제품에 바인딩된 datasource 라벨 목록(라우터가 받아들일 값의 정본).

    외부 AI 가 넘긴 `datasource` 인자를 검증할 때 이 목록과 대조한다.
    """
    try:
        rows = agent_core_mod._resolve_product_datasources(mem_conn, int(product_id)) or []
    except Exception:
        rows = []
    return [str(r.get("_label") or "").strip().lower() for r in rows if r.get("_label")]


def assert_datasource_allowed(requested: Any, labels: list[str]) -> None:
    """`datasource` 인자 교차검증. 미지정은 통과(라우터가 primary 로 해석).

    Raises:
        ScopeDenied: 요청 라벨이 이 제품 바인딩 밖.
    """
    req = str(requested or "").strip().lower()
    if not req:
        return
    if req not in labels:
        raise ScopeDenied(
            f"datasource '{req}' 는 이 제품에 바인딩돼 있지 않습니다. "
            f"사용 가능: {', '.join(labels) if labels else '(없음)'}",
            code="datasource_forbidden")


@contextlib.contextmanager
def scoped_execution(agent_core_mod: Any, tools_mod: Any, mem_conn,
                     product_id: int) -> Iterator[Any]:
    """확정 제품의 datasource 라우터를 ContextVar 에 걸고, 블록을 벗어나면 반드시 되돌린다.

    yield 값은 라우터(`_DatasourceRouter | None`). None 이면 단일-datasource 제품이라
    호출측이 `_resolve_product_datasource` 단일 경로로 연결을 잡아야 한다.

    **반드시 finally 로 reset** 한다 — 웹 프로세스는 요청 간 스레드를 재사용하므로, 누수되면
    다음 요청이 **이전 요청의 스코프**로 tool 을 돌린다(교차 계정 유출).
    """
    router = None
    token = None
    try:
        ds_list = agent_core_mod._resolve_product_datasources(mem_conn, int(product_id)) or []
        if ds_list:
            def _connect_ds(ds_dict):
                return agent_core_mod.connect_with_retry(
                    database=None, autocommit=True, datasource=ds_dict)
            router = tools_mod._DatasourceRouter(ds_list, _connect_ds)
            token = tools_mod.set_active_ds_router(router)
        yield router
    finally:
        if token is not None:
            try:
                tools_mod.reset_active_ds_router(token)
            except Exception:
                pass
        if router is not None:
            try:
                router.close_all()
            except Exception:
                pass


# ── L4: 권한 비대칭 flag (feature-0041) ───────────────────────────────────────

def permission_asymmetry(sessions: "list[dict[str, Any]]") -> dict[str, Any] | None:
    """같은 `client_id` 에 **권한 집합이 크게 다른** 세션이 동시 활성인지 판정한다.

    ## 왜 이 축인가

    한 AI 런타임이 A·B·C 계정 세션을 동시에 다루는 것은 허용된다(내부 서비스는 병렬 작업이
    필요하다). 그런데 **오염의 실제 피해 크기는 세션 수가 아니라 권한 격차**에 달려 있다 —
    같은 제품만 보는 세션끼리 섞이면 손해가 작고, 한쪽만 민감 데이터소스에 닿을 수 있으면 크다.
    그래서 차단이 아니라 **위험 구간만 조준해 표시**한다.

    Args:
        sessions: `[{"account_id": int, "products": set|list[int]}, …]` — 같은 client 의 활성 세션.

    Returns:
        비대칭이 유의하면 finding dict, 아니면 None. 판정은 **자카드 유사도**로 한다 —
        교집합 크기만 보면 큰 집합끼리의 부분 겹침을 과소평가하고, 차집합만 보면 한쪽이
        작을 때 과대평가한다.

    ⚠ 이 함수는 **표시 전용**이다. 차단하면 병렬 세션 허용 결정(2026-08-12)을 뒤집는 것이 된다.
    """
    live = [s for s in (sessions or []) if s.get("account_id") is not None]
    if len(live) < 2:
        return None

    sets = {int(s["account_id"]): {int(p) for p in (s.get("products") or ())} for s in live}
    accounts = sorted(sets)
    worst: tuple[float, int, int] | None = None
    for i, a in enumerate(accounts):
        for b in accounts[i + 1:]:
            sa, sb = sets[a], sets[b]
            union = sa | sb
            if not union:
                continue                      # 둘 다 권한 없음 — 비교 대상 아님
            jaccard = len(sa & sb) / len(union)
            if worst is None or jaccard < worst[0]:
                worst = (jaccard, a, b)

    if worst is None:
        return None
    jaccard, a, b = worst
    if jaccard >= 0.5:                        # 절반 이상 겹치면 유의한 비대칭 아님
        return None
    # ⚠ 반환값에 **계정 id 를 담지 않는다**(codex P1): 이 finding 은 원장·운영자용이고,
    #   호출자에게 상대 계정을 알려주면 교차 테넌트 정보 노출이 된다(`client_id` 는 공유 가능한
    #   앱 식별자다). 운영자는 원장의 account_id·client_id 컬럼으로 대상을 특정할 수 있다.
    return {
        "kind": "permission_asymmetry",
        "n_accounts": len(accounts),
        "jaccard": round(jaccard, 3),
        "detail": (f"같은 client 에 권한 격차가 큰 세션이 동시 활성입니다 "
                   f"(계정 {len(accounts)}개, 최소 제품집합 유사도 {jaccard:.2f}). "
                   f"교차오염이 일어나면 피해가 큰 조합입니다."),
    }
