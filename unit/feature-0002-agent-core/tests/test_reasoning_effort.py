"""사용자 지정 추론 강도(reasoning-effort) unit test — feature-0003 reasoning-effort-selector.

대화 화면에서 고른 추론 강도(low/normal/high/max)가:
  1) model_catalog 매핑/정규화 규칙대로 budget_tokens 로 해석되고,
  2) thinking 지원 모델(claude-*)일 때만 _call_llm 이 요청 단위 extra_body.thinking 로 주입하며,
  3) 미지정/미지원 모델이면 주입하지 않고(config 기본값 유지),
  4) Anthropic 제약(1024 ≤ budget < agent max_tokens)을 모든 레벨이 만족하고,
  5) worker 경로(_payload_to_kwargs)도 reasoning_level 을 동등 전달함(inproc 패리티)
을 회귀 방지로 고정한다.
"""

from __future__ import annotations

import pytest

import agent_core
from shared import runtime_settings as _rs
from shared.model_catalog import (
    DEFAULT_REASONING_LEVEL,
    REASONING_LEVELS,
    _REASONING_BUDGETS,
    max_tokens_for_model,
    model_supports_thinking,
    normalize_reasoning_level,
    thinking_budget_for_level,
)


# ── 1. model_catalog 매핑/정규화 ──────────────────────────────────────────────

def test_reasoning_levels_are_four_ordered_tiers():
    # 선택 가능 레벨 4개(낮음→매우 높음 순서). REASONING_LEVELS 는 유효 키 튜플.
    assert REASONING_LEVELS == ("low", "normal", "high", "max")
    assert DEFAULT_REASONING_LEVEL == "normal" and DEFAULT_REASONING_LEVEL in REASONING_LEVELS


def test_normalize_reasoning_level():
    assert normalize_reasoning_level("high") == "high"
    assert normalize_reasoning_level("  MAX ") == "max"
    assert normalize_reasoning_level("normal") == "normal"
    assert normalize_reasoning_level("bogus") is None
    assert normalize_reasoning_level("") is None
    assert normalize_reasoning_level(None) is None


def test_thinking_budget_for_level():
    # 명시 레벨만 budget. 'normal'/미지정/미상 → None(override 안 함 = 모델 config 기본).
    assert thinking_budget_for_level("low") == 2000
    assert thinking_budget_for_level("high") == 10000
    assert thinking_budget_for_level("max") == 16000
    assert thinking_budget_for_level("normal") is None
    assert thinking_budget_for_level(None) is None
    assert thinking_budget_for_level("nope") is None


def test_normal_is_no_override_b1_regression_guard():
    # B1(적대검증 BLOCKING): '일반'이 고정 budget 을 주입하면 선택기 미상호작용 sonnet 이
    # config 기본 16000 → 5000 으로 조용히 강등된다. '일반'은 반드시 no-override(None) 여야 한다.
    assert "normal" not in _REASONING_BUDGETS
    assert thinking_budget_for_level("normal") is None


def test_model_supports_thinking():
    assert model_supports_thinking("claude-haiku-4") is True
    assert model_supports_thinking("claude-sonnet-4") is True
    assert model_supports_thinking("edge") is False
    assert model_supports_thinking("gemma4:e2b") is False
    assert model_supports_thinking(None) is False


def test_all_budgets_respect_anthropic_constraints():
    # override budget < max_tokens (agent 경로) 且 budget >= 1024 (Anthropic 하한).
    cap = max_tokens_for_model("claude-haiku-4", "agent")
    assert cap is not None
    assert _REASONING_BUDGETS  # 비어있지 않음
    for level, budget in _REASONING_BUDGETS.items():
        assert budget >= 1024, f"{level} budget {budget} < Anthropic min 1024"
        assert budget < cap, f"{level} budget {budget} must be < agent max_tokens {cap}"


# ── 2. _call_llm 요청 단위 thinking 주입 ─────────────────────────────────────

