"""web_context — app.py 에서 추출한 leaf helper (feature-0012 P5b Final).

P5b 의 목표는 28K-line app.py 모놀리스를 도메인 router + 공유 컨텍스트 모듈로 분할하는 것이다.
본 모듈은 그 첫 공유-컨텍스트 조각으로, **app-internal 의존이 전혀 없는 순수 leaf helper** 만
담는다.

INVARIANT: 본 모듈은 `from app import` 를 **절대 포함하지 않는다**(단방향 app → web_context
edge 만 유지 → 순환 import 불가). stdlib-only 로 유지한다. app.py 는 본 심볼들을 다시
`from web_context import ...` 로 재가져와 모듈 전역에 rebind 한다 — 따라서 app.py 내 기존
호출부(bare name)와 테스트의 `monkeypatch.setattr(app, ...)` 가 모두 그대로 동작한다(behavior-neutral).
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import sys

from fastapi import Request

# app.py 의 AGENT_MODE(L82)와 동일 표현식의 env-mirror — web_context 를 app-free 로 유지하기
# 위함(_parse_trusted_proxies 의 prod/staging fail-loud 분기가 참조). 둘 다 import 시점에 같은
# 환경변수를 읽어 동일 값을 갖는다(파생 상수, 결정적). app 의 startup-validation 블록은 app 의
# AGENT_MODE 를 계속 사용한다.
AGENT_MODE = os.getenv("AGENT_MODE", "").strip().lower()


def _sanitize_session_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value or "")
    if cleaned:
        return cleaned[:64]
    return ""


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


_TrustedNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_trusted_proxies(raw: str) -> tuple[_TrustedNetwork, ...]:
    items: list[_TrustedNetwork] = []
    bad: list[str] = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            items.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            bad.append(token)
    if bad:
        if AGENT_MODE in {"prod", "staging"}:
            raise RuntimeError(
                f"WEB_TRUSTED_PROXIES: invalid CIDR(s) in {AGENT_MODE}: {bad}"
            )
        print(
            f"[startup] WARNING: WEB_TRUSTED_PROXIES contains invalid CIDR(s) (skipped): {bad}",
            file=sys.stderr,
        )
    return tuple(items)


WEB_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("WEB_TRUSTED_PROXIES", ""))


def _is_trusted_proxy(host: str) -> bool:
    if not host or not WEB_TRUSTED_PROXIES:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in network for network in WEB_TRUSTED_PROXIES)


def _get_client_ip(request: Request) -> str:
    direct_ip = (request.client.host if request.client else "") or ""
    if direct_ip and _is_trusted_proxy(direct_ip):
        forwarded = request.headers.get("x-forwarded-for", "").strip()
        if forwarded:
            first = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(first)
            except ValueError:
                return direct_ip
            return first
    return direct_ip
