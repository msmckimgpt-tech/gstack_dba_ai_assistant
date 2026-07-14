"""conv-audit FR-partial-evidence-false-verification — 부분 증거 전수 단정 환각 봉인 회귀 테스트.

라이브 관측(conv 20260714…e6add7f1 "첨부파일과 실제 DB 비교 검증"):
① execute_sql 결과가 183행 중 50행 미리보기로 절단(gunzlog 전체 미열람)됐는데 답변은
   전수 검증한 것처럼 서술 + 첨부에 실재하는 TRUNCATE 를 "누락"으로 오진(환각).
② `SELECT @@lower_case_table_names` 가 denylist(@@)에 거부되자 문서상 기본값(0)으로
   추측해 반대 결론(실측 1) — 거부 피드백에 SHOW VARIABLES 교정 힌트 부재.

봉인 4-lever 를 단언한다:
- A: 절단 안내문에 epistemic 자기교정 지침(미열람 행 단정 금지·재조회 유도·CSV 비가독).
- B: 소형 결과 char-budget 내 전체 표시(_TOOL_PREVIEW_ROWS_MAX/CHAR_BUDGET) — 대형은 기존 캡.
- C: SYSTEM_PROMPT HANDLING RESULTS 확장(절단·부재/전수 단정·전/후 비교·옵션 실측).
- D: @@ 거부에 SHOW VARIABLES 유도 힌트(MySQL 한정, 가드 허용범위 불변).
"""
from __future__ import annotations

import agent_core
from modules import tools as T


def _rows(n: int, wide: bool = False) -> list:
    cell = "x" * 90 if wide else "tbl"
    return [(f"{cell}_{i}", "gunzgame") for i in range(n)]


# ── Lever B: byte-bounded 미리보기 확장 ──────────────────────────────────────


def test_small_result_under_cap_unchanged():
    stats: dict = {}
    out = T._format_result_sets(
        [("rows", ["TABLE_NAME", "TABLE_SCHEMA"], _rows(10))],
        max_rows=50, expand_rows=500, expand_char_budget=12_000, stats=stats,
    )
    assert "(10 행)" in out and "행만 표시" not in out
    assert stats == {"total_rows": 10, "shown_rows": 10, "truncated": False}


def test_medium_result_expands_fully_within_char_budget():
    # 라이브 재현: 183행 테이블 목록(협폭) — 종전엔 50행 절단 → 전수 표시로 구조 봉인
    stats: dict = {}
    out = T._format_result_sets(
        [("rows", ["TABLE_NAME", "TABLE_SCHEMA"], _rows(183))],
        max_rows=50, expand_rows=500, expand_char_budget=12_000, stats=stats,
    )
    assert "tbl_182" in out, "마지막 행까지 표시되어야 함"
    assert "행만 표시" not in out and "(183 행)" in out
    assert stats["truncated"] is False and stats["shown_rows"] == 183


def test_wide_result_stays_capped_with_epistemic_marker():
    # 광폭 행(행당 ~200자)은 char-budget 이 지켜 기존 50행 캡 유지 + 미열람 경고
    stats: dict = {}
    out = T._format_result_sets(
        [("rows", ["A", "B"], _rows(400, wide=True))],
        max_rows=50, expand_rows=500, expand_char_budget=12_000, stats=stats,
    )
    assert stats["truncated"] is True
    assert 50 <= stats["shown_rows"] < 400, "50행 하한 보장 + 예산 내 제한"
    assert "행만 표시" in out and "미열람" in out and "단정하지 말 것" in out


def test_row_hard_cap_500():
    stats: dict = {}
    T._format_result_sets(
        [("rows", ["N"], [(i,) for i in range(600)])],
        max_rows=50, expand_rows=500, expand_char_budget=1_000_000, stats=stats,
    )
    assert stats["shown_rows"] == 500 and stats["truncated"] is True


def test_legacy_call_without_expansion_keeps_cap():
    # expand 인자 없는 기존 caller(get_sample_rows 등)는 종전 동작(캡) 유지
    stats: dict = {}
    out = T._format_result_sets(
        [("rows", ["N"], [(i,) for i in range(80)])], max_rows=50, stats=stats,
    )
    assert stats["shown_rows"] == 50 and stats["truncated"] is True
    assert "(80 행 중 50행만 표시" in out


# ── Lever A: execute_sql 절단 안내문 epistemic 지침 ─────────────────────────


def _run_execute_sql_with(monkeypatch, rows):
    monkeypatch.setattr(T, "_raw_execute_sql", lambda conn, sql: ([("rows", ["c1", "c2"], rows)], 0.01))
    monkeypatch.setattr(T, "save_csv", lambda name, cols, rows_: f"/shared/out/{name}.csv")
    monkeypatch.setattr(T, "_apply_query_cap", lambda conn: None)
    monkeypatch.setattr(T, "_freeform_sql_access_error", lambda sql: None)
    return T._tool_execute_sql(object(), {"sql": "SELECT c1, c2 FROM `db`.`t`"})


def test_execute_sql_truncated_note_has_self_correction(monkeypatch):
    out = _run_execute_sql_with(monkeypatch, _rows(2000, wide=True))
    assert "미리보기" in out
    assert "보지 못했습니다" in out and "단정은 금지" in out
    assert "좁혀 재조회" in out
    assert "CSV 는 사용자 다운로드 전용" in out and "읽을 수 없습니다" in out
    # 기존 표시 계약(답변에 전체 표 삽입 금지 + CSV 링크 제공) 유지
    assert "답변에 전체 표를 삽입하지 말고" in out


def test_execute_sql_small_result_no_truncation_note(monkeypatch):
    out = _run_execute_sql_with(monkeypatch, _rows(183))
    assert "tbl_182" in out and "보지 못했습니다" not in out and "행만 표시" not in out


# ── Lever C: SYSTEM_PROMPT grounding 계약 ───────────────────────────────────
# NOTE: 애초 계획의 Lever D(@@ 거부→SHOW VARIABLES 힌트)는 병렬 세션의
# CHG-20260714T153113-sysvar-select-guard 가 MySQL `@@` denylist 를 아예 제거해
# `SELECT @@var` 가 통과하게 되면서 dead 경로가 되어 제거했다. 서버 옵션 실측 계약은
# 아래 SYSTEM_PROMPT 규칙(Lever C)이 담당한다(@@ or SHOW VARIABLES 로 실제 값 조회).


def test_system_prompt_has_partial_evidence_grounding_rules():
    p = agent_core.SYSTEM_PROMPT
    assert "PREVIEW-TRUNCATED" in p and "행 중 N행만 표시" in p
    assert "ABSENCE / COMPLETENESS" in p and "미확인" in p
    assert "COMPARING an attachment" in p and "describe_routine" in p
    # SERVER OPTIONS 실측 계약: @@ 는 이제 허용(sysvar-guard) — 문서 기본값 추측 금지 규칙 유지.
    assert "SERVER OPTIONS" in p and "read the actual value first" in p
    assert "documented defaults" in p
    # 기존 계약 보존(우발 삭제 방지)
    assert "NEVER FABRICATE" in p and "0 rows" in p


def test_server_variable_redirect_removed():
    # Lever D 제거 회귀 가드: dead 힌트 함수가 재도입되지 않도록.
    assert not hasattr(T, "_server_variable_redirect")
