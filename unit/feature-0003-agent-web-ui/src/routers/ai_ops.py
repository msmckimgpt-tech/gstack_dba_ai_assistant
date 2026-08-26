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
from shared.model_catalog import canonical_usage_model, canonical_usage_model_sql

INCLUDE_ORDER = 220  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()

_log = logging.getLogger(__name__)

# 상태 severity — worst-of 롤업용(높을수록 나쁨). "na"(해당없음)는 롤업에서 제외.
_SEV = {"ok": 0, "unknown": 1, "degraded": 2, "down": 3}
_SEV_LABEL = {"ok": "정상", "unknown": "부분 가시", "degraded": "저하", "down": "중단", "na": "해당 없음"}


# ── 상태 축 ─────────────────────────────────────────────────────────────────────
def _provider_axis() -> dict:
    """LLM provider 외부요인 제한 상태(PG agent_runtime.llm_provider_health cheap read)."""
    # feature-0043(codex 리뷰 P2): **관리자 관제는 마스킹된 값을 보면 안 된다.**
    # 대화 UI 는 차단 중 provider 상태를 non-restricted 로 덮는다(전송에 영향이 없고, 복구 ping
    # 이 불가능해 배너가 영구 고착되므로). 그 마스킹이 이 화면까지 오면 운영자는 "정상" 만 보고,
    # 게이트를 되돌리는 순간 숨어 있던 제한이 되살아난다 — 전환 전 위험 확인이 불가능해진다.
    # 그래서 여기서는 **원본**을 읽고, 차단 사실은 별도 필드로 함께 싣는다.
    blocked = False
    try:
        raw = app._read_llm_provider_status_admin() or {}
        blocked = bool(raw.get("server_llm_blocked"))
        st = str(raw.get("state") or "unknown").lower()
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
    detail = f"state={st}"
    if blocked:
        # 차단 중임을 **관제에는 명시**한다. 이걸 빼면 운영자는 degraded 를 보고 "왜 아무도
        # 영향을 안 받지?" 를, 반대로 ok 를 보고 "정말 괜찮은가?" 를 판단할 근거가 없다.
        detail += " · 서버 계정 LLM 차단(외부 AI 브리지) — 대화 전송에는 영향 없음"
    return {"key": "provider", "label": "LLM 제공자", "state": state, "detail": detail,
            "server_llm_blocked": blocked}


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
    _BASE_COLS = ("id, task, model, resolved_model, total_tokens, prompt_tokens, "
                  "completion_tokens, latency_ms, created_at, run_id, conversation_id")

    # TASK-20260703-aiops-target(0032): '최근 활동' 에 인사이트 분석 대상(schema/schema.table/노드 FQN)을
    # 표시하기 위해 target 컬럼을 additive 로 SELECT(맨 끝 인덱스 11). 컬럼 부재(마이그 미적용 / agent image
    # stale — memory: deploy-migration-stale-agent-image)면 base 컬럼만으로 재조회해 피드가 깨지지 않게
    # 자가치유(has_target=False → target=None). SELECT 전용이라 rollback 은 무손실.
    def _fetch(cols: str):
        if cursor is not None:
            cur.execute(
                "SELECT " + cols + " FROM agent_runtime.llm_usage WHERE id < %s ORDER BY id DESC LIMIT %s",
                (int(cursor), int(limit) + 1),
            )
        else:
            cur.execute(
                "SELECT " + cols + " FROM agent_runtime.llm_usage ORDER BY id DESC LIMIT %s",
                (int(limit) + 1,),
            )
        return cur.fetchall() or []

    # usage-metric-charts(2026-08-13): 캐시 토큰(0056)을 사다리 최상단에 추가한다. 행 단위 비용이
    #   캐시 할인 단가를 반영해야 관리 콘솔 사용량 집계와 같은 값이 된다. 컬럼 부재(마이그 미적용·
    #   stale image)면 한 단계씩 내려가 피드 자체는 계속 뜬다(기존 target 자가치유와 동형).
    has_cache = True
    has_target = True
    try:
        rows = _fetch(_BASE_COLS + ", target, cache_read_tokens, cache_write_tokens")
    except Exception:
        has_cache = False
        try:
            cur.connection.rollback()
        except Exception:
            pass
        try:
            rows = _fetch(_BASE_COLS + ", target")
        except Exception:
            try:
                cur.connection.rollback()  # abort 트랜잭션 정리 후 target 제외 재조회
            except Exception:
                pass
            rows = _fetch(_BASE_COLS)
            has_target = False
    has_more = len(rows) > limit
    items = []
    for r in rows[:limit]:
        tx = taxonomy_for(r[1])
        served = r[3] or r[2]  # COALESCE(resolved_model, model) — 비용 계산·라우팅 상세의 서빙 기준
        # aiops-model-canonical: 활동 목록의 주 모델 배지는 canonical family 로 표시 → 관리 콘솔
        # LLM 사용량 도넛/기타 표기와 정합(라우팅 변형·실 모델 ID·gemma 폴백이 통일된 실 모델명으로 노출).
        # req_model(요청 alias)·resolved_model(실 서빙)은 아래에서 raw 로 보존 → 상세 펼침의
        # '요청 → 서빙' 라우팅(계정 분기·gemma 폴백 등) audit 정보는 그대로 유지(정보 손실 없음).
        served_canonical = canonical_usage_model(served)
        prompt_t = int(r[5] or 0)
        completion_t = int(r[6] or 0)
        # 인덱스 12/13 = cache_read/cache_write (사다리 최상단 경로에서만 존재).
        cache_r = int(r[12] or 0) if (has_cache and len(r) > 12) else 0
        cache_w = int(r[13] or 0) if (has_cache and len(r) > 13) else 0
        items.append({
            "id": int(r[0]), "task": r[1], "category": tx["category"], "label": tx["label"],
            "model": served_canonical, "total_tokens": int(r[4] or 0),
            "cost_usd": app._estimate_llm_cost_usd(served, prompt_t, completion_t, cache_r, cache_w),
            "latency_ms": (int(r[7]) if r[7] is not None else None),
            "created_at": (r[8].isoformat() if r[8] else None),
            # ── 상세 확장용 additive 필드 ──
            "req_model": r[2], "resolved_model": r[3],
            "prompt_tokens": prompt_t, "completion_tokens": completion_t,
            "run_id": r[9], "conversation_id": r[10],
            # 0032: 인사이트 분석 대상(schema/schema.table/노드 FQN). 대상 없는 활동(추론·요약 등)·컬럼 부재 시 None.
            #   len(r) > 11 가드: 폴백 경로(base 컬럼만)나 target 미포함 행에서 IndexError 방지(방어심층).
            "target": ((r[11] or None) if (has_target and len(r) > 11) else None),
        })
    next_cursor = items[-1]["id"] if (has_more and items) else None
    return items, next_cursor


