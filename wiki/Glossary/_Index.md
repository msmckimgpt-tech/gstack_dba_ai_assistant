---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, vocabulary]
ai_read_priority: 8
wiki_role: index
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/CONVENTIONS.md
---

# Glossary — MOC

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/index` |
| 정본 (template 용어) | [[../../docs/CONVENTIONS\|docs/CONVENTIONS.md]] §9 |
| Entry 수 | 24 (inline) |

## 1. 개요

프로젝트 도메인 용어집. 정본은 `docs/CONVENTIONS.md §9`. 본 vault 의 도메인 용어는 그 mirror + 본 프로젝트만의 추가 용어.

## 2. 상세 — Terms (inline)

| 용어 | 정의 | 참조 |
|---|---|---|
| unit | 기능 단위 작업 폴더 (`unit/<feature-id>/`) | [[../Features/_Index]] |
| feature-id | 기능 폴더 고유 식별자 (`feature-NNNN-<purpose>`) | [[../Features/_Index]] |
| source of truth | 특정 사실의 정본 문서 | [[../../docs/CONVENTIONS]] |
| rewrite | 문서 전체를 최신 상태로 덮어쓰는 정책 | [[../../docs/CONVENTIONS]] §9 |
| append-only | 기존 항목 수정·삭제 없이 새 항목만 추가하는 정책 | [[../../docs/CONVENTIONS]] §9 |
| runtime artifacts | `../../artifacts/` 에 저장되는 로그·세션·DB 데이터·인증서 | [[../Decisions/ADR-0013-shared-runtime-separation]] |
| execution root | `docker-compose.yml` / `Makefile` / `.env` 가 위치한 저장소 실행 루트 | [[../../docs/PROJECT]] |
| .aiignore | AI 컨텍스트 제외 패턴 파일 (.gitignore 문법) | AGENTS.md §10.4 |
| playbook | 반복 작업 절차 표준화 (`PB-NNNN`) | `playbooks/` |
| plan-review | Plan-Review-Execute 의 plan 단계 (Major/Critical 진입) | [[../Decisions/ADR-0016-template-v3]] |
| worktree | Git worktree 활용한 물리적 작업 분리 (병렬 AI) | AGENTS.md §13.2 |
| LEARNINGS.md | AI 학습 기록 (mistake/pattern/quirk/preference) append-only | AGENTS.md §11.2 |
| CODEBASE_MAP.md | 저장소 파일 구조 요약 | [[../../docs/CODEBASE_MAP]] |
| ADR | Architecture Decision Record (`docs/DECISIONS.md` entry) | [[../Decisions/_Index]] |
| REQ-XXXX / TASK-XXXX | 요구사항 / 작업 단위 식별자 | CONVENTIONS §3 |
| CHG-YYYYMMDD-XXXX | 변경 식별자 (`MODIFY.md` entry) | CONVENTIONS §3 |
| REV-YYYYMMDD-XXXX | 리뷰 식별자 (`REVIEW.md` entry) | CONVENTIONS §3 |
| WebAuditEvents | 본 프로젝트 audit 단일 테이블 | [[../Decisions/ADR-0019-web-audit-events]] |
| agent_kb | KB Postgres 정본 database | [[../Decisions/ADR-0021-kb-postgres-rbac]] |
| agent_kb_rw / agent_kb_ro | KB Postgres role (Layer 1 RBAC) | [[../Decisions/ADR-0021-kb-postgres-rbac]] |
| `kb.*` permission | application-level RBAC (Layer 2) | ADR-0021 |
| dual-write | M2 phase 의 MySQL + Postgres 양쪽 KB write | [[../Decisions/ADR-0021-kb-postgres-rbac]] |
| pg_branch | UPSERT 의 `(xmax = 0)` xmax tag (INSERT vs UPDATE) | feature-0002 FUNCTION |
| namu-style | 나무위키 표준 entry 형식 (사용자 명시 요청) | [[../concepts/namu-style-format]] |
| 3-layer (raw/wiki/schema) | Karpathy LLM Wiki 패턴 | [[../concepts/llm-wiki-3-layer]] |

## 3. 분리 정책

- entry 6 개 미만: 본 파일 표 inline
- 6 개 이상: 각 용어 `Glossary/<term-slug>.md` 로 분리 (현재는 24 inline — 24 가 *project-specific* + *template-shared* 의 혼합이라 inline 유지)

## 4. 관련 문서

- [[../../docs/CONVENTIONS|docs/CONVENTIONS.md]] §9 (정본)
- [[../concepts/_Index|Concepts MOC]] — 긴 개념은 concepts/
- [[../entities/_Index|Entities MOC]] — 고유 명사는 entities/

## 5. 둘러보기

- 상위: [[../Index|Index]]
- sibling: [[../concepts/_Index]] · [[../entities/_Index]]

## 6. 분류

`#wiki/index` · `#wiki/glossary` · `#confidence/high`
