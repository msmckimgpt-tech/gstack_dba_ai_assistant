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
--   AgentMemoryFacts (VIEW) → (TASK-0140 폐기 — fact_entries 가 정본, 중복 스냅샷 제거)
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
-- T2-4: agent_memory_facts MATERIALIZED VIEW → TASK-0140 (2026-06) 폐기. 자동
--       refresh 미연동으로 drift, 라이브 read 0. 정의 제거 (라이브 DROP 은 오케스트레이터).
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
    embedding      vector(1024),                  -- titan-embed v2 / 경로B local (1024-dim) — AGENT_KB_EMBEDDING_DIM 정합 (alembic 0001 baseline=1024). TASK-0306: stale 1536 정정(fresh-install 차원 불일치 해저드 제거)
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
-- 6. agent_memory_facts — TASK-0140 (2026-06)에서 폐기.
--    사유: fact_entries(정본, 780행)의 중복 스냅샷이며 자동 refresh hook 가
--    연동되지 않아 drift 위험만 남음. 라이브 코드 데이터 read 0 (진단 참조뿐).
--    matview / index / grant / comment 정의를 모두 제거. 라이브 객체 DROP 은
--    오케스트레이터가 별도 실행: DROP MATERIALIZED VIEW IF EXISTS public.agent_memory_facts;
-- ============================================================================

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
-- 8. ITEM-10 (ROADMAP dba-ai-nl2sql): 용어사전 + ENUM 코드사전 (semantic-lite).
--    도메인 용어 정의·컬럼 열거형 코드↔라벨 매핑을 ds-scoped(scope_key) 로 저장.
--    질문/스키마 매칭 시 _build_knowledge_context 가 프롬프트에 datamark 주입.
-- ============================================================================
CREATE TABLE IF NOT EXISTS kb_glossary (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',  -- datasource 격리(fact_entries 동일 컨벤션)
    term        varchar(128) NOT NULL,
    definition  text         NOT NULL,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_kb_glossary_scope_term UNIQUE (scope_key, term)
);
CREATE INDEX IF NOT EXISTS ix_kb_glossary_scope ON kb_glossary (scope_key);
CREATE INDEX IF NOT EXISTS ix_kb_glossary_term_trgm ON kb_glossary USING gin (term gin_trgm_ops);
DROP TRIGGER IF EXISTS trg_kb_glossary_updated_at ON kb_glossary;
CREATE TRIGGER trg_kb_glossary_updated_at
    BEFORE UPDATE ON kb_glossary
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
-- 0023 미러(용어사전 대화 자율등록): 역할 차원(role_key) + 출처(source). boot 정본이라 alembic 과 동형 미러
-- 필수 — 미러 누락 시 배포에서 role_key 컬럼/신 UNIQUE 부재 → record/upsert 의 ON CONFLICT (scope,role,term)
-- 매칭 실패 런타임 에러(0021 sample_feedback 부트스트랩 미러 트랩과 동형). ADD COLUMN/DROP·ADD CONSTRAINT 멱등.
ALTER TABLE kb_glossary ADD COLUMN IF NOT EXISTS role_key varchar(64) NOT NULL DEFAULT '*';
ALTER TABLE kb_glossary ADD COLUMN IF NOT EXISTS source   varchar(24) NOT NULL DEFAULT 'manual';
ALTER TABLE kb_glossary DROP CONSTRAINT IF EXISTS ux_kb_glossary_scope_term;
ALTER TABLE kb_glossary DROP CONSTRAINT IF EXISTS ux_kb_glossary_scope_role_term;
ALTER TABLE kb_glossary ADD  CONSTRAINT ux_kb_glossary_scope_role_term UNIQUE (scope_key, role_key, term);
CREATE INDEX IF NOT EXISTS ix_kb_glossary_scope_role ON kb_glossary (scope_key, role_key);

CREATE TABLE IF NOT EXISTS enum_dictionary (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',
    schema_name varchar(128) NOT NULL DEFAULT '',
    table_name  varchar(128) NOT NULL,
    column_name varchar(128) NOT NULL,
    code        varchar(128) NOT NULL,   -- 컬럼 raw 값(상태코드 등)
    label       text         NOT NULL,   -- 사람이 읽는 의미
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_enum_dictionary_scope_col_code
        UNIQUE (scope_key, schema_name, table_name, column_name, code)
);
CREATE INDEX IF NOT EXISTS ix_enum_dictionary_scope ON enum_dictionary (scope_key);
CREATE INDEX IF NOT EXISTS ix_enum_dictionary_col
    ON enum_dictionary (scope_key, table_name, column_name);
