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
### Run 2026-06-30 — Environment: CLI (라이브 배포, 이 호스트 — 사용자 "전체 배포" 승인)
- **TEST-...-1 insight graceful (라이브 실증)**: insight-worker recreate(신 코드 c5356a5) 후 SIGTERM(stop)
  측정 — **stop 18s(<30s grace), ExitCode=0(SIGKILL 아님)**, 로그 3종 출력: "signal 15 수신 — graceful
  shutdown 예약"(handler 발화) + "datasource 루프 조기 종료"(cooperative checkpoint 작동) + "graceful
  shutdown 완료". → graceful 동작 확인.
  - **라이브 적발·수정 2건(정적검증·패널 미포착, 라이브에서만)**: (a) 경계-only graceful 은 긴 cycle 에
    mid-cycle SIGTERM 을 못 끊어 첫 측정 31~32s(SIGKILL 경계) → `run_insight_cycle` 의 per-datasource
    루프에 **협조적 `_INSIGHT_SHUTDOWN` 체크포인트** 추가(부분 cycle 멱등). (b) 워커가 logging 미설정이라
    INFO 로그 비가시 → handler/checkpoint 로그를 `console.print` 로 전환(가시화). 수정 후 18s/exit0/로그 확인.
- **TEST-...-3 restore-rehearsal (라이브 실증)**: `make backup`(agent_kb 250M + agent_memory 32M) →
  `make restore-rehearsal` → **PG throwaway 34 테이블 + MySQL throwaway 29 테이블 복원·검증·DROP, PASS**.
  프로덕션 agent_kb/agent_memory 미접촉, orphan rehearsal DB 0(cleanup trap 확인). agent_memory 32M
  = 비어있지 않음(Web* auth/RBAC/products/datasources/sessions — '거의 빈' 추정 반박).
- **TEST-...-4 cron 멱등 (라이브)**: `install-backup-cron` 2회 → crontab 의 'feature-0015' 항목 정확히 2개
  (매일 03:00 backup + 주간 일 03:30 restore-rehearsal), 무관 항목 보존.

> 위 (a)/(b) 수정은 main 핫픽스(feature-0015 머지 후 라이브 검증 적발 — caddy 핫픽스와 동류)로 반영.

## 4. 미수행 사유
- 라이브 insight graceful recreate / restore-rehearsal 실행 / cron 설치는 docker·DB·crontab 접근이
  필요 → 배포 단계에서 수행·기록.
