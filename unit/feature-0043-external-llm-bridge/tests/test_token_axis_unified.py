"""feature-0043 — 인증 축 통일: **모든 인증은 `mat_` 하나로** (사용자 결정 2026-08-27).

## 왜 필요한가

두 토큰 축이 공존했다.

| 접두 | 축 | 발급 | 상태 |
|---|---|---|---|
| `mat_` | OAuth access token (도구 표면 `/api/ai/tools/*`·`/api/ai/mcp`) | `/ai/connect` self-serve · MCP 는 표준 OAuth 자동 | **유일 축** |
| `matk_` | 대화 API 토큰 (`/api/ask`) | `bin/api-token-issue.sh` (운영자 CLI) | **신규 발급 중단** |

`matk_` 축은 **서버 계정 LLM 으로 답변을 만들던 경로**다. 그 LLM 이 차단된 지금 그 토큰을
새로 발급해도 아무것도 완결되지 않는다 — 죽은 경로의 자격증명을 안내하는 것은 사용자를
막다른 길로 보내는 것이다.

**기존 토큰의 인증은 막지 않는다**(무회귀). 막는 것은 신규 발급과 **안내**다.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent

WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
DISCOVERY = WEB_SRC / "routers" / "ai_discovery.py"
GUIDE = WEB_SRC / "static" / "ai-api-guide.md"
OAUTH_STORE = WEB_SRC / "oauth_store.py"
ISSUE_SH = _REPO / "bin" / "api-token-issue.sh"
LAUNCHER_SH = _REPO / "bin" / "conversation-mcp.sh"


def _uncommented(path: pathlib.Path, comment: str = "#") -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").split("\n")
            if ln.strip() and not ln.strip().startswith(comment)]


# ── 발급 축 ──────────────────────────────────────────────────────────────────


def test_oauth_store_issues_mat_prefix():
    """OAuth access token 은 `mat_` 다 — 축의 정의."""
    text = OAUTH_STORE.read_text(encoding="utf-8")
    assert 'new_secret("mat_")' in text
    assert 'new_secret("matk_")' not in text, "OAuth 축이 대화 API 접두를 쓴다"


def test_connect_endpoint_issues_oauth_token():
    """`/ai/connect` 가 OAuth 축 토큰을 발급한다(대화 API 토큰이 아니라)."""
    text = (WEB_SRC / "routers" / "oauth_as.py").read_text(encoding="utf-8")
    assert "issue_console_token(" in text
    assert "matk_" not in text, "connect 경로가 대화 API 토큰을 언급한다"


# ── 안내: 발견 자료 ───────────────────────────────────────────────────────────


def test_discovery_hint_is_mat_prefix():
    """AI 가 읽는 발견 자료의 토큰 힌트가 `mat_` 다.

    이 힌트가 틀리면 외부 AI 는 **발급받을 수 없는 토큰**을 찾아 헤매다 멈춘다.
    """
    text = DISCOVERY.read_text(encoding="utf-8")
    assert '"token_format_hint": "mat_' in text, "발견 자료 힌트가 mat_ 가 아니다"
    assert '"token_format_hint": "matk_' not in text


def test_discovery_points_to_self_serve_and_mcp():
    """발급 방법 안내가 self-serve(`/ai/connect`)와 MCP 자동 연결을 가리킨다.

    구 안내는 "운영자에게 요청 → CLI 발급" 이었다. 그 CLI 는 이제 신규 발급을 거절한다.
    """
    text = DISCOVERY.read_text(encoding="utf-8")
    assert "/ai/connect" in text
    assert "/api/ai/mcp" in text
    # `how_to_obtain`(따라 하는 안내)에는 중단된 CLI 가 없어야 한다.
    # `deprecated_scheme`(왜 안 되는지 설명)에서의 언급은 남아야 한다 — 그게 사라지면
    # 옛 문서를 본 사람이 이유를 알 수 없다.
    how_to = text[text.index('"how_to_obtain"'):text.index('"deprecated_scheme"')]
    assert "bin/api-token-issue.sh" not in how_to, "발급 안내가 중단된 CLI 를 가리킨다"


def test_discovery_marks_ask_axis_as_non_generating():
    """`/api/ask` 가 더 이상 답변을 만들지 않는다는 사실이 스펙에 있다.

    이걸 빼면 외부 AI 는 200 응답(대기 안내)을 답변으로 오해한다.
    """
    text = DISCOVERY.read_text(encoding="utf-8")
    assert "더 이상 답변을 생성하지 않는다" in text or "답변을 생성하지 않는다" in text


# ── 안내: 사용자 가이드 ───────────────────────────────────────────────────────


def test_guide_token_format_is_mat():
    text = GUIDE.read_text(encoding="utf-8")
    assert "`mat_…`" in text, "가이드가 mat_ 형식을 명시하지 않는다"


def test_guide_marks_matk_deprecated():
    """가이드가 구 축을 **명시적으로 폐기 표시**한다 — 침묵하면 옛 문서를 본 사람이 그대로 쓴다."""
    text = GUIDE.read_text(encoding="utf-8")
    assert "matk_" in text, "폐기 사실 자체가 사라지면 옛 토큰 보유자가 이유를 알 수 없다"
    assert "더 이상 사용하지 않는다" in text or "DEPRECATED" in text


def test_guide_has_no_operator_request_flow():
    """"운영자에게 요청" self-serve-없음 안내가 남아 있지 않다(이제 self-serve 다)."""
    text = GUIDE.read_text(encoding="utf-8")
    assert "self-serve 없음" not in text


# ── 발급 차단 ────────────────────────────────────────────────────────────────


def test_issue_script_blocks_new_matk():
    """신규 `matk_` 발급이 차단된다 — 죽은 경로의 자격증명을 새로 만들지 않는다."""
    text = ISSUE_SH.read_text(encoding="utf-8")
    assert "ALLOW_DEPRECATED_MATK" in text, "차단 게이트가 없다"
    assert "exit 3" in text
    # revoke 는 통과해야 한다 — 기존 토큰을 거둘 수 없으면 폐기가 불가능해진다.
    assert '"--revoke"' in text or "'--revoke'" in text


def test_issue_script_points_to_mat_axis():
    text = ISSUE_SH.read_text(encoding="utf-8")
    assert "/ai/connect" in text and "/api/ai/mcp" in text


def test_legacy_launcher_is_marked_deprecated():
    text = LAUNCHER_SH.read_text(encoding="utf-8")
    assert "DEPRECATED" in text
    assert "mat_" in text


# ── 축 분리 불변식 ────────────────────────────────────────────────────────────


def test_tool_surface_does_not_accept_conversation_tokens():
    """도구 표면은 `WebOAuthTokens`(mat_)만 본다 — 대화 API 토큰으로 도달할 수 없다.

    두 축이 섞이면 "인증은 통일했다" 는 주장이 코드에서 거짓이 된다.
    """
    text = (WEB_SRC / "routers" / "ai_tools.py").read_text(encoding="utf-8")
    assert "require_ai_token" in text
    assert "WebApiTokens" not in text, "도구 표면이 대화 API 토큰 테이블을 참조한다"


@pytest.mark.parametrize("path", [DISCOVERY, GUIDE])
def test_no_active_matk_issuance_instructions(path):
    """활성(비주석) 안내에 `matk_` **발급 절차**가 남아 있지 않다.

    폐기 *설명* 은 남아야 하지만(왜 안 되는지), 발급 명령을 그대로 두면 따라 하게 된다.
    """
    text = path.read_text(encoding="utf-8")
    for m in re.finditer(r"api-token-issue\.sh[^\n]*", text):
        line = m.group(0)
        # 폐기 신호는 언급 **앞뒤** 어디에 있어도 된다 — 한국어 문장은 서술어가 뒤에 온다
        # ("… `bin/api-token-issue.sh`)는 더 이상 사용하지 않는다"). 앞쪽만 보면 놓친다.
        window = text[max(0, m.start() - 400):m.start() + 400]
        assert any(k in window for k in ("DEPRECATED", "더 이상", "중단", "deprecated")), (
            f"{path.name}: 발급 명령이 폐기 맥락 없이 남아 있다 — {line[:80]}"
        )
