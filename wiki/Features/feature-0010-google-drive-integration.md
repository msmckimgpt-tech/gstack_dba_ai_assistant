---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: stub
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
feature_id: feature-0010-google-drive-integration
linked_unit: unit/feature-0010-google-drive-integration
created: 2026-06-23
sources:
  - ../../unit/feature-0010-google-drive-integration/docs/FUNCTION.md
---

# Feature — Google Drive 연동 토대

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0010-google-drive-integration/docs/FUNCTION|unit/feature-0010-google-drive-integration/docs/FUNCTION.md]].

## 1. 한 줄 요약

각 사용자 계정이 본인 Google Drive 를 연결하는 멀티테넌트 연동의 **인증 구조 + MCP 구성 토대** (연동 미수행 / 기본 비활성).

## 2. 상태

- **단계**: stub (토대 scaffolding — 라이브 연동·UI·refresh 회전은 활성화 cycle 이월)
- **마지막 갱신**: 2026-06-23
- **AI 작업자**: claude (TASK-20260623T190000-gdrive-foundation)

## 3. 책임 경계

- **입력**: `WEB_GDRIVE_*`(.env.oauth) / `GDRIVE_MCP_*`(.env) · 로그인 세션 · (활성 시) Google OAuth code.
- **출력**: `WebGoogleDriveTokens` 암호화 토큰 행 · `/api/integrations/google-drive/{status,connect,callback,disconnect}` · `/status` 메타데이터.
- **side-effect**: 계정별 OAuth 토큰을 `cred_crypto`(AAD=`gdrive:{account_id}`)로 암호화 저장. 평문/외부 호출 0건(토대).

## 4. 관련 정본

- [[../../unit/feature-0010-google-drive-integration/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0010-google-drive-integration/docs/TASK|TASK.md]] — 작업 컨텍스트 (active)
- [[../../unit/feature-0010-google-drive-integration/docs/DECISIONS|DECISIONS.md]] — ADR(seam A / app.py 인라인 / 스키마 / scope)
- [[../../unit/feature-0010-google-drive-integration/docs/ANCHOR|ANCHOR.md]] — 방향성 stable reference

## 5. 관련 노트

- [[feature-0003-agent-web-ui]] — 인증 코드·라우트·DDL 의 물리 위치(app.py, cross-feature touch)
- [[feature-0007-bedrock-llm-provider]] — per-user 자격증명 폐기→서비스관리 선례(대비: Drive 는 계정별 저장)
- [[../Decisions/_Index|Decisions MOC]] — 관련 ADR

## 6. Open questions / 미해결

- per-account MCP seam(A) Authorization 헤더 로그 마스킹 + refresh 회전 동시성(활성화 cycle).
- disconnect 시 Google revoke 백채널 + id_token/access_token 서명(JWKS) 검증 강화.
- 설정 UI(연결 버튼/상태) 미구현 — 현재 백엔드 API 만.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0010-google-drive-integration/docs/MODIFY.md` 에.

- 2026-06-23: 초안 작성 (feature 신규 생성 동반, 토대 scaffolding).
