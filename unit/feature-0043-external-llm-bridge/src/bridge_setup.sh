#!/bin/sh
# mysql-ai 브리지 설치·기동 스크립트 (POSIX — Linux · macOS · WSL).
#
# ## 왜 이 파일이 있는가 (P0-AC, 사용자 제보 2026-08-28)
#
#     "LLM에 요청함에 따라 구축하는 방식이 모두 달라 사용자의 경험이 일정하지 않다"
#
# 종전의 유일한 연결 경로는 **서버가 만든 지시문을 사람이 자기 AI 에 붙여넣는 것**이었다.
# 그 순간부터 무엇이 일어날지는 그 AI 의 해석에 달렸다 — 어떤 AI 는 MCP 로 등록하고, 어떤
# AI 는 curl 로 한 번 부르고 끝내고, 어떤 AI 는 러너를 안 띄운다. 결과가 매번 다르므로
# **재현도, 지원도, 문서화도 되지 않는다.**
#
# 이 스크립트가 그 해석층을 걷어낸다. 하는 일이 여기 고정돼 있고, 같은 입력이면 같은 결과다.
# AI 는 여전히 **답변을 만드는 데** 쓰이지만 **연결을 만드는 데는 쓰이지 않는다.**
#
# ## 하는 일 (이 순서로, 전부)
#
#   1. 사내 사설 CA 를 받아 **지문을 대조**한다 (전역 설치 안 함 — 이 러너 프로세스 한정)
#   2. `bridge_agent.py` 를 받아 **체크섬을 대조**한다
#   3. `mysql-ai-bridge://` 프로토콜 핸들러를 등록한다 (웹 [내 AI 실행] 버튼용)
#   4. `--check` 로 연결을 확인하고, 통과하면 러너를 상주시킨다
#
# 어느 단계든 대조에 실패하면 **거기서 멈춘다**. 계속 진행하는 선택지는 없다.
#
# ## 하지 않는 일
#
#   · `pip install` · 패키지 매니저 호출 — 러너는 파이썬 표준 라이브러리만 쓴다
#   · OS·브라우저 신뢰 저장소 변경 — CA 는 `--cacert` 로 그 프로세스에만 준다
#   · 토큰을 디스크에 쓰기 — 토큰은 이 셸의 환경변수로만 전달된다
#   · 부팅 자동 등록 — 재부팅하면 러너는 사라진다 (그 사실을 웹 화면이 표시한다)
#
# ## 사용
#
#   BRIDGE_BASE=https://host BRIDGE_TOKEN=mat_... sh bridge_setup.sh
#
# 웹 콘솔의 [연결 명령 복사] 가 이 두 값을 채운 한 줄을 만들어 준다.
#
# ## 환경 판단은 빈칸으로 받는다 (P0-AD, 사용자 결정 2026-08-28)
#
# 위 P0-AC 는 **실행**의 비결정성을 없앴다. 그런데 **판단**은 여전히 이 스크립트 안에 박혀
# 있다 — python 은 `python3 → python` 순으로 찍고, 핸들러는 `uname` 으로 가른다. 그 고정값이
# 틀리는 환경이 실제로 있다(실측 2026-08-28: 브라우저는 Windows, `claude` 는 WSL 안. 어느
# `uname` 분기도 그 조합을 맞히지 못한다). 조합은 열려 있어서 우리가 열거할 수 없다.
#
# 그 머신에는 이미 LLM CLI 가 있다 — 그것이 이 브리지의 전제다(없으면 브리지가 무의미하다).
# 그래서 **판단만** 그쪽에 맡기고, 하는 일은 여기 그대로 둔다:
#
#     LLM 이 채운다 → `BRIDGE_PROBED_*`     (조사해서 알아내는 값)
#     이 스크립트가 한다 → 대조·설치·기동     (무엇을 할지는 여기 고정)
#
# `PROBED_` 접두가 계약이다: **그 값은 신뢰하지 않고 검증한다.** 아래 `probed_*` 함수들이
# 실존·형식·화이트리스트를 확인하고, 벗어나면 **버리고 기본 동작으로 간다**(막지 않는다 —
# 판단이 틀렸다고 연결까지 못 하게 만들면 그 사용자는 아무 경로도 남지 않는다).
#
# ⚠ 왜 `BRIDGE_ARGS` 를 그대로 쓰지 않고 칸을 따로 두는가: 그 변수는 무검증으로 러너 명령에
#   들어가고, 러너에는 `--cmd`(임의 명령 실행)·`--base`/`--token`/`--ca`(다른 서버로 돌리기)
#   같은 인자가 있다. 사람이 직접 줄 때는 자기 책임이지만, **LLM 이 채우는 칸**이 되는 순간
#   그것은 프롬프트 인젝션의 착지점이다. 그래서 사람 칸(`BRIDGE_ARGS`, 무검증·기존 호환)과
#   LLM 칸(`BRIDGE_PROBED_ARGS`, allowlist)을 **이름으로 가른다.**
set -eu

BRIDGE_BASE="${BRIDGE_BASE:-}"
BRIDGE_TOKEN="${BRIDGE_TOKEN:-}"
BRIDGE_CA_SHA256="${BRIDGE_CA_SHA256:-}"
BRIDGE_AGENT_SHA256="${BRIDGE_AGENT_SHA256:-}"
BRIDGE_HOME="${BRIDGE_HOME:-$HOME/.mysql-ai-bridge}"
# 사람이 직접 주는 칸 — 무검증(기존 호환). 자기 머신에서 자기가 쓰는 인자다.
#
# ⚠ **따옴표 그룹은 보존되지 않는다.** 이 값은 러너 명령에서 비인용 전개되므로 공백으로만
#   쪼개지고, `--cmd 'my-ai -p {prompt}'` 는 `--cmd` `'my-ai` `-p` `{prompt}'` 네 토큰이 된다
#   (codex P2-7 실측). 이것은 이 변경이 만든 결함이 아니라 **원래 그랬던 동작**이지만,
#   "기존 호환" 이라고 적으면서 그 한계를 숨기면 주장이 코드보다 넓어진다. 공백이 든 값이
#   필요하면 러너를 직접 실행하거나 `BRIDGE_CMD` 환경변수를 쓴다(러너가 읽는다).
BRIDGE_ARGS="${BRIDGE_ARGS:-}"

# ── LLM 이 채우는 칸 (전부 검증 대상) ────────────────────────────────────────
#: 이 머신의 파이썬. 비면 `python3 → python` 자동탐지(종전 동작).
BRIDGE_PROBED_PY="${BRIDGE_PROBED_PY:-}"
#: 러너가 쓸 로컬 AI CLI 이름(`--ai` 로 전달). 비면 러너가 스스로 감지한다.
BRIDGE_PROBED_AI="${BRIDGE_PROBED_AI:-}"
#: 러너 추가 인자. **allowlist 안의 것만** 통과한다(`--workers` 등 수치·불리언 축).
BRIDGE_PROBED_ARGS="${BRIDGE_PROBED_ARGS:-}"
#: 프로토콜 핸들러 등록 방식. `auto`(기본, uname 분기) · `none`(등록 안 함).
#: ⚠ `native` 를 함께 공개했었는데 **구현이 `auto` 와 같은 분기**였다(codex P2-8). 사용자는
#:   판단값을 준 줄 알지만 동작은 바뀌지 않는다 — 없는 선택지는 공개하지 않는다.
BRIDGE_PROBED_HANDLER="${BRIDGE_PROBED_HANDLER:-auto}"

