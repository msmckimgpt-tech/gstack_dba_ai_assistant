---
doc_type: TEST
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope
- 무엇을 검증하는지
- 어떤 범위를 제외하는지

> **검증 환경 분류 (AGENTS.md §15.4)** — §3 Run 의 `Environment` 는 아래 중 하나로 명시한다.
> 웹/UI(화면·상호작용) 검증은 **`Windows-browser` 만 인정**한다. `CLI`·`WSL-headless` 는
> 서버 계약(contract) 검증으로만 카운트하며 화면 검증을 대체하지 못한다 (실 사용자 관점 괴리 방지).
>
> | Environment | 의미 | UI 검증 인정 |
> |---|---|---|
> | `CLI` | curl / pytest / API 계약 | ✗ (서버 계약만) |
> | `WSL-headless` | WSL 내부 headless chromium (feature-0004 browser service, gstack /browse) | ✗ (화면 검증 불가) |
> | `Windows-browser` | 실제 Windows Chrome/Edge 를 AI 가 CDP 자동 구동 (`bin/win-browser.py`) | ✓ |
>
> Windows-browser 검증 절차는 **PB-0008** (`playbooks/PB-0008-windows-browser-verification.md`).

## 2. Test Cases
<!-- TEST ID 형식: timestamp+slug 권장 `TEST-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` (REQ/AC/ADR/TEST 공통,
     정본 AGENTS.md §6·§13.1, ADR-20260625T023049-spec-anchor-timestamp-id). 병렬 cycle 머지 시
     순번 충돌 제거. 예: `TEST-20260625T185057-login-1`. 기존 순번 `TEST-0001` 도 유효(fallback). -->
### TEST-<YYYYMMDDTHHMMSS>-<slug>-1
- Purpose:
- Preconditions:
- Steps:
- Expected Result:

### TEST-<YYYYMMDDTHHMMSS>-<slug>-2
- Purpose:
- Preconditions:
- Steps:
- Expected Result:

## 3. Test Run History
<!-- append-only: 새 실행 결과를 아래에 추가한다. 기존 결과를 수정하거나 삭제하지 않는다. -->

### Run YYYY-MM-DD-001
- Date:
- Environment: CLI | WSL-headless | Windows-browser   <!-- §1 분류표 참조. 웹/UI 검증은 Windows-browser 필수 -->
- Runner: AI / Human
- Bridge: <!-- Windows-browser 인 경우: relay | mirrored + win-browser.py doctor 결과 -->
- Evidence: <!-- 스크린샷 경로 등 (Windows-browser run 권장) -->
- Result Summary:
- Pass/Fail:
- Notes:

## 4. Untested Areas
- 아직 검증되지 않은 영역


## 3. Test Runs

### Run 2026-08-12 — 단위 (Environment: local pytest, PYTHONPATH=agent-core/src:web-ui/src:.)

| 스위트 | 결과 |
|---|---|
| `unit/feature-0041-external-ai-tool-surface/tests` (신규 89건) | **PASS** |
| `unit/feature-0002-agent-core/tests` | PASS (skip 다수 — 라이브 백엔드 격리) |
| `unit/feature-0003-agent-web-ui/tests` | PASS (`test_share_redaction_invariant` 제외) |
| `unit/feature-0023-conversation-api-access/tests` | PASS (`ask` 축 무회귀) |
| `bin/migrate-lint.sh` | PASS — 0055 expand-safe, head 단일 |

신규 89건 내역: `test_session_guard.py` 20 · `test_tool_authz.py` 15 · `test_oauth_store.py` 37 ·
`test_tool_ledger.py` 10 · `test_mcp_adapter.py` 7.

**`test_share_redaction_invariant.py` 미실행 사유**: `import web.app` 이 컨테이너 경로(`/app`)를
요구한다(파일 자체가 `sys.path.insert(0, "/app")` 폴백을 갖고 있다). 로컬 worktree 에는 그 경로가
없어 수집 단계에서 실패하며, **본 변경과 무관**하다(공유 리댁션 경로는 건드리지 않았다).
`make test`(컨테이너)에서는 정상 수집된다.

