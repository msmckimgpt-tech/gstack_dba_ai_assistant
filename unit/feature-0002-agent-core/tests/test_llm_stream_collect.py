"""대화 LLM 호출 스트리밍 전환 (conv-audit `FR-llm-attempt-cap-inside-latency-tail`).

재현한 사고(2026-08-14, UI 표시 "새 대화" · 1:1 · 추론강도 max · 첨부 4건): 요청 접수 뒤
1라운드 LLM 호출이 **900초 무응답으로 per-attempt 상한에 걸려** 그때까지의 추론이 통째로
폐기됐고, 재시도가 같은 요청을 처음부터 다시 태워 481초 만에 성공했다(prompt 51,191 /
completion 48,221 tok). 사용자 대기 23분, 그 사이 진행 표시는 **두 번만** 갱신됐다 —
14:52:07 "추론하는 중" → 15:07:07 "재연결하는 중 (1/2)". 사용자는 살아 있는 run 을 멈춘
것으로 판단해 운영 개입을 요청했다.

근본은 상한의 **측정 대상**이었다. 비스트리밍 단일 호출에서 per-attempt 상한은 "응답 완료
까지" 를 재는데, 30일 성공 라운드 1,271건의 실측 지연은 p50 12.5s · p95 238.5s · **max
854s**(700s+ 3건 · 480s+ 7건)로 상한(콘솔 live 900s) **안쪽**이었다. 즉 정상적으로 진행 중인
무거운 추론이 상한에 걸리는 구조였다. 스트리밍에서는 같은 상한이 **chunk 간 무응답 간격**에
걸리므로 긴 정상 추론은 살아남고 진짜 hang 만 잡힌다(라이브 실측: ttft 2.16s,
`reasoning_content` delta 가 사고 중에도 도착).

합격선:
  1. chunk 를 누적한 결과가 비스트리밍 `message` 와 **같은 표면**을 갖는다 — `.content` ·
     `.tool_calls[i].id` · `.function.name` · `.function.arguments`. 소비처 3곳(메인 라운드 ·
     red-team 재생성 · red-team 재추론)이 무변경으로 남는 근거.
  2. `tool_calls` delta 는 index 별로 조립된다 — `arguments` 는 이어붙이고 `name` 은 첫 값만
     채택한다(litellm 의 Anthropic 변환이 name 을 반복 실어도 중복 연결되지 않게).
  3. `usage` 는 `choices=[]` 인 마지막 chunk 에서 포착된다(토큰 회계 무회귀).
  4. **reasoning/thinking delta 는 답변에 섞이지 않는다** — provider-private chain of thought
     를 사용자 답변으로 승격시키지 않는 기존 정책. 진행 신호용으로 분량만 센다.
  5. 취소는 스트림 수신 중에 반영되고, **일시 실패로 분류되지 않는다**(전용 예외). 종전에는
     per-attempt 전체가 단일 블로킹 호출이라 그 사이 눌린 중단이 무시됐다.
  6. `stream_options` 폴백 판정은 **좁다** — 일반 장애(500/연결 절단)를 폴백으로 삼켜 한 번 더
     태우면 이 봉인이 없애려는 "대기 배가" 를 스스로 재현한다.
  7. 진행 콜백은 **주기 게이트**로만 불린다(chunk 마다 부르면 DB 폴링이 chunk 수만큼 늘어난다).
  8. 출하 상수 계약 — 킬 스위치와 주기 기본값을 출하 값으로 직접 검증한다.
"""
import time

import pytest

import agent_core as AC
from shared import config as cfg

# 주기 게이트(진행 표시·취소 폴링)는 **실제 경과 시간**으로 열린다. 메모리 안 제너레이터는
# chunk 처리가 마이크로초라 아무리 작은 주기를 줘도 도달하지 못하므로, 주기 관련 테스트는
# chunk 사이에 최소한의 실경과를 만든다(총 수십 ms).
_TICK = 0.004


# ── 스트림 chunk 더블 ────────────────────────────────────────────────────────
class _Fn:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _TCDelta:
    def __init__(self, index=0, id=None, type=None, function=None):  # noqa: A002
        self.index = index
        self.id = id
        self.type = type
        self.function = function


class _Delta:
    def __init__(self, content=None, tool_calls=None, reasoning_content=None):
        self.content = content
        self.tool_calls = tool_calls
        self.reasoning_content = reasoning_content


