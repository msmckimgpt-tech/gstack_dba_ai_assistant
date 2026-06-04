#!/usr/bin/env bash
# bin/playwright-mcp.sh
#
# feature-0008 — Playwright MCP (@playwright/mcp) 를 **실제 Windows 브라우저**(CDP)에
# attach 시켜 Claude Code(VSCode/CLI)에 native in-loop 브라우저 도구를 제공하는 launcher.
#
# 역할 분담:
#   - bin/win-browser.py  : 브리지 성립(Chrome + 무권한 relay) + 스크립트/시나리오(run) +
#                            완료 게이트 증거(TEST.md §3) + CI. ← 브리지를 먼저 띄운다.
#   - 본 스크립트(MCP)     : 그 위에서 대화형(in-loop) 탐색/조작 — browser_snapshot(a11y),
#                            browser_click/type 등 MCP 도구를 모델 루프에서 직접 사용.
#   둘 다 **같은 relay/Chrome** 에 attach (동일 화면). MCP 는 `connect_over_cdp` 와 동일
#   메커니즘으로 Windows Chrome 에 붙으므로 로컬 브라우저 바이너리 불요.
#
# 동작:
#   1. relay endpoint 해석: WIN_BROWSER_CDP_ENDPOINT 우선, 없으면 http://<win_host>:<relay_port>
#      (win_host = /etc/resolv.conf nameserver 또는 기본 게이트웨이; relay_port=WIN_BROWSER_RELAY_PORT|9223)
#   2. (옵션) WIN_BROWSER_MCP_AUTOLAUNCH=1 이면, endpoint 미도달 시 win-browser.py launch 로
#      Chrome+무권한 relay 자동 기동 (기본 off — 예기치 않은 브라우저 창 방지).
#   3. exec npx -y @playwright/mcp@latest --cdp-endpoint="<EP>" "$@"   (stdio MCP server)
#
# Claude Code 등록 (project scope):
#   claude mcp add --scope project playwright -- bash <repo>/bin/playwright-mcp.sh
#   (또는 repo/.mcp.json 참조 — 첫 사용 시 사용자 승인 필요)
#
# 환경변수:
#   WIN_BROWSER_CDP_ENDPOINT   CDP HTTP endpoint 강제 지정 (기본 자동 해석)
#   WIN_BROWSER_RELAY_PORT     relay 포트 (default 9223 — win-browser.py 와 일치)
#   WIN_BROWSER_MCP_AUTOLAUNCH 1 이면 미도달 시 win-browser.py launch 자동 호출
#   PLAYWRIGHT_MCP_EXTRA_ARGS  추가 인자 (예: "--headless" / "--isolated")

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELAY_PORT="${WIN_BROWSER_RELAY_PORT:-9223}"

resolve_win_host() {
  local ns
  ns="$(grep -m1 '^nameserver' /etc/resolv.conf 2>/dev/null | awk '{print $2}')"
  if [ -n "$ns" ]; then printf '%s\n' "$ns"; return; fi
  ip route show default 2>/dev/null | awk '/via/{print $3; exit}'
}

if [ -n "${WIN_BROWSER_CDP_ENDPOINT:-}" ]; then
  EP="${WIN_BROWSER_CDP_ENDPOINT%/}"
else
  WIN_HOST="$(resolve_win_host)"
  [ -n "$WIN_HOST" ] || { echo "[playwright-mcp] WIN host IP 해석 실패 — WIN_BROWSER_CDP_ENDPOINT 지정 필요" >&2; exit 1; }
  EP="http://${WIN_HOST}:${RELAY_PORT}"
fi

# endpoint 도달 확인 (옵션 autolaunch).
if ! curl -s -m 3 "${EP}/json/version" >/dev/null 2>&1; then
  if [ "${WIN_BROWSER_MCP_AUTOLAUNCH:-0}" = "1" ] && [ -f "$SCRIPT_DIR/win-browser.py" ]; then
    echo "[playwright-mcp] 브리지 미도달 → win-browser.py launch 자동 기동" >&2
    python3 "$SCRIPT_DIR/win-browser.py" launch >/dev/null 2>&1 || true
  else
    echo "[playwright-mcp] WARN: ${EP} CDP 미도달 — 먼저 'python3 bin/win-browser.py launch' 실행 권장 (또는 WIN_BROWSER_MCP_AUTOLAUNCH=1)" >&2
  fi
fi

echo "[playwright-mcp] attach → ${EP}" >&2
# shellcheck disable=SC2086
exec npx -y @playwright/mcp@latest --cdp-endpoint="${EP}" ${PLAYWRIGHT_MCP_EXTRA_ARGS:-} "$@"