DROP TRIGGER IF EXISTS trg_enum_dictionary_updated_at ON enum_dictionary;
CREATE TRIGGER trg_enum_dictionary_updated_at
    BEFORE UPDATE ON enum_dictionary
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 0023 미러: 용어사전 대화 자율등록 검토 큐 + 유사어 참조 (boot 정본 미러 — GRANT 블록 §10 이 권한 부여).
CREATE TABLE IF NOT EXISTS glossary_feedback (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key            varchar(96)  NOT NULL DEFAULT 'common',
    role_key             varchar(64)  NOT NULL DEFAULT '*',
    term                 varchar(128) NOT NULL,
    suggested_definition text         NOT NULL,
    confidence           real         NOT NULL DEFAULT 0.5,
    status               varchar(16)  NOT NULL DEFAULT 'pending',  -- pending|auto_promoted|promoted|rejected
    source_run_id        varchar(64),
    conversation_id      varchar(128),
    promoted_glossary_id bigint,
    approved_by          varchar(64),
    created_at           timestamptz  NOT NULL DEFAULT now(),
    updated_at           timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_glossary_feedback_status
        CHECK (status IN ('pending', 'auto_promoted', 'promoted', 'rejected')),
    CONSTRAINT ux_glossary_feedback_scope_role_term UNIQUE (scope_key, role_key, term)
);
CREATE INDEX IF NOT EXISTS ix_glossary_feedback_status ON glossary_feedback (status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_glossary_feedback_scope  ON glossary_feedback (scope_key, role_key);
DROP TRIGGER IF EXISTS trg_glossary_feedback_updated_at ON glossary_feedback;
CREATE TRIGGER trg_glossary_feedback_updated_at
    BEFORE UPDATE ON glossary_feedback
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS glossary_relations (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    from_id       bigint      NOT NULL REFERENCES kb_glossary(id) ON DELETE CASCADE,
    to_id         bigint      NOT NULL REFERENCES kb_glossary(id) ON DELETE CASCADE,
    relation_type varchar(16) NOT NULL DEFAULT 'similar',  -- synonym|similar|see_also
    created_by    varchar(64),
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_glossary_relations_type
        CHECK (relation_type IN ('synonym', 'similar', 'see_also')),
    CONSTRAINT ck_glossary_relations_distinct CHECK (from_id <> to_id),
    CONSTRAINT ux_glossary_relations UNIQUE (from_id, to_id, relation_type)
);
CREATE INDEX IF NOT EXISTS ix_glossary_relations_from ON glossary_relations (from_id);
CREATE INDEX IF NOT EXISTS ix_glossary_relations_to   ON glossary_relations (to_id);

-- ----------------------------------------------------------------------------
-- 8a. ITEM-11 Phase 2 (ROADMAP dba-ai-nl2sql): 테이블/컬럼 설명 사전 (semantic-lite).
--     사람이 작성한 테이블·컬럼 의미 설명을 ds-scoped(scope_key) 로 저장한다. 두 경로로 주입:
--       (B) _build_knowledge_context 가 질문 매칭 행을 grounding 섹션에 datamark 주입.
--       (A) describe_table 가 native COLUMN_COMMENT 가 빈 컬럼을 KB 설명으로 오버레이
--           (MSSQL 빈 comment gap, dialects.py describe_columns row[6]='' 해소).
--     enum_dictionary 컨벤션(scope_key/schema_name 기본값·UNIQUE·트리거) 그대로 모사한다.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS table_descriptions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',  -- datasource 격리(enum_dictionary 동일 컨벤션)
    schema_name varchar(128) NOT NULL DEFAULT '',
    table_name  varchar(128) NOT NULL,
    description text         NOT NULL,
    source      varchar(24)  NOT NULL DEFAULT 'manual',  -- manual|bootstrap (provenance)
    created_by  varchar(64),
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_table_descriptions_scope_tbl
        UNIQUE (scope_key, schema_name, table_name)
);
CREATE INDEX IF NOT EXISTS ix_table_descriptions_scope ON table_descriptions (scope_key);
DROP TRIGGER IF EXISTS trg_table_descriptions_updated_at ON table_descriptions;
CREATE TRIGGER trg_table_descriptions_updated_at
    BEFORE UPDATE ON table_descriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS column_descriptions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',
    schema_name varchar(128) NOT NULL DEFAULT '',
    table_name  varchar(128) NOT NULL,
    column_name varchar(128) NOT NULL,
    description text         NOT NULL,
    source      varchar(24)  NOT NULL DEFAULT 'manual',
    ordinal     integer,     -- feature-0016 graphux5: 실제 스키마 컬럼 순서(DDL ORDINAL_POSITION). NULL=미상.
    created_by  varchar(64),
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_column_descriptions_scope_col
        UNIQUE (scope_key, schema_name, table_name, column_name)
);
-- feature-0016 graphux5: 기존 DB(alembic 0026 미적용 경로)에도 ordinal 을 보장(정본은 alembic 0026).
ALTER TABLE column_descriptions ADD COLUMN IF NOT EXISTS ordinal integer;
CREATE INDEX IF NOT EXISTS ix_column_descriptions_scope ON column_descriptions (scope_key);
CREATE INDEX IF NOT EXISTS ix_column_descriptions_col
    ON column_descriptions (scope_key, table_name, column_name);
