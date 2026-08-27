---
doc_type: REVIEW
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: append-only
source_of_truth: true
---

# Review

## REV-20260826T142000-ai-claude-feature-0043 [CODEX:staged-diff] — CHANGES-REQUESTED

- **일시**: 2026-08-26
- **범위**: `git diff --cached` 37파일 (Step A·B·C 전체)
- **모델**: gpt-5.6-sol (`codex exec -s read-only`, effort=high)
- **판정**: **CHANGES-REQUESTED — P1 5건 · P2 3건**

### 확인된 것 (통과)

- 게이트 우회 경로 **없음** — chokepoint 2곳 외 직접 chat 클라이언트 생성은 의도적으로 제외한
  임베딩 worker 뿐임을 codex 가 독립 확인.
- `list_open_requests`·`claim_request` 의 `AccountId` 스코프와 `UPDATE ... ClaimedBy IS NULL`
  원자성 자체는 올바름.
- `git diff --cached --check` · MySQL DDL lint 통과.

### P1 (치명 — 출하 전 수정 필수)

| # | 발견 | 왜 치명적인가 |
|---|---|---|
| P1-1 | **HTTP MCP 어댑터에 신규 도구 2종 미등록** (`feature-0041/src/external_tool_mcp_http.py:309`) | REST 라우트만 추가돼 **주 접근 경로 `/api/ai/mcp` 에서 대기 질문을 발견·점유할 수 없다.** 사용자 요구("무설치 = URL+토큰 등록만")의 핵심을 정면으로 깬다 |
| P1-2 | **브리지 분기가 LLM 토큰 쿼터 검사보다 뒤** (`conversations.py:4077` vs `:3514`) | 계정 토큰 한도가 소진되면 **서버 LLM 을 전혀 안 쓰는 브리지 요청도 429** 로 막힌다 — 쿼터 소진을 벗어나려는 전환 목적 자체가 무효화 |
| P1-3 | **dispatch 반환 계약 미충족** (`conversations.py:4434`, `:65`) | `bridge_pending`·`bridge_task_id` 가 최종 JSON 조립에서 **버려지고** `conversation_id` 도 빈 값. 적재 실패 반환에 `_http_status` 가 없어 **DB INSERT 실패가 HTTP 200** 으로 나간다 |
| P1-4 | **사용자 메시지가 대화에 저장되지 않음** (`conversations.py:55`) | 기존 agent 경로가 하던 user 메시지 저장이 누락. 대화 기록에서 질문이 사라지고, `claim_request` 도 현재 질문만 줘 **이전 문맥·첨부·role 을 개인 AI 에 전달하지 않는다** |
| P1-5 | **claim 후 영구 점유** (`ai_tools.py:630`) | 점유를 먼저 커밋하고 원장을 뒤에 기록 → 원장 503 이나 AI 실행 실패 시 `ClaimedBy` 가 영구 유지돼 목록에서 사라진다. lease 만료·release 경로 없음 |

### P2 (권고)

| # | 발견 |
|---|---|
| P2-1 | `submit_answer` UPDATE 가 `ClaimedBy` 미검사 — 같은 계정 다른 세션이 claim 없이 먼저 제출 가능(원자적 claim 이 소유권으로 집행되지 않음) |
| P2-2 | 신규 컬럼 3개를 **별도 ALTER 3회** — 단일 ALTER 로 묶고 신규 설치용 `CREATE TABLE` 에도 컬럼 포함 권장 |
| P2-3 | 폴링 쿼리에 맞는 복합 인덱스 부재 — 현 `(AccountId, CreatedAt)` 는 과거 external/submitted task 까지 훑어 상시 폴링 부하 누적. `(AccountId, Origin, Status, ClaimedBy, CreatedAt)` 계열 필요 |

### 조치

**전건 미수정 상태로 이 cycle 을 마감하지 않는다.** P1 5건은 기능이 실제로 동작하지 않게 만들거나
(P1-1·P1-3·P1-4) 전환 목적을 무효화하며(P1-2) 데이터를 고착시킨다(P1-5).

