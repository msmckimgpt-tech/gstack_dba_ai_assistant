# mysql_ai 템플릿 작업 지침서

## 목표
현재 디렉토리(`.`)에 템플릿 실행 루트로 재구성된 MySQL 기반 `agent_cli` 환경을 운영한다.
최우선 목적은 **요청 의도에 맞는 실제 데이터 결과를 빠르게 반환**하는 것이다.
- 이 문서는 원본 루트 `AGENTS.md`의 의미를 유지한 채 템플릿 구조에 맞게 옮긴 정본이다.
- 템플릿 사본은 **단독 실행**을 전제로 하며, 원본 프로젝트와의 동시 기동은 지원하지 않는다.

## 연구 기반 방향 전환 (강제)
- 목표 상태는 "LLM 파라미터에 DB를 암기"가 아니라, **외부 지식베이스를 완전 구축**하고 LLM이 매 요청 시 해당 지식을 참조해 SQL을 작성하는 구조다.
- 따라서 지식 품질의 1순위는 `DB -> Memory KB` 동기화 완전성이고, 2순위는 LLM 입력 패키징 정확도다.
- 요청 텍스트를 코드가 임의 가공/축약/휴리스틱 분기하는 방식은 금지한다.
- LLM에는 가능한 한 **요청 원문 + 근거 지식 + 실행 결과 피드백**을 전달한다.
- 사용자 질의 경로에서 SQL은 **오직 LLM이 작성**한다. 코드 템플릿 SQL(`COUNT(*)`, 메타 점검 SQL, fast-aggregate SQL) 생성/주입은 금지한다.

## 웹 기준 업계 표준 반영 (강제)
- 대화 상태는 단순 문자열 누적이 아니라 **안정적인 상태 관리**로 유지한다.
  - 메타 점검 발화(예: "문맥 이해하니?")는 `origin_request`를 덮어쓰지 않는다.
  - 주제 전환은 명시 전환 신호(새 도메인/새 객체/명시 SQL)일 때만 반영한다.
- 메모리는 `short-term(thread)` + `long-term(global)`를 분리해 사용하고, 실행마다 근거 패키지를 재구성한다.
- RAG 라우팅은 `retrieve -> rerank -> grounded plan` 순서를 지키고, 근거 부족일 때만 메타탐색으로 폴백한다.
- 근거가 없는 객체 강제 집계(`random table count`)를 금지한다.
- 참고 표준:
  - OpenAI Conversation State: https://platform.openai.com/docs/guides/conversation-state
  - LangGraph Memory: https://docs.langchain.com/oss/python/langgraph/add-memory
  - Anthropic Tool Use: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
  - Azure RAG Architecture: https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-architecture

## 절대 금지 (충돌 항목 제거)
- 문자열 패턴 기반 의도 분기/강제 SQL 경로 금지 (`_is_aggregate_like_request` 류 금지).
- 요청 토큰 매칭 기반 객체 점수화/선택 금지(테이블 선택은 LLM resolver + 근거 패키지 기준).
- 요청 토큰 매칭 기반 KB 검색 필터링 금지(근거 로딩은 전체/스키마/객체 exact 기준으로 수행).
- `planner_constraints.*` 같은 임의 제약 변수로 LLM 행동을 강제하는 방식 금지.
- `AGENT_KB_FACT_LIMIT`, `AGENT_GLOBAL_KB_FACT_LIMIT`, `AGENT_INSIGHT_OBJECT_MAX_CANDIDATES` 등 **고정 상한 기반 샘플링 설계 금지**.
- "요약만 주입하고 원문 근거는 버리는 구조" 금지.
- 사용자의 요청과 무관한 스키마/테이블 탐색을 먼저 수행하는 행동 금지.
- 명시 근거 없이 객체를 임의 선택해 `COUNT(*)`로 즉시 응답하는 동작 금지.
- 객체 선택 실패 시 `schema_top`/`fallback_top_candidate`/가중치 상위 1개 같은 임의 폴백 금지.

## 최우선 과제 (우선순위 고정)
- `1)` 정확도: 메타데이터 나열이 아닌 실제 결과/결론 반환
- `2)` 맥락: follow-up(`다시/이어서/아까 그거`)에서도 의도 유지
- `3)` 지식 재사용: 기존 검증 근거 재활용으로 재탐색 최소화
- `4)` 성능: 90초 초과 비율 감소, 루프/중복 탐색 제거

