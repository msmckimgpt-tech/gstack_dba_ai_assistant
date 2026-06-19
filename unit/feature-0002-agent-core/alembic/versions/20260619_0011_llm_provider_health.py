"""agent_runtime.llm_provider_health — LLM provider 외부요인 제한 정본 (TASK-20260619T014034).

ask-worker(agent_core) 가 LLM 호출 실패/성공으로 provider별 health 를 passive upsert 하고,
web 의 active probe(hybrid)가 선제 upsert 한다. 관리자 키 갱신 전까지 sticky 한 외부 제한
(AWS Bedrock 자격증명 만료 등)을 사용자가 명시적으로 확인할 수 있게 표면화하기 위함.
PK=provider(bedrock|local|openai).

**자격증명 비영속**: state/kind/message/error_tag(예외 클래스명만)·source·since 만 저장.
api key·AWS secret·토큰은 절대 안 들어간다(datasource_health 0006 동형 원칙).

**DEPLOY TRAP (load-bearing — 0006 datasource_health 동형)**: 본 마이그는 superuser 로 적용
(bin/alembic-migrate.sh)되므로 신규 테이블에 **명시 GRANT 를 넣지 않으면** ask-worker/web
(agent_kb_rw)가 upsert 시 permission denied → health 영속이 조용히 실패한다. 아래 GRANT 필수.

revision 이 스키마 권위. 신규 테이블 CREATE + 인덱스 + GRANT 만(기존 데이터 무손실, 안전).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_llm_provider_health"
down_revision: Union[str, None] = "0010_core_conv_forked_from"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS agent_runtime.llm_provider_health (
    provider    varchar(32) PRIMARY KEY,   -- bedrock | local | openai
    state       varchar(16) NOT NULL,       -- ok | restricted | unknown
    kind        varchar(32),                -- credential_expired | auth_invalid | throttled | unavailable | not_configured | unknown
    message     varchar(512),               -- 사용자 친화 한국어 메시지
    error_tag   varchar(120),               -- 예외 클래스명/코드 축약(비밀 비포함)
    source      varchar(16),                -- ask | probe
    since       timestamptz,                -- 현재 state 시작 시각(edge)
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_llm_provider_health_state   ON agent_runtime.llm_provider_health (state);
CREATE INDEX IF NOT EXISTS ix_llm_provider_health_updated ON agent_runtime.llm_provider_health (updated_at DESC);

-- 명시 GRANT (위 DEPLOY TRAP 참조 — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함).
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.llm_provider_health TO agent_kb_rw;
GRANT SELECT                        ON agent_runtime.llm_provider_health TO agent_kb_ro;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.llm_provider_health;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
