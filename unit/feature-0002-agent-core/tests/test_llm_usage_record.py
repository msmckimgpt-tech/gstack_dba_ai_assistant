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
    # 컬럼 꼬리 순서: … target, latency_ms, step_gap_ms, target_scope, cache_read_tokens,
    # cache_write_tokens. pt=5·ct=6·tt=7 보존(회귀 0).
    # **0056(캐시 계측)으로 맨 끝 두 자리가 캐시 축**(의도된 계약 변경) — target_scope 는 뒤에서 셋째.
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    resp = FakeResp(usage=FakeUsage(10, 5), model="claude-haiku-4")
    llm._record_llm_usage("core", "agent", resp, latency_ms=200, step_gap_ms=1300)
    sql, params = fake.cursor_obj.executed[0]
    assert "step_gap_ms" in sql
    assert params[5] == 10 and params[6] == 5 and params[7] == 15  # pt/ct/tt 보존
    assert params[-1] == 0 and params[-2] == 0  # 캐시 미제공 응답 → 0(미측정 NULL 아님)
    assert params[-3] is None  # target_scope (미전달·ContextVar 미설정 → NULL)
    assert params[-4] == 1300  # step_gap_ms
    assert params[-5] == 200   # latency_ms


# ── 0047: target_scope(사용 기록 데이터소스 귀속) ────────────────────────────────
def test_record_target_scope_explicit_arg(monkeypatch):
    """명시 인자가 최우선 — 병렬 스레드 경로(ContextVar 미전파)의 정확한 귀속 보장."""
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    resp = FakeResp(usage=FakeUsage(10, 5), model="claude-haiku-4")
    llm._record_llm_usage("core", "node_analysis", resp, target="log_v2.t1",
                          target_scope="mysql-abc123")
    sql, params = fake.cursor_obj.executed[0]
    assert "target_scope" in sql
    assert params[-3] == "mysql-abc123"   # 0056: 뒤 두 자리는 캐시 축


def test_record_target_scope_contextvar_fallback(monkeypatch):
    """미전달 시 active-datasource ContextVar 폴백(insight 워커 사이클 경로)."""
    import shared.config as cfg
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    prev = cfg.get_active_datasource()
    try:
        cfg.set_active_datasource("mssql-ctxvar")
        resp = FakeResp(usage=FakeUsage(10, 5), model="claude-haiku-4")
        llm._record_llm_usage("core", "table_insight", resp, target="dbo.T")
        _sql, params = fake.cursor_obj.executed[0]
        assert params[-3] == "mssql-ctxvar"   # 0056: 뒤 두 자리는 캐시 축
    finally:
        cfg.set_active_datasource(prev)


def test_record_target_scope_clipped_to_96(monkeypatch):
    """VARCHAR(96) 초과는 잘라 INSERT 실패(계측 유실)를 막는다."""
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    resp = FakeResp(usage=FakeUsage(10, 5), model="claude-haiku-4")
    llm._record_llm_usage("core", "table_insight", resp, target_scope="x" * 200)
    _sql, params = fake.cursor_obj.executed[0]
    assert len(params[-3]) == 96          # 0056: 뒤 두 자리는 캐시 축


def test_record_step_gap_none_when_omitted(monkeypatch):
    # step_gap 미전달(첫 라운드·단발 호출) → NULL 로 남아 KPI 통계에서 제외.
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    llm._record_llm_usage("edge", "classify", FakeResp(usage=FakeUsage(1, 1), model="m"))
    _, params = fake.cursor_obj.executed[0]
    assert params[-4] is None  # step_gap_ms 미측정 (0056: 뒤 두 자리는 캐시 축)


