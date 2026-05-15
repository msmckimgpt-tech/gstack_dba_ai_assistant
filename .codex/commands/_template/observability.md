---
description: Plan or add observability evidence for a feature using the template's documentation and verification structure.
argument-hint: [feature id or observability concern]
---

# /_template:observability — Codex Observability Adapter

Arguments: `$ARGUMENTS`

## Required Flow

1. Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/CONVENTIONS.md`, and `docs/SECURITY.md`.
2. Resolve the target feature from `$ARGUMENTS` or changed paths.
3. Read the feature's `docs/{FUNCTION,TASK,REPORT,TEST,ANCHOR}.md` when present.
4. Identify the minimum useful evidence for this project:
   - logs or metrics
   - health checks
   - test output
   - failure reproduction notes
   - operational runbook notes
5. Implement or document the observability change according to current Codex mode and `AGENTS.md` §7.1.

## Guardrails

- Do not introduce external monitoring services or paid dependencies without explicit approval.
- Never log secrets, tokens, passwords, or sensitive data.
- Keep observability evidence linked from `REPORT.md` or `TEST.md`.
