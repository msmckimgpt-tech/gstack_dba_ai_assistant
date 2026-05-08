---
doc_type: INTERNALS
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Agent Core Internals

## 1. 이 문서의 목적

`agent_core.py` 와 `modules/*` 내부 동작은 지금까지 대부분 **코드 주석**에만 기술되어 있었다. 본 문서는 사용자·운영자가 소스를 열지 않고도 다음 사항을 파악할 수 있도록 정리한다.

- 에이전트 1회 실행이 어떻게 흘러가는가 (loop 구조와 신호)
- `SYSTEM_PROMPT` 가 어떤 블록으로 구성되어 있고 왜 그 순서인가
- `TOOL_DEFINITIONS` 가 왜 `execute_sql` 을 맨 앞에 놓는가
- 지식(Insight/KV/Fact) 이 어느 시점에 프롬프트에 들어가는가
- CSV·미리보기·대형 표 접힘 (collapse) 이 어떻게 2 단계로 처리되는가
- 인사이트 fast path 가 언제 활성화되는가

Insight 서브시스템(백그라운드 워커) 만을 다루는 문서는 [INSIGHTS.md](./INSIGHTS.md) 에 분리되어 있다. 본 문서는 **질의 처리 시 에이전트가 그 인사이트를 어떻게 활용하는지**에 초점을 맞춘다.

## 2. 에이전트 1회 실행 흐름 (run_agent)

