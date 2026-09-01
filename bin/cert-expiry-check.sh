#!/usr/bin/env bash
# =============================================================================
# cert-expiry-check.sh — 사내 TLS 인증서(leaf + Root CA) 만료 **감시**.
#   feature-0006-lan-proxy-access (사용자 결정 2026-09-01 — «만료 모니터링만»)
#
# ## 왜 필요한가 — 이미 있는 것과 무엇이 다른가
#
# `bin/deploy-web.sh` 의 `preflight_tls()` 가 이미 leaf 만료를 본다. 그런데 그것은
# **배포할 때만** 돈다. 배포가 없으면 신호도 없고, 그 사이 만료되면 **첫 신호가 전면
# outage** 다. 그리고 그 preflight 는 **Root CA 를 아예 보지 않는다** — CA 가 만료되면
# 테스터 전원이 재설치해야 하므로 leaf 만료보다 회복 비용이 훨씬 크다.
#
#   deploy-web.sh preflight = **게이트** (배포 직전 · leaf 14일 · WARN 후 배포 계속)
#   이 스크립트             = **감시**   (주기 실행 · leaf 30일 / CA 180일 기본)
#
# ⚠ 감시 임계는 게이트 임계보다 **넓어야 한다**. 좁으면 게이트가 먼저 울려 감시가 아무것도
#   더해 주지 않는다. 이 관계는 테스트로 잠겨 있다(`test_cert_expiry_monitor.py`).
#
# ## 파일과 라이브를 함께 본다
#
# 디스크의 cert 를 갱신하고 **배포하지 않으면** 사용자가 받는 것은 여전히 옛 cert 다.
# 파일만 보면 그 창을 못 본다. `--live <host:port>` 로 실제 서빙본을 함께 확인하고,
# 둘의 만료가 다르면 그 사실 자체를 보고한다(= 갱신했으나 미배포).
#
# ## 사용
#   bash bin/cert-expiry-check.sh [옵션]
#     --certs-dir <dir>     인증서 디렉토리 (기본: <project_root>/artifacts/certs)
#     --host <fqdn>         leaf 디렉토리 이름 (기본: .env 의 WEB_PUBLIC_HOST)
#     --live <host[:port]>  실제 서빙 중인 cert 도 함께 확인 (기본 포트 443)
#     --leaf-warn <days>    leaf 경고 임계 (기본 30)
#     --leaf-crit <days>    leaf 위험 임계 (기본 7)
#     --ca-warn <days>      Root CA 경고 임계 (기본 180)
#     --ca-crit <days>      Root CA 위험 임계 (기본 30)
#     --quiet               정상일 때 아무것도 출력하지 않음 (cron 용 — 문제시에만 메일)
#     -h | --help
#
# ## 종료 코드 (cron 알림이 이것으로 갈린다)
#   0  정상 (모든 축이 warn 임계 밖)
#   1  WARN     — warn 임계 침범 (갱신 계획 필요)
#   2  CRITICAL — crit 임계 침범 또는 이미 만료 (즉시 조치)
#   3  실행 오류 (파일 부재·openssl 실패·사용법)
#
# 의존성: openssl. 추가 패키지 불필요.
# =============================================================================
set -uo pipefail   # ⚠ -e 는 쓰지 않는다 — openssl -checkend 의 비-0 는 «만료 임박» 이라는
                   #   정상 신호이지 스크립트 실패가 아니다. -e 면 첫 경고에서 죽는다.

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(dirname "$(git -C "$SCRIPT_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" 2>/dev/null || echo "$SCRIPT_ROOT")"

CERTS_DIR="$REPO_ROOT/../artifacts/certs"
HOST=""
LIVE=""
LEAF_WARN=30
LEAF_CRIT=7
CA_WARN=180
CA_CRIT=30
QUIET=0

log()  { [ "$QUIET" -eq 1 ] || printf '[cert-expiry] %s\n' "$*"; }
warn() { printf '[cert-expiry] WARN: %s\n' "$*" >&2; }
crit() { printf '[cert-expiry] CRITICAL: %s\n' "$*" >&2; }
die()  { printf '[cert-expiry] ERROR: %s\n' "$*" >&2; exit 3; }

while [ $# -gt 0 ]; do case "$1" in
  --certs-dir) CERTS_DIR="${2:?}"; shift 2 ;;
  --host)      HOST="${2:?}"; shift 2 ;;
  --live)      LIVE="${2:?}"; shift 2 ;;
  --leaf-warn) LEAF_WARN="${2:?}"; shift 2 ;;
  --leaf-crit) LEAF_CRIT="${2:?}"; shift 2 ;;
  --ca-warn)   CA_WARN="${2:?}"; shift 2 ;;
  --ca-crit)   CA_CRIT="${2:?}"; shift 2 ;;
  --quiet)     QUIET=1; shift ;;
  -h|--help)   sed -n '2,50p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) die "unknown arg: $1 (--help 참조)" ;;
