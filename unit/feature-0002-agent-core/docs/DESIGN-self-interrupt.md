---
doc_type: DESIGN
feature_id: feature-0002-agent-core
scope: feature
status: proposed
edit_policy: rewrite
source_of_truth: false
title: DESIGN — 무거운 쿼리 자가규제 (EXPLAIN 사전 게이팅 + per-query cap); self-interrupt 는 reconsider 로 보류
---

# DESIGN — LLM 오케스트레이터 자율 self-interrupt

> **상태: 설계 (proposed). 구현 전 PLAN-APPROVED + outside-voice 필수.** 위험 등급
> **Critical** (§12.3 — agent 실행 경계·동시성·in-flight 쿼리 강제 종료). ask-worker
> (out-of-process 실행, ADR-WEB-0004) 의 "위임+폴링" 패턴을 **tool 레벨**에 한 단계
> 더 적용한다.

## 1. 배경 / 문제

라이브 인시던트(2026-06-09): 분기 대화에서 "총괄 통계 집계" 요청 → agent 가 대용량
게임 테이블 집계 SQL 을 단일 step 에서 **5~6분씩** 실행(run `20260609061952-22ba2717`
의 step8=83s, step10=361s, step11=325s, 총 ~13분 후 정상 done). 그 동안:
- step 카운트가 멈춰 "처리 중, 단계 진행 안 됨" 으로 보임(실제론 진행 중).
- 무거운 집계가 primary MySQL 을 포화 → 가벼운 인증/폴링 쿼리가 web `read_timeout`
  (`WEB_DB_QUERY_TIMEOUT_SEC=8s`)을 초과 → `Lost connection 2013` burst → 다른
  요청들이 `_require_account` 에서 죽어 프런트 고아 "처리 중" 버블.

**무거운 쿼리 자체는 감수한다(가속 안 함).** 목표는 **agent 가 부하 과다를 스스로
인지하고 자율적으로 중단(self-interrupt)** 해 폭주를 막고 가진 정보로 마무리하는 것.

## 2. 현행 제약 (타당성 조사 grounding)

| 항목 | 현행 | 위치 |
|---|---|---|
| 실행 모델 | agent loop 동기 블로킹 — `execute_tool→_tool_execute_sql→db.execute_sql→cur.execute(sql)` 가 쿼리 끝까지 블록 | agent_core.py:2175, tools.py:573·596, db.py:221-241 |
| cancel 폴링 | loop 4지점(top/LLM후/tool전/tool후)에서만 — **쿼리 실행 중엔 미점검** | agent_core.py:2005·2043·2145·2177 |
| mid-query 중단 | **불가** — `KILL QUERY` 없음, `CONNECTION_ID()` 미포착, per-query timeout 없음, async 격리 없음 | (grep 결과 부재) |
| 최종 backstop | `run_timeout_sec`(=max(AGENT_TIMEOUT_SEC*3, EARLY_FINALIZE/1000), 라이브 900s) + `max_steps` — **loop 진입 시점에만** 점검 | agent_core.py:1995·2008·2004 |
| 부하 신호 | LLM 에 노출되는 부하 신호 **0**(elapsed/step 은 hard limit 에만 사용) | — |
| 자가 규제 | finalize(즉시답변, tool 중단 후 답), drift guard, step validation 존재 | agent_core.py:2016, memory.py:369 |

**결정적 제약**: 동기 블로킹 + KILL 부재. self-interrupt 는 "쿼리를 별도 스레드로
비동기 실행 + `CONNECTION_ID()` 포착 + 별도 monitor conn 에서 `KILL QUERY`" 라는
**신규 메커니즘** 없이는 불가능 — 이것이 설계의 심장이며 **기술 실현성 게이트(Phase 0)**.

## 3. 결정된 정책 (사용자, 2026-06-09)
- **권한 모델: LLM 판단만.** 부하 임계 자동 KILL(하드 가드레일) 없음 — 부하 기반
  중단은 전적으로 오케스트레이터 LLM 의 판단. **단, 부하무관 최종 backstop 으로
  기존 `run_timeout_sec`/`max_steps` 는 유지**(절대 상한 — 무한 미중단 방지). 즉
  "부하 때문에 일찍 끊을지" 는 LLM 이, "절대 한도" 는 run_timeout 이 담당.
