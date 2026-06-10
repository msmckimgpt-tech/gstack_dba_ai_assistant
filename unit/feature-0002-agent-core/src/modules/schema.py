import mysql.connector
import re
import stat
import sys
import time
__all__ = [
    "DATE_TOKEN_RE",
    "SCHEMA_USAGE_GROUPS",
    "USER_ID_CANDIDATES",
    "_build_schema_usage_answer_from_compact",
    "_build_stats_select_sql",
    "_build_time_where_clause",
    "_choose_preferred_schema",
    "_coerce_schema_list",
    "_compact_schema_meta_for_request",
    "_contains_structure_intent",
    "_contains_time_intent",
    "_contains_user_daily_intent",
    "_detect_requested_schema",
    "_extract_explicit_date_range",
    "_extract_request_tokens",
    "_extract_schema_table_candidates",
    "_infer_preferred_schema",
    "_infer_schema_from_request",
    "_is_generic_clarification_question",
    "_is_schema_usage_intent",
    "_load_global_schema_preferences",
    "_load_schema_pref_scores",
    "_looks_like_followup_request",
    "_maybe_record_summary_facts",
    "_pick_columns_from_prompt",
    "_pick_date_column",
    "_pick_numeric_column",
    "_pick_table_candidates",
    "_pick_table_from_prompt",
    "_pick_user_id_column",
    "_question_needs_structure",
    "_rank_schemas_by_tokens",
    "_record_schema_insight_from_search",
    "_record_schema_prefs_from_search",
    "_record_table_usage_insight",
    "_seed_preferred_schema_from_global",
    "_should_auto_finalize",
    "_should_skip_aux_updates",
    "_token_matches",
    "load_known_schemas",
    "load_schema_metadata",
]


"""Schema metadata loading, preferences, detection."""
from .config import *
import json, re, time
from typing import Any

def _extract_request_tokens(text: str) -> list[str]:
    if not text:
        return []
    lowered = str(text).lower()
    en_tokens = re.findall(r"\b[a-z][a-z0-9_]{2,}\b", lowered)
    ko_tokens = re.findall(r"[가-힣]{2,}", str(text))
    generic = {
        "db",
        "database",
        "schema",
        "table",
        "column",
        "data",
        "count",
        "min",
        "max",
        "date",
        "result",
    }
    generic_ko = {
        "데이터",
        "테이블",
        "컬럼",
        "스키마",
        "요청",
        "조회",
        "결과",
        "확인",
        "분석",
        "정보",
        "집계",
        "기준",
        "최소",
        "최대",
        "일자",
        "날짜",
        "포함",
        "제외",
        "간단",
        "값",
    }
    ordered: list[str] = []
    seen: set[str] = set()
    for token in en_tokens:
        tok = str(token or "").strip().lower()
        if not tok or tok in generic or tok in seen:
            continue
        seen.add(tok)
        ordered.append(tok)
    for token in ko_tokens:
        tok = str(token or "").strip()
        if not tok or tok in generic_ko or tok in seen:
            continue
        seen.add(tok)
        ordered.append(tok)
    return ordered


def _rank_schemas_by_tokens(conn, tokens: list[str], limit: int = 3) -> list[str]:
    if not conn or not tokens:
        return []
    excluded = [
        "information_schema",
        "mysql",
        "performance_schema",
        "sys",
        MEMORY_DB,
    ]
    like_clauses = " OR ".join(["LOWER(`TABLE_NAME`) LIKE %s"] * len(tokens))
    params: list[Any] = [f"%{token}%" for token in tokens]
    params.extend(excluded)
    params.append(int(limit))
    placeholders = ",".join(["%s"] * len(excluded))
    sql = (
        "SELECT `TABLE_SCHEMA`, COUNT(*) AS hits "
        "FROM `information_schema`.`TABLES` "
        f"WHERE `TABLE_SCHEMA` NOT IN ({placeholders}) "
        f"AND ({like_clauses}) "
        "GROUP BY `TABLE_SCHEMA` "
        "ORDER BY hits DESC, `TABLE_SCHEMA` "
        "LIMIT %s"
    )
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        rows = cur.fetchall() or []
        return [str(row[0]) for row in rows if row and row[0]]
    finally:
        cur.close()


