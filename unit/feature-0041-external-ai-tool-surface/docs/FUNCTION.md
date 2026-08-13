---
doc_type: FUNCTION
feature_id: feature-0041-external-ai-tool-surface
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

외부 사용자의 AI 런타임(Claude Code 등 MCP 클라이언트)이 **스스로 추론하면서** 본 서비스의
데이터소스·RAG·메타지식에 접근할 수 있도록, 내부 에이전트가 쓰던 도구를 인증·스코프·원장이
붙은 **외부 도구 표면**으로 노출한다. 추론이 호출자 런타임에서 일어나므로 LLM 토큰 비용은
호출자에게 귀속되고, 서비스는 자격증명을 일절 보관하지 않는다. 신원은 **우리 로그인 세션**
(사용자별)이 정하고 비용은 **머신의 AI 런타임**이 부담하는 2축 분리 구조이며, 그 비대칭에서
오는 세션 교차오염을 구조적 유도 + 결정론적 탐지로 다룬다.

feature-0023(외부 AI가 `ask` 로 **우리 LLM의 답변**을 받는 축)과는 목적·신뢰경계·비용 주체가
다른 별개 표면이다. 두 표면은 병존하며 용도로 구분한다.

## 2. Goal

- REQ-20260812-external-ai-tool-surface: 외부 AI가 자기 계정 LLM으로 추론하면서 본 서비스의
  데이터·컨텍스트에 접근하는 도구 표면을 제공한다. 서비스는 사용자 LLM 자격증명을 보관하지
  않고, 대화 기록은 서비스 측에 남으며, 세션 간 데이터 교차오염은 유도·탐지로 통제한다.

## 3. In Scope (P0)

- **인증(OAuth AS)**: Dynamic Client Registration + Authorization Code + **PKCE S256 강제**.
  사람이 브라우저에서 로그인·동의하는 단계 필수. 단기 access token + refresh, 웹 로그아웃 시
  revoke 전파.
  - **저장 계약**(codex P1): 인가 코드는 **1회용 + 단TTL**(≤60s) 이고 발급 시 `client_id` ·
    `redirect_uri` · `code_challenge` 에 결합된다. access/refresh 는 **해시 저장**
    (`WebApiTokens.TokenHash` 규약 재사용). refresh 는 **rotation** 하며 **reuse 탐지 시 해당
    계열 전체 폐기**.
  - **DCR 정책**(codex P1): `redirect_uri` 는 **HTTPS 고정**(native loopback
    `http://127.0.0.1:*` · `http://localhost:*` 만 예외) · **정확 일치**(prefix/와일드카드 금지) ·
    등록 **rate limit** + 등록 감사. 임의 URI 등록을 허용하면 인가 코드 탈취·피싱 표면이 열린다.
- **client instance 등록**: 머신의 AI 런타임을 `client_id`로 1급 식별. 모든 세션은
  `(client_id, account_id)` 쌍으로 열린다.
- **task 세션 계약**: `open_task` → `get_task_context` → (도구 호출)* → `submit_answer`.
  모든 도구 호출에 `task_id` 필수.
- **P0 도구 9종**: `open_task` · `get_task_context` · `list_schemas` · `describe_schema` ·
  `describe_table` · `search_tables` · `get_foreign_keys` · `get_table_indexes` · `submit_answer`
- **세션 격리 4층(L1~L4)**: 도구 이름 네임스페이싱 · 데이터 블록 세션 각인 · 결정론적 교차오염
  탐지 · 권한 비대칭 flag
- **인젝션 처리**: 나가는 데이터 datamark 각인(3층) + 들어오는 텍스트 3단 판정
  (allow / neutralize+flag / reject) + **저장 시점** datamark
- **부하 원장**: `tool_call_usage` 신설 + 토큰·계정·client 단위 rate/동시성/누적 행수 게이트
- **대화 기록**: 원 질문(`open_task`)·조회 원장·최종 답변(`submit_answer`)을 서비스 측에 적재
- **전송 2종**: REST 정본 + stdio MCP 어댑터(i) + HTTP/SSE MCP(ii)
- **발견 자료**: 익명 static contract에 등록·인가 흐름 가이드 추가(인스턴스 데이터 0 유지)

## 4. Out of Scope

- **P1 이후로 이월**: `execute_sql` · `explain_query` · `get_sample_rows`(행수 예산·rate
  limit·추출 원장이 선행 조건) / `describe_routine` · `search_routines` ·
  `check_table_coverage` · `graph_navigate`(P2) / `review_answer` opt-in red-team(P3)
- **영구 제외**: `scratch_*` 4종 · `read_attachment` · `update_attachment` — 쓰기·첨부 계열은
  외부 노출 대상 아님(세션 간 서버측 공유 상태를 만들지 않기 위함이기도 하다)
