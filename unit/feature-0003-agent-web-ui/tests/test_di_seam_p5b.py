"""feature-0012 P5b — DI seam 회귀 스위트 (Phase 1, DI_SEAM_BLUEPRINT §4.2).

auth DI seam(get_conn / get_current_account / get_optional_account / require_permission /
_AuthError + _auth_error_handler)의 응답 셰이프·status·body 를 legacy `_json_error` 와
byte-동치로 고정한다. 클러스터 마이그(Phase 2..7)가 이 계약을 깨면 여기서 적발된다.

핵심 단언:
- 401/403/500 body = {"error": <메시지>} (정확 문자열). HTTPException 의 {"detail":...} 회귀를
  탐지하기 위해 **"detail" 키 부재**를 명시 단언한다(블루프린트 R1).
- get_optional_account: 미인증·conn 실패·내부 예외 → None(절대 raise 금지).
- get_conn: _connect_memory 실패 → None yield(raise 금지) → required=500 / optional=None 분기 토대(§18.8 HIGH).
- get_current/get_optional 의 _get_authenticated_account(conn, request) **인자 순서** 가드(footgun, 적대 패널 HIGH-2).
- require_permission: 빈 perms → ValueError(footgun 가드, §18.8 LOW); message= 로 원본 403 메시지 보존.
- 파일럿 /api/llm/health(get_conn + inline auth): authed=probe / 미인증·conn실패=cheap read /
  **인증쿼리 raise → 500 전파**(legacy 동치, 적대 패널 HIGH-1 회귀 가드).
- auth deps 의 라우트 소비 계약(401/403/500)을 throwaway mini-app 으로 end-to-end 검증(route-parity 무영향, 패널 MEDIUM #6).
- 예외 핸들러 등록: production app TestClient 로 _AuthError→{"error"} 직렬화 확인(route-parity 미탐지 영역).

make test(agent 이미지, --no-deps): DB/네트워크 없이 monkeypatch + dependency_overrides 로 실행.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import app as appmod


# ─────────────────────────────────────────────────────────────────────────────
# fakes / helpers
# ─────────────────────────────────────────────────────────────────────────────
class _Req:
    """_get_authenticated_account 가 보는 최소 request — cookies 만 사용(미인증=빈 dict)."""

    def __init__(self, cookies: dict | None = None) -> None:
        self.cookies = cookies or {}


_SENTINEL_CONN = object()  # non-None conn 자리표시(.cookies 없음 → 인자순서 가드에 활용)


def _override_conn(value):
    """production app 의 get_conn 의존성을 주어진 값으로 override(benign conn 또는 None)."""
    appmod.app.dependency_overrides[appmod.get_conn] = lambda: value


def _mini_route_app(dep):
    """auth dep 하나를 라우트에 소비시키는 throwaway FastAPI app(_AuthError 핸들러 등록).

    production 라우트를 건드리지 않고(=route-parity 무영향) get_current_account/require_permission
    의 'Depends 로 라우트에서 소비될 때' 의 401/403/500 계약을 end-to-end 로 검증하기 위함."""
    from fastapi import Depends, FastAPI

    m = FastAPI()
    m.add_exception_handler(appmod._AuthError, appmod._auth_error_handler)

    @m.get("/probe")
    def _probe(account=Depends(dep)):  # noqa: ANN001
        return {"id": account.get("id")}

    return m


def _mini_client(m):
    from fastapi.testclient import TestClient

    return TestClient(m, base_url="http://localhost", raise_server_exceptions=True)


# ─────────────────────────────────────────────────────────────────────────────
# get_conn — conn 실패 시 None yield (§18.8 HIGH 토대)
# ─────────────────────────────────────────────────────────────────────────────
def test_get_conn_yields_conn_and_closes(monkeypatch):
    closed = []

    class _Conn:
        autocommit = True

        def rollback(self):  # 정상경로 미발화(autocommit=True)
            raise AssertionError("autocommit=True 인데 rollback 호출됨")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(appmod, "_connect_memory", lambda: _Conn())
    gen = appmod.get_conn()
    conn = next(gen)
    assert isinstance(conn, _Conn)
    with pytest.raises(StopIteration):
        next(gen)  # teardown(finally) 발화 → close
    assert closed == [True]


def test_get_conn_rolls_back_uncommitted_on_teardown(monkeypatch):
    events = []

    class _Conn:
        autocommit = False  # 에러 경로(autocommit 미복원) 시뮬레이션

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    monkeypatch.setattr(appmod, "_connect_memory", lambda: _Conn())
    gen = appmod.get_conn()
    next(gen)
    with pytest.raises(StopIteration):
        next(gen)
    assert events == ["rollback", "close"]  # 미커밋 변경 되돌린 뒤 close


def test_get_conn_yields_none_on_connect_failure(monkeypatch):
    def _boom():
        raise RuntimeError("no db")

    monkeypatch.setattr(appmod, "_connect_memory", _boom)
    gen = appmod.get_conn()
    conn = next(gen)
    assert conn is None  # raise 가 아니라 None yield
    with pytest.raises(StopIteration):
        next(gen)  # finally: conn is None → close 미시도, 오류 없음


# ─────────────────────────────────────────────────────────────────────────────
# get_current_account — 401(미인증) / 500(conn 실패), _require_account byte-동치
# ─────────────────────────────────────────────────────────────────────────────
def test_get_current_account_unauth_raises_401(monkeypatch):
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)
    with pytest.raises(appmod._AuthError) as ei:
        appmod.get_current_account(_Req(), conn=_SENTINEL_CONN)
    assert ei.value.status_code == 401
    assert ei.value.message == "로그인이 필요합니다."


def test_get_current_account_conn_none_raises_500():
    with pytest.raises(appmod._AuthError) as ei:
        appmod.get_current_account(_Req(), conn=None)
    assert ei.value.status_code == 500
    assert ei.value.message == "db connection failed"  # legacy 121 사이트 byte-동치


def test_get_current_account_authed_returns_account(monkeypatch):
    acct = {"id": 1, "permissions": {}}
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: acct)
    assert appmod.get_current_account(_Req(), conn=_SENTINEL_CONN) is acct


def test_get_current_account_calls_auth_with_conn_then_request(monkeypatch):
    """_get_authenticated_account(conn, request) 인자 순서 가드 — swap 회귀 탐지(footgun, app.py docstring; 패널 HIGH-2)."""

    def _spy(a, b):
        assert not hasattr(a, "cookies"), "위치1 은 conn 이어야 함(request 가 전달됨 — 순서 swap)"
        assert hasattr(b, "cookies"), "위치2 는 request(.cookies) 여야 함(conn 이 전달됨 — 순서 swap)"
        return {"id": 1}

    monkeypatch.setattr(appmod, "_get_authenticated_account", _spy)
    req = _Req(cookies={appmod.SESSION_COOKIE: "x"})
    assert appmod.get_current_account(req, conn=_SENTINEL_CONN)["id"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# get_optional_account — 절대 raise 금지(미인증/conn실패/내부예외 → None)
# ─────────────────────────────────────────────────────────────────────────────
def test_get_optional_account_unauth_returns_none(monkeypatch):
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)
    assert appmod.get_optional_account(_Req(), conn=_SENTINEL_CONN) is None


def test_get_optional_account_conn_none_returns_none():
    assert appmod.get_optional_account(_Req(), conn=None) is None  # graceful, no raise


def test_get_optional_account_swallows_internal_exception(monkeypatch):
    def _boom(conn, request):
        raise RuntimeError("LastSeen UPDATE 실패")

    monkeypatch.setattr(appmod, "_get_authenticated_account", _boom)
    assert appmod.get_optional_account(_Req(), conn=_SENTINEL_CONN) is None  # fail-soft 보존


def test_get_optional_account_calls_auth_with_conn_then_request(monkeypatch):
    """인자 순서 가드(패널 HIGH-2) — get_optional_account 도 (conn, request) 순서 보존."""

    def _spy(a, b):
        assert not hasattr(a, "cookies")
        assert hasattr(b, "cookies")
        return {"id": 2}

    monkeypatch.setattr(appmod, "_get_authenticated_account", _spy)
    req = _Req(cookies={appmod.SESSION_COOKIE: "x"})
    assert appmod.get_optional_account(req, conn=_SENTINEL_CONN)["id"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# require_permission — 403(원본 message 보존) / 통과 / 빈 perms 가드(§18.8 LOW)
# ─────────────────────────────────────────────────────────────────────────────
def test_require_permission_denied_raises_403_with_original_message():
    dep = appmod.require_permission(
        "admin.console.manage", message="관리 콘솔 수정 권한이 필요합니다."
    )
    acct = {"id": 1, "permissions": {"admin.console.manage": False}}
    with pytest.raises(appmod._AuthError) as ei:
        dep(account=acct)
    assert ei.value.status_code == 403
    assert ei.value.message == "관리 콘솔 수정 권한이 필요합니다."  # 60종 메시지 byte 보존


def test_require_permission_granted_returns_account():
    dep = appmod.require_permission("admin.console.manage")
    acct = {"id": 1, "permissions": {"admin.console.manage": True}}
    assert dep(account=acct) is acct


def test_require_permission_default_message():
    dep = appmod.require_permission("some.perm")
    acct = {"id": 1, "permissions": {}}
    with pytest.raises(appmod._AuthError) as ei:
        dep(account=acct)
    assert ei.value.status_code == 403
    assert ei.value.message == "권한이 없습니다."  # 기본값(generic 9 사이트)


def test_require_permission_empty_perms_is_guarded():
    with pytest.raises(ValueError):
        appmod.require_permission()  # 무인자 footgun → 데코레이션 시점 차단


def test_require_permission_multiple_perms_are_anded():
    dep = appmod.require_permission("a", "b")
    assert dep(account={"id": 1, "permissions": {"a": True, "b": True}})["id"] == 1
    with pytest.raises(appmod._AuthError):
        dep(account={"id": 1, "permissions": {"a": True, "b": False}})


# ─────────────────────────────────────────────────────────────────────────────
# _auth_error_handler — {"error": msg}+status, "detail" 키 부재(HTTPException 회귀 가드 R1)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "message,status",
    [
        ("로그인이 필요합니다.", 401),
        ("관리 콘솔 수정 권한이 필요합니다.", 403),
        ("db connection failed", 500),
    ],
)
def test_auth_error_handler_shape(message, status):
    resp = asyncio.run(appmod._auth_error_handler(_Req(), appmod._AuthError(message, status)))
    assert resp.status_code == status
    body = json.loads(resp.body)
    assert body == {"error": message}
    assert "detail" not in body  # HTTPException({"detail":...}) 회귀 탐지


# ─────────────────────────────────────────────────────────────────────────────
# 파일럿 /api/llm/health (get_conn + inline auth) — end-to-end TestClient (production app)
# ─────────────────────────────────────────────────────────────────────────────
def test_llm_health_authed_probes(client, monkeypatch):
    import modules.llm_provider_health as llmh

    captured = {}

    def _probe(*, timeout_sec: int = 8, force: bool = False):
        captured["force"] = force
        return {"state": "ok", "probed": True}

    monkeypatch.setattr(llmh, "probe_provider", _probe)
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: {"id": 1, "permissions": {}})
    _override_conn(object())  # benign conn (get_conn 성공)
    resp = client.get("/api/llm/health")
    assert resp.status_code == 200
    assert resp.json() == {"state": "ok", "probed": True}
    assert captured["force"] is False  # force 미지정 → False


def test_llm_health_force_param_passthrough(client, monkeypatch):
    import modules.llm_provider_health as llmh

    captured = {}
    monkeypatch.setattr(
        llmh,
        "probe_provider",
        lambda *, timeout_sec=8, force=False: captured.update(force=force) or {"state": "ok"},
    )
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: {"id": 1, "permissions": {}})
    _override_conn(object())
    resp = client.get("/api/llm/health?force=1")
    assert resp.status_code == 200
    assert captured["force"] is True  # force=1 → bool(1)=True 전달


def test_llm_health_unauthenticated_cheap_read_no_probe(client, monkeypatch):
    import modules.llm_provider_health as llmh

    monkeypatch.setattr(appmod, "_read_llm_provider_status", lambda: {"state": "cheap"})
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)

    def _must_not_probe(*a, **k):
        raise AssertionError("미인증 경로는 probe 를 트리거하면 안 된다")

    monkeypatch.setattr(llmh, "probe_provider", _must_not_probe)
    _override_conn(object())
    resp = client.get("/api/llm/health")
    assert resp.status_code == 200
    assert resp.json() == {"state": "cheap"}  # probe 없이 마지막 알려진 상태


def test_llm_health_conn_failure_cheap_read(client, monkeypatch):
    """§18.8 HIGH end-to-end: _connect_memory 실패 → get_conn None → 파일럿 'if conn is None' →
    cheap read(legacy get_llm_health 의 conn-acquire-fail 200 동치). deps override 없이 실 get_conn 경로를 탄다."""

    def _boom():
        raise RuntimeError("no db")

    monkeypatch.setattr(appmod, "_connect_memory", _boom)
    monkeypatch.setattr(appmod, "_read_llm_provider_status", lambda: {"state": "connfail"})
    resp = client.get("/api/llm/health")
    assert resp.status_code == 200
    assert resp.json() == {"state": "connfail"}  # 500 회귀 없음 — fail-soft 보존


def test_llm_health_auth_query_raises_propagates_500(client_capture_errors, monkeypatch):
    """legacy 동치(적대 패널 HIGH-1 회귀 가드): conn 은 열렸으나 인증 쿼리가 raise → 예외 전파(→500).

    legacy get_llm_health 는 _get_authenticated_account 를 직접(except 없이) 호출 → 전파 → Starlette
    ServerErrorMiddleware 의 generic 500(plain text "Internal Server Error"). get_optional_account 로
    위임했다면 except→None 으로 삼켜 200 cheap-read 로 변형됐을 경로다. inline auth 유지로 500 전파를 고정한다."""

    def _raise(conn, request):
        raise RuntimeError("auth query exploded")

    monkeypatch.setattr(appmod, "_get_authenticated_account", _raise)
    monkeypatch.setattr(appmod, "_read_llm_provider_status", lambda: {"state": "MUST-NOT-APPEAR"})
    _override_conn(object())
    resp = client_capture_errors.get("/api/llm/health")
    assert resp.status_code == 500  # 200 으로 강등되지 않음(핵심 — legacy 와 동일하게 전파)
    assert resp.text == "Internal Server Error"  # Starlette generic 500(plain text) — legacy byte-동치
    assert "MUST-NOT-APPEAR" not in resp.text  # cheap read 로 강등되지 않음


def test_auth_error_handler_registered_on_app(client):
    """등록된 _auth_error_handler 가 production app 의 전체 미들웨어(TrustedHost/CORS)를 통과해
    {"error":msg}+status 로 직렬화함을 검증 — route-parity 미탐지 영역(블루프린트 §4.2 #2).
    get_conn 을 _AuthError raise 로 override 해(인위적) 등록된 핸들러의 직렬화를 확인."""

    def _raise():
        raise appmod._AuthError("teapot", 418)

    appmod.app.dependency_overrides[appmod.get_conn] = _raise
    resp = client.get("/api/llm/health")
    assert resp.status_code == 418
    body = resp.json()
    assert body == {"error": "teapot"}
    assert "detail" not in body  # Starlette generic({"detail":...}) 우회 없음


# ─────────────────────────────────────────────────────────────────────────────
# auth deps 의 라우트 소비 계약 — throwaway mini-app end-to-end (패널 MEDIUM #6)
# production 라우트 미변경(route-parity 무영향) 으로 Phase 2 마이그 계약을 미리 고정.
# ─────────────────────────────────────────────────────────────────────────────
def test_route_consumes_get_current_account_401(monkeypatch):
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)
    m = _mini_route_app(appmod.get_current_account)
    m.dependency_overrides[appmod.get_conn] = lambda: object()
    resp = _mini_client(m).get("/probe")
    assert resp.status_code == 401
    body = resp.json()
    assert body == {"error": "로그인이 필요합니다."}
    assert "detail" not in body


def test_route_consumes_get_current_account_500_on_conn_fail():
    m = _mini_route_app(appmod.get_current_account)
    m.dependency_overrides[appmod.get_conn] = lambda: None  # conn 획득 실패
    resp = _mini_client(m).get("/probe")
    assert resp.status_code == 500
    body = resp.json()
    assert body == {"error": "db connection failed"}
    assert "detail" not in body


def test_route_consumes_get_current_account_200(monkeypatch):
    monkeypatch.setattr(
        appmod, "_get_authenticated_account", lambda conn, request: {"id": 7, "permissions": {}}
    )
    m = _mini_route_app(appmod.get_current_account)
    m.dependency_overrides[appmod.get_conn] = lambda: object()
    resp = _mini_client(m).get("/probe")
    assert resp.status_code == 200
    assert resp.json() == {"id": 7}


def test_route_consumes_require_permission_403():
    dep = appmod.require_permission("kb.sample.curate", message="샘플 큐레이션 권한이 필요합니다.")
    m = _mini_route_app(dep)
    m.dependency_overrides[appmod.get_current_account] = lambda: {
        "id": 1,
        "permissions": {"kb.sample.curate": False},
    }
    resp = _mini_client(m).get("/probe")
    assert resp.status_code == 403
    body = resp.json()
    assert body == {"error": "샘플 큐레이션 권한이 필요합니다."}  # message= 보존
    assert "detail" not in body


def test_route_consumes_require_permission_200():
    dep = appmod.require_permission("kb.sample.curate")
    m = _mini_route_app(dep)
    m.dependency_overrides[appmod.get_current_account] = lambda: {
        "id": 9,
        "permissions": {"kb.sample.curate": True},
    }
    resp = _mini_client(m).get("/probe")
    assert resp.status_code == 200
    assert resp.json() == {"id": 9}


def test_route_consumes_get_optional_account_anonymous_200(monkeypatch):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)
    m = FastAPI()
    m.add_exception_handler(appmod._AuthError, appmod._auth_error_handler)

    @m.get("/probe")
    def _probe(account=Depends(appmod.get_optional_account)):  # noqa: ANN001
        return {"anon": account is None}

    m.dependency_overrides[appmod.get_conn] = lambda: object()
    resp = TestClient(m, base_url="http://localhost").get("/probe")
    assert resp.status_code == 200
    assert resp.json() == {"anon": True}  # 익명 허용, 401 없음
