---
doc_type: REVIEW
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260812-0001 [CODEX:plan-docs] — accepted

- Related Change: CHG-20260812-0001 (feature 신설 + 계획 산출물)
- Reason: AGENTS.md §18.8 검증 패널. 위험도 Critical(인증·인가 + 신규 데이터 유출면)이라
  security 렌즈 필수인데 세션에 Agent-tool 제약이 걸려 있어, feature-0030(2026-07-29 사용자
  확인) 선례대로 §18.8.2 정합 경로인 `/codex review` 를 채택했다.
- 실행: `codex exec -s read-only` + `git diff --cached` (첫 시도는 프롬프트 길이로 5분 게이트
  타임아웃 — 최소 프롬프트로 재시도 성공, 52,962 tokens). GATE: **FAIL (P1 3건)** → 전건
  in-cycle 수정 후 본 엔트리 기록.

### 지적 사항과 처리

1. **[P1] 원장 fail-open ↔ AC-6 모순** (FUNCTION.md §9)
   원장 기록 실패를 best-effort로 두면 호출이 누적 한도에서 누락돼 "모든 호출이 기록되고 상한
   초과 시 429"라는 AC-6과 충돌한다. → **수정**: 원장 기록·예산 차감을 **결과 반환 전 원자적
   커밋**으로 승격하고 실패 시 5xx(결과 미반환). 관측 전용 필드 결손만 best-effort 유지.
   완료 판정에 "기록 실패 주입 시 결과 미반환" 회귀 테스트 추가.

2. **[P1] OAuth 저장 계약 부재** (TASK.md §2.1)
   인가 코드 단회성·TTL, 토큰 해시 저장, refresh rotation/reuse 탐지, PKCE S256, redirect_uri
   결합이 계획·AC에 없었다. → **수정**: FUNCTION.md §3에 저장 계약 명시, `oauth_as.py` symbol에
   `_consume_auth_code`·`_rotate_refresh` 추가, `WebOAuthTokens`(해시 컬럼만) 신설,
   **AC-10** 신규.

3. **[P1] DCR redirect URI 정책 부재** (FUNCTION.md §3)
   "AI가 스스로 등록"이 결정사항이라 DCR이 열려 있는데 URI 제약이 없어 인가 코드 탈취·피싱
   표면이 생긴다. → **수정**: HTTPS 고정(loopback 예외)·정확 일치·등록 rate limit 명시,
   **AC-11** 신규.

4. **[P2] AC-5 과대 약속** (교차오염 탐지)
   외부 AI가 값을 요약·환산·재서술하면 출처를 결정론적으로 판별할 수 없다. → **수정**: AC-5를
   **명시적 유출 신호**(라벨·`task_id`·카나리·원문 그대로의 값)로 한정하고 **미탐 허용**을
   문면에 명시. 테스트는 "명시적 유출 양성 / 정상 답변 음성"만 단정.

- Alternatives Considered: 지적 4건 모두 계획 문서의 실질 결함이라 이월 없이 in-cycle 수정.
  P2는 문면 한정으로 처리(탐지 로직을 더 정교하게 만드는 선택지는 비용 대비 효과가 낮고,
  ANCHOR §1이 이미 "완전 격리 불가"를 방향으로 못박고 있어 정합).
- Risks: 본 cycle 산출물은 계획 문서뿐이라 런타임 위험 0. 구현 위험은 §2.1 위험도 Critical에
  귀속되며, 특히 (a) 도구 스코프 ContextVar → 명시 인자 승격이 내부 대화 경로에 회귀를 낼 수
  있고 (b) OAuth AS는 신규 인증 표면이라 §18.8 보안 렌즈를 구현 cycle에서 다시 받아야 한다.
- Open Questions: 없음 (2026-08-12 대화로 신원/비용 2축·동시 세션 허용·검증 이관 범위·인젝션
  처리·전송 2종·대화 기록 보존·context_depth 전부 확정).
- Human Approval Needed: **예** — §7.1 Critical. TASK.md §2.1에 `PLAN-APPROVED` 마커가
  부여되기 전까지 구현 착수 금지(§5 BLOCKED 등재).


## REV-20260812-0002 [CODEX:implementation] — accepted

- Related Change: CHG-20260812-0002 (P0 구현)
- Reason: §18.8 security 렌즈. 계획 리뷰(REV-0001)는 **문서**에 대한 것이라 코드 리뷰를
  대체하지 않는다 — 배포 전 필수라고 스스로 적어 둔 항목을 같은 cycle 에서 이행했다.
- 실행: `codex exec -s read-only` + `git diff --cached -- '*.py'`. GATE **FAIL (P1 2건)** →
  4건 전부 in-cycle 수정 + 회귀 테스트 5건 추가.

### 지적 사항과 처리 — 전부 MCP 어댑터(클라이언트 측)에 집중

1. **[P1] Bearer token 이 평문/MITM 에 노출** — `BASE_URL` 의 https 미검증 + TLS 검증 끄기 허용.
   → `_require_https()` 신설(https 강제, loopback 만 예외, 위반 시 fail-loud SystemExit).
   검증 끄기는 사내 self-signed 현실 때문에 남기되 **`EXT_TOOL_CA_BUNDLE`(사설 CA)** 을 권장
   경로로 추가하고, 끄면 stderr 경고를 낸다. 회귀 테스트 2건.
2. **[P1] `LABEL` 이 선택이라 L1 격리가 무력화** — 라벨 없는 두 계정 인스턴스가 **같은 tool
   이름**을 갖는다. 세션 격리의 유일한 물리적 gate 가 선택 사항이었다.
   → `_require_label()` 로 **필수화** + charset/길이 검증(`[A-Za-z0-9_-]{1,32}`).
   `_name()` 의 `if LABEL else` 분기 제거. 회귀 테스트가 그 분기의 부활을 막는다.
3. **[P2] 오류 본문이 각인 없이 tool 결과로 유입** — 성공 경로의 인젝션 gate 를 오류 경로로
   우회할 수 있다. → `_defang()` 으로 sentinel·`[SCOPE]` 제거 후 반환(HTTPError·일반 예외 양쪽).
4. **[P2] 응답 크기 무제한 `read()`** — 오동작·탈취된 endpoint 가 MCP 프로세스 메모리를 고갈.
   → `_MAX_BYTES`(기본 8MiB) 상한 + 초과 시 `response_too_large`.

