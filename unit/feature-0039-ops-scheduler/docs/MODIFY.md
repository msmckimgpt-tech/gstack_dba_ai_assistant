---
doc_type: MODIFY
feature_id: feature-0039-ops-scheduler
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify History

## CHG-20260804T104000-ai-root-f0039 — 운영 정기 잡 인-컨테이너 이관
- 일시: 2026-08-04 (KST) / 작업자: AI (ai/root/feature-0039-ops-scheduler)
- **신규**
  - `unit/feature-0002-agent-core/src/scripts/ops_scheduler.py` — 5-필드 cron 스케줄러
    (파싱 fail-loud · 잡별 겹침 방지 · SIGTERM graceful · heartbeat).
  - `.../scripts/ops_backup.sh` — `bin/backup.sh` 의 네트워크 클라이언트 이식판.
  - `.../scripts/ops_restore_rehearsal.sh` — `bin/restore-rehearsal.sh` 이식판 **+ AGE 사전
    프로비저닝 수정**.
  - `.../scripts/ops_graph_sync.sh` — flock(호스트 공유) + `metadata_graph_sync.py` 직접 호출.
  - `.../scripts/healthcheck_ops_scheduler.py` — heartbeat 신선도 healthcheck.
  - `unit/feature-0002-agent-core/tests/test_ops_scheduler.py` — 26건.
- **변경**
  - `docker-compose.yml` — `ops-scheduler` 서비스 추가(agent 이미지·`dbnet` 단독·
    `../artifacts` 및 `${OPS_LOCK_DIR}` 마운트·healthcheck·`restart: unless-stopped`).
  - `unit/feature-0002-agent-core/src/Dockerfile` — PGDG `postgresql-client-16` 추가
    (서버 16.14 와 메이저 정합; trixie 기본 client-17 은 PG16 복원을 깨뜨림).
  - `bin/backup.sh` · `bin/restore-rehearsal.sh` — 수동 실행용 얇은 래퍼로 전환
    (`docker exec <ops-scheduler>`). `make backup` / `make restore-rehearsal` 무회귀.
  - `bin/metadata-graph-sync.sh` — 대상 컨테이너에 `ops-scheduler` 우선 추가 + 이관 주석.
  - `bin/install-backup-cron.sh` · `bin/install-metadata-graph-sync-cron.sh` — install 경로
    폐지(deprecated, exit 2 안내), `--remove` / `--print` 만 유지.
  - `bin/deploy-web.sh` — `WORKERS` 에 `ops-scheduler` 편입(배포 시 이미지 핀·롤아웃 동반).
- **호스트 상태 변경(코드 밖)**: root crontab 의 `# feature-0015 zd-backup` 2줄 +
  `# feature-0016 metadata-graph-sync` 2줄 제거 + 이관 안내 주석 1줄 추가.

## CHG-20260804T104600-ai-root-f0039-age-restore — 복원 리허설 AGE 결함 수정
- 일시: 2026-08-04 (KST) / 작업자: AI / 승인: 사용자 (2026-08-04 AskUserQuestion)
- `ops_restore_rehearsal.sh`: throwaway DB 생성 직후 `CREATE EXTENSION IF NOT EXISTS age`
  실행. `pg_dump --clean` 산출물의 `DROP EXTENSION IF EXISTS age;` 가 빈 DB 에서
  `ERROR: schema "ag_catalog" does not exist` 로 실패하던 것을 해소
  (AGE 가 `shared_preload_libraries` 로 올라온 서버에서 utility 훅이 `ag_catalog` 를 무조건
  조회해 `IF EXISTS` 가 단락되지 않음).
- 영향: feature-0016 AGE cutover(2026-06-30) 이후 **5주간 FAIL** 하던 주간 PG 복원 리허설이
  PASS 로 회복 (라이브 실측: 사용자 테이블 67개 복원). 프로덕션 DB 미접촉.

## CHG-20260804T115000-ai-root-f0039-panel-hardening — §18.8 codex 패널 지적 수정
- 일시: 2026-08-04 (KST) / 작업자: AI / 근거: REVIEW.md `REV-20260804T115000` [CODEX:review]
- `Makefile` — `up` 의 build 목록·이미지 검증 루프·기동 블록에 `ops-scheduler` 편입
  (`ENABLE_OPS_SCHEDULER=0` 로만 비활성). 빠지면 신규·재부팅 환경에서 정기 잡 전면 정지.
- `docker-compose.yml` — ① 마운트를 `../artifacts` 전체 → `backups`·`metadata-graph` 2개로 축소
  (그 아래 `mysql-data`·`postgres-data`·`postgres-replica-data`·`minio-data` 라이브 데이터 보호),
  ② `depends_on` 을 mysql·postgres 로 override(무관한 gateway/MinIO unhealthy 가 스케줄러를
  막지 않게), ③ `stop_grace_period` 60s→300s + `OPS_SCHED_SHUTDOWN_GRACE_SEC=280`.
- `ops_scheduler.py` — ① SIGTERM 시 진행 잡을 유예까지 **기다린 뒤** terminate(배포 recreate 가
  백업 회차를 죽이던 경로), ② dom/dow 무제한 판정을 값 집합 → **문법(`*`)** 기준으로 교정
  (`parse_cron` 반환형이 `(집합, 무제한여부)` 튜플로 변경).
- `ops_backup.sh` — ① `<ts>.partial` staging 후 무결성 통과 시에만 rename(부분 산출물이 보존
  회전을 잡아먹어 정상 백업을 밀어내던 경로 차단), ② MySQL 암호를 argv → `--defaults-extra-file`
  (0600) + `2>/dev/null` 제거로 실패 원인이 로그에 남게 함.
- `ops_restore_rehearsal.sh` — 동일 defaults-file 적용 + 최신 백업 선택 시 `.partial` 제외.
- `tests/test_ops_scheduler.py` — 회귀 3건 추가(문법 기준 무제한 판정 2 · 유예 내 완주 1) → 29건.
