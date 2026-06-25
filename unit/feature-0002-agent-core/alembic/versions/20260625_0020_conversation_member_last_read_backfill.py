"""conversation_members.last_read_message_id baseline backfill (feature-0009 gc-unread-baseline).

0019 가 컬럼을 ADD 만 하고 기존 멤버 커서를 NULL 로 남겨, 사이드바 unread 배지가
`COALESCE(last_read,0)` → `id > 0` 으로 **기존 메세지 전체를 안 읽음으로 집계**하는
문제(읽은 대화에도 "전체 개수" 회색 배지)를 보정한다. 사용자 의도는 "읽지 않은 *신규*
메세지만" 이므로, 배포 시점 이전 메세지는 "이미 본 것"으로 간주한다.

backfill: last_read_message_id 가 NULL 인 멤버 행을 그 대화의 현재 MAX(core_messages.id)
로 초기화한다. → 이후 도착하는 신규 메세지만 unread. 메세지가 하나도 없는 대화는 매칭되는
sub 행이 없어 NULL 유지(unread 0). 멱등: IS NULL 조건이라 재실행 시 이미 보정된 행을
건너뛴다(읽음 처리로 전진한 커서를 되돌리지 않음).

신규 가입 멤버의 baseline 은 group_members.add_member 의 INSERT 에서 가입 시점
MAX(id) 로 set 하므로(코드 변경 동반), 본 마이그레이션은 *기존* 데이터 일회성 보정이다.

데이터 무손실: UPDATE 만(컬럼 변경 0). downgrade 는 no-op — 어느 행이 원래 NULL 이었는지
복원 불가하므로 되돌리지 않는다.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_conversation_member_last_read_backfill"
down_revision: Union[str, None] = "0019_conversation_member_last_read"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
UPDATE agent_runtime.conversation_members AS cm
SET last_read_message_id = sub.max_id
FROM (
    SELECT conversation_id, MAX(id) AS max_id
    FROM agent_runtime.core_messages
    GROUP BY conversation_id
) AS sub
WHERE cm.conversation_id = sub.conversation_id
  AND cm.last_read_message_id IS NULL;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    # backfill 은 데이터 보정 — 원래 NULL 이었던 행을 식별/복원할 수 없어 되돌리지 않는다.
    pass
