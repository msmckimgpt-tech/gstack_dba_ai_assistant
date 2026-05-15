---
description: Initialize a copied ai_delegated_dev_template project for real consumer use under Codex.
argument-hint: [project name or initialization notes]
---

# /_template:init — Codex Project Initialization

Arguments: `$ARGUMENTS`

Use this after copying the template into a consumer project.

## Required Flow

1. Resolve `policy_root` as `repo/` when `repo/AGENTS.md` exists, otherwise `.`.
2. Read `FIRST_REQUEST.md`, `AGENTS.md`, `docs/PROJECT.md`, `docs/STATUS.md`, and `docs/CONVENTIONS.md`.
3. Detect leftover example/template content:
   - `unit/feature-0001-example-hello-service`
   - placeholder project names
   - template-only TODOs that should be customized
4. Prepare a concrete initialization checklist:
   - project identity and scope
   - `.aiignore`
   - domain conventions
   - first real feature unit
   - verification command to run after edits
5. If Codex is allowed to edit, apply the initialization changes requested by the user. Otherwise return a plan.

## Guardrails

- Do not delete user-created consumer files without explicit instruction.
- Keep `AGENTS.md` as the policy source of truth.
- Record assumptions in the appropriate project or feature docs.
