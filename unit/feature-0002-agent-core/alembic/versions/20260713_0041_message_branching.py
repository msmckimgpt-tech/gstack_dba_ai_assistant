"""message_branching — 메시지 편집(ChatGPT식 브랜치) 데이터 모델 (feature-0019-message-editing Phase 1).

현재 대화 모델은 append-only(메시지 편집 없음). 본 마이그레이션은 대화 내부 **브랜치 트리**를
도입해 사용자 메시지 편집·재답변·버전 페이징을 지원한다(FUNCTION REQ-ME-R1~R5, DESIGN §2).

핵심 안전장치 = **게이트 플래그 fast-path** (0037 `has_restricted_members` 패턴 답습):
`core_conversations.has_branches=false`(거의 모든 대화)면 recall/history 로더가 기존 linear
경로 그대로 → **byte-identical, 회귀 0**(AC-ME-2). 첫 편집(reanswer)에서만 true set.

두 message store(core_messages=LLM 문맥, messages=표시)는 독립 id-space 이므로 브랜치 포인터도
**각 store 내부 id 로 저장**한다(cross-store 시각 cut 불필요 — fork DESIGN F1 회피, ANCHOR INV-5).

컬럼(비파괴 additive):
  - core_messages / messages:
      parent_message_id    bigint       — 브랜치 트리 predecessor(같은 store id). NULL=대화 첫 메시지.
      edit_root_message_id bigint       — 편집된 user 메시지 버전 체인 root(첫 버전 id). 그룹핑/정렬.
      edit_version         int NOT NULL DEFAULT 1  — 버전 순번(1=원본).
  - core_conversations:
      has_branches            boolean NOT NULL DEFAULT false — 게이트 플래그(첫 편집에서 set).
      active_leaf_message_id  bigint                          — 활성 브랜치 leaf(core_messages.id).
                                                                NULL=linear tail(=MAX(id)).

**live 안전**: 전부 nullable 또는 constant-default(bigint NULL / int DEFAULT 1 / boolean DEFAULT
false) → PG11+ 카탈로그 전용 변경(테이블 rewrite 없음). migrate-lint expand-safe(순수 additive).
신규 컬럼은 기존 테이블 GRANT 자동 상속(0026 규약). downgrade=DROP(무손실 — 브랜치 기능 비활성).
적용 순서: 0037(agent_runtime.core_conversations) 선행 전제.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0041_message_branching"
down_revision: Union[str, None] = "0040_routine_objects_semantic_cluster"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1) core_messages (LLM 문맥 정본) 브랜치 컬럼
ALTER TABLE agent_runtime.core_messages
    ADD COLUMN IF NOT EXISTS parent_message_id    bigint,
    ADD COLUMN IF NOT EXISTS edit_root_message_id bigint,
    ADD COLUMN IF NOT EXISTS edit_version         integer NOT NULL DEFAULT 1;

-- 2) messages (표시 store) 동일 미러
ALTER TABLE agent_runtime.messages
    ADD COLUMN IF NOT EXISTS parent_message_id    bigint,
    ADD COLUMN IF NOT EXISTS edit_root_message_id bigint,
    ADD COLUMN IF NOT EXISTS edit_version         integer NOT NULL DEFAULT 1;

-- 3) core_conversations 게이트 플래그 + 활성 브랜치 leaf (0037 has_restricted_members 패턴)
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS has_branches           boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS active_leaf_message_id bigint;

-- 4) active-path recursive CTE(m.id = path.parent_message_id) 조인용 인덱스
CREATE INDEX IF NOT EXISTS ix_core_messages_parent
    ON agent_runtime.core_messages (conversation_id, parent_message_id);
CREATE INDEX IF NOT EXISTS ix_messages_parent
    ON agent_runtime.messages (conversation_id, parent_message_id);

-- 5) 버전 체인(형제 버전 집계·페이징 메타) 조회용 partial index (비편집=NULL 제외 → 슬림)
CREATE INDEX IF NOT EXISTS ix_core_messages_edit_root
    ON agent_runtime.core_messages (edit_root_message_id)
    WHERE edit_root_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_messages_edit_root
    ON agent_runtime.messages (edit_root_message_id)
    WHERE edit_root_message_id IS NOT NULL;
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS agent_runtime.ix_messages_edit_root;
DROP INDEX IF EXISTS agent_runtime.ix_core_messages_edit_root;
DROP INDEX IF EXISTS agent_runtime.ix_messages_parent;
DROP INDEX IF EXISTS agent_runtime.ix_core_messages_parent;

ALTER TABLE agent_runtime.core_conversations
    DROP COLUMN IF EXISTS active_leaf_message_id,
    DROP COLUMN IF EXISTS has_branches;

ALTER TABLE agent_runtime.messages
    DROP COLUMN IF EXISTS edit_version,
    DROP COLUMN IF EXISTS edit_root_message_id,
    DROP COLUMN IF EXISTS parent_message_id;

ALTER TABLE agent_runtime.core_messages
    DROP COLUMN IF EXISTS edit_version,
    DROP COLUMN IF EXISTS edit_root_message_id,
    DROP COLUMN IF EXISTS parent_message_id;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
