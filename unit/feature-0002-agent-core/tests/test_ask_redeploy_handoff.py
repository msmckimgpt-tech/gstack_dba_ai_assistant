"""재배포 인계 봉인 회귀 테스트 (conv-audit FR-ask-orphan-redeploy-dead-air).

배경(실측): 배포는 ask-worker 컨테이너를 `--force-recreate` 한다. 종전 worker id 가
`gethostname()`(=컨테이너 id) 기반이라 재생성 후 `reclaim_worker_jobs_on_boot` 의
자기-이름 일치가 **항상 0행**이었고, 죽은 run 은 전역 stale sweeper 의 STALE_SEC(수백초)
창을 통째로 기다렸다. 60일 8대화에서 dead-air 142~1649s, 3건은 최종 error, 재실행이
사용자 메시지를 중복 저장해 화면에 두 번 보였다(9대화).

봉인 3축을 고정한다:
  A. 종료 시 lease 반납 — `release_worker_jobs_on_shutdown` + drain 종료 경로 호출.
  B. role 기반 identity + 같은 role 의 죽은 이전 인스턴스 회수(`reclaim_role_orphan_jobs`).
  C. 재시도에서 사용자 메시지 중복 저장 억제(`dedup_user_message_since`).

실 PG 없이(make test 는 --no-deps) FakeConn 으로 SQL 계약과 배선을 검증한다.
"""
from __future__ import annotations

import os
import threading

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
        self.executed = []
        self.one_results = list(one_results or [])
        self.all_results = list(all_results or [])

    def cursor(self):
        return FakeCursor(self)

    def last_sql(self):
        return self.executed[-1][0]

    def last_params(self):
        return self.executed[-1][1]


# ── A. 종료 시 lease 반납 ────────────────────────────────────────────────
def test_release_on_shutdown_requeues_with_lease_fencing():
    conn = FakeConn(all_results=[[(7, "c1", "r1"), (8, "c2", "r2")]])
    rows = aj.release_worker_jobs_on_shutdown(
        conn, "ask-worker[ask_worker]-h1-1", attempts_cap=3)
    assert [r["id"] for r in rows] == [7, 8]
    sql = conn.last_sql().upper()
    # 기존 requeue 와 동일한 상태 전이 — 새 status 를 만들지 않는다.
    assert "SET STATUS = 'PENDING'" in sql
    assert "LEASE_EPOCH = LEASE_EPOCH + 1" in sql  # 살아있는 자기 executor fencing
    assert "HEARTBEAT_AT = NULL" in sql
    assert "STATUS = 'RUNNING'" in sql
    # attempts 는 claim 시점 증가분이므로 SET 절에서 건드리지 않는다(cap 이중 소모 방지).
    assert "ATTEMPTS" not in sql.split("WHERE")[0]


def test_release_on_shutdown_respects_attempts_cap():
    """claim SQL 에 cap 게이트가 없으므로, cap 도달 행을 pending 으로 돌리면 무한 재실행."""
    conn = FakeConn(all_results=[[]])
    aj.release_worker_jobs_on_shutdown(conn, "ask-worker[ask_worker]-h1-1", attempts_cap=3)
    sql = conn.last_sql().upper()
    assert "ATTEMPTS < %(CAP)S" in sql
    assert conn.last_params()["cap"] == 3


def test_release_on_shutdown_matches_own_slots_only():
    conn = FakeConn(all_results=[[]])
    aj.release_worker_jobs_on_shutdown(conn, "ask-worker[ask_worker]-h1-1", attempts_cap=3)
    params = conn.last_params()
    assert params["worker"] == "ask-worker[ask_worker]-h1-1"
    # 병렬 executor 는 `<worker_id>#<slot>` 으로 claim → prefix 매칭이 자기 슬롯 전부를 덮는다.
    assert params["worker_like"].endswith("#%")
    # `_` 는 LIKE 와일드카드라 리터럴로 이스케이프돼야 한다(role 명에 흔함: ask_worker).
    assert "ask\\_worker" in params["worker_like"]


def test_release_on_shutdown_noop_on_blank_worker_id():
    conn = FakeConn()
    assert aj.release_worker_jobs_on_shutdown(conn, "", attempts_cap=3) == []
    assert conn.executed == []  # 빈 prefix 로 전체 행을 쓸어버리지 않는다


