"""kb_glossary role 차원 + 대화 자율등록 큐(glossary_feedback) + 유사어 참조(glossary_relations).

요청(2026-06-29): 「관리 콘솔 > 메타데이터 > 용어사전」이 사용자 대화로부터 assistant 판단 하에
자율적으로 등록되도록 구성. 단 ① 역할(role)별 사용 용어가 겹치지 않는 구조, ② 유사한 의미가
있으면 참조 가능한 구조. 사용자 결정(AskUserQuestion 2026-06-29):
  - 등록 자율성 = **하이브리드 자동승급**(고신뢰도 자동 등록[source='auto'·되돌리기 가능],
    저신뢰도는 검토 큐[glossary_feedback.status='pending']).
  - 역할 기본 귀속 = **공용(common, role_key='*')** — 역할 특수할 때만 특정 role_key.

스키마 변경(기존 데이터 무손실·멱등):
  1. kb_glossary 에 role_key(역할 차원, 기본 '*'=공용)·source(manual|auto|auto_promoted) 컬럼 ADD.
     UNIQUE(scope_key, term) → UNIQUE(scope_key, role_key, term) 로 재정의 → 같은 용어를 역할별로
     독립 보유(겹침 방지). 기존 행은 role_key='*' 로 backfill(DEFAULT) → 동작 불변.
  2. glossary_feedback — 대화에서 추론된 용어 후보의 검토/자동승급 큐(sample_feedback 동형).
     status: pending(검토 대기) / auto_promoted(고신뢰도 자동승급·감사 추적) / promoted(관리자 승인) /
     rejected(거부 — 재제안 차단, poisoning 방어).
  3. glossary_relations — 용어 간 유사어/동의어/참조 링크(역할 경계 횡단 허용). from_id↔to_id(kb_glossary).

**DEPLOY TRAP (load-bearing — 0013/0011 동형)**: superuser 로 적용되므로 신규 테이블에 명시 GRANT 를
넣지 않으면 ask-worker/web(agent_kb_rw)가 upsert 시 permission denied. 아래 GRANT 필수.
agent_kb_schema.sql §8/§10 과 정합.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
# 0021/0022 는 sample_feedback(unique_vote·id_space) 가 선점 — 본 마이그는 그 뒤 0023 으로 체인
# (rebase 시 마이그 번호 충돌 해소: 0020 → 0021_unique_vote → 0022_id_space → 0023_glossary).
revision: str = "0023_glossary_role_autoreg"
down_revision: Union[str, None] = "0022_sample_feedback_id_space"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- ── 1. kb_glossary: role 차원 + source 추가, UNIQUE 키 재정의 ────────────────────
ALTER TABLE kb_glossary ADD COLUMN IF NOT EXISTS role_key varchar(64) NOT NULL DEFAULT '*';
ALTER TABLE kb_glossary ADD COLUMN IF NOT EXISTS source   varchar(24) NOT NULL DEFAULT 'manual';
-- 기존 (scope_key, term) UNIQUE 를 (scope_key, role_key, term) 로 교체 → 역할별 비중복 namespace.
-- 신규 제약도 ADD 전에 DROP IF EXISTS(트리거 패턴) → 재실행 멱등(PG 는 ADD CONSTRAINT IF NOT EXISTS 미지원).
ALTER TABLE kb_glossary DROP CONSTRAINT IF EXISTS ux_kb_glossary_scope_term;
ALTER TABLE kb_glossary DROP CONSTRAINT IF EXISTS ux_kb_glossary_scope_role_term;
ALTER TABLE kb_glossary ADD  CONSTRAINT ux_kb_glossary_scope_role_term
    UNIQUE (scope_key, role_key, term);
CREATE INDEX IF NOT EXISTS ix_kb_glossary_scope_role ON kb_glossary (scope_key, role_key);

-- ── 2. glossary_feedback: 대화 자율등록 검토/자동승급 큐 (sample_feedback 동형) ──────
CREATE TABLE IF NOT EXISTS glossary_feedback (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key            varchar(96)  NOT NULL DEFAULT 'common',
    role_key             varchar(64)  NOT NULL DEFAULT '*',
    term                 varchar(128) NOT NULL,
    suggested_definition text         NOT NULL,
    confidence           real         NOT NULL DEFAULT 0.5,
    status               varchar(16)  NOT NULL DEFAULT 'pending',
    source_run_id        varchar(64),
    conversation_id      varchar(128),
    promoted_glossary_id bigint,
    approved_by          varchar(64),
    created_at           timestamptz  NOT NULL DEFAULT now(),
    updated_at           timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_glossary_feedback_status
        CHECK (status IN ('pending', 'auto_promoted', 'promoted', 'rejected')),
    CONSTRAINT ux_glossary_feedback_scope_role_term
        UNIQUE (scope_key, role_key, term)
);
CREATE INDEX IF NOT EXISTS ix_glossary_feedback_status
    ON glossary_feedback (status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_glossary_feedback_scope
    ON glossary_feedback (scope_key, role_key);
DROP TRIGGER IF EXISTS trg_glossary_feedback_updated_at ON glossary_feedback;
CREATE TRIGGER trg_glossary_feedback_updated_at
    BEFORE UPDATE ON glossary_feedback
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── 3. glossary_relations: 유사어/동의어/참조 링크 (역할 경계 횡단 허용) ─────────────
CREATE TABLE IF NOT EXISTS glossary_relations (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    from_id       bigint      NOT NULL REFERENCES kb_glossary(id) ON DELETE CASCADE,
    to_id         bigint      NOT NULL REFERENCES kb_glossary(id) ON DELETE CASCADE,
    relation_type varchar(16) NOT NULL DEFAULT 'similar',
    created_by    varchar(64),
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_glossary_relations_type
        CHECK (relation_type IN ('synonym', 'similar', 'see_also')),
    CONSTRAINT ck_glossary_relations_distinct CHECK (from_id <> to_id),
    CONSTRAINT ux_glossary_relations UNIQUE (from_id, to_id, relation_type)
);
CREATE INDEX IF NOT EXISTS ix_glossary_relations_from ON glossary_relations (from_id);
CREATE INDEX IF NOT EXISTS ix_glossary_relations_to   ON glossary_relations (to_id);

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON glossary_feedback, glossary_relations TO agent_kb_rw;
GRANT SELECT                         ON glossary_feedback, glossary_relations TO agent_kb_ro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS glossary_relations;
DROP TABLE IF EXISTS glossary_feedback;
DROP INDEX IF EXISTS ix_kb_glossary_scope_role;
ALTER TABLE kb_glossary DROP CONSTRAINT IF EXISTS ux_kb_glossary_scope_role_term;
ALTER TABLE kb_glossary DROP COLUMN IF EXISTS source;
ALTER TABLE kb_glossary DROP COLUMN IF EXISTS role_key;
-- best-effort: 역할별 중복 term 이 생겼다면 재추가가 실패할 수 있음(다운그레이드 한정 허용).
ALTER TABLE kb_glossary ADD CONSTRAINT ux_kb_glossary_scope_term UNIQUE (scope_key, term);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
