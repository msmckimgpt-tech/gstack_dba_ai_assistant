"""api-exposure-hardening (2026-08-11): 미인증 표면 축소 회귀 가드.

배경 — 외부 AI(codex)가 무인증 상태로 라이브 API 를 감사해 "인증 없이 LLM 공급자·모델 카탈로그·
내부 호스트명·장애 시각이 공개된다" 를 적발했고, 코드·라이브 양쪽에서 재현됐다. 세 엔드포인트 모두
`docs/SECURITY.md §7` 의 anonymous allowlist 표에 **등재되지 않은 채** 익명 200 을 반환하고 있었다
(정책 문서와 코드의 drift).

본 파일이 고정하는 불변식:
  1. 미인증 응답에 인프라 식별 정보(provider / public_host / 모델 카탈로그 / 장애 epoch)가 없다.
  2. **인증 응답은 불변** — 축소는 미인증 경로에만 적용된다(기능 회귀 0).

conftest 의 `client` 픽스처(TestClient + dependency_overrides)를 재사용한다.
"""
from __future__ import annotations

import pytest

import app as appmod


class _FakeConn:
    """`conn.close()` 만 받는 최소 fake — 핸들러가 미인증 경로에서 conn 을 닫는다."""

    def close(self):
        return None


def _override_conn(value):
    appmod.app.dependency_overrides[appmod.get_conn] = lambda: value


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    appmod.app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# /api/llm/health — 미인증은 state 만
# ─────────────────────────────────────────────────────────────────────────────
def test_llm_health_anonymous_omits_provider_and_timestamps(client, monkeypatch):
    """미인증 응답에서 provider·source·epoch 가 제거된다(state 만 잔존)."""
    monkeypatch.setattr(
        appmod,
        "_read_llm_provider_status",
        lambda: {
            "provider": "bedrock",
            "state": "ok",
            "source": "ask",
            "since_epoch": 1786381220,
            "updated_epoch": 1786419868,
        },
    )
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)
    _override_conn(object())

    body = client.get("/api/llm/health").json()

    assert body == {"state": "ok"}, "미인증 응답은 state 하나로 축소돼야 한다"
    for leaked in ("provider", "source", "since_epoch", "updated_epoch"):
        assert leaked not in body


def test_llm_health_authenticated_response_unchanged(client, monkeypatch):
    """인증 경로는 probe 결과를 그대로 — 축소가 인증 응답까지 깎지 않는다."""
    import modules.llm_provider_health as llmh

    monkeypatch.setattr(
        llmh, "probe_provider", lambda **_k: {"state": "ok", "provider": "bedrock", "probed": True}
    )
    monkeypatch.setattr(
        appmod, "_get_authenticated_account", lambda conn, request: {"id": 1, "permissions": {}}
    )
    _override_conn(object())

    assert client.get("/api/llm/health").json() == {
        "state": "ok",
        "provider": "bedrock",
        "probed": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# /api/session — 미인증은 authenticated 판정만
# ─────────────────────────────────────────────────────────────────────────────
def test_session_anonymous_omits_model_and_local_llm(client, monkeypatch):
    monkeypatch.setattr(appmod, "_connect_memory", lambda: _FakeConn())
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)
    monkeypatch.setattr(appmod, "_is_local_llm_available", lambda: True)
    monkeypatch.setattr(appmod, "_resolve_session_default_model", lambda: "claude-haiku-4")

    body = client.get("/api/session").json()

    assert body == {"authenticated": False}
    assert "default_model" not in body, "기본 모델은 로그인 전 노출 대상이 아니다"
    assert "local_llm_enabled" not in body, "로컬 LLM 운용 여부는 로그인 전 노출 대상이 아니다"


def test_session_anonymous_on_db_failure_also_minimal(client, monkeypatch):
    """DB 미가용 fallback 경로도 동일하게 축소된다(우회로 차단)."""

    def _boom():
        raise RuntimeError("no db")

    monkeypatch.setattr(appmod, "_connect_memory", _boom)
    monkeypatch.setattr(appmod, "_is_local_llm_available", lambda: True)
    monkeypatch.setattr(appmod, "_resolve_session_default_model", lambda: "claude-haiku-4")

    assert client.get("/api/session").json() == {"authenticated": False}


# ─────────────────────────────────────────────────────────────────────────────
# /api/api-vault/options — 미인증은 빈 카탈로그
# ─────────────────────────────────────────────────────────────────────────────
def test_api_vault_options_anonymous_returns_empty_catalog(client, monkeypatch):
    monkeypatch.setattr(appmod, "_connect_memory", lambda: _FakeConn())
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)

    body = client.get("/api/api-vault/options").json()

    assert body == {"default_model": None, "models": []}
    for leaked in ("public_host", "public_url", "provider"):
        assert leaked not in body, f"{leaked} 는 익명에게 노출되면 안 된다"


def test_api_vault_options_db_failure_does_not_leak_catalog(client, monkeypatch):
    """fail-soft 가 fail-open 이 되지 않는다 — 인증 확정 실패 시 카탈로그를 주지 않는다.

    종전 구현은 예외 시 `models = list(PUBLIC_API_MODEL_OPTIONS)` 로 되돌려, DB 를 불능으로 만들 수
    있는 요청자에게 오히려 전체 목록을 내주는 형태였다.
    """

    def _boom():
        raise RuntimeError("no db")

    monkeypatch.setattr(appmod, "_connect_memory", _boom)

    body = client.get("/api/api-vault/options").json()

    assert body == {"default_model": None, "models": []}


def test_api_vault_options_authenticated_response_unchanged(client, monkeypatch):
    """인증 응답의 키 집합과 권한 필터는 불변."""
    from shared.model_catalog import API_DEFAULT_MODEL

    filtered = [{"value": "claude-haiku-4", "label": "claude-haiku", "group": "Claude"}]
    monkeypatch.setattr(appmod, "_connect_memory", lambda: _FakeConn())
    monkeypatch.setattr(
        appmod, "_get_authenticated_account", lambda conn, request: {"id": 1, "permissions": {}}
    )
    monkeypatch.setattr(
        appmod, "_filter_models_for_account_access", lambda account, models, conn=None: filtered
    )

    body = client.get("/api/api-vault/options").json()

    assert body["models"] == filtered, "권한 필터 결과가 그대로 실려야 한다"
    assert body["default_model"] == API_DEFAULT_MODEL
    assert set(body) == {"default_model", "models", "public_host", "public_url", "provider"}
