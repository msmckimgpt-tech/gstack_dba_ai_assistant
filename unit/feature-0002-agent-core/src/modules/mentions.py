"""Mention parsing — feature-0009-group-conversation (S3 Chat+Mention).

그룹 대화 멤버 메시지의 멘션 토큰을 파싱하는 **canonical** 파서. 동일 문법이 프론트엔드
(`static/mentions.js`) 와 1:1 로 미러링되어야 한다(CSO/eng 리뷰: FE↔BE divergence 위험 —
프론트가 @assistant 칩을 그려도 백엔드가 enqueue 판정을 다르게 하면 "응답 안 함" 또는
"의도치 않은 호출"). 두 구현은 `_CANONICAL_CASES`(test_mentions.py) 로 계약 고정된다.

문법(canonical):
  - 멘션 = 단어 경계(문자열 시작 또는 공백/구두점 뒤) 의 `@` + 이름.
    이름 charset = [A-Za-z0-9._-]+ (전형 username). 이메일(`a@b.com`) 오매칭 방지를 위해
    `@` 앞이 단어 문자(\\w)면 멘션 아님.
  - `@assistant`(대소문자 무시) = AI 호출 토큰(예약어). 이 토큰이 있으면 LLM 응답 트리거.
  - 그 외 `@name` = 사용자 멘션(주의 환기, LLM 미호출). username 검증/존재 확인은 호출자
    책임(본 파서는 토큰만 추출).

사용처:
  - app.py 메시지 전송: mentions_assistant 여야 ask_jobs enqueue(actor=발신자). 아니면
    사람 채팅으로 저장만(LLM 미호출).
  - agent_core 히스토리: 사용자 메시지에 발신자 라벨 부여 시 멘션 표시 활용(S3 후속).
"""

from __future__ import annotations

import re
from typing import Any

# AI 호출 예약 멘션 이름(소문자 비교).
ASSISTANT_MENTION = "assistant"

# 단어 경계 @mention: 앞이 문자열 시작 또는 비-(ASCII 단어/@) 문자(이메일 a@b 오매칭 방지),
# 이름은 [A-Za-z0-9._-]+. 캡처그룹 1 = 이름.
# ★lookbehind 는 ASCII-explicit([A-Za-z0-9_@]) — Python \w(유니코드) ↔ JS \w(ASCII) 차이로
#   FE↔BE 가 갈리지 않게 고정. 덕분에 "안녕@assistant"(한글 뒤 @) 도 양쪽 동일하게 멘션 인식.
_MENTION_RE = re.compile(r"(?<![A-Za-z0-9_@])@([A-Za-z0-9._-]+)")


def parse_mentions(text: str | None) -> dict[str, Any]:
    """메시지 텍스트에서 멘션을 추출한다.

    Returns dict:
      - mentions_assistant (bool): `@assistant` 포함 여부(LLM 호출 트리거).
      - mentioned_usernames (list[str]): assistant 제외, 등장 순서 dedup 된 사용자 멘션 이름.
      - tokens (list[dict]): [{name, start, end}] — 원문 위치(렌더/하이라이트용).
    """
    if not text:
        return {"mentions_assistant": False, "mentioned_usernames": [], "tokens": []}
    tokens: list[dict[str, Any]] = []
    mentions_assistant = False
    seen: set[str] = set()
    usernames: list[str] = []
    for m in _MENTION_RE.finditer(text):
        name = m.group(1)
        tokens.append({"name": name, "start": m.start(), "end": m.end()})
        if name.lower() == ASSISTANT_MENTION:
            mentions_assistant = True
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            usernames.append(name)
    return {
        "mentions_assistant": mentions_assistant,
        "mentioned_usernames": usernames,
        "tokens": tokens,
    }


def message_invokes_assistant(text: str | None) -> bool:
    """편의 함수: 이 메시지가 LLM 응답을 트리거하는지(=@assistant 멘션 포함)."""
    return parse_mentions(text)["mentions_assistant"]


# ─────────────────────────────────────────────────────────────────────────────
# feature-0009 gc-unread-badge: 사이드바 "안 읽은 @멘션" 카운트용 SQL regex 미러.
# parse_mentions 의 단어경계 문법을 SQL regex(PG POSIX ERE `~*` / MySQL ICU `REGEXP`)로
# 옮긴 것 — 메세지 본문에 `@<username>` 멘션이 있는지를 SQL 집계로 세기 위함. lookbehind
# 미지원(POSIX/ICU)이라 `(?<![A-Za-z0-9_@])` 를 `(^|[^A-Za-z0-9_@])` 로, 이름 뒤 charset
# 경계를 `([^A-Za-z0-9._-]|$)` 로 옮긴다. 대소문자 무시는 호출측(PG `~*` / MySQL LOWER()).
# 본 모듈에 두어 parse_mentions(파서)·static/mentions.js(FE)·SQL 카운트가 한 문법을 공유한다.
# ─────────────────────────────────────────────────────────────────────────────

# POSIX ERE / ICU 공통 메타문자 — username 에 섞여 있으면 escape. 이름 charset 은 보통
# [A-Za-z0-9._-] 라 실질적으로 `.`/`-` 만 해당하나, 방어적으로 전체 집합을 escape.
_SQL_RE_METACHARS = frozenset(r".^$*+?()[]{}|\-/")


def sql_mention_regex(username: str | None) -> str | None:
    """`@<username>` word-boundary 를 매칭하는 SQL regex 문자열. username 없으면 None.

    예) username="bob" → r"(^|[^A-Za-z0-9_@])@bob([^A-Za-z0-9._-]|$)".
    `@bob` 이 `@bob2`/`@bob.kim`(이름 charset 연속) 에는 매칭되지 않고, `a@bob`(이메일류)
    에도 매칭되지 않는다 — parse_mentions 와 동일 경계. 대소문자 무시는 호출측이 담당한다.
    """
    if not username:
        return None
    esc = "".join(("\\" + ch) if ch in _SQL_RE_METACHARS else ch for ch in username)
    return r"(^|[^A-Za-z0-9_@])@" + esc + r"([^A-Za-z0-9._-]|$)"
