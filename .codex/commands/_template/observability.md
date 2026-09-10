---
description: "기능의 동작과 장애 원인을 확인할 수 있도록, 필요한 로그·지표와 확인 방법을 설계하거나 추가합니다."
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
