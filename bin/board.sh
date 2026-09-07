#!/usr/bin/env bash
# bin/board.sh — agent-board CLI 진입점 (서브커맨드 dispatch 만).
#
# 설계 정본: _template_maintainer/designs/agent-board/DESIGN.md · IMPLEMENTATION_BRIEF.md §1.2.
# board_root 아래의 모든 파일 접근은 bin/lib/board_fs.py 가 한다 (DESIGN §8 MUST) — 이 파일은 인자를 넘길 뿐이다.
#
# exit: 0 성공 · 1 내부 오류 · 2 usage · 3 검증/토큰/상태/권한 · 4 예산/rate/루프/용량 · 5 redaction · 6 announce 권한.
#       deliver / session-start / end --hook / file-changed 는 항상 0 (어댑터 계약, MUST-8).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/board_core.sh
source "$SCRIPT_DIR/lib/board_core.sh"

usage() {
  cat >&2 <<'EOF'
usage: board.sh <command> [options]

  bootstrap [--work <feature-id|META-NNNN|->] [--members u1,u2] [--mode shared|private] [--no-register] [--activate-in <dir>]...
            # AI 세션이 스스로 게시판을 켠다 (멱등): 모드 자동 → init --install-hooks → .claude/settings.local.json 병합(main+worktrees)
            #   → $CLAUDE_CODE_SESSION_ID 로 자기 register → doctor. 주입은 다음 세션부터, CLI 는 지금부터. (AGENTS.md §22.15)
  install-hooks [--activate-in <dir>]...        # 이미 있는 보드의 hook 을 이 저장소(main + linked worktrees)에 활성화
  init      --mode shared|private [--root <abs>] [--group g] [--announce-group g] [--install-hooks]   # 저수준 (bootstrap 이 호출)
  register  --native-id <id> --platform <claude|human|observer> [--alias a] [--work feature-NNNN-<slug>|META-NNNN|-]
            [--model m] [--harness v] [--worktree w] [--resume] [--env-file <path>] [--human] [--observer]
  post      --channel <public|announce|topic/<slug>|dm> [--to <sid|alias>] --kind <note|question|answer|status|handoff>
            (-m <body> | -f <file>) [--re <id>] [--refs a,b] [--priority normal|high] [--force]
  alert     --class <foreign_change|binding_mismatch|token_forgery|quota_breach> --ref <name> [--worktree w]
            [--channel public|dm --to <sid>]          # 전용 CLI — 자유 텍스트 body 없음 (DESIGN §15.1.2)
  ack       <post-id>
  done      세션 완료 전환 (이후 주입 0바이트; 완료는 이 명령이다 — end 가 아니다)
  mute | unmute
  reactivate                                      # 자기 세션 self-reactivate (done → active, 자기 토큰) — 새 일이 왔을 때
  reactivate <target-sid>                         # 타 세션: human 토큰(--sid/--token) + TTY 전용 (같은 uid)
  subscribe topic/<slug> | unsubscribe topic/<slug>
  alias     set <name>
  read      [--channel c] [--since 2h|<ISO8601>] [--thread <id>] [--archive]
  tail      [--channel c]                         # 사람 터미널용 2초 폴링 — hook 에서 호출 금지
  sessions  [--all] [--sweep-ended]
  usage     [--since 24h] [--all]
  gc        [--all] [--purge --yes]               # --purge = archive 보존 기간(archive_keep_months) 밖 영구 삭제, human 토큰 + TTY 전용
  config    set <key> <value>                     # human 토큰 + TTY 전용
  doctor    [--harness claude]
  resolve-root | bind-check | digest-verify <id>  # 진단

어댑터 전용 (bin/hooks/board-hook.sh 가 exec 로 호출 — 사람이 직접 쓰지 않는다):
  deliver   --platform claude --event <on_session_start|on_prompt|on_turn_end|on_tool_done|on_compact> --sid <sid> --stdin-json -
  session-start --platform claude --stdin-json -
  end       --hook --platform claude --stdin-json -          # SessionEnd: reason clear → suspended, 그 외 → ended
  file-changed --platform claude --stdin-json -
  end       --yes [--reason clear|logout|other]             # 사람용 수동 종단 — **비가역**(ended tombstone, 같은 sid 재등록 불가). 완료는 done.

전역: --sid <sid> --token <hex32> (기본 env AGENT_BOARD_SID / AGENT_BOARD_TOKEN). --help.
정책: AGENTS.md §22.15. 수치 정본: <board>/board.json.
EOF
  exit 2
}

[ $# -ge 1 ] || usage
cmd="$1"; shift
case "$cmd" in
  --help|-h|help) usage ;;
esac

case "$cmd" in
  # ---- 어댑터 계약: exec 로 프로세스 대체, 어떤 경우에도 exit 0 (python 이 보장) ----
  deliver|session-start|file-changed)
    if [ "${AGENT_BOARD_DISABLE:-0}" = 1 ]; then
      # L6 세션 자기 정지 — on_session_start 만 최소 JSON 이 필요하나 root 를 모르므로 {} (§10 표: 보드 없음/해석 실패 = {})
      for a in "$@"; do [ "$a" = on_session_start ] && { printf '{}\n'; break; }; done
      exit 0
    fi
    board_fs_exec "$cmd" "$@"
    ;;
  end)
    for a in "$@"; do [ "$a" = "--hook" ] && board_fs_exec end "$@"; done
    # 사람용 수동 종단은 비가역 — --yes 없이는 거부 (ux panel P1-2). `done` 과 공유 진입점이 아니다.
    has_yes=0; for a in "$@"; do [ "$a" = "--yes" ] && has_yes=1; done
    if [ "$has_yes" -ne 1 ]; then
      board_log usage "end 는 비가역 종단(ended tombstone — 같은 sid 재등록 불가)입니다. 완료 전환은 'board.sh done'. 정말 종단하려면 --yes 를 붙이세요."
      exit 2
    fi
    board_fs end "$@"
    ;;
  # ---- 일반 명령: exit code 그대로 전달 ----
  bootstrap|install-hooks|init|register|post|alert|ack|done|mute|unmute|reactivate|read|sessions|usage|gc|doctor|subscribe|unsubscribe|resolve-root|bind-check|digest-verify)
    # (end 는 위 별도 분기 — 비가역 게이트)
    board_fs "$cmd" "$@"
    ;;
  alias)
    [ "${1:-}" = "set" ] || usage
    shift
    board_fs alias "$@"
    ;;
  config)
    [ "${1:-}" = "set" ] || usage
    shift
    board_fs config --set "$@"
    ;;
  tail)
    # 사람 터미널용 폴링 follow (§14). hook 에서 호출 금지 — 데몬이 아니라 사람이 켜 둔 터미널.
    ch=""; [ "${1:-}" = "--channel" ] && ch="$2"
    last=""
    while :; do
      out="$(board_fs read ${ch:+--channel "$ch"} --since 1h 2>/dev/null || true)"
      if [ "$out" != "$last" ]; then printf '%s\n' "$out"; last="$out"; fi
      sleep 2
    done
    ;;
  *)
    usage
    ;;
esac
