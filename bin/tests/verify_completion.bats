#!/usr/bin/env bats
#
# verify_completion.bats — pilot-core test suite for bin/verify-completion.sh
#
# Covers:
#   - Argument parsing (pre-commit/post-commit/shared/help)
#   - META mode auto-detection (pure-meta changeset skip)
#   - Check #2 (TASK.md), #3 (MODIFY.md), #4 (FUNCTION.md), #6 (ANCHOR §1-§3),
#     #7 (§4 quality gate), #8 (unstaged residual)
#   - 24h bootstrap grace
#   - Regression tests for the §16.2 10% enforcement gap
#
# Run:
#   cd repo && bats bin/tests/verify_completion.bats

# -----------------------------------------------------------------------------
# Test fixture setup
# -----------------------------------------------------------------------------

setup() {
  # Isolate: create a fresh bare-like git repo per test.
  TESTDIR=$(mktemp -d /tmp/verify-completion-test-XXXXXX)
  cd "$TESTDIR"
  git init --quiet --initial-branch=main
  git config user.email "test@example.invalid"
  git config user.name "Test Runner"

  # Mirror the template layout we're testing against.
  mkdir -p unit/_template/docs
  mkdir -p unit/feature-0001-demo/docs
  mkdir -p unit/feature-0001-demo/src
  mkdir -p shared/docs
  mkdir -p bin

  # Copy the script-under-test into the fixture repo's bin/.
  cp "${BATS_TEST_DIRNAME}/../verify-completion.sh" bin/verify-completion.sh
  chmod +x bin/verify-completion.sh

  # Minimal ANCHOR skeleton (matches repo's _template structure)
  cat > unit/_template/docs/ANCHOR.md <<'EOF'
---
doc_type: ANCHOR
feature_id: feature-xxxx-template
created_at: YYYY-MM-DDTHH:MM:SSZ
status: active
edit_policy: mixed
source_of_truth: true
---
# ANCHOR: <feature-id>

## §1. 외부 관점 요약
(작성 필요)

## §2. 대안 분기
(작성 필요)

## §3. 가정된 사용 시나리오
(작성 필요)

## §4. 외부 검증 로그 (append-only)
(엔트리 없음)
EOF

  # Minimal initial commit so git log/HEAD queries work.
  git add . && git commit --quiet -m "test-setup: initial fixture"
}

teardown() {
  cd /
  rm -rf "$TESTDIR"
}

# -----------------------------------------------------------------------------
# Fixture builders
# -----------------------------------------------------------------------------

make_feature_docs() {
  local fid="${1:-feature-0001-demo}"
  local age_hours="${2:-0}"  # ANCHOR.md virtual age
  local fdir="unit/$fid"

  # TASK.md with an unchecked checkbox
  cat > "$fdir/docs/TASK.md" <<'EOF'
---
doc_type: TASK
feature_id: feature-0001-demo
status: active
edit_policy: rewrite
---
# Task
- [ ] Initial work
EOF

  # MODIFY.md (append-only)
  cat > "$fdir/docs/MODIFY.md" <<'EOF'
---
doc_type: MODIFY
feature_id: feature-0001-demo
edit_policy: append-only
---
# Modify Log
EOF

  # FUNCTION.md
  cat > "$fdir/docs/FUNCTION.md" <<'EOF'
---
doc_type: FUNCTION
feature_id: feature-0001-demo
edit_policy: rewrite
---
# Function
Initial spec.
EOF

  # ANCHOR.md with a specific created_at
  local created_at
  if [ "$age_hours" = "0" ]; then
    created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  else
    created_at=$(date -u -d "$age_hours hours ago" +%Y-%m-%dT%H:%M:%SZ)
  fi
  cat > "$fdir/docs/ANCHOR.md" <<EOF
---
doc_type: ANCHOR
feature_id: $fid
created_at: $created_at
edit_policy: mixed
---
# ANCHOR: $fid

## §1. 외부 관점 요약
(작성 필요)

## §2. 대안 분기
(작성 필요)

## §3. 가정된 사용 시나리오
(작성 필요)

## §4. 외부 검증 로그 (append-only)
(엔트리 없음)
EOF

  git add "$fdir/"
  git commit --quiet -m "feat($fid): scaffold"
}