# ── B. role 기반 고아 회수 ──────────────────────────────────────────────
def test_role_reclaim_excludes_self_and_uses_short_window():
    conn = FakeConn(all_results=[[], [(9, "c9", "r9")]])
    out = aj.reclaim_role_orphan_jobs(
        conn,
        role_prefix="ask-worker[ask_worker]-",
        self_prefix="ask-worker[ask_worker]-new-1",
        stale_seconds=60,
        attempts_cap=3,
    )
    assert [r["id"] for r in out["requeued"]] == [9]
    assert out["errored"] == []
    sql = conn.last_sql().upper()
    assert "CLAIMED_BY LIKE %(ROLE_LIKE)S" in sql
    assert "NOT (CLAIMED_BY = %(SELF)S OR CLAIMED_BY LIKE %(SELF_LIKE)S)" in sql
    assert "HEARTBEAT_AT < NOW() - MAKE_INTERVAL(SECS => %(STALE)S)" in sql
    assert "LEASE_EPOCH = LEASE_EPOCH + 1" in sql
    params = conn.last_params()
    assert params["stale"] == 60
    assert params["role_like"].endswith("%")
    assert params["self_like"].endswith("#%")


def test_role_reclaim_errors_at_attempts_cap_like_global_sweep():
    """cap 회계는 전역 sweep 과 동일해야 한다 — cap 도달은 requeue 가 아니라 terminal error."""
    conn = FakeConn(all_results=[[(11, "c11", "r11")], []])
    out = aj.reclaim_role_orphan_jobs(
        conn, role_prefix="ask-worker[ask_worker]-",
        self_prefix="ask-worker[ask_worker]-new-1", stale_seconds=60, attempts_cap=3)
    assert [r["id"] for r in out["errored"]] == [11]
    assert out["requeued"] == []
    err_sql = conn.executed[0][0].upper()
    req_sql = conn.executed[1][0].upper()
    assert "SET STATUS = 'ERROR'" in err_sql and "ATTEMPTS >= %(CAP)S" in err_sql
    assert "SET STATUS = 'PENDING'" in req_sql and "ATTEMPTS < %(CAP)S" in req_sql


def test_role_reclaim_noop_on_blank_role_or_self_prefix():
    # self_prefix 가 비면 제외 술어가 무력해져 자기 행까지 회수한다 → 호출 자체를 거부.
    for role, self_p in (("", "w"), ("r", ""), ("", "")):
        conn = FakeConn()
        assert aj.reclaim_role_orphan_jobs(
            conn, role_prefix=role, self_prefix=self_p,
            stale_seconds=60, attempts_cap=3) == {"requeued": [], "errored": []}
        assert conn.executed == []


def test_role_prefix_cannot_collide_with_longer_role():
    """`ask-worker-<role>-` 형식은 role `x` 가 role `x-y` 의 job 을 회수할 수 있었다."""
    import modules.ask as ask
    prev = {k: os.environ.get(k) for k in ("AGENT_WORKER_ROLE", "AGENT_SESSION")}
    try:
        os.environ.pop("AGENT_SESSION", None)
        os.environ["AGENT_WORKER_ROLE"] = "ask_worker"
        short_prefix = ask._worker_role_prefix()
        os.environ["AGENT_WORKER_ROLE"] = "ask_worker-blue"
        long_id = ask._worker_id()
        assert not long_id.startswith(short_prefix), (short_prefix, long_id)
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_sanitize_role_is_injective_across_bracket_variants():
    """단순 제거는 비단사 — `x-y` 와 `x]-y` 가 같은 prefix 가 되면 경계가 다시 무너진다."""
    import modules.ask as ask
    assert ask._sanitize_role("ask_worker") == "ask_worker"
    assert ask._sanitize_role("ask_worker-blue") == "ask_worker-blue"
    a = ask._sanitize_role("x-y")
    b = ask._sanitize_role("x]-y")
    assert a != b
    assert "[" not in b and "]" not in b  # 대괄호는 role 안에 절대 들어오지 않는다
    assert ask._sanitize_role("") == "unknown"
    assert ask._sanitize_role("x]-y") == ask._sanitize_role("x]-y")  # 결정적


def test_like_prefix_escapes_wildcards():
    assert aj._like_prefix("ask_worker") == "ask\\_worker"
    assert aj._like_prefix("a%b") == "a\\%b"
    assert aj._like_prefix("a\\b") == "a\\\\b"


