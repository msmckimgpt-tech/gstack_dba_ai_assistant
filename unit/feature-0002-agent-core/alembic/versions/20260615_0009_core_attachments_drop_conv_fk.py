"""core_attachments / sandbox_schemas 의 conversation FK 제거 (TASK-0279 라이브 rollout 후속).

0008 이 `core_attachments.conversation_id → core_conversations` FK(ON DELETE CASCADE)를 걸었으나,
라이브 backfill 에서 **272 첨부 중 126 행이 FK 위반**으로 적재 실패했다. 원인: MySQL 원본
`WebConversationAttachments` 는 conversation FK 가 **없어** 대화가 삭제된 orphan 첨부(05-27 cutover
시기 등, AgentCoreConversations 가 PG cutover 로 드롭되어 복구 불가)가 정상 존재했다. PG 의 strict FK 가
그 orphan 의 이전을 막아 (1) faithful 마이그레이션 불가 + (2) `attachment_backfill --verify` diff=0
게이트 영구 차단 → read cutover 불가.

해결: conversation FK 를 제거해 MySQL 의 no-FK 현실과 정합시킨다. `conversation_id` 컬럼과 인덱스
(`ix_core_attachments_conv`)는 유지 → JOIN/조회는 그대로. 신규 업로드의 대화 존재는 앱이 보장한다
(업로드는 살아있는 대화에만 가능). 서브테이블 FK(`fk_core_att_derived_att`/`fk_core_att_provider_att`,
attachment_id → core_attachments)는 id 보존으로 안정적이라 **유지**(orphan 없음, derived 1행 정상 적재).

데이터 무손실(제약만 제거, 컬럼·인덱스·데이터 불변). web=DML-only role 이라 본 마이그(superuser)가 정본
적용 경로. bootstrap `agent_runtime_schema.sql` §6d 도 FK 제거로 갱신(fresh deploy 정합).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_core_attachments_drop_conv_fk"
down_revision: Union[str, None] = "0008_core_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_attachments
    DROP CONSTRAINT IF EXISTS fk_core_attachments_conv;
ALTER TABLE agent_runtime.core_attachment_sandbox_schemas
    DROP CONSTRAINT IF EXISTS fk_core_att_sandbox_conv;
"""

# downgrade 는 orphan 행이 있으면 strict 재추가가 실패하므로 NOT VALID 로 재추가한다
# (기존 행 검증 skip, 신규만 강제). 0008 의 원래 의도(신규 무결성)는 보존하되 orphan 은 허용.
DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_attachments
    ADD CONSTRAINT fk_core_attachments_conv
    FOREIGN KEY (conversation_id) REFERENCES agent_runtime.core_conversations (conversation_id)
    ON DELETE CASCADE NOT VALID;
ALTER TABLE agent_runtime.core_attachment_sandbox_schemas
    ADD CONSTRAINT fk_core_att_sandbox_conv
    FOREIGN KEY (conversation_id) REFERENCES agent_runtime.core_conversations (conversation_id)
    ON DELETE CASCADE NOT VALID;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
