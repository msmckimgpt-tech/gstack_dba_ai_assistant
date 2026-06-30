---
doc_type: TASK
feature_id: feature-0015-zd-hygiene-backup
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude) / Human approved (①+②+⑤)
- Priority: high
- Last Updated: 2026-06-30

## 2. Implementation Plan
### 2.1 Plan
- **영향 파일:** `unit/feature-0002-agent-core/src/modules/insight.py`, `docker-compose.yml`(insight-worker),
  `bin/mysql-ddl-lint.sh`(신규), `docs/CONVENTIONS.md §13`, `Makefile`, `bin/backup.sh`,
  `bin/restore-rehearsal.sh`(신규), `bin/install-backup-cron.sh`(신규), 본 feature docs.
- **접근:** ① ask.py 의 `_install_signal_handlers` 패턴을 insight 에 복제(signal alias 로 지역변수 충돌 회피)
  + stop_grace_period 30s. ② diff-mode online-DDL lint(migrate-lint 동형) + 컨벤션. ⑤ 백업 범위 명시 +
  throwaway-DB 복원 리허설 + 멱등 cron.
- **위험도:** Major (worker 배포 + DB 복원 스크립트 + cron/호스트). 비파괴·additive.

<!-- PLAN-APPROVED by ms.mckim.gpt (user) on 2026-06-30 — "①+②+⑤ 항목을 진행해주세요" -->

## 3. Task Queue
- [x] TASK-20260630T140100-insight-graceful: insight-worker SIGTERM graceful + stop_grace_period
- [x] TASK-20260630T140101-mysql-ddl-lint: online-DDL 게이트 + CONVENTIONS §13 + make
- [x] TASK-20260630T140102-backup-restorability: 범위 명시 + restore-rehearsal + cron + make
- [ ] TASK-20260630T140103-deploy: insight-worker recreate(graceful) + backup cron 설치(main repo)

## 4. In Progress
- 정적검증 완료 → 검증 패널 → commit/PR/merge/deploy.

## 5. Blocked
- 없음 (PLAN-APPROVED).

## 6. Done
- 무중단 feasibility 분석(wf_1d634d33) → ①②⑤ 도출 + 구현 + 정적검증.

## 7. Next Action
- 검증 패널(restore-rehearsal/insight) → verify-completion → 머지 → 배포.

## 8. Completion Checklist
- [ ] 단위/정적 검증 통과 (py_compile/bash -n/lint self-test/compose config/make -n)
- [ ] FUNCTION/MODIFY/REVIEW/REPORT/TEST 정합
- [ ] STATUS.md 갱신
- [ ] verify-completion PASS
- [ ] commit/push/PR/merge
- [ ] 배포(insight recreate + cron 설치) — 라이브 검증 기록
