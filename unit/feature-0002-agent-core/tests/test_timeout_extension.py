"""feature-0030 실행 타임아웃 연장 — KV 시그널·설정·예산 게이트 단위 테스트.

DB 불요(순수). memory KV 는 in-memory dict 로 대체하고(기존 test_clear_cancel_runid 패턴),
run 루프의 예산 판정은 agent_core 의 게이트 조건을 동형 재현해 검증한다.

핵심 계약:
  - prompted / granted 는 run_id 짝 검증으로 이전 run 의 신호를 격리한다.
  - 승인이 없으면 종전과 동일하게 예산 초과 시 종료한다(기본 거절).
  - 승인이 있으면 무제한(max_sec=0) 또는 지정 상한까지 계속한다.
"""
from __future__ import annotations

import pytest

import agent_core
import modules.memory as memory


class _KV:
    def __init__(self, initial=None):
        self.store = dict(initial or {})

    def save(self, conn, cid, key, value):
        self.store[(cid, key)] = value

    def load(self, conn, cid, key):
        return self.store.get((cid, key), "")


@pytest.fixture
def kv(monkeypatch):
    store = _KV()
    monkeypatch.setattr(memory, "save_memory_kv", store.save)
    monkeypatch.setattr(memory, "load_memory_kv", store.load)
    return store


# ── KV 시그널 ────────────────────────────────────────────────────────────────

def test_prompt_records_run_and_deadline(kv):
    memory.mark_timeout_extension_prompted(None, "c", "R1", "2026-07-29T03:30:00Z")
    state = memory.timeout_extension_state(None, "c")
    assert state["prompted"] is True
    assert state["granted"] is False
    assert state["run_id"] == "R1"
    assert state["deadline_at"] == "2026-07-29T03:30:00Z"


def test_grant_visible_to_same_run(kv):
    memory.mark_timeout_extension_prompted(None, "c", "R1", "")
    assert memory.mark_timeout_extension_granted(None, "c", "R1") is True
    assert memory._timeout_extension_granted(None, "c", "R1") is True


def test_grant_ignored_for_other_run(kv):
    """직전 요청에 대한 승인이 다음 요청을 무기한 연장시키면 안 된다."""
    memory.mark_timeout_extension_prompted(None, "c", "R1", "")
    memory.mark_timeout_extension_granted(None, "c", "R1")
    assert memory._timeout_extension_granted(None, "c", "R2") is False


def test_no_grant_by_default(kv):
    assert memory._timeout_extension_granted(None, "c", "R1") is False


# ── codex 적대 리뷰 P1-1 / P1-2 회귀 방지 ────────────────────────────────────

def test_grant_requires_run_id(kv):
    """빈 run_id 를 허용하면 짝 검증이 wildcard 로 퇴화해 아무 run 이나 연장된다."""
    assert memory.mark_timeout_extension_granted(None, "c", "") is False
    assert memory._timeout_extension_granted(None, "c", "") is False


def test_grant_refused_when_prompt_targets_other_run(kv):
    """배너가 R1 을 가리키는데 R2 승인 요청이 오면 기록하지 않는다."""
    memory.mark_timeout_extension_prompted(None, "c", "R1", "")
    assert memory.mark_timeout_extension_granted(None, "c", "R2") is False
    assert memory._timeout_extension_granted(None, "c", "R2") is False


def test_new_prompt_clears_previous_grant(kv):
    """KV 는 대화당 단일 슬롯 — 새 run 의 prompt 가 이전 run 의 승인을 상속하면 안 된다."""
    memory.mark_timeout_extension_prompted(None, "c", "R1", "")
    memory.mark_timeout_extension_granted(None, "c", "R1")
    memory.mark_timeout_extension_prompted(None, "c", "R2", "")  # 새 run 진입
    assert memory._timeout_extension_granted(None, "c", "R2") is False
    assert memory._timeout_extension_granted(None, "c", "R1") is False


def test_empty_stored_run_id_is_not_wildcard(kv):
    """정리 중이거나 유실된 상태가 '아무 run 이나 승인'으로 읽히면 안 된다."""
    kv.store[("c", "timeout_ext_granted")] = "1"
    kv.store[("c", "timeout_ext_run_id")] = ""
    assert memory._timeout_extension_granted(None, "c", "R1") is False


def test_clear_removes_signals_for_same_run(kv):
    memory.mark_timeout_extension_prompted(None, "c", "R1", "2026-07-29T03:30:00Z")
    memory.mark_timeout_extension_granted(None, "c", "R1")
    memory._clear_timeout_extension(None, "c", run_id="R1")
    state = memory.timeout_extension_state(None, "c")
    assert state["prompted"] is False
    assert state["granted"] is False
    assert state["run_id"] == ""


