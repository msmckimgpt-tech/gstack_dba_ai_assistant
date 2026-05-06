#!/usr/bin/env bash
#
# persona-install.sh — install the Template Persona Skill Pack into a consumer
# repo as a git submodule at .claude/commands/_template.
#
# Design rationale: contract.md §7.1 — default mode is submodule-based
# automatic install (U2 convention). Consumer projects pull personas by
# referencing a single upstream source of truth. Idempotent re-runs are safe.
#
# Usage:
#   bin/persona-install.sh                          # install using $PERSONA_REPO_URL
#   bin/persona-install.sh --source-url <url>       # install with explicit URL
#   bin/persona-install.sh --check                  # verify existing install (no changes)
#   bin/persona-install.sh --help
#
# Exit codes:
#   0 — success (install completed or --check passed)
#   1 — install or verification failure
#   2 — usage error (bad args, not in git repo, missing source URL)
#
# Idempotent: re-running with a URL that matches the already-installed submodule
# is a no-op (prints a notice and exits 0). Passing a conflicting URL is an
# error — unregister the submodule first.
#
# Permissions: this file should be mode 0755 (chmod +x) before use.
#
# Dependencies: bash, git. No jq, no additional runtime deps.

set -euo pipefail

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

readonly SUBMODULE_PATH=".claude/commands/_template"

# -----------------------------------------------------------------------------
# Output helpers (color only if stdout is a tty)
# -----------------------------------------------------------------------------

if [ -t 1 ]; then
  readonly C_RED=$'\033[31m'
  readonly C_GREEN=$'\033[32m'
  readonly C_YELLOW=$'\033[33m'
  readonly C_DIM=$'\033[2m'
  readonly C_RESET=$'\033[0m'
else
  readonly C_RED=""
  readonly C_GREEN=""
  readonly C_YELLOW=""
  readonly C_DIM=""
  readonly C_RESET=""
fi

say()  { printf '%s\n' "$1" >&2; }
info() { printf '%s%s%s\n' "$C_DIM" "$1" "$C_RESET" >&2; }
ok()   { printf '%s%s%s\n' "$C_GREEN" "$1" "$C_RESET" >&2; }
warn() { printf '%s%s%s\n' "$C_YELLOW" "$1" "$C_RESET" >&2; }

die() {
  printf '%sERROR: %s%s\n' "$C_RED" "$1" "$C_RESET" >&2
  if [ -n "${2:-}" ]; then
    printf '%s  recover: %s%s\n' "$C_DIM" "$2" "$C_RESET" >&2
  fi
  exit "${3:-1}"
}

usage() {
  cat >&2 <<'EOF'
Usage:
  bin/persona-install.sh                          # install using $PERSONA_REPO_URL
  bin/persona-install.sh --source-url <url>       # install with explicit URL
  bin/persona-install.sh --check                  # verify existing install
  bin/persona-install.sh --help

Installs the Template Persona Skill Pack as a git submodule at:
  .claude/commands/_template

Environment:
  PERSONA_REPO_URL   default submodule source URL (used when --source-url absent)

Exit codes:
  0 — success
  1 — install or verification failure
  2 — usage error
EOF
  exit 2
}

# -----------------------------------------------------------------------------
# Environment validation
# -----------------------------------------------------------------------------

require_git_repo() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "not inside a git work tree" \
        "cd into your consumer project (the repo/ root) and re-run" 2
  fi
  cd "$(git rev-parse --show-toplevel)"
}

# -----------------------------------------------------------------------------
# .gitmodules inspection (pure bash — no jq)
# -----------------------------------------------------------------------------

# Read the configured url for our submodule path from .gitmodules.
# Prints the URL on stdout, empty string if not registered.
read_submodule_url() {
  if [ ! -f .gitmodules ]; then
    return 0
  fi
  git config -f .gitmodules --get "submodule.${SUBMODULE_PATH}.url" 2>/dev/null || true
}

# -----------------------------------------------------------------------------
# Install flow
# -----------------------------------------------------------------------------

