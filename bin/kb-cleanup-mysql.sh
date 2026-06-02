#!/usr/bin/env bash
# kb-cleanup-mysql.sh — M5 (TASK-0025) MySQL KB 5 정본 cleanup.
#
# ADR-0021 §Consequences (g) + ADR-0025 (M5 cleanup 정책) 의 cutover 후 정리:
#   1. M4 cutover 완료 후 **2주일 무회귀 confirm** 필수 (Stage B 안전 window).
#   2. mysqldump backup → artifacts/shared/mysql-kb-backup-<ISO>.sql.gz (~수 MB).
#   3. 5 정본 DROP — AgentMemoryFacts (VIEW), AgentMemoryRagObjects,
#      AgentMemoryRagDocuments, AgentMemoryFactEntries, AgentMemoryTexts (의존
#      순서 역순).
#   4. `--confirm I_UNDERSTAND_DATA_LOSS` flag 없이는 dry-run 만 (DROP SQL 출력만).
#   5. dual-write 로직 (`_DualWriteMirror` mirror call) 의 코드 삭제는 별
#      M5-implementation cycle 책임 — 본 script 는 DB 측 정리만.
#
# rollback (Stage C 진입 = 데이터 손실 가능 시점):
#   - DROP 실행 전: `--confirm` 없이 dry-run 으로 명령 확인 + backup 보관 확인.
#   - DROP 실행 후: mysqldump 의 역방향 restore — 단, M4 이후 새 row 는 PG only,
#     restore 는 partial (M5 진입 timestamp 까지의 snapshot 만).
#
# Usage:
#   bin/kb-cleanup-mysql.sh --dry-run                        # DROP SQL 출력만
#   bin/kb-cleanup-mysql.sh --backup-only                    # mysqldump 만
#   bin/kb-cleanup-mysql.sh --confirm I_UNDERSTAND_DATA_LOSS # 실 DROP
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

# .env 파싱 — `.env` 부재/무매칭 시 grep 이 rc=1(no-match)/2(file 부재) 를 반환하고,
# `set -euo pipefail` (특히 pipefail) 이 이 command-substitution 할당을 치명적 종료로
# 만든다. 단위 테스트 (test_m5_cleanup.py) 는 wrapper `.env` 없이 `bash script --dry-run`
# 등으로 호출하므로 arg 파싱/Stage 1 진입 전 rc=2 로 조용히 죽었다 (이것이 deselect
# 사유였음). `|| true` 로 grep 의 비치명적 처리 — 운영 시엔 .env 존재, 부재 시에도
# MYSQL_DB 는 아래 default 로 fallback, MYSQL_PW 는 실제 DB 접속 단계에서만 필요.
MYSQL_PW="$( { grep -E '^MYSQL_ROOT_PASSWORD=' "$ENV_FILE" 2>/dev/null || true; } | cut -d= -f2-)"
MYSQL_DB="$( { grep -E '^AGENT_MEMORY_DB=' "$ENV_FILE" 2>/dev/null || true; } | cut -d= -f2-)"
MYSQL_DB="${MYSQL_DB:-agent_memory}"

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

# 의존 순서 — VIEW 먼저, 그 후 FK depend 없는 base table 마지막.
TABLES=(
  "AgentMemoryFacts"        # VIEW
  "AgentMemoryRagObjects"
  "AgentMemoryRagDocuments"
  "AgentMemoryFactEntries"
  "AgentMemoryTexts"
)

# ─── Stage 1: precondition ──────────────────────────────────────────────────
echo "[INFO] M5 cleanup mode=${MODE}"

