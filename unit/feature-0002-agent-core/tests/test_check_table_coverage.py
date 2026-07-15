"""TASK-20260714T233000-attach-table-coverage: 첨부 SQL ↔ 실 DB 테이블 커버리지 결정론 대조 검증.

conversation_audit FR-partial-evidence 라이브 실측 잔존(LoginEventLog false-missing)의 근본 =
모델이 첨부 CamelCase(`LoginEventLog`)를 실 DB 소문자(`logineventlog`, lower_case_table_names=1)와
대소문자 구분 비교해 '누락' 오판. 프롬프트 레버는 확률적으로만 완화 → 코드로 결정론 봉인.

`_tool_check_table_coverage` 는 DB 테이블명(정본) 기준으로, 첨부가 그 테이블을 **조작**
(TRUNCATE/DELETE/DROP/INSERT/UPDATE/ALTER)하는지 case-fold 로 판정한다. §18.8 적대패널
REV-20260714T233000 이 적발한 B1(절단)·B2(주석 오염)·M1(컬럼/함수 동명 오집계) 회귀도 검증.
"""
from __future__ import annotations

import modules.tools as tools


def _install(monkeypatch, db_tables, attachment_content, *, allow=True, truncated=False):
    """DB 테이블 목록 + 첨부 콘텐츠를 주입(순수 로직 검증, 실 DB/MinIO 비의존)."""
    monkeypatch.setattr(tools, "_struct_schema_access_error", lambda s: (None if allow else "오류: 차단됨"))
    monkeypatch.setattr(tools._dialects, "active", lambda: type("D", (), {
        "describe_schema_tables": staticmethod(lambda schema, db="": "SELECT 1"),
    })())
    rows = [(t, 0, "InnoDB", "") for t in db_tables]
    monkeypatch.setattr(tools, "_raw_execute_sql", lambda conn, sql: ([("rows", ["table"], rows)], None))
    import agent_core
    monkeypatch.setattr(
        agent_core, "_load_attachment_inline_texts",
        lambda: {528: {"filename": "init.sql", "content": attachment_content, "truncated": truncated}},
    )


def _section(out: str, header_kw: str) -> str:
    """출력에서 특정 섹션 헤더 이후 텍스트(다음 '###' 전까지) 반환."""
    if header_kw not in out:
        return ""
    tail = out.split(header_kw, 1)[1]
    return tail.split("\n###", 1)[0].split("\n>", 1)[0]


# ── 핵심 seal: CamelCase 조작이 미조작(누락)으로 오판되지 않음 ──────────────────
def test_camelcase_op_counted_not_missing(monkeypatch):
    db = ["logineventlog", "charactermakinglog", "errorlog"]
    att = (
        "USE `gunzlog`;\n"
        "TRUNCATE TABLE `charactermakinglog`;\n"
        "TRUNCATE TABLE `LoginEventLog`;\n"   # CamelCase — DB 는 소문자
    )
    _install(monkeypatch, db, att)
    out = tools._tool_check_table_coverage(None, {"schema_name": "gunzlog"})
    assert "미조작 **1**" in out            # errorlog 만 미조작
    miss = _section(out, "조작(TRUNCATE/DELETE/DROP 등)하지 않는 DB 테이블")
    assert "errorlog" in miss
    assert "logineventlog" not in miss       # 대소문자 seal: 미조작 아님


# ── B2: 블록/인라인/# 주석이 활성으로 새지 않음 ─────────────────────────────
def test_block_comment_not_active_op(monkeypatch):
    db = ["account", "gametype"]
    att = (
        "USE `gunzgame`;\n"
        "TRUNCATE TABLE `account`;\n"
        "/* 의도적 보존: TRUNCATE TABLE `gametype`; */\n"   # 블록주석 — 비활성
    )
    _install(monkeypatch, db, att)
    out = tools._tool_check_table_coverage(None, {"schema_name": "gunzgame"})
    assert "스크립트가 조작 **1**" in out
    assert "주석에서만 조작 **1**" in out    # gametype 은 주석 조작
    assert "미조작 **0**" in out


def test_inline_and_hash_comment_not_active_op(monkeypatch):
    db = ["account", "gametype", "level"]
    att = (
        "TRUNCATE TABLE `account`; -- TRUNCATE TABLE `gametype`;\n"   # 인라인 트레일링
        "# TRUNCATE TABLE `level`;\n"                                  # MySQL # 주석
    )
    _install(monkeypatch, db, att)
    out = tools._tool_check_table_coverage(None, {"schema_name": "s"})
    assert "스크립트가 조작 **1**" in out    # account 만 활성
    assert "주석에서만 조작 **2**" in out    # gametype, level


