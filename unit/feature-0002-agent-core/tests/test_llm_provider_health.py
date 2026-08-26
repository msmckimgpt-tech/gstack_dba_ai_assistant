"""LLM provider 외부요인 제한 분류기 — classify_llm_provider_error (TASK-20260619T014034).

PG 없이 순수 분류 로직만 검증(자격증명 만료/인증실패/쓰로틀/서비스불가/미설정/폴백 +
자격증명 비유출 + 사용자 친화 메시지). PG upsert/probe 는 통합경로(라이브)에서 검증.
"""
from __future__ import annotations

import time

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


# ── active probe 요청 구성 (thinking budget 오진 회귀 방지) ─────────────────
# 배경: probe 가 max_tokens=1 고정으로 thinking 강제 alias(claude-*, litellm config budget_tokens=5000)에
# 보내면 Anthropic 제약(max_tokens > thinking.budget_tokens) 위반 → 항상 400 → classify None →
# record_provider_ok/restricted 어느 것도 못 남겨 stale restricted 배너를 영영 해소 못 했다.
# (llm-routing-interactive-split "thinking budget > max_tokens 오진"). probe 는 valid ping 이어야 한다.

class _CapturingClient:
    def __init__(self, sink):
        self._sink = sink
        self.chat = self  # client.chat.completions.create 체인 모사
        self.completions = self

    def create(self, **kwargs):
        self._sink.append(kwargs)
        return object()  # 성공 응답(내용 무관 — probe 는 예외 유무만 본다)


def _run_probe(monkeypatch, model, supports_thinking, *, force=True, state="ok", ts=0.0):
    captured: list = []
    ok_calls: list = []
    # feature-0043: 이 헬퍼의 대상은 **게이트 뒤의 ping 계약**(thinking budget·max_tokens·throttle)
    # 이다. 게이트가 닫힌 채 두면 probe 가 첫 줄에서 반환해 captured 가 항상 비고, 검사하려던
    # 계약을 아무도 안 본다(vacuous pass). 게이트 자체의 계약은 아래 전용 테스트가 본다.
    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "1")
    monkeypatch.setattr("shared.config.OPENAI_MODEL", model, raising=False)
    monkeypatch.setattr("shared.model_catalog.model_supports_thinking",
                        lambda m: supports_thinking, raising=False)
    monkeypatch.setattr("modules.llm._get_llm_client",
                        lambda **kw: _CapturingClient(captured), raising=False)
    # PG 격리 — 상태 기록/조회를 no-op/고정으로. source="ask" 로 두어 M2 probe-throttle 우회.
    monkeypatch.setattr(lph, "record_provider_ok", lambda **kw: ok_calls.append(kw))
    monkeypatch.setattr(lph, "record_provider_restricted", lambda *a, **kw: None)
    monkeypatch.setattr(lph, "read_provider_health",
                        lambda *a, **kw: {"state": state, "source": "ask"})
    # ts=0.0(기본) = 미-probe 센티넬 → throttle 되지 않음(probe-throttle-monotonic-flake: time.monotonic()
    #   절대값 무관하게 결정적). ts>0(최근 스탬프) 을 주면 TTL 내 throttle 을 검증할 수 있다.
    lph._PROBE_STATE["ts"] = ts
    lph._PROBE_STATE["running"] = False
    lph.probe_provider(force=force)
    return captured, ok_calls


def test_probe_thinking_model_sends_valid_max_tokens_over_budget(monkeypatch):
    captured, ok_calls = _run_probe(monkeypatch, "claude-haiku-4-interactive", True)
    assert len(captured) == 1, "probe 가 LLM 호출을 정확히 1회 해야 한다"
    kw = captured[0]
    budget = kw["extra_body"]["thinking"]["budget_tokens"]
    assert budget == lph._PROBE_THINKING_BUDGET
    # 핵심 불변식: max_tokens > thinking.budget_tokens (Anthropic 제약, 400 회귀 방지)
    assert kw["max_tokens"] > budget
    # valid ping 성공 → OK 기록되어 stale 배너 해소 가능
    assert len(ok_calls) == 1


def test_probe_non_thinking_model_uses_minimal_max_tokens(monkeypatch):
    captured, ok_calls = _run_probe(monkeypatch, "edge", False)
    assert len(captured) == 1
    kw = captured[0]
    assert kw["max_tokens"] == 1          # 비-thinking(로컬 gemma 등)은 최저 비용 유지
    assert "extra_body" not in kw          # thinking override 주입 안 함
    assert len(ok_calls) == 1


def test_probe_adaptive_model_sends_effort_not_budget(monkeypatch):
    # sonnet5-upgrade H7(적대리뷰): adaptive 모델(Sonnet 5 계열=claude-sonnet-4 alias) probe 는
    # budget_tokens(400 유발) 대신 output_config.effort 를 보낸다. max_tokens 는 여유(>1)를 준다.
    captured, ok_calls = _run_probe(monkeypatch, "claude-sonnet-4", True)
    assert len(captured) == 1
    kw = captured[0]
    assert kw.get("extra_body") == {"output_config": {"effort": "low"}}
    assert "thinking" not in kw.get("extra_body", {})   # budget_tokens 절대 미주입
    assert kw["max_tokens"] > 1                          # adaptive 여유(잘림 방지)
    # cc-identity-inject: adaptive probe 는 Claude Code identity 를 첫 system 블록으로 주입(없으면 429).
    from shared.model_catalog import OAUTH_FRONTIER_IDENTITY
    assert kw["messages"][0] == {"role": "system", "content": OAUTH_FRONTIER_IDENTITY}
    assert len(ok_calls) == 1                            # valid ping 성공 → 배너 자동해소


