"""feature-0022: agent PG scratch workspace — 순수 로직·보안 guard 단위 테스트.

DB(psycopg)·라이브 PG 를 요구하는 경로(materialize/run_sql/reaper 실행)는 라이브/PB 단계에서
검증하고, 여기서는 psycopg 없이 검증 가능한 (1) 스키마명 결정론 (2) 타입 추론 (3) 식별자 안전화
(4) **scratch guard**(대화 스키마 밖 접근·위험 구문 차단 — 보안 핵심) (5) enabled 기본 OFF 게이트를
다룬다. guard 는 sqlglot 만 있으면 검증 가능(라이브 DB 불필요).
"""

import datetime as dt

import modules.scratch as scratch


# ── 스키마명 결정론 ──────────────────────────────────────────────────────────
def test_schema_for_deterministic_and_format():
    s1 = scratch.schema_for("conv-abc")
    s2 = scratch.schema_for("conv-abc")
    assert s1 == s2
    assert scratch._SCHEMA_RE.match(s1), s1  # s_<24 hex>
    assert scratch.schema_for("other") != s1


def test_schema_for_empty_none():
    assert scratch.schema_for("") is None
    assert scratch.schema_for(None) is None


# ── 타입 추론 ────────────────────────────────────────────────────────────────
def test_infer_pg_type():
    assert scratch.infer_pg_type([1, 2, 3]) == "bigint"
    assert scratch.infer_pg_type([1, 2.5, 3]) == "double precision"
    assert scratch.infer_pg_type([True, False]) == "boolean"
    assert scratch.infer_pg_type([dt.datetime(2026, 1, 1), dt.datetime(2026, 2, 1)]) == "timestamptz"
    assert scratch.infer_pg_type(["a", "b"]) == "text"
    assert scratch.infer_pg_type([1, "x"]) == "text"          # 혼합 → text
    assert scratch.infer_pg_type([None, None]) == "text"       # 전부 null → text
    assert scratch.infer_pg_type([1, None, 2]) == "bigint"     # null 무시
    assert scratch.infer_pg_type([True, 1]) == "text"          # bool+int 혼합 → text


# ── 식별자 안전화 ────────────────────────────────────────────────────────────
def test_safe_ident():
    assert scratch._safe_ident("Orders", "t") == "orders"
    assert scratch._safe_ident("my table!", "t") == "my_table_"
    assert scratch._safe_ident("123abc", "t").startswith("t")   # 선두 숫자 → fallback 접두
    assert scratch._safe_ident("", "col_0") == "col_0"
    assert len(scratch._safe_ident("x" * 200, "t")) <= 63


def test_dedupe_idents():
    out = scratch._dedupe_idents(["a", "a", "b", "a"])
    assert len(set(out)) == len(out)     # 전부 유일
    assert out[0] == "a"


# ── scratch guard (보안 핵심) ────────────────────────────────────────────────
CONV_SCHEMA = scratch.schema_for("guard-test")  # 예: s_<hex>


def _ok(sql):
    return scratch.scratch_guard(sql, CONV_SCHEMA)[0]


def test_guard_allows_workspace_operations():
    assert _ok("SELECT * FROM orders")
    assert _ok("SELECT a.x FROM orders a JOIN users u ON a.id = u.id")
    assert _ok("CREATE TABLE t (id bigint, v text)")
    assert _ok("INSERT INTO t VALUES (1, 'x')")
    assert _ok("UPDATE t SET v = 'y' WHERE id = 1")
    assert _ok("DELETE FROM t WHERE id = 1")
    assert _ok("DROP TABLE t")
    assert _ok("WITH c AS (SELECT 1 AS a) SELECT * FROM c")
    # 자기 대화 스키마로 명시 자격한 참조는 허용.
    assert _ok(f"SELECT * FROM {CONV_SCHEMA}.orders")


def test_guard_blocks_cross_schema():
    for sql in (
        "SELECT * FROM public.users",
        "SELECT * FROM _scratch_admin.schema_registry",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM some_other_schema.t",
    ):
        assert not scratch.scratch_guard(sql, CONV_SCHEMA)[0], sql


def test_guard_blocks_cross_db_catalog():
    assert not _ok("SELECT * FROM appdb.dbo.t")  # 3-part(catalog) → 차단


def test_guard_blocks_multi_statement():
    assert not _ok("SELECT 1; DROP TABLE t")


def test_guard_blocks_dangerous_constructs():
    assert not _ok("COPY t FROM '/etc/passwd'")
    assert not _ok("SET search_path TO public")


def test_guard_blocks_dangerous_functions():
    assert not _ok("SELECT pg_read_file('/etc/passwd')")
    assert not _ok("SELECT dblink('a', 'b')")
    assert not _ok("SELECT pg_sleep(10)")


