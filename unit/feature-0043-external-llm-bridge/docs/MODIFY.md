---
doc_type: MODIFY
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify History

## CHG-20260828T193000-ai-claude-feature-0043-ai-assisted-setup — 환경 판단만 그 머신의 AI 에게 (P0-AD)

- **날짜**: 2026-08-28
- **REQ**: REQ-20260828-ai-assisted-setup
- **위험도**: Major (§12.3 — 설치 경로에 외부 판단이 들어온다. 단 값은 전부 재검증되고
  실행 경로는 그대로라 신뢰 앵커는 이동하지 않는다)
- **승인**: 사용자 결정 2026-08-28 (검토 요청 → 조건부 가능 결론 → "설계 및 구현 진행")

### 배경 — 같은 날 정반대로 전환한 이력 위에서

오전에 P0-AC 가 「AI 지시문 → 결정론 스크립트」로 기본 경로를 바꿨다. 근거는 사용자 제보였다:
"LLM에 요청함에 따라 구축하는 방식이 모두 달라 사용자의 경험이 일정하지 않다".

그런데 그 스크립트도 **판단은 하드코딩**이었다. python 은 `python3 → python`, 핸들러는
`uname` 분기. 오후에 실측된 조합이 그것을 깼다 — **브라우저는 Windows, `claude` 는 WSL 안.**
어느 분기도 맞히지 못하고, 조합은 열려 있어 열거할 수 없다.

그 머신에는 이미 LLM CLI 가 있다(그것이 이 브리지의 전제다). 그래서 **판단만** 맡긴다.

### 변경 내용

**1. 설치 스크립트 — 빈칸으로 받고 다시 검증한다** (`bridge_setup.{sh,ps1}`)

`BRIDGE_PROBED_PY` · `_AI` · `_ARGS` · `_HANDLER` 네 칸. `PROBED_` 접두가 계약이다 —
**신뢰하지 않고 검증한다**. 실존·타입·범위·allowlist 를 통과하지 못하면 버리고 기본 동작으로
간다(막지 않는다 — 판단이 틀렸다고 연결까지 못 하게 하면 그 사용자는 아무 경로도 없다).

사람 칸(`BRIDGE_ARGS`, 무검증·기존 호환)과 **이름으로 가른다**. 러너에는 `--cmd`(임의 명령
실행)·`--base`/`--token`(다른 서버로 돌리기)이 있고, LLM 이 채우는 칸이 되는 순간 그것은
프롬프트 인젝션의 착지점이기 때문이다.

**2. 서버 — 명령을 만들지 않고 빈칸만 채우게 한다** (`compose_probe_setup_instruction`)

`compose_connect_handoff` 는 "연결해줘" 라 경로가 매번 달라진다. 이쪽은 명령을 이미 만들어
놓고 **빈칸이 그 명령 안에 실재**한다. 위임 금지 3항(대조·명령형태·판정)을 지시문이 직접 적고,
`BRIDGE_ARGS` 를 채우지 말라는 선도 긋는다.

**3. 화면 — 세 경로** (모달 · 단독 페이지 양쪽)

결정론 명령(기본) → **AI에게 조사만 맡기기**(신규) → AI에게 전부 맡기기(기존 보조).

### 구현 중 자체 발견한 결함 2건

1. **`drop()` 이 stdout** — `$(probed_args_filtered)` 명령치환 안에서 부른 경고가 치환값에
   먹혀, **차단은 되는데 경고만 사라졌다**. 「조용히 버리지 않는다」를 주석에 적어 두고 그
   반대를 구현한 형태다. → stderr 로.
2. **빈칸이 없는 "빈칸을 채워라"** — 지시문은 빈칸을 요구하는데 명령에는 `BRIDGE_PROBED_*`
   가 없었다. AI 가 변수를 스스로 지어 붙이면 오타 하나로 조용히 무시된다(셸은 모르는 변수를
   그냥 환경에 실어 보내고 스크립트는 읽지 않는다). → probe 전용 명령에 빈칸 삽입.

### 검증

- 회귀 93건 신규 — 기본 61(`test_ai_assisted_setup.py`) + codex 조치 32(`..._codex.py`)
- **뮤턴트 5종 전건 KILL** — allowlist 무력화 8 · drop→stdout 25 · AI 실존검사 제거 1 ·
  빈칸 제거 1 · 위임금지 블록 제거 1
- `make test` 컨테이너 전량 green (exit 0, FAILED 0) · ruff clean
- 정본↔배포본 sha256 일치(sh·ps1 양쪽)

### 적대 리뷰 조치 (REV-20260828T193000, P1 3 · P2 4 전건)

codex 가 **93건 green 상태에서** 아래를 그대로 통과시켜 보였다:
`BRIDGE_PROBED_AI=rm` · `--workers .` · `--workers 1..2` · `--workers 999999999`.

- **P1-1** 실존 검사는 「무엇인지」를 확인하지 않는다 → 알려진 AI CLI allowlist(3곳 동기)
- **P1-2** UI 의 "결과는 ①과 같습니다" 가 거짓 → 「스크립트가 같다」 + 비결정성 고지
- **P1-3** 문서 미갱신 → 본 entry 포함 5개 문서
- **P2-1** 수치 축 타입·범위 → `--workers` 1~64 정수, 시간 1~86400
- **P2-2** `native` 가 `auto` 와 동일 구현 → 공개 목록에서 제거
- **P2-3** python 탐색 순서 3곳 불일치 → 통일
- **P2-4** 테스트가 문자열만 봄 → `set --` 실제 argv 전개 검사

## CHG-20260828T171500-ai-claude-feature-0043-tool-permission-friction — 「도구 사용 승인을 사용자에게 요구하는」 답변 제거

- **날짜**: 2026-08-28
- **REQ**: REQ-20260828-tool-permission-friction
- **위험도**: Major (§12.3 — 인증 경로 변경. 단 표면을 **좁히는** 방향이라 보안 저하 없음)
- **승인**: 사용자 결정 2026-08-28 (수정 범위 2축 선택 — 권한 미개입 · MCP 배제)

### 무엇이 있었나 (라이브 제보)

웹 대화창의 assistant 가 두 턴 연속 이렇게 답했다:

    첨부 파일 접근 권한이 필요합니다.
    웹 인터페이스의 권한 승인 대화에서 `mcp__mysql-ai__read_task_attachment` 도구 사용을
    승인해주신 후 "권한 승인했습니다" 라고 말씀해주세요.

그 사용자에게는 **승인할 방법도, 승인해야 할 이유도 없었다.** 승인 대화가 존재하지 않는다 —
러너는 다른 머신의 헤드리스 CLI 이고 웹 사용자는 그 프로세스에 접근할 수단이 없다.

### 진짜 원인은 권한이 아니라 자격증명 경합이었다

`claude -p` 를 직접 구동해 확인했다. MCP 도구는 **권한 프롬프트 없이 호출됐고**, 돌아온 것은
`HTTP 401 유효하지 않거나 만료된 토큰입니다` 였다. 즉 권한 게이트는 애초에 닫혀 있지 않았다.

러너는 프롬프트에 이 task 에 결속된 토큰을 실어 보낸다. 그런데 같은 머신의 `claude` 에 같은
서비스의 MCP 서버가 상주 설정돼 있으면(`~/.claude.json` 의 **별개** `mat_` 토큰) 모델은 그
도구를 먼저 집는다. 그 토큰이 만료된 순간 조사가 통째로 401 이 되고, 모델은 401 을 「권한이
없다」로 읽어 **승인 요청**을 만든다. 그 문장이 그대로 웹 대화에 렌더됐다.

### 변경 내용

**1. 실행 측 — 경합하는 두 번째 인증 표면을 없앤다**

`_RUNTIME_SPECS["claude"]["argv"]` 에 `--strict-mcp-config` 추가
(`["claude", "-p", "--strict-mcp-config", "{prompt}"]`). `--mcp-config` 를 함께 주지
않으므로 MCP 서버는 **0개**가 된다(실측: 도구 목록 없음).

- 조사 도구 8종은 프롬프트의 HTTP 경로로 전부 제공되므로 **조사 능력은 줄지 않는다**.
  줄어드는 것은 만료된 두 번째 인증 경로뿐이다.
- 이것은 사용자의 **권한 설정을 낮추는 것이 아니라 좁히는 것**이다. 파일 상단 보안 계약의
  「네 런타임의 권한 설정이 마지막 방어선이고 그것을 낮추라고 요구하지 않는다」는 그대로다.
  `--dangerously-skip-permissions` · `--permission-mode bypassPermissions` 는 쓰지 않으며,
  그 사실을 회귀 테스트로 잠갔다.
- codex 에는 대응 플래그가 없다(실측 `codex exec --help`) — 그 런타임에서는 아래 2번이
  유일한 방어선이라는 사실을 주석으로 남겼다.

**2. 프롬프트 측 — 실행 불가능한 지시를 답으로 내지 않는다**

`compose_prompt` 에 3개 계약 추가:

- 「도구 사용 권한이나 승인을 사용자에게 요구하지 마라 — 이 답을 읽는 사람은 네 실행 환경의
  승인 절차에 접근할 수 없고, 승인할 대상도 없다」 (금지 + **이유**)
- 「실패하면 승인을 요청하지 말고 무엇이 어떻게 실패했는지 적은 뒤 확인한 범위까지 답하라」
  (금지만 두면 모델은 침묵하거나 조사를 지어낸다 — **대체 행동**을 준다)
- 「이 토큰이 조사의 유일한 자격증명이다 — 다른 경로의 자격증명을 쓰지 마라. 그쪽은 이
  질문과 무관한 계정일 수 있다」 (만료보다 나쁜 경우: *유효한* 남의 계정 토큰)

**3. 배포 사본 동기화** — `unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py`
(사용자가 내려받아 sha256 을 대조하는 그 파일).

### 검증

- 신규 회귀 11건(`test_tool_permission_friction.py`) — 실행 측 4 · 프롬프트 측 7.
  계약을 **동작으로** 잠근다(`build_cmd`·`compose_prompt` 를 실제로 돌린다).
- **뮤테이션 역검증 5종 전건 KILL** — 플래그 제거 / 플래그를 프롬프트 뒤로 / 승인금지 문구
  제거 / 자격증명 단일화 문구 제거 / 대체행동 지시 제거. 각 뮤턴트는 적용 여부를 앵커
  단언으로 확인한 뒤 실행했고, 매번 원본 sha256 복원을 확인했다.
- 기존 계약 테스트 3건은 base argv 를 표에서 **유도**하도록 갱신 — 호출 형태가 바뀌어도 그
  테스트들이 지키려는 성질(신고 밖 값은 인자가 되지 않는다)은 그대로 잠긴다.
- `make test` 컨테이너 전량 green (exit 0, FAILED 0) · ruff clean · 브리지 스위트 622건.

### 적대 리뷰 조치 (REV-20260828T171500, P1 4 · P2 4 전건)

codex 가 **기본 경로 바깥의 네 구멍**을 지목했다 — 내 조치는 `build_cmd` 기본 경로만 막고
있었다.

- **P1-1** 학습 플래그(`_coerce_flag`)로 배제·권한 축을 되열 수 있었다. `["--mcp-config",
  "{model}"]` 는 기존 방어 3종(토큰 수·치환자·옵션 시작)을 **전부 만족**한다 → 형태가 아니라
  **축**을 보는 `_FORBIDDEN_FLAG_FRAGMENTS` 추가(치환자 포함 토큰도 검사)
- **P1-2** `--cmd` 경로는 배제가 빠진다 → 1회 경고(명령 자동 수정 안 함)
- **P1-3** 배제가 사용자의 **모든** MCP 에 걸린다 → `BRIDGE_KEEP_MCP=1` 탈출구
- **P1-4** 프롬프트 계약은 집행이 아닌데 FUNCTION 이 단정했다(REVIEW 와 불일치) →
  `annotate_approval_request` 로 제출 경로 감지 + FUNCTION 문구 정정
- **P2** 회귀 29건 추가 · 구버전 CLI fail-loud · `REQ`/`AC` 정의로 추적성 복구 · whitespace

브리지 스위트 651건 green (신규 40건). 뮤턴트 8종 전건 KILL.

## CHG-20260826T135206-ai-claude-feature-0043 — 서버 계정 LLM 차단 + pull 브리지 (Step A·B·C)

- **날짜**: 2026-08-26
- **REQ**: REQ-20260826-external-llm-bridge
- **위험도**: Critical (§12.3 — 라이브 답변 생성 경로 전면 정지 + 신규 데이터 경로)
- **승인**: `TASK.md` §2.1 `PLAN-APPROVED by ms.mckim.gpt on 2026-08-26`

### 변경 내용

**Step A — 서버 계정 LLM fail-closed 차단**

| 파일 | 변경 |
|---|---|
| `shared/llm_gate.py` | **신규** — `server_llm_enabled()`(기본 False) · `note_server_llm_blocked()`(caller별 60s throttle) · `server_llm_blocked_message()` · `reset_gate_cache_for_tests()` |
| `unit/feature-0002-agent-core/src/modules/llm.py` | `_get_llm_client()` 선두 게이트 + import. 모든 chat 클라이언트의 단일 출구 |
| `unit/feature-0002-agent-core/src/agent_core.py` | `_run_agent_core()` 의 직접 `OpenAI(...)` 생성부 앞 게이트 + import(`_` 접두 alias) |
| `unit/feature-0007-.../src/config/litellm_config.yaml` | 계정 alias 14종 + `fallbacks` 블록 주석 처리. `titan-embed`(로컬 bge-m3)만 활성. 파일 상단에 전환 사유·되돌리기 절차 |
| `unit/feature-0002-agent-core/tests/_alias_transition.py` | **신규** — 전환 상태 판정 + 대체 계약 단정 헬퍼 |
| `unit/feature-0002-agent-core/tests/test_{llm_edge_free_routing,meta_llm_edge_free,conversation_answer_no_edge_alias}.py` | 10개 테스트에 전환 분기 가드(skip 아님 — 대체 계약 단정). 되돌리면 원 계약 자동 복원 |

**Step B — pull 작업 브리지**

| 파일 | 변경 |
|---|---|
| `unit/feature-0003-.../src/routers/_bootstrap_schema.py` | `WebAiTasks` 에 `Origin`·`ClaimedBy`·`ClaimedAt` 멱등 추가(`ALGORITHM=INPLACE, LOCK=NONE`). `ConversationId` 는 기존 컬럼 재사용 |
| `unit/feature-0003-.../src/routers/ai_tools.py` | 신규 도구 `list_open_requests`·`claim_request`(catch-all 라우트보다 앞에 등록). `submit_answer` 에 `_deliver_web_bridge_answer()` 연결 |
| `unit/feature-0003-.../src/routers/conversations.py` | `_enqueue_web_bridge_task()` 신규 + `/api/ask` 의 dispatch **앞** 분기 |

**Step C — 개인 머신 러너 (무설치)**

| 파일 | 변경 |
|---|---|
| `unit/feature-0043-.../src/bridge_runner.py` | **신규** — 표준 라이브러리 전용 단일 파일. `--claim`/`--submit`/`--watch --exec` |
| `unit/feature-0043-.../tests/test_bridge_runner_stdlib.py` | **신규** — AST 로 stdlib-only 계약 잠금(AC-9) |
| `unit/feature-0043-.../tests/test_llm_gate.py` | **신규** — AC-1·2·7·8 회귀 24건 |

### 왜 이렇게 했는가 (핵심 판단 3개)

1. **코드 기본값을 차단으로**: `.env` 는 gitignore, `config/` 는 미배포. 설정이 정본이면 "설정이 안 실린
   환경에서 잠금이 풀린다" 는 뒤집힌 안전성이 생긴다. 잊으면 잠기는 쪽으로 실패하게 했다.
