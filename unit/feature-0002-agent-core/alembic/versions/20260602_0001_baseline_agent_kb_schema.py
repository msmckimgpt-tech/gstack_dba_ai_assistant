"""baseline: agent_kb 현행 스키마 (TASK-0143 #15)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-02

이 revision 은 의도적으로 비어 있다(empty upgrade/downgrade).

이유 — additive 도입의 안전 전제:
  라이브 `agent_kb` 스키마는 scripts/agent_kb_schema.sql 의 raw DDL +
  app/agent_core 부트스트랩(`_ensure_pg_schema()`)으로 이미 존재한다. baseline 의
  목적은 그 "현행 상태" 를 alembic 의 시작점으로 **표시(stamp)** 하는 것이지
  스키마를 다시 만드는 것이 아니다.

운영 절차(라이브, 스키마 변경 0):
    make migrate-stamp          # = alembic stamp head
  → 기존 DB 에 alembic_version 테이블만 생성하고 이 revision 으로 마킹.
    DDL 은 한 줄도 실행하지 않는다.

검증(라이브 무영향):
    alembic upgrade head --sql  # 빈 baseline → BEGIN/COMMIT 만 렌더(no-op).

신규 스키마 변경은 이 baseline 위에 `make migrate-new name=...` 로 새 revision
을 쌓고, 리뷰 후 `make migrate` 로 적용한다. 기존 부트스트랩 DDL 의 alembic
이관은 후속 단계(docs/MIGRATIONS.md "후속 작업" 참조).
"""
from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 의도적 no-op — 라이브 현행 스키마를 baseline 으로 stamp 만 한다.
    # 신규 DDL 은 후속 revision 으로 추가. (TASK-0143 additive 제약)
    pass


def downgrade() -> None:
    # baseline 아래로는 내려가지 않는다(현행 스키마가 곧 시작점).
    pass
