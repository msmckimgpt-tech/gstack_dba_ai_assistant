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
from shared.model_catalog import canonical_usage_model_sql

INCLUDE_ORDER = 40  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
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
    # TASK-AIOPS: AI 상태 타일 — conn(worker heartbeat) + 축 헬퍼가 provider/datasource PG 를 자체
    #   RO 연결로 읽음. _isolate 위젯 격리 + 축별 try/except 로 한 축 실패가 전체를 깨지 않음.
    _isolate("ai_ops", lambda: app._dash_widget_ai_ops(conn))

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
async def admin_put_system_prompt(
    request: Request,
    actor=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch12: _require_account→account+conn 완전 DI. scope별 조건부 perm/403 은 본문 유지.
    # get_conn finally:close 가 _load_system_prompt·_upsert_system_prompt·audit raise 시 leak 해소.
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    scope = str(data.get("scope") or "").strip().lower()
    if scope not in ("global", "product", "role", "account"):
        return app._json_error("scope 은 global/product/role/account 중 하나여야 합니다.", 400)
    content = str(data.get("content") or "")
    product_id = int(data.get("product_id") or 0) or None
    role_id = int(data.get("role_id") or 0) or None
    account_id = int(data.get("account_id") or 0) or None
    if scope == "global":
        # TASK-0095: GLOBAL 은 product/role/account ids 무시 (force NULL).
        if not app._account_has_permission(actor, "system_prompt.global.write"):
            return app._json_error("전역 시스템 프롬프트 관리 권한이 없습니다.", 403)
        product_id = None
        role_id = None
        account_id = None
    elif scope == "product":
        if not app._account_has_permission(actor, "product.manage"):
            return app._json_error("제품 시스템 프롬프트 관리 권한이 없습니다.", 403)
        if not product_id:
            return app._json_error("product_id 가 필요합니다.", 400)
        role_id = None
        account_id = None
    elif scope == "role":
        if not app._account_has_permission(actor, "system_prompt.manage.role.any"):
            return app._json_error("역할 시스템 프롬프트 관리 권한이 없습니다.", 403)
        if not role_id:
            return app._json_error("role_id 가 필요합니다.", 400)
        account_id = None
    else:  # account
        target_account = account_id or int(actor["id"])
        if target_account != int(actor["id"]) and not app._account_has_permission(actor, "system_prompt.manage.role.any"):
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
        return app._json_error(f"audit write failed: {audit_exc}", 500)
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


# ==== feature-0012 ITEM-10 p13 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _load_dashboard_pref_row(conn, account_id: int) -> dict | None:
    cur = conn.cursor()
    try:
        cur.execute("SELECT Content FROM WebDashboardPreferences WHERE AccountId = %s", (int(account_id),))
        row = cur.fetchone()
    except Exception:
        return None
    finally:
        try:
            cur.close()
        except Exception:
            pass
    if not row or not row[0]:
        return None
    try:
        parsed = app.json.loads(row[0])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


# ==== feature-0012 ITEM-10 p14 — app.py 에서 이동 (9종). app 전역은 app.X 동적 참조. ====

def _dash_pct_delta(current, prior):
    """전기간(직전 동일 윈도우) 대비 변화율(%). prior 가 0/None 이면 None(기준선 없음)."""
    try:
        p = float(prior)
        if p <= 0:
            return None
        return round((float(current) - p) / p * 100.0, 1)
    except Exception:
        return None

def _dash_fill_daily(rows, days: int) -> list:
    """[(day, count)] (day=date/datetime/str) → 윈도우 일자별 정수 배열(오래된→최신, 결측=0).

    sparkline 용. 점 과밀 방지 위해 최대 60일. UTC 일자 기준 gap-fill(트렌드 근사이므로
    DB tz 미세차는 허용). days<2 면 단일 점이라 프런트가 sparkline 을 생략한다.
    """
    span = max(1, min(int(days), 60))
    counts: dict[str, int] = {}
    for r in (rows or []):
        d = r[0]
        if d is None:
            continue
        key = d.isoformat()[:10] if hasattr(d, "isoformat") else str(d)[:10]
        try:
            counts[key] = int(r[1] or 0)
        except Exception:
            counts[key] = 0
    today = datetime.now(app.timezone.utc).date()
    return [counts.get((today - app.timedelta(days=i)).isoformat(), 0) for i in range(span - 1, -1, -1)]

def _dash_widget_accounts(conn, days: int = 7) -> dict:
    d = int(days)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT "
            " SUM(CASE WHEN IsActive=1 AND DeletedAt IS NULL THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN IsActive=0 AND DeletedAt IS NULL THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN DeletedAt IS NOT NULL THEN 1 ELSE 0 END), "
            f" SUM(CASE WHEN LastLoginAt >= (NOW() - INTERVAL {d} DAY) AND DeletedAt IS NULL THEN 1 ELSE 0 END), "
            " COUNT(*) FROM WebAccounts"
        )
        r = cur.fetchone() or (0, 0, 0, 0, 0)
        active, inactive, deleted, recent, total = (int(x or 0) for x in r)
        cur.execute(
            "SELECT COALESCE(rr.Name, '(역할 없음)'), COUNT(*) "
            "FROM WebAccounts a LEFT JOIN WebRoles rr ON rr.Id = a.RoleId "
            "WHERE a.DeletedAt IS NULL GROUP BY a.RoleId, rr.Name ORDER BY 2 DESC LIMIT 8"
        )
        by_role = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    return {
        "tab": "accounts",
        "metrics": [
            {"label": "활성 계정", "value": active, "primary": True, "accent": "ok"},
            {"label": "비활성", "value": inactive},
            {"label": "삭제됨", "value": deleted, "accent": "muted"},
            {"label": f"최근 {d}일 로그인", "value": recent},
            {"label": "전체", "value": total},
        ],
        "lists": ([{"title": "역할별 계정", "rows": by_role}] if by_role else []),
    }