- Alternatives Considered: (1)에서 "검증 끄기 옵션 자체를 제거" 도 검토했으나 사내 self-signed
  환경(CONTRIBUTING §10)에서 현실적으로 막힌다 — 대신 **올바른 경로(CA 지정)를 1급으로 만들고
  끄기는 경고와 함께 남기는** 절충. (2)는 절충 없이 필수화 — 선택으로 두면 격리가 사실상 없다.
- Risks: 지적 4건이 전부 **클라이언트 측 어댑터**였다는 점이 시사적이다 — 서버측 관문은
  단위 테스트로 두껍게 덮었는데 어댑터는 "얇은 래퍼" 라는 이유로 덜 봤다. 얇아도 토큰을 들고
  네트워크에 나가는 컴포넌트다.
- Open Questions: 없음.
- Human Approval Needed: **배포**는 사람 결정(외부 영향 + Critical). 라이브 e2e 미실시 상태.


## REV-20260812-0003 [SKIPPED:pre-deploy-hardening] — 배포 전 자체 점검 (패널 재호출 불요)

- Related Change: CHG-20260812-0003 (catchup 체인 보호)
- Reason: 라이브 배포 직전 `LEARNINGS.md` 의 반복 결함 목록을 이 변경에 대조하다 발견한
  **순수 방어 수정**이다. 새 기능·새 경로·새 노출면이 0 이고, 기존 함수의 try 경계만 넓혀
  예외가 `_ensure_seed_catchup` 로 새지 않게 한다.
- 발견 내용: `conn.cursor()` 가 try 밖 → 커서 획득 실패가 catchup 으로 전파 → 뒤따르는 6건
  (gdrive·아바타·첨부 버전·DB allowlist·**audit events**·**audit chain**)이 조용히 skip.
  `resource-acquire-outside-try` 는 LEARNINGS 에 **4 cycle 반복**으로 기록된 패턴이고,
  seed-catchup abort 는 별도 사례로 기록돼 있다 — 둘이 겹치는 자리였다.
- 판단: §18.8 패널 재호출을 하지 않는 근거 — (a) 변경이 `try:` 한 줄 이동 + except 추가이고
  (b) 방향이 항상 안전한 쪽(예외 봉인)이며 (c) AST 단정 7건으로 회귀를 고정했고 (d) 직전
  REV-0002 codex 리뷰의 대상 코드와 같은 파일이 아니다. 새 판단이 필요한 설계 변경이 아니다.
- Risks: 예외를 삼키므로 **테이블 생성 실패가 조용해진다.** 그 대가는 의도적이다 — 실패 시
  이 feature 의 엔드포인트가 fail-closed 로 막히고(도달면 0), 무관한 서브시스템은 살아남는다.
  배포 후 검증에서 4개 테이블 실재를 직접 확인해 이 침묵을 보완한다(POST-DEPLOY).
- Human Approval Needed: 아니오 (배포 자체는 `deploy_scope: included` 사전 승인 + 사용자
  2026-08-12 명시 지시).


## REV-20260812-0004 [SKIPPED:deploy-failure-rootfix] — 라이브 기동 실패 근본 수정

- Related Change: CHG-20260812-0004
- Reason: 배포 1차에서 web-a 가 `ModuleNotFoundError` 로 기동 실패. 코드 거주지 이동이라
  설계 판단이 바뀌지 않아 패널을 재호출하지 않는다(로직 변경 0 — `git mv` + import 경로).
- **놓친 이유(정직)**: 단위 테스트가 **repo 레이아웃**에서만 돌았다. "repo 에서 import 되는 것"
  과 "배포 이미지에서 import 되는 것" 은 다른 집합인데, 그 차이를 재는 게이트가 없었다.
  codex 리뷰 2회도 이걸 못 잡았다 — diff 만 보면 경로가 자연스러워 보이고, Dockerfile COPY
  목록과 대조해야만 드러난다.
- 재발 방지: `test_container_importability.py` 5건 — Dockerfile COPY 목록을 파싱해 (a) 서버측
  모듈이 COPY 되는 트리 안에 있는지 (b) 라우터가 이미지에 없는 경로로 `sys.path` 를 주입하지
  않는지 (c) top-level import 가 이미지 레이아웃에서 해석되는지 정적으로 확인한다.
- 사용자 영향: **0** — 무중단 롤링(one-at-a-time)이 설계대로 작동해 web-b(구코드)가 계속
  서빙했고, Caddy 가 실패한 web-a 를 passive 격리했다. 이 사고는 그 안전망이 실제로 동작함을
  확인해 준 사례이기도 하다.
- Human Approval Needed: 아니오 (배포 재실행은 `deploy_scope: included` 범위).

## REV-20260812-0005 [SKIPPED:post-deploy-record] — 배포 검증 기록 (코드 변경 0)

- Related Change: CHG-20260812-0005
- Reason: 라이브 배포 결과와 POST-DEPLOY probe 12항을 정본에 기록하는 문서 전용 변경.
  코드·설정 변경이 0 이라 §18.8 패널 대상이 아니다.
- 검증 요지: 서비스 4종 커밋 일치 · 무중단 실측 0건 · alembic 0055 직접 확인 · 신규 테이블
  5종 실재 · 무토큰 401 · DCR 201 / 비-HTTPS 400 · 미로그인 authorize 302→/login ·
  기존 경로(`/livez`·`/api/ai/manifest`·`/llms.txt`) 200.
- **정직 표기 2건**: (1) 인증된 전 구간 e2e 는 사람 브라우저 인가가 필요해 미검증 —
  자동 probe 로 대체 불가(설계 의도). (2) probe 가 남긴 DCR client 1건이 라이브에 존재
  (`deploy-probe` — `client_id` 만으로는 무권한이라 무해, 정리하려면 revoke).
- Human Approval Needed: 아니오.


## REV-20260812-0006 [CODEX:remaining-surface] — accepted

- Related Change: CHG-20260812-0006
- 실행: `codex exec -s read-only` + `git diff --cached -- '*.py'`. GATE **FAIL (P1 3건)** →
  5건 전부 in-cycle 수정 + 회귀 테스트 6건 추가.

