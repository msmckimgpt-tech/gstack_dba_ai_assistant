"""M4 (TASK-0024) — PgKbBackend.search_rag_documents() + read backend routing.

실 DB 호출 없이 monkeypatch + FakeConn 으로 검증:
- PgKbBackend.search_rag_documents — pg_trgm SQL emit + params 정합
- _PG_SEARCH_RAG_DOCUMENTS_WITH_TEXT vs _NO_TEXT 분기
- query_text 비어있을 시 ORDER BY weight DESC fallback (FtScore 부재)
- empty conversation_ids 시 [] 반환
- knowledge._load_rag_documents_for_request_pg 의 _pg_available False → None
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _load_kb_backend():
    from modules import kb_backend as kb  # type: ignore
    return kb


# ─────────────────────────────────────────────────────────────────────────────
# PgKbBackend.search_rag_documents — SQL emit
# ─────────────────────────────────────────────────────────────────────────────


def test_search_rag_documents_with_text_emits_pg_trgm_sql():
    """query_text 가 있을 때 similarity() 함수 호출 SQL 발행."""
    kb = _load_kb_backend()

    captured = []
    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): captured.append((sql, params))
        def fetchall(self): return [
            ("conv1", "user-count-7d", "최근 7일 가입 사용자 수", 5, "repair", None, "2026-05-22", 0.85),
        ]

    class FakeConn:
        def cursor(self): return FakeCursor()

    backend = kb.PgKbBackend()
    rows = backend.search_rag_documents(
        FakeConn(),
        conversation_ids=["conv1", "conv2"],
        query_text="7일 가입자",
        scope_keys=["common", "sales_q4"],
    )

    assert len(captured) == 1
    sql, params = captured[0]
    assert "similarity(" in sql
    assert "rag_documents" in sql.lower()
    assert "texts" in sql.lower()
    assert "= ANY(%(conv_ids)s)" in sql
    assert params["conv_ids"] == ["conv1", "conv2"]
    assert params["query_text"] == "7일 가입자"
    assert params["scope_keys"] == ["common", "sales_q4"]

    # Row passthrough
    assert len(rows) == 1
    assert rows[0][7] == 0.85  # ft_score


def test_search_rag_documents_no_text_no_score_column():
    """query_text='' 시 NO_TEXT SQL — similarity() 없음 + ORDER BY weight."""
    kb = _load_kb_backend()
    captured = []
    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): captured.append((sql, params))
        def fetchall(self): return []
    class FakeConn:
        def cursor(self): return FakeCursor()

    backend = kb.PgKbBackend()
    backend.search_rag_documents(
        FakeConn(),
        conversation_ids=["conv1"],
        query_text="",
        scope_keys=None,
    )
    sql, params = captured[0]
    assert "similarity(" not in sql, f"NO_TEXT 분기인데 similarity() 호출됨"
    assert "ORDER BY d.weight DESC" in sql
    # query_text 미전달
    assert "query_text" not in params


def test_search_rag_documents_empty_conv_ids_returns_empty():
    kb = _load_kb_backend()

    class FakeCursor:
        called = False
        def execute(self, *a, **kw): FakeCursor.called = True

    class FakeConn:
        def cursor(self): return FakeCursor()

    backend = kb.PgKbBackend()
    result = backend.search_rag_documents(
        FakeConn(),
        conversation_ids=[],
        query_text="anything",
    )
    assert result == []
    assert not FakeCursor.called


def test_search_rag_documents_scope_keys_none_sql_null_clause():
    """scope_keys=None 시 SQL params['scope_keys']=None — `IS NULL OR =ANY` clause."""
    kb = _load_kb_backend()
    captured = []
    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): captured.append((sql, params))
        def fetchall(self): return []
    class FakeConn:
        def cursor(self): return FakeCursor()

    backend = kb.PgKbBackend()
    backend.search_rag_documents(
        FakeConn(),
        conversation_ids=["conv1"],
        query_text="hello",
        scope_keys=None,
    )
    _, params = captured[0]
    assert params["scope_keys"] is None


# ─────────────────────────────────────────────────────────────────────────────
# knowledge._load_rag_documents_for_request_pg — _pg_available False → None
# ─────────────────────────────────────────────────────────────────────────────


def test_load_rag_documents_pg_returns_none_when_unavailable(monkeypatch):
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from modules import knowledge  # type: ignore

    monkeypatch.setattr(
        sys.modules["shared.db"], "_pg_available", lambda: False, raising=True,
    )
    result = knowledge._load_rag_documents_for_request_pg(
        ["conv1"], "request", ["common"],
    )
    assert result is None


def test_load_rag_documents_pg_calls_backend(monkeypatch):
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from modules import knowledge, kb_backend  # type: ignore

    monkeypatch.setattr(
        sys.modules["shared.db"], "_pg_available", lambda: True, raising=True,
    )

    class FakeConn:
        closed = False
        def close(self): FakeConn.closed = True

    # REV-20260522-0012 B3 흡수: _pg_connect_ro 사용 확인.
    monkeypatch.setattr(
        sys.modules["shared.db"], "_pg_connect_ro", lambda *a, **kw: FakeConn(), raising=True,
    )

    captured = []
    def _spy_search(self, conn, *, conversation_ids, query_text, scope_keys=None):
        captured.append({
            "conv_ids": conversation_ids,
            "query_text": query_text,
            "scope_keys": scope_keys,
        })
        return [
            ("conv1", "k1", "PG content", 3, "repair", None, "2026-05-22", 0.7),
        ]
    monkeypatch.setattr(kb_backend.PgKbBackend, "search_rag_documents", _spy_search)
    # TASK-0135: 본 테스트는 trigram 경로 검증 — 쿼리 임베딩을 None 으로 mock 해
    # 결정적으로 trigram fallback 을 타게 한다 (벡터 경로는 라이브 canary 로 검증).
    monkeypatch.setattr(knowledge, "_embed_query_vector", lambda *a, **k: None)

    result = knowledge._load_rag_documents_for_request_pg(
        ["conv1"], "test request", ["common"],
    )
    assert len(captured) == 1
    assert captured[0]["conv_ids"] == ["conv1"]
    assert captured[0]["query_text"] == "test request"
    assert captured[0]["scope_keys"] == ["common"]
    assert result is not None
    assert len(result) == 1
    assert result[0]["conversation_id"] == "conv1"
    assert result[0]["text"].startswith("PG content")
    assert result[0]["ft_score"] == 0.7
    assert FakeConn.closed


# ─────────────────────────────────────────────────────────────────────────────
# REV-20260522-0012 B4 흡수: fail-soft fallback regression test —
# AGENT_KB_READ_BACKEND=postgres + PG fail → MySQL fallback 작동 확인 (B1 fix
# 의 logger 정의 없으면 NameError 로 crash 했을 path).
# ─────────────────────────────────────────────────────────────────────────────


def test_pg_read_failure_falls_back_to_mysql(monkeypatch):
    """PG read 실패 시 logger.warning 호출 + MySQL path 진행 (NameError 없이)."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from modules import knowledge  # type: ignore

    # AGENT_KB_READ_BACKEND=postgres 시뮬레이션
    monkeypatch.setattr(
        sys.modules["shared.config"], "AGENT_KB_READ_BACKEND", "postgres", raising=True,
    )
    # PG path 가 Exception raise — fail-soft 진입
    def _raise(*a, **kw):
        raise RuntimeError("simulated PG outage")
    monkeypatch.setattr(
        knowledge, "_load_rag_documents_for_request_pg", _raise, raising=True,
    )

    # MySQL cursor mock — fail-soft fallthrough 시 호출됨
    mysql_called = []
    class FakeCursor:
        def execute(self, sql, params):
            mysql_called.append((sql, params))
        def fetchall(self):
            return [("conv1", "fact_key1", "mysql content", 2, "repair", None, "2026-05-22")]
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    # logger 정의 확인 — knowledge.py 에 module-level logger 가 있어야 함
    assert hasattr(knowledge, "logger"), "B1 fix 누락: knowledge.logger 부재 — fail-soft 가 NameError"

    # fail-soft 가 NameError 없이 작동하고 MySQL fallback 호출
    result = knowledge._load_rag_documents_for_request(
        FakeConn(), ["conv1"], "test request",
    )
    assert len(mysql_called) == 1, "MySQL fallback 미호출"
    assert result, "MySQL fallback 결과 비어있음"
    assert result[0]["conversation_id"] == "conv1"