# ── 워커 공유 자원 예산 (T0b worker-ds-budget) ────────────────────────────────
#: 워커가 flush 한 스냅샷 디렉토리(컨테이너 `/shared` = 호스트 artifacts/shared). web 도 같은
#: 볼륨을 마운트하므로 **PG 테이블·마이그레이션 없이** 파일로 읽는다 — 카운터는 워커 프로세스
#: 메모리에 있고 이 프로세스는 그것을 직접 볼 수 없다.
_WORKER_RES_DIR = "/shared/perf"
#: 파일당 상한(바이트) — 신뢰 경계 안(우리 워커가 쓴 파일)이지만 손상·거대 파일에 대한 방어.
_WORKER_RES_MAX_BYTES = 64 * 1024
#: 표시 상한 — 워커 컨테이너 수는 소수(insight/ask)라 넉넉하다.
_WORKER_RES_MAX_FILES = 8
#: stale 판정(초) — flush 는 insight cycle 마다 일어난다. 초과 시 값 대신 stale 표식을 준다.
_WORKER_RES_STALE_SEC = 1800


def _safe_int(v) -> int:
    """JSON 직렬화 안전 정수 변환. NaN/Infinity/비수치는 0.

    ⚠ `float("NaN")`·`float("Infinity")` 는 파이썬에서 정상 float 이지만 **표준 JSON 이 아니어서**
    `JSONResponse` 직렬화가 `ValueError` 를 내 500 이 된다 — 관측 조회가 콘솔을 깨는 fail-open 위반
    (codex P1, REV-20260730T1430). 손상된 스냅샷 파일이 그 값을 담을 수 있으므로 경계에서 막는다.
    """
    import math
    try:
        if isinstance(v, bool) or v is None:
            return 0
        f = float(v)
        if not math.isfinite(f):
            return 0
        return int(f)
    except Exception:
        return 0


def _safe_float(v) -> float:
    """JSON 직렬화 안전 실수 변환. NaN/Infinity/비수치는 0.0 (`_safe_int` 와 동일 사유)."""
    import math
    try:
        if isinstance(v, bool) or v is None:
            return 0.0
        f = float(v)
        if not math.isfinite(f):
            return 0.0
        return round(f, 4)
    except Exception:
        return 0.0


