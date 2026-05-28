---
doc_type: ARCHITECTURE
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.15.0
domain: [architecture]
ai_read_priority: 4
---

# Architecture

## 1. 전체 구조
저장소는 크게 다음 영역으로 나뉜다.

- 공통 정책: `../AGENTS.md`, `./*`
- 기능 단위 구현: `../unit/<feature-id>/`
- 공통 코드 예약 영역: `../shared/`
- 파생 산출물: `../../artifacts/*`
- 환경값 정본 의미: `../.env` (원본 루트 `.env` 의미 유지)

## 2. 책임 분리
### 공통 정책 영역
프로젝트 전반에 적용되는 규칙, 제약, 용어, 보안 기준을 정의한다.

### 기능 영역
기능별 코드, 테스트, 명세, 변경 이력, 리뷰, 보고를 관리한다.

### 공통 코드 영역 (shared/)
여러 기능에서 공통으로 사용하는 코드가 생길 때만 사용한다.

### 산출물 영역
빌드 결과, 로그, MySQL 데이터, 세션 파일, 인증서 등 런타임 파생 결과를 저장한다.

## 3. 기능 단위 구조 원칙
각 기능은 아래 하위 구조를 가진다.
- `src/` : 기능 구현
- `tests/` : 기능 테스트
- `docs/` : 기능 문서

## 4. 현재 기능 맵
| 기능 ID | 책임 |
|---------|------|
| feature-0001-platform-runtime | MySQL 설정, DAB 설정, SQL 유틸리티 |
| feature-0002-agent-core | agent CLI 및 코어 모듈 + KB Postgres 최적화 (T1~T5, 2026-05-28) |
| feature-0003-agent-web-ui | FastAPI Web UI 및 정적 자산 + **audit subsystem (TASK-0073)** — `WebAuditEvents` + `record_audit_event` dispatcher + admin 11 / user 5 endpoint hook + `audit.*` 4 RBAC + chunked PK purge. SECURITY.md §9 정합. |
| feature-0004-browser-automation | Playwright 브라우저 제어 |
| feature-0005-qa-mcp | MCP 테스트와 QA 스크립트 |
| feature-0006-lan-proxy-access | Caddy 및 Windows LAN 프록시 자산 + `_get_client_ip` X-Forwarded-For trust 정책 (SECURITY.md §9.7) |

## 5. source of truth 원칙
동일한 사실을 여러 문서에 중복 확정하지 않는다.
- 기능의 현재 동작: `FUNCTION.md`
- 작업 진행 상태: `TASK.md`
- 최근 진행 요약: `REPORT.md`
- 변경 기록: `MODIFY.md`
- 판단 근거: `REVIEW.md`
- 의사결정: `DECISIONS.md`
- 프로젝트 전체 현황: `STATUS.md`

## 6. 기능 간 의존성 맵
| 기능 ID | 의존 대상 | 의존 유형 | 비고 |
|---------|----------|----------|------|
| feature-0003-agent-web-ui | feature-0002-agent-core | uses | Web UI가 코어 모듈을 import |
| feature-0003-agent-web-ui | feature-0006-lan-proxy-access | uses | TASK-0073: `_get_client_ip` X-Forwarded-For trust 가 Caddy `trust_forwarded_for` / `trusted_proxies` 설정에 의존 (SECURITY.md §9.7) |
| feature-0004-browser-automation | feature-0001-platform-runtime | uses | 운영 런타임과 함께 구동 |
| feature-0005-qa-mcp | feature-0001-platform-runtime | uses | Compose와 환경값 공유 |
| feature-0005-qa-mcp | feature-0002-agent-core | uses | 에이전트/MCP 모드 검증 |
| feature-0005-qa-mcp | feature-0004-browser-automation | uses | 브라우저 제어 smoke 검증 |
| feature-0006-lan-proxy-access | feature-0001-platform-runtime | uses | Web/TLS 운영 자산 공유 |

### 의존 유형 정의
- `requires`: 대상 기능이 완성되어야 구현 가능
- `uses`: 대상 기능의 API/인터페이스를 사용하지만 독립 개발 가능
- `extends`: 대상 기능을 확장하는 관계

## 7. KB Postgres 성능 최적화 레이어 (2026-05-28)

T1~T5 로드맵 완수 후의 Postgres 데이터 경로 구성.

### 7.1 쿼리 최적화 (T1)
- `_load_top_facts_pg()`: NOT EXISTS O(N²) → `DISTINCT ON` + covering index (`ix_fact_entries_conv_scope_key_rank`)
- `_build_knowledge_payload()`: N+1 루프 → `ANY(array)` 단일 쿼리 (local+global 통합)

### 7.2 스키마 최적화 (T2)
- `agent_memory_facts`: regular VIEW → **MATERIALIZED VIEW** (CONCURRENTLY refresh 지원)
- `category_join_hints_json`: TEXT → **JSONB** + GIN index
- `texts.embedding`: partial ivfflat index (WHERE embedding IS NOT NULL)

### 7.3 인프라 최적화 (T3)
- PgBouncer transaction-mode sidecar (`edoburu/pgbouncer`, `pgbouncer:5432`)
- PostgreSQL 서버 파라미터 전면 조정 (shared_buffers, WAL, checkpoint 등)
- `pg_stat_statements` + `kb_slow_queries` view + autovacuum scale_factor=0

### 7.4 Lock / 캐시 최적화 (T4)
- Advisory lock: MySQL GET_LOCK → `pg_try_advisory_lock(hashtext(name))`
- 캐시 무효화: TTL 폴링 → `kb_invalidations` 테이블 + `pg_notify` groundwork
- `_is_refresh_due()` PG 무효화 플래그 연동

### 7.5 Replica 분리 (T5)
- `postgres-replica` streaming replica 서비스 (profile: replica)
- `AGENT_KB_PG_HOST_RO` / `AGENT_KB_PG_PORT_RO` 환경변수로 read-only 라우팅

## 8. 통합 테스트 정책
- 현재 단계에서는 구조/기동 검증 위주로 운영한다.
- 엄격한 도메인 시나리오는 기능별 `docs/TEST.md`를 정본으로 후속 작성한다.
- 통합 테스트 자동화가 생기면 `../tests/integration/`로 승격한다.

## 8. 확장 원칙
- 기능 간 공통성이 반복되면 공통 모듈로 승격을 검토한다.
- 구조 변경이 필요한 경우 프로젝트 수준 `DECISIONS.md`에 남긴다.

## 9. artifacts 조직 규칙
`/artifacts/`는 재생성 가능한 파생 결과물을 저장한다.

### 9.1 디렉토리 구조
```
artifacts/
├── build/              # 빌드 산출물
├── reports/            # 생성된 보고서
├── exports/            # 내보내기 파일
├── tmp/                # 임시 파일
└── <feature-id>/       # 기능별 산출물 (검증 결과, 로그 등)
    └── <timestamp>/    # 실행 시점별 격리
```

### 9.2 규칙
- artifacts는 git 추적 대상이 아니다 (repo 외부에 위치).
- 기능별 산출물은 `<feature-id>/` 하위에 타임스탬프 디렉토리로 격리한다.
- 빌드/테스트 산출물은 재생성 가능해야 하며, source of truth가 아니다.
- 공유 런타임 데이터(로그, 세션 등)는 `artifacts/shared/`에 둔다.
- `.gitkeep` 파일로 디렉토리 구조를 유지한다.
