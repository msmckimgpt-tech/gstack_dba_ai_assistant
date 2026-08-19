"""redteam_review_rounds — 자가검증/재검증 회차 단계 원장 (feature-0021).

0042/0043/0045 의 `agent_runtime.redteam_reviews` 는 한 답변(run)당 **요약 1행**만
남긴다: `findings` = 최초 리뷰, `verify_findings` = **마지막** 재검증. 그래서 수정 루프가
여러 라운드를 돌아도 중간 회차(2회차 재검증이 무엇을 지적했고 3회차 수정이 어떤 방식이었는지)
는 어디에도 남지 않았고, 관리 콘솔 '감사 > AI 운영 현황 > 추론' 은 대화의 마지막 리뷰
사항만 보여줄 수밖에 없었다.

본 테이블은 그 **회차 단계 전부**를 append-only 로 기록한다 (요약 행은 통계·하위호환용으로
유지 — 본 테이블은 그 요약을 분해한 원장):

- round_index=0, phase='review'  : 최초 자가 적대 리뷰 (findings)
- round_index=N, phase='revise'  : N회차 수정 (revise_method=rederive|rewrite, axis, tool_rounds)
- round_index=N, phase='verify'  : N회차 재검증 (verdict, findings)

정렬 계약: 회차는 `(round_index ASC, id ASC)` — 콘솔이 회차 단계를 진행 순서 그대로
표시한다. 같은 round_index 안에서는 revise → verify 순으로 INSERT 되므로 id 오름차순이
곧 진행 순서다.

**답변 본문 비저장 (최소 노출)**: 수정본 텍스트는 저장하지 않고 길이(`answer_chars`)만
남긴다 — `/api/admin/reasoning/notes` 가 "파일 내용 비반환, 목록 메타만" 규약을 쓰는 것과
같은 판단. findings 의 claim/evidence 는 이미 리뷰어가 생성한 지적문이라 기존 노출 범위와
동일하다.

**신규 테이블 GRANT 필수** (0008 DEPLOY TRAP 규약): superuser 로 적용되므로 명시 GRANT 가
없으면 agent(agent_kb_rw) INSERT / web RO(agent_kb_ro) SELECT 가 permission denied 로
조용히 실패한다 (0042 와 동일 함정).

live 안전: 신규 테이블 CREATE + 인덱스 + GRANT 만 (기존 데이터 무손실, 순수 additive —
migrate-lint expand-safe). downgrade = DROP (파생 관측 데이터 소실 허용 — 0042 규약 동형).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0048_redteam_review_rounds"
down_revision: Union[str, None] = "0047_llm_usage_target_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS agent_runtime.redteam_review_rounds (
    id              BIGSERIAL PRIMARY KEY,
    review_id       BIGINT      NOT NULL
                    REFERENCES agent_runtime.redteam_reviews (id) ON DELETE CASCADE,
    conversation_id TEXT,
    run_id          TEXT,
    round_index     INTEGER     NOT NULL DEFAULT 0,   -- 0=최초 자가검증, 1..N=N회차
    phase           VARCHAR(16) NOT NULL,             -- review | revise | verify
    verdict         VARCHAR(16),                      -- pass | revise (revise 단계는 NULL)
    findings        JSONB,                            -- [{axis,severity,claim,evidence,fix_hint}]
    block_count     INTEGER     NOT NULL DEFAULT 0,
    warn_count      INTEGER     NOT NULL DEFAULT 0,
    revise_method   VARCHAR(32),                      -- rederive | rewrite (phase='revise')
    revise_axis     VARCHAR(64),                      -- 재도출로 승격된 BLOCK 축
    tool_rounds     INTEGER     NOT NULL DEFAULT 0,   -- 재추론이 돈 도구 라운드
    answer_chars    INTEGER,                          -- 수정본 길이(본문 비저장 — 최소 노출)
    note            VARCHAR(64),                      -- 라운드-로컬 메모(종료 사유 등)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 원장 무결성 — 잘못된 INSERT 가 유효한 감사 이력처럼 남지 않게 한다. phase 는 코드가
    -- 쓰는 3종으로 고정하고, 카운트/인덱스는 음수를 거부한다. (review_id, round_index, phase)
    -- UNIQUE 는 걸지 않는다 — 한 라운드에 같은 phase 를 2회 기록하는 확장(예: 수정 재시도
    -- 이력)을 막기 때문. (2026-08-19 부터 실사용: 수정 무산출 재시도가 같은 round_index 에
    -- phase='revise' 를 2회 기록한다 — note='revise_failed_retry' 행 + 채택/종료 행.)
    CONSTRAINT ck_redteam_rounds_phase
        CHECK (phase IN ('review', 'revise', 'verify')),
    CONSTRAINT ck_redteam_rounds_nonneg
        CHECK (round_index >= 0 AND block_count >= 0 AND warn_count >= 0
               AND tool_rounds >= 0 AND (answer_chars IS NULL OR answer_chars >= 0))
);

-- 콘솔 조회 계약: 요약 행 묶음 → 회차 오름차순.
CREATE INDEX IF NOT EXISTS ix_redteam_review_rounds_review
    ON agent_runtime.redteam_review_rounds (review_id, round_index, id);
-- 대화 단위 감사(대화별 전체 회차 추적)용 보조 인덱스.
CREATE INDEX IF NOT EXISTS ix_redteam_review_rounds_conversation
    ON agent_runtime.redteam_review_rounds (conversation_id, id);

-- 명시 GRANT (0008 DEPLOY TRAP 규약 — superuser 적용이라 자동 상속 없음).
GRANT SELECT, INSERT ON agent_runtime.redteam_review_rounds TO agent_kb_rw;
GRANT USAGE, SELECT ON SEQUENCE agent_runtime.redteam_review_rounds_id_seq TO agent_kb_rw;
GRANT SELECT ON agent_runtime.redteam_review_rounds TO agent_kb_ro;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.redteam_review_rounds;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
