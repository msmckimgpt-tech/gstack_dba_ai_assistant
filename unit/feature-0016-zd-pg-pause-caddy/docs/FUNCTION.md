---
doc_type: FUNCTION
feature_id: feature-0016-zd-pg-pause-caddy
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
무중단 feasibility 분석(wf_1d634d33)의 "조건부→가능 승격" 2항목 구현:
- **PG pgbouncer PAUSE 래퍼** (`bin/pg-restart.sh`): pgbouncer(transaction-mode)를 PAUSE 해 신규 RW
  쿼리를 에러 대신 큐잉시킨 채 PG primary 를 재시작(config/minor)하고 RESUME → near-zero RW 단절.
- **deploy-web.sh Caddyfile reconcile**: Caddyfile 변경 시(host vs caddy 컨테이너 sha 불일치)만 caddy 를
  recreate(WSL2 bind-mount inode-stale 대응 — reload 로는 옛 내용 재독). 무변경 시 무접촉(blip 0).

## 2. Goal
- REQ-20260630T150000-pg-pause-restart: PG primary config/minor 재시작을 RW 에러 없이(큐잉) 수행.
- REQ-20260630T150001-caddy-reconcile: 배포 시 Caddyfile 변경을 자동 반영(변경 시에만 recreate).

## 3. In Scope
- `docker-compose.yml` pgbouncer `ADMIN_USERS=${AGENT_KB_PG_USER}`(=agent_kb_rw, userlist 보유 → admin
  콘솔 PAUSE/RESUME 인증 가능. 기본 admin_users=postgres 는 userlist 부재로 불가였음).
- `bin/pg-restart.sh`: 컨테이너 내 psql 로 admin(비밀번호 호스트 미노출), **RESUME trap 보장**, PAUSE
  timeout, postgres healthy 대기, pgbouncer 경유 RW probe. `make pg-restart`.
- `bin/deploy-web.sh` `reconcile_caddy()`: sha 비교 → 변경 시 caddy adapt 검증 후 recreate + edge 회복 대기.

## 4. Out of Scope
- PG major 업그레이드/데이터 호환 단계(정비창 필요). DB 엔진 HA/failover(단일 호스트 SPOF — 범위 밖).
- 전용 pgbouncer admin user 분리(현재 agent_kb_rw 재사용 — 하드닝 후속).

## 5. Inputs / 6. Outputs
- pg-restart: (in) restart action(기본 postgres force-recreate) → (out) PAUSE→restart→RESUME, RW 큐잉으로 무에러.
- reconcile_caddy: (in) 호스트 Caddyfile sha vs caddy 컨테이너 sha → (out) 다르면 검증·recreate, 같으면 no-op.

## 7. Main Flow
- PG config 변경: `make pg-restart` → pgbouncer PAUSE → postgres recreate → healthy → RESUME → RW 정상.
- 배포 중 Caddyfile 변경: deploy-web.sh 가 자동 감지→검증→recreate(변경 시에만).

## Pre-approved Changes
- 사용자 승인(2026-06-30): "PG pgbouncer PAUSE 래퍼" + "deploy-web.sh Caddyfile recreate 자동화" 진행.
- deploy_scope: included. 배포 영향: pgbouncer 1회 recreate(ADMIN_USERS 적용 — 짧은 RW blip),
  이후 pg-restart 는 near-zero. reconcile_caddy 는 변경 시에만.

> 보안 메모: agent_kb_rw 를 pgbouncer admin_users 로 — 내부 신뢰 role + dbnet 전용이라 수용. 전용 admin
> 분리는 하드닝 후속.
