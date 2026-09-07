"""Codex lifecycle binding for the existing, platform-neutral board operations.

The core's CLI deliberately still advertises its measured Claude adapter only.
This module owns Codex support without rewriting that core (including local
user changes). Its separately loaded module gets a process-local delivery gate
and wire renderer. Identity remains ``codex:<uid>:<native id>``; authentication,
filesystem validation, quotas, redaction, locks and emit-before-commit remain
the original board implementation. No Claude session or environment is used.

Contract: https://learn.chatgpt.com/docs/hooks.md (reviewed 2026-09-07).
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys


EVENTS = {
    "SessionStart": "on_session_start",
    "UserPromptSubmit": "on_prompt",
    "Stop": "on_turn_end",
    "SessionEnd": None,
}


def load_core():
    path = Path(__file__).resolve().parents[1] / "lib" / "board_fs.py"
    name = "_codex_board_core"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("board_core_unavailable")
    core = importlib.util.module_from_spec(spec)
    sys.modules[name] = core  # dataclass resolves its module during import
    spec.loader.exec_module(core)

    old_final, old_empty = core._final_json, core._empty_output

    def render(platform, event, text, root_path):
        if platform != "codex":
            return old_final(platform, event, text, root_path)
        # Codex has no FileChanged/watchPaths contract. The shared output is
        # informational only: no decision, continue, permission or commands.
        name = core.CLAUDE_EVENT_NAME[event]  # vocabulary also used by Codex
        output = {"hookEventName": name}
        if text:
            output["additionalContext"] = text
        return core.jdump({"hookSpecificOutput": output})

    def empty(platform, event, root_path):
        if platform != "codex":
            return old_empty(platform, event, root_path)
        return "{}" if event in ("on_session_start", "on_compact") else ""

    core.P1_DELIVER_PLATFORMS = (*core.P1_DELIVER_PLATFORMS, "codex")
    core._final_json = render
    core._empty_output = empty
    # This lifecycle adapter receives and maintains presence only. The existing
    # auto-done check may update its own state, but must not publish an implicit
    # cross-session status message. Explicit board posting remains a user action.
    core.post_status_done = lambda *args, **kwargs: None
    return core


def handle(payload: dict, cwd: str) -> str:
    """Run one Codex hook against an already initialized board, never bootstrap."""
    event = payload.get("hook_event_name")
    native = payload.get("session_id")
    if event not in EVENTS or os.environ.get("AGENT_BOARD_DISABLE") == "1":
        return ""
    core = load_core()
    if not isinstance(native, str) or not core.fm(core.RE_NATIVE, native):
        return ""
    if event == "SessionStart" and payload.get("source") not in (
        "startup", "resume", "clear", "compact"
    ):
        return ""
    sid = "codex:%s:%s" % (core.current_uid_name(), native)
    root = None
    log = None
    try:
        res, root, board, log = core.open_board(cwd, log_sid=sid)
        if res is None or root is None or board is None:
            return ""
        if event == "SessionEnd":
            # Codex reports `other` for ordinary close, idle timeout AND
            # archive/delete. It cannot identify permanent deletion. Suspend
            # rather than tombstone so `codex resume` retains its cursor/state.
            core.transition(root, board, log, sid=sid, token=None,
                            target="suspended", hook=True, reason="codex_session_end")
            log.emit("codex-hook", "suspended", event=event)
            return ""
        if event == "Stop":
            # The released Codex Stop contract documents continuation decisions
            # and common fields, not additionalContext consumption. Sending
            # board context here could advance a cursor for an ignored message.
            # Maintain only our presence/auto-done state; deliver on the next
            # UserPromptSubmit or SessionStart. Zero context means zero budget.
            pres = core.load_presence(root, sid, log)
            if pres is None:
                return ""
            with core.Flock(root, ("cursors", sid, "lock"), 0o600, nonblock=True) as lock:
                if not lock.held:
                    return ""
                pres = core.authz_session(root, sid, None, log, tuple(core.STATES))
                if pres["state"] == "active":
                    pres["last_seen"] = core.iso_utc()
                    if payload.get("stop_hook_active") is not True and core.auto_done_signal(root, sid, pres):
                        pres["state"] = "done"
                        pres["done_at"] = core.iso_utc()
                    core.save_presence(root, pres)
            return ""
        if event == "SessionStart":
            source = payload["source"]
            pres = core.load_presence(root, sid, log)
            # Do not rotate a live session's token on duplicate/compact starts
            # or reactivate done/muted sessions. Core resume restores prev_state.
            if pres is None or (source != "compact" and (
                pres.get("state") == "suspended" or pres.get("stale_since")
            )):
                model = payload.get("model")
                core.do_register(
                    root, board, res, log, native_id=native, platform="codex",
                    alias=None, work="-", model=model if isinstance(model, str) else None,
                    harness="codex", worktree=os.path.realpath(cwd), resume=True,
                    env_file=None,
                )
            log.emit("codex-hook", "session_start", event=event, source=source)
        board_event = "on_compact" if (
            event == "SessionStart" and payload["source"] == "compact"
        ) else EVENTS[event]
        # Important: let core deliver emit and flush its final Codex JSON while
        # holding the session lock, then commit the cursor. Capturing or changing
        # stdout after deliver would introduce a message-loss window.
        return core.deliver(res, root, board, log, platform="codex",
                            event=board_event, sid=sid, stdin_obj=payload)
    except Exception as exc:
        if log is not None:
            log.emit("codex-hook", "failed", event=event, error=type(exc).__name__)
        return ""
    finally:
        if root is not None:
            root.close()


def main() -> int:
    try:
        # Bound reads; reject duplicate keys with the board's strict parser.
        raw = sys.stdin.buffer.read((1 << 20) + 1)
        if len(raw) > 1 << 20:
            return 0
        core = load_core()
        payload = core.json_loads_strict(raw)
        if not isinstance(payload, dict):
            return 0
        # Codex executes hooks in session cwd. Never choose a filesystem scope
        # from prompt, transcript path, board message or a supplied --root.
        out = handle(payload, os.getcwd())
        if out:
            sys.stdout.write(out + "\n")
            sys.stdout.flush()
    except Exception as exc:
        # No prompt/transcript/credential values in errors; a hook never blocks.
        sys.stderr.write(json.dumps({"component": "codex-board-hook",
                                     "error": type(exc).__name__}) + "\n")
    return 0
