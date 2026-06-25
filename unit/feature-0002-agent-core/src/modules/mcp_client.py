import urllib.request, urllib.error
import mysql.connector
import os
import re
import sys
import time
__all__ = [
    "_augment_search_objects_with_table_meta",
    "_compact_search_objects_result",
    "_extract_mcp_content",
    "_extract_table_targets_from_search_results",
    "_mcp_ensure_initialized",
    "_mcp_error_info",
    "_mcp_jsonrpc_request",
    "_mcp_result_to_result_sets",
    "_normalize_columns",
    "_normalize_search_object_type",
    "_normalize_search_pattern",
    "mcp_call",
    "mcp_list_tools",
    "mcp_tool_names",
    "mcp_tools_catalog",
    "normalize_local_args",
    "normalize_mcp_args",
]


"""MCP protocol client for DBHub MCP server."""
from shared.config import *
import json, os, re, urllib.error, urllib.request
from typing import Any
from shared import config as cfg

def _mcp_jsonrpc_request(method: str, params: dict[str, Any] | None = None, notify: bool = False):

    body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if not notify:
        body["id"] = cfg.MCP_REQUEST_ID
        cfg.MCP_REQUEST_ID += 1
    if params is not None:
        body["params"] = params

    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if cfg.MCP_SESSION_ID:
        headers["Mcp-Session-Id"] = cfg.MCP_SESSION_ID

    req = urllib.request.Request(MCP_URL, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=MCP_TIMEOUT_SEC) as resp:
        if not cfg.MCP_SESSION_ID:
            cfg.MCP_SESSION_ID = resp.headers.get("Mcp-Session-Id") or cfg.MCP_SESSION_ID
        if notify:
            return None

        raw = resp.read().decode("utf-8")
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "text/event-stream" in content_type or raw.startswith("event:"):
            data_lines = [
                line[len("data:") :].strip()
                for line in raw.splitlines()
                if line.startswith("data:")
            ]
            payload = json.loads(data_lines[-1]) if data_lines else {}
        else:
            payload = json.loads(raw)

        if isinstance(payload, dict) and "error" in payload:
            raise RuntimeError(f"MCP 오류: {payload.get('error')}")
        return payload.get("result") if isinstance(payload, dict) else payload


def _mcp_ensure_initialized() -> None:
    if cfg.MCP_SESSION_ID:
        return

    _mcp_jsonrpc_request(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mysql-ai-agent", "version": "1.0"},
        },
    )
    try:
        _mcp_jsonrpc_request("notifications/initialized", {}, notify=True)
    except Exception:
        pass


def _extract_mcp_content(result: Any) -> Any:
    if not isinstance(result, dict):
        return result

    if "structuredContent" in result:
        return result["structuredContent"]

    content = result.get("content")
    if not isinstance(content, list) or not content:
        return result

    for entry in content:
        if not isinstance(entry, dict):
            continue
        entry_type = entry.get("type")
        if entry_type == "json":
            return entry.get("json") or entry.get("data") or result
        if entry_type == "text":
            text = str(entry.get("text", "")).strip()
            if not text:
                continue
            try:
                return json.loads(text)
            except Exception:
                return {"text": text}
    return result


def mcp_list_tools() -> list[dict[str, Any]]:
    _mcp_ensure_initialized()
    try:
        result = _mcp_jsonrpc_request("tools/list", {}) or {}
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MCP tools/list 호출 실패: {exc}") from exc
    payload = _extract_mcp_content(result)
    if isinstance(payload, dict) and isinstance(payload.get("tools"), list):
        return payload["tools"]
    if isinstance(result, dict) and isinstance(result.get("tools"), list):
        return result["tools"]
    return []