if [ "$MODE" = "drop" ]; then
  if [ "$CONFIRM" != "I_UNDERSTAND_DATA_LOSS" ]; then
    echo "ERROR: --confirm I_UNDERSTAND_DATA_LOSS 필수 (대문자 + underscore 정확)" >&2
    echo "  본 명령은 MySQL KB 5 정본 영구 삭제 — rollback 시 mysqldump restore 필요" >&2
    exit 2
  fi
  # REV-20260522-0013 B7 흡수: env fallback — shell env 우선, 없으면 .env file.
  read_backend="${AGENT_KB_READ_BACKEND:-$(grep -E '^AGENT_KB_READ_BACKEND=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)}"
  if [ "$read_backend" != "postgres" ]; then
    echo "ERROR: AGENT_KB_READ_BACKEND=$read_backend (=postgres 가 아님)" >&2
    echo "  M4 cutover 가 활성이지 않은 상태에서 M5 cleanup 진행 차단" >&2
    exit 2
  fi
  # REV-20260522-0013 B3 흡수: dual-write sentinel — `_DualWriteMirror` caller
  # 코드 cleanup 이 선행되어야 DROP 후 MySQL caller cur.execute 가 NoSuchTable 로
  # crash 안 함. .env 의 AGENT_KB_DUAL_WRITE=0 으로 명시 신호.
  dual_write="${AGENT_KB_DUAL_WRITE:-$(grep -E '^AGENT_KB_DUAL_WRITE=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)}"
  if [ "$dual_write" = "1" ] || [ "$dual_write" = "true" ] || [ "$dual_write" = "yes" ]; then
    echo "ERROR: AGENT_KB_DUAL_WRITE=$dual_write 가 아직 활성 — M5-implementation cycle 의 caller 코드 삭제 선행 필요" >&2
    echo "  caller (knowledge.py:633/598 + utils.py:957/1179/1230) 의 _dual_write_kb 호출 site 가" >&2
    echo "  남아있는 상태에서 DROP 시 MySQL INSERT crash. AGENT_KB_DUAL_WRITE=0 + agent 재기동 후 재시도" >&2
    exit 2
  fi
  # REV-20260522-0013 B4 흡수: 14-day monitoring window enforcement.
  if [ -z "$CUTOVER_DATE" ]; then
    echo "ERROR: --cutover-date YYYY-MM-DD 필수 (ADR-0025 의 14-day window 강제)" >&2
    echo "  예: --cutover-date 2026-05-22 (M4 cutover 의 .env 변경 일자)" >&2
    exit 2
  fi
  if ! printf '%s' "$CUTOVER_DATE" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
    echo "ERROR: --cutover-date 형식 오류: '$CUTOVER_DATE' (YYYY-MM-DD)" >&2
    exit 2
  fi
  cutover_epoch=$(date -d "$CUTOVER_DATE" +%s 2>/dev/null || true)
  now_epoch=$(date +%s)
  if [ -z "$cutover_epoch" ]; then
    echo "ERROR: --cutover-date 유효한 날짜 아님: '$CUTOVER_DATE'" >&2
    exit 2
  fi
  days_since=$(( (now_epoch - cutover_epoch) / 86400 ))
  if [ "$days_since" -lt 14 ]; then
    echo "ERROR: cutover-date 후 ${days_since}일 경과 — ADR-0025 의 14-day window 미달" >&2
    echo "  $((14 - days_since))일 추가 monitoring 후 재시도" >&2
    exit 2
  fi
  echo "[INFO] cutover-date ${CUTOVER_DATE} 후 ${days_since}일 경과 — 14-day window PASS"
  # REV-20260522-0013 B6 흡수: TTY interactive double-confirm.
  if [ -t 0 ]; then
    echo ""
    echo "================================================================"
    echo "⚠️  영구 데이터 삭제 — MySQL KB 5 정본 DROP"
    echo "    backup: artifacts/shared/mysql-kb-backup-<ISO>.sql.gz"
    echo "    rollback: Stage C 이후 데이터 손실 가능"
    echo "    confirm phrase 를 정확히 typing 후 Enter:"
    echo "================================================================"
    printf "  > "
    read -r typed_phrase
    if [ "$typed_phrase" != "I_UNDERSTAND_DATA_LOSS" ]; then
      echo "ERROR: typed phrase 'I_UNDERSTAND_DATA_LOSS' 와 일치 안 함 — 진행 차단" >&2
      exit 2
    fi
  elif [ -z "${KB_M5_RUN_FROM_HUMAN_SHELL:-}" ]; then
    echo "ERROR: non-TTY 환경 — KB_M5_RUN_FROM_HUMAN_SHELL=1 설정 후 재시도" >&2
    echo "  CI/cron 등의 자동 실행 차단" >&2
    exit 2
  else
    echo "[WARN] TTY bypass active (KB_M5_RUN_FROM_HUMAN_SHELL=1) — interactive confirm skipped"
  fi
