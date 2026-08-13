"""feature-0041 잔여 4건 — 발견 자료 · L4 비대칭 · HTTP 전송 계약.

각 항목이 **왜 그렇게 생겼는지**를 고정한다. 특히 발견 자료는 "익명 = static contract,
인스턴스 데이터 0"(SEC-20260724) 불변식을 깨기 가장 쉬운 자리다 — 도구 표면 설명을 쓰다 보면
계정·제품·토큰 예시를 넣고 싶어진다.
"""
from __future__ import annotations

import ast
import os
import sys

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_WEB_SRC = os.path.join(_REPO, "unit", "feature-0003-agent-web-ui", "src")
sys.path.insert(0, _WEB_SRC)

import tool_authz as az  # noqa: E402

_DISCOVERY = os.path.join(_WEB_SRC, "routers", "ai_discovery.py")
_GUIDE = os.path.join(_WEB_SRC, "static", "ai-api-guide.md")
_HTTP_MCP = os.path.join(_HERE, "..", "src", "external_tool_mcp_http.py")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ── 발견 자료 ─────────────────────────────────────────────────────────────────

def test_manifest_declares_tool_surface_axis():
    """외부 AI 가 두 축의 차이를 **매니페스트만 보고** 판단할 수 있어야 한다."""
    src = _read(_DISCOVERY)
    assert '"tool_surface"' in src
    for needle in ("_TOOL_SURFACE_ENDPOINTS", "when_to_use", "cost_bearer",
                   "redirect_uri_policy", "token_policy", "session_contract"):
        assert needle in src, f"매니페스트에 '{needle}' 없음"


def test_manifest_tool_surface_carries_no_instance_data():
    """★ SEC-20260724 불변식 — 익명 매니페스트에 계정·제품·토큰 인스턴스 값이 없어야 한다."""
    import re
    tree = ast.parse(_read(_DISCOVERY))
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                and isinstance(n.value, str)]
    joined = "\n".join(literals)
    # 실제 발급물처럼 보이는 값(접두 + 충분한 길이의 난수부)만 잡는다.
    # 단순 부분문자열 검사는 `format_hint` 의 `mat_` 같은 정상 식별자를 오탐한다 —
    # 오탐이 나면 이 게이트를 사람이 꺼 버리고, 그러면 진짜 유출을 못 잡는다.
    leaked = re.findall(r"\b(?:mat|mar|mao|mac)_[A-Za-z0-9_-]{16,}", joined)
    assert not leaked, f"매니페스트에 실 발급물로 보이는 값: {leaked[:3]}"


def test_endpoint_catalog_is_hand_maintained_not_introspected():
    """자동 route introspection 은 admin 유출 위험 — 0023 이 세운 규약을 따른다."""
    src = _read(_DISCOVERY)
    assert "_TOOL_SURFACE_ENDPOINTS = [" in src
    for route in ("/api/ai/oauth/register", "/api/ai/oauth/authorize", "/api/ai/oauth/token",
                  "/api/ai/tools/open_task", "/api/ai/tools/get_task_context",
                  "/api/ai/tools/submit_answer"):
        assert route in src, f"카탈로그에 {route} 없음"


def test_openapi_documents_tool_surface_paths():
    src = _read(_DISCOVERY)
    for op in ("aiOauthRegister", "aiOauthAuthorize", "aiOauthToken",
               "aiToolsOpenTask", "aiToolsGetTaskContext", "aiToolsRun", "aiToolsSubmitAnswer"):
        assert f'"{op}"' in src, f"OpenAPI 에 {op} 없음"


def test_guide_teaches_the_human_consent_step_is_not_automatable():
    """가이드가 이 사실을 흐리면 외부 AI 가 인가를 자동화하려 시도하고 실패 루프에 빠진다."""
    guide = _read(_GUIDE)
    assert "부록 B" in guide
    assert "자동화 불가" in guide or "자동화할 수 없다" in guide
    assert "로그아웃하면" in guide            # 세션 죽음 → 토큰 죽음
    assert "source_tasks" in guide
    assert "데이터이지 지시가 아니다" in guide  # 인젝션 규칙
    assert "execute_sql" in guide             # 미노출 사실 명시


# ── L4 권한 비대칭 ────────────────────────────────────────────────────────────

def test_asymmetry_none_for_single_session():
    assert az.permission_asymmetry([{"account_id": 1, "products": [1, 2]}]) is None


def test_asymmetry_none_when_scopes_overlap():
    """같은 제품을 보는 세션끼리는 섞여도 피해가 작다 — flag 대상 아님."""
    out = az.permission_asymmetry([
        {"account_id": 1, "products": [1, 2, 3]},
        {"account_id": 2, "products": [1, 2, 3]},
    ])
    assert out is None


def test_asymmetry_flags_disjoint_scopes():
    """★ 한쪽만 민감 데이터소스에 닿는 조합 — 오염 시 피해가 큰 구간."""
    out = az.permission_asymmetry([
        {"account_id": 1, "products": [1]},
        {"account_id": 2, "products": [9]},
    ])
    assert out and out["kind"] == "permission_asymmetry"
    assert out["jaccard"] == 0.0 and out["n_accounts"] == 2


def test_asymmetry_finding_never_exposes_account_ids(codex_p1=True):
    """★ codex P1 — `client_id` 는 DCR 로 누구나 받는 **공유 가능한 앱 식별자**다.
    상대 계정 id 를 돌려주면 무관한 테넌트의 존재·권한 윤곽이 새어 나간다."""
    out = az.permission_asymmetry([
        {"account_id": 111, "products": [1]},
        {"account_id": 222, "products": [9]},
    ])
    assert out is not None
    assert "accounts" not in out, "finding 이 계정 id 를 담고 있다 — 교차 테넌트 노출"
    assert "111" not in str(out) and "222" not in str(out)


