"""public.sample_feedback — 답변당 고유 피드백 키에 message_id_space 추가 (H5(b) 해소).

마이그 0021 은 (created_by, message_id) 로 답변당 고유 투표를 강제했으나, message_id 는 표시
store(`agent_runtime.messages.id`)와 core fallback(`core_messages.id`)의 **두 독립 IDENTITY
공간**서 올 수 있어(숫자 겹침 가능 — agent_core 가 "독립 시퀀스" 로 명시) fork·마이그로 대화가
core-only→display 로 전환되는 경우 cross-space 충돌(서로 다른 답변이 같은 키)·wrong-bubble 복원이
가능했다(적대 리뷰 H5(b)).

수정: `message_id_space varchar(16)`(값 'display'|'core') 를 추가하고 고유 인덱스를
(created_by, message_id, message_id_space) 로 확장. 두 공간의 같은 숫자 id 는 이제 다른 키로
구분된다. record_feedback / /api/history(id_space 노출·복원) 가 함께 갱신된다.

기존 행: message_id_space 신규 컬럼은 `DEFAULT 'display'`(라이브 적재분은 전부 표시 store 경로) →
무손실. 인덱스 교체는 DROP→CREATE(IF EXISTS/IF NOT EXISTS 멱등). agent_kb_schema.sql 부트스트랩
정본에도 동일 미러(배포 boot 적용).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022_sample_feedback_id_space"
down_revision: Union[str, None] = "0021_sample_feedback_unique_vote"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 3-col 인덱스는 **새 이름**(ux_sample_feedback_user_msg_space_vote)을 쓴다 — 구 2-col 인덱스
# (ux_sample_feedback_user_msg_vote, 0021)와 이름이 같으면 부트스트랩의 `CREATE ... IF NOT EXISTS`
# 가 정의 변경을 감지 못해(same-name no-op) 2-col 로 잔존하는 trap 을 피한다.
UPGRADE_SQL = r"""
ALTER TABLE sample_feedback ADD COLUMN IF NOT EXISTS message_id_space varchar(16) NOT NULL DEFAULT 'display';

DROP INDEX IF EXISTS ux_sample_feedback_user_msg_vote;
CREATE UNIQUE INDEX IF NOT EXISTS ux_sample_feedback_user_msg_space_vote
    ON sample_feedback (created_by, message_id, message_id_space)
    WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested = false;
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ux_sample_feedback_user_msg_space_vote;
ALTER TABLE sample_feedback DROP COLUMN IF EXISTS message_id_space;
CREATE UNIQUE INDEX IF NOT EXISTS ux_sample_feedback_user_msg_vote
    ON sample_feedback (created_by, message_id)
    WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested = false;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
