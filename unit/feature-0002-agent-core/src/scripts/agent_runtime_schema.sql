-- ============================================================================
-- AR-M1 (TASK-0112) cycle: agent_runtime Postgres schema DDL 정본.
--
-- 본 DDL 은 MySQL agent_memory DB 의 6 agent runtime 테이블을 PostgreSQL
-- agent_kb.agent_runtime schema 로 이관하는 구조 정의.
-- AR-M2 dual-write phase 부터 본 schema 의 테이블이 runtime write 의 mirror target.
-- AR-M4 cutover 시점에 read path 도 본 schema 사용.
--
-- 대상 테이블 (MySQL → Postgres):
--   AgentCoreConversations  → agent_runtime.core_conversations
--   AgentCoreMessages       → agent_runtime.core_messages
--   AgentMemoryKv           → agent_runtime.kv
--   AgentMemoryMessages     → agent_runtime.messages
--   AgentMemorySteps        → agent_runtime.steps
--   AgentMemorySummary      → agent_runtime.summary
--
-- Dialect 변환 매핑 (MySQL → Postgres):
--   bigint AUTO_INCREMENT         → bigint GENERATED ALWAYS AS IDENTITY
--   varchar(N) COLLATE utf8mb4_*  → varchar(N) (Postgres default UTF-8)
--   longtext                      → text
--   timestamp(3) ON UPDATE CURR.. → timestamptz + BEFORE UPDATE trigger
--   json                          → jsonb
--   PRIMARY KEY (a, b)            → PRIMARY KEY (a, b) (composite 유지)
--
-- 명명 규칙: snake_case (Postgres convention)
--   AgentCoreConversations  → core_conversations
--   AgentCoreMessages       → core_messages
--   AgentMemoryKv.ConversationId → kv.conversation_id
--   AgentMemoryKv.Key           → kv.key
--   AgentMemoryKv.Value         → kv.value
--   AgentMemoryMessages.Id      → messages.id
--   AgentMemorySteps.RunId      → steps.run_id
--   AgentMemorySteps.StepIndex  → steps.step_index
--   등
--
-- 사용법 (bootstrap):
--   docker exec repo-postgres-1 psql -U postgres -d agent_kb \
--     -f /path/to/agent_runtime_schema.sql
--   또는 bin/agent-runtime-bootstrap.sh --apply-schema 가 본 파일 적용
--   (AR-M1 이후 bootstrap.sh 확장 예정)
-- ============================================================================

-- 0-pre. schema 존재 보장 (bootstrap.sh 가 선행 실행되어야 하지만 방어적 guard).
CREATE SCHEMA IF NOT EXISTS agent_runtime;

-- 0. UPDATE timestamp 자동 갱신 트리거 함수 (MySQL ON UPDATE 대체).
--    agent_kb_schema.sql 의 set_updated_at() 과 동일 함수 — CREATE OR REPLACE 로
--    중복 정의 안전.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 1. core_conversations — MySQL AgentCoreConversations 등가
--    PK: conversation_id varchar(128) — MySQL 원본과 동일 (UUID 스타일 string)
--    인덱스: owner_account_id, product_id, updated_at
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.core_conversations (
    conversation_id   varchar(128) PRIMARY KEY,
    topic             varchar(256) DEFAULT '',
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    owner_account_id  bigint,
    owner_assigned_at timestamptz,
    product_id        bigint,
    product_mode      varchar(8)   NOT NULL DEFAULT 'pinned',
    -- TASK-0248: 참조 제품이 삭제되면 그 제품을 pinned 한 대화는 차단(blocked)으로
    -- 전환된다 — 이력 열람은 가능하되 더 이상 진행(새 메시지)할 수 없다. blocked_at
    -- 이 NULL 이 아니면 차단. 정본은 alembic 0005_core_conv_blocked.
    blocked_at        timestamptz,
    blocked_reason    varchar(256),
    -- TASK-0273: "삭제" 를 soft-archive 로 전환 — archived_at 이 NULL 이 아니면 보관
    -- (소유자 목록 숨김 + 진행 차단, 데이터 보존). 정본은 alembic 0007_core_conv_archived.
    archived_at            timestamptz,
    archived_by_account_id bigint,
    -- TASK-20260617T082131: fork 본 식별 마커. fork 는 소스(타 계정 가능) 메시지를 복사하고
    -- owner 를 포크계정으로 재귀속하므로, owner 격리만으론 콘텐츠 출처 격리가 안 됨. account
    -- insight 추출·회상은 forked_from_conversation_id IS NULL 만 대상(cross-account 누출 차단).
    forked_from_conversation_id varchar(128)
);

