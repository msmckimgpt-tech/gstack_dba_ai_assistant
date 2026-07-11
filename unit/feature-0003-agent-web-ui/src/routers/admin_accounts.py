"""feature-0012 P5b Final — admin_accounts 도메인 APIRouter (계정 관리(아바타/잠금/TOTP)).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import JSONResponse

from collections.abc import Iterable

import app

INCLUDE_ORDER = 170  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.put("/api/admin/accounts/{account_id}/avatar")
async def admin_upload_account_avatar(account_id: int, request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """관리자가 대상 계정의 프로필 아바타 업로드(console.manage + account.update). 이전 아바타 교체."""
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        actor, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
            return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
        if not app._account_has_permission(actor, "account.update"):
            return app._json_error("계정 수정 권한이 필요합니다 (account.update).", 403)
        target = app._load_account_by_id(conn, account_id)
        if not target:
            return app._json_error("account not found", 404)
        if target.get("deleted_at"):
            return app._json_error("삭제된 계정은 수정할 수 없습니다.", 400)
        body = await file.read()
        object_key, info = app._store_image_upload(
            body, prefix="avatars", owner_id=int(account_id), max_bytes=app._AVATAR_MAX_BYTES,
            mime_hint=(file.content_type or ""),
        )
        if not object_key:
            return app._json_error(info, 400)
        cur = conn.cursor()
        try:
            cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (int(account_id),))
            row = cur.fetchone()
            old_key = row[0] if row else None
            cur.execute("UPDATE WebAccounts SET AvatarObjectKey = %s WHERE Id = %s", (object_key, int(account_id)))
            conn.commit()
        finally:
            cur.close()
        if old_key and old_key != object_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "avatar_url": app._avatar_url_for(int(account_id), object_key)})
    finally:
        conn.close()

@router.delete("/api/admin/accounts/{account_id}/avatar")
def admin_delete_account_avatar(account_id: int, request: Request) -> JSONResponse:
    """관리자가 대상 계정의 아바타 제거(console.manage + account.update) → Identicon 폴백."""
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        actor, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
            return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
        if not app._account_has_permission(actor, "account.update"):
            return app._json_error("계정 수정 권한이 필요합니다 (account.update).", 403)
        target = app._load_account_by_id(conn, account_id)
        if not target:
            return app._json_error("account not found", 404)
        cur = conn.cursor()
        try:
            cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (int(account_id),))
            row = cur.fetchone()
            old_key = row[0] if row else None
            cur.execute("UPDATE WebAccounts SET AvatarObjectKey = NULL WHERE Id = %s", (int(account_id),))
            conn.commit()
        finally:
            cur.close()
        if old_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "avatar_url": None})
    finally:
        conn.close()

@router.get("/api/admin/accounts")
def admin_accounts(request: Request, account=Depends(app.require_permission("console.access", "account.read", message="관리 콘솔 조회 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    accounts = app._list_admin_accounts(conn)
    # TASK-20260623T030418-quota-rbac-permission: quota.read 미보유 actor 에는 한도 필드 비노출.
    app._strip_quota_fields_if_unpermitted(accounts, account)
    summary = {
        "total": len(accounts),
        "active": sum(1 for item in accounts if item.get("is_active") and not item.get("deleted_at")),
        "inactive": sum(1 for item in accounts if not item.get("is_active") and not item.get("deleted_at")),
        "deleted": sum(1 for item in accounts if item.get("deleted_at")),
        "management": sum(1 for item in accounts if app._is_management_permission_set(item.get("permissions"))),
    }
    return JSONResponse({"accounts": accounts, "summary": summary})

@router.patch("/api/admin/accounts/{account_id}")
async def admin_update_account(
    account_id: int,
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch11: _require_account→account+conn 완전 DI. perm·escalation·override·survivor 본문 유지.
    # get_conn finally:close 가 _load_account_by_id·_role_grant_excess·override·UPDATE·audit raise 시 leak 해소.
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.update"):
        return app._json_error("계정 수정 권한이 필요합니다.", 403)
    target = app._load_account_by_id(conn, account_id)
    if not target:
        return app._json_error("account not found", 404)
    if target.get("deleted_at"):
        return app._json_error("삭제된 계정은 수정할 수 없습니다.", 400)

    # TASK-0052 Phase 1C 작업 중 발견된 pre-existing 버그 fix:
    # `target` 은 _fetch_account_rows 결과로 role_id / role_key 등이 flat key 로 들어 있다.
    # `target.get("role")` 은 항상 None 이라 next_role_id 가 0 으로 떨어져 PATCH 마다 RoleId=0 으로
    # 덮어써졌음 (admin role 손실 → 권한 lockout). 직접 role_id 키를 사용한다.
    next_role_id = int(data.get("role_id") or target.get("role_id") or 0)
    next_is_active = bool(data.get("is_active", target.get("is_active")))
    override_values = dict(target.get("permission_overrides") or {})

    if "role_id" in data:
        if not app._account_has_permission(actor, "account.role.assign"):
            return app._json_error("역할 부여 권한이 필요합니다.", 403)
        next_role = app._load_role_by_id(conn, next_role_id)
        if not next_role or not next_role.get("is_active"):
            return app._json_error("활성 역할만 부여할 수 있습니다.", 400)
        # TASK-0300 (REQ-0287, 사용자 결정 2026-06-17): 역할 *배정* 경유 escalation 차단.
        # 본인 보유 권한 범위를 초과하는 권한을 가진 역할은 배정할 수 없다(역할 편집 우회 차단의
        # 보완 — 사전 정의된 고권한 역할을 골라 부여하는 우회 봉쇄). 역할이 실제로 바뀔 때만 검사
        # (동일 역할 재지정 no-op 은 escalation 아님 — 타 필드 수정 시 false-block 방지).
        if int(next_role_id) != int(target.get("role_id") or 0):
            _assign_excess = app._role_grant_excess_for_actor(actor, next_role.get("permission_codes"))
            if _assign_excess:
                return app._json_error(
                    "본인이 보유하지 않은 권한을 가진 역할은 배정할 수 없습니다: "
                    + ", ".join(_assign_excess),
                    403,
                )
    else:
        next_role = app._load_role_by_id(conn, next_role_id)

    if "is_active" in data and next_is_active != bool(target.get("is_active")):
        required = "account.activate" if next_is_active else "account.deactivate"
        if not app._account_has_permission(actor, required):
            return app._json_error("계정 상태 변경 권한이 필요합니다.", 403)

    # TASK-0052 Phase 1B: catalog 를 conn 으로 1 회 조회 후 validation/normalization 모두에 전달.
    _catalog_defs, catalog_codes, catalog_map = app._resolve_permission_catalog(conn)

    if "permission_overrides" in data:
        if not app._account_has_permission(actor, "account.permission.override.manage"):
            return app._json_error("권한 override 관리 권한이 필요합니다.", 403)
        try:
            override_values = app._normalize_override_payload(
                data.get("permission_overrides") if isinstance(data.get("permission_overrides"), dict) else {},
                catalog_codes=catalog_codes,
                catalog_map=catalog_map,
            )
        except ValueError as exc:
            return app._json_error(str(exc), 400)
        # TASK-0300 (REQ-0287, 인가 §12.3): privilege escalation 방지 — actor 가 본인 보유 권한
        # 범위 안에서만 override 설정 가능. 미보유 권한 설정 시 403, 범위 밖 기존 override 는 보존(merge).
        try:
            override_values = app._enforce_override_self_scope(
                actor,
                override_values,
                target.get("permission_overrides"),
            )
        except ValueError as exc:
            return app._json_error(str(exc), 403)

    role_permission_codes = app._load_role_permission_codes(conn, [next_role_id]).get(next_role_id, set())
    next_permissions = app._apply_permission_overrides(
        role_permission_codes,
        override_values,
        catalog_codes=catalog_codes,
    )
    try:
        app._ensure_management_survivor_for_account_change(
            conn,
            int(account_id),
            next_is_active=next_is_active,
            next_permissions=next_permissions,
        )
    except ValueError as exc:
        return app._json_error(str(exc), 400)

    cur = conn.cursor()
    cur.execute(
        """
