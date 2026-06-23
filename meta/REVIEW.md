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
