"""feature-0041 — 상한 콘솔 노출 · HTTP 전송 기동 배선 · e2e 절차서 계약.

이번 cycle 의 세 축을 정적으로 고정한다. 라이브 기동 자체는 배포 후 probe 로 확인하지만,
**배선이 빠지면 배포해도 조용히 안 도는** 부분(compose·Dockerfile·deploy 스파인·Caddy)은
여기서 잡는다 — 2026-08-12 의 "이미지에 모듈이 없어 기동 실패" 와 같은 계열이다.
"""
from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "unit", "feature-0003-agent-web-ui", "src"))

from shared import runtime_settings as rs  # noqa: E402
import tool_ledger as tl  # noqa: E402


def _read(*parts: str) -> str:
    with open(os.path.join(_REPO, *parts), encoding="utf-8") as fh:
        return fh.read()


# ── 상한이 콘솔에 노출되는가 ──────────────────────────────────────────────────

def test_all_ledger_limits_are_console_editable():
    """★ 코드 기본값만 있고 콘솔에 없으면 운영자가 급할 때 손댈 방법이 없다."""
    keys = {s["key"] for s in rs.list_specs() if s.get("group") == "external_tool_surface"}
    assert set(tl.DEFAULTS) == keys, f"콘솔 노출 누락/초과: {set(tl.DEFAULTS) ^ keys}"


def test_spec_defaults_match_code_defaults():
    """runtime_settings 리터럴 복제본과 코드 기본값이 갈리면 콘솔 표시가 거짓이 된다."""
    spec = {s["key"]: s["default"] for s in rs.list_specs()
            if s.get("group") == "external_tool_surface"}
    for key, val in tl.DEFAULTS.items():
        assert spec[key] == val, f"{key}: spec={spec[key]} vs code={val}"


def test_limits_are_live_apply_mode():
    """재기동해야 반영되면 '급히 풀기' 가 성립하지 않는다."""
    for s in rs.list_specs():
        if s.get("group") == "external_tool_surface":
            assert s["apply_mode"] == "live", f"{s['key']} 가 live 가 아니다"


def test_no_dead_knobs_in_console(codex_p1=True):
    """★ 콘솔에 보이는데 아무 데서도 읽지 않는 knob 은 **존재하지 않는 방어를 표시**한다.
    동시 실행 상한은 미구현이라 의도적으로 제거했다 — 구현되면 그때 올린다."""
    keys = {s["key"] for s in rs.list_specs() if s.get("group") == "external_tool_surface"}
    assert "AGENT_EXT_TOOL_CONCURRENCY" not in keys
    assert "AGENT_EXT_TOOL_CONCURRENCY" not in tl.DEFAULTS


