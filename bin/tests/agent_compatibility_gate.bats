#!/usr/bin/env bats
# Exercise the actual completion gate against staged git changes and validated
# review artifacts. No function extraction, source-text assertions or skip flags.

setup() {
  FIXTURE="$BATS_TEST_TMPDIR/compatibility"
  mkdir -p "$FIXTURE/repo/bin" "$FIXTURE/repo/unit/feature-0001-demo/docs"
  mkdir -p "$FIXTURE/repo/unit/feature-0001-demo/src" "$FIXTURE/repo/.codex/skills/example"
  cp "$BATS_TEST_DIRNAME/../verify-completion.sh" "$FIXTURE/repo/bin/"
  cp "$BATS_TEST_DIRNAME/../review-md-append-from-subagent-output.sh" "$FIXTURE/repo/bin/"
  cd "$FIXTURE/repo"
  git init --quiet --initial-branch=main
  git config user.email "test@example.invalid"
  git config user.name "Compatibility Gate Fixture"
  mkdir -p meta
  printf '# Meta Review Records\n' > meta/REVIEW.md
  printf 'initialized_at=2026-09-07T00:00:00Z\n' > .template-init-marker
  printf '# Task\n- [ ] Initial implementation\n' > unit/feature-0001-demo/docs/TASK.md
  printf '# Modify\n' > unit/feature-0001-demo/docs/MODIFY.md
  printf '# Function\nInitial feature specification.\n' > unit/feature-0001-demo/docs/FUNCTION.md
  printf 'print("baseline")\n' > unit/feature-0001-demo/src/main.py
  cat > unit/feature-0001-demo/docs/ANCHOR.md <<EOF
---
created_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
---
## §1. External perspective
Bootstrap fixture.
## §2. Alternatives
Bootstrap fixture.
## §3. Usage
Bootstrap fixture.
## §4. Validation
EOF
  printf '%s\n' '---' 'name: example' 'description: Fixture skill.' '---' '# Example' > .codex/skills/example/SKILL.md
  git add .
  git commit --quiet -m 'test: initialize consumer fixture'
  git worktree add --quiet -b ai/codex/compatibility "$FIXTURE/.worktrees/compatibility"
  cd "$FIXTURE/.worktrees/compatibility"
}

stage_accepted_review() {
  local artifact="$BATS_TEST_TMPDIR/qa-fixture.md"
  cat > "$artifact" <<'EOF'
### 1. Blocking issues
(no findings)

### 2. Cross-domain concerns
(no findings)

### 3. Challenge to current spec
This is a synthetic integration-test artifact, not a production review claim.
Compatibility guidance is policy metadata; adding application code must still
trigger operational companion checks, and metadata must still require a review.

### 4. Verdict
PASS — fixture contains no blocking findings; negative controls test gate failure.
EOF
  run bash bin/review-md-append-from-subagent-output.sh _meta_ qa-reviewer "$artifact" \
    --scope project-meta --trigger 'compatibility metadata integration fixture'
  [ "$status" -eq 0 ]
  git add meta
}

stage_compatibility_path() {
  case "$1" in
    override)
      printf '# Agent context\nRead shared environment guidance.\n' > AGENTS.override.md
      git add AGENTS.override.md ;;
    environment)
      mkdir -p .agents
      printf '# Environment\nClaude and Codex share project status.\n' > .agents/ENVIRONMENT.md
      git add .agents/ENVIRONMENT.md ;;
    skills)
      mkdir -p .agents/skills
      ln -s ../../.codex/skills/example .agents/skills/example
      git add .agents/skills/example ;;
  esac
}

assert_meta_pass() {
  [ "$status" -eq 0 ]
  [[ "$output" == *"META mode: pure-meta changeset detected"* ]]
  [[ "$output" == *"CHECK#9 PASS"* ]]
  [[ "$output" == *"CHECK#10 PASS"* ]]
  [[ "$output" == *"CHECK#11 PASS"* ]]
  [[ "$output" == *"verify-completion: PASS"* ]]
}

@test "AGENTS.override.md passes the complete META gate with a validated review" {
  stage_compatibility_path override
  stage_accepted_review
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  assert_meta_pass
}

@test ".agents/ENVIRONMENT.md passes the complete META gate with a validated review" {
  stage_compatibility_path environment
  stage_accepted_review
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  assert_meta_pass
}

@test "the .agents/skills discovery symlink passes the complete META gate" {
  stage_compatibility_path skills
  stage_accepted_review
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  assert_meta_pass
  [ -f .agents/skills/example/SKILL.md ]
}

@test "compatibility metadata still fails when cycle review evidence is absent" {
  stage_compatibility_path environment
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  [ "$status" -eq 1 ]
  [[ "$output" == *"META mode: pure-meta changeset detected"* ]]
  [[ "$output" == *"CHECK#9 FAIL"* ]]
}

@test "compatibility metadata mixed with product code retains operational companion failures" {
  stage_compatibility_path override
  stage_compatibility_path environment
  stage_compatibility_path skills
  stage_accepted_review
  printf 'print("new behavior")\n' > unit/feature-0001-demo/src/main.py
  git add unit/feature-0001-demo/src/main.py
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" != *"META mode: pure-meta changeset detected"* ]]
  [[ "$output" == *"CHECK#2 FAIL"* ]]
  [[ "$output" == *"CHECK#3 FAIL"* ]]
  [[ "$output" == *"CHECK#4 FAIL"* ]]
  [[ "$output" == *"CHECK#9 PASS"* ]]
}

@test "unlisted .agents runtime files are not accidentally exempted as metadata" {
  stage_compatibility_path environment
  stage_accepted_review
  printf 'print("runtime")\n' > .agents/runtime.py
  git add .agents/runtime.py
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" != *"META mode: pure-meta changeset detected"* ]]
  [[ "$output" == *"CHECK#2 FAIL"* ]]
}

@test "compatibility metadata remains subject to the unconditional conflict guard" {
  stage_compatibility_path environment
  stage_accepted_review
  printf '%s\n' '<<<<<<< HEAD' 'unresolved content' '>>>>>>> other' >> .agents/ENVIRONMENT.md
  git add .agents/ENVIRONMENT.md
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  [ "$status" -eq 1 ]
  [[ "$output" == *"META mode: pure-meta changeset detected"* ]]
  [[ "$output" == *"CHECK#9 PASS"* ]]
  [[ "$output" == *"CHECK#14 FAIL"* ]]
}

@test "committed compatibility changes also pass the post-commit META gate" {
  stage_compatibility_path override
  stage_compatibility_path environment
  stage_compatibility_path skills
  stage_accepted_review
  git commit --quiet -m 'test: compatibility metadata with review'
  run bash bin/verify-completion.sh --post-commit META-9001-compatibility
  assert_meta_pass
}
