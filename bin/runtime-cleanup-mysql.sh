#!/usr/bin/env bash
# runtime-cleanup-mysql.sh — AR-M5 (TASK-0119) MySQL agent_runtime 6 테이블 cleanup.
#
# ADR-0027 Addendum §Consequences (canary 기간 완료 후) + ADR-0028 (AR-M5 cleanup 정책):
#   1. AR-M4 cutover 완료 후 **14일 무회귀 confirm** 필수 (Stage B 안전 window).
#   2. mysqldump backup → artifacts/shared/runtime-m5-mysql-backup-<ISO>.sql.gz.
#   3. 6 테이블 DROP — convention 상 parent 마지막 순서:
#        AgentCoreMessages, AgentMemoryMessages, AgentMemorySteps,
#        AgentMemorySummary, AgentMemoryKv, AgentCoreConversations.
#      (MySQL 에는 FK constraint 없음 — PG side 만 FK 보유. 순서는 convention.)
#   4. `--confirm I_UNDERSTAND_DATA_LOSS` flag 없이는 dry-run 만 (DROP SQL 출력만).
#   5. dual-write 로직 (runtime_backend.py _dual_write_runtime) 의 코드 삭제는
#      별 AR-M5-impl cycle 책임 — 본 script 는 DB 측 정리만.
#
# rollback (Stage C 진입 = 데이터 손실 가능 시점):
#   - DROP 실행 전: --confirm 없이 dry-run 으로 명령 확인 + backup 보관 확인.
#   - DROP 실행 후: mysqldump 의 역방향 restore — 단, AR-M4 cutover 이후 새 row 는
#     PG only, restore 는 partial (AR-M5 진입 timestamp 까지의 snapshot 만).
#
# Usage:
#   bin/runtime-cleanup-mysql.sh --dry-run                        # DROP SQL 출력만
#   bin/runtime-cleanup-mysql.sh --backup-only                    # mysqldump 만
#   bin/runtime-cleanup-mysql.sh --confirm I_UNDERSTAND_DATA_LOSS \
#     --cutover-date YYYY-MM-DD                                   # 실 DROP
#
# Exit codes:
#   0 — 모든 단계 완료 (또는 dry-run 결과)
#   1 — 일부 단계 실패 (backup 또는 DROP)
#   2 — invalid args / 환경 부재 / confirm flag 누락

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
SHARED_DIR="${WRAPPER_ROOT}/artifacts/shared"
mkdir -p "$SHARED_DIR"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
MYSQL_CONTAINER="${COMPOSE_PROJECT_NAME}-mysql-1"

# pipefail-safe .env reader — `|| echo "$default"` rescues grep non-zero exit.
_env_get() {
  local key="$1" default="${2:-}"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '[:space:]' || echo "$default"
}

MYSQL_PW="$(_env_get MYSQL_ROOT_PASSWORD)"
MYSQL_DB="$(_env_get AGENT_MEMORY_DB agent_memory)"

MODE=""
CONFIRM=""
CUTOVER_DATE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      [ -n "$MODE" ] && { echo "ERROR: mode 중복 지정 — --dry-run/--backup-only/--confirm 中 1개만" >&2; exit 2; }
      MODE="dry-run"; shift ;;
    --backup-only)
      [ -n "$MODE" ] && { echo "ERROR: mode 중복 지정" >&2; exit 2; }
      MODE="backup"; shift ;;
    --confirm)
      [ -n "$MODE" ] && { echo "ERROR: mode 중복 지정" >&2; exit 2; }
      [ -z "${2:-}" ] && { echo "ERROR: --confirm 다음에 string 필요" >&2; exit 2; }
      CONFIRM="$2"; MODE="drop"; shift 2 ;;
    --cutover-date)
      [ -z "${2:-}" ] && { echo "ERROR: --cutover-date YYYY-MM-DD 필요" >&2; exit 2; }
      CUTOVER_DATE="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[ -z "$MODE" ] && MODE="dry-run"

# N-1: MySQL 에는 FK constraint 없음. 순서는 convention (parent AgentCoreConversations 마지막).
TABLES=(
  "AgentCoreMessages"
  "AgentMemoryMessages"
  "AgentMemorySteps"
  "AgentMemorySummary"
  "AgentMemoryKv"
  "AgentCoreConversations"
)

