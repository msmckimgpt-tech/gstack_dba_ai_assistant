"""conversation_folders — 대화 폴더(프로젝트 워크스페이스) 데이터 모델 (feature-0024-conversation-folders).

좌측 대화 목록에 폴더(프로젝트) 구조를 도입한다(FUNCTION REQ-20260723-folder-*). 두 신규 테이블:

  1) conversation_folders  — 계정 소유 재귀 폴더(self-FK parent_folder_id). 폴더 지침(instructions)·
     기본 데이터소스/제품 스코프 핀·soft-delete(archived_at, Trash+undo). 대화 정본과 별개라
     폴더를 지워도 대화는 core_conversations 에 그대로 보존된다(REQ-folder-delete-keep).
  2) folder_conversation_map — **계정별** 대화↔폴더 배정(PK=(account_id, conversation_id)). 한 대화가
     여러 멤버에게 보일 때 각자 자기 폴더 트리에 독립 배치(사용자 결정 D2, REQ-folder-organize).

**재귀 깊이**: parent_folder_id self-FK 로 무제한 중첩 가능하되, 최대 깊이는 런타임 설정
(WebRuntimeSettings folder_max_depth, 기본 4)으로 app-level 강제 + 순환 방지(사용자 결정 D1).

**DEPLOY TRAP (0012/0006 동형 — load-bearing)**: 본 마이그는 superuser(bin/alembic-migrate.sh)로
적용되므로 신규 테이블에 **명시 GRANT 를 넣지 않으면** web/ask-worker(agent_kb_rw)가 INSERT/SELECT
시 permission denied → 폴더가 조용히 실패한다. 아래 GRANT 필수. conversation_folders 는 IDENTITY
PK 라 암묵 시퀀스가 생기므로 ALL SEQUENCES GRANT 도 재실행(신규 시퀀스 커버).

**live 안전**: 전부 CREATE TABLE/INDEX IF NOT EXISTS(신규 테이블) → 기존 테이블 rewrite 0,
core_conversations 미변경(배정은 map 테이블에 격리 — 컬럼 추가조차 없음). migrate-lint expand-safe
(순수 additive). downgrade=DROP(무손실 — 폴더 기능 비활성, 대화·메시지 무영향).
parity: scripts/agent_runtime_schema.sql 에 동일 DDL(멱등) — revision 이 prod 스키마 권위.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0044_conversation_folders"
down_revision: Union[str, None] = "0043_redteam_rederive_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1) conversation_folders — 계정 소유 재귀 폴더. parent_folder_id self-FK(NULL=root).
CREATE TABLE IF NOT EXISTS agent_runtime.conversation_folders (
    folder_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_account_id  bigint       NOT NULL,
    parent_folder_id  bigint,
    name              varchar(120) NOT NULL,
    instructions      text,
    datasource_id     bigint,
    product_id        bigint,
    sort_order        integer      NOT NULL DEFAULT 0,
    archived_at       timestamptz,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT fk_conv_folders_parent
        FOREIGN KEY (parent_folder_id)
        REFERENCES agent_runtime.conversation_folders (folder_id)
        ON DELETE SET NULL
);
-- 소유자별 트리 조회(재귀 CTE parent 체인) + 활성 필터.
CREATE INDEX IF NOT EXISTS ix_conv_folders_owner
    ON agent_runtime.conversation_folders (owner_account_id, parent_folder_id);

-- 2) folder_conversation_map — 계정별 대화↔폴더 배정. PK=(account_id, conversation_id).
--    폴더 삭제(하드) 시 배정만 CASCADE 제거(대화는 core_conversations 에 보존).
CREATE TABLE IF NOT EXISTS agent_runtime.folder_conversation_map (
    account_id       bigint       NOT NULL,
    conversation_id  varchar(128) NOT NULL,
    folder_id        bigint       NOT NULL,
    assigned_at      timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, conversation_id),
    CONSTRAINT fk_folder_map_folder
        FOREIGN KEY (folder_id)
        REFERENCES agent_runtime.conversation_folders (folder_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_folder_map_conv
        FOREIGN KEY (conversation_id)
        REFERENCES agent_runtime.core_conversations (conversation_id)
        ON DELETE CASCADE
);
-- 폴더 내 대화 조회(폴더 렌더) + 계정 뷰 조회.
CREATE INDEX IF NOT EXISTS ix_folder_map_folder
    ON agent_runtime.folder_conversation_map (folder_id);
CREATE INDEX IF NOT EXISTS ix_folder_map_account
    ON agent_runtime.folder_conversation_map (account_id, folder_id);

-- 3) 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 미커버).
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.conversation_folders      TO agent_kb_rw;
GRANT SELECT                        ON agent_runtime.conversation_folders      TO agent_kb_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.folder_conversation_map   TO agent_kb_rw;
GRANT SELECT                        ON agent_runtime.folder_conversation_map   TO agent_kb_ro;
-- IDENTITY 암묵 시퀀스(conversation_folders.folder_id) 포함 — 신규 시퀀스 USAGE 재보장.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA agent_runtime TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.folder_conversation_map;
DROP TABLE IF EXISTS agent_runtime.conversation_folders;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