# Fill ANCHOR §1-§3 with real content
fill_anchor_1_3() {
  local fid="${1:-feature-0001-demo}"
  local anchor="unit/$fid/docs/ANCHOR.md"
  cat > "$anchor" <<EOF
---
doc_type: ANCHOR
feature_id: $fid
created_at: $(date -u -d "48 hours ago" +%Y-%m-%dT%H:%M:%SZ)
edit_policy: mixed
---
# ANCHOR: $fid

## §1. 외부 관점 요약
This feature exists because ops teams need it. Without it they manually SSH into
boxes to check logs, which is slow and error-prone. External viewers might ask
why we didn't just use the existing log aggregator — answer below.

## §2. 대안 분기
- **Alt-A: Use Datadog.** Persona: enterprise SRE team. Skipped: cost at our scale.
- **Alt-B: Self-host Loki.** Persona: ops-heavy startup. Skipped: maintenance burden.

## §3. 가정된 사용 시나리오
A new engineer joins in 6 months, opens the dashboard, types a feature name, and
sees last-hour errors without asking anyone. No manual SSH, no tickets.

## §4. 외부 검증 로그 (append-only)
(엔트리 없음)
EOF
}

# Append a well-formed §4 entry
append_good_anchor_4_entry() {
  local fid="${1:-feature-0001-demo}"
  local human="${2:-alice}"
  local anchor="unit/$fid/docs/ANCHOR.md"
  cat >> "$anchor" <<EOF

### $(date -u +%Y-%m-%dT%H:%M:%SZ) — source: human:$human
**challenge:** verified that direction still aligns with §1 external perspective
**body:**
After reviewing recent commits and the current ANCHOR §1-§3 statements, the work
still addresses the same operational pain: manual SSH for log inspection. The
dashboard implementation is on track, and no divergent user requests have been
observed. Confirming that we continue on the chosen path. Spent about ten
minutes reviewing to get to this conclusion, which is enough to spot drift if it
existed.
EOF
}

# Append a malformed (cargo-cult) entry
append_bad_anchor_4_entry() {
  local fid="${1:-feature-0001-demo}"
  local anchor="unit/$fid/docs/ANCHOR.md"
  cat >> "$anchor" <<'EOF'

### 2026-04-24T10:00:00Z — source: human:bob
**challenge:** spot check
**body:**
pass
EOF
}

stage_task_checkbox_delta() {
  local fid="${1:-feature-0001-demo}"
  local task="unit/$fid/docs/TASK.md"
  sed -i 's|- \[ \] Initial work|- [x] Initial work|' "$task"
  git add "$task"
}

stage_modify_append() {
  local fid="${1:-feature-0001-demo}"
  local modify="unit/$fid/docs/MODIFY.md"
  cat >> "$modify" <<'EOF'

## CHG-20260424-0001
- Date: 2026-04-24
- Summary: initial implementation
- Files: src/main.py
EOF
  git add "$modify"
}

stage_function_update() {
  local fid="${1:-feature-0001-demo}"
  local function_md="unit/$fid/docs/FUNCTION.md"
  printf '\n\nUpdated behavior: new dashboard endpoint.\n' >> "$function_md"
  git add "$function_md"
}

stage_code_change() {
  local fid="${1:-feature-0001-demo}"
  local src="unit/$fid/src/main.py"
  mkdir -p "$(dirname "$src")"
  printf 'print("hello")\n' > "$src"
  git add "$src"
}

# -----------------------------------------------------------------------------
# Argument parsing / help
# -----------------------------------------------------------------------------

@test "argparse: --help prints usage and exits 2" {
  run bash bin/verify-completion.sh --help
  [ "$status" -eq 2 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "argparse: no args → usage" {
  run bash bin/verify-completion.sh
  [ "$status" -eq 2 ]
}

@test "argparse: --pre-commit without feature-id → usage error" {
  run bash bin/verify-completion.sh --pre-commit
  [ "$status" -eq 2 ]
  [[ "$output" =~ "feature-id" ]]
}

@test "argparse: invalid feature-id format → exit 2" {
  make_feature_docs
  run bash bin/verify-completion.sh --pre-commit "bogus"
  [ "$status" -eq 2 ]
  [[ "$output" =~ "invalid feature-id" ]]
}

# -----------------------------------------------------------------------------
# META mode auto-detection
# -----------------------------------------------------------------------------

stage_review_fixture() {
  local review="${1:-meta/REVIEW.md}"
  mkdir -p "$(dirname "$review")"
  printf '\n## REV-20260908T000000-gate-fixture [SUBAGENT:qa-reviewer] — PASS\n\nSynthetic gate fixture; no production review claim.\n' >> "$review"
  git add "$review"
}

@test "META mode: AGENTS.md change with review skips operational companions" {
  echo "# dummy AGENTS rule" > AGENTS.md
  git add AGENTS.md
  stage_review_fixture
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "META mode" ]]
}

