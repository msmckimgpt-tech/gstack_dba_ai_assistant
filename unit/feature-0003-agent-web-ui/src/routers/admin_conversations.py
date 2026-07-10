"""feature-0012 P5b Final — admin_conversations 도메인 APIRouter (보관 대화 감사).

NS-BOUND=0(검증): 동반 테스트(test_conversation_archive.py::test_p1_admin_archived_requires_perm)는
TestClient + as_account override 로 호출(핸들러 직접참조 0, app.<handler> monkeypatch 0).
require_permission/get_conn 은 DI seam 객체(dependency_overrides 객체키 cross-module 안전).

순환 안전: app 이 모든 정의 후 맨 끝 include_router. DI seam 함수(require_permission/get_conn)는
객체 동일성이 dependency_overrides 정합에 필요하므로 `from app import`(미디어 라우터와 동일 규약).
_json_error/_ARCHIVED_CONV_LIMIT 은 monkeypatch 대상 아님(검증). 경로/메서드/응답·SQL byte-동치.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from app import require_permission, get_conn, _json_error, _ARCHIVED_CONV_LIMIT

INCLUDE_ORDER = 20  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/admin/conversations/archived")
def admin_archived_conversations(request: Request, account=Depends(require_permission("conversation.archive.read.any", message="보관 대화 조회 권한이 필요합니다 (conversation.archive.read.any).")), conn=Depends(get_conn)) -> JSONResponse:
    """보관된 대화 목록(admin 감사). 권한: conversation.archive.read.any.

    PG 정본(agent_runtime.core_conversations, archived_at IS NOT NULL) + MySQL 계정 메타 enrich.
    메타만 반환(제목/소유자/보관시각/보관자) — 메시지 본문 미포함. q 검색·limit(≤500) 지원.
    """
    q = (request.query_params.get("q") or "").strip()
    try:
        limit = int(request.query_params.get("limit", str(_ARCHIVED_CONV_LIMIT)))
    except Exception:
        limit = _ARCHIVED_CONV_LIMIT
    limit = max(1, min(_ARCHIVED_CONV_LIMIT, limit))

    items: list[dict[str, Any]] = []
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
        except Exception:
            logging.getLogger(__name__).warning("admin_archived: pg connect failed", exc_info=True)
            return _json_error("대화 저장소(PG) 연결 실패", 503)
        try:
            where = ["c.archived_at IS NOT NULL"]
            params: list[Any] = []
            if q:
                where.append("(c.topic ILIKE %s OR c.conversation_id ILIKE %s)")
                params.extend([f"%{q}%", f"%{q}%"])
            sql = (
                "SELECT c.conversation_id, COALESCE(NULLIF(TRIM(c.topic),''),'(제목 없음)'), "
                "c.owner_account_id, c.created_at, c.updated_at, c.archived_at, "
                "c.archived_by_account_id, c.product_id "
                "FROM agent_runtime.core_conversations c "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY c.archived_at DESC LIMIT %s"
            )
            params.append(limit)
            with pg.cursor() as pgcur:
                pgcur.execute(sql, tuple(params))
                for r in (pgcur.fetchall() or []):
                    items.append({
                        "conversation_id": str(r[0]),
                        "topic": str(r[1] or ""),
                        "owner_account_id": (int(r[2]) if r[2] is not None else None),
                        "created_at": (r[3].isoformat() if r[3] else None),
                        "updated_at": (r[4].isoformat() if r[4] else None),
                        "archived_at": (r[5].isoformat() if r[5] else None),
                        "archived_by_account_id": (int(r[6]) if r[6] is not None else None),
                        "product_id": (int(r[7]) if r[7] is not None else None),
                    })
        finally:
            try:
                pg.close()
            except Exception:
                pass
    else:
        # MySQL 폴백.
        try:
            cur = conn.cursor(dictionary=True)
            try:
                where = ["c.archived_at IS NOT NULL"]
                params2: list[Any] = []
                if q:
                    where.append("(c.topic LIKE %s OR c.conversation_id LIKE %s)")
                    params2.extend([f"%{q}%", f"%{q}%"])
                cur.execute(
                    "SELECT c.conversation_id, c.topic, c.owner_account_id, c.created_at, "
                    "c.updated_at, c.archived_at, c.archived_by_account_id, c.product_id "
                    "FROM AgentCoreConversations c "
                    f"WHERE {' AND '.join(where)} ORDER BY c.archived_at DESC LIMIT %s",
                    tuple(params2) + (limit,),
                )
                for m in (cur.fetchall() or []):
                    items.append({
                        "conversation_id": str(m.get("conversation_id") or ""),
                        "topic": str(m.get("topic") or "(제목 없음)"),
                        "owner_account_id": (int(m["owner_account_id"]) if m.get("owner_account_id") is not None else None),
                        "created_at": str(m.get("created_at") or ""),
                        "updated_at": str(m.get("updated_at") or ""),
                        "archived_at": str(m.get("archived_at") or ""),
                        "archived_by_account_id": (int(m["archived_by_account_id"]) if m.get("archived_by_account_id") is not None else None),
                        "product_id": (int(m["product_id"]) if m.get("product_id") is not None else None),
                    })
            finally:
                cur.close()
        except Exception:
            logging.getLogger(__name__).warning("admin_archived: MySQL query failed", exc_info=True)
            return _json_error("대화 저장소 조회 실패", 503)

    # 계정 메타(소유자/보관자 사용자명) enrich (MySQL).
    acct_ids = sorted({i for e in items for i in (e.get("owner_account_id"), e.get("archived_by_account_id")) if i is not None})
    meta: dict[int, str] = {}
    if acct_ids:
        try:
            ph = ",".join(["%s"] * len(acct_ids))
            mcur = conn.cursor(dictionary=True)
            try:
                mcur.execute(f"SELECT Id, Username FROM WebAccounts WHERE Id IN ({ph})", tuple(acct_ids))
                for m in (mcur.fetchall() or []):
                    meta[int(m["Id"])] = str(m.get("Username") or "")
            finally:
                mcur.close()
        except Exception:
            logging.getLogger(__name__).warning("admin_archived: owner meta enrich failed", exc_info=True)
    for e in items:
        e["owner_username"] = meta.get(e.get("owner_account_id")) if e.get("owner_account_id") is not None else None
        e["archived_by_username"] = meta.get(e.get("archived_by_account_id")) if e.get("archived_by_account_id") is not None else None
    return JSONResponse({"items": items, "count": len(items), "truncated": len(items) >= limit})