def _worker_resources() -> dict:
    """워커 자원 예산·계측 스냅샷 수집 (read-only, fail-open).

    반환 `{"available": bool, "workers": [...], "reason": str?}`. 파일 부재·손상·권한 오류는
    전부 `available: false` + reason 으로 강등한다 — 관측 조회가 콘솔 응답을 깨면 본말전도다
    (§20 ai-ops 의 부분 degrade 규약 답습).
    """
    import glob
    import json
    import os
    import time
    out: dict = {"available": False, "workers": []}
    try:
        # **최신 우선 정렬(mtime DESC)** — 표시 상한(_WORKER_RES_MAX_FILES)에 도달해도 현행 워커가
        #   남는다. 파일명 사전순이면 어느 것이 잘릴지 예측할 수 없어 살아 있는 워커가 유령
        #   스냅샷에 밀릴 수 있다(라이브에서 실제로 스냅샷이 누적됐다 — role 안정화와 한 쌍의 방어).
        cands = glob.glob(os.path.join(_WORKER_RES_DIR, "worker-resources-*.json"))
        def _mtime(p):
            try:
                return os.stat(p).st_mtime
            except Exception:
                return 0.0
        # mtime 동률이면 경로 오름차순으로 **결정적** 정렬(codex P2) — tie-break 가 없으면
        #   glob 반환 순서에 따라 상한 밖으로 밀리는 파일이 실행마다 달라진다.
        paths = sorted(cands, key=lambda p: (-_mtime(p), p))
    except Exception as exc:
        out["reason"] = f"디렉토리 조회 실패: {exc.__class__.__name__}"
        return out
    if not paths:
        out["reason"] = "워커 스냅샷 없음 — 워커가 아직 flush 하지 않았거나 구 이미지"
        return out
    now = time.time()
    for path in paths[:_WORKER_RES_MAX_FILES]:
        try:
            # P2 방어: 공유 볼륨은 다른 컨테이너도 쓴다. symlink 를 따라가면 그 컨테이너가 임의
            #   JSON 파일을 읽히게 만들 수 있으므로 **링크는 건너뛰고**, realpath 가 스냅샷
            #   디렉토리 하위인지 재확인한다(디렉토리 이탈 차단). 지표 위조 자체는 볼륨 쓰기
            #   권한을 가진 주체(우리 워커)의 신뢰 문제라 여기서 막지 않는다 — 읽기 표면만 좁힌다.
            if os.path.islink(path):
                continue
            real = os.path.realpath(path)
            base_real = os.path.realpath(_WORKER_RES_DIR)
            if os.path.dirname(real) != base_real:
                continue
            st = os.stat(real)
            if not os.path.isfile(real) or st.st_size > _WORKER_RES_MAX_BYTES:
                continue
            path = real
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                continue
            age = max(0.0, now - st.st_mtime)
            entry = {
                "role": str(data.get("role") or os.path.basename(path))[:64],
                "flushed_at": str(data.get("flushed_at") or "")[:32],
                "age_sec": int(age),
                "stale": age > _WORKER_RES_STALE_SEC,
                "background_enabled": bool(data.get("background_enabled", True)),
                "resources": {},
                "conns": {},
            }
            for key, val in (data.get("resources") or {}).items():
                if not isinstance(val, dict):
                    continue
                entry["resources"][str(key)[:16]] = {
                    "limit": _safe_int(val.get("limit")),
                    "peak": _safe_int(val.get("peak")),
                    "in_use": _safe_int(val.get("in_use")),
                    "acquired": _safe_int(val.get("acquired")),
                    "rejected": _safe_int(val.get("rejected")),
                    "reject_ratio": _safe_float(val.get("reject_ratio")),
                }
            for key, val in (data.get("conns") or {}).items():
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    continue          # 문자열·None 등 손상 값은 제외(계약: 정수 카운터)
                entry["conns"][str(key)[:16]] = _safe_int(val)
            out["workers"].append(entry)
        except Exception:
            continue          # 파일 하나가 손상돼도 나머지는 보여준다
    out["available"] = bool(out["workers"])
    if not out["available"]:
        out["reason"] = "스냅샷 파싱 실패 — 파일 손상 또는 권한"
    return out


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
    latency = {"measured_calls": 0, "avg_ms": None, "p50_ms": None, "p95_ms": None,
               "multistep_requests": 0, "agent_requests": 0}
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
                # usage-model-canonical 정합(aiops-model-canonical): 서빙 모델을 canonical family 로 접어
                # 집계. 출력은 taxonomy 카테고리 롤업이라 모델 차원이 노출되지 않는다. calls/total_tokens 는
                # 정수 sum 이라 그룹 세분도와 무관하게 카테고리 합계가 불변. cost 는 _estimate 가 호출마다
                # round(…,4) 하므로 raw 다중 그룹→canonical 단일 그룹 재결합으로 카테고리 cost 가 최하위
                # 4번째 소수(≈$0.0001) 수준에서 미세 변동할 수 있다(단일 round 라 오히려 더 정확 — pricing 은
                # _estimate 내부 canonical 로 이미 정확했음). 마지막 raw 모델 그룹핑을 제거해 향후 모델 차원
                # 노출 시 라우팅 변형 재분점을 구조적으로 예방하는 것이 본 변경의 실질 효과.
                try:
                    # usage-metric-charts: 캐시 인지 비용. 컬럼 부재(0056 미적용)면 리터럴 0 판으로 재실행.
                    app._usage_cache_exec(cur, pg, lambda cr, cw: (
                        f"SELECT task, {canonical_usage_model_sql('COALESCE(resolved_model, model)')} AS m, count(*), "
                        f"sum(prompt_tokens), sum(completion_tokens), sum(total_tokens), "
                        f"sum({cr}), sum({cw}) "
                        f"FROM agent_runtime.llm_usage WHERE created_at >= {win} GROUP BY task, 2"
                    ))
                    for r in (cur.fetchall() or []):
                        task, m = r[0], r[1]
                        calls, pt, ct, tt = int(r[2] or 0), int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)
                        crw, cww = int(r[6] or 0), int(r[7] or 0)
                        tx = taxonomy_for(task)
                        e = cat_fold.setdefault(tx["category"], {
                            "category": tx["category"], "calls": 0, "total_tokens": 0,
                            "cost_usd": 0.0, "_tasks": {},
                        })
                        e["calls"] += calls
                        e["total_tokens"] += tt
                        e["cost_usd"] += app._estimate_llm_cost_usd(m, pt, ct, crw, cww)
                        te = e["_tasks"].setdefault(task, {
                            "task": task, "label": tx["label"], "calls": 0, "total_tokens": 0,
                        })
                        te["calls"] += calls
                        te["total_tokens"] += tt
                except Exception:
                    _log.debug("ai_ops categories query failed", exc_info=True)

                # 2) 태스크별 지연 = 단계 간 간격 (TASK-20260703-aiops-ttft-latency, 정의 A). p50/p95 는
                #    step_gap_ms(에이전트 라운드 사이 도구·오케스트레이션 간격)로 집계 — 호출 전체 왕복이
                #    아닌 '단계 간 간격'. step_gap_ms 는 다단계 agentic 루프(task='agent')만 비-NULL이라
                #    사실상 에이전트 추론 전용. 컬럼 부재/마이그(0033) 전이면 실패 → 스킵(부분 degrade).
                try:
                    cur.execute(
                        f"SELECT task, count(step_gap_ms), avg(step_gap_ms), "
                        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY step_gap_ms), "
                        f"percentile_cont(0.95) WITHIN GROUP (ORDER BY step_gap_ms) "
                        f"FROM agent_runtime.llm_usage "
                        f"WHERE created_at >= {win} AND step_gap_ms IS NOT NULL GROUP BY task"
                    )
                    for r in (cur.fetchall() or []):
                        lat_by_task[r[0]] = {
                            "measured": int(r[1] or 0),
                            "avg_ms": (round(float(r[2]), 1) if r[2] is not None else None),
                            "p50_ms": (round(float(r[3]), 1) if r[3] is not None else None),
                            "p95_ms": (round(float(r[4]), 1) if r[4] is not None else None),
                        }
                except Exception:
                    _log.debug("ai_ops step-gap-by-task query failed (step_gap_ms 컬럼 부재?)", exc_info=True)

                # 3) 전체 지연 KPI = 단계 간 간격. 계측(0033) 이후 — step_gap_ms=NULL(첫 라운드·단발 호출·
                #    마이그 이전 행) 은 집계에서 자동 제외(aggregate 는 NULL 무시 → cutover 오염 0). '지연' =
                #    사용자가 답변을 받는 총 시간이 아니라 각 추론 단계 간 나타나는 간격(도구 실행 + 오케스트레이션).
                #    F2(observability): 다단계 요청 분모도 함께 — step_gap 은 다단계(≥2 라운드) 요청에서만
                #    표본이 나오므로, 단발 요청 위주 window 에서 빈 tile 을 '고장' 으로 오인하지 않도록
                #    multistep_requests(간격 표본 있는 run_id 수) / agent_requests(전체 에이전트 요청 수) 노출.
                try:
                    cur.execute(
                        f"SELECT count(step_gap_ms), avg(step_gap_ms), "
                        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY step_gap_ms), "
                        f"percentile_cont(0.95) WITHIN GROUP (ORDER BY step_gap_ms), "
                        f"count(DISTINCT run_id) FILTER (WHERE step_gap_ms IS NOT NULL), "
                        f"count(DISTINCT run_id) FILTER (WHERE task = 'agent') "
                        f"FROM agent_runtime.llm_usage "
                        f"WHERE created_at >= {win}"
                    )
                    lr = cur.fetchone()
                    if lr:
                        latency = {
                            "measured_calls": int(lr[0] or 0),
                            "avg_ms": (round(float(lr[1]), 1) if lr[1] is not None else None),
                            "p50_ms": (round(float(lr[2]), 1) if lr[2] is not None else None),
                            "p95_ms": (round(float(lr[3]), 1) if lr[3] is not None else None),
                            "multistep_requests": int(lr[4] or 0),
                            "agent_requests": int(lr[5] or 0),
                        }
                except Exception:
                    _log.debug("ai_ops step-gap KPI query failed", exc_info=True)

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
    # T0b: 워커 자원 예산이 실제로 병목이면(거절 발생) attention 으로 부상시킨다 — 상한을 올릴지
    #   판단해야 하는 신호다. 거절 0 이면 게이트 미발동(정상)이라 조용히 둔다.
    worker_resources = _worker_resources()
    for w in worker_resources.get("workers") or []:
        if not w.get("background_enabled", True):
            attention.append({
                "level": "degraded", "label": "백그라운드 분석 정지",
                "detail": f"{w.get('role')}: 전역 사용 스위치가 꺼져 있습니다(분석·클러스터링·분류 중단).",
            })
        for rk, rv in (w.get("resources") or {}).items():
            if int(rv.get("rejected") or 0) > 0:
                attention.append({
                    "level": "degraded", "label": f"자원 예산 병목({rk})",
                    "detail": (f"{w.get('role')}: 상한 {rv.get('limit')} · 최대 점유 {rv.get('peak')} · "
                               f"거절 {rv.get('rejected')}회(거절률 {rv.get('reject_ratio')}). "
                               "상한을 올리거나 처리량을 낮추세요."),
                })

    # feature-0032: 백그라운드 LLM 토큰 예산(rolling 24h). 소진되면 자동 분석이 다음 주기로
    #   밀리므로 "왜 분석이 안 도나" 의 1차 답이 된다 — attention 으로 부상시킨다.
    try:
        from shared import llm_budget as _lb
        llm_token_budget = _lb.snapshot()
    except Exception:
        llm_token_budget = {"enabled": False, "measurable": False, "exhausted": False}
    if llm_token_budget.get("exhausted"):
        attention.append({
            "level": "degraded", "label": "백그라운드 LLM 토큰 상한 도달",
            "detail": (f"최근 24시간 {llm_token_budget.get('spent')}/{llm_token_budget.get('cap')} 토큰. "
                       "새 자동 분석·요약·분류가 다음 주기로 밀립니다(대화 답변은 정상). "
                       "상한을 올리거나 처리량을 낮추세요."),
        })
    elif llm_token_budget.get("enabled") and (llm_token_budget.get("used_ratio") or 0) >= 0.8:
        attention.append({
            "level": "watch", "label": "백그라운드 LLM 토큰 상한 임박",
            "detail": (f"최근 24시간 {llm_token_budget.get('spent')}/{llm_token_budget.get('cap')} 토큰 "
                       f"({int((llm_token_budget.get('used_ratio') or 0) * 100)}%) 사용."),
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
        # T0b: 워커 공유 자원 예산·계측(파일 스냅샷). 라우트 추가 없음 — 기존 응답 확장.
        "worker_resources": worker_resources,
        # feature-0032: 백그라운드 LLM 토큰 예산 현황(rolling 24h) — 라우트 추가 없이 응답 확장.
        "llm_token_budget": llm_token_budget,
        # 위젯 deep-link 계약: 대시보드 타일 → 이 탭. data-admin-tab 값(hyphen)과 정확히 일치.
        "tab": "ai-ops",
    })