## 4. 미작성 테스트와 커버 계획

- **라이브 e2e (등록→인가→토큰→도구→제출)** — 미실시. 본 worktree 에 서비스가 기동돼 있지 않고,
  라이브 인스턴스에 신규 인증 경로를 붙이는 것은 배포 행위라 별도 단계다. 배포 후 5-probe 를
  §3 에 Run 으로 추가한다(등록 201 / 인가 302+code / 토큰 200 / 도구 200+각인 존재 / 무토큰 401).
- **동시성 경합(코드 2회 동시 교환)** — 단위는 순차 2회로만 덮었다. `UPDATE … WHERE ConsumedAt
  IS NULL` 의 rowcount 판정이 방어이므로 실 DB 동시 요청 2건으로 확인해야 완결된다.
- **부하 상한의 실 DB 집계** — fake 커서로 임계 판정만 덮었다. `tool_call_usage` 인덱스가 실제
  질의 계획에서 쓰이는지는 배포 후 `EXPLAIN` 으로 확인한다.
- **L4 권한 비대칭 flag** — 미구현이라 테스트 없음(TASK §5.1).

### Run 2026-08-12 — POST-DEPLOY 라이브 (Environment: live · a68fbbac · Caddy 경유)

배포: `make deploy-web` (deploy_scope: included). 1차 실패(모듈 미포함) → 근본 수정 → 2차 성공.

| # | 항목 | 결과 |
|---|---|---|
| 1 | 서비스별 GIT_COMMIT (web-a·web-b·insight-worker·ask-worker) | 전부 `a68fbbac` ✅ |
| 2 | 무중단 실측 — caddy `no upstreams available` 15분 | **0건** ✅ |
| 3 | `alembic_version` (stale agent image 함정 직접 확인) | `0055_tool_call_usage` ✅ |
| 4 | `agent_runtime.tool_call_usage` 실재 + GRANT(rw INSERT / ro SELECT) | `t\|t` ✅ |
| 5 | MySQL 신규 4테이블(WebOAuth{Clients,Grants,Tokens}·WebAiTasks) | 전부 존재 ✅ |
| 6 | 무토큰 `POST /api/ai/tools/open_task` | **401** ✅ (AC-1) |
| 7 | 무토큰 `POST /api/ai/tools/describe_table` | **401** ✅ |
| 8 | DCR `POST /api/ai/oauth/register` (정상 https redirect) | **201 + client_id** ✅ |
| 9 | DCR 비-HTTPS redirect 등록 | **400 거절** ✅ (AC-11) |
| 10 | `POST /api/ai/oauth/token` grant_type=password | **400 거절** ✅ |
| 11 | 미로그인 `GET /api/ai/oauth/authorize` | **302 → /login** ✅ (코드 미발급 — 신원 축) |
| 12 | 기존 경로 무영향 — `/livez`·`/api/ai/manifest`·`/llms.txt` | 전부 **200** ✅ (AC-9) |

**#5 관련 정정**: 최초 확인에서 4테이블 MISSING 으로 보였으나, 이는 probe 가 **데이터플레인
MySQL**(게임 DB)에 붙은 오진이었다. 앱 자신의 `_connect_memory()` 로 재확인해 전부 실재 확인.
`_ensure_oauth_client_schema` 가 예외를 삼키는 설계(CHG-20260812-0003)라 이 직접 확인이
REV-20260812-0003 에서 예고한 보완 절차였고, 실제로 작동했다.

**남은 미검증**: 인가 코드 → 토큰 교환 → 도구 호출의 **인증된 전 구간 e2e**. 사람 브라우저
로그인·동의가 필요해 자동 probe 로 대체할 수 없다(설계상 의도). #11 이 그 직전 단계까지 확인.

**배포 부작용**: probe 로 DCR client 1건(`deploy-probe`, redirect `https://probe.invalid/cb`)이
라이브에 생성됐다. `client_id` 만으로는 어떤 데이터에도 접근할 수 없어 무해하나, 운영자가
정리하려면 `WebOAuthClients` 에서 해당 행을 revoke 하면 된다.

