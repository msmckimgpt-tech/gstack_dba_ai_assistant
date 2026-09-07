#!/usr/bin/env bash
# bin/hooks/board-hook.sh — agent-board 의 Claude Code hook 어댑터 (DESIGN.md §11.1 · BRIEF §2.1).
#
# 계약 (MUST-8 · 단일 계약): **어떤 입력에도 exit 0**, `decision`/`continue` 필드를 내지 않는다.
#   플랫폼은 settings 블록이 `--platform claude` 로 **선언**한다 — env 스니핑은 python 의 교차확인일 뿐이다.
#   P1 은 Claude Code 만 동작한다 (Q-8). `--platform codex|gemini` 는 주입 없이 exit 0 (platform_unsupported 로그).
#
# 이 스크립트는 stdin 을 그대로 넘기며 `exec board.sh …` 로 **자기 프로세스를 대체**한다 (§10 출력 경계):
#   deliver 가 최종 JSON 을 직접 하네스에 쓰므로 «flush 뒤, 하네스 도달 전» 에 끼어드는 프로세스가 없다.
#
# 이벤트 매핑 (stdin.hook_event_name — 2026-09-04 Claude 2.1.227 실측 어휘):
#   SessionStart(startup|resume|clear|fork) → session-start  (register + cursor 초기화 + deliver, 항상 JSON 1개,
#                                                            hookSpecificOutput.watchPaths=[<board>/seq/SEQ])
#   SessionStart(compact)                   → session-start  (python 이 source==compact 를 on_compact 로 처리)
#   UserPromptSubmit                        → deliver on_prompt
#   Stop                                    → deliver on_turn_end   (stop_hook_active 는 python 이 단락; decision 없음)
#   PostToolUse | PostToolBatch (opt-in)    → deliver on_tool_done
#   FileChanged                             → file-changed (file_path==<board>/seq/SEQ ∧ event∈{change,add} → PENDING + systemMessage)
#   PreCompact                              → 무출력 (기록만)
#   SessionEnd                              → end --hook (clear → suspended, 그 외 → ended; 항상 0)
#
# 절대경로 계약 (§11.1): `init --install-hooks` 가 이 파일의 realpath 로 settings 블록을 만든다. 상대경로 `repo/bin/...`
#   는 linked worktree cwd 에서 존재하지 않아 exit 0 으로 삼켜진다 — 쓰지 않는다.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
BOARD_SH="$SCRIPT_DIR/../board.sh"

platform=""
while [ $# -gt 0 ]; do
  case "$1" in
    --platform) platform="${2:-}"; shift 2 ;;
    --platform=*) platform="${1#--platform=}"; shift ;;
    *) shift ;;
  esac
done

# 플랫폼 미선언 → 무동작 (BRIEF §2.5: «--platform 미선언 호출 → exit 0 무출력»)
[ -n "$platform" ] || exit 0
[ -x "$BOARD_SH" ] || [ -f "$BOARD_SH" ] || exit 0

# stdin 을 한 번 읽어 이벤트명만 뽑고, 본문은 그대로 넘긴다 (파싱 실패 → 무출력 exit 0).
input="$(cat 2>/dev/null || true)"
event="$(printf '%s' "$input" | python3 -c 'import json,sys
try:
    o=json.load(sys.stdin); print(o.get("hook_event_name","") if isinstance(o,dict) else "")
except Exception:
    print("")' 2>/dev/null || true)"

case "$event" in
  SessionStart)
    printf '%s' "$input" | exec bash "$BOARD_SH" session-start --platform "$platform" --stdin-json - ;;
  UserPromptSubmit)
    printf '%s' "$input" | exec bash "$BOARD_SH" deliver --platform "$platform" --event on_prompt --stdin-json - ;;
  Stop)
    printf '%s' "$input" | exec bash "$BOARD_SH" deliver --platform "$platform" --event on_turn_end --stdin-json - ;;
  PostToolUse|PostToolBatch)
    printf '%s' "$input" | exec bash "$BOARD_SH" deliver --platform "$platform" --event on_tool_done --stdin-json - ;;
  FileChanged)
    printf '%s' "$input" | exec bash "$BOARD_SH" file-changed --platform "$platform" --stdin-json - ;;
  SessionEnd)
    printf '%s' "$input" | exec bash "$BOARD_SH" end --hook --platform "$platform" --stdin-json - ;;
  *)
    exit 0 ;;
esac
