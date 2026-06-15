"""agent_runtime.datasource_health — datasource 연결 health 정본 (TASK-0255 R2).

insight-worker 가 매 cycle datasource 별 연결 상태(conn_health 권위 status + 이번 cycle scan_outcome)를
upsert 한다. 관리콘솔이 "연결 불안정으로 미커버"(status=unstable / scan_outcome=circuit_open)를 "권한 실패"
(scan_outcome=perm_failed)와 **구분해** 표면화하기 위함. PK=scope_key(엔드포인트 해시, 라벨 rename 불변).

**자격증명 비영속**: host/port/engine/status/fails/errno-tag 만 저장. user/password 는 절대 안 들어간다
(conn_health.snapshot()·datasources scope_key 불변식 동형).

**DEPLOY TRAP (load-bearing)**: baseline 0001 migration 은 GRANT 를 포함하지 않는다(grant 는 .sql 부트스트랩
전용이고 ALTER DEFAULT PRIVILEGES 는 `public` 스키마에만 설정됨 — agent_kb_schema.sql:282-293). 본 마이그는
postgres **superuser** 로 적용(bin/alembic-migrate.sh)되므로, 신규 테이블에 **명시 GRANT 를 넣지 않으면**
insight-worker(agent_kb_rw)가 INSERT 시 permission denied → R2 영속이 조용히 실패한다. 아래 GRANT 필수.

revision 이 스키마 권위. 본 마이그는 신규 테이블 CREATE + 인덱스 + GRANT 만(기존 데이터 무손실, 안전).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_datasource_health"
down_revision: Union[str, None] = "0005_core_conv_blocked"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS agent_runtime.datasource_health (
    scope_key          varchar(64) PRIMARY KEY,   -- 엔드포인트 해시(engine-sha256[:12]). 라벨 rename 불변
    datasource_label   varchar(255),              -- 표시용 라벨(가변)
    engine             varchar(16)  NOT NULL,      -- mysql | mssql
    host               varchar(255),              -- 엔드포인트 host (WebDatasources 관례 — 비밀 아님)
    port               integer,
    status             varchar(16)  NOT NULL,      -- conn_health 권위: healthy | unstable | unknown
    last_scan_outcome  varchar(24),               -- ok | circuit_open | perm_failed | other_failed | skipped_no_db
    fail_count         integer      NOT NULL DEFAULT 0,
    last_error_tag     varchar(80),               -- errno/메시지 80자 축약(자격증명 비포함)
    last_checked_at    timestamptz,               -- conn_health 마지막 probe 시각
    last_scan_at       timestamptz,               -- 이 insight cycle 시각
    last_transition_at timestamptz,               -- status 변경 시각(edge)
    run_id             varchar(64),
    updated_at         timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_datasource_health_status  ON agent_runtime.datasource_health (status);
CREATE INDEX IF NOT EXISTS ix_datasource_health_updated ON agent_runtime.datasource_health (updated_at DESC);

-- 명시 GRANT (위 DEPLOY TRAP 참조 — superuser 적용이라 ALL TABLES 스냅샷·DEFAULT PRIVILEGES 가 커버 못 함).
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.datasource_health TO agent_kb_rw;
GRANT SELECT                        ON agent_runtime.datasource_health TO agent_kb_ro;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.datasource_health;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
