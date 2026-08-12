---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0020-zd-deploy-all
linked_unit: unit/feature-0020-zd-deploy-all
sources:
  - ../../unit/feature-0020-zd-deploy-all/docs/FUNCTION.md
---

# Feature — 무중단 배포 커버리지 완성 (zd-deploy-all)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0020-zd-deploy-all/docs/FUNCTION|unit/feature-0020-zd-deploy-all/docs/FUNCTION.md]].

## 1. 한 줄 요약

feature-0014(web 롤링)·0015(graceful/DDL)·0016-zd(PG PAUSE)·0017(빌드게이트) 위에, 배포가
필요한 나머지 전부 — 워커(insight/ask) 자동 롤아웃·bedrock-gateway surge 무중단 교체·caddy
이미지 드리프트·alembic stale-image 가드 — 를 같은 deploy 스파인(`bin/deploy-web.sh`)으로 완성.

## 2. 상태

- **단계**: in-progress
- **마지막 갱신**: 2026-07-14 (정본 `feature_status_date` 기준. 2026-08-12 quiesce 게이트 2 cycle(`ed257c1e` 워커·gateway 교체 게이트 · `9f43c3ca` 배포 스파인 밖 재생성 봉인 — `bin/lib/quiesce.sh`·`bin/safe-recreate.sh`·`bin/recreate-audit.sh`)은 머지·실측됐으나 정본 TASK/STATUS 의 상태 전이가 미반영 — feature-cycle 소관)
- **AI 작업자**: ai/claude/feature-0020-zd-deploy-all

## 3. 책임 경계

- 입력: origin/main HEAD (coalesce), `docker-compose.yml` base file-set, deploy state 파일.
- 출력: `mysql-ai-web:<sha>`(web-a/b)·`mysql-ai-agent:<sha>`(insight/ask) 핀 롤아웃,
  (드리프트 시) gateway surge 교체·caddy recreate. `make deploy-all`=`deploy-web`.
- side-effect: `artifacts/deploy/` state(key=value)·last-good 태그 회전·keep-N prune.
- Out of scope: DB HA/엔진 재시작·호스트 무중단(0015 ANCHOR)·gateway 상시 2-replica.

## 4. 관련 정본

- [[../../unit/feature-0020-zd-deploy-all/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0020-zd-deploy-all/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0020-zd-deploy-all/docs/ANCHOR|ANCHOR.md]] — 외부 관점·대안 분기
- [[../../unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK|feature-0014 RUNBOOK.md]] — 배포 운영 절차(§9 개정)

## 5. 관련 노트

- [[feature-0014-zero-downtime-deploy]] · [[feature-0015-zd-hygiene-backup]] ·
  [[feature-0016-zd-pg-pause-caddy]] · [[feature-0017-deploy-build-gate]] — 선행 무중단군

## 6. Open questions / 미해결

- bedrock-gateway 상시 2-replica (메모리 예산 — 사람 결정)
- 첫 배포 이후 agent last-good 축적 → 워커 자동 롤백 경로 라이브 자연 검증

## 7. 변경 이력 (이 카드)

- 2026-07-14: 카드 생성 (feature 신규 — cycle ai/claude/feature-0020-zd-deploy-all)
