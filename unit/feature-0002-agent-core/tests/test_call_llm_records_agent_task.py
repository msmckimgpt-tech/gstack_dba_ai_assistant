"""_call_llm 계측 unit test — TASK-0163 RC1.

메인 agentic loop 의 LLM 호출(_call_llm)이 이전엔 _record_llm_usage chokepoint 를
우회해 사용자 대화 메인 추론이 한 건도 llm_usage 에 기록되지 않았다. 본 테스트는
_call_llm 이 응답 직후 _record_llm_usage(model, "agent", response) 를 호출하고
message 를 반환함을 회귀 방지로 고정한다.
"""

from __future__ import annotations

import agent_core


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
        self.model = "edge-real-model"


class _Completions:
    def create(self, **kwargs):
        return _Resp()


class _Client:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _Completions()})()


def test_call_llm_records_with_agent_task(monkeypatch):
    calls = []
    monkeypatch.setattr(
        agent_core, "_record_llm_usage",
        lambda model, task, resp, conversation_id=None, run_id=None: calls.append(
            (model, task, resp, conversation_id, run_id)
        ),
    )
    # 부수 의존 무력화 (vision/attachment/catalog 는 본 테스트 관심 밖).
    monkeypatch.setattr(agent_core, "_load_attachment_inline_images", lambda: None)
    monkeypatch.setattr(agent_core, "messages_for_provider", lambda messages, **kw: messages)
    monkeypatch.setattr(agent_core, "model_supports_vision", lambda m: False)
    monkeypatch.setattr(agent_core, "max_tokens_for_model", lambda m, t: None)

    # TASK-0163: race-free 귀속 — 호출자가 conversation_id/run_id 를 명시 전달.
    out = agent_core._call_llm(
        _Client(), [{"role": "user", "content": "hi"}], "auto",
        conversation_id="conv-X", run_id="run-X",
    )

    assert out == "FINAL_MESSAGE"
    assert len(calls) == 1
    model, task, resp, conv, run = calls[0]
    assert model == "auto"
    assert task == "agent"
    assert resp.usage.total_tokens == 2
    assert conv == "conv-X"
    assert run == "run-X"


def test_call_llm_record_failure_does_not_break(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("usage record failed")

    monkeypatch.setattr(agent_core, "_record_llm_usage", _boom)
    monkeypatch.setattr(agent_core, "_load_attachment_inline_images", lambda: None)
    monkeypatch.setattr(agent_core, "messages_for_provider", lambda messages, **kw: messages)
    monkeypatch.setattr(agent_core, "model_supports_vision", lambda m: False)
    monkeypatch.setattr(agent_core, "max_tokens_for_model", lambda m, t: None)

    # 회계 실패가 메인 추론 응답을 깨면 안 됨.
    out = agent_core._call_llm(_Client(), [{"role": "user", "content": "hi"}], "auto")
    assert out == "FINAL_MESSAGE"
