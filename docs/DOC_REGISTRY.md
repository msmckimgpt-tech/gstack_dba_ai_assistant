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
3. `status|lifecycle: archived` 는 `docs/_archive/` 에 위치.
4. `bin/ssot-lint.sh` 가 1~3 + 'tracked .env*.bak* 0건' 을 강제.

## 도메인 → 정본 지도

| domain | **canonical (SSOT)** | lifecycle | reference / mirror (복제 금지) | archive |
|---|---|---|---|---|
| AI 운영 정책 | `AGENTS.md` | active(rewrite) | CLAUDE.md · GEMINI.md · CONTRIBUTING.md · CONVENTIONS.md §3.1·§7 (→ 포인터화 P1) | — |
| 의사결정(ADR) | `docs/DECISIONS.md` | ledger(append-only) | AGENTS.md §18(링크) · wiki/Decisions/*(mirror) | — |
| 프로젝트 현황 | `unit/<feature>/docs/{TASK,REPORT}` | active(feature) | `docs/STATUS.md`(인덱스 only, P1) · wiki/Features/*(카드 mirror) | — |
| 아키텍처 | `docs/ARCHITECTURE.md` | active(rewrite) | wiki/Architecture/*(mirror) · ~~wrapper Architecture/~~(삭제 P1) | — |
| 보안 정책 | `docs/SECURITY.md` | active(rewrite) | — | — |
| 코드 규약 | `docs/CONVENTIONS.md` | active(rewrite) | (AGENTS 중복 흡수 P1) | — |
| 용어(Glossary) | `docs/CONVENTIONS.md §9` | active | wiki/Glossary/*(mirror) | — |
| 학습 이력 | `docs/LEARNINGS.md` | ledger(append-only) | wiki(미러 예정) | — |
| 관측 이력 | — | — | — | `docs/_archive/OBSERVATIONS.md`(P1, stale) |
| 진입점 | `FIRST_REQUEST.md`(전역) | active | README.md(들) = 포인터 | `docs/_archive/GOAL.md`(P1) |
| 제품 코드 | `unit/<feature>/src` (경계=디렉토리) | active | cross-cut(예 0009)은 소유 feature src + `unit/<x>/docs/ANCHOR.md` 위치 매핑 | — |
| 공통 코드 | `shared/` | active | (feature 복제 dedup P5) | — |
| 런타임 산출물 | wrapper `artifacts/`(gitignore, 1곳) | transient | — | — |
| 마이그레이션 메모 | `docs/MIGRATION_*.md`(진행 중) | draft | — | (완료 시 `docs/_archive/`) |
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

## 미해소 (P1~P5 에서 정리)
- STATUS.md 가 아직 현황을 셀에 누적(290KB) — P1 에서 인덱스화.
- wiki 의 `source_of_truth: true` 는 `wiki/Log.md`(자체 ledger, 정당) 1건뿐 — `bin/ssot-lint.sh --check wiki-sot` 로 확인. (적대 리뷰가 지목한 ADR-0005/Module-Map 은 실제 `sot:false`로 이미 정합 — P4 는 신규 카드의 sot:false 일관성 유지 + mirrors 백필에 집중.)
- 🔴 tracked secret 백업 3건 — P3(rotation 선행).
