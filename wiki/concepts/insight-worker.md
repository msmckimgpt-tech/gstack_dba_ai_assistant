---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, insight, worker, rag]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [insight worker, insight-worker, schema 통찰 워커, 분석 완료율]
tags: [insight, worker, rag, coverage, postgres]
last_updated: 2026-06-23
---

# Insight Worker (schema 통찰 + 분석 완료율)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 | `unit/feature-0002-agent-core/docs/INSIGHTS.md` · `FUNCTION.md` |
| 관련 TASK | TASK-0223 (완료율 UI) · TASK-0242 (DB별 파악내용 표면화, main 4afa120) |
| 최종 갱신 | 2026-06-12 |

## 1. 개요

백그라운드에서 데이터소스의 schema/table 을 스캔해 **역할·도메인·조인 힌트 통찰**을 `rag_objects` + `texts` 에 캐시하는 워커. assistant 의 grounding 품질을 높이고, 관리 콘솔이 제품별 **분석 완료율**과 DB별 파악 내용을 표면화한다.

## 2. 데이터 모델 + 런타임 정합

- 통찰 저장: `public.rag_objects` (객체 메타) ⋈ `texts` (`text_content` = 역할/도메인/key columns 서술).
- **conversation_id sentinel**: insight 행은 `rag_objects.conversation_id = __global__` (`GLOBAL_CONVERSATION_ID`). 워커 런타임 대화는 `__insight_worker__` — **둘은 다름** (혼동 시 분자 0 hotfix 발생, TASK-0242).
- **liveness**: heartbeat KV 로 '분석중' 판정 (`_insight_worker_liveness`). heartbeat stale 시 `_should_run_inline_insight_scan()` 가 인라인 scan 트리거.
- datasource 격리는 [[datasource-aware-rag]] (endpoint-hash scope).

## 3. 분석 완료율 (coverage, TASK-0223)

- 관리 콘솔 > 제품 각 항목에 분석완료율% 배지 + per-DB breakdown.
- **모수** = 접근가능 DB (`WebProductDatabases`), **분자** = PG `rag_objects` 통찰.
- 매칭 = 라이브 카탈로그 `(schema, table)` ∩ rag set 교집합 (MSSQL `dbo` 차원 · NULL/hash 이중기록 해소).
- scope = `_dsr.scope_key` (엔드포인트 해시, `.env` 라벨 폴백) + 기본 엔드포인트 NULL 폴백. 분모 = resolve 된 datasource RO 좌표 직결.

## 4. DB별 파악내용 표면화 (TASK-0242)

- 각 DB 행에 insight worker 가 파악한 역할/도메인을 **한 줄 인라인** (펼침 X) + 추가 picker 도메인 힌트 · 3-state (미분석/분석중/분석됨).
- 신규 read `GET /api/admin/products/{id}/db-insights?datasource=<key>` (`console.access`, 바인딩 datasource 검증 400/404).
- coverage 와 동일 `_resolve_product_insight_scope` scope 로 `rag_objects ⋈ texts` DB별 묶음 (`_compute_product_db_insights` / `_clean_insight_segment` / `_compose_db_insight_text`).

## 5. 함정 (운영)

- **livelock**: cutover 가 read-back 2경로(artifact verify + fingerprint KV)를 DROP 된 MySQL 에 남겨 무한 재생성 → ollama 코어 연속 점유 (TASK-0145/0146 수정).
- `app.py _log` 는 일부 함수 로컬 import → 신규 함수는 `logging.getLogger` 선언 (F821 hotfix).
- **"DB 파악 진전 없음" = 2축 (TASK-0305)**: ① **커버리지** — `insight_worker.log` cycle summary 의 `db_failed`(/`db_targets`)가 크면 등록 catalog DB 다수가 스캔 실패. 대개 RO 로그인이 그 DB 에 per-DB `GRANT` 안 된 권한실패(MSSQL 18456/916). conn_health 서킷은 `engine:host:port` **엔드포인트 단위**라 host 가 살아있는 per-DB 권한실패를 격리 못 하고, 인증 에러는 서킷 피드백에서 제외돼 영구 재시도 → status=degraded 고정·완료율 정체. **조치는 운영 GRANT**(`bin/datasource-mssql-ro-bootstrap-multidb.sql` 을 실패 DB 마다) — 코드 아님. TASK-0305 RC5 가 `db_failed_{perm,circuit,other}` 를 cycle summary 에 노출하므로 perm(GRANT 대상) vs network(circuit/other) 를 로그로 구분. ② **fingerprint churn** — `insight_route.log` 에 같은 schema 가 `reason=fingerprint_changed` 로 반복 재생성되고 테이블명이 대/소문자로 진동(TF_ErrorLog↔tf_errorlog)하면, MSSQL information_schema 케이스 불안정. TASK-0305 RC2 가 fingerprint 해시 VALUE 에 `casefold` 적용해 안정화(저장 키 불변). ③ **force_scan spin** — `pending_table_repairs`>0 이 영구 유지되며 cycle 이 매 8s tick 마다 도는데 `tables_generated=0` 이면, 무경계 detector 가 budget(15s) 못 닿는 미완성 tail 로 force_scan 을 영구 latch 한 것. TASK-0305 RC3 진전기반 backoff 가 pending-only 무진전 스캔을 backoff(미완성 tail 의 spin 차단, 건강한 처리량은 보존).

## 6. 인용 source

- `unit/feature-0002-agent-core/docs/INSIGHTS.md` · `FUNCTION.md` (정본)
- `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` (coverage/db-insights 엔드포인트)

## 7. 관련 concept

- [[datasource-aware-rag]] · [[rag]] · [[kb-postgres-pgvector]] · [[multi-datasource]]

## 8. 관련 entity

- [[../entities/postgres]] · [[../entities/mysql]] · [[../entities/mssql]]

## 9. 외부 link

- [pgvector](https://github.com/pgvector/pgvector)

## 분류

`#wiki/concept` · `#concept_category/pattern` · `#domain/insight` · `#confidence/high`
