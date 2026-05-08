# Template Changelog

이 저장소는 `ai_delegated_dev_template` 의 메타 변경 이력을 기록한다. 각 entry는
v3.x 버전 또는 release-candidate 시점에 의미 있는 정책·도구·스켈레톤 변경을
요약한다.

## v3.6.0 — 2026-05-06 (migration infrastructure — non-BREAKING)

### Summary

소비자 프로젝트가 future template 변경을 안전하게 흡수할 수 있는 **migration runner + safety nets** 도입. NON-BREAKING. `/autoplan` 2026-04-30 session 으로 결정된 split release 의 두 번째 단계 (v3.5.1 → **v3.6.0** → v4.0.0-rc.1 → v4.0.0).

핵심 기여:

1. **`bin/template-upgrade.sh`** — 9-mode orchestrator (`--check` / `--check-deps` / `--diagnose` / `--dry-run [--diff]` / `--apply` / `--rollback` / `--state-repair` / `--unlock-stale` / `--help`). transaction 보장 (lock → backup → apply → validate → atomic state). BREAKING hop guard (자동 `bin/template-bake-check.sh` 호출).
2. **`bin/template-version.sh`** + **`bin/template-bake-check.sh`** — 버전 조회 + 5-항목 pre-condition guard.
3. **7 incremental hops** (`v3.0.0-to-v3.1.0` ... `v3.5.1-to-v3.6.0`) — 6 frontmatter-bump synonyms + 1 REAL hop adding 3 frontmatter fields.
4. **4 lib helpers** (`common`, `state`, `frontmatter-update`, `customization-detect`) — option B "영역별 정책" customization 보존, BSD/GNU sed 호환 wrapper, no yq/jq 의존성.
5. **`/_template:version-upgrade` SKILL** — Claude Code conversational wrapper (별도 submodule PR, 향후 통합).
6. **bats fixtures + 9 tests** — clean / customized 양쪽 v3.0.0 → v3.6.0 walk + idempotency + rollback + customization preservation (sha256 byte-identical 검증).

### Added

- 3 frontmatter fields (additive) on all template policy docs:
  - `template_version` (canonical version tracker)
  - `domain` (e.g., `[governance, workflow, context, safety]` for AGENTS.md)
  - `ai_read_priority` (integer, maps to AGENTS §3.1)
- `docs/TEMPLATE_UPGRADE.md` — canonical entry doc (3-command quickstart + all flags + error catalog + 4 common scenarios)
- `bin/migrations/README.md` — hop authoring guide for v3.7.0+ contributors
- `README.md` Source of Truth 표 + quickstart paragraph

### Changed

- `bin/verify-completion.sh` `is_meta_path` 갱신 — `_template_maintainer/*`, `README.md`, `FIRST_REQUEST.md` 추가 (META-class 인식)

### Compatibility

- NON-BREAKING. §번호 변경 0건. consumer 의 customization (Makefile, docker-compose.yml, MCP_DESIGN.md, TODOS.md 등) 자동 보존.
- 소비자 적용: `bash repo/bin/template-upgrade.sh --check` → `--dry-run --diff` → `--apply` (3 명령어 quickstart).
- frontmatter 가 있는 정책 docs 만 영향 (frontmatter 없는 README/CLAUDE/TEMPLATE_CHANGELOG 는 skip).

### Deferred to v4.0.0-rc.1

- §번호 재배치 (§12 ↔ §13 swap, §18 → §17~§21 분리) — BREAKING
- `lib/path-rewrite.sh` — §rebalance 구현용 (현재 caller 부재)
- 추가 frontmatter fields (`reads_first`, `references`, `token_budget`)
- `_template_meta/` 디렉토리 메커니즘 (현재는 deferral, 필요성 입증 후 검토)

### Deferred to v3.7.0+

- `--strategy=merge` opt-in (option C 3-way merge) — base fixture 신뢰성 확보 후 도입

### References

- Plan: `/root/.claude/plans/template-v3.6.0-plan.md`
- Source `/autoplan` session: `/root/.claude/plans/template-version-sync-plan.md` (Decision Audit Trail 1~34)
- Maintainer cycle: `_template_maintainer/HISTORY.md` META-CYCLE-003

### Next

`v4.0.0-rc.1` (BREAKING — §rebalance + frontmatter 확장) — 소비자 ≥ 2 개에서 v3.6.0 흡수 성공 + 1~2주 bake 후 trigger. 사용자 directed `/_template:version-upgrade --apply` 호출 시 `bin/template-bake-check.sh` 자동 호출 (5-항목 점검). Plan: `/root/.claude/plans/template-v4.0.0-rc.1-plan.md`.

---

## v3.5.1 — 2026-04-30 (frontmatter drift repair + maintainer history 이관)

### Summary

v3.0 ~ v3.4 의 누적 변경이 commit 되어 왔지만 `AGENTS.md` frontmatter 의
`template_version` 은 v3.0.0 으로 정체된 상태였다. 본 release 는 그 drift 를
**v3.5.1** 로 정정하고, 동시에 `repo/meta/` 에 섞여있던 template 자체 evolution
이력 (META-CYCLE-001 / -002 + 10 review artifacts) 을 `repo/_template_maintainer/`
로 이관한다 — 소비자 프로젝트 배포 시 메인테이너 이력이 섞이는 문제 제거.

본 release 는 NON-BREAKING. v3.6.0 (migration infra) 의 base. 두 변경 모두
`/autoplan` 2026-04-30 session 결과로 결정된 split release 의 첫 단계.

### Changed

- `AGENTS.md` frontmatter `template_version: v3.0.0` → `v3.5.1` (drift repair).
- `repo/_template_maintainer/` 신설 — `README.md` (정책) + `HISTORY.md`
  (META-CYCLE-001/002 + v0.2 backlog) + `REVIEW_INDEX.md` (REV-20260430-0001~0010)
  + `reviews/` (10 review artifacts 이관).
- `repo/meta/TASK.md` / `repo/meta/REVIEW.md` 소비자 영역 skeleton 으로 reset
  (frontmatter + 사용 가이드 주석만 보존).
- `repo/.gitignore` — review-panel transient state (`meta/.review-lock`,
  `meta/reviews/.state-*`, `_template_maintainer/...`) 추가.

### Compatibility

- 호환 유지. §번호 변경 0건. 다른 정책 docs frontmatter 변경 0건.
- `bin/verify-completion.sh` 의 `is_meta_path` 함수는 v3.6.0 에서 갱신 (현재는
  `repo/meta/**` 만 META path 로 인식 — `_template_maintainer/**` 는 maintainer
  자체 영역이라 META cycle 검증 대상 아님).
- 소비자 프로젝트 영향: 본 release 흡수 시 `repo/meta/` 내 자체 customization 이
  있다면 `_template_maintainer/` 로 무관하게 그대로 유지됨 (영역 분리).

### References

