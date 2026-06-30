---
doc_type: TASK
feature_id: feature-0016-zd-pg-pause-caddy
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude) / Human approved
- Priority: high
- Last Updated: 2026-06-30

## 2. Implementation Plan
### 2.1 Plan
- **영향 파일:** `docker-compose.yml`(pgbouncer ADMIN_USERS), `bin/pg-restart.sh`(신규),
  `bin/deploy-web.sh`(reconcile_caddy), `Makefile`(pg-restart), 본 feature docs.
- **접근:** ① pgbouncer admin_users 를 DB_USER(agent_kb_rw, userlist 보유)로 → 컨테이너 내 psql 로
  PAUSE/RESUME. RESUME trap 보장 + PAUSE timeout. ② deploy-web.sh 가 Caddyfile host/container sha
  비교 → 다르면 adapt 검증 후 recreate(변경 시에만).
- **위험도:** Major (pg-restart 는 라이브 pgbouncer/PG path; RESUME 실패 시 RW 차단 위험 → trap 필수).

<!-- PLAN-APPROVED by ms.mckim.gpt (user) on 2026-06-30 — "PG pgbouncer PAUSE 래퍼 / deploy-web.sh Caddyfile recreate 자동화" -->

## 3. Task Queue
- [x] TASK-20260630T150100-pg-pause: compose ADMIN_USERS + bin/pg-restart.sh + make
- [x] TASK-20260630T150101-caddy-reconcile: deploy-web.sh reconcile_caddy()
- [ ] TASK-20260630T150102-deploy-test: pgbouncer recreate(ADMIN_USERS) + pg-restart 라이브 실증 + reconcile 검증

## 4. In Progress
- 정적검증 완료 → 검증패널 → verify-completion → 머지 → 라이브 테스트.

## 5. Blocked
- 없음 (PLAN-APPROVED).

## 6. Done
- feasibility 분석 "조건부→가능" 후속 ①② 구현 + 정적검증.

## 7. Next Action
- 검증패널(pg-restart RESUME 보장/reconcile) → verify-completion → 머지 → 라이브.

## 8. Completion Checklist
- [ ] 정적검증(bash -n/compose config/make -n)
- [ ] FUNCTION/MODIFY/REVIEW/REPORT/TEST 정합
- [ ] STATUS.md 갱신
- [ ] verify-completion PASS
- [ ] commit/push/PR/merge
- [ ] 배포·라이브 검증(pgbouncer ADMIN_USERS 적용 + pg-restart PAUSE→restart→RESUME + reconcile_caddy)
