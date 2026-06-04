"""baseline: agent_kb 현행 스키마 전체 재현 (TASK-0143 + TASK-0149 #15)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-02

이 revision 은 라이브 `agent_kb` 스키마(2026-06-04 read-only `pg_dump --schema-only`
실측)를 **전부 재현**한다. fresh deploy 는 `alembic upgrade head` 만으로 빈 DB 에
KB 스키마 전체(확장 3 + 스키마 2 + 함수 + 테이블 12 + 뷰 1 + 인덱스 + 트리거 + FK)
를 구축할 수 있다. alembic 이 스키마 source-of-truth 가 된다.

멱등(idempotent) 정규화:
  - 확장/스키마/테이블/인덱스: `... IF NOT EXISTS`.
  - PK/UNIQUE/FK 제약: pg_dump 의 별도 `ALTER TABLE ADD CONSTRAINT` (비멱등) 대신
    `CREATE TABLE IF NOT EXISTS` 본문에 인라인으로 접어 넣어 재실행 안전.
  - 함수/뷰: `CREATE OR REPLACE`.
  - 트리거: PG14+ `CREATE OR REPLACE TRIGGER` (라이브 PG16).
이로써 부트스트랩 DDL(`_ensure_pg_schema()`)과 공존해도 충돌 없이 재적용 가능.

pgvector(HNSW)/pg_trgm(GIN) 인덱스는 alembic op.create_index 로 표현이 어렵고
정밀도 손실 위험이 있어 **raw SQL `op.execute(...)`** 로 라이브 실측 그대로 재현한다.

drift 해소: `scripts/agent_kb_schema.sql` 은 texts.embedding 을 ivfflat(lists=32)
으로 정의했으나 라이브 실측은 HNSW(`USING hnsw (embedding vector_cosine_ops)`)다.
본 baseline 은 **라이브 실측(HNSW)** 을 정본으로 재현한다(docs/MIGRATIONS.md 참조).

운영 절차:
  - 라이브(스키마 이미 존재): `make migrate-stamp` (= alembic stamp head). DDL 0.
  - fresh deploy(빈 DB): `make migrate` (= alembic upgrade head). 위 DDL 전체 적용.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- ===========================================================================
-- 확장 + 스키마 (확장은 public 에 설치 — 라이브 실측)
-- ===========================================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE SCHEMA IF NOT EXISTS agent_runtime;

-- ===========================================================================
-- 함수: updated_at 자동 갱신 트리거 함수 (public)
-- ===========================================================================
CREATE OR REPLACE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- ===========================================================================
-- agent_runtime 스키마 테이블 (제약 인라인)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.core_conversations (
    conversation_id character varying(128) NOT NULL,
    topic character varying(256) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    owner_account_id bigint,
    owner_assigned_at timestamp with time zone,
    product_id bigint,
    product_mode character varying(8) DEFAULT 'pinned'::character varying NOT NULL,
    CONSTRAINT core_conversations_pkey PRIMARY KEY (conversation_id)
);

CREATE TABLE IF NOT EXISTS agent_runtime.core_messages (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME agent_runtime.core_messages_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    role character varying(20) NOT NULL,
    content text,
    tool_calls jsonb,
    tool_call_id character varying(128),
    name character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT core_messages_pkey PRIMARY KEY (id),
    CONSTRAINT fk_core_messages_conv FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations(conversation_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_runtime.kv (
    conversation_id character varying(128) NOT NULL,
    key character varying(128) NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT kv_pkey PRIMARY KEY (conversation_id, key)
);

CREATE TABLE IF NOT EXISTS agent_runtime.llm_usage (
    id bigint NOT NULL,
    conversation_id character varying(255),
    run_id character varying(255),
    model character varying(128),
    task character varying(64),
    prompt_tokens integer DEFAULT 0 NOT NULL,
    completion_tokens integer DEFAULT 0 NOT NULL,
    total_tokens integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_usage_pkey PRIMARY KEY (id)
);
-- llm_usage 는 라이브에서 serial 시퀀스(IDENTITY 아님) — 동등 재현.
CREATE SEQUENCE IF NOT EXISTS agent_runtime.llm_usage_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE agent_runtime.llm_usage_id_seq OWNED BY agent_runtime.llm_usage.id;
ALTER TABLE ONLY agent_runtime.llm_usage
    ALTER COLUMN id SET DEFAULT nextval('agent_runtime.llm_usage_id_seq'::regclass);

CREATE TABLE IF NOT EXISTS agent_runtime.messages (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME agent_runtime.messages_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    role character varying(32) NOT NULL,
    content text NOT NULL,
    meta_json jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT messages_pkey PRIMARY KEY (id),
    CONSTRAINT fk_messages_conv FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations(conversation_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_runtime.steps (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME agent_runtime.steps_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    run_id character varying(64) NOT NULL,
    step_index integer NOT NULL,
    action character varying(32) NOT NULL,
    tool character varying(64) NOT NULL,
    intent character varying(255) NOT NULL,
    work_text text,
    work_source character varying(16),
    reason_text text,
    reason_source character varying(16),
    args_json text NOT NULL,
    sql_text text,
    result_summary_json text,
    error_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT steps_pkey PRIMARY KEY (id),
    CONSTRAINT fk_steps_conv FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations(conversation_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_runtime.summary (
    conversation_id character varying(128) NOT NULL,
    summary text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT summary_pkey PRIMARY KEY (conversation_id),
    CONSTRAINT fk_summary_conv FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations(conversation_id) ON DELETE CASCADE
);

-- ===========================================================================
-- public 스키마 테이블 (KB) — 제약 인라인
-- ===========================================================================
CREATE TABLE IF NOT EXISTS public.fact_entries (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME public.fact_entries_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    fact_key character varying(128) NOT NULL,
    scope_key character varying(96) DEFAULT 'common'::character varying NOT NULL,
    text_hash character(64) DEFAULT ''::bpchar NOT NULL,
    fact_fingerprint character(40) NOT NULL,
    weight integer DEFAULT 1 NOT NULL,
    confidence numeric(3,2),
    source_type character varying(32),
    source_run_id character varying(64),
    source_sql text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT fact_entries_pkey PRIMARY KEY (id),
    CONSTRAINT ux_fact_entries_conv_scope_key_fp
        UNIQUE (conversation_id, scope_key, fact_key, fact_fingerprint)
)
WITH (autovacuum_vacuum_scale_factor='0', autovacuum_vacuum_threshold='500',
      autovacuum_analyze_scale_factor='0', autovacuum_analyze_threshold='250');
COMMENT ON TABLE public.fact_entries IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryFactEntries 의 Postgres 등가. M2 dual-write 부터 작성. T3-10 autovacuum 조정 적용.';

CREATE TABLE IF NOT EXISTS public.kb_invalidations (
    channel character varying(64) NOT NULL,
    invalidated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT kb_invalidations_pkey PRIMARY KEY (channel)
);

CREATE TABLE IF NOT EXISTS public.rag_documents (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME public.rag_documents_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    scope_key character varying(96) DEFAULT 'common'::character varying NOT NULL,
    doc_type character varying(32) DEFAULT 'fact'::character varying NOT NULL,
    fact_key character varying(128),
    text_hash character(64) DEFAULT ''::bpchar NOT NULL,
    content_hash character(40) NOT NULL,
    weight integer DEFAULT 1 NOT NULL,
    source_type character varying(32),
    source_run_id character varying(64),
    source_sql text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT rag_documents_pkey PRIMARY KEY (id),
    CONSTRAINT ux_rag_docs_conv_scope_key_hash
        UNIQUE (conversation_id, scope_key, fact_key, content_hash)
);
COMMENT ON TABLE public.rag_documents IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryRagDocuments 의 Postgres 등가.';

CREATE TABLE IF NOT EXISTS public.rag_objects (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME public.rag_objects_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    scope_key character varying(96) DEFAULT 'common'::character varying NOT NULL,
    object_type character varying(32) NOT NULL,
    object_key character varying(255) NOT NULL,
    schema_name character varying(128),
    table_name character varying(128),
    column_name character varying(128),
    text_hash character(64),
    weight integer DEFAULT 1 NOT NULL,
    source_type character varying(32),
    source_run_id character varying(64),
    category_domain character varying(128),
    category_entity_type character varying(64),
    category_metric_family character varying(128),
    category_event_type character varying(128),
    category_time_grain character varying(64),
    category_join_hints_json jsonb,
    category_confidence numeric(3,2),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT rag_objects_pkey PRIMARY KEY (id),
    CONSTRAINT ux_rag_objects_conv_scope_type_key
        UNIQUE (conversation_id, scope_key, object_type, object_key)
);
COMMENT ON TABLE public.rag_objects IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryRagObjects 의 Postgres 등가. T2-6: category_join_hints_json JSONB + GIN index.';

CREATE TABLE IF NOT EXISTS public.texts (
    text_hash character(64) NOT NULL,
    text_content text NOT NULL,
    embedding public.vector(1024),
    embedding_model character varying(64),
    embedded_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT texts_pkey PRIMARY KEY (text_hash)
);
COMMENT ON TABLE public.texts IS 'TASK-0015 §2.1 M1 — MySQL AgentMemoryTexts 의 Postgres 등가. embedding 컬럼은 본 테이블에만 (Blocker B-4). T2: partial ivfflat index (WHERE embedding IS NOT NULL).';

-- ===========================================================================
-- 인덱스 (btree / GIN(pg_trgm) / HNSW(pgvector)) — 라이브 실측
-- ===========================================================================
-- agent_runtime
CREATE INDEX IF NOT EXISTS ix_core_conv_owner ON agent_runtime.core_conversations USING btree (owner_account_id);
CREATE INDEX IF NOT EXISTS ix_core_conv_product ON agent_runtime.core_conversations USING btree (product_id);
CREATE INDEX IF NOT EXISTS ix_core_conv_updated ON agent_runtime.core_conversations USING btree (updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_core_messages_conv_id ON agent_runtime.core_messages USING btree (conversation_id, id);
CREATE INDEX IF NOT EXISTS ix_kv_updated ON agent_runtime.kv USING btree (updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_llm_usage_conv ON agent_runtime.llm_usage USING btree (conversation_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_created ON agent_runtime.llm_usage USING btree (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_llm_usage_model ON agent_runtime.llm_usage USING btree (model);
CREATE INDEX IF NOT EXISTS ix_messages_conv_created ON agent_runtime.messages USING btree (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_steps_conv_created ON agent_runtime.steps USING btree (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_steps_conv_run ON agent_runtime.steps USING btree (conversation_id, run_id);

-- public.fact_entries
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_key ON public.fact_entries USING btree (conversation_id, fact_key);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_run ON public.fact_entries USING btree (conversation_id, source_run_id);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_scope_key_rank ON public.fact_entries USING btree (conversation_id, scope_key, fact_key, weight, updated_at, id);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_scope_run ON public.fact_entries USING btree (conversation_id, scope_key, source_run_id);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_scope_weight ON public.fact_entries USING btree (conversation_id, scope_key, weight, updated_at);
CREATE INDEX IF NOT EXISTS ix_fact_entries_conv_weight ON public.fact_entries USING btree (conversation_id, weight, updated_at);

-- public.rag_documents
CREATE INDEX IF NOT EXISTS ix_rag_docs_conv_fact_key ON public.rag_documents USING btree (conversation_id, fact_key);
CREATE INDEX IF NOT EXISTS ix_rag_docs_conv_scope_updated ON public.rag_documents USING btree (conversation_id, scope_key, updated_at);
CREATE INDEX IF NOT EXISTS ix_rag_docs_conv_scope_weight ON public.rag_documents USING btree (conversation_id, scope_key, weight, updated_at);

-- public.rag_objects (GIN on jsonb)
CREATE INDEX IF NOT EXISTS ix_rag_objects_category ON public.rag_objects USING btree (conversation_id, scope_key, category_domain, category_event_type, updated_at);
CREATE INDEX IF NOT EXISTS ix_rag_objects_conv_scope ON public.rag_objects USING btree (conversation_id, scope_key, object_type, updated_at);
CREATE INDEX IF NOT EXISTS ix_rag_objects_join_hints_gin ON public.rag_objects USING gin (category_join_hints_json);
CREATE INDEX IF NOT EXISTS ix_rag_objects_schema_table ON public.rag_objects USING btree (schema_name, table_name, column_name);

-- public.texts (pg_trgm GIN + pgvector HNSW — 라이브 정본)
CREATE INDEX IF NOT EXISTS ix_texts_content_trgm ON public.texts USING gin (text_content public.gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_texts_embedding_hnsw ON public.texts USING hnsw (embedding public.vector_cosine_ops);

-- ===========================================================================
-- 뷰 (pg_stat_statements 의존 — 확장 생성 이후라 안전)
-- ===========================================================================
CREATE OR REPLACE VIEW public.kb_slow_queries AS
 SELECT "left"(query, 120) AS query_preview,
    round((mean_exec_time)::numeric, 2) AS avg_ms,
    round((max_exec_time)::numeric, 2) AS max_ms,
    calls,
    round(((total_exec_time / (NULLIF(calls, 0))::double precision))::numeric, 2) AS total_per_call_ms,
    (rows / NULLIF(calls, 0)) AS avg_rows
   FROM public.pg_stat_statements
  WHERE ((query ~* 'fact_entries|rag_documents|rag_objects|texts'::text) AND (mean_exec_time > (10)::double precision))
  ORDER BY mean_exec_time DESC
 LIMIT 50;
COMMENT ON VIEW public.kb_slow_queries IS 'T3-10: pg_stat_statements 기반 KB 테이블 슬로우 쿼리 모니터링. mean_exec_time > 10ms 필터.';

-- ===========================================================================
-- 트리거 (PG14+ CREATE OR REPLACE TRIGGER — 라이브 PG16)
-- ===========================================================================
CREATE OR REPLACE TRIGGER trg_core_conv_updated_at BEFORE UPDATE ON agent_runtime.core_conversations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_kv_updated_at BEFORE UPDATE ON agent_runtime.kv FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_summary_updated_at BEFORE UPDATE ON agent_runtime.summary FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_fact_entries_updated_at BEFORE UPDATE ON public.fact_entries FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_rag_docs_updated_at BEFORE UPDATE ON public.rag_documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_rag_objects_updated_at BEFORE UPDATE ON public.rag_objects FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
"""


