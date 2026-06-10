"""회귀 테스트 — AR-M5 cutover 잔존 라우팅 누락 (TASK-0196).

TASK-0189(캘린더/추천) 와 동일 결함 class — 삭제된 MySQL 테이블
(AgentMemoryMessages/AgentCoreMessages/AgentCoreConversations 등)을 PG 라우팅 게이트
없이 조회하던 면들을 PG(agent_runtime.*)로 라우팅했다. 본 파일은 web(app.py) 측 3건 중
monkeypatch 로 DB 없이 검증 가능한 2건을 가드한다(나머지 admin_delete_product 는 라이브
검증). convo_search(agent-core)는 feature-0002 쪽 테스트 참조.

대상:
  T1 `_collect_matched_excerpts`: env=postgres 일 때 PG agent_runtime.messages/core_messages
     를 조회하고, 삭제된 MySQL 테이블(_connect_memory conn cursor)은 건드리지 않는다 →
     검색 발췌 스니펫이 더 이상 항상 빈칸이 아니다.
  T2 `_conv_update_topic`(rename_conversation_title 이 위임): env=postgres 일 때 PG
     agent_runtime.core_conversations 를 UPDATE 하고 MySQL 은 건드리지 않는다.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import app


class _FakePgCursor:
    def __init__(self, fetchall_rows):
        self._rows = fetchall_rows
        self.executed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append(sql)
        return None

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakePgConn:
    def __init__(self, fetchall_rows=()):
        self.cursor_obj = _FakePgCursor(fetchall_rows)
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


class _FakeMemCursor:
    def execute(self, *a, **k):
        raise AssertionError("PG 모드에서 삭제된 MySQL 테이블(conn cursor)을 조회하면 안 됨")

    def close(self):
        return None


class _FakeMemConn:
    def __init__(self):
        self.cursor_calls = 0

    def cursor(self, *a, **k):
        self.cursor_calls += 1
        return _FakeMemCursor()

    def close(self):
        return None


# ── T1: _collect_matched_excerpts PG 라우팅 ──────────────────────────────────
def test_collect_matched_excerpts_routes_to_pg(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    pg = _FakePgConn(fetchall_rows=[("c1", "dbgame 스키마를 조회한 결과입니다")])
    monkeypatch.setattr("modules.db._pg_connect", lambda: pg)
    mem = _FakeMemConn()

    out = app._collect_matched_excerpts(mem, ["c1"], "dbgame")

    assert out.get("c1"), "PG 경로에서 발췌가 비어 있으면 안 됨(빈칸 회귀)"
    assert "dbgame" in out["c1"]
    assert mem.cursor_calls == 0
    assert any("agent_runtime.messages" in s for s in pg.cursor_obj.executed)
    assert any("agent_runtime.core_messages" in s for s in pg.cursor_obj.executed)


# ── T2: _conv_update_topic(rename 위임) PG 라우팅 ────────────────────────────
def test_conv_update_topic_routes_to_pg(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    pg = _FakePgConn()
    monkeypatch.setattr("modules.db._pg_connect", lambda: pg)
    mem = _FakeMemConn()

    app._conv_update_topic(mem, "c1", "새 제목")

    assert mem.cursor_calls == 0, "rename 은 더 이상 raw UPDATE AgentCoreConversations 안 함"
    assert any("UPDATE agent_runtime.core_conversations" in s for s in pg.cursor_obj.executed)
