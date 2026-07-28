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

import time
import app

INCLUDE_ORDER = 210  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


# ITEM-10 routers-p11 이동분.
def _autonomous_generate_product_prompt(product_id: int) -> dict:
    """제품 1건의 프롬프트를 무인 자동완성·저장하고 1회성 마커를 기록한다.

    호출 전 조건(프롬프트 미입력 + 분석률>=임계 + 마커 미설정)은 sweep 이 검사하지만, 저장
    직전 마커 행을 `SELECT ... FOR UPDATE` 로 잠그고 '마커 미설정 + 프롬프트 미입력'을 재검사한다
    (LLM 호출(수십초) 중 수동 입력/경합 보호 — TOCTOU). `app._connect_memory` 는 autocommit=True 라
    부분 commit 위험이 있어, 저장 동안만 `autocommit=False` 로 전환해 upsert+마커+audit 를 **단일
    tx** 로 commit 한다(부분 실패 시 rollback → 마커/프롬프트 정합 = 1회성 불변식 보호), finally 환원.

    반환: {status, product_id, ...}.
      status ∈ {ok, skip_present, skip_marked, no_llm, no_body, error}.
    """
    log = logging.getLogger(__name__)

    # 1) 조립 (request-less). 제품 부재/LLM 클라이언트 부재면 skip(마커 미설정 → 다음 cycle 재시도).
    error, ctx = app._assemble_product_prompt_llm_request(int(product_id))
    if error is not None:
        code = int(getattr(error, "status_code", 0) or 0)
        return {
            "status": "no_llm" if code == 503 else "error",
            "product_id": product_id,
            "reason": f"assemble:{code}",
        }

    # 2) LLM 호출 (동기 — sweep 은 daemon thread 컨텍스트라 이벤트 루프 블로킹 없음).
    try:
        _aiops_t0 = time.perf_counter_ns()
        resp = ctx["openai_client"].chat.completions.create(**ctx["create_kwargs"])
        # AI 운영 관제 계측(TASK-AIOPS): daemon thread 라 그대로 기록(이벤트 루프 무영향).
        # system actor → conversation_id=None 명시(cfg 전역 race 차단).
        try:
            from modules.llm import _record_llm_usage
            _record_llm_usage(
                str(ctx.get("llm_model") or ""), "prompt_gen", resp,
                conversation_id=None,
                latency_ms=int((time.perf_counter_ns() - _aiops_t0) // 1_000_000),
            )
        except Exception:
            pass
        choice = resp.choices[0]
        generated = (choice.message.content or "").strip()
        truncated = getattr(choice, "finish_reason", None) == "length"
    except Exception as exc:  # noqa: BLE001 — 어떤 LLM 오류든 skip(다음 cycle 재시도)
        log.warning("auto_prompt LLM 생성 실패 product_id=%s err=%r", product_id, exc)
        return {"status": "error", "product_id": product_id, "reason": "llm_failed"}

    if not generated:
        return {"status": "no_body", "product_id": product_id, "reason": "empty"}
    if truncated:
        log.warning(
            "auto_prompt 본문 잘림(finish_reason=length) product_id=%s model=%s — 그대로 저장",
            product_id, ctx.get("llm_model"),
        )

    # 3) 저장 — 마커 행 FOR UPDATE 잠금 + 재검사 후 upsert+마커+audit 를 단일 명시 tx 로.
    conn = app._connect_memory()
    try:
        conn.autocommit = False  # app._connect_memory 기본 autocommit=True → 부분 commit 방지(B1).
        cur = conn.cursor()
        cur.execute(
            "SELECT AutoPromptGeneratedAt FROM WebProducts WHERE Id = %s FOR UPDATE",
            (int(product_id),),
        )
        mrow = cur.fetchone()
        cur.close()
        if mrow is None:
            conn.rollback()
            return {"status": "error", "product_id": product_id, "reason": "product_gone"}
        if mrow[0] is not None:
            conn.rollback()
            return {"status": "skip_marked", "product_id": product_id}
        if app._product_prompt_present(conn, product_id):
            conn.rollback()
            return {"status": "skip_present", "product_id": product_id}

        app._upsert_system_prompt(
            conn,
            scope="product",
            content=generated,
            product_id=int(product_id),
            updated_by_account_id=None,  # system 주체
        )
        cur2 = conn.cursor()
        cur2.execute(
            "UPDATE WebProducts SET AutoPromptGeneratedAt = UTC_TIMESTAMP() WHERE Id = %s",
            (int(product_id),),
        )
        cur2.close()
        # audit (system actor) — 같은 tx, commit 시 함께 기록. 실패해도 본 흐름 유지.
        try:
            app.record_audit_event(
                conn,
                actor={"actor_type": "system"},
                action="admin.product.prompt.autogenerate",
                resource_type="product",
                resource_id=str(product_id),
                change_json={
                    "trigger": "insight_coverage_threshold",
                    "threshold": app._AUTO_PROMPT_COVERAGE_THRESHOLD,
                    "content_len": len(generated),
                    "truncated": truncated,
                    "grounded": bool(ctx.get("meta_base", {}).get("grounded")),
                },
            )
        except Exception as aexc:  # noqa: BLE001
            log.warning("auto_prompt audit 기록 실패(무시) product_id=%s err=%r", product_id, aexc)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        log.warning("auto_prompt 저장 실패 product_id=%s err=%r", product_id, exc)
        return {"status": "error", "product_id": product_id, "reason": "save_failed"}
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
        conn.close()

    log.info(
        "auto_prompt 자동완성 저장 완료 product_id=%s content_len=%s (threshold=%s%%)",
        product_id, len(generated), app._AUTO_PROMPT_COVERAGE_THRESHOLD,
    )
    return {"status": "ok", "product_id": product_id, "content_len": len(generated)}


# ITEM-10 routers-p9: 제품 인사이트 계산 헬퍼 이동(app.X 동적 — coverage 는 setattr 1× 패치 대상이나 클러스터 내부 호출 0 = 관통 표면 없음).
def _compute_product_db_insights(conn, product: dict, datasource_key=None) -> dict:
    """제품의 한 datasource scope 에서 insight-worker 가 DB(catalog)별로 파악한 내용을 모은다 (TASK-0242).

    반환: {ok, reason, scope, engine, datasource_key, worker{alive,age_sec,status}, by_db{<db_lower>:{...}}}.
    by_db[<db_lower>] = {db, domain, description, detail_text, analyzed_schema, analyzed_tables, analyzed_objects}.
    """
    pid = int(product.get("id") or 0)
    out = {
        "ok": False, "reason": "", "scope": None, "engine": "mysql",
        "datasource_key": None, "worker": app._insight_worker_liveness(conn), "by_db": {},
    }
    # 편집 대상(펼친) datasource 로 scope 해석 (멀티 datasource). 미지정=primary/legacy.
    chosen = (str(datasource_key).strip().lower() if datasource_key else "") or (product.get("datasource_key") or None)
    resolved = app._resolve_product_insight_scope(conn, {"id": pid, "datasource_key": chosen})
    if not resolved["ok"]:
        out["reason"] = resolved["reason"]
        return out
    scope = resolved["scope"]
    allow_null = resolved["allow_null"]
    engine = (resolved.get("engine") or "mysql").strip().lower()
    out["scope"] = scope
    out["engine"] = engine
    out["datasource_key"] = chosen or None

    # REV-20260612-0242 MINOR: PG 연결을 try/finally 로 닫아 예외 경로 누수 차단(기존 coverage 패턴 개선).
    #  방어적 LIMIT — 한 datasource scope 의 schema+table 통찰은 현실적으로 수백 단위. ORDER BY 로 결정적 절단
    #  (schema 가 table 보다 먼저 와 DB 노드 통찰이 우선 보존).
    pg = None
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
        pgc = pg.cursor()
        cond = "(o.datasource_key = %s" + (" OR o.datasource_key IS NULL" if allow_null else "") + ")"
        pgc.execute(
            f"""
            SELECT o.object_type, o.schema_name, o.table_name,
                   o.category_domain, COALESCE(t.text_content, ''), o.object_key
            FROM public.rag_objects o
            LEFT JOIN public.texts t ON t.text_hash = o.text_hash
            WHERE o.conversation_id = %s AND o.scope_key = %s
              AND o.object_type IN ('schema','table')
              AND {cond}
            ORDER BY o.object_type, o.schema_name, o.table_name
            LIMIT 5000
            """,
            ["__global__", "common", scope],
        )
        rows = pgc.fetchall() or []
    except Exception as exc:
        out["reason"] = "PG 통찰 조회 실패"
        logging.getLogger("app").warning("db_insights pg fail pid=%s err=%r", pid, exc)
        return out
    finally:
        if pg is not None:
            try:
                pg.close()
            except Exception:
                pass

    # DB(catalog) 단위 집계. TASK-0243: 키를 schema_name 이 아니라 object_key 에서 파싱한 catalog 로 —
    #  MSSQL 은 schema_name=dbo(SQL스키마)라 등록 DB(catalog)와 차원이 달라 schema_name 으로 묶으면
    #  전부 'dbo' 한 바구니가 되어 등록 DB 행/picker 매칭이 빗나간다. MySQL 은 catalog==schema_name(무변경).
    by: dict = {}
    for otype, sname, tname, cat_domain, text, okey in rows:
        # 그룹핑 키 결정: MSSQL 만 object_key 의 catalog 파싱(schema_name=dbo 차원 문제), MySQL/기타는
        # schema_name 직접 사용 — db==schema==catalog 라 TASK-0242 와 byte-identical(무회귀 보장, object_key
        # 파싱을 MySQL 에 적용해 생길 수 있는 이론적 엣지[DB명 내 '.']까지 원천 차단).
        if engine == "mssql":
            cat = app._db_catalog_from_object_key(okey, engine, otype)
            if cat is None:
                # bare(default_db, catalog 미인코딩) MSSQL 통찰 — 등록 catalog 에 귀속 불가 → 표시 대상 아님.
                continue
        else:
            cat = str(sname or "").strip()
        db = str(cat).strip()
        dbl = db.lower()
        if not dbl:
            continue
        ent = by.setdefault(dbl, {
            "db": db, "domain": None, "schema_text": None,
            "tables": [], "analyzed_schema": False, "analyzed_tables": 0,
        })
        dom = (str(cat_domain).strip() if cat_domain else "") or None
        txt = str(text or "").strip()
        if otype == "schema":
            ent["analyzed_schema"] = True
            if dom and not ent["domain"]:
                ent["domain"] = dom
            if txt:
                ent["schema_text"] = txt
        elif otype == "table" and tname:
            ent["analyzed_tables"] += 1
            ent["tables"].append({"table": str(tname).strip(), "domain": dom, "text": txt})
            if dom and not ent["domain"]:
                ent["domain"] = dom

    by_db: dict = {}
    for dbl, ent in by.items():
        desc, detail = app._compose_db_insight_text(ent)
        by_db[dbl] = {
            "db": ent["db"],
            "domain": ent["domain"],
            "description": desc,
            "detail_text": detail,
            "analyzed_schema": ent["analyzed_schema"],
            "analyzed_tables": ent["analyzed_tables"],
            "analyzed_objects": ent["analyzed_tables"] + (1 if ent["analyzed_schema"] else 0),
        }
    out["ok"] = True
    out["by_db"] = by_db
    return out

def _compute_product_insight_coverage(conn, product: dict) -> dict:
    """한 제품의 insight-worker 객체 분석 완료율 산출 (TASK-0223).

    반환: {product_id, pct, analyzed_objects, total_objects, per_db[], measurable, reason, engine}.
    measurable=False 는 측정 불가(데이터소스 해석/연결 실패 등) — UI 가 "측정 불가" 로 graceful 표시.
    """
    pid = int(product.get("id") or 0)
    base = {
        "product_id": pid, "pct": None, "analyzed_objects": 0, "total_objects": 0,
        "per_db": [], "measurable": False, "reason": "", "engine": "mysql",
    }
    db_rows = [r for r in app._list_product_databases(conn, pid) if r.get("schema_name")]
    if not db_rows:
        base["reason"] = "접근 가능 데이터베이스 없음(미바인딩)"
        base["measurable"] = True  # 측정됨 — 객체 0
        return base

    from shared import db as _db
    from shared.db import _pg_connect

    # ── TASK-0249: 멀티 datasource(1:N) 인식 ──
    # 각 접근 DB 는 자기 datasource(WebProductDatabases.DatasourceKey, 미설정 시 제품 primary)에 산다.
    # 이전 구현은 제품 primary 하나로 모든 DB 를 질의해, 타 서버에 사는 DB 가 0 테이블(0/0)로 잘못
    # 표기됐다(예: 제품의 dbgame 이 player 서버에 있는데 auth 서버에 질의). datasource_key 별로
    # 그룹핑해 각 그룹을 자기 좌표로 질의하고 결과를 합산한다. (분자 scope·분모 라이브 카탈로그를
    # 그룹마다 일치시켜 db-insights 와 같은 datasource 차원을 본다.)
    primary_dskey = product.get("datasource_key")
    order = [r["schema_name"] for r in db_rows]   # 노출 순서 보존(프런트 1:1 매칭)
    groups: dict = {}   # effective datasource_key -> [db_name,...]
    for r in db_rows:
        eff = r.get("datasource_key") or primary_dskey
        groups.setdefault(eff, []).append(r["schema_name"])

    # PG 통찰 연결은 그룹 간 재사용(그룹마다 scope 만 바꿔 조회). 실패 시 전역 측정 불가.
    try:
        pg = _pg_connect()
    except Exception as exc:
        base["reason"] = "PG 통찰 조회 실패"
        logging.getLogger("app").warning("insight_coverage pg connect fail pid=%s err=%r", pid, exc)
        return base

    def _analyzed_sets_for_scope(scope: str, allow_null: bool):
        """rag_objects 통찰 보유 객체 집합 (해당 datasource scope). 반환 (tables:set, schemas:set)."""
        analyzed_tables = set()   # {(schema_lower, table_lower)}
        analyzed_schemas = set()  # {schema_lower}
        pgc = pg.cursor()
        cond = "(datasource_key = %s" + (" OR datasource_key IS NULL" if allow_null else "") + ")"
        # insight-worker 의 schema/table 통찰은 전역 fact 라 conversation_id=GLOBAL_CONVERSATION_ID(`__global__`)
        # 로 저장된다(워커 런타임 conv `__insight_worker__` 가 아니라). scope_key='common' 은 rag scope.
        pgc.execute(
            f"""
            SELECT object_type, schema_name, table_name
            FROM public.rag_objects
            WHERE conversation_id = %s AND scope_key = %s
              AND object_type IN ('schema','table')
              AND {cond}
            """,
            ["__global__", "common", scope],
        )
        for otype, sname, tname in (pgc.fetchall() or []):
            s = str(sname or "").strip().lower()
            if not s:
                continue
            if otype == "table" and tname:
                analyzed_tables.add((s, str(tname).strip().lower()))
            elif otype == "schema":
                analyzed_schemas.add(s)
        pgc.close()
        return analyzed_tables, analyzed_schemas

    per_db_by_name: dict = {}   # db -> per_db row
    engines_seen: list = []
    default_db_seen = None
    resolved_any = False
    pg_failed = False
    try:
        for dskey, dbs in groups.items():
            resolved = app._resolve_product_insight_scope(conn, {"id": pid, "datasource_key": dskey})
            if not resolved["ok"]:
                # 이 datasource 만 해석 불가 — 해당 DB 들만 연결 불가로 표기(타 그룹 무영향).
                for db in dbs:
                    per_db_by_name[db] = {
                        "db": db, "connected": False, "schema_analyzed": False,
                        "tables_total": 0, "tables_analyzed": 0,
                        "note": resolved.get("reason") or "데이터소스 해석 불가",
                    }
                continue
            resolved_any = True
            coords = resolved["coords"]
            engine = resolved["engine"]
            scope = resolved["scope"]
            allow_null = resolved["allow_null"]
            engines_seen.append(engine)
            if default_db_seen is None:
                default_db_seen = resolved.get("default_db")

            okssrf, _ssrf_reason, pin = app._ssrf_check_host(coords.get("host"))
            if not okssrf:
                for db in dbs:
                    per_db_by_name[db] = {
                        "db": db, "connected": False, "schema_analyzed": False,
                        "tables_total": 0, "tables_analyzed": 0,
                        "note": "데이터소스 호스트 차단(SSRF)",
                    }
                continue
            coords_pinned = {**coords, "host": pin}

            # ── 분모: 라이브 카탈로그 (schema, table) — 이 그룹의 datasource 좌표로 ──
            db_tables: dict = {}
            if engine == "mssql":
                # MSSQL: 접근DB=catalog(database) 마다 별도 연결(DB 컨텍스트가 DB별로 다름).
                # per-DB 연결 격리 — RO 로그인이 일부 DB 에만 GRANT 된 경우, 한 DB 연결 실패가
                # 전체를 오염시키지 않도록 실패 DB 만 connected=False + note 로 표기한다.
                for db in dbs:
                    try:
                        pairs = set(_db.list_information_schema_tables(coords_pinned, database=db, timeout=5))
                        db_tables[db] = {"pairs": pairs, "connected": True, "note": ""}
                    except Exception as exc:
                        db_tables[db] = {
                            "pairs": set(), "connected": False,
                            "note": "연결 불가(RO 권한/도달 — 데이터소스 자격증명·DB GRANT 확인)",
                        }
                        logging.getLogger("app").info(
                            "insight_coverage mssql db conn fail pid=%s db=%s err=%r", pid, db, exc)
            else:
                # MySQL: DB==스키마, 한 연결이 그룹의 모든 DB 를 본다. 연결 실패=이 datasource 도달 불가
                # → 그룹 DB 만 연결 불가(타 datasource 그룹 무영향). [대소문자 매칭은 db.py LOWER() 가 처리]
                try:
                    rows = _db.list_information_schema_tables(coords_pinned, schemas=dbs, timeout=5)
                    by_schema: dict = {}
                    for s, t in rows:
                        by_schema.setdefault(str(s).strip().lower(), set()).add((str(s), str(t)))
                    for db in dbs:
                        db_tables[db] = {
                            "pairs": by_schema.get(str(db).strip().lower(), set()),
                            "connected": True, "note": "",
                        }
                except Exception as exc:
                    logging.getLogger("app").warning(
                        "insight_coverage catalog fail pid=%s ds=%s err=%r", pid, dskey, exc)
                    for db in dbs:
                        db_tables[db] = {
                            "pairs": set(), "connected": False,
                            "note": "데이터소스 카탈로그 조회 실패(연결/권한)",
                        }

            # ── 분자: PG rag_objects 통찰 (이 그룹 scope) ──
            try:
                analyzed_tables, analyzed_schemas = _analyzed_sets_for_scope(scope, allow_null)
            except Exception as exc:
                pg_failed = True
                logging.getLogger("app").warning("insight_coverage pg fail pid=%s err=%r", pid, exc)
                break

            for db in dbs:
                info = db_tables.get(db) or {"pairs": set(), "connected": False, "note": ""}
                if not info.get("connected"):
                    per_db_by_name[db] = {
                        "db": db, "connected": False, "schema_analyzed": False,
                        "tables_total": 0, "tables_analyzed": 0,
                        "note": info.get("note") or "연결 불가",
                    }
                    continue
                pairs = info["pairs"]
                tables_total = len(pairs)
                tables_analyzed = sum(
                    1 for (s, t) in pairs
                    if (s.strip().lower(), t.strip().lower()) in analyzed_tables
                )
                live_schemas = {s.strip().lower() for (s, _t) in pairs}
                db_schema_analyzed = 1 if (
                    (live_schemas & analyzed_schemas) or (str(db).strip().lower() in analyzed_schemas)
                ) else 0
                per_db_by_name[db] = {
                    "db": db, "connected": True,
                    "schema_analyzed": bool(db_schema_analyzed),
                    "tables_total": tables_total,
                    "tables_analyzed": tables_analyzed,
                    "note": "",
                }
    finally:
        try:
            pg.close()
        except Exception:
            pass

    if pg_failed:
        base["reason"] = "PG 통찰 조회 실패"
        return base

    # ── 합산 (원래 노출 순서) : 각 connected DB = 1 DB노드 + N table노드. 비연결 DB 는 분모 제외. ──
    # 동명 DB 가 서로 다른 datasource 그룹에 등록될 수 있어(멀티 datasource 의 정상 시나리오 — 같은
    # 'dbCommon' 이 여러 서버에 존재) per_db_by_name 은 dict(이름 1키)다. order 는 중복을 포함할 수
    # 있으므로 seen 가드로 한 번만 집계·노출한다(이중 카운트 방지 → pct 왜곡 차단). TASK-0249.
    total_obj = 0
    analyzed_obj = 0
    connected_count = 0
    per_db = []
    seen_dbs: set = set()
    for db in order:
        if db in seen_dbs:
            continue
        seen_dbs.add(db)
        row = per_db_by_name.get(db) or {
            "db": db, "connected": False, "schema_analyzed": False,
            "tables_total": 0, "tables_analyzed": 0, "note": "연결 불가",
        }
        per_db.append(row)
        if row.get("connected"):
            connected_count += 1
            db_total = row["tables_total"] + 1   # +1 = DB(schema) 노드
            db_analyzed = row["tables_analyzed"] + (1 if row["schema_analyzed"] else 0)
            total_obj += db_total
            analyzed_obj += db_analyzed

    base["engine"] = engines_seen[0] if engines_seen else "mysql"
    base["default_db"] = default_db_seen
    base["total_objects"] = total_obj
    base["analyzed_objects"] = analyzed_obj
    base["per_db"] = per_db
    base["pct"] = (round(100.0 * analyzed_obj / total_obj, 1) if total_obj > 0 else None)
    # 측정 가능한 DB 가 하나라도 있으면 measurable. 전부 연결 불가(또는 datasource 미해석)이면
    # "측정 불가" badge 로 graceful 표시(0% 로 오인 방지).
    base["measurable"] = connected_count > 0
    if connected_count == 0:
        base["reason"] = (
            "데이터소스를 해석할 수 없습니다(미바인딩/삭제 확인)." if not resolved_any
            else "접근 가능 데이터베이스에 연결할 수 없습니다(RO 권한/도달 확인)."
        )
    return base


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
async def upload_product_icon(product_id: int, request: Request, file: UploadFile = File(...), account=Depends(app.require_permission("product.update", message="제품 수정 권한이 필요합니다 (product.update).")), conn=Depends(app.get_conn)) -> JSONResponse:
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
def delete_product_icon(product_id: int, request: Request, account=Depends(app.require_permission("product.update", message="제품 수정 권한이 필요합니다 (product.update).")), conn=Depends(app.get_conn)) -> JSONResponse:
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
    if not app._account_has_permission(account, "product.create"):
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
        # feature-0028 (P1-B): 동적 권한(product.access.*) 변경 — 카탈로그 TTL 캐시 즉시 무효화.
        app.invalidate_permission_catalog_cache()
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
        # feature-0028 (P1-B): 동적 권한(product.access.*) 변경 — 카탈로그 TTL 캐시 즉시 무효화.
        app.invalidate_permission_catalog_cache()
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
    if not app._account_has_permission(account, "product.update"):
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
        # feature-0028 (P1-B): 동적 권한(product.access.*) 변경 — 카탈로그 TTL 캐시 즉시 무효화.
        app.invalidate_permission_catalog_cache()
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
    if not app._account_has_permission(account, "product.delete"):
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
        # feature-0028 (P1-B): 동적 권한(product.access.*) 변경 — 카탈로그 TTL 캐시 즉시 무효화.
        app.invalidate_permission_catalog_cache()
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
async def admin_update_product_databases(
    product_id: int,
    request: Request,
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    # ITEM-11 batch13: _require_account→account+conn 완전 DI(마지막 산재-close leak 핸들러).
    # get_conn finally:close 가 datasource 검증·UPDATE raise 시 산재 close 경로의 leak 을 해소.
    if product_id <= 0:
        return app._json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return app._json_error("invalid json", 400)
    if not app._account_has_permission(account, "product.update"):
        return app._json_error("제품 관리 권한이 필요합니다.", 403)
    cur = conn.cursor()
    cur.execute("SELECT Id, DatasourceKey FROM WebProducts WHERE Id = %s", (int(product_id),))
    _prow = cur.fetchone()
    if not _prow:
        cur.close()
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
    # ── FR-schema-name-case-drift (B, ingestion 정규화) ──────────────────────────
    # 저장 직전 각 스키마명을 datasource 서버의 **실제 case** 로 정규화한다. 프론트 picker(admin.js 가
    # MySQL 스키마명을 `.toLowerCase()` 로 저장)·수기 입력이 소문자로 보내도, case-sensitive MySQL
    # (lower_case_table_names=0)에서 그 스키마 조회가 0행이 되는 drift 를 **write 시점에** 봉인한다
    # (예: 서버 `DEV_1_1_1_20` ↔ 입력 `dev_1_1_1_20`). 런타임 A(agent_core canonicalize)와 짝을 이뤄
    # 신규 저장 case 를 서버 실제값으로 고정. **degrade-safe**: datasource 미해소·SSRF 차단·연결 실패·
    # 모호(대소문자만 다른 동명 복수) → 입력 case 유지(저장 차단 안 함, 기존 동작). MySQL 대상만
    # (MSSQL 은 catalog case-insensitive — 정규화 불필요).
    if cleaned and _ds_engine == "mysql" and _dskey:
        try:
            from shared import datasources as _dsr
            from shared import db as _db
            _norm_ds = _dsr.resolve(conn, _dskey)
            if _norm_ds:
                _okssrf, _rsn, _pin = app._ssrf_check_host(_norm_ds.get("host"))
                if _okssrf:
                    _low2real: dict[str, str] = {}
                    _ambig: set[str] = set()
                    for _n in (_db.list_server_databases({**_norm_ds, "host": _pin}) or []):
                        _r = str(_n); _l = _r.strip().lower()
                        if _l in _low2real and _low2real[_l] != _r:
                            _ambig.add(_l)  # 대소문자만 다른 동명 복수 → 모호(정규화 안 함)
                        else:
                            _low2real[_l] = _r
                    for _l in _ambig:
                        _low2real.pop(_l, None)
                    for _it in cleaned:
                        _rc = _low2real.get(str(_it["schema_name"]).strip().lower())
                        if _rc:
                            _it["schema_name"] = _rc  # 서버 실제 case 로 고정
        except Exception:
            logging.getLogger(__name__).debug("schema_case_normalize_skip ds=%s", _dskey)

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
                # §59: 'ai'(승인된 AI 제안)도 rule 과 동일하게 — 제출 스키마와 충돌하면 manual 승격
                #   우선 규약으로 정리(잔존 시 평문 INSERT 가 PK 1062 로 저장 전체 500, 패널 MAJOR).
                cur.execute(
                    "DELETE FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s "
                    "AND LOWER(SchemaName) = %s AND COALESCE(Source,'manual') IN ('rule','ai')",
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
        return app._json_error(f"audit write failed: {audit_exc}", 500)
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


@router.post("/api/admin/products/{product_id}/datasources/{key}/ai-suggestions/approve")
async def admin_approve_product_ai_suggestions(product_id: int, key: str, request: Request) -> JSONResponse:
    """§59: AI 분류 제안(pending RuleId NULL·Reason 'ai_suggest:*')을 allowlist 로 승격(Source='ai').

    rule 귀속 승인(approve-pending)과 동일 게이트·검증(제외 DB·이름 길이/주입) 미러 — 규칙이 없는
    제안 행은 기존 엔드포인트가 조용히 no-op 라 별도 경로가 필요하다(ADR-025). product.manage."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    try:
        # 패널 MINOR: default-all 금지 — AI 제안 승인은 **명시 스키마 목록 필수**(사람의 개별 검토가
        #   ADR-025 핵심 통제. 기존 rule 승인의 1-click 전체는 rule 1개 귀속이라 범위가 다름).
        want = data.get("schemas") if isinstance(data, dict) else None
        if not isinstance(want, list) or not want:
            return app._json_error("schemas 목록이 필요합니다", 400)
        pending = [p for p in app._list_db_rule_pending(conn, int(product_id), dsk)
                   if not int(p.get("rule_id") or 0)
                   and str(p.get("reason") or "").startswith("ai_suggest")]
        pend_names = {p["schema_name"] for p in pending}
        targets = [s for s in want if str(s) in pend_names]
        if not targets:
            return JSONResponse({"ok": True, "approved": []})
        try:
            from shared import datasources as _dsr
            _ds = _dsr.resolve(conn, dsk)
            engine = str((_ds or {}).get("engine") or "mysql").strip().lower()
            excluded = app._db_rule_excluded_lower(engine)
        except Exception:
            # 패널 MINOR: resolve 실패 시 mysql 강등이 MSSQL 시스템 DB 창을 연다 — 합집합으로 방어.
            excluded = app._db_rule_excluded_lower("mysql") | app._db_rule_excluded_lower("mssql")
        # 패널 MAJOR: allowlist 변이 + 감사는 원자화 — autocommit 커넥션이면 audit 실패 rollback 이
        #   no-op 라 감사 없는 접근면 확장이 확정된다(admin_settings/admin_datasources 정본 패턴 미러).
        _prev_ac = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
        except Exception:
            pass
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
                "VALUES (%s,%s,%s,%s,%s,'ai',NULL)",
                (int(product_id), str(name), "", max_sort, dsk))
            cur.execute("DELETE FROM WebProductDatabasePending WHERE ProductId=%s AND LOWER(DatasourceKey)=%s AND SchemaName=%s AND RuleId IS NULL",
                        (int(product_id), dsk, str(name)))
            approved.append(str(name))
        cur.close()
        try:
            app.record_audit_event(
                conn, actor=app._db_rule_audit_actor(account), action="admin.product.ai_suggest.approve",
                resource_type="product", resource_id=str(product_id),
                change_json={"datasource_key": dsk, "names": approved})
            conn.commit()
        except Exception as audit_exc:
            conn.rollback()
            return app._json_error(f"audit write failed: {audit_exc}", 500)
        finally:
            try:
                conn.autocommit = _prev_ac
            except Exception:
                pass
        return JSONResponse({"ok": True, "approved": approved})
    finally:
        conn.close()


@router.post("/api/admin/products/{product_id}/datasources/{key}/ai-suggestions/reject")
async def admin_reject_product_ai_suggestions(product_id: int, key: str, request: Request) -> JSONResponse:
    """§59: AI 분류 제안 거부 — pending(RuleId NULL·ai_suggest) 행 삭제(멱등). product.manage.

    거부된 스키마는 다음 pass 의 taken(pending) 제외에서 빠져 재제안될 수 있다 — 반복 거부가
    소음이면 운영이 규칙/수동 매핑으로 확정하는 것이 정본 경로(ADR-025 한계)."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    conn, account, dsk, error = app._db_rule_gate(request, product_id, key)
    if error:
        return error
    try:
        want = data.get("schemas") if isinstance(data, dict) else None
        if not isinstance(want, list) or not want:
            return app._json_error("schemas 목록이 필요합니다", 400)
        pending = [p for p in app._list_db_rule_pending(conn, int(product_id), dsk)
                   if not int(p.get("rule_id") or 0)
                   and str(p.get("reason") or "").startswith("ai_suggest")]
        pend_names = {p["schema_name"] for p in pending}
        targets = [s for s in want if str(s) in pend_names]
        if not targets:
            return JSONResponse({"ok": True, "rejected": []})
        rejected: list[str] = []
        _prev_ac = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
        except Exception:
            pass
        cur = conn.cursor()
        for name in targets:
            cur.execute("DELETE FROM WebProductDatabasePending WHERE ProductId=%s AND LOWER(DatasourceKey)=%s AND SchemaName=%s AND RuleId IS NULL",
                        (int(product_id), dsk, str(name)))
            if getattr(cur, "rowcount", 0):
                rejected.append(str(name))
        cur.close()
        try:
            app.record_audit_event(
                conn, actor=app._db_rule_audit_actor(account), action="admin.product.ai_suggest.reject",
                resource_type="product", resource_id=str(product_id),
                change_json={"datasource_key": dsk, "names": rejected})
            conn.commit()
        except Exception as audit_exc:
            conn.rollback()
            return app._json_error(f"audit write failed: {audit_exc}", 500)
        finally:
            try:
                conn.autocommit = _prev_ac
            except Exception:
                pass
        return JSONResponse({"ok": True, "rejected": rejected})
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


# ==== feature-0012 ITEM-10 p13 — app.py 에서 이동 (6종). app 전역은 app.X 동적 참조. ====

def _db_rule_excluded_lower(engine: str) -> "set[str]":
    """M2: 시스템/내부 제외 집합(소문자) — 분산된 상수 union 을 단일 consult. 엔진별 시스템 DB."""
    eng = str(engine or "mysql").strip().lower()
    ex = {x.lower() for x in app._DATABASES_AVAILABLE_INTERNAL}
    try:
        ex.add(str(app.MEMORY_DB).lower())
    except Exception:
        pass
    if eng == "mssql":
        ex |= {x.lower() for x in app._DATABASES_AVAILABLE_SYSTEM_MSSQL}
    else:
        ex |= {x.lower() for x in app._DATABASES_AVAILABLE_METADATA}
    return ex

def _db_rule_audit_actor(account: "dict | None") -> "dict | None":
    """B3: 감사 귀속용 actor — 규칙 생성자(또는 요청 계정) 계정으로 ActorAccountId 기록(system NULL 회피)."""
    if not account:
        return None
    return {
        "account_id": account.get("id"),
        "role_id": account.get("role_id"),
        "username": account.get("username"),
        "actor_type": "account",
        "session_id": None,
        "remote_addr": None,
        "user_agent": None,
        "request_id": None,
    }

def _reconcile_one_db_rule(conn, rule: dict, *,
                           actor_account: "dict | None", can_manage: bool, trigger: str) -> dict:
    """단일 규칙 reconcile — 라이브 DB 와 대조해 신규 일치 DB 를 자동적용(cap 이하·can_manage) 또는
    pending(초과·미보유) 으로 스테이징. **기존 행(manual ∪ 전 규칙)** 전체로 dedup → 다중 규칙에서 한
    DB 는 먼저 추가한 규칙이 소유(RuleId). manual 행 절대 미변경(B4). 열거 실패=no-op(M4). 자동행 SortOrder
    말미(M5). 감사는 규칙 생성자 귀속(B3)."""
    result = {"status": "ok", "auto_added": [], "pending": [], "rule_id": int(rule.get("id") or 0)}
    pid = int(rule.get("product_id") or 0)
    dsk = str(rule.get("datasource_key") or "").strip().lower()
    rid = int(rule.get("id") or 0)
    if pid <= 0 or not dsk or rid <= 0:
        result["status"] = "bad-args"
        return result
    if not rule.get("is_enabled"):
        result["status"] = "disabled"
        return result
    # 라이브 DB 열거 (M4: 모든 실패 = no-op — 빈 목록을 '전부 제거'로 해석 금지).
    try:
        from shared import datasources as _dsr
        from shared import db as _db
        ds = _dsr.resolve(conn, dsk)
        if not ds:
            result["status"] = "ds-unresolved"
            return result
        okssrf, _reason, _pin = app._ssrf_check_host(ds.get("host"))
        if not okssrf:
            result["status"] = "ssrf-blocked"
            return result
        classified = _db.list_server_databases_classified({**ds, "host": _pin})
    except Exception:
        result["status"] = "enumerate-failed"
        return result
    if not isinstance(classified, list):
        result["status"] = "enumerate-failed"
        return result
    engine = str(ds.get("engine") or "mysql").strip().lower()
    user_names = [d["name"] for d in classified
                  if isinstance(d, dict) and not d.get("system") and d.get("name")]
    excluded = app._db_rule_excluded_lower(engine)
    matched = app._match_db_rule(user_names, rule["include_pattern"], rule.get("exclude_pattern"), engine, excluded)
    # 기존 행(manual ∪ 전 규칙) — dedup(소문자) + SortOrder max(M5: 자동행은 말미). 다중 규칙 cross-dedup.
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT SchemaName, COALESCE(SortOrder,0) FROM WebProductDatabases "
            "WHERE ProductId=%s AND LOWER(DatasourceKey)=%s", (pid, dsk))
        rows = cur.fetchall() or []
    finally:
        cur.close()
    existing_lower = {str(r[0]).strip().lower() for r in rows}
    max_sort = max([int(r[1] or 0) for r in rows], default=0)
    new = [m for m in matched if str(m).strip().lower() not in existing_lower]
    if not new:
        app._touch_db_rule_sync(conn, rid)
        conn.commit()
        result["status"] = "no-change"
        return result
    auto = bool(can_manage) and len(new) <= int(rule.get("cap") or 3)
    cur = conn.cursor()
    try:
        if auto:
            for i, name in enumerate(new):
                # MAJOR#1(재리뷰): INSERT IGNORE — 동시 reconcile 경쟁/PK 미마이그 시에도 중복 allowlist 행 방지.
                cur.execute(
                    "INSERT IGNORE INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, "
                    "DatasourceKey, Source, RuleId) VALUES (%s,%s,%s,%s,%s,'rule',%s)",
                    (pid, name, "", max_sort + (i + 1) * 10, dsk, rid))
                # 자동 추가된 schema 의 잔여 pending(다른 규칙이 보류해 둔 것) 정리(phantom 제거).
                cur.execute(
                    "DELETE FROM WebProductDatabasePending WHERE ProductId=%s AND LOWER(DatasourceKey)=%s AND SchemaName=%s",
                    (pid, dsk, name))
            result["auto_added"] = list(new)
        else:
            for name in new:
                cur.execute(
                    "INSERT IGNORE INTO WebProductDatabasePending (ProductId, DatasourceKey, SchemaName, "
                    "RuleId, Reason) VALUES (%s,%s,%s,%s,%s)",
                    (pid, dsk, name, rid, ("cap_exceeded" if can_manage else "no_manage")))
            result["pending"] = list(new)
    finally:
        cur.close()
    try:
        app.record_audit_event(
            conn, actor=app._db_rule_audit_actor(actor_account),
            action=("admin.product.db.autoadd" if auto else "admin.product.db.staged"),
            resource_type="product", resource_id=str(pid),
            change_json={"datasource_key": dsk, "rule_id": rid, "trigger": str(trigger),
                         "names": list(new), "auto": auto, "cap": int(rule.get("cap") or 3),
                         "creator_account_id": rule.get("created_by_account_id")},
        )
    except Exception as _aexc:
        try:
            conn.rollback()
        except Exception:
            pass
        result["status"] = f"audit-failed: {_aexc}"
        return result
    app._touch_db_rule_sync(conn, rid)
    conn.commit()
    return result

def _reconcile_product_db_rules(conn, product_id: int, ds_key: str, *,
                                actor_account: "dict | None", can_manage: bool, trigger: str) -> dict:
    """(product, datasource) 의 **모든** enabled 규칙을 순차 reconcile(SortOrder 순 — 앞 규칙이 DB 우선 소유).
    각 규칙은 직전 규칙의 커밋된 행까지 dedup 대상으로 본다(cross-rule 이중 추가 방지)."""
    agg = {"status": "ok", "auto_added": [], "pending": [], "per_rule": []}
    rules = app._get_product_db_rules(conn, int(product_id or 0), str(ds_key or "").strip().lower())
    if not rules:
        agg["status"] = "no-rule"
        return agg
    for rule in rules:
        if not rule.get("is_enabled"):
            continue
        r = app._reconcile_one_db_rule(conn, rule, actor_account=actor_account, can_manage=can_manage, trigger=trigger)
        agg["auto_added"].extend(r.get("auto_added") or [])
        agg["pending"].extend(r.get("pending") or [])
        agg["per_rule"].append({"rule_id": rule.get("id"), "status": r.get("status"),
                                "auto_added": r.get("auto_added") or [], "pending": r.get("pending") or []})
    return agg

def _reconcile_all_db_rules_once() -> None:
    """백그라운드 1 cycle: 모든 enabled 규칙을 creator 권한 재검증(M3) 후 규칙별 reconcile."""
    try:
        conn = app._connect_memory()
    except Exception:
        return
    try:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(f"SELECT {app._DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules WHERE IsEnabled=1 "
                        "ORDER BY ProductId, DatasourceKey, SortOrder, Id")
            rules = [app._normalize_db_rule_row(r) for r in (cur.fetchall() or [])]
        except Exception:
            try:
                cur.execute(f"SELECT {app._DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules WHERE IsEnabled=1")
                rules = [app._normalize_db_rule_row(r) for r in (cur.fetchall() or [])]
            except Exception:
                rules = []
        finally:
            cur.close()
        for rule in rules:
            try:
                creator_id = int(rule.get("created_by_account_id") or 0)
                creator = app._load_account_by_id(conn, creator_id) if creator_id > 0 else None
                # M3: creator 가 현재도 **활성·비삭제 + product.manage** 일 때만 자동 GRANT — 아니면 pending.
                creator_ok = bool(creator and creator.get("is_active") and not creator.get("deleted_at"))
                can_manage = bool(creator_ok and app._account_has_permission(creator, "product.update"))
                app._reconcile_one_db_rule(conn, rule, actor_account=creator, can_manage=can_manage, trigger="background")
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                continue
    finally:
        try:
            conn.close()
        except Exception:
            pass

def _db_rule_gate(request: Request, product_id: int, key: str):
    """(conn, account, ds_key, error) — product.manage + 제품 존재 + datasource 바인딩 검증(임의 키 차단)."""
    if int(product_id or 0) <= 0:
        return (None, None, None, app._json_error("invalid product_id", 400))
    dsk = str(key or "").strip().lower()
    if not dsk:
        return (None, None, None, app._json_error("invalid datasource key", 400))
    try:
        conn = app._connect_memory()
    except Exception:
        return (None, None, None, app._json_error("db connection failed", 500))
    account, error = app._require_account(request, conn)
    if error:
        conn.close()
        return (None, None, None, error)
    if not app._account_has_permission(account, "product.update"):
        conn.close()
        return (None, None, None, app._json_error("제품 관리 권한이 필요합니다.", 403))
    cur = conn.cursor()
    cur.execute("SELECT Id, DatasourceKey FROM WebProducts WHERE Id = %s", (int(product_id),))
    prow = cur.fetchone()
    if not prow:
        cur.close()
        conn.close()
        return (None, None, None, app._json_error("product not found", 404))
    primary = (str(prow[1]).strip().lower() if len(prow) > 1 and prow[1] else "")
    bound = False
    try:
        cur.execute(
            "SELECT 1 FROM WebProductDatasources WHERE ProductId=%s AND LOWER(DatasourceKey)=%s LIMIT 1",
            (int(product_id), dsk))
        bound = bool(cur.fetchone())
    except Exception:
        bound = (dsk == primary)
    if not bound and primary and dsk == primary:
        bound = True
    cur.close()
    if not bound:
        conn.close()
        return (None, None, None, app._json_error(f"datasource '{dsk}' 는 이 제품에 바인딩되지 않았습니다.", 400))
    return (conn, account, dsk, None)


# ==== feature-0012 ITEM-10 p14 — app.py 에서 이동 (6종). app 전역은 app.X 동적 참조. ====

def _list_product_datasources(conn, product_id: int) -> list[dict[str, Any]]:
    """TASK-0228 (1:N): 제품에 바인딩된 datasource 키 목록(primary 우선). 미이전/테이블 부재 시
    레거시 단일 바인딩(WebProducts.DatasourceKey)으로 폴백 — 단일 바인딩 제품은 항상 1건 반환.

    반환: [{"datasource_key": str, "is_primary": bool, "sort_order": int}, ...]
    """
    if product_id <= 0:
        return []
    out: list[dict[str, Any]] = []
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "SELECT LOWER(DatasourceKey), IsPrimary, SortOrder FROM WebProductDatasources "
                "WHERE ProductId = %s ORDER BY IsPrimary DESC, SortOrder ASC, DatasourceKey ASC",
                (int(product_id),),
            )
            for r in cur.fetchall() or []:
                if r and r[0]:
                    out.append({
                        "datasource_key": str(r[0]).strip().lower(),
                        "is_primary": bool(r[1]),
                        "sort_order": int(r[2] or 0),
                    })
        except Exception:
            out = []
        if not out:
            # 폴백: 레거시 단일 바인딩(join 미이전 또는 테이블 부재).
            cur.execute("SELECT DatasourceKey FROM WebProducts WHERE Id = %s LIMIT 1", (int(product_id),))
            r = cur.fetchone()
            if r and r[0] and str(r[0]).strip():
                out.append({"datasource_key": str(r[0]).strip().lower(), "is_primary": True, "sort_order": 0})
    finally:
        cur.close()
    return out

def _list_db_rule_pending(conn, product_id: int, ds_key: str) -> "list[dict]":
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT SchemaName AS schema_name, Reason AS reason, RuleId AS rule_id, DetectedAt AS detected_at "
            "FROM WebProductDatabasePending WHERE ProductId=%s AND LOWER(DatasourceKey)=%s ORDER BY SchemaName",
            (int(product_id), str(ds_key).strip().lower()))
        return [
            {"schema_name": str(r.get("schema_name") or ""), "reason": str(r.get("reason") or ""),
             "rule_id": (int(r["rule_id"]) if r.get("rule_id") is not None else None),
             "detected_at": str(r.get("detected_at") or "")}
            for r in (cur.fetchall() or [])
        ]
    except Exception:
        return []
    finally:
        cur.close()

