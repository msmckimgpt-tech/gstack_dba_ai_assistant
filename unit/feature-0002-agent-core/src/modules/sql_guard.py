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

# 금지 function names (case-insensitive). MySQL(기본) 어휘.
_FORBIDDEN_FUNCTIONS = {
    "sleep",
    "benchmark",
    "load_file",
    "load_extension",
    "get_lock",
    "release_lock",
    "uuid",  # information leak (uuid host id) — Sprint 1 conservative
}

# T-SQL(MSSQL) 금지 function/table-function names (P6, DESIGN §3.4 축3). FROM 절에 등장 가능한
# OPENROWSET/OPENQUERY 류는 single-SELECT shape 를 통과하므로 AST Func 검출 + regex 양면 차단.
_FORBIDDEN_FUNCTIONS_TSQL = {
    "openrowset",     # 임의 파일/원격 데이터 읽기
    "openquery",      # linked server 임의 쿼리
    "opendatasource", # ad-hoc 원격 연결
    "xp_cmdshell",    # OS 명령 실행(RCE)
    "sp_executesql",  # 동적 SQL
    "waitfor",        # WAITFOR DELAY — SLEEP 등가(DoS)
}

# 보조 denylist regex (allowlist 가 못 잡는 edge — backup defense). MySQL 어휘 (골든: 무변경).
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

# T-SQL(MSSQL) 보조 denylist regex (P6, DESIGN §3.4 축3 매트릭스 박제). AST shape allowlist 가
# single-SELECT 로 통과시키는 위험 구문(FROM 절 table-function·인라인 위험구문)을 텍스트로 보강 차단.
# `--` 주석 audit-only 패턴은 _DENYLIST_PATTERNS 와 동일 문자열이어야 block 제외 필터가 동작한다.
_DENYLIST_PATTERNS_TSQL: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bxp_cmdshell\b", re.IGNORECASE),       # RCE
    re.compile(r"\bsp_executesql\b", re.IGNORECASE),     # 동적 SQL
    re.compile(r"\bsp_oacreate\b", re.IGNORECASE),       # OLE automation
    re.compile(r"\bOPENROWSET\b", re.IGNORECASE),        # 임의 파일/원격 읽기
    re.compile(r"\bOPENQUERY\b", re.IGNORECASE),         # linked server
    re.compile(r"\bOPENDATASOURCE\b", re.IGNORECASE),    # ad-hoc 원격
    re.compile(r"\bWAITFOR\b", re.IGNORECASE),           # DELAY/TIME — DoS
    re.compile(r"\bEXEC(UTE)?\b", re.IGNORECASE),        # 동적 실행/proc 호출
    re.compile(r"\bINTO\s+", re.IGNORECASE),             # SELECT ... INTO newtbl (부수효과: 테이블 생성)
    re.compile(r"@@", re.IGNORECASE),                    # @@VERSION 등 시스템변수 정보유출
    re.compile(r"/\*\+\s*[^*]*\*/"),                     # optimizer hint 주석
    re.compile(r"--[ \t]*[^\n]*", re.MULTILINE),         # line comment (audit only)
)

# dialect(sqlglot name) → (denylist patterns, 추가 금지 function set)
_DIALECT_DENYLIST: "dict[str, tuple[tuple[re.Pattern[str], ...], set[str]]]" = {
    "mysql": (_DENYLIST_PATTERNS, set()),
    "tsql": (_DENYLIST_PATTERNS_TSQL, _FORBIDDEN_FUNCTIONS_TSQL),
}


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


def _check_secondary_denylist(sql: str, dialect: str = "mysql") -> list[str]:
    """보조 denylist regex — backup defense (allowlist 미흡 케이스 잡기). dialect 별 어휘 적용."""
    patterns, _ = _DIALECT_DENYLIST.get(str(dialect or "mysql").lower(), (_DENYLIST_PATTERNS, set()))
    matched: list[str] = []
    for pat in patterns:
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


def _collect_table_refs(node) -> list[tuple[str, str, str]]:
    """AST 의 모든 Table 노드의 (catalog, db, name) 반환 (P6: 3-part catalog 차원 포함).

    sqlglot 이 dialect 로 파싱하면 식별자 인용(MSSQL `[..]`/ANSI `"..."`, MySQL 백틱)은
    이미 벗겨진 plain 토큰으로 들어온다 → 대괄호/3-part/큰따옴표 우회(B-1) 가 닫힌다.
    `catalog` 는 3-part `catalog.schema.table` 의 DB 차원(MSSQL cross-DB 차단용, MySQL 은 보통 빈값).
    """
    if _exp is None:
        return []
    out: list[tuple[str, str, str]] = []
    for table in node.find_all(_exp.Table):
        # `.catalog`/`.db`/`.name` 은 인용(대괄호·백틱·ANSI 큰따옴표)을 벗긴 plain 텍스트를 준다.
        # str(table.args.get("db")) 는 quoted=True 일 때 따옴표를 포함해(`"agent_memory"`) 금지스키마
        # 비교가 빗나간다 → 반드시 unquoted accessor 사용(따옴표 우회 B-1 차단의 핵심).
        catalog = (table.catalog or "").strip().lower()
        db = (table.db or "").strip().lower()
        name = (table.name or "").strip().lower()
        if name:
            out.append((catalog, db, name))
    return out