UPDATE WebAccounts
SET RoleId = %s,
    IsActive = %s,
    ApprovedByAccountId = %s,
    ApprovedAt = CASE
        WHEN ApprovedAt IS NULL AND %s = 1 THEN CURRENT_TIMESTAMP
        ELSE ApprovedAt
    END
WHERE Id = %s
        """,
        (
            next_role_id,
            int(next_is_active),
            int(actor["id"]),
            int(next_permissions.get("conversation.ask") or next_permissions.get("console.access")),
            int(account_id),
        ),
    )
    cur.close()
    app._set_account_overrides(conn, int(account_id), override_values)
    if not next_is_active:
        cur = conn.cursor()
        cur.execute("UPDATE WebAuthSessions SET IsRevoked = 1 WHERE AccountId = %s", (int(account_id),))
        cur.close()
    updated = app._load_account_by_id(conn, account_id)
    # TASK-0073 Phase A5: same-tx audit hook. 실패 = caller tx rollback (fail-safe).
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.account.update",
            resource_type="account",
            resource_id=str(account_id),
            before=target,
            after=updated,
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    # TASK-0098: admin context — 권한 정보 명시 포함.
    payload = app._serialize_account(updated, include_permissions=True) or {}
    payload["permission_overrides"] = dict((updated or {}).get("permission_overrides") or {})
    # TASK-20260623T030418-quota-rbac-permission (outside-voice MAJOR-1 흡수): PATCH 응답도
    #   quota.read 미보유 actor 에는 한도 필드 비노출(account.update 만으로 한도 열람 우회 차단).
    app._strip_quota_fields_if_unpermitted(payload, actor)
    return JSONResponse({"ok": True, "account": payload})

@router.post("/api/admin/accounts/{account_id}/password-reset")
def admin_account_password_reset(
    account_id: int,
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch6: _require_account→account+conn 완전 DI. perm·self-reset 은 본문 유지.
    # get_conn finally:close 가 _load_account_by_id·UPDATE·audit raise 시 conn leak 을 해소.
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.update"):
        return app._json_error("계정 수정 권한이 필요합니다.", 403)
    if int(actor["id"]) == int(account_id):
        return app._json_error(
            "자기 자신의 비밀번호는 이 흐름으로 초기화할 수 없습니다. 프로필 드로어의 비밀번호 변경을 사용하세요.",
            400,
        )
    target = app._load_account_by_id(conn, account_id)
    if not target:
        return app._json_error("account not found", 404)
    if target.get("deleted_at"):
        return app._json_error("삭제된 계정의 비밀번호는 초기화할 수 없습니다.", 400)
    # 12 byte URL-safe = 16 글자 이상의 임시 비밀번호 — _is_valid_password (10~128 자) 통과.
    while True:
        temporary_password = secrets.token_urlsafe(12)
        if app._is_valid_password(temporary_password):
            break
    password_hash = app._hash_password(temporary_password)
    cur = conn.cursor()
    try:
        cur.execute(
            # TASK-20260619T021356-login-attempt-limit (보안 ②): 비밀번호 초기화는 로그인 실패 잠금도 함께 해제
            # (관리자 개입 = 정당 사용자 회복 경로).
            "UPDATE WebAccounts SET PasswordHash = %s, MustChangePassword = 1, "
            "FailedLoginAttempts = 0, LockedUntilAt = NULL WHERE Id = %s",
            (password_hash, int(account_id)),
        )
        # 기존 세션 일괄 revoke — 대상 계정이 강제로 재로그인 후 새 비번 설정하도록.
        cur.execute(
            "UPDATE WebAuthSessions SET IsRevoked = 1 WHERE AccountId = %s",
            (int(account_id),),
        )
    except Exception:
        cur.close()
        return app._json_error("비밀번호 초기화에 실패했습니다.", 500)
    cur.close()
    # TASK-0073 Phase A5: same-tx audit hook (PasswordHash / temporary_password 명시 redact).
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.account.password-reset",
            resource_type="account",
            resource_id=str(account_id),
            before=target,
            after=None,
            request_ctx={"sessions_revoked": True},
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    return JSONResponse({
        "ok": True,
        "account_id": int(account_id),
        "username": str(target.get("username") or ""),
        "temporary_password": temporary_password,
        "expires_hint": "다음 로그인 시 즉시 변경됩니다.",
    })

@router.post("/api/admin/accounts/{account_id}/unlock")
def admin_account_unlock(
    account_id: int,
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금을 비밀번호 변경 없이 즉시 해제.

    표적 DoS(공격자가 정당 사용자를 일부러 잠금)로부터의 관리자 회복 경로 — 비밀번호
    초기화(강제 변경 동반)와 달리 잠금만 푼다. 권한: password-reset 와 동일
    (`console.access` + `console.manage` + `account.update`). 신규 RBAC 권한 없음.

    ITEM-11 batch4: _require_account→account+conn 완전 DI(get_current_account/get_conn).
    perm 은 AND 조합·per-perm 다른 403 메시지라 본문 인라인 유지. get_conn finally:close 가
    _load_account_by_id·_account_has_permission raise 시 conn leak 을 해소. byte-동치:
    401 "로그인이 필요합니다."·500 "db connection failed" 인라인 동일. account_id<=0 400 은
    본문 유지(authed 동일; account_id<=0+unauth 이중 엣지만 401 선행, benign).
    """
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.update"):
        return app._json_error("계정 수정 권한이 필요합니다.", 403)
    target = app._load_account_by_id(conn, account_id)
    if not target:
        return app._json_error("account not found", 404)
    was_locked = bool(target.get("is_locked"))
    try:
        app._login_reset_lockout(conn, int(account_id))
    except Exception:
        return app._json_error("잠금 해제에 실패했습니다.", 500)
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="auth.unlock",
            resource_type="account",
            resource_id=str(account_id),
            before=None,
            after=None,
            request_ctx={
                "target_account_id": int(account_id),
                "username": str(target.get("username") or ""),
                "was_locked": was_locked,
            },
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    return JSONResponse({
        "ok": True,
        "account_id": int(account_id),
        "username": str(target.get("username") or ""),
        "was_locked": was_locked,
    })

