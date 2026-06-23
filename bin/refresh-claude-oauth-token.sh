#!/usr/bin/env bash
# =============================================================================
# refresh-claude-oauth-token.sh — 개발 단계 전용 (2026-06-23)
# =============================================================================
# claude-corp 계정(masangsoft.com)의 Claude Code OAuth access token 을 읽어
# bedrock-gateway(litellm) 의 ANTHROPIC_API_KEY 로 주입한다.
#
# 배경: 정식 배포 전 개발 단계에서, 회사가 발급한 Claude Team 구독 계정으로
#   LLM 백엔드를 운용한다(AGENTS.md / 사용자 지시). Anthropic OAuth access token
#   은 short-lived(~수시간) 이므로 주기적으로 갱신해야 게이트웨이가 안 끊긴다.
#   claude-corp 의 Claude Code 가 refresh token 으로 access token 을 자동 갱신하면,
#   본 스크립트가 그 최신 토큰을 게이트웨이에 반영한다.
#
# 토큰이 바뀐 경우에만 컨테이너를 재생성한다(불필요한 recreate 방지).
# 배포 시: litellm_config.yaml 을 Bedrock provider 로 복구하고 본 cron 을 제거한다.
# =============================================================================
set -euo pipefail

CRED="/home/claude-corp/.claude/.credentials.json"
REPO="/root/download/docker/mysql_ai_delegated_dev/repo"
ENV_FILE="$REPO/.env.bedrock"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [refresh-oauth] $*"; }

[ -f "$CRED" ] || { log "ERROR: credentials 없음: $CRED"; exit 1; }

# 1) claude-corp access token 추출 (출력에 토큰 노출 안 함)
TOKEN="$(python3 -c "import json,sys
d=json.load(open('$CRED'))
o=d.get('claudeAiOauth') or d
t=o.get('accessToken','')
sys.stdout.write(t)")"
[ -n "$TOKEN" ] || { log "ERROR: accessToken 비어있음"; exit 1; }

# 2) 현재 게이트웨이가 들고 있는 토큰과 비교 → 변경 시에만 반영
CUR="$(grep -m1 '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
if [ "$TOKEN" = "$CUR" ]; then
  log "토큰 변경 없음 — skip (recreate 안 함)"
  exit 0
fi

# 3) .env.bedrock 의 ANTHROPIC_API_KEY 갱신 (없으면 추가). 토큰에 특수문자 가능 → python 으로 안전 치환
python3 - "$ENV_FILE" "$TOKEN" <<'PY'
import sys
path, tok = sys.argv[1], sys.argv[2]
try:
    lines = open(path).read().splitlines()
except FileNotFoundError:
    lines = []
out, done = [], False
for l in lines:
    if l.startswith('ANTHROPIC_API_KEY='):
        out.append('ANTHROPIC_API_KEY=' + tok); done = True
    else:
        out.append(l)
if not done:
    out.append('ANTHROPIC_API_KEY=' + tok)
open(path, 'w').write('\n'.join(out) + '\n')
PY

# 4) 토큰 변경 반영 — restart 는 env_file 재로드 안 하므로 반드시 재생성
cd "$REPO"
docker compose -f docker-compose.yml up -d --force-recreate bedrock-gateway >/dev/null 2>&1
log "claude-corp OAuth 토큰 갱신됨 → bedrock-gateway 재생성 완료"