- **범위: 전체 설계 한 번에** 확정 후 단계적 구현(Phase 0~5).

## 4. 아키텍처 (ask-worker run 내부에서 동작 — 신규 분산 큐 없음)

실행은 이미 ask-worker(out-of-process)에서 돈다. self-interrupt 는 그 `run_agent`
실행 **내부**에서 스레드로 구현 → 신규 서비스/큐 불필요(위험 최소).

```
run_agent loop (ask-worker process)
  └─ heavy tool(execute_sql) 호출 시 (flag=async 경로):
       1. monitor conn(전용)에서 쿼리 conn 의 CONNECTION_ID() 포착
       2. 쿼리를 worker thread/future 로 실행 (loop 는 비블로킹)
       3. loop 가 watch tick(예: 1~2s):
            - user cancel/finalize 폴링(기존 4지점 → 이제 mid-query 즉시 반영)
            - 부하 신호 수집(§5)
       4. soft 임계/주기 도달 시 **오케스트레이터 의사결정 지점**:
            - 부하 컨텍스트를 LLM 에 제시 → LLM 이 {계속 대기 | 중단} 판단
            - LLM 이 중단 선택 → monitor conn 에서 KILL QUERY <id>
       5. KILL 후: tool_result="부하 과다로 중단됨(가진 데이터로 답 또는 더 가벼운
          쿼리로 재시도)" → LLM 후속 판단(기존 finalize 류 경로 재사용)
  └─ 절대 상한: run_timeout_sec/max_steps 초과 시 무조건 break(기존)
```

### 4.1 컴포넌트
1. **비동기·중단가능 heavy tool 실행기** — execute_sql 을 thread/future 로 실행 +
   `CONNECTION_ID()` 포착. flag `AGENT_HEAVY_TOOL_ASYNC=off`(기본) 로 기존 동기 경로
   보존. (db.py/tools.py/agent_core.py 신규 경로.)
2. **mid-query KILL** — 별도 monitor connection 에서 `KILL QUERY <id>`. (DB 유저
   KILL 권한 검증 = Phase 0.)
3. **부하 관측 신호 수집기**(§5) — LLM 에 노출.
4. **오케스트레이터 의사결정** — LLM 판단만. 부하 컨텍스트 주입 + 중단 결정 경로
   + 프롬프트 정책. backstop = run_timeout/max_steps(부하무관 절대 상한).

## 5. 부하 관측 신호 (LLM 판단 입력)
LLM 이 "부하 과다" 를 판단하려면 관측 가능 신호가 필요(현재 0):
- (a) 현재 in-flight heavy 쿼리 경과시간 + 동시 실행 수(이 run 내).
- (b) MySQL `processlist` 의 활성 무거운 쿼리/대기 수(별도 RO 조회).
- (c) 직전 쿼리 latency 추세.
- (선택) ask-worker 동시 처리 job 수.
→ watch tick 마다 수집해 의사결정 지점에서 LLM system 컨텍스트/도구결과로 제시.

## 6. 핵심 위험 (why outside-voice 필수)
1. **엉뚱한 쿼리 KILL** — `CONNECTION_ID()` 포착과 `KILL QUERY` 사이 conn id 재사용
   race → 무관한 세션 KILL. 포착-실행-KILL 을 동일 conn lease 로 fencing, KILL 전
   processlist 로 쿼리 동일성 재확인.
2. **부분 결과/일관성** — KILL 된 쿼리의 부분 상태. SELECT(읽기)라 데이터 변형은
   없으나, cursor/conn 상태 정리 + autocommit 경계 확인. KILL 후 그 conn 폐기.
3. **KILL 권한** — 데이터 DB 유저(`AGENT_DATA_DB_USER` RO)가 자기 세션 `KILL QUERY`
   가능한지(보통 자기 쿼리는 가능, 타 세션은 `CONNECTION_ADMIN` 필요). **Phase 0 검증.**
4. **LLM-only 미중단/과중단** — 하드 가드레일이 없으므로: LLM 이 영영 중단 안 하면
   `run_timeout`(900s) 이 최종 backstop(부하무관). LLM 이 과하게 중단하면 작업 미완 →
   프롬프트 정책 + 의사결정 빈도 튜닝. (가드레일 미채택은 사용자 명시 결정 — 트레이드
   오프 문서화.)
