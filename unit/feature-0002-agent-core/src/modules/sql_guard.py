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
    # re-gate(5차): 서버/로그인 정체성·역할·권한 enumeration + DB/객체/스키마 메타데이터 probe 함수.
    # AST 함수명 기반 차단(주석 난독화·문자열 리터럴 오판에 견고 — regex 대체).
    "serverproperty", "suser_name", "suser_id", "suser_sid", "suser_sname", "original_login",
    "is_srvrolemember", "is_rolemember", "is_member", "has_perms_by_name", "fn_my_permissions",
    "fn_builtin_permissions", "connectionproperty", "context_info", "host_name", "host_id",
    "user_name", "app_name", "loginproperty", "pwdcompare", "pwdencrypt",
    "db_name", "db_id", "databasepropertyex", "databaseproperty", "has_dbaccess",
    "file_name", "filegroup_name", "object_id", "object_name", "object_schema_name",
    "object_definition", "objectproperty", "objectpropertyex", "col_name", "col_length",
    "columnproperty", "schema_id", "schema_name", "current_schema", "type_id", "type_name", "typeproperty",
    "cert_id", "database_principal_id", "fulltextcatalogproperty", "indexproperty",
    "indexkey_property",
    # re-gate(6차): 추가 정체성·권한·메타데이터 probe 함수.
    "current_user", "user_id", "permissions", "sessionproperty", "session_context",
    "fileproperty", "filegroupproperty", "index_col", "stats_date",
    # re-gate(7차): SQL Server Security Functions(암호화/키/인증서) + 메타데이터 함수 전 계열 보강.
    # 수동 denylist 의 누락을 줄이기 위해 MS 문서 카테고리(Security/Metadata Functions)를 망라.
    # (DB GRANT 가 hard backstop — RO 로그인은 CONTROL 권한 부재로 키/인증서 함수 자체가 실패하지만,
    #  앱-레이어에서도 enumeration 표면을 줄인다.)
    "certprivatekey", "certencoded", "certproperty", "cert_id",
    "asymkey_id", "asymkeyproperty", "symkeyproperty",
    "key_id", "key_guid", "key_name",
    "decryptbykey", "decryptbykeyautoasymkey", "decryptbykeyautocert", "decryptbyasymkey",
    "decryptbycert", "decryptbypassphrase",
    "encryptbykey", "encryptbyasymkey", "encryptbycert", "encryptbypassphrase",
    "signbyasymkey", "signbycert", "verifysignedbyasymkey", "verifysignedbycert",
    "crypt_gen_random", "cryptographic_provider_properties",
    "assemblyproperty", "fulltextserviceproperty", "applock_mode", "applock_test",
    "file_id", "file_idex", "filegroup_id", "filegroup_name", "file_name",
    "object_definition", "original_db_name", "parsename", "scope_identity",
    "database_principal_id", "loginproperty", "suser_name",
}

# re-gate(6차): niladic 정체성 함수(USER/SESSION_USER/SYSTEM_USER/CURRENT_USER)는 sqlglot 버전에 따라
# 함수 노드가 아니라 **bare Column 식별자**로 파싱된다(v27: SESSION_USER/USER=Column). 무자격(table 없음)·
# 무인용 식별자만 차단해 실제 컬럼(`[user]`/`t.user`)은 허용한다.
_NILADIC_IDENTITY_FUNCS = frozenset({"user", "session_user", "system_user", "current_user"})

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
    # re-gate(5차): 시스템/메타데이터 함수(SERVERPROPERTY/OBJECT_ID/DB_NAME/...)·NEXT VALUE FOR 는 raw regex
    # 가 문자열 리터럴(`'OBJECT_ID'`)·주석 난독화(`NEXT/**/VALUE FOR`)에서 과·미차단하므로 **AST 기반**
    # (_FORBIDDEN_FUNCTIONS_TSQL + _has_forbidden_special_node)으로 이전했다. 여기 regex 목록엔 두지 않는다.
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
        # re-gate BLOCKER2: TVF-in-FROM(`forbidden.dbo.fnTvf()`)은 this=Anonymous 라 name='' 이지만
        # catalog(forbidden)/db(dbo)가 채워진다 — name 비어도 catalog/db 가 있으면 수집해 cross-DB 검사 대상.
        if name or catalog or db:
            out.append((catalog, db, name))
    return out


