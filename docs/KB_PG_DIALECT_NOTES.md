---
doc_type: reference
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.9.0
domain: [database, migration, reference]
ai_read_priority: 7
---

# KB MySQL → Postgres Dialect Notes

본 문서는 TASK-0015 §2.1 의 KB Postgres pgvector 마이그레이션의 **dialect 변환 카탈로그** 정본. M2 ~ M4 phase 의 cycle 진입 시 application-측 query rewrite / schema 적용 / 운영 정책 결정의 reference. ADR-0021 (RBAC 재정의) + ADR-0024 (Sprint 4 namespace) + outside-voice review (`REV-20260520-0005`, M1 cycle Plan subagent) Blocker 1 / Nice-to-have 의 해소 산출.

## 1. dialect 매핑 카탈로그 (요약)

| MySQL 8.0 | Postgres 16 + pgvector | 변환 phase | 주의 |
|---|---|---|---|
| `bigint NOT NULL AUTO_INCREMENT` | `bigint GENERATED ALWAYS AS IDENTITY` | M1 (schema) | M3 backfill 에서 MySQL Id 보존 필요 시 `BY DEFAULT` 로 ALTER 검토 |
| `varchar(N) COLLATE utf8mb4_unicode_ci` | `varchar(N)` (default LC_COLLATE) | M1 (schema) | docker image `pgvector/pgvector:pg16` default `en_US.utf8` — 한글 정렬 byte order. ORDER BY 결과 정확도 차이 가능 |
| `char(N)` | `char(N)` | M1 | 정합 |
| `decimal(P,S)` | `numeric(P,S)` | M1 | 정합 |
| `longtext` | `text` | M1 | Postgres `text` 2GB 상한 (MySQL `longtext` 4GB) — KB 사용 패턴에서 무관 |
| `timestamp(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)` | `timestamptz NOT NULL DEFAULT now()` + `BEFORE UPDATE` trigger | M1 | Postgres `ON UPDATE` 부재 — `set_updated_at()` trigger 함수가 NEW.updated_at = now() |
| `ENGINE=InnoDB` | (자동, 생략) | M1 | 정합 |
| `FULLTEXT KEY ... ON (col)` | `pg_trgm GIN ... USING gin(col gin_trgm_ops)` | M1 | **의미 비등가** — §2 query rewrite 표 참조 |
| `MATCH(col) AGAINST(:q IN NATURAL LANGUAGE MODE)` | (자연어 토큰 / BM25-like) | M4 cutover | **의미 비등가** — pg_trgm `similarity()` 또는 tsvector match 로 query rewrite. §2 표 참조 |
| `INSERT ... ON DUPLICATE KEY UPDATE` | `INSERT ... ON CONFLICT (cols) DO UPDATE SET ...` | M2 dual-write | unique constraint 명시 필요 |
| `INSERT IGNORE` | `INSERT ... ON CONFLICT DO NOTHING` | M2 dual-write | 정합 |
| `cursor.execute(sql, multi=True)` | psycopg `cursor.execute(sql)` (multi-statement 자연) | M2 dual-write | psycopg3 는 multi-statement 받음 — multi=True 인자 제거 |
| `mysql.connector.errorcode.ER_*` | psycopg `errors.UniqueViolation` 등 typed exception | M2 dual-write | error handling 분기 코드 1:1 매핑 catalog 필요 |
| `SET @@session.foreign_key_checks=0` | `SET session_replication_role = 'replica'` | (사용 안 함) | KB 5종 사이 FK 없음 — 본 cycle 비관련 |

## 2. FULLTEXT 사용 위치 + Postgres rewrite 의도 (Blocker 1)

본 cycle 의 M-1 baseline (`bin/kb-measure-baseline.sh` joins audit) + grep 결과 MySQL FULLTEXT 사용은 **2 위치**:

### 2.1 `modules/memory.py:143` — schema 정의