### 지적과 처리

1. **[P1] L4 가 교차 테넌트 정보를 노출** (`ai_tools.py`) — 가장 무거운 지적. OAuth `client_id` 는
   DCR 로 누구나 받는 **앱 식별자**이지 설치·사용자 식별자가 아니다. 서로 무관한 사용자가 같은
   client_id 를 쓸 수 있는데, 나는 그걸 "한 머신의 런타임" 으로 가정하고 **상대 계정 id·권한
   겹침을 응답에 실었다.** → finding 에서 계정 id 제거(`n_accounts` 로 대체) + **응답에서 완전
   제거해 원장 전용**으로 전환. L4 의 목적은 운영자 관측이지 호출자 통보가 아니다.
2. **[P1] HTTP 전송이 `0.0.0.0` 평문 수신** — 전달하기도 전에 Bearer token 이 노출된다.
   → **loopback 기본 바인딩** + 외부 바인딩은 `EXT_TOOL_HTTP_ALLOW_PUBLIC_BIND=1` 명시 opt-in
   (TLS 종단 프록시 전제) + 경고.
3. **[P1] urllib 자동 리다이렉트가 `Authorization` 을 타 호스트로 전달** — 두 어댑터 모두 해당.
   → `_NoRedirect` 핸들러로 전면 금지(우리 API 는 도구 호출에 리다이렉트를 쓰지 않는다).
4. **[P2] `EXT_TOOL_VERIFY_TLS=0` 이 Bearer 채널 인증을 완전히 끔** → **loopback upstream 에서만**
   허용, 그 외는 fail-loud. 사내 self-signed 는 `EXT_TOOL_CA_BUNDLE` 이 정답.
5. **[P2] L4 의 무제한 계정 fan-out** — 공유 client 에 계정이 많으면 인증된 요청 1건이 DB 증폭.
   → `_ASYMMETRY_MAX_ACCOUNTS=8` 상한(판정 본질은 격차 유무라 표본으로 족하다).

- Risks: 1번은 **내 설계 전제가 틀렸던 사례**다 — "client_id = 머신" 가정을 문서(ANCHOR §1)에도
  썼는데, DCR 특성상 성립하지 않는다. L4 를 원장 전용으로 내리면서 그 가정에 의존하는 표면은
  없어졌지만, 향후 client_id 를 신원 축으로 쓰려는 시도는 같은 함정에 빠진다.
- Human Approval Needed: 아니오 (배포는 `deploy_scope: included`).

## REV-20260812-0007 [SKIPPED:scope-decision] — 콘솔 탭 제외 결정 기록

- Related Change: CHG-20260812-0007
- Reason: 범위 결정 기록(코드 0). 사용자 결정 2026-08-12 — `admin.js` 를 다른 활성 브랜치 2개가
  편집 중이라 충돌 위험이 크고, `visual_verification_scope: always` 로 PB-0008 이 하드 게이트여서
  붙이면 나머지 3건 출하까지 묶인다. 상한은 이미 집행 중이라 기능 공백이 아니다.
- Human Approval Needed: 아니오 (사용자가 직접 결정).


## REV-20260812-0008 [SKIPPED:post-deploy-record] — 2차 배포 검증 기록 (코드 0)

- Related Change: CHG-20260812-0008
- Reason: 배포 결과 기록(문서 전용). 코드·설정 변경 0.
- 검증 요지: 서비스 4종 `e1372f32` 일치 · 무중단 0건 · 매니페스트 `tool_surface`(endpoints 8) ·
  OpenAPI 7 path · 가이드 부록 B 서빙 · **익명 노출 인스턴스 데이터 0 라이브 실측** ·
  기존 발견 경로 200 · 도구 표면 무토큰 401.
- 정직 표기: HTTP/SSE 전송은 **라이브 미기동**(포트·TLS 프록시 운영 결정 선행). 코드 경로만 확보.
- Human Approval Needed: 아니오.

## REV-20260812-0009 [CODEX:P1x4,P2x2] — 잔여 3건 완결 (HTTP 기동 · 콘솔 노출 · e2e 절차서)

- Related Change: CHG-20260812-0009
- Reviewer: `/codex review` (§18.8 대체 패널)

### 지적과 처리

1. **[P1] `ext-tool-mcp` 에 `networks` 누락** — compose 기본 네트워크에 붙어 `dbnet` 의 web·caddy
   와 이름 해석이 안 된다. 기동은 성공하고 **모든 도구 호출만 502** 가 되는, 헬스체크로도 안
   잡히는 형태였다. → `networks: [dbnet]` + 헬스체크를 TCP 에서 **HTTP 프로브**로 교체.
2. **[P1] 엣지 경로와 서버 경로 불일치** — Caddy 가 `/api/ai/mcp` 를 그대로 넘기는데 FastMCP 는
   `/mcp` 에서 듣고 있었다(전량 404). → `_HTTP_PATH = "/api/ai/mcp"` 로 통일.
3. **[P1] e2e 스크립트가 `curl -k`** — access/refresh token 을 TLS 검증 없이 전송. → 사내 rootCA
   가 있으면 `--cacert` 로 **검증**, 없을 때만 경고와 함께 `-k`(모드를 화면에 표시).
4. **[P1] 존재하지 않는 방어를 콘솔이 표시** — `AGENT_EXT_TOOL_CONCURRENCY` 는 소비처가 없고
   `AGENT_EXT_TASK_OPEN_MAX` 는 집행되지 않았으며 RPM 은 `open_task` 에 안 걸려 있었다.
   운영자가 "동시 실행을 제한했다" 고 믿는 상태가 가장 위험하다. → 미구현 knob **삭제**,
   `check_open_tasks` 구현 + `open_task` 에 RPM·미제출 게이트 배선.
5. **[P2] MCP 전송 계층 무인증** — Bearer 는 도구 실행 시점에만 검사되므로 그 전에 익명
   클라이언트가 스트림을 열어 프로세스 자원을 소모할 수 있다. → 엣지에서 `Authorization`
   **헤더 존재 자체**를 요구해 익명 연결 차단(유효성은 여전히 upstream 몫).
6. **[P2] upstream 이 `web-a` 고정 + TCP 헬스체크** → 콤마 목록 failover(**연결 실패에만** 재시도
   — HTTP 오류를 넘기면 같은 부작용이 두 번 난다) + HTTP 프로브.

