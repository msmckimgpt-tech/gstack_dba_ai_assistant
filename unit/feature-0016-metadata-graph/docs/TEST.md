---
doc_type: TEST
feature_id: feature-0016-metadata-graph
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 통합 테스트 (라이브 AGE 필요 — CI 에서 AGE 없으면 skip)

### docker/verify-age.sql — Phase 0 (AC-1)
격리 AGE 컨테이너에서 AGE create_graph + Cypher + pgvector(ivfflat/cosine) + pg_trgm(GIN/similarity)
공존 회귀. 실행:
```bash
docker build -f docker/Dockerfile.pg-age -t pg-age:0016-test docker/
docker run -d --name v -e POSTGRES_PASSWORD=v pg-age:0016-test
docker exec -i v psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f - < docker/verify-age.sql
```
2026-06-30 결과: `AGE+pgvector+pg_trgm coexist: PASS` (AGE 1.6.0 · pgvector 0.8.2 · pg_trgm 1.6).

### alembic 0025 — Phase 1a (AC-2 부분)
throwaway 에 마이그 적용 → 멱등 재적용 → 라벨 13개(v6/e7) 확인 → RBAC(rw쓰기/ro읽기/ro쓰기차단).
2026-06-30 결과: 적용+멱등 OK, RBAC 방어심층 PASS(`permission denied for table Product`).
전제: `shared_preload_libraries='age'` 로 기동(앱 role LOAD 불가).

### tests/test_metadata_graph_age.py — Phase 1b (AC-4 부분)
metadata_graph 모듈을 라이브 AGE 에 대해 행위 검증(모듈은 conn 주입 시 shared.db 미import → 단독 가능).
검증: sync 노드/엣지 MERGE · 멱등(노드 중복 0) · 한국어 · Cypher injection 방어 · 검색 · k-hop 이웃.
실행:
```bash
docker run -d --name pgage-t -e POSTGRES_PASSWORD=v -e POSTGRES_DB=agent_kb \
  pg-age:0016-test -c shared_preload_libraries=age
docker exec -i pgage-t psql -U postgres -d agent_kb -f - < <UPGRADE_SQL of 0025>
docker run --rm --network container:pgage-t \
  -v .../metadata_graph.py:/app/metadata_graph.py:ro \
  -v .../test_metadata_graph_age.py:/app/test_metadata_graph_age.py:ro \
  -e PYTHONPATH=/app -e DSN="host=localhost port=5432 dbname=agent_kb user=postgres password=v" \
  python:3.11-slim bash -c "pip install -q 'psycopg[binary]' && python /app/test_metadata_graph_age.py"
```
2026-06-30 결과: `ALL ASSERTS PASS {search_orders:3, search_주문:1, nb_nodes:7, nb_edges:9, orders_node_count:1}`.

## 단위 테스트 (AGE 불요 — 순수 함수)
- (예정) `_cq()` 이스케이프 · `_props_set()` 화이트리스트 · `_vkey()` — pytest, AGE 미필요.

## 후속 (Phase 2~5)
- 투영 API 계약 테스트(cap·scope 격리·빈 그래프 graceful).
- KB 회귀 스위트(`make test`) — AI 정합(Phase 4) 후.
- PB-0008 라이브 브라우저 검증(그래프 UI) — cutover 후.
