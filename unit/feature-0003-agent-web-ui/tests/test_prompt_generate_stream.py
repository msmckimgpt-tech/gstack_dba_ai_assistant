"""TASK-0233 — 제품 프롬프트 자동작성 LLM 토큰 스트리밍(SSE) 로직 계약 테스트.

admin_generate_product_prompt_stream 은 LLM 의 동기 stream(ChatCompletionChunk
generator)을 별 스레드 + asyncio.Queue 로 브릿지해 SSE(progress/token/done/error)
로 흘려보낸다. app.py 는 컨테이너 전용 의존성(modules.memory 등)이 있어 로컬 import
불가하므로, 여기서는 핸들러가 의존하는 두 계약을 독립 검증한다:

  1. SSE 프레임 직렬화(`_sse_pack` 와 동형) + 파싱 라운드트립 — 한국어/JSON 안전.
  2. Queue 브릿지 소비 루프의 누적/truncated/error 분기 — fake chunk generator 로
     실제 핸들러의 event_stream 소비 로직과 동일한 술어를 재현.

핸들러 코드(app.py)가 이 술어와 어긋나면 회귀다 — 동일 로직 유지가 계약.
"""

import asyncio
import json


# ── 1. SSE 프레임 직렬화/파싱 (app._sse_pack 동형) ──────────────────────

def _sse_pack(event: str, payload: dict) -> str:
    """app.py _sse_pack 와 동일 술어. 어긋나면 회귀."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _parse_sse_frames(blob: str):
    """admin.js 가 하는 SSE 파싱과 동형 — `\\n\\n` 경계로 프레임 분리, event/data 추출."""
    frames = []
    for raw in blob.split("\n\n"):
        raw = raw.strip()
        if not raw:
            continue
        ev, data = None, None
        for line in raw.split("\n"):
            if line.startswith("event:"):
                ev = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
        frames.append((ev, json.loads(data) if data else None))
    return frames


def test_sse_pack_korean_roundtrip():
    """한국어 payload 가 SSE 직렬화→파싱 라운드트립에서 보존돼야 한다(ensure_ascii=False)."""
    frame = _sse_pack("token", {"text": "안녕하세요 분석 어시스턴트"})
    assert frame.startswith("event: token\n")
    assert frame.endswith("\n\n")
    ev, payload = _parse_sse_frames(frame)[0]
    assert ev == "token"
    assert payload["text"] == "안녕하세요 분석 어시스턴트"


def test_sse_pack_multiple_frames_parse():
    """여러 프레임을 이어 붙여도 경계로 정확히 분리돼야 한다."""
    blob = (
        _sse_pack("progress", {"stage": "generating", "label": "생성 중"})
        + _sse_pack("token", {"text": "A"})
        + _sse_pack("token", {"text": "B"})
        + _sse_pack("done", {"prompt": "AB", "meta": {"truncated": False}})
    )
    frames = _parse_sse_frames(blob)
    assert [f[0] for f in frames] == ["progress", "token", "token", "done"]
    assert frames[-1][1]["prompt"] == "AB"
    assert frames[-1][1]["meta"]["truncated"] is False


# ── 2. Queue 브릿지 소비 루프 (app.event_stream 동형) ───────────────────

class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content=None, finish_reason=None):
        self.delta = _FakeDelta(content)
        self.finish_reason = finish_reason


class _FakeChunk:
    def __init__(self, content=None, finish_reason=None):
        self.choices = [_FakeChoice(content, finish_reason)]


def _fake_stream(tokens, finish_reason="stop", raise_at=None):
    """OpenAI SDK 의 stream=True 동기 generator 모사."""
    for i, t in enumerate(tokens):
        if raise_at is not None and i == raise_at:
            raise RuntimeError("boom")
        yield _FakeChunk(content=t)
    yield _FakeChunk(finish_reason=finish_reason)


async def _consume(make_stream):
    """app.event_stream 의 Queue 브릿지 소비 루프와 동일 술어를 재현.

    make_stream: () -> 동기 generator (LLM stream). 별 스레드에서 iterate.
    반환: (frames, accumulated, truncated, error_msg)
    """
    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()
    SENTINEL = object()

    def produce():
        def _emit(item):
            try:
                loop.call_soon_threadsafe(q.put_nowait, item)
            except Exception:
                pass
        try:
            for chunk in make_stream():
                if not getattr(chunk, "choices", None):
                    continue
                ch = chunk.choices[0]
                delta = getattr(getattr(ch, "delta", None), "content", None)
                if delta:
                    _emit(("token", delta))
                fr = getattr(ch, "finish_reason", None)
                if fr is not None:
                    _emit(("finish", fr))
        except Exception as e:  # noqa: BLE001
            _emit(("error", str(e)))
        finally:
            _emit(("__end__", SENTINEL))

    frames = []
    frames.append(("progress", {"stage": "generating"}))
    loop.run_in_executor(None, produce)

    accumulated = []
    truncated = False
    error_msg = None
    while True:
        kind, val = await q.get()
        if kind == "token":
            accumulated.append(val)
            frames.append(("token", {"text": val}))
        elif kind == "finish":
            truncated = (val == "length")
        elif kind == "error":
            error_msg = val
        elif val is SENTINEL:
            break

    if error_msg is not None:
        frames.append(("error", {"error": f"LLM 생성 실패: {error_msg}"}))
    else:
        frames.append(("done", {"prompt": "".join(accumulated).strip(),
                                 "meta": {"truncated": truncated}}))
    return frames, "".join(accumulated), truncated, error_msg


def test_stream_accumulates_tokens_and_done():
    """정상 스트림: 토큰 누적 → done event, truncated=False."""
    frames, acc, truncated, err = asyncio.run(
        _consume(lambda: _fake_stream(["제품 ", "분석 ", "프롬프트"], finish_reason="stop"))
    )
    assert acc == "제품 분석 프롬프트"
    assert truncated is False
    assert err is None
    assert frames[0][0] == "progress"
    assert [f[0] for f in frames if f[0] == "token"] == ["token", "token", "token"]
    assert frames[-1][0] == "done"
    assert frames[-1][1]["prompt"] == "제품 분석 프롬프트"


def test_stream_truncated_on_length():
    """finish_reason='length' 면 done.meta.truncated=True."""
    frames, acc, truncated, err = asyncio.run(
        _consume(lambda: _fake_stream(["부분 본문"], finish_reason="length"))
    )
    assert truncated is True
    assert frames[-1][0] == "done"
    assert frames[-1][1]["meta"]["truncated"] is True


def test_stream_error_emits_error_event():
    """스트림 중 예외 → error event(부분 토큰은 누적되나 done 대신 error)."""
    frames, acc, truncated, err = asyncio.run(
        _consume(lambda: _fake_stream(["t0", "t1", "t2"], raise_at=1))
    )
    assert err is not None and "boom" in err
    assert frames[-1][0] == "error"
    assert "LLM 생성 실패" in frames[-1][1]["error"]
    # raise_at=1 → 첫 토큰(t0)만 누적된 뒤 예외.
    assert acc == "t0"
