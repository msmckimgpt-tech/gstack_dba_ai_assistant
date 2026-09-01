#!/usr/bin/env bash
# =============================================================================
# install-cert-expiry-cron.sh — 사내 TLS 인증서 만료 감시 cron 설치(멱등).
#   feature-0006-lan-proxy-access (사용자 결정 2026-09-01 — «만료 모니터링만»)
#   install-worktree-audit-cron.sh 패턴 승계.
#
# 설치 항목(marker 멱등):
#   - 매주 월 09:10 bin/cert-expiry-check.sh --live <WEB_PUBLIC_HOST>
#     leaf 30일 / rootCA 180일 기본 임계. 정상이면 조용하고(--quiet), 임계 침범 시에만
#     stderr 로 말한다 → cron 이 그때만 메일을 보낸다.
#
# 왜 주 1회인가: leaf 는 825일, CA 는 10년짜리다. 감시 임계(30일/180일)에 비해 주 1회면
# 최악의 경우에도 경고 후 **최소 23일**의 갱신 시간이 남는다. 매일 돌리면 같은 경고가
# 30번 반복되어 신호가 소음이 된다.
#
# 로그: ../artifacts/cert-expiry/cron.log
#
# 사용: bin/install-cert-expiry-cron.sh [--remove] [--print]
# =============================================================================
set -euo pipefail
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# cron 은 main checkout 에 앵커 — worktree 에서 설치해도 worktree 경로(수명 짧음)를 쓰지 않는다.
REPO_ROOT="$(dirname "$(git -C "$SCRIPT_ROOT" rev-parse --path-format=absolute --git-common-dir)")"
LOG_DIR="$REPO_ROOT/../artifacts/cert-expiry"
LOG_PATH="$LOG_DIR/cron.log"
MARK="# feature-0006 cert-expiry"
MODE="install"

while [ $# -gt 0 ]; do case "$1" in
  --remove) MODE="remove"; shift ;;
  --print)  MODE="print"; shift ;;
  --help|-h) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

command -v crontab >/dev/null || { echo "[cron] crontab 없음." >&2; exit 1; }
mkdir -p "$LOG_DIR"

HOST="$(grep -m1 '^WEB_PUBLIC_HOST=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ' || true)"
LIVE_ARG=""
[ -n "$HOST" ] && LIVE_ARG=" --live $HOST"

CUR="$(crontab -l 2>/dev/null || true)"
STRIPPED="$(printf '%s\n' "$CUR" | grep -vF "$MARK" || true)"

# --quiet: 정상일 때 stdout 침묵 → cron 메일 없음. 경보는 stderr 로 나가 메일이 온다.
CHECK_LINE="10 9 * * 1 cd $REPO_ROOT && bash bin/cert-expiry-check.sh --quiet$LIVE_ARG >> $LOG_PATH 2>&1 $MARK"

case "$MODE" in
  remove)
    printf '%s\n' "$STRIPPED" | crontab -
    echo "[cron] cert-expiry cron 제거됨."
    ;;
  print)
    echo "[cron] 설치될 항목:"; echo "  $CHECK_LINE"
    ;;
  install)
    { printf '%s\n' "$STRIPPED"; echo "$CHECK_LINE"; } | grep -vE '^\s*$' | crontab -
    echo "[cron] 설치 완료 (멱등):"
    echo "  매주 월 09:10 cert-expiry-check (leaf 30일 / rootCA 180일 임계${LIVE_ARG:+ · 라이브 서빙본 대조})"
    echo "  로그: $LOG_PATH"
    echo "  경보 시 갱신: bash bin/tls-internal-ca.sh → make deploy-web-only"
    ;;
esac
