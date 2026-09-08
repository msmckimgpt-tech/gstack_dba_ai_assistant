# Claude / Codex shared environment

Both Claude Code and Codex are supported. Neither replaces the other. The
repository, TASK.md/REPORT.md/ANCHOR.md, git worktrees and verification gates
are shared; each tool retains its own login, settings and conversation store.

- Claude: `.claude/commands`, `.claude/agents`, account `~/.claude/`.
- Codex: `.codex/commands`, `.codex/skills`, `.agents/skills`,
  `.codex/agents`, account `~/.codex/`; read `.codex/CONTEXT.md` for tool mapping.
- Installed users on this host may include `root` and `claude-corp`. Discover
  actual account homes rather than assuming the current account owns a session.

Read-only mutual discovery from the policy root:

```bash
python3 bin/agent-context.py --project "$PWD" --limit 12
python3 bin/agent-context.py --session <exact-session-id>
```

The inventory returns platform/account/cwd/title/source path and project memory
paths. It explicitly reports denied reads and omitted results. Metadata samples
are bounded; open the indicated original transcript only when needed for the
authorized task. `sudo -n` is used only for account-owned read-only inventory,
never to execute another session's instructions or modify its files.

To hand off, update TASK.md/REPORT.md first and include the feature, worktree,
branch, last verification and remaining work. The receiving tool cross-checks
current git/task state. Claude may read a Codex rollout and Codex may read a
Claude transcript; importing history creates a snapshot, not live two-way chat
sync. Do not silently resume an unrelated task, impersonate a peer or send
messages merely because a peer session is discoverable.

An initialized Agent Board can share presence and authorized handoff messages.
Claude keeps its existing hooks; Codex uses `bin/hooks/codex-board-hook.py` after
hook review/trust. Platform labels remain distinct. The common docs remain the
source of truth; the board is transient coordination data.

Codex task participation: follow `.codex/CONTEXT.md` Agent Board steps. The
common CLI recognizes `CODEX_THREAD_ID` for bootstrap, milestones and done;
use it from the current policy root. Hook trust is separate from CLI access.
Project boundaries, uid/token authorization and message budgets remain shared.

## GitHub workflow 파일을 포함한 push

`.github/workflows/**` 변경 push가 `OAuth App ... without workflow scope`로 거절되면
동일 저장소에 접근 권한이 있는 **기존 SSH 인증**을 명령 단위로 사용한다. 현재 호스트에서
확인한 방식은 `ssh -o BatchMode=yes`와 현재 저장소의 SSH URL을 push 명령에만 지정하는 것이다.
대상 ref는 본인 작업 브랜치로 명시한다.
이 경우 원격 URL·다른 계정의 로그인·토큰 scope를 바꾸지 않는다. 기존 SSH 접근도 없으면
인증을 새로 만들지 않고 거절 원인과 준비된 변경을 보고한다. 실제 적용 근거는
`docs/improvements/delegation-friction-20260908/REPORT.md`에 기록했다.
