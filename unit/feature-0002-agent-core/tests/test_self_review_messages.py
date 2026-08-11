"""feature-0021 red-team revise/rederive 재프롬프트 메시지 조립 회귀.

근본 원인(라이브 추적, 2026-07-24): 수정 지시를 초안(assistant) 뒤에 role=system 으로
붙이면 LiteLLM/Anthropic 어댑터가 그 system 을 top-level system 파라미터로 hoist →
초안 assistant 가 배열의 마지막 turn = **prefill** 이 되어 모델이 재작성 대신 초안을
이어쓴다. 완결된 초안은 이어쓸 게 없어 ~빈 응답(라이브 completion_tokens=3)을 내고,
호출부가 None→fail-open 으로 **미수정 초안을 그대로 전달**한다(revise verdict 42건 중 35건
revision_applied=false 관측). 지시를 trailing user turn 으로 두면 정상 재작성된다.

이 테스트는 `_build_self_review_messages` 가 (a) 지시를 **role=user** 로, (b) 배열의
**마지막 turn** 으로 두고, (c) 초안을 그 앞의 assistant turn(=prefill 아님)으로 두는
불변식을 고정한다 — role=system 회귀 재발을 결정적으로 차단.
"""
from __future__ import annotations

import agent_core


def _base():
    return [
        {"role": "system", "content": "제품 시스템 프롬프트"},
        {"role": "user", "content": "TF_Raw_JSON 분석해줘"},
        {"role": "tool", "content": "도구 결과", "tool_call_id": "t1"},
    ]


def test_instruction_is_trailing_user_turn():
    base = _base()
    out = agent_core._build_self_review_messages(base, "초안 답변 전문", "수정 지시")
    # 지시는 배열의 마지막 turn 이고 role=user 여야 한다 (prefill 방지의 핵심).
    assert out[-1] == {"role": "user", "content": "수정 지시"}
    # 초안은 그 바로 앞의 assistant turn — user 지시가 뒤따르므로 prefill 이 아니다.
    assert out[-2] == {"role": "assistant", "content": "초안 답변 전문"}


def test_no_trailing_system_message():
    # 회귀 가드: 지시가 role=system 으로 새어들면 안 된다 (hoist→prefill 재발).
    out = agent_core._build_self_review_messages(_base(), "draft", "instr")
    assert out[-1]["role"] != "system"
    # 지시 텍스트가 system role 로 실린 메시지가 하나도 없어야 한다.
    assert not any(m.get("role") == "system" and m.get("content") == "instr" for m in out)


def test_base_messages_preserved_and_not_mutated():
    base = _base()
    base_snapshot = [dict(m) for m in base]
    out = agent_core._build_self_review_messages(base, "draft", "instr")
    # 원본 base 를 in-place 로 변형하지 않는다(closure 재호출 안전 — revise 루프 다회).
    assert base == base_snapshot
    # base 전체가 순서대로 앞에 보존된다.
    assert out[: len(base)] == base
    assert len(out) == len(base) + 2


# ── answer-origin-realign: 대화 목표 보조 앵커의 누출 게이트 (2026-07-28) ────
# thread_goal/origin_request 는 대화의 (가려졌을 수 있는) 첫 요청에서 파생된 자유 텍스트라
# message id 에 묶이지 않아 공유창 visibility window 로 자를 수 없다. bounded 발신자에게
# 주입하면 수정 지시가 가려진 구간 요약을 그 발신자의 생성 컨텍스트로 실어나른다.

def test_realign_thread_goal_suppressed_for_bounded_sender():
    assert agent_core._realign_thread_goal("이 대화의 목표", True) == ""


def test_realign_thread_goal_passthrough_for_unbounded_sender():
    assert agent_core._realign_thread_goal("이 대화의 목표", False) == "이 대화의 목표"


def test_realign_thread_goal_normalizes_empty():
    assert agent_core._realign_thread_goal(None, False) == ""
    assert agent_core._realign_thread_goal("", False) == ""


# ── 2026-07-29 회귀 교정: 리뷰어·수정 지시에 줄 '대화 실질 요청' 과 첨부 근거 ──
# 다중 턴에서 현재 발화("네 맞습니다.")만 넘기면 리뷰어가 실질 답변을 "묻지도 않은 걸 답했다"
# 로 오판하고, 그 오판이 수정 루프를 통해 답변을 붕괴시킨다(라이브 run #132).

def test_conversation_request_prefers_origin_over_latest_utterance():
    got = agent_core._review_conversation_request(
        "쿼리 리뷰를 진행해주세요.", "쿼리 리뷰", "네 맞습니다.", False)
    assert got == "쿼리 리뷰를 진행해주세요."


def test_conversation_request_falls_back_to_goal_then_utterance():
    assert agent_core._review_conversation_request("", "쿼리 리뷰", "네", False) == "쿼리 리뷰"
    assert agent_core._review_conversation_request("", "", "월별 매출", False) == "월별 매출"
    assert agent_core._review_conversation_request("", "", "", False) == ""


