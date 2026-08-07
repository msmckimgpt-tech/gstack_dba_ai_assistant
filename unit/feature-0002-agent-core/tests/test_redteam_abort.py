"""단위 테스트 — red-team 리뷰어 대기 구간의 사용자 탈출구 (FR-redteam-first-pass-unabortable).

배경(라이브 실측 2026-08-07, 대화 `…226e27aa`): 답변 본문은 9.6초에 완성됐는데 리뷰어
호출이 `REDTEAM_TIMEOUT_SEC`(운영 300초) 동안 무응답 → 사용자에게는 312초 만에 전달됐다.
그 구간에는 취소·'즉시 답변' 체크도 진행 표시 갱신도 없어, 화면이 "답변을 자가 검증하는
중"에 멈춘 채 어떤 버튼도 듣지 않았다(= "응답이 더 이상 진행되지 않는다").

여기서 고정하는 계약:
- 리뷰어를 기다리는 **동안** 중단 신호가 들어오면 즉시 초안을 전달한다(fail-open).
- 이미 끝난 리뷰의 판정은 중단 신호가 있어도 버리지 않는다(콘솔의 "무엇이 남았는지" 보존).
- 대기가 길어지면 진행 표시를 갱신하되 **백오프**한다(매 tick 이 DB step 행이므로).
- 최초 검증 패스와 재검증 패스 **양쪽** 모두에 적용된다(배선 사각 방지 — 헬퍼 직접
  호출만으로는 orchestrate 가 실제로 그 헬퍼를 타는지 증명하지 못한다).
- 재검증이 끝나지 않은 채 나가면 직전(수정 이전) BLOCK 을 "미해소"로 단정하지 않는다.
- 중단 신호를 읽지 못하는 상태는 중단으로 오해하지 않되, 연속 실패 시에만 판정을 포기한다.
- 콜백이 하나도 없으면 종전대로 직접 호출한다(무회귀).

**§18.8 패널 반영**: 아래 `_fast_poll` 은 대기 시간을 줄이려고 상수를 낮추지만, 그러면
"테스트한 값"과 "출하되는 값"이 달라져 상수 자체를 되돌리는 뮤테이션이 전부 생존한다
(`test-env-override-skip-vacuous-pass` 패턴 — 패널이 `_REVIEW_ABORT_POLL_SEC=300` 뮤턴트로
실증했고, 그건 원 인시던트 그 자체다). 그래서 **fixture 를 쓰지 않는 상수 계약 테스트**를
따로 둔다.
"""
from __future__ import annotations

import contextvars
import threading
import time

import pytest

import shared.runtime_settings as _rts
from modules import redteam


def _settings(monkeypatch, **overrides):
    values = {
        "REDTEAM_ENABLED": 1,
        "REDTEAM_MIN_LEVEL": 1,
        "REDTEAM_MAX_REVISIONS": 1,
        "REDTEAM_TIMEOUT_SEC": 25,
        "REDTEAM_REDERIVE_ENABLED": 0,
        "REDTEAM_REVISE_UNTIL_RESOLVED": 0,
        "REDTEAM_VERIFY_MIN_LEVEL": 0,
        "REDTEAM_UNRESOLVED_NOTICE": 0,
        "REDTEAM_HISTORY_CONV_LIMIT": 0,
        "REDTEAM_WALL_BUDGET_SEC": 0,
    }
    values.update(overrides)
    monkeypatch.setattr(_rts, "get_int", lambda key: values.get(key, 0))


def _block(axis: str = "grounding") -> dict:
    return {"axis": axis, "severity": "BLOCK", "claim": "c", "evidence": "e", "fix_hint": "f"}


@pytest.fixture()
def recorded(monkeypatch):
    """record_review 호출을 가로채 stop_reason·verdict·rounds 를 관측 가능하게 만든다."""
    rows: list[dict] = []
    monkeypatch.setattr(redteam, "record_review", lambda **kw: rows.append(kw))
    return rows


