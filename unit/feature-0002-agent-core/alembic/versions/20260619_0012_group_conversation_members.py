"""agent_runtime: 그룹 대화 멤버십 + 메시지 발신자 귀속 (feature-0009-group-conversation).

여러 account 가 하나의 대화에 참여하는 그룹 대화의 정본 스키마:
  - conversation_members: 멤버십(열람 권한의 정본). owner_account_id 는 backward-compat 유지.
  - core_messages.sender_account_id: 메시지 발신 멤버 귀속(그룹 채팅 화자 식별·LLM 맥락).
  - core_messages.thread_root_message_id: Slack형 스레드 컬럼 훅(v1 동작 미연동).

parity: scripts/agent_runtime_schema.sql (멱등 CREATE/ALTER 동일). revision 이 prod 스키마 권위.
기존 데이터 무손실: ADD COLUMN IF NOT EXISTS(nullable) + CREATE TABLE/INDEX IF NOT EXISTS.

**DEPLOY TRAP (0011/0006 동형 — load-bearing)**: 본 마이그는 superuser(bin/alembic-migrate.sh)로
적용되므로 신규 테이블 `conversation_members` 에 **명시 GRANT 를 넣지 않으면** web/ask-worker
(agent_kb_rw)가 INSERT/SELECT 시 permission denied → 멤버십이 조용히 실패한다. 아래 GRANT 필수.
core_messages 는 baseline 에서 이미 GRANT 되어 ALTER ADD COLUMN 은 추가 GRANT 불요.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_group_conversation_members"
down_revision: Union[str, None] = "0011_llm_provider_health"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1. conversation_members — 그룹 대화 멤버십(열람 권한 정본). PK=(conversation_id, account_id).
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
-- 멤버 기준 대화 목록 조회용(_list_conversations 멤버십 OR). account_id 선두.
CREATE INDEX IF NOT EXISTS ix_conv_members_account
    ON agent_runtime.conversation_members (account_id);

-- 2. core_messages 발신자 귀속 + 스레드 컬럼 훅(nullable, 기존 행 무손실).
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS sender_account_id bigint;
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS thread_root_message_id bigint;
CREATE INDEX IF NOT EXISTS ix_core_messages_thread
    ON agent_runtime.core_messages (conversation_id, thread_root_message_id);

-- 3. 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 미커버).
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.conversation_members TO agent_kb_rw;
GRANT SELECT                        ON agent_runtime.conversation_members TO agent_kb_ro;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.conversation_members;
ALTER TABLE agent_runtime.core_messages DROP COLUMN IF EXISTS thread_root_message_id;
ALTER TABLE agent_runtime.core_messages DROP COLUMN IF EXISTS sender_account_id;
DROP INDEX IF EXISTS agent_runtime.ix_core_messages_thread;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