def _load_global_schema_preferences(
    conn,
    conversation_id: str,
    limit: int = 3,
    scope_keys: list[str] | None = None,
) -> list[str]:
    if not conn or not AGENT_GLOBAL_KB_FACTS:
        return []
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return []
    try:
        score_limit = max(int(limit) * 4, 12)
    except Exception:
        score_limit = 12
    score_map = _load_schema_pref_scores(
        conn,
        conversation_id,
        limit=score_limit,
        scope_keys=scope_keys,
    )
    if score_map:
        ordered_scores = sorted(score_map.items(), key=lambda x: (-int(x[1]), x[0]))
        return [str(schema or "").strip() for schema, _ in ordered_scores[: max(1, int(limit))] if str(schema or "").strip()]

    scope_keys = scope_keys or _scope_candidates()
    normalized_scopes: list[str] = []
    include_blank_scope = False
    for key in scope_keys:
        key_str = str(key or "").strip()
        if key_str == "":
            include_blank_scope = True
            continue
        normalized_scopes.append(_normalize_scope_key(key_str))
    scope_clause = ""
    scope_params: list[Any] = []
    if normalized_scopes:
        placeholders = ",".join(["%s"] * len(normalized_scopes))
        scope_clause = f" AND (ScopeKey IN ({placeholders})"
        scope_params.extend(normalized_scopes)
        if include_blank_scope:
            scope_clause += " OR ScopeKey IS NULL OR ScopeKey = ''"
        scope_clause += ")"
    elif include_blank_scope:
        scope_clause = " AND (ScopeKey IS NULL OR ScopeKey = '')"
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
SELECT FactKey
FROM AgentMemoryFacts
WHERE ConversationId = %s AND FactKey LIKE 'schema_pref:%%'{scope_clause}
ORDER BY Weight DESC, UpdatedAt DESC
LIMIT %s
            """,
            [conversation_id, *scope_params, int(limit)],
        )
        rows = cur.fetchall() or []
        prefs: list[str] = []
        for row in rows:
            if not row:
                continue
            key = str(row[0] or "")
            if key.startswith("schema_pref:"):
                prefs.append(key.split(":", 1)[1])
        return [p for p in prefs if p]
    except Exception:
        return []
    finally:
        cur.close()


def _load_schema_pref_scores(
    conn,
    conversation_id: str,
    limit: int = 12,
    scope_keys: list[str] | None = None,
) -> dict[str, int]:
    if not conn:
        return {}
    scope_keys = scope_keys or _scope_candidates()
    normalized_scopes: list[str] = []
    include_blank_scope = False
    for key in scope_keys:
        key_str = str(key or "").strip()
        if key_str == "":
            include_blank_scope = True
            continue
        normalized_scopes.append(_normalize_scope_key(key_str))
    scope_clause = ""
    scope_params: list[Any] = []
    if normalized_scopes:
        placeholders = ",".join(["%s"] * len(normalized_scopes))
        scope_clause = f" AND (ScopeKey IN ({placeholders})"
        scope_params.extend(normalized_scopes)
        if include_blank_scope:
            scope_clause += " OR ScopeKey IS NULL OR ScopeKey = ''"
        scope_clause += ")"
    elif include_blank_scope:
        scope_clause = " AND (ScopeKey IS NULL OR ScopeKey = '')"
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
SELECT FactKey, Weight
FROM AgentMemoryFactEntries
WHERE ConversationId = %s AND FactKey LIKE 'schema_pref:%%'{scope_clause}
ORDER BY Weight DESC, UpdatedAt DESC
LIMIT %s
            """,
            [conversation_id, *scope_params, int(limit)],
        )
        rows = cur.fetchall() or []
    except Exception:
        cur.execute(
            """
SELECT FactKey, Weight
FROM AgentMemoryFactEntries
WHERE ConversationId = %s AND FactKey LIKE 'schema_pref:%%'
ORDER BY Weight DESC, UpdatedAt DESC
LIMIT %s
            """,
            (conversation_id, int(limit)),
        )
        rows = cur.fetchall() or []
    finally:
        cur.close()
    scores: dict[str, int] = {}
    for row in rows:
        if not row:
            continue
        key = str(row[0] or "")
        if not key.startswith("schema_pref:"):
            continue
        schema = key.split(":", 1)[1]
        if _is_system_schema(schema):
            continue
        try:
            weight = int(row[1]) if row[1] is not None else 1
        except Exception:
            weight = 1
        scores[schema] = max(scores.get(schema, 0), weight)
    return scores


