"""llm_usage.step_gap_ms 컬럼 추가 (AI 운영 관제 패널 — 지연 단위 재정의: 단계 간 간격)

Revision ID: 0033_llm_usage_step_gap
Revises: 0032_llm_usage_target
Create Date: 2026-07-03

`agent_runtime.llm_usage` 에 `step_gap_ms INTEGER` (nullable) 를 additive 로 추가한다.
한 요청(run_id) 안의 **연속된 에이전트 추론 라운드(agentic tool-loop) 사이의 간격** — 즉
직전 라운드 LLM 호출이 끝난 뒤 다음 라운드 LLM 호출이 시작되기까지 걸린 시간(도구 실행 +
오케스트레이션)을 ms 로 best-effort 기록해, AI 운영 관제 패널의 지연 KPI(p50/p95)를
"사용자가 답변을 받는 총 시간" 이 아니라 "각 추론 단계 간 나타나는 간격" 으로 재정의한다
(TASK-20260703-aiops-ttft-latency, 사용자 확정 정의 A).

**왜 신규 컬럼인가 (기존 latency_ms 재정의 대신)**: `latency_ms`(0030) 는 단일 LLM 호출의
전체 왕복(생성 포함)이다 — 답변 길이에 비례하는 "답변 생성 시간" 신호. 사용자 기준은 "단계 간
간격"(라운드 사이 도구·오케스트레이션 대기)이므로 별 축으로 분리한다. `latency_ms`(왕복)는
보존 — 두 신호를 모두 확보. 과거 행은 step_gap_ms=NULL 로 남아 KPI(percentile_cont …
step_gap_ms WHERE step_gap_ms IS NOT NULL)에서 자동 제외 → cutover 통계 오염 0.

**측정 위치**: agent_core `_run_agent_core` 루프가 라운드별 `_call_llm` 종료 시각(perf_counter)
을 기억했다가 다음 라운드 호출 직전 gap 을 계산해 `_call_llm(step_gap_ms=)` 로 전달한다.
run_id 의 **첫 라운드는 선행 단계가 없어 NULL**(KPI 에서 제외). 비-agent task(단발 호출)도
NULL. 즉 step_gap_ms 는 오직 다단계 에이전트 루프의 라운드 간 간격만 담는다.

**nullable + DEFAULT 없음**: 미측정(첫 라운드·단발 호출·미전달)은 NULL 로 남아 통계 제외.
DEFAULT 0 을 쓰지 않는 이유 — 미측정을 0ms 로 오인하면 p50/p95 오염(0030 latency_ms 동일 규약).

멱등(idempotent): `ADD COLUMN IF NOT EXISTS` — 부트스트랩 DDL(agent_runtime_schema.sql)이
동일 컬럼을 이미 만들었어도 재적용 안전(공존, parity 반영됨).

배포 순서 안전(expand/contract expand-only): 마이그(컬럼 additive nullable)와 core/web 코드가
역순/부분 배포돼도 (a) OLD INSERT 는 신컬럼 무관하게 성공, (b) NEW 코드가 컬럼 부재 상태에서
INSERT 해도 _record_llm_usage 의 컬럼-부재 폴백(step_gap 제외 재INSERT)이 usage 행을 보존,
(c) ai_ops.py 집계 쿼리는 쿼리별 try/except 로 컬럼 부재 시 부분 degrade. rollback 은 이미지만
되돌리고 alembic downgrade 를 실행하지 않으므로 컬럼 잔존은 무해(nullable, 미참조 시 무영향).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033_llm_usage_step_gap"
down_revision: Union[str, None] = "0032_llm_usage_target"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    ADD COLUMN IF NOT EXISTS step_gap_ms INTEGER;
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    DROP COLUMN IF EXISTS step_gap_ms;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
