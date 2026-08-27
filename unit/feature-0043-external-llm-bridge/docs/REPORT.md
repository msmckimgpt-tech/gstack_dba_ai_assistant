---
doc_type: REPORT
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. 현재 상태

**배포 완결 `11049643` — 두 자물쇠(앱 게이트 + gateway config) 라이브 반영 · 전 서비스 SHA 일치 · 무중단 blip 0 · 스모크 PASS. PB-0008 화면 시각검증만 미수행(브리지 setup 불가 — 사유 명시).**

서버 보유 계정(`claude-corp`/`root`)으로 나가는 chat 호출은 두 겹(코드 게이트 + 설정 주석)으로
차단됐고, 웹 대화 질문은 `WebAiTasks` 의 대기 작업이 되어 개인 머신 AI 가 MCP/REST 로 가져갈 수 있다.
로컬 임베딩(bge-m3)은 의도적으로 살아 있다.

**2026-08-28 (TASK-20260828T060000)**: 브리지에 **런타임 조작면 3종**(인터럽트 · 맥락 전환 ·
진행 스트리밍)을 붙이고 러너를 병렬화했다. 셋 다 기존 서버 LLM 경로에는 이미 있었고 브리지로
이관되지 않은 축이었다(P0-E 와 같은 "연결이 끊긴" 형태). 답변 **본문** 스트리밍은
의도적으로 하지 않았다 — 이유는 §7.1.

## 2. 산출물

| 층 | 파일 | 요지 |
|---|---|---|
| 게이트 | `shared/llm_gate.py` | fail-closed 단일 정본. 코드 기본값 = 차단 |
| 차단선 ① | `modules/llm._get_llm_client()` | 모든 chat 클라이언트의 단일 출구 |
| 차단선 ② | `agent_core._run_agent_core()` | 직접 `OpenAI(...)` 생성 경로 backstop |
| 차단선 ③ | `litellm_config.yaml` | 계정 alias 14종 + fallbacks 주석. `titan-embed` 만 활성 |
| 스키마 | `_bootstrap_schema.py` | `WebAiTasks` +`Origin`·`ClaimedBy`·`ClaimedAt` (online DDL) |
| 도구 | `ai_tools.py` | `list_open_requests` · `claim_request` + `submit_answer` 대화 전달 |
| 웹 분기 | `conversations.py` | `_enqueue_web_bridge_task()` — `/api/ask` dispatch 앞 |
| 러너 | `bridge_runner.py` | 표준 라이브러리 전용 단일 파일 (무설치) |
| 상태 API | `ai_tools.bridge_status` | 웹 세션 인증 폴링(본문 미포함) |
| 프론트 | `static/app/composer.js` | `bridge_pending` 소비 → SSE 감시(폴링 폴백) → 대화 재로드 |
| MCP 어댑터 | `external_tool_mcp_{http,server}.py` | 두 전송 모두 브리지 도구 노출 |
| **취소 정본** | `shared/bridge_tasks.py` | lease·점유가능 SQL·상태값 + `cancel_bridge_tasks`(미점유 DELETE / 점유 canceled) — **두 라우터가 공유** |
| **취소 배선** | `conversations.{cancel_request,_enqueue_web_bridge_task}` | 중단 버튼 · 재전송 supersede 가 같은 정본을 부른다 |
| **협조적 취소** | `ai_tools.wait_for_request` | 취소에도 즉시 반환 + `canceled_task_ids`. **신규 도구 0** |
| **집행** | `ai_tools.submit_answer` | 취소된 task 는 409(각인·저장 전 판정) |
| **진행 스트리밍** | `ai_tools.bridge_stream` | SSE 55초 상한 + `_counted_stream`(배포 pre-drain 계량) |
| **진행 단계** | `ai_tools._bridge_live_steps` | `tool_call_usage` 를 답변 **전에** 노출 |
| **병렬 러너** | `bridge_agent.py` | 워커 N개(기본 2) + 취소 시 자식 프로세스 kill |
| 테스트 | `tests/` 9파일 | **236건 green** (신규 인터럽트·스트리밍 25건 포함) |

## 3. 검증 (현재까지)

- **feature-0043 스위트 71건 green** — 게이트 기본값·배선(양방향)·정직한 실패·설정 자물쇠·
  러너 stdlib 계약 + codex 리뷰 조치 8건의 배선 단정.
- **alias 계약 31건 green** — 전환 분기 가드 적용 후 `test_llm_edge_free_routing` ·
  `test_meta_llm_edge_free` · `test_conversation_answer_no_edge_alias` 전건 통과.