def _table_alias_names(node) -> set[str]:
    """re-gate(7차): statement 의 테이블 alias·테이블명·CTE 명 집합(소문자).

    UDT/CLR 인스턴스 메서드 호출(`p.geom.STArea()`)의 leading 식별자는 **테이블 alias**(p)이지 catalog 가
    아니다. 함수 namespace 추출 시 leading 이 이 집합에 있으면 메서드 호출로 보고 catalog 검사에서 제외한다
    (정상 spatial/XML/CLR 메서드 과차단 방지)."""
    if _exp is None:
        return set()
    names: set[str] = set()
    for t in node.find_all(_exp.Table):
        try:
            a = (t.alias or "").strip().lower()
            if a:
                names.add(a)
            n = (t.name or "").strip().lower()
            if n:
                names.add(n)
        except Exception:
            pass
    for c in node.find_all(_exp.CTE):
        try:
            a = (c.alias or "").strip().lower()
            if a:
                names.add(a)
        except Exception:
            pass
    return names


def _collect_qualified_func_refs(node) -> list[tuple[str, str]]:
    """re-gate BLOCKER2: 3-part **함수호출**(`catalog.schema.fn()`)의 (catalog, schema) 추출.

    `SELECT forbidden.dbo.fnLeak()` 은 sqlglot 에서 Table 노드가 아니라 Dot 체인
    `Dot(Dot(Id(forbidden), Id(dbo)), Anonymous(fnLeak))` 로 파싱돼 `_collect_table_refs` 가 못 잡는다.
    말단이 함수(Func/Anonymous)인 Dot 의 앞쪽 식별자 체인을 namespace 로 보고 catalog(DB)/schema 를 뽑아
    cross-DB allowlist 검사 대상에 포함시킨다(미허용 DB 의 scalar/TVF 우회 차단).

    re-gate(7차): leading 식별자가 테이블 alias/명/CTE 면 UDT 메서드 호출(`p.geom.STArea()`)이므로 제외.
    """
    if _exp is None:
        return []
    out: list[tuple[str, str]] = []
    aliases = _table_alias_names(node)

    def _idents(n, acc):
        if n is None:
            return
        if isinstance(n, _exp.Dot):
            _idents(n.args.get("this"), acc)
            e = n.args.get("expression")
            if isinstance(e, _exp.Identifier):
                acc.append((e.name or "").strip().lower())
        elif isinstance(n, _exp.Identifier):
            acc.append((n.name or "").strip().lower())
        elif isinstance(n, _exp.Column):
            for part in ("catalog", "db", "table"):
                p = n.args.get(part)
                if isinstance(p, _exp.Identifier):
                    acc.append((p.name or "").strip().lower())

    for dot in node.find_all(_exp.Dot):
        expr = dot.args.get("expression")
        if isinstance(expr, (_exp.Func, _exp.Anonymous)):
            acc: list[str] = []
            _idents(dot.args.get("this"), acc)
            acc = [a for a in acc if a]
            if acc and acc[0] in aliases:
                continue  # 테이블 alias.column.method() — UDT 메서드 호출, catalog 아님
            if len(acc) >= 2:
                # 마지막 2개 = (catalog, schema) — 예: [forbidden, dbo] → catalog=forbidden, schema=dbo
                out.append((acc[-2], acc[-1]))
            elif len(acc) == 1:
                # re-gate(5차) BLOCKER2: 1-part 함수 namespace — MySQL `db.fn()` 의 db(=schema, allowlist 대조
                # 대상) / MSSQL `dbo.fn()` 의 schema. schema 슬롯으로 반환해 collect 가 schemas 에 합류시킨다.
                out.append(("", acc[0]))
    return out


