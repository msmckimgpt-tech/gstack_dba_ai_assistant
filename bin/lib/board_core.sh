#!/usr/bin/env bash
# bin/lib/board_core.sh — agent-board 의 bash 함수 라이브러리 (DESIGN.md §20 부록 A 규율).
#
# 규칙 (DESIGN §8 MUST · BRIEF §1.1): 이 파일과 board.sh 는 **board_root 아래 경로를 coreutils 에 넘기지 않는다**.
#   board_root 아래의 모든 파일 접근은 `board_fs.py` 서브커맨드 호출로만 표현한다. 여기 남는 것은
#   인자 검증 · 프로세스 오케스트레이션 · exit code 매핑 · usage 출력이다.
#   bats 가 «bash 소스에 $BOARD_ROOT 를 인자로 받는 coreutils 호출 0건» 을 정적으로 단언한다 (BRIEF §1.5-37).
#
# 보안 검증(sid·slug 등)은 bash regex 로 하지 않는다 (AGENTS.md §22.14) — python re.fullmatch 로 위임.
#
# exit code 정본: DESIGN §9. 이 라이브러리는 board_fs.py 의 exit code 를 **그대로** 전달한다.

# shellcheck disable=SC2034
BOARD_CORE_VERSION="0.9.4"

# --- 경로 ---------------------------------------------------------------------
board_lib_dir() {
  local src="${BASH_SOURCE[0]}"
  while [ -L "$src" ]; do src="$(readlink "$src")"; done
  cd "$(dirname "$src")" && pwd -P
}
BOARD_LIB="${BOARD_LIB:-$(board_lib_dir)}"
BOARD_FS="${BOARD_FS:-$BOARD_LIB/board_fs.py}"

# --- 로그 (board_root 밖 — stderr 만) ------------------------------------------
board_log() {   # $1=level $2=reason [$3=msg]
  printf 'board.sh[%s]: %s%s\n' "$1" "$2" "${3:+ — $3}" >&2
}

# --- python3 위임 ----------------------------------------------------------------
# 모든 board_root 접근은 여기로만. cwd 는 호출자의 것을 그대로 넘긴다 (§4.2 해석은 python 이 한다).
board_fs() {
  python3 "$BOARD_FS" --cwd "$PWD" "$@"
}

# 어댑터 전용: 자기 프로세스를 board_fs.py 로 대체한다 (§10 출력 경계 — R2 P1-10).
board_fs_exec() {
  exec python3 "$BOARD_FS" --cwd "$PWD" "$@"
}

# --- 인자 검증 (형식만 — 의미 검증은 python) ------------------------------------
board_require_arg() {   # $1=name $2=value
  if [ -z "${2:-}" ]; then
    board_log usage "missing --$1"
    return 2
  fi
}

board_validate_sid() {   # 부록 A-4: 파일 접근이 없으므로 인라인 python 허용
  python3 -c 'import re,sys; sys.exit(0 if re.fullmatch(r"[a-z0-9-]{1,16}:[a-z_][a-z0-9_-]{0,31}:[A-Za-z0-9_.-]{1,80}", sys.argv[1]) else 3)' "$1"
}

board_validate_event() {
  case "$1" in
    on_session_start|on_prompt|on_turn_end|on_tool_done|on_compact) return 0 ;;
    *) return 2 ;;
  esac
}

board_validate_platform_p1() {   # Q-8: P1 은 claude 만 동작. 다른 값은 파싱은 되되 no-op (python 이 platform_unsupported 로그).
  case "$1" in
    claude|codex|gemini) return 0 ;;
    *) return 2 ;;
  esac
}

# --- resolve (사람용 진단) -------------------------------------------------------
board_resolve_root() {   # stdout: board_root 또는 빈 줄 (보드 없음). 검증 실패 → rc 3
  board_fs resolve-root
}
