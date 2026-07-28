---
doc_type: WIKI_ARTICLE
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/CODEBASE_MAP.md
  - ../../docs/PROJECT.md
---

# Architecture — Module Map

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/article` |
| 정본 | [[../../docs/ARCHITECTURE\|docs/ARCHITECTURE.md]] §4·§9 + [[../../docs/CODEBASE_MAP\|docs/CODEBASE_MAP.md]] |
| 디렉토리 수 | top-level 8 (정책 / unit / shared / docs / bin / wiki / artifacts / .worktrees) |

## 목차

1. [개요](#1-개요)
2. [상세](#2-상세)
     - [2.1 Top-level 매핑](#21-top-level-매핑)
     - [2.2 Feature 디렉토리 인덱스](#22-feature-디렉토리-인덱스)
     - [2.3 docs/ 정본 인덱스](#23-docs-정본-인덱스)
     - [2.4 artifacts/ 조직 (정본 §9)](#24-artifacts-조직-정본-9)
3. [관련 문서](#3-관련-문서)
4. [둘러보기](#4-둘러보기)
5. [외부 link](#5-외부-link)
- [분류](#분류)

## 1. 개요

저장소 top-level 디렉토리 ↔ 책임 매핑. 정본 [[../../docs/ARCHITECTURE|ARCHITECTURE]] §4 + [[../../docs/CODEBASE_MAP|CODEBASE_MAP]] 의 시각적 mirror.

## 2. 상세

### 2.1 Top-level 매핑

| 디렉토리 | 책임 | 정본 / 갱신 책임 |
|---|---|---|
| `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` | 정책 정본 + multi-agent schema 호환 | `AGENTS.md` (정본 — schema 파일) |
| `docs/` | 정책·도메인 정본 (PROJECT/ARCHITECTURE/DECISIONS/CONVENTIONS/SECURITY/STATUS 외) | 각 파일 frontmatter `source_of_truth: true` |
| `unit/<feature-id>/` | feature 단위 구현·문서·테스트 | `unit/<id>/docs/FUNCTION.md` 가 기능 정본 |
| `shared/` | 공통 코드 예약 영역 | `shared/AGENTS.md` (있다면) + `shared/MODIFY.md` |
| `bin/` | 운용·검증 스크립트 (`verify-completion.sh`, `wiki-lint.sh`, `kb-cutover-readiness.sh`, ...) | 각 스크립트 자체 |
| `playbooks/` | 반복 작업 표준화 (`PB-NNNN`) | 각 PB 파일 |
| `wiki/` | 사람용 graph 입구 (본 vault) | mirror — 정본 없음 |
| `../../artifacts/` (repo 외부) | runtime artifacts | git 미추적 |
| `_template_maintainer/` | template base 만의 운용 영역 | consumer 미배포 (정상) |

### 2.2 Feature 디렉토리 인덱스

- [[../Features/_Index|Features MOC]] — feature-0001 ~ feature-0029

#### 2.2.1 feature-0002 핵심 모듈 (멀티 데이터소스, 2026-06)

| 모듈 | 책임 | concept |
|---|---|---|
| `modules/dialects/` | `Dialect` ABC + `MySQLDialect`/`MSSQLDialect` (SQL 방언 분기) | [[../concepts/multi-datasource]] |
| `cred_crypto.py` | KEK/DEK envelope 암호화 (`WebDatasources` password) | [[../concepts/datasource-registry]] |
| `runtime_backend.py` | `PgRuntimeBackend` — agent_runtime PG read/write (dual-write 코드 제거됨) | [[../Decisions/ADR-0027-agent-runtime-pg-schema]] |
| `_DatasourceRouter` | 호출 단위 connection/allowlist/dialect 잠금 | [[../concepts/multi-datasource]] |
| `sql_guard` / `_extract_sql_schema_refs` | 3축 보안 게이트 AST allowlist + denylist | [[../concepts/db-level-access]] |

### 2.3 docs/ 정본 인덱스

| docs/ 파일 | 역할 | wiki mirror |
|---|---|---|
| `PROJECT.md` | 프로젝트 목적·범위·성공 기준 | overview §1 |
| `ARCHITECTURE.md` | 시스템 구조 | [[Overview]] |
| `DECISIONS.md` | ADR 정본 | [[../Decisions/_Index]] |
| `CONVENTIONS.md` | 작업 규약 / 용어집 / Admin Console 정책 | [[../Glossary/_Index]] |
| `SECURITY.md` | 보안 정책 (audit, trust, RBAC) | [[Data-Flow]] §2.2 |
| `STATUS.md` | 프로젝트 전체 진행률 | overview §2.4 |
| `WIKI.md` | wiki vault 운용 정본 | 본 vault 전체 |
| `CODEBASE_MAP.md` | 파일 구조 요약 | 본 노트 |
| `LEARNINGS.md` | AI 학습 누적 (append-only) | (mirror 없음 — AI context 전용) |
| `OBSERVATIONS.md` | 운영 관찰 | (mirror 없음) |
| `KB_PG_DIALECT_NOTES.md` | KB Postgres dialect 노트 | feature-0002 카드에서 cross-link |

### 2.4 artifacts/ 조직 (정본 §9)

```
artifacts/
├── build/              # 빌드 산출물
├── reports/            # 생성된 보고서
├── exports/            # 내보내기 파일
├── tmp/                # 임시 파일
└── <feature-id>/<ts>/  # feature 별 timestamp 격리
```

repo 외부 — `.gitignore` 추적 대상 아님.

## 3. 관련 문서

- [[Overview]]
- [[Data-Flow]]
- [[../../docs/CODEBASE_MAP|CODEBASE_MAP]] (정본)
- [[../../docs/ARCHITECTURE|ARCHITECTURE]] (정본)

## 4. 둘러보기

- 상위: [[Overview]]
- sibling: [[Data-Flow]]
- 관련 ADR: [[../Decisions/ADR-0012-feature-unit-restructure]] · [[../Decisions/ADR-0013-shared-runtime-separation]] · [[../Decisions/ADR-0010-status-doc]]

## 5. 외부 link

- 없음

## 분류

`#wiki/article` · `#confidence/high` · `#maturity/substantial`
