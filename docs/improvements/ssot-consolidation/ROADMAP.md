---
doc_type: DQA_ROADMAP
initiative: ssot-consolidation
created_at: 2026-06-23
source_research: ./RESEARCH.md
status: active
schema_version: 1
source_of_truth: false
---

# 개발 로드맵 — SSOT 통합 (Single Source of Truth)

> 적대 리뷰(42 에이전트, 확정 16/기각 19, blocker 1) 반영 v2. **다른 세션이 0 맥락으로 읽고 착수 가능**해야 한다.
> 진단 증거: [RESEARCH.md](./RESEARCH.md). SSOT 계약 정본: [../../DECISIONS.md](../../DECISIONS.md) ADR-0031 + [../../DOC_REGISTRY.md](../../DOC_REGISTRY.md).

## 0. 맥락 (context-free 진입)
프로젝트가 거버넌스(메타)·제품 두 레이어로 14개월 누적되며 정본이 다중화·비대화·stale 화되어,
AI 세션이 "무엇이 진실인지" 판정에 실패 → 작업 미정립. 목표 = 모든 사실이 정확히 한 곳의 정본을 갖는 구조.
- 대상 제품: `mysql_ai` (AI assistant). 정본 진입: repo/AGENTS.md · docs/PROJECT.md · docs/ARCHITECTURE.md
- 측정 기반: `bin/ssot-lint.sh` (Phase 0 신설), `bin/verify-completion.sh` check #9

## SSOT 계약 4조 (ADR-0031 정본)
1. 한 도메인 = 한 정본. `source_of_truth: true` 는 도메인당 정확히 1개.
2. 참조는 복제 금지 — `mirrors:`/`sources:` 로 정본 경로 선언.
3. archived 는 `docs/archive/` 로 격리(루트 오염 금지).
4. drift 는 lint 가 강제(도메인당 SOT 1개 / 참조의 source 선언 / archived 위치 / tracked secret 0).

## 1. 종속성 그래프
```
P0(계약·lint·registry) ──requires──▶ P1(문서정본) ──▶ P2(worktree 흡수) ──▶ P4(wiki 참조-only)
P0 ──▶ P3(secret/clutter, CRITICAL) [rotation 선행=사용자]
P1 ──▶ P5(코드 재배치+검증) [import 그래프 실측 선행]
```
- P3 는 P0(글롭 가드·registry) 후 가능하나 rotation(사용자/외부) 완료 전 secret 단계 진행 금지.
- P4 는 P1(docs 정본 확정) 의존(mirror 출처 고정 후 동기화 의미 성립).
- P5 는 P1(정본 지도) 의존 + import 의존성 그래프 실측 선행.

## 2. Phase 시퀀스
| Phase | 포함 | risk | 진입 조건 | worktree |
|---|---|---|---|---|
| P0 | 계약 ADR·DOC_REGISTRY·ssot-lint 골격·ROADMAP 정식화 | low | (없음) | ai/claude/META-0003-ssot-consolidation |
| P1 | 아카이빙·포인터화·STATUS 인덱스화·frontmatter | medium | P0 | 〃 |
| P2 | 활성 worktree 정본 흡수·in-flight TASK | medium | P1 | 〃 |
| P3 | secret 노출 종료·clutter | **critical** | P0 + **rotation(사용자)** | ai/claude/META-0004-secret-cleanup (별도 PR) |
| P4 | wiki 참조-only·자동 동기화 | medium | P1 | 〃 ssot-consolidation |
| P5 | 코드 재배치·전역 검증/회귀 | major | P1 + import 실측 | 단위별 독립 PR |

> P0·P1·P2·P4 는 본 worktree 공유(순차 commit). P3·P5 단위는 격리 PR(롤백 단위 분리, §13.2.7).

## 3. 항목 (각 1 cycle)

### ITEM-P0 · SSOT 계약 고정 + META cycle 등록 + lint 골격
- **status**: in-progress
- **feature_id**: META-0003-ssot-consolidation
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: []
- **why**: 정본이 기계적으로 결정되려면 계약(ADR)·기계가독 지도(DOC_REGISTRY)·강제(lint)가 선행돼야 함.
- **작업**:
  - ADR-0031(SSOT 계약 4조 + 도메인 정본 지도) → docs/DECISIONS.md
  - docs/DOC_REGISTRY.md 신설(domain→canonical→mirrors→lifecycle)
  - bin/ssot-lint.sh 골격(WARN-only) + `--selftest`
  - 본 RESEARCH/ROADMAP 정식화
  - META 층위(§18.4) 명시 — Meta-Cycle trailer/path-fallback 으로 cycle 경계 등록
- **gate**: `bash bin/ssot-lint.sh --selftest` 통과(오탐 0) + verify-completion check #9(REVIEW.md entry) + 신규 문서만(비파괴)

### ITEM-P1 · 문서 정본 정리
- **status**: pending
- **feature_id**: META-0003-ssot-consolidation
- **risk_grade**: Major   <!-- STATUS 정본 재정의 → plan-review -->
- **depends_on**: [ITEM-P0]
- **작업**: GOAL/OBSERVATIONS → docs/archive/; STATUS 인덱스화(상태+최근 TASK 3링크); CONVENTIONS §3.1·§7→포인터, AGENTS §18 ADR본문→DECISIONS 링크, CLAUDE/GEMINI/CONTRIBUTING/README 포인터화; WIKI.md vs wiki/README.md 정본 1개; cross-cut(0009) 정본 보정 + TASK/REPORT §1 stale 라인 정합; frontmatter(mirrors/sources/lifecycle) 백필.
- **gate**: ssot-lint(도메인당 SOT 1) + 링크 무결성 + STATUS<30KB + check #9 + in-flight TASK 'active' 링크 정확

