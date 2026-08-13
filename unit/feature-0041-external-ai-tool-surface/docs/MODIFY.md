---
doc_type: MODIFY
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260812-0001
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: feature 신설 + 계획 산출물 작성. 외부 AI가 **자기 계정 LLM으로 추론**하면서 본
  서비스의 데이터소스·RAG에 접근하는 도구 표면의 방향(ANCHOR)·명세(FUNCTION)·구현 계획
  (TASK §2.1)을 확정. 코드 변경 0 — 계획 승인 대기 상태.
- Files:
  - `unit/feature-0041-external-ai-tool-surface/**` (신규 — `unit/_template` 복제 후 docs 3종 작성)
  - `unit/feature-0023-conversation-api-access/docs/ANCHOR.md` (§1 방향 분기 문단 추가 —
    `ask` 축 유지 · 원시 도구 축은 0041로 분리)
- Impact: 런타임 무영향(문서만). feature-0023 동작·scope·절대 denylist 무변경.
  후속 구현은 Critical 등급이라 §7.1 PLAN-APPROVED 이후 착수.
- Rollback Notes: 단일 커밋 revert. 신규 디렉터리 삭제 + 0023 ANCHOR §1 문단 제거로 원복.

## CHG-20260812-0002
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface (PLAN-APPROVED 2026-08-12)
- Summary: P0 구현. 보안 코어 4모듈 + REST 표면 2라우터 + MCP stdio 어댑터 + 스키마 5종.
  테스트 89건. **라이브 배포·e2e 는 미실시**.
- Files:
  - `unit/feature-0002-agent-core/alembic/versions/20260812_0055_tool_call_usage.py` (신규)
  - `unit/feature-0003-agent-web-ui/src/routers/{oauth_as,ai_tools}.py` (신규)
  - `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py` (`_ensure_oauth_client_schema`
    — WebOAuthClients/Grants/Tokens/WebAiTasks · fast/slow 양 경로 호출)
  - `unit/feature-0003-agent-web-ui/src/app.py` (재수출 1줄)
  - `unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json` (228→236, 신규 8 route)
  - `unit/feature-0041-external-ai-tool-surface/src/{session_guard,tool_authz,oauth_store,
    tool_ledger,external_tool_mcp_server}.py` (신규)
  - `unit/feature-0041-external-ai-tool-surface/tests/*` (5파일 89건)
  - `docs/SECURITY.md` §44 신설 · `docs/ARCHITECTURE.md` feature/의존 표 · `docs/STATUS.md`
- Impact: **기존 경로 무변경** — `modules/tools.py` 미수정, feature-0023 `ask` 축 무변경,
  내부 대화 경로는 새 authz seam 을 거치지 않는다. 신규 route 8개는 전부 OAuth 토큰 뒤.
  마이그레이션 0055 는 additive(expand-safe, migrate-lint PASS).
- Rollback Notes: route 8개는 라우터 파일 2개 삭제로 사라진다(자동 등록이라 배선 편집 불필요).
  alembic downgrade 0055 는 DROP TABLE(신규 테이블이라 데이터 손실 없음). MySQL 신규 테이블 4종은
  남겨도 무해(참조 없음).

## CHG-20260812-0003
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: **배포 전 발견 — catchup 체인 보호.** `_ensure_oauth_client_schema` 의
  `conn.cursor()` 가 try 밖에 있어, 커서 획득 실패가 `_ensure_seed_catchup`(운영 재기동
  fast path) 으로 전파되면 **뒤따르는 catchup 항목 6건이 조용히 skip** 되는 구조였다
  (gdrive 토큰·아바타 컬럼·첨부 버전·DB allowlist 규칙·**audit events**·**audit chain**).
  `docs/LEARNINGS.md` 의 seed-catchup abort 사례 + resource-acquire-outside-try 반복 결함과
  동일 기전.
- Files: `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py` ·
  `unit/feature-0041-external-ai-tool-surface/tests/test_bootstrap_catchup_isolation.py` (신규 7건)
- Impact: 신규 테이블 부재는 이 feature 엔드포인트만 fail-closed 로 막고(의도), 무관한
  서브시스템은 건드리지 않는다. 기존 동작 무변경.
