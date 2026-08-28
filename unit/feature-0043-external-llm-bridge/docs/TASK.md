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
| TASK-20260828T070000-ai-claude-feature-0043 | 진행 스트리밍(SSE 55초) · 인터럽트 · 맥락 전환 supersede · 병렬 러너 | [ ] in-progress |

| TASK-20260828T093000-ai-claude-feature-0043 | **라이브 실측 P1~P3 4건 수정** — 취소 무한 재통보 tight loop(답변 유실) · stall 오집계 · `_http:0` 연결실패 오판 · 답변 후 버튼 박제 | [x] done |

| TASK-20260828T140000-ai-claude-feature-0043 | **codex 적대 리뷰 P1 4건·P2 4건 전건 조치** — 취소 미확인 보고·워커 포화 시 취소 정지·SSE 이벤트루프 블로킹/무상한·점유실패로 러너 종료 외 | [x] done |

| TASK-20260828T150000-ai-claude-feature-0043 | **실제 LLM 라이브 검증** — 8축 전부 PASS · 사전 분석 3건 오판 기록 · 잔여 괴리 1건(모델 조작면 설명 부재) | [x] done |

## 4. Requested Scope (요청 범위)

사용자가 이 세션에서 실제로 요청한 항목 (§16.7 G1 — 완료 선언 전 항목당 1행 대조).

