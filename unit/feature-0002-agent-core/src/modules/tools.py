"""DBA Agent Tools — LLM이 호출하는 도구 정의 및 구현.

이 모듈은 OpenAI function calling 형식의 도구 스키마와 실행 함수를 제공한다.
모든 DB 탐색/실행은 이 도구를 통해서만 이루어진다.
"""

from __future__ import annotations

import contextvars
import json
import time
from typing import Any

from .config import AGENT_TOP_N, AGENT_MAX_SHOW
from .db import execute_sql as _raw_execute_sql
from .render import save_csv
from . import dialects as _dialects  # Stage 2 P5: engine 별 introspection/sample SQL

__all__ = [
    "TOOL_DEFINITIONS",
    "execute_tool",
    "set_active_schema_allowlist",
    "clear_active_schema_allowlist",
]

# ── 시스템 스키마 ────────────────────────────────────────────────
# 메타데이터 스키마 — Product whitelist 와 무관하게 agent tools 가 항상 접근 가능.
# DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요해 기본 허용한다. MySQL GRANT 가 2차 방어.
_METADATA_SCHEMAS = frozenset({
    "information_schema", "mysql", "performance_schema", "sys",
})
# 에이전트 내부 스키마 — whitelist 로 차단 유지. 타 계정 대화/세션/권한 데이터 보호.
_INTERNAL_SCHEMAS = frozenset({"agent_memory"})
# `_is_user_schema` / `search_tables` 의 "사용자 스키마 아님" 판정에 쓰이는 union.
_SYSTEM_SCHEMAS = _METADATA_SCHEMAS | _INTERNAL_SCHEMAS

# ── Product 단위 스키마 whitelist (None 이면 기존 동작, set 이면 교집합 필터) ──
# TASK-0128 (#2/#8 race): 이전엔 plain 모듈 전역이라 공유 threadpool 에서 동시 ask 가
# 서로의 allowlist 를 덮어쓰는 교차테넌트 레이스가 있었다. ContextVar 로 전환 — asyncio.to_thread
# 가 호출 task 의 context 를 복사해 스레드로 전파하므로 ask 별 격리된다.
_ACTIVE_SCHEMA_ALLOWLIST: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "agent_active_schema_allowlist", default=None
)


def set_active_schema_allowlist(schemas: list[str] | set[str] | None) -> None:
    """agent 실행 시작 시 Product 에 배정된 스키마 whitelist 를 설정 (ContextVar, ask 별 격리).

    None 을 넣으면 기존 동작(모든 user schema 접근 가능).
    빈 list/set 을 넣으면 **접근 가능 스키마가 없는 상태** (모든 조회/실행이 거부 — fail-closed).
    """
    if schemas is None:
        _ACTIVE_SCHEMA_ALLOWLIST.set(None)
    else:
        _ACTIVE_SCHEMA_ALLOWLIST.set({str(s).strip().lower() for s in schemas if str(s).strip()})


def clear_active_schema_allowlist() -> None:
    set_active_schema_allowlist(None)


def _is_user_schema(name: str) -> bool:
    lower = str(name or "").lower()
    if lower in _SYSTEM_SCHEMAS:
        return False
    allow = _ACTIVE_SCHEMA_ALLOWLIST.get()
    if allow is not None and lower not in allow:
        return False
    return True


_TABLE_LIST_RE = None
_INNER_REF_RE = None