-- TASK-0248: 기존 테이블(이미 생성됨)에도 멱등 적용 — alembic 미적용 환경 self-heal.
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS blocked_at timestamptz;
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS blocked_reason varchar(256);
-- TASK-0273: archived 컬럼 멱등 ALTER (alembic 미적용 환경 self-heal).
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS archived_by_account_id bigint;
-- TASK-20260617T082131: fork 마커 멱등 ALTER (alembic 미적용 환경 self-heal).
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS forked_from_conversation_id varchar(128);

CREATE INDEX IF NOT EXISTS ix_core_conv_owner
    ON agent_runtime.core_conversations (owner_account_id);

CREATE INDEX IF NOT EXISTS ix_core_conv_archived
    ON agent_runtime.core_conversations (archived_at);

CREATE INDEX IF NOT EXISTS ix_core_conv_product
    ON agent_runtime.core_conversations (product_id);

CREATE INDEX IF NOT EXISTS ix_core_conv_updated
    ON agent_runtime.core_conversations (updated_at DESC);

CREATE OR REPLACE TRIGGER trg_core_conv_updated_at
    BEFORE UPDATE ON agent_runtime.core_conversations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 2. core_messages — MySQL AgentCoreMessages 등가
--    PK: id (bigint identity)
--    FK: conversation_id → core_conversations (application-level, 명시적 FK 추가)
--    인덱스: (conversation_id, id)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.core_messages (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id varchar(128) NOT NULL,
    role            varchar(20)  NOT NULL,
    content         text,
    tool_calls      jsonb,
    tool_call_id    varchar(128),
    name            varchar(64),
    created_at      timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_core_messages_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_core_messages_conv_id
    ON agent_runtime.core_messages (conversation_id, id);

-- ============================================================================
-- 3. kv — MySQL AgentMemoryKv 등가
--    PK: (conversation_id, key) — composite (MySQL 원본과 동일)
--    특이사항: __global__ scope 지원 (conversation_id='__global__')
--    FK 의도적 생략: __global__ sentinel (cross-conversation KV) 이
--    core_conversations 에 존재하지 않으므로 FK 가 걸리면 INSERT 전부 실패.
--    application-level validation 으로 대체 (MySQL 원본과 동일 정책).
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.kv (
    conversation_id varchar(128) NOT NULL,
    key             varchar(128) NOT NULL,
    value           text         NOT NULL,
    updated_at      timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (conversation_id, key)
);

CREATE INDEX IF NOT EXISTS ix_kv_updated
    ON agent_runtime.kv (updated_at DESC);

CREATE OR REPLACE TRIGGER trg_kv_updated_at
    BEFORE UPDATE ON agent_runtime.kv
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 4. messages — MySQL AgentMemoryMessages 등가
--    PK: id (bigint identity)
--    FK: conversation_id → core_conversations (application-level)
--    인덱스: (conversation_id, created_at DESC)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.messages (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id varchar(128) NOT NULL,
    role            varchar(32)  NOT NULL,
    content         text         NOT NULL,
    meta_json       jsonb,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_messages_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_messages_conv_created
    ON agent_runtime.messages (conversation_id, created_at DESC);

-- ============================================================================
-- 5. steps — MySQL AgentMemorySteps 등가
--    PK: id (bigint identity)
--    FK: conversation_id → core_conversations (application-level)
--    인덱스: (conversation_id, created_at DESC), (conversation_id, run_id)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.steps (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id       varchar(128) NOT NULL,
    run_id                varchar(64)  NOT NULL,
    step_index            int          NOT NULL,
    action                varchar(32)  NOT NULL,
    tool                  varchar(64)  NOT NULL,
    intent                varchar(255) NOT NULL,
    work_text             text,
    work_source           varchar(16),
    reason_text           text,
    reason_source         varchar(16),
    args_json             text         NOT NULL,
    sql_text              text,
    result_summary_json   text,
    error_text            text,
    created_at            timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_steps_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_steps_conv_created
    ON agent_runtime.steps (conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_steps_conv_run
    ON agent_runtime.steps (conversation_id, run_id);

-- ============================================================================
-- 6. summary — MySQL AgentMemorySummary 등가
--    PK: conversation_id — one row per conversation
--    FK: conversation_id → core_conversations
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.summary (
    conversation_id varchar(128) PRIMARY KEY,
    summary         text         NOT NULL,
    updated_at      timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_summary_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);

CREATE OR REPLACE TRIGGER trg_summary_updated_at
    BEFORE UPDATE ON agent_runtime.summary
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 6b. LLM usage 회계 (TASK-0136 #11) — 토큰 사용량 기록. 비용 가시성/예산용.
--     account_id 는 conversation_id → core_conversations.owner_account_id join 으로 도출
--     (insight 워커 등 시스템 사용은 owner NULL). admin 한정 노출(console.usage.read RBAC).
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.llm_usage (
    id                BIGSERIAL PRIMARY KEY,
    conversation_id   VARCHAR(255),
    run_id            VARCHAR(255),
    model             VARCHAR(128),
    resolved_model    VARCHAR(128),
    task              VARCHAR(64),
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_llm_usage_created ON agent_runtime.llm_usage (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_llm_usage_conv ON agent_runtime.llm_usage (conversation_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_model ON agent_runtime.llm_usage (model);

-- ============================================================================
-- 6c. datasource_health — datasource 연결 health 정본 (TASK-0255 R2)
--     insight-worker 가 매 cycle datasource 별 연결 상태(conn_health 권위 status + scan_outcome)를 upsert.
--     관리콘솔이 "연결 불안정으로 미커버"를 "권한 실패"와 구분해 표면화. PK=scope_key(엔드포인트 해시).
--     자격증명 비영속(host/port/engine/status/fails/errno-tag 만). alembic 0006 과 동형 — fresh deploy 정합.
--     §7 의 GRANT ... ON ALL TABLES 가 본 테이블을 자동 커버(부트스트랩 스냅샷).
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.datasource_health (
    scope_key          VARCHAR(64) PRIMARY KEY,
    datasource_label   VARCHAR(255),
    engine             VARCHAR(16)  NOT NULL,
    host               VARCHAR(255),
    port               INTEGER,
    status             VARCHAR(16)  NOT NULL,
    last_scan_outcome  VARCHAR(24),
    fail_count         INTEGER      NOT NULL DEFAULT 0,
    last_error_tag     VARCHAR(80),
    last_checked_at    TIMESTAMPTZ,
    last_scan_at       TIMESTAMPTZ,
    last_transition_at TIMESTAMPTZ,
    run_id             VARCHAR(64),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_datasource_health_status  ON agent_runtime.datasource_health (status);
CREATE INDEX IF NOT EXISTS ix_datasource_health_updated ON agent_runtime.datasource_health (updated_at DESC);

-- ============================================================================
-- 6d. core_attachments (+ 부속 3) — 첨부 메타 MySQL→PG 통합 (TASK-0277)
--     MySQL agent_memory 의 첨부 4 테이블 등가. 정본은 alembic 0008_core_attachments.
--     id 는 MySQL Id 보존(GENERATED ALWAYS 금지) — dual-write 기간 MySQL 이 ID 권위자,
--     RootAttachmentId/AttachmentId/프론트 URL 이 기존 Id 참조하므로 신규발급 시 무결성 붕괴.
--     아래 §7 의 GRANT ... ON ALL TABLES 가 본 테이블들을 자동 커버(부트스트랩 스냅샷).
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.core_attachments (
    id                          bigint        PRIMARY KEY,
    conversation_id             varchar(128)  NOT NULL,
    account_id                  bigint        NOT NULL,
    object_key                  varchar(512)  NOT NULL,
    original_filename           varchar(255)  NOT NULL,
    filename_hmac               char(64)      NOT NULL,
    mime_type                   varchar(128)  NOT NULL,
    size_bytes                  bigint        NOT NULL,
    size_bucket                 varchar(16)   NOT NULL,
    sha256                      char(64)      NOT NULL,
    kind                        varchar(16)   NOT NULL,
    upload_status               varchar(24)   NOT NULL DEFAULT 'uploaded',
    attachment_derived_messages jsonb,
    created_at                  timestamptz   NOT NULL DEFAULT now(),
    deleted_at                  timestamptz,
    delete_pending              smallint      NOT NULL DEFAULT 0,
    delete_reason               varchar(16),
    meta_json                   jsonb,
    root_attachment_id          bigint,
    version_number              int           NOT NULL DEFAULT 1,
    created_by_role             varchar(16)   NOT NULL DEFAULT 'user',
    superseded_at               timestamptz,
    -- conversation FK 의도적 미설정(alembic 0009): MySQL 원본은 conversation FK 가 없어 대화 삭제된
    -- orphan 첨부가 정상 존재 → strict FK 면 faithful 이전 불가. conversation_id 컬럼+인덱스로 JOIN 유지.
    CONSTRAINT uq_core_attachments_version_chain
        UNIQUE (root_attachment_id, version_number)
);
CREATE INDEX IF NOT EXISTS ix_core_attachments_conv
    ON agent_runtime.core_attachments (conversation_id, deleted_at);
CREATE INDEX IF NOT EXISTS ix_core_attachments_account
    ON agent_runtime.core_attachments (account_id, created_at);
CREATE INDEX IF NOT EXISTS ix_core_attachments_status
    ON agent_runtime.core_attachments (upload_status, delete_pending);
CREATE INDEX IF NOT EXISTS ix_core_attachments_root
    ON agent_runtime.core_attachments (root_attachment_id);

CREATE TABLE IF NOT EXISTS agent_runtime.core_attachment_sandbox_schemas (
    id              bigint        PRIMARY KEY,
    conversation_id varchar(128)  NOT NULL,
    schema_name     varchar(64)   NOT NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    dropped_at      timestamptz,
    delete_pending  smallint      NOT NULL DEFAULT 0,
    CONSTRAINT uq_core_att_sandbox_conv   UNIQUE (conversation_id),
    CONSTRAINT uq_core_att_sandbox_schema UNIQUE (schema_name)
    -- conversation FK 의도적 미설정(alembic 0009, core_attachments 와 동일 사유 — orphan 허용)
);
CREATE INDEX IF NOT EXISTS ix_core_att_sandbox_pending
    ON agent_runtime.core_attachment_sandbox_schemas (delete_pending, dropped_at);

CREATE TABLE IF NOT EXISTS agent_runtime.core_attachment_derived_messages (
    id              bigint        PRIMARY KEY,
    attachment_id   bigint        NOT NULL,
    message_id      bigint        NOT NULL,   -- 비-FK: PG messages.id 와 id-space 불일치(cutover 재발급)
    derivation_type varchar(24)   NOT NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT fk_core_att_derived_att
        FOREIGN KEY (attachment_id)
        REFERENCES agent_runtime.core_attachments (id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_core_att_derived_att
    ON agent_runtime.core_attachment_derived_messages (attachment_id);
CREATE INDEX IF NOT EXISTS ix_core_att_derived_msg
    ON agent_runtime.core_attachment_derived_messages (message_id);
CREATE INDEX IF NOT EXISTS ix_core_att_derived_type
    ON agent_runtime.core_attachment_derived_messages (derivation_type, created_at);

CREATE TABLE IF NOT EXISTS agent_runtime.core_attachment_provider_files (
    id                     bigint        PRIMARY KEY,
    attachment_id          bigint        NOT NULL,
    provider               varchar(32)   NOT NULL,
    provider_file_id       varchar(255)  NOT NULL,
    uploaded_at            timestamptz   NOT NULL DEFAULT now(),
    deleted_at             timestamptz,
    last_delete_attempt_at timestamptz,
    delete_attempt_count   int           NOT NULL DEFAULT 0,
    last_error             varchar(512),
    CONSTRAINT fk_core_att_provider_att
        FOREIGN KEY (attachment_id)
        REFERENCES agent_runtime.core_attachments (id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_core_att_provider_att
    ON agent_runtime.core_attachment_provider_files (attachment_id);
CREATE INDEX IF NOT EXISTS ix_core_att_provider_pf
    ON agent_runtime.core_attachment_provider_files (provider, provider_file_id);
CREATE INDEX IF NOT EXISTS ix_core_att_provider_pending
    ON agent_runtime.core_attachment_provider_files (deleted_at, last_delete_attempt_at);

-- ============================================================================
-- 7. Role grants (post-table creation)
--    DEFAULT PRIVILEGES 가 이미 설정됐으므로 bootstrapped role 에는 자동 적용됨.
--    하지만 명시적 grant 로 이중 보장.
-- ============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA agent_runtime
    TO agent_kb_rw;

GRANT SELECT
    ON ALL TABLES IN SCHEMA agent_runtime
    TO agent_kb_ro;

GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA agent_runtime
    TO agent_kb_rw;
