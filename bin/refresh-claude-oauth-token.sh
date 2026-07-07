#!/usr/bin/env bash
# =============================================================================
# refresh-claude-oauth-token.sh — 개발 단계 전용 (2026-06-23, static-check-only 2026-07-07)
# =============================================================================
# 지정된 계정의 Claude Code OAuth access token 을 읽어 bedrock-gateway(litellm) 에 주입한다.
#
# 주입 정책 (병행 주입, 라이브 API 호출 없음):
#   - **두 slot 을 동시에 채운다** (택일이 아니라 병행):
#       ANTHROPIC_API_KEY      ← 우선순위($ACCOUNTS, claude-corp 우선 + root 폴백) 첫 사용가능 계정.
#       ANTHROPIC_API_KEY_ROOT ← root 계정 전용 토큰.
#     litellm_config 가 claude-haiku-4(=ANTHROPIC_API_KEY, claude-corp) → claude-haiku-4-root
#     (=ANTHROPIC_API_KEY_ROOT, root Max) → edge-fallback(로컬 gemma) 로 **요청-레벨 fallback** 하므로,
#     한 계정이 실패(401/429)해도 litellm 이 다음 계정/로컬로 즉시 우회한다. 두 토큰이 각 env 에
#     동시에 존재해야 이 체인이 성립하므로 병행 주입한다.
#       claude-corp : 회사가 발급한 Claude Team 구독 계정 (/home/claude-corp/.claude)
#       root        : 개인 Max 계정 (/root/.claude) — 2순위 fallback (rate-limit tier 가 더 높음)
#   - 각 slot 은 정적 검사(파일 만료)만으로 판정해 사용가능 시에만 갱신(사용불가는 게이트웨이
#     미중단 위해 기존값 유지). 두 slot 모두 사용불가면 미변경 + exit 1.
#   - 우선순위는 CLAUDE_OAUTH_ACCOUNTS 로 지정 가능 (공백 구분, 기본 "claude-corp root"). CLAUDE_OAUTH_ACCOUNT
#     명시 시 1순위 slot 은 그 계정만 사용(root slot 은 항상 root — litellm root deployment 용).
#
# "사용 불가(실패)" 판정 — 정적 검사(cheap, 네트워크 없음)만 수행:
#   1) credentials 파일 부재
#   2) accessToken 비어있음
#   3) 토큰이 이미 만료 또는 만료 임박 (남은 TTL ≤ CLAUDE_OAUTH_MIN_TTL 초, 기본 300s)
#
# ── 2026-07-07 라이브 probe 제거 ─────────────────────────────────────────────
#   이전(2026-06-29~2026-07-06)엔 정적 검사를 통과한 후보에 대해 Anthropic
#   /v1/messages 로 실제 max_tokens=1 ping 을 보내(계정 "사용량 소진"은 정적
#   검사로 못 잡으므로) 라이브 가용성까지 확인했다. 이 probe 가 24/7 30분
#   주기로 claude-corp 계정에 대해 **실 API 호출**을 발생시켜, claude-corp 의
#   5시간 rolling 사용 윈도우 경계가 :00/:30 격자에 계속 재고정되는 부작용이
#   있었다 — session-keepalive-cron.sh(07:35/12:35 핑)가 그 날의 첫 실호출이
#   되지 못해 리셋 시각이 예측 불가하게 드리프트했다.
#
#   이 probe 는 2026-07-03 insight-llm-fallback 이후 구조적으로 중복이었다 —
#   litellm_config.yaml 의 `fallbacks:` 체인(요청-레벨, 반응형)이 실제 호출이
#   실패(401/429)하는 시점에 이미 다음 계정/로컬로 우회한다. litellm 소스
#   (router.py `should_retry_this_error` / `async_function_with_fallbacks_common_utils`)
#   확인 결과 AuthenticationError(401)·RateLimitError(429) 모두 예외 타입과
#   무관하게 정상적으로 fallback 경로를 탄다(ContextWindowExceededError /
#   ContentPolicyViolationError 만 별도 특별 처리). 즉 probe 가 "미리 찔러보고"
#   판단하던 것을, litellm 이 매 실제 요청마다 진짜 트래픽 기준으로 더 정확하게
#   반응형으로 이미 수행하고 있었다.
#
#   따라서 본 스크립트는 static_check() 만으로 판정한다. 사용량이 소진된
#   계정도 (파일이 만료되기 전까지는) ANTHROPIC_API_KEY 에 계속 주입되지만,
#   그 계정으로의 실제 요청이 401/429 를 받으면 litellm 이 즉시 다음
#   deployment 로 우회하므로 서비스 영향은 없다. claude-corp 복귀도 별도
#   로직이 불필요하다 — 자격증명 파일이 유효한 한 매 실행마다 계속 1순위로
#   주입되므로, 계정이 회복되면 litellm 이 다음 실제 요청부터 자동으로
#   claude-corp 를 다시 성공시킨다.
#
# 안전장치:
#   - 어떤 후보도 사용 불가면 .env/컨테이너를 **건드리지 않고** exit 1 (transient 장애로
#     동작 중인 게이트웨이를 깨뜨리지 않음 — 마지막으로 주입된 토큰 유지).
#
# 관측 (로그 기반, 실 API 호출 없음):
#   매 실행 시 bedrock-gateway 컨테이너의 최근 로그(docker compose logs — 로컬
#   컨테이너 stdout 을 읽을 뿐 네트워크/과금 없음)에서 RateLimitError /
#   AuthenticationError 발생 건수를 집계해, 0건이 아닐 때만 한 줄 요약을
#   남긴다(정상 시 무음 — 30분 주기 로그 비대화 방지). CLAUDE_OAUTH_OBS_WINDOW
#   로 조회 구간 조정 가능.
#
# 환경변수 요약:
#   CLAUDE_OAUTH_ACCOUNT       단일 계정 강제(폴백 없음). 지정 시 ACCOUNTS 무시.
#   CLAUDE_OAUTH_ACCOUNTS      우선순위 목록(공백 구분). 기본 "claude-corp root".
#   CLAUDE_OAUTH_MIN_TTL       만료 임박 임계(초). 기본 300.
#   CLAUDE_OAUTH_OBS_WINDOW    관측 로그 조회 구간(`docker compose logs --since`). 기본 35m.
#
# 배경: 정식 배포 전 개발 단계에서, 위 계정의 Claude Code OAuth 로 LLM 백엔드를
#   운용한다(AGENTS.md / 사용자 지시). Anthropic OAuth access token 은
#   short-lived(~수시간) 이므로 주기적으로 갱신해야 게이트웨이가 안 끊긴다.
#
# 토큰이 바뀐 경우에만 컨테이너를 재생성한다(불필요한 recreate 방지).
# --check 옵션: .env/컨테이너 미변경, 어느 계정이 선택되는지만(정적 검사) 진단 출력.
# 배포 시: litellm_config.yaml 을 Bedrock provider 로 복구하고 본 cron 을 제거한다.
# =============================================================================
set -euo pipefail

