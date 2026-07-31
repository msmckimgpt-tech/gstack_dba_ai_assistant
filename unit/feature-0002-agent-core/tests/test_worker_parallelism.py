"""feature-0025 worker-parallelism — runtime_settings performance 그룹 + 병렬도 accessor 단위 테스트.

DB/LLM 불요(순수). 스냅샷 파일 I/O 는 tmp_path 로 격리한다. 검증 핵심:
  - performance 그룹이 레지스트리·serialize_registry("performance" 버킷)에 등록된다.
  - 기본값이 shared/config.py env 기본값과 동일하다(override 없으면 현행 동작 byte-동치 = opt-in).
  - 신규 동시성(concurrency) accessor 가 기본 1(순차)이고, override 를 [min,max] 로 clamp 한다.
  - ASK_WORKER_CONCURRENCY 는 restart, 나머지 성능 knob 은 live apply_mode.
"""
from __future__ import annotations

import pytest

from shared import runtime_settings as rs


@pytest.fixture
def snap(tmp_path, monkeypatch):
    """격리된 스냅샷 경로 + 캐시 리셋. write(dict) 로 override 를 쓴다. 성능 knob env 오염 제거."""
    path = tmp_path / "runtime_settings.json"
    monkeypatch.setenv("RUNTIME_SETTINGS_SNAPSHOT_PATH", str(path))
    monkeypatch.delenv("RUNTIME_SETTINGS_DISABLED", raising=False)
    # 배포 env(compose anchor/insight-worker 의 TICK=60 등)가 리터럴-기본 검증을 오염시키지 않도록 제거.
    for _k in (
        "AGENT_NODE_ANALYSIS_CONCURRENCY", "AGENT_NODE_ANALYSIS_BATCH_PER_TICK",
        "AGENT_INSIGHT_WORKER_TICK_SEC", "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY",
        "AGENT_METADATA_CLUSTER_INTERVAL_SEC", "AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS",
        "AGENT_ASK_WORKER_CONCURRENCY", "AGENT_ASK_WORKER_IDLE_POLL_MS",
        "AGENT_KB_EMBEDDING_BATCH_MAX_ROWS", "AGENT_KB_EMBEDDING_INTERVAL_SEC",
        "AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP", "AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC",
    ):
        monkeypatch.delenv(_k, raising=False)
    rs._cache["overrides"] = None
    rs._cache["loaded_at"] = 0.0
    rs._cache["frozen"] = None

    def _write(overrides):
        rs.write_snapshot(overrides)

    return _write


PERF_KEYS = {
    "AGENT_NODE_ANALYSIS_CONCURRENCY", "AGENT_NODE_ANALYSIS_BATCH_PER_TICK",
    "AGENT_INSIGHT_WORKER_TICK_SEC", "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY",
    "AGENT_METADATA_CLUSTER_INTERVAL_SEC", "AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS",
    "AGENT_ASK_WORKER_CONCURRENCY", "AGENT_ASK_WORKER_IDLE_POLL_MS",
    "AGENT_KB_EMBEDDING_BATCH_MAX_ROWS", "AGENT_KB_EMBEDDING_INTERVAL_SEC",
    # feature-0016 change-reanalysis(2026-07-27): 사람 confirm 없는 자동 LLM 지출 경로의
    # 라이브 정지 스위치(CAP=0) — env-only 면 폭주 시 재배포해야 멈춘다.
    "AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP", "AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC",
    # worker-resource-isolation T0(2026-07-30): 위 knob 은 **작업별** 병렬도이고 아래는 여러
    # 작업이 함께 쓰는 **자원 총량** 상한 + 전역 정지 스위치다. 상세 계약은
    # test_worker_resource_budget.py.
    "AGENT_BACKGROUND_ANALYSIS_ENABLED", "AGENT_WORKER_LLM_BUDGET",
    # T0b(2026-07-30): 게이트와 함께 추가된 자원 총량 knob.
    "AGENT_WORKER_DS_BUDGET", "AGENT_WORKER_TASK_BUDGET",
    # feature-0032 llm-token-budget(2026-07-30): 사람 confirm 없는 자동 LLM 지출의 24h 상한.
    "AGENT_BACKGROUND_LLM_TOKEN_CAP_24H",
    # feature-0033 analysis-synthesis(2026-07-30): L2 클러스터 합성 요약 생성 스위치.
    "AGENT_METADATA_CLUSTER_SUMMARY",
    # feature-0034 analysis-consumption(2026-07-30): L2 요약의 답변 grounding 주입 스위치.
    "AGENT_CLUSTER_SUMMARY_GROUNDING",
    # feature-0031 analysis-grounding(2026-07-30): 분석 증거 수집의 사용 여부와 깊이 상한.
    #   운영 DB read 부하가 여기서 나므로 재배포 없이 조절·정지할 수 있어야 한다.
    "AGENT_METADATA_STATS_ENABLED", "AGENT_METADATA_STATS_MAX_STAGE",
    "AGENT_METADATA_STATS_DAY_MAX_STAGE", "AGENT_METADATA_STATS_REFRESH_HOURS",
}


