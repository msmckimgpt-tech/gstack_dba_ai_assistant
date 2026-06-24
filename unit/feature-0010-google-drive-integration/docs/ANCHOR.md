---
doc_type: ANCHOR
feature_id: feature-0010-google-drive-integration
created_at: 2026-06-23T19:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0010-google-drive-integration — Google Drive 연동 토대

## §1. 외부 관점 요약
처음 코드를 여는 사람은 "Google 로그인 OAuth(TASK-20260619)가 이미 있는데 왜 Drive 연동 코드를
또 만들지? 그 토큰을 재사용하면 안 되나?" 라고 의문을 가질 수 있다. 이유: 로그인 OAuth 는
SSO(openid/email/profile)라 **토큰을 저장하지 않고 id_token claim 만 쓰고 버린다**. Drive 접근은
(a) `drive.readonly` 같은 **별도 scope**, (b) `access_type=offline` 의 **refresh_token**, (c) 계정마다
**영속 저장**이 필요해 근본적으로 다른 레이어다. 또 하나의 의문 — "왜 토대만 만들고 실제 연동을 안
하나?": 인증/외부연동/개인 Drive 접근은 Critical(SECURITY.md §3) 이라 활성화·배포에 사람 승인이
필요하고, 사용자 요청 자체가 "기반 구조만, 연동은 아직" 이었기 때문이다. 그래서 모든 경로가 기본
비활성(flag OFF → 404)이고 외부 Google 호출이 0건이다.

## §2. 대안 분기
- **Alt-A: 로그인 OAuth 에 Drive scope 를 합쳐 단일 흐름으로.** 페르소나: 흐름을 최소화하려는 팀.
  안 고른 이유: 로그인은 모든 사용자 필수·토큰 미저장인데 Drive 는 opt-in·토큰 영속이라 수명·동의·
  보안 표면이 다르다. 합치면 로그인마다 Drive 동의를 강요하거나 토큰 저장 정책이 뒤섞인다. → 분리.
- **Alt-B: 토큰을 별도 신규 모듈(feature-0010/src) 로 분리해 app.py 무수정.** 페르소나: 소유권 깔끔함
  중시 팀. 안 고른 이유: web 이미지 Dockerfile 이 feature-0002/0003 만 통합(unified ns)하고 feature-0010
  src 를 복사하지 않아 런타임 미임포트. 빌드 변경은 토대 범위 밖 위험. → 인증 코드는 로그인 OAuth·TOTP
  선례대로 app.py 인라인(feature-0010 attribution), 소유권은 ANCHOR/MODIFY 로 추적.
- **Alt-C(MCP seam): 서비스계정 도메인 위임(C).** 페르소나: 단일 Workspace 사내. 안 고른 이유: 임의
  Gmail/외부 계정 불가 + 위임 권한이 과대. "각 계정의 본인 Drive" 일반화에는 per-call 토큰 주입(A)이 맞다.

## §3. 가정된 사용 시나리오
6개월 후 다른 작업자가 이 연동을 **활성화**하는 cycle 을 맡는다. 그는 ANCHOR/FUNCTION/DECISIONS 만
읽고 다음을 파악할 수 있어야 한다: (1) Drive 토큰은 `WebGoogleDriveTokens` 에 `cred_crypto`(AAD=
`gdrive:{account_id}`)로 암호화돼 있고, (2) connect/callback 라우트는 이미 있으며 `WEB_GDRIVE_ENABLED=1`
+ credential 주입으로 켜지고, (3) 에이전트가 Drive 를 도구로 쓰려면 `src/gdrive_mcp_seam.py` 의
seam(A) 자리에 mcp_client 어댑터를 끼우고 `refresh_access_token()`/revoke 를 구현하면 된다. 즉 "어디를
켜고 무엇을 마저 구현할지" 가 코드와 문서로 못박혀 있어야 한다 — 폐쇄 루프로 재발명하지 않도록.

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님. 활성화/배포 milestone 시 사람이 append.)
