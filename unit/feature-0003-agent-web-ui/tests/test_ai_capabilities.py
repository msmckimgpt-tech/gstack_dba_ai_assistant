"""feature-0023 conversation-quality-controls — `/api/ai/capabilities` 계약 + 보안 불변식.

외부 AI 가 대화 품질(모델·추론 강도·제품·폴더 지침·첨부)을 조정하려면 "이 토큰이 실제로 쓸 수
있는 값"을 알아야 한다. 익명 발견 자료(매니페스트·큐레이션 OpenAPI)는 static contract 전용이라
(SEC-20260724) 계정별 값을 담을 수 없으므로 본 엔드포인트가 그 간극을 닫는다.

검증하는 불변식:
  1. **익명 401** — 인스턴스 데이터(모델·제품·폴더 목록)가 무인증으로 새지 않는다.
  2. 인증 시 5축(model/reasoning_level/product/folder_instructions/attachments) 계약 제공.
  3. 모델·제품 목록이 **계정 권한 필터를 거친다** — 선택기(`/api/session`)와 같은 함수를 쓰므로
     capabilities 가 보여준 값을 `/api/ask` 가 403 하는 불일치가 없어야 한다.
  4. 권한 없는 축은 **조용한 빈 배열이 아니라** `available:false` + 사유(note).
  5. `conversation_id` 는 접근 가능한 대화만 — 남의 대화 설정 oracle 금지.
  6. 익명 매니페스트는 **포인터만** 싣고 값 목록(모델·제품 이름)을 싣지 않는다.

실행: python3 -m pytest unit/feature-0003-agent-web-ui/tests/test_ai_capabilities.py
"""
from __future__ import annotations

import json

import pytest

import app as appmod


_MODELS = [
    {"value": "claude-haiku-4", "label": "Haiku", "group": "Claude", "description": "빠름",
     "supports_vision": True},
    {"value": "claude-opus-5", "label": "Opus", "group": "Claude", "description": "심층",
     "supports_vision": True},
]
_PRODUCTS = [
    {"id": 3, "product_key": "KR", "name": "국내", "description": "국내 DB", "is_default": True,
     "datasource_key": "mysql_kr", "default_role_access": True, "icon_url": None},
    {"id": 4, "product_key": "MY", "name": "말레이", "description": "", "is_default": False,
     "datasource_key": "mssql_my", "default_role_access": True, "icon_url": None},
]


class _NullConn:
    def close(self):
        pass


@pytest.fixture
def caps_env(monkeypatch):
    """capabilities 가 동적 참조하는 app.* 심볼을 테스트 더블로 교체하는 빌더.

    핸들러는 DI 가 아니라 `app._connect_memory` + `app._get_authenticated_account` 를 직접 부르므로
    (익명 401 을 DI override 로 우회당하지 않게 하려는 의도적 inline 인증) monkeypatch 로 세운다.
    """

    def _setup(*, account, models=None, products=None, perms=None,
               folders=None, conv_access=True, conv_product=None, kv=None):
        monkeypatch.setattr(appmod, "_connect_memory", lambda: _NullConn(), raising=False)
        monkeypatch.setattr(appmod, "_get_authenticated_account",
                            lambda conn, request: account, raising=False)
        monkeypatch.setattr(appmod, "_filter_models_for_account_access",
                            lambda acct, ms, conn=None: list(models if models is not None else _MODELS),
                            raising=False)
        monkeypatch.setattr(appmod, "_list_products",
                            lambda conn, include_inactive=False: list(_PRODUCTS), raising=False)
        monkeypatch.setattr(appmod, "_filter_products_for_account_access",
                            lambda acct, ps: list(products if products is not None else _PRODUCTS),
                            raising=False)
        monkeypatch.setattr(appmod, "_get_default_product_id", lambda conn: 3, raising=False)
        monkeypatch.setattr(appmod, "_coerce_default_product_id",
                            lambda pid, ps: (int(pid) if any(int(p["id"]) == int(pid) for p in ps) else 0),
                            raising=False)
        monkeypatch.setattr(appmod, "_account_has_permission",
                            lambda acct, code: bool((perms or {}).get(code)), raising=False)
        monkeypatch.setattr(appmod, "_account_can_access_conversation",
                            lambda conn, acct, cid, own, any_: conv_access, raising=False)
        monkeypatch.setattr(appmod, "_load_conversation_product",
                            lambda conn, cid: conv_product, raising=False)
        monkeypatch.setattr(appmod, "load_memory_kv",
                            lambda conn, cid, key: (kv or {}).get(key, ""), raising=False)
        if folders is not None:
            from routers import _folder_store as store
            monkeypatch.setattr(store, "list_folders", lambda owner_id: list(folders), raising=False)

    return _setup


