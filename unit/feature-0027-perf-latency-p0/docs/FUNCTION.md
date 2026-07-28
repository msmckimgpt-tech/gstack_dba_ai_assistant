---
doc_type: FUNCTION
feature_id: feature-0027-perf-latency-p0
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
feature-0026 전수 성능 조사·계측이 확정한 병목 지도의 **P0 개선 1차분**. 답변 체감 지연의
최대 비-품질 항목(post-answer 큐레이션)과 자원 미스매치 2건(MySQL 버퍼풀·정적 자산 전송)을
공격적으로, 그러나 답변 품질에 손대지 않고 제거한다. red-team 게이팅·thinking 예산은 품질
트레이드오프라 본 cycle 범위 밖(사용자 결정 포인트로 표면화).

## 2. Goal
- REQ-20260728-perf-latency-p0: 측정 근거 기반 P0 병목 제거 (사용자 지시 2026-07-28:
  "자율적으로 우선순위를 판단하여 개선작업 착수").
  - AC-20260728T010000-perf-latency-p0-1 (**A**): **worker 경로**(라이브 현행)에서 topic/
    용어/ENUM 부가 LLM 3건이 job terminal 전이(finish_ask_job) **이후** 실행된다 — 사용자
    대기에서 제거 + stale-sweep 사각 없음. **in-process 경로는 종전 순서(터미널 전) 유지**
    (§18.8 backend B2 — done 후 실행은 첨부 strip 전 raw 블록 노출 창 재개방이고 체감 이득 0).
    큐레이션 결과물·datasource scope 귀속·usage 귀속(run_id)은 종전과 동일.
  - AC-20260728T010000-perf-latency-p0-2 (**D**): grounding 3개 로더(용어/ENUM·테이블/컬럼
    설명·관계)가 요청당 단일 공유 RO 연결을 사용한다 (replica 핸드셰이크 3→1).
  - AC-20260728T010000-perf-latency-p0-3 (**C**): MySQL `innodb_buffer_pool_size` 128MB→1G
    (cnf 영속 + 라이브 SET GLOBAL 무중단 적용, 버퍼풀 히트율 perf-snapshot §8 전/후 실측).
  - AC-20260728T010000-perf-latency-p0-4 (**E**): Caddy `encode zstd gzip` + `/static/*`
    immutable Cache-Control — 텍스트 자산 전송량 ~1/5, 재방문 304 왕복 제거.

## 3. In Scope
- feature-0002 agent_core: 큐레이션 **패키지화**(`result["_post_answer_curation"]`, 활성
  datasource ContextVar 명시 캡처) + `run_post_answer_curation()` (terminal 후 실행·컨텍스트
  재설정/해제·fail-open) + in-process done 직후 호출 + grounding 공유 RO conn.
- feature-0002 modules/ask.py: `_finalize_deferred_terminal` 직후 큐레이션 호출 (worker 경로).
- feature-0001 mysql cnf: buffer pool 1G 영속화. feature-0006 Caddyfile: encode+header.
- bin/perf-snapshot.sh §3c 캡션 의미 동기화 (터미널 후 실행으로 변경됨).

## 4. Out of Scope (후속 cycle)
- red-team 게이팅/예산 조정 (품질 트레이드오프 — 사용자 결정), agent thinking 예산.
- web get_conn 풀링·ask_result to_thread·권한 카탈로그 캐시 (web-perf 별도 slice).
- 그래프 sync churn 감쇠. uvicorn --workers.

## 7. Main Flow (A)
run 성공 → 답변 mirror 저장 → (redteam 포함) breakdown 기록 → 게이트(answer+_writes_allowed)
통과 시 **패키지 조립**(datasource key/engine/default_db 캡처) →
- worker: KV terminal(finalize) → job terminal(finish_ask_job) → `run_post_answer_curation`
- in-process: 조립 지점에서 즉시 `run_post_answer_curation` (종전 순서)
함수 내부(단일 소유): _writes_allowed 재검증 → ContextVar·cfg 전역(run/conv) 재설정 →
topic/용어/ENUM → KV last_post_answer_ms → **이전 값 복원**.

## 8. Edge Cases
- 패키지 None/비정상 → no-op. 큐레이션 실패 → 흡수(이미 전달된 답변 무영향, `_log` 1줄).
- 컨텍스트는 finally 해제 — worker executor 스레드 재사용 시 다음 job 누출 방지.
- `_slim_result` keep-allowlist 라 패키지가 result_json 에 잔류하지 않음 + 양 경로 pop.
- 공유 RO conn 미가용 → 로더 자체 폴백(fail-soft 계약 불변). 로더는 주입 conn 을 close 하지
  않음(owned=False 계약 — 각 모듈 `_ro_conn`).
- 사용자 가시 변화: topic 이 답변 도착 수 초 뒤 갱신될 수 있음(사이드바 7s 폴링 내 자연 반영).

## 10. Dependencies
- feature-0026 계측 (before/after 실측 근거·수단). deploy_scope: included (전역).
