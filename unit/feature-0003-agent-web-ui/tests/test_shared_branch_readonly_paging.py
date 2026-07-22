"""feature-0019 shared-readonly-paging 보안 단위 테스트.

공유/그룹·익명 공유-링크 뷰에서 편집 버전 페이징을 **읽기전용 + 가시성 scoped** 로 여는 백엔드
헬퍼의 보안 게이트를 고정한다. 핵심 위협: 멤버/익명 뷰어가 자기 가시 범위(window/공유 id-범위)
**밖** 버전을 카운트·sibling_ids·존재·내용으로 누출/프로빙하는 것(fail-closed 여야 함).
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src")))

import routers._conv_store as cs
import shared.db as sdb


class _Cur:
    def __init__(self, pg):
        self.pg = pg
        self.r = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.r = self.pg.results.pop(0) if self.pg.results else None

    def fetchone(self):
        if isinstance(self.r, list):
            return self.r[0] if self.r else None
        return self.r

    def fetchall(self):
        return self.r if isinstance(self.r, list) else ([] if self.r is None else [self.r])


class _Pg:
    def __init__(self, results):
        self.results = list(results)

    def cursor(self):
        return _Cur(self)

    def close(self):
        pass


# ── id-범위 술어 (익명 공유 스냅샷 가시성 게이트) — 순수 로직 ──

def test_idrange_pred_bounds():
    p = cs._branch_idrange_pred(1270, 1290)  # [floor, anchor]
    assert p(1271, None, None, "user") is True
    assert p(1270, None, None, "user") is True     # 경계 inclusive
    assert p(1290, None, None, "user") is True
    assert p(1269, None, None, "user") is False    # floor 아래(가려짐)
    assert p(1299, None, None, "user") is False    # anchor 위(공유 범위 밖 — 누출 차단)


def test_idrange_pred_open_bounds():
    assert cs._branch_idrange_pred(None, None) is None            # 무제한 → 술어 없음(전체)
    p_lo = cs._branch_idrange_pred(1270, None)
    assert p_lo(1269, None, None, "user") is False and p_lo(9999, None, None, "user") is True
    p_hi = cs._branch_idrange_pred(None, 1290)
    assert p_hi(1, None, None, "user") is True and p_hi(1291, None, None, "user") is False


# ── 버전 그룹 window 스코핑 (누출 게이트) ──

def test_version_groups_filters_out_of_range_siblings():
    # 형제 4개(1271,1277,1289,1299) parent 1270 — 공유 window[1270,1290] 이면 1299 는 범위 밖.
    rows = [
        ("1270", 1271, None, None, "user"),
        ("1270", 1277, None, None, "user"),
        ("1270", 1289, None, None, "user"),
        ("1270", 1299, None, None, "user"),  # anchor(1290) 위 — 배제돼야
    ]
    pg = _Pg([rows])
    groups = cs._branch_version_groups(pg, "cid", visible_pred=cs._branch_idrange_pred(1270, 1290))
    assert groups == {"1270": [1271, 1277, 1289]}, "범위 밖 1299 는 카운트·sibling_ids 에서 배제(누출 차단)"


def test_version_groups_no_pred_returns_all():
    rows = [("1270", 1271), ("1270", 1299)]
    pg = _Pg([rows])
    groups = cs._branch_version_groups(pg, "cid", visible_pred=None)  # owner/1:1 → 전체
    assert groups == {"1270": [1271, 1299]}


def test_version_groups_singleton_not_returned():
    rows = [("1270", 1271), ("__root__", 1200)]
    pg = _Pg([rows])
    assert cs._branch_version_groups(pg, "cid", visible_pred=None) == {}  # version_count<=1 제외


# ── 읽기전용 대상 검증 + leaf 해소 (fail-closed) ──

def _patch_pg(monkeypatch, results):
    monkeypatch.setattr(sdb, "_pg_connect", lambda *a, **k: _Pg(results))


def test_resolve_readonly_leaf_valid_in_range(monkeypatch):
    # SELECT → user 메시지(id=1277, 범위 내), 그다음 _branch_leaf_of → leaf=1278
    _patch_pg(monkeypatch, [(1277, None, None, "user"), (1278,)])
    leaf = cs._branch_resolve_readonly_leaf("cid", 1277, floor_id=1270, anchor_id=1290)
    assert leaf == 1278


def test_resolve_readonly_leaf_out_of_range_denied(monkeypatch):
    # 대상이 범위 밖(id=1299 > anchor 1290) → None(fail-closed, leaf 조회도 안 함)
    _patch_pg(monkeypatch, [(1299, None, None, "user")])
    assert cs._branch_resolve_readonly_leaf("cid", 1299, floor_id=1270, anchor_id=1290) is None


def test_resolve_readonly_leaf_non_user_denied(monkeypatch):
    _patch_pg(monkeypatch, [(1278, None, None, "assistant")])  # user 아님 → None
    assert cs._branch_resolve_readonly_leaf("cid", 1278, floor_id=1270, anchor_id=1290) is None


def test_resolve_readonly_leaf_missing_denied(monkeypatch):
    _patch_pg(monkeypatch, [None])  # 없는 메시지 → None
    assert cs._branch_resolve_readonly_leaf("cid", 999999, floor_id=1270, anchor_id=1290) is None


def test_resolve_readonly_leaf_none_target(monkeypatch):
    assert cs._branch_resolve_readonly_leaf("cid", None) is None  # 파싱 전 조기 None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))


# ── [SEC-3 회귀] 브랜치된 그룹의 사람-채팅이 active-path 에서 은닉되지 않도록 체인 ──

class _PgConnStub:
    def cursor(self):
        class _C:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def execute(s, *a, **k): pass
        return _C()
    def commit(self):
        pass
    def close(self):
        pass


def test_group_chat_chains_onto_branch_when_has_branches(monkeypatch):
    """브랜치된 대화(has_branches)에서 사람-채팅 미러가 active_leaf 에 체인 + 전진 →
    active-path 필터(공유/그룹 읽기전용 페이징)에서 은닉되지 않는다(적대 보안리뷰 [3] 봉인)."""
    import modules.runtime_backend as rb
    calls = {}

    class _BE:
        def load_branch_state(self, pg, *, conversation_id):
            return {"has_branches": True, "active_leaf_id": 5000}
        def load_display_branch_state(self, pg, *, conversation_id):
            return {"has_branches": True, "active_leaf_id": 1000}
        def save_core_message(self, pg, *, conversation_id, role, content, sender_account_id, parent_message_id=None):
            calls["core_parent"] = parent_message_id
            return 5001
        def save_memory_message(self, pg, *, conversation_id, role, content, meta_json, parent_message_id=None, **kw):
            calls["disp_parent"] = parent_message_id
            return 1001
        def set_active_leaf(self, pg, *, conversation_id, leaf_id):
            calls["core_leaf"] = leaf_id
        def set_active_display_leaf(self, pg, *, conversation_id, leaf_id):
            calls["disp_leaf"] = leaf_id

    monkeypatch.setattr(rb, "_get_pg_runtime_backend", lambda: _BE())
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _PgConnStub())
    cs._save_group_chat_message_pg("cid", 42, "안녕하세요", username="member")
    assert calls["core_parent"] == 5000, "core 는 active_leaf 에 체인(고아 아님)"
    assert calls["disp_parent"] == 1000, "display 는 active_display_leaf 에 체인"
    assert calls["core_leaf"] == 5001 and calls["disp_leaf"] == 1001, "두 store leaf 전진"


def test_group_chat_nonbranch_stays_linear(monkeypatch):
    """비분기 대화(has_branches=false, 거의 전부): parent None·leaf 미전진(기존 linear append, 무회귀)."""
    import modules.runtime_backend as rb
    calls = {}

    class _BE:
        def load_branch_state(self, pg, *, conversation_id):
            return {"has_branches": False, "active_leaf_id": None}
        def save_core_message(self, pg, *, conversation_id, role, content, sender_account_id, parent_message_id=None):
            calls["core_parent"] = parent_message_id
            return 7
        def save_memory_message(self, pg, *, conversation_id, role, content, meta_json, parent_message_id=None, **kw):
            calls["disp_parent"] = parent_message_id
            return 8
        def set_active_leaf(self, *a, **k):
            calls["advanced"] = True
        def set_active_display_leaf(self, *a, **k):
            calls["advanced"] = True

    monkeypatch.setattr(rb, "_get_pg_runtime_backend", lambda: _BE())
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _PgConnStub())
    cs._save_group_chat_message_pg("cid", 42, "hi")
    assert calls["core_parent"] is None and calls["disp_parent"] is None, "비분기 = parent 미설정"
    assert "advanced" not in calls, "비분기 = leaf 전진 안 함(무회귀)"
