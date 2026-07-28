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

## CHG-20260724-0004 (Minor §12.3 — API 발견 blackbox 검증 후속: 가이드 정확화 + 기계판독 OpenAPI)
- Date: 2026-07-24
- Related Requirement: REQ-20260722-conversation-api-access (발견 진입점 검증 후속)
- Summary: 서브에이전트에 URL 만 주고 발견·학습을 blackbox 검증한 결과(성공) 드러난 가이드 공백 보정.
  - #4 **`GET /api/ai/openapi.json` 신설** — 외부 AI 코드젠용 수기 OpenAPI 3.1(conversation-only,
    관리 제외, JSON Schema + 예제 + Bearer securityScheme). `app.openapi()`(admin 포함) 미사용.
  - #1 가이드 401 vs 403 계층 명확화(무토큰=401 신원없음 / 유효토큰-스코프밖=403).
  - #3 `/api/ask` 동기(블로킹) 계약 명시 + 폴링은 진행 중 run 관찰용(비동기 시작 엔드포인트 없음).
  - #5 base_url 정본=매니페스트 origin(가이드 예제 도메인은 예시) 주석.
  - #2 토큰 문의 연락처 — 매니페스트 `auth.contact`(env `AI_API_TOKEN_CONTACT`, 기본 placeholder).
  - llms.txt 에 openapi 링크. 매니페스트 errors/notes/openapi_url 보강.
- Files: `routers/ai_discovery.py`(_openapi_spec + route + manifest 보강), `static/{ai-api-guide.md,llms.txt}`,
  `docs/SECURITY.md`(§7 allowlist), `tests/test_ai_discovery.py`(+openapi·contact 계약), route golden.
- Impact: additive. 신규 익명 엔드포인트는 static contract(수기 OpenAPI, admin 제외, 데이터 0). 문서 정확화.
- Rollback Notes: 라우터/스펙/문서 revert. 완전 가역.

## CHG-20260728T103500-ai-claude-conversation-quality-controls (Major §12.3 — 외부 AI 대화 품질 조정 표면)
- Date: 2026-07-28
- Related Requirement: REQ-20260722-conversation-api-access (품질 조정 확장 —
  AC-20260728T103500-conversation-quality-controls-1~5)
- Summary: 외부 AI 가 대화 품질 5축(모델·추론 강도·제품·폴더 커스텀 지침·첨부)을 **발견하고
  조정**할 수 있게 했다. 모델·추론 강도는 이미 `/api/ask` 계약에 있었고, 실제 간극은 (a) 제품 축이
  발견 자료에 전무, (b) "내 토큰이 쓸 수 있는 값" 조회 경로 부재였다.
  - **`GET /api/ai/capabilities` 신설(인증 필수, 신규 권한 코드 0)** — 계정별 라이브 옵션 카탈로그.
    모델/제품은 작업 화면 선택기와 **같은 필터 함수** 재사용(표시-집행 정합), 폴더는 owner-scope
    스토어, `conversation_id` 동봉은 `_account_can_access_conversation` 게이트. 축별 독립 try 로
    부분 degrade. 권한 없는 축은 값 은닉 + `available:false` + 사유.
  - **익명 발견 자료는 포인터만** — 매니페스트에 `quality_controls{discover, axes[5]}` 추가하되
    계정별 값 목록은 싣지 않아 §7 "익명=static contract, 인스턴스 데이터 0" 불변식 보존.
  - **큐레이션 OpenAPI +6 path** (`/api/ai/capabilities`·`PATCH …/product`·`/api/folders`(GET,POST)·
    `PATCH /api/folders/{id}`·`PATCH …/folder`·`POST …/attachments`) + `Capabilities`/`Folder`/
    `QualityAxis` 스키마 + `AskRequest` 에 `product_mode`/`product_id`(신규 대화 한정 명시).
  - **가이드 §4.7 신설**(축별 표·curl 예제 4종·구 토큰 403 안내) + `llms.txt` 품질 조정 항목.
  - **MCP tool +7** (`list_capabilities`·`set_conversation_product`·`list_folders`·`create_folder`·
    `set_folder_instructions`·`move_conversation_to_folder`·`upload_attachment`) + `ask` 에
    `product_id`/`product_mode` 인자(기존 대화에 주면 조용한 무시 대신 명시 오류) + stdlib multipart 헬퍼.
  - **토큰 안전 기본 scope 에 `folder.` 확장** (`_API_TOKEN_SAFE_DEFAULT_SCOPES`, CLI
    `_ALLOWED_SCOPE_PREFIXES`/기본 발급값). 절대 denylist 무변경 — `.any`·관리 네임스페이스는 그대로 차단.
- Files: `unit/feature-0003-agent-web-ui/src/routers/ai_discovery.py`(capabilities +
  카탈로그/매니페스트/OpenAPI 확장), `unit/feature-0003-agent-web-ui/src/web_context.py`(scope 상수),
  `unit/feature-0003-agent-web-ui/src/static/{ai-api-guide.md,llms.txt}`,
  `unit/feature-0023-conversation-api-access/src/conversation_mcp_server.py`,
  `bin/{api-token-issue.sh,conversation-mcp.sh}`,
  `unit/feature-0003-agent-web-ui/tests/{test_ai_capabilities.py(신규 10),test_api_token_auth.py(+5),
  test_product_list_rbac.py(T9 강화),route_snapshot_p5b.json(골든 +1 route)}`,
  `docs/{SECURITY.md §25.1,ARCHITECTURE.md,ROUTEMAP.md,STATUS.md}`, feature docs.
- Impact: **additive**. 기존 인증/대화 경로 무회귀 — `/api/ask` body 계약 불변(제품 힌트는 기존
  신규-대화-한정 동작 그대로), 신규 권한 코드 0, 스키마 변경 0. 기존 발급 토큰은 저장된 scope 가
  유지되어 폴더 축이 닫힌 채 무회귀(열려면 재발급). 전체 회귀 2586 passed / 0 failed.
- Rollback Notes: 라우터·MCP·문서 revert + scope 상수 2곳 원복 + 골든 스냅샷 원복. 완전 가역
  (DB 마이그레이션 없음).
