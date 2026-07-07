"""enum_dictionary source 차원 + 대화 자율수집 큐(enum_feedback) — 용어사전(0023) ENUM 대칭.

요청(2026-07-07): 「관리 콘솔 > 지식베이스 > 메타데이터」의 용어사전과 ENUM 코드사전 모두가 assistant
대화로부터 후보를 수집하고, 사용자가 각 후보를 채택(승급)할 수 있게 한다. 용어사전은 0023
(glossary_feedback + 하이브리드 자동승급)로 이미 구현돼 있고, 본 마이그는 그 대칭을 ENUM 코드사전에
부여한다 (사용자 결정 2026-07-07: 범위=전체 한 사이클).

스키마 변경(기존 데이터 무손실·멱등, 0023 동형):
  1. enum_dictionary 에 source(manual|auto) 컬럼 ADD. 기존 행은 'manual' 로 backfill(DEFAULT) →
     동작 불변. kb_glossary.source(0023)와 동일 의미 — 자동수집분 되돌리기(reject auto_promoted →
     source='auto' 행 회수)를 안전하게 구분하기 위함. (auto_promoted 는 enum_feedback.status 값이지
     source 값이 아니다 — source 컬럼에는 manual/auto 만 기록.)
  2. enum_feedback — 대화에서 추론된 코드↔라벨 후보의 검토/자동승급 큐(glossary_feedback 동형).
     status: pending(검토 대기) / auto_promoted(고신뢰도 자동승급·감사 추적) / promoted(관리자 승인) /
     rejected(거부 — 재제안 차단, poisoning 방어). key = (scope,schema,table,column,code)
     (enum_dictionary UNIQUE 와 동일 컨벤션).

**DEPLOY TRAP (load-bearing — 0013/0023 동형)**: superuser 로 적용되므로 신규 테이블에 명시 GRANT 를
넣지 않으면 ask-worker/web(agent_kb_rw)가 upsert 시 permission denied. 아래 GRANT 필수.
agent_kb_schema.sql §8/§10 과 정합.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0039_enum_feedback"
down_revision: Union[str, None] = "0038_node_analysis_refine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- ── 1. enum_dictionary: source 차원 추가 (kb_glossary.source 0023 동형) ──────────────
ALTER TABLE enum_dictionary ADD COLUMN IF NOT EXISTS source varchar(24) NOT NULL DEFAULT 'manual';

-- ── 2. enum_feedback: 대화 자율수집 검토/자동승급 큐 (glossary_feedback 0023 동형) ──────
--   key = (scope, schema, table, column, code) — enum_dictionary UNIQUE 와 동일 컨벤션(같은 코드에
--   후보 라벨은 하나만 계류). suggested_label 은 후보 라벨(text). promoted_enum_id = 승급 대상
--   enum_dictionary.id (감사 추적).
CREATE TABLE IF NOT EXISTS enum_feedback (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key          varchar(96)  NOT NULL DEFAULT 'common',
    schema_name        varchar(128) NOT NULL DEFAULT '',
    table_name         varchar(128) NOT NULL,
    column_name        varchar(128) NOT NULL,
    code               varchar(128) NOT NULL,
    suggested_label    text         NOT NULL,
    confidence         real         NOT NULL DEFAULT 0.5,
    status             varchar(16)  NOT NULL DEFAULT 'pending',
    source_run_id      varchar(64),
    conversation_id    varchar(128),
    promoted_enum_id   bigint,
    approved_by        varchar(64),
    created_at         timestamptz  NOT NULL DEFAULT now(),
    updated_at         timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_enum_feedback_status
        CHECK (status IN ('pending', 'auto_promoted', 'promoted', 'rejected')),
    CONSTRAINT ux_enum_feedback_scope_col_code
        UNIQUE (scope_key, schema_name, table_name, column_name, code)
);
CREATE INDEX IF NOT EXISTS ix_enum_feedback_status
    ON enum_feedback (status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_enum_feedback_scope
    ON enum_feedback (scope_key, table_name, column_name);
DROP TRIGGER IF EXISTS trg_enum_feedback_updated_at ON enum_feedback;
CREATE TRIGGER trg_enum_feedback_updated_at
    BEFORE UPDATE ON enum_feedback
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON enum_feedback TO agent_kb_rw;
GRANT SELECT                         ON enum_feedback TO agent_kb_ro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS enum_feedback;
ALTER TABLE enum_dictionary DROP COLUMN IF EXISTS source;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
