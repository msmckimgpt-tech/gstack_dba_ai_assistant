"""Run the production authentication transition behavior checks with pytest."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_auth_transition_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for browser JavaScript behavior checks")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("verify_auth_transition.mjs"))],
        capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