5. **스레드 안전성** — mysql.connector conn 은 thread-unsafe. query conn / monitor
   conn / mem conn 을 **스레드별 분리**. 포착·KILL 은 monitor conn 전용.
6. **기존 cancel/finalize/run_timeout 과의 상호작용** — 4중 폴링 + 신규 watch tick +
   KILL + finalize 의 시맨틱 충돌 방지. self-interrupt 는 cancel 과 구분(사용자 취소 vs
   agent 자율 중단)되어 별 status/메시지.
7. **무거운 쿼리 동시성 폭주** — 비동기화가 동시 실행을 늘릴 수 있음. (현재는 단일
   step 직렬이라 영향 작으나) per-run heavy-query 동시 실행 1로 제한(직렬 유지) — 병렬
   fan-out 은 본 설계 범위 밖(별도).

## 7. 롤아웃
flag `AGENT_HEAVY_TOOL_ASYNC=inprocess(동기,기본)|async`. off→canary→on. 동기 경로
(현행)는 async 가 프로덕션 검증될 때까지 보존, env 한 번에 rollback.

## 8. 단계적 plan
- **Phase 0 (실현성 게이트 — 필수 통과)**: 라이브에서 데이터 DB 유저로
  `SELECT CONNECTION_ID()` 포착 + 별도 conn `KILL QUERY <id>` 가 in-flight 무거운
  쿼리를 실제로 끊는지 PoC. **실패 시 설계 전면 재검토**(KILL 불가면 self-interrupt
  불가 — 대안: per-query `max_execution_time` 힌트 또는 statement timeout).
- **Phase 1**: 비동기·중단가능 heavy tool 실행기(thread + connection_id 포착) +
  mid-query **user cancel** 즉시 반영(KILL). flag off 기본. (즉효 UX: 사용자 취소가
  쿼리 중에 먹힘.)
- **Phase 2**: 부하 관측 신호(§5) 수집 + LLM 컨텍스트 노출.
- **Phase 3**: LLM 자율 의사결정 경로(중단 결정 + KILL) + 프롬프트 정책 + self-interrupt
  status/메시지.
- **Phase 4**: 롤아웃 flag(off→canary→on) + 회귀테스트 + 부하 시나리오 + PB-0008.
- **Phase 5**: outside-voice 적대적 diff 리뷰 + docs.

## 9. 검증 계획
- 단위: connection_id 포착·KILL race(동일성 재확인)·thread별 conn 격리·부하 신호
  수집·self-interrupt status·flag off 동기경로 무변경.
- 통합: 라이브 무거운 쿼리 mid-flight KILL→conn 폐기→LLM 후속(가벼운 재시도/부분답);
  사용자 취소가 쿼리 중 즉시 반영; run_timeout backstop 동작.
- 부하: LLM 이 부하 신호 보고 중단 결정; 미중단 시 run_timeout backstop.
- make test 회귀 0 + py_compile + outside-voice.

## 10. outside-voice 적대적 설계 리뷰 결과 (2026-06-09) — **RECONSIDER-APPROACH**

general-purpose subagent 적대적 리뷰(feedback_outside_voice_for_rbac 정책)가 **구현 전 재검토** 판정. 핵심:

- **BLOCKER C — "LLM 판단만" 은 내부 모순(구현 불가, 사용자 정책 재확인 필요)**: LLM 은 호출돼야만 동작. 비동기 쿼리 중 *언제 LLM 에게 "중단?" 을 물을지* 는 **비-LLM 휴리스틱(consult-cadence)** 이 정해야 함 = 사실상 가드레일(사용자가 거부한 바로 그것). 순수형(매 tick LLM 폴링)은 6분 쿼리당 ~180+ LLM 호출 = 비용/지연/부하 자체 증가로 비현실. → "고정 consult 주기 + LLM 최종 판단" 으로 재정의해야 하며 이는 사용자가 승인한 "임계 없음" 과 **다름 → 재승인 필요**.
- **BLOCKER E — 단일 `db_conn` 공유 생명주기**: 현재 run 전체가 conn 1개(agent_core.py:1902) 재사용. KILL 후 그 conn 은 에러 상태 → 다음 step 마다 `Commands out of sync`. → 무거운 쿼리는 **전용 conn 신규 개방**, KILL 시 그 conn 만 폐기, 쿼리 스레드 reaping(KILL 실패/run_timeout/SIGTERM 시) 필수.
- **MAJOR A** — `agent_ro` 가 자기 세션 KILL 은 가능(같은 계정)하나 Phase 0 는 **실제 집계 쿼리류**로 테스트해야(SLEEP PoC 무의미). `MAX_EXECUTION_TIME` fallback 은 LLM-driven 논지와 모순 + 집계에 미적용 가능 → fallback 아님.
- **MAJOR B** — connection_id 재사용 race. thread-id 만으론 부족 → SQL 에 `/* run=.. step=.. */` 마커 삽입 후 processlist `INFO` 마커 일치 시에만 KILL.
- **MAJOR D — self-interrupt 가 인시던트를 못 고칠 수 있음**: LLM 은 자기제한에 약해 "계속 대기" 를 택하기 쉬움 → 무거운 쿼리가 run_timeout(900s)까지 그대로 → 인시던트보다 악화 가능. run_timeout 은 per-run(per-query 아님)이라 primary 포화를 못 막음.
- **MAJOR G — 부하신호 (b) processlist 는 `agent_ro` 로 불가**(PROCESS 권한 없음 → 자기 스레드만 보임). 부여하면 보안모델(최소권한) 약화. 실제 포화 신호(web read_timeout 초과)는 **다른 프로세스(web)** 에 있어 worker 에서 미관측. → primary 에 `SELECT 1` canary latency probe(RO 가능)로 대체 권장.
- **MAJOR F** — cancel KV 가 이미 이중용도(user-cancel + lease-loss fencing). self-interrupt 가 이를 재사용하면 run 전체가 멈춤(의도 반대). 별도 in-thread 신호로 cancel 경로에서 **분리** + lease-loss 우선순위 명시.

### 최강 대안 (리뷰 권고)
- **replica 라우팅(우선)**: 인시던트의 본질은 "무거운 읽기가 primary 를 포화 → 가벼운 auth/poll 쿼리 starve". `db.py:115` 에 **REPLICA_DB 라우팅 코드가 이미 있으나 dormant**(REPLICA_DB_ENABLED 미설정). 데이터-plane 읽기를 replica 로 보내면 **신규 스레드/KILL/LLM 머신 0 으로 primary 健全 유지** = 인시던트 직격 해소. (단 데이터 DB 의 read replica 가용성 확인 필요.)
- **EXPLAIN 사전 게이팅**: `_tool_explain_query`(tools.py:628) 이미 존재 → 실행 전 예상 rows 임계 초과 시 LLM 에게 쿼리 축소 유도 → 6분 쿼리가 *시작조차 안 함*.
- **per-query wall-clock cap**(statement-level): 900s per-run 보다 나은 backstop.

### 판정
self-interrupt 는 **가장 복잡·고위험**(Critical) 이고 LLM 의 자발적 중단 선택에 의존해 **인시던트를 못 고칠 수도** 있음. 고유 가치(부분답 조기 반환)는 가용성 fix 가 아니라 UX. → **replica 라우팅으로 primary 를 먼저 안전하게 만든 뒤** self-interrupt 는 (추진 시) C(정책 재정의)·E(전용 conn) 를 gating BLOCKER 로 해결하고 진행. **status: reconsider — 본 설계 그대로 구현하지 않음.**

## 11. 확정 방향 (사용자 결정 2026-06-09) — EXPLAIN 사전 게이팅 + per-query cap

self-interrupt(mid-query KILL) 는 **보류**. 사용자 의도("agent 가 무거운 부하를 스스로 회피·규제, 단 필요시 무거운 쿼리는 감수")를 모순·고위험 없이 충족하는 **사전(pre-execution) 자가규제** 로 전환. 위험등급 **Major**(KILL/스레드/async/동시성 변경 없음 — execute_sql 경로에 사전 점검 + 시간 cap 추가, flag-gated, 비파괴 추가).