def _has_overqualified_function(node) -> bool:
    """re-gate(3차) BLOCKER2: 4-part 함수호출(`server.db.schema.fn()`) 검출.

    Dot-체인 함수의 namespace 식별자가 3개 이상이면 linked-server 4-part 다(`linked.appdb.dbo.fnLeak()`).
    `_collect_qualified_func_refs` 는 뒤 2개(catalog.schema)만 취해 leading linked-server 를 버리므로,
    여기서 별도 검출해 전면 거부한다(Table 4-part 거부와 대칭).

    re-gate(7차): leading 이 테이블 alias/명/CTE 면 UDT 메서드 체인이므로 4-part 로 오판하지 않는다.
    """
    if _exp is None:
        return False
    aliases = _table_alias_names(node)
    for dot in node.find_all(_exp.Dot):
        expr = dot.args.get("expression")
        if isinstance(expr, (_exp.Func, _exp.Anonymous)):
            acc: list[str] = []
            _idents_chain(dot.args.get("this"), acc)
            acc = [a for a in acc if a]
            if acc and acc[0] in aliases:
                continue  # UDT 메서드 호출 — 과차단 방지
            if len(acc) >= 3:
                return True
    return False


def _idents_chain(n, acc):
    """Dot/Identifier/Column 체인의 식별자를 순서대로 수집(헬퍼 — _collect_qualified_func_refs 와 공유 로직)."""
    if n is None or _exp is None:
        return
    if isinstance(n, _exp.Dot):
        _idents_chain(n.args.get("this"), acc)
        e = n.args.get("expression")
        if isinstance(e, _exp.Identifier):
            acc.append((e.name or "").strip().lower())
    elif isinstance(n, _exp.Identifier):
        acc.append((n.name or "").strip().lower())
    elif isinstance(n, _exp.Column):
        for part in ("catalog", "db", "table"):
            p = n.args.get(part)
            if isinstance(p, _exp.Identifier):
                acc.append((p.name or "").strip().lower())


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
        # re-gate(3차) CTE 오판: CTE 명(WITH c AS ...)의 참조(`FROM c`)는 무자격 테이블이 아니다.
        # CTE alias 를 모아 무자격 판정에서 제외(정상 CTE 가 has_unqualified 로 차단되던 회귀 차단).
        cte_names = set()
        for _cte in stmt.find_all(_exp.CTE):
            try:
                a = (_cte.alias or "").strip().lower()
                if a:
                    cte_names.add(a)
            except Exception:
                pass
        for catalog, db, name in _collect_table_refs(stmt):
            if db:
                schemas.add(db)
            elif name and name not in cte_names:
                # name 만 있는 무자격 테이블(스키마 미지정) — fail-closed 대상. CTE 참조·catalog/db-only(TVF)은 제외.
                has_unqualified = True
            if catalog:
                catalogs.add(catalog)
        # re-gate BLOCKER2: 3-part 함수호출의 catalog/schema 도 cross-DB 검사 대상에 합류.
        for fcatalog, fschema in _collect_qualified_func_refs(stmt):
            if fschema:
                schemas.add(fschema)
            if fcatalog:
                catalogs.add(fcatalog)
        # FR-readonly-query-shapes-overblock: read-only SHOW(SHOW CREATE TABLE/COLUMNS/INDEX/TABLE STATUS)
        # 의 대상 스키마(.db)도 제품 allowlist 대조 대상에 포함(caller _freeform_sql_access_error 가 강제).
        # SHOW VARIABLES/STATUS 등 .db 없는 서버-전역 introspection 은 스키마 참조 0 → allowlist 무영향.
        if isinstance(stmt, _exp.Show):
            _sdb = _show_target_db(stmt)
            if _sdb:
                schemas.add(_sdb)
    return (schemas, has_unqualified, catalogs)


def _collect_function_names(node) -> list[str]:
    """AST 의 모든 Func / Anonymous 의 이름 (소문자).

    Anonymous 함수는 sql_name() 이 'ANONYMOUS' 를 줘 실제 이름을 놓치므로 `.name` 을 쓴다. AST 기반이라
    주석 난독화(`OBJECT_ID/**/(...)`)·문자열 리터럴(`'OBJECT_ID'`) 오판에 모두 견고하다(regex 대체).
    """
    if _exp is None:
        return []
    out: list[str] = []
    for fn in node.find_all(_exp.Func):
        if isinstance(fn, _exp.Anonymous):
            name = str(getattr(fn, "name", "") or "")
        else:
            try:
                name = fn.sql_name()
            except Exception:
                name = type(fn).__name__
        out.append(str(name or "").lower())
    return out


