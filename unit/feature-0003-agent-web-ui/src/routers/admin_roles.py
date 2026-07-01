"""feature-0012 P5b Final — admin_roles 도메인 APIRouter (역할 관리(아이콘/CRUD/프롬프트)).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import JSONResponse

import app

router = APIRouter()


@router.put("/api/admin/roles/{role_id}/icon")
async def admin_upload_role_icon(role_id: int, request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """역할 아이콘 업로드(console.manage + role.update). 이전 아이콘 교체."""
    if role_id <= 0:
        return app._json_error("invalid role_id", 400)
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
        if not app._account_has_permission(actor, "role.update"):
            return app._json_error("역할 수정 권한이 필요합니다 (role.update).", 403)
        cur = conn.cursor()
        try:
            cur.execute("SELECT IconObjectKey FROM WebRoles WHERE Id = %s", (int(role_id),))
            row = cur.fetchone()
        finally:
            cur.close()
        if row is None:
            return app._json_error("역할을 찾을 수 없습니다.", 404)
        old_key = row[0]
        body = await file.read()
        object_key, info = app._store_image_upload(
            body, prefix="role-icons", owner_id=int(role_id), max_bytes=app._ICON_MAX_BYTES,
            mime_hint=(file.content_type or ""),
        )
        if not object_key:
            return app._json_error(info, 400)
        cur = conn.cursor()
        try:
            cur.execute("UPDATE WebRoles SET IconObjectKey = %s WHERE Id = %s", (object_key, int(role_id)))
            conn.commit()
        finally:
            cur.close()
        if old_key and old_key != object_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "icon_url": app._role_icon_url_for(int(role_id), object_key)})
    finally:
        conn.close()

@router.delete("/api/admin/roles/{role_id}/icon")
def admin_delete_role_icon(role_id: int, request: Request) -> JSONResponse:
    """역할 아이콘 제거(console.manage + role.update) → Identicon 폴백."""
    if role_id <= 0:
        return app._json_error("invalid role_id", 400)
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
        if not app._account_has_permission(actor, "role.update"):
            return app._json_error("역할 수정 권한이 필요합니다 (role.update).", 403)
        cur = conn.cursor()
        try:
            cur.execute("SELECT IconObjectKey FROM WebRoles WHERE Id = %s", (int(role_id),))
            row = cur.fetchone()
            old_key = row[0] if row else None
            cur.execute("UPDATE WebRoles SET IconObjectKey = NULL WHERE Id = %s", (int(role_id),))
            conn.commit()
        finally:
            cur.close()
        if old_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "icon_url": None})
    finally:
        conn.close()

@router.get("/api/admin/roles")
def admin_roles(request: Request, account=Depends(app.require_permission("console.access", "role.read", message="역할 조회 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    roles = app._list_roles(conn)
    # TASK-20260623T030418-quota-rbac-permission: quota.read 미보유 actor 에는 역할 기본 한도 비노출.
    app._strip_quota_fields_if_unpermitted(roles, account)
    return JSONResponse({"roles": roles})

@router.post("/api/admin/roles")
async def admin_create_role(request: Request) -> JSONResponse:
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
    if not app._account_has_permission(actor, "role.create"):
        conn.close()
        return app._json_error("역할 생성 권한이 필요합니다.", 403)
    role_key = app._sanitize_role_key(data.get("role_key", ""))
    if not app._is_valid_role_key(role_key):
        conn.close()
        return app._json_error("role_key 형식이 올바르지 않습니다.", 400)
    # TASK-0052 Phase 1B: dynamic catalog 기반 검증.
    _catalog_defs, catalog_codes_for_role, _catalog_map = app._resolve_permission_catalog(conn)
    try:
        permission_codes = app._validate_permission_codes(
            data.get("permission_codes") or [],
            catalog_codes=catalog_codes_for_role,
        )
    except ValueError as exc:
        conn.close()
        return app._json_error(str(exc), 400)
    if permission_codes and not app._account_has_permission(actor, "role.permission.manage"):
        conn.close()
        return app._json_error("역할 권한 배치 권한이 필요합니다.", 403)
    # TASK-0300 (REQ-0287): privilege escalation 방지 — 신규 역할 생성 시에도 본인 미보유 권한은
    # 부여 불가(역할 생성 경유 우회 차단). 신규 역할이라 current=빈 집합 → 부여 권한 전부 self-scope 검사.
    try:
        permission_codes = app._enforce_role_permission_self_scope(actor, permission_codes, set())
    except ValueError as exc:
        conn.close()
        return app._json_error(str(exc), 403)
    name = str(data.get("name", "") or "").strip()
    if not name:
        conn.close()
        return app._json_error("role name is required", 400)
    description = str(data.get("description", "") or "").strip()
    is_active = bool(data.get("is_active", True))
    is_default_signup = bool(data.get("is_default_signup", False))
    if is_default_signup and not is_active:
        conn.close()
        return app._json_error("기본 가입 역할은 활성 상태여야 합니다.", 400)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM WebRoles WHERE RoleKey = %s LIMIT 1", (role_key,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return app._json_error("이미 존재하는 role_key 입니다.", 409)
    cur.close()
    role_id = app._create_role_with_permissions(
        conn,
        role_key,
        name=name,
        description=description,
        is_active=is_active,
        is_default_signup=is_default_signup,
        permission_codes=permission_codes,
    )
    if is_default_signup:
        app._assign_default_signup_role(conn, role_id)
    role = app._load_role_by_id(conn, role_id)
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.role.create",
            resource_type="role",
            resource_id=str(role_id),
            before=None,
            after=role,
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
    return JSONResponse({"ok": True, "role": role})

@router.patch("/api/admin/roles/{role_id}")
async def admin_update_role(role_id: int, request: Request) -> JSONResponse:
    if role_id <= 0:
        return app._json_error("invalid role_id", 400)
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
    if not app._account_has_permission(actor, "role.update"):
        conn.close()
        return app._json_error("역할 수정 권한이 필요합니다.", 403)
    current_role = app._load_role_by_id(conn, role_id)
    if not current_role:
        conn.close()
        return app._json_error("role not found", 404)
    if "role_key" in data and app._sanitize_role_key(data.get("role_key", "")) != current_role.get("key"):
        conn.close()
        return app._json_error("role_key 는 수정할 수 없습니다.", 400)
    next_name = str(data.get("name", current_role.get("name")) or "").strip()
    next_description = str(data.get("description", current_role.get("description")) or "").strip()
    next_is_active = bool(data.get("is_active", current_role.get("is_active")))
    next_is_default_signup = bool(data.get("is_default_signup", current_role.get("is_default_signup")))
    next_permission_codes = set(current_role.get("permission_codes") or [])
    if "permission_codes" in data:
        if not app._account_has_permission(actor, "role.permission.manage"):
            conn.close()
            return app._json_error("역할 권한 배치 권한이 필요합니다.", 403)
        # TASK-0052 Phase 1B: dynamic catalog 기반 검증.
        _catalog_defs_u, catalog_codes_for_role_u, _catalog_map_u = app._resolve_permission_catalog(conn)
        try:
            next_permission_codes = app._validate_permission_codes(
                data.get("permission_codes") or [],
                catalog_codes=catalog_codes_for_role_u,
            )
        except ValueError as exc:
            conn.close()
            return app._json_error(str(exc), 400)
        # TASK-0300 (REQ-0287): privilege escalation 방지 — 본인 미보유 권한을 역할에 신규 부여 시
        # 403(역할 경유 우회 차단), 본인 범위 밖 기존 역할 권한은 보존(merge).
        try:
            next_permission_codes = app._enforce_role_permission_self_scope(
                actor,
                next_permission_codes,
                current_role.get("permission_codes"),
            )
        except ValueError as exc:
            conn.close()
            return app._json_error(str(exc), 403)
        try:
            app._ensure_management_survivor_for_role_change(conn, int(role_id), next_permission_codes)
        except ValueError as exc:
            conn.close()
            return app._json_error(str(exc), 400)
    if current_role.get("is_default_signup") and not next_is_default_signup:
        conn.close()
        return app._json_error("기본 가입 역할은 다른 역할을 지정하기 전에는 해제할 수 없습니다.", 400)
    if next_is_default_signup and not next_is_active:
        conn.close()
        return app._json_error("기본 가입 역할은 활성 상태여야 합니다.", 400)
    if current_role.get("is_default_signup") and not next_is_active:
        conn.close()
        return app._json_error("기본 가입 역할은 비활성화할 수 없습니다.", 400)
    cur = conn.cursor()
    cur.execute(
        """