# ── B. worker identity 가 컨테이너 재생성에 불변인가 ──────────────────────
def test_worker_role_prefers_compose_injected_session():
    import modules.ask as ask
    prev = {k: os.environ.get(k) for k in ("AGENT_WORKER_ROLE", "AGENT_SESSION")}
    try:
        os.environ.pop("AGENT_WORKER_ROLE", None)
        os.environ["AGENT_SESSION"] = "ask_worker"
        # hostname 이 바뀌어도(=컨테이너 재생성) role prefix 는 그대로여야 한다.
        assert ask._worker_role() == "ask_worker"
        assert ask._worker_role_prefix() == "ask-worker[ask_worker]-"
        assert ask._worker_id().startswith("ask-worker[ask_worker]-")
        os.environ["AGENT_WORKER_ROLE"] = "explicit_role"
        assert ask._worker_role() == "explicit_role"
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_worker_id_falls_back_to_hostname_without_role_env():
    import socket
    import modules.ask as ask
    prev = {k: os.environ.get(k) for k in ("AGENT_WORKER_ROLE", "AGENT_SESSION")}
    try:
        os.environ.pop("AGENT_WORKER_ROLE", None)
        os.environ.pop("AGENT_SESSION", None)
        assert ask._worker_role() == socket.gethostname()
    finally:
        for k, v in prev.items():
            if v is not None:
                os.environ[k] = v


# ── A. 반납 배선(중복 호출 무해 + 실패 흡수) ────────────────────────────
def test_release_own_leases_marks_cancel_and_signals_failure(monkeypatch):
    import modules.ask as ask
    canceled: list = []

    class _C:
        def close(self):
            pass

    def _fake_release(conn, worker_id, *, attempts_cap):
        return [{"id": 1, "conversation_id": "c", "run_id": "r"}]

    monkeypatch.setattr(ask, "_pg", lambda: _C())
    monkeypatch.setattr(ask.ask_jobs, "release_worker_jobs_on_shutdown", _fake_release)
    monkeypatch.setattr(ask, "mark_cancel_requested",
                        lambda conn, cid, run_id="": canceled.append((cid, run_id)))
    assert ask._release_own_leases("w1", reason="t") == 1
    # lease_epoch++ 만으로는 구 executor 가 heartbeat 주기(10s) 뒤에야 멈춘다 — 새 인스턴스는
    # ~0.5s 안에 재claim 하므로 반납 즉시 cancel 을 마킹해 겹침 창을 좁혀야 한다.
    assert canceled == [("c", "r")]

    def _boom(*a, **k):
        raise RuntimeError("pg down")

    monkeypatch.setattr(ask, "_pg", _boom)
    # 예외는 흡수하되 **None** 으로 실패를 알린다 — "0건 반납" 과 구분돼야 재시도가 산다.
    assert ask._release_own_leases("w1", reason="t") is None


def test_shutdown_timer_skips_when_already_released(monkeypatch):
    import modules.ask as ask
    fired = {"n": 0}

    def _fake_release(worker_id, *, reason):
        fired["n"] += 1
        return 0

    monkeypatch.setattr(ask, "_release_own_leases", _fake_release)
    ask._LEASE_RELEASED.set()
    try:
        ask._arm_shutdown_lease_release("w1", 1)
        # 이미 반납 완료 신호가 서 있으면 타이머 스레드 자체를 띄우지 않는다.
        assert fired["n"] == 0
    finally:
        ask._LEASE_RELEASED.clear()


def test_shutdown_timer_releases_after_drain(monkeypatch):
    import modules.ask as ask
    done = threading.Event()

    def _fake_release(worker_id, *, reason):
        done.set()
        return 1

    monkeypatch.setattr(ask, "_release_own_leases", _fake_release)
    ask._LEASE_RELEASED.clear()
    try:
        ask._arm_shutdown_lease_release("w1", 1)
        assert done.wait(10), "drain 예산 경과 후 lease 반납이 일어나야 한다"
        assert ask._LEASE_RELEASED.is_set()
    finally:
        ask._LEASE_RELEASED.clear()


def test_shutdown_timer_keeps_signal_clear_on_failure(monkeypatch):
    """반납 실패를 성공으로 표시하면 메인 종료 경로가 재시도를 건너뛴다."""
    import modules.ask as ask
    tried = threading.Event()

    def _fake_release(worker_id, *, reason):
        tried.set()
        return None  # 실패

    monkeypatch.setattr(ask, "_release_own_leases", _fake_release)
    ask._LEASE_RELEASED.clear()
    try:
        ask._arm_shutdown_lease_release("w1", 1)
        assert tried.wait(10)
        assert not ask._LEASE_RELEASED.is_set()
    finally:
        ask._LEASE_RELEASED.clear()


