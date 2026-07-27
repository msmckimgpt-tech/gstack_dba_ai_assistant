"""요청-스코프 DB 커넥션 카운터 (feature-0026-perf-observability).

web HTTP 타이밍 미들웨어(feature-0003 `perf_metrics.PerfTimingMiddleware`)가 요청 진입 시
`activate()` 로 컨텍스트를 열고, 커넥션 수립 지점(shared/db `_pg_connect`/`_pg_connect_ro`,
web `app._connect_memory`)이 `incr()` 로 센다. 컨텍스트 밖(워커·CLI·배치)에서는 `incr()` 가
no-op — 오버헤드는 ContextVar get 1회다.

설계 제약 (FUNCTION.md §8/§9):
  - fail-open: 어떤 예외도 호출자에게 전파하지 않는다 (계측이 요청을 죽이면 본말전도).
  - dict 참조 공유: anyio threadpool 로 넘어간 sync 핸들러도 contextvars 복사본이 같은
    dict 객체를 가리키므로 증분이 미들웨어 쪽 스냅샷에 반영된다.
"""
from __future__ import annotations

import contextvars

_CTX: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "perf_db_counters", default=None
)

#: incr 가 인식하는 카운터 키 (신규 키는 여기와 perf_metrics 스냅샷 렌더에 함께 추가)
KEYS = ("mysql_conns", "pg_conns", "pg_ro_conns")


def activate() -> tuple[dict, contextvars.Token]:
    """요청 시작 — 새 카운터 dict 를 컨텍스트에 심고 (dict, reset token) 을 돌려준다."""
    counters = {k: 0 for k in KEYS}
    token = _CTX.set(counters)
    return counters, token


def deactivate(token: contextvars.Token) -> None:
    """요청 종료 — 컨텍스트 복원 (미들웨어 finally 에서 호출)."""
    try:
        _CTX.reset(token)
    except Exception:
        pass


def incr(key: str, n: int = 1) -> None:
    """활성 컨텍스트가 있으면 카운터 증가, 없으면 no-op. 예외 무전파."""
    try:
        counters = _CTX.get()
        if counters is not None:
            counters[key] = counters.get(key, 0) + n
    except Exception:
        pass


def current() -> dict | None:
    """활성 카운터 dict (없으면 None). 테스트·디버그용."""
    try:
        return _CTX.get()
    except Exception:
        return None
