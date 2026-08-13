#!/usr/bin/env bash
# feature-0041 — 외부 AI 도구 표면 전 구간 e2e (사람 1회 개입).
#
# 인가 단계만 사람이 브라우저로 하고 나머지는 이 스크립트가 한다. 그 한 단계를 자동화하지
# 않는 것이 설계다 — 신원이 "우리 로그인 세션" 이라는 축이 거기서 생긴다.
#
# 사용: bash unit/feature-0041-external-ai-tool-surface/scripts/e2e-authorize.sh
# 상세: unit/feature-0041-external-ai-tool-surface/docs/E2E_RUNBOOK.md
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck disable=SC1091
[ -f .env ] && source .env 2>/dev/null || true
HOST="${WEB_PUBLIC_HOST:-mysql-ai.company.local}"
BASE="https://${HOST}"
REDIRECT="http://127.0.0.1:8765/cb"
# codex P1 — 이 스크립트는 access/refresh token 을 실어 보낸다. `-k`(검증 생략)로 고정하면
# 그 토큰이 MITM 에 무방비다. 사내 rootCA 가 있으면 **검증한다**; 없을 때만 경고와 함께 -k.
CA_PEM="${WEB_TLS_CA_FILE:-$REPO_ROOT/../artifacts/certs/rootCA.pem}"
if [ -f "$CA_PEM" ]; then
  CURL=(curl -s --max-time 30 --cacert "$CA_PEM")
  TLS_MODE="verified (--cacert $CA_PEM)"
else
  CURL=(curl -sk --max-time 30)
  TLS_MODE="UNVERIFIED (-k) — rootCA 를 찾지 못했습니다"
fi

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
row()  { printf '  %-22s %s\n' "$1" "$2"; }
fail() { printf '\n\033[31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

say "0) 대상 확인"
row "base" "$BASE"
row "TLS" "$TLS_MODE"
case "$TLS_MODE" in UNVERIFIED*)
  printf '\033[33m  ⚠ TLS 미검증 상태로 토큰을 전송합니다. 사내 CA 경로를 WEB_TLS_CA_FILE 로 주세요.\033[0m\n' ;;
esac
code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$BASE/livez") || fail "서비스에 도달 불가"
row "GET /livez" "$code"
[ "$code" = "200" ] || fail "/livez 가 200 이 아닙니다 (hosts 설정 확인)"

say "1) client 등록 (DCR)"
reg=$("${CURL[@]}" -X POST "$BASE/api/ai/oauth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"client_name\":\"e2e-runbook\",\"redirect_uris\":[\"$REDIRECT\"]}")
CLIENT_ID=$(printf '%s' "$reg" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("client_id",""))')
[ -n "$CLIENT_ID" ] || fail "client_id 발급 실패: $reg"
row "client_id" "$CLIENT_ID"

# PKCE — S256 전용
VERIFIER=$(python3 -c 'import secrets;print(secrets.token_urlsafe(64)[:96])')
CHALLENGE=$(python3 -c "
import hashlib,base64,sys
v=sys.argv[1].encode()
print(base64.urlsafe_b64encode(hashlib.sha256(v).digest()).rstrip(b'=').decode())" "$VERIFIER")
STATE=$(python3 -c 'import secrets;print(secrets.token_urlsafe(12))')

AUTH_URL="$BASE/api/ai/oauth/authorize?client_id=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$CLIENT_ID")"
AUTH_URL+="&redirect_uri=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$REDIRECT")"
AUTH_URL+="&code_challenge=$CHALLENGE&code_challenge_method=S256&state=$STATE&scope=data.read"

say "2) ★ 사람이 할 단계 — 브라우저에서 아래 URL 을 여세요"
printf '\n%s\n\n' "$AUTH_URL"
cat <<'EOS'
  · 사내 계정으로 로그인돼 있어야 합니다(아니면 로그인 화면 → 로그인 후 자동 복귀).
  · 리다이렉트되면 "연결할 수 없음" 화면이 뜨는 것이 정상입니다(127.0.0.1:8765 는 안 띄웁니다).
  · 주소창의 code= 뒤 값만 복사해 아래에 붙여넣으세요. 코드는 60초 · 1회용입니다.
EOS
printf '\ncode> '
read -r CODE
[ -n "$CODE" ] || fail "code 가 비었습니다"
CODE="${CODE%%&*}"; CODE="${CODE##*code=}"