# ── C. 재시도 시 사용자 메시지 중복 저장 억제 ────────────────────────────
def test_execute_job_passes_dedup_since_only_on_retry(monkeypatch):
    """attempts>1 일 때만 dedup_user_message_since 를 run_agent 로 넘긴다."""
    import datetime as _dt
    import modules.ask as ask

    seen: list[dict] = []

    class _FakeAgentCore:
        @staticmethod
        def run_agent(**kwargs):
            seen.append(kwargs)
            return {"answer": "ok", "conversation_id": kwargs.get("conversation_id")}

        @staticmethod
        def _new_run_id():
            return "run-x"

    import sys
    monkeypatch.setitem(sys.modules, "agent_core", _FakeAgentCore)
    # `**_` — 이 더블은 seam 의 **반환 계약**만 고정한다. 인자를 고정 arity 로 받으면 호출부에
    # 인자가 하나 늘 때마다(예: conv-audit `ask_job_id`) 이 테스트가 그 변화와 무관한 이유로
    # TypeError 를 낸다 — 더블이 계약이 아니라 서명을 잠그는 셈이라 무관한 회귀 신호가 된다.
    monkeypatch.setattr(ask, "_payload_to_kwargs",
                        lambda payload, account_id, run_id, **_: {"user_message": "q"})
    monkeypatch.setattr(ask, "_cleanup_inline_paths", lambda payload: None)
    monkeypatch.setattr(ask, "_postprocess_attachment_blocks",
                        lambda cid, aid, result, run_id: None)
    monkeypatch.setattr(ask, "_finalize_deferred_terminal", lambda cid, run_id, result: None)
    monkeypatch.setattr(ask.ask_jobs, "set_job_run_id", lambda *a, **k: True)
    monkeypatch.setattr(ask.ask_jobs, "finish_ask_job", lambda *a, **k: True)
    monkeypatch.setattr(ask, "_heartbeat_loop", lambda *a, **k: None)

    created = _dt.datetime(2026, 7, 30, 6, 36, 40, tzinfo=_dt.timezone.utc)
    base = {"id": 1, "conversation_id": "c1", "lease_epoch": 1, "account_id": 10,
            "payload": {}, "created_at": created}

    ask._execute_job(FakeConn(), dict(base, attempts=1))
    assert "dedup_user_message_since" not in seen[-1], "첫 시도는 종전 동작(무조건 저장)"

    ask._execute_job(FakeConn(), dict(base, attempts=2))
    assert seen[-1].get("dedup_user_message_since") == created, "재시도는 job 수명 기준 대조"


def test_dedup_helper_is_fail_open_without_since():
    """since=None(첫 실행·web inproc) 이면 조회 없이 빈 판정 → 종전대로 저장."""
    import agent_core
    assert agent_core._user_message_already_persisted("c1", "hi", 10, None) == {}


def test_dedup_helper_fails_open_on_backend_error(monkeypatch):
    """조회 실패는 저장 쪽으로 fail-open — 중복 1행이 요청문 유실보다 안전."""
    import datetime as _dt
    import agent_core
    import modules.runtime_backend as rb

    def _boom(method_name, **kwargs):
        raise RuntimeError("pg down")

    monkeypatch.setattr(rb, "_read_runtime_pg", _boom)
    out = agent_core._user_message_already_persisted(
        "c1", "hi", 10, _dt.datetime(2026, 7, 30, tzinfo=_dt.timezone.utc))
    assert out == {}


def test_user_message_persisted_since_sql_scopes_to_job_lifetime():
    """dedup 조회가 job 수명 이후 구간만 본다 — 과거의 동일 문구는 억제 대상 아님."""
    import modules.runtime_backend as rb
    import datetime as _dt

    backend = rb.PgRuntimeBackend()
    conn = FakeConn(one_results=[(1,), None])
    since = _dt.datetime(2026, 7, 30, tzinfo=_dt.timezone.utc)
    out = backend.user_message_persisted_since(
        conn, conversation_id="c1", content="q", sender_account_id=10, since=since)
    assert out == {"core": True, "display": False}
    core_sql = conn.executed[0][0].upper()
    disp_sql = conn.executed[1][0].upper()
    assert "CREATED_AT >= %(SINCE)S" in core_sql
    assert "ROLE = 'USER'" in core_sql
    assert "IS NOT DISTINCT FROM" in core_sql  # sender NULL 도 동일 취급
    assert "AGENT_RUNTIME.CORE_MESSAGES" in core_sql
    assert "AGENT_RUNTIME.MESSAGES" in disp_sql
    assert "CREATED_AT >= %(SINCE)S" in disp_sql


