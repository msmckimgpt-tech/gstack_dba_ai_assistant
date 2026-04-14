#!/usr/bin/env bash
set -euo pipefail

mkdir -p .ai-runtime

{
  echo "# Repository triage signals"
  echo
  echo "## Open follow-up issues"
  gh issue list --state open --label "needs-followup" --limit 20 \
    --json number,title,url,labels \
    --jq '.[] | "- #\(.number) \(.title) | \(.url)"' || true
  echo
  echo "## Open blocked issues"
  gh issue list --state open --label "status:blocked" --limit 20 \
    --json number,title,url \
    --jq '.[] | "- #\(.number) \(.title) | \(.url)"' || true
  echo
  echo "## Open pull requests"
  gh pr list --state open --limit 20 \
    --json number,title,url,labels \
    --jq '.[] | "- PR #\(.number) \(.title) | \(.url)"' || true
  echo
  echo "## Recent failed workflow runs"
  gh api "repos/${GH_REPO}/actions/runs?per_page=20" \
    --jq '.workflow_runs[] | select(.conclusion == "failure") | "- \(.name) | \(.display_title) | \(.html_url)"' \
    | head -n 10 || true
  echo
  echo "## docs/STATUS.md excerpt"
  sed -n '1,120p' docs/STATUS.md 2>/dev/null || true
} > .ai-runtime/triage_signals.md