#: 설치 로그에도 **시각을 적는다** (사용자 요청 2026-08-31). 어느 단계에서 오래 걸리는지는
#: 줄 사이의 시간차로만 보이는데, 시각이 없으면 그 차이를 읽을 수 없다 — 실제로
#: "러너 체크섬 일치 이후가 오래 걸린다" 는 제보를 받고서야 단계별로 재 봤다.
_ts() { date '+%Y-%m-%d %H:%M:%S'; }
die() { printf '\n[bridge-setup %s] 중단: %s\n' "$(_ts)" "$1" >&2; exit 1; }
say() { printf '[bridge-setup %s] %s\n' "$(_ts)" "$1"; }
#: 검증에서 버린 값은 **말한다**. 조용히 버리면 LLM 이 채운 값이 반영된 줄 알고, 그 오해는
#: 화면 어디에도 드러나지 않는다(러너의 `unmet` 고지와 같은 이유).
#:
#: ⚠ **stderr 로 쓴다.** stdout 으로 쓰면 `$(probed_args_filtered)` 같은 명령치환 안에서 부른
#:   경고가 치환값에 먹혀 화면에 안 나온다 — 실측에서 `--cmd` 주입을 정확히 차단하면서
#:   경고만 사라졌다(2026-08-28 자체 발견). 「조용히 버리지 않는다」를 주석에 적어 두고 그
#:   반대를 구현한 형태라, 값을 거르는 것만큼 **거른 사실이 도달하는 것**도 계약이다.
drop() { printf '[bridge-setup %s] ⚠ %s — 이 값은 버리고 기본 동작으로 진행합니다.\n' "$(_ts)" "$1" >&2; }

[ -n "$BRIDGE_BASE" ] || die "BRIDGE_BASE 가 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요."
[ -n "$BRIDGE_TOKEN" ] || die "BRIDGE_TOKEN 이 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요."

# ── LLM 이 채운 칸 검증 ──────────────────────────────────────────────────────
#
# 원칙: **버릴 수는 있어도 넘길 수는 없다.** 값이 이상하면 기본 동작으로 떨어지고, 어떤 경우에도
# 검증을 통과하지 않은 문자열이 명령의 일부가 되지 않는다.

#: 파이썬 후보를 실제로 **실행해** 3.8+ 인지 본다. 이름만 보면 `python` 이 2.7 인 머신에서
#: 러너가 문법 오류로 죽고, 그 죽음은 "AI 가 답을 안 한다" 로만 보인다.
py_ok() {
  [ -n "${1:-}" ] || return 1
  command -v "$1" >/dev/null 2>&1 || return 1
  "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1
}

PY=""
if [ -n "$BRIDGE_PROBED_PY" ]; then
  # 옵션으로 해석될 수 있는 것(선행 `-`)과 셸 메타문자는 애초에 받지 않는다 — 이 값은
  # 명령의 첫 토큰이 된다.
  case "$BRIDGE_PROBED_PY" in
    -*|*' '*|*'"'*|*"'"*|*';'*|*'|'*|*'&'*|*'$'*|*'`'*|*'('*|*'<'*|*'>'*)
      drop "BRIDGE_PROBED_PY 가 실행 파일 이름·경로 형태가 아닙니다" ;;
    *)
      if py_ok "$BRIDGE_PROBED_PY"; then
        PY="$BRIDGE_PROBED_PY"
        say "파이썬: $PY (조사값)"
      else
        drop "BRIDGE_PROBED_PY='$BRIDGE_PROBED_PY' 를 쓸 수 없습니다(미실존 또는 3.8 미만)"
      fi ;;
  esac
fi
if [ -z "$PY" ]; then
  for cand in python3 python; do
    if py_ok "$cand"; then PY="$cand"; break; fi
  done
fi
[ -n "$PY" ] || die "파이썬 3.8 이상을 찾지 못했습니다. 설치한 뒤 다시 실행하세요.
  (경로를 알고 있다면: BRIDGE_PROBED_PY=/path/to/python3 ... sh bridge_setup.sh)"

#: LLM 칸이 지목할 수 있는 AI CLI — **알려진 이름만**.
#:
#: ⚠ 종전에는 "PATH 에 실재하면 통과" 였다. 그러면 `BRIDGE_PROBED_AI=rm` 이 통과해
#:   `--ai rm` 이 되고, 러너는 그것을 AI CLI 로 **실행**한다(codex 적대 리뷰 실측).
#:   실존 검사는 「없는 것을 거르는」 장치이지 「무엇인지 확인하는」 장치가 아니었다.
#:
#: 표 밖 CLI 를 쓰는 길은 남아 있다 — 사람 칸(`BRIDGE_ARGS="--ai mycli"`)이다. LLM 칸은
#: 좁게, 사람 칸은 넓게. 자기 머신에서 자기가 지목하는 것과, 서버가 준 텍스트를 읽은 AI 가
#: 지목하는 것은 신뢰의 층이 다르다.
_KNOWN_AI_CLIS="claude codex gemini ollama"

AI_ARGS=""
if [ -n "$BRIDGE_PROBED_AI" ]; then
  _ai_known=0
  for _k in $_KNOWN_AI_CLIS; do
    [ "$BRIDGE_PROBED_AI" = "$_k" ] && _ai_known=1 && break
  done
  if [ "$_ai_known" != "1" ]; then
    drop "BRIDGE_PROBED_AI='$BRIDGE_PROBED_AI' 는 알려진 AI CLI 가 아닙니다($_KNOWN_AI_CLIS). 다른 CLI 는 BRIDGE_ARGS=\"--ai <이름>\" 로 직접 주세요"
  elif command -v "$BRIDGE_PROBED_AI" >/dev/null 2>&1; then
    AI_ARGS="--ai $BRIDGE_PROBED_AI"
    say "AI 런타임: $BRIDGE_PROBED_AI (조사값)"
  else
    drop "BRIDGE_PROBED_AI='$BRIDGE_PROBED_AI' 가 PATH 에 없습니다"
  fi
fi

#: 러너 추가 인자 — **allowlist**. 여기 없는 것은 통째로 버린다.
#:
#: 통과시키는 축은 「이 머신의 사양·속도에 맞추는 수치」뿐이다. 그것이 LLM 이 조사해서 알
#: 만한 것이고, 틀려도 성능만 달라진다. 반대로 러너에는 `--cmd`(임의 명령을 AI 호출로
#: 실행)·`--base`/`--token`/`--ca`(다른 서버·다른 자격증명으로 돌리기)·`--once`/`--check`
#: (상주하지 않고 끝나기)가 있고, 그중 하나라도 이 칸으로 들어오면 이 스크립트가 보장한다는
#: 것이 전부 무너진다.
probed_args_filtered() {
  _out=""
  _expect=""
  for _tok in $BRIDGE_PROBED_ARGS; do
    if [ -n "$_expect" ]; then
      # 직전 플래그의 값 자리. ⚠ `*[!0-9.]*` 하나로 뭉뚱그리면 `.` · `1..2` 가 통과한다
      # (codex 실측) — 그 값은 러너의 argparse 에서 죽고, 사용자는 설치가 끝난 줄 알았다가
      # "러너가 바로 종료됐다" 만 본다. **축마다 실제 타입으로** 본다.
      case "$_expect" in
        --workers|--max-workers)
          # 러너 쪽이 `int` 다. 상한도 둔다 — 999999999 개 워커는 조사 결과가 아니라 사고다.
          case "$_tok" in
            ''|*[!0-9]*) drop "BRIDGE_PROBED_ARGS: $_expect 의 값 '$_tok' 이 정수가 아닙니다"; _out=""; return 1 ;;
          esac
          if [ "$_tok" -lt 1 ] || [ "$_tok" -gt 64 ]; then
            drop "BRIDGE_PROBED_ARGS: $_expect 의 값 '$_tok' 이 범위(1~64) 밖입니다"; _out=""; return 1
          fi ;;
        *)
          # `--worker-idle-sec` · `--ai-timeout` 은 `float`. 소수점은 **한 번만**.
          case "$_tok" in
            ''|*[!0-9.]*|.|*.*.*) drop "BRIDGE_PROBED_ARGS: $_expect 의 값 '$_tok' 이 숫자가 아닙니다"; _out=""; return 1 ;;
          esac
          # 정수부만 떼어 범위를 본다(POSIX sh 에는 실수 비교가 없다).
          _int="${_tok%%.*}"; [ -n "$_int" ] || _int=0
          if [ "$_int" -lt 1 ] || [ "$_int" -gt 86400 ]; then
            drop "BRIDGE_PROBED_ARGS: $_expect 의 값 '$_tok' 이 범위(1~86400초) 밖입니다"; _out=""; return 1
          fi ;;
      esac
      _out="$_out $_expect $_tok"; _expect=""
      continue
    fi
    case "$_tok" in
      --workers|--max-workers|--worker-idle-sec|--ai-timeout) _expect="$_tok" ;;
      --refresh-caps) _out="$_out $_tok" ;;
      *) drop "BRIDGE_PROBED_ARGS: '$_tok' 은 허용 목록에 없습니다"; _out=""; return 1 ;;
    esac
  done
  [ -z "$_expect" ] || { drop "BRIDGE_PROBED_ARGS: $_expect 에 값이 없습니다"; return 1; }
  printf '%s' "${_out# }"
  return 0
}

