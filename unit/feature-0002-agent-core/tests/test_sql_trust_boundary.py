"""TASK-0128 (#2/#8) SQL 신뢰경계 회귀 테스트.

이전 가드(uppercase prefix denylist)가 통과시키던 우회들을 sql_guard AST + ContextVar
allowlist 로 차단하는지 검증한다. 감사 DEEP_AUDIT_20260529.md #2 / #11(테스트 공백) 흡수.
"""
from __future__ import annotations

import contextvars

import pytest

from modules.sql_guard import validate_sql_for_sandbox

AGENT_FORBIDDEN = frozenset({"agent_memory", "mysql"})


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM dblog.orders LIMIT 5",
        "SELECT a.x FROM dblog.t a JOIN dblog.u b ON a.id=b.id WHERE a.x>0",
        "WITH c AS (SELECT 1 AS a) SELECT a FROM c",
        "SELECT * FROM information_schema.tables WHERE table_schema='dblog'",
        "SELECT * FROM sys.schema_table_statistics LIMIT 1",
    ],
)
def test_agent_select_allowed(sql):
    """정상 분석 SELECT/CTE + 카탈로그 조회는 허용 (회귀 방지 — 에이전트 정상 동작)."""
    r = validate_sql_for_sandbox(sql, forbidden_schemas=AGENT_FORBIDDEN)
    assert r.ok, f"정상 쿼리가 차단됨: {sql} :: {r.error_reason}"


@pytest.mark.parametrize(
    "sql,reason_kw",
    [
        ("SELECT 1; DELETE FROM dblog.orders", "multi"),       # 다중문
        ("/* c */ DELETE FROM dblog.orders", "SELECT"),         # 주석 우회 + write
        ("\tDELETE FROM dblog.orders", "SELECT"),               # 탭 우회 + write
        ("INSERT INTO dblog.orders VALUES (1)", "SELECT"),      # write verb (구 denylist 미차단)
        ("UPDATE dblog.orders SET x=1 WHERE id=1", "SELECT"),   # write verb
        ("REPLACE INTO dblog.orders VALUES (1)", "SELECT"),     # write verb
        ("SELECT * FROM agent_memory.WebAccounts", "agent_memory"),  # 내부 인증 테이블
        ("SELECT * FROM mysql.user", "mysql"),                  # 시스템 자격증명
        ("SELECT SLEEP(5)", "SLEEP"),                           # DoS
        ("SELECT BENCHMARK(1000000, MD5('x'))", "BENCHMARK"),   # DoS
        ("SELECT * FROM dblog.t FOR UPDATE", "FOR"),            # lock
        ("SELECT LOAD_FILE('/etc/passwd')", "LOAD_FILE"),       # 파일 유출
    ],
)
def test_agent_dangerous_blocked(sql, reason_kw):
    """write/다중문/내부스키마/DoS/lock/파일유출은 모두 차단."""
    r = validate_sql_for_sandbox(sql, forbidden_schemas=AGENT_FORBIDDEN)
    assert not r.ok, f"위험 쿼리가 통과됨: {sql}"


def test_allowlist_contextvar_isolation():
    """_ACTIVE_SCHEMA_ALLOWLIST 가 ContextVar 라 동시 ask 간 격리됨 (#8 race)."""
    import modules.tools as t

    def set_and_get(schemas):
        t.set_active_schema_allowlist(schemas)
        return t._ACTIVE_SCHEMA_ALLOWLIST.get()

    r1 = contextvars.copy_context().run(set_and_get, ["dblog"])
    r2 = contextvars.copy_context().run(set_and_get, ["dbgame"])
    assert r1 == {"dblog"}
    assert r2 == {"dbgame"}
    # 한 컨텍스트의 set 이 다른 컨텍스트로 누출되지 않음.
    assert r1 != r2


def test_whitelist_violation_blocks_cross_product():
    """allowlist 활성 시 비허용 스키마 참조는 위반으로 검출 (교차 product 격리)."""
    import modules.tools as t

    def check():
        t.set_active_schema_allowlist(["dblog"])
        # 허용 스키마
        assert t._whitelist_violation({"dblog"}) is None
        # 메타데이터는 항상 허용
        assert t._whitelist_violation({"information_schema"}) is None
        # 타 product 스키마는 차단
        assert t._whitelist_violation({"dbgame"}) is not None

    contextvars.copy_context().run(check)


def test_whitelist_none_allows_all_user_schemas():
    """allowlist 미설정(None=레거시 비-product 모드) 시 user 스키마 허용 (동작 보존)."""
    import modules.tools as t

    def check():
        t.set_active_schema_allowlist(None)
        assert t._whitelist_violation({"dblog", "dbgame"}) is None

    contextvars.copy_context().run(check)
