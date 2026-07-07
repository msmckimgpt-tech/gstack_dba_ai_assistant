"""회귀 방지 — 대화 답변(task='agent')은 edge-free alias 로만 litellm 에 나간다.

FR-edge-fallback-conversation-context-loss (2026-07-07, conversation_audit):
사용자 대면 assistant 답변이 두 claude 계정 완전 장애 시 edge-fallback(gemma4:e2b,
ctx 4096)으로 silent 강등돼 ~30K 토큰 대화 히스토리가 잘리고 맥락이 파괴됐다
(실측 conv …9e0883bb). 봉인: _call_llm 이 litellm 에 보내는 model 을 edge-free
대화 전용 alias(claude-haiku-4-chat)로 치환한다. litellm_config.yaml 에서 -chat
체인은 edge 를 포함하지 않으므로 두 계정 실패 시 429/401 을 raise → 깨끗이 실패.

본 테스트가 고정하는 계약:
- G1  conversation_answer_model: claude-haiku-4 → claude-haiku-4-chat 치환.
- G2  claude-sonnet-4 등 매핑 밖 model 은 identity(무회귀; sonnet 은 애초에 edge
      폴백이 없다).
- G3  _call_llm 이 litellm(create)에 보내는 'model' kwarg 는 치환된 -chat alias.
- G4  단, _record_llm_usage 로는 **원본** model(claude-haiku-4)을 기록한다(표시/집계
      정합 유지; 실제 서빙 모델은 resolved_model 로 추적).

`make test`(agent 이미지)에서 DB 없이 monkeypatch 로 실행된다.
"""

from __future__ import annotations

import os

import pytest

import agent_core
from shared.model_catalog import API_DEFAULT_MODEL, conversation_answer_model


class _Usage:
    prompt_tokens = 1
    completion_tokens = 1
    total_tokens = 2


class _Choice:
    message = "FINAL_MESSAGE"


class _Resp:
    def __init__(self):
        self.choices = [_Choice()]
        self.usage = _Usage()
        self.model = "claude-haiku-4-5"


class _CaptureCompletions:
    def __init__(self, sink):
        self._sink = sink

    def create(self, **kwargs):
        self._sink["model"] = kwargs.get("model")
        return _Resp()


class _CaptureClient:
    def __init__(self, sink):
        self.chat = type("Chat", (), {"completions": _CaptureCompletions(sink)})()


# ── G1 / G2: 순수 헬퍼 ─────────────────────────────────────────────────────
def test_conversation_answer_model_maps_haiku_to_chat():
    assert conversation_answer_model("claude-haiku-4") == "claude-haiku-4-chat"


def test_conversation_answer_model_identity_for_unmapped():
    # sonnet 은 litellm fallbacks 목록에 없어 edge 강등이 없다 → 치환 불필요.
    assert conversation_answer_model("claude-sonnet-4") == "claude-sonnet-4"
    # 로컬/기타 모델·공백도 identity(무회귀).
    assert conversation_answer_model("edge") == "edge"
    assert conversation_answer_model("") == ""
    assert conversation_answer_model(None) == ""


def _patch_side_effects(monkeypatch, recorded):
    monkeypatch.setattr(
        agent_core, "_record_llm_usage",
        lambda model, task, resp, conversation_id=None, run_id=None, latency_ms=None,
        target=None, step_gap_ms=None: recorded.append((model, task)),
    )
    monkeypatch.setattr(agent_core, "_load_attachment_inline_images", lambda: None)
    monkeypatch.setattr(agent_core, "messages_for_provider", lambda messages, **kw: messages)
    monkeypatch.setattr(agent_core, "model_supports_vision", lambda m: False)
    monkeypatch.setattr(agent_core, "max_tokens_for_model", lambda m, t: None)
    monkeypatch.setattr(agent_core, "model_supports_thinking", lambda m: False)


