---
doc_type: FUNCTION
feature_id: feature-0039-ops-scheduler
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

운영 정기 잡(플랫폼 논리 백업 · 백업 복원 리허설 · AGE 메타데이터 그래프 동기화)의 실행
주체를 **호스트 root crontab → `ops-scheduler` 컨테이너 서비스**로 옮긴다. 스케줄 정본은
crontab 이 아니라 `docker-compose.yml` 의 `ops-scheduler` 환경변수이며, 잡 로직은 이미지
안(`/app/scripts/ops_*.sh`)에 실린다. 산출물 경로·스케줄 시각·동시성 가드는 이관 전과
동일하게 유지된다.

**왜 root 였는가**: 기존 래퍼(`bin/backup.sh` 등)가 전부 `docker exec` 로 DB 컨테이너에
들어가는 구조였고, 이 호스트는 docker 소켓 접근이 `root` 에만 있다
(`bin/install-metadata-graph-sync-cron.sh` 원 주석이 "반드시 sudo(root crontab)로 실행" 을
요구한 유일한 근거). 잡을 서비스 안으로 옮기면 docker 소켓 의존 자체가 사라져 root 권한
근거가 소멸한다. **반대 방향(컨테이너에 docker 소켓 마운트)은 컨테이너→호스트 root 승격
경로라 채택하지 않았다.**

## 2. Goal

- REQ-20260804-ops-scheduler-in-service: crontab 의 `cd <repo> && bin/*.sh` 형태 4개 항목이
  호스트 `root` 계정이 아니라 서비스 내부에서 실행된다.
- AC-20260804T104000-ops-scheduler-in-service-1: 4개 잡이 이관 전과 **동일한 벽시계 시각**에
  발화한다 (03:00 백업 / 일 03:30 리허설 / 매 30분 증분 sync / 04:17 전량 sync).
- AC-20260804T104000-ops-scheduler-in-service-2: 어떤 잡도 docker 소켓을 요구하지 않는다
  (= root 권한 근거 소멸). 컨테이너에 docker 소켓을 마운트하지도 않는다.
- AC-20260804T104000-ops-scheduler-in-service-3: 그래프 sync 의 §82 동시성 가드가 **호스트에
  남아 있는** `bin/routine-backfill.sh` 와 계속 상호배제된다.
- AC-20260804T104000-ops-scheduler-in-service-4: root crontab 의 해당 4줄이 제거되고, 이관을
  알리는 주석만 남는다 (중복 실행 방지).
- REQ-20260804-restore-rehearsal-age-fix: AGE cutover 이후 실패해 온 PG 복원 리허설이 다시
  PASS 한다 (사용자 승인 하 범위 추가 — 아래 §11 참조).

## 3. In Scope

- `ops-scheduler` compose 서비스 (agent 이미지 재사용, `dbnet` 단독, `../artifacts` 및
  AGE lock 디렉터리 마운트).
- 인-컨테이너 스케줄러 `scripts/ops_scheduler.py` — 5-필드 cron 스펙 해석, 잡별 겹침 방지,
  SIGTERM graceful, heartbeat 기반 healthcheck.
- 잡 스크립트 3종 이식: `ops_backup.sh` · `ops_restore_rehearsal.sh` · `ops_graph_sync.sh`.
- agent 이미지에 `postgresql-client-16`(PGDG) 추가 — pg_dump 를 **서버와 같은 메이저**로 고정.
- 호스트 `bin/backup.sh` · `bin/restore-rehearsal.sh` 를 수동 실행용 얇은 래퍼로 전환.
- `bin/install-*-cron.sh` 2종을 제거 전용(deprecated)으로 전환.
- `bin/deploy-web.sh` 의 `WORKERS` 에 `ops-scheduler` 편입 (배포 시 이미지 핀 동반).
- 복원 리허설의 AGE 사전 프로비저닝 결함 수정.

## 4. Out of Scope

- `bin/routine-backfill.sh` 이관 — cron 미등록(수동 실행)이라 대상 아님. lock 공유로 계속 정합.
- `*/30 refresh-claude-oauth-token.sh` cron 이관 — 호스트 `~/.claude` 자격증명 파일을 직접
  다루므로 컨테이너 내부 실행이 성립하지 않는다 (요청의 `cd <repo> && ...` 형태에도 미해당).
- `wsl-cleanup.sh` · RDS 제어 · xtrabackup · scheduled-inspection 등 본 프로젝트 밖 cron 항목.
- 백업 **범위** 변경 (feature-0015 명시 범위 불변) · PITR/WAL 아카이빙 도입.

