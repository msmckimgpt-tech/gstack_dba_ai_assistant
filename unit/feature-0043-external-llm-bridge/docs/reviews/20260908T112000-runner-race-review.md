---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0043-external-llm-bridge
agent: runner_race_review
timestamp: 2026-09-08T11:20:00+09:00
trigger: runner update concurrency and recovery
verdict: PASS
---

### 1. Blocking issues
(no findings)

### 2. Cross-domain concerns
(no findings)

### 3. Challenge to current spec
R1은 단순 파일 잠금만으로 실행 세대·부모 감독·종료 중 재기동을 보장하지 못함을 지적했다. 기동 스탬프, 소유 프로세스 감독, 세대별 UI 이벤트, 실제 생존 PID 검사로 보완했다. R2/R3는 수정 후 PASS다. 배포 및 사용자 설치 적용은 코드 리뷰 판정과 분리한다.

### 4. Verdict
PASS



---

# Runner update recovery — R1 backend / QA / security review

- Worktree: `/root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0043-runner-update-recovery`
- Task: `TASK-20260908T120000-runner-update-recovery`
- Reviewer: `runner_race_review`
- Mode: read-only repository review; only this requested `/tmp` artifact written. Reproductions used temporary files and isolated child processes; no real service, account token, or AI runtime was called.
- Verdict: REQUEST CHANGES — two P1 findings were fixed during the review; three P2 findings remain at the observed snapshot.
- Scope: agent events / lifecycle / selfupdate; client core / supervisor / bridge / GUI; actual two-process update harness and supervisor tests.
- Task acceptance: two old runners sharing one installed bundle both return with the new build; explicit disconnect causes zero restarts; bounded retries and a disconnected notification; Windows process and argument semantics preserved; existing HTTPS / CA / fixed download path / token boundaries maintained.

## 1. Blocking issues

### P2-1 — queued `connected` overwrites an already reported disconnection

File: `unit/feature-0046-native-client/src/client/gui.py`, `_connect` (`self._post("connected", None)`) and `_on_connected`.

The supervisor starts its watcher before `spawn_runner` returns. A fast initial exit can post `runner_state(disconnected)` before `_connect` posts `connected`. `_on_connected` unconditionally displays connected and enables disconnect, so the final UI claims a connection for an already stopped runner. The same unconditional event can outlive an explicit disconnect; the newly added generation guard only covers `runner_state`.

Reproduced with the actual RunnerSupervisor and an isolated `python -c 'raise SystemExit(0)'` child. A controlled delay in the spawn wrapper allows the watcher to finish before returning, a legal thread scheduling order. The actual GUI `_connect` method produced:

```
[('runner_state', (0, 'disconnected', '연결이 끊겼습니다 — 다시 연결해 주세요.')),
 ('connected', None)]
runner_returncode = 0
```

Required change: attach generation and process identity to the connected event and validate both current ownership and current runner state in `_on_connected`. Verify both fast exit and explicit stop before event delivery.

### P2-2 — the two-process harness accepts historical readiness without checking current liveness or duplicates

File: `unit/feature-0043-external-llm-bridge/tests/verify_runner_update_processes.py:114` through the return result around line 122.

PASS currently means each token has appeared at least once in the new-build heartbeat set and each stderr file contains at least two `run.ready` strings. It does not check that both current runners are alive at the success point or that each token has exactly one active current process. A runner that dies just after its new heartbeat / ready event can satisfy the condition; duplicate new instances can also satisfy it. The test therefore does not completely establish the user's central requirement that both runners return and remain available.

Required change: for managed runners inspect Supervisor current pid and `running`, assert exactly one current live process per token, and inspect process instance IDs in the event ledger. For unmanaged Windows track the replacement PID from `run.start`, since the original Popen PID is obsolete after CRT exec. Add a short observation window or repeated fresh heartbeat to distinguish current recovery from a historical event. Cleanup must confirm those actual replacement PIDs exit.

### P2-3 — immutable runtime fingerprint still samples disk after source compilation

File: `unit/feature-0043-external-llm-bridge/src/agent/events.py`, `_read_running_source` and `_RUNNING_BUILD, RUNNING_BUNDLE_PATH = _read_running_source()`.

