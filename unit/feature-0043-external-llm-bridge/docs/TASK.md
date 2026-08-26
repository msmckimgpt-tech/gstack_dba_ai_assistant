---
doc_type: TASK
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress (라이브 배포 `0b2b4435` 완료 · 실측 PASS · PB-0008 화면 검증만 잔여)
- Owner: AI (계획·구현) / Human (승인)
- Priority: high
- Last Updated: 2026-08-27

## 2. Implementation Plan

### 2.1 Plan

**위험도: Critical** (§12.3 — 라이브 서비스의 답변 생성 경로 전면 정지 + 신규 데이터 경로.
인증·인가 자체는 feature-0041 계약 재사용이나, 사용자 대면 동작이 전면 바뀐다.)

#### 다의어 고지 — "역방향으로 개인 머신 LLM 호출" 이 무엇으로 판정되는가 (§7.1 · §16.7 G1)

> **입력**: 웹 대화창에서 `kingsraid_kr 에서 어제 신규 가입자 수` 전송
> **기대 출력**: (1) 즉시 "내 AI 처리 대기 중" 상태 말풍선, (2) 개인 머신 러너가 집어간 뒤
> 같은 대화창에 답변이 렌더, (3) 그 사이 서버 `llm_usage` 테이블 행 증가 **0건**.
>
> (3)이 이 cycle 의 판정 핵심이다 — 답변이 나왔는데 `llm_usage` 가 늘었다면 서버 계정이 쓰인 것이므로 실패다.

#### 영향받는 파일 · symbol

| 경로 | symbol / 변경 | 비고 |
|---|---|---|
| `shared/llm_gate.py` | **신규** — `server_llm_enabled()` · `assert_server_llm_allowed(caller)` · `SERVER_LLM_BLOCKED_REASON` | fail-closed 단일 정본. **코드 기본값 = 차단**(env `AGENT_SERVER_LLM_ENABLED=1` 로만 해제) — `.env` 미배포/누락 환경에서도 차단이 유효 |
| `unit/feature-0002-agent-core/src/modules/llm.py` | `_get_llm_client()` 선두 게이트 | 모든 chat 클라이언트의 단일 출구. `_openai_chat_completion_with_deadline` 이 내부에서 재호출하므로 한 곳으로 전 경로 커버 |
| `unit/feature-0002-agent-core/src/agent_core.py` | L7378 인근 `OpenAI(...)` 직접 생성부에 게이트 | 두 번째 클라이언트 생성 경로 (chokepoint 우회 차단) |
| `unit/feature-0002-agent-core/src/scripts/kb_embedding_worker.py` | **무변경** | 임베딩 = 로컬 `bge-m3`/ollama. 게이트 비적용 (AC-7) |
| `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml` | 계정 alias 14종 주석처리 + `fallbacks` 블록 주석처리. `titan-embed` 만 활성 유지 | 기존 Bedrock 토글 idiom. 되돌리기 = 주석 해제 |
| `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py` | `WebAiTasks` 에 `Origin` · `ConversationId` · `ClaimedBy` · `ClaimedAt` 멱등 추가 | 기존 `ALGORITHM=INPLACE, LOCK=NONE` idiom + `information_schema` 선조회 + 실패 시 `logging.error` 가시화 |
| `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` | 신규 `list_open_requests` · `claim_request` + `P0_TOOLS` 확장 | 계정 스코프 교차검증 필수. 점유는 SQL `WHERE ClaimedBy IS NULL` 안에서(TOCTOU 금지) |
| `unit/feature-0003-agent-web-ui/src/routers/conversations.py` | `/api/ask` — 게이트 차단 시 `_enqueue_bridge_task()` 로 분기 | 기존 worker/inprocess dispatch 앞단. 그룹·공유 경로 동일 적용 |
| `unit/feature-0003-agent-web-ui/static/*` | 대기 말풍선 · 답변 폴링 · `/ai/connect` 안내 배너 | PB-0008 시각검증 대상(§15.4.1 · `visual_verification_scope: always`) |
| `unit/feature-0043-external-llm-bridge/src/bridge_runner.py` | **신규** — 개인 머신 폴링 러너 | `list→claim→도구→submit` 루프. 서버 코드 아님(클라이언트 배포물). **Python 표준 라이브러리 전용**(`urllib` — `mcp` SDK·`requests` 등 외부 패키지 import 금지). REST `/api/ai/*` 를 직접 호출한다 |
| `docs/SECURITY.md` | 신규 절 — 브리지 위협모델(대기 질문 열람 경계 · 점유 경합 · 미응답 방치) | §18.8 security 렌즈 대상 |
| `docs/ARCHITECTURE.md` · `docs/ROUTEMAP.md` | feature 표 + 라우트 갱신 | **`python3 bin/gen-routemap.py` 재생성 필수** (CI Code-Navigation gate) |
| `docs/STATUS.md` | feature-0043 행 추가 | |

