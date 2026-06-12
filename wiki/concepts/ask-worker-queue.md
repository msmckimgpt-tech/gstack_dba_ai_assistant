---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, worker, queue, runtime]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [ask-worker, out-of-process ask, ask_jobs queue]
tags: [worker, queue, postgres, skip-locked, runtime]
last_updated: 2026-06-12
---

# Ask-worker 큐 (out-of-process 실행)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 설계 | [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-ask-worker\|DESIGN-ask-worker.md]] · ADR-WEB-0004 |
| 관련 TASK | TASK-0159/0160/0164 (설계·finalizer) → **TASK-0169 구현·cutover (main 584b8dd)** |
| 최종 갱신 | 2026-06-12 |

## 1. 개요

agent 실행을 web 프로세스 lifecycle 에서 분리해, web 재배포가 진행 중 run 을 죽이는 **orphan-on-redeploy** 를 제거한 패턴. PG job 큐 `ask_jobs` + 별도 `ask-worker` 서비스가 실행을 담당한다.

> **구현 현황**: DESIGN-ask-worker / ADR-WEB-0004 는 B(ask-worker)를 "설계만, 이월" 로 표기했으나, 이후 **TASK-0169 에서 구현 + cutover 완료** (flag=worker 라이브, web 재배포 중 run 생존 실측). A(SIGTERM graceful finalizer, TASK-0164)는 부팅 reconciliation 의 대칭 역으로 먼저 라이브.

## 2. 핵심 메커니즘 (설계)

- **job 큐** `agent_runtime.ask_jobs` (PG): status `pending|claimed|running|done|error|canceled`. payload = `_run_agent_core` kwargs mirror (user_message, model, temperature, product_id, role_id, allowed_schemas, attachment_ids).
- **claim**: `SELECT … FOR UPDATE SKIP LOCKED` + `UPDATE status='running'` → 워커당 exactly-once.
- **heartbeat + stale sweeper**: `heartbeat_at` + TTL 기반 requeue (워커 crash), attempts cap, fail-closed. stale threshold = `max(run_timeout_sec, ~900s)`.
- **slot/concurrency**: DB per-account running-job count 가 in-memory `_ACTIVE_REQUESTS` 대체 (multi-replica 정합).
- **첨부 temp**: 공유 볼륨 `/shared`, 워커 `finally` cleanup.
- **flag** `AGENT_ASK_EXECUTION_MODE` (`inprocess|worker`, default inprocess 롤백용 → 운영 worker 라이브).

## 3. 불변식

- web 재배포가 in-flight run 을 죽이지 않음 (프로세스 분리).
- `SKIP LOCKED` + heartbeat requeue 로 exactly-once.
- worker per-attempt `run_id` = fencing (재사용 금지). → 취소/재요청 정합 ([[../Features/feature-0003-agent-web-ui]] TASK-0241).

## 4. 관련 run-status 정합 (TASK-0241)

sentinel run_id (enqueue 선기록) + `set_run_status` (only_if_current_run) terminal 가드 + 무조건 takeover(claim) — cancel/즉시-재요청 clobber 차단의 3중 정합 trap.

## 5. 인용 source

- [[../../unit/feature-0003-agent-web-ui/docs/DESIGN-ask-worker|DESIGN-ask-worker.md]] (정본 설계)
- `unit/feature-0003-agent-web-ui/docs/DECISIONS.md` ADR-WEB-0004

## 6. 관련 concept

- [[insight-worker]] — ask-worker 가 mirror 한 워커 패턴
- [[kb-postgres-pgvector]] — `agent_runtime` schema 공유

## 7. 관련 entity

- [[../entities/postgres]]

## 8. 관련 ADR

- [[../Decisions/ADR-0027-agent-runtime-pg-schema]] — `agent_runtime` schema 정본

## 9. 외부 link

- [PostgreSQL — SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)

## 분류

`#wiki/concept` · `#concept_category/pattern` · `#domain/worker` · `#domain/queue` · `#confidence/high`
