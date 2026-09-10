---
description: "소비자 프로젝트에 최신 템플릿 변경을 반영할 때, 현재 버전과 적용할 변경을 확인하고 업그레이드를 돕습니다."
argument-hint: [--check|--dry-run --diff|--apply|--rollback]
---

# /_template:version-upgrade — Codex Template Upgrade Adapter

Arguments: `$ARGUMENTS`

## Required Flow

1. Read `AGENTS.md` and `docs/TEMPLATE_UPGRADE.md`.
2. Treat `bin/template-upgrade.sh` as canonical. This command is only a conversational wrapper.
3. Default to `--check` when `$ARGUMENTS` is empty.
4. Before mutating modes (`--apply`, `--rollback`, `--state-repair`, `--unlock-stale`):
   - inspect `git status --short`;
   - explain expected impact;
   - obey current Codex approval and Plan Mode constraints.
5. For read-only modes, run the script and summarize pending hops or diagnostics.

## Guardrails

- Do not edit migration state manually when the script has a mode for it.
- Do not use `--force` unless the user explicitly asks and the risk is documented.
- After apply/rollback, inspect `git diff` and report changed policy/tooling files.