@test "META mode: bin/ script edit with review skips operational companions" {
  echo "# tweak" >> bin/verify-completion.sh
  git add bin/verify-completion.sh
  stage_review_fixture
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "META mode" ]]
}

@test "META mode: unit/_template/ edit with review skips operational companions" {
  echo "# skeleton tweak" >> unit/_template/docs/ANCHOR.md
  git add unit/_template/docs/ANCHOR.md
  stage_review_fixture
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "META mode" ]]
}

@test "META mode: mixed META+operational commit treated as operational (not META)" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  # AGENTS.md (META) + feature src (operational) → operational gate
  echo "# dummy" > AGENTS.md
  git add AGENTS.md
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  stage_review_fixture unit/feature-0001-demo/docs/REVIEW.md
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  # Check that META mode did NOT activate (no skip message)
  [[ ! "$output" =~ "META mode" ]]
  # Must evaluate checks. Whether pass/fail depends on fixture state — we just
  # verify it ran the gate.
  [[ "$output" =~ "CHECK#" ]]
}

# -----------------------------------------------------------------------------
# Check #2: TASK.md checkbox delta
# -----------------------------------------------------------------------------

@test "CHECK#2 PASS: staged TASK.md has [x] delta" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#2 PASS" ]]
}

@test "CHECK#2 FAIL: TASK.md has unstaged changes in pre-commit" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  # Modify TASK.md but DON'T stage
  sed -i 's|- \[ \] Initial work|- [x] Initial work|' "unit/feature-0001-demo/docs/TASK.md"
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#2 FAIL" ]]
  [[ "$output" =~ "unstaged" ]]
}

@test "CHECK#2 FAIL: TASK.md missing" {
  make_feature_docs
  rm unit/feature-0001-demo/docs/TASK.md
  git commit --quiet -am "temp"
  # Need to have something staged to avoid META-only skip
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#2 FAIL" ]]
}

# -----------------------------------------------------------------------------
# Check #3: MODIFY.md new CHG- entry
# -----------------------------------------------------------------------------

@test "CHECK#3 PASS: new CHG- entry staged" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#3 PASS" ]]
}

@test "CHECK#3 FAIL: no new CHG- entry (regression test for 10% gap)" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  stage_task_checkbox_delta
  # Skip stage_modify_append — this reproduces the §16.2 MODIFY.md omission
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#3 FAIL" ]]
}

# -----------------------------------------------------------------------------
# Check #4: FUNCTION.md staged when code files staged
# -----------------------------------------------------------------------------

@test "CHECK#4 PASS: code staged AND FUNCTION.md staged" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#4 PASS" ]]
}

@test "CHECK#4 PASS: docs-only change skips FUNCTION.md requirement" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  stage_task_checkbox_delta
  stage_modify_append
  # No code change, no FUNCTION.md update — should skip
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#4 PASS" ]]
}

@test "CHECK#4 FAIL: code staged but FUNCTION.md not (regression test for 10% gap)" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  stage_task_checkbox_delta
  stage_modify_append
  # Skip stage_function_update — this reproduces the §16.2 FUNCTION.md omission
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#4 FAIL" ]]
}

# -----------------------------------------------------------------------------
# Check #6: ANCHOR §1-§3 blank check with 24h grace
# -----------------------------------------------------------------------------

@test "CHECK#6 PASS: blank §1-§3 within 24h bootstrap grace" {
  make_feature_docs "feature-0001-demo" "0"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  # ANCHOR §1-§3 still blank, but created_at is "now" → grace applies
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#6 PASS" ]]
  [[ "$output" =~ "24h bootstrap grace" ]]
}

@test "CHECK#6 FAIL: blank §1-§3 past 24h grace" {
  make_feature_docs "feature-0001-demo" "48"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#6 FAIL" ]]
  [[ "$output" =~ "§1" ]]
}

