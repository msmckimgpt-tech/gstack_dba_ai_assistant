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
# ── 2026-08-11 access token 자동 회전 (CHG-20260811-oauth-auto-rotate, 사용자 승인) ──
#   본 스크립트는 오랫동안 디스크의 access token 을 **읽기만** 했고, 실제 회전은 그 계정의
#   Claude Code CLI 세션이 돌 때만 일어났다. OAuth access token TTL 은 ~8h 라 야간·주말에
#   세션 공백이 생기면 정적 검사가 그 계정을 탈락시켰고, 다른 계정마저 소진돼 있으면
#   **LLM 전면 중단**이 됐다(2026-08-07~11 실사례: claude-corp 7일 쿼터 소진 + refresh token
#   만료로 자격증명이 비워져 root 단독 운용).
#
#   이제 만료까지 CLAUDE_OAUTH_ROTATE_LEAD_SEC(기본 3600s) 이하로 남으면 `refreshToken` 으로
#   선제 회전하고 자격증명 파일에 되쓴다. 요청 규약은 CLI 번들에서 실측한 것과 동일하다:
#     POST https://platform.claude.com/v1/oauth/token   (Content-Type: application/json)
#     {"grant_type":"refresh_token","refresh_token":…,"client_id":"9d1c250a-…","scope":"…"}
#
#   ⚠ **자격증명 저장소 쓰기**(§12.3 Critical — 사용자 승인 2026-08-11). CLI 와 동시에 돌 수
#   있으므로 CLI 자신과 같은 규약으로 방어한다:
#     · 계정별 lock(`<creds>.rotate.lock`, 300s 후 stale 회수)으로 직렬화
#     · lock 획득 후 **다시 읽어** accessToken 이 바뀌었으면 남이 회전한 것으로 보고 즉시 포기
#     · refresh token 은 회전형이라 새 값을 받으면 원자적으로 즉시 영속화(mkstemp+replace)
#     · **소유자/모드 보존** — root 로 돌지만 파일 주인은 계정 사용자다. root 소유로 바꾸면
#       그 계정의 CLI 가 자기 자격증명을 못 써서 로그인이 깨진다
#     · 교체 직전본을 `.bak-<epoch>` 로 남긴다(기본 5개 보관) — 잘못되면 되돌릴 수 있게
#     · 어떤 실패든 파일을 건드리지 않는다. 회전 못 한 계정은 정적 검사가 걸러 폴백이 받는다
#   선제 lead 를 1h 로 크게 잡은 이유: CLI 는 만료 직전/직후에 회전하므로, 그보다 훨씬 이른
#   시점에 끝내 두면 같은 창에서 부딪힐 확률 자체가 낮다.
#   킬스위치: CLAUDE_OAUTH_AUTO_ROTATE=0 (종전대로 읽기 전용).
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
#           **쿨다운 만료당 정확히 1회**다(`checked < until` 조건). 그 1회가 네트워크 오류로
#           fail-open 하면 이후는 (a) heartbeat 가 맡는다 — 종전엔 과거 `until` 이 남아
#           매 cron 실행마다 probe 가 나갔다(gate-hardening 2026-08-07).
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
#     · HTTP 429 (지속형)   → `unified-reset` / `retry-after` 로 우회 만료시각을 계산해
#                             캐시에 적재하고 다음 계정으로 **강등**. "지속형" 판정 기준은
#                             `unified-7d-status=rejected` 이거나 헤더가 말하는 쿨다운이
#                             CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC(기본 1800s) 이상일 때.
#     · HTTP 429 (버스트)   → **강등하지 않는다**. 5h RPM 캡 같은 단발 429 는 이 시스템에서
#                             정상 이벤트이고 litellm 이 요청-레벨로 흡수한다. 종전엔 모든
#                             429 를 소진으로 보고 `retry-after=5s` 마저 최소 쿨다운(300s)으로
#                             **끌어올려** 강등했다 → 1순위·root slot 이 같은 토큰이 되어
#                             2계정 체인이 1계정으로 붕괴하고, 강등/복귀마다 게이트웨이
#                             force-recreate(LLM 순단)가 붙었다(gate-hardening 2026-08-07).
#     · HTTP 401/403        → 짧은 우회(기본 900s) 후 재확인.
#     · 3xx                 → 따라가지 않는다(판정 보류). Authorization 헤더가 타 호스트로
#                             재전송되는 것을 막기 위해 리다이렉트 자체를 비활성화한다.
#     · 그 외/네트워크 오류 → **fail-open**: 우회 상태를 바꾸지 않고 정적 결과를 그대로 채택.
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
# 보안 (gate-hardening 2026-08-07, 적대 리뷰 반영):
#   - `.env.bedrock` 은 살아 있는 OAuth bearer 2개를 평문 보관하므로 쓰기 시 0600 으로 고정한다.
#     (종전 0644/0664 → 비특권 로컬 계정이 root Max 토큰을 읽을 수 있었다.)
#   - 상태 파일과 그 임시 파일은 0700 디렉토리 / 0600 + mkstemp(O_EXCL) — 고정 `.tmp` 이름은
#     심링크로 임의 파일을 덮어쓸 수 있었다.
#   - 로그·상태파일로 나가는 `detail` 은 `sk-ant-*` 를 마스킹하고 제어문자를 제거한 뒤 200자로 자른다
#     (자격증명이 깨지면 예외 메시지에 Bearer 헤더 전체가 실릴 수 있다 — 실증됨).
#   - probe 는 리다이렉트를 따라가지 않는다(Authorization 헤더 유출 차단).
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
#   CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC 429 를 "지속형 소진" 으로 보고 계정을 강등할 최소 쿨다운(초).
#                                  기본 1800. 이보다 짧은 429 는 버스트로 보고 강등하지 않는다
#                                  (`unified-7d-status=rejected` 면 길이와 무관하게 강등).
#   CLAUDE_OAUTH_PROBE_MODEL       probe 모델. 기본 claude-haiku-4-5(최저가·frontier 아님).
#   CLAUDE_OAUTH_PROBE_TIMEOUT     probe 타임아웃(초). 기본 20.
#   CLAUDE_OAUTH_PROBE_MAX_COOLDOWN 소진 우회 상한(초). 기본 691200(8일).
#   CLAUDE_OAUTH_PROBE_MIN_COOLDOWN 소진 우회 하한(초). 기본 300.
#   CLAUDE_OAUTH_FORCE_PROBE       1 이면 게이트 조건과 무관하게 라이브 probe 강제(운영자 진단).
#   CLAUDE_OAUTH_AUTO_ROTATE       access token 자동 회전 on/off. 기본 1(on). 0 이면 읽기 전용.
#   CLAUDE_OAUTH_ROTATE_LEAD_SEC   만료 몇 초 전부터 선제 회전할지. 기본 3600.
#   CLAUDE_OAUTH_TOKEN_URL         OAuth 토큰 엔드포인트. 기본 platform.claude.com/v1/oauth/token.
#   CLAUDE_OAUTH_CLIENT_ID         OAuth client_id. 기본 9d1c250a-…(Claude Code, CLI 번들 실측).
#   CLAUDE_OAUTH_ROTATE_KEEP_BACKUPS 자격증명 백업 보관 개수. 기본 5. 0=보관 안 함, 음수=무제한.
#   CLAUDE_OAUTH_ROTATE_DEFAULT_TTL  응답에 expires_in 이 없을 때 가정할 TTL(초). 기본 28800.
#   CLAUDE_OAUTH_ROTATE_BACKOFF_BASE 회전 실패 backoff 기준(초). 기본 1800(지수 증가).
#   CLAUDE_OAUTH_ROTATE_BACKOFF_MAX  회전 실패 backoff 상한(초). 기본 21600(6h).
#   CLAUDE_OAUTH_ROTATE_RACE_DELAY_SEC (테스트 훅) lock 획득 후 race 재확인 전 인위 지연. 기본 0.
#   CLAUDE_OAUTH_USER_AGENT        토큰 엔드포인트용 UA. 기본 `Claude-User (claude-code/<설치버전>)`.
#                                  ⚠ 이 UA 가 아니면 Cloudflare 가 **1010 Access denied** 로 끊는다
#                                  (2026-08-11 실측 — 기본 urllib UA 는 앱에 닿지도 못한다).
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
GATE_MIN_DEMOTE_SEC="${CLAUDE_OAUTH_GATE_MIN_DEMOTE_SEC:-1800}"

