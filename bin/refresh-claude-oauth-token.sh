#!/usr/bin/env bash
# =============================================================================
# refresh-claude-oauth-token.sh — 개발 단계 전용
#   (2026-06-23 도입 / static-check-only 2026-07-07 / 사용량-소진 게이트 2026-08-07)
# =============================================================================
# 지정된 계정의 Claude Code OAuth access token 을 읽어 bedrock-gateway(litellm) 에 주입한다.
#
# 주입 정책 (병행 주입):
#   - **두 slot 을 동시에 채운다** (택일이 아니라 병행):
#       ANTHROPIC_API_KEY      ← 우선순위($ACCOUNTS, claude-corp 우선 + root 폴백) 첫 사용가능 계정.
#       ANTHROPIC_API_KEY_ROOT ← root 계정 전용 토큰.
#     litellm_config 가 claude-haiku-4(=ANTHROPIC_API_KEY, claude-corp) → claude-haiku-4-root
#     (=ANTHROPIC_API_KEY_ROOT, root Max) → (edge 없음, 종단) 로 **요청-레벨 fallback** 하므로,
#     한 계정이 실패(401/429)해도 litellm 이 다음 계정으로 즉시 우회한다. 두 토큰이 각 env 에
#     동시에 존재해야 이 체인이 성립하므로 병행 주입한다.
#       claude-corp : 회사가 발급한 Claude Team 구독 계정 (/home/claude-corp/.claude)
#       root        : 개인 Max 계정 (/root/.claude) — 2순위 fallback
#   - 각 slot 은 사용가능 시에만 갱신(사용불가는 게이트웨이 미중단 위해 기존값 유지).
#     두 slot 모두 사용가능 계정이 없으면 미변경 + exit 1.
#   - 우선순위는 CLAUDE_OAUTH_ACCOUNTS 로 지정 가능 (공백 구분, 기본 "claude-corp root"). CLAUDE_OAUTH_ACCOUNT
#     명시 시 1순위 slot 은 그 계정만 사용(root slot 은 항상 root — litellm root deployment 용).
#
# "사용 불가(실패)" 판정 — 2단:
#   (A) 정적 검사(cheap, 네트워크 없음) — 항상 수행
#       1) credentials 파일 부재
#       2) accessToken 비어있음
#       3) 토큰이 이미 만료 또는 만료 임박 (남은 TTL ≤ CLAUDE_OAUTH_MIN_TTL 초, 기본 300s)
#   (B) 사용량 소진 게이트(라이브 1-probe) — **1순위 slot 후보에만**, 아래 §게이트 조건에서만
#
# ── 2026-07-07 라이브 probe 제거 (배경) ──────────────────────────────────────
#   이전(2026-06-29~2026-07-06)엔 정적 검사를 통과한 후보에 대해 Anthropic
#   /v1/messages 로 실제 max_tokens=1 ping 을 보내(계정 "사용량 소진"은 정적
#   검사로 못 잡으므로) 라이브 가용성까지 확인했다. 이 probe 가 24/7 30분
#   주기로 claude-corp 계정에 대해 **실 API 호출**을 발생시켜, claude-corp 의
#   5시간 rolling 사용 윈도우 경계가 :00/:30 격자에 계속 재고정되는 부작용이
#   있었다. 그래서 probe 를 전면 제거하고 정적 검사만 남겼다 — litellm 의
#   요청-레벨 `fallbacks:` 체인이 실제 401/429 시점에 반응형으로 우회하므로
#   "미리 찔러보는" probe 는 구조적으로 중복이라는 판단이었다.
#
# ── 2026-08-07 사용량-소진 게이트 도입 (CHG-20260807-oauth-exhaustion-gate) ──
#   위 판단의 구멍이 라이브에서 드러났다. 2026-08-07 claude-corp 의 **7일(주간)
#   쿼터가 100% 소진**됐다(실측 헤더: `anthropic-ratelimit-unified-7d-status=rejected`,
#   `7d-utilization=1.0`, `retry-after=176528` ≈ 2.04일). 자격증명 파일은 멀쩡하므로
#   정적 검사는 계속 통과 → 매 cron 이 claude-corp 를 1순위 slot 에 재주입 →
#   "게이트가 root 로 옮겨오지 않는" 상태가 리셋 시각까지 ~2일간 고착됐다.
#
#   litellm fallback 이 있어도 이 상태가 해로운 이유:
#     1) **비용/지연**: 모든 LLM 호출이 소진된 claude-corp 로 먼저 나가 429 를 받고
#        (num_retries=1 이라 2회) 그 뒤에야 root 로 우회한다 — 대화 한 턴의 모든
#        보조 단계(plan/classify/sql_*/answer/…)마다 왕복이 2배로 붙는다.
#     2) **폴백 없는 alias 는 즉시 전면 실패**: bare `claude-sonnet-4` / `claude-opus-5`
#        는 (의도적 격리로) root 폴백이 없다. 1순위 slot 이 소진 계정이면 이 경로는
#        우회 없이 그대로 죽는다.
#   → 소진이 "요청마다 반응형으로 흡수되는 일시 오류"가 아니라 **일(day) 단위로
#     지속되는 상태**일 때는, 계정 선택 자체를 옮기는 것이 맞다.
#
#   § 게이트 조건 — 라이브 probe 는 다음 중 하나일 때만 발생한다:
#       (a) 저빈도 heartbeat — 이 계정의 마지막 라이브 판정으로부터
#           CLAUDE_OAUTH_GATE_RECHECK_SEC(기본 3600s) 이상 지났다.
#       (b) 이 계정에 소진 캐시가 있고 그 만료 시각이 지났다(= 복구 확인 1회).
#       (c) 게이트웨이 최근 로그에 RateLimitError/AuthenticationError 가 잡혔다
#           (아래 관측 단계가 무료로 수집 — 체인 전체가 죽는 장애를 더 빨리 잡는 보조 신호).
#       (d) CLAUDE_OAUTH_FORCE_PROBE=1 (운영자 수동 진단).
#     소진 캐시가 유효한 동안(=until 이전)에는 **probe 없이** 그 계정을 건너뛴다 —
#     root 로 옮겨간 뒤에도 30분마다 claude-corp 로 되돌아가는 flapping 이 없고,
#     소진 기간 내내 라이브 호출이 0 이다.
#
#     ⚠ (c) 만으로는 부족하다 — 실측(2026-08-07 라이브): claude-corp 가 429 여도 litellm 이
#     root 로 **성공적으로 폴백하면 게이트웨이 로그에는 `200 OK` 한 줄만 남는다**
#     (폴백 사실은 응답 헤더 `x-litellm-attempted-fallbacks=1` / `x-litellm-model-group=
#     claude-haiku-4-chat-root` 에만 드러난다). 즉 "매 요청이 소진 계정을 먼저 때리고 있는"
#     바로 그 상태가 로그상으로는 완전 무증상이다. 그래서 (a) heartbeat 가 주 신호이고
#     (c) 는 체인 전체가 실패해 스택트레이스가 찍히는 경우를 조금 더 빨리 잡는 보조다.
#
#     § heartbeat 비용/부작용 — 1순위 후보에 대해 최대 시간당 1회, 최소 ping
#     (max_tokens=16, haiku). 2026-07-07 에 probe 를 없앤 이유는 30분 주기 호출이
#     claude-corp 의 5h rolling 윈도우를 :00/:30 격자에 재고정해
#     `session-keepalive-cron.sh`(07:35/12:35 정렬 핑)를 무력화한다는 것이었는데,
#     그 keepalive cron 은 현재 존재하지 않고(crontab 확인 2026-08-07) 서비스는 24/7 실
#     트래픽으로 이미 윈도우를 열어 둔다. 그럼에도 우려가 남으면
#     CLAUDE_OAUTH_GATE_RECHECK_SEC=0 으로 heartbeat 만 끄면 된다((b)(c)(d) 는 유지).
#
#   § 판정 → 상태
#     · HTTP 200            → 소진 캐시 해제, 그 계정을 1순위로 사용(복구 자동 승격).
#     · HTTP 429            → `anthropic-ratelimit-unified-reset`(epoch) 또는 `retry-after`
#                             로 우회 만료시각을 계산해 캐시에 적재하고 다음 계정으로.
#     · HTTP 401/403        → 짧은 우회(기본 900s) 후 재확인.
#     · 그 외/네트워크 오류 → **fail-open**: 상태를 바꾸지 않고 정적 결과를 그대로 채택.
#                             (2026-07-30 게이트웨이 DNS 34분 단절을 "계정 소진"으로
#                              오판해 계정을 옮기는 사고를 원천 차단 — 도달성 장애 ≠ 소진)
#
#   § 상태 파일 — CLAUDE_OAUTH_STATE_FILE (기본 /var/lib/dqa-llm-oauth/exhaustion.json).
#     `{"<account>": {"until": <epoch|0>, "checked": <epoch>, "detail": "..."}}`.
#     `until` 은 우회 만료(0=소진 아님), `checked` 는 마지막 라이브 판정 시각(heartbeat 기준).
#     소실되면 다음 실행이 heartbeat 조건으로 즉시 다시 채운다(내구성 요구 없음).
#
#   § 되돌리기 — CLAUDE_OAUTH_EXHAUSTION_GATE=0 이면 게이트 전체가 비활성이 되어
#     2026-07-07~2026-08-06 의 정적-검사-전용 동작으로 즉시 복귀한다.
#
# 안전장치:
#   - 어떤 후보도 사용 불가면 .env/컨테이너를 **건드리지 않고** exit 1 (transient 장애로
#     동작 중인 게이트웨이를 깨뜨리지 않음 — 마지막으로 주입된 토큰 유지).
#   - 모든 후보가 소진 게이트에 걸리면(전 계정 소진) 게이트를 무시하고 정적 1순위를
#     유지한다 — 어차피 어디로 가도 실패이므로, 주입을 멈춰 stale 토큰을 남기는 것보다
#     최신 토큰을 유지하는 편이 복구가 빠르다.
#
# 관측 (로그 기반, 실 API 호출 없음):
#   매 실행 시 bedrock-gateway 컨테이너의 최근 로그(docker compose logs — 로컬
#   컨테이너 stdout 을 읽을 뿐 네트워크/과금 없음)에서 RateLimitError /
#   AuthenticationError 발생 건수를 집계해, 0건이 아닐 때만 한 줄 요약을
#   남긴다(정상 시 무음 — 30분 주기 로그 비대화 방지). CLAUDE_OAUTH_OBS_WINDOW
#   로 조회 구간 조정 가능. 이 집계는 위 게이트 조건 (a) 의 입력이기도 하다.
#
# 환경변수 요약:
#   CLAUDE_OAUTH_ACCOUNT           단일 계정 강제(폴백 없음). 지정 시 ACCOUNTS 무시.
#   CLAUDE_OAUTH_ACCOUNTS          우선순위 목록(공백 구분). 기본 "claude-corp root".
#   CLAUDE_OAUTH_MIN_TTL           만료 임박 임계(초). 기본 300.
#   CLAUDE_OAUTH_OBS_WINDOW        관측 로그 조회 구간(`docker compose logs --since`). 기본 35m.
#   CLAUDE_OAUTH_EXHAUSTION_GATE   사용량-소진 게이트 on/off. 기본 1(on). 0 이면 정적 검사만.
#   CLAUDE_OAUTH_STATE_FILE        소진 캐시 경로. 기본 /var/lib/dqa-llm-oauth/exhaustion.json.
#   CLAUDE_OAUTH_GATE_RECHECK_SEC  heartbeat 간격(초). 기본 3600. 0 이면 heartbeat 비활성
#                                  (소진 캐시 만료·게이트웨이 오류·강제 probe 만 남는다).
#   CLAUDE_OAUTH_PROBE_MODEL       probe 모델. 기본 claude-haiku-4-5(최저가·frontier 아님).
#   CLAUDE_OAUTH_PROBE_TIMEOUT     probe 타임아웃(초). 기본 20.
#   CLAUDE_OAUTH_PROBE_MAX_COOLDOWN 소진 우회 상한(초). 기본 691200(8일).
#   CLAUDE_OAUTH_PROBE_MIN_COOLDOWN 소진 우회 하한(초). 기본 300.
#   CLAUDE_OAUTH_FORCE_PROBE       1 이면 게이트 조건과 무관하게 라이브 probe 강제(운영자 진단).
#   CLAUDE_OAUTH_CRED_ROOT         (테스트/스테이징 훅) credentials 탐색 루트. 지정 시
#                                  `<root>/<account>/.credentials.json` 를 읽는다. 미지정(기본)이면
#                                  실계정 경로(/root/.claude, /home/<acct>/.claude).
#   CLAUDE_OAUTH_PROBE_URL         (테스트/스테이징 훅) probe 엔드포인트. 기본 Anthropic /v1/messages.
#   CLAUDE_OAUTH_REPO              (테스트 훅) repo 루트. 기본 운영 경로. `.env.bedrock` 위치와
#                                  `docker compose` 실행 디렉토리를 결정한다.
#
# 배경: 정식 배포 전 개발 단계에서, 위 계정의 Claude Code OAuth 로 LLM 백엔드를
#   운용한다(AGENTS.md / 사용자 지시). Anthropic OAuth access token 은
#   short-lived(~수시간) 이므로 주기적으로 갱신해야 게이트웨이가 안 끊긴다.
#
# 토큰이 바뀐 경우에만 컨테이너를 재생성한다(불필요한 recreate 방지).
# --check 옵션: .env/컨테이너/상태파일 미변경 + 라이브 probe 없음. 캐시된 게이트 상태만
#   반영해 어느 계정이 선택되는지 진단 출력한다.
# 배포 시: litellm_config.yaml 을 Bedrock provider 로 복구하고 본 cron 을 제거한다.
# =============================================================================
set -euo pipefail

