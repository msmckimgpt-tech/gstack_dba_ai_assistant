"""feature-0012 P5b Final — admin_quotas 도메인 APIRouter (완전-DI 추출).

핸들러 3종(require_permission RP). 동반 테스트는 위치 전환(직접호출/getsource).
uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). byte-동치.
"""
from __future__ import annotations


from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

INCLUDE_ORDER = 70  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/admin/quotas")
def admin_list_quotas(request: Request, actor=Depends(app.require_permission("console.access", "quota.read", message="LLM 사용 한도 조회 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """역할별 기본 + 계정별 특수 LLM 토큰 한도 목록.
    TASK-20260623T030418-quota-rbac-permission: 권한 quota.read(조회 전용 위임 가능)."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT r.Id AS role_id, r.RoleKey AS role_key, r.Name AS name, "
            "MAX(CASE WHEN q.QuotaType='daily' THEN q.TokenLimit END) AS daily, "
            "MAX(CASE WHEN q.QuotaType='monthly' THEN q.TokenLimit END) AS monthly "
            "FROM WebRoles r LEFT JOIN WebRoleTokenQuotas q ON q.RoleId = r.Id "
            "GROUP BY r.Id, r.RoleKey, r.Name ORDER BY r.Id"
        )
        roles = [
            {"role_id": int(x["role_id"]), "role_key": x.get("role_key"), "name": x.get("name"),
             "daily": int(x["daily"]) if x.get("daily") is not None else None,
             "monthly": int(x["monthly"]) if x.get("monthly") is not None else None}
            for x in (cur.fetchall() or [])
        ]
        cur.execute(
            "SELECT a.Id AS account_id, a.Username AS username, "
            "MAX(CASE WHEN q.QuotaType='daily' THEN q.TokenLimit END) AS daily, "
            "MAX(CASE WHEN q.QuotaType='monthly' THEN q.TokenLimit END) AS monthly "
            "FROM WebAccountTokenQuotas q JOIN WebAccounts a ON a.Id = q.AccountId "
            "GROUP BY a.Id, a.Username ORDER BY a.Username"
        )
        overrides = [
            {"account_id": int(x["account_id"]), "username": x.get("username"),
             "daily": int(x["daily"]) if x.get("daily") is not None else None,
             "monthly": int(x["monthly"]) if x.get("monthly") is not None else None}
            for x in (cur.fetchall() or [])
        ]
    finally:
        cur.close()
    return JSONResponse({"roles": roles, "account_overrides": overrides, "enforce": bool(app.LLM_QUOTA_ENFORCE)})


@router.put("/api/admin/quotas/role/{role_id}")
async def admin_set_role_quota(role_id: int, request: Request, actor=Depends(app.require_permission("console.access", "quota.read", "quota.manage", message="LLM 사용 한도 조절 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """역할 기본 LLM 토큰 한도 설정. body {daily?, monthly?} — null/생략=상속 해제, 0=무제한.
    TASK-20260623T030418-quota-rbac-permission: 권한 quota.manage(조절, quota.read 선행)."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    # TASK-20260623T030418-quota-rbac-permission (outside-voice MAJOR-2 흡수): "조절은 조회 종속"을
    #   서버에서 집행 — quota.manage 만으로 blind-write 불가. quota.read + quota.manage 동시 필요.
    cur = conn.cursor()
    try:
        cur.execute("SELECT RoleKey FROM WebRoles WHERE Id = %s LIMIT 1", (int(role_id),))
        rr = cur.fetchone()
    finally:
        cur.close()
    if not rr:
        return app._json_error("role not found", 404)
    daily = app._quota_parse_limit(data.get("daily"))
    monthly = app._quota_parse_limit(data.get("monthly"))
    try:
        app._quota_upsert(conn, "WebRoleTokenQuotas", "RoleId", int(role_id), daily, monthly)
    except Exception:
        return app._json_error("한도 저장에 실패했습니다.", 500)
    try:
        app._audit_admin_mutation(
            conn, request, actor, action="quota.role.update", resource_type="role",
            resource_id=str(role_id), before=None, after=None,
            request_ctx={"role_id": int(role_id), "daily": daily, "monthly": monthly},
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    return JSONResponse({"ok": True, "role_id": int(role_id), "daily": daily, "monthly": monthly})


@router.put("/api/admin/quotas/account/{account_id}")
async def admin_set_account_quota(account_id: int, request: Request, actor=Depends(app.require_permission("console.access", "quota.read", "quota.manage", message="LLM 사용 한도 조절 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """계정 특수(override) LLM 토큰 한도. body {daily?, monthly?} — null/생략=override 해제(역할 상속).
    TASK-20260623T030418-quota-rbac-permission: 권한 quota.manage(조절, quota.read 선행)."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    # TASK-20260623T030418-quota-rbac-permission (outside-voice MAJOR-2 흡수): 조절은 조회 종속.
    target = app._load_account_by_id(conn, int(account_id))
    if not target:
        return app._json_error("account not found", 404)
    daily = app._quota_parse_limit(data.get("daily"))
    monthly = app._quota_parse_limit(data.get("monthly"))
    try:
        app._quota_upsert(conn, "WebAccountTokenQuotas", "AccountId", int(account_id), daily, monthly)
    except Exception:
        return app._json_error("한도 저장에 실패했습니다.", 500)
    try:
        app._audit_admin_mutation(
            conn, request, actor, action="quota.account.update", resource_type="account",
            resource_id=str(account_id), before=None, after=None,
            request_ctx={"account_id": int(account_id), "daily": daily, "monthly": monthly},
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    return JSONResponse({"ok": True, "account_id": int(account_id), "daily": daily, "monthly": monthly})


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (4종). app 전역은 app.X 동적 참조. ====

def _quota_upsert(conn, table: str, key_col: str, key_id: int, daily, monthly) -> None:
    """role/account 한도 upsert. 값이 None 이면 해당 QuotaType 행 삭제(상속으로 복귀).
    table/key_col 은 코드 상수만(엔드포인트가 고정 전달) — SQL injection 무관."""
    cur = conn.cursor()
    try:
        for qtype, val in (("daily", daily), ("monthly", monthly)):
            if val is None:
                cur.execute(
                    f"DELETE FROM {table} WHERE {key_col} = %s AND QuotaType = %s",
                    (int(key_id), qtype),
                )
            else:
                cur.execute(
                    f"INSERT INTO {table} ({key_col}, QuotaType, TokenLimit) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE TokenLimit = VALUES(TokenLimit)",
                    (int(key_id), qtype, max(0, int(val))),
                )
    finally:
        cur.close()

def _quota_parse_limit(raw) -> "int | None":
    """body 값 → 한도 int. None/빈값/음수 = None(상속/해제). 0 = 무제한(명시)."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    try:
        v = int(raw)
    except Exception:
        return None
    if v < 0:
        return None  # 음수 = 무효 → 상속/해제 취급
    return min(v, 9_000_000_000_000_000)  # BIGINT 안전 상한 clamp (overflow 500 방지, outside-voice MINOR)

def _account_effective_quota(conn, account_id: int, role_id: int, quota_type: str) -> "int | None":
    """계정 override → 역할 기본 → None(무제한) 순 유효 한도. 0=무제한(명시). (보안 ④)"""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT TokenLimit FROM WebAccountTokenQuotas WHERE AccountId = %s AND QuotaType = %s LIMIT 1",
            (int(account_id), str(quota_type)),
        )
        r = cur.fetchone()
        if r is not None:
            return int(r[0] or 0)
        if role_id:
            cur.execute(
                "SELECT TokenLimit FROM WebRoleTokenQuotas WHERE RoleId = %s AND QuotaType = %s LIMIT 1",
                (int(role_id), str(quota_type)),
            )
            rr = cur.fetchone()
            if rr is not None:
                return int(rr[0] or 0)
        return None
    finally:
        cur.close()

def _account_period_usage_tokens(account_id: int, quota_type: str) -> int:
    """PG agent_runtime.llm_usage 에서 본인 소유 대화의 토큰 합 — 'daily'=달력 당일,
    'monthly'=달력 당월(date_trunc). best-effort(실패 시 0=무제한 취급, fail-open)."""
    trunc = "day" if quota_type == "daily" else "month"
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        return 0
    try:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(sum(u.total_tokens), 0) "
                "FROM agent_runtime.llm_usage u "
                "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE c.owner_account_id = %s AND u.created_at >= date_trunc('{trunc}', now())",
                (int(account_id),),
            )
            row = cur.fetchone()
            return int((row[0] if row else 0) or 0)
    except Exception:
        return 0
    finally:
        try:
            pg.close()
        except Exception:
            pass


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _check_account_token_quota(conn, account: dict) -> "tuple[bool, str]":
    """LLM 사용량 한도 사전 게이트. (allowed, error_message). 무제한/미설정/인프라장애=allowed.
    enforce 킬스위치 OFF 면 무조건 allowed. (보안 ④, fail-open)"""
    if not app.LLM_QUOTA_ENFORCE or not account:
        return (True, "")
    account_id = int(account.get("id") or 0)
    role_id = int(account.get("role_id") or 0)
    if account_id <= 0:
        return (True, "")
    _label = {"daily": "일일", "monthly": "월간"}
    for qtype in app._LLM_QUOTA_TYPES:
        try:
            limit = app._account_effective_quota(conn, account_id, role_id, qtype)
        except Exception:
            limit = None
        if not limit or int(limit) <= 0:
            continue  # 무제한/미설정
        used = app._account_period_usage_tokens(account_id, qtype)
        if used >= int(limit):
            # 주체 구분: "계정의 ... 한도" 로 명시 — 서비스 자체 요청량 한도
            # (llm_provider_health KIND_THROTTLED)와 도달 주체를 구분한다.
            return (
                False,
                f"계정의 {_label.get(qtype, qtype)} LLM 토큰 사용 한도({int(limit):,})를 초과했습니다. "
                f"현재 사용량 {int(used):,}. 관리자에게 문의하거나 한도 초기화 시점까지 기다려 주세요.",
            )
    return (True, "")
