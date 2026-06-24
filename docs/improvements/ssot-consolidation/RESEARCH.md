---
doc_type: DQA_RESEARCH
initiative: ssot-consolidation
created_at: 2026-06-23
status: active
schema_version: 1
source_of_truth: false
---

# RESEARCH — SSOT 통합 (문서·코드·운영 파편화 진단)

> 사용자 보고 증상: "비대화된·파편화된 코드/문서로 인해 작업이 정립되지 못하고 요청을 제대로 수행하지 못함."
> 본 문서는 진단(증거)과 적대 리뷰 기록을 담는다. 실행 계획은 [ROADMAP.md](./ROADMAP.md).

## 0. 대상 제품
- `mysql_ai` — AI assistant(web UI + NL2SQL + group conversation + datasource RBAC 등). Python 3.11 / Docker Compose / MySQL+Postgres+MinIO.
- AI 위임 개발 템플릿(`ai_delegated_dev_template` v3.34.1) consumer.
- 정본 진입: repo/AGENTS.md · docs/PROJECT.md · docs/ARCHITECTURE.md

## 1. 진단 — SSOT 위반 4범주

### 1.1 정본 다중화 (같은 사실이 N곳, sot=true 충돌)
- 의사결정: docs/DECISIONS.md + AGENTS.md §18 + wiki/Decisions(ADR-0005 sot=true) — 3곳
- 현황: unit/*/docs/{TASK,REPORT} + STATUS.md(290KB) + wiki/Features — 3곳, drift
- 아키텍처: docs/ARCHITECTURE.md + wiki/Architecture(Module-Map sot=true) + wrapper Architecture/ — 3곳
- 운영정책: AGENTS.md + CONVENTIONS.md §3.1·§7 — 중복 선언
- 용어: CONVENTIONS.md §9 + wiki/Glossary — 2곳

### 1.2 비대화 (컨텍스트 로드 차단)
- STATUS.md 290KB/331줄(평균 875자/줄 — 셀 누적), AGENTS.md 189KB/3219줄/22섹션,
  DECISIONS 84KB, LEARNINGS 57KB, SECURITY 45KB.

### 1.3 stale 잔존 (오도)
- GOAL.md(archived, 루트 잔존) — 검증된 사고: /goal 세션이 이미 출하된 8기능 재구현(헤더 자증).
- OBSERVATIONS.md status:active 인데 50일+ stale.

### 1.4 제품 코드 SSOT 위반
- feature-0009 코드가 0002/0003 에 분산(경계 붕괴), attachment_reconciliation 이중(0002 238줄/0003 342줄),
  shared/ 빈 껍데기, 단일 Dockerfile 이 0002+0003 묶음, skeleton features(0005/0008/0009).

### 1.5 운영 잔재
- 🔴 tracked secret 백업 3건(아래 §3 BLOCKER), legacy worktrees/(빈), pb0008 산출물 분산, .template-backups 1604파일(gitignore).

## 2. wiki 추가 검증 결론
- ~85파일/12섹션. **98% docs mirror, 2% 고유**(Log.md=ledger, hot.md=세션캐시, concepts/=설계의도).
- 자동 동기화 부재 → 진행중 feature 만 최신, 완료 feature(0001/0004~0007) stale.
- wiki sot:true 는 `wiki/Log.md`(ledger) 1건뿐 — 정당(ssot-lint 로 확인). ※ 적대 리뷰가 지목한 ADR-0005/Module-Map '거짓 SOT' 는 실측 결과 이미 `sot:false` 로, lint 가 리뷰 주장을 반증함.
- 권고: **참조-only 레이어로 명확화 + 자동 동기화** (완전 폐기는 Log/hot/concepts 손실로 위험).

## 3. 🔴 BLOCKER — secret 노출 (적대 리뷰 #12, 실행 전 필수)
`.env.secret.bak-task0228` / `.env.bak-task0211` / `.env.bak-task0279`:
- 모두 git TRACKED + **origin/main HEAD(3ad5a37) + 다수 원격 브랜치 + 머지 PR(#231/#263)** 에 존재. NOT gitignore.
- 실 자격증명 포함: `AGENT_DATASOURCE_KEK_V1`, `MYSQL_ROOT_PASSWORD`, `WEB_BOOTSTRAP_ADMIN_PASSWORD`, `AGENT_KB_PG_*` 등.
- origin = 외부 GitHub(`gstack_dba_ai_assistant`).
- **`git rm` 은 과거 blob 제거 못 함 → rm-only = 노출 제거 0.** rotation 무조건 1순위(=사용자/외부 작업).

## 4. 적대 리뷰 기록 (2026-06-23, 42 에이전트 / 6 렌즈)
- raw 35건 → **확정 16 / 기각 19** (기각 다수: critics 가 미커밋 plan 을 repo 에서 못 찾아 환각 → 검증 단계가 기각).
- blocker 1(secret), major 다수: Dockerfile 분리 시 148 cross-feature import 붕괴 / attachment_reconciliation 은 중복 아닌 별개 worker(0002 에 미배선 GDPR legal-erasure) / feature-0009 코드 이동 시 import 붕괴 / check #9(REVIEW.md) 게이트 누락 / secret grep 패턴이 3건 중 2건 미검출 / .gitignore 글롭 부재 / Phase 4 롤백 경로 부재 / 검증 phase 부재.
- 강화 결과: secret=rotation 1순위 격상, Phase 2(활성 worktree 흡수) 신설, Phase 5 import 실측 선행+전역 검증 통합, 전 Phase 게이트에 check #9 추가. → [ROADMAP.md](./ROADMAP.md).