### ITEM-P2 · 활성 worktree 정본 흡수 + in-flight TASK 마이그레이션
- **status**: done (정책 명문화 — DOC_REGISTRY "In-flight worktree 현황 흡수". 현 충돌 위험 0: 현행 worktree ahead=0, stale leftover 는 정리 대상)
- **risk_grade**: Major
- **depends_on**: [ITEM-P1]
- **작업**: 활성 worktree(attach-cutover/conn-health/feature-0002/feature-0010/task0234) 미머지 TASK 를 STATUS 인덱스가 'active' 링크로 표기; STATUS 재작성 vs doc-sync rollup 동시편집 충돌 방지(동결창/머지순서); 흡수 마이그레이션 가이드.
- **gate**: 머지 시 ssot-lint 통과 + in-flight TASK 미단절 + 동시편집 충돌 0

### ITEM-P3 · secret 노출 종료 + 운영 잔재 (CRITICAL)
- **status**: blocked (rotation=사용자/외부 작업 + §12 사람 승인 대기)
- **feature_id**: META-0004-secret-cleanup
- **risk_grade**: Critical
- **depends_on**: [ITEM-P0]
- **작업**:
  1. **rotation 1순위 무조건**: 노출 자격증명(KEK/DB/admin/LLM/oauth/minio) 전수 식별 → rotation → 옛 키 폐기 → 로그 모니터링. (사용자/외부)
  2. ai/claude/META-0004-secret-cleanup worktree + PR(§13.2.7) + §12 사람 최종 승인 + Critical 이중 승인.
  3. .gitignore 글롭(.env*.bak*, *.bak-task*) + pre-commit/ssot-lint 'tracked .env*.bak* 0건' 가드.
  4. history rewrite(filter-repo)는 원격 브랜치+worktree+머지PR 영향 runbook 동반 별도 작업(게이트 아님). rotation 이 1차 방어선.
  5. 비파괴 clutter: legacy worktrees/ 삭제, pb0008 1곳 통합, .template-backups prune.
- **gate**: rotation 폐기증빙 + `git ls-files | grep -iE '\.env\..*(bak|secret)|\.bak-task'` → 0건 + `git log --all` 스캔 + GitHub Push Protection + check #9 + §12 승인 기록
- **rm-only 금지** — 이미 push 된 노출은 rm 으로 제거 불가.

### ITEM-P4 · wiki 참조-only 체계화
- **status**: pending
- **feature_id**: META-0003-ssot-consolidation
- **risk_grade**: Major
- **depends_on**: [ITEM-P1]
- **작업**: wiki 전역 sot:false 일관성 검증(`ssot-lint --check wiki-sot` — 현재 Log.md 1건만 sot:true, 정당; 리뷰의 ADR-0005/Module-Map '거짓 SOT' 는 실제 sot:false 로 오판이었음); 신규 카드 mirrors/sources 백필; mirror 자동 재생성 hook/CI; stale 카드(0001/0004~0007) 백필/동결 라벨; concepts→docs/improvements 승격 검토; hot/Index/overview frontmatter 정규화 + wiki-lint 의무화.
- **gate**: wiki-lint + drift 0(정본 mtime ≤ mirror mtime) + check #9

### ITEM-P5 · 제품 코드 재배치 + 전역 검증/회귀
- **status**: pending
- **feature_id**: META-0003-ssot-consolidation (코드 단위는 별도 feature-NNNN cycle 로 분기)
- **risk_grade**: Major
- **depends_on**: [ITEM-P1]
- **작업**:
  - 선행: import 의존성 그래프 실측(app.py 148 `from modules.*`).
  - shared/ 추출(modules.→shared. 재정의 + 148 import + 두 이미지 빌드 컨텍스트)을 Dockerfile 분리의 전제로 — 분리 자체는 선행 없이는 비실행.
  - attachment_reconciliation 'dedup' 폐기: live 0003판 무변경, 0002판 GDPR(admin_purge/legal, 미배선) 사양 여부 결정, env키(POLL_SEC vs INTERVAL_SEC) 정본 ADR 후 alias. 단순 합치기 금지.
  - feature-0009 '코드 이동' 옵션 삭제 → cross-cut 을 ANCHOR/CODEBASE_MAP 에 명시만. skeleton(0005/0008/0009) '코드 없음/계획' 라벨.
  - 각 단위 독립 PR + 롤백 경로(이미지 태그 보존 + compose 기준점 + revert + 이전 이미지 redeploy + 롤백 리허설 1회).
  - 전역 회귀: `make test`(pytest unit/feature-0002·0003/tests + ruff) + 전체 docker compose build + browser 검증.
- **gate**: make test PASS + 전체 build + browser + 롤백 리허설 + plan-review 승인 + check #9 + 단독 cycle

## 4. Open Decisions (사용자 입력)
1. secret rotation 범위 + history rewrite 추가 수행 여부(+저장소 public/private 확인)
2. STATUS 과거 누적 셀: unit TASK 링크만 vs STATUS_ARCHIVE 보존
3. wiki 자동 동기화: pre-commit hook vs CI vs 수동 lint
4. 0002 attachment_reconciliation GDPR legal-erasure: 배선/제거/보존
5. 단일 Dockerfile 분리: Phase 5 에서 분리까지 vs cross-cut 명시 + 단일 이미지 유지
6. §18.4 인간 개입 강도: 전 Phase vs Critical(P3)·Major(P5)만
