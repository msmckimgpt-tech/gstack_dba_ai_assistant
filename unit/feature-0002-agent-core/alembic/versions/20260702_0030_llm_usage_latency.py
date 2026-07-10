"""llm_usage.latency_ms 컬럼 추가 (AI 운영 관제 패널 — 계측)

Revision ID: 0030_llm_usage_latency
Revises: 0029_node_analysis_relevance
Create Date: 2026-07-02

`agent_runtime.llm_usage` 에 `latency_ms INTEGER` (nullable) 를 additive 로 추가한다.
LLM chat 호출의 순수 API 왕복 지연(ms)을 best-effort 로 기록해 AI 운영 관제 패널의
latency KPI(p50/p95)에 사용한다.

**nullable + DEFAULT 없음**: 미측정 호출(예: latency 미전달 helper 경로)은 NULL 로 남아
통계에서 제외된다. DEFAULT 0 을 쓰지 않는 이유 — 미측정을 0ms 로 오인하면 p50/p95 통계가
오염된다. cost 컬럼은 추가하지 않는다(단가표 `_LLM_PRICE_USD_PER_1M` 가 web app.py 에만
있어 core 가 import 불가 → cost 는 read-time 계산 유지, admin_usage 패턴).

멱등(idempotent): `ADD COLUMN IF NOT EXISTS` — 부트스트랩 DDL(agent_runtime_schema.sql)
이 동일 컬럼을 이미 만들었어도 재적용 안전(공존, parity 반영됨).

운영 절차(TASK-0149 패턴): 라이브는 이전 head 로 stamp 되어 있으므로
`bin/alembic-migrate.sh upgrade` 가 offline `--sql` 로 ALTER 를 생성해 postgres 로컬 소켓
superuser 로 적용한다(app role agent_kb_rw 는 DDL 권한 없음).

배포 순서 안전: 마이그(컬럼 additive nullable)와 web 코드가 역순/부분 배포돼도 (a) OLD INSERT
는 신컬럼 무관하게 성공하고, (b) NEW 코드가 컬럼 부재 상태에서 INSERT 해도 _record_llm_usage
전체 try/except 가 예외를 삼켜 LLM 응답 무영향. rollback(deploy-web --rollback)은 이미지만
되돌리고 alembic downgrade 를 실행하지 않으므로 컬럼 잔존은 무해(nullable, 미참조 시 무영향).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030_llm_usage_latency"
down_revision: Union[str, None] = "0029_node_analysis_relevance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    DROP COLUMN IF EXISTS latency_ms;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
