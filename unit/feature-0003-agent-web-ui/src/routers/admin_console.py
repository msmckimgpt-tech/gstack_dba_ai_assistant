"""feature-0012 P5b Final — admin_console 도메인 APIRouter (관리 콘솔 메타: me·권한·DB·개요·헬스).

완전-DI 핸들러 5종(admin_me·admin_permissions·admin_list_available_databases·admin_overview·
admin_health_attachment_grants, require_permission RP). uniform `import app`+`app.X` 동적참조
(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존. 핸들러-사용 stdlib 명시 import.
순환 안전(맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app

router = APIRouter()


@router.get("/api/admin/me")
def admin_me(request: Request, account=Depends(app.require_permission("console.access", message="관리 콘솔 접근 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """관리 콘솔 전용 self 정보 endpoint (TASK-0098).

    `console.access` permission 보유자만 200 + permissions 포함 응답을 받는다.
    미보유자 = 403, 비로그인 = 401. admin.js 가 본 endpoint 로 진입 게이트를
    검사한다 — `/api/auth/me` (일반 self) 의 permissions 필드가 제거되어도
    admin 콘솔 진입이 깨지지 않도록 분리한 admin-context endpoint.

    Codex outside voice F1 (blocker) 흡수.
    """
    user_payload = app._serialize_account(account, include_permissions=True) or {}
    app._strip_quota_fields_if_unpermitted(user_payload, account)
    return JSONResponse({
        "ok": True,
        "user": user_payload,
    })


@router.get("/api/admin/permissions")
def admin_permissions(request: Request, account=Depends(app.require_permission("console.access", message="관리 콘솔 접근 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    # TASK-0052 Phase 1A: catalog 를 app._resolve_permission_catalog 경로로 조회.
    # Phase 1A 시점에는 정적 PERMISSION_DEFINITIONS 와 동일한 결과지만, plumbing 을 미리 검증.
    # Phase 1B 에서 conn 이 동적 product 권한까지 union 한 catalog 를 반환하도록 확장 예정.
    catalog_definitions, _catalog_codes, _catalog_map = app._resolve_permission_catalog(conn)
    return JSONResponse({"permissions": app._permission_catalog_payload(catalog=catalog_definitions)})


@router.get("/api/admin/databases/available")
def admin_list_available_databases(request: Request, account=Depends(app.require_permission("console.access", message="관리 콘솔 접근 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """Live MySQL `SHOW DATABASES` enumeration for the product DB whitelist picker.

    - 권한: `console.access` (등록은 별도로 `product.manage` 가 필요한 PUT /api/admin/products/{id}/databases 에서 검사).
    - `metadata_schemas`: 정책상 항상 접근 가능한 4 종 (REV-20260422-0006). 실제 서버 존재 여부는 `present` 필드로 표기.
    - `user_schemas`: 메타·내부(`agent_memory`, MEMORY_DB) 제외 + 정규식 통과 schema 만 정렬해 반환.
    """

    try:
        probe = app._open_memory_connection(database=None)
    except Exception:
        return app._json_error("DB 목록 조회 실패", 500)
    try:
        cur = probe.cursor()
        try:
            cur.execute("SHOW DATABASES")
            rows = [str((r[0] if isinstance(r, tuple) else r) or "").lower() for r in cur.fetchall()]
        finally:
            cur.close()
    finally:
        probe.close()

    present = {name for name in rows if name}
    metadata_payload = [
        {"schema_name": name, "present": name in present, "always_accessible": True}
        for name in app._DATABASES_AVAILABLE_METADATA
    ]
    excluded = set(app._DATABASES_AVAILABLE_METADATA) | set(app._DATABASES_AVAILABLE_INTERNAL)
    excluded.add(app.MEMORY_DB.lower())
    user_schemas = sorted(
        name for name in present
        if name not in excluded and app._DATABASES_AVAILABLE_NAME_RE.match(name)
    )
    return JSONResponse({
        "metadata_schemas": metadata_payload,
        "user_schemas": user_schemas,
    })


@router.get("/api/admin/overview")
def admin_overview(request: Request, actor=Depends(app.require_permission("console.access", message="관리 콘솔 접근 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0210: 관리 콘솔 대시보드 카테고리별 RBAC-스코프 집계.

    actor 가 보유한 표시 권한의 위젯 데이터만 반환한다 — 권한 경계가 곧 데이터
    노출 경계다(usage 권한 없는 operator 는 응답에 토큰/비용이 없음). 각 위젯은
    독립 try/except 로 격리되어 한 위젯의 DB 실패가 전체 대시보드를 깨뜨리지 않는다.
    `catalog` 는 actor 가 볼 수 있는 위젯 목록(client-rendered grant_health/pending 포함)을
    카탈로그 순서로 반환해 프런트가 권한 기준 위젯 집합을 서버 권위로 받게 한다.
    """
    try:
        days = int(request.query_params.get("days", "7"))
    except Exception:
        days = 7
    days = max(1, min(365, days))

    catalog = [
        {"key": w["key"], "title": w["title"], "source": w["source"]}
        for w in app._DASHBOARD_WIDGETS
        if app._actor_can_see_widget(actor, w)
    ]
    permitted = {c["key"] for c in catalog}
    widgets: dict = {}
    log = logging.getLogger(__name__)
    actor_id = int(actor["id"])
    # TASK-0294: `.own`/`.any` 짝 위젯의 데이터 스코프 — `.any` 미보유면 본인 데이터로 제한.
    audits_scope = app._widget_data_scope(actor, "audit.read.any")
    conv_scope = app._widget_data_scope(actor, "conversation.list.any")

    def _isolate(key: str, fn):
        if key not in permitted:
            return
        try:
            widgets[key] = fn()
        except Exception:
            log.warning("admin_overview: widget %s failed", key, exc_info=True)
            widgets[key] = {"error": True, "metrics": [], "lists": []}

    # MySQL 위젯 (시간 기반 위젯엔 days 윈도우 전파 — TASK-0218 거짓 컨트롤 정직화)
    _isolate("accounts", lambda: app._dash_widget_accounts(conn, days))
    _isolate("roles", lambda: app._dash_widget_roles(conn))
    _isolate("products", lambda: app._dash_widget_products(conn))
    _isolate("datasources", lambda: app._dash_widget_datasources(conn))
    _isolate("audits", lambda: app._dash_widget_audits(conn, days, scope=audits_scope, account_id=actor_id))

    # PG 위젯 (conversations + usage) — 단일 연결 재사용
    if ("conversations" in permitted) or ("usage" in permitted):
        pg = None
        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
        except Exception:
            log.warning("admin_overview: pg connect failed", exc_info=True)
            pg = None
        if pg is None:
            for k in ("conversations", "usage"):
                if k in permitted:
                    widgets[k] = {"error": True, "metrics": [], "lists": []}
        else:
            try:
                _isolate("conversations", lambda: app._dash_widget_conversations(pg, days, scope=conv_scope, account_id=actor_id))
                _isolate("usage", lambda: app._dash_widget_usage(pg, days))
            finally:
                try:
                    pg.close()
                except Exception:
                    pass

    return JSONResponse({"catalog": catalog, "widgets": widgets, "window_days": days})