DROP TRIGGER IF EXISTS trg_column_descriptions_updated_at ON column_descriptions;
CREATE TRIGGER trg_column_descriptions_updated_at
    BEFORE UPDATE ON column_descriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ----------------------------------------------------------------------------
-- feature-0013 relationship-diagrams: 테이블 관계(FK·join) edge 저장소.
-- introspection(fk_introspect) + 대화 JOIN 학습(conversation)의 단일 수렴점. mermaid 다이어그램 grounding.
-- 정본은 alembic/versions/20260629_0024_table_relationships.py — 본 DDL 은 문서적 정합용.
CREATE TABLE IF NOT EXISTS table_relationships (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key         varchar(96)  NOT NULL DEFAULT 'common',
    datasource_key    varchar(64)  NOT NULL DEFAULT '',
    source_schema     varchar(128) NOT NULL DEFAULT '',
    source_table      varchar(128) NOT NULL,
    source_column     varchar(128) NOT NULL,
    target_schema     varchar(128) NOT NULL DEFAULT '',
    target_table      varchar(128) NOT NULL,
    target_column     varchar(128) NOT NULL,
    source_table_fqn  varchar(257) NOT NULL,
    target_table_fqn  varchar(257) NOT NULL,
    constraint_name   varchar(128) NOT NULL DEFAULT '',
    cardinality       varchar(24)  NOT NULL DEFAULT '',
    source            varchar(24)  NOT NULL DEFAULT 'fk_introspect',
    confidence        real         NOT NULL DEFAULT 1.0,
    source_run_id     varchar(64),
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_table_relationships_source
        CHECK (source IN ('fk_introspect', 'conversation', 'llm_insight')),
    CONSTRAINT ux_table_relationships_edge
        UNIQUE (scope_key, source_table_fqn, source_column, target_table_fqn, target_column)
);
CREATE INDEX IF NOT EXISTS ix_table_relationships_src ON table_relationships (scope_key, source_table_fqn);
CREATE INDEX IF NOT EXISTS ix_table_relationships_tgt ON table_relationships (scope_key, target_table_fqn);
DROP TRIGGER IF EXISTS trg_table_relationships_updated_at ON table_relationships;
CREATE TRIGGER trg_table_relationships_updated_at
    BEFORE UPDATE ON table_relationships
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 8b. ITEM-02+03 (ROADMAP dba-ai-nl2sql): 샘플쿼리 few-shot 저장소 + 피드백 flywheel.
--    sample_queries  — NL↔SQL 샘플(ds-scoped, 임베딩). approved∧active 만 검색·주입 대상.
--                      flywheel-ready: source_type(provenance)·status(신선도)·weight(품질가중).
--    sample_feedback — 답변 👍/👎/"샘플 등록" 원천. 승인 큐 경유로 sample_queries 승급
--                      (자동학습 금지 — poisoning 방어). generated_sql 은 PII 마스킹 저장.
-- ============================================================================
CREATE TABLE IF NOT EXISTS sample_queries (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key     varchar(96)  NOT NULL DEFAULT 'common',   -- datasource 격리(fact_entries 컨벤션)
    nl_question   text         NOT NULL,
    sql           text         NOT NULL,                    -- 프롬프트 예시 전용(직접 실행 금지)
    domain        varchar(64)  NOT NULL DEFAULT '',
    weight        integer      NOT NULL DEFAULT 100,        -- 품질·사용 가중(검색 랭킹)
    embedding     vector(1024),                             -- nl_question 임베딩(titan-embed v2 = 1024-dim; alembic 0001 texts 정본과 일치)
    source_type   varchar(24)  NOT NULL DEFAULT 'manual',   -- manual|feedback|auto-harvest|eval
    status        varchar(16)  NOT NULL DEFAULT 'active',   -- active|stale|retired (신선도)
    approved      boolean      NOT NULL DEFAULT false,      -- 큐레이션 게이트(검색은 approved 만)
    created_by    varchar(64),
    last_validated_at timestamptz,                          -- validate_sample_sql 최근 검증
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_sample_queries_scope_nl UNIQUE (scope_key, nl_question)
);
CREATE INDEX IF NOT EXISTS ix_sample_queries_scope_appr
    ON sample_queries (scope_key, approved, status);