#### 접근 방법

1. **게이트 먼저** — 차단선을 세우기 전에 대체 경로를 열지 않는다. `shared/llm_gate.py` + chokepoint 2곳 +
   회귀 테스트(모든 alias 로 `_get_llm_client()` 가 `None`)까지 한 묶음.
2. **설정 주석은 게이트 다음** — `litellm_config.yaml` 은 "두 번째 자물쇠"다. 설정만 주석하면 호출이
   401/404 로 지저분하게 죽으므로, 게이트가 먼저 정직한 사유를 내도록 한 뒤 주석한다.
3. **스키마 → 도구 → ask 분기 → 프론트** 순. 원장·각인은 기존 0041 계약을 그대로 타고 새로 만들지 않는다.
4. **러너는 마지막** — 서버 계약이 확정된 뒤 클라이언트를 붙인다.
5. **되돌리기 경로 확보** — 게이트 knob 1개 + 주석 해제로 원복. REPORT.md 에 절차 명시.

#### 완료 판정 기준 (항목별 — FUNCTION.md §8 AC 와 1:1)

- **AC-1** 게이트: 활성(기본) 상태에서 `claude-opus-5-chat` · `claude-haiku-4-interactive` · `claude-sonnet-4-chat`
  등 전 alias 로 `_get_llm_client()` 호출 → 전건 `None`. **뮤테이션 역검증**: 게이트를 제거하면 이 테스트가 FAIL 한다.
- **AC-2** 설정: `grep -c 'os.environ/ANTHROPIC_API_KEY' litellm_config.yaml` 의 **비주석 라인** 0건을 단정하는 테스트.
- **AC-3** ask 분기: `/api/ask` 1회 → `WebAiTasks` 1행(`Origin='web'` · `ConversationId` 일치) + `llm_usage` 증가 0.
- **AC-4** 격리: A 질문이 B 토큰 `list_open_requests` 에 부재 + B `claim_request` 403.
- **AC-5** 점유: 동일 `task_id` 2회 claim → 2번째 409, `ClaimedBy` 불변.
- **AC-6** 도달성: PB-0008 실 Windows 브라우저로 웹 질문 → 대기 → 답변 렌더 전 구간 1회 통과
  (`reachability_scope: included` — 컴포넌트 health 로 갈음 금지).
- **AC-7** 임베딩 무회귀: 게이트 활성 상태에서 KB 임베딩 경로 정상(기존 스위트 green).
- **AC-8** 정직한 실패: 차단 호출이 예외를 삼키지 않고 사유를 로그 + 사용자 대면 안내로 낸다.
- **AC-9** 무설치 계약 (사용자 결정 2026-08-26): 개인 머신에 **어떤 패키지도 설치하지 않고** 브리지가 동작한다.
  - 주 경로: `https://<host>/api/ai/mcp` 를 AI 클라이언트에 **URL + 토큰 등록만** — 서버 호스팅이라 클라이언트 설치 0.
  - 보조 경로: `bridge_runner.py` 단일 파일 — **표준 라이브러리만 import** 하는 것을 AST 로 단정하는 테스트
    (`import` 문 전수 검사 → stdlib allowlist 밖 모듈 0건). 주석이 검사를 통과시키지 않도록 문자열이 아닌 AST 로 본다.
  - 신규 도구 2종은 **REST 정본 + MCP 래퍼 양쪽**에 노출 — `curl` 만으로도 전 구간이 가능하다.