REPO="${CLAUDE_OAUTH_REPO:-/root/download/docker/mysql_ai_delegated_dev/repo}"
ENV_FILE="$REPO/.env.bedrock"

MIN_TTL="${CLAUDE_OAUTH_MIN_TTL:-300}"
OBS_WINDOW="${CLAUDE_OAUTH_OBS_WINDOW:-35m}"

# 사용량-소진 게이트 (CHG-20260807-oauth-exhaustion-gate)
GATE_ENABLED="${CLAUDE_OAUTH_EXHAUSTION_GATE:-1}"
STATE_FILE="${CLAUDE_OAUTH_STATE_FILE:-/var/lib/dqa-llm-oauth/exhaustion.json}"
PROBE_MODEL="${CLAUDE_OAUTH_PROBE_MODEL:-claude-haiku-4-5}"
PROBE_TIMEOUT="${CLAUDE_OAUTH_PROBE_TIMEOUT:-20}"
PROBE_MAX_COOLDOWN="${CLAUDE_OAUTH_PROBE_MAX_COOLDOWN:-691200}"
PROBE_MIN_COOLDOWN="${CLAUDE_OAUTH_PROBE_MIN_COOLDOWN:-300}"
GATE_RECHECK_SEC="${CLAUDE_OAUTH_GATE_RECHECK_SEC:-3600}"
FORCE_PROBE="${CLAUDE_OAUTH_FORCE_PROBE:-0}"

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

