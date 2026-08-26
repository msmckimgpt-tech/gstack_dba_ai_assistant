"""feature-0043 AC-9 — 개인 머신 러너의 **무설치 계약**을 AST 로 잠근다.

사용자 결정(2026-08-26): "개인 머신에서 서비스를 작동시키는 환경적인 제한이 최소화되어야 합니다.
별도의 종속 패키지 설치없이…" — 러너가 `requests` 하나만 import 해도 그 제약이 깨지고,
"파일 하나 내려받아 실행" 이 "pip install 부터 하세요" 로 바뀐다.

**문자열 검사가 아니라 AST 로 본다.** 주석이나 docstring 에 `import requests` 라는 글자가 있어도
통과해야 하고(설명 목적), 실제 import 문은 하나도 없어야 한다 — 텍스트 스캔은 이 둘을 구분하지 못한다.
"""
from __future__ import annotations

import ast
import pathlib
import sys

RUNNER = pathlib.Path(__file__).resolve().parents[1] / "src" / "bridge_runner.py"


def _imported_roots(tree: ast.AST) -> set[str]:
    """소스가 실제로 import 하는 최상위 모듈 이름들."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` (level>0) 는 상대 import — 단일 파일 배포물에 있으면 안 된다.
            if node.level and node.level > 0:
                roots.add(f"<relative:{node.module or ''}>")
            elif node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_runner_exists():
    assert RUNNER.is_file(), f"러너 파일이 없다: {RUNNER}"


def test_runner_imports_stdlib_only():
    """AC-9 — 표준 라이브러리 밖 모듈을 import 하지 않는다."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    roots = _imported_roots(tree)

    # `sys.stdlib_module_names` 는 3.10+ 에서 제공되는 **실제 표준 라이브러리 명단**이다.
    # 직접 allowlist 를 손으로 적으면 새 import 가 추가될 때 명단을 같이 고치는 것을 잊어
    # 계약이 조용히 느슨해진다.
    stdlib = set(sys.stdlib_module_names)
    stdlib.add("__future__")

    external = sorted(r for r in roots if r not in stdlib)
    assert external == [], (
        f"러너가 외부 패키지를 import 한다: {external} — "
        "개인 머신 무설치 계약(AC-9)이 깨진다"
    )


def test_runner_does_not_import_mcp_sdk():
    """`mcp` SDK 의존은 특히 금지 — `pip install mcp` 가 곧 설치 요구다.

    (stdlib-only 테스트가 이미 잡지만, 이 feature 에서 가장 유혹적인 위반이라 이름으로 못박는다.)
    """
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    assert "mcp" not in _imported_roots(tree)


def test_runner_is_syntactically_valid_and_has_entrypoint():
    src = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "main" in names, "진입점 main() 이 없다"
    assert "__main__" in src, "직접 실행 진입점이 없다"


def test_runner_refuses_plaintext_http():
    """토큰이 평문으로 나가지 않게 — https 강제 로직이 존재한다."""
    src = RUNNER.read_text(encoding="utf-8")
    assert "https" in src and "평문" in src, "https 강제 경로가 보이지 않는다"
    assert "BRIDGE_VERIFY_TLS" not in src, (
        "TLS 검증을 끄는 스위치를 두면 안 된다 — Bearer 토큰이 MITM 에 노출된다"
    )
