"""feature-0023 conversation-quality-controls — MCP 클라이언트 경로 조립 안전성.

`conversation_mcp_server.py` 는 import 시점에 `mcp` SDK 와 필수 env(BASE_URL·TOKEN)를 요구해
bare import 가 안 된다(fail-loud 설계). 그래서 `ast` 로 대상 helper 만 추출해 검증한다
(feature-0003 `test_perm_self_scope.py` 와 동일 관용구).

검증 대상 — `_path_seg` (§18.8 보안 리뷰에서 적발·수정된 결함의 회귀 게이트):
`urllib.parse.quote` 의 기본 `safe='/'` 는 슬래시를 통과시킨다. tool 인자 `conversation_id` 는
이 MCP 서버를 구동하는 LLM 이 채우고 그 입력에 신뢰할 수 없는 대화 내용이 섞일 수 있으므로
(prompt injection), 세그먼트가 경로를 벗어나면 클라이언트가 의도하지 않은 엔드포인트를 때린다.
서버측 인증·scope·절대 denylist 가 최종 방어선이지만, 클라이언트도 의도한 경로만 만들어야 한다.
"""
from __future__ import annotations

import ast
import os
import sys
import urllib.parse

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src", "conversation_mcp_server.py")
_TARGET = "_path_seg"


def _load_path_seg():
    """`_path_seg` 함수만 ast 로 추출해 격리 네임스페이스에서 실행·반환."""
    tree = ast.parse(open(_SRC, encoding="utf-8").read())
    fn = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == _TARGET),
        None,
    )
    assert fn is not None, f"{_TARGET} 를 {_SRC} 에서 찾지 못함"
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict = {"urllib": urllib}
    exec(compile(module, _SRC, "exec"), ns)  # noqa: S102 - 자기 소스 추출 실행
    return ns[_TARGET]


path_seg = _load_path_seg()


@pytest.mark.parametrize("raw", [
    "x/../../api/admin/openapi.json",
    "../../api/admin/openapi.json",
    "a/b",
    "/api/admin/accounts",
])
def test_path_traversal_is_encoded(raw):
    """슬래시가 그대로 남으면 경로를 벗어난다 — 반드시 %2F 로 인코딩."""
    out = path_seg(raw)
    assert "/" not in out, f"슬래시가 인코딩되지 않음: {raw!r} -> {out!r}"
    assert "%2F" in out


def test_query_and_fragment_are_encoded():
    """`?`·`#` 가 살아 있으면 세그먼트 밖으로 새어 쿼리/프래그먼트가 된다."""
    out = path_seg("cid?admin=1#frag")
    for ch in ("?", "#"):
        assert ch not in out, f"{ch!r} 가 인코딩되지 않음: {out!r}"


def test_normal_conversation_id_round_trips():
    """정상 대화 id(영숫자·하이픈)는 변형 없이 그대로 — 기존 호출 무회귀."""
    cid = "20260728-3f2a9b1c"
    assert path_seg(cid) == cid


def test_none_and_empty_are_safe():
    assert path_seg("") == ""
    assert path_seg(None) == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