```python
FULLTEXT INDEX FT_Texts_Content (TextContent)
```

- MySQL `AgentMemoryTexts` 테이블의 FULLTEXT index 정의 (CREATE TABLE 일부).
- Postgres 등가: `agent_kb_schema.sql:66` 의 `CREATE INDEX ix_texts_content_trgm ON texts USING gin (text_content gin_trgm_ops)` (pg_trgm GIN index).
- **의미 비등가**: pg_trgm 은 3-gram substring 검색 (LIKE %x% 최적화), MySQL FULLTEXT 는 자연어 토큰화 + BM25-like 가중치.

### 2.2 `modules/knowledge.py:1434` — query 사용 (1건)

```python
SELECT ...,
    MATCH(t.TextContent) AGAINST(%s IN NATURAL LANGUAGE MODE) AS FtScore
FROM AgentMemoryRagDocuments d
LEFT JOIN AgentMemoryTexts t ON t.TextHash = d.TextHash
WHERE d.ConversationId IN (...) ...
ORDER BY FtScore DESC, d.Weight DESC, d.UpdatedAt DESC, d.Id DESC
```

- 함수: `_load_rag_documents_for_request(conn, request, ...)`. 사용자 요청과 RagDocuments 의 TextContent 의 자연어 유사도를 `FtScore` 로 계산 + 가중치/시각/Id 와 결합한 ranking.
- **read path** — M2 dual-write phase 에서는 read 가 MySQL only 이므로 본 query 변경 안 함. **M4 cutover 시점에 rewrite 필요**.

**M4 cutover 시 Postgres rewrite 옵션**:

**(a) pg_trgm `similarity()`** — 권장 default (Blocker 1 해소):
```sql
SELECT ...,
    similarity(t.text_content, %s) AS ft_score
FROM rag_documents d
LEFT JOIN texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id IN (...) AND t.text_content %% %s
ORDER BY ft_score DESC, d.weight DESC, d.updated_at DESC, d.id DESC
```
- `%%` operator 가 trigram similarity threshold 통과 필터 (default 0.3).
- `similarity()` 가 0~1 의 normalized score.
- pg_trgm GIN index (ix_texts_content_trgm) 가 가속.
- **의미 차이**: 자연어 토큰화 안 함 (substring 만). 한글 / 영문 mixed query 에서는 substring 매칭이 자연어 token 보다 약함.

**(b) tsvector `to_tsvector + @@`** — 자연어 토큰화 권장 시:
```sql
SELECT ...,
    ts_rank(to_tsvector('english', t.text_content), plainto_tsquery('english', %s)) AS ft_score
FROM rag_documents d
LEFT JOIN texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id IN (...)
  AND to_tsvector('english', t.text_content) @@ plainto_tsquery('english', %s)
ORDER BY ft_score DESC, d.weight DESC, d.updated_at DESC, d.id DESC
```
- `to_tsvector('english', ...)` 가 자연어 token + stemming. **다국어 (한글) 토큰화 부적합** — `simple` config 또는 별도 dictionary 필요.
- index 보강 필요: `CREATE INDEX ON texts USING gin (to_tsvector('english', text_content))` (M4 cycle 책임).

**(c) pgvector embedding similarity** — KB Postgres 의 강점:
```sql
SELECT ...,
    (t.embedding <=> %s::vector) AS distance,
    1 - (t.embedding <=> %s::vector) AS ft_score
FROM rag_documents d
LEFT JOIN texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id IN (...)
ORDER BY t.embedding <=> %s::vector
LIMIT 50
```
- `<=>` 가 cosine distance. embedding 입력은 사용자 query 의 embedding (별도 OpenAI 호출 필요).
- ivfflat / hnsw index 가속.
- **runtime 비용**: query 마다 OpenAI embedding API 호출 1회 추가 — latency + cost trade-off.