# ── G3 / G4: _call_llm 이 litellm 에 보내는 model vs 기록하는 model ─────────────
def test_call_llm_routes_haiku_to_edge_free_chat_alias(monkeypatch):
    sink: dict = {}
    recorded: list = []
    _patch_side_effects(monkeypatch, recorded)

    out = agent_core._call_llm(
        _CaptureClient(sink), [{"role": "user", "content": "hi"}], "claude-haiku-4",
        conversation_id="conv-X", run_id="run-X",
    )

    assert out == "FINAL_MESSAGE"
    # G3: litellm 에는 edge-free 대화 alias 가 나간다(gemma 폴백 원천 차단).
    assert sink["model"] == "claude-haiku-4-chat"
    # G4: 기록/표시 model 은 원본 유지(집계 정합).
    assert recorded == [("claude-haiku-4", "agent")]


def test_call_llm_leaves_sonnet_unchanged(monkeypatch):
    sink: dict = {}
    recorded: list = []
    _patch_side_effects(monkeypatch, recorded)

    agent_core._call_llm(
        _CaptureClient(sink), [{"role": "user", "content": "hi"}], "claude-sonnet-4",
    )

    # sonnet 은 매핑 밖 → litellm·기록 모두 원본.
    assert sink["model"] == "claude-sonnet-4"
    assert recorded == [("claude-sonnet-4", "agent")]


# ── G5: 잠재 취약성 봉인 (적대 패널 NIT — 두 리뷰어 독립 지적) ────────────────────────
# 봉인이 리터럴 "claude-haiku-4" 문자열 매핑에 의존하므로, 나중에 대화 기본 모델
# (API_DEFAULT_MODEL)이 다른 edge-fallback alias 로 바뀌면 edge-free 보장이 조용히
# 깨질 수 있다. 진짜 불변식 — "대화 기본 모델의 litellm 아웃바운드 체인에 로컬/edge
# (gemma) 모델이 도달 불가" — 을 litellm_config.yaml 을 실제 파싱해 고정한다. 이 테스트가
# 깨지면(기본 모델 변경·-chat 체인에 edge 추가·새 alias 도입 등) 반드시 재검토해야 한다.
_LITELLM_CFG = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..",
    "feature-0007-bedrock-llm-provider", "src", "config", "litellm_config.yaml",
))


def _reachable_aliases(fallbacks_map: dict[str, list[str]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(fallbacks_map.get(cur, []))
    return seen


def test_default_conversation_model_chain_is_edge_free():
    yaml = pytest.importorskip("yaml")  # yaml 부재 환경에서는 skip(정본 make test 에는 존재)
    with open(_LITELLM_CFG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    # alias → 실제 라우팅 model 문자열.
    model_of = {
        m["model_name"]: str(m.get("litellm_params", {}).get("model", ""))
        for m in cfg["model_list"]
    }
    # alias → 폴백 리스트 (litellm_settings.fallbacks = 단일키 dict 의 리스트).
    fb_map: dict[str, list[str]] = {}
    for entry in cfg.get("litellm_settings", {}).get("fallbacks", []):
        for k, v in entry.items():
            fb_map[k] = list(v)

    # 대화 답변이 실제로 litellm 에 보내는 아웃바운드 alias.
    outbound = conversation_answer_model(API_DEFAULT_MODEL)
    assert outbound in model_of, (
        f"대화 아웃바운드 alias '{outbound}'(API_DEFAULT_MODEL={API_DEFAULT_MODEL})가 "
        f"litellm model_list 에 없음 — 라우팅 불가"
    )

    reachable = _reachable_aliases(fb_map, outbound)
    # 도달 가능한 모든 alias 의 실 model 은 anthropic/* 여야 한다(로컬/edge/gemma 도달 금지).
    offenders = {
        a: model_of.get(a, "<unknown>")
        for a in reachable
        if not model_of.get(a, "").startswith("anthropic/")
    }
    assert not offenders, (
        f"대화 답변 폴백 체인(from '{outbound}')에서 비-anthropic(로컬/edge/gemma) 모델 도달: "
        f"{offenders}. 대화 답변은 edge 로 강등돼선 안 된다(FR-edge-fallback-conversation-context-loss). "
        f"기본 모델 변경/체인 수정 시 반드시 재검토."
    )
    # 명시적으로 gemma/edge alias 자체가 도달 불가임을 재확인.
    assert "edge-fallback" not in reachable