# re-gate(5차): SYSTEM_USER/SUSER_SNAME/CURRENT_USER → CurrentUser, SESSION_USER → SessionUser, NEXT VALUE FOR
# → NextValueFor 로 정규화돼 함수명 검출을 빠져나간다. 해당 노드 타입을 직접 차단(주석 난독화에도 견고).
def _has_forbidden_special_node(node) -> str | None:
    if _exp is None:
        return None
    if list(node.find_all(_exp.NextValueFor)):
        return "NEXT VALUE FOR"
    if hasattr(_exp, "CurrentUser") and list(node.find_all(_exp.CurrentUser)):
        return "SYSTEM_USER/SUSER_SNAME"
    if hasattr(_exp, "SessionUser") and list(node.find_all(_exp.SessionUser)):
        return "SESSION_USER"
    # bare Column 으로 파싱되는 niladic 정체성 함수(버전 의존). 무자격·무인용만 차단(실제 컬럼은 통과).
    for col in node.find_all(_exp.Column):
        if col.args.get("table"):
            continue  # 자격 있는 컬럼(t.user) — 실제 컬럼
        ident = col.this
        if isinstance(ident, _exp.Identifier) and not getattr(ident, "quoted", False):
            if (ident.name or "").lower() in _NILADIC_IDENTITY_FUNCS:
                return f"niladic system function: {ident.name}"
    return None


# FR-readonly-query-shapes-overblock (§18.8 승인 Critical): sql_guard 의 SELECT/CTE-only shape 게이트가
# LLM 이 리뷰·introspection 에 자연스럽게 쓰는 **read-only** 패턴을 과차단하던 것을 좁게 보정한다.
# 허용 대상은 (1) 최상위 set-op(UNION/INTERSECT/EXCEPT of SELECTs) (2) 아래 read-only SHOW 화이트리스트뿐.
# GRANTS/PRIVILEGES/PROCESSLIST/DATABASES/ENGINE/PLUGINS/BINLOG/MASTER·SLAVE·REPLICA STATUS 등 enumeration·
# 복제내부·권한열람 SHOW 는 **계속 차단**(정보노출/보안). SHOW 대상 스키마(.db)는 forbidden(내부DB) 차단 +
# 제품 allowlist(collect_schema_refs→_freeform_sql_access_error) 강제. 쓰기·부수효과 SHOW 는 애초에 없음.
_READONLY_SHOW_KINDS: frozenset = frozenset({
    # 테이블/뷰 구조·DDL 리뷰(이 마찰의 "테이블 변경사항" 필요) + 서버 config/status.
    # 루틴(PROCEDURE/FUNCTION) 정의는 전용 도구 describe_routine 이 담당하므로 SHOW CREATE PROCEDURE/
    # FUNCTION 은 여기 넣지 않는다(guard 는 계속 거부→describe_routine 유도, 중복 경로 방지).
    "CREATE TABLE", "CREATE VIEW",
    "COLUMNS", "FULL COLUMNS",
    "INDEX", "INDEXES", "KEYS",
    "TABLE STATUS",
    "VARIABLES", "SESSION VARIABLES", "GLOBAL VARIABLES",
    "STATUS", "SESSION STATUS", "GLOBAL STATUS",
})


def _show_kind(show) -> str:
    """exp.Show 의 종류(`.this`)를 대문자·단일공백 정규화."""
    return re.sub(r"\s+", " ", str(getattr(show, "this", "") or "").strip()).upper()


def _show_target_db(show) -> str:
    """exp.Show 의 대상 스키마(.db) 를 인용 제거 lowercase 로. 없으면 ''."""
    if _exp is None:
        return ""
    db = show.args.get("db")
    if isinstance(db, _exp.Identifier):
        return (db.name or "").strip().lower()
    if db is None:
        return ""
    return str(db).strip().strip("`\"[]").lower()


