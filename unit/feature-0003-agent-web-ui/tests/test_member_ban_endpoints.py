"""member-kick-ban 엔드포인트 authz 소스 계약 테스트 — feature-0009.

실 DB/HTTP 없이 app.py 를 ast 로 파싱해, ban/unban/bans 엔드포인트와 join 엔드포인트의
**핵심 인가 게이트**(엄격 owner 전용, 소유자/자기 차단 금지, 차단자 join 거부)를 회귀 고정한다.
라이브 authz 검증은 PB-0008/배포 후 — 본 테스트는 owner-only 가드가 소스에서 사라지지 않게 막는다.
"""
from __future__ import annotations

import ast
import os

APP_PY = os.path.join(
    os.path.dirname(__file__), "..", "src", "app.py"
)


def _func_src(name: str) -> str:
    with open(APP_PY, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(src, node)
            assert seg, f"source segment empty for {name}"
            return seg
    raise AssertionError(f"function {name} not found in app.py")


# ── ban 엔드포인트: 엄격 owner 전용 + 가드 ──────────────────────────────────
def test_ban_endpoint_is_owner_only_strict():
    s = _func_src("ban_conversation_member")
    # owner 전용: _conversation_owned_by_account 게이트로 403.
    assert "_conversation_owned_by_account(conn, cid, actor_id)" in s
    assert '대화 소유자만 멤버를 차단할 수 있습니다.' in s
    # 엄격 owner 전용 — conversation.member.manage 보유자도 통과 못 함(ban 경로에 manage 분기 없음).
    assert '_account_has_permission(account, "conversation.member.manage")' not in s
    # 소유자/자기 자신은 차단 불가(409 가드).
    assert "대화 소유자는 차단할 수 없습니다." in s
    assert "자기 자신은 차단할 수 없습니다." in s
    # 멤버 제거 + ban 목록 등재 + audit.
    assert "group_members.remove_member(pg, cid, target_id)" in s
    assert "group_members.ban_member(" in s
    assert 'action="conversation.member.ban"' in s
    # 유효하지 않은 대상(<=0) 거부.
    assert "if target_id <= 0:" in s
    # 비원자 fail-window 안전화: ban_member 가 remove_member 보다 먼저(차단 등재됨+멤버 잔존 방향).
    assert s.index("ban_member(") < s.index("remove_member(pg, cid, target_id)")


def test_fork_rejects_banned_account():
    """적대 리뷰 BLOCKER 회귀 가드: 차단된 account 는 share-token fork 로도 거부(403, fail-closed)."""
    s = _func_src("public_share_fork")
    assert "is_banned(" in s, "fork 에 is_banned 게이트가 있어야 함(BLOCKER 회귀)"
    assert "이 대화에서 차단되어" in s
    assert 'action="conversation.member.fork_blocked"' in s
    # fail-closed: 예외 시 _fk_banned = True.
    assert "_fk_banned = True" in s
    # 차단 게이트가 실제 복제(_fork_conversation_impl) 보다 먼저.
    assert s.index("is_banned(") < s.index("_fork_conversation_impl(")


def test_unban_endpoint_is_owner_only():
    s = _func_src("unban_conversation_member")
    assert "_conversation_owned_by_account(conn, cid, actor_id)" in s
    assert '_account_has_permission(account, "conversation.member.manage")' not in s
    assert "group_members.unban_member(pg, cid, target_id)" in s
    assert 'action="conversation.member.unban"' in s


def test_bans_list_endpoint_is_owner_only():
    s = _func_src("list_conversation_bans")
    assert "_conversation_owned_by_account(conn, cid, actor_id)" in s
    assert '_account_has_permission(account, "conversation.member.manage")' not in s
    assert "group_members.list_bans(pg, cid)" in s


# ── join 엔드포인트: 차단자 재참여 거부 ──────────────────────────────────────
def test_join_rejects_banned_account():
    s = _func_src("join_conversation_via_share")
    assert "is_banned(" in s
    assert "이 대화에서 차단되어 참여할 수 없습니다." in s
    assert '"403"' in s or "403" in s
    # 차단 체크가 멱등 already 체크/멤버 추가보다 먼저 (banned 면 add_member 도달 안 함).
    idx_ban = s.index("is_banned(")
    idx_add = s.index("add_member(")
    assert idx_ban < idx_add, "ban check must precede add_member"
    assert 'action="conversation.member.join_blocked"' in s