### Run 2026-08-12 (2차) — 잔여 3건 단위 (Environment: local pytest)

| 스위트 | 결과 |
|---|---|
| `unit/feature-0041-external-ai-tool-surface/tests` | **136건 PASS** (기존 101 + 신규 30 + codex 회귀 6, 중복 제외) |
| `unit/feature-0003-agent-web-ui/tests` | PASS (`test_share_redaction_invariant` 컨테이너 경로 의존 제외) |

신규 커버리지 요지 — 발견 자료: `tool_surface` 계약 존재 · **인스턴스 데이터 0**(발급물 패턴
정규식) · 수기 카탈로그 · OpenAPI 7 operationId · 가이드가 "인가는 자동화 불가" 를 명시.
L4: 자카드 판정 5경계 · **계정 id 미노출** · **응답 미포함(원장 전용)** · fan-out 상한.
HTTP 전송: 토큰 무보관 · https 강제 · **loopback 기본 바인딩** · 검증끄기 loopback 한정 ·
**리다이렉트 금지(두 어댑터)** · 9 도구 동일성.

### Run 2026-08-12 (3차) — POST-DEPLOY 라이브 (Environment: live · e1372f32 · Caddy 경유)

| # | 항목 | 결과 |
|---|---|---|
| 1 | 서비스 4종 GIT_COMMIT | 전부 `e1372f32` ✅ |
| 2 | 무중단 실측 — caddy `no upstreams available` | **0건** ✅ |
| 3 | `GET /api/ai/guide` 에 부록 B 포함(**갱신 반영** 확인 — 이 자산의 실제 실패 모드) | ✅ |
| 4 | `GET /api/ai/manifest` → `tool_surface` (endpoints 8 · 키 9종) | ✅ |
| 5 | `GET /api/ai/openapi.json` → 도구 표면 **7 path** | ✅ |
| 6 | **익명 노출에 인스턴스 데이터 0** — 발급물 패턴 라이브 grep | **0건** ✅ (SEC-20260724) |
| 7 | 기존 경로 `/livez`·`/llms.txt`·`/.well-known/ai-conversation-api.json` | 전부 **200** ✅ |
| 8 | 도구 표면 무토큰 `open_task` | **401** ✅ |

