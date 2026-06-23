---
doc_type: FUNCTION
feature_id: feature-0010-google-drive-integration
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function — Google Drive 연동 토대

## 1. Summary
각 사용자 계정이 **본인의 Google Drive** 를 서비스에 연결할 수 있게 하는 멀티테넌트 연동의
**인증 구조 + MCP 구성 토대**다. 본 cycle 범위는 "연동 미수행(no live connection)" — 구조(스키마·
암호화 토큰 저장·OAuth connect 라우트·MCP 서버 seam·env 설정)만 구축하고 **기본 비활성**이다.
계정별 OAuth access/refresh 토큰을 `cred_crypto`(KEK/DEK envelope, AAD=`gdrive:{account_id}`)로
암호화 저장하며, 로그인용 Google OAuth(SSO, TASK-20260619T034522)와는 별개 레이어다(Drive scope +
offline access + 토큰 영속 저장).

## 2. Goal
- REQ-20260623-0001: 각 계정이 본인 Google Drive 에 연결할 수 있는 **기반 구조**를 구현한다(연동은 아직 안 함).
- REQ-20260623-0002: 연동에 필요한 **MCP 구성**(Google Drive MCP 서버 자리표 + per-account 토큰 주입 seam)을 scaffold 한다.
- REQ-20260623-0003: **인증 구조**(계정별 OAuth 토큰의 암호화 저장 + connect/disconnect/status 경로)를 구축한다.

## 3. In Scope
- `WebGoogleDriveTokens` 테이블(계정별 암호화 access/refresh 토큰 + 만료/scope/연결상태). `_ensure_web_tables` fast+slow 양 경로 멱등 생성.
- 토큰 저장/조회/삭제 헬퍼(`_gdrive_store_tokens`/`_gdrive_connection_status`/`_gdrive_delete_tokens`) — `cred_crypto` 재사용, AAD 바인딩.
- OAuth connect 흐름 라우트(`/api/integrations/google-drive/{status,connect,callback,disconnect}`) — 로그인 사용자 귀속, PKCE+서명 state, **기본 비활성(flag OFF → 404)**.
- MCP 구성 scaffold: `bin/gdrive-mcp.sh`(런처 stub) + docker-compose `gdrive-mcp` 서비스(profile `gdrive`, 기본 비활성) + per-account 토큰 주입 seam 모듈(`src/gdrive_mcp_seam.py`).
- env 설정: `.env.oauth.example`(WEB_GDRIVE_* client config) + `.env.example`(GDRIVE_MCP_* 런타임).

## 4. Out of Scope
- **실제 Google API 호출 / 라이브 연동**(토큰 교환은 flag OFF 로 도달 불가 — 외부 네트워크 호출 0건).
- access_token 만료 시 refresh_token **회전**(seam 명세만 — `refresh_access_token()` = NotImplementedError).
- disconnect 시 Google **revoke endpoint 백채널** 호출(로컬 삭제만).
- id_token/access_token **서명(JWKS) 검증** 강화(로그인 토대와 동일 — 배포 전 TODO).
- Drive 파일을 LLM 컨텍스트로 주입하는 **에이전트 도구 배선**(MCP 서버 실구현 + mcp_client 연결).
- **설정 UI**(연결 버튼/상태 표시) — 백엔드 status/connect/disconnect API 만 제공(프론트는 후속).

## 5. Inputs
- `WEB_GDRIVE_ENABLED` / `WEB_GDRIVE_CLIENT_ID` / `WEB_GDRIVE_CLIENT_SECRET` / `WEB_GDRIVE_REDIRECT_URI` / `WEB_GDRIVE_SCOPES` (`.env.oauth`).
- `GDRIVE_MCP_ENABLED` / `GDRIVE_MCP_URL` / `GDRIVE_MCP_IMAGE` / `GDRIVE_MCP_PORT` / `GDRIVE_MCP_CMD` (`.env`).
- 로그인 세션 쿠키(`mysql_ai_session`) → `_get_authenticated_account` → `account['id']`.
- (활성 시) Google OAuth authorization code(callback query) + KEK(`.env.secret`)/DEK.

