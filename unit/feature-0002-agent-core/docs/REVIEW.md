---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260615-0255 [SUBAGENT:5-lens adversarial — db.py blast-radius / GRANT trap / credential-leak / soft-telemetry / regression] — SHIP_WITH_FIXES
- Date: 2026-06-15
- Cycle: TASK-0255 (insight 연결 탄력성 R1 로그 edge-trigger / R2 PG datasource_health / R3 control-plane bounded timeout)
- 패널: 5개 distinct-lens 적대 리뷰어(각자 REFUTE 시도) + adjudicator 코드대조 종합 (Workflow `task0255-adversarial-review`).
- Verdict: **SHIP_WITH_FIXES**. 제출된 BLOCKER 5건은 전수 코드대조 결과 **환각(없는 코드/오독 라인 인용)** 으로 전부 기각(실 차단 결함 0건). 정당 MAJOR 2건 + MINOR 반영:
  - **M-2 (필수·자격증명 불변식)**: except 로그 `err=%r, _ds_exc`(raw driver 예외 — args 에 DSN/계정 가능) → `err=%s, str(_ds_exc)[:160]`. 수정 완료.
  - **M-1 (메모리 누수)**: `_LAST_DS_SCAN_STATUS` 가 삭제·rename datasource 의 stale key 무한 누적 → 매 cycle registry 동기 prune(PG prune 동형) 추가. 수정 완료.
  - **MINOR**: success `else` 블록 try/except 감싸 R2/R1 격리 명문화, `_pg` upsert `last_checked_at = COALESCE(...)` 보존, web `_read_insight_datasource_health` 조회실패 debug 로그. 반영.
- 기각 근거(요약): control-plane breaker 미적용 불변식은 `should_fast_fail`/`status_for`(scope_key None→무동작)로 코드 확인; prune 은 실패 datasource 도 `_record_ds_health` 로 keep 에 포함되어 정상 행 미삭제; alembic 0006 체인 0001→…→0006 무결; psycopg `connect_timeout` 은 TCP 핸드셰이크 전용(쿼리 실행 무관). 상세는 워크플로 산출.
- 자격증명 노출면 전수: PG 행·upsert params·web 응답·admin.js clean(L3 검증), 로그 1곳(M-2)만 수정 필요했고 반영.

## REV-20260612-0248 [SCHEMA-ONLY:additive-column, cross-feature] — SHIP
- Date: 2026-06-12
- Cycle: TASK-0248 (관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환 — 주 cycle 은 web feature-0003, 본 feature 영향은 **스키마/alembic 만**)
- 검토: `agent_runtime.core_conversations` 에 `blocked_at timestamptz`/`blocked_reason varchar(256)` **additive** 추가(데이터 무손실 — 기존 행 NULL=미차단). alembic `0005_core_conv_blocked` down_revision=`0004_rag_objects_datasource` 체인 정상, ADD/DROP COLUMN IF EXISTS 멱등. agent-core 런타임 코드(insight/ask/agent_core) 무변경 — 차단 로직 전량 web `/api/ask`. 적대적 보안/정합 리뷰 본문은 feature-0003 REV-20260612-0248(2-agent) 참조(SHIP).
- 검증: py_compile + make test 컨테이너 전체 회귀 0. Cross-ref: feature-0003 REV-20260612-0248 / CHG-20260612-0248 / TASK-0248.

## REV-20260612-0250 [SUBAGENT:conn-health-monitor-adversarial] — SHIP-WITH-FIXES(BLOCKER 2 + MAJOR 3 + MINOR 3 흡수)
- Date: 2026-06-12
- Cycle: TASK-0250 (연결 health 모니터 — background 사전판정 격리, **Major §12.3** 런타임+관리콘솔 연결 경로)
- 패널: outside-voice 적대적 동시성/보안(SSRF) 리뷰 subagent **2-pass**(1차 NOT-SHIP → 발견 전량 흡수 → 2차 재게이트 SHIP-WITH-FIXES). 런타임 가용성+SSRF 표면 변경이라 [[feedback_outside_voice_for_rbac]] 정합으로 외부 시각 필수.
- 1차 발견(NOT-SHIP) 및 흡수:
  - **B1 (BLOCKER) TCP 성공 ≠ DB 연결 가능**: TCP-only probe 가 max_connections 소진·DB 재시작(TCP 는 열림)을 healthy 오판 → worker 재점유로 설계 목적 무력화. → **2단 probe**: TCP 선검사(100ms fast-fail) + 실제 DB connect+SELECT 1(`probe_datasource`, 적응형 1s→10s). 회귀 `test_monitor_tcp_open_db_down_marks_unstable`.
  - **B2 (BLOCKER) 1회 blip 전면 차단**: foreground 1회 실패 즉시 unstable. → 복구를 background 실제 DB probe(2s→×2→60s)가 담당 → false-positive 창 bounded(~2s), foreground half-open trial 제거(thundering-herd 함정 원천 차단).
  - **M1 dead breaker config + 미문서 신규 env**: → `AGENT_DB_BREAKER_*` 3 제거 + `.env.example` 에 `AGENT_CONN_*` 9 문서화.
  - **M2 pool 기아→stale→gate 무력화**: → TCP fast-fail(죽은 서버 10s 점유 안 함) + `_loop` next_due 정렬 + unstable backoff + `should_fast_fail` stale 강등을 `monitor_running()=False` 한정.
  - **M3 SSRF rebinding + 상시 SYN**: → probe 직전 `_is_blocked_target`(getaddrinfo 재해석 후 메타데이터/loopback/link-local/multicast/reserved fail-closed, 사설 RFC1918 운영허용). 잔여: 사설 rebinding 은 runtime agent connect 와 동일 노출(accepted-parity).
  - **m1 admin unknown 고착** → lazy `/test` 폴백. **m2 `_STATE` 누수** → `_prune_state`. **m3 stop in-flight** → daemon worker+queue.