# ─── Stage 1: precondition ──────────────────────────────────────────────────
echo "[INFO] AR-M5 runtime cleanup mode=${MODE}"

if [ "$MODE" = "drop" ]; then
  if [ "$CONFIRM" != "I_UNDERSTAND_DATA_LOSS" ]; then
    echo "ERROR: --confirm I_UNDERSTAND_DATA_LOSS 필수 (대문자 + underscore 정확)" >&2
    echo "  본 명령은 MySQL agent_runtime 6 테이블 영구 삭제 — rollback 시 mysqldump restore 필요" >&2
    exit 2
  fi

  # shell env 우선, 없으면 .env file.
  read_backend="${AGENT_RUNTIME_READ_BACKEND:-$(_env_get AGENT_RUNTIME_READ_BACKEND)}"
  if [ "$read_backend" != "postgres" ]; then
    echo "ERROR: AGENT_RUNTIME_READ_BACKEND=${read_backend:-<미설정>} (=postgres 가 아님)" >&2
    echo "  AR-M4 cutover 가 활성이지 않은 상태에서 AR-M5 cleanup 진행 차단" >&2
    exit 2
  fi

  # M-1: dual_write 대소문자 정규화 (TRUE/YES/On 등 모두 차단).
  dual_write_raw="${AGENT_RUNTIME_DUAL_WRITE:-$(_env_get AGENT_RUNTIME_DUAL_WRITE)}"
  dual_write="$(echo "${dual_write_raw}" | tr '[:upper:]' '[:lower:]')"
  if [ "$dual_write" = "1" ] || [ "$dual_write" = "true" ] || \
     [ "$dual_write" = "yes" ] || [ "$dual_write" = "on" ]; then
    echo "ERROR: AGENT_RUNTIME_DUAL_WRITE=${dual_write_raw} 가 아직 활성 — AR-M5-impl cycle 의 caller 코드 삭제 선행 필요" >&2
    echo "  runtime_backend.py 의 dual-write 경로가 남아있는 상태에서 DROP 시 MySQL INSERT crash." >&2
    echo "  AGENT_RUNTIME_DUAL_WRITE=0 + agent 재기동 후 재시도" >&2
    exit 2
  fi

  # 14-day monitoring window enforcement (ADR-0028).
  if [ -z "$CUTOVER_DATE" ]; then
    echo "ERROR: --cutover-date YYYY-MM-DD 필수 (ADR-0028 의 14-day window 강제)" >&2
    echo "  예: --cutover-date 2026-05-27 (AR-M4 cutover 의 .env 변경 일자)" >&2
    exit 2
  fi
  if ! printf '%s' "$CUTOVER_DATE" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
    echo "ERROR: --cutover-date 형식 오류: '${CUTOVER_DATE}' (YYYY-MM-DD)" >&2
    exit 2
  fi
  cutover_epoch=$(date -d "$CUTOVER_DATE" +%s 2>/dev/null || true)
  now_epoch=$(date +%s)
  if [ -z "$cutover_epoch" ]; then
    echo "ERROR: --cutover-date 유효한 날짜 아님: '${CUTOVER_DATE}'" >&2
    exit 2
  fi
  days_since=$(( (now_epoch - cutover_epoch) / 86400 ))
  if [ "$days_since" -lt 14 ]; then
    echo "ERROR: cutover-date 후 ${days_since}일 경과 — ADR-0028 의 14-day window 미달" >&2
    echo "  $((14 - days_since))일 추가 monitoring 후 재시도" >&2
    exit 2
  fi
  echo "[INFO] cutover-date ${CUTOVER_DATE} 후 ${days_since}일 경과 — 14-day window PASS"

  # TTY interactive double-confirm.
  if [ -t 0 ]; then
    echo ""
    echo "================================================================"
    echo "  영구 데이터 삭제 — MySQL agent_runtime 6 테이블 DROP"
    echo "    backup: artifacts/shared/runtime-m5-mysql-backup-<ISO>.sql.gz"
    echo "    rollback: Stage C 이후 데이터 손실 가능"
    echo "    confirm phrase 를 정확히 typing 후 Enter:"
    echo "================================================================"
    printf "  > "
    read -r typed_phrase
    if [ "$typed_phrase" != "I_UNDERSTAND_DATA_LOSS" ]; then
      echo "ERROR: typed phrase 'I_UNDERSTAND_DATA_LOSS' 와 일치 안 함 — 진행 차단" >&2
      exit 2
    fi
  elif [ -z "${RUNTIME_M5_RUN_FROM_HUMAN_SHELL:-}" ]; then
    echo "ERROR: non-TTY 환경 — RUNTIME_M5_RUN_FROM_HUMAN_SHELL=1 설정 후 재시도" >&2
    echo "  CI/cron 등의 자동 실행 차단" >&2
    exit 2
  else
    # N-3: non-TTY bypass audit trail.
    echo "[WARN] TTY bypass active (RUNTIME_M5_RUN_FROM_HUMAN_SHELL=1) — interactive confirm skipped" >&2
  fi
