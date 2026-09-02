"""2026-09-02 — datasource health 텔레메트리가 **한 행 때문에 통째로 유실되지 않는다**.

## 이 테스트가 잠그는 사고 (라이브 실측)

`insight` 사이클이 매번 남겨야 할 datasource health 가 로그만 남기고 사라졌다:

    datasource_health_persist_failed err=AmbiguousParameter — soft telemetry, cycle 계속

원인은 upsert SQL 의 한 줄이다. 같은 파라미터가 두 문맥에 쓰인다:

    CASE WHEN %(last_checked_at)s IS NULL          -- 타입 미상
         THEN NULL ELSE to_timestamp(%(last_checked_at)s) END   -- double precision

값이 float 이면 드라이버가 타입을 실어 보내 통과하지만, **`None` 이면 타입 없는 NULL** 이
가고 Postgres 가 추론에 실패한다(42P08). 그래서 **한 번도 체크되지 않은 datasource 가 섞인
사이클에서만** 터졌고 — 그 한 행이 batch 전체를 되돌려 health 가 통째로 유실됐다.

라이브 PG 로 직접 확인한 재현:

    SELECT CASE WHEN %(t)s IS NULL THEN NULL ELSE to_timestamp(%(t)s) END
      t=1756000000.0 → OK
      t=None         → AmbiguousParameter: could not determine data type of parameter $1
"""
from __future__ import annotations

import re

from modules import insight as I


def test_last_checked_at_placeholders_are_cast():
    """`last_checked_at` 자리표시자는 **전부** 명시 캐스트를 달고 있다.

    캐스트가 하나라도 빠지면 그 문맥에서 타입 추론이 다시 애매해진다.
    """
    sql = I._DS_HEALTH_UPSERT_SQL
    bare = re.findall(r"%\(last_checked_at\)s(?!\s*::)", sql)
    assert not bare, f"캐스트 없는 자리표시자 {len(bare)}개 — None 이 오면 42P08 로 batch 가 죽는다"


def test_every_cast_is_double_precision():
    """**모든** 자리표시자가 `double precision` 으로 캐스트된다.

    ⚠ 「어딘가에 `::double precision` 이 있다」만 보면, 한쪽만 다른 타입으로 바꾼 뮤턴트가
      그대로 통과한다(2026-09-02 뮤테이션 Q3 에서 실증). `to_timestamp` 은 epoch(초)를
      double precision 으로 받으므로 두 문맥의 타입이 **같아야** 추론이 애매해지지 않는다.
    """
    sql = I._DS_HEALTH_UPSERT_SQL
    casts = {c.strip() for c in re.findall(r"%\(last_checked_at\)s::([a-z ]+)", sql)}
    assert casts, "자리표시자에 캐스트가 하나도 없다"
    assert casts == {"double precision"}, f"타입이 갈린다: {casts!r}"


def test_other_named_params_unchanged():
    """다른 파라미터는 건드리지 않았다 — 이 수정의 범위는 한 컬럼이다."""
    sql = I._DS_HEALTH_UPSERT_SQL
    for name in ("scope_key", "label", "engine", "host", "port", "status",
                 "scan_outcome", "fail_count", "last_error_tag", "run_id"):
        assert f"%({name})s" in sql, f"{name} 자리표시자가 사라졌다"


def test_upsert_still_targets_conflict_on_scope_key():
    """멱등 upsert 계약(scope_key 충돌 시 갱신)이 유지된다."""
    sql = I._DS_HEALTH_UPSERT_SQL
    assert "ON CONFLICT (scope_key) DO UPDATE" in sql
