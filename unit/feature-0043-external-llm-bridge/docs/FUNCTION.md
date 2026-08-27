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

### P0-E. **사용감 패리티** — 전환이 기존 경험을 바꾸지 않는다 (사용자 결정 2026-08-27)

> "기존의 LLM 작동에 관련된 기능들(DB 요청사항 수행, 대화 내역 보존, 그룹 대화 Assistant 호출 등)에
> 대한 사용감은 동일하게 유지되어야 합니다." … "LLM 요청구조가 변경되면서 사용자 경험이 바뀐 부분이
> 기존의 동작 및 경험과 정합하도록 전수적으로 상세하게 수정 및 검증해주세요."

브리지는 `agent_core` 를 타지 않는다. 그래서 **기존 경로가 답변마다 하던 일을 브리지가 "그냥 안 하는"**
구멍이 생긴다. 계산이 아니라 **연결**이 끊긴 형태라, 헬퍼 단위 테스트로는 전부 통과한다.

| 축 | 계약 |
|---|---|
| 그룹 발신자 | 질문 meta 에 `sender_account_id`·`sender_username`·`group_chat` 각인 (기존 키와 동일) |
| 제품 귀속 | 답변 meta 에 `_answer_product_attribution` 각인 (`ProductMode` 를 task 에 굳혀 auto/pinned 구분) |
| 대화 내역 | 표시 store + **회수 store(`core_messages`)** 양쪽 기록. 순서는 표시 확정 → 회수 |
| 첨부 | task 에 `AttachmentIds` 적재 → `claim_request` 가 목록 반환 → `read_task_attachment` 로 본문 |
| 진입점 | `/api/ask` 를 재dispatch 하는 **모든 화면 동작**(전송·재답변·AI로 고치기)이 브리지를 처리 |
| 차단 안내 | 대화용 문구와 **다른** `feature_blocked_message()` — "고장이 아니다" 를 말한다 |
| 제한 배너 | 차단 중 provider health 는 non-restricted 로 표면화(거짓 경보·영구 고착 방지), 사유는 남긴다 |

**의도적으로 복원하지 않은 것** (정직한 잔여):

- `attachment-edit` / `attachment-new` 블록 → 다운로드 첨부 변환. 개인 AI 가 이 관례를 모르고,
  외부 입력으로 첨부 버전을 만드는 것은 별도의 쓰기 경계 설계가 필요하다. 반쯤 만들면 "가끔 되는"
  기능이 되므로 열지 않았다.
- 답변의 실행 단계(`AI 추론` 탭)·결과 CSV. 브리지 답변은 서버 run 이 없어 단계가 존재하지 않는다.
  없는 것을 있는 것처럼 그리지 않는다.

### P0-F. 대기 안내는 **대화에 남아야 한다** (라이브 제보 2026-08-27)

브리지가 `agent_core` 를 우회한다는 것은 "답변을 만들지 않는다" 만이 아니라 **"답변을 저장하지도
않는다"** 는 뜻이다. 그 저장은 누군가 다시 해야 한다.

전환 직후에는 대기 안내를 동기 응답의 `answer` 로만 돌려주고 대화에 저장하지 않았다. 프런트는
**저장된 이력**을 그리므로 화면에는 질문만 남았고, 토스트는 몇 초 뒤 사라졌다 — 사용자에게는
"전송했는데 아무 일도 일어나지 않는" 상태였다(실제 제보).

| 시점 | 대화에 남는 것 |
|---|---|
| 전송 직후 | 질문(발신자 각인) + **대기 안내 assistant 말풍선**(`placeholder: true`) |
| 답변 도착 | 같은 말풍선이 **답변으로 덮어써짐**(`placeholder: false`) — 말풍선 2개가 아니다 |
| 안내를 못 찾음(구 task) | 답변을 새 말풍선으로 append(폴백) |

덮어쓰기 범위는 3겹으로 좁힌다 — 대화 · `role='assistant'` · **이 task 의** placeholder.
넓으면 남의 말풍선을 덮는다.

대기 안내는 **회수 store 에 넣지 않는다**. 시스템 안내이지 대화 내용이 아니다 — 넣으면 이후
LLM 문맥에 "AI 가 대기 안내를 했다" 는 가짜 turn 이 섞인다.

### P0-G. 안내는 **사용자의 언어**로, **상태에 맞게** (사용자 제보 2026-08-27)

> "가이드 메시지를 확인했지만, 일반적인 사용자는 '외부 AI 연결( /ai/connect )' 라는 의미 자체를
> 인지하지 못합니다."

