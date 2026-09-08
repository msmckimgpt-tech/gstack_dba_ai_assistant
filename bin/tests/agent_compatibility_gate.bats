#!/usr/bin/env bats
# Exercise the actual completion gate against staged git changes and synthetic
# review records. No function extraction, source-text assertions or skip flags.

setup() {
  FIXTURE="$BATS_TEST_TMPDIR/compatibility"
  mkdir -p "$FIXTURE/repo/bin" "$FIXTURE/repo/unit/feature-0001-demo/docs"
  mkdir -p "$FIXTURE/repo/unit/feature-0001-demo/src" "$FIXTURE/repo/.codex/skills/example"
  cp "$BATS_TEST_DIRNAME/../verify-completion.sh" "$FIXTURE/repo/bin/"
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
  local artifact="meta/reviews/qa-fixture.md"
  mkdir -p meta/reviews
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
  cat >> meta/REVIEW.md <<'EOF'

## REV-20260908T000000-gate-fixture [SUBAGENT:qa-reviewer] — PASS

- Trigger: synthetic compatibility metadata integration fixture
- Artifact: [fixture](reviews/qa-fixture.md)
EOF
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

@test "AGENTS.override.md passes the complete META gate with a review record" {
  stage_compatibility_path override
  stage_accepted_review
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  assert_meta_pass
}

@test ".agents/ENVIRONMENT.md passes the complete META gate with a review record" {
  stage_compatibility_path environment
  stage_accepted_review
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  assert_meta_pass
}

@test "template upgrade state passes META verification and retains mandatory review" {
  printf 'template_version=v3.54.1\n' > .template-state
  git add .template-state
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  [ "$status" -eq 1 ]
  [[ "$output" == *"META mode: pure-meta changeset detected"* ]]
  [[ "$output" == *"CHECK#9 FAIL"* ]]
  stage_accepted_review
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  assert_meta_pass
}

@test ".aiignore read-scope policy is META and still requires review evidence" {
  printf 'docs/old-notes.md\n' > .aiignore
  git add .aiignore
  run bash bin/verify-completion.sh --pre-commit META-9001-compatibility
  [ "$status" -eq 1 ]
  [[ "$output" == *"META mode: pure-meta changeset detected"* ]]
  [[ "$output" == *"CHECK#9 FAIL"* ]]
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

stage_ui_cycle() {
  printf 'visual_verification_scope: always\n' > "$FIXTURE/FIRST_REQUEST.md"
  mkdir -p unit/feature-0001-demo/src/static unit/feature-0001-demo/docs/test-runs.d
  printf 'const changed = true;\n' > unit/feature-0001-demo/src/static/app.js
  printf '\n- [x] UI fixture\n' >> unit/feature-0001-demo/docs/TASK.md
  printf '\n## CHG-20260908T000000-ui-fixture\nSynthetic change.\n' >> unit/feature-0001-demo/docs/MODIFY.md
  printf '\nUI fixture specification.\n' >> unit/feature-0001-demo/docs/FUNCTION.md
  stage_accepted_review
  git add unit
}

@test "CHECK13 accepts current DQA-client PASS evidence in a fragment" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nResult: PASS\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 0 ]
  [[ "$output" == *'CHECK#13 PASS visual verification'* ]]
  [[ "$output" == *'Environment: DQA-client'* ]]
}

@test "CHECK13 preserves legacy TEST.md browser evidence as an alternative warning" {
  stage_ui_cycle
  printf 'Environment: Windows-browser\nResult: PASS\n' > unit/feature-0001-demo/docs/TEST.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 0 ]
  [[ "$output" == *'CHECK#13 WARN visual verification'* ]]
  [[ "$output" != *'CHECK#13 PASS visual verification'* ]]
  [[ "$output" == *'대체 증거'* ]]
}

