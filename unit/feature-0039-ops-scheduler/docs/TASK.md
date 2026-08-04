---
doc_type: TASK
feature_id: feature-0039-ops-scheduler
status: active
feature_status: review
feature_status_date: 2026-08-04
feature_status_note: 운영 정기 잡 4종(백업·복원 리허설·AGE 그래프 sync 증분/전량)을 호스트 root crontab → ops-scheduler 컨테이너 서비스로 이관 — docker 소켓 의존 제거(= root 권한 근거 소멸)·스케줄 정본을 compose 환경변수로 이동·§82 flock 은 bind-mount inode 공유로 호스트 routine-backfill 과 상호배제 유지. pg_dump 는 PGDG 16 으로 서버 메이저 고정(client-17 산출물은 PG16 복원 불가 실측). 부수: AGE cutover 이후 5주간 FAIL 하던 PG 복원 리허설 결함 수정(ag_catalog 사전 프로비저닝, 사용자 승인) — 761MB 실백업 전량 복원 PASS
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: review
- Owner: AI
- Priority: high
- Last Updated: 2026-08-04

## 2. Implementation Plan

### 2.1 Plan

- **영향받는 파일:**
  - `docker-compose.yml` — `ops-scheduler` 서비스 신설
  - `unit/feature-0002-agent-core/src/Dockerfile` — `postgresql-client-16`(PGDG) 추가
  - `unit/feature-0002-agent-core/src/scripts/ops_scheduler.py` (신규)
  - `unit/feature-0002-agent-core/src/scripts/ops_backup.sh` (신규)
  - `unit/feature-0002-agent-core/src/scripts/ops_restore_rehearsal.sh` (신규)
  - `unit/feature-0002-agent-core/src/scripts/ops_graph_sync.sh` (신규)
  - `unit/feature-0002-agent-core/src/scripts/healthcheck_ops_scheduler.py` (신규)
  - `unit/feature-0002-agent-core/tests/test_ops_scheduler.py` (신규)
  - `bin/backup.sh` · `bin/restore-rehearsal.sh` — 얇은 래퍼로 전환
  - `bin/metadata-graph-sync.sh` — `ops-scheduler` 우선 대상 + 이관 주석
  - `bin/install-backup-cron.sh` · `bin/install-metadata-graph-sync-cron.sh` — 제거 전용 전환
  - `bin/deploy-web.sh` — `WORKERS` 에 `ops-scheduler` 편입
  - 호스트 root crontab — 해당 4줄 제거 + 이관 주석
- **변경 대상 symbol:** `parse_cron` / `cron_matches` / `load_jobs` / `JobRunner` (신규),
  `WORKERS` (deploy-web.sh), `services.ops-scheduler` (compose)
- **접근 방법:** 잡 로직을 이미지 안으로 옮겨 `docker exec` 의존을 제거하고(= root 권한 근거
  소멸), 스케줄은 compose 환경변수로 선언한다. DB 접속은 `dbnet` 네트워크 클라이언트로
  전환하되 pg_dump 메이저는 서버(16)에 고정한다. AGE sync 의 flock 은 호스트 lock 파일을
  bind-mount 해 inode 를 공유, `bin/routine-backfill.sh` 와의 상호배제를 그대로 보존한다.
- **완료 판정 기준:** FUNCTION.md §2 의 AC-1~4 전건 + 라이브 실측(백업 산출·복원 리허설
  PASS·그래프 sync ok·lock 3-케이스) + root crontab 4줄 제거 확인.
- **위험도:** Major (백업=DR 경로 · 배포 스파인 변경 · 외부 실행주체 이전)

<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-08-04 (AskUserQuestion: 토폴로지=전용 ops-scheduler / crontab=제거+주석 / DR 결함=이번 cycle 수정) -->

## 3. Task Queue
- [x] TASK-20260804T104000-ai-root-f0039-scheduler — 인-컨테이너 스케줄러 + cron 파서
- [x] TASK-20260804T104100-ai-root-f0039-jobs — 잡 스크립트 3종 이식(네트워크 클라이언트)
- [x] TASK-20260804T104200-ai-root-f0039-image — pg client 메이저 정합(PGDG 16)
- [x] TASK-20260804T104300-ai-root-f0039-compose — compose 서비스 + 배포 스파인 편입
- [x] TASK-20260804T104400-ai-root-f0039-host-wrappers — host 래퍼·cron 설치 스크립트 전환
- [x] TASK-20260804T104500-ai-root-f0039-tests — pytest 26건
- [x] TASK-20260804T104600-ai-root-f0039-age-restore-fix — 복원 리허설 AGE 결함 수정
- [x] TASK-20260804T104700-ai-root-f0039-live-verify — 라이브 실측(백업·복원·sync·lock)
- [ ] TASK-20260804T104800-ai-root-f0039-cutover — 배포 후 root crontab 4줄 제거