@router.post("/api/admin/accounts/{account_id}/totp/disable")
def admin_account_totp_disable(account_id: int, request: Request) -> JSONResponse:
    """TASK-20260619T040000-two-factor-auth (보안 ⑥): 관리자 2FA 강제 해제(분실 디바이스 복구).

    비밀번호 변경 없이 2FA 만 제거 → 사용자가 비밀번호로 로그인 후 재설정. 권한:
    password-reset 동일(`console.access`+`console.manage`+`account.update`). 신규 RBAC 0.
    """
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        actor, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
            return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
        if not app._account_has_permission(actor, "account.update"):
            return app._json_error("계정 수정 권한이 필요합니다.", 403)
        target = app._load_account_by_id(conn, account_id)
        if not target:
            return app._json_error("account not found", 404)
        was_enabled = app._totp_is_enabled(conn, int(account_id))
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM WebAccountTotp WHERE AccountId=%s", (int(account_id),))
        finally:
            cur.close()
        try:
            app._audit_admin_mutation(
                conn, request, actor, action="auth.totp.admin_disable", resource_type="account",
                resource_id=str(account_id), before=None, after=None,
                request_ctx={"target_account_id": int(account_id),
                             "username": str(target.get("username") or ""), "was_enabled": was_enabled},
                target_account_id=int(account_id),
            )
            conn.commit()
        except Exception as audit_exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return app._json_error(f"audit write failed: {audit_exc}", 500)
        return JSONResponse({"ok": True, "account_id": int(account_id), "was_enabled": was_enabled})
    finally:
        conn.close()

