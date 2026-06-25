"""agent_runtime: 그룹 대화 멤버 차단(ban) 목록 (feature-0009 member-kick-ban).

소유자(owner)가 특정 참여자를 추방(kick=멤버 제거, 재참여 가능)하거나 차단(ban=제거 +
이 테이블 등재)할 수 있게 한다. 차단된 account 는 `POST /api/share/{token}/join` 의
is_banned 체크로 공유 링크 재참여가 거부된다. 해제(unban)=이 테이블에서 행 제거.

parity: scripts/agent_runtime_schema.sql (멱등 CREATE 동일). revision 이 prod 스키마 권위.
기존 데이터 무손실: CREATE TABLE IF NOT EXISTS (신규 테이블).

**DEPLOY TRAP (0012 동형 — load-bearing)**: 본 마이그는 superuser(bin/alembic-migrate.sh)로
적용되므로 신규 테이블 `conversation_member_bans` 에 **명시 GRANT 를 넣지 않으면**
web/ask-worker(agent_kb_rw)가 INSERT/SELECT/DELETE 시 permission denied → ban/unban/조회가
조용히 실패한다. 아래 GRANT 필수.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_conversation_member_bans"
down_revision: Union[str, None] = "0017_table_column_descriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- conversation_member_bans — owner 가 특정 account 를 이 대화에서 재참여 차단(ban).
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

-- 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 미커버).
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.conversation_member_bans TO agent_kb_rw;
GRANT SELECT                        ON agent_runtime.conversation_member_bans TO agent_kb_ro;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.conversation_member_bans;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