def test_probe_budget_model_no_cc_identity(monkeypatch):
    # budget 계열(haiku)은 CC identity 미요구 → probe 도 미주입(첫 메시지 = user ping).
    from shared.model_catalog import OAUTH_FRONTIER_IDENTITY
    captured, _ = _run_probe(monkeypatch, "claude-haiku-4-interactive", True)
    kw = captured[0]
    assert kw["messages"][0].get("role") == "user"
    assert all(m.get("content") != OAUTH_FRONTIER_IDENTITY for m in kw["messages"])


# ── recovery-only gate: ok/unknown 은 실제 호출 없이 cached 반환(5h 윈도우 재고정 방지) ──

def test_probe_skips_real_call_when_state_ok(monkeypatch):
    # 비-force + state=ok → 실제 claude ping 을 하지 않는다(재고정·비용 회피).
    captured, ok_calls = _run_probe(monkeypatch, "claude-haiku-4-interactive", True,
                                    force=False, state="ok")
    assert captured == [], "ok 상태의 idle 폴링은 실제 claude 호출을 유발하면 안 된다"
    assert ok_calls == []


def test_probe_skips_real_call_when_state_unknown(monkeypatch):
    captured, _ = _run_probe(monkeypatch, "claude-haiku-4-interactive", True,
                             force=False, state="unknown")
    assert captured == [], "unknown 상태도 실제 호출 없이 cached 반환"


def test_probe_pings_when_restricted_for_recovery(monkeypatch):
    # 비-force + state=restricted → 복구 감지 위해 valid ping 발생(max_tokens>budget).
    captured, ok_calls = _run_probe(monkeypatch, "claude-haiku-4-interactive", True,
                                    force=False, state="restricted")
    assert len(captured) == 1, "restricted 상태는 복구 감지를 위해 능동 ping 해야 한다"
    assert captured[0]["max_tokens"] > captured[0]["extra_body"]["thinking"]["budget_tokens"]
    assert len(ok_calls) == 1


def test_probe_force_pings_regardless_of_ok_state(monkeypatch):
    # force(사용자 명시 재시도)는 ok 여도 gate 우회하고 즉시 실제 ping.
    captured, ok_calls = _run_probe(monkeypatch, "claude-haiku-4-interactive", True,
                                    force=True, state="ok")
    assert len(captured) == 1
    assert len(ok_calls) == 1


# ── probe-throttle-monotonic-flake: ts=0.0(미-probe 센티넬) throttle 회귀 잠금 ──
# 배경: throttle 이 `now - ts < min_gap`(now=time.monotonic()=부팅 이후 절대초)만 봤을 때, 초기 ts=0.0 이면
# monotonic()<min_gap 인 갓-부팅 워커/CI 러너에서 첫 probe 가 spurious throttle 됐다(restricted 복구 ping
# 누락 + 러너 uptime 에 따라 restricted 테스트가 flaky). 수정: last_ts>0 일 때만 throttle.

def test_probe_sentinel_ts_zero_not_throttled_regardless_of_monotonic(monkeypatch):
    # ts=0.0(미-probe 센티넬) → time.monotonic() 절대값과 무관하게 throttle 안 됨(결정적 ping).
    captured, ok_calls = _run_probe(monkeypatch, "claude-haiku-4-interactive", True,
                                    force=False, state="restricted", ts=0.0)
    assert len(captured) == 1, "ts=0.0 센티넬은 monotonic 절대값과 무관하게 throttle 되면 안 된다(flake 회귀)"
    assert len(ok_calls) == 1


def test_probe_recent_ts_within_ttl_throttles(monkeypatch):
    # 최근 실제 스탬프(ts>0, TTL 내) → skip(throttle 유지) — 센티넬 수정이 정상 throttle 을 깨지 않음.
    captured, _ = _run_probe(monkeypatch, "claude-haiku-4-interactive", True,
                             force=False, state="restricted", ts=time.monotonic())
    assert captured == [], "TTL 내 최근 probe(ts>0)는 skip(throttle)해야 한다"


# ── feature-0043 게이트: 차단 중 probe 는 ping 하지 않고 배너도 띄우지 않는다 ────
def test_probe_does_not_call_provider_while_server_llm_blocked(monkeypatch):
    """차단 중 실제 호출 0 — 어차피 분류도 못 하면서 비용·로그만 남긴다."""
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    called = []
    monkeypatch.setattr("modules.llm._get_llm_client",
                        lambda **kw: called.append(kw), raising=False)
    monkeypatch.setattr(lph, "_read_provider_health_raw",
                        lambda *a, **kw: {"state": lph.STATE_RESTRICTED, "source": "ask",
                                          "kind": lph.KIND_THROTTLED, "message": "소진"})
    lph._PROBE_STATE["ts"] = 0.0
    lph._PROBE_STATE["running"] = False
    out = lph.probe_provider(force=True)
    assert called == [], "차단 중인데 provider 를 호출했다"
    # restricted 였더라도 표면은 non-restricted 여야 한다 — 전송 경로에 영향이 없고, 복구 ping 이
    # 불가능해 그대로 두면 배너가 **영구 고착**된다.
    assert out["state"] == lph.STATE_OK
    assert out["source"] == "llm-gate"
    assert out.get("server_llm_blocked") is True


def test_raw_health_still_reports_restriction_while_blocked(monkeypatch):
    """마스킹은 표면 한정 — 원본 경로는 사실을 그대로 준다(운영 진단이 죽으면 안 된다)."""
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    assert hasattr(lph, "_read_provider_health_raw")
