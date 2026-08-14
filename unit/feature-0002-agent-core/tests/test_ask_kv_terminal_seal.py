"""조기 종료 run 의 KV terminal 봉인 (conv-audit FR-early-return-kv-never-finalized).

사용자 보고(2026-08-14): 첨부 2건을 올리고 쿼리 리뷰를 요청했는데 "5분이 지나도 시작
자체가 진행되지 않는" 상태. 실제로는 job 이 0.12초 만에 `error` 로 끝났고(primary
datasource 회로차단), KV `last_status` 만 `processing` + enqueue sentinel 로 남아
`/api/ask_result` 가 45초 주기로 무한 폴링했다.

근본: `run_agent` 는 KV 를 실제 run_id 로 인계하기 **전**에 `result["error"]` 만 채우고
예외 없이 정상 return 하는 조기 종료 경로가 여럿인데, 워커의 KV 마감은
`raised` / `_deferred_terminal` / resume-giveup 세 갈래뿐이라 이를 전부 놓쳤다.

여기서는 봉인 A(`_ensure_kv_terminal`)와 봉인 B(`latest_terminal_job_for_conversation`)
의 계약을 고정한다.
"""
from __future__ import annotations

import json

import modules.ask as ask
import modules.ask_jobs as aj


# ── 봉인 A: 워커의 KV terminal 최종 보장 ─────────────────────────────────────
class _KV:
    """set_run_status/load_memory_kv 를 메모리 dict 로 대체(실 PG 불요)."""

    def __init__(self, initial=None):
        self.store = dict(initial or {})
        self.writes = []  # [(status, run_id, error)]

    def load(self, conn, cid, key):
        return self.store.get((cid, key), "")

    def set_status(self, conn, cid, status, run_id="", duration_ms=None,
                   error=None, only_if_current_run=False):
        self.writes.append((status, run_id, error))
        self.store[(cid, "last_status")] = status
        if run_id:
            self.store[(cid, "last_status_run_id")] = run_id


def _patch(monkeypatch, kv):
    monkeypatch.setattr(ask, "load_memory_kv", kv.load)
    monkeypatch.setattr(ask, "set_run_status", kv.set_status)


def test_early_return_with_enqueue_sentinel_is_finalized(monkeypatch):
    """회귀 재현: KV=processing + `enqpre-` sentinel 인 조기 종료 run 을 error 로 마감.

    이 케이스가 봉인 전 사용자 dead-air 의 원인이었다 — sentinel 을 "다른 run 이 인계했다"
    로 오인해 건너뛰면 봉인이 성립하지 않는다.
    """
    kv = _KV({("c", "last_status"): "processing",
              ("c", "last_status_run_id"): "enqpre-ff866eeec0dd"})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R1", {"error": "데이터소스 응답이 지연되고 있습니다."}, False)
    assert kv.store[("c", "last_status")] == "error"
    assert kv.store[("c", "last_status_run_id")] == "R1"
    assert kv.writes[-1][2] == "데이터소스 응답이 지연되고 있습니다."


def test_no_op_when_already_terminal(monkeypatch):
    # 정상 경로가 마감한 done 을 덮으면 성공 턴이 실패로 뒤집힌다.
    kv = _KV({("c", "last_status"): "done", ("c", "last_status_run_id"): "R1"})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R1", {"answer": "완료"}, False)
    assert kv.writes == []
    assert kv.store[("c", "last_status")] == "done"


def test_skips_when_other_real_run_took_over(monkeypatch):
    # supersede 가드: 다른 실제 run 이 대화 상태 슬롯을 인계했으면 건드리지 않는다.
    kv = _KV({("c", "last_status"): "processing", ("c", "last_status_run_id"): "R_new"})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R_old", {"error": "boom"}, False)
    assert kv.writes == []
    assert kv.store[("c", "last_status")] == "processing"


def test_finalizes_own_run(monkeypatch):
    kv = _KV({("c", "last_status"): "processing", ("c", "last_status_run_id"): "R1"})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False)
    assert kv.store[("c", "last_status")] == "error"


