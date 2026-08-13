"""feature-0041 — 배포 이미지 import 가능성 게이트 (라이브 실패로 발견된 사각).

## 왜 이 파일이 있는가

최초 구현은 서버측 모듈을 feature-local `unit/feature-0041-.../src` 에 두고 라우터가
`sys.path.insert` 로 그 경로를 주입했다. 단위 테스트는 **repo 레이아웃**에서 돌기 때문에 전부
통과했지만, 라이브 배포에서 web-a 가 기동 즉시 죽었다:

    File "/app/web/routers/ai_tools.py", line 47, in <module>
        import oauth_store as _store
    ModuleNotFoundError: No module named 'oauth_store'

agent 이미지 Dockerfile 은 `feature-0002/src`·`shared`·`feature-0003/src` 만 COPY 한다 —
feature-0041 의 `src/` 는 이미지 안에 존재하지 않는다. 즉 **"repo 에서 import 되는 것" 과
"배포 이미지에서 import 되는 것" 이 다른데, 그 차이를 재는 테스트가 없었다.**

이 파일이 그 차이를 잰다. 라우터가 top-level 에서 import 하는 1st-party 모듈이 전부
Dockerfile 이 COPY 하는 경로 안에 실재하는지 정적으로 확인한다(컨테이너 없이).
"""
from __future__ import annotations

import ast
import os
import re

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_DOCKERFILE = os.path.join(_REPO, "unit", "feature-0002-agent-core", "src", "Dockerfile")
_WEB_SRC = os.path.join(_REPO, "unit", "feature-0003-agent-web-ui", "src")
_ROUTERS = os.path.join(_WEB_SRC, "routers")

# 본 feature 가 추가한 라우터. 이 목록이 늘면 여기에 추가한다.
_OUR_ROUTERS = ("ai_tools.py", "oauth_as.py")
# 라우터가 쓰는 feature-0041 서버측 모듈.
_OUR_MODULES = ("oauth_store", "session_guard", "tool_authz", "tool_ledger")


def _dockerfile_copy_targets() -> list[str]:
    with open(_DOCKERFILE, encoding="utf-8") as fh:
        body = fh.read()
    return [m.group(1) for m in re.finditer(r"^COPY\s+(\S+)\s+\S+", body, re.M)]


def test_server_side_modules_live_in_a_copied_directory():
    """★ 서버측 모듈은 Dockerfile 이 COPY 하는 트리 안에 있어야 한다.
    feature-local src 에 두면 repo 테스트는 통과하고 **라이브만 죽는다**."""
    copied = _dockerfile_copy_targets()
    assert "unit/feature-0003-agent-web-ui/src" in copied, \
        "web src COPY 가 사라졌다 — 이 게이트의 전제가 무너진다"
    for mod in _OUR_MODULES:
        path = os.path.join(_WEB_SRC, f"{mod}.py")
        assert os.path.isfile(path), (
            f"{mod}.py 가 web src 밖에 있다 — 배포 이미지에 포함되지 않아 기동이 죽는다")


def test_routers_do_not_inject_syspath_to_uncopied_paths():
    """★ `sys.path.insert` 로 이미지에 없는 경로를 가리키면 라이브에서만 실패한다.
    로컬에서 통과하는 우회로를 구조적으로 막는다."""
    for name in _OUR_ROUTERS:
        with open(os.path.join(_ROUTERS, name), encoding="utf-8") as fh:
            src = fh.read()
        assert "sys.path.insert" not in src, (
            f"{name} 이 sys.path 를 주입한다 — 배포 이미지 레이아웃과 갈릴 수 있다")
        assert "feature-0041-external-ai-tool-surface" not in src, (
            f"{name} 이 feature-local 경로를 참조한다 — 그 디렉터리는 이미지에 없다")


