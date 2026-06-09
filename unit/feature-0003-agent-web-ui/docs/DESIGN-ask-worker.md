---
doc_type: DESIGN
feature_id: feature-0003-agent-web-ui
scope: feature
status: proposed
edit_policy: rewrite
source_of_truth: false
title: DESIGN — out-of-process ask 실행모델 (ask-worker)
---

# DESIGN — out-of-process ask 실행모델 (ask-worker)

> **상태: 설계만 (proposed). 구현 안 됨.** TASK-0164 에서 A(SIGTERM graceful finalizer)로
> orphan-on-redeploy 를 저위험 차단했고, 본 문서는 구조적 정답(B)을 미래 cycle 용으로 남긴다.
> 구현은 자체 cycle + outside-voice 리뷰 + 전체 테스트 계획 후 착수 (Critical §12.3 — agent
> 실행 경계·동시성·크래시 시맨틱 변경). 결정 근거는 DECISIONS.md ADR-WEB-0004.

## 1. 문제 / 목표

`/api/ask` 는 agent 를 web 프로세스 안에서 `asyncio.to_thread(_run_agent_core, …)`
([app.py](../src/app.py) ~7836)로 실행한다 → in-flight run 이 web 프로세스와 생사를 같이한다.
web 재배포/`docker stop` 이 run 을 죽이면 terminal status 미도달 → orphan. TASK-0159(부팅
reconciliation)·0160(히스토리 정합)·0163-A(종료 finalizer)는 모두 **증상 완화/backstop**일 뿐
근본은 "실행이 web 수명에 묶여 있음"이다.

**목표**: agent 실행을 web 프로세스 밖 전용 `ask-worker` 로 분리 → web 재배포가 run 을 절대
건드리지 않음. web 은 thin enqueue + long-poll attach 계층이 되고, 0163-A 의 finalizer/부팅
reconciliation 은 거의 발동 안 하는 backstop 으로 격하.

**유리한 전제(이미 충족)**: run 상태가 이미 DB(KV `last_status*`/steps/core_messages) 기반이고,
cancel/finalize 가 KV 플래그 폴링(프로세스 무관)이며, 응답이 streaming 아닌 단일 JSON 이고,
`insight-worker`([docker-compose.yml](../../../docker-compose.yml) ~299)라는 동형 worker 템플릿이 있다.

## 2. 컴포넌트

### 2.1 신규 `ask-worker` 서비스 (insight-worker 템플릿)
- `*agent-common` 앵커 재사용(동일 이미지), `entrypoint: ["python","/app/agent_core.py","--ask-worker"]`
  → 신규 `run_ask_worker_loop()` (insight.py 의 `run_insight_worker_loop` ~1681 답습).
- `restart: unless-stopped`, networks `[dbnet, llm-shared, replica-net]`.
- heartbeat KV `ask_worker_last_cycle_at` + `scripts/healthcheck_ask_worker.py`(insight 헬스체크 클론,
  임계 env `ASK_WORKER_HEARTBEAT_MAX_AGE_SEC`).
- 동시성 = worker pool 크기/`deploy.replicas` (여러 worker 컨테이너 가능).

### 2.2 Job 모델 — 신규 `agent_runtime.ask_jobs` 테이블
> kv/steps overload 금지(큐 시맨틱 부적합). run 진행상태는 기존 kv/steps/core_messages 재사용
> → `/api/progress`·`/api/ask_result`·`/api/cancel`·`/api/finalize` 무변경.

컬럼(PG agent_runtime):
- `id` PK, `conversation_id`, `run_id`, `account_id`,
- `status` (`pending|claimed|running|done|error|canceled`),
- `claimed_by`(worker id), `claimed_at`, `started_at`, `finished_at`, `attempts`, `heartbeat_at`, `created_at`,
- payload(= `_run_agent_core` kwargs 미러, app.py ~7836-7854): `user_message`, `model`, `temperature`,
  `product_id`, `role_id`, `product_mode`, `allowed_schemas`(json), `attachment_ids`(json),
  `new_attachment_ids`(json), `image_inline_path`, `text_inline_path`.
- 인덱스: `(status, created_at)`(claim), `(conversation_id, run_id)`, `(heartbeat_at)`(stale sweep).
- 마이그레이션: alembic + `_ensure_*` slow/fast-path 디시플린(app.py ~3733/3619) 답습.