## 6. Outputs
- `WebGoogleDriveTokens` 행(계정별 암호화 토큰). 평문 토큰은 어떤 컬럼/로그에도 저장하지 않음.
- `/status` JSON(연결 메타데이터 — `connected`/`configured`/`scopes`/`token_expires_at`, 토큰 비노출).
- `/connect` 302 redirect(Google 동의 화면) / `/callback` 302 redirect(`/?gdrive_connected=1` 또는 `?gdrive_error=*`).
- `/disconnect` JSON(`{ok, connected:false}`) + 저장 토큰 삭제.

## 7. Main Flow
1. (활성 시) 로그인 사용자가 `/api/integrations/google-drive/connect` 진입.
2. PKCE verifier/challenge + 서명 state(계정 id `aid` 포함) + bind 쿠키 생성 → Google authz redirect(`access_type=offline`, `prompt=consent`).
3. `/callback`: state 서명/TTL + bind 쿠키 + 개시 계정 일치 검증 → code→token 교환(백채널 TLS).
4. access/refresh 토큰을 `cred_crypto`(AAD=`gdrive:{account_id}`)로 암호화 → `WebGoogleDriveTokens` upsert.
5. `/status` 로 연결 상태 조회, `/disconnect` 로 토큰 삭제.

## 8. Edge Cases
- flag/credential 미설정 → connect/callback 404(토대 기본). status/disconnect 는 항상 가용.
- KEK/DEK 부재 → `_gdrive_store_tokens`=False → `?gdrive_error=store`(토큰 미저장, fail-closed).
- refresh_token 미발급(재동의 없는 갱신) → 기존 RefreshTokenEnc 보존(COALESCE), access 만 갱신.
- 개시 계정 ≠ 콜백 계정 → `?gdrive_error=account`(교차 연동 차단).
- 사용자가 동의 거부 → `?gdrive_error=denied`.

## 9. Error Handling
- 모든 토큰 암호화/DB 실패는 fail-closed(저장 안 함, error redirect). 평문 토큰 메모리 즉시 폐기.
- DB 연결 실패 → 500 / 서버 error redirect. 롤백 보장(`conn.rollback()`).
- 활성화 전(토대)에는 외부 네트워크 경로 도달 불가 → 외부 장애 표면 없음.

## 10. Dependencies
### 내부 기능 의존성
- feature-0003-agent-web-ui: `app.py`(인증 코드·라우트·`WebGoogleDriveTokens` DDL 물리 위치, cross-feature touch — ANCHOR §2 참조), `_get_authenticated_account`, 로그인 OAuth `_oauth_*` 헬퍼 재사용.
- feature-0002-agent-core: `modules/cred_crypto`(envelope 암호화) + `modules/datasources`(DEK 발급/조회). 활성화 cycle 에서 `modules/mcp_client` 연결 예정.

### 외부 의존성
- Google OAuth 2.0(`accounts.google.com`/`oauth2.googleapis.com`) — **활성화 시에만**.
- Google Drive MCP 서버(operator 선택 — 토대 단계 placeholder).

### shared 모듈 의존성
- 없음.

## 11. Acceptance Criteria
- AC-0001: `WebGoogleDriveTokens` 가 fast+slow 양 경로에서 멱등 생성된다(기존 배포 무회귀).
- AC-0002: 토큰은 `cred_crypto` AESGCM(AAD=`gdrive:{account_id}`)로만 저장되고 평문은 어디에도 남지 않는다.
- AC-0003: `WEB_GDRIVE_ENABLED=0`(기본)에서 connect/callback 은 404 이고 외부 Google 호출이 0건이다.
- AC-0004: status/disconnect 는 로그인(401 게이트) 후 본인 계정에만 작용한다.
- AC-0005: per-account MCP 토큰 주입 seam(A)이 `src/gdrive_mcp_seam.py` + DECISIONS.md 로 명세된다.
- AC-0006: `app.py` py_compile 통과 + 기존 라우트/스키마 무영향.

## 12. Observability
- connect/callback 결과는 redirect query(`gdrive_connected`/`gdrive_error=*`)로 표면 — 토큰값 미노출.
- `/status` 로 계정별 연결 상태 점검(운영/디버그).
- (활성화 cycle) Authorization 헤더 마스킹 + MCP 호출 trace 추가 예정.

## 13. Pre-approved Changes
- 없음(인증/외부연동 — 활성화·배포는 사람 승인 필요, SECURITY.md §3).
