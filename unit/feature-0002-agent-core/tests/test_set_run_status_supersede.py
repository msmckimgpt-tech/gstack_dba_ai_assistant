"""set_run_status only_if_current_run supersede 가드 (TASK-0241).

취소→즉시 재요청 시, 뒤늦게 종료하는 old(취소된) run 의 terminal write 가 새 run 이
인계한 last_status_run_id 를 덮어쓰지 못하게 한다. claim/sentinel 선기록 같은 정당한
takeover 는 only_if_current_run=False(기본)로 무조건 write 를 유지한다.
"""
from __future__ import annotations

import modules.memory as memory


class _KV:
    """save/load 를 메모리 dict 로 대체 — 실 PG 없이 set_run_status 가드 로직 검증."""
    def __init__(self, initial=None):
        self.store = dict(initial or {})

    def save(self, conn, cid, key, value):
        self.store[(cid, key)] = value

    def load(self, conn, cid, key):
        return self.store.get((cid, key), "")


def _patch(monkeypatch, kv):
    monkeypatch.setattr(memory, "save_memory_kv", kv.save)
    monkeypatch.setattr(memory, "load_memory_kv", kv.load)


def test_guard_skips_when_current_run_differs(monkeypatch):
    # 새 run(R_new)이 인계한 상태를 old(R_old)의 terminal write 가 덮으면 안 된다.
    kv = _KV({("c", "last_status_run_id"): "R_new", ("c", "last_status"): "processing"})
    _patch(monkeypatch, kv)
    memory.set_run_status(None, "c", "canceled", run_id="R_old", only_if_current_run=True)
    assert kv.load(None, "c", "last_status") == "processing"
    assert kv.load(None, "c", "last_status_run_id") == "R_new"


def test_guard_allows_when_current_run_matches(monkeypatch):
    kv = _KV({("c", "last_status_run_id"): "R1", ("c", "last_status"): "processing"})
    _patch(monkeypatch, kv)
    memory.set_run_status(None, "c", "canceled", run_id="R1", only_if_current_run=True)
    assert kv.load(None, "c", "last_status") == "canceled"
    assert kv.load(None, "c", "last_status_run_id") == "R1"


def test_guard_allows_when_no_current_run(monkeypatch):
    # last_status_run_id 가 비어 있으면(첫 기록 등) 가드 비활성 — 정상 기록.
    kv = _KV({("c", "last_status_run_id"): "", ("c", "last_status"): "processing"})
    _patch(monkeypatch, kv)
    memory.set_run_status(None, "c", "canceled", run_id="R1", only_if_current_run=True)
    assert kv.load(None, "c", "last_status") == "canceled"


def test_default_is_unconditional_takeover(monkeypatch):
    # only_if_current_run=False(기본): claim/sentinel 선기록 같은 정당한 takeover 는 무조건 write.
    kv = _KV({("c", "last_status_run_id"): "R_old", ("c", "last_status"): "canceled"})
    _patch(monkeypatch, kv)
    memory.set_run_status(None, "c", "processing", run_id="R_new")
    assert kv.load(None, "c", "last_status") == "processing"
    assert kv.load(None, "c", "last_status_run_id") == "R_new"


def test_sentinel_then_takeover_then_orphan_skip(monkeypatch):
    """BLOCKER 시퀀스: cancel→재요청 enqueue(sentinel)→worker claim(R_new)→orphan bail(R_old).

    최종적으로 새 run 의 (R_new, processing) 가 보존되고 orphan 의 canceled 는 skip 돼야 한다.
    """
    kv = _KV({("c", "last_status_run_id"): "R_old", ("c", "last_status"): "canceled"})
    _patch(monkeypatch, kv)
    # 1) 재요청 enqueue 선기록 — sentinel run_id(무조건 takeover).
    memory.set_run_status(None, "c", "processing", run_id="enqpre-deadbeef")
    assert kv.load(None, "c", "last_status_run_id") == "enqpre-deadbeef"
    # 2) worker claim — 실제 R_new 로 무조건 덮어씀.
    memory.set_run_status(None, "c", "processing", run_id="R_new")
    assert kv.load(None, "c", "last_status_run_id") == "R_new"
    # 3) orphan(R_old) bail terminal write — 가드로 skip(새 run 보존).
    memory.set_run_status(None, "c", "canceled", run_id="R_old", only_if_current_run=True)
    assert kv.load(None, "c", "last_status") == "processing"
    assert kv.load(None, "c", "last_status_run_id") == "R_new"