# ── 레지스트리 ──────────────────────────────────────────────────────────────
def test_performance_group_registered():
    reg = rs.serialize_registry({})
    assert "performance" in reg, "serialize_registry 에 performance 버킷이 있어야 한다"
    keys = {row["key"] for row in reg["performance"]}
    assert keys == PERF_KEYS, f"performance 버킷 키 불일치: {keys ^ PERF_KEYS}"
    # 성능 항목이 timeouts 등 다른 버킷으로 새지 않아야 한다(전용 서브탭 렌더 정합).
    other = set()
    for bucket in ("timeouts", "model_thinking_budgets", "reasoning_budgets", "redteam", "agent_max_outputs"):
        other |= {row["key"] for row in reg.get(bucket, [])}
    assert not (PERF_KEYS & other), "성능 knob 이 다른 버킷에 중복 노출되면 안 된다"


def test_performance_categories():
    reg = rs.serialize_registry({})
    cats = {row["category"] for row in reg["performance"]}
    assert cats == {"그래프 노드 분석", "cluster_label(클러스터 라벨)", "사용자 답변 처리",
                    "지식베이스 임베딩", "자원 격리·관측"}


def test_exposed_knob_defaults_track_config():
    """리뷰 FINDING-B: 기존 config 상수를 노출하는 knob 은 spec default 가 config 값과 **실측 일치**해야
    한다(리터럴 하드코딩 대조가 아니라 shared.config import 대조 — config default 드리프트를 강제로 잡는다).
    env 로 해당 키를 설정하지 않은 표준 테스트 환경에서 config 상수 = 코드 리터럴 기본값."""
    import os
    from shared import config as cfg
    exposed = {
        "AGENT_NODE_ANALYSIS_BATCH_PER_TICK": cfg.AGENT_NODE_ANALYSIS_BATCH_PER_TICK,
        "AGENT_INSIGHT_WORKER_TICK_SEC": cfg.AGENT_INSIGHT_WORKER_TICK_SEC,
        "AGENT_METADATA_CLUSTER_INTERVAL_SEC": cfg.AGENT_METADATA_CLUSTER_INTERVAL_SEC,
        "AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS": cfg.AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS,
        "AGENT_KB_EMBEDDING_BATCH_MAX_ROWS": cfg.AGENT_KB_EMBEDDING_BATCH_MAX_ROWS,
        "AGENT_KB_EMBEDDING_INTERVAL_SEC": cfg.AGENT_KB_EMBEDDING_INTERVAL_SEC,
        "AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP": cfg.AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP,
        "AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC": cfg.AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC,
    }
    for key, cfg_val in exposed.items():
        if os.getenv(key) is not None:
            continue  # env override 된 특수 환경 — 리터럴 대조 대상 아님(baseline 은 env 존중이 정상)
        assert rs.spec_for(key)["default"] == cfg_val, (
            f"{key}: spec default({rs.spec_for(key)['default']}) != config({cfg_val}) — byte-동치 드리프트")


def test_new_knob_defaults_opt_in():
    """신규(registry-only) knob 은 config 상수가 없다 — 기본값이 현행 동작(순차/현 폴링)과 동치인 리터럴."""
    assert rs.spec_for("AGENT_NODE_ANALYSIS_CONCURRENCY")["default"] == 1
    assert rs.spec_for("AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY")["default"] == 1
    assert rs.spec_for("AGENT_ASK_WORKER_CONCURRENCY")["default"] == 1
    # idle-poll MS 기본 500 == 기존 AGENT_ASK_WORKER_IDLE_POLL_SEC(0.5s) 와 동치.
    from shared import config as cfg
    assert rs.spec_for("AGENT_ASK_WORKER_IDLE_POLL_MS")["default"] == 500
    assert abs(cfg.AGENT_ASK_WORKER_IDLE_POLL_SEC - 0.5) < 1e-9


