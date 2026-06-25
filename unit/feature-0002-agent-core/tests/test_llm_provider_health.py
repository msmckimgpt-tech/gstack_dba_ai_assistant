"""LLM provider 외부요인 제한 분류기 — classify_llm_provider_error (TASK-20260619T014034).

PG 없이 순수 분류 로직만 검증(자격증명 만료/인증실패/쓰로틀/서비스불가/미설정/폴백 +
자격증명 비유출 + 사용자 친화 메시지). PG upsert/probe 는 통합경로(라이브)에서 검증.
"""
from __future__ import annotations

import modules.llm_provider_health as lph


class FakeAPIError(Exception):
    """OpenAI SDK 예외 shape 모사 — status_code / body 부착."""

    def __init__(self, message, status_code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# ── credential_expired (가장 구체적) ────────────────────────────────────
def test_expired_token_is_credential_expired():
    exc = FakeAPIError("ExpiredTokenException: The security token included in the request is expired.")
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r is not None
    assert r["kind"] == lph.KIND_CREDENTIAL_EXPIRED
    assert r["retryable"] is False
    assert "만료" in r["message"]
    assert "AWS Bedrock" in r["message"]  # provider 라벨 반영


def test_security_token_expired_phrase():
    exc = FakeAPIError("botocore error: the security token included in the request is expired")
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r["kind"] == lph.KIND_CREDENTIAL_EXPIRED


# ── auth_invalid ────────────────────────────────────────────────────────
def test_unrecognized_client_is_auth_invalid():
    exc = FakeAPIError("UnrecognizedClientException: The security token included in the request is invalid")
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r["kind"] == lph.KIND_AUTH_INVALID
    assert r["retryable"] is False


def test_status_403_is_auth_invalid():
    exc = FakeAPIError("forbidden", status_code=403)
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r["kind"] == lph.KIND_AUTH_INVALID


def test_status_401_is_auth_invalid():
    exc = FakeAPIError("unauthorized", status_code=401)
    assert lph.classify_llm_provider_error(exc)["kind"] == lph.KIND_AUTH_INVALID


# ── throttled ───────────────────────────────────────────────────────────
def test_throttling_is_throttled():
    exc = FakeAPIError("ThrottlingException: Rate exceeded")
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r["kind"] == lph.KIND_THROTTLED
    assert r["retryable"] is True


def test_status_429_is_throttled():
    exc = FakeAPIError("too many requests", status_code=429)
    assert lph.classify_llm_provider_error(exc)["kind"] == lph.KIND_THROTTLED


def test_throttled_message_is_service_level_without_provider_name():
    # 요청량 한도(throttle) 메시지는 "서비스 자체" 한도임을 명시하고 provider 이름
    # (AWS Bedrock 등)을 노출하지 않는다 — 계정 당 사용 한도와 주체를 구분한다.
    # (credential/auth/unavailable 등 다른 kind 는 관리자 진단용 provider 라벨 유지.)
    exc = FakeAPIError("ThrottlingException: Rate exceeded")
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r["kind"] == lph.KIND_THROTTLED
    assert "Bedrock" not in r["message"]
    assert "서비스" in r["message"]


# ── unavailable ─────────────────────────────────────────────────────────
def test_status_503_is_unavailable():
    exc = FakeAPIError("boom", status_code=503)
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r["kind"] == lph.KIND_UNAVAILABLE
    assert r["retryable"] is True


def test_service_unavailable_text():
    exc = FakeAPIError("ServiceUnavailableException: model not ready")
    assert lph.classify_llm_provider_error(exc)["kind"] == lph.KIND_UNAVAILABLE


# ── 폴백(분류 불가) → None ──────────────────────────────────────────────
def test_generic_code_error_returns_none():
    assert lph.classify_llm_provider_error(ValueError("local code bug: index out of range")) is None


def test_none_input_returns_none():
    assert lph.classify_llm_provider_error(None) is None


# ── 자격증명 비유출 + error_tag 경계 ────────────────────────────────────
def test_error_tag_no_secret_leak():
    exc = FakeAPIError(
        "AccessDeniedException: not authorized",
        status_code=403,
        body="aws_secret_access_key=SUPERSECRETVALUE region=us-east-1",
    )
    r = lph.classify_llm_provider_error(exc, provider="bedrock")
    assert r["kind"] == lph.KIND_AUTH_INVALID
    assert "SUPERSECRETVALUE" not in r["error_tag"]
    assert "SUPERSECRETVALUE" not in r["message"]
    assert len(r["error_tag"]) <= 120
    assert "AccessDenied" in r["error_tag"]  # 클래스명만 추출


# ── not_configured ──────────────────────────────────────────────────────
def test_not_configured_restriction_shape():
    r = lph.not_configured_restriction("bedrock")
    assert r["kind"] == lph.KIND_NOT_CONFIGURED
    assert r["retryable"] is False
    assert r["provider"] == "bedrock"
    assert r["message"]


# ── provider 라벨 ───────────────────────────────────────────────────────
def test_local_provider_label():
    exc = FakeAPIError("ExpiredTokenException")
    r = lph.classify_llm_provider_error(exc, provider="local")
    assert "로컬 LLM" in r["message"]


# ── confirmed 게이팅 (REV-0311 M3: 확정 신호만 sticky banner 영속) ──────────
def test_confirmed_true_for_specific_aws_class_token():
    # 특정 provider 오류 클래스명 매칭 → confirmed True (sticky banner 대상).
    assert lph.classify_llm_provider_error(FakeAPIError("ExpiredTokenException"), provider="bedrock")["confirmed"] is True
    assert lph.classify_llm_provider_error(FakeAPIError("AccessDeniedException: x"), provider="bedrock")["confirmed"] is True
    assert lph.classify_llm_provider_error(FakeAPIError("ThrottlingException: Rate exceeded"))["confirmed"] is True


def test_confirmed_false_for_bare_status_or_generic():
    # status code/generic 키워드만 매칭(transient·모호) → confirmed False (글로벌 banner 미영속).
    assert lph.classify_llm_provider_error(FakeAPIError("forbidden", status_code=403))["confirmed"] is False
    assert lph.classify_llm_provider_error(FakeAPIError("too many requests", status_code=429))["confirmed"] is False
    assert lph.classify_llm_provider_error(FakeAPIError("APIConnectionError: Connection reset by peer"))["confirmed"] is False


def test_not_configured_is_confirmed():
    assert lph.not_configured_restriction("bedrock")["confirmed"] is True


def test_record_restricted_skips_unconfirmed(monkeypatch):
    # 미확정 restriction 은 record_provider_state 를 호출하지 않는다(글로벌 banner 미영속).
    calls = []
    monkeypatch.setattr(lph, "record_provider_state", lambda *a, **k: calls.append((a, k)))
    lph.record_provider_restricted(lph.classify_llm_provider_error(FakeAPIError("forbidden", status_code=403)))
    assert calls == []  # 미확정 → skip
    lph.record_provider_restricted(lph.classify_llm_provider_error(FakeAPIError("ExpiredTokenException"), provider="bedrock"))
    assert len(calls) == 1  # 확정 → 영속
