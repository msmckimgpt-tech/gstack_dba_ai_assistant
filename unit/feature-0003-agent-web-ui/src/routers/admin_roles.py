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

from collections.abc import Iterable

import app

INCLUDE_ORDER = 180  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
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
async def admin_create_role(
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch9: _require_account→account+conn 완전 DI. perm·검증은 본문 유지.
    # get_conn finally:close 가 catalog·_create_role_with_permissions·audit raise 시 conn leak 해소.
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "role.create"):
        return app._json_error("역할 생성 권한이 필요합니다.", 403)
    role_key = app._sanitize_role_key(data.get("role_key", ""))
    if not app._is_valid_role_key(role_key):
        return app._json_error("role_key 형식이 올바르지 않습니다.", 400)
    # TASK-0052 Phase 1B: dynamic catalog 기반 검증.
    _catalog_defs, catalog_codes_for_role, _catalog_map = app._resolve_permission_catalog(conn)
    try:
        permission_codes = app._validate_permission_codes(
            data.get("permission_codes") or [],
            catalog_codes=catalog_codes_for_role,
        )
    except ValueError as exc:
        return app._json_error(str(exc), 400)
    if permission_codes and not app._account_has_permission(actor, "role.permission.manage"):
        return app._json_error("역할 권한 배치 권한이 필요합니다.", 403)
    # TASK-0300 (REQ-0287): privilege escalation 방지 — 신규 역할 생성 시에도 본인 미보유 권한은
    # 부여 불가(역할 생성 경유 우회 차단). 신규 역할이라 current=빈 집합 → 부여 권한 전부 self-scope 검사.
    try:
        permission_codes = app._enforce_role_permission_self_scope(actor, permission_codes, set())
    except ValueError as exc:
        return app._json_error(str(exc), 403)
    name = str(data.get("name", "") or "").strip()
    if not name:
        return app._json_error("role name is required", 400)
    description = str(data.get("description", "") or "").strip()
    is_active = bool(data.get("is_active", True))
    is_default_signup = bool(data.get("is_default_signup", False))
    if is_default_signup and not is_active:
        return app._json_error("기본 가입 역할은 활성 상태여야 합니다.", 400)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM WebRoles WHERE RoleKey = %s LIMIT 1", (role_key,))
    if cur.fetchone():
        cur.close()
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
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    return JSONResponse({"ok": True, "role": role})

