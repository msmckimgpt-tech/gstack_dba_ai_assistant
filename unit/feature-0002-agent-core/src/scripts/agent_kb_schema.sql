-- ============================================================================
-- TASK-0015 §2.1.3 M1 (TASK-0018 cycle): KB Postgres pgvector schema 정본.
--
-- 본 DDL 은 MySQL 의 5 KB 정본 (AgentMemoryFactEntries + AgentMemoryTexts +
-- AgentMemoryRagDocuments + AgentMemoryRagObjects + AgentMemoryFacts VIEW) 을
-- Postgres pgvector 의 등가 schema 로 옮기는 baseline. M2 dual-write phase 부터
-- 본 schema 의 테이블이 fact write 의 mirror target. M4 cutover 시점에 read path
-- 도 본 schema 의 테이블 사용.
--
-- Dialect 변환 매핑 (MySQL → Postgres):
--   bigint AUTO_INCREMENT         → bigint GENERATED ALWAYS AS IDENTITY
--   varchar(N) COLLATE utf8mb4_*  → varchar(N) (Postgres default UTF-8)
--   char(N)                       → char(N)
--   decimal(P,S)                  → numeric(P,S)
--   longtext                      → text
--   timestamp(3) ON UPDATE CURR.. → timestamptz + BEFORE UPDATE trigger
--   FULLTEXT KEY                  → tsvector + GIN index (또는 pgvector ANN)
--   ENGINE=InnoDB                 → (생략)
--
-- 명명 규칙 변환 (PascalCase → snake_case, Postgres convention):
--   AgentMemoryFactEntries  → fact_entries
--   AgentMemoryTexts        → texts
--   AgentMemoryRagDocuments → rag_documents
--   AgentMemoryRagObjects   → rag_objects
--   AgentMemoryFacts (VIEW) → agent_memory_facts (MATERIALIZED VIEW, T2-4)
--   ConversationId          → conversation_id
--   FactKey                 → fact_key
--   ... (전반적으로 snake_case 적용)
--
-- 사용법:
--   docker exec repo-postgres-1 psql -U postgres -d agent_kb -f /shared/agent_kb_schema.sql
--   또는 modules/memory.py 의 _ensure_pg_schema() 가 idempotent 적용
--
-- Embedding 컬럼 위치 결정 (Blocker B-4): texts.embedding 만. 동일 text_hash 의
-- fact_entries / rag_documents / rag_objects row 가 texts JOIN 시 자연 참조. M3
-- backfill 비용 최소화 (TextHash 별 1회 embed).
--
-- ANN index 선택 (Open Q #6): ivfflat (lists=100, partial WHERE embedding IS NOT NULL).
-- KB row ~800 (M-1 baseline) 에서 충분. 100K+ scale-up 시점에 hnsw 로 ALTER
-- (M5 후 ADR-0024 후보).
--
-- T2-4: agent_memory_facts → MATERIALIZED VIEW (CONCURRENTLY refresh 지원)
-- T2-6: category_join_hints_json TEXT → JSONB + GIN index
-- T3-10: pg_stat_statements + kb_slow_queries + autovacuum 조정
-- ============================================================================

-- 0. Extensions. CREATE 권한이 있는 superuser 가 1회 실행.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- FULLTEXT 대체 (LIKE %x% 최적화)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- T3-10: 슬로우 쿼리 추적

-- 1. UPDATE timestamp 자동 갱신 트리거 함수 (MySQL ON UPDATE 대체).
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. texts — TextHash 정규화 저장 + embedding 컬럼 (Blocker B-4 결정).
-- ============================================================================
CREATE TABLE IF NOT EXISTS texts (
    text_hash      char(64) PRIMARY KEY,
    text_content   text NOT NULL,
    embedding      vector(1536),                  -- text-embedding-3-small default dim
    embedding_model varchar(64),                  -- 어떤 모델로 embed 됐는지 추적
    embedded_at    timestamptz,                   -- embedding 생성 시각 (NULL = 미생성)
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- FULLTEXT 대체 — pg_trgm GIN index (LIKE %x% 빠름)
CREATE INDEX IF NOT EXISTS ix_texts_content_trgm
    ON texts USING gin (text_content gin_trgm_ops);

-- pgvector ANN index: NULL embedding 을 건너뛰는 partial index (T2 최적화).
-- NULL 행이 많을 때 ivfflat 은 무의미한 centroid 학습 → WHERE 절로 제거.
-- lists=32: sqrt(~1000 non-null rows). 100K+ 시 HNSW 로 전환 (ADR-0024 후보).
CREATE INDEX IF NOT EXISTS ix_texts_embedding_ivfflat
    ON texts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32)
    WHERE embedding IS NOT NULL;

-- ============================================================================
-- 3. fact_entries — fact 정본 (MySQL AgentMemoryFactEntries 등가).
-- ============================================================================
CREATE TABLE IF NOT EXISTS fact_entries (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id   varchar(128) NOT NULL,
    fact_key          varchar(128) NOT NULL,
    scope_key         varchar(96)  NOT NULL DEFAULT 'common',
    text_hash         char(64)     NOT NULL DEFAULT '',
    fact_fingerprint  char(40)     NOT NULL,
    weight            integer      NOT NULL DEFAULT 1,
    confidence        numeric(3,2),
    source_type       varchar(32),
    source_run_id     varchar(64),
    source_sql        text,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_fact_entries_conv_scope_key_fp
        UNIQUE (conversation_id, scope_key, fact_key, fact_fingerprint)
);

-- T3-10: autovacuum 조정 — ON CONFLICT DO UPDATE 워크로드는 dead tuple 축적이 빠름.
-- scale_factor=0 + threshold=500 → 500 행 dead tuple 마다 즉시 vacuum.
ALTER TABLE fact_entries SET (
    autovacuum_vacuum_scale_factor   = 0,
    autovacuum_vacuum_threshold      = 500,
    autovacuum_analyze_scale_factor  = 0,
    autovacuum_analyze_threshold     = 250
);

CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_key
    ON fact_entries (conversation_id, fact_key);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_weight
    ON fact_entries (conversation_id, weight, updated_at);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_run
    ON fact_entries (conversation_id, source_run_id);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_scope_weight
    ON fact_entries (conversation_id, scope_key, weight, updated_at);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_scope_run
    ON fact_entries (conversation_id, scope_key, source_run_id);
-- DISTINCT ON (_load_top_facts_pg) 에서 covering index 로 index-only scan 가능.
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_scope_key_rank
    ON fact_entries (conversation_id, scope_key, fact_key, weight, updated_at, id);

DROP TRIGGER IF EXISTS trg_fact_entries_updated_at ON fact_entries;
CREATE TRIGGER trg_fact_entries_updated_at
    BEFORE UPDATE ON fact_entries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 4. rag_documents — FactEntries 기반 backfill (MySQL AgentMemoryRagDocuments 등가).
-- ============================================================================
CREATE TABLE IF NOT EXISTS rag_documents (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id varchar(128) NOT NULL,
    scope_key       varchar(96)  NOT NULL DEFAULT 'common',
    doc_type        varchar(32)  NOT NULL DEFAULT 'fact',
    fact_key        varchar(128),
    text_hash       char(64)     NOT NULL DEFAULT '',
    content_hash    char(40)     NOT NULL,
    weight          integer      NOT NULL DEFAULT 1,
    source_type     varchar(32),
    source_run_id   varchar(64),
    source_sql      text,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    updated_at      timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_rag_docs_conv_scope_key_hash
        UNIQUE (conversation_id, scope_key, fact_key, content_hash)
);

CREATE INDEX IF NOT EXISTS ix_rag_docs_conv_scope_updated
    ON rag_documents (conversation_id, scope_key, updated_at);
CREATE INDEX IF NOT EXISTS ix_rag_docs_conv_scope_weight
    ON rag_documents (conversation_id, scope_key, weight, updated_at);
CREATE INDEX IF NOT EXISTS ix_rag_docs_conv_fact_key
    ON rag_documents (conversation_id, fact_key);

DROP TRIGGER IF EXISTS trg_rag_docs_updated_at ON rag_documents;
CREATE TRIGGER trg_rag_docs_updated_at
    BEFORE UPDATE ON rag_documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 5. rag_objects — FactEntries 기반 backfill + 카테고리 (D0~D3 라우팅 기초).
-- T2-6: category_join_hints_json TEXT → JSONB (GIN 인덱싱 + 타입 검증).
-- ============================================================================
CREATE TABLE IF NOT EXISTS rag_objects (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id          varchar(128) NOT NULL,
    scope_key                varchar(96)  NOT NULL DEFAULT 'common',
    object_type              varchar(32)  NOT NULL,
    object_key               varchar(255) NOT NULL,
    schema_name              varchar(128),
    table_name               varchar(128),
    column_name              varchar(128),
    text_hash                char(64),
    weight                   integer      NOT NULL DEFAULT 1,
    source_type              varchar(32),
    source_run_id            varchar(64),
    category_domain          varchar(128),
    category_entity_type     varchar(64),
    category_metric_family   varchar(128),
    category_event_type      varchar(128),
    category_time_grain      varchar(64),
    category_join_hints_json jsonb,            -- T2-6: TEXT → JSONB
    category_confidence      numeric(3,2),
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ux_rag_objects_conv_scope_type_key
        UNIQUE (conversation_id, scope_key, object_type, object_key)
);

CREATE INDEX IF NOT EXISTS ix_rag_objects_conv_scope
    ON rag_objects (conversation_id, scope_key, object_type, updated_at);
CREATE INDEX IF NOT EXISTS ix_rag_objects_schema_table
    ON rag_objects (schema_name, table_name, column_name);
CREATE INDEX IF NOT EXISTS ix_rag_objects_category
    ON rag_objects (conversation_id, scope_key, category_domain, category_event_type, updated_at);

DROP TRIGGER IF EXISTS trg_rag_objects_updated_at ON rag_objects;
CREATE TRIGGER trg_rag_objects_updated_at
    BEFORE UPDATE ON rag_objects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- T2-6: 기존 설치 마이그레이션 — TEXT 컬럼을 JSONB 로 변환 (idempotent).
-- GIN 인덱스는 JSONB 변환 완료 후 생성해야 하므로 DO 블록 이후에 위치.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rag_objects'
          AND column_name = 'category_join_hints_json'
          AND data_type = 'text'
    ) THEN
        ALTER TABLE rag_objects
            ALTER COLUMN category_join_hints_json
            TYPE jsonb USING category_join_hints_json::jsonb;
    END IF;