fi

# ─── Stage 2: mysqldump backup (B1+B2+B8 흡수) ──────────────────────────────
BACKUP_FILE=""
BACKUP_SHA256=""
BACKUP_DIR=""
if [ "$MODE" = "backup" ] || [ "$MODE" = "drop" ]; then
  ts="$(date -u '+%Y-%m-%dT%H%M%SZ')"
  # REV-20260522-0013 B8 흡수: 별 디렉터리 + chmod 0700.
  BACKUP_DIR="${SHARED_DIR}/m5-mysql-kb-backup-${ts}"
  mkdir -p "$BACKUP_DIR"
  chmod 0700 "$BACKUP_DIR"
  BACKUP_FILE="${BACKUP_DIR}/dump.sql.gz"
  echo "[STAGE 2] mysqldump backup → $BACKUP_FILE"

  if ! docker ps --format '{{.Names}}' | grep -qx "$MYSQL_CONTAINER"; then
    echo "ERROR: mysql container '${MYSQL_CONTAINER}' not running" >&2
    exit 1
  fi

  # REV-20260522-0013 B1 흡수: VIEW 포함 — mysqldump 의 table list 에 VIEW 도 명시.
  # mysqldump 는 list 에 등장한 VIEW 의 CREATE OR REPLACE VIEW DDL 도 dump.
  # REV-20260522-0013 C7 흡수: --hex-blob + --default-character-set=utf8mb4.
  if ! docker exec -i -e MYSQL_PWD="$MYSQL_PW" "$MYSQL_CONTAINER" mysqldump -uroot \
       --single-transaction --routines --triggers --add-drop-table \
       --hex-blob --default-character-set=utf8mb4 \
       "$MYSQL_DB" "${TABLES[@]}" 2>/tmp/m5-backup-err.log | gzip > "$BACKUP_FILE"; then
    echo "ERROR: mysqldump 실패. detail: $(cat /tmp/m5-backup-err.log)" >&2
    rm -rf "$BACKUP_DIR"
    exit 1
  fi
  chmod 0600 "$BACKUP_FILE"

  # REV-20260522-0013 B2 흡수: backup integrity verification.
  echo "[STAGE 2.1] backup integrity verify"
  if ! gunzip -t "$BACKUP_FILE" 2>/tmp/m5-gzip-err.log; then
    echo "ERROR: backup gzip integrity 실패. detail: $(cat /tmp/m5-gzip-err.log)" >&2
    rm -rf "$BACKUP_DIR"
    exit 1
  fi
  # SQL content sanity — 각 table 의 CREATE 또는 INSERT 등장 확인
  decompressed_lines=$(gunzip -c "$BACKUP_FILE" | wc -l)
  if [ "$decompressed_lines" -lt 10 ]; then
    echo "ERROR: backup 너무 짧음 (${decompressed_lines} lines) — corrupt 의심" >&2
    rm -rf "$BACKUP_DIR"
    exit 1
  fi
  # VIEW DDL + TABLE DDL 포함 확인.
  # 임시 파일 방식: grep -q early-exit → gunzip SIGPIPE(141) → pipefail false-negative 회피.
  # case-insensitive (-i): Linux MySQL lower_case_table_names=1 으로 소문자 저장.
  _VERIFY_TMP=$(mktemp /tmp/m5-kb-verify.XXXXXX)
  gunzip -c "$BACKUP_FILE" > "$_VERIFY_TMP"
  # VIEW DDL 포함 확인 (B1 enforcement)
  if ! grep -Eqi "CREATE.*(OR REPLACE.*)?VIEW.*AgentMemoryFacts" "$_VERIFY_TMP"; then
    echo "ERROR: backup 에 AgentMemoryFacts VIEW DDL 누락 — restore 불가" >&2
    rm -f "$_VERIFY_TMP"; rm -rf "$BACKUP_DIR"
    exit 1
  fi
  for tbl in "${TABLES[@]:1}"; do
    if ! grep -Eqi "CREATE TABLE.*\`?${tbl}\`?" "$_VERIFY_TMP"; then
      echo "ERROR: backup 에 ${tbl} CREATE TABLE 누락 — restore 불가" >&2
      rm -f "$_VERIFY_TMP"; rm -rf "$BACKUP_DIR"
      exit 1
    fi
  done
  rm -f "$_VERIFY_TMP"

  # REV-20260522-0013 B8 흡수: SHA256 sidecar.
  BACKUP_SHA256="${BACKUP_FILE}.sha256"
  ( cd "$BACKUP_DIR" && sha256sum "$(basename "$BACKUP_FILE")" > "$BACKUP_SHA256" )
  chmod 0600 "$BACKUP_SHA256"

  echo "  backup 완료: $(du -h "$BACKUP_FILE" | cut -f1)"
  echo "  path:        $BACKUP_FILE"
  echo "  sha256:      $(cat "$BACKUP_SHA256" | cut -d' ' -f1)"
  echo "  integrity:   PASS (${decompressed_lines} lines, VIEW+5 entries verified)"
