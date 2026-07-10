"""feature-0012 P5b Final — admin_usage 도메인 APIRouter (LLM 사용량/비용 집계 + 사용량 대화목록).

MIXED 도메인: admin_llm_usage(RP require_permission console.usage.read) + admin_usage_conversations
(AO get_current_account + 본문 _account_has_permission 2-perm 검사). 동반 테스트
(test_usage_conversations.py)가 핸들러 직접호출(account/conn 명시) + app.<helper> monkeypatch
(_query_usage_conversations·_usage_account_ids_for_role)를 쓰므로, 본 라우터는 **uniform
`import app`+호출시 `app.X` 동적 속성 접근**으로 작성한다(import-time 복사 아님 → monkeypatch 보존).
DI seam(require_permission/get_conn/get_current_account)도 `Depends(app.X)` — app 정본과 동일 객체라
dependency_overrides(객체키) 정합. _pg_connect 는 본문 내 shared.db import 유지(app 아님).
순환 안전: app 정의 후 맨 끝 include_router. 경로/메서드/응답·SQL·403 메시지 byte-동치.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

INCLUDE_ORDER = 30  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/admin/usage")
def admin_llm_usage(request: Request, account=Depends(app.require_permission("console.usage.read", message="LLM 사용량 조회 권한이 필요합니다 (운영자 전용).")), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0136 (#11): LLM 토큰 사용량/비용 집계 — admin 한정(console.usage.read).

    감사 #11/cost gap: ~128 step frontier 호출에 비용 가시성이 전무했다. 모든 LLM 호출이
    agent_runtime.llm_usage 에 기록되며 본 endpoint 가 기간(days)별 총합 + 모델별 + 계정별
    (conversation→owner join) + 일별 집계를 반환. 운영·비용 민감 정보이므로 일반 사용자에게
    노출하지 않는다(권한 console.usage.read = admin 전용).

    Query: days (기본 30, 1~365). Response: {window_days, totals, by_model, by_account, by_day}.
    """
    try:
        days = int(request.query_params.get("days", "30"))
    except Exception:
        days = 30
    days = max(1, min(365, days))
    # TASK-0166: granularity (시/일/주/월). date_trunc 단위는 화이트리스트로만 SQL 삽입.
    gran = request.query_params.get("gran", "day").lower()
    if gran not in app._USAGE_GRAN:
        gran = "day"
    gran_cfg = app._USAGE_GRAN[gran]
    bucket_expr = f"to_char(date_trunc('{gran}', created_at), '{gran_cfg['fmt']}')"
    bucket_limit = gran_cfg["limit"]
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception as exc:
        logging.getLogger(__name__).warning("admin_usage: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    try:
        win = f"now() - interval '{days} days'"
        with pg.cursor() as cur:
            # TASK-0181: requests = 작업 화면에서 보낸 요청 수(distinct run_id; NULL=insight 등 제외).
            cur.execute(
                f"SELECT COALESCE(count(*),0), COALESCE(sum(prompt_tokens),0), "
                f"COALESCE(sum(completion_tokens),0), COALESCE(sum(total_tokens),0), "
                f"COALESCE(count(distinct run_id),0) "
                f"FROM agent_runtime.llm_usage WHERE created_at >= {win}"
            )
            t = cur.fetchone() or (0, 0, 0, 0, 0)
            totals = {"calls": int(t[0]), "prompt_tokens": int(t[1]),
                      "completion_tokens": int(t[2]), "total_tokens": int(t[3]),
                      "requests": int(t[4])}
            # TASK-0163: resolved_model(실제 서빙 모델, LiteLLM 해소 결과) 기준으로
            # 집계하되 요청 별칭(model)도 함께 노출 → claude 계열 식별 + 별칭 추적.
            cur.execute(
                f"SELECT COALESCE(resolved_model, model) AS m, model, count(*), sum(total_tokens), "
                f"sum(prompt_tokens), sum(completion_tokens), count(distinct run_id) "
                f"FROM agent_runtime.llm_usage "
                f"WHERE created_at >= {win} GROUP BY COALESCE(resolved_model, model), model "
                f"ORDER BY 4 DESC NULLS LAST LIMIT 50"
            )
            by_model = []
            for r in (cur.fetchall() or []):
                pt_m, ct_m = int(r[4] or 0), int(r[5] or 0)
                by_model.append({"model": r[1], "resolved_model": r[0], "calls": int(r[2]),
                                 "requests": int(r[6] or 0),
                                 "total_tokens": int(r[3] or 0), "prompt_tokens": pt_m,
                                 "completion_tokens": ct_m,
                                 "cost_usd": app._estimate_llm_cost_usd(r[1], pt_m, ct_m)})
            # TASK-0176: 계정 × 모델 분해 → 계정별 추정 비용 산출(비용은 모델별 단가라
            # 모델 분해 필수). Python 으로 계정별 fold(calls/tokens/cost). 역할별 비용은
            # _aggregate_usage_by_role 가 enrich 된 by_account 의 cost_usd 를 재합산.
            cur.execute(
                f"SELECT c.owner_account_id, COALESCE(u.resolved_model, u.model), count(*), "
                f"sum(u.total_tokens), sum(u.prompt_tokens), sum(u.completion_tokens) "
                f"FROM agent_runtime.llm_usage u "
                f"LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE u.created_at >= {win} GROUP BY c.owner_account_id, COALESCE(u.resolved_model, u.model)"
            )
            _acct_fold: dict = {}
            for r in (cur.fetchall() or []):
                aid = int(r[0]) if r[0] is not None else None
                mk, calls_r, tok_r, pt_r, ct_r = r[1], int(r[2]), int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)
                e = _acct_fold.setdefault(aid, {"account_id": aid, "calls": 0, "total_tokens": 0, "cost_usd": 0.0, "_models": {}})
                e["calls"] += calls_r
                e["total_tokens"] += tok_r
                mc = app._estimate_llm_cost_usd(mk, pt_r, ct_r)
                e["cost_usd"] += mc
                # TASK-0181: 계정 × 모델 분해 보존(stacked 막대용).
                mm = e["_models"].setdefault(mk, {"model": mk, "total_tokens": 0, "cost_usd": 0.0})
                mm["total_tokens"] += tok_r
                mm["cost_usd"] += mc
            # TASK-0181: 계정별 요청 수(distinct run_id; run 은 conversation=계정 단위, NULL 제외).
            cur.execute(
                f"SELECT c.owner_account_id, count(distinct u.run_id) "
                f"FROM agent_runtime.llm_usage u "
                f"LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE u.created_at >= {win} AND u.run_id IS NOT NULL GROUP BY 1"
            )
            _acct_req = {(int(r[0]) if r[0] is not None else None): int(r[1]) for r in (cur.fetchall() or [])}
            by_account = sorted(_acct_fold.values(), key=lambda x: x["total_tokens"], reverse=True)[:100]
            for a in by_account:
                a["cost_usd"] = round(a["cost_usd"], 4)
                a["requests"] = _acct_req.get(a["account_id"], 0)
                a["models"] = sorted(a.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
                for m in a["models"]:
                    m["cost_usd"] = round(m["cost_usd"], 4)
            # TASK-0166: granularity bucket(시/일/주/월) 시계열 — 호출/토큰/prompt/completion.
            cur.execute(
                f"SELECT {bucket_expr} AS b, count(*), sum(total_tokens), "
                f"sum(prompt_tokens), sum(completion_tokens) FROM agent_runtime.llm_usage "
                f"WHERE created_at >= {win} GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}"
            )
            by_day = [{"day": r[0], "calls": int(r[1]), "total_tokens": int(r[2] or 0),
                       "prompt_tokens": int(r[3] or 0), "completion_tokens": int(r[4] or 0)}
                      for r in (cur.fetchall() or [])]
            # TASK-0164/0166: bucket × 모델 분해 (stacked bar). 최근 bucket_limit 버킷만
            # (서브쿼리로 by_day 와 동일 버킷 집합 보장 → 차트 정합).
            # TASK-0263: prompt/completion 합도 가져와 모델별 추정 비용(cost_usd) 산출 → hover 표시.
            cur.execute(
                f"SELECT {bucket_expr} AS b, COALESCE(resolved_model, model), sum(total_tokens), "
                f"sum(prompt_tokens), sum(completion_tokens) "
                f"FROM agent_runtime.llm_usage WHERE created_at >= {win} "
                f"AND {bucket_expr} IN (SELECT {bucket_expr} FROM agent_runtime.llm_usage "
                f"WHERE created_at >= {win} GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}) "
                f"GROUP BY 1, 2 ORDER BY 1"
            )
            by_day_model = [{"day": r[0], "model": r[1], "total_tokens": int(r[2] or 0),
                             "cost_usd": app._estimate_llm_cost_usd(r[1], int(r[3] or 0), int(r[4] or 0))}
                            for r in (cur.fetchall() or [])]
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # TASK-0163: 계정 ID → 사용자명·역할 매핑(MySQL, cross-DB) + 역할별 집계.
    # usage 는 PG·계정/역할은 MySQL 이라 SQL join 불가 → Python 으로 enrich/fold.
    acct_ids = [row["account_id"] for row in by_account if row["account_id"] is not None]
    acct_meta: dict[int, dict] = {}
    if acct_ids:
        try:
            placeholders = ",".join(["%s"] * len(acct_ids))
            mcur = conn.cursor(dictionary=True)
            try:
                mcur.execute(
                    f"SELECT a.Id AS id, a.Username AS username, r.Name AS role "
                    f"FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId "
                    f"WHERE a.Id IN ({placeholders})",
                    tuple(acct_ids),
                )
                for m in (mcur.fetchall() or []):
                    acct_meta[int(m["id"])] = {"username": m.get("username"), "role": m.get("role")}
            finally:
                mcur.close()
        except Exception:
            logging.getLogger(__name__).warning("admin_usage: role enrichment failed", exc_info=True)
    for row in by_account:
        meta = acct_meta.get(row["account_id"]) if row["account_id"] is not None else None
        row["username"] = (meta or {}).get("username")
        row["role"] = (meta or {}).get("role")
    by_role = app._aggregate_usage_by_role(by_account)
    # TASK-0166: 총 추정 비용 = 모델별 추정 비용 합(단가 미상 로컬은 0).
    totals["cost_usd"] = round(sum(m.get("cost_usd", 0) for m in by_model), 4)
    return JSONResponse({
        "window_days": days,
        "granularity": gran,
        "totals": totals,
        "by_model": by_model,
        "by_account": by_account,
        "by_role": by_role,
        "by_day": by_day,
        "by_day_model": by_day_model,
    })


@router.get("/api/admin/usage/conversations")
def admin_usage_conversations(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0263: 사용량 차트 클릭 → 집계 기여 대화목록(admin 콘솔 모달).

    권한: console.usage.read(사용량 조회) + conversation.list.any(타 계정 대화목록 열람).
    둘 다 필요 — 사용량은 admin 인데 대화목록 열람 권한이 없는 운영자에게 타 계정 대화
    제목을 노출하지 않기 위함(기존 RBAC 재사용, 신규 권한 0). 대화 메타(제목/일시/소유자/
    기간내 usage)만 반환 — 메시지 본문 미포함.
    """
    if not app._account_has_permission(account, "console.usage.read"):
        return app._json_error("LLM 사용량 조회 권한이 필요합니다 (운영자 전용).", 403)
    if not app._account_has_permission(account, "conversation.list.any"):
        return app._json_error("전체 대화목록 열람 권한이 필요합니다 (conversation.list.any).", 403)
    p = app._parse_usage_conv_params(request)
    # 역할 클릭 → 계정 집합 역매핑(MySQL). 모델/일자 클릭은 account 필터 없음.
    account_ids = None
    if p["account_id"] is not None:
        account_ids = [p["account_id"]]
    elif p["role"] is not None:
        account_ids = app._usage_account_ids_for_role(conn, p["role"])
        if account_ids is None:
            # "(시스템)" 역할 — owner 없는 비대화 usage. 대화목록 비어있음.
            return JSONResponse({"items": [], "truncated": False, "filter": p, "scope": "admin"})
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        logging.getLogger(__name__).warning("admin_usage_conversations: pg connect failed", exc_info=True)
        return app._json_error("usage 저장소(PG) 연결 실패", 503)
    try:
        items, truncated = app._query_usage_conversations(
            pg, days=p["days"], model=p["model"], account_ids=account_ids,
            day_label=p["day_label"], gran=p["gran"], owner_account_id=None,
            owner_is_null_ok=False,
        )
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # 계정 메타(사용자명/역할) enrich — 모달 표시용(cross-DB, MySQL).
    app._enrich_usage_conv_owner_meta(conn, items)
    return JSONResponse({"items": items, "truncated": truncated, "filter": p, "scope": "admin"})
