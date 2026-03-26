"""DBA Agent Tools — LLM이 호출하는 도구 정의 및 구현.

이 모듈은 OpenAI function calling 형식의 도구 스키마와 실행 함수를 제공한다.
모든 DB 탐색/실행은 이 도구를 통해서만 이루어진다.
"""

from __future__ import annotations

import json
import time
from typing import Any

from .config import AGENT_TOP_N, AGENT_MAX_SHOW
from .db import execute_sql as _raw_execute_sql
from .render import save_csv

__all__ = [
    "TOOL_DEFINITIONS",
    "execute_tool",
]

# ── 시스템 스키마 (탐색 대상에서 제외) ──────────────────────────
_SYSTEM_SCHEMAS = frozenset({
    "information_schema", "mysql", "performance_schema", "sys",
    "agent_memory",
})


def _is_user_schema(name: str) -> bool:
    return name.lower() not in _SYSTEM_SCHEMAS


# ══════════════════════════════════════════════════════════════════
#  OpenAI function calling 도구 스키마
# ══════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_tables",
            "description": "키워드로 테이블을 검색한다. 테이블명/컬럼명에서 키워드를 찾는다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "검색 키워드",
                    },
                    "schema_name": {
                        "type": "string",
                        "description": "스키마 이름 (선택)",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "테이블의 컬럼명, 타입, 키, 인덱스를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sample_rows",
            "description": "테이블의 샘플 데이터를 조회한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                    "limit": {"type": "integer", "description": "행 수 (기본 5)"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "SELECT SQL을 실행한다. 반드시 `schema`.`table` 형식을 사용한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "실행할 SELECT SQL",
                    },
                },
                "required": ["sql"],
            },
        },
    },
]

# 전체 도구 정의 (list_schemas, describe_schema, explain_query 등 추가 도구 포함)
# 작은 모델에서는 TOOL_DEFINITIONS (핵심 4개)만 사용하고,
# 큰 모델에서는 TOOL_DEFINITIONS_FULL을 사용할 수 있다.
TOOL_DEFINITIONS_FULL: list[dict[str, Any]] = TOOL_DEFINITIONS + [
    {
        "type": "function",
        "function": {
            "name": "list_schemas",
            "description": "MySQL 사용자 스키마 목록을 반환한다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_schema",
            "description": "스키마의 모든 테이블 목록과 행 수를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                },
                "required": ["schema_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_query",
            "description": "SQL 실행 계획(EXPLAIN)을 분석한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT SQL"},
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_table_indexes",
            "description": "테이블 인덱스 정보를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_foreign_keys",
            "description": "테이블 외래키 관계를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema_name": {"type": "string", "description": "스키마 이름"},
                    "table_name": {"type": "string", "description": "테이블 이름"},
                },
                "required": ["schema_name", "table_name"],
            },
        },
    },
]


# ══════════════════════════════════════════════════════════════════
#  도구 실행 함수
# ══════════════════════════════════════════════════════════════════

def _format_result_sets(result_sets: list, max_rows: int | None = None) -> str:
    """execute_sql 결과를 텍스트로 변환."""
    if max_rows is None:
        max_rows = AGENT_TOP_N
    parts: list[str] = []
    total_rows = 0
    for kind, col_or_count, rows in result_sets:
        if kind == "rows" and isinstance(rows, list):
            columns = col_or_count if isinstance(col_or_count, list) else []
            total_rows += len(rows)
            if columns:
                parts.append("| " + " | ".join(str(c) for c in columns) + " |")
                parts.append("|" + "|".join("---" for _ in columns) + "|")
            displayed = rows[:max_rows]
            for row in displayed:
                cells = []
                for v in row:
                    s = str(v) if v is not None else "NULL"
                    if len(s) > 100:
                        s = s[:100] + "..."
                    cells.append(s)
                parts.append("| " + " | ".join(cells) + " |")
            if len(rows) > max_rows:
                parts.append(f"\n... ({len(rows)} 행 중 {max_rows}행만 표시)")
            else:
                parts.append(f"\n({len(rows)} 행)")
        elif kind == "rowcount":
            parts.append(f"영향받은 행: {col_or_count}")
    return "\n".join(parts)


def _safe_ident(name: str) -> str:
    """SQL 식별자에서 위험 문자 제거."""
    return name.replace("`", "").replace(";", "").replace("'", "").replace('"', "").strip()