수정 순서 (의존 고려):
1. P1-2 — 브리지 분기를 쿼터 검사 **앞으로** 이동 (분기 위치 문제라 가장 먼저)
2. P1-3 — 반환 계약 정합 (`bridge_*` 필드 전파 + 적재 실패에 `_http_status: 500`)
3. P1-4 — user 메시지 저장 + `claim_request` 에 대화 문맥 포함
4. P1-1 — HTTP/stdio MCP 어댑터 도구 등록 (주 경로 복구)
5. P1-5 — claim lease(만료 시각) 또는 원장 실패 시 점유 롤백
6. P2 3건

### 메모

codex 는 "신규 pytest 는 실행 환경에 사용 가능한 임시 디렉터리가 없어 시작되지 못했다" 고 보고했다 —
샌드박스 제약이며, 본 세션에서 같은 스위트를 컨테이너 `make test` 로 전건 통과시켰다(`test-runs.d` 참조).

---

## REV-20260826T151500-ai-claude-feature-0043 [CODEX:remediation] — 조치 완료

앞 리뷰(REV-20260826T142000)의 **P1 5건 · P2 3건 전건 수정**. 각 수정은 배선 회귀 테스트로 잠갔다
(`tests/test_bridge_wiring.py` 25건) — 리뷰가 잡은 5건 중 4건이 "로직은 맞는데 호출되지 않거나
잘못된 순서" 였으므로, 헬퍼 correctness 가 아니라 **배선**을 단정하는 층이 필요했다.

| # | 조치 | 잠금 테스트 |
|---|---|---|
| P1-1 | HTTP·stdio MCP 어댑터 양쪽에 `list_open_requests`·`claim_request` 등록. stdio 는 정의만으로 부족해 `_register` 호출까지 단정 | `test_{http,stdio}_mcp_adapter_registers_bridge_tools` · `test_bridge_tools_registered_before_catchall` |
| P1-2 | LLM 토큰 쿼터 게이트를 `if _server_llm_enabled():` 로 조건부화. 브리지는 우리 계정 토큰을 쓰지 않으므로 그 한도의 대상이 아니다. 남용 방어는 `tool_ledger` 상한으로 축이 이동(사라지지 않음) | `test_llm_quota_gate_is_conditional_on_server_llm` |
| P1-3 | 반환에 `conversation_id` 추가 + 최종 JSON 조립에 `bridge_*` 전파 + 적재 실패에 `_http_status: 500` | `test_bridge_enqueue_returns_contract_fields` · `test_bridge_enqueue_failure_carries_http_status` · `test_ask_response_propagates_bridge_flags` |
| P1-4 | 적재 **전에** 사용자 메시지 저장(task 적재가 실패해도 질문은 화면에 남는다) + `claim_request` 가 최근 6 turn 문맥을 각인해 함께 전달(4000자 상한, 절단 시 명시) | `test_bridge_saves_user_message` · `test_claim_request_includes_conversation_context` · `test_conversation_context_is_marked` |
| P1-5 | 원장 실패 시 `_release_claim()` 으로 점유 롤백 — `Status='open'` 인 것만 되돌려 확정 불변 보존 | `test_claim_releases_on_ledger_failure` · `test_release_claim_preserves_submitted_tasks` |
| P2-1 | `submit_answer` UPDATE 에 `AND (Origin <> 'web' OR ClaimedBy = %s)`. 미점유 제출은 409 로 사유 구분 안내 | `test_submit_answer_requires_claim_for_web_tasks` |
| P2-2 | `CREATE TABLE` 에 3컬럼 포함 — 신규 설치는 ALTER 를 아예 돌지 않는다(기존 설치만 1회성 마이그레이션) | `test_create_table_includes_bridge_columns` |
| P2-3 | `IX_WebAiTasks_Bridge (AccountId, Origin, Status, ClaimedBy, CreatedAt)` 을 CREATE TABLE·마이그레이션 양쪽에 추가(online DDL) | `test_bridge_polling_index_exists` · `test_bridge_ddl_is_online` |

### 함께 완료한 것 (리뷰 밖)

