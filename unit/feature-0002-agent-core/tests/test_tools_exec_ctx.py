"""rel-selfheal 재검증 R-2: execute_sql 실행-시점 컨텍스트 스냅샷 단위 테스트.

1:N 라우터가 tool 종료 finally 에서 primary 컨텍스트로 복원한 뒤 대화 JOIN 학습이
ContextVar 를 읽으면, 라우팅된 SQL 에 primary 의 engine/DB/scope 가 오각인된다 —
학습은 실행 시점 스냅샷(get_last_execute_sql_context)을 읽는다. DB 연결 불요.
"""
from shared import config as cfg
from modules import tools as T


def test_snapshot_captures_routed_context_and_survives_restore():
    prev_ds = cfg.get_active_datasource()
    try:
        # 라우팅된 datasource 컨텍스트에서 스냅샷
        cfg.set_active_datasource("ds-secondary", engine="MSSQL", default_db="ProdDB")
        cfg.set_active_database("GameDB")
        T._snapshot_sql_exec_ctx()
        # primary 복원(라우터 finally 동작 모사) 후에도 스냅샷은 실행 시점 값 유지
        cfg.set_active_datasource("ds-primary", engine="mysql", default_db="maindb")
        ctx = T.get_last_execute_sql_context()
        assert ctx["scope_key"] == "ds-secondary"
        assert ctx["engine"] == "mssql"          # lower 정규화
        assert ctx["default_schema"] == "gamedb"  # set_active_database 의 lower 규약
    finally:
        cfg.set_active_database(None)
        cfg.set_active_datasource(prev_ds)


def test_snapshot_default_db_fallback_and_none_db():
    prev_ds = cfg.get_active_datasource()
    try:
        cfg.set_active_datasource("dsx", engine="mysql", default_db="SalesDB")
        cfg.set_active_database(None)
        T._snapshot_sql_exec_ctx()
        ctx = T.get_last_execute_sql_context()
        # active db 부재 시 default_db 폴백
        assert ctx["default_schema"] == "salesdb" and ctx["engine"] == "mysql"
    finally:
        cfg.set_active_datasource(prev_ds)