### 자체 발견 (codex 지적 아님)

- Caddy `@noauth`/`respond` 를 `handle` **밖**에 두면 adapt 결과에서 401 라우트가 프록시 뒤로
  밀려 **무력화**된다. `caddy adapt` 로 내부 순서가 `['static_response', 'reverse_proxy']` 인
  것을 확인하고 블록 안으로 이동. 테스트가 이 순서를 단정한다.

- Risks: 4번이 이번 cycle 의 교훈이다 — **콘솔에 노출한 knob 은 그 자체로 "이 방어가 있다" 는
  주장**이다. 소비처 없이 노출하면 문서보다 강한 거짓 안심을 만든다. `runtime_settings.py` 에
  주석으로 규율을 고정했고 `DEFAULTS` 와의 키 일치를 테스트가 검사한다.
- Human Approval Needed: 아니오 (`deploy_scope: included`).

## REV-20260813-0010 [CODEX:P1x3,P2x2] — 배포 실패 3중 원인과 수정

- Related Change: CHG-20260813-0010

`make deploy-web` 이 `ext-tool-mcp 상태=none` 으로 실패하고 워커군이 last-good 으로 롤백됐다
(web 은 신코드 유지 — expand/contract 로 안전). 원인이 **셋** 겹쳐 있었다.

1. **`mcp` 패키지가 이미지에 없었다.** Dockerfile COPY 는 테스트로 고정했지만 **런타임 의존**은
   아무도 검사하지 않았다. → `requirements.txt` 추가 + "컨테이너 진입점의 서드파티 import 는
   전부 requirements 에 있어야 한다" 는 정적 검사 추가.
   ⚠ 그 검사를 처음엔 파일 전체 부분문자열로 썼는데, **주석에 적힌 `ext-tool-mcp` 가 통과**
   시켜 뮤테이션(`mcp` 줄 삭제)이 살아남았다. requirement 줄만 파싱하도록 고쳐 KILL 확인.
2. **MCP SDK 2.0 이 `mcp.server.fastmcp` 를 제거**했다(`mcp.server.mcpserver.MCPServer`).
   `pip install mcp` 는 이제 2.x 를 주므로 **가이드대로 설치한 사용자도 깨진다**. → 두 세대를
   모두 받는 호환층. v2 엔 전역 `get_context()` 가 없어 헤더 접근을 **도구가 받은 ctx** 경유로
   바꿨다(`ctx.headers` / `ctx.request_context.request.headers` 양쪽).
3. **upstream 이 평문이 아니었다.** `ENABLE_WEB_TLS=1` 이라 web replica 는 8000 에서 TLS 로 듣고,
   인증서 SAN 에 `web-a` 가 없어 이름 검증이 실패한다. 검증을 끄는 대신 **Caddy 와 같은 모델**
   (`tls_server_name` + `header_up Host`)을 채택 — `_SniHTTPSConnection` 으로 검증 대상 이름만
   고정하고 rootCA 로 체인 검증한다. 결과적으로 평문 예외(`ALLOW_PLAINTEXT_UPSTREAM`)가
   기본 배포에서 사라져 **보안이 오히려 강해졌다**.

- 라이브 실측: 컨테이너에서 SDK 2.0 으로 기동 → `initialize` 200 · `tools/list` **9종** ·
  무토큰 호출 `no_authorization` · 가짜 토큰 호출 **상류 401 전달** · 구 경로 `/mcp` 404.
- Risks: 1번이 이번 cycle 두 번째 "COPY 는 맞는데 기동이 죽는다" 사례다(첫 번째는 8/12
  `oauth_store` 미포함). **이미지 경계는 파일 존재만이 아니라 의존까지가 계약**이다.
- Human Approval Needed: 아니오.

### codex 2차 리뷰 (같은 변경에 대한 적대 패널) — P1×3 · P2×2 전건 수정

1. **[P1] 검증 끄기 가드가 첫 upstream 만 검사** — `https://localhost,https://공격자` 조합이면
   첫 후보가 loopback 이라 통과하고, failover 후보에도 **같은 `CERT_NONE` 컨텍스트**로 토큰이
   나간다. → `BASE_URLS` **전수** 검사로 교체(위반 목록을 메시지에 찍는다).
2. **[P1] `mcp>=1.2.0` 은 streamable-http 가 없던 버전을 허용** — import 는 성공하고 생성자
   인자가 조용히 무시된 뒤 `run()` 에서 죽는다. → 하한을 `1.9.0` 으로 올리고, v1 경로에서
   `run_streamable_http_async` 부재를 **기동 시점에** fail-loud 로 잡는다.
3. **[P1] healthcheck 가 404·5xx 도 healthy 로 읽음** — 모든 `HTTPError` 를 성공 처리하고
   있었다. **바로 그 404(경로 불일치)가 이번 cycle 의 실제 결함**이었는데 healthcheck 는 그걸
   통과시켰을 것이다. → 허용 코드를 `400/405/406` 으로 고정(GET 은 이 전송의 정상 메서드가
   아니라 406 이 "살아 있음"의 신호 — 라이브 실측으로 확인).
4. **[P2] TLS·헤더 테스트가 문자열만 검사** — "구현이 실행 시 전부 `no_authorization` 을
   반환해도 통과한다"는 지적 그대로다. → `test_http_adapter_behavior.py` 신설: 가짜 SDK 모듈을
   주입해 어댑터를 **실제로 import·실행**한다(로컬에 mcp 가 없다고 skip 하면 그거야말로
   vacuous pass). 뮤테이션 4종(v1 헤더 경로 제거 · SNI 고정 무력화 · Host 헤더 제거 ·
   전수검사→첫 후보) 전부 KILL 확인.
5. **[P2] 호출마다 SSLContext 생성 + opener 영구 캐시** — 장기 실행 프로세스라 호출 수에 비례해
   누수. → 컨텍스트·opener 를 모듈 1회 생성으로 전환.

- Risks: 3번은 **방어가 오히려 결함을 숨기던** 사례다. healthcheck 를 느슨하게 쓰면 "healthy 인데
  아무것도 안 되는" 상태가 배포를 통과한다. 4번은 이번 cycle 에서 두 번째 vacuous-pass 적발이다
  (첫 번째는 requirements 부분문자열 검사). **문자열 검사는 계약을 못 지킨다** — 뮤테이션으로
  확인하지 않은 테스트는 없는 것과 같다.

