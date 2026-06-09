"""ask_jobs 큐 테이블 추가 — out-of-process ask-worker 실행모델 (TASK-0169)

Revision ID: 0003_ask_jobs
Revises: 0002_llm_usage_resolved_model
Create Date: 2026-06-09

`agent_runtime.ask_jobs` 는 `/api/ask` 의 agent 실행을 web 프로세스 밖 전용
`ask-worker` 로 분리하기 위한 job 큐다 (DESIGN-ask-worker.md / ADR-WEB-0004 의 B).
web 은 enqueue + 내부 long-poll attach 만 하고, 실행은 worker 가 claim 해서 돌린다.
run 진행상태(KV last_status / steps / core_messages)는 기존 테이블을 그대로 재사용
하므로 본 테이블은 큐/운영 메타만 담는다(run 테이블 overload 금지).

핵심 동시성 컬럼:
  - `status` (pending/claimed/running/done/error/canceled): claim 은
    `UPDATE ... WHERE id=(SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)` 단일문으로만
    수행해야 exactly-once 가 보장된다(autocommit conn 에서 SELECT 후 별도 UPDATE 는
    락 미유지 → double-claim).
  - `lease_epoch`: 매 (re)claim 마다 ++. worker 는 자기 lease 를 주기적으로 재확인해
    stale sweeper 가 requeue 로 빼앗았으면 write 를 중단한다(fencing — 살아있는 느린
    worker 와 requeue 후 새 worker 의 동시 double-run 방지).
  - `heartbeat_at`: worker 가 매 step + 긴 LLM call 내부에서 갱신. stale sweeper 는
    `heartbeat_at < now - 임계(≥ run_timeout + margin)` 인 running job 만 회수한다.
  - `attempts`: requeue 시 ++. cap 도달 시 terminal error(무한 requeue 차단).
  - `payload` (jsonb): run_agent kwargs 미러. `result_json` (jsonb): terminal 시
    worker 가 기록 → web 내부 attach 가 응답 shape 패리티를 위해 읽는다.

멱등: `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`. 부트스트랩 fast-path
`_ensure_ask_jobs()` (app.py / memory.py) 가 동일 DDL 을 재적용해도 안전(공존). 본
revision 이 스키마 권위이고 _ensure_* 는 dev/cold-boot 보조다.

FK 없음(의도): 큐 시맨틱 — conversation 삭제/부재와 decoupled. conversation_id 는
enqueue 시점에 이미 생성됨(app.py /api/ask 가 create_if_missing).

운영 절차(TASK-0149/0163 패턴): 라이브는 `0002_llm_usage_resolved_model` 로 stamp 되어
있으므로 `bin/alembic-migrate.sh upgrade` 가 offline `--sql` 로 ALTER/CREATE 를 생성해
postgres 로컬 소켓 superuser 로 적용한다(app role agent_kb_rw 는 DDL 권한 없음).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_ask_jobs"
down_revision: Union[str, None] = "0002_llm_usage_resolved_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS agent_runtime.ask_jobs (
    id bigint GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME agent_runtime.ask_jobs_id_seq
        START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1
    ),
    conversation_id character varying(128) NOT NULL,
    run_id character varying(64),
    account_id bigint NOT NULL,
    status character varying(16) NOT NULL DEFAULT 'pending',
    claimed_by character varying(128),
    claimed_at timestamp with time zone,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    attempts integer NOT NULL DEFAULT 0,
    lease_epoch integer NOT NULL DEFAULT 0,
    heartbeat_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    result_json jsonb,
    CONSTRAINT ask_jobs_pkey PRIMARY KEY (id),
    CONSTRAINT ask_jobs_status_chk CHECK (
        status IN ('pending','claimed','running','done','error','canceled')
    )
);

-- claim 정렬(FIFO): pending 을 created_at 순으로. SKIP LOCKED 스캔 효율.
CREATE INDEX IF NOT EXISTS ix_ask_jobs_claim
    ON agent_runtime.ask_jobs (status, created_at);

-- slot enforce: 계정별 활성 job count.
CREATE INDEX IF NOT EXISTS ix_ask_jobs_account
    ON agent_runtime.ask_jobs (account_id, status);

-- stale sweeper: running job 의 heartbeat 신선도 스캔.
CREATE INDEX IF NOT EXISTS ix_ask_jobs_heartbeat
    ON agent_runtime.ask_jobs (heartbeat_at);

-- cancel / ownership(backstop) lookup: conversation 단위 활성 job 조회.
CREATE INDEX IF NOT EXISTS ix_ask_jobs_conv
    ON agent_runtime.ask_jobs (conversation_id);
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.ask_jobs;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
