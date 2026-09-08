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

finalize_cycle() {
  (cd "$WT" && bash "$FIXTURE/bin/cycle-finalize.sh" --pr 7 "$@")
}

finalize_kept() {
  finalize_cycle --keep-worktree --keep-branch "$@"
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
  [[ "$output" == *'본 세션에서 생성한 worktree 를 작업 경로로 사용해 위임된 작업을 계속합니다.'* ]]
  [[ "$output" != *'새 Claude Code 세션을 worktree path 에서 시작하세요'* ]]
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

@test "cycle-finalize keep-worktree preserves local and remote branches without deletion attempts" {
  make_worktree
  export GH_FIXTURE_STATE=MERGED
  GIT_TRACE="$FIXTURE/git.trace" run finalize_cycle --keep-worktree
  [ "$status" -eq 0 ]
  [ -d "$WT" ]
  [ "$(git rev-parse "refs/heads/$GH_FIXTURE_HEAD")" = "$MAIN_INITIAL" ]
  [ "$(git --git-dir="$GH_FIXTURE_ORIGIN" rev-parse "refs/heads/$GH_FIXTURE_HEAD")" = "$MAIN_INITIAL" ]
  [[ "$output" == *"local branch:       kept (--keep-worktree): $GH_FIXTURE_HEAD"* ]]
  [[ "$output" == *"remote branch:      skipped (--keep-worktree): $GH_FIXTURE_HEAD"* ]]
  run grep -E 'worktree remove|branch -[dD]|push origin --delete' "$FIXTURE/git.trace"
  [ "$status" -eq 1 ]
}

@test "cycle-finalize keep-branch removes the worktree but retains both branches" {
  make_worktree
  export GH_FIXTURE_STATE=MERGED
  GIT_TRACE="$FIXTURE/git.trace" run finalize_cycle --keep-branch
  [ "$status" -eq 0 ]
  [ ! -d "$WT" ]
  git show-ref --verify --quiet "refs/heads/$GH_FIXTURE_HEAD"
  git --git-dir="$GH_FIXTURE_ORIGIN" show-ref --verify --quiet "refs/heads/$GH_FIXTURE_HEAD"
  [[ "$output" == *"worktree cleanup:   removed: $WT"* ]]
  [[ "$output" == *"local branch:       kept (--keep-branch): $GH_FIXTURE_HEAD"* ]]
  run grep -E 'branch -[dD]|push origin --delete' "$FIXTURE/git.trace"
  [ "$status" -eq 1 ]
}

@test "cycle-finalize default cleanup reports actual worktree and branch deletions" {
  make_worktree
  export GH_FIXTURE_STATE=MERGED
  run finalize_cycle
  [ "$status" -eq 0 ]
  [ ! -d "$WT" ]
  [[ "$output" == *"worktree cleanup:   removed: $WT"* ]]
  [[ "$output" == *"local branch:       deleted: $GH_FIXTURE_HEAD"* ]]
  [[ "$output" == *"remote branch:      deleted: $GH_FIXTURE_HEAD"* ]]
  run git show-ref --verify --quiet "refs/heads/$GH_FIXTURE_HEAD"
  [ "$status" -eq 1 ]
  run git --git-dir="$GH_FIXTURE_ORIGIN" show-ref --verify --quiet "refs/heads/$GH_FIXTURE_HEAD"
  [ "$status" -eq 1 ]
}

@test "cycle-finalize failed local branch deletion is reported as retained" {
  make_worktree
  git -C "$WT" commit -qm unmerged-local-commit --allow-empty
  export GH_FIXTURE_STATE=MERGED
  run finalize_cycle
  [ "$status" -eq 0 ]
  [ ! -d "$WT" ]
  git show-ref --verify --quiet "refs/heads/$GH_FIXTURE_HEAD"
  [[ "$output" == *"local branch:       retained (delete failed): $GH_FIXTURE_HEAD"* ]]
  [[ "$output" != *"local branch:       deleted:"* ]]
}

@test "cycle-finalize dry-run reports intended cleanup without claiming deletion" {
  make_worktree
  export GH_FIXTURE_STATE=MERGED
  run finalize_cycle --dry-run
  [ "$status" -eq 0 ]
  [ -d "$WT" ]
  git show-ref --verify --quiet "refs/heads/$GH_FIXTURE_HEAD"
  git --git-dir="$GH_FIXTURE_ORIGIN" show-ref --verify --quiet "refs/heads/$GH_FIXTURE_HEAD"
  [[ "$output" == *"worktree cleanup:   dry-run: would remove $WT"* ]]
  [[ "$output" == *"local branch:       dry-run: would delete $GH_FIXTURE_HEAD"* ]]
  [[ "$output" == *"remote branch:      dry-run: would delete $GH_FIXTURE_HEAD"* ]]
}

prepare_real_board_cycle() {
  unset CODEX_THREAD_ID CLAUDE_CODE_SESSION_ID AGENT_BOARD_SID AGENT_BOARD_TOKEN AGENT_BOARD_DISABLE BOARD_LIB BOARD_FS
  export XDG_STATE_HOME="$FIXTURE/xdg"
  mkdir -p "$REPO/bin/lib"
  cp "$FIXTURE/bin/cycle-finalize.sh" "$BATS_TEST_DIRNAME/../board.sh" "$REPO/bin/"
  cp "$FIXTURE/bin/lib/privilege.sh" "$BATS_TEST_DIRNAME/../lib/board_core.sh" "$BATS_TEST_DIRNAME/../lib/board_fs.py" "$REPO/bin/lib/"
  printf '# Isolated board fixture\n' > "$REPO/AGENTS.md"
  git add bin AGENTS.md
  git commit -qm 'tracked scripts executed from the removable worktree'
  git push -q origin main
  bash "$REPO/bin/board.sh" init --mode private >/dev/null
  BOARD_ROOT=$(sed -n 's/^root=//p' "$FIXTURE/.board-root")
  OWN_SID=$(bash "$REPO/bin/board.sh" register --platform codex --native-id finalize-self)
  PEER_SID=$(bash "$REPO/bin/board.sh" register --platform claude --native-id finalize-peer)
  make_worktree
  export GH_FIXTURE_STATE=MERGED
}

@test "cycle-finalize executed from the deleted worktree marks only its native session done" {
  prepare_real_board_cycle
  export CODEX_THREAD_ID=finalize-self CLAUDE_CODE_SESSION_ID=finalize-peer AGENT_BOARD_SID="$PEER_SID"
  export AGENT_BOARD_TOKEN="$(cat "$BOARD_ROOT/sessions/$PEER_SID.token")"
  peer_before=$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")
  run bash -c 'cd "$1" && bash bin/cycle-finalize.sh --pr 7' -- "$WT"
  [ "$status" -eq 0 ]
  [ ! -d "$WT" ]
  grep -q '"state":"done"' "$BOARD_ROOT/sessions/$OWN_SID.json"
  [ "$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")" = "$peer_before" ]
}

@test "cycle-finalize already-done native session is idempotent after authentication" {
  prepare_real_board_cycle
  export CODEX_THREAD_ID=finalize-self
  bash "$REPO/bin/board.sh" done --sid "$OWN_SID"
  peer_before=$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")
  run bash -c 'cd "$1" && bash bin/cycle-finalize.sh --pr 7' -- "$WT"
  [ "$status" -eq 0 ]
  [ ! -d "$WT" ]
  grep -q '"state":"done"' "$BOARD_ROOT/sessions/$OWN_SID.json"
  [ "$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")" = "$peer_before" ]
  [[ "$output" == *'agent-board 이미 완료'* ]]
  [[ "$output" != *'agent-board done 실패'* ]]
}

@test "cycle-finalize other board error on done session is not reported as already complete" {
  prepare_real_board_cycle
  export CODEX_THREAD_ID=finalize-self
  bash "$REPO/bin/board.sh" done --sid "$OWN_SID"
  cp "$REPO/bin/board.sh" "$REPO/bin/board-real.sh"
  cat > "$REPO/bin/board.sh" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = done ]; then
  printf 'board: token-mismatch fixture-diagnostic\n' >&2
  exit 3
fi
exec bash "$(dirname "$0")/board-real.sh" "$@"
EOF
  peer_before=$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")
  run bash -c 'cd "$1" && bash bin/cycle-finalize.sh --pr 7' -- "$WT"
  [ "$status" -eq 0 ]
  [ "$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")" = "$peer_before" ]
  [[ "$output" == *'agent-board done 실패'* ]]
  [[ "$output" != *'agent-board 이미 완료'* ]]
  [[ "$output" != *'fixture-diagnostic'* ]]
}

