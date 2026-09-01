"""feature-0012 P5b Final — admin/metadata 도메인 APIRouter (메타데이터 거버넌스: 용어사전/ENUM/테이블·컬럼 설명/샘플/그래프/부트스트랩/AI 자동완성).

DI 전환 33 핸들러(require_permission RP: kb.ingest.manual / kb.glossary.curate / kb.sample.curate)
+ 이연 1(admin_metadata_suggest — 동적 perm + pre-auth 404 gate, inline auth 유지). uniform
`import app`+`app.X` 동적참조(_metadata_* 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import logging
import asyncio
import json
import time

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

import app
from routers import _console_jobs

INCLUDE_ORDER = 120  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()

# 구조 묶음 단위 ENUM 검토 큐 '전체 승인/일부 해제 후 등록'(bulk-promote) 1회 상한. 한 컬럼 묶음의
# 코드 수는 통상 수십 이하지만, 다중 묶음 동시 등록/오용 방어로 요청당 건수를 cap 한다.
_ENUM_BULK_PROMOTE_MAX = 200


# ITEM-10 routers-p2: _metadata_* 헬퍼 20종 app.py 에서 이동(도메인 소유 정상화 — 판정표 §4).
# app 전역은 app.X 동적 참조(패치-단일점). _metadata_llm_complete 호출부는 app.X 유지(테스트 setattr 패치 관통).
def _metadata_resolve_account(request: Request):
    """RBAC(kb.ingest.manual) 게이트. (account, None) 또는 (None, JSONResponse[401/403/500])."""
    try:
        conn = app._connect_memory()
    except Exception:
        return None, app._json_error("db connection failed", 500)
    try:
        account, error = app._require_permission(request, conn, "kb.ingest.manual")
        if error:
            return None, error
        return account, None
    finally:
        conn.close()

def _product_scope_catalog(conn=None) -> list[dict]:
    """활성 제품 → 메타데이터 스코프 카탈로그 (metadata-product-scope 의 단일 해소점).

    관리 콘솔 > 지식베이스 > 메타데이터의 스코프 축은 **제품**이다. 사용자·메타데이터 관리자는
    데이터소스를 인식하지 않으므로 콘솔 선택기·scope 검증·부트스트랩이 모두 본 카탈로그를 원천으로 쓴다.

    반환 항목:
      - `scope_key`   : `product.<ProductKey>` — KB row 의 scope_key (shared.config.product_scope_key)
      - `product_id` / `product_key` / `name` / `sort_order`
      - `datasources` : 제품에 바인딩된 datasource [{key, is_primary}] — 표시용이 아니라 내부 해소용
      - `databases`   : 제품의 접근DB [{schema, datasource_key}] (`WebProductDatabases` = 제품별 접근DB SSOT).
                        부트스트랩 골격 대상 = 이 목록 — 서버 전체 스키마를 나열하지 않아 제품 경계 밖
                        DB 가 콘솔에 새지 않는다(종전 datasource 축의 부작용).

    조회 실패 시 [] (호출측이 'common' 만 허용하는 보수적 폴백으로 처리).
    """
    owned = False
    if conn is None:
        try:
            conn = app._connect_memory()
            owned = True
        except Exception:
            return []
    try:
        try:
            products = app._list_products(conn) or []
        except Exception:
            return []
        # 접근DB 는 한 번에 읽어 제품별로 접는다(제품 수만큼 쿼리 반복 방지).
        # `databases_ok=False`(읽기 실패)는 "접근DB 없음"과 **구별**해야 한다 — 동일시하면 경계
        # 강제가 transient 오류만으로 무력화되고(=접근DB 미선언 제품 취급) 서버 전체 DB 로
        # 폴백한다(codex review P1). 소비처(_scope_datasource_for_schema·부트스트랩)는 이 플래그가
        # False 면 fail-closed 로 거부한다.
        db_rows: dict = {}
        db_ok = True
        # DatasourceKey 컬럼 미이전(레거시) 스키마 폴백 — `_list_product_databases` 와 동일 계약.
        # 폴백 없이 바로 db_ok=False 로 떨어뜨리면 레거시 배치에서 전 제품 부트스트랩이 503 이 된다
        # (codex review P1). 두 쿼리가 모두 실패할 때만 '카탈로그 미가용'으로 판정한다.
        for _sql, _has_dsk in (
            ("SELECT ProductId, DatasourceKey, SchemaName FROM WebProductDatabases "
             "ORDER BY ProductId, SortOrder, SchemaName", True),
            ("SELECT ProductId, SchemaName FROM WebProductDatabases "
             "ORDER BY ProductId, SortOrder, SchemaName", False),
        ):
            db_rows = {}
            try:
                cur = conn.cursor()
                try:
                    cur.execute(_sql)
                    for row in (cur.fetchall() or []):
                        if isinstance(row, dict):
                            pid = row.get("ProductId")
                            dsk = row.get("DatasourceKey") if _has_dsk else ""
                            sch = row.get("SchemaName")
                        elif _has_dsk:
                            pid, dsk, sch = row[0], row[1], row[2]
                        else:
                            pid, dsk, sch = row[0], "", row[1]
                        sch = str(sch or "").strip()
                        if not sch:
                            continue
                        db_rows.setdefault(int(pid or 0), []).append(
                            {"schema": sch, "datasource_key": str(dsk or "").strip().lower()})
                finally:
                    cur.close()
                db_ok = True
                break
            except Exception:
                db_rows = {}
                db_ok = False
        if not db_ok:
            logging.getLogger(__name__).warning(
                "WebProductDatabases 조회 실패(레거시 폴백 포함) — 접근DB 경계 fail-closed 로 degrade",
                exc_info=True)
        out: list = []
        for p in products:
            pid = int(p.get("id") or 0)
            pkey = str(p.get("product_key") or "").strip()
            sk = _product_scope_key(pkey)
            if pid <= 0 or not sk:
                continue
            _sort = p.get("sort_order")
            out.append({
                "scope_key": sk,
                "product_id": pid,
                "product_key": pkey,
                "name": p.get("name") or pkey,
                "sort_order": int(_sort) if isinstance(_sort, (int, float)) else 100,
                # `_list_product_datasources` 가 이미 레거시 단일 바인딩(WebProducts.DatasourceKey)
                # 폴백을 수행하지만, 카탈로그가 그 불변식을 **자기 안에서** 보장하도록 마지막 폴백을
                # 둔다 — 여기서 비면 부트스트랩이 datasource 를 못 잡아 정상 제품이 막힌다.
                "datasources": _catalog_datasources(p),
                "databases": db_rows.get(pid, []),
                "databases_ok": db_ok,
            })
        out.sort(key=lambda e: (e["sort_order"], e["name"]))
        return out
    finally:
        if owned and conn is not None:
            try:
                conn.close()
            except Exception:
                pass

def _catalog_datasources(product) -> list[dict]:
    """제품 dict → [{key, is_primary}]. 1:N 바인딩 우선, 비면 레거시 단일 바인딩으로 폴백."""
    out = [{"key": str(d.get("datasource_key") or "").strip().lower(),
            "is_primary": bool(d.get("is_primary"))}
           for d in ((product or {}).get("datasources") or []) if d.get("datasource_key")]
    if out:
        return out
    legacy = str((product or {}).get("datasource_key") or "").strip().lower()
    return [{"key": legacy, "is_primary": True}] if legacy else []

def _product_scope_key(product_key):
    """제품 키 → 메타데이터 scope_key. shared.config.product_scope_key 얇은 래퍼(import 지역화)."""
    try:
        from shared import config as _cfg
        return _cfg.product_scope_key(product_key)
    except Exception:
        raw = str(product_key or "").strip().lower()
        return ("product." + raw) if raw else None

def _resolve_scope_product(scope_key, conn=None):
    """제품 스코프 키(`product.<key>`) → 카탈로그 엔트리. 미매칭/'common' → None."""
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == "common":
        return None
    for entry in _product_scope_catalog(conn):
        if entry["scope_key"] == sk:
            return entry
    return None

def _scope_database_units(scope_key, conn=None) -> list[dict]:
    """제품 스코프 → 부트스트랩/골격 대상 단위 목록 [{schema, datasource_key}].

    제품의 접근DB(`WebProductDatabases`)가 곧 그 제품에서 메타데이터를 기술할 수 있는 범위다.
    같은 schema 명이 제품의 두 datasource 에 걸치면(라이브: FH_QA 의 `FHWeb` 이 mssql-qa-idc·
    mssql-web-qa 양쪽) 첫 항목만 남긴다 — 설명의 정체는 (제품, schema, table) 이라 한 건이면 족하다.
    접근DB 가 한 건도 선언되지 않은 제품은 [] (호출측이 라이브 introspection 폴백을 결정).
    """
    entry = _resolve_scope_product(scope_key, conn)
    if not entry or not entry.get("databases_ok", True):
        return []   # 카탈로그 미가용 → 골격 대상 없음(fail-closed). 폴백 introspection 도 막힌다.
    seen: set = set()
    out: list[dict] = []
    for d in entry.get("databases") or []:
        sch = str(d.get("schema") or "").strip()
        if not sch or sch.lower() in seen:
            continue
        seen.add(sch.lower())
        out.append({"schema": sch, "datasource_key": d.get("datasource_key") or ""})
    return out

def _scope_datasource_for_schema(scope_key, schema_name, conn=None) -> str:
    """(제품 스코프, 접근DB명) → datasource 라벨. 해소 불가 시 "" (호출측이 ungrounded/404 처리).

    콘솔에서 데이터소스를 걷어냈으므로, introspection(골격·AI grounding)이 어느 물리 연결을 쓸지는
    서버가 제품 바인딩에서 해소한다.

    **제품 경계 강제 (codex review P1)**: 제품이 접근DB(`WebProductDatabases`)를 선언했다면 그
    목록이 곧 그 제품에서 기술 가능한 범위다 — 목록에 없는 schema 는 primary datasource 로
    폴백하지 않고 "" 를 반환한다. 폴백하면 요청자가 임의 schema 를 실어 그 제품 경계 밖 DB 를
    introspect·저장할 수 있다(공유 datasource 에서 특히 — 남의 제품 DB 노출).
    접근DB 미선언 제품만 primary(없으면 첫) datasource 로 폴백한다(라이브 introspection 경로).
    """
    entry = _resolve_scope_product(scope_key, conn)
    if not entry:
        return ""
    if not entry.get("databases_ok", True):
        return ""   # 접근DB 카탈로그 미가용 → 경계 판정 불가 → 거부(fail-closed).
    declared = entry.get("databases") or []
    sch = str(schema_name or "").strip().lower()
    if declared:
        # 접근DB 선언 제품 — allowlist 매칭만 허용(비매칭 schema 는 거부).
        if not sch:
            # schema 미지정(스키마 목록 조회용 폴백 해소)은 primary 로 허용.
            return _scope_primary_datasource(entry)
        for d in declared:
            if str(d.get("schema") or "").strip().lower() != sch:
                continue
            # 경계는 **schema 멤버십**이 정한다. DatasourceKey 가 빈 레거시 행
            # (`_list_product_databases` 의 컬럼-부재 폴백 산출)은 제품의 primary 로 해소한다 —
            # 여기서 거부하면 목록엔 뜨는데 골격·grounding 만 404/ungrounded 로 죽는다
            # (codex review P1). allowlist 밖 schema 는 아래 return "" 로 여전히 거부된다.
            return str(d.get("datasource_key") or "") or _scope_primary_datasource(entry)
        return ""
    return _scope_primary_datasource(entry)

def _scope_primary_datasource(entry) -> str:
    """카탈로그 엔트리의 primary(없으면 첫) datasource 라벨. 없으면 ""."""
    for d in (entry or {}).get("datasources") or []:
        if d.get("is_primary") and d.get("key"):
            return str(d["key"])
    for d in (entry or {}).get("datasources") or []:
        if d.get("key"):
            return str(d["key"])
    return ""

def _metadata_valid_scope_keys() -> set[str]:
    """허용 scope_key 집합 — **활성 제품 스코프** ∪ {'common'} (metadata-product-scope).

    종전엔 등록된 datasource 의 read-축 해소값(scope_key 필드 or 라벨)이 허용 집합이었다. 그런데
    사용자·메타데이터 관리자가 인식하는 작업 범위는 제품이고, 라이브에서 축이 양방향으로 어긋나
    있었다 — 1제품↔N데이터소스(KR_LIVE·KR_QA 각 7개)에서는 등록분이 그 중 1개 DS 질의에서만
    주입되고, 1데이터소스↔N제품(mssql-qa-idc 를 5개 제품이 공유)에서는 타 제품 메타데이터가
    혼입됐다. → write/read 축을 모두 제품(`product.<ProductKey>`)으로 통일한다.
    'common' 은 항상 허용(공용 사전 — 전 제품 적용). 조회 실패 시 'common' 만 허용(보수적).
    """
    keys = {"common"}
    try:
        for entry in _product_scope_catalog():
            keys.add(entry["scope_key"])
    except Exception:
        pass
    return keys

def _metadata_check_scope(scope_key: str):
    """scope_key 검증 → (normalized, None) 또는 (None, JSONResponse[400]). 빈값/미허용 거부."""
    sk = str(scope_key or "").strip().lower()
    if not sk:
        return None, app._json_error("scope_key 는 필수입니다.", 400)
    if len(sk) > app._METADATA_FIELD_CAPS["scope_key"]:
        return None, app._json_error("scope_key 가 너무 깁니다.", 400)
    allowed = _metadata_valid_scope_keys()
    if sk not in allowed:
        return None, app._json_error("허용되지 않은 scope_key 입니다 (등록된 제품 또는 'common' 공용).", 400)
    return sk, None

def _metadata_valid_role_keys() -> set[str]:
    """허용 role_key 집합 — 등록된 WebRoles.RoleKey ∪ {'*'(공용)}. 조회 실패 시 {'*'}만(보수적).

    용어사전 역할 차원(0021): role_key 는 WebRoles.RoleKey(admin/operator/sales/…) 또는 '*'(공용).
    역할별 비중복 namespace 를 위해 write 시 검증한다(임의 문자열 저장 방지).
    """
    keys = {app._GLOSSARY_COMMON_ROLE}
    conn = None
    try:
        conn = app._connect_memory()
        cur = conn.cursor()
        try:
            cur.execute("SELECT RoleKey FROM WebRoles")
            for row in (cur.fetchall() or []):
                rk = str((row[0] if not isinstance(row, dict) else row.get("RoleKey")) or "").strip().lower()
                if rk:
                    keys.add(rk)
        finally:
            cur.close()
    except Exception:
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return keys

def _metadata_check_role_key(role_key, *, default=app._GLOSSARY_COMMON_ROLE):
    """role_key 검증 → (normalized, None) 또는 (None, JSONResponse[400]). 빈값 → default('*')."""
    rk = str(role_key or "").strip().lower()
    if not rk:
        rk = default
    if len(rk) > app._METADATA_FIELD_CAPS["role_key"]:
        return None, app._json_error("role_key 가 너무 깁니다.", 400)
    if rk not in _metadata_valid_role_keys():
        return None, app._json_error("허용되지 않은 role_key 입니다 (등록된 역할 또는 '*' 공용).", 400)
    return rk, None

def _metadata_check_term_tier(value, *, default=None):
    """term_tier 검증 → (normalized|None, None) 또는 (None, JSONResponse[400]).

    빈값이면 `default` 를 돌려준다. `None` 이 기본인 이유: 수정(PUT)에서 「본문에 없으면 기존
    유지」를 표현해야 하는데, 여기서 임의로 'product' 로 접으면 **전역으로 표시해 둔 용어를
    수정만 해도 제품으로 되돌린다**(사용자가 고치지 않은 필드를 조용히 바꾸는 형태).
    """
    raw = str(value or "").strip().lower()
    if not raw:
        return default, None
    from modules import kb_glossary as _kg
    if raw not in _kg.TERM_TIERS:
        return None, app._json_error(
            "허용되지 않은 term_tier 입니다 (product | org | general).", 400)
    return raw, None

def _metadata_str_field(data: dict, key: str, *, required: bool = True):
    """문자열 필드 추출+trim+cap 검증 → (value, None) 또는 (None, JSONResponse[400])."""
    val = str((data or {}).get(key) or "").strip()
    if required and not val:
        return None, app._json_error(f"{key} 는 필수입니다.", 400)
    cap = app._METADATA_FIELD_CAPS.get(key)
    if cap is not None and len(val) > cap:
        return None, app._json_error(f"{key} 가 너무 깁니다 (최대 {cap}자).", 400)
    return val, None

async def _metadata_read_json(request: Request) -> dict:
    try:
        body_raw = await request.body()
        data = (await request.json()) if body_raw else {}
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}

def _metadata_audit(request, account, *, action, resource_id, change_json):
    """audit(memory conn, 별도) — CRUD 는 PG, audit 은 MySQL(cross-DB 분리). best-effort."""
    try:
        mconn = app._connect_memory()
        try:
            app.record_audit_event(
                mconn,
                actor=app._build_actor_from_request(request, account, actor_type="account"),
                action=action,
                resource_type="kb_metadata",
                resource_id=(str(resource_id) if resource_id is not None else None),
                change_json=change_json,
            )
            mconn.commit()
        finally:
            mconn.close()
    except Exception:
        logging.getLogger(__name__).warning("metadata audit 실패 action=%s id=%s", action, resource_id, exc_info=True)

def _metadata_iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v is not None else None)

def _metadata_enum_fields(data: dict):
    """ENUM 공통 필드 추출/검증 → (dict, None) 또는 (None, JSONResponse[400]).

    schema_name 은 선택(빈 문자열 허용 — 단일 스키마 DB), 나머지는 필수.
    """
    table_name, e = _metadata_str_field(data, "table_name")
    if e:
        return None, e
    column_name, e = _metadata_str_field(data, "column_name")
    if e:
        return None, e
    code, e = _metadata_str_field(data, "code")
    if e:
        return None, e
    label, e = _metadata_str_field(data, "label")
    if e:
        return None, e
    schema_name, e = _metadata_str_field(data, "schema_name", required=False)
    if e:
        return None, e
    return {"table_name": table_name, "column_name": column_name, "code": code,
            "label": label, "schema_name": schema_name}, None

def _metadata_resolve_account_perm(request: Request, perm: str):
    """서브뷰별 RBAC 게이트 — (account, None) 또는 (None, JSONResponse[401/403/500]).
    _metadata_resolve_account(kb.ingest.manual 고정)의 perm 가변 버전(samples=kb.sample.curate)."""
    try:
        conn = app._connect_memory()
    except Exception:
        return None, app._json_error("db connection failed", 500)
    try:
        account, error = app._require_permission(request, conn, perm)
        if error:
            return None, error
        return account, None
    finally:
        conn.close()

def _metadata_qualname(schema_name, table_name) -> str:
    return ".".join([p for p in [str(schema_name or "").strip(), str(table_name or "").strip()] if p])

def _metadata_introspect_table(datasource_key: str, schema_name: str, table_name: str):
    """tables/columns 자동완성 grounding — 대상 테이블의 실제 컬럼 목록을 best-effort 조회.

    부트스트랩 introspection 경로 재사용(RO 유저·dialect-aware·schema allowlist). datasource 미지정
    /'common'/schema 미지정/조회 실패 시 None(=ungrounded — 일반 설명으로 진행). 식별자는
    _safe_ident + load_known_schemas 멤버십으로만 통과(부트스트랩 SQLi 방어와 동일).
    """
    key = str(datasource_key or "").strip().lower()
    schema_name = str(schema_name or "").strip()
    table_name = str(table_name or "").strip()
    if not key or key == "common" or not table_name or not schema_name:
        return None
    ds, scope_key, derr = app._bootstrap_resolve_datasource(key)
    if derr or not ds:
        return None
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    from modules.tools import _safe_ident as _safe_ident_fn
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        safe_table = _safe_ident_fn(table_name)
        cols: list = []
        if engine == "mssql":
            # metadata-table-desc-fix: MSSQL 은 schema_name 이 **database**(부트스트랩 저장 규약과 동일).
            # 시스템 DB 제외 allowlist 로 검증 → 해당 DB 로 연결 → 비시스템 SQL 스키마에서 테이블 컬럼 탐색.
            dialect0 = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect0.system_databases()}
            # §58(적대 리뷰 MAJOR): 저장 라벨이 lower 계약(normalize_db_label)으로 바뀌었으므로
            #   allowlist 를 lower→원본 매핑으로 case-insensitive 매치하고 **연결은 원본 케이스**로
            #   한다(kb_metadata 의 LOWER 매칭 계약과 동형). 케이스-정확 set 이면 lower 라벨의
            #   membership 이 항상 실패해 grounding 이 무음 파괴된다(CS collation 서버 안전 겸비).
            db_map = {str(n).strip().lower(): str(n) for n in (_db.list_server_databases(ds) or [])
                      if str(n).strip().lower() not in sys_db}
            safe_db = _safe_ident_fn(schema_name)
            real_db = db_map.get(str(safe_db).strip().lower())
            if not real_db:
                return None
            conn = _db.connect(datasource=ds, database=real_db, autocommit=True)
            dialect = _dialects.active()
            sys_schema = {str(n).strip().lower() for n in dialect.system_schemas()}
            real_schemas = [s for s in (_schema.load_known_schemas(conn) or [])
                            if str(s).strip().lower() not in sys_schema]
            for sql_schema in real_schemas:
                ss = _safe_ident_fn(sql_schema)
                cur = conn.cursor()
                try:
                    cur.execute(dialect.describe_columns(ss, safe_table))
                    for crow in (cur.fetchall() or []):
                        if crow and crow[0]:
                            cols.append({"column_name": str(crow[0]), "data_type": str(crow[1] or "").lower()})
                        if len(cols) >= app._BOOTSTRAP_MAX_COLS_PER_TABLE:
                            break
                except Exception:
                    cols = []
                finally:
                    cur.close()
                if cols:
                    break  # 테이블을 담은 첫 SQL 스키마에서 종료(DB명 평탄화와 정합)
        else:
            conn = _db.connect(datasource=ds, autocommit=True)
            known = set(_schema.load_known_schemas(conn) or [])
            safe_schema = _safe_ident_fn(schema_name)
            if safe_schema not in known:
                return None
            dialect = _dialects.active()
            cur = conn.cursor()
            try:
                cur.execute(dialect.describe_columns(safe_schema, safe_table))
                for crow in (cur.fetchall() or []):
                    if crow and crow[0]:
                        cols.append({"column_name": str(crow[0]), "data_type": str(crow[1] or "").lower()})
                    if len(cols) >= app._BOOTSTRAP_MAX_COLS_PER_TABLE:
                        break
            finally:
                cur.close()
        return {"schema_name": schema_name, "table_name": table_name, "columns": cols} if cols else None
    except Exception:
        logging.getLogger(__name__).warning(
            "metadata suggest introspection 실패 ds=%s schema=%s table=%s", key, schema_name, table_name, exc_info=True
        )
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass

def _metadata_grounding_cols_line(grounding) -> str:
    if not grounding or not grounding.get("columns"):
        return ""
    cols = grounding["columns"][:60]
    names = ", ".join(
        (f"{c['column_name']}({c['data_type']})" if c.get("data_type") else c["column_name"]) for c in cols
    )
    return f"이 테이블의 실제 컬럼: {names}\n"

def _metadata_grounding_coltype(grounding, column_name) -> str:
    if not grounding or not column_name:
        return ""
    target = str(column_name).strip().lower()
    for c in (grounding.get("columns") or []):
        if str(c.get("column_name") or "").strip().lower() == target:
            return c.get("data_type") or ""
    return ""

def _metadata_suggest_messages(sub: str, fields: dict, grounding) -> list:
    """서브뷰별 자동완성 프롬프트 — 식별 필드 → 설명/정의/라벨/질문 1건. 본문만 출력하도록 지시."""
    f = fields
    if sub == "glossary":
        body = (
            "당신은 사내 데이터 분석 용어사전을 작성하는 전문가입니다.\n"
            f"다음 도메인 용어의 '정의'를 한국어 1~3문장으로 간결하게 작성하세요.\n"
            f"용어: {f.get('term', '')}\n"
            "판정 기준·계산 방식이 있으면 한 줄로 포함하세요. 정의 본문만 출력하고 따옴표·머리말을 붙이지 마세요."
        )
    elif sub == "enums":
        body = (
            "당신은 데이터베이스 코드값의 의미 라벨을 다는 전문가입니다.\n"
            f"테이블 {f.get('table_name', '')}, 컬럼 {f.get('column_name', '')} 의 코드 값 "
            f"'{f.get('code', '')}' 가 의미하는 한국어 라벨(짧은 명사구)을 출력하세요.\n"
            "라벨 텍스트만 출력하고 설명·따옴표·머리말을 붙이지 마세요."
        )
    elif sub == "tables":
        cols_line = _metadata_grounding_cols_line(grounding)
        body = (
            "당신은 데이터베이스 테이블 카탈로그를 작성하는 전문가입니다.\n"
            f"테이블 {_metadata_qualname(f.get('schema_name'), f.get('table_name'))} 가 담는 데이터와 용도를 "
            "한국어 1~3문장으로 설명하세요.\n"
            f"{cols_line}"
            "설명 본문만 출력하고 머리말·따옴표를 붙이지 마세요. 실제 컬럼이 주어졌으면 그에 근거하고, "
            "없으면 일반적이되 단정적이지 않게 작성하세요."
        )
    elif sub == "columns":
        dtype = _metadata_grounding_coltype(grounding, f.get("column_name"))
        body = (
            "당신은 데이터베이스 컬럼 사전을 작성하는 전문가입니다.\n"
            f"컬럼 {_metadata_qualname(f.get('schema_name'), f.get('table_name'))}.{f.get('column_name', '')}"
            f"{(' (' + dtype + ')') if dtype else ''} 이 담는 값과 의미를 한국어 1~2문장으로 설명하세요.\n"
            "설명 본문만 출력하고 머리말·따옴표를 붙이지 마세요."
        )
    else:  # samples
        body = (
            "당신은 SQL 의 의도를 자연어 질문으로 옮기는 전문가입니다.\n"
            "다음 SQL 이 답하는 자연어 질문을 한국어 1문장으로 작성하세요.\n"
            f"SQL:\n{f.get('sql', '')}\n"
            "질문 문장만 출력하고 머리말·따옴표·SQL 재출력을 하지 마세요."
        )
    return [{"role": "user", "content": body}]

def _metadata_bulk_describe_messages(mode: str, tables: list) -> list:
    """골격 일괄 자동완성 프롬프트 — JSON 객체로만 응답하도록 강하게 지시."""
    lines = []
    for t in tables:
        q = _metadata_qualname(t.get("schema_name"), t.get("table_name"))
        if mode == "columns":
            cols = ", ".join(
                (f"{c['column_name']}({c['data_type']})" if c.get("data_type") else c["column_name"])
                for c in (t.get("columns") or [])
            )
            lines.append(f"- {q}: {cols or '(컬럼 정보 없음)'}")
        else:
            cols = ", ".join(c["column_name"] for c in (t.get("columns") or [])[:40])
            lines.append(f"- {q} (컬럼: {cols or '없음'})")
    skeleton = "\n".join(lines)
    if mode == "tables":
        instruction = (
            "각 테이블이 담는 데이터/용도를 한국어 1~2문장으로 설명하세요.\n"
            "반드시 아래 JSON 객체로만 출력하세요(키=테이블 이름, 값=설명 문자열). 코드펜스·다른 텍스트 금지:\n"
            '{"테이블이름": "설명", ...}'
        )
    else:
        instruction = (
            "각 컬럼이 담는 값/의미를 한국어 1문장으로 설명하세요.\n"
            "반드시 아래 중첩 JSON 객체로만 출력하세요(키=테이블 이름, 값={컬럼 이름: 설명}). 코드펜스·다른 텍스트 금지:\n"
            '{"테이블이름": {"컬럼이름": "설명", ...}, ...}'
        )
    body = (
        "당신은 데이터베이스 카탈로그를 작성하는 전문가입니다. 아래 스키마 골격에 설명을 작성합니다.\n\n"
        f"=== 골격 ===\n{skeleton}\n\n{instruction}"
    )
    return [{"role": "user", "content": body}]

def _metadata_parse_json_object(text):
    """LLM 출력에서 JSON 객체 추출 — 코드펜스/전후 텍스트 허용. 실패 시 None."""
    if not text:
        return None
    s = str(text).strip()
    if s.startswith("```"):
        # ```json ... ``` 또는 ``` ... ``` 펜스 제거.
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            if s.lstrip()[:4].lower() == "json":
                s = s.lstrip()[4:]
    s = s.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    try:
        i = s.index("{")
        j = s.rindex("}")
        obj = json.loads(s[i:j + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None

def _metadata_bulk_shape_results(mode: str, tables: list, parsed: dict) -> list:
    """LLM JSON 응답을 프론트가 입력란에 매칭할 수 있는 리스트로 정형(대소문자/공백 무시 매칭)."""
    out: list = []
    pidx = {str(k).strip().lower(): v for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    cap = app._METADATA_FIELD_CAPS["description"]
    for t in tables:
        tname = t["table_name"]
        pv = pidx.get(tname.strip().lower())
        if mode == "tables":
            if isinstance(pv, str) and pv.strip():
                out.append({"schema_name": t.get("schema_name", ""), "table_name": tname,
                            "description": pv.strip()[:cap]})
        else:
            if isinstance(pv, dict):
                cidx = {str(k).strip().lower(): v for k, v in pv.items()}
                for c in (t.get("columns") or []):
                    cv = cidx.get(c["column_name"].strip().lower())
                    if isinstance(cv, str) and cv.strip():
                        out.append({"schema_name": t.get("schema_name", ""), "table_name": tname,
                                    "column_name": c["column_name"], "description": cv.strip()[:cap]})
    return out

async def _metadata_llm_complete(messages: list, *, task: str = "summary", temperature: float = 0.3):
    """메타데이터 AI 자동완성 공용 LLM 호출(비스트리밍). (text, meta, None) 또는 (None, None, JSONResponse).

    admin_generate_product_prompt 비스트리밍 경로와 동일 패턴 — 단일 uvicorn 루프를 막지 않도록
    run_in_executor 로 동기 호출을 오프로드. task = max_tokens cap 키('summary'=단건, 'prompt_gen'=일괄).
    """
    from modules.llm import _get_llm_client
    llm_model = app._resolve_session_default_model()
    client = _get_llm_client(model=llm_model)
    if client is None:
        # feature-0043 사용감 패리티: 운영 결정에 의한 차단은 장애 문구로 말하지 않는다.
        from shared.llm_gate import feature_blocked_message, server_llm_enabled

        if not server_llm_enabled():
            return None, None, app._json_error(
                feature_blocked_message("메타데이터 AI 자동완성"), 503)
        return None, None, app._json_error("LLM 클라이언트를 초기화할 수 없습니다.", 503)
    # cc-identity-chokepoint(2026-08-25): provider 전송 직전 관문(feature-0002 CHG-20260825T170000).
    from modules.llm import prepare_provider_messages
    create_kwargs: dict = {"model": llm_model,
                           "messages": prepare_provider_messages(messages, llm_model),
                           "timeout": 60}
    mt = app.max_tokens_for_model(llm_model, task)
    if mt is not None:
        create_kwargs["max_tokens"] = mt
    if app.model_supports_temperature(llm_model):
        create_kwargs["temperature"] = temperature

    def _aiops_create_and_record():
        # AI 운영 관제 계측(TASK-AIOPS): create + 회계를 executor 스레드에서 함께 실행(이벤트 루프 무영향).
        # task 는 reasoning 'summary' 와 구분되게 metadata_ 접두(taxonomy: ai.metadata.autocomplete).
        _t0 = time.perf_counter_ns()
        r = client.chat.completions.create(**create_kwargs)
        try:
            from modules.llm import _record_llm_usage
            _record_llm_usage(
                str(llm_model or ""), f"metadata_{task}", r, conversation_id=None,
                latency_ms=int((time.perf_counter_ns() - _t0) // 1_000_000),
            )
        except Exception:
            pass
        return r

    try:
        resp = await asyncio.get_event_loop().run_in_executor(None, _aiops_create_and_record)
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        truncated = getattr(choice, "finish_reason", None) == "length"
    except Exception as exc:  # noqa: BLE001 — 어떤 LLM 오류든 502 로 변환
        return None, None, app._json_error(f"LLM 생성 실패: {exc}", 502)
    return text, {"model": llm_model, "truncated": truncated}, None


# ── graph-perf-bg: /graph/columns introspection TTL 캐시 ──────────────────────────
#   /api/admin/metadata/graph/columns 는 그래프 투영에 Column 노드가 없는 테이블을 (더블)클릭할 때마다
#   데이터소스 information_schema 를 **라이브 조회**했다 — 요청 스레드를 1~5초 블로킹하고 무캐시라, 펼침
#   임계경로(그래프 fetch + columns fetch 2왕복)의 두 번째 왕복이 매번 재수행됐다. 성공한 introspection 을
#   (scope_key, fqn) 키로 짧은 TTL(기본 300s) 동안 프로세스 내 캐시해 반복 펼침·다중 사용자·재진입 왕복을
#   제거한다. **실패/빈 결과는 캐시하지 않는다**(일시 오류 재시도 보장). DDL 변경은 TTL 만료 후 자동 반영.
#   프로세스별 캐시라 마이그레이션 불필요(alembic 병렬 충돌 회피). TTL<=0 이면 캐시 비활성(테스트/디버그).
import os as _os
import time as _time
import threading as _threading

_COLUMNS_CACHE = {}                        # (scope_key, fqn) -> (expires_at_monotonic, payload_dict)
_COLUMNS_CACHE_LOCK = _threading.Lock()
_COLUMNS_CACHE_MAX = 512                    # 무한 성장 방지 상한


def _graph_columns_cache_ttl() -> float:
    try:
        return float(_os.environ.get("METADATA_GRAPH_COLUMNS_CACHE_TTL", "300") or 300)
    except (TypeError, ValueError):
        return 300.0


def _graph_columns_cache_get(scope_key: str, fqn: str):
    """유효 캐시 payload 반환(없거나 만료면 None). 만료 항목은 조회 시 청소."""
    if _graph_columns_cache_ttl() <= 0:
        return None
    now = _time.monotonic()
    with _COLUMNS_CACHE_LOCK:
        item = _COLUMNS_CACHE.get((scope_key, fqn))
        if not item:
            return None
        exp, payload = item
        if exp <= now:
            _COLUMNS_CACHE.pop((scope_key, fqn), None)
            return None
        return payload


def _graph_columns_cache_put(scope_key: str, fqn: str, payload) -> None:
    """성공 introspection payload 를 TTL 캐시. 상한 초과 시 만료 항목 청소 후 최소-만료 항목 축출."""
    ttl = _graph_columns_cache_ttl()
    if ttl <= 0:
        return
    now = _time.monotonic()
    with _COLUMNS_CACHE_LOCK:
        if len(_COLUMNS_CACHE) >= _COLUMNS_CACHE_MAX:
            for k in [k for k, (e, _p) in _COLUMNS_CACHE.items() if e <= now]:
                _COLUMNS_CACHE.pop(k, None)
            while len(_COLUMNS_CACHE) >= _COLUMNS_CACHE_MAX:
                _COLUMNS_CACHE.pop(min(_COLUMNS_CACHE, key=lambda k: _COLUMNS_CACHE[k][0]), None)
        _COLUMNS_CACHE[(scope_key, fqn)] = (now + ttl, payload)


#: 전역(`common`) 상속분을 목록에 덧붙이는 공통 규약 (2026-09-01, glossary 에서 이식).
#:
#: 읽기 캐스케이드는 `[제품, common]` 2단인데 관리 목록이 1단이면, 관리자는 「이 제품에 없다」로
#: 읽고 같은 항목을 제품 scope 에 다시 등록한다. 라이브 실측이 그 경로를 확인해 줬다 —
#: `column_descriptions` 833개 컬럼이 2개 이상 scope 중복이고 그중 826개(99.2%)는 **설명 텍스트까지
#: 동일**. ⚠ 그 중복은 **제품↔제품** 축이라 이 변경으로 정리되지 **않는다** — 여기서 막는 것은
#: 「전역에 올려도 안 보이니 아무도 안 올린다」는 **재생산 경로**다.
#:
#: 상속분은 `inherited: true` 로 내려보내고 **편집 대상이 아니다**(편집·삭제는 단일 scope 정확일치
#: 유지). 화면이 그 값 하나로 읽기 전용을 판정한다 — 프론트가 scope 를 비교해 스스로 판정하면
#: 두 벌이 되고, 한쪽이 낡으면 「눌러도 404 나는 편집 버튼」이 남는다.
def _with_inherited(rows, inherited_rows, to_item):
    """(자기 scope 행, 전역 상속 행) → 직렬화된 items. 상속분은 뒤에 붙는다."""
    return ([to_item(r, False) for r in rows]
            + [to_item(r, True) for r in inherited_rows])


def _load_inherited(pg, scope_key, loader, label):
    """전역 상속분 조회 — **fail-soft**. 상속분은 보조 정보라 실패가 목록 자체를 죽이지 않는다.

    반환 `(rows, failed)`. 실패를 **빈 목록으로 접지 않는다** — 접으면 화면이 「전역에 아무것도
    없다」와 「조회가 깨졌다」를 같게 보여주고, 관리자는 전자로 읽어 같은 항목을 제품 scope 에
    다시 등록한다(이번 cycle 이 고치는 중복이 그 경로로 재생산된다, §16.7 G9-b).

    `common` 을 보고 있으면 자기 자신이므로 붙이지 않는다(중복 표시 방지 — 실패 아님).
    """
    if str(scope_key or "") == "common":
        return [], False
    try:
        return loader(pg), False
    except Exception:
        logging.getLogger(__name__).warning("%s 전역 상속분 조회 실패", label, exc_info=True)
        return [], True


@router.get("/api/admin/metadata/glossary")
def admin_list_glossary(request: Request, account=Depends(app.require_permission('metadata.glossary.read'))) -> JSONResponse:
    """용어 목록 — 선택 scope + **전역(common) 상속분**. 권한 kb.ingest.manual.

    ?scope_key= (기본 'common'). ?role_key= 지정 시 그 역할 행만(공용 '*' 미포함) 필터 — 역할별
    조회. 미지정이면 scope 의 모든 역할 행(role_key 필드로 구분 표시).

    ## 왜 전역분을 함께 내려보내는가 (0057)

    답변에 실제로 주입되는 것은 `[제품, common]` **둘 다**인데(`_kb_scope_candidates`), 목록은
    제품 행만 보여 왔다. 그래서 관리자는 「이 제품에 이 용어가 없다」고 읽고 같은 용어를 제품
    scope 에 또 등록했다 — 라이브에서 34개 용어가 2~4개 scope 로 번진 경로가 정확히 이것이다.

    전역분은 `inherited: true` 로 표시해 내려보낸다. **편집 대상이 아니다** — 편집·삭제는 여전히
    단일 scope 정확일치로만 동작하고(캐스케이드 금지 유지), 화면이 그것을 읽기 전용으로 그린다.
    제품 scope 를 보고 있을 때만 붙인다(`common` 을 보고 있으면 자기 자신이라 중복이다).
    """
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    role_filter = None
    rk_param = request.query_params.get("role_key")
    if rk_param is not None and str(rk_param).strip() != "":
        role_filter, rerr = _metadata_check_role_key(rk_param)
        if rerr:
            return rerr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    inherited_rows: list = []
    try:
        rows = _kg.list_glossary_admin(pg, scope_key, role_key=role_filter)
        if scope_key != _kg.GLOBAL_SCOPE:
            # 실패해도 목록 자체는 살린다 — 상속분은 보조 정보다(fail-soft).
            try:
                inherited_rows = _kg.list_global_glossary_for_scope(pg, role_key=role_filter)
            except Exception:
                logging.getLogger(__name__).warning(
                    "admin_list_glossary 전역 상속분 조회 실패", exc_info=True)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary 조회 실패", exc_info=True)
        return app._json_error("용어 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass

    # row: (id, scope_key, role_key, term, definition, source, created_at, updated_at, term_tier)
    def _row(r, inherited):
        return {
            "id": int(r[0]), "scope_key": str(r[1] or ""), "role_key": str(r[2] or "*"),
            "term": str(r[3] or ""), "definition": str(r[4] or ""),
            "source": str(r[5] or "manual"),
            "created_at": _metadata_iso(r[6]), "updated_at": _metadata_iso(r[7]),
            "term_tier": str(r[8] or "product"),
            # 화면이 편집 가능 여부를 이 값 하나로 판정한다 — 프론트가 scope 를 비교해 스스로
            # 판정하면 두 벌이 되고, 한쪽이 낡으면 「지워지지 않는 삭제 버튼」이 남는다.
            "inherited": bool(inherited),
        }

    items = [_row(r, False) for r in rows] + [_row(r, True) for r in inherited_rows]
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key,
                         "role_key": role_filter,
                         "inherited_count": len(inherited_rows)})

@router.post("/api/admin/metadata/glossary")
async def admin_create_glossary(request: Request, account=Depends(app.require_permission('metadata.glossary.create'))) -> JSONResponse:
    """용어 생성(upsert). 권한 kb.ingest.manual. body: scope_key, term, definition."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    role_key, rerr = _metadata_check_role_key(data.get("role_key"))
    if rerr:
        return rerr
    term, terr = _metadata_str_field(data, "term")
    if terr:
        return terr
    definition, derr = _metadata_str_field(data, "definition")
    if derr:
        return derr
    from modules import kb_glossary as _kg
    # 등록 화면이 tier 를 보내지 않으면 **보고 있는 scope 가 답한다** — 전역 scope 에 손으로
    # 넣는 것은 곧 「전역 용어」 선언이고, 제품 scope 는 「제품 고유」다. 여기서 'product' 로
    # 고정하면 전역 사전 항목이 전부 product 로 표기돼 tier 축이 첫날부터 거짓이 된다.
    _tier_default = _kg.TIER_ORG if scope_key == _kg.GLOBAL_SCOPE else _kg.TIER_PRODUCT
    term_tier, tierr = _metadata_check_term_tier(data.get("term_tier"), default=_tier_default)
    if tierr:
        return tierr
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _kg.upsert_glossary_term(pg, scope_key, term, definition, role_key=role_key,
                                 term_tier=term_tier)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_glossary 실패", exc_info=True)
        return app._json_error("용어 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.term.create",
                    resource_id=f"{scope_key}:{role_key}:{term}",
                    change_json={"scope_key": scope_key, "role_key": role_key, "term": term,
                                 "term_tier": term_tier})
    return JSONResponse({"ok": True, "scope_key": scope_key, "role_key": role_key, "term": term,
                         "term_tier": term_tier})

