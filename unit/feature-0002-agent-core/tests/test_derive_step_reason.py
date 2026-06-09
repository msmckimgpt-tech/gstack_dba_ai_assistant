"""TASK-0175 — _derive_step_reason derived fallback 회귀 테스트.

배경: 실행 단계의 reason(왜)이 라이브에서 항상 빈 값이었다. LLM 이 tool_notes.reason
을 방출하지 않으면(SYSTEM_PROMPT 미지시) reason 에 derived fallback 이 없어
reason_text='' 로 고착. work 는 _derive_step_work fallback 으로 채워지나 reason 은
부재했음. 본 테스트는 모든 알려진 tool 이 비어있지 않은 결정적 근거를 파생하고,
호출부가 LLM 참값을 덮어쓰지 않음을 단언한다.
"""
from __future__ import annotations

import agent_core


def test_known_tools_yield_nonempty_reason():
    cases = {
        "list_schemas": {},
        "describe_schema": {"schema_name": "dbgame"},
        "describe_table": {"schema_name": "dbgame", "table_name": "item"},
        "search_tables": {"schema_name": "dbgame", "keyword": "item"},
        "get_sample_rows": {"schema_name": "dbgame", "table_name": "item"},
        "get_table_indexes": {"schema_name": "dbgame", "table_name": "item"},
        "get_foreign_keys": {"schema_name": "dbgame", "table_name": "item"},
        "explain_query": {"sql": "SELECT 1"},
    }
    for tool, args in cases.items():
        reason = agent_core._derive_step_reason(tool, args)
        assert reason and reason.strip(), f"{tool} 의 derived reason 이 비어있음"


def test_execute_sql_aggregate_vs_select():
    agg = agent_core._derive_step_reason(
        "execute_sql", {"sql": "SELECT COUNT(*) FROM `dbgame`.`item`"}
    )
    sel = agent_core._derive_step_reason(
        "execute_sql", {"sql": "SELECT * FROM `dbgame`.`item` LIMIT 10"}
    )
    assert "집계" in agg
    assert "조회" in sel
    assert agg != sel


def test_unknown_tool_returns_empty():
    # 알 수 없는 tool 은 빈 문자열(무의미한 근거 노출 방지 — 프런트가 빈 reason 은 미표시)
    assert agent_core._derive_step_reason("totally_unknown_tool", {}) == ""
    assert agent_core._derive_step_reason("", None) == ""


def test_case_and_none_args_robust():
    # tool 명 대소문자/공백 정규화 + args=None 방어
    assert agent_core._derive_step_reason("  DESCRIBE_TABLE  ", None)
    assert agent_core._derive_step_reason("Execute_SQL", {"sql": "select * from t"})
