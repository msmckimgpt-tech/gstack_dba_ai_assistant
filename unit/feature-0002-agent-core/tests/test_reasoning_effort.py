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


class _Completions:
    def __init__(self, sink):
        self._sink = sink

    def create(self, **kwargs):
        self._sink.append(kwargs)
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
    assert out == "FINAL"
    assert len(sink) == 1
    return sink[0]


def test_reasoning_level_injects_thinking_for_claude(monkeypatch):
    kwargs = _call(monkeypatch, "claude-haiku-4", "high")
    assert kwargs.get("extra_body") == {
        "thinking": {"type": "enabled", "budget_tokens": 10000},
    }


def test_reasoning_level_none_leaves_config_default(monkeypatch):
    kwargs = _call(monkeypatch, "claude-haiku-4", None)
    assert "extra_body" not in kwargs


def test_reasoning_level_normal_leaves_config_default(monkeypatch):
    # B1 회귀 가드(주입 레이어): '일반' 은 extra_body 를 넣지 않아 sonnet config 기본(16000)이 유지된다.
    kwargs = _call(monkeypatch, "claude-sonnet-4", "normal")
    assert "extra_body" not in kwargs


def test_reasoning_level_ignored_for_non_thinking_model(monkeypatch):
    # 로컬 LLM(gemma/edge) 은 thinking 미지원 → 주입 안 함(LiteLLM drop_params 방지 겸).
    kwargs = _call(monkeypatch, "edge", "max")
    assert "extra_body" not in kwargs


def test_invalid_reasoning_level_not_injected(monkeypatch):
    kwargs = _call(monkeypatch, "claude-haiku-4", "ultra")
    assert "extra_body" not in kwargs


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
    # 관리 콘솔에서 'high' 레벨 budget 을 12000 으로 설정 → 기본 10000 대신 주입.
    _stage_snapshot(tmp_path, monkeypatch, {"reasoning_budget:high": 12000})
    kwargs = _call(monkeypatch, "claude-haiku-4", "high")
    assert kwargs.get("extra_body") == {"thinking": {"type": "enabled", "budget_tokens": 12000}}


def test_reasoning_level_default_when_no_override(monkeypatch, tmp_path):
    # override 없으면 model_catalog 기본(high=10000) 유지.
    kwargs = _call(monkeypatch, "claude-haiku-4", "high")
    assert kwargs.get("extra_body") == {"thinking": {"type": "enabled", "budget_tokens": 10000}}


def test_normal_ignores_reasoning_override_but_model_override_applies(monkeypatch, tmp_path):
    # '일반'은 레벨 예산 대상 아님(B1) → reasoning override 무시. 대신 모델 override 가 적용된다.
    _stage_snapshot(tmp_path, monkeypatch, {
        "reasoning_budget:high": 12000,
        "model_thinking_budget:claude-sonnet-4": 9000,
    })
    kwargs = _call(monkeypatch, "claude-sonnet-4", "normal")
    assert kwargs.get("extra_body") == {"thinking": {"type": "enabled", "budget_tokens": 9000}}


# ── 3. worker 경로 패리티 (_payload_to_kwargs) ───────────────────────────────

def test_worker_payload_forwards_reasoning_level():
    from modules.ask import _payload_to_kwargs

    payload = {"user_message": "hi", "model": "claude-haiku-4", "reasoning_level": "high"}
    kwargs = _payload_to_kwargs(payload, account_id=7, run_id="run-1")
    assert kwargs["reasoning_level"] == "high"
    # 누락 payload 는 None(= run_agent 기본값 → override 없음).
    kwargs2 = _payload_to_kwargs({"user_message": "x"}, account_id=7, run_id="r")
    assert kwargs2["reasoning_level"] is None