def _seed_preferred_schema_from_global(
    mem_conn,
    conversation_id: str,
    request_text: str,
    kv: dict[str, Any] | None,
    known_schemas: list[str],
) -> str:
    if not mem_conn:
        return ""
    kv = kv or {}
    current = str(kv.get("preferred_schema") or "").strip()
    if current and not _is_system_schema(current):
        return current
    requested_schema = _detect_requested_schema(request_text, known_schemas) or ""
    if _has_same_domain_cue(request_text) and not requested_schema:
        for cid in _global_fact_conversation_ids(include_shared=True):
            recent_schema = str(
                load_memory_kv(mem_conn, cid, "last_global_domain_anchor_schema") or ""
            ).strip()
            if not recent_schema or _is_system_schema(recent_schema):
                continue
            if known_schemas and recent_schema not in known_schemas:
                continue
            try:
                save_memory_kv(mem_conn, conversation_id, "preferred_schema", recent_schema)
                recent_table = str(
                    load_memory_kv(mem_conn, cid, "last_global_domain_anchor_table") or ""
                ).strip()
                if recent_table:
                    save_memory_kv(
                        mem_conn,
                        conversation_id,
                        "cross_session_anchor_table",
                        recent_table,
                    )
            except Exception:
                pass
            return recent_schema
    scope = _build_request_scope_key(request_text, kv)
    scope_keys = _scope_candidates(scope)
    session_scope_scores: dict[str, int] = {}
    session_cid = GLOBAL_SESSION_CONVERSATION_ID or ""
    if session_cid:
        session_scope_scores = _load_schema_pref_scores(
            mem_conn,
            session_cid,
            limit=12,
            scope_keys=scope_keys,
        )
        if session_scope_scores:
            ordered = sorted(session_scope_scores.items(), key=lambda x: (-int(x[1]), x[0]))
            picked = str(ordered[0][0] or "").strip()
            if picked and not _is_system_schema(picked):
                if not known_schemas or picked in known_schemas:
                    try:
                        save_memory_kv(mem_conn, conversation_id, "preferred_schema", picked)
                    except Exception:
                        pass
                    return picked
    merged_scores: dict[str, int] = {}
    for global_cid in _global_fact_conversation_ids(include_shared=True):
        scores = _load_schema_pref_scores(
            mem_conn,
            global_cid,
            limit=12,
            scope_keys=scope_keys,
        )
        for schema, score in scores.items():
            if _is_system_schema(schema):
                continue
            merged_scores[schema] = max(merged_scores.get(schema, 0), int(score))
    if not merged_scores:
        return ""
    ordered = sorted(merged_scores.items(), key=lambda x: (-x[1], x[0]))
    picked = str(ordered[0][0] or "").strip()
    if not picked or _is_system_schema(picked):
        return ""
    if known_schemas and picked not in known_schemas:
        return ""
    try:
        save_memory_kv(mem_conn, conversation_id, "preferred_schema", picked)
    except Exception:
        pass
    return picked


def _infer_preferred_schema(
    db_conn,
    mem_conn,
    request_text: str,
    kv: dict[str, str],
    known_schemas: list[str],
    conversation_id: str | None = None,
    scope_key: str | None = None,
) -> str | None:
    kv = kv or {}
    detected = _detect_requested_schema(request_text, known_schemas)
    if detected:
        return detected
    anchor_schema = str(_load_domain_anchor(kv).get("schema") or "").strip()
    if (
        anchor_schema
        and not _is_system_schema(anchor_schema)
        and (not known_schemas or anchor_schema in known_schemas)
    ):
        return anchor_schema

    preferred = str(kv.get("preferred_schema") or "").strip()
    scores: dict[str, int] = {}
    if preferred and not _is_system_schema(preferred):
        scores[preferred] = max(scores.get(preferred, 0), 2)

    tokens = _extract_request_tokens(request_text)
    if tokens and db_conn is not None:
        ranked = _rank_schemas_by_tokens(db_conn, tokens, limit=3)
        if ranked:
            for idx, cand in enumerate(ranked):
                cand_name = str(cand or "").strip()
                if not cand_name or _is_system_schema(cand_name):
                    continue
                scores[cand_name] = max(scores.get(cand_name, 0), max(1, 6 - idx))

    if mem_conn is not None:
        scope_candidates = _scope_candidates(
            scope_key or _build_request_scope_key(request_text, kv)
        )
        local_scores = (
            _load_schema_pref_scores(
                mem_conn,
                conversation_id or "",
                8,
                scope_keys=scope_candidates,
            )
            if conversation_id
            else {}
        )
        global_scores: dict[str, int] = {}
        for global_cid in _global_fact_conversation_ids(include_shared=True):
            scores = _load_schema_pref_scores(
                mem_conn,
                global_cid,
                8,
                scope_keys=scope_candidates,
            )
            for schema, score in scores.items():
                global_scores[schema] = max(global_scores.get(schema, 0), score)
        combined: dict[str, int] = {}
        for schema, score in {**global_scores, **local_scores}.items():
            if _is_system_schema(schema):
                continue
            combined[schema] = max(combined.get(schema, 0), int(score))
        for schema, score in combined.items():
            scores[schema] = max(scores.get(schema, 0), int(score))
        for global_cid in _global_fact_conversation_ids(include_shared=True):
            prefs = _load_global_schema_preferences(
                mem_conn,
                global_cid,
                limit=1,
                scope_keys=scope_candidates,
            )
            if prefs:
                pref_schema = str(prefs[0] or "").strip()
                if pref_schema and not _is_system_schema(pref_schema):
                    scores[pref_schema] = max(scores.get(pref_schema, 0), 2)

    if scores:
        step_trace = load_step_trace_from_kv(kv)
        recent_entries = list(step_trace)[-max(1, AGENT_SCHEMA_BIAS_STEP_WINDOW) :]
        schema_hits: dict[str, int] = {}
        total_hits = 0
        for entry in recent_entries:
            if not isinstance(entry, dict):
                continue
            sql_text = str(entry.get("sql", "")).strip()
            if not sql_text and isinstance(entry.get("args"), dict):
                sql_text = str(entry.get("args", {}).get("sql", "")).strip()
            schema_name, _ = _extract_first_table_from_sql(sql_text)
            schema_name = str(schema_name or "").strip()
            if not schema_name or _is_system_schema(schema_name):
                continue
            schema_hits[schema_name] = schema_hits.get(schema_name, 0) + 1
            total_hits += 1
        if total_hits > 0:
            penalized: list[tuple[str, float]] = []
            for schema_name, hit in schema_hits.items():
                ratio = hit / float(total_hits)
                if ratio > AGENT_SCHEMA_BIAS_THRESHOLD and schema_name in scores:
                    scores[schema_name] = max(1, int(scores.get(schema_name, 1)) - AGENT_SCHEMA_BIAS_PENALTY)
                    penalized.append((schema_name, ratio))
            if penalized:
                try:
                    log_fact_quality(
                        "schema_bias_penalty",
                        {
                            "conversation_id": conversation_id or "",
                            "request": " ".join(str(request_text or "").split())[:120],
                            "penalized": [
                                {"schema": schema_name, "ratio": round(ratio, 3)}
                                for schema_name, ratio in penalized
                            ],
                        },
                    )
                except Exception:
                    pass

        filtered_scores: dict[str, int] = {}
        for schema, score in scores.items():
            schema_name = str(schema or "").strip()
            if not schema_name or _is_system_schema(schema_name):
                continue
            if known_schemas and schema_name not in known_schemas:
                continue
            filtered_scores[schema_name] = max(filtered_scores.get(schema_name, 0), int(score))
        if filtered_scores:
            best = sorted(filtered_scores.items(), key=lambda x: (-x[1], x[0]))[0][0]
            if best:
                return best
    return _choose_preferred_schema(db_conn) if db_conn is not None else None