**M4 cycle 의 결정 항목 (별 cycle 책임)**:
- 옵션 (a) (pg_trgm) 가 default 권장 — KB scale ~800 row 에서 substring 매칭 정확도 충분, runtime cost 0, schema 이미 ready.
- 옵션 (c) (pgvector embedding) 는 §15.6 D0~D3 라우팅의 핵심 — fact-우선 복구 후 RAG 보조 query 에서 활용. M4 cutover gate 의 "EXPLAIN ANALYZE 비교" 게이트 (Open Q #13) 의 baseline.
- 옵션 (b) (tsvector) 는 영문 자연어 비율이 높을 때 — 본 plan 의 KB 가 한/영 mixed 이라 우선순위 낮음.

**Application 측 query rewrite 책임자**: M4 cutover cycle (TASK 미할당, M3 backfill 완료 후). 본 cycle 안에서는 query rewrite 안 함 — read path 가 MySQL 유지.

## 3. 명명 규칙 매핑 (PascalCase → snake_case)

| MySQL | Postgres |
|---|---|
| `AgentMemoryFactEntries` | `fact_entries` |
| `AgentMemoryTexts` | `texts` |
| `AgentMemoryRagDocuments` | `rag_documents` |
| `AgentMemoryRagObjects` | `rag_objects` |
| `AgentMemoryFacts` (VIEW) | `agent_memory_facts` (VIEW) |
| `ConversationId` | `conversation_id` |
| `FactKey` | `fact_key` |
| `ScopeKey` | `scope_key` |
| `TextHash` | `text_hash` |
| `FactFingerprint` | `fact_fingerprint` |
| `Weight` | `weight` |
| `Confidence` | `confidence` |
| `SourceType` | `source_type` |
| `SourceRunId` | `source_run_id` |
| `SourceSql` | `source_sql` |
| `CreatedAt` | `created_at` |
| `UpdatedAt` | `updated_at` |
| `ContentHash` | `content_hash` |
| `DocType` | `doc_type` |
| `ObjectType` | `object_type` |
| `ObjectKey` | `object_key` |
| `SchemaName` | `schema_name` |
| `TableName` | `table_name` |
| `ColumnName` | `column_name` |
| `CategoryDomain` | `category_domain` |
| `CategoryEntityType` | `category_entity_type` |
| `CategoryMetricFamily` | `category_metric_family` |
| `CategoryEventType` | `category_event_type` |
| `CategoryTimeGrain` | `category_time_grain` |
| `CategoryJoinHintsJson` | `category_join_hints_json` |
| `CategoryConfidence` | `category_confidence` |
| (Postgres 신규) | `embedding` (vector(1536), Blocker B-4) |
| (Postgres 신규) | `embedding_model` (varchar(64)) |
| (Postgres 신규) | `embedded_at` (timestamptz, NULL = 미생성) |

## 4. LC_COLLATE 정책 (outside-voice REV-20260520-0005 Section A Nice-to-have)

- **현재 default**: pgvector/pgvector:pg16 image 의 `en_US.utf8` (Debian-based).
- **영향**: `varchar` / `text` 컬럼의 `ORDER BY` 결과가 MySQL `utf8mb4_unicode_ci` 와 다를 수 있음. 특히 한글 정렬은 byte order (`en_US.utf8`) — `초성 → 중성 → 종성` 의 자연어 정렬 부재.
- **영향 위치**:
  - `agent_kb.fact_entries` 의 `fact_key` / `scope_key` ORDER BY (대부분 ASCII / hash 라 영향 없음)
  - `agent_kb.rag_objects` 의 `schema_name` / `table_name` / `column_name` (영문 DDL 이름 — 영향 없음)
  - `agent_kb.texts` 의 `text_content` ORDER BY (있다면) — 본 plan 의 query 에 텍스트 ORDER BY 없음 — 영향 없음
- **결론**: 본 plan 의 query 패턴에서 LC_COLLATE 영향 0 추정. M4 cutover gate 의 EXPLAIN ANALYZE 결과 확인 필요. 영향 발견 시 ADR-0026 (별 ADR 후보) — `agent_kb` database 의 `LC_COLLATE='ko_KR.utf8'` 옵션 + initdb 재실행 또는 `COLLATE "ko_KR.utf8"` per-column.

## 5. IDENTITY 모드 (outside-voice REV-20260520-0005 Section A Nice-to-have)

- **현재 default (M1)**: `GENERATED ALWAYS AS IDENTITY`. application 이 명시적 `Id` value 를 INSERT 불가 — schema 자동.
- **M3 backfill 시점의 결정**: MySQL Id (AUTO_INCREMENT) 와 Postgres Id (IDENTITY) 의 매핑.
  - 옵션 A (권장): Postgres Id 를 새로 부여 (`OVERRIDING SYSTEM VALUE` 불요). 자연키 (Conv × Scope × FactKey × Fingerprint) 가 unique 보장 — Id 보존 불필요.
  - 옵션 B: MySQL Id 보존 위해 IDENTITY 를 `BY DEFAULT` 로 ALTER. 본 cycle 의 schema sql 변경 필요 (ALTER COLUMN id DROP IDENTITY + ADD IDENTITY BY DEFAULT).
- **결정**: 옵션 A. 자연키가 unique 보장 + Id 보존 의도 없음 (Id 는 internal). M3 backfill 의 `bin/kb-backfill.sh` 가 `ON CONFLICT (conversation_id, scope_key, fact_key, fact_fingerprint) DO NOTHING` 으로 idempotent.

## 6. multi-statement / cursor.execute 패턴 (outside-voice REV-20260520-0005 Section A D-3)

- **mysql.connector**: `cur.execute(sql, multi=True)` → iterator 반환. multi-statement 의 각 result 처리.
- **psycopg3**: `cur.execute(sql)` 가 multi-statement 자연 지원. iterator 패턴 부재 — 각 statement 의 result 는 마지막 statement 의 result 만 cursor 에 남음.
- **영향 위치**: `modules/db.py:execute_sql(conn, sql)` 의 multi-statement 패턴 (line ~103). MySQL 전용. Postgres 측은 별도 helper (M2 cycle 의 KbBackend 책임).
- **결정**: KB Postgres path 에서는 multi-statement 사용 안 함. 각 INSERT/UPDATE 을 별 cursor.execute() 호출로 분리. 이 패턴은 M2 dual-write 의 `_dual_write_kb()` 안에서 자연 구현.

## 7. 후속 cycle 의 책임 분배

| Phase | dialect 항목 | 책임 |
|---|---|---|
| M2 (TASK-0019) | `INSERT ... ON CONFLICT` / `cursor.execute()` 패턴 + KbBackend ABC | 본 cycle |
| M2~M4 사이 (TASK 미할당) | `mysql.connector.errorcode.ER_*` → psycopg `errors.UniqueViolation` 등 매핑 catalog | M2-b 의 별 cycle |
| M3 backfill | IDENTITY default 채택 (옵션 A) + `ON CONFLICT (자연키) DO NOTHING` | M3 cycle |
| M4 cutover | FULLTEXT → pg_trgm `similarity()` query rewrite (knowledge.py:1434) | M4 cycle |
| M4 cutover gate | EXPLAIN ANALYZE 비교 + LC_COLLATE 영향 검증 | M4 cycle |

## 8. 참조

- ADR-0021 (KB Postgres 분리 후 RBAC catalog 재정의) — Layer 1 / Layer 2
- ADR-0024 (Sprint 4 namespace 격리 — `agent_drag` vs `agent_kb`)
- TASK-0015 §2.1 PLAN-APPROVED multi-cycle plan
- outside-voice review `REV-20260520-0005` Section A (DDL dialect) + D-3 (dialect 변환 catalog)
- `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (M1 정본)
- `artifacts/shared/kb-baseline-2026-05-20.json` (M-1 baseline)