# 계정 우선순위를 순회해 정적 검사 + (1순위 slot 한정) 사용량-소진 게이트를 통과하는
# 첫 계정을 고른다.
#   stdout: "<account>\t<token>" (성공 시) — 토큰은 디스크에 쓰지 않고 메모리로만 전달
#   stderr: 계정별 진단 로그
#   exit  : 0=선택됨, 1=사용 가능 계정 없음
#   env   : GATE (1=소진 게이트 적용 / 0=정적 검사만), GW_DIRTY (게이트웨이 로그 오류 관측 여부)
select_account() {
  MIN_TTL="$MIN_TTL" \
  GATE="${GATE:-0}" \
  GW_DIRTY="${GW_DIRTY:-0}" \
  CHECK_ONLY="$DRY_RUN" \
  STATE_FILE="$STATE_FILE" \
  PROBE_MODEL="$PROBE_MODEL" \
  PROBE_TIMEOUT="$PROBE_TIMEOUT" \
  PROBE_MAX_COOLDOWN="$PROBE_MAX_COOLDOWN" \
  PROBE_MIN_COOLDOWN="$PROBE_MIN_COOLDOWN" \
  GATE_RECHECK_SEC="$GATE_RECHECK_SEC" \
  FORCE_PROBE="$FORCE_PROBE" \
  CRED_ROOT="${CLAUDE_OAUTH_CRED_ROOT:-}" \
  PROBE_URL="${CLAUDE_OAUTH_PROBE_URL:-https://api.anthropic.com/v1/messages}" \
  python3 - "$@" <<'PY'
import json, os, sys, time, urllib.error, urllib.request

min_ttl = int(os.environ.get('MIN_TTL', '300'))
gate_on = os.environ.get('GATE', '0').strip().lower() not in ('0', '', 'false', 'off', 'no')
gw_dirty = os.environ.get('GW_DIRTY', '0') == '1'
check_only = os.environ.get('CHECK_ONLY', '0') == '1'
force_probe = os.environ.get('FORCE_PROBE', '0').strip().lower() not in ('0', '', 'false', 'off', 'no')
state_file = os.environ.get('STATE_FILE', '')
probe_model = os.environ.get('PROBE_MODEL', 'claude-haiku-4-5')
probe_timeout = float(os.environ.get('PROBE_TIMEOUT', '20'))
max_cooldown = int(os.environ.get('PROBE_MAX_COOLDOWN', '691200'))
min_cooldown = int(os.environ.get('PROBE_MIN_COOLDOWN', '300'))
recheck_sec = int(os.environ.get('GATE_RECHECK_SEC', '3600'))
cred_root = os.environ.get('CRED_ROOT', '')  # 테스트/스테이징 훅 — 미지정이면 실계정 경로
probe_url = os.environ.get('PROBE_URL') or 'https://api.anthropic.com/v1/messages'
accounts = sys.argv[1:]

# OAuth frontier identity 게이트(Sonnet 5/Opus 5)는 system 첫 블록이 Claude Code identity 여야
# 200 이다. probe 모델은 haiku(비-frontier)라 필수는 아니지만, 모델을 바꿔도 게이트에 걸리지
# 않도록 항상 넣는다 — 넣어서 해로운 경우는 없다.
IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."


def cred_path(acct):
    if cred_root:
        return os.path.join(cred_root, acct, '.credentials.json')
    return '/root/.claude/.credentials.json' if acct == 'root' \
        else f'/home/{acct}/.claude/.credentials.json'


def ts():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def fmt(epoch):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch))


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


