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
import re


def _sanitize_session_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value or "")
    if cleaned:
        return cleaned[:64]
    return ""


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