PROBED_ARGS=""
if [ -n "$BRIDGE_PROBED_ARGS" ]; then
  if PROBED_ARGS=$(probed_args_filtered); then
    [ -z "$PROBED_ARGS" ] || say "러너 인자: $PROBED_ARGS (조사값)"
  else
    PROBED_ARGS=""
  fi
fi

#: 핸들러 등록 방식.
case "$BRIDGE_PROBED_HANDLER" in
  auto|none) ;;
  *) drop "BRIDGE_PROBED_HANDLER='$BRIDGE_PROBED_HANDLER' 는 auto|none 중 하나여야 합니다"
     BRIDGE_PROBED_HANDLER="auto" ;;
esac

#: 러너 명령에 실제로 붙는 인자. 사람 칸(`BRIDGE_ARGS`)이 뒤에 와서 **사람이 이긴다** —
#: 같은 인자가 겹치면 뒤가 유효하고, 자기 머신에서 자기가 준 값이 조사값보다 우선하는 것이 맞다.
RUNNER_ARGS="$AI_ARGS $PROBED_ARGS $BRIDGE_ARGS"

# ── 실행 전제 ────────────────────────────────────────────────────────────────
#
# ⚠ 입력 검증(위)이 **끝난 뒤**에 온다. 종전에는 `curl` 검사가 파이썬 탐색 바로 뒤,
#   즉 검증 구역 한가운데 있었다 — 논리적으로도 뒤섞인 배치이고(무엇을 실행할지 정하는 일과
#   실행 도구가 있는지 보는 일은 다른 층이다), 검증만 떼어 확인하려는 쪽에서는 `curl` 없는
#   환경(테스트 컨테이너)에서 그 줄에 걸려 검증 로직을 전혀 확인하지 못했다.
command -v curl >/dev/null 2>&1 || die "curl 이 없습니다."

mkdir -p "$BRIDGE_HOME"
chmod 700 "$BRIDGE_HOME" 2>/dev/null || true

# 호스트만 뽑는다. CA 는 **평문 HTTP** 로 받아야 한다 — 엣지 인증서를 서명한 것이 바로 그 CA 라,
# 아직 CA 가 없는 상태에서 https 로 받으려 하면 self-signed 로 실패하는 부트스트랩 데드락이다.
# 평문 채널의 위험은 아래 **지문 대조**가 덮는다(지문은 https 로 온 이 스크립트가 들고 있고
# 파일은 평문으로 오므로, 바꿔치려면 두 채널을 동시에 잡아야 한다).
HOST=$(printf '%s' "$BRIDGE_BASE" | sed -e 's#^[a-zA-Z][a-zA-Z0-9+.-]*://##' -e 's#/.*$##' -e 's#:.*$##')
[ -n "$HOST" ] || die "BRIDGE_BASE 에서 호스트를 읽지 못했습니다: $BRIDGE_BASE"

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else "$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  fi
}

# ── 1. CA ────────────────────────────────────────────────────────────────────
CA_PATH="$BRIDGE_HOME/rootCA.crt"
say "사내 CA 를 받는 중… (http://$HOST/trust/rootCA.crt)"
curl -fsS -o "$CA_PATH.tmp" "http://$HOST/trust/rootCA.crt" \
  || curl -fsSk -o "$CA_PATH.tmp" "$BRIDGE_BASE/trust/rootCA.crt" \
  || die "CA 를 받지 못했습니다. 사내망에 연결돼 있는지 확인하세요."

# 지문 대조. 서버가 값을 계산하지 못해 비어 있을 수 있는데(번들에 인증서가 여러 장이면 fail-closed
# 로 값을 내지 않는다), 그때는 **대조를 생략하고 그 사실을 말한다** — 조용히 넘어가면 사용자는
# 검증된 줄 안다.
if [ -n "$BRIDGE_CA_SHA256" ]; then
  GOT=$("$PY" - "$CA_PATH.tmp" <<'PYEOF'
import hashlib, ssl, sys
# 인증서 **DER** 기준으로 낸다 — 서버(`_ca_fingerprint`)와 `openssl x509 -fingerprint -sha256`
# 이 쓰는 것과 같은 기준. PEM 텍스트를 그냥 해싱하면 줄바꿈·주석 차이로 값이 갈린다.
pem = open(sys.argv[1], "r", encoding="utf-8", errors="replace").read()
try:
    der = ssl.PEM_cert_to_DER_cert(pem)
except Exception:
    sys.exit(1)
print(hashlib.sha256(der).hexdigest())
PYEOF
) || die "CA 지문을 계산하지 못했습니다(인증서 형식 확인 필요)."
  WANT=$(printf '%s' "$BRIDGE_CA_SHA256" | tr 'A-Z' 'a-z' | tr -d ':')
  GOT=$(printf '%s' "$GOT" | tr 'A-Z' 'a-z')
  [ "$GOT" = "$WANT" ] || die "CA 지문이 다릅니다.
  기대: $WANT
  실제: $GOT
  네트워크 중간에서 바뀌었을 수 있습니다. 진행하지 말고 운영자에게 알리세요."
  say "CA 지문 일치."
else
  # ⚠ **건너뛰지 않고 멈춘다** (codex 적대 리뷰 P1-3). 종전엔 "대조를 건너뜁니다" 라고 말하고
  #   그대로 진행했는데, 이 CA 는 **평문 HTTP 로 받은 것**이고 다음 줄에서 그것을 신뢰시킨다.
  #   대조 없이 진행하면 바꿔치기당한 CA 를 신뢰하게 되고, 그 뒤의 https·`mat_` 토큰까지
  #   전부 그 CA 를 쥔 쪽으로 간다. "경고 후 진행" 은 경고가 아니라 승인이다.
  #
  #   막다른 길로 두지는 않는다 — 운영자에게 값을 받아 넣는 경로와, 위험을 인지한 사용자의
  #   명시적 우회를 함께 준다.
  if [ "${BRIDGE_ALLOW_UNVERIFIED:-0}" = "1" ]; then
    say "⚠ BRIDGE_ALLOW_UNVERIFIED=1 — CA 지문 대조를 건너뜁니다. 신뢰할 수 있는 망에서만 쓰세요."
  else
    die "CA 지문을 받지 못해 대조할 수 없습니다.
  이 CA 는 평문 HTTP 로 받았고, 다음 단계에서 이 연결에 신뢰시킵니다 — 대조 없이 진행하면
  중간에서 바꿔치기당해도 알 수 없습니다.

  해결: 운영자에게 CA 지문(SHA-256)을 받아 다시 실행하세요.
        BRIDGE_CA_SHA256='<지문>' ... sh bridge_setup.sh
  (위험을 인지하고 강행하려면 BRIDGE_ALLOW_UNVERIFIED=1)"
  fi
