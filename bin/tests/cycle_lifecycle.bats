#!/usr/bin/env bats
# Real isolated Git repositories; GitHub is stubbed and no project board runs.

setup() {
  FIXTURE="$BATS_TEST_TMPDIR/cycle"
  REPO="$FIXTURE/repo"
  mkdir -p "$REPO" "$FIXTURE/bin/lib" "$FIXTURE/stubs"
  cp "$BATS_TEST_DIRNAME/../cycle-init.sh" "$BATS_TEST_DIRNAME/../cycle-finalize.sh" "$FIXTURE/bin/"
  cp "$BATS_TEST_DIRNAME/../lib/privilege.sh" "$FIXTURE/bin/lib/"
  cd "$REPO"
  git init -q --initial-branch=main
  git config user.name 'Cycle fixture'
  git config user.email 'test@example.invalid'
  printf 'main\n' > baseline
  git add baseline
  git commit -qm initial
  MAIN_INITIAL=$(git rev-parse HEAD)
  git init -q --bare "$FIXTURE/origin.git"
  git remote add origin "$FIXTURE/origin.git"
  git push -qu origin main
  export GH_LOG="$FIXTURE/gh.log"
  export GH_FIXTURE_HEAD='ai/test/feature-9001-cycle'
  export GH_FIXTURE_STATE=OPEN GH_FIXTURE_MSS=CLEAN
  export GH_FIXTURE_COMMON="$REPO/.git"
  export GH_FIXTURE_ORIGIN="$FIXTURE/origin.git" GH_FIXTURE_UPDATE=apply
  : > "$GH_LOG"
  cat > "$FIXTURE/stubs/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$GH_LOG"
case "$1 $2" in
  'pr view')
    if [[ "$*" == *'--jq .state'* ]]; then
      printf '%s\n' "$GH_FIXTURE_STATE"
    elif [[ "$*" == *'--jq '* ]]; then
      head=$(git --git-dir="$GH_FIXTURE_ORIGIN" rev-parse "refs/heads/$GH_FIXTURE_HEAD")
      printf '%s:%s:%s\n' "$GH_FIXTURE_STATE" "$GH_FIXTURE_MSS" "$head"
    else
      printf '{"state":"%s","mergeable":"MERGEABLE","mergeStateStatus":"%s","headRefName":"%s","title":"fixture"}\n' \
        "$GH_FIXTURE_STATE" "$GH_FIXTURE_MSS" "$GH_FIXTURE_HEAD"
    fi ;;
  'pr merge')
    # A separate descriptor cannot acquire the parent's merge lock.
    if flock -n "$GH_FIXTURE_COMMON/.merge.lock" true; then
      printf 'merge-without-lock\n' >> "$GH_LOG"
    fi ;;
  'pr update-branch')
    [ "$GH_FIXTURE_UPDATE" != fail ] || exit 1
    printf 'updated\n' >> "$GH_LOG"
    if [ "$GH_FIXTURE_UPDATE" = apply ]; then
      base=$(git --git-dir="$GH_FIXTURE_ORIGIN" rev-parse refs/heads/main)
      git --git-dir="$GH_FIXTURE_ORIGIN" update-ref "refs/heads/$GH_FIXTURE_HEAD" "$base"
    fi ;;
  *) exit 2 ;;
esac
EOF
  chmod +x "$FIXTURE/stubs/gh"
  export PATH="$FIXTURE/stubs:$PATH"
}

make_worktree() {
  WT="$FIXTURE/.worktrees/feature-9001-cycle"
  git worktree add -q -b "$GH_FIXTURE_HEAD" "$WT"
  git push -q origin "$GH_FIXTURE_HEAD"
}

finalize_kept() {
  (cd "$WT" && bash "$FIXTURE/bin/cycle-finalize.sh" --pr 7 --keep-worktree --keep-branch "$@")
}

@test "cycle-init topic base starts the worktree without advancing main to topic" {
  git checkout -qb topic
  printf 'topic\n' > topic
  git add topic
  git commit -qm topic
  topic_head=$(git rev-parse HEAD)
  git push -q origin topic
  git checkout -q main
  run bash "$FIXTURE/bin/cycle-init.sh" --feature feature-9001-cycle --agent test --base topic
  [ "$status" -eq 0 ]
  [ "$(git rev-parse main)" = "$MAIN_INITIAL" ]
  [ "$(git -C "$FIXTURE/.worktrees/feature-9001-cycle" rev-parse HEAD)" = "$topic_head" ]
}

@test "cycle-init resolves a remote-only base without checking it out in main" {
  git checkout -qb topic
  git commit -qm topic --allow-empty
  topic_head=$(git rev-parse HEAD)
  git push -q origin topic
  git checkout -q main
  git branch -D topic
  run bash "$FIXTURE/bin/cycle-init.sh" --feature feature-9001-cycle --agent test --base topic
  [ "$status" -eq 0 ]
  [ "$(git rev-parse main)" = "$MAIN_INITIAL" ]
  [ "$(git -C "$FIXTURE/.worktrees/feature-9001-cycle" rev-parse HEAD)" = "$topic_head" ]
}

@test "cycle-init preserves explicitly selected unpushed local base commits" {
  git checkout -qb topic
  git push -q origin topic
  git commit -qm local-topic --allow-empty
  topic_head=$(git rev-parse HEAD)
  git checkout -q main
  run bash "$FIXTURE/bin/cycle-init.sh" --feature feature-9001-cycle --agent test --base topic
  [ "$status" -eq 0 ]
  [ "$(git rev-parse main)" = "$MAIN_INITIAL" ]
  [ "$(git -C "$FIXTURE/.worktrees/feature-9001-cycle" rev-parse HEAD)" = "$topic_head" ]
}