def mcp_tool_names() -> list[str]:
    names: list[str] = []
    for tool in mcp_list_tools():
        if isinstance(tool, dict):
            name = str(tool.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def mcp_tools_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for tool in mcp_list_tools():
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name", "")).strip()
        if name:
            catalog[name] = tool
    return catalog


def _normalize_search_object_type(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    mapping = {
        "database": "schema",
        "databases": "schema",
        "db": "schema",
        "schema": "schema",
        "schemas": "schema",
        "스키마": "schema",
        "tables": "table",
        "table": "table",
        "테이블": "table",
        "columns": "column",
        "column": "column",
        "컬럼": "column",
        "열": "column",
        "procedures": "procedure",
        "procedure": "procedure",
        "프로시저": "procedure",
        "indexes": "index",
        "index": "index",
        "인덱스": "index",
        "all": "table",
        "*": "table",
        "any": "table",
    }
    if raw in mapping:
        return mapping[raw]
    return None


def _normalize_search_pattern(value: Any) -> str:
    pattern = str(value or "").strip()
    if not pattern:
        return ""
    if pattern in (".*", "*"):
        return "%"
    if "|" in pattern:
        pattern = pattern.split("|")[0].strip()
    if "," in pattern:
        pattern = pattern.split(",")[0].strip()
    if "*" in pattern and "%" not in pattern:
        pattern = pattern.replace("*", "%")
    if pattern and "%" not in pattern and "_" not in pattern:
        pattern = f"%{pattern}%"
    return pattern


def normalize_mcp_args(tool: str, args: dict[str, Any], tool_spec: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(args or {})

    if tool in MCP_EXECUTE_SQL_CANDIDATES:
        if "sql" not in normalized:
            for alias in ("query", "statement", "query_text"):
                if alias in normalized:
                    normalized["sql"] = normalized[alias]
                    break

    if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
        if "pattern" not in normalized:
            for alias in ("name", "keyword", "query", "search"):
                if alias in normalized:
                    normalized["pattern"] = normalized[alias]
                    break
        pattern = _normalize_search_pattern(normalized.get("pattern"))
        normalized["pattern"] = pattern or "%"

        object_type = _normalize_search_object_type(normalized.get("object_type"))
        if not object_type:
            object_type = "table"
        normalized["object_type"] = object_type
        # MCP search_objects: when object_type=table, prefer pattern and drop table filter.
        # Some servers reject "table" param unless object_type is column/index.
        if object_type == "table" and "table" in normalized:
            if not normalized.get("pattern"):
                normalized["pattern"] = normalized.get("table")
            normalized.pop("table", None)
        if "limit" not in normalized:
            normalized["limit"] = min(AGENT_TOP_N, 200)

    input_schema = tool_spec.get("inputSchema") if isinstance(tool_spec, dict) else None
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    if isinstance(properties, dict):
        normalized = {k: v for k, v in normalized.items() if k in properties}

    if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
        required = input_schema.get("required") if isinstance(input_schema, dict) else None
        required = required if isinstance(required, list) else []
        if "pattern" in required and not str(normalized.get("pattern", "")).strip():
            normalized["pattern"] = "%"
        if "object_type" in required and not str(normalized.get("object_type", "")).strip():
            normalized["object_type"] = "table"
        if "limit" in required and "limit" not in normalized:
            normalized["limit"] = min(AGENT_TOP_N, 200)
        for key in ("schema", "database", "db", "db_name"):
            if key in required and not str(normalized.get(key, "")).strip():
                normalized[key] = _required_schema_fallback()
        if isinstance(properties, dict):
            for key in ("schema", "database", "db", "db_name"):
                if key in properties and not str(normalized.get(key, "")).strip():
                    fallback = _preferred_default_schema()
                    if fallback:
                        normalized[key] = fallback

    return normalized


def normalize_local_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(args or {})
    if tool == "file_search":
        if "root" not in normalized:
            for key in ("path", "dir", "directory", "folder"):
                if key in normalized:
                    normalized["root"] = normalized[key]
                    break
        if "pattern" not in normalized:
            for key in ("name", "filename", "file", "keyword"):
                if key in normalized:
                    normalized["pattern"] = normalized[key]
                    break
        if "limit" in normalized and isinstance(normalized["limit"], str):
            try:
                normalized["limit"] = int(normalized["limit"].strip())
            except Exception:
                pass
    if tool == "file_read":
        if "file_path" not in normalized:
            for key in ("path", "file", "filename"):
                if key in normalized:
                    normalized["file_path"] = normalized[key]
                    break
        if "max_bytes" not in normalized:
            for key in ("limit", "max_size", "bytes", "max"):
                if key in normalized:
                    normalized["max_bytes"] = normalized[key]
                    break
        if "max_bytes" in normalized and isinstance(normalized["max_bytes"], str):
            try:
                normalized["max_bytes"] = int(normalized["max_bytes"].strip())
            except Exception:
                pass
    if tool == "restore_sql":
        if "file_path" not in normalized:
            for key in ("path", "file", "sql_file", "filename"):
                if key in normalized:
                    normalized["file_path"] = normalized[key]
                    break
        if "database" not in normalized:
            for key in ("db", "dbname", "target_db"):
                if key in normalized:
                    normalized["database"] = normalized[key]
                    break
        if "database" in normalized and isinstance(normalized["database"], str):
            db_val = normalized["database"].strip()
            if db_val.lower() in ("__use_db_name_in_file__", "__use_db_in_file__", "__use_file_db__"):
                normalized["database"] = ""
        if "overwrite" not in normalized:
            for key in ("force", "replace"):
                if key in normalized:
                    normalized["overwrite"] = bool(normalized[key])
                    break
        if "overwrite" in normalized and isinstance(normalized["overwrite"], str):
            normalized["overwrite"] = normalized["overwrite"].strip().lower() in ("1", "true", "yes", "y", "예")
    if tool == "convo_search":
        if "query" not in normalized:
            for key in ("q", "keyword", "text", "search"):
                if key in normalized:
                    normalized["query"] = normalized[key]
                    break
        if "limit" in normalized and isinstance(normalized["limit"], str):
            try:
                normalized["limit"] = int(normalized["limit"].strip())
            except Exception:
                pass
        if "include_current" in normalized and isinstance(normalized["include_current"], str):
            normalized["include_current"] = (
                normalized["include_current"].strip().lower() in ("1", "true", "yes", "y", "예")
            )
    return normalized


def mcp_call(tool: str, args: dict[str, Any]) -> Any:
    _mcp_ensure_initialized()
    try:
        result = _mcp_jsonrpc_request("tools/call", {"name": tool, "arguments": args})
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            cfg.MCP_SESSION_ID = None
            _mcp_ensure_initialized()
            result = _mcp_jsonrpc_request("tools/call", {"name": tool, "arguments": args})
        else:
            raise RuntimeError(f"MCP 호출 실패: {exc}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MCP 호출 실패: {exc}") from exc
    return _extract_mcp_content(result)


def _normalize_columns(columns: Any) -> list[str]:
    normalized: list[str] = []
    if not isinstance(columns, list):
        return normalized
    for col in columns:
        if isinstance(col, dict):
            normalized.append(str(col.get("name", "")))
        else:
            normalized.append(str(col))
    return normalized


def _mcp_result_to_result_sets(result: Any) -> list[tuple[str, Any, Any]]:
    result_sets: list[tuple[str, Any, Any]] = []

    if isinstance(result, dict):
        if isinstance(result.get("records"), list):
            cols, rows = records_to_columns_rows(result["records"])
            result_sets.append(("rows", cols, rows))
            return result_sets

        if isinstance(result.get("columns"), list) and isinstance(result.get("rows"), list):
            cols = _normalize_columns(result["columns"])
            rows = result["rows"]
            if rows and isinstance(rows[0], dict):
                mapped_rows = []
                for row in rows:
                    mapped_rows.append([row.get(col) for col in cols])
                rows = mapped_rows
            result_sets.append(("rows", cols, rows))
            return result_sets

        if isinstance(result.get("data"), list):
            data = result["data"]
            if data and isinstance(data[0], dict):
                cols, rows = records_to_columns_rows(data)
                result_sets.append(("rows", cols, rows))
                return result_sets
        if isinstance(result.get("data"), dict):
            data_obj = result["data"]
            if isinstance(data_obj.get("rows"), list):
                rows = data_obj["rows"]
                if rows and isinstance(rows[0], dict):
                    cols, mapped_rows = records_to_columns_rows(rows)
                    result_sets.append(("rows", cols, mapped_rows))
                    return result_sets
                if isinstance(data_obj.get("columns"), list):
                    cols = _normalize_columns(data_obj["columns"])
                    result_sets.append(("rows", cols, rows))
                    return result_sets
            if isinstance(data_obj.get("results"), list):
                results = data_obj["results"]
                if results and isinstance(results[0], dict):
                    cols, rows = records_to_columns_rows(results)
                    result_sets.append(("rows", cols, rows))
                    return result_sets
            if isinstance(data_obj.get("affected_rows"), int):
                result_sets.append(("rowcount", int(data_obj["affected_rows"]), None))
                return result_sets
            if isinstance(data_obj.get("count"), int) and not data_obj.get("rows"):
                result_sets.append(("rowcount", int(data_obj["count"]), None))
                return result_sets

        if isinstance(result.get("results"), list):
            for item in result["results"]:
                result_sets.extend(_mcp_result_to_result_sets(item))
            if result_sets:
                return result_sets

        if isinstance(result.get("rowcount"), int):
            result_sets.append(("rowcount", int(result["rowcount"]), None))
            return result_sets

        if isinstance(result.get("affected_rows"), int):
            result_sets.append(("rowcount", int(result["affected_rows"]), None))
            return result_sets

    if isinstance(result, list) and result and isinstance(result[0], dict):
        cols, rows = records_to_columns_rows(result)
        result_sets.append(("rows", cols, rows))

    return result_sets


def _compact_search_objects_result(result_sets: list[tuple[str, Any, Any]], max_items: int = 200) -> list[dict[str, Any]]:
    if not result_sets:
        return []
    for rs in result_sets:
        if rs[0] != "rows":
            continue
        cols = [str(c or "").lower() for c in rs[1]]
        rows = rs[2] or []
        if not rows:
            continue
        idx_name = cols.index("name") if "name" in cols else -1
        for fallback in ("table", "table_name", "column", "column_name"):
            if idx_name == -1 and fallback in cols:
                idx_name = cols.index(fallback)
                break
        idx_schema = -1
        for cand in ("schema", "table_schema", "database"):
            if cand in cols:
                idx_schema = cols.index(cand)
                break
        items: list[dict[str, Any]] = []
        for row in rows[:max_items]:
            if idx_name == -1:
                continue
            try:
                name = row[idx_name]
            except Exception:
                continue
            item = {"name": name}
            if idx_schema != -1:
                try:
                    item["schema"] = row[idx_schema]
                except Exception:
                    pass
            items.append(item)
        return items
    return []


def _extract_table_targets_from_search_results(
    result_sets: list[tuple[str, Any, Any]],
    max_tables: int,
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    if not result_sets:
        return targets
    table_limit = int(max_tables)
    unlimited = table_limit <= 0
    for rs in result_sets:
        if rs[0] != "rows":
            continue
        cols = [str(c or "").strip().lower() for c in (rs[1] or [])]
        rows = rs[2] or []
        if not rows:
            continue
        idx_name = -1
        for cand in ("name", "table", "table_name"):
            if cand in cols:
                idx_name = cols.index(cand)
                break
        if idx_name == -1:
            continue
        idx_schema = -1
        for cand in ("schema", "table_schema", "database", "db", "schema_name"):
            if cand in cols:
                idx_schema = cols.index(cand)
                break
        for row in rows:
            table_name = ""
            schema_name = ""
            if isinstance(row, dict):
                table_name = str(
                    row.get("name")
                    or row.get("table")
                    or row.get("table_name")
                    or ""
                ).strip()
                schema_name = str(
                    row.get("schema")
                    or row.get("table_schema")
                    or row.get("database")
                    or row.get("db")
                    or row.get("schema_name")
                    or ""
                ).strip()
            elif isinstance(row, (list, tuple)):
                try:
                    table_name = str(row[idx_name] or "").strip()
                except Exception:
                    table_name = ""
                if idx_schema != -1:
                    try:
                        schema_name = str(row[idx_schema] or "").strip()
                    except Exception:
                        schema_name = ""
            else:
                continue
            if "." in table_name and not schema_name:
                parts = table_name.split(".", 1)
                schema_name = parts[0].strip("` ")
                table_name = parts[1].strip("` ")
            table_name = table_name.strip("` ")
            schema_name = schema_name.strip("` ")
            if not table_name:
                continue
            if schema_name and (_is_system_schema(schema_name) or _should_block_default_schema(schema_name)):
                continue
            dedupe = f"{schema_name.lower()}.{table_name.lower()}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            targets.append((schema_name, table_name))
            if (not unlimited) and len(targets) >= table_limit:
                return targets
    return targets


def _augment_search_objects_with_table_meta(
    result_sets: list[tuple[str, Any, Any]],
    args: dict[str, Any],
    mcp_tools: list[str] | None,
) -> tuple[list[tuple[str, Any, Any]], float]:
    if not AGENT_SEARCH_OBJECTS_INCLUDE_TABLE_META:
        return result_sets, 0.0
    object_type = _normalize_search_object_type(args.get("object_type")) or "table"
    if object_type != "table":
        return result_sets, 0.0
    execute_tool = _find_tool_name(mcp_tools or [], MCP_EXECUTE_SQL_CANDIDATES)
    if not execute_tool:
        return result_sets, 0.0

    targets = _extract_table_targets_from_search_results(
        result_sets,
        AGENT_SEARCH_OBJECTS_META_MAX_TABLES,
    )
    if not targets:
        return result_sets, 0.0

    unified_cols = [
        "schema",
        "name",
        "object_type",
        "column_order",
        "column_name",
        "column_type",
        "is_nullable",
        "column_key",
        "extra",
        "index_name",
        "non_unique",
        "seq_in_index",
        "index_type",
        "index_collation",
    ]
    unified_rows: list[list[Any]] = []
    elapsed_ms = 0.0

    def _row_to_dict(cols: list[str], row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return {str(k): v for k, v in row.items()}
        if isinstance(row, (list, tuple)):
            mapped: dict[str, Any] = {}
            for idx, key in enumerate(cols):
                mapped[key] = row[idx] if idx < len(row) else None
            return mapped
        return {}

    # Base search_objects table rows
    for rs in result_sets:
        if rs[0] != "rows":
            continue
        cols = [str(c or "") for c in (rs[1] or [])]
        lower_cols = [c.lower() for c in cols]
        rows = rs[2] or []
        if not rows:
            continue
        for row in rows:
            mapped = _row_to_dict(cols, row)
            mapped_lc = {str(k).lower(): v for k, v in mapped.items()}
            name = str(
                mapped_lc.get("name")
                or mapped_lc.get("table")
                or mapped_lc.get("table_name")
                or ""
            ).strip()
            schema = str(
                mapped_lc.get("schema")
                or mapped_lc.get("table_schema")
                or mapped_lc.get("database")
                or mapped_lc.get("db")
                or mapped_lc.get("schema_name")
                or ""
            ).strip()
            if not name:
                if isinstance(row, (list, tuple)):
                    try:
                        idx_name = lower_cols.index("name")
                        name = str(row[idx_name] or "").strip()
                    except Exception:
                        name = ""
                    try:
                        idx_schema = lower_cols.index("schema")
                        schema = str(row[idx_schema] or "").strip()
                    except Exception:
                        pass
            if not name:
                continue
            if "." in name and not schema:
                parts = name.split(".", 1)
                schema = parts[0].strip("` ")
                name = parts[1].strip("` ")
            unified_rows.append(
                [
                    schema or None,
                    name or None,
                    "table",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ]
            )

    for schema_name, table_name in targets:
        safe_table = table_name.replace("'", "''")
        safe_schema = schema_name.replace("'", "''")
        if safe_schema:
            where = (
                f"`TABLE_SCHEMA` = '{safe_schema}' AND `TABLE_NAME` = '{safe_table}'"
            )
        else:
            where = (
                "`TABLE_SCHEMA` NOT IN ('information_schema','mysql','performance_schema','sys') "
                f"AND `TABLE_NAME` = '{safe_table}'"
            )
        columns_sql = (
            "SELECT "
            "`TABLE_SCHEMA` AS `schema_name`, "
            "`TABLE_NAME` AS `table_name`, "
            "`ORDINAL_POSITION` AS `column_order`, "
            "`COLUMN_NAME`, "
            "`COLUMN_TYPE`, "
            "`IS_NULLABLE`, "
            "`COLUMN_KEY`, "
            "`EXTRA` "
            "FROM `information_schema`.`COLUMNS` "
            f"WHERE {where} "
            "ORDER BY `TABLE_SCHEMA`, `TABLE_NAME`, `ORDINAL_POSITION`"
        )
        indexes_sql = (
            "SELECT "
            "`TABLE_SCHEMA` AS `schema_name`, "
            "`TABLE_NAME` AS `table_name`, "
            "`INDEX_NAME`, "
            "`NON_UNIQUE`, "
            "`SEQ_IN_INDEX`, "
            "`COLUMN_NAME`, "
            "`INDEX_TYPE`, "
            "`COLLATION` "
            "FROM `information_schema`.`STATISTICS` "
            f"WHERE {where} "
            "ORDER BY `TABLE_SCHEMA`, `TABLE_NAME`, `INDEX_NAME`, `SEQ_IN_INDEX`"
        )
        for sql_text in (columns_sql, indexes_sql):
            started = time.perf_counter()
            try:
                meta_result = mcp_call(execute_tool, {"sql": sql_text})
            except Exception:
                elapsed_ms += (time.perf_counter() - started) * 1000.0
                continue
            elapsed_ms += (time.perf_counter() - started) * 1000.0
            err_msg, _err_code = _mcp_error_info(meta_result)
            if err_msg:
                continue
            meta_sets = _mcp_result_to_result_sets(meta_result)
            if not meta_sets:
                continue
            for meta_rs in meta_sets:
                if meta_rs[0] != "rows":
                    continue
                meta_cols = [str(c or "") for c in (meta_rs[1] or [])]
                meta_rows = meta_rs[2] or []
                if not meta_rows:
                    continue
                for meta_row in meta_rows:
                    item = _row_to_dict(meta_cols, meta_row)
                    item_lc = {str(k).lower(): v for k, v in item.items()}
                    schema_val = str(item_lc.get("schema_name") or schema_name or "").strip() or None
                    table_val = str(item_lc.get("table_name") or table_name or "").strip() or None
                    if "column_order" in item_lc:
                        unified_rows.append(
                            [
                                schema_val,
                                table_val,
                                "column",
                                item_lc.get("column_order"),
                                item_lc.get("column_name"),
                                item_lc.get("column_type"),
                                item_lc.get("is_nullable"),
                                item_lc.get("column_key"),
                                item_lc.get("extra"),
                                None,
                                None,
                                None,
                                None,
                                None,
                            ]
                        )
                    else:
                        unified_rows.append(
                            [
                                schema_val,
                                table_val,
                                "index",
                                None,
                                item_lc.get("column_name"),
                                None,
                                None,
                                None,
                                None,
                                item_lc.get("index_name"),
                                item_lc.get("non_unique"),
                                item_lc.get("seq_in_index"),
                                item_lc.get("index_type"),
                                item_lc.get("collation"),
                            ]
                        )
    if unified_rows:
        return [("rows", unified_cols, unified_rows)], elapsed_ms
    return result_sets, elapsed_ms


def _mcp_error_info(result: Any) -> tuple[str, str]:
    if isinstance(result, dict):
        if result.get("success") is False and result.get("error"):
            return str(result.get("error")), str(result.get("code", ""))
        if isinstance(result.get("error"), str):
            return str(result.get("error")), str(result.get("code", ""))
        if isinstance(result.get("message"), str) and result.get("code"):
            return str(result.get("message")), str(result.get("code", ""))
    return "", ""


