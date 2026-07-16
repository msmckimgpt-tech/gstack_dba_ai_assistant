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
    forked_from_conversation_id varchar(128),
    -- feature-0009 gc-group-authz-flag: 그룹 대화 영구 플래그. 공유 링크(joinable) 생성 또는
    -- join 시 true 로 확정 — send-routing(비멘션=사람채팅)·사이드바 배지의 그룹 판정 신호.
    -- 정본은 alembic 0016_core_conv_is_group.
    is_group               boolean NOT NULL DEFAULT false
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
-- feature-0009 gc-group-authz-flag: is_group 멱등 ALTER (alembic 0016 미적용 환경 self-heal).
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS is_group boolean NOT NULL DEFAULT false;
-- share-visibility-window (alembic 0037): windowed 멤버 존재 게이트 플래그.
--   false(기본) → 가시성 필터 완전 우회(무회귀). true → loader 가 actor window 해석 + fail-closed.
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS has_restricted_members boolean NOT NULL DEFAULT false;
-- feature-0019 message-editing (alembic 0041): 브랜치(메시지 편집) 게이트 플래그 + 활성 leaf.
--   has_branches=false(기본) → recall/history 가 기존 linear 경로 그대로(회귀 0). 첫 편집에서 set.
--   active_leaf_message_id → 활성 브랜치 leaf(core_messages.id). NULL=linear tail(=MAX(id)).
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS has_branches boolean NOT NULL DEFAULT false;
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS active_leaf_message_id bigint;
-- display store 전용 활성 브랜치 leaf (core 와 대칭 — /api/history 표시 경로).
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS active_display_leaf_message_id bigint;

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

-- feature-0009-group-conversation (TASK-20260619T023140): 그룹 대화
--   sender_account_id      — 메시지 발신 account 귀속(멀티 멤버). NULL=레거시/시스템.
--   thread_root_message_id — Slack형 스레드 컬럼 훅. v1 동작 미연동(S6 에서 연동).
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS sender_account_id bigint;
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS thread_root_message_id bigint;

-- 스레드 컬럼 훅용 인덱스 (메인 타임라인 = thread_root_message_id IS NULL).
CREATE INDEX IF NOT EXISTS ix_core_messages_thread
    ON agent_runtime.core_messages (conversation_id, thread_root_message_id);

-- share-visibility-window (alembic 0037): owner-answer display-tag recall-측 봉인(REVIEW M1).
--   assistant 답변이 그린 recall 하한. NULL=미태깅. recall_full 은 epoch sentinel 로 기록.
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS recall_floor_created_at timestamptz;

-- share-visibility-window (alembic 0037): LLM recall 의 created_at 범위 술어용 인덱스.
--   windowed 멤버의 가시 경계(floor/ceiling)는 core_messages 를 created_at 으로 필터한다.
CREATE INDEX IF NOT EXISTS ix_core_messages_conv_created
    ON agent_runtime.core_messages (conversation_id, created_at);

-- feature-0019 message-editing (alembic 0041): 대화 내부 브랜치 트리(메시지 편집·재답변).
--   parent_message_id    — 브랜치 predecessor(같은 store id). NULL=대화 첫 메시지/비분기.
--   edit_root_message_id — 편집된 user 메시지 버전 체인 root(첫 버전 id). 형제 버전 그룹핑/정렬.
--   edit_version         — 버전 순번(1=원본).
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS parent_message_id bigint;
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS edit_root_message_id bigint;
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS edit_version integer NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS ix_core_messages_parent
    ON agent_runtime.core_messages (conversation_id, parent_message_id);
CREATE INDEX IF NOT EXISTS ix_core_messages_edit_root
    ON agent_runtime.core_messages (edit_root_message_id)
    WHERE edit_root_message_id IS NOT NULL;

-- ============================================================================
-- 2b. conversation_members — feature-0009-group-conversation (그룹 대화 멤버십)
--    PK: (conversation_id, account_id) — 멤버당 1행.
--    core_conversations.owner_account_id 는 backward-compat 로 유지하되, 멤버십이
--    열람 권한의 정본이 된다. role: 'owner' | 'member'.
--    backfill: 기존 대화의 owner_account_id → owner member 1행 (멱등, app 측 수행).
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.conversation_members (
    conversation_id       varchar(128) NOT NULL,
    account_id            bigint       NOT NULL,
    role                  varchar(16)  NOT NULL DEFAULT 'member',
    joined_at             timestamptz  NOT NULL DEFAULT now(),
    invited_by_account_id bigint,
    PRIMARY KEY (conversation_id, account_id),
    CONSTRAINT fk_conv_members_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);

-- 멤버 기준 대화 목록 조회용 (_list_conversations 멤버십 OR). account_id 선두.
CREATE INDEX IF NOT EXISTS ix_conv_members_account
    ON agent_runtime.conversation_members (account_id);

-- feature-0009 gc-unread-badge (alembic 0019): 멤버별 안 읽은 메세지 커서.
--   last_read_message_id — 그 멤버가 마지막으로 읽은 core_messages.id. NULL=한 번도 안 읽음.
--   사이드바 unread 배지 = id > last_read_message_id 인 (본인 미발신) user/assistant 메세지 수.
ALTER TABLE agent_runtime.conversation_members
    ADD COLUMN IF NOT EXISTS last_read_message_id bigint;

