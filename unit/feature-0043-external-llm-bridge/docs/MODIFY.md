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
## CHG-20260831T100000 — 관리 콘솔을 브리지 구조에 정합 (사용자 요청)

**요청**: "LLM 동작 과정이 바뀐 구조에 따라 '관리 콘솔' 에서 작동하던 LLM의 동작도 정합하게
구성하고 싶습니다."

**왜 필요했나**: feature-0043 이 서버 계정 LLM 을 차단하고 대화 답변을 개인 AI 브리지로
뒤집었는데 **그 전환이 대화 화면만 따라갔다**. `static/admin/*.js` 전체에 차단 사실을 읽는
코드가 0건이라, 버튼은 눌러야 503 을 알았고 집행되지 않는 설정이 "설정됨" 으로 보였으며
`LLM 사용량` 0 은 "아무도 안 쓴다" 로 읽혔다.

**무엇을 바꿨나**

- `routers/_console_llm.py` 신설 — 콘솔 LLM 상태 판정 **단일 정본**. `server_llm_blocked`
  (게이트)와 `delegation`(러너 신고)을 독립 축으로 유지. `/api/admin/me` 가 함께 싣는다.
- 조작면 4곳(메타 단건·일괄 · 프롬프트 자동작성 · 그래프 능동 분석)이 **누르기 전에** 상태를
  말한다. 판정은 `jobDelegable(jobKind)` — 러너 자격 ∧ 그 종류의 전 구간 배선.
- 미적용 설정 4종에 배지 + 패널 내 사유 dropdown + 설정 탭 최하단 집계(사용자 결정).
- `AI 운영 현황` 에 브리지 축·KPI·위임 작업 현황(소유/수행 계정 분리).
- `LLM 사용량`·`추론` 화면에 집계 범위 배너 — 지표의 침묵이 오독이 되던 두 자리.
- `WebAiTasks` 에 `Kind`·`JobKind`·`JobPayload`·`JobAppliedAt`·`JobApplyError` 비파괴 ADD.
  `WebOAuthTokens` 에 `RunnerFeatures`·`RunnerAgentVersion`.
- 배급 자격(`_runner_job_grants`/`_dispatch_scope_sql`)과 claim/submit 의 `Kind` 분기.

**되돌리기**: 게이트 1개(`AGENT_SERVER_LLM_ENABLED=1`) — 컬럼은 비파괴 ADD 라 잔존해도 무해.

**의도적 잔여 (정직하게)**: 각 기능의 **적재 호출부·프롬프트 조립·산출물 반영**(C2 호출부 ·
C7~C10)은 미완이다. 그것을 화면이 낙관하지 않도록 `JOB_SPECS[...]["wired"]` 를 **전부 False**
로 두었다 — `enqueue_console_job` 이 거절하고 조작면은 사유와 함께 비활성으로 보인다.
부분 배선을 True 로 적지 않는 것이 P0-M·P0-T 의 함정("고를 수 있는데 반영은 안 되는")을
다시 열지 않는 유일한 방법이다. 근거: `docs/REVIEW.md` REV-20260831T140000-console-job-scope.
## CHG-20260831T113350-ai-claude-feature-0043-live-steps-reasoning — 추론 구간 표시 + 진행 갱신 중단 해소

**제보 (2026-08-31)**: ① 「각 도구에 대한 수행시간은 확인되었지만, 추론을 진행하는 부분은
확인되지 않아」 ② 「답변 도중 실행단계의 진전이 갱신되지 않는다 … 새로고침하면 진전돼 있고
일정 시간 후 또 멈춘다」.

### 근본원인

| # | 무엇 | 왜 |
|---|---|---|
| R1 | 추론 구간이 화면에 없다 | 브리지 `activity` 단계가 `claim`·`submit` 둘뿐이라 **도구 사이**를 덮지 못했다. 도구 단계는 자기 `elapsed_ms` 만 갖고, 그 사이 간격은 어느 단계에도 귀속되지 않아 타임라인에서 사라졌다 |
| R2-a | 진행 갱신이 멈춘다 (주 원인) | `_consumeBridgeStream` 이 **모든** 예외를 `"aborted"` 로 반환 → `_streamBridgeStatus` 가 정상 종결로 읽어 `true` 반환 → 폴링 폴백도 안 걸림. **회선 오류 1회가 감시를 영구 종료**. 새로고침이 `resumeBridgePolling` 으로 되살리므로 제보의 증상과 정확히 일치 |
| R2-b | 상한이 조기 소진 | 예산이 **횟수**(33) 라 3초 오류 재시도가 55초 정상 재접속과 같은 값을 먹었다 |
| R2-c | 상한 도달 후 영구 정지 | `_bridge_live_steps` 가 `ORDER BY step_index ASC LIMIT 40` → 41번째부터 **가장 오래된 40건에 고정**, 서버 변경감지도 `len()` 만 봐서 신호가 영영 멎었다(무음 절단, §16.7 G9-b) |
| — | 부수 | 같은 함수가 tick(1초)마다 PG 커넥션을 열고 **닫지 않았다** |

### 변경

| 파일 | 무엇 |
|---|---|
| `routers/ai_tools.py` | `_record_bridge_reasoning_gap` 신규 — 도구 단계 직후 「결과를 검토하고 다음 작업을 정합니다」 activity 1건. `_bridge_live_steps` → 최신 쪽 창 + `(steps, omitted)` 반환 + 커넥션 close. `_bridge_stream_snapshot`·`bridge_status` 에 `steps_omitted`. `bridge_stream` 변경감지를 `(len, omitted, 마지막 step_index)` 서명으로 |
| `static/app/composer.js` | abort ↔ 회선 오류 분리(`"error"`) · 시간(단조 시계) 기준 예산 · 연속 오류 3회 시 폴링 강등 · 최소 재접속 주기 · 「단계 보기」 개수를 총 단계 수로 |
| `static/app.js` | `refreshStepSidePanelForRun(runId, steps, {live, omitted})` · 생략 고지 1줄 · 진행 중 마지막 단계 「진행 중」 표기 · 생략 시 '누적' 미표시 |
| `static/css/chat.css` | `.step-side-panel-time.is-running` · `.step-side-panel-omitted` |

### 지어내지 않는 선

추론 구간에 적는 것은 **우리가 관측한 간격**(도구가 결과를 돌려준 시각 ~ 다음 호출 도착)
뿐이다. `work_source='bridge-runtime'`, 사유 칸은 **비운다** — 그 AI 가 왜 그렇게 판단했는지는
우리가 모른다. 화면은 「내부 동작」 배지로 도구 단계와 구분해 그린다.

### 되돌리기

`_record_bridge_reasoning_gap` 호출 1줄을 지우면 R1 이 원복된다(단계는 append-only 라 기존
데이터에 영향 없음). R2 는 프런트 3함수 국소 변경이라 개별 revert 가능.

### 검증

컨테이너 pytest 전량 green (신규 서버 12건 + 프런트 구조 13건, 기존 계약 2건 갱신) ·
node 하네스 `verify_bridge_live_step_progress.mjs` 18/18 (뮤테이션 역검증 2종 포함) ·
codex 적대 리뷰 **P1 0건**, P2/P3 8건 중 6건 반영·2건 근거 기각.
## CHG-20260831T110000-runtime-caps-restore — 쓸 수 있는 모델·등급이 화면에서 사라졌다 (P0-AE)

**요구**: 연결된 내 AI 로 답할 때 쓸 모델·effort 가 확인되지 않는다. 사용자 재량대로 적용할 수
있게 하고, 지정된 값이 **실제 LLM 호출에 반영**되게 한다.

### 변경

| 파일 | 무엇 |
|---|---|
| `src/bridge_agent.py` | `_ask_json` 추출(1차·재질의 공용) · `_cli_help_text`·`_help_mentions_flag`·`_settle_effort_axis`·`_caps_axis_unsettled` 신규 · `_CAPS_EFFORT_PROMPT`·`_CAPS_AXIS_MIN_SEC`·`_CAPS_HELP_TIMEOUT_SEC` · `probe_runtime_caps` 가 축을 확정하고 `effort_probed` 표지를 남김 · `detect_runtimes` 가 미확정 캐시를 **축만** 재확정하고 새 결과가 캐시를 이김 · `sanitize_caps` 가 표지 보존 · `handle_one` 이 **반영된** 지정도 고지 |
| `static/agent/bridge_agent.py` | 배포 사본 동기화(byte-identical 계약) |
| `routers/conversations.py` | `requested_model=(model if model_explicit else None)` — 서버 alias 오염 차단 · 브리지 분기에서 **명시 선택만** 계정 기본값으로 저장 |
| `routers/system.py` | 카탈로그가 계정 기본값을 **지금 신고된 목록과 대조 후** `default_model`·`default_reasoning_level` 로 내려보냄 · 기본값 조회 실패를 자기 자리에서 삼켜 러너 목록을 지키지 않게 함 |
| `oauth_store.py` | `account_bridge_defaults` · `set_account_bridge_defaults`(None 축은 건드리지 않음) |
| `routers/_bootstrap_schema.py` | `WebAccounts.BridgeDefaultModel`·`BridgeDefaultEffort` 멱등 ALTER |
| `static/app/composer.js` | 등급 현재값 사슬에 계정 기본값 추가(로컬 미러 **뒤** — 방금 고른 값이 다른 기기 저장값에 밀리지 않게) |
| 테스트 4파일 | 회귀 25건 추가 + 기존 4건의 텍스트 window 취약성 교정 |

### 왜 이렇게 갈랐나

목록의 출처는 **연결된 AI** 라는 계약(사용자 결정)을 유지하면서 부분 응답을 복구해야 했다.
그래서 순서가 「다시 묻는다 → CLI 자신의 도움말로 확인한다 → 비운다」이다. 내장 표를 먼저
쓰면 그 표가 낡은 순간 고른 값이 조용히 무시되고, 그냥 비우면 실제로 되는 기능을 잃는다.

(플래그, 값 목록)은 **짝**으로만 채택한다. AI 가 준 플래그에 우리 표의 값을 붙이면 그 CLI 가
받지 않는 조합이 만들어지고, 그러면 화면은 반영된다고 말하는데 실행은 아닌 상태가 된다.

### 되돌리기

`AGENT_SERVER_LLM_ENABLED=1` 로 게이트를 열면 카탈로그는 종전 서버 목록으로 복원된다(불변).
축 복구만 끄려면 러너에서 `--refresh-caps` 없이 기존 `config.json` 을 쓰면 되고, 계정 기본값은
컬럼이 NULL 이면 종전과 동일하게 목록 첫 항목이 시작점이 된다(두 축 모두 폴백이 종전 동작).

## CHG-20260831T124500-ai-claude-feature-0043-wsl-scheme-handler — 핸들러를 «브라우저가 도는 OS» 에 등록

- **날짜**: 2026-08-31
- **REQ**: 사용자 라이브 제보 — "'내 AI 실행' 을 통해 연결을 시도했지만, 연결이 진행되지 않는것으로 확인되었습니다."
- **위험도**: Major (§12.3 — 사용자가 자기 머신에서 실행하는 설치 스크립트가 Windows 레지스트리
  HKCU 에 쓰게 된다. 관리자 권한 불요·사용자 범위·해제 명령 동반)
- **승인**: 사용자 결정 2026-08-31 (AskUserQuestion — "A+B 전부": 동작하게 만들되 실패 시 정직하게 강등)

### 원인 (라이브 실측)

| 관측 | 값 |
|---|---|
| Windows `HKCU\Software\Classes\mysql-ai-bridge` | **없음** |
| WSL `~/.local/share/applications/mysql-ai-bridge.desktop` | 있음 (08-31 10:03) + xdg-mime 기본값 설정됨 |
| 러너 | WSL `/home/claude-corp/.mysql-ai-bridge/` — 설치·동작 이력 있음, 현재 프로세스 없음 |
| 같은 계정 당일 토큰 4건 | `LastHeartbeatAt` **전부 NULL** (러너가 그 토큰을 집은 적 없음) |

`register_handler()` 가 `uname` 으로 갈라 **설치 셸이 도는 OS** 에 등록했다. 버튼을 누르는 주체는
셸이 아니라 **브라우저**다. 등록은 성공했고 스크립트는 "등록했습니다" 라고 말했고 Windows
브라우저는 그것을 보지 못했다 — 사용자는 동작한다고 믿고 눌렀고 아무 일도 일어나지 않았다.

### 변경 내용

- `bridge_setup.sh`
  - `is_wsl()` / `win_exe()` / `register_handler_windows()` 신규. WSL 이면 Windows HKCU 에
    스킴을 등록하고 핸들러가 `wsl.exe -d <배포판> -u <사용자> -- launch.sh "%1"` 로 되돌아온다.
  - 등록은 PowerShell **스크립트 파일**로 수행(WSL→Win32 인자 변환에서 따옴표가 먹히지 않게).
    쓰기 후 **조회로 사후검증**하고, 실패면 등록 성공으로 처리하지 않는다.
  - 보고 분기 `_handler_rc=3` 신설 — WSL 인데 Windows 등록 실패면 「등록했습니다」를 말하지
    않고 사유 + "버튼은 동작하지 않습니다" 를 낸다.
  - 생성되는 `launch.sh` 에 `bail()` — tty 에 붙어 있으면 오류 후 20초 붙잡는다(핸들러가 여는
    콘솔이 즉시 닫혀 오류가 사라지던 문제).
  - 해제 안내에 Windows 레지스트리 키 추가.
- `connect-modal.js`
  - `_launchRunner` 재작성 — hidden iframe → **최상위 이동**(클릭 핸들러 안에서 동기 실행),
    최대 30초(8회) 상태 재조회, 응답 없으면 실패로 강등 + 1단계 명령 강조·스크롤.
  - `refreshConnState()` 가 읽은 값을 반환(판정 단일화, 낡은 응답·실패는 `null`).
  - `_revealCommand()` — 스크롤 기준은 **상태 문구**(모달 맨 아래). 명령 기준으로 잡으면 방금
    띄운 실패 문구가 화면 밖에 남는다(PB-0008 실측).
- `search-audit.css` — `.connect-modal-code.is-attention` 강조.
- 서빙본 `static/agent/bridge_setup.sh` 동기화(사용자가 내려받는 것은 서빙본이고 체크섬도 거기서 난다).

### 실측 근거 (실 Windows + WSL)

- `-d "Ubuntu"` 형태는 **무동작**(wsl.exe 가 따옴표를 이름의 일부로 읽는다) · `-d Ubuntu` 는 3/3 기동.
- 크롬 hidden iframe 은 외부 프로그램 허용 판정에 **도달 흔적조차 없음**; `location.href` 는
  도달한다("Not allowed to launch … because a user gesture is required" 로그).
- 미등록 스킴을 최상위로 열어도 페이지는 그대로(URL·제목 불변) — iframe 을 쓰던 근거 소멸.
- 클릭에서 기동까지 4초는 부족, 8초에 3/3 성공 → 대기 창 30초.

## CHG-20260831T132500-ai-claude-feature-0043-live-steps-postdeploy — POST-DEPLOY 시각검증 증적

`CHG-20260831T113350-…` 의 라이브 검증. 배포본 `74e2672c` 실 Windows 브라우저(PB-0008)에서
페이지가 실제로 로드한 모듈 URL(`app.js?v=cb0480b0bd8e`)로 `import()` 해 **배포본과 같은
인스턴스**로 렌더를 확인했다. 코드 변경 0 — 증적 문서만.

- 추론 구간 91초가 카드에 붙는다(제보 ①) · 마지막 단계 「진행 중」 강조
- 총 단계 수 122 · 절단 고지 1줄 · 누적 미표시(제보 ② 잔여 층)
- 저장 답변 경로는 종전과 동일(무회귀)
- 미수행: 실 러너 end-to-end 왕복(무인 완결 불가) — 사유 명시

증적: `unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260831T113350-live-steps-reasoning-postdeploy.md`
캡처: `artifacts/pb0008-live-steps-reasoning/` (git 밖, §2)

## CHG-20260831T160000 — 콘솔 작업 위임 배선 (사용자 결정)

**무엇**: 관리 콘솔 LLM 기능의 위임 경로를 실제로 이었다 — 폴링 API(C6) · 조립부 뒤 위임
seam(C7a) · 프론트 대기/결과 채우기(C7b) · 러너 job 분기와 기능 신고(C10).

**이음매**: 네 기능 모두 `messages` 조립 **뒤**, LLM 호출 **앞** 한 지점. 조립부(스키마
grounding·제품 바인딩·필드 제약)를 그대로 재사용하고 여기서 프롬프트를 다시 쓰지 않는다.

**러너**: `kind='job'` 이면 대화 프레이밍(사내 DB 어시스턴트·제목 마커·답변 규약)을 씌우지
않는다 — 서버가 보낸 형식 요구와 충돌해 JSON 을 요구했는데 산문이 오는 것을 막는다.
`features`/`agent_version` 을 항상 신고하고 배치 동의는 `--batch` opt-in.

**개방한 종류**: `metadata_suggest`(text) · `metadata_bulk`(json) · `prompt_generate`(text).
`node_analysis`·`insight_summary`·`cluster_label` 은 반영 경로 미구현이라 `wired: False` —
그 상태에서 적재는 거절되고 조작면은 사유와 함께 비활성이다.

**되돌리기**: 게이트 1개 + `JOB_SPECS[...]["wired"]`.

## CHG-20260831T153000-ai-claude-feature-0043-wsl-postdeploy — POST-DEPLOY 증적 (코드 변경 0)

- **날짜**: 2026-08-31
- **위험도**: Minor (문서만)
- **내용**: `CHG-20260831T124500-…` 의 라이브 검증. 배포본 `b35fa376`(내 커밋 `f1f24f27` 포함
  확인) 에서 `[내 AI 실행]` 강등 경로를 실 Windows 브라우저로 재확인. web-a/b 이미지·
  `GIT_COMMIT` 일치 · healthz 200 · caddy `no upstreams available` 0건.
- **증적**: `docs/test-runs.d/TASK-20260831T124500-wsl-scheme-handler-postdeploy.md`

## CHG-20260831T161500-ai-claude-feature-0043-wsl-runner-survive — wsl.exe 가 러너를 거둬가던 것

- **날짜**: 2026-08-31
- **REQ**: 사용자 재제보 — "명령어 실행을 통해 러너를 상주시켰지만, '내 AI 실행' 과정을
  진행해도 연결이 진행되지 않았습니다."
- **위험도**: Minor (launch.sh 생성 템플릿 한 곳)

### 원인 (실측)

`CHG-20260831T124500-…` 로 Windows 핸들러 등록은 성공했다(로그: "Windows 쪽에 등록했습니다").
그런데 그 핸들러가 부르는 `launch.sh` 가 러너를 띄우고 **곧바로 끝나면 wsl.exe 가 그 자식까지
거둬간다**. 대조 실험:

| 실행 경로 | 결과 |
|---|---|
| `launch.sh` 직접 실행 | 러너 시작 2→3, 프로세스 생존 |
| `wsl.exe -- launch.sh` (원본) | 시작 3→3, **프로세스 없음** + 기존 러너도 pkill 로 소멸 |
| 같은 스크립트 + 부모가 `sleep 3` | 러너 생존, 「대기 시작」 도달 |
| `setsid` / stdin `< /dev/null` (부모 즉시 종료) | 둘 다 **실패** |

### 변경

`launch.sh` 가 러너를 띄운 뒤 ①생존 ②로그 증가 ③최소 3초를 모두 확인할 때까지(상한 30초)
기다린 뒤 종료한다. 죽었으면 `bail` 로 사유를 말하고 콘솔을 붙잡는다. stdin 도 `/dev/null`
로 끊는다(단독으로는 무효였지만 데몬화 위생).

### 검증

- 생성된 `launch.sh` 를 실제 `wsl.exe` 로 호출: 러너 0→1, 20초 뒤에도 생존,
  `/api/ai/connect/status` 가 `listening:true` · `ready:true`
- 회귀 2건(L12 대기 계약 · L13 사망 보고) — **수정 전 스크립트에서 2/2 FAIL** 실증
## CHG-20260831T170000-model-tree — 없는 모델을 보여주던 폴백 + 플랫폼 그룹 트리 (P0-AF)

**요구**: 실제 가용하지 않은 codex 모델(`gpt-5.1-*`)이 목록에 뜬다 · 플랫폼별 그룹 트리 ·
답변 본문에 모델·등급을 쓰지 않는다.

### 변경

| 파일 | 무엇 |
|---|---|
| `src/bridge_agent.py` | 폴백에서 **모델 목록 제거**(호출법만) · probe 재시도 1회(`attempts * 2`) · codex 내장 표 실측 세대로 갱신 · `handle_one` 의 반영 고지 삭제(미반영 고지는 유지) |
| `static/agent/bridge_agent.py` | 배포 사본 동기화 |
| `static/app/composer.js` | `_renderComposerModelMenu` 를 그룹 트리로(머리글 + 하위 항목) · 트리에서는 그룹 배지 생략 · 그룹 없으면 종전 flat |
| `static/css/chat.css` | `.composer-model-group-head` (작고 흐린 비선택 줄) + 하위 항목 들여쓰기 |
| 테스트 2파일 | 신규 7건(폴백 부재·ollama 예외·호출법 생존·재시도·세대 갱신·그룹 트리·머리글 스타일) + 기존 5건 갱신 |

### 왜 폴백을 없앴나

「목록의 출처는 연결된 AI」가 이 기능의 계약인데, 폴백이 그 계약을 뒷문으로 깨고 있었다.
물어보지 못했으면 **모른다고 하는 편이** 틀린 목록을 확신 있게 보여주는 것보다 낫다 —
후자는 사용자가 없는 모델을 고르고, CLI 가 거부하거나 조용히 다른 모델로 답한다.

잃는 것(첫 연결에서 probe 가 실패하면 그 그룹이 안 보인다)은 재시도와 캐시가 메운다.
한 번 성공하면 저장되므로 반복 사용자에게는 영향이 없다.

### 되돌리기

`_RUNTIME_SPECS` 의 `models` 는 그대로 있다 — `detect_runtimes` 의 폴백 블록에서 다시 읽게
하면 종전 동작으로 돌아간다(권장하지 않는다: 그 표가 낡는 순간 같은 결함이 재발한다).
## CHG-20260831T170034-ai-claude-feature-0043-live-steps-compact — 추론 구간 표시 밀도 + 실시간 누적

**요청 (2026-08-31, 직전 cycle 확인 후)**: ① 「추론 구간이 … 사이드 바 내부에서 비교적 큰 범위를
차지 … 최대한 단순한 형태로. 외곽선 및 배경 없이 한 줄로 출력되어도 문제없습니다. 목적 자체는
추론에 대한 소요시간을 확보하는 것」 ② 「최하단의 누적시간은 실시간으로 갱신 (단순히, 첫
호출시간과 현재시간의 차이로)」 ③ 「'▼ 쿼리결과' 버튼을 통해 확장되는 리스트에서 추론 구간은
의미있는 정보가 없는 것으로 확인되었으니, 출력하지 않도록」.

③ 은 **직전 cycle 이 만든 회귀**다 — 단계 수를 2배로 늘려 놓고 소요 칸이 없는 목록에도 그대로
흘려보냈다. SQL 단계가 별도 블록으로 빠지는 탓에 남은 내부 동작 문구들이 서로 인접해 같은 문장이
연달아 쌓였다(제보 화면 ×8).

### 변경

| 파일 | symbol | 무엇 |
|---|---|---|
| `static/app.js` | `_buildStepActivityRow` (신규) | 내부 동작 = **한 줄** 행(번호·문구·소요). 카드 컨테이너·배지·제목 블록 없음. 시작 시각·사유는 `title` |
| ″ | `_stepPanelTicker`·`_paintStepPanelLiveTimes`·`_liveDurEl` (신규) | `[data-live-from]` 요소의 **텍스트만** 1초마다 `지금 − 기준시각` 으로 갱신. 대상 없음/패널 닫힘이면 자기 정지 |
| ″ | `_renderStepSidePanelBody` | activity 분기 · 최하단 실시간 누적 기준점(첫 단계 기록 시각) · 진행 중 경과 티커 · 티커 起停 |
| ″ | `closeStepSidePanel` | 티커 정리 |
| `static/app/messages.js` | `bubbleVisibleSteps` (신규) · `renderMessageDetails` · `buildStepBlocks` | 말풍선 목록에서 내부 동작 제외. **여닫이 존재 판정도 같은 집합** — 전량이 내부 동작인 시점의 빈 확장 방지 |
| `static/css/chat.css` | `.step-side-panel-activity` | flex 한 줄(`nowrap` + `ellipsis`), border·background 없음 |

### 정보를 없애지 않는다

말풍선에서 뺀 내부 동작은 **「단계 보기」 사이드 패널에 그대로 있다**(거기에는 소요 칸이 있고,
그게 이 행의 존재 이유다). 한 줄로 접은 시작 시각·사유도 `title` 로 남는다 — 지운 게 아니라
접었다.

### 되돌리기

`_buildStepActivityRow` 분기 1개(`app.js`)와 `bubbleVisibleSteps` 필터 1개(`messages.js`)를
제거하면 직전 표시로 복귀한다. 티커는 `[data-live-from]` 이 없으면 애초에 돌지 않는다.

### 검증

컨테이너 pytest 전량 green(신규 12건) · node 하네스 18/18 무회귀 ·
codex 적대 리뷰 2R **P1 0건 수렴**(1R P2 2·P3 1 전건 반영) ·
PB-0008 실 Windows 브라우저 POST-DEPLOY.
## CHG-20260831T190000 — 위임 결과 각인 래퍼 노출 수정 (라이브 제보)

**무엇**: 콘솔 작업 폴링이 각인본(`WebAiTasks.Answer`)을 화면에 그대로 줘서
`⟦UNTRUSTED-DATA⟧ …` 래퍼가 폼 입력란에 들어갔다. 원문을 `JobResult` 로 따로 보존하고
폴링이 그것을 준다(과거 행은 `unwrap_external_answer` 폴백).

**왜 저장본을 나누나**: `Answer` 는 감사 보존 + 지연 인젝션 방어용이라 각인이 필요하고,
화면은 사람이 읽을 원문이 필요하다 — 대화 경로가 이미 같은 이유로 나눠 두고 있었다.

**되돌리기**: 컬럼은 비파괴 ADD. revert 시 폴백 경로가 과거 행을 그대로 처리한다.
## CHG-20260831T164500-ai-claude-feature-0043-setup-speed-logts — 등록 80초→0.7초 + 로그 시각

- **날짜**: 2026-08-31
- **REQ**: 사용자 제보 — "'러너 체크섬 일치.' 이후로 핸들러를 등록하는 부분의 시간이 너무
  오래 소요" · "로그 내 타임스탬프가 기록되도록"
- **위험도**: Minor (등록 경로 최적화 + 로그 포맷)

### 원인 (단계별 실측)

| 단계 | 소요 |
|---|---|
| `powershell -File` (**WSL UNC 경로**) | **80.27s** |
| `powershell -File` (Windows 로컬 경로) | 0.41s |
| `wsl.exe -l -q` · `wslpath` · `reg.exe` | < 0.1s |

