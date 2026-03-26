---
doc_type: TEST
feature_id: feature-0005-qa-mcp
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- `make mcp-test`가 새 경로 스크립트를 실행하는지 확인
- MCP 기본 initialize/list/call 흐름을 검증한다

## 2. Test Cases
- TEST-0001: `make mcp-test`가 `src/mcp_tests.py`를 호출한다
- TEST-0002: MCP 서버가 응답하지 않아도 SQL 모드 구조를 깨지 않는다
- TEST-0003: 엄격한 QA 시나리오 정의 필요

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 QA 시나리오는 후속 작성 예정
