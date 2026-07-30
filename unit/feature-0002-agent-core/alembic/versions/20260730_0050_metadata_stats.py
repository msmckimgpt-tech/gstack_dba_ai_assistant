"""metadata_stats — 노드 분석 접지용 통계 증거층 (feature-0031-analysis-grounding, L0).

그래프 뷰 'AI 능동 분석'의 LLM 입력에는 지금까지 **데이터 실측이 전혀 없었다** — 이름·설명·이웃
관계만 주고, 프롬프트가 "이름 규칙에서 가장 그럴듯한 의미를 추론하고 단정하라"고 지시한다. 결과적으로
1만여 건의 분석문이 추측을 정본처럼 담고 있다(summary 평균 94자). 본 마이그레이션은 그 추측을
데이터에 접지시킬 통계 저장소를 만든다.

신규 2 테이블(전부 additive, 기존 테이블 무변경):

- `metadata_table_stats`  : 테이블 단위 — 근사 row count · 컬럼 수 · PK/인덱스 구성 · FK 진출입 수
- `metadata_column_stats` : 컬럼 단위 — 타입/nullable/길이상한(카탈로그) + 표본 통계
                            (distinct 추정 · null 비율 · 숫자·시각 min/max · 문자열 길이 분포 ·
                             패턴 클래스 · 표본 내 유일성)

**원시 샘플값 미저장 (설계 불변식, 사용자 확정 2026-07-30)**
컬럼 값 자체는 어떤 형태로도 저장하지 않는다. 문자열 컬럼의 min/max 값도 저장하지 않는다 —
문자열 극단값은 사실상 원시 샘플 1건이며 이름·이메일·주소 컬럼에서는 곧 PII 다. 대신 길이 분포와
**패턴 클래스**(`value_pattern`)를 남긴다. 그 컬럼에는 CHECK 제약으로 열거된 분류값만 들어갈 수
있어, 실수로 원시값을 적재하려 하면 **DB 가 거부**한다(코드 리뷰가 아니라 스키마가 보증한다).
숫자·시각 타입만 min/max 를 남긴다(범위 파악 가치가 크고 개인 식별성이 낮다).

`stage` 는 수집 깊이다: 0=카탈로그만 · 1=표본 100 · 2=표본 1,000 · 3=정밀(운영자 승격).
승격은 하루 1단계 + 시간창 상한 + 운영자 승인이며, 수집 자체는 `ds` 자원 예산(feature-0025 T0b)
게이트 위에서 fail-soft 로 돈다.

**DEPLOY TRAP (0028 동형, load-bearing)**: 마이그레이션은 superuser 로 적용되므로 신규 테이블에
명시 GRANT 를 넣지 않으면 web/insight(agent_kb_rw)가 INSERT/UPDATE 시 permission denied 로
조용히 실패한다. 아래 GRANT 필수.

live 안전: CREATE TABLE IF NOT EXISTS + 인덱스 생성만 — 기존 테이블·데이터 무접촉.
migrate-lint expand-safe. downgrade = DROP TABLE(파생 통계 소실 허용 — 재수집 가능).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0050_metadata_stats"
down_revision: Union[str, None] = "0049_node_analysis_retry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS metadata_table_stats (
    scope_key     varchar(96)  NOT NULL,
    schema_name   varchar(128) NOT NULL,
    table_name    varchar(256) NOT NULL,
    row_count_est bigint,
    column_count  integer,
    pk_columns    text[],
    index_columns text[],
    fk_out        integer,
    fk_in         integer,
    stage         smallint     NOT NULL DEFAULT 0,
    sampled_rows  integer      NOT NULL DEFAULT 0,
    collected_at  timestamptz  NOT NULL DEFAULT now(),
    error         text,
    PRIMARY KEY (scope_key, schema_name, table_name)
);

COMMENT ON TABLE metadata_table_stats IS
    '테이블 단위 통계 증거(feature-0031 L0) — 노드 분석 payload 의 evidence 원천. 원시 데이터 미저장';
COMMENT ON COLUMN metadata_table_stats.row_count_est IS
    '근사 행 수 — 카탈로그 추정치(COUNT(*) 전수 스캔 금지)';
COMMENT ON COLUMN metadata_table_stats.stage IS
    '수집 깊이: 0=카탈로그만 1=표본100 2=표본1000 3=정밀(운영자 승격)';
COMMENT ON COLUMN metadata_table_stats.error IS
    '마지막 수집 실패 사유 — 다음 주기 재시도(수집 실패가 분석을 막지 않는다)';

CREATE TABLE IF NOT EXISTS metadata_column_stats (
    scope_key        varchar(96)  NOT NULL,
    schema_name      varchar(128) NOT NULL,
    table_name       varchar(256) NOT NULL,
    column_name      varchar(256) NOT NULL,
    data_type        varchar(64),
    is_nullable      boolean,
    char_max_len     integer,
    distinct_est     bigint,
    null_ratio       numeric(6,4),
    num_min          numeric,
    num_max          numeric,
    ts_min           timestamptz,
    ts_max           timestamptz,
    len_min          integer,
    len_max          integer,
    len_avg          numeric(10,2),
    value_pattern    varchar(16),
    unique_in_sample boolean,
    stage            smallint     NOT NULL DEFAULT 0,
    sampled_rows     integer      NOT NULL DEFAULT 0,
    collected_at     timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_key, schema_name, table_name, column_name),
    CONSTRAINT ck_metadata_column_stats_pattern CHECK (
        value_pattern IS NULL
        OR value_pattern IN ('digits', 'hex', 'uuid', 'email_like', 'mixed', 'empty')
    )
);

COMMENT ON TABLE metadata_column_stats IS
    '컬럼 단위 통계 증거(feature-0031 L0). 컬럼 값 자체는 저장하지 않는다 — 문자열 min/max 도 미저장';
COMMENT ON COLUMN metadata_column_stats.value_pattern IS
    '문자열 형태 분류(값 아님): digits|hex|uuid|email_like|mixed|empty. CHECK 제약이 원시값 적재를 거부한다';
COMMENT ON COLUMN metadata_column_stats.num_min IS
    '숫자 타입 최솟값 — 문자열 컬럼에는 채우지 않는다(원시 샘플 배제)';
COMMENT ON COLUMN metadata_column_stats.len_avg IS
    '문자열 길이 평균 — 문자열 컬럼의 범위 정보는 값이 아니라 길이로만 남긴다';
COMMENT ON COLUMN metadata_column_stats.unique_in_sample IS
    '표본 내 distinct = sampled_rows (키 후보 신호). 전수 UNIQUE 보장이 아니다';

-- 수집 스케줄러가 "오래된 것부터" 고르는 경로.
CREATE INDEX IF NOT EXISTS ix_metadata_table_stats_stale
    ON metadata_table_stats (scope_key, collected_at);

-- 분석 payload 조립이 (scope, schema, table) 로 컬럼 통계를 한 번에 읽는 경로는 PK prefix 가 받는다.

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON metadata_table_stats  TO agent_kb_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON metadata_column_stats TO agent_kb_rw;
GRANT SELECT ON metadata_table_stats  TO agent_kb_ro;
GRANT SELECT ON metadata_column_stats TO agent_kb_ro;
"""


DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_metadata_table_stats_stale;
DROP TABLE IF EXISTS metadata_column_stats;
DROP TABLE IF EXISTS metadata_table_stats;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
