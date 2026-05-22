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
# M2-c (TASK-0021) — 본문 구현.
# ============================================================================

verify_counts() {
  echo "[INFO] --counts: 4 KB 테이블 row count 비교 (since=${SINCE:-<all>})"
  local since_clause_mysql=""
  local since_clause_pg=""
  if [ -n "$SINCE" ]; then
    since_clause_mysql=" WHERE CreatedAt >= '$SINCE'"
    since_clause_pg=" WHERE created_at >= '$SINCE'"
  fi

  local failed_count=0
  for pair in "AgentMemoryFactEntries:fact_entries" \
              "AgentMemoryTexts:texts" \
              "AgentMemoryRagDocuments:rag_documents" \
              "AgentMemoryRagObjects:rag_objects"; do
    local my_tbl="${pair%%:*}"
    local pg_tbl="${pair##*:}"
    local my_count pg_count
    my_count=$(docker exec -i "$MYSQL_CONTAINER" mysql -uroot -p"$MYSQL_PW" \
      --skip-column-names -B -e "SELECT COUNT(*) FROM ${my_tbl}${since_clause_mysql};" \
      "$MYSQL_DB" 2>/dev/null | grep -v '^mysql:' | head -1 | tr -d '[:space:]' || true)
    pg_count=$(docker exec -i -e PGPASSWORD="$PG_PW" "$PG_CONTAINER" \
      psql -h localhost -p 5432 -U "$PG_USER" -d "$PG_DB" -tAc \
      "SELECT COUNT(*) FROM ${pg_tbl}${since_clause_pg};" 2>/dev/null | tr -d '[:space:]' || true)
    my_count="${my_count:-0}"
    pg_count="${pg_count:-0}"
    local diff=$((my_count - pg_count))
    printf '  %-30s mysql=%s  postgres=%s  diff=%d\n' "$my_tbl" "$my_count" "$pg_count" "$diff"
    if [ "$diff" -ne 0 ]; then
      failed_count=$((failed_count + 1))
    fi
  done

  if [ "$failed_count" -gt 0 ]; then
    echo "  FAIL: $failed_count tables mismatch" >&2
    return 1
  fi
  echo "  PASS: all 4 tables row count match"
  return 0
}

verify_content_hash() {
  echo "[INFO] --content-hash: rag_documents (conv, scope, fact_key) × content_hash 정합 (since=${SINCE:-<all>})"
  local since_clause_mysql=""
  local since_clause_pg=""
  if [ -n "$SINCE" ]; then
    since_clause_mysql=" AND CreatedAt >= '$SINCE'"
    since_clause_pg=" AND created_at >= '$SINCE'"
  fi

  local mysql_hashes pg_hashes
  mysql_hashes=$(docker exec -i "$MYSQL_CONTAINER" mysql -uroot -p"$MYSQL_PW" \
    --skip-column-names -B -e \
    "SELECT CONCAT(ConversationId, '|', ScopeKey, '|', IFNULL(FactKey, ''), '|', ContentHash) \
     FROM AgentMemoryRagDocuments WHERE 1=1${since_clause_mysql} ORDER BY 1;" \
    "$MYSQL_DB" 2>/dev/null | grep -v '^mysql:' | sort -u || true)
  pg_hashes=$(docker exec -i -e PGPASSWORD="$PG_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$PG_USER" -d "$PG_DB" -tAc \
    "SELECT conversation_id || '|' || scope_key || '|' || COALESCE(fact_key, '') || '|' || content_hash \
     FROM rag_documents WHERE TRUE${since_clause_pg} ORDER BY 1;" 2>/dev/null | sort -u || true)

  local only_mysql only_pg
  only_mysql=$(comm -23 <(printf '%s\n' "$mysql_hashes") <(printf '%s\n' "$pg_hashes") | wc -l | tr -d ' ')
  only_pg=$(comm -13 <(printf '%s\n' "$mysql_hashes") <(printf '%s\n' "$pg_hashes") | wc -l | tr -d ' ')
  echo "  mysql_only=${only_mysql}  postgres_only=${only_pg}"
  if [ "$only_mysql" -ne 0 ] || [ "$only_pg" -ne 0 ]; then
    echo "  FAIL: rag_documents content_hash divergent" >&2
    return 1
  fi
  echo "  PASS: rag_documents content_hash full match"
  return 0
}