@pytest.fixture()
def fast_poll(monkeypatch):
    """폴링·진행표시 주기를 실시간 대기 없이 관측 가능한 값으로 낮춘다.

    autouse 가 **아니다** — 상수 계약 테스트(`test_shipped_constants_*`)가 실제 출하 값을
    읽어야 하기 때문이다. 필요한 테스트만 명시적으로 요청한다.
    """
    monkeypatch.setattr(redteam, "_REVIEW_ABORT_POLL_SEC", 0.01)
    monkeypatch.setattr(redteam, "_REVIEW_ABORT_POLL_MAX_SEC", 0.02)
    monkeypatch.setattr(redteam, "_REVIEW_ABORT_POLL_FAST_WINDOW_SEC", 0.05)
    monkeypatch.setattr(redteam, "_REVIEW_PROGRESS_TICK_SEC", 0.02)
    monkeypatch.setattr(redteam, "_REVIEW_PROGRESS_TICK_BACKOFF", 4.0)
    monkeypatch.setattr(redteam, "_REVIEW_PROGRESS_TICK_MAX_SEC", 1.0)
    monkeypatch.setattr(redteam, "_REVIEW_WAIT_GRACE_SEC", 0.2)
    monkeypatch.setattr(redteam, "_REVIEW_ABORT_RESULT_GRACE_SEC", 0.05)


# ── 출하 상수 계약 (fixture 미사용 — 실제 배포되는 값을 본다) ──────────────────

def test_shipped_constants_bound_user_perceived_abort_latency():
    """'즉시 답변'을 누르고 반응까지의 최악 지연 = 폴링 간격 + 결과 유예.

    이 상한이 느슨해지면 봉인이 무력화된다 — 패널이 `_REVIEW_ABORT_POLL_SEC=300`
    뮤턴트로 전 스위트 통과를 실증했고, 그 값이 곧 원래 인시던트다.
    """
    assert redteam._REVIEW_ABORT_POLL_SEC <= 2.0
    assert redteam._REVIEW_ABORT_POLL_MAX_SEC <= 5.0
    assert redteam._REVIEW_ABORT_RESULT_GRACE_SEC <= 1.0
    worst_case = (redteam._REVIEW_ABORT_POLL_MAX_SEC
                  + redteam._REVIEW_ABORT_RESULT_GRACE_SEC)
    assert worst_case <= 5.0, f"중단 반응이 {worst_case}초까지 늦어질 수 있다"


def test_shipped_constants_keep_progress_visible_and_bounded():
    """첫 진행 갱신은 화면이 멈춰 보이기 전에 와야 하고, 누적 행 수는 유계여야 한다."""
    assert redteam._REVIEW_PROGRESS_TICK_SEC <= 20.0
    assert redteam._REVIEW_PROGRESS_TICK_BACKOFF > 1.0
    assert redteam._REVIEW_PROGRESS_TICK_MAX_SEC <= 180.0
    # 운영 상한(300초) 대기에서 몇 행이 쌓이는지 실제로 세어 본다.
    elapsed, gap, rows = 0.0, redteam._REVIEW_PROGRESS_TICK_SEC, 0
    while elapsed < 300.0:
        elapsed += gap
        rows += 1
        gap = min(redteam._REVIEW_PROGRESS_TICK_MAX_SEC,
                  gap * redteam._REVIEW_PROGRESS_TICK_BACKOFF)
    assert rows <= 8, f"300초 대기에 진행 표시 {rows}행이 쌓인다(각각 DB step INSERT)"


def test_shipped_wait_grace_is_small_relative_to_timeout():
    """대기 포기 유예는 리뷰어 상한에 비해 작아야 한다(오래 붙잡지 않되 정상 도착은 살린다)."""
    assert 0 < redteam._REVIEW_WAIT_GRACE_SEC <= 15.0
    assert 0 < redteam._REVIEW_WAIT_GRACE_RATIO <= 0.25


# ── 헬퍼 단위 계약 ────────────────────────────────────────────────────────────

