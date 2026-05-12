#!/usr/bin/env bash
#
# codex-template-install.sh — install/check repo-local Codex command surfaces
# for ai_delegated_dev_template consumer projects.
#
# Source of truth stays inside the repository:
#   .codex/commands/_template/*.md
#   .codex/skills/_template-*/SKILL.md
#   .agents/plugins/marketplace.json
#   plugins/ai-delegated-dev-template/
#
# User/global Codex locations are installation targets only.

set -euo pipefail

readonly CODEX_DIR=".codex"
readonly COMMAND_DIR=".codex/commands/_template"
readonly SKILL_DIR=".codex/skills"
readonly PLUGIN_DIR="plugins/ai-delegated-dev-template"
readonly PLUGIN_MANIFEST="plugins/ai-delegated-dev-template/.codex-plugin/plugin.json"
readonly PLUGIN_COMMAND_DIR="plugins/ai-delegated-dev-template/commands"
readonly PLUGIN_SKILL_DIR="plugins/ai-delegated-dev-template/skills"
readonly MARKETPLACE_FILE=".agents/plugins/marketplace.json"
readonly OUTER_LINK_NAME=".codex"
readonly OUTER_LINK_TARGET="repo/.codex"

COMMANDS="entry init observability persona-new test-strategy version-upgrade"

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

say() { printf '%s\n' "$1" >&2; }
info() { printf '%s%s%s\n' "$C_DIM" "$1" "$C_RESET" >&2; }
ok() { printf '%s%s%s\n' "$C_GREEN" "$1" "$C_RESET" >&2; }
warn() { printf '%s%s%s\n' "$C_YELLOW" "$1" "$C_RESET" >&2; }
fail_line() { printf '%sCHECK FAIL%s: %s\n' "$C_RED" "$C_RESET" "$1" >&2; }
pass_line() { printf '%sCHECK PASS%s: %s\n' "$C_GREEN" "$C_RESET" "$1" >&2; }
info_line() { printf '%sCHECK INFO%s: %s\n' "$C_DIM" "$C_RESET" "$1" >&2; }

die() {
  printf '%sERROR: %s%s\n' "$C_RED" "$1" "$C_RESET" >&2
  exit "${2:-1}"
}

usage() {
  cat >&2 <<'EOF'
Usage:
  bin/codex-template-install.sh --check
  bin/codex-template-install.sh --link
  bin/codex-template-install.sh --install-marketplace
  bin/codex-template-install.sh --install-prompts
  bin/codex-template-install.sh --help

Modes:
  --check                Verify repo-local Codex command/plugin structure.
  --link                 Create <wrapper>/.codex -> repo/.codex when using wrapper/repo layout.
  --install-marketplace  Run `codex plugin marketplace add <repo-root>`.
  --install-prompts      Link compatibility prompts into $CODEX_HOME/prompts.

Compatibility prompt names:
  Exact syntax attempt:  /_template:<name>  -> $CODEX_HOME/prompts/_template:<name>.md
  Fallback alias:        /_template-<name>  -> $CODEX_HOME/prompts/_template-<name>.md

Environment:
  CODEX_HOME  Defaults to ~/.codex.
EOF
  exit 2
}

require_git_repo() {
  local script_dir repo_candidate
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_candidate="$(dirname "$script_dir")"
  if git -C "$repo_candidate" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    cd "$(git -C "$repo_candidate" rev-parse --show-toplevel)"
    return 0
  fi

  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    cd "$(git rev-parse --show-toplevel)"
    return 0
  fi

  die "not inside a git work tree and could not resolve repo root from script path" 2
}

repo_root_abs() {
  pwd -P
}

can_symlink() {
  case "$(uname -s)" in
    Linux*|Darwin*) return 0 ;;
    *) return 1 ;;
  esac
}

check_file() {
  local file="$1"
  local label="${2:-$1}"
  if [ -f "$file" ]; then
    pass_line "$label present"
    return 0
  fi
  fail_line "$label missing: $file"
  return 1
}