def _acct(**extra):
    a = {"id": 7, "Id": 7, "username": "svc-bot", "permissions": {}}
    a.update(extra)
    return a


# ── 1. 보안 불변식: 익명 차단 ────────────────────────────────────────────────────
def test_capabilities_requires_auth(client, caps_env):
    caps_env(account=None)
    r = client.get("/api/ai/capabilities")
    assert r.status_code == 401, r.status_code
    # 미인증 응답에 인스턴스 데이터(모델/제품 이름)가 새지 않는다.
    blob = r.text
    assert "claude-opus-5" not in blob and "국내" not in blob


# ── 2·3. 인증 시 5축 계약 + 권한 필터 반영 ──────────────────────────────────────
def test_capabilities_axes_and_permission_filtering(client, caps_env):
    caps_env(
        account=_acct(_auth_via="api_token"),
        # 모델 RBAC 로 haiku 만 열린 계정
        models=[_MODELS[0]],
        # product.access 로 KR 만 열린 계정
        products=[_PRODUCTS[0]],
        perms={"conversation.attachment.upload.own": True},
    )
    r = client.get("/api/ai/capabilities")
    assert r.status_code == 200, r.text
    body = r.json()
    qc = body["quality_controls"]
    assert set(qc) == {"model", "reasoning_level", "product", "folder_instructions", "attachments"}

    # 모델: 권한 필터 결과만 — 선택기/ask 게이트와 같은 함수를 쓰므로 불일치가 없어야 한다.
    values = [m["value"] for m in qc["model"]["values"]]
    assert values == ["claude-haiku-4"]
    assert "claude-opus-5" not in json.dumps(qc["model"], ensure_ascii=False)
    assert qc["model"]["default"] == "claude-haiku-4"
    # 추론 강도가 효과 있는 모델인지 외부 AI 가 구분할 수 있어야 한다.
    assert "supports_thinking" in qc["model"]["values"][0]

    # 추론 강도: 4단계 + 'normal' 기본(무주입 계약)
    levels = [v["value"] for v in qc["reasoning_level"]["values"]]
    assert levels == ["low", "normal", "high", "max"]
    assert qc["reasoning_level"]["default"] == "normal"

    # 제품: 접근 가능 목록 + 기본값 보정
    assert [p["id"] for p in qc["product"]["values"]] == [3]
    assert qc["product"]["default_product_id"] == 3
    assert qc["product"]["modes"] == ["auto", "pinned"]

    # 첨부: 권한 있으니 available
    assert qc["attachments"]["available"] is True

    # 각 축은 "어디에 거는지"를 스스로 설명해야 한다(외부 AI 가 문서 없이 조작 가능).
    for axis in qc.values():
        assert axis.get("set_via"), axis

    assert body["account"]["auth"] == "api_token"
    assert body["conversation"] is None


# ── 4. 권한 없는 축은 available:false + 사유 ────────────────────────────────────
def test_capabilities_folder_axis_unavailable_states_reason(client, caps_env):
    caps_env(account=_acct(), perms={})  # folder.list.own / attachment 없음
    body = client.get("/api/ai/capabilities").json()
    folder = body["quality_controls"]["folder_instructions"]
    assert folder["available"] is False
    assert folder["readable"] is False
    assert folder["values"] == []
    # 조용한 빈 배열 금지 — "폴더가 없다" 와 "볼 권한이 없다" 를 외부 AI 가 구분해야 한다.
    assert "folder.list.own" in folder["note"]
    assert body["quality_controls"]["attachments"]["available"] is False
    assert body["quality_controls"]["attachments"]["note"]