def _insight_reset_ds_heads(scope_aliases, allow_null: bool) -> list[str]:
    """ds_fact_key 접두 목록. scope alias 마다 `ds:{alias}:`, allow_null 이면 무접두("")도 포함.

    TASK-0230 (M2): 단일 scope 가 아니라 alias 집합(hash/.env label) 전체를 처리해야 fingerprint 가
    어느 세대 키로 쓰였든 모두 삭제된다(잔존 fingerprint → 재분석 skip 방지).
    """
    heads: list[str] = []
    for alias in (scope_aliases or []):
        a = str(alias or "").strip().lower()
        if a:
            heads.append(f"ds:{app._like_escape(a)}:")
    if allow_null or not scope_aliases:
        heads.append("")  # 무접두 (ds=None 레거시 기록)
    # dedup, 순서 보존
    seen: set[str] = set()
    out: list[str] = []
    for h in heads:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out

def _insight_reset_fact_key_patterns(db, scope_aliases=None, allow_null: bool = False, live_schemas=None) -> list[str]:
    """DB `{db}` 의 insight fact_key 를 매칭하는 LIKE 패턴 목록 (ESCAPE '\\').

    저장 키 suffix(config.ds_object_suffix):
      - MySQL(db==schema):       `{db}`,  `{db}.{table}`
      - MSSQL 3-tier:            `{db}.{schema}`,  `{db}.{schema}.{table}`
      - MSSQL 2-tier(레거시):     `{schema}`,  `{schema}.{table}`  (catalog 없음 — live_schemas 로 보강)
    TASK-0230 (M1/M2): scope alias 전체 + 라이브 schema 목록(MSSQL 2-tier 레거시 catalog-less 키 포함)을
    커버한다. live_schemas 가 None/빈 경우 db 자체만(MySQL·3-tier) 패턴 생성(하위호환).

    하위호환: scope_aliases 가 문자열(단일 scope)로 들어오면 list 로 승격.
    """
    if isinstance(scope_aliases, str):
        scope_aliases = [scope_aliases]
    db_l = str(db or "").strip().lower()
    eq = app._like_escape(db_l)
    pre = eq + "."
    ds_heads = app._insight_reset_ds_heads(scope_aliases, allow_null)
    # db 자체 토큰(MySQL schema == db, MSSQL 3-tier catalog == db) + MSSQL 2-tier 레거시 schema 토큰.
    tokens: list[tuple[str, bool]] = [(eq, True)]  # (escaped, include_exact)
    for s in (live_schemas or []):
        s_l = str(s or "").strip().lower()
        if s_l and s_l != db_l:
            tokens.append((app._like_escape(s_l), True))
    patterns: list[str] = []
    for source in ("schema_insight", "table_insight"):
        for head in ds_heads:
            for tok, _exact in tokens:
                patterns.append(f"{source}:{head}{tok}")       # 정확히 토큰 (schema 노드)
                patterns.append(f"{source}:{head}{tok}.%")      # 토큰.<하위>
    seen: set[str] = set()
    uniq: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq

