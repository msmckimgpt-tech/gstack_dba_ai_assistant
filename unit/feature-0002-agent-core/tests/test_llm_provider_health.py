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


# ── bad_model (요청-레벨 400: 잘못된 모델명 라우팅) TASK-20260714-attach-grounding ──────
def test_litellm_invalid_model_name_is_bad_model():
    # 실관측: "/chat/completions: Invalid model name passed in model=auto. Call `/v1/models` ..."
    exc = FakeAPIError(
        "Error code: 400 - {'error': {'message': '/chat/completions: Invalid model name "
        "passed in model=auto. Call `/v1/models` to view available models'}}",
        status_code=400,
    )
    r = lph.classify_llm_provider_error(exc)
    assert r is not None
    assert r["kind"] == lph.KIND_BAD_MODEL
    assert r["retryable"] is False
    assert "모델" in r["message"]


def test_openai_model_not_found_is_bad_model():
    exc = FakeAPIError("The model `core` does not exist or you do not have access", status_code=404)
    assert lph.classify_llm_provider_error(exc)["kind"] == lph.KIND_BAD_MODEL


def test_bad_model_not_persisted_to_health():
    # 요청-레벨 오류 → 글로벌 provider health 미오염(persist_health=False).
    exc = FakeAPIError("Invalid model name passed in model=edge", status_code=400)
    r = lph.classify_llm_provider_error(exc)
    assert r["persist_health"] is False


# ── context_length (요청-레벨 400: 프롬프트가 컨텍스트 초과) ────────────────────────
def test_anthropic_context_limit_is_context_length():
    # 실관측 형태: "input length and max_tokens exceed context limit: 188240 + 21333 > 200000"
    exc = FakeAPIError(
        "Error code: 400 - input length and max_tokens exceed context limit: 188240 + 21333 > 200000",
        status_code=400,
    )
    r = lph.classify_llm_provider_error(exc)
    assert r is not None
    assert r["kind"] == lph.KIND_CONTEXT_LENGTH
    assert r["retryable"] is False


def test_openai_maximum_context_length_is_context_length():
    exc = FakeAPIError("This model's maximum context length is 200000 tokens", status_code=400)
    assert lph.classify_llm_provider_error(exc)["kind"] == lph.KIND_CONTEXT_LENGTH


def test_bedrock_input_too_long_is_context_length():
    exc = FakeAPIError("ValidationException: input is too long for requested model", status_code=400)
    assert lph.classify_llm_provider_error(exc)["kind"] == lph.KIND_CONTEXT_LENGTH


def test_context_length_message_is_actionable_and_not_persisted():
    exc = FakeAPIError("input is too long", status_code=400)
    r = lph.classify_llm_provider_error(exc)
    # 사용자가 스스로 복구할 수 있는 행동 안내(첨부를 나누거나 일부만) + 글로벌 health 미오염.
    assert "첨부" in r["message"] or "분량" in r["message"]
    assert r["persist_health"] is False


# ── 기존 provider-장애 kind 는 여전히 health 영속 대상(회귀 방지) ───────────────────
def test_existing_kinds_still_persist_health():
    cred = lph.classify_llm_provider_error(FakeAPIError("ExpiredTokenException"), provider="bedrock")
    assert cred["persist_health"] is True
    unavail = lph.classify_llm_provider_error(FakeAPIError("boom", status_code=503))
    assert unavail["persist_health"] is True


def test_bad_model_400_not_misclassified_as_auth():
    # 400(bad_model)이 auth(401/403) 로 오분류되지 않는지 순서 검증.
    exc = FakeAPIError("Invalid model name passed in model=auto", status_code=400)
    assert lph.classify_llm_provider_error(exc)["kind"] == lph.KIND_BAD_MODEL


# ── status 게이트 회귀 (REV-20260714T221500 적대 패널 MINOR-1/2) ──────────────────
# 위험 status(429/403)에 토큰/모델 어휘가 실려도 요청-레벨(persist_health=False) 로 훔쳐가지 않아야
# provider-health 배너가 억제되지 않는다. 이 가드가 없으면(_req_ok 게이트 제거 시) 아래가 깨진다.
def test_status_429_with_token_text_stays_throttled():
    # 실제 throttle(429)이 "too many tokens" 어휘 때문에 context_length 로 오분류되면 안 됨.
    exc = FakeAPIError("Rate limit: too many tokens submitted, slow down", status_code=429)
    r = lph.classify_llm_provider_error(exc)
    assert r["kind"] == lph.KIND_THROTTLED
    assert r["persist_health"] is True  # 실 provider 신호 → 글로벌 health 영속(배너 억제 금지)


def test_status_403_with_model_text_stays_auth():
    # 실제 auth(403)이 "unknown model" 어휘 때문에 bad_model 로 오분류되면 안 됨.
    exc = FakeAPIError("unknown model tier for this key", status_code=403)
    r = lph.classify_llm_provider_error(exc)
    assert r["kind"] == lph.KIND_AUTH_INVALID
    assert r["persist_health"] is True


def test_statusless_token_text_not_request_level():
    # status 를 잃은(래핑/네트워크) 예외가 토큰/모델 어휘를 담아도 요청-레벨 버킷으로 분류돼
    # persist_health=False 로 health 를 억제하면 안 된다(status 미상 → 요청-레벨 매칭 포기).
    for msg in ("too many tokens submitted, slow down", "unknown model tier"):
        r = lph.classify_llm_provider_error(FakeAPIError(msg, status_code=None))
        if r is not None:
            assert r["kind"] not in (lph.KIND_BAD_MODEL, lph.KIND_CONTEXT_LENGTH)
            assert r["persist_health"] is True
