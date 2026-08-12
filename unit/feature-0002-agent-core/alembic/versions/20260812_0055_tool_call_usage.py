"""tool_call_usage — 외부 AI 도구 표면 부하 원장 (feature-0041 external-ai-tool-surface).

요청(2026-08-12, REQ-20260812-external-ai-tool-surface): 외부 사용자의 AI 가 **자기 계정
LLM 으로 직접 추론**하면서 이 서비스의 데이터·컨텍스트에 접근한다. 추론이 우리 밖에서
일어나므로 `agent_runtime.llm_usage` 에는 행이 남지 않는다 — 즉 **토큰 축 원장과 그 위에
얹힌 모든 한도**(`WebRoleTokenQuotas` / `WebAccountTokenQuotas` / feature-0032 백그라운드
예산)가 이 트래픽에 대해 **항상 0 으로 읽혀 통과**한다.

비용은 우리가 안 내지만 **부하는 여전히 우리 DB 가 낸다.** 그래서 토큰이 아니라 **호출·행수·
바이트** 를 세는 별도 원장을 둔다. `llm_usage` 와 나란히 `agent_runtime` 에 두되 스키마는
공유하지 않는다 — 단위가 다르고(토큰 vs 행/바이트) 소비자도 다르다(비용 리포트 vs 부하 게이트).

  · account_id  = MySQL `WebAccounts.Id` 미러(FK 없음 — 교차 DB). 귀속의 정본.
  · client_id   = 머신 AI 런타임 식별자(OAuth DCR 발급). 신원:비용 = N:1 의 비용 축.
  · task_id     = task 세션 계약의 단위. 교차오염 대조의 조인 키.
  · outcome     = ok | denied | gated | error — denied/gated 도 반드시 기록한다
                  (거절이 안 남으면 남용 패턴을 사후 재구성할 수 없다).

**원장은 fail-closed 다 (codex REV-20260812-0001 P1)**: 누적 상한의 원천이 이 테이블이므로
기록 실패를 best-effort 로 두면 그 실패가 곧 상한 우회가 된다. 애플리케이션은 도구 결과를
반환하기 **전에** 이 행을 커밋하고, 실패 시 결과를 반환하지 않는다.

인덱스 설계 — 게이트 질의는 항상 "최근 N 초/시간 동안 이 주체가 얼마나 썼나" 형태다:
  · ix_tcu_account_time (account_id, created_at DESC) — 계정 단위 rate/누적
  · ix_tcu_client_time  (client_id,  created_at DESC) — 머신 단위 rate/누적
  · ix_tcu_task         (task_id)                     — 교차오염 대조·task 마감

**DEPLOY TRAP (0034/0028/0025 동형)**: superuser 적용이라 신규 테이블에 명시 GRANT 필수.
role 존재 가드로 감싼다(로컬 개발 DB 에 role 이 없을 수 있음).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0055_tool_call_usage"
down_revision: Union[str, None] = "0054_db_objects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS agent_runtime.tool_call_usage (
    id               bigserial     PRIMARY KEY,
    account_id       bigint        NOT NULL,
    client_id        varchar(64),
    task_id          varchar(64),
    conversation_id  varchar(255),
    tool             varchar(64)   NOT NULL,
    datasource_key   varchar(96),
    schema_name      varchar(255),
    rows_returned    integer       NOT NULL DEFAULT 0,
    bytes_out        integer       NOT NULL DEFAULT 0,
    est_scanned_rows bigint,
    latency_ms       integer,
    outcome          varchar(16)   NOT NULL DEFAULT 'ok',
    detail           varchar(255),
    created_at       timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT ck_tool_call_usage_outcome CHECK (
        outcome IN ('ok', 'denied', 'gated', 'error')
    )
);

CREATE INDEX IF NOT EXISTS ix_tcu_account_time
    ON agent_runtime.tool_call_usage (account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_tcu_client_time
    ON agent_runtime.tool_call_usage (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_tcu_task
    ON agent_runtime.tool_call_usage (task_id);

-- ── GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 미커버) ──────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runtime.tool_call_usage TO agent_kb_rw;
        GRANT USAGE, SELECT ON SEQUENCE agent_runtime.tool_call_usage_id_seq TO agent_kb_rw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        GRANT SELECT ON agent_runtime.tool_call_usage TO agent_kb_ro;
    END IF;
END $$;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.tool_call_usage;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