def _dash_widget_roles(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM WebRoles")
        role_count = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            "SELECT rr.Name, COUNT(rp.PermissionId) "
            "FROM WebRoles rr LEFT JOIN WebRolePermissions rp ON rp.RoleId = rr.Id "
            "GROUP BY rr.Id, rr.Name ORDER BY 2 DESC LIMIT 8"
        )
        by_perm = [{"label": str(x[0]), "value": int(x[1] or 0)} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    return {
        "tab": "roles",
        "metrics": [{"label": "역할 수", "value": role_count, "primary": True}],
        "lists": ([{"title": "역할별 권한 수", "rows": by_perm}] if by_perm else []),
    }

def _dash_widget_products(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT SUM(CASE WHEN IsActive=1 THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN IsActive=0 THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN DatasourceKey IS NOT NULL AND DatasourceKey <> '' THEN 1 ELSE 0 END), "
            " COUNT(*) FROM WebProducts"
        )
        r = cur.fetchone() or (0, 0, 0, 0)
        active, inactive, bound, total = (int(x or 0) for x in r)
    finally:
        cur.close()
    return {
        "tab": "products",
        "metrics": [
            {"label": "활성 제품", "value": active, "primary": True, "accent": "ok"},
            {"label": "비활성", "value": inactive, "accent": "muted"},
            {"label": "datasource 바인딩", "value": bound},
            {"label": "전체", "value": total},
        ],
        "lists": [],
    }

def _dash_widget_datasources(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute("SELECT SUM(CASE WHEN IsActive=1 THEN 1 ELSE 0 END), COUNT(*) FROM WebDatasources")
        r = cur.fetchone() or (0, 0)
        active, total = int(r[0] or 0), int(r[1] or 0)
        cur.execute("SELECT COALESCE(Engine,'mysql'), COUNT(*) FROM WebDatasources GROUP BY Engine ORDER BY 2 DESC LIMIT 8")
        by_engine = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    return {
        "tab": "datasources",
        "metrics": [
            {"label": "활성 데이터소스", "value": active, "primary": True, "accent": "ok"},
            {"label": "전체 등록", "value": total},
        ],
        "lists": ([{"title": "엔진별", "rows": by_engine}] if by_engine else []),
    }

def _dash_widget_usage(pg, days: int) -> dict:
    d = int(days)  # 호출부에서 [1,365] clamp → f-string 삽입 인젝션 불가
    cur_win = f"now() - interval '{d} days'"
    prior_lo = f"now() - interval '{2 * d} days'"

    def _cost_tok_for(cur, where):
        # usage-model-canonical: 대시보드 'AI 상태 > 사용량' 위젯의 '모델별 토큰' 목록도 canonical
        # family 로 접어(admin 콘솔 LLM 사용량 도넛과 동일 규칙) 라우팅 변형/실ID/gemma 폴백 중복 분점
        # 해소. 위젯이 deep-link 로 LLM 사용량 탭을 여므로 표기 정합 유지.
        _canon = canonical_usage_model_sql("COALESCE(resolved_model, model)")
        cur.execute(
            f"SELECT {_canon}, sum(total_tokens), sum(prompt_tokens), sum(completion_tokens) "
            f"FROM agent_runtime.llm_usage WHERE {where} GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 50"
        )
        rows = cur.fetchall() or []
        c = 0.0
        tk = 0
        models = []
        for x in rows:
            m = str(x[0] or "?")
            mt = int(x[1] or 0)
            c += app._estimate_llm_cost_usd(m, int(x[2] or 0), int(x[3] or 0))
            tk += mt
            models.append({"label": m, "value": mt})
        return round(c, 2), tk, models

    with pg.cursor() as cur:
        cur.execute(
            f"SELECT COALESCE(count(*),0), COALESCE(count(distinct run_id),0) "
            f"FROM agent_runtime.llm_usage WHERE created_at >= {cur_win}"
        )
        t = cur.fetchone() or (0, 0)
        calls, reqs = int(t[0] or 0), int(t[1] or 0)
        cost, tok, by_model = _cost_tok_for(cur, f"created_at >= {cur_win}")
        prior_cost, _ptok, _pm = _cost_tok_for(cur, f"created_at >= {prior_lo} AND created_at < {cur_win}")
        cur.execute(
            f"SELECT date_trunc('day', created_at)::date, sum(total_tokens) FROM agent_runtime.llm_usage "
            f"WHERE created_at >= {cur_win} GROUP BY 1 ORDER BY 1"
        )
        spark = app._dash_fill_daily(cur.fetchall(), d)
    primary = {"label": f"추정 비용 ({d}일)", "value": cost, "fmt": "usd", "primary": True, "spark": spark}
    dp = app._dash_pct_delta(cost, prior_cost)
    if dp is not None:
        primary["delta_pct"] = dp
        primary["delta_sentiment"] = "bad"  # 비용 증가는 부정 신호
    return {
        "tab": "usage",
        "metrics": [
            primary,
            {"label": "토큰", "value": tok},
            {"label": "요청", "value": reqs},
            {"label": "호출", "value": calls},
        ],
        "lists": ([{"title": "모델별 토큰", "rows": by_model[:8]}] if by_model else []),
        "window_days": d,
    }

def _dash_widget_ai_ops(conn) -> dict:
    """TASK-AIOPS: 대시보드 'AI 상태' 요약 타일 — 상태 배너(정상/저하/중단) + 워커/provider 요약.
    클릭 → AI 운영 현황 탭 deep-link(tab='ai-ops'). 상세(활동·비용·지연·카테고리 드릴다운)는 패널에서.

    상태 축 로직은 routers.ai_ops 를 재사용한다(request 시 lazy import — app↔routers 순환 회피).
    각 축 헬퍼가 provider/datasource PG 를 자체 RO 연결로 읽고 worker 는 conn(heartbeat)으로 읽어,
    한 축의 실패가 타 축에 전파되지 않는다(_isolate 위젯 격리 + 축별 try/except 이중 방어)."""
    from routers.ai_ops import (
        _provider_axis, _ask_worker_axis, _insight_worker_axis, _datasource_axis,
        _SEV, _SEV_LABEL,
    )
    axes = [_provider_axis(), _ask_worker_axis(conn), _insight_worker_axis(conn), _datasource_axis()]
    rolled = [a for a in axes if a["state"] != "na"]
    banner_state = "ok"
    for a in rolled:
        if _SEV.get(a["state"], 0) > _SEV.get(banner_state, 0):
            banner_state = a["state"]
    sentiment = {"ok": "good", "unknown": "warn", "degraded": "bad", "down": "bad"}.get(banner_state, "warn")
    workers_ok = sum(1 for a in (axes[1], axes[2]) if a["state"] == "ok")
    workers_total = sum(1 for a in (axes[1], axes[2]) if a["state"] != "na")
    return {
        "tab": "ai-ops",
        "metrics": [
            {"label": "종합 상태", "value": _SEV_LABEL.get(banner_state, banner_state),
             "primary": True, "sentiment": sentiment},
            {"label": "워커 정상", "value": f"{workers_ok}/{workers_total}"},
            {"label": "LLM 제공자", "value": _SEV_LABEL.get(axes[0]["state"], axes[0]["state"])},
        ],
        "lists": [{"title": "상태 축", "rows": [
            {"label": a["label"], "value": _SEV_LABEL.get(a["state"], a["state"])} for a in axes
        ]}],
    }

def _save_dashboard_pref_row(conn, account_id: int, content: dict) -> None:
    payload = app.json.dumps(content, ensure_ascii=False)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO WebDashboardPreferences (AccountId, Content) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE Content = VALUES(Content)",
            (int(account_id), payload),
        )
    finally:
        try:
            cur.close()
        except Exception:
            pass


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (5종). app 전역은 app.X 동적 참조. ====

def _permission_catalog_payload(
    *,
    catalog: list[dict[str, app.Any]] | None = None,
) -> list[dict[str, app.Any]]:
    """TASK-0052 Phase 1A: catalog 가 주어지면 그 list 를, None 이면 정적 PERMISSION_DEFINITIONS 를 반환.

    Phase 1B 에서 `_resolve_permission_catalog(conn)` 결과를 caller 가 전달.
    """
    source = catalog if catalog is not None else app.PERMISSION_DEFINITIONS
    return [dict(item) for item in source]

def _actor_can_see_widget(actor: dict, widget: dict) -> bool:
    """위젯 표시/데이터 권한 검사. `permission` 이 리스트면 하나라도 보유 시 True
    (TASK-0293: product/datasource 의 read|manage superset 게이팅 — _account_has_any_permission)."""
    perm = widget.get("permission")
    perms = perm if isinstance(perm, (list, tuple)) else (perm,)
    return app._account_has_any_permission(actor, *[str(p) for p in perms if p])

def _widget_data_scope(actor: dict, any_permission: str) -> str:
    """TASK-0294: 위젯 데이터 스코프 — `.any` 권한 보유 시 'any'(cross-account), 아니면 'own'(본인).

    audits/conversations 위젯은 `.own`/`.any` 짝을 가져, `.own` 만 보유한 사용자에게는
    본인 데이터로 스코프된 집계를 보여주고 cross-account(타 계정 username·소유자 집계)는
    `.any` 보유자에게만 노출한다. 위젯 가시성(_actor_can_see_widget)과 별개로 데이터 출력 경계."""
    return "any" if app._account_has_permission(actor, any_permission) else "own"

def _dashboard_default_prefs(actor: dict) -> dict:
    """actor 가 권한을 보유한 위젯만 기본 표시(카탈로그 순서)."""
    keys = [w["key"] for w in app._DASHBOARD_WIDGETS if app._actor_can_see_widget(actor, w)]
    return {
        "version": app._DASHBOARD_PREF_VERSION,
        "widgets": [{"key": k, "visible": True, "order": i} for i, k in enumerate(keys)],
    }

def _sanitize_dashboard_prefs(raw: dict) -> dict:
    """클라이언트 입력 prefs 를 알려진 위젯 키·boolean·int 로만 정규화.

    미지 키/중복/과대 입력을 거부한다. 권한 검증은 하지 않는다 — overview 가 권한
    없는 위젯 데이터를 애초에 반환하지 않으므로 prefs 에 그 키가 남아도 노출 위험이
    없고, 권한이 회복되면 그때 표시되도록 보존하는 편이 사용자 친화적이다.
    """
    widgets: list[dict] = []
    seen: set[str] = set()
    items = raw.get("widgets") if isinstance(raw, dict) else None
    if isinstance(items, list):
        for it in items[:64]:  # 과대 입력 상한
            if not isinstance(it, dict):
                continue
            key = str(it.get("key") or "")
            if key not in app._DASHBOARD_WIDGET_KEYS or key in seen:
                continue
            seen.add(key)
            try:
                order = int(it.get("order"))
            except Exception:
                order = len(widgets)
            widgets.append({"key": key, "visible": bool(it.get("visible", True)), "order": order})
    return {"version": app._DASHBOARD_PREF_VERSION, "widgets": widgets}


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (2종). app 전역은 app.X 동적 참조. ====

def _dash_widget_audits(conn, days: int = 7, *, scope: str = "any", account_id: int | None = None) -> dict:
    # TASK-0294: scope='own' 이면 본인이 actor 인 이벤트만 집계(ActorAccountId=self) + cross-account
    # by_actor(타 계정 username 목록)는 제거. scope='any' 는 전체 cross-account(기존). 위젯 가시성은
    # audit.read.own|any (둘 중 하나), 데이터 출력 경계는 본 scope — _audit_build_self_filter_sql 정합.
    d = int(days)
    own = scope == "own"
    if own and account_id is None:
        account_id = -1  # fail-closed: scope='own' 인데 account_id 부재 = 매칭 0(cross-account widen 금지).
    self_and = " AND ActorAccountId = %s" if own else ""
    self_args = (int(account_id),) if own else ()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY){self_and}",
            self_args,
        )
        cur_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {2 * d} DAY) AND OccurredAt < (NOW() - INTERVAL {d} DAY){self_and}",
            self_args,
        )
        prior_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt >= (NOW() - INTERVAL 1 DAY){self_and}",
            self_args,
        )
        last24 = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT DATE(OccurredAt), COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY){self_and} GROUP BY DATE(OccurredAt) ORDER BY 1",
            self_args,
        )
        spark = app._dash_fill_daily(cur.fetchall(), d)
        cur.execute(
            f"SELECT ActionCode, COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY){self_and} GROUP BY ActionCode ORDER BY 2 DESC LIMIT 8",
            self_args,
        )
        by_action = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
        # by_actor(타 계정 username × 활동량)는 cross-account enumeration — `.any` 전용. `.own` 은 생략.
        by_actor: list[dict] = []
        if not own:
            cur.execute(
                f"SELECT COALESCE(a.Username, '(익명/시스템)'), COUNT(*) "
                f"FROM WebAuditEvents ev LEFT JOIN WebAccounts a ON a.Id = ev.ActorAccountId "
                f"WHERE ev.OccurredAt >= (NOW() - INTERVAL {d} DAY) "
                f"GROUP BY ev.ActorAccountId, a.Username ORDER BY 2 DESC LIMIT 8"
            )
            by_actor = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    title_suffix = "(내 활동)" if own else ""
    primary = {"label": f"최근 {d}일 이벤트{title_suffix}", "value": cur_total, "primary": True, "spark": spark}
    dp = app._dash_pct_delta(cur_total, prior_total)
    if dp is not None:
        primary["delta_pct"] = dp
        primary["delta_sentiment"] = "neutral"  # 감사량 증감은 정보성(좋/나쁨 단정 불가)
    lists = []
    if by_action:
        lists.append({"title": f"액션별 ({d}일)", "rows": by_action})
    if by_actor:
        lists.append({"title": f"actor별 ({d}일)", "rows": by_actor})
    return {
        "tab": "audits",
        "metrics": [primary, {"label": "최근 24시간", "value": last24}],
        "lists": lists,
    }

