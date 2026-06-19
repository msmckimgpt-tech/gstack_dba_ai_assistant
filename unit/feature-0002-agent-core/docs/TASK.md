---
doc_type: TASK
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## TASK-0304 (current cycle) — 무거운 쿼리 사전 감지 → LLM 이 더 가벼운 쿼리로 재작성해 목적 달성 (Major §12.3, REQ-20260618-0304)
- 사용자 요청: "차단하기보다, LLM 이 무거운 쿼리를 미리 감지해 되도록 부하 적은 쿼리 구성으로 목적을 달성하도록 동작". (TASK-0299 SHOWPLAN 부하추정 활용 — gate=하드차단/warn=사후경고 둘 다 의도와 불일치.)
- 결정(AskUserQuestion): "가로채고 LLM 재작성" — 무거운 원본은 실행 전 가로채되 LLM 이 tool 루프에서 더 가벼운 쿼리로 재작성→목적 달성. 최종 사용자엔 차단 미노출(효율적 답변만).
- [x] (AC-0578) agent_core.py SYSTEM_PROMPT 에 "QUERY LOAD — STAY LIGHT" 섹션: ⓐ 처음부터 효율적 쿼리(필요 컬럼만·WHERE 한정·서버측 집계·표본 LIMIT/TOP) ⓑ 큰 조회 전 explain_query 자가확인 ⓒ 게이트가 무거운 쿼리 표시 시 confirm_heavy 강행 금지·더 가벼운 동등 쿼리로 재작성 ⓓ confirm_heavy=최후수단.
- [x] (AC-0578) tools.py gate 메시지 reframe: "차단" 톤 → "실행하지 않았습니다 + 더 가벼운 쿼리로 재구성해 다시 실행" 코칭(재작성 우선·confirm_heavy 후순위). execute_sql/confirm_heavy 도구 description 동반 정렬.
- [x] 테스트: `test_gate_message_coaches_rewrite_not_block`(재구성·실행안함·최후수단 단언) + 기존 게이트 토큰("무거운 쿼리"/"confirm_heavy=true") 보존 회귀 0.
- [ ] make test 컨테이너 회귀 0 + ruff.
- [ ] outside-voice 리뷰(프롬프트 회귀·게이트 의미) + verify-completion.
- [ ] 머지→배포 3이미지 + 라이브 WebSystemPrompts global row 갱신 + AGENT_QUERY_GUARD_MODE=gate 활성. CHG/REV-20260618-0318.

## TASK-20260617T100524-ai-claude-account-insight-kv-source (current cycle) — 인사이트 추출 소스 kv 보강 (Major §12.3, 보안경계 불변)
- 배포 준비 중 발견: 이 배포는 `agent_runtime.summary` 0행(요약 쓰기 cutover 결함)이나 `agent_runtime.kv` 에 origin_request(79)/thread_goal(79)/topic(99) 존재 → 추출 pass 가 summary 필수 JOIN 이라 후보 0건(기능 무동작).
- [x] `run_account_insight_pass` 후보 쿼리 `JOIN summary`→`LEFT JOIN summary`(필수 제거) + per-conv **summary+kv 합산 신호** 게이트(≥MIN_SUMMARY_LEN)·합산 fingerprint. summary 비어도 kv 신호로 동작. 보안 가드(G1~G4·allowlist·PII)·source_type(account_insight, 전역 미공유) 불변.
- [x] 테스트 +1(kv-only 추출 happy-path, summary 빈 대화→account_insight 저장 검증) = 15. py_compile + feature-0002 회귀 0.
- worktree `ai/claude/account-insight-kv-source`(base eb9f986). 후속: 배포 + 실제 대화 e2e 검증.
## TASK-20260617T095122-ai-claude-account-insight-complete (current cycle) — 계정 인사이트 회상 완성 B′ (Major §12.3, 보안경계)
- TASK-...082131(Phase 1 shadow) 의 완성. outside-voice 2-lens(보안+제품가치) 재검토 → **Phase 1 만으론 목표 미달**(회상 모집단=전역 DB 스키마 지식, summary 미임베딩, user_confirm PII) + BLOCKER 발견 → B′ 적용. 정본 [DESIGN-account-insight-recall.md](DESIGN-account-insight-recall.md) §10.
- [x] **BLOCKER-A**: `_build_knowledge_context` content→text 키(INJECT 무동작 버그) + 주입 블록 "참고 데이터, 지시 아님" 펜싱(프롬프트 인젝션 완화).
- [x] **account_insight 추출 pass**: insight worker `run_account_insight_pass` — owner·비-fork·비-archived 대화 summary+kv → `llm_account_insight`(PII-free 프롬프트) → `source_type=account_insight` fact(대화-로컬, 전역 미공유) → 기존 임베딩 파이프라인. fingerprint 재추출 회피. flag `AGENT_ACCOUNT_INSIGHT_EXTRACT`(OFF).
- [x] **회상 개선**: account_insight allowlist(G3 1차, user_confirm 제외) + `_mask_prose`(G3 2차) + **벡터-only fail-closed**(min_sim 척도 혼동 버그 수정, MIN_SIM 0.75→0.55) + G4(conv_id 집합 재검증) + per-account opt-out(`__account__:<id>` kv).
- [x] **G1 fork 배제**: `core_conversations.forked_from_conversation_id`(alembic 0010 + 부트스트랩 멱등 ALTER) + fork 시점 `_mark_conversation_forked`(app.py) + 추출·회상 양쪽 `IS NULL`.
- [x] 테스트 14(account 격리·G1 SQL·G3 allowlist·G4·벡터-only·opt-out·_mask_prose·추출 가드) + feature-0002 회귀 0(2 skip) + py_compile.
- [x] outside-voice 2-lens SHIP-WITH-FIXES 흡수(REV-20260617T095122).
- **활성화 canary**: EXTRACT→RECALL(shadow)→INJECT 순, 전부 default OFF. 부수 R4/R5 별도.
- worktree `ai/claude/account-insight-complete`(base fe8b8a4).

## TASK-20260617T082131-ai-claude-account-insight-recall (이전 cycle) — 계정 스코프 cross-conversation 인사이트 회상 Phase 1 shadow (Major §12.3, 보안경계)
- 사용자 요청: "새 대화를 시작하면 기존 대화에서 진행한 사용자 인사이트가 누락됨 → 세션 간 문맥/인사이트를 어렴풋이라도 이어받도록". (특정 명칭 기억이 아니라 문맥 영속화.)
- 설계 정본: [DESIGN-account-insight-recall.md](DESIGN-account-insight-recall.md). outside-voice 2명(보안 NOT-SHIP→가드 시 SHIP-WITH-FIXES / 정합성 SOUND-WITH-FIXES) 검증 완료.
- 근본: 회상 scope 가 `conversation_id = ANY({현재,워커샤드,__global__})` 뿐 → 계정 타 대화 배제. `core_conversations.owner_account_id`(idx 존재)로 account→conv_ids 도출해 기존 pgvector 회상에 주입하면 신규 테이블 0 으로 해결. 임베딩 1536/text-embedding-3-small, 동일 DB agent_kb cross-schema JOIN(ADR-0027 schema-qualified).
- **Phase 1 (본 cycle, shadow·flag default OFF)**:
  - [x] `modules/account_recall.py` — `_load_account_scoped_conv_ids`(G2: owner NOT NULL·archived 제외·현재대화 제외·`__global__` deny) + `recall_account_conv_facts`(기존 벡터 회상 재사용, shadow).
  - [x] `_build_knowledge_context` account_id/conversation_id optional 파라미터 + shadow 호출(default no-op, INJECT flag OFF). 호출부(run loop) 전파.
  - [x] config flags 5종 전부 default OFF (`AGENT_ACCOUNT_INSIGHT_RECALL/INJECT/MAX_CONVS/TOP_K/MIN_SIM`) + `__all__`.
  - [x] 단위 테스트 10 (계정 격리·owner NULL 제외·현재대화 제외·`__global__` 제외·account 무효·PG 미가용·flag OFF no-op·min_sim/top_k·exclude 전파). 로컬 pytest 10/10 + feature-0002 전체 회귀 0(2 skip) + py_compile.
  - [x] kb_backend.py stale 주석 정정(vector(1024) Titan v2 → 1536 text-embedding-3-small).
  - [x] outside-voice 2-lens(보안+정합성) SHIP-WITH-FIXES 흡수(REV-20260617T082131): 신규테이블 0 단순화·G1~G4 가드·dim 1536 정정.
- **INJECT 활성화는 본 cycle 범위 밖** — G1(fork 표식)·G3(PII 값-패턴 마스커) 완료 후 별 cycle. 부수발견 R4(`_mask_rows` 호출처 0건)·R5(convo_search 계정 스코핑) 별도 처리 후보.
- worktree `ai/claude/account-insight-recall`(base 3c6ba13).

## TASK-0299 (current cycle) — MSSQL 사전 부하추정 (SET SHOWPLAN_ALL) — MySQL EXPLAIN 등가 (Major §12.3, REQ-20260617-0299)
- 사용자 요청: "assistant 요청 시 datasource 가 MSSQL 일 경우 쿼리 실행 부하 조치를 어떻게 구성했는지" → MySQL 은 EXPLAIN 으로 부하 예측하는데 MSSQL 은 미구현(`supports_load_estimate=False`, gate=일괄 차단/warn·off=무방어)임을 확인 → "MSSQL 에서도 부하 추정으로 효율적 쿼리 작동" 구현 요청. DESIGN-multi-datasource §11 M-4 의 SHOWPLAN 후속(P6 이월분).
- 근본: MSSQL 은 EXPLAIN 구문이 없음 → `SET SHOWPLAN_ALL ON` 으로 본 쿼리를 실행하지 않고 추정 실행계획을 받아 예상 처리 행수 산출(MySQL EXPLAIN 등가).
- [x] (AC-0562) dialects.py: `MSSQLDialect.supports_load_estimate=True` + `_showplan` runner(ON→sql 미실행→`finally` OFF, 세션 poison 방지 Codex-7) + `estimate_load_rows`(EstimateRows×EstimateExecutions 최대) + `gate_fail_closed_on_estimate_error=True`(M-4). MySQL EXPLAIN 파싱은 dialect 로 이관만(골든 0).
- [x] (AC-0562) tools.py: `_estimate_explain_rows` 엔진무관 wrapper(dialect 에 실행 콜백 주입, 계층 보존) + 게이트 `must_estimate` 재구조화 — 추정 실패 fail-closed 는 confirm_heavy 무관(Codex-6), 추정 성공 known-heavy 만 confirm override.
- [x] (AC-0563) tools.py `_tool_explain_query` MSSQL SHOWPLAN plan 요약 표시(`_format_mssql_showplan`) + 도구 description/프롬프트 엔진중립화.
- [x] (AC-0563) `bin/datasource-mssql-ro-bootstrap{,-multidb}.sql` 에 `GRANT SHOWPLAN`(데이터 비노출·추정 plan 만 → 최소권한 RO 양립) + 검증 라인.
- [x] 테스트: 신규 `test_mssql_load_estimate.py` 19 + 골든 `test_query_guard.py` 16 회귀 0 + 기존 `test_mssql_security_boundary.py`/`test_multi_datasource.py` 계약·golden 갱신. 로컬 PYTHONPATH 전 스위트 PASS(2 skip).
- [ ] make test 컨테이너 회귀 0 + ruff clean.
- [ ] outside-voice 적대 코드리뷰(세션 poison/fail-closed 우회/cross-engine 격리) 흡수.
- [ ] 머지(PR) → agent-core 3 이미지(web/ask-worker/insight-worker) 재배포. CHG/REV-20260617-0310.