END
$$;

-- T2-6: JSONB GIN index — TEXT→JSONB 변환 DO 블록 이후에 생성 (순서 필수).
-- 기존 설치에서 TEXT 상태에서 생성 시 오류 방지 목적으로 여기로 이동.
CREATE INDEX IF NOT EXISTS ix_rag_objects_join_hints_gin
    ON rag_objects USING gin (category_join_hints_json);

-- ============================================================================
-- 6. agent_memory_facts MATERIALIZED VIEW (T2-4) — 주기적 CONCURRENTLY refresh.
--    MySQL AgentMemoryFacts (VIEW) 등가 → pre-computed 로 전환.
--    REFRESH MATERIALIZED VIEW CONCURRENTLY 는 고유 인덱스 필수.
-- ============================================================================

-- 기존 regular VIEW 가 남아있으면 제거 후 MATERIALIZED VIEW 생성 (idempotent).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_views WHERE viewname = 'agent_memory_facts'
    ) THEN
        DROP VIEW agent_memory_facts;
    END IF;
END
$$;

CREATE MATERIALIZED VIEW IF NOT EXISTS agent_memory_facts AS
SELECT DISTINCT ON (e.conversation_id, e.scope_key, e.fact_key)
    e.conversation_id  AS conversation_id,
    e.scope_key        AS scope_key,
    e.fact_key         AS fact_key,
    coalesce(t.text_content, '') AS fact_text,
    e.weight           AS weight,
    e.updated_at       AS updated_at