class _Choice:
    def __init__(self, delta=None, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, choices=None, usage=None, model=None):
        self.choices = choices
        self.usage = usage
        self.model = model


def _text_stream(parts, finish="stop", usage=None, model="claude-sonnet-4-chat", tick=0.0):
    for p in parts:
        if tick:
            time.sleep(tick)
        yield _Chunk(choices=[_Choice(delta=_Delta(content=p))], model=model)
    yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason=finish)], model=model)
    if usage is not None:
        yield _Chunk(choices=[], usage=usage, model=model)


# ── 1. 텍스트 누적 + 비스트리밍 표면 동형 ─────────────────────────────────────
def test_content_chunks_are_joined_in_order():
    msg, finish, usage, served, stats = AC._collect_llm_stream(
        _text_stream(["안녕", "하세", "요"], usage=object()))
    assert msg.content == "안녕하세요"
    assert msg.role == "assistant"
    assert msg.tool_calls is None          # 도구 없으면 None (비스트리밍 표면)
    assert finish == "stop"
    assert usage is not None
    assert served == "claude-sonnet-4-chat"
    assert stats["chunks"] >= 4 and stats["content_chars"] == 5


def test_tool_only_response_has_none_content():
    """비스트리밍은 tool_calls 만 있을 때 content=None 이다 — 그 표면을 맞춘다.

    `raw_answer = getattr(msg, "content", "") or ""` 소비처가 ""/None 을 같게 다루므로
    계약 위반은 아니지만, 표면이 어긋나면 "빈 답변 재요청" 분기 판정이 달라질 수 있다.
    """
    def _s():
        yield _Chunk(choices=[_Choice(delta=_Delta(
            tool_calls=[_TCDelta(0, id="call_1", type="function",
                                 function=_Fn(name="describe_table", arguments='{"t":'))]))])
        yield _Chunk(choices=[_Choice(delta=_Delta(
            tool_calls=[_TCDelta(0, function=_Fn(arguments='"users"}'))]))])
        yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason="tool_calls")])

    msg, finish, _u, _m, _st = AC._collect_llm_stream(_s())
    assert msg.content is None
    assert finish == "tool_calls"
    assert len(msg.tool_calls) == 1
    tc = msg.tool_calls[0]
    assert (tc.id, tc.type, tc.function.name) == ("call_1", "function", "describe_table")
    assert tc.function.arguments == '{"t":"users"}'


# ── 2. tool_calls delta 병합 ─────────────────────────────────────────────────
def test_multiple_tool_calls_merge_by_index_in_order():
    def _s():
        yield _Chunk(choices=[_Choice(delta=_Delta(tool_calls=[
            _TCDelta(1, id="b", function=_Fn(name="search_tables", arguments="{}")),
            _TCDelta(0, id="a", function=_Fn(name="describe_table", arguments='{"x":1}')),
        ]))])
        yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason="tool_calls")])

    msg, _f, _u, _m, stats = AC._collect_llm_stream(_s())
    assert [tc.id for tc in msg.tool_calls] == ["a", "b"]      # index 순서로 정렬
    assert stats["tool_calls"] == 2


def test_repeated_name_delta_does_not_duplicate():
    """litellm 의 Anthropic 변환이 같은 name 을 여러 조각에 실어도 이어붙이지 않는다."""
    def _s():
        for _ in range(3):
            yield _Chunk(choices=[_Choice(delta=_Delta(tool_calls=[
                _TCDelta(0, id="c1", function=_Fn(name="execute_sql", arguments="a"))]))])
        yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason="tool_calls")])

    msg, _f, _u, _m, _st = AC._collect_llm_stream(_s())
    assert msg.tool_calls[0].function.name == "execute_sql"    # "execute_sqlexecute_sql…" 아님
    assert msg.tool_calls[0].function.arguments == "aaa"       # arguments 는 누적


def test_nameless_tool_call_is_dropped():
    """이름 없는 tool_call 은 하류에서 호출할 수 없다 — 조립 결과에서 제외한다."""
    def _s():
        yield _Chunk(choices=[_Choice(delta=_Delta(tool_calls=[
            _TCDelta(0, id="x", function=_Fn(arguments="{}"))]))])
        yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason="tool_calls")])

    msg, _f, _u, _m, _st = AC._collect_llm_stream(_s())
    assert msg.tool_calls is None