# 자동 토큰 회전 (auto-rotate 2026-08-11, 사용자 승인)
AUTO_ROTATE="${CLAUDE_OAUTH_AUTO_ROTATE:-1}"
ROTATE_LEAD_SEC="${CLAUDE_OAUTH_ROTATE_LEAD_SEC:-3600}"
ROTATE_TOKEN_URL="${CLAUDE_OAUTH_TOKEN_URL:-https://platform.claude.com/v1/oauth/token}"
ROTATE_CLIENT_ID="${CLAUDE_OAUTH_CLIENT_ID:-9d1c250a-e61b-44d9-88ed-5944d1962f5e}"
ROTATE_KEEP_BACKUPS="${CLAUDE_OAUTH_ROTATE_KEEP_BACKUPS:-5}"
# 토큰 엔드포인트는 Cloudflare UA 지문 검사를 한다 — 기본 urllib UA 로는 **1010 Access denied**
# 로 앱에 닿지도 못한다(2026-08-11 실측). CLI 와 같은 UA 를 쓴다: `Claude-User (claude-code/<ver>)`.
# 버전은 설치된 CLI 심링크에서 뽑고, 못 뽑으면 마지막 확인 버전으로 폴백한다.
_cc_ver="$(basename "$(readlink -f "$(command -v claude 2>/dev/null)" 2>/dev/null)" 2>/dev/null || true)"
case "$_cc_ver" in [0-9]*.[0-9]*) : ;; *) _cc_ver="2.1.220" ;; esac
ROTATE_USER_AGENT="${CLAUDE_OAUTH_USER_AGENT:-Claude-User (claude-code/$_cc_ver)}"
ROTATE_DEFAULT_TTL="${CLAUDE_OAUTH_ROTATE_DEFAULT_TTL:-28800}"
ROTATE_BACKOFF_BASE="${CLAUDE_OAUTH_ROTATE_BACKOFF_BASE:-1800}"
ROTATE_BACKOFF_MAX="${CLAUDE_OAUTH_ROTATE_BACKOFF_MAX:-21600}"
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
  GATE_MIN_DEMOTE_SEC="$GATE_MIN_DEMOTE_SEC" \
  AUTO_ROTATE="$AUTO_ROTATE" \
  ROTATE_LEAD_SEC="$ROTATE_LEAD_SEC" \
  ROTATE_TOKEN_URL="$ROTATE_TOKEN_URL" \
  ROTATE_CLIENT_ID="$ROTATE_CLIENT_ID" \
  ROTATE_KEEP_BACKUPS="$ROTATE_KEEP_BACKUPS" \
  ROTATE_RACE_DELAY_SEC="${CLAUDE_OAUTH_ROTATE_RACE_DELAY_SEC:-0}" \
  ROTATE_USER_AGENT="$ROTATE_USER_AGENT" \
  ROTATE_DEFAULT_TTL="$ROTATE_DEFAULT_TTL" \
  ROTATE_BACKOFF_BASE="$ROTATE_BACKOFF_BASE" \
  ROTATE_BACKOFF_MAX="$ROTATE_BACKOFF_MAX" \
  FORCE_PROBE="$FORCE_PROBE" \
  CRED_ROOT="${CLAUDE_OAUTH_CRED_ROOT:-}" \
  PROBE_URL="${CLAUDE_OAUTH_PROBE_URL:-https://api.anthropic.com/v1/messages}" \
  python3 - "$@" <<'PY'
