"""앱 관리 CLI의 발견·선택·갱신을 실제 파일과 기존 브리지 계약으로 검증한다."""
import ast
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "feature-0043-external-llm-bridge" / "src"))
from client import core, discovery
from agent import discovery as runner


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    root = tmp_path / "OpenAI" / "Codex" / "bin"
    root.mkdir(parents=True)
    for module in (core, runner):
        monkeypatch.setattr(module, "_desktop_codex_root", lambda: str(root))
    return root


def install(root, digest="a" * 16, when=10):
    folder = root / digest
    folder.mkdir(exist_ok=True)
    exe = folder / "codex.exe"
    exe.write_bytes(b"test executable")
    os.utime(folder, (when, when))
    return str(exe)


@pytest.mark.parametrize("module", [core, runner])
def test_newest_complete_desktop_payload_is_used(desktop, module):
    old = install(desktop)
    fresh = install(desktop, "b" * 16, 20)
    (desktop / ("c" * 16)).mkdir()  # 앱 갱신 중 아직 실행 파일이 없는 폴더
    install(desktop, "not-a-payload", 99)
    assert module._desktop_codex_path() == fresh
    Path(fresh).unlink()
    assert module._desktop_codex_path() == old


@pytest.mark.parametrize("module", [core, runner])
def test_symlinks_and_non_executables_are_not_discovered(desktop, tmp_path, module):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "codex.exe").write_bytes(b"unrelated")
    (desktop / ("a" * 16)).symlink_to(outside, target_is_directory=True)
    folder = desktop / ("b" * 16)
    folder.mkdir()
    (folder / "codex.exe").symlink_to(outside / "codex.exe")
    (folder / "codex.cmd").write_text("echo wrong")
    assert module._desktop_codex_path() is None
    (folder / "codex.exe").unlink()
    (folder / "codex.exe").mkdir()
    assert module._desktop_codex_path() is None


def test_native_cli_and_desktop_remain_distinct_and_duplicates_collapse(desktop, monkeypatch):
    exe = install(desktop)
    monkeypatch.setattr(core, "which_runtime", lambda name: "C:/CLI/codex.exe")
    rows = core.native_runtimes("codex")
    assert [row.label for row in rows] == ["codex", "codex (ChatGPT 데스크톱)"]
    assert discovery.state_json(rows[1])["source"] == "chatgpt-desktop"
    assert rows[1].argv("exec", "literal & argument") == [exe, "exec", "literal & argument"]
    monkeypatch.setattr(core, "which_runtime", lambda name: exe)
    assert len(core.native_runtimes("codex")) == 1


def test_desktop_update_invalidates_location_cache_and_rechecks_answers(desktop, tmp_path, monkeypatch):
    old = install(desktop)
    monkeypatch.setattr(core, "which_runtime", lambda name: core._desktop_codex_path() if name == "codex" else None)
    monkeypatch.setattr(core, "_is_windows", lambda: False)  # 이 테스트에서는 WSL 열거를 하지 않는다.
    checked = []
    monkeypatch.setattr(core, "probe_runtime", lambda name, **kw: core.RuntimeState(name, logged_in=True, **kw))
    def verify(st):
        checked.append(st.path)
        st.answers = True
        return st
    monkeypatch.setattr(core, "verify_answers", verify)
    cache = discovery.DiscoveryCache(tmp_path / "dqa")
    cache.discover()
    cache.remember(cache.states[0])
    fresh = install(desktop, "b" * 16, 20)
    result = cache.discover()
    assert checked == [old, fresh]
    assert result["runtimes"][0]["path"] == fresh
    assert result["preferences"]["codex"] == "codex (ChatGPT 데스크톱)"
    assert result["runtimes"][0]["usable"]


def test_runner_finds_desktop_but_never_overrides_explicit_wsl_selection(desktop, tmp_path, monkeypatch):
    exe = install(desktop)
    monkeypatch.delenv("BRIDGE_RUNTIME_SELECTION", raising=False)
    monkeypatch.delenv("BRIDGE_AI_PATH_CODEX", raising=False)
    monkeypatch.setattr(runner, "_which", lambda name: None)
    monkeypatch.setattr(runner, "_ai_install_dirs", lambda: [])
    monkeypatch.setattr(runner, "_which_ai_in_wsl", lambda name: "/usr/bin/" + name)
    assert runner._which_ai("codex") == exe
    assert runner._which_ai("claude") == "/usr/bin/claude"
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({"codex": {"where": "wsl", "path": "/usr/bin/codex",
                                              "distro": "Ubuntu", "user": "alice"}}))
    monkeypatch.setenv("BRIDGE_RUNTIME_SELECTION", str(selection))
    assert runner._which_ai("codex") == "/usr/bin/codex"


def test_old_desktop_on_path_is_replaced_by_current_payload(desktop, tmp_path, monkeypatch):
    old = install(desktop)
    fresh = install(desktop, "b" * 16, 20)
    monkeypatch.setattr(core.shutil, "which", lambda name: old if name == "codex" else None)
    assert core.which_runtime("codex") == fresh
    monkeypatch.setattr(core, "which_runtime", lambda name: old if name == "codex" else None)
    assert [st.path for st in core.native_runtimes("codex")] == [fresh]
    monkeypatch.delenv("BRIDGE_RUNTIME_SELECTION", raising=False)
    monkeypatch.delenv("BRIDGE_AI_PATH_CODEX", raising=False)
    monkeypatch.setattr(runner, "_which", lambda name: old)
    assert runner._which_ai("codex") == fresh


def test_client_and_standalone_runner_keep_one_discovery_contract():
    for name in ("_desktop_codex_root", "_is_desktop_codex_path", "_desktop_codex_path"):
        assert ast.dump(ast.parse(inspect.getsource(getattr(core, name)))) == ast.dump(
            ast.parse(inspect.getsource(getattr(runner, name))))
