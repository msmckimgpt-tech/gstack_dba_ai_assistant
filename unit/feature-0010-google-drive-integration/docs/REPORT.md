---
doc_type: REPORT
feature_id: feature-0010-google-drive-integration
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report — Google Drive 연동 토대

## 최근 진행 요약 (2026-06-23)

**범위**: 각 계정이 본인 Google Drive 에 연결할 수 있는 **기반 구조(인증 + MCP 구성)** scaffolding.
사용자 결정 = "전체 scaffolding" (AskUserQuestion, 2026-06-23). **연동 미수행 / 기본 비활성 / 외부
Google 호출 0건.** worktree: `ai/claude/feature-0010-google-drive-integration` (base c364320).

### 구현 완료
1. **인증 구조 (app.py, feature-0003 인라인)**
   - `WebGoogleDriveTokens` 테이블 — 계정별 암호화 access/refresh 토큰 + 만료/scope/연결상태.
     `_ensure_web_gdrive_tokens_schema` fast(`_ensure_seed_catchup`)+slow(`_ensure_web_tables`) 양 경로 멱등.
   - 토큰 헬퍼: `_gdrive_dek`(DEK 로드, `_totp_dek` 동형) · `_gdrive_store_tokens`(upsert, AAD=`gdrive:{id}`,
     refresh COALESCE 보존) · `_gdrive_connection_status`(메타데이터만) · `_gdrive_delete_tokens`.
2. **OAuth connect 라우트 (app.py)**
   - `GET /api/integrations/google-drive/status` (로그인 필요, 항상 가용)
   - `GET /api/integrations/google-drive/connect` (flag OFF→404, PKCE+서명 state[계정 aid]+bind 쿠키)
   - `GET /api/integrations/google-drive/callback` (state/bind/계정일치 검증 → code→token → 암호화 저장)
   - `POST /api/integrations/google-drive/disconnect` (로그인 필요, 토큰 삭제)
   - 로그인 OAuth `_oauth_pkce_pair`/`_oauth_state_encode`/`_oauth_state_decode`/`_oauth_b64url` 재사용.
3. **MCP 구성 scaffold**
   - `bin/gdrive-mcp.sh` — 런처 stub(비활성 시 no-op, 활성+CMD 미설정 시 fail-loud).
   - `docker-compose.yml` `gdrive-mcp` 서비스 — profile `gdrive`(기본 미기동), `.env`만 inherit(client_secret 불필요, 검증 패널 반영 — seam A 는 계정별 user 토큰 주입).
   - `unit/feature-0010.../src/gdrive_mcp_seam.py` — per-account 토큰 주입 seam(A) 실행가능 명세
     (`load_account_drive_access_token`/`build_gdrive_mcp_headers`/`inject_for_call`, `refresh_access_token`=TODO).
4. **env / 정책 문서**
   - `.env.oauth.example`: `WEB_GDRIVE_*`(ENABLED/CLIENT_ID/SECRET/REDIRECT_URI/SCOPES). `.env.oauth` gitignore 보호.
   - `.env.example`: `GDRIVE_MCP_*`(ENABLED/URL/TIMEOUT/IMAGE/PORT/CMD, 비-secret).
   - `docs/SECURITY.md` §16 신설(Drive 토큰 저장·강화 TODO) + `docs/ARCHITECTURE.md` feature map/의존성.

### 검증 결과
- `python3 -m py_compile app.py` → OK. `bash -n bin/gdrive-mcp.sh` → OK. `gdrive_mcp_seam.py` py_compile → OK.
- docker-compose YAML 파싱 OK(gdrive-mcp, profile [gdrive], 17 services). 기본 배포 무영향(profile gated + flag OFF).
- 기존 라우트/스키마 무회귀(인라인 추가만, 기존 함수 무수정).

### 보안 메모 (배포 전 강화 TODO — SECURITY.md §16)
- (a) access_token 만료 refresh 회전, (b) disconnect 시 Google revoke 백채널, (c) state 영속 비밀(멀티워커),
  (d) id_token/access_token 서명(JWKS) 검증, (e) Authorization 헤더 로그 마스킹. **활성화·배포는 사람 승인 필요.**

### Git 동기화 결과
- 커밋: 본 cycle commit (branch `ai/claude/feature-0010-google-drive-integration`, base `2bf81d7`)
- verify-completion: PASS (9/9 checks, CHECK#13 WARN-only — UI 표면 없음 사유 TEST.md §3 명시)
- Push: 완료 (§16.3 Step 4 — BLOCKED 없음 + 승인 대기 없음 → 자동 push)
- main 병합: **보류** (PR 생성은 외부 영향 행동 — 사용자 confirm 대기, 전역 정책)
- 충돌 해결: base stale(c364320) → 현재 main(2bf81d7) rebase 시 충돌 0 (stash→reset→pop, app.py 자동병합)

### 다음 액션
- (confirm 대기) PR 생성 + main 병합 + 배포. deploy_scope: included 이나 토대 비활성이라 web 재빌드해도 무행동 변화(DDL 멱등 생성만).
- 활성화는 별도 cycle: credential 주입 + flag ON + SECURITY §17.4 강화 TODO 충족(refresh 회전·revoke·JWKS·마스킹·tests).
