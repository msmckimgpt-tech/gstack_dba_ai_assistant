#!/usr/bin/env bash
# tls-internal-ca.sh — 사내 자체 Root CA 발급 + 서버 leaf 인증서 서명
#   feature-0006-lan-proxy-access / TASK-0296 (REQ-0283, AC-0549~AC-0554)
#
# 목적
#   self-signed 인증서로 인한 브라우저 "안전하지 않은 연결" 경고를 제거한다.
#   - Root CA (장기, 기본 10년) 를 1회 생성한다 → 테스터 PC 신뢰 저장소에 1회
#     설치 (rootCA.pem 배포). 설치 가이드: TESTER_TLS_TRUST.md.
#   - 서버 leaf 인증서 (기본 825일) 를 Root CA 로 서명한다 → web 컨테이너가 서빙.
#   - leaf 는 만료 시 본 스크립트 재실행으로 transparent 교체된다 (Root CA 가
#     유지되므로 테스터 재설치 불필요). Root CA 키는 절대 재생성하지 않는다
#     (--force-ca 명시 시에만).
#
# 산출물 (모두 artifacts/certs — gitignore, 버전관리 밖. SECURITY.md §5/§6)
#   <certs>/rootCA.pem                              Root CA 공개 인증서 (테스터 배포)
#   <certs>/rootCA-key.pem                          Root CA 개인키 (0600, 서버 보관 — 배포 금지)
#   <certs>/<host>/fullchain.pem                    leaf + Root CA (web/caddy 서빙)
#   <certs>/<host>/privkey.pem                      leaf 개인키 (0600)
#
# Usage
#   bash bin/tls-internal-ca.sh [옵션]
#     --host <fqdn>      서버 공개 호스트명 (기본: .env 의 WEB_PUBLIC_HOST)
#     --san-dns <name>   추가 DNS SAN (반복 가능)
#     --san-ip <ip>      추가 IP SAN (반복 가능)
#     --days <n>         leaf 유효기간 일수 (기본 825 — Apple/macOS 안전 상한)
#     --ca-days <n>      Root CA 유효기간 일수 (기본 3650 = 10년)
#     --certs-dir <dir>  인증서 출력 디렉토리 (기본: <project_root>/artifacts/certs)
#     --force-ca         기존 Root CA 를 폐기하고 새로 생성 (테스터 전원 재설치 필요!)
#     --print-san        해석된 SAN 목록만 출력하고 종료 (검증용)
#     -h | --help        도움말
#
# 의존성: openssl (1.1.1+ / 3.x). 추가 패키지 불필요.
set -euo pipefail

log()  { printf '[tls-ca] %s\n' "$*" >&2; }
die()  { printf '[tls-ca][ERROR] %s\n' "$*" >&2; exit 1; }

# --- project_root / certs_dir 해석 (main worktree 기준 — docker-compose 의 ../artifacts 와 정합) ---
# cwd 와 무관하게 스크립트 위치($SCRIPT_DIR) 기준으로 git-common-dir 을 해석한다.
# main repo / linked worktree 어디서 실행해도 git-common-dir 은 항상 main repo 의
# .git 을 가리키므로 동일한 artifacts/ 경로로 수렴한다 (프로젝트 루트=비-git 여도 안전).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_COMMON_DIR="$(git -C "$SCRIPT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [ -n "$GIT_COMMON_DIR" ]; then
  MAIN_REPO_ROOT="$(cd "$(dirname "$GIT_COMMON_DIR")" && pwd)"
else
  # 비-git 환경 fallback: 스크립트 위치 기준 (bin/ 의 상위)
  MAIN_REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
PROJECT_ROOT="$(cd "$MAIN_REPO_ROOT/.." && pwd)"
ENV_FILE="$MAIN_REPO_ROOT/.env"

# --- 기본값 ---
HOST=""
DAYS=825
CA_DAYS=3650
CERTS_DIR=""
FORCE_CA=0
PRINT_SAN=0
EXTRA_DNS=()
EXTRA_IP=()

