---
doc_type: MODIFY
feature_id: feature-0010-google-drive-integration
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log — Google Drive 연동 토대

## CHG-20260623-0001 — Google Drive 연동 토대 scaffolding (TASK-20260623T190000-gdrive-foundation)

### 신규 파일
- `unit/feature-0010-google-drive-integration/` — feature unit(_template 복제) + docs 8종.
- `unit/feature-0010-google-drive-integration/src/gdrive_mcp_seam.py` — per-account 토큰 주입 seam(A) 명세.
- `bin/gdrive-mcp.sh` — Drive MCP 런처 stub(비활성 no-op).

### 변경 파일 (cross-feature touch — ADR-002 근거)
- `unit/feature-0003-agent-web-ui/src/app.py`:
  - 로그인 OAuth 콜백 직후(구 18182 부근)에 **feature-0010 섹션 1블록 삽입**: 설정 상수(`GDRIVE_*`) +
    `_ensure_web_gdrive_tokens_schema` + 토큰 헬퍼(`_gdrive_dek`/`_gdrive_store_tokens`/
    `_gdrive_connection_status`/`_gdrive_delete_tokens`) + OAuth 헬퍼(`_gdrive_configured`/
    `_gdrive_authorize_url`/`_gdrive_exchange_code`/`_gdrive_callback_redirect`) + 4 라우트.
  - `_ensure_seed_catchup`(fast path) + `_ensure_web_tables`(slow path)에 `_ensure_web_gdrive_tokens_schema(conn)`
    호출 각 1줄 추가(2FA TOTP 호출 직후).
- `docker-compose.yml`: `gdrive-mcp` 서비스 추가(profile `gdrive`, mcp 서비스 직후).
- `.env.oauth.example`: `WEB_GDRIVE_*` 블록 append.
- `.env.example`: `GDRIVE_MCP_*` 블록 append.
- `docs/SECURITY.md`: §16 "Google Drive 연동 토큰 저장" append.
- `docs/ARCHITECTURE.md`: §4 feature map + §6 의존성 맵에 feature-0010 행 추가.

### 무변경 보장
- feature-0002 `modules/mcp_client.py`(에이전트 hot-path) **무수정** — seam(A)은 명세만, 런타임 미배선.
- 기존 라우트/스키마/함수 무수정(인라인 추가 + 멱등 DDL 호출만).
