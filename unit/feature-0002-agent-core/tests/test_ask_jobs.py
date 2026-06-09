"""ask_jobs 큐 헬퍼 단위 테스트 (TASK-0169).

실 PG 없이(make test 는 --no-deps) FakeConn 으로 SQL 계약 + 반환 파싱을 검증한다.
핵심 안전 불변식(adversarial review 흡수)을 "SQL 에 그 절이 존재하는가" 로 회귀 고정:
  - claim 은 단일문 FOR UPDATE SKIP LOCKED (BLOCKER 2 double-claim 방지).
  - heartbeat/finish/set_run_id 는 lease_epoch 가드 (BLOCKER 3 fencing).
  - enqueue 는 단일문 INSERT…SELECT…WHERE count<limit (MAJOR 5 TOCTOU 방지) + stale 제외.
  - sweep 은 cap 초과→error / 미만→requeue(lease++) 2-statement.
"""
from __future__ import annotations

import json

import modules.ask_jobs as aj


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return self.conn.one_results.pop(0) if self.conn.one_results else None

    def fetchall(self):
        return self.conn.all_results.pop(0) if self.conn.all_results else []


class FakeConn:
    def __init__(self, one_results=None, all_results=None):
        self.executed = []  # [(sql, params)]
        self.one_results = list(one_results or [])
        self.all_results = list(all_results or [])

    def cursor(self):
        return FakeCursor(self)

    def last_sql(self):
        return self.executed[-1][0]

    def last_params(self):
        return self.executed[-1][1]


# ── claim: 단일문 atomic (BLOCKER 2) ──────────────────────────────────────
def test_claim_sql_is_single_statement_skip_locked():
    conn = FakeConn(one_results=[None])  # pending 없음
    assert aj.claim_ask_job(conn, "w1") is None
    sql = conn.last_sql().upper()
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "UPDATE AGENT_RUNTIME.ASK_JOBS" in sql
    assert "LEASE_EPOCH = LEASE_EPOCH + 1" in sql
    # SELECT...FOR UPDATE 가 UPDATE 서브쿼리 안 — 별도 SELECT/UPDATE 2문이 아님.
    assert sql.count("UPDATE AGENT_RUNTIME.ASK_JOBS") == 1


def test_claim_parses_json_payload_row():
    payload = {"user_message": "hi", "model": "edge"}
    row = (7, "conv-1", None, 42, json.dumps(payload), 3, 1)
    conn = FakeConn(one_results=[row])
    job = aj.claim_ask_job(conn, "w1")
    assert job["id"] == 7
    assert job["conversation_id"] == "conv-1"
    assert job["account_id"] == 42
    assert job["payload"] == payload  # str→dict 파싱
    assert job["lease_epoch"] == 3
    assert job["attempts"] == 1


def test_claim_accepts_dict_payload_row():
    # psycopg3 jsonb 는 dict 로 올 수 있음 — 그 경로도 처리.
    payload = {"user_message": "x"}
    row = (1, "c", "run-1", 9, payload, 0, 1)
    conn = FakeConn(one_results=[row])
    job = aj.claim_ask_job(conn, "w1")
    assert job["payload"] == payload
    assert job["run_id"] == "run-1"


# ── enqueue: 단일문 slot enforce (MAJOR 5) ────────────────────────────────
def test_enqueue_single_statement_slot_guard():
    conn = FakeConn(one_results=[(101,)])
    jid = aj.enqueue_ask_job(
        conn, conversation_id="c", run_id=None, account_id=5,
        payload={"a": 1}, account_limit=6, stale_seconds=300,
    )
    assert jid == 101
    sql = conn.last_sql().upper()
    assert sql.startswith("INSERT INTO AGENT_RUNTIME.ASK_JOBS")
    assert "SELECT" in sql and "WHERE (" in sql
    assert "< %(LIMIT)S" in sql  # count < limit 가드
    assert "MAKE_INTERVAL" in sql  # stale 제외 술어
    params = conn.last_params()
    assert params["limit"] == 6 and params["account_id"] == 5
    assert params["payload"] == json.dumps({"a": 1})
    assert params["run_id"] is None


def test_enqueue_returns_none_when_slot_full():
    conn = FakeConn(one_results=[None])  # WHERE count<limit 불만족 → 0 row
    jid = aj.enqueue_ask_job(
        conn, conversation_id="c", run_id=None, account_id=5,
        payload={}, account_limit=6, stale_seconds=300,
    )
    assert jid is None


# ── lease fencing (BLOCKER 3) ─────────────────────────────────────────────
def test_heartbeat_is_lease_guarded():
    conn = FakeConn(one_results=[(1,)])
    assert aj.heartbeat_ask_job(conn, 1, 4) is True
    sql = conn.last_sql().upper()
    assert "LEASE_EPOCH = %(LEASE)S" in sql and "STATUS = 'RUNNING'" in sql
    # lease 박탈 시 0 row → False
    conn2 = FakeConn(one_results=[None])
    assert aj.heartbeat_ask_job(conn2, 1, 4) is False