- [x] `root`·`claude-corp` 계정을 LLM 으로 사용하는 부분을 **모두 주석처리** — 산출물: `shared/llm_gate.py`(코드 기본값=차단) + `litellm_config.yaml` alias 14종·fallbacks 주석. 활성 `ANTHROPIC_API_KEY` 참조 0건
- [ ] 외부 계정(MCP)를 통해서만 서비스를 제공하는 구조를 **main 접근으로 구성** — 산출물: 라이브 `/api/ai/mcp` 에 도구 **12종 노출 실측**(브리지 2종 포함)·REST 라우트 401 도달·프론트 폴링 배포. **PB-0008 화면 시각검증만 미수행**(브리지 setup 불가·사유 명시)
- [ ] 웹 대화 화면 요청이 **역방향으로 각 개인 머신의 LLM 을 호출** — 산출물: pull 브리지 전 구간 배포 + 스키마 5컬럼·복합인덱스 라이브 적용 확인. 위와 같은 잔여(화면 시각검증)
- [x] 개인 머신 **환경 제한 최소화 · 별도 종속 패키지 설치 없이 · API 를 통한 제공** — 산출물: 주 경로 URL+토큰 등록만(어댑터 등록 테스트로 확인), REST `curl` 가능, `bridge_runner.py` stdlib 전용(AST 잠금)
- [x] cycle 종료 후 **바로 배포** — 산출물: `0b2b4435` 라이브 롤아웃 완료(web-a/b·ask/insight-worker·ops-scheduler·ext-tool-mcp 전 서비스 커밋 일치). gateway reconcile 만 스모크 전제 갱신(PR #1352) 후 완결 예정 — 앱 게이트가 정본이라 현재도 계정은 사용되지 않는다(라이브 실측)

### 2026-08-28 세션 요청 (P0-T)

- [x] **모델과 추론수준이 정합하지 않는 이슈 수정** — 산출물: 원인 확정(화면 값이 서비스 내부 alias 라 어떤 CLI 도 모름 · 기본값 haiku 이므로 사실상 전량 폴백) + 전달·적재·러너 경로 제거. 회귀 잠금 `test_ux_parity.py` 4건
- [x] **연결된 AI 에 따른 능동적 재구성** — 판정: 서버가 런타임 종류를 알 수 없어(MCP 어댑터 별도 컨테이너·`clientInfo` 부재) 재구성 불가. 사용자 결정으로 **재구성 대신 제거**. 산출물: `model_selector: "hidden"` 계약 + 컴포저 숨김 + 메뉴 가드
- [x] **제어 제한되면 브라우저에서 제거(숨김)** — 산출물: 카탈로그·화면·전송·적재 4지점 동시 차단. 게이트 해제 시 복원(이중 계약 테스트 `test_model_catalog_bridge_mode.py` 3건 · 조건 반전 뮤테이션 KILL)
- [ ] **화면 확인** — 사용자 결정(2026-08-28)으로 배포 후 **사용자 육안확인**에 위임. AI 는 PB-0008 브리지 복구 + 라이브 도달(status 200)까지 실측

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

### TASK-20260827T120000 — 대기 안내 미저장 결함 (라이브 제보)
- status: done
- risk: Major (사용자 대면 — 전송이 무반응으로 보임)
- [x] 대기 안내를 assistant 말풍선으로 저장(placeholder 각인)
- [x] 답변 도착 시 그 자리에 덮어쓰기 + append 폴백
- [x] 회수 store 오염 방지(안내 제외)
- [x] 회귀 5건
- [ ] **라이브 재현 확인** — 배포 후 웹에서 전송해 안내 말풍선이 보이는지(사용자 확인 필요)

### TASK-20260827T140000 — 안내를 사용자의 언어로 (사용자 제보)
- status: done
- risk: Minor (문구·안내 — 동작 계약 불변, DOM id 테스트로 고정)
- [x] 대기 안내 상태별 2종 + 누를 수 있는 링크
- [x] 토스트도 상태별(서버가 문구 지정)
- [x] `/ai/connect` 화면 재작성(실제 도구 이름·붙여넣을 위치·토큰 설명)
- [x] 회귀 11건
- [ ] **라이브 확인** — 연결 없는 상태의 안내와 `/ai/connect` 화면(사용자 확인 필요)

### TASK-20260827T160000 — 연결 화면 단일 흐름 (사용자 결정)
- status: done
- risk: Minor (연결 화면 UI·문구 — 토큰 발급 API 계약 불변)
- [x] 방법 ①/② 통합 → 단일 흐름
- [x] AI 용 지시문 생성(A/B/C 시도 순서 + 연결 직후 할 일)
- [x] 사람 재호출 없는 경로 우선(OAuth 는 C)
- [x] 계약 테스트 재작성 + DOM id 갱신
- [ ] **라이브 확인** — 실제 AI 가 이 지시문으로 연결에 성공하는가(사용자 확인 필요)

### TASK-20260827T180000 — 라이브 e2e 제보 3건 + 문구 정리
- status: done
- risk: Major (① 은 브리지 축 전체 장애)
- [x] ① `rows` → `rows_returned` + AST 전수 대조(8곳 중 1건) + 시그니처 회귀 테스트
- [x] ② `/api/ai/capabilities` 가 `mat_` 수용(같은 해석기 재사용)
- [x] ③ 가이드 13종 + 브리지 사용 순서 + 도구 수 대조 테스트
- [x] 안내 문구 슬롭 제거(대화창 4문단→2문장, 연결 화면·지시문·가이드)
- [ ] **라이브 재확인** — `list_open_requests` 200 및 claim→submit 완주(다른 세션 진행)

### TASK-20260827T200000 — 즉시 인지 · 상주 러너 · 인증 모달
- status: done
- risk: Major (신규 블로킹 엔드포인트 · 신규 배포 자산 · 대화 화면 상호작용 변경)
- [x] `wait_for_request` — 폴링 없이 즉시 인지, 간격 knob 없음
- [x] 상주 러너(런타임 무관·stdlib 전용) + 서버 배포 + 해시 일치 강제
- [x] 지시문에 설치 절차·CA·mcp add 포함(AI 가 스스로 실행)
- [x] 인증창 모달화(새 탭 의도 존중·단독 페이지 유지)
- [ ] **라이브 확인** — 대기→즉시 반환, 러너 상주, 모달 동작(사용자 테스트)

### TASK-20260827T220000 — 모델·추론 정합 + 실행 단계 복원 (사용자 제보)
- status: done
- risk: Major (요청 품질 계약 · 신규 steps 기록 경로)
- [x] 모델·추론 강도를 task 에 굳히고 claim 으로 전달
- [x] 러너가 실제 CLI 인자로 적용 + 폴백 시 사실 고지
- [x] 원장 → 실행 단계 복원 + run_id 각인
- [x] 사고 과정은 비워 둠(지어내지 않음) · 진행 도구 필터
- [ ] **라이브 확인** — 모델 선택 반영, 'AI 추론' 탭 표시(사용자 테스트)

### TASK-20260828T000000 — 진행 가시성 · 5단계 프롬프트 · 제품 인지
- status: done
- risk: Major (프롬프트 계약 · 말풍선 변조 경로 · 신규 컬럼)
- [x] ① 점유 시 말풍선 '처리 중' + phase 4종 + 연결 없음 고지
- [x] ② RoleId 적재 · 서버 조립(동일 함수) · 러너 맨 앞 배치
- [x] ③ 첨부 end-to-end 배선 고정
- [x] ④ 제품·데이터소스 인지 전달
- [ ] **라이브 확인** — 처리 중 표시, 운영자 지침 반영, 대상 제품 명시(사용자 테스트)

### TASK-20260828T050000 — 대화 제목 · 실행 단계 사유 (사용자 제보)
- status: done
- risk: Minor (비파괴 추가 — 신규 컬럼·마이그레이션 없음. 기존 steps/topic 저장 경로 재사용)
- 결정(사용자, AskUserQuestion 2026-08-27): 제목 = **하이브리드**(서버 즉시 + AI 제안) ·
  단계 사유 = **AI 제공 + 서버 보완**
- [x] 제목 ①: 적재 시점에 질문 앞머리로 즉시 설정(연결·미연결 두 분기 모두)
- [x] 제목 ②: `submit_answer` 의 `title` 수용 → 맥락 제목으로 승급(사용자 rename 은 보존)
- [x] 단계: 도구 호출 **그 시점에** 기록(인자·사유 동시 보유) — `_mirror_step` 재사용
- [x] 사유: MCP 어댑터 2종 × 조사 도구 9종에 `reason` + 도구 설명으로 요구, 러너 프롬프트 규약
- [x] 출처 각인 `external-ai` / `derived` — 파생 문구를 AI 사고로 위장하지 않음
- [x] 원장 이관을 중복 방지 fallback 으로 강등(구 task 전용)
- [x] `make test` 전량 green · 신규 테스트 38건 · 기존 계약 2건 갱신
- [ ] **라이브 확인** — 제목 즉시 변경 / 답변 후 맥락 제목 / 단계에 사유 표시(사용자 테스트)

### TASK-20260828T020000 — 로그아웃 연결 폐기 · 미연결 시 미적재
- status: done
- risk: Major (인증 상태 표시 · 적재 정책 변경)
- [x] 로그아웃 → 파생 토큰 revoke 전파(호출 배선)
- [x] 연결 판정을 인증 판정과 단일화
- [x] 연결 없으면 미적재(대화 기록·문맥은 유지, 폴링 없음)
- [x] 오탐 낸 순서 계약 4건을 범위 축소·AST 로 교체
- [ ] **라이브 확인** — 로그아웃 후 '연결 안 됨' 표시, 재요청 시 이전 문맥 동반(사용자 테스트)

### TASK-20260828T040000 — 연결 상태 상시 표시
- status: done
- risk: Minor (표시 전용 · 판정은 기존 함수 재사용)
- [x] `connect/status` 에 connected(인증과 동일 판정)
- [x] 컴포저 상시 표시 + 클릭 시 모달
- [x] 갱신 3시점(로드·발급 직후·탭 복귀), 폴링 없음
- [x] 실패 시 침묵(틀린 상태 미표시)
- [ ] **라이브 확인** — 표시가 실제 연결 상태를 따라가는가(사용자 테스트)

### TASK-20260828T060000-bridge-model-selector — 모델·추론 조작면 제거 (P0-M supersede)
- status: done
- risk: Major (사용자 대면 조작면 제거 · 카탈로그 응답 계약 변경)
- [x] 카탈로그가 차단 상태에서 `model_selector: "hidden"` + 빈 목록 반환(미인증 응답은 불변)
- [x] 컴포저 모델·추론 항목 숨김 + 메뉴 열기 가드(키보드·직접 호출 우회 차단)
- [x] 전송(`sendPrompt`)·재답변(`_submitMessageEdit`) 에서 model·reasoning_level 제외
- [x] 브리지 적재·`claim_request`·러너에서 모델/추론 경로 제거(컬럼은 이력으로 보존)
- [x] 이중 계약 테스트 — 차단 시 숨김 · 해제 시 복원(반환값 + 배선 양쪽), 조건 반전 뮤테이션 KILL
- [ ] **라이브 확인** — 화면에서 두 항목이 사라지고 전송이 정상인가(PB-0008)

### TASK-20260828T060000 — 상주 러너 기본화 · 대기 여부 관측
- status: done
- risk: Major (권장 경로 변경 · 신규 관측 축)
- [x] 지시문에서 러너를 필수 1단계로(이유·재시작 복귀 포함)
- [x] 원장으로 대기 여부 관측 + 3상태 표시
- [x] 러너 설정 저장(`--resume`)·토큰 미저장·401 복귀 안내
- [ ] **라이브 확인** — 재시작 후 '대기 안 함' 표시, `--resume` 복귀(사용자 테스트)

### TASK-20260828T070000 — 진행 스트리밍 · 인터럽트 · 맥락 전환 · 병렬

**위험도: Major** (§12.3 — 사용자 대면 동작 다수 + 신규 SSE 라우트 + 취소 상태 전이.
인증·인가 경계는 기존 계약 재사용이라 Critical 아님. 되돌리기 = 코드 revert + 재배포.)

#### 사용자 결정 (2026-08-28)

| 축 | 결정 |
|---|---|
| 범위 | 묶음 A(진행 스트리밍 + 인터럽트 + supersede) **+ 병렬 러너** |
| 전송 | **SSE + 55초 상한 재접속** (무제한 SSE 아님 — 배포 pre-drain 90초와의 상호작용을 55초로 묶는다) |
| 재요청 | 미점유 취소 + **점유는 협조적 취소 요청** |
| 늦은 답변 | **409 거절 + 대화 미전달** |

#### 다의어 고지 — "인터럽트가 되었다" 가 무엇으로 판정되는가 (§7.1 · §16.7 G1)

> **입력**: 대기 말풍선이 떠 있는 상태에서 컴포저의 **중단** 버튼 클릭
> **기대 출력**: (1) 말풍선이 즉시 '요청을 취소했습니다' 로 바뀌고 **새로고침해도 유지**,
> (2) `WebAiTasks` 의 그 행이 미점유면 **삭제**·점유면 `Status='canceled'`,
> (3) 그 뒤 개인 AI 가 `submit_answer` 하면 **409** 이고 대화에 답변이 **나타나지 않는다**.
>
> (3)이 판정 핵심이다 — 취소했는데 나중에 답변이 뜨면 "취소가 되었다" 가 거짓이 된다.

#### 왜 신규 도구를 추가하지 않는가 (설계 결정)

협조적 취소를 개인 AI 에게 알리려면 상태 조회 수단이 필요하다. 신규 도구(`check_task_state`)를
더하는 안을 먼저 검토했으나 **`wait_for_request` 를 확장하는 쪽**을 택했다.

- 러너는 이미 `wait_for_request` 에 상주한다. 그 응답에 `canceled_task_ids` 를 실으면 **채널이
  하나 더 생기지 않는다.**
- 대기 루프가 이미 0.5초마다 재조회하므로, 취소를 **그 루프의 두 번째 조건**으로 넣으면 새 질문과
  똑같이 **즉시 인지**된다(P0-J 의 "환경 차이 금지" 가 취소에도 그대로 적용된다).
- 도구 **개수가 불변**이라 P0-I 계약(매니페스트 · 가이드 열거 · `capabilities` · 도구 수 대조
  테스트)이 흔들리지 않는다. 도구를 늘리면 그 4곳이 동시에 어긋날 입구가 열린다.

등록형 AI(러너 미사용)는 이 신호를 안 읽을 수 있다 — 그쪽은 `submit_answer` 409 가 받는다.
**두 겹이지 이중 정의가 아니다**: 인지(러너, 조기 하차)와 집행(서버, 409)은 층이 다르다.

#### 영향받는 파일 · symbol

| 경로 | symbol / 변경 | 비고 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` | `_BRIDGE_CANCELED` 상수 · `wait_for_request` 루프에 취소 조회 + `canceled_task_ids` · `submit_answer` 취소 409 · `bridge_status` phase `canceled` + `steps` · **신규 `GET /api/ai/bridge_stream`** | SSE 는 `app._sse_pack` + `app._counted_stream` 재사용(feature-0014 pre-drain 계량 유지) |
| `unit/feature-0003-agent-web-ui/src/routers/conversations.py` | **신규 `_cancel_bridge_tasks`** (미점유 DELETE / 점유 UPDATE canceled) · `/api/cancel` 배선 · `_enqueue_web_bridge_task` 선행 supersede | `_delete_bridge_task` 는 이 함수로 흡수(술어 중복 제거) |
| `unit/feature-0003-agent-web-ui/src/static/app/composer.js` | `_streamBridgeStatus`(SSE + 재접속) · 폴링 폴백 유지 · 브리지 대기 중 `myAskInFlight` 유지 → 중단 버튼 노출 | PB-0008 시각검증 대상 |
| `unit/feature-0003-agent-web-ui/src/static/app/progress.js` | `_interruptCurrentRunForResend` 가 브리지 대기도 정리 | 기존 R3 경로에 브리지 축 합류 |
| `unit/feature-0043-external-llm-bridge/src/bridge_agent.py` | 워커 N개 동시 처리 · `canceled_task_ids` 확인 후 하차 | 배포본 `static/agent/bridge_agent.py` 와 **해시 일치** 유지 |
| `unit/feature-0003-agent-web-ui/src/static/ai-api-guide.md` | `wait_for_request` 응답의 `canceled_task_ids` 설명 | 도구 **수는 불변** |
| `docs/SECURITY.md` §49 · `docs/ARCHITECTURE.md` · `docs/STATUS.md` · `docs/ROUTEMAP.md` | 신규 라우트 · 취소 상태 전이 | `python3 bin/gen-routemap.py` 재생성 필수 |

#### 접근 방법

1. **취소 정본 먼저** — `_cancel_bridge_tasks` 하나를 만들고 `/api/cancel` · supersede · 중단
   버튼이 **전부 그것을 부른다**. 술어가 두 벌이면 "어디서 취소했느냐" 에 따라 결과가 갈린다.
2. **상태 전이를 서버가 한 단어로** — `phase` 에 `canceled` 를 더한다(기존 4종 + 1). 프런트가
   조합하지 않는다(P0-O 와 동일 원칙).
3. **SSE 는 기존 인프라 재사용** — 새 스트리밍 스택을 만들지 않는다. `_sse_pack`·`_counted_stream`·
   `X-Accel-Buffering: no` 는 프롬프트 자동작성에서 이미 프로덕션 검증된 조합이다.
4. **폴링을 지우지 않는다** — SSE 실패(프록시·구브라우저) 시 기존 `_pollBridgeAnswer` 로 폴백.
   전송 방식이 바뀌었다고 답변 도달성이 나빠지면 개선이 아니다.
5. **러너는 마지막** — 서버 계약(`canceled_task_ids`) 확정 후 붙인다.

#### 완료 판정 기준 (FUNCTION.md §8 AC-53~60 과 1:1)

- 중단 버튼이 브리지 대기 중 **뜬다**(현재는 안 뜸) · 누르면 말풍선이 취소로 바뀌고 새로고침 유지
- 미점유 task 는 DELETE · 점유 task 는 `canceled` · 취소된 task 에 대한 `submit_answer` 는 409
- 재전송 시 같은 대화의 이전 대기 task 가 supersede 되어 **FIFO 역전이 사라진다**
- `bridge_stream` 이 55초 상한 후 정상 종료하고 프런트가 재접속 · `active_streams` 가 0 으로 복귀
- 진행 중 도구 호출이 **답변 전에** 화면에 보인다
- 러너가 워커 N개로 동시 처리하고, 취소된 task 는 제출 전에 하차한다

- status: done (코드·문서·단위검증) / **잔여 = post-deploy PB-0008 실화면 검증**
- risk: Major
- [x] ① 취소 정본 — `shared/bridge_tasks.cancel_bridge_tasks` + `/api/cancel` 배선(서버 run 취소보다 **앞**)
- [x] ② 재전송 supersede — 적재 성공 뒤 실행 + `exclude_task_id` + 프런트 감시 정리
- [x] ③ `wait_for_request` 취소 즉시 인지(`canceled_task_ids`, **신규 도구 0**) + `submit_answer` 409
- [x] ④ `GET /api/ai/bridge_stream` SSE(55초 상한 · `_counted_stream` · 인증 선행)
- [x] ⑤ 프론트 SSE 수신·재접속 + **폴링 폴백 유지** + 중단 버튼 노출 + 진행 단계 렌더
- [x] ⑥ 러너 병렬 워커(기본 2) + 취소 시 자식 프로세스 kill + spin 방지
- [x] ⑦ 테스트(feature-0043 **243건** green · `make test` exit 0) · 문서 · ROUTEMAP · 라우트 골든
- [x] ⑧ **자체 적대 리뷰** — P1 1건(취소 TOCTOU: 취소된 답변이 대화에 append 될 수 있었음) + P2 3건 조치
- [x] ⑨ **PB-0008 브리지 근본원인 수정** — `win_host_ip()` 가 공용 DNS 를 Windows host 로 오판하던 것을 해소(여러 cycle 간 "setup 불가" 의 원인)
- [ ] ⑩ **POST-DEPLOY 실화면 검증** — 중단 버튼 · 취소/대체 말풍선 · 진행 단계 · SSE 재접속
      (대상 코드가 라이브에 없어 배포 전 관측 불가 — `deploy_scope: included` 로 배포 직후 수행)
- [ ] ⑪ **codex 외부 리뷰 재시도** — 이번 cycle 은 계정 사용량 한도로 산출물 0(REVIEW.md 에 기록)

### TASK-20260828T080000 — 미연결 질문 보관·이어받기 (사용자 결정)
- status: done
- risk: Minor (신규 상태값 2종 — 스키마 변경 없음 · 기존 적재 경로 재사용)
- 결정(사용자, AskUserQuestion 2026-08-28): 연결 수명 = **현행 유지**(로그아웃 시 AI 연결 해제) ·
  미연결 질문 = **마지막 1건만 이어받기**
- [x] 미연결도 적재하되 `Status='deferred'`(대기열 비가시) — 적재 경로 통합
- [x] 승격: 연결 후 첫 도구 호출에서 최근 1건만 `open`, 나머지 `expired` (단일 CASE UPDATE)
- [x] 24시간 상한 — 기억에 없는 응답 방지
- [x] 만료 말풍선 정정 + 실패 시 다음 연결에서 재시도(idempotent)
- [x] 미연결 응답을 프런트까지 전달(`bridge_deferred`·`bridge_queued`) — 완료 토스트 오표시 해소
- [x] `expired` 를 terminal phase 로(서버·프런트 양쪽)
- [x] codex P1 5건 중 3건 수정 + P2 3건 중 2건 수정, 2건은 한계 기록
- [x] `make test` 전량 green · 기존 계약 테스트 6건 갱신
- [ ] **라이브 확인** — 미연결 질문 후 연결 시 그 질문이 자동 처리되는지(사용자 테스트)
### TASK-20260828T100000 — 온보딩 지시문의 자기 증명 (외부 AI 거절 제보)

**위험도: Major** (§12.3 — 인증·인가 로직 무변경, 온보딩 문안 + 무결성 증거 노출.
되돌리기 = 코드 revert + 재배포. 신규 라우트·권한 변경 없음.)

**제보(2026-08-27)**: 외부 머신의 AI 가 연결 지시문 실행을 거절했다. 요지 — "단독 공인 IP 에서
사설 CA 를 받아 신뢰하고 같은 곳의 스크립트를 nohup 상주시키는 것은 무제한 원격 명령 채널이다.
평문 베어러 토큰 · '나한테 더 묻지 않아도 돼' · 자체 서명 CA 는 사회공학의 전형 신호다."

**판정**: 거절이 옳다. 코드는 실제로 훨씬 좁았지만(러너가 실행하는 명령은 소스에 하드코딩,
서버는 명령·코드를 보내지 않음) **지시문이 그 사실을 증명할 수단을 하나도 주지 않았다.**
증명이 없으면 남는 것은 신뢰 요구이고, 요구된 신뢰는 공격과 구분되지 않는다.

- status: done (코드·문서·단위검증) / 잔여 = 배포 후 실지시문 육안 확인
- risk: Major
- [x] ① 사회공학 신호 제거 — "나한테 더 묻지 않아도 돼" 폐기, 발급자·발급 경로 명시,
      설치·상주 전 확인 여지 보장
- [x] ② 검증 값 — 서버가 런타임에 계산한 CA 지문(DER 기준)·러너 체크섬을 지시문에 병기 +
      대조 명령(`openssl x509 -fingerprint`·`sha256sum`) + "같은 채널이라 뿌리는 아니다" 고지
- [x] ③ CA 신뢰 **범위** 명시 — `--cacert`/`NODE_EXTRA_CA_CERTS` 는 프로세스 한정,
      시스템·브라우저 저장소 무변경, 전역 설치 미요구
- [x] ④ 토큰 성질 — 세션 결합 · 로그아웃 즉시 무효 · 최대 12시간 · 재발급 경로
- [x] ⑤ 러너 단계 분리 — 내려받기+체크섬 → 소스 확인 → `--check` → `--once` → 상주,
      종료(`kill`)·로그(`bridge.log`) 안내. "턴 예산" 근거는 유지하되 **옮기는 것은 대기뿐**
- [x] ⑥ 러너 소스 상단 '보안 계약' — 받는 것/실행하는 것/하지 않는 것 + 직접 확인 명령 +
      **남는 신뢰 경계 정직 기술**(프롬프트가 상대 에이전트를 구동하는 여지는 남는다)
- [x] ⑦ 계약 테스트 20건(`test_handoff_trust.py`) — 문안 회귀 · DER 지문 정확성 ·
      다중 인증서 fail-closed · 캐시 신선도 · fail-open · 배선
- [x] ⑧ **POST-DEPLOY** — 2회 수행. 1차에서 **문안이 화면에 도달하지 않음**을 발견(→ TASK-20260828T120000),
      수정·재배포 후 2차 PASS(5,664자 · 지문·체크섬 실렌더 · 레이아웃 잘림 없음)

### TASK-20260828T120000 — 지시문이 화면에 도달하지 않았다 (라이브 PB-0008 발각)

**위험도: Minor** (§12.3 — 프런트 1파일에서 중복 사본 제거, 서버 값 사용. 인증·인가 무변경.)

**무엇이 있었나**: TASK-20260828T100000 배포 후 `/ai/connect` 를 실제 브라우저로 열어 보니
**옛 문안**이 나왔다(785자 · 러너·TLS·검증 값 전무 · 거절 사유였던 "나한테 더 묻지 않아도 돼"
포함). 배포는 정상이었다(전 서비스 `54e84874`) — `ai-connect.js` 가 서버가 실어 보낸
`body.handoff` 를 쓰지 않고 **자체 조립**하고 있었다.

`compose_connect_handoff` 의 docstring 이 정확히 이 상황을 경계하고 있었다("표시하는 곳이
둘이라 각자 조립하면 문안이 갈린다 — 한쪽만 고쳐지는 순간 어떤 사용자는 옛 안내를 받는다").
계약은 적혀 있었는데 **모달에만 걸려 있었다**(`test_modal_uses_server_composed_handoff`).
소스 테스트는 전부 green — 검사 대상 목록에 그 화면이 없었기 때문이다.

- status: done (코드·문서·단위검증) / 잔여 = 재배포 후 실화면 재확인
- risk: Minor
- [x] ① `ai-connect.js` 자체 조립 제거 → `body.handoff` 사용(표시·복사 양쪽)
- [x] ② dead code 정리 — `baseOf`(자체 조립 전용) · `issuedToken`(화면이 자격증명을 변수로
      들고 있을 이유가 없다)
- [x] ③ 계약을 **표시하는 화면 전부**로 확장 — `test_every_surface_uses_the_server_composed_handoff`
      (모달 + 단독 페이지 parametrize). 자체 조립 지문(`mcpServers`·인증 줄 연결·옛 마무리 문장)도 금지
- [x] ④ 회귀 역검증 — 단독 페이지를 자체 조립으로 되돌리는 뮤턴트 → KILL 확인
- [x] ⑤ **POST-DEPLOY** — 재배포(`369b40b1`) 후 실화면 PASS: 785자 옛 문안 → **5,664자** 새 문안,
      지문·체크섬 실렌더, 평문 CA 우선, 발급자·운영자지침·토큰노출면 고지 전건 확인.
      레이아웃 `overflow-y:auto` 스크롤 정상·잘림 없음, [복사]는 전문

### TASK-20260828T120000 — 러너 AI 타임아웃을 점유 lease 직전까지 (라이브 실측)
- status: done
- risk: Minor (상수 1개 · 러너 단일 파일 · 서버 무변경)
- 근거: PB-0008 실 브라우저 검증 중 27단계 조사가 900초 벽에 걸려 "AI 호출이 900초를 넘겨
  중단했습니다" 로 끝나는 것을 관측. 서버 lease(30분)는 아직 유효한데 러너만 먼저 포기했다.
- 결정(사용자 2026-08-28): **점유 lease 직전까지 연장**
- [x] `_AI_TIMEOUT_SEC` 900 → 1700 (lease 1800 − 제출 여유 100)
- [x] 두 값의 관계를 계약 테스트로 고정(lease 안 · lease 의 80% 이상)
- [x] 배포본 사본 동기화(해시 일치 테스트 통과)
- [ ] **라이브 확인** — 긴 조사가 900초에 끊기지 않는지(사용자 테스트)
### TASK-20260828T093000 — 라이브 실측 수정 4건

- status: done
- risk: Major (라이브 tight loop + 답변 유실 경로)
- [x] P1 취소 통보를 1회로(점유 해제) — `Status='canceled'` 는 유지
- [x] P2 러너 stall 은 open task 가 있을 때만 집계
- [x] P2 `_failed` 플래그 + `--check`·백오프 두 판정부 교체
- [x] P3 대기를 지운 쪽이 `renderComposer()` 책임 + 입력 핸들러 backstop
- [x] 회귀 9건 + 뮤테이션 역검증(점유 해제 제거 시 3건 KILL)
- [ ] **배포 후 재실측** — 같은 시나리오(Q1 처리 중 Q2 전송)로 러너 생존·Q2 답변 도달 확인

### TASK-20260828T140000 — 진행 표시 구조화 · 내부 동작 단계 · 진행 신호 기반 타임아웃
- status: done
- risk: Minor (표시층 통일 + 상수/갱신 1건 — 스키마 변경 없음)
- 제보(사용자 2026-08-28): ① 추론 단계 누락 ② 실행 단계가 텍스트 나열 ③ 900초 중단
- [x] ①② 뿌리 = 진행 표시가 원장(작업·근거 없음) + 자체 렌더러를 씀 → `agent_runtime.steps`
      + `buildStepDetailEl` 로 통일(말풍선 내 비-SQL 목록도 같은 카드)
- [x] ① 브리지 생애주기 activity 단계(claim·submit) — 출처 `bridge-runtime` 구분
- [x] ③ 도구 호출이 lease 갱신 + 러너 고정 상한 기본 제거(취소는 즉시 유지, opt-in 플래그)
- [x] 신규 20건 + 기존 계약 3건 갱신 · `make test` green
- [ ] **라이브 확인** — 진행 중 카드 구조·내부 동작 단계·긴 조사 무중단(사용자 테스트)
### TASK-20260828T140000 — codex 외부 리뷰 조치

- status: done
- risk: Major (취소 정합·부하·러너 생존)
- [x] P1-1 확인된 변경만 보고 + 못 지운 것은 취소 승격
- [x] P1-2 대기는 항상, 워커 자리는 비차단(취소 채널 유지)
- [x] P1-3 `to_thread` + 동시 상한 + finally 반납
- [x] P1-4 러너를 죽이지 않고 배압 · 일시 장애 영구 skip 금지
- [x] P2 4건(통보 세션 귀속·`_failed` 전 경로·죽은 커넥션·롤백 고아)
- [x] 회귀 7건 + 뮤테이션 역검증
- [ ] **실제 LLM 러너로 사용자 관점 재검토** — 사용자 로그인 후 수행

### TASK-20260828T160000 — 동시 처리를 수요에 맞춰 (사용자 요구)

**위험도: Minor** (§12.3 — 러너 단일 파일 내부 동시성 정책. 서버·인증·데이터 경계 무변경.
되돌리기 = revert + 재배포. 잘못돼도 최악이 종전 고정 동작이다.)

**요구**: "워커는 1개부터 시작하고, 현재 실행중인 워커 개수를 초과하는 동시 요청이 구성될 때
마다 동적으로 확장 … 특정 시간 이상 사용되지 않는 오래된 워커부터 비활성화."

**사용자 결정**(AskUserQuestion): 상한 **8** · 유휴 임계 **5분** · `--workers` 는 **시작값**
(명시해도 동적 확장 유지).

- status: done (코드·문서·단위검증) / 잔여 = 배포 후 라이브 로그로 확장·회수 관측
- risk: Minor
- [x] ① `WorkerPool` 신설 — 슬롯 목록(`last_used`) + Condition. 세마포어는 크기를 못 바꾼다
- [x] ② 확장 — `grow_to(len(pending))`, 상한까지. **관측된 수요에만** 반응(예측 확장 없음)
- [x] ③ 축소 — `reap(now)`: idle 초과분을 **오래된 것부터**, 최소 1 유지, 사용 중 보호
- [x] ④ **LIFO 취득** — 축소가 작동하려면 안 쓰는 슬롯이 계속 안 쓰인 채 남아야 한다
- [x] ⑤ tick = 서버 long-poll 반환. **타이머 스레드·추가 sleep 0**(P0-J 폴링 금지와 정합)
- [x] ⑥ 한 라운드 다건 claim — 확장한 자리를 그 라운드에 채운다
- [x] ⑦ knob 3종(`--workers`/`--max-workers`/`--worker-idle-sec` + 동명 env) · 지시문 안내
- [x] ⑧ 테스트 18건 신규(`test_worker_pool.py`) — 시작 1·수요 확장·상한·LRU 회수·최소 1·
      사용 중 보호·블로킹 대기·배선. 기존 계약 3건은 **skip 없이 새 구조로 이동**
- [x] ⑨ **codex 적대 리뷰** — P1 3·P2 3 전건 조치(포화 시 관측 정지 · 수요 과소계산 ·
      claim `_failed` 오판 · 락 밖 timestamp 정렬 파괴 · 상한 무력화 · 스레드 누수).
      지적된 테스트 사각 5종을 회귀로 잠금(18→23건)
- [x] ⑩ **POST-DEPLOY(부분)** — 배포본에서 **서빙 러너에 풀이 실렸음**(상수 4종)과
      **지시문이 안내 3줄을 렌더함**(5,771자·지문·체크섬 실값)을 컨테이너 런타임으로 확정.
      브라우저 화면 판독은 `win-browser` 세션 발급이 CDP 브리지를 닫는 도구 문제로 미완 —
      화면 도달 경로 자체는 TASK-…120000 에서 실화면 검증됨
- [ ] ⑪ **라이브 확장·회수 로그 관측** — 개인 AI 런타임이 붙은 상태에서 동시 2건 이상

### TASK-20260828T150000 — 실제 LLM 사용자 관점 검증

- status: done (문서 전용 — 코드 변경 0)
- risk: Minor
- [x] 부트스트랩 계정 자율 인증(env 정본) · 검증 후 자격증명 파기
- [x] 실 `claude` CLI 러너로 질문 5건 · 8축 전부 PASS
- [x] codex P1-2(워커 포화 중 취소 수신) **라이브 확정**
- [x] 사전 코드분석 3건 오판을 정직하게 기록
- [ ] **잔여 괴리** — 모델·추론 조작면이 사라진 자리에 설명 없음(UX 결정 필요, 사용자 확인 후)
- [ ] 미검증 — 첨부 업로드·그룹 `@assistant`·동시 다중 대화 체감