## 작업자 준수 체크 (시작 전/종료 전)
- 시작 전: "이번 변경이 정확도/맥락/지식 중 무엇을 개선하는지" 1줄로 남긴다.
- 종료 전: "실제 데이터 결과가 출력되는지" 확인한다.
- 종료 전: "동일 도메인 재요청에서 불필요한 메타탐색이 줄었는지" 확인한다.

## 지식 아키텍처 목표 (신규 기준)
### 1) 완전 구축 레이어
- `AgentMemoryFactEntries`는 DB 전역 구조 지식을 누락 없이 누적한다.
- 최소 저장 단위:
- 스키마
- 테이블
- 컬럼/타입
- PK/FK/인덱스
- 대표 조인 경로
- 검증된 지표 정의(메트릭 정의)

### 2) 요청별 근거 패키지 레이어
- `make ask` 실행마다 LLM 호출 전에 근거 패키지를 재구성한다.
- 패키지는 고정 top-k가 아니라 **coverage 기반**으로 생성한다.
- 기준:
- 요청에서 언급된 객체/동의어 포함
- 최근 성공 실행에서 사용된 객체 포함
- 도메인 앵커와 충돌하는 후보 배제 근거 포함

### 3) 실행 피드백 레이어
- 성공 SQL/실패 SQL/복구 경로를 지식에 반영한다.
- 같은 실패 시그니처는 즉시 우회 경로를 제시한다.

### 4) 카테고리 + Depth 라우팅 레이어 (신규)
- 인사이트 객체(`table_insight/schema_insight`)는 아래 카테고리를 구조화해 저장한다.
- `domain`, `entity_type`, `metric_family`, `event_type`, `time_grain`, `join_hints`, `confidence`
- 요청 실행 시 근거 선택은 고정 top-k가 아니라 `D0 -> D1 -> D2 -> D3` 단계로 확장한다.
- `D0`: 명시 객체/직전 확정 객체 우선
- `D1`: 스키마 앵커 범위
- `D2`: 스키마 + 도메인 카테고리 확장
- `D3`: 전체 근거 풀(최종 폴백)
- 단계 승급 사유(`ask_loop`, 재시도, 오류)는 로그에 남기고, 무관 스키마 점프를 금지한다.

## 구현 로드맵 (이후 작업계획 명시)
### P0 (즉시)
- `agent_cli` 플래닝 경로에서 강제 분기용 `planner_constraints` 주입 제거.
- LLM 입력 `knowledge`를 요약 중심에서 근거 중심으로 전환.
- 요청 원문 보존: follow-up 재작성/임의 문자열 덧붙이기 제거.
- 메타탐색은 "근거 부족"일 때만 허용하고 사유를 로그에 강제 기록.
- `origin_request`/`domain_anchor` 보호: 메타 점검 발화는 상태를 오염시키지 않도록 차단.
- RAG fallback 게이트: 명시 객체/앵커가 없는 경우 강제 객체 집계로 점프하지 않는다.

### P1 (우선)
- `AgentMemoryFactEntries`를 중심으로 전수 인덱싱 워커 구현.
- 인덱싱은 배치/페이지 방식으로 수행하되 최종 coverage는 100%를 목표로 한다.
- 고정 상한 대신 `incomplete_queue` 기반으로 미완료 객체 우선 처리.
- 질문 실행 전 preflight로 "요청 관련 근거 존재 여부"를 검사하고 부족 시 선동기화.

### P2 (구조 개선)
- `reg_*` FactKey는 행수/컬럼명 나열형 텍스트 저장을 중단하고, 아래 구조화 정보로 대체:
- metric 정의(분자/분모/기간/필터)
- 조인 경로(테이블/키)
- 검증 상태(confirmed/estimated)
- 근거 SQL 시그니처
- ScopeKey는 요청 문장 기반이 아니라 `domain/schema/object/metric` 구조화 키를 우선 사용.

### P3 (운영 안정화)
- 지식 참조 경로 추적 로그를 요청 단위로 필수화한다.
- "왜 그 객체를 선택했는지"를 점수 대신 근거 목록으로 남긴다.

## 기본 구조
- `./unit/feature-0001-platform-runtime/src`
- `./unit/feature-0002-agent-core/src`
- `./unit/feature-0003-agent-web-ui/src`
- `./unit/feature-0004-browser-automation/src`
- `./unit/feature-0005-qa-mcp/src`
- `./unit/feature-0006-lan-proxy-access/src`
- `./unit/<feature-id>/docs`
- `./shared`
- `./docs`
- `./.env`
- `./docker-compose.yml`
- `./Makefile`
- `./MCP_DESIGN.md`