- 사용자 LLM 자격증명의 보관·대리 호출(ANCHOR §2 Alt-B/C에서 폐기)
- feature-0023 `ask` 축의 동작 변경 — 무회귀
- 외부 AI 런타임 내부의 컨텍스트 격리 강제 (구조적으로 불가 — §9 참조)

## 5. Inputs

- OAuth: client 등록 요청, 인가 코드, refresh token
- 도구 인자: `task_id` · `question` · `schema`/`table`/`datasource` 식별자 · `source_tasks` ·
  `answer` · `self_review`(P3)
- 서버 설정: rate/동시성/누적 행수 상한, `context_depth` 기본값, 인젝션 판정 임계

## 6. Outputs

- 도구 결과: datamark 각인된 데이터 블록(`account`·`conversation`·`task`·`source` 라벨 포함)
- `tool_call_usage` 원장 행 (계정·client·task·도구·대상·행수·바이트·추정 스캔행·지연·판정)
- `messages` 적재 (원 질문 / 최종 답변, `meta_json.source='external_ai'`)
- 교차오염·인젝션·미제출 이벤트 플래그
- MCP 서버 `instructions` (세션 규범 전문, 연결당 1회)

## 7. Main Flow

1. AI 런타임이 공개 가이드로 등록 → `client_id` 획득
2. 인가 URL 제시 → **사람이 브라우저에서 로그인·동의** → access/refresh token 발급
3. MCP 연결 수립 — 서버 `instructions`에 세션 규범(account·session 각인) 주입, 도구 이름에
   세션 라벨 부여
4. `open_task(question)` → `task_id` 발급 + 원 질문 적재
5. `get_task_context(task_id)` → grounding 번들 조립(조회만, LLM 0) → datamark 각인 후 반환
6. 구조 조회 도구 호출 → 스코프 교차검증 → 각인 → 원장 기록
7. `submit_answer(task_id, answer, source_tasks)` → 선언 vs 원장 대조 → 대화 적재 → 판정 반환

## 8. Edge Cases

- 웹 세션 만료·로그아웃 → 다음 도구 호출 401 (revoke 전파)
- 인자의 datasource/schema가 계정 허용 집합 밖 → 403, fail-closed
- `task_id` 누락·타 계정 task → 400/403
- `submit_answer` 미호출로 방치된 task → `incomplete` 마감 + 미제출률 집계
- 동일 `client_id`의 다중 세션 동시 활성 → 허용하되 권한 집합 비대칭이면 flag
- grounding 요약 부재 → 기존 lazy 패턴대로 `request()`만 남기고 빈 섹션 반환(LLM 0)
- 인젝션 고신뢰 패턴 → 400 + client 단위 누적 카운터

## 9. Error Handling

- 인증·스코프 위반은 **fail-closed** (403/401), 부하 상한 초과는 429 + `retry-after`
- **원장 기록과 예산 차감은 원자적이며 fail-closed**(codex P1) — 도구 결과를 반환하기 **전에**
  `tool_call_usage` 기록(행수·바이트 포함)이 커밋되어야 하고, 기록 실패 시 결과를 반환하지
  않는다(5xx). 원장이 곧 누적 예산의 원천이므로 best-effort로 두면 **기록 실패가 상한 우회**가
  되어 AC-6과 모순된다. 관측 전용 필드(지연·판정 상세)의 결손만 best-effort 허용.
- **알려진 한계(강제 불가)**: 외부 AI가 세션 A의 데이터를 기억한 채 세션 B에 서술로 답하는 것은
  탐지도 차단도 못 한다. 각인·선언·대조는 "몰라서 섞임"을 제거할 뿐이고 "알고도 섞음"은 사후
  탐지 대상이다. `submit_answer` 미호출 역시 강제할 수 없다(소프트 강제만). SECURITY.md §14가
  "확률적 완화이지 보장이 아니다"라고 못박은 것과 동일한 성격이며, 실 경계는 RBAC·SQL
  guard·스코프 격리가 진다.

## 10. Dependencies

### 내부 기능 의존성
- feature-0023-conversation-api-access — Bearer 인증 경로·scope 교집합 choke-point·절대
  denylist·`WebApiTokens`·발견 계약. 본 feature는 그 위에 OAuth AS와 원시 도구 축을 얹되
  `ask` 축은 무변경
- feature-0003-agent-web-ui — 세션·RBAC·audit·`web_context.py` 권한 카탈로그
- feature-0002-agent-core — 도구 정의(`modules/tools.py`)·`_datamark_untrusted`(`agent_core.py`)·
  grounding 조립(`modules/cluster_context.py`)
