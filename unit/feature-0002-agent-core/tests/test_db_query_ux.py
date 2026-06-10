"""TASK: DB 조회 UX 개선 (db-query-ux-overhaul) 회귀 테스트.

대상 4건:
  FIX 1 — 스키마 grounding PG 전환 (_load_schema_list / _load_relevant_table_insights
          가 AGENT_KB_READ_BACKEND=postgres 시 PG 정본을 사용, 미가용 시 MySQL fallback)
  FIX 2 — system prompt 개편 (코드 상수 본문에 핵심 가드 문구가 존재하는지 sanity)
  FIX 3 — 멀티턴 맥락 보존 (_assemble_core_messages 의 user-turn 보존 +
          _is_low_information_request 인사/메타 origin 가드)
  FIX 4 — 첨부 리뷰 INSTRUCTION 우선순위 문구 sanity

라이브 DB 비의존 — 순수 함수 + monkeypatch dispatch 검증.
"""
import json
import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import agent_core  # noqa: E402
from modules import domain  # noqa: E402


# ── FIX 3b: _is_low_information_request ────────────────────────────────
def test_low_info_request_greetings_and_meta():
    assert domain._is_low_information_request("안녕하세요") is True
    assert domain._is_low_information_request("하이") is True
    assert domain._is_low_information_request("ㅎㅇ") is True
    assert domain._is_low_information_request("") is True
    assert domain._is_low_information_request("   ") is True


def test_low_info_request_data_work_is_not_low_info():
    # 데이터 작업 신호가 있으면 저정보 아님 (origin 으로 채택돼야 함)
    assert domain._is_low_information_request("dblog 로그인 통계 조회해줘") is False
    assert domain._is_low_information_request("이 쿼리 리뷰해줘") is False
    assert domain._is_low_information_request("회원 테이블 보여줘") is False
    assert domain._is_low_information_request("최근 한 달 매출 분석") is False


def test_low_info_request_short_korean_substantive_not_low_info():
    # [S1 회귀] 짧은 한국어/영문 실질 질문은 저정보가 아니어야 한다 (origin 보존).
    for q in ("매출?", "회원수", "주문 수", "DAU", "상품?", "가입자"):
        assert domain._is_low_information_request(q) is False, q


def test_low_info_request_meaningless_tokens_are_low_info():
    # 의미 토큰이 없는 발화(자모/문장부호/이모지)는 저정보.
    for q in ("ㅇㅇ", "ㅋㅋㅋ", "...", "!!!"):
        assert domain._is_low_information_request(q) is True, q


def test_should_refresh_origin_defers_low_info_first_message():
    # 빈 origin + 저정보 첫 발화 → continue(보류). 실질 발화 → shift.
    assert agent_core._should_refresh_origin_request("", "안녕하세요", None) == "continue"
    assert agent_core._should_refresh_origin_request("", "dblog 매출 통계 조회", None) == "shift"


# ── FIX 3a: _assemble_core_messages user-turn 보존 ─────────────────────
def _user_row(text):
    return {"role": "user", "content": text, "tool_calls": None,
            "tool_call_id": None, "name": None}


def _assistant_toolcall_row(call_id):
    tc = [{"id": call_id, "type": "function",
           "function": {"name": "execute_sql", "arguments": "{}"}}]
    return {"role": "assistant", "content": None,
            "tool_calls": json.dumps(tc), "tool_call_id": None, "name": None}


def _tool_row(call_id):
    return {"role": "tool", "content": "rows: ...", "tool_calls": None,
            "tool_call_id": call_id, "name": "execute_sql"}


def test_assemble_core_messages_preserves_early_user_intent():
    """tool 메시지가 윈도우를 점유해도 초기 user 의도가 보존되어야 한다."""
    rows = [_user_row("초기 제약: dblog 스키마만, 2024년 데이터")]
    for i in range(30):
        rows.append(_assistant_toolcall_row(f"call_{i}"))
        rows.append(_tool_row(f"call_{i}"))
    out = agent_core._assemble_core_messages(rows, max_messages=10)
    contents = [m.get("content") for m in out if m.get("content")]
    assert any("초기 제약" in c for c in contents), "초기 user 메시지가 유실됨"