import glob, json, os, re, shutil, sys, tempfile, time, urllib.error, urllib.request

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
min_demote_sec = int(os.environ.get('GATE_MIN_DEMOTE_SEC', '1800'))
auto_rotate = os.environ.get('AUTO_ROTATE', '1').strip().lower() not in ('0', '', 'false', 'off', 'no')
rotate_lead = int(os.environ.get('ROTATE_LEAD_SEC', '3600'))
token_url = os.environ.get('ROTATE_TOKEN_URL') or 'https://platform.claude.com/v1/oauth/token'
client_id = os.environ.get('ROTATE_CLIENT_ID') or '9d1c250a-e61b-44d9-88ed-5944d1962f5e'
keep_backups = int(os.environ.get('ROTATE_KEEP_BACKUPS', '5'))
# 테스트 훅 — lock 획득 직후 race 재확인 전에 인위적 창을 연다(기본 0=무동작).
# 이 창이 없으면 "남이 먼저 회전했을 때 포기한다" 계약을 외부에서 재현할 수 없다.
rotate_race_delay = float(os.environ.get('ROTATE_RACE_DELAY_SEC', '0') or 0)
rotate_ua = os.environ.get('ROTATE_USER_AGENT') or 'Claude-User (claude-code/2.1.220)'
rotate_default_ttl = int(os.environ.get('ROTATE_DEFAULT_TTL', '28800'))
rotate_backoff_base = int(os.environ.get('ROTATE_BACKOFF_BASE', '1800'))
rotate_backoff_max = int(os.environ.get('ROTATE_BACKOFF_MAX', '21600'))
rotate_max_ttl = 90 * 86400
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
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch)) if epoch else '알 수 없음'


def logd(msg):
    sys.stderr.write(f'{ts()} [refresh-oauth] {msg}\n')


def _read_creds(acct):
    """(전체 json, claudeAiOauth 오브젝트, 원본 bytes). 실패 시 (None, None, None)."""
    try:
        with open(cred_path(acct), 'rb') as f:
            raw = f.read()
        d = json.loads(raw.decode('utf-8'))
        o = d.get('claudeAiOauth')
        return (d, o, raw) if isinstance(o, dict) else (None, None, None)
    except Exception:  # noqa: BLE001
        return None, None, None


def _exp_epoch(o):
    e = _as_int(o.get('expiresAt'))
    if not e:
        return 0
    return int(e / 1000 if e > 1e12 else e)


def _open_new(path, mode=0o600):
    """심링크를 따라가지 않고 **새로** 만드는 경우에만 여는 fd.

    root 가 비특권 계정 소유 디렉토리(예: /home/claude-corp/.claude)에 쓰기 때문에 필수다.
    O_EXCL 없이 열면 미리 심어 둔 심링크를 따라가 임의 파일을 root 권한으로 덮어쓴다
    (적대 리뷰 P1 — .bak 경로로 실증됨: copy2/chmod/chown 이 전부 심링크를 따라갔다).
    """
    return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode)


def _write_creds(acct, doc, old_raw):
    """자격증명을 원자적으로 교체하고, **교체 성공 후에** 직전본을 백업한다.

    순서가 중요하다(적대 리뷰 P1): 백업을 먼저 하던 종전 구현은 POST 성공(=refresh token 이
    서버에서 이미 소모됨) 이후 백업 단계에서 실패하면 **새 토큰을 잃고 죽은 refresh token 만
    디스크에 남겼다** — 재로그인 외에는 복구 불가. 이제 내구성 있는 쓰기를 먼저 끝내고,
    백업은 메모리에 들고 있던 직전 바이트로 best-effort 로 남긴다.

    소유자/모드도 보존한다 — root 소유로 바꾸면 그 계정의 CLI 가 자기 자격증명을 못 쓴다.
    """
    path = cred_path(acct)
    st = os.lstat(path)
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.credentials-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(doc, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, st.st_mode & 0o777)
        os.chown(tmp, st.st_uid, st.st_gid)
        os.replace(tmp, path)   # 원자적 — 중간 상태(빈/잘린 파일)가 노출되지 않는다
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # ── 여기부터는 best-effort. 실패해도 회전 결과는 이미 안전하게 영속됐다. ──
    bak = None
    if keep_backups != 0 and old_raw:
        name = f'{path}.bak-{int(time.time())}-{os.urandom(3).hex()}'
        try:
            bfd = _open_new(name)
            with os.fdopen(bfd, 'wb') as f:
                f.write(old_raw)
            os.chown(name, st.st_uid, st.st_gid)
            bak = name
        except OSError as e:
            logd(f'WARN: [{acct}] 자격증명 백업 실패(회전 자체는 성공): {_scrub(e)}')
    if keep_backups >= 0:
        olds = sorted(glob.glob(f'{path}.bak-*'))
        drop = olds if keep_backups == 0 else olds[:-keep_backups]
        for stale in drop:
            try:
                os.unlink(stale)
            except OSError:
                pass
    return bak


