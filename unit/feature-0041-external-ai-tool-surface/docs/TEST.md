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
