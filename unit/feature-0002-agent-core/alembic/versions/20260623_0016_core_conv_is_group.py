"""core_conversations.is_group — 그룹 대화 영구 플래그 (feature-0009 gc-group-authz-flag).

그룹 대화 여부를 멤버 수(conversation_members COUNT)로만 파생하던 것을, **영구 플래그**로
승격한다. is_group=true 면 해당 대화는 "그룹 대화"로 확정되어 (1) send-routing 이 @assistant
멘션 없는 메시지를 사람-사람 채팅(store-only)으로 라우팅하고, (2) 사이드바에 그룹 배지를 표시한다.

플래그가 켜지는 시점:
  - 공유 링크(joinable) 생성 시 — "공유 = 협업 의도" 를 즉시 그룹으로 확정 (사용자 요청).
  - 누군가 공유 링크로 join 할 때.
파생 신호(member_count>1)와 함께 OR 로 그룹 판정에 쓰여, 기존 멤버 2+ 대화도 데이터 backfill
없이 정상 동작한다(컬럼 기본 false 만으로 충분).

데이터 무손실: 컬럼 ADD 만(기존 대화 is_group=false=비그룹). web 컨테이너는 DML-only role 이라
런타임 ALTER 불가 → 본 마이그레이션(superuser offline SQL)이 정본 적용 경로. 부트스트랩
DDL(agent_runtime_schema.sql)·app.py MySQL 폴백에도 동일 컬럼 멱등 ALTER 를 반영(0007 동형).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_core_conv_is_group"
down_revision: Union[str, None] = "0015_sample_queries_embed_dim_1024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS is_group boolean NOT NULL DEFAULT false;
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_conversations DROP COLUMN IF EXISTS is_group;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
