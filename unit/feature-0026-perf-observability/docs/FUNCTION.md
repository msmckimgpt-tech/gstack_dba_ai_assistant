---
doc_type: FUNCTION
feature_id: feature-0026-perf-observability
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
성능 병목을 **측정**하기 위한 관측(observability) 인프라. 2026-07-27 전수 성능 조사에서
확인된 계측 사각지대 — ① HTTP per-route 지연·요청당 DB 커넥션 수 (web) ② 워커 LLM 호출
latency 전무 (llm_usage.latency_ms NULL) ③ 답변 파이프라인 단계별 분해 부재 (redteam /
post-answer / grounding 세부) ④ 그래프 sync·insight cycle 소요 미기록 ⑤ 산재한 기존
신호(pg_stat_statements·ask_jobs·duration_breakdown·pgbouncer)의 집계 수단 부재 — 를
additive·비파괴·fail-open 계측으로 메운다. **사용자 가시 동작 변경 0** — 측정만 추가한다
(정밀: 답변당 KV 1 write(`last_post_answer_ms`, fail-open)·로그 라인 추가 — §18.8 C-6 정정).

## 2. Goal
- REQ-20260727-perf-observability: 성능 병목을 정량 측정할 수 있는 계측·집계 수단을
  라이브 서비스 회귀 없이 추가한다 (사용자 요청 2026-07-27: "병목 측정을 위한 별도의
  추가 개발사항이 필요하다면 자율적으로 진행").
  - AC-20260727T090800-perf-observability-1: web 의 모든 HTTP 요청이 route 단위로
    count/p50/p95/max/error·요청당 MySQL/PG 커넥션 수와 함께 집계되고, admin 이
    `GET /api/admin/perf/http` (`console.aiops.read`) 로 조회할 수 있다.
  - AC-20260727T090800-perf-observability-2: 모든 LLM 호출 경로(워커 task 포함)가
    `agent_runtime.llm_usage.latency_ms` 를 기록한다 (기존 NULL → 측정값).
  - AC-20260727T090800-perf-observability-3: 답변 duration_breakdown 에 `redteam_ms` 와
    `init_detail`(grounding 단계별)이 추가되고, post-answer 부가 LLM 구간(`last_post_answer_ms`)
    이 KV 로 남는다 — (feature-0027 이후) 터미널 *후* 큐레이션 소요의 계측으로 의미 갱신.
  - AC-20260727T090800-perf-observability-4: `bin/perf-snapshot.sh` 1회 실행으로
    전 신호(HTTP/LLM/ask E2E/redteam/PG/pgbouncer/MySQL/graph-sync/컨테이너)가
    `artifacts/perf/<ts>/` 스냅샷으로 집계된다.
  - AC-20260727T090800-perf-observability-5: 그래프 sync 리포트에 `duration_ms`,
    insight cycle 로그에 node_analysis·관계 프로브 카운터가 포함된다.
  - AC-20260727T090800-perf-observability-6: Caddy edge access log 가 활성화되어
    엣지 관점 요청 지연·상태코드가 docker logs 로 남는다.

## 3. In Scope
- feature-0003 web: 순수 ASGI 타이밍 미들웨어(`perf_metrics.py`) + `routers/admin_perf.py`
  (읽기 전용, 기존 `console.aiops.read` 재사용 — 신규 권한 0) + 주기적 로그 flush.
- shared: `perf_counters.py` 요청-스코프 커넥션 카운터 (비활성 시 no-op).
- feature-0002: llm.py 13개 `_record_llm_usage` 호출부 latency 전달, agent_core 단계
  타이머(redteam/post-answer/grounding), insight cycle payload·metadata_graph rep 확장.
- repo-level: `bin/perf-snapshot.sh`, Caddyfile `log` 지시어.

## 4. Out of Scope
- 병목 **개선** 자체 (버퍼풀 상향, 커넥션 풀링, gzip, 폴링→SSE 등) — 측정 결과 기반 후속 cycle.
- 관리 콘솔 UI 표면 (JSON API 만 — HTML/JS 무변경, PB-0008 비대상).
- DB 스키마 변경 (alembic 0건 — 기존 컬럼·JSON meta 만 사용).
- Prometheus/Grafana 등 외부 스택 도입.

## 5. Inputs
- HTTP 요청 (미들웨어 관통), LLM 호출 완료 이벤트, agent run 단계 경계, sync/cycle 실행.
- `bin/perf-snapshot.sh`: PG/MySQL/pgbouncer/docker 라이브 상태 (read-only 쿼리).

## 6. Outputs
- in-process 집계 (web 프로세스 메모리) + `GET /api/admin/perf/http` JSON.
- stdout `[perf-http]` 주기 로그 라인 (기본 300s, `WEB_PERF_LOG_INTERVAL_SEC`, 0=off).
- `agent_runtime.llm_usage.latency_ms` (전 task), `messages.meta_json.duration_breakdown.redteam_ms/init_detail`,
  KV `last_post_answer_ms`, insight `[insight_worker]` payload 확장 키, graph sync rep `duration_ms`.
- `artifacts/perf/<UTC-ts>/snapshot.md` + `raw/*.txt`.

## 7. Main Flow
1. 요청 진입 → 미들웨어가 perf_counters 컨텍스트 활성화 + 타이머 시작 → 응답 후
   route template 단위로 집계 (lock 1회, 실패 시 무시 — fail-open).
2. LLM 호출 → perf_counter_ns 왕복 측정 → `_record_llm_usage(latency_ms=...)`.
3. agent run → grounding 단계별 타이머(ContextVar) → breakdown merge → 저장.
4. 운영자/AI → `bin/perf-snapshot.sh` → 전 신호 일괄 수집 → artifacts.

## 7.1 알려진 한계 (§18.8 패널 spec challenge 수용)
- `/api/admin/perf/http` 는 **이 replica 프로세스만** 집계한다(sticky LB 아래 web-b 조회 제한).
  전-replica 정본 뷰는 `bin/perf-snapshot.sh` §10([perf-http] 양 replica 로그 수집)이다 —
  이를 위해 인증 우회 경로(포트 직노출·무인증 내부 조회)를 파지 않는다(§18.8 sec 도전 ① 결정).
- in-process 집계는 재기동 시 리셋 — before/after 비교는 **개선 배포 직전 perf-snapshot 1회
  실행**을 절차로 한다(ANCHOR §3 시나리오 보강). 오버플로 포화 route 의 p95 는 "≥600s" 로만
  보이며 정밀값은 slow ring·duration_breakdown 집계로 본다.

## 8. Edge Cases
- 미들웨어/카운터 예외는 요청 처리에 전파되지 않는다 (전 구간 try/except, fail-open).
- 집계 메모리는 route 카디널리티로 유계 (미매칭 경로는 `(unmatched)` 로 묶음, slow ring 50개 고정).
- 워커 프로세스에서 perf_counters 는 컨텍스트 미활성 → no-op (오버헤드: dict get 1회).
- llm_usage INSERT 실패는 종전과 동일하게 silent (기존 fail-open 계약 유지).

## 9. Non-functional
- 미들웨어 오버헤드 목표 < 0.1ms/req (lock 짧게, 히스토그램 fixed bucket).
- 스냅샷 스크립트는 read-only — 어떤 상태도 변경하지 않는다.

## 10. Dependencies
- 기존: `agent_runtime.llm_usage`(0030/0032/0033), `console.aiops.read` 권한, pgbouncer ADMIN_USERS,
  primary pg_stat_statements. 신규 외부 의존 0.
- replica pg_stat_statements 적재는 운영 env(`KB_PG_REPLICA_PRELOAD`) 변경 + replica 재기동 (배포 단계 수행).

## Pre-approved Changes
- deploy_scope: included (전역 FIRST_REQUEST.md 선언 승계 — cycle 시작 시점 기존 선언)