def test_finalizes_when_kv_run_id_empty(monkeypatch):
    kv = _KV({("c", "last_status"): "processing", ("c", "last_status_run_id"): ""})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False)
    assert kv.store[("c", "last_status")] == "error"


def test_answer_without_error_is_finalized_as_done(monkeypatch):
    """답변이 있는데 KV 마감만 실패한 run 을 error 로 적으면 성공 턴을 날조하게 된다."""
    kv = _KV({("c", "last_status"): "processing", ("c", "last_status_run_id"): "R1"})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R1", {"answer": "리뷰 결과입니다."}, False)
    assert kv.store[("c", "last_status")] == "done"
    assert kv.writes[-1][2] == ""


def test_missing_error_and_answer_gets_default_message(monkeypatch):
    kv = _KV({("c", "last_status"): "processing", ("c", "last_status_run_id"): "enqpre-x"})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R1", {}, False)
    assert kv.store[("c", "last_status")] == "error"
    assert kv.writes[-1][2]  # 빈 문구로 마감하지 않는다(프런트가 원인을 표시해야 함)


def test_load_failure_does_not_write(monkeypatch):
    """판정 불가 상태에서 무조건 write 하면 다른 run 의 상태를 덮을 수 있다."""
    writes = []

    def _boom(conn, cid, key):
        raise RuntimeError("kv down")

    monkeypatch.setattr(ask, "load_memory_kv", _boom)
    monkeypatch.setattr(ask, "set_run_status",
                        lambda *a, **k: writes.append((a, k)))
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False)
    assert writes == []


# ── 봉인 B: ask_jobs terminal backstop ──────────────────────────────────────
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


class FakeConn:
    def __init__(self, one_results=None):
        self.executed = []
        self.one_results = list(one_results or [])

    def cursor(self):
        return FakeCursor(self)


def test_backstop_returns_none_when_active_job_exists():
    """새 요청이 진행 중인데 직전 run 의 terminal 을 돌려주면 답변을 끊는다."""
    conn = FakeConn(one_results=[(1,)])  # 활성 job 존재
    assert aj.latest_terminal_job_for_conversation(conn, "c") is None
    # 활성 확인 1회로 끝나야 한다(불필요한 2차 조회 없음).
    assert len(conn.executed) == 1
    assert "status IN ('pending','claimed','running')" in conn.executed[0][0]


def test_backstop_active_set_includes_claimed():
    """§18.8 codex [P1]: claim~running 창을 활성에서 빠뜨리면 진행 중 답변을 끊는다."""
    conn = FakeConn(one_results=[(1,)])
    aj.latest_terminal_job_for_conversation(conn, "c")
    assert "'claimed'" in conn.executed[0][0]


def test_other_active_job_probe_excludes_self():
    conn = FakeConn(one_results=[None])
    assert aj.has_other_active_job_for_conversation(conn, "c", 683) is False
    sql, params = conn.executed[-1]
    assert "id <> %(jid)s" in sql and params["jid"] == 683
    assert "'claimed'" in sql


def test_backstop_returns_latest_terminal_job():
    conn = FakeConn(one_results=[
        None,                                                    # 활성 job 없음
        (683, "20260814063132-70b86fc1", "error",
         json.dumps({"error": "데이터소스 응답이 지연되고 있습니다.", "answer": ""}), None),
    ])
    got = aj.latest_terminal_job_for_conversation(conn, "c")
    assert got["id"] == 683
    assert got["status"] == "error"
    assert got["error"] == "데이터소스 응답이 지연되고 있습니다."
    assert got["run_id"] == "20260814063132-70b86fc1"
    sql = conn.executed[-1][0]
    assert "status IN ('done','error','canceled')" in sql
    assert "ORDER BY id DESC" in sql   # 최신 1건 — created_at 은 동시 INSERT 에 비결정적


def test_backstop_returns_none_when_no_job_at_all():
    conn = FakeConn(one_results=[None, None])
    assert aj.latest_terminal_job_for_conversation(conn, "c") is None