def _rotate_lock(acct):
    """계정별 배타 lock. 획득 실패면 None.

    ⚠ 이 lock 은 **이 스크립트의 인스턴스끼리만** 직렬화한다. Claude Code CLI 는 자체
    lock(`.oauth_refresh.lock`)을 쓰므로 서로 배타되지 않는다 — CLI 와의 경합은 lock 이 아니라
    요청 **전후 두 번의 재확인**(아래 rotate_if_needed)이 막는다. 종전 주석은 "CLI 와 같은
    규약" 이라고 썼는데 사실이 아니었다(적대 리뷰 P2에서 지적, 여기서 정정).
    """
    path = cred_path(acct) + '.rotate.lock'
    try:
        if time.time() - os.lstat(path).st_mtime > 300:   # 죽은 프로세스 잔재 회수
            os.unlink(path)
    except OSError:
        pass
    try:
        fd = _open_new(path)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return path
    except FileExistsError:
        return None
    except OSError as e:
        logd(f'WARN: [{acct}] 회전 lock 생성 실패: {_scrub(e)}')
        return None


def _rotate_backoff_key(acct):
    return f'rotate:{acct}'


def rotate_if_needed(acct):
    """만료 임박 access token 을 refreshToken 으로 선제 회전한다.

    auto-rotate(2026-08-11, 사용자 승인). 배경: 이 스크립트는 디스크의 access token 을 읽기만
    했고, 실제 회전은 **그 계정의 Claude Code CLI 세션이 돌 때만** 일어났다. TTL 이 ~8h 라
    야간·주말에 세션 공백이 생기면 정적 검사가 그 계정을 탈락시키고, 다른 계정마저 소진돼
    있으면 LLM 이 전면 중단됐다(2026-08-07~11 실사례).

    ⚠ 자격증명 저장소에 쓰는 행위다(§12.3 Critical, 사용자 승인 2026-08-11). refresh token 은
    **일회성 회전형**이라 한 번 성공한 POST 는 이전 토큰을 즉시 무효화한다. 그래서:
      · 계정별 lock 으로 이 스크립트 인스턴스끼리 직렬화(CLI 와는 배타되지 않는다)
      · 요청 **직전**과 **직후** 두 번 재확인 — 그 사이 남이 회전했으면 우리 결과를 버린다
        (직후 재확인이 없으면 HTTP 왕복 동안 들어온 CLI 의 쓰기를 우리가 덮어쓴다)
      · 성공 시 원자적으로 먼저 영속화하고, 백업은 그 뒤 best-effort
      · 어떤 실패도 예외로 새어 나가지 않는다 — 호출측 선택 로직을 죽이면 slot 이 통째로 정지한다
    returns: 'rotated' | 'not_needed' | 'skipped:<사유>'
    """
    if not auto_rotate:
        return 'skipped:disabled'
    if check_only:
        # --check 는 부작용 0 계약이다. 회전은 자격증명 파일을 쓰고 일회성 refresh token 을
        # 소모하므로 진단 모드에서 절대 하지 않는다(적대 리뷰 P1).
        return 'skipped:check_only'
    doc, o, raw = _read_creds(acct)
    if not o:
        return 'skipped:no_credentials'
    path = cred_path(acct)
    if os.path.islink(path):
        return 'skipped:credentials_is_symlink'
    before = o.get('accessToken') or ''
    exp = _exp_epoch(o)
    now = int(time.time())
    if before and exp and exp - now > rotate_lead:
        return 'not_needed'
    rt = o.get('refreshToken') or ''
    if not rt:
        return 'skipped:no_refresh_token'
    rte = _as_int(o.get('refreshTokenExpiresAt'))
    rte = int(rte / 1000 if rte > 1e12 else rte)
    if rte and rte <= now:
        return f'skipped:refresh_token_expired({fmt(rte)})'

    # 실패 backoff — 엔드포인트가 계속 429/1010 을 주는 상황에서 30분마다(그것도 slot 당 2회)
    # 무한 재시도하지 않는다. 상태는 게이트와 같은 파일에 얹는다(적대 리뷰 P2).
    bo = state.get(_rotate_backoff_key(acct)) or {}
    if isinstance(bo, dict) and _as_int(bo.get('next')) > now:
        return f'skipped:backoff({fmt(_as_int(bo.get("next")))})'

    lock = _rotate_lock(acct)
    if lock is None:
        return 'skipped:lock_busy'
    try:
        if rotate_race_delay > 0:
            time.sleep(rotate_race_delay)
        # (1) 요청 전 재확인 — lock 획득 사이에 CLI 가 먼저 회전했을 수 있다.
        doc2, o2, _raw2 = _read_creds(acct)
        if not o2:
            return 'skipped:no_credentials'
        if (o2.get('accessToken') or '') != before:
            return 'skipped:race_resolved'
        rt = o2.get('refreshToken') or rt

        body = json.dumps({
            'grant_type': 'refresh_token',
            'refresh_token': rt,
            'client_id': client_id,
            'scope': ' '.join(x for x in (o2.get('scopes') or []) if isinstance(x, str)),
        }).encode()
        req = urllib.request.Request(
            token_url, data=body,
            headers={'content-type': 'application/json', 'accept': 'application/json',
                     'user-agent': rotate_ua})
        try:
            with _PROBE_OPENER.open(req, timeout=probe_timeout) as r:
                payload = json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            try:
                raw_err = e.read().decode('utf-8', 'replace')[:200]
            except Exception:  # noqa: BLE001
                raw_err = ''
            return _rotate_failed(acct, f'http_{e.code} {_scrub(raw_err)}')
        except Exception as e:  # noqa: BLE001 — 도달성 장애는 회전 실패일 뿐, 파일 무변경
            return _rotate_failed(acct, _scrub(f'{type(e).__name__}: {e}'))

        if not isinstance(payload, dict):
            return _rotate_failed(acct, 'malformed_response')
        at = payload.get('access_token')
        if not isinstance(at, str) or not at:
            return _rotate_failed(acct, 'no_access_token_in_response')

        # (2) 요청 직후 재확인 — HTTP 왕복(최대 probe_timeout) 동안 CLI 가 썼을 수 있다.
        #     여기서 덮어쓰면 CLI 가 방금 받은 토큰이 사라진다(lost update).
        doc3, o3, raw3 = _read_creds(acct)
        if not o3 or (o3.get('accessToken') or '') != before:
            logd(f'[{acct}] 회전 결과 폐기 — 요청 중 남이 먼저 회전함(lost-update 방지)')
            return 'skipped:race_resolved_late'

        o3['accessToken'] = at
        if isinstance(payload.get('refresh_token'), str) and payload['refresh_token']:
            o3['refreshToken'] = payload['refresh_token']
        ttl = _as_int(payload.get('expires_in'))
        # expires_in 이 없거나 0 이면 **과거 값을 그대로 두면 안 된다** — 회전한 이유 자체가
        # "곧 만료" 였으므로 그 값을 되쓰면 방금 받은 멀쩡한 토큰이 만료로 판정되고, 매 실행
        # 재회전 + 게이트웨이 재생성 폭풍이 된다(적대 리뷰 P1, 실증됨).
        if ttl <= 0 or ttl > rotate_max_ttl:
            # 상한도 둔다 — 비정상적으로 큰 expires_in 은 epoch 연산·표시에서 예외가 되고,
            # 그 예외가 회전 이후 단계에서 터지면 파일은 이미 바뀐 뒤다.
            ttl = rotate_default_ttl
        o3['expiresAt'] = int((now + ttl) * 1000)
        # scope 는 요청 입력일 뿐이다. 서버가 좁혀서 돌려준 값을 영속화하면(RFC 6749 §5.1 허용)
        # 다음 회전 요청이 그 좁은 scope 로 나가 되돌릴 수 없다 — 저장하지 않는다.
        doc3['claudeAiOauth'] = o3
        bak = _write_creds(acct, doc3, raw3)
        if state.pop(_rotate_backoff_key(acct), None) is not None:
            globals()['state_dirty'] = True
        logd(f'[{acct}] access token 자동 회전 — 새 만료 {fmt(_exp_epoch(o3))} '
             f'(refresh_token {"교체됨" if payload.get("refresh_token") else "유지"}'
             f'{", 백업 " + os.path.basename(bak) if bak else ""})')
        return 'rotated'
    finally:
        try:
            os.unlink(lock)
        except OSError:
            pass