def load_state():
    if not state_file:
        return {}
    try:
        with open(state_file) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001 — 캐시 소실/손상은 "상태 없음"과 동치(내구성 요구 없음)
        return {}


def save_state(state):
    if not state_file or check_only:
        return
    try:
        os.makedirs(os.path.dirname(state_file) or '.', exist_ok=True)
        tmp = state_file + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, state_file)
    except Exception as e:  # noqa: BLE001 — 캐시 쓰기 실패가 토큰 주입을 막아선 안 된다
        logd(f'WARN: 소진 캐시 저장 실패({state_file}): {e}')


def _cooldown_until(headers):
    """429 응답 헤더에서 우회 만료 epoch 을 뽑는다. 없으면 1시간."""
    now = int(time.time())
    cand = None
    reset = headers.get('anthropic-ratelimit-unified-reset')
    if reset:
        try:
            cand = int(float(reset))
        except (TypeError, ValueError):
            cand = None
    if cand is None:
        ra = headers.get('retry-after')
        if ra:
            try:
                cand = now + int(float(ra))
            except (TypeError, ValueError):
                cand = None
    if cand is None:
        cand = now + 3600
    return max(now + min_cooldown, min(cand, now + max_cooldown))


def _rl_summary(headers):
    """어느 claim(5h/7d)이 거부됐는지 한 줄 요약 — 로그 판독용."""
    bits = []
    for span in ('5h', '7d'):
        st = headers.get(f'anthropic-ratelimit-unified-{span}-status')
        util = headers.get(f'anthropic-ratelimit-unified-{span}-utilization')
        if st:
            bits.append(f'{span}={st}' + (f'({util})' if util else ''))
    claim = headers.get('anthropic-ratelimit-unified-representative-claim')
    if claim:
        bits.append(f'claim={claim}')
    return ' '.join(bits) or 'rate_limit_error'


