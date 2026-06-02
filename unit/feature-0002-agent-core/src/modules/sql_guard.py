"""Sandbox SQL allowlist guard (D14 + R-F3 Critical, Sprint 1 Ship 조건).

TASK-0094 Sprint 1 Phase 12. BRIEFING REV-20260521-0002 의 R-F3 (Codex 2차 Critical
finding) 흡수 — sqlglot 의 AST shape allowlist 방식. denylist 보조.

본 module 의 책임:
1. **SQL 파싱** — sqlglot 의 MySQL dialect.
2. **AST shape allowlist** — single SELECT/CTE only.
3. **금지 케이스** (R-F3 명시):
   - FOR UPDATE / LOCK IN SHARE MODE / share lock variants
   - EXPLAIN ANALYZE (run-with-side-effects)
   - optimizer side-effect hint (`/*+ ... */`)
   - SELECT SLEEP() / SELECT BENCHMARK()
   - user variable read·write (`@x`, `SET @x`)
   - INTO OUTFILE / INTO DUMPFILE
   - LOAD_FILE() / LOAD_EXTENSION
   - information_schema / mysql / performance_schema / sys 접근
   - multi-statement (`;` 로 두 statement)
   - SHOW / DESCRIBE / EXPLAIN (writable variants)
   - DDL/DML (CREATE/ALTER/INSERT/UPDATE/DELETE/DROP/TRUNCATE/REPLACE/MERGE/CALL)
4. **결과** — (ok: bool, error_reason: str, ast_summary: dict) — caller 가 audit
   `attachment.sandbox.sql_denied` dispatch.

D15 정합: 본 guard 를 통과한 SQL 도 `attachment_reader` MySQL user 권한이라
sandbox schema + 정본 SELECT only 만 가능. defense in depth.
"""

from __future__ import annotations

import re
from typing import Any

try:
    import sqlglot  # type: ignore[import-not-found]
    from sqlglot import exp as _exp  # type: ignore[import-not-found]
    SQLGLOT_AVAILABLE = True
except Exception:
    sqlglot = None  # type: ignore[assignment]
    _exp = None  # type: ignore[assignment]
    SQLGLOT_AVAILABLE = False


# 금지된 schema name (information_schema 등) — case-insensitive.
_FORBIDDEN_SCHEMAS = {
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
}

# 금지 function names (case-insensitive).
_FORBIDDEN_FUNCTIONS = {
    "sleep",
    "benchmark",
    "load_file",
    "load_extension",
    "get_lock",
    "release_lock",
    "uuid",  # information leak (uuid host id) — Sprint 1 conservative
}

# 보조 denylist regex (allowlist 가 못 잡는 edge — backup defense).
_DENYLIST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bINTO\s+OUTFILE\b", re.IGNORECASE),
    re.compile(r"\bINTO\s+DUMPFILE\b", re.IGNORECASE),
    re.compile(r"\bFOR\s+UPDATE\b", re.IGNORECASE),
    re.compile(r"\bLOCK\s+IN\s+SHARE\s+MODE\b", re.IGNORECASE),
    re.compile(r"\bEXPLAIN\s+ANALYZE\b", re.IGNORECASE),
    re.compile(r"\bLOAD\s+DATA\b", re.IGNORECASE),
    # TASK-0128 (#2): DoS/정보유출 함수 — AST Func 검출이 Anonymous 를 놓치는 경우 대비 regex 보강.
    re.compile(r"\bSLEEP\s*\(", re.IGNORECASE),
    re.compile(r"\bBENCHMARK\s*\(", re.IGNORECASE),
    re.compile(r"\bLOAD_FILE\s*\(", re.IGNORECASE),
    re.compile(r"\bGET_LOCK\s*\(", re.IGNORECASE),
    re.compile(r"/\*\+\s*[^*]*\*/"),  # optimizer hints
    re.compile(r"@@", re.IGNORECASE),  # system variables
    re.compile(r"\bSET\s+@", re.IGNORECASE),  # user variable write
    re.compile(r":=\s*"),  # user variable assignment
    re.compile(r"--[ \t]*[^\n]*", re.MULTILINE),  # line comment (audit only — not block by default)
)


class SqlGuardResult:
    __slots__ = ("ok", "error_reason", "ast_summary", "denied_patterns")

    def __init__(self, ok: bool, error_reason: str = "", ast_summary: dict | None = None, denied_patterns: list[str] | None = None) -> None:
        self.ok = ok
        self.error_reason = error_reason
        self.ast_summary = ast_summary or {}
        self.denied_patterns = denied_patterns or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_reason": self.error_reason,
            "ast_summary": self.ast_summary,
            "denied_patterns": self.denied_patterns,
        }


def _check_secondary_denylist(sql: str) -> list[str]:
    """보조 denylist regex — backup defense (allowlist 미흡 케이스 잡기)."""
    matched: list[str] = []
    for pat in _DENYLIST_PATTERNS:
        if pat.search(sql):
            matched.append(pat.pattern)
    return matched


def _check_multi_statement(sql: str) -> bool:
    """multi-statement 검사 — semicolon 으로 두 statement 가능. comment / string 안 ; 는 제외."""
    # 단순 검사 — sqlglot.parse 가 list 반환이므로 정밀 검사는 caller 가 len 비교.
    # 본 함수는 휴리스틱.
    stripped = re.sub(r"--[^\n]*", "", sql)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    # 문자열 리터럴 제거 (' 와 " 만).
    stripped = re.sub(r"'(?:[^'\\]|\\.)*'", "''", stripped)
    stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', stripped)
    # trailing semicolon 1 개 까지는 허용.
    stripped = stripped.rstrip().rstrip(";")
    return ";" in stripped