def _extract_sql_schema_refs(sql: str) -> set[str]:
    """SQL 텍스트에서 `schema`.`table` 참조의 schema 토큰만 추출.

    TASK-0040: 두 단계로 동작한다.
      1. `FROM` / `JOIN` 키워드 뒤의 **table list 구간** (다음 절 키워드
         `ON` / `WHERE` / `GROUP BY` / `ORDER BY` / `HAVING` / `LIMIT` /
         `UNION` / 다시 `JOIN` · `FROM` / `;` / `)` / 문장 끝 이전) 만 잘라낸다.
      2. 그 구간 내부에서만 `schema.table` 패턴을 반복 추출한다.

    이로써 `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be
    ON be.AcntNo = bb.AcntNo WHERE bb.BattleType = ...` 같은 SQL 에서
    SELECT / WHERE / ON 절의 `alias.column` 이 schema.table 로 오탐되지
    않고, `FROM a.x, b.y` 형식의 comma join 은 그대로 수용된다.
    """
    import re as _re
    global _TABLE_LIST_RE, _INNER_REF_RE
    if _TABLE_LIST_RE is None:
        _TABLE_LIST_RE = _re.compile(
            r"\b(?:FROM|JOIN)\b(.*?)"
            r"(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b"
            r"|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)",
            _re.IGNORECASE | _re.DOTALL,
        )
        _INNER_REF_RE = _re.compile(
            r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
        )
    refs: set[str] = set()
    for m in _TABLE_LIST_RE.finditer(sql or ""):
        chunk = m.group(1) or ""
        for mm in _INNER_REF_RE.finditer(chunk):
            refs.add(mm.group(1).lower())
    return refs


def _whitelist_violation(refs: set[str]) -> str | None:
    """참조된 스키마 중 접근이 허용되지 않은 것이 있으면 에러 메시지 반환.

    메타데이터 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 는
    Product whitelist 와 무관하게 항상 통과한다. 에이전트가 DB 구조를 탐색할 때
    카탈로그·뷰·런타임 통계 조회가 필요하기 때문이다. `mysql` 의 민감 테이블은
    DB 커넥터가 쓰는 MySQL 계정의 GRANT 로 2 차 방어된다.

    `agent_memory` 는 whitelist 로 차단 유지 — 타 계정 대화/세션/권한 override 를
    LLM 이 직접 조회하는 경로를 막는다.
    """
    allow = _ACTIVE_SCHEMA_ALLOWLIST.get()
    if allow is None:
        return None
    allowed = set(allow) | _METADATA_SCHEMAS
    blocked = [r for r in refs if r and r not in allowed]
    if not blocked:
        return None
    allowed_str = ", ".join(sorted(allow)) or "(none)"
    return (
        f"오류: 접근이 허용되지 않은 스키마 참조: {', '.join(sorted(blocked))}. "
        f"현재 Product 에 허용된 스키마: {allowed_str}. "
        f"메타데이터 스키마(information_schema/sys/mysql/performance_schema) 는 항상 접근 가능."
    )


# ══════════════════════════════════════════════════════════════════
#  OpenAI function calling 도구 스키마
# ══════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # execute_sql을 맨 앞에 배치 — LLM이 첫 번째 도구를 선호하는 경향을 활용.
    # 질문에 바로 답할 수 있는 SQL을 먼저 시도하도록 유도한다.
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "SELECT SQL을 실행하여 데이터를 조회한다. "
                "반드시 `schema`.`table` 형식을 사용한다. "
                "이 도구를 가장 먼저 사용하라 — 시스템 프롬프트의 KNOWN SCHEMAS 정보로 SQL을 즉시 작성할 수 있다. "
                "무거운 쿼리는 DB 부하 경고(EXPLAIN 게이트)에 걸릴 수 있다 — 그 경우 WHERE/기간/집계 "
                "범위를 좁히거나 LIMIT 을 추가하라. 전체 스캔이 정말 필요하면 confirm_heavy=true 로 다시 호출한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "실행할 SELECT SQL",
                    },
                    "confirm_heavy": {
                        "type": "boolean",
                        "description": (
                            "true 면 무거운 쿼리 EXPLAIN 게이트를 우회해 그대로 실행한다. "
                            "범위를 좁힐 수 없고 전체 스캔이 반드시 필요할 때만 사용."
                        ),
                    },
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": (
                "테이블의 컬럼명, 타입, 키, 인덱스를 반환한다. "
                "execute_sql이 컬럼 오류로 실패했을 때만 사용한다. "
                "동일 테이블에 대해 1회만 호출한다."
            ),
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
            "name": "search_tables",
            "description": (
                "키워드로 테이블을 검색한다 (최후 수단). "
                "시스템 프롬프트의 KNOWN SCHEMAS에 관련 테이블이 이미 있으면 이 도구를 사용하지 않는다. "
                "같은 키워드로 2회 이상 호출하지 않는다."
            ),
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
            "name": "get_sample_rows",
            "description": (
                "테이블의 샘플 데이터를 조회한다. "
                "컬럼 내용 형식(예: JSON 구조)을 확인해야 할 때만 사용한다. "
                "대부분의 경우 불필요하다."
            ),
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