@router.delete("/api/admin/accounts/{account_id}")
def admin_delete_account(
    account_id: int,
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch5: _require_account→account+conn 완전 DI. perm 은 per-perm 다른 403 메시지라
    # 본문 유지. get_conn finally:close 가 _load_account_by_id·survivor·mutate raise 시 leak 해소.
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.delete"):
        return app._json_error("계정 삭제 권한이 필요합니다.", 403)
    target = app._load_account_by_id(conn, account_id)
    if not target:
        return app._json_error("account not found", 404)
    if target.get("deleted_at"):
        return app._json_error("이미 삭제된 계정입니다.", 400)
    try:
        app._ensure_management_survivor_for_account_change(
            conn,
            int(account_id),
            next_is_active=False,
            next_permissions=app._account_permissions(target),
            deleting=True,
        )
    except ValueError as exc:
        return app._json_error(str(exc), 400)
    cur = conn.cursor()
    cur.execute(
        """
UPDATE WebAccounts
SET IsActive = 0,
    DeletedAt = CURRENT_TIMESTAMP,
    DeletedByAccountId = %s
WHERE Id = %s
        """,
        (int(actor["id"]), int(account_id)),
    )
    cur.execute("UPDATE WebAuthSessions SET IsRevoked = 1 WHERE AccountId = %s", (int(account_id),))
    cur.close()
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.account.delete",
            resource_type="account",
            resource_id=str(account_id),
            before=target,
            after=None,
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    return JSONResponse({"ok": True, "account_id": int(account_id)})


# ==== feature-0012 ITEM-10 p14 — app.py 에서 이동 (3종). app 전역은 app.X 동적 참조. ====

def _list_admin_accounts(conn) -> list[dict[str, app.Any]]:
    rows = app._fetch_account_rows(
        conn,
        "1=1",
        include_password=False,
        order_sql="ORDER BY (a.DeletedAt IS NULL) DESC, a.IsActive DESC, a.CreatedAt DESC",
    )
    rows = app._decorate_account_rows(conn, rows)
    if app.os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT owner_account_id, COUNT(*) FROM agent_runtime.core_conversations "
                    "WHERE owner_account_id IS NOT NULL GROUP BY owner_account_id"
                )
                count_rows = pgcur.fetchall() or []
            pg.close()
        except Exception:
            count_rows = []
        conversation_counts = {int(oid): int(cnt or 0) for oid, cnt in count_rows if int(oid or 0) > 0}
    else:
        cur = conn.cursor()
        cur.execute(
            """
SELECT owner_account_id, COUNT(*)
FROM AgentCoreConversations
WHERE owner_account_id IS NOT NULL
GROUP BY owner_account_id
            """
        )
        count_rows2 = cur.fetchall() or []
        cur.close()
        conversation_counts = {int(owner_id): int(count or 0) for owner_id, count in count_rows2 if int(owner_id or 0) > 0}
    items: list[dict[str, app.Any]] = []
    for row in rows:
        # TASK-0098: admin context — 권한 정보 명시 포함.
        payload = app._serialize_account(row, include_permissions=True) or {}
        payload["conversation_count"] = conversation_counts.get(int(row.get("id") or 0), 0)
        payload["permission_overrides"] = dict(row.get("permission_overrides") or {})
        items.append(payload)
    return items

