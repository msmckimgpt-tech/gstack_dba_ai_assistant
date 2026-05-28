---
doc_type: REVIEW
feature_id: feature-0001-platform-runtime
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260518-0001
- Date: 2026-05-18
- Decision: `mysql` 컨테이너의 `innodb_redo_log_capacity` 를 1 GiB (1073741824 bytes) 로 명시 설정. 99-mysql-ai-server.cnf 의 `[mysqld]` 섹션에 한 줄 추가 + trade-off 주석.
- Reason: MySQL 8.0 의 dynamic redo log 기본값 100 MiB 가 본 프로젝트의 write 패턴 (insight-worker 의 KB 집계, agent_memory 의 conversation/message append, share/duplicate 등 transactional 작업 빈도) 에서 장시간 가동 시 saturation 도달. `log_checkpointer` 가 LSN 따라잡지 못해 InnoDB 가 redo log 공간 확보 대기 → write 지연 → mysqladmin ping healthcheck timeout → unhealthy 분류 → `dependency failed to start: container repo-mysql-1 is unhealthy` 로 `make up` / `make web` init 차단. 1 GiB 는 MySQL 8.0+ 의 `innodb_redo_log_capacity` 권장 범위 (100 M ~ 128 G) 내 보수적 상향이며 약 10 배 — 본 프로젝트의 운영 가동 시간 (수 일 ~ 수 주) 동안 saturation 없이 동작.
- 대안 검토:
  - **Alt-A: docker restart 로 매번 reset**: 응급 처치는 가능하나 사용자 가시적 장애 (web init 차단) + 재발 시점이 예측 불가 → 거부.
  - **Alt-B: healthcheck threshold 완화 (interval/timeout/retries 늘림)**: unhealthy 분류 시점만 미루는 미봉책. 실제 write 지연은 그대로 → 거부.
  - **Alt-C: 4 GiB / 8 GiB 등 더 큰 값**: disk 사용량 비례 증가. 본 프로젝트의 write 패턴에는 1 GiB 가 충분하며, 후속 saturation 발생 시점에 정밀 측정 후 추가 상향 가능 → 1 GiB 채택.
- Risk:
  - **디스크 사용량 +900 MiB** (`artifacts/mysql-data/#innodb_redo/` 의 `*.log` 파일들이 최대 1 GiB 까지 동적 할당). artifacts 디스크 여유가 GB 단위로 있다는 전제 — 본 운영 환경에서는 무시 가능.
  - **재기동 시 redo log file resize 시간**: 100 MiB → 1 GiB 동적 resize 는 MySQL 8.0+ 가 background 로 수행. 본 cycle 검증에서 healthcheck 9 초만에 healthy 진입 — 운영 영향 무시 가능.
  - **rollback 시 disk 회수 지연**: `innodb_redo_log_capacity` 를 다시 줄이면 MySQL 이 다음 checkpoint 이후 자동 회수하나 즉시 회수 안 됨. 운영상 문제 없음 (디스크 여유 충분 가정).
  - **본 cycle 이 데이터 영역 무변경 보장**: redo log 는 commit flush buffer 일 뿐 데이터 정본은 `ibdata1` / `*.ibd` (별도 파일). 본 변경으로 데이터 손실 위험 0.
- Trace: REQ-20260518-0002 → TASK-0064 → CHG-20260518-0001 → REV-20260518-0001

## REV-20260515-0004
- Date: 2026-05-15
- Decision: `mysql`, `web`, `browser`, `caddy`, `mcp` 에 `restart: unless-stopped` 를 적용하고, `agent` / `memory-init` 은 restart 대상에서 제외한다.
- Reason: 현재 `make status` 에서 `mcp` 만 실행 중이고 `mysql/web/browser/insight-worker` 가 모두 내려간 상태가 확인됐다. 또한 `insight_worker.log` 에 `2005 (HY000): Unknown MySQL server host 'mysql' (-2)` 오류가 반복되어, 워커 내부 예외가 아니라 compose 네트워크에서 `mysql` 서비스가 사라진 시간이 있었다. 기존 Compose 에서는 장기 실행 서비스 중 `insight-worker` 만 restart policy 를 가지고 있어 Docker daemon/WSL 재시작이나 일시적 프로세스 종료 뒤 나머지 서비스가 자동 복구되지 않는다. `unless-stopped` 는 사람이 명시적으로 멈춘 상태는 존중하면서 비의도 종료와 daemon 재시작 복구를 제공하므로 `make up` 의 기대 동작에 맞다.
- Risk: 명시적 장애 상황에서도 컨테이너가 재시작을 반복할 수 있다. 그러나 MySQL healthcheck 와 서비스 로그로 원인 확인이 가능하고, `make down` / `make stop` 은 명시 중지 의도를 유지한다. `memory-init` 에 restart 를 적용하면 초기화 작업이 반복될 수 있어 제외했다.

## REV-20260515-0003
- Date: 2026-05-15
- Decision: `browser-up` / `insight-up` 도 `web` 타깃과 동일하게 `dc-build` 가드 + `up --no-build` 패턴으로 전환한다.
- Reason: `make browser-up` 실행 중 compose/buildx provenance metadata file race 가 재현됐다. 이미지 빌드는 성공했지만 compose 후처리에서 임시 metadata 파일을 찾지 못해 exit 2로 종료했다. 이미 `Makefile`에는 이 환경 결함을 흡수하는 `dc-build` 가드가 있으므로 같은 원인을 같은 방식으로 처리하는 것이 맞다.
- Risk: `up -d --no-build` 는 직전 `dc-build` 성공을 전제로 한다. `dc-build`가 실제 빌드 오류와 metadata race를 구분하므로, 빌드 실패를 숨기지 않는다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: 운영 자산만 버전관리 대상으로 두고 데이터/로그는 외부 산출물로 분리
- Reason: 기능 단위 추적성과 런타임 안전성 확보
- Risk: 엄격한 운영 검증 시나리오가 아직 없다

## REV-20260528-0001 [SKIPPED:no-rbac-no-schema-no-secret-handling]
- Date: 2026-05-28
- Decision: 99-mysql-ai-server.cnf 에 `log_bin_trust_function_creators = 1` + `local_infile = 1` 추가. backend/frontend/RBAC/DB schema/endpoint contract 무변경.
- Reason: 사용자 명시 요청 (개발 편의). config-only Minor 변경 — 외부 패널 리뷰 불필요.
- Risk: log_bin_trust_function_creators=1 은 binlog 환경에서 SUPER 권한 우회 가능 — 개발 환경 한정 사용 전제. local_infile=1 은 클라이언트 측 파일 인젝션 경로 열림 — 신뢰 클라이언트 환경 전제. 프로덕션 배포 전 재평가 권고.
