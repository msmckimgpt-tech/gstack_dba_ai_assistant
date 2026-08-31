"""conv-last-activity-updatedat — 사이드바 "최근 갱신" 이 두 활동 축 중 **나중 것**을 쓴다.

라이브 제보 (2026-08-31, 대화 `20260828073505-be34624d`): 요청을 보내 대화가 갱신됐는데도 부제의
"최근 갱신" 이 첫 턴 시각에 멈춰 있었다. 실측 — 마지막 메시지 08-31 10:54 vs 표시 08-28 16:38.

원인은 축이 **하나뿐**이었던 것이다:
  - KV 축(`last_activity_effective_at`, `_compute_display_status` 파생) = run 상태·step 시각.
    **서버 LLM run 이 있었던 대화만** 채워진다. 브리지(개인 AI 연결) 경로는 `last_status*` KV 를
    쓰지 않아 이 축이 통째로 빈다(사고 대화 실측 KV 키 0건).
  - 행 축(`last_activity_at` = `core_conversations.updated_at`) = 대화 활동 시각. 이쪽은 자동 제목
    부여 경로에서만 전진해 첫 턴에 고정돼 있었다(백엔드 측 `touch_conversation` 으로 해소).

프런트 표시식은 `effective || last_activity_at` 이라 **앞의 값이 있으면 뒤를 보지 않는다**. 따라서
서버가 두 축의 max 를 실어야 한다 — 서버 LLM 으로 시작해 브리지로 이어간 대화는 KV 가 첫 run
시각에 멈춘 채 남아 있고, KV 를 무조건 우선하면 그 대화에서 같은 결함이 되살아난다.

여기서 잠그는 계약:
  T1 KV 축만 있으면 그 값 (종전 동작 보존 — 진행 중 run 의 step 시각 우선).
  T2 행 축만 있으면 그 값 (브리지 경로 — 사고 시나리오의 직접 회귀).
  T3 둘 다 있으면 **나중 것** (혼합 경로 대화에서 KV 가 표시를 뒤로 끌어당기지 못한다).
  T4 tz 없는 행 값은 비교에서 제외 (MySQL naive DATETIME 을 UTC 로 오해 → 9시간 미래 점거 차단).
  T5 빈 입력은 빈 문자열 (프런트가 `created_at` 으로 폴백).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from routers import _conv_store as cs

KST = timezone(timedelta(hours=9))


# ── T1: KV 축 단독 ──────────────────────────────────────────────────────────────
def test_kv_axis_alone_is_used():
    kv = datetime(2026, 8, 31, 1, 54, 39)  # UTC naive — 판정 계층의 시간축
    assert cs._effective_activity_at(kv, "") == kv


def test_kv_axis_tz_aware_normalized_to_utc_naive():
    """판정 계층은 UTC naive 로 비교한다 — aware 가 섞이면 비교가 TypeError 로 죽는다."""
    kv = datetime(2026, 8, 31, 10, 54, 39, tzinfo=KST)
    assert cs._effective_activity_at(kv, "") == datetime(2026, 8, 31, 1, 54, 39)


# ── T2: 행 축 단독 (브리지 경로 = 사고 시나리오) ──────────────────────────────────
def test_row_axis_alone_is_used_when_kv_absent():
    """브리지 대화는 `last_status*` KV 가 없다 — 행 축이 유일한 활동 신호다."""
    got = cs._effective_activity_at(None, "2026-08-31 10:54:39.405521+09:00")
    assert got == datetime(2026, 8, 31, 1, 54, 39, 405521)


def test_row_axis_accepts_datetime_object():
    row = datetime(2026, 8, 31, 10, 54, 39, tzinfo=KST)
    assert cs._effective_activity_at(None, row) == datetime(2026, 8, 31, 1, 54, 39)


# ── T3: 두 축 공존 → 나중 것 ─────────────────────────────────────────────────────
def test_later_axis_wins_when_row_is_newer():
    """사고 대화의 형태: KV 가 첫 run 시각에 멈춰 있고 행이 최신.

    KV 를 무조건 우선하면(종전 `effective || row` 표시식) 표시가 첫 턴으로 되돌아간다.
    """
    kv = datetime(2026, 8, 28, 7, 38, 7)                      # 08-28 16:38 KST
    row = "2026-08-31 10:54:39.405521+09:00"                   # 08-31 10:54 KST
    assert cs._effective_activity_at(kv, row) == datetime(2026, 8, 31, 1, 54, 39, 405521)


def test_later_axis_wins_when_kv_is_newer():
    """진행 중 run: step 시각(KV)이 행 UPDATE 보다 앞서 간다 — 종전 개선을 되돌리지 않는다."""
    kv = datetime(2026, 8, 31, 3, 2, 0)
    row = "2026-08-31 11:19:00+09:00"                          # = 02:19 UTC
    assert cs._effective_activity_at(kv, row) == kv


# ── T4: tz 미지 값은 비교에서 제외 ────────────────────────────────────────────────
def test_naive_row_value_is_excluded_from_comparison():
    """MySQL 경로의 naive DATETIME 을 UTC 로 읽으면 KST 환경에서 9시간 미래가 되어 max 를
    영구 점거한다 (`_iso_or_empty` 가 봉인한 CHG-20260527-0001 tz 회귀와 같은 입구)."""
    kv = datetime(2026, 8, 31, 1, 54, 39)
    assert cs._effective_activity_at(kv, "2026-08-31 10:54:39") == kv


def test_naive_row_alone_yields_none():
    """tz 를 모르는 값 하나뿐이면 표면에 내보내지 않는다 — 프런트가 종전 필드로 폴백한다."""
    assert cs._effective_activity_at(None, "2026-08-31 10:54:39") is None


def test_unparsable_row_value_is_ignored():
    kv = datetime(2026, 8, 31, 1, 54, 39)
    assert cs._effective_activity_at(kv, "not-a-timestamp") == kv
    assert cs._effective_activity_at(None, "not-a-timestamp") is None


# ── T5: 빈 입력 ─────────────────────────────────────────────────────────────────
def test_empty_inputs_yield_none():
    assert cs._effective_activity_at(None, "") is None
    assert cs._effective_activity_at(None, None) is None


def test_iso_serialization_keeps_utc_marker():
    """표면 직렬화는 tz 를 명시한다 — 프런트 `new Date()` 가 로컬로 오해하지 않도록."""
    got = cs._iso_or_empty(cs._effective_activity_at(None, "2026-08-31 10:54:39+09:00"))
    assert got.endswith("+00:00")
    assert got.startswith("2026-08-31T01:54:39")


# ── 소스 잠금: 두 목록 경로 모두 max 를 통과한다 ───────────────────────────────────
def test_both_list_paths_route_through_effective_helper():
    """PG 경로와 MySQL 경로 두 곳 다 세팅한다 — 한쪽만 고치면 백엔드 전환 시 결함이 되살아난다."""
    from pathlib import Path

    src = Path(cs.__file__).read_text(encoding="utf-8")
    calls = src.count('_iso_or_empty(\n                _effective_activity_at(last_active, item.get("last_activity_at"))')
    assert calls == 2, f"목록 경로 2곳 중 {calls}곳만 max 를 통과한다"
    assert "_iso_or_empty(last_active)" not in src, "raw last_active 를 그대로 내보내는 경로가 남아 있다"
