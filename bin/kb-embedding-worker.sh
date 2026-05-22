#!/usr/bin/env bash
# kb-embedding-worker.sh — M3 (TASK-0023) texts.embedding 일괄 생성 wrapper.
#
# 본 wrapper 는 agent 컨테이너 안의 `scripts/kb_embedding_worker.py` 를 docker exec
# 으로 실행. OpenAI `text-embedding-3-small` (default, .env 의 AGENT_KB_EMBEDDING_MODEL
# 로 override) batch API. resumable (WHERE embedding IS NULL 자동 skip).
#
# Usage:
#   bin/kb-embedding-worker.sh --dry-run                  # count + cost 추정
#   bin/kb-embedding-worker.sh --max-rows 5000            # cost cap
#   bin/kb-embedding-worker.sh --model text-embedding-3-large
#
# Exit codes:
#   0 — 모든 pending row 처리 또는 --max-rows 도달
#   1 — API 실패 또는 일부 row 처리 실패
#   2 — invalid args / 환경 부재 (OPENAI_API_KEY / agent container)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
AGENT_CONTAINER="${COMPOSE_PROJECT_NAME}-agent-1"

if ! docker ps --format '{{.Names}}' | grep -qx "$AGENT_CONTAINER"; then
  echo "ERROR: agent container '${AGENT_CONTAINER}' not running" >&2
  exit 2
fi

# OPENAI_API_KEY 는 agent container 의 .env 에서 자동 inherit.
exec docker exec "$AGENT_CONTAINER" \
  python -m scripts.kb_embedding_worker "$@"