def _insight_reset_kv_key_patterns(db, scope_aliases=None, allow_null: bool = False, live_schemas=None) -> list[str]:
    """DB `{db}` 의 insight KV(fingerprint/refresh_at/scan offset) 키 LIKE 패턴 목록.

    저장 키(config.ds_scope_name / ds_fact_key):
      - `{source}:{suffix}` 또는 `{source}:ds:{alias}:{suffix}` — schema_fp/table_fp/*_refresh_at (접두)
      - `schema_instance_scan_offset:{schema}[:ds:{alias}]` (ds_scope_name 은 **접미** `:ds:{alias}`)
    TASK-0230 (M1/M2): scope alias 전체 + 라이브 schema(MSSQL 2-tier 레거시) 커버.
    """
    if isinstance(scope_aliases, str):
        scope_aliases = [scope_aliases]
    db_l = str(db or "").strip().lower()
    eq = app._like_escape(db_l)
    ds_heads = app._insight_reset_ds_heads(scope_aliases, allow_null)
    tokens: list[str] = [eq]
    for s in (live_schemas or []):
        s_l = str(s or "").strip().lower()
        if s_l and s_l != db_l:
            tokens.append(app._like_escape(s_l))
    patterns: list[str] = []
    # ds_fact_key 형식 (접두): schema_fp / table_fp / schema_insight_refresh_at / table_insight_refresh_at
    for source in ("schema_fp", "table_fp", "schema_insight_refresh_at", "table_insight_refresh_at"):
        for head in ds_heads:
            for tok in tokens:
                patterns.append(f"{source}:{head}{tok}")
                patterns.append(f"{source}:{head}{tok}.%")
    # ds_scope_name 형식 (접미): schema_instance_scan_offset:{schema}[:ds:{alias}]
    ds_suffixes: list[str] = []
    for alias in (scope_aliases or []):
        a = str(alias or "").strip().lower()
        if a:
            ds_suffixes.append(f":ds:{app._like_escape(a)}")
    if allow_null or not scope_aliases:
        ds_suffixes.append("")  # 접미 없음 (ds=None)
    for tail in ds_suffixes:
        for tok in tokens:
            patterns.append(f"schema_instance_scan_offset:{tok}{tail}")
            patterns.append(f"schema_instance_scan_offset:{tok}.%{tail}")
    seen: set[str] = set()
    uniq: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq

def _attach_product_conn_status(conn, products: list[dict[str, Any]]) -> None:
    """TASK-0261: 대화 화면 제품 목록에 datasource 연결(네트워크) 상태를 첨부한다(in-place).

    conn-health-monitor(TASK-0250)가 백그라운드로 미리 계산한 per-datasource 상태를
    재사용해 추가 probe 없이 즉시 표시한다. admin_list_datasources 와 동일 소스
    (`conn_health.snapshot()` × `datasources.scope_key`).

    각 product 의 `datasources[]` 항목마다 `conn_status`({status, elapsed_ms, checked_at})를
    붙이고, product 레벨 `conn_status_overall` 에 바인딩들의 **최악 상태**를 집계한다
    (conn-tristate 심각도: down > unstable > unknown > healthy — 하나라도 down→down,
    하나라도 unstable→unstable, 모두 healthy→healthy). 좌표/비밀번호는 노출하지 않는다
    (status/elapsed/checked_at 만 — datasource_public 마스킹과 동일).

    conn_health 미가용·datasource 미해석 등은 graceful — status=unknown 으로 둔다.
    바인딩이 없는 기본 단일 MySQL 제품은 status 무첨부(드롭업 dot 가 모드색 유지).
    """
    if not products:
        return
    try:
        from shared import conn_health as _ch
        _health = _ch.snapshot()
    except Exception:
        _health = {}
    try:
        from shared import datasources as _dsr
    except Exception:
        _dsr = None
    # datasource_key(소문자) → scope_key 캐시(제품 간 동일 키 재해석 방지).
    _sk_cache: dict[str, "str | None"] = {}

    def _status_for_key(dskey: "str | None") -> "dict[str, Any]":
        if not dskey or _dsr is None:
            return {"status": "unknown", "elapsed_ms": None, "checked_at": None}
        k = str(dskey).strip().lower()
        if k not in _sk_cache:
            try:
                _ds = _dsr.resolve(conn, k)
                _sk_cache[k] = _dsr.scope_key(_ds) if _ds else None
            except Exception:
                _sk_cache[k] = None
        sk = _sk_cache[k]
        h = _health.get(sk) if sk else None
        if not h:
            return {"status": "unknown", "elapsed_ms": None, "checked_at": None}
        return {
            "status": h.get("status") or "unknown",
            "elapsed_ms": h.get("last_elapsed_ms"),
            "checked_at": h.get("checked_at"),
        }

    _RANK = {"down": 4, "unstable": 3, "unknown": 2, "healthy": 1}
    for p in products:
        binds = p.get("datasources") if isinstance(p.get("datasources"), list) else []
        worst = None  # (rank, status)
        for b in binds:
            st = _status_for_key(b.get("datasource_key"))
            b["conn_status"] = st
            r = _RANK.get(st["status"], 2)
            if worst is None or r > worst[0]:
                worst = (r, st["status"])
        # 바인딩 없는 제품(기본 단일 MySQL)은 overall 무첨부 → 프론트가 모드색 유지.
        p["conn_status_overall"] = (worst[1] if worst else None)


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (13종). app 전역은 app.X 동적 참조. ====