FROM fact_entries e
LEFT JOIN texts t ON t.text_hash = e.text_hash
ORDER BY e.conversation_id, e.scope_key, e.fact_key, e.weight DESC, e.updated_at DESC, e.id DESC
WITH DATA;

-- CONCURRENTLY refresh 를 위한 고유 인덱스 (필수).
CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_memory_facts_conv_scope_key
    ON agent_memory_facts (conversation_id, scope_key, fact_key);

-- 빠른 조회를 위한 보조 인덱스.
CREATE INDEX IF NOT EXISTS ix_agent_memory_facts_weight
    ON agent_memory_facts (conversation_id, weight DESC, updated_at DESC);

-- ============================================================================
-- 7. T4-12: kb_invalidations — 글로벌 KB 캐시 무효화 공유 시계.
--    _pg_mark_kb_invalidation() 이 fact write 완료 후 갱신.
--    _pg_check_kb_invalidation() 이 _is_refresh_due 에서 TTL 판단 보조.
--    NOTIFY 도 병행 발행 (persistent listener 미래 확장 groundwork).
-- ============================================================================
CREATE TABLE IF NOT EXISTS kb_invalidations (
    channel        varchar(64) PRIMARY KEY,
    invalidated_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================================
-- 9. T3-10: 슬로우 쿼리 모니터링 뷰 (pg_stat_statements 기반).
--    agent_kb_ro 와 agent_kb_rw 가 조회 가능하도록 권한 부여.
-- ============================================================================
CREATE OR REPLACE VIEW kb_slow_queries AS
SELECT
    left(query, 120)                                AS query_preview,
    round(mean_exec_time::numeric, 2)               AS avg_ms,
    round(max_exec_time::numeric, 2)                AS max_ms,
    calls,
    round((total_exec_time / nullif(calls, 0))::numeric, 2) AS total_per_call_ms,
    rows / nullif(calls, 0)                         AS avg_rows
FROM pg_stat_statements
WHERE query ~* 'fact_entries|rag_documents|rag_objects|texts'
  AND mean_exec_time > 10
ORDER BY mean_exec_time DESC
LIMIT 50;

-- ============================================================================
-- 10. Role 권한 grant (M1 의 bin/kb-pg-role-bootstrap.sh 가 role 생성, 본 grant 가
--    schema 권한 fix). agent_kb_rw / agent_kb_ro 가 role-bootstrap 스크립트로 미리
--    생성되어 있어야 함.
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        GRANT USAGE ON SCHEMA public TO agent_kb_rw;
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON TABLE fact_entries, texts, rag_documents, rag_objects,
                      kb_invalidations TO agent_kb_rw;
        GRANT SELECT ON TABLE agent_memory_facts TO agent_kb_rw;
        GRANT SELECT ON TABLE kb_slow_queries TO agent_kb_rw;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agent_kb_rw;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO agent_kb_rw;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        GRANT USAGE ON SCHEMA public TO agent_kb_ro;
        GRANT SELECT
            ON TABLE fact_entries, texts, rag_documents, rag_objects,
                      agent_memory_facts, kb_invalidations, kb_slow_queries TO agent_kb_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT ON TABLES TO agent_kb_ro;
    END IF;
END
$$;

-- ============================================================================
-- 9. Schema metadata — 정본 위치 추적 (M-1 baseline JSON 의 비교 대상).
-- ============================================================================
COMMENT ON TABLE fact_entries IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryFactEntries 의 Postgres 등가. M2 dual-write 부터 작성. T3-10 autovacuum 조정 적용.';
COMMENT ON TABLE texts IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryTexts 의 Postgres 등가. embedding 컬럼은 본 테이블에만 (Blocker B-4). T2: partial ivfflat index (WHERE embedding IS NOT NULL).';
COMMENT ON TABLE rag_documents IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryRagDocuments 의 Postgres 등가.';
COMMENT ON TABLE rag_objects IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryRagObjects 의 Postgres 등가. T2-6: category_join_hints_json JSONB + GIN index.';
COMMENT ON MATERIALIZED VIEW agent_memory_facts IS 'T2-4: regular VIEW → MATERIALIZED VIEW 전환. REFRESH MATERIALIZED VIEW CONCURRENTLY 로 쓰기 차단 없이 갱신 가능. ux_agent_memory_facts_conv_scope_key 고유 인덱스 필수.';
COMMENT ON VIEW kb_slow_queries IS 'T3-10: pg_stat_statements 기반 KB 테이블 슬로우 쿼리 모니터링. mean_exec_time > 10ms 필터.';
