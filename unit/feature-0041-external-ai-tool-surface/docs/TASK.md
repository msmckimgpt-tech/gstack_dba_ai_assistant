---
doc_type: TASK
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress (PLAN-APPROVED 2026-08-12 → P0 구현 완료 · 라이브 배포 대기)
- Owner: AI (계획) / Human (승인)
- Priority: high
- Last Updated: 2026-08-12

## 2. Implementation Plan

### 2.1 Plan

**위험도: Critical** (§12.3 — 인증·인가 trust 모델 신설 + **신규 데이터 유출면**).
§7.1에 따라 계획 승인 전 구현 착수 금지. §18.8 security 렌즈 대상.

#### 영향받는 파일 · symbol

| 경로 | symbol / 변경 | 비고 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py` | **신규** — `register_client` · `authorize` · `token` · `revoke` + `_consume_auth_code()` · `_rotate_refresh()` · `_validate_redirect_uri()` | OAuth AS. PKCE **S256 강제**. 동의 화면은 기존 세션 인증 뒤. **저장 계약**(codex P1): 코드 1회용·TTL≤60s·(client_id, redirect_uri, code_challenge) 결합 / 토큰 해시 저장 / refresh rotation + reuse 시 계열 폐기. **DCR 정책**: redirect_uri HTTPS 고정(loopback 예외)·정확 일치·등록 rate limit |
| `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` | **신규** — P0 도구 9종 REST 핸들러 | 정본. MCP 어댑터는 이 API의 얇은 래퍼. **원장 기록+예산 차감은 결과 반환 전 원자적 커밋**(codex P1 — 실패 시 5xx, 결과 미반환) |
| `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py` | `_ensure_oauth_client_schema()` 신규 (`WebOAuthClients`·`WebOAuthGrants`·`WebOAuthTokens`) | `_ensure_web_api_tokens_schema` idiom 복제. 토큰은 해시 컬럼만(평문 컬럼 없음), refresh 계열 식별자 포함 |
| `unit/feature-0003-agent-web-ui/src/web_context.py` | `_get_account_by_oauth_token()` 신규, `_account_permissions` scope 교집합 재사용 | 절대 denylist 무변경 |
| `unit/feature-0002-agent-core/alembic/versions/00XX_tool_call_usage.py` | **신규** — `agent_runtime.tool_call_usage` | additive. `llm_usage` 와 동형 배치 |
| `unit/feature-0002-agent-core/src/modules/tools.py` | 핸들러의 스코프 원천을 ContextVar → **명시 인자**로 승격 (`execute_sql` 등 P1 대비 포함) | `llm_usage` 의 conversation_id 명시 전달과 동형 |
| `unit/feature-0002-agent-core/src/agent_core.py` | `_datamark_untrusted(content, label)` **호출측** label 확장 | 함수 시그니처 무변경 |
| `unit/feature-0041-.../src/external_tool_mcp_server.py` | **신규** — stdio 어댑터 (도구 이름 prefix 인자) | `conversation_mcp_server.py` 패턴 복제 |
| `unit/feature-0041-.../src/session_guard.py` | **신규** — `datamark_label()` · `detect_cross_session()` · `classify_injection()` | 격인·탐지·판정 |
| `shared/config.py` | `set_active_datasource` 계열에 명시 스코프 진입점 추가 | ContextVar 유지(내부 경로 무회귀) |
| `shared/runtime_settings.py` | 상한 knob 5종 (`AGENT_EXT_TOOL_RPM` 등) | feature-0018 슬라이스 재사용 |
| `docs/SECURITY.md` | 신규 절 (외부 도구 표면 위협모델) + §14 각인 확장 | §18.8 필수 |
| `docs/ARCHITECTURE.md` · `docs/ROUTEMAP.md` | feature 표 + 의존 표 + `gen-routemap.py` 재생성 | CI Code-Navigation gate |
| `unit/feature-0023-.../docs/ANCHOR.md` | §1에 방향 분기 한 줄(원시 도구 축은 0041) | **§4 아님** — §4는 human-only |

#### 접근 방법

1. **원장·스키마 먼저** — `tool_call_usage` + OAuth 테이블. 게이트 없는 도구를 먼저 열지 않는다.
2. **authz seam 승격** — 도구 핸들러가 스코프를 인자로 받도록 바꾸고, 내부 에이전트 경로는
   ContextVar에서 읽어 그 인자를 채우는 어댑터로 무회귀 유지. 이게 이 cycle의 최대 리팩터.
3. **OAuth AS** — MCP SDK의 `auth_server_provider`/`token_verifier` 활용. 사람 동의 단계는
   기존 세션 인증 뒤에 둔다. 로그아웃 → revoke 전파.
4. **도구 9종 REST** — 각 핸들러는 (스코프 교차검증 → 실행 → 각인 → 원장) 순서 고정.
5. **격리·판정** — L1 prefix, L2 각인, L3 대조, L4 flag + 인젝션 3단.
6. **MCP 어댑터 2종** — 로직 금지(얇은 래퍼), 서버 `instructions` 주입.
7. **문서·발견 자료** — SECURITY 신규 절, 익명 가이드에 등록·인가 흐름(인스턴스 데이터 0 유지).

#### 완료 판정 기준 (항목별)

- 원장: 도구 호출 1건마다 `tool_call_usage` 1행. 상한 초과 시 429 + `retry-after`.
  **원장 기록 실패를 주입하면 결과가 반환되지 않는다**(fail-closed 회귀 테스트 — 기록 누락으로
  누적 상한을 우회할 수 없음).
- OAuth 저장 계약: 인가 코드 2회 소비 시 2번째 거절 / 구 refresh 재사용 시 계열 폐기 확인 /
  DB에 평문 토큰 컬럼 부재 / `redirect_uri` prefix·와일드카드·비-loopback HTTP 등록 거절.
- authz seam: 허용 밖 datasource 인자에 403. **기존 내부 대화 경로 회귀 0**(전체 스위트 green).
- OAuth: 인가 없이 401 / 로그아웃 후 401 / refresh 정상 갱신 — 라이브 3-probe.
- 도구: 9종 각각 스코프 위반 403 + 정상 200 + 각인 존재를 단정하는 테스트.
- 각인: 반환 본문에 `account=`·`task=` 라벨 존재, sentinel 위조 문자열 제거 확인.
- 교차오염: 인위적 오염 페이로드로 `detect_cross_session()` 양성, 정상 답변에 음성.
- 인젝션: 고신뢰 패턴 400, `system_prompts` 같은 정상 식별자 통과(오탐 회귀 테스트).
- `get_task_context`: LLM 진입점 미호출 단정 테스트(소스·런타임 양쪽).
- 0023 무회귀: `ask` 경로 기존 테스트 전건 green.

<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-08-12 -->
<!-- 승인 근거: 2026-08-12 대화 — "네, 승인합니다. 구현 및 완수까지 진행해주세요." -->


## 3. Task Queue
- [x] TASK-20260812T075301-schema-ledger — `tool_call_usage` alembic + OAuth 테이블 부트스트랩
- [x] TASK-20260812T075301-authz-seam — 도구 스코프 ContextVar → 명시 인자 승격(내부 무회귀)
- [x] TASK-20260812T075301-oauth-as — 등록·인가·토큰·폐기 + 세션 결합/revoke 전파
- [x] TASK-20260812T075301-tools-p0 — P0 도구 9종 REST + task 세션 계약
- [x] TASK-20260812T075301-isolation — L1~L4 격리 + datamark 각인 3층
- [x] TASK-20260812T075301-injection — 3단 판정 + 저장 시점 datamark
- [x] TASK-20260812T075301-mcp-adapters — stdio(i) + HTTP/SSE(ii) 어댑터
- [x] TASK-20260812T075301-docs — SECURITY 신규 절·ARCHITECTURE·ROUTEMAP·발견 자료·0023 ANCHOR §1
- [x] TASK-20260812T090000-catchup-guard — 부트스트랩 catchup 체인 보호(배포 전 발견)
- [x] TASK-20260812T090000-deploy-1 — PR #1223 머지 + 배포 1차(실패: 이미지 미포함 모듈)
- [ ] TASK-20260812T090000-deploy-2 — 모듈 재배치 후 배포 2차 + POST-DEPLOY 검증

## 4. In Progress
- 없음

## 5. Blocked
- 없음 (PLAN-APPROVED 2026-08-12 로 해소)

## 5.1 잔여 (다음 cycle)
- HTTP/SSE MCP 전송(f-ii) — 현재 stdio 어댑터만. `FastMCP(streamable_http_path=…)` +
  `auth_server_provider` 로 서버측 전송을 붙이는 작업.
- 발견 자료 갱신 — `/api/ai/manifest`·`/api/ai/guide`·큐레이션 OpenAPI 에 OAuth 등록·인가 흐름과
  P0 도구 계약 추가(익명=static contract 불변식 유지).
- 라이브 배포 + e2e(등록→인가→토큰→도구→제출) 및 POST-DEPLOY 검증.
- L4 권한 비대칭 flag — 원장 컬럼은 준비됐으나 판정 로직 미구현.
- 관리 콘솔 '외부 도구 한도' 탭(`WebRoleTokenQuotas` 패턴 복제).

## 6. Done
- 요구사항 확정 (2026-08-12 대화 — 신원/비용 2축, 동시 다중 세션 허용, 검증 이관 범위,
  인젝션 처리, 전송 2종, 대화 기록 보존, context_depth 최대 제공)
- FUNCTION.md §2 REQ + §11 AC 9종 작성
- ANCHOR.md §1~§3 작성 (대안 4개 · 시나리오 1개)
- TASK.md §2.1 구현 계획 작성

## 7. Next Action
- 라이브 배포 후 e2e 검증(등록→인가→토큰→도구 호출→제출) + POST-DEPLOY 기록 → §5.1 잔여 착수

## 8. Completion Checklist
- [x] 모든 REQ의 AC가 구현되었다 (AC-1~11 — 단, AC-1·AC-2 의 **라이브** 확인은 배포 후, §5.1)
- [x] 단위 테스트(unit test)가 통과한다 — 신규 89건 + 기존 스위트 green
- [x] 전체/통합 테스트(integration test): 컨테이너 e2e 미실시 — 사유·커버 계획 TEST.md §4
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다 (CHG-20260812-0001/0002)
- [x] REVIEW.md에 판단 근거가 기록되었다 (REV-20260812-0001/0002)
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] TEST.md에 테스트 결과가 기록되었다
- [x] BLOCKED 항목이 없거나 사람에게 전달되었다 (없음 — 잔여는 §5.1)
- [x] STATUS.md에 기능 상태가 갱신되었다
- [x] LEARNINGS.md에 발견된 교훈이 기록되었다 (worktree stash 공유 함정)
- [x] Git 커밋이 완료되었다
- [x] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
- [x] 요청 범위 자기-열거 완결성 게이트를 통과했다 (§9 + AGENTS.md §16.7)

## 9. Requested Scope (요청 범위 자기-열거)

원 요청: "외부 사용자 AI 에게 API·스킬로 내부 접근을 제공하고, 각 대화의 실행 단계도 서비스 내
LLM 이 아닌 외부 사용자 AI 가 수행" (+ 계획 승인 후 "구현 및 완수").

- [x] `계획 산출물 (ANCHOR/FUNCTION/TASK §2.1)` — 산출물: `docs/{ANCHOR,FUNCTION,TASK}.md` ·
      배선: verify-completion PASS, PLAN-APPROVED 2026-08-12
- [x] `feature-0023 ANCHOR 방향 분기 기록` — 산출물: `unit/feature-0023-.../docs/ANCHOR.md` §1 3문단
- [x] `(a) 신원=로그인 세션 / 비용=머신 AI` — 산출물: `oauth_store.resolve_access_token`
      (SessionId JOIN WebAuthSessions) · 배선: `test_oauth_store.py::test_logout_kills_derived_token`
      등 6건이 세션 죽음→토큰 무효를 단정
- [x] `(c) 부하 원장 신규 축` — 산출물: alembic 0055 `tool_call_usage` + `tool_ledger.py` ·
      배선: `test_tool_ledger.py` 10건(기록 실패=거절, 상한 3종, 조회 불가=거절)
- [x] `(d) 검증을 사용자 LLM 으로` — 산출물: `get_task_context`(우리 LLM 0회 — `cluster_context`
      조회만) + `submit_answer(source_tasks)` 선언·대조 · 배선: 소스 단정 + 대조 6건
- [x] `(e) 인젝션 3단 판정 + §14 재사용` — 산출물: `session_guard.classify_injection` ·
      배선: reject 8건 / **정상 식별자 allow 7건**(오탐 회귀) / neutralize 2건
- [x] `(f) 전송 (i) stdio` — 산출물: `external_tool_mcp_server.py` · 배선: `test_mcp_adapter.py` 7건
- [ ] `(f) 전송 (ii) HTTP/SSE` — **미구현**. 사유·계획: TASK §5.1 (FastMCP streamable_http +
      auth_server_provider). 현재는 stdio 만으로도 사용 가능
- [x] `대화 기록 우리 쪽 보존` — 산출물: `WebAiTasks`(원 질문) + 원장(조회 이력) +
      `submit_answer`(최종 답변) · 한계: 제출은 자발적(소프트 강제, FUNCTION §9 명시)
- [x] `세션 격리 (동시 다중 허용)` — 산출물: L1 tool 이름 라벨 접미 · L2 각인 · L3 대조 · ·
      배선: 각 층 테스트. **L4 flag 는 미구현**(§5.1)
- [ ] `라이브 배포 + e2e` — **미실시**. 사유: 본 worktree 에서 서비스 미기동. 계획: §5.1

**주장 affordance 실측 (G3)**: 본 cycle 은 코드 경로를 만들되 **라이브 e2e 를 구동하지 않았다.**
"외부 AI 가 등록→인가→토큰→도구 호출→제출 을 완주한다" 는 **아직 실측되지 않은 주장**이며,
단위 테스트가 각 구간 계약만 고정한다. 배포 후 5-probe(등록 201 / 인가 302+code / 토큰 200 /
도구 200+각인 / 무토큰 401) 를 TEST.md §3 에 기록해야 이 항목이 닫힌다.

**경계변수 양측 검증 (G4)**:
- `AGENT_EXT_TOOL_RPM`(120) → 경계 이하 통과 / 도달 시 429 (`test_check_limits_blocks_rpm`,
  `test_check_limits_passes_under_threshold`)
- `AGENT_EXT_TOOL_ROWS_PER_HOUR`(200,000) · `_BYTES_PER_HOUR`(64MiB) → 각각 도달 시 429
- 인가 코드 TTL(60s) → 만료 전 소비 성공 / 만료 후 거절 (`test_auth_code_expires`)
- 교차오염 값 길이 임계(8자) → 8자 이상 원문 일치 탐지 / 미만 무시(오탐 방지,
  `test_detect_ignores_short_values_to_avoid_false_positives`)