def test_backstop_tolerates_unparsable_result_json():
    conn = FakeConn(one_results=[None, (1, "R1", "error", "<not json>", None)])
    got = aj.latest_terminal_job_for_conversation(conn, "c")
    assert got["status"] == "error"
    assert got["error"] == ""   # 파싱 실패는 흡수 — terminal 해소 자체는 유지


# ── 봉인 C: 조기 종료도 대화에 흔적을 남긴다 ────────────────────────────────
def _patch_core(monkeypatch, *, writes_allowed=True, dup=None, save_raises=False):
    import agent_core

    saved, mirrored, statuses = [], [], []

    def _save(conn, cid, role, content=None, **kw):
        if save_raises:
            raise RuntimeError("store down")
        saved.append((role, content))

    monkeypatch.setattr(agent_core, "_writes_allowed", lambda conn, cid: writes_allowed)
    monkeypatch.setattr(agent_core, "_save_message", _save)
    monkeypatch.setattr(agent_core, "_mirror_message",
                        lambda conn, cid, role, content, run_id="", **kw:
                        mirrored.append((role, content)))
    monkeypatch.setattr(agent_core, "set_run_status",
                        lambda conn, cid, status, **kw:
                        statuses.append((status, kw.get("error"), kw.get("run_id"))))
    monkeypatch.setattr(agent_core, "_user_message_already_persisted",
                        lambda *a, **k: dict(dup or {}))
    monkeypatch.setattr(agent_core, "_lookup_account_username", lambda conn, aid: "u1")
    return agent_core, saved, mirrored, statuses


def test_early_exit_persists_question_and_error(monkeypatch):
    """회귀 재현: 조기 종료가 사용자 질문조차 남기지 않아 "시작도 안 된" 것처럼 보였다."""
    core, saved, mirrored, statuses = _patch_core(monkeypatch)
    core._persist_early_exit(None, "c", "R1", "데이터소스 응답이 지연되고 있습니다.",
                             "쿼리 리뷰를 진행해주세요.", 10)
    assert ("user", "쿼리 리뷰를 진행해주세요.") in saved
    assert any(r == "assistant" and "데이터소스 응답이 지연" in (c or "") for r, c in saved)
    assert ("user", "쿼리 리뷰를 진행해주세요.") in mirrored
    assert statuses[-1][0] == "error"
    assert statuses[-1][2] == "R1"


def test_early_exit_respects_dedup_on_retry(monkeypatch):
    # job 재시도에서 요청문이 두 줄로 보이던 결함(FR-ask-orphan-redeploy-dead-air RC-2) 재발 방지.
    core, saved, mirrored, _ = _patch_core(monkeypatch, dup={"core": True, "display": True})
    core._persist_early_exit(None, "c", "R1", "boom", "같은 질문", 10,
                             dedup_user_message_since="2026-08-14T00:00:00Z")
    assert ("user", "같은 질문") not in saved
    assert ("user", "같은 질문") not in mirrored
    assert any(r == "assistant" for r, _ in saved)   # 오류 안내는 그대로 남긴다


def test_early_exit_finalizes_kv_even_when_store_write_fails(monkeypatch):
    """대화 기록이 실패해도 KV 마감은 반드시 이뤄져야 한다 — 아니면 무한 폴링이 남는다."""
    core, _, _, statuses = _patch_core(monkeypatch, save_raises=True)
    core._persist_early_exit(None, "c", "R1", "boom", "질문", 10)
    assert statuses[-1][0] == "error"


def test_early_exit_finalizes_kv_when_writes_not_allowed(monkeypatch):
    # 읽기 전용(공유/차단) 대화라도 KV 는 마감한다.
    core, saved, _, statuses = _patch_core(monkeypatch, writes_allowed=False)
    core._persist_early_exit(None, "c", "R1", "boom", "질문", 10)
    assert saved == []
    assert statuses[-1][0] == "error"


def test_early_exit_noop_without_conversation():
    import agent_core
    agent_core._persist_early_exit(None, "", "R1", "boom", "질문", 10)   # 예외 없이 no-op


