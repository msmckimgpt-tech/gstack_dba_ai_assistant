"""회귀 테스트 — 캘린더 날짜/시각 점프 엔드포인트의 PG 라우팅 누락 (AR-M5 cutover).

배경:
  메시지 정본이 MySQL `AgentMemoryMessages` → PG `agent_runtime.messages` 로 cutover
  되며 MySQL 테이블이 DROP 되었다(AR-M5). `_get_history` 는 `AGENT_RUNTIME_READ_BACKEND`
  로 분기해 PG 를 읽도록 이전됐지만, 캘린더를 떠받치는 두 엔드포인트는 이전에서 누락돼
  여전히 삭제된 MySQL 테이블을 직접 조회했다:

    - `/api/history_dates`  : 삭제된 테이블 조회 → except → 항상 `{"dates": {}}` 반환
                              → 캘린더에 클릭 가능한 날짜가 없음(= "날짜기준표 캘린더로
                              대화 구간 이동" 기능 누락).
    - `/api/history_anchor` : 삭제된 테이블 조회 → except → 500. 설령 행이 있어도 MySQL
                              Id 라 PG id 기반 DOM(`message-<id>`)과 매칭 실패.

  근본 원인: cutover 시 message 읽기 경로 중 일부(_get_history, _load_latest_assistant_
  message)만 PG 로 라우팅하고, 캘린더 backing 2개 엔드포인트는 누락.

테스트:
  T1 history_dates: env=postgres 일 때 PG `agent_runtime.messages` 를 읽고, MySQL
     `AgentMemoryMessages` (= _connect_memory cursor) 는 건드리지 않는다(회귀 가드).
  T2 history_anchor: env=postgres 일 때 PG id 를 message_id 로 반환한다(DOM id-space 일치).
  T3 history_dates: env != postgres(legacy) 일 때는 기존 MySQL 경로를 그대로 사용한다(back-compat).

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import json

import app


# ── PG fake ────────────────────────────────────────────────────────────────
class _FakePgCursor:
    def __init__(self, fetchall_rows, fetchone_row):
        self._fetchall_rows = fetchall_rows
        self._fetchone_row = fetchone_row
        self.executed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append(sql)
        return None

    def fetchall(self):
        return list(self._fetchall_rows)

    def fetchone(self):
        return self._fetchone_row


class _FakePgConn:
    def __init__(self, fetchall_rows=(), fetchone_row=None):
        self.cursor_obj = _FakePgCursor(fetchall_rows, fetchone_row)
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


# ── MySQL (memory) fake — PG 모드에서는 절대 cursor() 가 호출되면 안 된다 ──────
class _FakeMemCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *a, **k):
        return None

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        return None


class _FakeMemConn:
    def __init__(self, rows=()):
        self._rows = rows
        self.cursor_calls = 0
        self.closed = False

    def cursor(self):
        self.cursor_calls += 1
        return _FakeMemCursor(self._rows)

    def close(self):
        self.closed = True


class _DummyRequest:
    """history_* 는 request 를 _require_account 로만 넘기고, 우리는 그걸 monkeypatch 한다."""


def _patch_auth(monkeypatch, conv_id="conv-1"):
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"Id": 1}, None))
    monkeypatch.setattr(
        app, "_resolve_conversation_for_account", lambda conn, account, requested: conv_id
    )


def _body(resp):
    return json.loads(resp.body)


# ── T1: history_dates PG 라우팅 + MySQL 미접촉 회귀 가드 ──────────────────────
def test_history_dates_routes_to_pg_and_skips_dropped_mysql_table(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    mem = _FakeMemConn()
    monkeypatch.setattr(app, "_connect_memory", lambda: mem)
    _patch_auth(monkeypatch)
    pg = _FakePgConn(
        fetchall_rows=[
            ("2026-05-18", "09:05,14:30,14:30"),
            ("2026-05-19", "10:00"),
        ]
    )
    monkeypatch.setattr("modules.db._pg_connect", lambda: pg)

    resp = app.history_dates(_DummyRequest(), conversation_id="conv-1")
    body = _body(resp)

    # PG 행에서 조립 — 클릭 가능한 날짜가 생긴다(빈 dates 회귀 아님).
    assert body["dates"] == {"2026-05-18": ["09:05", "14:30"], "2026-05-19": ["10:00"]}
    assert body["first"] == "2026-05-18"
    assert body["last"] == "2026-05-19"
    # 회귀 가드: 삭제된 MySQL AgentMemoryMessages 를 조회하지 않았다.
    assert mem.cursor_calls == 0, "PG 모드에서 MySQL 테이블(_connect_memory cursor)을 건드리면 안 됨"
    assert pg.closed is True


# ── T2: history_anchor 는 PG id 를 반환한다(DOM id-space 일치) ────────────────
def test_history_anchor_returns_pg_id(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    mem = _FakeMemConn()
    monkeypatch.setattr(app, "_connect_memory", lambda: mem)
    _patch_auth(monkeypatch)
    pg = _FakePgConn(fetchone_row=(4242, "2026-05-18 14:30:00+09:00"))
    monkeypatch.setattr("modules.db._pg_connect", lambda: pg)

    resp = app.history_anchor(
        _DummyRequest(), conversation_id="conv-1", at="2026-05-18 14:30:00"
    )
    body = _body(resp)

    assert body["message_id"] == 4242
    assert mem.cursor_calls == 0, "PG 모드에서 삭제된 MySQL 테이블을 조회하면 안 됨"
    # 점프 매칭은 history_dates 라벨과 동일한 to_char wall-clock 기준 + **분 단위**여야 한다
    # (초 단위면 클릭한 분의 메시지가 직전으로 밀린다).
    assert any("to_char(created_at, 'YYYY-MM-DD HH24:MI')" in s for s in pg.cursor_obj.executed)
    assert all("HH24:MI:SS" not in s for s in pg.cursor_obj.executed), "초 단위 비교는 직전-메시지 결함"


# ── T3: legacy(env != postgres) 는 기존 MySQL 경로 유지 (back-compat) ─────────
def test_history_dates_legacy_mysql_path_when_backend_not_postgres(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)
    # MySQL 경로: DATE(CreatedAt), GROUP_CONCAT 결과 형태.
    mem = _FakeMemConn(rows=[("2026-05-18", "09:05,14:30")])
    monkeypatch.setattr(app, "_connect_memory", lambda: mem)
    _patch_auth(monkeypatch)

    # PG 가 호출되면 실패하도록 — legacy 경로는 PG 를 만지면 안 된다.
    def _boom():
        raise AssertionError("legacy 경로에서 PG 를 호출하면 안 됨")

    monkeypatch.setattr("modules.db._pg_connect", _boom)

    resp = app.history_dates(_DummyRequest(), conversation_id="conv-1")
    body = _body(resp)

    assert body["dates"] == {"2026-05-18": ["09:05", "14:30"]}
    assert mem.cursor_calls >= 1, "legacy 경로는 MySQL cursor 를 사용해야 함"


# ── T4: /api/suggestions 도 동일 cutover 결함 (입력 추천 500) — PG 라우팅 회귀 가드 ──
def test_suggestions_routes_to_pg_and_skips_dropped_mysql_table(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    mem = _FakeMemConn()
    monkeypatch.setattr(app, "_connect_memory", lambda: mem)
    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"Id": 1}, None))
    monkeypatch.setattr(app, "_account_has_permission", lambda account, perm: True)
    monkeypatch.setattr(
        app, "_list_conversations",
        lambda limit=200, account=None, conn=None: [{"id": "c1"}, {"id": "c2"}],
    )
    pg = _FakePgConn(fetchall_rows=[("최근 사용자 질문입니다",), ("또 다른 사용자 질문",)])
    monkeypatch.setattr("modules.db._pg_connect", lambda: pg)

    resp = app.suggestions(_DummyRequest(), limit=5)
    body = _body(resp)

    assert body["items"] == ["최근 사용자 질문입니다", "또 다른 사용자 질문"]
    # 회귀 가드: 삭제된 MySQL AgentMemoryMessages(_connect_memory cursor)를 조회하지 않았다.
    assert mem.cursor_calls == 0, "PG 모드에서 삭제된 MySQL 테이블을 조회하면 500(추천 죽음)"
    assert any("agent_runtime.messages" in s for s in pg.cursor_obj.executed)
