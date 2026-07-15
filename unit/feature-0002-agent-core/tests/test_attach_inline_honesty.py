"""① text-inline 회귀 + ② cap-note 정직화 (TASK-attach-inline-honesty).

배경(실데이터 감사):
  ① text kind 첨부(.sql 등)는 sandbox ingest 대상이 아니라 raw content 를 프롬프트에 **직접 인라인**
     해야 한다(TASK-0124). 과거 마찰(2026-05 다수 대화)은 text SQL 을 "sandbox ingest 대기/실패"로
     오인해 내용을 못 읽고 "붙여넣어 달라"고 했다. 이 경로를 직접 검증하는 회귀 테스트가 부재했다.
  ② 인라인 개수/크기 상한을 넘겨 map 에 없는 text 파일에 붙던 노트 "(content unavailable — check MinIO
     connectivity)" 는 원인을 **오귀속**해 모델이 인프라(MinIO) 장애를 fabrication 하게 했다(관측 대화
     20260615061233·FRICTION_LEDGER text-inline count cap). 정직한 노트로 교체.

`make test`(agent 이미지)에서 DB 없이 fake conn + `_load_attachment_inline_texts` monkeypatch 로 실행.
컬럼 순서: 0 Id,1 ConversationId,2 OriginalFilename,3 Kind,4 MimeType,5 SizeBytes,6 SizeBucket,
7 UploadStatus,8 MetaJson,9 RootAttachmentId,10 VersionNumber,11 CreatedByRole.
"""
from __future__ import annotations

import json

import agent_core


class _CaptureConn:
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


def _row(*, fname="proc.sql", kind="text", att_id=101, meta=None):
    return (
        att_id, "conv-x", fname, kind, "text/plain", 100, "small", "uploaded",
        json.dumps(meta) if meta is not None else "{}",
        None, 1, "user",
    )


# ── ① text content 인라인 회귀 (sandbox 오라우팅 방지) ─────────────────────────────
def test_text_attachment_content_is_inlined_not_sandbox(monkeypatch):
    # text kind 는 content 를 인라인 map 에서 직접 주입 — sandbox 경로로 새지 않는다.
    monkeypatch.setattr(
        agent_core, "_load_attachment_inline_texts",
        lambda: {101: {"content": "CREATE PROCEDURE Foo() BEGIN\n  SELECT 1;\nEND", "truncated": False}},
    )
    out = agent_core._build_attachment_context_section(
        _CaptureConn([_row(fname="Foo.sql")]), [101], conversation_id="conv-x")
    # 인라인 본문 섹션 + 실제 content 가 프롬프트에 들어간다.
    assert "ATTACHED FILE CONTENTS" in out, "text content 인라인 섹션 누락 — sandbox 로 오라우팅?"
    assert "CREATE PROCEDURE Foo()" in out, "text 파일 실제 content 미주입"
    assert "Foo.sql" in out
    # text 는 sandbox 스키마/샘플 경로로 가지 않는다(이 첨부에 한해).
    assert "SANDBOX SCHEMA" not in out, "text 첨부가 sandbox 경로로 새면 안 됨"
    # '내용 없음/붙여넣기' 류 거절 문구가 나오지 않는다.
    assert "content unavailable" not in out
    assert "content not inlined" not in out


def test_text_inline_records_content_len(monkeypatch):
    monkeypatch.setattr(
        agent_core, "_load_attachment_inline_texts",
        lambda: {101: {"content": "SELECT 42;", "truncated": False}},
    )
    out = agent_core._build_attachment_context_section(
        _CaptureConn([_row(fname="q.sql")]), [101], conversation_id="conv-x")
    assert "content_len=10" in out  # len("SELECT 42;")==10


# ── ② cap-note 정직화 (MinIO 오귀속 제거) ──────────────────────────────────────
def test_absent_inline_note_len0_does_not_falsely_blame_minio(monkeypatch):
    # 인라인 0개(map 빈) — 인프라 실패 가능성 最高. 옛 "check MinIO connectivity" 오귀속 제거 + 원인 미단정.
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts", lambda: {})
    out = agent_core._build_attachment_context_section(
        _CaptureConn([_row(fname="big.sql")]), [101], conversation_id="conv-x")
    assert "check MinIO connectivity" not in out, "MinIO 오귀속 문구 잔존 — fabrication 유발"
    assert "content not inlined" in out
    # 원인 미단정 + **진짜 회복 경로(재첨부)** — 존재하지 않는 "파일명 지정 우선순위" 아님(적대 패널 정정).
    assert "the cause is not confirmed" in out
    assert "Do NOT assert a specific cause" in out
    assert "re-attach" in out


def test_absent_inline_note_len_positive_honest_no_size_cap_no_minio(monkeypatch):
    # 상한 내 일부 인라인(len>0) — 인라인된 수 정직 보고 + MinIO/system 단정 회피 + 재첨부 회복.
    monkeypatch.setattr(
        agent_core, "_load_attachment_inline_texts",
        lambda: {201: {"content": "A", "truncated": False}, 202: {"content": "B", "truncated": False}},
    )
    out = agent_core._build_attachment_context_section(
        _CaptureConn([_row(att_id=101, fname="third.sql")]), [101], conversation_id="conv-x")
    assert "currently 2 loaded" in out            # 인라인된 수 정직 보고(cap·recency 단정 아님)
    assert "Do NOT claim a specific MinIO/system failure" in out
    assert "re-attach" in out                     # 진짜 회복 경로
    assert "check MinIO connectivity" not in out
    # 부재 원인으로 "size cap" 을 단정하지 않는다(크기초과는 truncate 되어 인라인됨 — 부재 원인 아님).
    assert "size cap" not in out
