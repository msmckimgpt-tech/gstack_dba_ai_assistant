"""SEC-20260723 REV-share-window — share 목록/폐기 authz 하드닝 회귀 테스트.

feature-0023 토큰 cross-account 감사 중 발견된 pre-existing 결함 2건 수정 검증:
- MEDIUM: `list_conversation_shares` 가 owner 2차 게이트 없이 `read.own` 멤버에게 전 share
  토큰을 노출 → 윈도우 제한 멤버가 full-scope share 토큰으로 가시성 윈도우 escape.
- LOW: `revoke_share` 가 미인가자에게 404(미존재)/403(존재-미인가)로 존재 oracle 노출.

DB 의존 핸들러라 소스-구조 검사(repo idiom: test_group_conversation_s2 동형)로 가드 상주를
검증한다. 실제 동작은 라이브 배터리(TEST.md §3)로 확증.

실행: python3 -m pytest unit/feature-0003-agent-web-ui/tests/test_share_list_owner_gate.py
"""
from __future__ import annotations

import ast
import os

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")


def _func_source(path: str, name: str) -> str:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(open(path, encoding="utf-8").read(), node) or ""
    raise AssertionError(f"{name} not found in {path}")


def test_list_conversation_shares_filters_non_owner_to_self():
    src = _func_source(os.path.join(_SRC, "routers", "conversations.py"), "list_conversation_shares")
    # 1차: 존재/접근 게이트 유지
    assert "_account_can_access_conversation" in src
    # owner/.any 감사자 판정 존재
    assert "_conversation_owned_by_account" in src, "owner 판정 누락"
    assert "conversation.read.any" in src
    assert "is_owner_or_auditor" in src, "owner/auditor 분기 플래그 누락"
    # 비-owner 는 CreatedBy=self 로 필터돼야(타인 full-scope 토큰 은닉 → escape 봉인)
    assert "CreatedBy = %s" in src, "비-owner CreatedBy 필터 누락(escape 봉인)"
    # owner/auditor 판정이 Token SQL 보다 앞
    gate_pos = src.index("is_owner_or_auditor")
    sql_pos = src.index("WebConversationShares")
    assert gate_pos < sql_pos, "owner 판정이 share Token SQL 보다 앞에 있어야 함"


def test_revoke_share_no_existence_oracle():
    src = _func_source(os.path.join(_SRC, "routers", "share.py"), "revoke_share")
    assert "is_creator or is_admin" in src
    authz_pos = src.index("is_creator or is_admin")
    # 실제 already_revoked 코드 분기(`RevokedAt") is not None`)를 앵커로 — 주석 텍스트가 아니라
    # 코드 순서를 검증(REV FINDING-B: 주석 앵커 tautology 회피).
    revoked_code = src.index('RevokedAt") is not None')
    assert authz_pos < revoked_code, "authz 검사가 already_revoked 코드 분기보다 앞이어야(oracle 봉인)"
    # 미인가 응답이 403 이 아니라 404(미존재와 동일)여야 존재 oracle 제거.
    # authz 실패 직후 return 이 404 여야 하고, 그 구간에 403 은 없어야 한다.
    seg = src[authz_pos:revoked_code]
    assert "404" in seg, "미인가 응답이 404(not-found 균질화)여야 함"
    assert "403" not in seg, "미인가 응답에 403 이 남아 있으면 안 됨(oracle 잔존)"


if __name__ == "__main__":
    import sys
    test_list_conversation_shares_filters_non_owner_to_self()
    test_revoke_share_no_existence_oracle()
    print("SEC share-window 가드 테스트 PASS")
    sys.exit(0)
