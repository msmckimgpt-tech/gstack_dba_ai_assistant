---
description: "개발 요청이나 수정할 문제를 전달하면, 프로젝트 상황에 맞게 작업을 정리하고 구현·검증을 진행합니다."
argument-hint: [actual request text]
---

# /_template:entry — Codex Bootstrap + Dispatch Adapter

Arguments: `$ARGUMENTS`

This is the Codex-owned counterpart of Claude Code's `/_template:entry`.
It preserves the same user-facing intent while using Codex-native behavior.

<!-- inbox-autonomy:codex-entry:v1 -->
**착수 신호·정책 재독·버전 경고 (v3.54.0)**: 도구로 정책을 읽기 전에 사용자에게 목적과 첫 작업을
한 번 알리고, 도구 작업이 길어지면 진행 상태를 알린다. 빈 인사말만으로 대체하지 않는다.
진입·cycle 경계에 실제 정책 경로와 내용 SHA-256을 대조하고 변경된 규정을 재독한다.
하네스 권장 버전 미달은 안내·경고이며 시작 차단 사유가 아니다. 가용 기능·대체 수단으로 진행한다.
이전 REVIEW/TASK의 verification_debt가 있으면 복구 여부와 필요한 재검증을 확인한다.
네이티브 auto-continue와 stale 재호출의 구분은 AGENTS.md §22.12의 명시 활성 등록 계약을 따른다.

<!-- /inbox-autonomy:codex-entry:v1 -->

## Required Flow

1. Resolve `policy_root` as a directory:
   - If `repo/AGENTS.md` exists from the current workspace wrapper, set `policy_root=repo`.
   - Otherwise, if `./AGENTS.md` exists, set `policy_root=.`.
   - If neither exists, stop and state that this command only works in an `ai_delegated_dev_template` project.
2. Read `.codex/CONTEXT.md` and `.agents/ENVIRONMENT.md` in the policy root.
   Retrieve the AGENTS.md heading index and the applicable sections named by
   the context adapter; do not request the entire large policy in one read.
   AGENTS.md §10.1 is the shared reading contract. Read wrapper FIRST_REQUEST.md
   when present, then CLAUDE.md, CONTRIBUTING.md, docs/PROJECT.md and the STATUS
   index. Read current target feature documents (or the matching meta/TASK.md
   entry); load architecture, security, conventions, reviews and playbooks by
   the applicable section/path rather than copying their full history.
   For an authorized mutation from main, create the task's isolated worktree
   and continue in this session (§13.2.1); no separate session request is needed.

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
