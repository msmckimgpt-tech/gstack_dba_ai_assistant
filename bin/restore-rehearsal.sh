#!/usr/bin/env bash
# =============================================================================
# restore-rehearsal.sh — feature-0015 (⑤): 백업 복원 가능성 정기 리허설.
#
# **feature-0039 이후: 본 파일은 수동 실행용 얇은 래퍼다.** 실제 리허설 로직은 컨테이너
# 안의 `/app/scripts/ops_restore_rehearsal.sh` 에 있고, 정기 실행은 호스트 root crontab
# 이 아니라 `ops-scheduler` 서비스가 담당한다(매주 일 03:30).
#
# 백업은 '복원될 때만' 백업이다. 최신 백업 산출물을 **throwaway DB**
# (agent_kb_rehearsal_<ts> / agent_memory_rehearsal_<ts>)로 복원해 객체 수를 검증하고
# 즉시 DROP 한다. **프로덕션 DB(agent_kb / agent_memory)는 절대 건드리지 않는다.**
#
# 사용: bin/restore-rehearsal.sh [--backup <dir>]   (컨테이너 경로 /artifacts/backups/<ts>/)
# Exit: 0 복원 검증 PASS / 1 FAIL / 2 usage 또는 ops-scheduler 컨테이너 부재.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
CONTAINER="${OPS_SCHEDULER_CONTAINER:-${COMPOSE_PROJECT_NAME}-ops-scheduler-1}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: ops-scheduler 컨테이너가 실행 중이 아닙니다 ($CONTAINER)." >&2
  echo "  먼저: docker compose up -d ops-scheduler   (또는 make deploy-workers)" >&2
  exit 2
fi

exec docker exec "$CONTAINER" /bin/bash /app/scripts/ops_restore_rehearsal.sh "$@"
