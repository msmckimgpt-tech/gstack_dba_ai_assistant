"""cluster_summaries — 클러스터 단위 합성 요약 저장소 (feature-0033-analysis-synthesis, L2).

라이브 실측(2026-07-30): 테이블 클러스터 **818개** · 멤버 15,365개 · 평균 18.8개 · 최대 1,300개.
각 클러스터에는 **평균 9자짜리 라벨만** 있고 요약이 없다. 즉 1만여 건의 노드 분석문이 상위
의미로 접히는 층이 없어, 전역 질의는 개별 분석문을 훑는 수밖에 없다(GraphRAG 계열이 계층 요약으로
전역 질의 토큰을 크게 줄이는 지점이 바로 여기다).

**왜 `_llm_content_labels` 확장이 아닌 신규 저장 계약인가**: 그 함수는 32자 라벨 계약이고 저장소가
`agent_runtime.kv`(짧은 값)다. 요약은 수백 자이고 "멤버 N개 중 M개 근거" 같은 메타를 함께 들고
있어야 하므로 별도 테이블이 맞다.

**클러스터 정체성 = `member_set_hash`** (cluster_id 아님). `semantic_cluster_id` 는 pass 마다
MDS 배치 순서로 재부여되어 churn 한다 — 좌표를 PK 로 쓰면 클러스터가 그대로인데도 캐시가 통째로
미스 난다. 멤버셋 지문을 PK 로 두면 재배치에도 캐시가 살아남는다.

**2중 버전 키**:
  - `l1_version`       : 멤버들의 분석문(L1) 지문 — 분석이 갱신되면 요약도 갱신된다.
  - `evidence_version` : 멤버 테이블들의 통계 증거(L0, feature-0031) 지문.
증거·분석이 바뀌면 요약이 낡았음을 이 두 값이 판정한다. ⚠ 반대로 **요약은 클러스터링 시그니처에
절대 유입되지 않는다** — 유입되면 요약 갱신이 재임베딩·재클러스터를 부르고, 그 결과가 다시 요약을
바꾸는 순환이 된다(feature-0031 ADR-0031-06 과 같은 계열의 불변식).

`analyzed_count` 는 정직성 장치다. 커버리지가 14.6% 인 현실에서 "멤버 20개짜리 클러스터를 요약했다"
와 "그중 3개만 상세분석이 있었다"는 전혀 다른 신뢰도인데, 요약문만 보면 구분할 수 없다.

**DEPLOY TRAP (0028·0050 동형)**: superuser 로 적용되므로 명시 GRANT 필수.

live 안전: CREATE TABLE IF NOT EXISTS + 인덱스만 — 기존 테이블 무접촉. migrate-lint expand-safe.
downgrade = DROP TABLE(요약은 재생성 가능한 파생물).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0051_cluster_summaries"
down_revision: Union[str, None] = "0050_metadata_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS cluster_summaries (
    scope_key        varchar(96)  NOT NULL,
    schema_name      varchar(128) NOT NULL,
    member_set_hash  varchar(64)  NOT NULL,
    cluster_id       integer,
    label            varchar(128),
    summary          text         NOT NULL,
    member_count     integer      NOT NULL DEFAULT 0,
    analyzed_count   integer      NOT NULL DEFAULT 0,
    l1_version       varchar(32),
    evidence_version varchar(32),
    model            varchar(64),
    created_at       timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_key, schema_name, member_set_hash)
);

COMMENT ON TABLE cluster_summaries IS
    '클러스터 단위 합성 요약(feature-0033 L2). 정체성은 member_set_hash — cluster_id 는 pass 마다 churn 한다';
COMMENT ON COLUMN cluster_summaries.member_set_hash IS
    '클러스터 정체성 = 멤버 키 집합의 지문. 재배치(cluster_id 변경)에도 캐시가 살아남는다';
COMMENT ON COLUMN cluster_summaries.l1_version IS
    '멤버 분석문(L1) 지문 — 값이 달라지면 요약이 낡은 것이므로 재생성';
COMMENT ON COLUMN cluster_summaries.evidence_version IS
    '멤버 통계 증거(L0) 지문. 증거 변경은 이 키로만 전파된다 — 클러스터링 시그니처에는 유입 금지';
COMMENT ON COLUMN cluster_summaries.analyzed_count IS
    '멤버 중 실제 상세분석이 있던 수. 요약 신뢰도의 정직한 표기(member_count 와 함께 읽는다)';

-- 스키마 단위 조회(콘솔·상위 합성) 경로.
CREATE INDEX IF NOT EXISTS ix_cluster_summaries_scope_schema
    ON cluster_summaries (scope_key, schema_name, created_at DESC);

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON cluster_summaries TO agent_kb_rw;
GRANT SELECT ON cluster_summaries TO agent_kb_ro;
"""


DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_cluster_summaries_scope_schema;
DROP TABLE IF EXISTS cluster_summaries;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
