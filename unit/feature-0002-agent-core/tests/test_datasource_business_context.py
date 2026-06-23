"""ITEM-04 — datasource 비즈니스 컨텍스트(Description/DomainTags) 단위 테스트.

LLM 무관: registry row→ds 매핑, router.describe() 노출, 멀티DS 그라운딩 프롬프트 조립을
순수 함수로 검증(acceptance: "설명이 그라운딩 프롬프트에 노출 · 단일DS 무영향").
"""
import agent_core
from modules import datasources as ds_mod
from modules import tools as tools_mod


# ── _row_to_ds: Description/DomainTags 매핑 + 구 스키마 graceful ──────────────
def _row(extra):
    # (key, engine, host, port, user, passwordenc=None, defaultdb, encver, insightenabled, *extra)
    return ("sales", "mysql", "h", 3306, "u", None, "salesdb", 1, 1, *extra)


def test_row_to_ds_maps_description_and_tags():
    ds = ds_mod._row_to_ds(None, _row(("영업 거래 데이터", "sales,orders,revenue")))
    assert ds["description"] == "영업 거래 데이터"
    assert ds["domain_tags"] == ["sales", "orders", "revenue"]


def test_row_to_ds_blank_tags_and_desc():
    ds = ds_mod._row_to_ds(None, _row(("", "  ,  ,")))
    assert ds["description"] is None
    assert ds["domain_tags"] == []


def test_row_to_ds_legacy_9col_graceful():
    # 구 스키마(Description/DomainTags 컬럼 부재) → None/[] 기본(기존 동작 보존).
    ds = ds_mod._row_to_ds(None, ("sales", "mysql", "h", 3306, "u", None, "salesdb", 1, 1))
    assert ds["description"] is None
    assert ds["domain_tags"] == []


# ── _DatasourceRouter.describe(): description/domain_tags 노출(좌표/비밀 비노출) ──
def test_router_describe_exposes_business_context():
    dss = [{
        "_label": "sales", "_is_primary": True, "_allow_schemas": ["salesdb"],
        "engine": "mysql", "host": "secret-host", "password": "secret",
        "description": "영업 거래 데이터", "domain_tags": ["sales", "orders"],
    }]
    router = tools_mod._DatasourceRouter(dss, lambda ds: None)
    out = router.describe()
    assert len(out) == 1
    d = out[0]
    assert d["description"] == "영업 거래 데이터"
    assert d["domain_tags"] == ["sales", "orders"]
    # 좌표/비밀번호는 describe() 에 절대 노출 안 됨.
    assert "host" not in d and "password" not in d


# ── 멀티DS 그라운딩 프롬프트: 설명/도메인 노출 + 단일DS(빈 입력) 무영향 ──────────
def test_grounding_injects_description():
    desc = [{
        "label": "sales", "engine": "mysql", "is_primary": True, "schemas": ["salesdb"],
        "description": "영업 거래 데이터", "domain_tags": ["sales", "orders"],
    }]
    out = agent_core._format_multi_ds_grounding(desc)
    assert "ACCESSIBLE DATASOURCES" in out
    assert "**sales**" in out
    assert "설명: 영업 거래 데이터" in out          # ← acceptance: 설명이 프롬프트에 노출
    assert "도메인: sales, orders" in out


def test_grounding_empty_when_no_datasources():
    # 단일DS/미바인딩 제품 → 빈 문자열(프롬프트 무변경, 무영향).
    assert agent_core._format_multi_ds_grounding([]) == ""


def test_grounding_omits_missing_description():
    # 설명 미입력 datasource 는 설명 라인 생략(기존 라벨/엔진/DB 라인만).
    desc = [{"label": "ops", "engine": "mysql", "is_primary": False, "schemas": ["opsdb"]}]
    out = agent_core._format_multi_ds_grounding(desc)
    assert "**ops**" in out
    assert "설명:" not in out
    assert "도메인:" not in out