fi
mv "$CA_PATH.tmp" "$CA_PATH"
chmod 600 "$CA_PATH" 2>/dev/null || true

# ── 2. 러너 ──────────────────────────────────────────────────────────────────
#
# ⚠ **Windows 판(bridge_setup.ps1)에는 여기에 없는 옵션이 하나 더 붙어 있다 — 의도된 divergence.**
#   그쪽은 윈도우 동봉 curl 이 **Schannel** 백엔드라, 사설 CA 에 CRL·OCSP 배포점이 없으면 폐기
#   상태가 «알 수 없음» 이 되고 curl 이 그것을 하드 실패로 본다
#   (`curl: (60) ... CERT_TRUST_REVOCATION_STATUS_UNKNOWN` — 사용자 제보 2026-08-31).
#   그래서 그쪽만 `--ssl-revoke-best-effort` 를 붙인다.
#
#   **이 파일에는 붙이지 않는다.** 리눅스·macOS curl 은 OpenSSL 계열이라 폐기검사를 기본으로
#   하지 않아 애초에 이 실패가 없고, 그 옵션은 Schannel 전용이라 여기서는 아무 일도 하지 않는다.
#   "두 판을 같게 맞춘다" 는 이유로 여기에 추가하거나 저쪽에서 빼지 말 것 — 같아야 하는 것은
#   **계약**(CA 지문 대조 → pin 된 CA 로만 https 수신 → 체크섬 대조)이고, 그 계약을 지키는 데
#   필요한 플랫폼별 수단은 다르다.
AGENT_PATH="$BRIDGE_HOME/bridge_agent.py"
say "러너를 받는 중…"
curl -fsS --cacert "$CA_PATH" -o "$AGENT_PATH.tmp" "$BRIDGE_BASE/static/agent/bridge_agent.py" \
  || die "러너를 받지 못했습니다. CA 신뢰 또는 네트워크를 확인하세요."

if [ -n "$BRIDGE_AGENT_SHA256" ]; then
  GOT=$(sha256_of "$AGENT_PATH.tmp" | tr 'A-Z' 'a-z')
  WANT=$(printf '%s' "$BRIDGE_AGENT_SHA256" | tr 'A-Z' 'a-z')
  if [ "$GOT" != "$WANT" ]; then
    # 롤링 배포 중에는 두 replica 가 다른 사본을 서빙할 수 있다. 이 고지가 없으면 정상 배포가
    # "침해 의심" 으로 읽혀 온보딩이 멈춘다.
    say "체크섬 불일치 — 배포 교대 중일 수 있어 1회 재시도합니다."
    sleep 20
    curl -fsS --cacert "$CA_PATH" -o "$AGENT_PATH.tmp" "$BRIDGE_BASE/static/agent/bridge_agent.py" \
      || die "러너 재수신 실패."
    GOT=$(sha256_of "$AGENT_PATH.tmp" | tr 'A-Z' 'a-z')
    [ "$GOT" = "$WANT" ] || die "러너 체크섬이 다릅니다.
  기대: $WANT
  실제: $GOT
  진행하지 말고 운영자에게 알리세요."
  fi
  say "러너 체크섬 일치."
else
  say "⚠ 서버가 러너 체크섬을 제공하지 않아 대조를 건너뜁니다."
fi
mv "$AGENT_PATH.tmp" "$AGENT_PATH"
chmod 600 "$AGENT_PATH" 2>/dev/null || true

# ── 3. 프로토콜 핸들러 ────────────────────────────────────────────────────────
#
# 브라우저는 샌드박스라 로컬 프로세스를 직접 띄우지 못한다. 그래서 웹의 [내 AI 실행] 버튼이
# 하는 일은 `mysql-ai-bridge://start` 를 여는 것이고, **그 스킴을 이 단계에서 OS 에 등록**한다.
# 이것이 "최초 1회 터미널, 이후 브라우저 원클릭" 의 실체다.
#
# ⚠ 러너 본체의 「설치물 없음」 계약과 다른 지점이다. 등록물은 여기(setup)에 있고 러너에는
#   없다 — 그래서 러너만 받아 쓰는 사람의 계약은 그대로다. 해제는 아래 안내 참조.
LAUNCH_SH="$BRIDGE_HOME/launch.sh"
cat > "$LAUNCH_SH" <<LAUNCHEOF
#!/bin/sh
# mysql-ai 브리지 러너 기동 (프로토콜 핸들러가 부른다).
# 토큰은 여기 없다 — 웹이 스킴 인자로 그때그때 넘긴다(mysql-ai-bridge://start?token=...).
set -eu
BRIDGE_HOME="\${BRIDGE_HOME:-\$HOME/.mysql-ai-bridge}"
URL="\${1:-}"
# ⚠ 이 스크립트는 **콘솔 창 안에서** 불릴 수 있다(Windows 핸들러가 wsl.exe 로 되부르는 경로).
#   그 창은 스크립트가 끝나는 순간 닫히므로, 오류를 그냥 출력하면 사용자는 **깜빡임만** 본다 —
#   그건 스킴이 등록되지 않았을 때와 화면상 구별되지 않는다(둘 다 "아무 일도 안 일어남").
#   그래서 터미널에 붙어 있을 때만 잠깐 붙잡아 둔다.
_ts() { date '+%Y-%m-%d %H:%M:%S'; }
bail() {
  printf '[bridge-launch %s] %s\n' "\$(_ts)" "\$1" >&2
  if [ -t 2 ]; then printf '\n(이 창은 20초 뒤 닫힙니다)\n' >&2; sleep 20; fi
  exit "\$2"
}
TOKEN=\$(printf '%s' "\$URL" | sed -n 's/.*[?&]token=\([^&]*\).*/\1/p')
[ -n "\$TOKEN" ] || bail "token 이 없습니다: \$URL" 2
# ⚠ 이 스킴은 **아무 웹페이지나 열 수 있다**. 그래서 토큰을 확인하기 전에는 아무것도 죽이지
#   않는다 — 종전엔 곧바로 pkill 이라, 임의 사이트가 쓰레기 토큰으로 이 URL 을 열게 하는 것만으로
#   정상 러너를 끌 수 있었다(codex 적대 리뷰 P2). 순서를 뒤집는다: **먼저 검증, 그다음 교체.**
case "\$TOKEN" in
  mat_*) ;;
  *) bail "token 형식이 아닙니다 — 무시합니다." 2 ;;
esac
BRIDGE_TOKEN="\$TOKEN" $PY "\$BRIDGE_HOME/bridge_agent.py" \\
  --base '$BRIDGE_BASE' --ca "\$BRIDGE_HOME/rootCA.crt" --check >/dev/null 2>&1 \\
  || bail "토큰이 유효하지 않습니다(만료·로그아웃) — 실행 중인 러너를 그대로 둡니다.
