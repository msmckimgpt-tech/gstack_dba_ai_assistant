#!/usr/bin/env python3
"""feature-0023 (REQ-20260722-conversation-api-access) — Conversation API MCP 서버.

이 제품(사내 AI assistant)의 **작업 화면 대화** 부분을 MCP tool 로 노출한다. 다른 AI
클라이언트(Claude Code, MCP 지원 에이전트 등)가 `ask`/`new_conversation`/
`list_conversations`/`get_history` tool 로 assistant 와 대화를 주고받는다.

conversation-quality-controls(2026-07-28): 대화 **품질 축**(모델·추론 강도·제품·폴더 커스텀
지침·첨부)도 tool 로 조정한다 — `list_capabilities`(먼저 호출해 허용 값 확인) ·
`set_conversation_product` · `list_folders` / `create_folder` / `set_folder_instructions` /
`move_conversation_to_folder` · `upload_attachment`.

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
import secrets
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
def _path_seg(value: str) -> str:
    """URL **경로 세그먼트 1개**로 안전하게 인코딩한다.

    `urllib.parse.quote` 의 기본 `safe='/'` 는 슬래시를 그대로 통과시켜, tool 인자로 받은
    `conversation_id` 가 `x/../../api/…` 같은 값이면 의도한 경로를 벗어난다. tool 인자는 이 MCP
    서버를 구동하는 LLM 이 채우고 그 입력에 신뢰할 수 없는 대화 내용이 섞일 수 있으므로
    (prompt injection), 세그먼트 인코딩은 `safe=''` 로 못박는다. 서버측 인증·scope·절대 denylist 가
    최종 방어선이지만, 클라이언트가 먼저 의도한 경로만 만들게 한다(§18.8 보안 리뷰 반영)."""
    return urllib.parse.quote(str(value or ""), safe="")


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


def _api_multipart_upload(path: str, *, field: str, filename: str, content: bytes) -> dict[str, Any]:
    """multipart/form-data 파일 업로드(첨부 전용). `_api_request` 와 동일한 에러 계약.

    stdlib 만으로 body 를 조립한다(추가 의존성 없이 urllib 유지). boundary 는 `secrets` 로
    생성하고, 파일 내용에 우연히 포함될 확률이 무시 가능하도록 충분한 엔트로피를 준다.
    filename 은 헤더 injection 을 막기 위해 CR/LF/따옴표를 제거한다."""
    boundary = "----mcpform" + secrets.token_hex(16)
    safe_name = "".join(c for c in (filename or "upload") if c not in '"\r\n') or "upload"
    pre = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{safe_name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    post = f"\r\n--{boundary}--\r\n".encode("utf-8")
    data = pre + content + post
    req = urllib.request.Request(
        BASE_URL + path, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {_TOKEN}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
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
        return {"error": f"업로드 실패: {type(e).__name__}", "detail": str(e)[:300]}
    try:
        return json.loads(raw)
    except Exception:
        return {"error": "응답 JSON 파싱 실패", "raw": raw[:500]}


# ── Tools ───────────────────────────────────────────────────────────────────────
@mcp.tool()
def ask(message: str, conversation_id: str | None = None,
        model: str | None = None, reasoning_level: str | None = None,
        product_id: int | None = None, product_mode: str | None = None) -> dict:
    """assistant 에게 메시지를 보내고 답변을 받는다(작업 화면 대화의 핵심).

    Args:
        message: 보낼 질문/메시지. 필수.
        conversation_id: 이어갈 대화 id. 생략 시 새 대화 생성.
        model: 사용할 모델(생략 시 서비스 기본). 허용 값은 `list_capabilities` 로 확인.
        reasoning_level: 추론 강도 low|normal|high|max(생략 시 모델 기본). 대화에 기억된다.
        product_id: 제품(데이터소스 스코프) id. **새 대화를 만들 때만** 반영된다 —
            기존 대화는 `set_conversation_product` 를 쓴다.
        product_mode: 'auto'|'pinned'. product_id 를 주면 기본 'pinned'.

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
    # 제품 힌트는 서버에서 **신규 대화 생성 경로에서만** 소비된다(기존 대화의 제품 변경 경로는
    # PATCH 단독 진실 — TASK-0047 race 가드). conversation_id 와 함께 보내면 서버가 무시하므로,
    # 호출자가 조용한 무시를 겪지 않도록 여기서 먼저 걸러 안내한다.
    if product_id is not None or product_mode:
        if conversation_id:
            return {"error": "기존 대화의 제품은 ask 로 바꿀 수 없습니다 — "
                             "set_conversation_product(conversation_id, product_id) 를 쓰세요."}
        mode = str(product_mode or ("pinned" if product_id is not None else "auto")).strip().lower()
        if mode not in ("auto", "pinned"):
            return {"error": "product_mode 는 'auto' 또는 'pinned' 여야 합니다."}
        body["product_mode"] = mode
        if mode == "pinned":
            if product_id is None:
                return {"error": "product_mode='pinned' 이면 product_id 가 필요합니다."}
            body["product_id"] = int(product_id)
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


# ── 대화 품질 조정 tool (conversation-quality-controls, 2026-07-28) ─────────────────────

