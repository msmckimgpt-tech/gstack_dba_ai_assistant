#!/usr/bin/env python3
"""Codex SessionStart, UserPromptSubmit, Stop and SessionEnd board adapter.

Install this absolute command in a trusted Codex hooks.json. It only uses an
existing board and never creates groups, installs hooks, or posts a message.
"""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codex-migration"))
try:
    from board_support import main

    raise SystemExit(main())
except Exception:
    # Missing core/dependencies must not interrupt the coding session.
    sys.stderr.write("codex-board-hook: adapter unavailable\n")
    raise SystemExit(0)
