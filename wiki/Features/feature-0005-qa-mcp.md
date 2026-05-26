---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, qa, mcp]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0005-qa-mcp
linked_unit: unit/feature-0005-qa-mcp
created: 2026-05-26
sources:
  - ../../unit/feature-0005-qa-mcp/docs/FUNCTION.md
---

# Feature — QA / MCP

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0005-qa-mcp |
| 상태 | active |
| 정본 | [[../../unit/feature-0005-qa-mcp/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | MCP 연결 검증 · QA 보조 스크립트 |

## 1. 개요

**Model Context Protocol** (MCP) 연결 검증 (`mcp_tests.py`) + 병렬 QA 테스트 보조 스크립트. `make mcp-test` 가 진입점이며 DBHub MCP 서버의 initialize/tools/list/call 흐름을 smoke check 한다.

## 2. 상세

### 2.1 책임 경계

- **입력**: `ENABLE_MCP`, `MCP_*` 환경값, 루트 compose / Makefile
- **출력**: MCP 도구 연결 확인, QA 실행 보조 스크립트
- **side-effect**: stdout test 결과

### 2.2 핵심 흐름 (FUNCTION §7)

1. `make mcp-test` 가 feature 경로의 테스트 스크립트 실행
2. 스크립트가 MCP 서버 initialize/tools/list/call 검증
3. 결과를 콘솔에 출력

### 2.3 에러 처리

- MCP 서버 미기동 / 도구 이름 불일치 / 스키마 미지정 → 비정상 종료 코드
- SQL 모드 실행 자체는 막지 않음 (MCP 비가용 시 SQL fallback)

## 3. 특징

- DBHub MCP 서버 ↔ agent 통합 검증
- TASK-0101 (REQ-20260522-0004) 의 실 환경 검증으로 closure — `docker ps --filter name=repo-mcp-1` Up + `curl http://localhost:28000/healthz` 200 + Workbench 정상

## 4. 사용법

```bash
make mcp-test            # MCP 연결 smoke
make mcp-up              # service 기동
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0001-platform-runtime]] — Compose / env 공유
- [[feature-0002-agent-core]] — agent / MCP 모드 검증
- [[feature-0004-browser-automation]] — 브라우저 제어 smoke

## 6. 관련 정본

- [[../../unit/feature-0005-qa-mcp/docs/FUNCTION|FUNCTION.md]]

## 7. 관련 노트

- [[../Architecture/Module-Map]]

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0004-browser-automation]] · [[feature-0002-agent-core]]

## 9. 외부 link

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [DBHub MCP](https://github.com/dbhub-ai/dbhub)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/draft` · `#domain/qa` · `#domain/mcp`
