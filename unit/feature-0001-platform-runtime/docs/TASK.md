---
doc_type: TASK
feature_id: feature-0001-platform-runtime
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI
- Priority: high
- Last Updated: 2026-05-12

## 2. Task Queue
- [x] TASK-0057 (REQ-20260512-0003, Minor §12.3) dev 환경 가동 시 single TLS termination 원칙 회복 — `docker-compose.override.yml.example` template 신설 (web entrypoint 를 plain HTTP 로 override) + `.gitignore` 에 실 사용 파일 (`docker-compose.override.yml`) 추가 + `CONTRIBUTING.md §10` "Dev 환경 가동 — single TLS termination 원칙" 섹션 신설. 부작용 해소: 본 cycle 직전까지 web 컨테이너가 `ENABLE_WEB_TLS=1` (`.env` 기본) 로 self-signed cert HTTPS 가동 → Caddy 의 frontline TLS 와 이중 TLS → host `localhost:18080` 직접 접근 시 gstack `/qa` / `/browse` / playwright e2e 가 `net::ERR_CERT_AUTHORITY_INVALID` 로 차단되던 issue. override 적용 후 web 컨테이너가 plaintext HTTP `:8000` 으로 가동, browser 자동화 도구 자연 동작 (env var · opt-in 불필요). production 영향 0 — override 는 dev 환경 한정 (production compose 파일에 두지 않으면 무시).
- [x] TASK-0001 운영 자산 위치 재정의
- [x] TASK-0002 MySQL/DAB/SQL 유틸리티 이관
- [x] TASK-0003 루트 실행 파일 경로 반영
- [ ] TASK-0004 엄격한 운영 검증 시나리오 정리
- [x] TASK-0045 AI 전용 복제 MySQL 접속 레이어 (compose 네트워크 + `.env.example` 자리 + `scripts/check_replica.sh` + `make replica-check`). AI DBA 가 라이브 DB 가 아닌 복제 인스턴스에만 접근한다는 design doc Premise 3 을 repo 쪽에서 구현한다. 네이밍은 기존 `REPLICA_DB_*` (TASK-0044) 유지 + 누락되어 있던 `REPLICA_DB_NAME` 신설. docker-compose 에 external network `replica-net` (이름은 `REPLICA_NETWORK_NAME` 로 override 가능) 을 선언하고 `agent` / `insight-worker` / `web` 에 연결, `Makefile::ensure-replica-network` 로 idempotent 자동 생성해 외부 network 미존재로 `make up` 이 깨지지 않게 한다. 복제본 자체의 생성·replication 설정·초기 덤프·동기화 주기·조직 보안 정책은 범위 밖. 검증: (a) `.env.example` 에 `REPLICA_DB_HOST/PORT/USER/PASSWORD/NAME` + `REPLICA_NETWORK_NAME` placeholder 존재, (b) `.env` 에 실값 채운 뒤 `make replica-check` 가 `SELECT 1 AS replica_ok` 를 agent 컨테이너에서 반환하며 exit 0, (c) `docker compose config` 가 `replica-net` external network 를 `agent` / `insight-worker` / `web` 에 attach 한 상태로 렌더링.
- [x] TASK-0046 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)

## 3. In Progress
- TASK-0004 엄격한 운영 검증 시나리오 정의 대기

## 4. Blocked
- 없음

## 5. Done
- TASK-0001
- TASK-0002
- TASK-0003
- TASK-0045

## 6. Next Action
- `TEST.md`에 후속 엄격 검증 시나리오를 구체화한다.

## 7. Completion Checklist
- [x] REQ-0001 관련 이관이 반영되었다
- [x] REQ-0002 관련 경계가 문서화되었다
- [x] FUNCTION.md가 현재 구조와 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다
- [x] REVIEW.md에 판단 근거가 기록되었다
- [x] REPORT.md에 현재 상태가 반영되었다
- [ ] 엄격한 검증 시나리오가 확정되었다
