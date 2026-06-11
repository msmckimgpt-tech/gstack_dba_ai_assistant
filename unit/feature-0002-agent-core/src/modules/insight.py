import uuid
import hashlib
import random
import re
import time
__all__ = [
    "_bootstrap_schema_insights",
    "_is_insight_worker_heartbeat_fresh",
    "_new_insight_worker_run_id",
    "_scan_instance_schema_insights",
    "_should_run_inline_insight_scan",
    "run_insight_cycle",
    "run_insight_worker_loop",
]


"""Schema/table insight scanning, bootstrap, background worker."""
from .config import *
import hashlib, json, logging, random, re, time, uuid
from datetime import datetime, timezone
from typing import Any

from . import dialects as _dialects  # P7: insight 컬럼 핑거프린트 dialect 분기(MSSQL)
from . import db as _db              # P7 follow-up: datasource 지원 connect_with_retry 명시 사용


# ---------------------------------------------------------------------------
# Fingerprint-based change detection
# ---------------------------------------------------------------------------

def _compute_schema_fingerprint(db_conn, schema: str) -> str:
    """스키마의 테이블 목록으로 핑거프린트를 계산한다."""
    cur = db_conn.cursor()
    try:
        cur.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
            (schema,),
        )
        rows = cur.fetchall() or []
        names = sorted(str(r[0]).strip() for r in rows if r and r[0])
        return hashlib.sha256("|".join(names).encode()).hexdigest()[:32]
    finally:
        cur.close()


def _compute_table_fingerprint(db_conn, schema: str, table: str) -> str:
    """테이블의 컬럼 이름+타입으로 핑거프린트를 계산한다."""
    cur = db_conn.cursor()
    try:
        cur.execute(
            f"SELECT {_dialects.active().fingerprint_column_projection()} "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (schema, table),
        )
        rows = cur.fetchall() or []
        parts = []
        for r in rows:
            parts.append(":".join(str(c or "").strip() for c in r))
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
    finally:
        cur.close()


def _compute_table_fingerprints_batch(db_conn, schema: str, tables: list[str]) -> dict[str, str]:
    """여러 테이블의 핑거프린트를 한 번의 쿼리로 계산한다."""
    if not tables:
        return {}
    cur = db_conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(tables))
        cur.execute(
            f"SELECT TABLE_NAME, {_dialects.active().fingerprint_column_projection()} "
            f"FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders}) "
            f"ORDER BY TABLE_NAME, ORDINAL_POSITION",
            [schema] + tables,
        )
        rows = cur.fetchall() or []
        table_parts: dict[str, list[str]] = {}
        for r in rows:
            tname = str(r[0] or "").strip()
            if not tname:
                continue
            part = ":".join(str(c or "").strip() for c in r[1:])
            table_parts.setdefault(tname, []).append(part)
        result = {}
        for tname, parts in table_parts.items():
            result[tname] = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
        return result
    finally:
        cur.close()


def _load_stored_fingerprints(mem_conn, prefix: str) -> dict[str, str]:
    """KV에서 특정 prefix의 핑거프린트들을 로드한다."""
    return _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, prefix)


def _save_fingerprint(mem_conn, key: str, fingerprint: str) -> None:
    """핑거프린트를 KV에 저장한다."""
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, key, fingerprint)
    except Exception:
        pass


def _insight_target_conversation_id() -> str:
    return str(GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID or "").strip()


def _empty_insight_artifact_state(fact_key: str) -> dict[str, Any]:
    return {
        "fact_key": str(fact_key or "").strip(),
        "has_fact": False,
        "has_text": False,
        "has_rag_document": False,
        "has_rag_object": False,
        "conversation_id": "",
        "scope_key": FACT_SCOPE_COMMON,
        "fact_text": "",
        "repair_text": "",
        "weight": 4,
        "source_type": "schema_insight",
        "source_run_id": "",
        "source_sql": "",
    }


def _remember_repair_text(state: dict[str, Any], text: str) -> None:
    candidate = str(text or "").strip()
    if candidate and not str(state.get("repair_text") or "").strip():
        state["repair_text"] = candidate


# 검증 read-back 실패를 가시화하기 위한 1회성 경고 마커. 과거엔 각 쿼리가
# `except Exception: rows = []` 로 오류를 조용히 삼켜, backend drift(예: 05-27
# cutover 로 MySQL AgentMemory* 테이블이 DROP)가 "artifact 전부 missing" 으로
# 오인되어 insight 무한 재생성(livelock)을 일으켜도 어떤 신호도 남지 않았다.
_INSIGHT_READBACK_WARNED: set[str] = set()


