"""Regression: TASK-0174 — "전체 N행 미리보기" 링크가 다른 쿼리 CSV 로딩.

`_collapse_large_tables` 가 답변 속 대형 표를 csv_paths 에 **위치 인덱스**로
1:1 매칭했다. 그러나 csv_paths 에는 표로 렌더되지 않은 보조 쿼리(MIN/MAX 등)
결과 CSV 까지 실행 순서대로 섞여 있어, 첫 대형 표(ranking 15행)에 보조 쿼리
CSV(MIN/MAX 1행)가 붙어 미리보기 클릭 시 무관한 결과를 로드했다 (#118 후속).

수정: 표의 데이터 값 토큰과 각 CSV 의 값 토큰 overlap 으로 매칭. 확신 매칭이
없으면(겹침 0) 잘못된 링크를 붙이지 않는다.

라이브 DB 비의존 — render.save_csv 로 실제 CSV 파일 생성 후 순수 함수 검증.
"""
from modules import render
import agent_core


_RANK_TABLE = "\n".join([
    "| 부위 | 아이템ID | 장착 캐릭터 수 |",
    "| --- | --- | --- |",
    "| 머리 | 2520504 | 10,112명 |",
    "| 머리 | 2520507 | 8,090명 |",
    "| 머리 | 2520505 | 4,878명 |",
    "| 가슴 | 2021501 | 515,285명 |",
    "| 가슴 | 2021001 | 265,856명 |",
    "| 가슴 | 2021002 | 120,000명 |",
    "| 다리 | 2030001 | 99,999명 |",
])


def _make_csvs(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    # 보조 쿼리(MIN/MAX) — 실행 순서상 먼저, 답변엔 표로 렌더 안 됨.
    minmax = render.save_csv("resultset1", ["MIN(ItemID)", "MAX(ItemID)"], [["1", "5000005"]])
    # ranking 쿼리 — 답변에 대형 표로 렌더됨. 값(ItemID·count)이 표와 일치.
    ranking = render.save_csv(
        "resultset1",
        ["Parts", "ItemID", "cnt"],
        [
            ["머리", "2520504", "10112"],
            ["머리", "2520507", "8090"],
            ["머리", "2520505", "4878"],
            ["가슴", "2021501", "515285"],
            ["가슴", "2021001", "265856"],
            ["가슴", "2021002", "120000"],
            ["다리", "2030001", "99999"],
        ],
    )
    return minmax, ranking


def test_collapse_links_table_to_matching_csv_not_positional(tmp_path, monkeypatch):
    minmax, ranking = _make_csvs(tmp_path, monkeypatch)
    answer = "ItemID 1~5,000,005 범위입니다.\n\n" + _RANK_TABLE
    # csv_paths 실행 순서 = [minmax, ranking]. 위치 인덱스였다면 minmax 가 붙던 버그.
    out = agent_core._collapse_large_tables(answer, [minmax, ranking])

    assert "전체 7행 미리보기" in out
    assert f"path={ranking}" in out      # 값이 일치하는 ranking CSV 로 링크
    assert f"path={minmax}" not in out   # 보조 쿼리 CSV 가 잘못 붙지 않음


def test_collapse_omits_link_when_no_value_and_no_shape_match(tmp_path, monkeypatch):
    minmax, _ranking = _make_csvs(tmp_path, monkeypatch)
    # _RANK_TABLE 은 3열, minmax 는 2열 — 값 overlap 0 + 컬럼 수도 불일치 →
    # 잘못된 링크를 붙이지 않고 생략.
    out = agent_core._collapse_large_tables(_RANK_TABLE, [minmax])

    assert "미리보기]" not in out
    assert "path=" not in out
    assert "2520504" in out  # 미리보기 데이터 행은 보존


def test_collapse_shape_fallback_for_measure_only_table(tmp_path, monkeypatch):
    # 식별 토큰이 없는 측정값(%·소수) 위주 표 — 값 매칭 불가지만 컬럼 수(3)가
    # 일치하는 CSV 로 폴백해 링크를 복구. 형태 불일치 보조쿼리(2열)는 배제.
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    minmax = render.save_csv("resultset1", ["MIN", "MAX"], [["1", "9999999"]])
    rates = render.save_csv(
        "resultset1",
        ["rank", "rate", "score"],
        [[str(n), f"{n}.5", f"{n}.0"] for n in range(1, 12)],
    )
    table = "\n".join([
        "| 순위 | 비율 | 점수 |",
        "| --- | --- | --- |",
        "| 1 | 12.5% | 4.5 |",
        "| 2 | 11.2% | 4.1 |",
        "| 3 | 9.8% | 3.9 |",
        "| 4 | 8.1% | 3.5 |",
        "| 5 | 7.0% | 3.2 |",
        "| 6 | 6.3% | 3.0 |",
        "| 7 | 5.1% | 2.8 |",
    ])
    # 측정값 셀에서 식별 토큰이 추출되지 않음을 전제 검증.
    assert agent_core._distinctive_tokens(["12.5%", "4.5", "1"]) == set()

    out = agent_core._collapse_large_tables(table, [minmax, rates])
    assert f"path={rates}" in out      # 컬럼 수 일치 CSV 로 폴백
    assert f"path={minmax}" not in out  # 형태 불일치 보조쿼리 배제


def test_distinctive_tokens_filters_rank_noise():
    # 1~2자리(순위) 제외, 콤마 천단위·단위 접미 포함 숫자열은 추출.
    toks = agent_core._distinctive_tokens(["1", "순위", "10,112명", "2520504"])
    assert "10112" in toks
    assert "2520504" in toks
    assert "1" not in toks   # 순위 노이즈 제외
