"""web HTTP per-route 타이밍 계측 (feature-0026-perf-observability, M1).

계측 사각지대 B1(HTTP per-route 레이턴시 전무)·B9(요청당 DB 커넥션 무관측)를 메우는
in-process 집계기 + 순수 ASGI 미들웨어. 저장소는 프로세스 메모리뿐 — DB/파일 쓰기 0.

  - `PerfTimingMiddleware`: 요청 지연(perf_counter_ns)·상태코드·요청당 MySQL/PG 커넥션 수
    (shared.perf_counters 컨텍스트)를 route template 단위로 집계. 순수 ASGI 래퍼 —
    BaseHTTPMiddleware 를 쓰지 않아 스트리밍(SSE/long-poll) 응답에 간섭하지 않는다.
  - `snapshot()`: `GET /api/admin/perf/http` (routers/admin_perf.py) 의 데이터 소스.
  - 주기 flush: `WEB_PERF_LOG_INTERVAL_SEC`(기본 300, 0=off)마다 상위 route 요약 1줄을
    stdout `[perf-http]` 로 남긴다 — 프로세스 밖(docker logs)에서 스크레이프 가능
    (bin/perf-snapshot.sh 소비).

설계 제약: 전 구간 fail-open (계측 예외가 요청 처리에 전파되지 않는다). route 카디널리티는
template 경로로 유계 — 미매칭(404 등)은 "(unmatched)" 로 묶는다. p50/p95 는 고정 로그 버킷
경계 보간(오차 ≤ 버킷 폭) — 요청당 오버헤드를 상수로 유지하기 위한 의도된 트레이드오프.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any

from shared import perf_counters

# 지연 히스토그램 버킷 상한 (ms). 마지막 버킷 초과분은 마지막 경계값으로 포화(saturate) —
# §18.8 패널 F-1: +inf 반환은 JSONResponse(allow_nan=False) 직렬화를 500 으로 죽인다.
# long-poll(/api/ask attach 등)의 수백 초 wall time 을 판독하도록 상한을 600s 까지 확장.
BUCKET_BOUNDS_MS = (1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000,
                    10000, 30000, 60000, 120000, 300000, 600000)

_LOCK = threading.Lock()
_STATS: dict[tuple[str, str], dict[str, Any]] = {}
# §18.8 sec C2: 느린 요청 51건이면 이전 샘플이 전부 밀린다(관측 부인) — 200 으로 확대.
# 여전히 축출 가능한 진단 보조이지 증적이 아니다(증적 정본 = audit/uvicorn/Caddy 로그).
_SLOW_RING: deque = deque(maxlen=200)
_STARTED_AT = time.time()
_FLUSH_THREAD_STARTED = False

SLOW_SAMPLE_MS = 1000  # slow ring 채집 임계

# §18.8 sec C1: method 축은 요청 라인 원문 토큰(비인증 입력) — 화이트리스트로 정규화하고
# _STATS 키 수에 하드 상한을 둬 비인증 트래픽의 무제한 메모리 증가를 코드로 차단한다
# (httptools 파서의 method allowlist 는 배포 우연이지 코드 보장이 아님).
_KNOWN_METHODS = frozenset(("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"))
_STATS_MAX_KEYS = 2000
_OVERFLOW_KEY = ("(other)", "(overflow)")


# Mount(예: /static) 는 scope["route"] 를 세팅하지 않는다(§18.8 C-1) — 고정 prefix 그룹으로
# 분리해 고QPS static 트래픽과 404 노이즈가 "(unmatched)" 한 행에 합산되는 판독 불능을 막는다.
MOUNT_GROUPS = (("/static/", "/static/*"),)


def _new_stat() -> dict[str, Any]:
    return {
        "count": 0,
        "error_count": 0,   # status >= 500
        "aborted_count": 0,  # status 미기록 완료(클라 중단·상위 예외 경로 — §18.8 C-2 과소집계 방지)
        "sum_ms": 0.0,
        "max_ms": 0.0,
        "buckets": [0] * (len(BUCKET_BOUNDS_MS) + 1),
        "mysql_conns": 0,
        "pg_conns": 0,
        "pg_ro_conns": 0,
    }


def _bucket_index(ms: float) -> int:
    for i, bound in enumerate(BUCKET_BOUNDS_MS):
        if ms <= bound:
            return i
    return len(BUCKET_BOUNDS_MS)


def record(method: str, route: str, status: int, ms: float, counters: dict | None) -> None:
    """요청 1건 집계. 예외 무전파 (fail-open)."""
    try:
        m = str(method or "?")
        if m not in _KNOWN_METHODS:
            m = "(other)"  # §18.8 sec C1: 원문 method 토큰 유입 차단
        key = (m, str(route or "(unmatched)"))
        with _LOCK:
            st = _STATS.get(key)
            if st is None:
                if len(_STATS) >= _STATS_MAX_KEYS:
                    key = _OVERFLOW_KEY  # §18.8 sec C1: 키 공간 하드 상한
                    st = _STATS.get(key)
                if st is None:
                    st = _STATS[key] = _new_stat()
            st["count"] += 1
            if int(status or 0) >= 500:
                st["error_count"] += 1
            elif int(status or 0) == 0:
                st["aborted_count"] += 1
            st["sum_ms"] += ms
            if ms > st["max_ms"]:
                st["max_ms"] = ms
            st["buckets"][_bucket_index(ms)] += 1
            if counters:
                for k in perf_counters.KEYS:
                    st[k] = st.get(k, 0) + int(counters.get(k, 0) or 0)
        if ms >= SLOW_SAMPLE_MS:
            _SLOW_RING.append({
                "ts": round(time.time(), 3),
                "method": key[0],
                "route": key[1],
                "status": int(status or 0),
                "ms": round(ms, 1),
                **{k: int((counters or {}).get(k, 0) or 0) for k in perf_counters.KEYS},
            })
    except Exception:
        pass


def _percentile_from_buckets(buckets: list[int], q: float) -> float | None:
    """버킷 경계 보간 percentile (상한값 반환 — 보수적).

    §18.8 F-1: 오버플로 버킷(마지막 경계 초과)은 +inf 가 아니라 **마지막 경계값으로 포화**해
    항상 유한값을 반환한다 — JSON 직렬화(allow_nan=False) 안전. 포화 여부는 값 == 마지막
    경계로 식별 가능(필드명 *_le 의 상한 의미는 포화 시 "≥" 로 읽는다 — snapshot 문서화).
    """
    total = sum(buckets)
    if total <= 0:
        return None
    rank = q * total
    cum = 0
    for i, c in enumerate(buckets):
        cum += c
        if cum >= rank:
            return float(BUCKET_BOUNDS_MS[min(i, len(BUCKET_BOUNDS_MS) - 1)])
    return float(BUCKET_BOUNDS_MS[-1])


def snapshot(top: int = 50) -> dict[str, Any]:
    """집계 스냅샷 — admin 엔드포인트/주기 flush 공용. 누적 시간(sum_ms) 내림차순."""
    rows = []
    with _LOCK:
        items = [(k, dict(v, buckets=list(v["buckets"]))) for k, v in _STATS.items()]
        slow = list(_SLOW_RING)  # §18.8 qa-경미: 동시 append 중 무락 순회 RuntimeError 방지
    for (method, route), st in items:
        p50 = _percentile_from_buckets(st["buckets"], 0.50)
        p95 = _percentile_from_buckets(st["buckets"], 0.95)
        cnt = st["count"] or 1
        rows.append({
            "method": method,
            "route": route,
            "count": st["count"],
            "error_count": st["error_count"],
            "aborted_count": st.get("aborted_count", 0),
            "avg_ms": round(st["sum_ms"] / cnt, 1),
            "p50_ms_le": p50,
            "p95_ms_le": p95,
            "max_ms": round(st["max_ms"], 1),
            "sum_ms": round(st["sum_ms"], 1),
            "db_per_req": {
                k: round(st.get(k, 0) / cnt, 2) for k in perf_counters.KEYS
            },
        })
    rows.sort(key=lambda r: r["sum_ms"], reverse=True)
    return {
        "started_at": _STARTED_AT,
        "uptime_sec": round(time.time() - _STARTED_AT, 1),
        "routes": rows[: max(1, int(top))],
        "route_count": len(rows),
        "slow_samples": slow,
        "bucket_bounds_ms": list(BUCKET_BOUNDS_MS),
    }


def _flush_loop(interval: int) -> None:
    import json as _json
    while True:
        time.sleep(interval)
        try:
            snap = snapshot(top=10)
            line = {
                "uptime_sec": snap["uptime_sec"],
                "route_count": snap["route_count"],
                "top": [
                    {k: r[k] for k in ("method", "route", "count", "avg_ms", "p95_ms_le", "sum_ms")}
                    for r in snap["routes"]
                ],
            }
            print("[perf-http] " + _json.dumps(line, ensure_ascii=False), flush=True)
        except Exception:
            pass


def start_flush_thread() -> None:
    """주기 로그 flush 데몬 기동 (멱등). WEB_PERF_LOG_INTERVAL_SEC=0 이면 미기동."""
    global _FLUSH_THREAD_STARTED
    if _FLUSH_THREAD_STARTED:
        return
    try:
        interval = int(os.getenv("WEB_PERF_LOG_INTERVAL_SEC", "300") or "300")
    except Exception:
        interval = 300
    if interval <= 0:
        return
    _FLUSH_THREAD_STARTED = True
    threading.Thread(target=_flush_loop, args=(max(30, interval),),
                     name="web-perf-flush", daemon=True).start()


class PerfTimingMiddleware:
    """순수 ASGI 타이밍 래퍼 — http 스코프만 계측, 그 외(lifespan/websocket)는 투명 통과."""

    def __init__(self, app):
        self.app = app
        start_flush_thread()

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        t0 = time.perf_counter_ns()
        counters, token = perf_counters.activate()
        status_holder = [0]

        async def send_wrapper(message):
            try:  # §18.8 C-2: status 추출 실패가 응답 경로로 전파되지 않게 (fail-open 완결)
                if message.get("type") == "http.response.start":
                    status_holder[0] = int(message.get("status", 0) or 0)
            except Exception:
                pass
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                # §18.8 B1: unhandled 예외 500 은 ServerErrorMiddleware(본 미들웨어 바깥)가
                # 응답을 만들어 send_wrapper 를 통과하지 않는다 — 여기서 500 으로 계상하고
                # 전파 동작은 불변(re-raise).
                if status_holder[0] == 0:
                    status_holder[0] = 500
                raise
        finally:
            perf_counters.deactivate(token)
            try:
                ms = (time.perf_counter_ns() - t0) / 1_000_000
                route_obj = scope.get("route")
                route_path = getattr(route_obj, "path", None)
                if not route_path:
                    # Mount(/static)는 route 미세팅(§18.8 C-1) — 고정 prefix 그룹으로 분리.
                    raw = str(scope.get("path", "") or "")
                    for prefix, group in MOUNT_GROUPS:
                        if raw.startswith(prefix):
                            route_path = group
                            break
                    else:
                        # 미매칭(404) — 원시 경로 카디널리티 폭주(+URL 비밀 잔류) 방지 위해 묶음.
                        route_path = "(unmatched)"
                record(scope.get("method", "?"), route_path, status_holder[0], ms, counters)
            except Exception:
                pass