def probe(tok):
    """라이브 1-probe. returns (verdict, until_epoch, detail).

    verdict: 'ok' | 'exhausted' | 'unauthorized' | 'unknown'
    'unknown' 은 **판정 보류**(네트워크/도달성 장애 등) — 호출측이 fail-open 한다.
    """
    body = json.dumps({
        'model': probe_model,
        'max_tokens': 16,
        'system': [{'type': 'text', 'text': IDENTITY}],
        'messages': [{'role': 'user', 'content': 'ping'}],
    }).encode()
    req = urllib.request.Request(
        probe_url, data=body,
        headers={
            'authorization': 'Bearer ' + tok,
            'anthropic-version': '2023-06-01',
            'anthropic-beta': 'oauth-2025-04-20',
            'content-type': 'application/json',
        })
    try:
        with urllib.request.urlopen(req, timeout=probe_timeout) as r:
            r.read()
            return 'ok', 0, f'HTTP {r.status}'
    except urllib.error.HTTPError as e:
        headers = {k.lower(): v for k, v in (e.headers or {}).items()}
        try:
            raw = e.read().decode('utf-8', 'replace')[:200]
        except Exception:  # noqa: BLE001
            raw = ''
        if e.code == 429:
            return 'exhausted', _cooldown_until(headers), f'429 {_rl_summary(headers)}'
        if e.code in (401, 403):
            return 'unauthorized', int(time.time()) + max(min_cooldown, 900), f'{e.code} {raw}'
        return 'unknown', 0, f'{e.code} {raw}'
    except Exception as e:  # noqa: BLE001 — DNS/TLS/타임아웃 등은 전부 판정 보류(fail-open)
        return 'unknown', 0, f'{type(e).__name__}: {e}'