- Rollback Notes: 해당 함수의 try 경계만 되돌리면 되나, 되돌릴 이유가 없다(순수 방어).

## CHG-20260812-0004
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: **라이브 배포 실패 → 근본 수정.** 서버측 모듈 4종을 feature-local `src/` 에서
  `unit/feature-0003-agent-web-ui/src/` 로 이동하고 라우터의 `sys.path` 주입을 제거.
- 발견 경위: `make deploy-web` 에서 web-a 가 기동 즉시
  `ModuleNotFoundError: No module named 'oauth_store'` 로 죽음. agent 이미지 Dockerfile 은
  feature-0002/src · shared · feature-0003/src 만 COPY 하므로 feature-0041 의 `src/` 는
  이미지에 존재하지 않는다. **단위 테스트는 repo 레이아웃에서 돌아 전부 통과**했다.
- Files:
  - `unit/feature-0003-agent-web-ui/src/{oauth_store,session_guard,tool_authz,tool_ledger}.py`
    (feature-0041 src 에서 `git mv`)
  - `unit/feature-0003-agent-web-ui/src/routers/{ai_tools,oauth_as}.py` (sys.path 주입 제거)
  - `unit/feature-0041-external-ai-tool-surface/tests/test_container_importability.py` (신규 5건)
  - 테스트 4파일 import 경로 정정
- Impact: 무중단 롤링이 설계대로 작동해 **사용자 영향 0** — web-b(구코드)가 계속 서빙했고
  Caddy 가 web-a 를 passive 격리했다. 라이브 확인: Caddy `/livez` 200(`git_commit=d619259d`).
  alembic 0055 는 이미 적용 완료(롤백 불필요 — additive).
- Rollback Notes: 모듈 위치 이동이라 되돌릴 이유 없음. 되돌리면 같은 기동 실패가 재현된다.

## CHG-20260812-0005
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: **라이브 배포 완료(`a68fbbac`) + POST-DEPLOY 12항 검증 기록** — 문서 전용.
- Files: `docs/TEST.md` §3 (POST-DEPLOY Run) · `docs/REPORT.md` · `docs/TASK.md`
- Impact: 코드 변경 0. 배포 사실과 검증 증적을 정본에 고정.
- Rollback Notes: 해당 없음(기록).

## CHG-20260812-0006
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: 잔여 3건 구현 — 발견 자료 · L4 권한 비대칭 flag · HTTP/SSE MCP 전송.
  codex 리뷰 P1 3건·P2 2건 전건 in-cycle 수정. 테스트 136건.
