"""브리지 축(개인 AI ↔ 웹)의 배포 연속성 — in-flight 관측 + lame-duck drain.

feature-0045-zd-bridge-continuity.

## 왜 필요한가

무중단 스파인(`bin/deploy-web.sh`)의 pre-drain 게이트는 `/livez` 의 `active_streams` 만
본다. 그 카운터는 SSE 프롬프트 자동작성과 CSV export **두 곳에서만** 증감한다
(`_prompt_context.py` · `admin_audits.py`). 개인 AI 가 붙들고 있는 55초 블로킹 대기
(`wait_for_request`)도, 그 AI 가 조사 중인 도구 호출(`execute_sql` 등)도 세지 않는다.

즉 브리지로 요청을 주고받는 **바로 그 중에도** 게이트는 "조용함(0)" 으로 읽고 replica 를
내린다. 무중단은 HTTP 단발 요청 축에서만 성립했고, 브리지 축은 그 보호 밖에 있었다.

## 두 종류를 다르게 다룬다

| | 대기(waiter) | 작업(tool call) |
|---|---|---|
| 무엇 | `wait_for_request` 로 질문을 기다리는 중 | 개인 AI 가 조사 중인 도구 호출 |
| 끊기면 | 잃는 것이 없다(다시 부르면 된다) | **그 왕복이 버려진다** |
| 배포 시 | 드레인 신호로 **즉시 비운다**(기다리지 않는다) | **끝날 때까지 기다린다** |

대기를 기다리면 배포가 매번 최대 55초 늦어지고, 연결된 AI 가 여럿이면 그 지연이 겹친다.
반대로 작업을 안 기다리면 사용자가 던진 질문의 조사가 중간에 죽는다 — 그리고 러너는
"실패했다" 는 답변을 제출하므로, 사용자에게는 **틀린 답이 도착한 것**으로 보인다.

## 드레인의 실체

`begin_drain()` 이 켜지면 이 replica 는 **lame-duck** 이 된다:

1. `/livez` 가 503 → Caddy active health(`health_interval 2s` · `health_fails 1`)가
   2초 안에 이 replica 를 LB 후보에서 제외한다 → **신규 요청 유입이 멈춘다**.
2. 대기 중인 롱폴이 즉시 `timed_out: true` 로 정상 반환한다 → 클라이언트가 곧바로 다시
   부르면 남은 replica 가 받는다(오류가 아니므로 러너의 재시도 경로를 타지 않는다).
3. 진행 중인 도구 호출은 **그대로 완주**한다. 드레인은 문을 닫는 것이지 손님을 내쫓는
   것이 아니다.

상태는 **프로세스 로컬**이다 — recreate 되면 새 프로세스에서 자동으로 꺼진다. 파일이나
DB 에 두면 배포가 중단됐을 때 그 흔적이 남아 replica 가 영원히 lame-duck 이 된다.
"""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

#: 대기 중인 블로킹 롱폴 수(`wait_for_request`). 드레인 신호로 즉시 0 이 된다.
_WAITERS = 0
#: 진행 중인 브리지 도구 호출 수. 이것이 0 이 될 때까지 배포가 기다린다.
_TOOLS = 0
_LOCK = threading.Lock()

#: 드레인 상태. 프로세스 로컬 — recreate 되면 사라진다(그래야 한다).
_DRAINING = False
#: 드레인 시작 시각(`time.time()`). 스파인 로그·진단에서 "언제부터 문을 닫았나" 를 본다.
_DRAIN_STARTED_AT = 0.0

#: 이 경로는 **작업이 아니라 대기**다. 미들웨어가 in-flight 로 세면 배포가 영원히 못 간다
#: (대기는 상시 존재한다). 대기 카운트는 라우터가 `waiting()` 으로 직접 한다.
WAIT_PATH = "/api/ai/tools/wait_for_request"
#: 브리지 도구 표면의 경로 접두. 이 아래의 호출이 곧 "개인 AI 가 조사 중" 이다.
TOOLS_PREFIX = "/api/ai/tools/"
#: 드레인 중에도 **받아 주는** 경로. 조사를 마친 AI 의 마무리 단계라, 여기서 돌려보내면
#: 이미 끝난 작업이 버려진다(러너는 제출 실패를 재시도하지 않는다). 중복 제출은
#: `SubmittedAt IS NULL` 가드가 막으므로 받는 편이 안전하다.
DRAIN_EXEMPT_PATHS = frozenset({
    "/api/ai/tools/submit_answer",
    "/api/ai/tools/read_task_attachment",
})


@contextmanager
def waiting() -> Iterator[None]:
    """블로킹 대기 1건을 계상한다. 예외로 빠져나가도 반드시 감소한다."""
    global _WAITERS
    with _LOCK:
        _WAITERS += 1
    try:
        yield
    finally:
        with _LOCK:
            _WAITERS = max(0, _WAITERS - 1)


@contextmanager
def tool_call() -> Iterator[None]:
    """브리지 도구 호출 1건을 계상한다. 이 값이 0 이 될 때까지 배포가 기다린다."""
    global _TOOLS
    with _LOCK:
        _TOOLS += 1
    try:
        yield
    finally:
        with _LOCK:
            _TOOLS = max(0, _TOOLS - 1)


def is_draining() -> bool:
    return _DRAINING


def begin_drain() -> None:
    """이 replica 를 lame-duck 으로 만든다. **멱등** — 스파인이 폴링하며 반복 호출한다."""
    global _DRAINING, _DRAIN_STARTED_AT
    with _LOCK:
        if not _DRAINING:
            _DRAINING = True
            _DRAIN_STARTED_AT = time.time()