def _block_conversations_for_product(
    product_id: int,
    reason: str,
    *,
    conn=None,
) -> int:
    """제품 삭제 시 그 제품을 pinned 한 대화를 일괄 차단한다. Returns 차단된 행 수.

    이미 차단된 대화(blocked_at IS NOT NULL)는 재차단하지 않는다(reason/시각 보존).
    backend-aware. production(PG) 경로가 정본. 호출자가 차단 실패를 loud 하게 처리할
    수 있도록 예외는 전파한다(삭제 핸들러가 catch + 경고 로깅).
    """
    if not product_id or int(product_id) <= 0:
        return 0
    if app.os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.core_conversations "
                    "SET blocked_at = now(), blocked_reason = %s "
                    "WHERE product_id = %s AND blocked_at IS NULL",
                    (reason, int(product_id)),
                )
                affected = int(pgcur.rowcount or 0)
            pg.commit()
            return affected
        finally:
            pg.close()
    own_conn = conn is None
    if own_conn:
        conn = app._connect_memory()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE AgentCoreConversations "
            "SET blocked_at = NOW(), blocked_reason = %s "
            "WHERE product_id = %s AND blocked_at IS NULL",
            (reason, int(product_id)),
        )
        affected = int(cur.rowcount or 0)
        cur.close()
        try:
            conn.commit()
        except Exception:
            pass
        return affected
    finally:
        if own_conn and conn is not None:
            conn.close()

