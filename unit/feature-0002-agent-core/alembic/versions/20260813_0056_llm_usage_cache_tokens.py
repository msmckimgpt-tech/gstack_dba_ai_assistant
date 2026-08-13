"""llm_usage 캐시 토큰 계측 컬럼 — 프롬프트 캐시 읽기/쓰기 (usage-metric-charts 2026-08-13).

요청(2026-08-13): "LLM 사용량 …에 cache hit 된 입출력 또한 항목에 추가".

착수 전 실측으로 확인한 사실:
  · 게이트웨이(litellm) 응답 usage 에는 `cache_read_input_tokens` / `cache_creation_input_tokens`
    가 **항상 실려 온다**(캐싱 미사용 호출에서도 0 으로 존재).
  · `_record_llm_usage` 는 prompt/completion/total 3종만 판독해 그 값을 **버리고 있었다**.
  · `prompt_tokens` 는 캐시 토큰을 **포함**한 값이다(실측 5039 = text 37 + creation 5002).
    따라서 캐시가 활성화되면 기존 비용식은 캐시분을 정가로 계산해 **과대 계상**한다 —
    소비측(`_estimate_llm_cost_usd`)이 캐시분을 할인 단가로 분리하려면 이 두 컬럼이 필요하다.

`prompt_tokens` 와의 관계(집계·표시의 전제):
    prompt_tokens = 순수 입력 + cache_read_tokens + cache_write_tokens
즉 두 컬럼은 입력의 **부분집합**이지 별개 축이 아니다. 합산해서 총 토큰을 다시 만들지 않는다.

expand-only (CONVENTIONS §12): NOT NULL DEFAULT 0 의 컬럼 추가뿐이라 구 코드(컬럼 미인지)와
신 코드가 공존해도 안전하다. 구 코드의 INSERT 는 DEFAULT 0 으로 채워지고, 신 코드의 SELECT 는
마이그 미적용 DB 에서 컬럼 사다리(`_record_llm_usage`)가 한 단계 내려가 기록 자체는 보존한다.

**소급 불가(정직 표기)**: 기존 행은 기록 시점에 캐시 값을 받지 않았으므로 전부 0 이다. 화면의
캐시 지표는 이 마이그 적용 + 캐싱 활성화 **이후 호출부터** 의미를 갖는다.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0056_llm_usage_cache_tokens"
down_revision: Union[str, None] = "0055_tool_call_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_write_tokens INTEGER NOT NULL DEFAULT 0;
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    DROP COLUMN IF EXISTS cache_read_tokens,
    DROP COLUMN IF EXISTS cache_write_tokens;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