## 4. In Progress
- 없음

## 5. Blocked
- 없음

## 6. Next Actions
- PR 머지 → `make deploy-workers` (ops-scheduler 포함 롤아웃) → 호스트 crontab 4줄 제거.

## 7. Completion Checklist
- [x] 모든 REQ의 AC가 구현되었다
- [x] 자동 테스트가 통과한다 (신규 26건 · 전 스위트 회귀 0)
- [x] 웹/UI 변경 없음 — UI 표면 0 (compose·스크립트·이미지만) → PB-0008 미해당
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다
- [x] REVIEW.md에 판단 근거가 기록되었다
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] TEST.md에 테스트 결과가 기록되었다
- [x] BLOCKED 항목이 없다
- [x] STATUS.md에 기능 상태가 갱신되었다
- [x] LEARNINGS.md에 발견된 교훈이 기록되었다 (AGE pg_dump --clean 복원 불가)
- [x] ANCHOR.md §1~§3이 채워져 있다
- [ ] `bin/verify-completion.sh --pre-commit feature-0039-ops-scheduler`가 PASS한다
- [ ] Git 커밋/원격 동기화 완료
- [ ] (deploy-backed) 라이브 재배포 검증 — cycle-finalize 후 ops-scheduler healthy + 잡 실행 확인
- [x] 요청 범위 자기-열거 완결성 게이트를 통과했다 (§9)

## 8. Notes
- 이관 전/후 스케줄 등가성은 `test_ops_scheduler.py` 의 `LEGACY_SPECS` 상수가 회귀 가드다.

## 9. Requested Scope

사용자 원 요청: "crontab 내부에 `cd /root/download/docker/mysql_ai_delegated_dev/repo && ...`
로 구성된 부분이 `root` 계정으로 실행되기 보다, 서비스 내부에서 동작되도록 구성해주세요."

대상은 root crontab 의 해당 형태 **4줄** 전부다 (G1 열거 — 항목당 1행, G2 로 개별 확인):

- [x] `0 3 * * * cd <repo> && bin/backup.sh` 를 서비스 내부 실행으로 이관 — 산출물: compose `ops-scheduler.OPS_SCHED_BACKUP` + `/app/scripts/ops_backup.sh`; 실측: 컨테이너 백업 rc=0(761M+46M)
- [x] `30 3 * * 0 cd <repo> && bin/restore-rehearsal.sh` 를 서비스 내부 실행으로 이관 — 산출물: `OPS_SCHED_RESTORE_REHEARSAL` + `ops_restore_rehearsal.sh`; 실측: 전량 복원 rc=0 PASS(PG 67·MySQL 32 테이블)
- [x] `*/30 * * * * cd <repo> && bin/metadata-graph-sync.sh --incremental` 를 서비스 내부 실행으로 이관 — 산출물: `OPS_SCHED_GRAPH_INCREMENTAL` + `ops_graph_sync.sh`; 실측: sync `ok:true errors:0` + 루프 2회 발화
- [x] `17 4 * * * cd <repo> && bin/metadata-graph-sync.sh --full` 를 서비스 내부 실행으로 이관 — 산출물: `OPS_SCHED_GRAPH_FULL`; 실측: `ops_scheduler.py --list` 로 04:17 해석 확인
- [x] 실행 주체에서 `root` 근거 제거 — 산출물: docker 소켓 미사용(소켓 마운트도 안 함) 잡 스크립트 3종; 실측: dbnet 네트워크 클라이언트만으로 전 잡 성공
- [x] §82 동시성 가드가 호스트 `routine-backfill.sh` 와 계속 상호배제 — 산출물: lock bind-mount + `ops_graph_sync.sh` 가드; 실측: 미마운트 rc=1 / 호스트 보유 rc=3 / 정상 rc=0
- [ ] root crontab 해당 4줄 제거 + 이관 안내 주석 — 산출물: crontab 갱신; **배포 직후 수행(잔여)**

범위 밖으로 판정한 crontab 항목(사유는 FUNCTION.md §4): `refresh-claude-oauth-token.sh`
(`cd` 형태 아님 + 호스트 자격증명 파일 조작), `wsl-cleanup.sh` · RDS 제어 · xtrabackup ·
scheduled-inspection · `local-llm-edge` 재시작 (본 프로젝트 repo 밖).

승인 하 추가 범위: PG 복원 리허설 AGE 결함 수정 (FUNCTION.md §11).
