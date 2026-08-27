"""feature-0041 — HTTP 어댑터 **동작** 검증 (문자열 검사가 아닌 실행).

## 왜 이 파일이 따로 있는가

기존 어댑터 테스트는 소스에 특정 문자열이 있는지만 봤다. codex 2차 리뷰가 정확히 그 점을
찔렀다 — "구현이 실행 시 전부 `no_authorization` 을 반환해도 통과할 수 있다". 실제로 이번
cycle 에서 SDK 세대 교체(`ctx.headers` ↔ `ctx.request_context.request.headers`)가 있었는데,
그건 문자열 검사로는 한쪽 세대의 조용한 오작동을 절대 못 잡는다.

`mcp` SDK 없이도 돌도록 **가짜 SDK 모듈을 주입**하고 어댑터를 실제로 import 해 함수를 부른다
(로컬 pytest 에 mcp 가 없다고 skip 하면 그거야말로 vacuous pass 다).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

import pytest

_HERE = os.path.dirname(__file__)
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src", "external_tool_mcp_http.py"))

_BASE_ENV = {
    "EXT_TOOL_API_BASE_URL": "https://web-a:8000,https://web-b:8000",
    "EXT_TOOL_UPSTREAM_TLS_SERVER_NAME": "mysql-ai.company.local",
    "EXT_TOOL_UPSTREAM_HOST_HEADER": "mysql-ai.company.local",
    "EXT_TOOL_HTTP_BIND": "127.0.0.1",
}


def _fake_sdk(generation: int) -> dict:
    """v1/v2 SDK 를 흉내 낸다. 어댑터는 v2 를 먼저 시도하므로, v1 을 강제하려면
    v2 모듈을 import 불가 상태로 둬야 한다."""

    class _Ctx:  # 도구 시그니처 주석용 — 인스턴스는 테스트가 직접 만든다
        pass

    class _Server:
        def __init__(self, name, **kw):
            self.name = name
            self.kw = kw
            self.tools: dict = {}

        def tool(self, *a, **kw):
            def deco(fn):
                self.tools[fn.__name__] = fn
                return fn
            return deco

        def add_tool(self, fn, name=None, description=None, **kw):
            self.tools[name or fn.__name__] = fn

        def run(self, *a, **kw):  # pragma: no cover — 테스트는 기동하지 않는다
            raise AssertionError("테스트가 서버를 기동해서는 안 된다")

        # v1 계열 가드(streamable-http 지원 여부)를 통과시키기 위한 표식
        async def run_streamable_http_async(self, **kw):  # pragma: no cover
            raise AssertionError

    mods = {}
    pkg = types.ModuleType("mcp"); pkg.__path__ = []
    server = types.ModuleType("mcp.server"); server.__path__ = []
    mods["mcp"] = pkg
    mods["mcp.server"] = server
    target = "mcp.server.mcpserver" if generation == 2 else "mcp.server.fastmcp"
    mod = types.ModuleType(target)
    mod.Context = _Ctx
    if generation == 2:
        mod.MCPServer = _Server
    else:
        mod.FastMCP = _Server
    mods[target] = mod
    return mods


def _load(generation: int = 2, **env):
    """가짜 SDK 를 꽂고 어댑터를 새로 import 한다."""
    saved_env = {k: os.environ.get(k) for k in list(_BASE_ENV) + list(env)}
    saved_mods = {k: sys.modules.get(k) for k in
                  ("mcp", "mcp.server", "mcp.server.mcpserver", "mcp.server.fastmcp")}
    try:
        os.environ.update({k: str(v) for k, v in {**_BASE_ENV, **env}.items()})
        for k in ("mcp", "mcp.server", "mcp.server.mcpserver", "mcp.server.fastmcp"):
            sys.modules.pop(k, None)
        sys.modules.update(_fake_sdk(generation))
        spec = importlib.util.spec_from_file_location(
            f"_ext_tool_http_probe_{generation}_{len(env)}", _SRC)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


# ── 헤더 추출 (세대별 실제 경로) ──────────────────────────────────────────────

class _V2Ctx:
    """v2 — `Context.headers` 가 매핑을 준다."""

    def __init__(self, headers):
        self.headers = headers


class _V1Ctx:
    """v1 — 요청 객체를 두 단계 타고 들어간다."""

    def __init__(self, headers):
        req = types.SimpleNamespace(headers=headers)
        self.request_context = types.SimpleNamespace(request=req)


@pytest.mark.parametrize("generation", [1, 2])
def test_bearer_is_read_from_each_sdk_generation(generation):
    """★ 한 세대만 다루면 다른 세대에서 **전 호출이 no_authorization** 이 된다.
    문자열 검사로는 절대 잡히지 않는 형태라 실제로 부른다."""
    mod = _load(generation)
    assert mod._SDK == generation, "가짜 SDK 주입이 의도한 세대를 태우지 않았다"
    token = "Bearer mat_probe_value"
    assert mod._bearer_from_context(_V2Ctx({"authorization": token})) == token
    assert mod._bearer_from_context(_V1Ctx({"authorization": token})) == token


def test_bearer_is_empty_when_transport_carries_no_headers():
    """stdio 등 헤더가 없는 전송에서 예외로 죽으면 안 된다 — 빈 값으로 떨어져야 한다."""
    mod = _load(2)
    assert mod._bearer_from_context(object()) == ""
    assert mod._bearer_from_context(_V2Ctx({})) == ""
    assert mod._bearer_from_context(_V2Ctx(None)) == ""


def test_post_refuses_without_authorization_and_never_calls_upstream():
    """토큰이 없으면 **상류를 부르지 않는다** — 무인증 요청을 web 으로 흘리면 안 된다."""
    mod = _load(2)
    called = []
    mod._opener = lambda *a, **kw: called.append(1)  # 호출되면 즉시 드러난다
    out = mod._post("/api/ai/tools/open_task", {"question": "x"}, _V2Ctx({}))
    assert "no_authorization" in out
    assert not called, "토큰 없이 상류를 호출했다"


def test_post_sends_authorization_and_pinned_host_header():
    """★ Host 를 고정하지 않으면 앱의 TrustedHost 가 400 을 준다(Caddy 가 같은 이유로 고정)."""
    mod = _load(2)
    seen = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b'{"ok": true}'

    class _Op:
        def open(self, req, timeout=None):
            seen["url"] = req.full_url
            seen["headers"] = dict(req.header_items())
            return _Resp()

    mod._opener = lambda *a, **kw: _Op()
    out = mod._post("/api/ai/tools/open_task", {"question": "x"},
                    _V2Ctx({"authorization": "Bearer mat_x"}))
    assert '"ok"' in out
    assert seen["url"].startswith("https://web-a:8000/")
    lowered = {k.lower(): v for k, v in seen["headers"].items()}
    assert lowered["authorization"] == "Bearer mat_x"
    assert lowered["host"] == "mysql-ai.company.local"


# ── TLS 이름 고정 ─────────────────────────────────────────────────────────────

def test_sni_connection_wraps_with_the_pinned_name_not_the_url_host(monkeypatch):
    """★ 이 한 줄이 없으면 `web-a` 로 호스트명 검증이 돌아 전 호출이 TLS 오류가 된다.
    반대로 검증을 끄면 토큰이 MITM 에 노출된다 — **이름만** 바뀌는지 실행해서 본다."""
    mod = _load(2)
    captured = {}

    class _FakeCtx:
        def wrap_socket(self, sock, server_hostname=None):
            captured["name"] = server_hostname
            return sock

    conn = mod._SniHTTPSConnection("web-a", 8000)
    conn._context = _FakeCtx()
    conn.sock = object()
    conn.sni_hostname = "mysql-ai.company.local"
    # 소켓 연결은 건너뛰고 wrap 단계만 실행한다.
    # ⚠ monkeypatch 로 되돌린다 — stdlib 클래스를 영구 변경하면 이후 테스트가 전부 오염된다.
    monkeypatch.setattr(mod.http.client.HTTPConnection, "connect", lambda self: None)
    conn.connect()
    assert captured["name"] == "mysql-ai.company.local", "URL 호스트로 검증하고 있다"


def test_opener_is_built_once_not_per_call():
    """codex P2 — 장기 실행 프로세스라 호출마다 컨텍스트를 만들면 그대로 누수다."""
    mod = _load(2, EXT_TOOL_CA_BUNDLE="")
    assert mod._opener() is mod._opener(), "호출마다 다른 opener 를 만든다"


# ── 기동 거부 (fail-loud) ─────────────────────────────────────────────────────

def test_plaintext_upstream_is_refused_by_default():
    with pytest.raises(SystemExit):
        _load(2, EXT_TOOL_API_BASE_URL="http://web-a:8000")


def test_verify_off_is_refused_when_any_upstream_is_remote():
    """★ codex P1 — 첫 후보만 검사하면 `loopback,공격자` 조합으로 우회된다."""
    with pytest.raises(SystemExit):
        _load(2, EXT_TOOL_VERIFY_TLS="0",
              EXT_TOOL_API_BASE_URL="https://localhost:8000,https://evil.example:443")


def test_verify_off_is_allowed_when_every_upstream_is_loopback():
    """경계 반대편 — 전부 loopback 이면 기동한다(로컬 개발 경로가 죽으면 안 된다)."""
    mod = _load(2, EXT_TOOL_VERIFY_TLS="0",
                EXT_TOOL_API_BASE_URL="https://localhost:8000,https://127.0.0.1:8443")
    assert mod._VERIFY_TLS is False


def test_public_bind_requires_explicit_optin():
    with pytest.raises(SystemExit):
        _load(2, EXT_TOOL_HTTP_BIND="0.0.0.0")


def test_all_tools_are_registered_at_import():
    """등록 자체가 import 부수효과다 — 데코레이터가 깨지면 도구 0개로 조용히 뜬다."""
    mod = _load(2)
    assert sorted(mod.mcp.tools) == sorted([
        "open_task", "get_task_context", "submit_answer",
        # feature-0043 (2026-08-26): 웹 대화 pull 브리지. 이 둘이 빠지면 무설치 주 경로
        # (`/api/ai/mcp`)에서 대기 질문을 발견·점유할 수 없다(codex 리뷰 P1-1).
        "list_open_requests", "claim_request",
        # feature-0043 사용감 패리티(2026-08-27): 첨부 본문 읽기.
        "read_task_attachment",
        "wait_for_request",
        "list_schemas", "describe_schema", "describe_table", "search_tables",
        "get_foreign_keys", "get_table_indexes",
        "execute_sql",   # P1 (2026-08-14)
    ]), sorted(mod.mcp.tools)
