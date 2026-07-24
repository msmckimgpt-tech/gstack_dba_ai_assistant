"""conv-audit (csv-inline-no-download): 대형 ```csv 펜스 블록 → /api/file 링크 후처리.

기존 `_collapse_large_tables` 는 Markdown 표(`|...|`)만 인식하는 blind spot 이 있어,
모델이 결과를 ```csv 펜스 블록으로 붙이면(라이브 관측 지배 패턴) 다운로드 링크가 전혀
주입되지 않아 "다운로드하실 수 있습니다" 안내가 dead-end 였다. `_collapse_large_csv_blocks`
는 대형 ```csv 블록을 MD 표와 동일하게 처리한다 — 값 토큰 매칭으로 저장 CSV 를 찾으면
헤더+미리보기 N행으로 접고 전체는 /api/file 링크로 제공, 매칭 실패 시 데이터 손실 없이 원문 유지.

라이브 DB 비의존 — render.save_csv 로 실제 CSV 파일 생성 후 순수 함수 검증.
"""
from modules import render
import agent_core


def _csv_block(header, rows):
    lines = ["```csv", header]
    lines.extend(rows)
    lines.append("```")
    return "\n".join(lines)


# ChapterIndex,DungeonIndex,Difficulty,Win_Count_Star_3,Fail_Count 형태 (라이브 재현).
_HEADER = "ChapterIndex,DungeonIndex,Difficulty,Win_Star3,Fail"
_ROWS = [
    "1,1,1,8,0",
    "1,2,1,3,0",
    "1,3,1,7,0",
    "1,4,1,34,0",
    "1,5,1,36,0",
    "1,6,1,29,0",
    "1,7,1,290123,0",  # 식별 토큰(≥3자리 숫자)
    "2,1,1,410456,1",
]


def _make_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    rows = [r.split(",") for r in _ROWS]
    return render.save_csv("resultset1", _HEADER.split(","), rows)


def test_large_csv_block_gets_download_link(tmp_path, monkeypatch):
    csv_path = _make_csv(tmp_path, monkeypatch)
    answer = "차원별 집계 결과입니다:\n\n" + _csv_block(_HEADER, _ROWS)
    out = agent_core._collapse_large_csv_blocks(answer, [csv_path])

    # 8 데이터 행 > threshold(5) → 미리보기로 접고 /api/file 링크 주입.
    assert "전체 8행 미리보기" in out
    assert f"path={csv_path}" in out
    # 헤더는 유지되고, 미리보기 상한(5행)을 넘는 뒤쪽 행은 잘려나간다.
    assert _HEADER in out
    assert "2,1,1,410456,1" not in out  # 마지막(8번째) 행은 미리보기에서 제외


def test_small_csv_block_untouched(tmp_path, monkeypatch):
    csv_path = _make_csv(tmp_path, monkeypatch)
    small = _csv_block(_HEADER, _ROWS[:3])  # 3 데이터 행 ≤ threshold
    answer = "소형 결과:\n\n" + small
    out = agent_core._collapse_large_csv_blocks(answer, [csv_path])
    # 소형 블록은 접지 않는다(원문 그대로) — 프론트 다운로드 버튼이 처리.
    assert out == answer
    assert "미리보기" not in out


def test_no_matching_csv_preserves_block(tmp_path, monkeypatch):
    # 저장 CSV 는 전혀 다른 값 → 값 토큰 overlap 0 → 링크 미주입, 블록 원문 보존(데이터 손실 방지).
    monkeypatch.setattr(render, "AGENT_OUT_DIR", str(tmp_path))
    unrelated = render.save_csv("resultset1", ["A", "B"], [["999888", "777666"]])
    answer = "결과:\n\n" + _csv_block(_HEADER, _ROWS)
    out = agent_core._collapse_large_csv_blocks(answer, [unrelated])
    # 매칭 실패 → 전체 블록(모든 행) 그대로 유지.
    assert "2,1,1,410456,1" in out
    assert "미리보기" not in out


def test_no_csv_paths_is_noop():
    answer = "결과:\n\n" + _csv_block(_HEADER, _ROWS)
    assert agent_core._collapse_large_csv_blocks(answer, []) == answer


def test_answer_without_csv_block_unchanged(tmp_path, monkeypatch):
    csv_path = _make_csv(tmp_path, monkeypatch)
    answer = "일반 텍스트 답변입니다. CSV 블록 없음."
    assert agent_core._collapse_large_csv_blocks(answer, [csv_path]) == answer


def _md_table(header, rows):
    lines = ["| " + " | ".join(header.split(",")) + " |"]
    lines.append("| " + " | ".join(["---"] * len(header.split(","))) + " |")
    for r in rows:
        lines.append("| " + " | ".join(r.split(",")) + " |")
    return "\n".join(lines)


def test_collapse_result_blocks_shared_used_no_double_link(tmp_path, monkeypatch):
    # 적대 리뷰 MINOR 회귀 잠금: 같은 결과가 MD표 + ```csv 블록 양쪽으로 나와도
    # 공유 used 로 하나의 CSV 가 이중 매칭되지 않는다 → /api/file 링크 정확히 1개.
    csv_path = _make_csv(tmp_path, monkeypatch)
    answer = (
        "표로도, CSV 로도 같은 결과를 제시합니다.\n\n"
        + _md_table(_HEADER, _ROWS)
        + "\n\n"
        + _csv_block(_HEADER, _ROWS)
    )
    out = agent_core._collapse_result_blocks(answer, [csv_path])
    assert out.count("/api/file?path=") == 1          # 이중 링크 없음(공유 used)
    assert out.count(f"path={csv_path}") == 1
    # 링크를 못 받은 쪽(csv 블록)은 원문 유지 → 데이터 손실 없음(프론트 버튼이 처리).
    assert "2,1,1,410456,1" in out


def test_collapse_result_blocks_noop_paths(tmp_path, monkeypatch):
    csv_path = _make_csv(tmp_path, monkeypatch)
    assert agent_core._collapse_result_blocks("", [csv_path]) == ""
    assert agent_core._collapse_result_blocks("텍스트", []) == "텍스트"
