---
doc_type: MODIFY
feature_id: feature-0015-zd-hygiene-backup
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260630T140000-zd-hygiene-backup
- Date: 2026-06-30
- Related Requirement: REQ-...140000-insight-graceful, ...140001-mysql-online-ddl, ...140002-backup-restorability
- Summary: 백엔드/DB 무중단 위생 ①②⑤ — insight-worker graceful shutdown, MySQL online-DDL 게이트,
  백업 복원 리허설 + cron.
- Files:
  - 수정: `unit/feature-0002-agent-core/src/modules/insight.py`(graceful loop), `docker-compose.yml`
    (insight-worker stop_grace_period 30s), `docs/CONVENTIONS.md`(§13), `Makefile`(3 타깃), `bin/backup.sh`(범위 주석)
  - 신규: `bin/mysql-ddl-lint.sh`, `bin/restore-rehearsal.sh`, `bin/install-backup-cron.sh`,
    `unit/feature-0015-zd-hygiene-backup/docs/*`
- Impact:
  - 비파괴·additive. insight-worker 는 graceful 종료(쓰기 멱등 backstop 유지). mysql-ddl-lint 는 신규
    ALTER 만 diff-mode 강제(기존 grandfathered). backup/restore/cron 은 프로덕션 DB 미접촉(throwaway 복원).
  - 배포: insight-worker rebuild+recreate(사용자 요청경로 아님 → 체감 0), backup cron 설치(호스트).
- Rollback Notes: insight.py revert + insight-worker recreate. lint/스크립트는 신규라 제거만으로 원복.
  cron 은 `bin/install-backup-cron.sh --remove`.