- **feature-0002 스위트** — 전환 전 baseline 대비 신규 실패 0건. (`test_scratch.py` 6건 +
  `test_attachment_delivery_tool.py` 2건은 **main 에서도 동일하게 실패**하는 환경성 항목으로 확인.)
- **구문·설정** — 편집한 Python 파일 전건 AST 통과 · `composer.js` ESM 구문 통과 · `litellm_config.yaml` YAML 파싱 정상 ·
  활성 `ANTHROPIC_API_KEY` 참조 **0건** · 활성 model_list = `titan-embed` 1건.

## 4. codex 리뷰 조치 (REV-20260826T142000 → REV-20260826T151500)

독립 리뷰가 **P1 5건 · P2 3건**을 적발했고 **전건 수정**했다. 5건 중 4건이 배선 결함이었다 —
로직은 맞는데 호출되지 않거나(어댑터 미등록), 잘못된 순서에 있거나(쿼터 뒤), 결과가 버려졌다(필드 유실).

| # | 무엇이 깨져 있었나 | 조치 |
|---|---|---|
| P1-1 | MCP 어댑터에 신규 도구 미등록 → **무설치 주 경로에서 대기 질문이 보이지 않음** | HTTP·stdio 양쪽 등록 (`_register` 호출까지 테스트로 단정) |
| P1-2 | 브리지 요청이 **LLM 토큰 쿼터**에 막힘 → 쿼터 소진 탈출이 그 쿼터에 막히는 모순 | 게이트를 `if _server_llm_enabled():` 로 조건부화 |
| P1-3 | `bridge_pending` 유실 · INSERT 실패가 HTTP 200 | 필드 전파 + `_http_status: 500` |
| P1-4 | 사용자 질문이 대화에 저장 안 됨 · claim 이 문맥 미전달 | 적재 **전** user 메시지 저장 + 최근 6 turn 각인 전달 |
| P1-5 | 원장 실패 시 `ClaimedBy` 영구 고착 | `_release_claim()` 롤백(`Status='open'` 한정) |
| P2-1~3 | 제출 소유권 미집행 · CREATE TABLE 컬럼 누락 · 폴링 인덱스 부재 | 전건 수정 |

각 수정은 `tests/test_bridge_wiring.py` **25건**이 AST·소스 층에서 잠근다.

### 2차 리뷰 (REV-20260827T000500) — P1 6건 · P2 3건 추가 조치

1차 조치분을 다시 리뷰시키자 **절반만 닫힌 것들**이 드러났다. 가장 무거운 것은 폴링이었다:
`selectConversation()` 은 이미 활성인 대화면 즉시 return 하도록 설계돼 있어(읽음처리만),
**폴링은 성공하고 토스트까지 뜨는데 답변은 화면에 영영 나타나지 않았다.** `loadHistory()` 로 교체.

| # | 발견 | 조치 |
|---|---|---|
| P1-A | 폴링 후 화면 미갱신 (기능 사망) | `loadHistory({preserveScroll:true})` |
| P1-B | `submitted` 확정 후 원장 실패 → 전달 불가·재제출 409 | 전달을 원장보다 **먼저** |
| P1-C | `save_memory_message` 가 실패를 삼키고 0 반환 | 반환값 확인 + `Delivered` 컬럼 + 상태 API 분리 보고 |
| P1-D | claim 이 원장 실패 한 경로에서만 해제 | **lease 30분** (`_CLAIMABLE_SQL` 공유) |
| P1-E | **claim/submit 시점 대화 권한 미재검증** — 퇴출된 계정이 최신 문맥을 읽고 답변을 쓴다 | `_conversation_access_denied()` 양 시점 fail-closed |
| P1-F | 러너가 `conversation_context` 무시 | `_compose_prompt()` |
| P2-A~C | 세션 소유권 · 중복 저장/실패 미감지 · 폴러 4xx | `ClaimedClient` · INSERT→저장 순서 + 취소 · 4xx 즉시 중단 |

codex 의 자기 지적("회귀 테스트가 배선 검사라 상태 전이·장애·권한을 못 본다")을 받아
**상태/장애/권한 축 17건**을 추가했다.

## 5. 잔여

1. **PB-0008 화면 시각검증** — `bin/win-browser.py` 브리지가 이 환경에서 성립하지 않는다
   (`win_host` 를 DNS 주소 `8.8.8.8` 로 오판 · 무권한 relay 도 CDP 도달 실패). 해소는 관리자
   PowerShell `netsh portproxy` 또는 `.wslconfig` mirrored + WSL 재시작이며 이 세션 범위 밖이다.
   **대체 실측**(게이트 차단 · MCP 도구 12종 노출 · 스키마 5컬럼+인덱스 · 라우트 401/405 도달)은
   전건 PASS 이나, 그것은 "부품이 제자리에 있다" 까지이고 **화면이 의도대로 움직이는지는 별개 주장**이다.
   절차·해소조건: `unit/feature-0003-agent-web-ui/docs/test-runs.d/REV-20260827T000500-bridge-poll-ui.md`
