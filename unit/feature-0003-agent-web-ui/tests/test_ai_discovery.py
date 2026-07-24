"""feature-0023 api-discovery — 외부 AI 발견 진입점 계약 + 보안 불변식 테스트.

발견 엔드포인트는 익명(무인증)이라 DB 없이 TestClient 로 검증한다. 핵심:
- /llms.txt · /.well-known/ai-conversation-api.json · /api/ai/manifest · /api/ai/guide = 200
- 매니페스트 보안 불변식: conversation-only (관리 `/api/admin/*` 미포함), Bearer 인증 명시
- FastAPI 기본 /openapi.json · /docs · /redoc = 404 (SEC-20260724 비활성화)
- /api/admin/openapi.json = 401 (무인증) — admin-gated
"""
from __future__ import annotations

import json


def test_llms_txt_served(client):
    r = client.get("/llms.txt")
    assert r.status_code == 200, r.status_code
    body = r.text
    assert "Conversation API" in body
    assert "Bearer" in body
    assert "/api/ai/guide" in body


def test_manifest_contract_and_security_invariants(client):
    for path in ("/.well-known/ai-conversation-api.json", "/api/ai/manifest"):
        r = client.get(path)
        assert r.status_code == 200, (path, r.status_code)
        m = r.json()
        # 인증 계약
        assert m["ai_api"]["auth"]["scheme"] == "Bearer"
        assert "how_to_obtain" in m["ai_api"]["auth"]
        # conversation 엔드포인트 존재
        paths = [e["path"] for e in m["ai_api"]["endpoints"]]
        assert "/api/ask" in paths
        assert "/api/new_conversation" in paths
        # ★ 보안 불변식: 호출 가능한 엔드포인트 카탈로그에 관리 경로가 없어야
        #   (설명 필드 excluded/notes 는 "/api/admin/* 은 제외"라 언급할 수 있으므로 blob 전체가
        #    아니라 endpoints 카탈로그의 실제 path 만 검사한다.)
        assert all(not str(p).startswith("/api/admin") for p in paths), paths
        assert all("admin" not in str(e.get("summary", "")).lower() for e in m["ai_api"]["endpoints"])
        # 스코프·제외가 명시돼 AI 가 경계를 학습
        blob = json.dumps(m, ensure_ascii=False)
        assert "denylist" in blob or "관리" in m["ai_api"]["excluded"]


def test_manifest_has_contact_and_openapi_and_sync(client):
    m = client.get("/api/ai/manifest").json()["ai_api"]
    # REV FINDING #2: 토큰 문의 연락처 노출
    assert m["auth"].get("contact"), "auth.contact(토큰 문의처) 누락"
    # REV FINDING #4: 기계판독 스키마 링크
    assert m.get("openapi_url", "").endswith("/api/ai/openapi.json")
    # REV FINDING #3: /api/ask 동기 dispatch 명시
    ask = [e for e in m["endpoints"] if e["path"] == "/api/ask"][0]
    assert "synchronous" in ask.get("dispatch", "")


def test_curated_openapi_conversation_only(client):
    r = client.get("/api/ai/openapi.json")
    assert r.status_code == 200, r.status_code
    spec = r.json()
    assert spec["openapi"].startswith("3.1")
    paths = list(spec["paths"].keys())
    assert "/api/ask" in paths and "/api/history" in paths
    # ★ 보안 불변식: 큐레이션 스펙에 관리 경로 없어야
    assert all(not p.startswith("/api/admin") for p in paths), paths
    # Bearer 보안 스킴
    assert spec["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    # AskRequest 스키마가 message 필수
    assert "message" in spec["components"]["schemas"]["AskRequest"]["required"]


def test_guide_served(client):
    r = client.get("/api/ai/guide")
    assert r.status_code == 200, r.status_code
    body = r.text
    assert "Bearer" in body
    assert "/api/ask" in body
    # 관리 콘솔 제외가 가이드에 명시
    assert "관리 콘솔" in body


def test_openapi_and_docs_disabled(client):
    # SEC-20260724: 익명 전체 스키마 노출 비활성화 → 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_admin_openapi_requires_auth(client):
    # admin-gated 대체 — 무인증은 401(로그인 필요)
    r = client.get("/api/admin/openapi.json")
    assert r.status_code in (401, 500), r.status_code  # 401 정상; DB 미가용 환경은 500(db connection failed)


def test_manifest_catalog_source_is_curated_not_introspected():
    # 불변식 #3: 카탈로그는 수기 관리 정본(자동 introspection 아님) — 소스에 상수 존재.
    import os
    src = os.path.join(os.path.dirname(__file__), "..", "src", "routers", "ai_discovery.py")
    txt = open(src, encoding="utf-8").read()
    assert "_CONVERSATION_ENDPOINTS" in txt
    # app.openapi() 자동 스키마를 매니페스트에 쓰지 않아야(admin 유출 방지) — 매니페스트 함수는
    # _CONVERSATION_ENDPOINTS 를 쓰고, app.app.openapi() 는 admin-gated 라우트에서만.
    assert "def _manifest" in txt
    # `_manifest` 함수 본문만 슬라이스(다음 top-level def 까지). 뒤에 _openapi_spec 등이 와도
    # 그 docstring 의 "openapi()" 언급에 오검출되지 않게 함수 경계로 자른다.
    start = txt.index("def _manifest")
    nxt = txt.index("\ndef ", start + 1)
    manifest_fn = txt[start:nxt]
    assert "openapi()" not in manifest_fn, "매니페스트가 자동 openapi introspection 을 쓰면 admin 유출 위험"