def test_length_finish_reason_is_preserved():
    """출력 상한 절단 신호가 그대로 전달된다 — `FR-attach-delivery-truncated-by-output-cap`
    봉인이 `finish_reason == "length"` 에 의존하므로, 스트리밍이 이 값을 잃으면 그 봉인이
    **조용히 무력화**된다. 라이브 실측으로도 확인했다(haiku, content 6,566자 → 'length')."""
    _msg, finish, _u, _m, _st = AC._collect_llm_stream(_text_stream(["긴 답변"], finish="length"))
    assert finish == "length"


# ── 2-b. 완결 신호 부재 = 실패 (비스트리밍에 없던 실패 모드) ─────────────────
def test_stream_without_finish_reason_is_incomplete():
    """조용한 EOF(프록시 절단·게이트웨이 교체)를 정상 종료로 착각하지 않는다.

    이 방어가 없으면 절단된 답변이 완전한 답변으로, 불완전 JSON arguments 가 완전한 도구
    호출로 하류에 전달된다 — 비스트리밍에는 존재하지 않던 입구다.
    """
    def _s():
        yield _Chunk(choices=[_Choice(delta=_Delta(content="여기까지만 오고 소켓이"))])
        yield _Chunk(choices=[_Choice(delta=_Delta(content=" 조용히 닫혔다"))])
        # finish_reason 없이 끝 — StopIteration 은 정상 종료와 구별되지 않는다.

    with pytest.raises(AC._LLMStreamIncomplete):
        AC._collect_llm_stream(_s())


def test_incomplete_stream_does_not_leak_partial_tool_calls():
    """절단된 tool_calls(불완전 arguments)도 승격되지 않는다."""
    def _s():
        yield _Chunk(choices=[_Choice(delta=_Delta(
            tool_calls=[_TCDelta(0, id="c", type="function",
                                 function=_Fn(name="execute_sql", arguments='{"sql":"SELECT'))]))])

    with pytest.raises(AC._LLMStreamIncomplete):
        AC._collect_llm_stream(_s())


def test_empty_stream_is_incomplete_not_empty_answer():
    """chunk 0개도 '빈 답변' 이 아니라 실패다 — 빈 답변 재요청 루프로 새지 않게."""
    with pytest.raises(AC._LLMStreamIncomplete):
        AC._collect_llm_stream(iter([]))


def test_incomplete_is_transient_by_classification():
    """전용 분기 없이도 기존 재시도 계약이 흡수한다(미분류 예외 → transient)."""
    from modules.llm import classify_agent_llm_failure, FAILURE_TRANSIENT

    info = classify_agent_llm_failure(AC._LLMStreamIncomplete("stream ended without finish_reason"))
    assert info["kind"] == FAILURE_TRANSIENT


# ── 3. usage 포착 (choices 가드 앞에서) ──────────────────────────────────────
def test_usage_chunk_with_empty_choices_is_captured():
    sentinel = object()
    _msg, _f, usage, _m, _st = AC._collect_llm_stream(
        _text_stream(["ok"], usage=sentinel))
    assert usage is sentinel


# ── 4. reasoning delta 는 답변에 섞이지 않는다 (보안 정책) ────────────────────
def test_reasoning_delta_never_enters_content():
    def _s():
        yield _Chunk(choices=[_Choice(delta=_Delta(reasoning_content="비밀 사고과정"))])
        yield _Chunk(choices=[_Choice(delta=_Delta(content="최종 답변"))])
        yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason="stop")])

    msg, _f, _u, _m, stats = AC._collect_llm_stream(_s())
    assert msg.content == "최종 답변"
    assert "비밀" not in (msg.content or "")
    assert stats["reasoning_chars"] == len("비밀 사고과정")   # 분량만 센다(진행 신호용)


# ── 5. 취소는 스트림 중에 반영되고 일시 실패가 아니다 ──────────────────────────
def test_cancel_during_stream_raises_dedicated_exception():
    def _s():
        for i in range(50):
            time.sleep(_TICK)
            yield _Chunk(choices=[_Choice(delta=_Delta(content=str(i)))])

    with pytest.raises(AC._LLMStreamCanceled):
        AC._collect_llm_stream(_s(), abort_check=lambda: "cancel", abort_poll_sec=_TICK)