def _dash_widget_conversations(pg, days: int = 7, *, scope: str = "any", account_id: int | None = None) -> dict:
    # TASK-0294: scope='own' 이면 본인 소유 대화만 집계(owner_account_id=self) + cross-account
    # '활성 소유자' metric(타 계정 수) 제거. scope='any' 는 전체(기존). 위젯 가시성은 conversation.list.own|any.
    d = int(days)
    cur_win = f"now() - interval '{d} days'"
    prior_lo = f"now() - interval '{2 * d} days'"
    prior_hi = cur_win
    own = scope == "own"
    if own and account_id is None:
        account_id = -1  # fail-closed: scope='own' 인데 account_id 부재 = 매칭 0(cross-account widen 금지).
    args = (int(account_id),) if own else ()

    def _w(extra: str) -> str:
        parts = [p for p in (extra, "owner_account_id = %s" if own else "") if p]
        return (" WHERE " + " AND ".join(parts)) if parts else ""

    # WHERE 절을 미리 구성(f-string 안 중첩 따옴표 회피 — Python 3.11 호환).
    one_day = "created_at >= now() - interval '1 day'"
    w_total = _w("")
    w_d1 = _w(one_day)
    w_cur = _w(f"created_at >= {cur_win}")
    w_prior = _w(f"created_at >= {prior_lo} AND created_at < {prior_hi}")
    base = "SELECT COUNT(*) FROM agent_runtime.core_conversations"
    with pg.cursor() as cur:
        cur.execute(f"{base}{w_total}", args)
        total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(f"{base}{w_d1}", args)
        d1 = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(f"{base}{w_cur}", args)
        cur_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(f"{base}{w_prior}", args)
        prior_total = int((cur.fetchone() or (0,))[0] or 0)
        # '활성 소유자'(distinct owner) 는 cross-account 집계 — `.own` 은 항상 본인 1명이라 생략.
        owners = None
        if not own:
            cur.execute("SELECT COUNT(DISTINCT owner_account_id) FROM agent_runtime.core_conversations WHERE owner_account_id IS NOT NULL")
            owners = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT date_trunc('day', created_at)::date, count(*) FROM agent_runtime.core_conversations"
            f"{w_cur} GROUP BY 1 ORDER BY 1",
            args,
        )
        spark = app._dash_fill_daily(cur.fetchall(), d)
    title_suffix = "(내 대화)" if own else ""
    primary = {"label": f"최근 {d}일 대화{title_suffix}", "value": cur_total, "primary": True, "spark": spark}
    dp = app._dash_pct_delta(cur_total, prior_total)
    if dp is not None:
        primary["delta_pct"] = dp
        primary["delta_sentiment"] = "neutral"
    metrics = [
        primary,
        {"label": "최근 24시간", "value": d1, "accent": "ok"},
        {"label": "내 전체 대화" if own else "전체 대화", "value": total},
    ]
    if owners is not None:
        metrics.append({"label": "활성 소유자", "value": owners})
    return {"metrics": metrics, "lists": []}
