"""`bin/measure-precondition-grounding.py` 집계 로직 회귀 (conversation_audit).

이 감지기는 `FR-review-precondition-assumed-not-verified` 의 **재발 여부를 판정하는
유일한 상시 신호**다. 감지기가 조용히 틀리면 "수정이 작동한다" 는 거짓 결론이 나온다 —
실제로 §18.8 codex 리뷰가 3라운드에 걸쳐 집계 결함 3건을 잡았고, 그중 하나는
**성공 신호(`미확인` 카운터)가 구조적으로 영원히 0** 인 결함이었다. 그래서 프로즈가
아니라 테스트로 고정한다.
"""
import importlib.util
import pathlib
import sys
import types

REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    "precondition_detector", REPO / "bin" / "measure-precondition-grounding.py")
M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(M)


def _row(answer: str, tools: str = "", cid: str = "conv-abcdefgh", mid: str = "1"):
    return [cid, mid, "2026-08-03 10:00", answer, tools]


# ── 집계 계약 ───────────────────────────────────────────────────────────────

def test_unverified_claim_is_counted():
    r = M.analyse([_row("| `steampaymenthistory` | 신규 생성 예정 |")])
    assert r["status_claims"] == 1
    assert r["unverified_claims"] == 1
    assert r["offending_conversations"][0]["objects"] == ["steampaymenthistory"]


def test_claim_backed_by_tool_result_is_not_counted_as_unverified():
    r = M.analyse([_row("| `steampaymenthistory` | 신규 생성 예정 |",
                        tools="## 'steampaymenthistory' 검색 결과 ... 1 테이블 검색됨")])
    assert r["status_claims"] == 1
    assert r["unverified_claims"] == 0


def test_unknown_only_line_is_counted_even_without_status_vocabulary():
    """§18.8 codex R3 P2 — 이 결함이 살아 있으면 **성공 신호가 영원히 0** 이다.

    `_CLAIM`(상태 어휘)을 먼저 요구하면 `\\`orders\\`: 미확인` 처럼 미확인만 쓴 줄이
    통째로 건너뛰어져, 수정이 작동해 미확인 표기가 늘어도 카운터가 오르지 않는다.
    """
    r = M.analyse([_row("- `orders_table`: 미확인 (조회하지 못했습니다)")])
    assert r["honest_unknown_objects"] == 1
    assert r["status_claims"] == 0
    assert r["unverified_claims"] == 0


def test_assertion_wins_over_earlier_unknown_for_same_object():
    """§18.8 codex R2 P1 — 앞줄 미확인이 뒷줄의 근거 없는 단정을 가리면 안 된다."""
    r = M.analyse([_row("| `ccu_table` | 미확인 |\n| `ccu_table` | 존재함 |")])
    assert r["status_claims"] == 1, "단정이 한 번이라도 있으면 주장으로 세야 한다"
    assert r["unverified_claims"] == 1
    assert r["honest_unknown_objects"] == 0, "단정된 객체는 정직 처리로 세지 않는다"


def test_same_object_across_lines_counts_once():
    r = M.analyse([_row("`x_table` 존재함\n`x_table` 이미 존재\n`x_table` 신규 생성 예정")])
    assert r["status_claims"] == 1


def test_tool_names_locals_and_constraint_names_excluded():
    """도구명·SQL 로컬변수·인덱스명은 DB 객체 상태 주장이 아니다(구조적 오탐)."""
    r = M.analyse([_row(
        "`search_tables` 로 확인했으나 존재하지 않음\n"
        "`p_BatchSize` 파라미터가 없습니다\n"
        "`IDX_AID_RegDate` 인덱스가 존재하지 않음\n"
        "`INFORMATION_SCHEMA` 에 없음")])
    assert r["status_claims"] == 0, "전부 제외 대상"


# ── fail-closed ────────────────────────────────────────────────────────────

def _fake_run(returncode: int, stdout: str, stderr: str = ""):
    class _R:
        pass
    _R.returncode, _R.stdout, _R.stderr = returncode, stdout, stderr
    return types.SimpleNamespace(run=lambda *a, **k: _R())


def test_empty_result_fails_closed(monkeypatch):
    """§18.8 codex R2 P1 — timeout abort 가 '대화 0건' 정상 측정으로 보고되면 안 된다."""
    monkeypatch.setattr(M, "subprocess", _fake_run(0, "   \n", "canceling statement"))
    try:
        M._fetch(90)
    except SystemExit as e:
        assert e.code == 3
    else:                                        # pragma: no cover
        raise AssertionError("빈 결과가 통과했다")


def test_psql_error_fails_closed(monkeypatch):
    monkeypatch.setattr(M, "subprocess", _fake_run(1, "", "permission denied"))
    try:
        M._fetch(90)
    except SystemExit as e:
        assert e.code == 2
    else:                                        # pragma: no cover
        raise AssertionError("psql 오류가 통과했다")


def test_query_is_read_only_and_bounded():
    """RO 강제 + 타임아웃 — 운영 DB 를 읽는 도구의 최소 안전장치."""
    assert "BEGIN READ ONLY;" in M._SQL
    assert "statement_timeout" in M._SQL
    assert "ON_ERROR_STOP=1" in " ".join(
        (REPO / "bin" / "measure-precondition-grounding.py").read_text(encoding="utf-8").split())
    # 쓰기 구문이 섞여 있지 않아야 한다.
    for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"):
        assert kw not in M._SQL.upper().replace("STATEMENT_TIMEOUT", "")


def test_output_does_not_claim_to_be_a_bound():
    """§18.8 codex R2 P1 — 오탐·누락이 둘 다 있으므로 '하한' 표기는 거짓이다."""
    src = (REPO / "bin" / "measure-precondition-grounding.py").read_text(encoding="utf-8")
    assert "하한 측정" not in src
    assert "스크린이지 지표가 아니다" in src