def _compose_db_insight_text(ent: dict) -> tuple:
    """by_db 누적 항목(ent) → (한 줄 description, 멀티라인 detail_text[hover title용]).

    description = 도메인 + (schema summary | table 도메인 요약). detail_text = schema 전문 + 테이블별 정제 본문.
    """
    domain = ent.get("domain")
    summary = app._clean_insight_segment(ent.get("schema_text") or "")
    if not summary and ent.get("tables"):
        # schema insight 없으면 table 도메인들로 합성.
        tdoms = []
        for t in ent["tables"]:
            d = t.get("domain")
            if d and d not in tdoms:
                tdoms.append(d)
        if tdoms:
            summary = "주요 테이블 도메인: " + ", ".join(tdoms[:4])
    parts = []
    if domain:
        parts.append(str(domain))
    if summary:
        parts.append(summary)
    description = " — ".join(parts) if parts else None

    lines = []
    if ent.get("schema_text"):
        lines.append("· " + str(ent["schema_text"]))
    for t in ent.get("tables", [])[:12]:
        tname = t.get("table") or ""
        tdesc = app._clean_insight_segment(t.get("text") or "") or (t.get("domain") or "")
        lines.append(f"· {tname}: {tdesc}" if tdesc else f"· {tname}")
    detail_text = "\n".join(lines) if lines else None
    return description, detail_text

def _db_catalog_from_object_key(object_key: str, engine: str, object_type: str):
    """rag_objects.object_key 에서 DB(catalog) 키를 추출 (TASK-0243 — MSSQL 차원 수정).

    object_key = `{ds_prefix}:{path}` (ds_prefix = datasource_key 라벨/해시 — `_ds_valid_key` 가 ':' 를
    금지하므로 첫 ':' 로 안전 분리, 접두값 자체는 버린다). **MSSQL 은 schema_name 컬럼이 SQL 스키마(dbo)**
    라 등록 DB(catalog, 예: GameLog_100)와 차원이 달라 schema_name 으로 by_db 를 묶으면 매칭이 빗나가
    'dbo' 한 바구니로 뭉친다. catalog 는 object_key path 에 인코딩돼 있으므로 거기서 파싱한다.
      - MySQL(db==schema): path = `{db}`(schema) | `{db}.{table}`(table) → catalog = 첫 segment.
      - MSSQL: path = `{catalog}.{sqlschema}`(schema, per-DB scan) | `{catalog}.{sqlschema}.{table}`(table)
        | `{sqlschema}`(bare default_db schema) | `{sqlschema}.{table}`(bare default_db table)
        → 충분한 segment 면 첫 segment 가 catalog, 부족(=bare default_db)하면 None(등록 catalog 미귀속).
    반환: catalog(str) 또는 None(귀속 불가 — 호출부에서 MSSQL 은 skip, MySQL 은 schema_name 폴백).
    """
    ok = str(object_key or "")
    path = ok.split(":", 1)[1] if ":" in ok else ok
    path = path.strip()
    if not path:
        return None
    segs = path.split(".")
    if str(engine or "").lower() == "mssql":
        # table = catalog.sqlschema.table(3) / schema = catalog.sqlschema(2). 그 미만이면 bare(catalog 없음).
        need = 3 if object_type == "table" else 2
        return segs[0] if len(segs) >= need and segs[0] else None
    # MySQL: db == catalog == 첫 segment (schema=`db`, table=`db.table`).
    return segs[0] if segs and segs[0] else None

def _like_escape(value: str) -> str:
    r"""PG LIKE 패턴의 메타문자(\, %, _)를 ESCAPE '\' 기준으로 이스케이프한다 (인젝션/오매칭 차단)."""
    s = str(value or "")
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

def _validate_db_rule_pattern(pattern: str) -> "tuple[bool, str]":
    """B2(강화): 저장 전 정규식 검증 — 길이·compile·backref·그룹수량자·중첩수량자·무한수량자 개수.
    catastrophic backtracking 의 구조적 벡터(그룹에 붙은 수량자 `)[*+?{]`, alternation+quantifier,
    counted repetition of groups)를 차단해 백그라운드/요청 스레드 hang(ReDoS)을 막는다. (ok, error)."""
    p = str(pattern or "").strip()
    if not p:
        return (False, "패턴이 비어 있습니다.")
    if len(p) > app._DB_RULE_PATTERN_MAX:
        return (False, f"패턴이 너무 깁니다(최대 {app._DB_RULE_PATTERN_MAX}자).")
    if app._DB_RULE_BACKREF_RE.search(p):
        return (False, "역참조(backreference)는 허용되지 않습니다.")
    if app._DB_RULE_NESTED_QUANT_RE.search(p) or app._DB_RULE_GROUP_QUANT_RE.search(p):
        return (False, "그룹에 붙은 수량자/중첩 수량자는 ReDoS 위험으로 허용되지 않습니다(예: (a|a)*, (.*a){20}).")
    if len(re.findall(r"[*+]", p)) > app._DB_RULE_MAX_UNBOUNDED_QUANT:
        return (False, f"무한 수량자(*,+)가 너무 많습니다(최대 {app._DB_RULE_MAX_UNBOUNDED_QUANT}).")
    try:
        re.compile(p)
    except re.error as exc:
        return (False, f"정규식 오류: {exc}")
    return (True, "")

