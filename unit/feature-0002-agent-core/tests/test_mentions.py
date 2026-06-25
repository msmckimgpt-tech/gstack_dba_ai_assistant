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


# ─────────────────────────────────────────────────────────────────────────────
# feature-0009 gc-unread-badge: sql_mention_regex 가 parse_mentions 와 동일 경계를
# 인식하는지 — 사이드바 "안 읽은 @멘션" 카운트(SQL ~* / REGEXP)가 파서와 갈리면 배지 숫자가
# 틀린다. 같은 _CANONICAL_CASES 표로 SQL regex(파이썬 re, IGNORECASE=대소문자무시 미러)를 검증.
# ─────────────────────────────────────────────────────────────────────────────

import re

# 실제 계정 username 류 후보(예약어 'assistant' 는 제외 — parse_mentions 가 별도 토큰으로
# 빼므로 sql_mention_regex 의 literal 매칭과 의도적으로 다르다. unread-멘션은 실사용자 대상).
_REGEX_CANDIDATES = ["alice", "bob", "Alice", "BOB", "user_name-1.x", "user_name", "bob2"]


def _sql_re_match(username: str, text: str) -> bool:
    pat = mentions.sql_mention_regex(username)
    if pat is None:
        return False
    return re.search(pat, text or "", re.IGNORECASE) is not None


def test_sql_mention_regex_agrees_with_parser():
    """각 케이스에서 '이 username 을 멘션했나' 가 parse_mentions(정본)과 SQL regex 가 일치."""
    for text, _want_assistant, want_users in _CANONICAL_CASES:
        truth = {u.lower() for u in want_users}
        for cand in _REGEX_CANDIDATES:
            expect = cand.lower() in truth
            got = _sql_re_match(cand, text)
            assert got == expect, (
                f"text={text!r} cand={cand!r} expect={expect} got={got} "
                f"pat={mentions.sql_mention_regex(cand)!r}"
            )


def test_sql_mention_regex_none_for_empty():
    assert mentions.sql_mention_regex("") is None
    assert mentions.sql_mention_regex(None) is None


def test_sql_mention_regex_word_boundary_edges():
    # @bob 이 @bob2/@bob.kim(이름 charset 연속) 에 오매칭 안 함, a@bob(이메일류) 안 함.
    assert _sql_re_match("bob", "@bob hi") is True
    assert _sql_re_match("bob", "hey @bob please") is True
    assert _sql_re_match("bob", "@bob") is True            # 문자열 끝 경계
    assert _sql_re_match("bob", "@bob, ok") is True         # 구두점 종료
    assert _sql_re_match("bob", "(@bob)") is True           # 괄호 앞뒤 경계
    assert _sql_re_match("bob", "@bob2 nope") is False      # 이름 연속(숫자)
    assert _sql_re_match("bob", "@bob.kim") is False        # 이름 연속(.)
    assert _sql_re_match("bob", "a@bob") is False           # @ 앞 단어문자(이메일류)
    # 특수문자 포함 username escape (정규식 메타 안전).
    assert _sql_re_match("user_name-1.x", "@user_name-1.x ok") is True
    assert _sql_re_match("user_name", "@user_name-1.x ok") is False  # greedy charset 경계
