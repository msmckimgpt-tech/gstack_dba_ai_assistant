#!/usr/bin/env bash
# bin/conversation-mcp.sh
#
# Conversation API MCP 서버 런처 (feature-0023 — REQ-20260722-conversation-api-access).
#
# 이 제품의 "작업 화면 대화"(/api/ask 등)를 MCP tool 로 노출한다. 다른 AI 클라이언트가
# ask/new_conversation/list_conversations/get_history tool 로 assistant 와 대화한다.
# 대화 품질 조정 tool(conversation-quality-controls, 2026-07-28): list_capabilities /
# set_conversation_product / list_folders / create_folder / set_folder_instructions /
# move_conversation_to_folder / upload_attachment (+ ask 의 model·reasoning_level·product 인자).
# 인증은 Bearer API 토큰(feature-0023 Phase 1) — gdrive-mcp.sh 와 동형의 gated 런처.
#
# 기본 비활성: CONVERSATION_MCP_ENABLED!=1 이면 즉시 no-op(exit 0). 활성 시 필수 env
# (BASE_URL·TOKEN)가 없으면 fail-loud(exit 2).
#
# 활성화 절차(운영자):
#   1) bin/api-token-issue.sh --account <저권한 서비스계정> --label "<용도>" 로 토큰 발급.
#   2) .env.conversation-mcp (gitignored) 에 아래 값 주입:
#        CONVERSATION_MCP_ENABLED=1
#        CONVERSATION_API_BASE_URL=https://mysql-ai.company.local   # 또는 http://localhost:8000
#        CONVERSATION_API_TOKEN=mat_...                             # `/ai/connect` 발급 (구 matk_ 아님)
#
# ⚠ DEPRECATED (feature-0043, 2026-08-27): 이 런처는 `/api/ask` 축(서버 계정 LLM)이 살아
#   있을 때의 것이다. 그 LLM 은 차단됐으므로 이 구성으로는 답변이 오지 않는다.
#   권장 경로는 `https://<host>/api/ai/mcp` 를 AI 클라이언트에 URL 로 등록하는 것이다
#   (설치물·토큰 발급 모두 불요 — 표준 OAuth 로 자동 연결).
#        # CONVERSATION_API_VERIFY_TLS=0     # 사내 self-signed 시
#        # CONVERSATION_API_DEFAULT_MODEL=... # 선택
#   3) .mcp.json 의 conversation-api 서버로 등록되어 있으므로 MCP 클라이언트가 자동 기동.
#      (수동 실행: CONVERSATION_MCP_ENABLED=1 bash bin/conversation-mcp.sh)
#
# 보안: 토큰은 stdout/로그에 출력하지 않는다. env 로만 전달.
#
# Exit codes: 0 = no-op(비활성) 또는 정상 기동, 2 = 활성인데 설정 누락(fail-loud)

set -euo pipefail

log() { printf "[conversation-mcp] %s\n" "$*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# .env.conversation-mcp (gitignored, optional) 로드 — 있으면 env 주입.
ENV_FILE="$REPO_DIR/.env.conversation-mcp"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

ENABLED="${CONVERSATION_MCP_ENABLED:-0}"
case "$(printf '%s' "$ENABLED" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|on) ENABLED=1 ;;
  *)             ENABLED=0 ;;
esac

if [ "$ENABLED" != "1" ]; then
  log "비활성(CONVERSATION_MCP_ENABLED!=1) — no-op 종료. 활성화 절차는 이 파일 상단 주석 참조."
  exit 0
fi

if [ -z "${CONVERSATION_API_BASE_URL:-}" ] || [ -z "${CONVERSATION_API_TOKEN:-}" ]; then
  log "FAIL: CONVERSATION_MCP_ENABLED=1 이지만 CONVERSATION_API_BASE_URL / CONVERSATION_API_TOKEN 가 비어 있다."
  log "      bin/api-token-issue.sh 로 토큰 발급 후 .env.conversation-mcp 에 주입하라."
  exit 2
fi

SERVER_PY="$REPO_DIR/unit/feature-0023-conversation-api-access/src/conversation_mcp_server.py"
if [ ! -f "$SERVER_PY" ]; then
  log "FAIL: MCP 서버 파일이 없습니다: $SERVER_PY"
  exit 2
fi

log "conversation-api MCP 서버 기동 (base=${CONVERSATION_API_BASE_URL}, tls_verify=${CONVERSATION_API_VERIFY_TLS:-1})"
exec python3 "$SERVER_PY"