웹 화면에서 [연결 준비] 를 다시 누르고 [내 AI 실행] 을 눌러 주세요." 3
pkill -f 'bridge_agent.py' >/dev/null 2>&1 || true
# ⚠ **부모가 즉시 끝나면 wsl.exe 가 이 자식까지 죽인다** (실측 2026-08-31). 이 스크립트는
#   Windows 핸들러에서 \`wsl.exe -- launch.sh\` 로 불리는데, 그 명령이 끝나는 순간 WSL 이
#   세션을 정리하면서 방금 띄운 러너를 함께 거둬간다. \`nohup\`·\`setsid\`·stdin 차단 전부
#   막지 못했고(3종 다 실패), **부모가 자식이 자리잡을 때까지 살아 있는 것만** 통했다.
#
#   증상은 앞선 결함과 똑같이 «아무 일도 일어나지 않음» 이다 — rc=0, 오류 없음, 로그에
#   러너 시작 줄조차 없음. 게다가 위 \`pkill\` 은 이미 실행됐으므로 **돌던 러너까지 사라진다**
#   (누르기 전보다 나빠진다). 그래서 여기서 기다린다.
BEFORE_LINES=0
[ -f "\$BRIDGE_HOME/bridge.log" ] && BEFORE_LINES=\$(wc -l < "\$BRIDGE_HOME/bridge.log" 2>/dev/null || echo 0)
BRIDGE_TOKEN="\$TOKEN" nohup $PY "\$BRIDGE_HOME/bridge_agent.py" \\
  --base '$BRIDGE_BASE' --ca "\$BRIDGE_HOME/rootCA.crt" --resume $RUNNER_ARGS \\
  < /dev/null >> "\$BRIDGE_HOME/bridge.log" 2>&1 &
CHILD=\$!
# 살아 있고 + 로그가 늘었고 + 최소 3초 — 셋을 다 본다. 로그만 보면 아직 못 쓴 순간에 속고,
# 생존만 보면 곧 거둬질 자식을 살아 있다고 읽는다(실측 하한이 3초였다).
WAITED=0
while [ "\$WAITED" -lt 30 ]; do
  sleep 1
  WAITED=\$((WAITED + 1))
  kill -0 "\$CHILD" 2>/dev/null || bail "러너가 바로 종료됐습니다. 로그를 확인하세요: \$BRIDGE_HOME/bridge.log" 4
  NOW_LINES=\$(wc -l < "\$BRIDGE_HOME/bridge.log" 2>/dev/null || echo 0)
  if [ "\$NOW_LINES" -gt "\$BEFORE_LINES" ] && [ "\$WAITED" -ge 3 ]; then
    printf '[bridge-launch %s] 내 AI 를 실행했습니다. 웹 화면의 표시가 '"'"'내 AI 대기 중'"'"' 으로 바뀝니다.\\n' "\$(_ts)"
    exit 0
  fi
done
# 30초가 지나도 첫 줄이 없다 — 살아는 있으므로 죽이지 않고, 무엇을 볼지 말한다.
printf '[bridge-launch %s] 러너가 아직 준비 중입니다(30초). 로그: %s\\n' "\$(_ts)" "\$BRIDGE_HOME/bridge.log"
LAUNCHEOF
chmod 700 "$LAUNCH_SH"

# ── 3-a. 등록할 곳은 «셸» 이 아니라 «브라우저» 를 따른다 ──────────────────────
#
# 종전 구현은 `uname` 으로 갈라 **이 셸이 도는 OS** 에 등록했다. 그런데 이 버튼을 누르는
# 주체는 셸이 아니라 **브라우저**다. WSL 셸 + Windows 브라우저 조합에서는 등록이 성공하고도
# 브라우저가 그 등록을 보지 못한다 — 그리고 종전 코드는 그 상태에서 「등록했습니다」 라고
# 말했다. 사용자는 동작한다고 믿고 버튼을 누르고, 아무 일도 일어나지 않는다.
#
# 실측(2026-08-31): `HKCU\Software\Classes\mysql-ai-bridge` 키 없음 ·
# `~/.local/share/applications/mysql-ai-bridge.desktop` 있음 · 버튼 무동작 · 같은 계정의
# 토큰 4건이 전부 하트비트 없이 남음. 사용자 제보 "'내 AI 실행' 을 통해 연결을 시도했지만,
# 연결이 진행되지 않는것으로 확인되었습니다."
#
# 그래서 WSL 이면 **Windows 쪽(HKCU)에도** 등록하고, 그 핸들러가 `wsl.exe` 로 이 배포판의
# `launch.sh` 를 되부르게 한다. 관리자 권한은 필요 없다(HKCU 는 이 사용자 범위).

#: 이 셸이 WSL 안인가. `BRIDGE_FORCE_WSL=1|0` 으로 강제할 수 있다 — 감지가 틀리는 배포판과
#: 테스트에서 쓴다. 보안 게이트가 아니라 환경 판정이므로 강제를 열어 둔다.
is_wsl() {
  case "${BRIDGE_FORCE_WSL:-}" in 1) return 0 ;; 0) return 1 ;; esac
  [ -n "${WSL_DISTRO_NAME:-}" ] && return 0
  [ -e /proc/sys/fs/binfmt_misc/WSLInterop ] && return 0
  grep -qi microsoft /proc/version 2>/dev/null && return 0
  return 1
}

#: WSL 에서 Windows 실행파일 경로를 찾는다.
#:
#: ⚠ `command -v` 하나만 믿으면 안 된다 — interop PATH 가 실려 있지 않은 셸(서비스·cron·
#:   일부 컨테이너 셸)이 실제로 있고, 그 셸에서는 `powershell.exe` 가 «없음» 으로 오판된다
#:   (실측 2026-08-31: 같은 머신인데 `command -v powershell.exe` 는 빈 값, 절대경로는 실행됨).
#: ⚠ `powershell.exe` 는 System32 **직하가 아니다** — `System32\WindowsPowerShell\v1.0\` 에 있고,
#:   Windows PATH 가 그 디렉토리를 담고 있어서 평소엔 티가 안 난다. 폴백 목록을 System32 만으로
#:   두면 interop PATH 없는 셸에서 「powershell.exe 없음」 으로 오판한다(추출 실행 테스트가
#:   실제로 그렇게 실패했다, 2026-08-31).
win_exe() {
  _we=$(command -v "$1" 2>/dev/null || true)
  if [ -n "$_we" ]; then printf '%s' "$_we"; return 0; fi
  for _wr in /mnt/c/Windows /c/Windows /mnt/c/WINDOWS /c/WINDOWS; do
    for _ws in System32 System32/WindowsPowerShell/v1.0 SysWOW64 ""; do
      if [ -n "$_ws" ]; then _wd="$_wr/$_ws"; else _wd="$_wr"; fi
      if [ -x "$_wd/$1" ]; then printf '%s' "$_wd/$1"; return 0; fi
    done
  done
  return 1
}