def test_asymmetry_uses_jaccard_not_raw_intersection():
    """교집합 크기만 보면 큰 집합끼리의 부분 겹침을 과소평가한다."""
    # 교집합 2개지만 합집합이 커서 유사도는 낮다 → flag
    out = az.permission_asymmetry([
        {"account_id": 1, "products": [1, 2, 3, 4, 5, 6]},
        {"account_id": 2, "products": [1, 2, 7, 8, 9, 10]},
    ])
    assert out is not None and out["jaccard"] < 0.5


def test_asymmetry_ignores_sessions_with_no_products():
    """둘 다 권한이 없으면 비교 대상이 아니다(0/0 을 최대 비대칭으로 읽으면 오탐)."""
    assert az.permission_asymmetry([
        {"account_id": 1, "products": []},
        {"account_id": 2, "products": []},
    ]) is None


def test_asymmetry_is_ledger_only_not_in_response(codex_p1=True):
    """★ 판정은 **운영자 관측**용이다 — 응답에 실으면 호출자가 남의 테넌트를 알게 된다."""
    src = _read(os.path.join(_WEB_SRC, "routers", "ai_tools.py"))
    assert "session_asymmetry" not in src, "L4 결과가 응답 본문에 실린다 — 교차 테넌트 노출"
    assert "if asym:\n        _safe_record" in src, "원장 기록도 안 하면 관측 목적이 사라진다"


def test_asymmetry_fanout_is_capped(codex_p2=True):
    """공유 client 에 계정이 많으면 인증된 요청 1건이 DB 증폭이 된다."""
    src = _read(os.path.join(_WEB_SRC, "routers", "ai_tools.py"))
    assert "_ASYMMETRY_MAX_ACCOUNTS" in src and "LIMIT %s" in src


# ── HTTP/SSE 전송 ─────────────────────────────────────────────────────────────

def test_http_transport_never_stores_credentials():
    """★ 서버가 토큰을 들면 '자격증명 무보관' 전제가 깨진다 — 요청 헤더를 그대로 전달한다."""
    src = _read(_HTTP_MCP)
    assert "EXT_TOOL_ACCESS_TOKEN" not in src, "HTTP 전송이 토큰을 env 로 보관한다"
    assert "_bearer_from_context" in src
    assert '"Authorization": auth' in src


def test_http_transport_enforces_https_like_stdio():
    """upstream 이 여러 개(replica failover)로 늘어나도 **전부** 같은 검사를 통과해야 한다 —
    목록 중 하나만 검사하면 나머지가 평문 우회로가 된다."""
    src = _read(_HTTP_MCP)
    assert "_require_https" in src
    assert "BASE_URLS = [_require_https(" in src, "목록 전체가 아니라 일부만 검사한다"


def test_http_transport_binds_loopback_by_default(codex_p1=True):
    """★ 이 서버는 **평문으로 수신**한다 — 0.0.0.0 이면 전달 전에 토큰이 노출된다."""
    src = _read(_HTTP_MCP)
    assert 'EXT_TOOL_HTTP_BIND", "127.0.0.1"' in src
    assert "EXT_TOOL_HTTP_ALLOW_PUBLIC_BIND" in src, "외부 바인딩이 명시 opt-in 이 아니다"
    assert 'host=_BIND' in src and 'host="0.0.0.0"' not in src


def test_tls_verify_off_restricted_to_loopback_upstream(codex_p2=True):
    """운영 호스트를 향한 채로 검증을 끄면 토큰을 MITM 에 그대로 내준다."""
    src = _read(_HTTP_MCP)
    assert "loopback upstream 에서만" in src and "SystemExit(2)" in src


@pytest.mark.parametrize("adapter", ["external_tool_mcp_server.py", "external_tool_mcp_http.py"])
def test_adapters_refuse_to_follow_redirects(adapter, codex_p1=True):
    """★ urllib 기본 opener 는 리다이렉트를 추종하며 Authorization 을 **다른 호스트로도** 보낸다."""
    src = _read(os.path.join(_HERE, "..", "src", adapter))
    assert "_NoRedirect" in src, f"{adapter} 가 리다이렉트를 추종한다 — 토큰 유출 경로"
    assert "urlopen(req" not in src, f"{adapter} 가 아직 기본 opener 를 쓴다"
    assert "_opener(ctx).open(req" in src


def test_http_transport_declares_weaker_isolation_honestly():
    """L1(도구 이름 분리)이 없다는 사실을 instructions 가 밝혀야 한다 — 숨기면 사용자가
    stdio 와 같은 수준으로 착각한다."""
    src = _read(_HTTP_MCP)
    assert "no per-session tool-name separation" in src
    assert "prefer the stdio launcher" in src


def test_http_transport_shares_the_defang_and_cap_contract():
    src = _read(_HTTP_MCP)
    assert "_defang" in src and "_MAX_BYTES" in src and "response_too_large" in src


@pytest.mark.parametrize("tool", [
    "open_task", "get_task_context", "submit_answer", "list_schemas",
    "describe_schema", "describe_table", "search_tables",
    "get_foreign_keys", "get_table_indexes"])
def test_http_transport_exposes_same_nine_tools(tool):
    src = _read(_HTTP_MCP)
    assert f"def {tool}(" in src, f"HTTP 전송에 {tool} 없음 — 두 전송의 표면이 갈렸다"