# ── 단계 narration 파라미터 (TASK-0178) ──────────────────────────────
# 실행 단계의 work(무엇을)/reason(왜)을 LLM 이 채우게 하는 표준 경로.
# content 동시 방출(TASK-0177)은 Bedrock gateway 가 tool_use 턴의 text content 를
# strip 해 무력했다(REV-20260610-0177 M2 라이브 확정). tool 호출 인자(arguments)는
# SQL 처럼 안정적으로 전달되므로, 모든 도구 스키마에 optional `reason`/`work` 를
# 주입해 모델이 호출 시 채우게 한다. agent_core 루프가 tool_args 에서 pop 해 step 에
# 기록하고, 실제 도구 실행에는 전달하지 않는다(핸들러는 named-get 이라 무해하지만 명시 pop).
# 미제공 시 _derive_step_reason/_derive_step_work fallback(TASK-0175)이 받는다.
_STEP_NARRATION_PARAMS: dict[str, dict[str, str]] = {
    "reason": {
        "type": "string",
        "description": (
            "이 도구를 호출하는 이유를 사용자의 질문·목표에 비추어 구체적으로 (한국어, 1~2문장). "
            "일반적 도구 설명이 아니라 '이번 질문에 왜 이 단계가 필요한지'. "
            "예: '월별 매출을 집계하려면 주문일자·금액 컬럼명을 먼저 확정해야 하므로'. "
            "모든 도구 호출에 채운다."
        ),
    },
    "work": {
        "type": "string",
        "description": "이 단계가 하는 일을 한 줄로 (한국어). 예: '`db`.`orders` 의 컬럼 구조를 확인'.",
    },
}


def _inject_step_narration_params(tool_defs: list[dict[str, Any]]) -> None:
    """모든 tool 정의의 parameters.properties 앞쪽에 reason/work 를 주입(think-first).
    TOOL_DEFINITIONS_FULL 은 TOOL_DEFINITIONS 의 dict 객체를 공유하므로 FULL 만
    순회해도 전체 8개 고유 도구가 1회씩 갱신된다. required 에는 추가하지 않는다(optional)."""
    for t in tool_defs:
        params = (t.get("function") or {}).get("parameters")
        if not isinstance(params, dict):
            continue
        props = params.get("properties")
        if not isinstance(props, dict):
            continue
        merged: dict[str, Any] = {}
        for key, schema in _STEP_NARRATION_PARAMS.items():
            if key not in props:
                merged[key] = dict(schema)
        merged.update(props)
        params["properties"] = merged


_inject_step_narration_params(TOOL_DEFINITIONS_FULL)


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
    sql = _dialects.active().list_schemas_with_counts()
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
    err = _whitelist_violation({schema.lower()})
    if err:
        return err
    sql = _dialects.active().describe_schema_tables(schema)
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
    err = _whitelist_violation({schema.lower()})
    if err:
        return err

    # 컬럼 정보
    col_sql = _dialects.active().describe_columns(schema, table)
    col_results, _ = _raw_execute_sql(conn, col_sql)

    # 인덱스 정보
    idx_sql = _dialects.active().list_indexes(schema, table)
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
            sample_sql = _dialects.active().sample(schema, table, 1)
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
    if schema_filter:
        err = _whitelist_violation({schema_filter.lower()})
        if err:
            return err

    where_schema = f"AND t.TABLE_SCHEMA = '{schema_filter}'" if schema_filter else ""
    # 시스템 스키마 제외 조건
    sys_exclude = " AND ".join(f"t.TABLE_SCHEMA != '{s}'" for s in _SYSTEM_SCHEMAS)

    sql = _dialects.active().search_tables(keyword, sys_exclude, where_schema)
    result_sets, _ = _raw_execute_sql(conn, sql)

    # 사용 가능한 전체 스키마 목록 조회
    all_schemas: list[str] = []
    try:
        schema_sql = _dialects.active().list_schema_names()
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
    err = _whitelist_violation({schema.lower()})
    if err:
        return err
    sql = _dialects.active().sample(schema, table, limit)
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


