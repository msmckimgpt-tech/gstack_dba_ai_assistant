#!/usr/bin/env bash
# =============================================================================
# install-metadata-graph-sync-cron.sh — feature-0016: 메타데이터 지식그래프 주기 동기화 cron(멱등).
#
# 관계형 SSOT(table/column_descriptions·table_relationships·glossary) 변경 + FK introspection·
# 대화 JOIN 학습으로 늘어난 관계를 AGE `metadata_kb` 그래프에 주기 반영한다. sync 는 멱등(MERGE)
# 이라 중복 무해, ~수초 소요(현 규모). cutover(AGENT_METADATA_GRAPH_SYNC_ENABLED=1) 이후에만 실효.
#
# 설치 항목(marker 로 멱등 — 재실행해도 중복 추가 안 함):
#   - 매 30분  bin/metadata-graph-sync.sh
# 로그: ../artifacts/metadata-graph/cron.log
#
# 사용: sudo bin/install-metadata-graph-sync-cron.sh [--remove] [--print]
#   --print  : 설치될/현재 crontab 만 출력(변경 없음)
#   --remove : 본 스크립트가 설치한 항목 제거
#
# ⚠️ **반드시 sudo(root crontab)로 실행** — 이 호스트는 일반 사용자에게 docker 소켓 접근이 없어
#    (permission denied) cron 이 docker exec 에 실패한다. feature-0015 backup cron 과 동일하게
#    root crontab 에서 실행되어야 한다(root 는 docker 접근 가능). bin/metadata-graph-sync.sh 는
#    plain docker 를 쓰므로 root cron 컨텍스트에서 정상 동작한다.
# =============================================================================
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_ROOT/../artifacts/metadata-graph"
LOG_PATH="$LOG_DIR/cron.log"
MARK="# feature-0016 metadata-graph-sync"
MODE="install"

while [ $# -gt 0 ]; do case "$1" in
  --remove) MODE="remove"; shift ;;
  --print) MODE="print"; shift ;;
  --help|-h) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

command -v crontab >/dev/null || { echo "[cron] crontab 없음 — 호스트에 cron 설치 필요." >&2; exit 1; }
mkdir -p "$LOG_DIR"

CUR="$(crontab -l 2>/dev/null || true)"
# 기존 marker 라인 제거(멱등 재설치 / remove 공통)
STRIPPED="$(printf '%s\n' "$CUR" | grep -vF "$MARK" || true)"

# insight-load-spread (부하 분산): 매 30분 --incremental(변경분만, 거의 no-op — WAL/CPU 스파이크 제거) +
# 매일 04:17 --full(삭제/파단 노드 정리, 워터마크 무시). 과거엔 30분마다 전량 5.7만 MERGE 를 autocommit
# 개별 커밋으로 돌려 30분 주기 WAL fsync 폭주를 만들었다. 증분+batched 로 상시 부하를 평탄화한다.
SYNC_LINE="*/30 * * * * cd $REPO_ROOT && bin/metadata-graph-sync.sh --incremental >> $LOG_PATH 2>&1 $MARK"
FULL_LINE="17 4 * * * cd $REPO_ROOT && bin/metadata-graph-sync.sh --full >> $LOG_PATH 2>&1 $MARK"

case "$MODE" in
  remove)
    printf '%s\n' "$STRIPPED" | crontab -
    echo "[cron] feature-0016 metadata-graph-sync cron 제거됨."
    ;;
  print)
    echo "[cron] 설치될 항목:"; echo "  $SYNC_LINE"; echo "  $FULL_LINE"
    echo "[cron] 현재 crontab:"; printf '%s\n' "$CUR" | sed 's/^/  /'
    ;;
  install)
    { printf '%s\n' "$STRIPPED"; echo "$SYNC_LINE"; echo "$FULL_LINE"; } | grep -vE '^\s*$' | crontab -
    echo "[cron] 설치 완료 (멱등):"
    echo "  매 30분   bin/metadata-graph-sync.sh --incremental (변경분만)"
    echo "  매일 04:17 bin/metadata-graph-sync.sh --full (삭제/파단 정리)"
    echo "  로그: $LOG_PATH"
    ;;
esac