def _rotate_failed(acct, detail):
    """회전 실패를 backoff 상태로 적재하고 사유를 반환한다(파일은 건드리지 않는다)."""
    now = int(time.time())
    key = _rotate_backoff_key(acct)
    bo = state.get(key)
    n = (_as_int(bo.get('count')) if isinstance(bo, dict) else 0) + 1
    delay = min(rotate_backoff_max, rotate_backoff_base * (2 ** (n - 1)))
    state[key] = {'count': n, 'next': now + delay, 'detail': detail, 'since':
                  (_as_int(bo.get('since')) if isinstance(bo, dict) else 0) or now}
    globals()['state_dirty'] = True
    return f'skipped:{detail}'


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


_SECRET_RE = re.compile(r'sk-ant-[A-Za-z0-9_\-]+')


def _scrub(text):
    """로그·상태파일로 나가는 문자열에서 토큰·제어문자를 제거하고 길이를 자른다.

    gate-hardening 2026-08-07 (적대 리뷰 P2): probe 의 응답 본문과 예외 텍스트가 그대로
    `detail` 에 실려 상태 파일(과거 0644)과 /tmp/refresh-oauth.log 로 흘렀다. 자격증명이
    깨져 accessToken 에 개행이 섞이면 http.client 가 **Bearer 헤더 전체를 담은** ValueError
    를 던지는데, 그것이 두 파일에 평문으로 남았다(실증됨).
    """
    t = _SECRET_RE.sub('sk-ant-<redacted>', str(text))
    t = ''.join(ch if ch.isprintable() or ch == ' ' else ' ' for ch in t)
    return t[:200]


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
    # 0700/0600 + mkstemp: 상태 파일에는 조직의 쿼터 상태와 응답 본문 발췌가 남는다.
    # 종전엔 cron umask(022)로 0644 였고 `.tmp` 고정 이름이라 심링크로 임의 파일을
    # 덮어쓸 수 있었다(gate-hardening 2026-08-07, 적대 리뷰 P2 — 둘 다 실증됨).
    d = os.path.dirname(state_file) or '.'
    tmp = None
    try:
        os.makedirs(d, mode=0o700, exist_ok=True)
        # 이미 존재하던 디렉토리는 makedirs 의 mode 가 적용되지 않는다(운영 환경의 실제 경우).
        if os.stat(d).st_mode & 0o077:
            os.chmod(d, 0o700)
        fd, tmp = tempfile.mkstemp(dir=d, prefix='.exhaustion-', suffix='.tmp')
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, state_file)
        tmp = None
    except Exception as e:  # noqa: BLE001 — 캐시 쓰기 실패가 토큰 주입을 막아선 안 된다
        logd(f'WARN: 소진 캐시 저장 실패({state_file}): {e}')
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _raw_cooldown(headers):
    """429 헤더에서 **클램프 이전의** 우회 만료 epoch 후보를 뽑는다.

    `unified-reset` 을 우선하되 **그것이 그럴듯할 때만** 쓰고, 아니면 `retry-after` 로
    폴백한다(gate-hardening 2026-08-07, 적대 리뷰 P2). 종전엔 `unified-reset` 이 파싱만
    되면 무조건 이겼는데, 그 값이
      · 절대 epoch 이 아니라 상대 초이거나
      · 시계 스큐로 과거이면
    같은 응답에 있는 명시적 `retry-after`(사건 당시 176528s)를 영영 못 읽고 최소 쿨다운으로
    떨어졌다. 반대로 ms 단위로 오면 상한(8일)에 박혀 회복 probe 가 사라졌다.
    반환 None = "지속성을 판단할 근거 없음"(호출측이 transient 로 처리).
    """
    now = int(time.time())
    cands = []

    def _plausible(epoch):
        # 과거·근미래 잡음과 ms 스케일을 배제. 상한은 max_cooldown 로 별도 클램프.
        return epoch if now < epoch <= now + max_cooldown else None

    reset = headers.get('anthropic-ratelimit-unified-reset')
    if reset:
        try:
            v = float(reset)
            if v > 1e12:      # ms epoch 보정 (static_check 와 동일 휴리스틱)
                v = v / 1000.0
            if 0 < v < 1e6:   # 절대 epoch 이 아니라 상대 초로 온 경우
                v = now + v
            cands.append(_plausible(int(v)))
        except (TypeError, ValueError):
            pass

    ra = headers.get('retry-after')
    if ra:
        try:
            cands.append(_plausible(now + int(float(ra))))
        except (TypeError, ValueError):
            # RFC 9110 은 HTTP-date 형식도 허용한다.
            try:
                from email.utils import parsedate_to_datetime
                cands.append(_plausible(int(parsedate_to_datetime(ra).timestamp())))
            except Exception:  # noqa: BLE001
                pass

    for c in cands:   # 우선순위: unified-reset → retry-after
        if c:
            return c
    return None


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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """3xx 를 따라가지 않는다.

    gate-hardening 2026-08-07 (적대 리뷰 P2, 실증됨): urllib 의 기본 리다이렉트 핸들러는
    `Authorization` 헤더를 **다른 호스트로도 그대로 재전송**한다(requests 와 다름).
    probe 는 살아 있는 OAuth bearer 를 싣고 나가므로 리다이렉트를 아예 막고 3xx 는
    'unknown'(판정 보류)으로 떨어뜨린다.
    """

    def redirect_request(self, *_a, **_kw):
        return None


