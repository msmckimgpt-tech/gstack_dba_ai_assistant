---
description: "빌드·실행·테스트 명령을 간편하게 쓰고 싶을 때, 프로젝트에 맞는 Makefile을 작성합니다."
argument-hint: [makefile intent — optional]
---

# /_template:makefile — Codex Makefile Factory

Arguments: `$ARGUMENTS`

User-invoked only. AGENTS.md §20 (Makefile 권유 정책) defines the trigger policy; AI must not auto-chain into this command.

## Required Flow

1. Read AGENTS.md §20 (Makefile 권유 정책), §18 (ANCHOR — Makefile/ARCHITECTURE.md row), §19.6 (권유-only 원칙), §19.7 (scope: project-agnostic).
2. Probe consumer state:
   - `repo/Makefile` existence (if present, ask before overwrite).
   - `repo/.template/MAKEFILE_DECLINED` or `docs/DECISIONS.md` ADR "Makefile 불채택" — if either present, halt + re-confirm before proceeding (AGENTS.md §20.2.1 opt-out).
   - Signal scan (read-only): grep for `bash …`, `npm …`, `python …`, `docker …`, `make …` patterns across `README.md`, `FIRST_REQUEST.md`, `docs/PROJECT.md`, and `unit/feature-*/scripts/*.sh`.
3. Q&A (sequential, follow-up at most once per question if ambiguous):
   - **Q1 — Entry-point inventory**: one command per line.
   - **Q1.5 — Shell-injection sanity check** (mandatory per AGENTS.md §20.4): echo collected commands back to user with a one-line warning that recipe lines are evaluated by `/bin/sh -c` and metachars (`;`, `&&`, `|`, backticks, `$()`, `>`, `&`) are active. Require explicit confirm. Skip not allowed.
   - **Q2 — Target naming / grouping**: `target_name: <original command>` per line. Recommend `up`/`down`/`build`/`test`/`clean`/`<feature>-<verb>`/`help`.
   - **Q3 — Target dependencies** (optional): which targets depend on others; `none` if not applicable.
   - **Q4 — Extras** (optional): `help` auto-output, `phony` declarations, `default` goal, `env-check` target, free-text others. Also `permanently skip` branch — touch `repo/.template/MAKEFILE_DECLINED` and exit without writing Makefile.
4. Assemble `repo/Makefile`:
   - `.DEFAULT_GOAL := <Q4.default or help>`
   - `.PHONY: <…>` if Q4.phony selected (or always — recommended).
   - Per-target body with `## <comment>` for help integration.
   - `help` target body using `grep -E '^[a-zA-Z_-]+:.*?##'` + `awk` pattern.
   - Header comment: reference AGENTS.md §20 + ARCHITECTURE anchor.
5. Display assembled body to user, then write to `repo/Makefile`. Also touch `repo/.template/makefile-hint-shown` to prevent re-recommendation (AGENTS.md §20.2.1).
6. Offer anchor table activation (AGENTS.md §20.4): the `Makefile | docs/ARCHITECTURE.md | 실행 진입점` row is commented in template-base anchor table. Ask whether to uncomment for this consumer; act only on explicit confirm.

## Guardrails

- Project-agnostic: do not assume specific feature names. Use only entries user provided in Q1.
- Single output: exactly one `repo/Makefile`. No other file mutations unless user explicitly confirms anchor-table activation in step 6.
- Overwrite policy: if `repo/Makefile` exists, halt and ask before overwriting.
- HUMAN-LOCKED: do not touch any `HUMAN-LOCKED` regions in AGENTS.md / docs.
- No auto-chain: after writing the Makefile, suggest `make help` and ADR-via-DECISIONS.md for future target changes; do not invoke other commands automatically.
- Plan Mode: if Codex is in Plan Mode, return the exact `repo/Makefile` content the user would write instead of editing.
