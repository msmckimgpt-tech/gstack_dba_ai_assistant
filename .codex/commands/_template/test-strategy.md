---
description: Build a focused test strategy for the current feature or change set.
argument-hint: [feature id or test concern]
---

# /_template:test-strategy — Codex Test Strategy Adapter

Arguments: `$ARGUMENTS`

## Required Flow

1. Read `AGENTS.md`, `docs/CONVENTIONS.md`, and the relevant feature docs.
2. Inspect the code paths implied by `$ARGUMENTS` or the current diff.
3. Produce or update test strategy around:
   - behavior under test
   - risk areas
   - unit/integration/manual checks
   - verification commands
4. If editing is allowed, update the feature's `docs/TEST.md` and add or adjust tests.

## Guardrails

- Prefer real executable tests over documentation-only checks when the repository has a runnable test stack.
- Do not invent passing results. Only record commands actually run.
- For database changes, include rollback/data-integrity checks appropriate to the current DB stack.
