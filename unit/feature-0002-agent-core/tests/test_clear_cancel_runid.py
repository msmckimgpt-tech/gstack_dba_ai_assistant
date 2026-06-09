"""_clear_cancel_request run-id 스코프 가드 (TASK-0169 MJ-2).

ask-worker fencing 은 lease 박탈된 worker(run R1)를 멈추려 cancel 을 R1 으로 마킹한다.
같은 conversation 의 새 worker(run R2)가 종료하며 무조건 clear 하면 R1 대상 cancel 이
지워져 R1 이 계속 돈다(double-run). cancel_run_id 가 다른 run 이면 clear 를 막아야 한다.
"""
from __future__ import annotations

import modules.memory as memory


class _KV:
    """save/load 를 메모리 dict 로 대체 — 실 PG 없이 _clear_cancel_request 로직 검증."""
    def __init__(self, initial=None):
        self.store = dict(initial or {})

    def save(self, conn, cid, key, value):
        self.store[(cid, key)] = value

    def load(self, conn, cid, key):
        return self.store.get((cid, key), "")


def _patch(monkeypatch, kv):
    monkeypatch.setattr(memory, "save_memory_kv", kv.save)
    monkeypatch.setattr(memory, "load_memory_kv", kv.load)


def test_clear_skipped_when_cancel_targets_other_run(monkeypatch):
    kv = _KV({("c", "cancel_requested"): "1", ("c", "cancel_run_id"): "R1"})
    _patch(monkeypatch, kv)
    # R2 가 종료하며 clear 시도 → R1 대상 cancel 은 보존돼야 함.
    memory._clear_cancel_request(None, "c", run_id="R2")
    assert kv.load(None, "c", "cancel_requested") == "1"
    assert kv.load(None, "c", "cancel_run_id") == "R1"


def test_clear_runs_when_same_run(monkeypatch):
    kv = _KV({("c", "cancel_requested"): "1", ("c", "cancel_run_id"): "R1"})
    _patch(monkeypatch, kv)
    memory._clear_cancel_request(None, "c", run_id="R1")
    assert kv.load(None, "c", "cancel_requested") == ""
    assert kv.load(None, "c", "cancel_run_id") == ""


def test_clear_runs_when_no_run_id_arg(monkeypatch):
    # 하위호환: run_id 미지정이면 현행처럼 무조건 clear.
    kv = _KV({("c", "cancel_requested"): "1", ("c", "cancel_run_id"): "R1"})
    _patch(monkeypatch, kv)
    memory._clear_cancel_request(None, "c")
    assert kv.load(None, "c", "cancel_requested") == ""


def test_clear_runs_when_cancel_run_empty(monkeypatch):
    # untargeted cancel(빈 run_id)은 어느 run 이든 clear 가능.
    kv = _KV({("c", "cancel_requested"): "1", ("c", "cancel_run_id"): ""})
    _patch(monkeypatch, kv)
    memory._clear_cancel_request(None, "c", run_id="R9")
    assert kv.load(None, "c", "cancel_requested") == ""
