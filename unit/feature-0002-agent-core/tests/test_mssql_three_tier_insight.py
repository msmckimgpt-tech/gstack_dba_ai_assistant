"""TASK-0223 — MSSQL database.schema.table 3계층 insight fact_key 정합 테스트.

MSSQL 은 database.schema.table 3계층이라 insight fact_key suffix 에 database(catalog)를 포함해야
datasource 내 여러 DB 가 구분된다. MySQL(schema==database)은 종전 2계층 유지.

합격선:
- MySQL(active_database 미설정): 기존 2계층 fact_key 와 byte-identical (회귀 0).
- MSSQL(active_database 설정): 3계층 suffix + object_key 에 database 포함(cross-DB 유일성).
- grounding grouping(_insight_object_group)이 MySQL=schema, MSSQL=database.schema 로 정합.

실 DB 없이 ContextVar + 순수 함수로 검증.
"""
from modules import config as cfg
from modules.utils import _infer_rag_object_from_fact
from agent_core import _insight_object_group


def _reset_ds():
    cfg.set_active_datasource(None)


# ──────────────────────────────────────────────────────────────────────────
# 1. ds_object_suffix — 2계층(MySQL) vs 3계층(MSSQL)
# ──────────────────────────────────────────────────────────────────────────
def test_ds_object_suffix_mysql_two_tier():
    """active_database 미설정 → 2계층(기존과 동치)."""
    _reset_ds()
    assert cfg.ds_object_suffix("dbgame") == "dbgame"
    assert cfg.ds_object_suffix("dbgame", "item") == "dbgame.item"


def test_ds_object_suffix_mssql_three_tier():
    """active_database 설정 → database 를 최상위로 포함한 3계층."""
    _reset_ds()
    cfg.set_active_datasource("mssql-abc", engine="mssql")
    cfg.set_active_database("dk_data_release")
    try:
        assert cfg.ds_object_suffix("dbo") == "dk_data_release.dbo"
        assert cfg.ds_object_suffix("dbo", "QuestInfo") == "dk_data_release.dbo.QuestInfo"
    finally:
        _reset_ds()


def test_ds_object_suffix_explicit_database_arg():
    """database 명시 인자가 ContextVar 보다 우선(테스트/명시 호출용)."""
    _reset_ds()
    assert cfg.ds_object_suffix("dbo", "T", database="GameLog_100") == "gamelog_100.dbo.T"


def test_set_active_datasource_resets_database():
    """datasource 전환 시 active_database 가 None 으로 리셋(이전 DB 누출 차단)."""
    cfg.set_active_datasource("mssql-abc", engine="mssql")
    cfg.set_active_database("dk_data_release")
    assert cfg.get_active_database() == "dk_data_release"
    cfg.set_active_datasource("mysql-xyz", engine="mysql")  # 전환
    assert cfg.get_active_database() is None
    _reset_ds()


def test_ds_fact_key_signature_unchanged():
    """ds_fact_key 시그니처 불변 — suffix 만 받아 합성(3자 정합 보존)."""
    _reset_ds()
    cfg.set_active_datasource("mssql-abc", engine="mssql")
    cfg.set_active_database("dk_data_release")
    try:
        key = cfg.ds_fact_key("table_insight", cfg.ds_object_suffix("dbo", "QuestInfo"))
        assert key == "table_insight:ds:mssql-abc:dk_data_release.dbo.QuestInfo"
    finally:
        _reset_ds()


# ──────────────────────────────────────────────────────────────────────────
# 2. _infer_rag_object_from_fact — 3계층 파싱 + object_key database 포함
# ──────────────────────────────────────────────────────────────────────────
def test_infer_mysql_two_tier_unchanged():
    """MySQL 2계층 — schema/table 추출, object_key 기존 형식(회귀 0)."""
    ot, ok, sn, tn, cn, dk = _infer_rag_object_from_fact("table_insight:dbgame.item", "")
    assert ot == "table"
    assert ok == "dbgame.item"
    assert sn == "dbgame"
    assert tn == "item"


def test_infer_mssql_three_tier_table():
    """MSSQL 3계층 — schema_name=schema, table_name=table, object_key 에 database 접두."""
    ot, ok, sn, tn, cn, dk = _infer_rag_object_from_fact(
        "table_insight:ds:mssql-abc:dk_data_release.dbo.QuestInfo", ""
    )
    assert ot == "table"
    assert sn == "dbo"          # schema 단위 유지(_build_insight_object_maps/grounding 정합)
    assert tn == "QuestInfo"    # _sanitize_ident_part 는 대소문자 보존
    assert dk == "mssql-abc"    # datasource_key 분리
    # object_key = {datasource_key}:{database}.{schema}.{table} (cross-ds + cross-db 유일)
    assert ok == "mssql-abc:dk_data_release.dbo.QuestInfo"


def test_infer_mssql_three_tier_schema():
    """MSSQL 3계층 schema 키 — database.schema."""
    ot, ok, sn, tn, cn, dk = _infer_rag_object_from_fact(
        "schema_insight:ds:mssql-abc:dk_data_release.dbo", ""
    )
    assert ot == "schema"
    assert sn == "dbo"
    assert dk == "mssql-abc"


def test_infer_mssql_cross_db_object_key_unique():
    """같은 dbo.QuestInfo 라도 database 가 다르면 object_key 가 유일(read-back livelock 방지 근거)."""
    _, ok_a, _, _, _, _ = _infer_rag_object_from_fact(
        "table_insight:ds:mssql-abc:db_a.dbo.QuestInfo", ""
    )
    _, ok_b, _, _, _, _ = _infer_rag_object_from_fact(
        "table_insight:ds:mssql-abc:db_b.dbo.QuestInfo", ""
    )
    assert ok_a != ok_b  # database 가 object_key 에 포함되어 충돌 없음


# ──────────────────────────────────────────────────────────────────────────
# 3. _insight_object_group — grounding grouping (MySQL=schema, MSSQL=database.schema)
# ──────────────────────────────────────────────────────────────────────────
def test_insight_object_group_mysql():
    """2계층 table suffix → schema (기존 name.find('.') 결과와 동일)."""
    assert _insight_object_group("dbgame.item") == "dbgame"


def test_insight_object_group_mssql():
    """3계층 table suffix → database.schema (schema_insight suffix 와 동일 단위)."""
    assert _insight_object_group("dk_data_release.dbo.QuestInfo") == "dk_data_release.dbo"


def test_insight_object_group_no_dot():
    """점 없는 입력 → 빈 문자열(방어)."""
    assert _insight_object_group("foo") == ""


def test_insight_object_group_schema_table_consistency():
    """table grouping 키와 schema_insight suffix 가 양쪽 엔진에서 일치 → desc 매칭 정합."""
    # MySQL: schema_insight suffix='dbgame', table group='dbgame'
    assert _insight_object_group("dbgame.item") == "dbgame"
    # MSSQL: schema_insight suffix='dk_data_release.dbo', table group='dk_data_release.dbo'
    assert _insight_object_group("dk_data_release.dbo.QuestInfo") == "dk_data_release.dbo"
