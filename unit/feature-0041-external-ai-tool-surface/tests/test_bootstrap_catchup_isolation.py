"""feature-0041 — 부트스트랩 catchup 체인 보호 (배포 전 발견 · LRN 반복 결함).

`_ensure_oauth_client_schema` 는 `_ensure_seed_catchup`(운영 재기동 fast path) **중간**에서
호출되고, 그 함수는 항목마다 try 로 감싸지 않는다. 여기서 예외가 새면 뒤따르는 catchup 항목
(gdrive 토큰 · 아바타 컬럼 · 첨부 버전 · DB allowlist 규칙 · **audit events** · **audit chain**)이
전부 조용히 skip 된다.

신규 테이블 부재는 이 feature 의 엔드포인트만 fail-closed 로 막지만, catchup 중단은 **무관한
서브시스템을 조용히 망가뜨린다** — 그래서 이 함수는 어떤 실패도 밖으로 내보내지 않는다.
"""
from __future__ import annotations

import ast
import os
import sys

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..",
                    "feature-0003-agent-web-ui", "src", "routers", "_bootstrap_schema.py")


def _func(name: str) -> ast.FunctionDef:
    with open(_SRC, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} 없음")


def test_cursor_acquisition_is_inside_try():
    """★ `cur = conn.cursor()` 가 try 밖이면 커서 획득 실패가 호출측으로 전파된다
    (LEARNINGS 의 resource-acquire-outside-try 반복 결함)."""
    fn = _func("_ensure_oauth_client_schema")
    # 함수 본문의 top-level 문 중 docstring 이후 첫 실행문이 Try 여야 한다
    body = [n for n in fn.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert body, "본문이 비었다"
    first = body[0]
    assert isinstance(first, ast.Assign), "cur = None 초기화가 사라졌다"
    assert isinstance(body[1], ast.Try), "커서 획득이 try 밖에 있다 — catchup 체인이 끊긴다"
    # cursor() 호출이 그 Try 안에 있는지
    calls = [n for n in ast.walk(body[1])
             if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "cursor"]
    assert calls, "conn.cursor() 가 try 안에 없다"


def test_function_swallows_all_exceptions():
    """이 함수는 어떤 예외도 밖으로 내보내지 않아야 한다 — bare `except Exception` 핸들러 존재."""
    fn = _func("_ensure_oauth_client_schema")
    outer = [n for n in fn.body if isinstance(n, ast.Try)]
    assert outer, "최상위 try 없음"
    handlers = outer[0].handlers
    assert handlers, "최상위 try 에 except 가 없다 — 예외가 catchup 으로 전파된다"
    assert any(getattr(h.type, "id", "") == "Exception" for h in handlers)


def test_cursor_close_is_guarded():
    """`cur` 이 None 일 수 있으므로 finally 의 close 도 방어돼야 한다."""
    fn = _func("_ensure_oauth_client_schema")
    outer = [n for n in fn.body if isinstance(n, ast.Try)][0]
    assert outer.finalbody, "finally 없음"
    src = ast.dump(ast.Module(body=outer.finalbody, type_ignores=[]))
    assert "Compare" in src or "IsNot" in src, "finally 가 cur is not None 을 확인하지 않는다"


@pytest.mark.parametrize("later_item", [
    "_ensure_web_gdrive_tokens_schema",
    "_ensure_avatar_icon_schema",
    "_ensure_web_audit_events_schema",
    "_ensure_web_audit_chain_schema",
])
def test_later_catchup_items_still_follow_us(later_item):
    """blast radius 고정 — 이 항목들이 우리 뒤에 있다는 사실이 위 방어의 근거다.
    순서가 바뀌어 우리가 마지막이 되면 방어의 필요성이 줄지만, 그때도 방어는 무해하다."""
    with open(_SRC, encoding="utf-8") as fh:
        src = fh.read()
    catchup = src[src.index("def _ensure_seed_catchup"):]
    ours = catchup.index("_ensure_oauth_client_schema(conn)")
    theirs = catchup.index(f"{later_item}(conn)")
    assert theirs > ours, f"{later_item} 가 더 이상 우리 뒤에 있지 않다 — 주석 근거 갱신 필요"
