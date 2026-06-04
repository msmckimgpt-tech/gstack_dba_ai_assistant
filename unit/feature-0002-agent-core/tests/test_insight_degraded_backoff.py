"""TASK-0147 — insight worker degraded read-back backoff.

read 정본(PG) 부재 시 `_insight_readback_degraded()` 가 True 를 반환해 cycle 이
생성을 skip(status=degraded_readback) 하고 loop 가 긴 backoff 를 적용하도록 하는
가드를 검증한다. 실 DB 없이 monkeypatch 로만 분기 확인.

배경: cutover 이후 insight read-back(artifact 검증·fingerprint 맵)의 정본은 PG.
PG 부재 시 read-back 이 (DROP 된) MySQL fallback 으로 떨어져 모든 artifact/fingerprint
가 missing/changed 로 오판 → 무한 재생성(livelock) 동력. 이 가드가 그 재발을 차단.
"""
from __future__ import annotations


def test_degraded_false_when_mysql_backend(monkeypatch):
    import modules.config as cfg
    import modules.runtime_backend as rb
    import modules.insight as insight

    monkeypatch.setattr(cfg, "AGENT_KB_READ_BACKEND", "mysql", raising=False)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "mysql", raising=False)
    # MySQL 모드면 read-back 이 live mem_conn 을 쓰므로 불일치 없음 → PG probe 안 함.
    assert insight._insight_readback_degraded() is False


def test_degraded_true_when_pg_unavailable(monkeypatch):
    import modules.config as cfg
    import modules.insight as insight

    monkeypatch.setattr(cfg, "AGENT_KB_READ_BACKEND", "postgres", raising=False)
    monkeypatch.setattr(insight, "_pg_available", lambda: False)
    assert insight._insight_readback_degraded() is True


def test_degraded_true_when_pg_probe_fails(monkeypatch):
    import modules.config as cfg
    import modules.insight as insight

    monkeypatch.setattr(cfg, "AGENT_KB_READ_BACKEND", "postgres", raising=False)
    monkeypatch.setattr(insight, "_pg_available", lambda: True)

    def _boom(*a, **k):
        raise RuntimeError("pg connection refused")

    monkeypatch.setattr(insight, "_pg_connect_ro", _boom)
    assert insight._insight_readback_degraded() is True


def test_degraded_false_when_pg_probe_ok(monkeypatch):
    import modules.config as cfg
    import modules.insight as insight

    monkeypatch.setattr(cfg, "AGENT_KB_READ_BACKEND", "postgres", raising=False)
    monkeypatch.setattr(insight, "_pg_available", lambda: True)

    class _Cur:
        def execute(self, *a, **k):
            return None

        def fetchone(self):
            return (1,)

        def close(self):
            return None

    class _Conn:
        def cursor(self):
            return _Cur()

        def close(self):
            return None

    monkeypatch.setattr(insight, "_pg_connect_ro", lambda *a, **k: _Conn())
    assert insight._insight_readback_degraded() is False
