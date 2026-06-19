"""ITEM-01 eval harness 스모크 — 순수 단위(Bedrock·DB 불요, make test 포함).

라이브 측정(실제 파이프라인 + fixture)은 `make eval` 가 수행한다. 본 테스트는 결정적
구성요소(정규화/동치/retrieval P·R/read-only 가드/golden 무결성)만 검증한다.
"""
import datetime
import os
import sys
from decimal import Decimal

# tests/eval 를 sys.path 에 보장(pytest prepend 가 보통 처리하나 명시).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import metrics as M  # noqa: E402
import runner as R  # noqa: E402


def test_result_equiv_order_insensitive():
    a = [(1, "x"), (2, "y")]
    b = [(2, "y"), (1, "x")]
    assert M.result_equiv(a, b)


def test_result_equiv_numeric_normalization():
    # int / Decimal / 숫자문자열 / float 동치.
    assert M.result_equiv([(63,)], [(Decimal("63.000000"),)])
    assert M.result_equiv([(63.0,)], [("63",)])


def test_result_equiv_detects_mismatch():
    assert not M.result_equiv([(4,)], [(5,)])
    assert not M.result_equiv([(1,), (2,)], [(1,)])


def test_date_normalization():
    assert M.result_equiv([(datetime.date(2024, 1, 2),)], [("2024-01-02",)])


def test_retrieval_pr_na_when_no_groundtruth():
    assert M.retrieval_precision_recall([1, 2], []) is None
    assert M.retrieval_precision_recall([], None) is None


def test_retrieval_pr_computation():
    out = M.retrieval_precision_recall(["a", "b", "c"], ["b", "c", "d"])
    assert out["precision"] == round(2 / 3, 4)
    assert out["recall"] == round(2 / 3, 4)


def test_readonly_guard_allows_select():
    assert R._is_readonly("SELECT COUNT(*) FROM eval_fixture.customers")
    assert R._is_readonly("  with t as (select 1) select * from t  ")


def test_readonly_guard_blocks_mutations():
    assert not R._is_readonly("DELETE FROM eval_fixture.customers")
    assert not R._is_readonly("DROP TABLE eval_fixture.orders")
    assert not R._is_readonly("INSERT INTO eval_fixture.products VALUES (9,'x','y',1,1)")
    assert not R._is_readonly("")


def test_readonly_guard_blocks_exfiltration():
    # REV BLOCKER 회귀: 파일 유출/읽기계 차단.
    assert not R._is_readonly("SELECT a FROM t INTO OUTFILE '/tmp/x'")
    assert not R._is_readonly("SELECT a FROM t INTO DUMPFILE '/tmp/x'")
    assert not R._is_readonly("SELECT LOAD_FILE('/etc/passwd')")


def test_readonly_guard_allows_replace_function():
    # 오탐 회귀: REPLACE() 는 read-only 문자열 함수 → 허용.
    assert R._is_readonly("SELECT REPLACE(name,'a','b') FROM eval_fixture.customers")


def test_read_result_csv(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("cnt\n4\n", encoding="utf-8")
    cols, rows = R._read_result_csv(str(p))
    assert cols == ["cnt"]
    assert rows == [["4"]]
    # agent CSV(문자열) vs typed expected 가 정규화로 동치.
    assert M.result_equiv([(4,)], rows)


def test_readonly_guard_no_false_positive_on_column_names():
    # 'created_at' / 'update_count' 같은 컬럼명이 변경계로 오탐되지 않아야.
    assert R._is_readonly("SELECT created_at, update_count FROM eval_fixture.orders")


def test_judge_cap_default():
    assert isinstance(M.judge_cap(), int)
    assert M.judge_cap() >= 0


def test_golden_set_integrity():
    """golden ≥20 질문 + 필수 필드 + datasource 가드(eval_fixture)."""
    import pytest
    yaml = pytest.importorskip("yaml")
    path = os.path.join(os.path.dirname(__file__), "golden", "eval_fixture.yaml")
    with open(path, "r", encoding="utf-8") as f:
        golden = yaml.safe_load(f)
    assert golden["datasource"] == "eval_fixture"
    qs = golden["questions"]
    assert len(qs) >= 20, f"golden 질문 {len(qs)}개 — ≥20 필요(AC1)"
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids)), "golden id 중복"
    for q in qs:
        assert q["nl_question"].strip()
        sql = q["expected_sql"].strip().lower()
        assert sql.startswith("select"), f"{q['id']}: expected_sql 는 SELECT"
        assert "eval_fixture." in sql, f"{q['id']}: expected_sql 는 eval_fixture 스키마 한정"