def test_finalize_during_stream_is_distinct_from_cancel():
    """'즉시 답변' 은 취소와 **다른** 예외다 — 하류 처리가 다르다(§18.8 [P1]).

    취소는 run 을 끝내고, finalize 는 바깥 루프의 도구-없는 마무리 라운드로 넘긴다. 한 bool 로
    합치면 사용자가 '즉시 답변' 을 눌렀는데 요청이 취소되거나(반대로) 무시된다.
    """
    def _s():
        for i in range(50):
            time.sleep(_TICK)
            yield _Chunk(choices=[_Choice(delta=_Delta(content=str(i)))])

    with pytest.raises(AC._LLMStreamFinalizeRequested):
        AC._collect_llm_stream(_s(), abort_check=lambda: "finalize", abort_poll_sec=_TICK)


def test_unknown_abort_signal_does_not_stop_stream():
    """알 수 없는 문자열은 중단 신호가 아니다(오중단 금지)."""
    msg, _f, _u, _m, _st = AC._collect_llm_stream(
        _text_stream(["계", "속"], tick=_TICK), abort_check=lambda: "maybe", abort_poll_sec=_TICK)
    assert msg.content == "계속"


def test_stream_is_closed_on_abort_and_on_success():
    """abort 로 빠져나가도 응답을 닫는다 — 안 닫으면 연결·upstream 생성이 GC 까지 남는다."""
    class _ClosableStream:
        def __init__(self, n):
            self.closed = False
            self._n = n

        def __iter__(self):
            for i in range(self._n):
                time.sleep(_TICK)
                yield _Chunk(choices=[_Choice(delta=_Delta(content="z"))])
            yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason="stop")])

        def close(self):
            self.closed = True

    aborted = _ClosableStream(50)
    with pytest.raises(AC._LLMStreamCanceled):
        AC._collect_llm_stream(aborted, abort_check=lambda: "cancel", abort_poll_sec=_TICK)
    assert aborted.closed is True, "abort 경로에서 close 누락"

    ok = _ClosableStream(2)
    AC._collect_llm_stream(ok)
    assert ok.closed is True, "정상 종료 경로에서 close 누락"


def test_cancel_check_failure_is_fail_open():
    """취소 판정이 예외를 던지면(KV/DB 일시 장애) 답변을 계속한다 — 오취소 금지."""
    def _boom():
        raise RuntimeError("kv down")

    msg, _f, _u, _m, _st = AC._collect_llm_stream(
        _text_stream(["살아", "있다"], tick=_TICK), abort_check=_boom, abort_poll_sec=_TICK)
    assert msg.content == "살아있다"


def test_cancel_not_polled_when_interval_zero():
    """poll 주기 0(비활성)이면 취소 검사를 아예 하지 않는다(종전 동작)."""
    calls = []
    msg, _f, _u, _m, _st = AC._collect_llm_stream(
        _text_stream(["x"]), abort_check=lambda: calls.append(1) or "cancel",
        abort_poll_sec=0.0)
    assert msg.content == "x" and calls == []


# ── 6. stream_options 폴백 판정은 좁다 ───────────────────────────────────────
@pytest.mark.parametrize("exc, expected", [
    (TypeError("unexpected keyword argument 'stream_options'"), True),
    (Exception("Error code: 400 - unrecognized request argument supplied: stream_options"), True),
    (Exception("Error code: 400 - invalid_request_error: include_usage unsupported"), True),
    # ↓ 실제 장애 — 폴백으로 삼키면 같은 요청을 한 번 더 태워 대기가 배가된다.
    (Exception("Error code: 500 - internal server error"), False),
    (Exception("Connection error."), False),
    (Exception("Request timed out."), False),
    (Exception("Error code: 429 - rate_limit_error"), False),
])
def test_stream_options_fallback_is_narrow(exc, expected):
    assert AC._stream_options_rejected(exc) is expected


# ── 7. 진행 콜백은 주기 게이트로만 불린다 ────────────────────────────────────
def test_progress_callback_is_rate_limited():
    seen = []
    AC._collect_llm_stream(_text_stream(["x"] * 200), on_progress=seen.append,
                           progress_interval_sec=3600.0)   # 이 스트림 동안 도달 불가
    assert seen == []


def test_progress_callback_receives_elapsed_and_counts():
    seen = []

    def _s():
        for i in range(5):
            time.sleep(_TICK)
            yield _Chunk(choices=[_Choice(delta=_Delta(content="ab"))])
        yield _Chunk(choices=[_Choice(delta=_Delta(), finish_reason="stop")])

    AC._collect_llm_stream(_s(), on_progress=seen.append, progress_interval_sec=_TICK)
    assert seen, "주기 도달 시 최소 1회 호출"
    assert set(("elapsed_sec", "chunks", "content_chars", "reasoning_chars")) <= set(seen[0])
    assert seen[-1]["content_chars"] > 0