resolve_source_url() {
  local cli_url="$1"
  if [ -n "$cli_url" ]; then
    printf '%s' "$cli_url"
    return 0
  fi
  if [ -n "${PERSONA_REPO_URL:-}" ]; then
    printf '%s' "$PERSONA_REPO_URL"
    return 0
  fi
  die "no submodule source URL provided" \
      "bin/persona-install.sh --source-url <url>   OR   export PERSONA_REPO_URL=<url>" \
      2
}

do_install() {
  local url="$1"

  # Ensure parent dir exists (.claude/commands). Created tracked-empty if needed.
  mkdir -p "$(dirname "$SUBMODULE_PATH")"

  local existing_url
  existing_url=$(read_submodule_url)

  if [ -n "$existing_url" ]; then
    if [ "$existing_url" = "$url" ]; then
      info "submodule already registered at ${SUBMODULE_PATH} with matching URL"
      info "running 'git submodule update --init --recursive' to ensure contents present"
      git submodule update --init --recursive -- "$SUBMODULE_PATH" >/dev/null 2>&1 || \
        die "failed to update submodule ${SUBMODULE_PATH}" \
            "git submodule update --init --recursive -- ${SUBMODULE_PATH}"
    else
      die "submodule at ${SUBMODULE_PATH} is registered with a different URL: ${existing_url}" \
          "git submodule deinit -f ${SUBMODULE_PATH} && git rm -f ${SUBMODULE_PATH} && rm -rf .git/modules/${SUBMODULE_PATH}"
    fi
  else
    # Path must not already exist (git submodule add would refuse)
    if [ -e "$SUBMODULE_PATH" ]; then
      die "${SUBMODULE_PATH} already exists on disk but is not a registered submodule" \
          "rm -rf ${SUBMODULE_PATH} && bin/persona-install.sh --source-url ${url}"
    fi

    info "adding submodule: ${url} -> ${SUBMODULE_PATH}"
    if ! git submodule add "$url" "$SUBMODULE_PATH" >/dev/null 2>&1; then
      die "git submodule add failed for ${url}" \
          "verify the URL is reachable: git ls-remote ${url}"
    fi

    info "initializing and fetching submodule content"
    if ! git submodule update --init --recursive -- "$SUBMODULE_PATH" >/dev/null 2>&1; then
      die "git submodule update --init --recursive failed" \
          "git submodule update --init --recursive -- ${SUBMODULE_PATH}"
    fi
  fi

  # Verify at least one .md file is present in the submodule.
  if ! find "$SUBMODULE_PATH" -maxdepth 3 -type f -name '*.md' 2>/dev/null | head -1 | grep -q .; then
    die "no .md persona files found under ${SUBMODULE_PATH}" \
        "verify the source repo contains persona .md files: git ls-remote ${url}"
  fi

  ok "installed: ${SUBMODULE_PATH} <- ${url}"
  say ""
  say "Available personas:"
  find "$SUBMODULE_PATH" -maxdepth 2 -type f -name '*.md' 2>/dev/null | sort | while IFS= read -r f; do
    printf '  - /%s\n' "$(basename "$f" .md)" >&2
  done
  say ""
  info "next: review ${SUBMODULE_PATH}/ then commit the .gitmodules + gitlink entry"
}

# -----------------------------------------------------------------------------
# Check flow
# -----------------------------------------------------------------------------