def _list_active_accounts(conn) -> list[dict[str, app.Any]]:
    rows = app._fetch_account_rows(
        conn,
        "a.IsActive = 1 AND a.DeletedAt IS NULL",
        include_password=False,
    )
    return app._decorate_account_rows(conn, rows)

def _enforce_override_self_scope(
    actor: dict[str, app.Any] | None,
    submitted_overrides: dict[str, str] | None,
    existing_overrides: dict[str, str] | None,
) -> dict[str, str]:
    """TASK-0300 (REQ-0287, 인가 §12.3): 관리자는 본인이 보유한 권한 범위 안에서만 계정
    permission override 를 설정할 수 있다 — privilege escalation(자기 권한 초과 부여) 방지.

    - ``submitted_overrides`` 는 ``_normalize_override_payload`` 결과(allow/deny 만, inherit 제거됨).
    - 본인 미보유 권한에 allow/deny 를 설정하려 하면 ``ValueError`` → caller 가 403.
      (요구사항 "숨김 처리 + 설정 불가": 미보유 권한은 allow·deny 모두 불가.)
    - 본인 범위 **밖** 권한의 기존 override 는 보존(merge)한다. UI 가 그 권한 행을 숨겨
      payload 에서 누락돼도 ``_set_account_overrides`` 의 delete-all-then-insert 로 삭제되지
      않게 하는 데이터 무결성 가드다.
    """
    editable = app._actor_editable_permission_codes(actor)
    submitted = dict(submitted_overrides or {})
    existing = dict(existing_overrides or {})
    escalating = sorted(code for code in submitted if code not in editable)
    if escalating:
        raise ValueError(
            "본인이 보유하지 않은 권한은 설정할 수 없습니다: " + ", ".join(escalating)
        )
    merged: dict[str, str] = {
        code: value for code, value in existing.items() if code not in editable
    }
    merged.update(submitted)
    return merged


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (8종). app 전역은 app.X 동적 참조. ====

def _actor_editable_permission_codes(actor: dict[str, app.Any] | None) -> set[str]:
    """TASK-0300: actor(편집 주체)가 실제로 보유한(effective=True) 권한 code 집합.
    관리 콘솔에서 actor 가 타 계정/역할에 부여·설정할 수 있는 권한의 상한(self-scope)이다."""
    return {code for code, granted in app._account_permissions(actor).items() if granted}

def _role_grant_excess_for_actor(
    actor: dict[str, app.Any] | None,
    role_permission_codes: "Iterable[str] | None",
) -> list[str]:
    """TASK-0300 (REQ-0287, 사용자 결정 2026-06-17): 역할 *배정* 경유 escalation 차단용 —
    주어진 역할의 권한 중 actor 가 보유하지 않은 code 목록(정렬). 빈 list 면 배정 가능.

    역할 편집(권한 부여) 차단을 우회해 "사전 정의된 고권한 역할을 골라 배정" 하는 경로를 막는다.
    """
    editable = app._actor_editable_permission_codes(actor)
    return sorted({str(c) for c in (role_permission_codes or [])} - editable)

