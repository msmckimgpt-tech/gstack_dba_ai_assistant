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
from shared.model_catalog import canonical_usage_model, canonical_usage_model_sql

INCLUDE_ORDER = 30  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


# ITEM-10 routers-p11 이동분.
def _query_usage_conversations(pg, *, days: int, model: "str | None", account_ids: "list[int] | None",
                               day_label: "str | None", gran: str, owner_account_id: "int | None",
                               owner_is_null_ok: bool) -> "tuple[list[dict], bool]":
    """llm_usage ⋈ core_conversations 로 차원 필터된 대화 목록 + 대화별 기간내 usage 집계.

    필터(모두 AND, None=무시):
      - model: COALESCE(u.resolved_model, u.model) = model (차트 by_model 규칙과 동일)
      - account_ids: c.owner_account_id IN (...) — 역할 클릭은 그 역할 계정 집합을 호출측이 산출해 전달.
      - day_label: to_char(date_trunc(gran, u.created_at), fmt) = day_label (by_day 규칙과 동일)
      - owner_account_id: 본인 범위 강제(profile) — c.owner_account_id = owner_account_id.
    owner_is_null_ok=False 면 owner NULL(시스템) 대화 제외(profile·계정 클릭). True 면 "(시스템)" 역할
    클릭처럼 owner NULL 도 포함(account_ids 가 [None] 신호일 때 호출측이 별도 처리).

    반환: (items[{conversation_id, topic, owner_account_id, created_at, updated_at, blocked_at,
                  calls, total_tokens, prompt_tokens, completion_tokens, cost_usd, models[]}], truncated)
    conversation_id NOT NULL 강제(INNER JOIN) — insight/시스템 비대화 usage 제외.
    """
    # PG 는 `interval $1`(파라미터) 문법을 불허 → `%s::interval` 캐스트로 days 를 바인드한다
    # (admin_llm_usage 는 int 보간 `interval '{days} days'`; 여기선 캐스트로 파라미터화 유지).
    win = "now() - %s::interval"
    where = ["u.conversation_id IS NOT NULL", "u.created_at >= " + win]
    params: list = [f"{int(days)} days"]
    # 모델 필터는 canonical family 기준 — 도넛/차트 라벨(canonical_usage_model_sql)과 동일 규칙이라
    # 'claude-haiku-4' 클릭이 -interactive/-chat/실ID 변형 대화까지 모두 매칭(차트 수치 ↔ 대화목록 정합).
    if model:
        where.append(canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)") + " = %s")
        params.append(model)
    if account_ids is not None:
        # 빈 집합이면 결과 0 (역할에 계정이 없음).
        if not account_ids:
            return ([], False)
        ph = ",".join(["%s"] * len(account_ids))
        where.append(f"c.owner_account_id IN ({ph})")
        params.extend([int(a) for a in account_ids])
    if owner_account_id is not None:
        where.append("c.owner_account_id = %s")
        params.append(int(owner_account_id))
    elif not owner_is_null_ok:
        where.append("c.owner_account_id IS NOT NULL")
    if day_label:
        bucket_expr, _fmt = app._usage_bucket_match_sql(gran)
        where.append(f"{bucket_expr} = %s")
        params.append(day_label)
    where_sql = " AND ".join(where)
    # 대화별 × 모델 분해(모델 stacked·비용용) → Python fold. LIMIT 은 대화 수 기준(+1 로 truncated 감지).
    # 모델 분해 키도 canonical family — 대화 모달의 models[] 가 도넛과 동일 표기로 표시(라우팅 변형 미분점).
    _canon_m = canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)")
    sql = (
        "SELECT u.conversation_id, c.topic, c.owner_account_id, c.created_at, c.updated_at, "
        f"c.blocked_at, {_canon_m} AS m, count(*) AS calls, "
        "sum(u.total_tokens) AS tok, sum(u.prompt_tokens) AS pt, sum(u.completion_tokens) AS ct, "
        "max(u.created_at) AS last_used "
        "FROM agent_runtime.llm_usage u "
        "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
        f"WHERE {where_sql} "
        "GROUP BY u.conversation_id, c.topic, c.owner_account_id, c.created_at, c.updated_at, c.blocked_at, "
        f"{_canon_m}"
    )
    fold: dict = {}
    with pg.cursor() as cur:
        cur.execute(sql, tuple(params))
        for r in (cur.fetchall() or []):
            cid = r[0]
            e = fold.get(cid)
            if e is None:
                e = {
                    "conversation_id": cid, "topic": (r[1] or ""),
                    "owner_account_id": (int(r[2]) if r[2] is not None else None),
                    "created_at": (r[3].isoformat() if r[3] else None),
                    "updated_at": (r[4].isoformat() if r[4] else None),
                    "blocked": bool(r[5] is not None),
                    "calls": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
                    "cost_usd": 0.0, "_models": {}, "_last_used": r[11],
                }
                fold[cid] = e
            mk, calls_r = r[6], int(r[7] or 0)
            tok_r, pt_r, ct_r = int(r[8] or 0), int(r[9] or 0), int(r[10] or 0)
            e["calls"] += calls_r
            e["total_tokens"] += tok_r
            e["prompt_tokens"] += pt_r
            e["completion_tokens"] += ct_r
            mc = app._estimate_llm_cost_usd(mk, pt_r, ct_r)
            e["cost_usd"] += mc
            mm = e["_models"].setdefault(mk, {"model": mk, "total_tokens": 0, "cost_usd": 0.0})
            mm["total_tokens"] += tok_r
            mm["cost_usd"] += mc
            if r[11] and (e["_last_used"] is None or r[11] > e["_last_used"]):
                e["_last_used"] = r[11]
    items = list(fold.values())
    # 기간내 사용량(토큰) 큰 순 → 같은 집계에 가장 많이 기여한 대화 먼저.
    items.sort(key=lambda x: x["total_tokens"], reverse=True)
    truncated = len(items) > app._USAGE_CONV_LIMIT
    items = items[:app._USAGE_CONV_LIMIT]
    for e in items:
        e["cost_usd"] = round(e["cost_usd"], 4)
        e["models"] = sorted(e.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
        for m in e["models"]:
            m["cost_usd"] = round(m["cost_usd"], 4)
        e["last_used_at"] = (e.pop("_last_used").isoformat() if e.get("_last_used") else None)
    return (items, truncated)


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
            # usage-model-canonical: 실제 서빙 모델(COALESCE(resolved_model, model))을 canonical
            # family 로 접어 집계 → 라우팅 변형 alias(-interactive/-chat/-root)·실 모델 ID·gemma 폴백이
            # 한 논리 모델로 합쳐진다('모델별 비중' 도넛 중복 분점 해소). run_id distinct 도 canonical
            # 그룹 단위로 dedup 되어 요청 수 과대계상이 없다. model==resolved_model==canonical 로 채워
            # 프론트 modelKeyOf/도넛 라벨/색맵/드릴다운 필터가 동일 키로 정합(admin.js 무변경).
            _canon = canonical_usage_model_sql("COALESCE(resolved_model, model)")
            cur.execute(
                f"SELECT {_canon} AS m, count(*), sum(total_tokens), "
                f"sum(prompt_tokens), sum(completion_tokens), count(distinct run_id) "
                f"FROM agent_runtime.llm_usage "
                f"WHERE created_at >= {win} GROUP BY {_canon} "
                f"ORDER BY 3 DESC NULLS LAST LIMIT 50"
            )
            by_model = []
            for r in (cur.fetchall() or []):
                m = r[0]
                pt_m, ct_m = int(r[3] or 0), int(r[4] or 0)
                by_model.append({"model": m, "resolved_model": m, "calls": int(r[1]),
                                 "requests": int(r[5] or 0),
                                 "total_tokens": int(r[2] or 0), "prompt_tokens": pt_m,
                                 "completion_tokens": ct_m,
                                 "cost_usd": app._estimate_llm_cost_usd(m, pt_m, ct_m)})
            # TASK-0176: 계정 × 모델 분해 → 계정별 추정 비용 산출(비용은 모델별 단가라
            # 모델 분해 필수). Python 으로 계정별 fold(calls/tokens/cost). 역할별 비용은
            # _aggregate_usage_by_role 가 enrich 된 by_account 의 cost_usd 를 재합산.
            _canon_u = canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)")
            cur.execute(
                f"SELECT c.owner_account_id, {_canon_u}, count(*), "
                f"sum(u.total_tokens), sum(u.prompt_tokens), sum(u.completion_tokens) "
                f"FROM agent_runtime.llm_usage u "
                f"LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE u.created_at >= {win} GROUP BY c.owner_account_id, {_canon_u}"
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
                f"SELECT {bucket_expr} AS b, {_canon} , sum(total_tokens), "
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


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (4종). app 전역은 app.X 동적 참조. ====

def _estimate_llm_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    """TASK-0166: 모델 토큰 → 추정 비용(USD). 단가 미상(로컬/edge 등)은 0.

    usage-model-canonical: 단가 조회 키를 canonical family 로 접는다. 단가표
    (_LLM_PRICE_USD_PER_1M)는 base alias(claude-haiku-4/claude-sonnet-4)만 등록돼, 라우팅 변형
    (claude-haiku-4-chat/-interactive)이나 실 모델 ID(claude-haiku-4-5-20251001)가 그대로 들어오면
    미매칭으로 비용 $0 로 오표시되던 gap 이 있었다. canonical 화로 변형/실ID 도 올바른 단가로 계상되고,
    gemma 폴백(edge)은 canonical 'edge' → 단가 미등록 → 0(로컬 무료) 로 정직하게 남는다."""
    key = canonical_usage_model(model)
    p = app._LLM_PRICE_USD_PER_1M.get(key)
    if not p:
        return 0.0
    return round((prompt_tokens or 0) / 1e6 * p["in"] + (completion_tokens or 0) / 1e6 * p["out"], 4)

def _aggregate_usage_by_role(by_account: list[dict]) -> list[dict]:
    """TASK-0163: 계정별 LLM usage 를 역할별로 폴딩.

    account_id 가 None(insight 워커 등 owner 없는 시스템 호출) → "(시스템)" 버킷,
    계정은 있으나 역할 미지정(role NULL) → "(역할 없음)" 버킷. total_tokens desc 정렬.
    PG(usage)·MySQL(역할) cross-DB 라 SQL join 불가 → enrich 된 by_account 를 Python 집계.
    """
    buckets: dict[str, dict] = {}
    for row in by_account:
        if row.get("account_id") is None:
            key = "(시스템)"
        else:
            key = row.get("role") or "(역할 없음)"
        b = buckets.setdefault(key, {"role": key, "calls": 0, "requests": 0,
                                     "total_tokens": 0, "cost_usd": 0.0, "_models": {}})
        b["calls"] += int(row.get("calls") or 0)
        b["requests"] += int(row.get("requests") or 0)  # TASK-0181: 요청 수(distinct run_id) 합산
        b["total_tokens"] += int(row.get("total_tokens") or 0)
        b["cost_usd"] += float(row.get("cost_usd") or 0)  # TASK-0176: 역할별 추정 비용 합산
        # TASK-0181: 역할별 모델 분해(stacked 막대용) — 계정의 models[] 를 역할로 합산.
        for m in (row.get("models") or []):
            mm = b["_models"].setdefault(m["model"], {"model": m["model"], "total_tokens": 0, "cost_usd": 0.0})
            mm["total_tokens"] += int(m.get("total_tokens") or 0)
            mm["cost_usd"] += float(m.get("cost_usd") or 0)
    out = []
    for b in buckets.values():
        b["cost_usd"] = round(b["cost_usd"], 4)
        b["models"] = sorted(b.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
        for m in b["models"]:
            m["cost_usd"] = round(m["cost_usd"], 4)
        out.append(b)
    return sorted(out, key=lambda x: x["total_tokens"], reverse=True)

def _usage_bucket_match_sql(gran: str) -> "tuple[str, str]":
    """day 필터용 bucket 표현식 + 화이트리스트 검증된 to_char 포맷.

    admin_llm_usage 의 _USAGE_GRAN[gran]['fmt'] 와 동일 — 클릭한 일자 라벨(차트의 by_day[].day)이
    그 포맷 문자열이므로, 동일 to_char(date_trunc(...)) 로 매칭하면 차트 막대 ↔ 대화 정합.
    반환: (bucket_expr, fmt). gran 미허용 시 day 폴백.
    """
    g = gran if gran in app._USAGE_GRAN else "day"
    fmt = app._USAGE_GRAN[g]["fmt"]
    return (f"to_char(date_trunc('{g}', u.created_at), '{fmt}')", fmt)

def _enrich_usage_conv_owner_meta(conn, items: list[dict]) -> None:
    """대화 owner_account_id → 사용자명/역할 enrich(MySQL, 모달 표시용). in-place."""
    ids = sorted({e["owner_account_id"] for e in items if e.get("owner_account_id") is not None})
    if not ids:
        return
    meta: dict[int, dict] = {}
    try:
        ph = ",".join(["%s"] * len(ids))
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                f"SELECT a.Id AS id, a.Username AS username, r.Name AS role "
                f"FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId WHERE a.Id IN ({ph})",
                tuple(ids),
            )
            for m in (cur.fetchall() or []):
                meta[int(m["id"])] = {"username": m.get("username"), "role": m.get("role")}
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("usage_conversations: owner meta enrich failed", exc_info=True)
        return
    for e in items:
        mm = meta.get(e.get("owner_account_id")) if e.get("owner_account_id") is not None else None
        e["owner_username"] = (mm or {}).get("username")
        e["owner_role"] = (mm or {}).get("role")


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _usage_account_ids_for_role(conn, role_key: str) -> "list[int] | None":
    """역할 클릭(by_role 의 role 키) → 그 역할에 속한 account_id 집합(MySQL).

    by_role 규칙(_aggregate_usage_by_role)과 동일:
      "(시스템)"   → None (owner NULL 대화 = 비대화 usage. 대화목록에선 빈 집합 — 시스템 호출엔 대화 없음)
      "(역할 없음)" → RoleId NULL(또는 역할 매핑 실패) 계정들
      그 외        → WebRoles.Name == role_key 인 계정들
    반환: account_id 리스트(빈 리스트 가능) 또는 None(시스템 — 대화 없음).
    """
    if role_key == "(시스템)":
        return None
    cur = conn.cursor()
    try:
        if role_key == "(역할 없음)":
            cur.execute("SELECT a.Id FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId WHERE r.Name IS NULL")
        else:
            cur.execute("SELECT a.Id FROM WebAccounts a JOIN WebRoles r ON r.Id = a.RoleId WHERE r.Name = %s", (role_key,))
        return [int(row[0]) for row in (cur.fetchall() or [])]
    finally:
        cur.close()


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (2종). ====

# date_trunc granularity 화이트리스트 + 표시 포맷 + bucket 개수 상한(차트 막대 과밀 방지).
_USAGE_GRAN = {
    "hour":  {"fmt": "YYYY-MM-DD HH24:00", "limit": 168},
    "day":   {"fmt": "YYYY-MM-DD",          "limit": 90},
    "week":  {"fmt": "YYYY-MM-DD",          "limit": 53},
    "month": {"fmt": "YYYY-MM",             "limit": 36},
}

# TASK-0166: LLM 비용 추정 단가 (USD per 1M tokens). 로컬 LLM(edge/core/auto/code)=0.
# Bedrock claude 공시가 근사 — 정확 단가는 시점/리전별 변동하므로 운영자 참고용 "추정"이다.
# 별칭(model) 기준 매핑(LiteLLM 이 resolved_model 에도 별칭을 반환하는 경우가 많음).
_LLM_PRICE_USD_PER_1M = {
    "claude-haiku-4": {"in": 1.0, "out": 5.0},
    "claude-sonnet-4": {"in": 3.0, "out": 15.0},
    # opus5-model(2026-07-27): Opus 5 공시가 $5 / $25 per MTok. canonical family 키(claude-opus-5)와
    # 동일해 -chat/-chat-root 라우팅 변형·실 모델 ID 도 이 단가로 계상된다(단가 $0 오표시 gap 차단).
    "claude-opus-5": {"in": 5.0, "out": 25.0},
}
