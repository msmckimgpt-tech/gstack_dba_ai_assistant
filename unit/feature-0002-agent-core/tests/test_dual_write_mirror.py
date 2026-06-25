"""KbBackend / _DualWriteMirror unit test — dual-write 의 핵심 invariant 검증.

TASK-0020 (M2-b) 산출. 본 test 는 실 Postgres connection 없이 monkeypatch 로 동작 —
fixture 가 `_pg_available()` 와 `_pg_connect()` 를 가짜 객체로 대체. M2-c runtime
검증 (실 DB 호출) 은 `test_anchor_invariant_postgres.py` 에서 별도 수행.

검증 항목:
1. `_pg_available()` False 시 mirror 호출이 silent no-op (M0~M2-a 패턴)
2. `_pg_available()` True + `AGENT_KB_PG_REQUIRED=0` + Pg 호출 실패 시 silent log
3. `_pg_available()` True + `AGENT_KB_PG_REQUIRED=1` + Pg 호출 실패 시 fail-loud
4. `_pg_available()` True + Pg 호출 성공 시 caller 의 cursor.execute 와 양쪽 mirror
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """각 test 가 AGENT_KB_PG_REQUIRED 환경변수를 독립 제어."""
    monkeypatch.delenv("AGENT_KB_PG_REQUIRED", raising=False)
    yield


def _load_kb_backend():
    """conftest.py 가 sys.path 통합. 본 함수는 backward-compat shim."""
    from modules import kb_backend as kb  # type: ignore
    kb._BACKENDS_CACHE = None
    return kb


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: _pg_available() False 시 mirror 가 silent no-op
# ─────────────────────────────────────────────────────────────────────────────


def test_mirror_silent_noop_when_pg_unavailable(monkeypatch):
    """M0~M2-a 핵심 invariant: postgres 미가동 환경에서 caller flow 무영향."""
    kb = _load_kb_backend()
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_available",
        lambda: False,
        raising=True,
    )
    kb._BACKENDS_CACHE = None

    # mirror 호출 — _pg_available() False 이므로 silent no-op
    result = kb._dual_write_kb.upsert_text(text_hash="abc", text_content="hello")
    assert result is None

    # get_backends() 가 pg_b=None 반환 확인
    mysql_b, pg_b = kb.get_backends()
    assert mysql_b is not None
    assert pg_b is None


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: _pg_available() True + REQUIRED=0 + Pg 호출 실패 → silent log
# ─────────────────────────────────────────────────────────────────────────────


def test_mirror_silent_log_when_required_zero_and_pg_call_fails(monkeypatch):
    """M0~M2-a 의 graceful skip: AGENT_KB_PG_REQUIRED=0 시 mirror 실패 silent."""
    kb = _load_kb_backend()
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_available",
        lambda: True,
        raising=True,
    )
    monkeypatch.delenv("AGENT_KB_PG_REQUIRED", raising=False)
    kb._BACKENDS_CACHE = None

    # _pg_connect 가 실패 raise — connection 단계 fail
    def _connect_fails(*a, **kw):
        raise RuntimeError("simulated connection failure")
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_connect",
        _connect_fails,
        raising=True,
    )

    # mirror 호출 — silent no-op (caller flow 보호)
    result = kb._dual_write_kb.upsert_text(text_hash="abc", text_content="hello")
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: _pg_available() True + REQUIRED=1 + Pg 호출 실패 → fail-loud
# ─────────────────────────────────────────────────────────────────────────────


def test_mirror_fail_loud_when_required_one_and_pg_call_fails(monkeypatch):
    """M2-b 의 fail-loud invariant: AGENT_KB_PG_REQUIRED=1 시 mirror 실패 propagate."""
    kb = _load_kb_backend()
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_available",
        lambda: True,
        raising=True,
    )
    monkeypatch.setenv("AGENT_KB_PG_REQUIRED", "1")
    kb._BACKENDS_CACHE = None

    def _connect_fails(*a, **kw):
        raise RuntimeError("simulated connection failure")
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_connect",
        _connect_fails,
        raising=True,
    )

    with pytest.raises(RuntimeError, match="simulated connection failure"):
        kb._dual_write_kb.upsert_text(text_hash="abc", text_content="hello")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: _pg_available() True + Pg 호출 성공 → PgKbBackend method 호출 + close
# ─────────────────────────────────────────────────────────────────────────────


def test_mirror_calls_pg_backend_on_success(monkeypatch):
    """dual-write 정합: mirror 가 PgKbBackend.upsert_text 호출 + connection close."""
    kb = _load_kb_backend()
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_available",
        lambda: True,
        raising=True,
    )

    # 가짜 connection — close 호출 추적
    closed = {"value": False}

    class FakeCursor:
        def __init__(self):
            self.executed = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            self.executed.append((sql.strip().split("\n", 1)[0].strip(), params))

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            closed["value"] = True

    fake_conn = FakeConn()
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_connect",
        lambda *a, **kw: fake_conn,
        raising=True,
    )
    kb._BACKENDS_CACHE = None

    # mirror 호출
    result = kb._dual_write_kb.upsert_text(
        text_hash="abc123", text_content="dual-write payload"
    )
    # upsert_text 는 RETURNING id 없으므로 None
    assert result is None
    # connection close 확인
    assert closed["value"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: KbBackend ABC method 누락 시 instantiate 실패
# ─────────────────────────────────────────────────────────────────────────────


def test_kb_backend_abc_enforces_abstract_methods():
    """ABC 강제 — Mysql/Pg backend 가 모든 abstract method 구현."""
    kb = _load_kb_backend()
    # MysqlKbBackend / PgKbBackend 의 instantiation 자체가 ABC method 정합 검증
    mysql_b = kb.MysqlKbBackend()
    pg_b = kb.PgKbBackend()
    # 5 method 모두 callable
    for method_name in (
        "upsert_fact_entry",
        "delete_fact_entries_by_conv_scope_key",
        "prune_fact_entries_keep_top",
        "upsert_text",
        "upsert_rag_document",
        "upsert_rag_object",
    ):
        assert callable(getattr(mysql_b, method_name))
        assert callable(getattr(pg_b, method_name))


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: _BACKENDS_CACHE singleton (REV-20260520-0007 Nice-to-have)
# ─────────────────────────────────────────────────────────────────────────────


def test_get_backends_returns_cached_instance(monkeypatch):
    """outside-voice REV-20260520-0007 Nice-to-have: process-level cache."""
    kb = _load_kb_backend()
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_available",
        lambda: True,
        raising=True,
    )
    kb._BACKENDS_CACHE = None

    first = kb.get_backends()
    second = kb.get_backends()
    # 동일 instance 재사용 (cache)
    assert first[0] is second[0]
    assert first[1] is second[1]


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: PgKbBackend.set_text_embedding 호출 → SQL UPDATE
# ─────────────────────────────────────────────────────────────────────────────


def test_pg_backend_set_text_embedding(monkeypatch):
    """M3 backfill cycle 의 entry — embedding 컬럼 UPDATE."""
    kb = _load_kb_backend()

    captured_sql = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            captured_sql.append((sql, params))

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    backend = kb.PgKbBackend()
    backend.set_text_embedding(
        FakeConn(),
        text_hash="abc",
        embedding=[0.1, 0.2, 0.3],
        embedding_model="text-embedding-3-small",
    )
    assert len(captured_sql) == 1
    sql, params = captured_sql[0]
    assert "UPDATE texts" in sql
    assert "::vector" in sql
    assert params["text_hash"] == "abc"
    assert params["embedding"] == [0.1, 0.2, 0.3]
    assert params["embedding_model"] == "text-embedding-3-small"


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: MysqlKbBackend.upsert_text 직접 호출 → INSERT IGNORE 발행
# ─────────────────────────────────────────────────────────────────────────────


def test_mysql_backend_upsert_text_uses_insert_ignore():
    """M4 cutover 전후의 backward-compat — MysqlKbBackend 직접 호출 가능."""
    kb = _load_kb_backend()

    captured = []

    class FakeCursor:
        def __init__(self):
            self.lastrowid = 0
            self.rowcount = 0

        def execute(self, sql, params):
            captured.append((sql, params))

        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    backend = kb.MysqlKbBackend()
    backend.upsert_text(FakeConn(), text_hash="h1", text_content="content")
    assert len(captured) == 1
    sql, params = captured[0]
    assert "INSERT IGNORE INTO AgentMemoryTexts" in sql
    assert params == ("h1", "content")


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 (outside-voice REV-20260520-0008 Critical): caller actual call
# verification — `_text_store_insert()` 가 `_dual_write_kb.upsert_text` 호출.
# ─────────────────────────────────────────────────────────────────────────────


def test_caller_text_store_insert_invokes_mirror(monkeypatch):
    """Caller integration: utils.py:_text_store_insert 가 mirror 호출 invoke."""
    kb = _load_kb_backend()

    # Mirror upsert_text spy
    called = []
    original = kb._dual_write_kb.upsert_text

    def spy(*, text_hash, text_content):
        called.append({"text_hash": text_hash, "text_content": text_content})

    monkeypatch.setattr(kb._dual_write_kb, "upsert_text", spy)

    # Mock cursor for MySQL INSERT (no-op)
    class FakeCursor:
        def execute(self, *a, **kw):
            pass

    # Import caller and invoke
    from modules import utils  # type: ignore

    result_hash = utils._text_store_insert(FakeCursor(), "hello dual-write")

    # Hash 반환 + spy 호출 확인
    assert len(result_hash) == 64  # SHA-256 hex
    assert len(called) == 1
    assert called[0]["text_content"] == "hello dual-write"
    assert called[0]["text_hash"] == result_hash

    # Restore
    monkeypatch.setattr(kb._dual_write_kb, "upsert_text", original)


# ─────────────────────────────────────────────────────────────────────────────
# Test 10 (outside-voice REV-20260520-0008 Nice-to-have): silent log call
# verification — caplog 으로 logger.warning 호출 검증.
# ─────────────────────────────────────────────────────────────────────────────


def test_mirror_silent_log_emits_warning(monkeypatch, caplog):
    """M0~M2-a silent log 패턴: AGENT_KB_PG_REQUIRED=0 시 logger.warning emit."""
    import logging

    kb = _load_kb_backend()
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_available",
        lambda: True,
        raising=True,
    )
    monkeypatch.delenv("AGENT_KB_PG_REQUIRED", raising=False)
    kb._BACKENDS_CACHE = None

    def _connect_fails(*a, **kw):
        raise RuntimeError("simulated pg connect fail")
    monkeypatch.setattr(
        sys.modules["shared.db"],
        "_pg_connect",
        _connect_fails,
        raising=True,
    )

    caplog.set_level(logging.WARNING, logger="agent_core.kb_backend")
    result = kb._dual_write_kb.upsert_text(text_hash="abc", text_content="hello")
    assert result is None
    # Warning log emit 확인
    assert any(
        "kb_pg_mirror: connection failed" in rec.message
        for rec in caplog.records
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 11 (M2-d TASK-0022): pg_branch thread-local tagging — INSERT 와 UPDATE 분기.
# ─────────────────────────────────────────────────────────────────────────────


def test_pg_branch_insert_vs_update(monkeypatch):
    """xmax = 0 returning 으로 INSERT/UPDATE 분기 검출 — thread-local 캡쳐."""
    kb = _load_kb_backend()

    # Fake cursor: returning (id, pg_inserted) tuple
    inserted_value = {"value": True}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            self._sql = sql

        def fetchone(self):
            return (42, inserted_value["value"])

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    backend = kb.PgKbBackend()
    # INSERT branch
    kb._clear_pg_branch()
    backend.upsert_fact_entry(
        FakeConn(),
        conversation_id=None, fact_key="k", scope_key="common", text_hash="h" * 64,
        fact_fingerprint="fp", weight=1,
    )
    assert kb._get_last_pg_branch() == "insert"

    # UPDATE branch
    inserted_value["value"] = False
    kb._clear_pg_branch()
    backend.upsert_fact_entry(
        FakeConn(),
        conversation_id=None, fact_key="k", scope_key="common", text_hash="h" * 64,
        fact_fingerprint="fp", weight=2,
    )
    assert kb._get_last_pg_branch() == "update"


# ─────────────────────────────────────────────────────────────────────────────
# Test 12 (M2-d TASK-0022): mirror latency counter — process-level metrics.
# ─────────────────────────────────────────────────────────────────────────────


def test_mirror_metrics_counter(monkeypatch):
    """_DualWriteMirror 호출이 process-level metrics counter 에 기록."""
    kb = _load_kb_backend()
    kb.reset_mirror_metrics()
    monkeypatch.setattr(
        sys.modules["shared.db"], "_pg_available", lambda: True, raising=True,
    )

    class FakeCursor:
        rowcount = 1  # upsert_text 의 DO NOTHING branch 감지용
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return (1, True)

    class FakeConn:
        def cursor(self): return FakeCursor()
        def close(self): pass

    monkeypatch.setattr(
        sys.modules["shared.db"], "_pg_connect",
        lambda *a, **kw: FakeConn(), raising=True,
    )
    monkeypatch.setattr(kb, "_log_kb_write_audit", lambda **kw: None, raising=True)
    kb._BACKENDS_CACHE = None

    # mirror 3회 호출
    kb._dual_write_kb.upsert_text(text_hash="h" * 64, text_content="t")
    kb._dual_write_kb.upsert_fact_entry(
        conversation_id=None, fact_key="k", scope_key="common", text_hash="h" * 64,
        fact_fingerprint="fp", weight=1,
    )
    kb._dual_write_kb.upsert_text(text_hash="h2" * 32, text_content="t2")

    metrics = kb.get_mirror_metrics()
    assert metrics["calls_total"] == 3, f"calls_total={metrics['calls_total']}"
    assert metrics["calls_by_method"]["upsert_text"] == 2
    assert metrics["calls_by_method"]["upsert_fact_entry"] == 1
    assert metrics["latency_ms_total"] >= 0.0
    assert metrics["latency_ms_avg"] >= 0.0
    assert metrics["audit_calls_total"] == 3
    assert metrics["audit_failures_total"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 12 (TASK-0219): datasource-aware rag_object 파서 — `{source}:ds:{ds}:{suffix}`
# 접두를 분리해 schema/table 정규화 + datasource_key 추출 + object_key ds-접두.
# 과거 회귀: `table_insight:ds:winsql:dbo.X` → schema `dswinsqldbo`(쓰레기), ds 객체 0건.
# ─────────────────────────────────────────────────────────────────────────────


def test_infer_rag_object_datasource_scoped():
    """ds-스코프 fact 키가 깨끗한 schema/table + datasource_key + ds-접두 object_key 로 파싱."""
    from modules import utils  # type: ignore

    # MSSQL ds 테이블 인사이트
    otype, okey, schema, table, col, ds = utils._infer_rag_object_from_fact(
        "table_insight:ds:winsql:dbo.T_ItemLog", ""
    )
    assert otype == "table"
    assert schema == "dbo", f"schema mangled: {schema!r}"  # 과거 'dswinsqldbo' 회귀 방지
    assert table == "T_ItemLog"
    assert ds == "winsql"
    assert okey == "winsql:dbo.T_ItemLog"  # ds-접두로 cross-ds 유일성

    # ds 스키마 인사이트
    otype, okey, schema, table, col, ds = utils._infer_rag_object_from_fact(
        "schema_insight:ds:winsql:dbo", ""
    )
    assert otype == "schema" and schema == "dbo" and ds == "winsql"
    assert okey == "winsql:dbo"

    # 무접두(기본 단일 MySQL) — datasource_key 빈 문자열, object_key 접두 없음
    otype, okey, schema, table, col, ds = utils._infer_rag_object_from_fact(
        "table_insight:dbgame.items", ""
    )
    assert otype == "table" and schema == "dbgame" and table == "items"
    assert ds == ""
    assert okey == "dbgame.items"