# .env 에서 WEB_PUBLIC_HOST / WEB_ALLOWED_HOSTS 읽기 (있으면)
ENV_PUBLIC_HOST=""
ENV_ALLOWED_HOSTS=""
if [ -f "$ENV_FILE" ]; then
  ENV_PUBLIC_HOST="$(grep -E '^WEB_PUBLIC_HOST=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'"' \r' || true)"
  ENV_ALLOWED_HOSTS="$(grep -E '^WEB_ALLOWED_HOSTS=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'"' \r' || true)"
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --host)       HOST="${2:?}"; shift 2;;
    --san-dns)    EXTRA_DNS+=("${2:?}"); shift 2;;
    --san-ip)     EXTRA_IP+=("${2:?}"); shift 2;;
    --days)       DAYS="${2:?}"; shift 2;;
    --ca-days)    CA_DAYS="${2:?}"; shift 2;;
    --certs-dir)  CERTS_DIR="${2:?}"; shift 2;;
    --force-ca)   FORCE_CA=1; shift;;
    --print-san)  PRINT_SAN=1; shift;;
    -h|--help)    sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0;;
    *)            die "unknown arg: $1";;
  esac
done

[ -n "$HOST" ] || HOST="$ENV_PUBLIC_HOST"
[ -n "$HOST" ] || die "host 미지정 — --host 또는 .env 의 WEB_PUBLIC_HOST 필요"
[ -n "$CERTS_DIR" ] || CERTS_DIR="$PROJECT_ROOT/artifacts/certs"

command -v openssl >/dev/null 2>&1 || die "openssl 가 설치되어 있지 않다"

# --- SAN 목록 조립 ---
# 기준: host + (.env WEB_ALLOWED_HOSTS 의 DNS/IP) + 내장 기본 + 추가 플래그.
declare -A DNS_SET=()
declare -A IP_SET=()

is_ip() { printf '%s' "$1" | grep -qE '^([0-9]{1,3}\.){3}[0-9]{1,3}$|:'; }

add_san() {
  local v="$1"
  [ -n "$v" ] || return 0
  case "$v" in web) return 0;; esac   # docker 내부 서비스명은 SAN 불필요
  if is_ip "$v"; then IP_SET["$v"]=1; else DNS_SET["$v"]=1; fi
}

add_san "$HOST"
add_san "localhost"
DNS_SET["localhost"]=1
IP_SET["127.0.0.1"]=1

# .env WEB_ALLOWED_HOSTS (콤마구분) 흡수
if [ -n "$ENV_ALLOWED_HOSTS" ]; then
  IFS=',' read -ra _ah <<< "$ENV_ALLOWED_HOSTS"
  for h in "${_ah[@]}"; do add_san "$(printf '%s' "$h" | xargs)"; done
fi
for d in "${EXTRA_DNS[@]:-}"; do [ -n "$d" ] && DNS_SET["$d"]=1; done
for i in "${EXTRA_IP[@]:-}";  do [ -n "$i" ] && IP_SET["$i"]=1; done

# SAN 문자열 생성 (정렬해 결정적)
SAN_LINES=()
mapfile -t _dns_sorted < <(printf '%s\n' "${!DNS_SET[@]}" | sort)
mapfile -t _ip_sorted  < <(printf '%s\n' "${!IP_SET[@]}"  | sort)
for d in "${_dns_sorted[@]}"; do SAN_LINES+=("DNS:$d"); done
for i in "${_ip_sorted[@]}";  do SAN_LINES+=("IP:$i"); done
SAN_STR="$(IFS=,; echo "${SAN_LINES[*]}")"

if [ "$PRINT_SAN" = "1" ]; then
  echo "host=$HOST"
  echo "certs_dir=$CERTS_DIR"
  echo "SAN=$SAN_STR"
  exit 0
fi

log "project_root: $PROJECT_ROOT"
log "certs_dir:    $CERTS_DIR"
log "host:         $HOST"
log "leaf SAN:     $SAN_STR"
log "leaf days:    $DAYS  | CA days: $CA_DAYS"

ROOT_CA_CERT="$CERTS_DIR/rootCA.pem"
ROOT_CA_KEY="$CERTS_DIR/rootCA-key.pem"
LEAF_DIR="$CERTS_DIR/$HOST"
LEAF_CERT="$LEAF_DIR/fullchain.pem"
LEAF_KEY="$LEAF_DIR/privkey.pem"

mkdir -p "$CERTS_DIR" "$LEAF_DIR"

# --- 1) Root CA (멱등 — 존재하면 재사용, --force-ca 시에만 재생성) ---
if [ "$FORCE_CA" = "1" ] && { [ -f "$ROOT_CA_CERT" ] || [ -f "$ROOT_CA_KEY" ]; }; then
  log "WARN: --force-ca — 기존 Root CA 폐기. 테스터 전원이 새 Root CA 를 재설치해야 한다."
  rm -f "$ROOT_CA_CERT" "$ROOT_CA_KEY"
