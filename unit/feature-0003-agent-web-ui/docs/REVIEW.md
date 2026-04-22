---
doc_type: REVIEW
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260326-0001
- Date: 2026-03-26
- Decision: Web UI는 소유권만 분리하고 런타임 이미지는 core feature Dockerfile에서 조립한다
- Reason: 실행 경로를 단순하게 유지하면서 기능 경계를 문서화하기 위함
- Risk: Web UI 단독 이미지 분리가 필요한 경우 추가 조정이 필요하다

## REV-20260421-0002
- Date: 2026-04-21
- Decision: 대화 fork 는 신규 `conversation.fork` permission 을 추가하지 않고 기존 `conversation.create` + 원본에 대한 `read.own/read.any` 조합으로 판정한다.
- Reason: fork 의 본질은 "내 계정으로 새 대화를 만들어 메시지를 채우는 것" 이며, 이는 `conversation.create` + 원본 읽기 가능 여부의 교집합과 정확히 일치한다. 신규 permission 을 추가하면 모든 role 매트릭스를 갱신해야 하고 override/role seed 와 기존 관리 콘솔 문서도 동시에 고쳐야 해 범위가 불필요하게 커진다.
- Risk: 향후 "타 계정 대화 읽기는 가능하나 fork 는 금지" 정책이 필요해질 경우, 별도 deny override 나 새 permission 도입이 추가로 필요하다.
- Alternatives considered:
  - `conversation.fork` 신규 permission 도입: 범위/가치 대비 비용이 크다고 판단해 기각.
  - 서버 측에서 `_get_history` + `/api/new_conversation` + 연속 `/api/ask` 로 프론트엔드가 재현: 원본 CreatedAt 보존 불가, 내부 메시지 필터도 어긋나며, 대규모 round-trip 발생 → 기각.

## REV-20260421-0003
- Date: 2026-04-21
- Decision: fork 시 `AgentMemoryMessages` 삽입을 `memory.py` helper 가 아닌 app.py 엔드포인트에서 직접 SQL 로 수행한다.
- Reason: helper 는 `CreatedAt` 을 DB DEFAULT CURRENT_TIMESTAMP 로 맡기지만 fork 는 **원본 시계열을 보존** 해야 사용자가 기존 대화를 재생하는 맥락이 깨지지 않는다. 또 `MetaJson` 에 `forked_from_*` 을 합성 주입하려면 insert 지점을 직접 제어할 필요가 있다.
- Risk: helper 가 향후 감사 필드/트랜잭션 훅을 추가할 경우 엔드포인트 로직도 함께 업데이트해야 한다. `docs/FUNCTION.md` 의 Dependencies 에 memory 스키마 의존성을 명시해 이 커플링을 추적한다.
- Alternatives considered:
  - helper 에 `created_at_override` 매개변수 추가: core feature 의 public API 계약을 바꿔야 하고 fork 외 호출처가 없어서 인터페이스 부풀림이라 판단해 기각.

