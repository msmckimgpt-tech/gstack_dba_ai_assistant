#!/usr/bin/env bash
# wiki-lint.sh — Wiki 의 structural health check (v3.13.0+)
#
# 출처 (web evidence): SamurAIGPT/llm-wiki-agent (2.7k stars) 의 CLAUDE.md
# "Lint Workflow" verbatim 6-category 중 structural 3개를 자동화.
# + namu 편집지침 (https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C)
# 의 "150자 ≥ sub-문단 5 ≥" 분리 권장 추가.
#
# Usage:
#   bash bin/wiki-lint.sh              # default: WARN-only, exit 0
#   bash bin/wiki-lint.sh --strict     # 발견 시 exit 1
#   bash bin/wiki-lint.sh --check orphan|broken|missing-entity|split
#   bash bin/wiki-lint.sh --json
#   bash bin/wiki-lint.sh --help

set -u
# Note: set -e disabled — function 들이 finding count 를 return $found 로 반환하므로
# 자동 종료 회피. 명시적 exit code 처리는 TOTAL 카운트 + --strict flag 로.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../AGENTS.md" ]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif git rev-parse --show-toplevel >/dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(pwd)"
fi
WIKI_DIR="$REPO_ROOT/wiki"

STRICT=0
JSON=0
SPECIFIC_CHECK=""

usage() {
  cat <<EOF
Usage: bash bin/wiki-lint.sh [OPTIONS]

Options:
  --check <name>   Run only this check (orphan | broken | missing-entity | split)
  --strict         Exit code 1 on findings (default: WARN-only, exit 0)
  --json           Output machine-readable JSON
  --help           Show this help
EOF
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --check) SPECIFIC_CHECK="$2"; shift 2 ;;
    --strict) STRICT=1; shift ;;
    --json) JSON=1; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [ ! -d "$WIKI_DIR" ]; then
  echo "[wiki-lint] $WIKI_DIR not found — wiki/ vault 미도입 (v3.12.0 이전)" >&2
  exit 0
fi

collect_pages() {
  find "$WIKI_DIR" -type f -name '*.md' \
    -not -path '*/raw/*' \
    -not -path '*/.obsidian/*' \
    -not -path '*/_attachments/*' \
    -not -path '*/.trash/*' \
    | sort
}

