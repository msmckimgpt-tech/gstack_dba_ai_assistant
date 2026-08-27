"""feature-0045 — 앱 측 브리지 배포 연속성 계약(in-flight 관측 + lame-duck drain).

여기서 지키는 것은 하나다: **배포가 진행되어도 개인 AI 와 주고받던 요청이 끊기지 않는다.**

그 하나를 두 종류로 나눠 다룬다 — 대기(끊겨도 잃을 게 없으므로 즉시 비운다)와 작업(끊기면
그 왕복이 버려지므로 끝날 때까지 기다린다). 이 파일의 테스트 대부분은 그 **구분**이 유지되는지를
본다. 둘을 같게 다루는 순간 배포가 영원히 못 끝나거나(대기를 기다림), 사용자의 질문이
중간에 죽는다(작업을 안 기다림).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "feature-0003-agent-web-ui" / "src"


def _load_drain():
    """`bridge_drain` 을 파일 경로로 직접 적재한다.

    `web` 패키지 전체를 import 하면 DB·설정 의존이 딸려와 이 계약과 무관한 이유로 깨진다.
    이 모듈은 stdlib 만 쓰므로 단독 적재가 가능하고, 그것이 곧 "게이트 판정이 다른 것에
    의존하지 않는다" 는 사실의 확인이기도 하다.
    """
    path = _SRC / "bridge_drain.py"
    spec = importlib.util.spec_from_file_location("bridge_drain_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def drain():
    mod = _load_drain()
    yield mod
    mod.end_drain()


# ── 관측: 두 종류를 **따로** 센다 ────────────────────────────────────────────

def test_waiters_and_tools_are_counted_separately(drain):
    """한 숫자로 합치면 배포가 판단할 수 없다.

    대기는 상시 존재하고(연결된 AI 는 늘 기다린다) 작업은 간헐적이다. 합쳐 놓으면 게이트는
    "항상 바쁨" 을 보고 매번 상한까지 기다리다 강행한다 — 관측을 붙인 의미가 사라진다.
    """
    assert drain.counts() == (0, 0)
    with drain.waiting():
        assert drain.counts() == (1, 0)
        with drain.tool_call():
            assert drain.counts() == (1, 1)
        assert drain.counts() == (1, 0)
    assert drain.counts() == (0, 0)


def test_counters_unwind_on_exception(drain):
    """예외로 빠져나가도 감소한다 — 안 그러면 한 번의 오류가 배포를 영구 차단한다."""
    with pytest.raises(RuntimeError):
        with drain.tool_call():
            raise RuntimeError("boom")
    assert drain.counts() == (0, 0)


def test_snapshot_exposes_both_axes_and_drain_state(drain):
    """`/livez` · `/readyz` · `/internal/bridge-drain` 이 **같은 함수**를 쓴다.

    세 창구가 각자 값을 조립하면 언제든 갈리고, 갈리는 순간 배포는 자기가 보는 쪽을 믿는다.
    """
    snap = drain.snapshot()
    assert snap["bridge_waiters"] == 0 and snap["bridge_inflight"] == 0
    assert snap["draining"] is False
    drain.begin_drain()
    assert drain.snapshot()["draining"] is True


# ── 드레인: 문을 닫되 손님은 내쫓지 않는다 ──────────────────────────────────

def test_begin_drain_is_idempotent(drain):
    """스파인이 폴링하며 반복 호출한다 — 두 번째 호출이 시작 시각을 리셋하면 안 된다."""
    drain.begin_drain()
    first = drain.snapshot().get("draining_for_sec")
    drain.begin_drain()
    second = drain.snapshot().get("draining_for_sec")
    assert first is not None and second is not None and second >= first


def test_end_drain_restores_service(drain):
    """되돌릴 수 없으면, 배포가 replica 를 못 내리고 중단했을 때 그 replica 는 문이 닫힌 채로
    남는다. 상대까지 교체하려 드는 순간 available upstream 이 0 이다."""
    drain.begin_drain()
    assert drain.is_draining() is True
    drain.end_drain()
    assert drain.is_draining() is False
    assert "draining_for_sec" not in drain.snapshot()


# ── 미들웨어: 신규만 돌려보낸다 ──────────────────────────────────────────────

class _Recorder:
    """ASGI 하위 앱 대역. 호출 여부와 그 시점의 카운터를 기록한다."""

    def __init__(self, drain_mod):
        self.calls = 0
        self.seen_counts = None
        self._drain = drain_mod

    async def __call__(self, scope, receive, send):
        self.calls += 1
        self.seen_counts = self._drain.counts()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})


async def _drive(app, path):
    sent = []

    async def send(msg):
        sent.append(msg)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    await app({"type": "http", "path": path, "method": "POST"}, receive, send)
    return sent


def _run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


def test_tool_calls_are_counted_while_in_flight(drain):
    """계상은 **핸들러가 도는 동안** 유효해야 한다 — 끝난 뒤에 세면 게이트가 볼 것이 없다."""
    inner = _Recorder(drain)
    app = drain.BridgeInflightMiddleware(inner)
    _run(_drive(app, "/api/ai/tools/execute_sql"))
    assert inner.calls == 1
    assert inner.seen_counts == (0, 1), "핸들러 실행 중 in-flight 가 1 이 아니다"
    assert drain.counts() == (0, 0), "끝난 뒤에도 남아 있으면 배포가 영원히 기다린다"


def test_wait_path_is_not_counted_as_work(drain):
    """대기를 작업으로 세면 **배포가 영원히 못 간다** — 연결된 AI 는 늘 대기 중이기 때문이다."""
    inner = _Recorder(drain)
    app = drain.BridgeInflightMiddleware(inner)
    _run(_drive(app, drain.WAIT_PATH))
    assert inner.seen_counts == (0, 0)


def test_non_tool_paths_are_untouched(drain):
    """대화·정적 자산 등 나머지 트래픽은 이 게이트의 관할이 아니다."""
    inner = _Recorder(drain)
    app = drain.BridgeInflightMiddleware(inner)
    _run(_drive(app, "/api/ask"))
    assert inner.calls == 1 and inner.seen_counts == (0, 0)


def test_draining_turns_away_new_tool_calls_with_a_routable_signal(drain):
    """드레인 중 **신규** 도구 호출은 503 + `X-Bridge-Draining` 으로 돌려보낸다.

    MCP 어댑터는 엣지를 거치지 않고 `web-a` → `web-b` 순서로 직결한다. 이 신호가 없으면
    어댑터는 드레인된 replica 를 계속 붙잡고, `bridge_inflight` 가 0 이 되지 않아 배포가
    상한까지 기다리다 강행한다 — 무중단을 위해 만든 장치가 정확히 반대로 작동한다.
    """
    inner = _Recorder(drain)
    app = drain.BridgeInflightMiddleware(inner)
    drain.begin_drain()
    sent = _run(_drive(app, "/api/ai/tools/execute_sql"))
    assert inner.calls == 0, "드레인 중인데 신규 호출이 핸들러까지 갔다"
    start = sent[0]
    assert start["status"] == 503
    headers = {k.decode(): v.decode() for k, v in start["headers"]}
    assert headers.get("x-bridge-draining") == "1", (
        "재라우팅 신호가 없으면 호출측이 이것을 장애로 읽고 백오프에 들어간다")
    assert drain.counts() == (0, 0), "돌려보낸 요청을 in-flight 로 세면 배포가 스스로를 막는다"


def test_draining_turns_away_the_wait_path_too(drain):
    """대기 경로도 **503 + 재라우팅 헤더**다 (적대 리뷰 P1 반영).

    초판은 여기서 200(`draining: true`)을 돌려줬다. 그런데 MCP 어댑터의 재라우팅 조건은
    503 + 헤더이고 200 은 성공이므로, 어댑터는 드레인된 replica(`web-a`)를 **드레인 내내
    붙잡고** 매 호출마다 상한 조회 + 원장 기록을 태우며 질문을 인지하지 못했다.

    이미 붙들려 있던 롱폴은 이 미들웨어를 지난 뒤이므로 라우터의 정상 종료로 완주한다 —
    그 경로는 `ai_tools.wait_for_request` 가 담당하고 여기서 막지 않는다.
    """
    inner = _Recorder(drain)
    app = drain.BridgeInflightMiddleware(inner)
    drain.begin_drain()
    sent = _run(_drive(app, drain.WAIT_PATH))
    assert inner.calls == 0, "드레인 중 신규 대기 요청이 라우터까지 갔다"
    assert sent[0]["status"] == 503
    headers = {k.decode(): v.decode() for k, v in sent[0]["headers"]}
    assert headers.get("x-bridge-draining") == "1"


@pytest.mark.parametrize("path", sorted(_load_drain().DRAIN_EXEMPT_PATHS))
def test_draining_still_accepts_the_last_step(drain, path):
    """제출·첨부 읽기는 드레인 중에도 받는다 (적대 리뷰 P2 반영).

    `submit_answer` 는 이미 이 replica 에서 조사를 마친 AI 의 **마지막 한 걸음**이다. 503 을
    내면 러너는 재시도 없이 답변을 버리고(`handle_one` 은 로그만 남긴다) 사용자 화면은
    "조사·작성 중" 에서 lease 만료까지 멈춘다. 중복 제출은 `SubmittedAt IS NULL` 가드가 막는다.
    """
    inner = _Recorder(drain)
    app = drain.BridgeInflightMiddleware(inner)
    drain.begin_drain()
    sent = _run(_drive(app, path))
    assert inner.calls == 1, f"{path} 가 드레인 중 거절됐다 — 끝난 작업이 버려진다"
    assert sent[0]["status"] == 200