REPO="/root/download/docker/mysql_ai_delegated_dev/repo"
ENV_FILE="$REPO/.env.bedrock"

MIN_TTL="${CLAUDE_OAUTH_MIN_TTL:-300}"
OBS_WINDOW="${CLAUDE_OAUTH_OBS_WINDOW:-35m}"

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

# 계정 우선순위를 순회해 정적 검사를 통과하는 첫 계정을 고른다(라이브 API 호출 없음).
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

for acct in accounts:
    tok, reason = static_check(acct)
    if not tok:
        logd(f'[{acct}] 건너뜀 — {reason}')
        continue
    logd(f'[{acct}] 선택 — 정적 검사 통과 (파일 만료 전, 라이브 확인 없음)')
    sys.stdout.write(f'{acct}\t{tok}')
    sys.exit(0)

logd(f'ERROR: 사용 가능한 계정 없음 (후보: {" ".join(accounts) or "(비어있음)"})')
sys.exit(1)
PY
}

# 병행 주입 — 1순위 slot(ANTHROPIC_API_KEY)과 2순위 slot(ANTHROPIC_API_KEY_ROOT)에 각각 토큰을
# 주입한다. litellm_config 의 claude-haiku-4(corp) → claude-haiku-4-root(root) → edge-fallback
# 요청-레벨 fallback 이 작동하려면 두 토큰이 각 env 에 동시에 존재해야 한다.
#   - ANTHROPIC_API_KEY      ← 기존 우선순위($ACCOUNTS, claude-corp 우선 + root 폴백) 첫 사용가능 계정.
#   - ANTHROPIC_API_KEY_ROOT ← root 계정 전용(claude-haiku-4-root deployment). 사용불가면 기존값 유지.
# 각 slot 은 정적 검사만 하고 사용가능 시에만 갱신(사용불가는 게이트웨이 미중단 위해 기존값 유지 —
# litellm 이 401/429 시 다음 fallback 으로 흡수). 하나라도 변경되면 bedrock-gateway 재생성 1회.

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

# 관측 (로그 기반, 실 API 호출 없음): bedrock-gateway 컨테이너의 최근 로그에서
# RateLimitError/AuthenticationError 발생 건수를 집계 — 0건이면 무음(로그 비대화 방지).
log_fallback_observability() {
  local logs rl_count auth_count
  logs="$(cd "$REPO" && docker compose -f docker-compose.yml logs --no-color --since "$OBS_WINDOW" bedrock-gateway 2>/dev/null)" || logs=""
  rl_count="$(printf '%s\n' "$logs" | grep -c 'RateLimitError' 2>/dev/null)" || rl_count=0
  auth_count="$(printf '%s\n' "$logs" | grep -c 'AuthenticationError' 2>/dev/null)" || auth_count=0
  if [ "$rl_count" != "0" ] || [ "$auth_count" != "0" ]; then
    log "[관측] 최근 ${OBS_WINDOW} bedrock-gateway 로그 — RateLimitError ${rl_count}건 / AuthenticationError ${auth_count}건 (litellm 요청-레벨 fallback 이 처리 — 조치 불요, 참고용)"
  fi
}
log_fallback_observability

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