- Files:
  - `unit/feature-0003-agent-web-ui/src/routers/ai_discovery.py` (`tool_surface` 블록 ·
    `_TOOL_SURFACE_ENDPOINTS` 8종 · 큐레이션 OpenAPI 7 path)
  - `unit/feature-0003-agent-web-ui/src/static/ai-api-guide.md` (부록 B — 외부 AI 도구 표면)
  - `unit/feature-0003-agent-web-ui/src/tool_authz.py` (`permission_asymmetry` — 자카드 판정)
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` (L4 배선 · 원장 전용 · fan-out 상한)
  - `unit/feature-0041-.../src/external_tool_mcp_http.py` (신규 — HTTP/SSE 전송)
  - `unit/feature-0041-.../src/external_tool_mcp_server.py` (리다이렉트 금지)
  - `unit/feature-0041-.../tests/test_remaining_surface.py` (신규 30건)
- Impact: 발견 자료는 익명 노출 확대이나 **인스턴스 데이터 0** 불변식 유지(테스트 고정).
  L4 는 원장 전용이라 응답 계약 무변경. HTTP 전송은 신규 프로세스로 기존 경로 무영향.
- Rollback Notes: HTTP 전송은 파일 삭제로 소멸(배선 없음). 발견 자료·L4 는 해당 블록 제거.

## CHG-20260812-0007
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: **콘솔 '외부 도구 한도' 탭을 이번 출하에서 제외** (사용자 결정 2026-08-12).
- Files: `docs/TASK.md` §5.1 · `docs/FUNCTION.md` §14
- Impact: 기능 공백 아님 — 상한은 `tool_ledger.DEFAULTS` 로 이미 집행 중이고 탭은 조절 UI다.
- Rollback Notes: 해당 없음(범위 결정 기록).

## CHG-20260812-0008
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: 2차 라이브 배포(`e1372f32`) + POST-DEPLOY 8항 검증 기록. 문서 전용.
- Files: `docs/TEST.md` §3 (3차 Run) · `docs/REPORT.md` §3.1 · `docs/TASK.md`
- Impact: 코드 0.
- Rollback Notes: 해당 없음(기록).

## CHG-20260812-0009
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: 잔여 3건 완결 — **HTTP/SSE 전송 라이브 기동**(compose 서비스 + 엣지 경로) ·
  **상한 콘솔 노출**(runtime_settings 슬라이스) · **전 구간 e2e 절차서**(사람 1회 개입).
  codex 리뷰 P1 4건·P2 2건 전건 in-cycle 수정. 테스트 161건.
- Files:
  - `docker-compose.yml` (`ext-tool-mcp` 신규 서비스 — `networks: [dbnet]` · HTTP 프로브 헬스체크)
  - `unit/feature-0002-agent-core/src/Dockerfile` (HTTP 어댑터 1개만 `/app/ext_tools/` 로 COPY)
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` (`handle /api/ai/mcp*` — 익명 401 선차단)
  - `bin/deploy-web.sh` (`WORKERS` 에 `ext-tool-mcp` 추가 — 롤아웃 스파인 편입)
  - `shared/runtime_settings.py` (`external_tool_surface` 그룹 4 knob)
  - `unit/feature-0003-agent-web-ui/src/tool_ledger.py` (`effective_limits` · `check_open_tasks`)
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` (`open_task` 에 RPM·미제출 게이트)
  - `unit/feature-0041-.../src/external_tool_mcp_http.py` (경로 정합 · replica failover · https 전수)
  - `unit/feature-0041-.../docs/E2E_RUNBOOK.md` + `scripts/e2e-authorize.sh` (신규)
  - `unit/feature-0041-.../tests/test_bringup_and_limits.py` (신규)
- Impact: 신규 컨테이너 1개(dbnet). 엣지에 경로 1개 추가 — `/api/ai/mcp*` 만 분기하고 나머지
  `/api/ai/*` 는 그대로 web 이 받는다. `open_task` 에 게이트 2종이 붙어 **한도 초과 시 429**
  (기존 200 이던 조합이 429 가 될 수 있음 — 기본값 기준 정상 사용에서는 도달하지 않는다).
- Rollback Notes: compose 서비스 제거 + Caddyfile `handle /api/ai/mcp*` 블록 제거로 원복.
  knob 은 삭제해도 `DEFAULTS` 가 남아 집행은 유지된다.

## CHG-20260813-0010
- Date: 2026-08-13
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: **라이브 기동 실패 3중 원인 수정** — ① agent 이미지에 `mcp` 미설치 ②
  MCP SDK 2.0 이 `mcp.server.fastmcp` 제거 ③ upstream 이 평문이 아니라 TLS.
  배포 실패 후 컨테이너에서 실제로 기동·프로토콜 왕복을 확인하고 고쳤다.
- Files:
  - `unit/feature-0002-agent-core/src/requirements.txt` (`mcp>=1.2.0`)
  - `unit/feature-0041-.../src/external_tool_mcp_http.py` (SDK 호환층 · ctx 기반 헤더 ·
    `_SniHTTPSConnection`/`_SniHTTPSHandler` · Host 헤더)
  - `unit/feature-0041-.../src/external_tool_mcp_server.py` (SDK 호환층)
  - `docker-compose.yml` (https upstream · rootCA 마운트 · SNI/Host 고정 · 평문 예외 제거)
  - `bin/deploy-web.sh` (`dump_service_logs` — 기동 실패 시 원인 노출)
  - `unit/feature-0041-.../tests/{test_bringup_and_limits,test_container_importability,
    test_remaining_surface}.py`
- Impact: `ext-tool-mcp` 가 실제로 기동한다. 다른 서비스는 이미지에 패키지 1개가 늘어날 뿐
  코드 경로 무변경. upstream 연결이 평문→**검증된 TLS** 로 강화됐다.
- Rollback Notes: compose 서비스 제거로 원복. `mcp` 의존은 남아도 무해(아무도 import 안 함).

## CHG-20260813-0011
- Date: 2026-08-13
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: 콘솔 상한을 **전용 패널**로 이동 — 배포 후 실제 렌더를 확인하니 그룹 미분류라
  `timeouts` 버킷으로 흘러 **'실행 타임아웃' 패널 안에 섞여** 있었다(문서는 별도 섹션이
  있는 것처럼 기술 — 과장이었다).
- Files:
  - `shared/runtime_settings.py` (`ext_tool` 버킷 + 응답 포함)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (패널 `ext-tool-limits` + 서브탭 nav)
  - `unit/feature-0003-agent-web-ui/src/static/admin/settings.js`
    (`mountExtToolLimitsPanel`·`renderExtToolLimits`·`RS_EXT_TOOL_KEYS`)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (미저장 dot 서브탭 라우팅)
  - `unit/feature-0041-.../tests/test_bringup_and_limits.py` (배치 회귀 4건)
- Impact: 기존 패널 4종 무변경(추가만). `timeouts` 버킷에서 4행이 빠져 나온다.
- Rollback Notes: 버킷 분기 제거 시 자동으로 이전 동작(timeouts 혼입)으로 돌아간다.

## CHG-20260813-0012
- Date: 2026-08-13
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: 배포 후 검증 증적 기록 — PB-0008 콘솔 패널 재검증(수정 전/후) + 라이브 엣지 경유
  MCP 전 구간 프로브. **문서 전용**(코드 0).
- Files: `docs/TEST.md` §3 (8·9차 Run) · `docs/REPORT.md` §3.3 ·
  `unit/feature-0003-agent-web-ui/docs/test-runs.d/REV-20260813T140000-ext-tool-limits-panel.md` §3·§4
  (+ evidence 2장)
- Impact: 코드 0.
- Rollback Notes: 해당 없음(기록).

## CHG-20260813-0013
- Date: 2026-08-13
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: **인증 접근성 재설계** — 셸 스크립트 없이 "URL 접속 → 로그인 → 허용" 으로 끝나게
  했다. 사용자 지적("특정 스크립트 실행은 접근성이 매우 낮다")의 뿌리는 **표준 discovery 부재**
  였고, 그 과정에서 **미로그인 사용자가 `/login` 404 를 보던 결함**과 **동의 화면 부재로 인한
  링크 클릭 탈취 경로**를 함께 잡았다.
- Files:
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py` (동의 흐름 3엔드포인트 ·
    RFC 8414/9728 메타데이터 4 · 콘솔 발급 2 · scope 정규화 · 강제변경 차단)
  - `unit/feature-0003-agent-web-ui/src/oauth_store.py` (`consume_consent_nonce` ·
    `issue_console_token`)
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` (401 `WWW-Authenticate` · scope 집행)
  - `unit/feature-0003-agent-web-ui/src/app.py` (`_AuthError.headers` — 선택 인자)
  - `unit/feature-0003-agent-web-ui/src/routers/static_pages.py` (`/ai/connect`)
  - `static/{oauth-consent,ai-connect}.{html,js}` · `static/ai-connect.css` ·
    `static/app/next-target.js` (신규)
  - `static/app/auth.js` · `static/app.js` (로그인 후 `?next=` 복귀 3경로)
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` (엣지 401 챌린지)
  - `docs/ROUTEMAP.md` · `tests/route_snapshot_p5b.json` (route +9 반영)
- Impact: **기존 401 응답 셰이프 무변경**(헤더는 준 곳에만). `authorize` GET 이 더 이상 코드를
  발급하지 않는다 — 이 URL 을 직접 호출하던 자동화가 있다면 동의 화면을 받는다(설계상 의도).
  scope 집행이 켜지므로 `data.read` 가 없는 토큰은 403 — 현행 발급물은 전부 `data.read` 다.
- Rollback Notes: 라우터·정적 파일 되돌림. 스키마 변경 없음(nonce 는 기존 `WebOAuthGrants` 재사용).
