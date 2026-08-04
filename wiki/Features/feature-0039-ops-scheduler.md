---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki, ops]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0039-ops-scheduler
linked_unit: unit/feature-0039-ops-scheduler
created: 2026-08-04
sources:
  - ../../unit/feature-0039-ops-scheduler/docs/FUNCTION.md
---

# Feature — 운영 정기 잡 인-컨테이너 스케줄러 (ops-scheduler)

> 사람용 입구. 정본: [[../../unit/feature-0039-ops-scheduler/docs/FUNCTION|FUNCTION.md]].

## 목차

- [한 줄 요약](#한-줄-요약)
- [상태](#상태)
- [책임 경계](#책임-경계)
- [운영 메모](#운영-메모)
- [관련 정본](#관련-정본)
- [관련 노트](#관련-노트)
- [Open questions](#open-questions)

## 한 줄 요약

백업·복원 리허설·AGE 그래프 동기화 같은 정기 운영 잡을 호스트 root crontab 대신 `ops-scheduler`
컨테이너 서비스가 돌린다 — 스케줄 정본이 `docker-compose.yml` 로 옮겨와 배포와 함께 따라간다.

## 상태

- 단계: review (코드·문서·라이브 e2e 완료 / 배포 + crontab 제거 잔여)
- 마지막 갱신: 2026-08-04

## 책임 경계

- 입력: compose 환경변수 `OPS_SCHED_*` (cron 스펙) · `agent-common` env_file 의 DB 자격 ·
  마운트 `../artifacts`, `${OPS_LOCK_DIR}`
- 출력: `../artifacts/backups/<ts>/*.sql.gz` · `cron.log` 2종 · AGE `metadata_kb` 갱신 ·
  `docker logs repo-ops-scheduler-1`
- side-effect: 프로덕션 DB 는 **읽기 전용**(pg_dump/mysqldump). 복원 리허설은 throwaway DB
  생성·DROP 만 수행하며 `agent_kb`/`agent_memory` 를 접촉하지 않는다.

## 운영 메모

- 잡을 잠시 멈추려면 `OPS_SCHED_ENABLED=0` (전체) 또는 해당 `OPS_SCHED_*` 를 빈 문자열(개별).
- 수동 1회 실행은 여전히 `make backup` / `make restore-rehearsal` /
  `bin/metadata-graph-sync.sh` — 내부적으로 `ops-scheduler` 컨테이너에 exec 한다.
- pg_dump 는 **서버 메이저에 핀**되어 있다. PG 를 17 로 올리면 Dockerfile 의
  `postgresql-client-16` 도 함께 올려야 한다(안 그러면 복원 불가가 조용히 재발).
- AGE 그래프 sync 의 flock 은 호스트 `bin/routine-backfill.sh` 와 **같은 파일**을 공유한다.
  lock 디렉터리 마운트가 빠지면 sync 는 실행을 거부한다(fail-loud).

## 관련 정본

- [[../../unit/feature-0039-ops-scheduler/docs/FUNCTION|FUNCTION]]
- [[../../unit/feature-0039-ops-scheduler/docs/TASK|TASK]] (active)
- [[../../unit/feature-0039-ops-scheduler/docs/REPORT|REPORT]]
- [[../../unit/feature-0039-ops-scheduler/docs/DECISIONS|DECISIONS]] — ADR 3건

## 관련 노트

- [[feature-0015-zd-hygiene-backup]] — 백업/리허설 원 로직·범위
- [[feature-0016-metadata-graph]] — AGE 그래프 sync·§82 동시성 가드
- [[feature-0020-zd-deploy-all]] — 배포 스파인(WORKERS 이미지 핀)
- [[../Architecture/Module-Map]]

## Open questions

- `bin/routine-backfill.sh` 도 서비스 내부로 옮길 것인가 (현재 호스트 수동 실행, lock 공유로 정합).
- 복원 리허설 FAIL 을 로그 밖 신호(알림·health)로 승격할 것인가 — 5주간 아무도 못 본 전례 있음.
