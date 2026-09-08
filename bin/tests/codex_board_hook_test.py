#!/usr/bin/env python3
"""Codex adapter integration checks; every operation uses an isolated board."""

import json
import os
from pathlib import Path
import pwd
import shutil
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
                      (self.cwd.parent / ".board-root").read_text().splitlines())
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

    def copied_adapter(self):
        hook = self.cwd / 'bin/hooks/codex-board-hook.py'
        support = self.cwd / 'bin/codex-migration/board_support.py'
        hook.parent.mkdir(parents=True)
        support.parent.mkdir(parents=True)
        shutil.copyfile(HOOK, hook)
        shutil.copyfile(REPO / 'bin/codex-migration/board_support.py', support)
        return hook

    def test_legacy_consumer_without_board_core_is_quiet_and_not_upgraded(self):
        hook = self.copied_adapter()
        result = self.command(['python3', str(hook)], json.dumps({
            'hook_event_name': 'SessionStart', 'session_id': 'test-session', 'source': 'startup'
        }))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        self.assertFalse((self.cwd / 'bin/lib/board_fs.py').exists())
        self.assertFalse((self.wrapper / '.board-root').exists())

    def test_existing_board_core_failure_is_reported_even_when_dependency_is_missing(self):
        hook = self.copied_adapter()
        core = self.cwd / 'bin/lib/board_fs.py'
        core.parent.mkdir(parents=True)
        core.write_text('raise FileNotFoundError("missing_dependency")\n')
        result = self.command(['python3', str(hook)], '{}')
        self.assertEqual((result.returncode, result.stdout), (0, ''))
        self.assertEqual(json.loads(result.stderr), {
            'component': 'codex-board-hook', 'error': 'FileNotFoundError'
        })

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

    def test_missed_start_registers_on_prompt_and_disable_stays_quiet(self):
        self.init_board()
        self.assertIsNone(self.hook("UserPromptSubmit", turn_id="unregistered"))
        self.assertEqual(self.presence()["state"], "active")
        before = self.presence()
        self.env["AGENT_BOARD_DISABLE"] = "1"
        self.assertIsNone(self.start())
        self.assertEqual(self.presence(), before)

    def test_native_env_event_mismatch_never_registers_foreign_thread(self):
        self.init_board()
        self.env["CODEX_THREAD_ID"] = "actual-thread"
        for event, fields in (("SessionStart", {"source": "startup"}),
                              ("UserPromptSubmit", {}), ("Stop", {}), ("SessionEnd", {})):
            self.assertIsNone(self.hook(event, **fields))
        self.assertEqual(list((self.root / "sessions").glob("*.json")), [])

    def test_cli_codex_identity_overrides_parent_claude_exports(self):
        self.init_board()
        writer = self.writer()
        self.env.update(CODEX_THREAD_ID="test-session", CLAUDE_CODE_SESSION_ID="test-writer",
                        AGENT_BOARD_SID=writer, AGENT_BOARD_TOKEN="example-parent-token")
        post = self.board("milestone", "--work", "META-0073", "-m", "Codex starts")
        self.assertIn('"sid":"' + self.sid + '"', (self.root / "channels/public" / (post + ".md")).read_text())
        self.assertEqual(self.presence()["work_ref"], "META-0073")
        self.board("post", "-m", "Codex finding")
        self.board("done")
        self.assertEqual(self.presence()["state"], "done")
        self.board("reactivate")
        self.assertEqual(self.presence()["state"], "active")
        peer = json.loads((self.root / "sessions" / (writer + ".json")).read_text())
        self.assertEqual(peer["state"], "active")

    def test_bootstrap_binds_existing_hook_registration_without_resetting_state(self):
        self.init_board()
        self.start()
        self.env["CODEX_THREAD_ID"] = "test-session"
        token = self.token()
        cursor = self.root / "cursors" / self.sid / "state.json"
        before = cursor.read_bytes()
        for state in ("active", "muted", "done"):
            if state == "muted":
                self.board("mute")
            if state == "done":
                self.board("unmute")
                self.board("done")
            self.board("bootstrap", "--work", "META-0073", "--worktree", str(self.cwd))
            self.assertEqual(self.presence()["work_ref"], "META-0073")
            self.assertEqual(self.presence()["state"], state)
            self.assertEqual(self.presence()["worktree"], self.cwd.name)
            self.assertEqual(self.token(), token)
            self.assertEqual(cursor.read_bytes(), before)

    def test_bad_codex_id_never_falls_back_to_only_peer(self):
        self.init_board()
        writer = self.writer()
        self.env["CODEX_THREAD_ID"] = "../bad"
        for args in (("post", "-m", "must not publish"), ("done",), ("reactivate",)):
            result = self.command(["bash", str(BOARD), *args])
            self.assertEqual(result.returncode, 3, result.stderr)
        result = self.command(["bash", str(BOARD), "milestone", "-m", "bad identity"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("bad_native_id", result.stderr)
        self.assertEqual(list((self.root / "channels/public").glob("*.md")), [])
        self.assertEqual(json.loads((self.root / "sessions" / (writer + ".json")).read_text())["state"], "active")

    def test_reactivate_checks_platform_as_well_as_native_id(self):
        self.init_board()
        peer = self.board("register", "--platform", "claude", "--native-id", "test-session")
        self.board("done", "--sid", peer)
        self.env["CODEX_THREAD_ID"] = "test-session"
        result = self.command(["bash", str(BOARD), "reactivate", "--sid", peer])
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("self_only", result.stderr)

    def test_cross_platform_question_answer_uses_same_project_only(self):
        self.init_board()
        self.start()
        writer = self.writer()
        self.env["CODEX_THREAD_ID"] = "test-session"
        question = self.board("post", "--channel", "dm", "--to", writer,
                              "--kind", "question", "-m", "Which module owns migration?")
        delivered = self.command(["bash", str(BOARD), "deliver", "--platform", "claude",
                                  "--event", "on_prompt", "--sid", writer, "--stdin-json", "-"], "{}")
        self.assertIn("Which module", delivered.stdout)
        self.board("post", "--sid", writer, "--channel", "dm", "--to", self.sid,
                   "--kind", "answer", "--re", question, "-m", "Migration belongs to bin/migrations.")
        own_cwd, own_root = self.cwd, self.root
        self.cwd = Path(self.tmp.name) / "other-project/repo"
        self.cwd.mkdir(parents=True)
        (self.cwd / "AGENTS.md").write_text("# Other project\n")
        self.init_board()
        self.assertNotEqual(self.root, own_root)
        self.start()
        self.assertIsNone(self.hook("UserPromptSubmit", turn_id="other"))
        self.assertNotIn("Migration belongs", self.board("read"))
        self.cwd, self.root = own_cwd, own_root
        context = self.hook("UserPromptSubmit", turn_id="answer")
        self.assertIn("Migration belongs", context["hookSpecificOutput"]["additionalContext"])

    def test_linked_worktree_resolves_same_board_and_other_repo_pointer_is_rejected(self):
        self.command(["git", "init", "-q"])
        self.command(["git", "add", "AGENTS.md"])
        result = self.command(["git", "-c", "user.name=Test", "-c", "user.email=t@t", "commit", "-qm", "init"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.init_board()
        own_cwd = self.cwd
        linked = Path(self.tmp.name) / "linked"
        result = self.command(["git", "worktree", "add", "-qb", "test", str(linked)])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.cwd = linked
        self.start()
        self.assertEqual(self.presence()["worktree"], linked.name)
        self.cwd = Path(self.tmp.name) / "foreign/repo"
        self.cwd.mkdir(parents=True)
        (self.cwd / "AGENTS.md").write_text("# Foreign\n")
        shutil.copyfile(own_cwd.parent / ".board-root", self.cwd.parent / ".board-root")
        self.assertIsNone(self.start())


if __name__ == "__main__":
    unittest.main()
