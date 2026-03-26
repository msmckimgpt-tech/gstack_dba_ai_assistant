import difflib
import mysql.connector
import re
import sys
import time
__all__ = [
    "_auto_recover_not_found_sql",
    "_build_validation_sql",
    "_extract_primary_table_ref_from_sql",
    "_extract_schema_name_from_error",
    "_extract_table_name_from_error",
    "_extract_unknown_column",
    "_is_sql_syntax_error",
    "_load_known_schemas_via_mcp",
    "_load_table_candidates_via_mcp",
    "_mcp_auto_retry",
    "_replace_column_in_sql",
    "_replace_schema_in_sql",
    "_replace_table_in_sql",
    "_resolve_conversation_by_index",
    "_safe_fix_missing_column_sql",
    "_should_auto_continue_on_error",
    "_validate_sql_probe",
]


"""SQL parsing, validation, auto-recovery, rewriting."""
from .config import *
import json, re, time
from typing import Any

_TABLE_REF_RE = re.compile(
    r"(?:FROM|JOIN)\s+`?([A-Za-z0-9_]+)`?\s*\.\s*`?([A-Za-z0-9_]+)`?",
    re.IGNORECASE,
)
_EXCLUDED_SCHEMAS_FOR_REF = {
    "information_schema", "mysql", "performance_schema", "sys", "agent_memory",
}


def _extract_primary_table_ref_from_sql(sql: str) -> str:
    """SQL의 FROM/JOIN 절에서 첫 번째 schema.table 참조를 추출한다."""
    if not sql:
        return ""
    for m in _TABLE_REF_RE.finditer(sql):
        schema = (m.group(1) or "").strip().lower()
        table = (m.group(2) or "").strip().lower()
        if schema in _EXCLUDED_SCHEMAS_FOR_REF:
            continue
        if table:
            return f"{schema}.{table}" if schema else table
    return ""


def _is_sql_syntax_error(msg: str, code: Any = None) -> bool:
    if code is not None:
        try:
            code_str = str(code).strip()
        except Exception:
            code_str = ""
        if code_str in ("1064", "1149", "ER_PARSE_ERROR", "SQL_PARSE_ERROR", "PARSER_ERROR", "SYNTAX_ERROR"):
            return True
    text = (msg or "").lower()
    if "syntax" in text or "parse error" in text:
        return True
    if "you have an error in your sql syntax" in text:
        return True
    return False


def _should_auto_continue_on_error(msg: str) -> bool:
    if not msg:
        return False
    text = (msg or "").lower()
    patterns = (
        "unknown column",
        "doesn't exist",
        "does not exist",
        "unknown table",
        "table doesn't exist",
        "table does not exist",
        "no such table",
        "unknown database",
        "ambiguous",
        "syntax",
        "not found",
    )
    return any(p in text for p in patterns)


