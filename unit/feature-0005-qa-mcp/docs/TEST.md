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
- TEST-0003 (엄격한 QA 시나리오, 2026-07-28 확정): `make mcp-test` 가 MCP 프로토콜
  **initialize → tools/list → tools/call** 전 구간을 왕복하고, `tools/call` 이 **실 DB
  메타데이터**(테이블명·스키마·컬럼 수·행 수)를 JSON-RPC 응답으로 반환한다. 판정은 최종
  `jsonrpc` 응답 payload 에 실데이터가 실려 오는지로 한다(연결 성공만으로는 불충분).

## 3. Test Run History
- 2026-07-28 (TEST-0003 엄격한 QA 시나리오 — Environment: 라이브 `repo-mcp-1` + 실 MySQL):
  - `make mcp-test` 실행 → initialize / tools/list / tools/call 왕복 완주,
    종료 메시지 "MCP 테스트가 완료되었습니다."
  - 최종 `tools/call` 응답(`jsonrpc 2.0`, `id: 4`)에 **실 DB 메타데이터 20건**이 실려 왔다 —
    `account_db.account`(19 컬럼 · 242,973 행) · `agent_memory.webauditevents`(17 컬럼 ·
    508,663 행) 등 스키마·컬럼 수·행 수 포함, `truncated: true`.
  - 판정: **PASS**. 연결 성공이 아니라 **실데이터 반환**까지 확인했다. TEST-0003 을
    placeholder 에서 실 시나리오로 확정하고 본 Run 으로 닫는다.

- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 QA 시나리오는 후속 작성 예정