## REV-20260421-0004
- Date: 2026-04-21
- Decision: Product-단위 DB 접근 whitelist 를 agent tools 레벨의 모듈-전역 `_ACTIVE_SCHEMA_ALLOWLIST` + `set/clear` 헬퍼로 구현하고, `run_agent` 는 본문(원래 `run_agent`) 을 `_run_agent_core` 로 rename 한 뒤 thin wrapper 로 감싸 try/finally 안에서 whitelist 를 세팅/복원한다.
- Reason: 도구 dispatch(`execute_tool`) 로 whitelist 를 모든 경로에 파라미터로 전파하려면 tool 시그니처 전부 확장 + 기존 호출처(CLI/insight worker 포함) 모두 갱신이 필요하다. 모듈-전역 + context 매니저 패턴은 (1) call site 가 `agent_core.run_agent` 만 변경, (2) 모든 tool 이 단일 `_whitelist_violation(refs)` 진입점만 공유, (3) finally 로 워커 스레드 재사용 시 leak 방지라는 세 조건을 동시에 만족한다.
- Risk: `run_agent` 가 재진입(reentrant) 될 경우 마지막 setter 가 이전 whitelist 를 덮어쓴다. 현재 구조는 `asyncio.to_thread` 로 worker 당 1 호출이므로 충돌이 없지만, 향후 nested agent 호출이 도입되면 stack-based state(`contextvars.ContextVar`) 로 전환해야 한다.
- Alternatives considered:
  - tool signature 확장(`execute_tool(conn, tool, args, *, allowed_schemas)`): 호출처 파급이 크고, `_tool_execute_sql` 이 내부 helper 에서 재귀 참조를 할 때 또 다시 전달해야 해 반복 노이즈가 발생해 기각.
  - `threading.local`: `asyncio.to_thread` 의 스레드 풀이 재사용되므로 cleanup 이 반드시 finally 로 이뤄져야 한다는 점에서 현재 전역 + finally 패턴과 실질적 동일, 단순성 우선해 현 안 채택.

## REV-20260421-0005
- Date: 2026-04-21
- Decision: `_whitelist_violation` 이 `information_schema` 만 명시적으로 bypass 하고, 그 외 시스템 스키마(`mysql`, `performance_schema`, `sys`, `agent_memory`) 는 whitelist 규칙을 통해 **기본 차단** 한다.
- Reason: 초기 구현은 `_SYSTEM_SCHEMAS` 전체를 bypass 했으나, 이는 "Product=KR 이 `dbgame`/`dblog`/`dbauth` 만 허용" 이라는 운영 의도와 충돌한다. agent 가 `SELECT * FROM mysql.user` 를 요청하면 whitelist 가 손을 대지 않고 통과시켜 자격 정보가 유출될 수 있다. `information_schema` 만 "스키마 카탈로그 자체 조회 용도로 필요" 라는 명시적 이유로 예외 처리하고, 나머지 시스템 스키마는 whitelist 에 수동 등록하지 않는 한 차단되도록 한다.
- Risk: 운영 중 `agent_memory` 나 `mysql` 시스템 스키마 쿼리가 필요해질 경우 Product DB 목록에 수동 추가가 필요하다. 현재 설계상 이는 audit 목적에 부합하며, 과도한 접근이 발생하기 전에 관리 콘솔에서 명시적으로 추가해야만 허용된다.
- Alternatives considered:
  - 모든 `_SYSTEM_SCHEMAS` bypass(초기 안): 운영 의도와 보안 모두 어긋나 기각.
  - `_SYSTEM_SCHEMAS` 중 특정 항목만 화이트리스트(예: `agent_memory` 만 항상 허용): 현재 agent 가 자신의 메모리 DB 를 조회할 이유가 없어 불필요한 표면적 확장이라 기각.
- Superseded in part by: REV-20260422-0006 (메타데이터 4 스키마 bypass 재도입, `agent_memory` 차단 유지 부분은 유효).