#: Windows 브라우저가 보는 곳(HKCU)에 스킴을 등록한다. 실패 사유는 `$HANDLER_WIN_WHY` 에.
#:
#: 등록은 **PowerShell 스크립트 파일**로 한다. `reg.exe add /d '...\"%1\"'` 는 WSL→Win32
#: 인자 변환에서 따옴표가 한 겹씩 먹혀, 조용히 깨진 커맨드라인이 등록된다. 파일로 넘기면
#: 인용 규칙이 한 언어(PowerShell) 안에서만 적용돼 경계를 건널 것이 없다.
register_handler_windows() {
  HANDLER_WIN_WHY=""
  WSL_EXE=$(win_exe wsl.exe) || { HANDLER_WIN_WHY="wsl.exe 를 찾지 못했습니다"; return 1; }
  PS_EXE=$(win_exe powershell.exe) || { HANDLER_WIN_WHY="powershell.exe 를 찾지 못했습니다"; return 1; }

  # ⚠ **`-d`·`-u` 값은 따옴표로 감싸면 안 된다** (실측 2026-08-31). 레지스트리 커맨드라인은
  #   ShellExecute 가 wsl.exe 에 **원문 그대로** 넘기고, wsl.exe 의 자체 파서는 이 두 옵션의
  #   값에서 따옴표를 벗기지 않는다 — `-d "Ubuntu"` 는 이름이 `"Ubuntu"` 인 배포판을 찾다가
  #   rc=-1 로 죽고, 그 오류는 즉시 닫히는 콘솔에 찍혀 사라진다. 즉 **버튼을 눌러도 아무 일도
  #   일어나지 않는** 형태가 되어, 이 절이 고치려는 결함과 화면상 구별되지 않는다.
  #   (변형 실측: `-d "Ubuntu"` FAIL · `-d Ubuntu` PASS — 경로 쪽 따옴표는 무관했다.)
  #
  #   따옴표를 못 쓰므로 공백·따옴표가 든 이름은 **표현할 수단이 없다**. 그때는 조용히
  #   생략하지 않고 등록을 포기하고 사유를 말한다 — `-u` 를 생략하면 기본 사용자로 러너가
  #   떠서 `$HOME` 이 달라지고(`~/.mysql-ai-bridge` 없음) "왜 안 되지" 가 한 겹 더 깊어진다.
  _safe_word() {
    case "${1:-}" in
      "" ) return 1 ;;
      *[!A-Za-z0-9._-]* ) return 1 ;;
      * ) return 0 ;;
    esac
  }

  # ── 배포판 이름 — «어느 배포판인가» 를 추측하지 않는다 ────────────────────────
  #
  # ⚠ `wsl.exe -l -q` 의 **첫 줄은 현재 셸의 배포판이 아니다**(설치 순서·기본값에 따라 다르다).
  #   그것을 현재 배포판으로 가정하면, 배포판이 여럿인 머신에서 핸들러가 **엉뚱한 배포판의**
  #   `launch.sh` 를 부른다 — 그 경로에는 파일이 없으니 아무 일도 안 일어나고, 설치는 성공으로
  #   표시된다. 정확히 이 절이 고치려는 「조용한 무동작」 이 형태만 바꿔 되돌아온다.
  #   그래서 목록 폴백은 **배포판이 정확히 하나일 때만** 쓴다(그때는 현재 셸이 그것일 수밖에 없다).
  #   `-d` 생략(기본 배포판)도 같은 이유로 쓰지 않는다.
  _distro="${WSL_DISTRO_NAME:-}"
  if [ -z "$_distro" ]; then
    # `wsl.exe -l -q` 는 UTF-16LE 를 뱉는다 — NUL·CR 에 더해 **BOM(0xFF 0xFE)** 도 걷어내야
    # 한다. NUL 만 지우면 첫 이름 앞에 `\xff\xfe` 가 붙어 정상 이름이 거절된다(codex P2).
    _dlist=$("$WSL_EXE" -l -q 2>/dev/null | tr -d '\000\r\377\376' | sed '/^[[:space:]]*$/d' || true)
    _dcount=$(printf '%s\n' "$_dlist" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')
    if [ "$_dcount" = "1" ]; then
      _distro=$(printf '%s' "$_dlist" | sed -n '1p')
    else
      HANDLER_WIN_WHY="이 셸의 WSL 배포판 이름을 확정할 수 없습니다(WSL_DISTRO_NAME 미설정, 후보 ${_dcount}개) — 엉뚱한 배포판에 연결하지 않도록 등록하지 않습니다"
      return 1
    fi
  fi
  if ! _safe_word "$_distro"; then
    HANDLER_WIN_WHY="배포판 이름 '$_distro' 에 공백·특수문자가 있어 핸들러 명령으로 넘길 수 없습니다"
    return 1
  fi
  HANDLER_WIN_DISTRO="$_distro"
  _dopt="-d $_distro"

  _wuser=$(id -un 2>/dev/null || printf '%s' "${USER:-}")
  if ! _safe_word "$_wuser"; then
    HANDLER_WIN_WHY="이 셸의 사용자 이름('$_wuser')을 핸들러 명령으로 넘길 수 없습니다"
    return 1
  fi

  # 경로는 큰따옴표로 감싸 넘기므로 **경로 안의 큰따옴표·개행·제어문자**가 인용을 깨뜨린다
  # (codex P2). 깨진 커맨드라인은 등록에는 성공하고 클릭에는 무동작이라, 또 조용한 실패가 된다.
  case "$LAUNCH_SH" in
    *'"'*|*'%'*) HANDLER_WIN_WHY="설치 경로('$LAUNCH_SH')에 따옴표·%가 있어 핸들러 명령으로 넘길 수 없습니다"; return 1 ;;
  esac
  if [ "$LAUNCH_SH" != "$(printf '%s' "$LAUNCH_SH" | tr -d '\000-\037\177')" ]; then
    HANDLER_WIN_WHY="설치 경로에 제어문자가 있어 핸들러 명령으로 넘길 수 없습니다"
    return 1
  fi

  # wsl.exe 는 System32 에 있고 System32 는 Windows PATH 에 항상 있다. 그래도 절대경로를
  # 우선 쓴다 — PATH 를 손댄 환경에서 엉뚱한 실행파일이 잡히는 것을 막는다.
  _win_wsl=$(wslpath -w "$WSL_EXE" 2>/dev/null || printf 'wsl.exe')

  # `--` 뒤는 셸을 거치지 않고 execvp 로 간다(`?`·`&` 가 든 URL 이 그대로 argv[1] 이 된다).
  # 이 자리의 따옴표는 wsl.exe 가 제대로 처리한다(위 옵션 값과 다른 지점 — 실측으로 갈랐다).
  _cmdline="\"$_win_wsl\" $_dopt -u $_wuser -- \"$LAUNCH_SH\" \"%1\""
  # 아래 PowerShell 리터럴은 홑따옴표로 감싼다 — 값에 홑따옴표가 있으면 그 리터럴이 깨진다.
  # 깨진 채로 등록하느니 등록하지 않고 **말한다**.
  case "$_cmdline" in
    *"'"*) HANDLER_WIN_WHY="경로·사용자명에 홑따옴표가 있어 안전하게 등록할 수 없습니다"; return 1 ;;
  esac

  # ── PS1 은 **Windows 로컬 디스크**에 둔다 (실측 2026-08-31) ───────────────────
  #
  # ⚠ `powershell -File` 에 **WSL 경로**(`\\wsl.localhost\<distro>\…`)를 주면 UNC 해석이
  #   걸려 **80초**가 든다. 같은 스크립트를 Windows 로컬 경로로 주면 **0.4초**다 —
  #   200배 차이이고, 사용자에게는 "러너 체크섬 일치" 뒤로 설치가 멈춘 것처럼 보인다
  #   (사용자 제보 2026-08-31). 그래서 %TEMP% 에 쓰고 그 Windows 경로로 실행한다.
  #
  #   실측: powershell -File (WSL UNC) 80.27s · (Windows 로컬) 0.41s ·
  #         wsl.exe -l -q 0.08s · wslpath 0.00s · reg.exe query 0.04s
  # ⚠ **Windows 프로세스 기동 횟수를 센다.** 부하가 걸린 머신에서 exe 하나가 3초씩 든다
  #   (실측: powershell·cmd·reg 모두 3.0~3.4s. 한가할 땐 0.04~0.4s). 그래서 「무엇을 부르는가」
  #   보다 「몇 번 부르는가」가 체감을 지배한다 — 종전 3회(TEMP 조회·등록·검증)를 1회로 줄인다.
  #
  #   TEMP 는 대개 **Windows 호출 없이** 얻을 수 있다: WSL 이 물려받은 PATH 에
  #   `/mnt/c/Users/<사용자>/AppData/Local/Microsoft/WindowsApps` 가 들어 있다. 거기서
  #   프로필 경로를 떼어 쓴다(공짜). 못 얻으면 그때만 `cmd.exe` 를 한 번 부른다.
  _wintmp=""
  _prof=$(printf '%s\n' "$PATH" | tr ':' '\n' \
          | sed -n 's|^\(.*/mnt/[a-z]/Users/[^/]*\)/.*|\1|p' | head -1)
  if [ -n "$_prof" ] && [ -d "$_prof/AppData/Local/Temp" ] && [ -w "$_prof/AppData/Local/Temp" ]; then
    _wintmp="$_prof/AppData/Local/Temp"
  else
    _t=$("$(win_exe cmd.exe || printf '')" /c 'echo %TEMP%' 2>/dev/null | tr -d '\r\n') || _t=""
    case "$_t" in
      ?:\\*) _wintmp=$(wslpath -u "$_t" 2>/dev/null || true) ;;
      *) _wintmp="" ;;
    esac
    [ -n "$_wintmp" ] && [ -d "$_wintmp" ] && [ -w "$_wintmp" ] || _wintmp=""
  fi

  # ⚠ 파일명을 **매번 고유하게** 만들고 생성 실패를 검사한다 (codex 2R P1-2). 고정 이름을
  #   쓰면 이전 실행이 남긴 (혹은 다른 배포판용으로 쓰인) 스크립트가 그대로 실행될 수 있고,
  #   그 PS1 안의 자기 대조는 **그 옛 값끼리** 맞으므로 통과한다 — 바깥 검사는 키 존재만 보니
  #   "현재 배포판에 등록했다" 고 보고하면서 레지스트리는 다른 명령을 가리키게 된다.
  if [ -n "$_wintmp" ]; then
    _ps1="$_wintmp/mysql-ai-bridge-reg.$$.ps1"
  else
    # %TEMP% 를 못 얻었다 — 느리지만 되는 경로로 간다. 느려지는 사실을 말한다.
    say "  (Windows 임시 폴더를 찾지 못해 느린 경로로 등록합니다 — 1분 이상 걸릴 수 있습니다.)"
    _ps1="$BRIDGE_HOME/.register_win_handler.$$.ps1"
  fi
  rm -f "$_ps1" 2>/dev/null || true
  # ⚠ **UTF-8 BOM 을 먼저 쓴다.** Windows PowerShell 5.1 은 BOM 없는 `.ps1` 을 시스템 ANSI
  #   코드페이지로 읽어 한글 주석이 깨지고, 깨진 바이트가 인접한 따옴표·괄호를 삼켜 파서가
  #   죽는다(사용자 제보 2026-08-31, `bridge_setup.ps1` 에서 실제로 발생). 여기 생성물도
  #   한글 주석을 담으므로 같은 위험이 있다 — 지금 우연히 통과하는 것에 기대지 않는다.
  printf '\357\273\277' > "$_ps1" 2>/dev/null || true
  if ! cat >> "$_ps1" <<PSEOF
