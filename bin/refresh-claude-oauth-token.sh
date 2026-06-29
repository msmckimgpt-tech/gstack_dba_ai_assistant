#!/usr/bin/env bash
# =============================================================================
# refresh-claude-oauth-token.sh — 개발 단계 전용 (2026-06-23, fallback+probe 2026-06-29)
# =============================================================================
# 지정된 계정의 Claude Code OAuth access token 을 읽어
# bedrock-gateway(litellm) 의 ANTHROPIC_API_KEY 로 주입한다.
#
# 계정 선택 정책 (2026-06-29 — 서비스 내부 폴백 + 라이브 probe):
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
# "사용 불가(실패)" 판정 — 후보 계정을 다음 두 단계로 검사하고, 하나라도 걸리면 건너뛴다:
#   [정적 검사] (cheap, 네트워크 없음)
#     1) credentials 파일 부재
#     2) accessToken 비어있음
#     3) 토큰이 이미 만료 또는 만료 임박 (남은 TTL ≤ CLAUDE_OAUTH_MIN_TTL 초, 기본 300s)
#   [라이브 probe] (CLAUDE_OAUTH_PROBE=1 기본 — 위 정적 검사 통과한 후보만 수행)
#     4) litellm 과 동일한 방식(sk-ant-oat → Authorization: Bearer +
#        anthropic-beta: oauth-2025-04-20)으로 Anthropic /v1/messages 에 max_tokens=1
#        ping 을 보내 HTTP 200 이 아니면 "사용 불가"로 본다.
#        → 이것이 핵심: 토큰은 유효(미만료)해도 구독 **사용량이 소진**되면 실제 호출이
#          429(rate_limit_error)로 거부된다. 정적 검사만으로는 이 상태를 못 잡아
#          "사용 가능"으로 오판하므로(2026-06-29 관측), 라이브 probe 로 실제 호출
#          가능 여부를 확인한 뒤 폴백한다.
#   claude-corp 가 회복되면(probe 200) 다음 실행에서 claude-corp 로 자동 복귀.
#
# 안전장치:
#   - 어떤 후보도 사용 불가면 .env/컨테이너를 **건드리지 않고** exit 1 (transient 장애로
#     동작 중인 게이트웨이를 깨뜨리지 않음 — 마지막으로 주입된 토큰 유지).
#   - CLAUDE_OAUTH_PROBE=0 으로 라이브 probe 비활성화 가능(정적 검사만 — probe 가
#     오작동하거나 네트워크 격리 환경일 때의 escape hatch).
#
# 환경변수 요약:
#   CLAUDE_OAUTH_ACCOUNT       단일 계정 강제(폴백 없음). 지정 시 ACCOUNTS 무시.
#   CLAUDE_OAUTH_ACCOUNTS      우선순위 목록(공백 구분). 기본 "claude-corp root".
#   CLAUDE_OAUTH_MIN_TTL       만료 임박 임계(초). 기본 300.
#   CLAUDE_OAUTH_PROBE         라이브 probe 활성(1/0). 기본 1.
#   CLAUDE_OAUTH_PROBE_MODEL   probe 모델. 기본 claude-haiku-4-5 (가장 저렴).
#   CLAUDE_OAUTH_PROBE_TIMEOUT probe HTTP timeout(초). 기본 20.
#
# 배경: 정식 배포 전 개발 단계에서, 위 계정의 Claude Code OAuth 로 LLM 백엔드를
#   운용한다(AGENTS.md / 사용자 지시). Anthropic OAuth access token 은
#   short-lived(~수시간) 이므로 주기적으로 갱신해야 게이트웨이가 안 끊긴다.
#
# 토큰이 바뀐 경우에만 컨테이너를 재생성한다(불필요한 recreate 방지).
# --check 옵션: .env/컨테이너 미변경, 어느 계정이 선택되는지만(probe 포함) 진단 출력.
# 배포 시: litellm_config.yaml 을 Bedrock provider 로 복구하고 본 cron 을 제거한다.
# =============================================================================
set -euo pipefail

REPO="/root/download/docker/mysql_ai_delegated_dev/repo"
ENV_FILE="$REPO/.env.bedrock"

