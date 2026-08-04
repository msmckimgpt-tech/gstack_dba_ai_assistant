---
doc_type: TEST
feature_id: feature-0039-ops-scheduler
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope

- **포함**: cron 스펙 해석의 이관 등가성 · 잡 레지스트리·킬스위치 · 겹침 방지 · 잡 로그 경로 ·
  heartbeat · 컨테이너 실행 e2e(백업 산출 / 복원 리허설 / 그래프 sync) · flock 호스트-컨테이너
  상호배제 3-케이스.
- **제외**: 백업 *범위* 자체(feature-0015 정본) · AGE 그래프 sync 로직(feature-0016 정본) ·
  UI 표면(본 feature 는 UI 표면 0 → PB-0008 미해당).

## 2. Test Cases

### TEST-20260804T104000-ops-scheduler-1 — 이관 등가성(스케줄)
- Purpose: 4개 잡이 이관 전 crontab 과 **동일 시각**에 발화한다.
- Preconditions: `unit/feature-0002-agent-core/tests/test_ops_scheduler.py` 의 `LEGACY_SPECS`.
- Steps: 분 단위로 창을 훑어 발화 시각 목록을 산출·대조.
- Expected: 03:00 매일 / 03:30 **일요일만** / `*/30` 은 :00·:30 / 04:17 매일.

### TEST-20260804T104000-ops-scheduler-2 — 스펙 오류 fail-loud
- Purpose: 잘못된 cron 스펙이 "조용히 안 도는 잡" 이 되지 않는다.
- Steps: 필드 수·범위·step·비수치·역순 범위 8종 주입.
- Expected: 전부 `CronSpecError`.

### TEST-20260804T104000-ops-scheduler-3 — 겹침 방지
- Purpose: 이전 실행이 진행 중이면 이번 주기는 skip.
- Steps: 장수명 잡 기동 후 `JobRunner.start()` 재호출.
- Expected: 두 번째 호출이 `False`.

### TEST-20260804T104000-ops-scheduler-4 — flock 호스트↔컨테이너 상호배제
- Purpose: §82 동시성 가드가 이관 후에도 `bin/routine-backfill.sh`(호스트)와 성립한다.
- Steps: (a) lock 미마운트 (b) 호스트가 flock 보유 중 (c) 자유 상태 — 각각 컨테이너 실행.
- Expected: (a) exit 1 fail-loud (b) exit 3 skip (c) exit 0 정상 sync.

### TEST-20260804T104000-ops-scheduler-5 — 컨테이너 백업/복원 e2e
- Purpose: 네트워크 클라이언트 전환 후에도 백업이 산출되고 **복원된다**.
- Steps: 컨테이너에서 `ops_backup.sh` → `ops_restore_rehearsal.sh`.
- Expected: 두 덤프 생성 + throwaway DB 복원 후 객체 수 ≥ 1 + 임시 DB 정리.

### TEST-20260804T104000-ops-scheduler-7 — dom/dow 무제한 판정은 문법 기준
- Purpose: `1-31` 처럼 값이 전 범위여도 `*` 가 아니면 제한 필드로 본다(vixie-cron 규칙).
- Steps: `0 0 1-31 * 0` 이 평일에도 매칭되는지 + `0 0 * * 0` 대조군.
- Expected: 전자는 매일 매칭, 후자는 일요일만.

### TEST-20260804T104000-ops-scheduler-8 — 백업 staging 원자성
- Purpose: 실패한 부분 산출물이 '완료 백업' 으로 보이지 않는다.
- Steps: 백업 실행 후 디렉터리 확인 + `.partial` 미끼를 두고 리허설 대상 선택 확인.
- Expected: 완료 시 `.partial` 잔존 0, 리허설이 `.partial` 을 고르지 않음.

### TEST-20260804T104000-ops-scheduler-6 — mysqldump 클라이언트 등가성
- Purpose: 이미지의 MariaDB 계열 `mysqldump` 가 MySQL 8.0 서버 내장본과 동등한 DDL 을 낸다.
- Steps: 네트워크 덤프와 `docker exec` 서버-내장 덤프의 `CREATE TABLE`~`) ENGINE` 구간 diff.
- Expected: 바이트 동일.