def test_progress_callback_exception_does_not_break_answer():
    """진행 표시 실패가 답변을 깨지 않는다(계측이 기능을 죽이지 않는 기존 원칙)."""
    def _boom(_info):
        raise RuntimeError("emit failed")

    msg, _f, _u, _m, _st = AC._collect_llm_stream(
        _text_stream(["답", "변"], tick=_TICK), on_progress=_boom, progress_interval_sec=_TICK)
    assert msg.content == "답변"


def test_progress_callback_may_abort_via_cancel_exception():
    """콜백이 취소를 감지해 전용 예외를 올리면 그건 삼키지 않고 전파한다."""
    def _cb(_info):
        raise AC._LLMStreamCanceled("canceled inside progress")

    def _s():
        for _ in range(10):
            time.sleep(_TICK)
            yield _Chunk(choices=[_Choice(delta=_Delta(content="y"))])

    with pytest.raises(AC._LLMStreamCanceled):
        AC._collect_llm_stream(_s(), on_progress=_cb, progress_interval_sec=_TICK)


# ── 8. 출하 상수 계약 ────────────────────────────────────────────────────────
def test_shipped_stream_defaults():
    """fixture 로 낮추지 않고 출하 값을 직접 검증한다(상수 되돌림 뮤턴트 차단)."""
    assert cfg.AGENT_LLM_STREAM_ENABLED is True          # 기본 활성 — 킬 스위치는 opt-out
    assert cfg.AGENT_LLM_STREAM_PROGRESS_SEC == 120.0    # 15분 구간이 최소 7회 갱신된다
    assert cfg.AGENT_LLM_STREAM_CANCEL_POLL_SEC == 10.0
    # body `timeout` 은 건드리지 않았다 — feature-0007 계약(콘솔 값 = per-attempt upstream
    # 상한)이 그대로 유지된다. 초판의 배수 knob 은 라이브 실측이 전제를 반증해 제거했다.
    assert not hasattr(cfg, "AGENT_LLM_STREAM_UPSTREAM_MULT")


def test_progress_interval_splits_the_observed_dead_window():
    """실측 무진전 구간(900초)이 주기로 쪼개져 사용자가 진행을 본다 — 회귀 시 이 수치가 깨진다."""
    observed_dead_window_sec = 900.0
    updates = observed_dead_window_sec / cfg.AGENT_LLM_STREAM_PROGRESS_SEC
    assert updates >= 7, "15분 구간에 최소 7회 진행 표시가 갱신되어야 한다"


# ── 9. 메인/red-team 배선 (§18.8 패널 QA [P1] — 콜백 제거 뮤턴트 차단) ────────
def test_main_loop_wires_progress_and_abort_callbacks():
    """메인 라운드가 `_call_llm` 에 진행·abort 콜백을 **실제로 넘기는지** 잠근다.

    수집기 단위 테스트는 콜백을 직접 주입하므로, 루프가 인자를 빼먹어도(뮤턴트) 전부 통과한다
    — 그러면 진행 표시와 스트림 중 탈출구가 조용히 사라진다. `_run_agent_core` 를 통째로
    돌리려면 DB·프롬프트·도구 전 계층이 필요해, 여기서는 호출 지점의 인자 배선을 소스에서
    확인한다. **한계**: 인자가 전달되는 사실만 잠그고 콜백의 내용은 위 단위 테스트가 담당한다.
    주석은 제외해 "주석에만 남은 배선" 이 통과하지 않게 한다.
    """
    import inspect
    import re

    src = inspect.getsource(AC._run_agent_core)
    code = "\n".join(
        re.sub(r"#.*$", "", ln) for ln in src.splitlines()
    )
    # 메인 라운드 호출부: 두 인자가 모두 실려야 한다.
    assert "on_stream_progress=" in code, "메인 라운드가 진행 콜백을 넘기지 않는다"
    assert "stream_abort_check=" in code, "메인 라운드가 abort 콜백을 넘기지 않는다"
    # red-team 두 경로(재생성·재추론)도 abort 를 넘긴다 — 넘기지 않으면 리뷰어 호출 중
    # 사용자 신호가 per-attempt 상한까지 무시된다.
    assert code.count("stream_abort_check=") >= 3, (
        "abort 배선이 메인 + red-team 2경로(재생성·재추론) 모두에 있어야 한다: "
        f"발견 {code.count('stream_abort_check=')}곳"
    )
    # 두 신호를 구분해 돌려주는 콜백이 존재한다(bool 로 합치면 하류 처리가 뒤섞인다).
    assert '"finalize"' in code and '"cancel"' in code