## TASK-0289 (current cycle) — 수행시간 end-to-end 집계 + 내부 동작(activity) step + 큐 대기 단축 (feature-0003 TASK-0289 의 agent-core 면, Major §12.3)
- 사용자 보고(feature-0003 TASK-0289): 실측 45초인데 화면엔 25초 표시(내부 동작 집계 숨겨짐) + 내부 동작(단계별 DB동작 외) 미표현. agent-core 가 수행시간 측정·step 기록의 근원.
- 근본원인: 표시 `duration_ms` 가 `run_start`(모든 초기화 이후) 기준 → LLM 루프만 집계. step 은 tool 호출만 기록(activity 없음). worker 큐 유휴 폴링 tick 1~2s.
- [x] (P1) `_compute_duration_breakdown(queued_ms, agent_entry_perf, run_start, now_perf)` → `{queued/init/inference/total}`. `_run_agent_core` 진입 `agent_entry_perf` + `queued_ms_seed` 파라미터(run_agent→_run_agent_core 전파). 표시·KV·meta `duration_ms`=total, meta `duration_breakdown` 동봉.
- [x] (P1) worker(`modules/ask.py`)가 `ask_jobs.claim_ask_job` created_at(RETURNING 추가, len-guard)로 큐 대기 산출 → `queued_ms_seed`.
- [x] (P2) `_emit_activity` nested helper(맥락 로드/분석 준비/추론 라운드/결과 정리) `action='activity'`·`tool=''` step + `emit_index` 통합 step_index(tool step 도 emit_index 사용). `_writes_allowed`/예외 안전 skip.
- [x] (P4) `AGENT_ASK_WORKER_IDLE_POLL_SEC`(float, 0.5) 유휴 claim 폴링 분리 — `tick_sec`(reconnect) 불변.
- [x] 테스트: test_duration_breakdown.py 3 + test_ask_jobs.py created_at 2 + feature-0002 전체 회귀 0(2 skip) + py_compile.
- [x] outside-voice 적대 코드리뷰 흡수(REV-20260616-0302) — **SHIP(BLOCKER 0)**: emit_index 정합·TASK-0241 clobber 불변·queued_ms tz-safe(timestamptz)·_emit_activity 안전·activity 헬퍼 격리 전부 confirmed.
- [x] 머지(PR #288 → main 4178cf7) → ask-worker 재빌드(agent_core baked, repo-ask-worker-1 Up + `_compute_duration_breakdown`/`IDLE_POLL=0.5` 실측) → feature-0003 TASK-0289 PB-0008 PASS 와 함께 마감. CHG/REV-20260616-0302.

## 0. TASK-0255 (current cycle) — insight 연결 탄력성 (R1 로그 edge-trigger / R2 PG datasource_health / R3 control-plane bounded timeout)
- [x] **조사**: 급성 병목(연결대기 starvation)은 TASK-0247/0250 으로 이미 해소 — 라이브 실측 cycle ~2.6s(불안정 DS 7개+에도 fast-fail). 잔존 3건 발견.
- [x] **R1**: scan_failed 로그 edge-trigger(`_LAST_DS_SCAN_STATUS` + `_ds_scan_status_changed`, registry 동기 prune) — 상태 전이 시에만 WARNING(매-cycle 도배 ~20만 줄/2일 제거). `DatasourceCircuitOpen` 을 `_is_perm` 보다 먼저 분기.
- [x] **R2**: `agent_runtime.datasource_health` PG 영속(alembic `0006` + 부트스트랩 §6c + **명시 GRANT**) + `_persist_datasource_health`(soft, registry prune) + web `admin_list_datasources` `insight_health` 첨부 + admin.js "인사이트 스캔 상태" 행 → **연결불안정 vs 권한실패 구분**. 자격증명 비영속.
- [x] **R3**: control-plane bounded connect timeout(`AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC`=10, `_controlplane_connect_timeout` — MySQL control-plane(db.py) + KB PG(_pg_connect/_ro)). breaker 미적용(timeout 만). R3a cold-window 미채택.
- [x] 테스트 19개(`test_task0255_*`) + `make test` GREEN(ruff pass); **5-lens adversarial review SHIP_WITH_FIXES** — BLOCKER 5건 환각 기각, M-2(자격증명 로그)·M-1(메모리 prune)·MINOR 반영.
- [x] main 머지(PR #208, `a410986`) → agent/insight-worker/ask-worker/web 재배포 + PG 마이그 `0006`(superuser GRANT) → **런타임 검증 PASS**: 로그 도배 멈춤(24초 7→7), datasource_health 8행(불안정7 `circuit_open`/정상1 `ok`), 자격증명 컬럼 0, `_controlplane_connect_timeout()=10` baked, heartbeat status=ok ~2.67s. **PB-0008 PASS**(불안정/정상 "인사이트 스캔 상태" 구분 실증, feature-0003 TEST.md §4).

## 1. Current Status
- State: **TASK-0250 (연결 health 모니터 — background 사전판정으로 불안정 datasource 격리 완성) 구현 완료, 리뷰·배포 진행** — 신규 `modules/conn_health.py` 가 2단 probe(TCP 선검사+실제 DB connect+SELECT 1)로 per-datasource 연결 상태를 미리 유지, agent(`connect_with_retry` gate)·관리콘솔(사전계산 conn_status)이 즉시 읽어 한 datasource 불안정이 정상 datasource 요청을 막지 않음. 구 TASK-0247 in-process breaker 흡수·대체 (cycle: TASK-0250)
- State(이전): **TASK-0247 (데이터플레인 연결 격리 — bounded connect timeout + in-process breaker) 완료** [TASK-0250 으로 진화·대체]
- State(이전): **TASK-0230 (멀티 datasource 1:N — 제품 1개 ↔ 여러 datasource 참조) 완료** — 제품이 여러 datasource 에 바인딩될 수 있고, assistant 가 한 질문에서 tool 의 `datasource` 인자로 대상을 골라 datasource 별 (연결·allowlist·dialect) 격리 컨텍스트로 조회한다 + 제품 프롬프트 자동작성이 모든 바인딩 datasource 의 DB 를 인지 (cycle: TASK-0230)
- Owner: AI (본 cycle: agent_core `conn_health.py`(신규)/`db.py`(gate)/`config.py`/`datasources.py`/`ask.py`/`insight.py` + feature-0003 admin 표시)
- Priority: high
- Last Updated: 2026-06-16

## 1.1 Current Cycle
- [x] TASK-0290 (Minor §12.3 — conn-tristate TCP 선검사 timeout 2000→5000ms). 사용자 보고: "관리 콘솔 > 데이터소스 의 mysql-mv-qa-* 버튼이 연결 안 됨처럼 보이나 실제론 ~1700ms 느린 연결 → 빨강(불안정)으로 표시되어야". **라이브 진단(repo-web-1, docker exec probe 재현 + HTTP conn_status)**: 백엔드 classify 양호 — mv-qa 3개 TCP 193~195ms + DB 1749~1766ms → `classify`=unstable(빨강) 정확, 현재 HTTP `/api/admin/datasources` conn_status 도 unstable. 사용자가 본 회색은 **web 재시작 콜드 스타트(07:47Z) thundering herd 의 일시 TCP timeout→down 오판**(이후 복구). mysql-kr-an2-* 7개는 TCP 2003~2237ms(2000ms 임계 초과)→down 이며 5s 로도 timeout+DB errno=2003=**진짜 도달불가**(down 정확, 수정 대상 아님). **산출**: config.py `AGENT_CONN_TCP_TIMEOUT_MS` 기본 2000→5000 — 콜드/원거리 RTT spike 흡수해 연결 가능한 느린 서버를 unstable(빨강) 유지, 죽은 서버는 timeout 무관/5s timeout→down 정확. 30s 는 죽은서버 7개×워커4 점유로 모니터 라운드 지연(성능이슈) 기각, 5s 채택(사용자 "성능 이슈면 5초"). REV-20260616-0299 [SELF] Panel SKIPPED(보안/RBAC 무관 timeout 상향). 배포 web+ask-worker+insight-worker 재빌드(config = agent-core 3 이미지 baked). worktree `ai/claude/conn-tcp-timeout`.
  - [x] 배포·라이브 검증 PASS — 콜드 스타트(컨테이너 재시작) 후 HTTP conn_status: mysql-mv-qa-* **unstable**(빨강, 1744~1793ms)/mysql-kr-an2-* **down**(5s timeout errno=2003 진짜 도달불가, 정확)/gz-qa-kr healthy. 구 2000ms 의 콜드 down 오판 제거 실증(TEST.md TASK-0290, CHG-20260616-0300).
- [x] TASK-0250 (REQ-20260612-0250, **Major §12.3** — 연결 health 모니터: 불안정 datasource 격리를 background 사전판정으로 완성). 사용자 후속 보고(TASK-0247 배포 후에도 "한 연결 실패 시 정상도 대기") + 설계 제안(queue·timeout 100ms→×2→10s). **진단**: breaker 가 3 요청 실패 후 open(그 전 각 요청 10s×retry 점유) + 관리콘솔 연결확인이 `probe_datasource` 직접(breaker 미적용)+4-cap 세마포어+8s. **사용자 확정(AskUserQuestion 2회)**: 둘 다 적용 + 구조 AI 검토 → **Connection Health Monitor**(상태만, warm 연결 X). **산출**: ① `conn_health.py` background 모니터(daemon scheduler+worker pool+queue) **2단 probe**(TCP 100ms 선검사 + 실제 DB connect+SELECT 1 적응형 1s→10s), 성공 healthy/실패 unstable backoff. ② `connect_with_retry` 가 `should_fast_fail` gate + `record_foreground_result` 피드백(복구는 background → half-open trial 불요). ③ 관리콘솔 `admin_list_datasources` 사전계산 `conn_status` + admin.js 세마포어 lazy probe 폐기→즉시 표시. ④ ask-worker/web/insight-worker 각자 모니터 기동. 구 breaker 흡수(db.py 내부 제거, dead config 정리). **outside-voice 2-pass NOT-SHIP→SHIP-WITH-FIXES**(REV-20260612-0250: B1 TCP≠DB→2단 probe·B2·M1 dead config·M2 pool 기아·M3 SSRF rebinding[`_is_blocked_target`]·m1/m2/m3 흡수). **검증**: 신규 `test_conn_health.py` 21 PASS + make test 컨테이너 회귀 0 + ruff clean. flag `AGENT_CONN_HEALTH_ENABLED` 기본 ON. ANCHOR §1~§3 충돌 없음. worktree `ai/claude/conn-health-monitor`. 동시세션 0248·0249 선점→§13.1 재번호 0250.
- [x] TASK-0247 (REQ-20260612-0247, **Major §12.3** — 데이터소스 연결 불안정의 blast radius 를 각 연결별로 격리). 사용자 보고: "관리 콘솔에서 데이터소스 연결이 하나라도 불안정하면 제품 화면에서 나머지 정상 연결까지 결과가 느림 → 연결 이슈 범위를 각 연결별로 격리". **근본 원인**: data-plane 연결의 `connection_timeout`(MySQL)/`login_timeout`(MSSQL)이 쿼리 예산 `AGENT_TIMEOUT_SEC`(운영 300s)를 재사용 → 불안정 연결 1회 시도가 최대 300s 블록 + `connect_with_retry`×3 → ~900s. 운영 `AGENT_ASK_EXECUTION_MODE=worker` + 단일 ask-worker 직렬 처리 → 불안정 datasource 바인딩 job 1건이 worker 를 점유 → 정상 datasource 제품 job 큐 대기. **산출(db.py + config.py)**: ① `AGENT_DB_CONNECT_TIMEOUT_SEC`(기본 10s, `_dataplane_connect_timeout()`)로 연결 수립 상한을 쿼리 예산에서 분리(MySQL `connection_timeout`·MSSQL `login_timeout`; MSSQL 쿼리 `timeout` 은 `AGENT_TIMEOUT_SEC` 유지). control-plane(`datasource=None`) 미적용. ② per-datasource circuit breaker — `scope_key`(엔진+host+port) 기준 in-memory(`_BREAKER_STATE`+`threading.Lock`). **게이트(`_breaker_admit`)·실패기록을 `connect_with_retry` 경계에서 요청당 1회**(모든 런타임 datasource 연결이 이 경유 — false-open 증폭 차단, THRESHOLD=실패한 요청 수). 연속 `AGENT_DB_BREAKER_FAIL_THRESHOLD`(3) 회 **연결 수립 실패**(`_is_connect_breaker_failure` — connect-stage 만, deadlock 1205·인증 1045 제외) → open → `AGENT_DB_BREAKER_COOLDOWN_SEC`(30s) 동안 `DatasourceCircuitOpen` 즉시 raise(실제 connect 미호출). 쿨다운 후 **정확히 1개** half-open trial(`half_open_at` 토큰, 락 내 단일성·stale 회수) 성공 close/실패 re-open/비-연결실패 토큰해제. ③ `connect_with_retry` admit raise 로 breaker-open 재시도 0. 부기는 `_breaker_safe` 격리. tool 경로(`execute_tool`)는 기존 `conn_for` try/except 로 per-datasource 에러 surface(타 datasource 무영향). **outside-voice 2-pass 적대 리뷰 NOT-SHIP→흡수→SHIP-WITH-FIXES**(REV-20260612-0247: B1 thundering herd·B2 stuck-open·M1 retry 증폭·M4 분류오염·m1 누수·m2 노출·잔여 흡수). **검증**: 신규 `test_db_circuit_breaker.py` **22**(8스레드 단일trial 동시성 포함) + **make test 컨테이너 회귀 0** + ruff clean. 사용자 확정(AskUserQuestion): Breaker + timeout 분리. flag `AGENT_DB_BREAKER_ENABLED` 기본 ON. ANCHOR §1~§3 충돌 없음(런타임 신뢰성 개선·모듈 경계 무변경). worktree `ai/claude/ds-connect-isolation`(base f9d8207). 동시세션 `task0244-ds-picker-status` 가 TASK-0244 선점 → §13.1 재번호 0244→0247 (동시세션이 0244·0245·0246 선점).
- [x] TASK-0230 (REQ-20260611-0230, **Critical §12.3** — 멀티 datasource 1:N: 제품 ↔ 여러 datasource 참조 [cross-feature, agent-core 측]). 사용자 요청: "assistant 가 답변하려면 여러 데이터소스·DB 에 접근해야 하는데 단일 datasource 만 가능 → 관리 콘솔 > 제품 > 데이터소스에서 여러 데이터소스도 참조하도록". 기존 멀티 datasource(TASK-0185~0226)는 product↔datasource **1:1**(WebProducts.DatasourceKey 단일 컬럼)이었다. **agent-core 산출**: ① `agent_core._resolve_product_datasources`(복수) — ≥2 바인딩 시 datasource 별 dict(`_label`/`_allow_schemas`/`_is_primary`) 반환, 0~1 은 [](기존 `_resolve_product_datasource` 단일 경로 보존=동작 0 변경). `_product_datasource_keys`(join 우선·primary 폴백), `_datasource_allow_schemas`(차원 격리, **fail-closed** — 차원 컬럼 부재 시 [] 반환해 전체목록 broadcast 교차노출 차단, REV-0230 MAJOR-2). ② `tools.py` `_DatasourceRouter` — run-scoped 라벨→{ds, lazy conn} 맵 + `activate(label)` 이 그 datasource 의 allowlist·engine·default_db ContextVar 를 **단일 단위로** 활성화(보안 게이트 기준). `execute_tool` 이 tool 인자 `datasource` 로 대상 선택→`conn_for`+`activate` **동일 라벨 lockstep**(연결↔allowlist 불일치 창 없음)→handler→primary 복원. 미바인딩 라벨 거부. `build_tool_definitions_for_datasources`(각 도구에 datasource enum 주입, 원본 불변 깊은복사). `set/get/reset_active_ds_router`(ContextVar, finally reset). ③ run-loop 통합 — ≥2 면 라우터 등록 + 다중연결 lazy(primary 즉시) + grounding 에 "ACCESSIBLE DATASOURCES"(라벨·엔진·접근DB, 좌표/비번 비노출) 주입(사용자 요청: 어시스턴트가 접근 가능 datasource DB 인지) + finally `close_all`+reset. ④ `insight.py` `_discover_mssql_databases` — datasource 차원(WebProductDatabases.DatasourceKey) 우선 + primary/join 바인딩 union 폴백. **검증**: 신규 `test_product_multi_datasource.py` 15(라우터 격리·lockstep·fail-closed·enum 주입·단일경로 무변경) + feature-0003 `test_product_multi_datasource_api.py` 7 + make test 컨테이너 **회귀 0**(F/E 0) + ruff clean. **outside-voice 적대적 보안 리뷰(REV-20260611-0230) BLOCKER 0** — 핵심 격리 HOLD(연결·allowlist·engine 단일 라벨 활성·tool 순차·게이트는 항상 활성 datasource 것). MAJOR-1(migration loud+검증)·MAJOR-2(allow_schemas fail-closed)·MAJOR-3(resolve 실패 silent 강등 금지) 흡수. flag `AGENT_MULTI_DATASOURCE_ENABLED` OFF + 단일 바인딩 = 동작 0 변경. worktree `ai/claude/product-multi-datasource`(base e93b181). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0226 (REQ-20260611-0226, **Major §12.3** — MSSQL insight-worker per-DB 스캔 커버리지: 권한 이슈로 탐색 불가한 DB 해소 + 가시화). 사용자 요청: "제품에서 선택된 `접근 가능 데이터베이스` 를 대상으로 스캔하되, 각 DB 연결 중 권한 이슈로 탐색이 불가능한 부분을 해소". **근본 원인**: insight-worker 는 [`_discover_mssql_databases`](../src/modules/insight.py)로 datasource 에 바인딩된 제품들의 접근가능 DB(`WebProductDatabases`) union 을 올바르게 발견하지만, 그 각 DB 로 `connect_with_retry(database=db)` 재연결 시 RO 로그인이 **단일 DB 에만** USER/GRANT 돼 있으면(기존 `bin/datasource-mssql-ro-bootstrap.sql` 은 단일 `TARGET_DB` 템플릿) 'Login failed'(18456)/'Cannot open database'(916) 로 막혀 `run_insight_cycle` 의 per-DB `except` 가 **조용히 skip** → 등록 DB 중 일부만 인사이트 생성되고 운영자에게 누락이 안 보였다. **산출**: ① `modules/insight.py` — `scan_report` 에 `db_targets`(발견 DB 수)/`db_failed`(연결·스캔 실패 수) 누적 + per-DB `except` 에서 권한거부 패턴(login failed/cannot open database/permission/denied/18456/916/229/297) 감지 시 진단 힌트(부트스트랩 SQL 재실행 안내) 로깅 + `db_failed>0` 면 status='degraded'(publish_failed 와 동일 가시화 정책) + heartbeat KV(`insight_worker_last_db_targets`/`_db_failed`) + payload 노출. ② `bin/datasource-mssql-ro-bootstrap-multidb.sql` 신규 — 한 공유 RO 로그인을 제품 접근가능 DB **전체**에 USER+db_datareader 멱등 부트스트랩(커서 순회, QUOTENAME 인젝션 차단, 시스템 DB 제외, 쓰기역할 제거 hardening, 0단계 서버 전역 prereq 검증). 기존 단일-DB 스키마 GRANT-only 템플릿과 **상호 배타**(보안 trade-off 사용자 명시 승인 — schema 격리 대신 DB 단위 db_datareader). ③ 발견 로직·런타임 allowlist(tools.py 3-part catalog 대조)는 **이미 데이터소스/제품 접근가능 DB 기준**이라 변경 불요(확인). **검증**: pytest 신규 `test_mssql_perdb_coverage.py` 8 + 관련 회귀(three_tier/degraded_backoff/security_boundary/multi_datasource) 131 PASS, 회귀 0 + py_compile. **MySQL 단일 datasource(db_targets=0) 동작 0 변경.** worktree `ai/claude/mssql-perdb-grant-coverage`(base 14334ab). ANCHOR §1~§3 충돌 없음(LLM 재생성 순서 무관 — 발견 커버리지·권한·가시화만).
- [x] TASK-0223 (REQ-20260611-0223, **Major §12.3** — MSSQL database-aware 3계층 insight + 제품 프롬프트 자동작성 실데이터 정합 [feature-0003 주관, agent-core 교차변경]). MSSQL 은 database.schema.table 3계층인데 insight-worker 가 `dbo` 단일 DB 만 스캔 + fact_key 에 database 누락 → 제품 등록 DB(`dk_data_release` 등)와 매칭 불가였다. **agent-core 산출**: ① `config.py` `_ACTIVE_DATABASE` ContextVar + `set_active_database`/`get_active_database` + `ds_object_suffix`(active database 있으면 3계층 `{db}.{schema}.{table}`, 없으면 2계층 — `ds_fact_key` 시그니처 불변=write·read-back·grounding 3자 정합 보존; set_active_datasource 가 datasource 전환 시 database 리셋). ② `insight.py` MSSQL multi-database 스캔(`_discover_mssql_databases` 제품 등록 DB 기반, DB별 `connect_with_retry(database=db)` 재연결 + `set_active_database`, 권한밖 DB 연결실패 격리) + suffix 조립부 전수 `ds_object_suffix` 치환(table_insight/schema_insight/table_fp/schema_fp/*_refresh_at) + `_build_insight_object_maps`/read-back 을 `object_key`(database 포함 유일) 키로 전환(cross-DB 동일 `dbo.<table>` 충돌 livelock 방지). ③ `utils.py` `_infer_rag_object_from_fact` 3계층(database.schema.table) 파싱 + object_key 에 database 접두(유일성). ④ `schema.py` bootstrap 2곳 `ds_object_suffix` 치환(2계층 누락 수정). ⑤ `agent_core.py` `_insight_object_group` — grounding(`_load_schema_list`) grouping 을 MySQL=schema/MSSQL=database.schema 로 정합(table_insight↔schema_insight desc 매칭). **검증**: pytest 444 passed/2 skipped(신규 `test_mssql_three_tier_insight.py` 13, 회귀 0) + 라이브(MSSQL 제품 60테이블 grounded, ask-worker grounding 정상). 적대적 리뷰 4결함 수정(REV-20260611-0223). worktree `ai/claude/feature-0003-agent-web-ui`(base c769612). **MySQL 2계층 byte-identical(active_database=None) — 회귀 0.** 잔재: 구형식 2계층 fact_key(키 마이그레이션 진행 중).
- [x] TASK-0208 (**Minor §12.3** — "전체 N행 미리보기" 오링크: 비-결과 분석표 false-positive). `_collapse_large_tables`→`_match_csv_for_table` 의 컬럼수 폴백(2순위)이 LLM 이 손으로 쓴 분석·요약 표(쿼리 결과 아님)에도 컬럼수만 우연히 같은 무관 CSV 를 붙여, 클릭 시 frontend 값 가드가 "결과 파일이 미리보기와 일치하지 않아…" 422 토스트로 거부하던 오링크. **수정**: 표에 식별 토큰이 **있는데도 어느 CSV 와도 overlap 0** 이면(=쿼리 결과 아님의 음성 증거) 폴백 미적용·링크 생략. 폴백은 식별 토큰이 **아예 없는** 측정값-전용 표에만 한정(TASK-0174 회귀 보존). 회귀 테스트 2(분석표 링크 생략 + 다중표 used[] 슬롯 보존), 수정 전 코드에서 신규 테스트 실패 교차검증. outside-voice 적대 리뷰 SHIP-WITH-NITS(BLOCKER 0, REV-20260611-0208). 순수 백엔드(app.js 무변경)→CHECK#13 N/A. worktree `ai/claude/preview-link-nonresult`(base 4c34363). 잔여=ask-worker 재배포.
- [x] TASK-0193 (REQ-20260610-0193, **Major §12.3** — 멀티 datasource Stage 2 P5: Dialect 어댑터). tools.py introspection/sample SQL 을 engine 별 dialect 로 추상화. **산출**: `modules/dialects.py`(MySQLDialect 골든 그대로 + MSSQLDialect 동일 컬럼순서 T-SQL) + tools.py 8사이트 `_dialects.active()` 치환 + config `_ACTIVE_DATASOURCE_ENGINE`+set_active_datasource(engine=) + agent_core run-wide 엔진(run_agent finally 해제). **outside-voice SHIP-able BLOCKER 0**(REV-20260610-0193): MySQL 골든 byte-identical·MSSQL 컬럼순서·P3 격리 유지. MAJOR M1(ContextVar finally 예외안전) 흡수, MINOR m3(시스템스키마 필터 MySQL방언)=P6 이월. make test **318 passed**(신규 6, 회귀 0)+ruff clean. **보안 게이트는 MySQL 방언 — P6 전 MSSQL 활성화 금지(shadow).** worktree `ai/claude/multi-datasource-p5-dialect`(base 36bf285). 잔여=P6 보안·P7 통합+재게이트.
- [x] TASK-0192 (REQ-20260610-0192, **Major §12.3** — 멀티 datasource Stage 2 P4: MSSQL 드라이버 + 연결 디스패치). engine='mssql' datasource 연결 인프라(방언/보안 P5/P6 이월). **산출**: requirements `pymssql>=2.2.0`+sqlglot `<28` pin / db.py `_pymssql` import + `_connect_mssql`(1433, M-1) + connect() engine 디스패치 / `_collect_cursor_result` 크로스엔진(`description`, mysql 등가) / probe engine 분기. make test **312 passed**(신규 P4 5, 회귀 0)+ruff clean, pymssql-2.3.13 설치 확인. REV-20260610-0192 [SKIPPED:driver-infra](보안 표면 0, MSSQL 보안=P6·종합 outside-voice=P7). flag OFF shadow. worktree `ai/claude/multi-datasource-p4-mssql`(base 2646cbb). 잔여=P5 Dialect·P6 보안·P7 통합+재게이트.
- [x] TASK-0191 (REQ-20260610-0191, **Major §12.3** — 멀티 datasource P3: insight_worker per-datasource). insight fact 키를 datasource 차원으로 분리해 grounding 교차노출 차단(Codex-3) + worker datasource 순회. flag OFF=무접두 동작 0 변경. **산출**: config ContextVar+ds_fact_key/like/strip/scope_name(write·read-back·grounding 3자 정합 단일소유=livelock 방지) / insight.py 키빌드 18곳 치환+datasource 순회(연결실패 격리·스캔KV scope·scan_report 누적) / agent_core grounding ds 필터(not_like + set_active_datasource 직전·finally 해제) + M2 MySQL fallback 가드. **outside-voice subagent SHIP-ABLE BLOCKER 0**(REV-20260610-0191): livelock PASS(동일변수)·보안 PASS(PG ds-스코프)·flag OFF PASS. MAJOR(scan_report 누적)·M2 흡수, MINOR(kb_retrieval=기존 결함) 이월. make test **307 passed**(신규 4, 회귀 0)+ruff clean. worktree `ai/claude/multi-datasource-p3`(base 6449b75). 잔여=Stage 2 MSSQL.
- [x] TASK-0190 (REQ-20260610-0190, **Major §12.3** — 멀티 datasource P2: multi-MySQL Web UI). P1 의 admin datasource API 를 관리 콘솔 UI 로 노출 + 연결테스트 + 대화 datasource 라벨. **산출**: `db.probe_datasource`(flag 무관 연결테스트, errno-only 비유출) + `POST /api/admin/datasources/{key}/test`(console.access, 등록 키만→SSRF 불가) + `_list_products` datasource_key 노출 + admin.js(loadAdminData datasources fetch + renderProductDetail datasource select·연결테스트, console.manage 게이트) + app.js(product 배지) + CSS + 캐시버스터. make test **302 passed**(신규 probe 2, 회귀 0)+ruff clean+node --check. **outside-voice subagent 보안 리뷰 PASS-WITH-NITS BLOCKER 0**(REV-20260610-0190): SSRF 구조차단·errno-only·authz 정상, MINOR 2 수용. 권한 카탈로그 신규 0. cross-feature(0002 probe+0003 UI). worktree `ai/claude/multi-datasource-p2`(base f299125). 잔여(P3): insight per-datasource.
- [x] TASK-0187 (REQ-20260610-0187, **Critical §12.3** — 멀티 datasource P1: multi-MySQL 레지스트리 + 연결 디스패치 + 보안경계). ADR-CORE-0003 의 Stage 1 첫 구현. assistant 가 product 별 다른 MySQL datasource 분석. flag `AGENT_MULTI_DATASOURCE_ENABLED` 기본 OFF → 동작 0 변경. **구현 개선**: 기존 `WebProducts` 에 `DatasourceKey` 바인딩 → product RBAC·allowlist 자동 재사용(대화→product→datasource), 별도 테이블·PG 마이그레이션 0. **산출**: config `DATASOURCES`(.env named credential, 좌표·비밀번호 DB/payload 비저장)+flag+마스킹 / `db.connect(datasource=)` flag-게이트 라우팅 / `agent_core._resolve_product_datasource` 단일 chokepoint(in-process+ask-worker) / web admin list·set 엔드포인트(console.manage·audit). insight 는 P3 이월. **보안경계(security-first)**: datasource 접근=product.access(연결 전 enforce), allowlist 자동 datasource-scope. **outside-voice 적대적 보안 리뷰(REV-20260610-0187 SUBAGENT, Codex /tmp 오류→subagent fallback, NEEDS-TWEAK BLOCKER 0) M-1/M-2/N-2 흡수**: default_db allowlist 우회→database=None(M-1), 미등록 키 fail-open→fail-closed(M-2), DS_USER root 폴백 금지(N-2). make test **297 passed/2 skipped**(신규 15, 회귀 0)+ruff clean. RBAC 카탈로그 신규 0. 잔여(P2): CRUD UI·선택기. worktree `ai/claude/multi-datasource-p1`(base ea0746b). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0185 (REQ-20260610-0185, **design-only** — 멀티 datasource 롤아웃 시퀀싱 결정 기록). TASK-0183 plan-eng-review/Codex 가 남긴 미해결 결정 3건(§4 Q6/Q7/Q8)을 사용자 결정으로 확정. **(Q6/Q8) multi-MySQL 먼저** — Stage 1(P1~P3) MySQL 전용, MSSQL 은 Stage 2(P4~P7, RBAC outside-voice 재게이트). **(Q7) 보안경계 연결과 동시** — datasource RBAC + datasource-스코프 allowlist + per-datasource RO 자격증명이 P1 에(flag≠권한검사, Codex-4). 반영: DESIGN §4 resolved + §5 Stage 1/2 재구성 + §10 갱신 + ADR-CORE-0003. 잔여(Stage 2): §4 Q1~Q5. REV-20260610-0185 [SKIPPED:decision-recording]. 코드/RBAC/스키마 mutation 0. worktree `ai/claude/multi-datasource-decisions`(base b4e52b5). 동시세션 TASK-0184 충돌→0185.
- [x] TASK-0183 (REQ-20260610-0183, **Critical §12.3 — design-only** — 멀티 datasource 설계 2차 검토: plan-eng-review + Codex cross-model). TASK-0182 설계의 엔지니어링 매니저 4섹션 리뷰 + **Codex cross-model outside voice**(REJECT, BLOCKER 4+MAJOR 5) 수행 후 발견을 DESIGN 에 직접 반영. **신규 핵심**: (Codex-2 보안결함 정정) `db_datareader+DENY` 가 allowlist 와 양립불가 → **전용 role 에 허용 view/object 만 GRANT SELECT** 본문 정정. (Codex-1) AST 추출도 무자격/view/ownership chaining 우회 → `datasource_id+catalog+schema+object`. (Codex-3) insight 격리가 fingerprint 키에만 → fact 스코프 교차노출. (Codex-4) 보안경계 P1 뒤늦음. (Codex-6) confirm_heavy LLM 자기우회 + fetchall 무제한. Claude eng: 단일 canonical AST(A2/C1)·pool cap·insight stagger. **반영**: DESIGN §1·§3.2·§3.3·§3.4·§3.6·§4 정정 + §10 신설 + GSTACK REVIEW REPORT. **미해결(구현 착수 시)**: P1 시퀀싱(사용자 보류)·보안경계 P1 전진·scope 정당화 — §4 Q6/Q7/Q8. 코드/RBAC/스키마/시크릿 mutation 0 — 문서만. worktree `ai/claude/multi-datasource-eng-review`(base e5a4591). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0182 (REQ-20260610-0182, **Critical §12.3 — design-only** — 멀티 datasource(MySQL·MSSQL) 데이터평면 설계). 사용자 질문("assistant·insight_worker 가 단일 MySQL 만 바라보는데 여러 엔진의 DB 를 바라보게 가능?")의 타당성·범위 규명(AskUserQuestion: 범위=멀티 datasource 동시, 엔진=MySQL·MSSQL) 후 **설계 문서만** 산출. **산출**: `docs/DESIGN-multi-datasource.md`(3계층 결합 규명 + datasource 레지스트리·드라이버 디스패치·Dialect 인터페이스·보안게이트 멀티방언·LLM grounding·insight per-datasource·RBAC/시크릿·P0~P6 롤아웃) + ADR-CORE-0002(A 네이티브 dialect-adapter 채택, dbhub MCP 기각) + **outside-voice 적대적 설계 리뷰 REV-20260610-0182**(NEEDS-TWEAK, BLOCKER 3+MAJOR 4 — "sqlglot dialect 주입만으로 가드" 전제 거짓 규명: 진짜 격리는 tools.py 정규식 allowlist[MSSQL 식별자 우회 B-1]+RO GRANT[MSSQL 등가 미설계 B-2]+T-SQL 위험구문 커버 0[B-3]). 전 발견을 DESIGN §2.3.1/§3.2~3.4/§3.6/§4/§5/§9 에 design-fold. **구현 이월**(자체 다중 cycle + plan-eng-review + RBAC outside-voice). 코드/RBAC/스키마/시크릿/엔드포인트 mutation 0 — 문서만. worktree `ai/claude/multi-datasource-design`(base 308c6f2). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0172 (REQ-20260609-0172, **Major §12.3** — 무거운 쿼리 자가규제: EXPLAIN 사전 게이팅 + per-query cap). 라이브 인시던트("분기 대화 처리중 단계 안 진행" = 5~6분 대용량 집계 쿼리; ask-worker 는 정상 완주, frozen step 착시 + collateral 포화)의 자가규제 대응. **방향 전환 이력**: 사용자가 self-interrupt(mid-query KILL)를 요청 → outside-voice 설계리뷰가 RECONSIDER("LLM 판단만" 내부모순 + 단일 db_conn KILL 후 깨짐 + LLM 자발중단 의존 + agent_ro processlist 관측불가) → 사용자 결정으로 **EXPLAIN 사전게이팅+cap 으로 전환**(self-interrupt 보류, DESIGN-self-interrupt.md §10~§11). **산출**: `modules/tools.py`(`_estimate_explain_rows` rows×filtered/100 추정 + `_apply_query_cap` MAX_EXECUTION_TIME + `_tool_execute_sql` gate/warn/off 분기 + `confirm_heavy` override) + `modules/config.py`(`AGENT_QUERY_GUARD_MODE`/`_EXPLAIN_ROWS_WARN`/`_MAX_EXECUTION_MS`). flag 기본 off=무변경, canary off→warn→gate. outside-voice 2회(설계 RECONSIDER + diff FIX-BEFORE-ENABLING-GATE, M1/M2/m3/m4 흡수, REV-20260609-0172). make test 회귀 0(신규 test_query_guard 15). worktree `ai/claude/self-interrupt`. **이월**: 정상 무거운 쿼리의 UX·collateral 포화는 replica 라우팅(인프라).
- [x] TASK-0169 (REQ-20260609-0168, **Critical §12.3** — out-of-process ask-worker 실행모델, agent-core 측). 정본 plan/checklist 은 feature-0003 TASK-0169(§2.1 PLAN-APPROVED). agent-core 산출: `alembic/versions/20260609_0003_ask_jobs.py`(큐 테이블) + `modules/ask_jobs.py`(단일문 atomic claim B2 / 단일문 slot enforce M5 / lease fencing B3 / stale sweep / cancel-pending / active_inline_paths / 멱등 `_ensure_ask_jobs`) + `modules/ask.py`(`run_ask_worker_loop` — 시간기반 heartbeat 스레드로 긴 LLM step false-positive requeue 차단, lease 박탈 시 KV cancel fencing, 고아 inline reaper 활성 job 제외, boot self-reclaim, SIGTERM graceful) + `scripts/healthcheck_ask_worker.py` + `agent_core.py`(`run_agent`/`_run_agent_core` optional `run_id`, `--ask-worker` dispatch) + `config.py`(`AGENT_ASK_*`, stale 기본값을 run_timeout+180 으로 동적 산출 — make test 가 AGENT_TIMEOUT_SEC=300 환경 false-positive 포착·수정) + `memory.py`(`set_run_status` run_id→status M4, `_clear_cancel_request` run_id-scoped MJ-2). 테스트 3파일(test_ask_jobs/test_ask_worker/test_clear_cancel_runid). make test 244 pass·회귀 0. **outside-voice 적대적 리뷰 흡수**(REV-20260609-0168). worktree `ai/claude/ask-worker`.
- [x] TASK-0163 (REQ-20260609-0163, **Major §12.3** — LLM 사용량 회계 복구: 메인 추론 계측 + 실제 모델 해소 + 계정별/역할별 집계). **증상(사용자 보고)**: 관리 콘솔 > 감사 > LLM 사용량에서 모델별이 `edge`·`시스템`만 보이고 claude 계열·계정별·역할별 집계가 없음. **라이브 진단(PG `agent_runtime.llm_usage` 19,602행, 06-02~06-08)**: 전부 `model='edge'`, task=table_insight(16594)/schema_insight(2958)/topic(27)/classify(23) — insight worker + 보조뿐, 99.7%가 `conversation_id='__insight_worker__'`(owner NULL→계정별 표 `(시스템)`). **사용자 대화 메인 추론 LLM 호출이 단 1건도 기록 안 됨.** **근본 원인 3**: (RC1 핵심) 메인 agentic loop 호출 `_call_llm`(agent_core.py:1699, 호출처 2007 단일)이 `client.chat.completions.create()` 의 `.choices[0].message` 만 반환하고 `response.usage` 를 버려 `_record_llm_usage` chokepoint 를 우회 → 메인 추론(최대 토큰)이 회계 누락(계정별/역할별이 비던 진짜 이유). classify(`llm_classify_origin_shift`)/topic(`llm_generate_topic`)만 llm.py 경유로 기록. `llm.py:llm_plan` 은 죽은 코드(호출처 0). (RC2) `_record_llm_usage` 가 요청 별칭(`edge`/`core`/`auto`)만 `model` 에 저장, 실제 서빙 모델(`resp.model`, LiteLLM proxy 가 별칭→Bedrock model 해소) 미기록 → claude 식별 불가. (RC3) `admin_llm_usage` 에 by_role 부재 + 계정 숫자 ID. 역할은 MySQL(`WebAccounts.RoleId`→`WebRoles.Name`), usage 는 PG → cross-DB. **산출**: (1) alembic `0002_llm_usage_resolved_model`(down_revision 0001_baseline, `ADD COLUMN IF NOT EXISTS resolved_model varchar(128)`, 멱등 offline SQL) + bootstrap `agent_runtime_schema.sql` parity(백필 불요, NULL 허용). (2) `_record_llm_usage` 가 `served=str(getattr(resp,"model",""))[:128] or None` 을 `resolved_model` 컬럼에 INSERT(best-effort·per-call conn 불변). (3) `_call_llm` 이 응답 직후 `_record_llm_usage(model, "agent", response, conversation_id, run_id)` 호출(self-guard 위 try/except 이중) + `agent_core` import 에 `_record_llm_usage` 추가. **race 수정(outside-voice B1)**: `/api/ask` 는 agent 를 in-process(`asyncio.to_thread`)로 실행([[TASK-0159]])하므로 cfg 전역(MEMORY_CONVERSATION_ID/CURRENT_RUN_ID)은 동시 ask(WEB_PARALLEL_LIMIT) 간 덮어써져 토큰이 잘못된 계정/역할에 귀속될 수 있음(메인 추론=최대 토큰이라 노출 큼). 따라서 `_record_llm_usage`/`_call_llm` 에 `conversation_id`/`run_id` optional 인자 추가 → 메인 추론은 `run_agent` 의 정확한 cid/run_id 를 **명시 인자**로 전달(thread 격리·race-free). helper(classify/topic 등 소량 호출)는 미전달=cfg 전역 fallback(기존 동작 유지·follow-up). 초기 안에 있던 `cfg.MEMORY_CONVERSATION_ID=cid` 직접 set 은 race window 확대라 제거. (4) `admin_llm_usage`: by_model `COALESCE(resolved_model, model)` 집계(model+resolved_model 둘 다 노출), by_account 를 이미 열린 MySQL conn 으로 `WebAccounts LEFT JOIN WebRoles` username·role enrich(MySQL conn 추가 개방 0), `_aggregate_usage_by_role` 순수 헬퍼 Python 폴딩(account None→`(시스템)`, role None→`(역할 없음)`, total_tokens desc), 응답에 `by_role`. 권한 `console.usage.read`(admin) **무변경 — RBAC 카탈로그 0**. (5) admin.html 역할별 표(#usageByRole) + admin.js `tbl(rows,cols)` fmt 에 row 전달, by_role 렌더·계정 username·역할·모델 `별칭 → 해소` 표시, 캐시버스터 `?v=20260609-usage-roles`. (6) `tests/test_llm_usage_record.py`(7: resolved_model/명시 인자 우선/cfg fallback/cfg 귀속/None/no-op/PG 실패 삼킴) + `tests/test_call_llm_records_agent_task.py`(2: agent task+명시 conv/run 기록/실패 비전파). **검증**: make test(컨테이너) **215 passed/5 skipped**(신규 9 PASS, 회귀 0) + ruff All passed + py_compile/node --check + **outside-voice 적대적 diff 리뷰 NEEDS-TWEAK→PASS, BLOCKER 1 흡수(REV-20260609-0163)**. RBAC/secret/endpoint 신규 0, 스키마 additive only. **한계(문서화)**: 계측은 앞으로의 호출만(과거 19,602행 소급 불가), claude 물리 모델 구분은 LiteLLM 이 `response.model` 에 별칭 반환 시 제한적(실 claude 사용 후 검증, 필요 시 feature-0007 LiteLLM config follow-up). worktree `ai/claude/llm-usage-metering`(base 353f062). cross-feature(feature-0002 계측/마이그레이션/테스트 + feature-0003 엔드포인트/프론트).
- [x] TASK-0160 (REQ-20260608-0160, **Major §12.3** — 중단 run 의 고아 tool_use → LLM payload 400 방지). **증상(사용자 보고)**: 웹 DBA 챗 재질의 시 `LLM 호출 오류: Error code: 400 ... BedrockException ... messages.N: tool_use ids were found without tool_result blocks immediately after: tooluse_... Each tool_use block must have a corresponding tool_result block`. **근본 원인**: `/api/ask` 는 agent 를 web 프로세스 안 in-process(`asyncio.to_thread`)로 실행([[TASK-0159]]). web 재배포가 ask 를 `execute_sql` 도중 죽이면 assistant 의 `tool_use` 블록만 `core_messages` 에 저장되고 대응 `tool_result`(tool role) 전에 종료 → 재생성 시 그 고아 tool_use 가 LLM payload 에 실려 Anthropic/Bedrock 이 400 거부 → 대화 영구 사용불가. `_normalize_history_rows` 에 페어링 가드가 있었으나 **미완성** — assistant(tool_calls)를 먼저 `normalized` 에 append 한 뒤 다음 행이 tool 이 아니면 `pending_tool_ids.clear()` 만 하고 이미 추가된 고아 assistant 를 회수하지 못함. **수정(agent_core.py `_normalize_history_rows` 단일 함수)**: assistant(tool_calls) 턴을 버퍼링(`pending_assistant`+`pending_tool_ids`+`pending_tool_rows`)해 턴 종료(다음 비-tool 행/다음 tool_use assistant/EOF) 시 `_flush()` 가 **모든 tool_use id 해소 시에만 commit, 하나라도 미해소면 턴 전체(assistant+부분 tool 결과) drop**. 매칭 없는 고아 tool 행도 drop(기존 유지). 윈도우 경계(`_assemble_core_messages` 의 `normalized[-max:]`) 절단 고아도 함께 무해화. **즉시 해소**: 라이브 대화 `20260608025216-3014b095` 의 고아 msg 1147(+에러버블 1184) 삭제(전수 점검 잔존 고아 0). **회귀 테스트**: `tests/test_history_tooluse_sanitize.py` 6 case(고아 턴/부분 턴/EOF 경계/고아 tool 행/유효 멀티턴/마커 보존) PASS. 검증: py_compile / pytest 6 passed / verify-completion / REV-20260608-0160. RBAC/schema/secret/endpoint 무변경, 단일 함수 read 경로 정합화.

- [x] TASK-0151 (REQ-20260605-0151, **Major §12.3** — DB 조회 사용자 경험 개선: 환각·반복질문·첨부무시·사고미확장 해소). **증상(사용자 보고 6건)**: ① 한 번에 요청 미인지 ② 앞서 말한 내용을 반복 질문 ③ 복잡한 요청은 사용자가 다 설명해야 함 ④ 제안 쿼리/결과가 실제 DB와 다름(환각) ⑤ 쿼리 리뷰용 파일을 첨부해도 자기 DB 기준으로만 답함 ⑥ 시킨 대로만 하고 스스로 사고를 확장 안 함. **라이브 규명(3 subagent + 직접 검증)**: (③④ root cause) `_load_schema_list`/`_load_relevant_table_insights`(="KNOWN SCHEMAS authoritative" grounding 주입원)가 05-27 cutover 로 DROP 된 MySQL `AgentMemoryFactEntries`/`AgentMemoryTexts` 만 조회 → 예외 삼킴 → **grounding 이 항상 비어버림**. 실데이터는 PG `public.fact_entries`(table_insight 765 + schema_insight 15)에 실재하나 사용자 경로에 한 번도 주입 안 됨. 게다가 base SYSTEM_PROMPT 이 "이 (빈) 섹션을 primary 로 쓰고 search/verify 하지 말고 바로 SQL 써라" → grounding 0 상태에서 테이블/컬럼 환각. (② root cause) `_assemble_core_messages` 의 50-메시지 윈도우를 tool 결과가 ~62% 점유 → 초기 user 의도 탈락 + `_should_refresh_origin_request` 가 인사/메타를 origin 으로 고정/오분류. (⑤) 배선은 정상이나 prompt 가 "내 DB 조회"만 강제 + 첨부 리뷰 의도 분기 부재 + text cap(20) `ORDER BY Id ASC` 로 최신 첨부 무음 누락. (①⑥) clarification 도구 부재 + prompt 가 탐색/검증/사고확장을 구조적으로 억제("answer, not explore / limited step budget / verify 금지"). **산출 4건**: (FIX1) `agent_core._global_insight_rows_pg`/`_extract_schema_desc`/`_kb_read_is_pg` 신규 + `_load_schema_list`/`_load_relevant_table_insights` 가 `AGENT_KB_READ_BACKEND=postgres` 시 PG(`_pg_connect_ro`) 정본 조회, 미가용/예외 시 MySQL fallback 보존. (FIX2) base SYSTEM_PROMPT 전면 개편 — grounding 부재/불일치 시 search/describe 발견 의무 + "테이블/컬럼 추측 금지" + 0-rows/에러 환각 가드 + 첨부 리뷰 우선순위 분기 + 사고확장/애매 시 가정명시 후 되묻기, well-grounded 정상 케이스 1-call 효율 유지(코드 상수 + 라이브 `WebSystemPrompts` global row 동시 갱신). (FIX3) `_assemble_core_messages` 가 윈도우 밖 standalone user 메시지를 최대 8개 보존(재정규화로 orphan tool 제거) + `domain._is_low_information_request` 로 인사/메타 origin 고정 차단. (FIX4) `_build_attachment_context_section` text INSTRUCTION 에 리뷰 우선순위 명시 + app.py `_prepare_text_inline_attachments` `ORDER BY Id ASC`→`DESC`(+reverse) 로 cap 초과 시 최신 첨부 보존. **검증**: ruff(All passed) + pytest **189 passed/2 skipped**(신규 `test_db_query_ux.py` 12건, 회귀 0) + 라이브 PG SQL 3종 실데이터 반환 확인 + outside-voice 적대적 diff 리뷰. 변경 파일 3(agent_core.py / domain.py / app.py) + 테스트 1. RBAC/schema/secret/endpoint 무변경.
- [x] TASK-0147 (REQ-20260604-0147, **Major §12.3** — insight worker degraded read-back backoff = livelock 재발 방지). TASK-0145/0146 이 read-back 2경로를 PG 로 고쳤으나, **PG 가 다운되면** 두 read-back 이 (DROP 된) MySQL fallback 으로 떨어져 다시 전부 missing/changed 오판 → 무한 재생성(livelock) 재발 가능(현 fallback 은 빈 결과 + 1회 warn 뿐). 방어 가드 추가: (1) `insight._insight_readback_degraded()` — read backend 가 postgres 인데 `_pg_available()` 실패 또는 `_pg_connect_ro()+SELECT 1` probe 실패면 True(MySQL 모드면 항상 False — live mem_conn 사용이라 불일치 없음). (2) `run_insight_cycle` 이 lock 획득 후 degraded 면 scan/generate skip + status=`degraded_readback`(`should_log` 통과로 가시화). (3) `run_insight_worker_loop` 이 cycle status 가 `degraded_readback`/`error` 면 짧은 tick(8s) 대신 `AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC`(기본 300s) backoff — PG 복구 대기, 무의미한 재시도(livelock 동력) 정지. **검증**: ruff PASS + pytest **177 passed/2 skipped**(신규 `test_insight_degraded_backoff.py` 4건) + 라이브 functional(PG up→False, `_pg_available=False`→True). **outside-voice 불요**(REV-20260604-0147 [SKIPPED] — RBAC/schema/secret/endpoint 무변경, read 경로 방어 가드 only, REV-0145 의 이미 리뷰된 패턴 연장).
- [x] TASK-0145 (REQ-20260604-0145, **Major §12.3** — insight worker livelock 근본 수정 + 운영 하드닝). **증상**: 본 프로젝트를 오래 실행하면 머신 전체가 점점 느려짐(최근 2개월 주기 확인). **근본 원인**: insight worker(`run_insight_worker_loop`, tick=8s)의 영속 검증 read-back `_load_insight_artifact_states` 가 05-27 cutover 로 DROP 된 MySQL `AgentMemory*` 테이블(존재하지 않음)을 조회 → 예외가 `except: rows=[]` 로 **조용히 삼켜져** 4파트(fact/text/rag_document/rag_object) 전부 missing 으로 오판 → `artifact_missing` 영구 유지 → 매 8s 동일 객체 무한 재생성(**livelock**). 그러나 쓰기 정본은 PG(`public.fact_entries` 780·`rag_documents` 19695 실재). **라이브 근거**: 당일 432 cycle / generate_insight **6721건 전부 verify=partial_persist, 성공 0**(agent_memory 123회·global_db 117회 등 동일객체 반복). 이 무한 LLM(edge=ollama, CPU-bound) 호출이 ~3코어 연속 점유(6h 에 CPU 17h) + insight_route.log 최대 1GB/일 + postgres/pgbouncer json 로그 90MB/6h → WSL2 page cache/vmmem 무한 팽창으로 머신 progressive slowdown. **산출**: (A 근본) `modules/insight.py` — `_load_insight_artifact_states_pg()` 신규(PG `fact_entries`/`rag_documents`/`rag_objects`+`texts` join, `_pg_connect_ro()` least-priv) + `_load_insight_artifact_states` 가 `AGENT_KB_READ_BACKEND=postgres` 시 PG read-back 분기(PG 미가용 시 MySQL fallback) + 공유 row-처리 헬퍼 5종(`_apply_insight_*_rows`/`_build_insight_object_maps`) 추출 + 삼켜지던 예외 가시화(`_warn_insight_readback_failed`). `modules/kb_scope.py` — `_scope_filter_sql_pg`(snake_case `scope_key`) + **`_load_kv_prefix_map` PG 분기**(동일 cutover 잔재의 두 번째 면 — fingerprint/refresh_at 맵을 MySQL `AgentMemoryKv`(DROP됨)가 아니라 PG `agent_runtime.kv` 에서 읽도록 `load_memory_kv` 와 동형으로 라우팅). **두 read-back 불일치**: (1) artifact 영속 검증(reason `artifact_missing`) + (2) fingerprint 변경 감지(reason `fingerprint_changed`) — 둘 다 PG 로 고쳐야 무한 재생성이 완전히 멈춘다(1번만 고치면 reason 이 `fingerprint_changed` 로 바뀌며 재생성 지속, 라이브로 확인됨). (B 하드닝) `docker-compose.yml` — 15개 서비스 전부 로그 로테이션(json-file max-size 20m/max-file 5) + mem_limit/pids_limit(현재 사용량 대비 넉넉 — runaway 만 차단, mem_limit 은 page cache 까지 cgroup 귀속해 WSL2 vmmem 상한). `config.py`/`utils.py` — `AGENT_LOG_MAX_BYTES`(기본 50MB) + `append_log_line` 크기 회전. `bin/gc.sh` — 로그 day-dir retention(기본 14d). **검증**: py_compile + ruff(All checks passed) + pytest **173 passed/2 skipped**(baseline 동일, 회귀 0) + 라이브 functional(수정 모듈 컨테이너 import → 재생성 반복 3키 전부 `complete=True/missing=[]`, OLD 코드는 `complete=False`+4파트 missing) + 라이브 SQL(4파트 PG 실재 확인). **outside-voice review (general-purpose subagent, REV-20260604-0145) Verdict PASS — BLOCKER 0**(컬럼 매핑·scope NULL 처리·커넥션 close·false-positive 위험 전부 확인). **이월(TODOS)**: PG 다운 시 degraded read-back 에서 재생성 backoff(현재 로깅만), 별도 compose 프로젝트(local-llm/ollama·mysql-lts)의 리소스 제한.

- [x] TASK-0123 (REQ-20260528-T1T5, **Major §12.3** — Postgres KB 성능 최적화 T1~T5 로드맵 + PgBouncer/Replica 전체 활성화). **산출 9건**: (a) `modules/knowledge.py` — `_load_top_facts_pg()` 신규 (DISTINCT ON + ANY(array) 단일 쿼리, N+1 제거) + `_build_knowledge_payload()` PG fast path 분기 + `_acquire_advisory_lock_pg()` / `_release_advisory_lock_pg()` (pg_try_advisory_lock(hashtext)) + `_is_refresh_due()` PG 무효화 플래그 연동. (b) `modules/db.py` — `_pg_connect_ro()` replica 라우팅 + `_pg_mark_kb_invalidation()` UPSERT + pg_notify + `_pg_check_kb_invalidation()` 조회. (c) `modules/config.py` — `AGENT_KB_PG_HOST_RO` / `AGENT_KB_PG_PORT_RO` 추가. (d) `modules/kb_backend.py` — `_DualWriteMirror._mirror()` fact write 후 `_pg_mark_kb_invalidation()` 호출. (e) `modules/memory.py` — `_ensure_pg_schema()` pg_matviews UNION (MV 감지 버그 수정). (f) `src/scripts/agent_kb_schema.sql` — pg_stat_statements + MATERIALIZED VIEW (CONCURRENTLY, 고유 인덱스) + JSONB + GIN + autovacuum + kb_invalidations + kb_slow_queries view + partial ivfflat index + GIN 인덱스 순서 버그 수정 (TEXT→JSONB DO block 이후로 이동). (g) `docker-compose.yml` — PgBouncer transaction-mode sidecar + PostgreSQL 14 파라미터 튜닝 + postgres-replica (streaming async, profile:replica) + postgres-replica-init entrypoint list 형식 수정 + replica max_connections 50→100. (h) `.env` — `AGENT_KB_PG_HOST=pgbouncer` + `AGENT_KB_PG_HOST_RO=postgres-replica` + `AGENT_KB_PG_USER_RO` / `AGENT_KB_PG_PASSWORD_RO` 추가. (i) `docs/ARCHITECTURE.md` §7 신규 (T1~T5 최적화 레이어) + wiki 3건 갱신 (Data-Flow.md / kb-postgres-pgvector.md / hot.md). **활성화 과정 발견/수정 3건**: (1) pgbouncer `AUTH_TYPE=md5` → `scram-sha-256` (userlist 평문 저장으로 PostgreSQL SCRAM 정합), (2) agent_kb_rw 비밀번호 scram-sha-256 재설정 (md5 임시 우회 제거), (3) pg_hba.conf `host replication all all scram-sha-256` 추가 (replica pg_basebackup 허용). **검증**: T1(DISTINCT ON fact_entries 780행 조회 OK) + T2(MV 780행 0.062ms) + T3(PgBouncer → postgres 172.18.0.7 PASS) + T4(kb_invalidations UPSERT 0.098ms) + T5(postgres-replica is_in_recovery=True 172.18.0.12, WAL async streaming). **outside-voice 불요** (RBAC role 변경 없음, endpoint 변경 없음, 기존 agent_kb_rw/ro role 재사용).

- [x] TASK-0120 (풀 테스트 수행 — 서비스 전체 버그 제거). 모든 명세 기능에 대한 풀 테스트 진행 + 발견 오류 전부 수정. **수정 파일 7건**: agent_core.py + llm.py (SyntaxWarning 이스케이프 시퀀스 2건), kb_backfill.py (TABLE_MAPPING[texts] id_col/select_cols 수정 + _insert_pg_batch row[1:] 통일), kb_backend.py (_DualWriteMirror 클래스 신규 + _dual_write_kb 인스턴스 + 6 mirror method), runtime_backend.py (AGENT_RUNTIME_DUAL_WRITE + RuntimeBackend ABC + MysqlRuntimeBackend + PgRuntimeBackend 10 read method + _dual_write_runtime_mirror), utils.py (_text_store_insert → _dual_write_kb.upsert_text 연동), memory.py (save_memory_kv → _dual_write_runtime_mirror 연동). pytest 결과: 146 PASS, 2 SKIP, 0 FAIL (feature-0002 전체).

- [x] TASK-0119 (REQ-20260527-AR-M5, **Major §12.3** — MySQL agent_runtime 6 테이블 DROP, outside-voice 필수). Phase 2 AR-M5: MySQL `agent_memory` DB 의 agent_runtime 6 테이블 cleanup 스크립트. **본 cycle 산출 3건**: (a) `bin/runtime-cleanup-mysql.sh` 신규 — Stage A/B/C 3단계 cleanup 정책 (ADR-0028), --dry-run/--backup-only/--confirm 3 mode, 4 gate (AGENT_RUNTIME_READ_BACKEND=postgres + dual_write 대소문자 정규화 차단 + --cutover-date 14-day window + TTY double-confirm), mysqldump backup (gzip+sha256+integrity, backtick-anchored CREATE TABLE 검증), 6 테이블 DROP FK convention 순서, ERR trap. (b) `tests/test_runtime_m5_cleanup.py` 신규 (16 test) — script 존재/syntax/dry-run/DROP 순서 + confirm 거부 + mode 중복 거부 + 4 gate 검증 + ADR-0028 문서화 확인. (c) `docs/DECISIONS.md` ADR-0028 신규 (Stage A/B/C + DROP 순서 + confirm string + 대안 폐기). **outside-voice review (REV-20260527-0009, SUBAGENT) Verdict NEEDS-FIX → PASS**: C-1(MYSQL_PWD cmdline→env) + M-1(dual_write 대소문자) + M-2(Stage 5 rollback hint + ERR trap) + M-3(grep backtick-anchor + 50-line threshold) + N-1/N-2/N-3 모두 본 cycle 내 반영. pytest 16/16 PASS (신규) + 131/131 PASS (전체, pre-existing 8 failure 제외).

- [x] TASK-0118 (REQ-20260527-AR-M4, **Major §12.3** — cutover read path, outside-voice 필수). Phase 2 AR-M4: `AGENT_RUNTIME_READ_BACKEND=postgres` env 도입 + PgRuntimeBackend 9 read method + fail-soft dispatcher + memory.py 7 read 분기 + agent_core.py 3 read 분기. **본 cycle 산출 5건**: (a) `modules/runtime_backend.py` 수정 — `AGENT_RUNTIME_READ_BACKEND` env var + `_PG_LOAD_KV/ALL/BY_KEY_VALUE/SUMMARY/MESSAGES/STEPS/CORE_MESSAGES` + `_PG_LIST_CONVERSATIONS` + `_PG_GET_CONV_MESSAGES_FULL` 9 SQL 상수 + `PgRuntimeBackend` 9 read method (load_kv/all/by_key_value/summary/messages/steps/core_messages/list_conversations/get_conv_messages_full) + `_get_pg_runtime_conn_ro()` (_pg_connect_ro 우선, 실패 시 _pg_connect fallback) + `_read_runtime_pg(method_name, **kwargs)` dispatcher (fail-soft: None 반환 on no-postgres env / conn None / unknown method / exception). (b) `modules/memory.py` 수정 — 7 read 함수 PG 분기 추가 (load_memory_kv / load_memory_kv_all / load_memory_context / load_recent_steps / list_conversations / list_processing_conversation_ids / list_delete_requested_conversation_ids) + `_assemble_steps()` helper 추출 (MySQL+PG 공유). (c) `agent_core.py` 수정 — `_assemble_core_messages()` helper 추출 + `_load_conversation_messages` PG 분기 (tool_calls JSONB→json.dumps 재직렬화) + `list_all_conversations` PG 분기 (3-tuple→dict 변환) + `get_conversation_messages` PG 분기 (timestamptz→isoformat). (d) `tests/test_runtime_read_backend.py` 신규 (23 test) — _read_runtime_pg routing 5건 / PgRuntimeBackend 9 method SQL 검증 / memory.py PG 분기 4건 / agent_core.py PG 분기 4건. (e) `bin/runtime-cutover-readiness.sh` 신규 (7 gate: dual-write 활성/row count/ANCHOR/unit test/PG read test/env 정합/backfill state). **web UI app.py 제외**: feature-0003 `_list_conversations` 는 MySQL `Accounts` cross-DB JOIN 의존 — AR-M4b 또는 Phase 3 별도 cycle 지정. ADR-0027 addendum 신규. **outside-voice review (REV-20260527-0008, SUBAGENT)** Verdict PASS. pytest 23/23 PASS (신규) + 122/122 PASS (전체, pre-existing 2 failure 제외). 다음 cycle: AR-M5 (MySQL 6 table DROP).

- [x] TASK-0117 (REQ-20260527-AR-M3, **Minor §12.3** — backfill ETL, 신규 파일만). Phase 2 AR-M3: MySQL agent_memory → Postgres agent_runtime 6 테이블 초기 backfill ETL. **본 cycle 산출 3건**: (a) `scripts/runtime_backfill.py` 신규 (~280 LOC, kb_backfill.py 패턴 답습) — `TABLE_ORDER` (FK 의존성 순서: core_conversations → core_messages → messages → steps → summary → kv) + `TABLE_MAPPING` (6 entry, id_col/offset_pk/since_col/jsonb_indices 이분법) + `_iter_mysql_rows()` (offset_pk=True→OFFSET pagination, False→Id>last_id) + `_build_insert_sql()` (jsonb_indices 기반 `%s::jsonb` cast) + `_insert_pg_batch()` (has_id→row[1:] skip, offset_pk→row 전체) + `backfill_table()` + `main()`. 멱등: upsert 테이블(conversations/kv/summary)은 ON CONFLICT DO NOTHING. append-only(core_messages/messages/steps)는 state file last_checkpoint 재개 기반. `--since AGENT_RUNTIME_DUAL_WRITE_START_TS` filter. (b) `bin/runtime-backfill.sh` 신규 — docker exec wrapper (kb-backfill.sh 패턴, `/shared` state dir). (c) `tests/test_runtime_backfill.py` 신규 (19 test) — TABLE_ORDER/MAPPING 정합 / state roundtrip / corrupted state / build_insert_sql (ON CONFLICT / jsonb cast / append-only) / _insert_pg_batch dry-run / kv full-row / core_messages id skip / steps id skip / empty rows / main smoke / single table / failure→1. **outside-voice 불요** (신규 파일만, 기존 caller 수정 0건, RBAC 무변경, write path 무변경). pytest 19/19 PASS (신규) + 101/103 PASS (전체, pre-existing 2 failure 제외). 다음 cycle: AR-M4 (cutover read path — AGENT_RUNTIME_READ_BACKEND env 분기 + PgRuntimeBackend read method).

- [x] TASK-0116 (REQ-20260527-AR-M2-d, **Minor §12.3** — xmax pg_branch tagging, code mutation 비파괴). Phase 2 AR-M2-d: PgRuntimeBackend `_execute_upsert_with_branch()` 헬퍼 + UPSERT 3개 SQL에 `RETURNING (xmax = 0) AS pg_inserted` 절 추가 + `_rt_pg_op_local` thread-local pg_branch 기록. 3 upsert (save_conversation/save_kv/save_memory_summary) → `_execute_upsert_with_branch` 호출. insert 3개 (save_core_message/save_memory_message/save_memory_step) → pg_branch=None. **outside-voice 불요** (기존 caller 수정 없음, KB M2-d 답습). pytest 82/82 PASS.

- [x] TASK-0115 (REQ-20260527-AR-M2-c, **Minor §12.3** — audit helper + verify/stress 스크립트, code mutation 비파괴). Phase 2 AR-M2-c: `_log_runtime_write_audit()` helper + `_build_runtime_audit_resource_id()` + `_RT_AUDIT_ACTION_MAP` + `_dual_write_runtime_mirror` 내 audit 호출 (mirror 성공 후) + `bin/runtime-dual-write-verify.sh` (~155 LOC, --counts/--audit-sla/--all 3 mode) + `bin/runtime-dual-write-stress.sh` (~80 LOC). `AGENT_RUNTIME_AUDIT_ENABLED=False` 기본값 (opt-in). 검증: verify.sh --counts PASS (PG=0 예상, dual-write 비활성). **outside-voice review (general-purpose, REV-20260527-0006) Verdict PASS (minor note 3개 non-blocking)**. pytest 82/82 PASS.

- [x] TASK-0114 (REQ-20260527-AR-M2-b, **Major §12.3** — method body 구현 + caller 수정, outside-voice 필수). Phase 2 AR-M2-b: `PgRuntimeBackend` 6 method 실제 구현 + `_dual_write_runtime_mirror` connection 내부화 + `memory.py` / `agent_core.py` caller mirror callsite 추가. **본 cycle 산출 4건**: (a) `modules/runtime_backend.py` 수정 (~170 LOC 추가) — 6 SQL 상수 (`_PG_UPSERT_CONVERSATION` / `_PG_INSERT_CORE_MESSAGE` / `_PG_UPSERT_KV` / `_PG_INSERT_MEMORY_MESSAGE` / `_PG_INSERT_STEP` / `_PG_UPSERT_SUMMARY`) + `PgRuntimeBackend` 6 method body + `_get_pg_runtime_conn()` + `_dual_write_runtime_mirror(method_name, **kwargs)` (pg_conn_factory 파라미터 제거 — connection 내부화) + connection 실패 이중 try/except (conn open 단계 + method 호출 단계 각각 PG_REQUIRED 분기). `tool_calls::jsonb` 캐스트 (ADR-0027 C2 정합, outside-voice 지적 반영). (b) `modules/memory.py` 수정 (+4 mirror callsite) — `save_memory_message` / `save_memory_kv` / `save_memory_summary` / `save_memory_step` 각 MySQL write 후 `_dual_write_runtime_mirror()` 호출. (c) `agent_core.py` 수정 (+3 mirror callsite) — `_save_message` / `_ensure_conversation` / `_update_conversation_topic` 각 MySQL write 후 `_dual_write_runtime_mirror()` 호출. (d) `tests/test_dual_write_runtime.py` 신규 (13 test, FakeConn/FakeCursor 패턴) — 12개 시나리오 (no-op / pg unavailable / UPSERT SQL / RETURNING id / 14-column INSERT / UPSERT summary / UPSERT conversation / jsonb cast / non-fatal / fatal / conn.close() 안전성 / memory.py caller 연동). `tests/test_anchor_invariant_runtime.py` 수정 (M2-b API 변경 반영: PgRuntimeBackend 구현 완료 assertion + mirror 시그니처 monkeypatch 패턴 업데이트). **outside-voice review (general-purpose subagent, `REV-20260527-0005`) Verdict NEEDS-FIX — tool_calls::jsonb 캐스트 누락 본 cycle 내 반영 완료**. pytest 23/23 PASS (runtime test files) + 82/82 PASS (전체 suite, pre-existing 2 failure 제외). 다음 cycle: AR-M2-c (cross-DB audit `bin/runtime-dual-write-verify.sh` + stress test).

- [x] TASK-0113 (REQ-20260527-AR-M2-a, **Minor §12.3** — ABC + skeleton, code mutation 비파괴). Phase 2 AR-M2-a: `RuntimeBackend` ABC + `MysqlRuntimeBackend` + `PgRuntimeBackend` skeleton + `_dual_write_runtime_mirror` entry point + test scenario catalog. **본 cycle 산출 2건**: (a) `modules/runtime_backend.py` 신규 (~220 LOC, kb_backend.py M2-a 패턴 답습) — 6 abstract method (save_conversation / save_core_message / save_kv / save_memory_message / save_memory_step / save_memory_summary) + MysqlRuntimeBackend (NotImplementedError skeleton) + PgRuntimeBackend (NotImplementedError skeleton) + _dual_write_runtime_mirror (AGENT_RUNTIME_DUAL_WRITE=0 default, no-op) + thread-safe singleton. (b) `tests/test_anchor_invariant_runtime.py` 신규 (10 test) — 6 시나리오 카탈로그 (RT-S1~RT-S6) + ABC 구조 확인 (import / 6 abstract method / NotImplementedError) + dual-write mirror 동작 (no-op / non-fatal / fatal 분기). **outside-voice 불요** (code mutation 비파괴 — 신규 파일만, 기존 caller 0 수정, RBAC 무변경, AGENT_RUNTIME_DUAL_WRITE default False). 다음 cycle: AR-M2-b (6 method body 구현 + caller mirror 추가 — outside-voice 필수).

- [x] TASK-0112 (REQ-20260527-AR-M1, **Major §12.3** — schema DDL + RBAC grant, outside-voice 필수). Phase 2 AR-M1: 6 agent runtime 테이블 DDL 정본 작성 + Postgres `agent_kb.agent_runtime` schema 적용 + ADR-0027 + schema compare 검증 도구. **본 cycle 산출 4건**: (a) `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql` 신규 (~140 LOC) — CREATE SCHEMA IF NOT EXISTS 방어 guard + set_updated_at() trigger 함수 + 6 테이블 (core_conversations / core_messages / kv / messages / steps / summary) + 인덱스 + trigger + GRANT. C1 흡수: kv FK 의도적 생략 주석 명시 (`__global__` sentinel 1588건). C2 흡수: messages.meta_json → jsonb. N5 흡수: CREATE SCHEMA IF NOT EXISTS 방어 guard. (b) Postgres `agent_kb.agent_runtime` schema 에 DDL apply 완료 (6 테이블 CREATE 확인). (c) `bin/agent-runtime-schema-compare.sh` 신규 (~120 LOC, kb-schema-compare.sh 패턴 답습) — 6 테이블 MySQL↔Postgres 컬럼 정합 비교, PASS 확인. (d) `docs/DECISIONS.md` ADR-0027 신규 (agent_runtime schema 설계 결정 — PK 전략 / FK 정책 / kv __global__ 의도적 생략 / meta_json jsonb / search_path 전역 변경 없음 / 인덱스 전략 / RBAC grant / Alternatives 검토). **outside-voice review (backend+qa subagent, `REV-20260527-0003`) Verdict PASS — Critical 2 (C1/C2) 본 cycle 내 반영**. 다음 cycle: AR-M2-a (`modules/runtime_backend.py` 신규 — Postgres write path dual-write).

- [x] TASK-0111 (REQ-20260527-AR-M0, **Minor §12.3** — Postgres 인프라, 비파괴 추가). Phase 2 AR-M0: `agent_kb` DB 안 `agent_runtime` schema 신설 + role grant + docs. **본 cycle 산출 3건**: (a) `bin/agent-runtime-bootstrap.sh` 신규 (~110 LOC, kb-pg-role-bootstrap.sh 패턴 답습) — 4 mode (all/--create-schema/--grant-roles/--check), wrapper path auto-detect, docker exec repo-postgres-1, 멱등 (CREATE IF NOT EXISTS). agent_runtime schema CREATE + agent_kb_rw/ro 에 USAGE + DEFAULT PRIVILEGES grant. (b) `docs/SECURITY.md` §10 신규 — agent_runtime Postgres schema RBAC 정책 (schema 설계 원칙 + role 권한 표 + 운영 절차 + ADR 참조). (c) 이관 plan §7 진행 기록 AR-M0 entry + migration plan AR-M0 task 완료 마킹. **schema 실제 적용**: `agent_kb.agent_runtime` schema CREATE 완료 (has_schema_privilege(agent_kb_rw, agent_runtime, USAGE)=t / agent_kb_ro=t). **T3 결정**: search_path 전역 변경 없음 — AR-M1 SQL 에서 schema-qualified (`agent_runtime.core_conversations` 등) 명시. **outside-voice 불요** (기존 role 재사용, 신규 role 신설 없음, DDL = schema 1개 CREATE, AR-M1 에서 outside-voice 필수). 다음 cycle: AR-M1 DDL + RBAC (6 runtime 테이블 DDL + ADR-0026 + outside-voice 필수).

- [x] TASK-0110 (REQ-20260527-AR-M-1, **Minor §12.3** — read-only baseline 측정). Phase 2 AR-M-1: 6 agent runtime 테이블 (AgentCoreConversations/AgentCoreMessages/AgentMemoryKv/AgentMemoryMessages/AgentMemorySteps/AgentMemorySummary) 의 사전 baseline 측정. **본 cycle 산출 2건**: (a) `bin/agent-runtime-measure-baseline.sh` 신규 (~190 LOC, kb-measure-baseline.sh 패턴 답습) — 5 mode (--rows/--schema/--callsites/--fk/--kv/--all), wrapper path 자동 detect, docker exec repo-mysql-1 직접 호출. (b) `artifacts/shared/agent-runtime-baseline-2026-05-27.json` — 6 테이블 exact row count (총 2676 row: Conversations 33 / Messages 392 / Kv 1987 / MemoryMessages 123 / Steps 141 / Summary 0) + insert rate (messages ~9.5/day / memory_messages ~3.0/day / steps ~3.4/day) + callsite 인벤토리 (feature-0002 core 54건 / feature-0003 web 105건) + FK 분석 (explicit FK 0, application-level implicit FK 확인) + KV scoping (__global__ 1588건 / conversation-scoped 399건). **outside-voice 불요** (read-only, code mutation 0건, RBAC 변경 0건). 다음 cycle: AR-M0 (Postgres agent_runtime schema CREATE + agent-runtime-bootstrap.sh).

- [x] TASK-0109 (REQ-20260526-0109, **Minor §12.3** — plan-only, project-level cross-cutting migration plan 문서 등록). 사용자 결정 (2026-05-26): agent_memory MySQL DB 의 모든 테이블 (agent\* 11개 + web\* 18개) 을 PostgreSQL 영역으로 이관 + 최종 agent_memory MySQL DB 자체 deprecation. agent\* 11개 → agent_kb DB 안 새 schema `agent_runtime` 신설. **본 cycle 산출 2건**: (a) `docs/MIGRATION_AGENT_MEMORY_TO_PG.md` 신규 (project-level cross-cutting plan 정본 — Phase 1 KB 5 정본 cleanup 마무리 + Phase 2 AR-M-1~M5 6 runtime 테이블 이관 cycle + Phase 3 18 web\* 별 DB outline + Phase 4 agent_memory DB deprecation). 기존 KB plan (TASK-0015 §2.1) 의 multi-cycle 구조 답습 — 각 sub-phase = 별 ai/\* worktree + 별 PR + 별 verify-completion. (b) `unit/feature-0002-agent-core/docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md` append. **본 turn 의 deliverable 은 plan 문서 등록 + docs append 까지** — 실 implementation 0건 (RBAC/schema/code mutation 없음). **outside-voice review SKIPPED** (`REV-20260526-0003 [SKIPPED:plan-only-no-code-no-rbac-no-schema]`) — 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합 (RBAC catalog 변경 없음, code path 변경 없음, schema mutation 없음). 신규 세션 진입 시 본 plan 문서의 Phase 2 AR-M-1 (baseline 측정) 부터 작업 시작 권장.

- [x] TASK-0026 (REQ-20260526-0001, **Major §12.3** — RBAC role 분리 인지 변경 + DDL credential path 도입). 직전 배포 (main = f03c270) production 검증 중 `repo-memory-init-1` 컨테이너가 exit 1 (`KB Postgres schema 적용 실패 (AGENT_KB_PG_REQUIRED=1): attempted relative import with no known parent package`) 로 재현된 증상의 정식 fix. **본 cycle 산출 6건**: (a) `unit/feature-0002-agent-core/src/Dockerfile` — `COPY .../src/scripts /app/scripts` 추가 (kb_backfill.py 등 ship), (b) `agent_core.py:init_memory()` — relative `from .modules.*` → absolute `from modules.*` (entry point `python /app/agent_core.py` 가 `__package__=None` 이라 relative 실패), (c) `modules/memory.py:_ensure_pg_schema()` — DDL 을 별 superuser connection 으로 분리 (agent_kb_rw 는 DML 전용 — DDL 권한 없음). `AGENT_KB_PG_SUPERUSER*` 1순위 + `AGENT_KB_PG_USER`/`PASSWORD` legacy fallback (B-1 흡수). schema 누락 시 RuntimeError + actionable hint (B-2 흡수 — silent PASS 차단). `try/except ImportError` 의 `e.name` 검사로 fallback 범위 좁힘 (B-3 흡수 — `.db` 내부 실제 ImportError 까지 덮지 않음), (d) `scripts/kb_backfill.py` — `AgentMemoryTexts` PK = `TextHash` (char 64) 반영해 texts 만 OFFSET pagination 으로 전환 (~800 행 frozen 가정 + 주석 명시). 다른 테이블은 Id-based cursor pagination 유지 (회귀 0), (e) `.env.example` — `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` / `AGENT_KB_PG_SUPERUSER_HOST` 3 변수 신규 + bootstrap.sh 와의 정합 주석, (f) `unit/feature-0002-agent-core/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` append. **outside-voice review (Codex `codex-cli 0.130.0`, `REV-20260526-0001`) Verdict BLOCK + Critical 3 본 cycle 내 반영 완료** (B-1 superuser env name divergence → fallback / B-2 검증 fail-loud / B-3 ImportError fallback 좁히기). Nice-to-have 2 (.env.example + kb_backfill.py frozen 주석) 동반 흡수. **본 turn 의 deliverable 은 6 산출 + Critical 3 흡수까지**. Runtime 재검증 (production stack `docker compose -p kb-fix-verify` isolated 또는 본 main stack 에 fix 이미지 재빌드 → memory-init exit 0 확인) 은 commit/PR/머지 후 사용자 turn 책임.

- [x] TASK-0025 (REQ-20260522-0007, **Major §12.3** — RBAC 영향 cycle, 데이터 손실 boundary) §2.1 PLAN-APPROVED 의 **M5 phase (Cleanup — MySQL KB 5 정본 deprecation)** 실행. M4 cutover 후 MySQL KB 5 정본 (`AgentMemoryFacts` VIEW + 4 base table) 의 deprecation 절차 명문화 + cleanup script + ADR-0025 (14-day monitoring + Stage A/B/C boundary + `I_UNDERSTAND_DATA_LOSS` confirm). **본 cycle 산출 4건**: (a) `bin/kb-cleanup-mysql.sh` (~250 LOC) — 3 mode (dry-run / backup-only / confirm), mysqldump backup (VIEW DDL 포함 + utf8mb4 + hex-blob), backup integrity verify (gzip -t + line count + per-table CREATE TABLE/VIEW 존재 assertion), SHA256 sidecar + chmod 0600, 14-day window enforce (`--cutover-date YYYY-MM-DD`), AGENT_KB_DUAL_WRITE=0 sentinel 강제, TTY interactive double-confirm (또는 `KB_M5_RUN_FROM_HUMAN_SHELL=1`), env fallback (shell 우선, .env 보조), 후 DROP 검증, (b) `docs/DECISIONS.md` ADR-0025 (M5 cleanup 정책 + 14-day window + Stage A/B/C 정량화 + Alternative 검토 + 후속 액션), (c) `modules/kb_backend.py` 의 `_DualWriteMirror` class docstring 에 DEPRECATION NOTICE 추가 (코드 삭제는 M5-implementation cycle 책임), (d) `tests/test_m5_cleanup.py` 11 unit test (script exists/syntax/dry-run/wrong confirm 거부/mode 중복 거부/missing arg 거부/dual_write sentinel/cutover-date 누락/14-day 미달/deprecation notice/ADR-0025 정합). **outside-voice review (Plan subagent, `REV-20260522-0013`) Verdict FAIL + Blocker 5 + Critical 4 본 cycle 내 반영 완료** (B-1 VIEW DDL 포함 / B-2 backup integrity verify / B-3 AGENT_KB_DUAL_WRITE=0 sentinel / B-4 14-day window runtime enforce / B-5 mode 중복 + missing arg 거부 / B-6 TTY interactive confirm / B-7 env fallback / B-8 chmod 0600 + SHA256). C-1~C-7 nice-to-have 일부 흡수 (utf8mb4 + hex-blob + MYSQL_PWD env). **본 turn 의 deliverable 은 4 산출 + Blocker 5 + Critical 4 흡수까지**. **M5-implementation cycle (별 cycle, 사용자 결정)** 책임: `_DualWriteMirror` module + 5 caller mirror call site 코드 삭제.

- [x] TASK-0024 (REQ-20260522-0006, **Major §12.3**) — M4 cutover read path + pg_trgm + AGENT_KB_READ_BACKEND routing + cutover readiness + REV-20260522-0012 Critical 4 흡수. **done in commit 351e35b**.

- [x] TASK-0023 (REQ-20260522-0005, **Minor §12.3** — RBAC 무변경, 데이터 이전 작업) — M3 backfill ETL + embedding worker, **done in commit 957be67**.

- [x] TASK-0022 (REQ-20260522-0002, **Major §12.3**) — M2-d pg_branch xmax + S2/S4/S5/S6 + tagging coverage gate + Nice-to-have 7 + REV-20260522-0010 Critical 6 흡수. **done in commit bc3fa81**.

- [x] TASK-0101 (REQ-20260522-0004, **Minor §12.3** — backlog closure batch, cross-feature docs). 본 세션 (TASK-0098 ship + TASK-0100 hot-fix 후) 의 잔여 backlog 항목 일괄 closure. (a) **feature-0002**: TASK-0010 (작업 브랜치 commit 후 clean integration worktree cherry-pick/push) + TASK-0011 (원본 워크트리 더티 동일성 재확인) → 과거 작업 흐름의 마무리 docs, 코드 작업 자체는 이미 완료. (b) **feature-0001 / 0004 / 0005 / 0006**: TASK-0004 (엄격한 시나리오 정의) → placeholder. (c) **feature-0005**: TASK-0005 (MCP 서비스 기동 검증) → 본 cycle 실 환경 검증. (d) **feature-0003**: TASK-0072 → main 의 TASK-0099 closure 재확인.
- [x] TASK-0100 (REQ-20260522-0003, **Minor §12.3** — multipart UploadFile 의존성 hot-fix). `python-multipart>=0.0.9` 한 줄 추가 → web container 안정.
- [x] fix/query-result-string-truncation (Minor §12.3) — render.py CSV 기반 `preview_table` 구성.
- [x] TASK-0021 (REQ-20260522-0001, **Major §12.3**) — M2-c cross-DB audit explicit + SLA verify body + stress.sh body + S1/N1/N2 실 구현 + REV-20260521-0009 Critical 6 흡수. **done in commit 7540e17**.

## 1.2 Implementation Plan (TASK-0026 — KB Postgres bootstrap fix 본 cycle)

영향 파일 (본 cycle, code + env + docs):
- `unit/feature-0002-agent-core/src/Dockerfile` (+1 LOC) — `COPY .../src/scripts /app/scripts` 추가. agent image 가 kb_backfill.py / kb_embedding_worker.py / agent_kb_schema.sql 을 ship.
- `unit/feature-0002-agent-core/src/agent_core.py` (+/- 2 LOC, line 2016 / 2018) — `from .modules.db import _pg_available` → `from modules.db import _pg_available`, 동일하게 `.modules.memory` → `modules.memory`. entry point `python /app/agent_core.py` 직접 실행이라 `__package__ = None` → relative import 실패.
- `unit/feature-0002-agent-core/src/modules/memory.py` (+45 LOC, 1410-1462 + 1564-1582) — `_ensure_pg_schema()` 의 DDL 분리. (i) `try/except ImportError` 의 `e.name` 검사로 fallback 범위 좁힘 (B-3). (ii) `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` 1순위, unset 시 `AGENT_KB_PG_USER` / `AGENT_KB_PG_PASSWORD` legacy fallback (B-1). (iii) superuser conninfo + autocommit + `cur.execute(schema_sql)`. SUPERPASSWORD 없으면 DDL skip (bootstrap.sh `--apply-schema` 가 사전 적용했다는 가정). (iv) return dict 직전에 `expected_tables` / `missing_extensions` / `view_present` 검증 — 누락 시 RuntimeError + actionable hint (B-2 — silent PASS 차단).
- `unit/feature-0002-agent-core/src/scripts/kb_backfill.py` (+45 LOC) — `AgentMemoryTexts` PK = `TextHash` (char 64) 인지 반영. `TABLE_MAPPING["texts"]` 에 `text_hash_pk: True` flag + `id_col: TextHash` + `select_cols` 에서 `Id` 제거. `_iter_mysql_rows()` 가 `text_hash_pk` 분기에서 OFFSET pagination (~800 행, 성능 충분). `_insert_pg_batch()` 가 `text_hash_pk` 시 `row` 전체 INSERT (다른 테이블은 `row[1:]` 로 Id skip). frozen 가정 주석 추가 (Nice-to-have).
- `.env.example` (+11 LOC) — `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` / `AGENT_KB_PG_SUPERUSER_HOST` 3 변수 + bootstrap.sh 정합 주석 (Nice-to-have).
- `unit/feature-0002-agent-core/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`: REQ-20260526-0001 + TASK-0026 + CHG-20260526-0001 + REV-20260526-0001 + REPORT Summary 1줄.

접근 방법:
1. **Bug root cause**: production 의 memory-init container 가 `python /app/agent_core.py` (절대 path 실행) 로 띄워지는데, `from .modules.db import _pg_available` 의 relative import 가 `__package__ = None` 환경에서 `ImportError: attempted relative import with no known parent package` 로 실패. `AGENT_KB_PG_REQUIRED=1` 의 fail-loud 분기가 작동해 sys.exit(1). 따라서 production 의 KB Postgres schema 가 이미 적용된 상태에서도 검증 단계까지 못 가서 init 실패.
2. **Fix path A (relative→absolute)**: agent_core.py 의 2개 import 만 absolute 로. memory.py 등 라이브러리 모듈은 양쪽 import 컨텍스트 (relative 또는 absolute) 가능하도록 try/except 패턴 유지하되, `e.name` 검사로 진짜 ImportError 가리지 않게.
3. **Fix path B (DDL/role 분리)**: `agent_kb_rw` 가 DML 전용임을 인지해 DDL 은 별 superuser conn 사용. SUPERPASSWORD unset 일 때는 bootstrap.sh 가 이미 적용했다는 가정으로 skip + 검증만 수행.
4. **Fix path C (fail-loud)**: 검증 단계가 silent PASS 되지 않도록 expected schema 정합 검사 + actionable hint.
5. **Fix path D (kb_backfill PK)**: 별 issue 지만 production runtime 에 영향. M3 backfill 이 future cycle 에서 호출될 때 정상 작동하도록.

**Outside-voice review**: 호출 ✓ (사용자 args 명시 + RBAC role 분리 인지 변경 = `feedback_outside_voice_for_rbac.md` 정책 정합). Codex `codex-cli 0.130.0`, `REV-20260526-0001`. Verdict **BLOCK** → **PASS 전환** (Critical 3 본 cycle 흡수 + Nice-to-have 2 동반 흡수).

**Runtime 검증 (사용자 운영 turn 책임)**:
1. PR squash merge + main pull --ff-only 후 main = f03c270 + 본 cycle commit.
2. production stack `docker compose build memory-init` 또는 `agent` (공유 image).
3. `docker compose up -d memory-init` → exit 0 확인 + 로그에 `KB Postgres schema 적용 완료: tables=[fact_entries, rag_documents, rag_objects, texts], view=True, extensions=[pg_trgm, vector], grants=...` 출력 확인.
4. 추가 회귀: `make ask` 등 agent 호출 시 KB read path 정상 작동 확인.
5. 만약 production 의 schema 가 부재이면 RuntimeError + actionable hint 출력 — 사용자가 `bin/kb-pg-role-bootstrap.sh --apply-schema` 사전 실행 후 재시도.

위험도: **Major §12.3** — RBAC role 분리 인지 변경 (DDL = superuser, DML = agent_kb_rw) + 4 code 파일 + ENTRYPOINT import path 변경. Pre-approved Changes (§2.1 PLAN-APPROVED 의 M2~M5 phase 가 KB Postgres bootstrap path 정합 보장 — 본 fix 는 그 path 의 implementation defect 수정).

## 1.3 Implementation Plan (TASK-0023 — M3 Backfill ETL + embedding worker, done — 보존)

영향 파일 (본 cycle, ETL + embedding + test):
- `unit/feature-0002-agent-core/src/scripts/kb_backfill.py` (신규 ~280 LOC) — TABLE_MAPPING (4 table) + load_state/save_state + open_mysql_conn/open_pg_conn (기존 modules/db.py 재사용) + _iter_mysql_rows paginate + _insert_pg_batch ON CONFLICT DO NOTHING + backfill_table progress logging + main() argparse (--table/--since/--batch-size/--dry-run/--reset-state).
- `unit/feature-0002-agent-core/src/scripts/kb_embedding_worker.py` (신규 ~190 LOC) — get_settings (config.py 의 5 env 변수) + open_pg_conn + call_openai_embeddings (retry + timeout) + count_pending/fetch_pending_batch/update_embeddings + estimate_cost_usd (model 별 가격 추정) + main() argparse + dry-run cost estimation.
- `bin/kb-backfill.sh` (신규 ~45 LOC) — docker exec agent + AGENT_KB_BACKFILL_STATE_DIR=/shared.
- `bin/kb-embedding-worker.sh` (신규 ~25 LOC) — docker exec agent + arg passthrough.
- `unit/feature-0002-agent-core/src/modules/config.py` (+~15 LOC) — AGENT_KB_EMBEDDING_MODEL (text-embedding-3-small default) + DIM (1536) + BATCH_SIZE (100) + TIMEOUT_SEC (60) + MAX_ATTEMPTS (3) + EXPORT_VARS 등록.
- `tests/test_kb_backfill.py` (신규 ~125 LOC) — 4 unit test (TABLE_MAPPING 정합 / state roundtrip / dry-run no-op / main smoke).
- `tests/test_kb_embedding_worker.py` (신규 ~140 LOC) — 6 unit test (cost estimation 3 model + length mismatch + UPDATE SQL emit + dry-run no-OpenAI).
- `docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + 본 entry + Summary.

접근 방법:
1. TABLE_MAPPING — 4 table 의 mysql → pg 컬럼 명명 (SnakeCase 적용, KB_PG_DIALECT_NOTES.md 정합) + ON CONFLICT clause (texts/fact_entries 는 DO NOTHING, rag_documents/rag_objects 는 ON CONFLICT...DO NOTHING — backfill 은 멱등 진입이므로 DO UPDATE 불필요).
2. backfill state file — artifacts/shared/kb-backfill-state.json (host mount /shared).
3. dry-run path — `_insert_pg_batch` 가 INSERT 안 함, len(rows) 반환. SELECT 만.
4. embedding batch — OpenAI text-embedding-3-small 의 input=list batch (~100 text per API call).
5. dry-run cost — sample batch 1회 fetch + 평균 char count × pending → cost USD 추정.
6. test — FakeConn / FakeCursor 패턴, monkeypatch 으로 실 DB/API 우회.

**Outside-voice review**: SKIPPED — 본 cycle 의 ETL 은 RBAC 변경 없음 (agent_kb_rw role 의 기존 INSERT 권한 활용), endpoint 변경 없음, audit 변경 없음. 사용자 메모 `feedback_outside_voice_for_rbac.md` 정책 정합.

**Runtime 검증 deferral (사용자 / M4 별 cycle 책임)**:
1. main worktree `git pull --ff-only` + agent container 가동 확인.
2. `bin/kb-backfill.sh --dry-run` → 분모 정의 (총 row count + 4 table 별 last_id).
3. `bin/kb-backfill.sh --since $KB_DUAL_WRITE_START_TS` → 실제 ETL 진행.
4. `bin/kb-embedding-worker.sh --dry-run` → cost 추정 (M-1 baseline ~800 texts ≈ USD <0.05).
5. `bin/kb-embedding-worker.sh` → 실 OpenAI 호출.
6. `bin/kb-dual-write-verify.sh --counts --since $KB_DUAL_WRITE_START_TS` → 4 table row count 일치.

위험도: **Minor §12.3** — 데이터 이전 작업, RBAC / endpoint / audit 변경 없음. PLAN-APPROVED 범위 (§2.1.3 M3 phase).

## 1.3 Implementation Plan (TASK-0022 — M2-d pg_branch + S2-S6 + delete/prune SLA + Nice-to-have, done — 보존)

영향 파일 (본 cycle, instrumentation + tooling + test):
- `unit/feature-0002-agent-core/src/modules/kb_backend.py` (+~120 LOC) — 3 UPSERT SQL 에 `RETURNING id, (xmax = 0) AS pg_inserted` + `_pg_op_local` threading.local + `_get_last_pg_branch()` / `_clear_pg_branch()` helpers + `_execute_returning_id()` branch 캡쳐 (insert/update) + delete/prune/upsert_text 의 branch 라벨 + `_log_kb_write_audit(pg_branch=...)` 시그니처 + ChangeJson `pg_branch` 필드 + `_MIRROR_METRICS` + `get_mirror_metrics()` / `reset_mirror_metrics()` + `_DualWriteMirror._mirror()` 의 timing.
- `bin/kb-dual-write-verify.sh` (+~70 LOC) — `verify_audit_sla_delete_prune()` 신규 (JSON_UNQUOTE(JSON_EXTRACT(ChangeJson, '$.pg_branch')) 기반) + `--audit-sla-delete-prune` mode + `--since` ISO 8601 validation (C-4) + stderr suppress 일부 제거 (C-7).
- `bin/kb-dual-write-stress.sh` (+~30 LOC) — `--keep-agent-container` (C-2: docker exec agent 재사용) + `--log-dir` (C-3: per-step log file) + `step_log()` helper.
- `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (+~150 LOC) — `_setup_mock_mirror_env()` 공통 fixture (C-5 `_BACKENDS_CACHE` finalize) + S2 (rag_objs INSERT SQL 캡쳐 + category COALESCE NULLIF) + S4 (scope_key=sales_q4 보존 검증) + S5 (SQL template category COALESCE NULLIF assertion) + S6 (agent_kb_schema.sql VIEW DDL DISTINCT ON + tie-break 정합).
- `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (+~80 LOC) — Test 11 pg_branch insert/update (FakeCursor fetchone 가 (id, pg_inserted) tuple) + Test 12 metrics counter (3 mirror call → calls_total=3, calls_by_method 정합, audit_calls_total=3).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + outside-voice REV-20260522-0010 entry (계획) + 본 cycle 산출 기록.

접근 방법:
1. PG SQL 3 UPSERT 에 `RETURNING id, (xmax = 0) AS pg_inserted` 적용 — xmax = 0 은 INSERT, xmax != 0 은 UPDATE (PostgreSQL 의 row-level TX id semantics).
2. `_pg_op_local` threading.local + `_clear_pg_branch()` (mirror 진입 시 reset) + `_get_last_pg_branch()` (audit 호출 시 read).
3. `_execute_returning_id()` 의 row 가 length>=2 시 branch 캡쳐. delete/prune/upsert_text 는 method body 에서 branch 라벨 직접 set.
4. `_log_kb_write_audit()` 시그니처 `pg_branch` 추가 + ChangeJson 에 기록.
5. `_MIRROR_METRICS` dict + 4 metric (calls_total, calls_by_method, latency_ms_total/max, audit_calls/failures) + `_MIRROR_METRICS_LOCK` thread safety.
6. `_DualWriteMirror._mirror()` 의 진입/실패/성공 path 모두 `_record_mirror_latency()` 호출 + audit failure flag.
7. `bin/kb-dual-write-verify.sh` 의 `verify_audit_sla_delete_prune()` — JSON_EXTRACT 로 pg_branch 카운트.
8. `--since` ISO 8601 정규식 검증.
9. `bin/kb-dual-write-stress.sh` 의 `--keep-agent-container` 모드 — docker ps 로 agent service running 검출 시 docker exec 재사용. `--log-dir` per-step log file (각 step 의 timestamp + status).
10. S2/S4/S5/S6 mock-pattern 실 구현. S3 은 schema 정합 assertion 만 + skip 유지.
11. Test 11/12 — pg_branch + metrics 단위 검증.

**Runtime 검증 deferral (M3 별 cycle / 추후 책임)**:
1. `bin/kb-dual-write-verify.sh audit-sla-delete-prune --since <ISO>` 실 측정 (pg_branch tagging 활성 후 windowing)
2. `--keep-agent-container` 모드의 실 latency 개선 정량 측정 (M2-c default ~12분 → 예상 ~3분)
3. process-level latency baseline measurement: `get_mirror_metrics()` 의 production-like sampling

위험도: **Major (§12.3 — RBAC 동반 변경)**. PLAN-APPROVED 범위 + 사용자 "이번 세션에서 남은 cycle 모두 완수" 명시 + outside-voice review 호출 + Nice-to-have 7건 흡수 + S2/S4/S5/S6 실 구현.

## 1.3 Implementation Plan (TASK-0021 — M2-c cross-DB audit + SLA + invariant test, done — 보존)

영향 파일 (본 cycle, audit + tooling + test):
- `unit/feature-0002-agent-core/src/modules/kb_backend.py` (+~155 LOC, 919 → ~1075 LOC) — `_log_kb_write_audit()` helper + `_KB_AUDIT_ACTION_MAP` (6 method → ActionCode/ResourceType) + `_KB_AUDIT_SENSITIVE_KEYS` (text_content/source_sql 제외) + `_build_audit_resource_id()` composite builder (REV-20260521-0009 B-5 — conv|scope|key|... 식별 정밀화) + `_DualWriteMirror._mirror()` 의 audit explicit call (성공 후 best-effort) + `_BACKENDS_LOCK` thread-safe double-checked locking (REV-20260520-0008 Nice-to-have) + `threading` import + ChangeJson 16KB 캡 (REV-20260521-0009 B-6) + `pg_op_kind` tagging (REV-20260521-0009 B-1 — write/delete/prune 분리 기반).
- `bin/kb-dual-write-verify.sh` (+~125 LOC) — `verify_counts()` 본문 (4 테이블 pair count diff) + `verify_content_hash()` 본문 (rag_documents content_hash CONCAT identity 비교) + `verify_audit_sla()` 본문 (GREATEST(created_at, updated_at) PG denominator + write-only audit numerator + over-count fail-loud + zero-denominator INCONCLUSIVE exit 2, REV-20260521-0009 B-1/C-8 흡수).
- `bin/kb-dual-write-stress.sh` (+~40 LOC) — `trigger_insight_cycles()` + `trigger_ask_iterations()` 실 호출 구현 (docker exec insight-worker / docker compose run --rm agent) + FAILURES counter + exit code propagation.
- `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (+~290 LOC) — S1 (RagDocuments missing) 실 구현 (FakeConn + FakeCursor SQL 캡쳐 + monkeypatch `_log_kb_write_audit` 우회) + N1 (LLM call zero) 실 구현 (`modules.llm` 의 `_get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` prefix + `OpenAI` 모두 monkeypatch tripwire, REV-20260521-0009 B-2 흡수; prune signature `keep_limit=` 정정 + DELETE SQL assertion, REV-20260521-0009 B-3 흡수) + N2 (TRUNCATE denied) env-gated (`AGENT_KB_PG_INTEGRATION_TEST=1`) + S2-S6 skip 유지 (M2-d 위임).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + outside-voice REV-20260521-0009 entry + 본 cycle 산출 기록 + Critical 5 흡수 명시 + Nice-to-have 8 → M2-d.

접근 방법:
1. WebAuditEvents schema 파악 (Id/ActorAccountId/ActorRoleId/ActorType='system'/TargetAccountId/SessionId/ActionCode/ResourceType/ResourceId/ChangeJson/MaskedFields/RemoteAddr/UserAgent/RequestId/OccurredAt).
2. kb_backend.py 에 `_log_kb_write_audit()` 추가 — connect_with_retry(database=MEMORY_DB, autocommit=True, attempts=1, REV-20260521-0009 B-4) + ActorType='system' INSERT + ChangeJson 직렬화 (sensitive 제외) + 16KB 캡 + composite ResourceId.
3. `_DualWriteMirror._mirror()` 에 audit explicit call 통합 — mirror 성공 후 try/except 안에서 silent log 패턴.
4. `bin/kb-dual-write-verify.sh` 의 3 함수 본문 — counts/content-hash/audit-sla.
5. `bin/kb-dual-write-stress.sh` 본문 — docker exec + docker compose run + FAILURES counter.
6. `tests/test_anchor_invariant_postgres.py` 의 S1 + N1 + N2 실 구현.
7. Outside-voice review (Plan subagent, REV-20260521-0009) 호출. NEEDS-TWEAK Verdict + Critical 5 본 cycle 내 반영:
   - **B-1**: verify_audit_sla() 분모 GREATEST(created_at, updated_at) + write-only numerator + over-count fail-loud + zero-denom INCONCLUSIVE
   - **B-2**: N1 LLM tripwire 를 `modules.llm` 의 entry point (`_get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` / `OpenAI`) 로 정정 + smoke assertion (적어도 1 patch 설치)
   - **B-3**: prune `keep_limit=` 정정 + 6 method SQL 발행 assertion
   - **B-4**: `connect_with_retry(attempts=1)` — best-effort
   - **B-5**: ResourceId composite (conv|scope|fact_key|... 정확 식별)
   - **B-6**: ChangeJson 16KB 캡

**Runtime 검증 deferral (M2-d 별 cycle 의 사용자 책임)**:
1. main worktree `git pull --ff-only`
2. `.env` 의 `AGENT_KB_PG_REQUIRED=1` 활성 환경
3. `bin/kb-dual-write-stress.sh --insight-cycles 3 --ask-iterations 5` 실 실행
4. `bin/kb-dual-write-verify.sh audit-sla --since <ISO>` → miss_ppm ≤ 1000 검증
5. S2-S6 invariant fixture 실 구현 (실 Postgres + insight worker 통합)
6. Latency baseline production-like 측정 (REPORT.md §4 risk log 0번 entry)

위험도: **Major (§12.3 — RBAC 동반 변경)**. PLAN-APPROVED 범위 + 사용자 "다음 Phase도 진행" 명시 + outside-voice review 호출 + Critical 5 본 cycle 흡수.

## 1.3 Implementation Plan (TASK-0019 — M2-a dual-write 준비, done — 보존, summary)

본 §1.3 의 deliverable 요약:
- `docs/KB_PG_DIALECT_NOTES.md` (~200 LOC) + ADR-0024 (Sprint 4 namespace 격리) ✓
- `agent_core.py:init_memory()` 확장 + `memory.py:_ensure_pg_schema()` grants 검증 + `kb_backend.py` ABC + skeleton + Postgres SQL 템플릿 ✓
- `bin/kb-dual-write-{verify,stress}.sh` skeleton + `tests/test_anchor_invariant_postgres.py` 6 시나리오 catalog ✓
- `docker-compose.yml memory-init.depends_on postgres` (Critical) + `.env.example` (`AGENT_KB_PG_REQUIRED` + `KB_DUAL_WRITE_START_TS`) ✓
- M1 outside-voice review (`REV-20260520-0005`) 의 4 Blocker 모두 해소 + outside-voice (`REV-20260520-0007`) Verdict NEEDS-TWEAK + Critical 4 + Blocker 3 본 cycle 내 반영 ✓
- commit `8dc6d8c` + push + main ff-merge ✓

## 1.4 Implementation Plan (TASK-0018 — M1 Postgres DDL + RBAC role, done — 보존, summary)

본 §1.3 의 deliverable 요약:
- `agent_kb_schema.sql` (241 LOC) + `bin/kb-pg-role-bootstrap.sh` (200 LOC) + `bin/kb-schema-compare.sh` (157 LOC) + `_ensure_pg_schema()` + ADR-0021 (2-layer hybrid) ✓
- outside-voice review (Plan subagent, `REV-20260520-0005`) Verdict NEEDS-TWEAK + 4 Critical 본 cycle 내 반영 ✓
- commit `8152ce9` + push + main ff-merge ✓ (squashed M1 + renumber fixup)

## 1.5 Implementation Plan (TASK-0017 — M0 인프라 도입, done — 보존, summary)

영향 파일 (본 cycle, schema 정의 + script + ADR 만, 실 DB 적용 없음):
- `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규, ~241 LOC) — 5 KB 테이블 (`fact_entries` / `texts` / `rag_documents` / `rag_objects`) + VIEW (`agent_memory_facts`) + index (covering + ivfflat for `texts.embedding`) + role grant `DO $$` block. dialect 변환 (PascalCase → snake_case, AUTO_INCREMENT → IDENTITY, ON UPDATE → trigger, FULLTEXT → pg_trgm GIN). pgvector + pg_trgm extension 활성화.
- `bin/kb-pg-role-bootstrap.sh` (신규, ~200 LOC) — `agent_kb` database + `agent_kb_rw` / `agent_kb_ro` role 생성 + schema sql 적용. 4 mode + rotate-password. **outside-voice Critical #1 반영**: `change_me_*` literal fallback fail-loud (`AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1` 명시 confirm 필요).
- `bin/kb-schema-compare.sh` (신규, ~157 LOC) — MySQL ↔ Postgres information_schema.columns 비교, snake_case ↔ PascalCase normalization, missing column 검출.
- `unit/feature-0002-agent-core/src/modules/memory.py` — `_ensure_pg_schema()` 함수 추가 (~100 LOC). M2 dual-write 진입 시 호출 entry. psycopg fail-soft + tables/view/extensions 존재 검증 query.
- `docs/DECISIONS.md` — ADR-0021 신규 (KB Postgres 분리 후 RBAC catalog 재정의). 2-layer hybrid model. **outside-voice Critical #2~#4 반영**: `kb.mutate.any` 명명 일관성 / cross-DB audit SLA ≤ 0.1% / password rotation graceful degradation / dynamic grant blindspot cycle 명시.
- `.env.example` — `AGENT_KB_PG_RW_PASSWORD` + `AGENT_KB_PG_RO_PASSWORD` 2 변수 추가 (outside-voice Critical #1).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md` — cycle 등록 + 결과 기록 + FUNCTION §10 의 KB DB 스키마 표 갱신 (5 테이블 명 확정).

접근 방법:
1. **MySQL schema 입수** — 5 테이블의 `SHOW CREATE TABLE` 출력 분석. 컬럼 / 타입 / nullable / default / index / unique 정확 파악.
2. **Postgres DDL 작성** — dialect 변환 매핑 적용. embedding 컬럼은 `texts.embedding vector(1536)` 만 (Blocker B-4 결정). VIEW 는 `DISTINCT ON` 패턴 (MySQL correlated subquery 등가).
3. **Role 권한 모델 설계** — 2-layer hybrid (connection-level Postgres role + application-level catalog). `agent_kb_rw` (CRUD) / `agent_kb_ro` (SELECT) 분리. `DO $$` guard 로 schema sql 의 grant block 멱등.
4. **Bootstrap script** — 4 mode (`--create-db` / `--create-roles` / `--apply-schema` / `--all`) + `--rotate-password`. weak password fail-loud (ADR-0021 §Decision Layer 1 의 보안 요구사항).
5. **schema-compare script** — M1 cycle 의 검증 게이트. MySQL ↔ Postgres 컬럼 정합 자동 확인.
6. **`_ensure_pg_schema()`** — M2 dual-write 진입 entry point. M1 에서는 정의만, 호출 없음.
7. **ADR-0021 작성** — 결정 / Consequences / Alternatives / 후속 액션 4 섹션.
8. **Outside-voice review (Plan subagent) 호출** — 사용자 메모리 정책 `feedback_outside_voice_for_rbac.md` 적용. NEEDS-TWEAK Verdict + 4 Critical 본 cycle 내 반영.

**Runtime 검증 deferral (사용자 별 turn)**:
1. main worktree 의 `make start` 로 postgres 컨테이너 가동 (이전 cycle 의 deferral 도 포함)
2. `.env` 의 `AGENT_KB_PG_RW_PASSWORD` / `AGENT_KB_PG_RO_PASSWORD` 값 설정 (또는 weak password 우회 시 `AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1`)
3. `bin/kb-pg-role-bootstrap.sh --all` 실행 — database 생성 + role 신설 + schema 적용
4. `bin/kb-schema-compare.sh` PASS 확인 — 4 테이블 컬럼 정합
5. `psql -U agent_kb_rw -d agent_kb -c "INSERT INTO fact_entries (conversation_id, fact_key, fact_fingerprint) VALUES ('__test__', 'test', 'abc');"` smoke (M2 dual-write 검증 사전 점검)

위험도: **Major (§12.3 — RBAC role 신설 = 인증/인가 변경)**. PLAN-APPROVED 범위 + 사람 confirm 권장 (사용자 "다음 Cycle 이어서 진행" = 진행 의도 표명) + outside-voice review 필수 (메모리 정책).

## 1.6 Implementation Plan (TASK-0016 — M-1 baseline 측정, done — 보존, summary)

영향 파일 (본 cycle, 비파괴 추가만):
- `docker-compose.yml` — `postgres` 서비스 신규 (pgvector/pgvector:pg16, dbnet, healthcheck `pg_isready`, `../artifacts/postgres-data` 볼륨, port `${AGENT_KB_PG_PORT:-5432}`). **agent depends_on 에는 추가 안 함** — M0 는 standalone (Section F-4 권고).
- `.env.example` — `AGENT_KB_PG_*` 17 변수 신설 (§2.1.4 전체). connection 6 + read backend + dual-write + embedding 5 + ANN 4.
- `unit/feature-0002-agent-core/src/requirements.txt` — `psycopg[binary]>=3.1` + `pgvector>=0.2.4` 추가.
- `unit/feature-0002-agent-core/src/modules/config.py` — `AGENT_KB_PG_HOST` / `PORT` / `DB` / `USER` / `PASSWORD` / `SSLMODE` / `_ENABLED` + `AGENT_KB_READ_BACKEND` / `AGENT_KB_DUAL_WRITE` 9 export.
- `unit/feature-0002-agent-core/src/modules/db.py` — psycopg optional import (fail-soft) + `_pg_available()` + `_pg_connect(database=None, autocommit=True)` 추가. 기존 mysql.connector 경로 무영향.
- `bin/kb-pg-healthcheck.sh` (신규, 177 LOC) — 4 mode: `--container` / `--connect` / `--pg-connect` / `--extension`. `--all` 합본. `COMPOSE_PROJECT_NAME=repo` 강제 + main worktree `.env` fallback.
- `bin/kb-measure-baseline.sh` — `--latency` mode 추가 (5/5 보완). 5 시나리오 × N 회 (default 3, `--latency-n 10` 권장) wall-clock 측정. `docker compose -f <main compose> -p repo run --rm agent "<question>"` 호출.
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md` — cycle 등록 + 결과 기록.

접근 방법:
1. **docker-compose `postgres` 서비스 추가** — standalone (agent depends_on 비추가). volume `postgres-data`, port `${AGENT_KB_PG_PORT}:5432`, healthcheck `pg_isready`. dbnet 만 (llm-shared / replica-net 비포함).
2. **`.env.example` AGENT_KB_PG_* 17 변수 추가** — §2.1.4 전체. 값은 빈 string (사용자가 `.env` 에서 채움).
3. **requirements.txt** — psycopg[binary]>=3.1 + pgvector>=0.2.4. Docker image 재빌드 시 자동 설치.
4. **config.py + db.py** — psycopg fail-soft import (M0~M1 환경에서 컨테이너 미가동 시 graceful). `_pg_available()` 가 None 체크 + env 변수 검사. `_pg_connect()` 는 RuntimeError 로 fail-loud (caller fallback 신호).
5. **bin/kb-pg-healthcheck.sh** — 4 stage: container running → psql SELECT 1 → pgvector extension available → agent `_pg_connect()` smoke. M0 runtime 검증 게이트.
6. **bin/kb-measure-baseline.sh --latency** — M-1 cycle 의 deferral (Blocker B-2 1/5) 보완. 측정 가능 상태 (script implementation) 까지 본 cycle. 실 측정은 사용자가 별 turn 에서 `bin/kb-measure-baseline.sh --latency --latency-n 10` 호출.

**Runtime 검증 deferral (사용자 별 turn)**: 본 cycle 의 코드·설정 변경 commit 후, 사용자가 main worktree 의 `chore/template-v3.9.0-upgrade` 작업 마무리 + `git pull --ff-only` + `.env` 의 `AGENT_KB_PG_*` 변수 값 채움 (host=postgres, port=5432, db=agent_kb, user=postgres, password=change_me_pg, sslmode=prefer) + `make start` 재기동 → `bin/kb-pg-healthcheck.sh --all` PASS 확인 → `bin/kb-measure-baseline.sh --latency --latency-n 10` 실행 → JSON artifact 갱신 (TASK-0017 measurement_ready 마감). 본 검증 단계는 외부 LLM API 호출 + docker 환경 의존성 큰 작업으로 자동 진행이 어려움.

검증 (본 turn): `python3 -m py_compile config.py db.py` PASS + `bash -n` syntax check PASS + `docker compose config` syntax OK (warning 만 .env 부재 — 본 worktree 의 .env 가 git 추적 외라 정상).

위험도: Minor (비파괴 추가). PLAN-APPROVED 범위 + outside-voice F-4 권고 정합 ("agent depends_on 비추가" 로 startup ordering 영향 0).

## 1.7 Implementation Plan (TASK-0015, done — 보존, summary)

본 §1.5 의 정본 plan 은 §2.1 (PLAN-APPROVED) 로 승격됨. TASK-0015 cycle 의 deliverable 요약:
- §2.1 multi-cycle plan 정본 작성 ✓
- outside-voice review (Plan subagent NEEDS-TWEAK + 11 Blocker) ✓
- §2.1.11 추적 표 ✓
- PLAN-APPROVED 마커 (2026-05-20 by ms.mckim.gpt@gmail.com) ✓
- commit `6ac2288` + push + main ff-merge ✓

## 1.8 Implementation Plan (TASK-0014 / TASK-0013, done — 보존, summary)

본 §1.6 는 historical TASK plan summary. 상세 본문은 git history (commit `6ac2288` 이전의 TASK.md) 참조.

- **TASK-0014** (REQ-20260515-0003, Minor §12.3): `compose_system_prompt()` 의 Account scope 가 공통 + Product 전용 누적 (Role scope 와 동일 패턴) 으로 정정. `src/agent_core.py` + `tests/test_compose_system_prompt.py` 3건 통과.
- **TASK-0013** (REQ-20260515-0002, Minor §12.3): `compose_system_prompt()` 의 Role scope 의 `ProductId IS NULL` 공통 prompt 를 fallback 이 아니라 누적 적용으로 전환. `src/agent_core.py` + `tests/test_compose_system_prompt.py` 2건 통과.

## 2. Implementation Plan

### 2.1 Plan — KB 정본 MySQL → Postgres pgvector 마이그레이션 (multi-cycle, plan-review)

> **Status**: ✓ **PLAN-APPROVED (2026-05-20 by ms.mckim.gpt@gmail.com)** — 본 §2.1 직후의 PLAN-APPROVED 마커 참조. M-1 cycle 부터 Execute 진입 가능.
> **Outside-voice review**: ✓ 완료 — Plan subagent (`REV-20260520-0002`) 가 **NEEDS-TWEAK** verdict + 11 Blocker / 5 Nice-to-have 식별. 본 §2.1 본문과 §2.1.11 에 NEEDS-TWEAK 적용 결과 반영.
> **Execute 진입 조건**: ✓ 충족됨 — `<!-- PLAN-APPROVED by ... on 2026-05-20 -->` 마커가 본 §2.1 직후에 부여됨.
> **위험도**: Critical (§12.3 — 롤백 어려운 마이그레이션 + RBAC catalog 신설 가능성 + 정책 §11.3·§14.1·§15.6·§15.7 변경 동반).
> **Cycle scope**: 본 §2.1 은 multi-cycle plan 이며 각 phase (M-1 → M0 → M1 → M2 → M3 → M4 → M5) 가 별 cycle (별 ai/* worktree + 별 PR + 별 verify-completion) 로 실행된다.
> **사용자 직접 확인 대기**: D-1 Sequencing 의 권장 default 는 Sprint 4 plan 의 D RAG schema 가 본 plan 의 `rag_documents` / `rag_objects` 와 공유 가능한지 여부에 따라 분기된다 (§2.1.1 D-1 / §2.1.7 Open Q #1+#8 / §2.1.11 Blocker B-1).

#### 2.1.0 배경 (Why)

현재 `agent_memory` DB (MySQL 8.0) 가 보유하는 KB 정본 5종은 다음과 같다.

| 정본 | 역할 | 현재 크기 추정 | 핵심 query 시그니처 |
|---|---|---|---|
| `AgentMemoryFacts` (VIEW) | `FactEntries` 의 합성 view (knowledge.py:697 주석 — "FactEntries 기반 VIEW로 전환됨, 별도 INSERT 불필요") | view (저장 0) | `SELECT ... FROM AgentMemoryFacts WHERE ConversationId IN ('__global__', :cid) AND FactKey ...` |
| `AgentMemoryFactEntries` | fact 정본 (`schema_insight:*`, `table_insight:*`, 대화별 fact, ScopeKey 인덱싱) | REPORT.md 기준선: `table_insight` fact 28→30 (확장 진행 중). 전체는 `incomplete table 126` + 누적 schema_insight 포함 수백~수천 row 예상 | INSERT/DELETE/SELECT — knowledge.py:598, 633, 761~905; insight.py:160 |
| `AgentMemoryTexts` | `TextHash → TextContent` 정규화 저장 (FactEntries / RagDocs / RagObjects 가 공통 참조) | 정규화로 중복 제거된 텍스트 본문 | utils.py:957~964 INSERT IGNORE INTO `AgentMemoryTexts` |
| `AgentMemoryRagDocuments` | FactEntries 기반 backfill, `ConversationId × ScopeKey × FactKey × ContentHash` UNIQUE | insight.py:200 cycle 후 `28 → 56` row | memory.py:202~219, 692~714; utils.py:1179; insight.py:200 |
| `AgentMemoryRagObjects` | FactEntries 기반 backfill + `CategoryDomain` / `CategoryEventType` / `CategoryMetricFamily` 컬럼 (D0~D3 라우팅의 §15.6 카테고리 기초) | insight.py:244 cycle 후 `28 → 30` row | memory.py:226~250, 723~766; utils.py:1230; insight.py:244, 288 |

KB 근거 패키지 구성 (AGENTS.md §11.3·§15.6) 의 현재 query path 는 다음 7개 모듈에 분산되어 있다 — `modules/memory.py` (1,366 LOC), `modules/knowledge.py` (3,153 LOC), `modules/insight.py` (1,410 LOC), `modules/schema.py` (1,426 LOC), `modules/planner.py` + `modules/utils.py` + `agent_core.py`. 총 7,500+ LOC 의 raw SQL (mysql.connector cursor 기반) 가 영향 범위.

**개선 동기**:
1. MySQL FULLTEXT + LIKE 기반 검색은 §15.6 §1) 의 coverage 기반 검색·§15.7 P2 의 metric/조인/검증상태 구조화 + §4) 의 카테고리 + Depth 라우팅 (D0→D1→D2→D3) 을 의미 거리 (embedding similarity) 로 표현하기 어렵다. pgvector 의 `ivfflat` / `hnsw` ANN index 가 자연 대응.
2. RAG 의 `ScopeKey × FactKey × ContentHash` unique 키 검색은 transactional 정합성과 별개로, embedding 기반 ANN 가 §11.3 의 "근거 충족 시 메타탐색 건너뛰기" 판정을 더 견고하게 만든다.
3. fact / RAG / Text / Object 4종 완전성 검사 (insight.py 의 repair_from_fact 루프) 는 새 storage 에서도 ANCHOR §3 invariant 로 보존되어야 한다.
4. 직전 세션의 multi-cycle plan 의 Sprint 4 (D RAG, PGVector 도입) 와 동일 Postgres 인프라를 공유할 수 있으면 도입 비용 1회.

**비-동기 (이 plan 이 다루지 않는 것)**:
- 응답 latency 개선 자체는 1차 목표가 아니다 (pgvector ANN 이 MySQL covering index 보다 느릴 가능성도 있으며, plan 수립 단계에서는 가정하지 않는다).
- LLM 모델 / SQL composer / planner 정책 변경 (별 cycle).
- agent_memory DB 의 비-KB 테이블 (`AgentMemoryConversations`, `AgentMemoryMessages`, `AgentMemorySteps`, `agentmemorykv`) 은 본 마이그레이션 범위 외 — MySQL 유지. KB 만 분리.

#### 2.1.1 결정 매트릭스

본 plan 이 PLAN-APPROVED 받기 위해 사용자가 명시적으로 확정해야 할 결정 3개. outside-voice review (Codex) 호출의 1차 입력이다.

**D-1. Sequencing (직전 multi-cycle plan 의 Sprint 4 D RAG 와의 선후 관계)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. 선행 (권장)** | 본 마이그레이션 (M0~M5) 이 Sprint 4 보다 먼저 진행 → Sprint 4 의 D RAG 는 본 마이그레이션이 구축한 pgvector 인프라 baseline 위에 D-only feature 만 얹는다. | 인프라 도입 1회로 통일. Sprint 4 의 D RAG 가 pgvector ANN 을 자연스럽게 사용 가능. KB cutover 후 새 D RAG 도 즉시 새 storage 에 작성. | 본 마이그레이션 phase M0~M5 가 critical path. Sprint 4 의 D RAG 가 본 마이그레이션 cutover (M4) 까지 대기. | **선행 (M0~M2 까지)** + **M3~M5 는 Sprint 4 와 병행** — M2 dual-write 단계 도달 후 Sprint 4 가 새 D RAG 를 pgvector 측에 직접 작성하기 시작. M3 backfill ETL 과 Sprint 4 가 동시 진행. M4 cutover 는 Sprint 4 D RAG 검증 + 본 마이그레이션 검증의 AND. |
| **B. 병행** | 본 마이그레이션과 Sprint 4 가 처음부터 같은 phase 로 진행. | 일정 단축 가능. | dual-write 로직 + D RAG 신규 schema + 5종 정본 이전 schema 가 동시에 변하므로 schema 충돌 가능성 + verify-completion 검증 어려움 + rollback 매트릭스 폭발. | (비권장) |
| **C. 후행** | Sprint 4 (D RAG, PGVector 도입) 가 먼저 완료 → Sprint 4 가 구축한 pgvector 인프라 위에 본 마이그레이션이 KB 5종 이전. | Sprint 4 의 D RAG 가 안정화된 후 KB 이전이라 risk 분산. | pgvector 인프라가 D RAG 만의 용도로 1차 도입되어, 후속 KB 이전 시 schema 명명·tablespace·index 정책 재논의 필요. 인프라 1차 도입 시점의 설계가 D RAG-only 가정으로 굳어질 risk. | (사용자 결정 필요 — outside-voice review 가 Sprint 4 schema 단순도 판정에 따라 전환 권유 가능) |

> **권장 default**: A (선행 + M3~M5 와 Sprint 4 병행).

**D-2. Topology (단일 Postgres cluster vs 별 인스턴스)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. 단일 cluster + 별 database (권장)** | 1 Postgres 인스턴스 안에 `agent_kb` database 신설. Sprint 4 의 D RAG 와 동일 인스턴스 안 별 database (예: `agent_drag`) 또는 schema (`agent_kb.kb`, `agent_drag.drag`) 분리. | 운영 부담 1 인스턴스. 백업·관측 통합. 인스턴스 내 vector index 메모리 공유. docker-compose 의 `postgres` 서비스 단일. | DB-level 권한 격리는 가능하나 cluster-level fault 가 양 도메인 동시 영향. shared-buffer 경합. | **A 권장** — KB + D RAG 둘 다 read-heavy + 같은 agent 프로세스가 접근하므로 cluster 분리 이득보다 운영 단순성 이득이 크다. |
| **B. 별 인스턴스** | KB 용 `agent_kb_pg` + D RAG 용 `agent_drag_pg` 2 개 Postgres 인스턴스. | 완전 격리. 한쪽 fault 가 다른 쪽 무영향. 메모리·index 독립. | 운영 부담 2배. docker-compose 서비스 2개. 백업·관측·credential 별도. cluster 간 cross-query 불가. | (비권장 — 본 plan 규모에서) |

> **권장 default**: A. schema-level 분리는 추후 ADR 로 결정 가능.

**D-3. Module rewrite strategy (raw psycopg vs SQLAlchemy ORM)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. raw psycopg3 + pgvector extension (권장)** | 현재 `mysql.connector` cursor 패턴을 그대로 psycopg3 cursor 로 교체. pgvector 의 native `vector` 타입은 psycopg3 의 `register_vector()` adapter 로 처리. | 현재 7,500+ LOC 의 raw SQL 패턴 보존. 마이그레이션 risk 최소화. SQL 한 줄 한 줄을 그대로 대응 변환 가능. | ORM 의 schema migration / typed model 이득 없음. raw SQL 의 dialect 차이 (e.g., `INSERT ... ON DUPLICATE KEY UPDATE` → `INSERT ... ON CONFLICT DO UPDATE`) 를 모든 INSERT/UPDATE 위치에서 수동 변환. | **A 권장** — 본 마이그레이션의 1차 목표는 정본 위치 이전이지 ORM 도입이 아니다. ORM 도입은 별 ADR. |
| **B. SQLAlchemy 2.x + pgvector dialect** | knowledge/insight/memory/schema 모듈을 ORM 모델 + session 패턴으로 재작성. | typed model + migration tool (Alembic) + cross-DB portability. | 7,500+ LOC 의 raw SQL 의도가 ORM expression 으로 1:1 대응 안 됨. 마이그레이션 + ORM 도입 동시 진행은 risk 폭발. cycle 분리 필요. | (별 ADR / 별 cycle) |

> **권장 default**: A (raw psycopg3 + pgvector adapter).

#### 2.1.2 영향 파일 (Execute 단계 — phase M0~M5 의 union)

**Source code (agent-core)**:
- `unit/feature-0002-agent-core/src/modules/memory.py` (1,366 LOC) — CREATE TABLE + ALTER + backfill (lines 202~766). Postgres DDL 로 dialect 변환 + `vector(N)` 컬럼 추가 + `ivfflat` / `hnsw` index 정의.
- `unit/feature-0002-agent-core/src/modules/knowledge.py` (3,153 LOC) — FactEntries CRUD (598, 633, 761~905). 모든 query path 의 dialect 변환 + connection helper 분기.
- `unit/feature-0002-agent-core/src/modules/insight.py` (1,410 LOC) — fact / RAG 4종 완전성 검사 + repair_from_fact (160, 200, 244, 288). ANCHOR §3 invariant 의 정본 구현 위치. 새 storage 에서도 동일 흐름 보존 검증.
- `unit/feature-0002-agent-core/src/modules/schema.py` (1,426 LOC) — `AgentMemoryFacts` (VIEW) / FactEntries 직접 조회 (198, 253, 265). VIEW 정의 자체를 Postgres 로 재작성.
- `unit/feature-0002-agent-core/src/modules/planner.py` — FactEntries 기반 plan 입력 (241, 256).
- `unit/feature-0002-agent-core/src/modules/utils.py` — TextHash 저장 (957~964) + RAG INSERT (1179, 1230) + `_load_rag_documents_for_request` / `_load_rag_objects_for_request` / `_filter_rag_objects_for_depth` 등 D0~D3 라우팅의 핵심 helper.
- `unit/feature-0002-agent-core/src/agent_core.py` — `_build_knowledge_context()` (232) + FactEntries / Texts JOIN (273, 293, 357). KB 조회 진입점.
- `unit/feature-0002-agent-core/src/modules/db.py` — connection factory. **psycopg3 connection helper 추가** + 기존 mysql.connector 와 공존 (M2 dual-write 단계).

**Infra**:
- `docker-compose.yml` — `postgres` 서비스 추가 (image: `pgvector/pgvector:pg16` 또는 `ankane/pgvector`). `agent` 컨테이너의 `depends_on` 확장. credential / port (5432 host-side) 정의.
- `docker-compose.override.yml.example` — 로컬 dev / WSL 대응 환경변수 예시.
- `.env.example` — 신규 변수 (§2.1.4 참조).

**Tests**:
- `unit/feature-0002-agent-core/tests/test_pgvector_migration.py` (신규) — dual-write 정합성 + fact-우선 복구 invariant + RagObjects category 보존 + D0~D3 라우팅 회귀.
- `unit/feature-0002-agent-core/tests/test_compose_system_prompt.py` — 회귀 검증 (KB 변경이 system prompt 조립에 영향 없음 확인).

**Policy docs (META path — §18.4 META mode 적용)**:
- `AGENTS.md §11.3` — "관련 질문에서 먼저 `AgentMemoryFactEntries` 근거를 조회한다" → "관련 질문에서 먼저 `agent_kb.fact_entries` (Postgres pgvector) 근거를 조회한다. 조회 path 는 `modules/knowledge.py:_load_kb_entries()` 가 단일 진입점." 형태로 갱신.
- `AGENTS.md §14.1` — 신규 변수 그룹 추가 (`AGENT_KB_PG_*`, `AGENT_KB_READ_BACKEND`, `AGENT_KB_DUAL_WRITE`, `AGENT_KB_EMBEDDING_*`, `AGENT_KB_ANN_*`).
- `AGENTS.md §15.6` — §1) 완전 구축 레이어의 저장소 명 변경 (`AgentMemoryFactEntries` → `agent_kb.fact_entries`). §4) 카테고리 + Depth 라우팅의 D0~D3 가 pgvector ANN similarity threshold 로 표현되는 방식 명시.
- `AGENTS.md §15.7` — 구현 로드맵의 P1/P2 항목을 pgvector 컨텍스트로 갱신.
- `unit/feature-0002-agent-core/docs/FUNCTION.md` — §10 Dependencies 의 `Memory DB 스키마 (agent_memory)` 표에 Postgres `agent_kb` 추가 + `AgentMemoryFactEntries` 행 deprecated 표시.
- `unit/feature-0002-agent-core/docs/INSIGHTS.md` — §4 아키텍처 개요 다이어그램 갱신 (MEMORY DB 박스 안의 FactEntries / Texts 가 Postgres 박스로 이동).
- `unit/feature-0002-agent-core/docs/ANCHOR.md §1·§3` — §1 외부 관점에 "왜 KB 가 별도 Postgres 인스턴스인가?" 추가. §3 가정된 사용 시나리오는 저장소 이름만 변경, fact-우선 복구 invariant 동일.
- `unit/feature-0002-agent-core/docs/AGENT_CORE_INTERNALS.md` — `_build_knowledge_context()` 의 새 query path 반영.
- `docs/DECISIONS.md` — 신규 ADR (예: ADR-0022 "KB 정본 Postgres pgvector 이전") + topology / sequencing / module rewrite 의 3-D 결정 근거.
- `docs/CONVENTIONS.md` — Postgres 명명 규칙 (snake_case) vs MySQL (PascalCase) 매핑 표 추가.
- `docs/SECURITY.md` — Postgres credential 관리 + RBAC catalog hook (`kb.read.any` / `kb.write.any` 신설 가능성, §2.1.5 참조).
- `docs/STATUS.md` — feature-0002 상태에 "KB Postgres 이전 (TASK-0015 계열, multi-cycle)" 표시.
- `docs/CODEBASE_MAP.md` — `agent_kb_schema.sql` (신규) + `bin/kb-backfill.sh` (신규) 등록.

**Tooling (신규)**:
- `bin/kb-backfill.sh` — MySQL → Postgres 초기 backfill ETL (M3 단계). 멱등 + resumable + progress 로그.
- `bin/kb-dual-write-verify.sh` — M2 dual-write 단계의 row count + content hash 정합 검증.
- `bin/kb-cutover-readiness.sh` — M4 cutover 진입 전 게이트 (모든 검증 PASS 시에만 cutover 허용).
- `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규) — Postgres DDL 정본.

#### 2.1.3 Phase 분해 (M-1 ~ M5)

각 phase 는 별 cycle (별 worktree + 별 PR + 별 verify-completion + REPORT.md 갱신) 로 진행한다. phase 간 인계는 본 §2.1 + 각 cycle 의 TASK.md §1.2 (cycle-specific plan) 가 정본.

**M-1 — 사전 baseline 측정 (Blocker B-2 — outside-voice NEEDS-TWEAK)**
- 목적: M0 인프라 도입 전, 현재 KB 의 정량 상태를 측정해 후속 phase 의 회귀 판정 기반을 확보. plan 의 가정 (row 수 / latency / EXPLAIN) 이 추정에 그치지 않도록 측정 산출물로 대체.
- 산출:
  - `bin/kb-measure-baseline.sh` (신규) — 다음 5종 측정 1회 실행:
    1. **Row count**: `SELECT COUNT(*)` 5종 (`AgentMemoryFactEntries` + `AgentMemoryTexts` + `AgentMemoryRagDocuments` + `AgentMemoryRagObjects` + `AgentMemoryFacts` (VIEW)).
    2. **`make ask` latency baseline**: 아래 5종 시나리오의 p50/p99 (각 시나리오 N=10 회 반복) — Blocker B-10 의 구체 catalog 항목.
       - **S1 단순**: "최근 7일간 가입한 사용자 수를 알려줘"
       - **S2 follow-up**: S1 후속으로 "그 중 PaymentMethod 가 카드인 비율은?"
       - **S3 모호**: "최근에 trend 가 어떻게 되고 있어?" (객체 미지정)
       - **S4 메타탐색**: "users 관련 테이블이 뭐가 있어?" (search_tables trigger 의도)
       - **S5 복구**: insight 가 누락된 테이블에 대해 ask 후 fact-우선 복구 path 진입 확인 — `insight_route.log` 에 `repair_from_fact` 흐름 기록 여부.
    3. **EXPLAIN baseline**: 주요 KB query 5건의 `EXPLAIN FORMAT=JSON` (MySQL) 출력 보관 — knowledge.py:761~905 의 핵심 SELECT 5건.
    4. **비-KB JOIN audit** (Open Q #9): `AgentMemoryConversations` / `AgentMemoryMessages` / `AgentMemorySteps` 가 KB 5종과 cross-table JOIN 하는 코드 위치 grep — 결과 0건이 예상이나 확인 필수.
    5. **현재 RBAC catalog 의 KB 접근 패턴 audit** (Blocker B-8): `unit/feature-0003-agent-web-ui/src/app.py:PERMISSION_DEFINITIONS` 의 `kb.*` / `memory.*` 항목 카운트 + agent-core 의 mysql_connector 접근 path 정리.
  - `artifacts/shared/kb-baseline-2026-05-20.json` — 측정 결과 정본 (M4 cutover gate 의 비교 대상).
- 검증: 위 5종 모두 실행 + JSON 저장 + REPORT.md 에 핵심 수치 요약 추가.
- 위험도: Minor (read-only 측정).
- 사람 승인: 불요 (PLAN-APPROVED 범위).

**M0 — 인프라 도입 (Sprint 4 와 공유 가능)**
- 목적: `pgvector/pgvector:pg16` docker-compose 서비스 추가 + agent 컨테이너의 connection helper 추가 (read-only test connection).
- 산출: `docker-compose.yml` 의 `postgres` 서비스, `.env.example` 의 `AGENT_KB_PG_*` 변수, `modules/db.py` 의 `_pg_connect()` helper, `bin/kb-pg-healthcheck.sh`.
- 검증: `make start` 후 agent 컨테이너에서 `_pg_connect()` 가 `SELECT 1` 통과. 기존 MySQL 흐름 무영향 (regression check).
- 위험도: Minor (비파괴 추가).
- 사람 승인: 불요 (Pre-approved Changes 후보 — 사용자 PLAN-APPROVED 마커가 본 M0 ~ M5 모두를 사전 승인).
- D-1 결정에 따라 Sprint 4 와 동시 진행 가능 — 단 schema namespace 충돌 회피 (Sprint 4 는 `agent_drag` database, KB 는 `agent_kb` database).

**M1 — Postgres DDL + Postgres role 신설 + 빈 schema 배치**
- 목적: `agent_kb` database + 5종 table (`facts`, `fact_entries`, `texts`, `rag_documents`, `rag_objects`) 의 Postgres DDL 작성. `vector(N)` 컬럼 + `ivfflat` / `hnsw` index 추가. `agent_kb_rw` / `agent_kb_ro` Postgres role 신설.
- 산출: `agent_kb_schema.sql` (DDL 정본) + `modules/memory.py` 의 `_ensure_pg_schema()` 함수 + `bin/kb-pg-role-bootstrap.sh` (Postgres role 신설 스크립트). embedding 저장 위치 결정 (Blocker B-4): **`texts.embedding` (TextHash 별 단일 embedding)** — TextHash 정규화 시점에 1회 embed → 동일 TextHash 의 다른 fact_entries / rag_documents / rag_objects row 가 재embed 비용 없이 vector 참조. `fact_entries.embedding` / `rag_objects.embedding` 컬럼은 없음 (Texts → 5종 JOIN 시 자연 참조).
- 검증: schema 적용 후 `\d+ agent_kb.fact_entries` + `\d+ agent_kb.texts` 가 모든 컬럼 + index 출력. MySQL 측 schema 와 컬럼 정합성 (이름 / 타입 / nullable / default) 비교 표 (`bin/kb-schema-compare.sh` 신규 임시 도구). `AgentMemoryFacts` VIEW 의 Postgres 측 정의 명시 (Blocker — Open Q #10).
- 위험도: **Major (Minor → Major 격상, Blocker B-8)** — Postgres role 신설 = 인증/인가 구조 변경 (§12.3). 단순 schema 배치 자체는 비파괴이나 role 권한 모델은 §12.1 사람 승인 대상.
- 사람 승인: **필수** — M1 cycle 의 PR 머지 전 사용자 confirm + `docs/SECURITY.md §RBAC` 갱신 + 본 plan §2.1.5 의 ADR-0021 작성 시작 (M4 cutover 전 완료 필수, Blocker B-9).
- D-3 dialect 변환 카탈로그 (Nice-to-have) 도 M1 산출에 포함 권장 — `bin/kb-dialect-audit.sh` 로 `ON DUPLICATE KEY UPDATE` / `INSERT IGNORE` / `TIMESTAMP(3) ON UPDATE` / `cursor.execute(multi=True)` 의 발생 위치 카운트.

**M2 — Dual-write phase (Blocker B-3 — fail rate 분모 정의 + synthetic load)**
- 목적: KB 정본 INSERT/UPDATE/DELETE 가 MySQL + Postgres 양쪽 동시 적용. read 는 MySQL only (지금까지 정본). `KbBackend` 추상화 인터페이스 도입 (4종 sub-backend: `FactEntriesBackend` + `RagDocumentsBackend` + `RagObjectsBackend` + `TextsBackend` — Section C 권고).
- 산출: `modules/knowledge.py`, `modules/insight.py`, `modules/utils.py` 의 write path 에 `_dual_write_kb()` 래퍼 추가. `unit/feature-0002-agent-core/src/modules/kb_backend.py` (신규) — `KbBackend` ABC + `MysqlKbBackend` + `PgKbBackend` 분리. embedding 컬럼은 M2 에서는 `texts.embedding` 만 NULL 로 작성 (M3 에서 backfill 시 일괄 embedding 생성).
- 검증 게이트:
  - **fail rate 분모 정의 (Blocker B-3)**: 비교 대상은 "M2 시작 이후 새로 INSERT 된 row" 만 (M-1 baseline 시점의 ContentHash 기준 backfill 미완료 row 는 분모 제외). `bin/kb-dual-write-verify.sh --since 2026-MM-DD` 형식의 timestamp filter 도입.
  - **Synthetic write load (Blocker B-3)**: 1주일 wait 대신 1주일 + synthetic load. `bin/kb-dual-write-stress.sh` (신규) 가 강제 insight cycle 3회 + ask 5종 시나리오 5회 = 약 50건 새 write 강제 trigger. 통계적 power 확보.
  - **Partial failure 시나리오 (Section C 권고)**: cross-DB tx 불가 → fact_entries INSERT 성공 + rag_documents INSERT 실패 의 partial failure 처리 명시. 정합 검증의 분모 정의 시점에 partial failure row 는 별도 카운트 → REPORT.md 에 분리 보고.
  - **ANCHOR §3 invariant 시나리오 6종 (Blocker B-7)**: `tests/test_anchor_invariant_postgres.py` (신규) — §2.1.6 의 6종 시나리오 통과. M2 → M3 진입 전 PASS 필수.
- 위험도: Major (write path 침습, rollback 가능하나 데이터 정합 risk).
- 사람 승인: PLAN-APPROVED 범위 (Pre-approved Changes 의 "비파괴적 추가").
- ANCHOR §3 invariant: fact-우선 복구 흐름 (insight.py 의 `repair_from_fact`) 이 M2 단계에서는 여전히 MySQL FactEntries 를 source 로 읽지만, write 는 양쪽으로 — Postgres 측 fact_entries 의 정합이 M2 검증의 1차 게이트. "repair_from_fact path 진입 시 LLM 호출 0건" assertion 도 M2 게이트에 포함 (negative assertion, Section C 권고).

**M3 — Backfill ETL + embedding 일괄 생성**
- 목적: M2 시작 시점 이전의 MySQL FactEntries / RagDocuments / RagObjects / Texts 의 모든 row 를 Postgres 로 backfill. 동시에 `texts.embedding` 컬럼의 embedding 을 일괄 생성 (OpenAI `text-embedding-3-small` default, 또는 로컬 모델 — §2.1.4 의 `AGENT_KB_EMBEDDING_MODEL` toggle). M1 결정에 따라 embedding 은 TextHash 별 단일 — 동일 TextHash 의 fact_entries / rag_documents / rag_objects 가 자연 참조 (Blocker B-4).
- 산출: `bin/kb-backfill.sh` — resumable + progress 로그 + chunked PK pagination + idempotency. **Idempotency 키 (Section B 권고)**: 자연키 (Conv × Scope × FactKey × Fingerprint) 기반의 `ON CONFLICT (conv_id, scope_key, fact_key, fingerprint) DO NOTHING` — Postgres 측 SERIAL id 와 무관. **Resume 전략 (Section B 권고)**: embedding API 부분 실패 시 `embedding IS NULL AND text_hash IS NOT NULL` row 만 재처리 + per-row try/except + retry queue + `AGENT_KB_EMBEDDING_MAX_ATTEMPTS=3`.
- 검증: backfill 완료 후 양쪽 row count 일치 + 모든 Postgres `texts` row 의 `embedding IS NOT NULL` + `bin/kb-dual-write-verify.sh` 100% 정합 (M-1 baseline 의 row count + M2 dual-write 의 새 row 합산).
- 위험도: Major (대용량 데이터 이동 + 외부 embedding API 호출 비용).
- Embedding cost 추정 (outside-voice review Section E #4): M-1 baseline 의 `texts` row 수 측정 후 정확 추정 가능. row 수 ~수천 가정 시 `text-embedding-3-small` USD 0.02/1M tokens × 평균 500 tokens/row ≈ USD 0.01~0.5. **plan 의 "USD <100" estimate 는 over-budgeted** 이나 §12.1 외부 비용 조항의 confirm trigger 는 유지 (보수적).
- 사람 승인: PLAN-APPROVED 범위. 단 M-1 baseline 측정 후 cost estimate 가 USD 100 초과로 판명되면 별도 사람 confirm.

**M4 — Cutover (read path 전환)**
- 목적: read path (knowledge.py 의 `_load_kb_entries`, utils.py 의 `_load_rag_documents_for_request` / `_load_rag_objects_for_request` 등) 를 Postgres 로 전환. MySQL 측은 read-only mode 진입.
- 산출: read helper 의 모든 query path 가 `_pg_connect()` 사용. `AGENT_KB_READ_BACKEND=postgres` 환경변수 (M4 진입 시 1, M5 까지 유지).
- 검증 게이트 (`bin/kb-cutover-readiness.sh`):
  - backfill 완료 + dual-write 1주일 정합 fail rate < 0.01% (B-3 분모 정의 적용)
  - ANCHOR §3 invariant 시나리오 6종 (§2.1.6) PASS — 자동화 (`tests/test_anchor_invariant_postgres.py`)
  - **`make ask` 회귀 5종 catalog (Blocker B-10)** PASS — M-1 의 S1~S5 시나리오 (동일 질문, expected 답변 정확성 + insight_route.log path).
  - **Latency 정량 임계 (Blocker B-6)** — M-1 baseline 대비 p99 latency 증가 **50% 이내**. 50% 초과 시 cutover 차단. 임계 초과 사유가 pgvector ANN tuning (probes / lists) 으로 해결 가능하면 M3 으로 복귀 후 재진입.
  - **EXPLAIN ANALYZE 비교 (Open Q #13)** — 주요 query 5건의 Postgres `EXPLAIN ANALYZE` 결과가 ivfflat/hnsw index 사용 확인 (Seq Scan 아님).
  - **ADR-0021 작성 완료 (Blocker B-9)** — `docs/DECISIONS.md` 에 ADR-0021 (KB Postgres 분리 후 RBAC catalog 재정의) entry 가 본 cycle 시작 전 완료.
- 위험도: **Critical** — rollback path 가 명확하지 않은 시점. read backend 전환은 in-place 이므로 cutover 자체는 빠르나 회귀 시 영향 큼.
- 사람 승인: 필수 (별도 confirm + REPORT.md 에 cutover 결정 기록).
- **Rollback window 3단계 (Blocker B-5)**:
  - **Stage A (cutover 직후 ~ M4 cycle 종료 전)**: `AGENT_KB_READ_BACKEND=mysql` 환경변수 1줄 변경 + agent 컨테이너 재기동 — full rollback. MySQL 측 정합이 dual-write 로 보존되어 있음.
  - **Stage B (M4 종료 ~ M5 진입 전)**: dual-write 유지 + read 만 Postgres. rollback 시 MySQL 측 데이터 정합이 여전히 보존되므로 1줄 변경으로 rollback 가능. M5 진입 전까지가 안전 window.
  - **Stage C (M5 cleanup 후)**: MySQL DROP TABLE 완료 → **rollback = 데이터 손실** (M5 의 mysqldump 보관 ETL 역방향 복원 필요). 따라서 M5 진입 결정은 별 cycle 의 PLAN-APPROVED + 사람 confirm.

**M5 — Cleanup (MySQL KB 정본 제거)**
- 목적: M4 cutover 후 2주일 무회귀 확인 후 MySQL 측 KB 5종 정본 drop (또는 read-only deprecated 상태로 유지). dual-write 로직 제거.
- 산출: `modules/knowledge.py`, `modules/insight.py` 의 `_dual_write_kb()` 호출 제거 + MySQL DDL drop (`DROP TABLE AgentMemoryFactEntries` 등).
- 검증: `make ask` 5종 회귀 + 정책 doc (§11.3, §14.1, §15.6, §15.7) 의 최종 갱신 (MySQL 측 KB 정본 참조 제거).
- 위험도: **Critical** — DROP TABLE 은 §12 의 "파괴적 데이터 변경" 에 해당. 사람 승인 필수.
- 사람 승인: 필수 (§12.1 BLOCKED: awaiting-human-approval).
- rollback: backfill 의 역방향 ETL 필요 — drop 전 mysqldump 보관 권장 (M5 의 사전 단계로 dump artifact 보관).

#### 2.1.4 환경변수 신설 (§14.1 갱신 대상)

```bash
# Postgres KB connection (M0~M5 전반)
AGENT_KB_PG_HOST=postgres
AGENT_KB_PG_PORT=5432
AGENT_KB_PG_DB=agent_kb
AGENT_KB_PG_USER=agent_kb_rw
AGENT_KB_PG_PASSWORD=<secret>
AGENT_KB_PG_SSLMODE=prefer

# Read backend 전환 (M4 cutover)
AGENT_KB_READ_BACKEND=mysql   # M0~M3: mysql, M4~M5: postgres
AGENT_KB_DUAL_WRITE=0         # M0~M1: 0, M2~M5 진입까지: 1, M5 후: 0

# Embedding 관리 (M3 backfill + 이후 incremental)
AGENT_KB_EMBEDDING_MODEL=text-embedding-3-small
AGENT_KB_EMBEDDING_DIM=1536
AGENT_KB_EMBEDDING_BATCH_SIZE=50
AGENT_KB_EMBEDDING_TIMEOUT_SEC=30

# ANN index (M1 schema + M4 query)
AGENT_KB_ANN_INDEX_TYPE=ivfflat   # or hnsw
AGENT_KB_ANN_LISTS=100            # ivfflat lists 파라미터
AGENT_KB_ANN_PROBE=10             # query 시 probe 개수
AGENT_KB_ANN_RECALL_TARGET=0.95   # SLA — recall 측정 시 임계
```

기존 `AGENT_KB_*` 변수 (예: `AGENT_KB_COVERAGE_MODE`, `AGENT_KB_REQUIRE_EVIDENCE`, `AGENT_KB_PREFETCH_ON_ASK`) 는 backend 와 무관하게 유지된다.

#### 2.1.5 RBAC catalog hook (별 cycle — outside-voice review 필수)

본 plan 은 RBAC catalog 신설 자체를 포함하지 않는다 (별 ADR + 별 cycle). 다만 본 마이그레이션이 RBAC 의 hook point 를 변경할 가능성이 있으므로 plan-review 단계에서 outside-voice 가 다음 3개 항목을 검증해야 한다.

1. **Storage 권한 매핑** — 현재 RBAC catalog (있다면 `docs/SECURITY.md` 의 RBAC 표 참조) 의 `kb.*` 또는 `memory.*` 권한이 MySQL connection 단위로 정의되어 있는지. Postgres 분리 후 `agent_kb_rw` / `agent_kb_ro` 두 role 신설 필요 가능성.
2. **`kb.read.any` / `kb.write.any` 의 의미 변화** — 사용자 메시지가 명시한 "storage 이전 후 재정의" — 본 plan 의 outside-voice review 가 이 catalog 항목의 정의가 MySQL 의 row-level vs Postgres 의 schema-level 권한 모델 사이에서 어떻게 mapping 되는지 확인.
3. **정적 catalog blindspot** — 메모리 정책 (`feedback_outside_voice_for_rbac.md`) 이 명시한 정적 catalog 의 blindspot. outside-voice review 가 dynamic grant 흐름까지 검토.

본 §2.1.5 의 결과는 outside-voice review 결과 (§2.1.7) 와 합쳐 별 ADR (예: ADR-0021 "KB Postgres 분리 후 RBAC catalog 재정의") 에 정본 기록.

#### 2.1.6 ANCHOR §3 invariant 보존 검증

ANCHOR.md §3 의 가정된 사용 시나리오:
> insight-worker의 기존 복구 로직을 건드려야 할 때: 새 AI 세션이 REPORT.md를 읽으면 `fact/RAG/Text/Object 4종 완전성 확인 → 기존 fact 기반 복구 가능 시 즉시 복구 → 복구 불가 시에만 LLM 재생성` 순서가 명시되어 있다. 이 순서를 뒤집으면 LLM 호출 비용이 폭발한다.

**보존 방법**:
1. `modules/insight.py` 의 `_check_artifact_completeness()` + `_repair_from_fact()` 흐름은 storage 추상화 (`KbBackend` 인터페이스, M2 도입) 뒤에서 동일하게 작동.
2. M2 dual-write phase 의 검증 항목에 "fact 기반 복구 시나리오 1건 (`test_artifact_repair_postgres.py`)" 추가 — Postgres 측 fact_entries 에서 RagDocuments 가 누락된 row 를 인위적으로 만든 후, repair 흐름이 정상 동작하는지 확인.
3. M4 cutover 직전 게이트 (`bin/kb-cutover-readiness.sh`) 에 "fact-우선 복구 시나리오 PASS" 를 명시 게이트 항목으로 추가.
4. ANCHOR.md §3 의 본문은 변경 없음. §1 의 외부 관점에 "왜 KB 가 별도 Postgres 인스턴스인가?" 추가 — M0 cycle 에서 함께 갱신.

#### 2.1.7 Open Questions (outside-voice review 가 답해야 할 항목)

1. **D-1 Sequencing** — 권장 default (A: 선행 + M3~M5 와 Sprint 4 병행) 가 Sprint 4 의 D RAG schema 복잡도와 정합한가? Sprint 4 의 D RAG 가 본 plan 의 `agent_kb.rag_objects` 와 schema 공유 가능한가, 별 namespace 인가?
2. **D-2 Topology** — 단일 cluster + 별 database 권장 default 가 prod / dev / WSL 환경 차이에서 안정적인가? docker-compose 의 메모리 footprint 추정.
3. **D-3 Module rewrite** — raw psycopg3 + pgvector adapter 권장 default 가 7,500+ LOC raw SQL 의 dialect 변환 비용을 충분히 커버하는가? 자동 dialect 변환 도구 (예: `pgloader` 의 SQL 변환) 의 사용 가능성.
4. **Embedding cost** — M3 backfill 의 OpenAI embedding 호출 비용 추정 (현재 KB row 추정 ~수천 ~ 수만). 로컬 모델 (예: `sentence-transformers/all-MiniLM-L6-v2`) 대안.
5. **RBAC catalog** — §2.1.5 의 3개 항목. 정적 catalog 의 blindspot 검토.
6. **`ivfflat` vs `hnsw` index** — RAG row 수 + 쿼리 패턴 (D0~D3 라우팅의 selectivity) 기준으로 어느 index 가 적합한가? `AGENT_KB_ANN_INDEX_TYPE` default 결정.
7. **Cutover rollback path** — M4 cutover 후 회귀 발견 시 `AGENT_KB_READ_BACKEND=mysql` 1줄 변경으로 충분한가? dual-write 가 M5 까지 유지되므로 데이터 정합은 보존되나, 어느 시점부터 MySQL 측 정합이 손상되기 시작하는가?
8. **Sprint 4 D RAG 와의 schema 공유** — 직전 multi-cycle plan 의 Sprint 4 가 정의한 D RAG schema 가 본 plan 의 `rag_documents` / `rag_objects` 와 어떻게 다른가? 본 cycle 에서는 Sprint 4 plan 정본을 확인할 수 없음 — outside-voice review 가 사용자에게 직접 확인 요청.

#### 2.1.8 검증 체크리스트 (각 phase 종료 시점)

각 phase 별 별도 verify-completion 호출. 5종 정본 + ANCHOR §3 invariant 가 모든 phase 의 공통 검증 항목.

| Phase | 검증 항목 | 게이트 |
|---|---|---|
| M0 | docker-compose `postgres` 서비스 healthy + `_pg_connect()` PASS + 기존 MySQL 흐름 무영향 | `make ask` 회귀 5종 PASS |
| M1 | Postgres DDL 적용 + schema-compare 결과 컬럼 정합 일치 | `bin/kb-schema-compare.sh` exit 0 |
| M2 | dual-write 1주일 fail rate < 0.01% + ANCHOR §3 invariant 시나리오 PASS | `bin/kb-dual-write-verify.sh` 7일 누적 PASS |
| M3 | backfill 완료 + 양쪽 row count 일치 + 모든 Postgres row 의 `embedding IS NOT NULL` + embedding cost 기록 | `bin/kb-backfill.sh --verify` exit 0 |
| M4 | cutover readiness 게이트 PASS + `make ask` 회귀 5종 PASS + ANCHOR §3 invariant 시나리오 PASS | `bin/kb-cutover-readiness.sh` exit 0 + 사람 승인 |
| M5 | 2주일 무회귀 + MySQL drop 전 dump 보관 + 정책 doc 최종 갱신 | 사람 승인 + REPORT.md cutover 결정 기록 |

#### 2.1.9 위험도 (§12.3) — phase 별 (outside-voice NEEDS-TWEAK 반영)

| Phase | 위험도 | 사람 승인 |
|---|---|---|
| M-1 | Minor (read-only baseline 측정) | 불요 (PLAN-APPROVED 범위) |
| M0 | Minor (비파괴 추가 — docker-compose + connection helper) | 불요 (PLAN-APPROVED 범위) |
| M1 | **Major (Postgres role 신설 = 인증/인가 변경, Blocker B-8)** | **필수** — `agent_kb_rw` / `agent_kb_ro` role 권한 모델은 §12.1 사람 승인 대상 + ADR-0021 작성 시작 |
| M2 | Major (write path 침습 + KbBackend 추상화 도입) | PLAN-APPROVED 범위 (Pre-approved Changes — 비파괴적 추가) |
| M3 | Major (대용량 데이터 이동 + 외부 embedding cost) | PLAN-APPROVED 범위 + embedding cost > USD 100 시 별도 confirm (M-1 baseline 후 정확 추정) |
| M4 | Critical (read backend 전환 + ADR-0021 게이트) | 필수 — 별도 confirm + REPORT.md cutover 결정 기록 + ADR-0021 작성 완료 + latency 임계 PASS |
| M5 | Critical (파괴적 데이터 변경 — DROP TABLE) | 필수 — §12.1 BLOCKED: awaiting-human-approval + mysqldump 보관 ETL 사전 완료 |

#### 2.1.10 outside-voice review 호출 시점 + 방식

본 cycle (TASK-0015, plan 작성) 단계에서 1회 ✓ **완료** — `REVIEW.md REV-20260520-0002` 정본:
- 호출 channel: Plan subagent (Software architect agent) — `feedback_outside_voice_for_rbac.md` 정책의 "Codex/subagent 외부 시각 항상 호출" 충족.
- 입력: 본 §2.1 전체 + REVIEW.md `REV-20260520-0001` 의 trade-off 기록 + ANCHOR §3 invariant + 관련 src 모듈.
- 검증 결과: **NEEDS-TWEAK** — 11 Blocker + 5 Nice-to-have. 본 §2.1 본문에 반영 완료 (§2.1.11 추적 표 참조).
- Verdict 변환: 11 Blocker 가 §2.1 본문 또는 §2.1.11 의 명시 게이트 항목으로 반영되어 PLAN-APPROVED 진행 가능 상태로 전환.

추가 호출 시점 (Execute 단계):
- **M2 → M3 진입 직전**: dual-write 정합성 시나리오 + KbBackend 추상화 인터페이스 catalog 검토 — 별 cycle 의 plan-review 에 다시 outside-voice.
- **M3 → M4 진입 직전**: cutover readiness 게이트 검토 — Critical 진입이라 outside-voice 필수. ADR-0021 작성 완료 검증 포함.

#### 2.1.11 Outside-voice NEEDS-TWEAK 반영 추적

`REV-20260520-0002` 의 11 Blocker 가 §2.1 본문 어디에 반영되었는지 추적. 사용자 PLAN-APPROVED 마커 부여 전 각 항목 확인 권장.

| ID | Blocker | 반영 위치 | 반영 방식 |
|---|---|---|---|
| **B-1** | D-1 Sequencing 조건부 default (Sprint 4 schema 확인 분기) | §2.1 status / §2.1.1 D-1 표 / §2.1.7 Open Q #1+#8 / §7 Next Action | 사용자 직접 확인 항목 — Sprint 4 D RAG schema 가 KB rag_objects 와 공유 가능 여부 명시 확인 후 A/C 분기. PLAN-APPROVED 마커 시점에 사용자가 답변. |
| **B-2** | M0 이전 baseline 측정 phase 추가 (row count + latency + EXPLAIN + 비-KB JOIN audit + RBAC audit) | §2.1.3 신규 **M-1** phase | M0 이전 별 cycle 로 추가. 5종 측정 + JSON artifact 보관. M4 cutover gate 의 비교 대상. |
| **B-3** | M2 검증 정합 정의 (fail rate 분모 + synthetic load) | §2.1.3 M2 검증 게이트 | "M2 시작 이후 새 row 만 분모" + `bin/kb-dual-write-stress.sh` synthetic load (강제 insight 3회 + ask 5회). |
| **B-4** | M3 embedding 저장 schema 결정 | §2.1.3 M1 산출 / M3 목적 | **`texts.embedding` (TextHash 별 단일)** 채택. `fact_entries.embedding` / `rag_objects.embedding` 컬럼 없음. 동일 TextHash 의 다른 row 재embed 불요. |
| **B-5** | M4 rollback window 3단계 명시 | §2.1.3 M4 Rollback window | Stage A (cutover 직후) / Stage B (M5 진입 전) / Stage C (M5 cleanup 후) 의 rollback 가능성 차별. |
| **B-6** | M4 latency 정량 임계 | §2.1.3 M4 검증 게이트 | M-1 baseline 대비 p99 latency 증가 50% 이내. 초과 시 cutover 차단. |
| **B-7** | ANCHOR §3 invariant 시나리오 6종 catalog | §2.1.6 보존 방법 + M2 게이트 + `tests/test_anchor_invariant_postgres.py` | 시나리오 카탈로그 6종 자동화 + LLM 호출 0건 negative assertion. |
| **B-8** | RBAC role 신설 위험도 격상 + 사람 승인 | §2.1.9 위험도 표 M1 (Minor → Major) + §2.1.3 M1 사람 승인 | M1 의 `agent_kb_rw` / `agent_kb_ro` 신설 = 인증/인가 변경 → 사람 confirm 필수. |
| **B-9** | ADR-0021 (RBAC catalog 재정의) 작성을 M4 cutover 전 게이트 명시 | §2.1.3 M1 + M4 + §2.1.5 | M1 cycle 에서 ADR-0021 작성 시작 + M4 cutover gate 의 명시 항목. |
| **B-10** | `make ask` 5종 시나리오 구체 catalog | §2.1.3 M-1 (S1~S5 명시) + M4 게이트 | S1 단순 / S2 follow-up / S3 모호 / S4 메타탐색 / S5 복구 — 각 N=10 회 반복 + 정확성 + insight_route.log path 확인. |
| **B-11** | 정책 doc 갱신 목록 보강 | §2.1.2 영향 파일 (Policy docs) | `docs/ARCHITECTURE.md` + `docs/LEARNINGS.md` + `FUNCTION.md §10` (Postgres 16 + pgvector extension 외부 의존성) 추가 필요. **본 plan 의 §2.1.2 Policy docs 목록을 사용자가 확인 시점에 인지 + 별 cycle 의 META commit 에 반영.** |

§2.1.7 Open Questions 의 추가 항목 (outside-voice 가 식별):
- **#9 — 비-KB JOIN audit**: KB 테이블과 `AgentMemoryConversations` / `AgentMemoryMessages` / `AgentMemorySteps` 의 cross-table JOIN 가능성. M-1 phase 의 audit 항목으로 흡수.
- **#10 — `AgentMemoryFacts` VIEW 의 Postgres 정의**: M1 phase 의 `agent_kb_schema.sql` 에 명시 항목으로 흡수.
- **#11 — embedding 모델 vendor lock-in fallback**: 모델 교체 시 dim 변경 + backfill 재실행 전략. Nice-to-have (별 ADR).
- **#12 — Latency baseline 측정**: M-1 phase 에 흡수.
- **#13 — EXPLAIN ANALYZE 검증**: M4 cutover gate 의 명시 항목으로 흡수.

Nice-to-have (PLAN-APPROVED 후 별 cycle / 별 ADR — 본 §2.1 의 게이트 항목 아님):
- D-3 dialect 변환 카탈로그 (M1 산출 권장)
- M5.5 post-cleanup canary 1주일
- EXPLAIN ANALYZE 비교 자동화 (M4 gate 의 수동 검증을 M5 후 자동화)
- embedding 모델 vendor lock-in fallback (Open Q #11)
- transactional partial failure 정책 (Section C 권고, M2 보강 가능)

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 -->
<!-- Sprint 4 D RAG schema 확인 (Blocker B-1) 는 M1 cycle 진입 전 별도 확인 필수 -->
<!-- M1 (RBAC role 신설), M4 (cutover), M5 (DROP TABLE) 은 각 phase 진입 시점에 별도 사람 confirm 유효 -->

### 2.2 Previous Plan — insight-worker 4종 완전성 + repair_from_fact + log 재편 (완료, 보존)

본 §2.2 는 TASK-0001~0009 의 historical plan 이다. 본 cycle (TASK-0015) 와 무관하며 historical reference 로 보존된다.

- **영향받는 파일:** `unit/feature-0002-agent-core/src/modules/insight.py`, `unit/feature-0002-agent-core/src/modules/utils.py`, `unit/feature-0002-agent-core/docs/TASK.md`, `unit/feature-0002-agent-core/docs/REPORT.md`, `unit/feature-0002-agent-core/docs/MODIFY.md`, `unit/feature-0002-agent-core/docs/TEST.md`, `AGENTS.md`
- **접근 방법:** 현재 worker 후보 선정 로직에 `4종 아티팩트 완전성 검사`를 추가해 `fingerprint` 만 남고 실제 insight 데이터가 누락된 객체를 다시 처리한다. 이미 fact 텍스트가 남아 있는 경우에는 기존 fact 기반으로 RAG/Text/Object 를 즉시 복구하고, 복구 불가 시에만 LLM 재생성을 수행한다. 로그는 `/shared/logs/YYYY-MM-DD/` 구조로 재정렬하고, 오래된 일자 디렉토리는 `archive/YYYY-MM-DD.tar.gz` 로 압축한다.
- **기준선:** `table_fp:*` `154`, `table_insight` fact `28`, `table_insight` RAG object `28`, fact 자체가 없는 incomplete table `126`, `insight_worker.log` 루트 평면 누적, `insight_route.log` 부재
- **위험도:** Major
- **완료 cycle**: TASK-0001 ~ TASK-0009 (TASK-0010, TASK-0011 은 commit/push 마무리만 남음 — §3 Task Queue 참조). 본 plan 의 정본 invariant 가 ANCHOR.md §3 으로 승격됨.

## 3. Task Queue
- [x] TASK-0001 원본 더티 워크트리 상태 기록 및 보존 전략 확정
- [x] TASK-0002 별도 worktree와 내부 작업 브랜치 생성
- [x] TASK-0003 누락 원인 재현과 기준선 수치 확인
- [x] TASK-0004 로그 유틸을 일자 디렉토리 + 7일 후 tar.gz 보관 구조로 개편
- [x] TASK-0005 insight 후보 선정에 아티팩트 완전성 검사 추가
- [x] TASK-0006 기존 fact 기반 복구 + 복구 실패 시 LLM 재생성 경로 추가
- [x] TASK-0007 worker 상세 추적 로그에 실제 참조 schema/table/column 기록 추가
- [x] TASK-0008 실제 insight cycle 실행 후 누락 복구/로그 생성 검증
- [x] TASK-0009 REPORT/MODIFY/TEST/AGENTS 문서 갱신
- [x] TASK-0010 작업 브랜치 commit 후 clean integration worktree에서 cherry-pick/push
- [x] TASK-0011 원본 워크트리 더티 상태 동일성 재확인
- [x] TASK-0012 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)
- [x] TASK-0013 Role scope 시스템 프롬프트 공통 누적 적용
- [x] TASK-0014 Account scope 누적 + Product → Role → Account 순서 정정
- [x] TASK-0015 (Critical §12.3) KB 정본 MySQL → Postgres pgvector 마이그레이션 plan 정본 작성 + outside-voice review + PLAN-APPROVED 마커 (commit `6ac2288`)
- [x] TASK-0016 (Minor §12.3) M-1 사전 baseline 측정 4/5 + `bin/kb-measure-baseline.sh` 신규 + `artifacts/shared/kb-baseline-2026-05-20.json` 정본 (commit `8db796c`)
- [x] TASK-0017 (Minor §12.3) M0 인프라 도입 — docker-compose `postgres` 서비스 + `.env.example` AGENT_KB_PG_* + requirements.txt psycopg + db.py `_pg_connect()` + `bin/kb-pg-healthcheck.sh` + `bin/kb-measure-baseline.sh --latency` mode (commit `63f5833`)
- [x] TASK-0018 (Major §12.3) M1 Postgres DDL + RBAC role 신설 + ADR-0021 (commit `8152ce9`)
- [x] TASK-0019 (Major §12.3) M2-a dual-write 준비 — KbBackend ABC + skeleton + Blocker 1-4 해소 (commit `8dc6d8c`)
- [ ] TASK-0020 (Major §12.3, **본 cycle**) M2-b dual-write 본 구현 — KbBackend method body 12 + `_DualWriteMirror` helper + caller 5 위치 mirror 호출 + 10 unit test + outside-voice REV-20260520-0008 Critical 6 / Blocker 2 본 cycle 내 반영. M2-c (cross-DB audit explicit call + 7-day SLA + invariant test fixture) 별 cycle 위임.

## 4. In Progress
- TASK-0020 M2-b dual-write 본 구현 — method body + caller 5 + 10 unit test + Critical/Blocker 반영 완료, M2-c cycle (cross-DB audit + 7-day SLA + invariant test fixture) 대기.
- TASK-0010 작업 브랜치 commit 및 integration 반영 준비 (historical, 본 cycle 과 별개)

## 5. Blocked
- 없음 (TASK-0015 PLAN-APPROVED 마커 부여 완료, 본 cycle 의 outside-voice REV-20260520-0008 Critical 6 + Blocker 2 본 cycle 내 반영 완료).

## 6. Done
- TASK-0001 ~ TASK-0009
- TASK-0012, TASK-0013, TASK-0014
- TASK-0015 (commit `6ac2288` + main ff-merge 2026-05-20)
- TASK-0016 (commit `8db796c` + main ff-merge 2026-05-20)
- TASK-0017 (commit `63f5833` + main ff-merge 2026-05-20)
- TASK-0018 (commit `8152ce9` + main ff-merge 2026-05-20)
- TASK-0019 (commit `8dc6d8c` + main ff-merge 2026-05-21)

## 7. Next Action
1. (본 cycle) verify-completion PASS + commit + push + main ff-merge + worktree cleanup.
2. (사용자 별 turn — TASK-0017 / 0018 / 0019 / 0020 통합 runtime 검증):
   - main worktree 에서 `git pull --ff-only` (origin/main 의 본 cycle commit 흡수)
   - `.env` 의 `AGENT_KB_PG_*` 8 변수 채움 (HOST/PORT/DB/USER/PASSWORD/SSLMODE + RW/RO PASSWORD + AGENT_KB_PG_REQUIRED + KB_DUAL_WRITE_START_TS)
   - `make start` 재기동 → postgres 컨테이너 가동 + memory-init `_ensure_pg_schema()` 자동 호출 + `grants_present` 검증 PASS
   - `bin/kb-pg-healthcheck.sh --all` + `bin/kb-pg-role-bootstrap.sh --all` + `bin/kb-schema-compare.sh` PASS (TASK-0017/0018 통합 검증)
   - `AGENT_KB_PG_USER=agent_kb_rw` 전환 + agent 재기동 → fact write 시 `_DualWriteMirror` 가 양쪽 INSERT
3. (**M2-c cycle**, 별 worktree) Cross-DB audit + 7-day SLA + integration test fixture:
   - `_DualWriteMirror._mirror()` 안에서 mirror 성공 시 `WebAuditEvents` audit row INSERT (ActionCode `kb.write.mirror`)
   - `bin/kb-dual-write-verify.sh --audit-sla` 본문 구현 + miss_rate ≤ 0.1% target 검증
   - `bin/kb-dual-write-stress.sh --insight-cycles 3 --ask-iterations 10` 7-day stress run
   - `tests/test_anchor_invariant_postgres.py` 의 6 시나리오 + 2 negative assertion fixture/assertion 실 구현 (S1-S6 + N1 LLM 0건 + N2 TRUNCATE)
   - Nice-to-have 5건 (LC_COLLATE / tsvector simple / `_BACKENDS_CACHE` thread-safe lock / psycopg autocommit docstring / MysqlKbBackend caller drift 방지)
4. (별 cycle, M2~M4 사이) `PERMISSION_DEFINITIONS` 의 `kb.*` 4 항목 추가 (`kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export`) + `docs/SECURITY.md` 갱신.
5. (별 cycle, M2~M4 사이) **Dynamic grant blindspot cycle** (ADR-0021 §후속 액션) — `WebPermissions IsDynamic=1` 패턴의 `kb.*` 적용 검증.
6. (별 cycle, M3) Backfill ETL + embedding 일괄 생성 — `bin/kb-backfill.sh` + `texts.embedding` (Blocker B-4 결정). Embedding cost USD <0.01 추정 (M-1 baseline 기준).
7. (별 cycle, M4) Cutover — read backend 전환 + FULLTEXT → pg_trgm rewrite + EXPLAIN ANALYZE 비교 게이트 + ADR-0021 의 §후속 액션 게이트 항목 모두 완료 확인.

## 8. Completion Checklist (TASK-0020 — M2-b dual-write 본 구현 cycle)
- [ ] `unit/feature-0002-agent-core/src/modules/kb_backend.py` rewrite (~780 LOC: ABC + `prune_fact_entries_keep_top` 보강 + MysqlKbBackend 6 method body + PgKbBackend 6 method body + `_DualWriteMirror` helper + `_dual_write_kb` singleton + `_BACKENDS_CACHE` process-level cache)
- [ ] Caller 5 위치 mirror 호출 (utils.py:957 _text_store_insert + utils.py:1179 RagDoc + utils.py:1230 RagObj + knowledge.py:633 _publish_fact + knowledge.py:598 _prune_fact_entries_for_key)
- [ ] `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` 신규 (10 unit test: no-op / silent log / fail-loud / 성공 / ABC / cache / set_text_embedding / MysqlKbBackend / caller integration / caplog)
- [ ] `unit/feature-0002-agent-core/tests/conftest.py` 신규 (sys.path 통합)
- [ ] `docs/DECISIONS.md` ADR-0021 §Consequences 보강 (Cross-DB audit M2-c cycle 책임)
- [ ] Outside-voice review (Plan subagent, `REV-20260520-0008`) 호출 + Verdict NEEDS-TWEAK + Critical 6 / Blocker 2 본 cycle 내 반영:
  - [ ] Critical 1+2+3: caller 4 위치 silent/fail-loud pattern 통일 (knowledge.py:677-696 dead try/except 제거 + `_prune_fact_entries_for_key` 광역 swallow 분리)
  - [ ] Critical 4: REPORT.md §4 risk log 0번 entry (latency baseline 측정 M2-c 책임)
  - [ ] Critical 5: test isolation (conftest.py + dual import path 제거)
  - [ ] Critical 6: caller actual call test (Test 9 `_text_store_insert` + mock cursor + spy mirror)
  - [ ] Blocker 7+8: ADR-0021 §Consequences M2-c cycle 책임 명시
- [ ] py_compile (kb_backend.py + knowledge.py + utils.py) PASS + bash -n + test compile PASS
- [ ] `bin/verify-completion.sh --pre-commit feature-0002-agent-core` PASS
- [ ] Git 커밋 (`Task-Cycle: feature-0002-agent-core` trailer) + push + main ff-merge + worktree cleanup

## 9. Completion Checklist (TASK-0019, TASK-0018, TASK-0017, TASK-0016, TASK-0015 — done, 보존)
TASK-0019 (M2-a):
- [x] KbBackend ABC + skeleton + Postgres SQL 템플릿 + Blocker 1-4 해소 + Critical 4 / Blocker 3 본 cycle 내 반영
- [x] verify-completion PASS (10/10) + commit `8dc6d8c` + push + main ff-merge

TASK-0016, TASK-0015, TASK-0017, TASK-0018 (보존):
TASK-0016 (M-1 baseline 측정):
- [x] `bin/kb-measure-baseline.sh` 신규 + 4/5 측정 + JSON artifact + REPORT/MODIFY/REVIEW 갱신
- [x] verify-completion PASS (10/10) + commit `8db796c` + push + ff-merge

TASK-0015 (plan-review):
- [x] §2.1 plan 정본 작성 완료
- [x] REVIEW.md `REV-20260520-0001` + `REV-20260520-0002 [SUBAGENT:Plan-subagent]`
- [x] MODIFY.md `CHG-20260520-0001`
- [x] REPORT.md §1·§4·§7 plan-review 상태 표면화 + PLAN-APPROVED 후 갱신
- [x] outside-voice review (Plan subagent, NEEDS-TWEAK + 11 Blocker 반영)
- [x] PLAN-APPROVED 마커 부여 (ms.mckim.gpt@gmail.com on 2026-05-20)
- [x] verify-completion PASS (10/10 checks)
- [x] commit `6ac2288` + push + main ff-merge + worktree cleanup

### AR-M4-read — PgRuntimeBackend read 메서드 구현 (2026-05-27)
- [x] `PgRuntimeBackend` 에 10개 read 메서드 추가 — SQL 상수 이미 정의됨 (CHG-20260527-AR-M4-read): load_kv / load_kv_all / load_kv_by_key / load_kv_by_key_value / load_summary / load_messages / load_steps / list_conversations / load_core_messages / get_conv_messages_full. MySQL fallback 제거로 인해 `agent_memory.agentmemorykv` 없음 오류 해소.

### TASK-0121 — AR-M5 PG cutover 잔존 MySQL 쿼리 차단 (2026-05-27)
- [x] `delete_conversation`: `_pg_delete_conversation()` 신규 — PG agent_runtime + public KB 테이블 삭제 + MySQL try/except 보호
- [x] verify-completion PASS + commit + push + main ff-merge

### TASK-0121 — delete_conversation + ask_status 500 오류 수정 (2026-05-27)
- [x] memory.py `delete_conversation`: `_pg_delete_conversation()` 헬퍼 추가 (CHG-20260527-CONV-DELETE-PG)
  - PG: agent_runtime.kv 수동 + core_conversations CASCADE + public KB 3테이블
  - MySQL DELETE: try/except 보호 (테이블 DROP 후 silent fail)
- [x] app.py `_load_latest_assistant_message`: PG routing 추가 (CHG-20260527-ASK-STATUS-PG)
  - agent_runtime.messages WHERE role='assistant' ORDER BY id DESC LIMIT 50
  - JSONB dict → json.dumps() 직렬화 → 기존 json.loads() 루프 호환
- [x] py_compile 양 파일 구문 확인 OK
- [x] feature-0002 pytest 146 PASS / 2 SKIP 유지 확인
- [x] Docker 재빌드 + 재배포 (web + insight-worker)
- [x] 기능 검증: ask_status 200 + delete_conversation 200 확인 (실서비스)
- [x] verify-completion + 커밋 + push + main ff-merge

### TASK-0174 — "전체 N행 미리보기" 링크 오정렬 수정 (2026-06-09)
- [x] 근본: `_collapse_large_tables` 위치-인덱스 매칭 → 값 토큰 overlap + 컬럼수 폴백 매칭으로 교체 (`_distinctive_tokens`/`_md_table_body_cells`/`_md_table_col_count`/`_csv_signatures`/`_match_csv_for_table`). 형태 불일치 보조쿼리(MIN/MAX) CSV 배제.
- [x] 회귀 테스트 `tests/test_collapse_table_csv_match.py` (값매칭·무매칭생략·형태폴백·토큰필터 4종)
- [x] make test 컨테이너 PASS (0 fail) + ruff PASS
- [x] §18.8 검증 패널(SUBAGENT) → REV-20260609-0173, MAJOR 2건(측정값-only 표 링크소실/JS 오탐) FIX-FIRST 반영(컬럼수 폴백 + JS 임계≥2)
- [x] verify-completion PASS(9 checks) → 커밋 → push → main ff-merge(2b4da2a) → 재배포(web+ask-worker, healthz git_commit 일치·베이킹/서빙 확인) → 라이브 PB-0008 무회귀 확인 (collapse+링크 경로는 LLM 렌더 비결정성으로 온디맨드 재현 불가 — 회귀테스트가 결정적 증거)

### TASK-0175 — 실행 단계 reason(왜) derived fallback (2026-06-09)
- [x] **Minor §12.3** — 사용자 "각 단계 근거가 화면에 안 보인다" 재보고. 라이브 진단: 모든 step `work_source='derived'`·`reason_text=''`. 근본 ① SYSTEM_PROMPT 가 LLM 에 tool_notes(work/reason) 방출 미지시 → reason 미생성, ② reason 에 derived fallback 부재(work 와 달리). CHG-0173 프런트는 빈 reason 미표시라 표시할 데이터 자체가 없었음. (CHG-20260609-0175)
- [x] `_derive_step_reason(tool_name, args)` 신규 — `_derive_step_work` 대칭, tool 목적별 결정적 근거(execute_sql 은 집계/조회 분기). 미지원 tool=`""`.
- [x] 루프 배선: work 파생 직후 reason 도 비면 파생 + `reason_source='derived'`. LLM 참값 비덮어쓰기 가드.
- [x] 회귀 테스트 `tests/test_derive_step_reason.py` 4종(전 tool 비빔·집계vs조회·미지원 빈값·대소문자/None 방어). make test 컨테이너 **269 passed/2 skipped**(회귀 0). outside-voice [SKIPPED:display-metadata] (REV-20260609-0175).
- [ ] verify-completion PASS → 커밋 → push → main ff-merge → **재배포(ask-worker+web — 실행모드=worker 라 agent 루프는 ask-worker 컨테이너)** → 라이브 ask 후 step reason 노출 확인

### TASK-0177 — 실행 단계 근거를 LLM 이 실제 맥락으로 생성 (SYSTEM_PROMPT tool_notes 지시) (2026-06-10)
- [x] **Major §12.3** — 사용자 원의도: derived 템플릿이 아니라 **LLM 이 질문 맥락에 맞춘 실제 근거**. 근본 공백(SYSTEM_PROMPT 가 tool_notes 미지시)을 메움. TASK-0175 derived 는 비순응 안전망으로 유지. (CHG-20260610-0177)
- [x] `SYSTEM_PROMPT` 에 `## STEP NARRATION (tool_notes)` 섹션 — tool 호출 턴마다 content 에 `{"tool_notes":[{work,reason}]}` 방출(call 당 1 entry 동순서), reason 은 사용자 목표에 비춘 구체 근거. tool call 없는 턴엔 JSON 금지. OUTPUT 보강.
- [x] **B1 sanitizer**(outside-voice BLOCKER): `_strip_leaked_tool_notes` + 최종답변 배선 — 누수된 envelope 결정적 제거(통째면 빈문자열→재요청 루프). 프롬프트 억제 + 백엔드 fail-closed 이중.
- [x] 프롬프트 보강: M1 "i번째 note↔i번째 call(병렬 포함)", m1 따옴표 escape, m2 "tool call 없는 모든 턴".
- [x] 회귀 테스트 `tests/test_tool_notes_prompt.py` 9종(프롬프트 지시 존재·파서 라운드트립[멀티/펜스/패딩/절단]·sanitizer 4). make test 컨테이너 **278 passed/2 skipped**(회귀 0). py_compile OK.
- [x] outside-voice 적대적 리뷰 NEEDS-TWEAK→FIXED, BLOCKER 1 흡수 + MAJOR 3 반영/위임 (REV-20260610-0177).
- [ ] verify-completion → 커밋 → push → main ff-merge → **재배포(ask-worker+web) + 라이브 `WebSystemPrompts` global row 새 상수로 갱신**(GLOBAL row 가 상수 대체) → **카나리아: `reason_source='llm'` 비율 실측(M2) + 최종답변 JSON 누수 0 + 근거 맥락성 확인**

### TASK-0178 — 단계 근거를 LLM 이 생성: tool 인자(reason/work)로 전환 (2026-06-10)
- [x] **Major §12.3** — TASK-0177(content tool_notes) 전달 메커니즘 수정. **라이브 확정**: 0177 배포 후 카나리아 전 step `reason_source=derived`, core_messages content=`{"tool_notes":[{"work":"","reason":""}]}` → **Bedrock gateway 가 tool_use 턴 text content strip**(REV-0177 M2 실현). (CHG-20260610-0178)
- [x] tools.py: 전 도구 스키마에 optional `reason`/`work` 주입(`_inject_step_narration_params`, properties 맨 앞=think-first, required 제외). reason 설명=질문 맥락 구체 근거.
- [x] agent_core: 루프에서 `tool_args.pop("work"/"reason")` 추출(실행/저장 전 제거) + 우선순위 arg→content→derived. SYSTEM_PROMPT 를 "tool 인자 reason/work 채워라"로 교체.
- [x] 회귀 테스트 `tests/test_step_narration_params.py` 4(전 도구 주입·core 공유·think-first 순서·핸들러 추가인자 무해) + `test_tool_notes_prompt.py` 프롬프트 테스트 갱신. make test **282 passed/2 skipped**(회귀 0).
- [x] **머지 전 라이브 probe 카나리아 PASS**: worktree 배포+row 갱신 후 2 ask → **5 step 전부 `reason_source='llm'`**, 근거 질문 맥락 직결, 누수 0, 답변 정확. (REV-20260610-0178)
- [ ] verify-completion → 커밋 → push → main ff-merge → 머지판 재배포(GIT_COMMIT 정상 각인) → 최종 카나리아 재확인

### TASK-0196 — convo_search 도구 AR-M5 cutover 라우팅 누락 복구 (2026-06-10)
- [x] **Minor §12.3** (에이전트 도구 읽기경로 라우팅, RBAC·스키마·파괴 0) — 사용자 요청("mysql→PG 이관 미완으로 작동 안 하는 부분 검토")의 전 서비스 스윕 산물. web 3건은 feature-0003 TASK-0196. (CHG-20260610-0196)
- [x] **결함**: `convo_search`(LOCAL agent tool — 다른 대화 기록을 메시지/요약/주제로 검색)가 `modules/file_ops.py` 에서 PG 경로 전무한 채 삭제된 MySQL `AgentMemoryMessages`/`AgentMemorySummary`/`AgentMemoryKv` 3개를 `try/finally`(except 없음)로 조회 → 에이전트가 도구 호출 시 첫 쿼리에서 **throw**(도구 기능 사망). 정적 스윕(file_ops 가 `_pg_connect`/`agent_runtime`/`AGENT_RUNTIME_READ_BACKEND` 전혀 import 안 함)으로 확정.
- [x] **수정** ([src/modules/file_ops.py](../src/modules/file_ops.py)): `AGENT_RUNTIME_READ_BACKEND == "postgres"` 일 때 PG `agent_runtime.messages`/`summary`/`kv` 로 라우팅. ILIKE = MySQL utf8mb4_unicode_ci case-insensitive 패리티. PG `kv.key`/`value`(비예약어) unquoted, `include_current` 필터·`_format_row`(conv_id,role,content,created_at,source) 컬럼순서 동일. legacy MySQL else 보존.
- [x] 회귀 테스트 `tests/test_convo_search_pg_routing.py`(PG 라우팅 + 전달된 MySQL conn 미사용 가드 + 3 소스 모두 검색 + current 대화 제외). make test(컨테이너 pytest+ruff) exit=0(0002+0003 전체 회귀 0).
- [x] outside-voice 적대적 백엔드/QA 검토 SHIP(MAJOR 0) — REV-20260610-0196.
- [ ] verify-completion → main ff-merge → agent-core 서비스(ask-worker/insight-worker/web) 재배포 → 라이브 에이전트 convo_search 호출 검증.

### TASK-0200 — convo_search LIKE 메타문자 이스케이프 하드닝 (2026-06-10)
- [x] **Minor §12.3** (도구 읽기경로 하드닝, RBAC·스키마·계약 무변경) — REV-20260610-0196 이 지적한 MINOR 잔존의 실행. `convo_search` 가 `like_pattern = f"%{pattern}%"` 로 사용자 질의를 LIKE/ILIKE 패턴에 직접 끼워 `%`/`_` 가 와일드카드로 처리("100%"/"table_name" 등 오작동·과다매칭). `_collect_matched_excerpts` 와 동일하게 메타문자(`!`,`%`,`_`) 이스케이프(`!` 먼저 → `%`/`_`) + `ESCAPE '!'` 동반. 빈 질의는 전체 매칭(`%`, ESCAPE 없음) 유지. (CHG-20260610-0200) (#2 발췌 정렬은 web, feature-0003 TASK-0200.)
- [x] PG 분기(content/summary/value ILIKE) + MySQL legacy 분기(Content/Summary/`Value` LIKE) 6절 모두 `{like_escape}` 적용. like_pattern·like_escape 양 분기 공유(단일 소유).
- [x] 회귀 테스트 `tests/test_convo_search_pg_routing.py` 2 추가(메타문자→`%100!%!_x!!%`+ESCAPE 동반 / 빈 질의→`%`+ESCAPE 없음). make test exit=0(0002+0003 전체 회귀 0), ruff clean.
- [x] outside-voice [SKIPPED:minor-escaping-implements-REV-0196] (REV-20260610-0200).
- [ ] verify-completion → main ff-merge → agent-core 서비스 재배포 → 라이브 convo_search 메타문자 질의 검증.

### TASK-0201 — 멀티 datasource Stage 2 P6: MSSQL 보안경계 + 실 인스턴스 검증 (2026-06-10)
- [x] **Major §12.3** (멀티엔진 보안경계 — RBAC/데이터격리 면, outside-voice 필수). DESIGN-multi-datasource.md §3.4/§10/§11.
- [x] **축1 AST allowlist** (Codex-1): `_extract_sql_schema_refs` 정규식 → `sql_guard.collect_schema_refs`(활성 dialect 파싱). `_collect_table_refs` 가 `.catalog/.db/.name`(unquoted) 사용 → 대괄호/3-part/ANSI/백틱 우회(B-1) 봉쇄. 무자격 fail-closed + catalog cross-DB 차단(`_freeform_sql_access_error`). 레거시 단일 MySQL 무자격 허용(골든).
- [x] **축3 sql_guard dialect** (B-3): `validate_sql_for_sandbox(..., dialect=)` + sqlglot tsql 파싱. T-SQL denylist(xp_cmdshell/OPENROWSET/OPENQUERY/OPENDATASOURCE/WAITFOR/EXEC/sp_executesql/SELECT INTO/@@) + dialect 금지함수. into 이중차단(denylist+AST).
- [x] **m3 dialect 시스템/메타데이터 스키마**: Dialect 단일소유(A2/C1). MSSQL sys/INFORMATION_SCHEMA/guest/db_* 제외(dbo 유지), 항상허용=sys/INFORMATION_SCHEMA.
- [x] **M-4 부하게이트 fail-closed**: `Dialect.supports_load_estimate`(MSSQL=False) → gate 모드 사전차단. MySQL 골든(fail-open) 유지.
- [x] **Codex-6 confirm_heavy 비-LLM**: `AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM`(기본 true=현행, false=모델 자기우회 차단). UI 승인 P7 이월.
- [x] **Codex-2 GRANT 모델**: `bin/datasource-mssql-ro-bootstrap.sql` — db_datareader 금지, 전용 role 에 허용스키마만 GRANT SELECT, 0단계 서버 prereq(xp_cmdshell/cross-DB chaining/Ad Hoc Distributed Queries OFF) 검증. `sqlcmd -b` 필수.
- [x] **Codex-5/7 결정**: AST 재직렬화 미채택(원문실행 유지+denylist+pin, 잔존위험 명시) / 세션reset 아키텍처 해소(MSSQL fresh connect, MySQL pool_reset_session).
- [x] **§3.5 grounding 방언 주입**: 활성 엔진 mssql 이면 `_MSSQL_DIALECT_GUIDANCE`(TOP/대괄호/스키마명시/cross-DB금지/T-SQL함수) system prompt 주입.
- [x] 회귀 테스트 `tests/test_mssql_security_boundary.py`(dialect 매트릭스·B-1 우회·정책·M-4·Codex-6). 전체 스위트 RC=0(0002+0003 회귀 0), ruff 통과.
- [x] **실 MSSQL 검증**(사용자 Windows `172.28.64.1:14330`, dk_data_release): 최소권한 RO 생성 후 도구 전부 동작 + 보안경계 6/6 차단 + 2축 방어 실증(앱+DB GRANT). P5 dialect 버그 4건 수정(DMV 권한→sys.partitions / DB 고정 / row 컬럼 / index·FK dialect). 서버 xp_cmdshell ON 발견(앱·GRANT 로 무력화, 운영자 OFF 권고).
- [x] **outside-voice 적대적 보안 재게이트(MANDATORY)** REV-20260610-0201: 1차 REJECT(실 인스턴스 데이터 탈취 재현) → B1(BLOCKER 구조화도구 `]` 2차 SQLi)·M1(MAJOR sys 항상허용 유출)·M2(MAJOR gate confirm_heavy 우회) 수정 → 2차 **SHIP**. 라이브 재검증 PASS, 회귀테스트 추가, 전체 스위트 RC=0.
- [ ] 커밋 → main ff-merge → P6 배포(agent/ask-worker/insight-worker/web) → winsql datasource 등록+product 바인딩 → 라이브 assistant·insight-worker 검증.

### TASK-0203 — 멀티 datasource Stage 2 P7: insight-worker MSSQL dialect-화 (2026-06-11)
- [x] **Major §12.3** (insight 엔진 분기 — 데이터격리 무변경, 핑거프린트 livelock 면 주의). DESIGN §12.
- [x] **컬럼 핑거프린트 dialect projection**: `Dialect.fingerprint_column_projection()` (MySQL 골든 / MSSQL `CHARACTER_MAXIMUM_LENGTH`·KEY 상수 — SQL Server INFORMATION_SCHEMA 엔 COLUMN_TYPE/COLUMN_KEY 부재). insight.py 의 single/batch 컬럼 핑거프린트가 사용. FROM/WHERE 공통(ANSI) 유지·parameterized.
- [x] **engine-passing 버그 수정**: `run_insight_cycle` 의 `set_active_datasource(_ds_key)` → `engine=_ds_coords.get("engine")` (dialects.active() mysql 오인 차단).
- [x] **livelock 방지 확인**: write·read-back 동일 set_active_datasource(engine) 컨텍스트 → 동일 projection. 라이브 단일≡배치 해시 동일·결정성 STABLE.
- [x] 회귀테스트 `test_multi_datasource.py` 3종(MySQL projection 골든 / MSSQL MySQL-only 컬럼 부재 / active 엔진 분기). 전체 스위트 RC=0, ruff clean.
- [x] **실 MSSQL 검증**(dk_data_release CI): 컬럼/스키마/배치 핑거프린트 전부 동작(COLUMN_TYPE 실패 해소).
- [x] outside-voice 적대적 리뷰 REV-20260611-0203 (livelock 중심) **SHIP**(BLOCKER0·MAJOR0). MINOR 3 후속.
- [x] **라이브 cycle 검증 중 2 버그 발견·수정(P3 이래 잠복, 실 datasource 연결로만 노출)**: ① insight.py 의 `connect_with_retry` 가 `from .config import *` 로 **`modules.utils` 구버전**(datasource 인자 없음)에 바인딩 → winsql 순회가 매 cycle `TypeError` → **`modules.db` 의 datasource 지원판 명시 사용**(`_db.connect_with_retry`). ② per-datasource isolation 핸들러가 `logging.getLogger` 쓰는데 insight.py 가 **`logging` 미import**(config `__all__` 제외) → datasource 예외 시 핸들러가 NameError 로 재폭발(격리 실패) → `import logging` 추가. 둘 다 단일 MySQL 시절엔 미발현.
- [x] 라이브 LLM 인사이트 생성 검증: winsql `dbo.Item` payload → `llm_table_insight`(edge/로컬 게이트웨이) 정상 dict 산출(domain/summary/key_columns, 5.8s).
- [x] **sweep 3차(라이브 cycle 추가 발견)**: ③ `schema.py` `load_known_schemas` 가 백틱 인용 `information_schema.SCHEMATA`(MSSQL `Incorrect syntax near '`'`) → `_dialects.active().list_schema_names()`(MySQL 골든 동치/MSSQL sys.schemas)로 교체. ④ datasource 순회가 dialect 시스템 스키마(MSSQL guest/db_*)를 못 걸러 RO-거부 노이즈 → `_dialects.active().system_schemas()` 로 datasource 경로 필터(MySQL 경로 미변경). 라이브: `load_known_schemas(winsql)` → 필터 후 `['dbo','dev50']`.
- [ ] 커밋 → main ff-merge → insight-worker 재배포 → 라이브 winsql 인사이트 생성·publish 관측.
- [ ] (P7 잔여·후속) UI engine 배지 + MINOR-1 CS-collation 대문자 통일.

### TASK-0219 — datasource-aware rag_objects + 엔드포인트-해시 스코핑 (2026-06-11)
- [x] **문제 1 (RAG 구조 불일치)**: ds-스코프 fact 키 `{source}:ds:{ds}:{suffix}` 가 도입됐으나 `utils._infer_rag_object_from_fact` 가 `ds:winsql:dbo` → schema `dswinsqldbo`(쓰레기)로 망가뜨려 **ds rag_objects 0건**(ds rag_documents 1753건 존재에도). rag_objects 에 datasource 컬럼·검색 ds-필터 부재.
- [x] **문제 2 (스코프 키 불안정)**: 동시 TASK-0216/0218 로 `DatasourceKey` 가 admin rename 가능한 단순 라벨이 됨(`_generate_datasource_key`=엔진+호스트+포트 SHA-256). 라벨로 스코핑하면 rename 시 누적 insight 가 고아.
- [x] **파서 수정**: `:ds:{key}:` 접두 분리 → schema/table 정규화(`dbo`/`T_ItemLog`) + datasource_key 추출 + object_key 에 ds 접두(`{hash}:dbo.t`)로 cross-ds 유일성(UNIQUE `(conv,scope,type,object_key)` 불변). 6-tuple 반환.
- [x] **스키마**: `rag_objects.datasource_key VARCHAR(64)` 컬럼 + 필터 인덱스(alembic `0004_rag_objects_datasource`, ADD COLUMN, 무손실). 라이브 적용(0003→0004).
- [x] **쓰기/검색**: `upsert_rag_object`(base/MySQL/PG/Dual) datasource_key 전달 + `_PG_UPSERT_RAG_OBJECT` 컬럼/DO UPDATE. `search_rag_objects` 가 `get_active_datasource()` 로 ds-필터(`ds_fact_like` 동형 심층방어).
- [x] **엔드포인트-해시 스코핑**: `datasources.compute_scope_key/scope_key`(web `_generate_datasource_key` 동일 공식) — fact/RAG 스코핑 식별자를 라벨이 아닌 **engine+host+port 해시**로 고정. agent_core ask 경로 + insight 루프의 `set_active_datasource` 가 scope_key(해시) 사용 → 라벨 rename 에도 누적 지식 불변. 격리 모델 무변경(per-datasource, 엔드포인트=신원).
- [x] **jsonb ON CONFLICT 버그 수정(잠재)**: `category_join_hints_json`(jsonb) 의 `NULLIF(EXCLUDED.., '')` 가 ''를 jsonb 캐스팅하려다 **모든 rag_object conflict-갱신 실패**("invalid input syntax for type json") → NULLIF 제거(COALESCE, 호출부 None 전달). varchar category_* 는 NULLIF 유지. S5 invariant 정정.
- [x] **재키잉 스크립트**(`scripts/rekey_datasource_facts.py`): 옛 라벨(`main_mysql`/`winsql`/`mssql_local`) fact_entries/rag_documents 를 라이브 레지스트리 엔드포인트 해시로 재키잉(per-row `_fit_fact_key_storage` 절단 정합 + 병합) + rag_objects 재생성. 멱등·--dry-run·멀티-같은엔진 가드.
- [x] **회귀테스트**: `test_infer_rag_object_datasource_scoped`(ds 분리) + `test_scope_key_is_endpoint_hash_and_label_agnostic`(엔드포인트 해시·라벨독립). 호스트 391 passed, 컨테이너 make test RC=0.
- [x] **외부시각 적대적 리뷰(격리 경계)**: SHIP — 데이터 유출/격리 붕괴 BLOCKER 없음. 동일-엔드포인트·상이-경계 datasource 의 insight 병합은 비표준 구성·메타데이터 한정·4중 backstop(product 바인딩+allowlist+AST+RO-GRANT). Q4 멀티-같은엔진 재키잉 가드 반영.
- [x] **배포·라이브검증**(main dc3f0b0): web/ask-worker/insight-worker/agent 재빌드 + 마이그 적용 + 재키잉/백필. 검증: ds rag_objects 342(mysql-ddae8975d793=179 / mssql-f82c51b3425f=163), schema 망가짐 0(`dbo` 깨끗), no-ds 객체 788 NULL 보존, 제품1/7/8→mysql해시·90/91→mssql해시 resolve, retrieval ds-필터(active=mssql)→mssql 객체만 165(유출0).

### TASK-0256 — assistant 답변 diff 블록: SYSTEM_PROMPT diff 출력 지침 (2026-06-15)
- 목표: 첨부파일/사용자 쿼리 리뷰·편집 응답에서 변경(수정 SQL·편집본)을 markdown ```diff 블록으로 제시하도록 base SYSTEM_PROMPT 가 지시.
- [x] SYSTEM_PROMPT OUTPUT 섹션 뒤 "## SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK" 추가 (리뷰/편집 한정, 신규 SQL 작성은 ```sql 유지)
- [x] test_compose_system_prompt: SYSTEM_PROMPT 가 ```diff·DIFF BLOCK 포함 + OUTPUT 이후 위치 검증 (4 passed)
- [x] 라이브 WebSystemPrompts global row 갱신 — 적용완료(5799→6837자, 마커 검증 True, 컨테이너 백업 /tmp/task0256_global_prompt_backup.txt)
- [x] ask-worker 재배포(main 2befd37) + SYSTEM_PROMPT diff 지침 baked 검증

### TASK-0256e — 첨부파일 diff 줄번호 추적 (실제 파일 줄번호 기반 헌크 헤더) (2026-06-15)
- 사용자 보고: 첨부 파일 리뷰 diff 의 줄번호가 항상 1부터(또는 없이) — 실제 파일 줄 미추적.
- 근본원인: `_build_attachment_context_section` 이 첨부 본문을 줄번호 없이 raw 주입 → 모델이 실제 줄 모름 → `@@` 헌크 헤더 못 만듦 → 렌더러(buildDiffRows)는 헌크 없으면 1부터.
- [x] `_number_file_lines(content)`: 각 줄 `<N>→` prefix(우측정렬, prompt 사본만, 원본 무변경 — SQL추출 경로 무영향)
- [x] 본문 주입에 적용 + "LINE NUMBERS & DIFFS" instruction(실제 줄번호로 `@@ -N,M +N,M @@` 작성, prefix 코드 미포함)
- [x] test_attachment_line_numbers(5) + 렌더 폐루프 node 확인(`@@ -49` → gutter 49/50/51) + py_compile
- [x] ask-worker 재배포(main 63f4a5a) + baked 확인 + **라이브 LLM probe PASS**: 줄번호 첨부 → 모델 `@@ -4,2 +4,4 @@`(실제 줄번호) 헌크 출력·prefix 코드 미포함(TEST.md)

### TASK-0284 — 첨부 LLM 주입 스코프 conversation 통일 + 파일명 지칭 (Critical §12.3, 2026-06-16, feature-0003 주관)
- (feature-0003 TASK-0284 의 agent-core 측 변경) 첨부 LLM 컨텍스트 주입을 AccountId → ConversationId 스코프로 통일 + assistant 가 첨부를 파일명으로 지칭하도록.
- [x] `_build_attachment_context_section` 에 `conversation_id` 인자 추가 + PG/MySQL WHERE 를 conversation 우선 스코프(account 폴백, `_scope_by_conv`)로. 대화 접근권은 caller(app.py ask) 게이트.
- [x] `compose_system_prompt` + `_run_agent_core`(2610 호출부) conversation_id 전파
- [x] (이슈3) 첨부 포맷 파일명 우선: 목록 `- file "..." (attachment_id=..)`, csv/xlsx sandbox 라벨 `file "..."`, ATTACHED FILES 섹션에 "REFER TO ATTACHMENTS BY FILENAME" 지침
- [x] test_attachment_idor.py +4(conversation 스코프·account 폴백·파일명 우선) + make test 전체 회귀 0
- [ ] ask-worker 재빌드(agent_core baked) → 라이브 검증 — feature-0003 TASK-0284 와 함께 마감

### TASK-20260619T014034 — LLM provider 외부요인 제한(자격증명 만료) 명시 표면화 (Major §12.3, agent-core 면, 2026-06-19)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-19 -->
- 목표: Bedrock 등 외부 provider 장애(특히 AWS 키/자격증명 만료)로 LLM 응답이 막힐 때, 현재 raw 예외(`LLM 호출 오류: ExpiredToken`)/일반 에러로만 노출되던 것을 서비스 사용자가 여러 surface 로 명시 확인하도록. 사용자 결정: 범위=외부요인 제한(사용량/쿼리부하 아님), UI=인라인+패널+컴포저+툴팁 직/간접 다중, 감지=hybrid(passive+probe).
- [x] 신규 `modules/llm_provider_health.py`: `classify_llm_provider_error`(예외→{kind,provider,message,retryable,error_tag}, credential_expired/auth_invalid/throttled/unavailable/not_configured/unknown) + PG upsert/read(`agent_runtime.llm_provider_health`) + active `probe_provider`(max_tokens=1, TTL throttle).
- [x] agent_core: LLM 호출 예외 경로(`_call_llm` 2931)에서 분류→친화 메시지 치환 + passive `record_provider_restricted`; 성공 시 `record_provider_ok`(run 당 1회, try/except/else); 무자격증명(2568)→not_configured; `result["llm_restriction"]` 필드.
- [x] 스키마: `agent_runtime_schema.sql` §6e bootstrap DDL + alembic `0011_llm_provider_health`(GRANT 포함 — 0006 DEPLOY TRAP 동형). 자격증명 비영속(state/kind/message/error_tag(클래스명만)/source/since 만).
- [x] (feature-0003) app.py: `_read_llm_provider_status` + `GET /api/llm/health`(인증 게이트·probe) + `/api/session`·`_build_ask_status_snapshot` 에 `llm_provider_status` 동봉.
- [x] (feature-0003) 프론트 4 surface: 컴포저 상단 배너 + footer 상태점/툴팁 + 대화 인라인 notice + 실행단계 패널 노트 + send title(indirect). `/api/llm/health` 폴링(60s)+로드 직후 probe+'다시 확인' force. 캐시버스터 bump.
- [x] 검증: `test_llm_provider_health.py` 14(분류·자격증명 비유출·폴백·not_configured) + `verify_llm_restriction_surface.mjs` 35(정적+jsdom 4-surface 토글) + feature-0002 전체 pytest 회귀 0(2 skip) + py_compile + node --check.
- [x] 적대 코드리뷰(outside voice, secret leakage/probe auth·cost/agent_core else/PG 폴백) → REV-20260619-0311.
- [ ] 배포: ask-worker + web 재빌드(agent_core·app.py baked) + 마이그 0011 적용 → 라이브 검증(restricted 주입 PB-0008 Windows-browser 4-surface, 실 키만료 e2e 는 운영 의존).