2. **push(MCP sampling) 대신 pull**: sampling 은 프로토콜 2026-07-28 에서 폐기(SEP-2577)됐고
   Claude Code 가 미지원(anthropics/claude-code#1785). 오늘 동작하지 않고 내일 제거될 기능 위에
   제품 주경로를 얹지 않았다.
3. **기존 alias 계약 테스트를 skip 하지 않음**: skip 은 전환된 환경에서 그 계약을 영원히 검사하지 않게
   만든다(vacuous pass). 조건부 이중 계약으로 바꿔 양쪽 모두 실질 단정이 되게 했다.

### 검증

- `unit/feature-0043-.../tests` — 29건 green (게이트 24 · 러너 5)
- `test_{llm_edge_free_routing,meta_llm_edge_free,conversation_answer_no_edge_alias}` — 31건 green
- 편집한 7개 파일 AST 구문 검증 통과
- `litellm_config.yaml` YAML 파싱 정상 · 활성 `ANTHROPIC_API_KEY` 참조 0 · 활성 model_list = `titan-embed` 1건

### 교차 참조

- `shared/docs/MODIFY.md` — `shared/llm_gate.py` 신규 (§17)
- feature-0041 REPORT.md — 도구 표면이 웹 브리지의 수용부가 됨
- feature-0023 ANCHOR §1 — "두 표면 병존" 방향의 전환(§4 direction-drift 엔트리는 사람이 추가)

## CHG-20260826T151500-ai-claude-feature-0043 — codex 리뷰 P1·P2 전건 조치 + 프론트 폴링

- **날짜**: 2026-08-26
- **근거**: `REVIEW.md` REV-20260826T142000 [CODEX:staged-diff] — P1 5건 · P2 3건
- **위험도**: Critical (동일 cycle 연속 — 사용자 대면 경로)

### 변경 내용

| 파일 | 변경 |
|---|---|
| `unit/feature-0041-.../src/external_tool_mcp_http.py` | `list_open_requests`·`claim_request` `@mcp.tool` 등록 (**P1-1** — 주 접근 경로 복구) |
| `unit/feature-0041-.../src/external_tool_mcp_server.py` | 같은 도구 2종 정의 + `_register` 호출 (stdio 전송 계약 일치) |
| `unit/feature-0003-.../src/routers/conversations.py` | LLM 쿼터 게이트를 `if _server_llm_enabled():` 로 조건부화 (**P1-2**) · `_enqueue_web_bridge_task` 에 user 메시지 저장·`conversation_id`·`_http_status: 500` (**P1-3·P1-4**) · 최종 JSON 에 `bridge_*` 전파 (**P1-3**) |
| `unit/feature-0003-.../src/routers/ai_tools.py` | `claim_request` 에 `conversation_context`(각인) + 원장 실패 시 `_release_claim` (**P1-4·P1-5**) · `_recent_conversation_context()`·`_release_claim()` 신규 · `submit_answer` 에 `ClaimedBy` 조건 + 사유 구분 409 (**P2-1**) · `GET /api/ai/bridge_status` 신설(웹 세션 인증·본문 미포함) |
| `unit/feature-0003-.../src/routers/_bootstrap_schema.py` | `CREATE TABLE` 에 3컬럼 포함 (**P2-2**) · `IX_WebAiTasks_Bridge` 복합 인덱스 신규 설치·마이그레이션 양쪽 (**P2-3**, online DDL) |
| `unit/feature-0003-.../src/static/app/composer.js` | `bridge_pending` 소비 + `_pollBridgeAnswer()`(5초 주기·30분 상한·대화 이탈 시 중단·일시 오류 내성) · `selectConversation` import |
| `unit/feature-0043-.../tests/test_bridge_wiring.py` | **신규** — 배선 회귀 25건 |
| `unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json` · `docs/ROUTEMAP.md` | 신규 라우트 반영 재생성 (250 routes) |

### 왜 배선 테스트인가

리뷰가 잡은 P1 5건 중 **4건이 배선 결함**이었다 — 로직은 맞는데 호출되지 않거나(P1-1 어댑터 미등록),
잘못된 순서에 있거나(P1-2 쿼터 뒤), 결과가 버려졌다(P1-3 필드 유실). 헬퍼를 직접 호출하는 테스트는
그런 결함을 구조적으로 볼 수 없다. 그래서 `test_bridge_wiring.py` 는 AST·소스 층에서
"그 함수가 실제로 그 자리에 배선돼 있는가" 를 단정한다.

### 검증

- feature-0043 스위트 **54건 green** (게이트 24 · 러너 5 · 배선 25)
- 편집한 Python 5파일 AST 통과 · `composer.js` ESM 구문 통과

## CHG-20260827T000500-ai-claude-feature-0043 — codex 2차 리뷰 P1 6건 · P2 3건 조치

- **날짜**: 2026-08-27
- **근거**: `REVIEW.md` REV-20260827T000500 [CODEX:remediation-2]
- **위험도**: Critical (사용자 대면 경로 + 권한 경계)

### 변경 내용

| 파일 | 변경 |
|---|---|
| `.../static/app/composer.js` | 폴링 성공 시 `selectConversation` → **`loadHistory({preserveScroll:true})`** (P1-A: 전자는 활성 대화에서 no-op 이라 답변이 화면에 영영 안 나타났다) · 4xx 즉시 중단 (P2-C) · `delivered=false` 안내 |
| `.../routers/ai_tools.py` | `_conversation_access_denied()` 신규 — claim·submit 양 시점 **권한 재검증**(fail-closed, P1-E) · `_CLAIMABLE_SQL` + `_BRIDGE_CLAIM_LEASE_MIN=30` **lease** (P1-D) · 전달을 원장보다 **먼저** (P1-B) · `save_memory_message` 반환값 확인 + `Delivered` 기록 (P1-C) · `bridge_status` 가 `answered`/`delivered` 분리 · submit 에 `ClaimedClient` 조건 (P2-A) |
| `.../routers/conversations.py` | `_delete_bridge_task()` 신규 · 순서를 **INSERT → 저장** 으로 뒤집고 저장 실패 시 적재 취소 (P2-B) |
| `.../routers/_bootstrap_schema.py` | `ClaimedClient`·`Delivered` 컬럼 (CREATE TABLE + 마이그레이션 양쪽, online DDL) |
| `.../src/bridge_runner.py` | `_compose_prompt()` — 대화 문맥 + 질문 조립 (P1-F) |
| `.../tests/test_bridge_wiring.py` | **+17건** — 상태 전이·장애 경로·권한 축 (codex 가 지적한 배선-only 커버리지 공백) |

### 핵심 판단

- **폴링은 대화 전환이 아니라 재조회다.** `selectConversation()` 의 "이미 활성이면 return" 은
  의도된 동작(읽음처리 중복 방지)이고, 그것을 우회하려 상태를 조작하는 대신 목적에 맞는
  함수(`loadHistory`)를 쓴다.
- **전달 > 원장 순서.** task 가 이미 확정(`submitted`)된 뒤라 원장 실패로 전달을 막으면
  되돌릴 수 없다. 원장은 그 뒤에도 fail-closed 로 집행된다.
- **lease 로 고착 해소.** 명시적 release API 를 늘리는 대신 시간 기반으로 회수한다 —
  러너가 어떤 이유로 사라져도(크래시·절전·강제종료) 30분 뒤 자동으로 대기열에 돌아온다.

### 검증

- feature-0043 스위트 **71건 green** · 편집 파일 전건 구문 통과

## CHG-20260827T010000-ai-claude-feature-0043 — 배포 스모크의 전제를 전환 모드에 맞춤

- **날짜**: 2026-08-27
- **발견 경로**: 라이브 배포(`0b2b4435`) 중 gateway reconcile 이 대화 스모크 FAIL 로 안전 중단
- **위험도**: Major (배포 파이프라인 — 라이브 무장애로 끝났으나 reconcile 이 막혔다)

### 무엇이 일어났나

web·워커·`ext-tool-mcp` 는 신코드로 롤아웃됐고, 마지막 단계인 gateway reconcile 직전
`bin/smoke-conversation.sh` 가 **의도대로 FAIL** 했다:

```
[smoke-conv]   [llm-gate] 서버 계정 LLM 호출 차단 caller=modules.llm._get_llm_client
[smoke-conv]   SMOKE_FAIL client: _get_llm_client 가 None
```

이 스모크는 "배포본에서 **우리 LLM 이** 대화 답변을 만드는가" 를 검사한다(2026-08-26 장애의
회귀 방어). feature-0043 이 그 전제를 바꿨다 — 이제 답변은 사용자의 개인 머신 AI 가 만든다.
`deploy-web.sh` 는 스모크 실패 시 **교체하지 않고 중단**하므로 라이브 장애는 없었다(설계대로).

### 조치

전제가 사라졌다고 검사를 **없애지 않았다** — 계약을 바꿨다.

- 게이트가 차단 상태면: `_get_llm_client()` 가 정말 `None` 인지 단정하고 `SMOKE_OK` 로 통과.
  즉 **"차단이 실제로 걸려 있는가"** 를 검사한다 — "전환했다고 믿는데 계정이 계속 쓰이는"
  상태를 이 게이트가 계속 잡는다.
- 게이트가 열린 상태면: 종전 검사(실제 LLM 왕복) 그대로. 되돌리면 원 방어가 자동 복원된다.

### 교훈

전환이 **자기 배포 파이프라인의 전제**를 깬다는 것을 배포 시점에야 발견했다. 계획 단계의
blast-radius 목록(대화·보조·insight·분석·redteam·probe)에 **배포 게이트**가 빠져 있었다 —
"LLM 을 쓰는 곳" 을 셀 때 검증 스크립트를 세지 않은 것이다.

## CHG-20260827T013000-ai-claude-feature-0043 — 스모크 PASS 문구 모드 분리 + 라이브 실측 문서화

- **날짜**: 2026-08-27
- **위험도**: Minor (로그 문구 + 문서)

| 파일 | 변경 |
|---|---|
| `bin/smoke-conversation.sh` | PASS 문구를 모드별로 분리 — 전환 모드에서 확인한 것은 "차단" 인데 "답변 생성 확인" 으로 출력하고 있었다. 로그를 읽는 사람에게 없는 주장을 심지 않는다 |
| `unit/feature-0003-.../docs/test-runs.d/REV-20260827T000500-bridge-poll-ui.md` | PB-0008 미수행 사유 확정(win-browser 브리지 불가 실측 출력 포함) + 대체 실측 4종 + **여전히 미검증인 것** 명시 |
| `unit/feature-0043-.../docs/test-runs.d/TASK-20260827T000500-*.md` | POST-DEPLOY 실측표 + 배포 중 발견 결함·교훈 |
| `unit/feature-0043-.../docs/{REPORT,TASK}.md` | 상태·잔여를 배포 실측 결과로 갱신 |
| `wiki/{Log,hot}.md` | 전환 기록 · hot cache |

### 라이브 실측 (`0b2b4435`)

전 alias `client=None` · `/api/ai/mcp` 도구 12종(브리지 2종 포함) · `WebAiTasks` 5컬럼+
`IX_WebAiTasks_Bridge` · 신규 라우트 401/405 도달 · 수정한 스모크가 라이브에서 PASS.

## CHG-20260827T030000-ai-claude-feature-0043 — 인증 축을 `mat_` 하나로 통일

- **날짜**: 2026-08-27
- **근거**: 사용자 결정 — "`matk_` 대화 API 토큰을 발급하는 구조는 의도하지 않았습니다.
  모든 인증 및 사용은 `mat_` 토큰을 통해 이루어지도록 구성해주세요."
- **위험도**: Major (외부 통합 계약 — 안내면 변경 + 신규 발급 차단)

### 무엇이 문제였나

두 토큰 축이 공존했다.

| 접두 | 축 | 발급 | 이번 조치 |
|---|---|---|---|
| `mat_` | OAuth access token (`/api/ai/tools/*`·`/api/ai/mcp`) | `/ai/connect` self-serve · MCP 는 표준 OAuth 자동 | **유일 축** |
| `matk_` | 대화 API 토큰 (`/api/ask`) | `bin/api-token-issue.sh` 운영자 CLI | **신규 발급 중단** |

`/ai/connect` 는 이미 `mat_` 를 발급하고 있었다(`issue_console_token`). 문제는 **안내면**이었다 —
발견 자료·사용자 가이드·CLI 가 여전히 `matk_` 를 가리켰고, 그 축은 서버 계정 LLM 으로 답변을
만들던 경로다. 그 LLM 이 차단된 지금 `matk_` 를 새로 발급해도 **아무것도 완결되지 않는다**.
죽은 경로의 자격증명을 안내하는 것은 사용자를 막다른 길로 보내는 것이다.

### 변경 내용

| 파일 | 변경 |
|---|---|
| `routers/ai_discovery.py` | `token_format_hint` → `mat_…` · `how_to_obtain` 을 self-serve(`/ai/connect`) + MCP 자동 연결로 · `deprecated_scheme` 키 신설(왜 안 되는지) · OpenAI 스펙 description 에 "`/api/ask` 는 더 이상 답변을 생성하지 않는다" 명시 |
| `static/ai-api-guide.md` | 토큰 절을 `mat_` self-serve 기준으로 재작성 + 구 축 폐기 경고 · MCP 런처 예시에 DEPRECATED 배너 |
| `bin/api-token-issue.sh` | **신규 발급 차단**(exit 3) + `mat_` 축 안내. `--revoke` 는 통과(기존 토큰 폐기 경로 유지), `ALLOW_DEPRECATED_MATK=1` 강행 escape |
| `bin/conversation-mcp.sh` | DEPRECATED 배너 + 예시 토큰을 `mat_` 로 |
| `web_context.py` | charset 주석이 `matk_` 를 유일 예로 들던 것 → 두 접두 모두 서술 |
| `tests/test_token_axis_unified.py` | **신규 14건** — 발급 축·안내면·차단·축 분리 불변식 |

### 유지한 것 (무회귀)

**기존 `matk_` 토큰의 인증은 막지 않는다.** 막은 것은 신규 발급과 안내뿐이다. 이미 발급된
토큰으로 도는 통합이 있다면 갑자기 401 을 만나지 않는다 — 다만 `/api/ask` 는 답변 대신
브리지 대기 안내를 받는다(게이트가 이미 그렇게 동작한다).

### 축 분리 불변식

도구 표면(`ai_tools.py`)은 `WebOAuthTokens`(mat_)만 본다 — `WebApiTokens`(matk_)를 참조하지
않는다. 테스트로 고정했다. 두 축이 섞이면 "인증은 통일했다" 는 주장이 코드에서 거짓이 된다.

## CHG-20260827T090000 — 사용감 패리티 전수 정합 (TASK-20260827T090000)

**요청**: 전환으로 바뀐 사용자 경험을 기존 동작과 정합하도록 전수 수정·검증.

**진단**: 브리지는 `agent_core` 를 우회하므로, 기존 경로가 답변마다 하던 부수 작업이 통째로
빠졌다. 전부 **배선 결함**이라 헬퍼 테스트는 전건 통과했다.

| 대상 | 변경 |
|---|---|
| `_bootstrap_schema.py` | `WebAiTasks` + `ProductMode`·`SenderUsername`·`AttachmentIds` (온라인 DDL) |
| `conversations.py` | 발신자 각인 meta · core store 기록 · 제품모드/발신자/첨부 전달 |
| `ai_tools.py` | 답변 제품 각인 · core store 기록 · `attachments` 목록 · `read_task_attachment` 신설 |
| `composer.js` · `app.js` | `handleBridgePending` 단일 헬퍼 + 재답변·AI로 고치기 배선(거짓 성공 토스트 제거) |
| `llm_gate.py` | `feature_blocked_message()` — 대화 아닌 기능용 안내(장애 아님을 명시) |
| `_prompt_context.py` · `admin_metadata.py` | 차단과 초기화 실패를 구분해 안내 |
| `node_analysis.py` | 큐 적재 **전에** 거절(재시도 상한 소진 방지) |
| `insight.py` | cycle 시작 전 skip(빈 한 바퀴 + healthcheck 흔들림 방지) |
| `llm_provider_health.py` | `_gate_override` — 차단 중 거짓 제한 배너·영구 고착 차단, 원본 읽기 경로 보존 |
| `external_tool_mcp_{http,server}.py` | 첨부 읽기 도구 양쪽 어댑터 등록 |

**검증**: feature-0043 스위트 112건 green(기존 85 + 패리티 27) · 컨테이너 `make test` 전체 통과.

### CHG-20260827T090000 조치 (codex P1×1 · P2×6)

| 대상 | 조치 |
|---|---|
| `insight.py` | cycle 전체 게이트 **철회**(heartbeat·비-LLM 정비 복원) → LLM 잡 처리만 게이트 |
| `ai_tools.py` | 첨부 읽기 경계를 `submit_answer` 와 통일(client·lease·상태) · 원장 상한 선검사 · ContextVar 3종 역순 복원 |
| `system.py` · `app.py` · `ai_ops.py` | 관제 전용 `_read_llm_provider_status_admin()` seam — 관제는 원본, 대화 UI 는 마스킹 |
| `composer.js` · `app.js` | 대기 task registry + 재진입 폴링 복구 + 중복 폴링 가드 |
| 테스트 | 회귀 8건 추가 · insight 계약 재작성(heartbeat 유지) · `test_ai_ops` 픽스처를 새 seam 으로 |

## CHG-20260827T120000 — 대기 안내가 대화에 남지 않던 결함 (TASK-20260827T120000)

**라이브 제보(2026-08-27 09:58)**: "대화를 전송했지만, 답변 진행 or 가이드라인이 제공되지
않았습니다." 화면에는 사용자 질문 하나만 있었다.

**진단(DB 실측)** — 백엔드는 정상이었다:

| 확인 | 결과 |
|---|---|
| 브리지 task | `t_V7MgnRcT4aMYbb8n` · `status=open` ✅ |
| 질문 저장(표시) + 발신자 각인 | `{"sender_username":"admin","sender_account_id":10}` ✅ |
| 질문 저장(회수) | `core_messages` id 9009 ✅ |
| **대기 안내 말풍선** | **없음** ❌ |

**근본 원인**: 대기 안내를 응답 payload 로만 돌려주고 **대화에 저장하지 않았다.** 기존 경로에서는
`agent_core` 가 답변을 저장하는데 브리지는 그 경로를 타지 않는다. 프런트는 저장된 이력을 그리므로
질문만 남았고, 토스트는 몇 초 뒤 사라져 근거가 되지 못했다.

**놓친 이유**: "브리지가 `agent_core` 를 우회한다 = 기존 경로가 하던 일이 빠진다" 는 원칙을 각인·
첨부·발신자에는 적용했으면서, **답변 저장 자체**에는 적용하지 못했다. 각인의 *내용* 을 보느라
말풍선이 *존재하는지* 를 보지 않았다.

**조치**:
- 대기 안내를 `assistant` 말풍선으로 저장 + `placeholder: true` 각인 (`_BRIDGE_WAIT_NOTICE` 단일 상수)
- 답변 도착 시 **그 자리에 덮어쓴다**(`_replace_bridge_placeholder`) — 말풍선 2개가 아니라 하나가
  대기→답변으로 전환(기존 UX 와 동형). 못 찾으면 append 폴백(구 task 호환)
- 안내는 **회수 store 에 넣지 않는다** — 시스템 안내이지 대화 내용이 아니다(LLM 문맥 오염 방지)
- 회귀 5건

## CHG-20260827T140000 — 안내를 사용자의 언어로 (TASK-20260827T140000)

**사용자 제보**: "가이드 메시지를 확인했지만, 일반적인 사용자는 '외부 AI 연결( /ai/connect )' 라는
의미 자체를 인지하지 못합니다."

| 대상 | 변경 |
|---|---|
| `conversations.py` | 안내 2종(연결 없음/있음) + `_account_has_connected_ai`(fail-open) + 요청당 1회 판정 + `bridge_toast` 서버 지정 |
| `composer.js` | 토스트를 서버 문구 우선으로 — 연결 없는 사용자에게 "내 AI 가 처리" 는 사실이 아니다 |
| `ai-connect.html` · `.js` · `.css` | 제목·도입부·단계 재작성, 실제 도구 이름, 붙여넣을 위치, 토큰 1회 설명. DOM id 13개 불변 |
| 테스트 | 회귀 11건(상태 2종·용어·fail-open·단일 판정·연결 화면·DOM 계약) |

**설계 판단 2가지**
- 연결 여부 조회 실패는 **'연결됨'** 으로 본다 — 틀렸을 때 덜 성가신 방향.
- 용어는 **'토큰' 유지**. '열쇠' 같은 새 이름은 AI 도구 설정의 `token` 칸과 매칭을 끊는다.

## CHG-20260827T160000 — 연결 화면 단일 흐름 (TASK-20260827T160000)

**사용자 결정**: 방법 ①/② 통합 · AI 가 스스로 시도하며 판단 · 사람은 텍스트(토큰 포함) 복사·전달까지만.

| 대상 | 변경 |
|---|---|
| `ai-connect.html` | 두 절 → 단일 `connectFlow` + 3단계 안내(`aic-howto`) + 지시문 블록 |
| `ai-connect.js` | `handoff(token)` 신설 — AI 용 지시문 생성(A/B/C + 연결 직후 할 일). `issueToken`→`makeHandoff` |
| `ai-connect.css` | `.aic-howto` · `.aic-code--block`(스크롤·pre-wrap) |
| 테스트 | feature-0041 계약 재작성('무설정 우선'→'사람 재호출 없는 경로 우선') · 패리티 단일흐름/약속/DOM id 갱신 |

**설계 판단**: 커넥터 OAuth 를 **뒤로** 뺐다. 가장 간단해 보이지만 브라우저 '허용' 클릭으로
사람을 다시 부른다 — "복사만 하면 끝" 약속과 어긋난다.

## CHG-20260827T180000 — 라이브 e2e 제보 3건 + 안내 문구 정리 (TASK-20260827T180000)

### 이슈 ① (치명) — 웹 브리지 축 전체가 끊겨 있었다

다른 세션의 실 연결 테스트에서 `list_open_requests` 가 **항상 500**:

```
TypeError: record() got an unexpected keyword argument 'rows'
```

올바른 이름은 `rows_returned`. 조회는 끝난 뒤 **원장 기록 단계**에서 터져 대기 질문 유무와
무관하게 100% 실패했다. `claim_request` 는 이 도구가 주는 `task_id` 를 요구하므로 **웹에서 들어온
질문을 외부 AI 가 집어갈 경로가 통째로 죽어 있었다.** `open_task` 축은 정상이라 증상이 부분적으로만
보였다.

AST 로 `_ledger.record` 호출 8곳을 전수 대조 → **정확히 1건**. 수정 후 같은 형태의 재발을 막는
시그니처 대조 테스트를 넣었다(문자열이 아니라 `inspect.signature` 와 AST 호출부를 맞춘다).

**왜 못 잡았나**: 테스트가 "도구 등록·SQL 술어·권한 경계" 는 봤으나 **핸들러를 끝까지 실행해
보지 않았다.** 등록과 동작은 다른 사실이다.

### 이슈 ② — 매니페스트가 안내하는 곳에 토큰으로 갈 수 없었다

`/api/ai/capabilities` 가 쿠키 세션 전용이라 `mat_` 토큰만 가진 외부 AI 는 401. 그런데 매니페스트는
이 URL 을 `quality_controls.discover` 로 안내한다. 도구 표면과 **같은 해석기**(`require_ai_token`)를
재사용해 수용하도록 고쳤다 — 따로 구현하면 만료·폐기·scope 판정이 두 벌이 되고, 갈리는 순간
느슨한 쪽이 실질 경계가 된다.

### 이슈 ③ — 가이드가 브리지 축을 몰랐다

부록 B 가 "10종" 으로 브리지 3종을 누락. 가이드만 읽은 외부 AI 는 그 축의 **존재 자체를 모른다.**
13종으로 갱신 + 사용 순서(list → claim → read_attachment → submit) 추가. 도구 수가 실제 노출
집합과 어긋나지 않게 대조 테스트도 넣었다.

### 안내 문구 정리 (사용자 요청: 'AI Slop' 제거)

걷어낸 것: 서비스 구조 설명(사용자가 알 필요 없음), 반복 안심 문구, 이모지, 산발적 볼드,
검증 불가 약속("1~2분이면 끝납니다"). 대화창 안내는 **4문단 → 2문장**.

⚠ 줄이다 **보안 경고("남에게 주지 마세요")를 빠뜨렸고, 기존 계약 테스트가 잡아냈다.** 복원했다.

## CHG-20260827T200000 — 즉시 인지(폴링 금지) · 상주 러너 · 인증 모달 (TASK-20260827T200000)

| 대상 | 변경 |
|---|---|
| `ai_tools.py` | **`wait_for_request`** 신설 — 서버 보류형 대기(상한 55초 서버 고정), 루프마다 commit, 끊김 감지 |
| MCP 어댑터 2종 | 등록(총 **14종**) |
| `bridge_agent.py` | 상주 러너 신설 — stdlib 전용, sleep 없음, claude·codex·gemini·ollama 자동 감지 + `--cmd` |
| `static/agent/` | 러너 배포본(AI 가 직접 내려받음). 정본과 해시 일치를 테스트로 강제 |
| `oauth_as.py` | 지시문에 대기 지시·러너 설치 명령·사설 CA(`/trust/rootCA.crt`)·`claude mcp add`·재시작 주의 |
| `index.html`·`connect-modal.js`·CSS | 인증 모달 — 문서 위임 가로채기, 새 탭 의도 존중, 닫으면 토큰 제거 |
| 가이드 | 14종 + "폴링 말고 `wait_for_request`" |
| 테스트 | 대기 계약 5 · 러너 6 · 모달 6 · 지시문 2 |

## CHG-20260827T220000 — 모델·추론 정합 + 실행 단계 복원 (TASK-20260827T220000)

**사용자 제보 2건** (다른 세션 테스트 중):
① 웹↔AI 요청에서 사용 모델·추론 수준이 부정합 ② 각 추론 step 이 노출되지 않음

### ① 모델·추론 강도

dispatch 는 `model`·`reasoning_level` 을 `run_kwargs` 로 넘기는데 **브리지는 둘 다 버렸다.**
화면의 선택지가 아무 효과 없는 거짓 조작면이었다.

- 스키마 `RequestedModel`·`ReasoningLevel`(온라인 DDL) — 요청 시점 의도를 굳힌다
- `claim_request` 가 `requested` 로 전달 + "못 맞추면 밝혀라" 지시
- 러너가 `_MODEL_FLAG` 로 **실제 CLI 인자화**, 실패 시 기본 모델 폴백 + 사실 고지
- 추론 강도는 값이 아니라 **의도**로 전달(런타임마다 이름이 다르다)

### ② 실행 단계

`_materialize_bridge_steps` — 제출 시 `tool_call_usage` 의 도구 호출을 `agent_runtime.steps` 로
옮기고 답변 meta 에 `run_id`(=task_id) 각인(프런트 조회 키).

관측 사실만 옮긴다. LLM 사고 과정은 비워 둔다 — 지어내면 패널 전체가 못 믿을 것이 된다.
브리지 진행 도구(wait·claim·submit)는 걸러낸다. 기록 실패는 전달을 막지 않는다.

## CHG-20260828T000000 — 진행 가시성 · 5단계 프롬프트 · 제품 인지 (TASK-20260828T000000)

**사용자 제보 4건**(다른 세션 테스트 중): ① 진행 상황 불가시 ② 5단계 시스템 프롬프트 미적용
③ 첨부 배선 검토 ④ 제품 데이터소스 인지·표시

| 항목 | 실태 | 조치 |
|---|---|---|
| ① | 안내가 "가져가면 표시됩니다" 에서 멈춤 | 점유 시 **말풍선 본문 교체** + 서버가 정한 `phase` 4종 + 연결 없음 고지 |
| ② | **`compose_system_prompt` 미호출** — 운영자 지침 전량 소실 | `RoleId` 적재 → 서버가 **같은 함수**로 조립 → claim 전달 → 러너가 **맨 앞** 배치 |
| ③ | 배선 정상 | 적재→목록→읽기→고지 연결을 테스트로 고정 |
| ④ | 집행(scoped_execution)은 정상, **인지**가 없음 | 제품명·키·데이터소스 전달 + 프롬프트 명시 |

## CHG-20260828T020000 — 로그아웃 연결 폐기 · 미연결 시 미적재 (TASK-20260828T020000)

**제보**: 재로그인해도 AI 연결이 끊기지 않음. 화면이 "연결된 AI 가 가져가면…" 이라 안내.

| 원인 | 조치 |
|---|---|
| `revoke_for_session` 이 **정의만 되고 호출 없음**(테스트만 호출) | `auth_logout` 이 호출 + commit |
| 연결 표시 술어 ≠ 인증 술어(세션 미검사) | `account_has_live_token` 으로 단일화, 소비처 2곳 교체 |

**대기열 정책 변경**(사용자 결정): 연결 없으면 적재하지 않는다. 질문·안내는 대화에 남고,
연결 후 재요청 시 이전 문맥으로 함께 간다. 안내도 "저장해 두었습니다"→"다시 질문해 주세요".

**테스트 작성 교훈**: 분기가 하나 늘자 `src.index("A") < src.index("B")` 식 순서 계약 4건이
연쇄 오탐. `index()` 는 첫 등장을 찾으므로 새 분기가 앞에 끼면 다른 곳을 잰다. 순서 계약은
**해당 구간으로 범위를 좁혀** 재고, 구조 계약은 **AST 로 호출 인자를 직접** 본다.
## CHG-20260828T040000 — 연결 상태 상시 표시 (TASK-20260828T040000)

**제보**: 웹 화면에 연결 여부 메시지가 없어 1차 연결 완수를 확인할 수 없다.

| 대상 | 변경 |
|---|---|
| `oauth_as.connect_status` | `connected` 추가 — 판정은 `account_has_live_token`(인증과 동일) |
| `index.html` | 컴포저 하단 `#aiConnState` |
| `connect-modal.js` | `refreshConnState`·`bindConnState` — 로드·발급 직후·탭 복귀 3시점, 폴링 없음 |
| CSS | 연결됨(초록 ●) / 안 됨(주황 ○) |

**함께 실측한 것** (별건 확인): `wait_for_request` 는 엣지·공인 IP 양쪽에서 **55초 보류** 정상,
새 질문 도착 시 **2.27초 반환**. 다른 세션이 본 `elapsed=12s` 는 **배포 롤링 재시작**이 붙들린
연결을 끊은 것 — 긴 대기 요청이 정확히 그 대상이다.
## CHG-20260828T060000-bridge-model-selector — 모델·추론 조작면 제거 (TASK-20260828T060000-bridge-model-selector)

**제보**: "웹브라우저 간 AI가 연결된 상태에서 요청을 보낼 때 LLM 모델과 추론수준이 정합하지 않는다."
이어서 "웹브라우저 내부에서 제어하는 방법이 제한된다면, 아예 브라우저 내에서는 제거(숨김)
처리를 진행해도 문제없다."

**직전 cycle(P0-M)이 만든 것이 정확히 그 불일치였다.** 전달 계약은 배선대로 동작했지만, 전달된
값이 서비스 내부 alias(`claude-haiku-4`)라 어떤 CLI 도 알지 못했다 — 기본값이 haiku 이므로
사실상 **모든** 브리지 요청이 모델 지정 실패 → 기본 모델 폴백이었고, 요청은 반영되지 않으면서
"못 맞췄다" 는 고지만 매번 붙었다.

| 층 | 종전 | 조치 |
|---|---|---|
| 카탈로그 | 항상 서버 카탈로그(서버가 부를 수 없는 모델들) | 차단 시 빈 목록 + `model_selector: "hidden"` · 해제 시 `"visible"` 로 복원 |
| 화면 | 모델·추론 항목 상시 노출 | 두 항목 숨김 + 메뉴 열기 가드 |
| 전송 | `model`·`reasoning_level` 항상 동봉 | 숨김 상태면 미동봉(대화 KV 오염 차단) |
| 적재·전달 | task 에 굳히고 `claim_request` 로 전달 | 쓰지도 읽지도 않음(컬럼은 이력 보존) |
| 러너 | `_MODEL_FLAG` 로 CLI 인자 조립 + 폴백 고지 | 경로 제거. 고정은 `--cmd 'claude --model opus -p {prompt}'` |

**왜 "연결된 AI 에 맞춰 목록을 재구성" 이 아닌가**: 서버는 연결된 런타임의 종류를 알 수 없다 —
MCP 어댑터가 별도 컨테이너라 `clientInfo` 가 웹까지 오지 않는다. 신고 도구를 새로 만드는 안은
사용자 결정으로 기각(제어할 수 없으면 보여주지 않는다).

**되돌리기**: 게이트 1개(`AGENT_SERVER_LLM_ENABLED=1`). 제거가 아니라 조건부 숨김이며 양방향을
테스트가 잠근다.

## CHG-20260828T050000 — 대화 제목 · 실행 단계 사유 (TASK-20260828T050000)

**제보**(스크린샷 동반): ① 대화 제목이 "새 대화" 인 채 맥락에 따라 바뀌지 않는다.
② 실행 단계에 "어떠한 이유로, 어떤 작업이 수행되었다" 구조가 없다.

둘 다 P0-E 가 예고한 형태 — **계산이 아니라 연결**. 헬퍼는 멀쩡하고 단위 테스트도 통과한다.

| 축 | 원인 | 조치 |
|---|---|---|
| 제목 | `agent_core._try_update_topic` 을 브리지가 타지 않음. 두 번째 축(LLM 재생성)은 게이트로 잠겨 원형 복원 불가 | 2단 — 적재 시 서버가 질문 앞머리로 **즉시**, 제출 시 개인 AI 의 `title` 로 **승급** |
| 단계 | 단계를 **원장**에서 만들었는데 원장에 인자가 없다 → `SQL을 실행한다` 로 뭉뚱그려지고 사유 칸은 공백 | 기록 시점을 **도구 호출 그 순간**으로 이동(인자·사유를 동시에 가진 유일한 지점) |

**사유 확보**(사용자 결정 — AI 제공 + 서버 보완): MCP 어댑터 2종 × 조사 도구 9종에 선택 인자
`reason` 을 열고 **도구 설명으로 요구**한다(자리만 열면 선택 인자는 비어 온다). 미제공 시
**내부 경로와 같은 헬퍼**(`_derive_step_work`/`_derive_step_reason`)로 파생하고, 출처를
`external-ai` / `derived` 로 갈라 각인한다 — 파생 문구를 AI 의 사고인 양 표시하지 않는다.

**기존 동작과의 의도적 차이**: 서버 LLM 경로는 매 턴 제목을 무조건 덮어썼다(사용자 rename 도).
`supersedes` 판정으로 끊었다 — placeholder 이거나 *우리가 붙인* 질문 기반 제목일 때만 갱신한다.

**계약 테스트 갱신 2건**(skip 아님): `test_steps_do_not_fabricate_reasoning` 은 "사유를 비운다"
에서 "**출처를 구분한다**" 로, `test_submit_answer_requires_source_tasks` 는 인자 개수 고정에서
"source_tasks 를 생략할 수 없다" 로 — 둘 다 계약의 정신을 유지한 채 새 사실을 담게 했다.

## CHG-20260828T070000 — 상주 러너 기본화 · 대기 여부 관측 (TASK-20260828T070000)

**실측된 한계**: AI 가 대기 루프를 10분 돌다 질문을 **받은 직후** 멈췄다(claim 없음 → task 방치).
대기 1회 = 도구 호출 1회라 턴 예산을 태운다.

| 대상 | 변경 |
|---|---|
| `oauth_as.compose_connect_handoff` | 러너를 **필수 1단계**로 · 이유(턴 예산) · `--resume` 복귀 |
| `ai_tools.account_is_listening` | 원장 `wait_for_request` 최근성(150s)으로 **대기 여부 관측** |
| `bridge_status` · `connect_status` | `listening` + `not_listening` 국면 |
| `connect-modal.js` · CSS | 표시 3상태(대기 중 / 대기 안 함 / 연결 안 됨) |
| `bridge_agent.py` | 설정 저장(토큰 제외·0600) · `--resume` · 401 시 복귀 명령 출력 |

**설계 판단**: 판정 실패 방향을 반대로. 연결→fail-open(과잉 경고 방지),
대기→fail-closed(헛된 기다림 방지).
## CHG-20260828T070000 — 인터럽트 · 맥락 전환 · 진행 스트리밍 · 병렬 (TASK-20260828T070000)

**사용자 요청**: "웹브라우저 간 AI가 연결된 상태에서 요청을 스트리밍으로 구성할 수 있는지 +
일반 LLM 챗봇처럼 인터럽트·답변 중 재요청에 따른 맥락 전환·병렬 대화가 가능한지" 검토 후 구현.

검토 결과 셋 다 **기존(서버 LLM) 경로에는 이미 있었고 브리지에만 없었다.** 빠진 방식이
P0-E 와 같다 — 계산이 아니라 **연결**이 끊긴 형태라 헬퍼 테스트로는 전부 통과했다.

| 축 | 브리지의 실태 | 왜 |
|---|---|---|
| 인터럽트 | **UI 도달 불가** | `/api/ask` 가 즉시 반환 → `myAskInFlight` 가 곧바로 빔 → 중단 버튼이 안 뜸. `/api/cancel` 도 `WebAiTasks` 를 안 봄 |
| 맥락 전환 | 오히려 **역효과** | 새 질문이 task 를 *추가*하고 `CreatedAt ASC` 라 옛 질문이 먼저 처리됨. 게다가 claim 시점의 최신 문맥으로 답해 흐름과 어긋남 |
| 병렬 | 서버는 이미 병렬 | 직렬인 것은 **러너뿐**(`limit=1` + 순차 `handle_one` + 블로킹 `subprocess.run`) |
| 스트리밍 | 5초 폴링 + 답변 후에야 단계 | `_materialize_bridge_steps` 가 제출 시점에만 이관 |

**사용자 결정 4건**(AskUserQuestion): 범위=묶음A+병렬러너 · 전송=SSE 55초 상한 재접속 ·
재요청=미점유 취소+점유 협조적 취소 · 늦은 답변=409 거절.

### 조치

| 영역 | 변경 |
|---|---|
| 술어 단일화 | `shared/bridge_tasks.py` 신규 — lease·점유가능 SQL·상태값·`cancel_bridge_tasks` 정본. `ai_tools.py` 는 지역 별칭으로 **참조만** |
| 취소 | `_cancel_bridge_tasks_for` + `_mark_bridge_placeholders_canceled`. `/api/cancel` 이 **서버 run 취소보다 먼저** 호출(뒤에 두면 KV 실패가 이쪽을 삼킴) |
| 맥락 전환 | `_enqueue_web_bridge_task` 가 **적재 성공 뒤** 이전 대기를 supersede(`exclude_task_id`). 실패해도 최악이 종전 동작 |
| 협조적 취소 | `wait_for_request` 가 취소에도 **즉시 반환** + `canceled_task_ids`. **신규 도구 0** — P0-I 계약 4곳이 흔들리지 않는다 |
| 집행 | `submit_answer` 가 취소된 task 를 409(각인·저장 **전에** 판정) |
| 스트리밍 | `GET /api/ai/bridge_stream` — `_sse_pack`·`_counted_stream`·`X-Accel-Buffering:no` 재사용. **55초 상한**은 배포 pre-drain(90초)과의 상호작용 때문 |
| 진행 단계 | `_bridge_live_steps` — `tool_call_usage` 를 답변 **전에** 노출. 필터는 `_BRIDGE_PROGRESS_TOOLS` 로 제출 경로와 공유 |
| 프론트 | `_streamBridgeStatus`(SSE+재접속) → 실패 시 **폴링 폴백 유지**. `_bridgePendingHere()` 로 중단 버튼 노출 |
| 러너 | 워커 N개(기본 2) + 취소 시 **자식 프로세스 kill**(`Popen` + `Thread.join(timeout)`, sleep 0) |

### 설계상 넘지 않은 선 (정직한 잔여)

- **답변 토큰 스트리밍은 하지 않았다.** 등록형 MCP 클라이언트는 답을 다 쓴 뒤 도구를 부르므로
  현실적 상한이 문단 단위이고, 러너에서만 토큰 단위가 되어 **환경 차이**(P0-J)를 만든다.
  증분 제출은 인젝션 각인 계약(전문 단위)의 재설계도 선행해야 한다.
- **점유된 작업의 실행 중단은 협조적이다.** 남의 머신 프로세스에 kill 권한이 없다.
  안내 문구가 이 한계를 그대로 말한다("이미 가져간 뒤였다면 … 반영되지는 않습니다").
- **부분 추론 보존 등가물은 없다.** 기존 경로의 `preserve_reasoning` 에 대응하는 것이 브리지엔
  없다 — 개인 AI 안의 사고 과정은 관측 불가. 대신 조사 내역(도구 호출)은 보존된다.

### 테스트 교훈 (반복 패턴)

계약을 **고정 길이 윈도**(`text[i:i+2500]`)나 함수 본문 문자열로 잠근 테스트 8건이 리팩터링
한 번에 무더기로 깨졌다. 계약 자체는 살아 있는데 **검사 범위 밖으로 나간** 것이다. 더 나쁜
경우는 반대 방향이다 — 범위가 조용히 좁아져도 green 이면 아무도 모른다. 이번에 경계를
**문법으로**(괄호·중괄호 균형) 잡는 `_js_func` 헬퍼로 바꿨고, 그 과정에서 파라미터 구조분해의
`{` 를 본문으로 오인해 함수가 한 줄로 잘리는 함정도 만났다(그대로 뒀으면 계약 미검사인데 통과).
## CHG-20260828T100000 — 온보딩 지시문의 자기 증명 (TASK-20260828T100000)

**외부 AI 가 우리 온보딩을 거절했다**(제보 2026-08-27). 그 판단은 옳았고, 결함은 우리 쪽에 있었다.

| 그들이 본 것 | 실제 코드 | 왜 갈렸나 |
|---|---|---|
| "무제한 원격 코드·명령 채널" | 실행 명령은 `_CLI_ADAPTERS` 에 **하드코딩**. 서버가 보내는 것은 질문 텍스트뿐 | 지시문이 그 사실을 말하지도, 확인 수단을 주지도 않았다 |
| "알 수 없는 주체가 TLS 를 가로채도록 허용" | `--cacert`/`NODE_EXTRA_CA_CERTS` 는 **프로세스 한정**. 전역 설치를 요구한 적 없다 | 범위를 밝히지 않아 시스템 신뢰 저장소 설치로 읽혔다 |
| "감시 회피 목적" | 러너가 옮기는 것은 **대기**뿐. 추론은 여전히 상대 계정·정책 아래 | "예산이 없는 일반 프로세스라 그 일이 없다" 가 회피 설계로 읽혔다 |
| "평문 장기 크리덴셜" | 세션 결합 · 로그아웃 즉시 무효 · 최대 12시간 | 수명·폐기 경로를 한 줄도 적지 않았다 |
| "검증 불가" | CA 지문 인프라는 `bin/trust-bundle.sh` 에 **이미 있었다** | 그 지문이 **연결 지시문에는 한 글자도 없었다** |

진단: 이것은 로직 결함이 아니라 **증명 부재**다. 좁게 만든 것과 좁다는 것을 보이는 것은 다른 일이고,
후자를 안 하면 전자는 아무 소용이 없다.

### 조치

| 대상 | 변경 |
|---|---|
| `oauth_as._ca_fingerprint` (신규) | Root CA 의 SHA-256 **지문**(DER 기준 — 파일 바이트 아님). PEM 블록을 직접 추출해 앞머리 주석이 있어도 계산되고, **여러 장이면 값을 내지 않는다**(어느 장인지 말할 수 없으면 오경보가 된다) |
| `oauth_as._runner_checksum` (신규) | **서빙되는** `static/agent/bridge_agent.py` 의 SHA-256. 정본이 아니라 실물을 해싱한다 — 둘이 갈리면 체크섬은 안전장치가 아니라 오경보 장치가 된다 |
| `oauth_as._cached_digest` (신규) | (경로, mtime, size) 키 캐시. 경로만 키로 삼으면 CA 회전 후 **옛 지문**을 계속 실어 온보딩이 통째로 막힌다. 실패는 예외가 아니라 빈 값 — 무결성 값 때문에 발급이 죽으면 안 된다 |
| `oauth_as.compose_connect_handoff` | 머리말 교체(발급자 명시 · 확인 여지 보장) · 검증 값 블록 · CA 신뢰 **범위** 명시 · 토큰 성질 · 러너 5단계 분리(체크섬 → 소스 확인 → `--check` → `--once` → 상주 + `kill`·로그) · "턴 예산" 근거는 유지하되 **옮기는 것은 대기뿐**임을 밝힘 |
| `connect_issue_token` | 발급자 `username` 을 지시문에 전달 — 받는 AI 에게 유일한 출처 표시 |
| `bridge_agent.py` docstring | `## 보안 계약` 신설. 받는 것 / 실행하는 것 / 셸 미경유 / 원격 코드 없음 / 설치물 없음 / 나가는 곳 / 관측·종료 를 **직접 확인할 명령과 함께** 기술 |

### 정직하게 남긴 것

- **잔여 신뢰 경계를 러너 소스에 그대로 적었다**: 서버가 보낸 질문 텍스트는 상대 AI 의 프롬프트가
  되고, 그 AI 가 도구를 쓸 수 있다면 유도의 여지는 남는다. 이 파일이 없앨 수 있는 위험이 아니다.
  "전부 안전하다" 고 말하는 순간 문서 전체가 신뢰를 잃는다 — 한 군데의 과장이 나머지 사실까지
  의심하게 만든다. 그래서 상대 런타임의 권한 설정을 낮추라고 요구하지 않는다는 것도 함께 적었다.
- **지시문에 실린 지문은 신뢰의 뿌리가 아니다**(같은 채널로 온다). 뿌리는 운영자가 별도 채널로
  공유하는 지문이고, 지시문은 그 사실을 숨기지 않고 말한다. 그래도 "내려받은 것이 서버가 말한
  그것인가" 는 확인되고, 전송 중 바꿔치기와 오래된 사본은 걸러진다.
- **공인 IP 접속 자체는 바꾸지 않았다.** 공개 신뢰 인증서로의 전환은 이 cycle 의 범위가 아니고
  (사내 이름 해석·발급 경계가 따로 걸린다), 지문 대조가 그 자리를 메운다.

### 테스트

`test_handoff_trust.py` 20건. 문안 회귀를 **문자열로** 잠근 이유: 이 결함은 로직이 아니라
**문장**이었다. 다음 사람이 "간결하게" 줄이는 순간 그대로 되살아나고, 그때 다시 거절당한다.

작성 중 테스트가 실제 결함 1건을 잡았다 — `ssl.PEM_cert_to_DER_cert` 는 파일이 BEGIN 줄로
**시작**해야 하는데, 실물 CA 파일에는 앞머리 주석이 붙곤 한다. 그대로였다면 지문이 조용히
빈 값이 되어 "서버가 계산하지 못함" 으로 나갔을 것이다(고장 아닌 고장).

### 자체 적대 리뷰가 잡은 것 (같은 cycle)

| # | 심각도 | 결함 | 조치 |
|---|---|---|---|
| 1 | P1 | 지문을 `/certs/rootCA.pem` 으로 계산하는데 AI 가 실제로 받는 것은 `/trust/rootCA.crt` — **다른 파일**이다. CA 회전 후 `bin/trust-bundle.sh` 재조립이 누락되면 갈리고, 받는 쪽은 정상 절차를 따랐는데 불일치를 보고 중단한다 | web 에 `artifacts/trust-bundle:/srv/trust:ro` 마운트 + `_ca_bundle_path` 가 **서빙 파일 우선**, `/certs` 는 폴백 |
| 2 | P1 | `def _ca_fingerprint(path=_CA_BUNDLE_PATH)` — 기본 인자가 **import 시점에 바인딩**돼 런타임 env 변경이 반영되지 않는다. 더 나쁜 것은 이 결함이 **조용하다**는 점이다: 로컬에는 `/certs/rootCA.pem` 이 없어 어느 쪽이든 빈 값이라 테스트가 통과하고, 파일이 실재하는 컨테이너에서만 어긋난다(환경 사실에 기댄 vacuous pass) | `_ca_bundle_path()` 로 **호출 시점 해석** + `test_ca_path_is_resolved_at_call_time_not_import_time` 로 회귀 고정 |
| 3 | P3 | 캐시 키가 `(경로, mtime, size)` 라 파일이 바뀔 때마다 항목이 **쌓인다**(옛 키가 지워지지 않음) | 경로를 키로 두고 값에 `(mtime, size, digest)` — 갱신이 곧 대체 |

2번은 이 저장소가 반복해 온 형태다 — **테스트가 코드가 아니라 환경을 검증하고 있었다.**

### 적대 패널이 잡은 것 (같은 cycle · 보안 리뷰 + 뮤테이션 리뷰 2인)

**가장 값진 발견은 "우리가 새로 쓴 문장이 거짓이었다" 는 것이다.** 이 cycle 의 목적이 정직한
증명이었으므로, 그 안에 들어간 과장은 다른 어떤 결함보다 비쌌다.

| # | 심각도 | 결함 | 조치 |
|---|---|---|---|
| 1 | P1 | **"서버는 명령도 코드도 보내지 않는다 — 오가는 것은 질문 텍스트와 답변이다" 가 거짓.** `claim_request` 는 운영자 5단계 지침(`system_prompt`)을 함께 주고 러너가 그것을 프롬프트 **맨 앞**에 "이걸 시스템 프롬프트로 삼아 답하라" 로 놓는다. 질문·대화이력은 ⟦UNTRUSTED-DATA⟧ 로 구획되는데 **서버가 완전히 통제하는 이 필드만** 구획 없이 권위가 승격된다. 우리가 알려 준 확인 경로(`compose_prompt` 를 읽어라)로 30초면 드러난다 | 지시문·러너 계약 모두에 **채널의 존재와 의미**를 명시("운영자는 네 답변 방식에 영향을 줄 수 있다") + 무엇을 보면 확인되는지(`claim_request` 응답의 `system_prompt`) |
| 2 | P1 | **"토큰을 디스크에 쓰지 않는다" 가 오도.** `save_conf` 한정으론 참이지만, `compose_prompt` 가 토큰을 프롬프트 본문에 넣고 그 전문이 argv 로 CLI 에 넘어간다 → `/proc/<pid>/cmdline` · CLI 세션 기록 · (지시문대로 치면) 셸 히스토리 | 노출면 3곳을 그대로 적고 회피 수단(`BRIDGE_TOKEN` env — 코드에 이미 있었으나 안내가 없었다) + 수명 상한이 이 노출면의 상한임을 명시 |
| 3 | P2 | **CA 다운로드 부트스트랩 데드락.** 엣지 인증서를 서명한 것이 그 CA 라 CA 없는 클라이언트의 https 는 self-signed 로 실패하는데, 같은 지시문이 "검증을 끄지 마" 라고 못박아 우회로도 없다 — 막히거나·규칙을 어기거나·사람에게 되묻는 셋 중 하나. 엣지는 이 목적으로 `/trust/*` 를 **평문 HTTP** 로도 서빙한다(HSTS 를 뺀 이유도 그것) | 평문 URL 을 **먼저** 주고, 왜 평문인지와 **그 위험을 지문 대조가 덮는다**는 것(지문은 https 로, 파일은 http 로 오므로 바꿔치려면 두 채널을 동시에 잡아야 한다)을 함께 적음 |
| 4 | P2 | **롤링 배포 중 러너 체크섬 스큐.** web-a/web-b 가 한 번에 하나씩 교체되는 동안 브라우저(지시문 발급)와 AI 머신(파일 다운로드)은 **다른 클라이언트**라 sticky 가 묶어 주지 않는다 → 정상 배포가 "멈추고 알려라" 를 발동시킨다 | "배포 교대 중일 수 있다 — 1분 뒤 다시 받아 한 번 더 대조" 고지 |
| 5 | P2 | **`/trust/` 링크가 자기모순.** "전역 설치를 요구하지 않는다" 고 한 뒤 대조 근거로 그 링크를 주는데, 그 페이지 첫 화면이 certutil·`security add-trusted-cert` 다 — 없애려던 거절 사유를 링크 한 번으로 재확인시킨다 | "그 페이지는 사람용 전역 설치 안내다. 너는 설치할 필요 없고 **지문만** 대조하면 된다" |
| 6 | P2 | **`--base` 접두 검사 우회.** `http://127.0.0.1@evil.example` · `http://127.0.0.1.evil.example` 이 통과해 토큰이 평문으로 남의 서버로 나간다. 코드는 그대로였지만 이번에 이것을 "보안 계약" 의 검증 가능한 항목으로 **승격**시켰으므로 우회 가능성은 곧 계약 위반이다 | `_transport_is_safe` — urlsplit 으로 **hostname 판정**(urllib 이 실제로 접속할 값). 10 케이스 실측 |
| 7 | P3 | "나가는 곳 한 곳 … `Api.call` 이 유일한 자리" 가 거짓 — `BRIDGE_OLLAMA_URL` 이 두 번째 URL 생성 지점이고 프롬프트 전문을 POST 한다 | 둘 다 적고 조건(`--ai ollama` 일 때만)을 밝힘 |
| 8 | P3 | 같은 계약 표 안의 자기모순 — "끝나면 아무것도 남지 않는다" ↔ "`config.json` 을 남긴다" | 남는 것을 정확히 열거 |
| 9 | P3 | "권한은 DB 조사 도구뿐" 과장 — 같은 토큰이 `submit_answer`·`open_task`·`read_task_attachment` 까지 준다 | "네 계정의 것에 한정 — 조사·조회 + 답변 제출·첨부 열람" |
| 10 | P3 | `EXT_TOOL_CA_BUNDLE` 재사용 — **정반대 의미**의 이름(우리가 외부에 붙을 때 검증용 CA)이고 사용자 가이드가 값을 권한다. 누가 그 값을 web env 에 넣으면 "서빙 파일 우선" 이 조용히 무효 | 전용 이름 `BRIDGE_HANDOFF_CA_PATH` |

#### 뮤테이션 리뷰 — 39 뮤턴트 중 13 SURVIVE (테스트 사각지대)

계약이 **표현만 잠그고 의미·위치·활성 여부를 안 잠근** 형태가 대부분이었다.

| 사각지대 | 무엇이 뚫렸나 | 조치 |
|---|---|---|
| 배선 단방향 | `connect_issue_token` 의 `username=` 을 지워도 22건 전부 green — 발급자 표시가 영구 익명화되는데 아무도 모른다(헬퍼를 직접 부르는 테스트만 있었다) | 호출부 keyword 를 AST 로 검사 |
| 문안이 표현만 | 같은 뜻 다른 말("누구에게도 재확인할 필요 없어") · 문구를 모듈 상수로 이동 · **삼중따옴표 안의 `#` 로 시작하는 줄**을 주석 필터가 삼킴 | **렌더된 지시문**을 검사 + 금지어를 의미 단위로 확장 + 소스 잔재는 공용 `_srcutil.code_only`(같은 함정에 네 번 데인 feature 의 정본) |
| 우연 부분문자열 | `"kill" in text` 는 안내 줄을 지워도 **설명문의 "kill 한 번으로"** 가 대신 매칭 · 다운로드 URL 에 `?v=2` 가 붙어도 통과(그러면 받는 파일과 체크섬이 갈린다 — 이 파일이 막겠다던 오경보) | 라벨 앵커(`"종료: kill"`) · URL 은 **줄 끝 일치** |
| 자격증명 미검사 | 토큰을 플레이스홀더로 바꿔도 통과 → 붙여넣은 AI 가 401 만 보고 멈춘다(머리말이 거짓이 된다). 1차 수정도 부족했다 — A 섹션의 `--header "Authorization: Bearer …"` 가 대신 매칭 | **인증 줄 자체**에 앵커 + 경로별 실재 횟수 |
| 캐시 절반 | 빈 값도 캐시하면 **일시적 읽기 실패**(회전 중 부분 기록)가 영구 고착 · 키에서 size 를 빼면 초 단위 mtime 파일시스템의 같은-초 재배포를 놓침 | 두 축 각각 실측 테스트 |
| compose 활성 | 마운트를 주석 처리해도 부분문자열이 통과 → 폴백으로 떨어져 위 P1-1 이 부활 | `- ` 로 시작하는 **활성 줄**만 인정 |
| 세션 위생 | `_loaded()` 가 `feature-0003/src` 를 `sys.path[0]` 에 꽂고 `oauth_store` 를 세션에 남긴다. 이 저장소에는 top-level `modules` 가 **두 곳**이라, `oauth_as.py` 에 `modules.*` import 가 하나만 생기면 그 순간 무관한 테스트가 무더기로 깨진다(그리고 원인은 이 파일로 보이지 않는다) | 창에서 들어온 feature-0003 모듈 전부 원복 + 누수 없음을 테스트로 고정 |

조치 후 SURVIVE 였던 뮤턴트 5종(C2·X1·X7·X8·X11)을 **재적용해 전부 KILL 확인**. 테스트 22 → 37건.
## CHG-20260828T080000 — 미연결 질문 보관·이어받기 (TASK-20260828T080000)

**제보**: "인증을 포함한 요청 즉시 제목은 바뀌었지만 LLM 동작 및 실행 자체가 막힌 상태."

라이브 실측으로 **판정은 정확했음**을 확인했다 — 19:07:58 로그아웃이 AI 연결 토큰을 함께
폐기했고(P0-R 의 의도된 동작), 19:08 질문 시점엔 연결이 없었으며 19:09 에 재연결됐다.
결함은 판정이 아니라 **그 다음**이었다: 재입력 요구.

| 축 | 종전 | 지금 |
|---|---|---|
| 미연결 질문 | 적재 안 함 · "다시 질문해 주세요" | `Status='deferred'` 보관(대기열 비가시) |
| 연결 성립 | (없음) | 최근 1건만 `open` 승격 · 나머지 `expired` |
| 폭주 방지 | 적재 차단 | **승격 1건 제한** — 같은 것을 지키며 재입력만 제거 |

**codex 적대 리뷰 P1 5 · P2 3** — 승격 비원자성(→ 단일 `CASE WHEN` UPDATE) · 보상 삭제가
`deferred` 미포함(→ `CANCELABLE_STATUSES`) · 만료 말풍선 정정 실패의 영구 잔존(→ 최근 만료분
재정정, idempotent) · 미연결 응답이 프런트에 미도달(→ `bridge_deferred` 로 조립 조건 확장) ·
`expired` 가 terminal phase 미반영(→ 서버·프런트 양쪽) 수정. 2건(연결 판정이 토큰 존재 ·
대기 중 새 보류 인지)은 기존 구조의 한계로 기록.


## CHG-20260828T120000 — 지시문이 화면에 도달하지 않았다 (TASK-20260828T120000)

직전 cycle(CHG-20260828T100000)이 지시문을 전면 개정하고 배포까지 마쳤는데, **사용자가 보는
화면에는 옛 문안이 그대로 있었다.** 라이브 PB-0008 이 아니었으면 몰랐다.

| 확인 | 값 |
|---|---|
| 배포 | 전 서비스 `54e84874` (= main HEAD) — 정상 |
| 컨테이너 무결성 값 | CA 지문·러너 체크섬 모두 계산됨(마운트 정상) |
| **화면** | **785자 옛 문안** — 러너·TLS·검증 값 전무, "나한테 더 묻지 않아도 돼" 포함 |

원인: `ai-connect.js` 가 서버의 `body.handoff` 를 버리고 **자체 조립**했다. 서버 문안이 여러
차례 개정되는 동안 이 사본은 갱신되지 않아 몇 세대 뒤처졌다.

### 왜 테스트가 못 잡았나

계약(`지시문은 서버가 조립한다`)은 **적혀 있었고 테스트도 있었다** — 다만
`test_modal_uses_server_composed_handoff` 라는 이름 그대로 **모달에만** 걸려 있었다.
단독 페이지는 검사 대상 목록에 없었다. 계약이 틀린 것이 아니라 **적용 범위가 좁았고**,
그 좁음은 green 으로는 보이지 않는다.

이것은 이 저장소가 반복해 온 형태다 — "헬퍼는 맞는데 배선이 끊겨 있다"(같은 cycle 의 C2
뮤턴트가 발급 엔드포인트에서 정확히 같은 것을 보였다). 이번엔 배선이 아니라 **소비자 하나가
계약 밖에 있었다.**

### 조치

| 대상 | 변경 |
|---|---|
| `static/ai-connect.js` | 자체 조립 `handoff()` 제거 → `body.handoff` 를 표시·복사 양쪽에서 사용. `baseOf`(조립 전용)·`issuedToken`(화면이 자격증명을 붙들 이유 없음) 제거 |
| `test_ux_parity.py` | `test_modal_uses_server_composed_handoff` → `test_every_surface_uses_the_server_composed_handoff` — **표시하는 화면 전부**를 parametrize. 자체 조립의 지문(`mcpServers` · 인증 줄 문자열 연결 · 옛 마무리 문장)도 함께 금지 |

### 교훈

**소스층이 전부 green 이어도 화면은 죽어 있을 수 있다.** 이번 검증에서 값을 만든 것은 단위
테스트가 아니라 실제 브라우저였다 — 배포 후 화면을 열어 보는 절차가 없었다면, 보안 우려를
해소한 지시문은 **아무에게도 도달하지 않은 채** 완료로 기록됐을 것이다.

## CHG-20260828T140000 — 배포 후 실화면 검증 결과 기록 (증적 전용)

코드 변경 0. 두 cycle 의 POST-DEPLOY 항목을 **실측으로 닫는다**.

| cycle | 1차 | 2차(수정 배포 후) |
|---|---|---|
| TASK-…100000 (온보딩 지시문) | **결함** — 배포 정상인데 화면은 785자 옛 문안 | — |
| TASK-…120000 (화면 도달성) | 위 결함의 원인 규명·수정 | **PASS** — 5,664자 새 문안 도달 |

2차 판독(배포 `369b40b1`): CA 지문·러너 체크섬 **실값 렌더** · 평문 CA 가 https 보다 앞
(부트스트랩 데드락 해소) · 발급자 표시 · 운영자 시스템 지침 고지 · 토큰 노출면 고지 ·
5단계 러너 절차 · 거절 사유 문구 부재. 레이아웃 `max-height:340px`+`overflow-y:auto`
(`scrollHeight 4157`) 스크롤 정상·**잘림 없음**, [복사]는 DOM 전문.

증적: `unit/feature-0003-agent-web-ui/docs/test-runs.d/evidence/TASK-20260828T120000-connect-after.png`

**이 기록의 값**: "배포했다" 와 "사용자에게 도달했다" 는 다른 사실이고, 이번에 그 둘이 실제로
갈렸다. 완료 판정을 서비스 이미지 태그가 아니라 **화면**으로 한 것이 이 두 cycle 의 차이를
만들었다.
## CHG-20260828T120000 — 러너 AI 타임아웃 900s → 1700s (TASK-20260828T120000)

**관측**: PB-0008 실 브라우저 검증 중, 27단계 조사가 끝나기 전에 러너가 중단했다
(화면 답변: "AI 호출이 900초를 넘겨 중단했습니다").

900초는 서버 점유 lease(30분)의 **절반**이다. 즉 서버는 아직 그 러너의 점유를 인정하는데
러너만 먼저 포기하는 구간이 15분이나 있었다 — 개인 AI 는 답을 만드는 중이었다.

`1700초 = lease 1800초 − 제출 여유 100초`. 여유를 남기는 이유: 타임아웃 직후의
`submit_answer` 도 lease 안에서 끝나야 답변이 원 대화에 붙는다(lease 밖이면 그 사이 다른
세션이 같은 질문을 다시 집을 수 있다).

러너는 stdlib 전용 단일 파일이라 서버 상수를 import 할 수 없다. 그래서 **두 값의 관계를
계약 테스트로 고정**했다(lease 안 · lease 의 80% 이상) — 한쪽만 바뀌면 테스트가 잡는다.
## CHG-20260828T093000 — 취소 통보 무한 루프 · 연결실패 오판 · 버튼 박제 (TASK-20260828T093000)

**라이브 실측(PB-0008)에서만 드러난 결함 4건.** 앞선 cycle 의 테스트는 전부 green 이었고
**전부 맞았다** — 못 본 것은 구조가 아니라 **시간에 따른 루프 동역학**이었다.

### [P1] 취소를 매번 다시 통보해 tight loop → 러너 사망 → **다른 질문의 답변 유실**

`wait_for_request` 가 `Status='canceled' AND ClaimedBy=me` 행을 매 호출 다시 집었다. 그러면
`timed_out = not canceled` 가 영원히 False → 대기가 즉시 반환 → 호출측이 **간격 없이** 재호출.
P0-J 가 없애려던 그 tight loop 가, 이번엔 **우리 서버를 향해** 생겼다.

러너 로그(실측)가 그대로 보여준다:

    취소 통보: t_Y1Mwn…        ← supersede 정상
    t_mp8QM…: 내 AI 에게 전달   ← 병렬 워커 정상
    t_Y1Mwn…: 사용자가 취소했다 — 중단(제출 안 함)   ← 하차 정상
    취소 통보: t_Y1Mwn…        ← ❌ 같은 취소를 또
    FATAL: … 20회 연속 …        ← spin 가드 발동, 러너 사망

그리고 죽으면서 **진행 중이던 t_mp8QM 의 답변이 통째로 유실**됐다. 조용한 낭비가 아니라
사용자 대면 손실이다.

조치: 알린 **직후 점유를 놓는다**(`ClaimedBy=NULL`). `Status='canceled'` 는 **유지** —
`submit_answer` 409 집행과 화면의 `canceled` 국면이 그 값에 걸려 있다.

### [P2] 러너가 "처리할 것이 없는데" stall 로 셌다

`timed_out` 이 아니기만 하면 `stalled++` 했는데, `timed_out` 은 **취소 통보로도** False 가
되고 그때 `task_ids` 는 비어 있다. → `res.get("task_ids")` 가 있을 때만 센다.

### [P2] `_http: 0`(연결 실패)을 성공으로 읽었다 — `--check` 가 "연결 정상" 거짓보고

`Api.call` 은 연결 실패에 `{"_http": 0}` 을 돌려주는데 **0 은 falsy** 라
`not probe.get("_http")` 와 `if code:` 가 모두 성공으로 읽었다. 실측: 사설 CA 미지정 상태에서
`--check` 가 **"연결 정상."** 을 출력했고, 본 루프는 빈 응답을 정상 처리하다 spin 가드로 죽었다.

더 나빴던 것은 **주석과 코드의 어긋남**이다 — 백오프 블록 주석이 "`_http == 0` 을 다룬다" 고
적어 두었는데 조건이 `if code:` 라 정작 0 을 건너뛰었다. 주석만 읽으면 고쳐진 것으로 보인다.

조치: `{"_failed": True}` 명시 플래그 + 두 판정부 교체 + `--ca` 힌트.

### [P3] 답변 도착 후 중단 버튼이 '중단' 에 박제

입력 핸들러의 재렌더가 `_myAskInFlightHere() || _bridgePendingHere()` 로 게이트돼 있는데,
대기를 지우는 순간 그 술어가 false 가 된다 — **화면을 고쳐 줄 트리거가 정확히 그 시점에 꺼진다.**
글자를 넣어도 풀리지 않았다(실측).

조치: 대기를 지우는 자리(`_renderBridgeAnswer` · `_applyBridgePhase`)가 `renderComposer()` 를
호출한다(취소 경로는 이미 그랬다 — 그 비대칭이 이번 결함이었다). 입력 핸들러에는
`dataset.mode === "stop"` backstop 을 둔다.

### 교훈

이 4건은 **소스 단정으로는 볼 수 없는 성질**이었다 — "두 번째 호출에서 사라지는가",
"0 이 falsy 인가", "상태가 꺼지는 순간 누가 그리는가". 구조 테스트는 전부 통과했다.
회귀는 그 성질을 만들어 내는 **기전**을 단정하고(9건), 뮤테이션으로 실효를 확인했다.
## CHG-20260828T140000 — codex 적대 리뷰 P1 4건 · P2 4건 전건 조치 (TASK-20260828T140000)

계정 한도 회복으로 **외부 리뷰를 처음 확보**했다(앞 두 cycle 은 산출물 0). 8건 중 **3건이 내가
직전에 넣은 수정의 회귀이거나 그 수정이 만든 새 결함**이었다.

| # | 결함 | 조치 |
|---|---|---|
| P1-1 | 취소/supersede 가 **실제로 바꾸지 않은 task 도 성공 보고** → 취소 안내 아래 답변이 붙음. 내 P2 수정(쓰기 재확인)의 회귀 — 조건은 맞았고 **반환값이 안 따라왔다** | 건별 쓰기 + `rowcount` 확인, 확인분만 반환. 못 지운 것은 **취소로 승격** |
| P1-2 | 워커 포화 시 `slots.acquire()` 가 대기 앞이라 **취소 수신도 정지**(최대 28분 토큰 낭비) | 대기는 항상, 자리는 디스패치 직전 **비차단** |
| P1-3 | SSE 가 뷰어마다 커넥션 55초 점유 + **동기 DB 를 이벤트 루프에서** 실행(무관 경로까지 정지) | `asyncio.to_thread` + 동시 상한 40(초과는 **폴링 강등** 503) + `finally` 반납 |
| P1-4 | 점유 실패 1건이 **러너 전체 종료** → 다른 워커 답변 유실. 내 spin 가드의 blast radius 과다 | 죽이지 않고 배압 + 경고. 일시 장애(5xx·429·연결실패)는 영구 skip 금지 |
| P2-1 | 취소 통보가 계정 귀속 → 러너 B 가 A 의 통보를 소비, A 는 영원히 못 들음 | 수신자 조건에 `ClaimedClient` |
| P2-2 | `_failed` 를 claim·submit 에서 미확인(내 앞 수정은 대기 루프만) | 두 곳 판정 + submit 멱등 1회 재시도 |
| P2-3 | 죽은 커넥션 55초 재사용 → 완료·취소가 숨겨짐 | `_conn_broken` 신호로 재연결 |
| P2-4 | 적재 롤백 중 이미 점유되면 **질문 없는 고아 답변** | 못 지우면 취소로 승격 |

**교훈**: 세 축이 서로 다른 것을 잡았다 — 자체 감사는 순서 결함, 라이브 실측은 시간축,
**외부 리뷰는 내 수정이 만든 회귀와 내가 고른 설계의 대가**. 자기 코드의 트레이드오프는
자기가 가장 못 본다. 회귀 7건 + 뮤테이션 역검증(P1-1·P1-2 KILL).
## CHG-20260828T140000 — 진행 표시 구조화 · 내부 동작 · 진행 신호 타임아웃 (TASK-20260828T140000)

제보 3건이 두 뿌리로 모였다.

**뿌리 1 — 진행 표시가 완료본과 다른 축을 씀.** 데이터는 `tool_call_usage`(도구·스키마·행수
뿐), 렌더러는 `_renderBridgeSteps` 의 문자열 조립. 그래서 진행 중에만 `list_schemas 3행`
평문 나열이 됐고, 작업·근거가 실릴 자리가 아예 없었다. → 진행 표시도 `agent_runtime.steps`
(호출 시점에 우리가 기록한 것)를 읽고, `buildStepDetailEl` 로 그린다. 말풍선 안 비-SQL 단계
목록도 같은 카드로 교체.

**뿌리 2 — 상한을 러너의 시계로 집행함.** 900초 고정이라 27단계 조사가 중간에 끊겼다.
→ 도구 호출이 lease 를 갱신하고(진행 신호), 러너 고정 상한은 기본 제거. 상한은 "서버가
관측한 무진행 30분" 으로만 집행된다.

**추가**: 브리지 생애주기(가져감·제출함)를 `action='activity'` 단계로 남겨 "추론 단계 누락"
을 메웠다. 개인 AI 의 사고를 지어내지 않고, 우리가 관측한 진행만 `bridge-runtime` 출처로 적는다.

## CHG-20260828T160000 — 동시 처리를 수요에 맞춰 (TASK-20260828T160000)

고정 2개(`threading.Semaphore(workers)`)를 **수요 추종 풀**로 바꿨다. 고정값은 어느 쪽으로도
틀린다 — 질문 하나뿐인 대부분의 시간엔 남고, 몰릴 땐 모자란다.

| 대상 | 변경 |
|---|---|
| `WorkerPool` (신규) | 슬롯을 **목록**으로 든다(`last_used` + id). 카운터로는 "오래된 것부터 회수" 를 표현할 수 없다. `Condition` 기반이라 대기에 sleep 이 없다 |
| 확장 | `grow_to(len(pending))` — 서버가 준 대기 질문 수만큼, 상한(`--max-workers`, 기본 8)까지 |
| 축소 | `reap(now)` — idle(`--worker-idle-sec`, 기본 300초) 초과 유휴 슬롯을 **오래된 것부터**. 최소 1 유지 · 사용 중 보호 |
| 취득 순서 | **LIFO**(가장 최근에 쓴 것부터) |
| 메인 루프 | `slots.acquire()` → `pool.wait_for_free()`(자리 확인만, 잡지 않음) · `pending[0]` 단건 → `for task_id in pending` 다건 · 실패·draining 경로의 `slots.release()` 제거(자리를 잡기 전에 빠지므로 반납할 것이 없다) |

### 설계에서 중요한 두 가지

**LIFO 가 축소의 전제다.** 유휴 슬롯을 돌아가며 쓰면(FIFO) 전부 조금씩 최근이 되어 idle 임계를
넘는 슬롯이 영영 생기지 않는다 — 회수 코드가 아무리 맞아도 **호출될 일이 없다.** 한쪽만 계속
쓰면 나머지가 자연히 오래되어 대상이 된다.

**tick 을 새로 만들지 않았다.** 회수는 시간 기반인데, 타이머 스레드나 `sleep` 루프를 두면 이
파일이 지켜온 폴링 금지(P0-J)가 무너진다. 서버가 대기를 최대 55초 보류하므로 **그 반환이 곧
tick** 이다 — 조용한 시간대에는 타임아웃 라운드가 곧 회수 라운드가 된다. 새 sleep 0개.

### 깨진 기존 테스트 3건은 skip 하지 않고 이동·갱신

- `test_runner_waits_for_a_slot_before_asking_the_server` — 계약(자리 확인 후 질의) 그대로,
  검사 대상만 `slots.acquire()` → `pool.wait_for_free()`
- `test_runner_is_parallel_by_default` → `test_runner_scales_concurrency_to_demand` — "기본 2개
  고정" 은 **사용자 결정으로 바뀐 계약**이다. 원래 의도(긴 조사가 짧은 질문을 막지 않는다)는
  유지되고, 오히려 상한 8까지 늘 수 있어 종전보다 넓다
- `test_runner_wait_loop_cannot_spin[slots.release()]` — 실패 경로가 자리를 **잡기 전에** 빠지도록
  구조가 바뀌어 그 반납은 존재 이유가 사라졌다(구조적 해소). 대신 **점유 실패 시 잡아 둔 자리를
  반납하는가**로 대상을 옮겼다 — 그 경로는 여전히 고갈을 만들 수 있다

### codex 적대 리뷰가 잡은 것 (같은 cycle · 6건 전건 조치)

초판은 **동시성 결함 3종을 모두 갖고 있었다** — 관측 정지·수요 과소계산·실패 오판. 단위
테스트 66건이 전부 green 인 채였다.

| # | 심각도 | 결함 | 조치 |
|---|---|---|---|
| 1 | P1 | **포화되면 확장과 취소 통보가 함께 정지한다.** `wait_for_free()` 가 `wait_for_request` 앞에 있어, 슬롯 1개가 작업 중이면 대기 루프가 통째로 멈춘다. 취소는 그 응답 채널로만 오므로 사용자가 중단을 눌러도 최대 1700초 동안 개인 계정 토큰이 계속 탄다. **기본이 2였을 땐 남는 자리가 있어 가려져 있던 결함이, 1로 내리는 순간 상시화**됐다 | 서버를 **먼저** 읽고, 자리 대기는 **디스패치 뒤**로(한 건도 시작 못 했을 때만). 서버가 취소를 한 번만 알리고 점유를 놓으므로(`ai_tools` 의 같은 교훈) 즉시-반환 반복이 없다 |
| 2 | P1 | **확장량 과소 계산.** `grow_to(len(pending))` 가 진행 중 작업을 빼고 센다 — capacity 4·busy 3·pending 3 이면 총수요 6인데 아무것도 늘지 않고 한 건만 시작됐다(실측) | `grow_for(pending)` — 목표를 `in_use + pending` 으로. 대기 질문이 있으면 회수를 건너뛴다(곧 쓸 자리를 버리면 `available=0` 창이 생긴다) |
| 3 | P1 | **`claim_request` 연결 실패를 성공으로 판정.** `Api.call` 의 실패 계약은 `{_http: 0, _failed: True}` 인데 `_http` truthiness 만 봤다 — `0` 은 falsy 라 **점유하지도 못한 작업**이 워커로 넘어가고, 그 task 는 서버에서 계속 open 이라 무한 반복이 된다. 대기·`--check` 경로는 이미 `_failed` 를 보고 있었다 | claim 판정에 `_failed` 추가 |
| 4 | P2 | **락 밖 timestamp 가 정렬 불변식을 깬다.** 먼저 시각을 잰 스레드가 늦게 락을 잡으면 `_free` 가 역순이 되고, `reap` 이 맨 앞만 보고 break 해 **뒤에 갇힌 오래된 슬롯을 영영 회수하지 못한다** | `release(sid)` — 시각을 락 안에서 생성. 시그니처에서 시각을 없애 **구조적으로 불가능**하게 |
| 5 | P2 | **`--max-workers` 가 상한이 아니다.** `max(workers, max_workers)` 라 `--workers 100 --max-workers 8` 이 상한을 100 으로 밀어올렸다. 기존 `BRIDGE_WORKERS` 가 큰 머신에서 새 안전장치가 통째로 무력화되는 경로 | 시작값을 상한으로 clamp + 초과 시 로그. 풀 생성자도 자체 방어 |
| 6 | P2 | **스레드 시작 실패 시 슬롯·서버 점유가 함께 샌다.** 반납이 워커 `finally` 안에만 있어 `Thread.start()` 가 터지면 실행되지 않고, 예외가 main 까지 올라가 러너가 죽는다. task 는 lease 만료(30분)까지 묶인다 | `try/except (RuntimeError, OSError)` → 슬롯 반납 + skip |

**테스트 vacuous pass 도 함께 지적됐다**(P3): `test_grow_wakes_a_waiter` 는 waiter 와 다른
스레드가 `grow_for` 를 부르는데 실제 `main()` 에는 그런 구조가 없다(불가능한 실행으로 통과).
staggered demand · 포화 중 취소 · busy+pending 총수요 · `_failed` claim · 시각 역순 반납 ·
`workers > max_workers` · 스레드 시작 예외가 전부 빠져 있었다 — **결정적 재현 5개가 실패
동작을 보였는데 66건은 green** 이었다. 그 5개를 회귀 테스트로 잠갔다(총 23건).

**시계 주입 훅**을 둔 이유: 시각을 락 안에서 만들어야 정렬이 지켜지는데(#4), 그러면 호출측이
시각을 주입할 수 없어 회수 순서를 결정적으로 검증할 방법이 사라진다. 시계 자체를 갈아끼우면
둘 다 만족한다(`WorkerPool(..., clock=)`).

## CHG-20260828T180000 — 동적 풀 배포 후 확인 (증적 전용)

코드 변경 0. TASK-…160000 의 POST-DEPLOY 를 배포본 런타임으로 닫는다.

| 축 | 결과 |
|---|---|
| 서빙 러너 | `class WorkerPool` · 시작 1 · 상한 8 · 유휴 300초 — 컨테이너에서 직접 확인 |
| 지시문 | 배포본 `compose_connect_handoff` 실호출 → 5,771자 · CA 지문·러너 체크섬 실값 · 동시 처리 안내 3줄 |
| 풀 동작 | 1 → (진행 중 1 + 대기 3) 4 → 상한 8 → `WorkerPool(100, 8)` clamp 8 |

**미완 1건(정직)**: 브라우저 화면 판독. `win-browser` 의 `session-login`·`session-check` 가
CDP 브리지를 함께 닫아 `launch` → 로그인 → `goto` 가 서로를 무효화했다(3회 시도). 제품 결함이
아니라 검증 도구의 순서 의존 문제이며, 화면에 뜨는 문안이 서버 조립본 그대로라는 사실은 직전
cycle 에서 실화면으로 확인됐다(그 경로는 계약 테스트가 잠근다).

**남은 실측**: 개인 AI 런타임이 붙은 상태에서 동시 2건 이상 → 확장·회수 로그 관측.

## CHG-20260828T150000 — 실제 LLM 라이브 검증 (문서 전용, TASK-20260828T150000)

코드 변경 없음. 실제 `claude` CLI 러너로 질문 5건을 돌려 사용자 관점 전 구간을 검증하고
증적을 남겼다.

- **8축 전부 PASS** — 실 답변 · 인라인 쿼리결과(SQL 네비 + 결과 행) · 근거 · AI 추론 패널 ·
  진행 스트리밍 · **실 AI 작업 중 중단**(codex P1-2 조치의 라이브 확정) · 후속 질문 맥락 · 재답변
- **사전 코드분석 3건이 오판**이었음을 기록 — `tool_call_usage` 한 테이블만 보고 "인라인
  쿼리결과·rationale·CSV 없음" 이라 결론냈으나, 형제 cycle 들이 `agent_runtime.steps` 를 이미
  확장해 두었다. 원장 한 곳이 비었다고 정보가 어디에도 없는 것은 아니다.
- **잔여 괴리 1건** — 모델·추론 조작면이 사라진 자리에 설명이 없다(통제권은 러너 `--cmd` 로
  옮겨갔는데 화면이 그것을 말하지 않는다). UX 결정이라 사용자 확인 후 진행.
- 인증은 자율 수행(`WEB_BOOTSTRAP_ADMIN_*` env). 자격증명·토큰은 스크래치패드(0600)에만 두고
  검증 후 파기.
## CHG-20260828T200000 — `--check` 가 정상 연결에서도 항상 실패했다 (TASK-20260828T200000)

**라이브 실측이 아니었으면 못 찾았다.** 동적 풀 검증을 위해 러너를 띄우려다 `--check` 가
"연결 실패" 를 뱉었고, 확증해 보니 연결은 멀쩡했다.

| 대상 | 변경 |
|---|---|
| 확인용 probe | `wait_for_request`(10s) → `list_open_requests`(limit 1, 20s) |

**왜 틀렸나**: `wait_for_request` 는 질문이 없으면 55초를 보류하도록 설계된 도구다(P0-J 의
'폴링 아님' 이 바로 그 성질에 기대고 있다). 그것을 10초 timeout 으로 부르면 **정상 상태에서
반드시 read timeout** 이 난다. 확인용 호출은 **즉시 답하는 도구**여야 한다.

**왜 이제 드러났나**: 직전 cycle 이 `_failed` 판정을 추가하기 전에는 timeout(`_http=0`)을
**성공으로** 읽어 "연결 정상." 을 출력했다. 거짓 안심이었지만 결과적으로 통과했다. 그 오독을
고치자 반대쪽 오독이 표면화됐다 — **한쪽만 보면 두 오류가 서로를 가린다.**

**영향**: 온보딩 지시문의 ③단계가 `--check` 다. 질문이 없는 온보딩 시점에 항상 실패하므로,
외부 AI 는 연결이 정상인데도 거기서 멈춘다. 이 cycle 이 없었다면 "지시문은 고쳤는데 러너는
붙지 않는" 상태가 그대로 나갔다.

라이브 재확인: 같은 서버·같은 토큰으로 `--check` → `연결 정상.`
## CHG-20260828T150000 — 연결 지속(하트비트) + 로그아웃 시 러너 자동 종료 (TASK-20260828T150000)

연결이 **시간이 지나서** 끊기던 것을 **명시적으로 끊을 때만** 끊기게 바꿨다. 수명의 기준점을
'발급 시점' 에서 '마지막 생존 신호' 로 옮긴 것이 변경의 전부이고, 나머지는 그 결정의 파급이다.

| 파일 | 변경 |
|---|---|
| `routers/_bootstrap_schema.py` | `_ensure_bridge_heartbeat_schema` — `WebOAuthTokens.LastHeartbeatAt` 멱등 ALTER. fast/slow 양 경로 호출(운영 재기동은 slow path 를 안 탄다) |
| `oauth_store.py` | `heartbeat()` · `account_is_heartbeating()` · `_LIVE_TOKEN_PREDICATE` 상수화(두 판정이 한 술어를 공유) · 상수 3종 |
| `routers/ai_tools.py` | `POST /api/ai/bridge_heartbeat` · `_account_is_heartbeating()` · `account_is_listening(…, conn)` 2축 OR |
| `routers/oauth_as.py` | `_listening(…, conn)` · 연결 지시문의 토큰 수명 서술 정정 |
| `web_context.py` | 세션 만료 슬라이딩 + `AUTH_SESSION_MAX_DAYS`(절대 상한) |
| `bridge_agent.py`(+배포본) | `Api._post` 일반화 · `Api.heartbeat` · `start_heartbeat` 데몬 스레드 · `ActiveTasks` · `shutdown_after_drain` · 401 분기에서 drain 후 종료 |

### 왜 별도 테이블이 아니라 토큰 행인가

이 사실이 필요한 두 곳(수명 연장 · '지금 듣고 있는가' 판정)이 **모두 그 토큰 행을 이미 읽는다**.
나누면 같은 질문에 두 개의 답이 생기고, 갈리는 순간 느슨한 쪽이 사용자가 보는 진실이 된다
(P0-R 에서 이미 한 번 겪었다). `LastUsedAt` 을 재활용하지 않은 이유는 반대다 — 그것은 "쓰였다"
라는 넓은 사실이고, 여기서 필요한 것은 "대기하는 프로세스가 있다" 라는 좁은 사실이다.

### 왜 하트비트를 도구로 만들지 않았나

도구 표면은 "노출 = 가이드 열거 = `capabilities` = 수 대조" 가 계약(P0-I)이라 하나 늘리면 넷을
함께 고쳐야 하고, 무엇보다 **조사 도구 목록에 생존 신호가 끼면** AI 가 그것을 조사 수단으로 읽는다.
경로만 분리하고 **토큰 해석기는 공유**한다 — 인증 축이 갈리면 한쪽만 로그아웃을 반영한다.

### 기존 테스트가 깨진 두 곳 (계약은 유지, 검사 방식만 이동)

- `test_session_revoke_parity` 3건 — 술어를 상수로 모으면서 "함수 본문에 그 문자열이 있는가" 가
  성립하지 않게 됐다. 상수 값을 AST 로 읽어 **같은 조건**을 단정하고, 소비처가 그 상수를 쓰는지
  함께 본다(오히려 강한 계약).
- `test_runner_tells_how_to_come_back_on_401` — 401 을 보는 자리가 둘이 됐다(하트비트·대기 루프).
  복귀 안내는 **대기 루프 한 곳**이 정본이므로 검사 대상을 `main` 본문으로 특정했다. 파일 전체에서
  첫 `if code == 401:` 을 잡으면 하트비트 쪽을 보게 되어, 안내가 사라져도 통과한다.

### 교훈 — 하네스가 고장나면 '전건 통과' 와 '전건 생존' 이 같은 얼굴을 한다

뮤테이션 역검증 1차에서 9종이 **전부 생존**으로 나왔다. 원인은 코드가 아니라 하네스였다 —
컨테이너에 `pytest` 가 없어 출력이 `No module named pytest` 였고, "failed" 문자열이 없으니
스크립트가 그것을 '생존' 으로 읽었다. 신호 없음을 성공으로 읽는 판정은 언제나 이 방향으로
틀린다. `passed|failed` 어느 신호도 없으면 **HARNESS-BROKEN 으로 크게 실패**하도록 고친 뒤
재실행해 9종 전건 KILL 을 확인했다.

## CHG-20260828T170000-runtime-model-selector — 러너 신고 기반 모델·추론등급 선택기 (TASK-20260828T170000-runtime-model-selector)

- **날짜**: 2026-08-28
- **REQ**: 사용자 요구 — "웹브라우저 내 [모델 + 추론수준] 설정을 되살립니다. 해당 설정값에
  따른 워커를 동작시키고(없다면 워커 확장) 요청을 전달하는 방식으로 구성해주세요. 이는 각
  AI플랫폼에 대응되어야 하니 모델 종류의 확장도 염두해주세요. (claude 뿐만 아니라, codex 등...)"
- **위험도**: Major (외부 입력이 CLI 인자가 되는 신규 경로 + 라이브 조작면 복원)
- **계약**: `FUNCTION.md` §P0-Z3 (P0-T supersede)

### 왜

사용자가 "간단한 요청에도 큰 모델·깊은 추론이 도는 비효율" 을 지적했다. 조사해 보니 러너가
`--cmd` 없이 떠 있어 **모든 브리지 요청이 그 머신의 기본 모델 + 기본 effort** 로 처리되고
있었다(실측: `~/.claude/settings.json` 의 `effortLevel: high` 가 전 요청에 적용).

P0-T 가 하루 전 조작면을 지운 이유는 "서버가 런타임을 알 수 없어 고른 값을 번역할 수 없다"
였다. 사용자 결정으로 그 전제를 **러너가 직접 신고**해서 깬다 — 아는 쪽이 말한다.

### 변경 내용

| 층 | 종전 (P0-T) | 조치 (P0-Z3) |
|---|---|---|
| 러너 신고 | 없음 | `_RUNTIME_SPECS` 표(claude·codex·gemini·ollama) → `detect_runtimes()` 가 설치된 전부를 신고. ollama 는 `/api/tags` 실조회. 하트비트 본문에 **매번** 실음 |
| 스키마 | — | `WebOAuthTokens.RunnerCapabilities`(TEXT) · `WebAiTasks.RequestedRuntime`(VARCHAR32) 온라인 DDL |
| 저장 | — | `set_runner_capabilities` — **값이 바뀔 때만** 쓴다(30초 주기가 쓰기 증폭이 되지 않게). 유효성 술어는 하트비트와 **동일**(`_LIVE_TOKEN_PREDICATE`) |
| 카탈로그 | 차단이면 무조건 `hidden` | 차단 + 신고 있음 → 신고 목록(`runtime:model`, group=런타임) + `visible` + `model_selector_source: "runner"`. 신고 없음 → `hidden` 유지 |
| 전송·적재 | 미동봉·미적재 | 동봉 복원 + 세 컬럼 적재(`_split_runtime_model` 로 짝을 가름) |
| 전달 | `claim_request` 미전달 | `requested: {runtime, model, reasoning_level}` 전달 |
| 실행 | 인자 조립 경로 제거 | `build_cmd` — claude `--model/--effort`, codex `-m`/`-c model_reasoning_effort=`, gemini `-m`, ollama 본문 `model` |
| 화면 | 항목 숨김 | 같은 가드 유지(서버가 `visible` 일 때만 풀림) + 런타임별 추론등급(`reasoning_levels_by_runtime`) + 모델 변경 시 등급 재렌더 |
| 복원 | 저장 안 함 | 저장하되 hydration 이 **지금 신고된 목록**과 대조(`_bridge_model_offered`) |

### 신뢰 경계 (이 변경이 새로 만든 것)

신고는 토큰을 쥔 클라이언트가 주는 값이고, 그것이 DB → 화면 → `Popen` 인자로 흐른다. 두 겹:

- 서버 `_sanitize_runtimes`: 이름 문자집합(선행 `-`·공백·따옴표·세미콜론 불허) · 라벨 1줄 접기 ·
  개수/길이 상한 · **어긋난 항목만** 버림
- 러너 `build_cmd` 의 표 대조: 자기가 신고한 값만 인자화. 옵션 위장·타 런타임 모델·구 서버
  alias 전부 조용히 폐기 후 CLI 기본값

런타임 전환도 `want_runtime in _RUNTIME_SPECS and _which(want_runtime)` 로 이중 확인한다.

### 되돌리기

게이트 1개(`AGENT_SERVER_LLM_ENABLED=1`) — 해제 시 같은 코드가 원래 서버 카탈로그를 반환.
테스트가 세 갈래(신고 없음 / 신고 있음 / 게이트 해제)를 모두 잠근다.

### 검증

- 신규 `test_runtime_model_selector.py` 39건 — 신고 모양·주입 거부(파라미터 11종)·인자 순서·
  sanitizer 경계·저장/조회 술어 일치·프런트 배선
- `test_model_catalog_bridge_mode.py` 반환값 계약을 삼중으로 확장(신고 없음/있음/조회 실패/게이트 해제)
- P0-T 계약을 잠그던 5건은 **새 계약으로 재작성**(삭제 아님 — vacuous pass 방지)
- `make test` 전체 통과 · ruff clean
- `claude -p --model haiku --effort low "..."` 인자 순서 라이브 실측 통과
## CHG-20260828T160000 — 브리지 전 구간 라이브 검증 기록 (TASK-20260828T160000)

코드 변경 없음 — **증적만** 추가한다(문서 + 스크린샷 3장).

그동안 "미검증" 으로 남겨 온 항목들을 실제로 확인했다. 막고 있던 것은 두 가지였고 둘 다
이번에 풀렸다: ① 브리지 미성립(사용자가 relay 구성) ② 브라우저 계정과 러너 계정 불일치
(사용자가 부트스트랩 계정 자율 사용을 승인 → 그 계정으로 연결 발급·러너 기동까지 한 축에서 수행).

5개 축 전건 PASS(제목 2단 · 실행 단계 구조화 · 내부 동작 단계 · 미연결 보관 · 이어받기 1건).
상세는 REPORT §10 과 test-runs fragment.

## CHG-20260828T210000 — 동적 워커 풀 라이브 실측 (증적 전용)

코드 변경 0. 실제 러너를 라이브(`129b9a1a`)에 붙여 **확장·회수를 로그로** 확인했다.

```
[bridge] 대기 시작 … (동시 1건에서 시작 · 수요 시 최대 8 · 300초 유휴 시 회수 …)
[bridge] 취소 통보: t_ts6Q… — 진행 중이면 중단합니다.
[bridge] 동시 요청 1건(진행 중 1) — 슬롯 1개 확장, 동시 처리 2건
[bridge] 유휴 슬롯 1개 회수 — 동시 처리 1건
```

**두 P1 수정이 같은 로그에서 함께 실증됐다.**

- **총수요 기준 확장**(codex P1-2): 대기가 1건인데 확장이 일어났다 — 진행 중 1 + 대기 1 = 2 로
  셌기 때문이다. 종전 `grow_to(len(pending))` 였다면 1 ≤ capacity 1 이라 **확장 0** 이고, 두
  번째 질문은 첫 작업(25초)이 끝날 때까지 대기했다.
- **포화 중 취소 인지**(codex P1-1): `취소 통보` 가 **작업이 도는 중에** 도착했다. 대기 루프가
  자리에 막히지 않는다는 직접 증거다 — 종전 순서(자리 확보 → 질의)였다면 그 통보는 첫 작업이
  끝난 뒤에야 왔고, 그동안 개인 계정 토큰이 계속 탔다.

부수 관측: 실측 중 배포가 겹쳐 `서버 인스턴스 교대 중` 을 타고도 루프가 계속됐다(feature-0045).

## CHG-20260828T180000 — 진행 표시 자리·귀속 정합 (TASK-20260828T180000)

P0-Z 가 카드 구조는 맞췄으나 **자리와 귀속**이 틀렸다. 뿌리 셋:

1. 대기 말풍선에 `run_id` 각인이 없어 `_load_steps_for_message` 가 "이 시각 이전 최근 run"
   으로 폴백 → **직전 답변의 단계 수**가 붙었다(`단계 보기 (21)`).
2. 진행 단계 앵커가 **메시지 행**에 있었다 → 카드가 말풍선 밖 별개 블록으로 그려졌다.
3. `/api/progress` run 폴백이 브리지 run 을 잡아 **내부 경로 progress-strip** 까지 켰다 —
   P0-Z 가 만든 회귀다(사후 이관만 걸러내던 필터를, 호출 시점 기록이 우회했다).

조치: ① placeholder meta 에 `run_id = task_id` ② 앵커를 `.message-bubble` 로 ③ 폴백에서
`run_id NOT LIKE 't\_%'` 제외. 브리지 진행 표시는 전용 축(말풍선 안) 하나로 되돌렸다.
## CHG-20260828T220000 — 첨부 **쓰기** 복원 + 후처리 단일화 (TASK-20260828T220000)

사용자 제보로 P0-E 의 「의도적 잔여」 하나가 **판단 착오**였음이 드러났다. assistant 가 첨부를
고쳐 새 버전을 만들거나 새 파일을 남기는 동작이 브리지에서 사라졌는데, 사라진 자리가 조용하지
않았다 — 개인 AI 는 규약대로 블록을 만들었고 서버가 처리하지 않아 **파일 없이 "수정했습니다"**
가 남았다(라이브 실측, 첨부 1246 `sample.sql`, v1 그대로 + 원문 diff 노출).

P0-E 의 근거 「개인 AI 가 관례를 모른다」는 **사실이 아니었다**. 규약은 `agent_core` base
`SYSTEM_PROMPT` 에 있고 `_bridge_system_prompt` → `compose_system_prompt` 로 이미 전달되고 있었다.

- **정본 신설** `shared/attachment_write.py` — materialize edit → new → 도구 전달분 바인딩 →
  strip → 미전달 고지 → content 갱신. `ops` 로 web 원시연산 네임스페이스를 받는다.
- **worker 중복 제거** — `modules/ask.py` 의 자체 구현(~150행)을 정본 호출로 교체.
- **브리지 배선** — `_materialize_bridge_attachments`(`routers/ai_tools.py`)가 정본을 부르고,
  **영속에 성공했을 때만** 정리본을 돌려줘 회수 store(`core_messages`)에 넣는다. 원문 블록이
  회수본에 남으면 다음 턴 컨텍스트에 파일 전문이 통째로 재유입된다.
- **러너 프롬프트에 규약을 적지 않는다** — `system_prompt` 가 정본. 두 벌이면 형식이 갈릴 때
  서버 파서가 아는 쪽만 파일이 된다. 주석으로 이유를 고정하고 회귀로 잠갔다.
- **회귀 12건 신규** + 기존 worker 9건 **강화**(fake 가 정본에 stub 원시연산을 물려 실제 조립을
  검증하게 했다 — 이름만 얹으면 시퀀스가 가짜가 된다).

**잔여(정직하게)**: 동기 inproc 경로(`_ask_impl`)는 아직 세 번째 구현이다. 응답 body 에 첨부
목록을 싣고 materialize 사이에 step 을 기록해 shape 가 다르다 — 합치는 것이 옳지만 별도 cycle.

**병렬 대화 동시 진행**은 같은 세션에서 관측으로 확인했다 — 러너 워커 3에서 두 task 가 동시
처리되고 각 답변이 자기 대화에 앉았다(교차오염 없음). 증적:
`unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260828T220000-bridge-attachment-write.md`

## CHG-20260828T230000-caps-self-report — 능력 목록을 AI 자신이 정한다 (TASK-20260828T230000-caps-self-report)

- **날짜**: 2026-08-28
- **REQ**: 사용자 요구 — "실제 연결된 AI에 따라 '고를 수 있는 것'을 제한하여 노출. 노출 기준을
  설정하는 것은 연결 중 시도된 AI 스스로. … 플랫폼에 관계없이 클라이언트가 자유롭게 서술한
  모델과 추론레벨을 관대한 입장으로 수용"
- **위험도**: Major (새 outbound 실행 경로 + 사용자 계정 토큰 소모)
- **계약**: `FUNCTION.md` §P0-Z4 (P0-Z3 의 출처를 한 겹 더 옮김)

### 왜

P0-Z3 는 목록의 출처를 서버 → 러너로 옮겼지만, 러너가 신고한 것은 결국 우리가 적어 둔 표였다.
실측이 그 표가 틀렸음을 보여줬다 — codex 는 `gpt-5.6-sol`/`gpt-5.6-terra` 를 답했고(우리 표는
`gpt-5.1-codex`), 플래그도 `--model`(우리 표는 `-m`)이었다. claude 는 우리가 빠뜨린 `fable` 을 답했다.

### 변경 내용

| 층 | 종전 (P0-Z3) | 조치 (P0-Z4) |
|---|---|---|
| 목록 출처 | 러너의 `_RUNTIME_SPECS` 하드코딩 | **그 AI 에게 질의**(`probe_runtime_caps`). 표는 폴백으로 강등 |
| 호출법 | 하드코딩 플래그 | AI 가 답한 플래그. 없으면 표 |
| 표 밖 CLI | 지원 없음 | `--ai <이름>` 으로 지목 시 `[-p {prompt}]`·`[{prompt}]` 두 형태 시도 |
| 파싱 | (없음) | `_extract_json`(코드펜스·머리말 관대) + `_coerce_options`(문자열배열·name/id 키·매핑) + `_coerce_flag` |
| 캐시 | (없음) | `config.json` 의 `caps`. `--refresh-caps` 로만 갱신 |
| 질의 실행 | (없음) | **병렬**(순차 135초 → 병렬 112초) · **옵트인**(`probe=True`) · 실패 시 폴백 |
| 신뢰 경계 | 표 대조 | 동일 유지 + **플래그는 서버로 보내지 않음**(신고에 `model`/`effort` 키 없음) |

### 실측

- claude: 22.7초, 모델 4종·추론 5단계 정답
- codex: 112.3초, 모델 6종·추론 6단계 (표에 없던 값)
- 표 밖 가상 CLI(`mycli`)로 인자 조립·주입 거부 확인
- 신고 blob 에 `--model`/`{model}`/`model_flag` 부재 확인

### 고친 자기 결함

`float(os.environ.get(k, "0") or 120.0)` — `"0"` 은 문자열이라 truthy 이고 `or` 가 단락되지
않아 **timeout 이 0** 이 됐다. 질의가 시작하자마자 `TimeoutExpired` 로 죽고 폴백이 조용히
삼켜 "AI 가 답을 안 했다" 로 보였다. 실측으로만 드러나는 형태라 값 자체를 테스트로 잠갔다.

### 검증

`make test` 컨테이너 전량 green · ruff clean · 브리지 스위트 587건(신규 14건).

### 적대 리뷰 조치 (REV-20260828T230000, P1 2 · P2 6)

자체 점검이 P1 2건(플래그로 셸 실행·임의 플래그 편승 / 캐시 재검증 없음)을 먼저 잡았고
codex 가 같은 지점을 독립 지목했다. P2 6건은 전부 codex 발견:

- **P2-1** 신고 항목 얕은 복사 → 오염된 여분 키가 HTTP 본문에 실림(= "호출법 미유출" 계약이
  부분적으로 거짓이었다) → `{value,label}` 재구성
- **P2-2** 표 밖 `--ai` 가 실행 시 `detect_ai()` 로 갈아치워짐 → 이름 유지 + 학습한 호출 형태로 교정
- **P2-3** 폴백이 영구 캐시 → `source != "builtin"` 만 캐시
- **P2-4** 좀비 probe(후보 480초 vs 대기 250초) → 단일 절대 deadline 공유
- **P2-5** stdout 무상한 + JSON 탐색 O(n²) → 256KB · 후보 64개 상한
- **P2-6** `BRIDGE_CAPS_PROBE_TIMEOUT=abc` 로 **import 실패** → 유한 양수 5~1800초 검증

회귀 방어 테스트 15건 추가(브리지 스위트 611건 green).
## CHG-20260829T000000-resume-ai-scope — `--ai` 상속이 런타임을 지웠다 (TASK-20260829T000000-resume-ai-scope)

- **날짜**: 2026-08-28
- **위험도**: Minor (러너 1파일 · 되돌리기 자명)
- **계약**: `FUNCTION.md` §P0-Z5

**발단**: P0-Z4 배포 후 러너를 재기동했더니 로그가 `쓸 수 있는 것: Claude(4종, 추론 5단계)`
로만 나왔다 — codex 가 설치돼 있는데 신고에서 빠졌다.

**원인**: `save_conf` 가 **자동 감지 결과**를 `ai` 로 저장하고 `--resume` 이 그것을 상속한다.
P0-Z3 이전에는 `ai` 가 "무엇으로 답할까" 하나만 정했으므로 무해했지만, 지금은 같은 값이
`detect_runtimes(only)` 로 들어가 **신고 목록을 좁힌다**.

**조치**: 저장은 `args.ai` 명시분만, 상속은 제거(`base`·`ca`·`cmd` 만 복원).
회귀 테스트 2건(브리지 613건 green).

## CHG-20260828T200000 — 진행 표시를 기존 두 자리에서 갱신 (TASK-20260828T200000)

P0-AA 로 자리는 말풍선 안으로 옮겼으나 여전히 `.bridge-live-steps` 라는 **제3 블록**을 만들고
있었다. 완료본이 쓰는 두 자리(말풍선 details · 사이드 패널)는 아무도 갱신하지 않아, 드롭다운은
`1단계`인데 그 밖에 카드가 쌓이고 패널은 멈춰 있었다.

자리를 만들지 않고 **기존 두 자리를 갱신**한다 — details 는 `renderMessageDetails` 로 재구성
(펼침 유지), 「단계 보기」는 개수와 클릭 대상을 함께 교체, 사이드 패널은 `run_id` 로 대상
판정 후 갱신. 브리지가 내부 경로와 다른 판정 축(run_id)을 쓰는 이유는 대기 말풍선이
`pendingBubble` **객체가 아니라 저장된 메시지**이기 때문이다.
## CHG-20260828T240000 — 연결 게이트 + 원클릭 연결 (P0-AB · P0-AC)

**요구**: 브릿지 연결 상태가 아니면 요청을 막고 가이드를 즉시 제공, 메시지 박스 상호작용도
차단(연결 완수 후 활성화). 그리고 LLM 해석에 따라 결과가 달라지는 연결 방식을 정형화.

### 변경

| 파일 | 무엇 |
|---|---|
| `routers/oauth_as.py` | `_bridge_mode()` 신규 · `connect_status` 에 `ready`·`bridge_mode`·**`compose_blocked`** · `compose_launch_commands()` 신규 · `_setup_checksum()` · 발급 응답에 `launch` |
| `routers/conversations.py` | `_account_ai_is_listening()` 신규 · 토큰 없으면 **409 차단**(적재·저장 0) · 보류 축 `connected`→`listening` · `_BRIDGE_BLOCKED_ERROR`·`_BRIDGE_NOTICE_NOT_LISTENING` · 차단 응답 조립 |
| `static/app/connect-modal.js` | `isComposeBlocked`/`onComposeGateChange` export · `_paintGate` · 잠금 중 한정 폴링 · OS 탭 · `_launchRunner`(스킴) · `_copyFrom` |
| `static/app/composer.js` | `renderComposer` 잠금(`composerLocked`·`is-bridge-locked`) · `sendPrompt` 가드 · 409 흡수(말풍선 회수·입력 복원) |
| `static/app.js` | `onComposeGateChange` → `renderComposer` 배선 |
| `static/index.html` | 잠금 안내 패널(입력창 **위**) · 모달 재구성(명령 우선, 지시문 `<details>`) |
| `static/css/*` | 게이트 패널·OS 탭 스타일 · **footer 접힘 조건에 `.ai-conn` 추가** |
| `src/bridge_setup.{sh,ps1}` (신규) | CA·러너 대조 → 스킴 핸들러 등록 → `--check` → 상주. `static/agent/` 에 배포본(해시 일치 강제) |
| `feature-0006 Caddyfile` | 설치 스크립트 2개를 평문 HTTP 경로에 추가(부트스트랩 데드락) |

### 되돌리기

게이트 축은 `AGENT_SERVER_LLM_ENABLED=1` 하나로 전부 풀린다 — `_bridge_mode()` 가 False 가 되어
`compose_blocked` 도 False 가 되고, 잠금·차단이 동시에 사라진다(테스트가 양방향을 잠근다).
원클릭 축은 독립적이라 게이트와 무관하게 남는다.

### 검증

`make test` 컨테이너 전량 green · ruff clean · 신규 32건 + 기존 계약 9건 갱신.
PB-0008 실 Windows 브라우저에서 잠금·해제·모달 실측(결함 3건 발견·수정).