verify_audit_sla() {
  # M2-c (TASK-0021) 본문 — ADR-0021 §Consequences ≤0.1% miss_rate target 측정.
  #
  # outside-voice REV-20260521-0009 B-1 흡수: 이전 분모/분자 mismatch 정정 —
  # 1. PG denominator 는 fact_entries / rag_documents / rag_objects 의 INSERT+UPDATE
  #    모두 포함하도록 `GREATEST(created_at, updated_at) >= since` 사용. texts 는
  #    INSERT ON CONFLICT DO NOTHING (UPDATE branch 없음) 이라 created_at 만 사용.
  # 2. audit numerator 는 `kb.write.mirror` 만 — `kb.delete.mirror` /
  #    `kb.prune.mirror` 는 row count 감소 이벤트라 "rows present" denominator 와
  #    비교 불가. delete/prune SLA 는 M2-d cycle 의 별 metric 책임.
  # 3. `audit_count > pg_write_count` 이면 audit over-count 의 진짜 bug → 음수 ppm
  #    이 silent PASS 가 되지 않도록 fail-loud.
  # 4. **methodology limitation**: 같은 row 가 window 안에서 N 번 UPDATE 되면 PG
  #    는 1 row 로 count 되지만 audit 는 N 행. 정밀 매칭은 pg_branch tagging
  #    (xmax=0 기반) 의 M2-d 후속 cycle 책임. 본 cycle 은 stress run 의 traffic 이
  #    insert-heavy 라는 전제 (3 insight × ~30 fact + 25 ask 의 대부분 신규 row)
  #    하에서 ≤2x slack 을 적용.
  echo "[INFO] --audit-sla: ADR-0021 §Consequences ≤0.1% miss_rate target (since=${SINCE:-<all>})"
  if [ -z "$SINCE" ]; then
    echo "  ERROR: --since 또는 .env KB_DUAL_WRITE_START_TS 필수 (분모 정의)" >&2
    return 1
  fi

  local pg_write_count
  pg_write_count=$(docker exec -i -e PGPASSWORD="$PG_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$PG_USER" -d "$PG_DB" -tAc "
      SELECT
        (SELECT COUNT(*) FROM fact_entries   WHERE GREATEST(created_at, updated_at) >= '$SINCE')
        + (SELECT COUNT(*) FROM rag_documents WHERE GREATEST(created_at, updated_at) >= '$SINCE')
        + (SELECT COUNT(*) FROM rag_objects   WHERE GREATEST(created_at, updated_at) >= '$SINCE')
        + (SELECT COUNT(*) FROM texts         WHERE created_at >= '$SINCE')
    " 2>/dev/null | tr -d '[:space:]' || true)
  pg_write_count="${pg_write_count:-0}"

  # outside-voice B-1: kb.write.mirror 만 (delete/prune 제외 — denominator 와 비교 불가)
  local audit_count
  audit_count=$(docker exec -i "$MYSQL_CONTAINER" mysql -uroot -p"$MYSQL_PW" \
    --skip-column-names -B -e \
    "SELECT COUNT(*) FROM WebAuditEvents \
     WHERE ActionCode = 'kb.write.mirror' \
       AND OccurredAt >= '$SINCE';" \
    "$MYSQL_DB" 2>/dev/null | grep -v '^mysql:' | head -1 | tr -d '[:space:]' || true)
  audit_count="${audit_count:-0}"

  echo "  pg_write_count=${pg_write_count}  audit_count=${audit_count}  (scope: kb.write.mirror only)"

  if [ "$pg_write_count" -eq 0 ]; then
    # outside-voice C-8 흡수: zero-denominator 는 inconclusive — PASS 가 아닌 exit 2.
    echo "  INCONCLUSIVE: pg_write_count=0 (since=${SINCE}) — SLA 측정 분모 부족." >&2
    echo "  더 긴 window 또는 stress run 후 재시도. CI green-light 방지를 위해 exit 2." >&2
    return 2
  fi

  # outside-voice B-1: audit over-count 가 silent PASS 되지 않도록 명시 검출.
  # methodology limitation 으로 같은 row N-times update 의 경우 audit > pg 가능 —
  # 단 ≤2x 까지만 acceptable. 이를 초과하면 over-instrumentation 의 진짜 bug.
  if [ "$audit_count" -gt "$((pg_write_count * 2))" ]; then
    echo "  FAIL: audit_count (${audit_count}) > 2 × pg_write_count (${pg_write_count})" >&2
    echo "  audit over-count 의 bug 또는 same-row repeated update 의 극단치 — 조사 필요" >&2
    return 1
  fi

  # miss_ppm 계산 — audit_count > pg_write_count 의 경우 0 으로 clamp (PG side 가
  # missing 이 아니라 update branch 의 노이즈로 간주).
  local miss_ppm
  if [ "$audit_count" -ge "$pg_write_count" ]; then
    miss_ppm=0
    printf '  miss_rate = max(0, (%d - %d) / %d) = 0 ppm (audit≥pg — update branch 영향)\n' \
      "$pg_write_count" "$audit_count" "$pg_write_count"
  else
    miss_ppm=$(( (pg_write_count - audit_count) * 1000000 / pg_write_count ))
    printf '  miss_rate = (%d - %d) / %d = %d ppm\n' \
      "$pg_write_count" "$audit_count" "$pg_write_count" "$miss_ppm"
  fi
  local target_ppm=1000  # 0.1%
  printf '  target ≤ %d ppm\n' "$target_ppm"

  if [ "$miss_ppm" -gt "$target_ppm" ]; then
    echo "  FAIL: miss_rate ${miss_ppm} ppm > target ${target_ppm} ppm" >&2
    echo "  hard alert + M2 cycle rollback 결정 (ADR-0021 §Consequences)" >&2
    return 1
  fi
  echo "  PASS: miss_rate ${miss_ppm} ppm ≤ ${target_ppm} ppm"
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