def _as_int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


state = load_state()
state_dirty = False
chosen = None          # (acct, token)
gated_fallback = None  # 전 계정 소진 시 되돌아갈 정적 1순위

for acct in accounts:
    tok, reason = static_check(acct)
    if not tok:
        logd(f'[{acct}] 건너뜀 — {reason}')
        continue

    if not gate_on:
        logd(f'[{acct}] 선택 — 정적 검사 통과 (파일 만료 전, 라이브 확인 없음)')
        chosen = (acct, tok)
        break

    now = int(time.time())
    entry = state.get(acct) or {}
    until = _as_int(entry.get('until'))
    checked = _as_int(entry.get('checked'))

    if until > now:
        detail = entry.get('detail') or ''
        logd(f'[{acct}] 건너뜀 — 사용량 소진 캐시 ({fmt(until)} 까지 우회, {detail})')
        if gated_fallback is None:
            gated_fallback = (acct, tok)
        continue

    # 게이트 조건 (a) heartbeat / (b) 소진 캐시 만료 / (c) 게이트웨이 오류 관측 / (d) 강제
    stale = recheck_sec > 0 and (now - checked) >= recheck_sec
    need_probe = force_probe or until > 0 or gw_dirty or stale
    if not need_probe:
        age = f'{now - checked}s 전 판정' if checked else '판정 이력 없음'
        logd(f'[{acct}] 선택 — 정적 검사 통과 (게이트 재확인 불요: {age}, 라이브 probe 생략)')
        chosen = (acct, tok)
        break
    if check_only:
        why = '캐시 만료' if until > 0 else ('게이트웨이 오류 관측' if gw_dirty else 'heartbeat 도래')
        logd(f'[{acct}] 선택(잠정) — 정적 검사 통과. --check 이므로 라이브 probe 생략({why} 상태)')
        chosen = (acct, tok)
        break

    verdict, until_new, detail = probe(tok)
    if verdict == 'ok':
        if until > 0:
            logd(f'[{acct}] 사용량 회복 확인(HTTP 200) — 1순위 복귀')
        else:
            logd(f'[{acct}] 선택 — 라이브 확인 통과 ({detail})')
        state[acct] = {'until': 0, 'checked': now, 'detail': detail}
        state_dirty = True
        chosen = (acct, tok)
        break
    if verdict in ('exhausted', 'unauthorized'):
        state[acct] = {'until': until_new, 'checked': now, 'detail': detail}
        state_dirty = True
        logd(f'[{acct}] 건너뜀 — 라이브 {detail} → {fmt(until_new)} 까지 우회')
        if gated_fallback is None:
            gated_fallback = (acct, tok)
        continue
    # 판정 보류(네트워크/도달성/미분류) — 계정 소진으로 오판하지 않는다.
    # checked 만 갱신해 heartbeat 간격을 적용한다(도달성 장애 동안 매 실행 재시도로 cron 이
    # 지연되는 것을 막는다). until 은 건드리지 않으므로 우회도 일어나지 않는다.
    state[acct] = {'until': until, 'checked': now, 'detail': f'보류: {detail}'}
    state_dirty = True
    logd(f'[{acct}] 게이트 판정 보류(fail-open: {detail}) — 정적 결과 유지')
    chosen = (acct, tok)
    break

