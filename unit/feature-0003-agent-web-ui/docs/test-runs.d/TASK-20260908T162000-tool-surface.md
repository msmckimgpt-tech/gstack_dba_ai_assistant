# TASK-20260908T162000-tool-surface

## Local regression

- Timestamp: 2026-09-08T08:03:31.170056+00:00; base 2dede457 + task diff.
- Result: 717 PASS, 55 existing deprecation warnings (11.00s).
- Environment: local Python; DB_PORT/AGENT_KB_PG_PORT/AGENT_KB_PG_PORT_RO=1, runtime settings snapshot isolated under /tmp. No production database writes.
- Coverage: actual FastAPI path resolution/scoped tool dispatch; current revoked product/conversation; SQL disabled flag; whole catalog classification; core MySQL search/Agent schedule/explain input; MCP1/2 SDK HTTP+stdio import and argument transport; existing feature0041 full suite and bridge UX/heartbeat/prompt layer/KB regression.
- Independent panels: backend/security/qa PASS. Initial defects and counterexamples are in reviews/20260908T162000-tool-surface-*.md.
- Navigation: ROUTEMAP regenerated for get_tool_catalog; codenav-lint PASS. No app layout or interactive UI asset changes.

## Deployment

- Code PR #1635 merged; deployed commit ca3fe660. Canonical bin/deploy-web.sh scope=all exited 0 on 2026-09-08 (web rollout began 17:09 KST).
- Main had unrelated dirty paths, so built/deployed from clean detached sibling deploy-tool-audit-ca3fe660 with COMPOSE_PROJECT_NAME=repo. Existing secret files were linked without printing contents; shared artifacts paths stayed unchanged.
- web-a/b, ext-tool-mcp-a/b, insight-worker, ask-worker, ops-scheduler: all seven healthy and image/environment commit ca3fe660. 90-second soak PASS. ask-worker and temporary surge drained in 3 seconds each; surge removed. This does not establish zero loss for every edge request.
- All seven deployed containers: eight catalog checks each, 56 PASS (12 exposed + 9 restricted, exact handler classification, five new read tools, complete routine/SQL arguments, attachment alternative, DB_NAME guard guidance). These are in-process checks of deployed modules, not new AI answers.
- Actual installed MCP SDK on ext-tool-mcp-a registered 16 MCP tools, including get_tool_catalog and run_read_tool. SDK1/2 HTTP+stdio argument execution was covered by local regressions.
- Actual task/account/current conversation/product authorization: get_tool_catalog 200; unbound datasource 403; update_attachment 404 with attachment-edit/submit_answer alternative. Separate probe process suppressed ledger/step/lease writes only; ownership and access checks used real implementations. No bearer login or new token was created.
- Actual search_routines reached the datasource connection path, then returned HTTP500 with SQL Server connection timeout (DB-Lib 20009). TCP probes from the new web container, pre-rollout worker build 8f1116cf, and host all timed out against the configured endpoint. Docker subnets do not overlap the target. This is independent of the fixed tool-not-exposed 404; exact network/server cause remains undetermined. Routine definition/object/plan result verification was NOT-RUN after the failed connection. Product binding, endpoint, credentials and firewall were not changed.
- Canonical conversation smoke confirmed server-side LLM disabled by the existing BYO-AI gate. It did not generate a user AI response and is not counted as an answer success.
- Probe artifacts: /tmp/tool-audit-deploy.log, /tmp/tool-audit-runtime-results.json, /tmp/tool-audit-live-contract.log, /tmp/tool-audit-live-readonly.log. Durable evidence is summarized here; temporary logs are not a source of credentials or DB definitions.

## Actual user conversation

NOT-RUN new user AI generation or DQA window. Existing conversation source and task-linked audit records read only. Original conversation/attachments unchanged.

Corroboration SELECT on the PostgreSQL replica at 2026-09-08 17:19:22+09: the source conversation has zero new assistant turns since both the earlier attachment deployment (15:27:43) and this tool rollout (17:09:21). Thirty-day search_routines + 404/미제공 mentions remain one distinct conversation. No post-fix sample exists; status is fixed:deployed:unverified-live, not verified. Remaining acceptance: restore the configured DB connection, then verify routine search/definition and a new user-owned AI review in DQA.

## Documentation surface
Environment: DQA-client
Result: NOT-RUN
Reason: 변경된 static/ai-api-guide.md는 API 사용법 문서이며 앱 레이아웃/상호작용은 변경하지 않았다. 도구 제공 여부는 HTTP 라우팅과 MCP 실행으로 검증했다. 실제 DQA 창에서 새 AI 답변은 미실측이며 배포 경로 검증과 구분한다.
