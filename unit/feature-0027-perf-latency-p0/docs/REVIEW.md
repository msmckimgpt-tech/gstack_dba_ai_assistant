---
doc_type: REVIEW
feature_id: feature-0027-perf-latency-p0
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260728T010500-ai-root-perf-latency-p0 설계 판단 근거
- Related TASK: feature-0027-perf-latency-p0 / Timestamp: 2026-07-28T01:05:00Z
- **왜 A 가 1순위인가**: 측정상 사용자 대기 중 유일하게 '품질 무관' 인 직렬 구간(제거해도
  결과물 동일 — 시점만 이동). red-team(46s)은 revised 21/89 로 품질 기여가 실측돼 자율 제거
  불가(사용자 결정 포인트).
- **ContextVar 명시 캡처가 핵심 위험 통제**: run_agent finally 가 활성 datasource 를 해제하므로
  단순 이동 시 deferred 실행에서 scope_key='common' 오염(용어/ENUM 오귀속·격리 위반) —
  패키지에 key/engine/default_db 를 실어 재설정하고 finally 해제(스레드 재사용 누출 방지).
  fire-and-forget 스레드 대안은 이 보장이 취약해 기각(ANCHOR §2).
- **worker 경로 배선 위치**: `_finalize_deferred_terminal` **직후** — 첨부 후처리·terminal
  기록이 끝난 뒤라 raw 블록 노출 게이트(§18.8 BLOCKER 이력)와 무간섭. `_slim_result`
  keep-allowlist + 양 경로 pop 으로 result_json 오염 0.
- **C 1G 보수값**: mem_limit 3g, 실사용 ~1.1G — +0.9G 후 ~2.0G. 동적 변수라 즉시 적용·즉시
  revert 가능. 히트율 실측 후 2차 상향 판단.
- **E immutable 안전성 (§18.8 qa B1 정정 반영)**: 최초안(`/static/*` 전체 immutable)은
  unstamped 참조(vendor marked/purify — 파일명 무버전, 로고 svg) 존재로 **반증**됨(DOMPurify
  보안 패치 1년 고착 벡터). 쿼리 매처(`query v=*`)로 stamp 실은 요청에만 immutable 을 좁혀
  "URL=내용 결합일 때만 영구 캐시" 를 문법으로 강제.
- 사전 승인: deploy_scope: included(전역). PB-0008 비대상(웹 자산 무변경 — 전송 계층만).

## REV-20260728T023000-ai-root-perf-latency-p0 [AGENT-TEAM: SHIP-WITH-FIXES]
- **Related Change:** feature-0027 P0 성능 개선 (CHG-20260728T010500).
- **Panel:** §18.8 2-렌즈 적대 리뷰 (fresh-context) — ①backend/concurrency ②qa/regression skeptic.
- **Trigger:** performance/latency/caching keyword matched.
- **Verdict:** backend BLOCK·qa CONCERN → **전 결함 in-cycle 수정 후 SHIP** (BLOCKING 잔여 0).
- **Timestamp:** 2026-07-28T02:30:00Z

### 수용·수정한 결함 (전건 테스트/검증 동반)
- **[backend B1]** worker 가 삭제(pending_delete)·취소·오류 종결에도 큐레이션을 실행해 삭제된
  대화에 topic/제안이 부활. **FIX:** 3중 방어 — in-core 비성공 종결 패키지 pop + worker 는
  not-raised & 패키지 존재 시만 + 함수 내부 `_writes_allowed` 재검증(단일 소유).
- **[backend B2]** in-process 경로에서 done→큐레이션(25~35s)→strip 순서가 raw 첨부 블록 노출
  창(기지 §18.8 BLOCKER 패턴)을 재개방. **FIX:** 경로 분기 — in-process 는 종전 순서(조립
  지점 인라인, 체감 이득 0 이므로), worker 만 이연. 소스 잠금 테스트로 고정.
- **[backend B3 / qa B1]** unstamped vendor(marked·purify=DOMPurify)·로고에 `/static/*` 전면
  immutable 1년 → 보안 패치 고착. **FIX:** 쿼리 매처(`query v=*`) — stamp 실은 요청만 immutable,
  unstamped 는 ETag/304 유지. (배포 게이트가 vendor 를 명시 제외함을 실측 확인 — 전제 반증 수용.)
- **[backend C1]** worker 이연 시 cfg 전역 리셋 후라 큐레이션 llm_usage run_id NULL/오귀속.
  **FIX:** 함수가 payload run/conv 로 전역 설정 + finally 이전 값 복원(테스트 잠금).
- **[backend C2 / qa C3]** 큐레이션이 heartbeat 사각(running 상태)에서 실행 — provider 열화 시
  stale-sweep 이 완료된 답변을 requeue(중복 답변) 위험. **FIX:** worker 호출을 finish_ask_job
  (job terminal) **후**로 이동 — sweep 불가 시점. 소스 순서 테스트 잠금.
- **[backend C3]** 큐레이션의 `_connect_memory()` 는 소비처 전부가 무시하는 무용 MySQL 연결 +
  실패 결합. **FIX:** conn=None 관통, 연결 제거.
- **[backend C4]** `encode zstd gzip` 기본 매칭이 SSE(text/event-stream) 포함 — 토큰 스트리밍
  실시간성 열화 위험. **FIX:** 압축 대상 명시 allowlist(SSE 제외), adapt PASS.
- **[backend C5 / qa C1]** 공유 RO conn close 가 예외 경로 미보장. **FIX:** try/finally.
- **[qa C2]** 삭제 재검증(위 B1 에 통합). **[qa C4]** fail-open 배선 소실 은폐. **FIX:** 소스
  잠금 + rename 가드 + 공유 conn 계약 테스트 (test_post_answer_curation 8건).
- **[qa 반증 수용]** ANCHOR/REVIEW 의 "모든 /static 참조 buster 결합·vendor pin" 주장은 사실이
  아니었음 — 문서 정정 완료. feature-0026 FUNCTION 의 last_post_answer_ms 의미도 갱신.

### 패널이 결함 없음으로 확증한 것
- datasource scope 캡처 정합(`set_active_database` 는 insight 전용 — 큐레이션 읽기 경로는
  ds_fact_like=key 만), cnf `1G` 문법·3g 산술, 공유 conn autocommit(트랜잭션 오염 없음)·로더
  owned=False 계약, 이중 실행 경로 없음, 첫 메시지 topic 도 종전부터 답변 후 설정(가시 회귀 아님),
  perf-snapshot 캡션 변경 무회귀, 위험 후보 스위트 92+36 전건 PASS.
- **Human Approval Needed:** no (Minor·가역·품질 영향 축 불변·deploy_scope: included).