def _maybe_record_summary_facts(
    conn,
    conversation_id: str,
    sql_text: str,
    summary_data: dict[str, Any] | None,
    intent: str | None = None,
    source_run_id: str | None = None,
) -> None:
    if not conn or not isinstance(summary_data, dict):
        return
    schema, table = _extract_first_table_from_sql(sql_text)
    if not table:
        return
    schema = schema or ""
    if _is_system_schema(schema):
        return
    prefix = f"{schema}." if schema else ""
    col_names = summary_data.get("col_names")
    if isinstance(col_names, list) and col_names:
        text = f"{prefix}{table} 컬럼 예시: {', '.join([str(c) for c in col_names])}"
        _publish_fact(
            conn,
            conversation_id,
            f"cols:{prefix}{table}",
            text,
            4,
            source_type="result_summary",
            source_run_id=source_run_id,
            source_sql=sql_text,
        )
    rows = summary_data.get("rows")
    if isinstance(rows, int) and rows > 0:
        text = f"{prefix}{table} 최근 조회 결과 행수(샘플 기준): {rows}"
        _publish_fact(
            conn,
            conversation_id,
            f"rows:{prefix}{table}",
            text,
            2,
            source_type="result_summary",
            source_run_id=source_run_id,
            source_sql=sql_text,
        )


def _record_schema_prefs_from_search(
    conn,
    conversation_id: str,
    items: list[dict[str, Any]] | None,
    pattern: str | None = None,
    source_run_id: str | None = None,
) -> None:
    if not AGENT_SEARCH_PREF_FROM_METADATA:
        return
    if not conn or not items:
        return
    pattern = str(pattern or "").strip()
    if not pattern or pattern == "%":
        return
    system_schemas = {"information_schema", "mysql", "performance_schema", "sys"}
    counts: dict[str, int] = {}
    table_counts: dict[str, int] = {}
    for item in items:
        schema = str(item.get("schema") or "").strip()
        name = str(item.get("name") or "").strip()
        if not schema or schema.lower() in system_schemas:
            continue
        counts[schema] = counts.get(schema, 0) + 1
        if name:
            key = f"{schema}.{name}"
            table_counts[key] = table_counts.get(key, 0) + 1
    if not counts:
        return
    sorted_schemas = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    top_schema, top_count = sorted_schemas[0]
    second_count = sorted_schemas[1][1] if len(sorted_schemas) > 1 else 0
    if len(sorted_schemas) == 1 or top_count >= max(2, second_count + 1):
        _publish_fact(
            conn,
            conversation_id,
            f"schema_pref:{top_schema}",
            f"검색 결과에서 자주 등장한 스키마: {top_schema}",
            4,
            source_type="search_pref",
            source_run_id=source_run_id,
        )
        _record_schema_insight_from_search(
            conn,
            conversation_id,
            top_schema,
            [str(item.get("name", "")) for item in items if str(item.get("schema") or "").strip() == top_schema],
            source_run_id=source_run_id,
        )
        if table_counts:
            sorted_tables = sorted(table_counts.items(), key=lambda x: (-x[1], x[0]))
            top_table, _ = sorted_tables[0]
            _publish_fact(
                conn,
                conversation_id,
                f"table_pref:{top_table}",
                f"검색 결과에서 자주 등장한 테이블: {top_table}",
                3,
                source_type="search_pref",
                source_run_id=source_run_id,
            )