맞는 지적이다. `MCP`·`/ai/connect` 는 **만든 사람의 언어**이고, 경로 문자열은 누를 수도 없다.
그리고 안내가 하나뿐이라 상태와 무관하게 같은 말을 했다.

**상태별 안내** — 하나로는 둘 중 한쪽에게 반드시 틀린 말이 된다:

| 상태 | 첫 줄 | 왜 |
|---|---|---|
| 연결 없음 | "답변할 AI 가 아직 연결되어 있지 않습니다" + `[AI 연결하기](/ai/connect)` | "기다리세요" 는 영원히 오지 않을 것을 기다리라는 말 |
| 연결 있음 | "연결된 AI 가 가져가면 여기에 답변이 표시됩니다" | 설정은 끝났다 — "연결하세요" 는 소음 |

판정은 요청당 **1회**(`_account_has_connected_ai`)이고, 저장 본문·응답 `answer`·토스트가 **같은
판정**을 쓴다. 조회 실패는 "연결됨" 으로 본다(fail-open) — 확신 없이 "연결이 없습니다" 라고
단정하면 이미 연결한 사용자에게 매번 설정하라고 떠드는 쪽이 된다.

**`/ai/connect` 화면도 같은 기준으로** 다시 썼다. 링크를 눌러 도착한 화면이 또 전문 용어투성이면
안내를 고친 의미가 없다:

- 추상적 "MCP 를 지원하는 도구" → **실제 이름**(Claude Desktop, Claude Code). 사용자는 자기 도구가
  MCP 를 지원하는지 스스로 판정할 수 없다.
- "주소만 등록하면" → **어디에** 넣는지(연결/커넥터 추가 설정)
- "1) / 2) 그 외" → "방법 ① **대부분 이 방법으로 됩니다**" / "방법 ② **①이 안 될 때만**"
- "토큰" 은 **버리지 않고 설명한다** — 새 이름을 만들면 정작 도구 설정의 `token` 칸과 매칭이 끊긴다.

문구를 고쳐도 **JS 가 잡는 DOM id 13개는 불변**이다(테스트로 고정 — 문구 수정이 버튼을 죽이지
않게).

### P0-H. 연결은 **한 덩어리 지시문**으로 — 나머지는 AI 가 (사용자 결정 2026-08-27)

> 방법 1, 2를 통합해주세요. AI가 각 방법을 스스로 시도하며 판단하도록 구성해주세요.
>
> 웹페이지에서 사람이 특정 텍스트(토큰을 포함)를 복사하여 AI에게 전달하면 나머지 인증과정이
> 모두 AI가 진행할 수 있도록 구성해주세요.

종전에는 두 경로를 나란히 놓고 사람에게 고르게 했다(① 커넥터 등록 / ② 토큰 수동 입력).
사용자는 **자기 AI 가 어느 쪽에 해당하는지 판정할 수 없다** — "MCP 를 지원하는 도구인가" 는
만든 사람이나 답할 수 있는 질문이다.

**사람의 몫**: `[연결 정보 만들기]` → `[복사]` → AI 에 붙여넣기. **끝.**
**AI 의 몫**: 어느 방법이 되는지 시도해 판단하고 인증까지 완료.

지시문 순서는 "간단해 보이는 순" 이 아니라 **사람을 다시 부르지 않는 순**:

| 순서 | 방법 | 사람 개입 |
|---|---|---|
| A | MCP 설정에 URL + `Authorization: Bearer` 헤더 | 없음 |
| B | HTTP 직접 호출 | 없음 |
| C | 커넥터 주소만 등록(표준 OAuth) | 브라우저 '허용' 1회 → **뒤로** |

커넥터 OAuth 는 가장 간단해 보이지만 사람을 다시 부른다. "복사만 하면 끝" 이라는 약속을
지키려면 토큰이 이미 손에 있는 경로가 먼저여야 한다.

지시문 끝에 **연결 직후 할 일**(`list_open_requests` → `claim_request` → 조사 → `submit_answer`)을
넣어, 붙여넣는 순간 대기 중인 질문이 처리되게 한다.

토큰은 지시문에 함께 실린다 — 세션 결합이라 로그아웃 시 즉시 무효이고, 1회 노출이다.

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

- AC-20260827T090000-external-llm-bridge-13: 브리지 질문 meta 의 발신자 각인 키가 기존 경로와
  동일하다(그룹 대화에서 발신자가 표시된다).
