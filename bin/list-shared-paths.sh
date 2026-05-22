#!/usr/bin/env bash
#
# list-shared-paths.sh — AGENTS.md §13.2.2 F2 동적 path enumerator.
#
# F2 forbidden 동시-수정 path 의 hardcoded list 를 폐기 (D6C).
# 다음을 stdout 으로 출력 (1 path/line, sort -u):
#   1) repo 안 `*.md` 중 frontmatter 에 `edit_policy: human-guided` 가 있는 파일
#   2) repo 안 `*.md` 중 `<!-- HUMAN-LOCKED:START -->` 마커가 있는 파일
#   3) `repo/shared/**` 모든 일반 파일
#   4) 정적 release artifact (존재할 때만): VERSION, CHANGELOG.md,
#      TEMPLATE_CHANGELOG.md, package.json
#
# Usage:
#   bin/list-shared-paths.sh          # 호출은 repo root 에서. 결과 = path list.
#
# Exit:
#   0 — 항상 (빈 출력 가능).
#
# 호출자 예:
#   ai/* worktree 에서 mutate 전 다음 path 가 list 출력에 있는지 확인.
#
# Notes:
#   - .git/ , node_modules/ , vendor/ , dist/ , build/ 등은 제외.
#   - frontmatter detection 은 "파일 첫 30 라인 안 `edit_policy: human-guided`"
#     매칭 (YAML 다중 라인 edge — TODO T2 참조).

set -eu
# 빈 grep 결과로 인한 SIGPIPE/exit 1 전파를 피하기 위해 pipefail 미설정.

# repo root 자동 감지 (호출 cwd 가 subdir 여도 동작).
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  cd "$(git rev-parse --show-toplevel)"
fi

EXCLUDE_DIRS_REGEX='/\.git/|/node_modules/|/vendor/|/dist/|/build/|/\.template/'

scan_md_frontmatter() {
  # `*.md` 만 대상. 첫 30 라인 안 `edit_policy: human-guided` grep.
  find . -type f -name '*.md' 2>/dev/null \
    | grep -Ev "$EXCLUDE_DIRS_REGEX" \
    | while IFS= read -r f; do
        # head -30 + grep 으로 frontmatter 영역 한정 (false positive 감소).
        if head -30 "$f" 2>/dev/null | grep -Eq '^[[:space:]]*edit_policy:[[:space:]]*human-guided[[:space:]]*$'; then
          # leading ./ 제거 → repo-relative path.
          printf '%s\n' "${f#./}"
        fi
      done
}

scan_human_locked_marker() {
  # 전체 파일 scan — 마커가 frontmatter 밖에 있을 수 있음.
  find . -type f -name '*.md' 2>/dev/null \
    | grep -Ev "$EXCLUDE_DIRS_REGEX" \
    | while IFS= read -r f; do
        if grep -qF '<!-- HUMAN-LOCKED:START -->' "$f" 2>/dev/null; then
          printf '%s\n' "${f#./}"
        fi
      done
}

scan_shared_tree() {
  if [ -d "shared" ]; then
    find shared -type f 2>/dev/null \
      | grep -Ev "$EXCLUDE_DIRS_REGEX" \
      | sed 's|^\./||'
  fi
}

scan_release_artifacts() {
  local f
  for f in VERSION CHANGELOG.md TEMPLATE_CHANGELOG.md package.json; do
    if [ -f "$f" ]; then
      printf '%s\n' "$f"
    fi
  done
}

# v3.11.0: feature-bound REPORT.md 동적 enumeration (§13.1.a + §13.2.2 F2 확장).
# unit/<feature-id>/meta/REPORT.md 는 해당 feature 의 단일 worktree mutator 전용.
scan_feature_report_md() {
  find unit -maxdepth 3 -path '*/meta/REPORT.md' 2>/dev/null | sort -u | sed 's|^\./||'
}

{
  scan_md_frontmatter
  scan_human_locked_marker
  scan_shared_tree
  scan_release_artifacts
  scan_feature_report_md
} | sort -u
