"""share-visibility-window — 표시(view) 필터 · fork 교집합 window · 첨부 clip 회귀.

`make test`(agent 이미지, --no-deps)에서 실행. app 모듈은 conftest 경로로 import 된다.
검증(SECURITY.md §21):
  - _msg_outside_window: [floor,ceiling]∪[joined,∞) + owner-answer display-tag, fail-closed.
  - _resolve_copy_window: INTERSECTION(share window, 멤버 window), deny/empty.
  - _attachment_outside_window / _coerce_naive_dt: windowed fork 첨부 clip(fail-closed skip).
"""
from __future__ import annotations

import datetime as _dt

import app as appmod


# ── _coerce_naive_dt / _attachment_outside_window ────────────────────────────

def test_coerce_naive_strips_tz_and_parses_iso():
    aware = _dt.datetime(2026, 7, 4, 1, 2, 3, tzinfo=_dt.timezone.utc)
    assert appmod._coerce_naive_dt(aware) == _dt.datetime(2026, 7, 4, 1, 2, 3)
    assert appmod._coerce_naive_dt("2026-07-04T01:02:03") == _dt.datetime(2026, 7, 4, 1, 2, 3)
    assert appmod._coerce_naive_dt(None) is None
    assert appmod._coerce_naive_dt("nonsense") is None


def test_attachment_window_clip():
    lo = _dt.datetime(2026, 1, 10)
    hi = _dt.datetime(2026, 1, 20)
    # 범위 안 → 유지
    assert appmod._attachment_outside_window(_dt.datetime(2026, 1, 15), lo, hi) is False
    # 하단 아래 / 상단 위 → 배제
    assert appmod._attachment_outside_window(_dt.datetime(2026, 1, 5), lo, hi) is True
    assert appmod._attachment_outside_window(_dt.datetime(2026, 1, 25), lo, hi) is True
    # CreatedAt 불명(None) + window 활성 → fail-closed skip
    assert appmod._attachment_outside_window(None, lo, hi) is True
    # 한쪽 경계만
    assert appmod._attachment_outside_window(_dt.datetime(2026, 1, 5), lo, None) is True
    assert appmod._attachment_outside_window(_dt.datetime(2026, 1, 25), None, hi) is True


# ── _msg_outside_window ──────────────────────────────────────────────────────

def _win(floor_id=None, ceiling_id=None, joined_at=None, floor_ca=None):
    return {"floor_id": floor_id, "ceiling_id": ceiling_id, "joined_at": joined_at, "floor_ca": floor_ca}


def test_msg_below_floor_hidden():
    w = _win(floor_id=100)
    assert appmod._msg_outside_window(50, _dt.datetime(2026, 1, 1), {}, "user", w) is True
    assert appmod._msg_outside_window(150, _dt.datetime(2026, 1, 1), {}, "user", w) is False
    assert appmod._msg_outside_window(100, _dt.datetime(2026, 1, 1), {}, "user", w) is False  # inclusive


def test_msg_above_ceiling_hidden_unless_live_tail():
    joined = _dt.datetime(2026, 7, 1)
    w = _win(ceiling_id=200, joined_at=joined)
    # ceiling 초과 + 참여 이전(created_at < joined) = 은닉된 중간 갭
    assert appmod._msg_outside_window(250, _dt.datetime(2026, 6, 1), {}, "user", w) is True
    # ceiling 초과지만 참여 이후(라이브 tail) → 보임
    assert appmod._msg_outside_window(250, _dt.datetime(2026, 7, 5), {}, "user", w) is False


def test_msg_owner_answer_recall_full_hidden_from_bounded_viewer():
    w = _win(floor_id=100, floor_ca=_dt.datetime(2026, 7, 1))
    # recall_full 답변(무제한 문맥) → floor 가진 뷰어에게 은닉 (id 는 window 안이어도)
    assert appmod._msg_outside_window(150, _dt.datetime(2026, 7, 9), {"recall_full": True}, "assistant", w) is True
    # 태그 없는 assistant 답변은 id 만으로 판정(window 안 → 보임)
    assert appmod._msg_outside_window(150, _dt.datetime(2026, 7, 9), {}, "assistant", w) is False


def test_msg_owner_answer_recall_floor_older_than_viewer_hidden():
    vf = _dt.datetime(2026, 7, 1)
    w = _win(floor_id=100, floor_ca=vf)
    older = {"recall_floor_created_at": _dt.datetime(2026, 6, 1).isoformat()}  # 뷰어 floor 보다 이른 문맥
    assert appmod._msg_outside_window(150, _dt.datetime(2026, 7, 9), older, "assistant", w) is True
    newer = {"recall_floor_created_at": _dt.datetime(2026, 7, 2).isoformat()}  # 뷰어 floor 이후
    assert appmod._msg_outside_window(150, _dt.datetime(2026, 7, 9), newer, "assistant", w) is False


def test_msg_failclosed_on_bad_comparison():
    # created_at 이 None 인데 ceiling+joined 판정 필요 → fail-closed(숨김)
    w = _win(ceiling_id=200, joined_at=_dt.datetime(2026, 7, 1))
    assert appmod._msg_outside_window(250, None, {}, "user", w) is True


# ── _resolve_copy_window (monkeypatched _member_visibility_window) ────────────

def test_copy_window_intersection(monkeypatch):
    # 멤버 window [100,300], share window [50,250] → 교집합 [100,250]
    monkeypatch.setattr(appmod, "_member_visibility_window", lambda *a, **k: (100, 300))
    status, lo, hi = appmod._resolve_copy_window(None, "c1", 9, share_floor_id=50, share_ceiling_id=250)
    assert (status, lo, hi) == ("ok", 100, 250)


def test_copy_window_member_unbounded_uses_share(monkeypatch):
    monkeypatch.setattr(appmod, "_member_visibility_window", lambda *a, **k: (None, None))
    status, lo, hi = appmod._resolve_copy_window(None, "c1", 9, share_floor_id=50, share_ceiling_id=250)
    assert (status, lo, hi) == ("ok", 50, 250)


def test_copy_window_deny_on_member_error(monkeypatch):
    monkeypatch.setattr(appmod, "_member_visibility_window", lambda *a, **k: "DENY")
    assert appmod._resolve_copy_window(None, "c1", 9, share_floor_id=None, share_ceiling_id=None)[0] == "deny"


def test_copy_window_empty_intersection(monkeypatch):
    # 멤버 [300,None], share ceiling 200 → lower 300 > upper 200 → empty
    monkeypatch.setattr(appmod, "_member_visibility_window", lambda *a, **k: (300, None))
    assert appmod._resolve_copy_window(None, "c1", 9, share_floor_id=None, share_ceiling_id=200)[0] == "empty"