The new caching fixes a sibling replacement after initialization. It does not fix replacement between the interpreter loading / compiling the script and execution of the module-level fingerprint read. During that window the old code can cache the new disk fingerprint permanently, advertise the new build, and bypass the update. The writer sidecar is not acquired by the interpreter's startup read, so it does not close this window.

Deterministic source-loader-order reproduction used the actual current events source: compile the old source, replace the temporary script with a changed version, execute the already compiled old code. Observed:

```
executing_version = '2026.09.01'
disk_version = '2026.09.09'
reports_disk_new_build = True
cached_bundle = True
```

The harness starts both runners and waits for their first heartbeat before allowing any replacement, so this startup ordering is currently outside its coverage.

A complete fix needs a fingerprint derived from an immutable identity embedded in the executing code with matching server-side identity semantics, or an explicit startup reader / writer handshake. Do not claim exact loaded-code identification based solely on a cached second disk read. This remaining issue is startup-only; the much larger old-process / sibling-update window has been fixed.

## 2. Findings fixed during this review

### P1-F1 — valid runner stopped before validating replacement request: FIXED

The first observed Bridge `_do_connect` terminated and waited for the old runner before `_plan_for`, CA / checksum checks, or `check_connection`. The implementation was changed during the review to validate first, then replace under generation checks.

Rechecked with the actual Bridge and an existing fake process: a launch URL for another origin returned `no_base` and left `existing_stopped=False`. The later source also keeps `previous.terminate()` after successful `check_connection`.

### P1-F2 — initial path reread permanently disables self-update: FIXED

The first observed implementation cached `_RUNNING_BUILD` at import but called `running_bundle_path(_self_build())` later in main, after configuration and logging. A sibling replacement in between made that return None and permanently removed self-update support. The actual old check was reproduced with a temporary imported file.

The implementation now caches `RUNNING_BUNDLE_PATH` with the initial source read and initializes lifecycle's path from that value; main no longer rereads the disk for this decision. This fixes that path-recognition window. P2-3 above is the distinct earlier source-loading window.

## 3. Cross-domain concerns and confirmed boundaries

- `install_agent_file` already had same-directory mkstemp, fsync, and `os.replace`; the new fixed sidecar lock serializes cooperating writers and is never unlinked, avoiding split-lock-inode races.
- Client `install_runner` direct truncate/write was replaced by the same atomic writer protocol. The duplicated locking helper is reasonable under the standalone bundle packaging constraint; keep a behavioral compatibility test for both participants, not only selfupdate-to-selfupdate locking.
- Managed runners use a dedicated environment marker and exit 75; the supervisor owns the new Popen. This avoids relying on Windows exec preserving a Popen PID. Python's ordinary file descriptors are non-inheritable by default.
- Non-managed Windows reexec now quotes each CRT argument using `subprocess.list2cmdline([arg])`. Actual Windows verification must include the bundled interpreter under a path containing `DQA Connect`, Korean / space-containing script and CA paths, and a space-containing `--cmd` value.
- `reexec_self` failure now exits 1 instead of 0, so it is eligible for recovery rather than being mistaken for deliberate normal shutdown.
- Supervisor code bounds retries, cancels a pending retry on terminate, and drains stdout even when the browser shell has no reader. Existing tests exercise these behaviors with actual children. The reviewer did not repeat the parent's in-progress suite run.
- Tokens remain in the child environment rather than argv. Supervisor event messages do not include token, URL query, or subprocess exception text. No new token exposure was found in this diff. `output_tail` holds raw child output in memory; no new persistence or external transmission was added.
- Existing fixed update URL, HTTPS / configured CA validation, and deployed-single-file restriction are maintained. No request was made to weaken the authorized trust model.

## 4. Challenge to current diagnosis and evidence

The incident establishes two self-update stops and only one subsequent start. It does not by itself establish that two atomic replacements produced a partial Python file. Preserve that separation in REPORT: the unsafe client direct writer and Windows CRT argv behavior are concrete code findings; the historical runner's exact death cause is not proven solely by the 11 ms timestamps.

Official sources used in the preceding investigation and applied to this review:

- Microsoft CRT exec creates a process via CreateProcess and requires explicit quoting for arguments containing spaces: https://learn.microsoft.com/en-us/cpp/c-runtime-library/exec-wexec-functions?view=msvc-170
- CPython passes the parsed argv list directly into `_wexecv`: https://github.com/python/cpython/blob/3.13/Modules/posixmodule.c#L6429
- Windows file locks are not transferred to a child merely by inheriting a handle, and automatic unlock can lag process termination: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfile
- Python file descriptor inheritance defaults: https://docs.python.org/3/library/os.html#inheritance-of-file-descriptors

## 5. Verdict

REQUEST CHANGES for P2-1 / P2-2 / P2-3. The two original high-priority review findings were corrected during review, and the new supervisor / atomic writer direction preserves the intended trust and ownership boundaries. Do not treat the current two-process PASS as proof of duplicate-free current liveness until P2-2 is closed.

## 6. Follow-up design review during R1 handoff

Parent proposed embedding `_BUNDLE_SOURCE_SHA256` in the generated prelude. Runtime checks the disk bytes with only that prelude stamp removed against the constant loaded with the executing code. A match permits the existing full-file SHA12 report; a mismatch reports `""` but retains the originally recognized bundle path, enabling automatic update.

This design addresses P2-3 without changing the server's full-file fingerprint protocol. Verified `ai_tools.py::runner_build_is_stale` returns stale for `""` and reserves unknown for None. Implementation requirements:

1. Restamp every harness-modified old and new payload after the config-directory substitution and previous-deployment comment. Otherwise both variants permanently report an empty build.
2. Builder must write the exact UTF-8/LF bytes that it hashes, including on Windows; use bytes output to prevent newline conversion.
3. Remove only the single, well-defined prelude stamp line; absent or duplicate markers should not be interpreted as a verified fingerprint.
4. Retain bundle eligibility on digest mismatch only from the loaded marker plus actual entrypoint/source identity; module development without the generated marker stays ineligible.

Parent reports the queued-GUI connected guard and harness liveness checks are also being implemented. These follow-up implementations were not yet reread at this artifact's handoff; the original R1 verdict above records the reviewed snapshot, not a rejection of the proposed remediation.


---

# Runner update recovery — R2 backend / QA / security review

- Worktree: `/root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0043-runner-update-recovery`
- Task: `TASK-20260908T120000-runner-update-recovery`
- Reviewer: `runner_race_review`
- Scope: generated-source stamp / byte output; agent events, lifecycle, selfupdate; client core, supervisor, Bridge, GUI; actual-process update and supervisor regressions.
- Method: repository read-only review, targeted isolated runtime probes, and inspection of supplied Windows result files. Repository source files were not edited. Only this requested `/tmp` review artifact was written.
- Verdict: PASS for this reviewed scope — no outstanding P1 or P2 finding.

## 1. Blocking issues

None in the current reviewed snapshot.

R1 closure:

| Finding | R2 evidence | Status |
|---|---|---|
| P1: replacement request kills the existing runner before validation | Bridge validates plan, CA, runner and `check_connection` before terminating the old Supervisor; generation is checked again before spawn | Fixed |
| P1: delayed main path recheck disables updates after a sibling replacement | `RUNNING_BUNDLE_PATH` is cached with startup identity and lifecycle retains it without a main-time disk comparison | Fixed |
| P2: queued connected event overwrites disconnection / explicit stop | GUI connected event carries generation and process; handler verifies generation, ownership and current `running` state | Fixed |
| P2: historical ready events pass without current liveness | Harness checks two starts, final new build, exactly one live PID per identity, additional current `wait_for_request` roundtrips, and Supervisor running state | Fixed |
| P2: compiled old code caches the new disk fingerprint | Builder embeds a source SHA256 constant loaded with the code; startup checks the disk body against that constant, reporting empty/stale while retaining update eligibility on mismatch | Fixed |

Two small issues found during R2 were corrected and rechecked before this verdict:

- Startup read failure now returns `('', bundle)` after recognizing the loaded stamped entrypoint. A temporary file sharing / permission failure no longer permanently removes self-update eligibility. An isolated PermissionError injection returned an empty build with `bundle_path_retained=True`.
- The startup-race regression now sets `BRIDGE_LOG_DIR` under its pytest temporary directory before invoking actual update logging, avoiding writes into a real user's runner event logs.

