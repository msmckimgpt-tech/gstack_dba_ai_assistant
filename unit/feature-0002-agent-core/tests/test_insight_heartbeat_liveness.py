"""insight-heartbeat-liveness(2026-07-03): 진행-중 heartbeat throttle 갱신 검증.

긴 cycle(대량 테이블 LLM 생성) 동안 `insight_worker_last_cycle_at` heartbeat 가 cycle 완료 시각으로만
갱신돼 stale→unhealthy false-negative 로 오판되던 것을, cycle 진행 중(스키마·테이블 순회) throttle
갱신으로 해소한다. 본 테스트는 throttle 간격 억제·경과 시 저장·mem_conn None no-op·예외 삼킴을
monkeypatch 로 검증(실 DB 불요)."""
from __future__ import annotations


def test_touch_worker_heartbeat_throttle(monkeypatch):
    import modules.insight as insight

    saved = []
    monkeypatch.setattr(insight, "save_memory_kv",
                        lambda conn, cid, k, v: saved.append((k, v)))
    mem = object()  # truthy mem_conn

    # 커서를 오래 전으로 리셋 → 첫 호출은 저장
    insight._LAST_WORKER_HB_MONO[0] = 0.0
    insight._touch_worker_heartbeat_progress(mem, min_interval_sec=30)
    assert len(saved) == 1
    assert saved[0][0] == "insight_worker_last_cycle_at"

    # 방금 저장돼 커서가 now 로 전진 → 즉시 재호출은 throttle 로 억제
    insight._touch_worker_heartbeat_progress(mem, min_interval_sec=30)
    assert len(saved) == 1

    # 커서 리셋(= 간격 경과 시뮬) → 다시 저장
    insight._LAST_WORKER_HB_MONO[0] = 0.0
    insight._touch_worker_heartbeat_progress(mem, min_interval_sec=30)
    assert len(saved) == 2

    # mem_conn None → no-op(비차단)
    insight._touch_worker_heartbeat_progress(None, min_interval_sec=30)
    assert len(saved) == 2


def test_touch_worker_heartbeat_swallows_errors(monkeypatch):
    """save 실패(KV 장애)해도 예외 전파 안 함 — cycle 절대 안 깨뜨림(비차단)."""
    import modules.insight as insight

    def _boom(*a, **k):
        raise RuntimeError("kv down")

    monkeypatch.setattr(insight, "save_memory_kv", _boom)
    insight._LAST_WORKER_HB_MONO[0] = 0.0
    # 예외 없이 반환해야 한다
    insight._touch_worker_heartbeat_progress(object(), min_interval_sec=1)