UPDATE WebRoles
SET Name = %s,
    Description = %s,
    IsActive = %s,
    IsDefaultSignup = %s
WHERE Id = %s
        """,
        (
            next_name,
            next_description,
            int(next_is_active),
            int(next_is_default_signup),
            int(role_id),
        ),
    )
    cur.close()
    if "permission_codes" in data:
        app._set_role_permissions(conn, int(role_id), next_permission_codes)
    if next_is_default_signup:
        app._assign_default_signup_role(conn, int(role_id))
    role = app._load_role_by_id(conn, int(role_id))
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.role.update",
            resource_type="role",
            resource_id=str(role_id),
            before=current_role,
            after=role,
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
    return JSONResponse({"ok": True, "role": role})

@router.delete("/api/admin/roles/{role_id}")
def admin_delete_role(role_id: int, request: Request) -> JSONResponse:
    if role_id <= 0:
        return app._json_error("invalid role_id", 400)
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
    if not app._account_has_permission(actor, "role.delete"):
        conn.close()
        return app._json_error("역할 삭제 권한이 필요합니다.", 403)
    role = app._load_role_by_id(conn, int(role_id))
    if not role:
        conn.close()
        return app._json_error("role not found", 404)
    if role.get("is_default_signup"):
        conn.close()
        return app._json_error("기본 가입 역할은 삭제할 수 없습니다.", 400)
    cur = conn.cursor()
    cur.execute(
        """
