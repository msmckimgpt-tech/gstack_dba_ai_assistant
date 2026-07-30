"""feature-0025 worker-resource-isolation (T0) — 공유 자원 예산·kill-switch·계측 단위 테스트.

DB/LLM 불요(순수). 스냅샷 파일 I/O 는 tmp_path 로 격리한다. 검증 핵심:
  - 예산 게이트가 상한 안에서 통과하고 초과 시 **거절(False)** 한다 — 예외가 아니라 fail-soft.
  - `available()` 가 여유를 정확히 보고한다(호출측 claim clamp 의 근거).
  - 상한 변경이 **live 반영**되고, 상한을 내려도 이미 점유 중인 분은 강제 회수되지 않는다.
  - 미등록 자원 키는 게이트 없이 통과(fail-open) — 오타가 작업을 조용히 막지 않는다.
  - kill-switch: 설정 0 → 비활성, **조회 실패 → 활성**(fail-open — 설정 장애가 워커를 멈추지 않게).
  - ★회귀: `process_pending` 이 kill-switch 0 일 때 **claim 자체를 하지 않는다**
    (change-reanalysis cap==0 이 "신규만 차단"이라 적재분을 계속 소진했던 결함의 반복 금지).
  - 기본 상한이 현행 최대 동시성 이상이라 게이트가 발동하지 않는다(배포 시점 byte-동치).
"""
from __future__ import annotations

import threading

import pytest

from shared import resource_budget as rb
from shared import runtime_settings as rs


@pytest.fixture
def snap(tmp_path, monkeypatch):
    """격리된 스냅샷 경로 + 캐시/예산 상태 리셋. write(dict) 로 override 를 쓴다."""
    path = tmp_path / "runtime_settings.json"
    monkeypatch.setenv("RUNTIME_SETTINGS_SNAPSHOT_PATH", str(path))
    monkeypatch.delenv("RUNTIME_SETTINGS_DISABLED", raising=False)
    for _k in ("AGENT_BACKGROUND_ANALYSIS_ENABLED", "AGENT_WORKER_LLM_BUDGET",
               "AGENT_WORKER_PG_BUDGET", "AGENT_WORKER_DS_BUDGET"):
        monkeypatch.delenv(_k, raising=False)
    rs._cache["overrides"] = None
    rs._cache["loaded_at"] = 0.0
    rs._cache["frozen"] = None
    rb._reset_for_test()

    def _write(overrides):
        rs.write_snapshot(overrides)
        rs._cache["overrides"] = None
        rs._cache["loaded_at"] = 0.0

    yield _write
    rb._reset_for_test()


# ── 스펙 등록 · 기본값(byte-동치) ─────────────────────────────────────────────

def test_specs_registered_with_live_apply_mode(snap):
    """4 knob 이 performance 그룹에 등록되고 전부 live 적용이다(정지 스위치가 재배포를 요구하면 무의미)."""
    for key in ("AGENT_BACKGROUND_ANALYSIS_ENABLED", "AGENT_WORKER_LLM_BUDGET"):
        spec = rs.spec_for(key)
        assert spec is not None, f"{key} 스펙 미등록"
        assert spec["group"] == rs.GROUP_PERF
        assert spec["apply_mode"] == "live", f"{key} 는 live 여야 한다"


def test_no_knob_without_an_enforced_gate(snap):
    """게이트 없는 상한 knob 을 노출하지 않는다 — **거짓 컨트롤 금지**(codex P1).

    커넥션 총량(pg/ds)은 게이트가 T0b 로 이연됐으므로 knob 도 없어야 한다. 이 단정은 "상한을
    설정했는데 아무것도 강제되지 않는" 상태로 되돌아가는 것을 막는다(이 repo 가 같은 이유로
    `attachment.execute_sql_on.*` 를 제거한 선례).
    """
    for key in ("AGENT_WORKER_PG_BUDGET", "AGENT_WORKER_DS_BUDGET"):
        assert rs.spec_for(key) is None, f"{key} 는 게이트가 배선될 때(T0b) 함께 추가해야 한다"
    assert rb.RESOURCES == ("llm",), "게이트가 배선된 자원만 RESOURCES 에 등재한다"
    # 미등재 자원은 fail-open(게이트 없음) — 오타·미배선이 작업을 조용히 막지 않는다.
    with rb.acquire("pg") as ok:
        assert ok is True


def test_default_limits_exceed_current_max_concurrency(snap):
    """기본 상한 > 현행 최대 동시성 → 게이트 미발동(배포 시점 동작 불변)."""
    # 현행 최대: 노드 분석 8 + 클러스터 라벨 4 = 12 동시 LLM.
    assert rb.limit_for("llm") >= 12


# ── 예산 게이트 ──────────────────────────────────────────────────────────────

