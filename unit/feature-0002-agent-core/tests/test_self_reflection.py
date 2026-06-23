"""ITEM-07 — Self-Reflection 자가수정 루프 헬퍼 단위 테스트 (LLM 무관).

execute_sql 실패 분류·넛지 구조·보안가드 제외(우회 유도 금지)·bounded 표기를 검증.
회복률 A/B(harness, chat)는 별도 — 에러유발 golden Q 대상, paced.
"""
import agent_core as AC


def test_fixable_error_detected():
    assert AC._is_fixable_sql_error("오류: Unknown column 'foo' in 'field list'")
    assert AC._is_fixable_sql_error("오류: Table 'db.t' doesn't exist")
    assert AC._is_fixable_sql_error("오류: You have an error in your SQL syntax")


def test_real_db_execution_error_shapes_fixable():
    # REV M1 회귀: 실제 DB 실행 실패는 tools.py 가 'SQL 실행 오류:' / '도구 실행 오류' 로 반환.
    # 주 대상(unknown column/table/syntax)이 이 경로로 오므로 반드시 fixable.
    assert AC._is_fixable_sql_error("SQL 실행 오류: (1054, \"Unknown column 'naem' in 'field list'\")")
    assert AC._is_fixable_sql_error("SQL 실행 오류: (1146, \"Table 'eval_fixture.oders' doesn't exist\")")
    assert AC._is_fixable_sql_error("도구 실행 오류 (execute_sql @ ds): syntax error near ')'")


def test_guard_block_not_fixable():
    # 보안 가드 차단은 자가수정 대상 아님 — 우회 넛지 금지(security).
    assert not AC._is_fixable_sql_error("오류: 보안 정책상 차단된 SQL — 위험 구문")
    assert not AC._is_fixable_sql_error("오류: 접근이 허용되지 않은 데이터베이스 참조: secret_db")
    assert not AC._is_fixable_sql_error("오류: 내부 데이터베이스 직접 조회가 차단되었습니다")


def test_non_error_not_fixable():
    assert not AC._is_fixable_sql_error("결과: 42 rows")
    assert not AC._is_fixable_sql_error("")
    assert not AC._is_fixable_sql_error(None)


def test_classify_sql_error():
    assert AC._classify_sql_error("오류: Unknown column 'x'") == "unknown-column"
    assert AC._classify_sql_error("오류: Table doesn't exist") in ("unknown-table", "unknown-column")
    assert AC._classify_sql_error("오류: SQL syntax error near ')'") == "syntax"
    assert AC._classify_sql_error("SQL 실행 오류: syntax error near 'table'") == "syntax"  # REV N2: syntax 우선
    assert AC._classify_sql_error("오류: lock wait timeout exceeded") == "execution"


def test_reflection_nudge_structure():
    nudge = AC._sql_reflection_nudge(
        "오류: Unknown column 'naem'", "SELECT naem FROM customers", 1, 2)
    assert "[자가수정 1/2]" in nudge                       # bounded 표기
    assert "unknown-column" in nudge                        # 분류
    assert "SELECT naem FROM customers" in nudge            # 원 SQL
    assert "그대로 재실행하지 말 것" in nudge                # 반복 금지
    assert "describe_table" in nudge                        # 표적 힌트


def test_reflection_nudge_truncates_long_sql():
    long_sql = "SELECT " + ("x," * 500) + "1"
    nudge = AC._sql_reflection_nudge("오류: syntax", long_sql, 2, 2)
    assert "[자가수정 2/2]" in nudge
    assert len(nudge) < len(long_sql) + 500   # 원 SQL 400자 cap 으로 절단