def _warn_insight_readback_failed(stage: str, exc: Exception) -> None:
    """insight artifact 검증 read-back 실패를 insight_worker 로그에 1회 surface."""
    if stage in _INSIGHT_READBACK_WARNED:
        return
    _INSIGHT_READBACK_WARNED.add(stage)
    try:
        append_log_line(
            "insight_worker",
            json.dumps(
                {
                    "event": "insight_artifact_readback_failed",
                    "stage": stage,
                    "error": str(exc)[:200],
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        pass


def _build_insight_object_maps(
    keys: list[str],
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """fact_key → (schema rag-object, table rag-object) 매핑을 만든다 (backend 무관)."""
    schema_object_map: dict[str, str] = {}
    table_object_map: dict[tuple[str, str], str] = {}
    for fact_key in keys:
        object_type, _, schema_name, table_name, _ = _infer_rag_object_from_fact(fact_key, "")
        if object_type == "schema" and schema_name:
            schema_object_map[schema_name] = fact_key
        elif object_type == "table" and schema_name and table_name:
            table_object_map[(schema_name, table_name)] = fact_key
    return schema_object_map, table_object_map


def _apply_insight_fact_rows(states: dict[str, dict[str, Any]], rows: list) -> None:
    """fact_entries 행 → state(has_fact/has_text/meta). MySQL·PG 공용 (컬럼 순서 동일)."""
    seen_fact_keys: set[str] = set()
    for row in rows:
        fact_key = str(row[0] or "").strip()
        if not fact_key or fact_key in seen_fact_keys:
            continue
        seen_fact_keys.add(fact_key)
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        fact_text = str(row[3] or "").strip()
        state["has_fact"] = True
        state["conversation_id"] = str(row[1] or "").strip()
        state["scope_key"] = str(row[2] or "").strip() or FACT_SCOPE_COMMON
        state["fact_text"] = fact_text
        state["weight"] = int(row[4]) if row[4] is not None else 4
        state["source_type"] = str(row[5] or "").strip() or "schema_insight"
        state["source_run_id"] = str(row[6] or "").strip()
        state["source_sql"] = str(row[7] or "").strip()
        if fact_text:
            state["has_text"] = True
            _remember_repair_text(state, fact_text)


def _apply_insight_doc_rows(states: dict[str, dict[str, Any]], rows: list) -> None:
    """rag_documents 행 → state(has_rag_document/has_text). MySQL·PG 공용."""
    seen_doc_keys: set[str] = set()
    for row in rows:
        fact_key = str(row[0] or "").strip()
        if not fact_key or fact_key in seen_doc_keys:
            continue
        seen_doc_keys.add(fact_key)
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        doc_text = str(row[1] or "").strip()
        state["has_rag_document"] = True
        if doc_text:
            state["has_text"] = True
            _remember_repair_text(state, doc_text)


def _apply_insight_schema_object_rows(
    states: dict[str, dict[str, Any]], rows: list, schema_object_map: dict[str, str]
) -> None:
    """schema rag_objects 행 → state(has_rag_object/has_text). MySQL·PG 공용."""
    seen_schema_objects: set[str] = set()
    for row in rows:
        schema_name = str(row[0] or "").strip()
        if not schema_name or schema_name in seen_schema_objects:
            continue
        seen_schema_objects.add(schema_name)
        fact_key = schema_object_map.get(schema_name)
        if not fact_key:
            continue
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        object_text = str(row[1] or "").strip()
        state["has_rag_object"] = True
        if object_text:
            state["has_text"] = True
            _remember_repair_text(state, object_text)


def _apply_insight_table_object_rows(
    states: dict[str, dict[str, Any]], rows: list, table_object_map: dict[tuple[str, str], str]
) -> None:
    """table rag_objects 행 → state(has_rag_object/has_text). MySQL·PG 공용."""
    seen_table_objects: set[tuple[str, str]] = set()
    for row in rows:
        schema_name = str(row[0] or "").strip()
        table_name = str(row[1] or "").strip()
        key_ref = (schema_name, table_name)
        if not schema_name or not table_name or key_ref in seen_table_objects:
            continue
        seen_table_objects.add(key_ref)
        fact_key = table_object_map.get(key_ref)
        if not fact_key:
            continue
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        object_text = str(row[2] or "").strip()
        state["has_rag_object"] = True
        if object_text:
            state["has_text"] = True
            _remember_repair_text(state, object_text)


def _load_insight_artifact_states_pg(
    fact_keys: list[str],
) -> dict[str, dict[str, Any]] | None:
    """`_load_insight_artifact_states` 의 Postgres read-back 경로.

    `AGENT_KB_READ_BACKEND=postgres` 일 때 KB write 정본인 PG 테이블
    (public.fact_entries/rag_documents/rag_objects + texts join)에서 artifact 존재
    여부를 읽어, MySQL 경로와 동일한 state dict 를 만든다. `_pg_connect_ro()`
    (agent_kb_ro least-priv) 사용. PG 미가용이면 None 반환 → caller MySQL fallback.

    이 경로가 없으면 영속 검증이 (DROP 된) MySQL 테이블을 조회해 매 사이클 4-part
    전부 missing 으로 오판 → insight 무한 재생성(livelock)을 일으킨다."""
    keys = [str(key or "").strip() for key in (fact_keys or []) if str(key or "").strip()]
    states = {key: _empty_insight_artifact_state(key) for key in keys}
    if not keys:
        return states
    if not _pg_available():
        return None
    conversation_ids = _global_fact_conversation_ids(include_shared=True)
    if not conversation_ids:
        return states
    cid_placeholders = ",".join(["%s"] * len(conversation_ids))
    key_placeholders = ",".join(["%s"] * len(keys))
    scope_clause, scope_params = _scope_filter_sql_pg(_scope_candidates(FACT_SCOPE_COMMON))

    try:
        conn = _pg_connect_ro()
    except Exception as exc:
        _warn_insight_readback_failed("pg_connect", exc)
        return None
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT
    e.fact_key,
    e.conversation_id,
    e.scope_key,
    COALESCE(t.text_content, '') AS fact_text,
    e.weight,
    COALESCE(e.source_type, '') AS source_type,
    COALESCE(e.source_run_id, '') AS source_run_id,
    COALESCE(e.source_sql, '') AS source_sql
FROM public.fact_entries e
LEFT JOIN public.texts t ON t.text_hash = e.text_hash
WHERE e.conversation_id IN ({cid_placeholders})
  AND e.fact_key IN ({key_placeholders}){scope_clause}
ORDER BY e.fact_key, e.weight DESC, e.updated_at DESC, e.id DESC
                """,
                [*conversation_ids, *keys, *scope_params],
            )
            fact_rows = cur.fetchall() or []
        finally:
            cur.close()
        _apply_insight_fact_rows(states, fact_rows)

        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT
    d.fact_key,
    COALESCE(t.text_content, '') AS doc_text
FROM public.rag_documents d
LEFT JOIN public.texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id IN ({cid_placeholders})
  AND d.fact_key IN ({key_placeholders}){scope_clause}
ORDER BY d.fact_key, d.weight DESC, d.updated_at DESC, d.id DESC
                """,
                [*conversation_ids, *keys, *scope_params],
            )
            doc_rows = cur.fetchall() or []
        finally:
            cur.close()
        _apply_insight_doc_rows(states, doc_rows)

        schema_object_map, table_object_map = _build_insight_object_maps(keys)

        if schema_object_map:
            cur = conn.cursor()
            try:
                schema_placeholders = ",".join(["%s"] * len(schema_object_map))
                cur.execute(
                    f"""
SELECT
    o.schema_name,
    COALESCE(t.text_content, '') AS object_text
FROM public.rag_objects o
LEFT JOIN public.texts t ON t.text_hash = o.text_hash
WHERE o.conversation_id IN ({cid_placeholders})
  AND o.object_type = 'schema'
  AND o.schema_name IN ({schema_placeholders}){scope_clause}
ORDER BY o.schema_name, o.weight DESC, o.updated_at DESC, o.id DESC
                    """,
                    [*conversation_ids, *schema_object_map.keys(), *scope_params],
                )
                schema_rows = cur.fetchall() or []
            finally:
                cur.close()
            _apply_insight_schema_object_rows(states, schema_rows, schema_object_map)

        if table_object_map:
            cur = conn.cursor()
            table_filters = []
            table_params: list[str] = []
            for schema_name, table_name in table_object_map.keys():
                table_filters.append("(o.schema_name = %s AND o.table_name = %s)")
                table_params.extend([schema_name, table_name])
            try:
                cur.execute(
                    f"""
SELECT
    o.schema_name,
    o.table_name,
    COALESCE(t.text_content, '') AS object_text
FROM public.rag_objects o
LEFT JOIN public.texts t ON t.text_hash = o.text_hash
WHERE o.conversation_id IN ({cid_placeholders})
  AND o.object_type = 'table'
  AND ({' OR '.join(table_filters)}){scope_clause}
ORDER BY o.schema_name, o.table_name, o.weight DESC, o.updated_at DESC, o.id DESC
                    """,
                    [*conversation_ids, *table_params, *scope_params],
                )
                table_rows = cur.fetchall() or []
            finally:
                cur.close()
            _apply_insight_table_object_rows(states, table_rows, table_object_map)
    except Exception as exc:
        # PG read 실패 → 가시화 후 None 반환(caller MySQL fallback, cutover 미완 안전망).
        _warn_insight_readback_failed("pg_query", exc)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return states


def _load_insight_artifact_states(mem_conn, fact_keys: list[str]) -> dict[str, dict[str, Any]]:
    keys = [str(key or "").strip() for key in (fact_keys or []) if str(key or "").strip()]
    states = {key: _empty_insight_artifact_state(key) for key in keys}
    if not keys:
        return states
    # 05-27 cutover 이후 KB write 정본은 Postgres(public.fact_entries/rag_documents/
    # rag_objects/texts)다. MySQL AgentMemory* 테이블은 DROP 되어 더 이상 존재하지
    # 않으므로 영속 검증 read-back 도 동일 backend(PG)에서 읽어야 한다. 이 분기가
    # 없으면 매 사이클 4-part 전부 missing 으로 오판 → insight 무한 재생성(livelock).
    from .config import AGENT_KB_READ_BACKEND
    if AGENT_KB_READ_BACKEND == "postgres":
        pg_states = _load_insight_artifact_states_pg(keys)
        if pg_states is not None:
            return pg_states
        # PG 미가용 → 아래 MySQL fallback (cutover 미완 환경 안전망)
    if not mem_conn:
        return states
    conversation_ids = _global_fact_conversation_ids(include_shared=True)
    if not conversation_ids:
        return states
    cid_placeholders = ",".join(["%s"] * len(conversation_ids))
    key_placeholders = ",".join(["%s"] * len(keys))
    scope_clause, scope_params = _scope_filter_sql(_scope_candidates(FACT_SCOPE_COMMON))

    cur = mem_conn.cursor()
    try:
        cur.execute(
            f"""
SELECT
    e.FactKey,
    e.ConversationId,
    e.ScopeKey,
    COALESCE(t.TextContent, '') AS FactText,
    e.Weight,
    COALESCE(e.SourceType, '') AS SourceType,
    COALESCE(e.SourceRunId, '') AS SourceRunId,
    COALESCE(e.SourceSql, '') AS SourceSql
FROM AgentMemoryFactEntries e
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash
WHERE e.ConversationId IN ({cid_placeholders})
  AND e.FactKey IN ({key_placeholders}){scope_clause}
ORDER BY e.FactKey, e.Weight DESC, e.UpdatedAt DESC, e.Id DESC
            """,
            [*conversation_ids, *keys, *scope_params],
        )
        rows = cur.fetchall() or []
    except Exception as exc:
        _warn_insight_readback_failed("mysql_fact", exc)
        rows = []
    finally:
        cur.close()
    _apply_insight_fact_rows(states, rows)

    cur = mem_conn.cursor()
    try:
        cur.execute(
            f"""
SELECT
    d.FactKey,
    COALESCE(t.TextContent, '') AS DocText
FROM AgentMemoryRagDocuments d
LEFT JOIN AgentMemoryTexts t ON t.TextHash = d.TextHash
WHERE d.ConversationId IN ({cid_placeholders})
  AND d.FactKey IN ({key_placeholders}){scope_clause}
ORDER BY d.FactKey, d.Weight DESC, d.UpdatedAt DESC, d.Id DESC
            """,
            [*conversation_ids, *keys, *scope_params],
        )
        rows = cur.fetchall() or []
    except Exception as exc:
        _warn_insight_readback_failed("mysql_doc", exc)
        rows = []
    finally:
        cur.close()
    _apply_insight_doc_rows(states, rows)

    schema_object_map, table_object_map = _build_insight_object_maps(keys)

    if schema_object_map:
        cur = mem_conn.cursor()
        try:
            schema_placeholders = ",".join(["%s"] * len(schema_object_map))
            cur.execute(
                f"""
SELECT
    o.SchemaName,
    COALESCE(t.TextContent, '') AS ObjectText
FROM AgentMemoryRagObjects o
LEFT JOIN AgentMemoryTexts t ON t.TextHash = o.TextHash
WHERE o.ConversationId IN ({cid_placeholders})
  AND o.ObjectType = 'schema'
  AND o.SchemaName IN ({schema_placeholders}){scope_clause}
ORDER BY o.SchemaName, o.Weight DESC, o.UpdatedAt DESC, o.Id DESC
                """,
                [*conversation_ids, *schema_object_map.keys(), *scope_params],
            )
            rows = cur.fetchall() or []
        except Exception as exc:
            _warn_insight_readback_failed("mysql_schema_obj", exc)
            rows = []
        finally:
            cur.close()
        _apply_insight_schema_object_rows(states, rows, schema_object_map)

    if table_object_map:
        cur = mem_conn.cursor()
        table_filters = []
        table_params: list[str] = []
        for schema_name, table_name in table_object_map.keys():
            table_filters.append("(o.SchemaName = %s AND o.TableName = %s)")
            table_params.extend([schema_name, table_name])
        try:
            cur.execute(
                f"""
SELECT
    o.SchemaName,
    o.TableName,
    COALESCE(t.TextContent, '') AS ObjectText
FROM AgentMemoryRagObjects o
LEFT JOIN AgentMemoryTexts t ON t.TextHash = o.TextHash
WHERE o.ConversationId IN ({cid_placeholders})
  AND o.ObjectType = 'table'
  AND ({' OR '.join(table_filters)}){scope_clause}
ORDER BY o.SchemaName, o.TableName, o.Weight DESC, o.UpdatedAt DESC, o.Id DESC
                """,
                [*conversation_ids, *table_params, *scope_params],
            )
            rows = cur.fetchall() or []
        except Exception as exc:
            _warn_insight_readback_failed("mysql_table_obj", exc)
            rows = []
        finally:
            cur.close()
        _apply_insight_table_object_rows(states, rows, table_object_map)

    return states


def _insight_artifact_complete(state: dict[str, Any] | None) -> bool:
    info = state or {}
    return bool(
        info.get("has_fact")
        and info.get("has_text")
        and info.get("has_rag_document")
        and info.get("has_rag_object")
    )


def _insight_missing_parts(state: dict[str, Any] | None) -> list[str]:
    info = state or {}
    missing: list[str] = []
    if not info.get("has_fact"):
        missing.append("fact")
    if not info.get("has_text"):
        missing.append("text")
    if not info.get("has_rag_document"):
        missing.append("rag_document")
    if not info.get("has_rag_object"):
        missing.append("rag_object")
    return missing


def _detect_pending_insight_repairs(
    db_conn,
    mem_conn,
    schemas: list[str],
) -> dict[str, int]:
    report = {
        "pending_schema_repairs": 0,
        "pending_table_repairs": 0,
    }
    schema_names = [str(s or "").strip() for s in (schemas or [])]
    schema_names = [s for s in schema_names if s and not _is_system_schema(s)]
    if not db_conn or not mem_conn or not schema_names:
        return report

    schema_keys = [ds_fact_key("schema_insight", schema) for schema in schema_names]
    schema_states = _load_insight_artifact_states(mem_conn, schema_keys)
    for schema in schema_names:
        schema_key = ds_fact_key("schema_insight", schema)
        if not _insight_artifact_complete(
            schema_states.get(schema_key, _empty_insight_artifact_state(schema_key))
        ):
            report["pending_schema_repairs"] += 1

    cur = db_conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(schema_names))
        cur.execute(
            f"""
SELECT TABLE_SCHEMA, TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA IN ({placeholders})
ORDER BY TABLE_SCHEMA, TABLE_NAME
            """,
            schema_names,
        )
        rows = cur.fetchall() or []
    except Exception:
        rows = []
    finally:
        cur.close()

    table_keys: list[str] = []
    for row in rows:
        if not row:
            continue
        schema_name = str(row[0] or "").strip()
        table_name = str(row[1] or "").strip()
        if not schema_name or not table_name:
            continue
        table_keys.append(ds_fact_key("table_insight", f"{schema_name}.{table_name}"))

    if not table_keys:
        return report

    table_states = _load_insight_artifact_states(mem_conn, table_keys)
    for table_key in table_keys:
        if not _insight_artifact_complete(
            table_states.get(table_key, _empty_insight_artifact_state(table_key))
        ):
            report["pending_table_repairs"] += 1
    return report


def _build_insight_references(
    schema: str,
    table: str | None = None,
    col_names: list[str] | None = None,
    table_names: list[str] | None = None,
) -> list[str]:
    refs: list[str] = []
    schema_name = str(schema or "").strip()
    table_name = str(table or "").strip()
    if schema_name:
        refs.append(f"schema:{schema_name}")
    if table_name:
        refs.append(f"table:{schema_name}.{table_name}" if schema_name else f"table:{table_name}")
    max_candidates = max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))
    if table_name:
        for col_name in col_names or []:
            name = str(col_name or "").strip()
            if not name:
                continue
            refs.append(
                f"column:{schema_name}.{table_name}.{name}"
                if schema_name
                else f"column:{table_name}.{name}"
            )
            if len(refs) >= 2 + max_candidates:
                break
    else:
        for hint in table_names or []:
            name = str(hint or "").strip()
            if not name:
                continue
            refs.append(f"table:{schema_name}.{name}" if schema_name else f"table:{name}")
            if len(refs) >= 1 + max_candidates:
                break
    return refs


