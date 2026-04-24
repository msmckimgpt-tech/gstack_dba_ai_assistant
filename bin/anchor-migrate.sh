#!/usr/bin/env bash
#
# anchor-migrate.sh — migration day tool. One-shot installer/bootstrapper for:
#   1. ANCHOR.md skeleton copied into every existing unit/feature-* directory
#   2. Seed empty commit per feature with `Task-Cycle: MIGRATION` trailer
#      (establishes cycle boundary baseline — see eng review Decision 3)
#   3. post-commit hook installation + install-verification test
#      (critical gap fix — see eng review Failure Modes section)
#
# Usage:
#   bin/anchor-migrate.sh              # run migration
#   bin/anchor-migrate.sh --dry-run    # preview, no side effects
#   bin/anchor-migrate.sh --help
#
# Idempotent: re-running is safe. Features that already have ANCHOR.md are skipped.
# Features that already have a MIGRATION seed trailer are skipped.

set -euo pipefail

DRY_RUN=0

usage() {
  cat >&2 <<'EOF'
Usage:
  bin/anchor-migrate.sh              # run migration (creates ANCHOR.md, seed commits, installs hook)
  bin/anchor-migrate.sh --dry-run    # preview actions, make no changes
  bin/anchor-migrate.sh --help
EOF
  exit 2
}

die() { printf 'ERROR: %s\n' "$1" >&2; exit "${2:-1}"; }
say() { printf '%s\n' "$1" >&2; }
dry() { [ "$DRY_RUN" = "1" ]; }

require_git_repo() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"
  cd "$(git rev-parse --show-toplevel)"
}

# Ensure the skeleton file exists before we start copying from it.
ensure_skeleton() {
  local skeleton="unit/_template/docs/ANCHOR.md"
  if [ ! -f "$skeleton" ]; then
    die "ANCHOR.md skeleton not found at $skeleton. Implement Module A first."
  fi
  printf '%s' "$skeleton"
}

# Build list of feature dirs (unit/feature-*, unit/META-*). Excludes _template.
list_features() {
  find unit -maxdepth 1 -type d \( -name 'feature-*' -o -name 'META-*' \) 2>/dev/null | sort
}

# Copy skeleton into a feature, rewriting frontmatter.
install_anchor_for_feature() {
  local fdir="$1" skeleton="$2"
  local target="${fdir}/docs/ANCHOR.md"
  local fid
  fid=$(basename "$fdir")

  if [ -f "$target" ]; then
    say "  [SKIP] ANCHOR.md already exists at $target"
    return 0
  fi

  if dry; then
    say "  [DRY] would create $target with feature_id=$fid"
    return 0
  fi

  # Copy skeleton, replace placeholders
  local now_iso
  now_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  sed \
    -e "s|feature_id: feature-xxxx-template|feature_id: ${fid}|" \
    -e "s|created_at: YYYY-MM-DDTHH:MM:SSZ|created_at: ${now_iso}|" \
    -e "s|# ANCHOR: <feature-id> <feature-name>|# ANCHOR: ${fid}|" \
    "$skeleton" > "$target"

  say "  [DONE] created $target"
}

# Create a seed empty commit with Task-Cycle: MIGRATION trailer.
# Idempotent: skip if HEAD already contains such a seed for this feature.
seed_cycle_for_feature() {
  local fdir="$1"
  local fid
  fid=$(basename "$fdir")

  # Have we already seeded this feature?
  if git log --grep="^Task-Cycle: ${fid}$" --grep="^migration-seed$" --all-match \
       --format=%H 2>/dev/null | head -1 | grep -q .; then
    say "  [SKIP] seed commit already exists for $fid"
    return 0
  fi

  if dry; then
    say "  [DRY] would create seed empty commit for $fid"
    return 0
  fi

  # Need HEAD before we can create empty commits. If repo has no commits, bail.
  if ! git rev-parse HEAD >/dev/null 2>&1; then
    die "repo has no commits yet; cannot create seed"
  fi

  git commit --allow-empty -m "chore(${fid}): migration-seed

Establishes Task-Cycle baseline for external-anchor enforcement.
All subsequent ANCHOR.md §4 entries for this feature count from this commit forward.

Task-Cycle: ${fid}
migration-seed" >/dev/null

  say "  [DONE] seed commit for $fid: $(git rev-parse --short HEAD)"
}

