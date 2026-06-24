# META REVIEW

> META-layer 변경(`.claude/commands/`, `meta/`, `docs/improvements/` 등)의 검증 패널 기록. AGENTS.md §18.4 / §18.8 / §16.3 check #9.

## REV-20260619T024257-dqa-skill-suite [SUBAGENT:dqa-skill-design-review]

- **cycle**: ai/claude/dqa-skill-suite — `/_dqa` 개선 파이프라인 스킬 3종 + 부속 구조 신설
- **changeset (pure-meta)**:
  - `.claude/commands/_dqa/{improve_research,improve_listup,improve_cycle,README}.md`
  - `docs/improvements/_TEMPLATE-ROADMAP.md`
  - `docs/improvements/dba-ai-nl2sql/{RESEARCH,ROADMAP}.md` (seed)
- **panel**: 독립 general-purpose 리뷰어 1, 적대적 검토(거버넌스 충돌·스크립트 인터페이스·핸드오프·스케줄 안전성·종속성 모델·0맥락 계약).
- **verdict (1차)**: **NOT-SHIP** — BLOCKER 2 + MAJOR 4 + MINOR 3.
- **findings → 조치**:
  - **B1** (improve_cycle 가 `/loop` 전용 ScheduleWakeup 에 의존 → 범용 스케줄 부적합) → allowed-tools 에서 제거. Phase 6 을 "1 호출 = 1 항목, 연속 소진은 외부 wrapper(`/loop`·`/schedule`=CronCreate)" 로 외부화.
  - **B2** (cycle-init `--feature <item-slug>` ↔ verify-completion `<feature-id>` 불일치 → 구조적 미통과) → ROADMAP 항목 스키마에 `feature_id` 필드 신설. improve_cycle 이 양쪽에 동일 사용. unit doc(TASK/MODIFY/FUNCTION/ANCHOR/REVIEW) 갱신 단계를 Phase 3~5 에 명시.
  - **M1** (worktree 내부에서 `repo/` prefix 오류 → 0맥락 착수 시 "파일 없음") → 정본/코드 경로를 repo-상대(`AGENTS.md`·`unit/...`·`docs/...`)로 통일. ROADMAP entry_points·skill 본문·RESEARCH 정합화.
  - **M2** (무인 모드가 Major 를 plan-only 로 우회 → §7.1/§12.3 승인 게이트 위반) → 무인 모드는 **Minor 만 자율**, Major/Critical 은 `blocked: needs-human-plan-approval`.
  - **M3** (ROADMAP status 단독 doc-only 커밋이 META check #9 미충족) → status 갱신을 feature cycle 커밋에 동봉(별도 doc-only 커밋 회피); 불가피 시 `[SKIPPED]` 엔트리 절차.
  - **M4** (ready 선택 로직 모호 → starvation 가능) → 단일 규칙 확정: ready=(pending ∧ deps done), 정렬 Phase asc → risk asc → id asc. Phase=권장(배리어 아님) 합의.
  - **m1** (`in-progress(awaiting-merge)` status enum 외) → `status: in-progress` + `note: awaiting-merge PR#n`.
  - **m2** (`.codex` 미러 부재) → 의도(Claude 전용) — README 명시.
  - **m3** (research/listup 산출의 worktree 책임 공백) → 산출도 worktree 에서 작성(§13.2.7 F0) 명시.
- **verdict (2차, 조치 후)**: SHIP-WITH-FIXES — BLOCKER/MAJOR 전건 반영. 잔여 MINOR 없음(전건 조치).
- **note**: 본 묶음은 메타-도구(스킬 정의)로 비파괴 추가. 실제 ROADMAP 항목 구현은 각 `improve_cycle` 호출이 독립 feature cycle 로 verify-completion 게이트를 거친다.

## REV-20260619T030718-dqa-skill-suite [SKIPPED:additive-meta-tooling-docs]

- **cycle**: ai/claude/dqa-skill-suite (2차 commit) — 파이프라인 가동 + 추가 구조
- **changeset (pure-meta)**:
  - `docs/improvements/dba-ai-nl2sql/RESEARCH.md` — `## Round 2` append(F-015~F-019: enterprise 벤치마크·safety lower-bound·동적 few-shot·분해·NL rewriter + 채널 C 내부 히스토리 정합).
  - `.claude/agents/improve-fit-reviewer.md` — improve_listup 전용 적대적 정합 리뷰어(REV-1 패널이 쓴 6축 기준을 subagent 로 codify).
  - `CLAUDE.md` — Skill routing 에 `/_dqa:*` 1블록 등록.
- **panel skipped 사유 (§18.4 doc/meta-tooling carve-out)**: ① Round 2 = RESEARCH 에 findings append 만(ROADMAP/코드 무변경, 신규 production 동작 0) ② fit-reviewer agent = REV-1 에서 이미 검증된 패널 기준의 codify(신규 판단 로직 아님) ③ CLAUDE.md = 1블록 라우팅 추가. 비파괴·additive·meta-class 라 독립 패널 불요.
- **note**: Round 2 의 F-016(safety lower-bound 거부 평가축)·F-015(execution-based 벤치마크)는 차후 `improve_listup` 가 ITEM-01 acceptance 로 fold 예정(현재 RESEARCH 에만 적재 — research↔listup 단계 분리 준수).

## REV-20260619T032212-dqa-drain-mode [SUBAGENT:dqa-drain-mode-review]

- **cycle**: ai/claude/dqa-drain-mode — `/_dqa:improve_cycle` 드레인 모드 추가(no-arg → ready 항목 종속/순차 전체 구현)
- **changeset (pure-meta)**: `.claude/commands/_dqa/improve_cycle.md`(드레인 모드 + 실행모드 섹션 + Phase 6 + 종료조건) · `README.md`(정합 갱신)
- **panel**: `improve-fit-reviewer` subagent(첫 자가 사용). 적대적 검토 — 거버넌스 우회/외부영향 confirm/무인 안전선/종속 무결성/단건 회귀.
- **verdict (1차)**: **SHIP-WITH-FIXES** — MAJOR 3 + MINOR 2.
- **findings → 조치**:
  - **MAJOR-1** (시퀀스 batch 승인이 9개 Major 의 §7.1 개별 plan-review 를 대체=우회) → 드레인 승인을 **orchestration 메타승인으로 한정**(자동전진+Minor+commit/push 만 인가). 각 Major 는 항목 차례에 file/symbol/acceptance plan→PLAN-APPROVED 개별 유지.
  - **MAJOR-2** (불변제약 §외부영향 confirm ↔ "batch 가 per-item PR/머지 인가" 자기모순 + 전역 PR-confirm 이탈) → batch consent 에서 **PR 생성·머지·deploy 제거**. 항목별 confirm 유지.
  - **MAJOR-3** (무인 모드 판별 미정의 = fail-open 위험) → **fail-closed 기본값**: `--unattended` 명시 신호 또는 게이트 미응답이면 자동 진행 안 함(Minor-only 강등·blocked).
  - **MINOR-1** (종속 재로드 위치 모호) → 의사코드에 `cd main_worktree; git pull --ff-only; reload ROADMAP`(§13.2.5) 명시.
  - **MINOR-2** (STOP 분기 `continue` 누락·진행성 가드 일반화) → `continue` + `no_progress` 카운터로 교착 종료.
- **verdict (2차, 조치 후)**: SHIP-WITH-FIXES — MAJOR/MINOR 전건 반영. 단건 모드 회귀 없음(reviewer 통과).
- **note**: 드레인은 orchestration 만 자동화, 거버넌스 게이트(Major plan-review·Critical confirm·PR/deploy)는 항목별 유지 — "전체 자동 구현"이되 §7.1/§12.3/외부영향 confirm 불변.

## REV-20260623T055339-resume-codex-mirror [SKIPPED:additive-meta-tooling-codex-mirror]
- **cycle**: ai/claude/META-0001-resume-codex-mirror — `/_template:resume` 정본(personas submodule)의 소비자측 동기화 = submodule 포인터 bump + Codex 미러 2종.
- **changeset (pure-meta)**: `.claude/commands/_template`(gitlink 7f3ae74→a08bf56, personas PR#3 머지 반영) · `.codex/commands/_template/resume.md`(Codex shim, 정본 포인터) · `.codex/skills/_template-resume/SKILL.md`(Codex skill discovery wrapper) · `meta/REVIEW.md`(본 entry).
- **panel SKIP 사유**: 정본 `resume.md` 의 설계·정확성은 personas PR#3 직전 **5개 적대적 리뷰어 패널**(요구사항·거버넌스·스니펫 실측·엣지케이스·project-agnostic)로 이미 검증·수정 완료(FAIL 1 + leak 4 + nit 다수 반영). 본 소비자측 changeset 은 (a) 검증된 정본을 가리키는 thin shim/wrapper + (b) 머지된 업스트림 커밋으로의 포인터 bump 뿐 — 신규 로직 0, 행동 차이 0. §18.8 additive-meta-tooling 경량 경로 → SKIPPED.
- **verification**: Codex shim 상대경로(`../../../.claude/commands/_template/resume.md`) resolve 확인, SKILL.md `name: _template-resume`(하이픈)·description 형식이 기존 `_template-entry` 와 정합. gitlink 대상 a08bf56 은 personas origin/main(PR#3 머지)에 존재 → submodule fetch 가능.
- **Human Approval Needed**: 아니오 (additive meta tooling, 정본 패널 검증 완료, 사용자 전체 전파 승인).


## REV-20260623T092428-doc-sync-skill [SKIPPED:additive-meta-tooling-docs]

- **cycle**: ai/claude/doc-sync-skill — `/_dqa` 묶음에 standalone maintenance persona `doc_sync` 신설(머지 작업↔정책문서·wiki·릴리즈노트 drift 정합)
- **changeset (pure-meta)**:
  - `.claude/commands/_dqa/doc_sync.md` (신규 skill 본문 — frontmatter~종료조건)
  - `.claude/commands/_dqa/README.md` (`## 부가: 유지보수 persona (doc_sync)` 섹션 추가 — 파이프라인 표/다이어그램 불변)
  - `CLAUDE.md` (Skill routing 의 `/_dqa` 블록에 doc_sync 라우팅 1줄)
- **panel skipped 사유 (§18.4 doc/meta-tooling carve-out)**: skill 정의(.md)·README·CLAUDE.md 라우팅의 비파괴 additive 추가로, 신규 production 동작 0·코드 무변경. 신규 standalone persona 의 거버넌스 정합성은 독립 fit/convention/agnostic/repro 리뷰(아래 findings)로 이미 검증됨 → 별도 패널 불요.
- **review findings → 조치 (BLOCKER/MAJOR 전건 반영)**:
  - **B1·B2(repro·fit, verify META-mode 전제 거짓)**: 릴리즈노트는 `unit/feature-NNNN/src/static/...`(operational) 라 META mode 아님(`is_meta_path` 폴스루 실측). 불변 제약에 "타깃별 commit 분류" 신설 + Phase 4 를 (a)pure-meta META mode / (b)릴리즈노트 포함 operational gate 두 갈래로 재서술. 릴리즈노트 commit 은 owning feature-id 로 verify, 충족 불가 시 owning cycle 위임 정직 보고.
  - **B3(fit·repro, verify 인자 `META`)**: bare `META`/`<feature-id-or-META>` 가 `validate_feature_id` 정규식 미충족(die). 정규식 적합 `META-NNNN-<slug>` 발급 의무 + pure-meta short-circuit 발화 순서(`:1180`<`:1210`) 명시. bare META 예시 전면 제거.
  - **B4(repro, REVIEW entry path)**: pure-meta → `meta/REVIEW.md`, operational feature-bound → `unit/<fid>/docs/REVIEW.md` 분리 명시. entry 헤더 정규식(`REV-YYYYMMDDThhmmss-<branch> [SKIPPED|CODEX|...]`) 박음.
  - **M(convention, README/CLAUDE.md 미등록)**: README 에 maintenance 전용 섹션(파이프라인 표 밖) 추가, CLAUDE.md `/_dqa` 블록에 라우팅 1줄 추가.
  - **M(agnostic, project-specific 토큰 하드코딩)**: `feature-0009`·`WEB_PORT=18080`·`pgbouncer`·`repo-web-1`·`?v=20260623-rn-0623`·`verify_release_notes.mjs`·`WIKI_FEATURE_CARD`·`releases[0]`·`work/admin/common` enum·`/healthz` 전부 제거 → 카테고리 일반 서술 + "매번 discovery" 행동지시로 치환.
  - **M(repro, Phase 6 TLS/서비스 discovery)**: TLS 종단 discovery + `curl -k https→http fallback` + 서비스키/컨테이너명 discovery(`docker compose ps`) + `--no-deps` surgical rebuild + make-init 우회 명시.
  - **M(repro, no-delta 종결)**: 전 타깃 delta 0 시 브랜치·commit·verify 없이 early-exit("모두 최신") — 빈 changeset landing 도달 금지(불변 제약 + Phase 1 + 종료조건).
  - **MINOR/NIT 반영**: §13.1 ARCHITECTURE 색인 한정·신규 ADR 본문 금지(색인만); `/_template:entry`·`/document-release` 와 idempotency 경계 단락; §13.2.7 canonical worktree add(repo-상대 path) 인용; SKIP 토큰 `[SKIPPED:non-policy-doc]` vs `[SKIPPED:<슬러그>]` 구분; `git add -A/./-u` 금지 + `.env*.bak*`·`artifacts/`·`.worktrees/` 디코이 명시 + `git status` 확인; ACL setfacl 은 EACCES+`getfacl` 검출 게이트 후에만; wiki feature 수 정합 grep recipe(`ls -d unit/feature-*|wc -l` ground-truth) 명시; 정책문서 미구성/first-sync skip 분기; `pipeline_stage: standalone (maintenance)` + persona intro 어휘를 sibling("파이프라인") 정합.
- **잔여 MINOR(미반영, 사유)**: frontmatter `target_project: mysql_ai_delegated_dev` 유지(sibling 3종 동일 house-style — 묶음 일관성 우선, 런타임 무영향). `pipeline_stage` 자유형 값(`standalone (maintenance)`)은 의도적(번호 단계 아님 — 기존 `N/3` parser 와 불일치는 수용).
- **verdict**: SHIP-WITH-FIXES — BLOCKER 4 + MAJOR 7 전건 반영, MINOR/NIT 합리적 항목 전건 반영. 잔여는 house-style 메타데이터 2건(behavioral over-fit 아님).
- **note**: 비파괴 메타-도구(skill 정의) 추가. 실제 doc 정합 실행은 각 `/_dqa:doc_sync` 호출이 changeset 분류대로 verify-completion 게이트(META mode 또는 operational gate)를 직접 거친다.

## REV-20260624T005709-META-0003-ssot-consolidation [AGENT-TEAM:ssot-plan-redteam]

- **cycle**: ai/claude/META-0003-ssot-consolidation — SSOT 통합 initiative **Phase 0** (계약·레지스트리·lint 골격)
- **changeset (pure-meta)**:
  - `docs/DECISIONS.md` — ADR-0031 (SSOT 계약 4조) append
  - `docs/DOC_REGISTRY.md` — 신규 (도메인→정본 단일 지도, 기계가독)
  - `bin/ssot-lint.sh` — 신규 (WARN-only 골격 + `--selftest`)
  - `docs/improvements/ssot-consolidation/{RESEARCH,ROADMAP}.md` — 신규 (진단 + 0~5 강화 plan)
  - `meta/REVIEW.md` — 본 entry
- **panel (AGENT-TEAM)**: SSOT plan 적대 리뷰 workflow — 6 렌즈(SSOT 정합성·거버넌스 준수·런타임 안전성·누락·secret 처리·순서/실현성) × 독립 비평가, 적대 검증(refute 시도, 불확실시 기각), 강화 합성. 42 에이전트, raw 35 finding.
- **verdict**: SHIP-WITH-FIXES (Phase 0 한정) — 확정 16 / 기각 19, **BLOCKER 1**.
- **findings → 조치 (Phase 0 반영분)**:
  - **BLOCKER (#12 secret)**: 노출 secret `rm-only` 무의미(이미 origin/main+원격 브랜치+머지 PR push) → ADR-0031 §4 + `ssot-lint` 가 'tracked `.env*.bak*` 0건' 가드로 포착. rotation 1순위는 **Phase 3(META-0004, 사용자 rotation 진행 의사 확인)** 로 명시. Phase 0 자체는 secret 무변경.
  - **#9 (check #9 게이트 누락)**: 전 Phase 게이트에 verify-completion check #9(REVIEW.md) 추가 — 본 entry 가 첫 적용.
  - **#10/#16 (secret grep false pass/fail)**: ssot-lint 패턴 `(^|/)\.env[^/]*\.bak|\.bak-task[0-9]|\.secret\.bak` 로 3건 전수 검출 + `.example` 오탐 0 (`--selftest` 검증).
  - **#15 (.gitignore 글롭 부재)**: Phase 3 작업으로 명시.
  - **리뷰 오류 정정 (lint=ground truth)**: 리뷰가 지목한 wiki '거짓 SOT 2건(ADR-0005·Module-Map)' 은 실측 결과 `sot:false` — wiki `sot:true` 는 `wiki/Log.md` 1건뿐(정당). RESEARCH/ROADMAP/DOC_REGISTRY 정정.
- **gate**: `bash bin/ssot-lint.sh --selftest` **PASS**(오탐·미탐 0) + 실제 스캔이 secret 3건 + GOAL.md(archived) 검출(baseline — P1·P3 해소 예정). 신규 문서만 추가(비파괴).
- **Human Approval Needed**: Phase 0 = 비파괴 계약/골격 (사용자 "commit 후 Phase 1 계속" 승인). Major(P1 STATUS 인덱스화)·Critical(P3 secret)은 차례에 §12 별도 승인.
- **note**: 적대 리뷰 전문: `docs/improvements/ssot-consolidation/RESEARCH.md §4`. Phase 0 는 계약·강제 도구만 — 실제 정본 정리/노출 종료/코드 재배치는 P1~P5 가 각자 게이트를 거친다.

## REV-20260624T010743-META-0003-ssot-consolidation [SKIPPED:meta-docs-archive]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 1a** (stale 문서 아카이빙 + archive 위치 교정)
- **changeset (pure-meta)**:
  - `GOAL.md`(루트) → `docs/archive/GOAL.md` (R100 rename), `docs/OBSERVATIONS.md` → `docs/archive/OBSERVATIONS.md` (R100) + frontmatter `lifecycle: archived`
  - `docs/archive/README.md` 신규 (아카이브 보관소 색인)
  - `docs/DECISIONS.md` — ADR-0031 Addendum (archive 위치 `docs/_archive/`→`docs/archive/` 교정, 사유: `.gitignore:27` `_archive/` 무시)
  - `docs/DOC_REGISTRY.md` · `docs/improvements/ssot-consolidation/ROADMAP.md` · `bin/ssot-lint.sh` — `_archive`→`archive` 정합
- **panel SKIP 사유 (§18.4 doc/meta carve-out)**: 신규 production 동작 0. (1) GOAL.md 아카이빙은 STATUS.md(TASK-0133)가 이미 결정·기록한 의도의 물리적 완성(정본 변경 아님), (2) OBSERVATIONS 는 stale 스냅샷 격리, (3) archive 위치 교정은 gitignore 충돌 해소(기계적). rename R100(내용 무변경) + frontmatter only.
- **verification**: `bash bin/ssot-lint.sh --selftest` **PASS**. 실제 스캔 archived **0건**(이전 GOAL.md 1건 해소), secret 3건은 Phase 3(META-0004) 대상으로 잔존. staged changeset pure-meta(루트 비-meta 0). GOAL/OBSERVATIONS 참조는 전부 과거 이력 prose(코드 import 0) — 링크 무결성 영향 없음.
- **Human Approval Needed**: 아니오 (비파괴 아카이빙, 정본 무변경). Major(P1b STATUS 인덱스화)·Critical(P3 secret)은 차례에 §12 별도 승인.

## REV-20260624T012043-META-0003-ssot-consolidation [SKIPPED:status-index-verbatim-preserved]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 1b** (STATUS.md 인덱스화, Major §12.3)
- **changeset (pure-meta)**:
  - `docs/STATUS.md` — 290KB → **4.6KB** lean 인덱스(feature별 상태 1줄 + 정본 링크 + 1줄 요지). 누적 rollup·heavy 셀 제거
  - `docs/archive/STATUS_ARCHIVE.md` 신규 — 인덱스화 이전 STATUS verbatim 보존(cmp IDENTICAL) + archived frontmatter
  - `meta/REVIEW.md` — 본 entry
- **risk**: Major (정본 재정의 — 현황 상세 정본을 STATUS→`unit/<f>/docs/{TASK,REPORT}` 로 명시 이동). **plan-review 수행**(사용자 미결정 #2 = "STATUS_ARCHIVE 보존 후 인덱스화" 선택).
- **panel SKIP 사유**: 비파괴 — 전문 verbatim 보존(`cmp -s` IDENTICAL, rollup 159줄 유지)으로 **정보 손실 0**. STATUS 는 정책문서(AGENTS/CONVENTIONS/SECURITY) 아님(§18.8.1 경량 대상). 신규 production 동작 0. 정본 위계는 ADR-0031 + DOC_REGISTRY 가 정의.
- **verification**: STATUS.md 4,682 bytes(<30KB 성공기준 충족). 내부 링크 6개(unit TASK ×9, STATUS_ARCHIVE, DOC_REGISTRY, DECISIONS, ARCHITECTURE) 전부 타깃 존재 확인. ssot-lint archived 0건(STATUS_ARCHIVE 가 docs/archive/ 내 → skip), secret 3건 잔존(P3). feature-0009 cross-cut·feature-0010 worktree 미병합 명시.
- **Human Approval Needed**: 아니오 (사용자 plan-review + 미결정 #2 승인 완료, verbatim 보존으로 비가역성 없음). 원복 = git revert(미머지).
