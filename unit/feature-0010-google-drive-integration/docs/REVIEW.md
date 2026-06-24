---
doc_type: REVIEW
feature_id: feature-0010-google-drive-integration
status: active
edit_policy: append-only
source_of_truth: true
---

# Review — Google Drive 연동 토대

## 2026-06-23 — 토대 scaffolding self-review (AI: claude)

### 판단 근거 / 위험 등급
- Risk: **Critical** (인증·OAuth 자격증명·계정별 토큰 영속·외부연동). §7.1 Plan-Review-Execute 적용 —
  Plan 제시 + AskUserQuestion confirm("전체 scaffolding") 후 Execute. SECURITY.md §3(승인 필요 변경)에
  따라 **활성화/배포는 사람 승인** 으로 분리. 본 cycle 은 비활성 토대만(외부 호출 0건).

### 보안 검토 (SECURITY.md 정합)
- §1 평문 비밀 미저장: 토큰은 `cred_crypto` AESGCM 만으로 저장, 평문/암호문 어떤 응답에도 비노출
  (`_gdrive_connection_status` 는 메타데이터만). ✅
- §2 비밀 분리: client_secret 은 `.env.oauth`(gitignore, 11번 라인 확인), `.env.example`/`.env.oauth.example`
  은 placeholder/빈값만. gdrive-mcp 서비스는 `.env`+`.env.oauth` 만 inherit(least-privilege). ✅
- AAD 바인딩 `gdrive:{account_id}` — 계정간 암호문 재사용 차단(InvalidTag). ✅
- 교차 연동 차단: connect 가 서명 state 에 계정 `aid` 포함, callback 이 현재 로그인 계정과 일치 강제. ✅
- CSRF/세션고정: 로그인 OAuth 와 동일 서명 state + bind 쿠키(httponly/samesite=lax/secure). ✅
- fail-closed: KEK/DEK 부재 시 저장 실패→error redirect(토큰 미저장). ✅

### 잔여 리스크 (배포 전 — §16 강화 TODO, 본 cycle 의도적 미수행)
- refresh 회전/Google revoke 백채널 미구현 → disconnect 가 로컬 삭제만(외부 토큰은 Google 측 만료까지 유효).
- id_token/access_token 서명(JWKS) 검증 미강화(로그인 토대와 동일 — 백채널 TLS+claim 으로 토대 방어).
- state 비밀 미설정 시 프로세스 기동마다 임의값(멀티워커 영속 X) — 로그인 토대와 동일 한계.
- 위 항목은 FUNCTION.md §4 Out of Scope + SECURITY.md §16 에 명시. 활성화 cycle 의 진입 조건.

### 검증 산출물
- py_compile(app.py, gdrive_mcp_seam.py) PASS · bash -n(gdrive-mcp.sh) PASS · compose YAML PASS.
- 기존 동작 무회귀(profile gated + flag OFF + 인라인 추가만).

### Panel/2차 의견
- 본 cycle 은 비활성 토대라 라이브 검증 불가. 활성화 cycle 진입 시 `/cso`(보안) + `/plan-eng-review`
  (아키텍처) 권장 — 특히 seam(A) Authorization 마스킹 + refresh 회전 동시성.

## REV-20260623-0001 [AGENT-TEAM:security+backend] §18.8 적대적 검증 패널 — ACCEPT-WITH-FIXES

§18.8 dispatch(auth/credential→security, schema/API→backend). 2 적대 reviewer 가 main 대비 diff 를
독립 검토. 두 판정 모두 **ACCEPT-WITH-FIXES** — 보안 코어는 견고, 수정 권고 반영 완료.

### Security reviewer (CSO mindset) — ACCEPT-WITH-FIXES
- 검증 통과: 교차계정 hijack 방어(state `aid` 서명 + callback `aid==세션` 강제, 토큰은 세션 계정에 저장),
  봉투 암호화 + AAD 대칭(`gdrive:{id}`), KEK/DEK 부재 fail-closed, 기본 비활성 404 + 외부호출 0(유일 outbound
  `_gdrive_exchange_code` 가 404 게이트 뒤), `/status` 토큰 무노출, 파라미터라이즈 SQL, `.env.oauth` gitignore.
- 권고: [MINOR] `gdrive-mcp` scaffold 에 client_secret(.env.oauth) 불필요 → **적용**(env_file=.env 만).
  [NIT] tests 부재 → 활성화 cycle 이월(FUNCTION §4).

### Backend/correctness reviewer — ACCEPT-WITH-FIXES
- 검증 통과: schema 양 경로 멱등 등록, upsert conflict target=UNIQUE(AccountId,Provider), `expires_in→DATETIME`
  UTC naive 정확, `COALESCE(VALUES(RefreshTokenEnc),RefreshTokenEnc)` refresh 보존, 전 심볼 모듈스코프 해소
  (NameError 0, `account['id']` 소문자 정확), seam import-safe + AAD 대칭, compose 기본 profile 무영향·restart 루프 없음, 라우트/헬퍼 이름 충돌 없음.
- 권고: [MAJOR-1] base stale(c364320, PR#386) — main 이 5커밋 전진(2bf81d7, sample-feedback 등) →
  **적용**(main 으로 rebase: stash→reset→pop, 충돌 0, app.py 368줄 순수추가/삭제0, sample-feedback 11건 보존 확인).
  [MAJOR-2] `.env.oauth` env_file required:true → profile 활성 시 파일 부재 에러 → **적용**(env_file 에서 .env.oauth 제거로 동시 해소).
  [NIT-1] PKCE verifier 가 서명 state 내 평문(로그인 토대 동형, deferred-by-design, FUNCTION §4).

### 적용 결과(재검증)
- rebase 후: `git diff main` 클린(app.py 추가만, sample-feedback revert 0). py_compile(app.py·seam) PASS, bash -n PASS, compose YAML PASS.
- 잔여 deferred(배포 전, SECURITY §17.4): refresh 회전 · Google revoke · JWKS · Authorization 마스킹 · state 영속비밀 · tests. 활성화 cycle 진입조건.
