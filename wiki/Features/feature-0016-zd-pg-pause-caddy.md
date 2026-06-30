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
maturity: minimal
ai_generated: true
feature_id: feature-0016-zd-pg-pause-caddy
linked_unit: unit/feature-0016-zd-pg-pause-caddy
created: 2026-06-30
sources:
  - ../../unit/feature-0016-zd-pg-pause-caddy/docs/FUNCTION.md
---

# Feature — PG PAUSE 래퍼 + Caddy reconcile

> 정본은 [[../../unit/feature-0016-zd-pg-pause-caddy/docs/FUNCTION|FUNCTION.md]].

## 1. 한 줄 요약
무중단 feasibility "조건부→가능" 2항목: ① `bin/pg-restart.sh` 가 pgbouncer PAUSE→PG 재시작→RESUME 으로
PG primary config/minor 재시작을 RW 에러 없이(near-zero), ② `deploy-web.sh reconcile_caddy()` 가
Caddyfile 변경 시에만 caddy 를 recreate(inode-stale 대응).

## 2. 상태
- **단계**: review — 코드/정적검증 완료. 라이브(pgbouncer ADMIN_USERS recreate + pg-restart 실증)는 배포 단계.
- **마지막 갱신**: 2026-06-30 · claude / Human(PLAN-APPROVED).

## 3. 책임 경계
- pg-restart: (in) restart action → (out) PAUSE→restart→RESUME, RW 큐잉(무에러). RESUME trap 보장.
- reconcile_caddy: (in) host/container Caddyfile sha → (out) 다르면 검증·recreate, 같으면 no-op.

## 4. 관련 정본
- [[../../unit/feature-0016-zd-pg-pause-caddy/docs/FUNCTION|FUNCTION.md]] · [[../../unit/feature-0016-zd-pg-pause-caddy/docs/TASK|TASK.md]] · [[../../unit/feature-0016-zd-pg-pause-caddy/docs/ANCHOR|ANCHOR.md]]

## 5. 관련 노트
- [[feature-0014-zero-downtime-deploy]] — deploy-web.sh(reconcile_caddy 가 여기 거주) · [[feature-0006-lan-proxy-access]] caddy
- [[feature-0002-agent-core]] — agent_kb PG/pgbouncer · [[../entities/pgbouncer]](있으면)

## 6. Open questions / 후속
- 전용 pgbouncer admin user 분리(현재 agent_kb_rw 재사용 — 보안 하드닝).
- PG major 업그레이드·HA 는 범위 밖(단일 호스트 SPOF).

## 7. 변경 이력 (이 카드)
- 2026-06-30: 초안(①② 구현 반영).
