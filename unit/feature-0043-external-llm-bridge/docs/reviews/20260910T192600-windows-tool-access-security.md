# Windows Codex transport — security

- Related TASK: TASK-20260910-windows-tool-access
- Trigger: Windows native 조사 전송·인증 경계·회귀
- Timestamp: 2026-09-10T19:38:00+09:00
- Verdict: PASS
- Human Approval Needed: no (코드 검토)
- Source: bundle-only 독립 reviewer 최종 출력. bundle line은 해당 검토 시점 스냅샷 기준.

### 1. Blocking issues

(no findings)

### 2. Cross-domain concerns

(no findings)

### 3. Challenge to current spec

The remaining assumption is compatibility with the external machine’s managed policy. The Windows fixture validates shell-independent MCP calls, but cannot establish that policy outcome or successful FGT extraction for jgkim2. Keep those limitations explicit. In `unit/feature-0043-external-llm-bridge/src/agent/invoke.py::_codex_mcp_ca` (bundle lines 967–1001), the final implementation preserves both certificate labels and trust-purpose data, excludes private keys from generated bundles, and retains task-local cleanup. The accompanying pinned-certificate and trusted-certificate regressions address the identified preservation risks.

### 4. Verdict

**PASS** — No demonstrated security defect in the final supplied implementation; credentials, authorization boundaries, certificate verification, and transport isolation remain intact.