check_dir() {
  local dir="$1"
  local label="${2:-$1}"
  if [ -d "$dir" ]; then
    pass_line "$label present"
    return 0
  fi
  fail_line "$label missing: $dir"
  return 1
}

check_json_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -Eq "$pattern" "$file" 2>/dev/null; then
    pass_line "$label"
    return 0
  fi
  fail_line "$label not found in $file"
  return 1
}

check_outer_link() {
  local repo_root parent link_path target
  repo_root=$(repo_root_abs)
  parent=$(dirname "$repo_root")
  link_path="$parent/$OUTER_LINK_NAME"

  if [ "$(basename "$repo_root")" != "repo" ]; then
    info_line "outer Codex link skipped (repo root basename is not 'repo')"
    return 0
  fi

  if [ ! -L "$link_path" ]; then
    if [ -e "$link_path" ]; then
      fail_line "$link_path exists but is not a symlink"
      return 1
    fi
    info_line "outer Codex link absent at $link_path (run --link if Codex starts from wrapper)"
    return 0
  fi

  target=$(readlink "$link_path" 2>/dev/null || true)
  if [ "$target" = "$OUTER_LINK_TARGET" ]; then
    pass_line "outer Codex link present ($link_path -> $target)"
    return 0
  fi

  fail_line "$link_path points to $target (expected $OUTER_LINK_TARGET)"
  return 1
}

mode_check() {
  local fail=0
  check_dir "$CODEX_DIR" "Codex source directory" || fail=1
  check_dir "$COMMAND_DIR" "Codex _template command directory" || fail=1
  check_dir "$SKILL_DIR" "Codex skill directory" || fail=1
  check_dir "$PLUGIN_DIR" "Codex local plugin directory" || fail=1
  check_file "$PLUGIN_MANIFEST" "Codex plugin manifest" || fail=1
  check_file "$MARKETPLACE_FILE" "Codex local marketplace manifest" || fail=1

  local cmd skill_name
  for cmd in $COMMANDS; do
    check_file "$COMMAND_DIR/$cmd.md" "Codex command /_template:$cmd" || fail=1
    skill_name="_template-$cmd"
    check_file "$SKILL_DIR/$skill_name/SKILL.md" "Codex skill $skill_name" || fail=1
    check_file "$PLUGIN_COMMAND_DIR/$cmd.md" "Plugin command $cmd" || fail=1
    check_file "$PLUGIN_SKILL_DIR/$skill_name/SKILL.md" "Plugin skill $skill_name" || fail=1
  done

  if [ -f "$PLUGIN_MANIFEST" ]; then
    check_json_contains "$PLUGIN_MANIFEST" '"name"[[:space:]]*:[[:space:]]*"ai-delegated-dev-template"' "plugin.json name matches plugin folder" || fail=1
    check_json_contains "$PLUGIN_MANIFEST" '"skills"[[:space:]]*:[[:space:]]*"./skills/"' "plugin.json declares skills path" || fail=1
    check_json_contains "$PLUGIN_MANIFEST" '"displayName"[[:space:]]*:[[:space:]]*"AI Delegated Dev Template"' "plugin.json has displayName" || fail=1
  fi

  if [ -f "$MARKETPLACE_FILE" ]; then
    check_json_contains "$MARKETPLACE_FILE" '"path"[[:space:]]*:[[:space:]]*"./plugins/ai-delegated-dev-template"' "marketplace points at repo-local plugin" || fail=1
    check_json_contains "$MARKETPLACE_FILE" '"installation"[[:space:]]*:[[:space:]]*"AVAILABLE"' "marketplace installation policy present" || fail=1
    check_json_contains "$MARKETPLACE_FILE" '"authentication"[[:space:]]*:[[:space:]]*"ON_INSTALL"' "marketplace authentication policy present" || fail=1
  fi

  check_outer_link || fail=1

  if [ "$fail" -eq 0 ]; then
    ok "OK: repo-local Codex template command structure is valid"
    return 0
  fi
  warn "Codex template command structure has failures"
  return 1
}

