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
set -eu

BRIDGE_BASE="${BRIDGE_BASE:-}"
BRIDGE_TOKEN="${BRIDGE_TOKEN:-}"
BRIDGE_CA_SHA256="${BRIDGE_CA_SHA256:-}"
BRIDGE_AGENT_SHA256="${BRIDGE_AGENT_SHA256:-}"
BRIDGE_HOME="${BRIDGE_HOME:-$HOME/.mysql-ai-bridge}"
BRIDGE_ARGS="${BRIDGE_ARGS:-}"

die() { printf '\n[bridge-setup] 중단: %s\n' "$1" >&2; exit 1; }
say() { printf '[bridge-setup] %s\n' "$1"; }

[ -n "$BRIDGE_BASE" ] || die "BRIDGE_BASE 가 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요."
[ -n "$BRIDGE_TOKEN" ] || die "BRIDGE_TOKEN 이 비어 있습니다. 웹 콘솔의 [연결 명령 복사] 로 받은 명령을 그대로 실행하세요."

PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || die "python3 이 없습니다. 파이썬 3.8 이상을 설치한 뒤 다시 실행하세요."
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
TOKEN=\$(printf '%s' "\$URL" | sed -n 's/.*[?&]token=\([^&]*\).*/\1/p')
[ -n "\$TOKEN" ] || { printf 'token 이 없습니다: %s\n' "\$URL" >&2; exit 2; }
# ⚠ 이 스킴은 **아무 웹페이지나 열 수 있다**. 그래서 토큰을 확인하기 전에는 아무것도 죽이지
#   않는다 — 종전엔 곧바로 pkill 이라, 임의 사이트가 쓰레기 토큰으로 이 URL 을 열게 하는 것만으로
#   정상 러너를 끌 수 있었다(codex 적대 리뷰 P2). 순서를 뒤집는다: **먼저 검증, 그다음 교체.**
case "\$TOKEN" in
  mat_*) ;;
  *) printf 'token 형식이 아닙니다 — 무시합니다.\n' >&2; exit 2 ;;
esac
BRIDGE_TOKEN="\$TOKEN" $PY "\$BRIDGE_HOME/bridge_agent.py" \\
  --base '$BRIDGE_BASE' --ca "\$BRIDGE_HOME/rootCA.crt" --check >/dev/null 2>&1 \\
  || { printf '토큰이 유효하지 않습니다 — 실행 중인 러너를 그대로 둡니다.\n' >&2; exit 3; }
pkill -f 'bridge_agent.py' >/dev/null 2>&1 || true
BRIDGE_TOKEN="\$TOKEN" nohup $PY "\$BRIDGE_HOME/bridge_agent.py" \\
  --base '$BRIDGE_BASE' --ca "\$BRIDGE_HOME/rootCA.crt" --resume $BRIDGE_ARGS \\
  >> "\$BRIDGE_HOME/bridge.log" 2>&1 &
LAUNCHEOF
chmod 700 "$LAUNCH_SH"

register_handler() {
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
      command -v xdg-mime >/dev/null 2>&1 || return 1
      DESKTOP_DIR="$HOME/.local/share/applications"
      mkdir -p "$DESKTOP_DIR"
      cat > "$DESKTOP_DIR/mysql-ai-bridge.desktop" <<DESKEOF
[Desktop Entry]
Type=Application
Name=mysql-ai bridge launcher
Exec=$LAUNCH_SH %u
NoDisplay=true
Terminal=false
MimeType=x-scheme-handler/mysql-ai-bridge;
DESKEOF
      update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
      xdg-mime default mysql-ai-bridge.desktop x-scheme-handler/mysql-ai-bridge >/dev/null 2>&1 || return 1
      ;;
    *) return 1 ;;
  esac
  return 0
}

if register_handler; then
  say "웹 [내 AI 실행] 버튼용 핸들러를 등록했습니다 (mysql-ai-bridge://)."
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
  --base "$BRIDGE_BASE" --ca "$CA_PATH" --resume $BRIDGE_ARGS \
  >> "$BRIDGE_HOME/bridge.log" 2>&1 &
BRIDGE_PID=$!
sleep 2
if kill -0 "$BRIDGE_PID" 2>/dev/null; then
  say "완료. 웹 화면의 표시가 '내 AI 대기 중' 으로 바뀌면 질문을 보낼 수 있습니다."
  say "  로그   : $BRIDGE_HOME/bridge.log"
  say "  종료   : kill $BRIDGE_PID   (또는 pkill -f bridge_agent.py)"
  say "  해제   : rm -rf $BRIDGE_HOME  +  핸들러 등록 파일 삭제"
  say "           (Linux: ~/.local/share/applications/mysql-ai-bridge.desktop)"
else
  die "러너가 바로 종료됐습니다. 로그를 확인하세요: $BRIDGE_HOME/bridge.log"
fi
