---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, platform, mysql]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0001-platform-runtime
linked_unit: unit/feature-0001-platform-runtime
created: 2026-05-26
sources:
  - ../../unit/feature-0001-platform-runtime/docs/FUNCTION.md
  - ../../docs/ARCHITECTURE.md
---

# Feature — Platform Runtime

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0001-platform-runtime |
| 상태 | active |
| 정본 | [[../../unit/feature-0001-platform-runtime/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | MySQL 설정 · DAB · SQL 유틸리티 · replica 연결 |

## 1. 개요

MySQL 8.0 / DAB 운영 자산과 버전관리 대상 SQL 유틸리티를 관리하는 platform-level feature. 루트 실행 진입점이 본 feature 의 자산을 마운트하여 `make start` / `compose up` 으로 단일 명령 기동을 제공한다.

## 2. 상세

### 2.1 책임 경계

- **입력**: `.env`, `docker-compose.yml`, `Makefile`, `scripts/check_replica.sh`
- **출력**: MySQL 컨테이너 마운트 설정 파일, 운영자 SQL 점검 스크립트, `artifacts/` 경로 계약
- **side-effect**: `artifacts/mysql-data/` 데이터 영속 + `artifacts/shared/logs/` + `artifacts/mysql-backup/`

### 2.2 주요 사양 (FUNCTION.md 추출)

- **AC-0001~0003**: 설정 / SQL / 루트 실행 진입점이 새 구조 따름.
- **REQ-20260512-0003 (TASK-0057)**: `docker-compose.override.yml.example` 로 dev 환경 single TLS termination 회복 — host `localhost:18080` 직접 plain HTTP 가동.
- **REQ-20260515-0003 (TASK-0058)**: `make browser-up` / `make insight-up` 도 `dc-build` 가드 패턴 적용 (buildx provenance race 차단).
- **REQ-20260515-0004 (TASK-0059)**: 5 컨테이너 (`mysql`, `web`, `browser`, `caddy`, `mcp`) `restart: unless-stopped` 정렬.
- **REQ-20260518-0002 (TASK-0064)**: `innodb_redo_log_capacity = 1 GiB` 상향 — redo log saturation 회귀 차단 (MY-014084 / MY-014089).
- **TASK-0045**: replica MySQL 연결 정책 — `replica-net` external network + `REPLICA_DB_*` env + `make replica-check` smoke.

## 3. 특징

- Live game DB 가 아닌 **AI 전용 복제 인스턴스** 만 접근 (design Premise 3).
- `replica-net` external network idempotent 보장 — 복제 미부착 환경에서도 `make up` 정상.
- `innodb_redo_log_capacity` 1 GiB 상향으로 장시간 가동 healthcheck unhealthy 회귀 차단 (디스크 +900 MiB, 메모리 변화 0).

## 4. 사용법

```bash
# 표준 기동
make start

# Replica 연결 smoke
make replica-check

# 상태 확인
make status
```

자세한 운영 명령은 `Makefile` 정본 + `AGENTS.md §운영 명령` 참조.

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- 없음 (다른 feature 가 본 feature 에 의존하는 root)

### 5.2 본 feature 를 의존하는 feature

- [[feature-0004-browser-automation]] — 운영 런타임 공유
- [[feature-0005-qa-mcp]] — Compose / env 공유
- [[feature-0006-lan-proxy-access]] — Web/TLS 운영 자산 공유

## 6. 관련 정본

- [[../../unit/feature-0001-platform-runtime/docs/FUNCTION|FUNCTION.md]]
- [[../../unit/feature-0001-platform-runtime/docs/TASK|TASK.md]]
- [[../../unit/feature-0001-platform-runtime/docs/REPORT|REPORT.md]]

## 7. 관련 노트

- [[../Architecture/Module-Map]] — `unit/feature-0001-platform-runtime/` 위치
- [[../Decisions/ADR-0012-feature-unit-restructure]] — feature 단위 재배치
- [[../Decisions/ADR-0013-shared-runtime-separation]] — runtime artifacts 분리
- [[../Decisions/ADR-0021-kb-postgres-rbac]] — KB Postgres pgvector 가 본 feature 의 compose 에 포함

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0002-agent-core]] · [[feature-0006-lan-proxy-access]]
- 분류: platform / infra

## 9. 외부 link

- [MySQL 8.0 — innodb_redo_log_capacity](https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html#sysvar_innodb_redo_log_capacity)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/platform`
