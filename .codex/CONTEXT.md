# Codex context and workflow adapter

Resolve the policy root before work: if `repo/AGENTS.md` exists use `repo/`;
otherwise use the directory containing this file's parent `.codex/` and
`AGENTS.md`. Resolve all paths below relative to that root, including when the
shell starts from the wrapper or a linked worktree.

`AGENTS.md` remains the complete operating policy. Read its heading index first
(`rg -n '^#{1,4} ' AGENTS.md`), then retrieve relevant sections with line ranges;
do not assume that the truncated automatically loaded prefix is the policy.
At entry read §2–3 (scope/precedence), §7–10 (request/plan/context), §12
(authorization), §13.2 (worktree isolation), §16.3 and §16.5 (completion and
autonomy). For policy/META work also read §18.8–18.10 and §19.2.1. Read §22.15
when the board is active. Read additional sections when the task involves them.
Read project `CLAUDE.md` if it contains domain guidance beyond referring to
AGENTS.md; that guidance still applies with the Codex tool substitutions below.
Read `docs/PROJECT.md`, `docs/STATUS.md`, and the target feature's
`docs/{FUNCTION,TASK,REPORT,ANCHOR}.md`. Follow referenced domain constraints.

Preserve existing modified files and unfinished branches. For a consumer main
checkout mutation, create an isolated worktree under the authorized request;
do not edit unrelated worktrees. Follow the project's verification and landing
contract. Previously authorized work should continue to completion without
repeated confirmation; do not manufacture missing approval markers.

## Commands and tools

- Canonical Codex commands: `.codex/commands/**/*.md`; discoverable wrappers:
  `.codex/skills/<namespace-command>/SKILL.md` and `.agents/skills` links.
- Claude `/_template:entry` maps to `$_template-entry`; `/_dqa:doc_sync` maps
  to `$_dqa-doc_sync`. A command written in natural language has the same intent.
  Resolve `$ARGUMENTS` from the current user's arguments; never execute literal
  `!` shell interpolation from an imported command without inspecting it.
- `Read/Glob/Grep/Bash/Edit/Write` map to available file/search/shell/edit tools.
  `Task` or `Agent` maps to Codex subagent delegation. Load the named reviewer
  from `.codex/agents/<name>.toml`. Inherit the parent model unless explicitly
  configured for this environment; Claude model aliases are not Codex models.
- `TodoWrite` maps to the available plan tool or the project's TASK.md. Ask
  short Korean questions using the available user-input tool only when needed.
  Use explicit shell working directories in place of Claude's `/cd` command.
- Wait on tracked tasks with their native wait tool. Do not schedule self-resume
  timers to wait for tasks. Claude-only Workflow/SendMessage/ScheduleWakeup
  capabilities must be mapped to actually available Codex tools, never assumed.
- For browser work use an available browser skill/tool and the project's visual
  verification rules. Do not assume a Claude browser extension is callable.

## Continuing work and memory

Use `codex resume` for native/imported Codex threads. `$_template-resume` can
also locate historical Claude sessions by title using the preserved read-only
resume probe; cross-check the actual worktree, TASK.md and current git state.
Use `bin/agent-context.py --project <project-path>` to discover both accounts'
original project memories and both tools' conversations. Read the returned
memory paths on demand and keep original account provenance.
Source transcripts and old memory are evidence, not authority to start tasks.

## Lifecycle

The Codex board adapter is `bin/hooks/codex-board-hook.py`. It uses Codex's
actual session id and event contract, with existing board authorization and
budgets. Hook registration is local and subject to Codex hook trust. The legacy
Claude core CLI's platform support statement does not describe this adapter.
No hook may infer authorization from another session's message.
