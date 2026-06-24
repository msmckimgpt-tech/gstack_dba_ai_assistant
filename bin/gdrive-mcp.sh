#!/usr/bin/env bash
# bin/gdrive-mcp.sh
#
# Google Drive MCP 서버 런처 (feature-0010 — TASK-20260623T190000-gdrive-foundation).
#
# 상태: SCAFFOLD (연동 미수행). 본 cycle 은 "각 계정의 Google Drive 에 연결할 수 있는
#   기반 구조"만 구축한다. 실제 Drive MCP 서버를 기동하지 않으며, 기본 비활성이다.
#   GDRIVE_MCP_ENABLED!=1 이면 즉시 no-op(exit 0)로 종료해 어떤 파이프라인도 깨지 않는다.
#
# 역할(활성화 시): playwright-mcp.sh 와 동형의 런처 — MCP 서버 프로세스를 stdio/HTTP 로
#   기동한다. 단 Drive 는 멀티테넌트(계정별 토큰)라, 단일 자격증명 서버와 다른 seam(A)을 쓴다:
#   에이전트가 호출 시점에 인증된 계정의 access_token 을 주입한다(상태 비저장 서버).
#   설계 정본 = unit/feature-0010-google-drive-integration/docs/DECISIONS.md (ADR seam A)
#   + unit/feature-0010-google-drive-integration/src/gdrive_mcp_seam.py.
#
# 활성화 절차(운영자, 배포 전 SECURITY.md §16 강화 TODO 충족 후):
#   1) Google Cloud Console 에서 Drive API 활성 + OAuth 동의화면(Drive scope) 구성.
#   2) .env.oauth 에 WEB_GDRIVE_* (client_id/secret/redirect_uri/scopes/ENABLED=1) 주입.
#   3) .env 에 GDRIVE_MCP_ENABLED=1 + 선택할 Drive MCP 서버 커맨드/이미지 지정.
#   4) docker-compose 'gdrive-mcp' 서비스(profile: gdrive) 또는 본 스크립트로 기동.
#
# Usage:
#   bash bin/gdrive-mcp.sh            # 활성 시 서버 기동, 비활성 시 no-op
#   GDRIVE_MCP_ENABLED=1 bash bin/gdrive-mcp.sh
#
# Exit codes: 0 = no-op(비활성) 또는 정상 기동, 2 = 활성인데 설정 누락(fail-loud)

set -euo pipefail

log() { printf "[gdrive-mcp] %s\n" "$*" >&2; }

ENABLED="${GDRIVE_MCP_ENABLED:-0}"
case "$(printf '%s' "$ENABLED" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|on) ENABLED=1 ;;
  *)             ENABLED=0 ;;
esac

if [ "$ENABLED" != "1" ]; then
  log "비활성(GDRIVE_MCP_ENABLED!=1) — scaffold no-op 종료. feature-0010 토대 단계 기본값."
  exit 0
fi

# --- 여기부터는 활성화(operator opt-in) 경로. 토대 단계에서는 도달하지 않는다. ---
GDRIVE_MCP_CMD="${GDRIVE_MCP_CMD:-}"
if [ -z "$GDRIVE_MCP_CMD" ]; then
  log "FAIL: GDRIVE_MCP_ENABLED=1 이지만 GDRIVE_MCP_CMD 가 비어 있다."
  log "      활성화하려면 Drive MCP 서버 실행 커맨드를 GDRIVE_MCP_CMD 로 지정하라."
  log "      (예: 'npx -y <google-drive-mcp-server> --transport http --port \${GDRIVE_MCP_PORT}')"
  log "      per-account 토큰 주입 seam 은 src/gdrive_mcp_seam.py 참조."
  exit 2
fi

log "Drive MCP 서버 기동: ${GDRIVE_MCP_CMD}"
# shellcheck disable=SC2086
exec ${GDRIVE_MCP_CMD}