- **프론트 대기/폴링** — `payload.bridge_pending` 소비 → `_pollBridgeAnswer()`(5초 주기, 30분 상한).
  답변 도착 시 `selectConversation()` 으로 대화 재로드. 사용자가 다른 대화로 옮기면 조용히 중단.
  일시 네트워크 오류로 폴링이 죽지 않는다(다음 tick 재시도).
- **`GET /api/ai/bridge_status`** 신설 — **웹 세션 인증**(외부 토큰 도달 불가) + 계정 스코프,
  답변 **본문 미포함**(각인 블록이 두 경로로 새지 않게).

### 남은 것

- PB-0008 실 Windows 브라우저 시각검증 (웹 자산을 이번에 수정했으므로 필수)
- 도달성 1-probe (`reachability_scope: included`)

---

## REV-20260827T000500-ai-claude-feature-0043 [CODEX:remediation-2] — 2차 조치 완료

1차 조치분을 다시 리뷰시킨 결과 **P1 6건 · P2 3건**이 더 나왔다. 판정은 정확했다 — 특히 첫 번째는
**기능 자체가 죽는 결함**이었고, 1차 조치가 "닫혔다" 고 본 것 중 일부는 절반만 닫혀 있었다.

codex 의 자기 지적을 인용하면: *"핵심 회귀 테스트가 대부분 AST/문자열 배선 검사라 상태 전이·
장애·권한 결함을 검출하지 못한다."* 이번 조치는 그 축을 겨냥한 테스트 17건을 함께 넣었다.

### P1

| # | 발견 | 왜 치명적인가 | 조치 |
|---|---|---|---|
| A | **폴링 성공 후 화면이 갱신되지 않음** — `selectConversation()` 은 이미 활성인 대화면 즉시 return(읽음처리만) | 폴링은 성공하고 토스트까지 뜨는데 **답변은 영영 안 보인다**. 브리지의 사용자 대면 결과가 통째로 사라진다 | `loadHistory({preserveScroll:true})` 로 교체 — 필요한 것은 대화 *전환*이 아니라 현재 대화 *재조회* |
| B | `submitted` 와 대화 전달이 분리 — 원장 실패 시 확정됐는데 화면엔 없고 재제출은 409 | 복구 경로가 없는 상태가 굳는다 | 전달을 **원장보다 먼저** 수행. 원장 장애가 사용자 대면 결과를 훼손하지 않는다 |
| C | `save_memory_message` 가 쓰기 실패를 삼키고 `0` 반환 — 호출부가 미확인 | 저장 실패에도 `delivered=true` 보고 | 반환값 확인 + `Delivered` 컬럼 기록 + 상태 API 가 `answered`/`delivered` 분리 보고 |
| D | claim 이 원장 실패 **한 경로**에서만 해제 — 러너 종료·타임아웃·빈 답변은 점유 유지 | 질문이 목록에서 영구 소실 | **lease 30분** 도입. `list_open_requests`·`claim_request` 가 같은 술어(`_CLAIMABLE_SQL`) 공유 |
| E | **공유 대화 권한이 claim/submit 시점에 재검증되지 않음** | 질문 후 그룹에서 퇴출된 계정이 최신 문맥을 읽고 그 대화에 답변을 쓴다 | `_conversation_access_denied()` 로 양 시점 재검증(fail-closed). 거부 시 점유 해제 |
| F | 러너가 `conversation_context` 를 무시하고 `question` 만 전달 | P1-4 가 API 까지만 연결되고 러너에서 끊김 | `_compose_prompt()` 로 문맥+질문 조립 |

### P2

| # | 발견 | 조치 |
|---|---|---|
| A | 같은 계정의 **다른 세션**이 claim 없이 제출 가능 | `ClaimedClient` 컬럼 + submit 조건에 세션 비교(기존 행은 NULL 허용) |
| B | user 메시지·task INSERT 별도 커밋 — 재시도 시 중복 / 저장 실패 미감지 | 순서를 **INSERT → 저장** 으로 뒤집고, 저장 실패 시 `_delete_bridge_task()` 로 적재 취소(미점유 open 만) |
| C | 폴러가 401/403/404 도 30분 재시도 | 4xx 즉시 중단 |

### 검증

