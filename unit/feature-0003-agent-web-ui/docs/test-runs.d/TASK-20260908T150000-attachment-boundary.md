# TASK-20260908T150000-attachment-boundary

## Run — unit/integration seam
Environment: local Python, DB_PORT=1 / PG ports=1, no live database mutations
Result: PASS
Scenario: edit/new → following explanation/diff → next file; mixed fences; quoted examples; successful empty message; bridge recall/worker result; storage failure and ownership regressions
Evidence: 120 passed, 19 existing deprecation warnings; 6 focused test modules; backend/security/qa PASS. Exact file body/clean answer assertions preserve SQL comments. Actual bridge delivery records empty recall content.
Revision: base 49f7fa41 + task diff; 2026-09-08T06:09:53.549929+00:00

## Run — deployed runtime
Environment: deployed web-a/web-b, ext-tool-mcp-a/b, insight-worker, ask-worker, ops-scheduler
Result: PASS
Build: e8fd398b (PR #1629), 2026-09-08T06:27:43.349266+00:00
Scenario: file-boundary + answer preservation + empty successful answer + failure notice, edit/new each
Evidence: 7 services × 8 checks = 56 PASS; delivery directive present. Main deployment script exit 0, ready + 90s soak PASS, ask primary/surge drained in 6s each; surge removed. Secret presence booleans only, all true. No pending migration.

## Run — stored file replay
Environment: web-b deployed parser + MinIO GET, database replica SELECT discovery
Result: PASS
Scenario: stored object bytes used to reconstruct attachment blocks without writing data
Evidence: original SHA matches 10/10; contaminated answer tails excluded 6/6. No database or object writes. This is a parser replay, not restoration of stored artifacts or a new AI answer.

## Live user scope
User AI regeneration and actual DQA window: NOT-RUN. This change modifies backend parsing/prompt behavior, no frontend assets; verify-completion visual gate reports no UI asset change. Deployed function execution proves server behavior, not the outcome of a new model response. Next audit can measure post-deployment recurrence; stored older versions are preserved.