## 핵심 제약
- `_ai_delegated_dev_template` 외부 디렉토리 수정 금지.
- 런타임 산출물은 `../artifacts/`에만 저장한다.
- `.env.example` 기본값에는 실제 키를 넣지 않는다.
- 단, 기존 `OPENAI_API_KEY` 값이 이미 있으면 `.env`에서 삭제/덮어쓰기 금지.
- 컨테이너 내부 경로는 Linux 경로만 사용한다.
- 호스트 파일시스템 경로는 상대경로만 사용한다.
- 도커 제어는 반드시 `make` 타깃 사용(직접 docker/compose 명령 금지).
- DB 테스트/제어는 기본적으로 `make ask` 사용.
- 예외: 메모리 DB(`AGENT_MEMORY_DB`, `AgentMemory*`) 점검은 mysql client 직접 사용 허용.
- 메모리 DB 점검 시 `make ask`, `make mysql` 사용 금지.

## 실행 환경 고정 (WSL 강제)
- 모든 실행은 WSL(Ubuntu)에서만 수행.
- 작업 경로: 현재 디렉토리(`.`) 또는 저장소 상대경로 `./_ai_delegated_dev_template/repo`
- 시작 체크:
- `pwd`가 템플릿 실행 루트(또는 하위)
- `uname -s`가 `Linux`
- 불만족 시 즉시 WSL 전환 후 재시작.

### WSL 전환 표준 명령
- WSL 진입 후 저장소 루트에서 `cd ./_ai_delegated_dev_template/repo && make session-info`

### 금지 규칙
- `C:\...` 기준 실행 금지.
- Windows 인터프리터(`py.exe`, `python.exe`, `node.exe`) 실행 금지.

## 다중 AI 작업 충돌 방지
- `SESSION_TAG` 또는 `SESSION`을 고유값으로 분리한다.
- 확인: `make session-info`
- 단일 테스터 병렬 lane 규칙:
- `SESSION_TAG=<ai>_<lane>`
- lane 간 동일 태그 재사용 금지
- `WEB_PARALLEL_LIMIT` 초과 금지

## 운영 명령 (Make)
- `make start`
- `make stop`
- `make status`
- `make convo-clear`
- `make web`
- `make web-down`
- `make insight-up`
- `make insight-down`
- `make insight-status`
- `make insight-logs`
- `make mysql sql="SELECT 1;"` (사용자 명시 요청 시만)
- `make browser-up`
- `make browser-down`
- `make browser-session`
- `make browser-goto url="https://example.com"`
- `make browser-click selector="..."`
- `make browser-type selector="..." text="..."`
- `make browser-press selector="..." key="Enter"`
- `make browser-wait selector="..."`
- `make browser-text selector="..."`
- `make browser-html selector="..."`
- `make browser-shot`
- `make browser-close`

## Docker Compose 기준
- 서비스: `mysql`, `agent`, `memory-init`, `insight-worker`, `mcp`(선택)
- MySQL: `mysql:8.0`
- 볼륨:
- `../artifacts/shared:/shared`
- `../artifacts/mysql-data:/var/lib/mysql`
- `../artifacts/mysql-backup:/shared/mysql-backup`
- `../artifacts/certs:/certs`

## .env 정책 (대규모 개편)
### 유지/필수
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `AGENT_MEMORY_DB`
- `AGENT_MODE`
- `AGENT_INSIGHT_WORKER_ENABLED`
- `AGENT_INSIGHT_WORKER_TICK_SEC`
- `AGENT_SCHEMA_INSTANCE_SCAN`
- `AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC`
- `AGENT_LLM_REQUEST_PASSTHROUGH=1`
- `AGENT_INSIGHT_ROUTE_LOG=1`

### 제거/비권장 (충돌 항목)
- 고정 개수 기반 지식 주입/후보 제한 변수는 제거 또는 사용 중단한다.
- 예: `AGENT_KB_FACT_LIMIT`, `AGENT_GLOBAL_KB_FACT_LIMIT`, `AGENT_INSIGHT_OBJECT_MAX_CANDIDATES`
- `planner_constraints` 계열 제약 주입 플래그는 제거한다.