# ── §18.8 codex [P1] 반영분 회귀 ─────────────────────────────────────────────
class _ProbeConn:
    """has_other_active_job_for_conversation 만 대역 — 봉인 A 의 sentinel 소유 판정용."""

    def __init__(self, other_active: bool, raises: bool = False):
        self.other_active = other_active
        self.raises = raises


def _patch_probe(monkeypatch, conn):
    def _probe(c, cid, jid):
        if c.raises:
            raise RuntimeError("pg down")
        return c.other_active
    monkeypatch.setattr(aj, "has_other_active_job_for_conversation", _probe)


def test_sentinel_not_finalized_when_another_job_is_active(monkeypatch):
    """취소→즉시 재요청 창: 새 요청의 sentinel 을 내 terminal 로 덮으면 그 요청이 죽는다."""
    kv = _KV({("c", "last_status"): "processing",
              ("c", "last_status_run_id"): "enqpre-other"})
    _patch(monkeypatch, kv)
    conn = _ProbeConn(other_active=True)
    _patch_probe(monkeypatch, conn)
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False, conn=conn, job_id=683)
    assert kv.writes == []
    assert kv.store[("c", "last_status")] == "processing"


def test_sentinel_finalized_when_no_other_active_job(monkeypatch):
    kv = _KV({("c", "last_status"): "processing",
              ("c", "last_status_run_id"): "enqpre-mine"})
    _patch(monkeypatch, kv)
    conn = _ProbeConn(other_active=False)
    _patch_probe(monkeypatch, conn)
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False, conn=conn, job_id=683)
    assert kv.store[("c", "last_status")] == "error"


def test_sentinel_probe_failure_holds_off(monkeypatch):
    """소유 판정 불가면 보수적으로 보류 — 남은 무한 대기는 stale 창이 받는다."""
    kv = _KV({("c", "last_status"): "processing",
              ("c", "last_status_run_id"): "enqpre-x"})
    _patch(monkeypatch, kv)
    conn = _ProbeConn(other_active=False, raises=True)
    _patch_probe(monkeypatch, conn)
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False, conn=conn, job_id=683)
    assert kv.writes == []


def test_raised_run_is_error_even_with_answer(monkeypatch):
    """run_agent 가 예외로 끝났으면 부분 answer 가 남아 있어도 성공이 아니다(job 전이도 error)."""
    kv = _KV({("c", "last_status"): "processing", ("c", "last_status_run_id"): "R1"})
    _patch(monkeypatch, kv)
    ask._ensure_kv_terminal("c", "R1", {"answer": "partial"}, True)
    assert kv.store[("c", "last_status")] == "error"


def test_supersede_guard_enabled_when_kv_points_to_own_run(monkeypatch):
    """KV 가 내 run 이면 판정~write 사이 인계를 가드로 막는다(race 창 축소)."""
    seen = {}

    def _set(conn, cid, status, run_id="", duration_ms=None, error=None,
             only_if_current_run=False):
        seen["guard"] = only_if_current_run

    monkeypatch.setattr(ask, "load_memory_kv",
                        lambda c, cid, k: {"last_status": "processing",
                                           "last_status_run_id": "R1"}[k])
    monkeypatch.setattr(ask, "set_run_status", _set)
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False)
    assert seen["guard"] is True


def test_supersede_guard_disabled_for_sentinel(monkeypatch):
    """sentinel 에 가드를 켜면 곧 skip 이라 봉인 자체가 무력화된다."""
    seen = {}

    def _set(conn, cid, status, run_id="", duration_ms=None, error=None,
             only_if_current_run=False):
        seen["guard"] = only_if_current_run

    monkeypatch.setattr(ask, "load_memory_kv",
                        lambda c, cid, k: {"last_status": "processing",
                                           "last_status_run_id": "enqpre-x"}[k])
    monkeypatch.setattr(ask, "set_run_status", _set)
    ask._ensure_kv_terminal("c", "R1", {"error": "boom"}, False)
    assert seen["guard"] is False
