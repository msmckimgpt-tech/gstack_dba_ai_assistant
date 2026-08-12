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
