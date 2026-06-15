"""agent_runtime.core_attachments (+ 부속 3 테이블) — 첨부 메타 MySQL→PG 통합 (TASK-0277).

대화/메시지는 이미 PG agent_runtime 으로 cutover 됐으나(AGENT_RUNTIME_READ_BACKEND=postgres),
첨부 메타는 여전히 MySQL agent_memory 의 4 테이블이 정본이었다:
  WebConversationAttachments              → agent_runtime.core_attachments
  WebConversationAttachmentsSandboxSchemas → agent_runtime.core_attachment_sandbox_schemas
  WebAttachmentDerivedMessages            → agent_runtime.core_attachment_derived_messages
  WebConversationAttachmentProviderFiles  → agent_runtime.core_attachment_provider_files
MinIO 바이트·추출 RAG(agent_kb)는 이전 대상 아님 — object_key 참조만 PG 로 옮긴다.

**ID 권위 (load-bearing)**: core_attachments.id 는 `bigint PRIMARY KEY`(GENERATED ALWAYS 금지).
dual-write 기간 동안 MySQL AUTO_INCREMENT 가 ID 권위자이고, app.py 는 MySQL lastrowid 를 PG 에 *명시*
INSERT 한다. RootAttachmentId 자기참조·WebAttachmentDerivedMessages.AttachmentId·MetaJson.assistant_edit_of·
프론트 URL(/api/attachments/{id})이 모두 기존 Id 를 참조하므로 PG 가 신규 ID 를 발급하면 참조 무결성이
붕괴한다. MySQL 쓰기 폐기(후속 decommission cycle)에서 sequence/identity 부착·동기화한다. 부속 테이블도
backfill 멱등(ON CONFLICT (id) DO NOTHING)을 위해 동일하게 MySQL Id 를 보존한다.

**UNIQUE 동작**: uq_core_attachments_version_chain (root_attachment_id, version_number) 은 PG 기본
NULLS DISTINCT 라 MySQL UNIQUE 의 NULL 중복허용과 동일 — 기존 단일첨부(root=NULL, version=1 다수)와 무충돌.

**message_id 비-FK**: core_attachment_derived_messages.message_id 는 MySQL 메시지 id 값을 그대로 보존한다.
PG messages.id 는 cutover 시 GENERATED ALWAYS AS IDENTITY 로 *재발급*됐으므로 MySQL id 와 대응하지 않는다
→ FK 를 걸 수 없다(id-space 불일치). 느슨한 비정규화 참조로 둔다.

**DEPLOY TRAP (load-bearing — 0006 datasource_health 동형)**: baseline 0001 은 GRANT 를 포함하지 않고
ALTER DEFAULT PRIVILEGES 는 public 스키마에만 설정됐다. 본 마이그는 postgres **superuser** 로 적용
(bin/alembic-migrate.sh)되므로, 신규 테이블에 **명시 GRANT 가 없으면** web(agent_kb_rw)이 INSERT/SELECT 시
permission denied → dual-write/read 가 조용히 실패한다. 아래 GRANT 필수.

web 컨테이너는 DML-only role 이라 런타임 DDL 불가 → 본 마이그(superuser offline SQL)가 정본 적용 경로.
부트스트랩 DDL(agent_runtime_schema.sql)에도 동일 CREATE/GRANT 를 반영(fresh deploy 정합). revision 이
스키마 권위. 신규 테이블 CREATE + 인덱스 + GRANT 만(기존 데이터 무손실, 안전).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_core_attachments"
down_revision: Union[str, None] = "0007_core_conv_archived"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1. core_attachments — WebConversationAttachments 등가 (정본)
--    id 는 MySQL Id 보존(GENERATED ALWAYS 금지 — ID 권위 docstring 참조).
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
    -- TASK-0275 버전 체인 컬럼
    root_attachment_id          bigint,
    version_number              int           NOT NULL DEFAULT 1,
    created_by_role             varchar(16)   NOT NULL DEFAULT 'user',
    superseded_at               timestamptz,
    CONSTRAINT fk_core_attachments_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE,
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

-- 2. core_attachment_sandbox_schemas — WebConversationAttachmentsSandboxSchemas 등가
--    1 conversation = 1 sandbox schema (MySQL agent_memory 내 CREATE SCHEMA 라이프사이클 추적 메타).
CREATE TABLE IF NOT EXISTS agent_runtime.core_attachment_sandbox_schemas (
    id              bigint        PRIMARY KEY,
    conversation_id varchar(128)  NOT NULL,
    schema_name     varchar(64)   NOT NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    dropped_at      timestamptz,
    delete_pending  smallint      NOT NULL DEFAULT 0,
    CONSTRAINT uq_core_att_sandbox_conv   UNIQUE (conversation_id),
    CONSTRAINT uq_core_att_sandbox_schema UNIQUE (schema_name),
    CONSTRAINT fk_core_att_sandbox_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_core_att_sandbox_pending
    ON agent_runtime.core_attachment_sandbox_schemas (delete_pending, dropped_at);

-- 3. core_attachment_derived_messages — WebAttachmentDerivedMessages 등가 (many-to-many 조인)
--    attachment_id 는 core_attachments FK(CASCADE). message_id 는 비-FK(id-space 불일치, docstring 참조).
CREATE TABLE IF NOT EXISTS agent_runtime.core_attachment_derived_messages (
    id              bigint        PRIMARY KEY,
    attachment_id   bigint        NOT NULL,
    message_id      bigint        NOT NULL,
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

-- 4. core_attachment_provider_files — WebConversationAttachmentProviderFiles 등가
--    제3자 LLM Files API 라이프사이클(현재 라이브 writer 없음 — 구조 parity 만).
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

-- 명시 GRANT (DEPLOY TRAP — superuser 적용이라 ALL TABLES 스냅샷·DEFAULT PRIVILEGES 가 커버 못 함).
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.core_attachments                 TO agent_kb_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.core_attachment_sandbox_schemas  TO agent_kb_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.core_attachment_derived_messages TO agent_kb_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.core_attachment_provider_files   TO agent_kb_rw;
GRANT SELECT ON agent_runtime.core_attachments                 TO agent_kb_ro;
GRANT SELECT ON agent_runtime.core_attachment_sandbox_schemas  TO agent_kb_ro;
GRANT SELECT ON agent_runtime.core_attachment_derived_messages TO agent_kb_ro;
GRANT SELECT ON agent_runtime.core_attachment_provider_files   TO agent_kb_ro;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.core_attachment_provider_files;
DROP TABLE IF EXISTS agent_runtime.core_attachment_derived_messages;
DROP TABLE IF EXISTS agent_runtime.core_attachment_sandbox_schemas;
DROP TABLE IF EXISTS agent_runtime.core_attachments;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