def _tool_list_schemas(conn, _args: dict) -> str:
    sql = """
        SELECT
            s.SCHEMA_NAME,
            COUNT(t.TABLE_NAME) AS table_count,
            COALESCE(SUM(t.TABLE_ROWS), 0) AS approx_total_rows
        FROM information_schema.SCHEMATA s
        LEFT JOIN information_schema.TABLES t
            ON s.SCHEMA_NAME = t.TABLE_SCHEMA
        GROUP BY s.SCHEMA_NAME
        ORDER BY s.SCHEMA_NAME
    """
    result_sets, _ = _raw_execute_sql(conn, sql)
    # 시스템 스키마 필터링
    filtered: list[str] = []
    for kind, cols, rows in result_sets:
        if kind == "rows" and rows:
            filtered.append("| schema | tables | approx_rows |")
            filtered.append("|---|---|---|")
            for row in rows:
                schema_name = str(row[0])
                if not _is_user_schema(schema_name):
                    continue
                filtered.append(f"| {schema_name} | {row[1]} | {row[2]} |")
    return "\n".join(filtered) if filtered else "(사용자 스키마가 없습니다)"


def _tool_describe_schema(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    if not schema:
        return "오류: schema_name은 필수입니다."
    sql = f"""
        SELECT
            TABLE_NAME,
            TABLE_ROWS AS approx_rows,
            ENGINE,
            TABLE_COMMENT,
            CREATE_TIME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = '{schema}'
        ORDER BY TABLE_NAME
    """
    result_sets, _ = _raw_execute_sql(conn, sql)
    parts = [f"## 스키마: {schema}\n"]
    for kind, cols, rows in result_sets:
        if kind == "rows" and rows:
            parts.append("| table | approx_rows | engine | comment |")
            parts.append("|---|---|---|---|")
            for row in rows:
                comment = str(row[3] or "")[:40]
                parts.append(f"| {row[0]} | {row[1]} | {row[2]} | {comment} |")
            parts.append(f"\n총 {len(rows)} 테이블")
        elif kind == "rows":
            parts.append(f"스키마 '{schema}'에 테이블이 없거나 스키마가 존재하지 않습니다.")
    return "\n".join(parts)


def _tool_describe_table(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."

    # 컬럼 정보
    col_sql = f"""
        SELECT
            COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY,
            COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
        ORDER BY ORDINAL_POSITION
    """
    col_results, _ = _raw_execute_sql(conn, col_sql)

    # 인덱스 정보
    idx_sql = f"SHOW INDEX FROM `{schema}`.`{table}`"
    try:
        idx_results, _ = _raw_execute_sql(conn, idx_sql)
    except Exception:
        idx_results = []

    parts = [f"## `{schema}`.`{table}` 구조\n"]
    parts.append("### 컬럼")
    parts.append("| column | type | nullable | key | default | extra | comment |")
    parts.append("|---|---|---|---|---|---|---|")
    for kind, cols, rows in col_results:
        if kind == "rows" and rows:
            for row in rows:
                default_val = str(row[4]) if row[4] is not None else ""
                comment = str(row[6] or "")[:30]
                parts.append(
                    f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | "
                    f"{default_val} | {row[5]} | {comment} |"
                )

    if idx_results:
        parts.append("\n### 인덱스")
        parts.append("| index_name | non_unique | column | seq | cardinality |")
        parts.append("|---|---|---|---|---|")
        for kind, cols, rows in idx_results:
            if kind == "rows" and rows:
                for row in rows:
                    parts.append(
                        f"| {row[2]} | {row[1]} | {row[4]} | {row[3]} | {row[6]} |"
                    )

    # TEXT/JSON 컬럼이 있으면 자동으로 1행 샘플 추가 (JSON 구조 파악용)
    has_complex = False
    for kind, cols, rows in col_results:
        if kind == "rows" and rows:
            for row in rows:
                col_type = str(row[1]).lower()
                if any(t in col_type for t in ("text", "json", "blob", "longtext", "mediumtext")):
                    has_complex = True
                    break
    if has_complex:
        try:
            sample_sql = f"SELECT * FROM `{schema}`.`{table}` LIMIT 1"
            sample_results, _ = _raw_execute_sql(conn, sample_sql)
            sample_text = _format_result_sets(sample_results, max_rows=1)
            if sample_text:
                parts.append("\n### 샘플 데이터 (1행)")
                parts.append(sample_text)
        except Exception:
            pass

    return "\n".join(parts)


def _tool_search_tables(conn, args: dict) -> str:
    keyword = _safe_ident(args.get("keyword", ""))
    schema_filter = _safe_ident(args.get("schema_name", ""))
    if not keyword:
        return "오류: keyword는 필수입니다."

    where_schema = f"AND t.TABLE_SCHEMA = '{schema_filter}'" if schema_filter else ""
    # 시스템 스키마 제외 조건
    sys_exclude = " AND ".join(f"t.TABLE_SCHEMA != '{s}'" for s in _SYSTEM_SCHEMAS)

    sql = f"""
        SELECT DISTINCT
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.TABLE_ROWS AS approx_rows,
            t.TABLE_COMMENT
        FROM information_schema.TABLES t
        LEFT JOIN information_schema.COLUMNS c
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        WHERE ({sys_exclude})
            {where_schema}
            AND (
                t.TABLE_NAME LIKE '%{keyword}%'
                OR c.COLUMN_NAME LIKE '%{keyword}%'
                OR t.TABLE_COMMENT LIKE '%{keyword}%'
            )
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        LIMIT 50
    """
    result_sets, _ = _raw_execute_sql(conn, sql)

    # 사용 가능한 전체 스키마 목록 조회
    all_schemas: list[str] = []
    try:
        schema_sql = "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME"
        schema_rs, _ = _raw_execute_sql(conn, schema_sql)
        for kind, _, rows in schema_rs:
            if kind == "rows" and rows:
                all_schemas = [str(r[0]) for r in rows if _is_user_schema(str(r[0]))]
    except Exception:
        pass

    parts = [f"## '{keyword}' 검색 결과\n"]
    found_schemas: set[str] = set()
    for kind, cols, rows in result_sets:
        if kind == "rows" and rows:
            parts.append("| schema | table | approx_rows | comment |")
            parts.append("|---|---|---|---|")
            for row in rows:
                comment = str(row[3] or "")[:40]
                parts.append(f"| {row[0]} | {row[1]} | {row[2]} | {comment} |")
                found_schemas.add(str(row[0]))
            parts.append(f"\n{len(rows)} 테이블 검색됨")
        elif kind == "rows":
            parts.append("검색 결과가 없습니다.")

    # 검색되지 않은 스키마 안내
    if all_schemas and not schema_filter:
        missed = sorted(set(all_schemas) - found_schemas)
        if missed:
            parts.append(f"\n(참고: {', '.join(missed)} 스키마에는 '{keyword}' 매칭 테이블 없음)")
    return "\n".join(parts)


def _tool_get_sample_rows(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    limit = min(max(1, int(args.get("limit", 5))), 20)
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."
    sql = f"SELECT * FROM `{schema}`.`{table}` LIMIT {limit}"
    try:
        result_sets, elapsed = _raw_execute_sql(conn, sql)
        formatted = _format_result_sets(result_sets, max_rows=limit)
        # 바이너리 컬럼 감지 → 파싱 힌트 추가
        if "b'" in formatted or "b\"" in formatted or "\\x" in formatted:
            formatted += (
                "\n\n(NOTE: Binary columns detected. To parse binary flags, use: "
                "((ORD(SUBSTRING(binary_col, FLOOR(bit_index/8)+1, 1)) >> (bit_index % 8)) & 1) "
                "where bit_index is the item's order/position.)"
            )
        return formatted
    except Exception as e:
        return f"오류: {e}"


_TOOL_PREVIEW_ROWS = 50


def _tool_execute_sql(conn, args: dict) -> str:
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return "오류: sql은 필수입니다."
    # 위험한 SQL 차단
    upper = sql.upper().lstrip()
    blocked = ("DROP ", "TRUNCATE ", "DELETE ", "ALTER ", "GRANT ", "REVOKE ", "CREATE USER", "SET PASSWORD")
    for prefix in blocked:
        if upper.startswith(prefix):
            return f"오류: {prefix.strip()} 구문은 보안상 차단됩니다."
    try:
        result_sets, elapsed = _raw_execute_sql(conn, sql)
        csv_paths: list[str] = []
        total_row_count = 0
        for idx, (kind, columns, rows) in enumerate(result_sets, start=1):
            if kind != "rows" or not isinstance(columns, list):
                continue
            total_row_count += len(rows) if isinstance(rows, list) else 0
            csv_rows = []
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, (list, tuple)):
                        csv_rows.append(list(row))
                    else:
                        csv_rows.append([row])
            csv_paths.append(save_csv(f"resultset{idx}", [str(col) for col in columns], csv_rows))
        # LLM에게 미리보기(최대 5행)만 전달, 전체 결과는 CSV 참조
        preview = _format_result_sets(result_sets, max_rows=_TOOL_PREVIEW_ROWS)
        parts: list[str] = [preview] if preview else []
        if csv_paths:
            for path in csv_paths:
                parts.append(f"CSV 저장: {path}")
            if total_row_count > _TOOL_PREVIEW_ROWS:
                parts.append(
                    f"(전체 {total_row_count}행 — 위 표는 미리보기 {_TOOL_PREVIEW_ROWS}행입니다. "
                    f"답변에 전체 표를 삽입하지 말고, CSV 다운로드 링크를 제공하세요.)"
                )
        parts.append(f"(실행 시간: {elapsed:.2f}초)")
        return "\n\n".join(parts)
    except Exception as e:
        return f"SQL 실행 오류: {e}"


def _tool_explain_query(conn, args: dict) -> str:
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return "오류: sql은 필수입니다."
    explain_sql = f"EXPLAIN {sql}"
    try:
        result_sets, _ = _raw_execute_sql(conn, explain_sql)
        return _format_result_sets(result_sets)
    except Exception as e:
        return f"EXPLAIN 오류: {e}"


def _tool_get_table_indexes(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."
    sql = f"""
        SELECT
            INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX,
            CARDINALITY, INDEX_TYPE, NULLABLE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
        ORDER BY INDEX_NAME, SEQ_IN_INDEX
    """
    try:
        result_sets, _ = _raw_execute_sql(conn, sql)
        return _format_result_sets(result_sets)
    except Exception as e:
        return f"인덱스 조회 오류: {e}"


def _tool_get_foreign_keys(conn, args: dict) -> str:
    schema = _safe_ident(args.get("schema_name", ""))
    table = _safe_ident(args.get("table_name", ""))
    if not schema or not table:
        return "오류: schema_name과 table_name은 필수입니다."

    # 이 테이블이 참조하는 외래키
    outgoing_sql = f"""
        SELECT
            CONSTRAINT_NAME, COLUMN_NAME,
            REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '{schema}'
            AND TABLE_NAME = '{table}'
            AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
    """
    # 이 테이블을 참조하는 외래키
    incoming_sql = f"""
        SELECT
            CONSTRAINT_NAME, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME,
            REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_SCHEMA = '{schema}'
            AND REFERENCED_TABLE_NAME = '{table}'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """
    parts = [f"## `{schema}`.`{table}` 외래키\n"]

    try:
        out_results, _ = _raw_execute_sql(conn, outgoing_sql)
        parts.append("### 참조하는 테이블 (outgoing)")
        parts.append(_format_result_sets(out_results))
    except Exception as e:
        parts.append(f"outgoing 외래키 조회 오류: {e}")

    try:
        in_results, _ = _raw_execute_sql(conn, incoming_sql)
        parts.append("\n### 참조되는 테이블 (incoming)")
        parts.append(_format_result_sets(in_results))
    except Exception as e:
        parts.append(f"incoming 외래키 조회 오류: {e}")

    return "\n".join(parts)


# ── 도구 디스패처 ────────────────────────────────────────────────

_TOOL_HANDLERS = {
    "list_schemas": _tool_list_schemas,
    "describe_schema": _tool_describe_schema,
    "describe_table": _tool_describe_table,
    "search_tables": _tool_search_tables,
    "get_sample_rows": _tool_get_sample_rows,
    "execute_sql": _tool_execute_sql,
    "explain_query": _tool_explain_query,
    "get_table_indexes": _tool_get_table_indexes,
    "get_foreign_keys": _tool_get_foreign_keys,
}


def execute_tool(conn, tool_name: str, arguments: dict[str, Any]) -> str:
    """도구를 실행하고 결과 문자열을 반환한다."""
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return f"알 수 없는 도구: {tool_name}"
    try:
        return handler(conn, arguments)
    except Exception as e:
        return f"도구 실행 오류 ({tool_name}): {e}"
