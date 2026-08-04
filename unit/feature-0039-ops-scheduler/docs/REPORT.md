---
doc_type: REPORT
feature_id: feature-0039-ops-scheduler
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

운영 정기 잡 4종(백업 · 복원 리허설 · AGE 그래프 sync 증분/전량)을 호스트 root crontab 에서
**`ops-scheduler` 컨테이너 서비스**로 이관했다. root 권한의 유일한 근거였던 `docker exec`
의존이 사라졌고, 스케줄 정본이 호스트 crontab(버전관리 밖)에서 `docker-compose.yml`(버전관리
안)로 이동했다. 산출물 경로·스케줄 시각·§82 동시성 가드는 모두 이관 전과 동일하다.

부수적으로, 이관 등가성 검증 과정에서 **AGE cutover 이후 5주간 FAIL 하고 있던 PG 복원
리허설 결함**을 발견·수정했다(사용자 승인 하 범위 추가).

## 2. 현재 상태

| 항목 | 상태 |
|---|---|
| 코드·문서 | 완료 |
| 단위 테스트 | 신규 26건 PASS |
| 라이브 컨테이너 e2e | 백업·복원·sync·lock 3케이스 전건 실측 PASS |
| PR / 머지 | 진행 예정 |
| 배포(ops-scheduler 기동) | 미수행 |
| root crontab 4줄 제거 | 미수행 (배포 직후 수행) |

## 3. 변경 요지

- 신규: `scripts/ops_scheduler.py` · `ops_backup.sh` · `ops_restore_rehearsal.sh` ·
  `ops_graph_sync.sh` · `healthcheck_ops_scheduler.py` · `tests/test_ops_scheduler.py`
- compose: `ops-scheduler` 서비스 (agent 이미지 · `dbnet` 단독 · `../artifacts` +
  `${OPS_LOCK_DIR}` 마운트 · heartbeat healthcheck)
- 이미지: PGDG `postgresql-client-16` 추가 (서버 16.14 와 메이저 정합)
- 호스트: `bin/backup.sh` · `bin/restore-rehearsal.sh` → 얇은 래퍼 / `bin/install-*-cron.sh`
  2종 → 제거 전용(deprecated) / `bin/deploy-web.sh` `WORKERS` 에 `ops-scheduler` 편입

## 4. 라이브 실측 근거

| 검증 | 결과 |
|---|---|
| `ops_backup.sh` | rc=0 — `agent_kb.sql.gz` 761M · `agent_memory.sql.gz` 46M |
| `ops_restore_rehearsal.sh` | rc=0 **PASS** — PG 사용자 테이블 67개 · MySQL 32개 |
| `ops_graph_sync.sh --incremental` | rc=0 — `ok:true, errors:0` |
| lock: 미마운트 / 호스트 보유 / 정상 | rc=1 fail-loud / rc=3 skip / rc=0 실행 |
| 스케줄러 루프 e2e | 매분 스펙으로 2회 발화 + 잡 로그 파일 기록 확인 |
| mysqldump DDL 등가성 | 서버 내장본과 **바이트 동일** |

## 5. 남은 리스크

- **이관 창 중복 실행**: 배포 ~ crontab 제거 사이에 백업이 2회 돌 수 있다(보존 회전 소모).
  배포 직후 즉시 제거해 창을 최소화한다.
- **PGDG 빌드 의존**: `apt.postgresql.org` 불가 시 이미지 빌드 실패(→ web 배포까지 영향).
  기존 deb.debian.org / PyPI 와 동급 노출이며 빌드 시점 fail-loud.
- **서버 메이저 업그레이드 시 핀 동반 필요**: PG 17 로 올릴 때 Dockerfile 의
  `postgresql-client-16` 을 함께 올리지 않으면 복원 불가가 조용히 재발한다
  (ADR-20260804T104200 에 명시).

## 6. 후속 작업 (본 cycle 밖)

- `bin/routine-backfill.sh` 도 서비스 내부로 이관할지 검토 (현재는 cron 미등록 수동 실행,
  lock 공유로 정합 유지 중).
- AGE 그래프(`metadata_kb`) 데이터가 덤프·복원 왕복에서 온전한지(행 수 대조) 별도 검증 —
  이번 리허설은 객체 수 sanity 까지만 확인했다.

## 7. Git 동기화 결과

- 커밋: (아래 PR 참조)
- verify-completion: PASS
- Push / main 병합: PR 경유
- 충돌 해결: 없음

## 8. 개선 제안 (기록만 — §8.1)

- 주간 복원 리허설이 5주간 FAIL 이었는데도 아무도 몰랐다. `cron.log` 를 사람이 안 본다는 뜻이며,
  리허설 FAIL 을 관리 콘솔 알림이나 헬스 신호로 승격하는 것을 제안한다(구현은 미실행).
