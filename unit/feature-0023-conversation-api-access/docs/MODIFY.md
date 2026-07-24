---
doc_type: MODIFY
feature_id: feature-0023-conversation-api-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260722-0001
- Date: 2026-07-22
- Related Requirement: REQ-20260722-conversation-api-access (AC-...-1~5)
- Summary: 외부 AI 프로그래매틱 접근용 Bearer API 토큰 인증(Phase 1) + Conversation
  API MCP 서버(Phase 2) 신설. 세션 쿠키와 별개 인증 경로, scope allowlist 로 관리
  엔드포인트 원천 차단, 발급은 콘솔 밖 CLI, MCP 서버로 대화 tool 노출.
- Files:
  - `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py`:
    `_ensure_web_api_tokens_schema` 신규 + fast/slow path 등록.
  - `unit/feature-0003-agent-web-ui/src/web_context.py`: `_sanitize_api_token`,
    `_extract_bearer_token`, `_parse_token_scopes`, `_permission_in_token_scopes`,
    `_get_account_by_api_token` 신규 + `_account_permissions` scope 교집합 +
    `_get_authenticated_account` Bearer fallback.
  - `unit/feature-0003-agent-web-ui/src/app.py`: import 블록에
    `_ensure_web_api_tokens_schema` 추가(app.X 노출).
  - `bin/api-token-issue.sh`: 발급/폐기/조회 CLI(inline python, 파라미터라이즈드).
  - `unit/feature-0023-conversation-api-access/src/conversation_mcp_server.py`: MCP 서버.
  - `bin/conversation-mcp.sh`: gated 런처.
  - `.mcp.json`: conversation-api 서버 등록. `.gitignore`+`.env.conversation-mcp.example`.
  - `unit/feature-0003-agent-web-ui/tests/test_api_token_auth.py`: 단위 테스트.
- Impact: **additive·비파괴**. 스키마는 `CREATE TABLE IF NOT EXISTS`. 인증은 세션 쿠키
  경로 무회귀(쿠키 유효 시 토큰 fallback 미발동). scope=None 이면 권한 무변경.
- Rollback Notes: 코드 revert 로 인증 경로 원복(토큰 인증 비활성). WebApiTokens 테이블은
  잔존해도 무해(참조하는 코드 없으면 dead). MCP 서버/런처는 gated OFF 기본이라 무영향.

## CHG-20260722-0002
- Date: 2026-07-22
- Related Requirement: REQ-20260722-conversation-api-access (라이브 e2e 후속 hotfix)
- Summary: `bin/api-token-issue.sh` 가 실행 서비스를 `web` 로 하드코딩해 무중단 배포
  환경(feature-0014 web-a/web-b)에서 "service web is not running" 으로 실패하던 결함 수정.
  running 서비스 자동 감지(web → web-a → web-b → agent) 추가. 라이브 e2e(admin 계정 토큰
  → /api/ask 200 + admin 엔드포인트 403 + 무토큰 401) 로 인증·scope 코어는 정상 확인됨 —
  본 수정은 발급 CLI 의 운영 편의성 결함만 해소(인증/scope 로직 무변경).
- Files: `bin/api-token-issue.sh` (서비스 감지 블록 추가).
- Impact: 호스트 스크립트 전용(web 이미지·배포 무관). 인증/scope 로직 불변.
- Rollback Notes: 감지 블록 revert 시 `web` 하드코딩으로 복귀(무중단 배포 환경에서 재실패).

## CHG-20260724-0003 (Major §12.3 — 외부 AI용 API 발견 진입점 + 학습 가이드라인)
- Date: 2026-07-24
- Related Requirement: REQ-20260722-conversation-api-access 확장(외부 AI 발견성/학습)
- Summary: 외부 AI 가 웹사이트를 탐색하며 Conversation API 를 자연스럽게 인지·학습하도록
  큐레이션된(관리 콘솔 제외) 익명 static 발견 자료 추가 + FastAPI 기본 openapi 익명 노출 차단.
  - 익명 발견: `GET /llms.txt`(LLM 표준)·`GET /.well-known/ai-conversation-api.json`(매니페스트)·
    `GET /api/ai/manifest`(alias)·`GET /api/ai/guide`(상세 가이드라인 markdown).
  - `routers/ai_discovery.py` 신규(자동 등록). 매니페스트 카탈로그 `_CONVERSATION_ENDPOINTS`는
    수기 관리 정본(자동 introspection 아님 — admin 유출 방지).
  - **SEC-20260724**: FastAPI 기본 `/openapi.json`·`/docs`·`/redoc`(admin 포함 전체 스키마
    익명 유출) 비활성화(`docs_url=None,redoc_url=None,openapi_url=None`). 전체 스키마는
    admin-gated `GET /api/admin/openapi.json`(console.access)로 대체.
  - `static/index.html` head 에 발견 포인터(`<link rel="ai-conversation-api">` + meta, 화면 무영향).
  - `static/llms.txt`·`static/ai-api-guide.md` 신규. SECURITY.md §7 allowlist + §7.1 발견 네임스페이스 정책.
- Files: `routers/ai_discovery.py`(신규), `app.py`(FastAPI 설정), `static/{llms.txt,ai-api-guide.md,index.html}`,
  `docs/SECURITY.md`, `tests/test_ai_discovery.py`(신규 6 계약·불변식 테스트).
- Impact: additive. 신규 익명 엔드포인트는 static contract 전용(인스턴스 데이터 0·conversation only).
  openapi 비활성화는 익명 스키마 유출 제거(개발자 admin-gated 대체) — 기존 인증/대화 경로 무영향.
- Rollback Notes: 라우터/파일 revert + FastAPI 설정 원복(openapi 재노출). 완전 가역.