def test_await_returns_result_without_callbacks():
    """콜백이 없으면 폴링 없이 직접 호출한다(기존 동작 무회귀)."""
    called = {"n": 0}

    def _call():
        called["n"] += 1
        return {"verdict": "pass", "findings": []}

    review, aborted, gave_up = redteam._await_review_interruptible(_call, timeout_sec=25)
    assert review == {"verdict": "pass", "findings": []}
    assert aborted is False and gave_up is False and called["n"] == 1


def test_await_abort_keeps_result_that_lands_within_grace(fast_poll):
    """중단 신호가 있어도 유예 안에 도착한 결과는 채택한다(판정·findings 손실 방지)."""
    calls = {"n": 0}

    def _quick():
        time.sleep(0.05)
        return {"verdict": "revise", "findings": []}

    def _abort():
        calls["n"] += 1
        return True

    review, aborted, gave_up = redteam._await_review_interruptible(
        _quick, timeout_sec=25, abort_fn=_abort)
    assert aborted is False and gave_up is False
    assert review == {"verdict": "revise", "findings": []}
    assert calls["n"] >= 1, "중단 경로를 타지 않았다면 이 테스트는 유예를 증명하지 못한다"


def test_await_aborts_while_reviewer_still_running(fast_poll):
    """리뷰어가 아직 도는 중에 신호가 들어오면 기다리지 않고 (None, True, False)."""
    release = threading.Event()

    def _slow_call():
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    ticks = {"n": 0}

    def _abort():
        ticks["n"] += 1
        return ticks["n"] >= 2

    t0 = time.perf_counter()
    review, aborted, gave_up = redteam._await_review_interruptible(
        _slow_call, timeout_sec=25, abort_fn=_abort)
    elapsed = time.perf_counter() - t0
    release.set()
    assert review is None and aborted is True and gave_up is False
    # 리뷰어의 5초를 기다리지 않았다는 것이 이 결함의 핵심이다.
    assert elapsed < 2.0


def test_await_gives_up_after_timeout_plus_grace_scaled_by_timeout(fast_poll):
    """포기 시점이 **리뷰어 상한에 비례**한다 — 상수만 보고 3초에 버리면 p50 20초 리뷰가 전멸한다."""
    release = threading.Event()

    def _never():
        release.wait(timeout=10)
        return {"verdict": "pass", "findings": []}

    t0 = time.perf_counter()
    review, aborted, gave_up = redteam._await_review_interruptible(
        _never, timeout_sec=3, abort_fn=lambda: False)
    elapsed = time.perf_counter() - t0
    release.set()
    assert review is None and aborted is False
    assert gave_up is True, "대기 포기는 리뷰어 실패와 구분돼 보고돼야 한다"
    # timeout_sec=3 이 실제로 관측된다: 3초 전에 포기하지 않고, 3 + grace 직후에 포기한다.
    assert 3.0 <= elapsed < 4.5, elapsed


def test_await_emits_progress_while_waiting(fast_poll):
    release = threading.Event()
    labels: list[str] = []

    def _slow_call():
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    calls = {"n": 0}

    def _abort():
        calls["n"] += 1
        return calls["n"] >= 8

    redteam._await_review_interruptible(
        _slow_call, timeout_sec=25, abort_fn=_abort,
        progress_fn=labels.append, progress_prefix="답변을 자가 검증하는 중")
    release.set()
    assert labels, "대기 중 진행 표시가 한 번도 갱신되지 않았다"
    first = labels[0]
    assert first.startswith("답변을 자가 검증하는 중"), first
    assert "경과" in first and "상한" in first
    # 상한 값이 실제로 실린다(0 이나 빈 값이 아니다).
    assert "25초" in first, first
    # 탈출구 안내는 이 화면의 존재 이유다 — 문구가 사라지면 사용자는 기다리는 것 말고
    # 할 수 있는 일을 모른다.
    assert "즉시 답변" in first, first