def test_acquire_grants_within_limit_and_rejects_beyond(snap):
    snap({"AGENT_WORKER_LLM_BUDGET": 2})
    with rb.acquire("llm") as a:
        assert a is True
        with rb.acquire("llm") as b:
            assert b is True
            # 상한 2 소진 → 세 번째는 거절(예외 아님).
            with rb.acquire("llm") as c:
                assert c is False
    # 컨텍스트 이탈 후 전량 반납.
    assert rb.available("llm") == 2


def test_available_reports_remaining(snap):
    snap({"AGENT_WORKER_LLM_BUDGET": 3})
    assert rb.available("llm") == 3
    with rb.acquire("llm") as ok:
        assert ok
        assert rb.available("llm") == 2
    assert rb.available("llm") == 3


def test_release_on_exception_inside_block(snap):
    """블록 안에서 예외가 나도 점유가 반납된다(누수 금지)."""
    snap({"AGENT_WORKER_LLM_BUDGET": 1})
    with pytest.raises(RuntimeError):
        with rb.acquire("llm") as ok:
            assert ok
            raise RuntimeError("boom")
    assert rb.available("llm") == 1


def test_limit_change_is_live(snap):
    snap({"AGENT_WORKER_LLM_BUDGET": 1})
    assert rb.available("llm") == 1
    snap({"AGENT_WORKER_LLM_BUDGET": 4})
    assert rb.available("llm") == 4


def test_lowering_limit_does_not_force_reclaim(snap):
    """상한을 내려도 점유 중인 분은 유지된다 — 신규 획득만 막힌다(진행 중 작업 중단 금지)."""
    snap({"AGENT_WORKER_LLM_BUDGET": 3})
    with rb.acquire("llm") as a, rb.acquire("llm") as b:
        assert a and b
        snap({"AGENT_WORKER_LLM_BUDGET": 1})
        assert rb.available("llm") == 0          # 2 점유 > 상한 1 → 음수 아님(0 으로 clamp)
        with rb.acquire("llm") as c:
            assert c is False                    # 신규만 차단
    assert rb.available("llm") == 1               # 반납 후 새 상한 적용


def test_unknown_resource_is_fail_open(snap):
    with rb.acquire("nonexistent-resource") as ok:
        assert ok is True                         # 게이트 없이 통과
    assert rb.available("nonexistent-resource") > 0


def test_timeout_waits_and_succeeds_after_release(snap):
    """timeout 을 주면 짧게 대기하고, 다른 스레드가 반납하면 획득한다."""
    snap({"AGENT_WORKER_LLM_BUDGET": 1})
    holder_released = threading.Event()

    def _holder():
        with rb.acquire("llm") as ok:
            assert ok
            holder_released.wait(2.0)

    t = threading.Thread(target=_holder, daemon=True)
    t.start()
    # holder 가 점유할 시간을 준다.
    for _ in range(200):
        if rb.available("llm") == 0:
            break
        threading.Event().wait(0.005)
    holder_released.set()
    with rb.acquire("llm", timeout=2.0) as ok:
        assert ok is True
    t.join(2.0)


# ── kill-switch ─────────────────────────────────────────────────────────────

def test_background_enabled_default_true(snap):
    assert rb.background_enabled() is True


def test_background_disabled_when_zero(snap):
    snap({"AGENT_BACKGROUND_ANALYSIS_ENABLED": 0})
    assert rb.background_enabled() is False


def test_background_enabled_fail_open_on_settings_error(snap, monkeypatch):
    """설정 조회가 터지면 **활성**으로 본다 — 설정 장애가 워커를 통째로 멈추면 복구가 재배포뿐이 된다."""
    def _boom(_key):
        raise RuntimeError("settings unavailable")
    monkeypatch.setattr(rs, "get_int", _boom)
    assert rb.background_enabled() is True


# ── 계측 ─────────────────────────────────────────────────────────────────────

def test_snapshot_counts_acquired_rejected_peak(snap):
    snap({"AGENT_WORKER_LLM_BUDGET": 1})
    with rb.acquire("llm") as ok:
        assert ok
        with rb.acquire("llm") as no:
            assert no is False
    snapshot = rb.snapshot()
    llm = snapshot["resources"]["llm"]
    assert llm["acquired"] == 1
    assert llm["rejected"] == 1
    assert llm["peak"] == 1
    assert llm["reject_ratio"] == 0.5
    assert llm["limit"] == 1
    assert snapshot["background_enabled"] is True


def test_incr_conn_accumulates_and_ignores_unknown_keys(snap):
    rb.incr_conn("pg_conns")
    rb.incr_conn("pg_conns", 2)
    rb.incr_conn("bogus_key", 99)
    conns = rb.snapshot()["conns"]
    assert conns["pg_conns"] == 3
    assert "bogus_key" not in conns


def test_snapshot_zero_reject_ratio_when_gate_never_fires(snap):
    """게이트 미발동(거절 0) = 현행 동등의 실증 신호."""
    with rb.acquire("llm") as ok:
        assert ok
    assert rb.snapshot()["resources"]["llm"]["reject_ratio"] == 0.0


