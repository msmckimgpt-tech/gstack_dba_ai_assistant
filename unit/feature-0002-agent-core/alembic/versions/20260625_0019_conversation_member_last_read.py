"""conversation_members.last_read_message_id — 그룹 대화 안 읽은 메세지 커서 (feature-0009 gc-unread-badge).

그룹 대화 사이드바에 "안 읽은(새) 메세지" 카운트 배지(`<안읽음>[ / @<안읽은 멘션>]`)를 표시하기
위한 멤버별 읽음 커서. conversation_members 의 (conversation_id, account_id) 행마다 그 멤버가
마지막으로 읽은 core_messages.id 를 기록한다(NULL=한 번도 안 읽음=전부 새 메세지).

unread = 그 대화의 core_messages 중 id > last_read_message_id 이고 본인(sender_account_id)이
보내지 않은 user/assistant 메세지 수. unread mention = 그 중 @<본인username> 멘션 포함 수.
읽음 처리(POST /api/conversations/{cid}/read)는 커서를 GREATEST 로 전진만 한다.

데이터 무손실: 컬럼 ADD 만(nullable, 기존 멤버 last_read=NULL=전부 unread→읽으면 0).
conversation_members 는 0012 에서 이미 agent_kb_rw 에 UPDATE GRANT 보유 → 컬럼 추가에 추가
GRANT 불요(0012 의 'ALTER ADD COLUMN 은 추가 GRANT 불요'와 동형). 부트스트랩
DDL(agent_runtime_schema.sql)·app.py MySQL 폴백에도 동일 컬럼 멱등 ALTER 를 parity 반영.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_conversation_member_last_read"
down_revision: Union[str, None] = "0018_conversation_member_bans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.conversation_members
    ADD COLUMN IF NOT EXISTS last_read_message_id bigint;
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.conversation_members DROP COLUMN IF EXISTS last_read_message_id;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
