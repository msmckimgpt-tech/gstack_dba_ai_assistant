#!/usr/bin/env bash
# =============================================================================
# refresh-claude-oauth-token.sh — 개발 단계 전용 (2026-06-23, fallback+probe 2026-06-29)
# =============================================================================
# 지정된 계정의 Claude Code OAuth access token 을 읽어 bedrock-gateway(litellm) 에 주입한다.
#
# 주입 정책 (2026-07-03 insight-llm-fallback — **병행 주입** + 라이브 probe):
#   - **두 slot 을 동시에 채운다** (택일이 아니라 병행):
#       ANTHROPIC_API_KEY      ← 우선순위($ACCOUNTS, claude-corp 우선 + root 폴백) 첫 사용가능 계정.
#       ANTHROPIC_API_KEY_ROOT ← root 계정 전용 토큰.
#     litellm_config 가 claude-haiku-4(=ANTHROPIC_API_KEY, claude-corp) → claude-haiku-4-root
#     (=ANTHROPIC_API_KEY_ROOT, root Max) → edge-fallback(로컬 gemma) 로 **요청-레벨 fallback** 하므로,
#     한 계정이 burst rate-limit(429)로 막혀도 litellm 이 다음 계정/로컬로 즉시 우회한다. 두 토큰이
#     각 env 에 동시에 존재해야 이 체인이 성립하므로 병행 주입한다.
#       claude-corp : 회사가 발급한 Claude Team 구독 계정 (/home/claude-corp/.claude)
#       root        : 개인 Max 계정 (/root/.claude) — 2순위 fallback (rate-limit tier 가 더 높음)
#   - 각 slot 은 독립 검사(static+probe)해 사용가능 시에만 갱신(사용불가는 게이트웨이 미중단 위해 기존값
#     유지 — litellm 이 401/429 를 다음 fallback 으로 흡수). 두 slot 모두 사용불가면 미변경 + exit 1.
#   - 우선순위는 CLAUDE_OAUTH_ACCOUNTS 로 지정 가능 (공백 구분, 기본 "claude-corp root"). CLAUDE_OAUTH_ACCOUNT
#     명시 시 1순위 slot 은 그 계정만 사용(root slot 은 항상 root — litellm root deployment 용).
#
#   (이전 2026-06-29: 단일 slot 택일 폴백 → cron 이 계정 전환. 이후: 병행 주입 + litellm 요청-레벨 fallback.)
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

# insight-llm-fallback(2026-07-03): **병행 주입** — 1순위 slot(ANTHROPIC_API_KEY)과 2순위 slot
# (ANTHROPIC_API_KEY_ROOT)에 각각 토큰을 주입한다. litellm_config 의 claude-haiku-4(corp) →
# claude-haiku-4-root(root) → edge-fallback 요청-레벨 fallback 이 작동하려면 두 토큰이 각 env 에
# 동시에 존재해야 한다(한 계정이 burst 429 로 막혀도 litellm 이 다음 계정/로컬로 즉시 우회).
#   - ANTHROPIC_API_KEY      ← 기존 우선순위($ACCOUNTS, claude-corp 우선 + root 폴백) 첫 사용가능 계정.
#   - ANTHROPIC_API_KEY_ROOT ← root 계정 전용(claude-haiku-4-root deployment). 사용불가면 기존값 유지.
# 각 slot 은 독립 검사(static+probe)하고 사용가능 시에만 갱신(사용불가는 게이트웨이 미중단 위해 기존값
# 유지 — litellm 이 401/429 시 다음 fallback 으로 흡수). 하나라도 변경되면 bedrock-gateway 재생성 1회.

write_env_key() {  # $1=key $2=token — .env.bedrock 의 key= 안전 치환(없으면 추가). 특수문자 대응 python.
  python3 - "$ENV_FILE" "$1" "$2" <<'PY'
import sys
path, key, tok = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    lines = open(path).read().splitlines()
except FileNotFoundError:
    lines = []
out, done = [], False
for l in lines:
    if l.startswith(key + '='):
        out.append(key + '=' + tok); done = True
    else:
        out.append(l)
if not done:
    out.append(key + '=' + tok)
open(path, 'w').write('\n'.join(out) + '\n')
PY
}
cur_env_key() { grep -m1 "^$1=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true; }

# 1순위 slot: 기존 우선순위 순회(claude-corp 우선 + root 폴백) 첫 사용가능 계정.
SEL="$(select_account $ACCOUNTS)" || SEL=""
PRIMARY_ACCT="(none)"; PRIMARY_TOKEN=""
if [ -n "$SEL" ]; then PRIMARY_ACCT="${SEL%%$'\t'*}"; PRIMARY_TOKEN="${SEL#*$'\t'}"; fi

# 2순위 slot: root 계정 전용(claude-haiku-4-root deployment 용).
ROOT_SEL="$(select_account root)" || ROOT_SEL=""
ROOT_TOKEN=""
case "$ROOT_SEL" in *$'\t'*) ROOT_TOKEN="${ROOT_SEL#*$'\t'}";; esac

CUR_PRIMARY="$(cur_env_key ANTHROPIC_API_KEY)"
CUR_ROOT="$(cur_env_key ANTHROPIC_API_KEY_ROOT)"

# --check: 진단만 (변경 없음)
if [ "$DRY_RUN" = 1 ]; then
  log "[check] 1순위 ANTHROPIC_API_KEY=$PRIMARY_ACCT — $([ -z "$PRIMARY_TOKEN" ] && echo '사용불가·미변경' || { [ "$PRIMARY_TOKEN" = "$CUR_PRIMARY" ] && echo 동일 || echo '변경(실행 시 recreate)'; })"
  log "[check] 2순위 ANTHROPIC_API_KEY_ROOT=root — $([ -z "$ROOT_TOKEN" ] && echo '사용불가·미변경' || { [ "$ROOT_TOKEN" = "$CUR_ROOT" ] && echo 동일 || echo '변경(실행 시 recreate)'; })"
  exit 0
fi

if [ -z "$PRIMARY_TOKEN" ] && [ -z "$ROOT_TOKEN" ]; then
  log "ERROR: 두 slot 모두 사용 가능 계정 없음 — 게이트웨이 미변경(현 토큰 유지)."
  exit 1
fi

CHANGED=0
if [ -n "$PRIMARY_TOKEN" ] && [ "$PRIMARY_TOKEN" != "$CUR_PRIMARY" ]; then
  write_env_key ANTHROPIC_API_KEY "$PRIMARY_TOKEN"; CHANGED=1
  log "[$PRIMARY_ACCT → ANTHROPIC_API_KEY] 토큰 갱신"
fi
if [ -n "$ROOT_TOKEN" ] && [ "$ROOT_TOKEN" != "$CUR_ROOT" ]; then
  write_env_key ANTHROPIC_API_KEY_ROOT "$ROOT_TOKEN"; CHANGED=1
  log "[root → ANTHROPIC_API_KEY_ROOT] 토큰 갱신"
fi

if [ "$CHANGED" = 0 ]; then
  log "토큰 변경 없음(1순위=$PRIMARY_ACCT, root slot 동일) — skip (recreate 안 함)"
  exit 0
fi

# 토큰 변경 반영 — restart 는 env_file 재로드 안 하므로 반드시 재생성
cd "$REPO"
docker compose -f docker-compose.yml up -d --force-recreate bedrock-gateway >/dev/null 2>&1
log "OAuth 토큰 갱신 완료(1순위=$PRIMARY_ACCT, root slot=$([ -n "$ROOT_TOKEN" ] && echo '갱신/동일' || echo 미변경)) → bedrock-gateway 재생성"