# ── M1: 컬럼/함수/키워드 동명은 '조작'으로 오집계되지 않음 ──────────────────
def test_column_or_function_name_not_false_operated(monkeypatch):
    # DB `status`/`log` 이 컬럼/함수로만 등장 → 미조작(실제 TRUNCATE 안 됨).
    db = ["account", "status", "log"]
    att = (
        "TRUNCATE TABLE `account`;\n"
        "UPDATE `account` SET flag = 1 WHERE status = 1;\n"   # status = 컬럼
        "SELECT LOG(price) FROM `account`;\n"                 # log = 함수
    )
    _install(monkeypatch, db, att)
    out = tools._tool_check_table_coverage(None, {"schema_name": "s"})
    miss = _section(out, "하지 않는 DB 테이블")
    assert "status" in miss and "log" in miss   # 조작 아님 → 미조작
    assert "미조작 **2**" in out


# ── B1: 절단 첨부 → '미조작'을 authoritative 로 확정하지 않음 ────────────────
def test_truncated_attachment_downgrades_authority(monkeypatch):
    db = ["account", "errorlog"]
    att = "TRUNCATE TABLE `account`;\n"   # errorlog 는 안 보임(절단됐을 수 있음)
    _install(monkeypatch, db, att, truncated=True)
    out = tools._tool_check_table_coverage(None, {"schema_name": "s"})
    assert "첨부 절단됨" in out
    assert "확정(authoritative) 아님" in out
    assert "절단" in out


# ── m1: USE/schema-qualified 로 cross-schema 동명 구분 ──────────────────────
def test_cross_schema_qualified_not_counted(monkeypatch):
    # 대상 스키마 gunzlog, 첨부는 gunzgame.foo 만 조작 → gunzlog 관점에서 foo 는 미조작.
    db = ["foo"]
    att = "USE `gunzgame`;\nTRUNCATE TABLE `gunzgame`.`foo`;\n"
    _install(monkeypatch, db, att)
    out = tools._tool_check_table_coverage(None, {"schema_name": "gunzlog"})
    assert "미조작 **1**" in out
    assert "`foo`" in _section(out, "하지 않는 DB 테이블")


def test_all_operated_reports_no_missing(monkeypatch):
    db = ["a", "b"]
    att = "TRUNCATE TABLE `a`;\nDELETE FROM `B`;\n"   # b 는 대문자 + DELETE
    _install(monkeypatch, db, att)
    out = tools._tool_check_table_coverage(None, {"schema_name": "s"})
    assert "미조작 테이블 없음" in out
    assert "미조작 **0**" in out


def test_schema_access_gate_blocks(monkeypatch):
    _install(monkeypatch, ["a"], "TRUNCATE TABLE `a`;", allow=False)
    out = tools._tool_check_table_coverage(None, {"schema_name": "agent_memory"})
    assert "차단" in out


def test_missing_attachment_is_graceful(monkeypatch):
    _install(monkeypatch, ["a"], "TRUNCATE TABLE `a`;")
    import agent_core
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    out = tools._tool_check_table_coverage(None, {"schema_name": "s"})
    assert "첨부" in out and "찾을 수 없" in out


# ── 헬퍼 직접 검증 ──────────────────────────────────────────────────────────
def test_operated_tables_helper_case_and_ops():
    # 대소문자 무시 + 조작 동사 뒤만 + IF EXISTS 스킵.
    ops = tools._operated_tables(
        "TRUNCATE TABLE `LoginEventLog`;\nDROP TABLE IF EXISTS `Foo`;\nUPDATE `bar` SET x=1;", "s")
    assert ops == {"logineventlog", "foo", "bar"}
    # 컬럼/함수 동명은 미포함.
    assert "status" not in tools._operated_tables("UPDATE `t` SET c=1 WHERE status=1;", "s")


def test_split_sql_active_comment_helper():
    active, comment = tools._split_sql_active_comment(
        "TRUNCATE TABLE `a`; -- keep `b`\n/* `c` */\n# `d`\nDELETE FROM `e`;")
    assert "`a`" in active and "`e`" in active
    assert "`b`" in comment and "`c`" in comment and "`d`" in comment
    assert "`b`" not in active and "`c`" not in active and "`d`" not in active


def test_registered_in_tool_handlers():
    assert "check_table_coverage" in tools._TOOL_HANDLERS
    names = [d["function"]["name"] for d in tools.TOOL_DEFINITIONS]
    assert "check_table_coverage" in names   # LLM 노출 base 세트 포함
