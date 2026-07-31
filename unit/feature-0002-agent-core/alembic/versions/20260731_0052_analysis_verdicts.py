"""analysis_verdicts — 노드 분석문의 사실성 판정 저장소 (feature-0036, ITEM-10).

**왜 필요한가.** 지금까지 생성된 분석문의 사실성을 **아무도 확인하지 않았다**. 1만여 건이
쌓였고 그것이 클러스터 요약(L2)의 입력이 되고 대화 답변의 grounding 으로 주입되는데
(feature-0033·0034), 그 어느 지점에도 "이 서술이 실제 데이터와 맞는가"를 묻는 층이 없었다.
feature-0031 이 증거(L0 통계)를 만들었으니 이제 대조가 가능하다.

**왜 feature-0021 red-team 을 재사용하지 않았나.** 그 프롬프트는 `question + draft + evidence`
구조의 **답변 전용**이다. 노드 분석문에는 question 이 없고 evidence 의 성격도 다르다(대화
근거 vs 테이블 통계). 억지로 끼우면 두 계약이 서로를 제약한다.

**왜 `pass_no` 를 쓰지 않나.** `node_analysis_jobs.pass_no` 는 back-refine 세대를 뜻한다
(재분석 몇 번째인가). 검증은 그와 직교하는 축이라 같은 컬럼에 얹으면 "3번째 재분석"과
"3번째 검증"이 구분되지 않는다. 별 테이블이 정직하다.

**정직성 계약 (이 테이블의 존재 이유)**

  `verdict` ∈ supported | contradicted | unverifiable

  - `supported`     : 증거가 분석문의 주장을 뒷받침한다
  - `contradicted`  : 증거가 분석문과 **모순된다**
  - `unverifiable`  : 증거가 그 주장을 다루지 않는다(검증 실패가 아니다)

  ⚠ **판정에 실패하면 행을 만들지 않는다.** LLM 오류·타임아웃·예산 소진은 "미검증"이며,
  그것을 `supported` 로도 `unverifiable` 로도 기록하지 않는다. fail-open 이 "검증됨"으로
  둔갑하면 이 층은 있는 것보다 나쁘다 — 아무도 확인하지 않은 서술에 확인 도장이 찍힌다.

`analysis_hash` 가 PK 에 들어가는 이유: 분석문이 갱신되면(refine) 이전 판정은 그 새 문장에
대한 것이 아니다. 해시가 다르면 자연히 미검증으로 돌아간다.

**DEPLOY TRAP (0028·0050·0051 동형)**: superuser 로 적용되므로 명시 GRANT 필수.

live 안전: CREATE TABLE IF NOT EXISTS + 인덱스만. downgrade = DROP TABLE(판정은 재생성 가능).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0052_analysis_verdicts"
down_revision: Union[str, None] = "0051_cluster_summaries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS node_analysis_verdicts (
    scope_key      varchar(96)  NOT NULL,
    node_key       varchar(512) NOT NULL,
    analysis_hash  varchar(32)  NOT NULL,
    verdict        varchar(16)  NOT NULL,
    reason         text,
    evidence_stage smallint,
    model          varchar(64),
    created_at     timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_key, node_key, analysis_hash),
    CONSTRAINT ck_node_analysis_verdicts_verdict CHECK (
        verdict IN ('supported', 'contradicted', 'unverifiable')
    )
);

COMMENT ON TABLE node_analysis_verdicts IS
    '노드 분석문 ↔ 통계 증거 대조 판정(feature-0036 ITEM-10). 판정 실패는 행 없음(=미검증)';
COMMENT ON COLUMN node_analysis_verdicts.analysis_hash IS
    '판정 대상 분석문의 지문 — 분석이 갱신되면 해시가 달라져 자연히 미검증으로 돌아간다';
COMMENT ON COLUMN node_analysis_verdicts.verdict IS
    'supported=증거가 뒷받침 · contradicted=증거와 모순 · unverifiable=증거가 그 주장을 다루지 않음. '
    'LLM 실패·예산 소진은 어느 쪽도 아니며 행 자체를 만들지 않는다(미검증)';
COMMENT ON COLUMN node_analysis_verdicts.evidence_stage IS
    '판정에 쓰인 증거의 수집 깊이(metadata_table_stats.stage) — 얕은 증거의 판정을 구분한다';

-- 운영 조회: "모순 판정이 난 분석" · "스코프별 검증 현황".
CREATE INDEX IF NOT EXISTS ix_node_analysis_verdicts_scope_verdict
    ON node_analysis_verdicts (scope_key, verdict, created_at DESC);

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON node_analysis_verdicts TO agent_kb_rw;
GRANT SELECT ON node_analysis_verdicts TO agent_kb_ro;
"""


DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_node_analysis_verdicts_scope_verdict;
DROP TABLE IF EXISTS node_analysis_verdicts;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
