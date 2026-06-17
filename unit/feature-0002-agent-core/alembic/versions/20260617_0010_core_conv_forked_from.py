"""core_conversations.forked_from_conversation_id — fork 본 식별 마커 (TASK-20260617T082131).

account insight recall(계정 cross-conversation 회상)의 보안 가드 G1. fork 는 소스 대화(타 계정
가능)의 메시지를 복사하고 owner 를 포크계정으로 재귀속하므로(app.py `_fork_conversation_impl`),
owner_account_id 격리만으론 콘텐츠 출처가 격리되지 않는다(cross-account 누출 경로). 본 컬럼이
fork 본을 명시 표식해, account insight 추출·회상이 `forked_from_conversation_id IS NULL` 만
대상으로 삼아 fork-파생 인사이트가 회상에 섞이지 않게 한다.

데이터 무손실: 컬럼 ADD 만(기존 대화 = NULL = 비-fork 로 간주). web 컨테이너는 DML-only role
이라 런타임 ALTER 불가 → 본 마이그레이션(superuser offline SQL)이 정본 적용 경로. 부트스트랩
DDL(agent_runtime_schema.sql)·app.py fork set 에도 동일 반영(0007/0009 동형).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_core_conv_forked_from"
down_revision: Union[str, None] = "0009_drop_attach_conv_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS forked_from_conversation_id varchar(128);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_conversations DROP COLUMN IF EXISTS forked_from_conversation_id;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
