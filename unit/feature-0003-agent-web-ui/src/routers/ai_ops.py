"""routers/ai_ops.py — AI 운영 관제 패널 API (TASK-AIOPS).

관리 콘솔 > 감사 > AI 운영 현황 탭의 데이터 소스. `GET /api/admin/ai-ops`.
권한: `console.aiops.read` (admin 전용). **읽기 전용** — 파괴적 쓰기 없음.

설계:
  - 상태 축(worst-of 롤업): provider / ask-worker / insight-worker / datasource-scan.
    ask-worker 는 `_is_worker_mode()==False`(inprocess)면 **N/A** 로 롤업에서 제외
    (정상 inprocess 배포를 '중단'으로 오판 방지 — heartbeat 부재가 정상이므로).
  - 배너 = 축 worst-of. + KPI / Attention / 최근 활동 feed / 카테고리 드릴다운 / 계측 커버리지.
  - PG(agent_runtime) 집계는 **부분 degrade** — PG 미가용도 200 반환, PG 의존 지표만 unknown/빈값.
    admin_usage 의 503-전체실패 패턴을 쓰지 않는다(MySQL/heartbeat 기반 배너는 살아남음).
  - PG read 는 `_pg_connect_ro`(least-privilege). `llm_usage.latency_ms` 컬럼 부재(마이그 전)도
    쿼리별 try/except 로 삼켜 부분 degrade.
  - uniform `import app` + `app.X` 동적 접근(테스트 monkeypatch 보존, admin_usage 패턴). DI seam
    (require_permission/get_conn)도 `Depends(app.X)` — app 정본과 동일 객체(dependency_overrides 정합).

순환 안전: app 정의 후 맨 끝 include_router.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

router = APIRouter()

_log = logging.getLogger(__name__)

# 상태 severity — worst-of 롤업용(높을수록 나쁨). "na"(해당없음)는 롤업에서 제외.
_SEV = {"ok": 0, "unknown": 1, "degraded": 2, "down": 3}
_SEV_LABEL = {"ok": "정상", "unknown": "부분 가시", "degraded": "저하", "down": "중단", "na": "해당 없음"}


# ── 상태 축 ─────────────────────────────────────────────────────────────────────
def _provider_axis() -> dict:
    """LLM provider 외부요인 제한 상태(PG agent_runtime.llm_provider_health cheap read)."""
    try:
        st = str((app._read_llm_provider_status() or {}).get("state") or "unknown").lower()
    except Exception:
        st = "unknown"
    if st == "ok":
        state = "ok"
    elif st in ("down", "error", "unavailable"):
        state = "down"
    elif st == "unknown":
        state = "unknown"
    else:  # restricted / throttled / credential_expired 등
        state = "degraded"
    return {"key": "provider", "label": "LLM 제공자", "state": state, "detail": f"state={st}"}


def _ask_worker_axis(conn) -> dict:
    """요청 처리(ask) 워커 heartbeat. inprocess 모드면 N/A(롤업 제외).
    임계: age≤60s 정상 / 60<age≤120s 저하 / >120s·부재 중단 (WEB_ASK_WORKER_READY_MAX_AGE_SEC=60 정합)."""
    try:
        worker_mode = bool(app._is_worker_mode())
    except Exception:
        worker_mode = False
    if not worker_mode:
        return {"key": "ask_worker", "label": "요청 처리 워커", "state": "na",
                "detail": "inprocess 모드 (별도 워커 미사용)", "age_sec": None}
    try:
        age = app._ask_worker_age_sec(conn)
    except Exception:
        age = None
    if age is None:
        return {"key": "ask_worker", "label": "요청 처리 워커", "state": "down",
                "detail": "heartbeat 없음", "age_sec": None}
    if age <= 60:
        state = "ok"
    elif age <= 120:
        state = "degraded"
    else:
        state = "down"
    return {"key": "ask_worker", "label": "요청 처리 워커", "state": state,
            "detail": f"heartbeat {int(age)}s 전", "age_sec": int(age)}


def _insight_worker_axis(conn) -> dict:
    """insight 워커 heartbeat. 임계: alive(status ok/skip_locked & age≤max(30,STALE)) 정상 /
    age≤60s 저하 / 그 외·부재 중단. (_insight_worker_liveness 반환 재사용)."""
    try:
        liv = app._insight_worker_liveness(conn) or {}
    except Exception:
        liv = {}
    age = liv.get("age_sec")
    status = str(liv.get("status") or "")
    if liv.get("alive"):
        state = "ok"
    elif age is None:
        state = "down"
    elif age <= 60:
        state = "degraded"
    else:
        state = "down"
    detail = (f"status={status or '?'}" +
              (f", {int(age)}s 전" if age is not None else ", heartbeat 없음"))
    return {"key": "insight_worker", "label": "인사이트 워커", "state": state, "detail": detail,
            "age_sec": (int(age) if age is not None else None)}


def _datasource_axis() -> dict:
    """insight 스캔 관점 datasource health(PG agent_runtime.datasource_health) worst-of.
    매핑: ok→정상 / unstable·degraded·error·partial→저하 / circuit_open·perm_failed·failed→중단.
    스캔 이력 없음/PG 미가용({})은 unknown(부분 가시)."""
    try:
        health = app._read_insight_datasource_health() or {}
    except Exception:
        health = {}
    if not health:
        return {"key": "datasource", "label": "데이터소스 스캔", "state": "unknown",
                "detail": "스캔 상태 미가용", "scopes": 0}
    worst = "ok"
    deg = 0
    down = 0
    for _scope, h in health.items():
        st = str(h.get("status") or "").lower()
        outcome = str(h.get("scan_outcome") or "").lower()
        if outcome == "circuit_open" or st in ("perm_failed", "failed"):
            cur = "down"; down += 1
        elif st in ("unstable", "degraded") or outcome in ("error", "partial"):
            cur = "degraded"; deg += 1
        elif st == "ok":
            cur = "ok"
        else:
            cur = "degraded"; deg += 1
        if _SEV.get(cur, 0) > _SEV.get(worst, 0):
            worst = cur
    return {"key": "datasource", "label": "데이터소스 스캔", "state": worst,
            "detail": f"{len(health)}개 스코프 (저하 {deg}, 중단 {down})", "scopes": len(health)}


# ── 계측 커버리지 (정직 노출 — '전체 비용' 오해 방지) ────────────────────────────
_COVERAGE = {
    "instrumented": [
        "에이전트 추론", "보조 추론(검증·요약·분류·주제·SQL수정)", "인사이트 분석(스키마·테이블·계정·노드)",
        "용어사전 후보", "프롬프트 자동생성(수동 + 자율 sweep)", "메타데이터 자동완성",
    ],
    "uninstrumented": [
        {"name": "임베딩 (backfill·쿼리·샘플 3경로)", "reason": "embeddings.create 응답에 usage 필드 없음(SDK 한계)"},
        {"name": "LLM provider health probe", "reason": "헬스체크 전용 — 의도적 계측 제외"},
    ],
    "note": "위 미계측 활동은 llm_usage 에 기록되지 않아 KPI·비용 합계에서 제외됩니다('전체 비용' 아님).",
}

_ACTIVITY_LIMIT_DEFAULT = 30
_ACTIVITY_LIMIT_MAX = 100


def _query_activity(cur, taxonomy_for, *, cursor=None, limit=_ACTIVITY_LIMIT_DEFAULT):
    """llm_usage 활동 feed 를 id DESC(=created_at DESC — id BIGSERIAL 단조증가) 로 cursor 페이징.
    cursor(id) 미지정=최신부터. `WHERE id < cursor` + limit+1 조회로 has_more 판정 → 안정적
    keyset 페이징(OFFSET 아님). 반환 (items, next_cursor). 과거 기록 조회용(더 보기)."""
    # TASK-20260702-audit-nav-ux: '최근 활동' 클릭 상세 확장을 위해 SELECT 컬럼을 확장한다.
    #   요청 별칭(model)과 서빙 모델(resolved_model)을 분리 보존(요청→서빙 표시), run_id(요청 식별자),
    #   conversation_id(연결 대화 드릴다운)를 추가. 기존 반환 필드(model=served/total/cost/latency/...)는
    #   보존 — 상세 필드는 순수 additive(overview activity feed + /activity 페이징 공용, 신규 엔드포인트 무).
    _COLS = ("id, task, model, resolved_model, total_tokens, prompt_tokens, "
             "completion_tokens, latency_ms, created_at, run_id, conversation_id")
    if cursor is not None:
        cur.execute(
            "SELECT " + _COLS + " FROM agent_runtime.llm_usage WHERE id < %s ORDER BY id DESC LIMIT %s",
            (int(cursor), int(limit) + 1),
        )
    else:
        cur.execute(
            "SELECT " + _COLS + " FROM agent_runtime.llm_usage ORDER BY id DESC LIMIT %s",
            (int(limit) + 1,),
        )
    rows = cur.fetchall() or []
    has_more = len(rows) > limit
    items = []
    for r in rows[:limit]:
        tx = taxonomy_for(r[1])
        served = r[3] or r[2]  # COALESCE(resolved_model, model) — 행 표시·비용은 서빙 모델 기준(기존 규약 보존)
        prompt_t = int(r[5] or 0)
        completion_t = int(r[6] or 0)
        items.append({
            "id": int(r[0]), "task": r[1], "category": tx["category"], "label": tx["label"],
            "model": served, "total_tokens": int(r[4] or 0),
            "cost_usd": app._estimate_llm_cost_usd(served, prompt_t, completion_t),
            "latency_ms": (int(r[7]) if r[7] is not None else None),
            "created_at": (r[8].isoformat() if r[8] else None),
            # ── 상세 확장용 additive 필드 ──
            "req_model": r[2], "resolved_model": r[3],
            "prompt_tokens": prompt_t, "completion_tokens": completion_t,
            "run_id": r[9], "conversation_id": r[10],
        })
    next_cursor = items[-1]["id"] if (has_more and items) else None
    return items, next_cursor


@router.get("/api/admin/ai-ops/activity")
def admin_ai_ops_activity(
    request: Request,
    account=Depends(app.require_permission("console.aiops.read", message="AI 운영 현황 조회 권한이 필요합니다 (운영자 전용).")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """AI 운영 현황 '최근 활동' 과거 기록 페이징 — cursor(id) keyset 로 더 오래된 활동 조회.
    Query: cursor(id, 이 값보다 오래된 것), limit(기본 30, 1~100). PG 미가용 시 부분 degrade."""
    from shared.model_catalog import taxonomy_for

    try:
        limit = int(request.query_params.get("limit", str(_ACTIVITY_LIMIT_DEFAULT)))
    except Exception:
        limit = _ACTIVITY_LIMIT_DEFAULT
    limit = max(1, min(_ACTIVITY_LIMIT_MAX, limit))
    cursor_raw = request.query_params.get("cursor")
    cursor = None
    if cursor_raw:
        try:
            cursor = int(cursor_raw)
        except Exception:
            cursor = None

    items: list[dict] = []
    next_cursor = None
    pg_available = True
    try:
        from shared.db import _pg_connect_ro
        pg = _pg_connect_ro()
    except Exception:
        pg = None
        pg_available = False
    if pg is not None:
        try:
            with pg.cursor() as cur:
                items, next_cursor = _query_activity(cur, taxonomy_for, cursor=cursor, limit=limit)
        except Exception:
            _log.debug("ai_ops activity paging query failed", exc_info=True)
        finally:
            try:
                pg.close()
            except Exception:
                pass

    return JSONResponse({"items": items, "next_cursor": next_cursor, "pg_available": pg_available})


@router.get("/api/admin/ai-ops")
def admin_ai_ops(
    request: Request,
    account=Depends(app.require_permission("console.aiops.read", message="AI 운영 현황 조회 권한이 필요합니다 (운영자 전용).")),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """AI 운영 관제 종합 — 상태 배너/축 + KPI + Attention + 카테고리 드릴다운 + 최근 활동 + 커버리지.

    Query: days(기본 7, 1~90). 읽기 전용. PG 미가용 시 부분 degrade(200 유지)."""
    from shared.model_catalog import taxonomy_for, ai_categories

    try:
        days = int(request.query_params.get("days", "7"))
    except Exception:
        days = 7
    days = max(1, min(90, days))

    # ── 상태 축 → worst-of 배너 ──
    axes = [_provider_axis(), _ask_worker_axis(conn), _insight_worker_axis(conn), _datasource_axis()]
    rolled = [a for a in axes if a["state"] != "na"]
    banner_state = "ok"
    for a in rolled:
        if _SEV.get(a["state"], 0) > _SEV.get(banner_state, 0):
            banner_state = a["state"]
    banner = {"state": banner_state, "label": _SEV_LABEL.get(banner_state, banner_state)}

    # ── PG 집계 (부분 degrade) ──
    pg_available = True
    categories: list[dict] = []
    activity: list[dict] = []
    activity_next_cursor = None
    latency = {"measured_calls": 0, "avg_ms": None, "p50_ms": None, "p95_ms": None}
    activity_24h = {"calls": 0, "requests": 0}
    unmapped_tasks: list[str] = []

    try:
        from shared.db import _pg_connect_ro
        pg = _pg_connect_ro()
    except Exception:
        pg = None
        pg_available = False

    if pg is not None:
        try:
            win = f"now() - interval '{days} days'"
            cat_fold: dict[str, dict] = {}
            lat_by_task: dict[str, dict] = {}
            with pg.cursor() as cur:
                # 1) 카테고리/태스크 × 모델 (호출·토큰·비용). taxonomy self-surface.
                try:
                    cur.execute(
                        f"SELECT task, COALESCE(resolved_model, model) AS m, count(*), "
                        f"sum(prompt_tokens), sum(completion_tokens), sum(total_tokens) "
                        f"FROM agent_runtime.llm_usage WHERE created_at >= {win} GROUP BY task, 2"
                    )
                    for r in (cur.fetchall() or []):
                        task, m = r[0], r[1]
                        calls, pt, ct, tt = int(r[2] or 0), int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)
                        tx = taxonomy_for(task)
                        e = cat_fold.setdefault(tx["category"], {
                            "category": tx["category"], "calls": 0, "total_tokens": 0,
                            "cost_usd": 0.0, "_tasks": {},
                        })
                        e["calls"] += calls
                        e["total_tokens"] += tt
                        e["cost_usd"] += app._estimate_llm_cost_usd(m, pt, ct)
                        te = e["_tasks"].setdefault(task, {
                            "task": task, "label": tx["label"], "calls": 0, "total_tokens": 0,
                        })
                        te["calls"] += calls
                        te["total_tokens"] += tt
                except Exception:
                    _log.debug("ai_ops categories query failed", exc_info=True)

                # 2) 태스크별 latency (컬럼 부재/마이그 전이면 실패 → 스킵, 부분 degrade).
                try:
                    cur.execute(
                        f"SELECT task, count(latency_ms), avg(latency_ms), "
                        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), "
                        f"percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) "
                        f"FROM agent_runtime.llm_usage "
                        f"WHERE created_at >= {win} AND latency_ms IS NOT NULL GROUP BY task"
                    )
                    for r in (cur.fetchall() or []):
                        lat_by_task[r[0]] = {
                            "measured": int(r[1] or 0),
                            "avg_ms": (round(float(r[2]), 1) if r[2] is not None else None),
                            "p50_ms": (round(float(r[3]), 1) if r[3] is not None else None),
                            "p95_ms": (round(float(r[4]), 1) if r[4] is not None else None),
                        }
                except Exception:
                    _log.debug("ai_ops latency-by-task query failed (latency_ms 컬럼 부재?)", exc_info=True)

                # 3) 전체 latency KPI (계측 이후 window 만 — 마이그 이전 행은 NULL 제외).
                try:
                    cur.execute(
                        f"SELECT count(latency_ms), avg(latency_ms), "
                        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), "
                        f"percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) "
                        f"FROM agent_runtime.llm_usage "
                        f"WHERE created_at >= {win} AND latency_ms IS NOT NULL"
                    )
                    lr = cur.fetchone()
                    if lr:
                        latency = {
                            "measured_calls": int(lr[0] or 0),
                            "avg_ms": (round(float(lr[1]), 1) if lr[1] is not None else None),
                            "p50_ms": (round(float(lr[2]), 1) if lr[2] is not None else None),
                            "p95_ms": (round(float(lr[3]), 1) if lr[3] is not None else None),
                        }
                except Exception:
                    _log.debug("ai_ops latency KPI query failed", exc_info=True)

                # 4) 최근 24h 활동.
                try:
                    cur.execute(
                        "SELECT count(*), count(distinct run_id) FROM agent_runtime.llm_usage "
                        "WHERE created_at >= now() - interval '24 hours'"
                    )
                    ar = cur.fetchone() or (0, 0)
                    activity_24h = {"calls": int(ar[0] or 0), "requests": int(ar[1] or 0)}
                except Exception:
                    _log.debug("ai_ops 24h activity query failed", exc_info=True)

                # 5) 최근 활동 feed ("방금 무엇을 했나") — 최신 페이지 + 과거 페이징용 next_cursor.
                try:
                    activity, activity_next_cursor = _query_activity(
                        cur, taxonomy_for, limit=_ACTIVITY_LIMIT_DEFAULT)
                except Exception:
                    _log.debug("ai_ops activity feed query failed", exc_info=True)

            # 카테고리 정리 + latency 병합 + unmapped self-surface.
            cat_labels = ai_categories()
            for cat, e in cat_fold.items():
                tasks = sorted(e.pop("_tasks").values(), key=lambda x: x["total_tokens"], reverse=True)
                for t in tasks:
                    lt = lat_by_task.get(t["task"])
                    if lt:
                        t["p50_ms"] = lt["p50_ms"]
                        t["p95_ms"] = lt["p95_ms"]
                        t["measured"] = lt["measured"]
                e["label"] = cat_labels.get(cat, cat)
                e["cost_usd"] = round(e["cost_usd"], 4)
                e["tasks"] = tasks
                categories.append(e)
                if cat == "ai.other.unmapped":
                    unmapped_tasks = [t["task"] for t in tasks]
            categories.sort(key=lambda x: x["total_tokens"], reverse=True)
        finally:
            try:
                pg.close()
            except Exception:
                pass

    # ── Attention zone (심각도 우선 부상) ──
    attention: list[dict] = []
    for a in rolled:
        if a["state"] in ("degraded", "down"):
            attention.append({"level": a["state"], "label": a["label"], "detail": a["detail"]})
    if unmapped_tasks:
        attention.append({
            "level": "degraded", "label": "미분류 AI 활동",
            "detail": f"taxonomy 미등록 task {len(unmapped_tasks)}종: " + ", ".join(unmapped_tasks[:5]),
        })
    if not pg_available:
        attention.append({
            "level": "unknown", "label": "계측 저장소(PG) 미가용",
            "detail": "AI 활동·비용·지연 지표를 일시적으로 조회할 수 없습니다.",
        })

    return JSONResponse({
        "window_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "banner": banner,
        "axes": axes,
        "kpis": {
            "activity_24h": activity_24h,
            "latency": latency,
            "provider_state": axes[0]["state"],
            "workers_ok": sum(1 for a in (axes[1], axes[2]) if a["state"] == "ok"),
            "workers_total": sum(1 for a in (axes[1], axes[2]) if a["state"] != "na"),
        },
        "attention": attention,
        "categories": categories,
        "activity": activity,
        "activity_next_cursor": activity_next_cursor,
        "coverage": _COVERAGE,
        "pg_available": pg_available,
        # 위젯 deep-link 계약: 대시보드 타일 → 이 탭. data-admin-tab 값(hyphen)과 정확히 일치.
        "tab": "ai-ops",
    })
