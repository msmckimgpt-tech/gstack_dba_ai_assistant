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

# 페이징 단위 = **대화**(feature-0021 회차 원장 재구성). 리뷰 flat 목록이 아니라 대화
# 그룹을 한 페이지로 내려, 콘솔이 대화 단위 컨테이너로 스크롤을 격리할 수 있게 한다.
_REVIEW_LIMIT_DEFAULT = 12
_REVIEW_LIMIT_MAX = 50
# 대화당 반환 리뷰 상한 — 장기 대화 하나가 페이지를 독점하지 않도록. 상한 초과분은
# conversations[].capped=True 로 표시(무언의 절단 금지).
_PER_CONV_REVIEW_CAP = 20
# 리뷰당 반환 회차 상한 — 반복 수정은 하드 백스톱(50 라운드 ≈ 101 단계)까지 갈 수 있다.
# 실측 꼬리는 14 라운드(≈29 단계)라 40 이면 전량을 담는다. 초과분은 rounds_truncated 표시.
_PER_REVIEW_ROUND_CAP = 40
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


def _as_json_list(value) -> list:
    """JSONB 컬럼값 → list. 드라이버가 str 로 돌려주는 경우(구 psycopg 경로)까지 흡수."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    return value if isinstance(value, list) else []


def _row_to_item(r, *, include_rederive: bool, include_convergence: bool) -> dict:
    """redteam_reviews row → 콘솔 item dict (SELECT 컬럼 순서와 1:1 대응)."""
    item = {
        "id": int(r[0]), "conversation_id": r[1], "run_id": r[2], "verdict": r[3],
        "findings": _as_json_list(r[4]), "block_count": int(r[5] or 0), "warn_count": int(r[6] or 0),
        "verify_verdict": r[7], "revision_applied": bool(r[8]), "model": r[9],
        "latency_ms": (int(r[10]) if r[10] is not None else None),
        "reasoning_level": r[11], "is_group": bool(r[12]),
        "created_at": (r[13].isoformat() if r[13] else None),
        # rederive_*/수렴 관측 기본값 — 컬럼 부재 폴백/error 경로 호환
        # (프론트 stage 렌더가 항상 참조).
        "rederive_applied": False, "rederive_tool_rounds": 0, "rederive_axis": None,
        "verify_findings": [], "unresolved_block_count": 0, "revision_rounds": 0,
        "stop_reason": None,
        # 0048 회차 원장 — 아래 _attach_rounds 가 채운다(테이블 부재 시 빈 목록 유지).
        "rounds": [], "rounds_truncated": False,
    }
    _off = 14
    if include_rederive:
        item["rederive_applied"] = bool(r[_off])
        item["rederive_tool_rounds"] = int(r[_off + 1] or 0)
        item["rederive_axis"] = r[_off + 2]
        _off += 3
    if include_convergence:
        item["verify_findings"] = _as_json_list(r[_off])
        item["unresolved_block_count"] = int(r[_off + 1] or 0)
        item["revision_rounds"] = int(r[_off + 2] or 0)
        item["stop_reason"] = r[_off + 3]
    return item


def _select_cols(include_rederive: bool, include_convergence: bool) -> str:
    base_cols = ("id, conversation_id, run_id, verdict, findings, block_count, warn_count, "
                 "verify_verdict, revision_applied, model, latency_ms, reasoning_level, is_group, created_at")
    cols = base_cols + (", rederive_applied, rederive_tool_rounds, rederive_axis" if include_rederive else "")
    cols += (", verify_findings, unresolved_block_count, revision_rounds, stop_reason"
             if include_convergence else "")
    return cols


def _query_conversation_page(cur, *, cursor: int | None, conv_limit: int, per_conv_cap: int,
                             include_rederive: bool = False,
                             include_convergence: bool = False,
                             ) -> tuple[list[dict], list[dict], int | None]:
    """리뷰를 **대화 단위로 묶어** 페이징한다 (feature-0021 회차 원장 재구성).

    정렬 계약 (사용자 요구):
      - 대화 그룹: **가장 최근 리뷰가 있었던 대화 순서 desc** (그룹 keyset = MAX(id)).
      - 대화 내부: **진행 순서 asc** (id ASC = 시각 오름차순 — 회차 단계 그대로).

    이전 구현은 전체 리뷰를 id DESC flat 목록으로만 내려, 같은 대화의 리뷰가 목록 곳곳에
    흩어지고 페이징 경계에서 쪼개졌다. 대화를 페이징 단위로 삼으면 콘솔이 대화 단위 컨테이너
    를 만들 수 있고(스크롤 격리), "더 보기" 가 그룹을 쪼개지 않는다.

    per_conv_cap: 대화당 반환 리뷰 상한 (오래된 것부터 잘린다 — 최신 N건 유지). 상한에
    걸린 대화는 conversations[].capped=True 로 표시해, 잘렸다는 사실을 은폐하지 않는다.

    반환: (items, conversations, next_cursor)
      - items: 위 정렬 계약대로 정렬된 리뷰 목록 (대화 그룹 순 → 대화 내 asc).
      - conversations: [{conversation_id, review_count, returned_count, capped, last_id, last_at}]
      - next_cursor: 다음 페이지의 대화 keyset (이 값보다 오래된 last_id 를 가진 대화들).
    """
    # ── Q1. 대화 그룹 keyset (MAX(id) DESC) ──
    if cursor is not None:
        cur.execute(
            "SELECT COALESCE(conversation_id, '') AS ck, MAX(id) AS last_id, "
            "       MAX(created_at) AS last_at, COUNT(*) AS n "
            "  FROM agent_runtime.redteam_reviews "
            " GROUP BY 1 HAVING MAX(id) < %s "
            " ORDER BY last_id DESC LIMIT %s",
            (int(cursor), int(conv_limit) + 1),
        )
    else:
        cur.execute(
            "SELECT COALESCE(conversation_id, '') AS ck, MAX(id) AS last_id, "
            "       MAX(created_at) AS last_at, COUNT(*) AS n "
            "  FROM agent_runtime.redteam_reviews "
            " GROUP BY 1 "
            " ORDER BY last_id DESC LIMIT %s",
            (int(conv_limit) + 1,),
        )
    grows = cur.fetchall() or []
    has_more = len(grows) > conv_limit
    grows = grows[:conv_limit]
    if not grows:
        return [], [], None

    keys = [g[0] for g in grows]
    non_null_keys = [k for k in keys if k]
    # Q1 이 COALESCE(conversation_id,'') 로 묶으므로 NULL 과 빈 문자열은 **같은 그룹**이다.
    # Q2 도 그 정의를 그대로 따라야 한다 — 빈 문자열 행을 `IS NULL` 로만 조회하면 그 행이
    # items 에서 빠져 conversations[].returned_count/capped 가 어긋난다 (codex 리뷰 P2).
    want_blank = any(not k for k in keys)

    # ── Q2. 그 대화들의 리뷰 (대화당 최신 per_conv_cap 건) ──
    cols = _select_cols(include_rederive, include_convergence)
    cur.execute(
        "SELECT " + cols + " FROM ("
        "  SELECT " + cols + ", "
        "         ROW_NUMBER() OVER (PARTITION BY COALESCE(conversation_id, '') "
        "                            ORDER BY id DESC) AS rn "
        "    FROM agent_runtime.redteam_reviews "
        "   WHERE (conversation_id = ANY(%s) "
        "          OR (%s AND (conversation_id IS NULL OR conversation_id = '')))"
        ") t WHERE rn <= %s ORDER BY id",
        (non_null_keys, bool(want_blank), int(per_conv_cap)),
    )
    rows = cur.fetchall() or []
    by_conv: dict[str, list[dict]] = {}
    for r in rows:
        it = _row_to_item(r, include_rederive=include_rederive,
                          include_convergence=include_convergence)
        by_conv.setdefault(it["conversation_id"] or "", []).append(it)

    items: list[dict] = []
    conversations: list[dict] = []
    for g in grows:
        ck, last_id, last_at, total = g[0], int(g[1]), g[2], int(g[3] or 0)
        group = by_conv.get(ck, [])  # Q2 가 ORDER BY id 라 이미 대화 내 asc
        conversations.append({
            "conversation_id": (ck or None),
            "review_count": total,
            "returned_count": len(group),
            "capped": total > len(group),
            "last_id": last_id,
            "last_at": (last_at.isoformat() if last_at else None),
        })
        items.extend(group)

    next_cursor = int(grows[-1][1]) if has_more else None
    return items, conversations, next_cursor


def _attach_rounds(cur, items: list[dict]) -> bool:
    """items 에 회차 단계 원장(0048 redteam_review_rounds)을 붙인다 — 회차 asc.

    반환값은 원장 가용 여부. 0048 미적용(마이그/배포 대기) 이면 False 를 돌려주고 items 의
    `rounds` 는 빈 목록으로 남는다 — 콘솔은 그 경우 기존 요약 기반 타임라인으로 폴백해
    회귀 없이 동작한다 (구 데이터도 같은 경로).

    리뷰당 회차는 `_PER_REVIEW_ROUND_CAP` 로 상한을 둔다 — 반복 수정은 하드 백스톱(50
    라운드 ≈ 101 단계)까지 갈 수 있어, 상한이 없으면 한 페이지 응답이 수백 KB 로 부푼다
    (codex 리뷰 P2). 잘린 리뷰는 `rounds_truncated:true` 로 표시한다(무언의 절단 금지)."""
    ids = [it["id"] for it in items]
    if not ids:
        return True
    cur.execute(
        "SELECT review_id, round_index, phase, verdict, findings, block_count, warn_count, "
        "       revise_method, revise_axis, tool_rounds, answer_chars, note, created_at "
        "  FROM agent_runtime.redteam_review_rounds "
        " WHERE review_id = ANY(%s) "
        " ORDER BY review_id, round_index, id",
        (ids,),
    )
    by_review: dict[int, list[dict]] = {}
    truncated: set[int] = set()
    for r in cur.fetchall() or []:
        _rid = int(r[0])
        _bucket = by_review.setdefault(_rid, [])
        if len(_bucket) >= _PER_REVIEW_ROUND_CAP:
            truncated.add(_rid)
            continue
        _bucket.append({
            "round_index": int(r[1] or 0), "phase": r[2], "verdict": r[3],
            "findings": _as_json_list(r[4]),
            "block_count": int(r[5] or 0), "warn_count": int(r[6] or 0),
            "revise_method": r[7], "revise_axis": r[8],
            "tool_rounds": int(r[9] or 0),
            "answer_chars": (int(r[10]) if r[10] is not None else None),
            "note": r[11],
            "created_at": (r[12].isoformat() if r[12] else None),
        })
    for it in items:
        it["rounds"] = by_review.get(it["id"], [])
        it["rounds_truncated"] = it["id"] in truncated
    return True


@router.get("/api/admin/reasoning/redteam")
def admin_reasoning_redteam(
    request: Request,
    account=Depends(app.require_permission("console.reasoning.read", message=_PERM_MSG)),
) -> JSONResponse:
    """자가 적대 리뷰 활동 — 24h/7d 요약 통계 + **대화 단위** keyset 페이징.

    Query: cursor(대화 그룹 keyset — 이 값보다 오래된 last_id 를 가진 대화부터),
           limit(반환할 **대화 수**, 기본 12, 1~50).
    정렬: 대화는 최근 리뷰 순 desc, 대화 내 리뷰는 진행 순서 asc (회차 단계 그대로).
    각 리뷰에는 자가검증/재검증 회차 원장(`rounds`, 회차 asc)이 동봉된다.
    PG 미가용 시 부분 degrade."""
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
    conversations: list[dict] = []
    next_cursor = None
    stats: dict[str, Any] = {}
    pg_available = True
    # 회차 원장(0048) 가용 여부 — 부재 시 콘솔이 요약 기반 타임라인으로 폴백.
    rounds_available = False
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
                    # 0045 수렴 관측 요약 — 별도 try(컬럼 부재 stale 이미지에서 위 stats 와
                    # table_available 판정을 오염시키지 않는다).
                    if stats:
                        try:
                            cur.execute(
                                "SELECT COUNT(*) FILTER (WHERE unresolved_block_count > 0 "
                                "                        AND created_at >= now() - interval '7 days'), "
                                "       COALESCE(SUM(revision_rounds) FILTER "
                                "                (WHERE created_at >= now() - interval '7 days'), 0) "
                                "FROM agent_runtime.redteam_reviews"
                            )
                            _crow = cur.fetchone() or (0, 0)
                            stats["unresolved_7d"] = int(_crow[0] or 0)
                            stats["revision_rounds_7d"] = int(_crow[1] or 0)
                        except Exception:
                            try:
                                pg.rollback()
                            except Exception:
                                pass
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
                # 0045 수렴 관측 컬럼 존재 여부 — 동일 stale-image 방어.
                _has_convergence = True
                try:
                    cur.execute(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema='agent_runtime' AND table_name='redteam_reviews' "
                        "AND column_name='unresolved_block_count'"
                    )
                    _has_convergence = cur.fetchone() is not None
                except Exception:
                    _has_convergence = False
                try:
                    items, conversations, next_cursor = _query_conversation_page(
                        cur, cursor=cursor, conv_limit=limit,
                        per_conv_cap=_PER_CONV_REVIEW_CAP,
                        include_rederive=_has_rederive,
                        include_convergence=_has_convergence)
                except Exception:
                    # 테이블 부재/스키마 불일치 — 빈 목록과 구분해 table_available=False.
                    try:
                        pg.rollback()
                    except Exception:
                        pass
                    table_available = False
                # 회차 원장(0048) — 별도 try(테이블 부재 stale 이미지에서 목록 조회를
                # 오염시키지 않는다. 부재면 rounds=[] 로 남고 콘솔이 요약 폴백).
                if items:
                    try:
                        rounds_available = _attach_rounds(cur, items)
                    except Exception:
                        try:
                            pg.rollback()
                        except Exception:
                            pass
                        rounds_available = False
        except Exception:
            _log.debug("redteam reviews query failed", exc_info=True)
        finally:
            try:
                pg.close()
            except Exception:
                pass

    return JSONResponse({
        "stats": stats, "items": items, "conversations": conversations,
        "next_cursor": next_cursor, "pg_available": pg_available,
        "table_available": table_available, "rounds_available": rounds_available,
        "per_conversation_cap": _PER_CONV_REVIEW_CAP,
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
