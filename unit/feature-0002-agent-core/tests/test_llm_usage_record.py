"""_record_llm_usage unit test — TASK-0163 (LLM 사용량 회계: resolved_model + cfg 귀속).

실 Postgres 없이 monkeypatch(FakeConn/FakeCursor) 로 동작. conftest.py 가 src path 추가.

검증 항목:
1. resolved_model(resp.model) + model(별칭) + cfg 전역 conversation/run 이 INSERT 에 들어감
2. resp.model 부재 시 resolved_model = None
3. usage 부재 시 no-op (INSERT 0)
4. total_tokens <= 0 시 no-op
5. PG 실패를 조용히 삼킴(예외 비전파)
"""

from __future__ import annotations

import pytest

from modules import llm
import shared.config as cfg
import modules.runtime_backend as rb


class FakeCursor:
    def __init__(self):
        self.executed: list[tuple] = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def close(self):
        pass


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class FakeUsage:
    def __init__(self, pt, ct, tt=None):
        self.prompt_tokens = pt
        self.completion_tokens = ct
        self.total_tokens = tt if tt is not None else pt + ct


class FakeResp:
    def __init__(self, usage=None, model=None):
        self.usage = usage
        self.model = model


@pytest.fixture(autouse=True)
def _reset_cfg(monkeypatch):
    monkeypatch.setattr(cfg, "MEMORY_CONVERSATION_ID", "", raising=False)
    monkeypatch.setattr(cfg, "CURRENT_RUN_ID", "", raising=False)
    yield


def test_record_inserts_resolved_model_and_cfg(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    monkeypatch.setattr(cfg, "MEMORY_CONVERSATION_ID", "conv-1", raising=False)
    monkeypatch.setattr(cfg, "CURRENT_RUN_ID", "run-1", raising=False)
    resp = FakeResp(usage=FakeUsage(10, 5), model="bedrock/anthropic.claude-haiku-4")
    llm._record_llm_usage("auto", "agent", resp)
    assert fake.committed is True
    assert len(fake.cursor_obj.executed) == 1
    sql, params = fake.cursor_obj.executed[0]
    assert "resolved_model" in sql
    # params 순서: (conv, run, model, resolved_model, task, pt, ct, tt)
    assert params[0] == "conv-1"
    assert params[1] == "run-1"
    assert params[2] == "auto"
    assert params[3] == "bedrock/anthropic.claude-haiku-4"
    assert params[4] == "agent"
    assert params[5] == 10
    assert params[6] == 5
    assert params[7] == 15


def test_record_explicit_conv_run_override_cfg(monkeypatch):
    # TASK-0163: in-process 동시 ask race 방지 — 명시 인자가 cfg 전역보다 우선.
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    monkeypatch.setattr(cfg, "MEMORY_CONVERSATION_ID", "cfg-conv", raising=False)
    monkeypatch.setattr(cfg, "CURRENT_RUN_ID", "cfg-run", raising=False)
    resp = FakeResp(usage=FakeUsage(1, 1), model="m")
    llm._record_llm_usage("auto", "agent", resp, conversation_id="explicit-conv", run_id="explicit-run")
    _, params = fake.cursor_obj.executed[0]
    assert params[0] == "explicit-conv"  # cfg 전역(cfg-conv) 무시
    assert params[1] == "explicit-run"


def test_record_falls_back_to_cfg_when_args_omitted(monkeypatch):
    # helper(classify/topic 등)는 명시 인자 미전달 → 기존 cfg 전역 fallback 유지.
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    monkeypatch.setattr(cfg, "MEMORY_CONVERSATION_ID", "cfg-conv", raising=False)
    monkeypatch.setattr(cfg, "CURRENT_RUN_ID", "cfg-run", raising=False)
    resp = FakeResp(usage=FakeUsage(1, 1), model="m")
    llm._record_llm_usage("edge", "classify", resp)
    _, params = fake.cursor_obj.executed[0]
    assert params[0] == "cfg-conv"
    assert params[1] == "cfg-run"


def test_record_resolved_model_none_when_absent(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    resp = FakeResp(usage=FakeUsage(3, 2), model=None)
    llm._record_llm_usage("edge", "classify", resp)
    _, params = fake.cursor_obj.executed[0]
    assert params[2] == "edge"
    assert params[3] is None


def test_record_noop_when_usage_missing(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    llm._record_llm_usage("auto", "agent", FakeResp(usage=None, model="x"))
    assert fake.cursor_obj.executed == []


def test_record_noop_when_zero_tokens(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    llm._record_llm_usage("auto", "agent", FakeResp(usage=FakeUsage(0, 0), model="x"))
    assert fake.cursor_obj.executed == []


def test_record_swallows_pg_failure(monkeypatch):
    class BrokenConn:
        def cursor(self):
            raise RuntimeError("pg down")

        def close(self):
            pass

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: BrokenConn())
    # 예외가 전파되면 메인 LLM 응답이 깨지므로 절대 raise 하면 안 됨.
    llm._record_llm_usage("auto", "agent", FakeResp(usage=FakeUsage(1, 1), model="x"))


# ── TASK-20260703-aiops-ttft-latency (정의 A): step_gap_ms(단계 간 간격) 기록 ────────
def test_record_includes_step_gap_ms_last(monkeypatch):
    # step_gap_ms 는 INSERT 맨 끝(… target, latency_ms, step_gap_ms). pt=5·ct=6·tt=7 보존(회귀 0).
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    resp = FakeResp(usage=FakeUsage(10, 5), model="claude-haiku-4")
    llm._record_llm_usage("core", "agent", resp, latency_ms=200, step_gap_ms=1300)
    sql, params = fake.cursor_obj.executed[0]
    assert "step_gap_ms" in sql
    assert params[5] == 10 and params[6] == 5 and params[7] == 15  # pt/ct/tt 보존
    assert params[-1] == 1300  # step_gap_ms = 마지막
    assert params[-2] == 200   # latency_ms = 그 앞


def test_record_step_gap_none_when_omitted(monkeypatch):
    # step_gap 미전달(첫 라운드·단발 호출) → NULL 로 남아 KPI 통계에서 제외.
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    llm._record_llm_usage("edge", "classify", FakeResp(usage=FakeUsage(1, 1), model="m"))
    _, params = fake.cursor_obj.executed[0]
    assert params[-1] is None  # step_gap_ms 미측정


def test_record_negative_step_gap_becomes_none(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    llm._record_llm_usage("core", "agent", FakeResp(usage=FakeUsage(1, 1), model="m"),
                          latency_ms=100, step_gap_ms=-5)
    _, params = fake.cursor_obj.executed[0]
    assert params[-1] is None  # 음수 방어 → NULL