def end_drain() -> None:
    """드레인을 되돌린다.

    배포가 **replica 를 내리지 못하고 중단**했을 때 필요하다 — 그대로 두면 이 replica 는
    문을 닫은 채로 계속 살아 있고(LB 후보 제외), 상대까지 내려가면 전면 다운이 된다.
    """
    global _DRAINING, _DRAIN_STARTED_AT
    with _LOCK:
        _DRAINING = False
        _DRAIN_STARTED_AT = 0.0


def snapshot() -> dict[str, Any]:
    """현재 상태. `/livez` · `/readyz` · `/internal/bridge-drain` 이 **같은 값**을 쓴다."""
    with _LOCK:
        waiters, tools, draining, started = _WAITERS, _TOOLS, _DRAINING, _DRAIN_STARTED_AT
    out: dict[str, Any] = {
        "bridge_waiters": waiters,
        "bridge_inflight": tools,
        "draining": draining,
    }
    if draining and started:
        out["draining_for_sec"] = round(time.time() - started, 1)
    return out


def counts() -> tuple[int, int]:
    """(대기, 작업) — 게이트 판정에 쓰는 최소 형태."""
    with _LOCK:
        return _WAITERS, _TOOLS


#: 드레인 중 신규 도구 호출에 돌려주는 본문. 호출측(MCP 어댑터·러너)이 **다음 replica 로
#: 넘어가도록** 유도하는 신호다 — 장애가 아니라 교대라는 사실을 말한다.
_DRAINING_BODY = json.dumps(
    {"error": "draining",
     "detail": "이 서버 인스턴스가 배포 교대 중입니다. 곧바로 다시 시도하면 "
               "다른 인스턴스가 처리합니다."},
    ensure_ascii=False).encode("utf-8")


class BridgeInflightMiddleware:
    """`/api/ai/tools/*` 호출을 in-flight 로 계상하고, 드레인 중이면 **신규만** 돌려보낸다.

    **fail-open** — 계측이 요청 처리에 영향을 주지 않는다(`PerfTimingMiddleware` 와 같은 자세).

    미들웨어로 두는 이유: 도구 엔드포인트는 여럿이고 앞으로도 늘어난다. 각 핸들러에
    카운팅을 흩뿌리면 **새로 추가된 도구가 조용히 게이트 밖에 남는다** — 그 종류의 누락은
    "무중단인 줄 알았는데 아닌" 상태를 만들고, 아무도 알아채지 못한다.

    ## 드레인 중 신규 요청을 왜 여기서 막는가

    엣지(Caddy)는 `/livez` 503 을 보고 이 replica 를 후보에서 빼므로 **브라우저 트래픽은
    저절로 옮겨간다.** 그러나 MCP 어댑터(`ext-tool-mcp`)는 엣지를 거치지 않고 `web-a` →
    `web-b` 순서로 **직결**한다. 그래서 아무 것도 하지 않으면 드레인된 replica 로 새 도구
    호출이 계속 들어오고, `bridge_inflight` 가 영영 0 이 되지 않아 배포가 상한까지 기다리다
    강행한다 — 정확히 막으려던 그 결과다.

    503 은 **신규 요청에만** 적용된다. 이미 진행 중인 호출은 이 미들웨어를 지나간 뒤이므로
    영향을 받지 않고 완주한다. 문을 닫는 것이지 손님을 내쫓는 것이 아니다.

    ## 대기 경로도 503 이다 (적대 리뷰 P1)

    초판은 `wait_for_request` 를 503 대상에서 빼고 200(`draining: true`)으로 돌려줬다. 그런데
    어댑터의 재라우팅 조건은 **503 + 이 헤더**다 — 200 은 성공이므로 다음 후보로 넘어가지
    않는다. 그 결과 어댑터는 목록의 첫 replica(`web-a`)를 드레인 내내 붙잡고, 매 호출이 상한
    조회 + 원장 기록을 태우며 **질문을 인지하지 못한 채** 루프를 돌았다.

    그래서 **계상 제외**(대기를 작업으로 세면 배포가 영영 못 간다)와 **드레인 응답**을 분리해,
    대기 경로도 503 으로 돌려보낸다. 이미 붙들려 있던 롱폴은 이 미들웨어를 지난 뒤이므로
    라우터의 정상 종료(200 `draining: true`)로 완주한다 — 두 경로는 충돌하지 않는다.

    ## 제출은 돌려보내지 않는다 (적대 리뷰 P2)

    `submit_answer` 는 이미 이 replica 에서 조사를 마친 AI 의 **마지막 한 걸음**이다. 여기서
    503 을 내면 러너는 재시도 없이 답변을 버리고(`bridge_agent.handle_one` 은 제출 실패를
    로그만 남긴다), 사용자 화면은 "조사·작성 중" 에서 lease 만료까지 멈춘다. 중복 제출은
    `SubmittedAt IS NULL` 가드가 이미 막으므로 받아 주는 편이 안전하다 — 문을 닫아도
    **나가는 손님은 보낸다**. 같은 이유로 첨부 읽기도 면제한다(제출 직전 마무리 조사다).
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if not path.startswith(TOOLS_PREFIX):
            await self.app(scope, receive, send)
            return
        if is_draining() and path not in DRAIN_EXEMPT_PATHS:
            await send({"type": "http.response.start", "status": 503,
                        "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                    (b"x-bridge-draining", b"1"),
                                    (b"retry-after", b"1")]})
            await send({"type": "http.response.body", "body": _DRAINING_BODY})
            return
        if path == WAIT_PATH:
            # 대기는 **작업이 아니다.** 세면 연결된 AI 가 있는 한 배포가 영영 못 간다.
            await self.app(scope, receive, send)
            return
        with tool_call():
            await self.app(scope, receive, send)
