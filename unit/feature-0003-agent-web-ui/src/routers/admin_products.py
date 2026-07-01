"""feature-0012 P5b Final — admin_products 도메인 APIRouter (제품 CRUD/데이터소스/DB규칙/인사이트/프롬프트).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import asyncio
import logging
import re

from datetime import datetime
from datetime import timezone
from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from typing import Any

import app

router = APIRouter()


@router.patch("/api/admin/products/{product_id}/datasource")
async def admin_set_product_datasource(product_id: int, request: Request) -> JSONResponse:
    """product → datasource 키 바인딩 설정 (멀티 datasource P1).

    body: { datasource_key: str|null }. null/"" → 기본 단일 MySQL(DB_HOST)로 환원.
    값은 .env 에 등록된 datasource 키(config.DATASOURCES)여야 한다 — 미등록 키 거부(오타로 인한
    조용한 기본 폴백 방지). 좌표/비밀번호는 저장하지 않는다 (키만 — security-first, secret in env).
    관리 콘솔 수정 권한(console.access + console.manage) 필요.
    """
    from shared import datasources as _dsr
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    raw_key = (data.get("datasource_key") if isinstance(data, dict) else None)
    key = (str(raw_key).strip().lower() if raw_key not in (None, "") else None)
    # TASK-0205 §2.4: 제품별 참조 DB(MSSQL). datasource_database 키가 body 에 있을 때만 갱신.
    has_db_field = isinstance(data, dict) and ("datasource_database" in data)
    raw_db = (data.get("datasource_database") if isinstance(data, dict) else None)
    product_db = (str(raw_db).strip() if raw_db not in (None, "") else None)
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
    # TASK-0205: 키 검증을 레지스트리(DB+env)로 — .env 뿐 아니라 DB 등록 datasource 도 허용.
    _bound_ds = _dsr.resolve(conn, key) if key is not None else None
    if key is not None and _bound_ds is None:
        conn.close()
        return app._json_error(f"미등록 datasource 라벨: {key} (WebDatasources / .env 확인)", 400)
    # TASK-0205 MAJOR-1 (REV-0205 재게이트): 제품별 참조 DB override 의 **GRANT-범위 fail-closed 검증**.
    # admin 이 RO 로그인 접근 밖 DB 를 지정하면 product 바인딩만으로 권한 없는 DB 조회가 되는 것을 차단.
    # datasource 의 RO 로그인이 실제 접근 가능한 DB 목록(list_server_databases)에 속해야 허용(대소문자 무관).
    if has_db_field and product_db and _bound_ds is not None:
        from shared import db as _db
        okssrf, reason, _pin = app._ssrf_check_host(_bound_ds.get("host"))
        if not okssrf:
            conn.close()
            return app._json_error(f"호스트 차단(SSRF): {reason}", 400)
        try:
            _accessible = {str(n).strip().lower() for n in _db.list_server_databases({**_bound_ds, "host": _pin})}
        except Exception:
            conn.close()
            return app._json_error("참조 DB 검증 실패(datasource 연결/권한 확인).", 502)
        if product_db.strip().lower() not in _accessible:
            conn.close()
            return app._json_error(
                f"참조 DB '{product_db}' 는 datasource '{key}' 의 RO 로그인 접근 범위 밖입니다(거부).", 400)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
            if not cur.fetchone():
                return app._json_error("product not found", 404)
            # TASK-0277: 라벨 → stable surrogate Id(dual-write anchor). key=None(기본 단일 MySQL 환원)이면 None.
            _ds_id = None
            if key is not None:
                cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (key,))
                _idr = cur.fetchone()
                _ds_id = int(_idr[0]) if _idr and _idr[0] is not None else None
            if has_db_field:
                try:
                    cur.execute("UPDATE WebProducts SET DatasourceKey=%s, DatasourceDatabase=%s WHERE Id=%s",
                                (key, product_db, int(product_id)))
                except Exception:
                    # DatasourceDatabase 컬럼 부재(구 스키마) — 키만 갱신
                    cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (key, int(product_id)))
            else:
                cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (key, int(product_id)))
            # TASK-0277 dual-write: DatasourceId anchor 동기화(없으면 NULL). 컬럼 부재 graceful.
            try:
                cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s", (_ds_id, int(product_id)))
            except Exception:
                pass
        finally:
            cur.close()
        app.record_audit_event(
            conn,
            actor=app._build_actor_from_request(request, actor, actor_type="account"),
            action="admin.product.datasource.set",
            resource_type="product",
            resource_id=str(product_id),
            change_json={"datasource_key": key, **({"datasource_database": product_db} if has_db_field else {})},
        )
        # TASK-0228 (1:N): primary 바인딩을 join 테이블에도 동기화한다.
        #  - key 가 None(환원): 이 제품의 모든 primary 마킹 해제(다른 바인딩이 있으면 정렬상 보조로 강등).
        #  - key 설정: join 에 INSERT IGNORE + 그 키만 IsPrimary=1, 나머지는 0.
        try:
            cur2 = conn.cursor()
            try:
                cur2.execute("UPDATE WebProductDatasources SET IsPrimary=0 WHERE ProductId=%s", (int(product_id),))
                if key is not None:
                    cur2.execute(
                        "INSERT IGNORE INTO WebProductDatasources (ProductId, DatasourceKey, SortOrder, IsPrimary) "
                        "VALUES (%s, %s, 0, 1)", (int(product_id), key))
                    cur2.execute(
                        "UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                        (int(product_id), key))
                    # TASK-0277 dual-write: 이 바인딩 행의 DatasourceId anchor. 컬럼 부재 graceful.
                    if _ds_id is not None:
                        try:
                            cur2.execute(
                                "UPDATE WebProductDatasources SET DatasourceId=%s WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                (_ds_id, int(product_id), key))
                        except Exception:
                            pass
            finally:
                cur2.close()
        except Exception:
            pass  # join 테이블 부재(미이전) — primary 컬럼만으로 동작(하위호환)
        conn.commit()
        return JSONResponse({"product_id": int(product_id), "datasource_key": key,
                             **({"datasource_database": product_db} if has_db_field else {})})
    finally:
        conn.close()

@router.get("/api/admin/products/{product_id}/datasources")
async def admin_list_product_datasources(product_id: int, request: Request) -> JSONResponse:
    """TASK-0228 (1:N): 제품에 바인딩된 datasource 목록 + 각 datasource 의 접근가능 DB.

    console.access. 단일 바인딩(레거시) 제품도 primary 1건으로 반환(하위호환).
    """
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(actor, "console.access"):
        conn.close()
        return app._json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    # TASK-0288: 제품 구성 조회 권한(read|manage).
    if not app._account_has_any_permission(actor, "product.read", "product.manage"):
        conn.close()
        return app._json_error("제품 조회 권한이 필요합니다.", 403)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
            if not cur.fetchone():
                return app._json_error("product not found", 404)
        finally:
            cur.close()
        binds = app._list_product_datasources(conn, int(product_id))
        out = []
        for b in binds:
            dsk = b["datasource_key"]
            out.append({
                "datasource_key": dsk,
                "is_primary": b["is_primary"],
                "sort_order": b["sort_order"],
                "databases": app._product_allowed_schemas_for_datasource(conn, int(product_id), dsk),
            })
        return JSONResponse({"product_id": int(product_id), "datasources": out})
    finally:
        conn.close()

@router.post("/api/admin/products/{product_id}/datasources")
async def admin_add_product_datasource(product_id: int, request: Request) -> JSONResponse:
    """TASK-0228 (1:N): 제품에 datasource 바인딩 추가. console.access + console.manage + audit.

    body: { datasource_key: str, is_primary?: bool }. 미등록 키 거부(레지스트리 검증). 첫 바인딩이면
    자동 primary. is_primary=true 면 기존 primary 해제 + WebProducts.DatasourceKey 포인터도 갱신
    (resolve/insight 의 primary 경로 정합)."""
    from shared import datasources as _dsr
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    raw_key = (data.get("datasource_key") if isinstance(data, dict) else None)
    key = (str(raw_key).strip().lower() if raw_key not in (None, "") else None)
    if not key:
        return app._json_error("datasource_key 는 필수입니다.", 400)
    want_primary = bool(data.get("is_primary")) if isinstance(data, dict) else False
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not (app._account_has_permission(actor, "console.access") and app._account_has_permission(actor, "console.manage")):
        conn.close()
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    # 레지스트리 검증(미등록 키 거부 — 오타 silent 폴백 차단, PATCH 와 동일 게이트).
    if _dsr.resolve(conn, key) is None:
        conn.close()
        return app._json_error(f"미등록 datasource 라벨: {key} (WebDatasources / .env 확인)", 400)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
            if not cur.fetchone():
                return app._json_error("product not found", 404)
            # 현재 바인딩 수 — 첫 바인딩이면 강제 primary.
            cur.execute("SELECT COUNT(*) FROM WebProductDatasources WHERE ProductId=%s", (int(product_id),))
            existing = int((cur.fetchone() or [0])[0])
            # TASK-0277: 라벨 → stable surrogate Id 해석(dual-write anchor). 위 _dsr.resolve 검증을 통과한 키라
            # 보통 WebDatasources 에 존재(.env 전용 키면 Id 없음 → None, 키 캐시로만 동작).
            cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (key,))
            _idr = cur.fetchone()
            _ds_id = int(_idr[0]) if _idr and _idr[0] is not None else None
            make_primary = want_primary or existing == 0
            if make_primary:
                cur.execute("UPDATE WebProductDatasources SET IsPrimary=0 WHERE ProductId=%s", (int(product_id),))
            cur.execute(
                "INSERT IGNORE INTO WebProductDatasources (ProductId, DatasourceKey, SortOrder, IsPrimary) "
                "VALUES (%s, %s, %s, %s)",
                (int(product_id), key, (existing + 1) * 10, 1 if make_primary else 0))
            # TASK-0277 dual-write: DatasourceId(신규/기존 행 모두) — 라벨 rename 에도 불변인 anchor. 컬럼 부재 graceful.
            if _ds_id is not None:
                try:
                    cur.execute("UPDATE WebProductDatasources SET DatasourceId=%s WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                (_ds_id, int(product_id), key))
                except Exception:
                    pass
            # 이미 존재하던 바인딩이면 INSERT IGNORE no-op → primary 의도면 명시 갱신.
            if make_primary:
                cur.execute(
                    "UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                    (int(product_id), key))
                # primary 포인터(WebProducts.DatasourceKey + DatasourceId)도 동기화 — resolve/insight primary 경로 정합.
                cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (key, int(product_id)))
                if _ds_id is not None:
                    try:
                        cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s", (_ds_id, int(product_id)))
                    except Exception:
                        pass
        finally:
            cur.close()
        app.record_audit_event(
            conn, actor=app._build_actor_from_request(request, actor, actor_type="account"),
            action="admin.product.datasource.add", resource_type="product", resource_id=str(product_id),
            change_json={"datasource_key": key, "is_primary": bool(make_primary)})
        conn.commit()
        return JSONResponse({"product_id": int(product_id), "datasource_key": key, "is_primary": bool(make_primary)})
    finally:
        conn.close()

@router.delete("/api/admin/products/{product_id}/datasources/{key}")
async def admin_remove_product_datasource(product_id: int, key: str, request: Request) -> JSONResponse:
    """TASK-0228 (1:N): 제품에서 datasource 바인딩 제거. console.access + console.manage + audit.

    제거 대상이 primary 였으면 남은 바인딩 중 첫째(SortOrder)를 새 primary 로 승격 + WebProducts.DatasourceKey
    포인터 갱신(없으면 NULL). 해당 datasource 의 접근DB(WebProductDatabases) 행도 함께 삭제(고아 차단)."""
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    k = (str(key).strip().lower() if key else "")
    if not k:
        return app._json_error("invalid datasource key", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    actor, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not (app._account_has_permission(actor, "console.access") and app._account_has_permission(actor, "console.manage")):
        conn.close()
        return app._json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    try:
        cur = conn.cursor()
        new_primary: str | None = None
        try:
            cur.execute(
                "SELECT IsPrimary FROM WebProductDatasources WHERE ProductId=%s AND LOWER(DatasourceKey)=%s LIMIT 1",
                (int(product_id), k))
            row = cur.fetchone()
            if not row:
                return app._json_error("이 제품에 바인딩되지 않은 datasource 입니다.", 404)
            was_primary = bool(row[0])
            cur.execute("DELETE FROM WebProductDatasources WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                        (int(product_id), k))
            # 해당 datasource 의 접근DB 행도 정리(고아 allowlist 차단 — 보안 경계).
            cur.execute("DELETE FROM WebProductDatabases WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                        (int(product_id), k))
            if was_primary:
                cur.execute(
                    "SELECT LOWER(DatasourceKey) FROM WebProductDatasources WHERE ProductId=%s "
                    "ORDER BY SortOrder ASC, DatasourceKey ASC LIMIT 1", (int(product_id),))
                nr = cur.fetchone()
                new_primary = (str(nr[0]).strip().lower() if nr and nr[0] else None)
                if new_primary:
                    cur.execute("UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                (int(product_id), new_primary))
                cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (new_primary, int(product_id)))
                # TASK-0277: primary 포인터의 DatasourceId 도 동기화(승격 키의 Id; 없으면 NULL). 컬럼 부재 graceful.
                try:
                    _np_id = None
                    if new_primary:
                        cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (new_primary,))
                        _npr = cur.fetchone()
                        _np_id = int(_npr[0]) if _npr and _npr[0] is not None else None
                    cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s", (_np_id, int(product_id)))
                except Exception:
                    pass
        finally:
            cur.close()
        app.record_audit_event(
            conn, actor=app._build_actor_from_request(request, actor, actor_type="account"),
            action="admin.product.datasource.remove", resource_type="product", resource_id=str(product_id),
            change_json={"datasource_key": k, "new_primary": new_primary})
        conn.commit()
        return JSONResponse({"product_id": int(product_id), "removed": k, "new_primary": new_primary})
    finally:
        conn.close()

@router.put("/api/admin/products/{product_id}/icon")
async def upload_product_icon(product_id: int, request: Request, file: UploadFile = File(...), account=Depends(app.require_permission("product.manage", message="제품 관리 권한이 필요합니다 (product.manage).")), conn=Depends(app.get_conn)) -> JSONResponse:
    """제품 아이콘 업로드(product.manage). 이전 아이콘 교체."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT IconObjectKey FROM WebProducts WHERE Id = %s", (int(product_id),))
        row = cur.fetchone()
    finally:
        cur.close()
    if row is None:
        return app._json_error("제품을 찾을 수 없습니다.", 404)
    old_key = row[0]
    body = await file.read()
    object_key, info = app._store_image_upload(
        body, prefix="product-icons", owner_id=int(product_id), max_bytes=app._ICON_MAX_BYTES,
        mime_hint=(file.content_type or ""),
    )
    if not object_key:
        return app._json_error(info, 400)
    cur = conn.cursor()
    try:
        cur.execute("UPDATE WebProducts SET IconObjectKey = %s WHERE Id = %s", (object_key, int(product_id)))
        conn.commit()
    finally:
        cur.close()
    if old_key and old_key != object_key:
        try:
            from web.modules import storage_minio
            storage_minio.delete_object(str(old_key))
        except Exception:
            pass
    return JSONResponse({"ok": True, "icon_url": app._product_icon_url_for(int(product_id), object_key)})