def _validate_readonly_show(show, forbid: "set[str] | frozenset[str]", dialect: str) -> SqlGuardResult:
    """read-only SHOW introspection 검증 — 화이트리스트 종류 + 대상 스키마 forbidden 차단.

    허용 종류(SHOW CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES/STATUS 등)만 통과하고,
    나머지 SHOW(GRANTS/DATABASES/PROCESSLIST 등)는 기존과 동일하게 거부한다. 제품 allowlist 는
    collect_schema_refs(SHOW .db 수집)→tools._freeform_sql_access_error 가 별도로 강제한다.
    """
    kind = _show_kind(show)
    if kind not in _READONLY_SHOW_KINDS:
        # 비-read-only SHOW — shape 거부(기존 메시지 유지: 구조 탐색은 전용 도구/허용 SHOW 로 유도).
        return SqlGuardResult(
            False,
            error_reason=f"only SELECT/CTE allowed, got Show ({kind or 'SHOW'})",
            denied_patterns=[f"show:{kind or 'SHOW'}"],
        )
    dbname = _show_target_db(show)
    if dbname and dbname in forbid:
        return SqlGuardResult(
            False,
            error_reason=f"forbidden schema: {dbname}",
            denied_patterns=[f"schema:{dbname}"],
        )
    return SqlGuardResult(
        True,
        ast_summary={
            "statement_type": "SHOW",
            "dialect": dialect,
            "show_kind": kind,
            "show_db": dbname,
        },
    )


# REV-20260713T171821 §18.8 security 패널(적대검증): shape 게이트가 root 타입만 보므로, **데이터 수정 CTE**
# (`WITH c AS (DELETE/INSERT/UPDATE … RETURNING) SELECT … c`)나 서브쿼리·union 분기에 숨은 write/DDL 노드가
# accepted shape(Select/With/SetOp) 안에 실려 통과할 수 있었다(pre-existing 잠복 — MySQL/MSSQL 은 DML-in-CTE
# 미지원·RO GRANT 가 backstop 이나 guard 는 authoritative 여야 함). 트리 전체에서 write/DDL/command 노드를
# 스캔해 거부(defense-in-depth). SELECT/SHOW/UNION read-only 트리는 이 노드들을 포함하지 않는다(false-positive 0 실측).
_WRITE_NODE_TYPES: tuple = tuple(
    c for c in (
        getattr(_exp, _n, None) for _n in (
            "Insert", "Update", "Delete", "Merge",
            "Create", "Drop", "Alter", "TruncateTable",
            "Command", "Copy", "LoadData",
        )
    ) if c is not None
) if _exp is not None else ()