@router.patch("/api/admin/roles/{role_id}")
async def admin_update_role(
    role_id: int,
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch10: _require_account→account+conn 완전 DI. perm·검증·self-scope·survivor 본문 유지.
    # get_conn finally:close 가 catalog·UPDATE·_set_role_permissions·audit raise 시 conn leak 해소.
    if role_id <= 0:
        return app._json_error("invalid role_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "role.update"):
        return app._json_error("역할 수정 권한이 필요합니다.", 403)
    current_role = app._load_role_by_id(conn, role_id)
    if not current_role:
        return app._json_error("role not found", 404)
    if "role_key" in data and app._sanitize_role_key(data.get("role_key", "")) != current_role.get("key"):
        return app._json_error("role_key 는 수정할 수 없습니다.", 400)
    next_name = str(data.get("name", current_role.get("name")) or "").strip()
    next_description = str(data.get("description", current_role.get("description")) or "").strip()
    next_is_active = bool(data.get("is_active", current_role.get("is_active")))
    next_is_default_signup = bool(data.get("is_default_signup", current_role.get("is_default_signup")))
    next_permission_codes = set(current_role.get("permission_codes") or [])
    if "permission_codes" in data:
        if not app._account_has_permission(actor, "role.permission.manage"):
            return app._json_error("역할 권한 배치 권한이 필요합니다.", 403)
        # TASK-0052 Phase 1B: dynamic catalog 기반 검증.
        _catalog_defs_u, catalog_codes_for_role_u, _catalog_map_u = app._resolve_permission_catalog(conn)
        try:
            next_permission_codes = app._validate_permission_codes(
                data.get("permission_codes") or [],
                catalog_codes=catalog_codes_for_role_u,
            )
        except ValueError as exc:
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
            return app._json_error(str(exc), 403)
        try:
            app._ensure_management_survivor_for_role_change(conn, int(role_id), next_permission_codes)
        except ValueError as exc:
            return app._json_error(str(exc), 400)
    if current_role.get("is_default_signup") and not next_is_default_signup:
        return app._json_error("기본 가입 역할은 다른 역할을 지정하기 전에는 해제할 수 없습니다.", 400)
    if next_is_default_signup and not next_is_active:
        return app._json_error("기본 가입 역할은 활성 상태여야 합니다.", 400)
    if current_role.get("is_default_signup") and not next_is_active:
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
        return app._json_error(f"audit write failed: {audit_exc}", 500)
    return JSONResponse({"ok": True, "role": role})

@router.delete("/api/admin/roles/{role_id}")
def admin_delete_role(
    role_id: int,
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch7: _require_account→account+conn 완전 DI. perm 은 per-perm 다른 403 메시지라
    # 본문 유지. get_conn finally:close 가 _load_role_by_id·DELETE·audit raise 시 conn leak 을 해소.
    if role_id <= 0:
        return app._json_error("invalid role_id", 400)
    if not app._account_has_permission(actor, "console.access") or not app._account_has_permission(actor, "console.manage"):
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not app._account_has_permission(actor, "role.delete"):
        return app._json_error("역할 삭제 권한이 필요합니다.", 403)
    role = app._load_role_by_id(conn, int(role_id))
    if not role:
        return app._json_error("role not found", 404)
    if role.get("is_default_signup"):
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
        return app._json_error(f"audit write failed: {audit_exc}", 500)
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


# ==== feature-0012 ITEM-10 p14 — app.py 에서 이동 (2종). app 전역은 app.X 동적 참조. ====

def _list_roles(conn) -> list[dict[str, app.Any]]:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    r.Id AS id,
    r.RoleKey AS role_key,
    r.Name AS role_name,
    r.Description AS role_description,
    r.IsActive AS is_active,
    r.IsDefaultSignup AS is_default_signup,
    r.IconObjectKey AS icon_object_key,
    r.CreatedAt AS created_at,
    r.UpdatedAt AS updated_at,
    COUNT(CASE WHEN a.DeletedAt IS NULL THEN 1 END) AS member_count,
    -- TASK-20260623T014626-quota-ui-relocate: 역할 기본 LLM 토큰 한도(역할 상세 화면 편집용).
    (SELECT q.TokenLimit FROM WebRoleTokenQuotas q WHERE q.RoleId = r.Id AND q.QuotaType='daily' LIMIT 1) AS quota_daily,
    (SELECT q.TokenLimit FROM WebRoleTokenQuotas q WHERE q.RoleId = r.Id AND q.QuotaType='monthly' LIMIT 1) AS quota_monthly
FROM WebRoles r
LEFT JOIN WebAccounts a
  ON a.RoleId = r.Id
GROUP BY
    r.Id,
    r.RoleKey,
    r.Name,
    r.Description,
    r.IsActive,
    r.IsDefaultSignup,
    r.IconObjectKey,
    r.CreatedAt,
    r.UpdatedAt
ORDER BY
    r.IsDefaultSignup DESC,
    r.CreatedAt ASC
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    role_permission_map = app._load_role_permission_codes(
        conn,
        [int(row.get("id") or 0) for row in rows if int(row.get("id") or 0) > 0],
    )
    # TASK-0052 Phase 1B: catalog 1 회 조회 후 모든 role row 에 dynamic codes 까지 포함된 permissions 맵 build.
    _catalog_defs, catalog_codes, _catalog_map = app._resolve_permission_catalog(conn)
    items: list[dict[str, app.Any]] = []
    for row in rows:
        role_id = int(row.get("id") or 0)
        granted_codes = role_permission_map.get(role_id, set())
        items.append(
            {
                "id": role_id,
                "key": str(row.get("role_key") or ""),
                "name": str(row.get("role_name") or ""),
                "description": str(row.get("role_description") or ""),
                "is_active": bool(row.get("is_active")),
                "is_default_signup": bool(row.get("is_default_signup")),
                # TASK-0293: 역할 아이콘 URL. 설정 시 /api/roles/<id>/icon + 캐시버스터.
                # NULL=미설정 → 프론트가 role_key 시드 Identicon 렌더.
                "icon_url": app._role_icon_url_for(role_id, row.get("icon_object_key")),
                "created_at": str(row.get("created_at") or "") or None,
                "updated_at": str(row.get("updated_at") or "") or None,
                "member_count": int(row.get("member_count") or 0),
                "permission_codes": sorted(granted_codes),
                "permissions": {code: code in granted_codes for code in catalog_codes},
                # TASK-20260623T014626-quota-ui-relocate: 역할 기본 LLM 토큰 한도(null=미설정 무제한).
                "quota_daily": int(row["quota_daily"]) if row.get("quota_daily") is not None else None,
                "quota_monthly": int(row["quota_monthly"]) if row.get("quota_monthly") is not None else None,
            }
        )
    return items

def _enforce_role_permission_self_scope(
    actor: dict[str, app.Any] | None,
    submitted_codes: "Iterable[str] | None",
    current_codes: "Iterable[str] | None",
) -> set[str]:
    """TASK-0300 (REQ-0287): 역할 permission_codes 편집의 self-scope 가드 — privilege
    escalation 방지(역할 경유 우회 차단).

    - 본인 미보유 권한을 역할에 **신규 부여**(added = submitted − current)하면 ``ValueError`` → 403.
    - 본인 범위 밖의 기존 역할 권한은 보존(merge): UI 가 숨겨 payload 에서 누락돼도
      ``_set_role_permissions`` 의 delete-all-then-insert 로 제거되지 않게 한다. 즉 이미 부여돼
      있던 고권한을 "본인이 보유하지 않는다"는 이유로 임의 회수하지도 못한다(보존만).

    NOTE(의도된 비대칭 — 계정 override 의 ``_enforce_override_self_scope`` 와 다름): 역할은
    permission_codes 가 flat set 이라 이미 부여된 미보유 code 를 다시 제출해도 added 가 아니므로
    무해한 no-op (차단 X). 반면 계정 override 는 allow/deny **값**을 실어 미보유 code 제출 자체가
    의심 신호라 `submitted` 전체를 검사한다. 두 가드를 함부로 "통일" 하지 말 것.
    """
    editable = app._actor_editable_permission_codes(actor)
    submitted = {str(c) for c in (submitted_codes or set())}
    current = {str(c) for c in (current_codes or set())}
    illegal = sorted(code for code in (submitted - current) if code not in editable)
    if illegal:
        raise ValueError(
            "본인이 보유하지 않은 권한은 역할에 부여할 수 없습니다: " + ", ".join(illegal)
        )
    merged = set(submitted)
    for code in current:
        if code not in editable:
            merged.add(code)
    return merged


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (6종). app 전역은 app.X 동적 참조. ====

def _sanitize_role_key(value: str) -> str:
    return app.re.sub(r"[^a-z0-9_.-]", "", str(value or "").strip().lower())[:64]

def _is_valid_role_key(value: str) -> bool:
    return bool(app.ROLE_KEY_RE.match(str(value or "").strip().lower()))

def _validate_permission_codes(
    codes: list[str] | set[str] | tuple[str, ...],
    *,
    catalog_codes: Iterable[str] | None = None,
) -> set[str]:
    """TASK-0052 Phase 1A: catalog_codes 가 주어지면 그 catalog 에 포함된 code 만 허용."""
    allowed = set(catalog_codes) if catalog_codes is not None else set(app.PERMISSION_CODES)
    normalized = {str(code or "").strip() for code in codes if str(code or "").strip()}
    invalid = sorted(code for code in normalized if code not in allowed)
    if invalid:
        raise ValueError(f"unknown permissions: {', '.join(invalid)}")
    return normalized

def _set_role_permissions(conn, role_id: int, permission_codes: set[str]) -> None:
    permission_ids = app._permission_id_map(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM WebRolePermissions WHERE RoleId = %s", (int(role_id),))
    for code in sorted(permission_codes):
        permission_id = int(permission_ids.get(code) or 0)
        if permission_id <= 0:
            continue
        cur.execute(
            """
INSERT INTO WebRolePermissions (RoleId, PermissionId)
VALUES (%s, %s)
            """,
            (int(role_id), permission_id),
        )
    cur.close()

def _ensure_management_survivor_for_role_change(
    conn,
    role_id: int,
    next_role_permission_codes: set[str],
) -> None:
    accounts = app._list_active_accounts(conn)
    # TASK-0052 Phase 1B: catalog 1 회 조회 후 loop 에서 재사용.
    _catalog_defs, catalog_codes, _catalog_map = app._resolve_permission_catalog(conn)
    survivors = 0
    for account in accounts:
        account_role_id = int(account.get("role_id") or 0)
        if account_role_id == int(role_id):
            permissions = app._apply_permission_overrides(
                next_role_permission_codes,
                dict(account.get("permission_overrides") or {}),
                catalog_codes=catalog_codes,
            )
        else:
            permissions = app._account_permissions(account)
        if app._is_management_permission_set(permissions):
            survivors += 1
    if survivors <= 0:
        raise ValueError("관리 가능한 활성 계정은 최소 1개 이상 유지되어야 합니다.")

def _assign_default_signup_role(conn, role_id: int) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 0 WHERE Id <> %s", (int(role_id),))
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 1 WHERE Id = %s", (int(role_id),))
    cur.close()


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _load_role_by_id(conn, role_id: int) -> dict[str, app.Any] | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    Id AS id,
    RoleKey AS role_key,
    Name AS role_name,
    Description AS role_description,
    IsActive AS is_active,
    IsDefaultSignup AS is_default_signup,
    IconObjectKey AS icon_object_key,
    CreatedAt AS created_at,
    UpdatedAt AS updated_at
FROM WebRoles
WHERE Id = %s
LIMIT 1
        """,
        (int(role_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    granted_codes = app._load_role_permission_codes(conn, [int(role_id)]).get(int(role_id), set())
    # TASK-0052 Phase 1B: dynamic codes 포함된 catalog 로 permissions 맵 build.
    _catalog_defs, catalog_codes, _catalog_map = app._resolve_permission_catalog(conn)
    return {
        "id": int(row.get("id") or 0),
        "key": str(row.get("role_key") or ""),
        "name": str(row.get("role_name") or ""),
        "description": str(row.get("role_description") or ""),
        "is_active": bool(row.get("is_active")),
        "is_default_signup": bool(row.get("is_default_signup")),
        # TASK-0293: 역할 아이콘 URL (미설정 시 None → 프론트 role_key 시드 Identicon).
        "icon_url": app._role_icon_url_for(int(row.get("id") or 0), row.get("icon_object_key")),
        "created_at": str(row.get("created_at") or "") or None,
        "updated_at": str(row.get("updated_at") or "") or None,
        "permission_codes": sorted(granted_codes),
        "permissions": {code: code in granted_codes for code in catalog_codes},
    }
