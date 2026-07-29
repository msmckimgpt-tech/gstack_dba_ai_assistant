"""본문 검색 경로의 collation audit NameError 회귀 테스트 (TASK-20260729T170000).

결함: ITEM-10 p7(2026-07-11, CHG-20260711T161858)이 `_audit_message_table_collations` 를
app.py → `routers/_audit_infra.py` 로 옮기면서 `global _COLLATION_AUDIT_DONE` 선언만 따라가고
그 이름의 **module-level 정의는 app.py 에 남았다**. `global` 은 *그 모듈의* 전역을 가리키므로
첫 읽기(`if _COLLATION_AUDIT_DONE`)에서 곧바로 `NameError` — `_list_conversations` 의 본문
검색 게이트(`if normalized_q:`)가 이 함수를 부르는 탓에 **`GET /api/conversations?q=…` 가
2026-07-11~2026-07-29 내내 500** 이었다(라이브 PB-0008 검증 중 발견).

왜 기존 테스트가 못 잡았나(정직): 검색 관련 단위 테스트들이 이 함수를 monkeypatch 로 no-op
처리하거나 `_list_conversations_pg` 를 직접 호출해 `_list_conversations` 의 게이트를 건너뛰었다.
아래 테스트는 **패치 없이 실제 경로를 탄다**.

검증:
  N1  _audit_message_table_collations 가 NameError 없이 1회 동작하고 플래그를 app 전역에 쓴다.
  N2  두 번째 호출은 조기 반환(once per process) — 쿼리를 다시 실행하지 않는다.
  N3  플래그를 app 전역에 둔다(모듈 로컬 정의 신설 금지 — 상태 분기 방지).
  N4  `_list_conversations` 본문 검색 경로가 audit 함수를 **패치 없이** 통과한다(500 재발 차단).
  N5  audit 내부 실패는 검색을 막지 않는다(fail-soft).
"""
from __future__ import annotations

import app
from routers import _audit_infra, _conv_store


class _Cursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        self._store.setdefault("executed", []).append(str(sql))
        if self._store.get("raise"):
            raise RuntimeError("information_schema unavailable")

    def fetchall(self):
        return []

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self, store):
        self._store = store

    def cursor(self, *a, **k):
        return _Cursor(self._store)

    def close(self):
        pass


def _reset_flag(monkeypatch):
    monkeypatch.setattr(app, "_COLLATION_AUDIT_DONE", False, raising=False)


def test_n1_collation_audit_runs_without_nameerror(monkeypatch):
    _reset_flag(monkeypatch)
    store: dict = {}
    _audit_infra._audit_message_table_collations(_Conn(store))  # NameError 면 여기서 터진다
    assert store.get("executed"), "audit 쿼리가 실행되지 않았다"
    assert app._COLLATION_AUDIT_DONE is True


def test_n2_collation_audit_runs_once_per_process(monkeypatch):
    _reset_flag(monkeypatch)
    store: dict = {}
    conn = _Conn(store)
    _audit_infra._audit_message_table_collations(conn)
    first = len(store.get("executed", []))
    _audit_infra._audit_message_table_collations(conn)
    assert len(store.get("executed", [])) == first, "2회차는 조기 반환해야 한다"


def test_n3_flag_lives_on_app_module_not_router_module(monkeypatch):
    """플래그를 라우터 모듈에 새로 정의하면 app.py 의 것과 상태가 갈린다."""
    _reset_flag(monkeypatch)
    _audit_infra._audit_message_table_collations(_Conn({}))
    assert app._COLLATION_AUDIT_DONE is True, "app 전역이 갱신되어야 한다"
    assert "_COLLATION_AUDIT_DONE" not in vars(_audit_infra), (
        "라우터 모듈에 별도 정의를 두면 once-per-process 상태가 이중화된다"
    )


def test_n4_body_search_path_survives_audit_call(monkeypatch):
    """`_list_conversations` 의 본문 검색 게이트를 **패치 없이** 통과한다(500 재발 차단)."""
    _reset_flag(monkeypatch)
    monkeypatch.delenv("AGENT_RUNTIME_READ_BACKEND", raising=False)
    monkeypatch.setattr(app, "cleanup_pending_delete_conversations", lambda c: None, raising=False)
    monkeypatch.setattr(app, "list_delete_requested_conversation_ids", lambda c: [], raising=False)
    # _audit_message_table_collations 는 **일부러 패치하지 않는다** — 이 호출이 결함 지점이었다.
    store: dict = {}

    class _DictCursor(_Cursor):
        def fetchall(self):
            return []

    class _DictConn(_Conn):
        def cursor(self, *a, **k):
            return _DictCursor(self._store)

    items = _conv_store._list_conversations(
        50,
        account={"id": 1, "username": "t", "permissions": {"conversation.list.own": True}},
        conn=_DictConn(store),
        q="매출",
    )
    assert items == []
    assert any("information_schema" in s.lower() for s in store.get("executed", [])), (
        "audit 함수가 실제로 실행된 경로여야 회귀 가드로 의미가 있다"
    )


def test_n5_audit_failure_does_not_break_search(monkeypatch):
    _reset_flag(monkeypatch)
    store: dict = {"raise": True}
    # 예외를 삼키고 정상 반환해야 한다(fail-soft — 경고 목적 함수가 검색을 막지 않는다).
    _audit_infra._audit_message_table_collations(_Conn(store))