@test "cycle-finalize without native identity cannot borrow an inherited peer board session" {
  prepare_real_board_cycle
  export AGENT_BOARD_SID="$PEER_SID"
  peer_before=$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")
  run bash -c 'cd "$1" && bash bin/cycle-finalize.sh --pr 7' -- "$WT"
  [ "$status" -eq 0 ]
  [ ! -d "$WT" ]
  [ "$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")" = "$peer_before" ]
  shopt -s nullglob
  posts=("$BOARD_ROOT/channels/public/"*.md)
  [ "${#posts[@]}" -eq 0 ]
  [[ "$output" == *'native session id 미확인'* ]]
}

@test "cycle-finalize preserves verified suspended Claude SID token binding without native environment" {
  prepare_real_board_cycle
  export AGENT_BOARD_SID="$PEER_SID" AGENT_BOARD_TOKEN="$(cat "$BOARD_ROOT/sessions/$PEER_SID.token")"
  printf '{"session_id":"finalize-peer","reason":"other"}' | bash "$REPO/bin/board.sh" end --hook --platform claude --stdin-json -
  grep -q '"state":"suspended"' "$BOARD_ROOT/sessions/$PEER_SID.json"
  other_before=$(sha256sum "$BOARD_ROOT/sessions/$OWN_SID.json")
  run bash -c 'cd "$1" && bash bin/cycle-finalize.sh --pr 7' -- "$WT"
  [ "$status" -eq 0 ]
  [ ! -d "$WT" ]
  grep -q '"state":"done"' "$BOARD_ROOT/sessions/$PEER_SID.json"
  [ "$(sha256sum "$BOARD_ROOT/sessions/$OWN_SID.json")" = "$other_before" ]
}

@test "cycle-finalize rejects an incorrect inherited token without changing another session" {
  prepare_real_board_cycle
  export AGENT_BOARD_SID="$PEER_SID" AGENT_BOARD_TOKEN=00000000000000000000000000000000
  peer_before=$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")
  run bash -c 'cd "$1" && bash bin/cycle-finalize.sh --pr 7' -- "$WT"
  [ "$status" -eq 0 ]
  [ "$(sha256sum "$BOARD_ROOT/sessions/$PEER_SID.json")" = "$peer_before" ]
  shopt -s nullglob
  posts=("$BOARD_ROOT/channels/public/"*.md)
  [ "${#posts[@]}" -eq 0 ]
  [[ "$output" == *'검증된 SID/token 바인딩 없음'* ]]
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