## REV-20260813-0011 [SKIPPED:self-found-live-defect] — 콘솔 배치 정정

- Related Change: CHG-20260813-0011
- Reason: 배포 후 **내가 쓴 문서가 사실이 아님을 라이브에서 확인**하고 즉시 고친 건이다
  (외부 지적 아님). "`시스템 > 설정 > 외부 AI 도구` 에서 조절" 이라고 적었는데, 실제로는
  그룹이 미분류라 payload 가 `timeouts` 버킷으로 흘려보내 '실행 타임아웃' 패널 안에
  카테고리 소제목으로 렌더되고 있었다. 조절은 가능했으나 **있지도 않은 섹션을 문서가
  주장**하는 상태였고, 부하 상한을 타임아웃 화면에 두는 것 자체가 오분류다.
- 교훈: `runtime_settings` 에 그룹 상수를 추가해도 **payload 버킷 분기까지 하지 않으면
  UI 는 조용히 기타 취급**한다. 그룹 추가 = 3곳(스펙·버킷·패널) 계약이다.
- 검증: 뮤테이션 2종 KILL(버킷 분기 제거 · 프론트 미러 키 누락). 프론트 미러와 백엔드
  스펙의 키 일치를 테스트가 단정한다(드리프트하면 dot 라우팅이 조용히 틀린다).
- Human Approval Needed: 아니오.

## REV-20260813-0012 [SKIPPED:post-deploy-record] — 배포 후 검증 기록 (코드 0)

- Related Change: CHG-20260813-0012
- Reason: 라이브 검증 결과 기록(문서 전용). 코드·설정 변경 0.
- 검증 요지: 서비스 6종 `feadc089` 일치 · 무중단 0건 · 엣지 익명 401 · `initialize` 200 ·
  `tools/list` 9종 · 도구 호출이 **검증된 TLS 로 web 도달**(가짜 토큰 → 상류 401) ·
  PB-0008 로 콘솔 전용 패널 4행 렌더 + 타임아웃 패널에서 분리 확인.
- 정직 표기: **인가 이후 구간 e2e 는 여전히 미실측**(사람 브라우저 인가 1회 필요 —
  `docs/E2E_RUNBOOK.md`). AC-1 은 열린 채로 둔다.
- Human Approval Needed: 아니오.

## REV-20260813-0013 [CODEX:P1x3,P2x3] — 인증 접근성 재설계

- Related Change: CHG-20260813-0013

### 착수 전 자체 발견

사용자가 "스크립트 실행은 접근성이 매우 낮다" 고 지적해 조사하다가, **미로그인 사용자는
인가를 시작할 방법 자체가 없었음**을 라이브에서 확인했다 — `authorize` 가 `/login` 으로
리다이렉트하는데 그 라우트가 없다(로그인 UI 는 `/` SPA 안에 있다). 스크립트가 굴러간 것은
운영자가 이미 로그인돼 있었기 때문이다. **문서가 "브라우저로 인가한다" 고 적은 상태에서
실제로는 404 였다.**

### codex 지적과 처리 (P1×3 · P2×3 전건 수정)

1. **[P1] 오픈 리다이렉트** — `next=/\evil.com` 이 `startsWith("/")` 통과 · `startsWith("//")`
   미통과인데, 브라우저가 `\` 를 `/` 로 정규화해 **외부로 나간다.** → 판정을 순수 모듈
   `next-target.js` 로 분리하고 **URL 해석 후 origin 비교**로 교체(문자열 검사 폐기).
   9 케이스를 node 로 실행 검증.
2. **[P1] 승인 scope 보다 넓은 접근** — 임의 scope 를 서명·표시하면서 도구 인증은 scope 를
   전혀 읽지 않았다. `scope=openid` 로 무해하게 띄우고 같은 도구를 다 쓸 수 있었다.
   → 지원 집합 밖은 발급 전 거절(`invalid_scope`), 도구 인증이 `data.read` 를 **집행**(403).
   조용한 intersection 을 택하지 않은 이유: 사용자는 넓게 승인했다고 믿고 클라이언트는 좁은
   토큰을 받는 **양쪽 다 사실과 다른** 상태가 된다.
3. **[P1] 강제 비밀번호 변경 우회** — 강제 변경 모달은 SPA 안에서만 강제된다. `?next=` 복귀가
   그 앞으로 빠져나가 임시 비밀번호 계정이 토큰을 발급할 수 있었다. → 클라이언트 가드 +
   **서버측 403**(발급 3경로 전부).
4. **[P2] consent token 재사용 가능** → 서명 payload 에 nonce 를 싣고 승인 시 **DB UNIQUE 로
   소비**한다. 프로세스 메모리로 하면 replica 2대에서 각각 한 번씩 통과한다.
5. **[P2] 2FA 계정만 복귀 실패** — TOTP 성공 경로에 복귀가 없었다(보안을 강화한 사용자가 더
   나쁜 경험을 받는 형태). → 세 로그인 경로 모두 같은 함수를 통과.
6. **[P2] 보안 테스트가 문자열만 검사** — "취약한 구현을 그대로 PASS 시킨다"는 지적이 정확했다.
   → 가짜 `app` 모듈을 주입해 consent 서명·만료·세션교차·scope 정규화를 **실행**하고,
   `safeNextTarget` 은 node 로 9 케이스를 돌린다. 뮤테이션 5종 전부 KILL 확인.

- Risks: 3번은 **다른 feature 의 보안 장치(강제 변경)를 내 진입점이 우회시킨** 사례다. 새 진입점을
  만들 때 "기존 모달·게이트가 SPA 안에서만 강제되는가" 를 확인해야 한다.
- Human Approval Needed: 아니오 (`deploy_scope: included`).

## REV-20260813-0014 [SKIPPED:post-deploy-record] — 배포 후 기록 + 안내 정본 갱신 (코드 0)

- Related Change: CHG-20260813-0014
- Reason: 라이브 검증 결과 기록과 사용자 안내 문구 갱신(코드 0).
- 요지: **스크립트를 "사용 방법" 으로 안내하던 것이 문제의 절반**이었다. 가이드 최상단에
  "주소만 등록" 을 두고, 런북은 개발자 회귀 검증용으로 격하했다. AI 독자에게 "사용자에게 셸
  스크립트 실행을 요구하지 말 것" 을 명시했다.
- Human Approval Needed: 아니오.

## REV-20260813-0015 [SKIPPED:post-deploy-record] — 가이드 반영 실측 (코드 0)

- Related Change: CHG-20260813-0015
- Reason: 배포 결과 기록. 코드 0.
- 요지: 이 자산의 유일한 의미 있는 실패 모드("배포본 미반영")를 내용 대조로 확인했다.
- Human Approval Needed: 아니오.

## REV-20260814-0016 [SKIPPED:self-found-live-defect] — 엣지 401 호스트 고정

- Related Change: CHG-20260814-0016
- Reason: 사용자가 "외부 접속은 `https://112.185.196.20/` 경로" 라고 알려준 직후 실측으로
  확인한 결함(외부 지적 아님). 앱 401 은 `request.base_url` 을 따라 IP 를 돌려주는데
  **엣지 401 만 `{$WEB_PUBLIC_HOST}` 로 고정**돼 있었다. 클라이언트가 처음 만나는 것이
  엣지 401 이므로, IP 접속 사용자는 자동 discovery 를 시작조차 못 한다.
