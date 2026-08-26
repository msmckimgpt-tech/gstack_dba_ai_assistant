"""FR-unknown-owner-attachment-trusted-by-provenance-gate + FR-failed-attachment-edit-silently-stripped.

conversation_audit(2026-08-26) §18.8 codex 확인 라운드가 적발한 **선재** 결함 2건의 봉인 검증.

1. **소유 미상 첨부가 신뢰됐다.** 본문이 맥락에 들어가는 세 지점(목록 렌더 · 온디맨드
   `read_attachment` · 이미지)이 각자 ``owner and caller and owner != caller`` 를 써서,
   ``AccountId`` 가 NULL/0 이면 조건이 성립하지 않아 신호가 서지 않았다 — 확인 불가를 **신뢰**로
   처리한 것이다(방향이 반대). 판정을 `mark_untrusted_attachment_body` 정본으로 통일한다.
   과차단 방지 축도 함께 고정한다: ① 호출자 신원이 없으면 아무것도 단정하지 않는다
   ② csv/xlsx 는 sandbox 샘플이 **실제로 렌더될 때만** 신호를 세운다(메타 없는 첨부로 쓰기 도구가
   막히면 안 된다).
2. **차단 사유가 사실과 달랐다.** 소유 미상인데 "다른 멤버가 올린" 이라고 단정해, 모델이 그 문장을
   사용자에게 그대로 전달했다.
"""
from __future__ import annotations

import json
from datetime import datetime

import agent_core
import modules.tools as tools


class _RowsConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, *a, **k):
        rows = self._rows

        class _Cur:
            def execute(self, sql, params=None):
                self._sql = sql

            def fetchall(self):
                _q = getattr(self, "_sql", "")
                # sandbox 샘플이 **실제로 렌더되는** 조건을 재현한다 — 컬럼과 샘플 행이 모두
                # 나와야 셀 값이 프롬프트에 들어가고, 그때만 provenance 신호가 서는 것이 계약이다.
                if "information_schema" in _q:
                    return [("c1", "varchar(10)")]
                if _q.strip().upper().startswith("SELECT * FROM"):
                    return [("cell-value",)]
                return rows

            def close(self):
                pass

        return _Cur()


def _row(aid, fname, *, kind="text", uploader=50, meta=None):
    return (aid, "conv-x", fname, kind, "text/plain", 100, "small", "uploaded",
            json.dumps(meta or {}), None, 1, "user", uploader,
            datetime.strptime("2026-08-13 18:20", "%Y-%m-%d %H:%M"))


def _build(rows, ids, monkeypatch, *, account_id=10):
    monkeypatch.setenv("ATTACHMENT_IDS", ",".join(str(i) for i in ids))
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: None)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._UNTRUSTED_ATTACH_BODY_REASON_CTX.set("")
    return agent_core._build_attachment_context_section(_RowsConn(rows), ids, account_id, "conv-x")


# ── 판정 정본 ────────────────────────────────────────────────────────────────

def test_mark_helper_flags_unknown_owner():
    """확인 불가는 신뢰가 아니다 — 소유 미상도 신호를 세운다."""
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._UNTRUSTED_ATTACH_BODY_REASON_CTX.set("")
    assert agent_core.mark_untrusted_attachment_body(0, 10) is True
    assert agent_core.untrusted_attachment_body_in_context() is True
    assert agent_core.untrusted_attachment_body_reason() == "owner-unverified"


def test_mark_helper_flags_known_other_owner_with_specific_reason():
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._UNTRUSTED_ATTACH_BODY_REASON_CTX.set("")
    assert agent_core.mark_untrusted_attachment_body(99, 10) is True
    assert agent_core.untrusted_attachment_body_reason() == "other-member"


def test_mark_helper_is_silent_for_own_and_for_unknown_caller():
    """과차단 방지 2축 — 내 것이면 안 세우고, 호출자를 모르면 아무것도 단정하지 않는다."""
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    assert agent_core.mark_untrusted_attachment_body(10, 10) is False
    assert agent_core.mark_untrusted_attachment_body(99, 0) is False
    assert agent_core.untrusted_attachment_body_in_context() is False


def test_specific_reason_is_not_downgraded():
    """타 멤버(구체) 사유가 이미 섰으면 소유 미상이 그것을 덮지 않는다."""
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._UNTRUSTED_ATTACH_BODY_REASON_CTX.set("")
    agent_core.mark_untrusted_attachment_body(99, 10)
    agent_core.mark_untrusted_attachment_body(0, 10)
    assert agent_core.untrusted_attachment_body_reason() == "other-member"