fi

if [ "$MODE" = "backup" ]; then
  echo "[DONE] backup-only 완료. DROP 은 --confirm I_UNDERSTAND_DATA_LOSS 로 진행"
  exit 0
fi

# ─── Stage 3: DROP 명령 생성 ────────────────────────────────────────────────
echo "[STAGE 3] DROP SQL"
DROP_SQL=""
for tbl in "${TABLES[@]}"; do
  if [ "$tbl" = "AgentMemoryFacts" ]; then
    DROP_SQL="${DROP_SQL}DROP VIEW IF EXISTS ${MYSQL_DB}.${tbl};"$'\n'
  else
    DROP_SQL="${DROP_SQL}DROP TABLE IF EXISTS ${MYSQL_DB}.${tbl};"$'\n'
  fi
done
echo "$DROP_SQL" | sed 's/^/  /'

if [ "$MODE" = "dry-run" ]; then
  echo ""
  echo "[DRY-RUN] 위 DROP SQL 은 --confirm I_UNDERSTAND_DATA_LOSS 시점에 실행."
  echo "[DRY-RUN] mysqldump backup 은 --backup-only 또는 --confirm 시 자동 수행."
  exit 0
fi

# ─── Stage 4: DROP 실행 ─────────────────────────────────────────────────────
# C-1: MYSQL_PWD env var (not -p cmdline) — 비밀번호 ps aux 노출 차단.
echo "[STAGE 4] DROP 실행 (영구 삭제 — backup file: $BACKUP_FILE)"
if ! docker exec -i -e MYSQL_PWD="$MYSQL_PW" "$MYSQL_CONTAINER" mysql -uroot \
     "$MYSQL_DB" <<< "$DROP_SQL" 2>/tmp/m5-drop-err.log; then
  echo "ERROR: DROP 실행 실패. detail: $(cat /tmp/m5-drop-err.log)" >&2
  echo "  rollback: $BACKUP_FILE 으로 mysqldump restore" >&2
  exit 1
fi

# 검증 — table 존재 확인
echo "[STAGE 5] 검증 — DROP 완료 확인"
for tbl in "${TABLES[@]}"; do
  exists=$(docker exec -i -e MYSQL_PWD="$MYSQL_PW" "$MYSQL_CONTAINER" mysql -uroot \
    --skip-column-names -B -e \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${MYSQL_DB}' AND table_name=LOWER('${tbl}');" \
    2>/dev/null | head -1 | tr -d '[:space:]' || echo "1")
  if [ "$exists" = "0" ]; then
    echo "  OK ${tbl} dropped"
  else
    echo "  FAIL ${tbl} 여전히 존재" >&2
    exit 1
  fi
done

echo ""
echo "✅ M5 cleanup 완료"
echo "  backup: $BACKUP_FILE"
echo "  dropped: ${#TABLES[@]} entries"
echo ""
echo "다음 단계 (M5-implementation cycle, 별 cycle):"
echo "  1. _DualWriteMirror module 의 코드 삭제 (knowledge.py / utils.py caller 정리)"
echo "  2. ADR-0025 의 (e) deprecation timeline 마감 마킹"
echo "  3. audit ActionCode kb.*.mirror 의 deprecation 명시"
exit 0