@test "cycle-finalize merges CLEAN under a shared lock and releases it" {
  make_worktree
  run finalize_kept
  [ "$status" -eq 0 ]
  grep -q "^pr merge 7 --merge --match-head-commit $MAIN_INITIAL$" "$GH_LOG"
  run grep -q '^merge-without-lock$' "$GH_LOG"
  [ "$status" -eq 1 ]
  flock -n "$REPO/.git/.merge.lock" true
}

@test "cycle-finalize refuses BLOCKED despite textual MERGEABLE" {
  make_worktree
  export GH_FIXTURE_MSS=BLOCKED
  run finalize_kept
  [ "$status" -eq 1 ]
  [[ "$output" == *'mergeStateStatus=BLOCKED'* ]]
  run grep -q '^pr merge ' "$GH_LOG"
  [ "$status" -eq 1 ]
  flock -n "$REPO/.git/.merge.lock" true
}

@test "cycle-finalize refreshes a sufficiently behind branch before CLEAN merge" {
  make_worktree
  git commit -qm advance-main --allow-empty
  git push -q origin main
  MERGE_BEHIND_GATE=1 run finalize_kept
  [ "$status" -eq 0 ]
  grep -q '^pr update-branch 7$' "$GH_LOG"
  [ "$(grep -n '^pr update-branch ' "$GH_LOG" | cut -d: -f1)" -lt "$(grep -n '^pr merge ' "$GH_LOG" | cut -d: -f1)" ]
}

@test "cycle-finalize failed update and REST fallback cannot merge stale CLEAN head" {
  make_worktree
  git commit -qm advance-main --allow-empty
  git push -q origin main
  export GH_FIXTURE_UPDATE=fail
  MERGE_BEHIND_GATE=1 run finalize_kept
  [ "$status" -eq 1 ]
  [[ "$output" == *'update-branch 실패'* ]]
  grep -q '^api --method PUT ' "$GH_LOG"
  run grep -q '^pr merge ' "$GH_LOG"
  [ "$status" -eq 1 ]
}

@test "cycle-finalize successful update response without changed head cannot merge" {
  make_worktree
  git commit -qm advance-main --allow-empty
  git push -q origin main
  export GH_FIXTURE_UPDATE=noop
  MERGE_BEHIND_GATE=1 MERGE_CLEAN_TIMEOUT_SEC=0 run finalize_kept
  [ "$status" -eq 1 ]
  [[ "$output" == *'base가 PR head에 아직 없음'* ]]
  run grep -q '^pr merge ' "$GH_LOG"
  [ "$status" -eq 1 ]
}

@test "cycle-finalize bounded lock contention never reaches GitHub merge" {
  make_worktree
  exec 8> "$REPO/.git/.merge.lock"
  flock -n 8
  MERGE_LOCK_TIMEOUT_SEC=0 run finalize_kept
  [ "$status" -eq 1 ]
  [[ "$output" == *'merge mutex 획득 실패'* ]]
  run grep -q '^pr merge ' "$GH_LOG"
  [ "$status" -eq 1 ]
  flock -u 8
  exec 8>&-
}

@test "cycle-finalize already merged PR skips another merge" {
  make_worktree
  export GH_FIXTURE_STATE=MERGED
  run finalize_kept
  [ "$status" -eq 0 ]
  run grep -q '^pr merge ' "$GH_LOG"
  [ "$status" -eq 1 ]
}

make_registry() {
  mkdir -p "$FIXTURE/worktrees"
  REGISTRY="$FIXTURE/worktrees/REGISTRY.md"
  cat > "$REGISTRY" <<EOF
## Active
### $GH_FIXTURE_HEAD
- worktree: $WT

### ai/peer/other
- worktree: preserved-peer

## Closed
### ai/peer/older
- worktree: preserved-history
EOF
  chmod 640 "$REGISTRY"
}

@test "cycle-finalize closes only its registry entry and preserves inode mode and history" {
  make_worktree
  make_registry
  before_inode=$(stat -c %i "$REGISTRY")
  export GH_FIXTURE_STATE=MERGED
  run finalize_kept
  [ "$status" -eq 0 ]
  [[ "$output" == *'automatic entry close completed'* ]]
  [ "$(stat -c %i "$REGISTRY")" = "$before_inode" ]
  [ "$(stat -c %a "$REGISTRY")" = 640 ]
  active=$(awk '/^## Active$/{a=1;next} /^## Closed$/{a=0} a' "$REGISTRY")
  [[ "$active" != *"### $GH_FIXTURE_HEAD"* ]]
  [[ "$active" == *'### ai/peer/other'* ]]
  grep -q '^### ai/peer/older$' "$REGISTRY"
  grep -q '^- worktree: preserved-peer$' "$REGISTRY"
  [ "$(grep -c '^- closed_at:' "$REGISTRY")" -eq 1 ]
  before_second=$(sha256sum "$REGISTRY")
  run finalize_kept
  [ "$status" -eq 0 ]
  [ "$(sha256sum "$REGISTRY")" = "$before_second" ]
}

@test "cycle-finalize dry-run leaves registry content and metadata unchanged" {
  make_worktree
  make_registry
  before=$(sha256sum "$REGISTRY")
  before_stat=$(stat -c '%i:%a:%Y' "$REGISTRY")
  export GH_FIXTURE_STATE=MERGED
  run finalize_kept --dry-run
  [ "$status" -eq 0 ]
  [ "$(sha256sum "$REGISTRY")" = "$before" ]
  [ "$(stat -c '%i:%a:%Y' "$REGISTRY")" = "$before_stat" ]
  [ ! -e "$REGISTRY.lock" ]
}
