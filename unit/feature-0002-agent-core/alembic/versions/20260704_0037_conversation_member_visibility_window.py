"""공유창 [from,to] window 격리 — 멤버별 가시 범위(visibility window) 컬럼 추가

Revision ID: 0037_conversation_member_visibility_window
Revises: 0036_relationship_cross_datasource
Create Date: 2026-07-04

(주: 최초 0036 으로 작성했으나 병렬 머지된 feature-0016 의 0036_relationship_cross_datasource 와
 head 충돌 → 0037 로 re-parent. down_revision 을 그 0036 으로 잇는다. 컬럼/로직은 불변.)

feature: share-visibility-window (feature-0009 멤버십=열람경계 모델 확장; cross-cut 0002/0003).

**무엇을 추가하나 (전부 additive-nullable / DEFAULT — 무회귀):**

1. `agent_runtime.conversation_members` 에 멤버별 가시 범위 4컬럼:
   - `visible_floor_message_id   bigint`      — 하단 경계("여기부터 공유"). DISPLAY id-space
     (agent_runtime.messages.id = WebConversationShares.FloorMessageId 와 동일 공간). inclusive.
   - `visible_ceiling_message_id bigint`      — 상단 경계("여기까지 공유"). DISPLAY id-space
     (= WebConversationShares.AnchorMessageId 와 동일 공간). inclusive.
   - `visible_floor_created_at   timestamptz` — floor 경계 메세지의 created_at 스냅샷.
     **core(LLM) id-space 로의 유일한 bridge**. join 시 1회 비정규화(anchored fork 가
     src_rows[-1] created_at 으로 bridge 하는 것과 동형).
   - `visible_ceiling_created_at timestamptz` — ceiling 경계 메세지의 created_at 스냅샷.
   NULL(양 컬럼) = 그 방향 무제한 = 전체 가시(owner·기존 full 멤버). 기존 행 전부 NULL → 무회귀.

   **왜 DISPLAY id + created_at 스냅샷 둘 다인가**: 두 message store 는 독립 identity id-space
   (agent_runtime.messages ↔ agent_runtime.core_messages)이고 created_at 으로만 다리를 놓는다.
   display loader 는 messages.id 로 직접 필터하고, LLM recall loader(core_messages)는 created_at
   으로 필터하므로 양쪽 좌표를 모두 저장한다. last_read_message_id(core id-space, 가변)와 혼동 금지 —
   visibility 경계는 DISPLAY id-space + 불변 스냅샷이다.

2. `agent_runtime.core_conversations` 에 `has_restricted_members boolean NOT NULL DEFAULT false`:
   loader **게이트 플래그**. false(거의 모든 대화) → 가시성 필터 완전 우회(fast path, 무회귀, 신규
   실패면 0). true(windowed 멤버가 1명이라도 있는 대화) → loader 가 actor window 를 해석하고
   **fail-closed**(해석 실패 시 prior history [] — 절대 full 로 fallback 안 함). windowed join 이 true 로 set.

3. `ix_core_messages_conv_created ON agent_runtime.core_messages (conversation_id, created_at)`:
   LLM recall 의 created_at 범위 술어(`created_at >= floor_ca ...`)를 위한 인덱스. 기존 인덱스는
   (conversation_id, id) 뿐이라 created_at 범위 필터가 seq-scan 이 될 수 있다.

**보안 근거 (SECURITY.md §14 정합)**: 대화 내 history 는 LLM 에 native 메세지로 주입(datamark 대상
아님)이라, 가려진 구간이 참여자의 LLM 컨텍스트에 들어가는 것을 막는 유일한 방어는 recall loader 가
그 행을 **아예 로드하지 않는 것**이다. 본 마이그가 그 필터의 좌표(멤버 window)를 저장한다.

**GRANT**: conversation_members / core_conversations / core_messages 는 alembic 0012 에서 이미
agent_kb_rw 에 SELECT/INSERT/UPDATE/DELETE, agent_kb_ro 에 SELECT GRANT 됨. ADD COLUMN /
CREATE INDEX 는 추가 GRANT 불필요(0019 last_read 와 동일 idiom).

**멱등 + 배포순서 안전 (expand-only)**: 전부 `IF NOT EXISTS`. additive-nullable 이라
(a) OLD-code/NEW-schema = no-op, (b) NEW-code/OLD-schema 는 join-stamp 코드가 컬럼 부재 시
방어적 fallback(bare add_member) 하도록 구현 → 마이그 우선 랜딩 권장이나 역순도 안전. rollback 은
이미지만 되돌리고 downgrade 를 돌리지 않으므로 컬럼 잔존 무해(nullable, 미참조 시 무영향).

**PG 전용 feature**: MySQL-only 배포는 conversation_members / core_messages 가 없어 windowing 이
inert(익명 공유 뷰 snapshot 만 동작). 라이브 경로는 PG(AGENT_RUNTIME_READ_BACKEND=postgres).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0037_conversation_member_visibility_window"
down_revision: Union[str, None] = "0036_relationship_cross_datasource"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.conversation_members
    ADD COLUMN IF NOT EXISTS visible_floor_message_id bigint;
ALTER TABLE agent_runtime.conversation_members
    ADD COLUMN IF NOT EXISTS visible_ceiling_message_id bigint;
ALTER TABLE agent_runtime.conversation_members
    ADD COLUMN IF NOT EXISTS visible_floor_created_at timestamptz;
ALTER TABLE agent_runtime.conversation_members
    ADD COLUMN IF NOT EXISTS visible_ceiling_created_at timestamptz;

ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS has_restricted_members boolean NOT NULL DEFAULT false;

-- owner-answer display-tag 의 recall-측 봉인(REVIEW M1): assistant 답변이 그린 recall 하한을
-- core_messages 에 기록해, windowed recall 쿼리가 '뷰어 floor 아래 문맥을 그린 답변'을 배제한다.
-- NULL=미태깅(레거시/비제약). recall_full 은 epoch sentinel(1970-01-01)로 기록(어떤 floor 보다 이름).
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS recall_floor_created_at timestamptz;

CREATE INDEX IF NOT EXISTS ix_core_messages_conv_created
    ON agent_runtime.core_messages (conversation_id, created_at);
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS agent_runtime.ix_core_messages_conv_created;

ALTER TABLE agent_runtime.core_messages
    DROP COLUMN IF EXISTS recall_floor_created_at;

ALTER TABLE agent_runtime.core_conversations
    DROP COLUMN IF EXISTS has_restricted_members;

ALTER TABLE agent_runtime.conversation_members
    DROP COLUMN IF EXISTS visible_ceiling_created_at;
ALTER TABLE agent_runtime.conversation_members
    DROP COLUMN IF EXISTS visible_floor_created_at;
ALTER TABLE agent_runtime.conversation_members
    DROP COLUMN IF EXISTS visible_ceiling_message_id;
ALTER TABLE agent_runtime.conversation_members
    DROP COLUMN IF EXISTS visible_floor_message_id;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