def test_ds_conns_is_actually_instrumented(snap):
    """`ds_conns` 는 노출만 되고 증분되지 않으면 '0 = 부하 없음' 으로 오독된다(codex 재검증 NEW P2).

    `shared/db.connect` 의 datasource 경로(MySQL·MSSQL 양 엔진)가 계측을 호출하는지 소스로 단정한다 —
    실제 연결은 라이브 DB 가 필요해 단위 테스트로 못 열지만, 훅 배선 누락은 이 단정이 잡는다.
    """
    import inspect
    from shared import db as _db
    src = inspect.getsource(_db.connect)
    assert src.count('_worker_conn_incr("ds_conns")') >= 2, (
        "datasource 연결 경로(MSSQL + MySQL) 양쪽에 ds_conns 계측이 있어야 한다")
    # 카운터 자체는 증분 가능해야 한다.
    rb.incr_conn("ds_conns", 2)
    assert rb.snapshot()["conns"]["ds_conns"] == 2


# ── ★회귀: process_pending 이 kill-switch 0 에서 claim 하지 않는다 ─────────────

def test_process_pending_does_not_claim_when_background_disabled(snap, monkeypatch):
    """kill-switch 0 이면 **DB claim 조차** 하지 않는다.

    change-reanalysis `cap==0` 은 신규 트리거만 막아 이미 적재된 잡이 계속 LLM 을 소진했다
    (적대 리뷰 C2 — 중단 수단이 재배포·수동 SQL 뿐). 그 결함을 반복하지 않도록 claim 단계에서
    게이트한다. `_rw_conn` 이 호출되면 실패 — 커넥션조차 열지 않아야 한다.
    """
    from modules import node_analysis as na

    snap({"AGENT_BACKGROUND_ANALYSIS_ENABLED": 0})
    called = {"rw_conn": 0}

    def _no_conn(_conn):
        called["rw_conn"] += 1
        raise AssertionError("kill-switch 0 인데 PG 커넥션을 열었다 — claim 게이트 누락")

    monkeypatch.setattr(na, "_rw_conn", _no_conn)
    monkeypatch.setattr(na, "_cfg_enabled", lambda: True)
    rep = na.process_pending(max_nodes=5)
    assert called["rw_conn"] == 0
    assert rep["claimed"] == 0
    assert rep["done"] == 0
    assert rep["budget_deferred"] == 0


# ── 파일 flush (조회 경로 — 워커 프로세스 메모리 → 호스트 CLI) ─────────────────

def test_flush_snapshot_writes_parsable_json(snap, tmp_path):
    with rb.acquire("llm") as ok:
        assert ok
    target = rb.flush_snapshot("insight-worker", directory=str(tmp_path))
    assert target
    import json
    data = json.loads((tmp_path / "worker-resources-insight-worker.json").read_text(encoding="utf-8"))
    assert data["role"] == "insight-worker"
    assert data["flushed_at"]
    assert data["resources"]["llm"]["acquired"] == 1
    assert data["background_enabled"] is True


def test_flush_snapshot_sanitizes_role_to_prevent_path_escape(snap, tmp_path):
    """role 은 컨테이너 이름 유래 — 구분자가 섞여도 **디렉토리를 벗어나지 않는다**.

    보안 속성은 "파일명에 `..` 문자가 없다" 가 아니라 "결과 경로의 부모가 지정 디렉토리다" 다.
    `/` 가 제거되므로 `../../etc/passwd` 는 한 파일명(`..-..-etc-passwd`)으로 접히고 탈출하지 못한다.
    """
    import os
    target = rb.flush_snapshot("../../etc/passwd", directory=str(tmp_path))
    assert target
    assert os.path.dirname(os.path.realpath(target)) == os.path.realpath(str(tmp_path))
    assert os.sep not in os.path.basename(target).replace("worker-resources-", "")
    assert list(tmp_path.glob("worker-resources-*.json"))


def test_flush_snapshot_is_fail_open_on_bad_directory(snap):
    """쓸 수 없는 경로면 빈 문자열 — 예외를 올리지 않는다(flush 가 tick 을 죽이지 않게)."""
    assert rb.flush_snapshot("x", directory="/proc/nonexistent-dir/deeper") == ""


def test_process_pending_skips_tick_when_llm_budget_exhausted(snap, monkeypatch):
    """LLM 예산 여유 0 이면 claim 하지 않고 이번 tick 을 건너뛴다(잡을 실패시키지 않는다)."""
    from modules import node_analysis as na

    snap({"AGENT_WORKER_LLM_BUDGET": 1})
    monkeypatch.setattr(na, "_cfg_enabled", lambda: True)

    def _no_conn(_conn):
        raise AssertionError("예산 여유 0 인데 claim 을 시도했다")

    monkeypatch.setattr(na, "_rw_conn", _no_conn)
    with rb.acquire("llm") as ok:          # 상한 1 을 테스트가 점유 → 여유 0
        assert ok
        rep = na.process_pending(max_nodes=5)
    assert rep["claimed"] == 0