def test_assemble_core_messages_no_orphan_tool_at_start():
    """윈도우 슬라이스로 짝 잃은 tool 메시지는 재정규화로 제거되어야 한다."""
    rows = [_user_row("의도")]
    for i in range(30):
        rows.append(_assistant_toolcall_row(f"call_{i}"))
        rows.append(_tool_row(f"call_{i}"))
    out = agent_core._assemble_core_messages(rows, max_messages=9)
    # tool 메시지는 직전에 동일 tool_call_id 의 assistant tool_calls 가 있어야 유효.
    open_ids = set()
    for m in out:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            open_ids |= {tc["id"] for tc in m["tool_calls"]}
        elif m.get("role") == "tool":
            assert m.get("tool_call_id") in open_ids, "orphan tool 메시지 발견"


def test_assemble_core_messages_under_budget_unchanged():
    rows = [_user_row("a"), _user_row("b")]
    out = agent_core._assemble_core_messages(rows, max_messages=10)
    assert [m["content"] for m in out] == ["a", "b"]


# ── FIX 1: PG dispatch (_load_schema_list / _load_relevant_table_insights) ──
def test_load_schema_list_uses_pg_when_backend_pg(monkeypatch):
    monkeypatch.setattr(agent_core, "_kb_read_is_pg", lambda: True)

    def fake_rows(like, with_text, tokens=None, limit=None, not_like_pattern=None):
        if like.startswith("table_insight"):
            return [("table_insight:dblog.a", None),
                    ("table_insight:dblog.b", None),
                    ("table_insight:dbgame.c", None)]
        return [("schema_insight:dblog", "dblog domain: Game Data / 전투 로그")]

    monkeypatch.setattr(agent_core, "_global_insight_rows_pg", fake_rows)
    # mem_conn=None 이어도 PG 경로로 동작해야 한다 (이전 버그: MySQL 없으면 "" 반환).
    out = agent_core._load_schema_list(None)
    assert "dblog (2 tables)" in out
    assert "dbgame (1 tables)" in out
    assert "Game Data" in out


def test_load_relevant_table_insights_uses_pg(monkeypatch):
    monkeypatch.setattr(agent_core, "_kb_read_is_pg", lambda: True)
    monkeypatch.setattr(
        agent_core, "_global_insight_rows_pg",
        lambda *a, **k: [("table_insight:dblog.login", "login events table")],
    )
    out = agent_core._load_relevant_table_insights(None, "login 통계")
    assert "dblog.login" in out
    assert "login events table" in out


def test_load_schema_list_falls_back_when_pg_unavailable(monkeypatch):
    # PG 미가용(None 반환) + mem_conn 없음 → 빈 문자열 (graceful).
    monkeypatch.setattr(agent_core, "_kb_read_is_pg", lambda: True)
    monkeypatch.setattr(agent_core, "_global_insight_rows_pg", lambda *a, **k: None)
    assert agent_core._load_schema_list(None) == ""


# ── FIX 1 helper: _extract_schema_desc ─────────────────────────────────
def test_extract_schema_desc_domain_format():
    raw = "dblog domain: Game Data / This schema tracks battle logs / extra"
    desc = agent_core._extract_schema_desc(raw)
    assert "Game Data" in desc
    assert "This schema tracks battle logs" in desc


def test_extract_schema_desc_legacy_format():
    raw = "전투 로그 / 부가 설명"
    desc = agent_core._extract_schema_desc(raw)
    assert "전투 로그" in desc


# ── FIX 2: system prompt 핵심 가드 문구 sanity ─────────────────────────
def test_system_prompt_has_anti_hallucination_and_verify_guards():
    p = agent_core.SYSTEM_PROMPT
    assert "Never invent table or column names" in p
    assert "search_tables" in p and "describe_table" in p
    # 0-rows 환각 가드
    assert "0 rows" in p
    # 첨부 리뷰 분기
    assert "ATTACHED FILE CONTENTS" in p or "ATTACHED FILES" in p
    # 사고 확장 / 되묻기
    assert "ambiguous" in p
    # 과거의 "answer the user's question with data, not to explore" 안티-탐색 프레이밍 제거 확인
    assert "not to explore" not in p