SELECT COUNT(*)
FROM WebAccounts
WHERE RoleId = %s
  AND DeletedAt IS NULL
        """,
        (int(role_id),),
    )
    in_use = int((cur.fetchone() or (0,))[0] or 0)
    if in_use > 0:
        cur.close()
        conn.close()
        return app._json_error("미삭제 계정이 참조 중인 역할은 삭제할 수 없습니다.", 400)
    cur.execute("DELETE FROM WebRolePermissions WHERE RoleId = %s", (int(role_id),))
    cur.execute("DELETE FROM WebRoles WHERE Id = %s", (int(role_id),))
    cur.close()
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.role.delete",
            resource_type="role",
            resource_id=str(role_id),
            before=role,
            after=None,
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
    return JSONResponse({"ok": True, "role_id": int(role_id)})

@router.post("/api/admin/roles/{role_id}/prompt/generate")
async def admin_generate_role_prompt(role_id: int, request: Request) -> JSONResponse:
    """비스트리밍 역할 프롬프트 자동작성(호환 경로). 실시간 진행률은 GET .../stream."""
    error, ctx = await app._collect_role_prompt_context(role_id, request)
    if error:
        return error
    return await app._prompt_generate_json_response(
        ctx, log_label="admin_generate_role_prompt", log_ctx=f"role_id={role_id}"
    )

@router.get("/api/admin/roles/{role_id}/prompt/generate/stream")
async def admin_generate_role_prompt_stream(role_id: int, request: Request):
    """역할 '전체 제품 프롬프트' 자동작성 LLM 토큰 스트리밍(SSE)."""
    error, ctx = await app._collect_role_prompt_context(role_id, request)
    if error:
        return error
    return app._prompt_generate_stream_response(
        ctx, log_label="admin_generate_role_prompt_stream", log_ctx=f"role_id={role_id}"
    )