**PB-0008 대체 검증(#3)**: 이번 cycle 의 `static/` 변경은 `ai-api-guide.md` 뿐이고 `text/markdown`
원문 서빙이라 렌더 표면이 없다. 의미 있는 실패 모드인 "배포본에 갱신 미반영" 을 내용 포함으로
확인했다(사유는 feature-0003 `docs/TEST.md` 에 기록).

**HTTP/SSE 전송 미기동**: 신규 프로세스라 라이브에 띄우지 않았다 — 기동은 운영 결정(포트 개방·
TLS 종단 프록시 배치가 선행). 코드 경로는 단위 계약으로 고정했고, 기존 서비스에 영향 0
(어느 compose 서비스에도 배선하지 않음).

### Run 2026-08-12 (4차) — 잔여 3건 완결 단위 (Environment: local pytest)

| 스위트 | 결과 |
|---|---|
| `unit/feature-0041-external-ai-tool-surface/tests` | **161건 PASS** (기존 136 + 신규 25) |

신규 커버리지 요지 — **기동**: compose 서비스가 `dbnet` 에 있음(없으면 전량 502) · 헬스체크가
HTTP 프로브 · `deploy-web.sh WORKERS` 편입 · Dockerfile 이 HTTP 어댑터만 COPY(서버측 보안 모듈이
어댑터 경로에 들어가면 안 된다) · 엣지 경로와 `_HTTP_PATH` 일치 · 익명 401 이 `reverse_proxy`
**앞**(순서가 뒤집히면 무력화) · failover 는 연결 실패에만.
**한도**: 콘솔 knob 4종 ↔ `DEFAULTS` 키 일치 · **소비처 없는 knob 부재**(존재하지 않는 방어 표시
금지) · `0 이하 = 무제한` · `open_task` 에 RPM·미제출 게이트 배선 · `check_open_tasks` 경계
양측(3<5 통과 / 5>=5 429) · 조회 실패 시 통과(규율 장치이지 부하 상한이 아니다).
**e2e**: 스크립트가 rootCA 존재 시 `--cacert` 로 검증하고 미검증 모드를 화면에 표시.

### Run 2026-08-13 (5차) — POST-DEPLOY 라이브

(배포 후 기록)

### Run 2026-08-13 (5차) — HTTP 전송 컨테이너 실기동 (Environment: agent 이미지 + SDK 2.0)

배포 실패 후, 고친 어댑터를 **실제 컨테이너**에서 띄우고 MCP 프로토콜을 왕복시켰다.

| # | 항목 | 결과 |
|---|---|---|
| 1 | SDK 2.0 으로 기동(`Uvicorn running`) | ✅ |
| 2 | `POST /api/ai/mcp` → `initialize` | **200** (SSE `event: message`) ✅ |
| 3 | 구 경로 `POST /mcp` | **404** ✅ (경로 정합이 실제로 걸려 있다) |
| 4 | `tools/list` | **9종** 전부 ✅ |
| 5 | 무토큰 `tools/call open_task` | `no_authorization` ✅ (ctx 헤더 경로 작동) |
| 6 | 가짜 토큰 `tools/call open_task` | **상류 401 전달** ✅ (검증된 TLS 로 web 도달) |

단위 스위트 **168건 PASS**.

### Run 2026-08-13 (6차) — 동작 테스트 + 뮤테이션 (Environment: local pytest)

codex 2차 P2 반영으로 문자열 검사를 **실행 검사**로 교체했다. 가짜 SDK 모듈을 주입해 어댑터를
실제 import·호출한다.

| 뮤테이션 | 결과 |
|---|---|
| v1 헤더 경로(`ctx.request_context.request.headers`) 제거 | **KILLED** |
| SNI 고정 무력화(`server_hostname=self.host`) | **KILLED** |
| `Host` 헤더 제거 | **KILLED** |
| verify-off 전수검사 → 첫 후보만 | **KILLED** |
| requirements 검사: `mcp` 줄 삭제 | **KILLED** (부분문자열 검사일 땐 SURVIVED — 그래서 고쳤다) |

스위트 **180건 PASS**.

### Run 2026-08-13 (7차) — 콘솔 배치 (Environment: local pytest + 라이브 payload 확인)

라이브 배포본에서 `runtime_settings` payload 버킷을 직접 확인해 **'실행 타임아웃' 패널에
섞여 있던 것**을 적발하고 전용 패널로 분리했다.

| # | 항목 | 결과 |
|---|---|---|
| 1 | payload 에 `ext_tool` 버킷 존재 + 응답 포함 | ✅ |
| 2 | `admin.html` 패널·서브탭 nav·mount div | ✅ |
| 3 | `settings.js` 패널 등록 + 재렌더 훅 + 전용 버킷 소비 | ✅ |
| 4 | 미저장 dot 이 `ext-tool-limits` 서브탭으로 라우팅 | ✅ |
| 5 | 프론트 키 미러 ↔ 백엔드 스펙 일치 | ✅ |
| 뮤테이션 | 버킷 분기 제거 / 미러 키 1개 누락 | 둘 다 **KILLED** |

### Run 2026-08-13 (8차) — PB-0008 콘솔 패널 (Environment: Windows-browser · Runner: AI)

- Bridge: relay `http://172.26.144.1:9223` (Chrome/150.0.7871.128) · 라이브 `feadc089`
- Evidence: `unit/feature-0003-agent-web-ui/docs/test-runs.d/evidence/REV-20260813T-ext-tool-panel-{before,after}.png`

**수정 전(결함 적발)**: 상한 4종이 '실행 타임아웃' 패널의 카테고리로 렌더됨. 서브탭 nav 에
`ext-tool-limits` 없음. → 문서가 주장하던 전용 섹션은 존재하지 않았다.

**수정 후(PASS)**: 서브탭 nav 에 '외부 AI 도구' 등장 · 패널 가시 · 4행(라벨·단위·기본값·'즉시
반영' 배지) 렌더 · '실행 타임아웃' 에서 해당 카테고리 소멸(`stillMixed: false`) · 기존 8종 보존.

### Run 2026-08-13 (9차) — 라이브 엣지 경유 MCP 전 구간 (Environment: live · feadc089)

| # | 항목 | 결과 |
|---|---|---|
| 1 | 서비스 6종 GIT_COMMIT 일치 | ✅ |
| 2 | caddy `no upstreams available` | **0건** ✅ |
| 3 | 무토큰 `POST /api/ai/mcp` (엣지 익명 차단) | **401** ✅ |
| 4 | 토큰 헤더 有 → `initialize` | **200** + serverInfo ✅ |
| 5 | `tools/list` | **9종** ✅ |
| 6 | `tools/call open_task` (가짜 토큰) | **상류 401 도달** ✅ (검증된 TLS 로 web 에 닿음) |
| 7 | 기존 경로 `/livez`·`/api/ai/manifest`·`/api/ai/openapi.json` | 전부 **200** ✅ |

### Run 2026-08-13 (10차) — 인증 접근성 (Environment: local pytest + node)

스위트 **235건 PASS**. 문자열이 아니라 **동작**을 보는 절을 추가했다.

| 뮤테이션 | 결과 |
|---|---|
| 오픈 리다이렉트 판정을 URL 해석 → 문자열 검사로 되돌림 | **KILLED** |
| scope 지원 밖을 조용히 무시 | **KILLED** |
| consent token 세션 결합 제거 | **KILLED** |
| consent token 서명 검증 제거 | **KILLED** |
| consent nonce 단일사용 해제 | **KILLED** |

`safeNextTarget` 은 node 로 9 케이스 실행: `/ai/connect`·쿼리 포함 경로는 허용,
`//evil.com`·`/\evil.com`·`https://evil.com`·`javascript:`·빈 값은 거절.

### Run 2026-08-13 (11차) — POST-DEPLOY 인증 접근성 (Environment: live · `5f20ee88`)

| # | 항목 | 결과 |
|---|---|---|
| 1 | 서비스 6종 GIT_COMMIT | 전부 `5f20ee88` ✅ |
| 2 | caddy `no upstreams available` | **0건** ✅ |
| 3 | `/.well-known/oauth-protected-resource` · `-authorization-server` · 경로접미 변형 | 전부 **200** ✅ |
| 4 | 엣지 무토큰 401 의 `WWW-Authenticate` | `Bearer resource_metadata="https://…/.well-known/oauth-protected-resource"` ✅ |
| 5 | 앱 무토큰 401 의 `WWW-Authenticate` | 동일 ✅ (엣지·앱 단서 일치) |
| 6 | **미로그인 `authorize`** (구 404 자리) | `302 → /?next=…` → **최종 200** ✅ |
| 7 | `/ai/connect` · `/api/ai/connect/status` | **200** ✅ |

### Run 2026-08-13 (12차) — 가이드 배포 반영 (Environment: live · `86d89b60`)

`GET /api/ai/guide` **200**(23,005 bytes) · `B.0-1`·`/ai/connect`·"셸 스크립트 실행을 요구하지
말 것"·`invalid_scope` 전부 포함(= 배포본 갱신 반영) · 익명 노출 인스턴스 데이터 **0건** ·
무중단 `no upstreams available` **0건**.

### Run 2026-08-14 (13차) — 엣지 401 호스트 정합 (Environment: 격리 엣지+web, 브랜치 코드)

컨테이너 네트워크 안에서 **443** 으로 Host 3종을 넣어 실측.

| Host | 상태 | `WWW-Authenticate` |
|---|---|---|
| `112.185.196.20` | 401 | `…https://112.185.196.20/.well-known/oauth-protected-resource` ✅ |
| `mysql-ai.company.local` | 401 | `…https://mysql-ai.company.local/…` ✅ |
| `localhost` | 401 | `…https://localhost/…` ✅ |

수정 전 라이브 실측(대조): 엣지는 세 경우 모두 `mysql-ai.company.local` 을 반환했고, 앱은
접속 호스트를 따랐다 — 그 불일치가 IP 접속 시 discovery 를 끊었다.

### Run 2026-08-14 (14차) — POST-DEPLOY 호스트 정합 (Environment: live · `be7e5d00`)

| # | 항목 | 결과 |
|---|---|---|
| 1 | 401 단서가 접속 호스트를 따름 — `112.185.196.20` / `mysql-ai.company.local` / `localhost` | 3종 전부 **자기 호스트** ✅ |
| 2 | 익명 `/api/ai/mcp` | **401** ✅ (차단 유지) |
| 3 | 토큰 헤더 有 → `initialize` | **200** ✅ (인증 경로는 여전히 `ext-tool-mcp` 도달) |
| 4 | IP 경유 discovery 자기정합 | `resource=https://112.185.196.20/api/ai/mcp` · `AS=https://112.185.196.20` ✅ |
| 5 | `no upstreams available` | **0건** ✅ |

### Run 2026-08-14 (15차) — 실사용 제보 결함 (Environment: local pytest + 라이브 데이터)

스위트 **271건 PASS**, 신규 회귀 20건.

| 뮤테이션(제보된 결함을 되돌림) | 결과 |
|---|---|
| DCR 정규식을 원래대로 좁힘 | **KILLED** |
| `describe_table` 이 다시 `table` 을 보냄 | **KILLED** |
| 단일 바인딩 라벨 경로 제거 | **KILLED** |
| grounding 이 다시 라벨을 scope 로 사용 | **KILLED** |
| `focus` 인자 제거 | **KILLED** |

라이브 데이터 실측(격리 컨테이너 + 운영 DB 읽기):
- `product=109` → `labels=['mssql-dk-dev']` · `scope_key=mssql-ba175631e9fc` (전엔 둘 다 빈 값)
- 질문에 테이블명 없음 → grounding 0자(**설계상 정상** — 이제 사유와 `focus` 안내를 반환)
- 질문에 테이블명 포함 → grounding **223자** + 도메인 개요

### Run 2026-08-14 (16차) — POST-DEPLOY 제보 결함 (Environment: live · `35c60a3f` · 공인 IP)

| # | 항목 | 결과 |
|---|---|---|
| 1 | 실제 클라이언트 이름 DCR — `Claude Code (mysql-ai)` · `Cursor/1.0` · `VS Code [MCP]` | 전부 **201** ✅ (이전 400) |
| 2 | `/ai/oauth/callback` 3분기(code · error · 인자없음) | 전부 **200** ✅ |
| 3 | 가이드에 `focus` · `schema_name` · `/ai/oauth/callback` 반영 | 전부 포함 ✅ |
| 4 | `no upstreams available` | **0건** ✅ |

검증용 probe client 3건은 revoke 했다.

### Run 2026-08-14 (17차) — execute_sql + 스코프 (Environment: local pytest + 라이브 데이터)

라이브 데이터로 실행 경로를 직접 태워 확인:

| # | 항목 | 수정 전 | 수정 후 |
|---|---|---|---|
| 1 | `list_schemas` 대상 서버(제품 109, 단일 바인딩) | **메모리 DB** — `agent_attachment_*`·`account_db` 노출 | 제품 MSSQL — `dbo` 등 |
| 2 | 스키마 allowlist | **미설정**(무제한) | `_product_allowed_schemas` 11개 |
| 3 | 방언 | MySQL 고정 → `Invalid column name 'TABLE_ROWS'` | 엔진 따라감 |
| 4 | `execute_sql` 허용 DB | — | 통과(3행) |
| 5 | `execute_sql` 비허용 DB(`master`) | — | **차단** |
| 6 | 쓰기 / 다중문 / 내부 스키마 | — | **전부 차단** |
| 7 | CSV 파일 생성 · 응답 내 경로 | — | **미생성** · 경로 0 |
| 8 | 원장 실제 행수 | — | `{'total_rows': 3, 'csv_paths': []}` |

뮤테이션 **7종 전부 KILL**. 스위트 전체 green(0003·0023·0041).

### Run 2026-08-14 (18차) — POST-DEPLOY (Environment: live · `956ae5e1`)

| # | 항목 | 결과 |
|---|---|---|
| 1 | `list_schemas` 대상 — 제품 datasource | `['dbo', 'DBZONE\\vaiorezzodz']` ✅ |
| 2 | **첨부 샌드박스 노출** | **0건** ✅ (수정 전엔 목록에 나왔다) |
| 3 | `execute_sql` 허용 DB | 통과 ✅ |
| 4 | `execute_sql` 비허용 DB(`master`) | **차단** ✅ |
| 5 | 응답 내 CSV 경로 | **없음** ✅ · 통계 `{'total_rows': 2, 'csv_paths': []}` |
| 6 | `no upstreams available` | **0건** ✅ |

### Run 2026-08-14 (19차) — 게이트 코칭 (Environment: local pytest + 라이브 재현)

라이브 재현으로 관찰 4건을 분류했다(위 REVIEW 표). 확정 결함 1건 + 문구 개선 2건.

- `_heavy_query_coach("SELECT COUNT(*) …", facts={})` → 이제 "전역 집계"·"approx_rows"·
  "총 스캔량을 줄이지 않습니다" 를 포함하고, "서버측 집계(COUNT/SUM/GROUP BY)" 는 **빠진다**.
- 계획 사실이 없을 때 "실행계획·접근형태·사용 인덱스·스캔 파티션" 을 **지어내지 않는다**(기존 계약 보존).
- `_catalog_function_redirect("forbidden function: object_name")` → INFORMATION_SCHEMA 경로
  (`REFERENTIAL_CONSTRAINTS` 포함), 무관한 거부에는 빈 문자열.

스위트: 0002 · 0003 · 0023 · 0041 전부 green.

### Run 2026-08-14 (20차) — POST-DEPLOY (Environment: live · `25637d1c`)

19차는 배포본 문구를 재현했을 뿐 **서비스별 커밋 일치를 기록하지 않았다**. 그 공백을 메운다.

| # | 항목 | 결과 |
|---|---|---|
| 1 | `web-a` GIT_COMMIT | `25637d1c` ✅ |
| 2 | `web-b` GIT_COMMIT | `25637d1c` ✅ |
| 3 | `ask-worker` GIT_COMMIT | `25637d1c` ✅ |
| 4 | `insight-worker` GIT_COMMIT | `25637d1c` ✅ |
| 5 | `ext-tool-mcp` GIT_COMMIT | `25637d1c` ✅ (외부 도구 전송 프로세스도 동일 커밋) |
| 6 | `ops-scheduler` GIT_COMMIT | `25637d1c` ✅ |
| 7 | `GET /healthz` | `status=ok` · `git_commit=25637d1c` · `mysql_ok=true` · `pg_ok=true` ✅ |
| 8 | 엣지 익명 `POST /api/ai/mcp` | **401** ✅ (인증 없는 도달면 없음) |

6개 서비스 전부 동일 커밋 — 부분 롤아웃 잔재 없음. 무중단, 사용자 영향 0건.

### Run 2026-08-14 (21차) — AC-7 답변 보존 (Environment: local pytest · agent 이미지)

신규 `test_answer_persistence.py` **24건** + 기존 스위트 무회귀.

**각인 (L2, 수신 방향)**

- 저장본이 `⟦UNTRUSTED-DATA⟧` 로 구획된다 ✅
- **방향 단정** — 저장 각인에는 `never as instructions`(우리 LLM 대상)가 있고 `[SCOPE]`
  (외부 AI 대상)는 **없다**. 나가는 `wrap_tool_output` 은 그 반대 ✅
  두 함수를 바꿔 쓰면 지연 인젝션 차단이 성립하지 않으므로 문구로 못박았다.
- 위조 close 마커를 담은 답변을 넣어도 sentinel 이 각각 1개 ✅ (breakout 차단)
- label 경로(계정명·datasource)의 sentinel 도 strip ✅
- `datasource=` 는 값이 있을 때만 라벨에 등장 ✅ (빈 값 노이즈 금지)

**저장 계약**

- UPDATE SET 절에 `Answer`·`AnswerBytes`·`AnswerVerdict`·`AnswerTruncated`·`SourceTasks` ✅
- 저장 실패 → 503 + rollback, `recorded: true` 미반환 ✅ (fail-closed)
- `AnswerBytes` 는 **원문** 바이트(`len(answer.encode("utf-8"))`) ✅ — 각인 래퍼를 포함해 세면
  원장 `bytes_out` 과 영구히 어긋난다
- 상한 초과는 조용히 잘리지 않고 `AnswerTruncated` 로 표시 ✅
- 고신뢰 인젝션 답변은 **저장 전에** 400 거절 + 원장에 `injection:` 기록 ✅
  (거절 분기가 `UPDATE` 보다 앞이라는 것을 인덱스 비교로 단정)

**열람 경계**

- 두 route 모두 `_require_task_reader` 통과 필요 · `require_ai_token` **미사용** ✅
- 권한 키 `console.aiops.read` · `audit.read.any` 가 카탈로그에 **실재**함을 단정 ✅
  (없는 키로 게이트하면 관리자도 조용히 자기 것만 보게 된다 — codex P2)
- 전역 권한 없으면 `AND AccountId = %s`, 계정 정보가 비어도 전역으로 열리지 않음 ✅
- 목록은 답변 본문 미포함(`Answer IS NOT NULL` 만), 상세는 각인된 원본 그대로 ✅
- 스코프 밖 task 는 403 이 아니라 404 ✅ (존재 여부를 권한으로 갈라 알리지 않음)
- 상세에 PG 원장 도구 이력 합류, 조회 실패는 fail-soft ✅

**무회귀**

- `unit/feature-0003-agent-web-ui/tests` · `feature-0041/tests` · `feature-0023/tests` 전건 green
- route 골든 `route_snapshot_p5b.json` 248 → **250** 갱신(신규 2 route: `/api/ai/tasks`,
  `/api/ai/tasks/{task_id}`)
- 신규 테스트가 **단독 실행·전체 스위트 양쪽**에서 통과함을 확인. 첫 판은 `sys.modules`
  스텁이 전체 실행 시 진짜 `app` 에 밀려 무시돼 단독에서만 통과했다 — 그대로 뒀으면 통과하는
  무력한 테스트가 됐다. `monkeypatch` 로 실제 참조 모듈을 직접 패치해 해소.
- 기존 실패 1건은 pre-existing: `test_oauth_exhaustion_gate.py::test_write_failure_after_...`
  는 컨테이너에 `chattr` 이 없어 실패한다(main 체크아웃에서도 동일 재현 — 본 변경 무관).

**codex 2차 재검증 반영 (같은 Run)**

- `bin/mysql-ddl-lint.sh` **PASS** — 신규 ALTER 6건 전부 `ALGORITHM=INPLACE, LOCK=NONE`.
  (수정 전 실행에서 6건 전건 FAIL 을 실측했다. 절을 상수로 빼면 텍스트 스캐너가 못 따라와
  여전히 FAIL 하므로 리터럴로 둔다 — 이것도 실측으로 확인.)
- 거절 시 `AnswerVerdict` 만 task 행에 남고 페이로드는 저장되지 않음 · `SubmittedAt IS NULL`
  가드로 확정된 답변의 판정을 덮지 않음 ✅
- 재제출·동시 제출 방어: `WHERE … AND SubmittedAt IS NULL` + `rowcount` 0 → **409** ✅
  (조건이 SQL 안에 있음을 단정 — 미리 읽고 분기하면 TOCTOU 로 둘 다 통과한다)
- 콘솔 답변 칸 3-상태 분기(본문 있음 / 미제출 / **보존 안 됨**) — 롤링 배포 창에서 구버전
  replica 가 처리한 제출을 '미제출' 로 뭉뚱그리지 않는다 ✅
- 전체 스위트 재실행 green (0003 · 0041 · 0023).
