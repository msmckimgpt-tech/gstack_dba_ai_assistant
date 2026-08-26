---
doc_type: FUNCTION
feature_id: feature-0043-external-llm-bridge
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

서비스가 보유한 Claude 계정(`claude-corp` · `root`)으로 LLM을 호출하는 경로를 **전면 차단**하고,
사용자 대면 질의는 **각 사용자의 개인 머신 AI 런타임**(Claude Code 등 MCP 클라이언트)이
**자기 계정 LLM**으로 처리하도록 전환한다. 서버는 도구·컨텍스트·데이터만 제공하고 추론은 하지 않는다.

웹 대화 화면은 유지하되 동작이 바뀐다: 질문은 서버 LLM으로 가지 않고 **대기 작업**으로 적재되며,
그 사용자의 개인 머신 AI가 MCP로 가져가 답변하고, 답변이 같은 대화창에 렌더된다.
이 "역방향" 경로는 MCP `sampling`(서버→클라이언트 push)이 아니라 **도구 기반 pull**로 구현한다 —
sampling 은 프로토콜 `2026-07-28`에서 폐기됐고(SEP-2577, "New implementations SHOULD NOT adopt it"),
Claude Code 가 미지원이기 때문이다(anthropics/claude-code#1785, 2025-06-08 이래 open).

feature-0041(외부 AI 도구 표면)의 인증·도구·원장·각인 인프라를 그대로 재사용하며,
서비스는 **어떤 사용자 LLM 자격증명도 보관하지 않는다**.

## 2. Goal

- REQ-20260826-external-llm-bridge: 서버 보유 계정의 LLM 호출을 fail-closed 게이트로 차단하고,
  웹 대화 질의를 개인 머신 AI 런타임이 자기 계정 LLM으로 처리하는 pull 브리지를 주 접근 경로로 구성한다.
  서비스는 사용자 LLM 자격증명을 보관하지 않고, 대화 기록은 서비스 측에 남는다.

## 3. In Scope

### P0-A. 서버측 LLM 전면 차단
- `shared/llm_gate.py` 신규 — fail-closed 게이트 단일 정본. **코드 기본값이 차단**이며 env 로 해제한다
  (설정 파일 미배포 환경에서도 차단이 유효하도록 기본값을 안전측에 둔다).
- chat 클라이언트 생성 chokepoint 2곳(`modules/llm._get_llm_client`, `agent_core` 의 직접 `OpenAI(...)` 생성)에 게이트.
- `litellm_config.yaml` 의 계정 alias 14종 주석처리(기존 Bedrock 토글 idiom 재사용).
- 차단 대상: 대화 답변 · 대화 보조 10단계 · insight 배치 · node_analysis · cluster_label · redteam · probe.
- **비대상(유지)**: KB 임베딩(로컬 `bge-m3`/ollama — 계정 무관).

### P0-B. pull 작업 브리지
- `WebAiTasks` 확장(멱등 ALTER): `Origin`(web|external) · `ConversationId` · `ClaimedBy` · `ClaimedAt`.
- 신규 MCP 도구 2종: `list_open_requests`(내 계정의 대기 질문 목록) · `claim_request`(점유 + 컨텍스트 반환).
- 라우팅: **본인 질문은 본인 계정 토큰을 가진 세션만** 집을 수 있다(계정 스코프 교차검증).
- `/api/ask` 분기: 게이트가 차단 상태면 LLM 실행 대신 브리지 task 적재 + 대기 상태 반환.
- 웹 프론트: 대기 말풍선 · 답변 폴링 · `/ai/connect` 연결 안내.

### P0-D. 인증 축 통일 — `mat_` 하나로 (사용자 결정 2026-08-27)

**모든 인증 및 사용은 `mat_`(OAuth access token) 를 통해서만** 이루어진다.

| 접두 | 축 | 상태 |
|---|---|---|
| `mat_` | OAuth access token — `/api/ai/tools/*` · `/api/ai/mcp` | **유일 축**. `/ai/connect` self-serve 발급, MCP 는 표준 OAuth 로 발급조차 불요 |
| `matk_` | 대화 API 토큰 — `/api/ask` | **신규 발급 중단**. 기존 토큰 인증은 유지(무회귀) |

`matk_` 축은 서버 계정 LLM 으로 답변을 만들던 경로다. 그 LLM 이 차단된 지금 그 토큰으로는
아무것도 완결되지 않으므로, **발급도 안내도 하지 않는다**. 폐기 *설명* 은 남긴다 — 사라지면
옛 토큰 보유자가 왜 안 되는지 알 수 없다.

도구 표면은 `WebOAuthTokens`(mat_)만 참조하고 `WebApiTokens`(matk_)를 보지 않는다(축 분리 불변식).

### P0-C. 개인 머신 접속 — **무설치 계약** (사용자 결정 2026-08-26)
개인 머신에 **어떤 패키지도 설치하지 않고** 동작해야 한다. 세 경로 모두 이 제약을 지킨다.
- **주 경로 (설치 0)**: `https://<host>/api/ai/mcp` — HTTP/SSE MCP 를 **서버가 호스팅**하므로
  AI 클라이언트에 URL + 토큰을 등록하기만 하면 된다(feature-0041 기구축).
- **REST 정본 (설치 0)**: `/api/ai/*` — `curl` 만으로 전 구간(`list_open_requests` → `claim_request`
  → 도구 → `submit_answer`) 가능.
- **보조 러너**: `src/bridge_runner.py` — 단일 파일, **Python 표준 라이브러리만** 사용
  (`urllib`; `mcp` SDK·`requests` 등 외부 패키지 import 금지). 상주시키면 대기 질문이 자동 처리된다.

## 4. Out of Scope

- MCP `sampling`(`sampling/createMessage`) 채택 — 폐기 기능 + Claude Code 미지원(§1).
- BYOK(사용자 API 키 서버 보관) — ADR-0026 · feature-0041 ANCHOR §2 Alt-B/C 에서 폐기된 결정.
- 팀 공용 큐(타인 질문 대리 답변) — 교차 노출면이 생기므로 별도 동의 절차 후 후속 cycle.
- feature-0023 `ask` API 축의 재설계 — 서버 LLM 차단으로 **동작이 멈추는 것**은 본 cycle 범위이나,
  외부 토큰 계약 자체의 변경은 하지 않는다.
- 기존 대화 기록의 마이그레이션 — 열람은 그대로 유지된다.

## 5. Inputs

- 웹 대화 질문(사용자 계정 세션) · `conversation_id` · 제품/폴더 지침 등 기존 ask 파라미터
- MCP 도구 인자: `task_id` · `limit` · `answer` (기존 0041 계약 준용)
- 게이트 knob: `AGENT_SERVER_LLM_ENABLED`(기본 `0` = 차단)

## 6. Outputs

- `WebAiTasks` 행 — 웹 질문(`Origin='web'` · `ConversationId` 결속) · 점유 이력 · 각인된 답변
- 웹 대화창의 대기 상태 → 답변 렌더
- 차단된 서버 LLM 호출: 호출측에 **정직한 사유 문자열**(무음 실패·폴백 금지)
- `tool_call_usage` 원장 행(기존 0041 계약)

## 7. Main Flow

1. 사용자가 웹 대화창에 질문을 보낸다.
2. `/api/ask` 가 게이트를 확인한다 → 차단 상태면 LLM을 호출하지 않는다.
3. 질문을 `WebAiTasks`(`Origin='web'`, `Status='pending'`, `ConversationId`)로 적재하고 대기 상태를 반환한다.
4. 사용자의 개인 머신 러너가 `list_open_requests` 로 대기 질문을 발견하고 `claim_request` 로 점유한다.
5. 개인 머신의 AI가 **자기 계정 LLM**으로 추론하며 기존 0041 도구로 스키마·데이터를 조사한다.
6. `submit_answer` 로 답변을 제출한다(인젝션 판정 → 각인 → 저장 → 원장 — 기존 계약).
7. 웹 대화창이 폴링으로 답변을 받아 렌더한다.

## 8. Acceptance Criteria

- AC-20260826T135206-external-llm-bridge-1: 게이트 활성(기본) 상태에서 `_get_llm_client()` 가
  `None` 이 아닌 클라이언트를 반환하지 않는다 — 어떤 model alias 로도.
- AC-20260826T135206-external-llm-bridge-2: `litellm_config.yaml` 에 `ANTHROPIC_API_KEY`/
  `ANTHROPIC_API_KEY_ROOT` 를 참조하는 **활성**(비주석) alias 가 0개다.
- AC-20260826T135206-external-llm-bridge-3: 웹 대화창에 질문을 보내면 서버 LLM 호출 0회이고
  `WebAiTasks` 에 `Origin='web'` + `ConversationId` 결속 행이 1건 생성된다.
- AC-20260826T135206-external-llm-bridge-4: A 계정의 웹 질문은 B 계정 토큰의 `list_open_requests`
  응답에 나타나지 않고, B 의 `claim_request` 는 403 이다.
- AC-20260826T135206-external-llm-bridge-5: `claim_request` 는 1회만 성공한다(재점유 409).
- AC-20260826T135206-external-llm-bridge-6: `submit_answer` 후 웹 대화창이 답변을 렌더한다
  (PB-0008 실 Windows 브라우저 검증).
- AC-20260826T135206-external-llm-bridge-7: KB 임베딩(로컬 bge-m3)은 게이트 활성 상태에서도 정상 동작한다.
- AC-20260826T135206-external-llm-bridge-8: 차단된 호출은 무음 실패하지 않고 사유 문자열을 남긴다
  (로그 + 사용자 대면 안내).

- AC-20260827T030000-external-llm-bridge-10: 발견 자료·사용자 가이드의 토큰 힌트가 `mat_` 이고,
  발급 안내가 self-serve(`/ai/connect`)·MCP 자동 연결을 가리킨다. 중단된 CLI 를 따라 하도록
  안내하지 않는다(폐기 설명에서의 언급은 허용).
- AC-20260827T030000-external-llm-bridge-11: `bin/api-token-issue.sh` 가 신규 `matk_` 발급을
  거절한다(exit 3). `--revoke` 는 통과한다 — 폐기 경로까지 막으면 기존 토큰을 거둘 수 없다.
- AC-20260827T030000-external-llm-bridge-12: 도구 표면이 `WebApiTokens` 를 참조하지 않는다(축 분리).

## 9. Constraints / Risks

- **가용성**: 개인 머신 AI 런타임이 꺼져 있으면 답변이 오지 않는다. 이는 설계상 수용된 한계이며
  (feature-0041 ANCHOR §2 Alt-D 가 지적한 "상시 도달 불가"), UI에서 **대기 상태로 정직하게 표시**한다.
- **즉시성**: 폴링 주기만큼 지연된다. 서버 LLM 즉답과 동등한 체감은 목표가 아니다.
- **blast radius**: insight·node_analysis·cluster_label 등 배경 산출물 생성이 멈춘다. 기존 산출물은 보존된다.
- **되돌리기**: 게이트 knob 1개 + `litellm_config.yaml` 주석 해제로 원복 가능하도록 구성한다.

## Pre-approved Changes

- deploy_scope: included  <!-- 전역 선언(FIRST_REQUEST.md) 준용 · 사용자 결정 2026-08-26 "cycle 종료 후 바로 배포" -->
- reachability_scope: included  <!-- 사용자 진입 경로(웹 대화 → 답변 렌더) end-to-end 도달성까지 완료 조건 -->
