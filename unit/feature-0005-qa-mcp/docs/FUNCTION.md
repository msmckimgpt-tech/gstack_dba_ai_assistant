---
doc_type: FUNCTION
feature_id: feature-0005-qa-mcp
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
MCP 연결 검증과 QA 보조 스크립트를 관리한다.

## 2. Goal
- REQ-0001: MCP 테스트 스크립트를 기능 단위 구조로 이관한다.
- REQ-0002: 루트 `make mcp-test`가 새 경로를 사용하게 한다.

## 3. In Scope
- `src/mcp_tests.py`
- `src/scripts/run_parallel_tests.sh`
- MCP/QA 문서

## 4. Out of Scope
- MCP 서버 이미지 구현
- 엄격한 도메인 결과 검증

## 5. Inputs
- `ENABLE_MCP`, `MCP_*` 환경값
- 루트 compose와 Makefile

## 6. Outputs
- MCP 도구 연결 확인
- QA 실행 보조 스크립트

## 7. Main Flow
1. `make mcp-test`가 feature 경로의 테스트 스크립트를 실행한다.
2. 스크립트가 MCP 서버 initialize/tools/list/call을 검증한다.
3. 결과를 콘솔에 출력한다.

## 8. Edge Cases
- MCP 서버 미기동
- 도구 이름 불일치
- 스키마 미지정

## 9. Error Handling
- 실패 시 스크립트가 비정상 종료 코드로 끝난다.
- SQL 모드 실행 자체는 막지 않는다.

## 10. Dependencies
### 내부 기능 의존성
- feature-0001-platform-runtime
- feature-0002-agent-core
- feature-0004-browser-automation

### 외부 의존성
- DBHub MCP

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-0001: MCP 테스트 스크립트가 feature 구조로 이관되어 있다.
- AC-0002: `make mcp-test`가 새 경로를 실행한다.
- AC-0003: QA 스크립트가 문서화되어 있다.

## 12. Observability
- 콘솔 테스트 출력
- MCP 서비스 로그

## 13. Pre-approved Changes
- 비파괴적 스크립트 재배치와 진입 경로 수정
