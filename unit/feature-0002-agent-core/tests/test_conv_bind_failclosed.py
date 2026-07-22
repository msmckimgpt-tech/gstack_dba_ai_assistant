"""feature-0019 branch-hardening — 대화 바인딩 fail-closed 회귀 테스트.

웹/ask 경로(account_id 지정)에서 conversation_id 가 비어 있으면, `agent_core._run_agent_core` 는
프로세스 전역 env(AGENT_CONVERSATION_ID)·호스트 공유 파일(/shared/conversation_id) 폴백
(`_get_conversation_id`)을 쓰지 않고 즉시 실패한다(cross-conversation 누출 표면 봉인). CLI/eval
(account_id=None)은 파일 폴백을 유지한다(정당 — 단일 사용자 로컬).

(참고: 브랜치 체인 산란 방지 footgun B 는 PR #874/#875 'branch-chain-race' 로 이미 main 에 랜딩됨
 — runtime_backend.branch_run_active/branch_chain_* 메커니즘. 본 파일은 fail-closed 대화 바인딩 전용.)

`make test`(agent 이미지)에서 DB 없이 실행된다.
"""
from __future__ import annotations

import agent_core


def test_web_path_empty_conversation_id_fails_closed(monkeypatch):
    """account_id 지정(웹/ask) + conversation_id=None → fail-closed, 전역/공유 폴백 미호출."""
    called = {"get_conv": False}

    def _spy(*a, **k):
        called["get_conv"] = True
        return "LEAKED-SHARED-CID"  # 전역 env/공유 파일에 있을 법한 값

    monkeypatch.setattr(agent_core, "_get_conversation_id", _spy)
    res = agent_core.run_agent(
        "hi", conversation_id=None, account_id=7,
        model="claude-haiku-4-5-20251001",
    )
    assert res.get("error")                          # fail-closed 에러
    assert res.get("conversation_id") in ("", None)  # 어떤 대화에도 바인딩 안 함
    assert called["get_conv"] is False               # 전역/공유 대화 폴백 미사용(핵심)


def test_web_path_empty_string_conversation_id_fails_closed(monkeypatch):
    """conversation_id='' (빈 문자열) 도 falsy → fail-closed, 폴백 미호출."""
    called = {"get_conv": False}
    monkeypatch.setattr(
        agent_core, "_get_conversation_id",
        lambda *a, **k: called.__setitem__("get_conv", True) or "X",
    )
    res = agent_core.run_agent(
        "hi", conversation_id="", account_id=3, model="claude-haiku-4-5-20251001",
    )
    assert res.get("error")
    assert called["get_conv"] is False


def test_cli_path_does_not_trigger_failclosed():
    """account_id=None(CLI/eval)은 fail-closed 를 발동시키지 않는다(파일 폴백 정당).

    테스트 환경엔 LLM 자격증명이 없어 run 은 다른 사유로 조기 종료될 수 있으나(무방),
    반환 에러가 fail-closed '대화 컨텍스트' 에러여선 안 된다 — account_id=None 은 가드 대상 아님."""
    res = agent_core.run_agent(
        "hi", conversation_id=None, account_id=None,
        model="claude-haiku-4-5-20251001",
    )
    err = res.get("error") or ""
    assert "conversation_id 미지정" not in err
    assert "대화 컨텍스트를 확인할 수 없습니다" not in err


def test_web_path_with_conversation_id_passes_guard(monkeypatch):
    """account_id + conversation_id 둘 다 지정 → 가드 통과(폴백 미호출, cid 그대로 사용)."""
    called = {"get_conv": False}
    monkeypatch.setattr(
        agent_core, "_get_conversation_id",
        lambda *a, **k: called.__setitem__("get_conv", True) or "SHOULD-NOT-USE",
    )
    res = agent_core.run_agent(
        "hi", conversation_id="conv-explicit-123", account_id=7,
        model="claude-haiku-4-5-20251001",
    )
    # 가드는 통과(fail-closed 에러 아님). LLM 미설정 등 다른 에러로 끝날 수 있으나 무방.
    assert "conversation_id 미지정" not in (res.get("error") or "")
    assert called["get_conv"] is False  # conversation_id 명시 → 폴백 미호출
