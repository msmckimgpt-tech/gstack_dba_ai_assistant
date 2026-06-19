"""그룹 대화 S2 (Membership) 소스-계약 회귀 테스트 — feature-0009-group-conversation.

app import 없이 app.py/admin.js 텍스트를 검사해 핵심 계약을 고정한다(make test --no-deps,
DB·런타임 의존 불요). 통합/엔드포인트 동작 검증은 컨테이너 make test + 라이브에서 별도.
핵심 불변식:
  - 멤버십 OR 이 _list_conversations 양 경로(PG + MySQL)에 존재.
  - _account_can_access_conversation / _account_can_access_attachment 가 멤버십(_account_is_conversation_member)을 OR 로 포함.
  - 멤버 관리 엔드포인트 3개 등록 + 신규 권한 + audit action.
  - 신규 권한이 admin.js 의존성 맵에서 conversation.list.own 게이트 아래 중첩.
"""
from __future__ import annotations

from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
APP = (_SRC / "app.py").read_text(encoding="utf-8")
ADMIN_JS = (_SRC / "static" / "admin.js").read_text(encoding="utf-8")


def test_membership_or_in_both_list_paths():
    # PG 경로: agent_runtime.conversation_members 서브쿼리 OR.
    assert "SELECT conversation_id FROM agent_runtime.conversation_members" in APP
    # MySQL parity 경로: AgentCoreConversationMembers 서브쿼리 OR.
    assert "SELECT conversation_id FROM AgentCoreConversationMembers" in APP


def test_access_helpers_include_membership():
    # 중앙 게이트 + 첨부 게이트가 멤버십을 OR 로 포함해야 IDOR 없이 멤버 열람 가능(F6).
    assert "def _account_is_conversation_member(" in APP
    assert APP.count("_account_is_conversation_member(") >= 3  # 정의 + 대화게이트 + 첨부게이트


def test_member_endpoints_registered():
    assert '@app.get("/api/conversations/{cid}/members")' in APP
    assert '@app.post("/api/conversations/{cid}/members")' in APP
    assert '@app.delete("/api/conversations/{cid}/members/{account_id}")' in APP


def test_member_manage_permission_and_audit():
    assert '"code": "conversation.member.manage"' in APP
    assert 'action="conversation.member.add"' in APP
    assert 'action="conversation.member.remove"' in APP


def test_owner_cannot_be_removed_guard():
    # 소유자 멤버 제거 차단(409) 가드 존재.
    assert "대화 소유자는 멤버에서 제거할 수 없습니다." in APP


def test_invite_is_owner_or_manage_gated():
    # 멤버 추가는 owner 또는 conversation.member.manage 권한 게이트.
    assert 'conversation.member.manage' in APP
    assert "멤버를 관리할 권한이 없습니다." in APP


def test_permission_nested_under_list_gate_in_admin_js():
    # 신규 권한이 admin.js 의존성 맵에서 conversation.list.own 게이트 아래(progressive disclosure).
    assert '"conversation.member.manage": "conversation.list.own"' in ADMIN_JS
