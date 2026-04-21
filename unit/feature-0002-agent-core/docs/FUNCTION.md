---
doc_type: FUNCTION
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
자연어 요청을 받아 SQL 작성, 실행, 메모리 관리, 지식 관리, 복구 로직을 담당하는 핵심 에이전트 기능이다.

## 2. Goal
- REQ-0001: agent 코어 코드를 feature 구조로 이관한다.
- REQ-0002: 새 Dockerfile과 루트 실행 파일이 코어를 정상 참조하게 한다.

## 3. In Scope
- `agent_cli.py`, `agent_core.py`
- `modules/*`
- agent 이미지 Dockerfile
- 기본 smoke 검증을 위한 코어 테스트 파일

## 4. Out of Scope
- Web UI 정적 자산
- 브라우저 자동화 서비스
- 엄격한 질의 정확도 시나리오

## 5. Inputs
- 사용자 질문
- `.env`의 agent 관련 설정값
- MySQL 및 MCP 런타임

## 6. Outputs
- CLI 응답
- 메모리/지식/로그 기록
- SQL 실행 및 복구 흐름

## 7. Main Flow
1. `make ask` 또는 agent 컨테이너가 코어 엔트리(`agent_core.run_agent()`)를 호출한다.
2. 코어는 다음 순서로 1회 실행을 구성한다 (상세는 [AGENT_CORE_INTERNALS.md](./AGENT_CORE_INTERNALS.md#2-에이전트-1회-실행-흐름-run_agent) 참조):
   1. OpenAI 또는 로컬 LLM 게이트웨이 클라이언트를 준비한다.
   2. `agent_memory` DB에 대화/메시지/KV 테이블을 보장하고 대화 맥락(`origin_request` / `thread_goal`) 3-state 판정을 수행한다.
   3. `_build_knowledge_context()` 로 `KNOWN SCHEMAS & TABLES` + `RELEVANT TABLES FOR THIS QUESTION` 블록을 시스템 프롬프트에 주입한다.
   4. Step Loop: LLM 이 반환한 `tool_calls` 를 최대 3 개씩 실행(`execute_sql` / `describe_table` / `search_tables` / `get_sample_rows`)하고, 결과를 메모리에 기록한다. 도구 호출이 없으면 최종 답변으로 종료.
   5. 루프 상한은 `AGENT_MAX_STEPS` 와 `AGENT_TIMEOUT_SEC * 3` 이며, Web UI 의 "중단" / "즉시 답변" 신호를 각 틱마다 감지한다.
3. 결과를 콘솔(Rich Markdown) 또는 JSON 응답으로 Web UI 에 전달하고, 완료 시 `set_run_status()` 로 상태를 `done / error / canceled` 로 기록한다.
4. 별도 백그라운드 프로세스 `run_insight_worker_loop()` 이 MySQL 스키마/테이블 변경을 감지해 `schema_insight:*` / `table_insight:*` 캐시를 갱신한다. 상세는 [INSIGHTS.md](./INSIGHTS.md) 참조.

## 8. Edge Cases
- DB 연결 실패: `connect_with_retry()` 로 재시도, 최종 실패 시 `result["error"]` 에 실패 사유 기록.
- MCP 비가용: `SYSTEM_PROMPT_MCP` 경로는 `modules/mcp_client.py` 에서 핸드셰이크 실패를 감지해 SQL 모드로 폴백.
- Insight 워커 부재 / heartbeat stale: `_should_run_inline_insight_scan()` 이 감지해 질의 시점 인라인 스캔으로 품질을 유지 ([INSIGHTS.md §5.4](./INSIGHTS.md#54-인라인-fallback-워커-부재--장애)).
- `tool_result` 가 4000 자 초과: `(truncated)` 로 절단하되, 전체 결과는 CSV 로 별도 저장되어 사용자 접근 가능.
- 결과 행 수가 50 초과: LLM 에는 상위 50 행만 전달, 답변 렌더링 시 대형 마크다운 표는 `_collapse_large_tables()` 가 상위 5 행 + CSV 링크로 치환.
- LLM 이 빈 응답을 반환: `reasoning` 을 fallback 으로 쓰거나 "Korean Markdown 으로 답하라" 메시지를 최대 3 회 재시도.

## 9. Error Handling
- 코어 모듈은 자동 복구와 재시도 경로를 사용한다.
- 실패 원인은 로그와 실행 결과에 남긴다.
- Insight 워커 사이클 결과는 `agent_memory.agentmemorykv` 의 `insight_worker_last_status / _error / _duration_ms / _run_id` 키로 관측된다.

## 10. Dependencies
### 내부 기능 의존성
- 없음

### 외부 의존성
- OpenAI 또는 로컬 LLM API (`LLM_BASE_URL` 설정 시 로컬 게이트웨이 경유)
- MySQL 8.0 (본 DB + `agent_memory` 메모리 DB)

### shared 모듈 의존성
- 없음

### Memory DB 스키마 (agent_memory)
| 테이블 | 용도 |
|---|---|
| `AgentMemoryConversations` | 대화 엔터티 (id, topic, created_at, …) |
| `AgentMemoryMessages` | user/assistant/tool 메시지 기록 |
| `AgentMemorySteps` | 도구 실행 단계별 입출력 요약 |
| `AgentMemoryFactEntries` + `AgentMemoryTexts` | 지식/인사이트 저장 (`schema_insight:*`, `table_insight:*`, 대화별 facts) |
| `agentmemorykv` | Key-Value 메타 (`origin_request`, `thread_goal`, `insight_worker_last_*`, `schema_fp:*`, `table_fp:*`, cancel/finalize 플래그 등) |

## 11. Acceptance Criteria
- AC-0001: 코어 코드가 `src/` 아래로 이동되어 있다.
- AC-0002: 새 Dockerfile이 코어와 Web UI 코드를 함께 이미지에 넣는다.
- AC-0003: 루트 `make ask` 경로가 새 feature 구조를 사용한다.

## 12. Observability
- 로그: `../../../../artifacts/shared/logs`
  - `insight_worker.log` — 백그라운드 Insight 워커 사이클 결과 (JSON lines: `run_id`, `status`, `duration_ms`, `skipped_schemas/tables`, `event=fingerprint_skip` 등). 해석 가이드는 [INSIGHTS.md §9](./INSIGHTS.md#9-로그--신호--사용자-해석-가이드).
  - `llm_warn.log` — LLM 호출 실패/빈 응답/JSON 파싱 실패 (`_log_llm_warn()`).
  - `agent_run.log`, `tool_call.log` — 에이전트 실행 요약.
- 출력: `../../../../artifacts/shared/out`
  - `execute_sql` 결과 CSV 저장 경로. LLM 에는 미리보기 50 행만 전달되며 전체는 여기에서만 확인 가능.
- 관측 쿼리 (헬스 체크):
  ```sql
  -- Insight 워커 heartbeat
  SELECT `Key`, Value, UpdatedAt
  FROM agent_memory.agentmemorykv
  WHERE ConversationId = '__global__'
    AND `Key` LIKE 'insight_worker_last_%'
  ORDER BY `Key`;

  -- 캐싱된 인사이트 수
  SELECT
    SUM(FactKey LIKE 'schema_insight:%') AS schema_insights,
    SUM(FactKey LIKE 'table_insight:%')  AS table_insights
  FROM agent_memory.AgentMemoryFactEntries
  WHERE ConversationId = '__global__';
  ```
  자세한 해석은 [INSIGHTS.md §10](./INSIGHTS.md#10-헬스-체크-snippet) 참조.

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 Docker build 경로 수정