### 2.3 Job 생명주기 + claim
`pending` → (worker claim) `claimed/running` → terminal `done|error|canceled`.
- claim: `SELECT … FROM ask_jobs WHERE status='pending' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1`
  → `UPDATE status='running', claimed_by, started_at`. (insight 의 advisory-lock 패밀리와 정합; 큐엔 SKIP LOCKED.)
- worker 가 매 step `heartbeat_at` 갱신(기존 step-mirror 에 piggyback, agent_core ~1584).
- worker 는 기존 `set_run_status` 를 그대로 호출 → KV `last_status` 가 프런트의 단일 진실. `ask_jobs.status` 는 큐/운영 뷰.

### 2.4 `/api/ask` 변경
- 검증·conversation/product/role 해석은 현행 유지(app.py ~7334-7531).
- `to_thread` 대신: `last_status='processing'` write(기존 race 가드 유지) + `ask_jobs` enqueue + slot 획득
  → 기존 `/api/ask_result` long-poll(app.py ~10326) 로 내부 attach 해 **동기 응답 계약 유지**(클라 무변경),
  플래그로 async(클라가 ask_result 폴링) 폴백.

### 2.5 slot/동시성
`WEB_PARALLEL_LIMIT`(인메모리 `_ACTIVE_REQUESTS`, app.py ~671/1604)를 **DB 기반 per-account
running-job count** 로 이전: enqueue 시 `COUNT(ask_jobs WHERE account_id=? AND status IN (pending,claimed,running)) >= limit` → 429.
부수효과: 멀티 web replica 에서도 정합(현재 인메모리는 프로세스별이라 부정확).

### 2.6 cancel / finalize — **무변경**
`/api/cancel`·`/api/finalize` 가 KV 플래그(`cancel_requested`/`finalize_requested`)를 write 하고
agent loop 가 `_cancel_requested_for_run`·`_finalize_requested` 로 폴링 → 프로세스 무관, worker 가 동일 폴링.

### 2.7 크래시 / orphan
- web 재배포 → run 무영향(in-process agent 없음). 0163-A finalizer·부팅 reconciliation 은 backstop 으로 격하.
- worker 크래시 → heartbeat 기반 stale running-job sweeper(`run_ask_worker_loop` tick 또는 별 reaper):
  `status='running' AND heartbeat_at < now-임계` → requeue(`pending`, attempts++ cap) 또는 error + `set_run_status('error')`.
- worker 부팅 reconciliation(자기 소유 job 정리) — web 의 부팅 hook 과 동형.

## 3. 롤아웃
플래그 `AGENT_ASK_EXECUTION_MODE=inprocess|worker` (기본 `inprocess`):
- `inprocess` → 현행 `to_thread`(0163-A 보호).
- `worker` → `ask_jobs` enqueue (ask-worker 서비스 필요).
shadow → 점진 cutover → env 한 번에 rollback. `worker` 가 프로덕션 검증될 때까지 `inprocess` 경로 보존.

## 4. 핵심 위험 (why 자체 cycle + outside-voice)
1. 첨부 temp 파일 프로세스 간 핸드오프 — `image_inline_path`/`text_inline_path`(app.py ~7702/7723)를
   shared 볼륨(`../artifacts/shared:/shared`, web·agent-common 공통 마운트)에 쓰고 cleanup 을 worker
   `finally` 로 이전. read-after-delete/leak 주의.
2. exactly-once / no-double-run — SKIP LOCKED claim 정확성, requeue vs 중복 실행, attempts cap.
3. 동기 응답 계약 — `/api/ask` 가 현재 답변을 반환. 내부 long-poll 로 보존 시 latency/timeout/에러 표면 변화.
4. slot 시맨틱 변경(인메모리 per-process → DB per-account) — 멀티 replica 429 패리티 검증.
5. stale 임계 vs 정상 장기 run(`run_timeout_sec`, agent_core ~1974) — 정상 run false-positive requeue 방지.
6. ask_jobs 스키마 마이그레이션 + 멱등 ensure.
7. 백프레셔/큐 starvation (worker < 수요).

## 5. 테스트 계획(미래 cycle)
- 단위: claim race(SKIP LOCKED), stale sweeper requeue/error, slot count 429, payload round-trip.
- 통합: enqueue→worker 실행→KV/steps→ask_result attach 정상; web 재배포 중 run 생존; worker 크래시→requeue; cancel/finalize 동작.
- 라이브: PB-0008 Windows-browser(ask 전체 흐름) + 부하(백프레셔).