def test_finish_is_lease_guarded_and_validates_status():
    conn = FakeConn(one_results=[(1,)])
    assert aj.finish_ask_job(conn, 1, 2, "done", {"answer": "a"}) is True
    assert "LEASE_EPOCH = %(LEASE)S" in conn.last_sql().upper()
    conn2 = FakeConn(one_results=[None])
    assert aj.finish_ask_job(conn2, 1, 2, "error") is False
    # 잘못된 terminal status 거부
    try:
        aj.finish_ask_job(FakeConn(), 1, 2, "running")
        assert False, "invalid status 가 통과됨"
    except ValueError:
        pass


def test_set_job_run_id_lease_guarded():
    conn = FakeConn(one_results=[(1,)])
    assert aj.set_job_run_id(conn, 1, 3, "run-x") is True
    sql = conn.last_sql().upper()
    assert "SET RUN_ID = %(RUN_ID)S" in sql and "LEASE_EPOCH = %(LEASE)S" in sql


# ── stale sweeper: cap→error / 미만→requeue ───────────────────────────────
def test_sweep_separates_error_and_requeue():
    # 1st execute(error) → fetchall 반환, 2nd execute(requeue) → fetchall 반환
    conn = FakeConn(all_results=[
        [(10, "c10", "r10")],          # errored (cap 초과)
        [(11, "c11", "r11"), (12, "c12", "r12")],  # requeued
    ])
    out = aj.sweep_stale_jobs(conn, stale_seconds=300, attempts_cap=3)
    assert [r["id"] for r in out["errored"]] == [10]
    assert [r["id"] for r in out["requeued"]] == [11, 12]
    sqls = " ".join(s for s, _ in conn.executed).upper()
    assert "ATTEMPTS >= %(CAP)S" in sqls   # error 분기
    assert "ATTEMPTS < %(CAP)S" in sqls    # requeue 분기
    assert "LEASE_EPOCH = LEASE_EPOCH + 1" in sqls  # requeue fencing


# ── cancel-pending (2g) ───────────────────────────────────────────────────
def test_cancel_pending_only_targets_pending():
    conn = FakeConn(all_results=[[(20, "r20"), (21, "r21")]])
    out = aj.cancel_pending_jobs(conn, "conv-9")
    assert [r["id"] for r in out] == [20, 21]
    sql = conn.last_sql().upper()
    assert "SET STATUS = 'CANCELED'" in sql and "STATUS = 'PENDING'" in sql


# ── ownership lookup (B1) ─────────────────────────────────────────────────
def test_has_active_job_for_conversation():
    assert aj.has_active_job_for_conversation(FakeConn(one_results=[(1,)]), "c") is True
    assert aj.has_active_job_for_conversation(FakeConn(one_results=[None]), "c") is False
    conn = FakeConn(one_results=[(1,)])
    aj.has_active_job_for_conversation(conn, "c")
    assert "STATUS IN ('PENDING','RUNNING')" in conn.last_sql().upper()


def test_active_inline_paths_excludes_terminal(monkeypatch):
    # MJ-1: 활성 job 의 inline 경로만 수집 → reaper 가 read-after-delete 안 하도록.
    conn = FakeConn(all_results=[[
        ("/shared/ask-inline/a.json", None),
        (None, "/shared/ask-inline/b.json"),
        (None, None),
    ]])
    paths = aj.active_inline_paths(conn)
    assert paths == {"/shared/ask-inline/a.json", "/shared/ask-inline/b.json"}
    sql = conn.last_sql().upper()
    assert "STATUS IN ('PENDING','CLAIMED','RUNNING')" in sql


def test_reclaim_worker_jobs_on_boot():
    conn = FakeConn(all_results=[[(1,), (2,)]])
    assert aj.reclaim_worker_jobs_on_boot(conn, "w1") == 2
    assert "CLAIMED_BY = %(WORKER)S" in conn.last_sql().upper()


def test_ask_jobs_table_exists():
    # to_regclass 가 True → 존재, None/False → 미존재. (boot 시 오해성 DDL 경고 회피용)
    assert aj.ask_jobs_table_exists(FakeConn(one_results=[(True,)])) is True
    assert aj.ask_jobs_table_exists(FakeConn(one_results=[(False,)])) is False
    conn = FakeConn(one_results=[(True,)])
    aj.ask_jobs_table_exists(conn)
    assert "TO_REGCLASS('AGENT_RUNTIME.ASK_JOBS')" in conn.last_sql().upper()


# ── 멱등 DDL ───────────────────────────────────────────────────────────────
def test_ensure_ask_jobs_idempotent_ddl():
    conn = FakeConn()
    aj._ensure_ask_jobs(conn)
    sql = conn.last_sql().upper()
    assert "CREATE TABLE IF NOT EXISTS AGENT_RUNTIME.ASK_JOBS" in sql
    assert "CREATE INDEX IF NOT EXISTS IX_ASK_JOBS_CLAIM" in sql