## 2. Cross-domain concerns and checks

### Startup identity and trust

The generated prelude contains the SHA256 of the exact UTF-8 source before stamp insertion. The builder writes bytes, preserving that hash input across Windows newline rules. Runtime requires exactly one matching stamp line and a hash match after removal; a different loaded/disk generation is never reported as current. The existing server full-file SHA12 contract remains unchanged. `runner_build_is_stale('')` was checked during R1 and correctly requests an update; None remains the distinct server-unknown case.

The generated marker is an execution-generation identity, not a signature or a replacement for transport trust. Existing fixed download path, HTTPS and configured CA, download validation, and module-development exclusion remain intact. The loaded marker plus actual entrypoint/source identity is the basis for retaining the bundle path even when the disk is newer or temporarily unreadable.

### Installation and process ownership

Both new client installation and runner self-update use same-directory temporary files, fsync, fixed sidecar locking, and atomic replacement. Same-payload detection avoids a redundant replacement without suppressing the second old runner's restart. The fixed lock file is not deleted, preventing independently locked replacement lock inodes.

Managed self-update exits with code 75 and the owning Supervisor creates the replacement Popen. This avoids Windows CRT exec PID handoff problems. Non-managed Windows exec arguments receive CRT quoting. Reexec exceptions now exit nonzero. Retry attempts remain bounded, explicit stop cancels pending spawn, the output pipe is continuously drained, and Supervisor completion is signaled in its final cleanup path. Bridge shutdown waits for its owned supervisor and closes the server in finally blocks.

Tokens stay in child environment variables, not argv or generated event messages. No new token exposure, trust bypass, or foreign-process termination was found in this diff.

### Direct targeted R2 runtime check

Repeated the R1 GUI race with the actual RunnerSupervisor and an isolated `python -c 'raise SystemExit(0)'` child. The watcher was allowed to finish before the spawn wrapper returned. Delivered the real GUI's queued runner-state and connected events in order. Result:

```
gui_final_status = '연결이 끊겼습니다 — 다시 연결해 주세요.'
dead_runner_reported_connected = False
runner_returncode = 0
```

### Supplied Windows evidence inspected

Inspected the parent's final result files. All four runs used Windows Python 3.14.7 and reported two returned runners, two downloads, one live PID for each identity, and continuing wait roundtrips:

| Evidence file | Supervised | Staggered | Returned | Wait roundtrips a/b |
|---|---:|---:|---:|---:|
| `/tmp/runner-win-final-direct.log` | No | No | 2/2 | 10 / 9 |
| `/tmp/runner-win-final-stagger.log` | No | Yes | 2/2 | 68 / 9 |
| `/tmp/runner-win-final-supervised.log` | Yes | No | 2/2 | 10 / 10 |
| `/tmp/runner-win-final-supervised-stagger.log` | Yes | Yes | 2/2 | 88 / 10 |

The simultaneous managed case recorded a 3.43 ms download gap. These are inspected execution records supplied by the parent, not a claim that the reviewer reran Windows. The parent continues to own final build, full-suite and deployment verification.

## 3. Challenge to current spec

No outstanding challenge to the requested two-defect repair in this scope. Retain the factual distinction between the historical two-stop / one-start observation and an unproven claim that two already-atomic writes alone produced partial Python source. The actual fixes cover cooperating writer serialization, the unsafe client overwrite, Windows argument / process handoff, stable execution identity, and recovery after pre-logging child failure.

Later UI-copy edits discussed by the parent are not part of this source snapshot and are not implicitly reviewed by this verdict.

## 4. Verdict

PASS — R1 findings and the two R2 observations are closed in the reviewed code. No remaining P1/P2 backend, QA, or security defect was identified. Final release readiness still uses the parent's build, suite and deployment evidence, rather than this code-review verdict alone.


---

# Runner update recovery — R3 final limited-scope review

- Worktree: `/root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0043-runner-update-recovery`
- Task: `TASK-20260908T120000-runner-update-recovery`
- Reviewer: `runner_race_review`
- Mode: repository read-only; only this requested `/tmp` artifact written.
- Scope: connect-modal relaunch failure copy; handoff/web-shell regression selectors; runtime-discovery test isolation; removal of leaked `app` stub; Makefile/CI native-test registration; Windows GUI/tray recovery verifier.
- Verdict: PASS for the listed R3 scope. Product-core R2 PASS remains applicable; no new P1/P2 product defect was found.

