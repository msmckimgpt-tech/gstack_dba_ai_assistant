#!/usr/bin/env bash
#
# cleanup-empty-conversations.sh — 메시지가 0건인 빈 대화 row 를 일괄 정리.
#
# 설계 근거: TASK-0049 (REQ-20260506-0002) — TASK-0048 의 lazy 화 이전에 누적된 빈
# 대화 row 들을 일회성으로 정리한다. TASK-0048 이후엔 신규 누적이 차단되므로 본 스크립트는
# 한 번 실행하면 충분 (또는 정기 cron 으로 옵션).
#
# 보호 규칙 (§12.1 destructive 작업):
#  - 메시지가 0건인 대화만 대상.
#  - `AgentMemoryKv.last_status='processing'` 인 대화는 제외 (실행 중 ask race 보호).
#  - dry-run 이 기본. `--execute` 명시 없이는 DELETE 하지 않는다.
#  - `--owner-account-id <N>` 으로 특정 계정 한정 가능 (생략 시 전체 — admin 용도).
#  - `--keep-recent-min <분>` 으로 최근 N분 이내 created_at 대화는 보호 (default: 5).
#
# Usage:
#   bin/cleanup-empty-conversations.sh                                   # dry-run 전체
#   bin/cleanup-empty-conversations.sh --owner-account-id 1              # dry-run, 계정 1 한정
#   bin/cleanup-empty-conversations.sh --execute                         # 실제 삭제 (전체)
#   bin/cleanup-empty-conversations.sh --execute --owner-account-id 1    # 실제 삭제 (계정 1)
#   bin/cleanup-empty-conversations.sh --keep-recent-min 30 --execute    # 최근 30분 보호
#
# Requires: docker compose 가 동작 중이고 mysql 서비스가 healthy 여야 함.

set -euo pipefail

DRY_RUN=1
OWNER_FILTER_SQL=""
KEEP_RECENT_MIN=5

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      DRY_RUN=0; shift ;;
    --owner-account-id)
      if [[ -z "${2:-}" ]]; then echo "--owner-account-id 에 정수가 필요합니다." >&2; exit 2; fi
      if ! [[ "$2" =~ ^[0-9]+$ ]]; then echo "--owner-account-id 는 정수여야 합니다." >&2; exit 2; fi
      OWNER_FILTER_SQL="AND c.owner_account_id = $2"
      shift 2 ;;
    --keep-recent-min)
      if [[ -z "${2:-}" ]]; then echo "--keep-recent-min 에 정수(분)가 필요합니다." >&2; exit 2; fi
      if ! [[ "$2" =~ ^[0-9]+$ ]]; then echo "--keep-recent-min 는 정수여야 합니다." >&2; exit 2; fi
      KEEP_RECENT_MIN="$2"
      shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0 ;;
    *)
      echo "알 수 없는 옵션: $1" >&2
      exit 2 ;;
  esac
done

# 보안: SQL 주입 방지 — OWNER_FILTER_SQL 와 KEEP_RECENT_MIN 는 위에서 정수 검증 완료.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

# DB password 는 .env 의 DB_PASSWORD 에서 읽는다 — git 추적 대상이 아닌 값.
DB_PASSWORD=$(sed -n 's/^DB_PASSWORD=//p' .env | tail -n 1)
if [[ -z "$DB_PASSWORD" ]]; then
  echo "ERROR: .env 의 DB_PASSWORD 를 읽지 못했습니다." >&2
  exit 2
fi

# 공통 WHERE 조건: 메시지 0건 + last_status≠'processing' + created_at 이 최근 N분 이전.
# AgentCoreConversations 와 AgentMemoryMessages 의 collation 이 다를 수 있어 명시 변환.
WHERE_CLAUSE="
WHERE NOT EXISTS (
    SELECT 1 FROM AgentMemoryMessages m
    WHERE m.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci
  )
  AND NOT EXISTS (
    SELECT 1 FROM AgentMemoryKv k
    WHERE k.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci
      AND k.\`Key\` = 'last_status'
      AND k.Value = 'processing'
  )
  AND c.created_at < (NOW() - INTERVAL ${KEEP_RECENT_MIN} MINUTE)
  ${OWNER_FILTER_SQL}
"

PREVIEW_SQL="
SELECT
  COUNT(*) AS would_delete,
  MIN(c.created_at) AS oldest,
  MAX(c.created_at) AS newest
FROM AgentCoreConversations c
${WHERE_CLAUSE};
"

SAMPLE_SQL="
SELECT c.conversation_id, c.owner_account_id, c.created_at, c.product_mode
FROM AgentCoreConversations c
${WHERE_CLAUSE}
ORDER BY c.created_at DESC
LIMIT 10;
"

run_mysql() {
  docker compose --ansi=never exec -T mysql mysql \
    -uroot -p"${DB_PASSWORD}" agent_memory --default-character-set=utf8mb4 \
    -e "$1" 2>&1 | grep -v 'Using a password on the command line'
}

echo "=== Empty conversation cleanup ==="
echo "Mode: $([[ $DRY_RUN -eq 1 ]] && echo 'dry-run (no DELETE)' || echo 'EXECUTE (will DELETE)')"
echo "Owner filter: ${OWNER_FILTER_SQL:-<none — all accounts>}"
echo "Keep recent: ${KEEP_RECENT_MIN} minutes"
echo
echo "--- Preview ---"
run_mysql "$PREVIEW_SQL"
echo
echo "--- Sample (latest 10) ---"
run_mysql "$SAMPLE_SQL"

if [[ $DRY_RUN -eq 1 ]]; then
  echo
  echo "[dry-run] DELETE 는 실행하지 않았습니다. 실제 정리는 --execute 옵션으로 다시 호출하세요."
  exit 0
fi

# Execute path.
echo
echo "--- Executing DELETE ---"
DELETE_SQL="
DELETE c FROM AgentCoreConversations c
${WHERE_CLAUSE};
"
run_mysql "$DELETE_SQL"
echo
echo "--- Post-state ---"
run_mysql "$PREVIEW_SQL"
echo
echo "[done] empty conversations cleanup 완료."
