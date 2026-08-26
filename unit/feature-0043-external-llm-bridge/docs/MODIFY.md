---
doc_type: MODIFY
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify History

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
