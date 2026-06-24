---
doc_type: TASK
feature_id: feature-0010-google-drive-integration
task_id: TASK-20260623T190000-gdrive-foundation
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task — Google Drive 연동 토대

## 1. Current Status
- State: in-progress (토대 scaffolding 구현 완료 — verify/commit 잔여)
- Owner: AI (claude) / Human (sign-off 대기)
- Priority: high
- Risk: Critical (인증·OAuth 자격증명·계정별 토큰 영속·외부연동)
- Last Updated: 2026-06-23

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - feature-0003-agent-web-ui: `src/app.py` — `WebGoogleDriveTokens` DDL(`_ensure_web_gdrive_tokens_schema`, fast+slow 양 경로) + 토큰 store/status/delete 헬퍼 + OAuth connect 헬퍼(로그인 `_oauth_*` 재사용) + 4 라우트(status/connect/callback/disconnect).
  - feature-0010(신규 unit): `src/gdrive_mcp_seam.py`(per-account 토큰 주입 seam A) + docs.
  - 인프라: `bin/gdrive-mcp.sh`(런처 stub) + `docker-compose.yml`(gdrive-mcp 서비스, profile gdrive) + `.env.oauth.example`(WEB_GDRIVE_*) + `.env.example`(GDRIVE_MCP_*).
  - 정책: `docs/SECURITY.md`(§16 Drive 토큰 저장) + `docs/ARCHITECTURE.md`(feature map/의존성).
- **접근 방법:** 로그인 OAuth(TASK-20260619)·TOTP·datasource 암호화 선례를 그대로 재사용. 토큰은
  `cred_crypto` envelope(AAD=`gdrive:{account_id}`). 모든 경로 기본 비활성(flag OFF → 404), 외부 호출 0건.
  per-account MCP 는 단일자격증명 서버가 아닌 호출시 토큰 주입(seam A).
- **위험도:** Critical
- **검증:** py_compile + bash -n + compose YAML + verify-completion. 활성화/배포는 사람 승인.

<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 (AskUserQuestion: "전체 scaffolding (권장)") -->

## 3. Task Queue (슬라이스)
- [x] **S1 인증 구조** — `WebGoogleDriveTokens` DDL(fast+slow) + `cred_crypto` 토큰 store/status/delete 헬퍼(AAD 바인딩).
- [x] **S2 OAuth connect 라우트** — status/connect/callback/disconnect, PKCE+서명 state(계정 바인딩), flag OFF→404, code→token 교환 함수(활성 시만 도달).
- [x] **S3 MCP 구성 scaffold** — `bin/gdrive-mcp.sh` 런처 stub + docker-compose `gdrive-mcp`(profile gdrive) + `src/gdrive_mcp_seam.py`(seam A) + `.env` 설정.
- [x] **S4 문서** — FUNCTION/ANCHOR/DECISIONS/REPORT/REVIEW/MODIFY/TEST/WIKI_CARD + SECURITY.md §17 + ARCHITECTURE.md + wiki 카드/_Index/Log/hot.
- [x] **S5a 검증 패널** — §18.8 security+backend 적대 검증(REV-20260623-0001, ACCEPT-WITH-FIXES). 권고 반영: base rebase(MAJOR-1) + gdrive-mcp env_file `.env.oauth` 제거(MAJOR-2/MINOR-1).
- [x] **S5b base rebase** — stale base(c364320) → 현재 main(2bf81d7) rebase 완료(충돌 0, sample-feedback 보존, app.py 추가만).
- [ ] **S5c commit/push** — verify-completion PASS 후 commit/push(사용자 확인). deploy_scope: included 이나 토대 비활성이라 web 재빌드 무영향(배포 skip 가능).

## 4. 활성화 cycle 로 이월(Out of Scope — 본 cycle 미수행)
- 실 Google 토큰 교환 라이브 검증(credential 주입 + flag ON).
- `refresh_access_token()` 구현(만료 회전) + disconnect 시 Google revoke 백채널.
- Drive MCP 서버 실구현 + `mcp_client` seam(A) 어댑터 배선 + 에이전트 도구 노출.
- 설정 UI(연결 버튼/상태) + id_token/access_token 서명(JWKS) 검증 강화.

## 5. Notes
- cross-feature touch(app.py = feature-0003 물리 위치, feature-0010 소유) — ANCHOR §2 Alt-B 근거. MODIFY.md 에 라인 기록.
- 로그인 OAuth 와 동일 GCP 클라이언트 공유 가능(WEB_GDRIVE_CLIENT_ID 비우면 WEB_OAUTH_GOOGLE_* fallback).