# mysql-ai 브리지 — Windows 브라우저용 스킴 핸들러 등록 (HKCU, 관리자 권한 불필요).
# 이 파일은 bridge_setup.sh 가 생성하고 실행 직후 지운다.
\$ErrorActionPreference = 'Stop'
\$key = 'HKCU:\Software\Classes\mysql-ai-bridge'
New-Item -Path \$key -Force | Out-Null
New-ItemProperty -Path \$key -Name '(default)' -Value 'URL:mysql-ai bridge' -PropertyType String -Force | Out-Null
New-ItemProperty -Path \$key -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
New-Item -Path "\$key\shell\open\command" -Force | Out-Null
New-ItemProperty -Path "\$key\shell\open\command" -Name '(default)' -Value '$_cmdline' -PropertyType String -Force | Out-Null
# ── 되읽어 대조한다 ─────────────────────────────────────────────────────────
# 「키가 있다」는 「그 키에 우리가 쓴 값이 있다」가 아니다. 다른 설치·정책·이전 버전이 남긴
# 값이 그대로면 클릭은 무동작인데 등록은 성공으로 보고된다. 값까지 맞아야 성공이다.
\$actual = (Get-Item "\$key\shell\open\command").GetValue('')
if (\$actual -ne '$_cmdline') { throw "등록된 명령이 기대와 다릅니다: \$actual" }
PSEOF
  then
    rm -f "$_ps1" 2>/dev/null || true
    HANDLER_WIN_WHY="등록 스크립트를 만들지 못했습니다($_ps1)"
    return 1
  fi
  _ps1_win=$(wslpath -w "$_ps1" 2>/dev/null || true)
  [ -n "$_ps1_win" ] || { rm -f "$_ps1"; HANDLER_WIN_WHY="WSL 경로를 Windows 경로로 바꾸지 못했습니다(wslpath)"; return 1; }
  # ── 사후검증은 **이 한 번의 실행 안에서** 끝난다 ─────────────────────────────
  #
  # 「등록했다」 를 쓰기 성공으로 갈음하지 않는다 — 위 PS1 이 마지막에 값을 **되읽어 대조**하고
  # 어긋나면 `throw` 한다. 그래서 이 프로세스의 종료코드가 곧 「그 값이 실제로 거기 있다」다.
  #
  # 종전엔 여기서 PowerShell 을 **한 번 더** 띄워 `Test-Path` 로 확인했다. 같은 보장을 두 번
  # 하면서 Windows 프로세스 기동(부하 시 3초대)을 하나 더 쓴 것이라, 사용자가 겪은 "설치가
  # 멈춘 것 같다" 의 1/3 이 이 줄이었다. 보장을 줄이지 않고 호출만 줄인다.
  if ! "$PS_EXE" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$_ps1_win" >/dev/null 2>&1; then
    rm -f "$_ps1"
    HANDLER_WIN_WHY="레지스트리 쓰기·대조가 실패했습니다(실행 정책·정책 제한, 또는 등록된 값이 기대와 다름)"
    return 1
  fi
  rm -f "$_ps1"
  return 0
}

register_handler() {
  # 사용자가 "이 머신에서는 등록해도 소용없다" 를 명시한 경우 — 헛되이 등록물을 남기는
  # 대신 **안 하는 것**을 고를 수 있게 한다.
  [ "$BRIDGE_PROBED_HANDLER" = "none" ] && return 2
  case "$(uname -s 2>/dev/null || echo unknown)" in
    Darwin)
      # macOS 는 .app 번들이 필요하다. 최소 번들을 만들고 LaunchServices 에 등록한다.
      APP="$BRIDGE_HOME/MysqlAiBridge.app"
      mkdir -p "$APP/Contents/MacOS"
      cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>ai.mysql.bridge.launcher</string>
  <key>CFBundleName</key><string>MysqlAiBridge</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleURLTypes</key><array><dict>
    <key>CFBundleURLName</key><string>mysql-ai-bridge</string>
    <key>CFBundleURLSchemes</key><array><string>mysql-ai-bridge</string></array>
  </dict></array>
</dict></plist>
PLIST
      cat > "$APP/Contents/MacOS/launch" <<MACEOF
