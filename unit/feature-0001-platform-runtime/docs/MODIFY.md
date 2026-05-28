---
doc_type: MODIFY
feature_id: feature-0001-platform-runtime
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260518-0001
- Date: 2026-05-18
- Related Requirement: TASK-0064, REQ-20260518-0002
- Summary: TASK-0064 (Major §12.3 — mysql 컨테이너 server 설정 변경) `mysql` 의 `innodb_redo_log_capacity` 를 기본 100 MiB → 1 GiB 로 상향. MySQL 8.0+ 의 dynamic redo log 가 기본 100 MiB 한계에서 장시간 가동 시 saturation (`MY-014084 Threads are unable to reserve space in redo log`, `MY-014089 Redo log writer is waiting for a new redo log file`) 으로 healthcheck 가 unhealthy 분류되어, `make up` / `make web` 의 `init` step 이 `dependency failed to start: container repo-mysql-1 is unhealthy` 로 차단되던 운영 회귀를 차단.
- 발견 경위: TASK-0063 (feature-0003 conv-item menu) commit 직후 사용자 요청으로 `make web` 표준 호출 시 init step fail 재현 → `docker logs repo-mysql-1` 에 redo log saturation 경고가 수 초 간격으로 지속 출력, `Up 2 days (unhealthy)` 상태 확인. `docker restart repo-mysql-1` 으로 saturation reset 후 healthy 회복 가능하나, 장시간 가동 시 재발 — 본 cycle 에서 근본 fix 진행 (사용자 결정).
- Files:
  - `repo/unit/feature-0001-platform-runtime/src/mysql/conf.d/99-mysql-ai-server.cnf` — `[mysqld]` 섹션에 `innodb_redo_log_capacity = 1073741824` 추가. 회귀 사유 (MY-014084 / MY-014089) + trade-off (디스크 +900 MiB, 메모리 변화 0, 데이터 정본 무변경) 주석 한 단락 동봉.
  - `repo/unit/feature-0001-platform-runtime/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` — REQ-20260518-0002 / AC-0022~AC-0025 / TASK-0064 / CHG-20260518-0001 / REV-20260518-0001 entries.
  - `repo/docs/STATUS.md` — feature-0001 row 갱신 + 상단 prose entry.
- Verification:
  - `docker compose restart mysql` 후 healthcheck 9 초만에 `Up (healthy)` 진입.
  - `SELECT @@innodb_redo_log_capacity;` → `1073741824` (= 1.00 GiB) 확인.
  - `make up` 완주 — memory-init "메모리 테이블 초기화 완료" 출력, 5 컨테이너 (mysql healthy / web / browser / insight-worker / mcp) 모두 Up.
  - Endpoint smoke: Web UI `http://localhost:18080` HTTP 200 (18.8 KB), MCP `http://localhost:28000` HTTP 200.
- Impact: mysql 컨테이너 server 설정 변경. 데이터 정본 (`ibdata1`, `*.ibd`) 무변경 — `ib_logfile*` 만 1 GiB 까지 동적 resize. 운영 환경 적용 시 `docker compose restart mysql` 또는 `make restart` 만 필요. rollback 안전 (`innodb_redo_log_capacity` 줄이는 것도 동적 — 단 안 줄어든 상태에선 disk 회수까지 시간 필요).
- Trace: REQ-20260518-0002 → TASK-0064 → CHG-20260518-0001 → REV-20260518-0001

## CHG-20260515-0005
- Date: 2026-05-15
- Related Requirement: TASK-0060, REQ-20260515-0004
- Summary: TASK-0059 구현 커밋 이후 Git 동기화 결과를 `REPORT.md` 에 기록하고, 현재 공개 브랜치 scope 불일치로 원격 push/PR 갱신을 보류 처리.
- Files: `unit/feature-0001-platform-runtime/docs/{TASK,MODIFY,REPORT}.md`
- Impact: 구현 내용 변경 없음. `issue/26-lazy-create-routing-fix` 브랜치는 현재 요청(`make up` 컨테이너 안정화)과 이름/issue scope 가 맞지 않아, unrelated hotfix 를 기존 PR branch 에 push 하지 않도록 보류 사유를 문서화했다.
- Verification: `bash bin/verify-completion.sh --pre-commit feature-0001-platform-runtime`

