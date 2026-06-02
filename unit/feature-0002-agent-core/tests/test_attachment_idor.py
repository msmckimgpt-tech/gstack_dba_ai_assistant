"""TASK-0132 (#8): 첨부 IDOR 회귀 테스트.

`_build_attachment_context_section` 이 account_id 를 요구하고(fail-closed) 쿼리를 AccountId 로
스코프하는지 검증한다. 이전엔 ATTACHMENT_IDS(os.environ, 요청 제어) 를 Id IN(...) 만으로
조회해 타 계정 첨부 메타가 prompt 에 유출됐고, os.environ 동시요청 race 까지 겹쳤다.
"""
from __future__ import annotations

import agent_core


def test_attachment_context_requires_account_id():
    """account_id 없으면 fail-closed (빈 섹션) — 무계정 컨텍스트에서 첨부 노출 금지."""
    assert agent_core._build_attachment_context_section(object(), [1, 2], account_id=None) == ""
    # mem_conn None 도 빈 섹션
    assert agent_core._build_attachment_context_section(None, [1, 2], account_id=7) == ""
    # attachment_ids 비면 빈 섹션
    assert agent_core._build_attachment_context_section(object(), [], account_id=7) == ""


def test_attachment_context_scopes_by_account():
    """account_id 주어지면 쿼리가 AccountId = %s 로 스코프되고 params 에 account_id 포함."""
    captured: dict = {}

    class FakeCur:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCur()

    agent_core._build_attachment_context_section(FakeConn(), [101, 202], account_id=7)
    assert "AccountId = %s" in captured["sql"], "쿼리에 AccountId 스코프 누락 (IDOR 회귀)"
    assert 7 in tuple(captured["params"]), "params 에 account_id 누락"
    # 타 계정 id(99) 로는 동일 attachment_ids 라도 account_id 가 99 로 들어가 row 0 (DB 레벨 차단)
    agent_core._build_attachment_context_section(FakeConn(), [101, 202], account_id=99)
    assert 99 in tuple(captured["params"]) and 7 not in tuple(captured["params"])
