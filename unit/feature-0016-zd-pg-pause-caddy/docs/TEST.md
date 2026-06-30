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
### Run (예정) — Environment: CLI (배포 시, 이 호스트)
- TEST-...-1/2/3 (admin --check, pg-restart RW 무에러 실증, reconcile) — 배포 단계 기록.

## 4. 미수행 사유
- pg-restart 라이브 실증은 pgbouncer recreate(ADMIN_USERS) + 라이브 PG 재시작이 필요 → 배포 단계 수행.