def collect_schema_refs(
    sql: str, *, dialect: str = "mysql"
) -> "tuple[set[str], bool, set[str]]":
    """freeform SQL 의 table-ref 를 AST 로 수집 → (schemas, has_unqualified, catalogs).

    P6 축1: tools.py 의 정규식 `_extract_sql_schema_refs` 를 대체하는 단일 AST 추출점.
    동일 dialect 로 파싱하므로 sql_guard shape 게이트와 **방언 해석 차이(differential parse)** 가 없다.

    - schemas: 참조된 schema(db) 토큰 lowercase set (자격 있는 `schema.table` 의 schema).
    - has_unqualified: schema 미지정(무자격) table 이 하나라도 있으면 True (caller 가 datasource
      활성 시 fail-closed 거부 — Codex-1).
    - catalogs: 3-part `catalog.schema.table` 의 catalog 토큰 set (MSSQL cross-DB 차단용).

    파싱 실패 시 보수적으로 (set(), True, set()) — 무자격 취급해 datasource 경로에서 거부되게 한다
    (단, execute_sql 은 validate_sql_for_sandbox 가 선행해 파싱 실패를 이미 deny).
    """
    if not SQLGLOT_AVAILABLE or _exp is None:
        return (set(), True, set())
    try:
        parsed = sqlglot.parse(sql or "", dialect=str(dialect or "mysql").lower())
    except Exception:
        return (set(), True, set())
    schemas: set[str] = set()
    catalogs: set[str] = set()
    has_unqualified = False
    for stmt in parsed:
        if stmt is None:
            continue
        for catalog, db, _name in _collect_table_refs(stmt):
            if db:
                schemas.add(db)
            else:
                has_unqualified = True
            if catalog:
                catalogs.add(catalog)
    return (schemas, has_unqualified, catalogs)


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
    sql: str,
    *,
    forbidden_schemas: "set[str] | frozenset[str] | None" = None,
    dialect: str = "mysql",
) -> SqlGuardResult:
    """D14 + R-F3 — single SELECT (with optional CTE) only.

    Returns SqlGuardResult. ok=False 면 caller 가 audit `attachment.sandbox.sql_denied`
    dispatch + 사용자 에러 응답.

    TASK-0128 (#2): forbidden_schemas 로 호출 컨텍스트별 금지 스키마를 주입한다. 기본값
    None 이면 sandbox 기본 집합(_FORBIDDEN_SCHEMAS = information_schema/mysql/sys/perf).
    agent 의 execute_sql 은 카탈로그 조회가 필요하므로 {agent_memory} 만 금지해 호출한다.

    P6 (멀티 datasource Stage 2): dialect 인자로 `mysql`|`tsql` 분기. denylist 어휘·sqlglot
    파서·금지함수가 dialect 별로 적용된다. **T-SQL `SELECT ... INTO newtbl`(부수효과: 테이블
    생성)** 은 SELECT shape 로 보이므로 dialect 별 denylist(`INTO `) + AST into-arg 양면 차단.
    파싱 실패는 fail-closed(deny) 유지.
    """
    raw = (sql or "").strip()
    forbid = forbidden_schemas if forbidden_schemas is not None else _FORBIDDEN_SCHEMAS
    dialect = str(dialect or "mysql").lower()
    if not raw:
        return SqlGuardResult(False, error_reason="empty SQL")

    # 보조 denylist 우선 검사 (defense in depth) — dialect 별 어휘.
    matched = _check_secondary_denylist(raw, dialect)
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
        parsed = sqlglot.parse(raw, dialect=dialect)
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

    # into 검사 (dialect 무관: MySQL `INTO @var/OUTFILE`, T-SQL `SELECT ... INTO newtbl` 둘 다
    # sqlglot 이 select.args["into"] 로 노출 → 부수효과 SELECT 를 shape 단계에서 차단).
    if select_root.args.get("into"):
        return SqlGuardResult(False, error_reason="INTO clause not allowed", denied_patterns=["INTO"])

    # table refs 의 schema/catalog 검사 (catalog = 3-part DB 차원, P6 cross-DB).
    table_refs = _collect_table_refs(root)
    for catalog, db, name in table_refs:
        for part, label in ((catalog, "catalog"), (db, "schema"), (name, "table")):
            if part and part in forbid:
                return SqlGuardResult(
                    False,
                    error_reason=f"forbidden {label}: {part}",
                    denied_patterns=[f"{label}:{part}"],
                )

    # function 검사 — 기본 금지 + dialect 추가 금지.
    _, extra_forbidden_fns = _DIALECT_DENYLIST.get(dialect, (_DENYLIST_PATTERNS, set()))
    forbidden_fns = _FORBIDDEN_FUNCTIONS | set(extra_forbidden_fns)
    func_names = _collect_function_names(root)
    for fn in func_names:
        if fn in forbidden_fns:
            return SqlGuardResult(
                False,
                error_reason=f"forbidden function: {fn}()",
                denied_patterns=[f"fn:{fn}"],
            )

    # ast_summary — audit 의 normalized form.
    summary = {
        "statement_type": "SELECT_CTE" if isinstance(root, _exp.With) else "SELECT",
        "dialect": dialect,
        "table_refs": [
            f"{catalog + '.' if catalog else ''}{db + '.' if db else ''}{name}"
            for catalog, db, name in table_refs
        ],
        "function_count": len(func_names),
        "has_cte": isinstance(root, _exp.With),
    }
    return SqlGuardResult(True, ast_summary=summary)
