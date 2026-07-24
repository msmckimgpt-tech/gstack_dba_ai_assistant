"""feature-0023 api-discovery — 외부 AI 용 API 발견 진입점 + 학습 가이드라인.

외부 AI 가 웹사이트를 탐색하며 Conversation API 를 자연스럽게 인지하도록, LLM/에이전트가
관용적으로 찾는 위치에 **큐레이션된(관리 콘솔 제외) 발견 자료**를 익명으로 제공한다:

- `GET /llms.txt`                          — LLM 발견 표준 파일(사이트 탐색 시 최우선 조회)
- `GET /.well-known/ai-conversation-api.json` — 기계판독 매니페스트(.well-known 관용 위치)
- `GET /api/ai/manifest`                    — 위와 동일 매니페스트(API 네임스페이스 alias)
- `GET /api/ai/guide`                       — 상세 학습 가이드라인(markdown)

보안(SEC-20260724): 위 4개는 **익명이되 static contract 전용** — 인스턴스 데이터 0,
`conversation.*` 엔드포인트만 노출(관리 콘솔 `/api/admin/*` 미포함). SECURITY.md §7 allowlist 등재.
FastAPI 기본 `/openapi.json`·`/docs`·`/redoc`(admin 포함 전체 스키마 익명 유출)는 app.py 에서
비활성화했고, 전체 스키마가 필요한 개발자는 admin-gated `GET /api/admin/openapi.json` 로 조회한다.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

import app

# static_pages(무인증 정적) 계열 — 발견 자료는 인증 게이트 없음. 순서는 파일명 순 뒤쪽이면 충분.
INCLUDE_ORDER = 9_500

router = APIRouter()


# ── 큐레이션 엔드포인트 카탈로그 (conversation-only — admin 제외, 수기 관리 정본) ──────────
_CONVERSATION_ENDPOINTS = [
    {
        "method": "POST", "path": "/api/ask",
        "summary": "메시지를 보내고 assistant 답변을 받는다(작업 화면 대화의 핵심).",
        "request": {
            "message": "string (필수) — 질문/메시지",
            "conversation_id": "string (선택) — 이어갈 대화 id. 생략 시 새 대화 생성",
            "model": "string (선택) — 미지정 시 서비스 기본 모델",
            "reasoning_level": "string (선택) — low|normal|high|max",
        },
        "response": {
            "output": "string — assistant 답변 본문",
            "conversation_id": "string",
            "executed_sql": "string — 실행된 SQL(있으면)",
            "error": "string — 비어 있으면 성공",
            "duration_ms": "number",
        },
    },
    {"method": "POST", "path": "/api/new_conversation", "summary": "새 대화 생성 → conversation_id 반환.",
     "request": {}, "response": {"conversation_id": "string"}},
    {"method": "GET", "path": "/api/conversations", "summary": "내(토큰 계정) 대화 목록. 타 계정 대화는 노출 안 됨.",
     "request": {"cursor": "string (선택, keyset 페이징)"}, "response": {"items": "array"}},
    {"method": "GET", "path": "/api/history", "summary": "특정 대화의 메시지 이력(본인 소유/멤버만).",
     "request": {"conversation_id": "string (필수)"}, "response": {"conversation_id": "string", "messages": "array"}},
    {"method": "GET", "path": "/api/ask_status", "summary": "진행 중 ask 의 상태 스냅샷(슬롯 미점유).",
     "request": {"conversation_id": "string"}, "response": {"status": "string"}},
    {"method": "GET", "path": "/api/ask_result", "summary": "완료된 ask 결과 폴링(read-only).",
     "request": {"conversation_id": "string"}, "response": {"output": "string", "status": "string"}},
    {"method": "GET", "path": "/api/progress", "summary": "ask 진행 단계(스텝) 조회.",
     "request": {"conversation_id": "string"}, "response": {"steps": "array"}},
    {"method": "POST", "path": "/api/cancel", "summary": "진행 중 ask 취소.",
     "request": {"conversation_id": "string"}, "response": {"cancelled": "bool"}},
]


def _manifest(request: Request) -> dict:
    # base_url 은 이 매니페스트가 반영하는 유일한 런타임 값이다(guide_url·base_url). 안전성은
    # TrustedHostMiddleware(app.py, allowed_hosts=WEB_ALLOWED_HOSTS)가 off-allowlist Host 를
    # 400 으로 거부하는 데 의존한다 — `WEB_ALLOWED_HOSTS=*`(host 검사 무력화) 로 두면 익명
    # 매니페스트의 guide_url 이 임의 Host 로 반영될 수 있으므로 wildcard 를 쓰지 않는다(SEC-20260724 REV LOW).
    origin = str(request.base_url).rstrip("/")
    return {
        "schema_version": "1.0",
        "service": {
            "name": "mysql_ai",
            "title": "사내 DB 대화형 AI assistant",
            "description": "자연어로 사내 데이터베이스를 질의·분석하는 AI assistant. "
                           "외부 AI/에이전트가 아래 Conversation API 로 이 assistant 와 대화할 수 있다.",
        },
        "ai_api": {
            "purpose": "외부 AI 가 '작업 화면 대화'(/api/ask 등)를 프로그램으로 구동한다.",
            "base_url": origin,
            "auth": {
                "scheme": "Bearer",
                "header": "Authorization: Bearer <token>",
                "token_format_hint": "matk_… (원문 미저장, 발급 시 1회만 표시)",
                "how_to_obtain": "서비스 운영자에게 요청 → 운영자가 `bin/api-token-issue.sh "
                                 "--account <저권한 서비스계정> --label \"<용도>\"` 로 발급. "
                                 "관리 콘솔이 아닌 CLI 발급이다.",
                "scope_model": "토큰은 `conversation.*` + `product.access.*` 스코프만 가진다. "
                               "관리 콘솔(`/api/admin/*`)·교차계정 데이터는 scope allowlist + 절대 "
                               "denylist(`*.any`·관리 네임스페이스)로 **접근 불가**. 타 계정 대화 열람/"
                               "조작도 owner-or-member 게이트로 차단.",
            },
            "endpoints": _CONVERSATION_ENDPOINTS,
            "errors": {
                "400": "잘못된 요청(빈 메시지·허용되지 않은 모델 등)",
                "401": "인증 실패(토큰 없음/만료/폐기/변조)",
                "403": "권한/스코프 부족(예: 관리 엔드포인트·타 계정 대화·발화 권한 없음)",
                "429": "동시 요청 제한 또는 토큰 사용량 quota 초과 — 잠시 후 재시도",
                "503": "LLM/자격증명 일시 불가",
            },
            "guide_url": origin + "/api/ai/guide",
            "mcp": {
                "description": "이 Conversation API 를 MCP tool 로 감싼 서버(선택 소비 경로).",
                "launcher": "bin/conversation-mcp.sh (gated, .env.conversation-mcp 에 토큰 주입)",
                "tools": ["ask", "new_conversation", "list_conversations", "get_history"],
            },
            "excluded": "관리 콘솔(`/api/admin/*`)·인증/계정 관리는 의도적으로 미노출이며 토큰으로 접근 불가.",
            "notes": "사내 LAN 전제. 긴 응답은 /api/ask_result·/api/progress 로 폴링.",
        },
    }


@router.get("/.well-known/ai-conversation-api.json")
def well_known_ai_api(request: Request) -> JSONResponse:
    """기계판독 매니페스트(.well-known 관용 위치). 익명·static contract."""
    return JSONResponse(_manifest(request))


@router.get("/api/ai/manifest")
def ai_manifest(request: Request) -> JSONResponse:
    """매니페스트 alias(API 네임스페이스). 익명·static contract."""
    return JSONResponse(_manifest(request))


@router.get("/llms.txt")
def llms_txt() -> FileResponse:
    """LLM 발견 표준 파일(사이트 탐색 시 최우선 조회). static/llms.txt 서빙."""
    return app.FileResponse(app.STATIC_DIR / "llms.txt", media_type="text/plain; charset=utf-8")


@router.get("/api/ai/guide")
def ai_guide() -> FileResponse:
    """외부 AI 학습용 상세 API 가이드라인(markdown). static/ai-api-guide.md 서빙."""
    return app.FileResponse(app.STATIC_DIR / "ai-api-guide.md", media_type="text/markdown; charset=utf-8")


@router.get("/api/admin/openapi.json")
def admin_openapi(request: Request) -> JSONResponse:
    """전체 OpenAPI 스키마(admin 포함) — 개발자용. **console.access 필요**(익명 노출 대체).

    익명 /openapi.json 은 app.py 에서 비활성화됐다(admin 엔드포인트 스키마 유출 차단).
    권한 있는 관리자만 전체 스키마를 조회한다.
    """
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        _account, error = app._require_permission(request, conn, "console.access")
        if error:
            return error
    finally:
        conn.close()
    return JSONResponse(app.app.openapi())