class _Usage:
    prompt_tokens = 1
    completion_tokens = 1
    total_tokens = 2


class _Choice:
    message = "FINAL"


class _Resp:
    def __init__(self):
        self.choices = [_Choice()]
        self.usage = _Usage()
        self.model = "m"


# conv-audit FR-llm-attempt-cap-inside-latency-tail: 대화 경로는 stream=True 로 나간다.
# 더블은 두 모드를 다 지원한다(스트리밍 기본 + 킬 스위치 off 종전 경로).
def _final_stream():
    yield type("C", (), {
        "choices": [type("Ch", (), {
            "delta": type("D", (), {"content": "FINAL", "tool_calls": None,
                                    "reasoning_content": None})(),
            "finish_reason": "stop",
        })()],
        "usage": None, "model": "m",
    })()
    yield type("C", (), {"choices": [], "usage": _Usage(), "model": "m"})()


class _Completions:
    def __init__(self, sink):
        self._sink = sink

    def create(self, **kwargs):
        self._sink.append(kwargs)
        if kwargs.get("stream"):
            return _final_stream()
        return _Resp()


class _Client:
    def __init__(self, sink):
        self.chat = type("Chat", (), {"completions": _Completions(sink)})()


def _patch_common(monkeypatch):
    monkeypatch.setattr(agent_core, "_record_llm_usage", lambda *a, **k: None)
    monkeypatch.setattr(agent_core, "_load_attachment_inline_images", lambda: None)
    monkeypatch.setattr(agent_core, "messages_for_provider", lambda messages, **kw: messages)
    monkeypatch.setattr(agent_core, "model_supports_vision", lambda m: False)
    # max_tokens 는 실제 매핑을 그대로 사용(제약 검증과 정합).


def _call(monkeypatch, model, reasoning_level):
    _patch_common(monkeypatch)
    sink: list[dict] = []
    out = agent_core._call_llm(
        _Client(sink), [{"role": "user", "content": "hi"}], model,
        reasoning_level=reasoning_level,
    )
    # conv-audit: 스트리밍 경로의 반환은 누적된 message-like 다(계약: `.content`).
    assert out.content == "FINAL"
    assert len(sink) == 1
    kw = sink[0]
    # conv-audit FR-body-timeout-poisons-provider-request(2026-08-26): **body timeout 금지**.
    # 종전 계약(feature-0007 timeout-console-sync)은 `extra_body["timeout"]` 로 콘솔 값을 요청
    # 본문에 실었다. 구 게이트웨이는 이를 무시해 무해했으나, litellm 1.98.0 은 요청에 timeout 이
    # 있으면 내부 마커 `client_side_timeout` 을 심고 그것이 Anthropic body 로 새어 **400**
    # (`Extra inputs are not permitted`)을 만든다 — 1차·폴백 동일 body 라 대화가 전면 실패했다
    # (라이브 실측 2026-08-26). 그래서 단언을 뒤집는다: 본문에 timeout 이 **없어야** 한다.
    # per-attempt 상한의 실효는 request option(`_stream_kwargs["timeout"]`, 본문 아님)이 유지한다.
    assert "timeout" not in (kw.get("extra_body") or {}), (
        f"요청 본문에 timeout 이 실렸다 — 게이트웨이가 client_side_timeout 마커를 심어 "
        f"provider 400 을 유발한다: {kw.get('extra_body')}"
    )
    return kw


def _xb(kwargs):
    """extra_body 의 thinking/effort 부분(= 전체). timeout 은 더 이상 실리지 않는다.

    종전에는 항상-주입되던 timeout 을 걷어내는 헬퍼였다. 계약이 "본문 timeout 금지" 로 바뀐 뒤에도
    호출부를 그대로 두기 위해 형태만 유지한다(방어적 pop — 회귀 시 위 단언이 먼저 잡는다)."""
    eb = dict(kwargs.get("extra_body") or {})
    eb.pop("timeout", None)
    return eb


