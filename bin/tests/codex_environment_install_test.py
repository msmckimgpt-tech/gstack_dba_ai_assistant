#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'codex-environment-install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
hspec = importlib.util.spec_from_file_location('history', ROOT / 'agent-context.py')
history = importlib.util.module_from_spec(hspec)
hspec.loader.exec_module(history)


class Compatibility(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'project/repo'
        self.root.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'AGENTS.md').write_text('policy\n' * 10000)
        (self.root / 'CLAUDE.md').write_text('Domain rule must remain.\n')
        for folder in ['.claude/commands/_project', '.claude/commands/_local', '.claude/agents', '.codex/commands/_project']:
            (self.root / folder).mkdir(parents=True)
        (self.root / '.claude/commands/_project/run.md').write_text('Claude fallback')
        (self.root / '.codex/commands/_project/run.md').write_text('Codex custom canonical')
        (self.root / '.claude/commands/_local/inbox.md').write_text('Template-only sentinel')
        (self.root / '.claude/agents/reviewer.md').write_text('---\nname: reviewer\nmodel: opus\n---\nReview the actual diff.\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_is_read_only_and_apply_is_idempotent(self):
        original = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        self.assertTrue(installer.install(self.root, self.root, False))
        self.assertEqual(original, sorted(p.relative_to(self.root) for p in self.root.rglob('*')))
        installer.install(self.root, self.root, True)
        self.assertEqual([], installer.install(self.root, self.root, True))

    def test_canonical_domain_guidance_and_claude_preserved(self):
        original = (self.root / '.claude/commands/_project/run.md').read_bytes()
        installer.install(self.root, self.root, True)
        self.assertEqual(original, (self.root / '.claude/commands/_project/run.md').read_bytes())
        self.assertEqual('Codex custom canonical', (self.root / '.codex/commands/_project/run.md').read_text())
        self.assertIn('Domain rule must remain.', (self.root / 'CLAUDE.md').read_text())
        self.assertFalse((self.root / '.codex/commands/_local/inbox.md').exists())
        self.assertTrue((self.root / '.agents/skills/_project-run/SKILL.md').is_file())
        agent = tomllib.loads((self.root / '.codex/agents/reviewer.toml').read_text())
        self.assertNotIn('model', agent)
        self.assertIn('Review the actual diff.', agent['developer_instructions'])

    def test_custom_override_and_symlink_refused(self):
        (self.root / 'AGENTS.override.md').write_text('user-owned override')
        with self.assertRaises(ValueError):
            installer.install(self.root, self.root, True)
        (self.root / 'AGENTS.override.md').unlink()
        outside = Path(self.tmp.name) / 'outside'
        outside.write_text('original')
        (self.root / 'AGENTS.override.md').symlink_to(outside)
        with self.assertRaises(ValueError):
            installer.install(self.root, self.root, True)
        self.assertEqual('original', outside.read_text())

    def linked_target(self):
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        target = self.root.parent / '.worktrees/feature'
        subprocess.run(['git', '-C', str(self.root), 'worktree', 'add', '-q', '-b',
                        'compatibility-test', str(target)], check=True)
        return target

    def test_diverged_target_guidance_commands_and_native_skills_survive(self):
        target = self.linked_target()
        (target / 'CLAUDE.md').write_text('Target branch domain guidance.\n')
        command = target / '.codex/commands/_project/run.md'
        command.write_text('Target custom canonical.\n')
        extra = target / '.claude/commands/_project/new.md'
        extra.write_text('Target-only workflow.\n')
        skill = target / '.codex/skills/_project-run/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: _project-run\ndescription: Custom\n---\nCustom workflow.\n')
        before = skill.read_bytes()
        installer.install(self.root, target, True)
        self.assertIn('Target branch domain guidance.', (target / 'CLAUDE.md').read_text())
        self.assertNotIn('Domain rule must remain.', (target / 'CLAUDE.md').read_text())
        self.assertEqual(command.read_text(), 'Target custom canonical.\n')
        self.assertEqual(skill.read_bytes(), before)
        self.assertEqual((target / '.codex/commands/_project/new.md').read_text(), extra.read_text())
        self.assertTrue((target / '.agents/skills/_project-run/SKILL.md').is_file())
        self.assertEqual((self.root / 'CLAUDE.md').read_text(), 'Domain rule must remain.\n')

    def test_standard_wrappers_upgrade_but_edited_managed_bodies_are_preserved(self):
        skill = self.root / '.codex/skills/_project-run/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: _project-run\ndescription: Original\n---\n\n'
                         '# _project-run\n\nRead and follow `.codex/commands/_project/run.md` in the current repository.\n'
                         'That command file is the canonical Codex prompt for this workflow.\n')
        installer.install(self.root, self.root, True)
        self.assertIn('generated_by: codex-environment-install', skill.read_text())
        skill.write_text(skill.read_text() + '\nAdditional project restriction.\n')
        before = skill.read_bytes()
        installer.install(self.root, self.root, True)
        self.assertEqual(skill.read_bytes(), before)

    def test_multiline_descriptions_become_useful_skill_and_agent_labels(self):
        command = self.root / '.codex/commands/_project/run.md'
        command.write_text('---\ndescription: |\n  Review current changes.\n  Use the panel.\n---\nRun workflow.\n')
        agent = self.root / '.claude/agents/reviewer.md'
        agent.write_text('---\nname: reviewer\ndescription: >-\n  Review current changes\n  with project constraints.\n---\nReview.\n')
        installer.install(self.root, self.root, True)
        text = (self.root / '.codex/skills/_project-run/SKILL.md').read_text()
        desc = next(line.split(': ', 1)[1] for line in text.splitlines() if line.startswith('description: '))
        self.assertEqual(json.loads(desc), 'Review current changes.\nUse the panel.')
        config = tomllib.loads((self.root / '.codex/agents/reviewer.toml').read_text())
        self.assertEqual(config['description'], 'Review current changes with project constraints.')

    def test_wrapper_discovers_skills_and_policy(self):
        installer.install(self.root, self.root, True)
        installer.wrapper_links(self.root, True)
        self.assertTrue((self.root.parent / '.agents/skills/_project-run/SKILL.md').is_file())
        self.assertIn('repo/.codex/CONTEXT.md', (self.root.parent / 'AGENTS.md').read_text())

    def test_project_config_layer_is_created_without_overwriting_existing_settings(self):
        config = self.root / '.codex/config.toml'
        installer.install(self.root, self.root, True)
        self.assertTrue(config.is_file())
        self.assertEqual(tomllib.loads(config.read_text()), {})
        config.write_text('model_reasoning_effort = "high"\n')
        installer.install(self.root, self.root, True)
        self.assertEqual(config.read_text(), 'model_reasoning_effort = "high"\n')

    def test_history_card_distinguishes_tools_and_subagents(self):
        p = Path(self.tmp.name) / 'thread.jsonl'
        p.write_text('{"type":"session_meta","payload":{"id":"abc","cwd":"/work/repo","parent_thread_id":"parent"}}\n'
                     '{"type":"event_msg","payload":{"type":"user_message","message":"continue this work"}}\n')
        card = history.session_card(p, 'codex', 'root', {'abc': 'Saved title'})
        self.assertEqual('abc', card['id'])
        self.assertEqual('Saved title', card['title'])
        self.assertTrue(card['subagent'])
        self.assertTrue(history.matches_project('/work/.worktrees/feature', '/work/repo'))
        self.assertFalse(history.matches_project('/work-other/repo', '/work/repo'))

    def test_history_ignores_non_object_records_and_malformed_messages(self):
        p = Path(self.tmp.name) / 'thread.jsonl'
        p.write_text('[]\nnull\n5\n{"type":"user","message":[]}\n'
                     '{"type":"user","message":{"content":[{"type":"text","text":[]} ]}}\n'
                     '{"type":"user","cwd":"/work/repo","message":{"content":"Actual title"}}\n')
        card = history.session_card(p, 'claude', 'root', {})
        self.assertEqual(card['title'], 'Actual title')
        self.assertEqual(card['cwd'], '/work/repo')

    def test_history_project_identity_groups_main_linked_and_removed_worktrees(self):
        target = self.linked_target()
        self.assertTrue(history.matches_project(str(self.root), target))
        self.assertTrue(history.matches_project(str(target), self.root))
        self.assertTrue(history.matches_project(str(self.root.parent), target))
        removed = self.root.parent / '.worktrees/already-removed'
        self.assertTrue(history.matches_project(str(removed), target))
        self.assertFalse(history.matches_project('/another-project/repo', target))

    def test_import_receipt_marks_snapshot_and_preserves_original_recency(self):
        home = Path(self.tmp.name) / 'account'
        source = home / '.claude/projects/project/original.jsonl'
        source.parent.mkdir(parents=True)
        source.write_text('{"type":"user","cwd":"/work/repo","message":{"content":"Original work"}}\n')
        os.utime(source, (1_000_000_000, 1_000_000_000))
        codex = home / '.codex/sessions'
        codex.mkdir(parents=True)
        for sid in ['imported', 'native']:
            (codex / (sid + '.jsonl')).write_text(json.dumps({
                'type': 'session_meta', 'payload': {'id': sid, 'source': 'vscode', 'cwd': '/work/repo'}
            }) + '\n')
        receipt = home / '.codex/migration-20260907/native-home-import-result.json'
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({'completed': {'itemTypeResults': [
            {'itemType': 'SESSIONS', 'successes': [{'target': 'imported', 'source': str(source)}]}
        ]}}))
        data = history.own_inventory('account', home)
        cards = {x['id']: x for x in data['sessions']}
        self.assertEqual(cards['imported']['history_kind'], 'import_snapshot')
        self.assertEqual(cards['imported']['imported_from']['original_id'], 'original')
        self.assertTrue(cards['imported']['updated_at'].startswith('2001-09-09'))
        self.assertNotIn('history_kind', cards['native'])
        resumed_at = receipt.stat().st_mtime + 60
        os.utime(codex / 'imported.jsonl', (resumed_at, resumed_at))
        resumed = next(x for x in history.own_inventory('account', home)['sessions'] if x['id'] == 'imported')
        self.assertEqual(resumed['history_kind'], 'imported_with_later_activity')
        self.assertGreater(resumed['updated_at'], resumed['imported_at'])
        self.assertEqual(resumed['imported_from']['original_id'], 'original')

    def test_history_filter_tolerates_another_accounts_private_workspaces(self):
        with mock.patch.object(Path, 'is_file', side_effect=PermissionError('private')):
            self.assertEqual(history.project_anchor('/inaccessible/project/repo'),
                             Path('/inaccessible/project'))
        self.assertFalse(history.matches_project('C:\\Users\\developer\\project', self.root))


if __name__ == '__main__':
    unittest.main()