엔트리: [agent_core.py:935 `run_agent()`](../src/agent_core.py#L935).

```
run_agent(user_message, conversation_id, model, ...)
  │
  ├─ OpenAI 클라이언트 준비  (로컬 LLM이면 LLM_BASE_URL gateway)
  │
  ├─ 대화 메타 준비
  │    ensure_memory_schema() / _connect_memory() / _ensure_memory_tables()
  │    cleanup_pending_delete_conversations()
  │    _ensure_conversation(cid), _ensure_web_conversation_metadata(cid)
  │
  ├─ 대화 맥락 3-state (shift / evolve / continue)
  │    load_memory_kv("origin_request"), load_memory_kv("thread_goal")
  │    _should_refresh_origin_request() → "shift" | "evolve" | "continue"
  │
  ├─ 지식 주입
  │    _build_knowledge_context(mem_conn, user_message, history)
  │      → "KNOWN SCHEMAS & TABLES" + "RELEVANT TABLES FOR THIS QUESTION"
  │
  ├─ system/messages 구성 → SYSTEM_PROMPT + CONVERSATION CONTEXT + knowledge
  │
  └─ Step Loop  (step_count < max_steps, elapsed < run_timeout_sec)
       │
       ├─ _cancel_requested_for_run(cid, run_id)    → break (canceled)
       ├─ _finalize_requested(cid, run_id)          → tools=None 로 1회 호출
       ├─ _call_llm(client, messages, model, tools)
       │
       ├─ tool_calls 없음 → 최종 답변  → _collapse_large_tables → 저장 → break
       │
       └─ tool_calls 있음
            ├─ 최대 3개까지 slice    (len(tool_calls) > 3 → [:3])
            ├─ 각 도구 실행 execute_tool(db_conn, tool_name, tool_args)
            ├─ tool_result가 4000자 넘으면 "(truncated)" 절단
            ├─ messages.append({"role": "tool", ...})
            └─ _mirror_step(...) 으로 step 저장
```

종료 시 `set_run_status()` 로 `done / error / canceled` 상태를 기록하고, `_delete_requested()` 였다면 `delete_conversation_records()` 로 대화를 제거한다.

## 3. SYSTEM_PROMPT 구조

`SYSTEM_PROMPT` 는 [agent_core.py:70](../src/agent_core.py#L70) 에 정의된 단일 문자열이며, 아래 순서로 블록을 의도적으로 배치했다.

| # | 블록 | 목적 |
|---|---|---|
| 1 | **CRITICAL DIRECTIVE** | "Execute SQL first, explore later." 단 한 줄로 이 에이전트의 핵심 정책을 선언. 가장 먼저 등장한다. |
| 2 | **CORE RULES** | 날조 금지, `schema`.`table` 형식 강제, 한국어 키워드를 영문 식별자로 변환하라는 4가지 기본 규칙. |
| 3 | **STRATEGY (priority order)** | 전략 5개를 **우선순위 순**으로 배열. 1순위는 KNOWN SCHEMAS 섹션 참조, 4순위부터 `search_tables` 허용, 5순위 `get_sample_rows` 는 사실상 비권장. |
| 4 | **IDEAL FLOW EXAMPLE** | "1 tool call 으로 답이 나오는 경우" 를 실제 예시로 제시. LLM이 최단 경로를 선호하도록 유도한다. |
| 5 | **ANTI-PATTERNS** | `search_tables → describe → describe → ...` 같이 step 예산을 낭비하는 패턴 5개를 열거하고 명시적으로 금지. |
| 6 | **SQL PATTERNS** | Cross-schema JOIN, `JSON_TABLE` 같이 자주 필요한 MySQL 8 문법 스니펫. |
| 7 | **OUTPUT** | 결과가 모이면 도구 호출을 멈추고 **한국어 Markdown** 으로 답하라, 수치는 천단위 콤마, 행 비교시 표 사용. |

추가로 질의 시점에 아래 2 개 블록이 이어 붙는다 ([agent_core.py:1090-1101](../src/agent_core.py#L1090-L1101)).

- `## CONVERSATION CONTEXT` — `origin_request` + `thread_goal`. 직전 대화의 스레드 목표를 LLM 이 놓치지 않게 한다.
- `## KNOWN SCHEMAS & TABLES` + `## RELEVANT TABLES FOR THIS QUESTION` — `_build_knowledge_context()` 가 생성하는 동적 블록.

**MCP 모드**는 `llm.py` 의 `SYSTEM_PROMPT_MCP` ([llm.py:225](../src/modules/llm.py#L225)) 를 사용하며, 직접 DB 접속 대신 MCP 도구 호출 계획만 1 단계 반환하도록 규칙이 약간 다르다. MCP 모드는 `modules/mcp_client.py` 경유로만 활성화된다.

## 4. TOOL_DEFINITIONS 우선순위

[tools.py:37-125](../src/modules/tools.py#L37-L125) 가 핵심 4개 도구를 이 순서로 선언한다.

1. `execute_sql` — **맨 앞에 배치**. "LLM 이 리스트의 첫 번째 도구를 선호한다" 는 관찰(LRN-20260416-0001) 을 활용해, 첫 도구 호출이 바로 `execute_sql` 이 되도록 유도한다.
2. `describe_table` — `execute_sql` 이 컬럼 오류로 실패했을 때만. 동일 테이블 1 회 제한.
3. `search_tables` — 최후 수단. KNOWN SCHEMAS 에 이미 후보가 있으면 사용하지 않는다. 같은 키워드로 2 회 이상 호출 금지.
4. `get_sample_rows` — 거의 필요 없음. 컬럼 내용 형식(JSON 구조 등) 확인 시에만.

`TOOL_DEFINITIONS_FULL` ([tools.py:130](../src/modules/tools.py#L130)) 은 위 4 개 + `list_schemas / describe_schema / explain_query / get_table_indexes / get_foreign_keys / ...` 를 추가한 전체 정의다. 현재 `run_agent` 는 기본 4 개만 사용한다.

이 배치는 **SYSTEM_PROMPT 의 STRATEGY 섹션과 1:1 로 대응**한다. STRATEGY 가 우선순위를 말로 설명하면 TOOL_DEFINITIONS 는 그 순서를 구조로 강제한다.

## 5. 지식 주입 (Knowledge Injection)

`_build_knowledge_context()` ([agent_core.py:232](../src/agent_core.py#L232)) 는 질의마다 2개 블록을 생성한다.

- **`## KNOWN SCHEMAS & TABLES (authoritative — prefer these over tool-based discovery)`** — `_load_schema_list()` ([agent_core.py:113](../src/agent_core.py#L113)) 가 `AgentMemoryFactEntries` 의 `table_insight:*` 수를 스키마별로 집계하고, `schema_insight:*` 의 `domain:` 라인을 파싱해 도메인 설명을 붙인다.
  - 포맷: `- {schema} ({count} tables) — {domain} — {description}`
- **`## RELEVANT TABLES FOR THIS QUESTION`** — `_load_relevant_table_insights()` ([agent_core.py:191](../src/agent_core.py#L191)) 가 사용자 메시지에서 영문 토큰을 추출(`[a-zA-Z][a-zA-Z0-9_]{1,}`)해 `table_insight:*` FactKey/본문에 LIKE 매칭되는 최대 15 건을 상위 후보로 제시한다.

두 블록이 모두 비어 있으면 주입 자체가 스킵된다. 블록이 실려 있으면 SYSTEM_PROMPT 의 "KNOWN SCHEMAS 를 1 순위 참조원으로 쓰라" 는 규칙이 비로소 실효를 가진다. 이 데이터의 생성 주체는 백그라운드 Insight 워커이며, 구조는 [INSIGHTS.md](./INSIGHTS.md) 참조.

## 6. Step 예산 · 타임아웃 · 외부 신호

- **max_steps**: 기본 `AGENT_MAX_STEPS` (`config.py`), 루프는 `step_count < max_steps` 조건으로 돌며 초과 시 `"최대 도구 호출 횟수(...) 를 초과했습니다."` 메시지로 종료한다 ([agent_core.py:1347-1354](../src/agent_core.py#L1347-L1354)).
- **run_timeout_sec**: `max(AGENT_TIMEOUT_SEC * 3, AGENT_EARLY_FINALIZE_MS/1000)` ([agent_core.py:1113-1116](../src/agent_core.py#L1113-L1116)). 초과 시 `result["error"]="타임아웃으로 종료되었습니다."`.
- **cancel**: Web UI 의 "중단" 버튼이 `_cancel_requested` 플래그를 남기면, 루프 진입/LLM 호출 직후/각 도구 실행 전후에서 감지하여 즉시 break, 상태를 `canceled` 로 기록 ([agent_core.py:1123-1125, 1159-1161, 1246-1249, 1278-1281](../src/agent_core.py#L1123-L1125)).
- **finalize**: "즉시 답변" 버튼이 `_finalize_requested` 플래그를 남기면 다음 LLM 호출에서 `tools=None` 으로 보내 **도구 호출 없는 최종 답변**을 강제한다 ([agent_core.py:1134-1145](../src/agent_core.py#L1134-L1145)).
- **tool_calls 제한**: LLM 이 한 턴에 3개 초과 도구를 요청하면 앞에서 3개만 실행한다(`tool_calls[:3]`) ([agent_core.py:1214-1215](../src/agent_core.py#L1214-L1215)).
- **tool_result 절단**: 개별 도구 결과가 4000자를 넘으면 `"... (truncated)"` 로 자른다 ([agent_core.py:1283-1285](../src/agent_core.py#L1283-L1285)). 이는 컨텍스트 윈도우 절약을 위한 내부 제한이며, 전체 결과는 CSV 파일로 별도 저장된다 (§7).
- **empty_retries**: LLM 이 빈 content 를 반환하면 `reasoning` 을 fallback 으로 쓰거나, 그도 없으면 "한국어 Markdown 으로 답하라" 는 user 메시지를 최대 3 번까지 추가한다 ([agent_core.py:1166-1180](../src/agent_core.py#L1166-L1180)).

## 7. CSV 2 단계 (preview + 전체 파일)

`execute_sql` 결과를 LLM 에 모두 싣지 않는다. [tools.py:458-498](../src/modules/tools.py#L458-L498) 의 `_tool_execute_sql` 이 다음을 수행한다.

1. `_raw_execute_sql()` 로 전체 결과를 얻는다.
2. 각 result set 을 **통째로 CSV 파일**로 저장한다 — `render.save_csv("resultset{idx}", ...)`. 경로는 `/shared/out/...csv` 형식.
3. LLM 으로 돌려주는 문자열에는 **미리보기만** 넣는다 — `_format_result_sets(result_sets, max_rows=_TOOL_PREVIEW_ROWS)` (`_TOOL_PREVIEW_ROWS=50`, [tools.py:455](../src/modules/tools.py#L455)).
4. 미리보기 뒤에 `CSV 저장: <path>` 라인을 덧붙이고, 전체 행 수가 미리보기보다 많으면 *"답변에 전체 표를 삽입하지 말고 CSV 링크를 제공하세요"* 라는 지시를 함께 전달한다.

답변 렌더링 단계에서 `_collapse_large_tables()` ([agent_core.py:547](../src/agent_core.py#L547)) 가 다시 한 번 안전망 역할을 한다. 마크다운 표의 데이터 행이 `_TABLE_ROW_THRESHOLD=5` 를 넘으면 상위 5 행만 남기고 그 아래를 `📎 [전체 N행 미리보기](/api/file?path=...)` 링크로 치환한다.

결과적으로 **LLM 은 항상 최대 50 행만 읽고, 사용자는 CSV 로 전체를 받을 수 있다**. 이것이 대형 결과셋에서 컨텍스트를 터뜨리지 않는 핵심 장치다.

## 8. Planner Insight Fast Path

`modules/planner.py` 는 SQL 1 단계를 LLM 없이 직접 조립해 즉시 실행하는 경로를 갖는다. 핵심이 `_build_insight_object_fast_plan()` ([planner.py:1356](../src/modules/planner.py#L1356)) 이다.

- 활성 조건: `AGENT_INSIGHT_OBJECT_FASTPATH=1` 이고, 요청에서 대상 테이블을 추론할 만한 근거(명시된 스키마/테이블, `kv.preferred_schema`, knowledge 의 `insight_objects`) 가 충분할 때.
- 동작: `_collect_insight_candidates_from_knowledge()` + `_load_table_insight_candidates()` 로 후보를 모으고, 요청 키워드와의 매칭 점수를 계산한 뒤 상위 후보를 선택해 `execute_sql` 플랜을 생성한다.
- LLM 호출 없이 바로 SQL 로 직행하므로 **첫 답변까지의 지연을 크게 줄인다**. 실패/애매할 때만 기존 `llm_plan()` 경로로 폴백한다.
- Fallback 이유(`fallback_reason`)는 `disabled / empty_request / passthrough_guard_active / ...` 형태로 `info` 딕셔너리에 기록되어 관측 가능하다.

이 경로는 **Insight 워커가 축적한 `table_insight:*` 데이터가 없으면 활성되지 않는다**. 즉 Insight 서브시스템이 멈추면 이 fast path 도 자연스럽게 비활성된다 (시스템이 느려지긴 해도 오동작하지 않는다).

## 9. 대화 맥락 3-State (shift / evolve / continue)

[agent_core.py:1056-1080](../src/agent_core.py#L1056-L1080) 의 `origin_shift_type` 분기.

| 상태 | 판정 | 조치 |
|---|---|---|
| `shift` | 주제 자체가 완전히 바뀐 요청 | `origin_request` + `thread_goal` 모두 새 값으로 초기화 |
| `evolve` | 동일 도메인 내 목표 진화 | `thread_goal` 만 업데이트, `origin_request` 유지 |
| `continue` | 같은 목표의 후속 요청 | 둘 다 유지 (비어 있던 항목만 채움) |

판정은 `_should_refresh_origin_request()` ([modules/domain.py](../src/modules/domain.py)) 가 담당한다. 결과는 SYSTEM_PROMPT 뒤에 붙는 `CONVERSATION CONTEXT` 블록에 그대로 실려 LLM에 전달된다.

## 10. 코드 참조 요약

| 구성요소 | 경로 |
|---|---|
| 에이전트 엔트리 / 루프 | [agent_core.py:935 `run_agent()`](../src/agent_core.py#L935) |
| SYSTEM_PROMPT (SQL 모드) | [agent_core.py:70](../src/agent_core.py#L70) |
| SYSTEM_PROMPT_MCP | [llm.py:225](../src/modules/llm.py#L225) |
| 지식 주입 빌더 | [agent_core.py:232 `_build_knowledge_context()`](../src/agent_core.py#L232) |
| 스키마 목록 로더 | [agent_core.py:113 `_load_schema_list()`](../src/agent_core.py#L113) |
| 관련 테이블 로더 | [agent_core.py:191 `_load_relevant_table_insights()`](../src/agent_core.py#L191) |
| TOOL_DEFINITIONS (핵심 4개) | [tools.py:37](../src/modules/tools.py#L37) |
| TOOL_DEFINITIONS_FULL | [tools.py:130](../src/modules/tools.py#L130) |
| execute_sql 도구 (CSV 2 단계) | [tools.py:458 `_tool_execute_sql()`](../src/modules/tools.py#L458) |
| 대형 표 접힘 | [agent_core.py:547 `_collapse_large_tables()`](../src/agent_core.py#L547) |
| cancel/finalize 감지 | [memory.py](../src/modules/memory.py) `_cancel_requested`, `_finalize_requested` |
| Planner fast path | [planner.py:1356 `_build_insight_object_fast_plan()`](../src/modules/planner.py#L1356) |
| 대화 맥락 shift 판정 | [domain.py](../src/modules/domain.py) `_should_refresh_origin_request()` |

## 11. 관련 문서

- [INSIGHTS.md](./INSIGHTS.md) — 백그라운드 Insight 워커의 실행 경로와 저장 형식
- [FUNCTION.md](./FUNCTION.md) — 기능 단위 사양과 의존성
- [DECISIONS.md](./DECISIONS.md) — 설계 결정 기록 (ADR)
