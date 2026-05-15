---
doc_type: FUNCTION
feature_id: feature-0001-platform-runtime
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
템플릿 사본에서 MySQL/DAB 운영 자산과 버전관리 대상 SQL 유틸리티를 관리한다.

## 2. Goal
- REQ-0001: 루트 중심 운영 자산을 기능 단위 구조로 이관한다.
- REQ-0002: 런타임 산출물과 버전관리 자산의 경계를 분리한다.
- REQ-20260512-0003 (TASK-0057): dev 환경 가동 시 single TLS termination 원칙 회복 — host `localhost:18080` 직접 접근 시 web 컨테이너가 plain HTTP 로 가동되어 browser 자동화 도구 (gstack `/qa`, `/browse`, playwright e2e) 가 추가 옵션 없이 자연 동작한다. production / staging 환경 (Caddy frontline TLS 종단) 영향 0.
  - AC-0011: `docker-compose.override.yml.example` template 이 repo root 에 존재하며, web 서비스의 entrypoint 를 `["/bin/sh", "-c", "exec uvicorn web.app:app --host 0.0.0.0 --port 8000"]` 으로 override 한다.
  - AC-0012: `.gitignore` 에 `docker-compose.override.yml` 가 포함되어 실 사용 파일은 환경별 (gitignore) 로 관리된다.
  - AC-0013: `CONTRIBUTING.md §10` "Dev 환경 가동 — single TLS termination 원칙" 섹션이 개발자 onboarding 가이드 (1회 setup + 정합 원칙 + production-like 검증 방법) 를 제공한다.
  - AC-0014: override 적용 후 `curl http://localhost:18080/admin` HTTP 200 응답 + uvicorn 로그 `Uvicorn running on http://0.0.0.0:8000` 출력 + admin 정적 자산 cache-bust 정상 반영.
  - AC-0015: override 미적용 환경 (production / staging compose 파일에 override 미포함) 에서는 base compose 의 entrypoint 분기로 복귀해 self-HTTPS 가동 가능 — production 정합 영향 0.
- REQ-20260515-0003 (TASK-0058): docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 가 `browser-up` / `insight-up` 에서도 재발하지 않도록 기존 `dc-build` 가드 패턴을 적용한다.
  - AC-0016: `make browser-up` 은 `dc-build SERVICE=browser` 후 `up -d --no-build browser` 로 기동한다.
  - AC-0017: `make insight-up` 은 `dc-build SERVICE=insight-worker` 후 `up -d --no-build insight-worker` 로 기동한다.

## 3. In Scope
- MySQL `conf.d` 설정 파일
- DAB 설정 파일
- 버전관리 대상 SQL 유틸리티 스크립트
- `../../../../artifacts` 경계에 맞는 운영 문서화

## 4. Out of Scope
- 실제 MySQL 데이터 파일
- 세션, 로그, 인증서 파일 내용
- 도메인 검증 시나리오 작성

## 5. Inputs
- `../../../.env`
- `docker-compose.yml`
- `Makefile`
- `../../../scripts/check_replica.sh`

## 6. Outputs
- MySQL 컨테이너에 마운트되는 설정 파일
- 운영자가 재사용할 SQL 점검 스크립트
- `../../../../artifacts` 기준 경로 계약

## 7. Main Flow
1. 루트 실행 파일이 feature 경로의 설정 자산을 참조한다.
2. `make start`가 `../../../../artifacts` 디렉토리를 준비한다.
3. MySQL이 새 경로 기준으로 기동한다.

## 8. Edge Cases
- `../../../../artifacts/mysql-data`가 없으면 Makefile이 먼저 생성한다.
- 인증서 디렉토리가 없으면 `make web-tls-cert`가 생성한다.

## 9. Error Handling
- 경로 누락 시 Makefile이 생성 후 재시도한다.
- MySQL 기동 실패는 compose 상태와 로그로 확인한다.

## 10. Dependencies
### 내부 기능 의존성
- 없음

### 외부 의존성
- Docker Compose
- MySQL 8.0 이미지

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-0001: 설정 파일이 `src/mysql/conf.d`와 `src/dab` 아래로 이관되어 있다.
- AC-0002: SQL 유틸리티가 `src/sql` 아래로 이관되어 있다.
- AC-0003: 루트 실행 파일이 이 기능 경로만 참조한다.

## 12. Observability
- 로그는 `../../../../artifacts/shared/logs`
- 백업은 `../../../../artifacts/mysql-backup`

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 설정 파일 이관
- AI 전용 복제 MySQL 인스턴스 접속용 env/compose/check 스크립트 추가

## 14. 복제 MySQL 연결 정책 (TASK-0045)
AI DBA 는 라이브 게임 DB 가 아닌 **AI 전용 복제 인스턴스** 에만 접근한다 (design doc Premise 3). 본 기능은 복제본 자체의 생성·replication 동기화 (binlog/GTID/덤프 주기 등) 는 다루지 않으며, agent 컨테이너가 이미 존재하는 복제본에 도달할 수 있도록 repo 쪽 **런타임 접속 레이어** (compose 네트워크 + env 자리 + smoke check) 만 담당한다. 네이밍은 기존 agent-core 가 `modules/config.py` / `modules/db.py` 에서 사용 중인 `REPLICA_DB_*` 컨벤션 (primary 의 `DB_*` 와 parallel) 을 유지한다.

연결은 두 레이어로 구성된다. (a) **네트워크 레이어**: `docker-compose.yml` 에 external network `replica-net` (기본 이름 `replica-net`, `REPLICA_NETWORK_NAME` env 로 override 가능) 를 선언하고 `agent` / `insight-worker` / `web` 서비스에 연결한다. `Makefile::ensure-replica-network` 가 idempotent 로 네트워크를 보장하므로 복제본을 아직 붙이지 않은 배포에서도 `make up` 이 깨지지 않는다. (b) **자격증명 레이어**: `.env` 의 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` / `REPLICA_DB_NAME` 을 통해 agent-core 가 `modules/db.py::connect()` 에서 data-plane 쿼리(`database != MEMORY_DB`) 를 복제 인스턴스로 라우팅한다. 실제 값은 `.env` 또는 docker-compose secret 으로만 주입하고 commit 에 포함하지 않는다. smoke check 는 `make replica-check` (내부적으로 `scripts/check_replica.sh`) 로 agent 컨테이너 안에서 `SELECT 1` 을 수행한다.
