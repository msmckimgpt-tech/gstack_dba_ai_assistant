"""routers/admin_reasoning.py — AI 추론 조회 API (feature-0021).

**읽기 전용** — 파괴적 쓰기 없음. console-ia(2026-07-16) 재구성으로 화면·권한이 성격별로 분리:

  - GET /api/admin/reasoning/redteam           [감사 > AI 추론] 자가 적대 리뷰 요약 통계 +
                                               최근 판정. 권한 `console.reasoning.read`.
  - GET /api/admin/reasoning/notes             [감사 > AI 추론] 세션/제품 메모리 노트 임시
                                               파일 현황. 권한 `console.reasoning.read`.
  - GET /api/admin/reasoning/guidance          [설정 > 프롬프트 > 작동 지침 / 스킬] 지침/스킬
                                               레지스트리 (progressive disclosure — 목록 메타만,
                                               ?key= 단건 본문, ?kind=guidance|skill 필터).
                                               권한 `system_prompt.global.read` (프롬프트 조회 재사용).

설계 (ai_ops.py 규약 답습):
  - PG(agent_runtime.redteam_reviews) 읽기는 `_pg_connect_ro`(least-privilege) + **부분
    degrade** — PG 미가용/테이블 부재도 200 반환 + `pg_available:false`.
  - 지침 본문은 agent-core `modules.guidance_registry` 가 코드 상수를 lazy 참조 (단일
    진실원본 — 콘솔 조회를 위해 본문을 복제하지 않는다).
  - uniform `import app` + `Depends(app.require_permission(...))` (DI seam 정합).

순환 안전: app 정의 후 맨 끝 include_router (register_all).
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

import app

INCLUDE_ORDER = 240  # 등록 순서 — 현행 최대 230(admin_settings) 다음 슬롯
router = APIRouter()

_log = logging.getLogger(__name__)

_REVIEW_LIMIT_DEFAULT = 30
_REVIEW_LIMIT_MAX = 100
# console-ia(2026-07-16): 리뷰 활동/노트(감사) = console.reasoning.read, 지침/스킬(설정>프롬프트)
# 조회 = system_prompt.global.read 재사용(프롬프트 조회 성격 일치, 신규 권한 최소화).
_PERM_MSG = "AI 추론 활동 조회 권한이 필요합니다 (운영자 전용)."
_GUIDANCE_PERM_MSG = "프롬프트 지침/스킬 조회 권한이 필요합니다 (전역 시스템 프롬프트 조회 권한)."


@router.get("/api/admin/reasoning/guidance")
def admin_reasoning_guidance(
    request: Request,
    account=Depends(app.require_permission("system_prompt.global.read", message=_GUIDANCE_PERM_MSG)),
) -> JSONResponse:
    """작동 지침/스킬 레지스트리 — 목록(메타만) 또는 ?key= 단건 본문(progressive disclosure).
    ?kind=guidance|skill 로 필터(설정 > 프롬프트 > 작동 지침 / 스킬 항목이 각각 사용)."""
    key = str(request.query_params.get("key") or "").strip()
    kind = str(request.query_params.get("kind") or "").strip().lower()
    try:
        from modules import guidance_registry as _reg
    except Exception:
        _log.debug("guidance_registry import failed", exc_info=True)
        return JSONResponse({"items": [], "registry_available": False})
    if key:
        item = None
        try:
            item = _reg.get_guidance(key)
        except Exception:
            _log.debug("guidance detail failed", exc_info=True)
        if item is None:
            return JSONResponse({"error": "unknown_guidance_key"}, status_code=404)
        return JSONResponse({"item": item, "registry_available": True})
    try:
        items = _reg.list_guidance()
        if kind in ("guidance", "skill"):
            items = [it for it in items if it.get("kind") == kind]
    except Exception:
        _log.debug("guidance list failed", exc_info=True)
        items = []
    return JSONResponse({"items": items, "registry_available": True})


def _query_reviews(cur, *, cursor: int | None, limit: int,
                   include_rederive: bool = False) -> tuple[list[dict], int | None]:
    """redteam_reviews 를 id DESC keyset 으로 페이징 (ai-ops _query_activity 규약).

    include_rederive=True 면 0043 마이그 컬럼(rederive_applied/rederive_tool_rounds/
    rederive_axis)까지 SELECT 해 콘솔의 '결함 수정' 진행 단계에서 도구 재추론(rederive)
    발동 여부·라운드·축을 노출한다. stale agent 이미지(0043 미적용)에서는 호출부가
    information_schema 로 컬럼 부재를 감지해 include_rederive=False 로 폴백하므로 기존
    동작(리뷰 목록 노출)이 회귀 없이 유지된다.

    기본값은 fail-safe 로 False — 컬럼 존재를 확인한 호출자만 명시적으로 True 를 전달한다
    (kwarg 생략 시 base-only SELECT 라 stale 이미지에서도 UndefinedColumn 이 나지 않는다)."""
    base_cols = ("id, conversation_id, run_id, verdict, findings, block_count, warn_count, "
                 "verify_verdict, revision_applied, model, latency_ms, reasoning_level, is_group, created_at")
    cols = base_cols + (", rederive_applied, rederive_tool_rounds, rederive_axis" if include_rederive else "")
    if cursor is not None:
        cur.execute(
            "SELECT " + cols + " FROM agent_runtime.redteam_reviews WHERE id < %s ORDER BY id DESC LIMIT %s",
            (int(cursor), int(limit) + 1),
        )
    else:
        cur.execute(
            "SELECT " + cols + " FROM agent_runtime.redteam_reviews ORDER BY id DESC LIMIT %s",
            (int(limit) + 1,),
        )
    rows = cur.fetchall() or []
    has_more = len(rows) > limit
    items: list[dict] = []
    for r in rows[:limit]:
        findings = r[4]
        if isinstance(findings, str):
            try:
                findings = json.loads(findings)
            except Exception:
                findings = []
        item = {
            "id": int(r[0]), "conversation_id": r[1], "run_id": r[2], "verdict": r[3],
            "findings": findings or [], "block_count": int(r[5] or 0), "warn_count": int(r[6] or 0),
            "verify_verdict": r[7], "revision_applied": bool(r[8]), "model": r[9],
            "latency_ms": (int(r[10]) if r[10] is not None else None),
            "reasoning_level": r[11], "is_group": bool(r[12]),
            "created_at": (r[13].isoformat() if r[13] else None),
            # rederive_* 기본값 — 컬럼 부재 폴백/error 경로 호환 (프론트 stage 렌더가 항상 참조).
            "rederive_applied": False, "rederive_tool_rounds": 0, "rederive_axis": None,
        }
        if include_rederive:
            item["rederive_applied"] = bool(r[14])
            item["rederive_tool_rounds"] = int(r[15] or 0)
            item["rederive_axis"] = r[16]
        items.append(item)
    next_cursor = items[-1]["id"] if (has_more and items) else None
    return items, next_cursor


@router.get("/api/admin/reasoning/redteam")
def admin_reasoning_redteam(
    request: Request,
    account=Depends(app.require_permission("console.reasoning.read", message=_PERM_MSG)),
) -> JSONResponse:
    """자가 적대 리뷰 활동 — 24h/7d 요약 통계 + 최근 판정 keyset 페이징.
    Query: cursor(id, 이 값보다 오래된 것), limit(기본 30, 1~100). PG 미가용 시 부분 degrade."""
    try:
        limit = int(request.query_params.get("limit", str(_REVIEW_LIMIT_DEFAULT)))
    except Exception:
        limit = _REVIEW_LIMIT_DEFAULT
    limit = max(1, min(_REVIEW_LIMIT_MAX, limit))
    cursor_raw = request.query_params.get("cursor")
    cursor = None
    if cursor_raw:
        try:
            cursor = int(cursor_raw)
        except Exception:
            cursor = None

    items: list[dict] = []
    next_cursor = None
    stats: dict[str, Any] = {}
    pg_available = True
    # table_available: PG 는 붙었으나 redteam_reviews 가 아직 없는 경우(마이그 전 / stale agent
    # 이미지 배포 함정)를 "리뷰 없음"(빈 목록)과 구분한다. 부재면 콘솔이 "아직 준비 안 됨" 안내.
    table_available = True
    try:
        from shared.db import _pg_connect_ro
        pg = _pg_connect_ro()
    except Exception:
        pg = None
        pg_available = False
    if pg is not None:
        try:
            with pg.cursor() as cur:
                # 요약 통계 — cursor 미지정(첫 페이지)일 때만 (더 보기 페이징은 목록만).
                if cursor is None:
                    try:
                        cur.execute(
                            "SELECT COUNT(*) FILTER (WHERE created_at >= now() - interval '24 hours'), "
                            "       COUNT(*) FILTER (WHERE created_at >= now() - interval '7 days'), "
                            "       COUNT(*) FILTER (WHERE verdict='revise' AND created_at >= now() - interval '7 days'), "
                            "       COUNT(*) FILTER (WHERE revision_applied AND created_at >= now() - interval '7 days'), "
                            "       COUNT(*) FILTER (WHERE verdict='error' AND created_at >= now() - interval '7 days'), "
                            "       AVG(latency_ms) FILTER (WHERE created_at >= now() - interval '7 days') "
                            "FROM agent_runtime.redteam_reviews"
                        )
                        row = cur.fetchone() or (0, 0, 0, 0, 0, None)
                        stats = {
                            "reviews_24h": int(row[0] or 0), "reviews_7d": int(row[1] or 0),
                            "revise_7d": int(row[2] or 0), "revisions_applied_7d": int(row[3] or 0),
                            "errors_7d": int(row[4] or 0),
                            "avg_latency_ms_7d": (int(row[5]) if row[5] is not None else None),
                        }
                    except Exception:
                        # 테이블 부재(마이그 전) 등 — abort 트랜잭션 정리 후 부재로 표기.
                        try:
                            pg.rollback()
                        except Exception:
                            pass
                        stats = {}
                        table_available = False
                # 0043 rederive_* 컬럼 존재 여부 — stale agent 이미지(0043 미적용) 방어:
                # 부재 시 include_rederive=False 로 폴백해 UndefinedColumn 없이 기존 목록 노출.
                _has_rederive = True
                try:
                    cur.execute(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema='agent_runtime' AND table_name='redteam_reviews' "
                        "AND column_name='rederive_applied'"
                    )
                    _has_rederive = cur.fetchone() is not None
                except Exception:
                    _has_rederive = False
                try:
                    items, next_cursor = _query_reviews(
                        cur, cursor=cursor, limit=limit, include_rederive=_has_rederive)
                except Exception:
                    # 테이블 부재/스키마 불일치 — 빈 목록과 구분해 table_available=False.
                    try:
                        pg.rollback()
                    except Exception:
                        pass
                    table_available = False
        except Exception:
            _log.debug("redteam reviews query failed", exc_info=True)
        finally:
            try:
                pg.close()
            except Exception:
                pass

    return JSONResponse({
        "stats": stats, "items": items, "next_cursor": next_cursor,
        "pg_available": pg_available, "table_available": table_available,
    })


@router.get("/api/admin/reasoning/notes")
def admin_reasoning_notes(
    account=Depends(app.require_permission("console.reasoning.read", message=_PERM_MSG)),
) -> JSONResponse:
    """세션/제품 메모리 노트 임시 파일 현황 — scope/식별자/크기/갱신·TTL 잔여. 파일 내용 비반환
    (세션 노트는 대화 파생 텍스트 — 목록 메타만으로 운영 가시성 충족, 최소 노출)."""
    import shared.runtime_settings as _rts

    notes_root = os.getenv("AGENT_NOTES_DIR", "/shared/agent-notes")
    ttl_days = {"session": 7, "product": 30}
    try:
        ttl_days = {
            "session": max(1, _rts.get_int("REDTEAM_NOTES_SESSION_TTL_DAYS")),
            "product": max(1, _rts.get_int("REDTEAM_NOTES_PRODUCT_TTL_DAYS")),
        }
    except Exception:
        pass
    now = time.time()
    items: list[dict] = []
    for scope, days in ttl_days.items():
        base = os.path.join(notes_root, scope)
        try:
            names = sorted(os.listdir(base))
        except Exception:
            continue
        for name in names[:500]:
            path = os.path.join(base, name)
            try:
                st = os.stat(path)
            except Exception:
                continue
            age_sec = max(0, now - st.st_mtime)
            items.append({
                "scope": scope,
                "ident": name.removesuffix(".md"),
                "size_bytes": int(st.st_size),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
                "ttl_days": days,
                "expires_in_sec": max(0, int(days * 86400 - age_sec)),
            })
    return JSONResponse({
        "root": notes_root,
        "items": items,
        "ttl_days": ttl_days,
    })