esac; done

command -v openssl >/dev/null 2>&1 || die "openssl 이 없습니다."

# 감시 임계가 게이트(14일)보다 좁으면 감시가 무의미하다 — 조용히 두지 않고 거절한다.
DEPLOY_GATE_DAYS=14
if [ "$LEAF_WARN" -lt "$DEPLOY_GATE_DAYS" ]; then
  die "--leaf-warn($LEAF_WARN) 이 deploy-web.sh preflight 게이트($DEPLOY_GATE_DAYS 일)보다 좁습니다. 감시가 게이트보다 늦게 울리면 아무것도 더해 주지 않습니다."
fi

if [ -z "$HOST" ] && [ -f "$REPO_ROOT/.env" ]; then
  HOST="$(grep -m1 '^WEB_PUBLIC_HOST=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ')"
fi

ROOT_CA="$CERTS_DIR/rootCA.pem"
LEAF="$CERTS_DIR/$HOST/fullchain.pem"

RC=0
bump() { [ "$1" -gt "$RC" ] && RC="$1"; return 0; }

#: 한 인증서의 만료를 두 임계로 판정한다. $1=라벨 $2=PEM경로 $3=warn일 $4=crit일
check_file() {
  local label="$1" path="$2" wd="$3" cd_="$4" notafter
  [ -f "$path" ] || { warn "$label: 파일 없음 ($path) — 확인 불가"; bump 1; return; }
  notafter="$(openssl x509 -in "$path" -noout -enddate 2>/dev/null | cut -d= -f2-)"
  [ -n "$notafter" ] || { warn "$label: 만료일을 읽지 못함 ($path)"; bump 1; return; }

  if ! openssl x509 -in "$path" -checkend 0 >/dev/null 2>&1; then
    crit "$label: **이미 만료됨** ($notafter)"; bump 2; return
  fi
  if ! openssl x509 -in "$path" -checkend $(( cd_ * 86400 )) >/dev/null 2>&1; then
    crit "$label: ${cd_}일 내 만료 ($notafter)"; bump 2; return
  fi
  if ! openssl x509 -in "$path" -checkend $(( wd * 86400 )) >/dev/null 2>&1; then
    warn "$label: ${wd}일 내 만료 ($notafter) — 갱신 계획 필요"; bump 1; return
  fi
  log "$label: OK (만료 $notafter)"
}

log "certs-dir: $CERTS_DIR | host: ${HOST:-<미해석>}"
check_file "leaf($HOST)" "$LEAF"     "$LEAF_WARN" "$LEAF_CRIT"
check_file "rootCA"      "$ROOT_CA"  "$CA_WARN"   "$CA_CRIT"

# ── 라이브 서빙본 (선택) — 「갱신했으나 미배포」 창을 잡는다 ──────────────────
if [ -n "$LIVE" ]; then
  case "$LIVE" in *:*) : ;; *) LIVE="$LIVE:443" ;; esac
  live_pem="$(mktemp)"; trap 'rm -f "$live_pem"' EXIT
  if openssl s_client -connect "$LIVE" -servername "${HOST:-${LIVE%%:*}}" </dev/null 2>/dev/null \
       | openssl x509 -outform pem > "$live_pem" 2>/dev/null && [ -s "$live_pem" ]; then
    check_file "live($LIVE)" "$live_pem" "$LEAF_WARN" "$LEAF_CRIT"
    if [ -f "$LEAF" ]; then
      f_end="$(openssl x509 -in "$LEAF" -noout -enddate 2>/dev/null)"
      l_end="$(openssl x509 -in "$live_pem" -noout -enddate 2>/dev/null)"
      if [ -n "$f_end" ] && [ "$f_end" != "$l_end" ]; then
        warn "디스크 cert 와 서빙 cert 의 만료가 다릅니다 — 갱신 후 **미배포** 상태로 보입니다. (disk: ${f_end#*=} / live: ${l_end#*=})"
        bump 1
      fi
    fi
  else
    warn "live($LIVE): 서빙 cert 를 가져오지 못함 — 네트워크/포트 확인"
    bump 1
  fi
fi

case "$RC" in
  0) log "전체 정상." ;;
  1) warn "갱신 계획이 필요한 항목이 있습니다. 갱신: bash bin/tls-internal-ca.sh (leaf 재발급 — CA 유지, 테스터 재설치 불필요) → make deploy-web-only" ;;
  2) crit "즉시 조치 필요. 갱신: bash bin/tls-internal-ca.sh → make deploy-web-only" ;;
esac
exit "$RC"
