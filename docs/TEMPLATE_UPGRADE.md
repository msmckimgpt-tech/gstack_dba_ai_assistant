---
doc_type: TEMPLATE_UPGRADE_GUIDE
scope: repository
status: active
edit_policy: human-guided
source_of_truth: true
template_version: v3.44.1
domain: [workflow, tooling]
ai_read_priority: 5
---

# Template Upgrade Guide

`bin/template-upgrade.sh` is the canonical entry point for absorbing
`ai_delegated_dev_template` updates into your consumer project.

`/_template:version-upgrade` is the Claude Code SKILL wrapper that runs the
same logic conversationally — it is optional convenience, not the canonical
path. Either flow produces the same result.

## §0. Consumer repo Immutability (v3.8.0+, §13.2.7 F0)

**Direct edits to `<wrapper>/repo/` are forbidden in consumer projects.**

소비자 프로젝트에서 `repo/` directory 의 직접 mutation 은 `bin/verify-completion.sh`
check #11 (`check_11_repo_immutability`) 에 의해 차단됩니다. main checkout 의
working tree 가 dirty 인 채 `--pre-commit` 호출 시 FAIL.

### Update path (유일한 수단)

template 의 변경을 흡수하는 정상 경로는 다음 두 가지:

**(a) `bin/template-upgrade.sh --apply`** (권장 — customization preservation 자동)

```bash
cd /path/to/your/consumer/wrapper
bash repo/bin/template-upgrade.sh --apply
```

본 명령은 hop chain 을 적용하여 `repo/` 안의 managed 파일을 갱신합니다.
`bin/template-upgrade.sh` 자체는 §13.2.7 F0 의 carve-out 으로 처리됨 (script
가 mutation 하는 path 는 hop 의 의도된 영역이며, verify-completion 의 `--pre-commit`
호출 시점은 hop 완료 후 사용자가 commit 직전 — 그 시점은 customization 의
working tree 상태가 아닌 hop output 으로 정의됨).

**(b) `cd repo && git pull --ff-only origin main`** (raw — submodule / direct git 경로)

```bash
cd /path/to/your/consumer/wrapper/repo
git fetch origin
git pull --ff-only origin main
```

non-fast-forward 발생 시 (consumer 가 `repo/` 안을 customize 했거나 main 이
history rewrite 된 경우) → `git pull` 거부. customization conflict 는 worktree
에서 resolve 후 PR (Customization path 참조).

### Customization path (작업 수단)

`repo/` 안 정책 doc 또는 hop 또는 gate 를 자체 customize 하려면 **worktree 강제**:

```bash
cd /path/to/your/consumer/wrapper
git -C repo worktree add ../.worktrees/<feat> -b ai/<agent>/<feat>
cd .worktrees/<feat>
# ... 작업, commit, push ...
git push -u origin ai/<agent>/<feat>
```

이후 GitHub PR 또는 자동 머지 (§16.3 + §13.2.5). 머지 후 main worktree 의
다음 turn first action 으로 `cd repo && git pull --ff-only`.

### Escape hatch (긴급 회피)

```bash
GSTACK_SKIP_REPO_IMMUTABILITY=1 git commit ...
# or
bash repo/bin/verify-completion.sh --pre-commit feature-XXXX-x --skip-repo-immutability
```

emergency hotfix / CI 환경 차이 등 일시 우회용. 상시 사용 금지 — 사용 시
`REPORT.md` 에 사유 기록 권유.

### Carve-outs (자동 통과)

- **Template base maintainer** (`<repo>/_template_maintainer/HISTORY.md` 존재):
  ai_delegated_dev_template 의 source-of-truth 영역은 정책 비적용.
