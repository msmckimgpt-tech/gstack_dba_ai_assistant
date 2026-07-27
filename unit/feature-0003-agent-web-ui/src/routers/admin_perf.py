"""admin/perf 도메인 APIRouter (web HTTP 성능 계측 스냅샷 조회 — feature-0026-perf-observability).

URL: /api/admin/perf/http (1 route). RBAC: require_permission console.aiops.read
(admin 전용 — AI 운영 관제와 동일 관측 등급, 신규 권한 0). **읽기 전용** —
프로세스 메모리 집계(perf_metrics) 스냅샷만 반환, DB 접근 0·파괴적 쓰기 0.
INCLUDE_ORDER=250 — admin_reasoning(240) 뒤, 신규 관측 라우터 대역.

소유 feature: feature-0026-perf-observability (M1). 데이터 소스 = `perf_metrics.snapshot()`
(PerfTimingMiddleware 가 집계하는 route 단위 count/p50/p95/max/error + 요청당 DB 커넥션 수).
replica(web-a/web-b) 별 독립 집계 — 응답은 이 replica 프로세스의 값이다 (`replica` 필드로 식별).
관련 문서: docs/ROUTEMAP.md · unit/feature-0026-perf-observability/docs/FUNCTION.md AC-1.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

import app
import perf_metrics

INCLUDE_ORDER = 250  # 신규 관측 라우터 — admin_reasoning(240) 뒤 (등록 순서 고정)
router = APIRouter()


@router.get("/api/admin/perf/http")
def admin_perf_http(
    request: Request,
    top: int = 50,
    account=Depends(app.require_permission("console.aiops.read", message="AI 운영 현황 조회 권한이 필요합니다 (운영자 전용).")),
) -> JSONResponse:
    """web HTTP per-route 성능 스냅샷 (이 replica 프로세스 기동 이후 누적).

    routes[]: sum_ms 내림차순 — count/error_count/avg/p50(≤)/p95(≤)/max + 요청당 DB 커넥션.
    slow_samples[]: 최근 1s+ 요청 링버퍼(50). 집계는 in-process 메모리 — 재기동 시 리셋.
    """
    snap = perf_metrics.snapshot(top=max(1, min(200, int(top or 50))))
    return JSONResponse({
        "ok": True,
        "replica": os.getenv("HOSTNAME", "") or "",
        **snap,
    })