- feature-0031/0033/0037 — L0 증거·L2 클러스터 요약·L3 도메인 개요 (grounding 번들 원천)
- feature-0005-qa-mcp — MCP 서버 패턴
- feature-0021-redteam — 검토 규약(P3 `review_answer`에서 재사용)

### 외부 의존성
- MCP SDK (`mcp.server.fastmcp.FastMCP` — `instructions`·`auth_server_provider`·
  `token_verifier`·`streamable_http_path` 지원 확인)

### shared 모듈 의존성
- `shared/config.py` — datasource/product ContextVar (호출 단위 설정으로 전환 필요)
- `shared/runtime_settings.py` — 상한 knob

## 11. Acceptance Criteria

- AC-20260812T075301-external-ai-tool-surface-1: 인가 없이 도구를 호출하면 401이고, 웹에서
  로그아웃하면 그 세션의 다음 도구 호출이 401이 된다(세션 실재 강제).
- AC-20260812T075301-external-ai-tool-surface-2: 계정 허용 집합 밖의 datasource/schema를 인자로
  넘기면 403이며, 허용 집합은 인자가 아니라 세션 계정에서 도출된다(fail-closed).
- AC-20260812T075301-external-ai-tool-surface-3: 모든 도구 반환 데이터가
  `⟦UNTRUSTED-DATA account=… conversation=… task=… source=…⟧` 로 구획되고, 블록 내부의
  sentinel 위조 시도가 제거된다.
- AC-20260812T075301-external-ai-tool-surface-4: `get_task_context` 가 우리 LLM을 **한 번도**
  호출하지 않는다(테스트가 LLM 진입점 미호출을 단정).
- AC-20260812T075301-external-ai-tool-surface-5: `submit_answer` 의 `source_tasks` 선언과 실제
  원장이 불일치할 때 **명시적 유출 신호**(타 task의 datamark 라벨 · `task_id` 문자열 · 세션
  카나리 · 결과셋에 **원문 그대로** 존재하는 값)가 답변에 있으면 교차오염으로 판정·기록된다.
  **탐지 범위 한정(codex P2)**: 외부 AI가 값을 요약·환산·재서술하면 어느 task에서 왔는지
  결정론적으로 판별할 수 없다 — 본 AC는 미탐(false negative)을 허용하며, 탐지율을 보장하지
  않는다. 테스트는 "명시적 유출 양성 / 정상 답변 음성"만 단정한다.
- AC-20260812T075301-external-ai-tool-surface-6: 모든 도구 호출이 `tool_call_usage`에 기록되고,
  토큰·계정·client 단위 rate/동시성/누적 행수 상한 초과 시 429가 된다.
- AC-20260812T075301-external-ai-tool-surface-7: `open_task` 의 원 질문과 `submit_answer` 의
  최종 답변이 서비스 측 대화에 적재되며, **저장 시점에** datamark가 입혀진다(지연 인젝션 차단).
- AC-20260812T075301-external-ai-tool-surface-8: 고신뢰 인젝션 패턴은 400으로 거절되고,
  저·중신뢰 패턴은 통과하되 flag가 남는다(오탐으로 정상 질의가 막히지 않는다).
- AC-20260812T075301-external-ai-tool-surface-9: feature-0023 `ask` 경로의 기존 동작·scope·
  절대 denylist가 무변경이다(회귀 테스트).
- AC-20260812T075301-external-ai-tool-surface-10: 인가 코드는 1회 소비 후 재사용 시 거절되고,
  refresh rotation 후 **구 refresh token 재사용 시 해당 계열 전체가 폐기**된다. access/refresh 는
  평문으로 저장되지 않는다(해시 조회로만 검증).
- AC-20260812T075301-external-ai-tool-surface-11: DCR 로 등록되는 `redirect_uri` 는 HTTPS
  (또는 loopback) 이고 인가 시 **정확 일치**로만 매칭된다 — prefix·와일드카드·비-loopback HTTP
  등록은 거절되며, 등록 rate limit 초과 시 429.

## 12. Observability

- `tool_call_usage` — 도구·대상·행수·바이트·추정 스캔행·지연·판정(ok/denied/gated/error)
- 교차오염 의심 이벤트 (client_id·task 쌍·판정 근거)
- 인젝션 판정 카운터 (allow/neutralize/reject, client 단위 누적)
- task 미제출률 (client·계정 단위)
- 관리 콘솔: `시스템 > 설정 > **외부 AI 도구**` — **전용 패널**(`ext-tool-limits`)로 4 knob 을
  운영자가 재기동 없이 조절. payload 는 `ext_tool` 버킷(`external_tool_surface` 그룹).
  ⚠ 그룹을 미분류로 두면 `timeouts` 버킷으로 흘러가 **'실행 타임아웃' 패널에 섞인다**
  (라이브에서 실제로 그렇게 렌더됐다 — 부하 상한을 타임아웃 화면에서 찾게 된다).
  역할별/계정별 override 는 미도입(전역 상한만) — `WebRoleTokenQuotas` 패턴 복제는 실수요
  확인 후로 미룬다

