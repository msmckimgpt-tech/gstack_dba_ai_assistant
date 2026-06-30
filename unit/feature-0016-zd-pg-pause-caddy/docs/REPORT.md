---
doc_type: REPORT
feature_id: feature-0016-zd-pg-pause-caddy
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
무중단 feasibility "조건부→가능 승격" 2항목: PG pgbouncer PAUSE 래퍼(`bin/pg-restart.sh`)로 PG primary
config/minor 재시작을 near-zero RW 단절화, deploy-web.sh `reconcile_caddy()` 로 Caddyfile 변경 시
caddy 자동 recreate(inode-stale 대응). 정적검증 통과, 배포·라이브 검증 대기.

## 2. Progress
- Done: compose pgbouncer ADMIN_USERS / bin/pg-restart.sh / deploy-web.sh reconcile_caddy / make pg-restart / 정적검증.
- In Progress: 검증패널 → verify-completion → 머지 → 라이브(pgbouncer recreate + pg-restart 실증 + reconcile).

## 3. Recent Changes
- `docker-compose.yml`: pgbouncer `ADMIN_USERS: ${AGENT_KB_PG_USER:-postgres}`(=agent_kb_rw).
- `bin/pg-restart.sh`(신규): PAUSE→restart→RESUME, RESUME trap, PAUSE timeout, healthy 대기, RW probe.
- `bin/deploy-web.sh`: `reconcile_caddy()`(sha 비교→adapt 검증→recreate, 변경 시에만) + main wiring.
- `Makefile`: `pg-restart`.
- 총 변경 횟수: 1 (CHG-20260630T150000)

## 4. Open Issues
- 라이브: pgbouncer ADMIN_USERS 적용엔 pgbouncer **1회 recreate**(짧은 RW blip) 필요 — 이후 pg-restart 는 near-zero.
- pg-restart 의 RESUME 보장(trap)이 안전의 핵심 — 검증패널 우선 확인 대상.
- 보안: agent_kb_rw=admin_users (내부 신뢰, dbnet 전용). 전용 admin user 분리는 후속.

## 5. Test Status
- 정적: bash -n(pg-restart/deploy-web) OK / compose config(ADMIN_USERS=agent_kb_rw) / make -n pg-restart OK /
  caddy adapt(reconcile 검증 경로) OK.
- 라이브(배포 시): pgbouncer admin --check / pg-restart PAUSE→restart→RESUME(RW 무에러 실증) /
  Caddyfile 변경 시 reconcile recreate.

## 6. Git 동기화 결과
- (commit/PR 시 갱신)
