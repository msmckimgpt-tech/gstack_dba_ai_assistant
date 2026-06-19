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
