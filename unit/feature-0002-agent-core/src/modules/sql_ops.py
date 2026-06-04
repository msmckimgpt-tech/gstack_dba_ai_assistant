import difflib
import mysql.connector
import re
import sys
import time
__all__ = [
    "_build_validation_sql",
    "_extract_primary_table_ref_from_sql",
    "_extract_schema_name_from_error",
    "_extract_table_name_from_error",
    "_extract_unknown_column",
    "_is_sql_syntax_error",
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


def _validate_sql_probe(conn, sql_text: str) -> bool:
    if not conn or not sql_text:
        return False
    try:
        execute_sql(conn, sql_text)
        return True
    except Exception:
        return False


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



