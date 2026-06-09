"""llm_usage.resolved_model 컬럼 추가 (TASK-0163)

Revision ID: 0002_llm_usage_resolved_model
Revises: 0001_baseline
Create Date: 2026-06-09

`agent_runtime.llm_usage` 에 `resolved_model VARCHAR(128)` 를 additive 로 추가한다.
기존 `model` 컬럼은 요청 별칭(`edge`/`core`/`auto` 등)만 담고 있어, LiteLLM proxy 가
실제로 서빙한 모델(`response.model`)을 식별할 수 없었다(claude 계열 구분 불가).
`resolved_model` 은 provider 가 응답으로 반환한 실제 모델명을 best-effort 로 보관한다.

멱등(idempotent): `ADD COLUMN IF NOT EXISTS` — 부트스트랩 DDL(agent_runtime_schema.sql)
이 동일 컬럼을 이미 만들었어도 재적용 안전(공존). 백필 불필요(기존 행은 NULL 허용).

운영 절차(TASK-0149 패턴): 라이브는 `0001_baseline` 로 stamp 되어 있으므로
`bin/alembic-migrate.sh upgrade` 가 offline `--sql` 로 `0001_baseline:head` ALTER 를
생성해 postgres 로컬 소켓 superuser 로 적용한다(app role agent_kb_rw 는 DDL 권한 없음).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_llm_usage_resolved_model"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    ADD COLUMN IF NOT EXISTS resolved_model VARCHAR(128);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    DROP COLUMN IF EXISTS resolved_model;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
