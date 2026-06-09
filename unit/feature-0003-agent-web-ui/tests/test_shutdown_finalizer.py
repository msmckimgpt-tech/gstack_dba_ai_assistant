"""TASK-0164 회귀 테스트 — SIGTERM graceful shutdown finalizer.

배경:
  `/api/ask` 는 agent 를 `asyncio.to_thread` 로 web 프로세스 안에서 in-process 실행한다.
  web 재배포/`docker stop`(SIGTERM)이 in-flight run 을 죽이면 terminal status 미도달 →
  KV `last_status='processing'` 영구 고착(orphan). `_finalize_inflight_runs_on_shutdown`
  (@app.on_event("shutdown"))이 종료 시점에 *이 프로세스가 시작한* processing run 을
  error 로 마킹해 orphan 을 차단한다. 부팅 reconciliation 과 대칭:
    - 부팅 hook: `last_status_at <  _PROCESS_BOOT_UTC` (이전 프로세스 고아) 정리
    - 종료 hook: `last_status_at >= _PROCESS_BOOT_UTC` (이 프로세스 run) 정리

테스트:
  S1 이 프로세스의 processing run(>= boot) → set_run_status('error', shutdown 메시지) 호출.
  S2 부팅 이전(< boot) run → 종료 hook 은 건드리지 않음(부팅 hook 담당).
  S3 race 가드: 마킹 직전 재조회가 terminal(done)이면 덮어쓰지 않음.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

from datetime import timedelta

import app


class _FakeConn:
    def close(self):
        return None


def _make_load_kv(store):
    """store: {(cid, key): value} → load_memory_kv(conn, cid, key) 모킹.
    프로덕션 load_memory_kv 는 미존재 키에 "" 를 반환하므로 기본값을 "" 로 맞춘다."""
    def _load(conn, cid, key, default=""):
        return store.get((cid, key), default)
    return _load


def _patch_common(monkeypatch, cids, kv, calls):
    monkeypatch.setattr(app, "_open_memory_connection", lambda: _FakeConn())
    monkeypatch.setattr(app, "list_processing_conversation_ids", lambda conn: list(cids))
    monkeypatch.setattr(app, "load_memory_kv", _make_load_kv(kv))
    monkeypatch.setattr(
        app, "set_run_status",
        lambda conn, cid, status, **k: calls.append((cid, status, k)),
    )


# ── S1: 이 프로세스의 진행중 run 정리 ───────────────────────────────────────
def test_shutdown_finalizer_marks_this_process_processing(monkeypatch):
    after_boot = (app._PROCESS_BOOT_UTC + timedelta(seconds=5)).isoformat()
    cid = "c-live"
    kv = {
        (cid, "last_status_at"): after_boot,
        (cid, "last_status"): "processing",
        (cid, "last_status_run_id"): "rid1",
    }
    calls: list = []
    _patch_common(monkeypatch, [cid], kv, calls)

    app._finalize_inflight_runs_on_shutdown()

    assert len(calls) == 1
    marked_cid, status, kwargs = calls[0]
    assert marked_cid == cid
    assert status == "error"
    assert kwargs.get("run_id") == "rid1"
    assert kwargs.get("error") == app._SHUTDOWN_FINALIZE_MESSAGE


# ── S2: 부팅 이전 run 은 종료 hook 이 건드리지 않음 ─────────────────────────
def test_shutdown_finalizer_skips_pre_boot_runs(monkeypatch):
    before_boot = (app._PROCESS_BOOT_UTC - timedelta(minutes=30)).isoformat()
    cid = "c-orphan"
    kv = {
        (cid, "last_status_at"): before_boot,
        (cid, "last_status"): "processing",
        (cid, "last_status_run_id"): "rid2",
    }
    calls: list = []
    _patch_common(monkeypatch, [cid], kv, calls)

    app._finalize_inflight_runs_on_shutdown()

    assert calls == []  # 부팅 reconciliation 담당 — 종료 hook 은 제외


# ── S3: race 가드 — 막 완료된 run 은 덮어쓰지 않음 ──────────────────────────
def test_shutdown_finalizer_race_guard_skips_just_finished(monkeypatch):
    after_boot = (app._PROCESS_BOOT_UTC + timedelta(seconds=5)).isoformat()
    cid = "c-done"
    # last_status_at 은 >= boot 이지만, 마킹 직전 재조회에서 이미 terminal(done).
    kv = {
        (cid, "last_status_at"): after_boot,
        (cid, "last_status"): "done",
        (cid, "last_status_run_id"): "rid3",
    }
    calls: list = []
    _patch_common(monkeypatch, [cid], kv, calls)

    app._finalize_inflight_runs_on_shutdown()

    assert calls == []  # 에이전트의 정상 terminal 을 덮어쓰지 않음