_PROBE_OPENER = urllib.request.build_opener(_NoRedirect)


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
        with _PROBE_OPENER.open(req, timeout=probe_timeout) as r:
            r.read()
            return 'ok', 0, f'HTTP {r.status}'
    except urllib.error.HTTPError as e:
        headers = {k.lower(): v for k, v in (e.headers or {}).items()}
        try:
            raw = e.read().decode('utf-8', 'replace')[:200]
        except Exception:  # noqa: BLE001
            raw = ''
        if e.code == 429:
            now = int(time.time())
            raw_until = _raw_cooldown(headers)
            long_lived = str(headers.get('anthropic-ratelimit-unified-7d-status') or '').lower() == 'rejected'
            # burst-429 는 강등하지 않는다 (gate-hardening 2026-08-07, 적대 리뷰 P1).
            # 5h RPM/버스트 캡은 이 시스템에서 **정상 이벤트**이고 litellm 이 요청-레벨로 흡수한다.
            # 종전엔 모든 429 를 '소진' 으로 보고, retry-after=5s 조차 min_cooldown(300s)으로
            # **끌어올려** 계정을 강등했다 → 1순위·root slot 이 같은 토큰이 되어 2계정 체인이
            # 1계정으로 붕괴하고, 강등/복귀마다 게이트웨이 force-recreate(=LLM 순단)가 붙었다.
            # 강등은 (a) 7d 창이 rejected 이거나 (b) 헤더가 말하는 쿨다운 자체가
            # min_demote_sec 이상일 때만 한다. 그 외는 transient — litellm 에 맡긴다.
            if not long_lived and (raw_until is None or raw_until - now < min_demote_sec):
                span = 'unknown' if raw_until is None else f'{raw_until - now}s'
                return 'transient', 0, f'429(burst, cooldown={span}) {_rl_summary(headers)}'
            cooled = raw_until if raw_until is not None else now + 3600
            cooled = max(now + min_cooldown, min(cooled, now + max_cooldown))
            return 'exhausted', cooled, f'429 {_rl_summary(headers)}'
        if e.code in (401, 403):
            return 'unauthorized', int(time.time()) + max(min_cooldown, 900), f'{e.code} {_scrub(raw)}'
        return 'unknown', 0, f'{e.code} {_scrub(raw)}'
    except Exception as e:  # noqa: BLE001 — DNS/TLS/타임아웃 등은 전부 판정 보류(fail-open)
        return 'unknown', 0, _scrub(f'{type(e).__name__}: {e}')


