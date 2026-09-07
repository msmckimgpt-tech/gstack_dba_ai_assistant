"""세션 쿠키가 **서버 정책만큼 오래 산다** (사용자 제보 2026-09-07).

## 무엇이 잘못돼 있었나 — 실측으로 확정

`_set_session_cookie` 에 `max_age`/`expires` 가 없었다. 즉 **세션 쿠키**였고, 브라우저는
「이 브라우징 세션이 끝나면 버림」으로 다룬다.

- 웹에서는 안 보였다 — Chrome·Edge 가 재시작 시 세션 복원으로 가려 준다.
- 데스크톱 앱 창(WebView2)에는 그 복원이 **없다.** 프로세스가 끝나면 쿠키도 끝난다.

실측(2026-09-07, 사용자 프로필):

    영구 쿠키 저장소       → 쿠키 **0건**
    새 창에서 상태 조회    → `{"logged_in": false}`
    연결 상태 칩           → `ai-conn hidden`

사용자에게는 *"설치 후 로그인을 진행했습니다"* 뒤 다음 실행에서 조용히 로그아웃된 상태로
나타났다. 게다가 **이미 그려진 화면은 남고** 칩·잠금 안내만 사라져 고장으로 보이지 않았다.

## 이 파일이 잠그는 것

1. 쿠키에 **수명이 있다** — 없으면 앱 창은 매 실행 로그아웃이다.
2. 그 수명이 서버의 슬라이딩 창(`AUTH_SESSION_DAYS`)보다 **짧지 않다.** 짧으면 쿠키가
   제한 요인이 되어, 서버가 만료를 계속 미는데도 사용자는 그 날 로그아웃된다 —
   feature-0043 TASK-20260828T150000 이 서버 쪽에서 고친 증상을 쿠키 쪽에서 되살리는 꼴.
3. 보안 속성(`HttpOnly`·`SameSite`·https 에서 `Secure`)은 **그대로**다. 수명을 주는 것이
   다른 방어를 무르게 하는 변경이 되면 안 된다.
"""

from __future__ import annotations

import re

import pytest
from fastapi import Response
from starlette.datastructures import Headers
from starlette.requests import Request

import app as appmod
import web_context as ctx


def _request(scheme: str = "https") -> Request:
    return Request({
        "type": "http", "http_version": "1.1", "method": "GET", "path": "/",
        "raw_path": b"/", "query_string": b"", "headers": Headers({}).raw,
        "scheme": scheme, "server": ("svc.example", 443), "client": ("1.2.3.4", 1),
    })


def _set(scheme: str = "https") -> str:
    resp = Response()
    appmod._set_session_cookie(resp, _request(scheme), "sid-abc")
    raw = [v.decode() for k, v in resp.raw_headers if k == b"set-cookie"]
    assert raw, "Set-Cookie 가 없다"
    return raw[0]


# ── 1. 수명이 있다 ────────────────────────────────────────────────────────────────

def test_the_cookie_survives_closing_the_app():
    """**이 단정이 제보된 결함을 잡는다** — 수명이 없으면 앱 창은 매 실행 로그아웃이다."""
    header = _set()
    assert "Max-Age=" in header, (
        "세션 쿠키다 — 앱 창(WebView2)에는 세션 복원이 없어 실행할 때마다 로그아웃된다")


def test_the_cookie_is_not_the_limiting_factor():
    """서버가 만료를 계속 미는데 쿠키가 먼저 죽으면, 매일 쓰는 사용자가 그 날 로그아웃된다."""
    m = re.search(r"Max-Age=(\d+)", _set())
    assert m
    seconds = int(m.group(1))
    sliding = ctx.AUTH_SESSION_DAYS * 24 * 60 * 60
    assert seconds >= sliding, (
        f"쿠키 수명({seconds}s)이 서버의 슬라이딩 창({sliding}s)보다 짧다 — "
        "쿠키가 제한 요인이 된다")


def test_the_cookie_matches_the_absolute_cap():
    """권한은 서버가 정한다. 쿠키는 그 상한까지 운반만 하고, 그 뒤는 서버가 거절한다."""
    m = re.search(r"Max-Age=(\d+)", _set())
    assert int(m.group(1)) == ctx.AUTH_SESSION_MAX_DAYS * 24 * 60 * 60


# ── 2. 다른 방어는 그대로다 ───────────────────────────────────────────────────────

def test_defenses_are_not_loosened():
    """⚠ 수명을 주는 변경이 다른 방어를 무르게 하면 안 된다."""
    header = _set("https")
    assert "HttpOnly" in header, "스크립트가 세션을 읽을 수 있게 됐다"
    assert "samesite=lax" in header.lower(), "교차 사이트 전송이 열렸다"
    assert "Secure" in header, "https 인데 평문으로도 나간다"


def test_plain_http_does_not_claim_secure():
    """개발용 평문 접속에서 `Secure` 를 붙이면 쿠키가 아예 전달되지 않는다."""
    assert "Secure" not in _set("http")


# ── 3. 로그아웃은 여전히 지운다 ───────────────────────────────────────────────────

def test_logout_still_clears_it():
    """대조군 — 수명을 준 뒤에도 로그아웃이 쿠키를 지우는지."""
    resp = Response()
    appmod._clear_session_cookie(resp, _request())
    raw = [v.decode() for k, v in resp.raw_headers if k == b"set-cookie"]
    assert raw and ("Max-Age=0" in raw[0] or "expires=Thu, 01 Jan 1970" in raw[0].lower()), raw