- AC-20260827T090000-external-llm-bridge-14: 브리지 답변에 제품 귀속이 각인된다(제품 변경이 과거
  답변을 소급 변경하지 않는다).
- AC-20260827T090000-external-llm-bridge-15: 질문·답변이 회수 store 에도 기록된다(대화 복제·분기본에
  구멍이 없다).
- AC-20260827T090000-external-llm-bridge-16: 첨부가 task 에 실리고, 점유한 AI 만 `read_task_attachment`
  로 본문을 읽을 수 있다(소유·점유·현재권한 3겹).
- AC-20260827T090000-external-llm-bridge-17: 재답변·AI로 고치기가 브리지 대기를 인지한다(거짓 성공
  토스트 없음, 폴링 걸림).
- AC-20260827T090000-external-llm-bridge-18: 차단된 관리 콘솔 기능이 장애가 아니라 **운영 결정**임을
  말한다. 게이트를 되돌리면 진짜 장애 문구가 복원된다.
- AC-20260827T090000-external-llm-bridge-19: 차단 중 provider 제한 배너가 뜨지 않는다(전송 경로에
  영향이 없으므로 거짓 경보이고, 복구 ping 불가로 영구 고착된다).

- AC-20260827T120000-external-llm-bridge-20: 전송 직후 대화에 **대기 안내 assistant 말풍선**이
  남는다. 새로고침해도 남는다(토스트가 아니라 저장된 메시지).
- AC-20260827T120000-external-llm-bridge-21: 답변이 도착하면 그 말풍선이 답변으로 **바뀐다**
  (안내와 답변이 둘 다 남지 않는다). placeholder 각인이 없는 구 task 는 append 로 받는다.
- AC-20260827T120000-external-llm-bridge-22: 대기 안내가 회수 store(`core_messages`)에 없다.

- AC-20260827T140000-external-llm-bridge-23: 대기 안내가 **연결 여부에 따라 다르다**. 연결이 없으면
  첫 줄이 '설정이 필요하다' 이고 누를 수 있는 링크가 있다.
- AC-20260827T140000-external-llm-bridge-24: 저장 본문·응답·토스트가 같은 판정을 쓴다(요청당 1회 조회).
- AC-20260827T140000-external-llm-bridge-25: 사용자가 보는 텍스트에 설명 없는 `MCP` 가 없다.
- AC-20260827T140000-external-llm-bridge-26: `/ai/connect` 가 실제 도구 이름과 붙여넣을 위치를 말하고,
  '토큰' 을 한 번 설명한 뒤 그 말을 그대로 쓴다.
- AC-20260827T140000-external-llm-bridge-27: 문구 변경이 `ai-connect.js` 가 참조하는 DOM id 를 깨지 않는다.

- AC-20260827T160000-external-llm-bridge-28: `/ai/connect` 는 **단일 흐름**이다. 사람에게 연결
  방법을 고르게 하지 않는다(`방법 ①/②`·`connectAuto`/`connectManual` 부재).
- AC-20260827T160000-external-llm-bridge-29: 지시문의 방법 순서가 A→B→C 이고, C(OAuth)가 사람
  개입을 요구한다는 사실이 명시된다.
- AC-20260827T160000-external-llm-bridge-30: 화면이 "붙여넣은 뒤로는 AI 가 알아서 한다" 를 약속한다.
- AC-20260827T160000-external-llm-bridge-31: 지시문이 연결 직후 수행할 도구 순서를 포함한다.

## 9. Constraints / Risks

- **가용성**: 개인 머신 AI 런타임이 꺼져 있으면 답변이 오지 않는다. 이는 설계상 수용된 한계이며
  (feature-0041 ANCHOR §2 Alt-D 가 지적한 "상시 도달 불가"), UI에서 **대기 상태로 정직하게 표시**한다.
- **즉시성**: 폴링 주기만큼 지연된다. 서버 LLM 즉답과 동등한 체감은 목표가 아니다.
- **blast radius**: insight·node_analysis·cluster_label 등 배경 산출물 생성이 멈춘다. 기존 산출물은 보존된다.
- **되돌리기**: 게이트 knob 1개 + `litellm_config.yaml` 주석 해제로 원복 가능하도록 구성한다.

## Pre-approved Changes

- deploy_scope: included  <!-- 전역 선언(FIRST_REQUEST.md) 준용 · 사용자 결정 2026-08-26 "cycle 종료 후 바로 배포" -->
- reachability_scope: included  <!-- 사용자 진입 경로(웹 대화 → 답변 렌더) end-to-end 도달성까지 완료 조건 -->