# downgrade: 의존 역순(뷰 → 트리거 → 인덱스(테이블 DROP 으로 동반) → 테이블 →
# 함수 → 스키마). 확장은 다른 객체가 의존할 수 있어 DROP 하지 않는다(안전).
DOWNGRADE_SQL = r"""
DROP VIEW IF EXISTS public.kb_slow_queries;

-- public 테이블 (CASCADE 로 인덱스/트리거/제약 동반 제거)
DROP TABLE IF EXISTS public.texts CASCADE;
DROP TABLE IF EXISTS public.rag_objects CASCADE;
DROP TABLE IF EXISTS public.rag_documents CASCADE;
DROP TABLE IF EXISTS public.kb_invalidations CASCADE;
DROP TABLE IF EXISTS public.fact_entries CASCADE;

-- agent_runtime 테이블 (FK 자식 먼저, core_conversations 마지막)
DROP TABLE IF EXISTS agent_runtime.summary CASCADE;
DROP TABLE IF EXISTS agent_runtime.steps CASCADE;
DROP TABLE IF EXISTS agent_runtime.messages CASCADE;
DROP TABLE IF EXISTS agent_runtime.llm_usage CASCADE;
DROP TABLE IF EXISTS agent_runtime.kv CASCADE;
DROP TABLE IF EXISTS agent_runtime.core_messages CASCADE;
DROP TABLE IF EXISTS agent_runtime.core_conversations CASCADE;

DROP FUNCTION IF EXISTS public.set_updated_at();

DROP SCHEMA IF EXISTS agent_runtime CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