def test_reasoning_level_injects_thinking_for_claude(monkeypatch):
    kwargs = _call(monkeypatch, "claude-haiku-4", "high")
    assert _xb(kwargs) == {
        "thinking": {"type": "enabled", "budget_tokens": 10000},
    }


def test_reasoning_level_none_leaves_config_default(monkeypatch):
    # thinking/effort 미주입(config 기본 유지). timeout 은 별도로 항상 주입되므로 _xb 로 분리 검증.
    kwargs = _call(monkeypatch, "claude-haiku-4", None)
    assert _xb(kwargs) == {}


def test_reasoning_level_normal_leaves_config_default(monkeypatch):
    # B1 회귀 가드(주입 레이어): '일반' 은 thinking/effort 를 넣지 않아 sonnet config 기본(16000)이 유지된다.
    kwargs = _call(monkeypatch, "claude-sonnet-4", "normal")
    assert _xb(kwargs) == {}


def test_reasoning_level_ignored_for_non_thinking_model(monkeypatch):
    # 로컬 LLM(gemma/edge) 은 thinking 미지원 → thinking/effort 주입 안 함(LiteLLM drop_params 방지 겸).
    kwargs = _call(monkeypatch, "edge", "max")
    assert _xb(kwargs) == {}


def test_invalid_reasoning_level_not_injected(monkeypatch):
    kwargs = _call(monkeypatch, "claude-haiku-4", "ultra")
    assert _xb(kwargs) == {}


# ── 2c. sonnet5-upgrade: adaptive thinking(Sonnet 5) — budget_tokens 대신 output_config.effort ──
def test_model_thinking_style():
    from shared.model_catalog import model_thinking_style
    # claude-sonnet-4 alias 는 실제로 Sonnet 5 를 서빙 → adaptive.
    assert model_thinking_style("claude-sonnet-4") == "adaptive"
    assert model_thinking_style("claude-sonnet-5") == "adaptive"
    assert model_thinking_style("claude-sonnet-4-chat") == "adaptive"
    assert model_thinking_style("claude-haiku-4") == "budget"       # Haiku 4.5 = pre-Sonnet-5
    assert model_thinking_style("claude-haiku-4-chat") == "budget"
    assert model_thinking_style("edge") is None
    assert model_thinking_style(None) is None
    # opus5-model(2026-07-27): Opus 계열은 전부 adaptive-only(budget_tokens 400) → `claude-opus` prefix.
    # 요청 alias·라우팅 변형·실 모델 ID·미등재 Opus 버전이 모두 같은 스타일로 분류돼야 한다.
    assert model_thinking_style("claude-opus-5") == "adaptive"
    assert model_thinking_style("claude-opus-5-chat") == "adaptive"
    assert model_thinking_style("claude-opus-5-chat-root") == "adaptive"
    # 이전에는 미상 claude 로 None 이었으나(H2 보수 분류), Opus 4.8 도 budget_tokens 를 400 으로
    # 거부하는 adaptive-only 라 prefix 분류가 사실에 더 부합한다(claude-api 스펙).
    assert model_thinking_style("claude-opus-4-8") == "adaptive"
    # H2(적대리뷰) 보수 기본값은 유지 — opus/sonnet prefix 밖 미상 claude 는 여전히 None(무주입).
    assert model_thinking_style("claude-sonnet-6") is None


def test_effort_for_reasoning_level():
    from shared.model_catalog import effort_for_reasoning_level
    assert effort_for_reasoning_level("low") == "low"
    assert effort_for_reasoning_level("high") == "high"
    assert effort_for_reasoning_level("max") == "max"
    assert effort_for_reasoning_level("normal") is None   # 기본 high 유지(무override)
    assert effort_for_reasoning_level(None) is None
    assert effort_for_reasoning_level("nope") is None