fi

# ─── Stage 2: mysqldump backup ───────────────────────────────────────────────
BACKUP_FILE=""
BACKUP_SHA256=""
BACKUP_DIR=""
if [ "$MODE" = "backup" ] || [ "$MODE" = "drop" ]; then
  # N-2: guard against empty password — better error than cryptic mysqldump auth failure.
  [ -z "$MYSQL_PW" ] && { echo "ERROR: MYSQL_ROOT_PASSWORD not found in ${ENV_FILE}" >&2; exit 2; }
  ts="$(date -u '+%Y-%m-%dT%H%M%SZ')"
  BACKUP_DIR="${SHARED_DIR}/runtime-m5-mysql-backup-${ts}"
  mkdir -p "$BACKUP_DIR"
  chmod 0700 "$BACKUP_DIR"
  BACKUP_FILE="${BACKUP_DIR}/dump.sql.gz"
  echo "[STAGE 2] mysqldump backup → $BACKUP_FILE"

  if ! docker ps --format '{{.Names}}' | grep -qx "$MYSQL_CONTAINER"; then
    echo "ERROR: mysql container '${MYSQL_CONTAINER}' not running" >&2
    exit 1
  fi

  # C-1: MYSQL_PWD env var (not -p cmdline) — 비밀번호가 ps aux 에 노출 안 됨.
  if ! docker exec -i -e MYSQL_PWD="$MYSQL_PW" "$MYSQL_CONTAINER" mysqldump -uroot \
       --single-transaction --routines --triggers --add-drop-table \
       --hex-blob --default-character-set=utf8mb4 \
       "$MYSQL_DB" "${TABLES[@]}" 2>/tmp/runtime-m5-backup-err.log | gzip > "$BACKUP_FILE"; then
    echo "ERROR: mysqldump 실패. detail: $(cat /tmp/runtime-m5-backup-err.log)" >&2
    rm -rf "$BACKUP_DIR"
    exit 1
  fi
  chmod 0600 "$BACKUP_FILE"

  # backup integrity verification.
  echo "[STAGE 2.1] backup integrity verify"
  if ! gunzip -t "$BACKUP_FILE" 2>/tmp/runtime-m5-gzip-err.log; then
    echo "ERROR: backup gzip integrity 실패. detail: $(cat /tmp/runtime-m5-gzip-err.log)" >&2
    rm -rf "$BACKUP_DIR"
    exit 1
  fi
  # M-3: minimum 50 lines (empty 6-table mysqldump ~80 lines of header/footer).
  decompressed_lines=$(gunzip -c "$BACKUP_FILE" | wc -l)
  if [ "$decompressed_lines" -lt 50 ]; then
    echo "ERROR: backup 너무 짧음 (${decompressed_lines} lines) — corrupt 의심" >&2
    rm -rf "$BACKUP_DIR"
    exit 1
  fi
  # M-3: backtick-anchored pattern (`table`) to avoid substring matches.
  for tbl in "${TABLES[@]}"; do
    if ! gunzip -c "$BACKUP_FILE" | grep -Eq "CREATE TABLE \`${tbl}\`"; then
      echo "ERROR: backup 에 ${tbl} CREATE TABLE 누락 — restore 불가" >&2
      rm -rf "$BACKUP_DIR"
      exit 1
    fi
  done

  # SHA256 sidecar.
  BACKUP_SHA256="${BACKUP_FILE}.sha256"
  ( cd "$BACKUP_DIR" && sha256sum "$(basename "$BACKUP_FILE")" > "$BACKUP_SHA256" )
  chmod 0600 "$BACKUP_SHA256"

  echo "  backup 완료: $(du -h "$BACKUP_FILE" | cut -f1)"
  echo "  path:        $BACKUP_FILE"
  echo "  sha256:      $(cut -d' ' -f1 "$BACKUP_SHA256")"
  echo "  integrity:   PASS (${decompressed_lines} lines, 6 테이블 CREATE TABLE 확인)"
