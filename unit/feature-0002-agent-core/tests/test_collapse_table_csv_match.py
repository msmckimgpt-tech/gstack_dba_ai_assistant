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


def test_collapse_omits_link_for_analysis_table_with_tokens_no_overlap(tmp_path, monkeypatch):
    """TASK-0208: LLM 이 손으로 쓴 분석/요약 표(쿼리 결과 아님)에 "전체 N행
    미리보기" 오링크가 붙지 않아야 한다.

    재현(스크린샷): 답변에 SQL 분석용 쿼리 CSV(들)가 있고, 본문엔 쿼리 결과가
    아닌 "이슈 우선순위" 분석표가 있다. 분석표는 식별 토큰(라벨 문자열)이
    풍부하지만 어느 CSV 와도 겹치지 않는다. 그런데 컬럼 수가 우연히 같은 무관한
    CSV 가 폴백으로 붙어, 클릭 시 frontend 값 가드가 "결과 파일이 미리보기와
    일치하지 않아…" 로 거부했다. → 토큰이 있으면(겹침 0) 폴백 금지 → 링크 생략.
    """
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    # 대화 중 실행된 무관한 쿼리 결과 CSV — 5열(분석표와 컬럼 수만 우연히 동일).
    leftover = render.save_csv(
        "resultset1",
        ["c1", "c2", "c3", "c4", "c5"],
        [[f"r{n}a", f"r{n}b", f"r{n}c", f"r{n}d", f"r{n}e"] for n in range(1, 13)],
    )
    # LLM 이 손으로 쓴 5열 분석표(쿼리 결과 아님) — 라벨 토큰은 풍부.
    analysis = "\n".join([
        "| 우선순위 | ID | 파일 | 이슈 | 상태 |",
        "| --- | --- | --- | --- | --- |",
        "| CRITICAL | 1 | SP_LOG | GROUP_CONCAT IN 절 문자열 폭발 | 유효함 |",
        "| CRITICAL | 2 | SP_TRACE | SequenceID JOIN 팬아웃 | 재평가 올바른 설계 |",
        "| HIGH | 3 | SP_ORDER | ORDER BY 따옴표 정렬 무효 | 유효함 |",
        "| HIGH | 4 | SP_WIN | 윈도우 함수 LoginCount 비결정성 | 새로 발견 |",
        "| HIGH | 5 | SP_UNION | UNION 후 JOIN 로그인 로그 혼입 | 새로 발견 |",
        "| MEDIUM | 6 | SP_AGG | 집계 NULL 처리 누락 | 검토중 |",
    ])

    out = agent_core._collapse_large_tables(analysis, [leftover])

    assert "미리보기]" not in out      # 비-결과 분석표엔 링크 안 붙음
    assert "path=" not in out          # 무관한 CSV 링크 미부착
    assert "GROUP_CONCAT" in out       # 미리보기 데이터 행은 보존


def test_collapse_analysis_table_does_not_consume_genuine_csv_slot(tmp_path, monkeypatch):
    """TASK-0208 (used[] 슬롯 보존): 답변에 분석표와 진짜 결과표가 함께 있을 때,
    토큰 불일치 분석표가 폴백으로 CSV 슬롯을 소모해 뒤따르는 진짜 결과표의 링크를
    빼앗으면 안 된다. 분석표는 링크 생략(used 미설정) → 진짜 결과표는 값 매칭으로
    올바른 CSV 에 링크.
    """
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    # 진짜 ranking 쿼리 결과 — 값(ItemID·count)이 결과표와 일치. 컬럼 수=3.
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
    # 분석표(쿼리 결과 아님). 컬럼 수=3 — ranking CSV 와 우연히 동일.
    analysis = "\n".join([
        "| 우선순위 | 이슈 | 상태 |",
        "| --- | --- | --- |",
        "| CRITICAL | GROUP_CONCAT 폭발 | 유효함 |",
        "| CRITICAL | JOIN 팬아웃 | 재평가 |",
        "| HIGH | ORDER BY 정렬 무효 | 유효함 |",
        "| HIGH | 윈도우 함수 비결정성 | 새로 발견 |",
        "| HIGH | UNION 로그 혼입 | 새로 발견 |",
        "| MEDIUM | 집계 NULL 누락 | 검토중 |",
    ])
    # 답변 순서: 분석표가 먼저, 진짜 결과표가 나중 (분석표가 슬롯을 가로채는지 검증).
    answer = analysis + "\n\n" + _RANK_TABLE

    out = agent_core._collapse_large_tables(answer, [ranking])

    assert f"path={ranking}" in out       # 진짜 결과표가 올바른 CSV 로 링크
    assert out.count("미리보기]") == 1     # 링크는 정확히 1개(분석표엔 안 붙음)