- 2차 재게이트 잔여(흡수): `_refresh_targets` provider 예외 로그 errno/타입만(자격증명 verbatim 차단).
- 검증: 신규 `test_conn_health.py` 21 PASS(TCP+DB 2단·B1 회귀·SSRF 차단 4종·gate[monitor-aware]·backoff·foreground 피드백·prune·snapshot 비노출·db 통합 fast-fail/feedback/control-plane) + make test 컨테이너 회귀 0 + ruff clean.
- Risk: medium(런타임 모든 제품 질의 + 관리콘솔 통과 경로 + background daemon + 외부 SYN). 완화 — control-plane 미적용·flag `AGENT_CONN_HEALTH_ENABLED=0` 즉시 비활성·비밀번호 `_targets` 격리·SSRF fail-closed·daemon 종료 비차단. Rollback: env 0 또는 revert.
- Cross-ref: CHG-20260612-0250 / TASK-0250 / STATUS TASK-0250 / feature-0003 REV-20260612-0250. [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260612-0247 [SUBAGENT:ds-connect-isolation-breaker-adversarial] — SHIP-WITH-FIXES(BLOCKER 2 + MAJOR 2 + MINOR 흡수)
- Date: 2026-06-12
- Cycle: TASK-0247 (데이터플레인 연결 격리 — bounded connect timeout + per-datasource circuit breaker, **Major §12.3** 런타임 데이터플레인 경로)
- 패널: outside-voice 적대적 동시성/보안 리뷰 subagent **2-pass**(1차 NOT-SHIP → 발견 전량 흡수 → 2차 재게이트 SHIP-WITH-FIXES). 런타임 가용성 변경(연결 차단 판정)이라 [[feedback_outside_voice_for_rbac]] 정합으로 외부 시각 필수.
- 1차 발견(NOT-SHIP) 및 흡수:
  - **B1 (BLOCKER) half-open thundering herd**: `half_open` 플래그가 write-only 라 가드 역할 부재 → 쿨다운 만료 순간 web 다중스레드가 동시에 trial 통과해 죽은 DS 에 connect 폭주. → `half_open_at`(타임스탬프) 토큰을 `_BREAKER_LOCK` 안에서 검사·세팅해 **정확히 1개** trial 만 통과(나머지 fast-fail). 8스레드 동시성 테스트로 connect 호출 정확히 1회 검증.
  - **B2 (BLOCKER) stuck-open leak**: trial 보유 스레드 사망 시 토큰 영구 잔존 → 건강 DS 영구 차단. → `_breaker_trial_timeout`(connect_timeout×(retries+1)+5) 경과 시 stale 토큰 회수.
  - **M1 (MAJOR) retry 증폭**: `connect_with_retry` 의 내부 retry(×3)가 1요청에 breaker 를 즉시 threshold 까지 밀어 false-open. → breaker 게이트/기록을 **connect_with_retry 경계로 이동, 요청당 1회**. THRESHOLD=실패한 요청 수.
  - **M4 (MAJOR) 분류 오염**: `_should_retry_db_error` 재사용이 1205(deadlock) 등 쿼리시점 에러까지 카운트. → `_is_connect_breaker_failure`(connect-stage 만: 2002/2003/2005/2006/2013+connect 메시지; deadlock·인증 제외).
  - **m1/m2 (MINOR)**: 부기 예외 누수 → `_breaker_safe` 격리. 로그 `err=%r` 노출 → errno/타입만(`err=%s`). m3(MSSQL login_timeout 의 DNS/TCP 한계) 주석 문서화.
- 2차 재게이트 잔여(흡수): half-open trial 이 비-카운트 에러(인증 1045)로 끝나면 토큰 점유로 건강 DS 가 ≤trial_timeout 동안 fast-fail → `_breaker_record_failure` 가 비-연결 실패 시 `half_open_at` 즉시 해제(다음 요청=새 trial). 회귀 테스트 추가.
- 검증: 신규 `test_db_circuit_breaker.py` 22 PASS(timeout 분리·M1 요청당1회·8스레드 단일 trial 동시성·deadlock/인증 미카운트·stale 회수·per-key 격리·half-open 복구/재개방/토큰해제·control-plane 미적용·부기예외 비삼킴·no-retry·bounded timeout) + make test 컨테이너 전체 회귀 0 + ruff clean.
- Risk: medium(런타임 모든 제품 질의 통과 경로). 완화 — control-plane(memory DB) 미적용·flag `AGENT_DB_BREAKER_ENABLED` 로 즉시 비활성 가능·breaker open 은 connect-stage 실패만·bounded timeout 으로 in-flight 손상 상한. Rollback: `AGENT_DB_BREAKER_ENABLED=0`(런타임) 또는 파일 revert.
- Cross-ref: CHG-20260612-0247 / TASK-0247 / STATUS TASK-0247. [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260612-0237 [SKIPPED:llm-naming-cleanup-no-behavior-change] — PASS
- 패널 skip 사유: `openai` SDK 전송 클라이언트의 명명 정리(rename + dead env 제거 + env backward-compat). 라우팅/자격증명/보안 경계·동작 무변경. 적대적 패널 비대상(§18.8). 동시세션 선점→§13.1 재번호 0233→0236.
- Date: 2026-06-12
- Cycle: TASK-0237 (OpenAI legacy 명명 정리 — agent-core 측, **Major §12.3** cross-feature)
- 검토 결과: ① `_get_openai_client`→`_get_llm_client` 는 def rename + alias(`= _get_llm_client`)뿐 — `_resolve_tier_endpoint` 분기·캐시·`OpenAI(**kwargs)` 인스턴스화 로직 불변. 호출처 14곳(내부 7 + kb_retrieval + app + 테스트)이 신규명/alias 로 동일 객체 획득. ② env: 심볼명(`OPENAI_MODEL`/`AGENT_OPENAI_MAX_RETRIES`)은 16+2 사용처 보존, env **소스만** 새 이름 우선 → 사용처 코드 무변경. 운영 .env 구이름 fallback 으로 무중단. ③ `OPENAI_API_BASE` 는 read 0(dead) 확인 후 제거 — 부작용 없음. ④ model_catalog 죽은 분기는 `return None` 동작 보존(주석만 정정) — `max_tokens_for_model` 미등록 모델 fallback 유지.
- 검증: test_llm_env_naming.py 6(우선순위/fallback/default/제거) + 앵커 불변식(신·구 tripwire) + agent-core 전체 회귀 0 + alias 정합.
- Risk: low — 동작 무변경, alias·fallback 으로 무중단. Rollback: 파일 revert(alias 덕에 점진 가능).
- Cross-ref: CHG-20260612-0237(agent-core) / feature-0003 REV-20260612-0237 / TASK-0237.

## REV-20260611-0232 [SKIPPED:backend-cap-adjust-no-security-surface] — PASS
- 패널 skip 사유: max_tokens cap 표 task 키 추가 — 라우팅 로직·보안 경계 무변경. 적대적 패널 비대상(§18.8). 동시세션 insight-reset cycle 이 REV-0231 선점→§13.1 재번호 0231→0232. 아래는 backend correctness self-review.
- Date: 2026-06-11
- Cycle: TASK-0232 (제품 프롬프트 자동작성 잘림 해소 — agent-core 측 model_catalog cap 신설, **Major §12.3**)
- 분류: max_tokens cap 표 task 키 추가. 라우팅 로직·보안 경계 무변경. backend correctness self-review.
- 검토 결과: `"prompt_gen"` 신설은 `_CLAUDE_MAX_TOKENS`/`_LOCAL_LLM_MAX_TOKENS` dict 에 키 추가뿐 — `max_tokens_for_model` 의 tier 분기(local/claude/else) 로직 불변. 다른 task cap(insight/agent/summary/sql_fix/validate) 영향 0. Claude 20000 은 thinking budget(≤16000) 차감 후 ≥4000 본문 여유, 로컬 3072 ≤ 4K 컨텍스트. 무제한 아닌 명시 cap 으로 비용 폭주 차단(CHG-0004 정합).
- 검증: 신규 `test_prompt_gen_max_tokens.py` 5 PASS + `test_call_llm_records_agent_task.py` 회귀 0.
- Risk: low. Rollback: prompt_gen 키 삭제 시 default cap(8192) 폴백 — 동작 안전.
- Cross-ref: CHG-20260611-0232 (agent-core) / feature-0003 REV-20260611-0232 / TASK-0232.

## REV-20260611-0230 [SUBAGENT:product-multi-datasource-isolation-adversarial] — PASS(MAJOR 흡수)
- Related TASK: feature-0002-agent-core + feature-0003-agent-web-ui (TASK-0230, **Critical §12.3** — 멀티 datasource 1:N)
- Trigger: datasource 접근 경계(인가 결정) + schema allowlist + 다중 연결 라우팅 → security + backend (§18.8) + [[feedback_outside_voice_for_rbac]] 필수 게이트
- Timestamp: 2026-06-11
- Verdict: **BLOCKER 0** — 핵심 cross-datasource 격리 HOLD. MAJOR 3건 발견 → 전부 흡수. 재심 PASS-able.
- Panel: 적대적 outside-voice senior DB-security subagent(별 컨텍스트). "datasource A 컨텍스트에서 B 의 스키마/데이터 도달 가능?" 반증 시도 — execute_tool activate→handler→restore 시퀀스의 연결↔allowlist 불일치 창, datasource 인자 누락/미바인딩/공백·대소문자 변형, 레거시 행(DatasourceKey='') 폴백 누출, admin authz/IDOR, migration 안전성, 연결 cleanup, 0/1 바인딩 회귀.
- **격리 HOLD(반증 실패=안전)**: execute_tool 이 `label` 단일값으로 `conn_for(label)`+`activate(label)` lockstep → 연결/allowlist/engine 불일치 창 없음. tool 호출 루프는 in-thread 순차(동시 2 datasource 활성 불가). 게이트(`_freeform_sql_access_error`/`_whitelist_violation`)는 항상 활성 datasource 의 allowlist 기준 → B 의 DB 명을 grounding 으로 알아도 A 컨텍스트에서 쿼리하면 차단. `to_thread` context 복사 + ContextVar finally reset + `_ACTIVE_DS_ROUTER` 기본 None → 스레드 재사용 stale 없음. 미바인딩 라벨 명시 거부. 0/1 바인딩 byte-identical(라우터 None, enum 미주입, 원 resolve, 단일 close).
- **MAJOR-1 (흡수)**: `_ensure_web_product_datasources_schema` 가 ALTER/backfill/PK-migration 을 broad `try/except: pass` 로 삼켜, 부분 적용(컬럼 부재 + join ≥2)이 silent. → 컬럼 존재 선확인(information_schema) + 단계별 실패 loud 로깅(error) + 컬럼 부재 시 backfill/PK 이전 skip. atomic DROP+ADD(InnoDB) 유지.
- **MAJOR-2 (흡수, 최고 위험)**: `_datasource_allow_schemas`/`_product_allowed_schemas_for_datasource` 의 차원-컬럼-부재 폴백이 **차원 무필터 전체 DB 목록**을 반환 → ≥2 바인딩에서 모든 datasource 컨텍스트에 한 product 전체 DB broadcast = 교차노출(MAJOR-1 partial migration 과 결합 시 실제 leak). → `_datasource_allow_schemas`(런타임 게이트 입력)를 **fail-closed**([] 반환)로 전환 + 회귀 테스트(`test_datasource_allow_schemas_failclosed_on_missing_column`). app.py 의 동명 함수는 admin **표시용**(게이트 아님)이라 폴백 유지.
- **MAJOR-3 (흡수)**: `_resolve_product_datasources` 예외를 bare `except: []` 로 삼켜 ≥2 제품이 단일경로(넓은 allowlist)로 silent 강등. → 로그 가시화(silent 금지) + 단일경로 자체가 fail-closed(`DatasourceResolutionError`) 라 안전망 유지.
- **검증 SAFE(추가 확인)**: admin add/remove(console.access+console.manage), 미등록 키 거부(400), DELETE datasource 가 join+접근DB 고아 정리, PUT databases 가 요청 datasource_key 바인딩 검증, double-close 없음(router 활성 시 db_conn=primary, else 분기 skip).
- Artifact: (subagent 출력 본문 — agentId a2a454451a8ea4b9b; 4-section verdict + file:line 인용)
- Human Approval Needed: no (보안 trade-off 신규 0 — datasource 격리 강화 방향. Critical 작업이나 사용자 사전 confirm[전체 구현 + LLM tool 선택] 범위 내)
- Cross-ref: CHG-20260611-0230 / TASK-0230 / ADR-CORE-0003 / [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260611-0226 [SUBAGENT:mssql-perdb-coverage-security-adversarial] — CONCERN(BLOCK 흡수)
- Related TASK: feature-0002-agent-core (TASK-0226)
- Trigger: schema/migration/query + 보안경계(broaden DB read access) keyword matched → security + backend (§18.8)
- Timestamp: 2026-06-11
- Verdict: BLOCK 1건 발견 → 수정 후 CONCERN 잔여(전부 수용/문서화). 재심 PASS-able.
- Panel: 적대적 outside-voice security/backend subagent. context bundle(changed_files + insight.py diff + 신규 SQL 전문요지 + TASK/acceptance) 주입(§18.11). MSSQL 권한 확대(db_datareader)·동적 SQL 인젝션·telemetry 오탐·스코프 drift 반증 시도.
- **BLOCK B-1 (수정 완료)**: `bin/datasource-mssql-ro-bootstrap-multidb.sql` 3단계 검증 블록이 `SELECT '<name>'` 로 DB명을 **raw 문자열 연결** — DB명(SYSNAME)에 작은따옴표 가능(`[O'Brien]`)이라 구문 깨짐 + 2차 SQL injection 표면. 식별자엔 QUOTENAME 쓰면서 리터럴엔 안 쓴 비대칭 결함. **수정**: 리터럴 삽입을 `QUOTENAME(t.db_name, '''')`(작은따옴표 이스케이프)로 전환 + 검증 범위를 전체 ONLINE DB → `@target_dbs`(부트스트랩 대상) 한정(대상외 MISSING 노이즈 차단, C-1 스코프 정합 동시 해소). step2↔step3 사이 GO 제거(변수 스코프 유지).
- **CONCERN(수용/반영)**: ① perm_suspect 에러번호(916/229/297) substring 오탐 → 정규식 단어경계 `\b(...)\b` 로 전환(텍스트 토큰은 substring 유지) + 테스트 5 추가(rowcount '2297' false-positive 차단 검증). ② @target_dbs ↔ WebProductDatabases drift(두 독립 진실원천) → SQL 헤더에 동기화 경고 명시(초과=최소권한 위반, 부족=degraded 영구화). ③ db_failed 가 일시 오류까지 포함해 degraded 노이즈 → trade-off 합당(degraded=부분성공 신호, acceptance 가 가시화 요구) 판단으로 수용, perm 분리 카운트는 follow-up. ④ @sys 필터가 distribution/SSISDB/snapshot 미커버 → 운영자 통제 입력이라 차단 아님, follow-up.
- **PASS(반증 실패=안전)**: MySQL 회귀 0(db_failed 는 `_is_mssql_ds` 가드로 0 유지, db_targets 누적도 MSSQL 발견 분기 내 한정 → MySQL `[None]` 경로 미누적), degraded↔backoff 분리 정합(일반 degraded 는 run_insight_worker_loop backoff 미대상 — 정상 tick 유지가 설계 의도), 읽기 전용 유지(db_datawriter DROP hardening), 시스템 DB @sys+ONLINE 필터.
- Artifact: (subagent 출력 본문 — 본 index 에 요지 적재; 4-section verdict 포함)
- Human Approval Needed: no (사용자가 보안 trade-off 사전 승인 — db_datareader DB 단위 확대 명시 수락; Major §12.3 사전승인 범위)
- Cross-ref: CHG-20260611-0226 / TASK-0226 / [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260611-0223 [SUBAGENT:mssql-three-tier-adversarial]
- Date: 2026-06-11
- Cycle: TASK-0223 (MSSQL database-aware 3계층 insight — agent-core 교차변경), **Major §12.3**
- Panel: 적대적 subagent(feature-0003 REV-20260611-0223 와 동일 패널, agent-core 측 기록). config/insight/utils/schema/agent_core 변경에 대해 권한경계·write/read 정합(livelock)·MySQL 회귀·3계층 파싱·스캔비용 반증 시도.
- Verdict: 4 MAJOR 발견 → 전부 수정(상세는 feature-0003 REV-20260611-0223). agent-core 관련 2건: ① read-back 맵 cross-DB 충돌 livelock(`_build_insight_object_maps` `(schema,table)`→`object_key` 키 + 쿼리 `object_key IN` 매칭), ② bootstrap 2계층 누락(schema.py 2곳 `ds_object_suffix` 치환). 반증 실패(안전): MySQL 2계층 byte-identical(`ds_object_suffix` active_database=None), `_infer_rag_object_from_fact` 2계층 무변경, ContextVar 누출 없음(set_active_datasource 가 database 리셋), `_discover_mssql_databases` 파라미터 바인딩+권한밖 격리, fingerprint/refresh 키 정합.
- 검증: pytest 444 passed/2 skipped(신규 13). 라이브 MSSQL 제품 60테이블 grounded.
- Risk: medium — MSSQL multi-DB 신규 경로이나 정합·경계·회귀 검증. RBAC/스키마/시크릿 무변경.
- Cross-ref: CHG-20260611-0223 / TASK-0223 / (feature-0003) REV-20260611-0223.

## REV-20260611-0208 [SUBAGENT:preview-link-falsepositive-adversarial]
- Date: 2026-06-11
- Cycle: TASK-0208 ("전체 N행 미리보기" 오링크 — 비-결과 분석표 false-positive 봉쇄), **Minor §12.3**
- Panel: 적대적 backend/QA subagent — fix 가 (a) 보고된 false-positive 해소 (b) 측정값-전용 폴백(TASK-0174) 회귀 여부 (c) 신규/잔존 false-pos/false-neg 벡터 (d) `used[]`·토큰추출 엣지 집중.
- Verdict: **SHIP-WITH-NITS** (BLOCKER 0, MAJOR 0). 무반박 확인:
  - false-positive 해소 확정: 분석표 19 토큰 vs leftover CSV 0 토큰 → overlap 0 → `not table_tokens` 게이트가 `None` 반환·링크 생략.
  - 측정값-전용 폴백 회귀 0: %/소수 표와 rates CSV 모두 토큰 집합 공집합 → `not table_tokens` 분기 도달·컬럼수 폴백으로 링크 복구(TASK-0174 골든 유지).
  - `used[]` 무영향(매치 시에만 set), 헤더행 제외 일관, readable-empty(`set()`)/unreadable(`None`) CSV 가드 정상(crash 0).
- Findings(MINOR, 전부 수용/범위외):
  - M1 진짜 결과표를 과격 재포맷해 overlap 0(라벨 토큰 잔존)이면 링크 recall 손실 → **수용**(degraded "없는 링크" < broken "클릭 422"), docstring 에 trade-off 명시.
  - M2 `_distinctive_tokens` 토큰추출 맹점(①② 단독·통화·날짜 month/day 2자리 누락) — **pre-existing**, 본 fix 도입 아님. 휴리스틱 매처 장기 꼬리.
  - M3 측정값-전용 표에 동일 컬럼수 CSV 2+ 시 폴백이 첫 미사용 선택(tie-break 없음) — **pre-existing**, shape-as-key 본질 한계.
  - M4 다중표(진짜 결과+분석) used[] carry-over 테스트 부재 권고 → **본 cycle 반영**(`test_collapse_analysis_table_does_not_consume_genuine_csv_slot` 추가).
- Risk: very low — 답변 후처리 링크 매칭 정확도. RBAC/스키마/파괴 0, 순수함수. frontend 값 가드 defense-in-depth 유지.
- 검증: 수정 전 코드에서 신규 테스트 FAIL→수정 후 6/6 PASS, 인접 33 회귀 0.
- Cross-ref: CHG-20260611-0208 / TASK-0208 / TASK-0174(폴백 도입) / feature-0003 app.js 값 가드(#118).

## REV-20260610-0200 [SKIPPED:minor-escaping-implements-REV-0196]
- Date: 2026-06-10
- Cycle: TASK-0200 (convo_search LIKE 메타문자 이스케이프 하드닝), **Minor §12.3**
- Reason: 직전 패널(REV-20260610-0196)이 명시적으로 지적한 MINOR 잔존("convo_search 의 `like_pattern` LIKE 메타문자 미이스케이프, _collect_matched_excerpts 와 parity gap")의 **실행**. 동일 검증된 패턴(escape char 먼저 치환 → `%`/`_` → `ESCAPE '!'`)을 적용했고 RBAC/스키마/결과 shape/case-insensitive(ILIKE) 무변경. 파라미터화는 유지되어 SQLi 표면과 무관(LIKE 와일드카드 의미만 정정). 회귀 테스트 2(메타문자 이스케이프·빈 질의 전체매칭). make test exit=0. escape 순서·ESCAPE 절은 표준이라 추가 패널 불필요.
- Risk: very low — 검색 도구 LIKE 패턴 이스케이프.
- Cross-ref: CHG-20260610-0200 / TASK-0200 / REV-20260610-0196(원 지적) / feature-0003 REV-20260610-0200(#2 정렬).

## REV-20260610-0196 [SUBAGENT:cutover-routing-gaps-adversarial]
- Date: 2026-06-10
- Cycle: TASK-0196 (AR-M5 cutover 잔존 라우팅 누락 — agent-core convo_search), **Minor §12.3**
- Panel: 적대적 backend + QA subagent (web 3건 + convo_search 통합 리뷰, feature-0003 REV-20260610-0196 과 동일 패널).
- Verdict: **SHIP** (MAJOR 0). convo_search 관련 무반박 확인:
  - PG `kv.key`/`kv.value` 비예약어 → unquoted 정상(스키마 일치). MySQL 분기 backtick / PG 분기 무backtick 각각 정확.
  - 3 PG SELECT 의 컬럼순서가 `_format_row`(conv_id,role,content,created_at,source)와 정확 일치(summary: `'summary' AS role, summary AS content, updated_at AS created_at`; kv: `'topic' AS role, value AS content, updated_at AS created_at`).
  - 모든 PG 술어 `ILIKE`(case-insensitive 패리티), `include_current` 필터 동일, `from .db import _pg_connect` 존재(modules 패키지 동일).
- Findings(MINOR, pre-existing·범위 외): `like_pattern = f"%{pattern}%"` LIKE 메타문자(`%`/`_`) 미이스케이프 — MySQL·PG 분기 동일 패리티, cutover-routing 범위 외 추후 hardening 후보.
- Risk: low — 읽기 라우팅, RBAC/스키마/파괴 0. make test exit=0.
- Cross-ref: CHG-20260610-0196 / TASK-0196 / feature-0003 REV-20260610-0196.

## REV-20260610-0193 [SUBAGENT:p5-dialect-golden-regression]
- Date: 2026-06-10 (TASK-0193)
- Cycle: 멀티 datasource Stage 2 P5 (Dialect 어댑터 — tools.py introspection/sample SQL 의 MySQL/MSSQL 추상화). **Major §12.3**.
- Panel: 적대적 subagent — MySQL 골든 회귀 + run-wide ContextVar 가 P3 grounding 격리/엔진 지속을 깨는지 집중.
- Verdict: **SHIP-able, BLOCKER 0, MAJOR 1(흡수)**. **MySQL 골든 회귀 byte-identical 검증**(MySQLDialect 8 메서드가 기존 inline SQL 그대로, `explain()`=`EXPLAIN {sql}` 동일, `_estimate_explain_rows` MySQL 동작 0 변경). **MSSQL 컬럼순서 정합**(describe_columns 7컬럼·list_indexes row[1/2/3/4/6]·Non_unique is_unique 반전). **P3 grounding 격리 유지**(set 이 _build_knowledge_context 전, ds_fact_like/un-scoped MySQL fallback 가드 유효). **엔진 tool 루프 지속 OK**(run-wide set, grounding 후 미해제).
- 흡수: **MAJOR M1** datasource ContextVar 해제가 _run_agent_core 평문(예외 시 누락→ask-worker 스레드 재사용 stale, 주석은 finally 거짓) → **run_agent 의 finally(allowlist 해제와 동일 위치)로 이동**(예외 안전) + 주석 정정 + 회귀 테스트(예외 시 해제 단언).
- MINOR(이월): m3 `_SYSTEM_SCHEMAS`/`_is_user_schema` 가 MySQL 방언(sys/INFORMATION_SCHEMA/guest/db_* 미필터) → **P6** dialect-aware 시스템 스키마 필터. (P5 범위 외, MSSQL shadow-only)
- Resolution: M1 흡수 후 make test 318 passed/회귀 0. **보안 게이트(allowlist/sql_guard)는 아직 MySQL 방언 — P6 전 MSSQL datasource 활성화 금지(dialects.py·_estimate_explain_rows 주석 명시).** flag OFF shadow.

## REV-20260610-0192 [SKIPPED:driver-infra-security-deferred-p6]
- Date: 2026-06-10 (TASK-0192)
- Cycle: 멀티 datasource Stage 2 P4 (MSSQL 드라이버 pymssql + 연결 디스패치 + 크로스엔진 결과 수집). **Major §12.3**.
- Reason: P4 는 **드라이버 인프라만** — 신규 authz/SQL 생성/권한 카탈로그 표면 0. MSSQL datasource 접근 인가는 기존 product.access(P1, REV-0187 검토필)가 그대로 담당. MSSQL **보안경계(T-SQL allowlist·GRANT·denylist)는 P6** 에서 구현·리뷰되고, Stage 2 전체 RBAC outside-voice 적대적 재게이트는 **P7**(ADR-CORE-0003). 본 cycle 의 유일 회귀 위험인 `_collect_cursor_result` 의 `with_rows`→`description` 전환(라이브 MySQL 경로)은 **make test MySQL 골든 회귀로 검증**(312 passed, mysql.connector 는 SELECT 후 description set·비-row None 이라 등가). pymssql-2.3.13 컨테이너 설치 확인. 드라이버는 flag OFF 라 shadow.
- 잔여 보안 게이트: P6(MSSQL allowlist 무자격/catalog·전용 role GRANT·T-SQL denylist·AST 재직렬화·부하게이트), P7(Stage 2 종합 RBAC outside-voice).

## REV-20260610-0191 [SUBAGENT:p3-insight-livelock-security]
- Date: 2026-06-10 (TASK-0191)
- Cycle: 멀티 datasource P3 (insight_worker per-datasource: fact 키 datasource 스코프 + grounding 격리 + worker 순회). **Major §12.3** — livelock 민감.
- Panel: 적대적 subagent — livelock(write↔read-back↔grounding 키 3자 정합) + 보안(Codex-3 datasource 교차노출) + flag-OFF 회귀 집중.
- Verdict: **SHIP-ABLE, BLOCKER 0, MAJOR 1(흡수)**. **livelock PASS**: write 와 read-back 이 *동일 local 변수*(insight.py table_key)를 재사용 → ContextVar 타이밍과 무관하게 구조적 정합, fingerprint broad-prefix 로드 + exact-key 조회 안전. **보안 PASS**(PG 경로): grounding `set_active_datasource(_ds)` 가 유일 `_build_knowledge_context` 호출 직전·finally 해제, `ds:` 구분자 누출 없음(`table_insight:ds.users` 콜론-닷 비매치). **flag OFF PASS**: ds_targets=[(None,None)]·무접두·legacy 데이터 호환. **worker PASS**: ds=None 실패 raise·datasource 격리·_ds_conn close 가드·KNOWN_SCHEMAS 기본만 변이.
- 흡수: **MAJOR** scan_report 가 마지막 datasource 만 반영(telemetry 과소보고, 과거 livelock 잡은 관측성 약화) → int 누적+bool OR 로 수정. **M2** MySQL grounding fallback un-scoped(현재 dead path 라 unreachable 이나 잠재 Codex-3 누출) → datasource 활성 시 fallback 차단 가드.
- MINOR(이월): kb_retrieval.py `_load_existing_*` 무조건 MySQL 조회(no PG 분기)로 force_scan 매 tick — **기존 main 결함**(P3 무관, ds 수만큼 fingerprint 재계산 비용 증가) → TODO. 진짜 재생성 게이트(ds-스코프 fingerprint + PG artifact-complete)는 무한 재생성 막음.
- Resolution: MAJOR/M2 흡수 후 make test 307 passed/회귀 0. 핵심 무누출 테스트(`test_ds_grounding_like_no_cross_datasource_leak`) 포함. [[project_insight_livelock_readback_mismatch]]·[[feedback_outside_voice_for_rbac]] 정합.

## REV-20260610-0190 [SUBAGENT:p2-datasource-ui-security]
- Date: 2026-06-10 (TASK-0190)
- Cycle: 멀티 datasource P2 (multi-MySQL Web UI: 관리자 바인딩 UI + 연결테스트 + 대화 라벨). **Major §12.3**.
- Panel: focused 보안 subagent — P2 신규 백엔드 표면(probe 엔드포인트·`_list_products` datasource_key 노출)만 적대적 검토.
- Verdict: **PASS-WITH-NITS, BLOCKER 0 / MAJOR 0**. SSRF 구조적 차단(좌표를 request body 아닌 서버측 `config.DATASOURCES` 키 lookup 으로만 해석 — 사용자 host 주입 불가), authz 정상(probe=console.access, use-after-close 없음), 정보유출 없음(probe 실패 errno 만, host/user/pw 비유출).
- MINOR(수용): ① `datasource_key`(키 이름)가 /api/session·/api/auth/me 로 비-admin 채팅 사용자에 노출 — 단 키 이름은 비밀 아님이고 **대화 datasource 배지 기능상 의도된 노출**(좌표/비밀번호 X). ② probe rate-limit 부재 — admin 한정·단발 진단·timeout 8s 라 실위협 낮음.
- Resolution: 수정 불요(MINOR 는 by-design/저위험). make test 302 passed/회귀 0. [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260610-0187 [SUBAGENT:p1-security-boundary]
- Date: 2026-06-10 (TASK-0187)
- Cycle: 멀티 datasource P1 구현 (multi-MySQL 레지스트리 + 연결 디스패치 + 보안경계). **Critical §12.3** — 데이터 접근 경계·자격증명·RBAC.
- Panel: RBAC outside-voice 적대적 보안 리뷰. **Codex 시도 → `/tmp` sandbox 오류("No usable temporary directory")로 실패 → gstack 정책대로 Claude 적대적 subagent fallback**(별 컨텍스트, 보안 엔지니어). diff + db.py/config.py/agent_core.py/app.py + RBAC enforce 경로(`_account_has_product_access`) 추적.
- Verdict: **NEEDS-TWEAK, BLOCKER 0** — 핵심 보안 모델(product RBAC=datasource 게이트 연결 전 enforce, 자격증명 .env 전용 비저장, flag OFF=0변경, admin authz/injection) 코드에서 성립 확인. MAJOR 2 + MINOR 3 출시 전 수정.
- Findings·흡수: **M-1** datasource `default_db` 가 product allowlist 우회(미접두 쿼리 `SELECT * FROM t` → schema-ref 0 → 통과 → default_db 조회) → **FIX: db.connect datasource 경로가 default_db 를 암묵 기본 스키마로 적용 안 함(database=None 강제), allowlist 가 유일 게이트, schema-prefixed 쿼리만**. **M-2** 명시 바인딩 product 의 키 미등록/해석실패 시 운영 DB 로 fail-open → **FIX: 미등록 키는 `DatasourceResolutionError` raise(fail-closed, run 중단), 읽기실패만 None(기본 DB)**. **N-2** `DS_<KEY>_USER` 미설정 시 root 폴백 → **FIX: USER 필수(미설정 키 등록 제외)**. N-3(default_db BLOCKED_DEFAULT_SCHEMAS 미필터)=M-1 근인, FIX 에 포함. **N-1**(연결 실패 raw 예외에 host/port 노출, password 無) = **기존 단일-DB 경로와 동일한 pre-existing 패턴(P1 회귀 아님)** → 사용자향 메시지 일반화는 follow-up.
- 검증된 강점: RBAC 가 stored product_id(user 직접입력 아님, 3 write 경로 모두 게이트)로 run_agent 전 enforce + auto 모드 product_id=None→datasource 미해석+allowlist `[]`(fail-closed) / worker payload 에 좌표 무·product_id 만(재해석) / 자격증명 DB·payload·_pool_key·admin응답·로그 어디에도 비유출 / `_INTERNAL_SCHEMAS`(agent_memory) 차단 host 무관 유효.
- Resolution: M-1/M-2/N-2 흡수 후 make test 회귀 0(신규 test 갱신 — database 미적용·fail-closed raise·USER 필수 단언). 코드 mutation: config.py/db.py/agent_core.py. [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260610-0185 [SKIPPED:decision-recording-design-only]
- Date: 2026-06-10 (TASK-0185)
- Cycle: 멀티 datasource 롤아웃 시퀀싱 결정 기록 (DESIGN §4 Q6/Q7/Q8 → ADR-CORE-0003, §5 재구성)
- Reason: 사용자 결정(2026-06-10) 3건을 설계 문서에 못박는 design-only 변경. 코드/RBAC/스키마/시크릿/엔드포인트 mutation 0. 결정 자체는 직전 REV-20260610-0183(plan-eng-review + Codex cross-model)의 발견·권고로 이미 outside-voice 검토를 거쳤고, 본 cycle 은 그 결과를 사용자가 선택해 기록하는 것뿐. 신규 outside-voice 불필요 조건 충족.
- Decision recorded: multi-MySQL 먼저(Q6/Q8, Stage 1) + 보안경계 연결과 동시(Q7) — ADR-CORE-0003. 구현 Stage 2(MSSQL) 진입 시 RBAC outside-voice 재게이트 명시.

## REV-20260610-0183 [CODEX:design-eng-review-crossmodel]
- Date: 2026-06-10 (TASK-0183)
- Cycle: 멀티 datasource 설계 2차 검토 — `/plan-eng-review`(엔지니어링 매니저) + Codex cross-model outside voice. design-only.
- Panel: (a) Claude 엔지니어링 매니저 4섹션 리뷰(Architecture/Quality/Tests/Performance). (b) **Codex** (`codex exec`, model_reasoning_effort=high, read-only) cross-model — 1차(REV-0182 Claude subagent)·본 설계가 놓친 것 발굴.
- Verdict: Codex **REJECT** (BLOCKER 4 + MAJOR 5) + Claude eng (Arch 3/Quality 2/Perf 3). design-only 이라 전 발견 설계 직접 반영.
- Findings(신규, REV-0182 미포착): **Codex-1** AST 추출도 불완전(무자격 이름·view/synonym·ownership chaining → `datasource_id+catalog+schema+object`). **Codex-2** `db_datareader` 가 allowlist 와 양립불가(DB 전체 읽기) → 전용 role+허용 view 만 GRANT SELECT. **Codex-3** insight 격리가 fingerprint 키에만 — fact 스코프(`schema_insight`/`FACT_SCOPE_COMMON`) 교차노출. **Codex-4** rollout 이 보안경계 뒤늦음(P1~P4 datasource_id 무검증 연결권한). Codex-5 parser-differential(AST 재직렬화 실행). **Codex-6** confirm_heavy LLM 자기우회 + fetchall 무제한. Codex-7 MSSQL 세션상태 pool 누출. Codex-8 "제어평면 untouched" 거짓. Codex-9 scope 과대. Claude eng: 단일 canonical AST 공유(A2/C1)·pool cap(PF1)·insight stagger(PF2).
- Resolution (DESIGN-FOLD): §4 db_datareader 정정(전용 role GRANT), §3.4 축1 무자격/catalog 보강 + 축3 AST 재직렬화, §3.6 fact 스코프, §3.3 confirm_heavy/fetchall, §3.2 session reset/poison discard, §1 scope 정직성, §4 Q6/Q7/Q8(시퀀싱·보안우선·scope) open question, §10 신설 + GSTACK REVIEW REPORT.
- Cross-model 합의: scope 축소/MySQL-first(Codex-9↔Claude Step0), insight 교차노출(Codex-3↔M-2), pool 세션상태(Codex-7↔M-1). Codex 가 db_datareader 오류·보안경계 시퀀싱을 추가 포착.
- Risk: low (design-only, 구현 0). 구현 cycle 진입 전 §4 Q6·Q7·Q8 확정 + RBAC outside-voice 재게이트. [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260610-0182 [SUBAGENT:design-adversarial]
- Date: 2026-06-10 (TASK-0182)
- Cycle: 멀티 datasource(MySQL·MSSQL) 데이터평면 설계 (`DESIGN-multi-datasource.md`, design-only)
- Panel: skeptical 시니어 DB/보안 엔지니어 적대적 설계 리뷰(general-purpose subagent, 별 컨텍스트). 설계문서 + 근거코드(db.py/config.py/tools.py/sql_guard.py/insight.py/docker-compose.yml) 전수 검증.
- Verdict: **NEEDS-TWEAK** — BLOCKER 3 + MAJOR 4 + MISSING 6. 중심 전제("보안 게이트 재작성 불필요, sqlglot dialect 주입만으로 멀티엔진 가드")가 코드 현실에서 거짓임을 규명.
- Findings: **B-1** 진짜 테넌트 격리 게이트가 sql_guard 아닌 tools.py `_extract_sql_schema_refs` **정규식** — MSSQL 식별자(대괄호/3-part/ANSI 큰따옴표)에서 통째 우회(`agent_memory` 차단까지). **B-2** 차단 스키마 1차 방어가 실은 MySQL RO GRANT(에이전트 경로는 메타-스키마 의도적 허용) — MSSQL 등가 GRANT/DENY 미설계. **B-3** sqlglot tsql 견고성 미검증 + T-SQL 위험구문(xp_cmdshell/OPENROWSET/WAITFOR/SELECT INTO) 커버 0 + "AST shape 무변경" 거짓(SELECT INTO=부수효과). **M-1** execute_sql/_collect_cursor_result 가 mysql.connector 고유 API. **M-2** insight fingerprint/CSV 키 datasource 무차원→livelock 재발. **M-3** connect(datasource_id=None)=하위호환 이 `database` 문자열 라우팅과 충돌. **M-4** EXPLAIN 게이트 fail-OPEN→MSSQL 항상 통과.
- Resolution (DESIGN-FOLD, design-only 이라 코드 mutation 0): 전 발견을 `DESIGN-multi-datasource.md` 에 직접 반영 — §2.3.1 보안 3축 신설, §3.4 보안게이트 멀티방언 전면 재작성(정규식→AST 교체·T-SQL denylist 매트릭스·shape dialect 분기·sqlglot pin), §4 MSSQL GRANT/DENY 부트스트랩 산출물화, §3.2 plane+datasource_id 명시 라우팅+커서 dialect화, §3.3 fail-closed 전환, §3.6 datasource_id 키 하드요구 승격, §5 P0(드라이버/Dockerfile) 신설, §9 리뷰 반영표+잔여 MISSING. BLOCKER 3 = 설계 수준 해소.
- Risk: low (design-only, 구현 0). 구현 cycle 진입 시 §9 를 합격선 + 재리뷰(plan-eng-review + RBAC outside-voice) 게이트로 사용. [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260610-0178 [SKIPPED:display-metadata-live-canary-verified]
- Date: 2026-06-10 (TASK-0178)
- Cycle: 단계 근거를 tool 인자(reason/work)로 전환 — TASK-0177 의 전달 메커니즘 수정. **Major §12.3**(모든 답변 영향 — 프롬프트/tool 스키마).
- 사유: 변경 본질은 표시 메타데이터(work/reason) 의 **전달 경로**를 content(Bedrock strip) → tool 인자(안정)로 바꾼 것. 쿼리 실행/결과/answer/RBAC/스키마/회계 무변경, 핸들러는 named-get 이라 추가 인자 무해(테스트 단언). 개념적 위험(누수·과호출·순서)은 직전 cycle outside-voice(REV-20260610-0177)가 이미 적대적 검토했고, 그 리뷰가 명시 요구한 검증(M2: `reason_source='llm'` 라이브 실측)을 **머지 전 probe 카나리아로 충족**: 2 ask(다단계) 5 step 전부 `reason_source='llm'`·`work_source='llm'`, 근거가 질문 맥락 직결, 최종답변 JSON 누수 0, 답변 정확. 정적 재리뷰보다 강한 실증.
- 잔존 관찰(0177 M3): narration 이 over-calling 유발하는지 — probe 5 step 은 정상 범위(search→describe→execute 자연 순서), 답변 정확. 운영 모니터 지속.
- 게이트: make test 282 passed/2 skipped(신규 4, 회귀 0). Verdict: SAFE TO SHIP (라이브 카나리아 검증).

## REV-20260610-0177 [SUBAGENT: general-purpose 적대적 리뷰 — base SYSTEM_PROMPT tool_notes 변경, NEEDS-TWEAK→FIXED, BLOCKER 1 흡수]
- Date: 2026-06-10 (TASK-0177)
- 대상: base SYSTEM_PROMPT 에 tool_notes(work/reason) 방출 지시 추가. **Major §12.3** — 모든 사용자 답변에 영향(고-레버리지 프롬프트).
- 판정: NEEDS-TWEAK → FIXED. BLOCKER 1 + MAJOR 3 + MINOR 3 + NIT 2.
- **BLOCKER B1 (흡수·수정)**: 최종 답변 경로(agent_core.py 2207-2231)에 tool_notes/JSON envelope 를 벗기는 코드가 0 — 프롬프트의 "최종답변 JSON 금지"는 통계적 억제일 뿐 fail-closed 아님. 모델이 최종답변에 envelope 흘리면 사용자에게 raw JSON 노출(이 repo 의 TASK-0154/0155 모델산출물 형식깨짐 전례와 동형). **수정**: `_strip_leaked_tool_notes` 결정적 sanitizer 신규 + 최종답변 경로 배선(산문만 남김, 통째 envelope→빈문자열→기존 재요청 루프). 단위테스트 4.
- **MAJOR M1 (프롬프트 반영)**: `tool_calls[:3]` 절단(2270)과 위치-인덱스 매칭(2311)이 어긋나면 잘못된 reason 이 잘못된 step 에 귀속. 프롬프트에 "i번째 note ↔ i번째 tool call(병렬 호출 포함)" 명시. (args-기반 sanity-check 은 기존 동작 범위라 이월.)
- **MAJOR M2 (카나리아 위임)**: Bedrock 의 OpenAI 호환 레이어가 tool_use 동반 턴의 text content 를 빈값으로 정규화하면 tool_notes 미수신 → 전부 derived → 변경 효과 0 인데 조용히 통과("코드는 맞는데 모델이 그 경로를 안 탄다" = 이 repo 반복 실패모드, RC1/livelock 동형). **배포 카나리아에서 `reason_source='llm'` 비율 실측 필수** — 낮으면 토큰만 쓰고 목표미달.
- **MAJOR M3 (관찰 위임)**: narration 보상이 over-calling 유발 또는 reason 작문이 정확성 예산 잠식 위험(가설). 3-step 캡으로 부분 방어. 카나리아에서 step_count/환각 관찰.
- **MINOR**: m1 한국어 값 따옴표 escape(깨지면 derived fallback=무해) → 프롬프트에 escape/작은따옴표 권고 추가. m2 "final answer"→"tool call 없는 모든 턴(반문 포함)"으로 명확화. m3 길이캡 단위 불일치(무해).
- **NIT**: 토큰/지연 negligible(턴당 ~50-150토큰, 3-step 캡). 영/한 혼합 표준 패턴.
- 게이트: make test 278 passed/2 skipped(신규 9, 회귀 0). Verdict: **SAFE TO SHIP (B1 수정 후)** — 단 M2 카나리아 실측이 효과 확인의 진짜 게이트.

## REV-20260609-0175 [SKIPPED:display-metadata-no-rbac-no-schema-no-behavior-change]
- Date: 2026-06-09
- Cycle: TASK-0175 (실행 단계 reason derived fallback), **Minor §12.3**
- 사유: 변경은 순수 함수 `_derive_step_reason`(tool명→한국어 근거 문자열) 신규 + 루프 2줄 배선(`reason_text` 가 빈 경우에만 파생, **LLM 참값 비덮어쓰기**). step **표시 메타데이터**만 채울 뿐 쿼리 실행/결과/answer/RBAC/스키마/엔드포인트/프롬프트/회계 무변경 — agent 동작 위험면 0. `_derive_step_work`(이미 라이브 운영 중인 동형 derived 패턴)의 대칭 추가라 신규 설계 표면 없음. make test 269 passed/2 skipped(신규 4, 회귀 0). 시각 검증=라이브 ask 후 step 사이드 패널 reason 노출 확인(Windows-browser PB-0008 권장).

## REV-20260609-0172 [SUBAGENT: general-purpose 적대적 리뷰 ×2 — 무거운쿼리 자가규제, 설계 RECONSIDER + diff FIX-BEFORE-ENABLING-GATE]
- Date: 2026-06-09 (TASK-0172, **Major §12.3** — agent-core query path). feedback_outside_voice_for_rbac 정책(LLM-SQL 신뢰경계 인접).
- **1차(설계, self-interrupt 안)**: **RECONSIDER-APPROACH** — ① "LLM 판단만(가드레일 없음)" 은 내부 모순(비동기 쿼리 중 *언제 LLM 에 물을지* 는 비-LLM 휴리스틱 필수 = 사실상 가드레일; 순수형은 쿼리당 ~180 LLM 호출) ② 단일 `db_conn` 공유 → KILL 후 후속 step `Commands out of sync` ③ LLM 자발 중단 의존 → 인시던트 미해결 가능 ④ `agent_ro` 는 processlist 부하신호 관측 불가(PROCESS 권한). 더 간단·직접적 대안(EXPLAIN 사전게이팅 / per-query cap / replica 라우팅) 권고. → **사용자 결정: EXPLAIN 게이팅+cap 으로 전환**, self-interrupt 보류(DESIGN §10).
- **2차(전환안 구현 diff)**: **FIX-BEFORE-ENABLING-GATE**(off-default 머지 안전, sql_guard 무변경). 흡수: M1 `confirm_heavy` 문자열 "false" truthy 우회 → robust 파싱 / M2 `MAX_EXECUTION_TIME` session-scoped sticky → docstring 정정 / m3 rows 곱이 `filtered` 무시 false-positive → `rows×filtered/100` 반영 / m4 미지원 mode → off clamp. m5(EXPLAIN fail-open) 수용. 회귀테스트 15(문자열-false 우회 방지·filtered 반영 포함).
- Verdict: **SAFE-TO-MERGE (flag off 기본)** — gate 활성화 전 위 fix 완료. make test 회귀 0.

## REV-20260609-0168 [SUBAGENT: general-purpose 적대적 리뷰 ×2 — ask-worker 큐/실행/fencing, NEEDS-FIXES→FIXED, BLOCKER 3 + MAJOR 4 흡수]
- Date: 2026-06-09 (TASK-0169). 정본 리뷰 기록은 feature-0003 REV-20260609-0168 (양면 작업). 본 항목은 feature-0002 측 cross-reference.
- agent-core 측 핵심 검증·수정: B2 단일문 atomic claim(autocommit 안전) / B3 lease fencing + 시간기반 heartbeat 스레드(긴 LLM step false-positive requeue 차단) / M4 set_run_status 순서 / MJ-2 `_clear_cancel_request` run_id-scoped(fencing cancel 보존) / MJ-1 reaper 활성 job 첨부 제외 / config stale 동적 산출(AGENT_TIMEOUT_SEC=300→run_timeout 900 환경 false-positive 수정, 테스트가 포착).
- 회귀 테스트: test_ask_jobs / test_ask_worker / test_clear_cancel_runid. make test 244 pass·회귀 0.

## REV-20260609-0163 [SUBAGENT: general-purpose 적대적 diff 리뷰 — LLM 사용량 회계, NEEDS-TWEAK→PASS, BLOCKER 1 흡수]
- Date: 2026-06-09
- Cycle: TASK-0163 (REQ-20260609-0163, **Major §12.3** — LLM 사용량 회계 복구: 메인 추론 계측 + resolved_model + 계정별/역할별)
- Reviewer: general-purpose subagent (적대적 backend diff 리뷰 — llm.py `_record_llm_usage` / agent_core `_call_llm`+`run_agent` / app.py `admin_llm_usage`+`_aggregate_usage_by_role` / alembic 0002 / schema parity / 프론트). §18.8 trigger: schema/migration + 메인 LLM 경로 = backend 면.
- Verdict: **NEEDS-TWEAK → (B1 보정 후) PASS**. **BLOCKER 1 흡수.**
- **BLOCKER B1 (흡수 완료)**: 토큰 귀속의 전제가 동시성 하에서 불안전. `cfg.MEMORY_CONVERSATION_ID`/`CURRENT_RUN_ID` 는 contextvar 가 아닌 module global 인데, `/api/ask` 는 agent 를 subprocess 가 아니라 **in-process(`asyncio.to_thread`)로 실행**([[TASK-0159]], `_run_agent` subprocess helper 는 호출자 0 = 죽은 코드). `WEB_PARALLEL_LIMIT=6` per-account 동시 ask 시 thread A 의 cid 를 thread B 가 덮어써 A 의 토큰이 B 의 계정/역할로 오귀속 → 본 cycle 의 RC3(정확한 계정별/역할별) 목표 자체를 깨뜨림. 게다가 본 변경이 메인 추론(최대 토큰 소비)을 처음으로 이 racy 경로로 끌어들여 노출 확대. (Plan subagent 가 "subprocess per ask" 라 단언했으나 실제는 in-process — 외부 시각이 정정.) **조치**: `_record_llm_usage`/`_call_llm` 에 `conversation_id`/`run_id` optional 인자 추가 → 메인 추론은 `run_agent` 의 정확한 cid/run_id 를 명시 인자로 전달(thread 격리·race-free), 초안의 `cfg.MEMORY_CONVERSATION_ID=cid` 직접 set 은 race window 확대라 제거. helper(classify/topic 소량)는 미전달=cfg fallback 유지(기존 동작·회귀 아님). 회귀 테스트 2 추가(명시 인자 우선 / cfg fallback). **잔여(follow-up)**: helper 의 cfg 전역 race 는 기존 동작이며 contextvar 전면 전환(TASK-0137 attachment 패턴)은 별도 cycle.
- SHOULD-FIX S1 (문서화): 마이그레이션 선행 의존 — `_record_llm_usage` 의 bare except 가 "컬럼 없음" 을 삼켜 코드가 컬럼보다 먼저 배포되면 RC1 이 silent 0행. → 배포 순서 "make migrate 선행 후 web/insight 재배포" 강제(STATUS/REPORT/plan 명시).
- VERIFIED-CLEAR: INSERT 튜플 순서 정확(테스트 고정) / down_revision="0001_baseline" 정합·멱등 / cross-DB enrich 파라미터화(인젝션 0) / `_aggregate_usage_by_role` 폴딩 정확(중복계산 0, 시스템 버킷 정합) / 권한 `console.usage.read` 무변경 / 프론트 `esc()` XSS 안전 / MySQL conn 재사용·커서 close·enrich 실패 graceful / by_model ORDER BY 4·LIMIT 50 정합.
- 결론: B1 흡수 + 배포 순서 강제 후 deploy 안전. make test 215 passed/5 skipped(신규 9).

## REV-20260608-0160 [SUBAGENT: general-purpose 적대적 diff 리뷰 — _normalize_history_rows, APPROVE-WITH-NITS, BLOCKER 0]
- Date: 2026-06-08
- Cycle: TASK-0160 (REQ-20260608-0160, **Major §12.3** — 중단 run 고아 tool_use → LLM payload 400 방지)
- Reviewer: general-purpose subagent (적대적 backend 리뷰 — `_normalize_history_rows` + `_assemble_core_messages`/`_format_core_messages` 호출부 + 신규 테스트). §18.8 trigger: LLM payload/response shape = backend 면.
- Verdict: **APPROVE-WITH-NITS**. **BLOCKER 0**. (6 요청 케이스 + ~15 적대적 시나리오 직접 추적, 관련 테스트 47개 PASS.)
- VERIFIED-CORRECT: (1) 모든 케이스(고아 mid/EOF, 부분 멀티툴, 유효 멀티툴, 고아 tool 행, 빈 tool_calls, 재정렬/중복 tool, asst-tool_calls 연속)에서 commit 된 assistant tool_use id 가 직후 tool 로 전부 해소되고 고아 tool 행 미생존. (2) `_parsed_tool_calls` 마커 보존(1021-1022 → `_format_core_messages` 1134-1138 소비), 유효 인접 턴 오삭제 없음. (3) commit 순서 = 원본 순서(assistant 먼저, tool 도착순). (4) 윈도잉(`normalized[-max:]` 후 재정규화)은 경계 절단 고아를 drop 하는 안전망 — dangling tool_use 생성 불가(tool 은 항상 assistant 뒤). (5) 비-tool 평문 대화 byte-identical(회귀 0). (6) asst(tc)→asst(tc) 연속 시 두 번째가 `_flush` 트리거해 첫 미완 턴 drop(정확).
- Nits (Low): (a) **id 없는 tool_calls** 가 가드를 빠져나가 commit 될 수 있음(라이브 트리거 아님 — Anthropic 이 항상 toolu_* 부여 + save 경로 동일 id, **회귀 아님** — 구코드도 동일 맹점) → **반영함**: usable id 0개면 매칭 불가 sentinel 로 강제 drop + 회귀 테스트 `test_drops_idless_tool_calls_turn` 추가. (b) assistant-with-tool_calls 의 content(tool_notes) 가 formatted payload 에서 누락 — **기존 동작, 본 diff 무관**, display-only 메타라 payload 유효성 무영향(오해 방지용 명시).
- 결론: deploy 안전. 테스트 7 passed (하드닝 포함).

## REV-20260605-0151 [SUBAGENT: general-purpose 적대적 diff 리뷰 — Verdict NEEDS-TWEAK→ACCEPTED, BLOCKER 0]
- Date: 2026-06-05
- Cycle: TASK-0151 (DB 조회 사용자 경험 개선 — grounding PG 전환 + prompt 개편 + 멀티턴 보존 + 첨부 cap), **Major §12.3**
- Reviewer: general-purpose subagent (적대적 diff 리뷰 — agent_core.py / domain.py / app.py 전체 diff + 호출 컨텍스트)
- Verdict: NEEDS-TWEAK → (S1 보정 후) ACCEPTED. **BLOCKER 0**.
- Findings:
  - BLOCKER 0 — 인젝션(파라미터화 confirmed) / PG scope·cid 정합(write path 와 `__global__`+`common` 일치) / `pg_used` 빈결과 fallback 오작동 없음 / `with_text=False` NULL 분기 / IDOR 스코프 유지 / DESC+reverse 최신보존 / 멀티턴 orphan tool 재정규화 제거 전부 confirmed-clear.
  - **SHOULD-FIX [S1] (수정 완료)**: `domain._is_low_information_request` 의 `meaningful 길이 ≤3` 컷오프가 짧은 한국어 실질 질문('매출?','회원수','DAU','상품?')을 저정보로 오판 → origin 설정이 보류되어 본 cycle 의 목표(맥락 유실 해소)와 상충. **조치**: 길이 컷오프 제거 → "의미 토큰 부재(자모/문장부호/이모지)" 만 저정보로 판정 + 데이터 신호 명사셋 확장(매출/회원/주문/가입/결제/유저/사용자/상품/방문/접속/수익). 단일토큰 회귀 테스트 2건 추가(`test_low_info_request_short_korean_substantive_not_low_info` / `..._meaningless_tokens_are_low_info`). 라이브 확인: '매출?'/'회원수'/'DAU'→substantive, 'ㅇㅇ'/'...'→low-info.
  - NICE (수용/track): [N1] +8 user 보존의 prompt 예산 순증(bounded, 모니터링), [N2] window 말미 dangling assistant tool_calls(pre-existing), [N3] `_load_relevant_table_insights` 영어 전용 토크나이저(pre-existing — schema-list 한국어 설명이 보완).
- Resolution: BLOCKER 0 + S1 머지 전 반영 완료. 잔여 NICE 는 회귀 아님(pre-existing) — 별도 track.

## REV-20260604-0147 [SKIPPED:read 경로 방어 가드 — RBAC/schema/secret 무변경, REV-0145 패턴 연장]
- Date: 2026-06-04
- Cycle: TASK-0147 (insight worker degraded read-back backoff), **Major §12.3**
- Verdict: PASS
- Reason: PG 부재 시 insight 생성을 멈추고 backoff 하는 방어 가드 추가뿐. write 경로·RBAC·schema·secret·endpoint 무변경. `_pg_connect_ro()` 사용(least-priv) + 모든 경로 conn close(finally). MySQL 모드면 가드가 항상 False 라 기존 동작 무영향. 신규 단위테스트 4건 + 라이브 functional 로 분기 검증. REV-20260604-0145(외부 subagent 리뷰) 가 검증한 "cutover read-back 정본=PG" 인식의 robustness 연장이라 별도 outside-voice 불요.
- Note: backoff(기본 300s)는 PG 다운 시에만 발동 — 정상 운영(PG up)에선 status=ok → tick(8s) 유지라 heartbeat 신선도/healthcheck 무영향.

## REV-20260604-0146 [SKIPPED:동일 cutover read-back 불일치의 두 번째 면 — REV-0145 와 동일 패턴/리스크]
- Date: 2026-06-04
- Cycle: TASK-0145 후속 (`_load_kv_prefix_map` fingerprint KV read-back PG 라우팅), **Major §12.3**
- Verdict: PASS
- Reason: REV-20260604-0145 가 검증한 "cutover 후 read-back 을 write 정본(PG)으로 라우팅" 패턴과 동일. `_load_kv_prefix_map` 의 PG 분기는 이미 라이브로 검증된 `load_memory_kv` 패턴(`_read_runtime_pg("load_kv_all")`)을 그대로 따르며, 미가용 시 MySQL fallback 보존. RBAC/schema/secret/endpoint 무변경. 라이브 functional(PG fingerprint 765 read) + 재배포 후 generate_insight 수렴으로 실증.
- Note: 두 read-back 경로(artifact-verify, fingerprint-KV)를 모두 고쳐야 livelock 이 완전 정지 — 1번만 고치면 reason 이 `artifact_missing`→`fingerprint_changed` 로 전환되며 ollama 점유가 지속됨(라이브로 관찰·확인).

## REV-20260604-0145 [SUBAGENT:general-purpose — insight livelock PG read-back review]
- Date: 2026-06-04
- Cycle: TASK-0145 (insight worker livelock 근본 수정 + 운영 하드닝), **Major §12.3** — core 데이터 파이프라인 correctness
- Outside-voice channel: general-purpose subagent (독립 컨텍스트 — `git diff` + 변경 4개 모듈 + `agent_kb_schema.sql` DDL 대조 검토).
- Verdict: **PASS** (BLOCKER 0)
- 확인 결과:
  - A. PG read-back 가 MySQL 의미를 충실히 미러 — 8컬럼 select 순서/공유 `_apply_*` 인덱싱 일치, `texts` join + `COALESCE` 동형, `public.` schema-qualify 정확(ADR-0027, `_pg_connect_ro` search_path 미설정), `_scope_filter_sql_pg` 가 `IN(...) OR scope_key IS NULL OR ''` 로 `= ANY()` NULL-drop 함정 회피.
  - B. false-positive 위험 낮음(플래그는 실제 행/비어있지 않은 텍스트일 때만 set, completeness 는 4파트 AND), false-negative 위험은 원본 MySQL 설계와 동일(미회귀).
  - C. psycopg3(psycopg[binary]>=3.1) — `IN(%s,…)` placeholder 와 평탄화 param list 길이 일치, `dict.keys()` 는 list 리터럴로 spread(안전), 모든 경로(except→return None 포함) finally 에서 cursor/conn close — 누수 없음.
  - D. fallback(PG 미가용→MySQL 경로)은 이제 예외 surface 로 가시화 — 과거 완전 silent 대비 개선. (SHOULD-FIX: degraded 시 재생성 backoff 는 본 fix scope 밖 → TODOS 이월.)
  - E. 헬퍼 추출 리팩터는 MySQL 경로 출력 byte-동일(의도된 차이는 예외 로깅뿐).
  - F. 전역 `_INSIGHT_READBACK_WARNED` 동시성 무관 — worker 는 단일 프로세스/단일 `while True` 루프.
  - NIT: `_scope_filter_sql_pg`/`_pg_available`/`_pg_connect_ro` 의 `__all__` 등재가 load-bearing(주입 메커니즘) — 셋 다 등재 확인.

## REV-20260527-0120 [SKIPPED:Minor security hardening — single-file fallback removal]
- Date: 2026-05-27
- Cycle: TASK-0120 (reasoning fallback 노출 차단), **Minor §12.3**
- Verdict: PASS
- Reason: 단일 `agent_core.py` 변경으로 provider-private `reasoning` / `reasoning_content` 를 사용자 답변으로 내보내던 fallback 만 제거. RBAC, DB schema, audit, endpoint, tool 권한 변경 없음.
- Security note: "thinking 과정 출력" 요구는 raw chain-of-thought 노출이 아니라 공개 가능한 step trace (`work`, `reason`, `result_summary`) 로 처리해야 한다.

## REV-20260527-0009 [SUBAGENT:general-purpose — AR-M5 MySQL cleanup script review]
- Date: 2026-05-27
- Cycle: TASK-0119 (AR-M5 MySQL runtime tables cleanup), **Major §12.3** — data-loss boundary
- Outside-voice channel: general-purpose subagent (독립 컨텍스트 검토, `bin/runtime-cleanup-mysql.sh` + `docs/DECISIONS.md` ADR-0028 리뷰).
- Verdict: **NEEDS-FIX** → 수정 후 **PASS**
- Critical 1건 (C-1) 반영 완료:
  - C-1: Stage 4(DROP) + Stage 5(verify) 에서 `mysql -uroot -p"$MYSQL_PW"` cmdline 비밀번호 노출 → `docker exec -e MYSQL_PWD="$MYSQL_PW"` + `mysql -uroot` 로 수정. Stage 2(mysqldump)는 이미 올바른 방식 사용 중이었음.
- Major 3건 (M-1/M-2/M-3) 반영 완료:
  - M-1: `AGENT_RUNTIME_DUAL_WRITE` 체크가 case-sensitive (`"1"/"true"/"yes"` 만) — `TRUE/YES/On` 등 통과. `tr '[:upper:]' '[:lower:]'` 정규화 추가 + `"on"` 값도 차단.
  - M-2: Stage 5 실패 시 rollback hint 누락. `echo "FAIL ${tbl} 여전히 존재 — rollback: ${BACKUP_FILE} 으로 restore"` 추가. `trap ERR` 로 중단 시 backup path 항상 출력.
  - M-3: backup CREATE TABLE grep 패턴 `"CREATE TABLE.*\`?${tbl}\`?"` 이 서브스트링 매칭 허용 + 주석행 매칭 가능성. `"CREATE TABLE \`${tbl}\`"` (backtick-anchored) 로 강화. 최소 라인 수 10 → 50 으로 상향 (빈 6-table mysqldump ~80 lines).
- Minor 3건 (N-1/N-2/N-3) 반영 완료:
  - N-1: FK 코멘트 수정 — MySQL 에는 FK constraint 없음, PG only. 코멘트에 명시.
  - N-2: `MYSQL_PW` empty guard — backup/drop mode 진입 시 빈 비밀번호 early exit.
  - N-3: non-TTY bypass (`RUNTIME_M5_RUN_FROM_HUMAN_SHELL=1`) 시 audit 로그 `[WARN] TTY bypass active` 추가.

## REV-20260527-0008 [SUBAGENT:general-purpose — AR-M4 cutover read path review]
- Date: 2026-05-27
- Cycle: TASK-0118 (AR-M4 cutover read path), **Major §12.3**
- Outside-voice channel: general-purpose subagent (독립 컨텍스트 검토).
- Verdict: **NEEDS-FIX** → 수정 후 **PASS**
- Critical 2건 (C1/C2) 반영 완료:
  - C1: `_PG_LIST_CONVERSATIONS` 에 single-tenant 의도 주석 추가 (web UI multi-tenant 경로는 별도 cycle 명시).
  - C2: `list_delete_requested_conversation_ids` PG 경로를 `load_kv_by_key_value(value="1")` 에서 `load_kv_by_key` + client-side `_is_truthy_flag` 필터로 수정 — "true"/"yes" 값 포함하여 MySQL 패리티 완전 일치.
- Major 2건 (M1/M2) 반영 완료:
  - M1: `load_memory_context` PG partial failure 시 `logger.warning` 추가 — summary/msgs/kv None 여부 출력.
  - M2: `load_memory_context` happy path + partial failure fallthrough + list_delete_requested truthy values 3개 테스트 추가 (총 27 test).
- Minor 3건: m1 (메시지 순서 ordering 테스트 없음), m2 (tool_calls/content 동시 존재 주석), m3 (module-level env var 재로딩 문서화) — non-blocking, 다음 cycle 이슈 트래킹.

## REV-20260527-0007 [SKIPPED:Minor §12.3 — 신규 파일만, caller 수정 0건, RBAC 무변경]
- Date: 2026-05-27
- Cycle: TASK-0117 (AR-M3 backfill ETL)
- Reason: 신규 파일 추가만 (runtime_backfill.py + runtime-backfill.sh + test_runtime_backfill.py). 기존 caller (memory.py / agent_core.py / runtime_backend.py) 수정 0건. write path 무변경. RBAC 변경 0건. 실 DB 접근은 docker exec 환경에서만 발생 — 운영 read path/write path 에 영향 없음. outside-voice 불필요 조건 충족 (AGENTS.md §18.8: 신규 파일, 비파괴 추가, RBAC 무변경).

## REV-20260527-0006 [SUBAGENT:general-purpose — AR-M2-c/d audit + xmax review]
- Date: 2026-05-27
- TASK-Cycle: TASK-0115 (AR-M2-c) + TASK-0116 (AR-M2-d), **Minor §12.3**
- Outside-voice channel: general-purpose subagent (독립 컨텍스트 검토).
- Verdict: **PASS** (minor note 3개, non-blocking — Note 3 반영 완료)
  - Audit helper: `_RT_AUDIT_ACTION_MAP` 6 method + sensitive key 필터 + 16KB cap + best-effort connect + pg_branch opt + AGENT_RUNTIME_AUDIT_ENABLED opt-in — PASS.
  - xmax tagging: `_execute_upsert_with_branch()` + thread-local clear + 3 upsert 사용 + 3 insert pg_branch=None — PASS.
  - verify script: timestamp 컬럼 매핑 + ISO 8601 timezone + audit SLA 0.1% threshold — PASS.
- Timestamp: 2026-05-27T15:00:00Z

## REV-20260527-0005 [SUBAGENT:general-purpose — AR-M2-b dual-write 구현 review]
- Date: 2026-05-27
- TASK-Cycle: TASK-0114 (REQ-20260527-AR-M2-b, **Major §12.3** — PgRuntimeBackend 구현 + caller mirror callsite 추가)
- Outside-voice channel: general-purpose subagent (독립 컨텍스트 검토).
- Trigger: AGENTS.md §18.3 Major 분류 — caller 수정 7건 포함 (memory.py 4 + agent_core.py 3).
- Verdict: **NEEDS-FIX** (1 actionable + 1 observation)
  - **NEEDS-FIX (반영 완료)**: `_PG_INSERT_CORE_MESSAGE` 의 `%(tool_calls)s` 에 `::jsonb` 캐스트 누락 — DDL 상 `core_messages.tool_calls` 가 `jsonb` 타입이므로 캐스트 필수. `%(tool_calls)s::jsonb` 로 수정 완료 (runtime_backend.py line 92).
  - **Observation (문서화)**: `AGENT_RUNTIME_DUAL_WRITE` / `AGENT_RUNTIME_PG_REQUIRED` 는 module import 시 1회 평가. test fixture 가 env var 사후 설정 시 모듈 수준 상수에 미반영 → monkeypatch 로 직접 attribute 패치 필요 (현행 test 패턴이 이를 따르고 있음).
- SQL correctness: 전 6 SQL 상수 schema-qualified (`agent_runtime.*`) + named params `%(name)s` + ON CONFLICT 3개 (kv/summary/core_conversations) + RETURNING id + `::jsonb` cast (meta_json + tool_calls) — PASS.
- Exception isolation: conn open / method 호출 양 단계 try/except + PG_REQUIRED 분기 + conn.close() finally — PASS.
- Caller integration: 7개 callsite 모두 MySQL write 후 호출 + kwargs 정확 — PASS.
- Timestamp: 2026-05-27T14:00:00Z

## REV-20260527-0004 [SUBAGENT:general-purpose — AR-M1 DDL + RBAC review]
- Date: 2026-05-27
- TASK-Cycle: TASK-0112 (REQ-20260527-AR-M1)
- Verdict: PASS (Critical 2 반영 완료 — C1 kv FK 주석 + C2 meta_json jsonb)
- Timestamp: 2026-05-27T12:00:00Z

## REV-20260527-0003 [SKIPPED:plan-doc-m2a-skeleton]
- Related TASK: TASK-0113 (REQ-20260527-AR-M2-a, **Minor §12.3** — ABC + skeleton)
- Reason: code mutation 비파괴 (신규 파일만, 기존 caller 0 수정, RBAC 무변경, AGENT_RUNTIME_DUAL_WRITE default False).
- Timestamp: 2026-05-27T13:00:00Z

## REV-20260527-0002 [SKIPPED:infra-schema-only-no-new-role]
- Related TASK: TASK-0111 (REQ-20260527-AR-M0, **Minor §12.3** — Phase 2 AR-M0 Postgres 인프라)
- Reason: 본 cycle 은 기존 `agent_kb_rw` / `agent_kb_ro` role 재사용 + `agent_runtime` schema CREATE 만. 신규 Postgres role 신설 없음, 신규 RBAC PERMISSION_DEFINITIONS 항목 없음, production Python code path 변경 없음. 사용자 메모 `feedback_outside_voice_for_rbac.md` (RBAC catalog 변경 시 outside-voice 강제) 정합 — 본 cycle 은 catalog 변경 0건 (schema CREATE 는 Postgres infrastructure 레벨, PERMISSION_DEFINITIONS 변경 아님). AGENTS.md §18.8 dispatch: (a) "DDL" — schema 1개 CREATE 만, table DDL 없음. (b) "RBAC" — catalog 변경 없음. (c) code change — production Python code 0건. 본 KB M0 cycle 패턴 답습 (`REV-20260520-0004 [SKIPPED:outside-voice-not-required — M0 인프라 도입 cycle]`). 다음 cycle (AR-M1 DDL+RBAC — 6 runtime 테이블 CREATE + ADR-0026 + GRANT TABLE 권한) 진입 시 outside-voice 호출 필수.
- Timestamp: 2026-05-27T11:30:00Z

## REV-20260527-0001 [SKIPPED:read-only-baseline-no-code-no-rbac-no-schema]
- Related TASK: TASK-0110 (REQ-20260527-AR-M-1, **Minor §12.3** — Phase 2 AR-M-1 runtime baseline 측정)
- Reason: 본 cycle 은 `bin/agent-runtime-measure-baseline.sh` 신규 (read-only bash script — docker exec + mysql SELECT 만) + docs append 만. 실 code mutation 0건, RBAC catalog 변경 0건, schema mutation 0건, endpoint contract 변경 0건. 사용자 메모 `feedback_outside_voice_for_rbac.md` (RBAC 변경 시 outside-voice 강제) 정합 — 본 cycle 은 적용 trigger 외. AGENTS.md §18.8 dispatch 표 매칭: (a) schema/migration — 본 cycle 의 실 변경은 docs + read-only script 만, schema mutation 0건. (b) RBAC/auth — RBAC role 변경 0건. (c) code change — 0건 (bash read-only script 는 production path 외). 다음 cycle (AR-M0 Postgres schema CREATE + agent-runtime-bootstrap.sh, AR-M1 DDL+RBAC) 진입 시 outside-voice 호출 필수 (§18.8 trigger — DDL + RBAC 변경).
- Timestamp: 2026-05-27T11:00:00Z

## REV-20260526-0003 [SKIPPED:plan-only-no-code-no-rbac-no-schema]
- Related TASK: TASK-0109 (REQ-20260526-0109, **Minor §12.3** — plan-only, project-level cross-cutting migration plan 등록)
- Reason: 본 cycle 은 markdown plan 문서 1개 신규 (`docs/MIGRATION_AGENT_MEMORY_TO_PG.md`) + feature-0002 docs append 만. 실 code mutation 0건, RBAC catalog 변경 0건, schema mutation 0건, endpoint contract 변경 0건. 사용자 메모 `feedback_outside_voice_for_rbac.md` (RBAC 변경 시 outside-voice 강제) 정합 — 본 cycle 은 적용 trigger 외. AGENTS.md §18.8 dispatch 표 매칭: (a) "schema/migration" 키워드는 plan 문서 본문에서 등장하지만 본 cycle 의 실 변경은 docs 만 — schema mutation 부재. (b) "RBAC/auth" — 본 plan 의 Phase 2 AR-M1 시점에 RBAC role 결정 필요 (`agent_kb_rw` 재사용 vs `agent_runtime_rw` 신설) 이지만 본 cycle 의 deliverable 외. (c) "code change" — 0건. plan 문서 자체의 design 결정 (Phase 2 의 schema 선택 `agent_runtime` vs 별 DB) 은 실 implementation cycle (AR-M0/M1) 진입 시 outside-voice 호출 — 본 cycle 의 책임 외. 신규 세션이 Phase 2 AR-M1 진입 시 outside-voice 호출 필수 (DDL + RBAC 변경 = §18.8 trigger).
- Timestamp: 2026-05-26T07:00:00Z

## REV-20260526-0001 [SUBAGENT:codex — KB Postgres bootstrap fix (memory-init exit 1 정식 fix)]
- Date: 2026-05-26
- TASK-Cycle: TASK-0026 (KB Postgres bootstrap fix, **Major §12.3** — RBAC role 분리 인지 변경 + DDL credential path 도입)
- Outside-voice channel: codex (`codex-cli 0.130.0`, `codex exec --sandbox read-only`). 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 — RBAC role catalog 변경 + DDL credential path 도입은 정적 catalog blindspot 위험 영역.
- Trigger: 사용자 args 명시 호출 + §18.8 dispatch 키워드 (schema/role/RBAC) 매칭.
- Verdict: **BLOCK** → **PASS 전환** (Critical 3 본 cycle 내 흡수 + Nice-to-have 2 동반 흡수).
- Section A (Summary): 본 cycle 의 4 코드 파일 변경 (Dockerfile + agent_core.py + memory.py + kb_backfill.py, 총 +83/-26) 작성. 초안은 production memory-init 의 `attempted relative import` 증상을 해결 (absolute import + DDL superuser 분리). outside-voice review 가 3 Critical 식별: (B-1) memory.py 의 `AGENT_KB_PG_SUPERUSER` / `_SUPERPASSWORD` 이름이 bootstrap.sh 의 `AGENT_KB_PG_USER` / `_PASSWORD` 와 갈라짐 + .env.example 누락 → 운영자가 bootstrap 환경 재사용 가정하면 silent skip + (B-2) verification 이 fail-loud 아님 → SUPERPASSWORD 미설정 + schema 부재 + `AGENT_KB_PG_REQUIRED=1` 조합에서 "KB Postgres schema 적용 완료" 라고 출력하며 통과 = production symptom 재발 + (B-3) `except ImportError` 가 너무 광범 → `.db` 내부 실제 ImportError (psycopg 부재 등) 까지 덮어 원인 변경. 본 cycle 흡수 + Nice-to-have 2 동반.
- Section B (Critical findings — 본 cycle 내 반영 완료):
  - **B-1 (Critical)**: memory.py line 1439-1441 — `_ensure_pg_schema()` 의 superuser env contract 가 bootstrap.sh 와 갈라짐. **반영**: `AGENT_KB_PG_SUPERUSER` / `_SUPERPASSWORD` / `_SUPERUSER_HOST` 1순위 + `AGENT_KB_PG_USER` / `_PASSWORD` legacy fallback (`os.getenv(SUPER*) or os.getenv(LEGACY*)`). 운영자가 bootstrap 환경 그대로 재사용해도 silent skip 안 됨. `.env.example` 에 3 SUPER* 변수 추가 + bootstrap.sh 와의 정합 주석.
  - **B-2 (Critical)**: memory.py line 1571-1582 — return dict 직전에 verification 만 하고 누락 시 raise 안 함 → silent PASS. **반영**: `expected_tables = {fact_entries, texts, rag_documents, rag_objects}` + `expected_extensions = {vector, pg_trgm}` + `view_present` 검사 → 누락 시 `RuntimeError("KB Postgres schema verification failed: missing_tables=..., view_present=..., missing_extensions=...{ddl_hint}")` raise. `ddl_hint` 는 actionable — `AGENT_KB_PG_SUPERPASSWORD` 설정 또는 `bin/kb-pg-role-bootstrap.sh --apply-schema` 사전 실행 안내. `init_memory()` 의 `AGENT_KB_PG_REQUIRED=1` 분기가 RuntimeError 를 sys.exit(1) 로 변환 — production symptom 재발 차단.
  - **B-3 (Critical)**: memory.py line 1410-1413 (+ 1444-1448) — `try/except ImportError` 가 `.db` 내부의 실제 ImportError (예: psycopg 미설치) 까지 덮어 원인 변경. **반영**: `except ImportError as _imp_err:` + `if not (_imp_err.name is None or _imp_err.name == __package__): raise` — relative import 컨텍스트 부재 (`__package__ is None`) 일 때만 absolute fallback. `.db` 내부의 진짜 ImportError 는 그대로 전파.
- Section C (Nice-to-have — 본 cycle 동반 흡수):
  - C-1: `.env.example` 에 3 SUPER* 변수 + bootstrap.sh 와의 정합 주석 ✓.
  - C-2: kb_backfill.py 의 OFFSET pagination 에 "MySQL source must be frozen/read-only during backfill" 주석 추가 ✓ (M3 backfill 운영 가정 명시).
- Section D (Verdict): BLOCK → **PASS 전환** — 3 Critical + 2 Nice-to-have 본 cycle 흡수.
- Decision authority: 사용자 args 명시 + 사용자 메모 `feedback_outside_voice_for_rbac.md` 정책 정합. BLOCK verdict 가 본 cycle 의 변경 자체를 reject 한 것이 아니라 추가 safety 보강 요구 — 모두 반영 완료.

## REV-20260522-0013 [SUBAGENT:Plan-subagent — M5 cleanup script + ADR-0025 + dual-write deprecation]
- Date: 2026-05-22
- TASK-Cycle: TASK-0025 (M5 cleanup script + ADR-0025 + deprecation note, **Major §12.3** — RBAC 영향 cycle + 데이터 손실 boundary)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 (audit instrumentation deprecation timing + 데이터 손실 boundary).
- Verdict: **FAIL** → **PASS 전환** (Blocker 5 + Critical 4 본 cycle 내 흡수). 데이터 손실 가장 sensitive cycle — 표면적 safety (confirm string + dry-run + dependency-reverse drop order) 위에 outside-voice 가 식별: (B-1) mysqldump VIEW DDL 누락 → restore 불가 + (B-2) backup integrity verification 부재 → corrupt gzip silent loss + (B-3) `_DualWriteMirror` caller 제거 선행 없이 DROP → 운영 crash + (B-4) 14-day window policy-only, runtime 미강제 + (B-5) `--confirm` arg 누락 / mode 중복 silent promotion + (B-6) TTY interactive double-confirm 부재 + (B-7) env fallback 부재 + (B-8) backup chmod / SHA256 부재. 본 cycle 흡수.
- Section A (Summary): M5 의 4 산출 (cleanup script + ADR-0025 + deprecation docstring + 6 unit test) 작성. outside-voice 가 데이터 손실 boundary silent path 식별 — 5 Blocker 모두 흡수, test 11개로 확대.
- Section B (Blocker/Critical findings — 본 cycle 내 반영 완료):
  - **B-1 (Blocker)**: mysqldump 가 `"${TABLES[@]:1}"` 로 VIEW skip → DDL 누락 = restore 불가. **반영**: VIEW 포함 list + `CREATE.*VIEW.*AgentMemoryFacts` grep assertion.
  - **B-2 (Blocker)**: backup integrity verification 부재 → corrupt gzip silent. **반영**: `gunzip -t` + line count threshold + per-table `CREATE TABLE` + VIEW DDL assertion. fail 시 backup dir 삭제.
  - **B-3 (Blocker)**: caller 제거 선행 없이 DROP → MySQL `cur.execute()` crash. **반영**: `AGENT_KB_DUAL_WRITE=0` sentinel 강제. =1/true/yes 시 진행 차단 + M5-implementation cycle 선행 안내.
  - **B-4 (Blocker)**: 14-day window policy-only. **반영**: `--cutover-date YYYY-MM-DD` 필수 + ISO 8601 regex + `(today - cutover)/86400 < 14` 차단.
  - **B-5 (Blocker)**: `--confirm` mode 중복 / missing arg silent promotion. **반영**: mode 중복 거부 + arg 누락 거부 + default MODE.
  - **B-6 (Critical)**: TTY interactive double-confirm 부재. **반영**: `[ -t 0 ]` 시 `read -r typed_phrase` + 정확 비교, non-TTY 시 `KB_M5_RUN_FROM_HUMAN_SHELL=1` 강제.
  - **B-7 (Critical)**: env fallback 부재. **반영**: `${AGENT_KB_READ_BACKEND:-$(grep ...)}` shell 우선.
  - **B-8 (Critical)**: backup world-readable, no SHA256. **반영**: 별 디렉터리 0700 + dump.sql.gz 0600 + sha256 sidecar.
- Section C (Nice-to-have):
  - C-2 (MYSQL_PWD env) ✓ 흡수.
  - C-7 (utf8mb4 + hex-blob) ✓ 흡수.
  - C-1/C-3/C-4/C-5/C-6 M5-implementation/별 cycle 위임.
  - B-9 test thinness ✓ — 5 신규 test 추가 (11 PASS).
- Section D (Verdict): FAIL → **PASS 전환** — 5 Blocker + 4 Critical 본 cycle 흡수.
- Decision authority: 사용자 메시지 "이번 세션에서 남은 cycle을 모두 완수해주세요" + 데이터 손실 safety 흡수 승인.

## REV-20260522-0012 [SUBAGENT:Plan-subagent — M4 cutover (FULLTEXT → pg_trgm + read backend routing)]
- Date: 2026-05-22
- TASK-Cycle: TASK-0024 (M4 cutover read path 전환 + cutover readiness script, **Major §12.3** — RBAC 영향 cycle)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 (read backend switch 는 ADR-0021 의 2-layer RBAC 의 layer 1 — connection-level role 영향).
- Verdict: **FAIL** → **PASS 전환** (Critical 4 본 cycle 내 흡수 + B5 follow-up 명시).
- Section A (Summary): M4 cutover 의 핵심 산출 (PG search SQL + read backend routing + cutover readiness 10-gate script + 6 unit test) 작성. 단 outside-voice review 가 **4 Critical 결함** + 1 Critical follow-up 식별: (B1) `knowledge.py` 의 logger 미정의 → fail-soft except 가 NameError 로 hard-crash + (B2) PG scope_keys 의 NULL/'' 매치 누락 → MySQL `_scope_filter_sql()` 등가성 위배, 빈 scope row silent drop + (B3) `_pg_connect()` 가 RW user 사용 → ADR-0021 의 ro role 분리 정책 위배 (RBAC 회귀) + (B4) fail-soft fallback path 의 regression test 부재 → Gate 4 가 B1 검출 못 함 + (B5, follow-up) `AGENT_KB_PG_REQUIRED=1` 시 fail-loud propagate 가 의도 — 현재는 fail-soft 가 항상 적용. 본 cycle: B1/B2/B3/B4 즉시 흡수, B5 는 ADR-0021 후속 cycle (M4-tweak).
- Section B (Critical findings — 본 cycle 내 반영 완료):
  - **B-1 (Critical/Blocker)**: `knowledge.py` 의 `logger` symbol 미정의 → fail-soft `except Exception` 의 `logger.warning(...)` 가 `NameError` propagate → 실 production PG 실패 시 hard-crash (500). **반영**: `import logging` + `logger = logging.getLogger("agent_core.knowledge")` module-level 정의.
  - **B-2 (Critical/Blocker)**: PG `scope_key = ANY(%(scope_keys)s)` 가 `scope_key IS NULL` / `= ''` 매치 안 함. MySQL `_scope_filter_sql()` 는 candidate list 의 `""` 있으면 `IS NULL OR = ''` 절 emit — silent row drop. **반영**: `_INCL_NULL` vs `_STRICT` 4 variant SQL + `search_rag_documents()` 가 candidate list 검사 후 분기. blank `""` 는 `ANY()` 에는 안 들어가고 별 `IS NULL OR = ''` 절로 처리.
  - **B-3 (Critical/Blocker)**: read path 가 `_pg_connect()` (RW user) 사용 → ADR-0021 의 layer 1 (agent_kb_rw vs agent_kb_ro 분리) 위배. **반영**: `_pg_connect_ro()` 신설 + `AGENT_KB_PG_USER_RO` / `AGENT_KB_PG_PASSWORD_RO` env 변수 + `_load_rag_documents_for_request_pg()` 가 `_pg_connect_ro()` 사용 + ro 미설정 시 RW fallback + warning log.
  - **B-4 (Critical)**: fail-soft `except` branch 의 regression test 부재. **반영**: `test_pg_read_failure_falls_back_to_mysql` 추가 — PG path raise 시 logger.warning 호출 + MySQL path 호출 + 결과 반환 보장 + `hasattr(knowledge, "logger")` smoke assertion (B1 회귀 방지).
- Section C (Nice-to-have findings — M4-tweak 또는 M5 위임):
  - C-1: `_load_rag_documents_for_request_pg()` 가 매 호출 connection open+close — `psycopg_pool.ConnectionPool` 도입 권장 (M5).
  - C-2: cutover-readiness Gate 7/9 INCONCLUSIVE 가 자동화 ambiguous — `--accept-inconclusive` flag 권장 (M4-tweak).
  - C-3: pg_trgm vs MySQL FULLTEXT 의미적 divergence — golden fixture (M4-tweak).
  - C-4: typing imports 정합 ✓.
  - C-5: `_pg_connect_ro` 에 `SET TRANSACTION READ ONLY` 추가 (M4-tweak).
  - C-6: `AGENT_KB_DUAL_WRITE=1` post-cutover 전환 doc 명시 ✓.
  - C-7: ft_score fallback 정합 ✓.
  - **B-5 (Critical follow-up, M4-tweak)**: `AGENT_KB_PG_REQUIRED=1` 시 fail-loud propagate vs Stage A rollback safety 의 fail-soft 모순 — 별 ADR-0021 follow-up cycle.
- Section D (Verdict): FAIL → **PASS 전환** — 4 Critical 본 cycle 내 흡수 + B-5/C-1/C-2/C-3/C-5 M4-tweak/M5 위임.
- Decision authority: 사용자 메시지 "이번 세션에서 남은 cycle을 모두 완수해주세요" + Critical 흡수 명시 승인.

## REV-20260522-0011 [SKIPPED:rbac-unchanged-data-migration — M3 backfill ETL + embedding worker]
- Date: 2026-05-22
- TASK-Cycle: TASK-0023 (M3 backfill ETL + embedding worker, **Minor §12.3** — RBAC 무변경)
- Decision: outside voice / Plan subagent SKIP — 본 cycle 의 ETL 은 RBAC / endpoint / audit 변경 없음. agent_kb_rw role 의 기존 INSERT 권한을 활용한 데이터 이전 + texts.embedding 컬럼 일괄 생성만. 사용자 메모 `feedback_outside_voice_for_rbac.md` 의 "RBAC 변경 시점만 outside voice 요구" 정책 정합.
- Reason: (a) modules/kb_backend.py / verify.sh / stress.sh 변경 없음 — audit instrumentation 무변경. (b) PG SQL template 변경 없음 — TABLE_MAPPING 의 INSERT...ON CONFLICT 만 추가, 기존 SQL 재사용. (c) OpenAI embedding 호출은 read-only API call + texts UPDATE — `agent_kb_rw` role 의 기존 SELECT/UPDATE 권한으로 충분. (d) backfill 의 분모 정의 (--since $KB_DUAL_WRITE_START_TS) 가 M2 dual-write 시작 이전 row 만 처리하므로 중복 작성 위험 없음.
- 본 cycle 의 검증 방법:
  - `pytest tests/test_kb_backfill.py tests/test_kb_embedding_worker.py -v` — 10 PASS (TABLE_MAPPING 정합 / state roundtrip / dry-run no-op / main smoke / cost estimation / length mismatch / UPDATE SQL / dry-run no-OpenAI)
  - `pytest tests/` 전체 — 31 PASS, 2 SKIPPED (회귀 없음)
  - `bash -n bin/kb-backfill.sh` / `bin/kb-embedding-worker.sh` — syntax PASS
- Alt 거부:
  - **outside-voice review 호출**: ETL 의 정합성은 unit test 로 충분 검증. RBAC / 보안 영향 없음.
- Risks: (a) OpenAI API cost — M-1 baseline ~800 texts × text-embedding-3-small ≈ USD 0.01~0.05 (보수 추정), §12.1 외부 비용 조항의 USD 100 cap 안. dry-run cost estimation 으로 cap 사전 확인. (b) backfill state file (artifacts/shared/kb-backfill-state.json) 의 손상 — 재진입 시 last_id leftover, --reset-state 로 복원.
- Test: dry-run smoke + unit test 10건.

## REV-20260522-0010 [SUBAGENT:Plan-subagent — M2-d pg_branch + S2-S6 + delete/prune SLA + Nice-to-have 7]
- Date: 2026-05-22
- TASK-Cycle: TASK-0022 (M2-d pg_branch xmax + S2/S4/S5/S6 + tagging coverage gate + Nice-to-have 7, **Major §12.3** — RBAC 동반)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 (audit instrumentation 확장 + pg_branch tagging 신설). M2-c (`REV-20260521-0009`) 의 follow-up — Nice-to-have 7건 + xmax-based branch tracking 검증.
- Verdict: **NEEDS-TWEAK** → **PASS 전환** (2 Blocker + 4 Critical 본 cycle 내 흡수). 구조적 shape 정상 (`xmax = 0` semantics, metrics counter, test catalog). 단 (B-1) `--keep-agent-container` mode 가 존재하지 않는 `python -m agent_core --ask` invocation → silent zero-traffic + (B-2) `verify_audit_sla_delete_prune()` 의 분모/분자 가 cross-DB SLA 가 아닌 tagging coverage 임이 명시 안 됨 (false-green) + (B-3) `_clear_pg_branch()` 가 mirror 진입 첫 위치 아님 → stale 노출 가능 + (B-4) connection-failure path 에서 clear 누락 + (C-5) ChangeJson 16KB truncate 시 `pg_branch` 소실 + (C-1) xmax docstring 부정확. 본 cycle 흡수 완료.
- Section A (Summary): 6 산출 (pg_branch xmax + thread-local + audit ChangeJson 확장 + metrics + tagging coverage gate + S2/S4/S5/S6 + Nice-to-have 7) 정상 작성. 구조적으로 audit instrumentation 가 한 단계 정확해짐.
- Section B (Critical findings — 본 cycle 내 반영 완료):
  - **B-1 (Blocker)**: `--keep-agent-container` stress mode 가 존재하지 않는 `python -m agent_core --ask` 호출 → silent zero-traffic. **반영**: `python /app/agent_core.py "$question"` positional 정정 (agent_core.py:1796 argparse 정합).
  - **B-2 (Blocker)**: `verify_audit_sla_delete_prune()` 의 분모/분자 가 cross-DB SLA 아닌 tagging coverage. **반영**: 함수명 `verify_pg_branch_tag_coverage` rename + CLI flag `--pg-branch-tag-coverage` + docstring 의 "NOT a cross-DB SLA" 명시 + silent audit loss / thread-local leak 한계 explicit.
  - **B-3 (Critical)**: `_clear_pg_branch()` 위치 stale. **반영**: `_mirror()` 첫 줄로 이동 — 모든 early-return path 통일.
  - **B-4 (Critical)**: connection-failure path clear 누락. **반영**: B-3 와 동일 fix.
  - **C-5 (Critical)**: ChangeJson 16KB truncate 시 pg_branch 소실. **반영**: truncated dict 에 `pg_op_kind`, `pg_branch` 동반 보존.
- Section C (Nice-to-have): C-1 xmax docstring + C-2 metrics docstring + C-3 atomicity comment + C-4 regex 보강 + C-9 worst exit code propagation 본 cycle 흡수 ✓. C-6 (schema-path skip) / C-7 (MySQL 8.0+ floor 문서) / C-8 (FakeCursor cosmetic) M3 위임.
- Section D (Verdict): NEEDS-TWEAK → **PASS 전환** — 2 Blocker + 4 Critical 본 cycle 내 흡수.
- Decision authority: 사용자 "이번 세션에서 남은 cycle을 모두 완수해주세요" 승인.

## REV-20260522-0005 [SKIPPED:docs-only-batch-closure]
- Date: 2026-05-22
- Decision: TASK-0101 (REQ-20260522-0004, **Minor §12.3** — backlog closure batch). 본 세션의 잔여 backlog 항목 (TASK-0010/0011/0004 placeholder + TASK-0005 MCP 검증 + TASK-0072 재확인) 일괄 closure 마킹. outside voice / plan-eng-review skip — docs / 마킹만 + 동작 변경 0 + RBAC/DB/endpoint/audit 무변경.
- Reason: 본 closure 의 본질은 **기존 작업의 마무리 마킹**: (a) 코드 작업 자체는 이미 완료되었으나 TASK queue checkbox 가 잔존 (`[ ]`), (b) placeholder 시나리오 항목이 각 feature 의 TEST.md / ANCHOR §3 invariant 로 자연 흡수되어 별도 작업 불필요, (c) MCP 검증은 본 cycle 실 환경 health probe 로 완료. 본 cycle 의 절차 (cycle-init.sh + verify-completion + PR + cycle-finalize) 는 그대로 적용하되 outside voice 는 docs-only 변경에 가치 낮아 SKIPPED.
- 본 cycle 의 검증 방법:
  - 각 feature 의 TASK.md 의 `[x]` 마킹 변경이 `git diff` 으로 확인됨 (6 feature × 1-2 line edit).
  - TASK-0005 MCP 검증의 실 결과: `docker ps --filter name=repo-mcp-1` = `Up 23 hours`, `curl -s -o /dev/null -w "%{http_code}" http://localhost:28000/healthz` = `200`, Workbench UI 응답 정상 (서버 로그 `Workbench at http://localhost:8080/ MCP server endpoint at http://localhost:8080/mcp`).
  - TASK-0072 main closure 재확인: `grep "^- \[.\] TASK-0072 " unit/feature-0003-agent-web-ui/docs/TASK.md` 결과 = `[x] DEPLOYED` (TASK-0099 audit followup backlog tracker hygiene cycle 에서 처리됨).
- Alt 거부:
  - **각 feature 별 별 PR**: 시간 비용 큼 + ownership 모호 (cross-feature placeholder closure). 본 batch closure 는 main 의 TASK-0099 (audit followup backlog tracker hygiene) 와 동일 패턴 — single closure cycle 로 cross-feature 마킹.
  - **외부 시각 (Codex / plan-eng-review)**: docs / 마킹 closure 에 가치 낮음. 사용자 메모 `feedback_outside_voice_for_rbac` 도 RBAC 변경 시점만 요구.
- Deferral 항목 (본 batch 의 closure 대상 외):
  - **TASK-0034** (feature-0003 복잡 QA 성능 테스트): LLM API (gpt-5.4-mini 5 병렬) + 실 DB + truth 쿼리 작성 의존 → 사용자 운영 환경 위임.
  - **TASK-0044** (feature-0003 사업팀 pilot): admin 콘솔 manual 발급 + 사업팀 사용자 협업 + REPLICA_DB_* 설정 의존 → 사용자 운영 위임.
  - **TASK-0020** (feature-0002 KbBackend M2-b dual-write): main 에서 별 cycle 진행 — 본 batch 외.
  - **TASK-0021** (feature-0002 KbBackend M2-c cross-DB audit + SLA + invariant test): main 의 별 작업자 진행 중 (TASK-0021 rebase in-progress 확인) — 본 batch 외.
- Risks: docs / 마킹 closure 만, 회귀 위험 0.
- Test: TASK-0005 의 실 환경 health probe 외 별 test 추가 불필요 (docs / 마킹 closure).

## REV-20260522-0004 [SKIPPED:hot-fix-dependency-only]
- Date: 2026-05-22
- Decision: TASK-0100 (REQ-20260522-0003, **Minor** §12.3 — multipart UploadFile 의존성 hot-fix). TASK-0098 (PR #49) ship 직후 사용자 검증 단계에서 발견된 main build 회귀 차단. `python-multipart>=0.0.9` 한 줄 추가 + annotation. outside voice / plan-eng-review skip — 의존성 추가만 + 동작 변경 0 + RBAC/DB/endpoint/audit 무변경.
- Reason: 본 회귀의 root cause 는 PR #66 (TASK-0094 Sprint 1 Phase 5) 가 attachment upload endpoint 의 `UploadFile` 도입 시 의존성 추가를 누락. FastAPI 의 multipart UploadFile 처리에 `python-multipart` 가 필수. 본 hot-fix 는 미반영된 의존성을 명시화하는 것이며, 새 기능 추가 / 정책 변경 / 동작 분기 없음. Minor §12.3 의 통상적 build 회귀 fix 패턴.
- 본 cycle 의 검증 방법:
  - TASK-0098 의 사용자 위임 검증 (HTTP smoke 5/5 + UI dogfood 4 스크린샷) 이 본 hot-fix 적용 working tree 에서 PASS 확인 (artifacts/shared/task-0098-final-*.png). 즉 본 fix 위에서 본 cycle 외 다른 endpoint (`/api/auth/me`, `/api/admin/me`, Profile Drawer, admin 콘솔) 가 정상 작동 = 의존성 fix 의 부작용 없음 증명.
  - `docker compose build web` 후 `docker compose up -d --no-deps --force-recreate web` → web container `Up` 안정 + `curl http://localhost:18080/api/auth/me` HTTP 200 (또는 비로그인 401) 응답.
- Alt 거부:
  - **별 PR 분리 (TASK-0094 첨부 cycle 안에 흡수)**: 그 cycle 의 head 는 main 의 활발한 후속 PR (#66/#67/#69) 으로 이미 진행 중. 본 hot-fix 를 그 큰 cycle 에 묶으면 머지 timing 지연 + cycle ownership 모호. Minor §12.3 의 명확한 회귀 차단 → 본 별 cycle 진행이 정합.
  - **외부 시각 (Codex outside voice) 호출**: 의존성 추가 hot-fix 는 outside voice 가치 낮음. RBAC / 보안 / 데이터 영향 없음. 사용자 메모 `feedback_outside_voice_for_rbac` 도 RBAC 변경 시점만 outside voice 요구 — 본 fix 는 적용 외.
- Risks: 의존성 추가는 새 transitive dep 의 가능성 — `python-multipart` 는 표준 FastAPI multipart parser, 추가 위험 미미. version `>=0.0.9` 는 보수적 lower bound (pip 의 dependency resolver 가 적정 버전 선택). image rebuild 시점에만 `pip install` 실행 — 기존 운영 영향 0.
- Test: TASK-0098 사용자 검증 단계의 HTTP smoke 5/5 + UI dogfood 4 PASS (artifacts/shared/task-0098-final-01~04). 본 cycle 의 별 test 추가 불필요 (의존성 추가 hot-fix).

## REV-20260521-0009 [SUBAGENT:Plan-subagent — M2-c cross-DB audit + SLA + invariant test]
- Date: 2026-05-22
- TASK-Cycle: TASK-0021 (M2-c cross-DB audit explicit call + SLA verify body + stress.sh body + ANCHOR §3 invariant test S1/N1/N2, **Major §12.3** — RBAC 동반)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 (audit ActionCode 신설 + agent_kb_rw role check N2). M2-b (`REV-20260520-0008`) 의 follow-up — ADR-0021 §Consequences M2-c 책임 5건 산출 검증.
- Verdict: **NEEDS-TWEAK** → **PASS 전환** (5 Critical 본 cycle 내 반영). 구조적 shape 정상 (`_log_kb_write_audit()` 위치, audit SLA 함수 분기, S1/N1 mock 패턴, thread-safe lock). 단 (1) audit SLA 분모/분자 mismatch (UPSERT-update branch + delete/prune 행이 numerator 에는 들어가나 denominator 에서는 빠짐, 음수 ppm silent PASS) + (2) N1 LLM tripwire 가 존재하지 않는 `modules.llm_api` 패치 시도 (실 모듈은 `modules.llm`) + (3) prune signature `keep_top=` vs 실제 `keep_limit=` (silent swallow) + (4) `_log_kb_write_audit()` 매 호출 MySQL connect 무제한 retry + (5) ResourceId 가 단일 `fact_key`/`object_key` 평탄화 (conv|scope joinability 손실) + (6) ChangeJson 16KB 미캡 → 본 cycle 내 5 Critical 흡수 완료.
- Section A (Summary): 4 산출 (kb_backend.py audit / verify.sh / stress.sh / invariant test) 정상 작성. 구조적으로 ADR-0021 §Consequences M2-c 책임 5건을 cover. 단 metric 정확성과 test 실효성에 critical 결함 다수 → 본 cycle 내 흡수.
- Section B (Critical findings — 본 cycle 내 반영 완료):
  - **B-1 (Critical)**: `verify_audit_sla()` 분모/분자 mismatch. PG `created_at >= since` 만 사용 → UPSERT-update branch 제외 + audit 행은 모든 mirror 호출 카운트 → audit > pg → 음수 ppm silent PASS. **반영**: `GREATEST(created_at, updated_at) >= since` (texts 는 INSERT ON CONFLICT DO NOTHING 이라 created_at 만) + audit numerator 를 `kb.write.mirror` only 로 한정 (delete/prune 제외, M2-d 별 metric) + `audit > 2 × pg` 시 fail-loud + zero-denom INCONCLUSIVE exit 2 + ChangeJson 에 `pg_op_kind` 태깅 (write/delete/prune) — 후속 cycle 의 metric 분리 기반. methodology limitation (same row N-times update 노이즈) 명시.
  - **B-2 (Critical)**: N1 LLM tripwire 가 `modules.llm_api` monkeypatch 시도 — 실 모듈은 `modules.llm`. `from openai import OpenAI` binding 후라 `openai.OpenAI` patch 도 무효. **반영**: `modules.llm._get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` prefix 모든 함수 + `modules.llm.OpenAI` 직접 patch. smoke assertion (1 patch 라도 미설치 시 즉시 fail).
  - **B-3 (Critical)**: N1 prune 호출 `keep_top=10` 이 PgKbBackend `keep_limit=` 와 mismatch → `_mirror()` silent swallow → prune path 미실행. **반영**: signature 정정 (`conversation_id=None, scope_key="common", fact_key="k", keep_limit=10`) + 6 method SQL (`delete from fact_entries` / `rag_documents` / `rag_objects` / `fact_entries` / `texts`) 모두 captured 에 발행됐는지 assertion.
  - **B-4 (Critical)**: `_log_kb_write_audit()` 매 호출 `connect_with_retry()` 기본 `AGENT_DB_CONNECT_RETRIES` backoff → MySQL 일시 장애 시 caller block. **반영**: `attempts=1` — best-effort, silent log + SLA 가 miss count.
  - **B-5 (Critical)**: ResourceId 단일 `fact_key`/`object_key` 평탄화 → conv|scope joinability 손실. **반영**: `_build_audit_resource_id()` composite builder 신설 — `conv|scope|key|...` `|` 구분 string 64 char cap. None 은 `-` placeholder. 6 method 각 layout (text_hash[:64] / conv|scope|fact_key / conv|scope|fact_key|content_hash[:12] / conv|scope|object_type|object_key / conv|scope|fact_key|keep_limit).
  - **B-6 (Critical)**: ChangeJson 길이 제한 없음 → `max_allowed_packet` 또는 column length 초과 시 silent loss. **반영**: 16KB 캡 — 초과 시 `_truncated`, `_original_len`, `mirror_method`, `resource_id` metadata 만.
- Section C (Nice-to-have findings — M2-d 위임):
  - C-1: N2 env var `AGENT_KB_PG_INTEGRATION_TEST` README/playbook 미문서화.
  - C-2: stress.sh 25-iteration container churn — `docker exec` 재사용 옵션.
  - C-3: FAILURES counter step 별 미식별 — per-step log file.
  - C-4: verify.sh SINCE SQL injection escape (operator-driven, low risk).
  - C-5: S1/N1 의 `_BACKENDS_CACHE` reset finalize 누락 (test ordering risk).
  - C-6: `_PG_PRUNE_FACT_ENTRIES` 의 correlated IN 성능.
  - C-7: verify.sh `2>/dev/null` connection error suppress — debugging 저해.
  - C-8: zero-denominator PASS → 본 cycle 에서 INCONCLUSIVE exit 2 로 흡수.
- Section D (Verdict): NEEDS-TWEAK → **PASS 전환** — 5 Critical 본 cycle 내 흡수 + 1 Critical (B-6) 동반 흡수 (총 6 Critical). Nice-to-have 8건 M2-d 위임.
- Decision authority: 본 cycle 의 5 산출 + Critical 6 반영은 §2.1 PLAN-APPROVED 마커 범위 (Major §12.3 — RBAC 동반 변경). 사용자 메시지 "다음 Phase도 진행해주세요" + "(1) 방향으로 진행" 명시 승인.

## REV-20260520-0008 [SUBAGENT:Plan-subagent — M2-b dual-write 본 구현]
- Date: 2026-05-21
- TASK-Cycle: TASK-0020 (M2-b dual-write 본 구현, **Major §12.3** — RBAC 동반)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 (RBAC role `agent_kb_rw` 활성 cycle). M2-a (`REV-20260520-0007`) 의 follow-up — M2-a Critical/Blocker 가 본 cycle 까지 carry-over 안 됨을 확인 후 본 cycle 의 method body + caller 통합 + test design 검증.
- Verdict: **NEEDS-TWEAK** — KbBackend ABC + method body + Postgres SQL 의미 정합성은 PASS. 하지만 (1) caller 4 위치 silent/fail-loud pattern 불일치 + (2) `_publish_fact` dead try/except wrapper + (3) `_prune_fact_entries_for_key` 광역 swallow 의 mirror raise 침묵 + (4) latency baseline 미측정 + (5) test isolation (sys.path + dual import path) + (6) caller actual call test 부재 + Blocker (cross-DB audit explicit call 책임 cycle 미명시 + SLA 측정 도구 cycle 책임 명시) 본 cycle 내 반영 필요.
- Section A (KbBackend method body 의 의미 정합성) — **대체로 PASS**:
  - MySQL ↔ Postgres `upsert_fact_entry` 의 GREATEST(weight) + GREATEST(COALESCE(confidence, 0)) 정합 ✓
  - `upsert_rag_object` 의 카테고리 7 컬럼 `COALESCE(NULLIF(...))` 정합 ✓
  - `prune_fact_entries_keep_top` Postgres self-reference race condition theoretical risk — Nice-to-have docstring 권고
  - `MysqlKbBackend` ↔ caller raw SQL drift 방지 — M3 refactor TODO (Nice-to-have)
- Section B (Caller 5 위치 회귀 risk) — **Critical 3건 + Blocker 1건**:
  - `_text_store_insert`: silent log 패턴 ✓ (caller hot path 보호)
  - `_publish_fact`: dead try/except wrapper (knowledge.py:677-696) — re-raise 만 + 광역 except 없음 → no-op. **Critical**: 본 wrapper 삭제 + 정책 명문화
  - `_prune_fact_entries_for_key`: 광역 `except Exception: return 0` 가 mirror 의 fail-loud raise 까지 swallow → mysql 측 DELETE 후 postgres 측 정합 위배 silent break. **Critical**: MySQL DELETE 만 cover 분리
  - `_upsert_rag_memory_from_fact`: outer 광역 catch (caller chain) — 동일 silent break risk
  - Cross-DB audit explicit call 부재 (ADR-0021 §Consequences) — **Blocker**: M2-c cycle 책임 명시
- Section C (Partial failure 격리 + AGENT_KB_PG_REQUIRED) — **Critical 1건 + Blocker 1건**:
  - silent log format ✓ (structured `kb_pg_mirror_fail`) — aggregation 정책 부재 Nice-to-have
  - `_get_pg_conn()` 의 매 호출 새 connection — agent hot path latency 영향. **Critical**: latency baseline 측정/문서화 (M2-c 책임 명시)
  - `_BACKENDS_CACHE` singleton — multi-thread race condition theoretical risk (semantic 정합 유지) — Nice-to-have `threading.Lock()`
  - SLA 측정 도구 (`bin/kb-dual-write-verify.sh --audit-sla`) — **Blocker**: M2-c cycle 책임
- Section D (Test coverage) — **Critical 2건**:
  - 8 unit test 가 핵심 invariant cover ✓
  - **Critical**: caller actual call verification 부재 (regression 보호 부재)
  - **Critical**: test isolation — sys.path.insert + dual import path → CI 안정성 risk
  - `caplog` silent log verification — Nice-to-have
- Section E (잘못된 가정 / 누락) — **Critical 1건 + Blocker 1건**:
  - **Blocker**: Cross-DB audit explicit call 책임 cycle 미명시 (ADR-0021 §Consequences M2-c 책임)
  - **Critical**: caller 4 위치 silent/fail-loud pattern 불일치 정책 명문화 (Section B 와 합산)
  - REV-20260520-0007 Nice-to-have 7건 中 `_BACKENDS_CACHE` cache ✓, GREATEST(weight) ✓ — psycopg autocommit docstring 미흡수 (Nice-to-have)
- Critical (본 cycle 내 처리 완료):
  1. **Caller pattern 통일**: `knowledge.py:677-696` 의 dead try/except wrapper 삭제 + `_prune_fact_entries_for_key` 의 광역 swallow 를 MySQL DELETE 만 cover 로 한정 (mirror 호출은 외부 try block, fail-loud raise propagate)
  2. **Test isolation**: `unit/feature-0002-agent-core/tests/conftest.py` 신규 — sys.path 통합 + dummy env. test_dual_write_mirror.py 의 dual import path 제거
  3. **Caller actual call test** (Test 9): `_text_store_insert` + mock cursor + spy `_dual_write_kb.upsert_text` — caller integration 검증
  4. **silent log caplog verification** (Test 10): `caplog.set_level(WARNING, logger="agent_core.kb_backend")` + `kb_pg_mirror: connection failed` warning emit 확인
  5. **Latency baseline measurement deferral**: REPORT.md §4 risk log 0번 entry — M2-c 책임 명시 (production-like 환경 측정 + M3 process-level pool decision)
- Blocker (본 cycle 내 처리 완료):
  6. **Cross-DB audit explicit call**: ADR-0021 §Consequences 에 M2-c cycle 책임 명시 추가 — ActionCode `kb.write.mirror` INSERT + M4 cutover gate (f) 항목 PASS 필수
  7. **SLA 측정 도구 cycle 책임**: `bin/kb-dual-write-verify.sh --audit-sla` 본문 구현이 M2-c 산출. miss_rate ≤ 0.1% target.
- Nice-to-have (M2-c cycle 위임):
  - LC_COLLATE / IDENTITY `BY DEFAULT` 모드 명시 (M4)
  - `_BACKENDS_CACHE` thread-safe `threading.Lock()` (concurrency)
  - psycopg autocommit 정책 docstring (kb_backend.py)
  - `caplog` 외 추가 negative assertion (`_repair_from_fact()` idempotent N3)
  - MysqlKbBackend ↔ caller raw SQL drift 방지 (M3 refactor TODO)
- Decision authority: 본 cycle 의 method body + caller 수정 + 10 unit test + Critical/Blocker 반영은 §2.1 PLAN-APPROVED 마커 범위 (Major). 사용자 별도 confirm 불요 (사용자 메시지 "M2-b cycle 또한 진행" = 진행 의도 표명). M2-c 진입 게이트는 사용자가 `.env` 의 `AGENT_KB_PG_REQUIRED=1` + runtime 검증 통과 시점.

## REV-20260520-0007 [SUBAGENT:Plan-subagent — M2-a dual-write 준비 + 4 Blocker 해소]
- Date: 2026-05-21
- TASK-Cycle: TASK-0019 (M2-a dual-write 준비, **Major §12.3** — RBAC 동반)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 의 "권한 모델 변경 plan 은 Codex/subagent 외부 시각 항상 호출" 정책 적용. M1 의 NEEDS-TWEAK 4 Blocker 해소 + KbBackend ABC 의 single vs 4 sub-backend 분할 결정 + dual-write 정합 SLA design 의 검증.
- Verdict: **NEEDS-TWEAK** — KbBackend ABC + Blocker 4건 해소 + Postgres SQL 템플릿의 구조는 견고하나 (1) `_ensure_pg_schema()` 의 grants 검증이 USAGE on SCHEMA + sequence USAGE + TRUNCATE 명시 negative 누락 + (2) memory-init service 의 postgres race condition + (3) init_memory 의 광역 except 가 silent skip + (4) FUNCTION.md §10 갱신 누락 + Blocker (KB_DUAL_WRITE_START_TS .env / verify.sh --since default / REPORT.md risk log) 본 cycle 내 반영 필요.
- Section A (4 Blocker 해소 정합성) — **NEEDS-TWEAK**:
  - Blocker 1 (FULLTEXT → pg_trgm): 3 옵션 (pg_trgm `similarity()` / tsvector / pgvector embedding) + index 보강 + 한/영 mixed 분석 ✓. tsvector 의 `simple` config 옵션 미명시 (Nice-to-have).
  - Blocker 2 (`_ensure_pg_schema()` trigger): memory-init service 진입 선택 + 3-tier 처리 (silent skip / RuntimeError fail-loud / 광역 except graceful) ✓. **Critical**: 광역 except 의 `AGENT_KB_PG_REQUIRED` 환경 분기 필요 (M2-b 진입 시 fail-loud).
  - Blocker 3 (`has_table_privilege()`): role_exists + 4 table SELECT + RW mutate + VIEW SELECT ✓. **Critical**: USAGE on SCHEMA + sequence USAGE + TRUNCATE 명시 negative 누락.
  - Blocker 4 (ADR-0024): 별 database 결정 + 3 Alternatives 폐기 + Sprint 4 cycle 책임 명시 ✓.
- Section B (KbBackend ABC) — **PASS**:
  - 단일 ABC + 4 method group 분리 합리 ✓
  - method signature (kwargs 만, type hint 완전) ✓
  - partial failure 격리 책임이 caller (`_dual_write_kb()` wrapper) 위임 ✓
  - `set_text_embedding()` base default NotImplementedError 패턴 정합 ✓
  - `get_backends()` factory + circular import 회피 ✓
  - Postgres SQL 템플릿 (`_PG_UPSERT_*` ON CONFLICT + RETURNING id) 정합 ✓
- Section C (dual-write verify/stress) — **NEEDS-TWEAK**:
  - 4 mode 분리 ✓
  - **Blocker**: `--since` default 가 `.env` 의 `KB_DUAL_WRITE_START_TS` 자동 읽기 필요 (분모 noise 방지).
  - `verify_content_hash()` 의 cover 범위 (fact_entries 의 fact_fingerprint + 4 column 자연키 정합 미명시) 보강 권장 (Nice-to-have, M2-b 책임).
  - stress 의 `--ask-iterations 5` default 가 통계적 power 부족 — M2-b 진입 시 default 10 으로 조정 권장 (Nice-to-have).
- Section D (ANCHOR §3 invariant test catalog) — **PASS**:
  - 6 scenario + 2 negative assertion 매핑 정확 ✓
  - S5 의 "category 보존 NULL stay NULL" 결정 + `_PG_UPSERT_RAG_OBJECT` 의 COALESCE 패턴 정합 ✓
  - S6 multi-row priority 의 weight DESC, updated_at DESC, id DESC tie-breaker 정합 (M2-b 검증 권장)
  - fixture / assertion 책임 M2-b cycle 위임 명확 ✓
- Section E (잘못된 가정 / 누락) — **NEEDS-TWEAK**:
  - **Critical**: `memory-init.depends_on` 에 `postgres: service_healthy` 추가 필요 (race condition mitigation).
  - **Critical**: `init_memory()` 의 광역 except graceful skip 이 M2-b 진입 시 fail-loud 전환 정책 (`AGENT_KB_PG_REQUIRED=1` 환경 분기).
  - **Critical**: FUNCTION.md §10 의 init_memory 자동 호출 + grants_present + KbBackend ABC + invariant test catalog 갱신 누락 (verify-completion check #4 trigger).
  - **Blocker**: REPORT.md §4 risk log entry 7건 (audit SLA / FULLTEXT 비등가 / agent_drag 잔존 / depends_on required:false / except graceful / VIEW tie-breaker / psycopg autocommit) 추가 — M2-b 진입 게이트의 정본 기록.
  - `agent_drag` 의 실 결정은 Sprint 4 cycle 책임 — Blocker B-1 잔존, 본 cycle 안 진전 불가.
  - M2-b cycle 의 작업 분량 ~800-1000 LOC + integration test 1-2 일 — single cycle 으로 합당.
- Critical (본 cycle 내 처리 완료):
  1. `memory.py:_ensure_pg_schema()` 의 grants 검증 확장 — `has_schema_privilege('public', 'USAGE')` + `has_sequence_privilege('<tbl>_id_seq', 'USAGE')` + TRUNCATE 명시 negative 검증 ✓
  2. `docker-compose.yml:memory-init.depends_on` 에 `postgres: service_healthy` (`required: false`) 추가 ✓
  3. `agent_core.py:init_memory()` 의 `AGENT_KB_PG_REQUIRED` 환경 분기 (M0~M2-a optional / M2-b required) ✓
  4. `unit/feature-0002-agent-core/docs/FUNCTION.md §10` 갱신 (init_memory 자동 호출 + grants_present 필드 + KbBackend ABC + invariant test catalog) ✓
- Blocker (본 cycle 내 처리 완료):
  1. `.env.example` 에 `AGENT_KB_PG_REQUIRED` + `KB_DUAL_WRITE_START_TS` 2 변수 추가 ✓
  2. `bin/kb-dual-write-verify.sh --since` default 가 `.env` 의 `KB_DUAL_WRITE_START_TS` 자동 읽기 + 7-day fallback ✓
  3. `unit/feature-0002-agent-core/docs/REPORT.md §4` risk log 7건 추가 ✓
- Nice-to-have (M2-b cycle 책임):
  - LC_COLLATE 영향 검증 (M4 cutover gate EXPLAIN ANALYZE)
  - tsvector `simple` config 옵션 dialect notes 표 추가
  - `_PG_UPSERT_RAG_DOCUMENT` 의 GREATEST(weight) 의 MySQL 정합 확인
  - `get_backends()` 의 `functools.cache` singleton
  - stress 의 `--ask-iterations` default 10 으로
  - N3 (`_repair_from_fact()` idempotent) negative assertion 추가
  - psycopg autocommit 정책 docstring
- Decision authority: 본 cycle 의 ABC + Blocker 해소 + Critical/Blocker 반영은 §2.1 PLAN-APPROVED 마커 범위 안 (Major). 사용자 별도 confirm 불요 (사용자 메시지 "이어서 진행" = 진행 의도 표명). M2-b 진입 게이트는 사용자가 `.env` 의 `AGENT_KB_PG_REQUIRED=1` + `KB_DUAL_WRITE_START_TS` 명시 시점.

## REV-20260520-0006 [SKIPPED:renumber-only — ADR-0023 to ADR-0021]
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 fixup (ADR numbering 연속성)
- Decision: 본 cycle 1차 commit (`4bca163`) push 후 origin/main 의 ADR-0020 추가로 인한 numbering gap (0020 → 0023) 을 ADR-0021 로 연속화. text-level rename only — 의사결정 항목 / RBAC 모델 / schema 변경 / code semantic 변경 0건. Outside-voice 호출 불요로 판정.
- Outside-voice rationale: 의사결정 0건이라 외부 시각 호출 의미 없음. sed -i 의 mechanical rename + `git grep ADR-0023` 결과 0건 검증으로 충분.
- 참조: `CHG-20260520-0005` (fixup 의 상세 변경 목록).

## REV-20260520-0005 [SUBAGENT:Plan-subagent — M1 Postgres DDL + RBAC role 신설]
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 (M1 Postgres DDL + RBAC role, **Major §12.3** — 인증/인가 변경)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 의 "권한 모델 변경 plan 은 Codex/subagent 외부 시각 항상 호출" 정책 적용. ADR-0021 의 RBAC 재정의가 Critical 변경이라 본 cycle 의 핵심 검증 도구.
- Verdict: **NEEDS-TWEAK** — schema/DDL/role 의 구조는 견고하나 (1) ADR 의 정적 catalog blindspot 핵심 답 미흡 + (2) weak password literal fallback + (3) catalog 명명 일관성 + (4) Consequences 정량 SLA 부재 4 Critical 본 cycle 내 반영 필요.
- Section A (Postgres DDL dialect 정합성) — **대체로 정합, 미세 갭 2건**:
  - 컬럼 매핑 완전성 ✓ (4 테이블 모든 컬럼 + 6 인덱스 + 4 UNIQUE 정확 보존)
  - BIGINT → IDENTITY ✓, timestamp(3) → timestamptz + trigger ✓, decimal → numeric ✓, longtext → text ✓
  - **FULLTEXT → pg_trgm 의 의미 비등가** — MySQL `MATCH ... AGAINST` 의 자연어 토큰화 + BM25-like 와 pg_trgm 의 3-gram substring 검색 차이. application-측 query rewrite 정책이 M2~M4 사이 별 cycle 책임. 본 cycle 의 SQL 헤더 주석 또는 ADR 에 명시 권고.
  - LC_COLLATE default (docker image 의 `en_US.utf8` 가정) — 한글 정렬 byte order — Nice-to-have 명시.
- Section B (Role 권한 모델 + ADR-0021) — **견고, 단 정적 catalog blindspot 잔존**:
  - 2-layer hybrid 분리 합리 ✓ (connection-level + application-level)
  - agent_kb_rw/ro 권한 범위 정확 ✓ (TRUNCATE 제외 + ALTER DEFAULT PRIVILEGES 적용)
  - **`--apply-schema` 단독 호출 시 role 부재 → grant block silent skip risk** (Critical: ADR Consequences 에 명시 + bootstrap warning 추가)
  - **Cross-DB audit best-effort 의 SLA 부재** (Critical: ≤0.1% target 명시)
  - **`kb.write.any` 명명 일관성** — catalog 의 verb 패턴 (`audit.export` / `audit.purge`) 정합 안 됨 (Critical: `kb.mutate.any` 변경)
  - **`kb.read.own` enforcement 책임 위치 모호** — `ConversationId` 별 actor 결정 로직이 KB 측 아닌 web layer (Blocker — M2~M4 별 cycle 책임)
  - **Password rotation graceful degradation 부재** (Critical: `_pg_connect()` auth fail → backoff 3회 → mysql fallback / fail-loud 명시)
  - **정적 catalog blindspot** — 메모리 정책 핵심 — `WebPermissions IsDynamic=1` 패턴의 `kb.*` 적용 미명시 (Critical: ADR §후속 액션에 별 cycle 명시)
- Section C (Idempotency + 운영 안전성) — **안전, 운영 함정 1건**:
  - `_ensure_pg_schema()` 반복 호출 안전 ✓
  - ivfflat lists=100 + NULL embedding 의 자연 제외 (운영 함정: M3 backfill 진행 중 ANN recall 낮음 — M3 readiness gate 보강 권고)
  - `--all` 순서 (DB → roles → schema) 안전 ✓
  - **`has_table_privilege()` grant 검증 query 추가** (Blocker — M2 진입 전)
- Section D (누락 / 잘못된 가정) — **3건 식별**:
  - **schema 적용 시점의 "공백 상태"** — M2 진입까지 postgres 가 empty (Blocker: M2 plan 에 `_ensure_pg_schema()` 자동 호출 trigger 결정 명시)
  - **Connection pool 분리 정책** (M2 plan 책임)
  - **`agent_drag` namespace 격리 미명시** (Blocker → ADR-0024 후보, ADR-0021 §Consequences 에 명시 — Critical 항목으로 본 cycle 보강)
  - **VIEW 의 underlying table 권한 상속 부재** ✓ (agent_kb_ro 가 underlying SELECT 도 grant — 양호)
  - **`AGENT_KB_PG_RW_PASSWORD` default 'change_me_kb_rw' literal** (**Critical**: `.env.example` 에 변수 추가 + bootstrap fail-loud)
- Section E (ADR-0021 의 plan 정합) — **부분 정합, blindspot 핵심 항목 미답**:
  - §2.1.5 #1 storage 권한 매핑 → ADR Layer 1 ✓
  - §2.1.5 #2 의미 변화 → ADR Layer 2 ✓ (단 명명 일관성 issue)
  - §2.1.5 #3 정적 catalog blindspot → **부분 답** (Critical: dynamic grant 흐름 cycle 명시)
  - 후속 액션 cycle 분배 일부 명확 + 일부 누락 (Critical: dynamic grant cycle 위치 + ADR-0024 후보 명시)
- Critical (본 cycle 내 처리 완료):
  1. **`.env.example` 에 `AGENT_KB_PG_RW_PASSWORD` + `RO_PASSWORD` 추가** + bootstrap 의 `change_me_*` literal fail-loud (`AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1` 명시 confirm 필요) ✓
  2. **`kb.write.any` → `kb.mutate.any`** (catalog 명명 일관성, ADR text 수정) ✓
  3. **ADR §Consequences 보강**: cross-DB audit SLA ≤0.1% target + password rotation graceful degradation (backoff 3회 → fallback/fail-loud) + `--apply-schema` 단독 호출 시 grant skip warning ✓
  4. **ADR §후속 액션 보강**: dynamic grant blindspot cycle 위치 (M2~M4 사이) 명시 + ADR-0024 후보 (Sprint 4 통합) 명시 + `has_table_privilege()` 검증 query M2 책임 명시 ✓
- Blocker (M2 dual-write 진입 전 처리 필요):
  - FULLTEXT → pg_trgm application-측 query rewrite 정책 (또는 pg_trgm 충분성 검증)
  - `_ensure_pg_schema()` 자동 호출 trigger 결정 (startup? 첫 write 시? CLI?)
  - `has_table_privilege()` 검증 query 보강
  - `agent_drag` namespace 격리 ADR-0024 작성 (Sprint 4 통합 시점)
- Nice-to-have (후속 cycle):
  - LC_COLLATE / IDENTITY `BY DEFAULT` 모드 명시
  - M3 readiness gate 에 ivfflat NULL embedding 비율 게이트
  - connection pool 정책 명시 (M2 plan)
  - ADR-0021 의 "deprecated" → "신설 안 함" text 미세 수정
- Decision authority: 본 cycle 의 schema/DDL/role/ADR 결정은 §2.1 PLAN-APPROVED 마커 범위 안. 사용자 별도 confirm 불요 (사용자 메시지 "다음 Cycle 이어서 진행" = 진행 의도 표명). 다만 M2 진입 시 Blocker 4건 해소가 새 cycle 의 사전 조건.

## REV-20260520-0004 [SKIPPED:outside-voice-not-required — M0 인프라 도입 cycle]
- Date: 2026-05-20
- TASK-Cycle: TASK-0017 (M0 인프라 도입, Minor §12.3 — 비파괴 추가)
- Decision: §2.1 PLAN-APPROVED 의 M0 phase 실행 — `docker-compose.yml` 의 `postgres` 서비스 (standalone, pgvector/pgvector:pg16), `.env.example` 의 AGENT_KB_PG_* 17 변수, `requirements.txt` 의 psycopg+pgvector, `modules/{config,db}.py` 의 `_pg_connect()` helper + fail-soft import, `bin/kb-pg-healthcheck.sh` 신규, `bin/kb-measure-baseline.sh` 의 `--latency` mode 추가 (M-1 deferral 보완). 본 cycle 의 runtime 검증 (make start regression + postgres healthcheck + latency 5/5 측정) 은 별 turn 위임.
- Outside-voice rationale: 본 cycle 의 deliverable 은 비파괴 인프라 추가만이며 의사결정 항목 없음 (D-1/D-2/D-3 결정은 §2.1 PLAN-APPROVED 마커 부여 시점에 확정). RBAC catalog 변경 0건 (`agent_kb_rw`/`agent_kb_ro` role 신설은 M1 cycle 책임 — outside-voice Section D 권고대로 M1 에서 호출). 외부 시각 호출 불요로 판정 — `[SKIPPED:*]` entry 로 명시.
- 본 cycle 의 변경 영향 분석:
  - **docker-compose 의 startup ordering 영향 0** — postgres 서비스가 agent.depends_on 에 추가되지 않아 기존 agent boot 무영향 (outside-voice Section F-4 권고 정합). M2 dual-write 단계에서 agent.depends_on 에 추가될 때 healthcheck 가 healthy 까지 wait — 그 시점은 별 cycle 의 review.
  - **psycopg fail-soft import** — postgres 컨테이너 미가동 환경 (예: 사용자 .env 미설정) 에서도 agent 가 정상 boot. `_pg_available()` 가 graceful False 반환. M2 dual-write 진입 시 fail-loud 로 전환 — 그 시점에 별 cycle review.
  - **`.env.example` 17 변수** — §2.1.4 전체 (connection 6 + read backend + dual-write + embedding 5 + ANN 4). 값은 빈 string default — 사용자가 `.env` 에서 phase 별 점진 채움. M0 단계에서는 connection 6 만 필요, 나머지 11 변수는 M2~M4 에서 사용.
  - **`pgvector>=0.2.4`** — Python adapter (psycopg `register_vector()` 호출 시 사용). M1 schema 의 `vector(N)` 컬럼 INSERT 시점에 활용. M0 단계에서는 import 만, 사용 없음.
  - **kb-pg-healthcheck.sh 4 stage** — `--container` (docker ps + State.Health.Status) → `--connect` (docker exec psql SELECT 1) → `--extension` (pg_available_extensions → vector 존재 확인) → `--pg-connect` (agent 컨테이너에서 `_pg_connect()` smoke). 4 stage 가 M0 runtime 검증의 명시 게이트 (outside-voice Section F-4 권고 정합).
  - **kb-measure-baseline.sh --latency** — Blocker B-2 잔여 1/5 보완. 5 시나리오 × N 회 wall-clock 측정. `docker compose -f <main compose> -p repo run --rm agent "<question>"` 호출 패턴. default N=3 (`--latency-n 10` 권장 — M4 cutover gate baseline). 본 cycle 은 implementation 까지, 실 측정은 사용자 별 turn.
- Runtime 검증 deferral 사유:
  - main worktree 의 `chore/template-v3.9.0-upgrade` 작업이 in-progress (commit `f6836b4`) — docker compose state 가 본 ai/* worktree 의 변경 적용 안 됨. `make start` 재기동 시 main worktree 의 새 compose.yml 기반으로 진행 필요.
  - `.env` 의 AGENT_KB_PG_* 값을 사용자가 채워야 함 (특히 PASSWORD — 본 cycle 의 doc 에는 placeholder 만).
  - postgres `agent_kb` database 생성 + pgvector extension 활성화는 사용자 명시 동작 (예: `docker exec repo-postgres-1 psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector"`). M0 cycle 의 산출에는 이 명령 자동화 안 함 — M1 cycle 의 `_ensure_pg_schema()` 가 책임.
- 결정 영향 (후속 cycle):
  - **M1 cycle** — Postgres DDL + `agent_kb_rw`/`agent_kb_ro` role 신설 + `_ensure_pg_schema()` + ADR-0021 작성. Blocker B-1 (Sprint 4 schema 확인) M1 진입 전 사용자 직접 확인.
  - **M2 cycle** — `KbBackend` 추상화 + dual-write phase. `_dual_write_kb()` 래퍼 추가. agent.depends_on 에 postgres 추가 (그 시점에 startup ordering 변경).
  - **M3 cycle** — backfill ETL + embedding 일괄 생성 (Blocker B-4 의 `texts.embedding` schema 결정 적용). M-1 baseline 의 row count (FactEntries 774, Texts 798) 기준 embedding cost 추정 USD <0.01 — §12.1 confirm trigger 안전.
- 본 cycle 의 코드 mutation: db.py +60 LOC (`_pg_available` + `_pg_connect` + psycopg import), config.py +20 LOC (9 export + 9 변수 정의), docker-compose.yml +29 LOC (postgres 서비스 block), .env.example +28 LOC (17 변수 + 주석), requirements.txt +4 LOC (psycopg + pgvector + 주석), bin/kb-pg-healthcheck.sh 177 LOC 신규, bin/kb-measure-baseline.sh +75 LOC (--latency mode). Total: 신규 script 1 + 6 file modify, ~390 line 변경.
- Outside-voice 호출 시점 (앞으로):
  - **M1 cycle 진입 직전**: RBAC role 신설 + ADR-0021 작성 — Critical RBAC 변경이라 outside-voice 필수 (사용자 메모리 정책).
  - **M2 → M3 진입 직전**: dual-write 정합성 시나리오 + `KbBackend` 추상화 catalog — Major 변경.
  - **M3 → M4 진입 직전**: cutover readiness 게이트 — Critical.

## REV-20260520-0003 [SKIPPED:outside-voice-not-required — M-1 baseline 측정 cycle]
- Date: 2026-05-20
- TASK-Cycle: TASK-0016 (M-1 baseline 측정, Minor §12.3 — read-only)
- Decision: §2.1 PLAN-APPROVED 의 M-1 phase 실행 — `bin/kb-measure-baseline.sh` 신규 + 4/5 측정 + JSON artifact 저장. Latency (5/5) 는 docker compose project name 충돌 회피 위해 M0 cycle 로 defer.
- Outside-voice rationale: 본 cycle 의 deliverable 은 측정 + 데이터 수집만이며 의사결정 항목 없음 (TASK-0015 의 plan 결정은 이미 PLAN-APPROVED 마커 부여). RBAC 변경 / schema 변경 / 코드 변경 / 정책 변경 0건. §18.4 운영 (operational) 층위 + 사용자 메모리 `feedback_outside_voice_for_rbac.md` 의 "권한 모델 변경" 조건 비해당 (RBAC catalog audit 은 측정만, 변경 없음). 외부 시각 호출 불요로 판정 — verify-completion check #9 의 `[SKIPPED:*]` entry 로 명시.
- 측정 결과 sanity check (`artifacts/shared/kb-baseline-2026-05-20.json` 정본):
  - **Row count (a)**: FactEntries 774, Texts 798, RagDocuments 831, RagObjects 774, AgentMemoryFacts VIEW 774. 총 정본 ~3,177 row + VIEW 별도. 본 plan §2.1.0 의 "수천~수만" 가정 lower bound 확인. M3 backfill 의 embedding cost 추정 정합 — `texts.embedding` 798 row × `text-embedding-3-small` USD 0.02/1M tokens × 평균 500 tokens ≈ **USD 0.008** (예측 over-budget 의 1/12500). PLAN-APPROVED 의 "USD 100 시 별도 confirm" 임계는 안전 margin.
  - **EXPLAIN (b)**: Q1 (FactEntries `schema_insight:%`) range access via `IX_FactEntries_Conv_Key`. Q2 (RagDocuments) ref access via `UX_RagDocs_Conv_Scope_Key_Hash`. **Q3 / Q4 / Q5 (RagObjects + table_insight + category-filtered) ALL access** — full scan. KB row 수가 ~800 으로 작아 현재 latency 작으나 scale-up 시 pgvector ANN index (ivfflat / hnsw) 의 selectivity 이득 영역. M4 cutover gate 의 latency p99 +50% 임계 (Blocker B-6) 의 baseline 으로 활용.
  - **JOIN audit (c)**: 비-KB (Conversations / Messages / Steps) ↔ KB (FactEntries / Texts / RagDocuments / RagObjects / Facts) cross-table JOIN candidate 양방향 0건. **Open Question #9 ✓ 충족** — Postgres 분리 시 cross-DB JOIN 우려 없음. M0 의 docker-compose `postgres` 서비스 추가 + agent 컨테이너에서 dual connection (mysql + pgsql) 패턴이 자연 가능.
  - **RBAC catalog audit (d)**: `PERMISSION_DEFINITIONS` 총 40건 中 `kb.*` / `memory.*` / `agent_kb.*` = **0건**. outside-voice review Section D 정합 — KB 접근이 현재 RBAC catalog 외부 (connection-level: agent 컨테이너의 mysql_connector 가 root 권한으로 직접 접근). Postgres 분리 후 `agent_kb_rw` / `agent_kb_ro` role 신설 + ADR-0021 작성이 M1 cycle 의 명시 게이트 (Blocker B-8 / B-9).
  - **Latency (e)**: deferral. `latency.deferred_to = "M0"` JSON 필드 명시. M0 cycle 의 docker-compose 수정 시점에 `COMPOSE_PROJECT_NAME=repo` 강제 또는 `docker exec repo-web-1` 직접 호출 패턴 결정 + N=10 회 S1~S5 시나리오 측정.
- Blocker B-2 (M-1 baseline 측정 phase 추가) 의 부분 충족: 4/5 산출. 잔여 1/5 (latency) 는 M0 의 산출에 통합 — TASK.md §1.2 의 본 cycle plan 에 명시.
- 결정 영향: 본 측정 결과는 §2.1 의 phase M0~M5 모두에 영향. 특히:
  - **M3 embedding cost** 가 USD <0.01 추정 → §12.1 외부 비용 confirm trigger 안전 (USD 100 미만).
  - **M4 cutover latency 임계** baseline 확보 — `EXPLAIN_Q1~Q5` 의 query_cost 와 비교.
  - **M1 RBAC role 신설** 필수 확인 — kb.* = 0건 이라 catalog 추가 + connection-level enforcement 양쪽 필요.
- 결과 정본: `artifacts/shared/kb-baseline-2026-05-20.json` (git 추적 외 — `.gitignore` 적용). M4 cutover gate (`bin/kb-cutover-readiness.sh`) 가 본 JSON 의 EXPLAIN_Q1~Q5 cost + row count 와 cutover 후 측정값 비교.
- Next: M0 cycle (`ai/claude/0002/kb-pg-m0` 신규 worktree) — docker-compose `postgres` 서비스 추가 + `modules/db.py` 의 `_pg_connect()` helper + latency baseline 5/5 보완.

## REV-20260520-0002 [SUBAGENT:Plan-subagent — pgvector-migration-plan-review]
- Date: 2026-05-20
- TASK-Cycle: TASK-0015 (plan-review, Critical §12.3) — outside-voice review 결과 정본
- Outside-voice channel: Plan subagent (Software architect agent) — `feedback_outside_voice_for_rbac.md` 정책의 "Codex/subagent 외부 시각 항상 호출" 충족.
- Verdict: **NEEDS-TWEAK** — plan 골격 (6 phase 분해 + 3-D 결정 매트릭스 + ANCHOR §3 invariant 보존 의도 + RBAC 별 ADR 위임) 은 합리적이나 다수의 무검증 가정 + 검증 항목 누락 + 정량 baseline 부재로 PLAN-APPROVED 전 해소 필요.
- Section A (3-D 결정) — 보강 필요:
  - D-1 Sequencing 의 권장 default A 가 Sprint 4 schema unknown 위에 서 있음 (self-certification paradox) → 조건부 분기로 reclassify ("Sprint 4 schema 가 KB rag_objects 와 공유 → A 확정 / 별 namespace → C 검토").
  - D-2 Topology 의 메모리 footprint estimate 누락 (WSL2 + MySQL 8.0 공존 시 shared_buffers / ivfflat index 메모리 계산).
  - D-3 Module rewrite 의 dialect 변환 카탈로그 누락 (`ON DUPLICATE KEY UPDATE` / `INSERT IGNORE` / `TIMESTAMP(3) ON UPDATE` / `cursor.execute(multi=True)` 의 비대칭).
- Section B (Phase 분해) — 보강 필요:
  - M2 dual-write 의 fail rate 분모 정의 누락 (새 row 만 비교? ContentHash 일치 부분집합만?).
  - M2 1주일 wait 가 calendar comfort — synthetic load (강제 insight 3회 + ask 5회) 게이트 필요.
  - M3 backfill 의 idempotency 가 자연키 (Conv × Scope × FactKey × Fingerprint) 기반인지 SERIAL id 기반인지 미정의 + embedding API 부분 실패 시 resume 전략 미명시.
  - M3 의 embedding 저장 위치 schema 결정 부재 — `texts.embedding` (TextHash 별, 비용 최소) vs `fact_entries.embedding` (row 별, 비용 폭증) 결정 누락.
  - M4 cutover rollback window 3단계 (직후 / M5 진입 전 / M5 cleanup 후) 명시 누락.
  - M5 wait 2주일 동안의 active probe (`bin/kb-cutover-canary.sh`) 부재.
- Section C (ANCHOR §3 invariant) — 보강 필요:
  - `KbBackend` 추상화의 method signature catalog 미명시 — 단일 추상화가 아니라 4종 (`FactEntriesBackend` + `RagDocumentsBackend` + `RagObjectsBackend` + `TextsBackend`) 분할 가능성.
  - "fact 기반 복구 시나리오 1건" → 6종 카탈로그 (RagDocs 누락 / RagObjs 누락 / Texts 누락 / ScopeKey common 외 / RagObjs category stale / fact_entries 다중 row 우선순위).
  - transactional 약화 (cross-DB tx 불가) 명시 누락 — fact_entries 만 작성하고 rag_documents 가 빠지는 partial failure 의 정합 검증 미정의.
  - "repair_from_fact path 진입 시 LLM 호출 0건" negative assertion 누락.
- Section D (RBAC catalog) — Critical 보강 필요:
  - 현재 RBAC catalog (`unit/feature-0003-agent-web-ui/src/app.py:325~412` 의 `PERMISSION_DEFINITIONS`) 가 정적 tuple + 동적 row union 의 hybrid 패턴. 정적 catalog 의 blindspot 은 **정의 자체가 안 바뀌어도 enforcement path 가 바뀌는 것** — 본 plan 의 정확한 사례.
  - 현재 catalog 에 `kb.*` / `memory.*` 항목 0건 (grep 결과 확인) — KB 권한이 catalog 외부에 있음. Postgres 분리 후 connection pool 분리 → connection-level 권한이 새 enforcement layer.
  - `agent_kb_rw` / `agent_kb_ro` Postgres role 신설 = 인증/인가 변경 → M1 위험도 Minor → Major 격상 + 사람 승인 필수.
  - ADR-0021 (RBAC catalog 재정의) 작성 의무를 M4 cutover 전 게이트 항목에 명시 필요.
  - audit log 의 cross-DB tx 약화 명시 필요 (`WebAuditEvents` 는 MySQL 유지).
- Section E (Open Questions) — 보강 필요:
  - #4 embedding cost 추정: outside-voice 자체 추정 USD 0.01~0.5 (현재 row 수 추정 시). plan 의 "USD <100" estimate 는 over-budgeted, 그러나 **row 수 측정 자체를 plan 이 하지 않음**.
  - #6 ivfflat vs hnsw: KB row 수 ~수만 이하 → `ivfflat (lists=100, probes=10)` 충분. row 수 100K+ → `hnsw` 고려. 환경변수 toggle.
  - 신규 #9 (비-KB JOIN audit), #10 (VIEW 정의), #11 (embedding 모델 vendor lock-in), #12 (latency baseline 측정), #13 (EXPLAIN ANALYZE 검증) 추가 필요.
- Section F (잘못된 가정 / 누락) — Critical 보강 필요:
  - 5종 KB row count 정확 측정 (M0 이전 또는 M0 산출에 포함).
  - `make ask` 5종 시나리오의 latency p50/p99 baseline + EXPLAIN baseline.
  - M4 cutover gate 에 latency 정량 회귀 임계 (예: "p99 latency 증가 50% 이내").
  - `make ask` 5종 시나리오 구체 catalog (어떤 질문, 어떤 expected 답변) 명시.
  - 정책 doc 갱신 목록 보강: `docs/ARCHITECTURE.md`, `docs/LEARNINGS.md`, `unit/feature-0002-agent-core/docs/FUNCTION.md §10` (외부 의존성에 "Postgres 16 + pgvector extension" 추가).
  - dialect-specific 테스트 (`ON CONFLICT` 동작, `vector` 컬럼 INSERT, cosine similarity 결과) catalog.
- PLAN-APPROVED 전 해소 필수 (11 Blocker — 본 entry §2.1.11 에서 반영 추적):
  1. D-1 Sequencing 조건부 default (Sprint 4 schema 확인 분기).
  2. M0 이전 baseline 측정 phase 추가 (row count + latency + EXPLAIN + 비-KB JOIN audit).
  3. M2 검증 정합 정의 (fail rate 분모 + synthetic load).
  4. M3 embedding 저장 schema 결정 (`texts.embedding` 권장).
  5. M4 rollback window 3단계 명시.
  6. M4 latency 정량 임계.
  7. ANCHOR §3 invariant 시나리오 카탈로그 6종.
  8. RBAC role 신설 위험도 격상 (M1: Minor → Major + 사람 승인).
  9. ADR-0021 작성을 M4 cutover 전 게이트 명시.
  10. `make ask` 5종 시나리오 구체 catalog 명시.
  11. 정책 doc 갱신 목록 보강 (ARCHITECTURE / LEARNINGS / FUNCTION §10).
- Nice-to-have (별 ADR / 별 cycle):
  - D-3 dialect 변환 카탈로그
  - M5.5 post-cleanup canary 1주일
  - EXPLAIN ANALYZE 비교 자동화
  - embedding 모델 vendor lock-in fallback
  - transactional partial failure 정책
- 위 11 Blocker 가 `TASK.md §2.1` 본문 + `§2.1.11` 반영 표에 갱신되면 PLAN-APPROVED 진행 권장. 그 전에는 plan 의 "Execute 진입 조건" 이 self-certified 위에 서 있어 마커 부여 보류 권장.

## REV-20260520-0001
- Date: 2026-05-20
- TASK-Cycle: TASK-0015 (plan-review, Critical §12.3)
- Decision: KB 정본 5종 (`AgentMemoryFacts` view + `AgentMemoryFactEntries` + `AgentMemoryTexts` + `AgentMemoryRagDocuments` + `AgentMemoryRagObjects`) 의 정본 위치를 현재 MySQL (`agent_memory` DB) 에서 별도 Postgres pgvector 인스턴스 (`agent_kb` DB) 로 이전하는 multi-cycle plan 정본을 `TASK.md §2.1` 에 작성한다. 본 cycle 의 deliverable 은 plan 정본 + outside-voice review + 사용자 PLAN-APPROVED 마커까지이며, 실제 코드·schema·데이터 변경은 phase M0~M5 가 각각 별 cycle 로 진행한다.
- Trade-offs (3-D 결정 매트릭스 — `TASK.md §2.1.1` 참조):
  - **D-1 Sequencing**: 권장 default 는 A (선행 M0~M2 + M3~M5 와 Sprint 4 병행). Sprint 4 (D RAG, PGVector 도입) 와 pgvector 인프라 공유로 도입 비용 1회. Alternative B (병행 시작) 는 schema 충돌 + rollback 매트릭스 폭발로 비권장. Alternative C (후행 — Sprint 4 우선) 는 outside-voice review 가 Sprint 4 의 D RAG schema 가 KB 5종보다 단순하다고 판정 시 전환 가능.
  - **D-2 Topology**: 권장 default 는 A (단일 Postgres cluster + 별 database `agent_kb`). Sprint 4 의 D RAG 와 동일 인스턴스 공유. Alternative B (별 인스턴스) 는 운영 부담 2배로 본 plan 규모 대비 과대.
  - **D-3 Module rewrite**: 권장 default 는 A (raw psycopg3 + pgvector extension). 7,500+ LOC 의 raw SQL 패턴 보존 + dialect 변환만 수행. Alternative B (SQLAlchemy ORM 전환) 는 별 ADR + 별 cycle 로 분리 (마이그레이션 + ORM 도입 동시 진행은 risk 폭발).
- Risk:
  - **Critical (§12.3)** — 본 plan 의 Execute 단계 (M4 cutover, M5 cleanup) 는 롤백 어려운 마이그레이션 + DROP TABLE (파괴적 데이터 변경) 포함. 사람 승인 필수.
  - **외부 비용** — M3 backfill 의 embedding 호출 비용 (OpenAI `text-embedding-3-small`) 추정 USD <100. 초과 시 §12.1 별도 confirm.
  - **ANCHOR §3 invariant** — fact-우선 복구 흐름 (insight.py 의 `_check_artifact_completeness` + `_repair_from_fact`) 이 새 storage 에서도 보존되어야 한다. `KbBackend` 추상화 인터페이스 (M2 도입) 뒤에서 동일 동작 검증 필수. M2 / M4 의 검증 게이트에 명시 항목 포함.
  - **정책 doc 변경** — AGENTS.md §11.3·§14.1·§15.6·§15.7 갱신 동반. META path (§18.4) 이므로 phase 별 META mode commit 으로 분리.
  - **RBAC catalog blindspot** — 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정책에 따라 정적 catalog 의 dynamic grant blindspot 외부 검증 필수. `kb.read.any` / `kb.write.any` 의 storage 이전 후 재정의는 별 ADR (`ADR-0021` 후보) 로 분리.
- Alternatives 검토 후 폐기:
  - **MySQL FULLTEXT + LIKE 만으로 §15.6 §4) D0~D3 라우팅 구현 강화** — coverage 기반 검색은 LIKE 패턴 매칭으로는 의미 거리 표현 불가. embedding similarity 가 자연 대응. 폐기 사유: 검색 정확도 천장이 낮음.
  - **MySQL 8.0 의 `JSON_VALUE` + 자체 cosine similarity 함수 구현** — pure-MySQL 으로 vector similarity 시뮬레이션 가능하나 index 가 없어 full scan. 대규모 데이터에서 latency 폭발. 폐기.
  - **모든 KB 정본을 즉시 cutover (dual-write phase 생략)** — rollback path 없음. 폐기 (Critical risk 무대응).
- Outside-voice review 호출 사유 (사용자 명시 + 메모리 정책):
  - 사용자 메시지: "RBAC catalog 신설 가능성 (예: `kb.read.any`·`kb.write.any` 의 storage 이전 후 재정의) 과 정책 §11.3 변경 동반으로 Codex 또는 subagent outside-voice review 가 필수입니다."
  - 메모리 `feedback_outside_voice_for_rbac.md`: "권한 모델 변경 plan 은 Codex/subagent 외부 시각 항상 호출 (정적 catalog blindspot 대응)"
  - 호출 방식: 1차 Codex `/codex` consult — D-1/D-2/D-3 결정 + §2.1.5 RBAC 3개 항목 + §2.1.7 Open Questions 8개 검증.
  - 2차 (Codex 가 RBAC blindspot 발견 시): Plan subagent 호출 — dynamic grant 흐름 + RBAC catalog 재정의 검토.
- Decision authority: 본 plan 의 PLAN-APPROVED 마커는 **사용자** 가 부여한다 (§7.1 Critical 분기). AI 는 plan 작성 + outside-voice review 호출 + 사용자에게 plan 제시까지만 수행.
- Next-cycle plan: PLAN-APPROVED 후 M0 cycle (별 worktree `ai/claude/0002/kb-pg-m0`) → M1 → M2 → M3 → M4 (사람 confirm) → M5 (사람 confirm) 순서. 각 cycle 의 plan 은 `TASK.md §1.2` (cycle-specific) 에 별도 작성.

## REV-20260515-0003
- Date: 2026-05-15
- Decision: Account scope의 `ProductId IS NULL` 프롬프트도 Role scope 와 동일하게 fallback 이 아니라 항상 누적되는 공통 지침으로 해석한다. 전체 적용 순서는 `Product context → Role guidance → Account preferences → 현재 user message` 로 유지한다.
- Reason: 사용자가 의도한 구조는 Product, Role, Account, 요청이 순서대로 쌓이는 것이다. 기존 구현은 Product/Role/Account/user message 의 큰 순서는 맞았지만, Account Product 전용 프롬프트가 있으면 Account 공통 프롬프트가 누락될 수 있었다. 개인 기본 지침은 특정 Product 선택 이후에도 유지되어야 하므로 누적 방식이 맞다.
- Additional Fix: `_fetch()`가 특정 Product prompt 조회에서 miss 가 나면 공통 prompt 로 fallback 하던 동작은 Role/Account block 누적 구조에서는 중복 원인이 된다. 특정 Product 조회는 exact match 만 반환하고, 공통 조회는 별도 호출로 분리했다.
- Risk:
  - Account 공통 + Product 전용 개인 지침이 모두 있으면 prompt 길이가 증가한다. 하지만 개인 공통 지침 누락은 사용자 선호/제약 누락으로 이어져 더 위험하다.
  - 현재 사용자 요청은 system prompt 안에 복제하지 않고 마지막 `user` 메시지로 유지한다. 이는 대화형 LLM API의 역할 분리에 맞으며, 요청 원문 손상을 피한다.

## REV-20260515-0002
- Date: 2026-05-15
- Decision: Role scope의 `ProductId IS NULL` 프롬프트를 fallback 전용이 아니라 항상 누적되는 공통 지침으로 해석한다.
- Reason: 관리 콘솔의 Role detail 에서 "전 Product 공통"으로 입력한 지침은 특정 Product 선택 이후에도 역할 전체의 기본 행동 규칙으로 적용되어야 한다. 기존 구현은 Role×Product 프롬프트가 있으면 공통 지침을 버렸기 때문에 UI 문구와 런타임 의미가 어긋났다.
- Alternatives:
  - 기존 fallback 유지: 특정 Product별 세부 지침이 생기는 순간 Role 기본 지침이 사라져 사용자 의도와 불일치한다.
  - Product prompt에 Role 공통 내용을 복제: 중복 진실이 생기고 Role 변경 시 모든 Product prompt를 수정해야 하므로 거부.
- Risk:
  - Role 공통 지침이 길어지면 모든 pinned Product 대화의 시스템 프롬프트가 늘어난다. 다만 역할 지침은 운영 정책 성격이라 누락 비용이 중복 비용보다 크다.
  - account scope는 기존 우선순위/ fallback 의미를 유지했다. 이번 요청은 Role의 `전 Product 공통` 동작에 한정된다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: agent 이미지는 core feature Dockerfile에서 web-ui feature 소스를 함께 복사한다
- Reason: import 경로를 깨지 않으면서 기능 소유권을 분리하기 위함
- Risk: 이미지 빌드 경로가 루트 context에 의존한다

## REV-20260527-0003 [SUBAGENT:backend+qa — AR-M1 DDL+RBAC agent_runtime_schema.sql review]
- Date: 2026-05-27
- Cycle: TASK-0112 (AR-M1 DDL + RBAC)
- Subagent: backend+qa (§18.8 dispatch: schema, migration, foreign key → backend, qa)
- Verdict: PASS (no blockers)
- Absorbed: C1 (kv FK 의도적 생략 주석 명시화 — __global__ sentinel 로 인해 FK 적용 불가), C2 (meta_json text → jsonb), N5 (CREATE SCHEMA IF NOT EXISTS 방어 guard)
- Deferred: C3 n/a (MySQL AgentMemoryKv에 created_at 없음 확인), N1 (agent_kb_ro SEQUENCES — 현재 currval() 사용 사례 없음), N2 (product_mode varchar 확장 — MVP scope 외), N3 (steps (run_id, step_index) 복합 인덱스 — AR-M2 query pattern 확인 후 결정, ADR-0027 후속액션 명시), N4 (summary created_at — MVP scope 외)

## REV-20260527-0004 [SKIPPED:minor-abc-skeleton-no-caller-mutation-no-rbac]
- Date: 2026-05-27
- Cycle: TASK-0113 (AR-M2-a ABC + skeleton)
- Reason: 신규 파일 추가만 (runtime_backend.py + test_anchor_invariant_runtime.py). 기존 caller (memory.py / agent_core.py) 수정 0건. AGENT_RUNTIME_DUAL_WRITE 기본값 False — runtime write path 무변경. RBAC 변경 0건. outside-voice 불필요 조건 충족.

## REV-20260527-0005 [SKIPPED:pattern-match-sql-constants-already-reviewed]
- Date: 2026-05-27
- Cycle: AR-M4-read (CHG-20260527-AR-M4-read)
- Reason: read 메서드 10개 추가. SQL 상수는 기존 M4 절(lines 134~210)에 이미 정의·검토됨. 메서드 본체는 단순 `with conn.cursor() as cur: cur.execute(SQL_CONST, params); return cur.fetchall()` 패턴 — write 메서드와 동일 구조. RBAC 변경 0건. Caller (memory.py / agent_core.py) 수정 0건 (기존 PG guard가 None fallback으로 MySQL 경로 진입하던 것을 이제 정상 PG 경로로 처리). outside-voice 불필요 조건 충족.
- Risk: low — write 메서드 무변경. PG read 실패 시 기존 `_read_runtime_pg` except 가 None 반환 → caller 의 MySQL fallback 진행 (graceful degradation 보존).

## REV-20260527-0010 [SKIPPED:bug-fix-only-no-rbac-no-new-feature]
- Date: 2026-05-27
- Cycle: TASK-0120 (풀 테스트 + 버그 제거)
- Reason: 버그 수정 전용 cycle — RBAC 변경 0건, 새 기능 0건, 기존 테스트 명세 구현. 모든 수정은 기존 테스트(test_dual_write_mirror.py / test_anchor_invariant_runtime.py / test_dual_write_runtime.py / test_runtime_read_backend.py / test_kb_backfill.py / test_m5_cleanup.py)가 요구하는 동작을 채우는 것에 한정. outside-voice 불필요 조건 충족 (코드 mutation이 새로운 위험을 도입하지 않음).

## REV-20260527-0011 [SKIPPED:bug-fix-only-no-rbac-no-new-endpoint]
- Date: 2026-05-27
- Cycle: TASK-0121 (delete_conversation + ask_status 500 수정)
- Reason: PG routing 추가 전용 — 기존 동작을 MySQL 삭제된 테이블에서 PG로 이관. RBAC 변경 0건, 새 endpoint 0건, 새 기능 0건. `_pg_delete_conversation()` 은 기존 `delete_conversation()` 과 동일한 데이터를 PG에서 삭제. `_load_latest_assistant_message()` 는 동일 결과를 PG `agent_runtime.messages`에서 조회. outside-voice 불필요 조건 충족 (구조 변화 없는 backend migration).
- Risk: low — MySQL fallback try/except 유지. PG 실패 시 MySQL fallback(테이블 없어도 try/except로 silent fail). 기능 검증: ask_status 200 + delete_conversation 200 실서비스 확인.

## REV-20260609-0173 [SUBAGENT:preview-csv-value-match]
- Date: 2026-06-09
- Cycle: TASK-0174 ("전체 N행 미리보기" 링크 오정렬 수정)
- Panel: backend+QA adversarial subagent(general-purpose), diff 전수 + _distinctive_tokens 프로브.
- Verdict: 핵심 접근(값 토큰 overlap + consume-once + drop-on-no-match) sound, 회귀 테스트 유효. MAJOR 2건(동일 근본): ID/라벨 열 없는 측정값-only 대형 표는 토큰 추출 0 또는 LLM 재포맷으로 overlap 0 → backend 링크 소실(기존 동작 회귀)·JS 강제 거부 오탐.
- Resolution (FIX-FIRST): (1) backend 컬럼 수 일치 폴백 추가(_match_csv_for_table 2순위) — 측정값-only 표도 형태로 링크 복구, 형태 불일치 보조쿼리는 여전히 배제. (2) JS 가드 previewTokens≥2 임계 — 단일 토큰 우연 불일치 오탐 차단. MINOR(greedy 비전역최적)·NIT(날짜/전화 우연토큰)는 distinct-ID 우세로 실무 영향 낮음 — 수용.
- Risk: low — make test 컨테이너 PASS. 값/형태 모두 불일치 시 링크 생략 → 잘못된 링크 어느 경로로도 미부착.

## REV-20260609-0176 [SKIPPED:docs-only-cycle-closure]
- Date: 2026-06-09
- Cycle: TASK-0174 cycle closure (체크박스 완료 표기)
- Reason: 문서 한정 변경(TASK.md 체크박스 [ ]→[x]). 코드·RBAC·스키마·엔드포인트·시크릿 0건. 실질 수정은 이미 REV-20260609-0173(SUBAGENT 패널)에서 검토·배포됨. outside-voice 불필요 조건 충족.

## REV-20260615-0256 [SUBAGENT:ship]
- Date: 2026-06-15
- Cycle: TASK-0256 (SYSTEM_PROMPT diff 출력 지침), **Major §12.3** (라이브 global system prompt = 전 답변 영향).
- Trigger: 출력 포맷 변경 + 웹 렌더 동반 → outside-voice(general-purpose) 적대적 리뷰.
- Verdict: **SHIP** — 프롬프트 ```diff 예시 문자열 안전(py_compile PASS), OUTPUT 의 no-JSON/한국어 마크다운 규칙·ATTACHED FILES 섹션과 무충돌. diff 블록은 리뷰/편집 한정(신규 SQL=```sql)으로 과다사용 방지. test_compose_system_prompt 4 passed.
- Residual: 라이브 WebSystemPrompts global row 갱신(백업)·ask-worker 재배포 후 검증.
- Cross-ref: CHG-20260615-0256 / TASK-0256 / feature-0003 REV-20260615-0256.

## REV-20260615-0270 [SUBAGENT:ship]
- Date: 2026-06-15
- Cycle: TASK-0256e (첨부파일 diff 줄번호 추적 — 줄번호 주입 + 헌크 헤더 지시), **Minor §12.3** — agent-core 프롬프트 주입 1함수 + 지침 + 테스트. RBAC/스키마/엔드포인트/SQL추출/sandbox 0.
- Trigger: LLM 프롬프트(첨부 컨텍스트) 변경 → outside-voice(general-purpose) 적대적 리뷰.
- Verdict: **SHIP** (BLOCKER/MAJOR 0).
  - `_number_file_lines` edge-case 안전(splitlines 트레일링개행/\r\n/빈/단일/내부공백, 1-based off-by-one 0, 우측정렬 폭, 코드 본문 보존, U+2192 UTF-8 컴파일).
  - 부작용 0: 줄번호는 prompt 주입 사본에만(`_number_file_lines(content)` 호출부), 원본 content 는 length 측정 외 미사용. SQL추출(`_extract_sql_tables`=LLM tool sql)·sandbox(CSV/XLSX 별 분기)·image 무영향. 펜스 무결성 neutral-to-positive(`3→```` 는 column0 아님).
  - 계약 일치: 지침의 헌크 포맷 `@@ -<oldStart>,<oldCount> +<newStart>,<newCount> @@` 이 웹 렌더러 파서 regex(app.js)와 정확 일치 → gutter 가 실제 줄번호 seed. per-attachment 블록(`if text_content_entries`)에만 존재 → 채팅 붙여넣기 쿼리 과다-헌크 위험 차단 + "prefix 코드 미포함" 명시.
  - 토큰: 줄당 width+1자, 64KB/20파일 cap 내 marginal.
  - **MINOR #1 의도적 미적용**: SYSTEM_PROMPT `SHOWING CHANGES` 예시에 헌크 헤더 추가 제안 — 그러나 그 지침은 첨부+채팅붙여넣기 둘 다 적용되며 **채팅 붙여넣기는 실제 줄번호가 없어 헌크 헤더가 부적절(없는 번호 날조 유발)**. 줄번호가 있는 첨부에만 per-request instruction 으로 헌크 지시하는 현 설계가 정확 → 예시 미변경(live-row 동기화도 회피). MINOR #2(트레일링 개행 collapse) harmless.
- Residual: ask-worker 재배포 후 배포 프롬프트 줄번호 주입 확인 + (가능 시) 라이브 첨부 리뷰 e2e.
- Cross-ref: CHG-20260615-0256e / TASK-0256e / TASK-0256c(렌더 gutter) / feature-0003 REV-20260615-0267.

## REV-20260616-0291 [SUBAGENT:attachment-access]
- Date: 2026-06-16
- Cycle: TASK-0284 (첨부 3개 이슈), **Critical §12.3** — agent-core 측 변경(`_build_attachment_context_section` 주입 스코프 AccountId→ConversationId + 파일명 우선 포맷).
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] — 인가 경계(IDOR) 변경. feature-0003 REV-20260616-0291 의 적대적 보안 리뷰가 두 feature 변경(app.py + agent_core.py)을 동시 대조했다.
- Verdict: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 0, MINOR 1 — 흡수 지점은 feature-0003 app.py).
- agent-core 관련 confirmed-correct: `_build_attachment_context_section` 가 conversation_id 우선 스코프(PG `conversation_id = %s` / MySQL `ConversationId = %s`) + account 폴백, 둘 다 없으면 fail-closed("" 반환). `compose_system_prompt`/`_run_agent_core` 가 owned conv_id 를 전파(미게이트 호출자 0). 파일명 우선 포맷은 보안 무관.
- Verification: test_attachment_idor.py +4(conversation 스코프·account 폴백·파일명 우선) + make test 전체 회귀 0.
- Residual: ask-worker 재빌드(agent_core baked) — feature-0003 TASK-0284 와 함께 마감.
- Cross-ref: CHG-20260616-0291 / TASK-0284 / feature-0003 REV-20260616-0291(full).

## REV-20260616-0299 [SKIPPED:minor-config-timeout-no-security] — conn-tristate TCP timeout 2000→5000ms
- Date: 2026-06-16
- Cycle: TASK-0290 (CHG-20260616-0299), Minor §12.3 — 단일 config 파라미터(timeout 상향, 안전 방향).
- Trigger: 사용자 보고 — "관리 콘솔 > 데이터소스 의 mysql-mv-qa-* 버튼이 연결 안 됨처럼 보이나 실제론 ~1700ms 느린 연결이므로 빨강(불안정)이어야 한다" → 라이브 진단.
- 진단 근거(라이브 실측, repo-web-1, docker exec probe 재현):
  - 백엔드 classify 양호: mysql-mv-qa-* 3개 모두 TCP 193~195ms + DB 1749~1766ms → `classify`=**unstable**(빨강) 정확. HTTP `/api/admin/datasources` conn_status 도 현재 unstable. 즉 사용자가 본 회색은 web 재시작(07:47Z) 콜드 스타트 직후 thundering herd 의 일시 TCP timeout→down 오판이었고 이후 복구됨.
  - mysql-kr-an2-* 7개: 모니터 로그 `via=probe-tcp err=timeout` → fails=2 → down. HTTP conn_status elapsed=2003~2237ms(2000ms 임계 초과). 5s timeout 으로 직접 probe 해도 여전히 TCP timeout + DB errno=2003(MySQL 도달 불가) → **진짜 죽음, down 정확**(수정 대상 아님, 30s 로도 무의미).
- 결정: TCP 선검사 timeout 2000→5000ms. 콜드/원거리 RTT spike 흡수가 목적. 죽은 서버는 timeout 무관 즉답(ECONNREFUSED) 또는 5s timeout→down 으로 분류 정확도 보존.
- 대안 검토: 30s(사용자 1안) — 죽은 서버 7개가 워커 4개를 30s 점유 → 모니터 라운드 지연(다른 datasource status 갱신 밀림) + should_fast_fail down 판정 지연. 성능 이슈로 기각, 5s 채택(사용자 "성능 이슈면 5초" 정합).
- 리스크: 죽은 서버 down 확정이 2s→5s 지연(허용 — 모니터는 background daemon, 요청 경로 아님; down 은 backoff recheck 라 매 라운드 전수 probe 아님). flapping 무변(DOWN_AFTER_FAILS=2 유지). DB probe base(SLOW×3=3s)는 mv-qa 1749ms 충분 흡수 + DB 1회 fail 은 unstable(빨강)이라 회색 안 됨 → TCP timeout 만 상향으로 충분.
- Panel: SKIPPED — 보안/RBAC/스키마/인가경계 무관 단일 timeout 파라미터(안전 방향 상향). [[feedback_outside_voice_for_rbac]] 비해당.
- Residual: 배포 후 콜드 스타트 재현 검증(mv-qa unstable 유지, kr-an2 down).
- Cross-ref: CHG-20260616-0299 / TASK-0290 / TASK-0282(conn-tristate 도입 main 2e5778a).

## REV-20260616-0300 [SKIPPED:evidence-docs-only] — TASK-0290 라이브 검증 기록
- Date: 2026-06-16
- Cycle: TASK-0290 evidence(TEST.md append). 코드 무변경 docs-only.
- 결과: 배포 후 콜드 스타트 conn_status 실측 PASS — mv-qa unstable(빨강) 유지 + kr-an2 down(진짜 도달불가) 정확 + gz healthy. 구 2000ms down 오판 제거.
- Panel: SKIPPED — 검증 결과 기록만, 코드/보안/RBAC 무관.
- Cross-ref: CHG-20260616-0300 / REV-20260616-0299(본 변경 self-review) / TASK-0290.