# ── 목록 렌더 경로: 본문이 실제로 실릴 때만 ──────────────────────────────────

def test_unknown_owner_text_body_raises_signal(monkeypatch):
    """소유 미상 **텍스트 본문**이 프롬프트에 실리면 신호가 선다."""
    monkeypatch.setattr(agent_core, "_load_attachment_inline_texts",
                        lambda *a, **k: {70: {"content": "SELECT 1;", "truncated": False}})
    _build([_row(70, "x.sql", uploader=0)], [70], monkeypatch, account_id=10)
    assert agent_core.untrusted_attachment_body_in_context() is True


def test_unknown_owner_csv_without_sandbox_does_not_overblock(monkeypatch):
    """csv 인데 sandbox 메타가 없으면 샘플이 안 실린다 — 신호를 세우면 과차단이다."""
    _build([_row(71, "d.csv", kind="csv", uploader=0)], [71], monkeypatch, account_id=10)
    assert agent_core.untrusted_attachment_body_in_context() is False


def test_unknown_owner_csv_with_sandbox_raises_signal(monkeypatch):
    """샘플 셀이 **실제로 프롬프트에 들어가는** csv 는 신호를 세운다."""
    meta = {"sandbox_schema_name": "sbx", "sandbox_table_name": "t1", "rows_inserted": 3}
    _build([_row(72, "d.csv", kind="csv", uploader=0, meta=meta)], [72], monkeypatch, account_id=10)
    assert agent_core.untrusted_attachment_body_in_context() is True


def test_own_csv_with_sandbox_stays_open(monkeypatch):
    """무회귀 — 내 파일은 sandbox 가 실려도 신호를 세우지 않는다."""
    meta = {"sandbox_schema_name": "sbx", "sandbox_table_name": "t1", "rows_inserted": 3}
    _build([_row(73, "d.csv", kind="csv", uploader=10, meta=meta)], [73], monkeypatch, account_id=10)
    assert agent_core.untrusted_attachment_body_in_context() is False


# ── 차단 사유 문구 ───────────────────────────────────────────────────────────

def test_block_message_says_unverified_not_other_member(monkeypatch):
    """소유 미상에 '다른 멤버가 올린' 이라고 단정하면 사용자에게 사실과 다른 설명이 나간다."""
    monkeypatch.setattr(agent_core, "untrusted_attachment_body_in_context", lambda: True)
    monkeypatch.setattr(agent_core, "untrusted_attachment_body_reason", lambda: "owner-unverified")
    msg = tools._provenance_gate("scratch_sql")
    assert "소유자를 확인하지 못한 첨부 파일의 본문" in msg
    assert "다른 멤버가 올린" not in msg


def test_block_message_keeps_specific_wording_for_other_member(monkeypatch):
    monkeypatch.setattr(agent_core, "untrusted_attachment_body_in_context", lambda: True)
    monkeypatch.setattr(agent_core, "untrusted_attachment_body_reason", lambda: "other-member")
    msg = tools._provenance_gate("scratch_sql")
    assert "다른 멤버가 올린 첨부 파일의 본문" in msg


def test_sandbox_meta_without_renderable_columns_does_not_overblock(monkeypatch):
    """메타는 있는데 컬럼 조회가 비면 샘플이 안 실린다 — 등록 시점에 세우면 과차단이다.

    §18.8 codex 라운드 6 [P2]: "메타 등록 = 본문 있음" 이 아니다. 컬럼 조회 실패·빈 테이블이면
    셀 값이 프롬프트에 들어가지 않는다.
    """
    meta = {"sandbox_schema_name": "sbx", "sandbox_table_name": "t1", "rows_inserted": 3}
    rows = [_row(74, "d.csv", kind="csv", uploader=0, meta=meta)]

    class _NoColsConn:
        def cursor(self, *a, **k):
            class _C:
                def execute(self, sql, params=None):
                    self._sql = sql

                def fetchall(self):
                    if "information_schema" in getattr(self, "_sql", ""):
                        return []          # 컬럼 없음 → 샘플 섹션이 continue 로 빠진다
                    return rows

                def close(self):
                    pass
            return _C()

    monkeypatch.setenv("ATTACHMENT_IDS", "74")
    monkeypatch.setattr(agent_core, "_resolve_group_sender_labels", lambda *a, **k: None)
    agent_core._ATTACHMENT_TURN_FACTS_CTX.set(None)
    agent_core._UNTRUSTED_ATTACH_BODY_CTX.set(False)
    agent_core._build_attachment_context_section(_NoColsConn(), [74], 10, "conv-x")
    assert agent_core.untrusted_attachment_body_in_context() is False