def test_sonnet_adaptive_injects_effort_not_budget(monkeypatch):
    # Sonnet 5: 명시 레벨 → output_config.effort. budget_tokens 는 400 이므로 절대 주입 금지.
    for level, effort in (("low", "low"), ("high", "high"), ("max", "max")):
        kwargs = _call(monkeypatch, "claude-sonnet-4", level)
        assert _xb(kwargs) == {"output_config": {"effort": effort}}, level
        assert "thinking" not in kwargs.get("extra_body", {}), level


def test_sonnet_adaptive_normal_no_override(monkeypatch):
    # '일반'/미지정 → effort 미주입(config adaptive 기본 high 유지). budget_tokens 절대 미주입.
    for level in ("normal", None):
        kwargs = _call(monkeypatch, "claude-sonnet-4", level)
        assert _xb(kwargs) == {}, level


# ── 2c-opus. opus5-model: Opus 5 도 adaptive — effort 만, budget_tokens 는 절대 미주입 ──────
def test_opus_adaptive_injects_effort_not_budget(monkeypatch):
    for level, effort in (("low", "low"), ("high", "high"), ("max", "max")):
        kwargs = _call(monkeypatch, "claude-opus-5", level)
        assert _xb(kwargs) == {"output_config": {"effort": effort}}, level
        assert "thinking" not in kwargs.get("extra_body", {}), level


def test_opus_adaptive_normal_no_override(monkeypatch):
    for level in ("normal", None):
        kwargs = _call(monkeypatch, "claude-opus-5", level)
        assert _xb(kwargs) == {}, level


def test_opus_prepends_cc_identity_system(monkeypatch):
    # opus(adaptive)도 CC identity 를 첫 **별도 system 메시지**로 주입해야 429(identity 게이트) 회피.
    from shared.model_catalog import OAUTH_FRONTIER_IDENTITY
    kwargs = _call(monkeypatch, "claude-opus-5", "normal")
    msgs = kwargs["messages"]
    assert msgs[0] == {"role": "system", "content": OAUTH_FRONTIER_IDENTITY}
    assert msgs[1] == {"role": "user", "content": "hi"}   # 원 메시지 보존, CC 는 앞에만


# ── 2d. cc-identity-inject: OAuth frontier(Sonnet 5) 는 Claude Code identity 첫 system 블록 요구 ──
def test_requires_oauth_frontier_identity():
    from shared.model_catalog import requires_oauth_frontier_identity as R, OAUTH_FRONTIER_IDENTITY
    assert R("claude-sonnet-4") is True           # Sonnet 5 서빙 alias
    assert R("claude-sonnet-4-chat") is True
    assert R("claude-sonnet-5") is True
    # opus5-model(2026-07-27) 라이브 실증: Opus 5 도 CC identity 없으면 429 → 요구 True.
    assert R("claude-opus-5") is True
    assert R("claude-opus-5-chat") is True
    assert R("claude-opus-5-chat-root") is True
    assert R("claude-haiku-4") is False           # budget 계열은 미요구
    assert R("edge") is False
    assert R(None) is False
    assert OAUTH_FRONTIER_IDENTITY.startswith("You are Claude Code")


def test_sonnet_prepends_cc_identity_system(monkeypatch):
    # sonnet(adaptive)은 effective_messages 첫 블록에 Claude Code identity system 을 주입해야 429 회피.
    from shared.model_catalog import OAUTH_FRONTIER_IDENTITY
    kwargs = _call(monkeypatch, "claude-sonnet-4", "normal")
    msgs = kwargs["messages"]
    assert msgs[0] == {"role": "system", "content": OAUTH_FRONTIER_IDENTITY}
    assert msgs[1] == {"role": "user", "content": "hi"}   # 원 메시지 보존, CC 는 앞에만


def test_haiku_no_cc_identity_injection(monkeypatch):
    # budget 계열(haiku)은 identity 미요구 → 미주입(working 경로 무영향).
    from shared.model_catalog import OAUTH_FRONTIER_IDENTITY
    kwargs = _call(monkeypatch, "claude-haiku-4", "normal")
    assert kwargs["messages"][0] == {"role": "user", "content": "hi"}
    assert all(m.get("content") != OAUTH_FRONTIER_IDENTITY for m in kwargs["messages"])


