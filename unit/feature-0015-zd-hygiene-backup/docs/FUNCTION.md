---
doc_type: FUNCTION
feature_id: feature-0015-zd-hygiene-backup
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
feature-0014(web 무중단) 후속 — 백엔드/DB 계층의 무중단 위생 + 데이터 보존을 보강한다.
무중단 feasibility 분석(워크플로 wf_1d634d33)이 도출한 "지금 저비용·고효과" 3항목(①②⑤):
① insight-worker SIGTERM graceful, ② MySQL online-DDL 강제, ⑤ 백업 갭(복원 리허설+cron) 정비.

## 2. Goal
- REQ-20260630T140000-insight-graceful: insight-worker 가 SIGTERM 시 진행 cycle 을 루프 경계에서
  마치고 우아 종료(불필요 중단/LLM 낭비/healthcheck flap 제거). 멱등성은 기존 backstop 유지.
- REQ-20260630T140001-mysql-online-ddl: 신규 MySQL ALTER 가 online(LOCK=NONE) 강제 — silent
  COPY-lock 차단(단일 인스턴스 DML 무중단).
- REQ-20260630T140002-backup-restorability: 백업 범위 명시(sandbox 의도적 제외) + 복원 리허설 +
  정기 cron — 단일 인스턴스의 실질 위험(데이터 보존) 대응.

## 3. In Scope
- insight.py `run_insight_worker_loop` graceful shutdown(`_INSIGHT_SHUTDOWN` + signal alias +
  interruptible wait) + compose `insight-worker.stop_grace_period: 30s`.
- `bin/mysql-ddl-lint.sh`(diff-mode online-DDL 게이트) + CONVENTIONS §13 + `make mysql-ddl-lint`.
- `bin/restore-rehearsal.sh`(throwaway DB 복원 검증) + `bin/install-backup-cron.sh`(멱등) +
  backup.sh 범위 주석 + `make restore-rehearsal`/`install-backup-cron`.

## 4. Out of Scope
- HA(멀티 호스트/노드, 자동 failover, 오케스트레이터) — 단일 사용자 내부도구엔 over-engineering(분석 결론).
- DB 엔진 무중단 재시작/메이저 업그레이드, 호스트/커널 무중단(단일 호스트 SPOF 라 원천 불가).
- pgbouncer PAUSE 래퍼(③), PG WAL/PITR(later), bedrock-gateway 2-replica — 후속 후보.
- 기존 MySQL ALTER 사이트 retrofit(grandfathered — try/except 멱등 가드라 LOCK=NONE 추가 시 silent-skip 위험).

## 5. Inputs / 6. Outputs
- ① SIGTERM/SIGINT → `_INSIGHT_SHUTDOWN` → 루프 경계 종료.
- ② origin/main 대비 신규 MySQL ALTER → lint 통과/차단.
- ⑤ 최신 `../artifacts/backups/*` → throwaway DB 복원 → 행 검증 → DROP → PASS/FAIL; cron 항목 설치.

## 7. Main Flow
- 무중단 코드 변경: insight-worker 도 이제 ask-worker 처럼 graceful recreate.
- 무중단 스키마: 신규 MySQL ALTER 는 lint 가 online 강제; PG 는 §12 alembic 게이트.
- 데이터 보존: 매일 backup + 주간 restore-rehearsal(cron).

## Pre-approved Changes
- 사용자 승인(2026-06-30): "①+②+⑤ 항목을 진행". deploy_scope: included(전역 상속).
- 배포 영향: insight-worker rebuild+recreate(graceful, 사용자 요청경로 아님 → 체감 0) + backup cron 설치(호스트).
