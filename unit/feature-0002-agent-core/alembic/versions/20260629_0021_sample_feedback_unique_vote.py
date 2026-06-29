"""public.sample_feedback — 답변당 사용자별 고유 피드백(👍/👎) 강제.

버그: 답변 피드백(👍/👎)이 무조건 INSERT 되어, 새로고침·대화 전환 후 같은 사용자가 같은
답변에 중복 부여 가능. (frontend 의 in-session DOM 플래그만으로 차단 → 새로고침 시 소실.)

수정: 답변(message_id) 식별자 컬럼 추가 + (created_by, message_id) **부분 UNIQUE 인덱스**로
"한 사용자 = 한 답변당 1표"를 DB 계층에서 강제. record_feedback 은 ON CONFLICT 로 UPSERT
(last-write-wins, 변경 허용)한다.

부분 인덱스 술어 `WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested = false`:
  - 과거 행(message_id NULL — 본 마이그 이전 적재)은 인덱스 대상 외 → 충돌 없음(무손실·멱등).
  - 익명(created_by NULL)도 대상 외.
  - "샘플 등록"(suggested = true)은 검수 큐 제출이라 별 행 유지(투표 고유성과 분리) → 대상 외.

신규 컬럼 ADD + 부분 UNIQUE 인덱스 CREATE 만(기존 데이터 무손실, IF NOT EXISTS 멱등).
updated_at 트리거(trg_sample_feedback_updated_at)는 0014 에 이미 존재 — DO UPDATE 시 자동 발화.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021_sample_feedback_unique_vote"
down_revision: Union[str, None] = "0020_conversation_member_last_read_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE sample_feedback ADD COLUMN IF NOT EXISTS message_id bigint;

CREATE UNIQUE INDEX IF NOT EXISTS ux_sample_feedback_user_msg_vote
    ON sample_feedback (created_by, message_id)
    WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested = false;
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ux_sample_feedback_user_msg_vote;
ALTER TABLE sample_feedback DROP COLUMN IF EXISTS message_id;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