mode_link() {
  can_symlink || die "this OS does not support the expected symlink flow" 1

  local repo_root parent link_path
  repo_root=$(repo_root_abs)
  parent=$(dirname "$repo_root")
  link_path="$parent/$OUTER_LINK_NAME"

  if [ "$(basename "$repo_root")" != "repo" ]; then
    warn "repo root basename is not 'repo'; creating wrapper link is skipped"
    warn "current repo root: $repo_root"
    return 0
  fi

  if [ ! -d "$CODEX_DIR" ]; then
    die "$CODEX_DIR is missing; run from a template repo that contains Codex command sources" 1
  fi

  if [ -L "$link_path" ]; then
    local target
    target=$(readlink "$link_path" 2>/dev/null || true)
    if [ "$target" = "$OUTER_LINK_TARGET" ]; then
      ok "outer Codex link already exists: $link_path -> $target"
      return 0
    fi
    die "$link_path points to $target; expected $OUTER_LINK_TARGET" 1
  fi

  if [ -e "$link_path" ]; then
    die "$link_path already exists and is not a symlink; inspect it before linking" 1
  fi

  ln -s "$OUTER_LINK_TARGET" "$link_path"
  ok "outer Codex link created: $link_path -> $OUTER_LINK_TARGET"
}

link_prompt_file() {
  local source="$1"
  local dest="$2"

  if [ -L "$dest" ]; then
    local target
    target=$(readlink "$dest" 2>/dev/null || true)
    if [ "$target" = "$source" ]; then
      pass_line "prompt link already present: $dest"
      return 0
    fi
    fail_line "$dest points to $target (expected $source)"
    return 1
  fi

  if [ -e "$dest" ]; then
    fail_line "$dest already exists; refusing to overwrite user prompt"
    return 1
  fi

  ln -s "$source" "$dest"
  pass_line "prompt link created: $dest"
}

mode_install_prompts() {
  can_symlink || die "prompt compatibility install requires symlink support" 1

  local codex_home prompt_dir repo_root fail cmd source exact alias
  codex_home="${CODEX_HOME:-$HOME/.codex}"
  prompt_dir="$codex_home/prompts"
  repo_root=$(repo_root_abs)
  fail=0

  mkdir -p "$prompt_dir"

  for cmd in $COMMANDS; do
    source="$repo_root/$COMMAND_DIR/$cmd.md"
    if [ ! -f "$source" ]; then
      fail_line "source command missing: $source"
      fail=1
      continue
    fi
    exact="$prompt_dir/_template:$cmd.md"
    alias="$prompt_dir/_template-$cmd.md"
    link_prompt_file "$source" "$exact" || fail=1
    link_prompt_file "$source" "$alias" || fail=1
  done

  if [ "$fail" -eq 0 ]; then
    ok "OK: compatibility prompts installed in $prompt_dir"
    info "Restart Codex before expecting newly linked prompts to appear."
    return 0
  fi
  warn "prompt compatibility install had failures"
  return 1
}

mode_install_marketplace() {
  command -v codex >/dev/null 2>&1 || die "codex CLI is not on PATH" 1
  [ -f "$MARKETPLACE_FILE" ] || die "$MARKETPLACE_FILE missing" 1

  local repo_root
  repo_root=$(repo_root_abs)
  info "running: codex plugin marketplace add $repo_root"
  codex plugin marketplace add "$repo_root"
}

main() {
  local mode=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --check|--link|--install-marketplace|--install-prompts)
        if [ -n "$mode" ]; then
          die "choose exactly one mode" 2
        fi
        mode="$1"
        shift
        ;;
      --help|-h|help)
        usage
        ;;
      *)
        die "unknown option: $1" 2
        ;;
    esac
  done

  [ -n "$mode" ] || usage
  require_git_repo

  case "$mode" in
    --check) mode_check ;;
    --link) mode_link ;;
    --install-marketplace) mode_install_marketplace ;;
    --install-prompts) mode_install_prompts ;;
  esac
}

main "$@"
