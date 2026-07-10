"""llm_usage.target 컬럼 추가 (AI 운영 현황 — 최근 활동 '어떤 대상' 관측)

Revision ID: 0032_llm_usage_target
Revises: 0031_node_analysis_role
Create Date: 2026-07-03

`agent_runtime.llm_usage` 에 `target VARCHAR(200)` (nullable) 를 additive 로 추가한다.
인사이트 분석(스키마/테이블/노드 분석)이 **어떤 대상**(schema / schema.table / 노드 FQN)에
대해 동작했는지를 best-effort 로 기록해, AI 운영 현황 '최근 활동' 피드에서 라벨('테이블 분석'
'그래프 노드 분석') 옆에 대상을 표시한다.

**왜 task 컬럼에 넣지 않는가**: `llm_usage.task` 는 저카디널리티 카테고리 키
(`table_insight`/`node_analysis` …)로 KPI 드릴다운·커버리지가 `GROUP BY task` / TASK_TAXONOMY
정확 매칭에 의존한다(shared/model_catalog.py). 대상을 task 에 접합하면 카디널리티가 폭증해
집계·taxonomy 매칭이 깨진다. 따라서 대상은 **별도 컬럼**으로 분리(집계 무영향, 표시 전용).

**nullable + DEFAULT 없음**: 대상 없는 활동(agent 추론·요약·분류 등)은 NULL 로 남는다. 대상이
의미 있는 인사이트 분석(schema/table/node)만 채운다. account_insight 는 대상이 대화/계정
PII 라 기록하지 않는다(운영 피드 PII 유입 방지).

멱등(idempotent): `ADD COLUMN IF NOT EXISTS` — 부트스트랩 DDL(agent_runtime_schema.sql)
이 동일 컬럼을 이미 만들었어도 재적용 안전(공존, parity 반영됨).

운영 절차(TASK-0149·0030 패턴): 라이브는 이전 head 로 stamp 되어 있으므로
`bin/alembic-migrate.sh upgrade` 가 offline `--sql` 로 ALTER 를 생성해 postgres 로컬 소켓
superuser 로 적용한다(app role agent_kb_rw 는 DDL 권한 없음).

배포 순서 안전: 마이그(컬럼 additive nullable)와 코드가 역순/부분 배포돼도 (a) OLD INSERT 는
신컬럼 무관하게 성공하고, (b) NEW 코드가 컬럼 부재 상태에서 INSERT 해도 _record_llm_usage 가
target 포함 INSERT 실패 시 **target 제외 INSERT 로 폴백**(자가치유)해 usage 행 자체는 보존된다
(stale agent image 로 마이그레이션이 누락돼도 계측이 조용히 끊기지 않음). rollback 은 이미지만
되돌리고 alembic downgrade 를 실행하지 않으므로 컬럼 잔존은 무해(nullable, 미참조 시 무영향).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032_llm_usage_target"
down_revision: Union[str, None] = "0031_node_analysis_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    ADD COLUMN IF NOT EXISTS target VARCHAR(200);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    DROP COLUMN IF EXISTS target;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
