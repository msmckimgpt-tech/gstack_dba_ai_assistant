"""feature-0003 attach-full-scope — 자가 적대 리뷰어의 첨부 근거 범위 회귀 테스트.

리뷰어의 구조적 실패 모드는 "evidence digest 에 없는 파일 = 답변이 지어낸 것" 이라는 오판이다
(첨부 리뷰마다 재발하던 honesty/grounding false positive). 참조 스코프가 대화 전체로 넓어지면
인라인 상한 밖 첨부가 늘어나므로, 본문이 없더라도 **파일의 존재 자체**는 리뷰어에게 보여야 한다.
"""
from __future__ import annotations

import agent_core
from modules import redteam


def test_digest_separates_body_and_manifest_only():
    out = redteam.build_attachment_digest([
        {"filename": "a.sql", "content": "SELECT 1;", "truncated": False, "content_available": True},
        {"filename": "b.csv", "content": "", "truncated": False, "content_available": False, "kind": "csv"},
    ])
    assert "a.sql" in out and "SELECT 1;" in out
    assert "ALSO ATTACHED" in out, "본문 미주입 첨부의 존재를 알리는 섹션 누락"
    assert "b.csv" in out and "(csv)" in out
    assert "read_attachment" in out, "리뷰어가 '읽을 수 있는 파일' 임을 알아야 오판을 피함"


def test_digest_without_manifest_only_has_no_extra_section():
    out = redteam.build_attachment_digest([
        {"filename": "a.sql", "content": "SELECT 1;", "truncated": False},
    ])
    assert "ALSO ATTACHED" not in out


def test_manifest_survives_budget_pressure():
    """발췌가 예산을 다 먹어도 매니페스트는 남는다 — 사라지면 그 자체가 false positive 원인."""
    big = [{"filename": f"big{i}.sql", "content": "X" * 4000, "truncated": True} for i in range(5)]
    manifest = [{"filename": "late.sql", "content": "", "content_available": False, "kind": "text"}]
    out = redteam.build_attachment_digest(big + manifest)
    assert len(out) <= redteam._ATTACH_TOTAL_CAP_CHARS
    assert "late.sql" in out, "예산 초과 시에도 매니페스트는 보존되어야 함"


def test_manifest_cannot_evict_tool_evidence_at_scale():
    """매니페스트가 예산을 통째로 선점해 도구 근거·발췌를 밀어내지 못한다.

    참조 스코프가 대화 전량(최대 200건)이라 본문 없는 첨부가 대량으로 실릴 수 있다. 선점에
    상한이 없으면 리뷰어가 **도구 실행 근거를 하나도 못 보는** 상태가 된다(적대 리뷰 backend/qa
    BLOCK — 실측 cap 2500 대비 7,329~20,641자).
    """
    many_manifest = [
        {"filename": f"attachment-with-a-fairly-long-name-{i:03d}.csv", "content": "",
         "content_available": False, "kind": "csv"}
        for i in range(200)
    ]
    body = [{"filename": "evidence.sql", "content": "SELECT 1;", "truncated": False}]
    out = redteam.build_attachment_digest(body + many_manifest)
    assert len(out) <= redteam._ATTACH_TOTAL_CAP_CHARS, "digest 총 상한 초과"
    manifest_share = out.split("ALSO ATTACHED")[-1]
    assert len(manifest_share) <= redteam._ATTACH_TOTAL_CAP_CHARS * (
        redteam._ATTACH_MANIFEST_BUDGET_RATIO + 0.1
    ), "매니페스트가 예산을 과점"
    assert "evidence.sql" in out and "SELECT 1;" in out, "본문 발췌가 매니페스트에 축출되면 안 됨"


def test_evidence_digest_stays_within_cap_with_large_manifest():
    """build_evidence_digest 전체(도구 digest + 첨부 블록)도 상한을 지킨다."""
    steps = [{"tool_name": "execute_sql", "args": {"sql": "SELECT 1"},
              "result_preview": "1", "result_length": 1}]
    attachments = [{"filename": f"f{i:03d}.csv", "content": "", "content_available": False,
                    "kind": "csv"} for i in range(200)]
    out = redteam.build_evidence_digest(steps, attachments=attachments)
    assert len(out) <= redteam._EVIDENCE_CAP_CHARS
    assert "execute_sql" in out, "도구 실행 근거가 첨부 매니페스트에 밀려나면 안 됨"


def test_empty_input_yields_empty_digest():
    assert redteam.build_attachment_digest([]) == ""
    assert redteam.build_attachment_digest(None) == ""


def test_reviewer_instructions_cover_on_demand_reads():
    """리뷰어에게 **실제로 전달되는 프롬프트**가 '발췌 부재 = 창작' 오판과 재첨부 요구를 금지한다.

    모듈 소스 전체를 훑는 폴백 검사는 주석에도 걸려 항상 통과하는 tautology 다(적대 리뷰 qa) —
    지시문이 실린 정확한 상수를 본다.
    """
    prompt = redteam.REDTEAM_REVIEW_PROMPT
    assert "ALSO ATTACHED" in prompt, "매니페스트 섹션 해석 지시가 리뷰어 프롬프트에 없음"
    assert "read_attachment" in prompt
    assert "re-attach" in prompt, "재첨부 요구 금지 지시 누락"


def test_review_attachments_includes_uninlined_manifest(monkeypatch):
    """인라인된 본문 + 인라인 안 된 첨부 매니페스트가 함께 리뷰어에게 전달된다."""
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda: {31: {"filename": "a.sql", "content": "SELECT 1;", "truncated": False}})
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [
        {"id": 31, "filename": "a.sql", "kind": "text", "object_key": "k/31", "status": "uploaded", "meta_json": None},
        {"id": 22, "filename": "b.csv", "kind": "csv", "object_key": "k/22", "status": "ingested", "meta_json": None},
    ])
    out = agent_core._review_attachments(False)
    by_name = {a["filename"]: a for a in out}
    assert by_name["a.sql"]["content"] == "SELECT 1;"
    assert by_name["a.sql"]["content_available"] is True
    assert by_name["b.csv"]["content"] == "" and by_name["b.csv"]["content_available"] is False
    assert by_name["b.csv"]["kind"] == "csv"


def test_review_attachments_suppressed_for_bounded_sender(monkeypatch):
    """공유창 window 로 가려진 발신자에게는 첨부 근거를 넘기지 않는다(누출 게이트 유지)."""
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda: {31: {"filename": "a.sql", "content": "SELECT 1;", "truncated": False}})
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [
        {"id": 22, "filename": "b.csv", "kind": "csv", "object_key": "k/22", "status": "ingested", "meta_json": None},
    ])
    assert agent_core._review_attachments(True) == []
