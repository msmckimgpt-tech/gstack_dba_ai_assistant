"""TASK-0132 (#8): 첨부 IDOR 회귀 테스트.

`_build_attachment_context_section` 이 account_id 를 요구하고(fail-closed) 쿼리를 AccountId 로
스코프하는지 검증한다. 이전엔 ATTACHMENT_IDS(os.environ, 요청 제어) 를 Id IN(...) 만으로
조회해 타 계정 첨부 메타가 prompt 에 유출됐고, os.environ 동시요청 race 까지 겹쳤다.
"""
from __future__ import annotations

import agent_core


def test_attachment_context_requires_account_id():
    """account_id 없으면 fail-closed (빈 섹션) — 무계정 컨텍스트에서 첨부 노출 금지."""
    assert agent_core._build_attachment_context_section(object(), [1, 2], account_id=None) == ""
    # mem_conn None 도 빈 섹션
    assert agent_core._build_attachment_context_section(None, [1, 2], account_id=7) == ""
    # attachment_ids 비면 빈 섹션
    assert agent_core._build_attachment_context_section(object(), [], account_id=7) == ""


def test_attachment_context_scopes_by_account():
    """account_id 주어지면 쿼리가 AccountId = %s 로 스코프되고 params 에 account_id 포함."""
    captured: dict = {}

    class FakeCur:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCur()

    agent_core._build_attachment_context_section(FakeConn(), [101, 202], account_id=7)
    assert "AccountId = %s" in captured["sql"], "쿼리에 AccountId 스코프 누락 (IDOR 회귀)"
    assert 7 in tuple(captured["params"]), "params 에 account_id 누락"
    # 타 계정 id(99) 로는 동일 attachment_ids 라도 account_id 가 99 로 들어가 row 0 (DB 레벨 차단)
    agent_core._build_attachment_context_section(FakeConn(), [101, 202], account_id=99)
    assert 99 in tuple(captured["params"]) and 7 not in tuple(captured["params"])


# ── TASK-0284: 주입 스코프를 AccountId → ConversationId 로 통일 (account 폴백 보존) ──


class _CaptureConn:
    """execute(sql, params) 를 captured 에 기록하고 빈 결과를 주는 fake conn."""

    def __init__(self, captured: dict, rows=None):
        self._captured = captured
        self._rows = rows or []

    def cursor(self):
        captured = self._captured
        rows = self._rows

        class _Cur:
            def execute(self, sql, params=None):
                captured["sql"] = sql
                captured["params"] = params

            def fetchall(self):
                return rows

            def close(self):
                pass

        return _Cur()


def test_attachment_context_scopes_by_conversation():
    """conversation_id 주어지면 ConversationId 로 스코프되고 account_id 는 WHERE 에 안 들어간다.

    fork·이어받기 등 cross-account 시나리오에서 '대화에 속한 첨부'를 주입하기 위함. 대화 접근권은
    caller(app.py ask)가 게이트하므로, 본 함수는 대화 단위 스코프로 충분하다(타 대화 첨부 id 주입은
    ConversationId 불일치로 차단 — IDOR 안전망 유지)."""
    captured: dict = {}
    agent_core._build_attachment_context_section(
        _CaptureConn(captured), [101, 202], account_id=7, conversation_id="conv-abc"
    )
    assert "ConversationId = %s" in captured["sql"], "ConversationId 스코프 누락"
    assert "AccountId = %s" not in captured["sql"], "conversation 스코프 시 account 필터가 남으면 cross-account 차단됨"
    assert "conv-abc" in tuple(captured["params"]) and 7 not in tuple(captured["params"])

    # account_id 없이 conversation_id 만으로도 스코프(쿼리 실행) — 빈 섹션 폴백 아님
    captured.clear()
    agent_core._build_attachment_context_section(_CaptureConn(captured), [101], conversation_id="conv-x")
    assert "ConversationId = %s" in captured["sql"]
    assert "conv-x" in tuple(captured["params"])


def test_attachment_context_account_fallback_without_conversation():
    """conversation_id 미전달(legacy)이면 AccountId 폴백 유지 — 하위호환 + 무계정 fail-closed."""
    captured: dict = {}
    agent_core._build_attachment_context_section(_CaptureConn(captured), [101], account_id=7)
    assert "AccountId = %s" in captured["sql"] and 7 in tuple(captured["params"])
    # conversation_id / account_id 둘 다 없으면 빈 섹션(fail-closed)
    assert agent_core._build_attachment_context_section(object(), [101]) == ""


def test_attachment_listing_names_file_before_id():
    """TASK-0284(이슈3): 첨부 목록 라인이 파일명을 attachment_id 보다 앞에 노출 + 파일명 지칭 지침 포함."""
    # MySQL SELECT 컬럼 순서: (Id, ConversationId, OriginalFilename, Kind, MimeType, SizeBytes, SizeBucket, UploadStatus, MetaJson)
    row = (101, "conv-x", "report.csv", "other", "text/csv", 1234, "small", "uploaded", "{}")
    captured: dict = {}
    out = agent_core._build_attachment_context_section(
        _CaptureConn(captured, rows=[row]), [101], conversation_id="conv-x"
    )
    assert 'file "report.csv"' in out, "파일명이 따옴표로 노출되어야 함"
    listing = [ln for ln in out.splitlines() if "report.csv" in ln and "attachment_id=" in ln]
    assert listing, "첨부 목록 라인 누락"
    ln = listing[0]
    assert ln.index('file "report.csv"') < ln.index("attachment_id="), "파일명이 attachment_id 보다 앞이어야 함"
    assert "REFER TO ATTACHMENTS BY FILENAME" in out, "파일명 지칭 지침 누락"
