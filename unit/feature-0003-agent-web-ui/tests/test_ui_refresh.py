"""Run behavior checks against the production refresh controller and page guard."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_ui_refresh_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for browser JavaScript behavior checks")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("verify_ui_refresh.mjs"))],
        capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