2. **`.env` 정리** — 권한 정책상 이 세션에서 읽기·수정 불가. `AGENT_*_MODEL` 계열은 게이트가
   차단선을 쥐고 있어 기능상 무해하나, 위생을 위해 운영자가 직접 주석 처리하는 것이 좋다.

## 6. 되돌리기

두 자물쇠를 모두 풀어야 한다 — 의도된 이중화다.

1. env `AGENT_SERVER_LLM_ENABLED=1`
2. `litellm_config.yaml` 의 `# ` 접두 제거 (alias 14종 + fallbacks)

되돌리면 `_alias_transition` 가드가 자동으로 원래 edge-free 계약 검사로 복귀한다.

## 7. 알려진 한계 (설계상 수용)

- 개인 머신 AI 런타임이 꺼져 있으면 답변이 오지 않는다(feature-0041 ANCHOR §2 Alt-D 가 지적한
  "상시 도달 불가" — 본 설계가 해소한 것은 자격증명 보관 문제뿐이다). UI 는 이를 대기 상태로
  정직하게 표시하며 "곧 온다" 고 가장하지 않는다.
- ~~폴링 주기만큼 지연된다.~~ (2026-08-28 해소) 진행 상황은 SSE(`/api/ai/bridge_stream`)로
  전달되고, 국면 전환·조사 단계가 답변 전에 보인다. 다만 **답변 본문 자체는 여전히 단발**이다
  (아래 참조).
- insight·node_analysis·cluster_label 등 배경 산출물 생성이 멈춘다. 기존 산출물은 보존된다.

### 7.1 답변 토큰 스트리밍을 하지 않은 이유 (2026-08-28 판단)

진행 상황은 흘리지만 **답변 본문은 `submit_answer` 한 번에** 온다. 세 구간 중 병목이
"개인 AI → 서버" 이고, 그 구간은 MCP 도구 호출(요청/응답)이라 증분 전송이 계약에 없다.

증분 제출 도구(`append_answer_chunk`)를 더하는 안을 검토했고 **하지 않기로 했다**:

1. **등록형 클라이언트가 협조할 수 없다.** MCP 클라이언트는 LLM 이 답을 다 쓴 뒤 도구를
   부르므로 현실적 상한이 문단 단위다. 러너에서만 토큰 단위가 되어 **경로별 체감이 갈린다** —
   P0-J 가 명시적으로 금지한 "환경 차이" 다.
2. **인젝션 각인 계약이 전문 단위다.** `classify_injection` → `wrap_external_answer` 는
   완성된 답변에 적용된다. 청크마다 판정하면 문맥이 잘려 판정이 갈리고, 마지막에만 하면
   이미 사용자에게 보여준 뒤라 되돌릴 수 없다(SECURITY §49 경계 재설계 선행).
3. **`_LLMStreamIncomplete` 가 막던 실패 모드가 다시 열린다.** 청크는 왔는데 커밋이 안 오면
   절단된 답변이 완전한 답변으로 보인다.

채택하려면 (1)의 환경 차이를 사용자가 수용한다는 결정이 먼저 필요하다.

### 7.2 점유된 작업의 취소는 협조적이다

미점유 작업은 삭제되지만, 이미 개인 AI 가 가져간 작업은 **그 머신의 프로세스**라 우리에게
kill 권한이 없다. 우리가 하는 것은 세 가지다:

1. `Status='canceled'` 로 표시하고 `wait_for_request` 로 **즉시 통보**한다.
2. 러너(우리 코드)는 그 신호로 자식 프로세스를 죽이고 하차한다.
3. 그 신호를 읽지 않는 등록형 AI 는 `submit_answer` 에서 **409** 를 받는다.

즉 **"취소 즉시 화면은 풀린다, 남의 머신의 계산은 못 멈춘다"** 가 정직한 계약이며, 안내
문구가 그것을 그대로 말한다. 기존 경로의 `preserve_reasoning`(부분 추론 보존)에 대응하는
것은 **없다** — 개인 AI 안의 사고 과정은 관측 불가다. 조사 내역(도구 호출)만 남는다.

## 8. 개선 제안 (§8.1 — 기록만)

- 대기 질문이 일정 시간 미처리되면 사용자에게 알리는 경로(현재는 조용히 대기).
- `claim` 후 미제출 상태로 방치된 작업의 lease 만료·재큐잉.
