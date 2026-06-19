"""mentions canonical 파서 계약 테스트 — feature-0009-group-conversation (S3).

_CANONICAL_CASES 는 BE(modules/mentions.py)와 FE(static/mentions.js)가 **반드시 동일하게**
처리해야 하는 케이스표다. FE 미러는 verify_mentions.mjs 가 같은 표로 검증한다(node). 문법을
바꾸면 BE·FE·본 표를 함께 고친다(divergence 방지, CSO/eng 리뷰 지적).
"""
from __future__ import annotations

import modules.mentions as mentions

# (text, mentions_assistant, mentioned_usernames)
_CANONICAL_CASES = [
    ("", False, []),
    ("hello world", False, []),
    ("@assistant hi", True, []),
    ("hey @assistant please", True, []),
    ("@Assistant caps insensitive", True, []),          # assistant 예약어 대소문자 무시
    ("ping @alice and @bob", False, ["alice", "bob"]),
    ("@alice @assistant @alice again", True, ["alice"]),  # dedup + assistant 제외
    ("send mail a@b.com no mention", False, []),          # 이메일 오매칭 방지(@b 앞 'a' 단어문자)
    ("ask foo@assistant.com is email", False, []),        # @ 앞 단어문자 → 멘션 아님
    ("안녕@assistant 질문", True, []),                     # 한글 뒤 @ (ASCII lookbehind)
    ("(@assistant) parenthesized", True, []),             # 구두점 뒤 @ → 멘션
    ("@bob, hi there", False, ["bob"]),                   # 이름 뒤 구두점 종료
    ("@user_name-1.x ok", False, ["user_name-1.x"]),      # 전체 charset
    ("no@space here", False, []),                          # @ 앞 단어문자 → 멘션 아님
]


def test_canonical_cases_assistant_and_usernames():
    for text, want_assistant, want_users in _CANONICAL_CASES:
        got = mentions.parse_mentions(text)
        assert got["mentions_assistant"] == want_assistant, f"assistant mismatch: {text!r} -> {got}"
        assert got["mentioned_usernames"] == want_users, f"usernames mismatch: {text!r} -> {got}"


def test_message_invokes_assistant_convenience():
    assert mentions.message_invokes_assistant("@assistant go") is True
    assert mentions.message_invokes_assistant("just @bob chatting") is False
    assert mentions.message_invokes_assistant("") is False


def test_tokens_carry_positions():
    got = mentions.parse_mentions("hi @assistant and @bob")
    names = [t["name"] for t in got["tokens"]]
    assert names == ["assistant", "bob"]
    # span 이 원문 @ 위치를 가리킨다.
    for t in got["tokens"]:
        assert got_substr_at(("hi @assistant and @bob"), t) == "@" + t["name"]


def got_substr_at(text: str, token: dict) -> str:
    return text[token["start"]:token["end"]]