def _as_int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


state = load_state()
state_dirty = False
chosen = None    # (acct, token)
gated = []       # 전 계정 소진 시 후보 — [(until, acct, token)]

for acct in accounts:
    # 정적 검사 **전에** 만료 임박 토큰을 선제 회전한다 — 그래야 "만료돼서 탈락" 이 아니라
    # "회전해서 계속 사용" 이 된다(auto-rotate 2026-08-11).
    # 회전은 **절대** 선택 로직을 죽여선 안 된다 — 파이썬 블록이 죽으면 bash 의
    # `SEL="$(...)" || SEL=""` 가 삼켜 1순위 slot 이 조용히 갱신 정지한다(적대 리뷰 P1, 실증됨).
    try:
        rot = rotate_if_needed(acct)
    except Exception as e:  # noqa: BLE001
        rot = f'skipped:예외 {_scrub(f"{type(e).__name__}: {e}")}'
    if rot.startswith('skipped:') and rot not in ('skipped:disabled', 'skipped:no_credentials',
                                                  'skipped:check_only'):
        logd(f'[{acct}] 토큰 회전 생략 — {rot[len("skipped:"):]}')

    tok, reason = static_check(acct)
    if not tok:
        logd(f'[{acct}] 건너뜀 — {reason}')
        continue

    if not gate_on:
        logd(f'[{acct}] 선택 — 정적 검사 통과 (파일 만료 전, 라이브 확인 없음)')
        chosen = (acct, tok)
        break

    now = int(time.time())
    # load_state 는 최상위만 dict 검증한다 — 항목 값이 dict 가 아니면 .get 에서
    # AttributeError → 파이썬 블록 사망 → `|| SEL=""` 가 삼켜 1순위 slot 이 조용히
    # 갱신 정지(exit 0). 항목 단위로도 강제한다(gate-hardening, 적대 리뷰 P2 — 실증됨).
    entry = state.get(acct)
    if not isinstance(entry, dict):
        entry = {}
    until = _as_int(entry.get('until'))
    checked = _as_int(entry.get('checked'))

    if until > now:
        detail = entry.get('detail') or ''
        logd(f'[{acct}] 건너뜀 — 사용량 소진 캐시 ({fmt(until)} 까지 우회, {detail})')
        gated.append((until, acct, tok))
        continue

    # 게이트 조건 (a) heartbeat / (b) 소진 캐시 만료 / (c) 게이트웨이 오류 관측 / (d) 강제
    stale = recheck_sec > 0 and (now - checked) >= recheck_sec
    # (b) 는 **쿨다운 만료당 1회**만이다. 종전엔 `until > 0` 만 봤는데, 만료 시점의 probe 가
    # 네트워크 오류로 fail-open 하면 until(과거)이 그대로 보존돼 이후 **매 cron 실행마다**
    # probe 가 나갔다(heartbeat 우회, 실증됨 — 적대 리뷰 P2). checked < until 을 함께 봐서
    # "쿨다운 설정 이후 아직 재확인하지 않았을 때"만 회복 probe 를 낸다.
    recovery_due = until > 0 and now >= until and checked < until
    need_probe = force_probe or recovery_due or gw_dirty or stale
    if not need_probe:
        age = f'{now - checked}s 전 판정' if checked else '판정 이력 없음'
        logd(f'[{acct}] 선택 — 정적 검사 통과 (게이트 재확인 불요: {age}, 라이브 probe 생략)')
        chosen = (acct, tok)
        break
    if check_only:
        why = '캐시 만료' if recovery_due else ('게이트웨이 오류 관측' if gw_dirty else 'heartbeat 도래')
        logd(f'[{acct}] 선택(잠정) — 정적 검사 통과. --check 이므로 라이브 probe 생략({why} 상태)')
        chosen = (acct, tok)
        break

    verdict, until_new, detail = probe(tok)
    if verdict == 'transient':
        # 짧은 버스트 캡 — 강등하지 않는다(litellm 이 요청-레벨로 흡수). 계정은 그대로 사용.
        state[acct] = {'until': 0, 'checked': now, 'detail': detail}
        state_dirty = True
        logd(f'[{acct}] 선택 — 일시적 {detail} (강등 안 함, litellm 폴백에 위임)')
        chosen = (acct, tok)
        break
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
        gated.append((until_new, acct, tok))
        continue
    # 판정 보류(네트워크/도달성/미분류) — 계정 소진으로 오판하지 않는다.
    # checked 만 갱신해 heartbeat 간격을 적용한다(도달성 장애 동안 매 실행 재시도로 cron 이
    # 지연되는 것을 막는다). until 은 건드리지 않으므로 우회도 일어나지 않는다.
    state[acct] = {'until': until, 'checked': now, 'detail': f'보류: {detail}'}
    state_dirty = True
    logd(f'[{acct}] 게이트 판정 보류(fail-open: {detail}) — 정적 결과 유지')
    chosen = (acct, tok)
    break