def test_await_progress_ticks_back_off_with_margin(fast_poll):
    """진행 표시는 백오프한다 — `progress_fn` 이 매번 step 행을 저장하므로.

    비율로 단정한다(단순 `>` 는 스케줄러 지터와 신호 크기가 같아 뮤턴트가 8/15 생존했다 —
    §18.8 qa 패널 실측).
    """
    release = threading.Event()
    stamps: list[float] = []

    def _slow_call():
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    def _record(_label: str) -> None:
        stamps.append(time.perf_counter())

    calls = {"n": 0}

    def _abort():
        calls["n"] += 1
        return len(stamps) >= 3

    redteam._await_review_interruptible(
        _slow_call, timeout_sec=25, abort_fn=_abort, progress_fn=_record)
    release.set()
    assert len(stamps) >= 3, f"백오프 검증에 필요한 tick 이 부족하다: {len(stamps)}"
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    # backoff=4.0 이므로 마지막 간격은 첫 간격의 3배 이상이어야 한다(지터 마진 포함).
    assert gaps[-1] >= gaps[0] * 3, f"간격이 벌어지지 않았다: {gaps}"


def test_await_progress_tick_respects_max_cap(fast_poll, monkeypatch):
    """백오프에는 상한이 있다 — 없으면 긴 대기에서 진행 표시가 사실상 멈춘다."""
    monkeypatch.setattr(redteam, "_REVIEW_PROGRESS_TICK_MAX_SEC", 0.03)
    release = threading.Event()
    stamps: list[float] = []

    def _slow_call():
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    def _abort():
        return len(stamps) >= 5

    redteam._await_review_interruptible(
        _slow_call, timeout_sec=25, abort_fn=_abort, progress_fn=lambda _l: stamps.append(
            time.perf_counter()))
    release.set()
    assert len(stamps) >= 5
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    # cap(0.03s)이 걸리므로 후반 간격이 무한정 커지지 않는다.
    assert max(gaps[2:]) < 0.25, f"cap 이 걸리지 않았다: {gaps}"


def test_await_progress_exception_does_not_lose_the_review(fast_poll):
    """진행 표시는 DB 를 건드린다 — 그 실패가 리뷰 전체를 삼키면 안 된다."""
    def _call():
        time.sleep(0.08)
        return {"verdict": "pass", "findings": []}

    def _boom(_label: str) -> None:
        raise RuntimeError("step insert failed")

    review, aborted, gave_up = redteam._await_review_interruptible(
        _call, timeout_sec=25, abort_fn=lambda: False, progress_fn=_boom)
    assert review == {"verdict": "pass", "findings": []}
    assert aborted is False and gave_up is False


def test_await_abort_read_failure_is_not_treated_as_abort(fast_poll):
    """중단 신호를 읽지 못하는 상태를 '중단'으로 오해하면 리뷰가 통째로 사라진다."""
    def _call():
        time.sleep(0.08)
        return {"verdict": "pass", "findings": []}

    def _broken_abort():
        raise RuntimeError("mem_conn down")

    review, aborted, gave_up = redteam._await_review_interruptible(
        _call, timeout_sec=25, abort_fn=_broken_abort)
    assert aborted is False and gave_up is False
    assert review == {"verdict": "pass", "findings": []}


def test_await_abort_recovers_after_transient_read_failures(fast_poll):
    """일시적 읽기 실패 뒤 신호가 살아나면 **여전히 중단해야 한다**(연속 실패만 판정을 끈다)."""
    release = threading.Event()

    def _slow_call():
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    calls = {"n": 0}

    def _flaky():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError("transient")
        return True

    review, aborted, gave_up = redteam._await_review_interruptible(
        _slow_call, timeout_sec=25, abort_fn=_flaky)
    release.set()
    assert aborted is True and review is None and gave_up is False