say "3) 토큰 교환"
tok=$("${CURL[@]}" -X POST "$BASE/api/ai/oauth/token" \
  -d "grant_type=authorization_code" -d "code=$CODE" -d "client_id=$CLIENT_ID" \
  -d "redirect_uri=$REDIRECT" -d "code_verifier=$VERIFIER")
ACCESS=$(printf '%s' "$tok" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null || true)
REFRESH=$(printf '%s' "$tok" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("refresh_token",""))' 2>/dev/null || true)
[ -n "$ACCESS" ] || fail "토큰 교환 실패: $tok"
row "access_token" "${ACCESS:0:12}…"
row "refresh_token" "${REFRESH:0:12}…"

AUTHH=(-H "Authorization: Bearer $ACCESS" -H 'Content-Type: application/json')

say "4) 도구 흐름"
open=$("${CURL[@]}" -X POST "$BASE/api/ai/tools/open_task" "${AUTHH[@]}" \
  -d '{"question":"e2e 절차 검증 — 접근 가능한 스키마 구조를 확인한다"}')
TASK=$(printf '%s' "$open" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("task_id",""))' 2>/dev/null || true)
[ -n "$TASK" ] || fail "open_task 실패: $open"
row "open_task" "$TASK"

ctx=$("${CURL[@]}" -X POST "$BASE/api/ai/tools/get_task_context" "${AUTHH[@]}" -d "{\"task_id\":\"$TASK\"}")
printf '%s' "$ctx" | grep -q 'UNTRUSTED-DATA' && row "get_task_context" "각인 확인" \
  || fail "get_task_context 에 datamark 각인이 없습니다: ${ctx:0:200}"

ls=$("${CURL[@]}" -X POST "$BASE/api/ai/tools/list_schemas" "${AUTHH[@]}" \
  -d "{\"task_id\":\"$TASK\",\"arguments\":{}}")
printf '%s' "$ls" | grep -q 'UNTRUSTED-DATA' && row "list_schemas" "각인 확인" \
  || row "list_schemas" "응답: ${ls:0:120}"

sub=$("${CURL[@]}" -X POST "$BASE/api/ai/tools/submit_answer" "${AUTHH[@]}" \
  -d "{\"task_id\":\"$TASK\",\"answer\":\"e2e 검증 답변(더미).\",\"source_tasks\":[\"$TASK\"]}")
printf '%s' "$sub" | grep -q '"recorded": *true' && row "submit_answer" "기록됨" \
  || fail "submit_answer 실패: $sub"
findings=$(printf '%s' "$sub" | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get("cross_session_findings") or []))')
row "cross_session" "findings=$findings (기대 0)"

say "5) refresh 회전 + reuse 방어"
rot=$("${CURL[@]}" -X POST "$BASE/api/ai/oauth/token" \
  -d "grant_type=refresh_token" -d "refresh_token=$REFRESH" -d "client_id=$CLIENT_ID")
NEW_REFRESH=$(printf '%s' "$rot" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("refresh_token",""))' 2>/dev/null || true)
[ -n "$NEW_REFRESH" ] && [ "$NEW_REFRESH" != "$REFRESH" ] || fail "refresh 회전 실패: $rot"
row "refresh 회전" "새 토큰 발급됨"

reuse=$("${CURL[@]}" -o /dev/null -w '%{http_code}' -X POST "$BASE/api/ai/oauth/token" \
  -d "grant_type=refresh_token" -d "refresh_token=$REFRESH" -d "client_id=$CLIENT_ID")
row "구 refresh 재사용" "$reuse (기대 401)"
[ "$reuse" = "401" ] || fail "★ reuse 방어가 작동하지 않습니다 — 계열 폐기 로직 확인 필요"

say "6) 무토큰 거절"
noauth=$("${CURL[@]}" -o /dev/null -w '%{http_code}' -X POST "$BASE/api/ai/tools/open_task" \
  -H 'Content-Type: application/json' -d '{"question":"x"}')
row "무토큰 open_task" "$noauth (기대 401)"
[ "$noauth" = "401" ] || fail "무토큰 호출이 401 이 아닙니다"

printf '\n\033[32m전 구간 PASS\033[0m — 이 출력을 docs/TEST.md §3 에 Run 으로 기록하세요.\n'
printf '정리(선택): UPDATE WebOAuthClients SET RevokedAt=NOW() WHERE ClientId=%s;\n\n' "'$CLIENT_ID'"