-- ============================================================================
-- 2c. conversation_member_bans — feature-0009 member-kick-ban
--    소유자(owner)가 특정 account 를 이 대화에서 차단(ban) → 공유 링크로 재참여 영구 차단.
--    추방(kick)=conversation_members 에서 제거(재참여 가능). 차단(ban)=제거 + 이 테이블 등재
--    (POST /api/share/{token}/join 가 is_banned 체크로 거부). 해제(unban)=이 테이블에서 제거.
--    PK=(conversation_id, account_id) — account 당 1행. owner 는 차단 불가(엔드포인트 가드).
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.conversation_member_bans (
    conversation_id       varchar(128) NOT NULL,
    account_id            bigint       NOT NULL,
    banned_at             timestamptz  NOT NULL DEFAULT now(),
    banned_by_account_id  bigint,
    reason                varchar(512),
    PRIMARY KEY (conversation_id, account_id),
    CONSTRAINT fk_conv_member_bans_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);

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

-- feature-0019 message-editing (alembic 0041): 표시 store 브랜치 미러(core_messages 와 동형,
--   각 store 내부 id-space 로 저장 — cross-store 시각 cut 불필요, ANCHOR INV-5).
ALTER TABLE agent_runtime.messages
    ADD COLUMN IF NOT EXISTS parent_message_id bigint;
ALTER TABLE agent_runtime.messages
    ADD COLUMN IF NOT EXISTS edit_root_message_id bigint;
ALTER TABLE agent_runtime.messages
    ADD COLUMN IF NOT EXISTS edit_version integer NOT NULL DEFAULT 1;
-- 브랜치-헤드 sibling → core 짝 링크(브랜치 전환 좌표).
ALTER TABLE agent_runtime.messages
    ADD COLUMN IF NOT EXISTS core_message_id bigint;

CREATE INDEX IF NOT EXISTS ix_messages_parent
    ON agent_runtime.messages (conversation_id, parent_message_id);
CREATE INDEX IF NOT EXISTS ix_messages_edit_root
    ON agent_runtime.messages (edit_root_message_id)
    WHERE edit_root_message_id IS NOT NULL;

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
    latency_ms        INTEGER,        -- 0030: LLM 호출 전체 왕복(생성 포함) ms. best-effort, 미측정 NULL.
    target            VARCHAR(200),   -- 0032: 인사이트 분석 대상(schema / schema.table / 노드 FQN). 표시 전용, 집계 무영향(task 분리).
    step_gap_ms       INTEGER,        -- 0033: 에이전트 라운드 간 간격(도구·오케스트레이션) ms. 지연 KPI(p50/p95)의 '단계 간 간격' 축. 첫 라운드/단발 호출 NULL.
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
-- 6e. llm_provider_health — LLM provider 외부요인 제한 정본 (TASK-20260619T014034)
--     ask-worker(agent_core) 가 LLM 호출 실패/성공으로 passive upsert, web probe(hybrid)
--     가 선제 upsert. 사용자가 "AWS Bedrock 키 만료" 등 외부 제한을 명시 확인하도록 표면화.
--     PK=provider(bedrock|local|openai). **자격증명 비영속** — state/kind/message/error_tag
--     (예외 클래스명만)·source·since 만. api key·AWS secret 절대 미저장(datasource_health 동형).
--     §7 의 GRANT ... ON ALL TABLES 가 본 테이블을 자동 커버하지만, alembic 0011 은 superuser
--     적용이라 명시 GRANT 도 둔다(0006 DEPLOY TRAP 동형).
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runtime.llm_provider_health (
    provider    VARCHAR(32) PRIMARY KEY,    -- bedrock | local | openai
    state       VARCHAR(16) NOT NULL,        -- ok | restricted | unknown
    kind        VARCHAR(32),                 -- credential_expired | auth_invalid | throttled | unavailable | not_configured | unknown
    message     VARCHAR(512),                -- 사용자 친화 한국어 메시지
    error_tag   VARCHAR(120),                -- 예외 클래스명/코드 축약(비밀 비포함)
    source      VARCHAR(16),                 -- ask | probe
    since       TIMESTAMPTZ,                 -- 현재 state 시작 시각(edge)
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_llm_provider_health_state   ON agent_runtime.llm_provider_health (state);
CREATE INDEX IF NOT EXISTS ix_llm_provider_health_updated ON agent_runtime.llm_provider_health (updated_at DESC);

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

CREATE TABLE IF NOT EXISTS agent_runtime.redteam_reviews (
    id                BIGSERIAL PRIMARY KEY,
    conversation_id   TEXT,
    run_id            TEXT,
    verdict           VARCHAR(16) NOT NULL,
    findings          JSONB,
    block_count       INTEGER NOT NULL DEFAULT 0,
    warn_count        INTEGER NOT NULL DEFAULT 0,
    verify_verdict    VARCHAR(16),
    revision_applied  BOOLEAN NOT NULL DEFAULT FALSE,
    model             VARCHAR(128),
    latency_ms        INTEGER,
    reasoning_level   VARCHAR(16),
    is_group          BOOLEAN NOT NULL DEFAULT FALSE,
    -- feature-0002 축 인지 재도출(도구 재추론) 관측치 (0043 migration 미러).
    rederive_applied     BOOLEAN NOT NULL DEFAULT FALSE,
    rederive_tool_rounds INTEGER NOT NULL DEFAULT 0,
    rederive_axis        VARCHAR(64),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_redteam_reviews_conversation
    ON agent_runtime.redteam_reviews (conversation_id, id DESC);

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
