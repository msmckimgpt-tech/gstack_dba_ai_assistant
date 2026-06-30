---
doc_type: REPORT
feature_id: feature-0015-zd-hygiene-backup
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
feature-0014 후속 무중단 위생 ①②⑤ 구현. ① insight-worker SIGTERM graceful, ② MySQL online-DDL
강제 게이트, ⑤ 백업 범위 명시 + 복원 리허설 + 정기 cron. 무중단 feasibility 분석(wf_1d634d33)의
"저비용·고효과" 권고를 코드화. 정적검증 통과, 배포 대기.

## 2. Progress
- Done: ①②⑤ 코드 + 정적검증(py_compile/bash -n/lint self-test/make -n/compose config 전부 OK).
- In Progress: 검증 패널 → verify-completion → 머지 → 배포(insight recreate + cron 설치).

## 3. Recent Changes
- `insight.py`: `_INSIGHT_SHUTDOWN` + `_install_insight_signal_handlers` + `while not is_set` +
  interruptible `_INSIGHT_SHUTDOWN.wait` (signal alias 로 지역변수 충돌 회피).
- `docker-compose.yml`: insight-worker `stop_grace_period: 30s`.
- `bin/mysql-ddl-lint.sh`(신규, diff-mode), `docs/CONVENTIONS.md §13`, `Makefile`(mysql-ddl-lint/
  restore-rehearsal/install-backup-cron 타깃).
- `bin/backup.sh`(범위 주석), `bin/restore-rehearsal.sh`(신규), `bin/install-backup-cron.sh`(신규).
- 총 변경 횟수: 1 (CHG-20260630T140000)

## 4. Open Issues
- 배포: insight-worker recreate(graceful 검증) + cron 설치는 **main repo 에서** 실행해야 cron 경로가
  올바름(worktree 경로 아님). 배포 단계에서 처리.
- 후속(미포함): ③ pgbouncer PAUSE 래퍼, PG WAL/PITR, bedrock-gateway 2-replica — feasibility 분석의
  "투자 필요" 항목, 별 cycle.

## 5. Test Status
- 정적: insight py_compile OK / 3 신규 스크립트 bash -n OK / mysql-ddl-lint self-test 4/4 /
  install-backup-cron --print OK / make -n(3타깃) OK / compose config exit=0.
- 라이브(배포 시): insight-worker graceful recreate 관찰, restore-rehearsal 실행 PASS, cron 설치 확인.

## 6. Git 동기화 결과
- (commit/PR 시 갱신)