## 5. Inputs

- compose 환경변수: `OPS_SCHED_ENABLED` · `OPS_SCHED_BACKUP` · `OPS_SCHED_RESTORE_REHEARSAL` ·
  `OPS_SCHED_GRAPH_INCREMENTAL` · `OPS_SCHED_GRAPH_FULL` · `OPS_SCHED_TICK_SEC`.
- DB 접속 자격: `agent-common` env_file 체인이 주입 (`AGENT_KB_PG_SUPERUSER*` · `DB_HOST` ·
  `MYSQL_ROOT_PASSWORD`). 별도 신규 secret 없음.
- 마운트: `../artifacts` (백업 산출물·잡 로그) · `${OPS_LOCK_DIR}` (AGE sync flock).

## 6. Outputs

- `../artifacts/backups/<timestamp>/{agent_kb.sql.gz, agent_memory.sql.gz}` — 경로·보존정책 불변.
- `../artifacts/backups/cron.log` · `../artifacts/metadata-graph/cron.log` — 경로 불변
  (운영자의 기존 조회 경로 보존). 추가로 `docker logs repo-ops-scheduler-1`.
- `/tmp/ops-scheduler.heartbeat` — healthcheck 판정 소스.
- AGE `metadata_kb` 그래프 갱신 (이관 전과 동일).

## 7. Main Flow

```
compose up -d ops-scheduler
  └─ python /app/scripts/ops_scheduler.py
       ├─ load_jobs()  : env → cron 스펙 파싱 (실패 시 fail-loud exit 2)
       └─ 매 tick(20s) : 현재 분이 스펙에 매칭되면 JobRunner.start()
            ├─ 같은 분 중복 발화 차단 (fired slot)
            ├─ 이전 실행 진행 중이면 skip (겹침 방지)
            └─ subprocess → stdout + 잡별 로그 파일 tee
                 ├─ ops_backup.sh            pg_dump -h postgres / mysqldump -h mysql
                 ├─ ops_restore_rehearsal.sh throwaway DB 복원 검증 후 DROP
                 └─ ops_graph_sync.sh        flock(/opslocks) → metadata_graph_sync.py
```

## 8. Error Handling

| 상황 | 동작 |
|---|---|
| cron 스펙 오류 | 기동 시 fail-loud(exit 2). "조용히 안 도는 잡" 을 만들지 않는다. |
| 잡 프로세스 예외 | 스케줄러는 살아남고 rc 를 로그. 다음 주기에 재시도. |
| 이전 실행 미종료 | 이번 주기 skip + 로그 (겹침 누적 차단). |
| lock 디렉터리 미마운트 | 그래프 sync 는 **실행 거부**(exit 1) — 가드 없이 도는 것보다 안 도는 편이 안전. |
| 호스트가 lock 보유 | skip(exit 3) — `bin/routine-backfill.sh` 와의 상호배제. |
| 백업 산출물이 비정상적으로 작음 | 경고 + exit 1 (이관 전엔 경고만 — fail-loud 로 격상). |
| heartbeat 기록 실패 | 로그만 남기고 스케줄링 계속 (healthcheck 가 이후 stale 로 감지). |

## 9. Dependencies

- feature-0002-agent-core — 이미지·`modules.metadata_graph`·`scripts/` 거주지.
- feature-0015-zd-hygiene-backup — 백업/리허설 원 로직·범위 정의.
- feature-0016-metadata-graph — AGE 그래프 sync·§82 동시성 가드.
- feature-0020-zd-deploy-all — 배포 스파인(`WORKERS` 이미지 핀·롤아웃).

## 10. Constraints

- pg_dump 는 **서버 메이저와 동일**해야 한다. Debian trixie 본 저장소의 client-17 은 산출물에
  PG17 전용 `SET transaction_timeout` 을 넣어 PG16 복원을 깨뜨린다(실측). PGDG 16 고정.
- AGE sync 의 flock 은 **호스트와 같은 파일**이어야 한다 (inode 공유 bind-mount).
- 호스트 cron 과 컨테이너 스케줄러를 병행하면 백업이 하루 2회 실행돼 보존 회전이 절반이 된다 —
  이관은 원자적으로 (배포 후 crontab 제거) 수행한다.

## 11. Pre-approved Changes

- (2026-08-04 사용자 승인) AGE cutover 이후 5주간 FAIL 해 온 PG 복원 리허설 결함 수정을 본
  cycle 범위에 포함. 수정 범위는 **throwaway DB 전용 경로**이며 프로덕션 DB 를 접촉하지 않는다.
