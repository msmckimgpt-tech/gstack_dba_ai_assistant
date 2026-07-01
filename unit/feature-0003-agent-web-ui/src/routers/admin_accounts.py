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

import app

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
async def admin_update_account(account_id: int, request: Request) -> JSONResponse:
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        conn.close()
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.update"):
        conn.close()
        return app._json_error("계정 수정 권한이 필요합니다.", 403)
    target = app._load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return app._json_error("account not found", 404)
    if target.get("deleted_at"):
        conn.close()
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
            conn.close()
            return app._json_error("역할 부여 권한이 필요합니다.", 403)
        next_role = app._load_role_by_id(conn, next_role_id)
        if not next_role or not next_role.get("is_active"):
            conn.close()
            return app._json_error("활성 역할만 부여할 수 있습니다.", 400)
        # TASK-0300 (REQ-0287, 사용자 결정 2026-06-17): 역할 *배정* 경유 escalation 차단.
        # 본인 보유 권한 범위를 초과하는 권한을 가진 역할은 배정할 수 없다(역할 편집 우회 차단의
        # 보완 — 사전 정의된 고권한 역할을 골라 부여하는 우회 봉쇄). 역할이 실제로 바뀔 때만 검사
        # (동일 역할 재지정 no-op 은 escalation 아님 — 타 필드 수정 시 false-block 방지).
        if int(next_role_id) != int(target.get("role_id") or 0):
            _assign_excess = app._role_grant_excess_for_actor(actor, next_role.get("permission_codes"))
            if _assign_excess:
                conn.close()
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
            conn.close()
            return app._json_error("계정 상태 변경 권한이 필요합니다.", 403)

    # TASK-0052 Phase 1B: catalog 를 conn 으로 1 회 조회 후 validation/normalization 모두에 전달.
    _catalog_defs, catalog_codes, catalog_map = app._resolve_permission_catalog(conn)

    if "permission_overrides" in data:
        if not app._account_has_permission(actor, "account.permission.override.manage"):
            conn.close()
            return app._json_error("권한 override 관리 권한이 필요합니다.", 403)
        try:
            override_values = app._normalize_override_payload(
                data.get("permission_overrides") if isinstance(data.get("permission_overrides"), dict) else {},
                catalog_codes=catalog_codes,
                catalog_map=catalog_map,
            )
        except ValueError as exc:
            conn.close()
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
            conn.close()
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
        conn.close()
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
        conn.close()
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    conn.close()
    # TASK-0098: admin context — 권한 정보 명시 포함.
    payload = app._serialize_account(updated, include_permissions=True) or {}
    payload["permission_overrides"] = dict((updated or {}).get("permission_overrides") or {})
    # TASK-20260623T030418-quota-rbac-permission (outside-voice MAJOR-1 흡수): PATCH 응답도
    #   quota.read 미보유 actor 에는 한도 필드 비노출(account.update 만으로 한도 열람 우회 차단).
    app._strip_quota_fields_if_unpermitted(payload, actor)
    return JSONResponse({"ok": True, "account": payload})

@router.post("/api/admin/accounts/{account_id}/password-reset")
def admin_account_password_reset(account_id: int, request: Request) -> JSONResponse:
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        conn.close()
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.update"):
        conn.close()
        return app._json_error("계정 수정 권한이 필요합니다.", 403)
    if int(actor["id"]) == int(account_id):
        conn.close()
        return app._json_error(
            "자기 자신의 비밀번호는 이 흐름으로 초기화할 수 없습니다. 프로필 드로어의 비밀번호 변경을 사용하세요.",
            400,
        )
    target = app._load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return app._json_error("account not found", 404)
    if target.get("deleted_at"):
        conn.close()
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
        conn.close()
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
        conn.close()
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    conn.close()
    return JSONResponse({
        "ok": True,
        "account_id": int(account_id),
        "username": str(target.get("username") or ""),
        "temporary_password": temporary_password,
        "expires_hint": "다음 로그인 시 즉시 변경됩니다.",
    })

@router.post("/api/admin/accounts/{account_id}/unlock")
def admin_account_unlock(account_id: int, request: Request) -> JSONResponse:
    """TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금을 비밀번호 변경 없이 즉시 해제.

    표적 DoS(공격자가 정당 사용자를 일부러 잠금)로부터의 관리자 회복 경로 — 비밀번호
    초기화(강제 변경 동반)와 달리 잠금만 푼다. 권한: password-reset 와 동일
    (`console.access` + `console.manage` + `account.update`). 신규 RBAC 권한 없음.
    """
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        conn.close()
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.update"):
        conn.close()
        return app._json_error("계정 수정 권한이 필요합니다.", 403)
    target = app._load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return app._json_error("account not found", 404)
    was_locked = bool(target.get("is_locked"))
    try:
        app._login_reset_lockout(conn, int(account_id))
    except Exception:
        conn.close()
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
        conn.close()
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    conn.close()
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
def admin_delete_account(account_id: int, request: Request) -> JSONResponse:
    if account_id <= 0:
        return app._json_error("invalid account_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        conn.close()
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "account.delete"):
        conn.close()
        return app._json_error("계정 삭제 권한이 필요합니다.", 403)
    target = app._load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return app._json_error("account not found", 404)
    if target.get("deleted_at"):
        conn.close()
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
        conn.close()
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
        conn.close()
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    conn.close()
    return JSONResponse({"ok": True, "account_id": int(account_id)})
