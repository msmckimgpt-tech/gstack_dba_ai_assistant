"""llm_usage.target_scope 컬럼 추가 (사용 기록 → 데이터소스 정확 귀속)

Revision ID: 0047_llm_usage_target_scope
Revises: 0046_relationship_updated_at_if_changed
Create Date: 2026-07-28

`agent_runtime.llm_usage` 에 `target_scope VARCHAR(96)` (nullable) 를 additive 로 추가한다.
0032 가 도입한 `target`(schema / schema.table / 노드 FQN)에는 **데이터소스 차원이 없어서**,
관리 콘솔 '사용 기록'(감사 > AI 운영 현황 > LLM 사용량 드릴다운)이 시스템 사용분의 대상 화면으로
이동할 때 어느 데이터소스인지 특정하지 못했다.

**왜 역해소로는 부족했는가 (본 컬럼의 존재 이유)**: 직전 cycle
(CHG-20260728T113819-usage-records-system)은 `table_descriptions` ∪ `routine_objects` ∪
`rag_objects` 를 union 해 `target` → 데이터소스를 **역해소**했다. 그러나 dev/qa 가 같은 스키마·
테이블 이름을 공유하는 실환경에서 라이브 실측 8,399 distinct target 중 상당수가 후보 2+ 로
**구조적으로 모호**했고(추측 금지 정책상 "화면까지만 이동"으로 저하), 역해소는 조회 시점에
메타데이터 적재 상태에 의존해 시간이 지나면 답이 달라지는 문제도 있었다. 기록 시점에 이미
알고 있는 값을 **그때 저장**하는 것이 정본 해법이다.

**값의 의미**: 데이터소스 `scope_key` — 관리 콘솔 데이터소스 셀렉터(`metadataScopeSelect`/
`graphScopeSelect`)의 option value 이자 `rag_objects.datasource_key` 와 같은 공간
(DB 등록 ds=엔드포인트 해시 `mysql-<12hex>`, .env 레거시=라벨). 96자는 `rag_objects.scope_key`
(VARCHAR(96)) 와 동일 폭으로 맞춘다.

**왜 target 에 접합하지 않는가**: 0032 와 같은 이유 — `target` 은 표시용 자유 문자열이고,
스코프는 **필터·조인 키**로 쓰인다(드릴다운이 이 값으로 콘솔 스코프를 선택). 접합하면 파싱이
필요해지고 기존 target 표시가 깨진다.

**nullable + DEFAULT 없음**: 데이터소스 개념이 없는 활동(대화 추론·요약·분류·프롬프트 생성 등)과
**기존 행 전부**가 NULL 로 남는다. 소급 백필하지 않는다 — 과거 행의 정확한 스코프는 복원 불가라
추측 백필은 잘못된 귀속을 만든다. 웹은 `target_scope` 가 있으면 그것을, 없으면 종전 역해소를
쓰는 2단 폴백이라 legacy 행도 종전 수준으로 동작한다.

멱등(idempotent): `ADD COLUMN IF NOT EXISTS` — 부트스트랩 DDL(agent_runtime_schema.sql)이 동일
컬럼을 이미 만들었어도 재적용 안전(parity 반영됨).

배포 순서 안전(expand-only, CONVENTIONS §12): 컬럼이 additive nullable 이라 (a) 구 코드의 INSERT 는
신컬럼 무관하게 성공하고, (b) 신 코드가 컬럼 부재 상태에서 INSERT 해도 `_record_llm_usage` 가
target_scope 제외 INSERT 로 **폴백**해 usage 행 자체는 보존된다(0032·0033 과 동일한 자가치유
사다리 — stale agent image 로 마이그가 누락돼도 계측이 조용히 끊기지 않는다). rollback 은
이미지만 되돌리고 downgrade 를 실행하지 않으므로 컬럼 잔존은 무해(nullable, 미참조 시 무영향).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0047_llm_usage_target_scope"
down_revision: Union[str, None] = "0046_relationship_updated_at_if_changed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    ADD COLUMN IF NOT EXISTS target_scope VARCHAR(96);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.llm_usage
    DROP COLUMN IF EXISTS target_scope;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