## CHG-20260515-0004
- Date: 2026-05-15
- Related Requirement: TASK-0059, REQ-20260515-0004
- Summary: `make up` 으로 활성화한 장기 실행 컨테이너가 내려간 뒤 자동 복구되지 않는 문제를 막기 위해 Compose restart policy 를 정렬.
- Files: `docker-compose.yml`, `unit/feature-0001-platform-runtime/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`
- Impact: `mysql`, `web`, `browser`, `caddy`, `mcp` 에 `restart: unless-stopped` 를 적용했다. 기존 `insight-worker` 정책과 일치하며, Docker daemon/WSL 재시작 또는 일시적 프로세스 종료 후 장기 실행 서비스가 내려간 상태로 방치될 가능성을 줄인다. `agent` 와 `memory-init` 은 일회성/수동 실행 컨테이너라 restart 대상에서 제외했다.
- Verification: `make up`, `make status`, `make browser-health`

## CHG-20260515-0003
- Date: 2026-05-15
- Related Requirement: TASK-0058, REQ-20260515-0003
- Summary: `browser-up` / `insight-up` 에서도 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 를 흡수하도록 기존 `dc-build` 가드 패턴 적용.
- Files: `Makefile`, `unit/feature-0001-platform-runtime/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`
- Impact: `make browser-up` 과 `make insight-up` 이 `dc-build SERVICE=...` 로 이미지를 먼저 만들고 `up -d --no-build` 로 기동한다. web 타깃과 같은 root-cause 대응이라 metadata file 후처리 race 때문에 서비스 복구가 실패하지 않는다.
- Verification: `make browser-up`, `make insight-up`, `make status`

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: MySQL/DAB/SQL 유틸리티를 템플릿 feature 구조로 이관
- Files: src/mysql/conf.d/*, src/dab/dab-config.json, src/sql/*
- Notes: 런타임 데이터는 `../../../../artifacts`로 분리

## CHG-20260415-0002
- Date: 2026-04-15
- Summary: 내장 Local LLM bootstrap 스크립트를 제거해 플랫폼 runtime 경계를 MySQL 전용으로 복구
- Files: src/local-llm/init_ollama_models.sh
- Notes: Local LLM provider는 현재 repo가 아니라 외부 `/root/download/docker/local_llm` 에서 관리한다

## CHG-20260423-0003
- Date: 2026-04-23
- Summary: AI 전용 복제 MySQL 인스턴스 연결용 compose 네트워크 + env placeholder + smoke check 스크립트 추가 (TASK-0045)
- Files: docker-compose.yml, .env.example, Makefile, scripts/check_replica.sh, unit/feature-0001-platform-runtime/docs/FUNCTION.md, unit/feature-0001-platform-runtime/docs/TASK.md
- Notes: 네이밍은 과제 프롬프트의 `REPLICA_MYSQL_*` 가 아니라 기존 `modules/config.py` / `modules/db.py` (TASK-0044) 에서 이미 사용 중인 `REPLICA_DB_*` 를 유지 — primary 의 `DB_*` prefix 와 parallel 하고, 기존 agent-core 라우팅 로직을 재사용하기 위함. 누락되어 있던 `REPLICA_DB_NAME` 만 신설. 복제본 자체의 replication 설정 / 초기 full dump / 동기화 주기 / 조직 보안 정책은 repo 범위 밖이며, 본 변경은 접속 레이어(네트워크 + 자격증명 placeholder + connectivity probe) 만 담당.

## CHG-20260424-0001
- Date: 2026-04-24
- Related Requirement: TASK-0046 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — platform-runtime 책임 경계, `artifacts/` 분리 원칙, 대안(IaC/docker-root) 분기, replica 점검 시나리오.
- Files: unit/feature-0001-platform-runtime/docs/ANCHOR.md, unit/feature-0001-platform-runtime/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. 향후 요청이 platform-runtime §1-§3과 충돌하면 Conflict Protocol 발화 대상.
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 또는 feature 폐지 필요.

## CHG-20260512-0002
- Date: 2026-05-12
- Related Requirement: TASK-0057, REQ-20260512-0003
- Summary: dev 환경 가동 시 single TLS termination 원칙 회복 — web 컨테이너의 self-signed HTTPS 자체 가동을 dev 한정으로 plain HTTP 로 override 하여 gstack `/qa` / `/browse` / playwright 등 browser 자동화 도구의 TLS 차단 해소. 사용자 follow-up: TASK-0055 QA 진행 중 web 의 self-signed cert 가 browse 데몬을 차단해 정적 검증 fallback 이 필요했던 issue 의 root cause 해결.
- Files: docker-compose.override.yml.example (신규, template — `entrypoint` override 로 plain HTTP 가동), .gitignore (실 사용 파일 `docker-compose.override.yml` 추가), CONTRIBUTING.md (§10 신설 "Dev 환경 가동 — single TLS termination 원칙"), unit/feature-0001-platform-runtime/docs/TASK.md (TASK-0057 entry), unit/feature-0001-platform-runtime/docs/MODIFY.md (본 entry), unit/feature-0001-platform-runtime/docs/REPORT.md (Summary prepend), docs/STATUS.md (feature-0001 entry 갱신).
- Diff size: 신규 docker-compose.override.yml.example 28 lines, CONTRIBUTING.md +33 lines, .gitignore +4 lines.
- Impact: 개발자 머신마다 `cp docker-compose.override.yml.example docker-compose.override.yml && make web` 1회 setup 으로 host `localhost:18080` 이 plain HTTP 가동. browser 자동화 도구가 env var · opt-in 옵션 추가 없이 자연 동작. gstack-upgrade 마다 별도 patch 적용 불필요. production / staging 환경 영향 0 — production compose 파일에 override 를 두지 않으면 무시 (Caddy frontline TLS 종단 그대로 유지).
- Rollback Notes: `mv docker-compose.override.yml docker-compose.override.yml.disabled` 후 `make web` 재기동하면 base compose 의 entrypoint 분기로 복귀해 `ENABLE_WEB_TLS=1` (`.env` 기본) self-signed HTTPS 가동. revert 시점에 .gitignore + CONTRIBUTING.md §10 만 git revert 로 되돌리면 template 만 남고 dev 가동은 기존 HTTPS 로 유지.

## CHG-20260528-0001
- Date: 2026-05-28
- Related Requirement: TASK-0124, REQ-20260528-0001
- Summary: MySQL 서버 설정 파일에 개발 편의 옵션 2종 영구 추가 — `log_bin_trust_function_creators = 1` (binlog 활성화 환경에서 SUPER 권한 없이 stored function/procedure 생성 허용) + `local_infile = 1` (클라이언트 측 LOAD DATA LOCAL INFILE 허용). runtime `SET GLOBAL` 은 이미 사용자 측에서 적용 완료된 상태이며, 본 변경은 다음 컨테이너 재시작 시 자동 영구 적용되도록 설정 파일에 반영.
- Files:
  - `repo/unit/feature-0001-platform-runtime/src/mysql/conf.d/99-mysql-ai-server.cnf` — `[mysqld]` 섹션 하단에 2개 옵션 추가 (dev convenience 주석 동봉).
- Notes: 개발 편의 목적 설정. 프로덕션 환경 사용 시 security posture 재평가 권고 (log_bin_trust_function_creators 는 SUPER 우회, local_infile 은 클라이언트 인젝션 경로). 본 변경은 컨테이너 재시작 없이 적용되지 않음 — 사용자 요청으로 즉시 restart 는 보류.