def test_conversation_request_suppressed_for_bounded_sender():
    """origin/thread_goal 은 가려진 첫 요청 파생 — bounded 발신자에겐 주지 않는다(누출 게이트)."""
    assert agent_core._review_conversation_request("첫 요청", "목표", "네", True) == ""


def test_review_attachments_suppressed_for_bounded_sender(monkeypatch):
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda: {1: {"filename": "a.sql", "content": "SELECT 1"}})
    assert agent_core._review_attachments(True) == []


def test_review_attachments_maps_inline_texts(monkeypatch):
    # feature-0003 attach-full-scope: 인라인 본문 항목에 content_available=True 가 붙는다
    # (본문 없는 매니페스트 항목과 구분 — build_attachment_digest 가 두 섹션으로 나눈다).
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda: {1: {"filename": "a.sql", "content": "SELECT 1", "truncated": True},
                                 2: {"filename": "empty.sql", "content": "   "}})
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [])
    got = agent_core._review_attachments(False)
    assert got == [{"filename": "a.sql", "content": "SELECT 1", "truncated": True,
                    "content_available": True}]


def test_review_attachments_fail_open_on_loader_error(monkeypatch):
    def boom():
        raise RuntimeError("no inline path")

    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", boom)
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [])
    assert agent_core._review_attachments(False) == []


def test_review_attachments_still_lists_files_when_inline_loader_fails(monkeypatch):
    """인라인 로더가 죽어도 첨부의 **존재**는 리뷰어에게 전달된다 (feature-0003 attach-full-scope).

    본문이 없다고 파일을 목록에서 지우면, 그 파일을 논한 답변이 다시 '창작'으로 오판된다.
    """
    def boom():
        raise RuntimeError("no inline path")

    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", boom)
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [
        {"id": 9, "filename": "late.csv", "kind": "csv", "object_key": "k/9",
         "status": "ingested", "meta_json": None},
    ])
    got = agent_core._review_attachments(False)
    assert got == [{"filename": "late.csv", "content": "", "truncated": False,
                    "content_available": False, "kind": "csv"}]


# ── FR-redteam-digest-lacks-prior-attachment-version (라이브 실측 2026-08-11) ──
# 답변 모델은 프롬프트 `## FILE UPDATES` 로 v(n-1)→v(n) unified diff 를 받는데 리뷰어 digest 에는
# 없어서, "무엇이 바뀌었나" 에 정확히 답해도 무근거로 보여 grounding BLOCK 이 났다.
# **판정식은 프롬프트 렌더와 동일**해야 한다 — 이번 턴 신규(new_ids) + unified_diff 비어있지 않음.

_VD_ROW = {"id": 7, "filename": "a.sql", "kind": "text", "object_key": "k", "status": "ok",
           "meta_json": {"version_diff": {"from_version": 1, "to_version": 2,
                                          "unified_diff": "@@ -1 +1,2 @@\n+added\n",
                                          "truncated": False}}}


def _inline_one(monkeypatch, rows, new_ids="7"):
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda: {7: {"filename": "a.sql", "content": "SELECT 1"}})
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: rows)
    monkeypatch.setattr(agent_core, "_load_new_attachment_ids",
                        lambda: {int(x) for x in new_ids.split(",") if x.strip()})


def test_review_attachments_carries_version_diff_for_this_turn_upload(monkeypatch):
    _inline_one(monkeypatch, [_VD_ROW])
    got = agent_core._review_attachments(False)
    assert got[0]["version_diff"]["unified_diff"] == "@@ -1 +1,2 @@\n+added\n"
    assert got[0]["version_diff"]["from_version"] == 1
    assert got[0]["version_diff"]["to_version"] == 2


def test_review_attachments_omits_version_diff_when_not_new_this_turn(monkeypatch):
    """프롬프트 렌더가 이번 턴 신규에만 diff 를 싣는다 — 두 소비자가 같은 집합을 말해야 한다."""
    _inline_one(monkeypatch, [_VD_ROW], new_ids="")
    assert "version_diff" not in agent_core._review_attachments(False)[0]


def test_review_attachments_parses_meta_json_string(monkeypatch):
    """meta_json 이 문자열로 오는 경로(드라이버 차이)도 같은 사실을 내야 한다."""
    import json as _json
    row = dict(_VD_ROW, meta_json=_json.dumps(_VD_ROW["meta_json"]))
    _inline_one(monkeypatch, [row])
    assert agent_core._review_attachments(False)[0]["version_diff"]["to_version"] == 2


def test_review_attachments_ignores_empty_version_diff(monkeypatch):
    row = dict(_VD_ROW, meta_json={"version_diff": {"unified_diff": "   "}})
    _inline_one(monkeypatch, [row])
    assert "version_diff" not in agent_core._review_attachments(False)[0]


def test_review_attachments_version_diff_failure_is_fail_open(monkeypatch):
    def boom():
        raise RuntimeError("rows unavailable")
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda: {7: {"filename": "a.sql", "content": "SELECT 1"}})
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", boom)
    monkeypatch.setattr(agent_core, "_load_new_attachment_ids", lambda: {7})
    got = agent_core._review_attachments(False)
    assert got and got[0]["filename"] == "a.sql"   # 본문은 여전히 실린다
