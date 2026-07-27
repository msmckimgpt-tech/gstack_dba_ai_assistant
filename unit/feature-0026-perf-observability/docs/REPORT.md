---
doc_type: REPORT
feature_id: feature-0026-perf-observability
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. Summary
2026-07-27 전수 성능 조사(4 병렬 코드 탐색 + 라이브 관측)로 병목 지도를 확정하고, 측정
사각을 메우는 관측 인프라(M1~M6)를 구현했다. 측정 전용 — **사용자 가시 동작 변경 0**
(정밀: 답변당 KV 1 write `last_post_answer_ms`(fail-open)·로그 라인 추가 — §18.8 C-6 정정).

## 2. 병목 지도 (라이브 실측, 2026-07-20~27)
- **답변 E2E**: 평균 141s (p50 90s / p95 350s, ask_jobs 103건). 분해: agent LLM 87.8s(62%,
  평균 3.7회 직렬 호출) + red-team 파이프라인 46.4s(33%, BLOCK 0건/89) + 잔여 ~7s.
  저장된 breakdown 평균 107.4s vs 실측 141s — 격차 ~34s = post-answer(topic/용어/ENUM
  3 LLM, terminal 전 실행) + 전달 폴링 (S9 정확도 결함, M3 로 정량화 개시).
- **PG**: AGE cypher 590만 호출/12.5d (전체 쿼리 시간 지배), WAL ~4GB/일, 30분 주기
  그래프 sync 가 관계 엣지 수백~수천 건/회 churn. RO 핫패스는 pgbouncer 우회 replica
  (1g/shared_buffers 128MB) 직결 + 커넥션 풀 0 (요청당 수십 회 connect — grounding 직렬 8단계).
- **web**: HTTP 계측 전무였음. /api/ask_result long-poll 이 이벤트 루프에서 초당 ~10 PG conn.
  uvicorn 워커 1/replica. 정적 자산 1.1MB 비압축·Cache-Control 없음. 인증 요청당 8왕복.
- **MySQL**: innodb_buffer_pool_size 128MB(기본값) vs 데이터 48GB. slow log OFF(ADR-0020 의도).
- **워커**: 병렬 knob 라이브 4 (ask/node/cluster). heartbeat 가 유휴 초당 ~2 신규 PG conn.
  insight tick 은 node_analysis 직렬 LLM 에 블로킹.

## 3. 산출물 (M1~M6)
FUNCTION.md AC-1~6 · MODIFY.md CHG-20260727T091500 참조. 핵심: `/api/admin/perf/http`,
llm_usage.latency_ms 전 task, duration_breakdown.redteam_ms/init_detail, KV last_post_answer_ms,
sync rep duration_ms, `bin/perf-snapshot.sh`, Caddy access log.

## 4. 검증
- 단위: test_perf_metrics.py(5) + test_llm_latency_backfill.py(4) — make test 전체 스위트로 회귀 확인.
- 라이브: 배포 후 `/api/admin/perf/http` 200 + [perf-http] 로그 + perf-snapshot 실측 (§16.3 deploy-backed).

## 5. Risks / 남은 것
- replica pg_stat_statements preload 는 운영 env(`KB_PG_REPLICA_PRELOAD`) + replica 재기동 필요
  (배포 단계에서 적용 — RO 경로 수 초 단절 fail-soft 전제).
- 계측 자체의 오버헤드는 마이크로초대 설계이나 라이브 확인 항목에 포함.

## 8. 개선 제안 (측정 기반 후속 cycle 후보 — §8.1 기록만, 실행은 사용자 지시)
1. **P0 답변 지연**: post-answer 3 LLM 을 terminal 이후/비동기로 이동(체감 -25~35s), red-team
   게이팅 튜닝(REDTEAM_MIN_LEVEL 상향 검토 — BLOCK 0/89 실측), agent 호출 thinking 예산 재검토.
2. **P0 DB**: MySQL buffer pool 128MB→1~2G(동적 변수), PG RO 경로 커넥션 풀/pgbouncer 경유,
   grounding 8단계 단일 conn 재사용(이미 conn= 파라미터 설계됨) 또는 병렬 fan-out.
3. **P1 web**: Caddy `encode zstd gzip` + /static immutable Cache-Control, /api/ask_result
   루프 to_thread + conn 재사용, 인증 권한 카탈로그 프로세스 캐시 + LastSeenAt throttle.
4. **P1 그래프**: sync churn 원인(관계 자기교정 flap) 감쇠, incremental 창 최적화.
5. **P2**: uvicorn --workers, 사이드바 배지 경량 엔드포인트, EXPLAIN 게이트 캐시.