@router.get("/api/admin/health/attachment-grants")
def admin_health_attachment_grants(request: Request, account=Depends(app.require_permission("console.access", message="요청을 수행할 수 없습니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0094 Sprint 1 Phase 10 (R-F4): sandbox schema grant drift detection.

    권한: `console.access` 보유 (admin). sandbox_schema.detect_grant_drift 호출
    후 drift 목록 반환. drift 가 있으면 admin alert (운영자가 maintenance path
    재실행).
    """
    try:
        from web.modules import sandbox_schema as _ssch
    except Exception as exc:
        return app._json_error(f"sandbox_schema 모듈 import 실패: {exc}", 500)
    try:
        drift = _ssch.detect_grant_drift(conn)
    except Exception as exc:
        return app._json_error(f"drift detection 실패: {exc}", 500)
    return JSONResponse(
        {
            "scanned_at": datetime.utcnow().isoformat() + "Z",
            "drift_count": len(drift),
            "drift": drift,
            "healthy": len(drift) == 0,
        }
    )


@router.get("/api/admin/system-prompts")
def admin_get_system_prompt(
    request: Request,
    scope: str,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    if scope not in ("global", "product", "role", "account"):
        return app._json_error("scope 은 global/product/role/account 중 하나여야 합니다.", 400)
    # scope 별 권한 검사
    if scope == "global":
        # TASK-0095: GLOBAL 은 product/role/account ids 무시 (force NULL).
        if not app._account_has_permission(actor, "system_prompt.global.read"):
            return app._json_error("전역 시스템 프롬프트 조회 권한이 없습니다.", 403)
        product_id = None
        role_id = None
        account_id = None
    elif scope == "product":
        if not app._account_has_permission(actor, "product.manage"):
            return app._json_error("제품 시스템 프롬프트 조회 권한이 없습니다.", 403)
    elif scope == "role":
        if not app._account_has_permission(actor, "system_prompt.manage.role.any"):
            return app._json_error("역할 시스템 프롬프트 조회 권한이 없습니다.", 403)
    else:  # account
        target_account = int(account_id or 0)
        if target_account != int(actor["id"]) and not app._account_has_permission(actor, "system_prompt.manage.role.any"):
            return app._json_error("타 계정 프롬프트 조회 권한이 없습니다.", 403)
    row = app._load_system_prompt(
        conn,
        scope=scope,
        product_id=int(product_id) if product_id else None,
        role_id=int(role_id) if role_id else None,
        account_id=int(account_id) if account_id else None,
    )
    return JSONResponse({"prompt": row, "scope": scope})

@router.put("/api/admin/system-prompts")
async def admin_put_system_prompt(request: Request) -> JSONResponse:
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
    scope = str(data.get("scope") or "").strip().lower()
    if scope not in ("global", "product", "role", "account"):
        conn.close()
        return app._json_error("scope 은 global/product/role/account 중 하나여야 합니다.", 400)
    content = str(data.get("content") or "")
    product_id = int(data.get("product_id") or 0) or None
    role_id = int(data.get("role_id") or 0) or None
    account_id = int(data.get("account_id") or 0) or None
    if scope == "global":
        # TASK-0095: GLOBAL 은 product/role/account ids 무시 (force NULL).
        if not app._account_has_permission(actor, "system_prompt.global.write"):
            conn.close()
            return app._json_error("전역 시스템 프롬프트 관리 권한이 없습니다.", 403)
        product_id = None
        role_id = None
        account_id = None
    elif scope == "product":
        if not app._account_has_permission(actor, "product.manage"):
            conn.close()
            return app._json_error("제품 시스템 프롬프트 관리 권한이 없습니다.", 403)
        if not product_id:
            conn.close()
            return app._json_error("product_id 가 필요합니다.", 400)
        role_id = None
        account_id = None
    elif scope == "role":
        if not app._account_has_permission(actor, "system_prompt.manage.role.any"):
            conn.close()
            return app._json_error("역할 시스템 프롬프트 관리 권한이 없습니다.", 403)
        if not role_id:
            conn.close()
            return app._json_error("role_id 가 필요합니다.", 400)
        account_id = None
    else:  # account
        target_account = account_id or int(actor["id"])
        if target_account != int(actor["id"]) and not app._account_has_permission(actor, "system_prompt.manage.role.any"):
            conn.close()
            return app._json_error("타 계정 프롬프트 관리 권한이 없습니다.", 403)
        account_id = target_account
        role_id = None
    # before-state 캡처 (audit) — 기존 prompt 본문 length 비교를 위해.
    before_prompt = app._load_system_prompt(
        conn, scope=scope, product_id=product_id, role_id=role_id, account_id=account_id,
    ) or {}
    new_id = app._upsert_system_prompt(
        conn,
        scope=scope,
        content=content,
        product_id=product_id,
        role_id=role_id,
        account_id=account_id,
        updated_by_account_id=int(actor["id"]),
    )
    # TASK-0073 Phase A5: same-tx audit hook (system_prompt update).
    try:
        app._audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.system_prompt.update",
            resource_type="system_prompt",
            resource_id=f"{scope}:{product_id or 0}:{role_id or 0}:{account_id or 0}",
            before={"content": str(before_prompt.get("content") or "")},
            after={"content": content},
            request_ctx={
                "scope": scope,
                "product_id": product_id,
                "role_id": role_id,
                "account_id": account_id,
            },
            target_account_id=int(account_id) if (scope == "account" and account_id) else None,
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
    return JSONResponse({"ok": True, "id": new_id, "scope": scope, "deleted": new_id == 0})

@router.get("/api/admin/dashboard/preferences")
def admin_get_dashboard_prefs(request: Request, actor=Depends(app.require_permission("console.access", message="관리 콘솔 접근 권한이 필요합니다.")), conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-0210: 본인 계정의 대시보드 위젯 표시/순서 prefs (없으면 권한 기반 기본값).

    별도 RBAC 권한 없이 console.access 만 요구 — 본인 대시보드 레이아웃은 self-service.
    """
    defaults = app._dashboard_default_prefs(actor)
    saved = app._load_dashboard_pref_row(conn, int(actor["id"]))
    if saved and isinstance(saved.get("widgets"), list) and saved["widgets"]:
        return JSONResponse({
            "preferences": app._sanitize_dashboard_prefs(saved),
            "defaults": defaults,
            "customized": True,
        })
    return JSONResponse({"preferences": defaults, "defaults": defaults, "customized": False})

@router.put("/api/admin/dashboard/preferences")
async def admin_put_dashboard_prefs(request: Request) -> JSONResponse:
    """TASK-0210: 본인 계정 대시보드 prefs 저장(영속). 알려진 위젯 키로만 정규화."""
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        actor, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(actor, "console.access"):
            return app._json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
        prefs = app._sanitize_dashboard_prefs(data if isinstance(data, dict) else {})
        try:
            app._save_dashboard_pref_row(conn, int(actor["id"]), prefs)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            # REV-20260611-0210 MINOR: raw 예외 텍스트(드라이버 메시지·테이블/컬럼명)를
            # 클라이언트에 노출하지 않는다(선례 엔드포인트 정합) — 서버측에만 기록.
            logging.getLogger(__name__).warning("admin_put_dashboard_prefs: save failed", exc_info=True)
            return app._json_error("대시보드 설정 저장에 실패했습니다.", 500)
        return JSONResponse({"ok": True, "preferences": prefs})
    finally:
        try:
            conn.close()
        except Exception:
            pass