# ── 2b. feature-0018 reasoning-budgets: 관리 콘솔 override precedence ─────────
@pytest.fixture(autouse=True)
def _reset_runtime_settings(monkeypatch, tmp_path):
    """각 테스트를 override 없는 상태로 격리(스냅샷 부재 + 캐시 리셋). override 테스트는
    _rs.write_snapshot 으로 명시 설정."""
    monkeypatch.setenv("RUNTIME_SETTINGS_SNAPSHOT_PATH", str(tmp_path / "none.json"))
    monkeypatch.delenv("RUNTIME_SETTINGS_DISABLED", raising=False)
    _rs.invalidate_cache(); _rs._cache["frozen"] = None
    yield
    _rs.invalidate_cache(); _rs._cache["frozen"] = None


def _stage_snapshot(tmp_path, monkeypatch, overrides):
    p = tmp_path / "rs.json"
    monkeypatch.setenv("RUNTIME_SETTINGS_SNAPSHOT_PATH", str(p))
    _rs.invalidate_cache(); _rs._cache["frozen"] = None
    _rs.write_snapshot(overrides)


def test_reasoning_level_admin_override_beats_default(monkeypatch, tmp_path):
    # 관리 콘솔에서 (haiku,high) 레벨 budget 을 12000 으로 설정 → 기본 10000 대신 주입.
    _stage_snapshot(tmp_path, monkeypatch, {"reasoning_budget:claude-haiku-4:high": 12000})
    kwargs = _call(monkeypatch, "claude-haiku-4", "high")
    assert _xb(kwargs) == {"thinking": {"type": "enabled", "budget_tokens": 12000}}


def test_reasoning_level_default_when_no_override(monkeypatch, tmp_path):
    # override 없으면 model_catalog 기본(high=10000) 유지.
    kwargs = _call(monkeypatch, "claude-haiku-4", "high")
    assert _xb(kwargs) == {"thinking": {"type": "enabled", "budget_tokens": 10000}}


def test_normal_ignores_reasoning_override_but_model_override_applies(monkeypatch, tmp_path):
    # '일반'은 레벨 예산 대상 아님(B1) → reasoning override 무시. 대신 모델 override 가 적용된다(budget 계열=haiku).
    # (sonnet 은 sonnet5-upgrade 이후 adaptive 라 budget override 자체가 대상 아님 — 아래 별도 테스트.)
    _stage_snapshot(tmp_path, monkeypatch, {
        "reasoning_budget:claude-haiku-4:high": 12000,
        "model_thinking_budget:claude-haiku-4": 9000,
    })
    kwargs = _call(monkeypatch, "claude-haiku-4", "normal")
    assert _xb(kwargs) == {"thinking": {"type": "enabled", "budget_tokens": 9000}}


def test_reasoning_and_total_are_per_model(monkeypatch, tmp_path):
    # per-model 분리 + dual thinking style(sonnet5-upgrade): sonnet(adaptive)은 output_config.effort +
    # 자기 총출력, haiku(budget)는 budget_tokens + 자기 총출력. 서로의 override 가 섞이지 않는다.
    _stage_snapshot(tmp_path, monkeypatch, {
        "agent_max_output:claude-sonnet-4": 100000,
        "reasoning_budget:claude-sonnet-4:max": 60000,  # adaptive sonnet 에선 무시(budget 미사용)
    })
    ks = _call(monkeypatch, "claude-sonnet-4", "max")
    assert ks["max_tokens"] == 100000  # 총 출력 override 는 adaptive 에도 적용
    assert _xb(ks) == {"output_config": {"effort": "max"}}  # budget 아닌 effort
    kh = _call(monkeypatch, "claude-haiku-4", "max")
    assert kh["max_tokens"] == 24000  # haiku 기본 총 출력(override 무관)
    assert kh["extra_body"]["thinking"]["budget_tokens"] == 16000  # haiku 기본 max 예산


