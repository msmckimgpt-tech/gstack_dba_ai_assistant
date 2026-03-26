# MySQL MCP Design

## Goal
- SQL 모드를 기본값으로 유지하면서, 선택적으로 MCP 경로를 검증 가능한 상태로 유지한다.
- 템플릿 이관 후에도 `make mcp-up`, `make mcp-down`, `make mcp-test` 인터페이스를 그대로 유지한다.

## Runtime Modes
1. `AGENT_MODE=sql`
2. `AGENT_MODE=mcp`

## Layout
- MCP 테스트 스크립트: `unit/feature-0005-qa-mcp/src/mcp_tests.py`
- 런타임 compose 정의: `docker-compose.yml`
- 관련 환경값: `repo/.env`

## Constraints
- MCP가 비정상이더라도 SQL 모드 기동이 막히면 안 된다.
- 도구 검증은 읽기 위주로 수행한다.
- 테스트 결과는 우선 구조/기동 검증 수준으로 유지하고, 엄격한 시나리오는 후속 `TEST.md`에 정리한다.
