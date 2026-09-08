---
description: "프로젝트에서 반복하는 업무를 전용 명령으로 만들고 싶을 때, 역할과 사용법이 정리된 새 스킬을 만듭니다."
argument-hint: [persona name and purpose]
---

# /_template:persona-new — Codex Persona Factory

Arguments: `$ARGUMENTS`

## Required Flow

1. Read `AGENTS.md` §19 and the existing command/skill inventories:
   - `.codex/commands/_template/*.md`
   - `.codex/skills/_template-*/SKILL.md`
   - `.codex/commands/_persona/*.md` when present
   - `.codex/skills/_persona-*/SKILL.md` when present
   - `.claude/commands/_template/*.md`
   - `.claude/commands/_persona/*.md` when present
2. Derive a stable persona name from `$ARGUMENTS`.
3. Create project-owned artifacts only:
   - `.codex/commands/_persona/<name>.md` for Codex.
   - `.codex/skills/_persona-<name>/SKILL.md` as the Codex skill discovery wrapper.
   - `.claude/commands/_persona/<name>.md` only when Claude compatibility is requested.
4. The new persona must state:
   - purpose
   - accepted arguments
   - required reads
   - allowed edits
   - verification expectations
5. The Codex `SKILL.md` wrapper must point back to `.codex/commands/_persona/<name>.md`
   as the canonical command body and summarize when to use the persona.

## Guardrails

- Do not add project-specific behavior under `_template`; `_template` remains template-owned.
- Do not auto-chain personas. Recommend the next persona only when useful.
- If Codex is in Plan Mode, return the exact files and content to create instead of editing.