def _extract_unknown_column(msg: str) -> str | None:
    if not msg:
        return None
    m = re.search(r"Unknown column '([^']+)'", msg, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"Column '([^']+)'\s+does(?:\s+not|n't)\s+exist", msg, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"Unknown column `([^`]+)`", msg, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _safe_fix_missing_column_sql(sql: str, missing_col: str) -> str | None:
    # Policy: 코드 템플릿 SQL(COUNT(*) 등) 생성/주입 금지.
    # 누락 컬럼 수정은 LLM fix 경로(llm_fix_sql)에 위임한다.
    return None


def _extract_schema_name_from_error(msg: str) -> str | None:
    if not msg:
        return None
    m = re.search(r"Unknown database '([^']+)'", msg)
    if m:
        return m.group(1)
    m = re.search(r"Database '([^']+)' does(?: not|n't) exist", msg, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"Schema '([^']+)' does not exist", msg)
    if m:
        return m.group(1)
    m = re.search(r"Schema `([^`]+)` does not exist", msg)
    if m:
        return m.group(1)
    return None


def _extract_table_name_from_error(msg: str) -> tuple[str | None, str | None]:
    if not msg:
        return None, None
    m = re.search(r"Table '([^']+)'\s+does(?: not|n't)\s+exist", msg, re.IGNORECASE)
    if m:
        full = m.group(1).strip()
        if "." in full:
            schema, table = full.split(".", 1)
            return schema.strip("`"), table.strip("`")
        return None, full.strip("`")
    m = re.search(r"Unknown table '([^']+)'", msg, re.IGNORECASE)
    if m:
        full = m.group(1).strip()
        if "." in full:
            schema, table = full.split(".", 1)
            return schema.strip("`"), table.strip("`")
        return None, full.strip("`")
    return None, None


def _replace_schema_in_sql(sql: str, old_schema: str, new_schema: str) -> str:
    if not sql or not old_schema or not new_schema:
        return sql
    if old_schema == new_schema:
        return sql
    updated = sql
    updated = re.sub(
        rf"`{re.escape(old_schema)}`\.",
        f"`{new_schema}`.",
        updated,
    )
    updated = re.sub(
        rf"\b{re.escape(old_schema)}\.",
        f"{new_schema}.",
        updated,
    )
    return updated


def _replace_table_in_sql(sql: str, old_table: str, new_table: str, schema_hint: str = "") -> str:
    if not sql or not old_table or not new_table:
        return sql
    old = re.escape(old_table)
    schema_hint = str(schema_hint or "").strip().replace("`", "")
    pattern = re.compile(
        rf"(?i)\b(FROM|JOIN|UPDATE|INTO)\s+((`?[A-Za-z0-9_]+`?\.)?)`?{old}`?\b"
    )

    def _repl(match: re.Match) -> str:
        keyword = match.group(1)
        schema_prefix = match.group(2) or ""
        if schema_hint:
            return f"{keyword} `{schema_hint}`.`{new_table}`"
        if schema_prefix:
            return f"{keyword} {schema_prefix}`{new_table}`"
        return f"{keyword} `{new_table}`"

    updated = pattern.sub(_repl, sql)
    if updated == sql:
        updated = re.sub(
            rf"(?i)\b`?{old}`?\b",
            f"`{new_table}`",
            sql,
            count=1,
        )
    return updated


def _replace_column_in_sql(sql: str, old_col: str, new_col: str) -> str:
    if not sql or not old_col or not new_col:
        return sql
    old = re.escape(old_col)
    pattern = re.compile(rf"(?i)(`?){old}(`?)")
    return pattern.sub(f"`{new_col}`", sql)


def _build_validation_sql(schema: str, table: str, column: str = "") -> str:
    table = str(table or "").strip().replace("`", "")
    if not table:
        return ""
    schema = str(schema or "").strip().replace("`", "")
    column = str(column or "").strip().replace("`", "")
    target = f"`{schema}`.`{table}`" if schema else f"`{table}`"
    if column:
        return f"SELECT `{column}` FROM {target} LIMIT 1"
    return f"SELECT 1 FROM {target} LIMIT 1"


def _load_known_schemas_via_mcp(limit: int = 20) -> list[str]:
    if AGENT_MODE != "mcp":
        return []
    sql_tool = MCP_EXECUTE_SQL_CANDIDATES[0] if MCP_EXECUTE_SQL_CANDIDATES else ""
    if not sql_tool:
        return []
    try:
        result = mcp_call(sql_tool, {"sql": "SHOW DATABASES"})
    except Exception:
        return []
    err_msg, _err_code = _mcp_error_info(result)
    if err_msg:
        return []
    sets = _mcp_result_to_result_sets(result)
    if not sets:
        return []
    names: list[str] = []
    for row in sets[0].rows[: max(1, int(limit))]:
        schema_name = ""
        if isinstance(row, dict):
            for key in ("Database", "database", "SCHEMA_NAME", "schema_name"):
                if key in row:
                    schema_name = str(row.get(key) or "").strip()
                    if schema_name:
                        break
            if not schema_name and row:
                first_key = next(iter(row.keys()))
                schema_name = str(row.get(first_key) or "").strip()
        elif isinstance(row, (list, tuple)) and row:
            schema_name = str(row[0] or "").strip()
        if not schema_name:
            continue
        if _is_system_schema(schema_name) or _should_block_default_schema(schema_name):
            continue
        names.append(schema_name)
    uniq: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(name)
    return uniq[: max(1, int(limit))]


def _load_table_candidates_via_mcp(
    schema: str = "",
    pattern: str = "",
    limit: int = 20,
) -> list[tuple[str, str]]:
    if AGENT_MODE != "mcp":
        return []
    sql_tool = MCP_EXECUTE_SQL_CANDIDATES[0] if MCP_EXECUTE_SQL_CANDIDATES else ""
    if not sql_tool:
        return []
    esc_schema = str(schema or "").strip().replace("'", "''")
    esc_pattern = str(pattern or "").strip().replace("'", "''")
    where_clauses = [
        "TABLE_SCHEMA NOT IN ('information_schema','mysql','performance_schema','sys')"
    ]
    if esc_schema:
        where_clauses.append(f"TABLE_SCHEMA = '{esc_schema}'")
    if esc_pattern:
        where_clauses.append(f"TABLE_NAME LIKE '%{esc_pattern}%'")
    sql = (
        "SELECT TABLE_SCHEMA, TABLE_NAME "
        "FROM information_schema.TABLES "
        f"WHERE {' AND '.join(where_clauses)} "
        "ORDER BY TABLE_SCHEMA, TABLE_NAME "
        f"LIMIT {max(1, int(limit))}"
    )
    try:
        result = mcp_call(sql_tool, {"sql": sql})
    except Exception:
        return []
    err_msg, _err_code = _mcp_error_info(result)
    if err_msg:
        return []
    sets = _mcp_result_to_result_sets(result)
    if not sets:
        return []
    rows: list[tuple[str, str]] = []
    for row in sets[0].rows[: max(1, int(limit))]:
        schema_name = ""
        table_name = ""
        if isinstance(row, dict):
            schema_name = str(
                row.get("TABLE_SCHEMA")
                or row.get("table_schema")
                or row.get("schema")
                or row.get("SCHEMA")
                or ""
            ).strip()
            table_name = str(
                row.get("TABLE_NAME")
                or row.get("table_name")
                or row.get("name")
                or row.get("NAME")
                or ""
            ).strip()
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            schema_name = str(row[0] or "").strip()
            table_name = str(row[1] or "").strip()
        schema_name = _sanitize_ident_part(schema_name)
        table_name = _sanitize_ident_part(table_name)
        if not schema_name or not table_name:
            continue
        if _is_system_schema(schema_name) or _should_block_default_schema(schema_name):
            continue
        rows.append((schema_name, table_name))
    uniq: list[tuple[str, str]] = []
    seen: set[str] = set()
    for schema_name, table_name in rows:
        key = f"{schema_name}.{table_name}".lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((schema_name, table_name))
    return uniq[: max(1, int(limit))]


def _validate_sql_probe(conn, sql_text: str) -> bool:
    if not conn or not sql_text:
        return False
    try:
        execute_sql(conn, sql_text)
        return True
    except Exception:
        return False


def _auto_recover_not_found_sql(
    conn,
    sql_text: str,
    err_msg: str,
    err_code: Any,
    request_text: str,
    kv: dict[str, Any] | None = None,
    known_schemas: list[str] | None = None,
) -> tuple[str, str, str] | None:
    if not AGENT_ERROR_AUTO_RECOVERY:
        return None
    if not sql_text or not err_msg:
        return None
    title, _hint = _classify_error_message(err_msg, err_code)
    if title not in {"스키마 없음", "테이블 없음", "컬럼 없음"}:
        return None
    kv = kv or {}
    known_schemas = known_schemas or KNOWN_SCHEMAS
    schema_cur, table_cur = _extract_first_table_from_sql(sql_text)

    if title == "스키마 없음":
        missing_schema = _extract_schema_name_from_error(err_msg) or (schema_cur or "")
        schema_candidates: list[str] = []
        for s in known_schemas:
            name = str(s or "").strip()
            if not name or _is_system_schema(name) or _should_block_default_schema(name):
                continue
            schema_candidates.append(name)
        if conn:
            cur = conn.cursor()
            try:
                token = missing_schema or _detect_requested_schema(request_text, known_schemas) or ""
                if token:
                    cur.execute(
                        """
SELECT SCHEMA_NAME
FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME NOT IN ('information_schema','mysql','performance_schema','sys')
  AND SCHEMA_NAME LIKE %s
LIMIT 8
                        """,
                        (f"%{token}%",),
                    )
                    schema_candidates.extend([str(r[0]) for r in (cur.fetchall() or []) if r and r[0]])
            except Exception:
                pass
            finally:
                cur.close()
        preferred = str(kv.get("preferred_schema") or "").strip()
        if preferred and not _should_block_default_schema(preferred):
            schema_candidates.insert(0, preferred)
        if not schema_candidates:
            schema_candidates.extend(_load_known_schemas_via_mcp(limit=12))
        schema_candidates = [
            s
            for s in schema_candidates
            if s and not _is_system_schema(s) and not _should_block_default_schema(s)
        ]
        picked = ""
        for cand in schema_candidates:
            if missing_schema and cand.lower() == missing_schema.lower():
                continue
            picked = cand
            break
        if not picked:
            return None
        recovered = (
            _replace_schema_in_sql(sql_text, missing_schema, picked)
            if missing_schema
            else _prefix_use_schema(sql_text, picked)
        )
        recovered_table = _sanitize_ident_part(table_cur or "")
        if conn and recovered_table:
            cand_tables: list[str] = []
            cur = conn.cursor()
            try:
                cur.execute(
                    """
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME
LIMIT 120
                    """,
                    (picked,),
                )
                cand_tables.extend(
                    [_sanitize_ident_part(str(r[0])) for r in (cur.fetchall() or []) if r and r[0]]
                )
            except Exception:
                pass
            finally:
                cur.close()
            unique_tables: list[str] = []
            seen_tables: set[str] = set()
            for name in cand_tables:
                key = str(name or "").strip().lower()
                if not key or key in seen_tables:
                    continue
                seen_tables.add(key)
                unique_tables.append(str(name))
            if unique_tables and not any(t.lower() == recovered_table.lower() for t in unique_tables):
                ranked_tables = sorted(
                    unique_tables,
                    key=lambda t: difflib.SequenceMatcher(
                        None,
                        recovered_table.lower(),
                        t.lower(),
                    ).ratio(),
                    reverse=True,
                )
                picked_table = ""
                for cand in ranked_tables:
                    score = difflib.SequenceMatcher(
                        None,
                        recovered_table.lower(),
                        cand.lower(),
                    ).ratio()
                    if score < 0.34:
                        continue
                    picked_table = _sanitize_ident_part(cand)
                    break
                if picked_table:
                    recovered = _replace_table_in_sql(
                        recovered,
                        recovered_table,
                        picked_table,
                        schema_hint=picked,
                    )
                    recovered_table = picked_table
        if not conn and recovered_table:
            mcp_tables = _load_table_candidates_via_mcp(
                schema=picked,
                pattern=recovered_table,
                limit=24,
            )
            candidate_names = [
                _sanitize_ident_part(name) for schema_name, name in mcp_tables if schema_name == picked
            ]
            if candidate_names and not any(n.lower() == recovered_table.lower() for n in candidate_names):
                ranked_tables = sorted(
                    candidate_names,
                    key=lambda t: difflib.SequenceMatcher(
                        None,
                        recovered_table.lower(),
                        t.lower(),
                    ).ratio(),
                    reverse=True,
                )
                for cand in ranked_tables:
                    score = difflib.SequenceMatcher(
                        None,
                        recovered_table.lower(),
                        cand.lower(),
                    ).ratio()
                    if score < 0.34:
                        continue
                    cand = _sanitize_ident_part(cand)
                    if not cand:
                        continue
                    recovered = _replace_table_in_sql(
                        recovered,
                        recovered_table,
                        cand,
                        schema_hint=picked,
                    )
                    recovered_table = cand
                    break
        validation = "SELECT 1"
        if conn and recovered_table:
            probe_sql = _build_validation_sql(picked, recovered_table)
            if probe_sql:
                validation = probe_sql
        return recovered, validation, f"schema:{missing_schema or '?'}->{picked}"

    if title == "테이블 없음":
        err_schema, err_table = _extract_table_name_from_error(err_msg)
        base_schema = (
            err_schema
            or schema_cur
            or str(kv.get("preferred_schema") or "").strip()
            or _detect_requested_schema(request_text, known_schemas)
            or _preferred_default_schema(known_schemas)
        )
        target_table = _sanitize_ident_part(err_table or table_cur or "")
        if not target_table:
            return None
        table_candidates: list[tuple[str, str]] = []
        compact = _load_last_search_objects_compact(kv)
        for item in compact:
            name = _sanitize_ident_part(str(item.get("name") or "").strip())
            schema = _sanitize_ident_part(str(item.get("schema") or "").strip()) or base_schema
            if not name or _is_system_schema(schema):
                continue
            if target_table.lower() in name.lower():
                table_candidates.append((schema, name))
        if conn:
            cur = conn.cursor()
            try:
                if base_schema:
                    cur.execute(
                        """
SELECT TABLE_SCHEMA, TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s
  AND TABLE_NAME LIKE %s
ORDER BY TABLE_NAME
LIMIT 8
                        """,
                        (base_schema, f"%{target_table}%"),
                    )
                    table_candidates.extend(
                        [
                            (_sanitize_ident_part(str(r[0])), _sanitize_ident_part(str(r[1])))
                            for r in (cur.fetchall() or [])
                            if r and r[0] and r[1]
                        ]
                    )
                cur.execute(
                    """
SELECT TABLE_SCHEMA, TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA NOT IN ('information_schema','mysql','performance_schema','sys')
  AND TABLE_NAME LIKE %s
ORDER BY TABLE_SCHEMA, TABLE_NAME
LIMIT 12
                    """,
                    (f"%{target_table}%",),
                )
                table_candidates.extend(
                    [
                        (_sanitize_ident_part(str(r[0])), _sanitize_ident_part(str(r[1])))
                        for r in (cur.fetchall() or [])
                            if r and r[0] and r[1]
                        ]
                    )
            except Exception:
                pass
            finally:
                cur.close()
        if not conn:
            table_candidates.extend(
                _load_table_candidates_via_mcp(
                    schema=base_schema or "",
                    pattern=target_table,
                    limit=24,
                )
            )
        if conn and not table_candidates and base_schema:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
SELECT TABLE_SCHEMA, TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME
LIMIT 80
                    """,
                    (base_schema,),
                )
                table_candidates.extend(
                    [
                            (_sanitize_ident_part(str(r[0])), _sanitize_ident_part(str(r[1])))
                            for r in (cur.fetchall() or [])
                            if r and r[0] and r[1]
                        ]
                )
            except Exception:
                pass
            finally:
                cur.close()
        if not conn and not table_candidates and base_schema:
            table_candidates.extend(
                _load_table_candidates_via_mcp(
                    schema=base_schema,
                    pattern="",
                    limit=80,
                )
            )
        unique_candidates: list[tuple[str, str]] = []
        seen_candidates: set[str] = set()
        for cand_schema, cand_table in table_candidates:
            cand_schema = _sanitize_ident_part(cand_schema)
            cand_table = _sanitize_ident_part(cand_table)
            key = f"{cand_schema}.{cand_table}".lower()
            if not cand_table or key in seen_candidates:
                continue
            seen_candidates.add(key)
            unique_candidates.append((cand_schema, cand_table))
        target_lower = target_table.lower()
        ranked: list[tuple[float, str, str]] = []
        for cand_schema, cand_table in unique_candidates:
            score = difflib.SequenceMatcher(None, target_lower, cand_table.lower()).ratio()
            if base_schema and cand_schema and cand_schema.lower() == str(base_schema).lower():
                score += 0.12
            ranked.append((score, cand_schema, cand_table))
        ranked.sort(key=lambda x: x[0], reverse=True)
        picked_schema = ""
        picked_table = ""
        for score, cand_schema, cand_table in ranked:
            if target_table and cand_table.lower() == target_table.lower():
                continue
            if score < 0.38:
                continue
            picked_schema, picked_table = _sanitize_ident_part(cand_schema), _sanitize_ident_part(cand_table)
            break
        if not picked_table:
            return None
        recovered = _replace_table_in_sql(
            sql_text,
            target_table,
            picked_table,
            schema_hint=picked_schema or base_schema,
        )
        if err_schema and picked_schema and picked_schema.lower() != err_schema.lower():
            recovered = _replace_schema_in_sql(recovered, err_schema, picked_schema)
        validation = _build_validation_sql(picked_schema or base_schema, picked_table)
        if not validation:
            return None
        return recovered, validation, f"table:{target_table}->{picked_table}"

    if title == "컬럼 없음":
        missing_col = _extract_unknown_column(err_msg)
        if not missing_col:
            return None
        base_schema = (
            schema_cur
            or str(kv.get("preferred_schema") or "").strip()
            or _detect_requested_schema(request_text, known_schemas)
            or _preferred_default_schema(known_schemas)
        )
        base_table = table_cur or ""
        if not base_table:
            return None
        col_candidates: list[str] = []
        if conn:
            cur = conn.cursor()
            try:
                if base_schema:
                    cur.execute(
                        """
SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME LIKE %s
ORDER BY ORDINAL_POSITION
LIMIT 12
                        """,
                        (base_schema, base_table, f"%{missing_col}%"),
                    )
                else:
                    cur.execute(
                        """
SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_NAME = %s AND COLUMN_NAME LIKE %s
ORDER BY ORDINAL_POSITION
LIMIT 12
                        """,
                        (base_table, f"%{missing_col}%"),
                    )
                col_candidates.extend([str(r[0]) for r in (cur.fetchall() or []) if r and r[0]])
            except Exception:
                pass
            finally:
                cur.close()
        if not col_candidates:
            raw_summary = str(kv.get("last_result_summary") or "").strip()
            if raw_summary:
                try:
                    obj = json.loads(raw_summary)
                    names = obj.get("col_names") if isinstance(obj, dict) else None
                    if isinstance(names, list):
                        col_candidates.extend([str(c) for c in names if str(c).strip()])
                except Exception:
                    pass
        if conn and not col_candidates:
            cur = conn.cursor()
            try:
                if base_schema:
                    cur.execute(
                        """
SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
ORDER BY ORDINAL_POSITION
LIMIT 120
                        """,
                        (base_schema, base_table),
                    )
                else:
                    cur.execute(
                        """
SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_NAME = %s
ORDER BY ORDINAL_POSITION
LIMIT 120
                        """,
                        (base_table,),
                    )
                col_candidates.extend([str(r[0]) for r in (cur.fetchall() or []) if r and r[0]])
            except Exception:
                pass
            finally:
                cur.close()
        uniq_cols: list[str] = []
        seen_cols: set[str] = set()
        for cand in col_candidates:
            key = str(cand or "").strip().lower()
            if not key or key in seen_cols:
                continue
            seen_cols.add(key)
            uniq_cols.append(str(cand))
        picked_col = ""
        ranked_cols = sorted(
            uniq_cols,
            key=lambda c: difflib.SequenceMatcher(
                None,
                missing_col.lower(),
                str(c).lower(),
            ).ratio(),
            reverse=True,
        )
        for cand in ranked_cols:
            score = difflib.SequenceMatcher(None, missing_col.lower(), cand.lower()).ratio()
            if cand.lower() == missing_col.lower():
                continue
            if score < 0.35:
                continue
            picked_col = cand
            break
        if not picked_col:
            return None
        recovered = _replace_column_in_sql(sql_text, missing_col, picked_col)
        validation = _build_validation_sql(base_schema, base_table, picked_col)
        if not validation:
            return None
        return recovered, validation, f"column:{missing_col}->{picked_col}"

    return None


def _mcp_auto_retry(tool: str, args: dict[str, Any], result: Any) -> tuple[Any, dict[str, Any] | None]:
    if AGENT_DISABLE_AUTO_RETRY:
        return result, None
    err_msg, _ = _mcp_error_info(result)
    if not err_msg:
        return result, None
    target_db = DB_NAME_EFFECTIVE

    if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
        schema = str(args.get("schema", "")).strip()
        if schema and target_db and schema.lower() == target_db.lower() and schema != target_db:
            new_args = dict(args)
            new_args["schema"] = target_db
            retry_result = mcp_call(tool, new_args)
            return retry_result, new_args

    if tool in MCP_EXECUTE_SQL_CANDIDATES:
        schema = _extract_schema_name_from_error(err_msg)
        sql = str(args.get("sql", "")).strip()
        if schema and target_db and schema.lower() == target_db.lower() and sql:
            new_sql = _replace_schema_in_sql(sql, schema, target_db)
            if new_sql != sql:
                new_args = dict(args)
                new_args["sql"] = new_sql
                retry_result = mcp_call(tool, new_args)
                return retry_result, new_args

    return result, None


def _resolve_conversation_by_index(conn, index: int):
    rows = list_conversations(conn, limit=200)
    if index < 1 or index > len(rows):
        return None
    return rows[index - 1]