def _normalize_override_payload(
    payload: dict[str, app.Any] | None,
    *,
    catalog_codes: app.Iterable[str] | None = None,
    catalog_map: dict[str, dict[str, app.Any]] | None = None,
) -> dict[str, str]:
    """TASK-0052 Phase 1A: catalog_codes / catalog_map 을 명시적으로 받음.

    Phase 1B 에서 product 권한 override 가 들어오면 caller 가 conn-resolved catalog 를 전달.
    None 이면 정적 PERMISSION_CODES / PERMISSION_DEFINITION_MAP 사용 (기존 동작).
    """
    codes = list(catalog_codes) if catalog_codes is not None else list(app.PERMISSION_CODES)
    cmap = catalog_map if catalog_map is not None else app.PERMISSION_DEFINITION_MAP
    result: dict[str, str] = {}
    for code in codes:
        normalized = app._normalize_override_value((payload or {}).get(code))
        if normalized == app.OVERRIDE_INHERIT:
            continue
        result[code] = normalized
    invalid_keys = sorted(
        key for key in (payload or {}).keys() if str(key) not in cmap
    )
    if invalid_keys:
        raise ValueError(f"unknown override permissions: {', '.join(map(str, invalid_keys))}")
    return result

def _set_account_overrides(conn, account_id: int, override_values: dict[str, str]) -> None:
    permission_ids = app._permission_id_map(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM WebAccountPermissionOverrides WHERE AccountId = %s", (int(account_id),))
    for code, value in sorted(override_values.items()):
        permission_id = int(permission_ids.get(code) or 0)
        if permission_id <= 0:
            continue
        cur.execute(
            """
INSERT INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
VALUES (%s, %s, %s)
            """,
            (int(account_id), permission_id, value),
        )
    cur.close()

def _is_management_permission_set(permissions: dict[str, bool] | None) -> bool:
    payload = permissions or {}
    return bool(
        payload.get("console.manage")
        and payload.get("account.role.assign")
        and payload.get("role.permission.manage")
    )

def _ensure_management_survivor_for_account_change(
    conn,
    target_account_id: int,
    *,
    next_is_active: bool,
    next_permissions: dict[str, bool],
    deleting: bool = False,
) -> None:
    accounts = app._list_active_accounts(conn)
    survivors = 0
    seen_target = False
    for account in accounts:
        account_id = int(account.get("id") or 0)
        if account_id == int(target_account_id):
            seen_target = True
            if deleting or not next_is_active:
                continue
            permissions = next_permissions
        else:
            permissions = app._account_permissions(account)
        if app._is_management_permission_set(permissions):
            survivors += 1
    if not seen_target and not deleting and next_is_active and app._is_management_permission_set(next_permissions):
        survivors += 1
    if survivors <= 0:
        raise ValueError("관리 가능한 활성 계정은 최소 1개 이상 유지되어야 합니다.")

def _store_image_upload(body: bytes, *, prefix: str, owner_id: int, max_bytes: int,
                        mime_hint: str) -> "tuple[str, str] | tuple[None, str]":
    """이미지 bytes 검증 + MinIO 저장. 반환 (object_key, content_type) 또는 (None, error_msg).

    prefix='avatars'|'product-icons'. object key = `<prefix>/<owner_id>/<uuid>.<ext>`.
    """
    if not body:
        return (None, "빈 파일입니다.")
    if len(body) > max_bytes:
        return (None, f"이미지가 너무 큽니다(최대 {max_bytes // (1024 * 1024)}MB).")
    sniffed = app._sniff_image(body, mime_hint)
    if not sniffed:
        return (None, "지원하지 않는 이미지 형식입니다(PNG·JPG·WEBP만 허용).")
    ext, content_type = sniffed
    try:
        from web.modules import storage_minio
        import uuid as _uuid
        object_key = f"{prefix}/{int(owner_id)}/{_uuid.uuid4().hex}.{ext}"
        storage_minio.put_object_bytes(
            object_key, body, content_type=content_type,
            metadata={"kind": prefix, "owner_id": str(owner_id)},
        )
        return (object_key, content_type)
    except Exception as exc:
        app.logging.getLogger(__name__).warning("image upload store failed", exc_info=True)
        return (None, f"이미지 저장 실패: {exc}")

def _account_role_key(account: dict[str, app.Any] | None) -> str:
    """role 객체에서 RoleKey 추출. account 에 role row join 결과가 있으면 사용,
    없으면 빈 문자열."""
    if not account:
        return ""
    role = account.get("role")
    if isinstance(role, dict):
        return str(role.get("key") or role.get("RoleKey") or "").strip()
    return str(account.get("role_key") or "").strip()