- 선택지와 근거: 엣지에서 `{host}` 를 되비추는 방법은 **검증 없는 반사**라 택하지 않았다
  (`:443` catch-all 이라 임의 Host 가 들어온다). 앱은 이미 TrustedHost 로 호스트를 검증하고
  같은 단서를 만들므로, 401 생성을 앱으로 넘기는 것이 중복도 반사도 없다.
- 검증: 브랜치 Caddyfile+web 을 격리 기동해 Host 3종(공인 IP·사내 이름·localhost) 전부
  **접속 호스트를 따르는 단서**를 반환함을 실측. 익명이 `ext-tool-mcp` 에 닿지 않는 순서도
  adapt 결과와 테스트로 고정.
- 함정 기록: 격리 장비를 비표준 포트(18444)로 노출하면 Host 에 포트가 붙어 Caddy 사이트
  매칭이 달라진다(IP 호스트가 404). 컨테이너 네트워크 안에서 **443 으로** 재현해야 한다.
- Human Approval Needed: 아니오.

## REV-20260814-0017 [SKIPPED:post-deploy-record] — 호스트 정합 배포 검증 (코드 0)

- Related Change: CHG-20260814-0017
- Reason: 배포 결과 기록. 코드 0.
- 요지: 공인 IP·사내 이름·loopback 3종 모두 401 단서가 자기 호스트를 가리키고, 익명 차단과
  인증 경로(MCP `initialize` 200)는 그대로다.
- Human Approval Needed: 아니오.

## REV-20260814-0018 [SKIPPED:live-user-report] — 실사용 제보 결함 5건

- Related Change: CHG-20260814-0018
- Reason: 외부 세션이 실제로 연결·사용한 뒤 보고한 결함(내부 리뷰 아님). 전부 **테스트가
  있었는데도 통과했다** — 도구의 *존재*만 보고 *계약*을 보지 않았기 때문이다.

| # | 결함 | 왜 테스트가 못 잡았나 |
|---|---|---|
| 1 | DCR 이 `Claude Code (mysql-ai)` 를 400 거절 → **표준 클라이언트 자동 연결 불가** | 내가 만든 이름(`e2e-runbook`)으로만 시험했다. 실제 클라이언트 이름을 몰랐다 |
| 2 | `describe_table`·`get_foreign_keys`·`get_table_indexes` 가 `table` 을 보내는데 백엔드는 `table_name`+`schema_name` 을 읽음 → **어떤 인자로도 성공 불가** | "도구 9종이 등록되는가" 만 검사했다. 인자 이름을 백엔드와 대조하지 않았다 |
| 3 | `allowed_datasource_labels` 가 **바인딩 2개 이상에서만** 값을 반환 → 정당한 `datasource` 인자 전부 거부 + grounding scope 공백 | fake 커서로만 시험해 실제 제품 바인딩 형태를 안 봤다 |
| 4 | grounding 이 라벨을 scope 로 넘김(정본은 엔드포인트 해시) + 문자열 반환을 rows 로 착각해 `render()` 재호출 → 예외 → **bare except 가 삼킴** | 라이브 데이터로 한 번도 호출해 보지 않았다 |
| 5 | 빈 번들을 "(관련 요약 없음)" 한 줄로만 반환 → 정상인지 고장인지 구분 불가 | 응답 *형태*만 봤다 |

- 설계 보정: 클러스터 요약은 **질문에 테이블 이름이 있을 때만** 매칭된다(내부 대화 경로는 매 턴
  호출하므로 자연히 이름이 섞인다). 외부 AI 는 탐색 *전에* 한 번 부르므로 구조적으로 빌 수밖에
  없었다 → `focus` 인자를 추가해 **탐색 후 다시** 부를 수 있게 했다. 라이브 실측으로
  "테이블명 포함 질문 → 223자 grounding" 확인.
- Risks: 1번이 가장 무겁다. **자동 연결이 전 구간 불가**였는데 내 e2e 는 통과했다 — 내가 만든
  이름만 넣었기 때문이다. 외부 클라이언트가 보내는 값은 예측 대상이 아니라 **관측 대상**이다.
- 뮤테이션: 5건 전부 되돌려 KILL 확인.
- Human Approval Needed: 아니오.

## REV-20260814-0019 [SKIPPED:post-deploy-record] — 제보 결함 배포 검증 (코드 0)

- Related Change: CHG-20260814-0019
- Reason: 배포 결과 기록. 코드 0.
- 요지: 실제 클라이언트 이름 3종이 DCR 201 로 통과(이전 400 — 자동 연결 차단의 직접 원인),
  인가 완료 화면 3분기 200, 가이드 반영 확인. 검증 probe client 는 revoke.
- Human Approval Needed: 아니오.

## REV-20260814-0020 [CODEX:P1x3,P2x3] — execute_sql 개방과 스코프 결함

- Related Change: CHG-20260814-0020