if chosen is None and gated_fallback is not None:
    logd(f'WARN: 후보 전원 사용량 소진 — 게이트 무시하고 정적 1순위 [{gated_fallback[0]}] 유지')
    chosen = gated_fallback

if state_dirty:
    save_state(state)

if chosen is None:
    logd(f'ERROR: 사용 가능한 계정 없음 (후보: {" ".join(accounts) or "(비어있음)"})')
    sys.exit(1)

sys.stdout.write(f'{chosen[0]}\t{chosen[1]}')
sys.exit(0)
PY
}

# 병행 주입 — 1순위 slot(ANTHROPIC_API_KEY)과 2순위 slot(ANTHROPIC_API_KEY_ROOT)에 각각 토큰을
# 주입한다. litellm_config 의 claude-haiku-4(corp) → claude-haiku-4-root(root) 요청-레벨
# fallback 이 작동하려면 두 토큰이 각 env 에 동시에 존재해야 한다.
#   - ANTHROPIC_API_KEY      ← 우선순위($ACCOUNTS) 첫 사용가능 계정 (정적 검사 + 사용량-소진 게이트).
#   - ANTHROPIC_API_KEY_ROOT ← root 계정 전용(claude-*-root deployment). **게이트 미적용** —
#     이 slot 은 "체인 종단 = root" 라는 고정 배선이라 계정을 바꿀 여지가 없고, root 가 소진돼도
#     주입을 멈추면 stale 토큰만 남는다. 소진 여부는 1순위 slot 선택이 이미 반영한다.
# 각 slot 은 사용가능 시에만 갱신(사용불가는 게이트웨이 미중단 위해 기존값 유지 —
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
# 부수 효과: GW_DIRTY(=사용량-소진 게이트의 probe trigger 조건 (a))를 세팅한다.
GW_DIRTY=0
log_fallback_observability() {
  local logs rl_count auth_count
  logs="$(cd "$REPO" && docker compose -f docker-compose.yml logs --no-color --since "$OBS_WINDOW" bedrock-gateway 2>/dev/null)" || logs=""
  rl_count="$(printf '%s\n' "$logs" | grep -c 'RateLimitError' 2>/dev/null)" || rl_count=0
  auth_count="$(printf '%s\n' "$logs" | grep -c 'AuthenticationError' 2>/dev/null)" || auth_count=0
  if [ "$rl_count" != "0" ] || [ "$auth_count" != "0" ]; then
    GW_DIRTY=1
    log "[관측] 최근 ${OBS_WINDOW} bedrock-gateway 로그 — RateLimitError ${rl_count}건 / AuthenticationError ${auth_count}건 (litellm 요청-레벨 fallback 이 처리 — 조치 불요, 참고용)"
  fi
}
log_fallback_observability

# 1순위 slot: 우선순위 순회(claude-corp 우선 + root 폴백) 첫 사용가능 계정 — 소진 게이트 적용.
SEL="$(GATE="$GATE_ENABLED" GW_DIRTY="$GW_DIRTY" select_account $ACCOUNTS)" || SEL=""
PRIMARY_ACCT="(none)"; PRIMARY_TOKEN=""
if [ -n "$SEL" ]; then PRIMARY_ACCT="${SEL%%$'\t'*}"; PRIMARY_TOKEN="${SEL#*$'\t'}"; fi

# 2순위 slot: root 계정 전용(claude-*-root deployment 용) — 고정 배선이라 게이트 미적용.
ROOT_SEL="$(GATE=0 GW_DIRTY=0 select_account root)" || ROOT_SEL=""
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