## 3. Test Runs

### Run 2026-08-04 — 단위 (pytest)
- Environment: `CLI`
- Command: `python3 -m pytest unit/feature-0002-agent-core/tests/test_ops_scheduler.py -q`
- Result: **26 passed** (TEST-…-1/2/3 커버)

### Run 2026-08-04 — 라이브 컨테이너 e2e
- Environment: `CLI` (컨테이너 실행 — 본 feature 는 UI 표면 0 이라 Windows-browser 미해당)
- 이미지: 본 브랜치 Dockerfile 빌드 (`pg_dump 16.14` / `mysqldump 11.8.6-MariaDB`)

| 항목 | 결과 |
|---|---|
| `ops_scheduler.py --list` | 4잡 정상 해석 (03:00 / 일 03:30 / `*/30` / 04:17) |
| `ops_backup.sh` | rc=0 — `agent_kb.sql.gz` 761M · `agent_memory.sql.gz` 46M |
| `ops_restore_rehearsal.sh` (AGE fix 전) | rc=1 — `ERROR: schema "ag_catalog" does not exist` **(이관 전 호스트 cron 과 동일 — 등가성 확인)** |
| `ops_restore_rehearsal.sh` (AGE fix 후) | **rc=0 PASS** — PG 사용자 테이블 67개 · MySQL 32개 · 임시 DB 정리 |
| `ops_graph_sync.sh --incremental` (lock 미마운트) | rc=1 fail-loud |
| `ops_graph_sync.sh --incremental` (호스트 lock 보유) | rc=3 skip |
| `ops_graph_sync.sh --incremental` (정상) | rc=0 — `ok:true, errors:0, duration_ms 437` |
| 스케줄러 루프 e2e (매분 스펙, 75s) | 11:20:28 · 11:21:02 두 회 발화 + 잡 로그 파일 기록 확인 |
| mysqldump DDL diff (네트워크 vs 서버-내장) | **IDENTICAL** (콜레이션 `utf8mb4_0900_ai_ci` 보존) |
| pg_dump 17 vs 16 (사전 조사) | 17 산출물은 PG16 복원 시 `transaction_timeout` 로 rc=3 → **16 고정 근거** |

### Run 2026-08-04 — §18.8 codex 패널 지적 수정 후 재검증
- Environment: `CLI` (컨테이너 실행)
- 대상: P1-1~5 · P2-1 · P2-3 수정본 (REVIEW.md REV-20260804T115000 참조)

| 항목 | 결과 |
|---|---|
| pytest (신규 케이스 3건 포함) | **29 passed** |
| `ops_backup.sh` (staging→rename, defaults-file) | rc=0 · `.partial` 잔존 0 · 761M+46M |
| `ops_restore_rehearsal.sh` (`.partial` 미끼 배치 후) | rc=0 **PASS** — 완료 백업만 선택(`20260804_114053`), PG 67·MySQL 32 |
| `docker compose config` 렌더 | 마운트 `backups`·`metadata-graph` 2개로 축소 · `depends_on` mysql/postgres 2개 · `stop_grace_period 5m0s` · `OPS_SCHED_SHUTDOWN_GRACE_SEC=280` |
| shell 문법(`bash -n`) 8파일 | PASS |

### Run 2026-08-04 — 전 스위트 회귀
- Environment: `CLI`
- Command: `make test` (격리 compose 프로젝트 — 라이브 네트워크 미참여)
- Result: **3,647건 중 실패 0 · 오류 0** (3,645 passed / 2 skipped) · `ruff check` All checks passed

## 4. Regression Notes

- `LEGACY_SPECS` 상수가 이관 전 crontab 4줄의 스케줄을 그대로 담는다. 스케줄을 바꾸려면
  compose 환경변수와 이 상수를 **함께** 바꿔야 하므로, 무의식적 스케줄 드리프트가 적색이 된다.
- 복원 리허설의 AGE 사전 프로비저닝은 cutover 전 환경에서도 안전하다(실패 시 경고 후 계속).