- Plan: `/root/.claude/plans/template-v3.5.1-plan.md`
- Source `/autoplan` session: `/root/.claude/plans/template-version-sync-plan.md`
  (Decision Audit Trail #1, #18, AD-2 PRE-2)
- Maintainer archive: `repo/_template_maintainer/HISTORY.md`

### Next

`v3.6.0` (migration infrastructure non-BREAKING) — `/_template:version-upgrade`
SKILL + `bin/template-upgrade.sh` + 6 incremental hops + bats fixtures + option
B customization. Plan: `/root/.claude/plans/template-v3.6.0-plan.md`.

---

## v3.5.0-rc.1 — 2026-04-30 (정책문서 중복 제거 — Wave 1~3, 호환 유지)

### Summary
v3.0 ~ v3.4 진화 과정에서 같은 규칙이 3~5곳에 흩어진 패턴을 단일 source of
truth + 참조 stub 으로 정리. **§번호 변경 없음** — 호환 유지. 별도 plan
(`/root/.claude/plans/template-version-sync-plan.md`) 의 v4.0.0 BREAKING (§번호
재배치 + frontmatter 재설계 + 마이그레이션 인프라) 에 대한 선행 정리.

### Changed (Wave 1 — D2/D3/D4/D5)
- `AGENTS.md §14` — 환경변수 본문 9줄 → 3줄. 표준은 `docs/CONVENTIONS.md §8`
  참조로 단일화.
- `docs/CONVENTIONS.md §3` — 추적성 식별자 표 삭제 → `AGENTS.md §6` 참조.
  CONVENTIONS 측 표는 LRN 식별자 누락 약식이라 정본 지위 약했음.
- `shared/README.md` — 거버넌스/소유권 본문 9줄 → 2줄 참조. 정본은 `AGENTS.md
  §17`.
- `CONTRIBUTING.md §2.1` — 병렬 AI 격리 수준 표 → `AGENTS.md §13.2 / §16.4`
  참조 한 단락. CONTRIBUTING 은 인간 contributor high-level guide 로 한정.
- `README.md` — "문서 역할 구분" 3줄 제거 (AGENTS §5 정본).

### Changed (Wave 2 — D1/D6/D7/D8)
- `docs/PROJECT.md §7` — 제목 "우선순위" → "**가치 우선순위 (Trade-off Order)**"
  rename. AGENTS §3.1 (문서 위계) 와 명칭 충돌 해소. 본문에 의미 차이 주석 추가.
- `docs/ARCHITECTURE.md §5` — source-of-truth 매핑 7줄 → 1줄 (AGENTS §5 참조).
- `docs/CONVENTIONS.md §2` — 현재상태/이력 분류 → AGENTS §5 참조 단축. yaml
  frontmatter 예시는 유지.
- `CONTRIBUTING.md §4` — PR 체크리스트 도입에 AGENTS §5 참조 한 줄 추가
  (체크박스 자체는 유지).
- `docs/SECURITY.md §3` — 제목 "승인 필요 변경" → "**보안 도메인 특화 승인
  항목**" rename. 일반 승인 정책은 AGENTS §12 참조 한 줄 추가.

### Changed (Wave 3 — D9/D10)
- `README.md` — Source of Truth 표 형식으로 재작성. 기능 생성 규칙은
  `playbooks/PB-0001-new-feature-unit.md` 참조로 단축. CONTRIBUTING.md 항목 추가.
- `CONTRIBUTING.md §1.1` — AI 워크플로 6단계 → AGENTS §7/§10/§16 참조 한 단락.
  CONTRIBUTING 은 사람 contributor 워크플로 + PR 체크리스트 + 금지사항만 정의.

### Stats
- 8 파일 변경, +39 / -72 = **-33줄**
- AGENTS.md: 1111 → 1104, CONTRIBUTING.md: 102 → 91, README.md: 21 → 18,
  shared/README.md: 24 → 18, ARCH: 114 → 108, CONV: 197 → 191, PROJ: 125 → 129
  (+rename), SEC: 45 → 47 (+도입 한 줄)

### Notes
- §번호 변경 없음 — 소비자 프로젝트의 cross-reference 모두 그대로 유효.
  - 6개 소비자 + aws_data_manage 의 §번호 인용 grep 결과 깨진 reference 0건.
- v3.4.0-rc.1 의 Verification Subagent Panel 시스템을 첫 사용 사례 후보. META
  cycle: `Meta-Cycle: policy-doc-consolidation-2026-04-30`.
- 다음 단계: 별도 plan 의 v4.0.0 (Wave 4 §번호 재배치 + Wave 5 마이그레이션
  인프라) — 별도 세션에서 `/root/.claude/plans/template-version-sync-plan.md`
  진입 프롬프트로 시작.

## v3.4.0-rc.1 — 2026-04-28 (AI Verification Subagent Panel v0.1.5)

### Summary
multi-domain audit이 single-perspective AI 작업 직후 main session에 병렬 dispatch
되도록 하는 **AI Verification Subagent Panel** 도입. operational evidence
(transcripts ef46fb33, f046308b)에서 catch된 사용자 사후 누락 패턴을
구조적으로 닫기 위한 변경.

### Added
- `repo/.claude/agents/{ux,security,design,backend,qa}-reviewer.md` — 5 subagent
  pool. frontmatter `model:`/`tools:` 필드 없음 (bundle-only contract, §18.11).
- `repo/.claude/commands/review-panel.md` — `/review-panel` slash command.
  project-scope only (T2A). 8-step flow + §18.11 contract injection 명시.
  사용자 실행 전용이 아니라 AI 작업자가 완료 전 수행하는 verification protocol의
  Claude Code entrypoint.
- `repo/bin/review-md-append-from-subagent-output.sh` — strict 4-section + 4
  required fields validator. `--scope feature:<id> | project-meta |
  feature-meta:<id>` flag(R7 P1-1) + atomic flock + duplicate header detection.
- `repo/bin/run-review-panel.sh` — pre/post wrapper. SKIP filter (정책 doc 분기,
  line-count 무관), word-count proxy WARN, `--rejected <agent>:<reason>` flag
  (R7 P1-2), 영어 keyword + 한국어 명사 병기 stderr summary.
- `repo/bin/tests/{review_md_append,run_review_panel}.bats` — fixture 기반 unit
  tests.
- `repo/meta/REVIEW.md` + `repo/meta/TASK.md` — project-wide META index와
  v0.2 backlog 10항목 + META cycle definition.
- `repo/.claude/settings.json` — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
  (Agent Team escalation 옵션 보존).
- `repo/docs/REQUEST.md` + `repo/docs/REQUEST_ARCHIVE.md` — §19 Request-Form
  Protocol skeleton.

### Changed
- `repo/AGENTS.md`:
  - §18.4 — pure-meta commit이 모든 검사 skip하던 정책 갱신 → check #1~#8 skip
    + check #9 적용. META skip 정책의 단일 예외(R5 #9).
  - §18.5 — META cycle 경계 정의 추가. `Meta-Cycle: <id>` trailer 또는
    `meta/TASK.md` / `unit/<id>/meta/TASK.md` 첫 수정 commit 중 나중(R7 P1-3).
  - §18.8 — Verification Subagent Dispatch Policy 신설 (영어 + 한국어 명사
    병기 dispatch 표).
  - §18.9 — REVIEW.md Subagent Index + Artifact Schema 신설 (4 entry types:
    `[SUBAGENT:*]` / `[AGENT-TEAM:*]` / `[SKIPPED:*]` / `[REJECTED:*]`,
    R6 #3). `[REJECTED:*]`는 diagnostic trace이며 check #9 완료 증거로 계산하지
    않음.
  - §18.10 — Meta TASK Convention 신설 (project-wide vs feature-bound 분기).
  - §18.10.1 — META mode REVIEW location 신설 (path convention 자동 분기).
  - §18.11 — Subagent invocation contract 신설 (changed_files / diff_excerpt /
    task_md_content / acceptance_criteria 4-field bundle injection).
- `repo/bin/verify-completion.sh`:
  - check #9 (REVIEW.md cycle entry) 추가 — accepted
    `[SUBAGENT|AGENT-TEAM|SKIPPED]:*` 중 ≥ 1이 cycle 안에 있어야 PASS.
    `[REJECTED:*]` 단독 trace는 FAIL.
  - META mode early exit를 conditional하게 변경 — pure-meta changeset에서도
    check #9는 실행 (§18.4 단일 예외).
  - Stale `§17` 주석 참조 → `§18` 정정 (R7 P3-7).
  - Pilot check count 6 → 7로 갱신.
- `repo/unit/_template/docs/REVIEW.md` skeleton — 실제/예시 REV entry 제거.
  copy-base 오염 방지를 위해 schema 설명은 AGENTS.md §18.9로 위임.
- `repo/unit/_template/docs/ANCHOR.md` skeleton — stale `§17` 주석 참조 →
  `§18` 정정 (R7 P3-7). §4 human 검증은 일반 TASK cycle gate가 아니라
  release/milestone 또는 방향 전환 검증 시점에만 요구.
- `repo/docs/STATUS.md` — `review` 상태값 추가.
- `repo/docs/CODEBASE_MAP.md` — REQUEST / REQUEST_ARCHIVE skeleton 반영.
- `repo/playbooks/PB-0001-new-feature-unit.md` — `_template` REVIEW 이력 복사
  금지 validation 추가.
- `repo/.gitignore` — `.context/` AI runtime state 제외.

### Notes
- v0.1 hard-gate는 `verify-completion.sh check #9` 한 곳뿐. Stop hook
  hard-gate(Path B)는 v0.2 후보 (1주 pilot 후 정성·정량 데이터 수집 후 결정).
- subagent prompt 본문 변경 가능성 낮으므로 `_base.md.tmpl` + `render-agents.sh`
  DRY 도구는 v0.2 backlog (`meta/TASK.md` B-5).
- token-budget proxy ceiling (3x baseline / absolute 6500 words) 칼리브레이션은
  1주 pilot data로 (`meta/TASK.md` B-10).

### Migration
- 기존 feature는 구조 변경 없음. 단 완료 선언 전 AI 작업자가 verification panel
  protocol을 수행해야 하며, `/review-panel`은 그 Claude Code entrypoint다.
- 비정책 doc-only cycle은 `[SKIPPED:non-policy-doc]` trace로 통과 가능하다.
- all-reject cycle은 `[REJECTED:all-subagents]` diagnostic trace를 남기지만 check
  #9를 통과하지 않는다. AI는 prompt/context/artifact를 보정해 panel을 다시 실행해야
  한다.
- META cycle 진입 시 `Meta-Cycle: <slug>` trailer를 commit message에 추가하면
  cycle scope가 명시 추적된다 (선택).

### Self-verification panel pilot

본 release 자체에 대해 verification panel 을 release-QA 로 실행했다 (project-meta
scope, full panel: ux / security / design / backend / qa, dispatch trigger
`META policy-doc + code change full panel`). 5/5 BLOCK verdict + panel 실행이 자체
발견한 validator 결함 2 건. 정리:

#### Absorbed in this release

panel 실행 자체가 막히거나 audit-log 무결성에 직접 영향을 주는 결함을 본 release
산출물에 흡수.

- **validator quartet inverted 로직** (`bin/review-md-append-from-subagent-output.sh`
  L385): 완료된 quartet 후 새 Evidence 가 도착하면 `quartet_complete -ne 0` 가
  reject 를 발화시킴 (의도는 미완료 quartet 검출). `-eq 0` 로 정정. multi-finding
  §1/§2 가 거부되던 결함.
- **validator `head -1` SIGPIPE under `set -o pipefail`** (`...-output.sh` L498-504):
  큰 `S1_BODY` 에서 head 가 stdin 을 일찍 닫아 upstream printf 가 SIGPIPE → exit 141.
  `awk 'NF { print; exit }'` here-string 패턴으로 교체.
- **TRIGGER 제어문자 audit-log 위조 방어** (`...-output.sh` L126-135): `--trigger`
  값이 newline / CR / tab 포함 시 die. REVIEW.md `## REV-...` index header 를
  외부에서 forge 하는 경로 차단. `case "$TRIGGER" in *$'\n'*|*$'\r'*|*$'\t'*)`
  bash native pattern.
- **bats coverage**: `bin/tests/review_md_append.bats` 14 → 16. multi-finding §1
  quartet acceptance + TRIGGER 제어문자 reject.

#### Will follow-up (positive — 후속 cycle 적용 권장)

차후 적용이 권장되거나 적용 위험이 낮고 동작 개선이 명시적인 항목.

- **stderr summary verdict distribution** (ux): `bin/run-review-panel.sh` post-hook
  summary 에 `- verdicts / 판정: <P> PASS / <C> CONCERN / <B> BLOCK` 라인 + BLOCK
  list 추가. artifact 를 열기 전 verdict tally 즉시 가시.
- **REVIEW.md schema 가시성 promotion** (ux + design): HTML 주석 안의 schema 를
  가시 `## Schema` 섹션으로 promote. operational + meta skeleton voice 통일 (양쪽
  동일한 4-line 치트시트).
- **check #9 hint path 분기 안내** (ux): `bin/verify-completion.sh check_9_review_entry`
  FAIL hint 에 §18.10.1 path 분기 (META → `meta/REVIEW.md` / feature →
  `unit/<id>/docs/REVIEW.md`) inline 명시.
- **§18.8 dispatch 표 quick-decision rule** (ux + design): 표 위에 1-line 규칙 +
  bulletized 5-line domain summary 로 routing 비용 감소.
- **§18.10.1 → §18.11 numbering 재정렬** (design): REVIEW location 은 TASK
  convention 의 sub 가 아닌 peer. 기존 §18.11 → §18.12 로 이동. 모든 cross-ref
  (script doc string 포함) 정정.
- **§18.8 dispatch rule 중첩 해소** (design): "0 keyword + code → full" 와
  "0+cross ≥2 → full" 단일 행으로 통합 + precedence ("first match wins") 명시.
- **subagent `tools:` whitelist** (security): `.claude/agents/*-reviewer.md`
  frontmatter 에 `tools: []` (또는 `tools: [Read]`) 추가. bundle-only contract 를
  prose 에서 structural 로 격상.
- **bypass env var policy freeze** (security): AGENTS.md §18.4 SPOF 단락에 "future
  enforcement layer (Stop hook, pre-commit, CI gate) MUST NOT introduce bypass
  env var" invariant 추가. B-2 도입 시점에 frozen.
- **`mktemp` cross-fs atomicity** (security + backend): wrapper / validator 의
  `tmp=$(mktemp)` → `mktemp -p "$(dirname "$REVIEW_MD")"` + EXIT trap rm.
  tmpfs `/tmp` 환경 (CI runner 등) 에서 `mv` rename atomic 보장.
- **bold/fenced header reject test** (qa): schema 변형 (`**### 1. ...**`,
  fenced header) reject 케이스 lock.
- **inverse-CONCERN consistency test** (qa): CONCERN 인데 §1 + §2 둘 다
  `(no findings)` 인 케이스 거동 lock (현재 validator 는 accept — 의도 결정 후
  reject 로 fix 시 함께 작업).
- **whitespace `(no findings)` test** (qa): `(no findings)` 뒤 trailing
  whitespace / 빈 줄 케이스 거동 lock.
- **META-mode missing-entry actionable summary test** (qa): pure-meta + REVIEW.md
  entry 부재 → check #9 FAIL message 가 §18.10.1 분기 가이드를 포함하는지 assert.

#### Will not follow-up (negative — 본 release line 보류)

운영 위험 / 환경 제한 / 중복 / scope 확장으로 본 release line 보류.

- **feature-id regex injection allowlist** (security + backend): 현 naming
  (`feature-NNNN-name`) 이 regex-safe 라 latent. allowlist regex 추가는 향후
  naming 확장 유연성을 좁힌다. 환경 제한.
- **`flock` fallback explicit die** (backend): `meta/TASK.md` v0.2 backlog **B-7
  Multi-user concurrent shells flock 보강** 와 중복.
- **Lock symlink race + umask 077** (security): multi-tenant box (CI / 공유 dev
  VM) 가정. v0.1 single-user pilot 운영 가치 낮음. B-7 와 묶어 multi-user 도입
  시점에 평가.
- **`.gitignore` `**/.context/` 변경** (security): root-only vs nested 는 사용자
  design choice 영역. nested glob 도입은 의도적인 unit/<id>/.context commit case
  를 차단할 수 있음.
- **bash → Python/Go 재작성** (backend challenge): 대규모 refactor. 안정성 회귀
  위험, 의존성 증가, 운영 위험 큼.
- **slash command vs proactive worker UX 완전 분리** (ux challenge): 추상 분리,
  작업 분량 큼, 효과 불확실. pilot 데이터로 dominant case 검증 후 결정.
- **validator 자동 verdict 결정 (artifact verdict 필드 폐기)** (qa challenge):
  schema 의미 변경, consumer 호환 영향. multi-cycle 학습 후.
- **acceptance_criteria 기반 dispatch** (design challenge): TASK.md 작성 부담
  증가, 운영 prerequisite 변경. v0.2 retro 에서 dispatch 정확도 데이터로 결정.
- **input-side trust collapse 일반화 hardening** (security challenge): TRIGGER
  외 모든 caller-input sanitization. scope 확장 큼. v0.2 adversarial input pilot
  과 함께 평가.
- **REVIEW.md visual hierarchy 재포맷 (TL;DR + `<details>` collapse)** (design +
  ux): 기존 entry format 호환성 영향. 누적 시 가시성 문제는 v0.1 pilot 데이터로
  우선 검증.
- **flock concurrency bats test** (qa): 백그라운드 프로세스 race 시뮬레이션 +
  flock 미설치 skip 처리 복잡성. B-7 와 묶어 처리.
- **rejected artifact `/tmp` cleanup contract test** (qa): cleanup contract 자체가
  미정 (keep / delete / move-to-`.review-rejected`). 정책 결정 선행 필요.
- **`--rejected` reason padding edge-case test** (qa): marginal coverage value,
  현재 padding 로직 단순. 우선순위 낮음.

### Related artifacts
- Design v0.1.5: `~/.gstack/projects/ai_delegated_dev_template/root-main-design-20260427-153426.md`
- Test plan v0.1.5: `~/.gstack/projects/ai_delegated_dev_template/root-main-eng-review-test-plan-20260427-180645.md`
- Final checkpoint: `~/.gstack/projects/ai_delegated_dev_template/checkpoints/20260428-133322-v0.1.5-day-0-ready-R7-deferred.md`
- 7 review rounds 누적: 88 findings touched (R1 9 + R2 8 + R3 17 + R4 14 +
  R5 13 + R6 9 + R7 9), 79 흡수 + 9 deferred-to-implementation (R7 — 모두 본
  Day-0 commit에 자연 결정됨).

---

## v3.3.1-rc.1 — 2026-04-30 (Bootstrap entry persona 도입 — pilot 예정)

**Status: Release Candidate.** Pilot 검증 후 v3.3.1 또는 v3.4.0 으로 확정된다.
신규 세션 진입 시 정책·메타 문서가 우회되는 이슈를 명시 호출 가능한 skill 로 흡수.

### 도입 배경

v3.3.0-rc.1 에서 `_template/` persona 가 §19 Request-Form 계층을 채웠지만, **세션 진입 직전** 단계 — 즉 사용자가 새 세션을 열고 첫 요청을 던지는 시점 — 의 정책 prime 은 여전히 사용자의 수동 입력 ("정책 문서를 면밀히 검토한 뒤 …") 에 의존했다.

실측 패턴 (`/root/.claude/projects/-root-download-docker-mysql-ai-delegated-dev/*.jsonl` 다수 세션 첫 turn 분석):
- 대부분의 첫 user message 가 정책 prime 명령으로 시작
- 명령이 빠진 세션에서는 AI 가 `FIRST_REQUEST.md` / `repo/AGENTS.md` 를 우회하고 곧바로 작업 진입
- 정책 우회 → ANCHOR Conflict Protocol (§18.3), Plan-Review-Execute (§7.1), §10.5 conditional rules, Risk grade (§12.3) 모두 빈약하게 적용

v3.3.1 은 이 entry barrier 를 단일 명시 호출 (`/_template:entry <문장>`) 로 격상시킨다.

### Module A: `_template/entry.md` (신규 persona)

- 경로: `repo/.claude/commands/_template/entry.md` (기존 `_template/` git submodule 안)
- 호출 형식: `/_template:entry <실제 요청 문장>` (arg-given) 또는 `/_template:entry` (no-arg)
- 분류: **Read-only bootstrap adapter** — `worker-*` 가 아니다. §19.2 의 두 mode (조립 / 조립+실행) 어디에도 속하지 않는 entry adapter.
- `allowed-tools: Read, Bash, Glob, Grep` — `Write` / `Edit` / `Agent` 미허용으로 read-only 를 tool-level 에서 강제.

### Module A: 6-phase 흐름

1. **Phase 1 환경 감지** — `repo/AGENTS.md` 위치로 `policy_root` 결정, 못 찾으면 fail-loud. branch / head / template_version / last changelog entry 수집.
2. **Phase 2 Bootstrap Read** — AGENTS.md §3.1 우선순위 + §10.1 / §10.2 / §18.10 매핑된 13 row 표 순서로 Read. 미존재 / 실패 행은 explicit `(skipped: <이유>)` 로 briefing 에 기록 (암묵적 skip 금지).
3. **Phase 3 요청 분류** (arg-given 시) — Scope 추정, §18.8 dispatch hint, §10.5 conditional rules, §12.3 risk grade hint, §7.1 Plan-Review-Execute likelihood. 추가 Read 는 trigger 충족 시에만 (LEARNINGS, feature docs, shared/docs 등).
4. **Phase 4 ANCHOR Conflict Check** — Phase 3 에서 feature 식별 시 §18.3 명시 충돌만 검사 (자연 drift 는 §18.3 본 protocol 책임). 24h grace (§18.7) 인식.
5. **Phase 5 Briefing** — 7 section 출력 (Repository / Loaded docs / Active feature / Conflicts / Request triage / Persona·playbook 후보 / Handoff). VSCode markdown 링크 형식.
6. **Phase 6 종료** — auto-invoke 금지, main session 다음 turn 으로 인계.

### Module A: 안전·경계 정책

- **`repo/docs`, `repo/meta` 무수정** — entry 도입 자체가 정책 본문을 손대지 않는 것을 정의로 한다.
- **자동 작업 진입 금지** — Phase 5 이후 본 skill 안에서 코드 변경·테스트·subagent 발화를 하지 않는다. main session 이 다음 turn 에서 받아 처리.
- **§16.3 / §18 / §19 우회 금지** — entry 는 정본을 prime 할 뿐 정책을 대체하지 않는다.
- **Pain-response 아님** — pain 호소는 §16.3 (`verify-completion.sh`) / §18 (Conflict Protocol) / §19 (Request-Form persona) 의 책임. entry 는 adapter 다.
- **자동 chain 금지** — 다른 persona / playbook / agent 호출은 권유만 한다.
- **Re-anchor 모드** — stateless · idempotent. 세션 중간 호출도 안전 (briefing §1 위에 항상 re-anchor 1줄 출력). "첫 호출 / 중간 호출" 자동 판정 안 함 — 휴리스틱이 fragile 하기 때문.

### 운영 의미

- **§18 (외부 앵커)**: 방향성 재앵커 — 기존 (gstack 연동)
- **§19 (요청 조립)**: 기능 단위 form 조립 — 기존 (`_template/` 3 persona)
- **entry adapter**: **세션 진입 직전** 의 정책 prime — 신규
- 세 layer 는 독립 — entry 는 §19 mode 분류에 들지 않으며 §18 의 substitute 도 아니다.

### Pilot 범위 및 검증 계획

`mysql_ai_delegated_dev` 1 프로젝트. 이번 pilot 에서 검증할 것:

1. arg-given 모드 — Phase 1~6 정상 진행 + Phase 5 briefing 7 section 모두 생성
2. no-arg 모드 — Phase 3 / Phase 4 / Phase 5 §5 skip + 마지막 줄 user prompt 출력
3. 세션 중간 호출 — re-anchor 라인 출력 + read-only 보존 (working tree 무변경)
4. fail-loud — `repo/AGENTS.md` 부재 환경에서 실제 fail 메시지 출력
5. §18.8 dispatch hint — 5 도메인 키워드 (auth / schema / UI / API / performance) 각 1회 정확히 매칭

타 프로젝트는 v3.3.1 확정 이후 migration (submodule update 만으로 자동 전파).

### 마이그레이션 가이드 (v3.3.0-rc.1 → v3.3.1-rc.1)

소비자 프로젝트 적용 순서:

```bash
# 1. _template/ submodule 갱신 (entry.md 가 자동 포함됨)
cd <project>/repo
git submodule update --remote .claude/commands/_template

# 2. 신규 세션에서 호출 시험
# /_template:entry 정책 prime 시험
# /_template:entry <간단한 요청 문장> 정합 진입 시험

# 3. 기존 수동 prime 패턴을 점진적으로 entry 호출로 대체
```

추가 hook 설치 / `verify-completion.sh` 변경 / `bin/` 변경 없음.

### 알려진 한계 (정직한 기록)

1. **자동 호출 강제 부재** — entry 는 명시 호출 skill 이다. 사용자가 호출을 잊으면 여전히 우회 발생. v0.2 에서 SessionStart hook 자동 등록 검토 (Path B 형태, `bin/install-hooks.sh` 와 일관).
2. **Phase 2 Read 비용** — 13 row 모두 Read 시 토큰 소비. 작은 정책 docs (각 <10K) 라 실질 영향은 작지만, 매우 큰 프로젝트에서는 사이즈 평가 필요.
3. **§18.8 dispatch hint 정확도** — Phase 3.2 의 키워드 매칭은 휴리스틱. main session 의 `/review-panel` 실제 dispatch 와 차이 있을 수 있음 — entry 는 hint 만 제공한다고 명시.
4. **fail-loud 외 자동 복구 없음** — `repo/AGENTS.md` 가 없는 비-템플릿 디렉토리에서 호출 시 실패. 의도된 설계 (project-agnostic 보호).

### 후행 작업 (v3.3.1 확정 이후)

- v0.2: SessionStart hook 자동 발화 검토 (precision ≥ 80% 후 hard-gate, B-2 형태와 일관)
- v0.2: §10.5 conditional rules 실 매칭 정확도 데이터 수집 후 rule 자체 보강
- v0.2: Phase 2 Read 캐싱 옵션 (대형 프로젝트 대응)

### 산출 위치

- 신규 파일: `repo/.claude/commands/_template/entry.md` (submodule 안)
- 변경 기록: 본 `TEMPLATE_CHANGELOG.md` (git 외부, 최상위)
- `repo/docs/**`, `repo/meta/**`, `repo/AGENTS.md`, `bin/**` **미변경** — 정의대로.

---

## v3.3.0-rc.1 — 2026-04-25 (Request-Form Persona Pack 도입 — pilot 예정)

**Status: Release Candidate.** Pilot 검증 후 v3.3.0 또는 v4.0.0 으로 확정된다.
`mysql_ai_delegated_dev` 의 feature 단위 요청 조립·실행에 적용.

### 도입 배경

v3.2.0-rc.1 은 ANCHOR.md (외부 앵커) 로 **방향성** 의 외부 검증 지점을 확보했다.
그러나 개별 기능 요청이 AI 작업에 투입되기 **전 단계** 에서 요청의 형태를 다듬는
구조화된 프로토콜은 여전히 비공식이었다. v3.3.0 은 이 공백을 `Request-Form Persona`
메커니즘으로 채운다.

### Module A: Template Persona Pack

- 신규 디렉토리: `repo/.claude/commands/_template/` (git submodule)
- Submodule URL: `git@github.com:msmckimgpt-tech/ai-delegated-dev-template-personas.git`
- 초기 3 persona:
  - `persona-new` — project-owned persona 생성 factory
  - `observability` — §Observability section 조립 (조립-only)
  - `test-strategy` — §Test Contract section 조립 (조립-only)
- 설계 원칙: **project-agnostic** (scope 등 project 특화는 `_persona/` 가 담당).
- `boundary` persona 는 독립성 원칙 위반으로 v2 보류 (artifacts/persona-skill-design/boundary-draft.md).

### Module B: Project-owned Persona (factory 검증)

- `repo/.claude/commands/_persona/` — project-owned, template submodule update 와 무관.
- 첫 사례: pilot 의 `worker-design` (pilot 라이브 Q&A 로 생성, factory 동작 검증).

### Module C: REQUEST.md (신규 project-level 문서)

- `repo/docs/REQUEST.md` — Active 요청 로그. append-only.
- `repo/docs/REQUEST_ARCHIVE.md` — 완료·폐기 요청 로그. append-only.
- AGENTS.md §3.1 우선순위 **8번** 에 위치 (기존 playbooks 는 9번으로 이동).
- Entry 구조: `REQ-YYYYMMDD-NNNN <slug>` + frontmatter + §Section(s) + `### Outcome` block
  (`status: in-progress | completed | abandoned` / `completed_at` / `consumed_by`).

### Module D: AGENTS.md §19 Request-Form Protocol (신규 섹션)

§18 (외부 앵커) 와 구분된 신규 섹션:
- §19.1 목적
- §19.2 Persona 호출 (조립 + 실행 2 mode, `worker-*` prefix)
- §19.3 REQUEST 문서 거버넌스 (active / archive 분리)
- §19.4 Entry 구조
- §19.5 Archive move protocol (atomic commit 권장)
- §19.6 Persona 분업 원칙 (자기 section + in-context 합성 + 자동 chain 금지)
- §19.7 Scope 원칙 (project-agnostic / `_persona/` 경계)
- §19.8 Pain-response 책임 구분 (§16.3/§18 과 명시 구분)

### Module E: bin/persona-install.sh + bats

- `bin/persona-install.sh` — submodule 기반 자동 설치, `--check`, `--help`, idempotent
- `bin/tests/persona_install.bats` — 13 test cases (모두 pass). 기존 `anchor_migrate.bats` no regression.
- 기존 `bin/install-hooks.sh` / `bin/anchor-migrate.sh` 의 voice/style 미러링

### 운영 의미

- **§18 (외부 앵커)**: 프로젝트 방향성 재앵커 → gstack skill 연동 (기존)
- **§19 (요청 조립)**: 기능 단위 요청 form + 실행 → template persona 연동 (신규)
- 두 layer 는 독립. 용도 겹치지 않음.
- Pain-response 책임은 §16.3 (`verify-completion.sh`) / §18 (ANCHOR Conflict Protocol) 에 유지 — §19 의 책임이 아님.

### Pilot 범위 및 검증 계획

`mysql_ai_delegated_dev` 1 프로젝트. 이번 pilot 에서 검증할 것:

1. Factory 가 project-owned persona 를 실제 생성 가능한가 — **통과** (worker-design 생성 성공)
2. 조립-only persona 가 REQUEST.md 에 entry 를 올바르게 append 하는가 — **실사용 대기**
3. Worker-class persona 가 실행 승인 게이트를 올바르게 따르는가 — **실사용 대기**
4. Archive move protocol 이 데이터 손실 없이 작동하는가 — **실사용 대기**

타 프로젝트는 v3.3.0 확정 이후 migration.

### 내부 개발 이력

- Pilot mining (25 쌍 vague→concrete from 6 features + 63 commits + 11 sessions)
- 독립성 원칙 확정 (boundary v1 reject + 3 skill 자립형 재설계)
- gstack `design-review` 패턴 참조 (Identity hard-wire / Confusion Protocol / UX Principles 내장 / 0-10 Rating / mode routing / dialog-adaptive Phase 2)
- 9 refinements 일괄 반영 (correlation-key / silent-hang / config-flag degradation / diagnostic metadata / (e) 실행 모드 / Identity 필수화 / `worker-*` convention / REQUEST 분리 + Outcome.status + archive move)

산출물 보관: `artifacts/persona-skill-design/` (mining_raw, contract, sanity_check_observability, sanity_check_test_strategy, boundary-draft, worker-design-v2) — git 외부.

---

## v3.2.0-rc.1 — 2026-04-24 (외부 앵커 구조 도입 — pilot 예정)

**Status: Release Candidate.** 본 버전은 pilot 검증 후 v3.2.0 또는 v4.0.0으로 확정된다.
`mysql_ai_delegated_dev`의 진행 중인 1개 기능에 적용하여 1주일 pilot 후 Success Criteria 평가
(설계 문서: `~/.gstack/projects/ai_delegated_dev_template/root-main-design-20260423-235935.md`).

### 도입 배경

v3.1.0까지의 템플릿은 AI-delegated 개발의 **폐쇄 루프 문제**에 노출되어 있었다:
사용자가 TASK.md로 방향 설정 → AI가 구현 → AI가 문서 갱신 → 사용자가 확인 → 반복.
이 루프에 **외부 관점이 끼어드는 구조적 지점이 없다**. 실제 운용 결과 (37MB Claude Code
대화 로그, 16회 수동 context 재주입 ritual, 10% 완료 누락 패턴) 로 검증됨.

v3.2.0은 이를 해결하기 위해 **ANCHOR.md**를 9번째 1급 문서로 도입하고, AI가 완료 선언 전
반드시 호출하는 `bin/verify-completion.sh` gate를 추가한다.

### Module A: ANCHOR.md (외부 앵커 문서)

기능별 `docs/ANCHOR.md` 신설 (§1 외부 관점 / §2 대안 분기 / §3 가정된 사용 시나리오 /
§4 외부 검증 로그). AGENTS.md §18 "외부 앵커 정책" 에서 정책 명시.

**핵심 규칙 (변경 민감 항목):**

- **§4 author 제한 — `source: human:<name>` 만 허용.** AI는 §4 writer가 아니다.
  Self-certification paradox 차단 (eng review 결정 #1).
- **Conflict Protocol.** AI는 사용자 요청을 ANCHOR §1-§3과 교차 검토, 충돌 감지 시
  작업을 시작하지 않고 gstack skill 재앵커를 유도한다.
- **24h bootstrap grace.** 새 ANCHOR.md는 `created_at` 기준 24시간 이내면 §1-§3 빈칸/
  §4 엔트리 부재가 허용된다.
- **Canonical `created_at`.** frontmatter와 git log first-add commit 중 **더 이른 쪽**을
  사용. frontmatter 조작 방지.

### Module B: `bin/verify-completion.sh`

AI가 완료 선언 전 호출하는 AI-invoked verification tool. pre-commit / post-commit 2-mode.
`.git/hooks/post-commit`이 자동으로 post-commit mode를 호출 (AI discipline 의존 제거).

**파일럿 범위 (6 checks):**
- #2 TASK.md checkbox delta
- #3 MODIFY.md new CHG- entry
- #4 FUNCTION.md staged when code staged
- #6 ANCHOR §1-§3 (24h grace 적용)
- #7 ANCHOR §4 quality gate (≥ 200자 body, challenge 필드, source=human 검증)
- #8 unstaged residual

**v1.1 이후:** #1 feature 파일 범위 정밀화, #5 STATUS.md 갱신 검사.

### Module B: `bin/anchor-migrate.sh` (migration day 도구)

1회성 migration 도구. 기존 feature 디렉토리에 ANCHOR.md 스켈레톤 + seed commit
(`Task-Cycle: <feature-id>` trailer) 을 생성하고 post-commit hook을 설치한다.
Idempotent — 재실행 안전. `--dry-run` preview 모드 제공.

### Module B: `bin/install-hooks.sh`

post-commit hook 설치 + **설치 확인 테스트** 포함. eng review에서 발견된 critical gap
(hook silent failure) 대응.

### AGENTS.md 정책 변경

- **§16.1 완료 기준**: ANCHOR.md §1-§3 + §4 조건 추가.
- **§16.2 Completion Checklist**: ANCHOR.md 관련 3개 항목 추가 + `verify-completion.sh` 호출 항목.
- **§16.3 Git 동기화 절차**: rewrite — 기존 Step 1-4 수동 절차를 `verify-completion.sh`
  호출 구조로 치환. Task-Cycle trailer 필수 명시.
- **§17 shared/ 거버넌스**: `shared/docs/` 하위로 MODIFY.md 이동, REPORT.md 신설.
  `--shared` 모드 검증.
- **§18 외부 앵커 정책 (신규)**: ANCHOR.md 정책, §4 human-only, Conflict Protocol,
  운영/메타 층위 구분, TASK Cycle 정의, §4 품질 gate, Bootstrap grace.

### 운영/메타 층위 구조

AGENTS.md §18.4 공식화. §1 AI 전권 위임은 **운영 층위**에만 적용. 메타 층위
(템플릿 설계 자체, AGENTS.md 개정, ANCHOR 스켈레톤 재설계)는 인간이 개입한다.

- **Path convention 자동 감지**: `AGENTS.md`, `_template/**`, `bin/**`,
  `shared/docs/**`, `docs/**`, `unit/META-*/` 편집 시 META 모드.
- **Pure-meta commit**: `verify-completion.sh`가 skip.
- **Mixed commit (META + operational)**: operational로 취급 (gate 우회 방지).
- **`[META]` commit prefix 미지원**: path convention만 유효 (AI self-override 차단).
- **META feature**: `unit/META-NNNN-<name>/` 형식 pre-registered.

### TASK Cycle 단위

cycle = TASK (not commit). commit trailer `Task-Cycle: <feature-id>` 로 범위 명시.
cycle 시작: `Task-Cycle` trailer의 가장 이른 commit 또는 TASK.md first-mod commit 중 나중.
§4 엔트리는 cycle당 ≥ 1 필요.

### 테스트

- `bin/tests/verify_completion.bats` — 26 tests (argparse, META mode, check #2~#8, regression).
- `bin/tests/anchor_migrate.bats` — 10 tests (dry-run, idempotency, hook installation).
- 실행: `bats bin/tests/verify_completion.bats bin/tests/anchor_migrate.bats`
- **Dependencies**: `bats >= 1.8`. Shell script는 `jq` 미사용 (순수 bash + git + awk + grep).

### 마이그레이션 가이드 (v3.1.0 → v3.2.0-rc.1)

소비자 프로젝트(mysql_ai_delegated_dev 등) 적용 순서:

```bash
# 1. 설계대로 pilot 적용 — 가장 작은 진행 중 기능 1개 선정
cd <project>/repo
git checkout -b feat/adopt-anchor-v3.2.0-rc

# 2. 템플릿의 bin/*.sh, unit/_template/docs/ANCHOR.md, AGENTS.md §16-§18 복사

# 3. Migration day 실행
bash bin/anchor-migrate.sh --dry-run   # preview
bash bin/anchor-migrate.sh              # apply

# 4. pilot 기능 ANCHOR.md §1-§3 수동 작성 (24h 이내)

# 5. 1주일 pilot — Success Criteria 평가 (설계 문서 참조)
```

### 알려진 한계 (정직한 기록)

1. **§4 semantic validation 부재**: script는 형식만 검사. 내용의 실질성은 보장 못 함.
   최소 장벽(200자, challenge 필드, human source)만 제공.
2. **N=1 pilot**: 통계적 유의성 없음. 정성 signal 중심 평가.
3. **`[META]` prefix 폐기로 경계 케이스 존재**: shared/docs에 선언적 정책 추가 등은
   path convention 감지의 경계에 있음. pilot에서 검증 필요.

### 후행 작업 (v3.2.0 확정 이후)

- 6개 기존 기능에 ANCHOR.md 소급 적용 (migration day)
- verify-completion.sh 나머지 2개 검사 (#1 feature 범위 정밀화, #5 STATUS.md) → v1.1
- `bin/doctor --sampling` for §4 품질 샘플링 → v2
- §4 trace artifact hash 검증 (self-cert 방어 구조적 보완) → v3

---

## v3.1.0 — 2026-04-13 (감사 기반 보강)

4개 프로젝트(mysql_ai_delegated_dev, mysql_ai_delegated_migrator, xtrabackup, mysqlsh)의 v3.0.0 적용 현황을 감사하여 도출한 보강 항목을 적용.

### PB-0003 강화

`playbooks/PB-0003-feature-completion.md`에 **CODEBASE_MAP.md / LEARNINGS.md 갱신 단계**를 필수 Step으로 추가.
v3.0.0에서 두 문서는 신규로 만들어졌지만 완료 워크플로에 연결되지 않아 실제 프로젝트에서 비어 있는 채로 남는 경향이 관찰됨. PB-0003 Step 6·7로 명시적 갱신 (또는 "변경 없음" 확인)을 요구.

### 신규 Playbook (2개)

| 파일 | 설명 |
|------|------|
| `playbooks/PB-0005-dependency-update.md` | 외부 의존성 업데이트 절차 (버전 bump, 보안 패치, SDK 모델명 갱신) |
| `playbooks/PB-0006-template-migration.md` | 공용 템플릿 버전 업 마이그레이션 절차 (본 템플릿 자체의 후속 버전 대응) |

PB-0006은 본 v3.0.0 마이그레이션 경험을 표준화한 것. 섹션 번호 이동 시 교차 참조 일괄 갱신, 프로젝트 고유 섹션 보존, 기각 항목 ADR 기록 등의 실전 원칙을 포함.

### §10.5 조건부 규칙 예시 확장

`AGENTS.md §10.5`의 주석 예시를 3개 → 7개로 확장 (`*.sh`, `shared/**`, `Makefile`, `artifacts/**` 추가). 프로젝트 초기화 시 최소 3~5개 채울 것을 명시.

### 마이그레이션 가이드 (v3.0.0 → v3.1.0)

1. `playbooks/PB-0003-feature-completion.md` 교체 (템플릿에서 복사).
2. `playbooks/PB-0005-dependency-update.md`, `PB-0006-template-migration.md` 신규 복사.
3. `playbooks/README.md`를 템플릿 기준으로 갱신 (PB-0005, PB-0006 표 행 추가).
4. `AGENTS.md §10.5` 테이블이 비어 있으면 프로젝트 도메인 기반으로 3~5개 이상 채운다.
5. `/repo/docs/DECISIONS.md`에 v3.1.0 마이그레이션 ADR append.
6. `template_version: v3.1.0`으로 갱신.

---

## v3.0.0 — 2026-04-09 (상용 플랫폼 참조 개선)

Cursor, Jules, Devin, Copilot Workspace, Aider, Codex CLI 등 상용 AI 개발 플랫폼을 분석하여
9개 개선 항목을 도출하고 적용. AGENTS.md를 Part A~G 체계로 전면 재구성.

### AGENTS.md 전면 재구성

기존 §1~§20 평면 구조를 §1~§17, 7개 Part로 재편하여 AI 가독성 향상.

| Part | 범위 | 포함 섹션 |
|------|------|----------|
| **A — 기본 원칙** | 목적, 작업 범위, 문서 체계 | §1~§3 |
| **B — 기능 관리** | 기능 생성, 문서 역할, 추적성 | §4~§6 |
| **C — 작업 수행** | PRE 프로토콜, 구현, 불명확성 | §7~§9 |
| **D — 컨텍스트** | 읽기 범위, .aiignore, 조건부 규칙, 학습 | §10~§11 |
| **E — 승인 및 협업** | 승인 등급, 다중 AI, 격리, 에이전트 분리 | §12~§13 |
| **F — 설정** | 환경변수, 도메인 커스터마이징 | §14~§15 |
| **G — 완료 및 Git** | 완료 체크리스트, Git 동기화, 머지 충돌 | §16 |

### 신규 파일 (8개)

| 파일 | 개선 항목 | 설명 |
|------|----------|------|
| `repo/.aiignore` | #2 컨텍스트 제외 | `.gitignore` 문법의 AI 읽기 제외 패턴 |
| `repo/docs/LEARNINGS.md` | #4 AI 학습 메모리 | 카테고리별 학습 기록 (mistake/pattern/quirk/preference) |
| `repo/docs/CODEBASE_MAP.md` | #5 파일 인덱스 | 디렉토리 트리, 진입점, 모듈 인덱스, 외부 인터페이스 |
| `repo/playbooks/README.md` | #3 Playbook | 플레이북 인덱스 |
| `repo/playbooks/PB-0001-new-feature-unit.md` | #3 | 기능 유닛 생성 절차 |
| `repo/playbooks/PB-0002-add-shared-module.md` | #3 | shared 모듈 추가 절차 |
| `repo/playbooks/PB-0003-feature-completion.md` | #3 | 기능 완료 체크 및 Git 동기화 |
| `repo/playbooks/PB-0004-hotfix.md` | #3 | 긴급 수정 절차 |

### 기존 파일 섹션 추가/변경

| 파일 | 변경 내용 | 관련 개선 |
|------|----------|----------|
| `repo/AGENTS.md` | §7.1 Plan-Review-Execute 프로토콜 | #1 계획-검토-실행 |
| `repo/AGENTS.md` | §4.1 Playbook 참조, §5.2 LEARNINGS.md 역할 | #3, #4 |
| `repo/AGENTS.md` | §8.1 개선 제안 정책 | #7 Proactive Suggestions |
| `repo/AGENTS.md` | §10.4 .aiignore 컨텍스트 제외 | #2 .aiignore |
| `repo/AGENTS.md` | §10.5 조건부 규칙 활성화 | #8 Glob 기반 규칙 |
| `repo/AGENTS.md` | §11.2 학습 기록 정책 | #4 AI 학습 메모리 |
| `repo/AGENTS.md` | §13.2 작업 격리 (worktree/sandbox) | #6 Worktree 격리 |
| `repo/AGENTS.md` | §13.3 계획-실행 분리 에이전트 | #9 듀얼 에이전트 |
| `repo/unit/_template/docs/TASK.md` | §2 Implementation Plan 추가, §8 Completion Checklist 확장 | #1 |
| `repo/unit/_template/docs/REPORT.md` | §8 Suggested Improvements | #7 |
| `repo/unit/_template/docs/AGENTS.md` | §8.1 파일 패턴별 추가 규칙 | #8 |
| `repo/CONTRIBUTING.md` | §2.1 병렬 AI 브랜치 전략 | #6 |
| `repo/docs/CONVENTIONS.md` | §7 .aiignore 매핑, §9 용어 6개 추가 | #2, #3, #4, #5 |

### 개선 항목 참조 플랫폼

| # | 개선 항목 | 참조 플랫폼 |
|---|----------|-----------|
| 1 | Plan-Review-Execute 프로토콜 | Jules, Copilot Workspace, Devin |
| 2 | .aiignore 컨텍스트 제외 | Cursor, Aider |
| 3 | Playbook 반복 작업 템플릿 | Devin |
| 4 | AI 학습 메모리 (LEARNINGS.md) | Cursor Memories, Devin Knowledge |
| 5 | Codebase Map (파일 인덱스) | Aider repo-map |
| 6 | Worktree/샌드박스 격리 | Cursor 3, Codex |
| 7 | 개선 제안 (Proactive Suggestions) | Jules Suggested Tasks |
| 8 | Glob 기반 조건부 규칙 활성화 | Cursor .mdc, Windsurf |
| 9 | 계획-실행 분리 에이전트 가이드 | Windsurf, Devin |

### 마이그레이션 가이드 (v2.0.0 → v3.0.0)

**주의: 프로젝트가 이미 커스터마이징한 AGENTS.md는 섹션 번호가 변경되었으므로 주의한다.**

#### 단계 1: 새 파일 복사 (충돌 없음)
- [ ] `repo/.aiignore` 복사 → 프로젝트에 맞게 패턴 조정
- [ ] `repo/docs/LEARNINGS.md` 복사
- [ ] `repo/docs/CODEBASE_MAP.md` 복사 → 프로젝트 구조에 맞게 내용 갱신
- [ ] `repo/playbooks/` 디렉토리 전체 복사

#### 단계 2: AGENTS.md 재구성
- [ ] 기존 AGENTS.md를 백업한다
- [ ] 템플릿의 새 AGENTS.md 구조(Part A~G)를 기반으로 프로젝트 정책을 재배치한다
- [ ] 프로젝트 고유 섹션(도메인 규칙 등)을 새 구조에 맞게 이전한다
- [ ] `template_version: v3.0.0`으로 갱신한다

#### 단계 3: 템플릿 파일 섹션 추가
- [ ] `unit/_template/docs/TASK.md`에 §2 Implementation Plan 추가 (기존 §2~§7 → §3~§8로 번호 조정)
- [ ] `unit/_template/docs/REPORT.md`에 §8 Suggested Improvements 추가
- [ ] `unit/_template/docs/AGENTS.md`에 §8.1 파일 패턴별 추가 규칙 추가
- [ ] 기존 기능 폴더의 해당 문서에도 동일 섹션 추가

#### 단계 4: 프로젝트 공통 문서 갱신
- [ ] `CONTRIBUTING.md`에 §2.1 병렬 AI 브랜치 전략 추가
- [ ] `docs/CONVENTIONS.md` §7에 .aiignore 설명 추가, §9 용어집에 신규 용어 추가

#### 단계 5: 버전 마커 및 기록
- [ ] `repo/AGENTS.md` 프론트매터 `template_version: v3.0.0` 확인
- [ ] 프로젝트 `DECISIONS.md`에 "템플릿 v3.0.0 마이그레이션 적용" ADR 추가

### 적용하지 않는 항목 (이미 v2.0.0 적용 완료 시)
- v2.0.0에서 추가된 파일/섹션 (CONTRIBUTING.md, .env.example, §2.1 Git 루트 경계 등)
- 커밋 메시지 규칙, 설정 파일 주석 표준 (v2.x 패치에서 이미 적용된 경우)

---

## v2.0.0 — 2026-03-30 (실전 피드백 반영)

두 실제 프로젝트(mysql_ai_delegated_dev, xtrabackup)의 운영 경험을 반영한 대규모 개선.

### 새 파일 추가
| 파일 | 설명 |
|------|------|
| `repo/CONTRIBUTING.md` | 기여 워크플로 (AI/사람 기여 절차, 커밋 규칙, PR 체크리스트) |
| `repo/.env.example` | 환경변수 템플릿 (키, 기본값, 설명 관리) |
| `repo/unit/_template/src/README.md` | 소스 코드 레이아웃 설명 + config/ 계층 구조 |
| `repo/unit/_template/tests/README.md` | 테스트 실행 방법 설명 |
| `TEMPLATE_CHANGELOG.md` | 이 문서 — 템플릿 버전 관리 |

### 기존 파일 섹션 추가
| 파일 | 추가 섹션 | 설명 |
|------|----------|------|
| `repo/AGENTS.md` | §2.1 Git 루트 경계 | `.git`은 `/repo` 내에서만 초기화 |
| `repo/AGENTS.md` | §18 환경변수 및 설정 관리 | 설정 계층, .env.example 갱신 규칙 |
| `repo/AGENTS.md` | §19 도메인 커스터마이징 가이드 | 우선순위 로드맵, 절대 금지사항, 품질 게이트 |
| `repo/AGENTS.md` | 최상단 초기화 경고 | 템플릿 복사 직후 초기화 필요성 안내 |
| `repo/docs/CONVENTIONS.md` | §8 환경변수 및 설정 관리 | .env 네이밍, 계층 구조, 변경 추적 |
| `repo/docs/PROJECT.md` | §9 빌드 자동화 | Makefile, docker-compose 등 |
| `repo/docs/PROJECT.md` | §10 CI/CD 및 자동화 | 파이프라인, AI 워크플로 프롬프트 |
| `repo/docs/SECURITY.md` | §4 자격증명 관리 패턴 | credentials/, .gitignore, 0600 권한 |
| `repo/docs/ARCHITECTURE.md` | §8 artifacts 조직 규칙 | 기능별/시점별 격리 구조 |
| `repo/unit/_template/docs/AGENTS.md` | §8~§10 | 도메인 특화 규칙, 환경변수 정책, 절대 금지사항 |

### 기존 파일 수정
| 파일 | 변경 내용 |
|------|----------|
| `repo/.gitignore` | .env, credentials, .ai-runtime, Zone.Identifier 규칙 추가 |
| `FIRST_REQUEST.md` | 시나리오 0 (템플릿 초기화) 체크리스트 추가, Git 경계 경고 |
| `README.md` | 시작 방법을 1단계(초기화)/2단계(진행)로 분리, 파일 구조 갱신 |

### 마이그레이션 가이드 (진행 중인 프로젝트에 적용)

아래는 v1.0.0 기반 프로젝트에 v2.0.0 변경을 적용하는 체크리스트이다.
**주의: 프로젝트가 이미 커스터마이징한 파일은 덮어쓰지 말고 섹션 단위로 병합한다.**

#### 단계 1: 새 파일 복사 (충돌 없음)
- [ ] `repo/CONTRIBUTING.md` 복사 → 프로젝트에 맞게 §2 브랜치 전략, §3 커밋 메시지 규칙 조정
- [ ] `repo/.env.example` 복사 → 프로젝트 환경변수로 교체
- [ ] `repo/unit/_template/src/README.md` 복사
- [ ] `repo/unit/_template/tests/README.md` 복사
- [ ] 기존 기능 폴더(`unit/feature-*/`)에도 `src/README.md`, `tests/README.md` 추가

#### 단계 2: 기존 파일에 섹션 추가 (병합 필요)
- [ ] `repo/AGENTS.md`에 §2.1, §18, §19 추가 (기존 내용 뒤에 붙이되, 번호 충돌 확인)
- [ ] `repo/docs/CONVENTIONS.md`에 §8 환경변수 관리 추가 (기존 용어집 §번호 조정)
- [ ] `repo/docs/PROJECT.md`에 §9 빌드 자동화, §10 CI/CD 추가
- [ ] `repo/docs/SECURITY.md`에 §4 자격증명 관리 패턴 추가 (기존 §4→§5로 번호 조정)
- [ ] `repo/docs/ARCHITECTURE.md`에 §8 artifacts 조직 규칙 추가 (기존 §8→§9로 번호 조정)
- [ ] `repo/unit/_template/docs/AGENTS.md`에 §8~§10 추가
- [ ] 기존 기능 폴더의 `docs/AGENTS.md`에도 §8~§10 추가

#### 단계 3: .gitignore 보강
- [ ] `.env`, `.env.local`, `**/config/credentials/*.cnf`, `.ai-runtime/`, `*:Zone.Identifier` 규칙 추가

#### 단계 4: DECISIONS.md에 마이그레이션 기록
- [ ] 프로젝트 `DECISIONS.md`에 "템플릿 v2.0.0 마이그레이션 적용" ADR 추가

#### 단계 5: 버전 마커 갱신
- [ ] `repo/AGENTS.md` 프론트매터에 `template_version: v2.0.0` 추가

### 적용하지 않는 항목 (신규 프로젝트 전용)
- `FIRST_REQUEST.md`의 시나리오 0 (템플릿 초기화) — 이미 진행 중인 프로젝트에는 불필요
- `TEMPLATE-EXAMPLE` 마커 — 예시 콘텐츠가 이미 삭제된 프로젝트에는 불필요
- `feature-0001-example-hello-service/TEMPLATE-EXAMPLE.md` — 이미 삭제된 경우 불필요

---

## v1.0.0 — 2026-03-26 (초기 구조 + 리뷰 반영)

초기 템플릿 구조 생성 및 AI 리뷰 피드백 반영.

### 포함 내용 (ADR-0001 ~ ADR-0011)
- 현재 상태 / 이력 문서 분리 (rewrite vs append-only)
- AGENTS.md 정본 정책 체계 (§1~§17)
- 충돌 해석 원칙 명확화
- 승인 정책 비동기 블로킹 + 사전 승인 + 등급 분류
- TASK.md source_of_truth 격상
- TEST.md 혼합 정책 (케이스 rewrite + 결과 append-only)
- FUNCTION.md Dependencies 3분류 + Pre-approved Changes
- AI 읽기 범위 정책, 불명확성 대응, 컨텍스트 관리
- shared/ 거버넌스, append-only 아카이빙
- STATUS.md, 완료 체크리스트, 요구사항 진입 프로토콜
- .gitignore 상대 경로 수정