#!/bin/sh
exec "$LAUNCH_SH" "\$1"
MACEOF
      chmod 755 "$APP/Contents/MacOS/launch"
      /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
        -f "$APP" >/dev/null 2>&1 || return 1
      ;;
    Linux)
      # WSL 은 Linux 지만 브라우저가 **Windows 쪽**일 수 있다. 두 곳 다 시도하고, 어느 쪽이
      # 성공했는지를 따로 남긴다 — 성공 문구가 사실보다 넓어지지 않게 하려면 여기서 갈라야 한다.
      if is_wsl; then
        register_handler_windows && HANDLER_WIN="ok" || HANDLER_WIN="fail"
      fi
      # WSL 안에서도 WSLg·X11 로 Linux 브라우저를 쓸 수 있으므로 xdg 등록은 그대로 한다.
      # 실패해도 Windows 쪽이 성공했으면 버튼은 동작한다.
      # ⚠ 각 단계의 성패를 **개별로** 본다. `xdg-mime` 만 보면, desktop 파일 쓰기가 실패해도
      #   (경로가 디렉토리이거나 권한이 없거나 디스크가 찼거나) 등록 성공으로 보고된다 —
      #   그러면 「등록했습니다」 라고 말하고 클릭은 무동작이다(codex P1). 이 절이 고치는
      #   결함과 정확히 같은 형태다.
      HANDLER_LINUX="fail"
      if command -v xdg-mime >/dev/null 2>&1; then
        DESKTOP_DIR="$HOME/.local/share/applications"
        DESKTOP_FILE="$DESKTOP_DIR/mysql-ai-bridge.desktop"
        if mkdir -p "$DESKTOP_DIR" 2>/dev/null && cat > "$DESKTOP_FILE" <<DESKEOF
[Desktop Entry]
Type=Application
Name=mysql-ai bridge launcher
Exec=$LAUNCH_SH %u
NoDisplay=true
Terminal=false
MimeType=x-scheme-handler/mysql-ai-bridge;
DESKEOF
        then
          update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
          # 파일이 실재하고 비어 있지 않은지까지 본다 — 쓰기가 조용히 잘린 경우를 거른다.
          if [ -s "$DESKTOP_FILE" ] \
             && xdg-mime default mysql-ai-bridge.desktop x-scheme-handler/mysql-ai-bridge >/dev/null 2>&1; then
            HANDLER_LINUX="ok"
          fi
        fi
      fi
      # WSL 이면 «Windows 쪽이 성공했는가» 가 사실상의 판정이다 — 이 조합의 브라우저는
      # 대부분 Windows 쪽이고, xdg 등록만 성공한 상태가 정확히 이번 결함의 모양이었다.
      if is_wsl; then
        [ "$HANDLER_WIN" = "ok" ] && return 0
        return 3
      fi
      [ "$HANDLER_LINUX" = "ok" ] && return 0
      return 1
      ;;
    *) return 1 ;;
  esac
  return 0
}

#: 등록 결과 — `register_handler` 가 채운다. 초기값은 「시도 안 함」.
HANDLER_WIN="na"
HANDLER_LINUX="na"
HANDLER_WIN_WHY=""
HANDLER_WIN_DISTRO=""

register_handler && _handler_rc=0 || _handler_rc=$?
if [ "$_handler_rc" = "0" ]; then
  if [ "$HANDLER_WIN" = "ok" ]; then
    say "웹 [내 AI 실행] 버튼용 핸들러를 **Windows 쪽**에 등록했습니다 (mysql-ai-bridge://)."
    # 배포판은 **항상 확정된 상태**로만 여기 온다 — 확정 못 하면 위에서 등록 자체를 포기한다
    # (추측한 배포판에 연결하면 조용한 무동작이 형태만 바꿔 되돌아온다).
    say "  누르면 wsl.exe 가 배포판 '$HANDLER_WIN_DISTRO' 의 러너를 다시 띄웁니다."
    [ "$HANDLER_LINUX" = "ok" ] && say "  (WSL 안 브라우저용 xdg 등록도 함께 했습니다.)"
  else
    say "웹 [내 AI 실행] 버튼용 핸들러를 등록했습니다 (mysql-ai-bridge://)."
  fi
elif [ "$_handler_rc" = "2" ]; then
  # 실패가 아니라 **선택**이다. 실패 문구를 쓰면 사용자는 고칠 것을 찾는다.
  say "핸들러 등록을 건너뜁니다 (BRIDGE_PROBED_HANDLER=none — 이 머신의 브라우저는 여기 등록한"
  say "  핸들러를 보지 못한다는 조사 결과). 러너가 꺼지면 이 명령을 다시 실행하세요."
elif [ "$_handler_rc" = "3" ]; then
  # WSL 인데 Windows 등록만 실패 — 여기서 「등록했습니다」 라고 말하면 정확히 이번 결함이
  # 재생산된다(xdg 등록은 성공했지만 Windows 브라우저는 그것을 보지 못한다).
  say "⚠ 이 셸은 WSL 이고, Windows 쪽 핸들러 등록에 실패했습니다"
  say "  ($HANDLER_WIN_WHY)."
  say "  → Windows 브라우저의 [내 AI 실행] 버튼은 동작하지 않습니다. 러너가 꺼지면 이 명령을"
  say "     다시 실행하세요. (연결 자체에는 영향 없음)"
  [ "$HANDLER_LINUX" = "ok" ] && say "  (WSL 안에서 여는 브라우저라면 xdg 등록으로 동작합니다.)"
else
  # 등록 실패가 연결 자체를 막지는 않는다 — 러너는 아래에서 그대로 뜬다. 다만 브라우저
  # 버튼은 동작하지 않으므로 **그 사실을 말한다**(조용히 실패하면 버튼을 눌러 보고 고장으로 읽는다).
  say "⚠ 프로토콜 핸들러를 등록하지 못했습니다 — 웹의 [내 AI 실행] 버튼은 이 머신에서 동작하지"
  say "  않습니다. 러너가 꺼지면 이 명령을 다시 실행하세요. (연결 자체에는 영향 없음)"
fi

# ── 4. 연결 확인 → 상주 ──────────────────────────────────────────────────────
say "연결을 확인하는 중…"
BRIDGE_TOKEN="$BRIDGE_TOKEN" "$PY" "$AGENT_PATH" \
  --base "$BRIDGE_BASE" --ca "$CA_PATH" --check \
  || die "연결 확인에 실패했습니다. 토큰이 만료됐다면 웹에서 [연결 명령 복사] 를 다시 누르세요."

# 이미 떠 있는 러너는 정리한다. 두 개가 같은 계정으로 대기하면 같은 질문을 두 번 집으려다
# 한쪽이 409 로 하차하는데, 그 왕복이 사용자 계정 토큰을 태운다.
pkill -f 'bridge_agent.py' >/dev/null 2>&1 || true

say "러너를 상주시킵니다…"
BRIDGE_TOKEN="$BRIDGE_TOKEN" nohup "$PY" "$AGENT_PATH" \
  --base "$BRIDGE_BASE" --ca "$CA_PATH" --resume $RUNNER_ARGS \
  >> "$BRIDGE_HOME/bridge.log" 2>&1 &
BRIDGE_PID=$!
sleep 2
if kill -0 "$BRIDGE_PID" 2>/dev/null; then
  say "완료. 웹 화면의 표시가 '내 AI 대기 중' 으로 바뀌면 질문을 보낼 수 있습니다."
  say "  로그   : $BRIDGE_HOME/bridge.log"
  say "  종료   : kill $BRIDGE_PID   (또는 pkill -f bridge_agent.py)"
  say "  해제   : rm -rf $BRIDGE_HOME  +  핸들러 등록 삭제"
  say "           (Linux: ~/.local/share/applications/mysql-ai-bridge.desktop)"
  [ "$HANDLER_WIN" = "ok" ] && \
    say "           (Windows: reg.exe delete 'HKCU\\Software\\Classes\\mysql-ai-bridge' /f)"
else
  die "러너가 바로 종료됐습니다. 로그를 확인하세요: $BRIDGE_HOME/bridge.log"
fi