### 신규 권장 (향후 구현용)
- `AGENT_KB_COVERAGE_MODE=complete`
- `AGENT_KB_PREFETCH_ON_ASK=1`
- `AGENT_KB_PREFETCH_ON_START=1`
- `AGENT_KB_INCREMENTAL_SYNC_SEC=5`
- `AGENT_KB_REQUIRE_EVIDENCE=1`
- `AGENT_METADATA_FALLBACK_ONLY_WHEN_MISSING=1`
- `AGENT_INSIGHT_OBJECT_FASTPATH=1` (인사이트 객체 즉시 참조 활성)
- `AGENT_INSIGHT_FASTPATH_ALLOW_WITH_PASSTHROUGH=1` (`AGENT_LLM_REQUEST_PASSTHROUGH=1`이어도 근거 기반 fast-path 허용)
- `AGENT_INSIGHT_OBJECT_MAX_CANDIDATES=0` (고정 샘플링 제한 비활성, coverage 기반)
- `AGENT_INSIGHT_OBJECT_DB_FETCH_LIMIT=120` (한 턴에서 과도한 후보 확장 방지용 기본 상한)
- `AGENT_OBJECT_PICK_MIN_CONFIDENCE=0.55` (근거 기반 객체 선택 최소 신뢰도)
- `AGENT_OBJECT_RESOLVE_BATCH_SIZE=40` (대규모 후보군 LLM 선택 배치 크기)
- `AGENT_OBJECT_RESOLVE_MAX_BATCHES=6` (배치 선택 최대 반복 수)
- `AGENT_GENERIC_ASK_GUARD=1` (generic ask 반복 시 자동 재계획)
- `AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC=20` (선택 객체 기반 SQL 작성 LLM 타임아웃, timeout 완화)
- `AGENT_OBJECT_RESOLVE_MODEL=gpt-5-mini` (객체 선택 전용 모델 분리)
- `AGENT_SQL_COMPOSE_MODEL=gpt-5-mini` (SQL 작성 전용 모델 분리)
- `AGENT_SQL_REVIEW_MODEL=gpt-5-mini` (SQL grounding review 전용 모델 분리)
- `AGENT_SQL_GROUNDED_REVIEW=1` (선택 객체 SQL 실행 전 grounding reviewer 수행)
- `AGENT_SQL_GROUNDED_REWRITE_ON_FAIL=1` (review 실패 시 LLM 재작성 허용)
- `AGENT_SQL_GROUNDED_BLOCK_ON_FAIL=1` (review 실패 SQL 실행 차단)
- `AGENT_KNOWLEDGE_SQL_FALLBACK=1` (plan이 `ask`/메타로 수렴할 때 knowledge 근거 기반 SQL 1회 강제 생성)
- `AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC=20` (fallback LLM SQL compose 타임아웃)
- `AGENT_KNOWLEDGE_SQL_FALLBACK_MAX_OBJECT_TRIES=2` (fallback에서 객체 후보 재시도 최대 횟수)
- `AGENT_AUTO_FIX_SQL=1` (syntax/not-found 오류에 대한 LLM 기반 SQL 보정 활성)
- `AGENT_DISABLE_AUTO_RETRY=0` (오류 후 자동 재시도 비활성화 금지)
- `AGENT_ERROR_AUTO_RECOVERY=1` (SCHEMA/TABLE/COLUMN not-found 자동 복구 활성)
- `AGENT_AUTO_CONTINUE_AFTER_STEP=0` (정상 결과 1회 반환 후 불필요한 자동 `continue` 루프 방지)
- `AGENT_RAG_DOC_OBJECT_SCORE_BOOST=24` (RAG 문서 FT 점수를 객체 랭킹에 반영하는 가중치)
- `AGENT_SCHEMA_USAGE_RECORD_STRICT=1` (모호 요청 결과의 `table_pref` 오염 방지)
- `AGENT_PLAN_TIMEOUT_SEC=35` (기본 플래너 타임아웃)
- `AGENT_PLAN_TIMEOUT_RECOVERY_SEC=20` (복구/재시도 단계 플래너 타임아웃)
- `AGENT_PLAN_TIMEOUT_MIN_SEC=8` (플래너 최소 타임아웃)
- `AGENT_RAG_PRIORITY_TIMEOUT_SEC=12` (RAG 우선 재플랜 타임아웃)
- `AGENT_RAG_PRIORITY_FIRST=1` (지식 근거가 있으면 기본 플래너 전에 RAG 우선 플랜 단축 경로 시도)
- `AGENT_RAG_PRIORITY_SHORT_CIRCUIT=0` (모호 follow-up에서 임의 객체 short-circuit 비활성)
- `AGENT_AUX_SKIP_NEAR_DEADLINE_MS=15000` (마감 임계치에서 summary/validation 생략)
- `AGENT_OPENAI_MAX_RETRIES=0` (플래너/요약 호출의 SDK 재시도 비활성화로 상한 시간 준수)