@test "CHECK#6 PASS: §1-§3 filled past grace" {
  make_feature_docs "feature-0001-demo" "48"
  fill_anchor_1_3
  git add unit/feature-0001-demo/docs/ANCHOR.md
  git commit --quiet -m "fill anchor"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#6 PASS" ]]
}

# -----------------------------------------------------------------------------
# Check #7: ANCHOR §4 quality gate
# -----------------------------------------------------------------------------

@test "CHECK#7 PASS: good §4 entry past grace" {
  make_feature_docs "feature-0001-demo" "48"
  fill_anchor_1_3
  append_good_anchor_4_entry
  git add unit/feature-0001-demo/docs/ANCHOR.md
  git commit --quiet -m "add anchor content"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#7 PASS" ]]
}

@test "CHECK#7 FAIL: cargo-cult 'pass' entry past grace" {
  make_feature_docs "feature-0001-demo" "48"
  fill_anchor_1_3
  append_bad_anchor_4_entry
  git add unit/feature-0001-demo/docs/ANCHOR.md
  git commit --quiet -m "bad anchor"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#7 FAIL" ]]
}

@test "CHECK#7 PASS: no entries within 24h grace" {
  make_feature_docs "feature-0001-demo" "0"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#7 PASS" ]]
  [[ "$output" =~ "24h bootstrap grace" ]]
}

# -----------------------------------------------------------------------------
# Check #8: unstaged residual
# -----------------------------------------------------------------------------

@test "CHECK#8 PASS: clean staged set" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  # Commit ANCHOR updates first so they aren't unstaged residual
  git add unit/feature-0001-demo/docs/ANCHOR.md
  git commit --quiet -m "anchor content"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#8 PASS" ]]
}

@test "CHECK#8 FAIL: unstaged file remains" {
  make_feature_docs
  fill_anchor_1_3
  append_good_anchor_4_entry
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  # Add an unstaged file to trigger residual check
  echo "extra" > unit/feature-0001-demo/src/extra.py
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [[ "$output" =~ "CHECK#8 FAIL" ]]
}

# -----------------------------------------------------------------------------
# Full happy path (integration)
# -----------------------------------------------------------------------------

@test "integration: full valid staged set → exit 0 with PASS summary" {
  make_feature_docs "feature-0001-demo" "48"
  fill_anchor_1_3
  append_good_anchor_4_entry
  git add unit/feature-0001-demo/docs/ANCHOR.md
  git commit --quiet -m "anchor content"
  stage_task_checkbox_delta
  stage_modify_append
  stage_function_update
  stage_code_change
  stage_review_fixture unit/feature-0001-demo/docs/REVIEW.md
  run bash bin/verify-completion.sh --pre-commit "feature-0001-demo"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "verify-completion: PASS" ]]
}

# -----------------------------------------------------------------------------
# Shared mode
# -----------------------------------------------------------------------------

@test "--shared PASS: shared/docs/MODIFY.md has new CHG- entry" {
  echo "# shared README" > shared/README.md
  cat > shared/docs/MODIFY.md <<'EOF'
---
doc_type: SHARED_MODIFY
scope: shared
edit_policy: append-only
---
# shared MODIFY
EOF
  git add shared/
  git commit --quiet -m "shared scaffold"

  # Now stage a shared change with MODIFY entry
  mkdir -p shared/utils
  echo "def helper(): pass" > shared/utils/helper.py
  cat >> shared/docs/MODIFY.md <<'EOF'

## CHG-20260424-0001
- Date: 2026-04-24
- Summary: add helper utility
EOF
  git add shared/
  run bash bin/verify-completion.sh --shared
  [[ "$output" =~ "S1 PASS" ]]
}

@test "--shared FAIL: shared/ changed without MODIFY.md entry" {
  echo "# shared README" > shared/README.md
  cat > shared/docs/MODIFY.md <<'EOF'
---
doc_type: SHARED_MODIFY
edit_policy: append-only
---
# shared MODIFY
EOF
  git add shared/
  git commit --quiet -m "shared scaffold"

  # Stage a shared code change but skip MODIFY.md update
  mkdir -p shared/utils
  echo "def helper(): pass" > shared/utils/helper.py
  git add shared/utils/
  run bash bin/verify-completion.sh --shared
  [[ "$output" =~ "S1 FAIL" ]]
}