- **무회귀**: 0002/0003/0023/0041 전체 스위트 green · `bin/mysql-ddl-lint.sh` PASS ·
  `bin/gen-routemap.py --check` exit 0 · `verify-completion.sh --pre-commit` PASS.

#### 단계 분할 (배포 단위)

- **Step A** 서버 LLM 차단 (게이트 + litellm 주석 + 테스트) — 사용자 요청의 "주석처리" 절반이 여기서 완료
- **Step B** pull 브리지 (스키마 + 도구 2종 + ask 분기 + 프론트)
- **Step C** 폴링 러너 + 연결 안내 문서
- 세 Step 을 한 cycle 로 묶어 출하한다 — Step A 만 배포하면 웹 대화가 답변 없이 죽는 창이 생긴다.

<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-08-26 -->
<!-- 승인 근거: 2026-08-26 대화 — "개인 머신에서 서비스를 작동시키는 환경적인 제한이 최소화되어야
     합니다. 별도의 종속 패키지 설치없이, API를 통한 서비스 제공이 가능한 형태로 진행해주세요."
     → 진행 승인 + 무설치 제약(AC-9) 추가. 그 제약을 계획에 반영한 뒤 착수. -->

## 3. Task Queue

| ID | 내용 | 상태 |
|---|---|---|
| TASK-20260826T135206-ai-claude-feature-0043 | Step A — 서버 LLM fail-closed 게이트 + litellm alias 주석 + 회귀 테스트 | [x] done |
| TASK-20260826T135207-ai-claude-feature-0043 | Step B 백엔드 — WebAiTasks 확장 · 도구 2종 · /api/ask 분기 · 답변 대화 전달 | [x] done |
| TASK-20260826T135208-ai-claude-feature-0043 | Step C — bridge_runner.py(stdlib 전용) + AST 계약 테스트 | [x] done |
| TASK-20260826T135209-ai-claude-feature-0043 | 문서 — SECURITY §49 · ARCHITECTURE · ROUTEMAP 재생성 · STATUS · shared MODIFY · DECISIONS · TEST | [x] done |
| TASK-20260826T135210-ai-claude-feature-0043 | 검증 — 신규 29건 + alias 계약 31건 green · route golden 재생성 · make test 게이트에 0041/0043 편입 | [x] done |
| TASK-20260826T135211-ai-claude-feature-0043 | 프론트 대기/폴링(`bridge_pending` → `_pollBridgeAnswer`) + `GET /api/ai/bridge_status` | [x] done |
| TASK-20260826T151500-ai-claude-feature-0043 | codex 리뷰 P1 5건 · P2 3건 전건 조치 + 배선 회귀 25건 | [x] done |
| TASK-20260827T000500-ai-claude-feature-0043 | codex 2차 리뷰 P1 6건 · P2 3건 조치 + 상태/장애/권한 회귀 17건 | [x] done |
| TASK-20260827T010000-ai-claude-feature-0043 | 배포 스모크 전제를 전환 모드에 맞춤 + 라이브 실측 기록(PR #1352) | [x] done |
| TASK-20260827T030000-ai-claude-feature-0043 | 인증 축을 `mat_` 하나로 통일 — 발견자료·가이드·CLI·런처 전환 + 신규 `matk_` 발급 차단 + 회귀 14건 | [x] done |
| TASK-20260826T151501-ai-claude-feature-0043 | **잔여** — PB-0008 화면 시각검증(브리지 setup 불가·사유 명시) · gateway reconcile(PR #1352 병합 후) | [ ] pending |

## 4. Requested Scope (요청 범위)

사용자가 이 세션에서 실제로 요청한 항목 (§16.7 G1 — 완료 선언 전 항목당 1행 대조).

- [x] `root`·`claude-corp` 계정을 LLM 으로 사용하는 부분을 **모두 주석처리** — 산출물: `shared/llm_gate.py`(코드 기본값=차단) + `litellm_config.yaml` alias 14종·fallbacks 주석. 활성 `ANTHROPIC_API_KEY` 참조 0건
- [ ] 외부 계정(MCP)를 통해서만 서비스를 제공하는 구조를 **main 접근으로 구성** — 산출물: 라이브 `/api/ai/mcp` 에 도구 **12종 노출 실측**(브리지 2종 포함)·REST 라우트 401 도달·프론트 폴링 배포. **PB-0008 화면 시각검증만 미수행**(브리지 setup 불가·사유 명시)
- [ ] 웹 대화 화면 요청이 **역방향으로 각 개인 머신의 LLM 을 호출** — 산출물: pull 브리지 전 구간 배포 + 스키마 5컬럼·복합인덱스 라이브 적용 확인. 위와 같은 잔여(화면 시각검증)
- [x] 개인 머신 **환경 제한 최소화 · 별도 종속 패키지 설치 없이 · API 를 통한 제공** — 산출물: 주 경로 URL+토큰 등록만(어댑터 등록 테스트로 확인), REST `curl` 가능, `bridge_runner.py` stdlib 전용(AST 잠금)
- [x] cycle 종료 후 **바로 배포** — 산출물: `0b2b4435` 라이브 롤아웃 완료(web-a/b·ask/insight-worker·ops-scheduler·ext-tool-mcp 전 서비스 커밋 일치). gateway reconcile 만 스모크 전제 갱신(PR #1352) 후 완결 예정 — 앱 게이트가 정본이라 현재도 계정은 사용되지 않는다(라이브 실측)

## 5. Next Action

병합 → 배포(`deploy_scope: included`) → **POST-DEPLOY PB-0008 실 Windows 브라우저 시각검증**
(대기 말풍선 → 폴링 → 답변 렌더 + `llm_usage` 증가 0 확인) → 도달성 1-probe →
`unit/feature-0003-agent-web-ui/docs/test-runs.d/REV-20260827T000500-bridge-poll-ui.md` verdict 갱신.

### TASK-20260827T090000 — 사용감 패리티 전수 정합

사용자 요구: "기존의 LLM 작동에 관련된 기능들 … 사용감은 동일하게 유지" + "바뀐 부분이 기존 동작 및
경험과 정합하도록 **전수적으로** 상세하게 수정 및 검증".

- [x] 그룹 발신자 귀속 각인 복원 — 기존 경로와 **동일 키**(`sender_username`·`sender_account_id`·`group_chat`)
- [x] 답변 제품 귀속 각인 복원 — `ProductMode` 를 task 에 굳혀 auto/pinned 구분(제품 변경 소급 차단)
- [x] 대화 내역 보존 — 표시 store 에 더해 **회수 store(`core_messages`)** 기록(복제·분기 구멍 제거)
- [x] 첨부 도달 — `AttachmentIds` 적재 + `claim_request` 목록 + `read_task_attachment`(소유·점유·현재권한 3겹)
- [x] 2차 진입점 배선 — 재답변·AI로 고치기가 브리지 인지(거짓 성공 토스트 제거, 폴링 연결)
- [x] 차단 안내 정합 — 관리 콘솔 5곳·그래프 분석·insight 가 "장애"가 아닌 **운영 결정**임을 안내
- [x] 제한 배너 — 차단 중 거짓 경보·영구 고착 차단, 원본 진단 경로는 보존
- [x] 게이트가 깬 기존 스위트 4파일 **이중 계약** 전환(skip 금지) + 게이트 동작 계약 5건 신설
- [x] codex 적대 리뷰(P1 1 · P2 6) 전건 조치 + 회귀 8건
- [ ] 화면 실검증(PB-0008) — win-browser relay 불가로 미수행(사유·해소조건 test-runs.d 기록)

- status: done
- risk: Major (사용자 대면 동작 다수 · 온라인 DDL 3컬럼 · 신규 외부 도구 1)
- scope: 브리지 각인(발신자·제품) · core store · 첨부 도달 · 2차 진입점 배선 · 차단 안내 정합 · 제한 배너
- verify: feature-0043 112 green · 컨테이너 make test 전체 · golden/ROUTEMAP 재생성