def test_await_abort_gives_up_signal_after_consecutive_failures(fast_poll):
    """연속 3회 실패하면 중단 판정을 끄고 대기만 한다 — 그 뒤 신호는 무시된다."""
    release = threading.Event()

    def _slow_call():
        release.wait(timeout=1.2)
        return {"verdict": "pass", "findings": []}

    calls = {"n": 0}

    def _broken_then_true():
        calls["n"] += 1
        if calls["n"] <= 3:
            raise RuntimeError("mem_conn down")
        return True

    review, aborted, gave_up = redteam._await_review_interruptible(
        _slow_call, timeout_sec=25, abort_fn=_broken_then_true)
    release.set()
    assert aborted is False, "연속 실패 후에는 중단 판정을 신뢰하지 않는다"
    assert review == {"verdict": "pass", "findings": []}


def test_await_worker_exception_is_reported_as_review_failure(fast_poll):
    """워커에서 예외가 새면 호출측이 `review_error` 로 기록할 수 있어야 한다(행 유실 금지).

    `run_review` 는 자기 안의 Exception 을 삼키지만, 호출 인자 평가(히스토리 블록 조립 등)에서
    나는 예외는 이 헬퍼까지 올라온다. 그대로 두면 `orchestrate_review` 의 바깥 except 가
    삼켜 `redteam_reviews` 행 자체가 사라진다(예전에는 `review_error` 행이 남았다).
    """
    def _explode():
        raise RuntimeError("argument assembly failed")

    review, aborted, gave_up = redteam._await_review_interruptible(
        _explode, timeout_sec=25, abort_fn=lambda: False)
    assert review is None and aborted is False and gave_up is False


def test_await_propagates_real_datasource_contextvar_to_worker(fast_poll):
    """워커가 호출자의 **실제** datasource ContextVar 를 본다.

    스레드는 컨텍스트를 상속하지 않는다. 복사를 빠뜨리면 `_record_llm_usage` 의
    `get_active_datasource()` 폴백이 워커에서 빈 값을 봐 `llm_usage.target_scope` 가
    통째로 NULL 이 된다(리뷰어 호출의 데이터소스 비용 귀속 소실).
    """
    from shared import config as cfg

    assert hasattr(cfg, "set_active_datasource") and hasattr(cfg, "get_active_datasource"), (
        "active datasource ContextVar 가 사라졌다면 이 계약(그리고 llm_usage.target_scope "
        "귀속)이 무의미해진 것이므로 skip 이 아니라 실패로 드러나야 한다")
    previous = cfg.get_active_datasource()
    cfg.set_active_datasource("ds-scope-42")
    try:
        seen: dict[str, object] = {}

        def _call():
            seen["value"] = cfg.get_active_datasource()
            return {"verdict": "pass", "findings": []}

        review, aborted, _gave_up = redteam._await_review_interruptible(
            _call, timeout_sec=25, abort_fn=lambda: False)
        assert aborted is False and review is not None
        assert seen["value"] == "ds-scope-42"
    finally:
        cfg.set_active_datasource(previous)


def test_await_uses_named_worker_thread(fast_poll):
    """인시던트 중 스레드 덤프에서 주인을 알아볼 수 있어야 한다."""
    seen: dict[str, str] = {}

    def _call():
        seen["name"] = threading.current_thread().name
        return {"verdict": "pass", "findings": []}

    redteam._await_review_interruptible(_call, timeout_sec=25, abort_fn=lambda: False)
    assert "redteam" in seen["name"], seen


# ── orchestrate_review 배선 (헬퍼가 실제로 그 경로에 걸려 있는가) ─────────────

def test_orchestrate_already_aborted_still_keeps_fast_verdict(monkeypatch, recorded, fast_poll):
    """이미 '즉시 답변'이어도 **빠르게 끝나는** 리뷰의 판정은 버리지 않는다.

    중단은 "리뷰를 금지한다"가 아니라 "리뷰 때문에 기다리게 하지 않는다"이다.
    """
    _settings(monkeypatch)
    monkeypatch.setattr(redteam, "run_review",
                        lambda *a, **kw: {"verdict": "pass", "findings": []})
    answer, meta = redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        abort_fn=lambda: True)
    assert answer == "draft"
    assert meta is not None and meta["verdict"] == "pass"


