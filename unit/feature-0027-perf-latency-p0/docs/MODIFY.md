---
doc_type: MODIFY
feature_id: feature-0027-perf-latency-p0
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260728T010500-ai-root-perf-latency-p0 P0 성능 개선 1차 (A/D/C/E)
- 일시: 2026-07-28 / 작업자: AI (claude, branch ai/root/perf-latency-p0)
- 근거: feature-0026 전수 조사·계측 (답변 141s 중 post-answer ~34s 미기록 대기·RO 핸드셰이크
  다발·MySQL 버퍼풀 128MB/48GB·정적 1.1MB 비압축).
- **A**: `agent_core.py` — post-answer 큐레이션(topic/용어/ENUM) 실행을 패키지화해 KV
  terminal(done) **이후**로 이동. `run_post_answer_curation()` 신설(datasource ContextVar
  명시 캡처/재설정/해제·fail-open). in-process=done 직후, worker=`ask.py`
  `_finalize_deferred_terminal` 직후 호출. 실행 내용·게이트(answer+_writes_allowed)·scope 귀속 불변.
- **D**: `_build_knowledge_context` — 용어/ENUM·테이블/컬럼 설명·관계 3개 로더에 단일 공유
  RO 연결 주입(conn= 기설계 재사용, owned=False 계약 — replica 핸드셰이크 3→1).
- **C**: `unit/feature-0001-platform-runtime/src/mysql/conf.d/99-mysql-ai-server.cnf` —
  `innodb_buffer_pool_size = 1G` 영속화 (라이브는 배포 단계에서 SET GLOBAL 무중단 적용).
- **E**: `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — `encode zstd gzip` +
  `/static/*` `Cache-Control: public, max-age=31536000, immutable` (adapt PASS).
- 계측 동기화: `bin/perf-snapshot.sh` §3c 캡션(터미널 후 실행 의미로). 테스트:
  `test_post_answer_curation.py` 신규 3 (컨텍스트 캡처/해제·no-op·fail-open 계약).