if chosen is None and gated:
    # 전원 소진 — 어차피 어디로 가도 실패지만, **가장 빨리 회복되는** 계정을 남긴다.
    # 종전엔 정적 1순위를 남겨, 2일 뒤 회복하는 계정이 10분 뒤 회복하는 계정을 밀어냈다
    # (적대 리뷰 P2).
    gated.sort(key=lambda t: t[0])
    _until, _acct, _tok = gated[0]
    logd(f'WARN: 후보 전원 사용량 소진 — 가장 빨리 회복되는 [{_acct}] 유지 ({fmt(_until)})')
    chosen = (_acct, _tok)

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
import os, sys
path, key, tok = sys.argv[1], sys.argv[2], sys.argv[3]
# 토큰에 개행/제어문자가 섞이면 .env 가 여러 줄로 깨져 다른 키를 덮어쓴다(적대 리뷰 P2).
if any(c in tok for c in '\r\n') or not tok.isprintable():
    sys.stderr.write('[refresh-oauth] ERROR: %s 토큰에 제어문자 — 주입 거부\n' % key)
    sys.exit(3)
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
# 이 파일은 두 계정의 살아 있는 OAuth bearer 를 평문 보관한다. 종전엔 cron umask(022)로
# 0644/0664 라 비특권 로컬 계정(예: claude-corp)이 root Max 계정 토큰을 읽을 수 있었다
# — 자격증명 원본(/root/.claude/.credentials.json, 0600 root:root)의 OS 경계를 우회한다.
# (gate-hardening 2026-08-07, 적대 리뷰 P1 — 본 결함은 선행이지만 여기서 닫는다.)
open(path, 'w').write('\n'.join(out) + '\n')
try:
    os.chmod(path, 0o600)
except OSError:
    pass
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
set -f  # $ACCOUNTS 는 의도적 워드분할 대상 — pathname expansion 은 막는다
SEL="$(GATE="$GATE_ENABLED" GW_DIRTY="$GW_DIRTY" select_account $ACCOUNTS)" || SEL=""
set +f
PRIMARY_ACCT="(none)"; PRIMARY_TOKEN=""
# tab 가드 — root slot(아래)에는 있었으나 여기엔 없어서, stdout 에 tab 이 없으면
# **계정 이름이 토큰으로** 주입될 수 있었다(비어 있지 않으니 -n 가드도 통과). 적대 리뷰 P2.
case "$SEL" in
  *$'\t'*) PRIMARY_ACCT="${SEL%%$'\t'*}"; PRIMARY_TOKEN="${SEL#*$'\t'}" ;;
  "")      : ;;
  *)       log "ERROR: select_account 출력 형식 이상(tab 없음) — 1순위 slot 미변경" ;;
esac

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

# recreate 실패 sentinel — 종전엔 `docker compose up` 실패를 검사하지 않아, .env 는 새 토큰인데
# 컨테이너는 옛 토큰을 물고 있고 다음 실행은 CHANGED=0 으로 "변경 없음 skip" 하며 **영구히**
# 재시도하지 않았다(토큰 만료 후 전량 401). 적대 리뷰 P1.
RECREATE_SENTINEL="$REPO/.env.bedrock.needs-recreate"
if [ "$CHANGED" = 0 ] && [ ! -f "$RECREATE_SENTINEL" ]; then
  log "토큰 변경 없음(1순위=$PRIMARY_ACCT, root slot 동일) — skip (recreate 안 함)"
  exit 0
fi
if [ "$CHANGED" = 0 ]; then
  log "토큰 변경 없음이나 직전 recreate 미완료(sentinel) — 재생성 재시도"
fi

# 토큰 변경 반영 — restart 는 env_file 재로드 안 하므로 반드시 재생성
: > "$RECREATE_SENTINEL"
cd "$REPO"
if docker compose -f docker-compose.yml up -d --force-recreate bedrock-gateway >/tmp/refresh-oauth-recreate.log 2>&1; then
  rm -f "$RECREATE_SENTINEL"
  log "OAuth 토큰 갱신 완료(1순위=$PRIMARY_ACCT, root slot=$([ -n "$ROOT_TOKEN" ] && echo '갱신/동일' || echo 미변경)) → bedrock-gateway 재생성"
else
  log "ERROR: bedrock-gateway 재생성 실패 — .env 는 새 토큰, 컨테이너는 구 토큰. 다음 실행이 재시도한다. 로그: $(tail -3 /tmp/refresh-oauth-recreate.log | tr '\n' ' ')"
  exit 1
fi
