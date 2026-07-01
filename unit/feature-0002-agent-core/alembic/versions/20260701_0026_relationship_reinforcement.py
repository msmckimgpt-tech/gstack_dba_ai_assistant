"""table_relationships 강화(reinforcement) 컬럼 + 'inferred' source (feature-0016 implicit-edges).

요청(2026-07-01): insight 가 파악한 데이터소스에서 FK 로 직접 확인되지 않는 **암묵 JOIN 관계**를
추론해 연결점을 만들되, 그 연결이 정말 올바른지 **항상 검증**해 틀리면 가중치가 약해져 끊어지고
(broken) 맞으면 강해져 신뢰(trusted) 관계로 재구성되게 한다.

feature-0013 이 만든 `table_relationships` 를 **비파괴 확장**한다:
  - weight            : 동적 신뢰 가중치(0~1). 정적 confidence(출처 prior)와 분리 — 관찰/프로브로 갱신.
  - positive_signals  : 누적 양성 신호(실제 JOIN 사용 성공 · 실데이터 겹침 검증).
  - negative_signals  : 누적 음성 신호(실데이터 겹침 0 등). 음성이 양성보다 빠르게 깎이도록 비대칭.
  - status            : candidate | trusted | broken. broken 은 context·그래프에서 제외(학습된 '비관계').
  - last_validated_at : 마지막 검증 시각.
  - source CHECK 에 'inferred'(휴리스틱 추론) 추가.

비파괴 추가(ADD COLUMN 기본값 + CHECK 확장) — FUNCTION.md §12 사전 승인 범위(비파괴 추가만). downgrade=DROP COLUMN.

**DEPLOY TRAP 참고(0024 동형)**: 신규 컬럼은 테이블 레벨 GRANT(agent_kb_rw INSERT/UPDATE/SELECT,
agent_kb_ro SELECT)를 자동 상속하므로 별도 GRANT 불필요. superuser 적용에도 안전.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026_relationship_reinforcement"
down_revision: Union[str, None] = "0025_age_metadata_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1) 강화 컬럼 (비파괴 ADD, 멱등) ─────────────────────────────────────────────
ALTER TABLE table_relationships
    ADD COLUMN IF NOT EXISTS weight            real        NOT NULL DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS positive_signals  integer     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS negative_signals  integer     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS status            varchar(16) NOT NULL DEFAULT 'candidate',
    ADD COLUMN IF NOT EXISTS last_validated_at timestamptz;

-- 2) 기존 행 backfill: weight ← confidence, status ← 출처/신뢰도 기반 초기 분류.
--    (신규 feature — 이 시점엔 broken 행이 없으므로 1회성 backfill 안전.)
UPDATE table_relationships
   SET weight = confidence
 WHERE weight = 0.0;
UPDATE table_relationships
   SET status = CASE
       WHEN source = 'fk_introspect' THEN 'trusted'   -- FK 는 권위적 — 즉시 신뢰
       WHEN confidence >= 0.85        THEN 'trusted'
       ELSE 'candidate' END
 WHERE status = 'candidate';

-- 3) source CHECK 확장 ('inferred' 추가) ──────────────────────────────────────
ALTER TABLE table_relationships DROP CONSTRAINT IF EXISTS ck_table_relationships_source;
ALTER TABLE table_relationships
    ADD CONSTRAINT ck_table_relationships_source
    CHECK (source IN ('fk_introspect', 'conversation', 'llm_insight', 'inferred'));

-- 4) status CHECK ─────────────────────────────────────────────────────────────
ALTER TABLE table_relationships DROP CONSTRAINT IF EXISTS ck_table_relationships_status;
ALTER TABLE table_relationships
    ADD CONSTRAINT ck_table_relationships_status
    CHECK (status IN ('candidate', 'trusted', 'broken'));

-- 5) 가중치 정렬 read + broken 프루닝 스캔용 인덱스 ──────────────────────────────
CREATE INDEX IF NOT EXISTS ix_table_relationships_status_weight
    ON table_relationships (scope_key, status, weight DESC);
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_table_relationships_status_weight;
ALTER TABLE table_relationships DROP CONSTRAINT IF EXISTS ck_table_relationships_status;
ALTER TABLE table_relationships DROP CONSTRAINT IF EXISTS ck_table_relationships_source;
-- 'inferred' 행은 이 feature 산물 — 레거시 CHECK 를 validating 으로 재추가하기 전에 제거해야
-- "check constraint … is violated by some row" 로 downgrade 가 실패하지 않는다(backend 패널 MAJOR).
DELETE FROM table_relationships WHERE source = 'inferred';
-- source CHECK 를 0024 원형(‘inferred’ 없이)으로 복원
ALTER TABLE table_relationships
    ADD CONSTRAINT ck_table_relationships_source
    CHECK (source IN ('fk_introspect', 'conversation', 'llm_insight'));
ALTER TABLE table_relationships
    DROP COLUMN IF EXISTS last_validated_at,
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS negative_signals,
    DROP COLUMN IF EXISTS positive_signals,
    DROP COLUMN IF EXISTS weight;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
