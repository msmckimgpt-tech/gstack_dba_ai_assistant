"""table_relationships — updated_at 트리거를 '값 변경 시에만' 으로 (feature-0029 churn-a).

배경: `set_updated_at()`(baseline 0001)은 UPDATE 마다 무조건 `NEW.updated_at = now()` 를
찍는다. 그런데 관계 유지보수에는 **그래프 의미가 없는 rotation-only UPDATE** 두 종이 있다:
  - `_touch_validated`     : `SET last_validated_at = now()` (프로브 neutral — 순번 공정화)
  - `_backoff_validated`   : `SET last_validated_at = ... + backoff` (transient 실패 지연)
둘 다 weight/status/confidence 를 바꾸지 않는데도 `updated_at` 이 밀렸고, incremental
sync 는 `updated_at > since` 로 대상을 고르므로(metadata_graph `_scope_since_where`)
이 행들이 30분마다 AGE 로 재투영됐다 — **관계 1건 = cypher 11회**.

라이브 근거(2026-07-28 실측): 최근 2h 갱신 2,832행 중 ~1,796행(63%)이 값 무변경이었고,
broken 3,722행 중 3,603행(97%)이 파단 후 재-upsert 로 타임스탬프만 밀려 매 주기 이미
없는 엣지를 반복 DELETE 했다. sync duration 은 churn 행 수에 선형(무변경 cycle 18ms vs
1,453행 cycle 36초).

본 마이그레이션은 `table_relationships` **전용** 트리거를 `set_updated_at_if_changed()`
로 교체한다 — `updated_at`/`last_validated_at` 을 제외한 나머지 컬럼이 실제로 달라질 때만
now() 를 찍는다(`to_jsonb` diff — 신규 컬럼이 추가돼도 비교 목록 누락 함정이 없다).
다른 테이블의 `set_updated_at()` 은 그대로 둔다(영향 범위 최소).

live 안전: 함수 CREATE OR REPLACE + 해당 테이블 트리거 교체만. 테이블 재작성·풀 락 없음
(migrate-lint expand-safe — DROP/RENAME/타입변경/NOT NULL 추가 없음). 롤백은 baseline
트리거로 원복.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0046_relationship_updated_at_if_changed"
down_revision: Union[str, None] = "0045_redteam_convergence_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- §18.8: DROP TRIGGER 는 ACCESS EXCLUSIVE 를 요구한다. 41분짜리 --full sync 와 겹치면
-- 마이그레이션이 배치 커밋 경계까지 대기하며 뒤따르는 writer 를 줄세운다 — 짧게 실패하고
-- 배포 재시도가 처리하게 한다(deploy-web 은 migrate 실패 시 ABORT + 재시도 경로 보유).
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE FUNCTION public.set_updated_at_if_changed() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- 제외 목록 = **그래프에 투영되지 않는 컬럼 전량**(§18.8 B-2/B-3):
    --   updated_at/last_validated_at : 타임스탬프 자체(rotation·backoff)
    --   positive_signals/negative_signals : 신호 카운터 — 엣지 속성(eprops)에 없다.
    --     신호 1건마다 반드시 +1 이므로 제외하지 않으면 이 트리거가 파이썬 측 조건화를
    --     매번 덮어써 신호 경로 churn(라이브 2h 기준 54%)이 그대로 남는다.
    --   source_run_id : 마지막 기록 run — 표시/투영 대상 아님(63개 run 으로 회전).
    -- 본 diff 가 updated_at 전진의 **단일 정본**이다(파이썬 측 중복 정책 금지 — B-2 도전 수용).
    IF (to_jsonb(NEW) - 'updated_at' - 'last_validated_at'
                      - 'positive_signals' - 'negative_signals' - 'source_run_id')
       IS DISTINCT FROM (to_jsonb(OLD) - 'updated_at' - 'last_validated_at'
                      - 'positive_signals' - 'negative_signals' - 'source_run_id') THEN
        NEW.updated_at = now();
    ELSE
        NEW.updated_at = OLD.updated_at;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_table_relationships_updated_at ON public.table_relationships;
CREATE TRIGGER trg_table_relationships_updated_at
    BEFORE UPDATE ON public.table_relationships
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at_if_changed();
"""

DOWNGRADE_SQL = r"""
DROP TRIGGER IF EXISTS trg_table_relationships_updated_at ON public.table_relationships;
CREATE TRIGGER trg_table_relationships_updated_at
    BEFORE UPDATE ON public.table_relationships
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
