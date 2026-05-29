#!/usr/bin/env bash
#
# template-base-check.sh — Template base vs 소비자 프로젝트 자가 검증.
#
# 설계 근거: 2026-05-19 incident (PR #12) — 소비자 cleanup checklist 가 template
# base 자체에 잘못 적용되어 _template_maintainer/, .claude/commands/_maintainer/,
# unit/feature-0001-example-* 가 삭제됨. 본 스크립트는 그 분기점을 기계 검증으로
# 강제한다.
#
# 정책:
#   - **Template base** = `_template_maintainer/HISTORY.md` 가 존재하고 본문에
#     `## META-CYCLE-` heading ≥ 1 occurrence + `bin/migrations/registry.sh` 가
#     존재.
#   - **소비자 프로젝트** = 위 조건 1개 이상 부재 (cleanup 후 상태 또는 처음부터
#     없음).
#
# /_maintainer:improve SKILL Phase 1 의 2-step guard 와 동일한 신호를 사용한다.
# 분류 우회 옵션 없음 — 모호한 경우 fail-loud + 사용자 명시 확인 위임.
#
# Usage:
#   bin/template-base-check.sh                 # 인자 없음 — 현재 cwd 기준
#   bin/template-base-check.sh --target=<path> # 명시 경로
#   bin/template-base-check.sh --quiet         # exit code only, stdout 침묵
#   bin/template-base-check.sh --help
#
# Exit codes:
#   0 — template base (자가 진단 결과). stdout 에 "template-base" 1줄 출력.
#   1 — 소비자 프로젝트. stdout 에 "consumer" 1줄 + stderr 에 부재 신호 명시.
#   2 — usage error 또는 AGENTS.md 부재 (ai_delegated_dev_template 무관).
#
# Stdout (정상 mode):
#   template-base | consumer
#
# Stderr (verbose):
#   "signals=[A,B,C]" 또는 "missing=[X,Y]" 형식의 진단 1줄.
#
# 호출 예 (FIRST_REQUEST.md 시나리오 0):
#   if bash repo/bin/template-base-check.sh --quiet; then
#     echo "STOP: template base 에서는 시나리오 0 cleanup 을 실행하지 않는다."
#     exit 1
#   fi

set -euo pipefail

# ────────────────────────────────────────────────────────────────────────
# 인자 파싱
# ────────────────────────────────────────────────────────────────────────

TARGET=""
QUIET=0

usage() {
  sed -n '3,40p' "$0"
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target=*) TARGET="${1#--target=}" ;;
    --target) shift; TARGET="${1:-}" ;;
    --quiet|-q) QUIET=1 ;;
    --help|-h) usage ;;
    *)
      printf 'ERROR: unknown option: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

# ────────────────────────────────────────────────────────────────────────
# Policy root 결정
# ────────────────────────────────────────────────────────────────────────

if [ -n "$TARGET" ]; then
  if [ ! -d "$TARGET" ]; then
    printf 'ERROR: --target path not a directory: %s\n' "$TARGET" >&2
    exit 2
  fi
  cd "$TARGET"
fi

POLICY_ROOT=""
if [ -f "repo/AGENTS.md" ]; then
  POLICY_ROOT="repo"
elif [ -f "AGENTS.md" ]; then
  POLICY_ROOT="."
else
  printf 'ERROR: AGENTS.md not found in cwd or cwd/repo/. Not an ai_delegated_dev_template project.\n' >&2
  exit 2
fi

# ────────────────────────────────────────────────────────────────────────
# 2-step base detection (≡ /_maintainer:improve Phase 1)
# ────────────────────────────────────────────────────────────────────────

SIGNALS=()
MISSING=()

# Signal A — _template_maintainer/HISTORY.md 본문 META-CYCLE entry ≥ 1
if [ -f "$POLICY_ROOT/_template_maintainer/HISTORY.md" ]; then
  cycle_count=$(grep -c '^## META-CYCLE-' "$POLICY_ROOT/_template_maintainer/HISTORY.md" 2>/dev/null || echo 0)
  # SIGPIPE-safe count (no grep -q early-exit)
  if [ "${cycle_count:-0}" -gt 0 ]; then
    SIGNALS+=("_template_maintainer/HISTORY.md:META-CYCLE×${cycle_count}")
  else
    MISSING+=("_template_maintainer/HISTORY.md:META-CYCLE-entry-absent")
  fi
else
  MISSING+=("_template_maintainer/HISTORY.md")
fi

# Signal B — bin/migrations/registry.sh
if [ -f "$POLICY_ROOT/bin/migrations/registry.sh" ]; then
  SIGNALS+=("bin/migrations/registry.sh")
else
  MISSING+=("bin/migrations/registry.sh")
fi

# 분류: 두 신호 모두 있어야 template base
if [ ${#MISSING[@]} -eq 0 ]; then
  VERDICT="template-base"
  EXIT=0
else
  VERDICT="consumer"
  EXIT=1
fi

# ────────────────────────────────────────────────────────────────────────
# 출력
# ────────────────────────────────────────────────────────────────────────

if [ "$QUIET" -eq 0 ]; then
  printf '%s\n' "$VERDICT"
fi

if [ ${#SIGNALS[@]} -gt 0 ]; then
  printf 'signals=[%s]\n' "$(IFS=,; echo "${SIGNALS[*]}")" >&2
fi
if [ ${#MISSING[@]} -gt 0 ]; then
  printf 'missing=[%s]\n' "$(IFS=,; echo "${MISSING[*]}")" >&2
fi

exit "$EXIT"
