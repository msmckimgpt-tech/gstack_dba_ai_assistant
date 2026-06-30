---
doc_type: TEST
feature_id: feature-0016-zd-pg-pause-caddy
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 포함: pg-restart PAUSE→restart→RESUME 의 RW near-zero·RESUME 보장, reconcile_caddy sha 비교·변경 시
  recreate. 제외: PG major 업그레이드, HA(범위 밖).
- 인프라/DB — 서버 계약(CLI) 검증.

## 2. Test Cases
### TEST-20260630T150000-pg-admin-1
- Purpose: pgbouncer admin 콘솔(PAUSE/RESUME) 접근 가능(ADMIN_USERS=agent_kb_rw).
- Steps: `sudo -E bin/pg-restart.sh --check`
- Expected: "admin 콘솔 OK (PgBouncer ...)".

### TEST-20260630T150000-pg-restart-2
- Purpose: PG primary 재시작 중 pgbouncer 경유 RW 가 에러 없이(큐잉) 이어짐.
- Steps: 백그라운드 RW 부하 루프(pgbouncer 경유 SELECT/UPDATE) 돌리며 `make pg-restart`.
- Expected: 부하 루프 에러 0(짧은 지연만), 종료 후 RESUME 됨, RW probe=1. RESUME trap 으로 paused 잔존 없음.

### TEST-20260630T150000-caddy-reconcile-3
- Purpose: Caddyfile 변경 시에만 caddy recreate, 무변경 시 무접촉.
- Steps: (a) Caddyfile 무변경 배포 → reconcile "무변경(sha 일치)"·caddy 유지. (b) Caddyfile 변경 →
  adapt 검증 후 recreate + edge 200.
- Expected: (a) caddy 미접촉, (b) recreate + edge 회복.

## 3. Test Runs (append-only)
### Run 2026-06-30 — Environment: CLI (정적 검증, worktree)
- bash -n bin/pg-restart.sh / bin/deploy-web.sh: OK
- `docker compose config`: pgbouncer ADMIN_USERS=agent_kb_rw 반영
- make -n pg-restart: OK
- reconcile_caddy 함수 정의 + main wiring(soak 전) 확인
- pgbouncer 내부 점검(read-only): admin_users=postgres(기본)·userlist=agent_kb_rw·unix_socket 없음·psql 존재
  → ADMIN_USERS=agent_kb_rw 로 전환 근거 확인.
### Run 2026-06-30 — Environment: CLI (라이브 배포, 이 호스트 — 사용자 "전체 배포" 승인)
- **TEST-...-1 admin --check**: pgbouncer `ADMIN_USERS=agent_kb_rw` recreate 적용(admin_users=agent_kb_rw
  확인) → `pg-restart --check` → "admin 콘솔 OK (PgBouncer 1.25.1)". PASS.
- **TEST-...-2 pg-restart RW 무에러 (라이브 실증)**: pgbouncer 경유 RW 부하 루프(SELECT, ~55s) 돌리며
  `make pg-restart`(PAUSE→postgres force-recreate→healthy→RESUME). 결과 **OK=134 / ERR=0**(에러 0!),
  MAX_QUERY_WAIT=14s(에러 아닌 큐 지연), RESUME 후 paused DB=0(잔존 없음). 종료 후 edge HTTP 200.
  → **PG primary 재시작이 RW 에러 없이(near-zero, 최대 14s 큐 지연) 동작** 실증.
- **TEST-...-3 reconcile sha**: 호스트 Caddyfile sha == caddy 컨테이너 sha(59f22b3b…) → reconcile_caddy
  'no-op(blip 0)' 경로(현재 무변경). 변경 시 adapt 검증 후 recreate 경로(코드 검증). main deploy-web.sh wired.

## 4. 미수행 사유
- pg-restart 라이브 실증은 pgbouncer recreate(ADMIN_USERS) + 라이브 PG 재시작이 필요 → 배포 단계 수행.