def test_orchestrate_aborts_during_first_pass(monkeypatch, recorded, fast_poll):
    """첫 패스가 도는 중 신호 → 초안 즉시 전달 + 감사 행이 사실대로 남는다."""
    _settings(monkeypatch)
    release = threading.Event()

    def _slow_review(*a, **kw):
        release.wait(timeout=5)
        return {"verdict": "revise", "findings": [_block()]}

    monkeypatch.setattr(redteam, "run_review", _slow_review)
    seen = {"n": 0}

    def _abort():
        seen["n"] += 1
        return seen["n"] >= 2

    t0 = time.perf_counter()
    answer, meta = redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        abort_fn=_abort,
        revise_fn=lambda instr, draft=None: "MUST NOT BE CALLED")
    elapsed = time.perf_counter() - t0
    release.set()
    assert answer == "draft" and meta is None
    assert elapsed < 2.0, "리뷰어가 끝날 때까지 사용자를 붙잡았다"
    row = recorded[-1]
    assert row["stop_reason"] == "aborted"
    # 완료되지 않은 리뷰를 통과로 기록하면 감사 원장이 거짓이 된다.
    assert row["verdict"] == "error"
    assert row["revision_applied"] is False
    assert row["model"], "리뷰어 모델이 기록되지 않았다"
    assert row["latency_ms"] is not None


def test_orchestrate_first_pass_wait_giveup_is_distinguishable(monkeypatch, recorded, fast_poll):
    """우리가 대기를 포기한 경우는 리뷰어 실패와 다른 사유로 기록된다."""
    # plan["timeout_sec"] 은 하한 5초라 이 테스트는 실시간 ~5.5초를 쓴다 — 대기 포기 경로는
    # `timeout_sec` 을 실제로 관측해야만 의미가 있어(패널 B2) 상수로 우회하지 않는다.
    _settings(monkeypatch, REDTEAM_TIMEOUT_SEC=1)
    release = threading.Event()

    def _never(*a, **kw):
        release.wait(timeout=30)
        return {"verdict": "pass", "findings": []}

    monkeypatch.setattr(redteam, "run_review", _never)
    answer, meta = redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        abort_fn=lambda: False)
    release.set()
    assert answer == "draft" and meta is None
    assert recorded[-1]["stop_reason"] == "review_wait_giveup"


def test_orchestrate_aborts_during_verify_pass(monkeypatch, recorded, fast_poll):
    """재검증도 같은 사각지대였다 — 마지막 수정본을 채택하고 즉시 종료."""
    _settings(monkeypatch)
    release = threading.Event()
    state = {"pass_no": 0}

    def _review(*a, **kw):
        state["pass_no"] += 1
        if state["pass_no"] == 1:
            return {"verdict": "revise", "findings": [_block()]}
        release.wait(timeout=5)  # 재검증 호출이 상한까지 매달린다
        return {"verdict": "pass", "findings": []}

    monkeypatch.setattr(redteam, "run_review", _review)
    seen = {"n": 0}

    def _abort():
        if state["pass_no"] < 2:
            return False
        seen["n"] += 1
        return seen["n"] >= 2

    answer, meta = redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        abort_fn=_abort,
        revise_fn=lambda instr, draft=None: "revised")
    release.set()
    assert answer == "revised"
    assert meta is not None and meta["stop_reason"] == "aborted"
    assert meta["revision_applied"] is True
    # 회차 원장이 왜 마지막 회차인지 말해야 한다.
    rounds = recorded[-1]["rounds"]
    verify_rounds = [r for r in rounds if r.get("phase") == "verify"]
    assert verify_rounds and verify_rounds[-1].get("note") == "aborted", rounds
    assert recorded[-1]["stop_reason"] == "aborted"


