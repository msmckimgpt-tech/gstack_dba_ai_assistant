"""메타데이터 조회 확대 전에 제품 경계와 읽기 전용 검증을 고정한다."""
import pytest
from modules import tools as T, dialects as D
import shared.config as cfg


@pytest.fixture(autouse=True)
def isolate():
    allow = T._ACTIVE_SCHEMA_ALLOWLIST.set(None)
    display = T._ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.set(None)
    previous = (cfg.get_active_datasource(), cfg.get_active_datasource_engine(), cfg._ACTIVE_DEFAULT_DB.get())
    cfg.set_active_datasource(None)
    try:
        yield
    finally:
        T._ACTIVE_SCHEMA_ALLOWLIST.reset(allow)
        T._ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.reset(display)
        cfg.set_active_datasource(previous[0], engine=previous[1], default_db=previous[2])


@pytest.mark.parametrize('name,args,sql_fragment', [
    ('search_tables', {'keyword':'login'}, "t.TABLE_SCHEMA = 'Allowed'"),
    ('search_routines', {'keyword':'login'}, "ROUTINE_SCHEMA = 'Allowed'"),
    ('search_db_objects', {'object_role':'view'}, "TABLE_SCHEMA = 'Allowed'"),
])
@pytest.mark.parametrize('schema', [None, ' ', '`'])
def test_mysql_search_is_scoped_before_query_and_limit(monkeypatch, name, args, sql_fragment, schema):
    args = {**args, 'schema_name': schema} if schema is not None else args
    T.set_active_schema_allowlist(['Allowed'])
    queries = []
    def raw(conn, sql):
        queries.append(sql)
        if 'information_schema.schemata' in sql.lower():
            return [('rows', [], [('Allowed',), ('Other',)])], None
        assert sql_fragment in sql, sql
        return [('rows', [], [])], None
    monkeypatch.setattr(T, '_raw_execute_sql', raw)
    result = T._TOOL_HANDLERS[name](None, args)
    assert queries and 'Other' not in result


@pytest.mark.parametrize('name,args', [('search_tables',{'keyword':'x'}),('search_routines',{}),('search_db_objects',{})])
def test_empty_allowlist_performs_no_query(monkeypatch, name, args):
    T.set_active_schema_allowlist([])
    monkeypatch.setattr(T, '_raw_execute_sql', lambda *a: pytest.fail('empty scope queried'))
    assert '빈 접근목록' in T._TOOL_HANDLERS[name](None,args)


@pytest.mark.parametrize('sql', ['SET SHOWPLAN_ALL OFF; DELETE FROM Allowed.dbo.T', 'DELETE FROM Allowed.dbo.T', 'SELECT 1; SELECT 2', 'SELECT DB_NAME()'])
def test_explain_rejects_batch_writes_and_forbidden_functions_before_execution(monkeypatch, sql):
    cfg.set_active_datasource('test',engine='mssql',default_db='Allowed')
    T.set_active_schema_allowlist(['Allowed'])
    monkeypatch.setattr(T, '_raw_execute_sql', lambda *a: pytest.fail('unsafe SQL executed'))
    assert '보안 정책상 차단' in T._tool_explain_query(None, {'sql':sql})


def test_agent_job_keyword_uses_same_database_filter_as_returned_steps():
    sql = D.MSSQLDialect()._agent_jobs_sql(name='',keyword='needle',schema='Allowed',allow_dbs=['allowed'])
    assert "LOWER(k.database_name) IN ('allowed')" in sql
    assert "LOWER(k.database_name) = LOWER('Allowed')" in sql


def test_agent_job_alias_change_never_rewrites_database_literals():
    sql = D.MSSQLDialect()._agent_jobs_sql(name='', keyword='needle',schema='st.foo',allow_dbs=['st.foo'])
    assert "LOWER(k.database_name) IN ('st.foo')" in sql
    assert "LOWER(k.database_name) = LOWER('st.foo')" in sql
    assert "'k.foo'" not in sql