def _record_schema_insight_from_search(
    conn,
    conversation_id: str,
    schema: str,
    table_names: list[str],
    source_run_id: str | None = None,
) -> None:
    if not conn or not AGENT_SCHEMA_INSIGHT:
        return
    schema = str(schema or "").strip()
    if not schema or _is_system_schema(schema):
        return
    hints = [str(t) for t in (table_names or []) if str(t).strip()]
    payload = {"schema": schema, "columns": [], "table_hints": hints[: max(1, AGENT_SCHEMA_INSTANCE_SCAN_TABLE_LIMIT)]}
    insight = llm_schema_insight(payload)
    text = _format_schema_insight_text(schema, insight, col_names=[], table_names=hints)
    if not text:
        return
    _publish_fact(
        conn,
        conversation_id,
        ds_fact_key("schema_insight", schema),
        text,
        4,
        source_type="schema_insight",
        source_run_id=source_run_id,
        source_meta=insight if isinstance(insight, dict) else None,
    )


def _record_table_usage_insight(
    conn,
    conversation_id: str,
    schema: str,
    table: str,
    col_names: list[str] | None,
    source_run_id: str | None = None,
    fallback_schema: str | None = None,
) -> None:
    if not conn or not AGENT_SCHEMA_INSIGHT:
        return
    schema = str(schema or "").strip()
    table = str(table or "").strip()
    if not table or _is_system_schema(schema):
        return
    if not schema:
        return
    sample_cols = [str(c) for c in (col_names or []) if str(c).strip()]
    fact_key = ds_fact_key("table_insight", f"{schema}.{table}")
    existing = ""
    for global_cid in _global_fact_conversation_ids(include_shared=True):
        existing = _load_fact_text(
            conn,
            global_cid,
            fact_key,
            scope_keys=_scope_candidates(FACT_SCOPE_COMMON),
        )
        if existing:
            break
    if existing:
        # 이미 검증/생성된 테이블 인사이트가 있으면 재사용해 LLM 반복 호출을 방지한다.
        _upsert_fact(
            conn,
            GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID,
            fact_key,
            existing,
            4,
            scope_key=FACT_SCOPE_COMMON,
            source_type="schema_insight",
            source_run_id=source_run_id,
            source_sql="",
        )
        return
    if not sample_cols:
        return
    payload = {
        "schema": schema,
        "table": table,
        "columns": [
            {"name": col, "type": ""} for col in sample_cols[: max(1, AGENT_TABLE_INSIGHT_MAX_COLS)]
        ],
    }
    insight = llm_table_insight(payload)
    text = _format_table_insight_text(schema, table, insight, col_names=sample_cols)
    if not text:
        return
    _publish_fact(
        conn,
        conversation_id,
        fact_key,
        text,
        4,
        source_type="schema_insight",
        source_run_id=source_run_id,
        source_meta=insight if isinstance(insight, dict) else None,
    )


def _should_skip_aux_updates(tool: str, result_summary: dict[str, Any] | None, error: str | None) -> bool:
    tool_name = str(tool or "").strip()
    if tool_name in MCP_SEARCH_OBJECTS_CANDIDATES:
        return True
    if tool_name in {"file_search", "convo_search"}:
        return True
    if not error and _is_zero_summary(result_summary):
        return True
    return False


def _should_auto_finalize(kv: dict[str, Any]) -> bool:
    if not isinstance(kv, dict):
        return False
    tool = str(kv.get("last_result_tool", "")).strip()
    if tool not in ("execute_sql", "mcp_execute_sql"):
        return False
    raw = kv.get("last_result_summary")
    summary: dict[str, Any] | None = None
    if isinstance(raw, dict):
        summary = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                summary = parsed
        except Exception:
            summary = None
    if not summary or _is_zero_summary(summary):
        return False
    intent = str(kv.get("last_result_intent", "")).strip()
    if re.search(r"(샘플|컬럼|메타|스키마|탐색|목록|확인|존재)", intent):
        return False
    return True


def load_schema_metadata(conn, schema_name: str) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
SELECT `TABLE_NAME`, `COLUMN_NAME`, `DATA_TYPE`
FROM `information_schema`.`COLUMNS`
WHERE `TABLE_SCHEMA` = %s
ORDER BY `TABLE_NAME`, `ORDINAL_POSITION`
            """,
            (schema_name,),
        )
        column_rows = cur.fetchall() or []
    finally:
        cur.close()

    columns_by_table: dict[str, list[dict[str, str]]] = {}
    tables: list[str] = []
    for table_name, column_name, data_type in column_rows:
        t = str(table_name)
        if t not in columns_by_table:
            columns_by_table[t] = []
            tables.append(t)
        columns_by_table[t].append(
            {
                "name": str(column_name),
                "data_type": str(data_type).lower(),
            }
        )

    return {"tables": tables, "columns_by_table": columns_by_table}


def load_known_schemas(conn) -> list[str]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
SELECT `SCHEMA_NAME`
FROM `information_schema`.`SCHEMATA`
ORDER BY `SCHEMA_NAME`
            """
        )
        rows = cur.fetchall() or []
        return [str(row[0]) for row in rows if row and row[0]]
    finally:
        cur.close()