def test_orchestrate_verify_abort_does_not_claim_unresolved_defects(
        monkeypatch, recorded, fast_poll):
    """재검증이 끝나지 않았으면 '결함 미해소'를 단정하지 않는다.

    직전 판정의 BLOCK 은 **수정 이전** 답변에 대한 것이다. 그걸 미해소로 세면 검증하지도
    않은 답변에 대해 사실 주장을 하게 되고, 그 주장이 사용자 답변 말미에 고지로 찍힌다
    (`REDTEAM_UNRESOLVED_NOTICE` 운영 기본 1). §18.8 backend 패널 MAJOR.
    """
    _settings(monkeypatch, REDTEAM_UNRESOLVED_NOTICE=1)
    release = threading.Event()
    state = {"pass_no": 0}

    def _review(*a, **kw):
        state["pass_no"] += 1
        if state["pass_no"] == 1:
            return {"verdict": "revise", "findings": [_block()]}
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    monkeypatch.setattr(redteam, "run_review", _review)
    seen = {"n": 0}

    def _abort():
        if state["pass_no"] < 2:
            return False
        seen["n"] += 1
        return seen["n"] >= 2

    answer, meta = redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        abort_fn=_abort,
        revise_fn=lambda instr, draft=None: "revised")
    release.set()
    assert meta["unresolved_block_count"] == 0, meta
    assert meta["unresolved_notice_applied"] is False
    assert answer == "revised", "검증되지 않은 결함 고지가 답변에 붙었다"


def test_orchestrate_progress_updates_during_long_first_pass(monkeypatch, recorded, fast_poll):
    """긴 대기 중 진행 표시가 갱신되고, 그 라벨이 첫 패스 문구다."""
    _settings(monkeypatch)
    release = threading.Event()
    labels: list[str] = []

    def _slow_review(*a, **kw):
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    monkeypatch.setattr(redteam, "run_review", _slow_review)

    def _abort():
        return len(labels) >= 2

    redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        abort_fn=_abort, progress_fn=labels.append)
    release.set()
    assert labels, "진행 표시가 한 번도 갱신되지 않았다"
    assert any(label.startswith("답변을 자가 검증하는 중") and "경과" in label
               for label in labels), labels


def test_orchestrate_progress_updates_during_long_verify_pass(monkeypatch, recorded, fast_poll):
    """재검증 대기에도 진행 표시가 흐르고, 라벨이 **재검증** 문구여야 한다.

    한쪽만 배선하면 나머지가 같은 사각지대로 남는다 — 패널이 verify 쪽 `progress_fn=None`
    뮤턴트 생존으로 실증했다.
    """
    _settings(monkeypatch)
    release = threading.Event()
    labels: list[str] = []
    state = {"pass_no": 0}

    def _review(*a, **kw):
        state["pass_no"] += 1
        if state["pass_no"] == 1:
            return {"verdict": "revise", "findings": [_block()]}
        release.wait(timeout=5)
        return {"verdict": "pass", "findings": []}

    monkeypatch.setattr(redteam, "run_review", _review)

    def _abort():
        if state["pass_no"] < 2:
            return False
        return len([label for label in labels if "경과" in label]) >= 2

    redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        abort_fn=_abort, progress_fn=labels.append,
        revise_fn=lambda instr, draft=None: "revised")
    release.set()
    ticking = [label for label in labels if "경과" in label]
    assert ticking, f"재검증 대기 중 진행 표시가 없다: {labels}"
    assert all(label.startswith("수정본을 재검증하는 중") for label in ticking), ticking


def test_orchestrate_without_abort_fn_still_reviews(monkeypatch, recorded):
    """abort_fn 미전달 경로(기존 호출자)는 종전대로 리뷰를 수행한다."""
    _settings(monkeypatch)
    monkeypatch.setattr(redteam, "run_review",
                        lambda *a, **kw: {"verdict": "pass", "findings": []})
    answer, meta = redteam.orchestrate_review(
        question="q", draft_answer="draft", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False)
    assert answer == "draft"
    assert meta is not None and meta["verdict"] == "pass"
    assert recorded and recorded[-1]["stop_reason"] == "resolved"