def test_capabilities_folder_axis_lists_instructions_when_permitted(client, caps_env):
    caps_env(
        account=_acct(),
        perms={"folder.list.own": True, "folder.manage.own": True},
        folders=[{"folder_id": 12, "parent_folder_id": None, "name": "매출 분석",
                  "instructions": "표로 요약한다.", "depth": 1}],
    )
    folder = client.get("/api/ai/capabilities").json()["quality_controls"]["folder_instructions"]
    assert folder["available"] is True
    assert folder["values"][0]["folder_id"] == 12
    assert folder["values"][0]["instructions"] == "표로 요약한다."


# ── 5. conversation_id 접근 게이트 ──────────────────────────────────────────────
def test_capabilities_conversation_settings_when_accessible(client, caps_env):
    caps_env(
        account=_acct(),
        perms={},
        conv_access=True,
        conv_product={"product_id": 3, "product_mode": "pinned", "product_name": "국내"},
        kv={"model": "claude-opus-5", "reasoning_level": "high"},
    )
    conv = client.get("/api/ai/capabilities?conversation_id=c-1").json()["conversation"]
    assert conv["conversation_id"] == "c-1"
    assert conv["model"] == "claude-opus-5"
    assert conv["reasoning_level"] == "high"
    assert conv["product_id"] == 3 and conv["product_mode"] == "pinned"


def test_capabilities_conversation_denied_leaks_nothing(client, caps_env):
    caps_env(
        account=_acct(),
        perms={},
        conv_access=False,
        conv_product={"product_id": 99, "product_mode": "pinned", "product_name": "남의제품"},
        kv={"model": "claude-opus-5"},
    )
    conv = client.get("/api/ai/capabilities?conversation_id=someone-else").json()["conversation"]
    assert conv.get("error")
    # 타 계정 대화의 설정이 새지 않는다.
    assert "product_id" not in conv and "model" not in conv
    assert "남의제품" not in json.dumps(conv, ensure_ascii=False)


# ── 6. 익명 매니페스트는 포인터만 (static contract 불변식 유지) ──────────────────
def test_manifest_advertises_quality_controls_without_instance_data(client):
    m = client.get("/api/ai/manifest").json()["ai_api"]
    qc = m["quality_controls"]
    assert qc["discover"].endswith("/api/ai/capabilities")
    axes = {a["axis"] for a in qc["axes"]}
    assert axes == {"model", "reasoning_level", "product", "folder_instructions", "attachments"}
    # ★ 익명 매니페스트에 계정별 인스턴스 값(모델 카탈로그·제품 이름)이 실리면 안 된다.
    blob = json.dumps(qc, ensure_ascii=False)
    assert "claude-" not in blob, "익명 매니페스트에 모델 카탈로그가 노출됨"
    assert "product_key" not in blob


def test_curated_openapi_covers_quality_endpoints(client):
    spec = client.get("/api/ai/openapi.json").json()
    paths = spec["paths"]
    for p in ("/api/ai/capabilities",
              "/api/conversations/{conversation_id}/product",
              "/api/folders",
              "/api/folders/{folder_id}",
              "/api/conversations/{conversation_id}/folder",
              "/api/conversations/{conversation_id}/attachments"):
        assert p in paths, p
    # 관리 경로는 여전히 없어야 한다(SEC-20260724 불변식 회귀 방지).
    assert all(not p.startswith("/api/admin") for p in paths), list(paths)
    # ask body 에 제품 축이 노출되고, 신규 대화 한정임이 스키마에 적혀 있어야 한다.
    ask_props = spec["components"]["schemas"]["AskRequest"]["properties"]
    assert "product_mode" in ask_props and "product_id" in ask_props
    assert "신규 대화" in ask_props["product_id"]["description"]
    # $ref 로 참조한 스키마가 실제로 정의돼 있어야 한다(깨진 참조 방지).
    for name in ("Capabilities", "Folder", "QualityAxis"):
        assert name in spec["components"]["schemas"], name


def test_guide_documents_quality_controls(client):
    body = client.get("/api/ai/guide").text
    assert "/api/ai/capabilities" in body
    for kw in ("reasoning_level", "product_mode", "instructions", "attachments"):
        assert kw in body, kw
