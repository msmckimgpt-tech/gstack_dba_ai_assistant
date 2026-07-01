"""node_analysis — 그래프 노드 AI 능동 분석(재귀·백그라운드) 저장소 (feature-0016 graphux5).

요청(2026-07-01): 관리콘솔 그래프뷰 상세 패널에서 선택 노드에 대해 AI 가 능동적으로 분석하고,
선택 노드와 관련된 모든 다른 노드를 **재귀적으로 탐색**하며 분석을 수행한다. 부하 분산을 위해
insight-worker 백그라운드에서 처리한다.

두 테이블:
  - node_analysis_runs : 한 번의 "능동 분석" 요청(run) 단위 — 루트 노드 + 재귀 예산(depth/node) +
                          진행 카운터. 프론트가 run_id 로 진행률을 폴링한다.
  - node_analysis_jobs : run 이 재귀 확장하며 방문하는 노드별 잡 큐이자 결과 저장소. worker 가
                          status='pending' 을 FIFO 로 소비 → LLM 분석 → status='done'/analysis 기록 →
                          미방문 이웃을 (예산 내) pending 으로 재큐(재귀). UNIQUE(run_id,node_key)로 dedupe.

**비용 경계 (사용자 결정 2026-07-01 — 경계 있는 재귀)**: run 마다 depth_budget/node_budget 로 재귀를
캡하고 visited(=jobs 행 존재)로 dedupe 한다. "관련된 모든 노드"의 무한 확장(외부 LLM 비용 폭증)을 방지.

비파괴 추가(신규 테이블) — FUNCTION.md §12 사전 승인 범위(비파괴 추가만). downgrade=DROP.

**DEPLOY TRAP (load-bearing — 0024/0023 동형)**: superuser 로 적용되므로 신규 테이블에 명시 GRANT 를
넣지 않으면 web/insight(agent_kb_rw)가 INSERT/UPDATE 시 permission denied. 아래 GRANT 필수.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026_node_analysis"
down_revision: Union[str, None] = "0025_age_metadata_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- ── run 단위(요청) ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS node_analysis_runs (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        varchar(64)  NOT NULL,
    scope_key     varchar(96)  NOT NULL DEFAULT 'common',
    root_key      text         NOT NULL,
    root_label    varchar(32)  NOT NULL DEFAULT '',
    root_name     varchar(512) NOT NULL DEFAULT '',
    depth_budget  int          NOT NULL DEFAULT 2,
    node_budget   int          NOT NULL DEFAULT 150,
    status        varchar(16)  NOT NULL DEFAULT 'running',
    enqueued      int          NOT NULL DEFAULT 0,
    done          int          NOT NULL DEFAULT 0,
    failed        int          NOT NULL DEFAULT 0,
    requested_by  varchar(128),
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_node_analysis_runs_run_id UNIQUE (run_id),
    CONSTRAINT ck_node_analysis_runs_status CHECK (status IN ('running', 'done', 'failed'))
);
CREATE INDEX IF NOT EXISTS ix_node_analysis_runs_scope_root
    ON node_analysis_runs (scope_key, root_key);

-- ── 노드별 잡 큐 + 결과 ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS node_analysis_jobs (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      varchar(64)  NOT NULL,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',
    node_key    text         NOT NULL,
    node_label  varchar(32)  NOT NULL DEFAULT '',
    node_name   varchar(512) NOT NULL DEFAULT '',
    node_fqn    text         NOT NULL DEFAULT '',
    depth       int          NOT NULL DEFAULT 0,
    status      varchar(16)  NOT NULL DEFAULT 'pending',
    analysis    text,
    model       varchar(128),
    error       text,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_node_analysis_jobs_run_node UNIQUE (run_id, node_key),
    CONSTRAINT ck_node_analysis_jobs_status CHECK (status IN ('pending', 'running', 'done', 'failed')),
    CONSTRAINT fk_node_analysis_jobs_run
        FOREIGN KEY (run_id) REFERENCES node_analysis_runs (run_id) ON DELETE CASCADE
);
-- worker FIFO 폴링(pending 오래된 것부터)
CREATE INDEX IF NOT EXISTS ix_node_analysis_jobs_status_created
    ON node_analysis_jobs (status, created_at);
-- 상세 패널 조회(노드의 최신 done 분석)
CREATE INDEX IF NOT EXISTS ix_node_analysis_jobs_node_lookup
    ON node_analysis_jobs (scope_key, node_key, status);

DROP TRIGGER IF EXISTS trg_node_analysis_runs_updated_at ON node_analysis_runs;
CREATE TRIGGER trg_node_analysis_runs_updated_at
    BEFORE UPDATE ON node_analysis_runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_node_analysis_jobs_updated_at ON node_analysis_jobs;
CREATE TRIGGER trg_node_analysis_jobs_updated_at
    BEFORE UPDATE ON node_analysis_jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON node_analysis_runs TO agent_kb_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON node_analysis_jobs TO agent_kb_rw;
GRANT SELECT ON node_analysis_runs TO agent_kb_ro;
GRANT SELECT ON node_analysis_jobs TO agent_kb_ro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS node_analysis_jobs;
DROP TABLE IF EXISTS node_analysis_runs;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