### 이 cycle 이 드러낸 것 — 스코프가 처음부터 잘못 세워져 있었다

`execute_sql` 을 열려고 실행 경로를 다시 읽다가, **8/12 부터 라이브였던 구조 조회 자체가
잘못된 연결로 돌고 있었음**을 확인했다.

`scoped_execution` 은 다중 바인딩일 때만 라우터를 세우고, 단일 바인딩이면 `None` 을 돌려주며
docstring 에 "호출측이 단일 경로로 연결을 잡아야 한다" 고 적어 뒀다. **호출측(내 라우터)은
그렇게 하지 않고 memory DB 연결을 그대로 넘겼다.** 그리고 스키마 allowlist 설정도 라우터
경로에만 있었다. 결과(라이브 실측):

```
list_schemas → __invalid_default_db__ | account_db | agent_attachment_5fdcf3f9… |
               agent_attachment_a6429d… | dbauth | dbgame | dblog | …
```

**다른 대화의 첨부 샌드박스**와 `account_db` 가 목록에 나왔다. 대부분의 제품이 단일 바인딩이라
이건 예외가 아니라 **기본 경로**였다. 인증된 사용자에 한정되고 현재 사용자는 운영자 본인뿐이라
실제 피해는 없었지만, 제품 스코프 격리가 성립하지 않은 상태였다.

**교훈**: 계약을 docstring 으로 호출측에 미루면 지켜지지 않는다. 스코프를 세우는 함수가
스코프의 **모든 축**(연결·allowlist·방언)을 책임지도록 옮겼다.

### codex 지적과 처리 (P1×3 · P2×3 전건)

1. **[P1] 단일 datasource 에서 memory DB 연결** → 위. `scoped_execution` 이 연결까지 잡고,
   미바인딩이면 `ScopeDenied`(403) 로 **fail-closed**.
2. **[P1] 운영자 스위치가 항상 무력화** — `get_int(key, default)` 는 **TypeError**(인자 1개).
   except 가 True 를 돌려줘 스위치가 늘 켜진 상태였다. **문자열만 보던 내 테스트가 통과시켰다.**
   → 올바른 호출 + fail-**closed** + 실제 호출 테스트(옛 형태가 TypeError 임을 단정).
3. **[P1] 시간당 상한이 hard cap 이 아니다** — 실행 전 누적 확인이라 상한 직전 대형 쿼리 1회,
   동시 요청이 같은 잔여를 본다. → **건당 행 상한**(`AGENT_EXT_TOOL_SQL_MAX_ROWS`, 기본 10,000)
   으로 초과분을 유계로. 초과 결과는 **반환하지 않고 원장에는 기록**한다(부하는 발생했다).
   ⚠ 여전히 원자적 hard cap 이 아니다 — "초과분이 유계" 라고만 주장한다.
4. **[P2] 외부 호출도 CSV 를 생성** → `_suppress_csv` 로 **애초에 안 만든다**(디스크·잔존
   데이터·저장 실패 시 절대경로 유출 3건 동시 해소).
5. **[P2] CSV 저장 실패 시 경로 유출** → 위와 동일 해소.
6. **[P2] `datasource_key` 원장이 항상 빈 값** — `execute_tool` 이 `arguments` 에서 pop 한 뒤
   읽고 있었다 → 실행 **전에** 포착.

### 자체 발견 (테스트 스위트가 잡음)

`set_active_datasource` 는 **토큰을 반환하지 않는다**(setter). 반환값을 token 으로 받아
`if token is not None` 으로 복원하면 **절대 복원되지 않는다** — ContextVar 가 스레드에 남아
다음 요청이 이전 datasource 스코프로 돈다. 무관한 테스트(`test_ai_ops`)가 깨지며 드러났다.
단독 실행은 통과하고 스위트에서만 실패하는 형태였다.

- 뮤테이션: 7종 전부 KILL(스위치 옛 형태 · 메모리 연결 반환 · allowlist 미설정 · 미바인딩
  fail-open · 건당 상한 해제 · CSV 재생성 · datasource 사후 읽기).
- Human Approval Needed: 아니오 (`deploy_scope: included`).

## REV-20260814-0021 [SKIPPED:post-deploy-record] — 스코프 복구 배포 검증 (코드 0)

- Related Change: CHG-20260814-0021
- Reason: 배포 결과 기록. 코드 0.
- 요지: 구조 조회가 제품 datasource 를 향하고 **첨부 샌드박스 노출 0건**, `execute_sql` 은
  허용 DB 통과·비허용 DB 차단, CSV 경로 없음, 원장에 실제 행수 기록.
- Human Approval Needed: 아니오.

## REV-20260814-0022 [SKIPPED:live-user-report] — 게이트 코칭이 틀린 조언을 하던 것

- Related Change: CHG-20260814-0022
- Reason: 외부 세션의 2차 실사용 보고(내부 리뷰 아님). 관찰 4건을 라이브에서 재현해 분류했다.

| 관찰 | 재현 | 처리 |
|---|---|---|
| 부하 게이트가 `COUNT(*)` 차단 | ✅ | **코칭 수정** — 아래 |
| "부하추정 실패" 가 원인을 오도 | ❌ 재현 실패(`TRY_CAST`·`CAST+JOIN` 모두 통과) | 문구에 3번째 원인(SQL 형태) 추가 |
| `OBJECT_NAME` 금지로 sys 경로 차단 | ✅ | denylist **유지**(사용자 결정) + 표준 대안 안내 |
| `get_task_context` 가 다른 스키마 개요 | ✅ 설계대로 | 조치 없음 — 질문에 등장한 테이블이 속한 묶음을 찾는 층이다 |

### 핵심 — 코칭이 이미 한 일을 시키고 있었다

집계 전용 조언("전역 집계라 컬럼을 줄여도 스캔량이 안 줄어든다 / approx_rows 를 쓰라")은
**이미 있었지만 `if worst:` 안에만** 있었다. 계획 사실을 주지 않는 엔진(MSSQL)에서는 `else`
분기의 일반론 — "**서버측 집계(COUNT/SUM/GROUP BY)**" — 만 나갔고, 차단된 쿼리가 이미
`COUNT(*)` 였다. 외부 AI 는 그걸 받고 **구간 2분할로 우회**했는데 총 스캔량은 동일하다.
**게이트가 부하를 못 줄이고 마찰만 만들었다.**