@router.put("/api/admin/metadata/glossary/{term_id}")
async def admin_update_glossary(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.update'))) -> JSONResponse:
    """용어 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, term, definition."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    # role_key 는 선택 — 본문에 있으면 역할 귀속까지 변경(공용↔역할 이동), 없으면 기존 유지.
    role_key = None
    if "role_key" in (data or {}) and str(data.get("role_key") or "").strip() != "":
        role_key, rerr = _metadata_check_role_key(data.get("role_key"))
        if rerr:
            return rerr
    term, terr = _metadata_str_field(data, "term")
    if terr:
        return terr
    definition, derr = _metadata_str_field(data, "definition")
    if derr:
        return derr
    # 본문에 없으면 **기존 유지**(default=None) — 사용자가 고치지 않은 축을 바꾸지 않는다.
    term_tier, tierr = _metadata_check_term_tier(data.get("term_tier"))
    if tierr:
        return tierr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.update_glossary_term(pg, int(term_id), scope_key, term, definition,
                                            role_key=role_key, term_tier=term_tier)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 용어를 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        # UNIQUE(scope,role,term) 충돌 → 409 (같은 역할에 동일 용어 존재).
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("같은 역할에 동일 용어가 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_glossary 실패 id=%s", term_id, exc_info=True)
        return app._json_error("용어 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.term.update",
                    resource_id=int(term_id),
                    change_json={"scope_key": scope_key, "role_key": role_key, "term": term,
                                 "term_tier": term_tier})
    return JSONResponse({"ok": True, "id": int(term_id)})

@router.delete("/api/admin/metadata/glossary/{term_id}")
def admin_delete_glossary(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.delete'))) -> JSONResponse:
    """용어 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_glossary_term(pg, int(term_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_glossary 실패 id=%s", term_id, exc_info=True)
        return app._json_error("용어 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # 멱등 — affected=0(이미 없음)도 성공. audit 은 실제 삭제(affected>0)만 기록.
    if affected > 0:
        _metadata_audit(request, account, action="glossary.term.delete",
                        resource_id=int(term_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(term_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/glossary-feedback")
def admin_list_glossary_feedback(request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐 목록. 권한 kb.glossary.curate. ?status=(기본 pending, 'all'=전체) &scope_key= &role_key=."""
    status = str(request.query_params.get("status") or "pending").strip().lower()
    if status in ("all", ""):
        status = None
    # 'skipped_general' — 범용 DB 용어로 판정돼 **등록하지 않은** 후보(0057). 목록에서 볼 수
    # 있어야 오분류를 관리자가 promote 로 되살린다. 조회할 수 없으면 그 판정은 사실상 영구 삭제다.
    elif status not in ("pending", "auto_promoted", "promoted", "rejected", "skipped_general"):
        return app._json_error("허용되지 않은 status 입니다.", 400)
    scope_filter = None
    sk_param = request.query_params.get("scope_key")
    if sk_param is not None and str(sk_param).strip() != "":
        scope_filter, serr = _metadata_check_scope(sk_param)
        if serr:
            return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_feedback(pg, status=status, scope_key=scope_filter)
        # 배지 pending_count 도 list 와 동일 scope 로 한정 — datasource 선택 시 배지↔리스트 카운트 정합.
        pending_count = _kg.count_glossary_feedback(pg, status="pending", scope_key=scope_filter)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary_feedback 조회 실패", exc_info=True)
        return app._json_error("검토 큐 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, role_key, term, suggested_definition, confidence, status,
    #       source_run_id, conversation_id, promoted_glossary_id, approved_by,
    #       created_at, updated_at, term_tier)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "role_key": str(r[2] or "*"),
        "term": str(r[3] or ""), "suggested_definition": str(r[4] or ""),
        "confidence": float(r[5]) if r[5] is not None else None, "status": str(r[6] or ""),
        "source_run_id": (str(r[7]) if r[7] is not None else None),
        "conversation_id": (str(r[8]) if r[8] is not None else None),
        "promoted_glossary_id": (int(r[9]) if r[9] is not None else None),
        "approved_by": (str(r[10]) if r[10] is not None else None),
        "created_at": app._glossary_feedback_iso(r[11]), "updated_at": app._glossary_feedback_iso(r[12]),
        "term_tier": str(r[13] or "product"),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items),
                         "pending_count": int(pending_count), "status": status})

@router.post("/api/admin/metadata/glossary-feedback/{feedback_id}/promote")
def admin_promote_glossary_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐(pending) → 용어사전 승급. 권한 kb.glossary.curate."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        gid = _kg.promote_glossary_feedback(
            pg, int(feedback_id), approved_by=str((account or {}).get("username") or "") or None)
        if gid is None:
            pg.rollback()
            return app._json_error("해당 후보를 찾을 수 없거나 이미 처리되었습니다.", 404)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_promote_glossary_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("용어 승급 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.feedback.promote",
                    resource_id=int(feedback_id),
                    change_json={"feedback_id": int(feedback_id), "glossary_id": int(gid)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "glossary_id": int(gid)})

@router.post("/api/admin/metadata/glossary-feedback/{feedback_id}/reject")
def admin_reject_glossary_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.glossary.curate'))) -> JSONResponse:
    """검토 큐 거부(pending) 또는 자동등록 되돌리기(auto_promoted → source='auto' 행 회수).
    권한 kb.glossary.curate. 멱등."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.reject_glossary_feedback(pg, int(feedback_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_reject_glossary_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("용어 후보 거부 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="glossary.feedback.reject",
                        resource_id=int(feedback_id), change_json={"feedback_id": int(feedback_id)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "rejected": int(affected)})

@router.get("/api/admin/metadata/glossary/{term_id}/relations")
def admin_list_glossary_relations(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.read'))) -> JSONResponse:
    """해당 용어의 인접 참조(유사어/동의어/see_also) 목록. 권한 kb.ingest.manual."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_glossary_relations(pg, int(term_id))
    except Exception:
        logging.getLogger(__name__).warning("admin_list_glossary_relations 실패 id=%s", term_id, exc_info=True)
        return app._json_error("유사어 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (relation_id, relation_type, from_id, to_id, other_id, other_scope, other_role, other_term, other_def)
    items = [{
        "relation_id": int(r[0]), "relation_type": str(r[1] or ""),
        "from_id": int(r[2]), "to_id": int(r[3]),
        "other_id": int(r[4]), "other_scope_key": str(r[5] or ""), "other_role_key": str(r[6] or "*"),
        "other_term": str(r[7] or ""), "other_definition": str(r[8] or ""),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items), "term_id": int(term_id)})

@router.post("/api/admin/metadata/glossary/{term_id}/relations")
async def admin_add_glossary_relation(term_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.update'))) -> JSONResponse:
    """유사어 참조 추가. 권한 kb.ingest.manual. body: to_id(필수), relation_type(synonym|similar|see_also)."""
    data = await _metadata_read_json(request)
    try:
        to_id = int(data.get("to_id"))
    except (TypeError, ValueError):
        return app._json_error("to_id 는 필수(정수)입니다.", 400)
    if int(to_id) == int(term_id):
        return app._json_error("자기 자신은 참조로 연결할 수 없습니다.", 400)
    relation_type = str(data.get("relation_type") or "similar").strip().lower()
    if relation_type not in ("synonym", "similar", "see_also"):
        return app._json_error("relation_type 은 synonym|similar|see_also 중 하나여야 합니다.", 400)
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        # 두 용어 존재 확인(FK 위반 전 명시 404).
        if _kg.get_glossary_term(pg, int(term_id)) is None or _kg.get_glossary_term(pg, int(to_id)) is None:
            pg.rollback()
            return app._json_error("연결 대상 용어를 찾을 수 없습니다.", 404)
        _kg.add_glossary_relation(pg, int(term_id), int(to_id), relation_type,
                                  created_by=str((account or {}).get("username") or "") or None)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_add_glossary_relation 실패 from=%s to=%s", term_id, to_id, exc_info=True)
        return app._json_error("유사어 추가 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="glossary.relation.create",
                    resource_id=int(term_id),
                    change_json={"from_id": int(term_id), "to_id": int(to_id), "relation_type": relation_type})
    return JSONResponse({"ok": True, "from_id": int(term_id), "to_id": int(to_id),
                         "relation_type": relation_type})

@router.delete("/api/admin/metadata/glossary/relations/{relation_id}")
def admin_delete_glossary_relation(relation_id: int, request: Request, account=Depends(app.require_permission('metadata.glossary.update'))) -> JSONResponse:
    """유사어 참조 삭제(by relation id, 멱등). 권한 kb.ingest.manual."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_glossary_relation(pg, int(relation_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_glossary_relation 실패 id=%s", relation_id, exc_info=True)
        return app._json_error("유사어 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="glossary.relation.delete",
                        resource_id=int(relation_id), change_json={"relation_id": int(relation_id)})
    return JSONResponse({"ok": True, "id": int(relation_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/enums")
def admin_list_enums(request: Request, account=Depends(app.require_permission('metadata.enum.read'))) -> JSONResponse:
    """ENUM 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    inherited_rows: list = []
    inherited_failed = False
    try:
        rows = _kg.list_enum_admin(pg, scope_key)
        inherited_rows, inherited_failed = _load_inherited(
            pg, scope_key, _kg.list_global_enum_for_scope, "ENUM")
    except Exception:
        logging.getLogger(__name__).warning("admin_list_enums 조회 실패", exc_info=True)
        return app._json_error("ENUM 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, column_name, code, label, source, created_at, updated_at)
    def _item(r, inherited):
        return {
            "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
            "table_name": str(r[3] or ""), "column_name": str(r[4] or ""),
            "code": str(r[5] or ""), "label": str(r[6] or ""), "source": str(r[7] or "manual"),
            "created_at": _metadata_iso(r[8]), "updated_at": _metadata_iso(r[9]),
            "inherited": bool(inherited),
        }
    items = _with_inherited(rows, inherited_rows, _item)
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key,
                         "inherited_count": len(inherited_rows),
                         "inherited_error": inherited_failed})

@router.post("/api/admin/metadata/enums")
async def admin_create_enum(request: Request, account=Depends(app.require_permission('metadata.enum.create'))) -> JSONResponse:
    """ENUM 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, column_name, code, label, schema_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    fields, ferr = _metadata_enum_fields(data)
    if ferr:
        return ferr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _kg.upsert_enum_entry(pg, scope_key, fields["table_name"], fields["column_name"],
                              fields["code"], fields["label"], schema_name=fields["schema_name"])
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_enum 실패", exc_info=True)
        return app._json_error("ENUM 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="enum.entry.create",
                    resource_id=f"{scope_key}:{fields['table_name']}.{fields['column_name']}={fields['code']}",
                    change_json={"scope_key": scope_key, "table_name": fields["table_name"],
                                 "column_name": fields["column_name"], "code": fields["code"]})
    return JSONResponse({"ok": True, "scope_key": scope_key})

@router.put("/api/admin/metadata/enums/{entry_id}")
async def admin_update_enum(entry_id: int, request: Request, account=Depends(app.require_permission('metadata.enum.update'))) -> JSONResponse:
    """ENUM 수정(by id, scope 가드). 권한 kb.ingest.manual. body 동일."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    fields, ferr = _metadata_enum_fields(data)
    if ferr:
        return ferr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.update_enum_entry(
            pg, int(entry_id), scope_key, fields["table_name"], fields["column_name"],
            fields["code"], fields["label"], schema_name=fields["schema_name"])
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 ENUM 항목을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        # UNIQUE(scope,schema,table,column,code) 충돌 → 409 (다른 행과 key 중복).
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 key(스키마/테이블/컬럼/코드)의 ENUM 항목이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_enum 실패 id=%s", entry_id, exc_info=True)
        return app._json_error("ENUM 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="enum.entry.update",
                    resource_id=int(entry_id),
                    change_json={"scope_key": scope_key, "table_name": fields["table_name"],
                                 "column_name": fields["column_name"], "code": fields["code"]})
    return JSONResponse({"ok": True, "id": int(entry_id)})

@router.delete("/api/admin/metadata/enums/{entry_id}")
def admin_delete_enum(entry_id: int, request: Request, account=Depends(app.require_permission('metadata.enum.delete'))) -> JSONResponse:
    """ENUM 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.delete_enum_entry(pg, int(entry_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_enum 실패 id=%s", entry_id, exc_info=True)
        return app._json_error("ENUM 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="enum.entry.delete",
                        resource_id=int(entry_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(entry_id), "deleted": int(affected)})

# ── ENUM 코드사전 대화 자율수집 검토 큐(0039) — 용어사전 glossary-feedback 대칭 ────────────
@router.get("/api/admin/metadata/enum-feedback")
def admin_list_enum_feedback(request: Request, account=Depends(app.require_permission('kb.enum.curate'))) -> JSONResponse:
    """검토 큐 목록. 권한 kb.enum.curate. ?status=(기본 pending, 'all'=전체) &scope_key=."""
    status = str(request.query_params.get("status") or "pending").strip().lower()
    if status in ("all", ""):
        status = None
    elif status not in ("pending", "auto_promoted", "promoted", "rejected"):
        return app._json_error("허용되지 않은 status 입니다.", 400)
    scope_filter = None
    sk_param = request.query_params.get("scope_key")
    if sk_param is not None and str(sk_param).strip() != "":
        scope_filter, serr = _metadata_check_scope(sk_param)
        if serr:
            return serr
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        rows = _kg.list_enum_feedback(pg, status=status, scope_key=scope_filter)
        # 배지 pending_count 도 list 와 동일 scope 로 한정 — datasource 선택 시 배지↔리스트 카운트 정합.
        pending_count = _kg.count_enum_feedback(pg, status="pending", scope_key=scope_filter)
    except Exception:
        logging.getLogger(__name__).warning("admin_list_enum_feedback 조회 실패", exc_info=True)
        return app._json_error("검토 큐 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, column_name, code, suggested_label,
    #       confidence, status, source_run_id, conversation_id, promoted_enum_id, approved_by,
    #       created_at, updated_at)
    items = [{
        "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
        "table_name": str(r[3] or ""), "column_name": str(r[4] or ""), "code": str(r[5] or ""),
        "suggested_label": str(r[6] or ""),
        "confidence": float(r[7]) if r[7] is not None else None, "status": str(r[8] or ""),
        "source_run_id": (str(r[9]) if r[9] is not None else None),
        "conversation_id": (str(r[10]) if r[10] is not None else None),
        "promoted_enum_id": (int(r[11]) if r[11] is not None else None),
        "approved_by": (str(r[12]) if r[12] is not None else None),
        "created_at": _metadata_iso(r[13]), "updated_at": _metadata_iso(r[14]),
    } for r in rows]
    return JSONResponse({"items": items, "count": len(items),
                         "pending_count": int(pending_count), "status": status})

@router.post("/api/admin/metadata/enum-feedback/{feedback_id}/promote")
def admin_promote_enum_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.enum.curate'))) -> JSONResponse:
    """검토 큐(pending) → ENUM 코드사전 승급. 권한 kb.enum.curate."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        eid = _kg.promote_enum_feedback(
            pg, int(feedback_id), approved_by=str((account or {}).get("username") or "") or None)
        if eid is None:
            pg.rollback()
            return app._json_error("해당 후보를 찾을 수 없거나 이미 처리되었습니다.", 404)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_promote_enum_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("ENUM 승급 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="enum.feedback.promote",
                    resource_id=int(feedback_id),
                    change_json={"feedback_id": int(feedback_id), "enum_id": int(eid)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "enum_id": int(eid)})

@router.post("/api/admin/metadata/enum-feedback/{feedback_id}/reject")
def admin_reject_enum_feedback(feedback_id: int, request: Request, account=Depends(app.require_permission('kb.enum.curate'))) -> JSONResponse:
    """검토 큐 거부(pending) 또는 자동등록 되돌리기(auto_promoted → source='auto' 행 회수).
    권한 kb.enum.curate. 멱등."""
    from modules import kb_glossary as _kg
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _kg.reject_enum_feedback(pg, int(feedback_id))
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_reject_enum_feedback 실패 id=%s", feedback_id, exc_info=True)
        return app._json_error("ENUM 후보 거부 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="enum.feedback.reject",
                        resource_id=int(feedback_id), change_json={"feedback_id": int(feedback_id)})
    return JSONResponse({"ok": True, "id": int(feedback_id), "rejected": int(affected)})

@router.post("/api/admin/metadata/enum-feedback/bulk-promote")
async def admin_bulk_promote_enum_feedback(request: Request, account=Depends(app.require_permission('kb.enum.curate'))) -> JSONResponse:
    """검토 큐(pending) 다건 → ENUM 코드사전 일괄 승급(구조 묶음 단위 '등록'). 권한 kb.enum.curate.

    body: {"feedback_ids": [int, ...]}. 관리자가 묶음 체크리스트에서 '전체 승인' 또는 '일부 해제'
    후 선택한 후보만 승급한다. 미선택(해제)분은 pending 유지(거부 아님 — 비파괴). 단일 트랜잭션:
    하나라도 예외면 전체 롤백. 이미 처리된/없는 id 는 skip(skipped_ids)로 표시(부분 skip 은 정상).

    동시성: id 를 정렬해 결정적 lock 순서로 FOR UPDATE 를 획득한다(동시 bulk-promote 간 deadlock
    회피). 블로킹 DB 배치(최대 _ENUM_BULK_PROMOTE_MAX × 3 쿼리 + FOR UPDATE)는 run_in_executor 로
    이벤트 루프 밖(threadpool)에서 실행한다 — lock 대기가 워커 전체를 멈추지 않도록(단건 def 핸들러가
    threadpool 로 dispatch 되는 것과 동형; 본 핸들러는 body await 때문에 async 필수).
    """
    data = await _metadata_read_json(request)
    raw_ids = (data or {}).get("feedback_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return app._json_error("feedback_ids 는 비어있지 않은 배열이어야 합니다.", 400)
    # 파싱/DB 이전에 원본 길이부터 cap — 초대형 배열의 full-parse + O(n) 루프 선-DoS 차단.
    # (dedup 후 개수는 raw 길이 이하이므로 이 검사로 승급 대상 수도 자동 상한.)
    if len(raw_ids) > _ENUM_BULK_PROMOTE_MAX:
        return app._json_error(f"한 번에 최대 {_ENUM_BULK_PROMOTE_MAX}건까지 등록할 수 있습니다.", 400)
    seen = set()
    ids = []
    for v in raw_ids:
        # bool(JSON true/false) · 비정수 float(1.9) 은 명시 거부(int() 무언 강등/절단 차단).
        if isinstance(v, bool) or (isinstance(v, float) and not v.is_integer()):
            return app._json_error("feedback_ids 에 정수가 아닌 값이 있습니다.", 400)
        try:
            n = int(v)
        except (TypeError, ValueError):
            return app._json_error("feedback_ids 에 정수가 아닌 값이 있습니다.", 400)
        if n <= 0:
            return app._json_error("feedback_ids 는 양의 정수여야 합니다.", 400)
        if n in seen:
            continue
        seen.add(n)
        ids.append(n)
    ids.sort()   # 결정적 lock 순서(deadlock 회피).
    approved_by = str((account or {}).get("username") or "") or None
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)   # connect 는 connect_timeout 로 bounded(루프 blocking 무한 아님).
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)

    def _run_bulk(conn):
        # 블로킹 배치 — threadpool 에서 실행. conn 은 이 스레드에서만 순차 사용(동시 접근 없음).
        from modules import kb_glossary as _kg
        try:
            # FOR UPDATE 무한 대기 방어(_pg_connect 는 lock/statement timeout 미설정) —
            # 경합 lock 은 5s 후 실패→롤백→500(재시도 가능)로 fail-fast. 트랜잭션 로컬.
            _lc = conn.cursor()
            try:
                _lc.execute("SET LOCAL lock_timeout = '5s'")
            finally:
                _lc.close()
            out = _kg.bulk_promote_enum_feedback(conn, ids, approved_by=approved_by)
            conn.commit()
            return out
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        results = await asyncio.get_running_loop().run_in_executor(None, _run_bulk, pg)
    except Exception:
        logging.getLogger(__name__).warning("admin_bulk_promote_enum_feedback 실패 ids=%s", ids, exc_info=True)
        return app._json_error("ENUM 일괄 승급 실패", 500)
    promoted = [r for r in results if r.get("enum_id") is not None]
    skipped_ids = [r["feedback_id"] for r in results if r.get("enum_id") is None]
    _metadata_audit(request, account, action="enum.feedback.bulk_promote",
                    resource_id=None,
                    change_json={"requested": ids, "promoted_count": len(promoted),
                                 "skipped_ids": skipped_ids})
    return JSONResponse({"ok": True, "promoted_count": len(promoted),
                         "skipped_ids": skipped_ids, "results": results})

@router.get("/api/admin/metadata/tables")
def admin_list_table_desc(request: Request, account=Depends(app.require_permission('metadata.table.read'))) -> JSONResponse:
    """테이블 설명 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    inherited_rows: list = []
    inherited_failed = False
    try:
        rows = _km.list_table_desc_admin(pg, scope_key)
        inherited_rows, inherited_failed = _load_inherited(
            pg, scope_key, _km.list_global_table_desc_for_scope, "테이블 설명")
    except Exception:
        logging.getLogger(__name__).warning("admin_list_table_desc 조회 실패", exc_info=True)
        return app._json_error("테이블 설명 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, description, source, created_at, updated_at)
    def _item(r, inherited):
        return {
            "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
            "table_name": str(r[3] or ""), "description": str(r[4] or ""), "source": str(r[5] or ""),
            "created_at": _metadata_iso(r[6]), "updated_at": _metadata_iso(r[7]),
            "inherited": bool(inherited),
        }
    items = _with_inherited(rows, inherited_rows, _item)
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key,
                         "inherited_count": len(inherited_rows),
                         "inherited_error": inherited_failed})

@router.post("/api/admin/metadata/tables")
async def admin_create_table_desc(request: Request, account=Depends(app.require_permission('metadata.table.create'))) -> JSONResponse:
    """테이블 설명 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, description, schema_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    table_name, e = _metadata_str_field(data, "table_name")
    if e:
        return e
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    schema_name, e = _metadata_str_field(data, "schema_name", required=False)
    if e:
        return e
    source = "manual" if str(data.get("source") or "").strip().lower() != "bootstrap" else "bootstrap"
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _km.upsert_table_desc(pg, scope_key, table_name, description,
                              schema_name=schema_name, source=source,
                              created_by=str((account or {}).get("username") or "") or None)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_table_desc 실패", exc_info=True)
        return app._json_error("테이블 설명 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="table_desc.create",
                    resource_id=f"{scope_key}:{schema_name}.{table_name}",
                    change_json={"scope_key": scope_key, "schema_name": schema_name,
                                 "table_name": table_name, "source": source})
    return JSONResponse({"ok": True, "scope_key": scope_key, "table_name": table_name})

@router.put("/api/admin/metadata/tables/{desc_id}")
async def admin_update_table_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.table.update'))) -> JSONResponse:
    """테이블 설명 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, description, schema_name?, table_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    # key 컬럼(schema/table)은 선택 — 둘 다 주어질 때만 key 수정(부분 제공 거부).
    has_schema = "schema_name" in data
    has_table = "table_name" in data
    schema_name = table_name = None
    if has_table:
        table_name, e = _metadata_str_field(data, "table_name")
        if e:
            return e
        schema_name, e = _metadata_str_field(data, "schema_name", required=False)
        if e:
            return e
    elif has_schema:
        return app._json_error("table_name 없이 schema_name 만 수정할 수 없습니다.", 400)
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.update_table_desc(pg, int(desc_id), scope_key, description,
                                         schema_name=schema_name, table_name=table_name)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 테이블 설명을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 (스키마/테이블)의 설명이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_table_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("테이블 설명 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="table_desc.update",
                    resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id)})

@router.delete("/api/admin/metadata/tables/{desc_id}")
def admin_delete_table_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.table.delete'))) -> JSONResponse:
    """테이블 설명 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.delete_table_desc(pg, int(desc_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_table_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("테이블 설명 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="table_desc.delete",
                        resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/columns")
def admin_list_column_desc(request: Request, account=Depends(app.require_permission('metadata.column.read'))) -> JSONResponse:
    """컬럼 설명 목록 — 단일 scope. 권한 kb.ingest.manual. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    inherited_rows: list = []
    inherited_failed = False
    try:
        rows = _km.list_column_desc_admin(pg, scope_key)
        inherited_rows, inherited_failed = _load_inherited(
            pg, scope_key, _km.list_global_column_desc_for_scope, "컬럼 설명")
    except Exception:
        logging.getLogger(__name__).warning("admin_list_column_desc 조회 실패", exc_info=True)
        return app._json_error("컬럼 설명 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, schema_name, table_name, column_name, description, source, created_at, updated_at, ordinal)
    def _item(r, inherited):
        return {
            "id": int(r[0]), "scope_key": str(r[1] or ""), "schema_name": str(r[2] or ""),
            "table_name": str(r[3] or ""), "column_name": str(r[4] or ""),
            "description": str(r[5] or ""), "source": str(r[6] or ""),
            "created_at": _metadata_iso(r[7]), "updated_at": _metadata_iso(r[8]),
            "ordinal": (int(r[9]) if len(r) > 9 and r[9] is not None else None),
            "inherited": bool(inherited),
        }
    items = _with_inherited(rows, inherited_rows, _item)
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key,
                         "inherited_count": len(inherited_rows),
                         "inherited_error": inherited_failed})

@router.post("/api/admin/metadata/columns")
async def admin_create_column_desc(request: Request, account=Depends(app.require_permission('metadata.column.create'))) -> JSONResponse:
    """컬럼 설명 생성(upsert). 권한 kb.ingest.manual. body: scope_key, table_name, column_name, description, schema_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    table_name, e = _metadata_str_field(data, "table_name")
    if e:
        return e
    column_name, e = _metadata_str_field(data, "column_name")
    if e:
        return e
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    schema_name, e = _metadata_str_field(data, "schema_name", required=False)
    if e:
        return e
    source = "manual" if str(data.get("source") or "").strip().lower() != "bootstrap" else "bootstrap"
    # feature-0016 graphux5: 실제 스키마 컬럼 순서(1-based). 부트스트랩 저장이 골격(DDL) 순서를 전송.
    ordinal = data.get("ordinal")
    try:
        ordinal = int(ordinal) if ordinal is not None and str(ordinal).strip() != "" else None
    except (TypeError, ValueError):
        ordinal = None
    if ordinal is not None and not (0 < ordinal <= 100000):
        ordinal = None   # 비정상 범위(PG int 초과·음수·0)는 미지정 처리(500 회피)
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        _km.upsert_column_desc(pg, scope_key, table_name, column_name, description,
                               schema_name=schema_name, source=source,
                               created_by=str((account or {}).get("username") or "") or None,
                               ordinal=ordinal)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_create_column_desc 실패", exc_info=True)
        return app._json_error("컬럼 설명 등록 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="column_desc.create",
                    resource_id=f"{scope_key}:{schema_name}.{table_name}.{column_name}",
                    change_json={"scope_key": scope_key, "schema_name": schema_name,
                                 "table_name": table_name, "column_name": column_name, "source": source})
    return JSONResponse({"ok": True, "scope_key": scope_key, "table_name": table_name, "column_name": column_name})

@router.put("/api/admin/metadata/columns/{desc_id}")
async def admin_update_column_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.column.update'))) -> JSONResponse:
    """컬럼 설명 수정(by id, scope 가드). 권한 kb.ingest.manual. body: scope_key, description, schema_name?/table_name?/column_name?."""
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr
    description, e = _metadata_str_field(data, "definition" if "definition" in data else "description")
    if e:
        return e
    has_table = "table_name" in data
    has_column = "column_name" in data
    schema_name = table_name = column_name = None
    if has_table or has_column:
        # key 수정 시 table+column 둘 다 필수(부분 제공 거부).
        table_name, e = _metadata_str_field(data, "table_name")
        if e:
            return e
        column_name, e = _metadata_str_field(data, "column_name")
        if e:
            return e
        schema_name, e = _metadata_str_field(data, "schema_name", required=False)
        if e:
            return e
    # feature-0016 graphux5: ordinal(실제 스키마 컬럼 순서) 선택 수정. 미제공 → 미변경.
    ordinal = data.get("ordinal")
    if ordinal is not None and str(ordinal).strip() != "":
        try:
            ordinal = int(ordinal)
        except (TypeError, ValueError):
            ordinal = None
        if ordinal is not None and not (0 < ordinal <= 100000):
            ordinal = None   # 비정상 범위는 미지정 처리(500 회피)
    else:
        ordinal = None
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.update_column_desc(pg, int(desc_id), scope_key, description,
                                          schema_name=schema_name, table_name=table_name,
                                          column_name=column_name, ordinal=ordinal)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 컬럼 설명을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 (스키마/테이블/컬럼)의 설명이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_column_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("컬럼 설명 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="column_desc.update",
                    resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id)})

@router.delete("/api/admin/metadata/columns/{desc_id}")
def admin_delete_column_desc(desc_id: int, request: Request, account=Depends(app.require_permission('metadata.column.delete'))) -> JSONResponse:
    """컬럼 설명 삭제(by id, scope 가드, 멱등). 권한 kb.ingest.manual. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import kb_metadata as _km
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("메타데이터 저장소(PG) 연결 실패", 503)
    try:
        affected = _km.delete_column_desc(pg, int(desc_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_column_desc 실패 id=%s", desc_id, exc_info=True)
        return app._json_error("컬럼 설명 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="column_desc.delete",
                        resource_id=int(desc_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(desc_id), "deleted": int(affected)})


# ── graph-product-cat (feature-0016 §43): 제품(Products) 단위 카테고리 투영 ──────────────
#   그래프(AGE)는 Postgres `agent_kb` 에 있고 Product↔Datasource SSOT 는 MySQL(`WebProducts`·
#   `WebProductDatasources`)에 있다. AGE 에 Product/Datasource 노드를 물리 저장하는 대신, 투영 API 가
#   **질의시점에 MySQL SSOT 로부터 합성**한다("projection" 원칙 정합 — 마이그레이션·이중 정합 회피).
#   브리지: product → _list_product_datasources → datasource_key → shared.datasources.resolve → scope_key
#   (= 그래프 scope). scope_key 는 그대로 datasource-scoped 그래프(scope_roots/schemas)의 진입 키.
def _product_overview_graph(conn, product_id=None) -> dict:
    """활성 제품(product_id 지정 시 단일) + 바인딩 Datasource 노드 + USES 엣지 합성.

    노드: Product(key=`product:<id>`) · Datasource(key=`ds:<scope_key>`, scope_key 로 drill).
    여러 제품이 같은 datasource 를 공유할 수 있어 Datasource 노드는 dedup(엣지는 각 제품마다)."""
    from shared import datasources as _dsr
    try:
        products = app._list_products(conn)
    except Exception:
        products = []
    if product_id is not None:
        products = [p for p in products if int(p.get("id") or 0) == int(product_id)]
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ds: set[str] = set()
    for p in products:
        pid = int(p.get("id") or 0)
        if pid <= 0:
            continue
        pkey = "product:%d" % pid
        ds_list = p.get("datasources") or []
        nodes.append({
            "label": "Product", "key": pkey,
            "name": p.get("name") or p.get("product_key") or ("제품#%d" % pid),
            "fqn": p.get("product_key") or "", "scope_key": "",
            "product_key": p.get("product_key") or "", "datasource_count": len(ds_list),
        })
        for d in ds_list:
            dsk = d.get("datasource_key")
            if not dsk:
                continue
            try:
                ds = _dsr.resolve(conn, dsk)
            except Exception:
                ds = None
            # read-axis 정렬(§43 리뷰 MAJOR): 그래프 scope 는 admin_datasources 가 노출하는 read 축
            #   `scope_key or key`(DB-등록=엔드포인트 해시, .env 레거시=라벨)여야 drill-down 이 실 그래프와 일치한다.
            #   `_dsr.scope_key(ds)` 는 .env 도 해시로 계산해 read 축(라벨)과 어긋나 빈 그래프를 부른다 — 금지.
            sk = ((ds.get("scope_key") if ds else None) or str(dsk).strip().lower())
            if not sk:
                continue
            dnode = "ds:%s" % sk
            if dnode not in seen_ds:
                seen_ds.add(dnode)
                nodes.append({
                    "label": "Datasource", "key": dnode,
                    "name": (ds.get("name") if ds else None) or dsk,
                    "fqn": sk, "scope_key": sk, "datasource_key": str(dsk).strip().lower(),
                })
            edges.append({
                "id": "uses:%d:%s" % (pid, sk), "type": "USES",
                "source": pkey, "target": dnode, "status": "",
                "data": {"is_primary": bool(d.get("is_primary"))},
            })
    return {"nodes": nodes, "edges": edges}


def _products_for_scope(conn, scope_key) -> list[dict]:
    """그래프 scope(=datasource scope_key)를 사용하는 제품 목록(배너용). common/미지정은 []."""
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == "common":
        return []
    from shared import datasources as _dsr
    try:
        products = app._list_products(conn)
    except Exception:
        return []
    out: list[dict] = []
    for p in products:
        for d in (p.get("datasources") or []):
            dsk = d.get("datasource_key")
            if not dsk:
                continue
            try:
                ds = _dsr.resolve(conn, dsk)
            except Exception:
                ds = None
            # read-axis 정렬(§43 리뷰 MAJOR): _product_overview_graph 와 동일 규약 — scope_key or 라벨.
            rk = ((ds.get("scope_key") if ds else None) or str(dsk).strip().lower())
            if rk == sk:
                out.append({"id": int(p.get("id") or 0), "name": p.get("name") or "",
                            "product_key": p.get("product_key") or ""})
                break
    return out


def _schema_products_for_scope(conn, scope_key) -> dict:
    """§55 A(REQ-20260706 ①): scope 의 스키마(DB)명 → 그 DB 를 접근DB 로 선언한 제품 목록 매핑.

    그래프 뷰 스키마 클러스터의 **제품 카테고리** 데이터 원천. 브리지: scope → (read-axis 규약,
    _products_for_scope 동형) 그 scope 를 쓰는 (product, datasource_key) 쌍 → `WebProductDatabases`
    (ProductId, DatasourceKey, SchemaName — 제품별 접근DB SSOT) → {SchemaName: [{id,name,sort}]}.
    SchemaName 은 effective schema(=MSSQL/MySQL DB명) 규약이라 그래프 Schema 노드 name 과 조인 가능.
    AGE 미저장 — 질의시점 합성(ADR-014 원칙 계승). 실패·미매핑은 {}(프론트 '미분류' 폴백)."""
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == "common":
        return {}
    from shared import datasources as _dsr
    try:
        products = app._list_products(conn)
    except Exception:
        return {}
    prod_ds: list[tuple[dict, str]] = []
    for p in products:
        for d in (p.get("datasources") or []):
            dsk = d.get("datasource_key")
            if not dsk:
                continue
            try:
                ds = _dsr.resolve(conn, dsk)
            except Exception:
                ds = None
            rk = ((ds.get("scope_key") if ds else None) or str(dsk).strip().lower())
            if rk == sk:
                prod_ds.append((p, str(dsk)))
    if not prod_ds:
        return {}
    out: dict[str, list[dict]] = {}
    try:
        cur = conn.cursor()
        try:
            for p, dsk in prod_ds:
                pid = int(p.get("id") or 0)
                if pid <= 0:
                    continue
                cur.execute(
                    "SELECT SchemaName FROM WebProductDatabases "
                    "WHERE ProductId=%s AND DatasourceKey=%s ORDER BY SortOrder, SchemaName",
                    (pid, dsk))
                psort = p.get("sort_order")
                ent = {"id": pid, "name": p.get("name") or p.get("product_key") or ("제품#%d" % pid),
                       "sort": int(psort) if isinstance(psort, (int, float)) else 100}
                for row in cur.fetchall():
                    sch = str(row[0] or "").strip()
                    if not sch:
                        continue
                    lst = out.setdefault(sch, [])
                    if not any(e.get("id") == pid for e in lst):
                        lst.append(dict(ent))
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("_schema_products_for_scope 실패", exc_info=True)
        return {}
    return out


@router.get("/api/admin/metadata/graph")
def admin_metadata_graph(request: Request, account=Depends(app.require_permission('metadata.graph.read')), conn=Depends(app.get_conn)) -> JSONResponse:
    """메타데이터 지식그래프 투영(Apache AGE metadata_kb) — UI(Cytoscape)·검색 공급.

    권한 kb.ingest.manual. 8K 노드 규모라 **전체 덤프 금지** — 모드:
      - 제품:    ?mode=products / ?product=<id> → 제품(카테고리)→Datasource 개요 (MySQL SSOT 합성, graph-product-cat)
      - 이웃:    ?node=<key>&depth=1..3      → 해당 노드 k-hop (cap 적용)
      - 검색:    ?q=<부분일치>[&scope=<ds>]  → 이름/FQN CONTAINS (scope 지정 시 그 datasource 만)
      - 스키마:  ?scope=<ds>&mode=schemas    → Schema 카드 + table_count (graph-initview 경량 진입)
      - 단일스키마: ?scope=<ds>&schema=<key> → 그 스키마의 Table 만 (per-schema lazy, truncated 플래그)
      - 진입:    ?scope=<ds>                 → 그 datasource 의 Schema→Table 서브그래프(하위호환 유지)
    셋 다 없으면 빈 그래프. AGE cutover 전(확장 부재)엔 모듈이 graceful no-op → 빈 결과.
    scope 는 datasource scope_key(예: mssql-06656002eda6) — 각 데이터소스별 그래프 분리.
    """
    q = (request.query_params.get("q") or "").strip()
    node = (request.query_params.get("node") or "").strip()
    scope = (request.query_params.get("scope") or "").strip() or None
    schema = (request.query_params.get("schema") or "").strip()
    mode_param = (request.query_params.get("mode") or "").strip()
    product = (request.query_params.get("product") or "").strip()
    try:
        depth = int(request.query_params.get("depth") or "1")
    except (TypeError, ValueError):
        depth = 1
    depth = max(1, min(depth, 3))
    # graph-cap-audit(사용자 결정 2026-07-29): 종전 기본 50 이 검색 결과를 잘라 "50건 · 상한(검색어를
    #   좁혀보세요)" 를 띄우던 원인이다 — 찾아 놓고 안 보여주는 절단은 최적화가 아니라 오류이며, 목록
    #   렌더 부담은 프론트의 그룹 접기·가상 스크롤이 담당한다. 쿼리 파라미터가 없으면 **모듈 기본값**
    #   (`metadata_graph._SEARCH_CAP` 안전 가드)에 위임한다 — 여기서 숫자를 복제하면 두 곳이 어긋난다.
    _lim_raw = (request.query_params.get("limit") or "").strip()
    try:
        limit = int(_lim_raw) if _lim_raw else None
    except (TypeError, ValueError):
        limit = None

    # graph-product-cat (§43): 제품 카테고리 개요 — MySQL SSOT 합성(PG 불필요, early-return).
    #   product 는 숫자일 때만 단일 제품 트리거(비숫자는 통과 → 일반 dispatch; 리뷰 NIT 방어).
    if mode_param == "products" or product.isdigit():
        pid = int(product) if product.isdigit() else None
        try:
            pdata = _product_overview_graph(conn, product_id=pid)
        except Exception:
            logging.getLogger(__name__).warning("admin_metadata_graph products 조회 실패", exc_info=True)
            return app._json_error("제품 그래프 조회 실패", 503)
        return JSONResponse({
            "nodes": pdata.get("nodes", []), "edges": pdata.get("edges", []),
            "mode": "products", "q": "", "node": "", "scope": product or "", "depth": 1,
            "truncated": False, "products": [],
            "node_count": len(pdata.get("nodes", [])), "edge_count": len(pdata.get("edges", [])),
        })

    from modules import metadata_graph as _mg
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("그래프 저장소(PG) 연결 실패", 503)
    try:
        if node:
            data = _mg.neighborhood(node, depth=depth, conn=pg)
            mode = "neighborhood"
        elif q:
            _sn_kw = {"scope": scope, "conn": pg}
            if limit is not None:
                _sn_kw["limit"] = limit   # 명시 요청만 override — 미지정은 모듈 안전 가드
            data = {"nodes": _mg.search_nodes(q, **_sn_kw), "edges": []}
            mode = "search"
        elif scope and schema:
            data = _mg.schema_tables(scope, schema, conn=pg)
            mode = "schema_tables"
        elif scope and mode_param == "schemas":
            data = _mg.scope_schemas(scope, conn=pg)
            mode = "scope_schemas"
        elif scope:
            data = _mg.scope_roots(scope, conn=pg)
            mode = "scope_roots"
        else:
            data = {"nodes": [], "edges": []}
            mode = "empty"
    except Exception:
        logging.getLogger(__name__).warning("admin_metadata_graph 조회 실패", exc_info=True)
        return app._json_error("그래프 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # graph-product-cat (§43): 진입 모드(scope_roots/schemas)에서만 이 datasource 를 쓰는 제품 목록 첨부(배너용).
    #   neighborhood/search/schema_tables 등 임계경로 모드는 skip(MySQL 왕복 절감).
    scope_products = []
    schema_products = {}
    if scope and mode in ("scope_roots", "scope_schemas"):
        try:
            scope_products = _products_for_scope(conn, scope)
        except Exception:
            scope_products = []
        # §55 A: 스키마(DB)별 제품 매핑 — 프론트 카테고리 그룹(CAT 계층)의 데이터 원천. 실패는 {}(미분류 폴백).
        try:
            schema_products = _schema_products_for_scope(conn, scope)
        except Exception:
            schema_products = {}
    return JSONResponse({
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "mode": mode,
        "q": q, "node": node, "scope": scope or "", "depth": depth,
        "truncated": bool(data.get("truncated", False)),
        # graph-hop-budget(2026-07-28): 절단 위치·규모. 프론트가 "무엇이 잘렸는지" 를 정확히 말해
        #   앵커 직결 목록(1-hop 전량 수집이라 절단과 무관)에 경고를 오귀속하지 않게 한다.
        "truncated_hop": data.get("truncated_hop"),
        "omitted_nodes": int(data.get("omitted_nodes") or 0),
        # 적대리뷰 R2-c: hop 별 신규 노드 수. 프론트가 "선택한 깊이가 결과를 바꿨는가" 를 엣지 존재로
        #   추측하지 않고 확장 실적으로 판정한다(hop 1 관계 엣지에 속아 힌트가 숨던 결함).
        "expanded_hops": list(data.get("expanded_hops") or []),
        "expanded_hop_edges": list(data.get("expanded_hop_edges") or []),
        "products": scope_products,
        "schema_products": schema_products,
        "node_count": len(data.get("nodes", [])), "edge_count": len(data.get("edges", [])),
    })

@router.post("/api/admin/metadata/graph/analyze")
async def admin_metadata_graph_analyze(request: Request, account=Depends(app.require_permission('metadata.graph.analyze'))) -> JSONResponse:
    """그래프 노드 AI 능동 분석 트리거(항목2). 권한 metadata.graph.analyze(graph-analyze-perm 2026-07-14 후 조회 metadata.graph.read 에서 분리된 실행 전용 하위 권한 — LLM 호출·KB 갱신·비용 유발 특권 동작).

    body: {node_key, scope_key?, depth?, node_budget?, prompt?}. run 을 만들고 즉시 202 반환 — 실제
    분석은 insight-worker 백그라운드가 선택 노드에서 관련 노드를 재귀 탐색하며 노드별 수행(부하 분산).
    prompt(ADR-017, 선택 ≤400자): hover 툴팁으로 입력한 사용자 분석 지침 — run 에 저장돼 앵커 토큰
    합류 + LLM user_intent 로 자율 반영된다.
    진행은 GET .../graph/analyze?run_id= 로 폴링, 노드 결과는 GET .../graph/analyze/node?node= 로 조회.
    """
    data = await _metadata_read_json(request)
    node_key = str(data.get("node_key") or data.get("node") or "").strip()
    if not node_key or ":" not in node_key:
        return app._json_error("node_key(그래프 노드 키)는 필수입니다.", 400)
    scope_key = str(data.get("scope_key") or node_key.split(":", 1)[0] or "common").strip().lower()
    depth = data.get("depth")
    node_budget = data.get("node_budget")
    user_prompt = str(data.get("prompt") or "").strip()[:400] or None
    from modules import node_analysis as _na
    res = _na.enqueue_analysis(scope_key, node_key, depth_budget=depth, node_budget=node_budget,
                               requested_by=str((account or {}).get("username") or "") or None,
                               user_prompt=user_prompt)
    if not res.get("ok"):
        reason = res.get("reason") or "분석 시작 실패"
        # fix: 서버측 실패(PG 미가용/disabled/enqueue 실패)는 5xx. 클라 입력 오류만 400(라우트가 이미
        #   node_key 를 검증하므로 'node_key 필수'는 사실상 발생 안 함).
        code = 400 if reason == "node_key 필수" else 503
        return app._json_error(f"AI 능동 분석 시작 실패: {reason}", code)
    _metadata_audit(request, account, action="node_analysis.enqueue", resource_id=node_key,
                    change_json={"scope_key": scope_key, "run_id": res.get("run_id"),
                                 "depth": depth, "node_budget": node_budget,
                                 "reused": res.get("reused", False),
                                 "prompt_len": len(user_prompt or ""),
                                 "prompt_preview": (user_prompt or "")[:120] or None})
    return JSONResponse({"ok": True, "run_id": res.get("run_id"), "status": res.get("status"),
                         "reused": res.get("reused", False), "progress": res.get("progress")},
                        status_code=202)

@router.post("/api/admin/metadata/graph/analyze-schema")
async def admin_metadata_graph_analyze_schema(request: Request, account=Depends(app.require_permission('metadata.graph.analyze'))) -> JSONResponse:
    """DB(스키마) 단위 AI 능동 분석(§53·§55). 권한 metadata.graph.analyze(노드 분석과 동일 실행 권한 — graph-analyze-perm 2026-07-14 후 조회 metadata.graph.read 에서 분리).

    body: {schema_key, scope_key?, prompt?, only_missing?=true, dry_run?}. 스키마 소속 Table·Routine 을
    depth=0 시드로 일괄 enqueue — §55(REQ-20260706 ③): 시드별 직계 컬럼 + per-seed 앵커 게이팅 재귀
    전개(depth=AGENT_NODE_ANALYSIS_SCHEMA_DEPTH, 총예산 min(SCHEMA_RUN_BUDGET_MAX, planned×EXPAND_FACTOR)).
    비용 가드 = only_missing 기본 + AGENT_NODE_ANALYSIS_SCHEMA_CAP(기본 200) + 예산 캡 + 빈약 노드만
    back-refine(REFINE_MAX). dry_run=true 는 run 미생성 — 대상 집계만 반환(프론트 confirm 용).
    진행 폴링은 기존 GET .../graph/analyze?run_id= 재사용(enqueued 는 재귀 전개로 실행 중 증가)."""
    data = await _metadata_read_json(request)
    schema_key = str(data.get("schema_key") or data.get("schema") or "").strip()
    if not schema_key or ":" not in schema_key:
        return app._json_error("schema_key(스키마 노드 키)는 필수입니다.", 400)
    scope_key = str(data.get("scope_key") or schema_key.split(":", 1)[0] or "common").strip().lower()
    user_prompt = str(data.get("prompt") or "").strip()[:400] or None
    only_missing = bool(data.get("only_missing", True))
    dry_run = bool(data.get("dry_run", False))
    from modules import node_analysis as _na
    res = _na.enqueue_schema_analysis(scope_key, schema_key,
                                      requested_by=str((account or {}).get("username") or "") or None,
                                      user_prompt=user_prompt, only_missing=only_missing,
                                      dry_run=dry_run)
    if not res.get("ok"):
        reason = res.get("reason") or "분석 시작 실패"
        code = 400 if reason == "schema_key 필수" else 503
        return app._json_error(f"DB 단위 AI 능동 분석 시작 실패: {reason}", code)
    if not dry_run and res.get("status") in ("running",):
        _metadata_audit(request, account, action="node_analysis.enqueue_schema", resource_id=schema_key,
                        change_json={"scope_key": scope_key, "run_id": res.get("run_id"),
                                     "planned": res.get("planned"), "total_tables": res.get("total_tables"),
                                     "total_routines": res.get("total_routines"),
                                     "missing": res.get("missing"), "capped": res.get("capped", False),
                                     "only_missing": only_missing, "reused": res.get("reused", False),
                                     "prompt_len": len(user_prompt or ""),
                                     "prompt_preview": (user_prompt or "")[:120] or None})
    return JSONResponse({"ok": True, "run_id": res.get("run_id"), "status": res.get("status"),
                         "total_tables": res.get("total_tables"),
                         "total_routines": res.get("total_routines"), "missing": res.get("missing"),
                         "planned": res.get("planned"), "capped": res.get("capped", False),
                         "reused": res.get("reused", False), "progress": res.get("progress"),
                         "reason": res.get("reason")},
                        status_code=200 if dry_run or res.get("status") == "noop" else 202)


@router.post("/api/admin/metadata/graph/analyze/retry")
async def admin_metadata_graph_analyze_retry(request: Request, account=Depends(app.require_permission('metadata.graph.analyze'))) -> JSONResponse:
    """일시 실패로 굳은 노드 분석 잡을 다시 큐에 올린다(analysis-retry-resilience, 2026-07-30).

    권한은 실행 권한 `metadata.graph.analyze` 재사용 — LLM 재호출을 유발하므로 조회 권한으로는 부족하고,
    신규 권한 코드는 만들지 않는다(기존 트리거와 같은 특권 동작).

    body: {run_id?, scope_key?, dry_run?=false, limit?} — `run_id` 또는 `scope_key` 중 최소 하나 필수
    (무제한 전역 회수는 LLM 비용이 예측 불가라 허용하지 않는다). 회수 대상은 일시 실패(transient·상한
    소진)와 0049 이전 레거시 LLM 실패뿐이며, 'verification-cleanup(취소)' 같은 인위적 실패와 영구 실패
    (bad_model/context_length)는 제외된다. dry_run=true 는 대상 수만 반환(프론트 confirm 용).
    """
    data = await _metadata_read_json(request)
    run_id = str(data.get("run_id") or "").strip() or None
    scope_key = str(data.get("scope_key") or "").strip().lower() or None
    if not run_id and not scope_key:
        return app._json_error("run_id 또는 scope_key 중 하나는 필수입니다.", 400)
    dry_run = bool(data.get("dry_run", False))
    try:
        limit = int(data.get("limit") or 500)
    except Exception:
        limit = 500
    from modules import node_analysis as _na
    res = _na.retry_failed_jobs(run_id=run_id, scope_key=scope_key, limit=limit, dry_run=dry_run)
    if not res.get("ok"):
        reason = res.get("reason") or "재시도 실패"
        return app._json_error(f"실패 잡 재시도 실패: {reason}", 503)
    if not dry_run and res.get("retried"):
        _metadata_audit(request, account, action="node_analysis.retry_failed",
                        resource_id=(run_id or scope_key or ""),
                        change_json={"run_id": run_id, "scope_key": scope_key,
                                     "retried": res.get("retried"), "runs": res.get("runs"),
                                     "limit": limit})
    return JSONResponse({"ok": True, "dry_run": bool(res.get("dry_run")),
                         # retried = 이번 실행량(limit 적용) · eligible = 전체 대상(dry_run 만)
                         "retried": res.get("retried", 0), "eligible": res.get("eligible"),
                         "capped": bool(res.get("capped", False)), "runs": res.get("runs", 0),
                         "run_ids": res.get("run_ids") or []})


def _parse_graph_column_key(raw) -> dict | None:
    """그래프 Column 노드 key `<scope>:<schema>.<table>.<column>` 파싱(§55 B curate). 실패 None."""
    k = str(raw or "").strip()
    if ":" not in k:
        return None
    scope, fqn = k.split(":", 1)
    parts = [p for p in fqn.split(".") if p != ""]
    if len(parts) < 2 or not scope:
        return None
    column, table = parts[-1], parts[-2]
    schema = ".".join(parts[:-2])
    return {"scope": scope.strip().lower(), "schema": schema, "table": table, "column": column,
            "table_fqn": (f"{schema}.{table}" if schema else table)}


@router.post("/api/admin/metadata/graph/relationship/curate")
async def admin_metadata_graph_relationship_curate(request: Request,
                                                   account=Depends(app.require_permission('metadata.table.update')),
                                                   conn=Depends(app.get_conn)) -> JSONResponse:
    """§55 B(REQ-20260706 ②): 관계 사람 큐레이션 — trust(신뢰 승격) / break(파단).

    크로스-데이터소스 후보는 프로브 검증이 불가해 source='manual' 승격이 **유일한 신뢰 경로**인데
    (ADR-019), 그 호출자가 미배선이라 영구 candidate(AI 컨텍스트 미주입)로 남던 dead-end 를 해소한다.
    intra-DS 관계에도 동작(운영자 확정/오탐 즉시 파단). 권한 metadata.table.manage(메타데이터 큐레이션 축).

    body: {action: 'trust'|'break', src: <Column key>, tgt: <Column key>} — key 는 그래프 Column 노드
    key(`<scope>:<schema>.<table>.<column>`). trust=upsert(source='manual'→trusted, weight 1.0) + 그래프
    엣지 즉시 투영. break=status 'broken'·weight 0 + 그래프 엣지 즉시 회수. 관계형 SSOT(PG)와 그래프
    (AGE) 동시 정합 — 다음 sync_graph 주기와도 멱등."""
    data = await _metadata_read_json(request)
    action = str(data.get("action") or "").strip().lower()
    if action not in ("trust", "break"):
        return app._json_error("action 은 'trust' 또는 'break' 여야 합니다.", 400)
    src = _parse_graph_column_key(data.get("src"))
    tgt = _parse_graph_column_key(data.get("tgt"))
    if not src or not tgt:
        return app._json_error("src/tgt(그래프 Column 노드 키)는 필수입니다.", 400)
    from modules import metadata_graph as _mg
    from modules import relationships as _rel
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=True)
    except Exception:
        return app._json_error("그래프 저장소(PG) 연결 실패", 503)
    updated = 0
    try:
        cur = pg.cursor()
        try:
            # §55 패널 fix: ds-키 매칭에 ''(레거시 — scope 배선 이전 행, 라이브 실측 scope_key='common'
            # +ds '' 797행) 허용. 정확 매칭만 쓰면 레거시 행에서 UPDATE 0건인데 AGE 엣지만 삭제/승격돼
            # 다음 sync_graph 가 원상복구(부활/강등 flap)한다 — SSOT·그래프 동시 정합이 목적.
            if action == "trust":
                # 기존 행 우선 UPDATE(방향 그대로) — upsert 를 먼저 쓰면 기존 행의 UNIQUE 키(레거시 ''-ds)와
                # 어긋날 때 **중복 행**이 생기고, 원 candidate 가 계속 프로브·파단되며 같은 그래프 엣지를
                # 삭제/신뢰로 뒤집는 flap 이 남는다(패널 MAJOR). 매칭 0건일 때만 신규 manual 행 upsert.
                cur.execute(
                    "UPDATE table_relationships SET status='trusted', weight=1.0, source='manual', "
                    "       confidence=1.0, negative_signals=0, updated_at=now() "
                    "WHERE source_table_fqn=%s AND source_column=%s "
                    "  AND target_table_fqn=%s AND target_column=%s "
                    "  AND (source_datasource_key=%s OR source_datasource_key='') "
                    "  AND (target_datasource_key=%s OR target_datasource_key='')",
                    (src["table_fqn"], src["column"], tgt["table_fqn"], tgt["column"],
                     src["scope"], tgt["scope"]))
                updated = int(cur.rowcount or 0)
                if not updated:
                    ok = _rel.upsert_relationship(
                        pg, src["scope"],
                        src_schema=src["schema"], src_table=src["table"], src_column=src["column"],
                        tgt_schema=tgt["schema"], tgt_table=tgt["table"], tgt_column=tgt["column"],
                        source="manual", datasource_key=src["scope"],
                        source_datasource_key=src["scope"], target_datasource_key=tgt["scope"])
                    if not ok:
                        return app._json_error("관계 승격 실패(관계 저장소)", 503)
                    updated = 1
                _mg.sync_relationship(cur, src["scope"], src["table_fqn"], src["column"],
                                      tgt["table_fqn"], tgt["column"], source="manual",
                                      confidence=1.0, weight=1.0, status="trusted",
                                      tgt_scope=tgt["scope"])
            else:
                # break: 방향 그대로 + 역방향 행 모두 파단(추론기가 어느 방향으로 저장했든 오탐 회수).
                cur.execute(
                    "UPDATE table_relationships SET status='broken', weight=0.0, updated_at=now() "
                    "WHERE (source_table_fqn=%s AND source_column=%s "
                    "       AND target_table_fqn=%s AND target_column=%s "
                    "       AND (source_datasource_key=%s OR source_datasource_key='') "
                    "       AND (target_datasource_key=%s OR target_datasource_key='')) "
                    "   OR (source_table_fqn=%s AND source_column=%s "
                    "       AND target_table_fqn=%s AND target_column=%s "
                    "       AND (source_datasource_key=%s OR source_datasource_key='') "
                    "       AND (target_datasource_key=%s OR target_datasource_key=''))",
                    (src["table_fqn"], src["column"], tgt["table_fqn"], tgt["column"],
                     src["scope"], tgt["scope"],
                     tgt["table_fqn"], tgt["column"], src["table_fqn"], src["column"],
                     tgt["scope"], src["scope"]))
                updated = int(cur.rowcount or 0)
                _mg.delete_relationship(cur, src["scope"], src["table_fqn"], src["column"],
                                        tgt["table_fqn"], tgt["column"], tgt_scope=tgt["scope"])
                _mg.delete_relationship(cur, tgt["scope"], tgt["table_fqn"], tgt["column"],
                                        src["table_fqn"], src["column"], tgt_scope=src["scope"])
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("relationship_curate 실패", exc_info=True)
        return app._json_error("관계 큐레이션 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="graph.relationship.curate",
                    resource_id=f"{data.get('src')}->{data.get('tgt')}",
                    change_json={"action": action, "updated": updated,
                                 "cross_ds": src["scope"] != tgt["scope"]})
    return JSONResponse({"ok": True, "action": action, "updated": updated,
                         "cross_ds": src["scope"] != tgt["scope"]})

@router.get("/api/admin/metadata/graph/analyze")
def admin_metadata_graph_analyze_status(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """분석 run 진행률 폴링(항목2). 권한 metadata.graph.read(결과·진행 상태 조회 — 실행은 graph.analyze). ?run_id=<hex>.
    반환 {status, enqueued, done, failed, done_keys[...]} — 프론트가 done_keys 로 분석 마커 표시."""
    run_id = (request.query_params.get("run_id") or "").strip()
    if not run_id:
        return app._json_error("run_id 는 필수입니다.", 400)
    from modules import node_analysis as _na
    st = _na.get_run_status(run_id)
    if st is None:
        return app._json_error("run 을 찾을 수 없습니다.", 404)
    return JSONResponse(st)

@router.get("/api/admin/metadata/graph/analyze/node")
def admin_metadata_graph_analyze_node(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """노드의 최신 분석 상태/결과(상세 패널, 항목2). 권한 metadata.graph.read(결과 조회 — 실행은 graph.analyze). ?node=<key>[&scope=<ds>].
    반환 {status:'none'|'pending'|'running'|'done'|'failed', analysis:{summary,relationships,usage,caveats}}."""
    node = (request.query_params.get("node") or "").strip()
    if not node:
        return app._json_error("node 는 필수입니다.", 400)
    scope = (request.query_params.get("scope") or "").strip() \
        or (node.split(":", 1)[0] if ":" in node else "common")
    from modules import node_analysis as _na
    res = _na.get_node_analysis(scope, node)
    if res is None:
        return app._json_error("조회 실패", 503)
    return JSONResponse(res)

@router.get("/api/admin/metadata/graph/analyze/status")
def admin_metadata_graph_analyze_status_bulk(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """스코프 내 노드들의 분석 상태 **일괄** 집계(그래프 초기 렌더 마커용, 항목1). 권한 metadata.graph.read(상태 조회 — 실행은 graph.analyze).
    ?scope=<ds> — 그 datasource 스코프의 완료/진행중 node_key 집합을 반환한다. 프론트는 그래프 로드/검색/확장
    직후 이 결과로 마커(보라 '분석됨'·주황 '분석중')와 역할 표식(node-role-viz)을 **노드 클릭 없이** 즉시 적용한다.
    반환 {done_keys:[...], running_keys:[...], roles:{node_key:role}}. PG 미가용 시 빈 집합(마커 없음 — 그래프는 정상)."""
    scope = (request.query_params.get("scope") or "").strip() or "common"
    from modules import node_analysis as _na
    res = _na.get_scope_analysis_status(scope)
    if res is None:
        # PG 미가용/예외 — 그래프 자체는 렌더되어야 하므로 빈 집합으로 graceful(마커만 생략).
        return JSONResponse({"done_keys": [], "running_keys": [], "roles": {}, "unavailable": True})
    return JSONResponse({"done_keys": res.get("done_keys", []), "running_keys": res.get("running_keys", []),
                         "roles": res.get("roles", {})})

@router.get("/api/admin/metadata/graph/columns")
def admin_metadata_graph_columns(request: Request, account=Depends(app.require_permission('metadata.graph.read'))) -> JSONResponse:
    """더블클릭 컬럼 즉석 introspection(항목3). 권한 metadata.graph.read(그래프 조회 — 실행은 graph.analyze). ?node=<table key `scope:schema.table`>.

    그래프 투영(SSOT=column_descriptions)에 Column 노드가 없어(큐레이션/분석 미진행) 더블클릭해도
    컬럼이 안 펼쳐지던 문제를 해소한다. 그래프에 컬럼이 없으면 **데이터소스 information_schema 를 즉석
    조회**해 Column 노드 + HAS_COLUMN 엣지로 반환한다(read-only, 그래프 미저장). 실패 시 introspected=False
    + reason 으로 명확 피드백(silent no-op 금지)."""
    node = (request.query_params.get("node") or "").strip()
    if not node or ":" not in node:
        return app._json_error("node(테이블 키 `scope:schema.table`)는 필수입니다.", 400)
    scope_key = node.split(":", 1)[0]
    fqn = node.split(":", 1)[1]
    parts = [p for p in fqn.split(".") if p]
    if len(parts) < 2:
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "테이블 노드가 아니거나 스키마.테이블 형식이 아닙니다."})
    schema = parts[0]
    table = parts[-1]
    import re as _re
    _ident = r"^[A-Za-z0-9_$\- ]+$"
    if not _re.match(_ident, schema) or not _re.match(_ident, table):
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "식별자에 허용되지 않는 문자가 있어 조회를 건너뜁니다."})
    # graph-perf-bg: 성공 introspection 캐시 히트면 ds 해석·라이브 DB 연결·information_schema 조회 전량 우회.
    _cached = _graph_columns_cache_get(scope_key, fqn)
    if _cached is not None:
        return JSONResponse(_cached)
    ds, derr = app._graph_resolve_ds_by_scope(scope_key)
    if derr:
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node, "reason": derr})
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    conn = None
    engine = ""
    rows = []
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL: fqn 첫 세그먼트가 DB(카탈로그) — 그 DB 에 연결 후 테이블명으로 컬럼 조회(스키마 무관).
            conn = _db.connect(datasource=ds, database=schema, autocommit=True)
            cur = conn.cursor()
            cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                        f"WHERE TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION")
            rows = cur.fetchall()
            cur.close()
        else:
            # MySQL: schema == database. information_schema 는 서버 전역 → 무-database 연결 + WHERE 필터.
            conn = _db.connect(datasource=ds, autocommit=True)
            dialect = _dialects.active()
            cur = conn.cursor()
            cur.execute(dialect.describe_columns(schema, table))  # SELECT COLUMN_NAME, COLUMN_TYPE, ...
            rows = cur.fetchall()
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("graph columns introspect 실패 node=%s", node, exc_info=True)
        return JSONResponse({"nodes": [], "edges": [], "introspected": False, "node": node,
                             "reason": "데이터소스 컬럼 조회 실패(권한/연결 확인, 또는 AI 능동 분석 사용)."})
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass
    nodes, edges = [], []
    ord_i = 0
    # graph-cap-audit(사용자 결정 2026-07-29): 종전 `rows[:500]` 은 컬럼이 500 을 넘는 와이드 테이블에서
    #   나머지를 조용히 버렸다 — 컬럼 목록은 데이터 자체라 잘라내면 오류다(렌더 부담은 프론트 컬럼
    #   LOD §61·뷰포트 컬링 §65 가 담당). 전량 반환한다.
    for r in rows:
        cname = str(r[0]) if r and r[0] is not None else ""
        if not cname:
            continue
        ctype = str(r[1]) if len(r) > 1 and r[1] is not None else ""
        ckey = f"{scope_key}:{fqn}.{cname}"
        ord_i += 1   # describe_columns 는 ORDINAL_POSITION 순 → 인덱스가 실제 스키마 컬럼 순서(ERD 카드 정렬키)
        nodes.append({"label": "Column", "key": ckey, "name": cname,
                      "fqn": f"{fqn}.{cname}", "description": ctype, "source": "introspect", "ordinal": ord_i})
        edges.append({"source": node, "target": ckey, "type": "HAS_COLUMN",
                      "cardinality": None, "edge_source": "introspect"})
    payload = {"nodes": nodes, "edges": edges, "introspected": True,
               "count": len(nodes), "engine": engine, "node": node}
    if nodes:   # graph-perf-bg: 컬럼이 실제 조회된 성공만 캐시(빈/실패 결과는 재시도 보장 위해 미캐시)
        _graph_columns_cache_put(scope_key, fqn, payload)
    return JSONResponse(payload)

@router.get("/api/admin/metadata/samples")
def admin_list_samples(request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 목록 — 단일 scope. 권한 kb.sample.curate. ?scope_key= (기본 'common')."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "common")
    if serr:
        return serr
    from modules import sample_queries as _sq
    from shared.db import _pg_connect_ro
    try:
        pg = _pg_connect_ro()
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    inherited_rows: list = []
    inherited_failed = False
    try:
        rows = _sq.list_samples_admin(pg, scope_key)
        inherited_rows, inherited_failed = _load_inherited(
            pg, scope_key, _sq.list_global_samples_for_scope, "샘플쿼리")
    except Exception:
        logging.getLogger(__name__).warning("admin_list_samples 조회 실패", exc_info=True)
        return app._json_error("샘플 목록 조회 실패", 503)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    # row: (id, scope_key, nl_question, sql, domain, weight, approved, status, source_type, created_at, updated_at)
    def _item(r, inherited):
        return {
            "id": int(r[0]), "scope_key": str(r[1] or ""), "nl_question": str(r[2] or ""),
            "sql": str(r[3] or ""), "domain": str(r[4] or ""), "weight": int(r[5] or 0),
            "approved": bool(r[6]), "status": str(r[7] or ""), "source_type": str(r[8] or ""),
            "created_at": _metadata_iso(r[9]), "updated_at": _metadata_iso(r[10]),
            "inherited": bool(inherited),
        }
    items = _with_inherited(rows, inherited_rows, _item)
    return JSONResponse({"items": items, "count": len(items), "scope_key": scope_key,
                         "inherited_count": len(inherited_rows),
                         "inherited_error": inherited_failed})

@router.put("/api/admin/metadata/samples/{sample_id}")
async def admin_update_sample(sample_id: int, request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 수정(by id, scope 가드). 권한 kb.sample.curate. body: scope_key, nl_question?, sql?, domain?, weight?, approved?.

    하이브리드 C 임베딩: nl_question 변경 시에만 kb_retrieval._embed_query_vector 동기 시도 →
    성공이면 embedding 갱신(status='active'), 실패면 embedding 무효화(status='stale', 재임베딩 대기).
    nl 미변경 시 embedding touch 안 함. weight 1~1000 clamp. nl 중복(UNIQUE) → 409.
    """
    data = await _metadata_read_json(request)
    scope_key, serr = _metadata_check_scope(data.get("scope_key") or "")
    if serr:
        return serr

    # 부분 수정 — 본문에 키가 있을 때만 해당 필드 변경. 전부 미제공이면 400(no-op 거부).
    kwargs: dict = {}
    if "nl_question" in data:
        nlq, e = _metadata_str_field(data, "nl_question")
        if e:
            return e
        kwargs["nl_question"] = nlq
    if "sql" in data:
        sql_v = str(data.get("sql") or "").strip()
        if not sql_v:
            return app._json_error("sql 은 비울 수 없습니다.", 400)
        if len(sql_v) > 8000:  # 샘플 SQL 길이 cap(프롬프트 예시 전용 — 비대 방지)
            return app._json_error("sql 이 너무 깁니다 (최대 8000자).", 400)
        kwargs["sql"] = sql_v
    if "domain" in data:
        kwargs["domain"] = str(data.get("domain") or "").strip()
    if "weight" in data:
        try:
            w = int(data.get("weight"))
        except Exception:
            return app._json_error("weight 는 정수여야 합니다.", 400)
        kwargs["weight"] = max(app._SAMPLE_WEIGHT_MIN, min(app._SAMPLE_WEIGHT_MAX, w))  # 1~1000 clamp
    if "approved" in data:
        kwargs["approved"] = bool(data.get("approved"))
    if not kwargs:
        return app._json_error("수정할 필드가 없습니다.", 400)

    # 하이브리드 C: nl_question 변경 시에만 임베딩 동기 시도. 실패→None(코어가 status='stale').
    embed_changed = "nl_question" in kwargs
    embed_status = None  # 응답 진단용: 'active' | 'stale' | None(미변경)
    if embed_changed:
        vec = None
        try:
            from modules.kb_retrieval import _embed_query_vector
            vec = _embed_query_vector(kwargs["nl_question"])  # dim=1024(titan-embed v2)
        except Exception:
            vec = None
        kwargs["embedding"] = vec if vec else None
        embed_status = "active" if vec else "stale"

    from modules import sample_queries as _sq
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        affected = _sq.update_sample(pg, int(sample_id), scope_key, **kwargs)
        if affected <= 0:
            pg.rollback()
            return app._json_error("해당 샘플을 찾을 수 없습니다.", 404)
        pg.commit()
    except Exception as exc:
        try:
            pg.rollback()
        except Exception:
            pass
        if exc.__class__.__name__ in ("UniqueViolation", "IntegrityError"):
            return app._json_error("동일 질문(nl_question)의 샘플이 이미 있습니다.", 409)
        logging.getLogger(__name__).warning("admin_update_sample 실패 id=%s", sample_id, exc_info=True)
        return app._json_error("샘플 수정 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    _metadata_audit(request, account, action="sample.update",
                    resource_id=int(sample_id),
                    change_json={"scope_key": scope_key, "fields": sorted(k for k in kwargs if k != "embedding"),
                                 "embedding": embed_status})
    return JSONResponse({"ok": True, "id": int(sample_id), "embedding_status": embed_status})

@router.delete("/api/admin/metadata/samples/{sample_id}")
def admin_delete_sample(sample_id: int, request: Request, account=Depends(app.require_permission('kb.sample.curate'))) -> JSONResponse:
    """샘플 삭제(by id, scope 가드, 멱등). 권한 kb.sample.curate. ?scope_key= 필수."""
    scope_key, serr = _metadata_check_scope(request.query_params.get("scope_key") or "")
    if serr:
        return serr
    from modules import sample_queries as _sq
    from shared.db import _pg_connect
    try:
        pg = _pg_connect(autocommit=False)
    except Exception:
        return app._json_error("샘플 저장소(PG) 연결 실패", 503)
    try:
        affected = _sq.delete_sample(pg, int(sample_id), scope_key)
        pg.commit()
    except Exception:
        try:
            pg.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning("admin_delete_sample 실패 id=%s", sample_id, exc_info=True)
        return app._json_error("샘플 삭제 실패", 500)
    finally:
        try:
            pg.close()
        except Exception:
            pass
    if affected > 0:
        _metadata_audit(request, account, action="sample.delete",
                        resource_id=int(sample_id), change_json={"scope_key": scope_key})
    return JSONResponse({"ok": True, "id": int(sample_id), "deleted": int(affected)})

@router.get("/api/admin/metadata/scopes")
def admin_metadata_scopes(request: Request, account=Depends(app.get_current_account)) -> JSONResponse:
    """메타데이터 콘솔의 스코프 선택 옵션 — **제품 목록** + 공용(common). (metadata-product-scope)

    종전 콘솔은 `/api/admin/datasources` 로 스코프 옵션을 채워 관리자에게 데이터소스를 고르게 했다.
    사용자·메타데이터 관리자의 작업 범위 인식 단위는 제품이므로 본 엔드포인트가 그 축을 제공한다.
    응답 항목의 `database_count` 는 그 제품의 접근DB 수(부트스트랩 골격 대상 규모 힌트).
    RBAC: 세션 계정이면 조회 가능(제품 이름·키는 작업 화면 제품 선택기에도 이미 노출되는 정보).
    """
    scopes = [{
        "scope_key": "common",
        "product_id": 0,
        "product_key": "",
        "name": "공용 (모든 제품)",
        "database_count": 0,
        "is_common": True,
    }]
    for e in _product_scope_catalog():
        scopes.append({
            "scope_key": e["scope_key"],
            "product_id": e["product_id"],
            "product_key": e["product_key"],
            "name": e["name"],
            "database_count": len(e.get("databases") or []),
            "is_common": False,
        })
    return JSONResponse({"scopes": scopes})

@router.get("/api/admin/metadata/bootstrap/schemas")
def admin_bootstrap_schemas(request: Request, account=Depends(app.require_permission('metadata.table.manage'))) -> JSONResponse:
    """선택 **제품**의 골격 단위(unit) 목록. 권한 metadata.table.manage. ?scope_key=product.<key>

    metadata-product-scope: 단위 목록의 1차 원천은 그 제품의 **접근DB**(`WebProductDatabases`)다 —
    서버 전체 스키마를 나열하던 종전 datasource 축은 제품 경계 밖 DB 까지 콘솔에 노출했고(공유
    datasource 에서 특히), 관리자가 어느 DB 가 자기 제품 것인지 알 수 없었다. 접근DB 가 선언되지
    않은 제품만 라이브 introspection 으로 폴백한다(엔진별 unit 차이는 아래 그대로).

    폴백 시 엔진별 unit(metadata-table-desc-fix):
      - **MySQL**: schema == database. 시스템 스키마 + __invalid_default_db__ 센티넬 제외.
      - **MSSQL**: server > database > schema 4계층. unit = **database**(시스템 DB 제외).
    응답: {schemas:[...], scope_key, datasource, engine, unit_kind:"database"|"schema", source:"product-databases"|"introspect"}
    """
    scope_raw = str(request.query_params.get("scope_key") or request.query_params.get("scope") or "").strip()
    if not scope_raw:
        return app._json_error("scope_key(제품) 는 필수입니다.", 400)
    _entry = _resolve_scope_product(scope_raw)
    if _entry is None:
        # 'common' 또는 미등록/비활성 제품 — 골격 대상이 아니다(축이 제품이므로 404 가 정확한 의미).
        return app._json_error("해당 제품을 찾을 수 없거나 골격 대상이 아닙니다.", 404)
    if not _entry.get("databases_ok", True):
        return app._json_error("제품 접근 DB 목록을 조회할 수 없습니다. 잠시 후 다시 시도하세요.", 503)
    # 1차: 제품 접근DB — 라이브 연결 없이 즉답(대규모 MSSQL 서버 목록 조회 회피).
    units_declared = _scope_database_units(scope_raw)
    if units_declared:
        return JSONResponse({
            "schemas": [u["schema"] for u in units_declared],
            "scope_key": str(scope_raw or "").strip().lower(),
            "datasource": "",
            "engine": "",
            "unit_kind": "database",
            "source": "product-databases",
        })
    # 2차 폴백: 접근DB 미선언 제품 → 제품의 primary datasource 를 introspect.
    #   호출자 지정 `datasource` override 는 제거(제품 경계 우회 차단, codex review P1).
    ds_key = _scope_datasource_for_schema(scope_raw, "")
    ds, scope_key, derr = app._bootstrap_resolve_datasource(ds_key)
    if derr:
        return derr
    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL unit = database. 시스템 DB(master/model/msdb/tempdb) 제외.
            dialect = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect.system_databases()}
            units = [str(n) for n in (_db.list_server_databases(ds) or [])
                     if str(n).strip().lower() not in sys_db]
            unit_kind = "database"
        else:
            conn = _db.connect(datasource=ds, autocommit=True)  # RO 유저(데이터소스 좌표는 least-priv)
            raw = _schema.load_known_schemas(conn) or []  # dialect-aware(schema.py:788)
            units = [str(n) for n in raw
                     if str(n).strip().lower() not in app._BOOTSTRAP_MYSQL_SYS_SCHEMAS]
            unit_kind = "schema"
    except Exception:
        logging.getLogger(__name__).warning("admin_bootstrap_schemas 실패 ds=%s", scope_key, exc_info=True)
        return app._json_error("스키마 조회 실패", 503)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)  # 요청 컨텍스트 dialect 리셋
        except Exception:
            pass
    return JSONResponse({"schemas": units, "scope_key": str(scope_raw or "").strip().lower(),
                         "datasource": scope_key, "engine": engine, "unit_kind": unit_kind,
                         "source": "introspect"})

@router.post("/api/admin/metadata/bootstrap")
async def admin_bootstrap(request: Request, account=Depends(app.require_permission('metadata.table.create', 'metadata.table.update'))) -> JSONResponse:
    """선택 **제품**의 접근DB(schema) 테이블/컬럼 골격(미영속). 권한 metadata.table.*. body: scope_key, schema.

    metadata-product-scope: 물리 datasource 는 body 의 `scope_key`(제품) + `schema` 로 **서버가만**
    해소한다(`_scope_datasource_for_schema`). 호출자 지정 `datasource` override 는 제거했다 —
    override 를 남기면 임의 제품 scope 로 아무 datasource/schema 나 introspect 할 수 있어 제품
    경계가 무력화된다(codex review P1).

    골격은 저장하지 않는다 — UI 가 설명 빈칸을 prefill, 사람이 채워 tables/columns POST(source='bootstrap')
    로 저장한다. dialect-aware: MSSQL 은 set_active_datasource(engine=) 로 활성화 후 dialect.describe_columns
    경유(MySQL 백틱 하드코딩 load_schema_metadata 우회). 자동 1행 샘플/list_indexes 호출 안 함(부하/PII).
    """
    data = await _metadata_read_json(request)
    _bs_schema = str(data.get("schema") or "").strip()
    _bs_scope = str(data.get("scope_key") or "").strip()
    if not _bs_scope:
        return app._json_error("scope_key(제품) 는 필수입니다.", 400)
    _bs_entry = _resolve_scope_product(_bs_scope)
    if _bs_entry is None:
        return app._json_error("해당 제품을 찾을 수 없거나 골격 대상이 아닙니다.", 404)
    if not _bs_entry.get("databases_ok", True):
        return app._json_error("제품 접근 DB 목록을 조회할 수 없습니다. 잠시 후 다시 시도하세요.", 503)
    _bs_ds_key = _scope_datasource_for_schema(_bs_scope, _bs_schema)
    if not _bs_ds_key:
        # 제품은 실재하는데 해소 실패 = 그 제품의 접근DB allowlist 밖 schema (제품 경계 강제).
        return app._json_error("해당 제품의 접근 DB 가 아닙니다.", 404)
    ds, scope_key, derr = app._bootstrap_resolve_datasource(_bs_ds_key)
    if derr:
        return derr
    schema_name = _bs_schema
    if not schema_name:
        return app._json_error("schema 는 필수입니다.", 400)
    if len(schema_name) > app._METADATA_FIELD_CAPS["schema_name"]:
        return app._json_error("schema 가 너무 깁니다.", 400)

    from shared import config as _cfg
    from shared import db as _db
    from modules import dialects as _dialects
    from modules import schema as _schema
    from modules.tools import _safe_ident as _safe_ident_fn
    # REV B1(BLOCKER) — SQLi 차단: dialect.describe_schema_tables 는 schema 를 f-string 으로 SQL 에
    # 삽입(dialects.py `WHERE … = '{schema}'`)하므로, 구조화 도구(tools.py)와 동일하게
    # ① _safe_ident 로 인용 구분자 제거 + ② allowlist 멤버십으로만 통과시킨다.
    safe_schema = _safe_ident_fn(schema_name)
    conn = None
    try:
        engine = app._bootstrap_activate_dialect(ds, scope_key)
        if engine == "mssql":
            # MSSQL: schema 파라미터는 **database**. 시스템 DB 제외 allowlist 로 검증 후 해당 DB 로
            # 직접 연결(database 미지정 시 중립 tempdb 폴백 → 임시테이블 회귀)하고, 그 DB 안의 비시스템
            # SQL 스키마 테이블을 평탄 수집한다(저장 schema_name = database).
            dialect = _dialects.active()
            sys_db = {str(n).strip().lower() for n in dialect.system_databases()}
            # metadata-product-scope: allowlist 검증은 **대소문자 무관**, 연결은 **서버 원본 케이스**로.
            #   제품 접근DB(WebProductDatabases.SchemaName)는 §58 lower 계약으로 저장되는데 서버
            #   catalog 는 원본 케이스(`FHGame1`)를 유지한다 — 케이스-정확 비교면 정상 DB 가 404 로
            #   거부된다(codex review P2). `_metadata_introspect_table` 의 lower→원본 매핑과 동형.
            db_map = {str(n).strip().lower(): str(n) for n in (_db.list_server_databases(ds) or [])
                      if str(n).strip().lower() not in sys_db}
            real_db = db_map.get(str(safe_schema).strip().lower())
            if not real_db:
                return app._json_error("알 수 없는 database 이거나 접근할 수 없습니다.", 404)
            conn = _db.connect(datasource=ds, database=real_db, autocommit=True)
            tables = app._bootstrap_collect_skeleton_mssql(conn, _dialects, real_db)
        else:
            conn = _db.connect(datasource=ds, autocommit=True)
            known_schemas = set(_schema.load_known_schemas(conn) or [])
            if safe_schema not in known_schemas:
                return app._json_error("알 수 없는 schema 이거나 접근할 수 없습니다.", 404)
            tables = app._bootstrap_collect_skeleton(conn, _dialects, safe_schema)
    except Exception:
        logging.getLogger(__name__).warning("admin_bootstrap 실패 ds=%s schema=%s", scope_key, schema_name, exc_info=True)
        return app._json_error("스키마 골격 조회 실패", 503)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _cfg.set_active_datasource(None)
        except Exception:
            pass
    return JSONResponse({"tables": tables, "datasource": scope_key, "schema": schema_name})

@router.post("/api/admin/metadata/{sub}/suggest")
async def admin_metadata_suggest(sub: str, request: Request) -> JSONResponse:
    """메타데이터 단건 AI 자동완성 — 식별 필드 → 설명/정의/라벨/질문 1건(영속 안 함).

    RBAC 는 서브뷰별(glossary/enums/tables/columns=kb.ingest.manual, samples=kb.sample.curate).
    tables/columns 는 datasource 지정 시 실제 스키마(컬럼)에 best-effort grounding.
    """
    sub = str(sub or "").strip().lower()
    target = app._METADATA_SUGGEST_TARGET.get(sub)
    if not target:
        return app._json_error("알 수 없는 메타데이터 서브뷰입니다.", 404)
    perm = _METADATA_SUGGEST_PERM.get(sub, "metadata.table.update")
    account, error = _metadata_resolve_account_perm(request, perm)
    if error:
        return error
    # per-account rate-limit(429) — LLM dispatch 비용 DoS 방어(fix-with-ai 와 동일 패턴). RBAC 통과 후 검사.
    if not app._search_rate_limit_check(
        int(account.get("id") or 0),
        max_per_min=app._METADATA_AI_RATE_PER_MIN,
        scope=app.RATE_SCOPE_METADATA_AI,
    ):
        return app._json_rate_limited(
            "자동완성 요청이 너무 잦습니다.",
            app._rate_limit_retry_after(int(account.get("id") or 0), app.RATE_SCOPE_METADATA_AI),
        )
    data = await _metadata_read_json(request)
    fields: dict = {}
    for k in ("term", "schema_name", "table_name", "column_name", "code", "sql", "nl_question"):
        if k in data:
            v, ferr = _metadata_str_field(data, k, required=False)
            if ferr:
                return ferr
            fields[k] = v
    for req_k in app._METADATA_SUGGEST_REQUIRES.get(sub, []):
        if not fields.get(req_k):
            return app._json_error(f"자동완성하려면 먼저 '{req_k}' 를 입력하세요.", 400)
    grounding = None
    if sub in ("tables", "columns"):
        # metadata-product-scope: 프론트는 제품 스코프만 보낸다 — 물리 datasource 는 (제품, 접근DB)
        # 바인딩에서 **서버가만** 해소한다. 호출자 지정 override 는 제거(부트스트랩과 동일 근거 —
        # 임의 제품 scope 로 아무 datasource 나 introspect 하는 경계 우회 차단, codex review P1).
        # 해소 실패(경계 밖 schema·카탈로그 미가용)는 ungrounded 로 degrade — 일반 설명으로 진행.
        _sch = fields.get("schema_name") or ""
        _ds_key = _scope_datasource_for_schema(data.get("scope_key"), _sch)
        grounding = _metadata_introspect_table(_ds_key, _sch, fields.get("table_name") or "")
    messages = _metadata_suggest_messages(sub, fields, grounding)
    # feature-0043 TASK-20260831T100000 — 조립 **뒤**, 호출 **앞** 한 지점에서만 위임한다.
    #
    # 프롬프트 조립부(스키마 grounding · 제품 바인딩 · 필드 제약)가 이 기능의 자산이므로
    # 그것을 그대로 넘긴다. 여기서 새로 쓰면 같은 기능이 경로에 따라 다르게 산출되고,
    # 그때부터 한쪽은 반드시 낡는다(P0-P·P0-U 가 겪은 형태).
    #
    # `None` = 위임 대상 아님(게이트 열림 / 러너 자격 없음) → 종전 경로 그대로. 게이트가
    # 닫혀 있으면 그 경로가 `feature_blocked_message` 로 안내하므로 여기서 중복하지 않는다.
    _delegated = _console_jobs.maybe_delegate(
        request, account, job_kind="metadata_suggest", messages=messages,
        payload={"sub": sub, "target": target})
    if _delegated is not None:
        return _delegated
    text, meta, lerr = await app._metadata_llm_complete(messages, task="summary")
    if lerr:
        return lerr
    cap = app._METADATA_FIELD_CAPS.get(target)
    suggestion = text or ""
    if cap and len(suggestion) > cap:
        suggestion = suggestion[:cap].rstrip()
    return JSONResponse({
        "target": target,
        "suggestion": suggestion,
        "meta": {**(meta or {}), "grounded": bool(grounding and grounding.get("columns"))},
    })

@router.post("/api/admin/metadata/bootstrap/describe")
async def admin_metadata_bootstrap_describe(request: Request, account=Depends(app.require_permission('metadata.table.update'))) -> JSONResponse:
    """부트스트랩 일괄 AI 자동완성 — 골격(테이블/컬럼)의 설명을 1 LLM 호출로 생성(영속 안 함).

    프론트가 청크 단위(≤_METADATA_BULK_MAX_TABLES)로 호출해 진행률을 표면화한다. RBAC kb.ingest.manual.
    골격 식별자는 프롬프트 텍스트로만 사용(SQL 미사용)하므로 클라 제공 골격을 cap 후 신뢰한다.
    반환 results 는 {schema_name, table_name[, column_name], description} 리스트 — 프론트가 입력란에 채움.
    """
    # per-account rate-limit(429) — 청크 일괄 LLM dispatch 비용 DoS 방어. RBAC 통과 후 검사.
    if not app._search_rate_limit_check(
        int(account.get("id") or 0),
        max_per_min=app._METADATA_AI_RATE_PER_MIN,
        scope=app.RATE_SCOPE_METADATA_AI,
    ):
        return app._json_rate_limited(
            "일괄 자동완성 요청이 너무 잦습니다.",
            app._rate_limit_retry_after(int(account.get("id") or 0), app.RATE_SCOPE_METADATA_AI),
        )
    data = await _metadata_read_json(request)
    mode = str(data.get("mode") or "tables").strip().lower()
    if mode not in ("tables", "columns"):
        return app._json_error("mode 는 tables/columns 중 하나여야 합니다.", 400)
    raw_tables = data.get("tables")
    if not isinstance(raw_tables, list) or not raw_tables:
        return app._json_error("tables 골격이 필요합니다.", 400)
    if len(raw_tables) > app._METADATA_BULK_MAX_TABLES:
        return app._json_error(f"1회 호출은 테이블 {app._METADATA_BULK_MAX_TABLES}개 이하만 처리합니다.", 400)
    tables: list = []
    for t in raw_tables:
        if not isinstance(t, dict):
            continue
        tname = str(t.get("table_name") or "").strip()[:128]
        if not tname:
            continue
        sname = str(t.get("schema_name") or "").strip()[:128]
        cols: list = []
        for c in (t.get("columns") or [])[:app._BOOTSTRAP_MAX_COLS_PER_TABLE]:
            if not isinstance(c, dict):
                continue
            cn = str(c.get("column_name") or "").strip()[:128]
            if cn:
                cols.append({"column_name": cn, "data_type": str(c.get("data_type") or "").strip()[:64]})
        tables.append({"schema_name": sname, "table_name": tname, "columns": cols})
    if not tables:
        return app._json_error("유효한 테이블이 없습니다.", 400)
    messages = _metadata_bulk_describe_messages(mode, tables)
    # 위임 seam — 단건과 같은 자리(조립 뒤 · 호출 앞). 일괄은 대상 표를 payload 에 굳힌다:
    # 회수 시점에 "이 답이 어느 테이블들에 대한 것인가" 를 되물을 수 없기 때문이다.
    _delegated = _console_jobs.maybe_delegate(
        request, account, job_kind="metadata_bulk", messages=messages,
        payload={"mode": mode, "tables": tables})
    if _delegated is not None:
        return _delegated
    text, meta, lerr = await app._metadata_llm_complete(messages, task="prompt_gen", temperature=0.2)
    if lerr:
        return lerr
    parsed = _metadata_parse_json_object(text)
    if parsed is None:
        return app._json_error("AI 응답을 해석할 수 없습니다. 다시 시도하세요.", 502)
    results = _metadata_bulk_shape_results(mode, tables, parsed)
    return JSONResponse({"mode": mode, "results": results, "meta": {**(meta or {}), "count": len(results)}})


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (3종). app 전역은 app.X 동적 참조. ====

def _glossary_feedback_iso(v):
    return app._metadata_iso(v)

def _graph_resolve_ds_by_scope(scope_key: str):
    """scope_key → datasource dict. read(agent_core.set_active_datasource)와 동일 해소:
    ds.get('scope_key') or ds.get('key') or 라벨. 반환 (ds, None) 또는 (None, reason:str)."""
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == "common":
        return None, "데이터소스 스코프가 아닙니다(common)."
    from shared import datasources as _dsr
    mem = None
    try:
        mem = app._connect_memory()
    except Exception:
        mem = None
    try:
        ds_map = _dsr.all_datasources(mem) or {}
    except Exception:
        ds_map = {}
    finally:
        if mem is not None:
            try:
                mem.close()
            except Exception:
                pass
    for label, ds in ds_map.items():
        cand = str((ds.get("scope_key") or ds.get("key") or label) or "").strip().lower()
        if cand == sk:
            return ds, None
    return None, "해당 스코프의 데이터소스를 찾을 수 없습니다."

def _bootstrap_collect_skeleton_mssql(conn, _dialects, db_name: str) -> list:
    """MSSQL 골격 — 연결된 database 의 비시스템 SQL 스키마(dbo 등) 테이블을 평탄 수집(metadata-table-desc-fix).

    server > database > schema > table 4계층을 테이블 설명 모델의 (scope_key=datasource, schema_name,
    table_name) 3-키에 매핑한다 — **저장 schema_name = database(db_name)** (사용자 결정). describe_columns 는
    실제 SQL 스키마로 introspect 하되 산출 schema_name 은 db_name 으로 통일한다. 동일 table_name 이 복수 SQL
    스키마에 있으면 최초 1건만 남긴다(DB명 평탄화 한계 — 대부분 dbo 단일). 시스템 SQL 스키마(db_datareader 등
    고정 역할 + sys/information_schema)는 dialect.system_schemas() 로 제외. cap: 테이블 500 / 컬럼 200.
    """
    from modules.tools import _safe_ident as _safe_ident_fn
    from modules import schema as _schema
    from shared.config import normalize_db_label as _norm_db_label   # §58: store label lower 계약
    dialect = _dialects.active()
    sys_schema = {str(n).strip().lower() for n in dialect.system_schemas()}
    real_schemas = [s for s in (_schema.load_known_schemas(conn) or [])
                    if str(s).strip().lower() not in sys_schema]
    out: list = []
    seen: set = set()
    for sql_schema in real_schemas:
        if len(out) >= app._BOOTSTRAP_MAX_TABLES:
            break
        safe_sql_schema = _safe_ident_fn(sql_schema)
        tnames: list = []
        cur = conn.cursor()
        try:
            cur.execute(dialect.describe_schema_tables(safe_sql_schema))
            for row in (cur.fetchall() or []):
                if row and row[0]:
                    tnames.append(str(row[0]))
        finally:
            cur.close()
        for tname in tnames:
            if len(out) >= app._BOOTSTRAP_MAX_TABLES:
                break
            key = tname.strip().lower()
            if key in seen:
                continue  # DB명 평탄화: 동명 테이블(타 SQL 스키마)은 최초 1건만
            seen.add(key)
            safe_tname = _safe_ident_fn(tname)
            cols: list = []
            ccur = conn.cursor()
            try:
                ccur.execute(dialect.describe_columns(safe_sql_schema, safe_tname))
                for crow in (ccur.fetchall() or []):
                    if not crow or not crow[0]:
                        continue
                    cols.append({"column_name": str(crow[0]),
                                 "data_type": str(crow[1] or "").lower()})
                    if len(cols) >= app._BOOTSTRAP_MAX_COLS_PER_TABLE:
                        break
            except Exception:
                cols = []  # 단일 테이블 introspection 실패는 건너뜀(부분 골격 허용)
            finally:
                ccur.close()
            # §58(테이블축 케이스 정합): MSSQL 저장 schema_name(=DB명 라벨)은 set_active_database
            #   (TASK-0220)·routine backfill(§56 RC5)과 동일한 lower 계약 — sys.databases 원본 케이스를
            #   무가공 저장하면 cadence(lower) 축과 케이스-변형 이중 적재(라이브 실측 'AccountDB' 33행
            #   + AGE 중복 스키마 카드)가 생긴다. MSSQL 전용 함수라 MySQL 케이스 보존은 자동 충족.
            #   (질의 식별자는 sql_schema/tname — db_name 은 연결 바인딩 후 질의에 미사용.)
            out.append({"schema_name": _norm_db_label(db_name) or db_name,
                        "table_name": tname, "columns": cols})
    return out


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (3종). app 전역은 app.X 동적 참조. ====

def _bootstrap_collect_skeleton(conn, _dialects, schema_name: str) -> list:
    """dialect-aware 골격 수집 — {schema_name, table_name, columns:[{column_name, data_type}]}.

    테이블 목록은 dialect.describe_schema_tables(1쿼리), 각 테이블 컬럼은 dialect.describe_columns
    (row[0]=name, row[1]=type). MySQL/MSSQL 둘 다 동일 인터페이스(dialects.py). 자동 샘플/인덱스
    조회는 하지 않는다(부하/PII). cap: 테이블 500 / 테이블당 컬럼 200.
    """
    from modules.tools import _safe_ident as _safe_ident_fn
    dialect = _dialects.active()
    cur = conn.cursor()
    table_names: list[str] = []
    try:
        cur.execute(dialect.describe_schema_tables(schema_name))
        for row in (cur.fetchall() or []):
            if row and row[0]:
                table_names.append(str(row[0]))
            if len(table_names) >= app._BOOTSTRAP_MAX_TABLES:
                break
    finally:
        cur.close()

    out: list = []
    for tname in table_names:
        # REV B1 방어심층: tname 은 introspection 산출(DB 제어)이나 구조화 도구와 동일하게 _safe_ident 통과.
        safe_tname = _safe_ident_fn(tname)
        cols: list = []
        ccur = conn.cursor()
        try:
            ccur.execute(dialect.describe_columns(schema_name, safe_tname))
            for crow in (ccur.fetchall() or []):
                if not crow or not crow[0]:
                    continue
                cols.append({"column_name": str(crow[0]),
                             "data_type": str(crow[1] or "").lower()})
                if len(cols) >= app._BOOTSTRAP_MAX_COLS_PER_TABLE:
                    break
        except Exception:
            cols = []  # 단일 테이블 introspection 실패는 건너뜀(부분 골격 허용)
        finally:
            ccur.close()
        out.append({"schema_name": schema_name, "table_name": tname, "columns": cols})
    return out

def _bootstrap_resolve_datasource(ds_key: str):
    """datasource key → (ds_dict, scope_key, None) 또는 (None, None, JSONResponse).

    all_datasources(mem) 로 검증(미존재 404). scope_key 화이트리스트도 함께 통과시킨다.
    """
    key = str(ds_key or "").strip().lower()
    if not key:
        return None, None, app._json_error("datasource 는 필수입니다.", 400)
    if key == "common":
        return None, None, app._json_error("'common' 은 introspection 대상이 아닙니다.", 400)
    from shared import datasources as _dsr
    mem = None
    try:
        mem = app._connect_memory()
    except Exception:
        mem = None
    try:
        ds_map = _dsr.all_datasources(mem) or {}
    except Exception:
        ds_map = {}
    finally:
        if mem is not None:
            try:
                mem.close()
            except Exception:
                pass
    ds = ds_map.get(key)
    if not ds:
        return None, None, app._json_error("해당 datasource 를 찾을 수 없습니다.", 404)
    return ds, key, None

def _bootstrap_activate_dialect(ds: dict, scope_key: str):
    """introspection 전에 활성 dialect 를 설정(MSSQL 백틱 폴백 오류 방지). 끝나면 호출측이 리셋."""
    from shared import config as _cfg
    engine = str((ds or {}).get("engine") or "mysql").strip().lower()
    default_db = (ds or {}).get("default_db")
    _cfg.set_active_datasource(scope_key, engine=engine, default_db=default_db)
    return engine


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (4종). ====

_METADATA_FIELD_CAPS = {
    # 입력 길이 cap — KB 본문 비대화/UI 깨짐/저장소 남용 방어. PG 컬럼은 text 라 DB 강제는 없으니 web 가 cap.
    "scope_key": 64, "role_key": 64, "term": 200, "definition": 4000,
    "schema_name": 128, "table_name": 128, "column_name": 128, "code": 256, "label": 1000,
    # ITEM-11 Phase 2: 테이블/컬럼 설명·샘플 필드 cap. description 은 definition 과 동일(4000).
    "description": 4000, "nl_question": 2000, "domain": 64,
    # samples 자동완성 입력 — SQL 본문은 _metadata_suggest_messages 에서 프롬프트에 raw 삽입되므로
    # 입력 cap 으로 거대 프롬프트/토큰·비용 폭주를 차단(다른 식별 필드와 동일하게 _metadata_str_field 가 강제).
    "sql": 8000,
}

# 자동완성 대상 필드(서브뷰 → 생성할 설명 필드) — 프론트가 이 키에 결과를 채운다.
_METADATA_SUGGEST_TARGET = {
    "glossary": "definition",
    "enums": "label",
    "tables": "description",
    "columns": "description",
    "samples": "nl_question",
}

# 자동완성에 필요한 최소 식별 입력(없으면 400) — 빈 식별자로 날조 생성 방지.
_METADATA_SUGGEST_REQUIRES = {
    "glossary": ["term"],
    "enums": ["table_name", "column_name", "code"],
    "tables": ["table_name"],
    "columns": ["table_name", "column_name"],
    "samples": ["sql"],
}

# 서버측 서브뷰별 RBAC — admin.js _METADATA_SUBTAB_PERM 과 동치. graph-panel-perms(task4): 기능별 세부 권한으로 분리.
# perm-atomic-split(2026-07-15): 서브탭 진입(가시성) 게이트는 조회(read) 단위 — 묶음 manage 는 함의로 커버.
_METADATA_SUBTAB_PERM_SERVER = {
    "glossary": "metadata.glossary.read",
    "enums": "metadata.enum.read",
    "tables": "metadata.table.read",
    "columns": "metadata.column.read",
    "samples": "kb.sample.curate",
}

# perm-atomic-split: AI 자동완성(suggest)은 편집 보조 작동(LLM 비용 유발) — 조회가 아닌 수정(update)
# 단위로 게이트(samples 는 검수 단일 단위 유지). 서브탭 가시성 맵과 분리(조회만으론 LLM 비용 유발 불가).
_METADATA_SUGGEST_PERM = {
    "glossary": "metadata.glossary.update",
    "enums": "metadata.enum.update",
    "tables": "metadata.table.update",
    "columns": "metadata.column.update",
    "samples": "kb.sample.curate",
}