def _choose_preferred_schema(conn) -> str | None:
    cur = conn.cursor()
    try:
        excluded = {
            "information_schema",
            "mysql",
            "performance_schema",
            "sys",
            MEMORY_DB,
        }
        cur.execute(
            """
SELECT `TABLE_SCHEMA`, COUNT(*) AS `table_count`
FROM `information_schema`.`TABLES`
GROUP BY `TABLE_SCHEMA`
ORDER BY `table_count` DESC, `TABLE_SCHEMA`
            """
        )
        rows = cur.fetchall() or []
    finally:
        cur.close()

    candidates: list[tuple[str, int]] = []
    for schema_name, table_count in rows:
        name = str(schema_name)
        if name in excluded:
            continue
        try:
            count = int(table_count)
        except Exception:
            count = 0
        if count <= 0:
            continue
        candidates.append((name, count))
    if not candidates:
        return None
    return candidates[0][0]


def _token_matches(text: str, token: str) -> bool:
    if not text or not token:
        return False
    lower_text = text.lower()
    lower_token = token.lower()
    return lower_token in lower_text


def _pick_table_from_prompt(nl: str, schema_meta: dict[str, Any]) -> str | None:
    tables = schema_meta.get("tables", []) if isinstance(schema_meta, dict) else []
    if not tables:
        return None
    for table in sorted(tables, key=len, reverse=True):
        if _token_matches(nl, table):
            return table
    # 비전문가 질의에서 "주문"을 "order"로 자주 표현하는 경우를 보정.
    if "주문" in nl and "order" in tables:
        return "order"
    if len(tables) == 1:
        return tables[0]
    return None


def _pick_columns_from_prompt(nl: str, table_name: str, schema_meta: dict[str, Any]) -> list[dict[str, str]]:
    columns_by_table = schema_meta.get("columns_by_table", {}) if isinstance(schema_meta, dict) else {}
    candidates = columns_by_table.get(table_name, [])
    matched = []
    for col in sorted(candidates, key=lambda x: len(x["name"]), reverse=True):
        if _token_matches(nl, col["name"]):
            matched.append(col)
    return matched


def _pick_numeric_column(columns: list[dict[str, str]]) -> dict[str, str] | None:
    for col in columns:
        if col.get("data_type", "").lower() in NUMERIC_DATA_TYPES:
            return col
    return None


DATE_TOKEN_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?")
USER_ID_CANDIDATES = ("accountid", "userid", "playerid", "uid")


def _extract_explicit_date_range(nl: str) -> tuple[str | None, str | None]:
    if not nl:
        return None, None
    tokens = [m.group(0) for m in DATE_TOKEN_RE.finditer(nl)]
    if not tokens:
        return None, None

    start = None
    end = None
    for m in DATE_TOKEN_RE.finditer(nl):
        token = m.group(0)
        prefix = nl[max(0, m.start() - 10) : m.start()]
        if re.search(r"(시작|from|start)", prefix, re.IGNORECASE):
            start = token
        if re.search(r"(종료|끝|to|end)", prefix, re.IGNORECASE):
            end = token

    if not start and tokens:
        start = tokens[0]
    if not end and len(tokens) > 1:
        end = tokens[1]
    return start, end


def _contains_time_intent(nl: str) -> bool:
    start, end = _extract_explicit_date_range(nl)
    if start or end:
        return True
    if re.search(r"(오늘|어제|최근|지난)", nl):
        return True
    return bool(re.search(r"\d+\s*(일|주|개월|달|월|년)", nl))


def _pick_date_column(columns: list[dict[str, str]]) -> dict[str, str] | None:
    for col in columns:
        if col.get("data_type", "").lower() in DATE_DATA_TYPES:
            return col
    return None


def _build_time_where_clause(nl: str, date_column: str) -> str:
    # Policy: 코드 템플릿 SQL/WHERE 생성 금지. 시간 필터는 LLM이 작성한다.
    return ""


def _contains_user_daily_intent(nl: str) -> bool:
    if not nl:
        return False
    user = any(token in nl for token in ("유저별", "사용자별", "계정별", "아이디별"))
    daily = any(token in nl for token in ("일별", "일 단위", "일평균", "일 평균"))
    return user and daily


def _pick_user_id_column(columns: list[dict[str, str]]) -> dict[str, str] | None:
    if not columns:
        return None
    for cand in USER_ID_CANDIDATES:
        for col in columns:
            if col.get("name", "").lower() == cand:
                return col
    for col in columns:
        name = col.get("name", "").lower()
        if name.endswith("id") and name not in ("id", "idx", "index"):
            return col
    return None


def _build_stats_select_sql(
    nl: str,
    table_name: str,
    column_name: str | None,
    where_clause: str | None = None,
) -> str | None:
    # Policy: 코드 템플릿 SQL(COUNT(*)/AVG/SUM 등) 생성 금지. SQL은 오직 LLM이 작성한다.
    return None


SCHEMA_USAGE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("이벤트/보상", ("event", "reward", "mission", "gachapon", "coupon")),
    ("서버/채널/룸", ("server", "channel", "room", "address", "notify", "authorize", "authen")),
    ("접속/제어", ("disconnect", "ban", "allow", "deny", "ip", "auth")),
    ("거래/상점", ("trade", "shop", "item", "dlc", "price")),
    ("유저/통계", ("user", "count", "tf_", "stat", "metric")),
)


