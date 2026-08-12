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