@pytest.mark.parametrize("router", _OUR_ROUTERS)
def test_router_toplevel_imports_resolve_in_image_layout(router):
    """라우터가 top-level 에서 import 하는 1st-party 모듈이 `/app/web` 또는 `/app` 에
    해당하는 repo 경로에 실재하는지 확인한다(표준 라이브러리·서드파티는 제외)."""
    path = os.path.join(_ROUTERS, router)
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    # 이미지의 sys.path 에 해당하는 repo 디렉터리: /app/web, /app(=agent-core src·shared 루트)
    agent_src = os.path.join(_REPO, "unit", "feature-0002-agent-core", "src")
    search = [_WEB_SRC, agent_src, _REPO]

    third_party = {"fastapi", "starlette", "pydantic", "mcp", "psycopg", "mysql"}
    for node in tree.body:
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in third_party:
                continue
            try:                                    # 표준 라이브러리면 통과
                __import__(top)
                continue
            except Exception:
                pass
            found = any(
                os.path.isfile(os.path.join(base, f"{top}.py"))
                or os.path.isdir(os.path.join(base, top))
                for base in search)
            assert found, (
                f"{router} 의 `import {top}` 이 이미지 레이아웃에서 해석되지 않는다 "
                f"— COPY 되는 트리에 두거나 import 를 바꿔야 한다")


def test_mcp_adapter_stays_feature_local():
    """반대 방향 — MCP 어댑터는 **클라이언트 측**에서 돌므로 이미지에 들어가면 안 된다
    (들어가도 무해하지만, 거주지가 곧 실행 위치라는 신호를 흐린다)."""
    adapter = os.path.join(_HERE, "..", "src", "external_tool_mcp_server.py")
    assert os.path.isfile(adapter), "MCP 어댑터는 feature-local src 에 남아 있어야 한다"
    assert not os.path.isfile(os.path.join(_WEB_SRC, "external_tool_mcp_server.py"))


# ── 컨테이너에서 도는 스크립트의 서드파티 의존 ────────────────────────────────

def test_container_entrypoint_third_party_imports_are_installed(codex_p1=True):
    """★ COPY 만 검사하면 **파일은 있는데 기동만 죽는** 사각이 남는다(2026-08-13 실증).

    compose 가 agent 이미지로 띄우는 스크립트의 최상위 서드파티 import 는 전부 그 이미지의
    requirements 에 있어야 한다. 배포는 `ext-tool-mcp 상태=none` 이라는 모호한 메시지만 남기고
    워커군 전체를 롤백시켰다 — 실제 원인은 `ModuleNotFoundError: No module named 'mcp'` 였다.
    """
    import ast
    import sys as _sys

    def _slurp(*parts: str) -> str:
        with open(os.path.join(_REPO, *parts), encoding="utf-8") as fh:
            return fh.read()

    # ⚠ 파일 전체를 부분문자열로 검사하면 **주석에 적힌 이름**이 통과시킨다 —
    # 이 테스트를 처음 그렇게 썼다가 뮤테이션(`mcp` 줄 삭제)이 살아남는 것을 보고 고쳤다.
    # 실제 requirement 줄만 파싱해 배포명 집합을 만든다.
    raw = _slurp("unit", "feature-0002-agent-core", "src", "requirements.txt")
    req = set()
    for line in raw.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[\[<>=!~;\s]", line, 1)[0].strip().lower()
        if name:
            req.add(name.replace("_", "-"))
    src = _slurp("unit", "feature-0041-external-ai-tool-surface", "src",
                 "external_tool_mcp_http.py")
    tree = ast.parse(src)

    tops = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tops.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            tops.add(node.module.split(".")[0])

    stdlib = set(getattr(_sys, "stdlib_module_names", ()))
    # import 이름 ≠ 배포 이름인 경우만 여기에 적는다(현재는 없음 — 늘면 추가).
    _DIST = {}
    missing = [m for m in sorted(tops)
               if m not in stdlib and m != "__future__"
               and _DIST.get(m, m).replace("_", "-") not in req]
    assert not missing, (
        f"컨테이너 진입점이 import 하지만 requirements 에 없는 패키지: {missing} — "
        "이미지는 빌드되고 COPY 도 되지만 기동만 죽는다"
    )
