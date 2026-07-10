"""llm-routing-interactive-split (2026-07-04) — insight 백그라운드 배치 시간 기반 모델 강등 검증.

사용자 결정(2026-07-04): 사람 호출(대화·node_analysis)은 항상 claude, 백그라운드 insight 배치는
평일 근무시간엔 claude, 야간·주말엔 gemma(edge)로 강등해 비용 절감. 강등은 litellm fallback 이
아니라 llm._effective_insight_model() 이 현재 시각(KST)으로 결정한다 — OAuth 토큰이 24/7 유효해도
insight 만 off-hours 에 gemma 로 내려가야 하기 때문(사람 호출은 항상 claude interactive alias).

이 계약이 깨지면 (a) 주말/야간에 insight 가 claude 를 써 비용/사용량 초과, 또는 (b) 평일 근무시간에
gemma 로 품질 저하 → 회귀 방어. 경계 [START, END) 시(로컬=KST)와 주말(토·일) 전일 off-hours 확인.
"""
from __future__ import annotations

from datetime import datetime, timezone

from modules import llm


def _cfg(monkeypatch, *, base="claude-haiku-4", off="edge", start=10, end=19, tz=9):
    """_effective_insight_model 이 참조하는 llm 모듈 전역(= from shared.config import * 소산)을 주입."""
    monkeypatch.setattr(llm, "AGENT_INSIGHT_MODEL", base, raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_OFFHOURS_MODEL", off, raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_BUSINESS_START_HOUR", start, raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_BUSINESS_END_HOUR", end, raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_BUSINESS_TZ_OFFSET_HOURS", tz, raising=False)


def _utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


# 참고(KST 기준): 2026-07-04=토, 07-05=일, 07-06=월, 07-07=화.

def test_weekday_business_hours_uses_claude(monkeypatch):
    _cfg(monkeypatch)
    # 화 14:00 KST = 화 05:00 UTC → 근무시간 → base(claude)
    assert llm._effective_insight_model(_utc(2026, 7, 7, 5)) == "claude-haiku-4"


def test_weekday_night_uses_gemma(monkeypatch):
    _cfg(monkeypatch)
    # 화 22:00 KST = 화 13:00 UTC → off-hours → gemma(edge)
    assert llm._effective_insight_model(_utc(2026, 7, 7, 13)) == "edge"


def test_weekday_early_morning_uses_gemma(monkeypatch):
    _cfg(monkeypatch)
    # 화 08:00 KST = 월 23:00 UTC → 근무 전(08<10) → gemma
    assert llm._effective_insight_model(_utc(2026, 7, 6, 23)) == "edge"


def test_saturday_daytime_uses_gemma(monkeypatch):
    _cfg(monkeypatch)
    # 토 14:00 KST = 토 05:00 UTC → 주말 → gemma (근무시간대여도 주말이면 강등)
    assert llm._effective_insight_model(_utc(2026, 7, 4, 5)) == "edge"


def test_sunday_early_uses_gemma(monkeypatch):
    _cfg(monkeypatch)
    # 일 03:00 KST = 토 18:00 UTC → 주말 → gemma (UTC↔KST 날짜 경계 넘어가는 케이스)
    assert llm._effective_insight_model(_utc(2026, 7, 4, 18)) == "edge"


def test_boundary_start_inclusive(monkeypatch):
    _cfg(monkeypatch)
    # 화 10:00 KST = 화 01:00 UTC → [10,19) 시작 포함 → claude
    assert llm._effective_insight_model(_utc(2026, 7, 7, 1)) == "claude-haiku-4"


def test_boundary_end_exclusive(monkeypatch):
    _cfg(monkeypatch)
    # 화 19:00 KST = 화 10:00 UTC → end 미포함 → gemma
    assert llm._effective_insight_model(_utc(2026, 7, 7, 10)) == "edge"


def test_boundary_just_before_end(monkeypatch):
    _cfg(monkeypatch)
    # 화 18:59 KST = 화 09:59 UTC → 아직 근무 → claude
    assert llm._effective_insight_model(_utc(2026, 7, 7, 9, 59)) == "claude-haiku-4"


def test_offhours_blank_disables_degrade(monkeypatch):
    _cfg(monkeypatch, off="")
    # OFFHOURS 빈값 → 강등 비활성 → 시각 무관 항상 base (토요일이어도)
    assert llm._effective_insight_model(_utc(2026, 7, 4, 5)) == "claude-haiku-4"


def test_offhours_equal_base_disables_degrade(monkeypatch):
    _cfg(monkeypatch, off="claude-haiku-4")
    assert llm._effective_insight_model(_utc(2026, 7, 4, 5)) == "claude-haiku-4"


def test_naive_datetime_treated_as_utc(monkeypatch):
    _cfg(monkeypatch)
    # tz-naive 입력은 UTC 로 간주 — 화 05:00(naive)=화 14 KST → claude
    assert llm._effective_insight_model(datetime(2026, 7, 7, 5)) == "claude-haiku-4"


def test_custom_business_window(monkeypatch):
    _cfg(monkeypatch, start=9, end=18)
    # 커스텀 09-18: 화 08:30 KST → 근무 전 → gemma / 화 09:00 KST → 근무 → claude
    assert llm._effective_insight_model(_utc(2026, 7, 6, 23, 30)) == "edge"        # 화 08:30 KST
    assert llm._effective_insight_model(_utc(2026, 7, 7, 0)) == "claude-haiku-4"   # 화 09:00 KST
