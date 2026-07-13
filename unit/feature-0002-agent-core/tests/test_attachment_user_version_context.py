"""REQ-20260713-attach-user-version: 사용자 재업로드로 버전이 오른 첨부를 LLM 컨텍스트에서
assistant 가 인지하는지 검증.

`_build_attachment_context_section` 이:
  - version_number>1 인 첨부에 갱신 표식(🔄vN)을 붙인다(사용자 재업로드 / AI 수정 구분).
  - MetaJson.version_diff 가 있으면 `## FILE UPDATES` 섹션에 이전 버전 대비 unified diff 를
    datamark(비신뢰 구획)로 주입한다 → assistant 가 "무엇이 바뀌었는지" 인지.
  - v1(원본)에는 표식/FILE UPDATES 를 주입하지 않는다(회귀 방지 — 기존 단일 첨부 무영향).

`make test`(agent 이미지) 에서 DB 없이 fake conn 으로 실행.

MySQL SELECT 컬럼 순서(REQ-20260713 append 후):
  0 Id, 1 ConversationId, 2 OriginalFilename, 3 Kind, 4 MimeType, 5 SizeBytes,
  6 SizeBucket, 7 UploadStatus, 8 MetaJson, 9 RootAttachmentId, 10 VersionNumber, 11 CreatedByRole
"""
from __future__ import annotations

import json

import agent_core


class _CaptureConn:
    """execute(sql, params) 를 무시하고 미리 준 rows 를 fetchall 로 돌려주는 fake conn."""

    def __init__(self, rows):
        self._rows = rows

    def cursor(self, *a, **k):
        rows = self._rows

        class _Cur:
            def execute(self, sql, params=None):
                pass

            def fetchall(self):
                return rows

            def close(self):
                pass

        return _Cur()


def _row(*, meta=None, root=None, version=1, role="user", fname="report.sql", kind="text"):
    return (
        101, "conv-x", fname, kind, "text/plain", 100, "small", "uploaded",
        json.dumps(meta) if meta is not None else "{}",
        root, version, role,
    )


def test_user_version_label_and_diff_injected(monkeypatch):
    # diff 는 이번 턴 신규 첨부(NEW_ATTACHMENT_IDS)에만 주입된다(NIT gate).
    monkeypatch.setenv("NEW_ATTACHMENT_IDS", "101")
    vd = {"from_version": 1, "to_version": 2,
          "unified_diff": "--- report.sql (v1)\n+++ report.sql (v2)\n@@ -1 +1 @@\n-old_line\n+new_line",
          "truncated": False}
    row = _row(meta={"version_diff": vd}, root=100, version=2, role="user")
    out = agent_core._build_attachment_context_section(
        _CaptureConn([row]), [101], conversation_id="conv-x")
    # 파일 목록 라인의 버전 표식.
    assert "🔄v2" in out, "버전 표식(🔄v2) 누락"
    assert "사용자가 재업로드해 갱신" in out, "사용자 재업로드 표식 문구 누락"
    # FILE UPDATES 섹션 + diff 본문.
    assert "FILE UPDATES" in out, "FILE UPDATES 섹션 누락"
    assert "report.sql: v1 → v2" in out, "버전 전이 헤더 누락"
    assert "-old_line" in out and "+new_line" in out, "diff 본문 누락"


def test_v1_original_no_version_label():
    """단일 첨부(v1, root=NULL)에는 표식/FILE UPDATES 를 주입하지 않음(기존 동작 무회귀)."""
    row = _row(meta={}, root=None, version=1, role="user", fname="plain.sql")
    out = agent_core._build_attachment_context_section(
        _CaptureConn([row]), [101], conversation_id="conv-x")
    assert "🔄" not in out
    assert "FILE UPDATES" not in out


def test_assistant_version_label_distinct():
    """assistant 수정본(role='assistant')과 사용자 재업로드를 표식 문구로 구분."""
    row = _row(meta={}, root=50, version=3, role="assistant", fname="q.sql")
    out = agent_core._build_attachment_context_section(
        _CaptureConn([row]), [101], conversation_id="conv-x")
    assert "🔄v3" in out
    assert "AI 수정본" in out


def test_version_diff_datamarked(monkeypatch):
    """diff 본문은 비신뢰 → datamark sentinel 로 구획(인젝션 방어)."""
    monkeypatch.setenv("NEW_ATTACHMENT_IDS", "101")
    vd = {"from_version": 1, "to_version": 2, "unified_diff": "@@ -1 +1 @@\n-a\n+b", "truncated": False}
    row = _row(meta={"version_diff": vd}, root=100, version=2, role="user")
    out = agent_core._build_attachment_context_section(
        _CaptureConn([row]), [101], conversation_id="conv-x")
    # _datamark_untrusted 의 sentinel(_INJ_OPEN/_INJ_CLOSE)이 diff 를 감싸야 한다.
    assert agent_core._INJ_OPEN in out and agent_core._INJ_CLOSE in out


def test_truncated_diff_marked_in_context(monkeypatch):
    monkeypatch.setenv("NEW_ATTACHMENT_IDS", "101")
    vd = {"from_version": 2, "to_version": 3, "unified_diff": "@@ trimmed @@", "truncated": True}
    row = _row(meta={"version_diff": vd}, root=100, version=3, role="user")
    out = agent_core._build_attachment_context_section(
        _CaptureConn([row]), [101], conversation_id="conv-x")
    assert "[truncated]" in out


def test_diff_not_injected_for_session_attachment(monkeypatch):
    """이전 턴 버전(◆세션, NEW_ATTACHMENT_IDS 미포함)은 diff 를 재주입하지 않는다(NIT gate).
    단 🔄 버전 표식은 매 턴 유지되어 assistant 가 버전>1 을 계속 인지한다."""
    monkeypatch.delenv("NEW_ATTACHMENT_IDS", raising=False)
    vd = {"from_version": 1, "to_version": 2, "unified_diff": "@@ -1 +1 @@\n-a\n+b", "truncated": False}
    row = _row(meta={"version_diff": vd}, root=100, version=2, role="user")
    out = agent_core._build_attachment_context_section(
        _CaptureConn([row]), [101], conversation_id="conv-x")
    assert "FILE UPDATES" not in out, "세션(비-신규) 첨부는 diff 재주입 안 함"
    assert "🔄v2" in out, "버전 표식은 매 턴 유지"
