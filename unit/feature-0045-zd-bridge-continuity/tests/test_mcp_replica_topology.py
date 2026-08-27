"""feature-0045 — 개인 AI 가 붙는 표면(MCP)이 배포를 견디는 토폴로지인지.

단일 컨테이너였던 `ext-tool-mcp` 는 배포마다 통째로 recreate 되어 그 연결을 끊었다.
여기서 잠그는 것은 그 구조가 되돌아가지 않는다는 사실이다 — 이 결함은 조용하다.
컨테이너는 healthy 로 다시 뜨고, 끊긴 것은 사용자의 AI 연결뿐이다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = REPO_ROOT / "docker-compose.yml"
CADDYFILE = (REPO_ROOT / "unit" / "feature-0006-lan-proxy-access" / "src" / "caddy" / "Caddyfile")
MCP_SRC = (REPO_ROOT / "unit" / "feature-0041-external-ai-tool-surface" / "src"
           / "external_tool_mcp_http.py")


@pytest.fixture(scope="module")
def services():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def test_mcp_runs_as_two_identical_replicas(services):
    """하나뿐이면 그 교체가 곧 전면 단절이다. 정의가 갈리면 롤링 중 동작이 갈린다."""
    a, b = services.get("ext-tool-mcp-a"), services.get("ext-tool-mcp-b")
    assert a and b, "MCP replica 가 둘이 아니다"
    assert a == b, "두 replica 의 정의가 다르다 — 같은 anchor 를 공유해야 한다"
    assert "ext-tool-mcp" not in services, (
        "구 단일 서비스가 남아 있다 — 두 세대가 동시에 돌고, compose 가 정리하지 않는다")


def test_mcp_replicas_are_stateless(services):
    """replica 가 둘이면 세션이 프로세스에 묶여선 안 된다.

    LB 가 다음 요청을 다른 replica 로 보내는 순간 그 세션을 모르고 **404 `Session not found`**
    가 난다. 이 표면은 매 호출이 Bearer 토큰으로 독립 인증되므로 실을 상태가 없다.
    """
    env = services["ext-tool-mcp-a"]["environment"]
    assert env.get("EXT_TOOL_MCP_STATELESS", "").startswith("${EXT_TOOL_MCP_STATELESS:-1}"), (
        f"stateless 기본값이 켜져 있지 않다: {env.get('EXT_TOOL_MCP_STATELESS')!r}")


def test_stateless_flag_is_wired_where_the_sdk_actually_reads_it():
    """**문자열이 아니라 배선**을 본다 (적대 리뷰 P1).

    초판은 `assert "stateless_http=True" in src` 였고 그 단정은 통과했다 — 그런데 v2 SDK 는
    그 인자를 **생성자에서 받지 않는다**(`run_streamable_http_async` 의 kwarg 다). 코드가
    `TypeError` 를 WARN 으로 삼켜 조용히 stateful 로 떴고, 2-replica LB 뒤에서 요청 절반이
    세션 404 로 죽는 상태가 소스 검사로는 green 이었다(vacuous pass).

    그래서 여기서는 `_server_kwargs()` 를 **실행해** 그 값이 어느 자리에 실리는지 확인하고,
    가능하면 설치된 SDK 의 실제 시그니처와 대조한다.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ext_mcp_under_test", MCP_SRC)
    src = MCP_SRC.read_text(encoding="utf-8")
    # 모듈 전체 import 는 env(FATAL 경로)를 요구하므로 함수 본문만 떼어 실행한다.
    assert "def _server_kwargs()" in src, "배선 함수가 없다"
    ns: dict = {"_INSTRUCTIONS": "x", "_HTTP_PATH": "/p", "_PORT": 1, "_BIND": "0.0.0.0"}
    body = src[src.index("def _server_kwargs()"):src.index("_INIT_KW, _RUN_KW =")]
    for sdk, expect_in_run in ((2, True), (1, False)):
        ns["_SDK"] = sdk
        ns["_STATELESS"] = True
        exec(compile(body, str(MCP_SRC), "exec"), ns)
        init_kw, run_kw = ns["_server_kwargs"]()
        if expect_in_run:
            assert run_kw.get("stateless_http") is True, (
                "v2 는 run kwarg 로 받는다 — 생성자에 넣으면 TypeError 이고, 삼키면 stateful 로 뜬다")
            assert "stateless_http" not in init_kw
        else:
            assert init_kw.get("stateless_http") is True, "v1 은 생성자 인자다"
            assert "stateless_http" not in run_kw
    # 기동 실패를 삼키지 않는다 — 조용한 stateful 이 가장 나쁜 결과다.
    assert "raise SystemExit(2)" in src[src.index("_INIT_KW, _RUN_KW ="):], (
        "생성 인자 불일치를 WARN 으로 넘기면 깨진 토폴로지로 뜬다")


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("mcp") is None,
    reason="mcp SDK 미설치(로컬) — 컨테이너 make test 에서 검증된다")