fi

if [ "$MODE" = "backup" ]; then
  echo "[DONE] backup-only 완료. DROP 은 --confirm I_UNDERSTAND_DATA_LOSS --cutover-date YYYY-MM-DD 로 진행"
  exit 0
fi

# ─── Stage 3: DROP 명령 생성 ────────────────────────────────────────────────
echo "[STAGE 3] DROP SQL (parent AgentCoreConversations 마지막)"
DROP_SQL=""
for tbl in "${TABLES[@]}"; do
  DROP_SQL="${DROP_SQL}DROP TABLE IF EXISTS ${MYSQL_DB}.${tbl};"$'\n'
done
echo "$DROP_SQL" | sed 's/^/  /'

if [ "$MODE" = "dry-run" ]; then
  echo ""
  echo "[DRY-RUN] 위 DROP SQL 은 --confirm I_UNDERSTAND_DATA_LOSS --cutover-date YYYY-MM-DD 시점에 실행."
  echo "[DRY-RUN] mysqldump backup 은 --backup-only 또는 --confirm 시 자동 수행."
  echo "[DRY-RUN] I_UNDERSTAND_DATA_LOSS flag 없이는 실 DROP 실행 안 됨."
  exit 0
fi

# M-2: ERR trap — DROP 실행 중 중단 시 backup path 항상 출력.
trap 'echo "[ERR] 중단됨 — backup: ${BACKUP_FILE:-<없음>}" >&2' ERR

# ─── Stage 4: DROP 실행 ─────────────────────────────────────────────────────
echo "[STAGE 4] DROP 실행 (영구 삭제 — backup: $BACKUP_FILE)"
# C-1: MYSQL_PWD env var (not -p cmdline) — 비밀번호 cmdline 노출 방지.
if ! docker exec -i -e MYSQL_PWD="$MYSQL_PW" "$MYSQL_CONTAINER" \
     mysql -uroot "$MYSQL_DB" <<< "$DROP_SQL" 2>/tmp/runtime-m5-drop-err.log; then
  echo "ERROR: DROP 실행 실패. detail: $(cat /tmp/runtime-m5-drop-err.log)" >&2
  echo "  rollback: $BACKUP_FILE 으로 mysqldump restore" >&2
  exit 1
fi

# ─── Stage 5: 검증 ──────────────────────────────────────────────────────────
echo "[STAGE 5] 검증 — DROP 완료 확인"
for tbl in "${TABLES[@]}"; do
  # C-1: MYSQL_PWD env var for verify query.
  exists=$(docker exec -i -e MYSQL_PWD="$MYSQL_PW" "$MYSQL_CONTAINER" \
    mysql -uroot --skip-column-names -B -e \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${MYSQL_DB}' AND table_name='${tbl}';" \
    | grep -v '^mysql:' | head -1 | tr -d '[:space:]' || echo "1")
  if [ "$exists" = "0" ]; then
    echo "  OK ${tbl} dropped"
  else
    # M-2: rollback hint on Stage 5 failure.
    echo "  FAIL ${tbl} 여전히 존재 — rollback: ${BACKUP_FILE} 으로 restore" >&2
    exit 1
  fi
done

trap - ERR

echo ""
echo "AR-M5 cleanup 완료"
echo "  backup: $BACKUP_FILE"
echo "  dropped: ${#TABLES[@]} 테이블"
echo ""
echo "다음 단계 (AR-M5-impl cycle, 별 cycle):"
echo "  1. runtime_backend.py 의 dual-write 경로 코드 삭제"
echo "  2. AGENT_RUNTIME_DUAL_WRITE env 참조 제거"
echo "  3. ADR-0028 의 Stage C 마감 마킹"
exit 0