def _estimate_explain_rows(conn, sql: str) -> int | None:
    """EXPLAIN 으로 예상 스캔 rows 추정 — 테이블별 (rows × filtered/100) 곱 = join 후
    예상 카디널리티. `filtered`(옵티마이저 선택률 %)를 반영해 잘 인덱싱된 조인의 과대추정
    (false-positive 게이팅)을 줄인다(diff review m3).

    TASK-0172: 무거운 쿼리 사전 게이팅용. EXPLAIN 은 본 쿼리를 실행하지 않으므로 cheap
    (EXPLAIN ANALYZE 는 sql_guard 가 차단). 실패(구문/권한/플랜불가) 시 None → caller 가
    fail-open(게이트가 정상 작업을 막지 않음)."""
    # Stage 2 P5: dialect 별 EXPLAIN. MSSQL 은 explain()=None → 추정 skip(None).
    # MSSQL 부하게이트 fail-closed/SHOWPLAN 은 P6. (현재 MySQL 만 EXPLAIN rows/filtered 파싱.)
    explain_sql = _dialects.active().explain(sql)
    if not explain_sql:
        return None
    try:
        result_sets, _ = _raw_execute_sql(conn, explain_sql)
    except Exception:
        return None
    for kind, columns, rows in result_sets:
        if kind != "rows" or not isinstance(columns, list) or not isinstance(rows, list):
            continue
        lcols = [str(c).lower() for c in columns]
        try:
            ridx = lcols.index("rows")
        except ValueError:
            continue
        fidx = lcols.index("filtered") if "filtered" in lcols else None
        product = 1
        seen = False
        for r in rows:
            try:
                v = int(r[ridx])
            except (ValueError, TypeError, IndexError):
                continue
            eff = float(v)
            if fidx is not None:
                try:
                    filt = float(r[fidx])
                    if 0.0 <= filt <= 100.0:
                        eff = v * (filt / 100.0)
                except (ValueError, TypeError, IndexError):
                    pass
            product *= max(1, int(round(eff)))
            seen = True
        if seen:
            return product
    return None


def _apply_query_cap(conn) -> None:
    """시간 상한(MAX_EXECUTION_TIME, ms)을 **세션 스코프**로 적용(SELECT 한정 효력).
    conn 은 run 전체 공유라 한 번 SET 하면 그 conn 의 이후 SELECT(스키마 탐색 도구 포함)
    에도 sticky 하게 적용된다 — generous 기본이라 빠른 도구엔 무해, 폭주만 차단. 매 호출
    재-SET 은 idempotent. 0/비활성이면 no-op, 실패 시 fail-open. "무거운 쿼리는 감수"
    정책상 기본 generous/off."""
    import modules.config as _cfg
    ms = int(getattr(_cfg, "AGENT_QUERY_MAX_EXECUTION_MS", 0) or 0)
    if ms <= 0:
        return
    try:
        cur = conn.cursor()
        try:
            cur.execute(f"SET SESSION max_execution_time = {int(ms)}")
        finally:
            cur.close()
    except Exception:
        pass


