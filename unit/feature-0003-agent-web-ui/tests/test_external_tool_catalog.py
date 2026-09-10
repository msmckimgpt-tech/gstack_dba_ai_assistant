"""라이브 tool 404의 전송 계약과 제품 범위 검증."""
import asyncio
import contextlib
import json

import agent_core
import app
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules import tools as T
from routers import ai_tools as A
from external_tool_catalog import RESTRICTED_TOOLS, render_guidance


@pytest.fixture
def surface(monkeypatch):
    task = {"task_id": "test-task", "product_id": 1, "conversation_id": "test-conv"}
    calls = []
    monkeypatch.setattr(A, "_load_task", lambda *a: task)
    monkeypatch.setattr(A, "_conversation_access_denied", lambda *a: None)
    monkeypatch.setattr(A, "_kb_product_access_denied", lambda *a: None)
    monkeypatch.setattr(A, "_pg", lambda: None)
    monkeypatch.setattr(A._ledger, "check_limits", lambda *a, **kw: None)
    monkeypatch.setattr(A._ledger, "record", lambda *a, **kw: None)
    monkeypatch.setattr(A, "_renew_claim_lease", lambda *a: None)
    monkeypatch.setattr(A, "_record_bridge_step", lambda *a, **kw: None)
    monkeypatch.setattr(A._authz, "allowed_datasource_labels", lambda *a: ["test-ds"])
    @contextlib.contextmanager
    def scope(*a, **kw):
        yield "scoped-connection"
    monkeypatch.setattr(A._authz, "scoped_execution", scope)
    def execute(conn, name, args):
        calls.append((conn, name, dict(args)))
        return "scoped result"
    monkeypatch.setattr(T, "execute_tool", execute)
    monkeypatch.setattr(A, "_sql_enabled", lambda: True)
    api = FastAPI()
    api.include_router(A.router)
    api.dependency_overrides[A.require_ai_token] = lambda: {"account": {"id": 1, "username": "test"}}
    api.dependency_overrides[app.get_conn] = lambda: None
    with TestClient(api) as client:
        yield client, calls


def test_catalog_covers_all_core_tools_without_automatically_exposing_them(surface):
    client, _ = surface
    response = client.post('/api/ai/tools/get_tool_catalog', json={"task_id": "test-task"})
    assert response.status_code == 200
    catalog = response.json()["tool_catalog"]
    exposed = {t['name'] for t in catalog['tools']}
    static = {t['function']['name'] for t in T.TOOL_DEFINITIONS_FULL}
    assert static <= exposed | set(catalog['restricted'])
    assert set(T._TOOL_HANDLERS) == exposed | set(catalog['restricted'])
    assert exposed == A.EXPOSED_TOOLS
    assert not exposed & set(RESTRICTED_TOOLS)
    specs = {t['name']: t['parameters']['properties'] for t in catalog['tools']}
    assert {'database', 'offset', 'datasource'} <= set(specs['describe_routine'])
    assert 'confirm_heavy' in specs['execute_sql']


@pytest.mark.parametrize('tool,args', [
    ('search_routines', {'keyword': 'login', 'database': 'Allowed'}),
    ('describe_routine', {'schema_name': 'dbo', 'routine_name': 'login', 'database': 'Allowed', 'offset': 100}),
    ('search_db_objects', {'object_role': 'view'}),
    ('describe_db_object', {'object_role': 'view', 'object_name': 'v', 'database': 'Allowed'}),
    ('explain_query', {'sql': 'SELECT 1'}),
])
def test_previously_missing_tool_reaches_scoped_dispatch(surface, tool, args):
    client, calls = surface
    response = client.post('/api/ai/tools/' + tool, json={'task_id': 'test-task', 'arguments': args})
    assert response.status_code == 200, response.text
    assert calls == [('scoped-connection', tool, args)]
    assert 'UNTRUSTED-DATA' in response.json()['result']


@pytest.mark.parametrize('check', ['_conversation_access_denied', '_kb_product_access_denied'])
@pytest.mark.parametrize('tool', ['search_routines', 'get_tool_catalog'])
def test_revoked_access_never_reaches_tools(surface, monkeypatch, check, tool):
    client, calls = surface
    monkeypatch.setattr(A, check, lambda *a: A._json_err(403, 'revoked'))
    response = client.post('/api/ai/tools/' + tool, json={'task_id': 'test-task', 'arguments': {}})
    assert response.status_code == 403
    assert not calls


def test_disabled_sql_is_truthfully_advertised_and_blocked(surface, monkeypatch):
    client, calls = surface
    monkeypatch.setattr(A, '_sql_enabled', lambda: False)
    cat = client.post('/api/ai/tools/get_tool_catalog', json={'task_id': 'test-task'}).json()['tool_catalog']
    assert next(t for t in cat['tools'] if t['name'] == 'execute_sql')['enabled'] is False
    assert client.post('/api/ai/tools/execute_sql', json={'task_id': 'test-task'}).status_code == 403
    assert not calls


def test_internal_attachment_tool_returns_supported_alternative(surface):
    client, calls = surface
    response = client.post('/api/ai/tools/update_attachment', json={'task_id': 'test-task'})
    assert response.status_code == 404
    assert 'attachment-edit' in response.json()['detail']
    assert 'submit_answer' in response.json()['detail']
    assert 'search_routines' in response.json()['available_tools']
    assert not calls


def test_unknown_datasource_is_denied_before_dispatch(surface):
    client, calls = surface
    response = client.post('/api/ai/tools/search_routines', json={'task_id': 'test-task', 'arguments': {'datasource': 'other'}})
    assert response.status_code == 403
    assert not calls


def test_current_catalog_reaches_old_runner_system_channel(surface, monkeypatch):
    monkeypatch.setattr(agent_core, 'compose_system_prompt', lambda *a, **kw: 'operator rules')
    prompt = A._bridge_system_prompt(None, product_id=1, role_id=None, account_id=1, product_mode='pinned', conversation_id='test')
    assert prompt.startswith('operator rules')
    assert '/api/ai/tools/search_routines' in prompt
    assert 'source_attachment_id' in prompt and 'get_tool_catalog' in prompt
    assert 'DB_NAME()' in prompt and '차단 유지' in prompt
