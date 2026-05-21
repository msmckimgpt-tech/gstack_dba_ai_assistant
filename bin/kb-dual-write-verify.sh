#!/usr/bin/env bash
# kb-dual-write-verify.sh — TASK-0015 §2.1.3 M2 dual-write phase 의 정합 검증.
#
# ADR-0021 §Consequences 의 cross-DB audit SLA (≤0.1% target) 의 측정 도구.
# M2 dual-write 가 진행 중인 동안 MySQL `agent_memory` 측과 Postgres `agent_kb` 측의
# 5 KB 정본 row count + ContentHash + 자연키 정합을 확인.
#
# Mode:
#   --counts        row count 비교 (4 테이블) — M2 cycle 의 일상 모니터링
#   --content-hash  ContentHash 정합 검증 (rag_documents 의 (conv, scope, fact_key) 별
#                   ContentHash 가 양쪽 일치)
#   --since <ISO>   M2 시작 시점 (outside-voice Blocker B-3 의 fail rate 분모 정의)
#                   이후 INSERT 된 row 만 비교
#   --audit-sla     ADR-0021 §Consequences 의 audit INSERT 미실행 비율 측정 (M2 stress)
#   --all           위 4종 모두
#
# Skeleton (본 cycle): script structure 만. 실 실행은 M2-b 의 dual-write 활성 후.
#
# Usage:
#   bin/kb-dual-write-verify.sh --counts
#   bin/kb-dual-write-verify.sh --since 2026-05-21T00:00:00 --content-hash
#   bin/kb-dual-write-verify.sh --audit-sla --window-days 7
#
# Exit codes:
#   0 — 정합 (fail rate < 0.01% 또는 audit SLA ≤ 0.1%)
#   1 — mismatch 발견
#   2 — invalid args / 환경 부재
#
# 본 cycle (M2-a, TASK-0019): skeleton — 실 호출은 M2-b 책임.

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
MAIN_REPO_ROOT="${WRAPPER_ROOT}/repo"
ENV_FILE="${MAIN_REPO_ROOT}/.env"
[ -f "$ENV_FILE" ] || ENV_FILE="${REPO_ROOT}/.env"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
MYSQL_CONTAINER="${COMPOSE_PROJECT_NAME}-mysql-1"
PG_CONTAINER="${COMPOSE_PROJECT_NAME}-postgres-1"

env_get() {
  local var="$1" def="${2:-}"
  local val
  val="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 || true)"
  [ -z "$val" ] && val="$def"
  printf '%s' "$val"
}

MYSQL_PW="$(env_get MYSQL_ROOT_PASSWORD)"
PG_PW="$(env_get AGENT_KB_PG_PASSWORD)"
PG_USER="$(env_get AGENT_KB_PG_USER postgres)"
PG_DB="$(env_get AGENT_KB_PG_DB agent_kb)"
MYSQL_DB="$(env_get AGENT_MEMORY_DB agent_memory)"

MODE=""
SINCE=""
WINDOW_DAYS="7"
while [ $# -gt 0 ]; do
  case "$1" in
    --counts|--content-hash|--audit-sla|--all)
      MODE="${1#--}"; shift ;;
    --since)
      SINCE="$2"; shift 2 ;;
    --window-days)
      WINDOW_DAYS="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$MODE" ] || { echo "specify --counts / --content-hash / --audit-sla / --all" >&2; exit 2; }

# outside-voice REV-20260520-0007 Section C Blocker: --since default 가 .env 의
# KB_DUAL_WRITE_START_TS 에서 자동 읽기. 부재 시 fail rate 분모 폭증 (M1 부터의
# 모든 row 포함) → SLA 측정 부정확. 명시 안 됐고 .env 에도 없으면 1주일 default.
if [ -z "$SINCE" ]; then
  SINCE="$(env_get KB_DUAL_WRITE_START_TS)"
  if [ -z "$SINCE" ]; then
    SINCE="$(date -Iseconds -d '7 days ago' 2>/dev/null || date -u -v-7d '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo '')"
    [ -n "$SINCE" ] && echo "[INFO] --since not set + KB_DUAL_WRITE_START_TS empty — using 7-day window: $SINCE" >&2
  else
    echo "[INFO] --since auto-loaded from .env KB_DUAL_WRITE_START_TS: $SINCE" >&2
  fi
fi

# ============================================================================
# Skeleton functions — M2-b cycle 의 implementation 책임.
# ============================================================================

verify_counts() {
  echo "[M2-a SKELETON] --counts: 4 KB 테이블 row count 비교"
  echo "  MySQL: AgentMemoryFactEntries / Texts / RagDocuments / RagObjects"
  echo "  Postgres: fact_entries / texts / rag_documents / rag_objects"
  echo "  fail rate 분모: M2 시작 시점 이후 INSERT 된 row 만 (--since 인자 사용)"
  echo "  TODO (M2-b): docker exec 양쪽 + SELECT COUNT(*) WHERE created_at >= :since"
  return 0
}

verify_content_hash() {
  echo "[M2-a SKELETON] --content-hash: rag_documents 의 (conv, scope, fact_key) 별 ContentHash 정합"
  echo "  TODO (M2-b): MySQL SELECT ContentHash + Postgres SELECT content_hash → JOIN 매칭"
  return 0
}

verify_audit_sla() {
  echo "[M2-a SKELETON] --audit-sla: ADR-0021 §Consequences 의 cross-DB audit ≤0.1% target"
  echo "  Postgres KB write 발생 시 MySQL WebAuditEvents 에 audit row INSERT 비율 측정"
  echo "  TODO (M2-b): Postgres fact_entries.created_at >= :since 의 row 수 vs"
  echo "  TODO (M2-b): MySQL WebAuditEvents.CreatedAt >= :since AND ActionCode='kb.write' row 수"
  echo "  TODO (M2-b): miss_rate = 1 - (audit_count / write_count). target ≤ 0.001."
  return 0
}

case "$MODE" in
  counts)        verify_counts ;;
  content-hash)  verify_content_hash ;;
  audit-sla)     verify_audit_sla ;;
  all)
    verify_counts
    verify_content_hash
    verify_audit_sla
    ;;
esac

echo "kb-dual-write-verify (mode=${MODE}, since=${SINCE:-<not set>}): M2-a SKELETON — 실 검증은 M2-b dual-write 활성 후"
exit 0