### 11.1 메커니즘
1. **EXPLAIN 사전 게이팅 (자동·transparent)** — `_tool_execute_sql`(tools.py:573)이 `_raw_execute_sql` 전에 내부적으로 `EXPLAIN FORMAT=JSON {sql}` 실행 → 예상 스캔 rows 추정. 임계 초과 + 미confirm 이면 **쿼리 실행 대신** LLM 에 gate 메시지: "예상 ~X행 스캔(무거움). WHERE/LIMIT/집계범위를 좁히거나, 정말 필요하면 `confirm_heavy: true` 로 다시 호출하세요." LLM 이 좁히면 부하↓(자가규제), 필요하면 confirm 으로 그대로 실행("감수" 존중). EXPLAIN 실패 시 fail-open(그대로 실행 — 게이트가 정상 작업을 막지 않음).
2. **per-query cap (MAX_EXECUTION_TIME)** — execute_sql 은 sql_guard 로 단일 SELECT/CTE only 라 `MAX_EXECUTION_TIME` 적용 가능. 쿼리당 시간 상한(`SET SESSION max_execution_time` 또는 `/*+ MAX_EXECUTION_TIME(ms) */`)을 **관대하게** 설정(정상 5~6분 쿼리를 끊지 않음 — "감수") → 진짜 폭주(>cap)만 서버가 중단 → LLM 에 "시간 초과, 좁히세요". 기본 generous/off, 폭주 backstop 용.

### 11.2 설정 (config)
- `AGENT_QUERY_GUARD_MODE` = `off`(기본, 현행) | `warn`(실행하되 비용 경고 prepend) | `gate`(임계 초과 시 confirm 전 차단). 롤아웃 off→warn→gate.
- `AGENT_QUERY_EXPLAIN_ROWS_WARN` = EXPLAIN 추정 rows 임계(기본 예: 1,000,000).
- `AGENT_QUERY_MAX_EXECUTION_MS` = per-query 시간 cap(기본 0=비활성/generous; 폭주 방지용으로만).
- execute_sql tool 스키마에 `confirm_heavy: bool` 추가 + 프롬프트에 "gate 시 좁히거나 confirm_heavy 로 진행" 정책.

### 11.3 이 방향이 해결/미해결
- ✅ 무의미한 runaway 쿼리 자가회피(LLM 비용 인지 → 좁힘) + 폭주 시간 상한.
- ⚠️ *정상* 5~6분 쿼리의 UX(frozen step)·collateral 포화는 직접 해결 X — 그건 replica 라우팅(인프라) 영역. (사용자 결정으로 본 cycle 범위 밖, 이월.)
- self-interrupt 의 고유 가치(부분답 조기 반환)는 미구현(보류).

### 11.4 plan (Major)
1. config `AGENT_QUERY_*` + execute_sql 에 EXPLAIN 추정 헬퍼(`_estimate_explain_rows`) + gate 분기 + `confirm_heavy` arg.
2. MAX_EXECUTION_TIME cap 주입(SELECT 한정, generous).
3. 프롬프트 정책 1줄 + tool 스키마 갱신.
4. 단위테스트(추정 파서·gate 분기·confirm override·cap 주입·flag off 무변경) + make test 회귀 0.
5. outside-voice diff 리뷰(query-path 변경) + docs(MODIFY/REVIEW/TASK/FUNCTION).
6. 배포(flag off→warn canary→gate) + 라이브 검증.

### 11.5 outside-voice diff 리뷰 흡수 (2026-06-09, TASK-0172)
구현 diff 적대 리뷰 verdict **FIX-BEFORE-ENABLING-GATE**(off-default 라 머지 안전, sql_guard 무변경). 수정 흡수:
- **M1** — `confirm_heavy` 가 문자열 "false" 일 때 `bool("false")==True` 로 게이트 우회 → true/1/yes 또는 bool True 만 confirm 인정(회귀테스트 추가).
- **M2** — `MAX_EXECUTION_TIME` 은 session-scoped·sticky(공유 conn) — docstring 정정(per-query 오기 → 세션 스코프 backstop).
- **m3** — rows 곱이 `filtered` 무시해 잘 인덱싱된 join 과대추정 → `rows × filtered/100` 반영(false-positive 게이팅 감소).
- **m4** — 미지원 `AGENT_QUERY_GUARD_MODE` 값 → config 에서 off 로 정규화.
- m5(EXPLAIN 실패 fail-open) 수용(confirm_heavy escape + cap backstop 존재). make test 회귀 0(신규 test_query_guard 15).