- **ai/* worktree** (`<wrapper>/.worktrees/<feat>/`): F0 외 (F1 은 check #10 에서
  별도 검증).
- **`/_template:init` 부트스트랩**: `.template/init-completed` 마커 부재 시 1회
  carve-out (신규 consumer 첫 setup).
- **git pull / fetch / submodule update**: read-only 또는 fast-forward 만 — mutation
  아님.

상세: `repo/AGENTS.md` §13.2.7 + `repo/docs/DECISIONS.md` ADR-0021.

## Quickstart (3 commands)

```bash
cd /path/to/your/consumer/repo

# 1. See where you are
bash repo/bin/template-upgrade.sh --check

# 2. Preview what would change
bash repo/bin/template-upgrade.sh --dry-run --diff

# 3. Apply with backup
bash repo/bin/template-upgrade.sh --apply
```

Or in Claude Code: `/_template:version-upgrade --apply`.

## What it does

- Detects your consumer repo's current template version (from `.template-state`
  if present, else from `AGENTS.md` frontmatter `template_version`).
- Computes the chain of incremental hops to the template's latest version.
- Runs each hop with backup + transaction semantics: lock → backup → apply →
  validate → atomic state write.
- Preserves your customizations (option B "영역별 정책": consumer-only files
  like `Makefile` or `docker-compose.yml` are kept; managed policy doc bodies
  are updated; conflicts where you modified a managed file outside of marker
  blocks are reported).
- For BREAKING hops (e.g. v3.6.0 → v4.0.0-rc.1), auto-runs
  `bin/template-bake-check.sh` first as a 5-point pre-condition guard.

## Modes

| Mode | What | Read-only? |
|---|---|:---:|
| `(no flags)` / `--check` | Print declared / detected / pending hops report | ✓ |
| `--check-deps` | Print bash / git / sed versions | ✓ |
| `--diagnose` | Drift detection (declared vs actual content fingerprint) | ✓ |
| `--dry-run` | Print hop manifest | ✓ |
| `--dry-run --diff` | Apply to temp copy + show diff | ✓ |
| `--apply` | Backup + run hops + state write + 'what's new' summary | ✗ (mutates) |
| `--rollback` | Restore most recent backup | ✗ (mutates) |
| `--state-repair` | Rebuild `.template-state` from frontmatter probe | ✗ (mutates) |
| `--unlock-stale` | Force-remove stale `.template-upgrade.lock` | ✗ (mutates) |

## Modifiers

| Flag | Default | Purpose |
|---|---|---|
| `--json` | off | Output stable JSON schema where applicable |
| `--yes` / `--non-interactive` | interactive | Skip AskUserQuestion-style confirms |
| `--strategy=preserve` | `preserve` | Customization policy. v3.6.0 has only `preserve` (option B). v3.7.0+ adds `merge` (option C 3-way) |
| `--target-version=vX.Y.Z` | template HEAD | Target hop ceiling |
| `--keep-backups=N` | `5` | Backup retention count |
| `--force` | off | Override safety gates (working tree dirty, drift). NOT recommended |
| `--target=PATH` | (auto) | Override consumer repo detection — for tests |

## Customization preservation (option B "영역별 정책")

`v3.6.0` ships option B only. The classifier walks managed files and
classifies each:

| Class | Meaning | Behavior on `--apply` |
|---|---|---|
| `added` | Consumer-only file (e.g., `Makefile`, `docker-compose.yml`, `MCP_DESIGN.md`) | Preserved unchanged |
| `preserved` | Consumer-modified within marker block (`<!-- TEMPLATE-EXAMPLE -->`, `<!-- HUMAN-LOCKED:START -->`, `<!-- AI-EDITABLE:START -->`) | Preserved unchanged |
| `managed` | Consumer matches template-clean baseline | Updated by hop |
| `missing` | Template has it, consumer doesn't | Created by hop |
| `conflict` | Consumer modified a managed file outside markers | Backup + hop applies; consumer reviews `git diff` |
| `excluded` | Excluded from consumer (`.git`, `_template_maintainer/`, `bin/tests/`, `bin/migrations/`) | Ignored |

## State file: `.template-state`

`bin/template-upgrade.sh --apply` creates `.template-state` at consumer repo
root on first run. Schema (flat `KEY=VALUE`, no YAML/JSON parser dependency):

```
state_schema_version=1
declared_version=v3.5.0
detected_version=v3.5.0
applied_migrations=v3.0.0-to-v3.1.0,v3.1.0-to-v3.2.0,v3.2.0-to-v3.3.0,v3.3.0-to-v3.4.0,v3.4.0-to-v3.5.0
strategy=preserve
last_synced_at=2026-04-30T08:00:00Z
last_synced_template_commit=e18eea3
customized_paths=Makefile,docker-compose.yml,MCP_DESIGN.md
```

`AGENTS.md` frontmatter `template_version` is **canonical** — `.template-state`
is audit / cache. If they disagree, drift is reported and `--apply` refuses to
proceed without `--state-repair` or `--force`.

## Backup retention

Each `--apply` creates a single snapshot at `.template-backups/<from>-to-<to>-<ts>-<pid>/`
**before** any hop runs. Hops are atomic-or-restore from this snapshot.

`--rollback` restores the most recent snapshot.

By default `--keep-backups=5`; older snapshots are pruned at the end of each
successful `--apply`.

## Error message catalog

`bin/template-upgrade.sh` exits with these specific codes; messages always
suggest a recovery action.

| Exit | Trigger | Message format | Suggested action |
|:---:|---|---|---|
| 0 | success / no-op | (depends on mode) | — |
| 1 | generic / CONCERN | `ERROR: <reason>` | re-run with `--yes` to override (if appropriate) |
| 2 | usage error | `ERROR: unknown argument: ...` + usage | check `--help` |
| 3 | working tree dirty | `ERROR: N file(s) with uncommitted changes:` + git status | `git stash -u` or commit, or `--force` (NOT recommended) |
| 4 | lock held | `ERROR: lock file ... held by PID X (started ...)` | wait for other process, or `--unlock-stale` if PID dead |
| 5 | hop failed | `ERROR: hop ... exited with code N. Transcript: .template-upgrade-logs/...log. Backup intact at: ...` | `bash bin/template-upgrade.sh --rollback` |
| 6 | drift detected | `ERROR: declared template_version=v3.0.0 but ...` | `--state-repair` to rebuild, or `--force` |
| 7 | state corrupt | `ERROR: .template-state syntax error at line X` | `--state-repair` (corrupt file backed up to `.template-state.corrupt.<ts>`) |
| 8 | dep missing | `ERROR: missing required dependencies: ...` | install via OS package manager |
| 9 | bake-check BLOCK | `ERROR: bake-check BLOCK — refusing to apply BREAKING hop ...` | address the specific check (consumer adoption / drift / panel verdict / bats CI), see `bash bin/template-bake-check.sh` |

## Dependencies

**Consumer side (runtime)**:
- bash ≥ 3.2 (macOS-compatible)
- git ≥ 2.20
- sed (BSD or GNU — `lib/common.sh` `sed_inplace` wrapper handles both)
- awk (POSIX)
- grep (POSIX)
- cut (POSIX)
- `python3` — **content-delta hop 에만 필요** (정책 doc 본문 § 삽입을 수행하는 hop.
  v3.6.1+ 의 다수 hop 이 이 계층에 해당하며, 원자적 기록(`os.replace`)과 UTF-8 안전성을
  위해 사용한다). 오케스트레이터(`bin/template-upgrade.sh`)·state·frontmatter 계층 자체는
  python3 없이 동작하므로, frontmatter-bump hop 만 경유하는 업그레이드 경로는 영향받지
  않는다. python3 부재 시 **v3.40.0+ hop 은 어떤 파일도 건드리기 전에** 진단과 함께
  중단한다. 다만 그 이전 hop 일부(예: `v3.6.0-to-v3.6.1`)는 자체 python3 확인보다 먼저
  파일 복사를 시작하므로 **부분 적용 후 실패**할 수 있다 — pending 범위에 content-delta
  hop 이 있으면 업그레이드 시작 전에 설치하는 것이 안전하다 (`--check-deps` 가 부재를
  진단으로 알린다).

**Maintainer side (CI only)**:
- bats (for `bin/tests/migration_*.bats`)

**Optional (per `--strategy=` flag — v3.7.0+)**:
- `git merge-file` (only when `--strategy=merge` opt-in is added in v3.7.0+)

No `yq`. No `jq`. 오케스트레이터·state·frontmatter 계층은 Bash + git + POSIX text
utilities only (content-delta hop 의 `python3` 는 위 예외).

## Diagnostic commands

When something looks wrong:

```bash
# Print declared/detected/pending — usually first thing to check
bash bin/template-upgrade.sh --check

# Drift detection (declared_version vs detected_version)
bash bin/template-upgrade.sh --diagnose

# Verify your environment has all required tools
bash bin/template-upgrade.sh --check-deps

# Preview what would change without touching anything
bash bin/template-upgrade.sh --dry-run --diff

# If state file is corrupt or you've manually edited frontmatter:
bash bin/template-upgrade.sh --state-repair

# If there's a stale lockfile (e.g., previous run was killed):
bash bin/template-upgrade.sh --unlock-stale
```

## Setup (`/_template:version-upgrade` SKILL)

The SKILL wrapper lives in the `_template/` git submodule
(`ai-delegated-dev-template-personas` repo). 다음 두 등록 방식 중 하나만
있으면 작동한다.

### 방식 1 — consumer-local submodule update (default, 권장)

```bash
cd /path/to/your/consumer/repo
git submodule update --remote .claude/commands/_template
git add .claude/commands/_template
git commit -m "chore: bump _template submodule (version-upgrade SKILL)"
```

After this, Claude Code 가 working directory 가 해당 consumer repo 인 세션에서
`/_template:version-upgrade` 를 자동 인식한다 (project-level slash command).
다른 모든 `_template:*` SKILL 과 동일 패턴.

### 방식 2 — global registration (옵션, 머신 전체 공유)

`~/.claude/commands/_template/` 에 SKILL 파일을 두면 (symlink 또는 복사) 모든
프로젝트에서 인식된다:

```bash
mkdir -p ~/.claude/commands/_template
ln -s /path/to/template/repo/.claude/commands/_template/version-upgrade.md \
      ~/.claude/commands/_template/version-upgrade.md
```

CI / 일회성 환경 / submodule 못 쓰는 환경 용도. 일반적으로는 방식 1 권장.

### 등록 detection

`bin/template-upgrade.sh --apply` / `--rollback` 호출 시 위 두 위치 중 어느
하나라도 SKILL 파일을 가지고 있으면 정상 통과. 둘 다 없으면 안내 메시지 출력
(작동 자체는 차단되지 않음 — CLI 가 canonical path).

### Wrapper-level `.claude` symlink

소비자 프로젝트가 일반적으로 `<wrapper>/repo/` 구조 (= `repo/` 가 git repo
이고 `<wrapper>/` 가 그 상위 폴더) 인 경우, **cwd 가 wrapper 디렉토리**일 때도
Claude Code 의 SKILL discovery (cwd 기반 `.claude/commands/` 스캔) 가
동작하려면 다음 symlink 가 필요하다:

```
<wrapper>/.claude -> repo/.claude
```

template repo 자체도 동일 패턴 (`/path/to/template/.claude -> repo/.claude`)
을 사용한다.

`bin/template-upgrade.sh --apply` (그리고 up-to-date 분기) 가 호출 후미에서
**자동으로 이 symlink 를 생성**한다 (`ensure_wrapper_skill_link`). 멱등 —
이미 올바른 link 면 skip, 다른 형태의 파일/디렉토리가 있으면 보존하고 warn.

수동 셋업이 필요한 경우:

```bash
cd /path/to/your/<wrapper>
ln -sfn repo/.claude .claude
```

이 link 는 wrapper 폴더에 있고 git track 영역 외이므로 commit 대상이 아니다.

### CLI-only 사용 (SKILL 없이)

SKILL 등록 없이도 `bin/template-upgrade.sh --apply` 는 작동한다.
CLI 가 canonical path 이고, SKILL 은 conversational convenience 다.

## Setup (Codex `/_template:*` compatibility)

Codex 호환 command 의 source of truth 는 consumer repo 안의 `.codex/` 와
repo-local plugin/marketplace 구조다. `~/.codex` 와 Codex plugin cache 는 설치
대상일 뿐이며 template 업데이트의 원본으로 취급하지 않는다.

### Codex copy-base skill discovery

현재 확인된 Codex skill 호출 표면은 `$<skill-name>` 이다. 예를 들어
`$_template-entry`, `$_template-init`, `$_template-version-upgrade` 를 직접 호출할
수 있어야 한다. 자동완성은 Codex 가 시작된 workspace 에서 `.codex/skills` 를
발견할 때 동작한다.

copy-base 를 그대로 복사하면 wrapper-level symlink 가 누락되는 경우가 있다. 이때
`/path/to/project/.codex -> repo/.codex` 가 없으면 wrapper 에서 Codex 를 시작한
사용자는 `$` 자동완성에서 `_template-*` skill 을 보지 못한다. 첫 AI 작업자는
skill 이 없다고 판단하기 전에 다음을 먼저 수행한다:

```bash
# wrapper cwd: FIRST_REQUEST.md 와 repo/ 가 나란히 있는 위치
cd /path/to/your/consumer

# 1. repo-local Codex command/plugin 구조 검증
bash repo/bin/codex-template-install.sh --check

# 2. wrapper cwd 로 Codex 를 시작할 때 필요한 symlink 복구
bash repo/bin/codex-template-install.sh --link

# 3. 링크와 repo-local 구조 재검증
bash repo/bin/codex-template-install.sh --check
```

이미 `/repo` 안에서 Codex 를 시작한다면 `cd /path/to/your/consumer/repo` 후
`bash bin/codex-template-install.sh --check` 로 repo-local 구조를 검증한다.
`--link` 가 플랫폼 정책상 실패하면 Codex 를 `/repo` 에서 시작하고, wrapper-level
자동완성 제한을 작업 로그에 남긴다.

Codex local marketplace 로 노출하려면:

```bash
bash bin/codex-template-install.sh --install-marketplace
```

Codex 가 exact `/_template:<name>` namespace 를 plugin command 로 노출하지 못하는
버전에서는 prompt 호환 링크를 추가한다:

```bash
bash bin/codex-template-install.sh --install-prompts
```

이 명령은 `$CODEX_HOME/prompts` (기본 `~/.codex/prompts`) 아래에 다음 symlink 를
만든다:

- `_template:<name>.md` — exact syntax 시도용
- `_template-<name>.md` — colon namespace 거부 시 fallback alias

Codex 문서 기준으로 2026-05-11 현재 IDE extension 의 slash command 문서는
built-in 명령 중심이며, Codex app 문서는 enabled skills 가 slash command list 에도
표시될 수 있다고 설명한다. 따라서 VSCode IDE 에서 `/` 목록 노출 여부는 설치 후
실제 환경에서 확인하고, 미노출 시 prompt fallback 또는 `$` skill 호출을 사용한다.

## Common scenarios

### "I just pulled a new template version"

```bash
bash bin/template-upgrade.sh --check
# pending: 1 hop(s)
#     - v3.5.0-to-v3.6.0

bash bin/template-upgrade.sh --dry-run --diff
# (preview)

bash bin/template-upgrade.sh --apply
# Migration: v3.5.0 → v3.6.0 (1 hop)
# Backup: .template-backups/v3.5.0-to-v3.6.0-...
# [1/1] v3.5.0-to-v3.6.0 ... applied
# What's new: ...

git diff
git commit -am "chore: absorb template v3.6.0"
```

### "My frontmatter says v3.0.0 but I've actually absorbed v3.4.0 changes"

This is the drift case the v3.5.1 release explicitly repaired in the template
itself, and the migration runner detects+handles for consumers:

```bash
bash bin/template-upgrade.sh --diagnose
# ⚠ drift detected: declared_version=v3.0.0 but AGENTS.md frontmatter=v3.4.0

bash bin/template-upgrade.sh --state-repair
# (Rebuilds .template-state from AGENTS.md frontmatter)

bash bin/template-upgrade.sh --check
# pending: 1 hop(s)
#     - v3.4.0-to-v3.5.0

bash bin/template-upgrade.sh --apply
```

### "Migration broke something I didn't expect"

```bash
bash bin/template-upgrade.sh --rollback
# Rollback complete. Verify with `git diff` (or `git status` for untracked files).
```

Then:
- Inspect `.template-upgrade-logs/<ts>-<hop>.log` for what the hop did.
- Inspect the backup at `.template-backups/<from>-to-<to>-<ts>-<pid>/` for
  byte-level state pre-hop.
- File an issue against the template repo with the log + backup pointer.

### "I'm on v3.0.0 and the template is now v4.0.0-rc.1 (BREAKING)"

```bash
bash bin/template-upgrade.sh --check
# pending: 7 hop(s)
#     - v3.0.0-to-v3.1.0
#     - ...
#     - v3.5.1-to-v3.6.0
#     - v3.6.0-to-v4.0.0-rc.1 (BREAKING)

bash bin/template-upgrade.sh --apply
# (When the BREAKING hop is reached, bake-check runs automatically.)
# Migration: v3.0.0 → v4.0.0-rc.1 (7 hops)
# Backup: ...
# [1/7] v3.0.0-to-v3.1.0 ... applied
# [2/7] v3.1.0-to-v3.2.0 ... applied
# ...
# [7/7] v3.6.0-to-v4.0.0-rc.1
#   BREAKING hop — running bake-check...
#   [PASS] 1. consumer adoption: 3/6 ≥ 2
#   [PASS] 2. drift case: 0 detected
#   ...
#   bake-check PASS — proceeding
#   ... applied
```

If bake-check returns CONCERN, you'll be prompted to re-run with `--yes` or
address the concerns. If it returns BLOCK (severe issue), the runner aborts
with the partial backup intact — fix the underlying problem and retry.

## Authoring new migrations (v3.7.0+ contributors)

See `bin/migrations/README.md`.

## Reference

- Plan: `/root/.claude/plans/template-v3.6.0-plan.md`
- /autoplan source: `/root/.claude/plans/template-version-sync-plan.md`
- Library: `bin/migrations/lib/{common,state,frontmatter-update,customization-detect}.sh`
- Hops: `bin/migrations/v*-to-v*.sh`
- Registry: `bin/migrations/registry.sh`
- Tests: `bin/tests/migration_*.bats`
- Maintainer history: `_template_maintainer/HISTORY.md`