def _contains_structure_intent(text: str) -> bool:
    # Policy: keyword-based request intent heuristics are disabled.
    # Keep compatibility for explicit metadata SQL only.
    raw = str(text or "").strip()
    if not raw:
        return False
    if looks_like_sql(raw):
        return bool(re.search(r"\binformation_schema\b", raw, re.IGNORECASE))
    return False


def _question_needs_structure(question: str) -> bool:
    # Policy: keyword-based question classification is disabled.
    return _contains_structure_intent(question)


def _is_generic_clarification_question(question: str) -> bool:
    text = " ".join(str(question or "").split()).strip().lower()
    if not text:
        return False
    generic = {
        "요청 내용을 조금 더 구체적으로 알려주세요.",
        "요청 내용을 조금 더 구체적으로 알려주세요",
        "요청 내용을 더 구체적으로 알려주세요.",
        "요청 내용을 더 구체적으로 알려주세요",
        "요청을 구체적으로 알려주세요.",
        "요청을 구체적으로 알려주세요",
        "요청을 좀 더 구체적으로 알려주세요.",
        "요청을 좀 더 구체적으로 알려주세요",
        "mcp 도구 호출을 위해 필요한 정보가 부족합니다. 요청을 구체화해 주세요.",
        "mcp 도구 호출을 위해 필요한 정보가 부족합니다. 요청을 구체화해 주세요",
        "실행할 sql 의도를 구체적으로 알려주세요.",
        "실행할 sql 의도를 구체적으로 알려주세요",
    }
    return text in generic


def _is_schema_usage_intent(text: str) -> bool:
    # Policy: keyword-based request intent heuristics are disabled.
    return False


def _build_schema_usage_answer_from_compact(
    request_text: str,
    schema_hint: str,
    compact: list[dict[str, Any]] | None,
) -> str:
    if not _is_schema_usage_intent(request_text):
        return ""
    if not isinstance(compact, list) or not compact:
        return ""
    safe_hint = _sanitize_ident_part(schema_hint)
    by_schema: dict[str, list[str]] = {}
    for item in compact:
        if not isinstance(item, dict):
            continue
        schema = _sanitize_ident_part(str(item.get("schema") or "").strip())
        table = _sanitize_ident_part(str(item.get("name") or "").strip())
        if not table:
            continue
        key = schema or "__unknown__"
        bucket = by_schema.setdefault(key, [])
        if table not in bucket:
            bucket.append(table)
    if not by_schema:
        return ""
    resolved_schema = safe_hint
    tables: list[str] = []
    if resolved_schema and resolved_schema in by_schema:
        tables = by_schema.get(resolved_schema, [])
    if not tables:
        resolved_schema = sorted(by_schema.keys(), key=lambda s: (-len(by_schema[s]), s))[0]
        tables = by_schema.get(resolved_schema, [])
    if not tables:
        return ""

    group_counts: dict[str, int] = {}
    for table in tables:
        lower = table.lower()
        matched = False
        for label, tokens in SCHEMA_USAGE_GROUPS:
            if any(token in lower for token in tokens):
                group_counts[label] = group_counts.get(label, 0) + 1
                matched = True
                break
        if not matched:
            group_counts["기타"] = group_counts.get("기타", 0) + 1
    top_groups = sorted(group_counts.items(), key=lambda x: (-int(x[1]), x[0]))
    group_text = ", ".join([f"{name} {cnt}개" for name, cnt in top_groups[:3]]) if top_groups else ""
    sample_tables = ", ".join(tables[:6])
    schema_text = resolved_schema if resolved_schema != "__unknown__" else "해당"
    lines = [
        f"`{schema_text}` 스키마는 운영 메타데이터 성격의 객체를 담는 DB로 보입니다.",
        f"확인된 테이블 {len(tables)}개 (예: {sample_tables}).",
    ]
    if group_text:
        lines.append(f"주요 영역: {group_text}.")
    lines.append("정확한 업무 규칙은 핵심 테이블 정의/애플리케이션 로직과 함께 교차 확인이 필요합니다.")
    return _format_user_answer_text(" ".join(lines))


def _extract_schema_table_candidates(
    nl: str,
    kv: dict[str, str] | None,
    schema_meta: dict[str, Any] | None,
) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    text = nl or ""
    schemas: set[str] = set()
    tables: set[str] = set()
    schema_tables: list[tuple[str, str]] = []

    for match in re.finditer(r"`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?", text):
        schema = match.group(1)
        table = match.group(2)
        if schema and table:
            schema_tables.append((schema, table))
            schemas.add(schema)
            tables.add(table)

    schema_meta = schema_meta or {}
    table_hint = _pick_table_from_prompt(text, schema_meta)
    if table_hint:
        tables.add(table_hint)

    kv = kv or {}
    last_search_raw = kv.get("last_search_objects")
    if last_search_raw:
        try:
            compact = json.loads(last_search_raw)
        except Exception:
            compact = []
        if isinstance(compact, list) and compact:
            item = compact[0]
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if name:
                    tables.add(name)
                schema = str(item.get("schema", "")).strip()
                if schema:
                    schemas.add(schema)

    return schema_tables, list(schemas), list(tables)


