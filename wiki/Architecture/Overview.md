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
  - ../../docs/PROJECT.md
  - ../../docs/CODEBASE_MAP.md
---

# Architecture — Overview

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/article` |
| 정본 | [[../../docs/ARCHITECTURE\|docs/ARCHITECTURE.md]] |
| Wiki layer | mirror (graph 입구) |
| Feature 수 | 7 (feature-0001 ~ feature-0007) |

## 1. 개요

저장소는 **공통 정책 영역 / 기능 영역 / 공통 코드 영역 / 산출물 영역** 4 layer 로 분리되어, 기능별 소유권을 명확히 하면서도 단일 docker-compose 로 실행 가능하다. 정본은 [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] §1 — 본 노트는 그 mirror.

## 2. 상세

### 2.1 책임 분리 (정본 §2)

| Layer | 위치 | 책임 |
|---|---|---|
| 공통 정책 | `AGENTS.md`, `docs/*.md` | 프로젝트 전반 규칙·제약·용어·보안 기준 |
| 기능 영역 | `unit/<feature-id>/{src,tests,docs}/` | 기능별 코드·테스트·명세·이력·리뷰·보고 |
| 공통 코드 | `shared/` | 여러 기능에서 공통 사용하는 코드 (필요 시) |
| 산출물 | `../../artifacts/*` (repo 외부) | 빌드 결과, 로그, MySQL 데이터, 세션, 인증서 |

### 2.2 기능 단위 구조 (정본 §3)

각 feature 는 다음 sub-tree 를 갖는다:

```
unit/feature-NNNN-<purpose>/
├── src/      # 기능 구현
├── tests/    # 기능 테스트
└── docs/     # FUNCTION/TASK/REPORT/MODIFY/REVIEW/ANCHOR/...
```

### 2.3 현재 기능 맵 (정본 §4)

| Feature ID | 책임 |
|---|---|
| [[../Features/feature-0001-platform-runtime\|feature-0001-platform-runtime]] | MySQL/DAB 설정 + replica 연결 |
| [[../Features/feature-0002-agent-core\|feature-0002-agent-core]] | agent CLI / core / KB Postgres |
| [[../Features/feature-0003-agent-web-ui\|feature-0003-agent-web-ui]] | FastAPI Web UI + audit subsystem |
| [[../Features/feature-0004-browser-automation\|feature-0004-browser-automation]] | Playwright browser service |
| [[../Features/feature-0005-qa-mcp\|feature-0005-qa-mcp]] | MCP / QA scripts |
| [[../Features/feature-0006-lan-proxy-access\|feature-0006-lan-proxy-access]] | Caddy TLS + Windows LAN proxy |
| [[../Features/feature-0007-bedrock-llm-provider\|feature-0007-bedrock-llm-provider]] | AWS Bedrock (Claude) gateway |

### 2.4 기능 간 의존성 (정본 §6)

| Feature | 의존 대상 | 유형 | 비고 |
|---|---|---|---|
| feature-0003 | feature-0002 | uses | Web UI → core import |
| feature-0003 | feature-0006 | uses | `_get_client_ip` 가 Caddy `trust_forwarded_for` 의존 |
| feature-0004 | feature-0001 | uses | 운영 런타임 공유 |
| feature-0005 | feature-0001, feature-0002, feature-0004 | uses | Compose + agent + browser smoke |
| feature-0006 | feature-0001 | uses | Web/TLS 운영 자산 공유 |
| feature-0007 | feature-0002, feature-0003 | uses | LLM 호출 단일 진입점 통합 |

의존 유형 어휘 (`requires` / `uses` / `extends`) 정본은 ARCHITECTURE.md §6.

## 3. 특징

- **source of truth 원칙** (정본 §5): 동일 사실을 여러 문서에 중복 확정하지 않는다. FUNCTION/TASK/REPORT/MODIFY/REVIEW/DECISIONS/STATUS 의 각 책임이 분리됨.
- **runtime artifacts 외부화**: 로그·세션·MySQL data 가 `../../artifacts/` 로 분리되어 git 추적 대상 아님.
- **AI 위임 친화**: AI 가 작업 시 `AGENTS.md` 우선 read + 각 feature 의 `docs/` 자동 참조.

## 4. 관련 문서

- [[Data-Flow]] — 데이터 흐름 다이어그램
- [[Module-Map]] — 디렉토리 ↔ 책임 매핑
- [[../../docs/PROJECT|docs/PROJECT.md]]
- [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] (정본)

## 5. 둘러보기

- 상위: [[../Index|Index]] · [[../overview|overview]]
- sibling: [[Data-Flow]] · [[Module-Map]]
- 관련 ADR: [[../Decisions/ADR-0012-feature-unit-restructure]] · [[../Decisions/ADR-0013-shared-runtime-separation]] · [[../Decisions/ADR-0016-template-v3]]

## 6. 외부 link

- 없음 (모두 repo 안 정본)

## 분류

`#wiki/article` · `#confidence/high` · `#maturity/substantial`
