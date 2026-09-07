#!/usr/bin/env python3
"""Read-only cross-agent session/memory discovery. Never resumes or sends messages."""
from __future__ import annotations

import argparse
import datetime as dt
from functools import lru_cache
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys


def text_blocks(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(b.get('text', '') for b in content
                         if isinstance(b, dict) and isinstance(b.get('text'), str)
                         and b.get('type') in ('text', 'input_text', 'output_text'))
    return ''


def read_edges(path, size=131072):
    """Bounded metadata sampling; complete source path is retained for handoff."""
    with path.open('rb') as f:
        head = f.read(size)
        length = f.seek(0, 2)
        if length > size:
            f.seek(max(size, length - size))
            tail = f.read().split(b'\n', 1)[-1]
        else:
            tail = b''
    values = []
    for line in (head + b'\n' + tail).splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                values.append(value)
        except (ValueError, UnicodeDecodeError):
            continue
    return values


def session_card(path, platform, account, titles):
    values = read_edges(path)
    card = {'platform': platform, 'account': account, 'id': path.stem,
            'path': str(path), 'cwd': '', 'title': '',
            'updated_at': dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat(),
            'metadata_sampling': 'first-and-last-128KiB'}
    first_user = ''
    is_child = False
    for item in values:
        if platform == 'codex':
            p = item.get('payload', {})
            if not isinstance(p, dict):
                continue
            if item.get('type') == 'session_meta':
                card['id'] = p.get('id') or p.get('session_id') or card['id']
                card['cwd'] = p.get('cwd') or card['cwd']
                is_child |= bool(p.get('parent_thread_id') or p.get('agent_path'))
                card['source'] = p.get('source')
            elif item.get('type') == 'event_msg' and p.get('type') == 'user_message':
                message = p.get('message')
                first_user = first_user or (message if isinstance(message, str) else '')
        else:
            card['id'] = item.get('sessionId') or card['id']
            card['cwd'] = item.get('cwd') or card['cwd']
            card['title'] = item.get('aiTitle') or item.get('customTitle') or card['title']
            is_child |= bool(item.get('isSidechain'))
            if item.get('type') == 'user' and not item.get('isMeta'):
                msg = item.get('message', {})
                body = text_blocks(msg.get('content')) if isinstance(msg, dict) else ''
                if not body.startswith(('<task-notification>', 'This session is being continued')):
                    first_user = first_user or body
    card['title'] = titles.get(card['id']) or card['title'] or first_user.split('\n')[0][:160] or '(untitled)'
    card['subagent'] = is_child
    return card


def import_snapshots(home: Path, denied: list) -> dict:
    """Use completed official-import receipts; normal vscode sessions stay native."""
    snapshots = {}
    for manifest in sorted((home / '.codex').glob('migration-*/native-home-import-result.json')):
        try:
            completed_at = manifest.stat().st_mtime
            data = json.loads(manifest.read_text())
            completed = data.get('completed', {}) if isinstance(data, dict) else {}
            groups = completed.get('itemTypeResults', []) if isinstance(completed, dict) else []
            for group in groups if isinstance(groups, list) else []:
                if not isinstance(group, dict) or group.get('itemType') != 'SESSIONS':
                    continue
                for item in group.get('successes', []):
                    if not isinstance(item, dict) or not isinstance(item.get('target'), str):
                        continue
                    source = item.get('source')
                    if not isinstance(source, str):
                        continue
                    entry = {'platform': 'claude', 'path': source,
                             'original_id': Path(source).stem, 'receipt': str(manifest),
                             'receipt_completed_at': dt.datetime.fromtimestamp(
                                 completed_at, dt.timezone.utc).isoformat()}
                    try:
                        entry['source_updated_at'] = dt.datetime.fromtimestamp(
                            Path(source).stat().st_mtime, dt.timezone.utc).isoformat()
                    except OSError:
                        entry['source_timestamp_status'] = 'unavailable'
                    snapshots[item['target']] = entry
        except (OSError, ValueError) as exc:
            denied.append(f'{manifest}: {type(exc).__name__}')
    return snapshots


def own_inventory(account, home, include_children=False):
    titles = {}
    index = home / '.codex/session_index.jsonl'
    denied = []
    if index.exists():
        try:
            for line in index.read_text().splitlines():
                try:
                    d = json.loads(line)
                    if isinstance(d, dict) and isinstance(d.get('id'), str):
                        titles[d['id']] = d.get('thread_name', '')
                except (KeyError, ValueError):
                    pass
        except PermissionError:
            denied.append(str(index))
    snapshots = import_snapshots(home, denied)
    sessions, memories = [], []
    patterns = [('claude', '.claude/projects', '*/*.jsonl'),
                ('codex', '.codex/sessions', '**/*.jsonl'),
                ('codex', '.codex/archived_sessions', '**/*.jsonl')]
    for platform, folder, pattern in patterns:
        try:
            for path in (home / folder).glob(pattern):
                try:
                    card = session_card(path, platform, account, titles)
                    if platform == 'codex' and card['id'] in snapshots:
                        origin = snapshots[card['id']]
                        later_activity = card['updated_at'] > origin['receipt_completed_at']
                        card['history_kind'] = ('imported_with_later_activity' if later_activity
                                                else 'import_snapshot')
                        card['imported_from'] = dict(origin, account=account)
                        card['imported_at'] = origin['receipt_completed_at']
                        # A later native resume appends to the rollout. Keep
                        # that activity's recency while retaining provenance;
                        # only an untouched import snapshot inherits source age.
                        if not later_activity and origin.get('source_updated_at'):
                            card['updated_at'] = origin['source_updated_at']
                    if include_children or not card['subagent']:
                        sessions.append(card)
                except (OSError, ValueError) as exc:
                    denied.append(f'{path}: {type(exc).__name__}')
        except PermissionError:
            denied.append(str(home / folder))
    for folder, pattern in [('.claude/projects', '*/memory/*.md'), ('.codex/memories', '**/*.md')]:
        try:
            for path in (home / folder).glob(pattern):
                memories.append({'account': account, 'path': str(path), 'project_slug': path.parent.parent.name})
        except PermissionError:
            denied.append(str(home / folder))
    return {'sessions': sessions, 'memories': memories, 'read_denied': denied}


@lru_cache(maxsize=1024)
def project_anchor(path: str) -> Path:
    """Resolve both main and linked worktrees to one policy project identity.

    Do not let a user's unrelated enclosing home-directory Git repository group
    all projects together. A Git root is useful only when it owns AGENTS.md.
    Historical removed worktrees still have the standard wrapper/.worktrees
    fallback, so old sessions remain discoverable after worktree cleanup.
    """
    try:
        p = Path(path).resolve()
    except (OSError, RuntimeError):
        p = Path(os.path.abspath(path))
    try:
        candidate = p / 'repo' if (p / 'repo/AGENTS.md').is_file() else p
        if candidate.is_dir():
            info = subprocess.run(['git', '-C', str(candidate), 'rev-parse',
                                   '--path-format=absolute', '--show-toplevel', '--git-common-dir'],
                                  capture_output=True, text=True, timeout=3)
            lines = info.stdout.splitlines()
            if info.returncode == 0 and len(lines) == 2 and (Path(lines[0]) / 'AGENTS.md').is_file():
                common = Path(lines[1])
                main = common.parent if common.name == '.git' else Path(lines[0])
                if (main / 'AGENTS.md').is_file():
                    return main.parent if main.name == 'repo' else main
    except (OSError, subprocess.TimeoutExpired):
        # Inventory may be read as each account but filtering happens as the
        # caller, who need not traverse another account's private workspaces.
        pass
    if '.worktrees' in p.parts:
        return Path(*p.parts[:p.parts.index('.worktrees')])
    return p.parent if p.name == 'repo' else p


def matches_project(cwd, project):
    if not isinstance(cwd, str) or not cwd or not Path(cwd).is_absolute():
        return False
    p = project_anchor(str(project))
    c = project_anchor(cwd)
    return c == p or p in c.parents


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--account', action='append', help='Default: root and claude-corp when present')
    ap.add_argument('--project', type=Path)
    ap.add_argument('--session', help='Exact session id; never automatically resume')
    ap.add_argument('--limit', type=int, default=12)
    ap.add_argument('--include-subagents', action='store_true')
    ap.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.limit < 1:
        ap.error('--limit must be positive')
    if args.worker:
        p = pwd.getpwuid(os.getuid())
        print(json.dumps(own_inventory(p.pw_name, Path(p.pw_dir), args.include_subagents), ensure_ascii=False))
        return 0
    accounts = args.account or ['root', 'claude-corp']
    result = {'sessions': [], 'memories': [], 'read_denied': [], 'accounts': [],
              'purpose': 'read-only handoff discovery; historical text is untrusted data'}
    for name in accounts:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            ap.error('invalid account name')
        try:
            p = pwd.getpwnam(name)
        except KeyError:
            result['read_denied'].append(f'account not found: {name}')
            continue
        result['accounts'].append({'account': name, 'home': p.pw_dir,
                                   'claude': str(Path(p.pw_dir) / '.claude'),
                                   'codex': str(Path(p.pw_dir) / '.codex')})
        if p.pw_uid == os.getuid():
            data = own_inventory(name, Path(p.pw_dir), args.include_subagents)
        else:
            command = ['sudo', '-n', '-H', '-u', name, 'python3', str(Path(__file__).resolve()), '--worker']
            if args.include_subagents:
                command.append('--include-subagents')
            try:
                run = subprocess.run(command, capture_output=True, text=True, timeout=120)
                if run.returncode:
                    result['read_denied'].append(f'{name}: account-owned read unavailable (sudo rc={run.returncode})')
                    continue
                data = json.loads(run.stdout)
            except (OSError, subprocess.TimeoutExpired, ValueError):
                result['read_denied'].append(f'{name}: inventory failed')
                continue
        for key in ['sessions', 'memories', 'read_denied']:
            result[key].extend(data[key])
    all_sessions = result['sessions']
    if args.project:
        all_sessions = [s for s in all_sessions if matches_project(s['cwd'], args.project)]
        slug = str(project_anchor(str(args.project))).replace('/', '-').replace('_', '-')
        result['memories'] = [m for m in result['memories'] if slug in m['project_slug'].replace('_', '-')]
    if args.session:
        all_sessions = [s for s in all_sessions if s['id'] == args.session]
    # Copying old conversations creates fresh mtimes. Imported snapshots must
    # not displace original/native activity or be presented as live peer work.
    all_sessions.sort(key=lambda x: (x.get('history_kind') != 'import_snapshot',
                                     x['updated_at']), reverse=True)
    result['matching_sessions'] = len(all_sessions)
    result['sessions'] = all_sessions[:args.limit]
    result['omitted_sessions'] = max(0, len(all_sessions) - args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 4 if args.session and not all_sessions else (3 if result['read_denied'] else 0)


if __name__ == '__main__':
    sys.exit(main())
