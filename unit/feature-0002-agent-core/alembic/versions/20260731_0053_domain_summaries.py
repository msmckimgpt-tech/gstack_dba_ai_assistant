"""domain_summaries — 스키마(도메인) 단위 합성 요약 저장소 (feature-0037, ITEM-08 / L3).

라이브 실측(2026-07-31): 클러스터 요약 **1,006건**이 **120개 스키마**에 걸쳐 쌓였다(멤버
11,693). 클러스터 요약(L2)은 "이 묶음이 함께 무엇을 하는가"에 답하지만, "이 DB 전체가 어떤
도메인이고 그 안에 어떤 축들이 있는가"에는 답하지 않는다. 그 층이 L3 다.

**두 제약을 동시에 지킨다**

1. **사전 전량 생성 금지** (LazyGraphRAG 교훈 — 사전요약 0으로도 전역질의 품질 동등, 비용
   700배↓). 120개 스키마를 미리 다 합성하면 대부분은 아무도 읽지 않는다.
2. **답변 경로 런타임 합성 금지** (ADR-0034-07). 질문이 들어온 그 순간 LLM 을 부르면
   feature-0027 이 확보한 체감 지연 개선을 잠식한다.

두 제약은 얼핏 모순이다 — 미리 만들지도 말고 필요할 때 만들지도 말라니. 해법은 **요청과 생성을
분리**하는 것이다:

    grounding 이 조회 → 없으면 `requested_at` 만 남긴다(LLM 0, 지연 0)
    insight tick 이 요청된 것만 합성 → 다음 질문부터 주입된다

즉 "누가 실제로 찾았는가"가 생성 신호가 된다. 아무도 찾지 않은 스키마는 영원히 만들어지지 않고,
한 번 찾힌 스키마는 곧 채워진다. 첫 질문은 요약 없이 답하지만 그 대가로 120번의 헛된 합성을
치르지 않는다.

`cluster_set_hash` 는 그 스키마의 클러스터 요약 집합 지문이다 — 클러스터가 재구성되거나 요약이
갱신되면 도메인 요약도 낡은 것이므로 재생성 대상이 된다(feature-0033 의 2중 버전 키와 같은 계열).

**DEPLOY TRAP (0028·0050~0052 동형)**: superuser 로 적용되므로 명시 GRANT 필수.

live 안전: CREATE TABLE IF NOT EXISTS + 인덱스만. downgrade = DROP TABLE(재생성 가능한 파생물).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0053_domain_summaries"
down_revision: Union[str, None] = "0052_analysis_verdicts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS domain_summaries (
    scope_key        varchar(96)  NOT NULL,
    schema_name      varchar(128) NOT NULL,
    summary          text,
    cluster_count    integer      NOT NULL DEFAULT 0,
    member_count     integer      NOT NULL DEFAULT 0,
    analyzed_count   integer      NOT NULL DEFAULT 0,
    cluster_set_hash varchar(32),
    model            varchar(64),
    requested_at     timestamptz,
    request_count    integer      NOT NULL DEFAULT 0,
    generated_at     timestamptz,
    PRIMARY KEY (scope_key, schema_name)
);

COMMENT ON TABLE domain_summaries IS
    '스키마(도메인) 단위 합성 요약(feature-0037 L3). 요청(requested_at)과 생성(generated_at)이 분리된다 '
    '— 사전 전량 생성도, 답변 경로 런타임 합성도 하지 않기 위해서다';
COMMENT ON COLUMN domain_summaries.requested_at IS
    'grounding 이 이 스키마 요약을 찾았지만 없었던 시각. 이것이 생성 신호다 — 아무도 찾지 않은 '
    '스키마는 합성하지 않는다';
COMMENT ON COLUMN domain_summaries.request_count IS
    '요청 누적. 자주 찾히는 도메인을 먼저 합성하는 우선순위 신호';
COMMENT ON COLUMN domain_summaries.cluster_set_hash IS
    '그 스키마의 클러스터 요약 집합 지문 — 클러스터가 재구성되거나 요약이 갱신되면 재생성 대상';
COMMENT ON COLUMN domain_summaries.analyzed_count IS
    '입력이 된 클러스터 요약 중 상세분석 근거가 있던 수. 요약 신뢰도의 정직한 표기';

-- 생성 대기(요청됐지만 미생성) 조회 — 요청 많은 것부터.
CREATE INDEX IF NOT EXISTS ix_domain_summaries_pending
    ON domain_summaries (request_count DESC, requested_at)
    WHERE generated_at IS NULL AND requested_at IS NOT NULL;

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON domain_summaries TO agent_kb_rw;
GRANT SELECT ON domain_summaries TO agent_kb_ro;
"""


DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_domain_summaries_pending;
DROP TABLE IF EXISTS domain_summaries;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
