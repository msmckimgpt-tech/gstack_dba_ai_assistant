"""TASK-0108 Sprint 3 — modules.kb_ingest unit test.

FakeConn / FakeCursor 패턴으로 실 MySQL 없이 ingest_manual() 의 SQL 흐름 검증.

검증 항목:
1. happy path (신규 ScopeKey → INSERT IGNORE Texts + INSERT FactEntries, superseded=0)
2. ScopeKey 충돌 → UPDATE Weight=0 (supersede) + 새 row INSERT (superseded_count=N)
3. 동일 본문 재ingest → ON DUPLICATE KEY UPDATE (reactivated=True, superseded_count -=1)
4. scope_key empty → ValueError
5. body empty → ValueError
6. scope_key length > 96 → ValueError
7. SHA256/SHA1 정규화 결정 (FactFingerprint 가 whitespace 둔감)
"""

from __future__ import annotations

import hashlib
import pytest


# conftest.py 가 sys.path 통합.
from modules import kb_ingest  # type: ignore


class _FakeCursor:
    def __init__(self, existing_rows=None, fetchone_payloads=None):
        """existing_rows: SELECT ... FOR UPDATE 가 반환할 (Id, Weight, FactFingerprint) tuple list.

        kb_ingest.py 의 4-step 흐름:
          1) INSERT IGNORE Texts → rowcount 무시
          2) SELECT FOR UPDATE → fetchall() 가 existing_rows 반환
          3) UPDATE WHERE Id IN (...) (existing_active_ids 있을 때만) → supersede_count
          4) INSERT FactEntries ON DUPLICATE KEY UPDATE Id=LAST_INSERT_ID(Id) → lastrowid
        """
        self.queries = []
        self.params = []
        self._rowcount = 0
        self.lastrowid = 0
        self._existing_rows = list(existing_rows or [])
        self._fetchone_payloads = list(fetchone_payloads or [])

    def execute(self, sql, params=()):
        self.queries.append(sql.strip())
        self.params.append(tuple(params) if isinstance(params, (list, tuple)) else params)
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT ID, WEIGHT, FACTFINGERPRINT"):
            self._rowcount = len(self._existing_rows)
            self._last_select_fetchall = list(self._existing_rows)
        elif sql_upper.startswith("UPDATE AGENTMEMORYFACTENTRIES"):
            # Step 3: WHERE Id IN (...) — params length = active row count.
            params_tuple = tuple(params) if isinstance(params, (list, tuple)) else (params,)
            self._rowcount = len(params_tuple)
        elif sql_upper.startswith("INSERT INTO AGENTMEMORYFACTENTRIES"):
            self._rowcount = 1
            self.lastrowid = getattr(self, "_insert_lastrowid", 42)
        else:
            self._rowcount = 1

    @property
    def rowcount(self):
        return self._rowcount

    def fetchall(self):
        rows = getattr(self, "_last_select_fetchall", [])
        self._last_select_fetchall = []
        return rows

    def fetchone(self):
        if self._fetchone_payloads:
            return self._fetchone_payloads.pop(0)
        return None

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor
        self.commits = 0

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def _make_conn(existing_rows=None, insert_lastrowid=100):
    """existing_rows: kb_ingest.py 의 SELECT FOR UPDATE 가 볼 기존 row 목록.

    각 entry: (Id, Weight, FactFingerprint) tuple.
    """
    cur = _FakeCursor(existing_rows=existing_rows)
    cur._insert_lastrowid = insert_lastrowid
    return _FakeConn(cur), cur


def test_happy_path_new_scope():
    """1차 ingest — 기존 row 없음 → SELECT FOR UPDATE 가 빈 결과 → UPDATE skip → INSERT FactEntries."""
    conn, cur = _make_conn(existing_rows=[], insert_lastrowid=101)
    result = kb_ingest.ingest_manual(
        conn,
        scope_key="products.orders",
        body="# Orders\n\nThis is the canonical orders schema reference.",
        source_filename="orders.md",
        source_sha256="a" * 64,
    )
    assert result["fact_entry_id"] == 101
    assert result["superseded_count"] == 0
    assert result["reactivated"] is False
    assert len(result["text_hash"]) == 64
    assert len(result["fact_fingerprint"]) == 40
    # 본 cycle 흐름: INSERT IGNORE Texts → SELECT FOR UPDATE → INSERT FactEntries
    # (active row 없으면 UPDATE skip). 즉 3 statement.
    assert len(cur.queries) >= 3
    assert "INSERT IGNORE INTO AGENTMEMORYTEXTS" in cur.queries[0].upper()
    assert "SELECT ID, WEIGHT, FACTFINGERPRINT" in cur.queries[1].upper()
    assert "FOR UPDATE" in cur.queries[1].upper()
    assert "INSERT INTO AGENTMEMORYFACTENTRIES" in cur.queries[-1].upper()


