"""TASK-0289 — _compute_duration_breakdown 회귀 테스트.

배경: 표시 수행시간이 LLM 루프(run_start 기준)만 집계해 큐 대기·초기화가 빠지고,
실측 45초가 화면엔 25초로 줄어 보이던 불일치. breakdown 은 queued/init/inference 를
분해하고 total(=사용자 체감 end-to-end)을 헤드라인으로 낸다. 본 테스트는 그 산수를
결정적으로 고정한다(perf 값을 합성 주입).
"""
from __future__ import annotations

import agent_core


def test_breakdown_full_phases():
    # agent 진입 t=100.0s, 초기화 3.5s 후 추론 시작(103.5), 추론 25s 후 종료(128.5).
    # 큐 대기는 worker seed 로 2000ms 주입.
    bd = agent_core._compute_duration_breakdown(
        queued_ms=2000.0,
        agent_entry_perf=100.0,
        run_start=103.5,
        now_perf=128.5,
    )
    assert bd["queued_ms"] == 2000.0
    assert bd["init_ms"] == 3500.0
    assert bd["inference_ms"] == 25000.0
    # total = 큐 대기 + (종료-진입) = 2000 + 28500 = 30500
    assert bd["total_ms"] == 30500.0
    # total 은 항상 queued + init + inference 합과 일치(부동소수 반올림 허용).
    assert abs(bd["total_ms"] - (bd["queued_ms"] + bd["init_ms"] + bd["inference_ms"])) < 0.5


def test_breakdown_inprocess_no_queue():
    # in-process(큐 없음): queued=0, total=init+inference.
    bd = agent_core._compute_duration_breakdown(
        queued_ms=0.0,
        agent_entry_perf=10.0,
        run_start=11.0,
        now_perf=21.0,
    )
    assert bd["queued_ms"] == 0.0
    assert bd["init_ms"] == 1000.0
    assert bd["inference_ms"] == 10000.0
    assert bd["total_ms"] == 11000.0


def test_breakdown_clamps_negative_and_none():
    # run_start < agent_entry(있을 수 없는 음수 구간) 와 queued=None 은 0 으로 안전 클램프.
    bd = agent_core._compute_duration_breakdown(
        queued_ms=None,
        agent_entry_perf=50.0,
        run_start=49.0,  # 음수 init → 0
        now_perf=50.0,
    )
    assert bd["queued_ms"] == 0.0
    assert bd["init_ms"] == 0.0
    assert bd["inference_ms"] >= 0.0
    assert bd["total_ms"] >= 0.0