def _find_write_node(root) -> str | None:
    """accepted shape 트리(CTE 본체·서브쿼리·union 분기 포함) 안 write/DDL/command 노드명. 없으면 None."""
    if _exp is None:
        return None
    for cls in _WRITE_NODE_TYPES:
        for _ in root.find_all(cls):
            return cls.__name__
    return None


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
    # FR-readonly-query-shapes-overblock: read-only SHOW introspection(SHOW CREATE TABLE/VIEW·COLUMNS·
    # INDEX·TABLE STATUS·VARIABLES/STATUS 등)은 화이트리스트로 통과, 나머지 SHOW 는 거부.
    if isinstance(root, _exp.Show):
        return _validate_readonly_show(root, forbid, dialect)

    # AST shape allowlist: root 는 SELECT · WITH(CTE) · 최상위 set-op(UNION/INTERSECT/EXCEPT of SELECTs).
    # set-op 는 read-only 결합이며, 구성 SELECT·모든 하위노드가 아래 금지-스키마/함수/lock/into 검사를
    # find_all 로 **전수** 통과해야 한다(분기별 격리 — 예: `SELECT … UNION SELECT … FROM agent_memory.x`
    # 는 forbidden schema 로 차단됨).
    select_root = root
    if isinstance(root, _exp.With):
        # CTE root — 본체 select/set-op 부분 추출.
        select_root = root.this
    _SETOP = getattr(_exp, "SetOperation", None)
    _is_setop = _SETOP is not None and isinstance(select_root, _SETOP)
    if not (isinstance(select_root, _exp.Select) or _is_setop):
        return SqlGuardResult(False, error_reason=f"only SELECT/CTE/UNION allowed, got {root.__class__.__name__}")
    # set-op 이 실제 SELECT 로만 구성됐는지(비어있지 않은지) 방어.
    if _is_setop and not list(select_root.find_all(_exp.Select)):
        return SqlGuardResult(False, error_reason="set operation without SELECT branches", denied_patterns=["setop-empty"])

    # lock / into 검사 — **모든 SELECT 분기**(union 구성·CTE·서브쿼리 포함)에 적용.
    # (FOR UPDATE / LOCK IN SHARE MODE 는 select.args["locks"], MySQL `INTO @var/OUTFILE`·T-SQL
    #  `SELECT … INTO newtbl` 부수효과는 select.args["into"] 로 노출.) 단일 SELECT 도 자기 자신 1개.
    for _sel in root.find_all(_exp.Select):
        if _sel.args.get("locks"):
            return SqlGuardResult(False, error_reason=f"lock clause not allowed: {_sel.args.get('locks')}", denied_patterns=["FOR UPDATE/LOCK"])
        if _sel.args.get("into"):
            return SqlGuardResult(False, error_reason="INTO clause not allowed", denied_patterns=["INTO"])

    # write/DDL 노드 스캔(defense-in-depth) — accepted shape 안에 숨은 데이터 수정 CTE·서브쿼리 write 거부.
    # (root-level DML 은 위 shape 게이트가 이미 거부; 여기선 CTE 본체·서브쿼리·union 분기의 중첩 write 를 잡는다.)
    _wnode = _find_write_node(root)
    if _wnode:
        return SqlGuardResult(
            False,
            error_reason=f"write/DDL statement not allowed: {_wnode}",
            denied_patterns=[f"write:{_wnode}"],
        )

    # re-gate BLOCKER2(2차): 4-part 참조(`server.database.schema.object`) 차단. sqlglot 은 4-part 를
    # catalog/db/name 3슬롯으로 collapse 하며 실제 schema 를 잃어, 첫 토큰(linked-server 이름)이 catalog 로
    # 오인돼 cross-DB 검사를 우회한다(`appdb.forbidden.dbo.t`→catalog=appdb). linked-server/4-part 는 전면 거부.
    for _t in root.find_all(_exp.Table):
        try:
            if len(_t.parts) >= 4:
                return SqlGuardResult(
                    False,
                    error_reason="4-part(linked-server) reference not allowed",
                    denied_patterns=["4-part-ref"],
                )
        except Exception:
            pass
    # 4-part 함수호출(linked-server.db.schema.fn())도 거부 — Table 노드로 안 잡히는 Dot 체인.
    if _has_overqualified_function(root):
        return SqlGuardResult(
            False,
            error_reason="4-part(linked-server) function reference not allowed",
            denied_patterns=["4-part-func"],
        )
    # re-gate(5차): AST 정규화로 함수명 검출을 빠져나가는 특수 노드(NEXT VALUE FOR / SYSTEM_USER / SUSER_SNAME
    # / SESSION_USER / CURRENT_USER) — 주석 난독화에도 견고하게 노드 타입으로 차단.
    special = _has_forbidden_special_node(root)
    if special:
        return SqlGuardResult(
            False,
            error_reason=f"forbidden construct: {special}",
            denied_patterns=[f"node:{special}"],
        )

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
        "statement_type": (
            "SELECT_CTE" if isinstance(root, _exp.With)
            else "SET_OP" if _is_setop
            else "SELECT"
        ),
        "dialect": dialect,
        "table_refs": [
            f"{catalog + '.' if catalog else ''}{db + '.' if db else ''}{name}"
            for catalog, db, name in table_refs
        ],
        "function_count": len(func_names),
        "has_cte": isinstance(root, _exp.With),
    }
    return SqlGuardResult(True, ast_summary=summary)