@mcp.tool()
def list_capabilities(conversation_id: str | None = None) -> dict:
    """이 토큰으로 **실제 조정 가능한** 대화 품질 옵션을 조회한다. 품질을 바꾸기 전에 먼저 호출.

    사용 가능한 모델·제품·폴더는 토큰이 귀속된 서비스 계정의 권한에 따라 다르다. 목록 밖 값을
    보내면 400(카탈로그 밖) 또는 403(권한 밖)이므로 값을 추측하지 말고 여기서 얻는다.

    Args:
        conversation_id: 주면 그 대화의 현재 설정(model/reasoning_level/product)도 함께 반환.

    Returns:
        {quality_controls: {model, reasoning_level, product, folder_instructions, attachments},
         conversation} — 각 축은 {available, set_via, scope, default, values, note}.
        `available:false` 인 축은 이 토큰으로 조정할 수 없으며 note 에 사유가 있다.
    """
    params = {"conversation_id": conversation_id} if conversation_id else None
    return _api_request("GET", "/api/ai/capabilities", params=params)


@mcp.tool()
def set_conversation_product(conversation_id: str, product_id: int | None = None,
                             mode: str = "pinned") -> dict:
    """**기존 대화**의 제품(데이터소스 스코프)을 바꾼다 — 다음 ask 부터 적용된다.

    질의 대상 DB 범위를 정하는 축이라 답변 품질 영향이 가장 크다. 허용 product_id 는
    `list_capabilities` 의 quality_controls.product.values 참조.

    Args:
        conversation_id: 대상 대화 id. 필수.
        product_id: mode='pinned' 일 때 필수. 접근 권한 없는 제품이면 403.
        mode: 'pinned'(제품 고정) 또는 'auto'(고정 해제 — product_id 무시).
    """
    if not str(conversation_id or "").strip():
        return {"error": "conversation_id required"}
    m = str(mode or "pinned").strip().lower()
    if m not in ("auto", "pinned"):
        return {"error": "mode 는 'auto' 또는 'pinned' 여야 합니다."}
    body: dict[str, Any] = {"mode": m}
    if m == "pinned":
        if product_id is None:
            return {"error": "mode='pinned' 이면 product_id 가 필요합니다."}
        body["product_id"] = int(product_id)
    return _api_request("PATCH", f"/api/conversations/{_path_seg(conversation_id)}/product",
                        body=body)


@mcp.tool()
def list_folders() -> dict:
    """내 폴더(프로젝트 워크스페이스) 목록 + 각 폴더의 커스텀 지침을 조회한다."""
    return _api_request("GET", "/api/folders")


@mcp.tool()
def create_folder(name: str, instructions: str | None = None,
                  parent_folder_id: int | None = None) -> dict:
    """커스텀 지침을 가진 폴더를 만든다.

    폴더에 배정된 대화는 발화 시 그 지침이 시스템 프롬프트로 주입된다 — 톤·출력 형식·도메인
    규칙을 대화마다 반복 설명하지 않아도 된다.

    Args:
        name: 폴더 이름(최대 120자). 필수.
        instructions: 이 폴더 대화에 주입할 지침.
        parent_folder_id: 상위 폴더 id(중첩). 깊이 상한 초과 시 400.
    """
    if not str(name or "").strip():
        return {"error": "name required"}
    body: dict[str, Any] = {"name": name}
    if instructions is not None:
        body["instructions"] = instructions
    if parent_folder_id is not None:
        body["parent_folder_id"] = int(parent_folder_id)
    return _api_request("POST", "/api/folders", body=body)


@mcp.tool()
def set_folder_instructions(folder_id: int, instructions: str | None) -> dict:
    """폴더의 커스텀 지침을 갱신한다(None 이면 지침 제거).

    본인 소유 폴더만 수정된다 — 타 계정 폴더는 404.
    """
    return _api_request("PATCH", f"/api/folders/{int(folder_id)}",
                        body={"instructions": instructions})


@mcp.tool()
def move_conversation_to_folder(conversation_id: str, folder_id: int | None = None) -> dict:
    """대화를 폴더에 배정한다(folder_id=None 이면 폴더에서 빼낸다).

    배정하면 그 폴더의 커스텀 지침이 이후 답변에 적용된다.
    """
    if not str(conversation_id or "").strip():
        return {"error": "conversation_id required"}
    return _api_request("PATCH", f"/api/conversations/{_path_seg(conversation_id)}/folder",
                        body={"folder_id": int(folder_id) if folder_id is not None else None})


@mcp.tool()
def upload_attachment(conversation_id: str, file_path: str) -> dict:
    """대화에 문서를 첨부해 답변 근거(grounding)를 늘린다.

    Args:
        conversation_id: 대상 대화 id. 필수.
        file_path: 이 MCP 서버가 실행 중인 **클라이언트 측** 파일 경로. 필수.

    용량 상한(파일/대화/계정)을 넘으면 400. 첨부 권한이 없으면 403.
    """
    if not str(conversation_id or "").strip():
        return {"error": "conversation_id required"}
    path = str(file_path or "").strip()
    if not path:
        return {"error": "file_path required"}
    if not os.path.isfile(path):
        return {"error": f"파일을 찾을 수 없습니다: {path}"}
    try:
        with open(path, "rb") as fh:
            content = fh.read()
    except Exception as e:
        return {"error": f"파일 읽기 실패: {type(e).__name__}"}
    if not content:
        return {"error": "빈 파일은 업로드할 수 없습니다."}
    return _api_multipart_upload(
        f"/api/conversations/{_path_seg(conversation_id)}/attachments",
        field="file", filename=os.path.basename(path), content=content,
    )


if __name__ == "__main__":
    mcp.run()