def test_budget_clamped_to_total_minus_headroom(monkeypatch, tmp_path):
    # 총 출력을 낮추면 thinking budget 이 총−1024 로 clamp 되어 본문 여유(≥1024)가 보장된다.
    _stage_snapshot(tmp_path, monkeypatch, {
        "agent_max_output:claude-haiku-4": 8000,
        "reasoning_budget:claude-haiku-4:max": 16000,  # 총(8000)보다 큼
    })
    k = _call(monkeypatch, "claude-haiku-4", "max")
    assert k["max_tokens"] == 8000
    assert k["extra_body"]["thinking"]["budget_tokens"] == 8000 - 1024  # clamp


# ── 2e. feature-0007 timeout-console-sync: body timeout 이 콘솔 AGENT_TIMEOUT_SEC(live)를 추종 ──

def test_console_timeout_reaches_request_option_not_body(monkeypatch, tmp_path):
    """콘솔 타임아웃은 **request option** 으로만 전달된다 — 요청 **본문**에는 절대 싣지 않는다.

    conv-audit FR-body-timeout-poisons-provider-request(2026-08-26): 종전에는 같은 값을
    `extra_body["timeout"]`(= 요청 본문)에도 실었다. litellm 1.98.0 은 요청에 timeout 이 있으면
    내부 마커 `client_side_timeout` 을 심고 그것이 Anthropic body 로 새어 400 을 만든다
    (라이브 실측: 대화 전면 실패). 실효 per-attempt 상한은 request option 이 그대로 유지하므로,
    이 테스트가 잠그는 것은 **"상한은 살아 있되 본문은 오염되지 않는다"** 는 두 축이다.
    """
    _stage_snapshot(tmp_path, monkeypatch, {"AGENT_TIMEOUT_SEC": 450})
    kwargs = _call(monkeypatch, "claude-sonnet-4", "normal")
    # (1) 본문 무오염 — _call 안의 단언이 1차 방어, 여기서 명시적으로 한 번 더.
    assert "timeout" not in kwargs["extra_body"]
    assert _xb(kwargs) == {}  # '일반' sonnet 은 thinking/effort override 없음(B1 무회귀)
    # (2) 실효 상한 보존 — 콘솔 값이 per-request 클라이언트 timeout 으로 도달한다.
    assert kwargs["timeout"] == 450, "콘솔 타임아웃이 request option 으로 전달되지 않았다"
    # budget 계열(haiku)도 동일: 본문에는 thinking 만, timeout 은 request option.
    kh = _call(monkeypatch, "claude-haiku-4", "high")
    assert "timeout" not in kh["extra_body"]
    assert kh["timeout"] == 450
    assert kh["extra_body"]["thinking"]["budget_tokens"] == 10000


def test_request_option_timeout_default_when_no_console_override(monkeypatch):
    # override 없으면 runtime_settings 기본값(>=5)이 request option 으로 전달된다.
    kwargs = _call(monkeypatch, "claude-sonnet-4", "normal")
    assert "timeout" not in kwargs["extra_body"]
    assert isinstance(kwargs["timeout"], int) and kwargs["timeout"] >= 5


# ── 3. worker 경로 패리티 (_payload_to_kwargs) ───────────────────────────────

def test_worker_payload_forwards_reasoning_level():
    from modules.ask import _payload_to_kwargs

    payload = {"user_message": "hi", "model": "claude-haiku-4", "reasoning_level": "high"}
    kwargs = _payload_to_kwargs(payload, account_id=7, run_id="run-1")
    assert kwargs["reasoning_level"] == "high"
    # 누락 payload 는 None(= run_agent 기본값 → override 없음).
    kwargs2 = _payload_to_kwargs({"user_message": "x"}, account_id=7, run_id="r")
    assert kwargs2["reasoning_level"] is None
