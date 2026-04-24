---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: Web UI 앱과 정적 자산을 기능 단위 구조로 이관
- Files: src/app.py, src/static/*
- Notes: 코어 로직은 별도 feature에 유지

## CHG-20260414-0002
- Date: 2026-04-14
- Summary: 메인 워크스페이스를 작업 중심 콘솔 레이아웃으로 재개편하고 로그인/드로어/빠른 액션 UX를 재정의
- Files: src/static/index.html, src/static/styles.css, docs/TASK.md, docs/REPORT.md, docs/TEST.md
- Notes: 기존 기능 ID와 JS 결합은 유지하고, 시각 체계와 정보 배치를 전면 수정

## CHG-20260415-0003
- Date: 2026-04-15
- Summary: 계정/권한 체계를 실제 인증 모델로 교체하고, 대화 소유권과 관리자 화면 기준으로 Web UI를 전면 재구성
- Files: src/app.py, src/static/index.html, src/static/styles.css, src/static/app.js, src/static/admin.html, src/static/admin.js, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../.env
- Notes: `WebUsers`/`WebKeywords` 런타임 경로를 제거하고 `WebAccounts`/`WebAuthSessions`/`AgentCoreConversations.owner_account_id`를 기준으로 동작하도록 변경. 로컬 LLM 게이트웨이 미가용 시 false positive를 막기 위해 연결 가능 여부를 세션 응답에 반영

## CHG-20260415-0004
- Date: 2026-04-15
- Summary: App-Shell 기준 메인 레이아웃, 프로필 드로어, 병렬 대화 UX, 관리자 콘솔 사용성을 강화
- Files: src/app.py, src/static/index.html, src/static/styles.css, src/static/app.js, src/static/admin.html, src/static/admin.js, docs/TASK.md
- Notes: 사이드바 하단 프로필 트리거와 드로어 구조를 추가했고, `state.busyConversations`로 대화별 요청 상태를 분리했다. `/api/auth/me` 비밀번호 변경 엔드포인트, Admin 검색/필터/페이지네이션이 함께 추가되었다.

## CHG-20260415-0005
- Date: 2026-04-15
- Summary: 프로필 드로어를 3탭 구조로 재편하고 API Vault를 통합했으며, UI 정책/학습 문서를 최신화
- Files: src/static/index.html, src/static/styles.css, src/static/app.js, docs/AGENTS.md, docs/TASK.md, ../../../docs/LEARNINGS.md
- Notes: 계정별 설정을 탑바에서 제거하고 프로필 드로어의 `계정 / 보안 / API Vault` 탭으로 이동했다. 로그아웃 시 드로어 및 인증 폼 상태 초기화 규칙을 코드와 문서에 동시에 반영했다.

## CHG-20260415-0006
- Date: 2026-04-15
- Summary: 내장 Local LLM 소유 구성을 제거하고 외부 provider 소비 계약으로 전환
- Files: src/app.py, src/static/index.html, src/static/app.js, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../.env, ../../../../docker-compose.yml, ../../../../Makefile
- Notes: 현재 repo는 더 이상 Ollama/local-llm-gateway를 직접 기동하지 않는다. `LOCAL_LLM_API_BASE` 연결 가능 여부만 세션과 오류 메시지에 반영한다.

## CHG-20260416-0007
- Date: 2026-04-16
- Summary: Web UI 권한 모델을 RBAC + account override로 cutover하고 관리자 콘솔을 Accounts/Roles 2영역으로 재구성
- Files: src/app.py, src/static/index.html, src/static/app.js, src/static/admin.html, src/static/admin.js, src/static/styles.css, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../../../docs/STATUS.md
- Notes: role명 휴리스틱을 제거하고 `permission code + ownership`만으로 권한을 판정한다. `WebPermissions`/`WebRoles`/`WebRolePermissions`/`WebAccountPermissionOverrides`가 단일 정본이며, legacy `Role`/`Can*` 컬럼은 마이그레이션 원본으로만 남긴다. `/api/clear_memory`는 410으로 유지하고, 계정 삭제는 soft delete + 세션 폐기로 고정했다.

## CHG-20260421-0008
- Date: 2026-04-21
- Summary: 대화 사이드바의 내 계정/타 계정 대화 구분 하이라이트·정렬과 대화/말풍선 단위 fork(복제) 기능 도입
- Files: src/app.py, src/static/index.html, src/static/app.js, src/static/styles.css, docs/TASK.md, docs/FUNCTION.md, docs/REPORT.md, docs/REVIEW.md
- Notes: 사이드바는 `내 대화` / `타 계정 대화` 2 그룹으로 분할 렌더되고 내 대화는 primary 좌측 바 + 틴트, 타 계정 대화는 owner 뱃지를 강조한다. 말풍선 user 메시지에 `is-own-message` / `is-other-message` 톤 분리와 `나 (<username>)` / `<owner_username>` 라벨을 적용했다. 신규 `POST /api/fork_conversation` 은 `conversation.create` 권한과 원본 대화의 read 권한을 동시에 요구하며, 원본 `topic`(앞에 `[Fork] ` 접두사)과 메시지(internal 제외)를 `AgentMemoryMessages` 에 `CreatedAt` 보존 + `MetaJson.forked_from_*` 추가로 복제한다. 프론트엔드는 헤더 `대화 복사`(전체 복제), 말풍선 hover 액션 `여기서 분기`(부분 복제) 버튼을 제공한다.

## CHG-20260421-0009
- Date: 2026-04-21
- Summary: System Prompt Depth 3 계층(Product→Role→Account) + Product 단위 DB 접근 화이트리스트 도입
- Files: ../feature-0002-agent-core/src/agent_core.py, ../feature-0002-agent-core/src/modules/tools.py, src/app.py, src/static/admin.html, src/static/admin.js, src/static/index.html, src/static/app.js, src/static/styles.css, docs/TASK.md, docs/FUNCTION.md, docs/REPORT.md, docs/REVIEW.md
- Notes: 신규 테이블 `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` + `AgentCoreConversations.product_id` 컬럼 추가. `_runtime_tables_available` probe list 에 신규 3 테이블 포함해 기존 배포 재진입 시 자동 마이그레이션. 신규 permission `product.manage` / `system_prompt.manage.role.any` 를 `admin` 역할에 기본 부여, seed 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) 생성. `agent_core.compose_system_prompt` 가 base prompt 뒤로 `## PRODUCT CONTEXT` → `## ROLE GUIDANCE` → `## ACCOUNT PREFERENCES` 블록을 순차 append. `modules/tools.py` 에 모듈 전역 `_ACTIVE_SCHEMA_ALLOWLIST` + `set_/clear_active_schema_allowlist()` + `_whitelist_violation()` 을 두고, 모든 DB 도구 핸들러가 호출 직전 스키마 참조를 검사(`execute_sql` 은 `schema.table` 정규식 추출). `run_agent` 는 `allowed_schemas` kwarg 을 받아 try/finally 로 whitelist 를 세팅/복원하는 얇은 래퍼 + 본문 `_run_agent_core` 로 분리. 보안 수정: `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` 우회를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 직접 참조가 whitelist 로 차단되도록 했다. 관리 콘솔은 `계정 카테고리` / `상품 카테고리` 그룹 구분선 + `상품 (Products)` 탭(Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집기) 을 추가, Roles detail 에 Role scope prompt 편집기(Product 드롭다운 포함), 프로필 드로우에 `프롬프트` 탭(Account scope) 을 추가. 신규 API: `GET/POST/PATCH/DELETE /api/admin/products`, `PUT /api/admin/products/{id}/databases`, `GET/PUT /api/admin/system-prompts`, `GET/PUT /api/auth/me/system-prompt`. 세션 응답에 `products` / `default_product_id` 포함. `/api/new_conversation` / `/api/fork_conversation` / `/api/ask` 가 대화 `product_id` 를 해석해 `run_agent` 에 `product_id`/`role_id`/`account_id`/`allowed_schemas` 를 전달.

## CHG-20260422-0011
- Date: 2026-04-22
- Summary: agent_core `OpenAI()` 초기화에 per-call `timeout` + `max_retries` 를 적용하고 TASK-0034 러너 `ASK_TIMEOUT_SEC` 을 서버 `run_timeout_sec` 이상으로 정렬
- Files: ../feature-0002-agent-core/src/agent_core.py, tests/task0034_runner.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md
- Notes: TASK-0034 Q4/Q5 실패 원인 분석에서 확인된 근본 원인 1(agent_core 의 `OpenAI(**client_kwargs)` 가 timeout 파라미터 없이 초기화돼 LLM 호출이 무한 대기) 과 근본 원인 2(러너 600s < 서버 900s 로 클라이언트가 먼저 포기해 좀비 스레드 발생) 를 동시 대응. 1) `agent_core.py:26~32` import 에 `AGENT_OPENAI_MAX_RETRIES` 추가, `agent_core.py:1134~1139` `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. 현재 `.env` 값 기준 `timeout=300s`, `max_retries=0`. 2) `tests/task0034_runner.py:52~56` `ASK_TIMEOUT_SEC=600.0` 을 `ASK_TIMEOUT_SEC=960.0` 으로 인상하고 산정 근거 주석(`max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=900`) 추가. 검증: (a) `python3 -m py_compile` 통과, (b) `docker compose up -d --force-recreate web` 후 신규 컨테이너(StartedAt=2026-04-22T01:02:40Z) 기동, `docker exec grep` 으로 `timeout=max(5` 와 `AGENT_OPENAI_MAX_RETRIES` 반영 확인, `modules.config` import 시 `AGENT_TIMEOUT_SEC=300`/`AGENT_OPENAI_MAX_RETRIES=0` 확정, (c) bootstrap_admin 로그인 후 신규 대화로 `gpt-5.4-mini` 모델 `/api/ask` 한 턴 실행 — HTTP 200, wall=5s, steps_count=1, `list_schemas` + `SELECT FROM information_schema.schemata` 정상 실행.

## CHG-20260422-0010
- Date: 2026-04-22
- Summary: (문서화 전용) `/api/progress` 폴링 루프의 `setInterval` → 순번 기반 `setTimeout` + AbortController + 적응형 주기 리팩터 사후 리뷰 · 학습 기록
- Files: docs/TASK.md, ../../docs/LEARNINGS.md, docs/MODIFY.md
- Notes: 코드 변경 없음. TASK-0036 커밋(27127b9) 에 번들됐지만 commit message 에 언급되지 않은 폴링 리팩터를 TASK-0037 로 분리해 설계·검증·학습 내용을 사후 문서화한다. 검증: (a) `grep -c "setInterval" src/static/app.js` = 0, (b) 5 개 적응형 상수(`PROGRESS_FETCH_TIMEOUT_MS=4000`, `PROGRESS_POLL_ACTIVE_MS=1200`, `PROGRESS_POLL_IDLE_MS=3000`, `PROGRESS_POLL_HIDDEN_MS=10000`, `PROGRESS_POLL_ERROR_MS=8000`) 모두 `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조, (c) 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 수용하고 서버 run_id 와 불일치 시 `next_after_step=0` 으로 리셋 (line 4405-4406), (d) `curl -sk -b cookie https://127.0.0.1:18080/api/progress?conversation_id=&client_run_id=STALE` 가 HTTP 200 + `{steps, status, status_at, step_count, run_id, conversation_id}` 스키마를 반환. `docs/LEARNINGS.md` 에 `LRN-20260422-0011 장시간 작업 폴링 5원칙(순번 기반 setTimeout 체인 + AbortController + 요청당 timeout + document.hidden 감지 + 서버측 delta with client_run_id)` 을 추가.

## CHG-20260422-0014
- Date: 2026-04-22
- Summary: 클라이언트 타임아웃 시 대화 지속 복구 경로 도입 — 서버 read-only 상태/결과 엔드포인트 2종 + 브라우저 복구 다이얼로그 + test runner attach 분기 (TASK-0041)
- Files: src/app.py, src/static/app.js, tests/task0034_runner.py, docs/TASK.md, docs/MODIFY.md, docs/REPORT.md, docs/FUNCTION.md, docs/REVIEW.md, ../../docs/LEARNINGS.md
- Notes: 사용자 요청(2026-04-22) — "클라이언트 타임아웃이 나타날 경우 해당 대화를 사용자 판단하에 지속적으로 처리할 수 있는 방법" 에 대응. 에이전트 작업자 스레드는 `asyncio.to_thread` 로 HTTP 연결과 독립적으로 실행되므로, 클라이언트(httpx/브라우저/proxy)가 ReadTimeout 으로 끊겨도 백엔드에서 계속 완료까지 진행한다. 이 자원을 회수할 read-only 경로가 없어 기존엔 결과가 유실됐다. `src/app.py` 에 `_ASK_TERMINAL_STATUSES={done,error,canceled}` / `_ASK_SUCCESS_STATUSES={done,canceled}` 상수와 `_load_run_meta_kv(conn, conversation_id)` 단일 쿼리 KV loader, `_build_ask_status_snapshot(conn, conversation_id)` 스냅샷 빌더, `GET /api/ask_status` (1-shot, `conversation.read.own/any` 권한) 과 `GET /api/ask_result` (long-poll `wait<=60s`, deadline/0.5s interval, terminal 시 assistant/steps 전문, 타임아웃 시 `{timeout:true}`) 2 엔드포인트를 추가. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새로운 실행을 시작시키지 않는다. `src/static/app.js` 에 `ASK_ATTACH_POLL_WAIT_SEC=45` / `ASK_ATTACH_MAX_TOTAL_SEC=1800` 상수, `fetchAskStatus`/`showTimeoutRecoveryDialog`(3 버튼 모달: 요청 취소/즉시 답변/계속 기다리기, Escape 로 dismiss) / `attachAndWaitForResult` (long-poll 루프, run_id 고정, terminal 시 `refreshWorkspace`) 를 추가했고, `sendPrompt()` 의 `apiFetch("/api/ask",...)` 를 try/catch 로 감싸 실패 + `is_processing=true` 이면 다이얼로그 → 사용자 선택에 따라 `/api/cancel`/`/api/finalize`/attach 로 분기한다. `initializeWorkspace()` 끝에 boot-time auto-attach: 페이지 로드 시 현재 대화가 서버에서 처리 중이면 자동으로 busy 상태 + progress polling + attach 를 재개한다. `tests/task0034_runner.py` 에 `ATTACH_TIMEOUT_SEC=960.0` / `ATTACH_POLL_WAIT_SEC=45` 상수, `_steps_from_attach(meta)` 헬퍼, `_attach_run(client, cid, msg, t0)` 함수(ask_status → ask_result long-poll 반복)를 추가했고, 기존 `httpx.ReadTimeout` 분기가 `{"error": "client-read-timeout"}` 을 반환하는 대신 `_attach_run` 으로 이어받아 `attached_after_timeout=True, attach_verdict="succeeded-via-attach"|"attach-status-<status>"` 메타와 함께 turn 기록을 정상 작성한다. 검증: (a) `python3 -m py_compile` 3 파일 통과, (b) `node --check static/app.js` JS 문법 OK, (c) `make web` 재빌드/재기동 → 새 sha256 이미지 반영 + `/api/ask_status` / `/api/ask_result` 401 응답으로 라우팅 확인, (d) terminal 상태 대화에 대한 `/api/ask_status` + `/api/ask_result` 가 38ms 이내 snapshot/assistant 반환 확인, (e) `python3 tests/task0034_runner.py --target api --only Q4,Q5` 재수행. 보안: `/api/ask_status`/`/api/ask_result` 는 read-only 이며 기존 `conversation.read.own/any` 권한 모델 재사용 — 새로운 공격 표면 추가 없음. 범위: 서버 1 파일 약 190 줄, 프론트 1 파일 약 230 줄, 테스트 1 파일 약 95 줄.

## CHG-20260422-0013
- Date: 2026-04-22
- Summary: SQL schema whitelist 정규식을 context-aware 2 단계 스캐너로 재작성 — `alias.column` 오탐으로 합법 SQL 이 차단되던 TASK-0036 회귀 제거 (TASK-0040)
- Files: ../feature-0002-agent-core/src/modules/tools.py, docs/TASK.md, docs/MODIFY.md, docs/REPORT.md, docs/REVIEW.md, ../../docs/LEARNINGS.md
- Notes: 기존 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 는 SQL 문맥 구분 없이 모든 `x.y` 패턴을 `schema.table` 로 간주했다. `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a` 같은 alias.column 토큰이 전부 schema 후보로 수집되어 `_whitelist_violation` 이 Product whitelist=`{dbauth,dbgame,dblog}` 에서 `be`/`bb` 불허로 판정 → TASK-0034 Q4 재수행의 모든 턴이 `BLOCKED_SCHEMAS=bb,be` 로 실패했다. 수정: `_SCHEMA_TABLE_REF_RE` 를 제거하고 `_TABLE_LIST_RE`(`FROM`/`JOIN` 키워드 뒤 ~ 다음 절 키워드 `ON|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|UNION|JOIN|FROM|;|)|$` 전까지 lookahead) + `_INNER_REF_RE`(그 구간 내부에서 `schema.table` 만 추출) 2 단계 스캐너로 재작성. SELECT 절/WHERE 절/ON 절의 alias.column 은 FROM/JOIN 슬라이스 바깥이어서 더 이상 매칭되지 않는다. 검증: in-process 15 테스트 케이스 (단일 FROM / FROM+WHERE alias / FROM+JOIN+alias.col ON / 혼합 스키마 / 백틱 / subquery / 비허용 schema 차단 / SELECT 절 alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / 중복 refs dedup) 전부 expected refs 일치, `_whitelist_violation` 이 Q4-like SQL 에서 `{dblog}` 만 검출하고 `dbstat.foo` 는 여전히 차단. 범위: `modules/tools.py` 약 25 줄 (`_SCHEMA_TABLE_REF_RE` 제거 + 2 단계 스캐너 추가). TASK-0034 Q4/Q5 재수행을 가능하게 하는 선행 블로커 해제.

## CHG-20260422-0012
- Date: 2026-04-22
- Summary: 메타데이터 4 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 를 Product whitelist 와 무관하게 항상 agent tool 에서 접근 가능하도록 bypass 정책 확장 (REV-20260421-0005 일부 완화)
- Files: ../feature-0002-agent-core/src/modules/tools.py, docs/TASK.md, docs/MODIFY.md, docs/REVIEW.md, docs/FUNCTION.md, docs/REPORT.md
- Notes: 사용자 지시(2026-04-22, "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지") 에 따라 Product 단위 DB whitelist 의 bypass 집합을 확장. `tools.py` 의 `_SYSTEM_SCHEMAS` 단일 frozenset 을 `_METADATA_SCHEMAS`(information_schema/sys/mysql/performance_schema, whitelist bypass) + `_INTERNAL_SCHEMAS`(agent_memory, whitelist 차단 유지) 두 frozenset 으로 분리했고, `_SYSTEM_SCHEMAS` 는 이들의 union 으로 남겨 기존 `_is_user_schema` / `search_tables` UX 필터 동작을 보존했다. `_whitelist_violation` 의 `allowed` 집합을 `{information_schema}` 에서 `_METADATA_SCHEMAS` 전체로 교체. 차단 시 에러 메시지 끝에 "메타데이터 스키마(information_schema/sys/mysql/performance_schema) 는 항상 접근 가능" 한 줄을 덧붙여 LLM 이 잘못 참조한 user schema 를 information_schema 경로로 리디렉션할 수 있도록 힌트를 남긴다. `agent_memory` 는 계속 차단(타 계정 대화/세션/권한 override 보호). 검증: (a) `python3 -m py_compile modules/tools.py` 통과, (b) `docker compose up -d --build web` + `--force-recreate` 후 컨테이너 in-process 호출 8 케이스(whitelist=None/메타데이터 4종 bypass/허용 user schema/혼합 통과/agent_memory 차단/비허용 user schema 차단/`_is_user_schema` UX 필터 보존) 모두 통과, (c) `execute_tool` 경로로 `execute_sql("SELECT ... FROM information_schema.TABLES")` / `describe_schema("sys")` / `execute_sql("... performance_schema.tables")` 정상 응답, `execute_sql("... mysql.user")` 는 tool-level whitelist 통과 후 DB 에서 실제 행 반환(MySQL GRANT 가 열려있음 — REV-20260422-0006 에 2 차 방어 필요성 기록), `execute_sql("... agent_memory.AgentMemoryMessages")` 와 임의 비허용 `dbstat.*` 은 여전히 차단. 범위: 코드 변경 `tools.py` 1 파일 약 14 줄. `list_schemas` 결과에 메타데이터를 노출할지는 UX 결정 영역으로 현 상태(숨김) 유지.

## CHG-20260423-0015
- Date: 2026-04-23
- Summary: Approach A wedge (사업팀 자가서비스) pilot infra — sales role seed + role-scope system prompt seed + 복제 DB 접속 envelope + pilot onboarding runbook (TASK-0044)
- Files: src/app.py, ../feature-0002-agent-core/src/modules/config.py, ../feature-0002-agent-core/src/modules/db.py, ../../.env.example, docs/TASK.md, docs/MODIFY.md, docs/FUNCTION.md, ../../docs/STATUS.md
- Notes: office-hours 2026-04-23 세션에서 승인된 Approach A (사업팀 통계/단순 데이터 자가서비스 wedge) 의 infra 구현. (1) `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 를 추가 — operator 권한에서 `conversation.delete.own` 만 제거한 9 개 권한(conversation.create/ask/suggestions.read/list.own/read.own/file.read.own/rename.own/cancel.own/finalize.own) 으로 사업팀 pilot 이 자기 대화 흐름은 조작하되 과거 요청 기록 삭제는 막는 subset. (2) 신규 `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 부트스트랩 단계 — `_load_system_prompt` 로 존재 여부 먼저 확인해 idempotent(관리 콘솔 수정 존중), 없을 때만 `_upsert_system_prompt(scope='role', role_id=<sales>, product_id=None)` 로 4 지침(단순 조회 → 문장 / 집계 → 결과셋 표 / ad-hoc 분석 → DBA 팀 이관 안내 후 종료 / DB 쓰기 쿼리 거부) prompt 를 insert. `_ensure_seed_products` 바로 뒤에 호출해 sales role + WebSystemPrompts 스키마 준비 모두 보장된 상태에서 실행. `agent_core.compose_system_prompt` 가 기존 로직(TASK-0036) 그대로 `## ROLE GUIDANCE (sales)` 블록으로 주입한다. (3) `modules/config.py` 에 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` env 4 개 + 파생 `REPLICA_DB_ENABLED=bool(REPLICA_DB_HOST)` 추가, `__all__` 에 5 개 export. `modules/db.py::connect()` 에 라우팅 로직 — `REPLICA_DB_ENABLED` 가 True 이고 요청된 `database` 가 `MEMORY_DB`(=agent_memory) 가 아니면 복제 인스턴스(host/port/user/password) 로 접속, 그 외(미설정/메모리 연결/database=None) 는 기존 primary 파라미터. memory DB 는 항상 primary 이므로 대화·세션·권한 정본이 보존된다. (4) `.env.example` 에 `REPLICA_DB_HOST=` / `REPLICA_DB_PORT=` / `REPLICA_DB_USER=` / `REPLICA_DB_PASSWORD=` 4 placeholder + 사업팀 pilot 이름 치환용 `WEB_PILOT_SALES_USERNAMES=` 주석 추가. 실제 접속 정보/계정 이름은 `.env` 또는 docker-compose secret 으로만 주입(commit 금지). (5) pilot 계정 자동 생성은 하지 않음 — admin 이 관리 콘솔에서 수동 발급하도록 docs/TASK.md §TASK-0044 pilot onboarding runbook 에 3 단계 절차(계정 발급 / Product whitelist 2 가지 옵션 / 복제 DB 접속 등록) 기록. (6) Product 단위 접근 DB 화이트리스트 조정은 런타임 코드 변경 없이 runbook 으로 해결 — 옵션 A(KR Product 에서 dbauth 제거) 또는 옵션 B(KR-Sales Product 신규 생성) 중 조직 정책에 맞게 선택. 현재 seed 는 호환성을 위해 변경하지 않음. 검증: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/db.py` 통과, (b) `docker compose up -d --build web` 후 `/api/session` HTTP 200 OK + bootstrap_admin 로그인 성공, (c) MySQL 에 `SELECT r.RoleKey,r.Name,COUNT(rp.PermissionId) FROM WebRoles r LEFT JOIN WebRolePermissions rp ON r.Id=rp.RoleId WHERE r.RoleKey='sales' GROUP BY r.Id` 결과 1 row `sales / 사업팀 / 9`, (d) `SELECT LEFT(Content,60) FROM WebSystemPrompts WHERE Scope='role' AND RoleId=(SELECT Id FROM WebRoles WHERE RoleKey='sales') AND ProductId IS NULL` 1 row 에 "당신은 게임 사업팀을 지원하는 DBA 어시스턴트다" 로 시작. 범위: 코드 3 파일 약 70 줄(app.py +54, config.py +12, db.py +11), `.env.example` +6 줄, 문서 4 파일. 사업팀 pilot 의 단순/집계/ad-hoc 실제 응답 acceptance 3 개는 pilot 계정 발급 이후 admin 이 수동 확인(TASK.md AC 체크리스트의 미체크 3 항목) 하도록 남겨둔다 — 현재 환경에 사업팀 pilot 계정 발급이 선행되지 않아 코드 단독으로는 검증 불가.


## CHG-20260424-0016
- Date: 2026-04-24
- Related Requirement: TASK-0045 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — Web UI feature가 "UI + 서버 측 로직 전체" 범위임을 명시, System Prompt 3계층 조립의 Web feature 귀속 근거, layering 위반 방지, whitelist 관리 onboarding 시나리오.
- Files: unit/feature-0003-agent-web-ui/docs/ANCHOR.md, unit/feature-0003-agent-web-ui/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. System Prompt 조립을 core로 옮기려는 향후 요청은 §1 / §2 Alt-A와 충돌 감지 (Conflict Protocol 발화). whitelist 정책 변경 시 §3 시나리오가 onboarding 진입점 역할.
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
