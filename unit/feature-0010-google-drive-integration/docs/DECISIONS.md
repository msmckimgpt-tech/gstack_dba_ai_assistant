---
doc_type: FEATURE_DECISIONS
feature_id: feature-0010-google-drive-integration
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-001 — per-account MCP 토큰 주입(seam A) 채택
- Status: accepted
- Date: 2026-06-23
- Context: "각 계정이 본인 Google Drive 에 연결". DBHub/SQL MCP 는 단일 자격증명(서비스 DSN) 서버라
  멀티테넌트 Drive 에 맞지 않는다. 세 선택지 — (A) 호출시 토큰 주입(공유 상태비저장 서버 + Bearer
  per-call), (B) 계정별 서버 세션(토큰으로 초기화한 프로세스/세션), (C) 서비스계정 도메인 위임.
- Decision: **(A) 호출시 토큰 주입**을 채택. 공유 `gdrive-mcp` 서버는 자격증명을 보관하지 않고,
  에이전트가 tools/call 직전 인증된 계정의 access_token 을 `Authorization: Bearer` 로 주입한다.
  계약은 `src/gdrive_mcp_seam.py`(`load_account_drive_access_token`/`build_gdrive_mcp_headers`/
  `inject_for_call`)로 실행 가능하게 명세. 토큰 평문은 요청 처리 시점 메모리에만 잠깐 존재.
- Consequences: (+) 임의 Google 계정 지원, 서버 무상태, 수명관리 단순. (+) 토큰이 서버에 안 남음.
  (−) Drive MCP 서버가 per-call Authorization 을 받도록 요구(off-the-shelf 단일유저 서버는 thin
  wrapper 필요). (−) Authorization 헤더 로그 마스킹을 활성화 cycle 에서 보장해야 함.
- Supersedes: —
- Superseded By: —

## ADR-002 — 인증 코드는 app.py 인라인(feature-0010 attribution)
- Status: accepted
- Date: 2026-06-23
- Context: Drive 토큰 store/라우트는 web 컨테이너(MySQL WebAccounts) 에서 실행돼야 한다. web 이미지
  Dockerfile(`unit/feature-0002-agent-core/src/Dockerfile`)은 feature-0002 `modules` + feature-0003 `src`
  만 `/app` 으로 복사한다. 신규 feature-0010 src 모듈은 빌드 미포함 → 런타임 미임포트.
- Decision: 인증/라우트/DDL 코드는 **app.py(feature-0003) 인라인** — 로그인 OAuth(TASK-20260619)·
  TOTP·datasource 암호화와 동일 선례. feature-0010 attribution 주석 + ANCHOR/MODIFY 로 소유권 추적.
  feature-0010 unit 은 docs + MCP scaffold(bin/compose/seam) + env 를 소유.
- Consequences: (+) 빌드 변경 0(토대 위험 최소). (+) 로그인 `_oauth_*` 헬퍼 직접 재사용. (−) app.py
  비대화 지속 + 물리/논리 소유권 분리(추적으로 보완). (−) seam 모듈은 활성화 cycle 에서 Dockerfile
  통합 또는 web 측 재배치 필요.
- Supersedes: —
- Superseded By: —

## ADR-003 — `WebGoogleDriveTokens` 스키마 + envelope 암호화
- Status: accepted
- Date: 2026-06-23
- Context: 계정별 OAuth access/refresh 토큰을 평문 없이 영속 저장해야 한다(SECURITY.md §1).
- Decision: 신규 `WebGoogleDriveTokens`(Id PK, UNIQUE(AccountId,Provider), AccessTokenEnc/RefreshTokenEnc/
  TokenExpiresAt/GrantedScopes/EncryptionVersion/IsConnected/RevokedAt). 토큰은 `cred_crypto`
  AESGCM(DEK, AAD=`gdrive:{account_id}`) — TOTP/datasource 선례 동형. `_ensure_web_tables` fast+slow 멱등.
  refresh_token 미발급 시 기존값 COALESCE 보존. Provider 컬럼은 향후 다른 외부저장소 확장 여지.
- Consequences: (+) KEK(.env.secret) 부재 시 DB 유출돼도 복호 불가. (+) AAD 로 계정간 암호문 재사용 차단.
  (−) KEK/DEK 미설정 환경은 토큰 저장 비활성(fail-closed) — datasource 암호화와 동일 전제.
- Supersedes: —
- Superseded By: —

## ADR-004 — Drive scope 기본값 = drive.readonly(최소권한)
- Status: accepted
- Date: 2026-06-23
- Context: Drive 접근 범위. readonly vs file(앱 생성 파일) vs full drive.
- Decision: 기본 `https://www.googleapis.com/auth/drive.readonly`. 쓰기 필요 시 operator 가
  `WEB_GDRIVE_SCOPES` 로 명시 승격하고 사람 재승인(SECURITY.md §16).
- Consequences: (+) 최소권한 기본값으로 사고 표면 축소. (−) 쓰기 유스케이스는 명시 승격 필요.
- Supersedes: —
- Superseded By: —