부하 시엔 Windows exe **기동 자체가 3.0~3.4초**라, 3회 호출(TEMP 조회·등록·검증)이 그대로 쌓였다.

### 변경

- 등록 PS1 을 **Windows `%TEMP%`** 에 쓰고 그 Windows 경로로 실행 (UNC 해석 제거)
- TEMP 는 `PATH` 의 `/mnt/<드라이브>/Users/<사용자>/…` 에서 떼어 얻는다(Windows 호출 0회).
  못 얻으면 그때만 `cmd.exe` 1회. 둘 다 실패하면 종전 경로 + "느립니다" 고지
- 별도 `Test-Path` 검증 제거 — 등록 PS1 이 **되읽어 대조하고 throw** 하므로 보장은 동일
- `say`/`die`/`drop`(설치) · `_log`(러너) · `bail`·완료 문구(핸들러 실행) 에 시각 추가

### 검증

- **80.27초 → 0.73초** (라이브, 사용자 셸과 같은 PATH). 등록값 정확·임시파일 잔재 0
- 회귀 3건(L14 로컬 경로 · L15 기동 1회 · L16 시각) — **수정 전 스크립트에서 3/3 FAIL** 실증

## CHG-20260831T172000-ai-claude-feature-0043-ps1-bom — Windows PowerShell 경로 파싱 실패

- **날짜**: 2026-08-31
- **REQ**: 사용자 제보 — PowerShell 에서 설치 시 `식에 닫는 ')'가 없습니다` 외 파싱 오류 6건
- **위험도**: Minor (인코딩 표식 + 게이트 교정)

### 원인

Windows PowerShell 5.1 은 BOM 없는 `.ps1` 을 **시스템 ANSI 코드페이지**(CP949)로 읽는다.
한글 주석·메시지가 깨지고 깨진 바이트가 인접한 `'`·`)` 를 삼켜 파서가 죽었다.

| 대상 | 결과 |
|---|---|
| 서빙본(BOM 없음) | `ParseFile` **오류 6건** |
| BOM 추가본 | **PARSE OK**, `U+B7EC`(러) 정상 디코딩 |

**게이트가 두 겹으로 놓쳤다**: 기존 `test_windows_installer_parses` 는 ① `pwsh` 미설치라 항상
skip 이었고 ② 설령 돌아도 **PowerShell 7 은 BOM 없이도 UTF-8 로 읽어** 이 클래스를 못 본다.

### 변경

- `bridge_setup.ps1` 정본·서빙본에 UTF-8 BOM + 상단에 「BOM 없이 저장하면 재발」 경고
- 설치 중 생성하는 등록 PS1 도 `printf '\357\273\277'` 로 BOM 선행 후 append
- 회귀 2건: BOM 바이트 직접 검사 · 생성물의 BOM 선행 순서 검사. 기존 pwsh 검사에는
  「이 축은 여기서 안 잡힌다」를 명시

### 검증

- Windows PowerShell 5.1 실파싱 PARSE OK · 코드포인트 대조로 디코딩 정합 확인
- 신규 2건이 **수정 전 상태에서 2/2 FAIL** 실증 · 등록 왕복 재확인 PASS

## CHG-20260831T180000-ai-claude-feature-0043-ps-python-probe — Store 스텁이 설치를 죽이던 것

- **날짜**: 2026-08-31
- **REQ**: 사용자 제보 — `python3.exe : Python` / `NativeCommandError` 로 설치 중단
- **위험도**: Minor

### 원인

`WindowsApps\python3.exe` 는 Microsoft Store 로 보내는 **2바이트 스텁**이다. 실행 시 stderr 로
`Python` 을 뱉고, `$ErrorActionPreference='Stop'` 에서 그것이 **NativeCommandError 로 던져진다**
(`2>$null` 무효). 첫 후보에서 죽어 **진짜 파이썬(`Python314\python.exe`)까지 가지 못했다.**

### 변경