MIN_TTL="${CLAUDE_OAUTH_MIN_TTL:-300}"
PROBE="${CLAUDE_OAUTH_PROBE:-1}"
PROBE_MODEL="${CLAUDE_OAUTH_PROBE_MODEL:-claude-haiku-4-5}"
PROBE_TIMEOUT="${CLAUDE_OAUTH_PROBE_TIMEOUT:-20}"

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
  MIN_TTL="$MIN_TTL" PROBE="$PROBE" PROBE_MODEL="$PROBE_MODEL" PROBE_TIMEOUT="$PROBE_TIMEOUT" \
  python3 - "$@" <<'PY'
import json, os, sys, time, urllib.request, urllib.error

min_ttl = int(os.environ.get('MIN_TTL', '300'))
probe_on = os.environ.get('PROBE', '1') not in ('0', '', 'false', 'no')
probe_model = os.environ.get('PROBE_MODEL', 'claude-haiku-4-5')
probe_timeout = float(os.environ.get('PROBE_TIMEOUT', '20'))
accounts = sys.argv[1:]

def cred_path(acct):
    return '/root/.claude/.credentials.json' if acct == 'root' \
        else f'/home/{acct}/.claude/.credentials.json'

def ts():
    return time.strftime('%Y-%m-%d %H:%M:%S')

def logd(msg):
    sys.stderr.write(f'{ts()} [refresh-oauth] {msg}\n')

def static_check(acct):
    """정적 검사. 사용 가능하면 (token, None), 아니면 (None, 사유)."""
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

def live_probe(token):
    """litellm 과 동일한 OAuth 호출을 흉내내 실제 사용 가능 여부 확인.
    사용 가능(HTTP 200)하면 (True, detail), 아니면 (False, detail)."""
    body = json.dumps({
        'model': probe_model,
        'max_tokens': 1,
        # Claude Code OAuth 토큰의 정식 사용 형태에 맞춰 식별 system prompt 포함
        # (현재는 없어도 인증되지만, 향후 요구 변화에 대한 안전 마진).
        'system': "You are Claude Code, Anthropic's official CLI for Claude.",
        'messages': [{'role': 'user', 'content': 'ping'}],
    }).encode()
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages', data=body, method='POST',
        headers={
            'content-type': 'application/json',
            'authorization': f'Bearer {token}',
            'anthropic-version': '2023-06-01',
            'anthropic-beta': 'oauth-2025-04-20',
        })
    try:
        with urllib.request.urlopen(req, timeout=probe_timeout) as r:
            return (r.status == 200), f'HTTP {r.status}'
    except urllib.error.HTTPError as e:
        detail = f'HTTP {e.code}'
        try:
            j = json.loads(e.read().decode())
            etype = (j.get('error') or {}).get('type')
            if etype:
                detail += f' {etype}'
        except Exception:
            pass
        return False, detail  # 429(사용량 만료)/401/403 등 → 사용 불가
    except Exception as e:  # noqa: BLE001 — 네트워크/timeout 등은 사용 불가로 보고 다음 후보
        return False, f'probe 예외 {type(e).__name__}: {e}'

for acct in accounts:
    tok, reason = static_check(acct)
    if not tok:
        logd(f'[{acct}] 건너뜀 — {reason}')
        continue
    if probe_on:
        ok, detail = live_probe(tok)
        if not ok:
            logd(f'[{acct}] 건너뜀 — 라이브 호출 실패 ({detail})')
            continue
        logd(f'[{acct}] 선택 — 라이브 호출 성공 ({detail})')
    else:
        logd(f'[{acct}] 선택 — 정적 검사 통과 (probe 비활성)')
    sys.stdout.write(f'{acct}\t{tok}')
    sys.exit(0)

logd(f'ERROR: 사용 가능한 계정 없음 (후보: {" ".join(accounts) or "(비어있음)"})')
sys.exit(1)
PY
}

# 1) 계정 선택 + 토큰 추출 (정적 검사 + 라이브 probe)
SEL="$(select_account $ACCOUNTS)" || { log "ERROR: 토큰 주입 중단 — 사용 가능한 계정 없음 (후보: $ACCOUNTS). 게이트웨이 미변경(현 토큰 유지)."; exit 1; }
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