# ── feature-0021 적대 리뷰 대응 회귀 테스트 (BLOCK/HIGH 봉인) ──────────────────
def test_guard_blocks_function_body_bypass():
    # BLOCK: CREATE FUNCTION 문자열 본문에 cross-schema 참조 은닉 우회 — allowlist 로 전면 차단.
    assert not _ok("CREATE FUNCTION leak() RETURNS text LANGUAGE sql AS 'SELECT ssn FROM s_v.customers'")
    assert not _ok("CREATE OR REPLACE FUNCTION f() RETURNS void AS $$ BEGIN DROP SCHEMA s_v CASCADE; END $$ LANGUAGE plpgsql")
    assert not _ok("CREATE PROCEDURE p() LANGUAGE sql AS 'SELECT 1'")
    assert not _ok("CREATE VIEW v AS SELECT * FROM s_v.x")


def test_guard_blocks_pg_catalog_enumeration():
    # HIGH: pg_catalog 무자격 참조로 타 대화 메타데이터 열거 — pg_ 접두 차단.
    assert not _ok("SELECT * FROM pg_class")
    assert not _ok("SELECT nspname FROM pg_namespace")
    assert not _ok('SELECT * FROM "pg_tables"')
    assert not _ok("SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace")


def test_guard_blocks_other_ddl_and_commands():
    assert not _ok("DROP SCHEMA s_victim CASCADE")   # DROP 은 TABLE/INDEX kind 만
    assert not _ok("DO $$ BEGIN PERFORM 1; END $$")
    assert not _ok("CALL some_proc()")
    assert not _ok("CREATE EXTENSION dblink")
    assert not _ok("ALTER TABLE t SET SCHEMA public")


def test_guard_blocks_cross_schema_in_ctas_and_insert():
    # CTAS/INSERT 본문의 cross-schema 참조도 AST 로 잡혀 차단.
    assert not _ok("CREATE TABLE t AS SELECT * FROM s_victim.x")
    assert not _ok("INSERT INTO t SELECT * FROM s_victim.x")
    assert not _ok("CREATE TABLE t (LIKE s_victim.x)")


def test_guard_allows_ddl_index_and_ctas_self():
    assert _ok("CREATE INDEX ix ON orders(id)")
    assert _ok("DROP INDEX ix")
    assert _ok("CREATE TABLE summary AS SELECT id, count(*) FROM orders GROUP BY id")
    assert _ok("TRUNCATE orders")


def test_guard_denies_empty_and_unparseable():
    assert not _ok("")
    assert not _ok("this is not sql ;;;")


# ── enabled 게이트 (기본 OFF — 병합만으로 동작 안 바뀜) ─────────────────────────
def test_enabled_default_off(monkeypatch):
    # 런타임 스위치 기본 0 → enabled() False (인프라 여부와 무관).
    monkeypatch.setattr(scratch, "_rt", lambda key: 0 if key == "AGENT_SCRATCH_ENABLED" else scratch._DEFAULTS.get(key, 0))
    assert scratch.enabled() is False


def test_tool_defs_hidden_when_disabled(monkeypatch):
    import modules.tools as tools
    monkeypatch.setattr(scratch, "enabled", lambda: False)
    assert tools.scratch_tool_defs() == []
    base = [{"type": "function", "function": {"name": "execute_sql"}}]
    assert tools.with_scratch_tools(base) == base


def test_statement_timeout_sql_not_parameterized():
    # 회귀: PG 는 SET 값에 파라미터 바인딩을 허용하지 않는다 — 반드시 정수 인라인(placeholder 금지).
    stmt = scratch._statement_timeout_sql()
    assert stmt.startswith("SET statement_timeout = ")
    assert "%s" not in stmt and "$" not in stmt
    # 마지막 토큰이 정수여야 한다.
    assert stmt.rsplit("= ", 1)[1].strip().isdigit()


def test_scratch_guidance_constant_present():
    # feature-0022 guidance: assistant·ask-worker 가 scratch 를 적극 사용하도록 하는 프롬프트 지침이
    # 존재하고 4 도구를 언급하는지(활성 시 주입) 최소 sanity.
    import agent_core
    g = agent_core._SCRATCH_WORKSPACE_GUIDANCE
    assert isinstance(g, str) and len(g) > 100
    for tok in ("scratch_import", "scratch_sql", "scratch_list", "scratch_reset"):
        assert tok in g, tok


def test_tool_defs_shown_when_enabled(monkeypatch):
    import modules.tools as tools
    monkeypatch.setattr(scratch, "enabled", lambda: True)
    defs = tools.scratch_tool_defs()
    names = {d["function"]["name"] for d in defs}
    assert {"scratch_import", "scratch_sql", "scratch_list", "scratch_reset"} <= names
    base = [{"type": "function", "function": {"name": "execute_sql"}}]
    combined = tools.with_scratch_tools(base)
    assert len(combined) == len(base) + len(defs)