## REV-20260422-0007
- Date: 2026-04-22
- Decision: TASK-0040 (regex context-aware) 와 TASK-0041 (attach/resume 복구 경로) 두 건을 한 번에 반영한다. 두 건 모두 TASK-0034 Q4/Q5 재수행을 가능하게 만드는 전제 조건이었고, TASK-0041 은 코드 경로가 서로 독립이지만 향후 runner 의 타임아웃 내구성에도 동일한 장치가 필요했기 때문에 함께 기록한다.
- Reason:
  - TASK-0040: 기존 `_SCHEMA_TABLE_REF_RE` 단일 regex 는 SQL 문맥 정보가 없었다. SELECT 절/WHERE 절/ON 절의 `alias.column` 은 구문적으로 `schema.table` 와 같은 `x.y` 토큰이라 whitelist 검사기가 구분할 수 없었고, Q4-like SQL 이 전부 `BLOCKED_SCHEMAS=bb,be` 로 거부됐다. 기존 regex 를 확장해 negative lookbehind 로 해결하려고 시도해봐도 FROM/JOIN 뒤 alias 선언(`FROM dblog.t bb`) 과 이후 alias 참조 (`bb.BattleType`) 가 같은 SQL 안에 공존하는 구조라 1 단계 regex 로는 근본적으로 구분이 불가능하다. FROM/JOIN 구간을 slice 하고 그 안에서만 `schema.table` 을 찾는 2 단계 스캐너가 최소한의 정확도 게이트이고, SQL 파서를 도입하지 않는 선에서 가장 단순한 정답이다.
  - TASK-0041: 에이전트 작업자 스레드(`asyncio.to_thread` 로 분리된 CPU/IO 루프)는 HTTP 연결과 독립이다. 클라이언트가 ReadTimeout 으로 끊어지거나 브라우저를 닫아도 서버는 완료까지 진행하지만, 그 결과를 회수할 read-only 경로가 없어 유저 입장에서는 "타임아웃 = 답변 손실" 처럼 보였다. `AgentMemoryKv(last_status/last_status_run_id/last_duration_ms/last_error)` + `AgentMemoryMessages` + `AgentMemorySteps` 이 이미 진행 상태와 최종 결과를 저장하고 있으므로, 새로운 상태 저장소 없이 스냅샷 + long-poll read-only 2 엔드포인트만 추가하면 UX 복구가 가능하다. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 의도적으로 분리해 attach 가 새 실행을 시작시키지 않도록 했다 — 이것이 "새 요청으로 재진입해 중복 실행을 유발하지 않는" 안전 속성이다.
- Risk:
  1. 2 단계 regex 스캐너는 여전히 SQL 파서가 아니다. `WITH cte AS (...)` 같은 CTE 구문이나 `JOIN LATERAL (subquery)` 같은 복잡 구조에서 slice lookahead 경계가 어긋날 수 있음. 현재 agent 가 생성하는 SQL 범위에서는 15 케이스 검증으로 대응되지만, 생성 SQL 복잡도가 커지면 `sqlparse` 같은 경량 파서 도입을 재검토해야 한다.
  2. `/api/ask_status`/`/api/ask_result` 는 기존 `conversation.read.own/any` 권한을 재사용하므로 새로운 공격 표면은 없다. 다만 long-poll 60s 가 WEB_PARALLEL_LIMIT 과 별도로 백그라운드 연결을 유지하므로, 장기적으로 한 대화에 대해 동일 사용자가 다수 탭으로 polling 하면 연결 수가 쌓일 수 있다 (현재는 MCP 수준 트래픽에서는 무시 가능).
  3. 브라우저 boot-time auto-attach 는 페이지 새로고침 시마다 `/api/ask_status` 호출을 추가한다 — is_processing 여부만 체크하는 가벼운 쿼리라 비용은 미미하지만, 401/타 계정 대화 복구 시 attach 가 시작되지 않도록 권한 필터가 올바르게 동작해야 한다(기존 `_account_can_access_conversation` 로 보장됨).
- Alternatives considered:
  - TASK-0040 대안 (기각): 기존 regex 에 `(?<!\\w)\\s*` 류 lookbehind 를 덧붙여 alias.column 을 배제하는 방안 — alias 가 SELECT/WHERE/ON 모든 위치에 등장하므로 부정형 lookbehind 로 완전 배제가 불가. SQL 파서 도입 — 지금 필요한 정확도 대비 의존성 추가 비용이 크다.
  - TASK-0041 대안 (기각): 기존 `/api/progress` 폴링을 확장해 최종 답변을 같이 실어보내는 방안 — `/api/progress` 는 최근 N 스텝만 반환하고 응답 payload 크기를 keep-small 하도록 최적화되어 있어 최종 answer 를 싣기엔 부적합. Server-Sent Events / WebSocket 도입 — 인프라(프록시, TLS 종단, 재접속) 복잡도가 늘어나 현재 규모에 과하다.
  - TASK-0041 대안 (고려됨): 다이얼로그에서 `즉시 답변` 은 사실상 `/api/finalize` + attach 로 매핑됐는데, 이를 `/api/finalize` 없이 attach 만으로 끝내도 `finalize` 와 동등하지 않다 (LLM 추가 툴콜을 막지 않음). 본 구현은 두 경로를 구분 유지.
