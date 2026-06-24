---
doc_type: DOC_REGISTRY
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.34.1
domain: [governance, registry]
ai_read_priority: 3
---

# 문서 정본 레지스트리 (DOC_REGISTRY)

> **이 문서가 "정본이 어디인가?" 의 단일 답이다.** SSOT 계약은 [DECISIONS.md](./DECISIONS.md) ADR-0031.
> AI 세션은 어떤 사실을 찾을 때, 먼저 여기서 도메인의 canonical 경로를 확인하고 그곳만 정본으로 신뢰한다.
> 그 외 위치는 reference/mirror(복제 금지) 또는 archived 다.

## SSOT 계약 4조 (요약 — 정본 ADR-0031)
1. 한 도메인 = `source_of_truth: true` 문서 정확히 1개.
2. reference/mirror(`source_of_truth: false`)는 `mirrors:` 또는 `sources:` 로 정본 경로 선언, 내용 재서술 금지.
3. `status|lifecycle: archived` 는 `docs/archive/` 에 위치.
4. `bin/ssot-lint.sh` 가 1~3 + 'tracked .env*.bak* 0건' 을 강제.

## 도메인 → 정본 지도

| domain | **canonical (SSOT)** | lifecycle | reference / mirror (복제 금지) | archive |
|---|---|---|---|---|
| AI 운영 정책 | `AGENTS.md` | active(rewrite) | CLAUDE.md·GEMINI.md (`lifecycle:reference`, `sources:[AGENTS.md]` — P1c 완료), CONVENTIONS §7(이미 포인터). ※CONTRIBUTING/README 는 포인터 아닌 별개 내용 | — |
| 의사결정(ADR) | `docs/DECISIONS.md` | ledger(append-only) | AGENTS.md §18(링크) · wiki/Decisions/*(mirror) | — |
| 프로젝트 현황 | `unit/<feature>/docs/{TASK,REPORT}` | active(feature) | `docs/STATUS.md`(인덱스 only, P1) · wiki/Features/*(카드 mirror) | — |
| 아키텍처 | `docs/ARCHITECTURE.md` | active(rewrite) | wiki/Architecture/*(mirror) · ~~wrapper Architecture/~~(삭제 P1) | — |
| 보안 정책 | `docs/SECURITY.md` | active(rewrite) | — | — |
| 코드 규약 | `docs/CONVENTIONS.md` | active(rewrite) | (AGENTS 중복 흡수 P1) | — |
| 용어(Glossary) | `docs/CONVENTIONS.md §9` | active | wiki/Glossary/*(mirror) | — |
| 학습 이력 | `docs/LEARNINGS.md` | ledger(append-only) | wiki(미러 예정) | — |
| 관측 이력 | — | — | — | `docs/archive/OBSERVATIONS.md`(P1, stale) |
| 진입점 | `FIRST_REQUEST.md`(전역) | active | README.md(들) = 포인터 | `docs/archive/GOAL.md`(P1) |
| 제품 코드 | `unit/<feature>/src` (경계=디렉토리) | active | cross-cut(예 0009)은 소유 feature src + `unit/<x>/docs/ANCHOR.md` 위치 매핑 | — |
| 공통 코드 | `shared/` | active | (feature 복제 dedup P5) | — |
| 런타임 산출물 | wrapper `artifacts/`(gitignore, 1곳) | transient | — | — |
| 마이그레이션 메모 | `docs/MIGRATION_*.md`(진행 중) | draft | — | (완료 시 `docs/archive/`) |
| doc 레지스트리 | `docs/DOC_REGISTRY.md` (본 문서) | active(rewrite) | — | — |

## frontmatter 계약 (모든 .md)
```yaml
doc_type: <유형>
source_of_truth: true|false      # 도메인당 true 정확히 1개
lifecycle: active | ledger | reference | archived
mirrors: <정본경로>               # source_of_truth:false 인 mirror
sources: [<정본경로>...]          # 참조 문서
```
- unit/<feature>/docs/* 는 (feature_id, doc_type) 쌍으로 정본 유일성이 이미 결정됨 → domain 부여 불요.
- wiki/* 는 전역 `source_of_truth: false` (예외: wiki/Log.md = wiki 자체 ledger).

## In-flight worktree 현황 흡수 (Phase 2)
- **정책**: 미머지 worktree 의 작업 현황 정본 = 그 worktree 의 `unit/<feature>/docs/{TASK,REPORT}.md`.
  STATUS.md 인덱스는 **main 머지 기준** 상태를 반영하고, 미머지 활성 worktree 는 표 아래 note 로만 표기(예: feature-0010).
  머지 시 STATUS 행이 갱신된다. STATUS 인덱스는 셀 누적이 없어 worktree 머지 시 conflict 표면이 작다(인덱스화의 부수 효과).
- **현 상태(2026-06-24)**: 충돌 위험 0 — 현행 worktree(feature-0002, gc-share-group-sync)는 `ahead=0`(작업 main 머지 완료). 미머지 in-flight 작업 없음.
- **stale leftover**(attach-cutover / conn-health / task0232 — 258~417 commit behind, 06-12~15 방치, ahead 0~1): 흡수 대상 아님 → 운영 잔재 정리에서 `bin/cycle-finalize.sh` 또는 `git worktree remove` 대상.

## 미해소 (잔여 Phase)
- 🔴 tracked secret 백업 3건 — **P3 rotation(사용자) 선행 후** repo 위생. 런북: `docs/improvements/ssot-consolidation/SECRET-ROTATION-RUNBOOK.md`.
- 거버넌스 포인터화(CONVENTIONS §3.1·§7 ↔ AGENTS §3.1 중복 흡수) — **P1c** (정책문서 → §18.8.1 codex 검토).
- wiki mirrors/sources frontmatter 백필 + 동기화 메커니즘 — **P4** (sot:false 일관성은 이미 양호, lint 확인).
- 제품 코드 재배치(shared dedup·feature-0009 cross-cut·Dockerfile) — **P5** (import 그래프 실측 + 결정 #4/#5 선행).
