#!/usr/bin/env bash
# =============================================================================
# refresh-claude-oauth-token.sh — 개발 단계 전용 (2026-06-23, fallback 2026-06-29)
# =============================================================================
# 지정된 계정의 Claude Code OAuth access token 을 읽어
# bedrock-gateway(litellm) 의 ANTHROPIC_API_KEY 로 주입한다.
#
# 계정 선택 정책 (2026-06-29 변경 — 서비스 내부 폴백):
#   - 기본: claude-corp 계정을 우선 사용하고, 사용 불가 시 root 계정으로 자동 폴백.
#       claude-corp : 회사가 발급한 Claude Team 구독 계정 (/home/claude-corp/.claude)
#       root        : 개인 max 계정 (/root/.claude) — 회사 계정 사용 불가 시 폴백
#   - 우선순위는 CLAUDE_OAUTH_ACCOUNTS 로 직접 지정 가능 (공백 구분, 기본 "claude-corp root").
#   - CLAUDE_OAUTH_ACCOUNT 가 명시되면 그 계정만 사용 (폴백 없음 — 기존 수동 전환 호환).
#
#   이전(전): cron 에서 CLAUDE_OAUTH_ACCOUNT 를 켜고/끄며 대상 계정을 명시 전환했다.
#   이후(후): 스크립트가 내부에서 claude-corp 우선 + root 폴백을 수행하므로
#             cron 구성 수정 없이 계정 전환이 자동으로 일어난다.
#
# "사용 불가(실패)" 판정 — 다음 중 하나면 그 계정을 건너뛴다:
#   1) credentials 파일 부재
#   2) accessToken 비어있음
#   3) 토큰이 이미 만료 또는 만료 임박 (남은 TTL ≤ CLAUDE_OAUTH_MIN_TTL 초, 기본 300s)
#      → (3)이 핵심: claude-corp 의 Claude Code 가 갱신을 멈추면(구독 만료·미실행) 토큰이
#      만료되므로, 그 시점에 root 로 자동 전환되어 게이트웨이가 안 끊긴다.
#      claude-corp 가 회복되면(토큰 다시 유효) 다음 실행에서 claude-corp 로 자동 복귀.
#
# 배경: 정식 배포 전 개발 단계에서, 위 계정의 Claude Code OAuth 로 LLM 백엔드를
#   운용한다(AGENTS.md / 사용자 지시). Anthropic OAuth access token 은
#   short-lived(~수시간) 이므로 주기적으로 갱신해야 게이트웨이가 안 끊긴다.
#   해당 계정의 Claude Code 가 refresh token 으로 access token 을 자동 갱신하면,
#   본 스크립트가 그 최신 토큰을 게이트웨이에 반영한다.
#
# 토큰이 바뀐 경우에만 컨테이너를 재생성한다(불필요한 recreate 방지).
# --check 옵션: .env/컨테이너 미변경, 어느 계정이 선택되는지만 진단 출력.
# 배포 시: litellm_config.yaml 을 Bedrock provider 로 복구하고 본 cron 을 제거한다.
# =============================================================================
set -euo pipefail

REPO="/root/download/docker/mysql_ai_delegated_dev/repo"
ENV_FILE="$REPO/.env.bedrock"

# 토큰 만료 임박 임계(초). 이 시간 이내에 만료되는 토큰은 "실패"로 보고 다음 계정 폴백.
MIN_TTL="${CLAUDE_OAUTH_MIN_TTL:-300}"

# 계정 우선순위 결정
#   - CLAUDE_OAUTH_ACCOUNT 명시: 그 계정만 사용 (폴백 없음, 기존 수동 전환 호환)
#   - 아니면 CLAUDE_OAUTH_ACCOUNTS (기본 "claude-corp root") 순회
if [ -n "${CLAUDE_OAUTH_ACCOUNT:-}" ]; then
  ACCOUNTS="$CLAUDE_OAUTH_ACCOUNT"
else
  ACCOUNTS="${CLAUDE_OAUTH_ACCOUNTS:-claude-corp root}"
