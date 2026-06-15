#!/usr/bin/env bash
#
# install-hooks.sh — install .git/hooks/post-commit that auto-invokes verify-completion.sh
#
# Critical gap fix (eng review): post-commit hook silent failure. This installer runs
# a verification test after installation to confirm the hook is executable and reachable.
#
# Usage: bin/install-hooks.sh           # install + verify
#        bin/install-hooks.sh --check   # verify existing installation only
#        bin/install-hooks.sh --help
#
# Exit: 0 on success, 1 on install failure, 2 on usage error.

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  bin/install-hooks.sh          # install post-commit hook + verify install
  bin/install-hooks.sh --check  # verify existing installation (no install)
  bin/install-hooks.sh --help
EOF
  exit 2
}

die() { printf 'ERROR: %s\n' "$1" >&2; exit "${2:-1}"; }

require_git_repo() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "not inside a git work tree"
  fi
  cd "$(git rev-parse --show-toplevel)"
}

HOOK_PATH=""

compute_hook_path() {
  local hooks_dir
  hooks_dir=$(git rev-parse --git-path hooks 2>/dev/null)
  [ -n "$hooks_dir" ] || die "could not resolve git hooks directory"
  HOOK_PATH="${hooks_dir}/post-commit"
}

# The post-commit hook body. Embedded here (single source of truth).
# On commit, extracts TASK-ID or META-ID from message and invokes verify-completion.sh.
# NEVER blocks (exit 0) because the commit already happened — just warns loudly.
write_hook() {
  cat > "$HOOK_PATH" <<'HOOK_EOF'
#!/usr/bin/env bash
# post-commit hook — auto-invoke bin/verify-completion.sh after each commit.
# Installed by bin/install-hooks.sh. See AGENTS.md §16.3 and §17.
# NEVER blocks the commit (exit 0 always) — just warns on FAIL so AI sees the output.

set -u

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
verify="${repo_root}/bin/verify-completion.sh"
[ -x "$verify" ] || exit 0

msg=$(git log -1 --format=%s 2>/dev/null)

# Extract a TASK-ID / META-ID / feature-id from the subject line.
# Accepted patterns:
#   - "(TASK-0040)"
#   - "[TASK-0040]"
#   - "Task-Cycle: TASK-0040" in trailers
#   - "feat(feature-0003-name): ..."
feature_id=""
if [[ "$msg" =~ \(feature-([0-9]+|[0-9]{8}T[0-9]{6})-[a-zA-Z0-9-]+\) ]]; then
  feature_id=$(printf '%s' "$msg" | grep -oE 'feature-([0-9]+|[0-9]{8}T[0-9]{6})-[a-zA-Z0-9-]+' | head -1)
elif [[ "$msg" =~ \(META-([0-9]+|[0-9]{8}T[0-9]{6})-[a-zA-Z0-9-]+\) ]]; then
  feature_id=$(printf '%s' "$msg" | grep -oE 'META-([0-9]+|[0-9]{8}T[0-9]{6})-[a-zA-Z0-9-]+' | head -1)
fi

# Fallback: parse Task-Cycle trailer
if [ -z "$feature_id" ]; then
  trailer=$(git log -1 --format=%B 2>/dev/null | grep -m1 '^Task-Cycle:' || true)
  if [ -n "$trailer" ]; then
    feature_id=$(printf '%s' "$trailer" | awk '{print $2}')
  fi
fi

# No feature id extractable → skip verify silently (e.g., migration commits).
[ -n "$feature_id" ] || exit 0

# Validate feature_id matches expected pattern. Unknown values (e.g., MIGRATION,
# Task-ID standalone) mean this commit does not belong to an operational feature
# cycle — skip silently rather than erroring.
if [[ ! "$feature_id" =~ ^(feature|META)-([0-9]+|[0-9]{8}T[0-9]{6})(-[a-zA-Z0-9-]+)?$ ]]; then
  exit 0
fi

# Invoke verify in post-commit mode. Capture stderr.
if ! bash "$verify" --post-commit "$feature_id" >/dev/null 2>/tmp/post-commit-verify.log; then
  printf '\n⚠️  POST-COMMIT VERIFY FAILED for %s\n' "$feature_id"
  printf '   See: /tmp/post-commit-verify.log\n'
  cat /tmp/post-commit-verify.log
  printf '\n   Create a new commit to fix (amend is disallowed — see AGENTS.md §16.3).\n\n'
fi

exit 0
HOOK_EOF
  chmod +x "$HOOK_PATH"
}

verify_install() {
  [ -f "$HOOK_PATH" ] || { printf 'VERIFY_FAIL: hook file missing at %s\n' "$HOOK_PATH" >&2; return 1; }
  [ -x "$HOOK_PATH" ] || { printf 'VERIFY_FAIL: hook not executable\n' >&2; return 1; }
  # Smoke test — run the hook shell parse (no-op if script is fine)
  if ! bash -n "$HOOK_PATH" 2>/dev/null; then
    printf 'VERIFY_FAIL: hook has bash syntax errors\n' >&2
    return 1
  fi
  # Confirm it references verify-completion.sh
  if ! grep -q 'verify-completion.sh' "$HOOK_PATH"; then
    printf 'VERIFY_FAIL: hook does not reference verify-completion.sh\n' >&2
    return 1
  fi
  printf 'VERIFY_PASS: post-commit hook installed at %s\n' "$HOOK_PATH"
  return 0
}

main() {
  local action="install"
  if [ $# -ge 1 ]; then
    case "$1" in
      --help|-h) usage ;;
      --check) action="check" ;;
      *) die "unknown option: $1" 2 ;;
    esac
  fi

  require_git_repo
  compute_hook_path

  case "$action" in
    install)
      if [ -f "$HOOK_PATH" ]; then
        # Backup existing hook (idempotent overwrite with safety net)
        cp "$HOOK_PATH" "${HOOK_PATH}.bak.$(date +%s)"
        printf 'Backed up existing hook to %s.bak.*\n' "$HOOK_PATH"
      fi
      write_hook
      printf 'Wrote post-commit hook: %s\n' "$HOOK_PATH"
      verify_install
      ;;
    check)
      verify_install
      ;;
  esac
}

main "$@"