## 13. Pre-approved Changes

- 없음 (Critical — §7.1 Plan 승인 후 착수. `PLAN-APPROVED` 2026-08-12)

## 14. 구현 현황 (2026-08-13, P0)

구현된 파일과 §11 AC 의 대응. 라이브 배포는 3회 완료. **인가 이후 구간의 e2e 만 미실측** —
사람 브라우저 인가 1회가 필요하다(`docs/E2E_RUNBOOK.md`).

| 계층 | 파일 | 커버하는 AC |
|---|---|---|
| OAuth 저장 계약 | `src/oauth_store.py` | AC-1(세션 실재) · AC-10(코드 1회용·rotation/reuse·해시) · AC-11(DCR redirect) |
| OAuth HTTP | `routers/oauth_as.py` | 위 계약의 전송면 |
| authz seam | `src/tool_authz.py` | AC-2(스코프 fail-closed) |
| 각인·탐지·판정 | `src/session_guard.py` | AC-3(각인) · AC-5(교차오염, 명시 신호 한정) · AC-8(인젝션 3단) |
| 부하 원장 | `src/tool_ledger.py` + alembic 0055 | AC-6(원장·429·fail-closed) |
| 도구 표면 | `routers/ai_tools.py` | AC-4(`get_task_context` LLM 0) · AC-7(원 질문·답변 적재) |
| MCP 어댑터(stdio) | `src/external_tool_mcp_server.py` | L1 세션 격리(라벨 필수·https 강제·응답 상한) |
| MCP 어댑터(HTTP) | `src/external_tool_mcp_http.py` + compose `ext-tool-mcp` + Caddy `/api/ai/mcp` | 설치물 0 접속면. L1 없음(정직 표기) · 익명 연결 엣지 차단 · **SDK v1/v2 양 세대** · upstream 은 이름 고정한 **검증된 TLS** |
| 상한 조절 | `shared/runtime_settings.py` 그룹 `external_tool_surface` + `ext_tool` payload 버킷 · `admin.html` 패널 `ext-tool-limits` · `admin/settings.js` `mountExtToolLimitsPanel` | AC-6 의 운영 조절면 |
| 무회귀 | — | AC-9(feature-0023 `ask` 축 · 전 스위트 green) |
| 무회귀(부트스트랩) | `_ensure_oauth_client_schema` 예외 봉인 | catchup 체인 중단 방지 — 신규 테이블 부재는 이 feature 만 fail-closed, 무관 서브시스템 무영향 |

> ⚠ **코드 거주지**: 서버측 모듈 4종은 `unit/feature-0003-agent-web-ui/src/` 에 있다(= 컨테이너
> `/app/web`). feature-local `src/` 에 두면 agent 이미지가 COPY 하지 않아 **라이브 기동이 죽는다**
> (배포 1차 실패로 실증 — CHG-20260812-0004). `test_container_importability.py` 가 이 계약을 고정한다.
> MCP 어댑터만 feature-local 에 남는다 — 클라이언트 측에서 실행되므로 이미지에 들어갈 이유가 없다.

**노출 규율**: 콘솔에 올린 knob 은 그 자체로 "이 방어가 존재한다" 는 주장이다. 소비처 없는
knob 은 두지 않는다(`AGENT_EXT_TOOL_CONCURRENCY` 를 이 사유로 삭제 — REV-20260812-0009 #4).
`DEFAULTS` ↔ 콘솔 스펙 키 일치를 테스트가 검사한다.

**SDK 세대**: `mcp` 파이썬 SDK 2.0 이 `mcp.server.fastmcp` 를 제거하고
`mcp.server.mcpserver.MCPServer` 로 갈았다. 가이드가 안내하는 `pip install mcp` 는 2.x 를 주므로
**두 세대를 모두 받는다.** v2 엔 전역 `get_context()` 가 없어 헤더는 도구가 받은 ctx 로 읽는다
(`ctx.headers` / `ctx.request_context.request.headers`). 이미지 하한은 `mcp>=1.9`
(그 이전 v1 엔 streamable-http 전송이 없어 import 만 되고 run 에서 죽는다).

**전송 2종 차이(정직 표기)**: stdio 는 도구 이름에 라벨을 접미해 **호출자 AI 가 세션을 구분**할
수 있다(L1). HTTP 는 단일 표면이라 L1 이 없다 — 여러 계정을 동시에 다룰 때는 stdio 를 권한다.
서버측 방어(L2 각인·L3 대조·L4 원장)는 두 전송에 동일하게 적용된다.