- feature-0043 스위트 **71건 green** (게이트 24 · 러너 5 · 배선 25 · **상태/장애/권한 17**)
- 편집 Python 4파일 AST + `composer.js` ESM 구문 통과

---

## REV-20260827T013000-ai-claude-feature-0043 [SKIPPED:codex-quota-exhausted] — 스모크 문구 slice

- **범위**: `bin/smoke-conversation.sh` PASS 문구 모드 분리 + 문서(test-runs·REPORT·TASK·wiki)
- **판정**: 패널 미수행 — **사유를 정직하게 기록한다**

### 왜 미수행인가

이 cycle 의 앞선 두 slice 는 codex 패널을 각각 돌렸고(REV-20260826T142000 ·
REV-20260827T000500), 그 결과 P1 11건·P2 6건을 잡아 전건 조치했다. 3차 리뷰를 시도했으나
**codex 사용량 한도 소진**으로 실행되지 않았다:

```
ERROR: You've hit your usage limit. … try again at 1:21 AM.
```

### 무엇으로 갈음했나

- 변경 범위가 **로그 문구 1개 + 문서**다. 런타임 동작·계약·경계를 바꾸지 않는다.
- 그 문구 변경은 **라이브에서 직접 실행해 확인**했다:
  `PASS — 서버 계정 LLM 차단 확인(전환 모드). 대화 답변은 사용자 개인 AI 가 생성한다.`
- `bash -n` 구문 검사 통과.

### 남는 위험 (정직 표기)

문구 분기(`grep -q 'SMOKE_OK gate:'`)가 향후 스모크 출력 포맷 변경에 취약하다 —
`SMOKE_OK gate:` 접두를 바꾸면 조용히 옛 문구로 되돌아간다. 회귀 테스트로 잠그지 않았다
(스모크는 컨테이너 실행이 필요해 단위 스위트에 넣기 어렵다).

---

## REV-20260827T030000-ai-claude-feature-0043 [SKIPPED:codex-quota-exhausted] — 인증 축 통일 slice

- **범위**: 발견 자료·사용자 가이드·발급 CLI·런처의 토큰 축을 `mat_` 로 통일, 신규 `matk_` 발급 차단
- **판정**: 패널 미수행 — codex 사용량 한도가 아직 회복되지 않았다(REV-20260827T013000 과 동일 사유)

### 무엇으로 갈음했나

- **회귀 테스트 14건 신설**(`test_token_axis_unified.py`)이 이 slice 의 주장을 코드로 고정한다:
  발급 축(`new_secret("mat_")`) · 안내면(힌트·self-serve·MCP·`/api/ask` 비생성 명시) ·
  차단 게이트(`ALLOW_DEPRECATED_MATK`·`exit 3`·`--revoke` 통과) · **축 분리 불변식**
  (도구 표면이 `WebApiTokens` 를 참조하지 않는다).
- 테스트를 쓰는 과정에서 **자기 판정의 결함 2건**을 발견해 고쳤다 — 폐기 맥락 판정 창이 좁아
  한국어 서술어 위치(언급 뒤)를 놓쳤고, `how_to_obtain` 과 `deprecated_scheme` 을 구분하지 않아
  "폐기 설명에서의 언급" 까지 위반으로 잡았다. 검사 대상을 좁히는 대신 **창을 넓히고 구간을
  분리**했다(설명은 남아야 한다 — 사라지면 옛 토큰 보유자가 이유를 알 수 없다).
- `bash -n` 구문 검사 + 발급 차단 실행 확인(exit 3, `--revoke` 통과).

### 남는 위험 (정직 표기)

- 안내면 검사는 **문자열 기준**이다. 문구를 크게 바꾸면 테스트가 먼저 깨져 재작성을 강제하지만,
  의미는 유지한 채 표현만 바꾸는 경우에도 깨진다(false alarm 가능).
- 기존 `matk_` 토큰의 **런타임 동작은 이 slice 에서 바꾸지 않았다**. `/api/ask` 를 그 토큰으로
  부르면 브리지 대기 안내가 온다 — 게이트가 이미 그렇게 동작하지만, 그 경로를 겨냥한
  통합 테스트는 없다.

