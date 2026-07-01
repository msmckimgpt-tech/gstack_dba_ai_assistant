"""feature-0012 P5b Final — admin_sample_feedback 도메인 APIRouter (완전-DI 추출).

핸들러 3종(require_permission RP). 동반 테스트는 위치 전환(직접호출/getsource).
uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). byte-동치.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

router = APIRouter()


@router.get("/api/admin/sample-feedback")
def admin_list_sample_feedback(request: Request, account=Depends(app.require_permission("kb.sample.curate"))) -> JSONResponse:
    """검수 큐 — pending 샘플 피드백 목록. 권한: kb.sample.curate.

    PG(agent_kb) 의 sample_feedback(status='pending') 을 코어 list_pending_feedback 로 조회한다.
    generated_sql 은 적재 시점에 이미 PII 마스킹돼 저장됨(추가 마스킹 불필요). scope_key 쿼리로 ds 한정 가능.
    """

    scope_key = (request.query_params.get("scope_key") or "").strip() or None
    try:
        limit = int(request.query_params.get("limit", str(app._SAMPLE_FEEDBACK_LIMIT)))
    except Exception:
        limit = app._SAMPLE_FEEDBACK_LIMIT
    limit = max(1, min(app._SAMPLE_FEEDBACK_LIMIT, limit))

    from modules import sample_feedback as _sfb
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("피드백 저장소(PG) 연결 실패", 503)
    try:
        rows = _sfb.list_pending_feedback(pg, scope_key=scope_key, limit=limit)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_sample_feedback: 조회 실패", exc_info=True)
        return app._json_error("샘플 피드백 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass

    items: list[dict[str, Any]] = []
    for r in rows:
        # row: (id, scope_key, conversation_id, nl_question, generated_sql, vote, suggested, created_at)
        items.append({
            "id": int(r[0]),
            "scope_key": str(r[1] or ""),
            "conversation_id": (str(r[2]) if r[2] is not None else None),
            "nl_question": str(r[3] or ""),
            "generated_sql": str(r[4] or ""),
            "vote": str(r[5] or "up"),
            "suggested": bool(r[6]),
            "created_at": (r[7].isoformat() if hasattr(r[7], "isoformat") else (str(r[7]) if r[7] is not None else None)),
        })
    return JSONResponse({"items": items, "count": len(items), "truncated": len(items) >= limit})


@router.post("/api/admin/sample-feedback/{feedback_id}/approve")
async def admin_approve_sample_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission("kb.sample.curate"))) -> JSONResponse:
    """샘플 피드백 승급(promote) — sample_queries(approved=true, source_type='feedback'). 권한: kb.sample.curate.

    코어 promote_feedback(PG/agent_kb conn). 👎(down)/비-pending 은 승급 대상 아님(sample_id=None).
    embedding 미지정 → 코어가 titan-embed(1024-dim)로 임베딩. audit(memory conn) 분리 기록.
    """

    try:
        body_raw = await request.body()
        data = (await request.json()) if body_raw else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    domain = str(data.get("domain") or "").strip()
    try:
        weight = int(data.get("weight") or 100)
    except Exception:
        weight = 100
    weight = max(1, min(1000, weight))

    from modules import sample_feedback as _sfb
    from shared.db import _pg_connect
    try:
        # autocommit=False — register_sample(INSERT+임베딩) + status UPDATE 를 한 트랜잭션으로 묶어
        # 부분 적용(승급은 됐는데 status 미갱신, 또는 그 반대)을 방지(원자성). 실패 시 전체 rollback.
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("피드백 저장소(PG) 연결 실패", 503)
    try:
        sample_id = _sfb.promote_feedback(
            pg, feedback_id, approved_by=str((account or {}).get("username") or "") or None,
            weight=weight, domain=domain,
        )
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_approve_sample_feedback 실패 id=%s: %s", feedback_id, exc, exc_info=True)
        return app._json_error("샘플 승급 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass

    if sample_id is None:
        # 비-pending(이미 처리됨) 또는 👎(down, 승급 비대상). audit 없이 409 로 명시.
        return app._json_error("승급 대상이 아닙니다 (이미 처리되었거나 👎 피드백입니다).", 409)

    # same-tx 아닌 별도 memory conn 으로 audit (작업은 PG, audit 은 MySQL — cross-DB 분리).
    try:
        mconn = app._connect_memory()
        try:
            app.record_audit_event(
                mconn,
                actor=app._build_actor_from_request(request, account, actor_type="account"),
                action="sample.feedback.approve",
                resource_type="sample_feedback",
                resource_id=str(feedback_id),
                change_json={"promoted_sample_id": sample_id, "weight": weight, "domain": domain},
            )
            mconn.commit()
        finally:
            mconn.close()
    except Exception:
        logging.getLogger(__name__).warning("sample.feedback.approve audit 실패 id=%s", feedback_id, exc_info=True)

    return JSONResponse({"ok": True, "feedback_id": feedback_id, "sample_id": sample_id})


@router.post("/api/admin/sample-feedback/{feedback_id}/reject")
async def admin_reject_sample_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission("kb.sample.curate"))) -> JSONResponse:
    """샘플 피드백 거부(reject) — status='rejected'. sample_queries 미반영(poisoning 방어). 권한: kb.sample.curate."""

    from modules import sample_feedback as _sfb
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("피드백 저장소(PG) 연결 실패", 503)
    try:
        _sfb.reject_feedback(pg, feedback_id)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_reject_sample_feedback 실패 id=%s: %s", feedback_id, exc, exc_info=True)
        return app._json_error("샘플 거부 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass

    try:
        mconn = app._connect_memory()
        try:
            app.record_audit_event(
                mconn,
                actor=app._build_actor_from_request(request, account, actor_type="account"),
                action="sample.feedback.reject",
                resource_type="sample_feedback",
                resource_id=str(feedback_id),
                change_json={"status": "rejected"},
            )
            mconn.commit()
        finally:
            mconn.close()
    except Exception:
        logging.getLogger(__name__).warning("sample.feedback.reject audit 실패 id=%s", feedback_id, exc_info=True)

    return JSONResponse({"ok": True, "feedback_id": feedback_id})