def _collect_table_refs(node) -> list[tuple[str, str]]:
    """AST 의 모든 Table 노드의 (db, name) 반환."""
    if _exp is None:
        return []
    out: list[tuple[str, str]] = []
    for table in node.find_all(_exp.Table):
        db = str(table.args.get("db") or "").strip().lower()
        name = str(table.args.get("this") or "").strip().lower()
        if name:
            out.append((db, name))
    return out


def _collect_function_names(node) -> list[str]:
    """AST 의 모든 Func / Anonymous 의 이름 (소문자)."""
    if _exp is None:
        return []
    out: list[str] = []
    for fn in node.find_all(_exp.Func):
        try:
            name = fn.sql_name() if hasattr(fn, "sql_name") else str(fn.this if hasattr(fn, "this") else fn.__class__.__name__)
        except Exception:
            name = ""
        out.append(str(name or "").lower())
    return out


def validate_sql_for_sandbox(
    sql: str, *, forbidden_schemas: "set[str] | frozenset[str] | None" = None
) -> SqlGuardResult:
    """D14 + R-F3 — single SELECT (with optional CTE) only.

    Returns SqlGuardResult. ok=False 면 caller 가 audit `attachment.sandbox.sql_denied`
    dispatch + 사용자 에러 응답.

    TASK-0128 (#2): forbidden_schemas 로 호출 컨텍스트별 금지 스키마를 주입한다. 기본값
    None 이면 sandbox 기본 집합(_FORBIDDEN_SCHEMAS = information_schema/mysql/sys/perf).
    agent 의 execute_sql 은 카탈로그 조회가 필요하므로 {agent_memory} 만 금지해 호출한다.
    """
    raw = (sql or "").strip()
    forbid = forbidden_schemas if forbidden_schemas is not None else _FORBIDDEN_SCHEMAS
    if not raw:
        return SqlGuardResult(False, error_reason="empty SQL")

    # 보조 denylist 우선 검사 (defense in depth).
    matched = _check_secondary_denylist(raw)
    # comment-only pattern 은 block 안 함 — 다만 log 에 표기.
    block_patterns = [p for p in matched if p not in (r"--[ \t]*[^\n]*",)]
    if block_patterns:
        return SqlGuardResult(
            False,
            error_reason=f"denylist match: {block_patterns[0]}",
            denied_patterns=block_patterns,
        )

    if _check_multi_statement(raw):
        return SqlGuardResult(False, error_reason="multi-statement not allowed", denied_patterns=["multi-statement"])

    if not SQLGLOT_AVAILABLE:
        # sqlglot 부재 시 conservative — deny (sandbox SQL 은 ship gate 의 일부, 라이브러리 없으면 활성 안 함).
        return SqlGuardResult(False, error_reason="sqlglot library not available")

    try:
        parsed = sqlglot.parse(raw, dialect="mysql")
    except Exception as exc:
        return SqlGuardResult(False, error_reason=f"sqlglot parse failed: {exc}")

    if not parsed or len(parsed) > 1 or parsed[0] is None:
        return SqlGuardResult(False, error_reason=f"expected 1 statement, got {len(parsed)}")

    root = parsed[0]
    # AST shape allowlist: root 는 SELECT 또는 WITH (CTE) 이어야 함.
    select_root = root
    if isinstance(root, _exp.With):
        # CTE root — 본체 select 부분 추출.
        select_root = root.this
    if not isinstance(select_root, _exp.Select):
        return SqlGuardResult(False, error_reason=f"only SELECT/CTE allowed, got {root.__class__.__name__}")

    # lock clause 검사 (FOR UPDATE / LOCK IN SHARE MODE 등 sqlglot 가 SELECT.args["locks"] 로 expose).
    locks = select_root.args.get("locks") or []
    if locks:
        return SqlGuardResult(False, error_reason=f"lock clause not allowed: {locks}", denied_patterns=["FOR UPDATE/LOCK"])

    # into 검사.
    if select_root.args.get("into"):
        return SqlGuardResult(False, error_reason="INTO clause not allowed", denied_patterns=["INTO"])

    # table refs 의 schema 검사.
    table_refs = _collect_table_refs(root)
    for db, name in table_refs:
        if db and db in forbid:
            return SqlGuardResult(
                False,
                error_reason=f"forbidden schema: {db}",
                denied_patterns=[f"schema:{db}"],
            )
        # un-qualified table 이름이 forbidden schema 와 동일하면 (잠재 escape) 도 거부.
        if name in forbid:
            return SqlGuardResult(
                False,
                error_reason=f"forbidden table name: {name}",
                denied_patterns=[f"table:{name}"],
            )

    # function 검사.
    func_names = _collect_function_names(root)
    for fn in func_names:
        if fn in _FORBIDDEN_FUNCTIONS:
            return SqlGuardResult(
                False,
                error_reason=f"forbidden function: {fn}()",
                denied_patterns=[f"fn:{fn}"],
            )

    # ast_summary — audit 의 normalized form.
    summary = {
        "statement_type": "SELECT_CTE" if isinstance(root, _exp.With) else "SELECT",
        "table_refs": [f"{db + '.' if db else ''}{name}" for db, name in table_refs],
        "function_count": len(func_names),
        "has_cte": isinstance(root, _exp.With),
    }
    return SqlGuardResult(True, ast_summary=summary)