## REV-20260827T090000-ai-root-feature-0043 [CODEX:staged-diff] — CHANGES-REQUESTED → 조치 완료

`git diff --cached` 전량 적대 리뷰. **P1 1건 + P2 6건** 지적, 전부 실재로 확인하고 조치했다.

### [P1] insight 게이트가 heartbeat 와 비-LLM 방어까지 함께 껐다

cycle 진입부 early-return 이 `finally` **앞**이라 `insight_worker_last_cycle_at` 이 갱신되지
않았다 → 180초 뒤 healthcheck exit 1 → **차단 모드에서 컨테이너 상시 unhealthy**. LLM 무관
정비(role backfill · enum self-heal · datasource health · auth cooldown prune)도 함께 정지.

낭비를 줄이려던 최적화가 그 경로에 얹혀 있던 방어를 껐다. **cycle 전체 게이트를 철회**하고
순수 LLM 작업(`node_analysis.process_pending`)만 좁게 막았다. 남은 낭비는 작다 — 스캔 안의 LLM
호출은 `_get_llm_client()` 에서 즉시 None 을 받고 되돌아온다(로그는 caller 별 60초 throttle).

### [P2] 6건

| 지적 | 조치 |
|---|---|
| 첨부 읽기가 `ClaimedBy` 만 검사(client·lease·상태 누락) | `submit_answer` 와 **동일 경계**로 통일 |
| 원장 상한 우회(사후 record 만) | 읽기 **전** `check_limits()` — 첨부 본문이 가장 큰 payload |
| provenance ContextVar 미복원 | 플래그·사유·계정 3종 set/reset **역순** 복원 |
| 대화 재진입 시 폴링 미복구 | sessionStorage registry + `resumeBridgePolling` 배선 + 중복 폴링 가드 |
| 관제 화면이 마스킹된 `ok` 를 읽음 | `_read_llm_provider_status_admin()` seam 분리(원본 + 차단 표기) |
| (호출부 3곳 배선은 정상 확인) | — |

### 이 리뷰에서 얻은 것

**같은 실수를 두 번 했다**: "차단 중이니 하지 말자" 는 판단(insight skip · provider 마스킹)을
**대화 UI 기준으로 세우고 전역에 적용**했다. 교정은 둘 다 **소비자별 seam 분리**였다 —
대화 UI 는 마스킹, 관제는 원본; cycle 은 유지, LLM 작업만 차단.

codex 의 마지막 지적도 그대로 받는다: *"현재 테스트는 배선 문자열과 조기 반환만 확인해 위
실패 상태를 잡지 못한다."* 조치와 함께 회귀 8건을 더했으나 이들 역시 소스 층이다. **런타임
경계(만료 lease 로 첨부 읽기 → 409 등)는 배포 후 e2e 에서 실측한다** — 미검증을 검증으로
적지 않는다.

## REV-20260827T120000-ai-root-feature-0043 [SKIPPED:live-report-hotfix] — 라이브 제보 직접 수정

외부 적대 리뷰를 돌리지 않았다. 이 변경은 **라이브 사용자 제보로 결함이 이미 확정된** 수정이고,
원인·수정 범위가 좁다(말풍선 1개를 저장하고 갱신). 리뷰가 찾아줄 것을 이미 실측으로 알고 있다.

대신 확인한 것:
- 원인을 **DB 실측**으로 확정(추정 아님) — task/질문/각인은 정상, 안내만 부재
- 덮어쓰기 범위를 3겹으로 좁힘(대화 · role='assistant' · 이 task 의 placeholder). 범위가 넓으면
  남의 말풍선을 덮는다
- placeholder 각인을 답변에서 **지운다** — 안 지우면 이 답변이 다음 전달의 덮어쓰기 대상이 된다
- append 폴백 유지 — 이 기능 이전에 적재된 task 도 답변을 받아야 한다

**미검증**: 라이브 화면 재현. 배포 후 사용자가 웹에서 전송해 확인해야 완결된다 — 그 전까지
"고쳤다" 가 아니라 "고쳤다고 믿는다" 이다.

## REV-20260827T140000-ai-root-feature-0043 [SKIPPED:copy-only-change] — 문구 변경