fi

if [ -f "$ROOT_CA_CERT" ] && [ -f "$ROOT_CA_KEY" ]; then
  log "Root CA 재사용: $ROOT_CA_CERT (기존 배포 신뢰 유지)"
else
  log "Root CA 신규 생성 ..."
  openssl genrsa -out "$ROOT_CA_KEY" 4096 2>/dev/null
  chmod 600 "$ROOT_CA_KEY"
  openssl req -x509 -new -nodes -key "$ROOT_CA_KEY" \
    -sha256 -days "$CA_DAYS" \
    -subj "/CN=mysql-ai Internal Root CA/O=mysql-ai" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -addext "subjectKeyIdentifier=hash" \
    -out "$ROOT_CA_CERT" 2>/dev/null
  log "Root CA 생성 완료 (유효 ${CA_DAYS}일)"
fi

# --- 2) leaf 인증서 (Root CA 서명) ---
log "leaf 인증서 생성 ..."
TMP_EXT="$(mktemp)"
trap 'rm -f "$TMP_EXT"' EXIT
cat > "$TMP_EXT" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=$SAN_STR
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

openssl genrsa -out "$LEAF_KEY" 2048 2>/dev/null
chmod 600 "$LEAF_KEY"

LEAF_CSR="$(mktemp)"; trap 'rm -f "$TMP_EXT" "$LEAF_CSR"' EXIT
openssl req -new -key "$LEAF_KEY" -subj "/CN=$HOST" -out "$LEAF_CSR" 2>/dev/null

LEAF_ONLY="$(mktemp)"; trap 'rm -f "$TMP_EXT" "$LEAF_CSR" "$LEAF_ONLY"' EXIT
openssl x509 -req -in "$LEAF_CSR" \
  -CA "$ROOT_CA_CERT" -CAkey "$ROOT_CA_KEY" -CAcreateserial \
  -days "$DAYS" -sha256 -extfile "$TMP_EXT" \
  -out "$LEAF_ONLY" 2>/dev/null

# fullchain = leaf + Root CA (web/caddy 가 client 에 체인 전송)
cat "$LEAF_ONLY" "$ROOT_CA_CERT" > "$LEAF_CERT"
chmod 644 "$LEAF_CERT"

# --- 3) 검증 (AC-0552: 체인 + SAN + EKU + 만료) ---
log "검증 ..."
openssl verify -CAfile "$ROOT_CA_CERT" "$LEAF_CERT" >/dev/null \
  || die "체인 검증 실패 — leaf 가 Root CA 로 서명되지 않았다"

# leaf 가 self-signed 가 아님을 보증 (issuer != subject)
LEAF_SUBJECT="$(openssl x509 -in "$LEAF_CERT" -noout -subject)"
LEAF_ISSUER="$(openssl x509 -in "$LEAF_CERT" -noout -issuer)"
[ "$LEAF_SUBJECT" != "$LEAF_ISSUER" ] || die "leaf 가 여전히 self-signed (issuer==subject)"

echo
log "=== 완료 ==="
openssl x509 -in "$LEAF_CERT" -noout -subject -issuer -dates -ext subjectAltName,extendedKeyUsage | sed 's/^/[tls-ca]   /' >&2
echo
log "배포 파일 (테스터 PC 에 설치): $ROOT_CA_CERT"
log "서버 leaf 인증서:             $LEAF_CERT  (web/caddy 가 자동 서빙)"

# --- 4) 테스터 신뢰 설치 번들 갱신 (TASK-20260617T083954-ai-claude-trust-bundle, 있으면 자동) ---
TRUST_BUNDLE_SH="$SCRIPT_DIR/trust-bundle.sh"
if [ -x "$TRUST_BUNDLE_SH" ] || [ -f "$TRUST_BUNDLE_SH" ]; then
  log "테스터 설치 번들 갱신 (trust-bundle.sh) ..."
  bash "$TRUST_BUNDLE_SH" --host "$HOST" --certs-dir "$CERTS_DIR" >&2 || \
    log "WARN: trust-bundle.sh 실패 — 번들 미갱신 (수동: bash bin/trust-bundle.sh)"
fi

log "다음 단계: web/caddy 재시작으로 새 인증서 + 번들 반영"
log "  (repo 루트에서) sudo docker compose up -d --no-deps web caddy"
