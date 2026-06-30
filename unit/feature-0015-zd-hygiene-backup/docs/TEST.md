---
doc_type: TEST
feature_id: feature-0015-zd-hygiene-backup
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 포함: insight-worker graceful shutdown, mysql-ddl-lint 게이트 동작, restore-rehearsal 복원 검증,
  cron 설치 멱등성. 제외: HA/DB 엔진 무중단(범위 밖).
- 인프라/백엔드라 화면(UI) 검증 대상 아님 — 서버 계약(CLI) + 라이브 동작.

## 2. Test Cases
### TEST-20260630T140000-insight-graceful-1
- Purpose: insight-worker 가 SIGTERM 시 진행 cycle 경계에서 우아 종료(SIGKILL 대기 없이).
- Steps: insight-worker recreate(force-recreate) 시 로그에 "graceful shutdown" + grace 내 종료 관찰.
- Expected: stop_grace_period(30s) 내 정상 종료, 다음 부팅 정상 cycle.

### TEST-20260630T140000-mysql-ddl-lint-2
- Purpose: bare MySQL ALTER 적발, LOCK=NONE/PG/서명 escape 통과.
- Steps: `bash bin/mysql-ddl-lint.sh --self-test`
- Expected: 4 케이스 PASS.

### TEST-20260630T140000-restore-rehearsal-3
- Purpose: 최신 백업이 throwaway DB 로 복원되고 행 검증 통과, 프로덕션 미접촉.
- Steps: `make backup` → `make restore-rehearsal`
- Expected: PG/MySQL 모두 임시 DB 복원 + 테이블≥1 + 임시 DB DROP, PASS.

### TEST-20260630T140000-cron-idempotent-4
- Purpose: cron 설치 멱등(중복 추가 없음).
- Steps: `bin/install-backup-cron.sh` 2회 → `crontab -l | grep -c 'feature-0015'`
- Expected: 항상 2줄(중복 없음).

## 3. Test Runs (append-only)
### Run 2026-06-30 — Environment: CLI (정적 검증, worktree)
- insight.py py_compile: OK. graceful 구조(`_INSIGHT_SHUTDOWN`/handler/`while not is_set`/`wait`) 확인.
- bin/mysql-ddl-lint.sh: bash -n OK, self-test 4/4 PASS, diff-mode(현재 변경 신규 MySQL ALTER 0) 통과.
- bin/restore-rehearsal.sh / install-backup-cron.sh: bash -n OK.
- install-backup-cron --print: 항목 2개 + 현재 crontab 출력(변경 없음).
- make -n mysql-ddl-lint/restore-rehearsal/install-backup-cron: OK.
- compose config(insight stop_grace_period 30s 반영): exit=0.
### Run (예정) — Environment: CLI (배포 시, 이 호스트)
- TEST-...-1/3/4 (insight graceful recreate, restore-rehearsal 실행, cron 멱등) — 배포 단계 기록.

## 4. 미수행 사유
- 라이브 insight graceful recreate / restore-rehearsal 실행 / cron 설치는 docker·DB·crontab 접근이
  필요 → 배포 단계에서 수행·기록.