- How this relates to prior reviews: REV-20260422-0006 (메타데이터 4 스키마 bypass) 이후, Product DB whitelist 자체는 제대로 작동하지만 `_extract_sql_schema_refs` 가 alias 까지 오탐하던 부작용이 TASK-0040 에서 해제됐다. REV-20260421-0005 / REV-20260422-0006 의 "alias.column 은 whitelist 대상이 아님" 이라는 암묵 가정이 이제는 코드로도 성립한다.

## REV-20260422-0006
- Date: 2026-04-22
- Decision: `_whitelist_violation` 의 bypass 집합을 `{information_schema}` 에서 `_METADATA_SCHEMAS = {information_schema, sys, mysql, performance_schema}` 로 확장한다. `agent_memory` 는 `_INTERNAL_SCHEMAS` 로 분리해 **계속 차단** 유지.
- Reason: 사용자 지시(2026-04-22, "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지"). 실사용에서 agent 가 `information_schema.TABLES` 외에 `sys.schema_table_statistics` / `performance_schema.tables` / 드물게 `mysql.*` 을 교차 검증 조회하려는 시도가 차단당해 탐색 루프에 빠지는 현상이 관찰됐다. 메타데이터 4 종은 DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요한 "카탈로그적" 성격이므로 Product 관리자가 DB 목록에 일일이 추가하지 않아도 기본 허용되는 편이 운영 직관과 맞는다. `agent_memory` 는 타 계정 대화/세션/권한 override 를 담고 있어 성격이 다르며 계속 차단해야 한다.
- Risk:
  1. `mysql.user`/`mysql.db`/`mysql.global_priv` 에는 credential hash / grant 정보가 있다. 이 결정으로 tool-레벨 1 차 방어가 풀리므로, **DB 커넥터 MySQL 계정의 GRANT 가 2 차 방어로 남아야** 한다. 스모크 테스트 시점에서는 현 계정이 `mysql.user SELECT` 권한을 가지고 있어 실제 행이 반환됨을 확인했다 — 운영상 민감도가 높으면 MySQL 계정 GRANT 를 `information_schema` + Product DB 만 허용하도록 좁힐 것.
  2. `performance_schema`/`sys` 는 민감도 낮음(런타임 stat + 뷰 집합).
  3. write 가능 agent 계정을 도입하게 되면 본 결정을 재검토해야 한다(현재는 read-only 전제).
- Alternatives considered:
  - 메타데이터 스키마를 Product DB 목록에 수동 등록(REV-20260421-0005 의 원안): 관리 부담이 크고, 모든 Product 에서 동일하게 필요해 등록 누락 시 agent 가 탐색에 실패하는 결함이 재발한다. 기각.
  - `information_schema` + `sys` 2 종만 bypass: 사용자가 `mysql`/`performance_schema` 를 포함해 4 종을 명시했고, 둘 다 DBA 작업에서 교차 검증이 빈번해 2 종으로는 충분하지 않아 기각.
  - `agent_memory` 까지 포함한 전체 `_SYSTEM_SCHEMAS` bypass: agent 가 자신의 메모리 DB 를 읽을 이유가 없고, 타 계정 대화 유출 경로가 생기므로 기각.
- How this changes REV-20260421-0005: REV-20260421-0005 의 "`information_schema` 만 bypass" 결정을 "메타데이터 4 종 bypass, 에이전트 내부 스키마는 계속 차단" 으로 교체. `agent_memory`/임의 user schema 를 차단한다는 핵심 보안 의도는 유지된다.