@router.delete("/api/admin/products/{product_id}/icon")
def delete_product_icon(product_id: int, request: Request, account=Depends(app.require_permission("product.manage", message="제품 관리 권한이 필요합니다 (product.manage).")), conn=Depends(app.get_conn)) -> JSONResponse:
    """제품 아이콘 제거(product.manage) → 기본/Identicon 폴백."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT IconObjectKey FROM WebProducts WHERE Id = %s", (int(product_id),))
        row = cur.fetchone()
        old_key = row[0] if row else None
        cur.execute("UPDATE WebProducts SET IconObjectKey = NULL WHERE Id = %s", (int(product_id),))
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

@router.get("/api/admin/products")
def admin_list_products(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    if not app._account_has_permission(account, "console.access"):
        return app._json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    # TASK-0288: 관리 콘솔 제품 구성 **조회** 권한 게이트(read 또는 manage). 기존엔 console.access 만
    # 검사해 제품 관리 권한 없이도 제품 목록·접근 DB·시스템 프롬프트 구성이 노출됐다(③ 결함).
    # 작업 화면 제품 사용(product.access.<key>)과는 별개 축 — 여기선 관리 콘솔 구성 조회만 게이팅.
    if not app._account_has_any_permission(account, "product.read", "product.manage"):
        return app._json_error("제품 조회 권한이 필요합니다.", 403)
    products = app._list_products(conn, include_inactive=True)
    for p in products:
        p["databases"] = app._list_product_databases(conn, int(p["id"]))
    return JSONResponse({"products": products})

@router.get("/api/admin/products/insight-coverage")
def admin_products_insight_coverage(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """제품별 insight-worker 분석 완료율 (TASK-0223). console.access. ?product_id= 단건, ?refresh=1 캐시 무시."""
    if not app._account_has_permission(account, "console.access"):
        return app._json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    # TASK-0288: 제품 구성 조회 권한(read|manage) — coverage 배지는 제품 탭 표면.
    if not app._account_has_any_permission(account, "product.read", "product.manage"):
        return app._json_error("제품 조회 권한이 필요합니다.", 403)
    raw_pid = request.query_params.get("product_id")
    only_pid = None
    if raw_pid not in (None, ""):
        try:
            only_pid = int(raw_pid)
        except Exception:
            return app._json_error("invalid product_id", 400)
    force = str(request.query_params.get("refresh") or "").strip() in ("1", "true", "yes")
    products = app._list_products(conn, include_inactive=True)
    # TASK-0253: 프론트가 head-of-line 제거를 위해 제품마다 ?product_id= 단건을 **병렬** 호출한다.
    #  본 핸들러는 일반 def 라 Starlette 스레드풀에서 자동 병렬 실행되므로, 단건 N개 동시 요청이
    #  가장 느린 1건 시간 안에 끝난다(_compute_product_insight_coverage 는 라이브 DB 조회라 무겁다).
    #  단건일 때 대상 제품만 계산하고 즉시 break — 무관 제품 순회/계산을 피한다.
    out: dict = {}
    for p in products:
        pid = int(p["id"])
        if only_pid is not None and pid != only_pid:
            continue
        cache_key = (pid, p.get("datasource_key") or "")
        cov = None if force else app._insight_cov_cache_get(cache_key)
        if cov is None:
            cov = app._compute_product_insight_coverage(conn, p)
            app._insight_cov_cache_put(cache_key, cov)
        out[str(pid)] = cov
        if only_pid is not None:
            break
    return JSONResponse({"coverage": out})

@router.get("/api/admin/products/{product_id}/db-insights")
def admin_product_db_insights(product_id: int, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """제품의 datasource 별 DB insight 파악 내용 (TASK-0242). console.access.
    ?datasource=<key> 로 멀티 datasource 의 특정 바인딩 scope 선택(미지정=primary/legacy)."""
    if not app._account_has_permission(account, "console.access"):
        return app._json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    # TASK-0288: 제품 구성 조회 권한(read|manage).
    if not app._account_has_any_permission(account, "product.read", "product.manage"):
        return app._json_error("제품 조회 권한이 필요합니다.", 403)
    products = app._list_products(conn, include_inactive=True)
    product = next((p for p in products if int(p["id"]) == int(product_id)), None)
    if not product:
        return app._json_error("제품을 찾을 수 없습니다.", 404)
    req_ds = (request.query_params.get("datasource") or "").strip().lower()
    if req_ds:
        # 요청 datasource 가 제품에 바인딩됐는지 검증(임의 scope 조회 차단).
        bound = {b["datasource_key"] for b in app._list_product_datasources(conn, int(product_id))}
        if req_ds not in bound:
            return app._json_error("해당 제품에 바인딩되지 않은 데이터소스입니다.", 400)
    result = app._compute_product_db_insights(conn, product, req_ds or None)
    return JSONResponse(result)

@router.post("/api/admin/products/{pid:int}/insight-reset")
async def admin_product_insight_reset(request: Request, pid: int) -> JSONResponse:
    """제품의 접근 가능 데이터베이스 1개에 대한 insight 분석을 초기화(삭제)한다 (TASK-0228).

    권한 `insight.reset` (admin 한정 — 파괴적). body `{db: str, dry_run: bool}`.
    dry_run=true: 삭제 대상 건수만 반환(삭제 X). false: 단일 PG tx 로 fact/rag/KV 삭제 + self-audit.

    **DB 단위 삭제 주의**: 같은 datasource·같은 DB 를 공유하는 다른 제품의 완료율도 함께 0이 된다
    (insight 는 product 가 아니라 datasource-scope + DB 단위로 저장되므로). UI 가 이를 경고한다.
    삭제 후 insight-worker 가 다음 cycle 에 fingerprint 부재를 감지해 자동 재분석한다.
    """
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    db_name = str(data.get("db") or "").strip()
    dry_run = bool(data.get("dry_run"))
    if not db_name:
        return app._json_error("db (접근 가능 데이터베이스명) 가 필요합니다.", 400)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        if not app._account_has_permission(account, "insight.reset"):
            return app._json_error("insight 분석 초기화 권한이 필요합니다.", 403)

        product = next(
            (p for p in app._list_products(conn, include_inactive=True) if int(p["id"]) == pid),
            None,
        )
        if not product:
            return app._json_error("제품을 찾을 수 없습니다.", 404)

        # 요청 DB 가 실제로 이 제품의 접근 가능 DB 인지 검증 (임의 DB 주입 차단).
        accessible = {
            str(d.get("schema_name") or "").strip().lower()
            for d in app._list_product_databases(conn, pid)
            if d.get("schema_name")
        }
        if db_name.strip().lower() not in accessible:
            return app._json_error("해당 제품의 접근 가능 데이터베이스가 아닙니다.", 400)

        resolved = app._resolve_product_insight_scope(conn, product)
        if not resolved["ok"]:
            return app._json_error(f"데이터소스 스코프 해석 불가: {resolved['reason']}", 400)
        scope = resolved["scope"]
        allow_null = resolved["allow_null"]
        scope_aliases = resolved.get("scope_aliases") or ([scope] if scope else [])
        engine = resolved["engine"]
        coords = resolved["coords"]

        # ── 라이브 카탈로그 조회: 해당 DB 의 (schema, table) 쌍 + schema 집합 ──
        # TASK-0230 (M1): rag_objects 삭제를 완료율 분자(_compute_product_insight_coverage)와 **동일한
        # (schema_name, table_name) 교집합** 으로 통일한다. object_key LIKE 방식은 MSSQL 2-tier 레거시
        # (catalog-less `{scope}:dbo.t`)를 놓쳐 "지웠는데 완료율 그대로" 를 유발했다(보안리뷰 M1).
        # live schema 목록은 fact/KV 의 2-tier 레거시 키 패턴(catalog-less) 생성에도 쓴다.
        from shared import db as _db
        live_pairs: set = set()       # {(schema_lower, table_lower)}
        live_schemas: set = set()     # {schema_lower}
        okssrf, _ssrf_reason, pin = app._ssrf_check_host((coords or {}).get("host"))
        if not okssrf:
            return app._json_error("데이터소스 호스트 차단(SSRF)", 400)
        coords_pinned = {**coords, "host": pin}
        try:
            if engine == "mssql":
                rows = _db.list_information_schema_tables(coords_pinned, database=db_name, timeout=5)
            else:
                rows = _db.list_information_schema_tables(coords_pinned, schemas=[db_name], timeout=5)
            for s, t in rows:
                sl = str(s).strip().lower()
                tl = str(t).strip().lower()
                live_pairs.add((sl, tl))
                live_schemas.add(sl)
        except Exception as exc:
            logging.getLogger("app").warning("insight_reset catalog fail pid=%s db=%s err=%r", pid, db_name, exc)
            return app._json_error("데이터소스 카탈로그 조회 실패(연결/권한) — 초기화 대상 산정 불가.", 502)
        # MySQL 은 db==schema 라 live_schemas={db} 가 정상. MSSQL 은 dbo 등.

        fact_patterns = app._insight_reset_fact_key_patterns(db_name, scope_aliases, allow_null, live_schemas)
        kv_patterns = app._insight_reset_kv_key_patterns(db_name, scope_aliases, allow_null, live_schemas)

        try:
            from shared.db import _pg_connect
            pg = _pg_connect()
        except Exception as exc:
            logging.getLogger("app").warning("insight_reset pg connect fail pid=%s err=%r", pid, exc)
            return app._json_error("PG 연결 실패 — insight 저장소에 접근할 수 없습니다.", 500)

        fact_like_sql = " OR ".join(["fact_key LIKE %s ESCAPE '\\'"] * len(fact_patterns))
        kv_like_sql = " OR ".join(["key LIKE %s ESCAPE '\\'"] * len(kv_patterns))
        # rag_objects: 완료율 분자와 동일하게 (schema_name, table_name) 교집합 + schema 노드로 매칭.
        #   table 노드: (lower(schema_name), lower(table_name)) ∈ live_pairs
        #   schema 노드: lower(schema_name) ∈ live_schemas
        # 2-tier/3-tier object_key 형식과 무관 — schema_name/table_name 컬럼만 본다(완료율과 동일 행 집합).
        ro_ds_sql = "(datasource_key = %s" + (" OR datasource_key IS NULL" if allow_null else "") + ")"
        pair_vals = sorted(live_pairs)
        schema_vals = sorted(live_schemas)

        def _count_or_delete_rag(pgc_, do_delete: bool) -> int:
            """rag_objects 의 schema/table 노드를 (schema,table) 교집합으로 count 또는 delete."""
            total = 0
            verb = "DELETE FROM" if do_delete else "SELECT COUNT(*) FROM"
            # table 노드 — (schema,table) IN (...). 빈 집합이면 skip.
            if pair_vals:
                tuple_ph = ",".join(["(%s,%s)"] * len(pair_vals))
                flat: list = []
                for s, t in pair_vals:
                    flat.extend([s, t])
                sql_t = (
                    f"{verb} public.rag_objects "
                    f"WHERE conversation_id = %s AND scope_key = %s AND object_type = 'table' "
                    f"AND (lower(schema_name), lower(table_name)) IN ({tuple_ph}) AND {ro_ds_sql}"
                )
                pgc_.execute(sql_t, ["__global__", "common", *flat, scope])
                total += (pgc_.rowcount if do_delete else int((pgc_.fetchone() or [0])[0])) or 0
            # schema 노드 — lower(schema_name) IN (...).
            if schema_vals:
                sch_ph = ",".join(["%s"] * len(schema_vals))
                sql_s = (
                    f"{verb} public.rag_objects "
                    f"WHERE conversation_id = %s AND scope_key = %s AND object_type = 'schema' "
                    f"AND lower(schema_name) IN ({sch_ph}) AND {ro_ds_sql}"
                )
                pgc_.execute(sql_s, ["__global__", "common", *schema_vals, scope])
                total += (pgc_.rowcount if do_delete else int((pgc_.fetchone() or [0])[0])) or 0
            return total

        try:
            pgc = pg.cursor()
            if dry_run:
                pgc.execute(
                    f"SELECT COUNT(*) FROM public.fact_entries "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                fact_n = int((pgc.fetchone() or [0])[0])
                pgc.execute(
                    f"SELECT COUNT(*) FROM public.rag_documents "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                doc_n = int((pgc.fetchone() or [0])[0])
                ro_n = _count_or_delete_rag(pgc, do_delete=False)
                pgc.execute(
                    f"SELECT COUNT(*) FROM agent_runtime.kv "
                    f"WHERE conversation_id = %s AND ({kv_like_sql})",
                    ["__global__", *kv_patterns],
                )
                kv_n = int((pgc.fetchone() or [0])[0])
                pg.close()
                return JSONResponse({
                    "dry_run": True, "db": db_name, "product_id": pid,
                    "to_delete": {
                        "fact_entries": fact_n, "rag_documents": doc_n,
                        "rag_objects": ro_n, "kv": kv_n,
                        "total": fact_n + doc_n + ro_n + kv_n,
                    },
                })

            # ── 실제 삭제 ──
            actor = app._build_actor_from_request(request, account, actor_type="account")
            started_at = datetime.now(timezone.utc)
            # TASK-0230 (M3): audit.purge 패턴 답습 — 파괴적 삭제 **전에** start 이벤트를 먼저 commit 한다.
            # audit write 가 실패하면 삭제를 진행하지 않는다(정합성 fail-safe; 삭제만 되고 흔적 없는 상황 차단).
            try:
                app.record_audit_event(
                    conn, actor=actor, action="insight.reset.start",
                    resource_type="product_database", resource_id=f"{pid}:{db_name}",
                    change_json={
                        "product_id": pid, "db": db_name, "scope": scope,
                        "scope_aliases": scope_aliases, "allow_null": allow_null,
                        "started_at": started_at.isoformat(),
                    },
                )
                conn.commit()
            except Exception as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                pg.close()
                logging.getLogger("app").warning("insight_reset start-audit fail pid=%s err=%r", pid, exc)
                return app._json_error(f"초기화 시작 audit 기록 실패 — 삭제를 진행하지 않았습니다: {exc}", 500)

            deleted = {"fact_entries": 0, "rag_documents": 0, "rag_objects": 0, "kv": 0}
            pg.autocommit = False
            try:
                pgc.execute(
                    f"DELETE FROM public.fact_entries "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                deleted["fact_entries"] = pgc.rowcount or 0
                pgc.execute(
                    f"DELETE FROM public.rag_documents "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                deleted["rag_documents"] = pgc.rowcount or 0
                deleted["rag_objects"] = _count_or_delete_rag(pgc, do_delete=True)
                pgc.execute(
                    f"DELETE FROM agent_runtime.kv "
                    f"WHERE conversation_id = %s AND ({kv_like_sql})",
                    ["__global__", *kv_patterns],
                )
                deleted["kv"] = pgc.rowcount or 0
                pg.commit()
            except Exception as exc:
                try:
                    pg.rollback()
                except Exception:
                    pass
                pg.close()
                logging.getLogger("app").warning("insight_reset delete fail pid=%s db=%s err=%r", pid, db_name, exc)
                return app._json_error("insight 초기화 삭제 실패 — 변경이 롤백되었습니다. 로그를 확인하세요.", 500)
            pg.close()

            total_deleted = sum(deleted.values())
            completed_at = datetime.now(timezone.utc)
            # complete self-audit (best-effort — 삭제는 이미 성공, start 이벤트로 추적 보장됨).
            try:
                app.record_audit_event(
                    conn, actor=actor, action="insight.reset.complete",
                    resource_type="product_database", resource_id=f"{pid}:{db_name}",
                    change_json={
                        "product_id": pid, "db": db_name, "scope": scope,
                        "scope_aliases": scope_aliases, "allow_null": allow_null,
                        "deleted": deleted, "total_deleted": total_deleted,
                        "started_at": started_at.isoformat(), "completed_at": completed_at.isoformat(),
                    },
                )
                conn.commit()
            except Exception as exc:
                logging.getLogger("app").warning("insight_reset complete-audit fail pid=%s err=%r", pid, exc)

            # 완료율 캐시 무효화 (이 제품 + 같은 datasource 공유 제품들).
            try:
                with app._INSIGHT_COVERAGE_CACHE_LOCK:
                    app._INSIGHT_COVERAGE_CACHE.clear()
            except Exception:
                pass

            return JSONResponse({
                "dry_run": False, "db": db_name, "product_id": pid,
                "deleted": deleted, "total_deleted": total_deleted,
                "note": "다음 insight-worker cycle 에 자동 재분석됩니다.",
            })
        finally:
            try:
                if not pg.closed:
                    pg.close()
            except Exception:
                pass
    finally:
        conn.close()

@router.post("/api/admin/products")
async def admin_create_product(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(account, "product.manage"):
        conn.close()
        return app._json_error("제품 관리 권한이 필요합니다.", 403)
    product_key = str(data.get("product_key") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "").strip()
    sort_order = int(data.get("sort_order") or 100)
    is_active = bool(data.get("is_active", True))
    is_default = bool(data.get("is_default", False))
    # TASK-0053: product 의 default-role-access 정책 (D2-A 호환 default=True).
    default_role_access = bool(data.get("default_role_access", True))
    if not product_key or not name:
        conn.close()
        return app._json_error("product_key 와 name 은 필수입니다.", 400)
    if not re.match(r"^[A-Z][A-Z0-9_]{0,31}$", product_key):
        conn.close()
        return app._json_error("product_key 는 A-Z/0-9/_ 만, 1~32자 영문대문자로 시작.", 400)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM WebProducts WHERE ProductKey = %s", (product_key,))
    if int((cur.fetchone() or (0,))[0] or 0) > 0:
        cur.close()
        conn.close()
        return app._json_error("이미 존재하는 product_key 입니다.", 409)
    cur.close()
    # TASK-0052 Phase 1B (Codex Claim 2 — autocommit=True 기본 → 명시적 트랜잭션 wrapping):
    # WebProducts INSERT + WebPermissions INSERT (`product.access.<key>`, IsDynamic=1, ProductId=<new_id>)
    # + 모든 기존 role 에 grant backfill (D2-A 정책) 까지 한 commit/rollback. 부분 실패 시 product 자체를
    # 롤백해 drift 차단.
    new_id = 0
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            """
INSERT INTO WebProducts (ProductKey, Name, Description, IsActive, IsDefault, SortOrder, DefaultRoleAccess)
VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                product_key,
                name,
                description,
                1 if is_active else 0,
                1 if is_default else 0,
                sort_order,
                1 if default_role_access else 0,
            ),
        )
        new_id = int(cur.lastrowid or 0)
        if is_default:
            cur.execute("UPDATE WebProducts SET IsDefault = 0 WHERE Id <> %s", (new_id,))
        # 동적 권한 row 삽입 (Phase 1B 의 `_ensure_product_access_permissions` 와 동일 패턴, transaction 내 inline).
        permission_code = app._product_permission_code(product_key)
        cur.execute(
            """
INSERT INTO WebPermissions (Code, Label, Description, GroupName, IsDynamic, ProductId)
VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                permission_code,
                f"제품 접근 — {name}",
                f"이 계정은 {product_key} 제품에 접근할 수 있습니다 (대화 생성·pin·system prompt 읽기).",
                "product_access",  # TASK-0288: 작업 화면 제품 사용 권한 그룹.
                1,
                new_id,
            ),
        )
        new_permission_id = int(cur.lastrowid or 0)
        if new_permission_id <= 0:
            raise RuntimeError("permission row insert lastrowid empty")
        # TASK-0053: product 의 DefaultRoleAccess 정책 — true 면 모든 role 에 자동 grant, false 면 grant 안 함.
        # 정책의 주체는 product 자체 — 운영자가 product 생성 시 토글로 결정.
        if default_role_access:
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT r.Id, %s FROM WebRoles r
                """,
                (new_permission_id,),
            )
        cur.close()
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.autocommit = True
        conn.close()
        return app._json_error(f"제품 생성 실패: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
    # TASK-0073 Phase A5: same-tx audit hook (product create — after-state 만, before=None).
    try:
        app._audit_admin_mutation(
            conn,
            request,
            account,
            action="admin.product.create",
            resource_type="product",
            resource_id=str(new_id),
            before=None,
            after={
                "id": new_id,
                "product_key": product_key,
                "name": name,
                "description": description,
                "is_active": is_active,
                "default_role_access": default_role_access,
            },
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
    return JSONResponse({"ok": True, "product_id": new_id})

@router.patch("/api/admin/products/{product_id}")
async def admin_update_product(product_id: int, request: Request) -> JSONResponse:
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(account, "product.manage"):
        conn.close()
        return app._json_error("제품 관리 권한이 필요합니다.", 403)
    # TASK-0091 (REQ-20260520-0006, Codex outside voice C2): 명시 transaction —
    # autocommit=False + SELECT FOR UPDATE row lock + UPDATE + audit + commit.
    # 기존 코드는 autocommit=True default 라 UPDATE 가 즉시 commit 되어 audit
    # 실패 시 rollback 가능 0 였음 — audit integrity 결함. 본 cycle 에서 fix.
    try:
        conn.autocommit = False
    except Exception:
        pass
    try:
        # before snapshot — SELECT ... FOR UPDATE 로 row lock (concurrent PATCH 차단).
        existing = app._audit_product_snapshot(conn, product_id)
        if not existing:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.autocommit = True
            except Exception:
                pass
            conn.close()
            return app._json_error("product not found", 404)

        fields: list[str] = []
        params: list[Any] = []
        if "name" in data:
            fields.append("Name = %s")
            params.append(str(data.get("name") or "").strip())
        if "description" in data:
            fields.append("Description = %s")
            params.append(str(data.get("description") or "").strip())
        if "is_active" in data:
            fields.append("IsActive = %s")
            params.append(1 if bool(data.get("is_active")) else 0)
        if "sort_order" in data:
            fields.append("SortOrder = %s")
            params.append(int(data.get("sort_order") or 100))
        set_default = False
        if "is_default" in data:
            fields.append("IsDefault = %s")
            params.append(1 if bool(data.get("is_default")) else 0)
            set_default = bool(data.get("is_default"))
        # TASK-0053: default_role_access 정책 토글도 admin update 에서 변경 가능 (기존 product 정책 변경).
        if "default_role_access" in data:
            fields.append("DefaultRoleAccess = %s")
            params.append(1 if bool(data.get("default_role_access")) else 0)

        default_cleared_product_ids: list[int] = []
        if fields:
            params.append(int(product_id))
            cur = conn.cursor()
            cur.execute(f"UPDATE WebProducts SET {', '.join(fields)} WHERE Id = %s", tuple(params))
            cur.close()
            if set_default:
                # TASK-0091 (Codex C4): is_default=true side effect 추적 —
                # 영향 받은 product ids 를 audit ChangeJson 에 기록.
                cur = conn.cursor(dictionary=True)
                cur.execute(
                    "SELECT Id FROM WebProducts WHERE Id <> %s AND IsDefault = 1",
                    (int(product_id),),
                )
                default_cleared_product_ids = [int(r["Id"]) for r in (cur.fetchall() or [])]
                cur.close()
                cur = conn.cursor()
                cur.execute("UPDATE WebProducts SET IsDefault = 0 WHERE Id <> %s", (int(product_id),))
                cur.close()

        # after snapshot — UPDATE 결과 full row 캡처.
        updated = app._audit_product_snapshot(conn, product_id)

        # TASK-0073 Phase A5 + TASK-0091: same-tx audit hook (full before/after snapshot).
        before_for_audit: dict[str, Any] = dict(existing)
        after_for_audit: dict[str, Any] = dict(updated) if updated else {"id": int(product_id)}
        if set_default and default_cleared_product_ids:
            # extra context — builder 의 allowlist 외 보조 메타.
            after_for_audit["_default_cleared_product_ids"] = default_cleared_product_ids
        app._audit_admin_mutation(
            conn,
            request,
            account,
            action="admin.product.update",
            resource_type="product",
            resource_id=str(product_id),
            before=before_for_audit,
            after=after_for_audit,
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.autocommit = True
        except Exception:
            pass
        conn.close()
        return app._json_error(f"product update failed: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
    conn.close()
    return JSONResponse({"ok": True, "product_id": int(product_id)})

@router.delete("/api/admin/products/{product_id}")
def admin_delete_product(product_id: int, request: Request) -> JSONResponse:
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(account, "product.manage"):
        conn.close()
        return app._json_error("제품 관리 권한이 필요합니다.", 403)
    # TASK-0302 (외부리뷰 MAJOR — defense-in-depth): 기본 제품(IsDefault) 삭제는 백엔드에서도 차단한다.
    #   프론트 bulkProductDelete 의 canTargetRow(is_default 제외)는 client-trust 가드뿐이고, bulk DELETE
    #   경로가 이제 실제 서버 호출에 도달하므로(이전엔 _delete 무처리로 no-op) 서버 측 보호가 load-bearing.
    #   미존재 제품은 404(이전엔 WHERE Id=%s no-op 으로 200 오인). 단일 삭제 경로도 동일 가드 적용.
    _gcur = conn.cursor()
    _gcur.execute("SELECT IsDefault FROM WebProducts WHERE Id = %s", (int(product_id),))
    _grow = _gcur.fetchone()
    _gcur.close()
    if _grow is None:
        conn.close()
        return app._json_error("제품을 찾을 수 없습니다.", 404)
    if int(_grow[0] or 0) == 1:
        conn.close()
        return app._json_error("기본 제품은 삭제할 수 없습니다.", 409)
    # TASK-0248: 과거에는 참조 대화가 있으면 삭제를 거부(400)했으나, 이제는 삭제를 허용하고
    # 그 제품을 pinned 한 대화를 차단(blocked)으로 전환한다(이력 열람·공유는 가능, 진행 불가).
    # 아래 COUNT 는 새로 차단될(아직 미차단인 참조) 대화 수 — 응답/감사 메시지에만 사용하며
    # 삭제를 막지 않는다.
    # AR-M5 cutover: AgentCoreConversations MySQL 테이블 DROP → COUNT 를 PG
    # agent_runtime.core_conversations 로 라우팅(미라우팅 시 SELECT 가 500).
    if app._runtime_backend_is_pg():
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT COUNT(*) FROM agent_runtime.core_conversations "
                    "WHERE product_id = %s AND blocked_at IS NULL",
                    (int(product_id),),
                )
                referencing_count = int((pgcur.fetchone() or (0,))[0] or 0)
        finally:
            pg.close()
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM AgentCoreConversations "
            "WHERE product_id = %s AND blocked_at IS NULL",
            (int(product_id),),
        )
        referencing_count = int((cur.fetchone() or (0,))[0] or 0)
        cur.close()
    # TASK-0052 Phase 1B (Codex Claim 2): 명시적 트랜잭션으로 cascade 정합성 보장.
    # 신규: WebPermissions(IsDynamic=1, ProductId=<id>) + 그 권한을 참조하는 WebRolePermissions /
    # WebAccountPermissionOverrides 도 함께 정리. 부분 실패 시 product 도 그대로 유지 (rollback).
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("DELETE FROM WebSystemPrompts WHERE ProductId = %s", (int(product_id),))
        cur.execute("DELETE FROM WebProductDatabases WHERE ProductId = %s", (int(product_id),))
        # 동적 권한 row 의 id 들을 먼저 조회해 두고, 참조 row 들을 cascade 정리.
        cur.execute(
            "SELECT Id FROM WebPermissions WHERE IsDynamic = 1 AND ProductId = %s",
            (int(product_id),),
        )
        dyn_perm_ids = [int(r[0] or 0) for r in (cur.fetchall() or []) if r and r[0]]
        if dyn_perm_ids:
            placeholders = ",".join(["%s"] * len(dyn_perm_ids))
            cur.execute(
                f"DELETE FROM WebRolePermissions WHERE PermissionId IN ({placeholders})",
                tuple(dyn_perm_ids),
            )
            cur.execute(
                f"DELETE FROM WebAccountPermissionOverrides WHERE PermissionId IN ({placeholders})",
                tuple(dyn_perm_ids),
            )
            cur.execute(
                f"DELETE FROM WebPermissions WHERE Id IN ({placeholders})",
                tuple(dyn_perm_ids),
            )
        cur.execute("DELETE FROM WebProducts WHERE Id = %s", (int(product_id),))
        cur.close()
        # TASK-0073 Phase A5 (Eng review E5 cascade lock 순서): audit INSERT 가 같은 tx 안.
        # cascade 순서 (WebSystemPrompts → WebProductDatabases → WebRolePermissions →
        # WebAccountPermissionOverrides → WebPermissions → WebProducts) 끝 → audit INSERT.
        # builder 가 before-state (product_id) 만 사용 — cascade 결과는 conn 상태로 가시.
        app.record_audit_event(
            conn,
            actor=app._build_actor_from_request(request, account, actor_type="account"),
            action="admin.product.delete",
            resource_type="product",
            resource_id=str(product_id),
            change_json={
                "target_product_id": int(product_id),
                "cascade_dyn_permissions": len(dyn_perm_ids),
                "referencing_conversations": int(referencing_count),
            },
            target_account_id=None,
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.autocommit = True
        conn.close()
        return app._json_error(f"제품 삭제 실패: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
    conn.close()
    # TASK-0248: 제품 cascade 삭제가 commit 된 뒤, 그 제품을 pinned 한 대화를 차단으로 전환.
    # 삭제 commit 이후 별도 스토어(PG core_conversations)에 수행 — cross-store 라 단일 tx
    # 불가하므로 순서는 "삭제 먼저, 차단 나중". 차단이 실패해도 제품 권한(product.access.<key>)이
    # 이미 cascade 삭제돼 기존 ask 가드(권한 회수 403)가 fail-closed 로 보강하므로 진행은 막힌다.
    blocked_count = 0
    try:
        blocked_count = app._block_conversations_for_product(
            int(product_id), app._BLOCKED_PRODUCT_DELETED_REASON
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "admin_delete_product: 참조 대화 차단 실패 (product_id=%s) — 제품은 이미 삭제됨. "
            "해당 대화는 권한 회수 가드로 fail-closed 된다.",
            product_id, exc_info=True,
        )
    return JSONResponse({
        "ok": True,
        "product_id": int(product_id),
        "blocked_conversations": int(blocked_count),
    })

@router.put("/api/admin/products/{product_id}/databases")
async def admin_update_product_databases(product_id: int, request: Request) -> JSONResponse:
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return error
    if not app._account_has_permission(account, "product.manage"):
        conn.close()
        return app._json_error("제품 관리 권한이 필요합니다.", 403)
    cur = conn.cursor()
    cur.execute("SELECT Id, DatasourceKey FROM WebProducts WHERE Id = %s", (int(product_id),))
    _prow = cur.fetchone()
    if not _prow:
        cur.close()
        conn.close()
        return app._json_error("product not found", 404)
    # TASK-0228 (1:N): body 에 datasource_key 가 있으면 그 datasource 의 접근DB 만 교체(차원 격리).
    # 없으면 레거시 단일 경로 — 제품의 primary datasource 키를 사용(하위호환).
    _req_dskey = (str(data.get("datasource_key") or "").strip().lower() if isinstance(data, dict) else "")
    # re-gate(4차) MAJOR: 금지 DB 목록을 datasource 엔진별로 적용(MySQL 제품에서 'master' 가 정상 사용자
    # DB 일 수 있고, MSSQL 제품에서 'mysql' 이 정상 DB 일 수 있다 — cross-engine 과차단 방지).
    _ds_engine = "mysql"
    _ds_id = None  # TASK-0277: 이 차원 datasource 의 stable surrogate Id(dual-write anchor)
    _primary_dskey = (str(_prow[1]).strip().lower() if len(_prow) > 1 and _prow[1] else "")
    # TASK-0228: 차원 키 = 요청 datasource_key(있으면) 우선, 없으면 primary. 엔진 판정도 이 키 기준.
    _dskey = _req_dskey or _primary_dskey
    # 1:N 검증: 요청 datasource_key 가 제품에 실제 바인딩돼 있어야 한다(임의 키로 접근DB 주입 차단).
    if _req_dskey:
        try:
            cur.execute(
                "SELECT 1 FROM WebProductDatasources WHERE ProductId=%s AND LOWER(DatasourceKey)=%s LIMIT 1",
                (int(product_id), _req_dskey))
            _bound_ok = bool(cur.fetchone())
        except Exception:
            _bound_ok = (_req_dskey == _primary_dskey)  # join 미이전 폴백: primary 와 일치할 때만
        if not _bound_ok:
            cur.close()
            conn.close()
            return app._json_error(f"datasource '{_req_dskey}' 는 이 제품에 바인딩되지 않았습니다.", 400)
    if _dskey:
        _found = False
        try:
            cur.execute("SELECT Engine, Id FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (_dskey,))
            _er = cur.fetchone()
            if _er and _er[0]:
                _ds_engine = str(_er[0]).strip().lower()
                _found = True
            if _er and len(_er) > 1 and _er[1] is not None:
                _ds_id = int(_er[1])  # TASK-0277 dual-write anchor
        except Exception:
            _found = False
        if not _found:
            # re-gate(5차) MAJOR: WebDatasources 미존재 시 .env 레지스트리(config.DATASOURCES)도 확인 —
            # .env 기반 MSSQL datasource 가 MySQL 로 오판돼 금지목록이 잘못 적용되던 것 차단.
            try:
                from shared import config as _cfg2
                _envds = (getattr(_cfg2, "DATASOURCES", {}) or {}).get(_dskey)
                if _envds and _envds.get("engine"):
                    _ds_engine = str(_envds.get("engine")).strip().lower()
            except Exception:
                pass
    cur.close()
    _forbidden_meta = set(app._DATABASES_AVAILABLE_METADATA) if _ds_engine == "mysql" else set()
    _forbidden_sys = set(app._DATABASES_AVAILABLE_SYSTEM_MSSQL) if _ds_engine == "mssql" else set()
    raw_items = data.get("databases")
    if not isinstance(raw_items, list):
        return app._json_error("databases must be a list", 400)
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for i, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        # re-gate(3차) MAJOR: MSSQL DB 명은 **대소문자·하이픈·공백·선두숫자** 를 보존(Game-Log/2026DB 등
        # 정상 DB). 인젝션 차단을 위해 대괄호·따옴표·세미콜론·백틱·백슬래시·점·제어문자만 거부(브래킷
        # 인용 escape 방지). 비교(금지·dedup)는 소문자로, 저장은 원본 케이스로.
        schema = str(item.get("schema_name") or "").strip()
        if not schema:
            continue
        if len(schema) > 128 or re.search(r"""[\[\]'"`;\\.\x00-\x1f]""", schema):
            return app._json_error(f"invalid schema_name: {schema}", 400)
        slow = schema.lower()
        # re-gate BLOCKER4: 앱 내부 DB(agent_memory) 및 메타데이터 스키마는 allowlist 에 저장 불가
        # (구조화 도구가 allowlist 멤버를 신뢰 → agent_memory.WebAccounts.PasswordHash 유출 경로 차단).
        # 내부 DB(agent_memory)는 엔진 무관 항상 차단.
        if slow in app._DATABASES_AVAILABLE_INTERNAL:
            return app._json_error(f"내부 데이터베이스는 접근 목록에 추가할 수 없습니다: {schema}", 400)
        # 메타데이터/시스템 DB 는 해당 엔진에서만 차단(cross-engine 정상 DB 과차단 방지).
        if slow in _forbidden_meta:
            return app._json_error(f"메타데이터 스키마는 항상 접근 가능하므로 추가할 수 없습니다: {schema}", 400)
        if slow in _forbidden_sys:
            return app._json_error(f"시스템 데이터베이스는 접근 목록에 추가할 수 없습니다: {schema}", 400)
        if slow in seen:
            continue
        seen.add(slow)
        cleaned.append({
            "schema_name": schema,
            "description": str(item.get("description") or "").strip(),
            "sort_order": int(item.get("sort_order") or (i + 1) * 10),
        })
    # before-state 캡처 — 현재 schemas list.
    # TASK-0228 (1:N): datasource_key 차원이 있으면 그 datasource 의 행만 교체(다른 datasource 의
    # 접근DB 는 보존 — 차원 격리). 없으면 레거시 단일 경로(_dskey = primary).
    cur = conn.cursor()
    _has_ds_col = True
    try:
        cur.execute(
            "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s "
            "ORDER BY SortOrder ASC",
            (int(product_id), _dskey),
        )
        before_schemas = [str(r[0]) for r in (cur.fetchall() or [])]
    except Exception:
        # DatasourceKey 컬럼 부재(미이전) → 차원 없는 레거시 조회.
        _has_ds_col = False
        cur.execute(
            "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s ORDER BY SortOrder ASC",
            (int(product_id),),
        )
        before_schemas = [str(r[0]) for r in (cur.fetchall() or [])]
    cur.close()
    cur = conn.cursor()
    if _has_ds_col:
        # TASK-0277: DatasourceId 컬럼 존재 시 dual-write(stable surrogate anchor 동시 기록). 부재(미이전) 시 키만.
        try:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                "AND TABLE_NAME='WebProductDatabases' AND COLUMN_NAME='DatasourceId'"
            )
            _has_dsid_col = int((cur.fetchone() or [0])[0]) > 0
        except Exception:
            _has_dsid_col = False
        # TASK-20260618T044318 (B4): Source 컬럼 존재 시 manual/rule 구분 — 수동 PUT 은 **manual 행만** 교체하고
        #   rule 행(자동 동기화 결과)은 보존한다. manual 로 들어오는 schema 와 충돌하는 rule 행은 삭제
        #   (manual 우선 승격 — 중복 방지). Source 부재(미이전) 면 레거시 전체 교체.
        try:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                "AND TABLE_NAME='WebProductDatabases' AND COLUMN_NAME='Source'"
            )
            _has_source_col = int((cur.fetchone() or [0])[0]) > 0
        except Exception:
            _has_source_col = False
        if _has_source_col:
            cur.execute(
                "DELETE FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s "
                "AND COALESCE(Source,'manual') = 'manual'",
                (int(product_id), _dskey))
            for item in cleaned:
                cur.execute(
                    "DELETE FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s "
                    "AND LOWER(SchemaName) = %s AND COALESCE(Source,'manual') = 'rule'",
                    (int(product_id), _dskey, str(item["schema_name"]).strip().lower()))
        else:
            # 이 datasource 차원의 행만 삭제(다른 datasource 행 보존).
            cur.execute("DELETE FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s",
                        (int(product_id), _dskey))
        for item in cleaned:
            if _has_dsid_col and _has_source_col:
                cur.execute(
                    "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, DatasourceKey, DatasourceId, Source) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 'manual')",
                    (int(product_id), item["schema_name"], item["description"], int(item["sort_order"]), _dskey, _ds_id),
                )
            elif _has_dsid_col:
                cur.execute(
                    "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, DatasourceKey, DatasourceId) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (int(product_id), item["schema_name"], item["description"], int(item["sort_order"]), _dskey, _ds_id),
                )
            elif _has_source_col:
                cur.execute(
                    "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, DatasourceKey, Source) "
                    "VALUES (%s, %s, %s, %s, %s, 'manual')",
                    (int(product_id), item["schema_name"], item["description"], int(item["sort_order"]), _dskey),
                )
            else:
                cur.execute(
                    "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, DatasourceKey) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (int(product_id), item["schema_name"], item["description"], int(item["sort_order"]), _dskey),
                )
    else:
        cur.execute("DELETE FROM WebProductDatabases WHERE ProductId = %s", (int(product_id),))
        for item in cleaned:
            cur.execute(
                "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder) "
                "VALUES (%s, %s, %s, %s)",
                (int(product_id), item["schema_name"], item["description"], int(item["sort_order"])),
            )
    cur.close()
    # TASK-0073 Phase A5: same-tx audit hook (product databases update).
    try:
        app._audit_admin_mutation(
            conn,
            request,
            account,
            action="admin.product.databases.update",
            resource_type="product",
            resource_id=str(product_id),
            before={"id": int(product_id), "schemas": before_schemas},
            after={"id": int(product_id), "schemas": [c["schema_name"] for c in cleaned]},
            request_ctx={"product_id": int(product_id)},
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
    return JSONResponse({"ok": True, "databases": cleaned})

@router.get("/api/admin/products/{product_id}/datasources/{key}/db-rules")
async def admin_list_product_db_rules(product_id: int, key: str, request: Request) -> JSONResponse:
    """(product, datasource) 의 **모든** 규칙 + 규칙별 pending. 읽기 전용 — 조회는 allowlist 를 바꾸지 않는다."""
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    _ = account  # gate 가 권한 검증을 이미 수행(조회는 추가 reconcile 안 함).
    try:
        # TASK-20260619 (CONVENTIONS.md §10.7): 조회(view)는 더 이상 자동 reconcile/GRANT 하지 않는다.
        #   관리 콘솔 편집은 pending → "모두 적용" 으로만 allowlist 를 바꾼다(범위 A). 단순히 규칙
        #   에디터를 여는 것만으로 접근 가능 DB 가 늘어나던 우회 경로를 제거한다. 확정된 규칙의 자동
        #   동기화는 백그라운드 reconcile 루프(_start_db_rule_reconcile_loop)와 규칙 확정 시
        #   on-write reconcile 가 계속 담당하므로 "잦은 DB 변경 자동 반영" 기능 자체는 보존된다.
        rules = app._get_product_db_rules(conn, int(product_id), dsk)
        pending = app._list_db_rule_pending(conn, int(product_id), dsk)
        # pending 을 rule_id 별로 그룹(미귀속=None 키 0).
        pend_by_rule: dict[int, list] = {}
        for p in pending:
            pend_by_rule.setdefault(int(p.get("rule_id") or 0), []).append(p)
        out = []
        for r in rules:
            rp = app._rule_to_public(r)
            rp["pending"] = pend_by_rule.get(int(r.get("id") or 0), [])
            out.append(rp)
        return JSONResponse({"ok": True, "rules": out, "pending": pending,
                             "orphan_pending": pend_by_rule.get(0, [])})
    finally:
        conn.close()

@router.post("/api/admin/products/{product_id}/datasources/{key}/db-rules")
async def admin_create_product_db_rule(product_id: int, key: str, request: Request) -> JSONResponse:
    """신규 규칙 1건 생성(다중 규칙) + 즉시 reconcile. product.manage."""
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    try:
        include_pattern = str((data or {}).get("include_pattern") or "").strip()
        exclude_pattern = str((data or {}).get("exclude_pattern") or "").strip()
        try:
            cap = int((data or {}).get("cap") or 3)
        except Exception:
            cap = 3
        cap = max(1, min(cap, 100))
        ok, perr = app._validate_db_rule_pattern(include_pattern)
        if not ok:
            return app._json_error(f"include 패턴 오류: {perr}", 400)
        if exclude_pattern:
            ok2, perr2 = app._validate_db_rule_pattern(exclude_pattern)
            if not ok2:
                return app._json_error(f"exclude 패턴 오류: {perr2}", 400)
        cur = conn.cursor()
        # SortOrder = 현재 max+10(말미 추가). 미이전 graceful.
        try:
            cur.execute("SELECT COALESCE(MAX(SortOrder),0) FROM WebProductDatasourceDbRules "
                        "WHERE ProductId=%s AND LOWER(DatasourceKey)=%s", (int(product_id), dsk))
            next_sort = int((cur.fetchone() or [0])[0] or 0) + 10
        except Exception:
            next_sort = 100
        try:
            cur.execute(
                "INSERT INTO WebProductDatasourceDbRules "
                "(ProductId, DatasourceKey, IncludePattern, ExcludePattern, Cap, IsEnabled, SortOrder, CreatedByAccountId) "
                "VALUES (%s,%s,%s,%s,%s,1,%s,%s)",
                (int(product_id), dsk, include_pattern, (exclude_pattern or None), cap, next_sort, int(account.get("id") or 0)))
        except Exception:
            # SortOrder 컬럼 부재(마이그레이션 전) 폴백.
            cur.execute(
                "INSERT INTO WebProductDatasourceDbRules "
                "(ProductId, DatasourceKey, IncludePattern, ExcludePattern, Cap, IsEnabled, CreatedByAccountId) "
                "VALUES (%s,%s,%s,%s,%s,1,%s)",
                (int(product_id), dsk, include_pattern, (exclude_pattern or None), cap, int(account.get("id") or 0)))
        new_rule_id = int(cur.lastrowid or 0)
        cur.close()
        try:
            app._audit_admin_mutation(
                conn, request, account, action="admin.product.db_rule.set",
                resource_type="product", resource_id=str(product_id),
                before=None,
                after={"datasource_key": dsk, "rule_id": new_rule_id, "include": include_pattern, "exclude": exclude_pattern, "cap": cap},
                request_ctx={"product_id": int(product_id), "datasource_key": dsk})
            conn.commit()
        except Exception as audit_exc:
            conn.rollback()
            return app._json_error(f"audit write failed: {audit_exc}", 500)
        rule = app._get_db_rule_by_id(conn, new_rule_id)
        # ds-conn-bg-decouple: reconcile 는 live DB 열거(connect) 포함 → 이벤트 루프 밖(to_thread)에서.
        recon = (await asyncio.to_thread(
            app._reconcile_one_db_rule, conn, rule, actor_account=account, can_manage=True, trigger="rule-save")) if rule else {}
        return JSONResponse({"ok": True, "rule_id": new_rule_id, "reconcile": recon})
    finally:
        conn.close()

@router.put("/api/admin/products/{product_id}/datasources/{key}/db-rules/{rule_id}")
async def admin_update_product_db_rule(product_id: int, key: str, rule_id: int, request: Request) -> JSONResponse:
    """기존 규칙 1건 수정(Id 기준) + 즉시 reconcile. product.manage."""
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    try:
        rule = app._get_db_rule_by_id(conn, int(rule_id))
        if not rule or int(rule.get("product_id") or 0) != int(product_id) or str(rule.get("datasource_key")) != dsk:
            return app._json_error("rule not found", 404)
        include_pattern = str((data or {}).get("include_pattern") or "").strip()
        exclude_pattern = str((data or {}).get("exclude_pattern") or "").strip()
        try:
            cap = int((data or {}).get("cap") or 3)
        except Exception:
            cap = 3
        cap = max(1, min(cap, 100))
        ok, perr = app._validate_db_rule_pattern(include_pattern)
        if not ok:
            return app._json_error(f"include 패턴 오류: {perr}", 400)
        if exclude_pattern:
            ok2, perr2 = app._validate_db_rule_pattern(exclude_pattern)
            if not ok2:
                return app._json_error(f"exclude 패턴 오류: {perr2}", 400)
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebProductDatasourceDbRules SET IncludePattern=%s, ExcludePattern=%s, Cap=%s, IsEnabled=1 WHERE Id=%s",
            (include_pattern, (exclude_pattern or None), cap, int(rule_id)))
        cur.close()
        try:
            app._audit_admin_mutation(
                conn, request, account, action="admin.product.db_rule.set",
                resource_type="product", resource_id=str(product_id),
                before={"datasource_key": dsk, "rule_id": int(rule_id),
                        "include": rule.get("include_pattern"), "exclude": rule.get("exclude_pattern"), "cap": rule.get("cap")},
                after={"datasource_key": dsk, "rule_id": int(rule_id), "include": include_pattern, "exclude": exclude_pattern, "cap": cap},
                request_ctx={"product_id": int(product_id), "datasource_key": dsk})
            conn.commit()
        except Exception as audit_exc:
            conn.rollback()
            return app._json_error(f"audit write failed: {audit_exc}", 500)
        fresh = app._get_db_rule_by_id(conn, int(rule_id))
        # ds-conn-bg-decouple: reconcile 는 live DB 열거(connect) 포함 → 이벤트 루프 밖(to_thread)에서.
        recon = (await asyncio.to_thread(
            app._reconcile_one_db_rule, conn, fresh, actor_account=account, can_manage=True, trigger="rule-save")) if fresh else {}
        return JSONResponse({"ok": True, "reconcile": recon})
    finally:
        conn.close()

@router.delete("/api/admin/products/{product_id}/datasources/{key}/db-rules/{rule_id}")
async def admin_delete_product_db_rule(product_id: int, key: str, rule_id: int, request: Request) -> JSONResponse:
    """규칙 1건 삭제(Id 기준). strip=1 이면 그 규칙(RuleId)이 추가한 DB 행만 제거(다른 규칙·manual 보존)."""
    strip_rows = str(request.query_params.get("strip", "")).strip().lower() in ("1", "true", "yes")
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    try:
        rule = app._get_db_rule_by_id(conn, int(rule_id))
        if not rule or int(rule.get("product_id") or 0) != int(product_id) or str(rule.get("datasource_key")) != dsk:
            return app._json_error("rule not found", 404)
        cur = conn.cursor()
        cur.execute("DELETE FROM WebProductDatasourceDbRules WHERE Id=%s", (int(rule_id),))
        cur.execute("DELETE FROM WebProductDatabasePending WHERE ProductId=%s AND LOWER(DatasourceKey)=%s AND RuleId=%s",
                    (int(product_id), dsk, int(rule_id)))
        if strip_rows:
            # 이 규칙(RuleId)이 추가한 행만 제거(다른 규칙·manual 보존).
            cur.execute(
                "DELETE FROM WebProductDatabases WHERE ProductId=%s AND LOWER(DatasourceKey)=%s "
                "AND COALESCE(Source,'manual')='rule' AND RuleId=%s", (int(product_id), dsk, int(rule_id)))
        cur.close()
        try:
            app._audit_admin_mutation(
                conn, request, account, action="admin.product.db_rule.delete",
                resource_type="product", resource_id=str(product_id),
                before={"datasource_key": dsk, "rule_id": int(rule_id)},
                after={"stripped_rule_rows": strip_rows},
                request_ctx={"product_id": int(product_id), "datasource_key": dsk})
            conn.commit()
        except Exception as audit_exc:
            conn.rollback()
            return app._json_error(f"audit write failed: {audit_exc}", 500)
        return JSONResponse({"ok": True})
    finally:
        conn.close()

@router.post("/api/admin/products/{product_id}/datasources/{key}/db-rules/preview")
async def admin_preview_product_db_rule(product_id: int, key: str, request: Request) -> JSONResponse:
    """dry-run: 라이브 DB 에 패턴을 적용해 일치/신규 목록을 반환(쓰기 없음). UI 라이브 카운트."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    try:
        include_pattern = str((data or {}).get("include_pattern") or "").strip()
        exclude_pattern = str((data or {}).get("exclude_pattern") or "").strip()
        ok, perr = app._validate_db_rule_pattern(include_pattern)
        if not ok:
            return JSONResponse({"ok": False, "error": perr, "matched": [], "new": []})
        try:
            from shared import datasources as _dsr
            from shared import db as _db
            ds = _dsr.resolve(conn, dsk)
            if not ds:
                return JSONResponse({"ok": False, "error": "datasource 해석 실패", "matched": [], "new": []})
            okssrf, _r, _pin = app._ssrf_check_host(ds.get("host"))
            if not okssrf:
                return JSONResponse({"ok": False, "error": "SSRF 차단", "matched": [], "new": []})
            # ds-conn-bg-decouple: 명시적 dry-run preview 의 live connect 도 이벤트 루프 밖(to_thread)에서.
            classified = await asyncio.to_thread(
                _db.list_server_databases_classified, {**ds, "host": _pin})
        except Exception:
            return JSONResponse({"ok": False, "error": "DB 목록 조회 실패", "matched": [], "new": []})
        engine = str(ds.get("engine") or "mysql").strip().lower()
        user_names = [d["name"] for d in (classified or [])
                      if isinstance(d, dict) and not d.get("system") and d.get("name")]
        matched = app._match_db_rule(user_names, include_pattern, (exclude_pattern or None),
                                 engine, app._db_rule_excluded_lower(engine))
        cur = conn.cursor()
        cur.execute("SELECT LOWER(SchemaName) FROM WebProductDatabases WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                    (int(product_id), dsk))
        existing = {str(r[0]).strip().lower() for r in (cur.fetchall() or [])}
        cur.close()
        new = [m for m in matched if str(m).strip().lower() not in existing]
        return JSONResponse({"ok": True, "matched": matched, "new": new,
                             "matched_count": len(matched), "new_count": len(new)})
    finally:
        conn.close()

@router.post("/api/admin/products/{product_id}/datasources/{key}/db-rules/{rule_id}/approve-pending")
async def admin_approve_product_db_rule_pending(product_id: int, key: str, rule_id: int, request: Request) -> JSONResponse:
    """해당 규칙(rule_id)의 pending(보류) 일치 DB 를 allowlist 에 승격(Source='rule'). 1클릭 승인(B1). product.manage."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    try:
        rule = app._get_db_rule_by_id(conn, int(rule_id))
        if not rule or int(rule.get("product_id") or 0) != int(product_id) or str(rule.get("datasource_key")) != dsk:
            return app._json_error("rule not found", 404)
        rule_id = int(rule_id)
        want = data.get("schemas") if isinstance(data, dict) else None
        # 이 규칙(rule_id) 에 귀속된 pending 만 대상.
        pending = [p for p in app._list_db_rule_pending(conn, int(product_id), dsk)
                   if int(p.get("rule_id") or 0) == rule_id]
        pend_names = {p["schema_name"] for p in pending}
        if isinstance(want, list) and want:
            targets = [s for s in want if str(s) in pend_names]
        else:
            targets = [p["schema_name"] for p in pending]
        if not targets:
            return JSONResponse({"ok": True, "approved": []})
        engine = "mysql"
        try:
            from shared import datasources as _dsr
            _ds = _dsr.resolve(conn, dsk)
            engine = str((_ds or {}).get("engine") or "mysql").strip().lower()
        except Exception:
            pass
        excluded = app._db_rule_excluded_lower(engine)
        cur = conn.cursor()
        cur.execute("SELECT LOWER(SchemaName), COALESCE(SortOrder,0) FROM WebProductDatabases "
                    "WHERE ProductId=%s AND LOWER(DatasourceKey)=%s", (int(product_id), dsk))
        rows = cur.fetchall() or []
        existing = {str(r[0]).strip().lower() for r in rows}
        max_sort = max([int(r[1] or 0) for r in rows], default=0)
        approved: list[str] = []
        for name in targets:
            low = str(name).strip().lower()
            if not low or low in existing or low in excluded:
                continue
            if len(str(name)) > app._DB_RULE_NAME_MAX or app._DB_RULE_NAME_INJECT_RE.search(str(name)):
                continue
            max_sort += 10
            cur.execute(
                "INSERT IGNORE INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, DatasourceKey, Source, RuleId) "
                "VALUES (%s,%s,%s,%s,%s,'rule',%s)",
                (int(product_id), str(name), "", max_sort, dsk, rule_id))
            cur.execute("DELETE FROM WebProductDatabasePending WHERE ProductId=%s AND LOWER(DatasourceKey)=%s AND SchemaName=%s",
                        (int(product_id), dsk, str(name)))
            approved.append(str(name))
        cur.close()
        try:
            app.record_audit_event(
                conn, actor=app._db_rule_audit_actor(account), action="admin.product.db_rule.approve",
                resource_type="product", resource_id=str(product_id),
                change_json={"datasource_key": dsk, "rule_id": rule_id, "names": approved})
            conn.commit()
        except Exception as audit_exc:
            conn.rollback()
            return app._json_error(f"audit write failed: {audit_exc}", 500)
        return JSONResponse({"ok": True, "approved": approved})
    finally:
        conn.close()

@router.post("/api/admin/products/{product_id}/prompt/generate")
async def admin_generate_product_prompt(product_id: int, request: Request) -> JSONResponse:
    """비스트리밍 자동작성(기존 호환 경로). 실시간 진행률이 필요하면 GET .../stream 사용."""
    error, ctx = await app._collect_product_prompt_context(product_id, request)
    if error:
        return error
    return await app._prompt_generate_json_response(
        ctx, log_label="admin_generate_product_prompt", log_ctx=f"product_id={product_id}"
    )

@router.get("/api/admin/products/{product_id}/prompt/generate/stream")
async def admin_generate_product_prompt_stream(product_id: int, request: Request):
    """TASK-0237: 제품 프롬프트 자동작성 LLM 토큰 스트리밍(SSE). textarea 에 본문이 실시간으로 차오른다.

    인증·수집은 generator 진입 **전**에 완료 — 실패 시 JSON 403/404/503 으로 나가고 SSE 미진입.
    """
    error, ctx = await app._collect_product_prompt_context(product_id, request)
    if error:
        return error
    return app._prompt_generate_stream_response(
        ctx, log_label="admin_generate_product_prompt_stream", log_ctx=f"product_id={product_id}"
    )
