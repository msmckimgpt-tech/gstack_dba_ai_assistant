"""_merge_consecutive_user_messages 단위 테스트 — feature-0009-group-conversation (S3c).

그룹 대화에서 사람-사람 채팅(연속 user 메시지)이 @assistant 호출 사이에 쌓이면 role 교대
제약(Anthropic/Bedrock)을 위반할 수 있다 → 연속 user 를 단일 user 턴으로 병합. 본 테스트는
병합 정확성 + 무회귀(비-연속/비-string content)를 고정한다. (make test 컨테이너에서 실행 —
agent_core import 는 런타임 의존 필요.)
"""
from __future__ import annotations

import agent_core as ac


def test_merges_consecutive_user_turns():
    msgs = [
        {"role": "user", "content": "안녕"},
        {"role": "user", "content": "테이블 보여줘"},
        {"role": "user", "content": "@assistant 에러율은?"},
    ]
    out = ac._merge_consecutive_user_messages(msgs)
    assert len(out) == 1
    assert out[0]["role"] == "user"
    assert "안녕" in out[0]["content"] and "테이블 보여줘" in out[0]["content"] and "에러율" in out[0]["content"]


def test_preserves_alternation_and_assistant_turns():
    msgs = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "user", "content": "q3"},
        {"role": "assistant", "content": "a2"},
    ]
    out = ac._merge_consecutive_user_messages(msgs)
    assert [m["role"] for m in out] == ["user", "assistant", "user", "assistant"]
    assert out[2]["content"] == "q2\n\nq3"


def test_non_string_content_not_merged():
    # 이미지 array content 는 병합 대상 아님(안전).
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "img turn"}]},
        {"role": "user", "content": "다음 질문"},
    ]
    out = ac._merge_consecutive_user_messages(msgs)
    assert len(out) == 2  # 첫째가 string 아님 → 병합 안 함


def test_single_and_empty():
    assert ac._merge_consecutive_user_messages([]) == []
    one = [{"role": "user", "content": "only"}]
    assert ac._merge_consecutive_user_messages(one) == one