# ─────────────────────────────────────────────────────────────────────────────
# REV-20260522-0012 B2 흡수: scope_keys 의 blank string("") 매치 정합 검증.
# ─────────────────────────────────────────────────────────────────────────────


def test_search_rag_documents_blank_scope_includes_null(monkeypatch):
    """scope_keys 에 "" 포함 시 NULL/'' 매치 절 동반."""
    kb = _load_kb_backend()
    captured = []
    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): captured.append((sql, params))
        def fetchall(self): return []
    class FakeConn:
        def cursor(self): return FakeCursor()

    backend = kb.PgKbBackend()
    backend.search_rag_documents(
        FakeConn(),
        conversation_ids=["conv1"],
        query_text="hello",
        scope_keys=["primary", "common", ""],  # "_scope_candidates()" 의 default
    )
    sql, params = captured[0]
    # _INCL_NULL SQL 분기 사용 확인
    assert "scope_key IS NULL" in sql, "blank scope 포함인데 IS NULL 절 누락 (B2 위반)"
    assert "scope_key = ''" in sql, "blank scope 포함인데 = '' 절 누락 (B2 위반)"
    # blank 가 ANY 에는 안 들어감 (= '' 절이 별로 처리)
    assert "" not in (params["scope_keys"] or [])


def test_search_rag_documents_strict_scope_no_null_clause(monkeypatch):
    """scope_keys 에 "" 미포함 시 strict — NULL 절 없음."""
    kb = _load_kb_backend()
    captured = []
    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): captured.append((sql, params))
        def fetchall(self): return []
    class FakeConn:
        def cursor(self): return FakeCursor()

    backend = kb.PgKbBackend()
    backend.search_rag_documents(
        FakeConn(),
        conversation_ids=["conv1"],
        query_text="hello",
        scope_keys=["sales_q4"],
    )
    sql, params = captured[0]
    assert "scope_key IS NULL" not in sql, "strict scope 인데 IS NULL 절 포함 (B2 over-match)"