## 1. Blocking issues

None in the final reviewed snapshot.

One verifier defect was found and corrected during R3: the initial Windows script asserted that the tray reconnection toggle was disabled after a disconnection. Production correctly enables it and labels it `다시 연결`. The verifier now checks that actual intended contract.

The first Windows run subsequently reached the screenshot step but failed because Pillow was unavailable. The script now captures through a local PowerShell/System.Drawing helper instead of importing an undeclared Pillow dependency. The following Windows run returned a successful result; the failed first run was not treated as PASS.

## 2. Cross-domain concerns and verification

### Product copy

`unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js::MSG_RELAUNCH_NO_UPDATE` no longer sends the user to the deleted first-step command UI. It describes the observed update failure without falsely diagnosing an old launch script, and points to the existing DQA app update/reconnect path. The change does not modify authentication, launch eligibility, token handling, or update trust checks.

### Existing regression repairs

- `test_handoff_seam.py` limits double-quoted string matching to a line and finds the relevant click handler / `_fire` function instead of arbitrary slices around the first identifier occurrence. The asserted contracts still require token acquisition, an explained scheme failure, and absence of the deleted terminal path.
- `test_web_shell.py` checks that `_offerLaunch` returns for `clientBridge` before the button is exposed, matching the actual function's control flow.
- `test_runtime_model_selector.py` now intercepts `_which_ai`, which is what `detect_runtimes` actually calls. The selected failure-path test therefore controls installed-runtime discovery rather than accidentally depending on a workstation's real AI installations. Its capability probe remains stubbed.
- `test_bridge_attachment_write.py::test_done_waits_briefly_for_delivery` extracts selected function/constant AST nodes into an explicit namespace; it never imports the full app. Removing the unscoped `sys.modules['app']` stub preserves its assertions and removes pollution of subsequent tests.

No change weakens the associated behavioral assertions merely to silence a legitimate product regression.

### CI registration

Compared the actual explicit pytest arguments in Makefile and `.github/workflows/ci.yml` programmatically:

```
same_explicit_suite_set = True
native_registered_both = True
suite_count = 10
```

Native-client tests now run in both paths; this fixes the previous gap where pyproject testpaths alone did not affect commands supplying explicit test directories. The standalone Windows verifier is named `verify_...`, so it is not silently collected as a headless pytest test.

### Windows GUI/tray verifier

Reviewed `unit/feature-0046-native-client/tests/windows/verify_runner_recovery.py` and inspected `/tmp/runner-win-gui.log` after the corrected run. The verifier uses the actual ClientApp window and live tray backend, suppresses real runtime discovery, and creates isolated invalid-Python children. It checks bounded restart attempts, visible application disconnection status, actual tray notification invocation, zero remaining children, and that a late connected event cannot overwrite the failed state.

Inspected final execution record:

```
ok = true
python = '3.14.0'
spawned = 3
status = '연결이 끊겼습니다 — 자동 복구에 실패했습니다. 다시 연결해 주세요.'
notification title = '연결이 끊겼습니다'
live_children = 0
late_connected_ignored = true
```

This is a real Windows source-GUI/tray smoke check. It does not claim to test the installed WebView2 shell or to prove the OS displayed a balloon merely from the notification method being invoked. The parent owns screenshot inspection and final installed-build/deployment validation.

A nonblocking evidence-hardening suggestion was sent: set PowerShell `$ErrorActionPreference = 'Stop'` and verify the PNG exists and is nonempty after capture, so a nonterminating capture error cannot look successful from exit status alone.

## 3. Challenge to current spec

None. The R3 work repairs stale user guidance and test isolation/selection while keeping the original runner self-update/recovery objective unchanged. The parent's full `make test` run was still in progress during review and is not declared passed by this artifact.

## 4. Verdict

PASS — no outstanding P1/P2 finding in this final limited scope. The verifier's incorrect tray assertion and missing screenshot dependency were corrected, and the resulting Windows run passed its recovery assertions. R2 remains the product-core review; final test-suite, screenshot, packaging and deployment evidence belong to the parent completion record.