def _compact_schema_meta_for_request(
    schema_meta: dict[str, Any],
    request: str,
    kv: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(schema_meta, dict):
        return {}
    tables = schema_meta.get("tables") or []
    columns_by_table = schema_meta.get("columns_by_table") or {}
    if not tables:
        return {}

    kv = kv or {}
    schema_tables, _schemas, table_candidates = _extract_schema_table_candidates(
        request or "", kv, schema_meta
    )
    mention_tables, mention_refs = _extract_request_table_mentions(request or "", schema_meta)
    selected: list[str] = []
    if schema_tables:
        selected = [t for _schema, t in schema_tables if t]
    elif mention_refs:
        selected = [
            ref.split(".", 1)[1]
            for ref in mention_refs
            if "." in ref and ref.split(".", 1)[1]
        ]
    elif mention_tables:
        selected = list(mention_tables)
    elif table_candidates:
        selected = list(table_candidates)

    if not selected:
        selected = tables[: max(1, AGENT_SCHEMA_META_MAX_TABLES)]
    else:
        selected_set = set(selected)
        ordered = [t for t in tables if t in selected_set]
        selected = ordered[: max(1, AGENT_SCHEMA_META_MAX_TABLES)]

    compact_cols: dict[str, list[dict[str, str]]] = {}
    for table in selected:
        cols = columns_by_table.get(table, [])
        if AGENT_SCHEMA_META_MAX_COLS > 0:
            compact_cols[table] = cols[:AGENT_SCHEMA_META_MAX_COLS]
        else:
            compact_cols[table] = cols

    return {"tables": selected, "columns_by_table": compact_cols}


def _detect_requested_schema(
    text: str, known_schemas: list[str] | None = None
) -> str | None:
    if not text:
        return None
    candidates = known_schemas or KNOWN_SCHEMAS
    if not candidates:
        return None
    name_map = {str(name).lower(): str(name) for name in candidates if str(name).strip()}
    # LLM 원문 해석 우선 정책:
    # 코드에서는 schema.table 형태로 명시된 경우만 스키마를 감지한다.
    for match in re.finditer(r"`?([A-Za-z0-9_]+)`?\s*\.\s*`?[A-Za-z0-9_]+`?", text):
        schema = str(match.group(1) or "").strip().lower()
        if schema and schema in name_map:
            return name_map[schema]
    if looks_like_sql(text):
        lowered = text.lower()
        for key, val in name_map.items():
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(key)}\s*\.", lowered):
                return val
    # Plain-text schema mention support (exact match only).
    lowered_text = " ".join(str(text or "").lower().split())
    for key, val in name_map.items():
        if re.search(rf"(?<![a-z0-9_]){re.escape(key)}(?![a-z0-9_])", lowered_text):
            return val
    return None


def _infer_schema_from_request(text: str, schema_meta: dict[str, Any] | None = None) -> str | None:
    if not text:
        return None
    detected = _detect_requested_schema(text, KNOWN_SCHEMAS)
    if detected:
        return detected
    schema_tables, schemas, _ = _extract_schema_table_candidates(text, None, schema_meta)
    if schema_tables:
        schema, _table = schema_tables[0]
        if schema:
            return schema
    if schemas:
        return schemas[0]
    return None


_FOLLOWUP_CUES = (
    "다시", "이어서", "이어 ", "거기서", "해당 ", "그거", "그것", "아까",
    "위에서", "방금", "앞서", "이전에", "마저", "계속", "추가로",
    "나타나지 않", "출력되지 않", "안 나", "안나", "빠져있",
    "결과에서", "결과를", "수정해", "바꿔", "변경해",
)


def _looks_like_followup_request(text: str) -> bool:
    if not text:
        return False
    lowered = text.strip().lower()
    if _looks_confirmation_followup(text):
        return True
    if lowered in {"continue", "continue.", "계속", "계속.", "다음", "진행", "계속 진행", "이어서 진행"}:
        return True
    if any(cue in lowered for cue in _FOLLOWUP_CUES):
        return True


def _coerce_schema_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return [item for item in items if item]
    return []

def _pick_table_candidates(
    items: list[dict[str, Any]], pattern: str, max_items: int
) -> list[dict[str, Any]]:
    if not items:
        return []
    seen = set()
    ordered: list[dict[str, Any]] = []
    token = re.sub(r"[%_]", "", str(pattern or "")).strip().lower()

    def _add(item: dict[str, Any]) -> None:
        name = str(item.get("name", "")).strip()
        schema = str(item.get("schema", "")).strip()
        if not name:
            return
        key = f"{schema}.{name}".lower()
        if key in seen:
            return
        seen.add(key)
        ordered.append(item)

    if token:
        for item in items:
            name = str(item.get("name", "")).lower()
            if token and token in name:
                _add(item)
            if len(ordered) >= max_items:
                return ordered

    for item in items:
        _add(item)
        if len(ordered) >= max_items:
            break
    return ordered