def test_finish_reason_reaches_truncation_contextvar():
    """`finish_reason` 이 run-scoped 채널에 실제로 실린다 — 절단 안전망의 입력이다.

    반환값만 검증하면 `_LLM_LAST_FINISH_REASON_CTX.set(...)` 제거 뮤턴트가 통과하고,
    `FR-attach-delivery-truncated-by-output-cap` 의 절단 감지가 조용히 죽는다.
    """
    class _Completions:
        def create(self, **kwargs):
            assert kwargs.get("stream") is True
            return _text_stream(["잘린 답변"], finish="length")

    class _Client:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    AC._LLM_LAST_FINISH_REASON_CTX.set(None)
    AC._call_llm(_Client(), [{"role": "user", "content": "hi"}], "claude-haiku-4")
    assert AC._LLM_LAST_FINISH_REASON_CTX.get() == "length"
    # 절단 안전망의 공개 판정 함수까지 실제로 True 가 되어야 한다(채널만 채우고 소비되지 않으면
    # 의미가 없다).
    assert AC.last_answer_was_truncated() is True


def test_call_llm_requests_usage_in_stream_options():
    """`stream_options={"include_usage": True}` 가 실제로 전송된다 — 빠지면 토큰 회계가 빈다."""
    seen: dict = {}

    class _Completions:
        def create(self, **kwargs):
            seen.update(kwargs)
            return _text_stream(["ok"], usage=object())

    class _Client:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    AC._call_llm(_Client(), [{"role": "user", "content": "hi"}], "claude-haiku-4")
    assert seen.get("stream") is True
    assert seen.get("stream_options") == {"include_usage": True}
    # per-request read 상한(chunk 간 무응답)도 함께 실린다.
    assert isinstance(seen.get("timeout"), int) and seen["timeout"] > 0


def test_progress_is_not_emitted_per_chunk():
    """주기 게이트가 실제로 억제하는지 — `last_progress = now` 제거 뮤턴트 차단.

    "최소 1회" 만 보면 chunk 마다 activity 가 생겨도 통과해, 장시간 스트림에서 steps 가
    폭증하는 회귀를 놓친다. chunk 수보다 훨씬 적게 불리는 것을 상한으로 잠근다.
    """
    seen = []
    n_chunks = 60
    AC._collect_llm_stream(_text_stream(["c"] * n_chunks, tick=_TICK),
                           on_progress=seen.append,
                           progress_interval_sec=_TICK * 12)
    assert seen, "주기가 열렸는데 한 번도 안 불렸다"
    assert len(seen) <= n_chunks / 4, (
        f"주기 억제가 동작하지 않는다 — chunk {n_chunks}개에 진행 표시 {len(seen)}회"
    )


def test_progress_and_abort_intervals_have_floor():
    """운영자가 0.001 을 넣어도 하한으로 clamp 된다(0 = 비활성은 유지)."""
    import importlib

    import shared.config as _cfg

    def _reload(env):
        import os
        old = {k: os.environ.get(k) for k in env}
        os.environ.update({k: v for k, v in env.items()})
        try:
            return importlib.reload(_cfg)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    c = _reload({"AGENT_LLM_STREAM_PROGRESS_SEC": "0.001",
                 "AGENT_LLM_STREAM_CANCEL_POLL_SEC": "0.001"})
    assert c.AGENT_LLM_STREAM_PROGRESS_SEC >= 10.0
    assert c.AGENT_LLM_STREAM_CANCEL_POLL_SEC >= 2.0
    c = _reload({"AGENT_LLM_STREAM_PROGRESS_SEC": "0",
                 "AGENT_LLM_STREAM_CANCEL_POLL_SEC": "0"})
    assert c.AGENT_LLM_STREAM_PROGRESS_SEC == 0.0      # 0 = 비활성(종전 동작)
    assert c.AGENT_LLM_STREAM_CANCEL_POLL_SEC == 0.0
    _reload({})   # 출하 기본값 복원
