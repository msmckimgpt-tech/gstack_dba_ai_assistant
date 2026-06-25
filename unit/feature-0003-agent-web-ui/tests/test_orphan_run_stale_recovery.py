"""TASK-0159 회귀 테스트 — 고아 run 무한 폴링 (tz stale 버그 + 부팅 reconciliation).

배경:
  `/api/ask` 는 agent 를 `asyncio.to_thread` 로 web 프로세스 안에서 in-process 실행한다.
  web 재배포/재시작이 진행 중 ask 를 죽이면 `set_run_status("done")` 미도달 → KV
  `last_status='processing'` 영구 고착. 프런트엔드(ask_result/progress)는 terminal 을
  못 받아 무한 폴링하고, `last_status='processing'` 이 신규 질의(409)도 막는다.

  근본 결함은 2가지:
    ① `_last_step_at_for_run` 의 CHG-20260527-0001 회귀 — PG timestamptz(KST aware)를
       UTC 변환 없이 `replace(tzinfo=None)` 으로 strip → KST wall-clock 이 UTC 로 오인 →
       `_compute_display_status` 의 `datetime.utcnow()` 비교에서 elapsed 가 음수 → stale
       가드(20분)가 step 을 만든 run 에는 영원히 안 터짐.
    ② startup orphan reconciliation 부재 — 새 프로세스엔 살아있는 run 이 없으므로 부팅 전
       부터 processing 이던 KV 는 전부 고아인데, 정리 로직이 없었다.

테스트:
  T1 `_last_step_at_for_run`: PG aware KST datetime → 올바른 UTC naive 반환 (회귀 가드).
  T2 `_compute_display_status`: 오래된 step (>timeout) → ('stale_error', True); 최근 → ('processing', False).
  T3 startup reconciliation boot-guard 시맨틱: boot 이후 시작된 run 은 건드리지 않는다.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import app


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a, **k):
        return None

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def cursor(self):
        return _FakeCursor(self._row)

    def close(self):
        return None


# ── T1: tz 회귀 — PG aware(KST) → UTC naive ────────────────────────────────
def test_last_step_at_for_run_converts_aware_kst_to_utc_naive(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    kst = timezone(timedelta(hours=9))
    aware_kst = datetime(2026, 6, 8, 14, 33, 30, tzinfo=kst)  # = 05:33:30 UTC
    monkeypatch.setattr("shared.db._pg_connect", lambda: _FakeConn((aware_kst,)))

    result = app._last_step_at_for_run(None, "cid", "rid")

    assert result is not None
    assert result.tzinfo is None, "stale 비교(datetime.utcnow())와 정합하려면 naive 여야 함"
    # 핵심: KST wall-clock(14:33)이 아니라 UTC(05:33)로 변환돼야 한다.
    assert result == datetime(2026, 6, 8, 5, 33, 30)
    assert result != datetime(2026, 6, 8, 14, 33, 30), "회귀: tzinfo 만 strip 하면 안 됨"


def test_last_step_at_for_run_passes_through_naive(monkeypatch):
    """이미 naive(UTC) 인 값은 그대로 통과 (MySQL 패리티 / 방어)."""
    monkeypatch.setenv("AGENT_RUNTIME_READ_BACKEND", "postgres")
    naive = datetime(2026, 6, 8, 5, 33, 30)
    monkeypatch.setattr("shared.db._pg_connect", lambda: _FakeConn((naive,)))
    assert app._last_step_at_for_run(None, "cid", "rid") == naive


# ── T2: stale 가드 — 수정 후 정상 동작 ──────────────────────────────────────
def test_compute_display_status_marks_old_processing_stale(monkeypatch):
    now = datetime.utcnow()
    old = now - timedelta(seconds=app.WEB_PROGRESS_STALE_TIMEOUT_SECONDS + 120)
    monkeypatch.setattr(app, "_last_step_at_for_run", lambda *a, **k: old)
    status, is_stale = app._compute_display_status(
        None, "cid", "processing", old.isoformat(), "rid"
    )
    assert (status, is_stale) == ("stale_error", True)


def test_compute_display_status_keeps_recent_processing_live(monkeypatch):
    now = datetime.utcnow()
    recent = now - timedelta(seconds=30)
    monkeypatch.setattr(app, "_last_step_at_for_run", lambda *a, **k: recent)
    status, is_stale = app._compute_display_status(
        None, "cid", "processing", recent.isoformat(), "rid"
    )
    assert (status, is_stale) == ("processing", False)


def test_compute_display_status_terminal_passthrough():
    """processing 이 아닌 상태는 그대로 통과 (stale 판정 대상 아님)."""
    assert app._compute_display_status(None, "cid", "done", "", "rid") == ("done", False)
    assert app._compute_display_status(None, "cid", "error", "", "rid") == ("error", False)


# ── T3: startup reconciliation boot-guard 시맨틱 ────────────────────────────
def test_orphan_reconcile_boot_guard_semantics():
    """부팅 이후 시작된 run 은 reconciliation 대상에서 제외돼야 한다.

    실제 hook 의 가드는 `parsed >= _PROCESS_BOOT_UTC` 이면 skip. 여기서는 그 판정에
    쓰이는 `_parse_kv_timestamp` 출력이 boot 기준과 올바르게 비교되는지 확인한다.
    """
    boot = datetime.utcnow()
    before_boot = (boot - timedelta(minutes=30)).isoformat()
    after_boot = (boot + timedelta(seconds=5)).isoformat()

    parsed_before = app._parse_kv_timestamp(before_boot)
    parsed_after = app._parse_kv_timestamp(after_boot)

    assert parsed_before is not None and parsed_after is not None
    # boot 이전 → reconcile 대상 (skip 아님)
    assert not (parsed_before >= boot)
    # boot 이후 → skip (이 프로세스가 시작한 run)
    assert parsed_after >= boot