def test_installed_sdk_accepts_the_flag_where_we_put_it():
    """설치된 SDK 의 **실제 시그니처**와 대조한다. 자리가 또 바뀌면 여기서 걸린다."""
    import inspect
    try:
        from mcp.server.mcpserver import MCPServer as Server
        v2 = True
    except Exception:  # pragma: no cover — v1 환경
        from mcp.server.fastmcp import FastMCP as Server
        v2 = False
    if v2:
        assert "stateless_http" not in inspect.signature(Server.__init__).parameters, (
            "v2 생성자가 이 인자를 받게 바뀌었다 — 배선을 다시 확인하라")
        assert "stateless_http" in inspect.signature(
            Server.run_streamable_http_async).parameters
        # `run()` 이 **kwargs 를 전송별 함수로 넘기는지까지 본다(안 넘기면 조용히 무시된다).
        assert "kwargs" in inspect.getsource(Server.run)
    else:  # pragma: no cover
        assert "stateless_http" in inspect.signature(Server.__init__).parameters


def test_mcp_stop_grace_outlives_an_in_flight_relay(services):
    """이 프로세스는 개인 AI 의 요청을 web 으로 **중계 중**일 수 있다.

    종전 15s 는 그 왕복 상한(`EXT_TOOL_TIMEOUT_SEC=120`)보다 훨씬 짧아, 진행 중인 조사가
    SIGKILL 로 잘렸다. 조용하면 즉시 종료되므로 유휴 시 배포 시간에는 영향이 없다.
    """
    svc = services["ext-tool-mcp-a"]
    grace = str(svc["stop_grace_period"])
    relay = int(str(svc["environment"]["EXT_TOOL_TIMEOUT_SEC"]))
    seconds = int(re.match(r"^(\d+)s$", grace).group(1))
    assert seconds > relay, (
        f"stop_grace({grace}) 가 중계 상한({relay}s)보다 짧다 — 진행 중 조사가 잘린다")


def test_edge_load_balances_across_both_mcp_replicas():
    """엣지가 한쪽만 가리키면 replica 를 둘로 나눈 의미가 없다."""
    cf = CADDYFILE.read_text(encoding="utf-8")
    assert "reverse_proxy ext-tool-mcp-a:8971 ext-tool-mcp-b:8971" in cf
    # 내려간 replica 로의 dial 실패가 살아 있는 쪽으로 넘어가야 무중단이 성립한다.
    block = cf[cf.index("reverse_proxy ext-tool-mcp-a:8971"):]
    block = block[:block.index("\n\t\t}")]
    assert "lb_try_duration" in block, "재시도 창이 없으면 교체 순간의 요청이 그대로 실패한다"


def test_edge_does_not_use_active_health_on_the_mcp_route():
    """이 전송은 GET 에 4xx 로 답하는 것이 정상이고 그 코드가 SDK 버전마다 다르다.

    단일 `health_status` 로 고정하면 버전이 바뀌는 순간 **양 replica 가 동시에 down** 으로
    읽혀 경로 전체가 죽는다. 그래서 passive 격리 + 재시도로 간다.
    """
    cf = CADDYFILE.read_text(encoding="utf-8")
    block = cf[cf.index("reverse_proxy ext-tool-mcp-a:8971"):]
    block = block[:block.index("\n\t\t}")]
    assert "health_uri" not in block, "MCP 라우트에 active health 가 붙었다"
    assert "fail_duration" in block, "passive 격리조차 없으면 죽은 replica 가 계속 선택된다"


def test_adapter_reroutes_on_upstream_drain():
    """어댑터는 엣지를 거치지 않고 web replica 에 **직결**한다(web-a → web-b 순서).

    드레인된 replica 가 503 을 줄 때 다음 후보로 넘어가지 않으면, 그 replica 가 드레인된
    배포에서는 **모든 도구 호출이 실패**한다 — 무중단을 위해 만든 신호가 정반대로 작동한다.
    """
    src = MCP_SRC.read_text(encoding="utf-8")
    body = src[src.index("def _post("):src.index("class _SniHTTPSConnection")]
    assert "X-Bridge-Draining" in body, "드레인 신호를 읽지 않는다"
    m = re.search(r"if e\.code == 503 and .*?:\n(.*?)\n\s+# 그 외 HTTP 오류", body, re.S)
    assert m, "503 드레인 분기를 찾지 못했다"
    assert "continue" in m.group(1), "드레인 응답에서 다음 replica 로 넘어가지 않는다"
    # 나머지 HTTP 오류는 그대로 전달해야 한다 — 살아 있는 upstream 의 판정을 두 번 받거나
    # 부작용을 두 번 내면 안 된다.
    assert 'return json.dumps({"error": f"HTTP {e.code}"' in body


def test_adapter_still_lists_both_web_replicas(services):
    """upstream 후보가 하나면 web 롤링 중 그 replica 가 내려갈 때 도구 호출이 전부 실패한다."""
    env = services["ext-tool-mcp-a"]["environment"]
    base = env["EXT_TOOL_API_BASE_URL"]
    assert "web-a:8000" in base and "web-b:8000" in base
