#!/usr/bin/env bash
# kb-backfill.sh — M3 (TASK-0023) MySQL → Postgres backfill wrapper.
#
# 본 wrapper 는 agent 컨테이너 안의 `scripts/kb_backfill.py` 를 docker exec 으로
# 실행. 멱등 + resumable + dry-run 지원. state file 은 호스트의 artifacts/shared/
# 에 작성 (재실행 시 progress 보존).
#
# Usage:
#   bin/kb-backfill.sh --dry-run                          # 모두 dry-run
#   bin/kb-backfill.sh --table texts --batch-size 500
#   bin/kb-backfill.sh --since 2026-05-20T00:00:00
#   bin/kb-backfill.sh --reset-state                      # 처음부터
#
# Exit codes:
#   0 — 모든 backfill 완료
#   1 — 일부 table 실패 (state file 에서 재진입 가능)
#   2 — invalid args / 환경 부재

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER_A="$(dirname "$REPO_ROOT")"
WRAPPER_B="$(dirname "$WRAPPER_A")"
if [ -d "${WRAPPER_A}/repo" ] && [ -f "${WRAPPER_A}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_A"
elif [ -d "${WRAPPER_B}/repo" ] && [ -f "${WRAPPER_B}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_B"
else
  WRAPPER_ROOT="$WRAPPER_A"
fi
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
AGENT_CONTAINER="${COMPOSE_PROJECT_NAME}-agent-1"

# state file 디렉터리 — 컨테이너 /shared 마운트 == 호스트 artifacts/shared.
SHARED_DIR="${WRAPPER_ROOT}/artifacts/shared"
mkdir -p "$SHARED_DIR"

if ! docker ps --format '{{.Names}}' | grep -qx "$AGENT_CONTAINER"; then
  echo "ERROR: agent container '${AGENT_CONTAINER}' not running" >&2
  echo "  먼저 'make start' 또는 docker compose up agent" >&2
  exit 2
fi

# `python -m scripts.kb_backfill` — agent container 의 PYTHONPATH 가 /app/src 인 경우.
exec docker exec \
  -e AGENT_KB_BACKFILL_STATE_DIR=/shared \
  "$AGENT_CONTAINER" \
  python -m scripts.kb_backfill "$@"
