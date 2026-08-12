---
doc_type: TASK
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: plan-review (계획 작성 완료 — 사람 승인 대기)
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
- [ ] TASK-20260812T075301-schema-ledger — `tool_call_usage` alembic + OAuth 테이블 부트스트랩
- [ ] TASK-20260812T075301-authz-seam — 도구 스코프 ContextVar → 명시 인자 승격(내부 무회귀)
- [ ] TASK-20260812T075301-oauth-as — 등록·인가·토큰·폐기 + 세션 결합/revoke 전파
- [ ] TASK-20260812T075301-tools-p0 — P0 도구 9종 REST + task 세션 계약
- [ ] TASK-20260812T075301-isolation — L1~L4 격리 + datamark 각인 3층
- [ ] TASK-20260812T075301-injection — 3단 판정 + 저장 시점 datamark
- [ ] TASK-20260812T075301-mcp-adapters — stdio(i) + HTTP/SSE(ii) 어댑터
- [ ] TASK-20260812T075301-docs — SECURITY 신규 절·ARCHITECTURE·ROUTEMAP·발견 자료·0023 ANCHOR §1

## 4. In Progress
- 없음

## 5. Blocked
- TASK-20260812T075301-schema-ledger 이후 전 항목: BLOCKED: awaiting-human-approval —
  위험도 Critical(§7.1). §2.1 계획에 대한 사람 승인(PLAN-APPROVED 마커) 전에는 구현 착수 안 함.

## 6. Done
- 요구사항 확정 (2026-08-12 대화 — 신원/비용 2축, 동시 다중 세션 허용, 검증 이관 범위,
  인젝션 처리, 전송 2종, 대화 기록 보존, context_depth 최대 제공)
- FUNCTION.md §2 REQ + §11 AC 9종 작성
- ANCHOR.md §1~§3 작성 (대안 4개 · 시나리오 1개)
- TASK.md §2.1 구현 계획 작성

## 7. Next Action
- 사람이 §2.1 계획을 검토하고 `PLAN-APPROVED` 마커 부여 → TASK-…-schema-ledger 착수

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (AGENTS.md §8.2 단계 1)
- [ ] 전체/통합 테스트(integration test)가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다 (AGENTS.md §8.2 단계 2)
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
- [ ] 요청 범위 자기-열거 완결성 게이트를 통과했다 (§9 + AGENTS.md §16.7)

## 9. Requested Scope (요청 범위 자기-열거)

본 cycle의 요청 범위는 **계획 산출물까지**다 (구현은 승인 후 별도).

- [x] `신규 feature FUNCTION.md §2 + AC` — 산출물: `docs/FUNCTION.md` (REQ 1건 · AC 9건) ·
      배선 확인: `verify-completion` 문서 게이트로 확인 예정
- [x] `신규 feature ANCHOR.md` — 산출물: `docs/ANCHOR.md` (§1 2문단 · §2 대안 4개 · §3 시나리오 1개 ·
      §4 미기재) · 배선 확인: created_at 실 UTC(2026-08-12T07:53:01Z), §4 human-only 규약 준수
- [x] `TASK.md §2.1 구현 계획 (P0)` — 산출물: 본 문서 §2.1 (파일·symbol 표 13행 · 접근 7단계 ·
      완료 판정 9항 · 위험도 Critical) · 배선 확인: PLAN-APPROVED 미부여 상태로 §5 BLOCKED 명시
- [ ] `feature-0023 ANCHOR 방향 분기 기록` — 산출물: `unit/feature-0023-conversation-api-access/docs/ANCHOR.md` §1 ·
      배선 확인: 본 cycle 내 작성

**주장 affordance 실측 (G3)**: 해당 없음 (문서 산출물만, 실행 가능 기능 주장 없음).

**경계변수 양측 검증 (G4)**: 해당 없음 (본 cycle에 임계·윈도잉 로직 없음 — 상한 knob 5종의
경계 검증은 구현 cycle의 TASK-…-schema-ledger / …-tools-p0 항목에 귀속).
