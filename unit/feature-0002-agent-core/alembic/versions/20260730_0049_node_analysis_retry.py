"""node_analysis_retry — 노드 분석 잡의 일시 실패 재시도 계정 (feature-0016 analysis-retry-resilience).

사용자 리포트(2026-07-30): "그래프 뷰에서 AI 능동 분석이 (주기적인 네트워크 단절) 중단될 경우 …
네트워크가 다시 연결되더라도 아무런 작업이 이루어지지 않습니다."

원인은 잡 상태머신에 **재시도 계정이 없다**는 것이다. `llm_node_analysis` 는 네트워크 오류·타임아웃·
429·빈 응답을 전부 `None` 으로 평탄화하고, 호출측은 그 `None` 을 즉시 terminal `status='failed'` 로
기록한다. stale 회수(lease)는 `running` 만 대상이므로 `failed` 는 영구히 굳고, run 은 남은 잡이
없어지면 `done`/`failed` 로 마감된다 — 단절이 해소돼도 되살아날 행이 없다.

본 마이그레이션은 그 계정을 추가한다(컬럼 3개, 전부 additive):

- `attempts`        : 이 잡이 소비한 LLM 시도 횟수. `AGENT_NODE_ANALYSIS_MAX_ATTEMPTS` 를 넘으면
                      종전처럼 terminal `failed`(무한 재시도로 비용이 새지 않게 하는 상한).
- `next_attempt_at` : 재시도 예약 시각. claim 은 `next_attempt_at IS NULL OR <= now()` 만 집어간다
                      (지수 backoff — 단절 창에서 같은 잡을 즉시 재소모하지 않음).
- `error_kind`      : 마지막 실패의 분류(`transient` / `transient_exhausted` / `permanent`).
                      운영이 "이 실패가 회수 가능한가"를 SQL 한 줄로 판정할 수 있게 한다.

부분 인덱스 `ix_node_analysis_jobs_retry_due` 는 claim 게이트(`status='pending'` + due)를 받는다.
기존 `ix_node_analysis_jobs_claim_priority`(0029, depth/relevance/created_at)는 그대로 유지된다.

**GRANT 불필요**: 신규 테이블이 아니라 기존 `node_analysis_jobs`(0028 에서 agent_kb_rw/ro 에 부여)의
컬럼 추가라 테이블 레벨 권한이 그대로 상속된다.

live 안전: `ADD COLUMN ... DEFAULT`(PG11+ 는 테이블 재작성 없음) + 부분 인덱스 생성만 —
순수 additive, 기존 행 무손실(default 0/NULL 이 곧 "재시도 이력 없음" = 종전 동작).
migrate-lint expand-safe. downgrade = DROP COLUMN(파생 계정 소실 허용).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0049_node_analysis_retry"
down_revision: Union[str, None] = "0048_redteam_review_rounds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE node_analysis_jobs
    ADD COLUMN IF NOT EXISTS attempts        smallint    NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz,
    ADD COLUMN IF NOT EXISTS error_kind      varchar(32);

COMMENT ON COLUMN node_analysis_jobs.attempts IS
    '이 잡이 소비한 LLM 시도 횟수 — AGENT_NODE_ANALYSIS_MAX_ATTEMPTS 초과 시 terminal failed';
COMMENT ON COLUMN node_analysis_jobs.next_attempt_at IS
    '재시도 예약 시각(지수 backoff). claim 은 NULL 또는 <= now() 만 집어간다';
COMMENT ON COLUMN node_analysis_jobs.error_kind IS
    '마지막 실패 분류: transient | transient_exhausted | permanent';

-- claim 게이트(status='pending' + 예약 시각 도달) 전용 부분 인덱스.
CREATE INDEX IF NOT EXISTS ix_node_analysis_jobs_retry_due
    ON node_analysis_jobs (next_attempt_at)
    WHERE status = 'pending';
"""


DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_node_analysis_jobs_retry_due;
ALTER TABLE node_analysis_jobs
    DROP COLUMN IF EXISTS error_kind,
    DROP COLUMN IF EXISTS next_attempt_at,
    DROP COLUMN IF EXISTS attempts;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