def test_display_dedup_is_scoped_to_sender_in_group(monkeypatch):
    """그룹에서 다른 멤버가 같은 문장을 보낸 행을 '이미 저장됨' 으로 오인하면 미러가 유실된다."""
    import modules.runtime_backend as rb
    import datetime as _dt

    backend = rb.PgRuntimeBackend()
    since = _dt.datetime(2026, 7, 30, tzinfo=_dt.timezone.utc)

    # 그룹(미러가 발신자를 meta 에 실음) → 발신자까지 일치해야 한다.
    conn = FakeConn(one_results=[None, None])
    backend.user_message_persisted_since(
        conn, conversation_id="c1", content="q", sender_account_id=10,
        since=since, mirror_sender_account_id=10)
    disp_sql = conn.executed[1][0].upper()
    assert "META_JSON ->> 'SENDER_ACCOUNT_ID'" in disp_sql
    assert conn.executed[1][1]["mirror_sender"] == "10"

    # 1:1(미러에 발신자 없음·발신자도 한 명) → NULL 로 들어와 종전 판정 유지.
    conn2 = FakeConn(one_results=[None, None])
    backend.user_message_persisted_since(
        conn2, conversation_id="c1", content="q", sender_account_id=10,
        since=since, mirror_sender_account_id=None)
    assert conn2.executed[1][1]["mirror_sender"] is None


def test_dedup_sql_casts_bare_parameters():
    """POST-DEPLOY 실측 회귀: 타입 컨텍스트 없는 파라미터는 PG 가 쿼리 자체를 거부한다.

    `%(mirror_sender)s IS NULL` 은 `could not determine data type of parameter` 로 실패하고,
    `_read_runtime_pg` 가 그 예외를 흡수해 호출부가 fail-open 저장 → 중복 억제가 **통째로
    무력화**된다(라이브 job 485 재시도에서 실제 발생). 캐스트 존재를 회귀로 고정한다.
    FakeConn 은 실 SQL 을 실행하지 않으므로 이 문자열 고정이 유일한 자동 방어선이다.
    """
    import modules.runtime_backend as rb
    disp = rb._PG_USER_MESSAGE_EXISTS_DISPLAY
    core = rb._PG_USER_MESSAGE_EXISTS_CORE
    assert "%(mirror_sender)s::text IS NULL" in disp
    assert "= %(mirror_sender)s::text" in disp
    assert "%(sender_account_id)s::bigint" in core
    # 캐스트 없는 bare 파라미터가 IS NULL 과 붙어 있으면 안 된다.
    assert "%(mirror_sender)s IS NULL" not in disp


def test_user_message_persisted_since_returns_false_without_since():
    import modules.runtime_backend as rb
    backend = rb.PgRuntimeBackend()
    conn = FakeConn()
    out = backend.user_message_persisted_since(
        conn, conversation_id="c1", content="q", sender_account_id=10, since=None)
    assert out == {"core": False, "display": False}
    assert conn.executed == []


# ── 회귀 고정: 기존 전역 sweep 임계는 건드리지 않았다 ────────────────────
def test_global_stale_window_unchanged_and_role_window_is_narrower():
    from shared.config import (
        AGENT_ASK_WORKER_STALE_SEC,
        AGENT_ASK_WORKER_ROLE_STALE_SEC,
        AGENT_ASK_WORKER_DRAIN_SEC,
        AGENT_ASK_WORKER_HEARTBEAT_SEC,
    )
    # 전역 창은 cross-role false-positive 방지용으로 보수적으로 유지된다.
    assert AGENT_ASK_WORKER_ROLE_STALE_SEC < AGENT_ASK_WORKER_STALE_SEC
    # role 창은 heartbeat 주기의 충분한 배수여야 살아있는 worker 를 오회수하지 않는다.
    assert AGENT_ASK_WORKER_ROLE_STALE_SEC >= AGENT_ASK_WORKER_HEARTBEAT_SEC * 3
    # drain 예산은 compose stop_grace_period(70s) 보다 작아야 반납이 SIGKILL 前에 끝난다.
    assert 0 < AGENT_ASK_WORKER_DRAIN_SEC < 70