@test "CHECK13 reports DQA-client NOT-RUN with a reason as unverified" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nResult: NOT-RUN\nReason: client unavailable in fixture\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 0 ]
  [[ "$output" == *'CHECK#13 WARN visual verification'* ]]
  [[ "$output" != *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 does not accept a DQA-client environment without a result" {
  stage_ui_cycle
  printf 'Environment: DQA-client\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'CHECK#13 FAIL visual verification'* ]]
}

@test "CHECK13 does not borrow a PASS verdict from a different fragment" {
  stage_ui_cycle
  printf 'Environment: DQA-client\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  printf 'Result: PASS\n' > unit/feature-0001-demo/docs/test-runs.d/other.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'CHECK#13 FAIL visual verification'* ]]
}

@test "CHECK13 cannot relabel a browser PASS in the same TEST.md as DQA-client PASS" {
  stage_ui_cycle
  printf 'Environment: DQA-client\n\nEnvironment: Windows-browser\nResult: PASS\n' > unit/feature-0001-demo/docs/TEST.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [[ "$output" == *'CHECK#13 WARN visual verification'* ]]
  [[ "$output" != *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 explicit DQA-client failure cannot be hidden by a browser PASS" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nResult: FAIL\n\nEnvironment: Windows-browser\nResult: PASS\n' > unit/feature-0001-demo/docs/TEST.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'DQA-client 실행 FAIL 기록'* ]]
  [[ "$output" != *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 explicit failure takes priority over blocked environment notes" {
  stage_ui_cycle
  printf 'Environment: DQA-client (blocked)\nResult: FAIL\nReason: connecting failed\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'DQA-client 실행 FAIL 기록'* ]]
}

@test "CHECK13 one DQA scenario PASS cannot hide another DQA scenario FAIL" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nScenario: opening modal\nResult: PASS\n\nEnvironment: DQA-client\nScenario: connecting\nResult: FAIL\n' > unit/feature-0001-demo/docs/TEST.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'DQA-client 실행 FAIL 기록'* ]]
}

@test "CHECK13 a passing fragment cannot hide a failing DQA fragment" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nResult: PASS\n' > unit/feature-0001-demo/docs/test-runs.d/a-pass.md
  printf 'Environment: DQA-client\nResult: FAIL\n' > unit/feature-0001-demo/docs/test-runs.d/z-fail.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'DQA-client 실행 FAIL 기록'* ]]
}

@test "CHECK13 a successful rerun of the same named scenario resolves its earlier failure" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nScenario: connecting\nResult: FAIL\n\nEnvironment: DQA-client\nScenario: connecting\nResult: PASS\nEvidence: connection result returned after fixing the handler\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 0 ]
  [[ "$output" == *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 a different scenario PASS cannot resolve an earlier failure" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nScenario: connecting\nResult: FAIL\n\nEnvironment: DQA-client\nScenario: opening modal\nResult: PASS\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'DQA-client 실행 FAIL 기록'* ]]
}

@test "CHECK13 a later failure of the same scenario replaces its earlier PASS" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nScenario: connecting\nResult: PASS\n\nEnvironment: DQA-client\nScenario: connecting\nResult: FAIL\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'DQA-client 실행 FAIL 기록'* ]]
}

@test "CHECK13 an unrun DQA scenario remains visible beside a passing scenario" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nResult: PASS\n\nEnvironment: DQA-client\nResult: NOT-RUN\nReason: secondary action unavailable\n' > unit/feature-0001-demo/docs/TEST.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 0 ]
  [[ "$output" == *'CHECK#13 WARN visual verification'* ]]
  [[ "$output" != *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 legacy browser label without a result is not a client PASS" {
  stage_ui_cycle
  printf 'Environment: Windows-browser\n' > unit/feature-0001-demo/docs/TEST.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [[ "$output" == *'CHECK#13 WARN visual verification'* ]]
  [[ "$output" != *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 recognizes a single-environment fragment frontmatter verdict" {
  stage_ui_cycle
  printf '%s\n' '---' 'verdict: PASS' '---' '# UI run' '- **Environment**: **DQA-client**' > unit/feature-0001-demo/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 0 ]
  [[ "$output" == *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 requires a newly added run and rejects unchanged historical DQA evidence" {
  printf 'Environment: DQA-client\nResult: PASS\n' > unit/feature-0001-demo/docs/TEST.md
  git add unit
  git commit -qm 'historical fixture run'
  stage_ui_cycle
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'CHECK#13 FAIL visual verification'* ]]
}

@test "CHECK13 native window changes require evidence attributed to the native feature" {
  stage_ui_cycle
  printf 'Environment: DQA-client\nResult: PASS\n' > unit/feature-0001-demo/docs/test-runs.d/current.md
  mkdir -p unit/feature-0046-native-client/src/client
  printf '# native window change\n' > unit/feature-0046-native-client/src/client/window.py
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 1 ]
  [[ "$output" == *'CHECK#13 FAIL visual verification'* ]]
  [[ "$output" == *'unit/feature-0046-native-client/docs/TEST.md'* ]]
  mkdir -p unit/feature-0046-native-client/docs/test-runs.d
  printf 'Environment: DQA-client\nResult: PASS\n' > unit/feature-0046-native-client/docs/test-runs.d/current.md
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [ "$status" -eq 0 ]
  [[ "$output" == *'CHECK#13 PASS visual verification'* ]]
}

@test "CHECK13 native core and test-only changes do not require UI evidence" {
  mkdir -p unit/feature-0046-native-client/src/client unit/feature-0046-native-client/tests
  printf '# core fixture\n' > unit/feature-0046-native-client/src/client/core.py
  printf '# test fixture\n' > unit/feature-0046-native-client/tests/test_window.py
  git add unit
  run bash bin/verify-completion.sh --pre-commit feature-0001-demo
  [[ "$output" == *'CHECK#13 PASS visual verification :: (no web/UI asset change'* ]]
}

@test "CHECK13 covers each existing native window tray and panel surface" {
  printf 'visual_verification_scope: always\n' > "$FIXTURE/FIRST_REQUEST.md"
  mkdir -p unit/feature-0046-native-client/src/client
  for ui_file in window.py appwindow.py gui.py tray.py bridge.py; do
    path="unit/feature-0046-native-client/src/client/$ui_file"
    printf '# native UI fixture\n' > "$path"
    git add "$path"
    run bash bin/verify-completion.sh --pre-commit feature-0001-demo
    [[ "$output" == *'CHECK#13 FAIL visual verification'* ]]
    [[ "$output" == *'unit/feature-0046-native-client/docs/TEST.md'* ]]
    git reset -q HEAD -- "$path"
  done
}