def test_apply_modes():
    # 동시 답변 처리 수는 루프 진입 시 1회 읽는 스레드풀 크기 → restart. 나머지는 live(매 tick 재조회).
    assert rs.spec_for("AGENT_ASK_WORKER_CONCURRENCY")["apply_mode"] == "restart"
    for k in ("AGENT_NODE_ANALYSIS_CONCURRENCY", "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY",
              "AGENT_NODE_ANALYSIS_BATCH_PER_TICK", "AGENT_INSIGHT_WORKER_TICK_SEC",
              "AGENT_METADATA_CLUSTER_INTERVAL_SEC", "AGENT_ASK_WORKER_IDLE_POLL_MS"):
        assert rs.spec_for(k)["apply_mode"] == "live", k


def test_concurrency_bounds():
    assert rs.spec_for("AGENT_NODE_ANALYSIS_CONCURRENCY")["maximum"] == 8
    assert rs.spec_for("AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY")["maximum"] == 4
    assert rs.spec_for("AGENT_ASK_WORKER_CONCURRENCY")["maximum"] == 8
    for k in ("AGENT_NODE_ANALYSIS_CONCURRENCY", "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY",
              "AGENT_ASK_WORKER_CONCURRENCY"):
        assert rs.spec_for(k)["minimum"] == 1


# ── accessor: 기본(opt-in) + override + clamp ────────────────────────────────
def test_accessors_default_sequential(snap):
    """override 없으면 전부 순차(1) — 현행 동작 opt-in 보장."""
    assert rs.node_analysis_concurrency() == 1
    assert rs.cluster_label_concurrency() == 1
    assert rs.ask_worker_concurrency() == 1
    assert rs.ask_worker_idle_poll_sec() == 0.5


def test_accessors_reflect_override(snap):
    snap({
        "AGENT_NODE_ANALYSIS_CONCURRENCY": 4,
        "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY": 3,
        "AGENT_ASK_WORKER_CONCURRENCY": 6,
        "AGENT_ASK_WORKER_IDLE_POLL_MS": 200,
    })
    assert rs.node_analysis_concurrency() == 4
    assert rs.cluster_label_concurrency() == 3
    assert rs.ask_worker_concurrency() == 6
    assert rs.ask_worker_idle_poll_sec() == 0.2


def test_override_clamped_to_max(snap):
    # 위험값(풀 소진 유발) 주입 시 스펙 상한으로 clamp — get_int 경로.
    snap({
        "AGENT_NODE_ANALYSIS_CONCURRENCY": 999,
        "AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY": 999,
        "AGENT_ASK_WORKER_CONCURRENCY": 999,
    })
    assert rs.node_analysis_concurrency() == 8
    assert rs.cluster_label_concurrency() == 4
    assert rs.ask_worker_concurrency() == 8


def test_validate_value_rejects_out_of_range():
    ok, _v, err = rs.validate_value("AGENT_ASK_WORKER_CONCURRENCY", 99)
    assert not ok and "범위" in (err or "")
    ok, v, err = rs.validate_value("AGENT_ASK_WORKER_CONCURRENCY", 4)
    assert ok and v == 4 and err is None


def test_batch_per_tick_override_live(snap):
    snap({"AGENT_NODE_ANALYSIS_BATCH_PER_TICK": 40})
    assert rs.get_int("AGENT_NODE_ANALYSIS_BATCH_PER_TICK") == 40


def test_idle_poll_override_presence_signal(snap):
    """MAJOR-2 fix: ask.py _current_idle_poll 은 read_overrides() 에 MS 키가 있을 때만 신규 accessor 를
    쓰고, 없으면 legacy AGENT_ASK_WORKER_IDLE_POLL_SEC 로 폴백한다 — 그 존재 신호를 검증."""
    assert "AGENT_ASK_WORKER_IDLE_POLL_MS" not in rs.read_overrides()
    snap({"AGENT_ASK_WORKER_IDLE_POLL_MS": 250})
    assert "AGENT_ASK_WORKER_IDLE_POLL_MS" in rs.read_overrides()
    assert rs.ask_worker_idle_poll_sec() == 0.25
