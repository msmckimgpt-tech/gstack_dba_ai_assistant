---
doc_type: MODIFY
feature_id: feature-0016-zd-pg-pause-caddy
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260630T150000-zd-pg-pause-caddy
- Date: 2026-06-30
- Related Requirement: REQ-...150000-pg-pause-restart, REQ-...150001-caddy-reconcile
- Summary: PG pgbouncer PAUSE 래퍼(near-zero PG 재시작) + deploy-web.sh Caddyfile reconcile(변경 시 caddy recreate).
- Files:
  - 수정: `docker-compose.yml`(pgbouncer ADMIN_USERS), `bin/deploy-web.sh`(reconcile_caddy + wiring), `Makefile`(pg-restart)
  - 신규: `bin/pg-restart.sh`, `unit/feature-0016-zd-pg-pause-caddy/docs/*`
- Impact:
  - pg-restart: 라이브 PG/pgbouncer path. RESUME trap 보장이 안전 핵심(실패 시 RW 차단). PAUSE timeout 으로
    긴 트랜잭션 시 fail-safe(abort+RESUME). config/minor 한정(major 정비창).
  - ADMIN_USERS 적용은 pgbouncer 1회 recreate 필요(짧은 blip, 일회성).
  - reconcile_caddy: 변경 시에만 recreate(무변경 blip 0), adapt 검증 후라 깨진 config 로 caddy 안 죽임.
- Rollback Notes: pg-restart.sh 제거(신규)·Makefile/compose ADMIN_USERS revert. reconcile_caddy 는
  deploy-web.sh 함수 제거 + main 호출 1줄 제거. 모두 additive·비파괴.