- `Test-PyOk`: `Source` 가 `\WindowsApps\` 면 후보 제외 · 네이티브 호출만 `SilentlyContinue`
  + `try/catch` (전역 Stop 유지)
- 못 찾았을 때 안내를 실행 가능하게 (설치 링크 · `BRIDGE_PROBED_PY` · 스텁이 파이썬이 아님)

### 검증

- 실 Windows PowerShell 5.1: `python3 ok=False` → `python ok=True` → 예외 없이 완주
- 회귀 2건 · 수정 전에서 FAIL 실증

## CHG-20260831T173600-ai-claude-feature-0043-compact-evidence — 표시 밀도 조정 POST-DEPLOY 증적

`CHG-20260831T170034-…` 의 라이브 검증. 코드 변경 0 — 증적 문서만.

배포본이 **실제로 서빙하는 모듈**에 이번 변경 식별자가 있는지 먼저 대조한 뒤(app.js 7 hits ·
messages.js 3 hits), 페이지가 로드한 그 URL 로 `import()` 해 같은 인스턴스로 렌더했다.

- ① 내부 동작 행 **22px**(도구 카드 121px) · `border: none` · `background: transparent` · 배지 0
- ② 누적 3.2초 간격 3회 판독에서 증가폭이 경과와 일치(`지금 − 첫 단계 기록 시각`)
- ③ 말풍선 「쿼리 결과」 목록에 내부 동작 0건 — 제보의 반복 문구 ×8 소멸
- ④ 내부 동작만 있는 시점 → 여닫이 자체가 생기지 않음(빈 확장 없음)
- ⑤ 완료 답변 패널 → 티커 대상 0 · 2.6초 후 값 동일(정지 화면)

⚠ 이번 랜딩은 **GitHub Actions 를 게이트에서 제외**했다 — 07:50 이후 main 포함 전 실행이 계정
결제/한도로 러너 시작 전 실패(사용자 결정). 대체 근거는 CI 와 동일 스위트를 머지 base 에서
컨테이너 실행한 전량 green.

증적: `unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260831T170034-live-steps-compact-postdeploy.md`
캡처: `artifacts/pb0008-live-steps-compact/` (git 밖, §2)

## CHG-20260831T190000-ai-claude-feature-0043-python-autoinstall — 파이썬 설치 마찰 제거 (안 C)

- **날짜**: 2026-08-31
- **REQ**: 사용자 요청 — "최대한 종속 이슈를 제거… 개발자 외 일반 사용자도 사용할 수 있도록"
- **승인**: 사용자 결정 2026-08-31 (AskUserQuestion — **«C. 설치 마찰만 제거»**)
- **위험도**: Major (사용자 머신에 소프트웨어를 설치한다 — 동의 절차를 함께 넣어 완화)

### 근거가 된 실측 (스톡 Windows)

| 런타임 | 존재 |
|---|---|
| PowerShell 5.1 · .NET 4.x · `curl.exe` · `tar.exe` | **항상** |
| `winget` (App Installer 1.29.290) | **있음** |
| `node`/`npm` · `python` | **없음** |

러너는 표준 라이브러리만 쓴다(pip 의존 0) — 남은 종속은 «파이썬 런타임 유무» 하나였다.

### 변경 (`bridge_setup.ps1`)

- `Test-WingetOk` — 존재가 아니라 `--version` 실행으로 판정(스텁 방어, 파이썬에서 배운 축)
- 파이썬 미발견 시: 동의(`y/N`) → `winget install --id Python.Python.3.12 --exact --scope user
  --silent --accept-{package,source}-agreements --disable-interactivity`.
  `--scope user` 거부 환경 대비 1회 재시도
- `Update-PathFromRegistry` + 재탐지 + 표준 설치 위치 폴백
- 실패 시 안내를 winget 유무에 맞춰 분기

### 검증

- 실 Windows PowerShell 5.1: 파싱 PASS(BOM 보존) · `Test-WingetOk=True` ·
  `Update-PathFromRegistry` 예외 없음(PATH 1784→1824) · `Test-PyOk python3=False`(스텁) / `python=True`
- `winget show --id Python.Python.3.12 --accept-source-agreements` → rc=0, 3.12.10 확인
- 회귀 4건 — **수정 전에서 4/4 FAIL** 실증
- ⚠ **실제 설치는 실행하지 않았다** — 이 머신엔 이미 파이썬이 있고, 검증을 위해 남의 머신
  상태를 바꾸지 않는다. 설치 명령의 유효성은 `winget show` 로, 배선은 회귀로 확인했다.
## CHG-20260831T183000-runner-version-sync — 러너 지문 대조 + 연결 직후 카탈로그 갱신 (P0-AG)

**요구**: 재설치·재연결해도 옛 모델 목록이 그대로다 · 연결 완수 후 모델·추론 강도가 안 보이고
새로고침해야 나타난다.

### 변경

| 파일 | 무엇 |
|---|---|
| `src/bridge_agent.py` | `_self_build()` 신규(자기 파일 sha256 12자) · 하트비트에 `agent_build` · 응답의 `stale_build` 를 **세션당 한 번** 로그로 |
| `static/agent/bridge_agent.py` | 배포 사본 동기화 |
| `routers/_bootstrap_schema.py` | `WebOAuthTokens.RunnerBuild VARCHAR(16)` 멱등 ALTER |
| `oauth_store.py` | `set_runner_report(agent_build=…)` 저장(모양 강제 + 값 변경 시에만 쓰기) · `account_runner_build()` 조회 |
| `routers/ai_tools.py` | `_deployed_runner_build()`(배포본 지문, 프로세스 1회 캐시) · `_runner_update_hint(…, agent_build)` 에 `stale_build` |
| `routers/oauth_as.py` | `connect_status` 에 `runner_stale` — 서버가 판정하고 프런트는 불리언 하나만 읽는다 |
| `static/app/connect-modal.js` | 칩 4번째 상태 `stale` |
| `static/css/search-audit.css` | `.ai-conn[data-state="stale"]` |
| `static/app.js` | 게이트 변화 시 `loadVaultOptions()` → `renderComposer()` → 선택기 재렌더 (순서 고정) |

### 왜 버전만으로 부족했나

`AGENT_VERSION` 은 날짜 단위(`2026.08.31`)다. 그날 러너가 **세 번** 바뀌었고 셋 다 같은 버전이라
"배포본과 다른 러너" 를 표현할 축이 없었다. 지문은 그 질문에만 답한다 — 버전(호환성)과 지문
(동일성)은 서로를 대체하지 않으므로 둘 다 신고한다.

양쪽 지문을 다 아는 경우에만 판정한다. 구 러너는 지문을 아예 신고하지 않고, 그때 "다르다" 고
말할 근거는 없다(모르는 것을 경고로 바꾸지 않는다).

### 되돌리기

`RunnerBuild` 가 NULL 이면 대조가 서지 않아 종전과 동일하게 동작한다(경고 없음).
게이트 콜백은 `loadVaultOptions()` 호출만 빼면 종전 동기 렌더로 돌아간다.
## CHG-20260831T175500-ai-claude-corp-feature-0043-schannel-revocation — Windows 러너 수신 실패 + 같은 구간의 조용한 결함 3종

- **날짜**: 2026-08-31
- **REQ**: 사용자 제보 — "powershell 을 통해 해당 서비스를 연결할 경우 아래와 같은 이슈"
  (`curl: (60) schannel: CertGetCertificateChain trust error CERT_TRUST_REVOCATION_STATUS_UNKNOWN`)
- **위험도**: Major (TLS 신뢰 평가 경로를 건드린다 — 완화 범위를 폐기검사로 한정하고 대조군으로 실증)

### 근본 원인 (실측)

| 확인 항목 | 실측 결과 |
|---|---|
| 윈도우 기본 curl | `curl 8.13.0 (Windows) libcurl/8.13.0 **Schannel**` |
| 사내 root CA 확장 | CRL Distribution Points **부재** · Authority Information Access(OCSP) **부재** |
| 엣지 leaf 인증서 | 동일 — 폐기 정보 배포점 부재 |
| `--cacert` 만 | `curl: (60) … CERT_TRUST_REVOCATION_STATUS_UNKNOWN` (rc=60) |
| `--ssl-revoke-best-effort` 추가 | **rc=0**, 162,942 bytes 수신, SHA256 일치 |

Schannel 의 `CertGetCertificateChain` 은 체인을 세운 **뒤** 폐기 상태를 조회한다. 조회할 곳이
없으면 «알 수 없음» 이고 curl 은 그것을 하드 실패로 본다 — CA 신뢰 실패도 네트워크 실패도 아니다.
POSIX 판은 OpenSSL curl 이라 폐기검사를 기본으로 하지 않아 이 결함이 없다(**Windows 전용**).

### 변경 (`bridge_setup.ps1` 정본 + 서빙본, 바이트 동일)

- `Get-CurlRevokeArgs` — `--ssl-revoke-best-effort` → `--ssl-no-revoke` 순으로 **감지 후** 채택.
  감지는 네트워크를 타지 않는다(모르는 옵션이면 curl 이 파싱 단계에서 exit 2 → `--version` 판정).
  좁은 쪽을 먼저 쓰는 이유: 후자는 폐기검사를 통째로 끄고, 전자는 **CRL 에 닿아 revoked 면 여전히 멈춘다**.
- `Get-RemoteFile` — 러너 수신의 **단일 경로**. curl(`--cacert`) → 파이썬(`cafile`, **러너와 같은
  신뢰 앵커**). 종전에는 최초 수신과 체크섬 재시도가 각자 구현이었고, 다운로드는 Schannel·러너
  상주는 파이썬 TLS 로 **평가기가 둘**이었다(이번 결함이 그 갈라짐이다).
- `Invoke-NativeCapture` — 종료코드 + stderr 원문 회수. `Test-Downloaded` — 수신 실물 확인.
- 실패 시 시도한 **모든 경로의 사유**를 모아 낸다. 안내문이 폐기검사 문제를 지목한다.

### 같은 구간에서 함께 닫은 «조용한» 결함 3종

| 결함 | 실측 증상 | 조치 |
|---|---|---|
| 체크섬 재시도 실패 미검사 | 재시도 실패 후 낡은 파일이 남고 다음 대조가 "체크섬이 다릅니다" 로 **오진** | 재시도도 `Get-RemoteFile` 사용 + try/catch (POSIX 판은 `\|\| die` 로 무사했다) |
| 실행 실패의 fail-open | 없는 파이썬 경로로 불렀는데 `via=python` **성공 반환**(파일 없음) — `$LASTEXITCODE` 초기값 0 | 초기값 **127** + 성공 반환을 `Test-Downloaded` 로 보호 |
| 실패 사유 유실 | curl exit 60 인데 회수 길이 **0** — `SilentlyContinue` 가 stderr ErrorRecord 를 버린다 | `Continue` + ErrorRecord 원문만 추출(장식은 로케일 의존) |

### 변경 (`bridge_setup.sh` 정본 + 서빙본, 주석만)

- 러너 절에 **의도된 divergence** 주석 — 왜 여기엔 그 옵션이 없는지. 설명 없는 비대칭은
  parity 를 맞추려는 다음 변경이 되돌린다.

### 제가 만들었다가 되돌린 것 (정직 기록)

초안은 `Invoke-WebRequest` 를 «curl·파이썬 실패 시» 폴백으로 넓혔다. 실측에서 그것이
**무관한 CA 를 pin 해도 러너 수신을 성공**시켰다 — IWR 은 `$CaPath` 를 보지 않고 OS 신뢰
저장소로 검증하고, 이 머신에는 사내 CA 가 `CurrentUser\Root`·`LocalMachine\Root` 에 있었다.
신뢰 실패가 조용한 성공이 되는 경로였다. 제거했다 — 종전 코드의 IWR 은 «curl 부재 시» 에만
있었고 그 자리는 파이썬이 대신한다(pin 을 지키고, 앞 단계에서 3.8+ 를 이미 확보했다).

### 검증

- 실 Windows PowerShell 5.1(`5.1.19041.6456`): `ParseFile` **오류 0건**, `U+B7EC` 디코딩 OK
- 실 Windows 동작 매트릭스 A~G — 감지 `--ssl-revoke-best-effort` / 정상 `via=curl` sha OK /
  옵션 없음(수정 전 재현) `via=python` sha OK / curl 부재 `via=python` sha OK /
  **무관한 CA → 실패**(`CERT_TRUST_IS_UNTRUSTED_ROOT` + `CERTIFICATE_VERIFY_FAILED`) /
  파이썬 불가 → 실패 사유에 `CERT_TRUST_REVOCATION_STATUS_UNKNOWN` 실림 / 임시파일 잔재 0
- 회귀 `test_windows_tls_revocation.py` **18건** — 수정 전 코드에서 **13/18 FAIL** 실증(§16.7 G11-b)
- `_ps_code` 주석 스트리퍼를 실 PowerShell `[PSParser]::Tokenize`(토큰 2,602 · 오류 0)와 대조 검증
## CHG-20260831T175800-ai-claude-feature-0043-details-scroll-panel — 상세를 자기 스크롤 패널로 + 페이징 시 패널 내부 이동

**요청 (2026-08-31)**: 「'▼ 쿼리 결과'의 내용이 너무 길어질 경우에는 페이지 내 스크롤이 과도하게
길어지는 경향이 확인되었고 정작 중요한 쿼리데이터 결과셋이 밀려버리는 이슈 … 말풍선 내 별도의
스크롤 패널 내부에서만 렌더되도록 구성하고(최대 높이는 고정. 최소 높이는 제한 없음.),
쿼리데이터 결과셋을 페이징 할 때 마다 해당 위치로 내부 패널의 스크롤이 이동되도록」.

**원인**: `.message-details-body` 는 단계 목록 + SQL 패널 + 결과 표를 모두 쌓는데 **높이 상한이
없었다**. 상세를 펼치는 순간 페이지가 그만큼 길어지고, 정작 결과셋은 화면 밖으로 밀렸다.
게다가 `sql-navigator` 의 높이보존 floor(`minHeight`)가 가장 큰 패널 높이로 고정돼 짧은
결과셋으로 넘겨도 컨테이너가 줄지 않아 그 길이가 유지됐다.

### 변경

| 파일 | 무엇 |
|---|---|
| `static/css/chat.css` | `.message-details-body` → `max-height: min(70vh,680px)` + `overflow-y:auto` + `overscroll-behavior:contain` (min-height 미지정) · `.message-details-body .result-table-wrap` → `min(46vh,380px)` 로 **패널보다 좁힘** |
| `static/app/messages.js` | `revealInPanel` 신규 — 자기 패널 `scrollTop` 만 계산해 결과셋을 상단으로. 전환 경로를 `pageTo` 한 곳으로 합쳐 ◀▶·키보드가 모두 거치게. `focus({preventScroll:true})` |
| `static/app/composer.js` | 진행 중 재구성 시 내부 스크롤 보존(직전 rAF 취소 + `scrollTop===0` 일 때만) |

### 지켠 선

- **`scrollIntoView` 금지** — 조상 스크롤러 전부를 움직여 대화 로그와 페이지를 끌고 간다.
  이 cycle 이 없애려는 증상이 바로 그것이라, 자기 패널의 `scrollTop` 만 옮긴다.
- **패널 밖 인라인 표의 전역 상한은 불변** — 거긴 바깥 스크롤러가 없으므로 좁힐 이유가 없다.
- **사용자 조작과 다투지 않는다** — 복원은 패널이 아직 `scrollTop === 0` 일 때만.

### 되돌리기

CSS 두 규칙(`max-height`/`overflow-y` + 스코프 표 상한)을 지우면 종전 무제한 높이로 복귀한다.
`revealInPanel` 은 `pageTo` 안 3줄, 스크롤 보존은 `_renderBridgeSteps` 안 국소 블록이다.

### 검증

컨테이너 pytest 전량 green(신규 10건 — 패널 상한·중첩 방지 대소 불변식·reveal 배선·focus·
스크롤 보존) · node 하네스 18/18 무회귀 · codex 적대 리뷰 2R **P1 0건 수렴**(1R P2 3건 전건 반영)
· PB-0008 실 Windows 브라우저 POST-DEPLOY.

**관측된 flake(무관)**: `feature-0014 test_edge_rolling_gate.py::test_g3b_…` 가 부하 중 1회
타이밍 실패(2.0087s < 3s). 격리 재실행 3/3 PASS, 본 diff 는 feature-0014 파일을 0건 건드린다.
## CHG-20260831T184200-ai-claude-corp-feature-0043-schannel-postdeploy — POST-DEPLOY 라이브 검증 기록 (문서 전용)

- **날짜**: 2026-08-31
- **REQ**: §16.3 deploy-backed 완료 기준 — push/merge 는 코드 완료이지 배포 완료가 아니다
- **위험도**: Minor (문서 전용 — 코드 변경 0건)

`CHG-20260831T175500-…` 의 배포(`b28c3fab`) 후, **사용자가 실제로 내려받는 배포본 바이트**로
같은 시나리오를 재현한 증적을 적재한다. 배포 전 실측은 워킹트리 사본이었으므로 별 기록이다.

- `via=curl` 수신 성공(167,906 bytes) — 폴백이 아니라 **curl 경로 자체가 살아났다**
- main 정본 · 라이브 서빙본 · Windows 수신본 **3자 SHA256 일치**(`f38b984d…`)
- 무관한 CA 대조군은 배포본에서도 실패 — pin 유지 재확인
- 양 replica `GIT_COMMIT=b28c3fab` + **replica 내부 파일 해시 동일**(롤링 캐시 함정 차단)
- 엣지 `/healthz` 200 · soak 통과 · caddy `no upstreams available` **0건** · RestartCount 0
- 자기정정 1건: 하네스 기대 해시가 배포 전 러너 값이라 `MISMATCH` 가 났고, 3자 대조로
  «상수 stale» 임을 확정했다(수신 실패 아님). 불일치를 WARN 으로 강등하지 않았다.

## CHG-20260831T190000-verify-anchor-fix — 침묵 처리 계약을 구조로 잠금 (P0-AG 후속)

**요구**: 직전 커밋에서 임시 디버그 로그를 제거하자 계약 테스트가 앵커 문자열을 잃고 깨졌다.

### 변경

| 파일 | 무엇 |
|---|---|
| `routers/oauth_as.py` | 침묵 처리 주석의 원인 서술 정정(예외가 아니라 상주 프로세스의 옛 모듈) |
| `tests/test_model_catalog_bridge_mode.py` | 앵커를 문자열에서 **`except` 블록 구조**로 — `runner_stale = False` 와 `exc_info=True` 가 그 블록 안에 함께 있는지 본다 |

### 왜

주석 한 줄을 고치면 깨지는 테스트는 계약을 지키는 것이 아니라 **글자를 지키는 것**이다.
잠글 것은 "판정 실패가 거짓 경고가 되지 않고, 그러면서 추적 가능하다" 이지 특정 문구가 아니다.

## CHG-20260831T191500-gatepoll-anchor — 선재 계약 테스트 실패 해소 (P0-AG 후속)

`test_indicator_does_not_poll_when_unlocked` 가 **main 에서도** 실패하고 있었다. #1447 이
`_syncGatePoll` 의 폴링 사유를 둘(`_composeBlocked || _modalOpen`)로 늘리면서 계약 테스트를
갱신하지 않았고, 테스트는 조건 문자열(`_composeBlocked && !_gatePollTimer`)을 박제하고 있었다.

잠글 것은 사유의 **개수**가 아니라 «사유가 없으면 멎는다» 이므로 그 성질을 본다 —
`wantPoll && !_gatePollTimer` / `!wantPoll && _gatePollTimer` 가 같은 값의 양면인지까지.

## CHG-20260831T194000-ai-claude-feature-0043-scrollpanel-evidence — 스크롤 패널 POST-DEPLOY 실측 증적

`CHG-20260831T175800-…` 의 라이브 검증. 코드 변경 0 — 증적 문서만.

배포본(`47299f6a`) 서빙 자산에 이번 변경이 도달했는지 먼저 대조(messages.js 9 hits ·
chat.css 2 hits) 후, 페이지가 로드한 모듈 URL 로 `import()` 해 실측했다.

- 패널 `clientHeight 622` / `scrollHeight 782` → 자기 스크롤 · `min-height: 0px`(제한 없음)
- 안쪽 표 `378px` < 패널 `622px` — 중첩 스크롤 함정 부재
- 페이징: 패널 `scrollTop 0 → 375`, **대화 로그·문서 스크롤 0 불변**
- 결과셋 위치: `navOffset 381 → 6px`(코드의 여백 상수와 일치, 최대 스크롤 577 아님 = clamp 아님)
- 키보드(`ArrowRight`) 동일 경로 · 짧은 상세(단계 1건) `81px` 비스크롤

캡처: `artifacts/pb0008-details-scroll-panel/` (git 밖, §2). 검증 DOM 은 제거 확인.

## CHG-20260901T101500-ai-claude-corp-feature-0043-ci-testpath-parity — CI 미등재 3디렉토리 등재 + 재발 클래스 구조 잠금

- **날짜**: 2026-09-01
- **REQ**: 사용자 결정 2026-09-01 (AskUserQuestion — «미등재 3디렉토리 등재»)
- **위험도**: Minor (CI 커버리지 확대 — 제품 코드 무변경)

### 무엇이 문제였나

`pytest.ini` 의 `testpaths` 는 **인자를 명시하면 무시된다.** `Makefile` `test` 와 `ci.yml` 이
각자 경로를 나열하므로 한쪽에만 추가하면 «로컬 green + CI 사각» 이 **아무 신호 없이** 생긴다.
실측(2026-09-01): `feature-0041` · `feature-0043` · `feature-0008` 이 Makefile 에만 있었다 —
즉 그 스위트들은 CI 에서 **한 번도 돈 적이 없다**. 직전 cycle 이 feature-0043 에 추가한 회귀
18건도 마찬가지였다.

### 왜 점수정으로 끝내지 않았나 (§16.7 G10)

같은 클래스가 **네 번째** 재발이다 — feature-0014·0020 → 0023 → 0041·0043·0008. 세 번째까지의
대응은 매번 «그 경로를 목록에 추가» 였고, ci.yml 에는 이미 이 함정을 경계하는 주석까지 있었다.
**주석이 있는 채로 세 번 더 반복됐다.** 재발 관측이 쌓였으므로 구조 테스트로 승격한다.

### 변경

- `.github/workflows/ci.yml` — pytest 목록에 3디렉토리 추가 + 「두 목록은 같은 집합이어야
  한다」 규약 주석
- `unit/feature-0043-external-llm-bridge/tests/test_ci_testpath_parity.py` (신규 5건) —
  `Makefile` `test` ↔ `ci.yml` 의 `unit/*/tests` **집합 동일성**을 단언. 파서가 0개를 뽑아
  `set()==set()` 로 항진 통과하는 것을 막는 sanity 단언 + 등재 3건 되돌림 방지 단언 포함.
  주석 라인을 제거하고 비교한다(두 파일 주석에 feature 이름이 등장 — §16.7 G11-a).

### 검증

- 신규 5건 **PASS** · **수정 전 `ci.yml`(HEAD) 사본에서 4/5 FAIL** 실증 (§16.7 G11-b)
- 등재한 3디렉토리는 직전 cycle 의 컨테이너 전수 실행에서 이미 `rc=0` (근거 선행 확보)
## CHG-20260901T110000-aiops-external-realign — 「AI 운영 현황」을 외부AI 운영축으로 전면 재편 + 외부 AI 자가 검증 구현

**요청 (2026-09-01)**: "assistant 가 작동하는 구조가 변경됨에 따라 '관리 콘솔 > AI 운영 현황'
내부의 **모든 작동 사항들은 외부AI 작동에 정합한 구조로** 변경해주세요. 이제 **내부 AI 는
사용하지 않습니다**."

### 근본 원인 — 지표가 침묵으로 거짓말하고 있었다

이 탭의 거의 모든 수치가 `agent_runtime.llm_usage`(서버 계정 호출) 출처였다. 게이트가 닫힌 뒤
그 원장에는 새 행이 쌓이지 않으므로 화면이 0 으로 수렴했고, 그 0 은 **"아무도 AI 를 안 쓴다"**
로 읽혔다 — 실제로는 우리가 세지 않는 곳(각자의 개인 AI)에서 쓰고 있었고, 우리 쪽에 남는
활동은 도구 호출과 브리지 작업이었다.

`LLM 제공자` 축은 더 나빴다. 아무도 그 경로를 쓰지 않는데 그 축의 `degraded` 가 종합 배너의
worst-of 에 참여해 **쓰지 않는 provider 의 제한 하나가 화면 전체를 '저하' 로 물들이고**,
운영자가 실제로 봐야 할 브리지 신호를 같은 색으로 덮었다.

그리고 콘솔은 **없는 기능을 있다고 말하고 있었다** — `_console_llm.INACTIVE_SURFACES` 의
"답변을 만든 본인 AI 가 같은 5축으로 자기 답변을 검증하고 결과를 함께 제출합니다" 에 해당하는
경로가 코드에 없었다(러너도, `submit_answer` 도, 저장 컬럼도). 확인할 방법이 없는 종류의
거짓이다 — 원장이 비어 있으면 "결함이 없었나 보다" 로 읽힌다.

### 사용자 결정 (AskUserQuestion 4문, 2026-09-01)

전면 재편 · 과거 지표는 「기록」으로 격리 · 신규 지표 3종(도구 사용량 · 브리지 작업 대기열 ·
러너 현황 상세) · **자가 검증 제출까지 구현**.

### 변경 — 서브탭 재편

| AS-IS | TO-BE |
|---|---|
| `[LLM 사용량 · 운영 현황 · 추론 · 외부 AI 작업]` | `[운영 현황 · 브리지 작업 · 도구 사용량 · 기록]` |

- `static/admin.html` — 4 subpane 재배치(기존 블록은 **본문 무수정 이동**). `usage`·`reasoning`
  pane 은 「기록」 안 접이식 섹션으로, 서버 활동 이력 섹션 신설
- `static/admin/tasks.js`(신규) — 브리지 작업 통합 원장. `exttasks.js` 흡수(삭제)
- `static/admin/tools.js`(신규) — `tool_call_usage` 집계
- `static/admin/aiops.js` — 브리지·자가검증 KPI 를 앞으로, 러너 명부 신설,
  `llm_usage` 3블록을 `serverActivityHtml()` 로 분리해 **운영 현황·기록이 같은 함수**를 부른다
- `static/admin.js` — 서브탭 키 재편 + `_AI_SUBTAB_ALIAS` 를 모듈 스코프로 올려
  `switchTab`·`activateAiConsoleSubtab` **두 진입점이 같은 표**를 읽게 함
- `css/admin.css` — `.admin-archive-section` (토큰만 사용)

### 변경 — 서버

- `routers/ai_ops.py` — `_provider_axis` 차단 시 `na`(롤업 제외, `raw_state` 는 보존) ·
  `_runner_roster` · `_self_review_stats` · 신규 `GET /api/admin/ai-ops/{tools,tasks,runners}` ·
  `_COVERAGE_EXTERNAL`(하지 않는 일을 '계측됨' 으로 나열하지 않는다)
- `oauth_store.py` — `list_live_runners()`. 계정 중복 제거를 **파이썬에서** 한다(상관 서브쿼리는
  술어 사본을 하나 더 만들고, MySQL 느슨한 GROUP BY 는 실재하지 않는 러너를 만든다)
- `routers/admin_usage.py` — 활동 피드 정본 위치 주석 정정(차단 배포에서는 '기록' 안)

### 변경 — 자가 검증(5축) 실구현

- `shared/self_review.py`(신규) — 축·심각도·상한·지시문·`sanitize` 의 **단일 정본**.
  지시문 전문을 서버가 `claim_request` 로 내려보낸다 — 러너에 축을 박으면 갱신하지 않은 러너가
  낡은 축의 판정을 같은 컬럼에 쓴다(스키마는 같고 의미만 갈리는 어긋남)
- `alembic 0057` — `redteam_reviews.source`(server/external, 기본 `server`) · `task_id` additive
- `routers/ai_tools.py` — `claim_request` 가 지시 하달, `submit_answer` 가 `review` 수용 →
  `_record_external_review()`. **검증 없는 제출은 거절하지 않는다**(구 러너 보호 — 관측을 위해
  서비스를 끊는 거래는 성립하지 않는다)
- `static/agent/bridge_agent.py` — `run_self_review()` · `--no-self-review` ·
  `AGENT_FEATURES` 에 `self_review` · `AGENT_VERSION` `2026.09.01`
- `shared/bridge_tasks.py` — `RUNNER_FEATURE_SELF_REVIEW`
- `routers/_console_llm.py` — 문구를 **구현 범위까지만** 정정(검증은 하되 자동 수정 반복은
  하지 않음 · 최소 추론 강도는 적용 불가) + `delegated_feature` 로 **기능 단위** 판정

### 지어내지 않는 규율 (이 변경의 핵심)

- 형태를 못 갖춘 리뷰 응답은 **기록하지 않는다** — 빈 `pass` 로 접으면 "검증했고 문제없었다"
  는 주장이 되는데, 실제로는 러너의 AI 가 JSON 을 못 냈을 뿐이다
- 「고치라」고 했는데 살아남은 지적이 0건이면(우리가 전부 버렸다) **역시 기록하지 않는다** —
  `pass` 로 접으면 결함을 지적한 검증이 통과로 기록된다
- 원장 미준비(`available:false`)와 0건을 **가른다** — 전자를 0 으로 그리면 마이그레이션 상태가
  운영 상태에 대한 거짓말이 된다
- 화면의 「검증 없음(`—`)」과 「통과」를 가르고, 러너 명부가 그 이유(`미지원`)를 말한다

### 검증

- `make test` 전량 **PASS** · ruff clean · migrate-lint **expand-safe** · ROUTEMAP 264 routes
- 신규 회귀 **54건** + 기존 계약 3건 갱신(축 정정 — 근거는 test-runs fragment §1)
- **PB-0008 실 Windows 브라우저**(bind-mount 격리, 라이브 무접촉) 9항목 전건 PASS.
  **자체 발견 1건**: 커버리지 문구의 마크다운 강조가 평문 렌더라 별표가 화면에 그대로 떴다
  (소스 검사로는 잡히지 않는 부류) — 제거 후 재확인
- 증적: `unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260901T110000-aiops-external-realign.md`

## CHG-20260901T152000-runner-roster-honesty — 조회 실패를 「러너 0대」로 단정하던 결함

앞 CHG 의 자체 적대 검토에서 나온 **P1 1건**.

`oauth_store.list_live_runners` 가 질의 실패를 `return []` 로 삼켰고, `_runner_roster` 는
그 빈 목록에 `available: True` 를 붙였다. 화면은 빈 목록을 **"연결된 개인 AI 가 없습니다 —
들어오는 질문을 아무도 처리하지 못합니다"** 라는 빨간 단정으로 그린다. 즉 **질의 하나가
실패하면 관제가 장애를 선언한다.**

이것이 나쁜 이유는 두 가지다:

1. **이 cycle 이 없애려던 결함과 같은 형태다** — 「모르는 것」을 「나쁜 사실」로 바꿔 말하는 것.
2. **그 함수의 docstring 이 계약을 정확히 적어 두고 있었다** ("빈 목록이지 '러너 없음' 이
   아니므로, 호출측이 그 차이를 화면에 표현한다"). 주석이 계약을 말하는데 코드가 지키지 않으면
   다음 사람은 주석을 읽고 지켜지는 줄 안다 — 가장 늦게 발견되는 부류다.

### 변경

- `oauth_store.list_live_runners` — 질의 실패를 **위로 올린다**. 호출측(`_runner_roster`)이
  이미 `except` 로 감싸 `available:False` + 사유를 화면에 표면화한다.
- 단 `RunnerBuild`(2026-08-31 추가) 부재는 **컬럼 사다리로 한 단계 내려간다** — 지문 대조는
  이 명부가 답하는 네 질문 중 하나일 뿐인데, 그것 하나로 구 배포에서 화면이 통째로 비면
  안 된다(`_query_activity` 가 `target`·`cache_*` 에 쓰는 것과 같은 규율).
- 지문을 모르면 `stale_build` 를 **False 로 둔다** — 모르는 것을 stale 로 적으면 멀쩡한
  러너에게 재설치를 시킨다.

### 검증

- 회귀 2건 (`test_runner_roster_query_failure_is_not_reported_as_zero_runners` ·
  `test_runner_roster_survives_missing_runner_build_column`)
- **역검증**: 직전 커밋(`33e00e0e`)의 `oauth_store.py` 를 되돌려 실행 → **둘 다 FAIL**.
  내가 만든 뮤턴트가 아니라 **실제 출하 직전 코드**에서 죽는 것을 확인했다(자기충족 아님).
- `make test` 전량 PASS · ruff clean
## CHG-20260901T104500-ai-claude-feature-0043-steps-result-split — 단계/결과셋 범위 분리 · 스크롤은 단계만

**요청 (2026-09-01)**: 「'▼ 쿼리 결과' 를 펼쳤을 때, 각 단계와 결과셋 범위를 분리해주세요.
스크롤 대상은 각 단계 뿐입니다.」

**원인**: 직전 cycle(2026-08-31)이 상세 본문 전체를 하나의 스크롤 패널로 만들었다. 페이지가
과도하게 늘어나는 증상은 잡혔지만 **정작 보려던 결과셋까지 그 스크롤 안에 갇혔다** — 단계가
많을수록 결과셋을 찾아 굴려야 했다. 상한을 **무한 성장의 주범(단계 목록)** 에만 걸었어야 했다.

### 변경

| 파일 | 무엇 |
|---|---|
| `css/chat.css` | `.message-details-body` 의 `max-height`·`overflow-y`·`overscroll-behavior` 제거(스크롤러 해제) · `.step-detail-list` 신규 규칙 = **유일한 스크롤 대상**(`min(38vh,300px)` · min-height 미지정 · contain) · 상세 안 결과 표를 좁히던 스코프 규칙 제거 |
| `app/messages.js` | 결과셋을 「쿼리 결과」 제목 블록(`.sql-result-group.is-result-range`)으로 분리 — 단일/복수 SQL 모두 같은 자리 · `revealInPanel`·`_scrollableHost`·`_NAV_REVEAL_MARGIN_PX` **제거**(아래) |
| `app/composer.js` | 진행 중 스크롤 보존 대상을 `.message-details-body` → `.step-detail-list` 로 이동 |

### 죽은 코드를 남기지 않는다

2026-08-31 의 「페이징 시 내부 패널 스크롤 이동」 요구는 이제 **구조가** 만족시킨다 — 결과
범위가 단계 목록(고정 상한) 바로 아래 **고정 위치**라 페이징해도 자리가 움직이지 않는다.
그 코드를 남기면 어떤 조상도 스크롤하지 않으므로 영구 no-op, 즉 「동작하는 척하는 죽은 코드」가
된다(codex 적대 리뷰 P2). 제거하되 **복원 조건**(결과 범위를 다시 스크롤러 안에 넣으면 되살릴 것)을
코드 주석과 회귀 테스트에 남겼다.

### 페이지 높이는 왜 다시 늘지 않는가

바깥 캡을 걷었지만 **각 부분이 자기 상한을 갖는다** — 단계 목록 `min(38vh,300px)` · SQL 블록
`min(40vh,320px)` · 결과 표 `min(60vh,460px)`(기본 접힘). 셋 중 하나라도 상한을 잃으면 그 부분이
페이지를 다시 밀어내므로, 회귀 테스트가 **셋을 함께** 잠근다. 원래 증상의 주범이던 「상한 없는
단계 목록」은 이제 300px 에서 멈춘다.

### 되돌리기

CSS 두 규칙(`.step-detail-list` 캡 / `.message-details-body` 캡 복원)과 `buildStepBlocks` 의
결과 블록 감싸기 3줄이 전부다.

### 검증

컨테이너 pytest 전량 green(신규·개정 13건) · node 하네스 18/18 무회귀 ·
codex 적대 리뷰 2R **P1 0건 수렴**(1R P2 2건 — 1건 반영·1건 근거 기각) ·
PB-0008 실 Windows 브라우저 POST-DEPLOY.
## CHG-20260901T110000-win-ai-detect — 설치된 AI 를 찾아낸다 (윈도우 확장자 · PATH 밖 · 축 분리)

### 무엇이 있었나

윈도우 사용자가 웹 콘솔의 [연결 명령 복사] 를 그대로 실행했더니 CA·체크섬·핸들러까지 전부
통과한 뒤 마지막 단계에서 멈췄다:

```
[bridge 2026-09-01 10:43:55] FATAL: 쓸 수 있는 AI 를 찾지 못했습니다. --ai 또는 --cmd 로 지정하세요.
[bridge-setup] 중단: 연결 확인에 실패했습니다. 토큰이 만료됐다면 …
```

그 머신에는 `C:\Users\<사용자>\.local\bin\claude.exe` 가 있었고, 직접 실행하면
`2.1.70 (Claude Code)` 를 답했다. **AI 는 있었다. 우리가 못 찾았을 뿐이다.**

### 세 겹이었다

1. **확장자** — `_which` 가 `os.path.join(d, name)` 만 봤다. 윈도우에 `claude` 라는 이름의
   파일은 없다(`claude.exe` 가 있다). PATH 에 있었어도 못 찾는다.
2. **PATH 밖** — Claude Code 의 윈도우 설치기가 쓰는 `%USERPROFILE%\.local\bin` 이 사용자
   PATH 에 없었다(`Get-Command claude` 도 실패). PATH 만 보는 한 어떤 구현도 못 찾는다.
3. **축 뒤엉킴** — AI 감지가 연결 확인 **앞**이라, 감지 실패가 「연결 확인에 실패했습니다.
   토큰이 만료됐다면…」 으로 보고됐다. 토큰도 CA 도 네트워크도 멀쩡한 사용자가 그 셋을 뒤진다.

### 무엇을 했나

**러너 (`bridge_agent.py`)**

- `_exec_exts` / `_is_exec` 신설 — 윈도우는 `PATHEXT` 중 우리가 `Popen` 으로 띄울 수 있는
  것만(`.exe`·`.cmd`·`.bat`·`.com`). 확장자 없는 파일은 목록에 없다 — npm 이 함께 까는 sh
  shim 은 `CreateProcess` 로 실행되지 않아, 채택하면 **감지는 성공하고 호출만 죽는다**.
  `os.curdir` 은 보지 않는다(윈도우 `shutil.which` 와 다른 점 — 러너를 띄운 폴더의 동명
  파일이 사용자의 AI 를 가로채지 않게).
- `_ai_install_dirs` / `_which_ai` 신설 — PATH 에 없으면 표준 설치 위치를 본다. 다만 그
  탐색은 **`_RUNTIME_SPECS` 에 있는 이름에만** 열린다. 임의 이름으로 홈 디렉토리를 뒤져
  실행하면, 오타나 서버가 준 값 하나가 의도한 적 없는 프로그램의 실행이 된다.
- `_resolve_exe` — 실행 choke-point 3곳(`_ask_json` · `_cli_help_text` ·
  `_run_cli_cancelable`)과 `_ensure_strict_mcp_supported` 에서 argv[0] 을 해석한다. 한 자리에
  모으지 않으면 「찾았다」와 「부를 수 있다」가 갈린다.
- `main()` 순서 재배치 — AI 감지는 실패해도 **끝내지 않고**, 연결 확인 뒤에 축별로 판정한다.
  `--check` 종료코드: `0` 둘 다 정상 / `1` 연결 실패 / `3` 토큰 무효 / **`4` 연결 정상 + AI 없음**.
- `_no_ai_message` — 사용자 대면 안내에서 `--ai`·`--cmd` 를 지웠다. 대신 무엇이 필요한지와
  **어디를 찾아봤는지**(PATH + 표준 위치 전부)를 적는다. 이번 사용자처럼 「설치는 했는데
  그 폴더가 목록에 없다」를 스스로 알아볼 수 있게 하는 것이 이 목록의 목적이다.

**설치 스크립트 (`bridge_setup.ps1` · `bridge_setup.sh`)**

- `Test-AiPresent` / `_ai_present` — 실존 검사가 러너와 **같은 범위**를 본다. 두 곳이 갈리면
  설치기는 「없다」 하고 러너는 「있다」 하는 상태가 되고, 사용자는 어느 쪽도 믿을 수 없다.
- `--check` 의 exit 4 를 **따로** 다룬다. 연결 정상인 사용자에게 토큰 만료를 말하지 않는다.
- Drop 문구에서 `BRIDGE_ARGS='--ai <이름>'` 안내 제거(사용자 결정: 옵션을 요구하지 않는다).

### 되돌리기

`_which_ai`/`_resolve_exe` 를 `_which` 로 되돌리고 `main()` 의 감지 블록을 연결 확인 앞으로
옮기면 종전 동작이다. 설치 스크립트는 exit 4 분기 삭제 + `command -v` / `Get-Command` 복원.

### 검증

실 Windows(PowerShell 5.1 + Python 3.14) 실측 — `Get-Command claude`=**False** 인 상태에서
`_which_ai`가 `claude.exe` 를 찾아내고 `claude --help` **7,436자** 수신(= PATH 밖 실행 파일이
정말 실행됐다). 신규 회귀 26건 green + **뮤테이션 3종 역검증 전건 대응**(확장자 미고려 /
표준 위치 탐색 제거 / 감지를 연결 앞으로 되돌리기 — 각각 정확히 해당 테스트만 죽었다).
컨테이너 전수 `make test` rc=0 · ruff clean · PS 5.1 ParseErrors 0 · BOM 보존.
증적: `docs/test-runs.d/TASK-20260901T110000-win-ai-detect.md`.

### codex 적대 리뷰 반영 (P1 1건 · P2 4건 — 전건 조치)

리뷰가 이 cycle 의 **방향 자체가 가진 위험**을 짚었다. 전부 「더 많이 찾는」 변경이라, 넓힌
만큼 새 경로가 열리거나 종전에 되던 것이 깨질 수 있었다.

- **[P1] 배치 shim 을 직접 실행 대상으로 삼았다.** `.cmd`·`.bat` 는 `CreateProcess` 가
  `cmd.exe` 로 넘겨 실행하므로 인자가 셸 파싱을 한 번 더 통과한다. 우리는 사용자 질문 본문을
  그대로 인자로 넘기므로 `shell=False` 로도 명령 주입 경로가 열린다. → `_WIN_EXEC_EXTS` 를
  `.exe`·`.com` 으로 좁혔다. npm 전역 설치는 감지에서 빠지지만 **회귀는 아니다**(수정 전에도
  못 찾았다). 설치 스크립트 양판도 같은 목록으로 맞췄다.
- **[P2] 확장자가 이미 붙은 이름을 늘렸다** — `my-ai.exe` → `my-ai.exe.exe`. `_name_candidates`
  로 이미 붙은 확장자를 존중하고, 경로 지목 분기에서도 확장자 후보를 시도한다.
- **[P2] `--ai <표 안 이름>` 이 실존 확인을 우회했다** — 파일이 없어도 `--check` 가 「사용할
  AI: claude」와 0 을 냈다. 선택 로직을 `pick_ai()` 로 분리하고 지목한 이름도 실재를 확인한다.
  없으면 **다른 AI 로 갈아치우지 않는다**(사용자가 세운 제한을 넘지 않는다).
- **[P2] 감지를 실제로는 연결 확인 뒤로 옮기지 않았다** — 즉시 반환만 없앴을 뿐이었다.
  `pick_ai()` 호출을 `api.call` 뒤로 실제 이동했고, 테스트가 호출 **순서**를 잠근다.
- **[P2] 설치 스크립트와 러너의 판정이 비대칭** — `PATHEXT` 를 거르는 데 쓰면 그것을 손댄
  머신에서 두 곳의 답이 갈린다. 순서만 참고하고 목록은 항상 전부 본다. `-PathType Leaf`(ps1) ·
  `-f`(sh) 로 동명 디렉터리도 배제.

신규 회귀 8건 추가(총 34건). 상세는 `REVIEW.md` REV-20260901T114500.

## CHG-20260901T120000-glossary-term-tier (cross-cut, 정본 feature-0002)

`src/bridge_agent.py`(러너 정본): 답변 동봉 `#GLOSSARY:` 한 줄 규약 추가 — 이 턴에서 정의가
분명해진 도메인 용어 후보를 `[{term, definition, tier, confidence}]` 로 싣는다.

**왜 별도 콘솔 작업이 아니라 답변 동봉인가**: red-team 을 같은 방식으로 처리한 선례와 동형
(사용자 결정 2026-08-31 — 「요청 당시의 호출자가 스스로의 대화내역을 알 수 있으므로」).
답한 그 AI 가 이미 맥락을 갖고 있어 **추가 LLM 호출이 0** 이고, 별도 task 로 만들면 대화를 한 번
더 넘기며 개인 계정 토큰을 두 번 태운다.

**additive** — 규약을 모르는 구 실행 파일은 `glossary_terms` 를 싣지 않고, 서버는 `None` 과
`[]` 를 구분해 「규약 미지원 러너」와 「담을 것이 없던 턴」을 로그에서 가른다. 파싱 실패·형식
위반은 **답변을 상하게 하지 않는다**(줄만 떼고 빈 목록).

배포본(`unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py`)과 byte-동치 유지.
## CHG-20260901T110500-ai-claude-feature-0043-split-evidence — 범위 분리 POST-DEPLOY 실측 증적

`CHG-20260901T104500-…` 의 라이브 검증. 코드 변경 0 — 증적 문서만.

배포본(`65641296`) 서빙 자산 도달 대조(messages.js `is-result-range` 1 · chat.css
`min(38vh,300px)` 1) 후, 페이지가 로드한 모듈 URL 로 `import()` 해 실측:

- `.step-detail-list` 300/631 **스크롤** · `.message-details-body` 1256/1256 **비스크롤**(overflow visible)
- 결과표 상한 460px(상세 전용 380 축소 제거 확인) · 두 범위 제목 `["단계","쿼리 결과"]`
- 페이징(▶·ArrowRight): 단계 목록·대화 로그·문서 scrollTop **전부 불변**, 결과 위치 424px 고정
- 상세 전체 1295px = 단계 323 + 결과 921 (부분 상한 합 안, 유계)

**정직 표기**: 종전 바깥 캡(680)보다 높다 — 결과셋을 스크롤에서 뺀 대가다. 조정 지점은
CSS 세 줄(단계 300 · SQL 320 · 결과표 460)이며 구조 변경 없이 바꿀 수 있다.

캡처: `artifacts/pb0008-steps-result-split/` (git 밖, §2). 검증 DOM 제거 확인.

## CHG-20260901T121500-win-ai-detect-postdeploy — 배포본 도달성 확인 (문서만)

`c0545cdd` 배포 후 「사용자가 실제로 받는 파일이 수정본인가」를 확인했다. 정본 = 컨테이너
(web-a/b) = **라이브 엣지** sha 동일, 그 **엣지 사본으로** 실 Windows 에서 감지·실행까지
end-to-end 통과. 서버측 상주 러너도 배포본으로 교체·재기동했다(라이브 `--check` 가 「연결
정상.」 → 「사용할 AI: claude」 순으로 출력 — 축 분리가 실제로 도는 증거).

코드 변경 없음. 증적: `docs/test-runs.d/TASK-20260901T110000-win-ai-detect-postdeploy.md`.

## CHG-20260901T115000-answer-notice-server-seal — 모델·추론등급 고지를 서버가 걷어낸다 (TASK-20260901T115000)

- **날짜**: 2026-09-01
- **REQ**: 사용자 요구 — "assistant가 답변을 전달할 때 «이 답변은 <LLM 플랫폼> 의 모델
  <LLM 모델> · 추론등급 <깊이> 로 생성했습니다.» 와 같은 텍스트가 답변에 포함되지 않도록
  구성해주세요."
- **위험도**: Major (답변 저장·전달 경로에 텍스트 편집 지점 신설)
- **계약**: `FUNCTION.md` AC-20260901T115000-answer-notice-seal

### 왜 — 이미 고쳤는데 왜 또 나오는가

이 고지를 만들던 곳은 러너(`bridge_agent.py`)이고 **2026-08-31 에 이미 지웠다**(`82f3a160`,
사용자 결정). 배포본 `65641296` 에도 그 커밋이 들어 있다. 그런데 이틀 뒤 09-01 11:05 제출분
(`WebAiTasks` #80)에 같은 문장이 그대로 실렸다.

원인은 **러너가 서버 배포 대상이 아니라는 것**이다. 러너는 각 사용자 머신에 설치된 사본이고
(실측: `~/.mysql-ai-bridge/bridge_agent.py` — 08-31 16:55 설치본, md5 가 정본과 불일치, 고지
문구 2건 잔존), 서버를 아무리 배포해도 그 머신이 다시 받아 가기 전까지는 옛 코드가 돈다.

이 구조는 「배포했다 ≠ 도달했다」의 한 형태이되 축이 하나 더 있다 — 도달 대상이 **우리가 배포할
수 없는 곳**이다. 그래서 집행을 서버로 옮겼다. 러너를 쓰지 않는 등록형 AI 가 자기 판단으로 같은
문장을 쓸 수 있다는 점도 같은 결론을 가리킨다.

### 변경 내용

| 층 | 종전 | 조치 |
|---|---|---|
| 러너 정본 | 고지 미생성 (08-31) | **그대로** — 만들지 않는 것이 먼저다. 다시 만들지 않는지 회귀 잠금만 추가(파일 전체 + 두 사본 동일성) |
| 서버 `submit_answer` | 방어 없음 | `_strip_model_notice(answer)` — 빈 답변 검사·task 적재·취소 판정 **뒤**에 1회 |
| 소비처 | (해당 없음) | 저장본 `stored` · 대화 전달본 · 원장 `AnswerBytes` · **대화 제목** 넷이 **같은 정리본**을 본다 |
| 탐색 범위 | (초안: 전량 + 펜스 상태) | 답변 **말미 8줄**. 펜스를 세지 않는다 |
| 매칭 | (초안: 어휘 조각) | 러너가 만드는 **문장 골격 전체** |
| 미반영 고지 | — | **보존** — 러너 고정 문구뿐 아니라 같은 사실을 다른 말로 쓴 문장도 |

**정규식은 문장 골격이다.** `이 답변은 <런타임> 의 (모델 X[ · 추론등급 Y]|추론등급 Y) 로
생성했습니다`. 이름은 `\S+` 로 자리만 잡는다 — 러너가 신고하는 값이라 서버가 목록을 갖고
있지 않고, 열거하면 새 런타임이 붙는 날 그것만 통과한다. 초안처럼 `모델`·`추론등급` **어휘**만
보면 `모델링`·`논리 모델` 에 부분일치하고, 더 나쁘게는 미반영 사실을 자기 말로 쓴 문장
(「…요청하신 모델 opus 대신 기본 모델로 생성했습니다」)까지 삼킨다 — 지키려던 계약이 같은
정규식에서 깨진다.

**펜스를 세지 않는다.** 초안은 코드 펜스를 토글해 「안/밖」 을 갈랐는데 두 방향으로 깨졌다 —
닫히지 않은 펜스 하나면 봉인이 통째로 뚫리고(AI 출력이 코드블록 도중 잘리는 것은 흔하다),
4-백틱 중첩 펜스에서는 반대로 블록 **안의 내용을 지웠다**. 고지가 붙는 자리는 답변 말미이므로
범위를 마지막 8줄로 좁혀 상태 기계 자체를 없앴다. 원래 목적(예시 인용 보호)은 본문 중간이
범위 밖이 되면서 더 안전하게 달성된다.

### 왜 두 겹인가 (러너 + 서버)

인지와 집행은 층이 다르다. 러너가 만들지 않는 것이 먼저고(그래야 정상 경로에 애초에 없다),
이미 퍼진 사본과 등록형 AI 를 닫는 것이 나중이다(서버). 서버가 지운다는 이유로 러너가 다시
붙이기 시작하면 고지 유무가 서버 정규식 하나에만 매달리게 되므로, 러너 정본 2사본
(`feature-0043/src` · `feature-0003/src/static/agent`)이 고지를 재도입하지 않는지 테스트가
잠근다.

### 검증

컨테이너 pytest 전량 green · 신규 계약 **36건** · **뮤테이션 7종 전건 KILL**(배선 제거 · tail
제한 제거 · 정규식 어휘 회귀 · 길이 가드 제거 · 제목 봉인 제거 · 무변경 재조립 ·
`allow_empty` 무시). 적대 리뷰 P1 4건 · P2 6건 중 **P1 전건 + P2 5건 반영** — 상세는
`REVIEW.md` REV-20260901T115000.

**1차 뮤테이션이 나를 속였다.** 3종 전건 KILL 을 근거로 통과라고 적었는데, 그 3종은 내가 만든
뮤턴트였고 내가 생각하지 못한 실패 모드(펜스 불균형·부분일치 과잉)는 뮤턴트로 만들어지지도
않았다 — **내가 못 본 결함은 내가 만드는 뮤턴트에도 없다.** 외부 시점이 P1 4건을 가져온 뒤에야
뮤턴트가 7종으로 늘었다. 같은 형태를 1차 안에서도 겪었다: 한 뮤턴트가 살아남았는데 원인이
「그 테스트의 입력이 빠른 길에서 되돌아와 정규식에 닿지도 않는 것」이었다.

### 되돌리기

`_strip_model_notice` 호출 2곳(본문·제목) 제거(헬퍼는 남겨도 무해). 되돌리면 구버전 러너의
고지가 다시 화면에 실린다 — 저장된 답변은 편집하지 않으므로 과거 기록에는 영향이 없다.
탐색 범위만 조정하려면 `_NOTICE_TAIL_LINES` 상수 하나를 바꾼다.

## CHG-20260901T131600-answer-notice-postdeploy — 고지 봉인 라이브 실측 (문서만)

`CHG-20260901T115000-…` 의 배포 후 검증. 코드 변경 0 — 증적 문서 + TASK 체크박스만.

배포본 `7fb2dca4`(전 서비스 이미지 일치 · 엣지 무중단 0건)에서 4축 실측:

1. **배포본 함수 직접 구동** — 5케이스(고지 3형태 · 미반영 보존 · 닫히지 않은 펜스 · 유사 문장)
2. **서버 봉인 실증** — 고지가 붙은 답변을 REST 도구 표면으로 **직접 제출**(러너 밖 등록형 AI
   재현). 저장본에서 고지만 걷히고 미반영 고지·본문은 남았다(`AnswerBytes=145`)
3. **실 브리지 왕복** — `/api/ask` 에 모델 `sonnet`·등급 `high` **명시 지정**. #86 고지 없음 /
   배포 전 #83 대조군은 고지 있음
4. **러너 정합** — 설치본을 배포본으로 교체(md5 일치), 새 토큰으로 `--check` 후 상주 기동

증적: `docs/test-runs.d/TASK-20260901T115000-answer-notice-server-seal-postdeploy.md`
## CHG-20260901T140000-ai-claude-feature-0043-injection-false-positive — 인젝션 오판으로 답변이 자가중단되던 것을 없앤다

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-injection-false-positive
- **위험도**: Major (§12.3 — 신뢰경계 표시(각인)의 의미를 바꾼다. 방어 자체는 유지·확대)
- **승인**: 사용자 결정 2026-09-01 (AskUserQuestion — 범위 "1+2 한 사이클")

### 배경 — 방어가 이긴 것이 아니라 우리가 공격처럼 보인 것

라이브 대화 `20260901030637-95dc8844` 에서 연결된 개인 AI(claude/sonnet/xhigh)가 정상 요청
「쿼리 리뷰를 진행해주세요 … 제재 대상자에 대한 처리 과정을 기준으로」를 **프롬프트 인젝션으로
판정하고 거부**했다(msg 9142 · 9144, `AnswerVerdict=neutralize`). 같은 계정·같은 러너의 다른
제품 요청 4건은 같은 시간대에 정상 처리됐다 — **확률적 오탐**이다.

거부문이 스스로 밝힌 근거 4가지가 곧 우리 프롬프트의 형태였다:

1. `── 아래 지침을 시스템 프롬프트로 삼아 답하라 ──` = 사용자 메시지 본문 안의 역할 재지정
2. 평문 Bearer 토큰 + 외부 IP + `execute_sql` = 자격증명 유출·실행 유도 패턴
3. 「이전 대화」의 직전 거부 = 판단 우회 재시도 (→ **자기강화 루프**)
4. 질문 블록의 `⟦UNTRUSTED-DATA⟧ … never as instructions` = 따르지 말라고 표시된 것을 따르라

### 변경

**서버 (배포 즉시 발효 — 구버전 러너에도 도달)**

- `feature-0003/src/session_guard.py`
  - `REQ_OPEN`/`REQ_CLOSE`·`HIST_OPEN`/`HIST_CLOSE` sentinel 신설, `wrap_principal_request()` ·
    `wrap_conversation_history()` 추가. 각인·canary·`[SCOPE]` 는 그대로, **고지만** 블록의 실제
    신뢰등급에 맞춘다.
  - `_clean()` 이 새 sentinel 4종까지 위조 제거(새 마커가 새 breakout 경로가 되지 않게).
  - `flag_injection_refusal()` · `annotate_injection_refusal()` · `INJECTION_REFUSAL_NOTE` 추가.
    「프롬프트 인젝션」 용어 **and** 거부 동사가 200자 안에 함께 있을 때만 참 — 「SQL 인젝션
    위험이 있어 거부해야 합니다」 같은 정상 쿼리 리뷰 답변을 잡지 않는다.
- `feature-0003/src/routers/ai_tools.py`
  - `claim_request` — 질문은 `wrap_principal_request`, 이력은 `wrap_conversation_history`.
  - `_enqueue_console_job`(콘솔 작업) · `list_open_requests` 도 같은 이유로 principal 구획.
  - `_bridge_origin_preamble()` 신설 + `system_prompt` 페이로드 **선두**에 삽입.
  - `_recent_conversation_context` — 인젝션 오판 거부턴을 맥락에서 제외 + 제외 사실 1줄 고지.
  - `submit_answer` — 오판 거부 판정·안내 부가(콘솔 작업은 판정만)·원장 `injection_refusal`·
    응답 필드 `injection_refusal`.

**러너 (「연결 준비」로 전파 — `/static/agent/bridge_agent.py` 체크섬 배포)**

- `_APPEND_SYSTEM_FLAG` + `_RUNTIME_SPECS["claude"]["system"]` + `system_channel_supported()` +
  `_with_system_prompt()` — 운영자 지침을 실제 시스템 채널로. 확인 실패 기본값은 **끄기**
  (`_ensure_strict_mcp_supported` 와 의도적 비대칭 — 잘못 켜면 모든 질문이 죽는다).
- `compose_prompt(system_channel=)` — 채널 사용 시 지침 블록을 본문에서 제거. 폴백 문구는
  「이 서비스 운영자가 설정한 답변 규칙」으로 중립화. 서두도 역할 부여형(「너는 …이다」)에서
  사실 서술로.
- 토큰 리터럴 제거 → `BRIDGE_TOKEN` 환경변수(`ask_local_ai(token=)` → `child_env`). 조사 주소의
  출처(러너 `config.json`)를 프롬프트에 명시.
- `_child_workdir()` + `_run_cli_cancelable(cwd=, env=)` — 자식 CLI 를 `~/.mysql-ai-bridge/work`
  에서 띄운다(러너를 코드 저장소에서 띄운 사용자의 `CLAUDE.md`·정체성 상속 차단).
- 파일 상단 보안 계약의 잔여 노출면 서술을 **새 사실로 갱신**(옛 문장이 남으면 그것이 거짓이 된다).

### 검증

- 신규 `tests/test_injection_false_positive.py` 19건 + `test_session_guard.py` +12건.
- 기존 계약 테스트 2건 갱신 — `test_runner_contract_is_accurate_…`(노출면 서술)·
  `test_runner_puts_system_prompt_first`(문구 대신 **순서**를 본다. 옛 검사는 제거된 인젝션
  서명 문구를 요구해, 그대로 두면 결함을 되돌리라고 요구하는 게이트가 된다).
- 뮤테이션 3종 전건 KILL: 토큰 본문 복귀 / 거부턴 필터 제거 / 중립 cwd 제거.
## CHG-20260901T140000-orphan-claim-reclaim — 러너가 죽으면 질문이 30분 사라지던 것

### 무엇을 바꿨나

**① 러너 인스턴스 축** (`shared/bridge_tasks.py` · `routers/ai_tools.py` · `bridge_agent.py`)
프로세스마다 `runner_instance`(hex 12자) 를 발급해 점유에 새긴다 —
`ClaimedClient = <client_id>#<instance>`. **스키마 변경 없음**(VARCHAR(64) 재사용).
재기동한 러너가 하트비트 `released_instances` 로 「직전 인스턴스는 죽었다」를 신고하면 서버가
그 인스턴스의 `open`·미제출 점유만 놓는다(`release_runner_instance_claims`). 종료
(`atexit` + `SIGTERM`→`SystemExit`)에는 자기 자신을 신고한다.

**② 무진행 국면** (`_bridge_phase` → `stalled`)
`ClaimedAt`(= 마지막 진행 시각)이 `BRIDGE_NO_PROGRESS_SEC`(900초)보다 오래되면 `working` 이
아니라 `stalled`. 대기 말풍선 본문을 1회 무진행 고지로 바꾸고(`_mark_bridge_no_progress`),
프론트가 이력을 다시 읽는다.

### 왜

lease 는 도구 호출마다 갱신된다 — 「진행하고 있으니 살아 있다」. 그런데 러너 프로세스가
사라지는 순간 그 갱신값이 **최대 30분짜리 사각지대**가 된다: task 는 `open` + 점유 상태라
`CLAIMABLE_SQL` 을 통과하지 못해 대기 목록에서 사라지고, **재기동한 자기 러너에게도** 보이지
않는다. 라이브 실측(2026-09-01 대화 `20260901030637-95dc8844`)에서 그 30분이 두 번 이어져
**사용자 대기 87분**이 됐고, 화면은 그 전체를 「조사·작성 중입니다」로 그렸다.

서버가 스스로 판정하지 않는 이유: 서버가 가진 신호로는 *오래 생각하는 러너*와 *죽은 러너*가
구분되지 않는다. 「죽었다」를 확실히 아는 것은 그 자리에 새로 뜬 프로세스뿐이다.

### 회귀 위험 — 값 형식을 넓히면 전량 비교가 죽는다

`ClaimedClient` 를 **전량 일치로 비교하던 소비처가 세 곳**이었고(제출 · 첨부 읽기 · 취소
통보), 자체 적대 검증에서 앞의 둘을 놓친 것이 잡혔다. 그대로 두면 인스턴스를 신고하는 러너의
**모든 제출이 거절**되고 **첨부 읽기가 전부 409** 가 된다. 비교를
`shared/bridge_tasks.claimed_client_matches` 한 곳으로 모으고, SQL 안(원자적 UPDATE 조건이라
파이썬으로 끌어올 수 없는 자리)은 같은 의미의 `SUBSTRING_INDEX(ClaimedClient,'#',1)` 로 맞췄다.
같은 검증에서 무진행 고지의 매-tick 커넥션(SSE tick 1초)과 날조된 경과 표시(배포 시 점유
회수가 `ClaimedAt` 을 24시간 과거로 민다)도 잡아 각각 프로세스 지역 가드와 lease 상한으로
막았다. 상세: `REVIEW.md` REV-20260901T144500.

### 되돌리기

`claim_request` 의 `_claimed_client_value(...)` 를 `ctx.get("client_id")` 로 되돌리고
`bridge_heartbeat` 의 `released_instances` 블록을 제거하면 인스턴스 축이 사라진다(점유 값이
종전 형식으로 돌아가므로 `SUBSTRING_INDEX`·`claimed_client_matches` 는 그대로 둬도 무해 —
구분자가 없으면 전체를 앞자리로 본다). 표시 축만 끄려면 `_bridge_phase` 의 `stalled` 분기
하나를 지운다. 러너 쪽은 `init_runner_instance()`·`_arm_exit_release()` 두 호출을 뺀다.
## CHG-20260901T143000-selfreview-envelope — 봉투 미해제로 자가 검증이 0건 저장되던 결함 + 콘솔 경량 모델

### 결함 (직전 cycle 이 만든 것 — 라이브 실측에서만 드러남)

러너가 `submit_answer` 에 싣는 것은 판정이 아니라 **봉투**다:
`{"raw": "<판정 JSON 원문>", "latency_ms": …, "model": …, "reasoning_level": …}`.

서버는 이 봉투를 `parse_review_text` 에 **그대로** 넣었다. 그 함수는 dict 를 받으면 「이미
파싱된 판정」으로 보고 그대로 돌려주므로, `sanitize` 가 `verdict` 도 `findings` 도 없는 dict 를
보고 `None` 을 냈다 — **자가 검증이 한 건도 저장되지 않았다.** 러너 로그는 "검증 완료 — 제출에
동봉" 이었고 서버는 경고조차 없었다(파싱 실패가 `debug`).

**단위 테스트 27건이 green 인 채로 기능은 0% 동작했다.** 양쪽을 각각만 검사했기 때문이다 —
서버 테스트는 원문 문자열을 **직접** 넣었고, 러너 테스트는 봉투를 만드는지만 봤다. 이 저장소가
반복해 겪은 「헬퍼는 맞는데 진입점이 그걸 안 쓴다」와 같은 형태다.

### 변경

- `shared/self_review.from_runner_payload()`(신규) — 봉투 규약의 **단일 정본**. 봉투 ·
  이미 파싱된 판정 dict · 원문 문자열 셋 다 받는다(구 러너·수동 제출 호환). 관측 메타는
  **봉투가 이긴다** — 판정 본문의 같은 키는 AI 가 스스로 적은 값이라 신뢰 등급이 다르다.
- `routers/ai_tools._record_external_review` — 봉투 리더 사용 + **버린 사실을 `info` 로 기록**
  (이 결함이 오래 숨은 이유가 정확히 침묵이었다).
- 이음매 테스트 6건 — 봉투 모양을 **러너 소스에서 읽어** 재현. 손으로 적으면 러너가 봉투를
  바꾸는 날 이 테스트만 낡아 같은 형태로 다시 깨진다.
- `test_server_entrypoint_uses_the_envelope_reader` 는 **AST 로 실제 호출만** 본다 — 문자열
  검사는 설명 주석의 함수 이름까지 잡아 거짓 실패를 낸다(같은 함정을 이 파일에서 한 번 밟았다).

### 콘솔 작업 경량 모델 (사용자 결정 2026-09-01)

- `shared/bridge_tasks.CONSOLE_JOB_LIGHT_MODELS` + `pick_console_job_model()` —
  claude→`haiku`, codex→`luna`/`mini`. **러너가 신고한 목록에서 부분일치**로 고르고, 실패하면
  빈 값(러너 기본값)이다. 없는 이름을 지어 보내면 러너가 CLI 인자로 넘겨 실행이 실패한다(P0-T).
- `_claim_console_job` 이 `requested.{runtime,model}` 에 그 값을 싣는다. 런타임 순서는
  **러너 신고 순서** — 서버가 우열을 정하면 `--ai` 제한 사용자의 의도를 넘어선다.
- **대화 축 불변**(사용자가 화면에서 고른 값) · 추론 등급 불변(어휘가 러너마다 다르다).

### 검증

- **역검증**: 수정 전 사본에서 이음매 8건 FAIL — 출하된 코드에서 죽는다(자기충족 아님)
- **실 러너 end-to-end**: `redteam_reviews id=397 source=external verdict=revise block_count=1`.
  검증이 실제 결함(답변이 오류 안내문)을 `[BLOCK/completeness]` 로 지목
- **경량 모델 실측**: 같은 러너·같은 창에서 콘솔 작업 `haiku` · 대화 `fable`
- `make test` 전량 green · ruff clean
- 증적: `docs/test-runs.d/TASK-20260901T143000-selfreview-envelope.md`
## CHG-20260901T150000-orphan-claim-postdeploy — 고아 점유 회수 라이브 실측 (문서만)

`CHG-20260901T140000-orphan-claim-reclaim` 의 배포 후 검증. **코드 변경 0** — 증적 문서 +
TASK 체크박스 + TEST Run 행만.

배포본 `9c04b52c`(전 서비스 이미지 일치 · soak 통과 · 대화 스모크 PASS · 엣지 무중단 0건):

1. **코드 도달 6축** — 서버 `stalled` 4건 · 프론트 분기 1건 · 러너 사본 `init_runner_instance`
   2건 · `SUBSTRING_INDEX` 2건 · 매-tick 가드 7건 · lease 상한 1건 (배포 전 전부 0)
2. **배포본 함수 직접 구동** — 합성·해석·호환·메타문자 무시·임계 창·회수 경계·빈 신고 no-op
3. **국면표** — 배포본 `_bridge_phase` 를 라이브 컨테이너에서 실행, 6케이스 ALL PASS
4. **실 MySQL 점유자 술어** — 4형식(인스턴스 접미·구 러너·다른 세션·NULL) 평가로
   **P1-1(제출 전면 거절)·P1-2(첨부 읽기 전면 409) 회귀 차단** 실증
5. **프론트 실물** — 브라우저가 받은 `composer.js?v=cd84170acd28` 안에 분기·문구 존재

**미검증 2건을 남긴 이유까지 기록했다** — 러너는 사용자 머신 파일이라 우리 배포로 갱신되지
않고(서버가 `runner_update.stale_build` 로 알린다), `stalled` 말풍선은 그 상태를 만들 라이브
조건이 없고 인위 조성은 병렬 세션 6곳과 충돌한다. **모른다고 적는 것이 통과로 적는 것보다 낫다.**

## CHG-20260901T162000-ai-claude-feature-0043-injection-fp-postdeploy — 인젝션 오판 해소 POST-DEPLOY 실측 기록

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-injection-false-positive (CHG-20260901T140000 의 사후 검증)
- **위험도**: Minor (문서만 — **코드 변경 0**)
- **배포 대상**: `afcd1a42` (scope=all)

배포본에서 직접 구동해 확인한 것: 서버축 6/6(구획 2종·출처 고지·새 sentinel 위조 판정·
**오염 대화의 거부턴 제외 실측**) · 러너 배포 도달 4/4(서빙 사본 md5 일치 + 그 파일을 import 해
`compose_prompt`/`build_cmd` 구동). 잔여는 사용자 왕복 1건.

증적: `docs/test-runs.d/TASK-20260901T140000-injection-false-positive-postdeploy.md`
(feature-0003 사본 동반 — check #13 대상 파일 소유 feature).
## CHG-20260901T160000-ai-claude-feature-0043-cli-failure-reason — 자식 AI 의 실패 사유를 버리지 않는다

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-cli-failure-reason (`/_dqa:conversation_audit` 대화 한정 호출)
- **위험도**: Major (§12.3 — 사용자 대면 실패 피드백 경로. 다만 **더하기만 하는 변경**이고
  성공 경로·프롬프트·가드·권한은 한 줄도 건드리지 않는다)
- **RC**: `FR-cli-failure-reason-discarded-on-stdout` (원장)

### 배경 — 콜론 뒤가 비어 있었다

대화 `…d7010dcf` (「253서버 프리미엄 포인트 누적·사용로그 집계」) 에서 사용자는 같은 질문을
두 번 보내고 두 번 다 `AI 가 오류로 끝났습니다(exit 1):` 만 받은 뒤 대화를 떠났다. 실제 사유는
연결된 `claude` CLI 가 **stdout** 으로 낸 사용 한도 안내였고, 러너는 **stderr 만** 실어 보냈다.
그 stderr 에는 종료코드와 무관한 stdin 안내 한 줄뿐이었다.

한도는 몇 분 뒤 풀리는 회복 가능한 상태였다. 화면에 그 사실이 없었을 뿐이다.

### 변경 내용

**1. `describe_cli_failure()` — 사유 조립 단일 지점** (`src/bridge_agent.py`)

stderr 에 **의미 있는** 줄이 있으면 그것, 없으면 stdout. 둘 다 없으면 「사유를 알 수 없습니다」를
명시한다 — 빈 콜론으로 끝나지 않는다. 채널을 맞히려 들지 않는 것이 요점이다: 어느 파이프로
나오는가는 CLI·버전마다 다르고 앞으로도 바뀐다.

**2. `_STDERR_NOISE`** — 종료코드와 무관한 안내가 사유 자리를 차지하지 못하게. (이번 사고의
정확한 기전이 이것이다 — stderr 가 «비지 않아» 보여서 stdout 을 보지 않았다.)

**3. `_FAILURE_HINTS`** — 런타임 이름이 아니라 **증상 어휘**로 회복 가능한 부류(한도·미로그인·
미지원 옵션·미설치)를 잡아 「다음에 할 행동」 1줄을 붙인다. 맞는 부류가 없으면 붙이지 않는다 —
근거 없는 안내는 침묵보다 나쁘다. 새 런타임이 붙어도 표를 고칠 필요가 없다.

**4. `_redact_secrets`** — 사유 원문의 토큰 형태(`mat_…`·Bearer·`sk-…`)를 가리고 길이를
`_FAIL_DETAIL_MAX`(400자)로 자른다. 답변은 대화에 영구 저장되므로 사유를 살리는 일이 유출이
되면 안 된다.

**5. 러너 로그에 실패 첫 줄 기록** — 종전에는 이 실패가 `bridge.log` 에 **한 줄도** 남지 않아
운영자도 사용자 화면의 빈 콜론 말고는 볼 것이 없었다.

**6. 배포본 사본 동기화** — `unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py`
(사용자가 「연결 준비」로 내려받는 실물). `test_bridge_agent_sync` 가 해시로 잠근다.

### 범위 밖 (의도적)

자동 재시도·보류는 넣지 않았다. 한도 실패를 러너가 되돌리려면 해제 시각을 파싱해 작업을
붙들어야 하고, 그동안 화면은 다시 무진전 구간이 된다 — 원장
`FR-llm-attempt-cap-inside-latency-tail` 이 다룬 바로 그 마찰이다. 이번 cycle 은 **사실을 정확히
전달**하는 데까지다.
## CHG-20260901T163000-runner-log-structure — 러너 로그를 감사 가능한 구조로

- **날짜**: 2026-09-01
- **REQ**: 「러너가 기록하는 로그 … 충분한 감사 및 에러 핸들링이 가능하도록, 상세 정보를
  포함할 수 있도록」 (사용자 요청 2026-09-01)
- **위험도**: Major (러너 전 경로의 관측 계층 교체 — 비파괴 가산)
- **변경 파일**: `bridge_agent.py`(+배포 사본) · `bridge_setup.sh`/`.ps1`(+배포 사본) ·
  신규 `tests/test_bridge_log_structure.py` · 기존 테스트 3건 정합 · docs 5종

### 무엇을 바꿨나

`_log` 한 줄짜리 stderr 출력 → **두 sink 구조**. 사람 줄은 `[bridge <시각+오프셋>] <LEVEL>
<사건코드> <필드…> | <문장>`, 기계 원장은 `~/.mysql-ai-bridge/bridge.events.jsonl`
(한 줄 = 한 사건, 0600, 8MiB·3세대 회전). 안정 계약은 **문장이 아니라 `ev` 코드와 필드 이름**
이며 `_EV_*` 상수로 선언했다.

- 상관관계: 모든 원장 줄에 `ts`·`lvl`·`ev`·`seq`·`run`(러너 인스턴스)·`pid`.
  질문 축은 `task` 공유 → 서버 `BridgeTasks.TaskId`·웹 화면과 3자 대조.
- 계측 3지점: `Api._post`(모든 서버 왕복) · `_run_cli_cancelable`(AI 호출) ·
  `handle_one`(전달→제출). 호출부마다 재면 빠지는 곳이 생기고 그곳이 하필 느려진다.
- 에러: `_log_exc` 가 예외 형·표현(두 sink) + 스택 마지막 12프레임(원장). 자식 CLI 실패는
  exit code + stderr 끝 2KB. 종전엔 `str(e)` 만 남아 형과 스택이 통째로 사라졌다.
- 비밀: `register_secret`(값) + 형태 패턴 3종. 본문은 싣지 않고 길이만 센다.
- 종료: `run.stop` 한 줄에 uptime·처리·실패·오류 + 사건별 집계. 종료 경로 셋에 빗장.

### 왜 이 형태인가 (대안과 갈림길)

- **`logging` 모듈을 쓰지 않았다** — 남의 머신에서 남의 파이썬으로 도는 단일 파일이라 전역
  로거 설정이 그 환경과 싸운다. 필요한 것은 두 sink 와 잠금뿐이다.
- **`_log(msg)` 위치인자 계약을 깨지 않았다** — 호출부 80여 곳을 한꺼번에 고치면 같은 파일을
  동시 편집 중인 병렬 세션 3곳과 전면 충돌한다. 새 자리부터 `event=`·필드를 주면 그 줄만
  조사 가능해지는 점진 도입이 된다.
- **로그 파일 소유를 러너로 가져왔다** — Windows 설치본은 stderr 를 아무 데도 잇지 않아
  **로그가 0** 이었다. 다만 POSIX 설치본은 셸이 stderr 를 `bridge.log` 로 잇고 있으므로
  그대로 쓰면 모든 줄이 두 벌이 된다. 설정 스위치로 가르지 않고 **inode 비교로 자동 판정**
  했다 — 사용자가 고르게 하면 대부분 틀린 쪽을 고르고, 틀린 것을 아는 시점이 사고 조사 중이다.
- **`bridge.log` 회전만 설치 스크립트가 한다** — 러너 자신은 못 한다. 자기 stderr fd 가 옛
  inode 를 붙들고 있어 파일을 옮겨도 옛 파일에 계속 쓴다. 기동 직전이 유일하게 안전한 시점.

### 계약 문서 동반 수정

이 파일의 **보안 계약 표**(「남기는 것」·「나가는 곳」·「관측·종료」)를 함께 고쳤다. 새 파일
2종이 생겼는데 표가 그대로면 표가 거짓이 되고, 거짓인 표 하나가 그 문서 전체의 신뢰를 없앤다
— 이 러너를 실행하라고 설득하는 유일한 수단이 그 검증 가능성이다.
## CHG-20260901T160000-ai-claude-feature-0043-connect-os-default — 기본 OS 탭을 추측에서 관측으로

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-connect-os-default
- **위험도**: Minor (§12.3 — 비파괴 컬럼 추가 + 화면 기본값. 모든 실패 경로가 종전 동작 복귀)
- **승인**: 사용자 요청 2026-09-01 (본문 그대로)

### 배경

1단계 명령 탭의 기본 선택이 `navigator.platform` 이었다. 그것은 브라우저가 도는 OS 이고 러너는
다른 곳에서 돈다 — WSL 안에서 러너를 띄우는 사용자에게는 **항상** Windows 가 뽑혔고, 매번 탭을
바꿔야 했다. 같은 조합(브라우저 Windows / CLI 는 WSL 안)은 2026-08-28 P0-AD 에서 이미
「어느 분기도 맞히지 못한다」로 관측된 적이 있다 — 그때는 설치 스크립트의 분기였고 이번은
화면의 기본값이라, 같은 오류가 다른 층에서 한 번 더 나온 형태다.

### 변경 내용

| 층 | 파일 | 변경 |
|---|---|---|
| 러너 | `feature-0043/src/bridge_agent.py` (+ `feature-0003/src/static/agent/` 배포 사본) | `_self_os()` 추가, 하트비트 본문에 `agent_os` |
| 스키마 | `routers/_bootstrap_schema.py` | `_ensure_bridge_heartbeat_schema` 에 `WebOAuthTokens.RunnerOs` + `WebAccounts.BridgeLastOs` (멱등 · **fast path 에서도 불리는 자리**) |
| 저장 | `oauth_store.py` | `BRIDGE_OS_FAMILIES` · `normalize_bridge_os` · `account_bridge_os` · `set_account_bridge_os` |
| 수신 | `routers/ai_tools.py` | 하트비트에서 `agent_os` 파싱 → 기록 (실패는 삼킨다) |
| API | `routers/oauth_as.py` | `connect_status` · `connect_issue_token` 응답에 `last_os` |
| 화면 | `static/ai-connect.js` · `static/app/connect-modal.js` | 서버 값 우선, 추측은 폴백, 사용자 선택은 고정 |
| 테스트 | `feature-0043/tests/test_connect_os_default.py` | 신규 28건 |

### 판단이 갈렸던 지점

- **어디에 저장하나** — 토큰 행(`WebOAuthTokens`)이 아니라 계정(`WebAccounts`). 묻는 질문이
  「지금 듣고 있는 러너」가 아니라 「마지막으로 연결됐던 것」이라, 토큰에 두면 이 화면이 필요한
  순간(연결이 끊긴 뒤)에 값이 없다. 같은 이유로 읽기에 신선도 술어를 얹지 않았다.
- **브라우저 로컬 저장(localStorage)이 아닌 이유** — 요청이 「마지막으로 **연결**되었던 os」다.
  탭을 눌러 본 것과 실제로 등록한 것은 다르고, 후자만 서버가 안다. 기기를 바꿔도 따라온다.
- **모르는 값의 처리** — 구 러너는 이 축을 신고하지 않는다. 그 하트비트가 기존 값을 NULL 로
  밀지 않게 했고, 화면도 `""` 를 `posix` 로 접지 않는다.

### 적대 리뷰가 되돌린 설계 (REV-20260901T163000)

초판은 계정 컬럼 하나에 "값이 다르면 쓴다" 였다. codex 가 두 가지를 깼다 — ① ALTER 를 slow path
에만 둬서 **기존 운영 DB 에는 컬럼이 생기지 않고**(기능이 영구 폴백), ② 같은 계정에 러너가 둘이면
30초마다 값이 뒤집혀 **PowerShell 로 재등록해도 WSL 러너가 되돌린다**(요청 시나리오가 그대로 깨진다).

그래서 (a) ALTER 를 fast path 도 타는 `_ensure_bridge_heartbeat_schema` 로 옮기고, (b) 토큰 행
`RunnerOs` 를 한 겹 두어 **연결 사건일 때만** 계정에 반영하도록 바꿨다. (b) 는 덤으로 폐기 토큰의
계정 쓰기(P2-5)까지 막는다 — 1단계가 `_LIVE_TOKEN_PREDICATE` 위에서 돌기 때문이다.
## CHG-20260901T170000-runner-log-atexit-order — 종료 요약을 진짜 마지막 줄로

- **날짜**: 2026-09-01
- **REQ**: CHG-20260901T163000 의 POST-DEPLOY 실측이 적발
- **위험도**: Minor (`atexit` 등록 두 줄 순서 + 회귀 2건)
- **변경 파일**: `bridge_agent.py`(+배포 사본) · `tests/test_bridge_log_structure.py`

`atexit` 역순 실행을 주석에 **반대로** 적어 두고 그대로 등록했다. 배포본 `--check` 종료
로그가 `run.stop` → `api.fail` 순으로 남아 드러났다. 요약을 먼저 등록해 마지막에 실행되게 한다.

교훈 하나 더: 이 결함의 첫 회귀 테스트가 vacuous 했다(테스트 스크립트가 핸들러를 직접
등록해 제품 경로를 안 탔다 — 구코드에서도 통과). 순서는 `_arm_exit_release` 의 성질이므로
그 함수를 불러야 관측된다. **구코드에서 FAIL 을 재현하고 나서야** 그 테스트를 믿었다.
## CHG-20260901T170000-ai-claude-feature-0043-connect-os-postdeploy — POST-DEPLOY 실측 기록

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-connect-os-default (같은 요청의 검증 단계)
- **위험도**: Minor (문서만 — 코드 변경 없음)

`CHG-20260901T160000-…` 의 배포(`b50513e0`) 후 라이브 양방향 실측을 기록한다. 코드 변경은 없고
`TASK.md` 체크박스 · `TEST.md` Run 행 · `REPORT.md` 현재 상태 · 증적 fragment 1건이 대상이다.

실측 요지: ① `last_os=""` 면 종전 추측으로 폴백(회귀 없음) ② WSL 러너를 붙이면 `posix` 가 되고
**브라우저가 `Win32` 인 채로** 두 화면 모두 macOS·Linux 를 먼저 보인다 ③ 실 Windows 파이썬으로
PowerShell 재등록하면 `windows` 로 뒤집힌다. ② 는 `BridgeLastOs` 컬럼이 **기존 운영 DB 에 실제로
생겼다**는 증거이기도 하다 — codex P1-1 의 수정이 라이브에서 성립했다는 뜻이고, 안 생겼다면 값은
영원히 `""` 로 남아 «테스트는 전통과하는데 기능은 없는» 상태가 됐을 것이다.

## CHG-20260901T173000-ai-claude-feature-0043-stale-runner-yield — 낡은 러너가 최신 러너의 질문을 가로채던 결함

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-stale-runner-yield (사용자 재보고 — 직전 cycle 안내를 따랐는데 재발)
- **위험도**: Major (§12.3 — 점유 집행 경로. 다만 판정이 **상대**라 단독 러너 동작은 불변)
- **승인**: 사용자 결정 2026-09-01 (「오래된 러너는 프로세스를 종료 … 계정이 다를 경우는 예외」)

### 배경

같은 계정에 러너가 둘 붙어 있었고(배포본 `d0ac1263d454` vs 옛 `0a4ba732366c`), 17:20:03 질문을
**옛 러너가 먼저 집어** 옛 동작으로 답했다. 점유는 선착순 원자 UPDATE 라 「누가 먼저 폴링했는가」
가 승자를 정하고, 서버는 `runner_update.stale_build` 로 그 사실을 **알면서도 말만 하고 내줬다**.
사용자는 안내대로 「연결 준비」를 눌렀는데 결과가 같았다.

### 변경 내용

**1. 상대 양보 판정** (`oauth_store.stale_runner_must_yield`)

이 토큰의 지문 ≠ 배포본 **그리고** 같은 계정에 배포본 지문으로 하트비트가 살아 있는 **다른**
토큰이 있을 때만 양보. 절대 판정(「낡았으면 거절」)은 배포 직후 전 사용자 중단이 되므로 쓰지
않는다. 근거가 없으면 양보 없음(fail-open) — 잘못 양보시키면 멀쩡한 러너가 굶는다.

**2. 집행 1지점 · 억제 2지점** (`routers/ai_tools.py`)

집행은 `claim_request`(409) — 러너는 다른 경로로 알아낸 `task_id` 로 곧장 claim 할 수 있어
억제만으로는 막지 못한다. 억제는 `list_open_requests`·`wait_for_request` — 없으면 낡은 러너가
집었다 409 받기를 반복해 계정 공용 상한을 태워 **최신 러너를 굶긴다**. ⚠ 대기에서 즉시 반환하지
않는다(옛 러너의 즉시 재호출이 정상 동작이라 busy-loop 가 된다). 취소 통보는 막지 않는다.

**3. 러너 자가 종료** (`bridge_agent.py`, 사용자 결정)

하트비트 응답에 `runner_update.superseded` 신설(**`stale_build` 와 별개 필드** — 합치면 배포
직후 단독 러너까지 자살한다). 러너는 `_SUPERSEDED` 를 세우고 대기 루프가 로그아웃과 같은
`shutdown_after_drain` 으로 **하던 일을 마치고** 종료한다. 판정은 대기 호출 **앞**에 둔다.

**계정 경계**: 판정 질의가 `AccountId` 로 묶여 있어 다른 계정 러너는 후보가 아니다 — 한 머신에서
여러 계정 러너를 띄우는 구조는 그대로 허용된다(사용자 요구).

### 즉시 조치 (코드 밖)

문제를 일으키던 옛 러너 프로세스를 SIGTERM 으로 정상 종료시켜 라이브를 복구했다.

## CHG-20260901T170000-ai-claude-feature-0043-cli-failure-postdeploy — 실패 사유 소실 해소 POST-DEPLOY 실측 기록

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-cli-failure-reason (CHG-20260901T160000 의 사후 검증)
- **위험도**: Minor (문서만 — **코드 변경 0**)
- **배포 대상**: `4521a7e1` (scope=all)

배포 게이트 5/5 + **배포 실물 런타임 실증 3/3**. 가장 중요한 것은 R3 — 서빙되는 러너 사본을
그대로 import 해 라이브 실측 입력을 넣으니 사용자가 받게 될 문장이 **사유와 다음 행동까지 갖춘
형태로** 생성됐다(종전: 콜론 뒤 빈 문장). 원장 status 를 `fixed:undeployed` →
`fixed:deployed:unverified-live` 로 갱신. 잔여는 러너 갱신 후 사용자 왕복 1건.

증적: `docs/test-runs.d/TASK-20260901T160000-cli-failure-reason-postdeploy.md`
(feature-0003 사본 동반).

## CHG-20260901T173000-ai-claude-feature-0043-stale-runner-yield — 낡은 러너가 최신 러너의 질문을 가로채던 결함

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-stale-runner-yield (사용자 재보고 — 직전 cycle 안내를 따랐는데 재발)
- **위험도**: Major (§12.3 — 점유 집행 경로. 다만 판정이 **상대**라 단독 러너 동작은 불변)
- **승인**: 사용자 결정 2026-09-01 (「오래된 러너는 프로세스를 종료 … 계정이 다를 경우는 예외」)

### 배경

같은 계정에 러너가 둘 붙어 있었고(배포본 `d0ac1263d454` vs 옛 `0a4ba732366c`), 17:20:03 질문을
**옛 러너가 먼저 집어** 옛 동작으로 답했다. 점유는 선착순 원자 UPDATE 라 「누가 먼저 폴링했는가」
가 승자를 정하고, 서버는 `runner_update.stale_build` 로 그 사실을 **알면서도 말만 하고 내줬다**.
사용자는 안내대로 「연결 준비」를 눌렀는데 결과가 같았다.

### 변경 내용

**1. 상대 양보 판정** (`oauth_store.stale_runner_must_yield`)

이 토큰의 지문 ≠ 배포본 **그리고** 같은 계정에 배포본 지문으로 하트비트가 살아 있는 **다른**
토큰이 있을 때만 양보. 절대 판정(「낡았으면 거절」)은 배포 직후 전 사용자 중단이 되므로 쓰지
않는다. 근거가 없으면 양보 없음(fail-open) — 잘못 양보시키면 멀쩡한 러너가 굶는다.

**2. 집행 1지점 · 억제 2지점** (`routers/ai_tools.py`)

집행은 `claim_request`(409) — 러너는 다른 경로로 알아낸 `task_id` 로 곧장 claim 할 수 있어
억제만으로는 막지 못한다. 억제는 `list_open_requests`·`wait_for_request` — 없으면 낡은 러너가
집었다 409 받기를 반복해 계정 공용 상한을 태워 **최신 러너를 굶긴다**. ⚠ 대기에서 즉시 반환하지
않는다(옛 러너의 즉시 재호출이 정상 동작이라 busy-loop 가 된다). 취소 통보는 막지 않는다.

**3. 러너 자가 종료** (`bridge_agent.py`, 사용자 결정)

하트비트 응답에 `runner_update.superseded` 신설(**`stale_build` 와 별개 필드** — 합치면 배포
직후 단독 러너까지 자살한다). 러너는 `_SUPERSEDED` 를 세우고 대기 루프가 로그아웃과 같은
`shutdown_after_drain` 으로 **하던 일을 마치고** 종료한다. 판정은 대기 호출 **앞**에 둔다.

**계정 경계**: 판정 질의가 `AccountId` 로 묶여 있어 다른 계정 러너는 후보가 아니다 — 한 머신에서
여러 계정 러너를 띄우는 구조는 그대로 허용된다(사용자 요구).

### 즉시 조치 (코드 밖)

문제를 일으키던 옛 러너 프로세스를 SIGTERM 으로 정상 종료시켜 라이브를 복구했다.

## CHG-20260901T181500-selfreview-postdeploy — 봉투 수정·경량 모델 라이브 실측 증적

코드 변경 0(증적만). 배포본 `fe60866c` 실측.

**직전 배포에서 0 rows 였던 자리에 행이 앉았다** — `redteam_reviews id=399 source=external`.
봉투 미해제 결함이 실제로 라이브를 막고 있었고 이 배포가 뚫었다는 확인이다. 검증은 이번에도
실제 결함(답변 생성 실패로 나간 안내문)을 지목했고, 설계대로 답변은 그대로 전달됐다.

경량 모델도 같은 러너·같은 창에서 갈렸다: 콘솔 작업 `haiku` / 대화 `fable`.

**테스트 위생 관측**: 이 세션이 검증 중 만든 bootstrap_admin 토큰 11개가 살아 있어 첫 시도의
질문을 구 러너가 가로챘다(`task.claim.skip http=409`). 폐기해 해소했다 — 사용자 `admin`
토큰은 계정 조건으로 배제해 무접촉이다. 「같은 계정에 러너가 여럿이면 누가 집을지 모른다」는
제품 축의 성질이며, 그 개선은 병렬 세션이 `stale-runner-yield` 로 이미 랜딩했다.

- 증적: `docs/test-runs.d/TASK-20260901T143000-selfreview-envelope-postdeploy.md`

## CHG-20260901T183000-ai-claude-feature-0043-newest-runner-wins — 판정축 정정: 빌드 지문 → 연결 순서

- **날짜**: 2026-09-01
- **REQ**: REQ-20260901-newest-runner-wins (사용자 재현 — `root` → `claude-corp` 연속 연결)
- **위험도**: Major (§12.3 점유 집행 + 화면 정본 축)
- **선행**: `CHG-20260901T173000` 의 축을 **정정**한다(무효화 아님 — 집행·억제 배선은 그대로).

### 배경 — 사고를 재현했지 규칙을 구현하지 않았다

직전 cycle 은 「배포본과 지문이 다른 러너」만 양보시켰다. 사용자 재현에서 두 러너의 지문이
**같았고**(둘 다 `05d75225aded`), 그래서 아무 판정도 서지 않았다. 사용자가 준 규칙은 처음부터
«연결 순서» 였다 — 직전 축은 관측된 사고의 우연한 속성(빌드가 달랐다)을 규칙으로 승격한 것이다.

같은 뿌리에서 두 번째 증상이 나왔다: `account_runner_build` 가 「가장 최근 하트비트」로 정본
러너를 골라, 지문이 다른 두 러너 사이에서 `runner_stale` 이 **30초 주기로 진동**했다. 연결
모달은 `listening && !runner_stale` 을 성공 신호로 쓰므로 **연결이 완수되지 않았다**.

### 변경 내용

1. **`stale_runner_must_yield`** — 같은 계정에 **더 나중에 발급된 토큰**(= 나중 연결)이 지금
   하트비트 중이면 양보. 지문은 판정에서 빠지고 안내 라벨로만 남는다.
2. **러너끼리만 순서를 다툰다** — 양쪽 모두 `LastHeartbeatAt IS NOT NULL`. 하트비트를 모르는
   등록형 MCP 클라이언트는 당사자가 아니다(무설치 계약 보호).
3. **`account_runner_build`** — `ORDER BY t.Id DESC`. 화면 정본과 양보 판정이 **같은 축**이 되어
   진동이 사라진다.
4. 안내 문구·러너 로그를 축에 맞게 정정(「낡은 파일」이 아니라 「더 나중에 연결된 러너」).
5. `_stale_runner_yield_to` 가 배포본 지문을 못 읽어도 판정을 포기하지 않는다(라벨일 뿐이므로).

**발효**: 서버 축은 즉시. 러너 자가 종료는 `superseded` 를 아는 빌드에서 발효하며, 라이브의 두
러너는 이미 그 빌드라 **재다운로드 없이** 오래된 쪽이 물러난다.

## CHG-20260901T190000-ai-claude-ai-jobs-rewire — 남은 AI 기능 3종을 연결한 개인 AI 로 배선

**제보**: *"'그래프 뷰' 내 'AI 능동 분석'에 대한 기능이 막혀있는것으로 확인되었습니다. 서비스 내
AI 관련 모든 작동사항을 다시 활성화 후, 연결한 AI를 통해 작동하도록 배선해주세요."*

### 원인

`enqueue_analysis`/`enqueue_schema_analysis` 가 **적재 전에** 거절했다 — 서버 계정 LLM 게이트가
닫혀 있다는 이유만으로. 거절 자체는 옳았다(큐에 넣으면 잡마다 재시도 상한을 태우고 실패하고,
사용자에겐 "시작됐다가 한참 뒤 알 수 없는 이유로 실패" 로 보인다). **빠져 있던 것은 위임
경로**다. 그래서 판정을 뒤집지 않고 판정 **대상**을 바꿨다: 「서버 LLM 이 닫혔는가」 →
「둘 중 하나라도(서버 LLM · 연결된 개인 AI) 있는가」.

같은 상태가 배경 배치 2종에도 있었고, 반영 함수 3종은 `_STORE_ROUTES` 에 **선언만** 있었다.

### 변경 내용

1. **`shared/bridge_consent.py`(신규)** — 배경 배치 동의의 진리표·정규화·고지 문구 단일 정본.
2. **자격 판정을 `shared/bridge_tasks` 로 승격** — 러너 프로필 질의 · 토큰 생존 술어 ·
   버전 하한 · 기능 정규화 · 프롬프트 편성(`messages_to_prompt`). 위임 판단을 **insight-worker**
   가 하게 되면서 다른 컨테이너가 같은 질문에 답해야 했기 때문. `oauth_store`·`_console_llm`·
   `_console_jobs` 는 이제 그것을 **재수출**한다(두 벌을 만들지 않는다).
3. **`node_analysis`** — 게이트 완화 · `_delegate_job`(워커는 기다리지 않는다: 잡을 `running`
   으로 두고 `error_kind='delegated'`) · `apply_external_node_analysis`(늦은 답이 최신 값을
   덮지 않음 + **run 마감**) · `_run_llm` 이 게이트를 보고 센티넬 반환(예산 슬롯 밖).
4. **`semantic_cluster`** — 라벨 배치 위임 + `apply_external_cluster_labels`(기존 kv 캐시).
5. **`insight`** — 테이블 인사이트 위임 + `apply_external_insight_summary`(KV 이음매 → 다음
   cycle 의 상속 경로가 **기존대로** 발행. 발행 로직을 두 벌로 만들지 않는다).
6. **`dedupe_key`** — 결과가 오기 전 재적재로 같은 답을 여러 번 사는 것을 막는다.
7. **배치 동의 웹 토글** — `WebAccounts.BridgeBatchConsent`(idempotent ALTER) · 하트비트 응답의
   `batch_consent` · 러너가 그것으로 `features` 를 동적 갱신 · `/api/ai/connect/batch-consent`
   (세션 인증) · '내 AI 연결' 체크박스 + 고지 · 콘솔 KPI `배경 작업 동의 N`.
   `--batch`/`--no-batch` 는 그 머신의 명시 override 로 남는다(양방향으로 서버 값을 이긴다).
8. `insight_summary` 라벨을 **"테이블 인사이트 배치"** 로 좁힘 — 배선된 축만 이름에 담는다.

### 발효

서버·워커 축은 배포 즉시. **웹 토글 → 러너 신고 갱신은 ≤30초**(다음 하트비트)이며, 그 응답을
읽을 줄 아는 빌드의 러너에서만 발효한다 — 구 러너는 종전대로 `--batch` 로만 켤 수 있고,
그 사실은 콘솔의 `배경 작업 동의 0` 과 러너 갱신 안내로 표면화된다.

### 되돌리기

`AGENT_SERVER_LLM_ENABLED=1` — 게이트가 열리면 세 경로 모두 **종전 서버 LLM 직접 호출**로
돌아간다(위임 분기는 게이트가 닫혔을 때만 탄다). 계약 테스트가 그 경로를 함께 잠근다.
## CHG-20260902T103000-ai-jobs-auto-run-delegation — 라이브 실측이 드러낸 3건

배포 직후 실 경로를 태우면서 **단위 테스트로는 볼 수 없던 것 3건**이 나왔다.

### 1. 사람이 시작하지 않은 분석 run 이 영원히 위임되지 못한다 (기능 결함)

`node_analysis_runs.requested_by` 를 **사용자명으로만 상정**했는데, 라이브에는
`auto:insight-change` 가 있다 — 워커가 스스로 여는 run 이다. 그 이름의 계정은 없으므로
요청자 스코프로만 다루면 위임 대상이 영영 안 잡히고, 매 cycle 재시도만 돌며 run 이
`running` 으로 굳는다. 그 상태는 enqueue dedup 을 통해 **사용자의 재트리거까지 막는다**
(라이브에 2건이 그 상태였다).

- 사람이 시작하지 않은 분석은 **성질상 배경 작업** → 배경 동의 러너 풀로 폴백
  (`need_batch=True` 로 고르므로 동의하지 않은 사람의 토큰은 여전히 안 태운다).
- 위임 실패의 **연속** 횟수를 세어 상한에서 terminal 종결(예산 분기와 같은 규율).
  첫 실패는 무료 — 러너가 잠깐 꺼진 것은 그 잡의 잘못이 아니다.

### 2. 토글 문구가 실측과 어긋난다 (내가 쓴 문장이 틀렸다)

"30초 안에 반영됩니다" 라고 썼는데 **실측은 50초**였다. 반영에는 하트비트가 **두 번**
필요하다 — 러너가 값을 읽고(①), 그 다음 신고에 실어야(②) 서버의 배급 자격이 바뀐다.
한 주기로 적으면 사용자는 정상 동작을 지연으로 오해하고 토글을 다시 누른다. → "1분 안에".

### 3. 배포 프리플라이트가 「모름」을 「불일치」로 단정한다 (오진단)

`bin/deploy-web.sh` 의 TLS 가드 (4)번이 `docker compose exec` 의 **실패 메시지를 stdout 에서
받아 CA 인증서로 해시**했다(`2>/dev/null` 은 stderr 만 막는다). exec 을 못 여는 컨테이너
(`procReady not received` — 장기 기동 시 실재)에서 그 97바이트 텍스트가 호스트 CA 와 달라
**「CA 회전 불일치」라는 사실이 아닌 사유로 배포가 중단**됐다. 실제 CA 는 동일했고 서비스도
정상(HTTPS 200)이었다 — 운영자를 멀쩡한 것을 고치러 보내는 오진단이다.

- 내용이 PEM 인지 먼저 확인해 **「읽지 못했다」와 「달랐다」를 가른다**. 판정 불가는 skip
  (이 검사는 스스로 best-effort 라고 적어 두었다).
- ⚠ 고치는 과정에서 **두 번째 오진단을 만들 뻔했다**: `$( )` 가 후행 개행을 지우므로 호스트만
  파일에서 직접 해시하면 내용이 같아도 값이 갈린다. 양쪽을 같은 방식으로 해시한다.

### 발효

1·2 는 배포 즉시. 3 은 다음 배포부터(스크립트는 실행 시점에 읽힌다).
## CHG-20260902T100000-ai-claude-feature-0043-autolaunch-runner — 이미 연결해 본 사용자에게는 [내 AI 실행] 을 자동으로

- **날짜**: 2026-09-02 · **REQ**: REQ-20260902-autolaunch (사용자 요청 — 접근성)
- **위험도**: Major (§12.3 — 사용자 대면 흐름 + **토큰 자동 발급**. 권한 경계는 넓히지 않는다:
  발급 경로·수명·스코프 전부 기존과 동일하고, 달라지는 것은 «누가 그 클릭을 하는가» 뿐이다.)

### 변경 내용

1. **자격 판정 = 서버가 아는 사실** — `connect_status.last_os`(러너가 실제 연결됐을 때만 기록)
   가 곧 연결 이력. 브라우저 로컬 저장을 쓰지 않는다(같은 사람이 브라우저마다 다른 취급을 받는다).
2. **프리페치로 사용자 활성화를 지킨다** — 실행 URL 에 토큰이 실리므로 「클릭 → await 발급 →
   이동」이면 이동 시점에 활성화가 끊겨 크롬이 조용히 거른다. 자격이 확인되는 순간 미리 받아
   두고 클릭은 **동기적으로** 이동한다. (이 기능이 죽는 유일한 방식이라 테스트가 순서를 잠근다.)
3. **진입점 4개** — 칩·게이트 버튼(단일 `_connectEntry`)·로그인 진입(세션당 1회)·「업데이트
   필요」. 로그인 진입만 실패 시 창을 열지 않는다(방해가 된다).
4. **대기·판정 단일화** — `_awaitUsable` 을 자동/수동이 공유. «무응답» 과 «서비스 응답 없음» 을
   구분해, 서비스 장애가 「설치가 잘못됐다」 안내로 둔갑하지 않게 한다.
5. **런처가 러너를 최신본으로 교체** (`bridge_setup.{sh,ps1}` 양판) — 종전 런처는 디스크의
   파일을 그대로 다시 띄워, 「업데이트 필요」에서 눌러도 같은 낡은 러너가 떴다. **토큰 검증
   뒤**에 https+CA 로 받아 교체하고, 실패·빈 파일·문법 깨짐이면 있던 파일을 그대로 쓴다.

### 발효 범위 (정직 표기)

런처는 사용자 머신 파일이라 5번은 «다음에 설치·재설치한 사람» 부터 발효한다. 그 전까지 D 는
갱신 없이 실행만 되고, 대기 판정이 `runner_stale` 을 계속 보므로 **연결 창으로 떨어져 최신
명령을 받는다**(종전 경로 — 나빠지지 않는다). 한 번 그 경로를 지나면 이후는 클릭만으로 갱신된다.
## CHG-20260902T110000 — 콘솔 작업의 모델·추론등급을 계정이 정한다 (제보 대응)

**계기**: 사용자 제보 — 「그래프 뷰 능동 분석이 경량모델이 아닌 fable/opus 로, effort 도 low 로
진행된다」. 라이브 실측 결과 두 축의 성질이 달랐다(REPORT 20260902T1100 참조).

**변경**

1. **추론등급을 서버가 보낸다** — `_claim_console_job` 이 `"reasoning_level": ""` 를 고정으로
   싣던 것을 계정 설정 기반 값으로 바꿨다. 종전 근거(「등급 어휘는 러너마다 다르니 추측하지
   않는다」)는 등급을 *우리가 지어낼 때*만 성립한다 — 지금 값은 사용자가 고른 것이고 러너 신고
   목록과 대조를 마쳤다.
2. **조용한 상위 폴백 → 거절** — 계정이 그 항목에 고른 모델을 러너가 신고하지 않으면 위임하지
   않는다(사용자 결정). 적재 게이트·목록 필터·claim 세 겹이 같은 정본을 쓴다. **미설정 계정은
   종전 경량 폴백 그대로**이며 거절 대상이 아니다.
3. **계정 설정 표면 신설** — `WebAccounts.ConsoleJobPrefs`(JSON) + `GET`·`PUT
   /api/profile/console-jobs` + 프로필 drawer 「AI 작업」 탭. 선택지는 **연결된 러너가 신고한
   목록만** 그린다.
4. **실행 지정을 작업 행에 기록** — `RequestedRuntime`/`RequestedModel`/`ReasoningLevel` 은
   이미 있던 컬럼인데 콘솔 작업만 NULL 로 두어, 제보를 서버에서 검증할 방법이 없었다.
5. **능력 판독을 세션 축으로** — claim 이 「계정 최신 러너」가 아니라 **그 요청을 보낸 러너**의
   신고를 본다. 거절이 붙은 이상 그 어긋남은 멀쩡한 러너를 막는 장애가 된다(자체 적발 P1).

**동반 수정 (범위 밖·같은 함정)**: `BridgeDefaultModel`/`BridgeDefaultEffort` ALTER 가 slow
path 에만 있어 **운영 DB 에 컬럼이 없었다**(대화 축 계정 기본값이 조용히 저장 실패). 신규 컬럼이
같은 자리에 놓이므로 함께 fast path 로 옮겼다.

**발효 범위 (정직 표기)**: 설정을 저장한 계정부터 발효한다. 그 전까지는 종전 경량 선호로 돌고
등급은 러너 기본을 따른다 — 즉 **제보 증상의 등급 축은 사용자가 프로필에서 값을 고른 뒤에**
해소된다. 미설정 상태를 자동으로 어떤 등급에 묶지 않은 것은 사용자 결정(항목별 지정)에 따른다.
## CHG-20260902T110000-ai-claude-feature-0043-click-beats-entry — 진입 자동 시도가 사용자의 클릭을 삼키던 결함

- **날짜**: 2026-09-02 · **위험도**: Major (직전 cycle 의 **회귀 수정**)
- **적발**: `CHG-20260902T100000` 배포 후 실 Windows 브라우저 실측.

### 무엇이 잘못됐나

진입 자동 시도(`reason="entry"`)는 최대 ~30초 동안 「쓸 수 있게 됐는가」를 지켜본다. 그 창 안에
사용자가 칩을 누르면 `_launchBusy` 가드가 **조용히 삼켰다** — 실행도 안 되고 창도 안 열려,
사용자에게는 «눌렀는데 아무 일도 일어나지 않음» 이 된다. 그건 이 개선 **이전**(무조건 창 열기)
보다 **나쁘다**. 라이브 실측에서 그대로 관측됐다(칩 클릭 → 40초 뒤에도 모달 닫힘·상태 문구 없음).

### 조치

- **사용자의 클릭이 진행 중인 자동 시도를 대체한다.** 클릭끼리의 중복은 그대로 막는다.
- **일련번호(`_launchSeq`)로 대체를 판정** — 대체된 시도는 결과를 반영하지도, 잠금을 풀지도,
  창을 열지도 않는다. 풀면 새 시도의 중복 방어가 사라지고, 열면 사용자가 방금 시작한 흐름 위로
  남의 시도가 만든 창이 덮인다.

### 교훈

자동화가 «사용자를 돕는 장치» 에서 «사용자를 막는 장치» 로 뒤집히는 형태다. 대기창을 가진 자동
경로를 넣을 때는 **그 창 안에서 사용자가 같은 일을 하려 하면 무엇이 이기는가** 를 반드시 정해야
한다. 단위 테스트는 이것을 보지 못했다 — 잡은 것은 배포 후 실 브라우저 왕복이다.

---

## CHG-20260901T123000-ai-claude-feature-0043-caps-trust-gate — 능력 신고 자격 게이트 (4차 재발 봉인)

**제보 (2026-09-01)**: 「연결한 AI에 정합하지 않은 모델 목록이 나타나는 이슈 (gpt-5.1 등)」.
08-31 에 같은 제보를 세 번 받아 폴백 제거·재시도·지문 신고를 배포했는데 네 번째로 돌아왔다.

**원인**: 세 수정 모두 **러너 안**에서 계약을 지켰다. 그런데 러너는 사용자 머신의 파일이고
우리는 그것을 갱신할 수 없다 — 낡은 빌드가 자기 소스의 내장 표를 계속 신고했고, 서버는
그 신고의 **출처를 검증할 수단이 없어** 그대로 화면에 그렸다. 게다가 3차 수정의 지문 대조가
`deployed and reported and ...` 라 **지문을 신고하지 않는 러너**(= 결함을 가진 바로 그
모집단)를 조용히 «최신» 으로 통과시켰다.

라이브 3중 대조: 러너 파일 `af7c3fe19808`(폴백 제거 이전) · 로그 「codex: 응답을 받지 못해
내장 기본값을 씁니다」 · DB `WebOAuthTokens.Id=83` 의 `RunnerCapabilities` 에
`gpt-5.1-codex`·`-mini`, `RunnerBuild=''`.

**변경**

- `shared/bridge_tasks.py`: `RUNNER_FEATURE_CAPS_SELF_REPORT = "caps_self_report"` 신설
  (자격 이름의 단일 정본). 버전·지문이 아니라 **기능 신고**를 축으로 고른 이유를 주석에 명시 —
  버전은 날짜 단위라 같은 날을 못 가르고(3차 재발의 원인), 지문은 동일성 축이라 게이트로 쓰면
  러너 파일을 고치는 **모든 배포**가 멀쩡한 사용자의 선택기까지 지운다.
- `unit/feature-0043-external-llm-bridge/src/bridge_agent.py` (+ 서빙 미러
  `unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py`): `AGENT_FEATURES` 에
  `caps_self_report` 추가.
- `unit/feature-0003-agent-web-ui/src/oauth_store.py`: `_caps_trusted()` 신설 +
  `account_runner_profile` 이 자격 없는 신고의 `capabilities` 를 빈 목록으로 내리고
  `caps_trusted` 를 함께 반환. **관문을 저장 계층에 둔 이유**는 능력 소비처가 셋
  (카탈로그·저장 선택 복원·얇은 래퍼)이고 뒤 둘이 모두 이 함수를 지나기 때문(§16.7 G8-a).
  `features`·`agent_version`·`listening` 축은 불변 — 콘솔 위임까지 끊지 않는다.
- `unit/feature-0003-agent-web-ui/src/routers/system.py`: `account_runner_capabilities` →
  `account_runner_profile` 로 바꿔 목록과 자격을 **한 행에서** 읽는다. `runner_caps_stale` ·
  `runner_download_url` 을 응답에 추가하고 `model_selector_reason` 을 상태별로 가른다.
- `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py`: `runner_build_is_stale()` 신설 —
  지문 판정의 **단일 정본**. 지문 부재를 stale 로 판정(fail-closed). 배포본 지문을 못 읽으면
  판정하지 않는다(거짓 경고 방지).
- `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py`: `connect_status` 가 자기 비교를
  버리고 위 단일 판정을 호출 — 종전엔 같은 술어가 2벌이었다.
- 프런트 `static/index.html`·`css/chat.css`·`app/composer.js`: 숨김 사유를 그리는
  `#composerActionsSelectorNote` 신설. `model_selector_reason` 은 2026-08-28 부터 응답에
  있었으나 **소비처가 0개**였다 — 값의 존재와 도달은 다른 사실이다.

**테스트**: 신규 12건 + 갱신 4건. §16.7 G11-b 실증 — 소스만 `main` 으로 되돌린 상태에서
**16건 전부 FAIL** 확인 후 복원. 구조 단정
`test_builtin_model_table_never_reaches_the_report` 는 git 이력의 실제 결함 빌드
(`82f3a160^` = `8766f0e6f32c`)에 걸어 `gpt-5.1-codex` 누출을 재현했다(내가 만든 뮤턴트 아님).


---

## CHG-20260901T140000-ai-claude-feature-0043-caps-trust-gate-r2 — 적대 패널 조치 (P1 7 · concern 8)

§18.8 패널 3인이 **CONCERN / BLOCK / BLOCK** 을 냈고, 그중 셋은 뮤턴트로 실증됐다. 전건 조치.

**저장 계층 (`oauth_store.py`)**
- `set_runner_report`: 능력을 싣지 못한 신고(`None`)를 `"[]"` 로 바꿔 **이전 능력을 무효화**
  한다. `COALESCE` 가 옛 목록을 남기는 동안 같은 문장이 `RunnerFeatures` 는 덮어써서, 구
  러너의 `gpt-5.1-codex` 가 새 러너의 계약 선언을 얻어 인증되던 경로(backend B1).
- `account_runner_build`: `str | None` **tri-state**. 조회 실패·컬럼 부재는 `None`(모름)이고
  로그를 남긴다. 종전엔 셋이 모두 `""` 라, 「지문 부재 = 더 오래됨」 판정을 켠 순간
  `RunnerBuild` 컬럼 없는 배포의 **최신 러너 사용자 전원**에게 거짓 갱신 지시가 나갔다.
- `account_runner_profile`: 살아 있는 행을 `RUNNER_ROWS_SCAN_MAX`(8)까지 읽고 **하나라도
  계약 미선언이면 능력을 내지 않는다**(fail-closed). 신뢰된 행 *선호* 는 기각 — 그 목록으로
  고른 모델을 실제로 가져가는 것이 미선언 러너일 수 있다. `mixed_runners` 로 「갱신은 했고
  옛 것을 안 껐다」를 구분한다.
- `token_runner_profile`: 같은 게이트 적용(두 번째 관문). `_parse_caps_column` 공용화.
- `_caps_trusted` → **`declares_caps_contract`** rename + **모듈 레벨 import**(미테스트
  `except` 분기 소멸). docstring 에 「인가 경계가 아니라 호환성 자기신고」를 명시.

**provenance 축 신설 (재발 클래스 봉인 — qa §3)**
- 러너 `detect_runtimes`: 신고 항목마다 `source` 를 싣고, **캐시 경로 포함** 신고 직전에
  `_REPORTABLE_SOURCES`(`probe`/`cache`/`ollama`)로 거른다. ollama 실조회는 `builtin` 이
  아니라 `ollama` 로 표기(아니면 게이트가 그 사용자 선택기를 지운다).
- 서버 `_sanitize_runtimes`: 같은 집합 `_SANITIZE_SOURCE_ALLOW` 로 **수신 시점** 거름.
  저장 스키마는 4키 유지(`source` 는 게이트용이지 저장값이 아니다). 구조 테스트가 양쪽
  집합의 동일성과 `builtin` 부재를 잠근다.

**표면·문서**
- `system.py`: `caps_contract_declared` 반영 + `runner_mixed` 응답 + 사유 3분기.
- `index.html`/`chat.css`/`composer.js`: `role="presentation"` + `aria-live`(무효 role 제거),
  **다운로드 링크 배선**(소비처 0 이던 필드), **카탈로그 부재 시에도 말한다**.
- `_console_llm.py`: `runner` dict 키 집합을 성공/실패 분기에서 동일하게.
- 러너 `detect_runtimes` docstring: 없는 폴백을 현재 동작으로 서술하던 문단 재작성(양 미러).

**테스트**
- `_func_source` 가 **docstring 줄만** 제거(자기 설명이 자기 단언을 통과시키던 구멍).
  `ast.unparse` 재출력은 포맷 정규화로 무관한 단언 15건을 깨 **불채택**.
- 이름 정합·단일 판정은 AST(`ImportFrom` 노드 · `connect_status` 안 단일 대입)로 격상.
- 프런트는 `tests/verify_selector_note.mjs`(jsdom 10케이스)로 동작 검증. **CI 는 pytest
  전용이라 이 하네스를 실행하지 않는다**(컨테이너에 node 부재) — 그 사실을 증적에 명시.
- 신규 커버리지: 화석 가드 · 다중 러너 · malformed features · 두 번째 관문 · 투영 함수 전수 ·
  provenance(수신·신고 양쪽) · cached/probe 두 분기 · ollama 실조회.
- **단언별 G11-b**: qa 가 생존시킨 뮤턴트 8종(M1b·M2b·M3·M4b·M7·M8·M9b·M-C2)을 다시 넣어
  **전부 FAILED** 확인. 하네스가 처음 M8 을 놓친 사실과 그 원인(빠진 경계 케이스)도 기록.

---

## CHG-20260901T190000-ai-claude-feature-0043-caps-trust-gate-r3 — §18.8 (b) 재설계: 전역 게이트 철회, provenance 로 수렴

> **위 두 항(`caps-trust-gate` · `-r2`)이 서술하는 설계는 이 항으로 대체됐다.**
> 무엇을 왜 되돌렸는지는 아래 「철회」 표에 있고, 남은 설계는 FUNCTION.md §P0-Z6 이다.

### 왜 패치가 아니라 재설계인가

§18.8 확인 라운드 3인(security·backend·qa)이 **CONCERN / BLOCK / BLOCK** 을 냈다. 결정적인
것은 판정 자체가 아니라 **모양**이었다 — P1 개수가 라운드에 걸쳐 줄지 않았고(security 3→4,
backend 4→4), 2라운드 P1 중 **넷은 1라운드에서 내가 넣은 수정이 만든 결함**이었다. §18.8
수렴 계약 (b) 는 이 모양을 「또 한 번 패치할 신호가 아니라 재설계 신호」로 정의한다.

내가 스스로 실증한 예 하나를 적는다: ollama 폴백 항목의 `source` 를 `"builtin"` 에서
`"ollama"` 로 바꾼 순간, 캐시 쓰기 가드(`!= "builtin"`)의 극성이 뒤집혀 **그 목록이 영구히
굳는** 새 결함이 생겼다(security B1). 고칠수록 결함이 생기는 자리였다.

### 철회

| 철회한 것 | 대체 | 사유 |
|---|---|---|
| 전역 자격 선언 `caps_self_report`(`AGENT_FEATURES`·`shared/bridge_tasks` 상수) | 런타임별 `source` | 「이 빌드가 계약을 아는가」에 답하는 불리언 하나라 다음 포맷 변경에 다섯 번째 이름이 필요하다 — 재발 클래스를 닫는 게 아니라 한 iteration 미룬다 |
| 읽기 시점 게이트(`oauth_store.account_runner_profile` 의 자격 판정 · `token_runner_profile` 게이트) | 수신 시점 `_sanitize_runtimes` | 수신 시점 필터가 **첫 하트비트에** 낡은 목록을 지운다. 읽기 시점 게이트가 추가로 만드는 것은 「목록이 멀쩡한데도 잠기는」 상태뿐이었다 |
| 다중 러너 fail-closed + `mixed_runners`·`runner_caps_stale` 응답 필드 | — (제거) | 그 잠금에 **제품 안의 해제 수단이 없었다**. 옛 러너를 끄는 것은 사용자 머신에서만 가능하다 |
| `RUNNER_ROWS_SCAN_MAX` 다중 행 스캔 | 단일 행(`LastHeartbeatAt DESC LIMIT 1`) 복귀 | 위 규칙이 사라지면 여러 행을 읽을 이유가 없다 |
| 과대 신고 화석 가드(`set_runner_report` 의 저장 거부) | 잘라 저장 + `warning` 로그 | 저장하지 않으면 **직전 목록이 그대로 남는다** — 화석을 막으려던 가드가 화석을 보존한다 |
| 로컬 LLM(ollama) 런타임 전체 | — (제거, 사용자 결정) | 로컬 LLM 미사용. 남겨 두는 비용이 문서적이지 않았다(위 B1) |

### 남긴 것 · 고친 것

1. **런타임별 provenance 가 유일한 자물쇠다.** 러너가 항목마다 `source`(`probe`/`cache`/
   `builtin`)를 싣고, 러너(`_REPORTABLE_SOURCES`)와 서버(`_SANITIZE_SOURCE_ALLOW`)가 같은
   allowlist `{probe, cache}` 로 거른다. 단위가 런타임 하나라 나쁜 것만 떨어진다.
2. **기본값 fail-closed.** `sanitize_caps` 는 출처가 없으면 지어내지 않는다. 종전 판본은
   `"cache"` 를 기본값으로 넣었는데 **아무 writer 도 그 값을 쓰지 않아** 기본값이 곧 유일한
   값이었다 — 게이트 전체가 fail-open 이었다(backend 적대리뷰가 실증).
3. **출처를 모르는 캐시는 「캐시 없음」이다** — `detect_runtimes` 진입부에서 걸러 다시 묻는다.
4. **지문 판정 사본 3 → 1.** `ai_ops._runner_roster` 가 `deployed` 를 직접 비교하던 세 번째
   사본을 `runner_build_is_stale` 호출로 바꿨다(backend B2-R1: 그 상태에서 이 결함을 분류할
   운영 콘솔만 경고를 안 띄우고 있었다).
5. **사유는 러너가 듣고 있는가 하나로 갈린다** — `system.py` 3분기(표시 / 듣는데 목록 없음 /
   러너 없음). 러너가 없을 때는 **다운로드 링크를 주지 않는다**(다음 행동은 연결이다).
6. **안내 `<p>` 를 `role="menu"` 밖으로.** 메뉴 자식의 `role="note"`·`aria-live` 는 ARIA
   presentational-roles-conflict-resolution 으로 **무효화된다** — 배선은 됐는데 보조기술에는
   도달하지 않는 상태였다.

### 파일

- `unit/feature-0043-external-llm-bridge/src/bridge_agent.py`(+ 미러 `…/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py`, byte-동일): ollama 전면 제거 · `AGENT_FEATURES` 원복 · provenance 게이트 · `sanitize_caps` fail-closed · 캐시 필터
- `unit/feature-0003-agent-web-ui/src/oauth_store.py`: 읽기 시점 게이트·화석 가드 철회 · `account_runner_build` tri-state · 과대 신고 경고 로그
- `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py`: `runner_build_is_stale` 단일 판정 · `_SANITIZE_SOURCE_ALLOW`
- `unit/feature-0003-agent-web-ui/src/routers/system.py`: 단일 축(`runner_listening`) + 사유 3분기
- `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py`: 세 번째 사본 통합
- `unit/feature-0003-agent-web-ui/src/static/{index.html,app/composer.js}`: ARIA 자리 이동 · 사유·링크 배선
- `shared/bridge_tasks.py`: `RUNNER_FEATURE_CAPS_SELF_REPORT` 제거

### 검증

- `make test` — **6,913건 수집 / 6,898 passed · 15 skipped · 0 failed** · ruff `All checks passed!`
  (origin/main 68 커밋 재병합 후 실행).
- **뮤턴트 봉인 (§16.7 G11-b, 실측)**: qa 적대리뷰가 생존시킨 변형을 다시 넣어 exit code 로 확인.
  `M4b-v1`(`runner_stale: bool = False`) · `M4b-v2`(`if (runner_stale := False): pass`) 는
  **봉인 전 EXIT=0(생존)** 이었다 — 「모든 바인딩 형태를 모으고 나머지는 상수」까지 봐도
  **순서**를 안 보면 마지막 값이 판정을 이긴다. 호출이 자기 갈래의 마지막인지까지 보도록
  고친 뒤 4변형(`AnnAssign`·`NamedExpr`·상수 인자·주석 처리) + 꼬리 덮어쓰기 1종이 **전건
  EXIT=1(KILLED)**, 정상 소스는 EXIT=0. `M7-v2`(`AGENT_FEATURES + ("admin_jobs",)`)도 KILLED.
- 미러 byte-동일성은 `test_bridge_agent_sync` 가 잠근다.

---

## CHG-20260902T113000-ai-claude-feature-0043-caps-trust-gate-r4 — codex 확인 라운드 조치 (P1 1 · P2 2)

§18.8 확인 라운드를 **codex 채널**로 대체했다(사용자 결정 — Agent 패널 1회 허용은 소진).
지적 3건 모두 **재현 확인 후** 수정했고, 각각 뮤턴트로 실증했다. 판단 근거는
`REVIEW.md` 의 `REV-20260902T113000-…-r3 [CODEX:review]`.

### 변경 내용

1. **`oauth_store.set_runner_report` — 지문 컬럼 없이 재시도** (P1).
   `RunnerBuild` 컬럼이 없는 배포에서 통합 UPDATE 가 통째로 실패하면, 하트비트 핸들러가
   예외를 삼키는 동안 `LastHeartbeatAt` 만 갱신되고 **`RunnerCapabilities` 는 옛 값 그대로**
   남는다 — 이 cycle 이 닫으려는 화석 목록이 그 모집단에서만 영구히 살아남는 형태다.
   지문 축(`account_runner_build`)은 그 배포를 **명시적으로 지원**(`None` = 판정 안 함)하는데
   쓰기 축만 지원하지 않던 비대칭을 없앤다. 한 단 내려가 **능력·기능·버전 세 축은 반드시**
   새긴다 — provenance 필터의 전제가 여기 걸려 있다.
2. **`oauth_store.list_live_runners` — 하트비트 없던 행은 `None`** (P2).
   운영 명부는 러너가 아닌 토큰(등록형 MCP 클라이언트 등)도 일부러 포함하는데, 그 행의 빈
   지문을 「구 러너」로 읽어 **러너를 띄운 적도 없는 계정**에 갱신 지시가 붙었다. 판정 통합
   전에는 복제된 식이 `""` 를 stale 로 보지 않았으므로 **내 통합이 만든 오탐**이다.
3. **`composer.js._composerModelSelectorHidden` — 카탈로그 부재 = 숨김** (P2).
   종전엔 `undefined !== "hidden"` 이라 「보임」이었고, 그래서 카탈로그 fetch 실패 화면이
   **목록 없는 선택기 + 서버 기본값 라벨**을 내보냈다. 같은 이유로 「모델 목록을 불러오지
   못했습니다」 분기가 **도달 불가능한 죽은 코드**였다 — 그 분기를 jsdom 하네스가 **직접
   호출**해 통과시키고 있었다(진입점을 통과하지 않는 vacuous pass).
4. **jsdom 하네스 재작성** — 진입점(`_applyComposerSelectorVisibility`)을 함께 들고 와
   케이스 6 을 그 경로로 구동한다. 10 → **11 케이스**.
5. 신규 테스트 3건 + 뮤턴트 3종 KILLED 실증(exit code).

### 발효

서버 축은 배포 즉시. 러너 파일은 이 항에서 바뀌지 않는다(재다운로드 불필요).
## CHG-20260902T110000-ai-claude-runner-modularization — 러너 모듈 분할 + 배포본 이중화 제거

**요청**: 브리지 러너 개발 시 작업자AI 간 충돌이 빈번 → 관련 스크립트 모듈화 (사용자, 2026-09-02)

### 변경

| 경로 | 변경 |
|---|---|
| `unit/feature-0043-external-llm-bridge/src/agent/` | **신설** — 러너 정본 18 모듈 (`__init__` 포함). `_EMIT_ORDER` 가 번들 방출 순서 단일 정본 |
| `unit/feature-0043-external-llm-bridge/src/agent/state.py` | **신설** — 러너 인스턴스 가변 전역 + 접근자 3종 (`runner_instance`/`prev_runner_instance`/`set_runner_instance`) |
| `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py` | **신설** — 패키지 → 단일 파일 번들러 (`--stage-assets`·`--check`) |
| `unit/feature-0002-agent-core/src/Dockerfile` | 러너 소스 COPY + 빌드 RUN 추가 (자산 스탬프 계산 **앞**에 배치 — 종전 content-hash 범위 보존) |
| `bin/deploy-web.sh` | `bridge_runner_verify` 게이트 신설 + 롤링 직전 호출 |
| `conftest.py` (루트) | collection 전 배포 산출물 배치 (테스트 37개가 모듈 수준에서 경로를 상수로 잡으므로 fixture 로는 늦다) |
| `Makefile` | `bridge-agent` 타깃 신설 (`.PHONY` 등재) |
| `.gitignore` | 생성물 4개 등재 |
| `unit/feature-0043-external-llm-bridge/src/bridge_agent.py` | **git 추적 해제** (생성물) |
| `unit/feature-0003-agent-web-ui/src/static/agent/{bridge_agent.py,bridge_setup.sh,bridge_setup.ps1}` | **git 추적 해제** (생성물) |
| `unit/feature-0043-external-llm-bridge/tests/test_bridge_agent_sync.py` | 계약 교체 — 「정본↔배포본 동일」(동어반복화)  → 재현성·결정성·`_EMIT_ORDER` 전수·비순환·Dockerfile 배선·배포 게이트·무시 규칙 7종 |
| `unit/feature-0043-external-llm-bridge/tests/test_orphan_claim_reclaim.py` | 점유 인스턴스 축 단언을 접근자 표현으로 갱신 (계약 동일) |
| `unit/feature-0043-external-llm-bridge/src/README.md` | 소스 레이아웃·편집 절차·제약 문서화 |

### 발효

즉시(빌드 시점). 사용자가 내려받는 러너의 **동작은 변하지 않는다** — 산출물 diff 는
4,267행 중 57행이고 전부 ① 접근자 전환 12곳 ② `state` 블록 이동 ③ PEP8 빈 줄 2곳이다.
`_self_build()` 지문은 바뀌므로 기존 러너는 다음 하트비트에서 `runner_update` 안내를 받는다
(정상 경로 — 재설치하면 해소).

### 되돌리기

`git revert` 로 충분하다. 생성물이 커밋되지 않으므로 되돌린 트리에서도 `make bridge-agent`
(또는 이미지 빌드)가 종전과 같은 단일 파일을 만든다. 단 revert 시 `.gitignore` 항목이 함께
사라지므로 로컬 생성물을 먼저 지운다(`rm` 후 체크아웃).
## CHG-20260902T120000 — 재실행이 파일을 바꾸지 못하는 상태를 이름 붙여 내보낸다

### 무엇을 바꿨나

1. **`routers/oauth_as.py::connect_status`** — 응답에 `runner_build` 를 싣는다.
   `runner_stale` 만으로는 「다시 띄웠는데 같은 파일이 다시 떴다」와 「다른 파일로 바뀌었는데
   그것도 낡았다」가 구별되지 않는다. 전자는 **재실행으로는 영영 풀리지 않는** 상태다.
   판정은 여전히 서버가 내고(`runner_stale`), 이 값은 **동일성 축에만** 쓴다 — 화면은
   표시하지 않는다. 판정이 실패한 조회는 지문도 `None` 으로 거둔다(반쪽 사실 금지).
2. **`static/app/connect-modal.js`** — 실행을 쏘기 직전의 지문을 잡아 두고, 대기창이 끝난 뒤
   `_relaunchChangedNothing(before, now)` 로 대조한다. 참이면 `_relaunchNoUpdate` 증거를
   세우고 문구를 바꾼다. `_showRelaunchNoUpdate()` 는 창을 열고 **발급까지 대신 눌러** 1단계
   명령을 화면에 세운 뒤 그 사유를 말한다(겹쳐 부르면 토큰이 쌓이므로 in-flight 잠금 동반).
   증거가 있으면 `_connectEntry`·`_maybeAutoEntry` 는 실행을 쏘지 않고 곧바로 그 안내로 간다.
   증거는 **지문 변화** 또는 **최신 도달**로 해제된다.
   자동 실행과 [내 AI 실행] 이 **같은 판정 함수**를 쓴다 — 두 벌이면 같은 상황에 다른 설명을 한다.
3. **`static/index.html` · `css/chat.css`** — `#composerActionsSelectorNote` 를 `.composer-box`
   밖(`.composer-wrap` 안, 입력창 바로 위)으로 옮기고 단독 줄에 맞는 여백으로 바꿨다.

### 왜 (3) 이 결함이었나

`.composer-box` 는 `display:flex` 한 줄이고 형제인 두 팝업은 `absolute`/`fixed` 라 줄에서
빠져 있다 — 이 `<p>` 만 정적 흐름이라 **플렉스 항목**이 되어 입력창을 밀어냈다. 앞 cycle 이
`role="menu"` 제약을 피해 문단을 메뉴 밖으로 꺼냈지만, **그 이동이 배치까지 옮겨 주지는
않았다**. 제약을 만족시킨 자리가 레이아웃상 어떤 자리인지는 별도로 확인해야 하는 사실이다.

### 발효

서버·화면 축은 배포 즉시. **런처 자기 갱신은 이 항에서 바뀌지 않는다** — 이미 설치된 구
런처를 원격으로 되살릴 방법은 없고(러너에 자기 갱신 없음), 1회 재설치 뒤부터 자동이다.
이 변경은 그 1회가 **어디에 있는지 화면이 정확히 지목하게** 만드는 것이다.
## CHG-20260902T120000-ai-claude-runner-modularization-postdeploy — POST-DEPLOY 실측 기록

문서 전용(코드 변경 0). 배포 `ae02c3e1` 후 직전 cycle 의 잔여 검증 항목을 실측하고 기록했다.

| 경로 | 변경 |
|---|---|
| `docs/test-runs.d/TASK-20260902T120000-…-postdeploy.md` | **신설** — 게이트 판별력(양측)·baked 실물·도달성·실행·무중단 |
| `docs/TASK.md` | POST-DEPLOY cycle 섹션 + Requested Scope 이행 대조 |
| `docs/REPORT.md` | 현재 상태의 「잔여: POST-DEPLOY」를 실측 결과로 대체 |


## CHG-20260902T123000 — 화면이 서버 응답을 못 읽던 소비 계약 위반

**계기**: 직전 cycle 배포 후 PB-0008 실측 — 「AI 작업」 탭이 열리는데 항목 0개.

**원인**: `apiFetch` 는 파싱된 payload 를 반환하는데(비-2xx 는 자기가 throw) 새 로더가 그것을
Response 로 오인해 `res.json()` 을 불렀다. **정상 200 에서 예외**가 나고 catch 가 그것을
「불러오지 못했습니다」로 바꿔, 서버·단위 테스트 어느 쪽도 이상을 보고하지 않았다.

**변경**: 로더·저장이 payload 를 직접 소비. 재발 방지는 **소비 계약**을 작업 화면 번들 전역에
잠그는 정적 검사(`apiFetch` 결과에 `.json()`/`.ok` 금지) — 주석 제외, `.status` 는 본문 필드로
정당하므로 축에서 제외.

## CHG-20260902T130000 — POST-DEPLOY 실측 기록 (문서 전용)

`CHG-20260902T120000` 의 배포 후 검증을 test-run 조각에 기록. 배포 `293a20c8` 실 Windows
브라우저에서 **안내 켜짐에도 입력창 밀림 0px**(배포 전 −471px) · 문단 부모 `composer-wrap` ·
새 심볼 적재 · `runner_build` 응답 존재 · **서빙 JS = 테스트한 소스**(자산 스탬프 1줄 외 동일).

라이브에서 닫지 못한 것도 함께 적었다 — 「같은 지문 재기동 → 새 안내」는 계정에 **낡은
러너가 떠 있어야** 성립하는데 지금은 `listening=false` 이고, 그 러너를 대신 띄우는 것은
사용자 환경을 손대는 일이라 하지 않았다. 코드 변경 없음.
## CHG-20260902T140000 — Windows 명령줄 상한이 그 계정의 모든 답변을 죽이고 있었다

**계기**: 사용자 제보 — *"powershell 을 통한 연결이 수행되었지만, 실제 assistant 요청을 보내도
답변이 오지 않고 러너 로그에도 별도의 기록이 쌓이지 않는다"*.

**원인 2건** (제보의 두 절반이 서로 다른 결함이었다):

1. **`[WinError 206]`** — 운영자 지침 34,962자가 `--append-system-prompt` 로 **인자에** 실려
   Windows `CreateProcess` 상한(32,767)을 넘었다. 사용자 머신에서 경계 실측: 32,600 성공 /
   33,000 실패(러너 원장과 동일 예외). 그 계정의 **모든** 질문이 spawn 단계에서 죽고, 예외
   문자열이 답변 말풍선에 그대로 실렸다. POSIX 는 `ARG_MAX` 2MB 라 **Windows 전용 divergence**.
2. **기동 240초 침묵** — 능력 협상이 하트비트·대기보다 앞에 있고 실패해도 데드라인을 전부
   소진한다. 그 4분간 하트비트·로그·질문 수신이 **전부 0** 인데 설치 스크립트는 2초 뒤
   「완료」를 선언한다. 실패한 협상은 캐시되지 않아 재기동마다 반복된다.

**변경**:

| 파일 | 무엇 |
|---|---|
| `src/agent/invoke.py` | `_cmdline_len`(Windows 는 `list2cmdline` 으로 정확히) · `_cmdline_budget` · `_stdin_form` · `_fit_cmdline` · `system_channel_fits` · `_run_cli_cancelable(stdin_text=…)` · `_CMDLINE_OVERFLOW_MSG` |
| `src/agent/runtimes.py` | claude·codex 에 `stdin_ok`/`stdin_arg` 선언 (라이브 실측 기반) |
| `src/agent/handler.py` | 지침이 인자에 안 들어가면 본문으로 접는다 (`system_channel_fits`, 조립 **전** 판정) |
| `src/agent/lifecycle.py` | 하트비트·대기를 협상보다 **먼저**, 협상은 배경 스레드 + 신고 목록 제자리 갱신 |
| `src/agent/caps.py` | 협상 실패 **사유**를 `reason_out` 으로 올려 로그에 싣는다 |
| `tests/test_cmdline_length_limit.py` | **신규 14건** — 예산·stdin·overflow·배선·실 subprocess 왕복 |
| `tests/test_startup_not_blocked_by_caps.py` | **신규 2건** — 협상 중에도 대기·하트비트가 살아 있는가 |
| `tests/test_injection_false_positive.py` · `tests/test_runtime_model_selector.py` | 테스트 더블 시그니처 갱신 + 소스-문자열 단정 1건을 **행위 단정으로 재작성** |

**폴백 순서**(「지침을 온전히 넘기는 것」보다 「답이 오는 것」이 먼저다): 시스템 채널 →
(넘치면) 본문으로 접기 → 질문을 stdin 으로 → (그래도 넘치면) 행동 가능한 실패 문장.
정상 크기·POSIX 는 **종전 경로 그대로**.

**stdin 은 실측이다**: `printf … | claude -p --strict-mcp-config` · `codex exec
--skip-git-repo-check -` 양쪽 rc=0 확인. claude 는 자리를 비우고 codex 는 `-` 를 남긴다.
`gemini` 는 확인하지 않았으므로 선언하지 않았다(그 런타임은 정직한 실패로 간다).
## CHG-20260902T130000 — 수정 배포 후 화면 재실측 (증적)

`CHG-20260902T123000` 배포본(`5c02495f`)에서 같은 경로를 다시 밟아 결함 해소를 확인했다:
항목 6종 렌더(직전 0개) · 저장값 복원 · 러너 부재 시 저장값 보존 · 사유 표시 · UI 저장 왕복.
코드 변경 없음 — 증적 기록만(`unit/feature-0003-agent-web-ui/docs/test-runs.d/`).

**정직 표기**: 이 계정의 러너 토큰이 만료돼 「러너 연결 상태의 선택지 렌더」는 재현하지 못했다.
서버 판정은 살아 있는 러너의 실 신고로 검증했고, 화면 축은 「러너 없음」 상태만 실측했다.
## CHG-20260902T160000 — 프로필 'AI 작업' 탭을 계정 권한으로 추린다

사용자 요청(2026-09-02): 「'AI 작업' 탭에서 **실제로 해당 계정이 접근할 수 있는 기능**에 대해
권한을 소유한 경우에만 노출」.

종전 `GET /api/profile/console-jobs` 는 `JOB_SPECS` **전량**을 무조건 돌려줬다. `metadata.*` 나
`metadata.graph.analyze` 가 없는 계정에도 그 항목이 보였고, 모델을 골라 저장까지 되지만 정작
그 기능을 여는 엔드포인트가 403 이라 **작업이 오지 않는다** — 화면은 「설정됨」이라고 말하고
사용자는 원인을 알 수 없다.

| 파일 | 변경 |
|---|---|
| `shared/bridge_tasks.py` | `JOB_SPECS[*]["perms"]`(any-of) 6종 전수 선언 + `console_job_perms` · `visible_console_job_kinds` 신규 (+`__all__`) |
| `unit/feature-0003-agent-web-ui/src/routers/profile.py` | `_visible_console_job_kinds(account)` 헬퍼 · GET 은 추린 목록만 순회 · PUT 은 가시 범위로 교체 한정 + 비가시 종류 보존 + 응답 필터 |
| `unit/feature-0003-agent-web-ui/src/static/app/profile.js` | 0 항목 빈 상태 문구 + `_aiJobsSetEmpty`([저장]·[모두 기본값] 비활성) · **로드 실패 시에도 저장 차단** |
| `unit/feature-0043-external-llm-bridge/tests/test_ai_jobs_perm_gate.py` | **신규 42건** — 선언 전수·카탈로그 대조·any-of·순서 · **병합 행위 12건**(실 dict) · **레거시 묶음 함의 2건** · GET/PUT 배선 · 프런트 |

**권한 매핑**(집행 지점의 거울 — 새 권한 코드 0):

| 종류 | perms (any-of) | 집행 지점 |
|---|---|---|
| `metadata_suggest` | `metadata.{glossary,enum,table,column}.update` · `kb.sample.curate` | `_METADATA_SUGGEST_PERM` (서브뷰별) |
| `metadata_bulk` | `metadata.table.update` | `admin_metadata_bootstrap_describe` |
| `node_analysis` | `metadata.graph.analyze` | `admin_metadata_graph_analyze` |
| `prompt_generate` | **()** | 개인 프롬프트 자동작성은 로그인만 요구(`_collect_account_prompt_context`) |
| `insight_summary` · `cluster_label` | **()** | 배경 배치 — `_batch_consenting_account`(RBAC 아닌 **동의** 축) |

**PUT 이 「통째 교체」를 가시 범위로 좁힌 이유**: 전체 집합에 적용하면 권한이 빠진 계정의 저장
버튼 한 번이 숨겨진 항목의 기존 선택을 지운다. 권한은 되돌아올 수 있지만 설정은 돌아오지 않는다.
화면은 자기가 그린 것만 소유한다.


**동반 수정 (같은 불변식, 1줄)**: `loadAiJobs` 의 실패 경로도 저장을 막는다. 목록을 못 받은
상태의 [저장] 은 **빈 본문**을 보내는데, 서버는 그것을 「보이는 항목을 전부 비웠다」로 읽어
사용자의 선택을 지운다. 「보이는 것이 저장되는 것」 계약에서 «아무것도 못 봤다» 와 «전부 비웠다»
가 같은 모양이 되는 지점이라, 막는 자리는 프런트다. (변경 전에도 있던 경로지만, 이 cycle 이
세우는 「빈 목록에서 저장 버튼이 해를 끼치지 않는다」 불변식과 같은 자리라 함께 닫았다.)

**적대 리뷰(codex) 1R 조치 3건** — 상세는 `REVIEW.md` 의 적대 리뷰 원장:

| 파일 | 변경 |
|---|---|
| `shared/bridge_tasks.py` | `merge_visible_console_job_prefs`(정규화→가시성 필터 순서를 담은 정본 병합) · `_safe_has_permission`(권한 판정 예외를 **코드 단위**로 가둠 — 전면 실패해도 「요구 없는 종류만」으로 축소되고 화면은 산다) |
| `shared/bridge_tasks.py` (2R) | `read_console_job_prefs_strict` — 저장 baseline 전용 **엄격 읽기**. lenient 판은 조회 실패를 `{}` 로 돌려주는데(읽기 경로에서는 옳다) 그것을 쓰기 baseline 으로 쓰면 「보존할 것이 없다」로 오인해 숨긴 항목을 지운 문서를 쓰고 200 을 준다 |
| `.../static/app/profile.js` (2R) | 첫 성공 렌더 전까지 [저장]·[모두 기본값] 비활성 — 로딩 **중** 에도 `{}`(=전부 지우기)가 나갈 수 있었다 · **요청 세대 토큰**(`_aiJobsReqSeq`)으로 겹친 요청의 stale 응답 무시(옛 응답이 방금 저장한 값을 되돌리고, 그 상태의 재저장이 stale 을 굳혔다) |
| `.../routers/profile.py` | PUT 이 본문·`jobs` 의 dict 여부를 검사해 **400 거절**. 파싱 실패를 `{}` 로 흘리지 않는다 — 「의도한 비우기」와 「깨진 본문」이 서버에서 같은 모양이면 사고가 200 을 받고 조용히 지운다. 병합은 정본 함수에 위임(라우터 중복 구현 제거) |

**표시 축이지 집행이 아니다**: 각 기능의 서버 게이트는 종전 그대로다. 이 필터가 무엇을
통과시키든 권한 없는 계정이 그 기능을 부를 수는 없다.
## CHG-20260902T150000 — POST-DEPLOY 실측 기록 (문서 전용)

`CHG-20260902T140000` 의 배포 후 검증을 test-run 조각에 기록. 배포 `66769688` — 전 서비스
(web 2 · mcp 2 · worker 3) SHA 일치 · `no upstreams available` **0건** · RestartCount 0 ·
surge 잔존 0 · 대화 스모크 PASS.

핵심은 심볼 존재가 아니라 **배포본의 동작**을 확인한 것이다: 엣지에서 내려받은 바이트를
모듈로 적재해 라이브 실측 크기(지침 34,962 · 접힌 본문 38,456)로 6축 검증 — Windows 예산
30,719 · 34,962자 지침 채널 부적합 판정 · stdin 전환 · **자식이 실제로 읽은 38,456자** ·
gemini `overflow`(예외 대신 정직한 실패) · POSIX 무회귀. 내려받은 sha256 = 이미지 산출물 일치.

닫지 못한 것도 그대로 적었다 — 러너는 **사용자 머신의 파일**이라 새 사본을 받아 재기동해야
발효하고(서버가 바꿀 통로 없음), 그 머신 `claude` 는 로그인 만료 상태다(사용자 영역).
코드 변경 없음.
## CHG-20260902T160000 — 자식 입출력 인코딩을 로케일에 맡기지 않는다 (직전 수정이 연 실패면)

**계기**: 사용자 재보고 — 재연결 후에도 답변 미수신. 직전 cycle(`CHG-20260902T140000`)의 두
수정은 라이브에서 동작했으나(`startup_ms=811` · `system_channel.folded` · `cmdline.stdin`),
그 자리에서 `ai.fail dur_ms=46 stdout_bytes=0` 로 죽었다.

**진단 단서**: `ai.fail` 에 **`exit` 필드가 없다** = `proc.returncode is None` = 자식이 실패한
것이 아니라 **파이프 스레드가 예외로 죽었다**.

**원인**: `subprocess(text=True)` 는 로케일 인코딩을 쓴다. 사용자 머신
`locale.getencoding()=cp949` 이고 프롬프트의 `⟦USER-REQUEST⟧`(U+27E6)는 cp949 로 인코딩
불가 → `UnicodeEncodeError`. 종전에는 프롬프트가 argv(`CreateProcessW`, UTF-16)로 가서 이
경로가 닫혀 있었고, **직전 cycle 이 stdin 으로 옮기며 처음 열렸다**.

**변경**:

| 파일 | 무엇 |
|---|---|
| `src/agent/base.py` | **신규** `CHILD_TEXT_IO = {text, encoding="utf-8", errors="replace"}` — 자식 호출 규약 단일 정본 |
| `src/agent/invoke.py` | 자식 호출 3곳 적용 + `pump_exc`(파이프 예외 보존 → `ai.io_fail`) + `returncode is None` 전용 분기 |
| `src/agent/caps.py` | 능력 협상·`--help` 2곳 적용(읽기 축의 같은 지뢰) |
| `tests/test_child_io_encoding.py` | **신규 8건** — 규약·전수 적용·실 왕복·한글 무손상·깨진 바이트 관용·예외 비위장·rc None |

**실 Windows(cp949) 대조 검증**: 수정본은 40,000자(U+27E6 포함) 왕복 PASS + 한글 무손상,
수정 전 `text=True` 대조군은 같은 지점에서 `UnicodeEncodeError`.
## CHG-20260902T140000 — 러너 자기 갱신 + 화면의 낡음 접기

1. **`agent/selfupdate.py`**(신규) — 배포본 수신·검사·원자 교체·재기동. 규율은 정본 TASK 노트 §3.
2. **`agent/lifecycle.py`** — `_SELF_UPDATE` 신호(하트비트) + `try_self_update()`(대기 루프,
   «물러남 → 갱신 → 대기» 순) + `--no-self-update` + 능력 판정(`_SELF_UPDATE_OK`).
   `stale_build` 경고는 **스스로 못 고칠 때만** 찍는다.
3. **`agent/api.py`** — `Api.ca` 보존. 자기 갱신이 **같은 신뢰 앵커**로 받아야 하는데
   `ctx` 만 남기면 CA 를 다시 실어 날라야 하고, 그러면 한쪽만 바뀌었을 때 조용히 OS 신뢰
   저장소로 떨어진다.
4. **`shared/bridge_tasks.py`·`agent/events.py`** — `self_update` 기능 이름(양쪽 같은 값).
5. **`oauth_store.py`·`routers/oauth_as.py`** — `account_runner_self_updating()` →
   `connect_status.runner_self_updating`. 정본 러너 선택 축은 `account_runner_build` 와 **동일**.
6. **`static/app/connect-modal.js`** — `_actionableStaleOf()` 한 곳에서 접는다.

### 왜 «판정은 그대로, 조치만 자동화» 인가

사용자가 웹 리서치 결과를 보고 고른 조합이다. 지문 일치는 정확하지만 러너 파일이 거의 모든
배포에서 바뀌어 **무관한 배포**에도 참이 된다(실측: 재설치 3분 뒤 다른 세션 배포가 착륙해
「업데이트 필요」 재발 + 연결 모달 고착). 판정을 무르게 하는 대신 조치를 자동화하면 두 문제가
함께 사라지고, 엄격한 판정의 값어치(정확히 그 파일인가)는 그대로 남는다.

### 발효

**이 기능이 들어간 빌드부터**. 지금 도는 러너는 한 번 런처가 갈아 끼워야 하고(그 경로는
`CHG-20260902T100000` 에서 동작 확인), 그 뒤로는 배포가 몇 번을 나든 화면에 조치 요구가 뜨지 않는다.
## CHG-20260902T173000 — 'AI 작업' 권한 게이트 POST-DEPLOY 실측 (증적)

코드 변경 없음. 배포 `2a910ddb` 후 라이브 재실측 증적만 기록한다 —
`operator` 6행→**3행** · `admin` **6행 유지** · fail-open 차단 · 400 검증 ·
**비가시 항목 보존**(권한 부여→저장→회수→빈 저장→재부여 왕복에서 `claude:haiku/high` 생존).
검증 계정 `dqa_permgate_probe` 는 override 제거 + 비활성화로 정리했다.
증적: `unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260902T160000-ai-jobs-perm-gate.md §2`.

## CHG-20260902T150000 — POST-DEPLOY 실측 기록 (문서 전용)

`CHG-20260902T140000` 의 배포 후 검증. 배포 `a46727a2`.

- 화면·API 축: `runner_self_updating` 필드 존재 · 서빙 JS 심볼 5건 · 배포 러너에 자기 갱신
  코드 전량 적재.
- ⭐ **라이브 서버 상대 갱신 경로 5단계 실측**(수신·평문 거절·원자 교체·자기 인식·무한 고리
  차단). `/static/agent/bridge_agent.py` 가 공개 정적 경로라 **토큰 없이, 사용자 러너에
  영향 없이** 전 구간을 돌릴 수 있었다.
- ⚠ 배포 창에 `no upstreams available` **16건(12초)**. soak 는 통과 보고 — 그 게이트는 blip 을
  관용하므로 「성공 = 무중단」이 아니다. 코드 변경과 무관한 엣지/롤링 축이나 사실로 남긴다.

코드 변경 없음.

## CHG-20260902T170000 — 자식 입출력 인코딩 POST-DEPLOY 실측 (문서 전용)

`CHG-20260902T160000` 의 배포 후 검증. 배포 `1e394a14` — 전 서비스 SHA 일치 ·
`no upstreams available` 0건 · 대화 스모크 PASS · 서빙 러너에 수정 심볼 전건 존재.

정본 증거는 **실 Windows(cp949) 대조 검증**이다: 내려받은 배포본 바이트를 사용자 머신에서
그 로케일로 적재해 40,000자(U+27E6 포함)를 왕복시켜 PASS, 같은 조건의 수정 전 대조군은
`UnicodeEncodeError`. 대조군이 없으면 「PASS 가 이 수정 덕분」임을 말할 수 없다.

병합 변형 점검: 형제 cycle(#1522)의 `selfupdate.py` 가 전 구간 바이너리 모드임을 확인해
인코딩 축과 상호작용이 없음을 검증. 코드 변경 없음.
## CHG-20260902T180000-insight-apply-write-semantics — 라이브가 드러낸 반영 결함 2건

배경 배치를 **실제로 태우자** `insight_summary` 반영이 실패했다:
`저장 중 오류: name '_log' is not defined`.

### 1. 성공 경로에 `NameError` 가 있었다 (테스트가 거절 경로만 돌렸다)

`insight.py` 는 `_log` 를 **함수 안에서 지역으로** 만든다(모듈 레벨에 없다). 내가 추가한 두
함수는 그 이름을 그냥 참조했고, **거절 경로(payload 없음 → ValueError)만 테스트해서** 성공
경로가 한 번도 실행되지 않았다 — 전건 green 인 채로 배포됐고 라이브에서만 드러났다.

*예외를 던지는지 보는 것과 끝까지 도는지 보는 것은 다른 검사다.* 두 반영 함수의 **성공
경로를 실제로 구동하는** 테스트를 추가했다.

### 2. 더 나쁜 것 — 조용히 안 써도 "성공" 이었다

`save_memory_kv` 는 `conn` 인자를 쓰지 않고 자기 PG 연결을 열며, **실패하면 경고만 남기고
넘어간다.** 그 관대함은 그 함수의 다른 소비처(heartbeat·topic 처럼 다음 주기에 덮어써지는
값)에는 맞다. 그러나 여기는 **쓰기 축**이다 — 반영하지 못했는데 성공으로 접으면 콘솔은
"완료" 라 말하고 값은 어디에도 없으며, 다음 cycle 이 같은 작업을 사용자 계정 토큰으로
**다시 산다**.

되읽어 확인하고, 없으면 예외로 올려 작업 행에 사유를 남긴다.

### 알려진 한계 (수정 안 함)

개인 AI 가 `{"labels":[]}`(라벨할 것 없음)를 돌려주면 `cluster_label` 반영이 「유효한 라벨이
하나도 없습니다」로 실패 기록된다. 침묵보다는 낫지만, 그 배치는 다음 pass 에 다시 적재된다 —
**비용 성질은 전환 이전(서버 LLM 시절)과 같다**(그때도 캐시 미스로 재호출됐다). 재설계는
별건으로 둔다.
## CHG-20260902T140200-caps-live-sync — 능력 신고의 라이브 도착 + 계정 원장

사용자 제보 2건(2026-09-02): ① 러너가 신고한 모델·추론등급 목록이 새로고침 전까지 화면에
갱신되지 않아 체감 대기가 길다 ② 러너 실행마다 모델 종류가 일정하지 않다(플랫폼별 캐시 +
재연결 시 검증 요청).

### 무엇을 고쳤나

**① 갱신 신호를 «전이» 에서 «변화» 로.** 카탈로그 재조회 계기가 `onComposeGateChange`
(컴포저 잠금 **전이**) 하나였다. 러너는 능력 협상을 배경에서 돌리므로(질문 처리를 먼저
살린다 — `agent/lifecycle.py` 「협상은 뒤에서 한다」) 목록은 그 전이 **뒤** 20~120초에
도착하고, 그때 `compose_blocked` 는 안 바뀌므로 리스너가 발화하지 않았다. 잠금이 풀리며
상태 폴링까지 멎어(`wantPoll = _composeBlocked || _modalOpen`) **도착을 관측할 경로가 하나도
없었다.**

- 서버: `connect_status` → `caps_rev`(목록 내용 지문 12자)·`caps_pending`
- 프런트: `_paintCaps` 가 지문 변화를 관측 → `onCapsChange` → 카탈로그 재조회 + 재렌더.
  폴링 조건에 `_capsPollWanted()`(확인 창, 상한 5분) 추가 — 정상 상태 요청은 여전히 0
- 인라인 콜백을 `_refreshModelCatalogSurface` 로 추출 — 두 신호가 같은 절차를 공유

**② 사유 문구의 근거 없는 지시 제거.** 협상이 도는 정상 창(실측 claude 22.7초 · codex
112.3초)에 「최신 실행 파일로 다시 실행해 보세요」라고 말하고 있었다(§16.7 G7-c). 빌드
대조(`runner_build_is_stale`)로 셋을 가르고, 구 빌드가 아닐 때는 「…확인하는 중입니다」.

**③ 계정·런타임 단위 원장.** 신규 `WebAccounts.RunnerCapsBaseline`(JSON, additive).
`_ensure_bridge_heartbeat_schema`(fast path 에서도 불리는 유일한 자리) ALTER —
`BridgeDefaultModel` 이 slow path 전용이라 라이브에서 죽어 있던 선례를 반복하지 않는다.
종전 저장은 `WebOAuthTokens.RunnerCapabilities`(토큰 행)뿐이라 재연결 = 새 행 = NULL 이었다.

**④ 확인-후-표시.** 하트비트 응답 `caps_baseline` → 러너 `verify_runtime_caps`
(`_CAPS_VERIFY_PROMPT`: 「이 중 지금 쓸 수 있는 것 + 빠진 것」) → 통과분만 `verified` 출처로
신고. baseline **그대로**는 화면에 도달하지 않는다(사용자 결정). provenance allowlist 는
러너·서버 양쪽을 함께 넓혔고 구조 테스트가 동일성을 잠근다 — `baseline` 같은 «확인 전»
이름은 넣지 않는다(그것이 `gpt-5.1-codex` 화석과 같은 형태다).

**⑤ 사용일 기준 만료 14일** (사용자 결정) — `last_used_at` 갱신형. 생성일 기준이면 매일
쓰는 런타임도 14일마다 전면 재질의로 떨어져, 안정성을 얻으려고 만든 원장이 주기적으로
불안정을 재생산한다.

### 구현 중 자체 적발 (셋)

- **쓰기 증폭**: `merge_baseline` 이 신고마다 timestamp 를 새로 찍어 내용이 같아도 바이트가
  달라졌고, 그래서 저장 게이트의 「값이 그대로면 쓰지 않는다」가 **항상 거짓**이었다
  (계정당 30초마다 `UPDATE WebAccounts`). 같은 파일 주석이 갖지 못한 성질을 주장하고 있었다.
  → `BASELINE_TOUCH_MIN_SEC`(1시간) throttle. 내용 동일 + 직전 기록이 창 안이면 무접촉.
  실측: throttle=0 이면 30초 뒤 문서 불일치, 3600 이면 일치.
- **baseline 대기 위치**: 신호를 하트비트 **성공 분기**에만 뒀더니 서버에 닿지 못한 사용자가
  상한(≈16초)을 통째로 더 기다렸다 → 분기 체인 **뒤**(성공·실패 무관, baseline 파싱 이후).
- **자기 단정의 거짓 PASS**: 결손 주입에서 폴링 조건 단정이 **정의부**를 보고 통과했다
  (호출을 지웠는데 초록 — §16.7 G14-e 가 검사 자체에 되돌아온 형태). 호출 지점을 보게 재작성.

### 파일

| 파일 | 변경 |
|---|---|
| `shared/bridge_caps.py` | **신규** — 지문·병합·사용일 만료·throttle 순수 정본 |
| `routers/_bootstrap_schema.py` | `RunnerCapsBaseline` fast-path ALTER |
| `oauth_store.py` | `account_caps_baseline` · `merge_account_caps_baseline` |
| `routers/oauth_as.py` | `connect_status` → `caps_rev` · `caps_pending` |
| `routers/ai_tools.py` | 하트비트 원장 병합·`caps_baseline` 전달 · `verified` 허용 |
| `routers/system.py` | 사유 문구 3분기 + `caps_pending` |
| `static/app/connect-modal.js` | `onCapsChange` · `_paintCaps` · 폴링 창 |
| `static/app.js` | `_refreshModelCatalogSurface` 추출 + `onCapsChange` 소비 |
| `agent/caps.py` | `_CAPS_VERIFY_PROMPT` · `verify_runtime_caps` · `baseline_index` |
| `agent/lifecycle.py` | baseline 수신 · 협상 대기 · 출처 로그 분리 |
| `agent/timing.py` | `_CAPS_BASELINE_WAIT_SEC` |

신규 권한 코드 0 · 신규 route path 0 · 파괴적 변경 0. `shared/bridge_tasks.py` 무접촉
(활성 세션 2개가 hot_path 로 선언 중 — §13.2.5-A).

### 검증

신규 25건 + 결손 주입 8종 전건 FAIL 확인(G11-b, 격리 사본). `main` 기준선과 실패 집합 동일.
회귀 2건은 계약을 유지한 채 정합화(인라인 형태 결합 해제 · 하트비트 대역에 신규 책임 반영).


## CHG-20260902T163000-caps-live-sync-confirm2 — 확인 라운드 2회차 조치

정본 판정: `REVIEW.md` → `REV-20260902T163000-…[SELF:confirm-round-2]`.

### 왜 이 항목이 따로 있나

직전 라운드(CONCERN)의 P1 수정을 뮤테이션으로 재확인하려다 **주입 하네스 자체의 결함**을
찾았다 — 러너 실물(`src/bridge_agent.py`)은 루트 `conftest.py` 가 collection 시점에
`agent/` 패키지에서 조립하는 **빌드 생성물**인데, 격리 사본에 그 `conftest.py` 를 넣지
않아 재조립이 없었다. `cp -a` 로 함께 넘어온 **고친 조립본**이 실행되어, `agent/caps.py`
에 무엇을 주입해도 테스트는 원본을 보고 통과했다. 그래서 직전 라운드가 「M-B·M-D KILL」로
기록한 두 건은 **무효**이고, 그 기록을 이 항목이 정정한다.

이 결함의 성질: 실패가 「뮤턴트 생존」이 아니라 **「전건 KILL」로 위장**한다 — 검증했다는
신호를 주면서 아무것도 검증하지 않는다. 하필 그 부류를 잡는 도구에서 났다.

### 무엇을 고쳤나

**하네스** — 사본에 `conftest.py` + 빌드 스크립트를 포함하고, 세션 첫 실행으로 **구문 오류를
주입해 collection 이 실패하는지** 확인한다(주입이 실물에 도달함의 증거). 실패하지 않으면
그 세션의 뮤테이션 결과는 버린다.

**고친 하네스가 즉시 적발한 무단정 3건** (전부 출하 직전 트리에 실재, 러너 스위트 137건
전부 미포착):

| 결손 | 지웠을 때의 실제 결과 |
|---|---|
| `_CAPS_RUNTIME_NAME_RE` (서버 응답 런타임 **이름** 폭) | 서버가 막아 둔 `:` 재해석이 **서버→러너 방향으로** 되열림. 이 키는 `⟦UNTRUSTED-DATA⟧` 봉투 안 프롬프트 문장이자 `_which_ai` 조회 키다 |
| `--refresh-caps` 의 baseline 폐기 **배선** | 「버리고 다시 묻겠다」는 플래그가 직전 목록을 계속 먹임 = 화석에서 영구히 못 벗어남. 기존 테스트는 한 층 아래(`detect_runtimes` 인자)만 봤다 |
| `baseline_ready.set()` | 매 기동 `_CAPS_BASELINE_WAIT_SEC`(16초) 전액 대기 — 이 cycle 이 줄이려던 「체감 대기」의 재생산. 기존 테스트는 `start_heartbeat` 를 **가짜로 대체**해 진짜 코드가 한 번도 안 돌았다 |

**R3 잔여 4건**

- `oauth_store.py` — CAS predicate 를 **컬럼 원문**으로. 정규화 재직렬화를 쓰면 원문이
  갈라진 계정에서 `UPDATE` 가 **영구 0행**이 되고 그 고장이 **조용하다**(하트비트 200 ·
  러너 목록 수신 · 화면 정상, 저장만 멈춤). `_account_caps_baseline_row()` 신설:
  「쓸 필요가 있나」는 정규형, 「누가 먼저 썼나」는 원문.
- `agent/caps.py` — 확인 예산 `left/2` → 절대 상한 `_CAPS_VERIFY_TIMEOUT_SEC = 60.0`.
  240 − 60 = 180초가 열린 질의의 몫이고, 재시도가 겨냥한 **빠른** 실패에서 두 번째 시도가
  성립한다(초판은 남는 120초가 실측 codex 112.3초에 빠듯해 재시도가 사라졌다).
- `agent/caps.py` — 렌더 상한의 부등식을 **실측으로** 못박고(정제 최악치 3,493자 ↔ 상한
  1,600 ↔ 현장 입력 40종 중 31종 유지) 양쪽 끝을 실행으로 잠금. 건너뛴 **사유**도 둘로
  가름(「없습니다」 vs 「너무 길어 담지 못했습니다」 — 자르기 도입 뒤 남는 경우는 목록이
  **있는** 쪽이라 초판 문구가 조사자를 오도했다).
- 문서·주석 — `confirmed_at` 잔재 제거(스키마 주석 · `FUNCTION.md` JSON · 테스트 fixture),
  문구 표 3행을 **코드 verbatim** 으로(초판은 테스트가 **부재를 단정**하는 문장을 명세로
  적어 정면 충돌이었다), 승인 계획 문서엔 **구현 이탈 블록** 명시, `reasons` 주석의 거짓
  기술 정정.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `oauth_store.py` | `_account_caps_baseline_row` 신설 · CAS 를 원문 비교로 |
| `agent/caps.py` | `_CAPS_VERIFY_TIMEOUT_SEC` · 렌더 상한 부등식 · 사유 2분기 · 주석 정정 |
| `routers/_bootstrap_schema.py` | 항목 모양 주석을 실제 키로 |
| `docs/FUNCTION.md` · `docs/TASK*.md` · `docs/REVIEW.md` | 상충 해소 · 귀책 정정 |
| `tests/test_caps_live_sync.py` | 신규 6건(이름 폭 · refresh 배선 · ready 신호 · CAS 원문 4종 · 렌더 예산 · 사유) + AST 단정을 노드 타입으로 |

신규 권한 코드 0 · 신규 route path 0 · 파괴적 변경 0.

### 검증

**신규 57건 통과** · **뮤테이션 21종 KILL / 생존 0**(고친 하네스, 자기검사 통과, 사본 삭제).

⚠ AST 단정 한 건은 초판이 `ast.unparse(...).isidentifier()` 여서 `None`(unparse `"None"`)을
통과시켰다 — **노드 타입**(`ast.Name`)으로 바꿔야 `None`·`[]` 가 함께 걸린다. 「문자열로
뽑아 검사」가 리터럴 앞에서 무력해지는 부류.

### 프로세스 정정

보호 커밋 `ee4abe53` 의 메시지는 스테이징 유실을 **「외부 주체」**의 `git reset --hard` 로
적었다. **틀렸다** — 실제 행위자는 2차 라운드 리뷰 subagent 의 `git stash push -u` 이고,
복원에 쓴 stash 가 바로 그 명령이 만든 것이다(유실과 복원이 같은 원인). `--amend` 금지
(§16.3 Step 3)라 커밋 메시지는 그대로 남으므로 정정은 `REVIEW.md` 가 정본이다. 교훈은
「외부 침입」이 아니라 **read-only 로 부른 리뷰 subagent 가 트리를 변경할 수 있다**.


## CHG-20260902T173000-caps-per-platform-live — 플랫폼마다 실시간 갱신 + codex 라운드 조치

사용자 3차 제보(같은 turn): 「모든 AI 플랫폼의 모델·추론수준을 확인할 때까지 웹에서 갱신이
이루어지지 않는다. 탐색은 백그라운드로 두되 **각 플랫폼이 완수될 때마다** 실시간 갱신되게」.

### 근본 원인

능력 협상은 런타임마다 스레드를 띄우고 **전부 `join` 한 뒤** 결과를 1회 게시했다. 실측
claude 22.7초 · codex 112.3초이므로 그것은 **claude 의 목록이 90초를 기다린다**는 뜻이고,
거기에 하트비트 주기 30초가 더해진다. 사용자에게는 그 합이 「갱신이 안 된다」로 보인다.

### 무엇을 고쳤나

**① 조립을 함수로 분리 — 여러 번 불려도 안전하게.** `detect_runtimes` 의 신고 조립 루프를
`_assemble(present, probed, cached, detail_out)` 로 뺐다. 스레드가 `probed` 에 쓰는 동안
불리므로 **`probed` 를 순회하지 않고** 고정 목록 `present` 를 순회한다(순회 중 삽입은
`RuntimeError` 를 내고 그 예외가 협상 스레드를 죽인다).

**② 플랫폼 단위 중간 신고.** `detect_runtimes(on_settled=…)` → `resolve_caps` 통과 →
`lifecycle._publish_caps`. 최종 게시도 **같은 경로**를 쓴다 — 두 경로를 따로 두면 한쪽만
고쳐지는 날 「부분은 되는데 최종이 안 되는」 상태가 되고 그 차이는 라이브에서만 드러난다.
부분 신고가 안전한 근거: 계정 원장 병합이 합집합 누적이고 같은 프로세스의 `probed` 는
누적되므로 목록은 **자라기만** 한다. 콜백 예외는 삼키고 `caps.partial_report_failed` 로
남긴다(부가 경로가 본 경로를 죽이지 않는다).

**③ 하트비트 즉시 깨우기.** `start_heartbeat(nudge=…)`. 주기만 기다리면 플랫폼이 끝나도
최대 30초를 더 기다린다. **종료 신호도 같은 대기를 깨워야** 한다 — `nudge` 만 기다리면
`try_self_update` 가 `os.execv` 직전에 하트비트를 끊는 경로가 한 주기 밀린다
(`_HEARTBEAT_NUDGE_POLL_SEC = 0.5` 로 두 축을 번갈아 본다).

**④ ⭐ 관측 축 `caps_settling` — ①~③만으로는 두 번째 플랫폼에서 멈춘다.**
`caps_pending`(=「연결됐는데 목록이 비었다」)은 **첫 플랫폼이 도착하면 false** 가 되고,
그러면 프런트 폴링 창이 닫혀 90초 뒤 오는 codex 를 관측할 경로가 다시 하나도 없다 —
제보 ①의 결함이 「첫 플랫폼 이후」로 옮겨 앉을 뿐이다. 서버가 「신고가 방금 바뀌었다」를
**사실로** 낸다(`WebOAuthTokens.CapabilitiesAt` 이 `CAPS_SETTLING_SEC`=150초 안).

- 왜 서버인가: 프런트가 「직전 폴링과 지문이 다르다」로 대신 세우면 **새로 로드한 탭**이
  놓친다(비교할 직전 값이 없고 `caps_pending` 은 이미 false) — 새로고침한 사용자가 제보의
  증상을 그대로 다시 겪는 형태다.
- 왜 별 질의인가: 자연스러운 자리(`shared/bridge_tasks.runner_profile_for_account`)는 지금
  **다른 활성 세션들이 hot_path 로 선언**해 두었다(§13.2.5-A). 같은 파일을 동시에 고치면
  병합이 두 기능 중 하나를 조용히 죽인다 — 이 cycle 이 이미 그 부류를 한 번 검증했다.
- 값의 근거: 연속 신고 사이 실측 최악 간격 ≈90초 < **150** < 전체 질의 예산 240초 →
  간격을 덮으면서 **협상이 끝나면 반드시 닫힌다**(열린 채 남으면 종일 폴링).
- `runner_stale` 게이트를 **이 축에도** 적용한다 — 구 빌드는 신고가 정제에서 전부 떨어지는데
  `CapabilitiesAt` 은 기능·버전 축으로 갱신될 수 있어, 없으면 `caps_pending` 에서 막은
  종일 폴링이 이 축으로 되열린다.

**⑤ `pending` → `watch` 개명.** 그 값이 이제 pending ∪ settling 을 뜻하므로 낡은 이름을
남기지 않는다(이 cycle 이 반복해 고친 부류).

### codex 적대 라운드 조치 (REV-20260902T173000 — 판정 근거는 그쪽)

- **P1-2** `verify_streak` 이 확인 «횟수» 가 아니라 **하트비트 횟수**를 셌다 → 2.5분이면
  원장이 꺼진다(실측 재현). 신고가 닿은 뒤 같은 값의 다음 신고는 **`cache` 로 강등**한다.
- **P1-3** baseline 조회 실패가 `[]` 로 나가 러너가 자기 원장을 지웠다 → 저장층이 `None`
  (모른다)을 돌려주고 응답은 그때 **키를 싣지 않는다**.
- **P1-4** 카탈로그 재조회 실패가 지문을 소비해 영구 정지 → 지문은 **소비처가 성공한 뒤에**
  소비한다(`_refreshModelCatalogSurface` 가 프라미스로 실패를 말한다).
- **P2-5** 협상 중 로드된 탭이 첫 관측을 변화로 세지 않아 빈 목록으로 굳음 → 창이 열려 있으면
  첫 관측도 발화한다(정상 상태의 첫 관측은 여전히 무발화).
- **P2-9** 자기갱신이 진행 중인 협상을 `os.execv` 로 죽임 → `_CAPS_NEGOTIATING` 가드
  (`finally` 로 반드시 내린다 — 새면 그 프로세스가 자기갱신을 영구히 못 한다).

### 변경 파일

| 파일 | 변경 |
|---|---|
| `agent/caps.py` | `_assemble` 분리 · `on_settled` · `log_event` import |
| `agent/lifecycle.py` | `_publish_caps` · `_caps_nudge` · `verified`→`cache` 강등 · `_CAPS_NEGOTIATING` |
| `agent/timing.py` | `_HEARTBEAT_NUDGE_POLL_SEC` |
| `oauth_store.py` | `CAPS_SETTLING_SEC` · `account_caps_settling` · 조회 실패 `None` |
| `routers/oauth_as.py` | `caps_settling` (게이트는 `caps_pending` 과 동일) |
| `routers/ai_tools.py` | 「모른다」면 `caps_baseline` 키 부재 |
| `static/app/connect-modal.js` | `watch` 개명 · 두 축 합 · 지문 지연 소비 · 첫 관측 발화 |
| `static/app.js` | `_refreshModelCatalogSurface` 가 실패를 반환 |
| `tests/test_caps_live_sync.py` | 신규 6건 + 하네스 24검사(⑤~⑨) |
| `tests/test_runtime_model_selector.py` | 함수 경계 결합 해제(`_assemble` 분리로 빨개진 단정) |

신규 권한 코드 0 · 신규 route path 0 · 파괴적 변경 0 · 새 컬럼 0(`CapabilitiesAt` 재사용).

### 검증

컨테이너(py3.11) CI 전 경로 **rc=0 · FAILED 0**. ruff F821 은 **main 기준선과 동일**(1건
`CancelRegistry` — 조립 전 모듈 특성). 뮤테이션 **13종 추가 KILL / 생존 0**
(중간 신고 제거·콜백 예외 전파·nudge 무시·nudge 단독 대기·settling 축 제거·stale 게이트
누락·「모른다」를 참으로 접음·상한 60초·지문 선소비·소비처가 실패를 참으로 보고·강등 제거·
실패에 `[]`·저장층이 실패를 `[]`).

⚠ 이 라운드도 **자기 단정 2건이 항진명제**였다: ① 콜백 실패 단정이 반환 목록만 봤는데
`probed` 쓰기가 콜백보다 앞이라 뮤턴트도 통과했다(→ 구조화 로그 + 스레드 미처리 예외 부재로
전환) ② 프런트 하네스가 리스너를 대역으로 둬 「소비처가 실패를 말하는가」를 검사하지 않았다
(→ `app.js` 함수를 하네스에서 직접 실행). 「방어를 넣었다 ≠ 방어가 성립한다」.
## CHG-20260902T172500-ai-claude-feature-0043-bridge-answer-duration — 답변 완수 시 사라진 총 수행시간 복구

- **날짜**: 2026-09-02
- **REQ**: REQ-20260902-bridge-answer-duration
- **위험도**: Minor (§12.3 — 비파괴 additive 각인 1건. 프런트·CSS 무변경, 마이그레이션 없음)
- **승인**: 사용자 제보 2026-09-02 (「답변을 완수했을 때 총 수행시간이 출력되던 부분이 누락」)

### 배경 — 표시 코드는 살아 있었고, 각인이 끊겼다

프런트는 무손상이었다. `app.js` 의 답변 메타 렌더는 `message.meta.duration_ms > 0` 일 때
수행시간과 구간 분해를 그린다 — 코드도 CSS(`.message-meta-duration`)도 그대로다.

끊긴 것은 **서버가 그 값을 각인하는 배선**이다. 답변 경로가 둘인데 한쪽만 각인했다:
서버 LLM 경로(`agent_core` 의 `mirror_meta`)는 답변마다 굳혔고, 브리지 경로
(`_deliver_web_bridge_answer`)는 그 키를 아예 담지 않았다. feature-0043 이 브리지를 주
경로로 승격한 뒤 답변은 전부 후자로 흘렀고, 표시는 그날부터 사라졌다.

라이브 실측(`agent_runtime.messages`)이 경계를 정확히 짚는다 — `duration_ms` 를 가진 마지막
답변은 **2026-08-26 15:26**(id 2377)이고, 그 이후 브리지 답변 **104건은 예외 없이 없다**.

대기 중 표시는 정상이었다(`startElapsedTimer` 가 경과를 1초 간격으로 그린다). 그래서 사용자가
본 것은 「처리 중엔 시간이 보이고 **답변이 도착하는 순간 그 숫자가 사라지는**」 형태다.

### 변경 내용

| # | 무엇 | 어디 |
|---|---|---|
| ① | 총 수행시간 각인 helper — **end-to-end** 기준(`CreatedAt → SubmittedAt`), 구간은 `ClaimedAt` 으로 가른다 | `ai_tools._bridge_answer_duration_meta` (신규, 순수 함수) |
| ② | 원장 시각 조회 — 계산은 SQL(`TIMESTAMPDIFF`), 실패는 빈 dict (fail-open) | `ai_tools._bridge_task_duration_meta` (신규) |
| ③ | 답변 meta 에 각인 1줄 | `ai_tools._deliver_web_bridge_answer` |

프런트·`_replace_bridge_placeholder`·회수 store 는 **무변경** — placeholder 덮어쓰기가
`meta_json` 전량 교체라 각인이 그대로 실린다.

### 지킨 두 결정

**① 기준은 end-to-end 다.** 「러너가 실행한 시간」(`ClaimedAt` 기준)만 각인하면 대기 구간이
빠져, 대기 중 보였던 경과 타이머보다 **작은 숫자로 줄어든다**. 서버 LLM 경로가 TASK-0289 에서
같은 이유로 `run_start` 기준을 버렸다 — 두 경로의 기준을 맞춘다. 키 이름도 그 경로와 동일하게
뒀다(`total_ms`·`queued_ms`·`inference_ms`) — 프런트 `formatDurationBreakdown` 이 그 세 축만
읽으므로 새 라벨을 만들면 값은 저장되는데 표시가 빈다.

**② 각인 실패가 답변을 잃게 하지 않는다.** 소요 조회를 전달 경로의 주 SELECT 에 얹지 않고
분리했다. `ClaimedAt`/`SubmittedAt` 은 부트스트랩 ALTER 로 추가되는 컬럼이고 그 ALTER 가
실패한 환경이 이미 상정돼 있다(`submit_answer` 의 503 분기) — 한 쿼리로 묶으면 컬럼 부재가
**답변 전달 자체를** 실패시킨다. 결손 주입으로 실증했다(주입 ③ → 전달 실패 로그).

### 검증

- 신규 스위트 `test_bridge_answer_duration.py` **18 passed** — helper 값 계약 + `_deliver_web_bridge_answer` 실구동(가짜 DB) 양쪽.
- **결손 주입 3종 전건 FAIL 확인**: 각인 호출 제거 → 3 FAIL · 총량 기준을 `ClaimedAt` 으로 → 1 FAIL · 소요 조회를 주 SELECT 로 합침 → 4 FAIL(fail-open 파괴 포함).

## CHG-20260902T180500-ai-claude-feature-0043-duration-postdeploy — 수행시간 각인 POST-DEPLOY 실측 + 표시 중복 제거

- **날짜**: 2026-09-02
- **REQ**: REQ-20260902-bridge-answer-duration (후속)
- **위험도**: Minor (§12.3 — 각인 형태 조정 1건. 프런트 무변경)
- **승인**: `deploy_scope: included` (전역, FIRST_REQUEST.md)

### POST-DEPLOY 실측 — 라이브에서 실제로 각인됐다

배포 `ec649a6e`: 전 서비스 SHA 일치 · `no upstreams available` **0건** · surge 0 · healthz 200 ·
대화 스모크 PASS · 서빙 컨테이너에 신규 심볼 5 hits.

정본 증거는 **실 답변 2건**이다(사용자 머신 러너가 제출한 실제 대화 답변):

| 메시지 | 각인 | 원장 시각 대조 |
|---|---|---|
| 2623 (17:51:39) | 140000.0 · `{queued:40000, inference:100000}` | created 17:51:39 → claimed 17:52:19 → submitted 17:53:59 = **140s / 40s** ✓ |
| 2621 (17:50:30) | 36000.0 | created 17:50:30 → submitted 17:51:06 = **36s** ✓ |
| 2619 (배포 전) | **없음** | 경계가 배포 시점과 일치 — 대조군 |

### 라이브가 드러낸 것을 고쳤다

**표시 중복**: 대기가 0 인 답변의 분해는 실행 한 구간뿐이고 그 값이 총량과 같다. 프런트가
분해를 괄호로 덧붙이므로 화면에 `36초 (추론 36초)` 로 같은 숫자가 두 번 나왔다 — 정보가 0인
괄호다. 가를 것이 없으면(대기가 프런트 표시 임계 250ms 미만이거나 없음) `duration_breakdown`
을 **싣지 않는다**. 프런트 무변경으로 `36초` 만 남는다.

서버 임계가 프런트 임계와 갈리면 두 방향으로 조용히 틀린다(서버가 관대하면 그려지지 않는
분해를 각인, 엄하면 그릴 수 있는 구간을 미리 버림). `app.js` 의 숫자를 읽어 대조하는 테스트로
두 값을 묶었다.

**초 해상도가 상한**(관측): `WebAiTasks` 의 세 시각이 `DATETIME`(소수부 없음)이라
`TIMESTAMPDIFF(MICROSECOND, …)` 도 소수부가 0 이다 — 실측값이 전부 1000ms 배수인 이유다.
docstring 에 한계로 명시했다(컬럼을 `DATETIME(3)` 으로 올리는 것은 별건).

### 검증

`test_bridge_answer_duration.py` **22 passed**(기존 18 + 임계 정합·표시 가능 대기·즉시 점유
4건) · 관련 스위트 실패 0. 상세 증거는
`docs/test-runs.d/TASK-20260902T172500-bridge-answer-duration-postdeploy.md`.
