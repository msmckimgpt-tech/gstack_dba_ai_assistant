#!/usr/bin/env bats
#
# anchor_migrate.bats — tests for bin/anchor-migrate.sh + bin/install-hooks.sh
#
# Covers:
#   - Dry-run mode (no side effects)
#   - ANCHOR.md creation per feature with correct frontmatter
#   - Seed commit creation with Task-Cycle: <feature-id> trailer
#   - Idempotency (re-run is safe)
#   - post-commit hook installation + verification

setup() {
  TESTDIR=$(mktemp -d /tmp/anchor-migrate-test-XXXXXX)
  cd "$TESTDIR"
  git init --quiet --initial-branch=main
  git config user.email "test@example.invalid"
  git config user.name "Test Runner"

  mkdir -p unit/_template/docs
  mkdir -p unit/feature-0001-demo/docs
  mkdir -p unit/feature-0002-beta/docs
  mkdir -p bin

  # Copy scripts under test
  cp "${BATS_TEST_DIRNAME}/../verify-completion.sh" bin/verify-completion.sh
  cp "${BATS_TEST_DIRNAME}/../anchor-migrate.sh" bin/anchor-migrate.sh
  cp "${BATS_TEST_DIRNAME}/../install-hooks.sh" bin/install-hooks.sh
  chmod +x bin/*.sh

  # Skeleton ANCHOR (required by anchor-migrate)
  cat > unit/_template/docs/ANCHOR.md <<'EOF'
---
doc_type: ANCHOR
feature_id: feature-xxxx-template
created_at: YYYY-MM-DDTHH:MM:SSZ
status: active
edit_policy: mixed
---
# ANCHOR: <feature-id> <feature-name>

## §1. 외부 관점 요약
(작성 필요)

## §2. 대안 분기
(작성 필요)

## §3. 가정된 사용 시나리오
(작성 필요)

## §4. 외부 검증 로그 (append-only)
(엔트리 없음)
EOF

  # Initial commit so HEAD exists
  git add . && git commit --quiet -m "test-setup"
}

teardown() {
  cd /
  rm -rf "$TESTDIR"
}

@test "install-hooks: --check on fresh repo reports missing hook" {
  run bash bin/install-hooks.sh --check
  [ "$status" -eq 1 ]
  [[ "$output" =~ "VERIFY_FAIL" ]]
}

@test "install-hooks: install creates + verifies post-commit hook" {
  run bash bin/install-hooks.sh
  [ "$status" -eq 0 ]
  [[ "$output" =~ "VERIFY_PASS" ]]
  [ -x "$(git rev-parse --git-path hooks)/post-commit" ]
}

@test "install-hooks: hook references verify-completion.sh" {
  bash bin/install-hooks.sh >/dev/null 2>&1
  hook="$(git rev-parse --git-path hooks)/post-commit"
  grep -q "verify-completion.sh" "$hook"
}

@test "install-hooks: second install backs up existing hook" {
  bash bin/install-hooks.sh >/dev/null 2>&1
  run bash bin/install-hooks.sh
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Backed up existing hook" ]]
}

@test "anchor-migrate --dry-run: no files created, no commits made" {
  before_commit=$(git rev-parse HEAD)
  run bash bin/anchor-migrate.sh --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" =~ "DRY RUN" ]]
  [[ "$output" =~ "DRY" ]]
  # No ANCHOR.md created
  [ ! -f unit/feature-0001-demo/docs/ANCHOR.md ]
  # HEAD unchanged
  after_commit=$(git rev-parse HEAD)
  [ "$before_commit" = "$after_commit" ]
}

@test "anchor-migrate: creates ANCHOR.md per feature with correct frontmatter" {
  run bash bin/anchor-migrate.sh
  [ "$status" -eq 0 ]
  [ -f unit/feature-0001-demo/docs/ANCHOR.md ]
  [ -f unit/feature-0002-beta/docs/ANCHOR.md ]
  # Frontmatter substitutions
  grep -q "feature_id: feature-0001-demo" unit/feature-0001-demo/docs/ANCHOR.md
  grep -q "feature_id: feature-0002-beta" unit/feature-0002-beta/docs/ANCHOR.md
  # created_at replaced with real ISO
  ! grep -q "YYYY-MM-DD" unit/feature-0001-demo/docs/ANCHOR.md
}

@test "anchor-migrate: creates seed commit with Task-Cycle trailer per feature" {
  bash bin/anchor-migrate.sh >/dev/null 2>&1
  # Each feature should have a migration-seed commit with Task-Cycle trailer
  run git log --grep="^Task-Cycle: feature-0001-demo$" --format=%H
  [ -n "$output" ]
  run git log --grep="^Task-Cycle: feature-0002-beta$" --format=%H
  [ -n "$output" ]
}

@test "anchor-migrate: installs post-commit hook" {
  bash bin/anchor-migrate.sh >/dev/null 2>&1
  [ -x "$(git rev-parse --git-path hooks)/post-commit" ]
}

@test "anchor-migrate: idempotent (second run creates no duplicate seeds)" {
  bash bin/anchor-migrate.sh >/dev/null 2>&1
  seeds_first=$(git log --grep="migration-seed" --format=%H | wc -l | tr -d ' ')
  bash bin/anchor-migrate.sh >/dev/null 2>&1
  seeds_second=$(git log --grep="migration-seed" --format=%H | wc -l | tr -d ' ')
  [ "$seeds_first" = "$seeds_second" ]
}

@test "anchor-migrate: idempotent (second run does not overwrite existing ANCHOR.md)" {
  bash bin/anchor-migrate.sh >/dev/null 2>&1
  # Mark the file so we can detect overwrite
  echo "# user-added line" >> unit/feature-0001-demo/docs/ANCHOR.md
  bash bin/anchor-migrate.sh >/dev/null 2>&1
  grep -q "# user-added line" unit/feature-0001-demo/docs/ANCHOR.md
}

@test "post-commit hook: silently skips non-feature-id Task-Cycle values (MIGRATION, etc)" {
  bash bin/install-hooks.sh >/dev/null 2>&1
  hook="$(git rev-parse --git-path hooks)/post-commit"
  [ -x "$hook" ]

  # Create a commit with Task-Cycle: MIGRATION trailer — hook should skip silently
  echo "dummy" > dummy.txt
  git add dummy.txt
  run git commit -m "chore: bulk migration bundle

Task-Cycle: MIGRATION"
  [ "$status" -eq 0 ]
  # Output must NOT contain verify failure
  [[ ! "$output" =~ "POST-COMMIT VERIFY FAILED" ]]
  [[ ! "$output" =~ "invalid feature-id" ]]
}

@test "post-commit hook: silently skips bare TASK-ID without feature context" {
  bash bin/install-hooks.sh >/dev/null 2>&1
  echo "dummy" > dummy2.txt
  git add dummy2.txt
  run git commit -m "chore: task without feature scope

Task-Cycle: TASK-0042"
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "POST-COMMIT VERIFY FAILED" ]]
}
