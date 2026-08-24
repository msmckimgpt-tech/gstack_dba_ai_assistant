"""conv-audit FR-stale-threshold-below-llm-attempt-cap — stale 표시 임계가 per-attempt 상한
안쪽에 놓여 **살아있는 run 을 "작업 중단" 으로 오표시**하던 결함의 회귀 고정.

라이브 사고(2026-08-24, 실측):
  단일 LLM 호출이 응답 없이 상한(`AGENT_TIMEOUT_SEC`, 관리 콘솔 live = **1800초**)까지 대기하는
  동안에는 step 이 하나도 생기지 않는다(스트리밍 progress 게이트도 chunk 가 와야 열린다 —
  agent_core `_collect_llm_stream` 의 문서화된 한계). 그런데 표시 판정 임계는 코드 상수
  **1200초** 에 고정돼 있어, 12:22 부터 10분간 UI 가 `stale_error`("작업 중단 감지")를 띄우는
  동안 그 run 은 살아서 21회차 추론을 진행 중이었고 12:32:23 에 상한을 소진한 뒤 누적 도구
  결과를 보존한 채 정상 재개됐다. 사용자는 중단으로 믿고 이탈했다.

  즉 **판정 임계가 감시 대상의 최대 정상 소요보다 짧으면 그 판정은 구조적으로 거짓 양성**이다.
  운영자가 콘솔에서 상한만 올려도 표시 임계는 따라오지 않는 config drift 이므로, 데이터 값이
  아니라 **코드가 불변식을 강제**한다.

여기서 고정하는 계약:
  T1 불변식 — 어떤 상한 값에서도 유효 임계 > 상한 (드리프트가 다시 임계를 안쪽으로 못 민다).
  T2 운영자 의도 보존 — env 로 더 크게 준 값은 하한으로 남는다.
  T3 fail-open — 런타임 설정 조회 실패는 종전 상수로 되돌아간다(표시가 설정 가용성에 종속 안 됨).
  T4 사고 재현 — 상한 1800 에서 마지막 활동 1300초 전인 run 은 **stale 이 아니다**(종전엔 stale).
  T5 진짜 죽은 run 은 여전히 stale (가드를 무력화하지 않았다).
  T6 봉인 B — 판정이 본 마지막 활동 시각을 tz 명시 ISO 로 표면에 내보낸다.
  T7 (소스 잠금) 프런트가 그 값을 우선 표시한다.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import app
from routers import _conv_store as cs


@pytest.fixture(autouse=True)
def _reset_cap_high_water():
    """상한 high-water 는 **프로세스 상태**다(§18.8 codex [P1] 봉인) — 테스트 간 격리.

    리셋하지 않으면 앞선 테스트가 올려놓은 값이 뒤 테스트의 기대를 깨고, 실행 순서에 따라
    flaky 해진다.
    """
    saved = app._STALE_CAP_HIGH_WATER
    app._STALE_CAP_HIGH_WATER = 0
    yield
    app._STALE_CAP_HIGH_WATER = saved


# ── T1: 불변식 — 유효 임계는 언제나 per-attempt 상한보다 크다 ────────────────────
def test_effective_threshold_always_exceeds_attempt_cap(monkeypatch):
    """상한이 어떤 값이든(스펙 범위 5~3600) 임계가 그 안쪽으로 들어오지 않는다."""
    for cap in (5, 60, 300, 900, 1800, 3600):
        monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k, _c=cap: _c)
        eff = app._effective_stale_timeout_seconds()
        assert eff > cap, f"cap={cap} 에서 임계 {eff} 가 상한 안쪽 — 살아있는 run 이 오표시된다"


def test_effective_threshold_includes_requeue_margin(monkeypatch):
    """상한이 기본 하한을 넘으면 임계 = 상한 + 재큐 여유(margin)."""
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 1800)
    assert app._effective_stale_timeout_seconds() == 1800 + app.WEB_PROGRESS_STALE_MARGIN_SECONDS


# ── T2: 운영자 의도 보존 ────────────────────────────────────────────────────────
def test_configured_floor_wins_when_larger(monkeypatch):
    """env 로 명시한 큰 임계는 파생값에 눌리지 않는다(하한 역할)."""
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 60)
    assert app._effective_stale_timeout_seconds() == app.WEB_PROGRESS_STALE_TIMEOUT_SECONDS


# ── T3: fail-open ──────────────────────────────────────────────────────────────
def test_derivation_failure_falls_back_to_constant(monkeypatch):
    """런타임 설정 조회가 실패해도 표시 판정은 계속 동작한다(종전 상수)."""
    def _boom(_k):
        raise RuntimeError("snapshot unreadable")

    monkeypatch.setattr(app._runtime_settings, "get_int", _boom)
    assert app._effective_stale_timeout_seconds() == app.WEB_PROGRESS_STALE_TIMEOUT_SECONDS


def test_nonpositive_cap_falls_back_to_constant(monkeypatch):
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 0)
    assert app._effective_stale_timeout_seconds() == app.WEB_PROGRESS_STALE_TIMEOUT_SECONDS


# ── §18.8 codex [P1]: 상한 하락·조회 실패가 임계를 급락시키지 않는다 ──────────────
def test_cap_drop_does_not_shrink_threshold(monkeypatch):
    """진행 중 호출은 시작 시점 상한으로 대기한다 — 판정이 낮아진 값을 따라가면 그 호출이
    다시 오표시된다(봉인하려던 사고의 재현). high-water 로 그 창을 덮는다."""
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 1800)
    high = app._effective_stale_timeout_seconds()
    assert high == 1800 + app.WEB_PROGRESS_STALE_MARGIN_SECONDS
    # 운영자가 상한을 60초로 낮춤 → 이미 1800초로 대기 중인 호출이 있을 수 있다.
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 60)
    assert app._effective_stale_timeout_seconds() == high


def test_lookup_failure_keeps_high_water(monkeypatch):
    """조회 실패도 임계를 종전 상수로 떨어뜨리지 않는다(fail-open 이 오표시를 만들지 않게)."""
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 1800)
    high = app._effective_stale_timeout_seconds()

    def _boom(_k):
        raise RuntimeError("snapshot vanished")

    monkeypatch.setattr(app._runtime_settings, "get_int", _boom)
    assert app._effective_stale_timeout_seconds() == high


# ── §18.8 codex [P2]: clamp — 비정상 큰 값이 stale 을 영구 미보고로 만들지 않는다 ──
def test_absurd_cap_is_clamped(monkeypatch):
    """env baseline 은 스펙 clamp 를 안 거친다 — 파생이 그걸 그대로 믿으면 가드가 무력화된다."""
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 10 ** 9)
    eff = app._effective_stale_timeout_seconds()
    assert eff == app._STALE_CAP_CLAMP_MAX + app.WEB_PROGRESS_STALE_MARGIN_SECONDS
    assert eff <= 3600 + 3600, f"임계 {eff}s — 이 정도면 stale 이 사실상 보고되지 않는다"


def test_clamp_max_and_margin_are_bounded():
    assert 0 < app._STALE_CAP_CLAMP_MAX <= 3600
    assert 0 <= app.WEB_PROGRESS_STALE_MARGIN_SECONDS <= 3600


# ── T4: 사고 재현 — 살아있는 run 을 중단으로 표시하지 않는다 ─────────────────────
def test_live_run_waiting_inside_attempt_cap_is_not_stale(monkeypatch):
    """상한 1800 · 마지막 활동 1300초 전 = 정상 대기 구간 → stale 아님.

    종전 코드(임계 1200 고정)에서는 이 입력이 정확히 `stale_error` 였다 — 사고의 재현 입력.
    """
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 1800)
    last = datetime.utcnow() - timedelta(seconds=1300)
    monkeypatch.setattr(app, "_last_step_at_for_run", lambda *a, **k: last)
    status, is_stale, _ = app._compute_display_status(
        None, "cid", "processing", last.isoformat(), "rid"
    )
    assert (status, is_stale) == ("processing", False)
    # 인자형(스냅샷 번들) 경로도 같은 판정이어야 한다 — 두 경로가 갈리면 목록과 폴링이 어긋난다.
    assert app._display_status_from_step_at("processing", "", last)[:2] == ("processing", False)


# ── T5: 진짜 죽은 run 은 여전히 잡는다 ──────────────────────────────────────────
def test_dead_run_beyond_cap_plus_margin_is_still_stale(monkeypatch):
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 1800)
    last = datetime.utcnow() - timedelta(seconds=1800 + app.WEB_PROGRESS_STALE_MARGIN_SECONDS + 60)
    monkeypatch.setattr(app, "_last_step_at_for_run", lambda *a, **k: last)
    status, is_stale, _ = app._compute_display_status(
        None, "cid", "processing", last.isoformat(), "rid"
    )
    assert (status, is_stale) == ("stale_error", True)


# ── T6: 봉인 B — 마지막 활동 시각 직렬화 ────────────────────────────────────────
def test_last_active_serialized_with_explicit_utc():
    """naive 를 그대로 내보내면 프런트 `new Date()` 가 로컬(KST)로 읽어 9시간 어긋난다."""
    naive = datetime(2026, 8, 24, 3, 2, 23)
    out = cs._iso_or_empty(naive)
    assert out.startswith("2026-08-24T03:02:23")
    assert out.endswith("+00:00"), f"타임존 미명시 직렬화: {out}"


def test_iso_or_empty_rejects_non_datetime():
    assert cs._iso_or_empty(None) == ""
    assert cs._iso_or_empty("2026-08-24") == ""


# ── §18.8 codex [P2]: KV 시각 파싱이 offset 을 UTC 로 변환한다 ────────────────────
def test_parse_kv_timestamp_converts_offset_to_utc():
    """offset 을 변환 없이 strip 하면 KST wall-clock 이 UTC 로 오인돼 9시간 미래가 된다
    (`_last_step_at_for_run` CHG-20260527-0001 회귀의 KV 축 판)."""
    assert app._parse_kv_timestamp("2026-08-24T12:00:00+09:00") == datetime(2026, 8, 24, 3, 0, 0)
    assert app._parse_kv_timestamp("2026-08-24T03:00:00+00:00") == datetime(2026, 8, 24, 3, 0, 0)
    assert app._parse_kv_timestamp("2026-08-24T03:00:00Z") == datetime(2026, 8, 24, 3, 0, 0)
    # naive 는 그대로(UTC 로 기록한다는 KV 계약).
    assert app._parse_kv_timestamp("2026-08-24 03:00:00") == datetime(2026, 8, 24, 3, 0, 0)
    assert app._parse_kv_timestamp("") is None
    assert app._parse_kv_timestamp("not-a-time") is None


# ── §18.8 codex [P2]: terminal 도 마지막 활동을 돌려준다 ─────────────────────────
def test_terminal_status_returns_last_activity(monkeypatch):
    """None 을 주면 완료 대화의 `last_activity_effective_at` 이 비어 표면이 요청 시각으로
    폴백한다 — 계약이 processing 에서만 성립하던 비대칭."""
    done_at = datetime(2026, 8, 24, 3, 52, 0)
    # step 조회는 하지 않아야 한다(terminal 경로에서 PG 왕복을 늘리지 않는다).
    def _must_not_call(*a, **k):
        raise AssertionError("terminal 경로가 step 을 조회했다")

    monkeypatch.setattr(app, "_last_step_at_for_run", _must_not_call)
    status, is_stale, last_active = app._compute_display_status(
        None, "cid", "done", done_at.isoformat(), "rid"
    )
    assert (status, is_stale) == ("done", False)
    assert last_active == done_at
    assert cs._iso_or_empty(last_active).endswith("+00:00")


def test_terminal_step_at_path_takes_max(monkeypatch):
    """인자형 경로는 step 시각을 이미 받았으므로 마감 write 와 그 중 나중 것을 쓴다."""
    status_at = datetime(2026, 8, 24, 3, 52, 0)
    later_step = datetime(2026, 8, 24, 3, 53, 30)
    out = app._display_status_from_step_at("done", status_at.isoformat(), later_step)
    assert out[:2] == ("done", False)
    assert out[2] == later_step


def test_last_active_prefers_latest_of_status_and_step(monkeypatch):
    """status_at 과 step 시각 중 **나중** 것이 마지막 활동이다(둘 다 갱신원)."""
    monkeypatch.setattr(app._runtime_settings, "get_int", lambda _k: 1800)
    step = datetime.utcnow() - timedelta(seconds=30)
    status_at = datetime.utcnow() - timedelta(seconds=900)
    monkeypatch.setattr(app, "_last_step_at_for_run", lambda *a, **k: step)
    _, _, last_active = app._compute_display_status(
        None, "cid", "processing", status_at.isoformat(), "rid"
    )
    assert abs((last_active - step).total_seconds()) < 2


# ── T7: 소스 잠금 — 프런트가 실제 활동 시각을 우선 쓴다 ─────────────────────────
def _static(*parts: str) -> str:
    return (Path(app.__file__).parent / "static" / Path(*parts)).read_text(encoding="utf-8")


def test_frontend_prefers_effective_activity_timestamp():
    """부제 '최근 갱신' 과 stale 툴팁 둘 다 effective 필드를 우선 참조해야 한다.

    둘 중 하나만 고치면 같은 화면에서 서로 다른 '마지막 활동' 이 보인다.
    """
    app_js = _static("app.js")
    sidebar_js = _static("app", "sidebar.js")
    assert "conversation.last_activity_effective_at || conversation.last_activity_at" in app_js
    assert "item.last_activity_effective_at || item.last_activity_at" in sidebar_js


def test_subtitle_status_is_localized_not_raw_enum():
    """부제 상태 칸에 내부 enum(stale_error)이 그대로 노출되지 않는다."""
    app_js = _static("app.js")
    assert "`상태 ${pendingStatusLabel(conversation.status)}`" in app_js
    assert "`상태 ${conversation.status}`" not in app_js
