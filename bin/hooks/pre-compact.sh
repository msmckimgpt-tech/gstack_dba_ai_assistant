#!/usr/bin/env bash
# bin/hooks/pre-compact.sh — PreCompact hook (AGENTS.md §22.1)
#
# 목적: context compaction 발생 직전에 호출되어 압축 차단/허용 여부를 결정한다.
# 등록: .claude/settings.json 의 hooks.PreCompact 에 이 스크립트 경로를 설정한다.
#
# 반환 규칙 (Claude Code PreCompact hook 계약):
#   - stdout JSON {"decision":"block",...} + exit 2 → 압축 차단 (JSON stdout 우선 파싱)
#   - exit 0 (JSON 없음) → 압축 허용
#
# 참고: 이 스크립트는 Claude Code 프로세스의 cwd (project root, .claude/ 상위)에서 실행된다.
# repo/meta/TASK.md 경로는 project root 기준 상대 경로이다.

set -e

TASK_FILE="${TASK_FILE:-repo/meta/TASK.md}"

# in-progress TASK 존재 시 압축 차단 — 중요 컨텍스트 손실 방지
if [ -f "$TASK_FILE" ] && grep -q "status: in-progress" "$TASK_FILE" 2>/dev/null; then
  printf '{"decision":"block","reason":"in-progress TASK exists in %s — context loss risk"}\n' "$TASK_FILE"
  exit 2
fi

# 기본: 압축 허용
exit 0