CREATE INDEX IF NOT EXISTS ix_sample_queries_embedding_ivfflat
    ON sample_queries USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32)
    WHERE embedding IS NOT NULL;
DROP TRIGGER IF EXISTS trg_sample_queries_updated_at ON sample_queries;
CREATE TRIGGER trg_sample_queries_updated_at
    BEFORE UPDATE ON sample_queries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS sample_feedback (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key          varchar(96)  NOT NULL DEFAULT 'common',
    conversation_id    varchar(128),
    run_id             varchar(64),
    nl_question        text         NOT NULL,
    generated_sql      text,                                -- PII 마스킹 후 저장
    vote               varchar(8)   NOT NULL DEFAULT 'up',  -- up|down
    suggested          boolean      NOT NULL DEFAULT false, -- "샘플로 등록" 요청 동반
    status             varchar(16)  NOT NULL DEFAULT 'pending',  -- pending|promoted|rejected
    promoted_sample_id bigint,                              -- 승급된 sample_queries.id
    created_by         varchar(64),
    created_at         timestamptz  NOT NULL DEFAULT now(),
    updated_at         timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sample_feedback_status ON sample_feedback (status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_sample_feedback_scope ON sample_feedback (scope_key);
-- 답변당 사용자별 고유 피드백(👍/👎) — alembic 0021+0022 미러(boot idempotent 정본).
-- 한 created_by 가 한 답변(message_id, message_id_space)에 남기는 투표(suggested=false)는 1행으로
-- 강제(record_feedback UPSERT). message_id_space("display"|"core")는 표시 store id 와 core_messages
-- id 의 숫자 겹침을 구분(H5(b) — fork·마이그 경로전환 시 cross-space 충돌/오매칭 차단).
-- 과거 행(message_id NULL)·익명(created_by NULL)·"샘플 등록"(suggested=true)은 술어 제외 → 무손실.
ALTER TABLE sample_feedback ADD COLUMN IF NOT EXISTS message_id bigint;
ALTER TABLE sample_feedback ADD COLUMN IF NOT EXISTS message_id_space varchar(16) NOT NULL DEFAULT 'display';
-- 구 2-col 인덱스(0021) 정리 — 3-col 은 새 이름이라 same-name no-op trap 회피(boot 멱등).
DROP INDEX IF EXISTS ux_sample_feedback_user_msg_vote;
CREATE UNIQUE INDEX IF NOT EXISTS ux_sample_feedback_user_msg_space_vote
    ON sample_feedback (created_by, message_id, message_id_space)
    WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested = false;
DROP TRIGGER IF EXISTS trg_sample_feedback_updated_at ON sample_feedback;
CREATE TRIGGER trg_sample_feedback_updated_at
    BEFORE UPDATE ON sample_feedback
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

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
                      kb_invalidations, kb_glossary, enum_dictionary,
                      table_descriptions, column_descriptions,
                      glossary_feedback, glossary_relations, table_relationships,
                      sample_queries, sample_feedback TO agent_kb_rw;
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
                      kb_invalidations, kb_glossary, enum_dictionary,
                      table_descriptions, column_descriptions,
                      glossary_feedback, glossary_relations, table_relationships,
                      sample_queries, sample_feedback, kb_slow_queries TO agent_kb_ro;
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
-- TASK-0140: agent_memory_facts matview 폐기 — COMMENT 제거.
COMMENT ON VIEW kb_slow_queries IS 'T3-10: pg_stat_statements 기반 KB 테이블 슬로우 쿼리 모니터링. mean_exec_time > 10ms 필터.';