def _match_db_rule(user_names: "list[str]", include_pattern: str, exclude_pattern: "str | None",
                   engine: str, excluded_lower: "set[str]") -> "list[str]":
    """B5: 엔진별 case-folding(MySQL=IGNORECASE/이름 소문자, MSSQL=대소문자 구분) 으로 일치 DB 반환.
    Exclude 우선(M1: 모호하면 제외). 잘못된 exclude 는 over-grant 방지 위해 전체 매칭 무효([])."""
    flags = 0 if str(engine or "").strip().lower() == "mssql" else re.IGNORECASE
    inc_pat = str(include_pattern or "").strip()
    if not inc_pat:
        return []  # 빈 include 는 '전부 일치'가 아니라 '매치 없음'(over-grant 방지, B1).
    # 방어 심층(B2): 저장 검증을 재적용 — 백그라운드가 저장된 패턴을 돌릴 때도 ReDoS 벡터 차단.
    if not app._validate_db_rule_pattern(inc_pat)[0]:
        return []
    if exclude_pattern and not app._validate_db_rule_pattern(str(exclude_pattern))[0]:
        return []  # 안전하지 않은 exclude → 전체 무효(over-grant 금지).
    try:
        inc = re.compile(inc_pat, flags)
    except re.error:
        return []
    exc = None
    if exclude_pattern:
        try:
            exc = re.compile(str(exclude_pattern), flags)
        except re.error:
            return []  # exclude 컴파일 실패 → 안전하게 전체 무효(over-grant 금지).
    out: list[str] = []
    for nm in (user_names or [])[:app._DB_RULE_MATCH_BOUND]:
        name = str(nm or "").strip()
        if not name:
            continue
        low = name.lower()
        if low in excluded_lower:
            continue
        if len(name) > app._DB_RULE_NAME_MAX or app._DB_RULE_NAME_INJECT_RE.search(name):
            continue
        if not inc.search(name):
            continue
        if exc is not None and exc.search(name):
            continue  # exclude wins (M1)
        out.append(name)
    return out

def _normalize_db_rule_row(row: "dict | None") -> "dict | None":
    if not row:
        return None
    row["is_enabled"] = bool(row.get("is_enabled"))
    row["cap"] = int(row.get("cap") or 3)
    return row

def _get_product_db_rules(conn, product_id: int, ds_key: str) -> "list[dict]":
    """(product, datasource) 의 **모든** 규칙(SortOrder, Id 순). 테이블 미존재 graceful → []."""
    if product_id <= 0 or not ds_key:
        return []
    cur = conn.cursor(dictionary=True)
    try:
        try:
            cur.execute(
                f"SELECT {app._DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules "
                "WHERE ProductId=%s AND LOWER(DatasourceKey)=%s ORDER BY SortOrder ASC, Id ASC",
                (int(product_id), str(ds_key).strip().lower()))
        except Exception:
            # SortOrder 컬럼 부재(마이그레이션 전) → Id 순.
            cur.execute(
                f"SELECT {app._DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules "
                "WHERE ProductId=%s AND LOWER(DatasourceKey)=%s ORDER BY Id ASC",
                (int(product_id), str(ds_key).strip().lower()))
        rows = cur.fetchall() or []
    except Exception:
        return []
    finally:
        cur.close()
    return [app._normalize_db_rule_row(r) for r in rows]

def _get_db_rule_by_id(conn, rule_id: int) -> "dict | None":
    """규칙 1건 Id 조회(엔드포인트 per-rule 동작용). 테이블 미존재 graceful → None."""
    if int(rule_id or 0) <= 0:
        return None
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(f"SELECT {app._DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules WHERE Id=%s LIMIT 1",
                    (int(rule_id),))
        row = cur.fetchone()
    except Exception:
        return None
    finally:
        cur.close()
    return app._normalize_db_rule_row(row)

def _touch_db_rule_sync(conn, rule_id: int) -> None:
    try:
        cur = conn.cursor()
        cur.execute("UPDATE WebProductDatasourceDbRules SET LastSyncAt=CURRENT_TIMESTAMP WHERE Id=%s", (int(rule_id),))
        cur.close()
    except Exception:
        pass

def _rule_to_public(rule: dict) -> dict:
    return {
        "id": int(rule.get("id") or 0),
        "include_pattern": str(rule.get("include_pattern") or ""),
        "exclude_pattern": (str(rule["exclude_pattern"]) if rule.get("exclude_pattern") else ""),
        "cap": int(rule.get("cap") or 3),
        "is_enabled": bool(rule.get("is_enabled")),
        "last_sync_at": str(rule.get("last_sync_at") or ""),
    }