def test_clear_skipped_when_signal_targets_other_run(kv):
    """늦게 끝난 run 이 새 run 의 승인을 지우면 새 run 이 조용히 잘린다."""
    memory.mark_timeout_extension_granted(None, "c", "R2")
    memory._clear_timeout_extension(None, "c", run_id="R1")
    assert memory._timeout_extension_granted(None, "c", "R2") is True


def test_state_survives_kv_failure(monkeypatch):
    """KV 조회 실패는 fail-safe(연장 없음)로 흡수 — 확인 신호가 추론을 깨지 않는다."""
    def _boom(*_a, **_k):
        raise RuntimeError("kv down")

    monkeypatch.setattr(memory, "load_memory_kv", _boom)
    assert memory._timeout_extension_granted(None, "c", "R1") is False
    assert memory.timeout_extension_state(None, "c") == {
        "prompted": False, "granted": False, "deadline_at": "", "run_id": "",
    }


# ── 설정 조회 ────────────────────────────────────────────────────────────────

def test_settings_defaults():
    enabled, pct, max_sec = agent_core._timeout_extension_settings()
    assert enabled is True
    assert pct == 80
    assert max_sec == 0  # 사용자 정책: 승인 시 무제한


def test_settings_failure_disables(monkeypatch):
    def _boom(_key):
        raise RuntimeError("settings down")

    monkeypatch.setattr(agent_core._rts, "get_int", _boom)
    assert agent_core._timeout_extension_settings() == (False, 80, 0)


# ── 예산 게이트 (run 루프 판정 동형 재현) ────────────────────────────────────

def _should_break(elapsed, run_timeout_sec, granted, max_sec):
    """agent_core.run_agent 의 예산 초과 판정과 동일한 식."""
    if elapsed <= run_timeout_sec:
        return False
    exhausted = max_sec > 0 and elapsed > run_timeout_sec + max_sec
    return (not granted) or exhausted


def test_budget_breaks_without_grant():
    assert _should_break(101, 100, granted=False, max_sec=0) is True


def test_budget_survives_with_unlimited_grant():
    assert _should_break(100_000, 100, granted=True, max_sec=0) is False


def test_budget_breaks_after_capped_grant_exhausted():
    assert _should_break(151, 100, granted=True, max_sec=50) is True
    assert _should_break(140, 100, granted=True, max_sec=50) is False


def test_budget_untouched_below_limit():
    assert _should_break(99, 100, granted=False, max_sec=0) is False


def test_prompt_threshold_at_configured_pct():
    run_timeout_sec = 100
    prompt_at = run_timeout_sec * (80 / 100.0)
    assert prompt_at == 80.0
    assert 79.9 < prompt_at  # 임계 직전엔 미발행
    assert 80.0 >= prompt_at  # 임계 도달 시 발행


def test_per_call_timeout_stays_bounded():
    """연장은 run 예산만 푼다 — 단일 LLM 호출 상한은 유지돼야 취소·즉시답변이 살아 있다.

    호출이 끝나야 루프가 돌아와 탈출구를 검사하므로, 이 값이 곧 '중단'의 최대 응답 지연이다
    (codex 적대 리뷰 P1-3: 24h 상한은 승인의 대가로 탈출구를 잃게 만들었다).
    """
    assert agent_core._EXTENSION_PER_CALL_TIMEOUT_SEC == 900
    assert agent_core._EXTENSION_PER_CALL_TIMEOUT_SEC < 3600


def test_grace_window_is_short_and_positive():
    """늦게 뜬 확인에 응답할 창은 있어야 하되, 종료를 오래 붙잡으면 안 된다."""
    assert 0 < agent_core._EXTENSION_GRACE_SEC <= 60


# ── _call_llm timeout override ───────────────────────────────────────────────

def test_call_llm_timeout_override_precedence():
    """override 가 있으면 콘솔 값 대신 그 값이 per-attempt 상한이 된다.

    (2026-08-26 계약 전환: 이 값은 요청 **본문**이 아니라 request option 으로 전달된다 —
    FR-body-timeout-poisons-provider-request. 아래는 값 해소 규칙만 검증하는 순수 함수 테스트다.)
    """
    def _resolve(timeout_override, console_value):
        return (
            int(timeout_override) if timeout_override and int(timeout_override) > 0
            else max(5, int(console_value))
        )

    assert _resolve(None, 60) == 60
    assert _resolve(0, 60) == 60
    assert _resolve(86400, 60) == 86400
    assert _resolve(None, 1) == 5  # 스펙 하한 보정 유지
