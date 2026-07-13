"""read-only query shape 확장 (FR-readonly-query-shapes-overblock).

sql_guard 의 SELECT/CTE-only shape 게이트가 LLM 의 자연스러운 read-only 리뷰 SQL 을 과차단하던 것을
좁게 보정: (1) 최상위 set-op(UNION/INTERSECT/EXCEPT of SELECTs) (2) read-only SHOW 화이트리스트.

핵심 검증:
- 허용: UNION/UNION ALL of SELECTs · read-only SHOW(CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES/STATUS).
- **보안 불변식 유지(회귀 0)**: UNION 분기의 forbidden-schema/lock/into/금지함수는 여전히 차단 ·
  비-read-only SHOW(GRANTS/DATABASES/PROCESSLIST) 차단 · SHOW 대상 forbidden schema 차단 ·
  DELETE/DDL/multi-statement/INTO 차단 · SHOW .db 가 collect_schema_refs 로 제품 allowlist 대조에 합류.
"""
from __future__ import annotations

import modules.sql_guard as g

_INT = frozenset({"agent_memory"})


def _ok(sql, dialect="mysql"):
    return g.validate_sql_for_sandbox(sql, forbidden_schemas=_INT, dialect=dialect)


# ── 1. set-op(UNION) 허용 ──────────────────────────────────────────────
def test_union_of_selects_allowed():
    assert _ok("SELECT a FROM db.t1 UNION SELECT b FROM db.t2").ok is True


def test_union_all_allowed():
    r = _ok("SELECT a FROM db.t1 UNION ALL SELECT b FROM db.t2")
    assert r.ok is True
    assert r.ast_summary.get("statement_type") == "SET_OP"


def test_union_with_cte_allowed():
    assert _ok("WITH c AS (SELECT 1 AS x) SELECT x FROM c UNION SELECT b FROM db.t2").ok is True


# ── 2. set-op 분기별 보안 불변식 유지(회귀 0) ─────────────────────────────
def test_union_forbidden_schema_branch_blocked():
    r = _ok("SELECT a FROM db.t1 UNION SELECT pw FROM agent_memory.users")
    assert r.ok is False
    assert "agent_memory" in r.error_reason


def test_union_lock_branch_blocked():
    assert _ok("SELECT a FROM db.t1 FOR UPDATE UNION SELECT b FROM db.t2").ok is False


def test_union_forbidden_function_branch_blocked():
    assert _ok("SELECT SLEEP(3) UNION SELECT 1").ok is False


def test_union_into_branch_blocked():
    # INTO 부수효과가 어느 분기에 있어도 차단(분기 전수 검사).
    assert _ok("SELECT a INTO @v FROM db.t1 UNION SELECT b FROM db.t2").ok is False


# ── 3. read-only SHOW 허용 ─────────────────────────────────────────────
def test_show_create_table_allowed():
    r = _ok("SHOW CREATE TABLE `gunzgame`.`attendence`")
    assert r.ok is True
    assert r.ast_summary.get("statement_type") == "SHOW"
    assert r.ast_summary.get("show_db") == "gunzgame"


def test_show_variables_allowed():
    assert _ok("SHOW VARIABLES LIKE 'lower_case_table_names'").ok is True


def test_show_columns_index_status_allowed():
    assert _ok("SHOW COLUMNS FROM db.t").ok is True
    assert _ok("SHOW INDEX FROM db.t").ok is True
    assert _ok("SHOW TABLE STATUS FROM db").ok is True


# ── 4. SHOW 차단 유지 ──────────────────────────────────────────────────
def test_show_target_forbidden_schema_blocked():
    r = _ok("SHOW CREATE TABLE `agent_memory`.`x`")
    assert r.ok is False
    assert "agent_memory" in r.error_reason


def test_non_readonly_show_blocked():
    for sql in ("SHOW GRANTS", "SHOW DATABASES", "SHOW PROCESSLIST", "SHOW PRIVILEGES"):
        assert _ok(sql).ok is False, sql


def test_show_create_routine_not_in_readonly_allowlist():
    # 루틴 정의는 전용 도구 describe_routine 담당 — guard 는 SHOW CREATE PROCEDURE/FUNCTION 계속 거부
    # (중복 경로 방지, FR-show-create-routine-blocked 설계 유지). tools 가 describe_routine 으로 유도.
    assert _ok("SHOW CREATE PROCEDURE `db`.`p`").ok is False
    assert _ok("SHOW CREATE FUNCTION `db`.`f`").ok is False


# ── 4b. 데이터 수정 CTE / 중첩 write 거부 (REV §18.8 security 패널 CONFIRMED) ──
def test_data_modifying_cte_blocked():
    # WITH c AS (DELETE/INSERT/UPDATE … RETURNING) SELECT … 는 accepted shape(With→Select)로 보이나
    # write 노드가 트리에 숨어 있다 → defense-in-depth write-node 스캔이 거부해야 한다.
    for sql in (
        "WITH c AS (DELETE FROM t RETURNING id) SELECT * FROM c",
        "WITH c AS (INSERT INTO t VALUES (1) RETURNING id) SELECT * FROM c",
        "WITH c AS (UPDATE t SET x=1 RETURNING id) SELECT * FROM c",
    ):
        r = _ok(sql)
        assert r.ok is False, sql
        assert "write/DDL" in r.error_reason


def test_data_modifying_cte_blocked_tsql():
    r = _ok("WITH c AS (DELETE FROM t RETURNING id) SELECT * FROM c", dialect="tsql")
    assert r.ok is False


def test_recursive_and_nested_readonly_cte_allowed():
    # write 노드가 없는 정상 CTE·재귀 CTE·서브쿼리는 write-node 스캔 false-positive 없이 통과.
    assert _ok("WITH RECURSIVE r AS (SELECT 1 n UNION ALL SELECT n+1 FROM r WHERE n<5) SELECT * FROM r").ok is True
    assert _ok("SELECT a FROM db.t WHERE id IN (SELECT id FROM db.t2)").ok is True


# ── 5. 기존 불변식 회귀 0 ──────────────────────────────────────────────
def test_plain_select_still_ok():
    assert _ok("SELECT * FROM db.t WHERE id=1").ok is True


def test_write_and_multistatement_still_blocked():
    assert _ok("DELETE FROM db.t").ok is False
    assert _ok("UPDATE db.t SET x=1").ok is False
    assert _ok("SELECT 1; SELECT 2").ok is False
    assert _ok("SELECT a INTO OUTFILE '/tmp/x' FROM db.t").ok is False


# ── 6. collect_schema_refs 가 SHOW .db 를 수집(제품 allowlist 강제 경로) ──
def test_collect_schema_refs_picks_up_show_db():
    schemas, has_unqual, catalogs = g.collect_schema_refs(
        "SHOW CREATE TABLE `gunzgame`.`attendence`", dialect="mysql"
    )
    assert "gunzgame" in schemas


def test_collect_schema_refs_show_variables_no_schema():
    # 서버-전역 SHOW 는 스키마 참조 0 (allowlist 무영향).
    schemas, _has, _cat = g.collect_schema_refs("SHOW VARIABLES LIKE 'x'", dialect="mysql")
    assert not schemas