def _trace_insight_worker_event(
    run_id: str | None,
    phase: str,
    schema: str,
    object_type: str,
    object_name: str,
    reason: str,
    action: str,
    referenced_objects: list[str] | None = None,
    result: str = "",
    duration_ms: float | None = None,
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": utc_now_iso(),
        "run_id": str(run_id or "").strip(),
        "phase": str(phase or "").strip(),
        "schema": str(schema or "").strip(),
        "object_type": str(object_type or "").strip(),
        "object_name": str(object_name or "").strip(),
        "reason": str(reason or "").strip(),
        "action": str(action or "").strip(),
        "referenced_objects": referenced_objects or [],
        "result": str(result or "").strip(),
        "duration_ms": round(float(duration_ms or 0.0), 2),
        "error": str(error or "").strip()[:500],
    }
    if extra:
        payload.update(extra)
    log_insight_route("insight_worker", payload)


def _repair_insight_artifacts_from_state(
    mem_conn,
    fact_key: str,
    state: dict[str, Any],
    run_id: str | None,
    schema: str,
    object_type: str,
    object_name: str,
    referenced_objects: list[str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    current = dict(state or {})
    repair_text = str(current.get("repair_text") or current.get("fact_text") or "").strip()
    missing_parts = _insight_missing_parts(current)
    if not repair_text:
        _trace_insight_worker_event(
            run_id,
            "publish",
            schema,
            object_type,
            object_name,
            "artifact_missing",
            "repair_from_fact",
            referenced_objects=referenced_objects,
            result="unavailable",
            extra={"missing_parts": missing_parts},
        )
        return False, current
    started = time.perf_counter()
    try:
        _upsert_fact(
            mem_conn,
            str(current.get("conversation_id") or _insight_target_conversation_id()).strip()
            or _insight_target_conversation_id(),
            fact_key,
            repair_text,
            int(current.get("weight") or 4),
            scope_key=str(current.get("scope_key") or FACT_SCOPE_COMMON),
            source_type=str(current.get("source_type") or "schema_insight") or "schema_insight",
            source_run_id=str(current.get("source_run_id") or run_id or "").strip() or None,
            source_sql=str(current.get("source_sql") or "").strip() or None,
        )
        repaired = _load_insight_artifact_states(mem_conn, [fact_key]).get(
            fact_key, _empty_insight_artifact_state(fact_key)
        )
        complete = _insight_artifact_complete(repaired)
        _trace_insight_worker_event(
            run_id,
            "publish",
            schema,
            object_type,
            object_name,
            "artifact_missing",
            "repair_from_fact",
            referenced_objects=referenced_objects,
            result="ok" if complete else "partial_persist",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            extra={"missing_parts": _insight_missing_parts(repaired)},
        )
        return complete, repaired
    except Exception as exc:
        _trace_insight_worker_event(
            run_id,
            "publish",
            schema,
            object_type,
            object_name,
            "artifact_missing",
            "repair_from_fact",
            referenced_objects=referenced_objects,
            result="publish_failed",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            error=str(exc),
            extra={"missing_parts": missing_parts},
        )
        return False, current

def _bootstrap_schema_insights(
    db_conn,
    mem_conn,
    schemas: list[str],
    run_id: str | None = None,
) -> None:
    if not db_conn or not mem_conn or not AGENT_SCHEMA_BOOTSTRAP or not AGENT_SCHEMA_INSIGHT:
        return
    try:
        booted = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_insights_bootstrap_at")
        if booted:
            return
    except Exception:
        pass
    schema_list = [str(s or "").strip() for s in (schemas or [])]
    schema_list = [s for s in schema_list if s and not _is_system_schema(s)]
    if not schema_list:
        return
    existing_schema_insights = _load_existing_schema_insights(mem_conn)
    pending_schemas = [s for s in schema_list if s not in existing_schema_insights]
    seen_schemas = [s for s in schema_list if s in existing_schema_insights]
    schema_list = pending_schemas + seen_schemas
    existing_table_map = _load_existing_table_insight_map(mem_conn, schema_list)
    cur = db_conn.cursor()
    try:
        for schema in schema_list:
            cur.execute(
                """
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME
                """,
                (schema,),
            )
            rows = cur.fetchall() or []
            names = [str(r[0]).strip() for r in rows if r and r[0]]
            names = [n for n in names if n]
            if not names:
                continue
            seen_tables = existing_table_map.get(schema, set())
            pending = [t for t in names if t not in seen_tables]
            known = [t for t in names if t in seen_tables]
            prioritized = pending + known
            hints = prioritized[: max(1, int(AGENT_SCHEMA_BOOTSTRAP_MAX_TABLES))]
            if hints:
                _record_schema_insight_from_search(
                    mem_conn,
                    GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID,
                    schema,
                    hints,
                    source_run_id=run_id,
                )
    finally:
        cur.close()
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_insights_bootstrap_at", utc_now_iso())
    except Exception:
        pass


def _scan_instance_schema_insights(
    db_conn,
    mem_conn,
    schemas: list[str],
    run_id: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "scan_started": False,
        "schemas_evaluated": 0,
        "schemas_generated": 0,
        "schemas_repaired": 0,
        "tables_selected": 0,
        "tables_generated": 0,
        "tables_repaired": 0,
        "artifact_missing_selected": 0,
        "skipped_schemas": 0,
        "skipped_tables": 0,
        "deferred_tables": 0,
        "pending_schema_repairs": 0,
        "pending_table_repairs": 0,
        # TASK-0131 (#10): publish 실패(주로 LLM 호출 실패) 누적 — 사이클 status degrade 판정용.
        "publish_failed": 0,
    }
    if not db_conn or not mem_conn or not AGENT_SCHEMA_INSTANCE_SCAN or not AGENT_SCHEMA_INSIGHT:
        return report
    if not LLM_API_KEY or OpenAI is None:
        return report
    candidates = [str(s or "").strip() for s in (schemas or [])]
    candidates = [s for s in candidates if s and not _is_system_schema(s)]
    if not candidates:
        return report
    existing_schema_insights = _load_existing_schema_insights(mem_conn)
    missing = [schema for schema in candidates if schema not in existing_schema_insights]
    seen = [schema for schema in candidates if schema in existing_schema_insights]
    force_scan = bool(missing)
    candidates = missing + seen
    max_schemas = int(AGENT_SCHEMA_INSTANCE_SCAN_MAX_SCHEMAS or 0)
    if max_schemas > 0 and candidates:
        pick_limit = min(max_schemas, len(candidates))
        offset_key = ds_scope_name("schema_instance_scan_schema_offset")
        try:
            offset = int(load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key) or 0)
        except Exception:
            offset = 0
        if offset < 0:
            offset = 0
        if force_scan and missing:
            rotated_missing = _rotate_list(missing, offset)
            selected = rotated_missing[:pick_limit]
            if len(selected) < pick_limit and seen:
                rotated_seen = _rotate_list(seen, offset)
                selected.extend(rotated_seen[: pick_limit - len(selected)])
            candidates = selected
            base_len = len(missing) if missing else len(candidates)
        else:
            rotated_all = _rotate_list(candidates, offset)
            candidates = rotated_all[:pick_limit]
            base_len = len(rotated_all)
        if base_len > 0:
            step = pick_limit if base_len > pick_limit else 1
            new_offset = (offset + max(1, step)) % base_len
            try:
                save_memory_kv(
                    mem_conn, GLOBAL_CONVERSATION_ID, offset_key, str(new_offset)
                )
            except Exception:
                pass
    pending_repairs = _detect_pending_insight_repairs(db_conn, mem_conn, candidates)
    report["pending_schema_repairs"] = int(pending_repairs.get("pending_schema_repairs", 0) or 0)
    report["pending_table_repairs"] = int(pending_repairs.get("pending_table_repairs", 0) or 0)
    force_scan = bool(
        missing
        or report["pending_schema_repairs"]
        or report["pending_table_repairs"]
    )
    if not force_scan:
        try:
            last_scan = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, ds_scope_name("schema_instance_scan_at"))
            parsed = _parse_iso_time(str(last_scan)) if last_scan else None
            if parsed:
                elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()
                if elapsed < max(5, AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC):
                    return report
        except Exception:
            pass

    report["scan_started"] = True
    stored_schema_fps = _load_stored_fingerprints(mem_conn, "schema_fp:")
    stored_table_fps = _load_stored_fingerprints(mem_conn, "table_fp:")

    cur = db_conn.cursor()
    scan_start = time.perf_counter()
    budget_sec = max(5, int(AGENT_SCHEMA_INSTANCE_SCAN_BUDGET_SEC))
    table_seen_map = _load_existing_table_insight_map(mem_conn, candidates)
    schema_refresh_sec = int(AGENT_SCHEMA_INSIGHT_RESCAN_SEC or 0)
    table_refresh_sec = int(AGENT_TABLE_INSIGHT_RESCAN_SEC or 0)
    schema_refresh_map = _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, "schema_insight_refresh_at:")
    table_refresh_map = _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, "table_insight_refresh_at:")
    try:
        for schema in candidates:
            if time.perf_counter() - scan_start > budget_sec:
                break
            try:
                report["schemas_evaluated"] = int(report.get("schemas_evaluated", 0)) + 1
                # 스키마 핑거프린트 계산 (테이블 목록 기반)
                current_schema_fp = _compute_schema_fingerprint(db_conn, schema)
                schema_fp_key = ds_fact_key("schema_fp", schema)
                stored_schema_fp = stored_schema_fps.get(schema_fp_key, "")
                schema_structure_changed = (current_schema_fp != stored_schema_fp)

                cur.execute(
                    """
SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """,
                    (schema,),
                )
                col_rows = cur.fetchall() or []
                col_names: list[str] = []
                seen_cols: set[str] = set()
                for row in col_rows:
                    if not row or not row[0]:
                        continue
                    name = str(row[0]).strip()
                    if not name or name in seen_cols:
                        continue
                    seen_cols.add(name)
                    col_names.append(name)
                col_names = sorted(col_names)
                cur.execute(
                    """
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME
                    """,
                    (schema,),
                )
                table_rows = cur.fetchall() or []
                all_table_names = [str(r[0]).strip() for r in table_rows if r and r[0]]
                all_table_names = [t for t in all_table_names if t]
                schema_key = ds_fact_key("schema_insight", schema)
                schema_refresh_key = ds_fact_key("schema_insight_refresh_at", schema)
                schema_state = _load_insight_artifact_states(mem_conn, [schema_key]).get(
                    schema_key, _empty_insight_artifact_state(schema_key)
                )
                schema_artifact_missing = not _insight_artifact_complete(schema_state)
                schema_refresh_due = _is_refresh_due(
                    schema_refresh_map, schema_refresh_key, schema_refresh_sec
                )
                schema_has_stored_fp = bool(stored_schema_fp)
                schema_reason = ""
                if schema_artifact_missing:
                    schema_reason = "artifact_missing"
                    report["artifact_missing_selected"] = int(
                        report.get("artifact_missing_selected", 0)
                    ) + 1
                elif schema_structure_changed:
                    schema_reason = "fingerprint_changed"
                elif schema_refresh_due and not schema_has_stored_fp:
                    schema_reason = "refresh_due"

                schema_refs = _build_insight_references(
                    schema, table_names=all_table_names[: max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))]
                )
                if schema_reason == "artifact_missing":
                    repaired, schema_state = _repair_insight_artifacts_from_state(
                        mem_conn,
                        schema_key,
                        schema_state,
                        run_id,
                        schema,
                        "schema",
                        schema,
                        referenced_objects=schema_refs,
                    )
                    if repaired:
                        followup_reason = ""
                        if schema_structure_changed:
                            followup_reason = "fingerprint_changed"
                        elif schema_refresh_due and not schema_has_stored_fp:
                            followup_reason = "refresh_due"
                        if followup_reason:
                            schema_reason = followup_reason
                        else:
                            _mark_refresh_kv(mem_conn, schema_refresh_map, schema_refresh_key)
                            _save_fingerprint(mem_conn, schema_fp_key, current_schema_fp)
                            stored_schema_fps[schema_fp_key] = current_schema_fp
                            existing_schema_insights.add(schema)
                            report["schemas_repaired"] = int(report.get("schemas_repaired", 0)) + 1
                            schema_reason = ""

                if schema_reason:
                    schema_started = time.perf_counter()
                    schema_payload = {
                        "schema": schema,
                        "columns": col_names[: max(1, AGENT_SCHEMA_INSIGHT_MAX_COLS)],
                        "table_hints": [],
                    }
                    schema_error = ""
                    schema_insight = None
                    try:
                        schema_insight = llm_schema_insight(schema_payload)
                    except Exception as exc:
                        schema_error = str(exc)
                    schema_text = _format_schema_insight_text(
                        schema,
                        schema_insight if isinstance(schema_insight, dict) else None,
                        col_names=col_names,
                    )
                    publish_attempted = False
                    publish_skip_reason = ""
                    if (
                        not schema_error
                        and schema_text
                        and _should_publish_global_fact(schema_key, "schema_insight", 4, schema_text)
                    ):
                        _publish_fact(
                            mem_conn,
                            _insight_target_conversation_id(),
                            schema_key,
                            schema_text,
                            4,
                            scope_key=FACT_SCOPE_COMMON,
                            source_type="schema_insight",
                            source_run_id=run_id,
                            source_sql="",
                            source_meta=schema_insight if isinstance(schema_insight, dict) else None,
                        )
                        publish_attempted = True
                    elif schema_error:
                        publish_skip_reason = "llm_error"
                    elif not isinstance(schema_insight, dict):
                        publish_skip_reason = "invalid_response"
                    elif not schema_text:
                        publish_skip_reason = "empty_text"
                    else:
                        publish_skip_reason = "publish_filtered"
                    verified_schema_state = _load_insight_artifact_states(mem_conn, [schema_key]).get(
                        schema_key, _empty_insight_artifact_state(schema_key)
                    )
                    schema_complete = _insight_artifact_complete(verified_schema_state)
                    result = "ok" if schema_complete else "partial_persist"
                    if schema_error:
                        result = "publish_failed"
                        report["publish_failed"] = int(report.get("publish_failed", 0)) + 1
                    _trace_insight_worker_event(
                        run_id,
                        "publish",
                        schema,
                        "schema",
                        schema,
                        schema_reason,
                        "generate_insight",
                        referenced_objects=schema_refs,
                        result=result,
                        duration_ms=(time.perf_counter() - schema_started) * 1000.0,
                        error=schema_error,
                        extra={
                            "missing_parts": _insight_missing_parts(verified_schema_state),
                            "publish_attempted": bool(publish_attempted),
                            "publish_skip_reason": publish_skip_reason,
                        },
                    )
                    _trace_insight_worker_event(
                        run_id,
                        "verify",
                        schema,
                        "schema",
                        schema,
                        schema_reason,
                        "verify_persist",
                        referenced_objects=schema_refs,
                        result="ok" if schema_complete else "partial_persist",
                        extra={"missing_parts": _insight_missing_parts(verified_schema_state)},
                    )
                    if schema_complete:
                        _mark_refresh_kv(mem_conn, schema_refresh_map, schema_refresh_key)
                        _save_fingerprint(mem_conn, schema_fp_key, current_schema_fp)
                        stored_schema_fps[schema_fp_key] = current_schema_fp
                        existing_schema_insights.add(schema)
                        report["schemas_generated"] = int(report.get("schemas_generated", 0)) + 1
                else:
                    report["skipped_schemas"] = int(report.get("skipped_schemas", 0)) + 1

                offset_key = ds_scope_name(f"schema_instance_scan_offset:{schema}")
                batch = max(1, int(AGENT_SCHEMA_INSTANCE_SCAN_TABLE_LIMIT))
                if run_id == "init-memory":
                    batch = min(batch, 2)
                if not all_table_names:
                    try:
                        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key, "0")
                    except Exception:
                        pass
                    continue

                # 테이블 핑거프린트를 배치로 계산
                current_table_fps = _compute_table_fingerprints_batch(db_conn, schema, all_table_names)

                table_keys = [ds_fact_key("table_insight", f"{schema}.{name}") for name in all_table_names]
                artifact_states = _load_insight_artifact_states(mem_conn, table_keys)
                artifact_missing_tables: list[str] = []
                changed_tables: list[str] = []
                refresh_due_tables: list[str] = []
                reason_map: dict[str, str] = {}
                for tname in all_table_names:
                    table_key = ds_fact_key("table_insight", f"{schema}.{tname}")
                    state = artifact_states.get(table_key, _empty_insight_artifact_state(table_key))
                    tfp_key_chk = ds_fact_key("table_fp", f"{schema}.{tname}")
                    has_stored_tfp = bool(stored_table_fps.get(tfp_key_chk, ""))
                    current_tfp = current_table_fps.get(tname, "")
                    table_refresh_key = ds_fact_key("table_insight_refresh_at", f"{schema}.{tname}")
                    table_refresh_due = _is_refresh_due(
                        table_refresh_map,
                        table_refresh_key,
                        table_refresh_sec,
                    )
                    if not _insight_artifact_complete(state):
                        artifact_missing_tables.append(tname)
                        reason_map[tname] = "artifact_missing"
                    elif current_tfp != stored_table_fps.get(tfp_key_chk, ""):
                        changed_tables.append(tname)
                        reason_map[tname] = "fingerprint_changed"
                    elif (not has_stored_tfp) and table_refresh_due:
                        refresh_due_tables.append(tname)
                        reason_map[tname] = "refresh_due"

                ready_total = len(artifact_missing_tables) + len(changed_tables) + len(refresh_due_tables)
                report["skipped_tables"] = int(report.get("skipped_tables", 0)) + max(
                    0, len(all_table_names) - ready_total
                )

                try:
                    offset = int(load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key) or 0)
                except Exception:
                    offset = 0
                if offset < 0:
                    offset = 0
                selected_tables: list[str] = []
                primary_len = 0
                primary_selected = 0
                if artifact_missing_tables:
                    rotated_missing = _rotate_list(artifact_missing_tables, offset)
                    selected_tables.extend(rotated_missing[:batch])
                    primary_len = len(artifact_missing_tables)
                    primary_selected = min(len(selected_tables), batch)
                    if len(selected_tables) < batch and changed_tables:
                        selected_tables.extend(changed_tables[: batch - len(selected_tables)])
                    if len(selected_tables) < batch and refresh_due_tables:
                        selected_tables.extend(refresh_due_tables[: batch - len(selected_tables)])
                elif changed_tables:
                    rotated_changed = _rotate_list(changed_tables, offset)
                    selected_tables.extend(rotated_changed[:batch])
                    primary_len = len(changed_tables)
                    primary_selected = min(len(selected_tables), batch)
                    if len(selected_tables) < batch and refresh_due_tables:
                        selected_tables.extend(refresh_due_tables[: batch - len(selected_tables)])
                elif refresh_due_tables:
                    rotated_refresh = _rotate_list(refresh_due_tables, offset)
                    selected_tables.extend(rotated_refresh[:batch])
                    primary_len = len(refresh_due_tables)
                    primary_selected = min(len(selected_tables), batch)
                else:
                    try:
                        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key, "0")
                    except Exception:
                        pass
                    continue
                report["tables_selected"] = int(report.get("tables_selected", 0)) + len(selected_tables)
                selected_set = set(selected_tables)
                deferred_tables = [
                    table_name
                    for table_name in (artifact_missing_tables + changed_tables + refresh_due_tables)
                    if table_name not in selected_set
                ]
                if deferred_tables:
                    report["deferred_tables"] = int(report.get("deferred_tables", 0)) + len(deferred_tables)
                    _trace_insight_worker_event(
                        run_id,
                        "table_scan",
                        schema,
                        "schema",
                        schema,
                        "limit_exceeded",
                        "defer",
                        referenced_objects=_build_insight_references(
                            schema, table_names=deferred_tables[: max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))]
                        ),
                        result=f"deferred:{len(deferred_tables)}",
                    )
                table_cols: dict[str, list[tuple[str, str]]] = {}
                if selected_tables:
                    placeholders = ",".join(["%s"] * len(selected_tables))
                    cur.execute(
                        f"""
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
ORDER BY TABLE_NAME, ORDINAL_POSITION
                        """,
                        [schema] + selected_tables,
                    )
                    col_rows = cur.fetchall() or []
                    for table_name, col_name, data_type in col_rows:
                        tname = str(table_name or "").strip()
                        if not tname:
                            continue
                        name = str(col_name or "").strip()
                        if not name:
                            continue
                        table_cols.setdefault(tname, []).append(
                            (name, str(data_type or "").strip())
                        )
                for table in selected_tables:
                    if time.perf_counter() - scan_start > budget_sec:
                        break
                    col_rows = table_cols.get(table) or []
                    if not col_rows:
                        continue
                    cols_payload: list[dict[str, str]] = []
                    col_name_list: list[str] = []
                    seen_names: set[str] = set()
                    for col_name, data_type in col_rows:
                        name = str(col_name or "").strip()
                        if not name:
                            continue
                        if name in seen_names:
                            continue
                        seen_names.add(name)
                        col_name_list.append(name)
                        cols_payload.append({"name": name, "type": str(data_type or "").strip()})
                    if not cols_payload:
                        continue
                    col_name_list = sorted(col_name_list)
                    cols_payload = sorted(cols_payload, key=lambda x: str(x.get("name", "")))
                    table_key = ds_fact_key("table_insight", f"{schema}.{table}")
                    table_reason = reason_map.get(table, "artifact_missing")
                    table_refs = _build_insight_references(
                        schema,
                        table=table,
                        col_names=col_name_list,
                    )
                    table_state = artifact_states.get(
                        table_key, _empty_insight_artifact_state(table_key)
                    )
                    if table_reason == "artifact_missing":
                        report["artifact_missing_selected"] = int(
                            report.get("artifact_missing_selected", 0)
                        ) + 1
                        repaired, repaired_state = _repair_insight_artifacts_from_state(
                            mem_conn,
                            table_key,
                            table_state,
                            run_id,
                            schema,
                            "table",
                            table,
                            referenced_objects=table_refs,
                        )
                        if repaired:
                            artifact_states[table_key] = repaired_state
                            current_tfp = current_table_fps.get(table, "")
                            tfp_key = ds_fact_key("table_fp", f"{schema}.{table}")
                            has_stored_tfp = bool(stored_table_fps.get(tfp_key, ""))
                            followup_reason = ""
                            if current_tfp != stored_table_fps.get(tfp_key, ""):
                                followup_reason = "fingerprint_changed"
                            elif (not has_stored_tfp) and _is_refresh_due(
                                table_refresh_map,
                                ds_fact_key("table_insight_refresh_at", f"{schema}.{table}"),
                                table_refresh_sec,
                            ):
                                followup_reason = "refresh_due"
                            if followup_reason:
                                table_reason = followup_reason
                            else:
                                table_refresh_key = ds_fact_key("table_insight_refresh_at", f"{schema}.{table}")
                                _mark_refresh_kv(mem_conn, table_refresh_map, table_refresh_key)
                                if current_tfp:
                                    _save_fingerprint(mem_conn, tfp_key, current_tfp)
                                    stored_table_fps[tfp_key] = current_tfp
                                report["tables_repaired"] = int(report.get("tables_repaired", 0)) + 1
                                table_seen_map.setdefault(schema, set()).add(table)
                                continue
                    table_payload = {
                        "schema": schema,
                        "table": table,
                        "columns": cols_payload[: max(1, int(AGENT_TABLE_INSIGHT_MAX_COLS))],
                    }
                    table_started = time.perf_counter()
                    table_refresh_key = ds_fact_key("table_insight_refresh_at", f"{schema}.{table}")
                    table_error = ""
                    table_insight = None
                    try:
                        table_insight = llm_table_insight(table_payload)
                    except Exception as exc:
                        table_error = str(exc)
                    table_text = _format_table_insight_text(
                        schema,
                        table,
                        table_insight if isinstance(table_insight, dict) else None,
                        col_names=col_name_list,
                    )
                    publish_attempted = False
                    publish_skip_reason = ""
                    if (
                        not table_error
                        and table_text
                        and _should_publish_global_fact(table_key, "schema_insight", 4, table_text)
                    ):
                        _publish_fact(
                            mem_conn,
                            _insight_target_conversation_id(),
                            table_key,
                            table_text,
                            4,
                            scope_key=FACT_SCOPE_COMMON,
                            source_type="schema_insight",
                            source_run_id=run_id,
                            source_sql="",
                            source_meta=table_insight if isinstance(table_insight, dict) else None,
                        )
                        publish_attempted = True
                    elif table_error:
                        publish_skip_reason = "llm_error"
                    elif not isinstance(table_insight, dict):
                        publish_skip_reason = "invalid_response"
                    elif not table_text:
                        publish_skip_reason = "empty_text"
                    else:
                        publish_skip_reason = "publish_filtered"
                    verified_table_state = _load_insight_artifact_states(mem_conn, [table_key]).get(
                        table_key, _empty_insight_artifact_state(table_key)
                    )
                    table_complete = _insight_artifact_complete(verified_table_state)
                    result = "ok" if table_complete else "partial_persist"
                    if table_error:
                        result = "publish_failed"
                        report["publish_failed"] = int(report.get("publish_failed", 0)) + 1
                    _trace_insight_worker_event(
                        run_id,
                        "publish",
                        schema,
                        "table",
                        table,
                        table_reason,
                        "generate_insight",
                        referenced_objects=table_refs,
                        result=result,
                        duration_ms=(time.perf_counter() - table_started) * 1000.0,
                        error=table_error,
                        extra={
                            "missing_parts": _insight_missing_parts(verified_table_state),
                            "publish_attempted": bool(publish_attempted),
                            "publish_skip_reason": publish_skip_reason,
                        },
                    )
                    _trace_insight_worker_event(
                        run_id,
                        "verify",
                        schema,
                        "table",
                        table,
                        table_reason,
                        "verify_persist",
                        referenced_objects=table_refs,
                        result="ok" if table_complete else "partial_persist",
                        extra={"missing_parts": _insight_missing_parts(verified_table_state)},
                    )
                    if table_complete:
                        _mark_refresh_kv(mem_conn, table_refresh_map, table_refresh_key)
                        tfp_key = ds_fact_key("table_fp", f"{schema}.{table}")
                        current_tfp = current_table_fps.get(table, "")
                        if current_tfp:
                            _save_fingerprint(mem_conn, tfp_key, current_tfp)
                            stored_table_fps[tfp_key] = current_tfp
                        table_seen_map.setdefault(schema, set()).add(table)
                        report["tables_generated"] = int(report.get("tables_generated", 0)) + 1
                if primary_len > 0:
                    step = primary_selected if primary_selected > 0 else 1
                    new_offset = (offset + max(1, step)) % primary_len
                else:
                    new_offset = 0
                try:
                    save_memory_kv(
                        mem_conn,
                        GLOBAL_CONVERSATION_ID,
                        offset_key,
                        str(new_offset),
                    )
                except Exception:
                    pass
            except Exception:
                continue
    finally:
        cur.close()
    try:
        if report.get("scan_started"):
            save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, ds_scope_name("schema_instance_scan_at"), utc_now_iso())
    except Exception:
        pass
    return report


