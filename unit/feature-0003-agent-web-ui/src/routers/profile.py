"""feature-0012 P5b Final — profile 도메인 APIRouter (프로필 사용량/감사 조회).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Any

import app

INCLUDE_ORDER = 130  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/profile/usage/conversations")
def profile_usage_conversations(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0263: 본인 사용량 차트 클릭 → 본인 대화목록(작업 화면 프로필 모달).

    로그인만 필요(profile_llm_usage 와 동일 — 본인 소유 대화로 범위 강제, 신규 RBAC 0).
    owner_account_id = 로그인 계정으로 INNER 필터 → 타인 대화 노출 불가.
    """
    aid = int(account.get("id") or 0)
    if aid <= 0:
        return app._json_error("계정 식별 실패", 403)
    p = app._parse_usage_conv_params(request)
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        logging.getLogger(__name__).warning("profile_usage_conversations: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    try:
        # 본인 범위 강제 — role/account_id 파라미터 무시(권한 상승 차단), model/day 만 적용.
        items, truncated = app._query_usage_conversations(
            pg, days=p["days"], model=p["model"], account_ids=None,
            day_label=p["day_label"], gran=p["gran"], owner_account_id=aid,
            owner_is_null_ok=False,
        )
    finally:
        try:
            pg.close()
        except Exception:
            pass
    return JSONResponse({"items": items, "truncated": truncated,
                         "filter": {"days": p["days"], "gran": p["gran"], "model": p["model"], "day_label": p["day_label"]},
                         "scope": "self"})

@router.get("/api/profile/usage")
def profile_llm_usage(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0184: 본인 LLM 사용량 — 로그인 사용자 자신의 토큰/모델/요청 집계(간소판).

    admin_llm_usage(console.usage.read, admin 전용) 의 본인-범위 축소판. owner_account_id =
    로그인 계정으로 강제하고, 계정/역할 enrich·추정 비용은 제외한다(일반 사용자 화면에 단가
    비노출). 별도 RBAC 권한 없이 로그인만 요구 — 본인 소유 대화의 usage 로만 한정되므로
    권한 카탈로그 변경이 없다. 프로필 '사용 내역' 탭에서 사용.
    """
    aid = int(account["id"])
    try:
        days = int(request.query_params.get("days", "30"))
    except Exception:
        days = 30
    days = max(1, min(365, days))
    gran = request.query_params.get("gran", "day").lower()
    if gran not in app._USAGE_GRAN:
        gran = "day"
    gran_cfg = app._USAGE_GRAN[gran]
    bucket_expr = f"to_char(date_trunc('{gran}', u.created_at), '{gran_cfg['fmt']}')"
    bucket_limit = gran_cfg["limit"]
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        logging.getLogger(__name__).warning("profile_usage: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    try:
        win = f"now() - interval '{days} days'"
        # 본인 소유 대화로 한정 (INNER JOIN: owner 매칭 안 되는 insight/시스템 호출은 제외).
        base = (
            "FROM agent_runtime.llm_usage u "
            "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
            f"WHERE u.created_at >= {win} AND c.owner_account_id = %s"
        )
        with pg.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(count(*),0), COALESCE(sum(u.prompt_tokens),0), "
                "COALESCE(sum(u.completion_tokens),0), COALESCE(sum(u.total_tokens),0), "
                f"COALESCE(count(distinct u.run_id),0) {base}",
                (aid,),
            )
            t = cur.fetchone() or (0, 0, 0, 0, 0)
            totals = {"calls": int(t[0]), "prompt_tokens": int(t[1]),
                      "completion_tokens": int(t[2]), "total_tokens": int(t[3]),
                      "requests": int(t[4])}
            # TASK-0263: prompt/completion 합도 가져와 모델별 추정 비용(hover 표시). 본인 범위라 owner enrich 불요.
            cur.execute(
                "SELECT COALESCE(u.resolved_model, u.model) AS m, u.model, count(*), "
                f"sum(u.total_tokens), count(distinct u.run_id), sum(u.prompt_tokens), sum(u.completion_tokens) {base} "
                "GROUP BY COALESCE(u.resolved_model, u.model), u.model "
                "ORDER BY 4 DESC NULLS LAST LIMIT 50",
                (aid,),
            )
            by_model = [{"model": r[1], "resolved_model": r[0], "calls": int(r[2]),
                         "total_tokens": int(r[3] or 0), "requests": int(r[4] or 0),
                         "cost_usd": app._estimate_llm_cost_usd(r[1], int(r[5] or 0), int(r[6] or 0))}
                        for r in (cur.fetchall() or [])]
            cur.execute(
                f"SELECT {bucket_expr} AS b, count(*), sum(u.total_tokens) {base} "
                f"GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}",
                (aid,),
            )
            by_day = [{"day": r[0], "calls": int(r[1]), "total_tokens": int(r[2] or 0)}
                      for r in (cur.fetchall() or [])]
            cur.execute(
                f"SELECT {bucket_expr} AS b, COALESCE(u.resolved_model, u.model), sum(u.total_tokens), "
                f"sum(u.prompt_tokens), sum(u.completion_tokens) "
                f"{base} AND {bucket_expr} IN (SELECT {bucket_expr} {base} "
                f"GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}) GROUP BY 1, 2 ORDER BY 1",
                (aid, aid),
            )
            by_day_model = [{"day": r[0], "model": r[1], "total_tokens": int(r[2] or 0),
                             "cost_usd": app._estimate_llm_cost_usd(r[1], int(r[3] or 0), int(r[4] or 0))}
                            for r in (cur.fetchall() or [])]
            # TASK-0263: 본인 총 추정 비용(모델별 합).
            totals["cost_usd"] = round(sum(m.get("cost_usd", 0) for m in by_model), 4)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    return JSONResponse({
        "window_days": days,
        "granularity": gran,
        "totals": totals,
        "by_model": by_model,
        "by_day": by_day,
        "by_day_model": by_day_model,
    })

@router.get("/api/profile/audits")
def list_profile_audit_events(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """REQ-20260520-0004 (TASK-0089): 작업 화면 profile drawer 의 본인 audit row 조회.

    권한: `audit.read.own` 또는 `audit.read.any`. **backend 가 scope="own" 강제** —
    `.any` 보유자도 본인 row 만 조회 (admin 콘솔 `GET /api/admin/audits` 와 분리).
    Codex outside voice C2 — `.any` 가 drawer 에서 전체 audit 보이는 위험 차단.

    Query params: action_code / from_at / to_at / q / cursor / limit (admin endpoint 와 동일 schema,
    actor_account_id / actor_type 는 본인 한정이라 무시).

    Response: `{items: [...], next_cursor: <id>|None, scope: 'own'}`.
    """
    if not (
        app._account_has_permission(account, "audit.read.own")
        or app._account_has_permission(account, "audit.read.any")
    ):
        return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
    params = app._audit_parse_filter_params(request)
    cursor_id = app._audit_parse_cursor(params["cursor"])
    limit = app._audit_clamped_limit(params["limit"])
    # TASK-0089 (Codex C2): scope="own" 강제 — .any 보유자도 본인 row 만.
    where_clause, args = app._audit_compose_where(
        scope="own",
        account_id=int(account["id"]),
        params=params,
        cursor_id=cursor_id,
    )
    sql = (
        "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
        "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
        "RemoteAddr, UserAgent, RequestId, OccurredAt "
        f"FROM WebAuditEvents{where_clause} "
        "ORDER BY Id DESC LIMIT %s"
    )
    args.append(int(limit) + 1)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, tuple(args))
        rows = cur.fetchall() or []
    finally:
        cur.close()
    has_more = len(rows) > limit
    items = [app._audit_row_to_dict(r) for r in rows[:limit]]
    next_cursor = str(items[-1]["id"]) if has_more and items else None
    return JSONResponse({"items": items, "next_cursor": next_cursor, "scope": "own"})

@router.get("/api/profile/audits/{event_id}")
def get_profile_audit_event(event_id: int, request: Request) -> JSONResponse:
    """REQ-20260520-0004 (TASK-0089): profile drawer audit detail.

    `.own` 강제 (Actor = self — TASK-0293 Actor-only) — profile drawer 는 본인이 수행한
    행위만. 권한 부족 시 무조건 404 (byte-equal, metadata leak 차단).
    """
    if event_id <= 0:
        return app._json_error("invalid event_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not (
            app._account_has_permission(account, "audit.read.own")
            or app._account_has_permission(account, "audit.read.any")
        ):
            return app._json_error("감사 로그 조회 권한이 필요합니다.", 403)
        # TASK-0089: .own 강제 (admin endpoint 의 scope dependency 제거).
        cond, scope_args = app._audit_build_self_filter_sql(int(account["id"]))
        where_clause = f" WHERE Id = %s AND {cond}"
        args: list[Any] = [int(event_id)]
        args.extend(scope_args)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
                "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                "RemoteAddr, UserAgent, RequestId, OccurredAt "
                f"FROM WebAuditEvents{where_clause} LIMIT 1",
                tuple(args),
            )
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return app._json_error("audit event not found", 404)
        return JSONResponse({"item": app._audit_row_to_dict(row), "scope": "own"})
    finally:
        conn.close()
