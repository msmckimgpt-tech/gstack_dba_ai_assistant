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
    # TASK-AIOPS: _call_llm 이 이제 latency_ms 도 전달하므로 mock 이 이를 수용해야 한다
    # (미수용 시 TypeError → _call_llm 의 try/except 가 삼켜 기록 0건으로 회귀).
    monkeypatch.setattr(
        agent_core, "_record_llm_usage",
        # 0032: target=None, 0033: step_gap_ms=None 도 수용해야 한다(_record_llm_usage 신규 kwarg) —
        # 미수용 시 agent 경로가 신규 kwarg 를 넘기면 TypeError → _call_llm try/except 가 삼켜 기록 0건
        # 회귀. latency_ms 와 동일 방어.
        lambda model, task, resp, conversation_id=None, run_id=None, latency_ms=None, target=None,
        step_gap_ms=None: calls.append(
            (model, task, resp, conversation_id, run_id, latency_ms, step_gap_ms)
        ),
    )
    # 부수 의존 무력화 (vision/attachment/catalog 는 본 테스트 관심 밖).
    monkeypatch.setattr(agent_core, "_load_attachment_inline_images", lambda: None)
    monkeypatch.setattr(agent_core, "messages_for_provider", lambda messages, **kw: messages)
    monkeypatch.setattr(agent_core, "model_supports_vision", lambda m: False)
    monkeypatch.setattr(agent_core, "max_tokens_for_model", lambda m, t: None)

    # TASK-0163: race-free 귀속 — 호출자가 conversation_id/run_id 를 명시 전달.
    # TASK-20260703-aiops-ttft-latency: 루프가 계산한 step_gap_ms(단계 간 간격)를 전달 → 기록에 forwarding.
    out = agent_core._call_llm(
        _Client(), [{"role": "user", "content": "hi"}], "auto",
        conversation_id="conv-X", run_id="run-X", step_gap_ms=1300,
    )

    assert out == "FINAL_MESSAGE"
    assert len(calls) == 1
    model, task, resp, conv, run, latency_ms, step_gap_ms = calls[0]
    assert model == "auto"
    assert task == "agent"
    assert resp.usage.total_tokens == 2
    assert conv == "conv-X"
    assert run == "run-X"
    # TASK-AIOPS: main agent 경로도 latency 기록(중앙 래퍼 미경유 gap 보완).
    assert isinstance(latency_ms, int) and latency_ms >= 0
    # TASK-20260703 (정의 A): step_gap_ms 가 _record_llm_usage 로 forwarding 됨(단계 간 간격 계측).
    assert step_gap_ms == 1300


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