install_hook_with_verify() {
  local hooks_script="bin/install-hooks.sh"
  if [ ! -x "$hooks_script" ]; then
    die "bin/install-hooks.sh missing or not executable"
  fi

  if dry; then
    say "  [DRY] would run $hooks_script"
    return 0
  fi

  # Run installer + capture both stdout and stderr.
  local output rc=0
  output=$(bash "$hooks_script" 2>&1) || rc=$?

  printf '%s\n' "$output" | sed 's/^/  /'

  if [ "$rc" -ne 0 ]; then
    die "post-commit hook installation FAILED (rc=$rc). See output above."
  fi

  # Explicit post-install verification (double-check — critical gap insurance).
  local check_output check_rc=0
  check_output=$(bash "$hooks_script" --check 2>&1) || check_rc=$?
  printf '%s\n' "$check_output" | sed 's/^/  /'

  if [ "$check_rc" -ne 0 ]; then
    die "post-install verification FAILED (rc=$check_rc). Hook NOT reliable."
  fi

  say "  [DONE] post-commit hook installed and verified"
}

main() {
  if [ $# -ge 1 ]; then
    case "$1" in
      --help|-h) usage ;;
      --dry-run) DRY_RUN=1 ;;
      *) die "unknown option: $1" 2 ;;
    esac
  fi

  require_git_repo

  local skeleton
  skeleton=$(ensure_skeleton)

  say ""
  say "=== anchor-migrate.sh ==="
  if dry; then
    say "DRY RUN — no changes will be made"
  fi
  say ""

  say "Step 1/3: Install ANCHOR.md for each existing feature"
  local features
  features=$(list_features)
  if [ -z "$features" ]; then
    say "  (no features found under unit/ other than _template)"
  else
    local f
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      install_anchor_for_feature "$f" "$skeleton"
    done <<<"$features"
  fi
  say ""

  say "Step 2/3: Install post-commit hook + verify installation"
  install_hook_with_verify
  say ""

  say "Step 3/3: Seed Task-Cycle trailer commits per feature"
  # Commit the ANCHOR.md files first if we just created them (and NOT dry).
  if ! dry && [ -n "$features" ]; then
    # Stage new ANCHOR.md files explicitly
    local anchors=()
    local f
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      local anchor_path="${f}/docs/ANCHOR.md"
      if [ -f "$anchor_path" ]; then
        if git ls-files --error-unmatch "$anchor_path" >/dev/null 2>&1; then
          :  # already tracked
        else
          anchors+=("$anchor_path")
        fi
      fi
    done <<<"$features"

    if [ "${#anchors[@]}" -gt 0 ]; then
      git add "${anchors[@]}"
      git commit -m "chore: migration-init — ANCHOR.md skeletons for existing features

Installed ANCHOR.md skeleton for $(printf '%s\n' "${anchors[@]}" | wc -l | tr -d ' ') feature(s).
Part of migration day (see design doc: Module A rollout).

Task-Cycle: MIGRATION" >/dev/null
      say "  [DONE] committed ANCHOR.md files"
    fi
  fi

  if [ -n "$features" ]; then
    local f
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      seed_cycle_for_feature "$f"
    done <<<"$features"
  fi
  say ""

  say "=== migration complete ==="
  if dry; then
    say "No changes were made. Re-run without --dry-run to apply."
  else
    say "Installed ANCHOR.md, seed commits, and post-commit hook."
    say "Next: fill in §1-§3 of each ANCHOR.md within 24h."
  fi
}

main "$@"