do_check() {
  local fail=0

  # 1. Directory exists
  if [ ! -d "$SUBMODULE_PATH" ]; then
    printf '%sCHECK FAIL%s: directory missing: %s\n' "$C_RED" "$C_RESET" "$SUBMODULE_PATH" >&2
    printf '  recover: bin/persona-install.sh --source-url <url>\n' >&2
    fail=1
  else
    printf '%sCHECK PASS%s: directory present at %s\n' "$C_GREEN" "$C_RESET" "$SUBMODULE_PATH" >&2
  fi

  # 2. Registered in .gitmodules
  local url
  url=$(read_submodule_url)
  if [ -z "$url" ]; then
    printf '%sCHECK FAIL%s: not registered in .gitmodules as submodule.%s.url\n' \
      "$C_RED" "$C_RESET" "$SUBMODULE_PATH" >&2
    printf '  recover: bin/persona-install.sh --source-url <url>\n' >&2
    fail=1
  else
    printf '%sCHECK PASS%s: registered in .gitmodules -> %s\n' "$C_GREEN" "$C_RESET" "$url" >&2
  fi

  # 3. Has at least one .md file
  if [ -d "$SUBMODULE_PATH" ]; then
    if find "$SUBMODULE_PATH" -maxdepth 3 -type f -name '*.md' 2>/dev/null | head -1 | grep -q .; then
      local count
      count=$(find "$SUBMODULE_PATH" -maxdepth 3 -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
      printf '%sCHECK PASS%s: %s persona .md file(s) present\n' "$C_GREEN" "$C_RESET" "$count" >&2
    else
      printf '%sCHECK FAIL%s: no .md persona files under %s\n' "$C_RED" "$C_RESET" "$SUBMODULE_PATH" >&2
      printf '  recover: git submodule update --init --recursive -- %s\n' "$SUBMODULE_PATH" >&2
      fail=1
    fi
  fi

  # 4. Submodule not dirty (worktree matches recorded gitlink).
  # Only meaningful if the directory is actually a submodule worktree.
  if [ -d "$SUBMODULE_PATH" ] && [ -n "$url" ]; then
    local status_line
    status_line=$(git submodule status -- "$SUBMODULE_PATH" 2>/dev/null || true)
    if [ -z "$status_line" ]; then
      printf '%sCHECK FAIL%s: git submodule status returned nothing for %s\n' \
        "$C_RED" "$C_RESET" "$SUBMODULE_PATH" >&2
      printf '  recover: git submodule update --init --recursive -- %s\n' "$SUBMODULE_PATH" >&2
      fail=1
    else
      # Leading char of `git submodule status`: ' ' = clean, '+' = different commit,
      # '-' = not initialized, 'U' = merge conflicts.
      local lead
      lead=${status_line:0:1}
      case "$lead" in
        ' ')
          printf '%sCHECK PASS%s: submodule clean (%s)\n' "$C_GREEN" "$C_RESET" \
            "$(printf '%s' "$status_line" | awk '{print $1}')" >&2
          ;;
        '+')
          printf '%sCHECK FAIL%s: submodule commit differs from recorded ref\n' "$C_RED" "$C_RESET" >&2
          printf '  recover: git submodule update --init --recursive -- %s\n' "$SUBMODULE_PATH" >&2
          fail=1
          ;;
        '-')
          printf '%sCHECK FAIL%s: submodule not initialized\n' "$C_RED" "$C_RESET" >&2
          printf '  recover: git submodule update --init --recursive -- %s\n' "$SUBMODULE_PATH" >&2
          fail=1
          ;;
        'U')
          printf '%sCHECK FAIL%s: submodule has merge conflicts\n' "$C_RED" "$C_RESET" >&2
          printf '  recover: resolve conflicts under %s then commit\n' "$SUBMODULE_PATH" >&2
          fail=1
          ;;
        *)
          printf '%sCHECK FAIL%s: unrecognized submodule status: %s\n' "$C_RED" "$C_RESET" "$status_line" >&2
          fail=1
          ;;
      esac
    fi
  fi

  if [ "$fail" -eq 0 ]; then
    ok "OK: persona skill pack installed and clean at ${SUBMODULE_PATH}"
    return 0
  fi
  warn "not installed or broken — see failures above"
  return 1
}

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------

main() {
  local action="install"
  local source_url=""

  while [ $# -gt 0 ]; do
    case "$1" in
      --help|-h)
        usage
        ;;
      --check)
        action="check"
        shift
        ;;
      --source-url)
        if [ $# -lt 2 ]; then
          die "--source-url requires an argument" \
              "bin/persona-install.sh --source-url <url>" 2
        fi
        source_url="$2"
        shift 2
        ;;
      --source-url=*)
        source_url="${1#--source-url=}"
        shift
        ;;
      *)
        die "unknown option: $1" "bin/persona-install.sh --help" 2
        ;;
    esac
  done

  require_git_repo

  case "$action" in
    install)
      local url
      url=$(resolve_source_url "$source_url")
      do_install "$url"
      ;;
    check)
      do_check
      ;;
  esac
}

main "$@"