def _is_insight_worker_heartbeat_fresh(mem_conn) -> bool:
    if not mem_conn:
        return False
    try:
        last_cycle = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at")
        if not last_cycle:
            return False
        parsed = _parse_iso_time(str(last_cycle))
        if not parsed:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_sec = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        if age_sec < 0:
            age_sec = 0
        last_status = (
            load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_status")
            .strip()
            .lower()
        )
        if last_status not in {"ok", "skip_locked"}:
            return False
        return age_sec <= max(30, int(AGENT_INSIGHT_WORKER_STALE_SEC))
    except Exception:
        return False


def _should_run_inline_insight_scan(mem_conn) -> tuple[bool, str]:
    if AGENT_INLINE_INSIGHT_ON_ASK:
        return True, "inline_forced"
    if not AGENT_INSIGHT_WORKER_ENABLED:
        return True, "worker_disabled"
    if _is_insight_worker_heartbeat_fresh(mem_conn):
        return False, "worker_fresh"
    return True, "worker_stale_or_missing"


def _new_insight_worker_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-iw" + uuid.uuid4().hex[:6]


def _insight_readback_degraded() -> bool:
    """read 정본(PG)이 닿지 않으면 True — 그 상태에선 생성을 멈춰야 한다.

    cutover 이후 insight read-back(artifact 검증·fingerprint 맵)의 정본은 PG다.
    read backend 가 postgres 인데 PG 가 부재하면 read-back 이 (DROP 된) MySQL fallback
    으로 떨어져 모든 artifact/fingerprint 가 missing/changed 로 오판 → 매 tick 무의미한
    재생성(과거 livelock 의 동력)을 반복한다. 이 함수가 True 면 cycle 은 생성을 skip 하고
    loop 는 길게 backoff 한다. MySQL 모드(postgres 미사용)면 read-back 이 live mem_conn
    을 쓰므로 불일치가 없어 False."""
    from .config import AGENT_KB_READ_BACKEND
    try:
        from .runtime_backend import AGENT_RUNTIME_READ_BACKEND
    except Exception:
        AGENT_RUNTIME_READ_BACKEND = ""
    pg_mode = (AGENT_KB_READ_BACKEND == "postgres") or (
        AGENT_RUNTIME_READ_BACKEND == "postgres"
    )
    if not pg_mode:
        return False
    if not _pg_available():
        return True
    # 실제 연결 probe — 서버 down 시 _pg_available()(env/드라이버만 검사)만으론 못 잡는다.
    conn = None
    try:
        conn = _pg_connect_ro()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            cur.close()
        return False
    except Exception:
        return True
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def run_insight_cycle(run_id: str | None = None) -> dict[str, Any]:
    cycle_run_id = str(run_id or "").strip() or _new_insight_worker_run_id()
    started = time.perf_counter()
    lock_name = str(AGENT_INSIGHT_WORKER_LOCK_NAME or "").strip() or "agent_insight_worker_scan"
    status = "ok"
    err_text = ""
    schema_count = 0
    scan_triggered = 0
    lock_acquired = False
    scan_report: dict[str, Any] = {
        "scan_started": False,
        "schemas_evaluated": 0,
        "schemas_generated": 0,
        "schemas_repaired": 0,
        "tables_selected": 0,
        "tables_generated": 0,
        "tables_repaired": 0,
        "artifact_missing_selected": 0,
        "skipped_schemas": 0,
        "skipped_tables": 0,
        "deferred_tables": 0,
    }
    timing = _timing_breakdown_template(
        cycle_run_id, AGENT_INSIGHT_WORKER_CONVERSATION_ID, "__insight_worker__"
    )
    mem_conn = None
    db_conn = None
    try:
        mem_start = time.perf_counter()
        mem_conn = connect_with_retry(database=MEMORY_DB, autocommit=True)
        _timing_breakdown_add(
            timing, "memory_rw_ms", (time.perf_counter() - mem_start) * 1000.0
        )
        db_start = time.perf_counter()
        db_conn = connect_with_retry(database=DB_CONNECT_DB, autocommit=True)
        _timing_breakdown_add(
            timing, "memory_rw_ms", (time.perf_counter() - db_start) * 1000.0
        )

        lock_acquired = _acquire_advisory_lock(
            mem_conn,
            lock_name,
            timeout_sec=max(0, int(AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC)),
        )
        if not lock_acquired:
            status = "skip_locked"
        elif _insight_readback_degraded():
            # read 정본(PG) 부재 — 생성 시 read-back 이 빈 MySQL fallback 으로 떨어져
            # 전부 missing/changed 오판 → livelock 재발. 본 cycle 은 scan/generate 를
            # skip 하고 loop 가 degraded backoff 로 PG 복구를 기다린다.
            status = "degraded_readback"
        else:
            # 멀티 datasource (P3): 기본 단일 MySQL(ds=None) + 등록 datasource 들을 순회하며
            # 각각 datasource-스코프 fact 키로 인사이트를 생성한다. flag OFF 면 ds_targets 가
            # [(None, None)] 한 개라 기존 동작 0 변경(무접두 키). datasource 별 키는 ContextVar
            # (set_active_datasource)로 ds_fact_key 에 주입 → write·read-back·grounding 3자 정합.
            ds_targets = [(None, None)]
            if AGENT_MULTI_DATASOURCE_ENABLED and DATASOURCES:
                ds_targets += [(k, v) for k, v in DATASOURCES.items()]
            schema_count = 0
            plan_start = time.perf_counter()
            for _ds_key, _ds_coords in ds_targets:
                _ds_conn = None
                try:
                    # P7: datasource 의 engine 도 함께 set (없으면 dialects.active() 가 mysql 로
                    # 오인해 MSSQL 에 MySQL SQL 을 던진다 — 컬럼 핑거프린트 projection 분기 정합).
                    set_active_datasource(
                        _ds_key,
                        engine=(_ds_coords.get("engine") if _ds_coords else None),
                    )
                    if _ds_key is None:
                        _ds_conn = db_conn  # 기본 DB 는 이미 연결됨
                    else:
                        # datasource 는 database=None(M-1; MSSQL 은 _connect_mssql 이 default_db 로 고정).
                        # **db 모듈의 connect_with_retry 를 명시 사용** (REV-0203 P7 follow-up): insight 의
                        # 전역 `connect_with_retry`(from .config import *)는 `modules.utils` 의 구버전이라
                        # `datasource=` 인자가 없어 매 cycle TypeError → winsql 순회가 P3 이래 항상 실패했다.
                        # datasource 지원 + 재시도 로직은 modules.db 의 것에만 있다.
                        _ds_conn = _db.connect_with_retry(
                            database=None, datasource=_ds_coords, autocommit=True
                        )
                    _known = load_known_schemas(_ds_conn)
                    if _ds_key is None and _known:
                        KNOWN_SCHEMAS.clear()
                        KNOWN_SCHEMAS.extend(_known)
                    _scan_schemas = (_known or KNOWN_SCHEMAS) if _ds_key is None else (_known or [])
                    schema_count += len([s for s in (_scan_schemas or []) if s and not _is_system_schema(s)])
                    _bootstrap_schema_insights(_ds_conn, mem_conn, _scan_schemas, run_id=cycle_run_id)
                    _rep = _scan_instance_schema_insights(
                        _ds_conn,
                        mem_conn,
                        _scan_schemas,
                        run_id=cycle_run_id,
                    )
                    # REV-20260610-P3 MAJOR: 마지막 datasource 만 반영되던 telemetry 를 누적
                    # (과거 livelock 을 잡은 관측성 보존). int 필드 합산 + bool OR.
                    if isinstance(_rep, dict):
                        for _k, _v in _rep.items():
                            if isinstance(_v, bool):
                                scan_report[_k] = bool(scan_report.get(_k)) or _v
                            elif isinstance(_v, (int, float)):
                                scan_report[_k] = (scan_report.get(_k) or 0) + _v
                            else:
                                scan_report[_k] = _v
                    if _rep.get("scan_started"):
                        scan_triggered = 1
                except Exception as _ds_exc:
                    # 연결실패 격리 (PF2/Codex): 한 datasource 실패가 다른 datasource·기본 DB
                    # scan 을 막지 않는다. 기본 DB(ds=None) 실패는 바깥 except 로 전파(기존 동작).
                    if _ds_key is None:
                        raise
                    logging.getLogger("insight").warning(
                        "insight_datasource_scan_failed ds=%s err=%r — 다음 datasource 계속", _ds_key, _ds_exc,
                    )
                finally:
                    set_active_datasource(None)
                    if _ds_key is not None and _ds_conn is not None:
                        try:
                            _ds_conn.close()
                        except Exception:
                            pass
            _timing_breakdown_add(timing, "plan_ms", (time.perf_counter() - plan_start) * 1000.0)
    except Exception as exc:
        status = "error"
        err_text = str(exc).strip()[:500]
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        if mem_conn is not None:
            try:
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at", utc_now_iso())
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_status", status)
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_run_id", cycle_run_id)
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_error", err_text)
                save_memory_kv(
                    mem_conn,
                    GLOBAL_CONVERSATION_ID,
                    "insight_worker_last_duration_ms",
                    f"{duration_ms:.2f}",
                )
            except Exception:
                pass
        if lock_acquired and mem_conn is not None:
            _release_advisory_lock(mem_conn, lock_name)
        try:
            if db_conn is not None:
                db_conn.close()
        except Exception:
            pass
        try:
            if mem_conn is not None:
                mem_conn.close()
        except Exception:
            pass

    # TASK-0131 (#10): publish 가 시도됐으나 전부 실패(생성/복구 0)면 'ok' 가 아니라 'degraded'.
    # 이전엔 모든 publish 가 실패해도 status='ok' 라 operator 에게 거짓 신호를 줬다.
    _pub_failed = int(scan_report.get("publish_failed", 0) or 0)
    _generated = (
        int(scan_report.get("schemas_generated", 0) or 0)
        + int(scan_report.get("tables_generated", 0) or 0)
        + int(scan_report.get("schemas_repaired", 0) or 0)
        + int(scan_report.get("tables_repaired", 0) or 0)
    )
    if status == "ok" and _pub_failed > 0 and _generated == 0:
        status = "degraded"
    timing["total_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    timing["updated_at"] = utc_now_iso()
    timing["status"] = status
    timing["scan_triggered"] = int(scan_triggered)
    timing["schema_count"] = int(schema_count)
    timing["error"] = err_text
    payload = {
        "run_id": cycle_run_id,
        "status": status,
        "duration_ms": round(float(timing.get("total_ms", 0.0)), 2),
        "schema_count": int(schema_count),
        "scan_triggered": int(scan_triggered),
        "error": err_text,
    }
    payload.update(
        {
            "schemas_evaluated": int(scan_report.get("schemas_evaluated", 0) or 0),
            "schemas_generated": int(scan_report.get("schemas_generated", 0) or 0),
            "schemas_repaired": int(scan_report.get("schemas_repaired", 0) or 0),
            "tables_selected": int(scan_report.get("tables_selected", 0) or 0),
            "tables_generated": int(scan_report.get("tables_generated", 0) or 0),
            "tables_repaired": int(scan_report.get("tables_repaired", 0) or 0),
            "artifact_missing_selected": int(
                scan_report.get("artifact_missing_selected", 0) or 0
            ),
            "pending_schema_repairs": int(
                scan_report.get("pending_schema_repairs", 0) or 0
            ),
            "pending_table_repairs": int(
                scan_report.get("pending_table_repairs", 0) or 0
            ),
            "deferred_tables": int(scan_report.get("deferred_tables", 0) or 0),
            "skipped_schemas": int(scan_report.get("skipped_schemas", 0) or 0),
            "skipped_tables": int(scan_report.get("skipped_tables", 0) or 0),
            "publish_failed": int(scan_report.get("publish_failed", 0) or 0),
        }
    )
    should_log = status != "ok" or bool(scan_report.get("scan_started"))
    if should_log:
        timing_path = _write_timing_breakdown(timing)
        if timing_path:
            payload["timing_path"] = timing_path
        append_log_line("insight_worker", json.dumps(payload, ensure_ascii=False))
    return payload


def run_insight_worker_loop() -> None:
    if not AGENT_INSIGHT_WORKER_ENABLED:
        console.print("insight worker disabled: AGENT_INSIGHT_WORKER_ENABLED=0")
        return
    tick_sec = max(5, int(AGENT_INSIGHT_WORKER_TICK_SEC))
    degraded_backoff_sec = max(tick_sec, int(AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC))
    jitter_sec = max(0, int(AGENT_INSIGHT_WORKER_JITTER_SEC))
    if jitter_sec > 0:
        time.sleep(random.uniform(0, float(jitter_sec)))
    while True:
        result = run_insight_cycle()
        status = str((result or {}).get("status", "")).strip()
        # PG read 정본 부재(degraded_readback) / 연결 오류(error) 시엔 짧은 tick 대신
        # 길게 backoff — MySQL fallback 으로 떨어져 무의미한 재시도(livelock 동력)를
        # 반복하지 않고 PG 복구를 기다린다.
        if status in ("degraded_readback", "error"):
            time.sleep(degraded_backoff_sec)
        else:
            time.sleep(tick_sec)