집계 판정은 SQL 형태(regex)만 보므로 계획 사실이 필요 없다 → `if worst:` 밖으로 꺼냈다.
원래 codex P2 우려("계획 사실 없이 계획 유도 문구를 지어내지 말 것")는 테스트로 그대로 보존한다
— 그 우려와 이 조언은 출처가 다르다.

덧붙인 문장: **"구간을 나눠 여러 번 돌리는 것은 총 스캔량을 줄이지 않습니다"** — 실제로 그
우회를 했기 때문에 명시했다. 그리고 그들이 인용한 `1,690,449` 는 `list_schemas` 가 이미 준
approx_rows 였다 — 정답이 손에 있었는데 안내하지 않았다.

- Risks: 이 코칭은 **사내 assistant 대화 경로가 같이 쓴다.** 문구만 바뀌고 차단 기준은
  그대로라 회귀 위험은 낮지만, 골든 계약 테스트를 하나 고쳤다(계약 자체가 틀렸던 사례).
- Human Approval Needed: 아니오 (사용자가 두 결정을 직접 선택).

## REV-20260814-0023 [SKIPPED:non-policy-doc] — 정본 docs 를 라이브 상태로 정합

- Related Change: CHG-20260814-0023
- Reason: §18.8 dispatch 표의 "비정책 doc-only" 행 → panel SKIP. 변경 집합이 feature 소유
  `REPORT/TASK/TEST` + `docs/STATUS.md` 행뿐이고 코드·정책 doc 변경이 0 이다.
- Trigger: 코드 변경 0건 · 정책 doc(`AGENTS.md`/`CLAUDE.md`/`_template/`/`SECURITY.md` 등) 0건.
- 판단 근거 — **왜 문서 정합을 별 cycle 로 냈는가**: 이 feature 에서 "문서가 사실을 앞지른"
  사례가 이미 세 번 기록돼 있다(콘솔 섹션 부재 · 컨테이너 미기동 · `/login` 404). 이번은 그
  **역방향** — 사실이 문서를 앞질러 정본이 뒤처진 경우다. 특히 §1 의 "도달면 0" 은 보안 표면에
  대한 **반대 진술**이라 후행 독자가 위험을 과소평가할 수 있어, 다음 cycle 로 미루지 않았다.
- 검증: `25637d1c` 배포 상태를 주장으로 옮기지 않고 **직접 실측**했다 — 6개 서비스 GIT_COMMIT
  일치 · `/healthz` ok · 엣지 익명 `/api/ai/mcp` 401 (TEST.md Run 20차). 머지 PR 19건은
  `gh pr list` 로 카운트했다.
- Human Approval Needed: 아니오. 다만 TASK §7 에 **사용자 결정 대기 1건**을 명시적으로 옮겨
  적었다(`dbauth` 분석 task 의 정정 메모 부착 여부) — 직전 세션의 마지막 질문이 대화에만
  남아 있어 정본에서 유실될 위험이 있었다.

## REV-20260814-0024 [SKIPPED:non-policy-doc] — AC-7 미구현 확인, 정본 하향

- Related Change: CHG-20260814-0024
- Reason: §18.8 "비정책 doc-only" → panel SKIP. 코드 변경 0 · 정책 doc 0.
- Trigger: 코드 변경 0건. (발견 자체는 코드 감사였으나 이번 변경집합은 문서뿐이다.)
- 판단 근거 — **왜 완료 주장을 되돌렸는가**: AC-7 은 사용자가 2026-08-12 에 명시적으로 추가한
  요구("외부 AI 세션의 대화 기록 또한 우리 쪽에 남겨야 합니다")에서 나왔고, FUNCTION §6·§7·
  AC-7 세 곳에 적혀 있으며 §12 매핑표는 `routers/ai_tools.py` 를 담당 모듈로 지목한다.
  그런데 그 파일에 `messages` 적재가 없다. 이 feature 는 "존재하지 않는 방어를 콘솔이 표시"
  한 사례를 이미 세 번 기록했는데, 이번은 **정본이 존재하지 않는 보존을 주장**한 경우다.
  같은 부류이므로 같은 처리를 한다 — 주장을 내리고 결함으로 되돌린다.
- 검증 방식: 주장 대조가 아니라 **실측**. 코드(INSERT 전수·전역 grep) → 라이브 스키마(컬럼
  전수) → 라이브 데이터(원장 2행의 bytes_out) 순으로 세 층에서 같은 결론을 얻었다.
  단일 grep 음성으로 "없다" 를 선언하지 않았다.
- 범위 경계: **구현하지 않았다.** 적재 대상(전용 컬럼 vs `messages`)·datamark 시점·소급 처리는
  설계 결정이고, 이 cycle 은 이어받은 작업의 정본 정합이 계약이다(Resume≠Re-scope).
  사용자 결정 항목으로 TASK §7 에 올렸다.
- Human Approval Needed: **예** — AC-7 구현 여부·범위, 그리고 그와 묶인 `dbauth` task 정정 메모.

## REV-20260814-0025 [SKIPPED:non-policy-doc] — 미결 2건 사용자 결정 확정

- Related Change: CHG-20260814-0025
- Reason: §18.8 "비정책 doc-only" → panel SKIP. 코드 0 · 정책 doc 0.
- Trigger: 결정 기록만. 구현·설계 변경 없음.
- 요지: AC-7 은 **구현**(요구를 현재 수준으로 축소하지 않는다), `dbauth` 정정 메모는 **미부착**
  (붙일 실체가 없다는 것이 근거 — 답변 본문 미저장·메모 컬럼 부재. 기록 삭제도 하지 않는다).
- 후속 경계: AC-7 구현은 외부 입력 본문을 **영속화**하므로 신규 저장면이 생긴다. 각인·인젝션
  경계가 저장 경로까지 확장되어야 하며 Critical 등급으로 §7.1 계획 승인 후 착수한다.
  ADR-003 의 관찰(적재 레코드에 datasource 식별자를 포함하면 같은 부류의 혼동이 구조적으로
  예방된다)을 그 설계 입력으로 넘긴다.
- Human Approval Needed: 아니오(본 변경). AC-7 구현 cycle 은 별도 계획 승인 대상.