## 메모리/로그 운영
- `AgentMemoryFacts`, `AgentMemoryFactEntries`는 복수 근거를 보존한다.
- Fact에는 최소 `SourceRunId`, `SourceType`, `Weight/Confidence`를 보존한다.
- 지식 참조 경로 로그:
- `/shared/logs/insight_route.log`
- 필수 기록: 사용한 스키마/테이블, 근거 source, fallback 사유
- 타이밍 로그:
- `/shared/logs/timing.log`
- `/shared/logs/timing_breakdown_<run_id>.json`
- 실행 SQL 로그:
- `/shared/logs/*_executed_sql.log`

## 인사이트/근거 참조 운영 규정 (신규)
- 관련 질문에서 먼저 `AgentMemoryFactEntries` 근거를 조회한다.
- 근거 충족 시 `search_objects` 같은 메타탐색을 건너뛴다.
- 근거 부족일 때만 메타탐색을 수행하고, 부족 이유를 로그에 남긴다.
- 동일 요청 도메인에서 이미 검증된 객체가 있으면 해당 객체를 우선 사용한다.
- `AGENT_LLM_REQUEST_PASSTHROUGH=1`일 때는 모호 요청의 객체 short-circuit를 기본 비활성으로 둔다.
- 선택 객체 SQL은 실행 전 grounding review를 통과해야 하며, 실패 시 재작성 또는 차단한다.

## 맥락 품질 재발 방지 (P0/P1/P2)
### P0 (즉시 적용/회귀 불가)
- `origin_request`는 주제 전환 시 갱신한다.
- 요청/의도 판단에 문자열 휴리스틱을 사용하지 않는다.
- 코드에서 LLM 행동을 제약하는 강제 분기 변수 주입을 금지한다.
- 요청 원문을 임의 가공하지 않는다.
- 이미 답한 질문 반복 금지.
- 사용자 교정사항은 최우선 제약으로 즉시 반영.

### P1 (우선 적용)
- 연속 `ask` 구간에서도 요약/맥락 갱신.
- 검증된 결과를 전역 지식에 반영.
- 지식 충돌 시 최신/고신뢰 근거 우선.

### P2 (차후 적용)
- 스키마 메타는 요청 관련 객체 중심으로 전달.
- Fact 모델은 다중 근거/출처/신뢰도 보존을 확장.

## 비전문가 사용자 가정
- 사용자는 모호한 요청을 한다.
- 객체명/컬럼명을 틀릴 수 있다.
- "다시/이어서/알아서" 같은 follow-up이 많다.
- 오류 원인 분석을 agent에 위임한다.

### 대응 원칙
- 최소 검증 후 실행 가능한 결과를 우선 반환.
- 불확실성은 1회만 질문하고, 가능하면 실행 우선.
- 오류 시 동일 쿼리 반복 금지, 오류 유형별 복구 경로 전환.

## 테스트 조건
- 기존 테스트와 약간 다른 노이즈를 포함한다.
- 단순/일반/복잡 조건을 모두 포함한다.

## SVN 커밋 규칙
- **작업 완료 시 반드시 SVN에 커밋한다.**
- 커밋 메시지 형식:
  - 첫 줄: 전체 요약 (한 문장)
  - 빈 줄 2개
  - 이후: 간단한 불렛(`-`) 메시지로 세부사항 기입
- 예시:
```
로컬 LLM 게이트웨이 연동 및 Web UI API 키 선택적 전송


- config/agent_core/llm에 LLM_BASE_URL 지원 추가
- docker-compose에 llm-shared 네트워크 연결
- Web UI에서 LOCAL_LLM 모드 시 API 키 없이 전송 가능
- model_catalog에 local LLM 모델(auto/edge/core/code) 추가
```

## 완료 조건
- `make start`로 MySQL + 웹 + 브라우저 + 인사이트 워커 정상 기동.
- `make ask` 정상 동작.
- 브라우저 제어 기능 정상.
- MCP 사용 시 `make mcp-test` 통과.
- C/E/F/G 회귀 없음.
