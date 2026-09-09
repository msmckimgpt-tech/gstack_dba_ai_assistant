"""Installed slots are immutable; the launcher pointer is the activation record."""
from __future__ import annotations

import re
from pathlib import Path

from . import core, version

SLOT_RE = re.compile(r"([0-9]+(?:\.[0-9]+){0,3})-[0-9]+\Z")


def install_root() -> Path:
    app = core.app_dir()
    if app.parent.name == "versions" and SLOT_RE.fullmatch(app.name):
        return app.parent.parent
    return app


def active_version(root: Path | None = None) -> str:
    root = root if root is not None else install_root()
    try:
        slot = (root / "active-slot.txt").read_text(encoding="utf-8-sig").strip()
        match = SLOT_RE.fullmatch(slot)
        if not match:
            return ""
        path = root / "versions" / slot
        if path.resolve().parent != (root / "versions").resolve():
            return ""
        completed = (path / "install-complete.txt").read_text(encoding="utf-8-sig").strip()
        if completed != match[1]:
            return ""
        if not all((path / name).is_file() for name in
                   ("DQAConnect.exe", "runtime/python.exe")):
            return ""
        return match[1]
    except (OSError, ValueError):
        return ""


def prepared_version(current: str = version.CLIENT_VERSION) -> str:
    active = active_version()
    return active if version.is_newer(active, current) else ""


def verify_payload() -> int:
    try:
        if (core.app_dir() / "install-complete.txt").read_text().strip() != version.CLIENT_VERSION:
            return 1
        import webview  # noqa: F401
        import subprocess
        runtime = core.app_dir() / "runtime" / "python.exe"
        result = subprocess.run(
            [str(runtime), "-c", "import ssl, json, subprocess, urllib.request"],
            **core.hidden_child_kwargs(), timeout=30)
        return 0 if result.returncode == 0 else 1
    except Exception:
        return 1


def redirect_to_active(argv: list[str]) -> bool:
    """Old shortcuts to a versioned executable must follow the current installation."""
    import sys
    import subprocess
    if not getattr(sys, "frozen", False):
        return False
    app = core.app_dir()
    if app.parent.name != "versions" or not active_version():
        return False
    root = install_root()
    try:
        active_slot = (root / "active-slot.txt").read_text(encoding="utf-8-sig").strip()
    except OSError:
        return False
    if active_slot == app.name:
        return False
    subprocess.Popen([str(root / "DQALauncher.exe"), *argv], close_fds=True)
    return True
