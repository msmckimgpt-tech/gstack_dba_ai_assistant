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

import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

import app

# 토큰 발급 문의 연락처(운영자가 env 로 설정). 미설정 시 placeholder — 외부 AI 가 "어디로 문의"
# 를 알 수 있게 안내한다(REV FINDING #2, blackbox 검증에서 최대 통합 블로커로 지목).
# ⚠️ 이 값은 **익명 매니페스트로 공개**된다(SEC-20260724 REV LOW) — 운영자는 **팀/역할 채널**
# (예: 그룹 메일·티켓 큐)을 쓰고 개인 연락처·내부 전용 식별자는 넣지 않는다.
_TOKEN_CONTACT = str(os.getenv("AI_API_TOKEN_CONTACT", "") or "").strip() or (
    "이 배포의 서비스 운영자/관리팀 (연락처는 배포 환경별 — 운영자가 AI_API_TOKEN_CONTACT env 로 설정; "
    "익명 공개되므로 팀/역할 채널 권장)"
)

# static_pages(무인증 정적) 계열 — 발견 자료는 인증 게이트 없음. 순서는 파일명 순 뒤쪽이면 충분.
INCLUDE_ORDER = 9_500

router = APIRouter()


# ── 큐레이션 엔드포인트 카탈로그 (conversation-only — admin 제외, 수기 관리 정본) ──────────
_CONVERSATION_ENDPOINTS = [
    {
        "method": "POST", "path": "/api/ask",
        "summary": "메시지를 보내고 assistant 답변을 받는다(작업 화면 대화의 핵심).",
        "dispatch": "synchronous — 답변이 준비될 때까지 블로킹 후 `output` 에 담아 반환한다"
                    "(inprocess/worker 모드 모두 동일 동기 계약). 폴링 엔드포인트는 별도로 "
                    "진행 중 run 을 관찰할 때만 쓴다(비동기 시작 엔드포인트는 없음).",
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
    {"method": "GET", "path": "/api/ask_status", "summary": "해당 대화의 진행 중 run 상태 스냅샷(관찰용, ask 슬롯 미점유). "
                                                          "/api/ask 는 동기라 보통 불필요 — 긴 질의/타 세션 run 관찰 시에만 사용.",
     "request": {"conversation_id": "string — 이 대화의 최신/활성 run 을 반영"}, "response": {"status": "string"}},
    {"method": "GET", "path": "/api/ask_result", "summary": "해당 대화의 최근 완료 run 결과(read-only 관찰). /api/ask 응답으로 이미 받았으면 불필요.",
     "request": {"conversation_id": "string"}, "response": {"output": "string", "status": "string"}},
    {"method": "GET", "path": "/api/progress", "summary": "진행 중 run 의 단계(스텝) 관찰.",
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
                                 "관리 콘솔이 아닌 CLI 발급이다. self-serve 발급 엔드포인트는 없다.",
                "contact": _TOKEN_CONTACT,
                "scope_model": "토큰은 `conversation.*` + `product.access.*` 스코프만 가진다. "
                               "관리 콘솔(`/api/admin/*`)·교차계정 데이터는 scope allowlist + 절대 "
                               "denylist(`*.any`·관리 네임스페이스)로 **접근 불가**. 타 계정 대화 열람/"
                               "조작도 owner-or-member 게이트로 차단.",
            },
            "endpoints": _CONVERSATION_ENDPOINTS,
            "errors": {
                "400": "잘못된 요청(빈 메시지·허용되지 않은 모델 등) — 단, 토큰이 없으면 body 검증 전에 401.",
                "401": "인증 실패 — **토큰 없음/만료/폐기/변조**. 인증이 body 검증·권한보다 먼저다.",
                "403": "인증은 됐으나 권한/스코프 부족 — **유효 토큰인데** 관리 엔드포인트·타 계정 대화·발화권한 밖. "
                       "(무토큰은 403 이 아니라 401 이다 — 401=신원 없음, 403=신원 있으나 권한 없음.)",
                "429": "동시 요청 슬롯 제한 또는 토큰 사용량 quota 초과 — 지수 backoff 재시도.",
                "503": "LLM/자격증명 일시 불가 — 재시도.",
            },
            "openapi_url": origin + "/api/ai/openapi.json",
            "guide_url": origin + "/api/ai/guide",
            "mcp": {
                "description": "이 Conversation API 를 MCP tool 로 감싼 서버(선택 소비 경로).",
                "launcher": "bin/conversation-mcp.sh (gated, .env.conversation-mcp 에 토큰 주입)",
                "tools": ["ask", "new_conversation", "list_conversations", "get_history"],
            },
            "excluded": "관리 콘솔(`/api/admin/*`)·인증/계정 관리는 의도적으로 미노출이며 토큰으로 접근 불가.",
            "notes": "사내 LAN 전제. `/api/ask` 는 동기(블로킹)라 응답에 답변이 담긴다 — 폴링은 진행 중 "
                     "run 관찰용. 코드젠은 openapi_url(엄밀 스키마) 사용. base_url 은 이 매니페스트를 "
                     "서빙한 실제 origin 이 정본이다(가이드 예제의 도메인은 예시 — base_url 을 신뢰하라).",
        },
    }


