"""회귀 테스트 — convo_search(에이전트 도구) AR-M5 cutover 라우팅 누락 (TASK-0196).

배경: `convo_search` 는 다른 대화 기록을 검색하는 LOCAL agent tool 이다. file_ops.py 에
PG 경로가 전무한 채 삭제된 MySQL 테이블(AgentMemoryMessages/AgentMemorySummary/
AgentMemoryKv)을 try/finally(except 없음)로 조회 → 에이전트가 도구 호출 시 throw(기능 사망).

수정: AGENT_RUNTIME_READ_BACKEND=postgres 일 때 PG agent_runtime.messages/summary/kv 로
라우팅(ILIKE = MySQL case-insensitive 패리티). 본 테스트는 PG 라우팅 + 전달된 MySQL conn
미사용(삭제 테이블 미조회)을 가드한다.

`make test` (agent 이미지) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from modules import file_ops


class _FakePgCursor:
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table
        self.executed: list[str] = []
        self.params: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append(sql)
        self.params.append(params)
        if "agent_runtime.messages" in sql:
            self._last = self._rows_by_table.get("messages", [])
        elif "agent_runtime.summary" in sql:
            self._last = self._rows_by_table.get("summary", [])
        elif "agent_runtime.kv" in sql:
            self._last = self._rows_by_table.get("kv", [])
        else:
            self._last = []
        return None

    def fetchall(self):
        return list(self._last)


class _FakePgConn:
    def __init__(self, rows_by_table):
        self.cursor_obj = _FakePgCursor(rows_by_table)
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


class _FakeMemConn:
    """전달되는 MySQL conn — PG 모드에서는 절대 cursor() 가 호출되면 안 된다."""

    def __init__(self):
        self.cursor_calls = 0

    def cursor(self, *a, **k):
        self.cursor_calls += 1
        raise AssertionError("PG 모드에서 삭제된 MySQL 테이블(conn cursor)을 조회하면 안 됨")

    def close(self):
        return None


def test_convo_search_routes_to_pg(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    now = datetime(2026, 6, 8, 14, 0, 0, tzinfo=timezone.utc)
    rows = {
        "messages": [("other-cid", "user", "dbgame 관련 질문", now, "message")],
        "summary": [("other-cid", "summary", "dbgame 요약", now, "summary")],
        "kv": [("other-cid", "topic", "dbgame 주제", now, "topic")],
    }
    pg = _FakePgConn(rows)
    monkeypatch.setattr("shared.db._pg_connect", lambda: pg)
    mem = _FakeMemConn()

    out = file_ops.convo_search(mem, "current-cid", query="dbgame", limit=10)

    assert mem.cursor_calls == 0, "PG 모드에서 삭제된 MySQL 테이블을 조회하면 throw(도구 사망)"
    sources = {r["source"] for r in out}
    assert sources == {"message", "summary", "topic"}, "3개 PG 소스(messages/summary/kv) 모두 검색"
    # PG agent_runtime.* 3개 테이블 모두 조회했는지
    joined = " ".join(pg.cursor_obj.executed)
    assert "agent_runtime.messages" in joined
    assert "agent_runtime.summary" in joined
    assert "agent_runtime.kv" in joined
    # current 대화 제외(include_current=False default)
    assert all(r["conversation_id"] != "current-cid" for r in out)


# ── TASK-0200 MINOR: LIKE/ILIKE 메타문자 이스케이프 ───────────────────────────
def test_convo_search_escapes_like_metachars(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    pg = _FakePgConn({})  # 결과는 무관, 쿼리/파라미터만 검사
    monkeypatch.setattr("shared.db._pg_connect", lambda: pg)

    file_ops.convo_search(_FakeMemConn(), "current-cid", query="100%_x!", limit=5)

    # 메타문자(%, _, !)가 ESCAPE '!' 기준으로 이스케이프돼 와일드카드로 새지 않는다.
    like_params = [p[0] for p in pg.cursor_obj.params]  # 각 쿼리 첫 파라미터 = like_pattern
    assert all(lp == "%100!%!_x!!%" for lp in like_params), like_params
    assert all("ESCAPE '!'" in sql for sql in pg.cursor_obj.executed), "비어있지 않은 질의는 ESCAPE 동반"


def test_convo_search_empty_query_matches_all_without_escape(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    pg = _FakePgConn({})
    monkeypatch.setattr("shared.db._pg_connect", lambda: pg)

    file_ops.convo_search(_FakeMemConn(), "current-cid", query="", limit=5)

    like_params = [p[0] for p in pg.cursor_obj.params]
    assert all(lp == "%" for lp in like_params), "빈 질의 = 전체 매칭(%)"
    assert all("ESCAPE" not in sql for sql in pg.cursor_obj.executed), "빈 질의는 ESCAPE 절 없음"
