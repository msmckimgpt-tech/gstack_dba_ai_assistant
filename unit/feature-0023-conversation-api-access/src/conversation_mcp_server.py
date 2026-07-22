#!/usr/bin/env python3
"""feature-0023 (REQ-20260722-conversation-api-access) — Conversation API MCP 서버.

이 제품(사내 AI assistant)의 **작업 화면 대화** 부분을 MCP tool 로 노출한다. 다른 AI
클라이언트(Claude Code, MCP 지원 에이전트 등)가 `ask`/`new_conversation`/
`list_conversations`/`get_history` tool 로 assistant 와 대화를 주고받는다.

인증: **Bearer API 토큰**(feature-0023 Phase 1). 이 서버는 웹 서비스 밖(클라이언트 측)
에서 실행되며, `CONVERSATION_API_TOKEN` env 로 받은 토큰을 `Authorization: Bearer` 로
실어 HTTP 호출한다. 토큰은 로그에 남기지 않는다.

**관리 콘솔 미노출** — 대화 tool 만 제공(사용자 요구). 토큰 scope(`conversation.*`)가
서버측에서 관리 엔드포인트를 원천 차단하므로 이 서버가 관리 tool 을 열어도 무의미하지만,
표면 최소화를 위해 대화 tool 로만 한정한다.

## 환경변수
- CONVERSATION_API_BASE_URL  : 웹 서비스 베이스 URL (예: https://mysql-ai.company.local
                               또는 http://localhost:8000). 필수.
- CONVERSATION_API_TOKEN     : Bearer API 토큰(bin/api-token-issue.sh 로 발급). 필수.
- CONVERSATION_API_VERIFY_TLS: '0'/'false' 면 TLS 검증 비활성(사내 self-signed 대비). 기본 검증.
- CONVERSATION_API_DEFAULT_MODEL : ask 기본 모델(미지정 시 서버측 API_DEFAULT_MODEL 사용).
- CONVERSATION_API_TIMEOUT_SEC   : HTTP 타임아웃(기본 120).

## 실행
    CONVERSATION_API_BASE_URL=... CONVERSATION_API_TOKEN=... \
        python3 conversation_mcp_server.py
(보통 bin/conversation-mcp.sh 로 기동. .mcp.json 의 stdio 서버로 등록.)
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - 런처가 사전 안내
    sys.stderr.write(
        "[conversation-mcp] mcp SDK 를 import 하지 못했습니다. `pip install mcp` 후 재시도.\n"
        f"  ({exc})\n"
    )
    raise


# ── 설정 로드 (fail-loud) ──────────────────────────────────────────────────────
def _require_env(name: str) -> str:
    val = str(os.getenv(name, "") or "").strip()
    if not val:
        sys.stderr.write(f"[conversation-mcp] FATAL: 환경변수 {name} 가 필요합니다.\n")
        raise SystemExit(2)
    return val


BASE_URL = _require_env("CONVERSATION_API_BASE_URL").rstrip("/")
_TOKEN = _require_env("CONVERSATION_API_TOKEN")
_VERIFY_TLS = str(os.getenv("CONVERSATION_API_VERIFY_TLS", "1")).lower() not in ("0", "false", "no", "off")
_DEFAULT_MODEL = str(os.getenv("CONVERSATION_API_DEFAULT_MODEL", "") or "").strip()
_TIMEOUT = float(os.getenv("CONVERSATION_API_TIMEOUT_SEC", "120") or "120")

_SSL_CTX = None if _VERIFY_TLS else ssl._create_unverified_context()

mcp = FastMCP("conversation-api")


# ── HTTP helper ────────────────────────────────────────────────────────────────
def _api_request(method: str, path: str, *, body: dict | None = None, params: dict | None = None) -> dict[str, Any]:
    """웹 서비스 대화 API 호출. Bearer 토큰 주입. 응답 JSON(dict) 반환.

    토큰은 어떤 로그/에러 메시지에도 노출하지 않는다. 실패 시 {'error': ...} dict 반환
    (tool 호출자가 인지). 인증 실패(401/403)는 토큰/스코프 문제로 명시 안내."""
    url = BASE_URL + path
    if params:
        q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if q:
            url = f"{url}?{q}"
    data = None
    headers = {"Authorization": f"Bearer {_TOKEN}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        if e.code in (401, 403):
            return {"error": f"인증/권한 실패 (HTTP {e.code}) — API 토큰 또는 scope 를 확인하세요.",
                    "status": e.code, "detail": detail}
        return {"error": f"HTTP {e.code}", "status": e.code, "detail": detail}
    except Exception as e:
        return {"error": f"요청 실패: {type(e).__name__}", "detail": str(e)[:300]}
    try:
        return json.loads(raw)
    except Exception:
        return {"error": "응답 JSON 파싱 실패", "raw": raw[:500]}


# ── Tools ───────────────────────────────────────────────────────────────────────
@mcp.tool()
def ask(message: str, conversation_id: str | None = None,
        model: str | None = None, reasoning_level: str | None = None) -> dict:
    """assistant 에게 메시지를 보내고 답변을 받는다(작업 화면 대화의 핵심).

    Args:
        message: 보낼 질문/메시지. 필수.
        conversation_id: 이어갈 대화 id. 생략 시 새 대화 생성.
        model: 사용할 모델(생략 시 서비스 기본).
        reasoning_level: 추론 강도 low|normal|high|max(생략 시 모델 기본).

    Returns:
        {output, conversation_id, executed_sql, error} — output 이 assistant 답변 본문.
    """
    if not str(message or "").strip():
        return {"error": "empty message"}
    body: dict[str, Any] = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    eff_model = model or _DEFAULT_MODEL
    if eff_model:
        body["model"] = eff_model
    if reasoning_level:
        body["reasoning_level"] = reasoning_level
    resp = _api_request("POST", "/api/ask", body=body)
    if "error" in resp and resp.get("error") and "output" not in resp:
        return resp
    return {
        "output": resp.get("output", ""),
        "conversation_id": resp.get("conversation_id", ""),
        "executed_sql": resp.get("executed_sql", ""),
        "error": resp.get("error", ""),
    }


@mcp.tool()
def new_conversation() -> dict:
    """새 대화를 생성하고 conversation_id 를 반환한다."""
    return _api_request("POST", "/api/new_conversation", body={})


@mcp.tool()
def list_conversations() -> dict:
    """내(토큰 서비스 계정) 대화 목록을 조회한다."""
    return _api_request("GET", "/api/conversations")


@mcp.tool()
def get_history(conversation_id: str) -> dict:
    """특정 대화의 메시지 이력을 조회한다."""
    if not str(conversation_id or "").strip():
        return {"error": "conversation_id required"}
    return _api_request("GET", "/api/history", params={"conversation_id": conversation_id})


if __name__ == "__main__":
    mcp.run()