def _openapi_spec(request: Request) -> dict:
    """외부 AI 코드젠용 큐레이션 OpenAPI 3.1 스펙 — **conversation-only(관리 콘솔 제외)**.

    app.openapi()(admin 포함 전체)와 별개로 수기 관리한다(§7.1 불변식 — introspection 유출 방지).
    엄밀 JSON Schema + 예제로 클라이언트 코드젠을 지원한다(REV FINDING #4)."""
    origin = str(request.base_url).rstrip("/")
    _ask_req = {
        "type": "object", "required": ["message"],
        "properties": {
            "message": {"type": "string", "description": "질문/메시지", "example": "최근 7일 신규 가입 수를 알려줘"},
            "conversation_id": {"type": "string", "description": "이어갈 대화 id. 생략 시 새 대화 생성"},
            "model": {"type": "string", "description": "모델(생략 시 서비스 기본). 허용 목록은 배포별 — 보통 생략 권장"},
            "reasoning_level": {"type": "string", "enum": ["low", "normal", "high", "max"], "description": "추론 강도(선택)"},
        },
    }
    _ask_resp = {
        "type": "object",
        "properties": {
            "output": {"type": "string", "description": "assistant 답변 본문"},
            "conversation_id": {"type": "string"},
            "executed_sql": {"type": "string", "description": "실행된 SQL(있으면)"},
            "error": {"type": "string", "description": "비어 있으면 성공"},
            "duration_ms": {"type": "number"},
        },
        "example": {"output": "최근 7일 신규 가입은 1,240명입니다.", "conversation_id": "20260724-3f2a",
                    "executed_sql": "SELECT COUNT(*) FROM ...", "error": "", "duration_ms": 1820.4},
    }
    _err = {"type": "object", "properties": {"error": {"type": "string"}}, "example": {"error": "로그인이 필요합니다."}}
    _errs = {
        "401": {"description": "인증 실패(토큰 없음/만료/폐기/변조). 인증이 body·권한보다 먼저.",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        "403": {"description": "유효 토큰이나 스코프/권한 밖(관리·타 계정·발화권한).",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        "429": {"description": "동시 슬롯 제한 또는 quota 초과 — backoff 재시도.",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
    }

    def _cid_param(required: bool) -> list:
        return [{"name": "conversation_id", "in": "query", "required": required,
                 "schema": {"type": "string"}, "description": "대상 대화 id"}]

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "mysql_ai Conversation API (AI-facing, curated)",
            "version": "1.0",
            "description": "외부 AI 용 큐레이션 스펙 — `conversation.*` 엔드포인트만. 관리 콘솔(`/api/admin/*`)은 "
                           "의도적으로 제외된다. 인증=Bearer(matk_). `/api/ask` 는 동기.",
        },
        "servers": [{"url": origin}],
        "security": [{"bearerAuth": []}],
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "matk"}},
            "schemas": {
                "AskRequest": _ask_req, "AskResponse": _ask_resp, "Error": _err,
                "Conversation": {"type": "object", "properties": {"conversation_id": {"type": "string"},
                                 "topic": {"type": "string"}, "updated_at": {"type": "string"}}},
                "Message": {"type": "object", "properties": {"id": {"type": "integer"}, "role": {"type": "string"},
                            "content": {"type": "string"}, "created_at": {"type": "string"}}},
            },
        },
        "paths": {
            "/api/ask": {"post": {
                "summary": "메시지 전송 → assistant 답변(동기·블로킹).", "operationId": "ask",
                "requestBody": {"required": True, "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/AskRequest"}}}},
                "responses": {"200": {"description": "답변", "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/AskResponse"}}}},
                    "400": {"description": "빈 메시지·허용 안 된 모델"}, **_errs}}},
            "/api/new_conversation": {"post": {
                "summary": "새 대화 생성.", "operationId": "newConversation",
                "responses": {"200": {"description": "생성됨", "content": {"application/json": {"schema": {
                    "type": "object", "properties": {"conversation_id": {"type": "string"}}}}}}, **_errs}}},
            "/api/conversations": {"get": {
                "summary": "내(토큰 계정) 대화 목록.", "operationId": "listConversations",
                "parameters": [{"name": "cursor", "in": "query", "required": False, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "목록", "content": {"application/json": {"schema": {
                    "type": "object", "properties": {"items": {"type": "array", "items": {
                        "$ref": "#/components/schemas/Conversation"}}}}}}}, **_errs}}},
            "/api/history": {"get": {
                "summary": "대화 이력(본인 소유/멤버만; 아니면 빈 결과).", "operationId": "history",
                "parameters": _cid_param(True),
                "responses": {"200": {"description": "이력", "content": {"application/json": {"schema": {
                    "type": "object", "properties": {"conversation_id": {"type": "string"}, "messages": {
                        "type": "array", "items": {"$ref": "#/components/schemas/Message"}}}}}}}, **_errs}}},
            "/api/ask_status": {"get": {"summary": "진행 중 run 상태(관찰).", "operationId": "askStatus",
                "parameters": _cid_param(True), "responses": {"200": {"description": "상태"}, **_errs}}},
            "/api/ask_result": {"get": {"summary": "최근 완료 run 결과(관찰).", "operationId": "askResult",
                "parameters": _cid_param(True), "responses": {"200": {"description": "결과"}, **_errs}}},
            "/api/progress": {"get": {"summary": "진행 단계(스텝) 관찰.", "operationId": "progress",
                "parameters": _cid_param(True), "responses": {"200": {"description": "스텝"}, **_errs}}},
            "/api/cancel": {"post": {"summary": "진행 중 ask 취소.", "operationId": "cancel",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {
                    "type": "object", "required": ["conversation_id"],
                    "properties": {"conversation_id": {"type": "string"}}}}}},
                "responses": {"200": {"description": "취소"}, **_errs}}},
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


@router.get("/api/ai/openapi.json")
def ai_openapi(request: Request) -> JSONResponse:
    """외부 AI 코드젠용 큐레이션 OpenAPI 3.1 — conversation-only(관리 콘솔 제외). 익명·static contract."""
    return JSONResponse(_openapi_spec(request))


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
