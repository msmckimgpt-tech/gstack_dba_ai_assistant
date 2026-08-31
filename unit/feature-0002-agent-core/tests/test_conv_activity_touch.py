"""conv-last-activity-updatedat — 표시 store 쓰기가 대화 활동 시각(`updated_at`)을 전진시킨다.

배경 (라이브 제보 2026-08-31, 대화 `20260828073505-be34624d`): `core_conversations.updated_at` 을
움직이는 write 가 **자동 제목 부여 경로에만** 있었다(`_conv_store._conv_update_topic_if_auto`).
그 UPDATE 는 제목이 placeholder 일 때만 행을 잡으므로 첫 턴에 제목이 확정된 뒤로는 후속 턴이
쌓여도 시각이 전진하지 않았다 — 라이브 실측 마지막 메시지 08-31 10:54 vs `updated_at` 08-28 16:38
(2일 18시간). 사이드바 "최근 갱신" 과 목록 정렬(`ORDER BY c.updated_at DESC`)이 그 컬럼을 읽는다.

여기서 잠그는 것:
- 표시 store INSERT 마다 touch SQL 이 **같은 커넥션으로** 실행된다 (미분기·브랜치 두 경로 모두).
- touch 는 `UPDATE`(있는 행만) — UPSERT 를 재사용해 유령 대화를 만들지 않는다.
- touch 실패는 흡수한다 — 메시지 저장이 성공한 turn 을 실패로 보고하지 않는다(브리지 경로는
  저장 실패를 요청 취소로 읽는다).
- 회수 store(`core_messages`) 단독 쓰기는 touch 하지 않는다 — 화면에 없는 tool turn 이 활동
  시각을 밀어 올리지 않도록.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = str(Path(__file__).parent.parent / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


class FakeCursor:
    def __init__(self, owner, rows=None, fail_on: str | None = None):
        self._owner = owner
        self._rows = rows if rows is not None else [(4242,)]
        self._fail_on = fail_on

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._owner.captured.append((sql, params))
        if self._fail_on and self._fail_on in sql:
            raise RuntimeError("simulated PG failure")

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConn:
    def __init__(self, rows=None, fail_on: str | None = None):
        self.captured: list[tuple[str, object]] = []
        self._rows = rows
        self._fail_on = fail_on

    def cursor(self):
        return FakeCursor(self, self._rows, self._fail_on)

    def close(self):
        pass


def _backend():
    import modules.runtime_backend as rb

    return rb.PgRuntimeBackend()


def _touch_calls(conn: FakeConn) -> list[tuple[str, object]]:
    return [(s, p) for s, p in conn.captured
            if "UPDATE agent_runtime.core_conversations" in s and "updated_at = now()" in s]


# ─────────────────────────────────────────────────────────────────────────────
# 표시 store 쓰기 → touch
# ─────────────────────────────────────────────────────────────────────────────

def test_save_memory_message_touches_conversation():
    """미분기 정상 append 가 활동 시각을 전진시킨다 (증상의 직접 원인)."""
    conn = FakeConn()
    new_id = _backend().save_memory_message(
        conn, conversation_id="cid-1", role="assistant", content="답변")

    assert new_id == 4242, "INSERT 반환 id 가 touch 추가로 소실되면 브랜치 leaf 전진이 깨진다"
    touches = _touch_calls(conn)
    assert len(touches) == 1, f"touch 가 정확히 1회여야 한다: {conn.captured}"
    assert touches[0][1] == {"conversation_id": "cid-1"}


def test_save_memory_message_branch_write_also_touches():
    """브랜치(메시지 편집·재답변) 경로도 같은 대화의 활동이다 — 여기서 빠지면 편집 대화만 뒤처진다."""
    conn = FakeConn()
    _backend().save_memory_message(
        conn, conversation_id="cid-2", role="assistant", content="수정 답변",
        parent_message_id=11, edit_root_message_id=7, edit_version=2, core_message_id=99)

    assert len(_touch_calls(conn)) == 1


def test_touch_uses_update_not_upsert():
    """touch 는 있는 행만 건드린다 — UPSERT 재사용은 topic 없는 유령 대화를 만든다."""
    conn = FakeConn()
    _backend().touch_conversation(conn, conversation_id="cid-3")

    sqls = [s for s, _ in conn.captured]
    assert len(sqls) == 1
    assert sqls[0].strip().startswith("UPDATE agent_runtime.core_conversations")
    assert "INSERT" not in sqls[0]
    assert "WHERE conversation_id = %(conversation_id)s" in sqls[0]


def test_touch_skips_blank_conversation_id():
    conn = FakeConn()
    _backend().touch_conversation(conn, conversation_id="   ")
    assert conn.captured == []


# ─────────────────────────────────────────────────────────────────────────────
# fail-soft — 저장된 turn 을 실패로 만들지 않는다
# ─────────────────────────────────────────────────────────────────────────────

def test_touch_failure_does_not_break_message_save():
    """touch 실패가 예외로 올라오면 브리지 경로가 **저장 성공한 질문을 취소**한다."""
    conn = FakeConn(fail_on="UPDATE agent_runtime.core_conversations")
    new_id = _backend().save_memory_message(
        conn, conversation_id="cid-4", role="user", content="질문")

    assert new_id == 4242, "touch 실패가 메시지 id 반환을 삼키면 안 된다"


def test_touch_failure_is_logged_not_silent(caplog):
    conn = FakeConn(fail_on="UPDATE agent_runtime.core_conversations")
    with caplog.at_level("WARNING"):
        _backend().touch_conversation(conn, conversation_id="cid-5")
    assert any("touch_conversation" in r.message or "활동 시각" in r.getMessage()
               for r in caplog.records), "조용한 실패는 표시가 다시 뒤처져도 알 수 없게 만든다"


# ─────────────────────────────────────────────────────────────────────────────
# 경계 — 회수 store 단독 쓰기는 활동 시각을 밀지 않는다
# ─────────────────────────────────────────────────────────────────────────────

def test_save_core_message_does_not_touch():
    """회수 store 는 tool 호출까지 담는다(한 run 에 수십 건). 화면에 없는 turn 이 "최근 갱신" 을
    밀어 올리면 사용자가 읽는 값의 의미가 흐려지고, 행 UPDATE 도 그만큼 늘어난다."""
    conn = FakeConn()
    _backend().save_core_message(
        conn, conversation_id="cid-6", role="tool", content="{}", tool_call_id="tc-1")

    assert _touch_calls(conn) == []


def test_touch_sql_constant_targets_updated_at_only():
    """SQL 상수 자체를 잠근다 — 다른 컬럼이 섞이면 활동 시각 전진이 부수효과를 갖는다."""
    import modules.runtime_backend as rb

    sql = rb._PG_TOUCH_CONVERSATION
    assert "SET updated_at = now()" in sql
    for col in ("topic", "owner_account_id", "product_id", "product_mode", "archived_at"):
        assert col not in sql, f"touch SQL 이 {col} 을 건드린다"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