def test_open_task_is_rate_gated(codex_p1=True):
    """★ 상한이 구조 조회에만 걸려 있으면 task 생성은 무제한이다(DB 쓰기 경로)."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "routers", "ai_tools.py")
    open_task = src[src.index("async def open_task"):src.index("async def get_task_context")]
    assert "_ledger.check_limits(" in open_task
    assert "_ledger.check_open_tasks(" in open_task


def test_open_task_cap_is_actually_enforced():
    """미제출 상한이 집행되지 않으면 소프트 강제가 문서상 장치로만 남는다."""
    class _Cur:
        def __init__(self, n): self.n = n
        def execute(self, sql, params=()): assert "Status = 'open'" in sql
        def fetchone(self): return (self.n,)
        def close(self): pass
    class _Conn:
        def __init__(self, n): self.n = n
        def cursor(self): return _Cur(self.n)
    tl.check_open_tasks(_Conn(3), account_id=1, limits={"AGENT_EXT_TASK_OPEN_MAX": 5})
    with pytest.raises(tl.RateLimited) as exc:
        tl.check_open_tasks(_Conn(5), account_id=1, limits={"AGENT_EXT_TASK_OPEN_MAX": 5})
    assert exc.value.limit == "open_tasks"
    # 조회 실패는 통과 — 규율 장치이지 부하 상한이 아니다
    tl.check_open_tasks(None, account_id=1)


def test_upstream_tls_is_verified_not_disabled():
    """★ web replica 는 TLS 로 듣지만 인증서 SAN 에 컨테이너 이름이 없다. 여기서 검증을 끄면
    Bearer token 이 사내망 MITM 에 노출된다 — Caddy 처럼 **검증 대상 이름만 고정**한다."""
    compose = _read("docker-compose.yml")
    block = compose[compose.index("  ext-tool-mcp:"):]
    block = block[:block.index("\n  insight-worker:")]
    assert "EXT_TOOL_CA_BUNDLE: /certs/rootCA.pem" in block
    assert "EXT_TOOL_UPSTREAM_TLS_SERVER_NAME" in block and "EXT_TOOL_UPSTREAM_HOST_HEADER" in block
    assert "EXT_TOOL_VERIFY_TLS" not in block, "검증을 끄는 설정이 들어갔다"
    assert "/certs:ro" in block, "rootCA 를 마운트하지 않으면 기동은 되고 호출만 실패한다"
    assert "/shared" in block, "volumes 를 덮어쓰며 agent-common 의 /shared 가 사라졌다"


def test_sni_pinning_keeps_hostname_verification_on():
    """이름 고정은 검증을 **켠 채** 대상만 바꾸는 것이다. 이 클래스가 check_hostname 을
    건드리면 그 순간 사내 CA 가 서명한 아무 이름의 인증서나 통과한다."""
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src",
                "external_tool_mcp_http.py")
    assert "_SniHTTPSConnection" in src and "server_hostname=self.sni_hostname" in src
    body = src[src.index("class _SniHTTPSConnection"):src.index("class _NoRedirect")]
    assert "check_hostname" not in body, "SNI 경로가 호스트명 검증을 끄고 있다"
    assert "verify_mode" not in body


@pytest.mark.parametrize("adapter", ["external_tool_mcp_server.py", "external_tool_mcp_http.py"])
def test_adapters_support_both_mcp_sdk_generations(adapter):
    """★ SDK 2.0 이 `mcp.server.fastmcp` 를 제거했다. 가이드가 안내하는 `pip install mcp` 는
    이제 2.x 를 주므로, v1 만 지원하면 **안내대로 설치한 사용자가 바로 깨진다**
    (2026-08-13 배포 실패로 실증 — 이미지에 2.0 이 깔려 기동 불가)."""
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src", adapter)
    assert "from mcp.server.mcpserver import" in src, "v2 경로 미지원"
    assert "from mcp.server.fastmcp import" in src, "v1 경로 미지원(구 SDK 사용자)"
    assert "FastMCP(" not in src, "생성자가 v1 클래스명에 고정돼 있다"


def test_http_adapter_reads_headers_through_tool_context(codex_p1=True):
    """v2 에는 모듈 전역 `get_context()` 가 없다. 도구가 받은 ctx 로만 헤더를 읽어야 하며,
    두 세대의 접근 경로(`ctx.headers` / `ctx.request_context.request.headers`)를 모두 다뤄야
    한다 — 하나만 다루면 한쪽 세대에서 **전 호출이 no_authorization** 이 된다."""
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src",
                "external_tool_mcp_http.py")
    assert "mcp.get_context()" not in src, "v2 에 없는 전역 API 에 의존한다"
    assert 'getattr(ctx, "headers", None)' in src
    assert "ctx.request_context.request.headers" in src
    assert "def open_task(ctx: McpContext" in src, "도구가 ctx 를 받지 않으면 헤더에 못 닿는다"


def test_deploy_surfaces_startup_failure_cause():
    """★ `상태=none` 만 남기고 롤백하면 운영자가 원인을 못 본다 — 롤백이 이미지를 바꾼 뒤라
    로그가 사라지기도 한다(2026-08-13 실증: 원인은 컨테이너 로그 1줄이었다)."""
    sh = _read("bin", "deploy-web.sh")
    assert "dump_service_logs()" in sh
    fail_line = [ln for ln in sh.splitlines() if "기동 실패." in ln and "err " in ln]
    assert fail_line and "dump_service_logs" in fail_line[0], \
        "기동 실패 경로가 로그를 남기지 않는다"


def test_e2e_script_verifies_tls_when_ca_available(codex_p1=True):
    """★ 토큰을 싣는 스크립트가 `-k` 로 고정돼 있으면 MITM 에 무방비다."""
    sh = _read("unit", "feature-0041-external-ai-tool-surface", "scripts", "e2e-authorize.sh")
    assert "--cacert" in sh and "rootCA.pem" in sh
    assert "UNVERIFIED" in sh, "미검증 상태를 사용자에게 알리지 않는다"


def test_caddy_blocks_anonymous_mcp_connections(codex_p2=True):
    """MCP 전송 계층엔 verifier 가 없다 — 익명 스트림 개설을 엣지에서 끊는다."""
    cf = _read("unit", "feature-0006-lan-proxy-access", "src", "caddy", "Caddyfile")
    block = cf[cf.index("handle /api/ai/mcp*"):]
    block = block[:block.index("\n\thandle {")]
    # 주석에도 `reverse_proxy` 가 나오므로 지시어 줄만 남긴다 — 주석을 세면 순서 판정이 뒤집힌다.
    directives = "\n".join(ln for ln in block.splitlines() if not ln.strip().startswith("#"))
    assert "@noauth not header Authorization *" in directives
    assert directives.index("respond @noauth") < directives.index("reverse_proxy"), \
        "401 이 reverse_proxy 뒤면 익명 요청이 먼저 프록시로 나간다"


def test_mcp_path_matches_edge_path(codex_p1=True):
    """엣지가 경로를 그대로 넘기므로 서버도 같은 경로에서 받아야 한다(아니면 전부 404)."""
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src", "external_tool_mcp_http.py")
    assert '"/api/ai/mcp"' in src and "streamable_http_path=_HTTP_PATH" in src


def test_upstream_failover_only_on_connection_errors(codex_p2=True):
    """HTTP 오류를 다른 replica 로 재시도하면 같은 답을 두 번 받거나 부작용이 두 번 난다."""
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src", "external_tool_mcp_http.py")
    assert "BASE_URLS" in src and "for base in BASE_URLS" in src
    assert "다른 replica 로 넘기지 않는다" in src


def test_zero_means_unlimited(monkeypatch):
    """콘솔 minimum=0 규약 — 0 은 '상한 없음' 이어야 한다(운영자 탈출구)."""
    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=()): self._huge = True
        def fetchone(self): return (10**9, 10**9)
    class _Pg:
        def cursor(self): return _Cur()
    # 상한 0 → 초과 판정 자체를 하지 않는다
    tl.check_limits(_Pg(), account_id=1, client_id="c", limits={
        "AGENT_EXT_TOOL_RPM": 0, "AGENT_EXT_TOOL_ROWS_PER_HOUR": 0,
        "AGENT_EXT_TOOL_BYTES_PER_HOUR": 0})


def test_effective_limits_falls_back_to_defaults_when_settings_unavailable():
    """설정 조회 실패가 전면 차단이 되면 안 된다 — 상한은 코드 기본값으로도 집행된다."""
    conf = tl.effective_limits()
    assert set(conf) == set(tl.DEFAULTS) and all(isinstance(v, int) for v in conf.values())


# ── HTTP 전송 기동 배선 ───────────────────────────────────────────────────────

def test_compose_declares_ext_tool_mcp_service():
    import yaml
    d = yaml.safe_load(_read("docker-compose.yml"))
    svc = d["services"].get("ext-tool-mcp")
    assert svc, "compose 에 ext-tool-mcp 서비스가 없다"
    env = svc["environment"]
    # 기본값은 https — web replica 가 TLS 로 듣기 때문이다(`ENABLE_WEB_TLS=1`).
    # 평문 배포를 쓰는 환경은 EXT_TOOL_API_BASE_URL 로 덮어쓴다.
    assert "web-a:8000" in env["EXT_TOOL_API_BASE_URL"], "upstream 이 내부 web 이 아니다"
    assert ":-https://" in env["EXT_TOOL_API_BASE_URL"], "기본값이 https 가 아니다"
    assert "EXT_TOOL_ALLOW_PLAINTEXT_UPSTREAM" not in env, \
        "평문 예외가 기본 배포에 남아 있다 — TLS upstream 에서는 불필요하다"
    assert env["EXT_TOOL_HTTP_ALLOW_PUBLIC_BIND"] == "1"
    assert "ports" not in svc, "★ 포트를 직접 공개하면 평문 수신이 LAN 에 열린다 (Caddy 경유만)"


def test_dockerfile_copies_the_http_adapter():
    """★ 2026-08-12 재발 방지 — COPY 안 되면 배포해도 기동이 죽는다."""
    df = _read("unit", "feature-0002-agent-core", "src", "Dockerfile")
    assert "external_tool_mcp_http.py /app/ext_tools/" in df
    assert "/app/ext_tools/external_tool_mcp_http.py" in _read("docker-compose.yml")


def test_deploy_spine_rolls_out_the_new_service():
    """롤아웃 대상에서 빠지면 이미지만 새로 빌드되고 컨테이너는 구코드로 계속 돈다."""
    assert "ext-tool-mcp" in _read("bin", "deploy-web.sh")


def test_caddy_routes_mcp_before_the_catchall():
    """`handle` 은 순서가 의미를 갖는다 — 뒤에 두면 web 이 먼저 삼킨다."""
    cf = _read("unit", "feature-0006-lan-proxy-access", "src", "caddy", "Caddyfile")
    mcp = cf.index("handle /api/ai/mcp*")
    catchall = cf.index("reverse_proxy web-a:8000 web-b:8000")
    assert mcp < catchall, "MCP 라우트가 기본 handle 뒤에 있다"
    assert "ext-tool-mcp:8971" in cf


def test_plaintext_upstream_requires_explicit_optin():
    src = _read("unit", "feature-0041-external-ai-tool-surface", "src",
                "external_tool_mcp_http.py")
    assert "EXT_TOOL_ALLOW_PLAINTEXT_UPSTREAM" in src
    assert "compose 내부 네트워크 전용" in src


# ── e2e 절차서 ───────────────────────────────────────────────────────────────

def test_runbook_and_script_exist_and_agree():
    rb = _read("unit", "feature-0041-external-ai-tool-surface", "docs", "E2E_RUNBOOK.md")
    sh = _read("unit", "feature-0041-external-ai-tool-surface", "scripts", "e2e-authorize.sh")
    assert "e2e-authorize.sh" in rb, "절차서가 스크립트를 가리키지 않는다"
    assert "http://127.0.0.1:8765/cb" in rb and "http://127.0.0.1:8765/cb" in sh


@pytest.mark.parametrize("step", [
    "/api/ai/oauth/register", "/api/ai/oauth/authorize", "/api/ai/oauth/token",
    "/api/ai/tools/open_task", "/api/ai/tools/get_task_context",
    "/api/ai/tools/submit_answer"])
def test_script_covers_every_stage(step):
    sh = _read("unit", "feature-0041-external-ai-tool-surface", "scripts", "e2e-authorize.sh")
    assert step in sh, f"e2e 스크립트가 {step} 를 안 탄다"


def test_script_asserts_the_reuse_defense():
    """★ 이 단계가 빠지면 e2e 가 '되더라' 만 확인하고 **탈취 방어는 미검증**으로 남는다."""
    sh = _read("unit", "feature-0041-external-ai-tool-surface", "scripts", "e2e-authorize.sh")
    assert "구 refresh 재사용" in sh and 'reuse" = "401"' in sh.replace("$", "")