외부 적대 리뷰를 돌리지 않았다. 이 변경은 **사용자 대면 문구**가 본체이고, 결함은 이미 사용자가
직접 지목했다(용어를 못 알아듣는다). 리뷰어가 판정할 수 있는 것이 아니라 **사용자가 판정할 것**이다.

대신 코드 쪽 위험만 좁혀 확인했다:
- 연결 여부 조회를 **요청당 1회**로 묶었다 — 두 번 조회하면 그 사이 상태가 바뀌어 화면과 토스트가
  다른 말을 할 수 있다.
- 조회 실패를 **fail-open('연결됨')** 으로 뒀다 — 반대로 두면 DB 가 흔들릴 때마다 이미 연결한
  사용자에게 설정하라고 떠든다.
- `/ai/connect` 는 문구만 바꾸고 **DOM id 13개를 보존**했다. JS 가 잡는 id 가 하나라도 빠지면 버튼이
  조용히 죽는다 — 그래서 id 계약을 테스트로 고정했다(다음 문구 수정도 이 그물을 지난다).

**미검증**: 실제 사용자가 이 문구로 연결에 성공하는가. 그것이 이 변경의 유일한 성공 기준이고,
배포 후 확인해야 한다.

## REV-20260827T160000-ai-root-feature-0043 [SKIPPED:ui-copy-change] — 연결 화면 단일 흐름

외부 적대 리뷰 미실행. 변경 본체가 **화면 구성·지시문 문구**이고, 성공 판정은 "실제 AI 가 이
지시문으로 연결에 성공하는가" 라 리뷰어가 아니라 실사용이 답한다.

코드 쪽에서 좁혀 확인한 것:
- **DOM id 계약**을 새 이름으로 갱신하고 테스트로 고정 — JS 가 잡는 id 가 하나라도 빠지면
  버튼이 조용히 죽는다(화면은 멀쩡하고 클릭만 무반응).
- 토큰 발급 API(`/api/ai/connect/token`) **계약은 건드리지 않았다** — 화면만 바뀌었다.
- 지시문에 토큰이 들어가므로 1회 노출·세션 결합 경고를 그대로 유지했고, 그 3요소를 검사하는
  기존 테스트도 살아 있다.
- feature-0041 의 '무설정 경로 우선' 계약은 **폐기가 아니라 갱신**이다 — 구 계약 문구를 주석에
  남겨 왜 바뀌었는지 추적 가능하게 했다(그냥 지우면 다음 사람이 순서를 되돌린다).

**미검증**: 실제 AI 가 A·B·C 중 무엇을 골라 연결하는가. 배포 후 실사용으로 확인한다.

## REV-20260827T180000-ai-root-feature-0043 [SKIPPED:live-report-hotfix] — 실 연결 제보 조치

외부 적대 리뷰 미실행. **라이브 실 연결 테스트가 리뷰보다 강한 증거**를 이미 냈다 — 세 이슈 모두
재현 경로와 함께 제보됐고, ①은 스택트레이스까지 있었다.

이번에 확인된 검증 구멍이 핵심이다:

> 도구가 **등록됐는가** 는 봤지만, 그 핸들러가 **끝까지 도는가** 는 보지 않았다.

`list_open_requests` 는 등록·SQL·권한·어댑터 배선까지 전부 테스트가 있었고 전건 green 이었다.
그런데 마지막 줄(원장 기록)의 인자명 하나가 틀려 **100% 500** 이었다. 소스 층 테스트는 원리적으로
이걸 못 본다 — 실행하지 않기 때문이다.

메운 방식: 문자열 검사가 아니라 **`inspect.signature` × AST 호출부 전수 대조**. 오타든 이름
변경이든, 호출부든 시그니처든 어느 쪽이 바뀌어도 잡힌다. 같은 형태의 결함이 다른 7개 호출부에
없다는 것도 이 검사로 확인했다.

남은 한계: 이 방법도 **실행 검증이 아니다.** 핸들러 전체를 도는 통합 테스트(원장 스텁 + 실 호출)가
있어야 완전하고, 그건 다음 cycle 과제다.