def test_record_negative_step_gap_becomes_none(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    llm._record_llm_usage("core", "agent", FakeResp(usage=FakeUsage(1, 1), model="m"),
                          latency_ms=100, step_gap_ms=-5)
    _, params = fake.cursor_obj.executed[0]
    assert params[-4] is None  # 음수 방어 → NULL (0056: 뒤 두 자리는 캐시 축)


# ── usage-metric-charts(2026-08-13): 프롬프트 캐시 계측 + cache_control 주입 ──────────────
#
# 착수 전 게이트웨이 실측으로 확정한 응답 형태를 그대로 고정한다:
#   최상위 cache_read_input_tokens / cache_creation_input_tokens (Anthropic 원형)
#   prompt_tokens_details.{cached_tokens, cache_creation_tokens} (OpenAI 호환)
# provider 가 한쪽만 채우는 변형에서도 계측이 0 으로 굳지 않아야 한다.

class _CacheUsage(FakeUsage):
    def __init__(self, pt, ct, read=0, write=0, details=None):
        super().__init__(pt, ct)
        if read or write:
            self.cache_read_input_tokens = read
            self.cache_creation_input_tokens = write
        if details is not None:
            self.prompt_tokens_details = details


def test_record_captures_cache_tokens_top_level(monkeypatch):
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    resp = FakeResp(usage=_CacheUsage(5039, 101, read=5002, write=0), model="claude-haiku-4")
    llm._record_llm_usage("claude-haiku-4", "agent", resp)
    sql, params = fake.cursor_obj.executed[0]
    assert "cache_read_tokens" in sql and "cache_write_tokens" in sql
    assert params[-2] == 5002 and params[-1] == 0


def test_record_captures_cache_tokens_from_details_fallback(monkeypatch):
    """최상위 필드가 없고 prompt_tokens_details 만 있는 변형도 계측한다."""
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    resp = FakeResp(usage=_CacheUsage(5039, 101,
                                      details={"cached_tokens": 0, "cache_creation_tokens": 5002}),
                    model="claude-haiku-4")
    llm._record_llm_usage("claude-haiku-4", "agent", resp)
    _sql, params = fake.cursor_obj.executed[0]
    assert params[-2] == 0 and params[-1] == 5002


def test_record_cache_tokens_absent_is_zero_not_null(monkeypatch):
    """캐시 필드가 아예 없는 응답(로컬 LLM 등)은 0 — 미측정 NULL 이 아니라 '없음' 이 사실이다."""
    fake = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake)
    llm._record_llm_usage("edge", "classify", FakeResp(usage=FakeUsage(10, 5), model="gemma"))
    _sql, params = fake.cursor_obj.executed[0]
    assert params[-2] == 0 and params[-1] == 0


# ── _apply_prompt_cache: system 마지막 블록에만 브레이크포인트 ─────────────────────────

_BIG = "규칙 항목. " * 1200   # _PROMPT_CACHE_MIN_CHARS(4000) 초과


def _cc(msg):
    """메시지의 cache_control 지시 목록(블록 순서대로)."""
    c = msg.get("content")
    return [b.get("cache_control") for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def test_apply_prompt_cache_marks_last_system_only():
    msgs = [
        {"role": "system", "content": "Claude Code identity"},
        {"role": "system", "content": _BIG},
        {"role": "user", "content": "질문"},
    ]
    out = llm._apply_prompt_cache(msgs, "claude-haiku-4")
    # identity(첫 system)는 문자열 그대로 — 캐시 접두는 마지막 브레이크포인트까지 전부이므로
    # 표시는 한 곳이면 충분하다.
    assert out[0]["content"] == "Claude Code identity"
    assert _cc(out[1]) == [{"type": "ephemeral"}]
    assert out[2]["content"] == "질문"      # 히스토리에는 붙이지 않는다(매 턴 꼬리가 바뀜)
    assert msgs[1]["content"] == _BIG        # 원본 불변(재시도 경로 안전)


def test_apply_prompt_cache_skips_short_system():
    msgs = [{"role": "system", "content": "짧은 지시"}, {"role": "user", "content": "q"}]
    assert llm._apply_prompt_cache(msgs, "claude-haiku-4") is msgs   # 원본 그대로


def test_apply_prompt_cache_skips_local_llm():
    msgs = [{"role": "system", "content": _BIG}, {"role": "user", "content": "q"}]
    assert llm._apply_prompt_cache(msgs, "edge") is msgs


def test_apply_prompt_cache_respects_existing_control():
    msgs = [{"role": "system", "content": [{"type": "text", "text": _BIG,
                                            "cache_control": {"type": "ephemeral"}}]},
            {"role": "user", "content": "q"}]
    assert llm._apply_prompt_cache(msgs, "claude-haiku-4") is msgs   # 중복 브레이크포인트 금지


def test_apply_prompt_cache_no_system_is_noop():
    msgs = [{"role": "user", "content": _BIG}]
    assert llm._apply_prompt_cache(msgs, "claude-haiku-4") is msgs
