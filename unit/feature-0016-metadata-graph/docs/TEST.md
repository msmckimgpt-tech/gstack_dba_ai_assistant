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
- `tests/test_metadata_graph_units.py` — `_props_set`(ordinal 정수 리터럴·None 생략·비정수 주입차단) ·
  `_as_int` · `_node_dict`/`_node_from_props`(ordinal 반환). AGE·DB 불요.
  실행: `PYTHONPATH=unit/feature-0002-agent-core/src/modules python3 unit/feature-0016-metadata-graph/tests/test_metadata_graph_units.py`
  **2026-07-01 결과: PASS (8 tests)** — graphux5 ordinal 직렬화·주입방어 검증.
- (예정) `_cq()` 이스케이프 · `_vkey()` 추가 커버.

### graphux5 — 컬럼 세로정렬 + ordinal + 부드러운 엣지 (2026-07-01)
- **순수 함수(위 test_metadata_graph_units.py)**: PASS (8). ordinal 정수 리터럴 SET·주입안전·노드 직렬화.
- **AGE 통합(test_metadata_graph_age.py 검증 4d 추가)**: sync_column(ordinal=1/2) → neighborhood 노드가
  ordinal 보유. **컨테이너 재실행 필요**(AGE) — 배포 시 metadata-graph-sync 후 확인.
- **admin.js 구문**: `node --check` OK.
- **py_compile**: kb_metadata·metadata_graph·app.py·alembic 0027 OK.
- **API e2e (배포 후, 인증 브라우저)**: `GET /api/admin/metadata/columns?scope_key=mssql-06656002eda6` → HTTP 200,
  1030 컬럼 전건 `ordinal` 반환(예: Item 75컬럼 1:TemplateID·2:SortNum·3:Name…, DDL 순). ordinal 파이프라인
  (migration 0027 → column_descriptions → sync → API) 정합 확인.

#### PB-0008 실 Windows 브라우저 시각검증 (Environment: Windows-browser) — 2026-07-01 PASS
- 절차: `bin/win-browser.py launch` (Chrome 149, relay mode) → 관리콘솔 `메타데이터 > 🕸 그래프 뷰` →
  데이터소스 `mssql-qa-idc` 선택 → 검색/확장(`_metaGraphExpand`).
- **케이스1 `dk_data_release.Achievement`(4컬럼)**: Table 노드 하단으로 컬럼이 **실제 순서대로 세로 배치** —
  UniqueID(ord1,y65)→Type(ord2,y95)→Title(ord3,y125)→DLC(ord4,y155), x=172(테이블 x=118 +54 들여쓰기).
  Table→Column 연결선이 **직선이 아닌 부드럽게 꺾이는 선(round-taxi)** 으로 아래→오른쪽 트리 라우팅.
  스크린샷: `scratchpad/pb0008-03-columns-below-table.png`(세션 아티팩트).
- **케이스2 `dk_data_release.Item`(75컬럼) 스케일**: 75 HAS_COLUMN 엣지, ordinal top→bottom **단조 정렬**
  (1,2,3…73,74,75) — 대량 컬럼도 순서 정확. (긴 세로 스택은 줌으로 탐색, N1 판독성 MINOR 는 허용범위.)
- **결과: PASS** — 두 사용자 요구(①컬럼 테이블 하단 실제순서 세로배치 ②부드럽게 꺾이는 연결선) 모두 라이브 충족.
  배포 커밋 `git_commit=47d0f1a`, 자산 `admin.js?v=20260701-graphux10`, edge /healthz 200 안정.

## 후속 (Phase 2~5)
- 투영 API 계약 테스트(cap·scope 격리·빈 그래프 graceful).
- KB 회귀 스위트(`make test`) — AI 정합(Phase 4) 후.
- PB-0008 라이브 브라우저 검증(그래프 UI) — cutover 후.
