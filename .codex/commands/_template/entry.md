---
description: Prime ai_delegated_dev_template policy context, then dispatch the provided request under Codex-compatible guardrails.
argument-hint: [actual request text]
---

# /_template:entry — Codex Bootstrap + Dispatch Adapter

Arguments: `$ARGUMENTS`

This is the Codex-owned counterpart of Claude Code's `/_template:entry`.
It preserves the same user-facing intent while using Codex-native behavior.

## Required Flow

1. Resolve `policy_root` as a directory:
   - If `repo/AGENTS.md` exists from the current workspace wrapper, set `policy_root=repo`.
   - Otherwise, if `./AGENTS.md` exists, set `policy_root=.`.
   - If neither exists, stop and state that this command only works in an `ai_delegated_dev_template` project.
2. Read the policy context in priority order:
   - `<wrapper>/FIRST_REQUEST.md` when present.
   - `<policy_root>/AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`.
   - `<policy_root>/docs/{PROJECT,STATUS,ARCHITECTURE,CONVENTIONS,SECURITY,REQUEST}.md` when present.
   - `<policy_root>/playbooks/README.md` when present.
   - `<policy_root>/meta/{TASK,REVIEW}.md` when present.
3. Enumerate, but do not fully read unless needed:
   - `<policy_root>/.codex/commands/_template/*.md`
   - `<policy_root>/.codex/skills/_template-*/SKILL.md`
   - `<policy_root>/.claude/commands/_template/*.md`
   - `<policy_root>/.claude/agents/*.md`
4. If `$ARGUMENTS` is empty, stop after context priming and ask for the session request in one sentence.
5. If `$ARGUMENTS` is present, classify scope and continue the work in the same turn.

## Codex Guardrails

- Follow current system/developer mode. If Codex is in Plan Mode, produce a plan only. Otherwise execute the request.
- For non-trivial work, apply `AGENTS.md` §7.1 Plan-Review-Execute before edits.
- For feature-scoped work, read that feature's `docs/{AGENTS,FUNCTION,TASK,REPORT,ANCHOR}.md` when present.
- If `ANCHOR.md` conflicts with the request, stop and surface the conflict before implementation.
- For completion, use the repository verification protocol (`bin/verify-completion.sh`, `/review`, or the documented panel flow) that matches the changed paths.
- Do not treat this command as a replacement for `AGENTS.md`; it is only a context/bootstrap adapter.
