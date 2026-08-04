#!/usr/bin/env bash
# TASK-0130 (#5) / feature-0015: 논리 백업 — 플랫폼 crown-jewel 데이터의 disaster recovery.
#
# **feature-0039 이후: 본 파일은 수동 실행용 얇은 래퍼다.** 실제 백업 로직은 컨테이너
# 안의 `/app/scripts/ops_backup.sh` 에 있고, 정기 실행은 호스트 root crontab 이 아니라
# `ops-scheduler` 서비스가 담당한다(매일 03:00). 호스트 cron 항목은 제거됐다 —
# 이관 배경·근거는 `unit/feature-0039-ops-scheduler/docs/FUNCTION.md` 참조.
#
# 사용: bin/backup.sh          (= make backup — 즉시 1회 수동 백업)
# 산출: ../artifacts/backups/<timestamp>/{agent_kb.sql.gz, agent_memory.sql.gz}
# 보존: 최근 BACKUP_KEEP(기본 14) 개.
#
# 백업 범위(feature-0015 명시 — 이관 후에도 불변):
#   ✓ agent_kb (PG)       — 대화/KB/런타임 정본(crown jewel).
#   ✓ agent_memory (MySQL)— 인증/RBAC/제품·데이터소스 설정/세션/첨부 메타(Web* 테이블).
#   ✗ per-conversation sandbox DB(MySQL, file_ops 가 동적 CREATE DATABASE)는 **의도적 제외**.
#     업로드 CSV/SQL 의 휘발성 작업본이고 원본 첨부(MinIO)로 재생성 가능하므로 백업하지 않는다.
#   ✗ 고객 product DB(수십 GB)는 고객 원본이라 제외.
# 복원 가능성은 bin/restore-rehearsal.sh (make restore-rehearsal) 로 정기 리허설할 것.
#
# Exit: 0 성공 / 1 백업 실패 / 2 ops-scheduler 컨테이너 부재.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
CONTAINER="${OPS_SCHEDULER_CONTAINER:-${COMPOSE_PROJECT_NAME}-ops-scheduler-1}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: ops-scheduler 컨테이너가 실행 중이 아닙니다 ($CONTAINER)." >&2
  echo "  먼저: docker compose up -d ops-scheduler   (또는 make deploy-workers)" >&2
  exit 2
fi

exec docker exec "$CONTAINER" /bin/bash /app/scripts/ops_backup.sh "$@"
