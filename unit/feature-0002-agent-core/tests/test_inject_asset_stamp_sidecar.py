"""feature-0014 asset-stamp-cache-integrity: 빌드 스탬프 사이드카 계약.

런타임(`web/static_cache.py`)이 "요청 `?v=` == 내 빌드" 를 판정하려면 각 replica 가 자기
빌드 스탬프를 알아야 한다. 그 유일한 출처가 `inject_asset_stamp.py` 가 남기는
`<static>/.asset-stamp` 사이드카다 — **주입된 URL 의 스탬프와 반드시 같은 값**이어야 하며,
사이드카 자체가 해시 입력에 들어가 멱등성을 깨서도 안 된다(자기 참조).

이 계약이 깨지면 롤링 배포 창의 캐시 오염 차단이 통째로 무력화되므로(모든 요청이 불일치 →
상시 no-store, 또는 스탬프 부재 → 캐싱 상실) 여기서 고정한다.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "src" / "scripts" / "inject_asset_stamp.py"


def _load():
    spec = importlib.util.spec_from_file_location("inject_asset_stamp", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def static_tree(tmp_path: Path) -> Path:
    root = tmp_path / "static"
    (root / "graph").mkdir(parents=True)
    (root / "vendor").mkdir()
    (root / "admin.html").write_text(
        '<link rel="stylesheet" href="/static/styles.css?v=dev" />\n'
        '<script type="module" src="/static/admin.js?v=dev"></script>\n'
        '<script src="/static/vendor/g6.min.js?v=5.1.1"></script>\n',
        encoding="utf-8",
    )
    (root / "admin.js").write_text('import { x } from "./graph/graph.js?v=dev";\n', encoding="utf-8")
    (root / "graph" / "graph.js").write_text('export { y } from "./graph-core.js?v=dev";\n', encoding="utf-8")
    (root / "graph" / "graph-core.js").write_text("export const y = 1;\n", encoding="utf-8")
    (root / "styles.css").write_text("body{}\n", encoding="utf-8")
    (root / "vendor" / "g6.min.js").write_text("/*lib*/\n", encoding="utf-8")
    return root


def test_sidecar_written_and_matches_injected_stamp(static_tree: Path):
    mod = _load()
    assert mod.main.__module__  # 로드 확인
    rc = _run(mod, static_tree)
    assert rc == 0

    sidecar = (static_tree / mod.STAMP_SIDECAR).read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]{12}", sidecar), sidecar

    # 주입된 URL 스탬프와 **동일 값** — 다르면 런타임이 자기 자산을 전부 불일치로 판정한다.
    html = (static_tree / "admin.html").read_text(encoding="utf-8")
    assert f"styles.css?v={sidecar}" in html
    assert f"admin.js?v={sidecar}" in html
    js = (static_tree / "admin.js").read_text(encoding="utf-8")
    assert f"graph/graph.js?v={sidecar}" in js
    # vendor pin 은 보존(별개 버전 축).
    assert "vendor/g6.min.js?v=5.1.1" in html


def test_idempotent_stamp_across_reruns(static_tree: Path):
    """사이드카가 해시 입력에 섞이면 재실행마다 값이 바뀐다 — 그러면 롤아웃마다 전 캐시가 깨진다."""
    mod = _load()
    _run(mod, static_tree)
    first = (static_tree / mod.STAMP_SIDECAR).read_text(encoding="utf-8").strip()
    _run(mod, static_tree)
    second = (static_tree / mod.STAMP_SIDECAR).read_text(encoding="utf-8").strip()
    assert first == second, (first, second)


def test_stamp_changes_when_content_changes(static_tree: Path):
    mod = _load()
    _run(mod, static_tree)
    before = (static_tree / mod.STAMP_SIDECAR).read_text(encoding="utf-8").strip()
    (static_tree / "graph" / "graph-core.js").write_text("export const y = 2;\n", encoding="utf-8")
    _run(mod, static_tree)
    after = (static_tree / mod.STAMP_SIDECAR).read_text(encoding="utf-8").strip()
    assert before != after


def test_check_mode_does_not_write_sidecar(static_tree: Path):
    mod = _load()
    _run(mod, static_tree, check=True)
    assert not (static_tree / mod.STAMP_SIDECAR).exists()


def test_no_placeholder_left(static_tree: Path):
    """deploy-web.sh asset_stamp_verify 의 하드 차단 조건과 동일 — placeholder 잔존 0."""
    mod = _load()
    _run(mod, static_tree)
    for p in static_tree.rglob("*"):
        if p.is_file() and p.suffix in (".html", ".js") and "vendor" not in p.parts:
            assert "?v=dev" not in p.read_text(encoding="utf-8"), p


def _run(mod, root: Path, check: bool = False) -> int:
    import sys

    argv = ["inject_asset_stamp.py", "--root", str(root)] + (["--check"] if check else [])
    old = sys.argv
    sys.argv = argv
    try:
        return mod.main()
    finally:
        sys.argv = old
