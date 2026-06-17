#!/usr/bin/env bash
# trust-bundle.sh — 테스터용 Root CA 신뢰 설치 번들 조립
#   feature-0006-lan-proxy-access / TASK-20260617T083954-ai-claude-trust-bundle (REQ-0285, AC-0557~AC-0561)
#
# 목적
#   테스터가 PC 마다 수동으로 인증서를 옮기지 않도록, web 서버가 HTTP 로 제공할
#   "원클릭 설치 번들" 을 조립한다. 산출물은 caddy 가 `http://<host>/trust/` 로 서빙한다.
#   (최초 다운로드는 아직 Root CA 미설치 상태라 HTTP — 경고 없음. SECURITY.md §9.7 LAN 가정.)
#
#   ⚠ Root CA 배포는 신뢰 부트스트랩이라 채널 무결성이 본질적 한계다. 번들은 Root CA 의
#   SHA-256 지문을 페이지·스크립트에 노출하고, 설치 스크립트가 설치 전 지문을 재검증한다.
#   운영자는 지문을 신뢰 채널(사내 메신저 등)로 공유해 테스터가 대조하도록 안내한다.
#
# 산출물: <certs_dir>/../trust-bundle/  (= artifacts/trust-bundle, gitignore)
#   index.html                     OS 감지 + 다운로드 + 지문 안내 페이지
#   install-trust-windows.bat       자가-상승 + 임베드 인증서 + certutil 설치 (단일 파일)
#   install-trust-macos.command     sudo security add-trusted-cert (단일 파일)
#   rootCA.crt                      Root CA 공개 인증서 (Firefox/수동/Linux 용)
#
# Usage: bash bin/trust-bundle.sh [--certs-dir <dir>] [--host <fqdn>]
#   기본값은 tls-internal-ca.sh 와 동일하게 .env / git-common-dir 에서 해석.
set -euo pipefail
log() { printf '[trust-bundle] %s\n' "$*" >&2; }
die() { printf '[trust-bundle][ERROR] %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_COMMON_DIR="$(git -C "$SCRIPT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [ -n "$GIT_COMMON_DIR" ]; then
  MAIN_REPO_ROOT="$(cd "$(dirname "$GIT_COMMON_DIR")" && pwd)"
else
  MAIN_REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
PROJECT_ROOT="$(cd "$MAIN_REPO_ROOT/.." && pwd)"
ENV_FILE="$MAIN_REPO_ROOT/.env"
# 템플릿은 repo(소스) 에 있다 — main repo 기준.
TMPL_DIR="$MAIN_REPO_ROOT/unit/feature-0006-lan-proxy-access/src/trust-bundle"
# linked worktree 에서 실행 시 템플릿이 worktree 쪽에 있을 수 있다 → SCRIPT_DIR 기준 폴백.
[ -d "$TMPL_DIR" ] || TMPL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/unit/feature-0006-lan-proxy-access/src/trust-bundle"

HOST=""
CERTS_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST="${2:?}"; shift 2;;
    --certs-dir) CERTS_DIR="${2:?}"; shift 2;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0;;
    *) die "unknown arg: $1";;
  esac
done

if [ -z "$HOST" ] && [ -f "$ENV_FILE" ]; then
  HOST="$(grep -E '^WEB_PUBLIC_HOST=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'"' \r' || true)"
fi
[ -n "$HOST" ] || die "host 미지정 — --host 또는 .env WEB_PUBLIC_HOST 필요"
[ -n "$CERTS_DIR" ] || CERTS_DIR="$PROJECT_ROOT/artifacts/certs"

ROOT_CA="$CERTS_DIR/rootCA.pem"
[ -f "$ROOT_CA" ] || die "Root CA 부재: $ROOT_CA — 먼저 bin/tls-internal-ca.sh 실행"
[ -d "$TMPL_DIR" ] || die "템플릿 디렉토리 부재: $TMPL_DIR"
command -v openssl >/dev/null 2>&1 || die "openssl 필요"

OUT_DIR="$CERTS_DIR/../trust-bundle"
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

# --- 지문 / base64 산출 ---
FP_DISPLAY="$(openssl x509 -in "$ROOT_CA" -noout -fingerprint -sha256 | sed 's/^.*Fingerprint=//')"   # 콜론 구분 대문자
FP_HEX="$(printf '%s' "$FP_DISPLAY" | tr -d ':' | tr 'a-f' 'A-F')"
B64="$(openssl base64 -A -in "$ROOT_CA")"   # PEM 전체를 한 줄 base64

log "host:        $HOST"
log "bundle:      $OUT_DIR"
log "SHA-256:     $FP_DISPLAY"

# --- 치환 헬퍼 (base64 에 |,& 없음 — sed 안전) ---
render() {
  local src="$1" dst="$2"
  sed -e "s|__PUBLIC_HOST__|$HOST|g" \
      -e "s|__ROOTCA_SHA256__|$FP_DISPLAY|g" \
      -e "s|__ROOTCA_SHA256_HEX__|$FP_HEX|g" \
      -e "s|__ROOTCA_B64__|$B64|g" \
      "$src" > "$dst"
}

render "$TMPL_DIR/index.html.tmpl"                  "$OUT_DIR/index.html"
render "$TMPL_DIR/install-trust-windows.bat.tmpl"   "$OUT_DIR/install-trust-windows.bat"
render "$TMPL_DIR/install-trust-macos.command.tmpl" "$OUT_DIR/install-trust-macos.command"
chmod +x "$OUT_DIR/install-trust-macos.command"

# .bat 은 Windows cmd.exe 요건상 CRLF 줄바꿈이어야 한다 (LF 면 cmd 가 파일 위치를 잃어
# echo→cho·base64 가 명령으로 실행되는 파싱 붕괴 — TASK-20260617T083954-ai-claude-bat-encoding-fix). 템플릿은 ASCII 전용이라
# 코드페이지 무관. .command/​index.html 은 LF 유지(mac/web 정상).
sed -i 's/\r$//' "$OUT_DIR/install-trust-windows.bat"   # 기존 CR 제거(멱등)
sed -i 's/$/\r/'  "$OUT_DIR/install-trust-windows.bat"  # LF → CRLF
# ASCII 보장 검증 (비-ASCII 바이트가 섞이면 cmd 코드페이지 의존 회귀)
if LC_ALL=C grep -qP '[^\x00-\x7F]' "$OUT_DIR/install-trust-windows.bat"; then
  die "install-trust-windows.bat 에 비-ASCII 바이트 — 템플릿을 ASCII 전용으로 유지해야 함"
fi
cp "$ROOT_CA" "$OUT_DIR/rootCA.crt"
chmod 644 "$OUT_DIR/rootCA.crt"

# --- 무결성 자가검증: 임베드 base64 가 실제 Root CA 와 동일한지 ---
DECODED_FP="$(printf '%s' "$B64" | openssl base64 -d -A | openssl x509 -noout -fingerprint -sha256 | sed 's/^.*Fingerprint=//' | tr -d ':' | tr 'a-f' 'A-F')"
[ "$DECODED_FP" = "$FP_HEX" ] || die "임베드 base64 디코드 지문 불일치 — 번들 무효"

log "=== 완료 ==="
log "서빙 경로:   http://$HOST/trust/  (caddy file_server, HTTP — Root CA 미설치 상태 접근용)"
log "테스터 안내: 위 URL 접속 → OS 스크립트 실행(승인 1회). 지문 대조용 SHA-256:"
log "  $FP_DISPLAY"
ls -la "$OUT_DIR" | sed 's/^/[trust-bundle]   /' >&2
