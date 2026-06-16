---
doc_type: WIKI_LOG
scope: project
status: active
edit_policy: append-only
source_of_truth: true
template_version: v3.12.0
domain: [history, wiki]
ai_read_priority: 9
wiki_role: log
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Wiki — Log

Append-only 이력. AI 가 wiki 의 페이지를 추가/수정할 때마다 한 줄씩 누적한다. 기존 entry 는 수정·삭제 금지.

## Format

```
[YYYY-MM-DDTHH:MM:SSZ] <operation> | <wiki_role> | <path> | <one-line note>
```

- `<operation>`: `create` | `update` | `link` | `lint-fix` | `graduate`
- `<wiki_role>`: `index` | `article` | `log` | `source_summary` | `feature_card` | `adr_mirror`
- `<path>`: `wiki/` root 로부터의 상대 경로
- `<one-line note>`: 변경 이유 1줄 (≤ 100자)

## Entries

> 첫 entry 는 copy-base 직후 AI 가 vault 를 활성화할 때 작성한다.

<!-- AI: 새 entry 는 위 "## Entries" 헤딩 직후, 다음 줄에 prepend (최신순) -->

[2026-06-12T05:04:26Z] update | hot_cache | hot.md | 2026-06-12 멀티 데이터소스 시대 세션 컨텍스트로 재작성 (drift 해소)
[2026-06-12T05:04:26Z] update | article | overview.md | 멀티 데이터소스 서사 합성 — 8 feature / ADR-0027~0030 / 진행흐름·한계·다음단계 재정렬
[2026-06-12T05:04:26Z] update | index | Index.md | 도메인=멀티 데이터소스 분석 플랫폼 / 8 feature / ADR-0001~0030 + unit ADR
[2026-06-12T05:04:26Z] update | article | Architecture/Overview.md | 8 feature 맵 + 멀티 데이터소스·storage 단일화 특징
[2026-06-12T05:04:26Z] update | article | Architecture/Data-Flow.md | 멀티 데이터소스 data plane + ask-worker 큐 mermaid·trust boundary §2.5
[2026-06-12T05:04:26Z] update | article | Architecture/Module-Map.md | feature-0002 핵심 모듈(dialects/cred_crypto/runtime_backend) + feature 0001~0008
[2026-06-12T05:04:26Z] update | feature_card | Features/feature-0003-agent-web-ui.md | 관리콘솔(데이터소스CRUD·대시보드·LLM사용량·insight완료율)·ask-worker·취소재요청 §2.5
[2026-06-12T05:04:26Z] update | feature_card | Features/feature-0002-agent-core.md | 멀티 데이터소스 §2.5 (dialect·registry·DB접근·insight·EXPLAIN gate)
[2026-06-12T05:04:26Z] update | index | Features/_Index.md | feature-0008 추가 (7→8 active) + 0002/0003 한줄 갱신
[2026-06-12T05:04:26Z] create | article | entities/mssql.md | MSSQL entity — dialect·3-part·DB접근·envelope 자격
[2026-06-12T05:04:26Z] update | index | entities/_Index.md | MSSQL 등록 (9→10) + Tool 분류 갱신
[2026-06-12T05:04:26Z] update | article | entities/mysql.md | 멀티 데이터소스 시대(main_mysql datasource·DB-단위 접근) §2.4
[2026-06-12T05:04:26Z] create | article | concepts/ask-worker-queue.md | out-of-process ask 큐 (ask_jobs·SKIP LOCKED·TASK-0169 cutover)
[2026-06-12T05:04:26Z] create | article | concepts/insight-worker.md | schema 통찰 + 분석 완료율(0223) + DB별 파악내용(0242) + __global__ sentinel
[2026-06-12T05:04:26Z] create | article | concepts/datasource-aware-rag.md | ds-aware rag_objects + endpoint-hash scope(compute_scope_key) (TASK-0219)
[2026-06-12T05:04:26Z] create | article | concepts/db-level-access.md | DB-단위 접근 (catalog allowlist·시스템DB 가시성만) (TASK-0206)
[2026-06-12T05:04:26Z] create | article | concepts/datasource-registry.md | envelope 암호화 KEK/DEK + WebDatasources CRUD (TASK-0205)
[2026-06-12T05:04:26Z] create | article | concepts/multi-datasource.md | MySQL·MSSQL dialect adapter + 3축 보안 게이트 + 1:N 제품
[2026-06-12T05:04:26Z] update | index | concepts/_Index.md | 신규 concept 6종 등록 (6→12)
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0030-ssrf-guard-toggle.md | datasource SSRF 사설망 경계 env 토글
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0029-windows-browser-testing.md | 실제 Windows 브라우저 AI 자동 검증 (PB-0008)
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0028-runtime-mysql-cleanup.md | runtime 6 테이블 MySQL cleanup Stage A/B/C
[2026-06-12T05:04:26Z] create | adr_mirror | Decisions/ADR-0027-agent-runtime-pg-schema.md | agent_runtime PG schema + AR-M4 read cutover
[2026-06-12T05:04:26Z] update | index | Decisions/_Index.md | ADR-0027~0030 mirror 등록 + unit-level ADR-CORE/WEB 표 (§2.1)
[2026-05-28T15:50:00Z] update | hot_cache | hot.md | T1~T5 전체 활성화 완료 — PgBouncer md5/pg_hba 정합 수정 + replica streaming 확인
[2026-05-28T00:00:00Z] update | article | concepts/kb-postgres-pgvector.md | T1~T5 성능 최적화 로드맵 완수 반영 — DISTINCT ON/ANY/MV/JSONB/PgBouncer/replica/advisory-lock/LISTEN-NOTIFY
[2026-05-28T00:00:00Z] update | article | Architecture/Data-Flow.md | pgbouncer sidecar + postgres-replica 다이어그램 추가 (T3-8, T5-14)
[2026-05-28T00:00:00Z] update | hot_cache | hot.md | T1~T5 완수 세션 컨텍스트 압축 저장
[2026-05-26T06:52:40Z] update | index | Index.md | namu-style 인포박스 + 7-feature 매핑 + namu sections 정리 (v3.13.0 follow-up wiki sync)
[2026-05-26T06:52:40Z] update | article | overview.md | living synthesis — 7 feature 표 + 핵심 ADR + KB / 첨부 / Bedrock 흐름 합성
[2026-05-26T06:52:40Z] update | article | Architecture/Overview.md | ARCHITECTURE.md §1~§6 mirror — 4-layer 책임 / 7 feature 표 / 의존 표
[2026-05-26T06:52:40Z] update | article | Architecture/Data-Flow.md | mermaid flowchart — Caddy → web → agent loop / Bedrock / KB / MinIO + trust boundary 표
[2026-05-26T06:52:40Z] update | article | Architecture/Module-Map.md | top-level 디렉토리 매핑 + docs/ 정본 인덱스 + artifacts 조직 표
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0001-platform-runtime.md | namu-style — MySQL/DAB · replica · redo log 1 GiB
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0002-agent-core.md | namu-style — agent loop · KB Postgres M0~M5 · audit
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0003-agent-web-ui.md | namu-style — FastAPI · admin · audit · 첨부 · sandbox · share
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0004-browser-automation.md | namu-style — Playwright HTTP service
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0005-qa-mcp.md | namu-style — MCP test + QA helper
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0006-lan-proxy-access.md | namu-style — Caddy TLS · XFF trust · Windows portproxy
[2026-05-26T06:52:40Z] create | feature_card | Features/feature-0007-bedrock-llm-provider.md | namu-style — Bedrock gateway · API Vault 폐기 · env 분리
[2026-05-26T06:52:40Z] update | index | Features/_Index.md | 7 feature entry 표 채움
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0001-state-history-separation.md | 현재 상태 / 이력 분리
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0002-agents-md-canonical.md | AGENTS.md 정본 · CLAUDE.md 참조
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0003-first-request-scope.md | FIRST_REQUEST 부트스트랩 전용
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0004-blocked-preapproved-risk.md | BLOCKED + Pre-approved + 위험도
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0005-task-source-of-truth.md | TASK.md 정본 격상
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0006-test-md-mixed-policy.md | TEST.md 혼합 정책
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0007-conflict-resolution-rule.md | 충돌 해석 규칙
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0008-archiving-policy.md | append-only 20건 초과 아카이빙
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0009-shared-governance.md | shared/ 거버넌스
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0010-status-doc.md | docs/STATUS.md 도입
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0011-gitignore-artifacts.md | .gitignore artifacts 규칙 제거
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0012-feature-unit-restructure.md | feature 단위 재배치
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0013-shared-runtime-separation.md | shared ↔ artifacts 경계
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0014-env-canonical.md | .env / AGENTS.md 원본 의미 보존
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0015-template-v2.md | Template v2.0.0 마이그레이션
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0016-template-v3.md | Template v3.0.0 Plan-Review-Execute
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0017-github-automation-stack.md | superseded by ADR-0018
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0018-github-automation-decommission.md | GitHub 자동화 폐기
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0019-web-audit-events.md | WebAuditEvents dispatcher + 4 권한
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0020-slow-query-log-decoupled.md | slow_query_log 통합 거부
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0021-kb-postgres-rbac.md | KB Postgres 2-layer RBAC
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0022-minio-attachment-storage.md | MinIO 첨부 storage
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0023-sandbox-schema-mysql-users.md | sandbox schema + 4 user
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0024-postgres-database-isolation.md | 단일 cluster + 별 DB
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0025-m5-cleanup.md | M5 cleanup 14-day window (정본 ADR-0025 두 entry 중 하나)
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0025-pgvector-attachment-rag.md | PGVector attachment RAG (정본 ADR-0025 두 entry 중 하나)
[2026-05-26T06:52:40Z] create | adr_mirror | Decisions/ADR-0026-bedrock-llm-provider.md | Bedrock + API Vault 폐기 + Phase E
[2026-05-26T06:52:40Z] update | index | Decisions/_Index.md | 27 entry 표 (ADR-0025 두 mirror)
[2026-05-26T06:52:40Z] create | article | concepts/rag.md | RAG (Retrieval-Augmented Generation)
[2026-05-26T06:52:40Z] create | article | concepts/kb-postgres-pgvector.md | KB Postgres pgvector
[2026-05-26T06:52:40Z] create | article | concepts/audit-subsystem.md | Audit Subsystem
[2026-05-26T06:52:40Z] create | article | concepts/llm-wiki-3-layer.md | LLM Wiki 3-layer (raw/wiki/schema)
[2026-05-26T06:52:40Z] create | article | concepts/namu-style-format.md | namu-style 사람 facing 형식
[2026-05-26T06:52:40Z] create | article | concepts/sandbox-schema-isolation.md | Sandbox Schema Isolation
[2026-05-26T06:52:40Z] update | index | concepts/_Index.md | 6 concept entry 표
[2026-05-26T06:52:40Z] create | article | entities/mysql.md | MySQL 8.0
[2026-05-26T06:52:40Z] create | article | entities/postgres.md | PostgreSQL 16 (pgvector)
[2026-05-26T06:52:40Z] create | article | entities/aws-bedrock.md | AWS Bedrock
[2026-05-26T06:52:40Z] create | article | entities/litellm.md | LiteLLM proxy
[2026-05-26T06:52:40Z] create | article | entities/minio.md | MinIO
[2026-05-26T06:52:40Z] create | article | entities/playwright.md | Playwright
[2026-05-26T06:52:40Z] create | article | entities/caddy.md | Caddy
[2026-05-26T06:52:40Z] create | article | entities/karpathy.md | Andrej Karpathy
[2026-05-26T06:52:40Z] create | article | entities/obsidian.md | Obsidian
[2026-05-26T06:52:40Z] update | index | entities/_Index.md | 9 entity entry 표
[2026-05-26T06:52:40Z] update | index | Glossary/_Index.md | 24 inline term 표 (template + project-specific)
[2026-05-26T06:52:40Z] lint-fix | index | sources/_Index.md | 깨진 wikilink 예시 placeholder text 로 전환 (lint broken PASS)
[2026-05-26T06:52:40Z] lint-fix | index | syntheses/_Index.md | 깨진 wikilink 예시 placeholder text 로 전환 (lint broken PASS)

## [2026-06-15] feature | TASK-0256 assistant 답변 markdown diff 블록(리뷰 시 변경 제시) + 웹 UI diff 색 렌더 (PR#209, main 2befd37)
## [2026-06-16] docs | 서비스 소개 프레젠테이션(docs/presentation: 자기완결 HTML 덱 + SCENARIO.md 발표 스크립트·공격 질문 대응) 신설 + wiki 정합 갱신(연결상태 3색·datasource Id surrogate·첨부 PG cutover·답변 diff)
