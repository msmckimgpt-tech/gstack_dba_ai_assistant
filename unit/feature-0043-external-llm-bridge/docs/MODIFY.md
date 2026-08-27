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

## CHG-20260828T060000 — 상주 러너 기본화 · 대기 여부 관측 (TASK-20260828T060000)

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
