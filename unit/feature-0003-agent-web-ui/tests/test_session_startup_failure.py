"""Session storage unavailability is not a logged-out result."""
import json
from unittest.mock import Mock

from starlette.requests import Request
import app as appmod
from routers.system import get_session


def request():
    return Request({"type": "http", "method": "GET", "path": "/api/session", "headers": []})


def test_session_connection_failure_is_retryable_and_redacted(monkeypatch):
    monkeypatch.setattr(appmod, "_is_local_llm_available", lambda: False)
    monkeypatch.setattr(appmod, "_connect_memory", Mock(side_effect=RuntimeError("private-database-credential")))
    result = get_session(request())
    assert result.status_code == 503
    body = json.loads(result.body)
    assert set(body) == {"error"}
    assert "private-database-credential" not in result.body.decode()
    assert "set-cookie" not in result.headers


def test_real_signed_out_session_remains_minimal(monkeypatch):
    conn = Mock()
    monkeypatch.setattr(appmod, "_is_local_llm_available", lambda: False)
    monkeypatch.setattr(appmod, "_connect_memory", lambda: conn)
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda *_: None)
    result = get_session(request())
    assert result.status_code == 200
    assert json.loads(result.body) == {"authenticated": False}
    conn.close.assert_called_once_with()