fi

DRY_RUN=0
[ "${1:-}" = "--check" ] && DRY_RUN=1

# 진단 로그는 stderr 로 — stdout 은 토큰 캡처 전용이므로 오염시키지 않는다.
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [refresh-oauth] $*" >&2; }

# 계정 우선순위를 순회해 첫 사용 가능 계정을 고른다.
#   stdout: "<account>\t<token>" (성공 시) — 토큰은 디스크에 쓰지 않고 메모리로만 전달
#   stderr: 계정별 진단 로그
#   exit  : 0=선택됨, 1=사용 가능 계정 없음
select_account() {
  MIN_TTL="$MIN_TTL" python3 - "$@" <<'PY'
import json, os, sys, time

min_ttl = int(os.environ.get('MIN_TTL', '300'))
accounts = sys.argv[1:]

def cred_path(acct):
    return '/root/.claude/.credentials.json' if acct == 'root' \
        else f'/home/{acct}/.claude/.credentials.json'

def ts():
    return time.strftime('%Y-%m-%d %H:%M:%S')

def logd(msg):
    sys.stderr.write(f'{ts()} [refresh-oauth] {msg}\n')

def usable(acct):
    """사용 가능하면 (token, None), 아니면 (None, 사유)."""
    cred = cred_path(acct)
    if not os.path.isfile(cred):
        return None, f'credentials 없음: {cred}'
    try:
        with open(cred) as f:
            d = json.load(f)
    except Exception as e:  # noqa: BLE001 — 손상/권한 등 모든 파싱 실패는 폴백 대상
        return None, f'credentials 파싱 실패: {e}'
    o = d.get('claudeAiOauth') or d
    tok = o.get('accessToken') or ''
    if not tok:
        return None, 'accessToken 비어있음'
    exp = o.get('expiresAt')
    if exp is not None:
        secs = exp / 1000 if exp > 1e12 else exp  # ms epoch 보정
        remaining = int(secs - time.time())
        if remaining <= min_ttl:
            return None, f'토큰 만료/임박 (남은 {remaining}s ≤ {min_ttl}s)'
    return tok, None

for acct in accounts:
    tok, reason = usable(acct)
    if tok:
        logd(f'[{acct}] 선택 — 사용 가능')
        sys.stdout.write(f'{acct}\t{tok}')
        sys.exit(0)
    logd(f'[{acct}] 건너뜀 — {reason}')

logd(f'ERROR: 사용 가능한 계정 없음 (후보: {" ".join(accounts) or "(비어있음)"})')
sys.exit(1)
PY
}

# 1) 계정 선택 + 토큰 추출
SEL="$(select_account $ACCOUNTS)" || { log "ERROR: 토큰 주입 중단 — 사용 가능한 계정 없음 (후보: $ACCOUNTS)"; exit 1; }
ACCOUNT="${SEL%%$'\t'*}"
TOKEN="${SEL#*$'\t'}"
[ -n "$ACCOUNT" ] && [ -n "$TOKEN" ] || { log "ERROR: 계정/토큰 추출 실패 (sel=$ACCOUNT)"; exit 1; }

# 2) 현재 게이트웨이가 들고 있는 토큰과 비교
CUR="$(grep -m1 '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"

# --check: 진단만 (변경 없음)
if [ "$DRY_RUN" = 1 ]; then
  if [ "$TOKEN" = "$CUR" ]; then
    log "[check] 선택 계정=$ACCOUNT — 게이트웨이 토큰과 동일 (recreate 불필요)"
  else
    log "[check] 선택 계정=$ACCOUNT — 게이트웨이 토큰과 다름 (실행 시 recreate)"
  fi
  exit 0
fi

# 변경 시에만 반영
if [ "$TOKEN" = "$CUR" ]; then
  log "[$ACCOUNT] 토큰 변경 없음 — skip (recreate 안 함)"
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
log "[$ACCOUNT] OAuth 토큰 갱신됨 → bedrock-gateway 재생성 완료"