def test_scope_key_collision_supersedes():
    """2차 ingest 의 동일 ScopeKey — 기존 active row 3건 + 다른 fingerprint → 3 supersede + 새 INSERT."""
    existing = [
        (101, 90, "old_fp_1" + "0" * 32),
        (102, 90, "old_fp_2" + "0" * 32),
        (103, 90, "old_fp_3" + "0" * 32),
    ]
    conn, cur = _make_conn(existing_rows=existing, insert_lastrowid=205)
    result = kb_ingest.ingest_manual(
        conn,
        scope_key="products.orders",
        body="UPDATED orders schema with new column.",
    )
    assert result["fact_entry_id"] == 205
    assert result["superseded_count"] == 3
    assert result["reactivated"] is False
    # UPDATE Id IN (...) 의 params 가 3건.
    update_calls = [
        (q, p) for q, p in zip(cur.queries, cur.params)
        if q.strip().upper().startswith("UPDATE AGENTMEMORYFACTENTRIES")
    ]
    assert len(update_calls) == 1
    assert len(update_calls[0][1]) == 3


def test_reactivate_same_body():
    """동일 본문 재ingest — 동일 fingerprint 의 row 가 active 상태로 존재.

    SELECT FOR UPDATE 가 (777, 90, fp) 반환 → reactivated=True. superseded_count
    는 active 였으므로 1 demote 후 자기 자신 차감 = 0.
    """
    body = "User schema body content."
    fp = kb_ingest._compute_fact_fingerprint(body)
    existing = [(777, 90, fp)]
    conn, cur = _make_conn(existing_rows=existing, insert_lastrowid=777)
    result = kb_ingest.ingest_manual(
        conn,
        scope_key="products.users",
        body=body,
    )
    assert result["fact_entry_id"] == 777
    assert result["reactivated"] is True
    assert result["superseded_count"] == 0  # 1 active demote - 1 self


def test_mixed_supersede_and_reactivate():
    """기존 active 2건 + 동일 fp inactive 1건 → reactivated=True, superseded_count=2 (자기 inactive 차감 안 됨)."""
    body = "canonical body text"
    fp = kb_ingest._compute_fact_fingerprint(body)
    existing = [
        (501, 90, "other_fp_1" + "0" * 30),
        (502, 90, "other_fp_2" + "0" * 30),
        (503, 0, fp),  # 이전에 supersede 된 동일 본문
    ]
    conn, cur = _make_conn(existing_rows=existing, insert_lastrowid=503)
    result = kb_ingest.ingest_manual(
        conn,
        scope_key="products.x",
        body=body,
    )
    assert result["fact_entry_id"] == 503
    assert result["reactivated"] is True
    # active 2건 demote → superseded_count=2. 자기 fp row 는 inactive 였으므로 차감 안 함.
    assert result["superseded_count"] == 2


def test_scope_key_empty():
    conn, _ = _make_conn()
    with pytest.raises(ValueError):
        kb_ingest.ingest_manual(conn, scope_key="", body="x")
    with pytest.raises(ValueError):
        kb_ingest.ingest_manual(conn, scope_key="   ", body="x")


def test_body_empty():
    conn, _ = _make_conn()
    with pytest.raises(ValueError):
        kb_ingest.ingest_manual(conn, scope_key="x", body="")
    with pytest.raises(ValueError):
        kb_ingest.ingest_manual(conn, scope_key="x", body="   \n\t")


def test_scope_key_too_long():
    conn, _ = _make_conn()
    with pytest.raises(ValueError):
        kb_ingest.ingest_manual(conn, scope_key="a" * 97, body="x")


def test_fact_fingerprint_normalization():
    """동일 의미 body (whitespace 다름) 는 동일 fingerprint."""
    fp1 = kb_ingest._compute_fact_fingerprint("Hello World")
    fp2 = kb_ingest._compute_fact_fingerprint("  hello   world  ")
    fp3 = kb_ingest._compute_fact_fingerprint("HELLO\tWORLD\n")
    assert fp1 == fp2 == fp3
    # 실 다른 body 는 다른 fingerprint.
    fp4 = kb_ingest._compute_fact_fingerprint("Hello Word")
    assert fp1 != fp4


def test_text_hash_deterministic():
    body = "canonical body"
    h1 = kb_ingest._compute_text_hash(body)
    h2 = kb_ingest._compute_text_hash(body)
    assert h1 == h2
    assert h1 == hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_default_constants():
    assert kb_ingest.KB_MANUAL_CONVERSATION_ID == "__kb_manual__"
    assert kb_ingest.DEFAULT_MANUAL_WEIGHT == 90
    assert kb_ingest.DEFAULT_SOURCE_TYPE == "manual"