async def _prompt_generate_json_response(ctx: dict, *, log_label: str, log_ctx: str) -> JSONResponse:
    """자동작성 비스트리밍 코어 — ctx(create_kwargs 등)로 LLM 1회 호출 후 {prompt, meta} 반환.

    product/role/account 엔드포인트가 공유한다. log_label/log_ctx 는 잘림 경고 로그 식별용
    (예: log_label='admin_generate_role_prompt_stream', log_ctx='role_id=3').
    """
    openai_client = ctx["openai_client"]
    create_kwargs = ctx["create_kwargs"]
    _aiops_model = str(ctx.get("llm_model") or "")

    def _aiops_create_and_record():
        # AI 운영 관제 계측(TASK-AIOPS): create + 회계를 둘 다 executor 스레드에서 실행 →
        # uvicorn 이벤트 루프에서 동기 PG I/O 금지. 순수 API 왕복 지연만 측정.
        _t0 = time.perf_counter_ns()
        r = openai_client.chat.completions.create(**create_kwargs)
        try:
            from modules.llm import _record_llm_usage
            _record_llm_usage(
                _aiops_model, "prompt_gen", r, conversation_id=None,
                latency_ms=int((time.perf_counter_ns() - _t0) // 1_000_000),
            )
        except Exception:
            pass
        return r

    try:
        resp = await asyncio.get_event_loop().run_in_executor(None, _aiops_create_and_record)
        choice = resp.choices[0]
        generated = choice.message.content or ""
        # TASK-0232: max_tokens 도달로 본문이 잘렸는지 명시 검출 — 조용한 잘림 방지.
        finish_reason = getattr(choice, "finish_reason", None)
        truncated = finish_reason == "length"
        if truncated:
            logging.getLogger(__name__).warning(
                "%s truncated (finish_reason=length, model=%s, max_tokens=%s, %s)",
                log_label, ctx["llm_model"], ctx["max_tokens"], log_ctx,
            )
    except Exception as llm_exc:
        return app._json_error(f"LLM 생성 실패: {llm_exc}", 502)
    return JSONResponse(
        {"prompt": generated.strip(), "meta": {**ctx["meta_base"], "truncated": truncated}}
    )

def _clean_insight_segment(text: str) -> str:
    """insight text_content('schema domain: X / summary / usage / key columns: ...')에서 사람용 본문만 추출.
    '... domain: ...' 선두 라벨과 'key columns: ...' 꼬리를 떼어 summary/usage 만 ' · ' 로 잇는다."""
    segs = [s.strip() for s in str(text or "").split(" / ") if s.strip()]
    body = []
    for s in segs:
        low = s.lower()
        if low.startswith("key columns"):
            continue
        if " domain:" in low or low.startswith("domain:"):
            continue
        body.append(s)
    return " · ".join(body)


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (7종). app 전역은 app.X 동적 참조. ====

def _resolve_product_insight_scope(conn, product: dict) -> dict:
    """제품의 datasource scope 식별자를 해석한다 (TASK-0223 완료율 / TASK-0228 초기화 공용).

    완료율 분자 조회와 초기화 삭제가 **동일한 scope/allow_null/engine** 을 쓰도록 단일 출처로 분리한다
    (키 불일치로 인한 "지웠는데 완료율 그대로" / "엉뚱한 DB 삭제" 방지).

    반환: {ok: bool, reason: str, scope: str|None, allow_null: bool, engine: str,
           default_db: str|None, coords: dict|None}. ok=False 면 reason 만 의미 있음.
    """
    from shared import datasources as _dsr
    label = product.get("datasource_key")  # 라벨(소문자) 또는 None
    default_endpoint_scope = _dsr.compute_scope_key("mysql", app.DB_HOST, int(app.DB_PORT))
    out = {
        "ok": False, "reason": "", "scope": None, "allow_null": False,
        "engine": "mysql", "default_db": None, "coords": None,
    }
    coords = None
    engine = "mysql"
    scope = None
    default_db = None
    if label:
        try:
            coords = _dsr.resolve(conn, str(label).strip().lower())
        except Exception:
            coords = None
        if not coords:
            out["reason"] = "데이터소스 해석 불가(미등록/복호 실패)"
            return out
        engine = (coords.get("engine") or "mysql").strip().lower()
        scope = _dsr.scope_key(coords)  # 해시(또는 .env 레거시 라벨 폴백) — insight write 와 동일 식별자
        default_db = (str(coords.get("default_db") or "").strip() or None)
    else:
        # 라벨 NULL = 레거시 기본 MySQL. 같은 엔드포인트 등록 datasource 가 있으면 그 좌표 사용.
        try:
            for _k, _v in (_dsr.all_datasources(conn) or {}).items():
                if _v and _dsr.scope_key(_v) == default_endpoint_scope:
                    coords = _v
                    engine = (coords.get("engine") or "mysql").strip().lower()
                    scope = default_endpoint_scope
                    default_db = (str(coords.get("default_db") or "").strip() or None)
                    break
        except Exception:
            coords = None
        if not coords:
            out["reason"] = "기본(미바인딩) 제품 — 데이터소스 좌표 없음"
            return out

    # TASK-0230 (M2): 같은 엔드포인트가 시기별로 다른 scope 식별자로 기록될 수 있다(hash vs .env 레거시
    # label vs NULL). 완료율은 단일 scope 만 보지만, **초기화(fingerprint 삭제)는 모든 alias 를 지워야**
    # worker 가 다른 alias 의 잔존 fingerprint 로 재분석을 skip 하지 않는다. coords 의 host/port 로
    # compute_scope_key(hash) 와 .env label(있으면) 을 둘 다 alias 후보로 모은다.
    scope_aliases: list[str] = []
    if scope:
        scope_aliases.append(str(scope).strip().lower())
    try:
        _h = coords.get("host")
        _p = int(coords.get("port") or 0)
        if _h and _p:
            _hash_alias = _dsr.compute_scope_key(engine, _h, _p)
            if _hash_alias and _hash_alias.strip().lower() not in scope_aliases:
                scope_aliases.append(_hash_alias.strip().lower())
    except Exception:
        pass
    # .env 레거시 label (datasource 키 자체가 scope 로 쓰였던 경우 — 예: main_mysql)
    if label and str(label).strip().lower() not in scope_aliases:
        scope_aliases.append(str(label).strip().lower())

    out.update({
        "ok": True, "scope": scope,
        # scope == 기본 엔드포인트면 ds=None 스캔의 NULL 행도 같은 DB → 허용(완료율 set dedup·초기화 OR NULL).
        "allow_null": (scope == default_endpoint_scope),
        "scope_aliases": scope_aliases,  # 초기화 전용 — 완료율은 단일 scope 사용
        "engine": engine, "default_db": default_db, "coords": coords,
    })
    return out

def _list_products(conn, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    where = "" if include_inactive else " WHERE IsActive = 1"
    # TASK-0053: DefaultRoleAccess (product 가 자체 정책의 주체) 컬럼도 함께 SELECT.
    cur.execute(
        f"""
SELECT Id AS id, ProductKey AS product_key, Name AS name, Description AS description,
       IsActive AS is_active, IsDefault AS is_default, SortOrder AS sort_order,
       DefaultRoleAccess AS default_role_access, DatasourceKey AS datasource_key,
       IconObjectKey AS icon_object_key,
       CreatedAt AS created_at, UpdatedAt AS updated_at
FROM WebProducts
{where}
ORDER BY IsDefault DESC, SortOrder ASC, Id ASC
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        _dsk = row.get("datasource_key")
        _pid = int(row.get("id") or 0)
        # TASK-0228 (1:N): 제품에 바인딩된 전체 datasource 목록(primary 포함). 단일 바인딩 제품은 1건.
        _ds_list = app._list_product_datasources(conn, _pid) if _pid else []
        out.append({
            "id": _pid,
            "product_key": str(row.get("product_key") or ""),
            "name": str(row.get("name") or ""),
            "description": str(row.get("description") or ""),
            "is_active": bool(row.get("is_active")),
            "is_default": bool(row.get("is_default")),
            "sort_order": int(row.get("sort_order") or 0),
            "default_role_access": bool(row.get("default_role_access", True)),
            # 멀티 datasource (P2): primary datasource 키 (None=기본 단일 MySQL). 하위호환 단일 필드.
            "datasource_key": (str(_dsk).lower() if _dsk else None),
            # TASK-0228 (1:N): 전체 바인딩 목록 [{datasource_key, is_primary, sort_order}].
            "datasources": _ds_list,
            # TASK-0268: 제품 아이콘 이미지 URL(설정 시) — 미설정 시 None → 프론트 Identicon/기본.
            "icon_url": app._product_icon_url_for(_pid, row.get("icon_object_key")),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })
    return out

def _list_product_databases(conn, product_id: int) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    # TASK-0228 (1:N): DatasourceKey 차원 포함(미이전 스키마는 컬럼 부재 → 폴백). UI 가 datasource 별 그룹핑.
    try:
        cur.execute(
            """
SELECT SchemaName AS schema_name, Description AS description, SortOrder AS sort_order,
       LOWER(DatasourceKey) AS datasource_key, COALESCE(Source,'manual') AS source, RuleId AS rule_id
FROM WebProductDatabases
WHERE ProductId = %s
ORDER BY DatasourceKey ASC, SortOrder ASC, SchemaName ASC
            """,
            (int(product_id),),
        )
        rows = cur.fetchall() or []
    except Exception:
        cur.execute(
            """
SELECT SchemaName AS schema_name, Description AS description, SortOrder AS sort_order
FROM WebProductDatabases
WHERE ProductId = %s
ORDER BY SortOrder ASC, SchemaName ASC
            """,
            (int(product_id),),
        )
        rows = cur.fetchall() or []
    cur.close()
    return [
        {
            "schema_name": str(r.get("schema_name") or ""),
            "description": str(r.get("description") or ""),
            "sort_order": int(r.get("sort_order") or 0),
            # 미이전 행은 datasource_key 키 부재 → 빈 문자열(레거시 단일 차원).
            "datasource_key": (str(r.get("datasource_key") or "") or None),
            # TASK-20260618T044318: manual(수동) / rule(규칙 자동) 구분 — 미이전 행은 manual.
            "source": (str(r.get("source") or "manual") if "source" in r else "manual"),
            # TASK-20260618T061703: 다중 규칙 — 어느 규칙이 추가했는지(UI 가 규칙 카드에 종속 표시).
            "rule_id": (int(r["rule_id"]) if r.get("rule_id") is not None else None),
        }
        for r in rows
    ]

def _insight_worker_liveness(conn) -> dict:
    """insight-worker 생존 신호 (heartbeat KV) — db-insights 의 '분석중' 상태 판정용.

    반환: {"alive": bool, "age_sec": int|None, "status": str}.
    alive = last_status ∈ {ok, skip_locked} AND age ≤ max(30, STALE_SEC) (insight._is_*_heartbeat_fresh 와 정합).
    """
    from shared.config import GLOBAL_CONVERSATION_ID
    try:
        from shared.config import AGENT_INSIGHT_WORKER_STALE_SEC as _stale
    except Exception:
        _stale = 15
    out = {"alive": False, "age_sec": None, "status": ""}
    try:
        raw = app.load_memory_kv(conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at")
        status = (app.load_memory_kv(conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_status") or "").strip().lower()
        out["status"] = status
        if raw:
            ts = str(raw).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
            out["age_sec"] = age
            if status in {"ok", "skip_locked"} and age <= max(30, int(_stale)):
                out["alive"] = True
    except Exception:
        pass
    return out

def _insight_cov_cache_get(key):
    import time as _time
    with app._INSIGHT_COVERAGE_CACHE_LOCK:
        ent = app._INSIGHT_COVERAGE_CACHE.get(key)
        if not ent:
            return None
        ts, val = ent
        if (_time.time() - ts) > app._INSIGHT_COVERAGE_TTL_SEC:
            app._INSIGHT_COVERAGE_CACHE.pop(key, None)
            return None
        return val

def _insight_cov_cache_put(key, val):
    import time as _time
    with app._INSIGHT_COVERAGE_CACHE_LOCK:
        if len(app._INSIGHT_COVERAGE_CACHE) > 500:  # 단순 상한(누수 방지)
            app._INSIGHT_COVERAGE_CACHE.clear()
        app._INSIGHT_COVERAGE_CACHE[key] = (_time.time(), val)

def _read_insight_datasource_health() -> dict:
    """TASK-0255 R2: insight-worker 가 PG(agent_runtime.datasource_health)에 영속한 datasource 연결 health 를
    scope_key→dict 로 읽는다. 관리콘솔이 web 의 live conn_health(conn_status)와 **별개로** insight 스캔 관점의
    상태 — "연결 불안정으로 미커버"(status=unstable / scan_outcome=circuit_open) vs "권한 실패"(perm_failed) —
    를 구분 표시하기 위함. graceful: PG 미가용/테이블 부재(fresh deploy 마이그 전)/조회 실패는 {} 반환(목록 무영향).
    RO 연결(least-privilege). 자격증명 비포함(테이블에 애초 비영속)."""
    try:
        from shared.db import _pg_available, _pg_connect_ro
    except Exception:
        return {}
    if not _pg_available():
        return {}
    out: dict = {}
    conn = None
    try:
        conn = _pg_connect_ro()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT scope_key, status, last_scan_outcome, fail_count, last_error_tag, "
                "last_checked_at, last_scan_at, last_transition_at "
                "FROM agent_runtime.datasource_health"
            )
            for r in (cur.fetchall() or []):
                out[str(r[0])] = {
                    "status": r[1],
                    "scan_outcome": r[2],
                    "fail_count": int(r[3] or 0),
                    "last_error_tag": r[4],
                    "last_checked_at": (r[5].isoformat() if r[5] else None),
                    "last_scan_at": (r[6].isoformat() if r[6] else None),
                    "last_transition_at": (r[7].isoformat() if r[7] else None),
                }
        finally:
            cur.close()
    except Exception as exc:
        # 테이블 부재(마이그 전)/권한/PG down — soft, datasource 목록은 그대로. 진단용 debug 1줄(자격증명 비포함).
        logging.getLogger(__name__).debug("insight_datasource_health_query_failed: %s", type(exc).__name__)
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return out


# ==== feature-0012 ITEM-10 p17 — app.py 에서 이동한 도메인 상수 (1종). ====

_DB_RULE_SELECT_COLS = (
    "Id AS id, ProductId AS product_id, LOWER(DatasourceKey) AS datasource_key, "
    "IncludePattern AS include_pattern, ExcludePattern AS exclude_pattern, Cap AS cap, "
    "IsEnabled AS is_enabled, CreatedByAccountId AS created_by_account_id, LastSyncAt AS last_sync_at"
)
