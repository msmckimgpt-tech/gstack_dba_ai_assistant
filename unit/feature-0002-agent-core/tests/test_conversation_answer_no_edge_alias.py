"""회귀 방지 — 대화 답변(task='agent')은 edge-free alias 로만 litellm 에 나간다.

FR-edge-fallback-conversation-context-loss (2026-07-07, conversation_audit):
사용자 대면 assistant 답변이 두 claude 계정 완전 장애 시 edge-fallback(gemma4:e2b,
ctx 4096)으로 silent 강등돼 ~30K 토큰 대화 히스토리가 잘리고 맥락이 파괴됐다
(실측 conv …9e0883bb). 봉인: _call_llm 이 litellm 에 보내는 model 을 edge-free
대화 전용 alias(claude-haiku-4-chat)로 치환한다. litellm_config.yaml 에서 -chat
체인은 edge 를 포함하지 않으므로 두 계정 실패 시 429/401 을 raise → 깨끗이 실패.

본 테스트가 고정하는 계약:
- G1  conversation_answer_model: claude-haiku-4 → claude-haiku-4-chat 치환.
- G2  conversation_answer_model: claude-sonnet-4 → claude-sonnet-4-chat 치환
      (sonnet-chat-fallback 2026-07-24). 미매핑 claude alias 는 identity(무회귀).
- G3  _call_llm 이 litellm(create)에 보내는 'model' kwarg 는 치환된 -chat alias.
- G4  단, _record_llm_usage 로는 **원본** model(claude-haiku-4 / claude-sonnet-4)을 기록한다
      (표시/집계 정합 유지; 실제 서빙 모델은 resolved_model 로 추적).

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
        # 전체 kwargs 캡처(model + max_tokens + extra_body) — 기존 소비자는 sink["model"]만 읽어 무회귀.
        self._sink["model"] = kwargs.get("model")
        self._sink["max_tokens"] = kwargs.get("max_tokens")
        self._sink["extra_body"] = kwargs.get("extra_body")
        return _Resp()


class _CaptureClient:
    def __init__(self, sink):
        self.chat = type("Chat", (), {"completions": _CaptureCompletions(sink)})()


# ── G1 / G2: 순수 헬퍼 ─────────────────────────────────────────────────────
def test_conversation_answer_model_maps_haiku_to_chat():
    assert conversation_answer_model("claude-haiku-4") == "claude-haiku-4-chat"


def test_conversation_answer_model_maps_sonnet_to_chat():
    # sonnet-chat-fallback(2026-07-24): sonnet 도 edge-free 대화 chat alias 로 치환된다.
    # bare claude-sonnet-4 는 root fallback 이 없어 claude-corp 429 시 즉시 실패했다 → -chat 2계정 체인.
    assert conversation_answer_model("claude-sonnet-4") == "claude-sonnet-4-chat"


def test_conversation_answer_model_identity_for_unmapped_claude():
    # 매핑 밖 claude alias 는 identity(무회귀).
    assert conversation_answer_model("claude-opus-4") == "claude-opus-4"
    # 이미 해소된 chat alias 는 멱등.
    assert conversation_answer_model("claude-haiku-4-chat") == "claude-haiku-4-chat"
    assert conversation_answer_model("claude-sonnet-4-chat") == "claude-sonnet-4-chat"
    # 공백/None 은 identity(호출측이 상위에서 기본 모델로 해소; 여기서 변형하지 않음).
    assert conversation_answer_model("") == ""
    assert conversation_answer_model(None) == ""


# ── G2b: alias 누출 가드 (TASK-alias-leak-guard) ───────────────────────────────
# 대화 답변 경로는 고정 Bedrock 클라이언트로 나가므로(FR-edge-fallback: gemma tier-resolve 금지),
# 로컬 게이트웨이 alias(auto/edge/core/code)·미등록 bare 'claude' 가 identity 로 통과하면 Bedrock
# 프록시가 "Invalid model name passed in model=..." 400 을 낸다(실측 다수 대화). 이들을 대화 기본
# chat(claude-haiku-4-chat)로 해소해 raw alias 가 Bedrock 으로 새지 않게 봉인.
@pytest.mark.parametrize("alias", ["auto", "edge", "core", "code", "claude", "CLAUDE", " Edge "])
def test_conversation_answer_model_resolves_leaking_aliases(alias):
    out = conversation_answer_model(alias)
    assert out == "claude-haiku-4-chat", f"{alias!r} 는 Bedrock 400 유발 alias — 기본 chat 로 해소돼야 함"
    # 원본 raw alias 가 그대로 반환되면 안 된다(누출 방지 핵심).
    assert out.strip().lower() not in {"auto", "edge", "core", "code", "claude"}


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


def test_call_llm_routes_sonnet_to_edge_free_chat_alias(monkeypatch):
    sink: dict = {}
    recorded: list = []
    _patch_side_effects(monkeypatch, recorded)

    agent_core._call_llm(
        _CaptureClient(sink), [{"role": "user", "content": "hi"}], "claude-sonnet-4",
    )

    # sonnet-chat-fallback(2026-07-24): litellm 에는 edge-free 2계정 chat alias 가 나간다.
    assert sink["model"] == "claude-sonnet-4-chat"
    # 기록/표시 model 은 원본 유지(집계 정합).
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


# ── G5b: sonnet 대화 체인도 라우팅 가능 + edge-free + 2계정 fallback 보유 (sonnet-chat-fallback) ──
# 증상 봉인: 새 대화 sonnet 선택이 "서비스 자체의 요청량 한도"로 실패한 근본 원인은 bare claude-sonnet-4
# 가 root fallback 없는 단일 계정이라 claude-corp 429 시 즉시 raise 된 것. 이 테스트는 sonnet 대화
# 아웃바운드(claude-sonnet-4-chat)가 (1) litellm 에 등록돼 라우팅 가능하고, (2) 두 번째 계정(-chat-root)
# 으로 fallback 되며, (3) 그 체인이 edge(gemma)에 도달하지 않음을 고정한다. 셋 중 하나라도 깨지면 회귀.
def test_sonnet_conversation_chain_has_two_accounts_and_is_edge_free():
    yaml = pytest.importorskip("yaml")
    with open(_LITELLM_CFG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    model_of = {
        m["model_name"]: str(m.get("litellm_params", {}).get("model", ""))
        for m in cfg["model_list"]
    }
    api_key_of = {
        m["model_name"]: str(m.get("litellm_params", {}).get("api_key", ""))
        for m in cfg["model_list"]
    }
    fb_map: dict[str, list[str]] = {}
    for entry in cfg.get("litellm_settings", {}).get("fallbacks", []):
        for k, v in entry.items():
            fb_map[k] = list(v)

    outbound = conversation_answer_model("claude-sonnet-4")
    assert outbound == "claude-sonnet-4-chat"
    assert outbound in model_of, f"sonnet 대화 아웃바운드 '{outbound}' 가 litellm 에 미등록 — 라우팅 불가"

    reachable = _reachable_aliases(fb_map, outbound)
    # (2) 두 번째 계정으로 fallback — root 계정 alias 가 도달 가능해야 한다(단일 계정 429 생존).
    assert "claude-sonnet-4-chat-root" in reachable, (
        "sonnet 대화 체인에 root 계정 fallback 이 없다 — claude-corp 429 시 즉시 실패(원 결함 재발)."
    )
    # 두 계정이 서로 다른 자격 slot(ANTHROPIC_API_KEY vs _ROOT)을 써야 실질 2계정.
    assert "ANTHROPIC_API_KEY_ROOT" in api_key_of.get("claude-sonnet-4-chat-root", "")
    assert api_key_of.get("claude-sonnet-4-chat", "").endswith("ANTHROPIC_API_KEY")
    # (3) edge-free — 체인의 모든 도달 alias 실 model 은 anthropic/*(gemma/로컬 도달 금지).
    offenders = {
        a: model_of.get(a, "<unknown>")
        for a in reachable
        if not model_of.get(a, "").startswith("anthropic/")
    }
    assert not offenders, f"sonnet 대화 폴백 체인에서 비-anthropic 모델 도달: {offenders}"
    assert "edge-fallback" not in reachable

    # 격리 불변식(NIT-a): bare claude-sonnet-4 는 대화 경로가 쓰지 않는 probe/OPENAI_MODEL/node_analysis
    # 전용이라 **단일 계정·fallback 미등록**으로 유지돼야 한다. 미래에 bare sonnet 에 fallback 을 잘못
    # 추가하면(격리 파괴) 이 단정이 잡는다.
    assert "claude-sonnet-4" in model_of, "bare claude-sonnet-4 deployment 가 사라짐 — probe 경로 회귀"
    assert "claude-sonnet-4" not in fb_map, (
        "bare claude-sonnet-4 에 fallback 이 생겼다 — 비대화 경로(probe/node_analysis)까지 root 로 폴백"
        "시켜 격리를 깬다(대화 회복성은 -chat 체인이 전담)."
    )


# ── G6: 누출 alias 해소 대상이 litellm 에 실제 등록된 model_name 인지 (config invariant) ──
# resolver 를 프록시 실 레지스트리에 고정 — 미래에 기본 chat alias 를 바꿔 미등록 이름으로
# 해소하면(다시 400) 이 테스트가 잡는다.
def test_leaking_aliases_resolve_to_registered_proxy_name():
    yaml = pytest.importorskip("yaml")
    with open(_LITELLM_CFG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    registered = {m["model_name"] for m in cfg["model_list"]}
    for alias in ("auto", "edge", "core", "code", "claude"):
        out = conversation_answer_model(alias)
        assert out in registered, (
            f"'{alias}' 해소 결과 '{out}' 가 litellm model_list 에 없음 — Bedrock 400 재발 위험. "
            f"등록된 이름: {sorted(registered)}"
        )


# ── G7: _call_llm 배선 — model='auto' 가 litellm 에 raw 로 새지 않는다 (누출 회귀 방지) ──
def test_call_llm_resolves_leaking_alias_before_create(monkeypatch):
    sink: dict = {}
    recorded: list = []
    _patch_side_effects(monkeypatch, recorded)

    agent_core._call_llm(
        _CaptureClient(sink), [{"role": "user", "content": "hi"}], "auto",
        conversation_id="conv-A", run_id="run-A",
    )

    # litellm create 에는 해소된 chat alias 가 나가야 한다(raw 'auto' → Bedrock 400 방지).
    assert sink["model"] == "claude-haiku-4-chat"
    assert sink["model"] != "auto"
    # 기록/표시 model 은 원본('auto') 유지 — 표시/집계 정합(호출측 책임 불변).
    assert recorded == [("auto", "agent")]


# ── G8: 누출 alias 의 max_tokens/thinking 는 아웃바운드(-chat) 기준으로 산정 (패널 CONFIRMED-DEFECT#1) ──
# outbound(claude-haiku-4-chat)는 litellm config 에 고정 thinking budget(5000)을 갖는다. 누출 alias(auto)의
# max_tokens 를 원본 기준(local cap 2048)으로 잡으면 max_tokens<budget → Anthropic 2차 400. budget 은 실제
# 서빙 outbound 기준(agent_max_output(claude-haiku-4-chat)=20000>5000)으로 산정돼야 한다. G7 이 stub 로
# 놓친 예산 경로를 실제로 태워 봉인(단, agent_max_output 은 스파이로 DB 비의존·결정론).
def test_call_llm_sizes_budget_from_outbound_for_leaking_alias(monkeypatch):
    sink: dict = {}
    recorded: list = []
    budget_calls: list = []
    # 예산 경로를 실제로 태운다 — model_supports_thinking / max_tokens_for_model 미stub(진짜 분기).
    monkeypatch.setattr(
        agent_core, "_record_llm_usage",
        lambda model, task, resp, conversation_id=None, run_id=None, latency_ms=None,
        target=None, step_gap_ms=None: recorded.append((model, task)),
    )
    monkeypatch.setattr(agent_core, "_load_attachment_inline_images", lambda: None)
    monkeypatch.setattr(agent_core, "messages_for_provider", lambda messages, **kw: messages)
    monkeypatch.setattr(agent_core, "model_supports_vision", lambda m: False)
    monkeypatch.setattr(agent_core, "thinking_budget_for_level", lambda level: None)
    monkeypatch.setattr(agent_core._rts, "reasoning_budget_override", lambda m, lvl: None)
    monkeypatch.setattr(agent_core._rts, "model_thinking_budget_override", lambda m: None)
    # agent_max_output 는 스파이(호출 model 기록 + 고정 20000) — DB 비의존·결정론. 원본 'auto' 가 새면 잡힘.
    monkeypatch.setattr(agent_core._rts, "agent_max_output", lambda m: budget_calls.append(m) or 20000)

    agent_core._call_llm(
        _CaptureClient(sink), [{"role": "user", "content": "hi"}], "auto",
        conversation_id="conv-B", run_id="run-B",
    )

    assert sink["model"] == "claude-haiku-4-chat"           # 아웃바운드
    # 핵심: 예산 산정도 아웃바운드(-chat) 기준 — 원본 'auto'(local cap 2048)로 새지 않는다.
    assert budget_calls == ["claude-haiku-4-chat"]
    assert isinstance(sink["max_tokens"], int) and sink["max_tokens"] > 5000, (
        f"outbound max_tokens={sink.get('max_tokens')} 가 -chat 고정 thinking budget 5000 이하 "
        f"→ Anthropic max_tokens>budget_tokens 위반(2차 400)."
    )
    # 기록/표시는 원본('auto') 유지.
    assert recorded == [("auto", "agent")]


# ── G8b: sonnet 대화 경로 — adaptive thinking(Sonnet 5), budget_tokens 절대 미주입 (sonnet5-upgrade) ──
# sonnet(claude-sonnet-4 alias)은 Sonnet 5 를 서빙하며 adaptive thinking 을 쓴다. 예산 경로를 실제로 태워
# (1) outbound 가 -chat, (2) max_tokens 키가 **원본 claude-sonnet-4**(outbound 아님)의 agent_max_output,
# (3) '일반'(reasoning_level 미지정)에서 budget_tokens/thinking override 를 **절대 주입하지 않음**(Sonnet 5
# budget_tokens 400 방지)을 고정한다.
def test_call_llm_sonnet_adaptive_no_budget_tokens(monkeypatch):
    sink: dict = {}
    recorded: list = []
    budget_calls: list = []
    monkeypatch.setattr(
        agent_core, "_record_llm_usage",
        lambda model, task, resp, conversation_id=None, run_id=None, latency_ms=None,
        target=None, step_gap_ms=None: recorded.append((model, task)),
    )
    monkeypatch.setattr(agent_core, "_load_attachment_inline_images", lambda: None)
    monkeypatch.setattr(agent_core, "messages_for_provider", lambda messages, **kw: messages)
    monkeypatch.setattr(agent_core, "model_supports_vision", lambda m: False)
    monkeypatch.setattr(agent_core, "thinking_budget_for_level", lambda level: None)
    monkeypatch.setattr(agent_core._rts, "reasoning_budget_override", lambda m, lvl: None)
    monkeypatch.setattr(agent_core._rts, "model_thinking_budget_override", lambda m: None)
    # agent_max_output 스파이(호출 model 기록 + sonnet default 40000) — DB 비의존·결정론.
    monkeypatch.setattr(agent_core._rts, "agent_max_output", lambda m: budget_calls.append(m) or 40000)

    agent_core._call_llm(
        _CaptureClient(sink), [{"role": "user", "content": "hi"}], "claude-sonnet-4",
        conversation_id="conv-S", run_id="run-S",
    )

    assert sink["model"] == "claude-sonnet-4-chat"          # 아웃바운드(edge-free 2계정)
    # max_tokens 키는 **원본** claude-sonnet-4(outbound 아님)의 agent_max_output — usage/override 정합.
    assert budget_calls == ["claude-sonnet-4"]
    assert isinstance(sink["max_tokens"], int) and sink["max_tokens"] == 40000
    # 핵심(sonnet5-upgrade): adaptive 이므로 '일반'에서 budget_tokens/thinking override 를 주입하지 않는다
    # (Sonnet 5 는 thinking budget_tokens 를 400 으로 거부). feature-0007 timeout-console-sync 이후
    # extra_body 에는 항상 body timeout(live AGENT_TIMEOUT_SEC)이 실리므로 None 이 아니라, thinking/
    # output_config 가 **없음**을 확인한다(timeout 은 존재하되 추론 override 는 누출 없음).
    _eb = sink["extra_body"] or {}
    assert isinstance(_eb.get("timeout"), int) and _eb["timeout"] >= 5, f"body timeout 누락: {_eb}"
    assert "thinking" not in _eb and "output_config" not in _eb, f"adaptive sonnet 에 override 누출: {_eb}"
    # 기록/표시는 원본 유지.
    assert recorded == [("claude-sonnet-4", "agent")]
