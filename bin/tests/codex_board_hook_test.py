#!/usr/bin/env python3
"""Codex adapter integration checks; every operation uses an isolated board."""

import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
BOARD = REPO / "bin/board.sh"
HOOK = REPO / "bin/hooks/codex-board-hook.py"


class CodexBoardHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="codex-board-test-")
        self.addCleanup(self.tmp.cleanup)
        self.wrapper = Path(self.tmp.name) / "wrapper"
        self.cwd = self.wrapper / "repo"
        self.cwd.mkdir(parents=True)
        (self.cwd / "AGENTS.md").write_text("# Isolated test repository\n")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith((
            "AGENT_BOARD_", "CLAUDE_", "CODEX_", "BOARD_"
        ))}
        self.env["XDG_STATE_HOME"] = str(Path(self.tmp.name) / "xdg")
        self.uid = pwd.getpwuid(os.getuid()).pw_name
        self.sid = "codex:%s:test-session" % self.uid

    def command(self, argv, text=None):
        return subprocess.run(argv, cwd=self.cwd, env=self.env, input=text,
                              capture_output=True, text=True, timeout=10)

    def board(self, *args):
        result = self.command(["bash", str(BOARD), *args])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def init_board(self):
        self.board("init", "--mode", "private")
        fields = dict(line.split("=", 1) for line in
                      (self.wrapper / ".board-root").read_text().splitlines())
        self.root = Path(fields["root"])

    def hook(self, event, **fields):
        payload = dict(hook_event_name=event, session_id="test-session",
                       cwd=str(self.cwd), **fields)
        result = self.command(["python3", str(HOOK)], json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        if result.stdout.strip():
            obj = json.loads(result.stdout)
            self.assertFalse({"decision", "continue", "stopReason"} & obj.keys())
            self.assertNotIn("watchPaths", result.stdout)
            self.assertNotIn("AGENT_BOARD_TOKEN", result.stdout)
            return obj
        return None

    def start(self, **fields):
        return self.hook("SessionStart", source="startup", **fields)

    def presence(self):
        return json.loads((self.root / "sessions" / (self.sid + ".json")).read_text())

    def token(self):
        return (self.root / "sessions" / (self.sid + ".token")).read_text()

    def writer(self):
        return self.board("register", "--platform", "claude", "--native-id", "test-writer")

    def post(self, writer, body):
        self.board("post", "--sid", writer, "--channel", "public", "--kind", "note", "-m", body)

    def test_uninitialized_board_is_not_created(self):
        self.assertIsNone(self.start())
        self.assertFalse((self.wrapper / ".board-root").exists())
        self.assertEqual(sorted(p.name for p in self.cwd.iterdir()), ["AGENTS.md"])

    def test_rejects_malformed_duplicate_oversized_and_unknown_input(self):
        self.init_board()
        for raw in ("bad json", "[]", '{"session_id":"a","session_id":"b"}', " " * ((1 << 20) + 1)):
            result = self.command(["python3", str(HOOK)], raw)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
        self.assertIsNone(self.hook("FileChanged"))
        result = self.command(["python3", str(HOOK)], json.dumps({
            "hook_event_name": "SessionStart", "source": "startup", "session_id": "../bad\n"
        }))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(list((self.root / "sessions").glob("*.json")), [])

    def test_native_codex_registration_and_duplicate_start_preserve_token(self):
        self.init_board()
        self.env["CLAUDE_CODE_SESSION_ID"] = "foreign-claude-session"
        envfile = Path(self.tmp.name) / "claude-env"
        envfile.write_text("unchanged\n")
        self.env["CLAUDE_ENV_FILE"] = str(envfile)
        self.assertEqual(self.start(model="test-codex-model"), {})
        pres = self.presence()
        self.assertEqual((pres["platform"], pres["harness"], pres["model"]),
                         ("codex", "codex", "test-codex-model"))
        self.assertEqual(pres["sid"], self.sid)
        token = self.token()
        self.start()
        self.hook("SessionStart", source="compact")
        self.assertEqual(self.token(), token)
        self.assertEqual(envfile.read_text(), "unchanged\n")
        self.assertEqual(list((self.root / "sessions").glob("claude:*")), [])

    def test_prompt_delivery_keeps_core_cursor_and_codex_budget(self):
        self.init_board()
        self.start()
        writer = self.writer()
        self.post(writer, "isolated prompt message")
        obj = self.hook("UserPromptSubmit", turn_id="one", prompt="private input never echoed")
        context = obj["hookSpecificOutput"]
        self.assertEqual(context["hookEventName"], "UserPromptSubmit")
        self.assertIn('"body":"isolated prompt message"', context["additionalContext"])
        self.assertIn(self.sid, context["additionalContext"])
        self.assertNotIn("private input", json.dumps(obj))
        self.assertLessEqual(len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()), 2048)
        self.assertIsNone(self.hook("UserPromptSubmit", turn_id="two"))
        usage = self.root / "cursors" / self.sid / "usage.jsonl"
        self.assertTrue(usage.exists())

    def test_stop_updates_presence_without_consuming_context_cursor_or_budget(self):
        self.init_board()
        self.start()
        writer = self.writer()
        self.post(writer, "isolated stop message")
        state = self.root / "cursors" / self.sid / "state.json"
        before = state.read_bytes()
        self.assertIsNone(self.hook("Stop", turn_id="turn-one", stop_hook_active=True))
        self.assertIsNone(self.hook("Stop", turn_id="turn-one", stop_hook_active=False))
        self.post(writer, "next message")
        self.assertIsNone(self.hook("Stop", turn_id="turn-one", stop_hook_active=False))
        self.assertEqual(state.read_bytes(), before)
        self.assertFalse((state.parent / "usage.jsonl").exists())
        obj = self.hook("UserPromptSubmit", turn_id="turn-two")
        self.assertIn("next message", obj["hookSpecificOutput"]["additionalContext"])
        self.assertIn("isolated stop message", obj["hookSpecificOutput"]["additionalContext"])

    def test_session_end_suspends_and_resume_restores_state(self):
        self.init_board()
        self.start()
        self.hook("SessionEnd", reason="other")
        self.assertEqual(self.presence()["state"], "suspended")
        self.hook("SessionStart", source="resume")
        self.assertEqual(self.presence()["state"], "active")
        self.board("mute", "--sid", self.sid)
        self.hook("SessionEnd", reason="other")
        self.hook("SessionStart", source="resume")
        self.assertEqual(self.presence()["state"], "muted")

    def test_auto_done_and_resume_never_publish_or_reactivate(self):
        self.init_board()
        self.start()
        (self.root / "cursors" / self.sid / "DONE").write_text("1\n")
        self.assertIsNone(self.hook("UserPromptSubmit", turn_id="done-turn"))
        self.assertEqual(self.presence()["state"], "done")
        self.assertEqual(list((self.root / "channels/public").glob("*.md")), [])
        self.hook("SessionEnd", reason="other")
        self.hook("SessionStart", source="resume")
        self.assertEqual(self.presence()["state"], "done")

    def test_missing_start_is_recovered_by_first_prompt_without_posting(self):
        self.init_board()
        self.assertIsNone(self.hook("UserPromptSubmit", turn_id="unregistered"))
        self.assertEqual(self.presence()["platform"], "codex")
        self.assertEqual(self.presence()["state"], "active")
        token = self.token()
        self.assertIsNone(self.hook("UserPromptSubmit", turn_id="second"))
        self.assertEqual(self.token(), token)
        self.assertEqual(list((self.root / "channels/public").glob("*.md")), [])

    def test_disabled_lifecycle_does_not_create_presence(self):
        self.init_board()
        self.env["AGENT_BOARD_DISABLE"] = "1"
        self.assertIsNone(self.start())
        self.assertIsNone(self.hook("UserPromptSubmit", turn_id="disabled"))
        self.assertIsNone(self.hook("Stop"))
        self.assertIsNone(self.hook("SessionEnd", reason="other"))
        self.assertEqual(list((self.root / "sessions").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