check_orphan() {
  local found=0
  local issues=()
  local all_pages
  mapfile -t all_pages < <(collect_pages)
  local page rel slug
  for page in "${all_pages[@]}"; do
    rel="${page#$WIKI_DIR/}"
    case "$rel" in
      Index.md|Log.md|README.md|overview.md|_template*|*/_Index.md|*/_template*) continue ;;
      raw/*) continue ;;
    esac
    slug="$(basename "${rel%.md}")"
    if ! grep -rqE "\[\[(\.\./|.+/)*${slug}(\||\]\])" "$WIKI_DIR" --include='*.md' \
         --exclude-dir=raw --exclude-dir=.obsidian 2>/dev/null; then
      issues+=("$rel")
      found=$((found + 1))
    fi
  done
  if [ "$JSON" = "1" ]; then
    printf '"orphan": ['
    local first=1 item
    for item in "${issues[@]}"; do
      if [ "$first" = "1" ]; then first=0; else printf ','; fi
      printf '"%s"' "$item"
    done
    printf ']'
  else
    if [ "$found" -eq 0 ]; then
      printf '[wiki-lint] orphan: PASS (0)\n' >&2
    else
      printf '[wiki-lint] orphan: WARN (%d page)\n' "$found" >&2
      local item
      for item in "${issues[@]}"; do printf '  - %s\n' "$item" >&2; done
    fi
  fi
  return $found
}

check_broken() {
  local found=0
  local issues=()
  local all_pages
  mapfile -t all_pages < <(collect_pages)
  local page rel link target target_path basename_only page_dir resolved
  for page in "${all_pages[@]}"; do
    rel="${page#$WIKI_DIR/}"
    while IFS= read -r link; do
      target="${link%|*}"
      target="${target%%#*}"
      target="${target#\[\[}"
      target="${target%\]\]}"
      target="${target%\\}"  # trailing backslash (escaped \]]) strip
      case "$target" in
        ''|http://*|https://*) continue ;;
        # vault 외부 (.. 시작) 는 정본 docs/unit/ 로 가는 의도된 link — skip
        ..*|*../docs/*|*../unit/*|*../AGENTS*|*../CLAUDE*|*../GEMINI*|*../README*) continue ;;
        # placeholder syntax (<...> 또는 example) — skip
        *\<*|*example*|*XXXX*|*wikilink*|*\<slug\>*) continue ;;
      esac
      case "$target" in
        *.md) target_path="$target" ;;
        *) target_path="${target}.md" ;;
      esac
      page_dir="$(dirname "$rel")"
      if [ "$page_dir" = "." ]; then
        resolved="$WIKI_DIR/$target_path"
      else
        resolved="$WIKI_DIR/$page_dir/$target_path"
      fi
      basename_only="$(basename "$target_path")"
      if [ ! -f "$resolved" ] \
         && ! find "$WIKI_DIR" -name "$basename_only" -type f -not -path '*/raw/*' \
              -not -path '*/.obsidian/*' 2>/dev/null | grep -q .; then
        issues+=("$rel → [[$target]]")
        found=$((found + 1))
      fi
    done < <(grep -oE '\[\[[^][]+\]\]' "$page" 2>/dev/null || true)
  done
  if [ "$JSON" = "1" ]; then
    printf '"broken": ['
    local first=1 item
    for item in "${issues[@]}"; do
      if [ "$first" = "1" ]; then first=0; else printf ','; fi
      printf '"%s"' "$(echo "$item" | sed 's/"/\\"/g')"
    done
    printf ']'
  else
    if [ "$found" -eq 0 ]; then
      printf '[wiki-lint] broken: PASS (0)\n' >&2
    else
      printf '[wiki-lint] broken: WARN (%d link)\n' "$found" >&2
      local item
      for item in "${issues[@]}"; do printf '  - %s\n' "$item" >&2; done
    fi
  fi
  return $found
}

check_missing_entity() {
  local found=0
  local issues=()
  if [ ! -d "$WIKI_DIR/entities" ]; then
    if [ "$JSON" = "1" ]; then printf '"missing-entity": []'; else
      printf '[wiki-lint] missing-entity: SKIP (entities/ 부재)\n' >&2
    fi
    return 0
  fi
  local mention
  mention=$(grep -rohE '\[\[[A-Z][A-Za-z0-9_-]{2,}\]\]' "$WIKI_DIR" \
            --include='*.md' --exclude-dir=raw --exclude-dir=entities --exclude-dir=.obsidian 2>/dev/null \
            | sort | uniq -c | sort -rn || true)
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    local count name slug
    count="$(echo "$line" | awk '{print $1}')"
    name="$(echo "$line" | sed -E 's/^[[:space:]]*[0-9]+[[:space:]]+\[\[([^][]+)\]\].*$/\1/')"
    slug="$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
    if [ "$count" -ge 3 ] && [ ! -f "$WIKI_DIR/entities/$name.md" ] && [ ! -f "$WIKI_DIR/entities/$slug.md" ]; then
      issues+=("$name ($count refs)")
      found=$((found + 1))
    fi
  done <<< "$mention"
  if [ "$JSON" = "1" ]; then
    printf '"missing-entity": ['
    local first=1 item
    for item in "${issues[@]}"; do
      if [ "$first" = "1" ]; then first=0; else printf ','; fi
      printf '"%s"' "$(echo "$item" | sed 's/"/\\"/g')"
    done
    printf ']'
  else
    if [ "$found" -eq 0 ]; then
      printf '[wiki-lint] missing-entity: PASS (0)\n' >&2
    else
      printf '[wiki-lint] missing-entity: WARN (%d) — %s\n' "$found" "${issues[*]}" >&2
    fi
  fi
  return $found
}

check_split() {
  local found=0
  local issues=()
  local all_pages
  mapfile -t all_pages < <(collect_pages)
  local page rel long_subs
  for page in "${all_pages[@]}"; do
    rel="${page#$WIKI_DIR/}"
    case "$rel" in
      Log.md|README.md|_template*|*/_template*|raw/*) continue ;;
    esac
    long_subs=$(awk '
      /^### / { if (in_sub && length(sub_text) > 150) long++;
                in_sub = 1; sub_text = ""; next
              }
      /^## /  { if (in_sub && length(sub_text) > 150) long++;
                in_sub = 0; sub_text = ""; next
              }
      in_sub  { sub_text = sub_text $0 }
      END     { if (in_sub && length(sub_text) > 150) long++;
                print long+0 }
    ' "$page")
    if [ "${long_subs:-0}" -ge 5 ]; then
      issues+=("$rel ($long_subs long sub-sections)")
      found=$((found + 1))
    fi
  done
  if [ "$JSON" = "1" ]; then
    printf '"split-suggest": ['
    local first=1 item
    for item in "${issues[@]}"; do
      if [ "$first" = "1" ]; then first=0; else printf ','; fi
      printf '"%s"' "$(echo "$item" | sed 's/"/\\"/g')"
    done
    printf ']'
  else
    if [ "$found" -eq 0 ]; then
      printf '[wiki-lint] split-suggest: PASS (0)\n' >&2
    else
      printf '[wiki-lint] split-suggest: INFO (%d page, namu 편집지침 150자 sub 5+ 기준)\n' "$found" >&2
      local item
      for item in "${issues[@]}"; do printf '  - %s\n' "$item" >&2; done
    fi
  fi
  return $found
}

TOTAL=0
if [ "$JSON" = "1" ]; then
  printf '{'
  first_json=1
  for chk in orphan broken missing-entity split; do
    if [ -n "$SPECIFIC_CHECK" ] && [ "$SPECIFIC_CHECK" != "$chk" ]; then continue; fi
    if [ "$first_json" = "0" ]; then printf ','; fi
    case "$chk" in
      orphan) check_orphan; n=$? ;;
      broken) check_broken; n=$? ;;
      missing-entity) check_missing_entity; n=$? ;;
      split) check_split; n=$? ;;
    esac
    TOTAL=$((TOTAL + n))
    first_json=0
  done
  printf '}\n'
else
  for chk in orphan broken missing-entity split; do
    if [ -n "$SPECIFIC_CHECK" ] && [ "$SPECIFIC_CHECK" != "$chk" ]; then continue; fi
    case "$chk" in
      orphan) check_orphan; n=$? ;;
      broken) check_broken; n=$? ;;
      missing-entity) check_missing_entity; n=$? ;;
      split) check_split; n=$? ;;
    esac
    TOTAL=$((TOTAL + n))
  done
  if [ "$TOTAL" -eq 0 ]; then
    printf '[wiki-lint] all structural checks PASS\n' >&2
  else
    printf '[wiki-lint] total %d findings (WARN-only — v3.13.0 정책, --strict 로 exit 1 격상)\n' "$TOTAL" >&2
  fi
fi

if [ "$STRICT" = "1" ] && [ "$TOTAL" -gt 0 ]; then
  exit 1
fi
exit 0