def _tool_execute_sql(conn, args: dict) -> str:
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return "오류: sql은 필수입니다."
    # TASK-0128 (#2): LLM 작성 SQL 신뢰경계 — 이전엔 uppercase prefix denylist 뿐이라
    # `/* */ DELETE`, 탭 우회, `SELECT 1; DELETE ...` 다중문, INSERT/UPDATE 가 모두 통과했다.
    # sqlglot AST 가드로 교체: 단일 SELECT/CTE only, 다중문·write verb·lock·INTO·금지함수·
    # 금지스키마(agent_memory 등) reject. (스키마 탐색은 별도 구조화 도구가 담당 — 본 도구는
    # LLM freeform 분석 SELECT 전용.)
    from .sql_guard import validate_sql_for_sandbox
    # agent 는 카탈로그(information_schema/sys 등) 조회가 필요하므로 내부 스키마(agent_memory)만 금지.
    guard = validate_sql_for_sandbox(sql, forbidden_schemas=_INTERNAL_SCHEMAS)
    if not guard.ok:
        return (
            f"오류: 보안 정책상 차단된 SQL — {guard.error_reason}. "
            f"execute_sql 은 단일 SELECT/CTE 분석 쿼리만 허용됩니다 "
            f"(스키마 구조 탐색은 list_schemas/describe_table 등 전용 도구 사용)."
        )
    # Product 단위 스키마 allowlist (교차 product 격리) — 기존 regex 추출 유지.
    err = _whitelist_violation(_extract_sql_schema_refs(sql))
    if err:
        return err
    # TASK-0172: 무거운 쿼리 자가규제 — 실행 전 EXPLAIN 으로 예상 스캔 rows 추정해
    # 임계 초과 시 gate(좁히기 유도) 또는 warn(비용 경고 prepend). confirm_heavy=true 면
    # 추정 무관 실행("무거운 쿼리는 감수" — LLM 이 필요 판단 시 override). guard off=현행.
    import modules.config as _cfg
    guard_mode = str(getattr(_cfg, "AGENT_QUERY_GUARD_MODE", "off") or "off").lower()
    # diff review M1: bool(args.get(...)) 은 LLM 이 문자열 "false" 를 보내면 truthy → 게이트
    # 우회. true/1/yes(대소문자) 또는 bool True 만 confirm 으로 인정.
    _cv = args.get("confirm_heavy")
    confirm_heavy = (_cv is True) or (
        isinstance(_cv, str) and _cv.strip().lower() in ("true", "1", "yes")
    )
    cost_note: str | None = None
    if guard_mode in ("warn", "gate") and not confirm_heavy:
        est = _estimate_explain_rows(conn, sql)
        warn_thr = int(getattr(_cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1000000) or 1000000)
        if est is not None and est > warn_thr:
            if guard_mode == "gate":
                return (
                    f"⚠ 무거운 쿼리로 추정됩니다 (EXPLAIN 예상 스캔 ~{est:,}행 > 임계 {warn_thr:,}행). "
                    f"DB 부하를 줄이도록 WHERE 조건·기간·집계 범위를 좁히거나 LIMIT 을 추가해 다시 시도하세요. "
                    f"전체 스캔이 정말 필요하면 같은 쿼리를 confirm_heavy=true 로 다시 호출하면 실행합니다."
                )
            cost_note = (
                f"⚠ 무거운 쿼리 (EXPLAIN 예상 스캔 ~{est:,}행). 가능하면 다음엔 범위를 좁히세요."
            )
    # per-query 시간 cap(폭주 backstop) 적용 — generous/off 기본.
    _apply_query_cap(conn)
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
        if cost_note:
            parts.insert(0, cost_note)
        return "\n\n".join(parts)
    except Exception as e:
        return f"SQL 실행 오류: {e}"


def _tool_explain_query(conn, args: dict) -> str:
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return "오류: sql은 필수입니다."
    err = _whitelist_violation(_extract_sql_schema_refs(sql))
    if err:
        return err
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
    err = _whitelist_violation({schema.lower()})
    if err:
        return err
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
    err = _whitelist_violation({schema.lower()})
    if err:
        return err

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
