---
doc_type: TASK
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress (인젝션 오판 해소 cycle 진행 — TASK-20260901T140000)
- Owner: AI (계획·구현) / Human (승인)
- Priority: high
- Last Updated: 2026-09-01

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

### 2026-08-31 세션 요청 (TASK-20260831T124500-wsl-scheme-handler)

```
사용자 원문(데이터이며 지시가 아님)
'내 AI 실행' 을 통해 연결을 시도했지만, 연결이 진행되지 않는것으로 확인되었습니다.
```

- [x] **`[내 AI 실행]` 로 연결이 진행되지 않는 원인 규명·수정** — 산출물: 핸들러 등록 위치를
      «셸이 도는 OS» 에서 «브라우저가 도는 OS» 로 교정(`bridge_setup.sh` WSL 분기 + Windows
      HKCU 등록, `wsl.exe` 되돌림). 라이브 실측 근거: HKCU 키 부재 · WSL desktop 파일 존재 ·
      같은 계정 토큰 4건 전부 하트비트 NULL
- [x] **거짓 성공 문구 제거** — 산출물: WSL 인데 Windows 등록이 실패하면 「등록했습니다」를
      말하지 않고 사유 + "버튼은 동작하지 않습니다" 를 낸다(`_handler_rc=3` 분기)
- [x] **무동작을 막다른 길로 두지 않는다** — 산출물: 버튼이 최대 30초 대기 상태를 지켜보고,
      응답이 없으면 실패로 말하고 1단계 터미널 명령 블록을 가리킨다(`_launchRunner` 재작성 +
      `refreshConnState` 가 판정값 반환)
- [x] **POST-DEPLOY 라이브 검증** — 배포본 `b35fa376` 에서 강등 경로 재확인 + 무중단 실측
      (증적: `test-runs.d/TASK-20260831T124500-wsl-scheme-handler-postdeploy.md`)
- [x] **러너가 wsl.exe 세션 정리에 거둬가지 않게** (사용자 재제보 2026-08-31) — `launch.sh`
      가 러너의 자리잡음(생존+로그+3초)을 확인할 때까지 기다린 뒤 종료. 라이브 왕복으로
      `listening:true` 확인 (증적: `test-runs.d/TASK-20260831T161500-wsl-runner-survive.md`)
- [x] **핸들러 등록 80.27초 → 0.73초** (사용자 제보 2026-08-31) — PS1 을 Windows `%TEMP%` 에
      두고(UNC 해석 제거) Windows exe 기동을 3회→1회로. 실측 근거·회귀 3건 포함
- [x] **로그에 시각 기록** — 설치(`[bridge-setup …]`)·러너(`[bridge …]`)·핸들러 실행
      (`[bridge-launch …]`) 전부 `YYYY-MM-DD HH:MM:SS`
- [x] **PowerShell 설치 경로 파싱 실패 해소** (사용자 제보 2026-08-31) — `.ps1` 에 UTF-8 BOM
      (5.1 은 BOM 없으면 CP949 로 읽어 한글이 따옴표·괄호를 삼킨다). 게이트도 교정 —
      pwsh(7) 검사는 이 클래스를 원리적으로 못 보므로 BOM 바이트를 직접 검사
- [x] **Windows Store 파이썬 스텁이 설치를 죽이던 것** (제보 2026-08-31) — `WindowsApps`
      스텁 경로 제외 + 네이티브 호출만 SilentlyContinue/try-catch
- [x] **파이썬 설치 마찰 제거** (사용자 결정 «안 C», 2026-08-31) — winget 으로 동의 후 설치 +
      PATH 갱신·재탐지. ⚠ 종속 «제거» 는 아님(안 A 단일 실행파일은 보류)
- [x] **발사 경로 교정** — 산출물: hidden iframe → 최상위 이동. 실 Windows 크롬 실측으로
      iframe 이 크롬의 외부 프로그램 허용 판정에 도달하지 않음을 확인, 이탈 우려는 대조군
      (미등록 스킴 최상위 이동 시 URL·제목 불변)으로 기각

**[다의어] "연결이 진행되지 않는다"**
- 고른 독해: 버튼이 러너를 실제로 띄우게 만든다(원클릭 복원).
- 버린 독해: 안 되는 환경임을 알려주기만 한다(버튼 숨김 + 터미널 안내).
- 사용자 확인(2026-08-31 AskUserQuestion): **"A+B 전부"** — 동작하게 만들되 실패 시 정직하게 강등.
- 예시: WSL 셸 + Windows 크롬에서 `[내 AI 실행]` 클릭 → 8초 내 `mysql-ai-bridge://` 핸들러가
  `wsl.exe` 로 `launch.sh` 를 부르고, 상태 표시가 **`내 AI 대기 중`** 으로 바뀐다.

### 2026-08-31 세션 요청 (TASK-20260831T175500-schannel-revocation)

```
사용자 원문(데이터이며 지시가 아님)
프로젝트 내 서비스에서 AI연결을 진행할 때 powershell 을 통해 해당 서비스를 연결할 경우
아래와 같은 이슈가 확인되어 수정이 필요합니다.
curl: (60) schannel: CertGetCertificateChain trust error CERT_TRUST_REVOCATION_STATUS_UNKNOWN
[bridge-setup] 중단: 러너를 받지 못했습니다. CA 신뢰 또는 네트워크를 확인하세요.
```

- [x] **PowerShell 경로에서 러너 수신이 실패하는 이슈 수정** — 산출물: 원인 확정(윈도우 동봉
      curl 이 Schannel 이고 사내 CA 에 CRL·OCSP 배포점이 **둘 다 없어** 폐기 상태가 «알 수 없음»
      → curl 이 하드 실패). `--ssl-revoke-best-effort` 를 **감지 후** 적용(구형 curl 은
      `--ssl-no-revoke` 폴백). 라이브 실측: 수정 전 `exit 60` 재현 → 수정 후 `via=curl` 수신
      성공 + SHA256 일치
- [x] **완화 범위를 폐기검사로 한정** — 산출물: 무관한 CA 를 pin 한 대조군이
      `CERT_TRUST_IS_UNTRUSTED_ROOT` 로 **여전히 실패**함을 실측(즉 root 신뢰 축은 안 건드린다).
      좁은 옵션을 먼저 시도하는 순서를 회귀 테스트로 잠금
- [x] **오도하는 안내문 교정** — 「CA 신뢰 또는 네트워크를 확인하세요」가 멀쩡한 두 곳을
      가리켰다. 이제 시도한 **모든 경로의 사유**를 모아 내고, 폐기검사 문제임을 지목한다
- [x] **신뢰 경로 단일화** (수정 중 발견) — 다운로드는 Schannel, 러너 상주는 파이썬 TLS 로
      **평가기가 둘**이라 한쪽만 죽었다. curl 이 막히면 러너와 같은 경로(파이썬 `cafile`)로 받는다
- [x] **pin 우회 폴백 제거** (수정 중 **제가 만든** 결함) — IWR 을 실패-폴백으로 넓혔더니
      OS 신뢰 저장소로 검증돼 **무관한 CA 를 pin 해도 수신이 성공**했다(실측). IWR 제거
- [x] **fail-open 봉인** (수정 중 발견) — 실행 자체가 실패하면 `$LASTEXITCODE` 가 0 으로 남아
      «성공» 이 됐다(실측: 없는 파이썬 경로로 `via=python` 반환). 초기값 127 + 수신 실물 확인
- [x] **실패 사유 유실 봉인** (수정 중 발견) — `SilentlyContinue` 아래 파이프가 stderr
      ErrorRecord 를 버려 회수 길이가 **0** 이었다(실측). `Continue` + 원문만 추출
- [x] **체크섬 재시도 실패 미검사 봉인** (수정 중 발견) — 재시도 실패가 조용히 통과해 다음
      대조가 "체크섬이 다릅니다" 로 오진했다. POSIX 판은 같은 자리에 `|| die` 가 있어 무사
- [x] **POSIX 판 divergence 문서화** — `.sh` 에 «왜 여기엔 그 옵션이 없는지» 주석. 설명 없는
      비대칭은 parity 를 맞추려는 다음 변경이 되돌린다
- [x] **회귀 테스트** — `test_windows_tls_revocation.py` 18건. §16.7 G11-a 준수(대상 파일의
      주석이 단언을 통과시키지 못하게 주석·here-string 제외 코드영역만 검사, PowerShell
      토크나이저와 대조 검증) · G11-b 준수(수정 전 코드에서 **13/18 FAIL** 실증)
- [x] **서빙 사본 동일성 + BOM 유지** — `static/agent/` 양쪽 바이트 동일, `efbbbf` 보존
- [x] **CI 미등재 3디렉토리 등재 + 재발 클래스 구조 잠금** (사용자 결정 2026-09-01) —
      `feature-0041·0043·0008` 을 `ci.yml` 에 추가(근거: 컨테이너 전수 rc=0). 같은 누락이 **4번째**라
      §16.7 G10 에 따라 `Makefile`↔`ci.yml` 경로 집합 동일성 구조 테스트로 승격
      (`test_ci_testpath_parity.py` 5건, 수정 전 4/5 FAIL 실증)
- [x] **POST-DEPLOY 라이브 검증** — 배포본 `b28c3fab` 바이트로 사용자 시나리오 재현: `via=curl`
      수신 성공(167,906 bytes · 3자 SHA256 일치) · 무관한 CA 대조군 실패(pin 유지) · 양 replica
      커밋 일치 · 무중단 실측 `no upstreams available` 0건 (증적:
      `test-runs.d/TASK-20260831T175500-schannel-revocation-postdeploy.md`)

**[다의어] "수정이 필요합니다"**
- 고른 독해: 이 경로가 **성공하게** 만든다(사용자가 러너를 실제로 받아 연결까지 간다).
- 버린 독해: 안내문만 정확히 바꿔 사용자가 스스로 우회하게 한다(예: "curl 옵션을 추가하세요").
- 왜 앞을 골랐나: 로그가 `중단` 으로 끝나 온보딩이 그 자리에서 막힌다. 원인이 **우리 CA 의
  확장 부재**라 사용자가 고칠 수 있는 것이 아니다.
- 예시: 윈도우에서 `.\bridge_setup.ps1` 실행 → `러너를 받는 중…` 다음 줄이 오류가 아니라
  **`러너 체크섬 일치.`** 로 이어지고, `~\.mysql-ai-bridge\bridge_agent.py` 가 실재한다.

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
- [x] ⑪ **라이브 확장·회수 로그 관측** — 실제 러너를 라이브에 붙여 확인:
      `동시 요청 1건(진행 중 1) — 슬롯 1개 확장, 동시 처리 2건` ·
      `유휴 슬롯 1개 회수 — 동시 처리 1건`. **총수요 기준 확장**(codex P1-2)과
      **포화 중 취소 인지**(codex P1-1)가 같은 로그에서 함께 실증됐다

### TASK-20260828T150000 — 실제 LLM 사용자 관점 검증

- status: done (문서 전용 — 코드 변경 0)
- risk: Minor
- [x] 부트스트랩 계정 자율 인증(env 정본) · 검증 후 자격증명 파기
- [x] 실 `claude` CLI 러너로 질문 5건 · 8축 전부 PASS
- [x] codex P1-2(워커 포화 중 취소 수신) **라이브 확정**
- [x] 사전 코드분석 3건 오판을 정직하게 기록
- [ ] **잔여 괴리** — 모델·추론 조작면이 사라진 자리에 설명 없음(UX 결정 필요, 사용자 확인 후)
- [ ] 미검증 — 첨부 업로드·그룹 `@assistant`·동시 다중 대화 체감

### TASK-20260828T200000 — `--check` 가 정상 연결에서도 항상 실패했다 (라이브 실측)

**위험도: Minor** (러너 단일 파일 · 확인용 호출 1줄. 되돌리기 = revert + 재배포.)

**발견**: 동적 워커 풀의 라이브 실측 중 `--check` 가 "연결 실패" 를 출력. 확증해 보니
**연결은 정상**이었다.

| 확인 | 결과 |
|---|---|
| `list_open_requests` | **0.0초 · 200** (연결·인증 정상) |
| `--check` 의 호출(10초 timeout) | **10.0초 read timeout** → "연결 실패" |
| 같은 호출 90초 timeout | **55.3초** 뒤 `timed_out: true` (정상) |

`wait_for_request` 는 **질문이 없으면 55초를 보류하도록 설계**된 도구인데(그것이 '폴링 아님'
의 실체다) `--check` 가 10초 timeout 으로 불렀다. 즉 **대기 질문이 없는 정상 상태에서 반드시
실패**한다 — 그리고 **온보딩 시점이 정확히 그 상태**다. 지시문 ③단계가 `--check` 이므로 외부
AI 는 거기서 멈춘다.

직전 수정이 `_failed` 를 보게 하면서(거짓 "연결 정상" 제거) 이 결함이 드러났다 — **한쪽 오독을
고치니 반대쪽 오독이 보인** 형태다.

- status: done (코드·테스트·라이브 재확인)
- risk: Minor
- [x] ① 확인용 호출을 `list_open_requests`(limit 1, timeout 20s)로 — 같은 인증·같은 경로,
      즉시 응답. 401 판정은 그대로
- [x] ② 회귀 테스트 2건 + 되돌리는 뮤턴트 KILL 확인
- [x] ③ **라이브 재확인** — 같은 서버·같은 토큰으로 `--check` → `연결 정상.`

### TASK-20260828T160000 — 브리지 전 구간 라이브 검증 (PB-0008, 사용자 승인 하 자율 진행)
- status: done
- risk: Minor (문서·증적만 — 코드 변경 없음)
- [x] bootstrap 계정으로 로그인 → 연결 발급 → 러너 기동까지 자율 수행
- [x] ① 제목 2단(적재 즉시 · 답변 시 AI 제안) 화면 확인
- [x] ② 실행 단계 구조화 — 카드 10 · 옛 평문 나열 0
- [x] ③ 내부 동작(추론) 단계 — 도구 단계를 감싸고 출처 구분(bridge-runtime ↔ external-ai)
- [x] ④ 미연결 보관 — 말풍선 "이 질문부터 바로 처리합니다" · DB `deferred`
- [x] ⑤ 이어받기 — 최근 1건 승격·처리, 이전 건 `expired` + 말풍선 정정
- [ ] **미검증** — 긴 조사(10분+)에서의 무제한 대기(질문이 40초 내 종료돼 재현 불가)
### TASK-20260828T150000 — 연결 지속(하트비트) + 로그아웃 시 러너 자동 종료

**위험도: Critical** (§12.3 — 인증 토큰·웹 세션의 **수명 정책** 변경. 잘못 만들면 로그아웃이
집행되지 않는다.) 사용자 confirm 3건(AskUserQuestion 2026-08-28) 후 진행.

**무엇이 문제였나**: 끊기는 경로가 사건으로 분류돼 있지 않았다 — "시간이 지났다" 가 명시적
해제와 같은 취급이었다.

| 관측된 절단 | 원인 |
|---|---|
| 하루 두 번 러너 사망 | 콘솔 토큰 = 발급 후 최대 12시간 · refresh 없음 → `main` 이 401 에서 종료 |
| 14일째 갑작스런 로그아웃 | `WebAuthSessions.ExpiresAt` 고정(슬라이딩 없음) → 파생 토큰 동반 사망 |
| 일하는 중인 러너가 '대기 안 함' | 생존 신호가 `wait_for_request` 하나뿐(워커 포화 시 호출 자체가 없다) |

**사용자 결정 (2026-08-28)**: ① 브라우저 종료는 해제가 **아니다**(러너가 살아 있으면 유지)
② 토큰은 하트비트로 **슬라이딩 연장** ③ 세션은 **활동 기준 슬라이딩 + 절대 상한**.

- status: done (코드·단위검증) / 잔여 = 배포 후 PB-0008 실화면 + 도달성 실측
- risk: Critical
- [x] ① 스키마 — `WebOAuthTokens.LastHeartbeatAt` 멱등 ALTER, fast/slow **양 경로** 보장
- [x] ② `oauth_store.heartbeat()` — 인증과 **같은 resolver** 경유 + `GREATEST`(감소 금지) +
      `LEAST(…, 세션 만료)`(세션 초과 금지). 로그아웃은 UPDATE 자체가 나가지 않는다
- [x] ③ `POST /api/ai/bridge_heartbeat` — 도구 표면 **밖**(P0-I 수 대조 불변) · 원장 미기록 ·
      주기·창을 서버가 응답으로 지정(환경 차이 금지)
- [x] ④ `account_is_listening` = 하트비트 우선 + 원장 폴백(구 러너 무회귀)
- [x] ⑤ 웹 세션 슬라이딩 — `GREATEST(ExpiresAt, LEAST(CreatedAt+90d, NOW()+14d))`,
      throttle(60s) 안에서만 실행. `COALESCE(CreatedAt, NOW())` 로 NULL 시 UPDATE 전멸 방지
- [x] ⑥ 러너 — 하트비트 데몬 스레드(대기 스레드와 **분리**: 바쁠 때도 신호가 나간다) ·
      실패해도 죽지 않음 · 주기 하한 · 배포본 해시 동기화
- [x] ⑦ **로그아웃 시 자동 종료**(추가 요구) — `ActiveTasks` 로 유휴 관측 →
      `shutdown_after_drain`(유휴 즉시 / 진행 중이면 유예 대기 / 초과 시 취소 후 종료)
- [x] ⑧ 안내 문구 정합 — 연결 지시문·러너 보안계약의 "최대 12시간" 서술을 실제 동작으로
      (가이드가 실제와 어긋나면 AI 는 안내받은 대로 갔다가 막힌다 — P0-I)
- [x] ⑨ 계약 테스트 38건 + 기존 스위트 정합(술어 상수화·401 분기 특정) + route golden/ROUTEMAP
- [x] ⑩ 뮤테이션 역검증 **9종 전건 KILL** (로그아웃 우회 · GREATEST/LEAST 제거 · 하트비트 축
      제거 · 최근성 제거 · drain 미호출 · 등록 경합 · 유예 무시 · 스레드 1회). 1차 실행은
      하네스 고장(컨테이너 pytest 부재)으로 전건 '생존' 오판 — 신호 없음을 실패로 승격해 재실행
- [ ] **배포 후 실측** — PB-0008 실 Windows 브라우저(`/ai/connect` 문구 도달) + 러너 24시간
      연속 유지 + 로그아웃 시 자동 종료

### TASK-20260828T170000-runtime-model-selector — 러너 신고 기반 모델·추론등급 선택기 (P0-T supersede)

**요청**: "웹브라우저 내 [모델 + 추론수준] 설정을 되살립니다. 해당 설정값에 따른 워커를
동작시키고(없다면 워커 확장) 요청을 전달하는 방식으로 구성해주세요. 이는 각 AI플랫폼에
대응되어야 하니 모델 종류의 확장도 염두해주세요. (claude 뿐만 아니라, codex 등...)"

**발단**: "간단한 요청에도 큰 모델이나 깊은 추론수준이 진행되는 비효율" — 실측 결과 러너가
`--cmd` 없이 떠 있어 모든 요청이 그 머신의 기본 모델 + `effortLevel: high` 로 처리되고 있었다.

- [x] 러너 `_RUNTIME_SPECS` 표 — claude·codex·gemini·ollama (신규 플랫폼은 이 표에 1항목)
- [x] `detect_runtimes()` — 설치된 전부 신고, ollama 는 `/api/tags` 실조회
- [x] 하트비트 본문에 능력 신고(별도 채널 없음 — 살아있음과 능력은 같은 사실의 두 면)
- [x] 스키마 `RunnerCapabilities` · `RequestedRuntime` 온라인 DDL
- [x] `set_runner_capabilities` — 값 변경 시에만 쓰기, 술어는 하트비트와 동일
- [x] 카탈로그를 신고 기반으로 (신고 없으면 `hidden` 유지)
- [x] 전송·적재·전달 복원 + `_split_runtime_model`
- [x] `build_cmd` — 런타임별 실제 CLI 인자, **표 밖 값 거부**
- [x] 서버 `_sanitize_runtimes` (신뢰 경계)
- [x] 화면 — 런타임별 추론등급, 모델 변경 시 등급 재렌더
- [x] hydration 이 신고 목록과 대조(낡은 선택 복원 차단)
- [x] 테스트 신규 39건 + P0-T 계약 5건 재작성 · `make test` 전체 통과
- [x] 문서 (FUNCTION P0-Z3 · MODIFY · TASK · REPORT · TEST)
- [ ] **라이브 확인** — 러너 재기동 후 선택기 노출·플랫폼 그룹·등급 반영(사용자 테스트)
- [x] **배포 후 실측** — 배포(`396c0372`, 무중단 0건) 후 PB-0008 **5축 PASS**: 새 문구 실렌더
      (5,942자·옛 문구 부재) · 하트비트 200 · DB 간격 **720분**(TZ 축 수정 실증) ·
      `listening` false→true · **로그아웃 직후 하트비트 401**
- [ ] **잔여 실측** — 실 러너 기동 상태에서의 자동 종료 · 12시간 이상 연속 유지
      (둘 다 시간이 흘러야 관측된다)

### TASK-20260828T180000 — 진행 표시 자리·귀속 정합 (사용자 제보)
- status: done
- risk: Minor (앵커 위치 · meta 각인 · 폴백 조건 1건씩)
- 제보: 새 질문 말풍선에 **직전 답변의 「단계 보기 (21)」**, 그리고 진행 단계가 **말풍선 밖**에 나열
- [x] ① placeholder meta 에 `run_id = task_id` 각인 — 자기 run 의 단계를 가리키게
- [x] ② 진행 단계 앵커를 행 → **말풍선**으로 이동
- [x] ③ progress 폴백에서 브리지 run 제외(`t\_%`) — 내부 progress-strip 이중 렌더 차단
- [x] 신규 7건 · `make test` 신규 실패 0(feature-0008 4건은 main 에도 있는 기존 실패)
- [ ] **라이브 확인** — 새 질문 시 카드가 말풍선 안에, 단계 수가 자기 것인지(사용자 테스트)
- [ ] **배포 후 실측** — PB-0008 실 Windows 브라우저(`/ai/connect` 문구 도달) + 러너 24시간
      연속 유지 + 로그아웃 시 자동 종료
### TASK-20260828T220000 — 첨부 **쓰기** 복원 (assistant 파일 수정·생성)

- status: done
- risk: Major (§12.3 — 외부 입력이 첨부를 쓴다. 저장 가드는 기존 것을 그대로 쓰되 경로가 는다)
- 사용자 제보: "assistant가 첨부된 파일을 수정하여 버전관리는 진행하거나 새로운 첨부파일을
  추가하는 동작이 가능했습니다."
- [x] **결손 실증** — 라이브 `87d1beec`, 첨부 1246 `sample.sql`. 개인 AI 가 `attachment-edit`
      블록을 정확히 만들었으나 `versions` 는 v1 그대로, 블록은 strip 되지 않아 원문 diff 가
      채팅에 노출, 답변은 "수정했습니다" → **거짓 성공**
- [x] **P0-E 근거 정정** — 「개인 AI 가 관례를 모른다」가 사실이 아니었다. 규약은
      `system_prompt`(agent_core base)에 실려 이미 전달되고 있었다
- [x] **한 벌로 합침** — `_apply_assistant_attachment_blocks`(web 층 `routers/conversations.py`)
      신설, worker(`modules/ask.py`)의 중복 구현을 이 함수 호출로 교체, 브리지가 같은 함수 사용
- [x] fence 계수(`_count_attachment_block_fences`)도 공용화 — 인용 fence·들여쓴 fence 제외
- [x] 회수 store 에 **정리본** 기록(원문 블록 재유입 차단) · 영속 실패 시 원문 유지
- [x] 러너 프롬프트에 규약 **중복 정의 금지**(주석으로 이유 고정 + 회귀로 잠금)
- [x] 회귀 12건 신규(`test_bridge_attachment_write.py`) — 배선 3 · 한 벌 3 · 거짓 성공 금지 5 ·
      중복 안내 금지 1
- [x] **라이브 재실증**(머지 전 bind-mount) — `attachment-new` 생성 · user 계보 편집은 새 root
      분기(설계대로) · **assistant 계보 편집은 v1→v2 연장** · 실 Windows 브라우저에서 블록 헤더
      미노출·첨부 칩 표시 확인
- [x] **POST-DEPLOY** — 배포본 `e5223dcc` 에서 v4 생성 + 신규 첨부 생성 + 실 브라우저 판독 PASS · 무중단 실측 0건
- [x] **codex 적대 리뷰** — P1 4 · P2 2 전건 조치(제출-전달 사이 `done` 조기 노출 · 0행 갱신을
      영속으로 오보 · 미전달 분모가 실 파서와 불일치 · 블록만 있는 답변에서 원문 부활 ·
      테스트 2건 vacuous). 뮤테이션 역검증 5종 전건 KILL

### 잔여 (이 cycle 밖)

- 동기 inproc 경로(`_ask_impl`)의 첨부 후처리는 아직 별개 구현 — 응답 shape·step 기록이 얽혀
  있어 분리했다. **합친 것은 브리지(없던 것) + worker(중복) 2개**

### TASK-20260828T230000-caps-self-report — 능력 목록을 AI 자신이 정한다 (P0-Z4)

**요청**: "실제 연결된 AI에 따라 '고를 수 있는 것'을 제한하여 노출. 노출 기준을 설정하는 것은
연결 중 시도된 AI 스스로. 모델 및 추론레벨 형식에 맞추어 연결 시 답변되도록. claude 및 codex 등
AI 플랫폼에 관계없이, 클라이언트가 자유롭게 서술한 모델과 추론레벨을 관대하게 수용"

- [x] `_CAPS_PROBE_PROMPT` — 형식을 정확히 요구하는 질의문
- [x] `probe_runtime_caps` + 관대한 파싱 3종(`_extract_json`·`_coerce_options`·`_coerce_flag`)
- [x] 호출법(플래그)도 AI 응답에서 받기 → 플랫폼 무관
- [x] 표 밖 CLI 지원(`--ai <이름>`, 두 호출 형태 시도 후 통한 것 기억)
- [x] `config.json` 캐시 + `--refresh-caps` + 내장 표 폴백
- [x] 병렬 질의 + 명시적 옵트인(`probe=True`)
- [x] 플래그 미유출(서버 신고에서 제외) — 신뢰 경계 유지
- [x] 테스트 신규 14건 + 기존 계약 5건 갱신 · `make test` green
- [x] 문서 (FUNCTION P0-Z4 · MODIFY · TASK · REPORT · TEST)
- [ ] **라이브 확인** — 러너 재기동 후 AI 응답 목록이 화면에 뜨는지(사용자 테스트)

### TASK-20260829T000000-resume-ai-scope — `--ai` 상속이 런타임을 지웠다 (P0-Z5)

라이브 재기동에서 발견 — P0-Z4 배포 후 codex 가 신고에서 빠졌다.

- [x] `--resume` 의 `ai` 상속 제거 (base·ca·cmd 만 복원)
- [x] 저장은 명시 `--ai` 만
- [x] 회귀 테스트 2건 · 문서 (FUNCTION P0-Z5 · MODIFY · TASK · REPORT)
- [x] 재기동으로 라이브 확인

### TASK-20260828T200000 — 진행 표시를 기존 두 자리에서 갱신 (사용자 제보 2차)
- status: done
- risk: Minor (표시층 — 서버 무변경)
- 제보: 사이드바(실행 단계 패널)가 갱신되지 않고, 단계가 「실행 단계」 드롭다운 **밖**에서 갱신됨
- [x] `.bridge-live-steps` 제3 블록 폐기 — 말풍선 details 를 `renderMessageDetails` 로 재구성
- [x] 「단계 보기」 개수 + 클릭 대상 함께 갱신(리스너 중복 방지)
- [x] 사이드 패널 run 단위 갱신(`refreshStepSidePanelForRun`) — 다른 run 은 덮지 않음
- [x] 신규 7건 · 기존 계약 1건 갱신 · `make test` green
- [ ] **라이브 확인** — 진행 중 드롭다운·개수·패널이 함께 늘어나는지(사용자 테스트)
### TASK-20260828T240000-connect-gate — 요청과 연결을 가른다 (P0-AB · P0-AC)

**요청**: "[assistant 요청, 브릿지 연결] 을 각각 구분 / 브릿지가 연결된 상태가 아니라면 요청이
막히고 브릿지 연결 가이드가 곧바로 제공 / 요청이 막힘에 따라 메세지 박스 내 상호작용도 진행되지
않도록 (연결 완수 후 활성화) / AI요청을 통한 연결보다 정형화된 형식으로 연결하는 방법 검토 —
현재는 LLM에 요청함에 따라 구축하는 방식이 모두 달라 사용자 경험이 일정하지 않음"

**허용 기준(사용자)**: "머신 내 DQA프로세스가 실행중인지, 토큰이 연결되어 있는지 여부를 점검"

- [x] 게이트 = `connected ∧ listening`, 판정은 서버 1곳(`compose_blocked`) — 프런트 재조립 금지
- [x] `bridge_mode` 전제 — 서버 LLM 이 열려 있으면 잠그지 않는다(멀쩡한 서비스 정지 방지)
- [x] 서버 집행: 토큰 없음 → `409 bridge_blocked`, 적재·저장 **0**
- [x] 보류(`deferred`) 축 이동: `connected` → `listening` (게이트 통과 후 러너 꺼진 창만 보관)
- [x] 컴포저 잠금: 입력·전송·첨부·모델 (`is-bridge-locked`) + `sendPrompt` 가드 + 409 흡수
- [x] 안내 패널(사유별 2문구) + 조치 버튼 → 연결 모달. 잠금 중에만 5초 재조회 → 자동 해제
- [x] 원클릭 연결: `compose_launch_commands` + `bridge_setup.sh`/`.ps1`(CA·체크섬 대조 → 핸들러
      등록 → `--check` → 상주). AI 지시문은 `<details>` 보조로 강등
- [x] 브라우저 기동: `mysql-ai-bridge://` 스킴 + `[내 AI 실행]` 버튼 (HKCU·사용자 범위만)
- [x] 엣지: 설치 스크립트 2개를 평문 HTTP 경로에 추가(부트스트랩 데드락 해소, 범위 못박음)
- [x] 정본/배포본 해시 일치 테스트(러너와 같은 계약)
- [x] 테스트 신규 32건 + 기존 계약 9건 갱신 · `make test` green · ruff clean
- [x] **PB-0008 실 Windows 브라우저** — 잠금·해제·모달 실측 (test-runs.d 참조).
      그 과정에서 결함 3건 발견·수정(연결 칩 미표시 · 패널 위치 · 엣지 평문 경로)
- [x] 문서 (FUNCTION P0-AB/P0-AC · ANCHOR §3 direction-drift · TASK · TEST)
- [x] **사용자 확인 — 실패로 돌아왔다** (2026-08-31): 원클릭 명령·러너 상주까지는 동작했으나
      `[내 AI 실행]` 재기동이 **무동작**. 원인은 핸들러를 «셸이 도는 OS»(WSL)에 등록해
      Windows 브라우저가 보지 못한 것 → `TASK-20260831T124500-wsl-scheme-handler` 로 조치.
      재확인 대상은 그 조치 이후의 재기동이다
- [ ] **§4 direction-drift 엔트리** — ANCHOR §4 는 human-only(§18.2). 사람이 추가
### TASK-20260828T171500-tool-permission-friction — 승인을 요구하는 답변 제거

**요청** (라이브 제보 2026-08-28): "assistant 작동에서 사용자가 '도구 사용 승인' 에 대한
과정을 직접 진행하는 부분은 전혀 의도하지 않았습니다. assistant는 제공된 모든 도구를 사용할
수 있지만, 현재는 사용자에게 권한을 요청하고 있는 상황이고 사용자는 이를 승인할 수 있는
방법도, 승인해야할 이유도 없습니다."

- [x] **원인 실증** — `claude -p` 직접 구동. MCP 도구는 권한 프롬프트 **없이** 호출됐고
      반환은 `HTTP 401 유효하지 않거나 만료된 토큰`. 권한 게이트가 아니라 **자격증명 경합**
- [x] **실행 측** — `--strict-mcp-config` 로 상주 MCP 표면 배제 (실측: 도구 0개).
      `--mcp-config` 미동반 확인 — 함께 주면 배제가 아니라 교체가 된다
- [x] **프롬프트 측** — 승인 요구 금지 + 실패 시 대체 행동 + 토큰 단일화 3계약
- [x] **권한은 낮추지 않는다** — `--dangerously-skip-permissions`·`bypassPermissions` 미사용을
      회귀로 잠금(보안 계약 유지). 사용자 결정 2026-08-28
- [x] 배포 사본(`static/agent/bridge_agent.py`) 동기화 — sha256 대조 계약
- [x] 회귀 11건 신규 + 기존 계약 3건을 base-argv 유도형으로 갱신
- [x] 뮤테이션 역검증 5종 전건 KILL (적용 여부 앵커 단언 + 복원 sha256 확인)
- [x] `make test` 전량 green (exit 0) · ruff clean
- [ ] **라이브 실증** — 배포 + 러너 재기동 후 첨부 질문에서 승인 요청이 사라지는지
      (사용자 화면 확인 필요)

**codex 적대 리뷰 조치** (REV-20260828T171500 — P1 4 · P2 4 전건):

- [x] **P1-1** 학습 플래그로 MCP·권한 축 되열기 차단(`_FORBIDDEN_FLAG_FRAGMENTS` — 형태가
      아니라 축을 본다. 치환자 포함 토큰도 검사)
- [x] **P1-2** `--cmd` claude 경로 1회 경고(명령은 고치지 않는다 — 사용자가 통째로 준 것)
- [x] **P1-3** `BRIDGE_KEEP_MCP=1` 탈출구(배제는 그 사용자의 **모든** MCP 에 걸린다)
- [x] **P1-4** 계약 미준수 답변을 제출 경로에서 감지·안내 덧붙임 + FUNCTION 문구를
      「지시이지 집행이 아니다」로 정정(REVIEW 와 어긋나 있었다)
- [x] **P2-1** 회귀 29건 추가 + 뮤턴트 3종 추가 역검증(M6 11 KILL · M7 1 · M8 2)
- [x] **P2-2** 구버전 claude 플래그 미지원 시 빼고 경고(확인 실패 시엔 남긴다)
- [x] **P2-3** `REQ-20260828-tool-permission-friction` + `AC-…-1~7` 정의, TEST 15건 매핑
- [x] **P2-4** EOF whitespace

### TASK-20260828T193000-ai-assisted-setup — 환경 판단만 AI 에게 (P0-AD)

**요청**: "목적 자체는, LLM CLI에 연결시키기만 하면 됩니다. 그렇다면 해당 부분만, 각 머신에
설치된 LLM의 도움을 받아 능동적으로 세팅되도록 구성해도 문제없을지 검토해주세요."

- [x] **검토** — 조건부 가능. 경계는 「LLM=판단, 스크립트=실행」. 그 경계를 넘으면 P0-AC 가
      고친 문제(구축 방식이 매번 다름)로 되돌아간다
- [x] `bridge_setup.sh` — `BRIDGE_PROBED_*` 네 칸 + 실존·타입·범위·allowlist 검증
- [x] `bridge_setup.ps1` — 동형 (pwsh7 PARSE OK + 동형 동작 실측)
- [x] 서버 `compose_probe_setup_instruction` — 명령에 **실재하는 빈칸** + 위임 금지 3항
- [x] 화면 — 모달·단독페이지 **양쪽**에 셋째 경로(결정론 → AI조사 → AI전부위임)
- [x] 자체 발견 결함 2건 — `drop()` 이 stdout 이라 경고가 명령치환에 먹힘 · 지시문은 빈칸을
      요구하는데 명령에 빈칸이 없었음
- [x] 회귀 93건(기본 61 + codex 조치 32) · 뮤턴트 5종 전건 KILL
- [x] **codex 적대 리뷰** — P1 3 · P2 4 전건 조치 (아래)
- [x] `make test` 전량 green · ruff clean
- [ ] **라이브 실증** — 배포 후 실제로 AI 에게 조사 지시문을 주고 러너가 뜨는지
      (러너 재기동 토큰이 필요해 사용자 화면에서 완결)

**codex 적대 리뷰 조치** (REV-20260828T193000):

- [x] **P1** `BRIDGE_PROBED_AI=rm` 통과 → 알려진 AI CLI allowlist(sh·ps1·지시문 3곳 동기)
- [x] **P1** UI 가 "결과는 ①과 같습니다" 로 단정 → 「스크립트가 같다」로 정정 + 비결정성 고지
- [x] **P1** 문서 미갱신 → FUNCTION P0-AD · MODIFY · TASK · REVIEW · TEST 작성
- [x] **P2** `--workers .` · `1..2` · `999999999` 통과 → 축별 타입·범위 검증
- [x] **P2** `native` 모드가 `auto` 와 동일 구현 → 공개 목록에서 제거
- [x] **P2** python 탐색 순서가 sh(`python3`)·ps1(`python`)·지시문 3곳 불일치 → 통일
- [x] **P2** 테스트가 문자열만 봄 → `set --` 로 실제 argv 전개 검사 + 위험값 회귀 32건

### TASK-20260831T100000-console-llm-parity — 관리 콘솔을 브리지 구조에 정합 (사용자 요청)

**요청**: "프로젝트 내 서비스에서, LLM 동작 과정이 바뀐 구조에 따라 '관리 콘솔' 에서 작동하던
LLM의 동작도 정합하게 구성하고 싶습니다."

**위험도: Major** (§12.3 — 다수 파일 · `WebAiTasks` 비파괴 ALTER 2컬럼 · 신규 세션인증 API ·
러너 계약 확장. 인증·인가 규칙 변경 없음, 파괴적 데이터 없음. 되돌리기 = 게이트 1개
(`AGENT_SERVER_LLM_ENABLED=1`) + revert + 재배포. ALTER 는 `ALGORITHM=INPLACE, LOCK=NONE`
비파괴 ADD 라 롤백 시 잔존해도 무해.)

<!-- PLAN-APPROVED by mckim on 2026-08-31 -->

#### 진단 — 무엇이 어긋나 있었나

feature-0043 이 서버 계정 LLM 을 fail-closed 로 차단하고 대화 답변을 개인 AI 브리지로
뒤집었는데, **그 전환이 대화 화면만 따라갔다.** 관리 콘솔은 게이트의 존재를 모른다 —
`static/admin/*.js` 전체에 `server_llm_blocked` 참조가 **0건**이다. 그 결과:

| 축 | 어긋난 모습 |
|---|---|
| 조작면 | 버튼은 그대로 있고 **눌러야** 503 을 안다 (메타 자동완성 2 · 프롬프트 자동작성 3 · 능동 분석 1) |
| 설정·권한 | 저장은 되는데 집행되지 않는다 (모델 접근권한 · 추론 예산 · 자가 리뷰 · 실행 타임아웃) |
| 관측 | `LLM 사용량` 이 0 으로 수렴 → "아무도 AI 를 안 쓴다" 로 오독. `추론` 탭 영구 공백 |
| 부재 | 새 구조(연결된 러너 · 대기 큐)를 볼 자리가 관리자에게 없다 |

#### 사용자 결정 (AskUserQuestion 2026-08-31)

1. **하이브리드 + 브리지 위임 전면** — 정직화와 위임을 함께.
2. **미적용 배지 + 패널 내부 dropdown + 화면 최하단 집계 섹션**.
3. **AI 운영 현황에 브리지 축 추가**.
4. **위임 경계**: 관리자 실행 4종 + 배치 2종(insight sweep · cluster_label). **red-team 은
   배치가 아니라 「답변한 그 AI」에게** — 호출자가 자기 대화내역을 알기 때문. 모든 위임 작업은
   **상태와 계정 귀속이 화면에 명시**되어야 하고, 산출물은 **자율적으로 입력**된다
   (기존 경로의 쓰기 의미를 그대로 보존 — 검토형은 검토형으로, 자동기입형은 자동기입형으로).
5. **구 러너**: 자동 갱신 유도.

#### 설계 요지 — 콘솔 작업은 「대화가 없는 브리지 task」

새 파이프라인을 만들지 않는다. `claim_request` 는 이미 서버가 조립한 `system_prompt` 를
넘기고 `submit_answer` 는 텍스트를 받는다 — 콘솔 작업은 그 계약의 한 갈래다.

| 지점 | 대화(기존) | 콘솔 작업(신규) |
|---|---|---|
| 적재 | `Origin='web'` + `ConversationId` | `Kind='job'` + `JobPayload`, 대화 없음 |
| 배급 | `wait_for_request` → `claim_request` | 같은 도구. **능력 신고 러너에게만** |
| 프롬프트 | 5단계 지침 + 질문 + 대화 문맥 | 서버 조립 작업 프롬프트 (**기존 헬퍼 재사용**) |
| 회수 | 대화 말풍선 덮어쓰기 | `Answer` 저장 → 콘솔 폴링 → 기존 저장 경로로 write-through |

**두 벌 금지**: 프롬프트 조립은 `_assemble_{product,role,account}_prompt_llm_request` ·
메타데이터 · `node_analysis` 의 **기존 함수를 부른다**. 여기서 다시 쓰면 경로에 따라 다른
규칙으로 산출되고, 그때부터 한쪽은 반드시 낡는다 (P0-P 가 같은 함정을 이미 통과했다).

**구 러너 오염 차단**: 콘솔 작업을 모르는 러너가 그것을 집으면 채팅 프레이밍으로 감싸
JSON 산출물을 망친다. P0-Z3 의 원칙("신고가 없으면 선택기도 없다")을 그대로 적용 —
`features` 를 신고한 러너에게만 배급하고, 구버전에는 하트비트 응답으로 갱신을 지시한다.

#### Phase A — 정직화 (게이트를 화면이 안다)

- [x] **A1** 게이트 상태 단일 출처 — 관리 콘솔 부트스트랩 응답에 `server_llm_blocked` +
      위임 가능 여부. 프론트는 `adminState.llmGate` 한 곳만 읽는다 (판정을 화면마다 조립하면
      갈린다 — `can()` 류 display-permissive 게이트와 섞지 않는다)
- [x] **A2** 죽은 조작면 6종 — 누르기 **전에** 상태를 말한다. 위임 가능하면 위임 흐름으로,
      불가하면 disabled + 사유 + 조치 경로(연결/러너 갱신)
- [x] **A3** 죽은 설정·권한 4종 — 헤더 `미적용` 배지 + 패널 내부 `<details>`(왜·무엇이 대신·
      되돌리는 법) + **설정 탭 최하단 「현재 미적용 기능」 집계 섹션**
- [x] **A4** 관측 오독 차단 — `LLM 사용량` 상단 배너(이 집계는 차단 이전분 · 현재 활동은
      외부 AI 작업) · `추론` 탭 공백 대신 안내 · 계측 커버리지에서 '차단됨' 과 '미계측' 분리

#### Phase B — 브리지 관측 축

- [x] **B1** `ai_ops.py` `_bridge_axis()` — 연결 계정 수 · listening 러너 수 · open/working
      task 수 · 최근 제출 지연. worst-of 롤업 참여
- [x] **B2** KPI 타일 + 위임 작업 현황 표 — **어떤 작업이 · 어떤 상태로 · 어느 계정에서**
      (사용자 결정 4의 명시 표기 요구)

#### Phase C — 위임

- [x] **C1** 스키마 — `WebAiTasks` 멱등 ALTER: `Kind` · `JobPayload` · `JobResultAt`
- [ ] **C2** 적재 — `shared/bridge_tasks.enqueue_console_job()`. 배급 가능한 러너가 없으면
      **적재하지 않는다** (P0-S 동형 — 아무도 못 집는 작업을 쌓지 않는다)
- [x] **C3** 러너 능력 신고 — 하트비트에 `features` + `agent_version`. 구버전이면 응답으로
      갱신 지시(사용자 결정 5)
- [x] **C4** 배급·전달 — `wait_for_request`/`list_open_requests` Kind 필터,
      `claim_request` Kind 분기(대화 문맥·제목 규약 없이 `job` 블록)
- [x] **C5** 회수 — `submit_answer` Kind 분기. 대화 배달 대신 결과 저장 + **기존 저장 경로로
      write-through**(검토형은 폼에, 자동기입형은 저장소에 — 각자의 기존 의미 보존)
- [ ] **C6** 폴링 — `GET /api/admin/ai-jobs/{task_id}` 세션 인증, 본인 적재분만, 본문 포함
- [ ] **C7** 관리자 실행 4종 전환 — 메타 자동완성(단건·일괄) · 그래프 능동 분석 ·
      프롬프트 자동작성(제품·역할·개인)
- [ ] **C8** 배치 2종 전환 — insight sweep · cluster_label. 소유 계정·상태를 원장에 남긴다
- [ ] **C9** red-team 전환 — 배치가 아니라 **답변한 그 러너**가 자기 답변을 5축 자가 검증해
      함께 제출. `추론` 탭이 다시 채워진다
- [ ] **C10** 러너 — `compose_prompt` job 분기(verbatim + 도구 블록, 제목 마커 제외) ·
      배치 opt-out · 정본↔배포본 **해시 일치 유지**

> **진행 상태 (2026-08-31 세션 종료 시점)**
>
> A·B 는 **코드 완료 + 전량 green**. C 는 **배급·회수 계약까지** 서 있고, 각 기능의
> **적재 호출부·프롬프트 조립·산출물 반영**(C2 호출부 · C7~C10)이 남았다.
>
> 그 미완을 화면이 낙관하지 않도록 `JOB_SPECS[...]["wired"]` 를 **전부 False** 로 두었다 —
> `enqueue_console_job` 이 거절하고, 조작면은 `jobDelegable(jobKind)` 로 종류마다 판정해
> 사유와 함께 비활성으로 보인다. **부분 배선을 True 로 적지 않는 것**이 이 feature 가
> P0-M·P0-T 에서 두 번 밟은 함정("고를 수 있는데 반영은 안 되는")을 다시 열지 않는 유일한 방법이다.
>
> 즉 현재 상태에서 C 는 **비활성이며 안전하다**: 콘솔 작업은 적재되지 않고, 대화 브리지
> 경로의 술어는 구 러너에게 종전과 **동치**다(가지 1개).

#### Phase D — 검증

- [ ] **D1** 단위 — 게이트 3갈래(차단+위임가능 / 차단+위임불가 / 게이트해제) 양방향 잠금
- [ ] **D2** 구 러너 회귀 — `features` 미신고 러너에 콘솔 작업이 **배급되지 않음**
- [ ] **D3** `make test` 전량 green + ruff
- [ ] **D4** `verify-completion.sh --pre-commit`
- [ ] **D5** PB-0008 실 Windows 브라우저 시각검증 (`visual_verification_scope: always` — hard gate)
- [ ] **D6** 배포 (`deploy_scope: included`) + POST-DEPLOY 실측

#### 완료 판정 기준 (acceptance criteria)

- 관리 콘솔의 어떤 LLM 조작면도 **누르기 전에** 자기 상태를 말한다 (503 토스트로 처음 알게
  되는 경로가 0건).
- 집행되지 않는 설정·권한은 `미적용` 배지 + 사유 dropdown 을 갖고, 설정 탭 최하단 집계
  섹션에서 **한 자리에 모여** 보인다.
- `AI 운영 현황` 이 브리지 축을 롤업에 포함하고, 위임 작업의 **상태·소유 계정**을 표시한다.
- 위임 6종(관리자 4 + 배치 2)이 연결된 러너로 흘러 산출물이 **기존 저장 경로**에 도달한다.
- red-team 자가 검증 결과가 `추론` 탭에 다시 나타난다.
- `features` 미신고(구) 러너에는 콘솔 작업이 배급되지 않고, 화면이 갱신을 안내한다.
- `AGENT_SERVER_LLM_ENABLED=1` 로 되돌리면 종전 직접 경로가 복원된다 — 테스트가 양방향을 잠근다.

#### 적대 리뷰 조치 (REV-20260831T140000-console-job-scope)

- [x] **P1** 자격을 계정 최신 러너가 아니라 **그 토큰**의 신고에서 읽는다
      (`oauth_store.token_runner_profile`) — 동의하지 않은 러너에게 배치가 새던 경로
- [x] **P1** `_load_task` 배치 확대를 **제출 경로 opt-in** 으로 좁힘 — 조사 도구가 배치 task 의
      `ProductId`/`DatasourceKey` 를 스코프 bearer 로 쓰던 경로
- [x] **P2** `serialize_runner_features` 가 컬럼 폭 안에서 **항목 단위로** 끊는다 —
      `…,batch_jobs_evil` → `…,batch_jobs` 위조 차단
- [x] 회귀 9건 신설 + **뮤턴트 3종 전건 KILL 실증**. 첫 작성본이 뮤턴트를 못 죽인 원인
      (길이 정렬 우연 · filler dedup)까지 REVIEW 에 기록
- [x] **D3** `make test` 전량 green (6020 passed / 0 failed) + ruff clean
### TASK-20260831T110000-runtime-caps-restore — 쓸 수 있는 모델·추론등급이 화면에서 사라졌다 (P0-AE)

**요청**: "assistant(내 AI에 연결되었을 때) 에서 사용할 모델, effort가 확인되지 않는 이슈가
확인되었습니다. 사용자 재량대로 각 설정값을 적용하여 사용할 수 있도록 구성해주세요."
+ "설정된 모델 및 effort를 포함한 요청을 브릿지가 수신할 경우 실제 해당 설정값을 통해
LLM처리를 수행하도록 구성해주세요."

**사용자 결정**: 목록은 **연결된 AI 로부터 전달받는다**(사용자가 직접 타이핑하지 않는다) ·
지정값은 **계정 기본값 + 대화별 override** 로 기억한다.

**라이브 진단** (수정 전 실측):

| 관측 | 값 |
|---|---|
| 러너 신고(토큰 #47, 하트비트 정상) | claude: models=[opus,sonnet,haiku] **efforts=[]** · codex: 내장 폴백 |
| 직전 신고(#42, probe 성공본) | claude: +fable, efforts 5단계 · codex: gpt-5.6-* 6종 |
| 러너 캐시 `config.json` | `"efforts": [], "effort": null, "source": "probe"` |
| `claude --help` 실측 | `--effort <level>  Effort level for the current session` — **플래그는 실재한다** |
| `WebAiTasks` #69·#70 (당일) | `RequestedRuntime=NULL` `RequestedModel='claude-haiku-4'` `ReasoningLevel=NULL` |
| `WebAiTasks` #62·#65~68 (8/28) | `claude` / `sonnet` / `high` — 정상 |

**근본 원인 2건** (독립적이고, 둘 다 사용자 화면에서는 같은 증상으로 보인다):

- [x] **A. 부분 응답이 축을 통째로 죽였다** — `probe_runtime_caps` 가
      `efforts = ... if effort_flag else []`. AI 가 큰 JSON 하나에서 `effort_flag` **한 칸**을
      빠뜨리자 등급 목록이 전부 버려졌고, 그 부분 결과가 내장 표를 이겨(폴백은 질의 자체가
      실패했을 때만) **실제로 지원되는 `--effort` 가 화면에서 사라졌다**
- [x] **B. 무지정 요청에 서버 alias 가 굳었다** — `model = data.get("model") or
      API_DEFAULT_MODEL` 폴백 뒤에 `requested_model=model` 이라, 프론트가 값을 싣지 않은
      요청도 `claude-haiku-4` 로 적재됐다. 러너는 모르는 이름이라 버리고 기본값으로 답한 뒤
      **"요청하신 모델 claude-haiku-4 는 쓸 수 없어…" 라는 거짓 고지**를 붙였다

**조치**:

- [x] `_settle_effort_axis` 신규 — 축이 비면 ① **그 축만 좁게 재질의** → ② 내장 표의 짝을
      **그 CLI 의 `--help` 로 실재 확인** 후 채택 → ③ 확인 못 하면 비움(지어내지 않는다).
      (플래그, 값 목록) **짝을 섞지 않는다** — 섞으면 그 CLI 가 받지 않는 조합이 만들어진다
- [x] `_CAPS_EFFORT_PROMPT` 신규 — 축 하나만 묻는 좁은 질의(1차에서 빠진 필드를 답한다)
- [x] `_cli_help_text` · `_help_mentions_flag` — 낱말 경계 검사(`--effort` ≠ `--effort-level`),
      **못 읽음(None) 과 없음(False) 을 구분**
- [x] `effort_probed` 표지 + `_caps_axis_unsettled` — `effort: null` 이 뭉갠 두 사실("물어봤는데
      없다" / "다룬 적 없다")을 가른다. 없으면 이 복구가 **기존 사용자에게 영영 실행되지 않는다**
- [x] `detect_runtimes` — 미확정 캐시는 **축만** 재확정(전체 재질의 아님) · `probed` 가 캐시를 이긴다
- [x] `requested_model=(model if model_explicit else None)` — 무지정을 무지정으로 넘긴다
- [x] 계정 기본값 `WebAccounts.BridgeDefaultModel`·`BridgeDefaultEffort`(멱등 ALTER) +
      `account_bridge_defaults`/`set_account_bridge_defaults` + 카탈로그가 **지금 신고된 목록과
      대조 후** 내려보냄 + `composer.js` 가 그 값을 시작점으로 사용
- [x] 반영된 지정도 답변에 밝힌다 — 미반영만 고지하면 침묵이 "지정대로 됐다" 와 "지정이
      전달되지 않았다" 두 가지를 뜻해 사용자가 구분할 수 없다
- [x] 회귀 25건(러너 12 · 카탈로그 5 · 요청 고정 8) · `make test` 전량 green · ruff clean
- [x] **실측**: `--help` 폴백(claude 5단계 · codex 3단계 · gemini 정확히 비움) · 재질의
      (claude 가 `--effort` + 5단계 정확히 응답) · 조립 결과
      `claude -p --strict-mcp-config --model opus --effort xhigh <질문>`
- [x] 기존 테스트 4건의 **텍스트 window 취약성** 교정(계약 유지, 읽는 방법만 AST·정확 앵커로)
- [ ] **POST-DEPLOY 시각검증** — 선택기 렌더는 JS 라 배포 후 실 브라우저에서 확인(PB-0008)

## 20260831T1133-live-steps-reasoning — 추론 구간 표시 + 진행 갱신 중단 해소

**요청 (2026-08-31)**: ① 「각 도구에 대한 수행시간은 확인되었지만, 추론을 진행하는 부분은
확인되지 않아 수정이 필요합니다」 ② 「답변 도중 실행단계의 진전이 갱신되지 않는 … 시간이
지날때마다 각 실행 단계의 갱신이 멈추는 이슈를 수정해주세요」.

계획·근본원인·AC 는 `TASK-20260831T113350-live-steps-reasoning.md`.

- [x] R1 — `_record_bridge_reasoning_gap`: 도구 단계 직후 추론 구간 activity 1건
- [x] R2-a — abort ↔ 회선 오류 분리(`"error"`). **일시 오류 1회가 감시를 영구 종료하던 주범**
- [x] R2-b — 예산을 횟수 → **시간 30분**(단조 시계). 횟수는 폭주 안전판으로 격하
- [x] R2-c — 표시 창을 최신 쪽으로 + `steps_omitted` 동반(무음 절단 제거, §16.7 G9-b)
- [x] 부수 — `_bridge_live_steps` PG 커넥션 close (tick 마다 새던 것)
- [x] 서버 변경감지를 `(len, omitted, 마지막 step_index)` 서명으로
- [x] 연속 오류 3회 시 폴링 강등 · 최소 재접속 주기
- [x] 화면 — 「단계 보기」 총 단계 수 · 생략 고지 1줄 · 「진행 중」 표기 · 생략 시 누적 미표시
- [x] pytest 신규 25건(서버 12 · 프런트 구조 13) + 기존 계약 2건 갱신 · 컨테이너 전량 green
- [x] node 하네스 `verify_bridge_live_step_progress.mjs` 18/18 — **뮤테이션 역검증 2종 포함**
- [x] **codex 적대 리뷰 2R** — P1 0건 수렴 · P2/P3 8건 중 6건 반영 · 2건 근거 기각
- [x] **PB-0008 POST-DEPLOY 시각검증** — 배포본 `74e2672c` 실 Windows 브라우저에서 완료.
      추론 구간 91초가 카드에 붙고(제보 ①), 절단 고지·총 단계 수·「진행 중」 표기 확인(제보 ②),
      저장 답변 경로 무회귀. 증적 `feature-0003 docs/test-runs.d/…-postdeploy.md`
- [ ] 실 러너 end-to-end 왕복(회선 절단 → 재접속 눈 관측)은 사용자 머신 AI CLI + 새 토큰이
      필요해 무인 완결 불가 — 함수 수준은 하네스 S1~S8 이 덮는다

#### POST-DEPLOY (배포본 5e806c6a)

- [x] **D4** `verify-completion --pre-commit` PASS
- [x] **D5** **PB-0008 실 Windows 브라우저 시각검증 PASS (4/4 축)** — 배포본 5e806c6a.
      증적 `feature-0003 docs/test-runs.d/TASK-20260831T100000-console-llm-parity-postdeploy.md`.
      라이브가 `runner_idle` 분기를 타 `no_connection` 과 실제로 갈린 것이 부수 실증
- [x] **D6** 배포 완료 — web-a/b + 워커 5종 = `5e806c6a` · 대화 스모크 PASS(전환 모드) ·
      surge 잔존 0 · **무중단 실측 `no upstreams available` = 0** · `/readyz` git_commit 일치
- [ ] **위임 e2e 미검증** — `wired` 전부 False 라 콘솔 작업이 적재되지 않는다. 위임이 실제로
      도는 화면은 C7~C10 배선 후에야 관측 가능(정직한 잔여)

### TASK-20260831T160000-console-job-wiring — 위임 배선을 실제로 잇는다 (사용자 결정)

**사용자 결정(AskUserQuestion 2026-08-31)**: 배선 단위 = **6종 한 번에** · 배치 귀속 =
**러너 opt-in 현행** · red-team = **별도 호출로 분리** · 모델 권한 = **미적용 배지 유지**.

**위험도: Major** — 신규 세션인증 엔드포인트 1 · 러너 계약 확장 · 4개 조작면의 서버 경로 분기.
인증·인가 규칙 변경 없음. 되돌리기 = 게이트 1개 + `wired` 플래그.

#### 이음매 하나로 좁힌 이유

관리 콘솔의 네 기능은 전부 **`messages` 를 조립한 뒤** LLM 을 부른다. 그 조립부가 이
feature 의 자산이다(스키마 grounding · 제품 바인딩 · 필드 제약). 그래서 위임은 조립 **뒤**,
호출 **앞** 한 지점에만 끼운다 — 프롬프트를 여기서 새로 쓰면 같은 기능이 경로에 따라 다르게
산출되고, 그때부터 한쪽은 반드시 낡는다(P0-P·P0-U 가 겪은 형태).

- [x] **C6** `GET /api/admin/ai-jobs/{task_id}` — 세션 인증 · 본인 적재분만 · 국면을 서버가
      한 단어로 정한다(`waiting|working|done|apply_failed|canceled`). 본문은 완료 시에만
- [x] **C7a** 위임 seam — 메타 단건·일괄(`admin_metadata`) + 프롬프트 3종(`_prompt_context`)
- [x] **C7b** 프론트 — `awaitDelegatedResult` 로 대기·국면 표시·결과 채우기
- [x] **C10** 러너 — `kind='job'` 이면 대화 프레이밍을 **씌우지 않고** 프롬프트를 그대로 쓴다.
      `features`/`agent_version` 신고 + `--batch` opt-in. 정본↔배포본 해시 일치
- [x] 위임 계약 회귀 12건 신설
- [ ] **C8 배치 2종** — `apply_external_*` 미구현이라 `wired: False` 유지(적재 자체가 거절됨)
- [ ] **C9 red-team 별도 호출** — 러너 2차 호출 + `submit_answer` review 동반 (미착수)
- [ ] **node_analysis** — 반영 경로 미구현이라 `wired: False` 유지

#### 발견한 결함 (전부 자체 발견)

| 지점 | 무엇이 틀렸나 |
|---|---|
| `metadata_suggest` 형식 | `json` 으로 잡았는데 **기존 프롬프트는 평문**을 요구한다 → 위임 지시가 조립부와 모순 |
| 위임 결과 해석 | 서버 봉투(`{target, suggestion}`)를 AI 가 만들 리 없다 → payload 로 화면이 재구성 |
| 내 회귀 가드 | **자기 주석 문자열**을 매칭해 거짓 실패(memory 의 "구조단언은 주석 제외" 그대로) |
| 기존 `test_ux_parity` | 같은 취약성 — 내 주석이 노출시켰다. 계약은 두고 판정 대상만 코드로 좁힘 |
| 테스트 더블 3종 | 넓어진 시그니처(`delegate_ctx`)를 못 받아 TypeError |
| 하트비트 계약 검사 | 본문 **전체 동치**로 잠가, 무관한 축이 늘자 깨졌다 → `runtimes` 축으로 좁힘 |

검증: 8개 unit 디렉토리 **6253 passed / 0 failed** · ruff clean · route 골든 260→261
(추가 1 · 제거 0).

#### POST-DEPLOY (배포본 d550db16)

- [x] **배포** — web·워커 전 서비스 `d550db16` · 대화 스모크 PASS · surge 0 ·
      **무중단 실측 `no upstreams available` = 0**
- [x] **PB-0008** — 신규 ESM 모듈 로드 · 조작면 게이트 무회귀 · 폴링 404 계약 ·
      `delegable_jobs` 판정. 증적 `feature-0003 docs/test-runs.d/…-console-job-wiring-postdeploy.md`
- [ ] **위임 왕복 e2e 미관측** — `console_jobs` 신고 러너가 사용자 머신에 있어야 관측 가능
      (AI 가 띄울 수 없음). 함수 수준은 회귀 18건이 덮는다

## 20260831T1700-live-steps-compact — 추론 구간 표시 밀도 + 실시간 누적

**요청 (2026-08-31, 직전 cycle 확인 후)**: ① 「추론 구간이 사이드 바 내부에서 비교적 큰 범위를
차지 … 최대한 단순한 형태로. 외곽선 및 배경 없이 한 줄로 출력되어도 문제없습니다. 목적 자체는
추론에 대한 소요시간을 확보하는 것」 ② 「최하단의 누적시간은 실시간으로 갱신 (단순히, 첫
호출시간과 현재시간의 차이로)」 ③ 「'▼ 쿼리결과' 리스트에서 추론 구간은 … 출력하지 않도록」.

**다의어 없음** — 세 항목 모두 사용자가 관측 가능한 값(한 줄 / 실시간 / 미출력)을 직접 지정했다.

- [x] ① 사이드 패널 내부 동작 = 한 줄(번호·문구·소요), 외곽선·배경·배지 없음 · CSS 로 nowrap+ellipsis
- [x] ② 최하단 누적 1초 티커 (`지금 − 첫 단계 기록 시각`) · 진행 중 경과도 같은 티커
- [x] ② 경계 — 생략된 창은 기준점이 "처음" 이 아니라 티커 미적용(틀린 값을 흘리지 않는다)
- [x] ③ 말풍선 목록에서 내부 동작 제외 + **여닫이 판정도 같은 집합**(빈 확장 방지)
- [x] 티커 수명 — 대상 없음/패널 닫힘/완료된 답변이면 돌지 않는다(정지 화면은 정지)
- [x] pytest 신규 12건 · 전량 green · node 하네스 18/18 무회귀
- [x] **codex 적대 리뷰 2R** — P1 0건 수렴, 1R P2 2·P3 1 전건 반영
- [x] **PB-0008 POST-DEPLOY 시각검증** — 배포본에서 표시면 5개 전건 확인. 내부 동작 행
      **22px**(카드 121px) · border/background 없음 · 누적 3.2초 간격 3회 증가 실측 ·
      말풍선 반복 문구 **0회**(제보 ×8 소멸) · 빈 확장 없음 · 완료 패널 정지.
      증적 `feature-0003 docs/test-runs.d/…-compact-postdeploy.md`
- [ ] 실 러너 end-to-end 왕복은 사용자 머신 AI CLI + 새 토큰이 필요해 무인 완결 불가

### TASK-20260831T190000-job-result-unwrap — 위임 결과에 각인 래퍼가 노출됐다 (라이브 제보)

**제보(2026-08-31)**: 최신 러너를 붙이고 용어사전 자동완성을 실행하자 폼 입력란에
`⟦UNTRUSTED-DATA⟧ (account=… task=… source=external_ai_answer)` + `[UNTRUSTED] Authored by
an external AI runtime…` 이 본문과 함께 통째로 들어갔다.

**위험도: Minor** (읽기 경로 1곳 + 비파괴 컬럼 1개. 데이터 손실·권한 변경 없음.)

#### 원인 — 저장본이 둘인데 화면이 잘못된 쪽을 읽었다

`WebAiTasks.Answer` 는 **각인본**이다: 감사 보존 + 지연 인젝션 방어(저장된 답변은 나중에
요약·검색 경로로 우리 LLM 컨텍스트에 되돌아올 수 있다). 대화 경로는 이것을 화면에 쓰지
않는다 — 원문을 대화에 따로 저장하고 화면은 그쪽을 읽는다. `_deliver_web_bridge_answer` 의
주석이 그 이유를 이미 적어 두고 있었다:

> "각인된 본문이 아니라 원문을 저장한다 … 두 소비처의 요구가 달라 저장본을 나눈다."

콘솔 작업 경로가 그 규율을 따라가지 못하고 `Answer` 를 그대로 폴링 응답에 실었다.

- [x] `WebAiTasks.JobResult` 비파괴 ADD — 화면이 읽을 **원문**
- [x] 제출 시점에 원문 보존(`store_console_job_result`). 실패해도 반영을 막지 않는다
- [x] 폴링이 원문을 준다. **이 수정 이전 행**은 각인본을 벗겨 폴백(`unwrap_external_answer`) —
      버리면 이미 AI 가 답한 작업을 다시 시켜야 한다
- [x] `session_guard.unwrap_external_answer` — `wrap_external_answer` 의 정확한 역함수.
      형식을 못 알아보면 **원본 그대로**(추측해 자르면 본문이 사라진다)
- [x] 회귀 7건 + **뮤턴트 KILL 실증**(각인본을 그대로 내보내는 원래 결함 → 2건 FAIL)

#### 잠근 것은 구조가 아니라 **불변식**

「화면으로 나가는 본문에 sentinel 이 없다」 하나다. 저장을 어떻게 나누든, 파싱을 하든 안 하든
그것만 지켜지면 재발하지 않는다. 정본이 있으면 파싱하지 않는다는 것도 함께 잠갔다 —
폴백에 의존하기 시작하면 "저장본을 나눈다" 는 규율이 파싱으로 대체된다.

### TASK-20260831T170000-model-tree — 없는 모델을 보여주던 폴백 + 플랫폼 그룹 트리 (P0-AF)

**요청** (2026-08-31, 앞 cycle 검수 후): "codex에 대한 모델이 목록에 구성되었지만 해당 모델은
실제 가용한 모델이 아닌 것으로 확인되었습니다 (gpt-5.1 등. 실제론 gpt-5.6 모델과 Sol, Terra,
Luna 등이 포함되어야 함). 이러한 이슈를 해결하면서 플랫폼 별 목록도 그룹화하여 트리를
구성해주세요. … 추가로, assistant 실제 응답 내부에는 모델 및 추론 등급을 포함할 필요는 없습니다."

**근본 원인**: 내장 표(`_RUNTIME_SPECS`)를 **모델 목록 폴백**으로 썼다. 그 표는 우리가 적어 둔
시점에 멈춰 있어서, probe 가 실패한 런타임은 낡은 이름이 그대로 화면에 올랐다 —
`gpt-5.1-codex`(폐기 세대)가 보인 경로다. 「목록의 출처는 연결된 AI」라는 계약을 **폴백이
뒷문으로 깨고 있었다**.

- [x] **내장 표의 모델 목록을 신고에서 제외** — 호출법(argv·플래그)만 폴백한다. 호출법은 잘
      변하지 않고, 없으면 실행 자체가 불가능하며, 값이 아니라 형태라 "틀린 선택지를 제시"
      하는 문제가 생기지 않는다. ollama 는 예외(HTTP **실조회**라 우리가 적은 값이 아니다)
- [x] 답한 적 없는 런타임은 **신고하지 않는다** — 빈 그룹도 남기지 않는다. "물어보지 못했다"
      와 "이것을 쓸 수 있다" 는 다른 사실이고, 후자로 말하면 사용자는 없는 모델을 고른다
- [x] **probe 재시도 1회** — 표 안 CLI 는 후보 호출 형태가 하나뿐이라 첫 실패가 곧 포기였다.
      모델 폴백을 없앤 지금 그 실패는 "그 런타임이 화면에서 통째로 사라짐" 을 뜻한다
      (실측: codex 는 같은 조건에서 성공·실패를 오간다)
- [x] 표에 남은 codex 모델을 **실측 세대로 갱신**(gpt-5.6-sol/terra/luna · 5.5 · 5.4 · 5.4-mini
      + 등급 5단계). 신고에 안 쓰이더라도 낡은 값이 코드에 남으면 다음 사람이 현재 목록으로
      읽는다 — 이번 결함이 정확히 그렇게 시작했다
- [x] **플랫폼별 그룹 트리** — 머리글(`composer-model-group-head`, `role=presentation`) + 하위
      항목. 그룹이 하나도 없는 카탈로그(서버 LLM 모드)는 종전 flat 유지. 트리에서는 배지를
      달지 않는다(머리글과 같은 말을 두 번 쓰지 않는다)
- [x] **답변 본문의 모델·등급 고지 제거** — 확인 수단은 선택기 라벨이면 충분하고, 그쪽이
      답변을 읽기 전에 보인다. **미반영 고지는 남긴다**(그건 화면 어디에도 없는 사실이다)
- [x] 회귀 7건 추가 + 기존 계약 5건 갱신 · `make test` 전량 green · ruff clean
- [x] **PB-0008 실 Windows 브라우저**(bind-mount 격리, 라이브 무접촉) — 두 그룹 트리 실측:
      `CLAUDE`(Opus·Sonnet·Haiku·**Fable**) · `CODEX`(GPT-5.6 Sol/Terra/Luna·5.5·5.4·Mini).
      `gpt-5.1-*` 소멸 확인

### TASK-20260831T183000-runner-version-sync — 「재설치했는데 그대로」 + 연결 직후 선택기 미표시 (P0-AG)

**요청** (2026-08-31, 3차 검수): ① "브리지 러너를 실행 및 연결시킨 후 테스트를 진행했지만
여전히 같은 모델 목록이 나타난다"(스크린샷: `GPT-5.1 Codex`) ② "'내 AI 연결하기' 과정이 완수된
후에는 모델, 추론 강도 요소가 출력되지 않고, 웹페이지 새로고침을 진행하고 나서야 나타난다".

**원인 ① — 러너 버전이 날짜 단위라 같은 날 배포를 구분하지 못했다**

라이브 확인: 살아 있는 러너(하트비트 21초 전)가 `gpt-5.1-codex` 를 신고하고 있었고, 러너 파일은
16:55 설치본 — **폴백 제거 이전 배포본**이었다. 그날 러너가 세 번 바뀌었는데 `AGENT_VERSION` 은
`2026.08.31` 하나라, 서버도 화면도 "지금 도는 러너가 배포본과 다르다" 를 말할 수 없었다.
사용자는 재설치하고도 옛 목록을 보며 그 이유를 어디서도 알 수 없었다.

**원인 ② — 카탈로그는 페이지 로드 때 한 번만 받는다**

연결이 성립하면 `onComposeGateChange` 가 컴포저를 다시 그리지만, 모델·추론 강도 목록의 출처인
`/api/api-vault/options` 는 **다시 부르지 않았다**. 그래서 잠금은 풀리는데 목록은 "러너 없음"
상태 그대로였고, 새로고침해야 비로소 보였다 — 연결을 끝냈는데 화면이 그 사실을 절반만 반영.

- [x] 러너가 **자기 파일 지문**(`_self_build`, sha256 12자)을 하트비트에 싣는다. 버전=호환성
      축, 지문=동일성 축 — 다른 질문에 답하므로 둘 다 신고한다
- [x] `WebOAuthTokens.RunnerBuild`(멱등 ALTER) + `set_runner_report` 저장 + `account_runner_build`
- [x] 서버가 **자기 배포본**(`static/agent/bridge_agent.py`) 지문을 계산(프로세스 1회 캐시)해
      대조 → 하트비트 응답 `runner_update.stale_build` · `connect_status.runner_stale`
- [x] 러너가 그 사실을 **세션당 한 번** 로그로 알린다(30초마다 반복하면 소음이라 무시된다)
- [x] 연결 칩에 `stale` 상태 신설 — "내 AI 업데이트 필요"(파랑 계열 · `↑`). 잠금 사유가
      아니라 **안내** 사유다(답변은 온다)
- [x] 게이트 변화 시 **카탈로그를 먼저 다시 받고** 그 뒤에 선택기를 그린다(순서가 반대면
      옛 목록으로 그린다)
- [x] 회귀 6건 추가 + 기존 계약 2건 갱신 · `make test` 전량 green · ruff clean
- [x] **PB-0008 실측**: ① 러너 미연결 → 칩 "연결 안 됨" · 모델 항목 숨김 ② **새로고침 없이**
      러너 기동 → 칩 "내 AI 대기 중" · 모델(`Opus`)·추론(`Low`) 항목 즉시 표시
      ③ 지문이 다른 러너 → 러너 로그 경고 + 칩 "내 AI 업데이트 필요" + 사유 툴팁

**자체 발견**: 판정 실패를 완전히 침묵시켰더니 왜 안 서는지 추적할 수 없었다(실측 중 실제로
겪었다) — 사용자에게는 조용하되 로그에는 남기도록 고쳤다.

#### 후속 (같은 cycle)

- [x] 침묵 처리를 `except` 블록 **구조**로 잠갔다 — 임시 디버그를 걷어내면서 앵커 문자열이
      사라져 계약 테스트가 깨졌다(문자열이 아니라 구조를 봐야 하는 자리였다)
- [x] 주석의 원인 서술 정정 — "커서 재사용 오류" 가 아니라 **상주 프로세스가 옛 모듈을 들고
      있던 것**이었고, 로그가 없어 그것을 *배제하는 데만* 여러 왕복이 들었다
- [x] **선재 실패 1건 해소** — `test_indicator_does_not_poll_when_unlocked` 가 main 에서도
      깨져 있었다(#1447 이 폴링 사유를 둘로 늘리며 계약 테스트 미갱신). 조건 문자열을 박제하던
      앵커를 **성질**로 바꿨다: "사유가 없으면 멎는다" + "켜기/끄기가 같은 값의 양면"

## 20260831T1758-details-scroll-panel — 상세를 자기 스크롤 패널로 + 페이징 시 내부 이동

**요청 (2026-08-31)**: 「'▼ 쿼리 결과'의 내용이 너무 길어질 경우 페이지 내 스크롤이 과도하게
길어지고 정작 중요한 쿼리데이터 결과셋이 밀려버리는 이슈 … 말풍선 내 별도의 스크롤 패널
내부에서만 렌더(최대 높이는 고정. 최소 높이는 제한 없음.) … 쿼리데이터 결과셋을 페이징 할
때 마다 해당 위치로 내부 패널의 스크롤이 이동」.

- [x] `.message-details-body` = 자기 스크롤 패널(최대 높이 고정 · 최소 높이 무제한 · 페이지로 새지 않음)
- [x] 패널 안쪽 결과 표를 패널보다 좁혀 중첩 스크롤 함정 차단(전역 인라인 표 상한은 불변)
- [x] 페이징 시 **자기 패널 scrollTop 만** 이동 — `scrollIntoView` 금지(조상 전부를 움직임)
- [x] 전환 경로를 `pageTo` 한 곳으로 합침(◀▶·←/→/Home/End 전부) · `focus({preventScroll})`
- [x] 늦게 확정되는 레이아웃 대비 reveal 3회 재적용
- [x] 진행 중 재구성 시 내부 스크롤 보존(옛 예약 취소 + 사용자 조작 우선)
- [x] pytest 신규 10건 · 전량 green · node 하네스 18/18 무회귀
- [x] **codex 적대 리뷰 2R** — P1 0건 수렴, 1R P2 3건 전건 반영
- [x] **PB-0008 POST-DEPLOY 시각검증** — 배포본 `47299f6a` 실측 7항목 전건 PASS:
      패널 622/782 자기 스크롤(`min-height: 0`) · 안쪽 표 378 < 622 · 페이징 시 패널 scrollTop
      0→375 이동하고 **대화 로그·문서 스크롤 0 불변** · navOffset 381→**6px**(계산된 위치,
      clamp 아님) · 키보드 동일 · 짧은 상세 81px 비스크롤.
      증적 `feature-0003 docs/test-runs.d/…-details-scroll-panel-postdeploy.md`
## TASK-20260901T110000-aiops-external-realign — 「AI 운영 현황」을 외부AI 운영축으로 전면 재편 (P0-AH)

**요청 (2026-09-01)**: "assistant 가 작동하는 구조가 변경됨에 따라 '관리 콘솔 > AI 운영 현황'
내부의 **모든 작동 사항들은 외부AI 작동에 정합한 구조로** 변경해주세요. 이제 **내부 AI 는
사용하지 않습니다**."

**사용자 결정 (2026-09-01, AskUserQuestion 4문)**:
1. 재편 범위 = **전면 재편** (탭 자체를 외부AI 운영축으로 다시 나눔)
2. 서버계정 LLM 과거 지표 = **「기록」 으로 격리** (보존하되 기본 진입에서 제외)
3. 신규 지표 = **도구 사용량 집계 · 브리지 작업 대기열/이력 · 러너 현황 상세** (3종 전부)
4. 미구현 안내(`외부 AI 5축 자가 검증`) = **자가 검증 제출까지 구현**

### 2.1 Implementation Plan

**위험도: Major** (§12.3 — 다중 파일·신규 API·러너 프로토콜 확장. 인증/인가 구조 무변경,
파괴적 데이터 없음, 마이그레이션은 additive expand-safe.)

#### 다의어 고지 — "외부AI 정합한 구조" 가 무엇으로 판정되는가 (§7.1 · §16.7 G1)

> **입력**: 서버 계정 LLM 이 차단(`AGENT_SERVER_LLM_ENABLED` 미설정)된 배포에서
> 관리자가 `관리 콘솔 > AI 운영 현황` 에 진입.
> **기대 화면**: 첫 화면(운영 현황)의 **모든 수치가 외부AI 축**이다 —
> 러너 N대 · 대기/처리중 M건 · 도구 호출 K회 · 자가 검증 통과율.
> 서버 토큰·비용·모델 도넛은 **첫 화면에 없다**(「기록」 탭에만 있고 '전환 이전' 라벨을 단다).
> **수치 1개**: 첫 화면 KPI 타일 중 `agent_runtime.llm_usage` 를 출처로 하는 것 = **0개**.

#### 재편 결과 (AS-IS → TO-BE)

| AS-IS 서브탭 | 출처 | TO-BE |
|---|---|---|
| LLM 사용량 (`usage`) | `llm_usage` | → **기록**(`archive`) 안 섹션 1, '전환 이전' 라벨 |
| 운영 현황 (`ops`) | 축5 + llm_usage KPI | → **운영 현황**(`ops`), 외부AI 축으로 재구성 |
| 추론 (`reasoning`) | 서버 `redteam_reviews` | → **기록** 안 섹션 2 (서버측 이력) + 현행 외부AI 자가검증은 `tasks`/`ops` 로 |
| 외부 AI 작업 (`exttasks`) | `WebAiTasks`(전체) | → **브리지 작업**(`tasks`) 로 승격·통합 |
| — | `tool_call_usage` | → **도구 사용량**(`tools`) 신설 |

#### 영향받는 파일 · symbol

| 경로 | symbol / 변경 |
|---|---|
| `unit/feature-0002-agent-core/alembic/versions/20260901_0057_redteam_review_source.py` | **신규** — `redteam_reviews.source`(server/external) · `task_id` 컬럼 additive |
| `shared/bridge_tasks.py` | `RUNNER_FEATURE_SELF_REVIEW` 신설 |
| `shared/self_review.py` | **신규** — 5축 계약 정본(`AXES` · `build_instruction()` · `sanitize()`). 러너는 서버가 내려준 지시문을 실행만 한다 |
| `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` | `claim_request` 응답에 `self_review` 지시 · `submit_answer` 가 `review` 수용 → `_record_external_review()` |
| `unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py` | `run_self_review()` · `handle_one` 이 초안 뒤 1회 추가 호출 · 신고 feature 에 `self_review` |
| `unit/feature-0003-agent-web-ui/src/oauth_store.py` | `list_live_runners()` — 계정별 러너 현황 상세 |
| `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py` | `_provider_axis` 차단 시 `na` 강등 · `_runner_roster` · `_self_review_stats` · 신규 `GET /api/admin/ai-ops/{tools,tasks,runners}` |
| `unit/feature-0003-agent-web-ui/src/routers/_console_llm.py` | `redteam-review` 항목 `delegated: True` + 문구 정정 |
| `unit/feature-0003-agent-web-ui/src/static/admin.html` | 서브탭 4종 재편 + `tasks`/`tools`/`archive` subpane |
| `unit/feature-0003-agent-web-ui/src/static/admin/{aiops,tasks,tools,archive}.js` | `tasks.js`·`tools.js` 신규, `aiops.js` 재구성, `exttasks.js` → `tasks.js` 흡수 |
| `unit/feature-0003-agent-web-ui/src/static/admin.js` | `initAiConsoleSubtabs` 키 재편 + deep-link alias 하위호환 |

#### 완료 판정 기준 (acceptance criteria)

- `AC-20260901T110000-aiops-external-realign-1`: 게이트 차단 배포의 `AI 운영 현황` 첫 화면 KPI 중 `llm_usage` 출처 타일 0개.
- `-2`: 서브탭이 `[운영 현황 · 브리지 작업 · 도구 사용량 · 기록]` 이고, 구 deep-link(`tab=usage|ai-ops|reasoning`)가 빈 pane 없이 착지한다.
- `-3`: `tool_call_usage` 집계가 도구별·대상별·판정별로 화면에 나온다(현행 콘솔 어디에도 없던 축).
- `-4`: 러너가 자가 검증 JSON 을 `submit_answer` 에 실으면 `redteam_reviews(source='external')` 에 저장되고 화면에 판정이 뜬다.
- `-5`: 자가 검증을 신고하지 않은 구 러너의 제출도 **거절되지 않는다**(하위호환 — 검증은 선택).
- `-6`: `_console_llm.py` 의 안내 문구가 실제 코드 경로와 일치한다(없는 기능을 있다고 말하지 않는다).

<!-- PLAN-APPROVED by user on 2026-09-01 (AskUserQuestion 4문 응답) -->

### 2.2 이행

- [x] **서브탭 전면 재편** `[운영 현황 · 브리지 작업 · 도구 사용량 · 기록]` — 기존 pane 은
      본문 무수정 이동, `exttasks.js` 는 `tasks.js` 로 흡수(삭제)
- [x] **첫 화면에서 `llm_usage` 출처 타일 제거** (AC-1) — 라이브 실측으로 0개 확인.
      차단 배포에서만 숨기고 게이트가 열린 배포는 종전 그대로(정상 운영 관제를 무르게 하지 않음)
- [x] **`LLM 제공자` 축 롤업 제외** — 쓰지 않는 provider 의 제한이 배너를 물들이던 것을 끊되
      `raw_state` 는 보존(되돌리는 날 되살아날 제한을 전환 전에 확인할 수 있어야 한다)
- [x] **도구 사용량 신설** (AC-3) — `tool_call_usage` 를 도구별·대상별·계정별·일별로.
      실측 7일 2,956 호출 · 10,184 행 · 1.4 MB
- [x] **브리지 작업 통합 원장** — 대화 질문 + 콘솔 위임 + 배치 + 외부 세션. 소유/수행 계정 분리.
      목록에 **답변 본문을 싣지 않는다**(각인 블록 유출 방지)
- [x] **러너 명부** — 네 상태(미연결·미수신·기능 미신고·지문 불일치)를 **조치가 다르므로** 가른다
- [x] **기록 탭 격리** (AC-2) — 3섹션 접힘 + 펼칠 때 조회. 과거 기록 온전 보존
- [x] **옛 deep-link 흡수** (AC-2) — `admin_console.py` 가 아직 보내는 `tab:"usage"` 를 제품
      경로(대시보드 위젯 「열기 →」)로 실측: `ai-console/archive` 착지, 빈 pane 아님
- [x] **외부 AI 자가 검증(5축) 실구현** (AC-4·AC-6) — 계약 정본 `shared/self_review.py` ·
      마이그 0057 · `claim_request` 지시 하달 · `submit_answer` 수용·저장 · 러너 수행·신고
- [x] **하위호환** (AC-5) — 검증 없는 제출을 거절하지 않는다. 구 러너 사용자의 답변이 막히지 않음
- [x] **안내 문구 정정** (AC-6) — 없는 기능을 있다고 말하던 문장을 구현 범위까지만 말하도록.
      `delegated_feature` 로 기능 단위 판정(`--no-self-review` 사용자에게 '적용 중' 으로 안 보이게)
- [x] `make test` 전량 green · ruff clean · migrate-lint expand-safe · ROUTEMAP 264 routes
- [x] 신규 회귀 **54건** + 기존 계약 3건 **축 정정**(등호→하한 이상 · 소스 문자열→행위)
- [x] **PB-0008 실 Windows 브라우저**(bind-mount 격리, 라이브 무접촉) 9항목 전건 PASS +
      자체 발견 1건(평문 렌더에 마크다운 강조 → 별표 노출) 수정·재확인

#### 자체 적대 검토 후속 (같은 cycle)

- [x] **[P1] 러너 명부가 조회 실패를 「러너 0대」로 단정하던 것** — `list_live_runners` 가
      실패와 실제 0대를 둘 다 빈 목록으로 돌려줘, 화면이 "아무도 처리하지 못합니다" 라는
      빨간 단정을 그렸다. 질의 하나의 실패가 장애 선언이 되는 형태이고 이 cycle 이 없애려던
      오독과 같다. **docstring 은 그 계약을 정확히 적어 두고 있었는데 코드가 지키지 않았다**
- [x] `RunnerBuild`(뒤늦게 추가된 컬럼) 부재는 **한 단계 내려가 나머지를 살린다** — 그것
      하나로 구 배포에서 명부가 통째로 비면 안 된다(`_query_activity` 컬럼 사다리와 동형)
- [x] 회귀 2건 + **직전 커밋 `33e00e0e` 에서 둘 다 FAIL 실증**(자기충족 아님)
- [x] `/codex review` 2회 시도 모두 판정 실패(330초 타임아웃 · 쿼터 소진) — **"통과" 로
      적지 않고** REVIEW.md 에 사유와 남는 위험을 기록

#### 잔여 (POST-DEPLOY)

- [ ] 자가 검증 **end-to-end** — 마이그 0057 적용 + **러너 갱신** 후에야 판정이 원장에 앉는다.
      현재 라이브 러너는 `2026.08.31` 이라 `self_review` 미신고(화면이 `미지원` 으로 정확히 표시)

## 20260901T1045-steps-result-split — 단계/결과셋 범위 분리 · 스크롤은 단계만

**요청 (2026-09-01)**: 「'▼ 쿼리 결과' 를 펼쳤을 때, 각 단계와 결과셋 범위를 분리해주세요.
스크롤 대상은 각 단계 뿐입니다.」

- [x] 상세 본문 스크롤러 해제(캡·overflow 제거)
- [x] `.step-detail-list` = **유일한 스크롤 대상**(최대 높이 고정 · 최소 높이 무제한 · contain)
- [x] 결과셋을 「쿼리 결과」 제목 블록으로 분리 — 단일/복수 SQL 이 같은 자리
- [x] 상세 안 결과 표를 좁히던 스코프 규칙 제거(결과셋에 온전한 높이)
- [x] 페이징 reveal 제거(영구 no-op) + 복원 조건을 주석·테스트에 명시
- [x] 진행 중 스크롤 보존 대상을 단계 목록으로 이동
- [x] 페이지 유계성을 **부분별 상한 3종** 회귀 테스트로 승격
- [x] pytest 전량 green · node 하네스 18/18 · codex 2R P1 0건 수렴
- [x] **PB-0008 POST-DEPLOY 시각검증** — 배포본 `65641296` 6항목 전건 PASS: 단계 목록만
      스크롤(300/631) · 상세 본문 **비스크롤**(1256/1256, overflow visible) · 결과표 전역
      상한 460 복원 · 페이징 시 **어떤 스크롤도 불변**(결과 위치 424px 고정) · 두 범위 제목
      렌더 · 상세 1295px = 부분 상한 합 안(유계).
      증적 `feature-0003 docs/test-runs.d/…-steps-result-split-postdeploy.md`

## 20260901T1100-win-ai-detect — 설치된 AI 를 찾지 못하던 결함 3겹

**요청 (2026-09-01)**: 「powershell 로 진행했지만 `FATAL: 쓸 수 있는 AI 를 찾지 못했습니다.
--ai 또는 --cmd 로 지정하세요.` 로 연결이 진행되지 않습니다. 추가로, 사용자에게 특정 명령어
및 옵션을 요구해서는 안됩니다 — 일반적인 사용자 입장에서는 해당 옵션의 의미도, 사용법도
이해하지 못합니다.」

실측으로 확인한 사실: 그 머신에는 `claude.exe`(Claude Code 2.1.70)가 **설치돼 있었고 실행도
됐다.** 못 찾은 것은 우리 쪽이다.

- [x] `_which` 크로스플랫폼화 — 윈도우 실행 확장자(`.exe`·`.com`. `.cmd`·`.bat` 는 codex
      P1 조치로 제외 — 배치 shim 은 `cmd.exe` 파싱을 거쳐 명령 주입 경로가 열린다)
- [x] 확장자 없는 sh shim 배제 — 찾아 놓고 못 부르는 상태(WinError 193) 차단
- [x] `_which_ai` — PATH 밖 **표준 설치 위치**(`~/.local\bin` · npm 전역 · Ollama)까지 탐색
- [x] 그 탐색을 **알려진 AI 이름 allowlist 로 한정** (홈 디렉토리 임의 이름 실행 차단)
- [x] `_resolve_exe` — 실행 choke-point 3곳에서 argv[0] 을 찾은 경로로 해석
- [x] `--check` 를 **연결 축 / AI 축** 으로 분리 — exit 4 신설(연결 정상 + AI 없음)
- [x] 사용자 대면 안내에서 `--ai`·`--cmd` 제거 → 「무엇이 필요한가 · 어디를 찾아봤는가」
- [x] `bridge_setup.ps1`·`.sh` 대칭 — 같은 탐색 범위 + exit 4 전용 안내
- [x] 배포본 동기화 3종(러너·ps1·sh) · BOM 보존 · PS 5.1 ParseErrors 0
- [x] 신규 회귀 26건 green · **뮤테이션 3종 역검증 전건 대응**
- [x] 기존 4건 교정(계약 유지 — `_which`→`_which_ai` 이름·부재 정의 확장)
- [x] 컨테이너 전수 `make test` rc=0 · ruff clean
- [x] **실 Windows 실측** — `Get-Command claude`=False 인 채 `_which_ai`가 찾아내고
      `claude --help` 7,436자 수신(=PATH 밖 실행 파일이 실제로 실행됨)
- [x] **codex 적대 리뷰 P1 1건 · P2 4건 전건 조치** — 배치 shim 명령 주입 차단(`.cmd`·`.bat`
      제외) · 확장자 포함 이름 회귀 · `--ai` 실존 확인(`pick_ai`) · 감지를 실제로 연결 뒤로 ·
      설치기↔러너 판정 대칭. 회귀 8건 추가(총 34건) + 실 Windows 재실측
- [x] **POST-DEPLOY 도달성 검증** — 배포본 `c0545cdd` · 무중단 실측(`no upstreams` 0건) ·
      정본 = 컨테이너(web-a/b) = **라이브 엣지** sha 동일 · **엣지 사본으로** 실 Windows
      end-to-end(`Get-Command claude`=False 인 채 감지 성공 + 실제 프로세스 기동) ·
      안내 문구 실 PowerShell 표시 확인(옵션 이름 0회) · 서버측 러너 배포본 교체·재기동
      (라이브 `--check` = 「연결 정상.」 → 「사용할 AI: claude」 → exit 0).
      증적 `docs/test-runs.d/TASK-20260901T110000-win-ai-detect-postdeploy.md`
- [ ] 사용자 실제 설치 왕복 1회 (토큰은 사용자가 웹에서 발급 — [연결 명령 복사] 재실행)

## 20260901T1150-answer-notice-server-seal — 모델·추론등급 고지를 **서버가** 걷어낸다

**요청 (2026-09-01)**: 「프로젝트 내 서비스에서, assistant가 답변을 전달할 때 "이 답변은
<LLM 플랫폼> 의 모델 <LLM 모델> · 추론등급 <깊이> 로 생성했습니다." 와 같은 텍스트가 답변에
포함되지 않도록 구성해주세요.」

**사용자 결정 (2026-09-01)**: 차단 지점 = **서버 집행 + 러너 사본 갱신** 둘 다 ·
미반영 고지(「…쓸 수 없어 기본 설정으로 답했습니다」)는 **유지** · 이미 저장된 과거 답변
7건은 **그대로 둔다**(확정 답변 불변).

**라이브 진단** (수정 전 실측):

| 관측 | 값 |
|---|---|
| 고지 제거 커밋 `82f3a160` (2026-08-31) | 배포본 `65641296` 에 **포함됨** (`merge-base --is-ancestor` 확인) |
| repo 정본 `bridge_agent.py` | 고지 문구 **0건** |
| 실행 중 러너 (PID 69063, `~/.mysql-ai-bridge/`, 08-31 16:55 설치) | 고지 문구 **2건** — md5 가 정본과 불일치 |
| `WebAiTasks` 고지 포함 답변 | 7건 (#71·#73·#75·#76·#77·#78·**#80 = 09-01 11:05 제출**) |

**근본 원인**: 러너는 **서버 배포 대상이 아니다** — 각 사용자 머신에 설치된 사본이므로 정본을
고치고 배포해도 그 머신이 다시 받아 가기 전까지 옛 코드가 돈다. 서버에는 이 고지를 걸러내는
방어가 없었고, 러너를 쓰지 않는 등록형 AI 는 애초에 그 코드를 지나지 않는다.

- [x] 서버 `submit_answer` 에 `_strip_model_notice` choke-point — 빈 답변 검사·task 적재·취소
      판정 **뒤** 1회 (저장본·대화 전달본·원장 바이트수·**대화 제목** 네 소비처가 같은 정리본)
- [x] 매칭은 **문장 골격 전체** — 어휘 조각으로 보면 `모델링`·`논리 모델` 에 부분일치하고
      미반영 사실을 자기 말로 쓴 문장까지 삼킨다(지키려던 계약이 같은 정규식에서 깨진다)
- [x] 탐색 범위 = 답변 **말미 8줄**, **펜스를 세지 않는다** — 닫히지 않은 펜스로 봉인이
      뚫리거나 중첩 펜스 안이 지워지지 않는다. 본문 중간의 예시 인용은 범위 밖
- [x] 비용 상한(줄 길이 가드) + 본문이 비면 정리 안 함(빈 답변 400 이 task 를 박제하지 않게)
- [x] 계약 테스트 **36건** (`test_answer_model_notice_seal.py`) — 헬퍼 정확성 + **진입점 실구동**
- [x] **적대 리뷰(subagent) P1 4건 · P2 6건 → P1 전건 + P2 5건 반영** — 초안의 펜스 상태
      기계와 어휘 정규식을 둘 다 폐기시킨 지적
- [x] 뮤테이션 **7종 전건 KILL**
- [x] 러너 정본이 고지를 **다시 만들지 않는지** 회귀 잠금 (파일 전체 + 2사본 바이트 동일성)
- [x] 구버전 러너 설치 사본 갱신 + 재기동 — 배포본과 `md5 4c8851ca…` 일치, 새 토큰으로
      `--check` 통과 후 상주 기동(PID 1147300). 임시 토큰 파일 폐기
- [x] **라이브 실측 (배포본 `7fb2dca4`)** — 4축 전건 PASS: 배포 도달(엣지 무중단 0건) ·
      배포본 함수 직접 구동 5케이스 · **고지가 붙은 답변을 REST 로 직접 제출 → 저장본에서
      걷힘**(미반영 고지는 보존) · **실 브리지 왕복 #86**(모델 `sonnet`·등급 `high` 명시
      지정에도 고지 없음 / 배포 전 #83 대조군은 고지 있음).
      증적 `docs/test-runs.d/TASK-20260901T115000-answer-notice-server-seal-postdeploy.md`

---

## TASK-20260901T140000-orphan-claim-reclaim — 러너가 죽으면 질문이 30분 사라진다 (P0-AI)

**사용자 제보 (2026-09-01)**: 「"쿼리 리뷰를 진행해주세요. 라이브 기준 데이터라, QA
데이터소스에 정합하지 않을 수 있습니다. 제재 대상자" 대화에서 **추론 과정이 너무
길어지는** 이슈가 확인되었습니다.」

**라이브 진단** (대화 `20260901030637-95dc8844` · task `t_GliHOXeBognfeeOI`, claude·sonnet·xhigh):

| 시각 | 사실 | 출처 |
|---|---|---|
| 12:07:26 | 개인 AI 에 전달 | `bridge.log` |
| 12:07:46–12:13:20 | 도구 **14회** 정상 진행(354초) | `agent_runtime.steps` 29행 |
| 12:13~16 | 러너 **재설치·재기동** (`bridge_agent.py` mtime 12:13 · `config.json` 12:14 · 「대기 시작」 12:13:48·12:14:24 · 프로세스 12:16:09) → 자식 `claude` 사망 | 파일 mtime · 로그 · `ps` |
| 12:13:20→12:43:20 | **무진행 30분**. task 는 `open` + `ClaimedBy=10` + `ClaimedAt=12:13:20` 이라 `CLAIMABLE_SQL` 을 통과하지 못해 **재기동한 자기 러너에게도 안 보임** | `WebAiTasks` |
| 12:43:21 | lease 만료 → 재배달 → **조사를 처음부터 재실행** | `bridge.log` |
| 12:47:47 | 「토큰이 필요합니다」로 러너 종료 → **또 고아** | `bridge.log` |
| 13:34:23 | 사용자가 포기하고 재전송(supersede) → 새 task `t_DkWkdi0DNgdq552j` → **80초 만에 제출** | `WebAiTasks` |
| (13:34·13:40 제출 내용) | ⚠ **리뷰가 아니라 거부** — 러너의 AI 가 브리지 프롬프트를 프롬프트 인젝션으로 판정. **별건 결함**(아래 참조) | PB-0008 화면 · `WebAiTasks.Answer` |

**사용자 대기 87분.** 그 87분 중 60분 이상은 **아무도 그 질문을 볼 수 없던 시간**이다 — 길어진
것은 모델의 추론이 아니다. (87분을 끝낸 13:34 제출이 낸 것은 리뷰가 아니라 거부 답변이었다.
그것은 이 cycle 이 고치는 결함과 별개이며 아래 「PB-0008 에서 드러난 별건」에 기록한다.)

**근본 원인 두 겹**

1. **회수 경로 부재** — lease 는 도구 호출마다 갱신되므로(`_renew_claim_lease`) 러너
   프로세스가 사라지는 순간 그 갱신값이 **최대 30분짜리 사각지대**가 된다. 점유는 토큰의
   `client_id` 로만 표시돼 있어 「어느 프로세스가 들고 있나」를 아무도 답하지 못했고,
   그래서 재기동한 **같은 러너조차** 자기가 두고 온 작업을 되찾지 못했다.
2. **표시가 두 사실을 합쳤다** — `_bridge_phase` 는 점유돼 있기만 하면 `working` 이었다.
   「가져갔다」와 「진행하고 있다」가 한 국면으로 뭉개져, 화면은 그 30분을 「조사·작성
   중입니다」로 그렸다. 사용자에게는 그것이 **끝없이 길어지는 추론**이다.

**부차 관측** (수정 대상 아님, 기록만): 최근 8건이 전부 `xhigh` — 추론 등급이 계정 기본값
으로 고착돼 질문 난이도와 무관하게 적용된다(2026-08-31 사용자 결정 축이라 임의 변경 안 함).
정상 완료 건의 마지막 도구 이후 답변 작성 구간은 최대 621초(실측 15건).

### 이행

- [x] **러너 인스턴스 축** — 프로세스마다 `runner_instance`(hex 12자) 발급,
      `~/.mysql-ai-bridge/config.json` 에 보존. `claim_request` 가 그 값을
      `ClaimedClient = <client_id>#<instance>` 로 새긴다(스키마 변경 없음, VARCHAR(64) 재사용).
- [x] **사망 신고** — 하트비트 `released_instances`. 기동 첫 신호에 **직전 인스턴스**를,
      종료 시 **자기 자신**을 싣는다. 서버는 그 인스턴스가 점유한 `open`·미제출 작업만
      놓아준다(`ClaimedBy=NULL`). 30분 → **다음 하트비트까지(≤30초)**.
- [x] 신고는 **닿을 때까지 재시도** — 첫 신호가 배포 교대·순단에 걸리면 회수가 통째로
      유실된다. 서버 쪽은 멱등(이미 놓은 것은 0행)이라 반복 비용이 없다.
- [x] **종료 세 갈래를 한 출구로** — `atexit` + `SIGTERM`→`SystemExit`. 설치 스크립트가 옛
      러너를 정리할 때 쓰는 것이 정확히 그 시그널이다(재설치가 이번 결함의 발단).
      `SIGKILL`·전원 차단은 **다음 기동의 사망 신고**가 덮는다(두 경로는 대체 아닌 보완).
- [x] 경계는 `ClaimedBy = account_id` — 질문 소유 계정이 아니라 **점유자**. 배치 작업은
      소유 계정이 없어(`AccountId=0`) `AccountId` 로 닫으면 회수에서 통째로 빠진다.
- [x] **무진행 국면 `stalled`** — `ClaimedAt`(= 마지막 진행 시각)이 `BRIDGE_NO_PROGRESS_SEC`
      (900초)보다 오래되면 `working` 이 아니라 `stalled`. 임계는 정상 무도구 구간 최대치
      (621초)보다 크고 lease(1800초)보다 작다 — 사용자는 **회수가 일어나기 전에** 알게 된다.
      판정 불가(`None`)면 `working` 유지(관측 못 한 것을 「멈췄다」로 단정하지 않는다).
- [x] 대기 말풍선 본문을 **1회** 무진행 고지로 교체(`_mark_bridge_no_progress`) — UPDATE 조건에
      「아직 진행 중 문구일 것」을 걸어 매 tick no-op. 고지는 사용자가 **할 수 있는 일**로 끝난다
      (러너 확인 → 다시 켜면 자동 재배달 → 원치 않으면 중단).
- [x] 판정·후행을 **한 곳**에 — 폴링(`bridge_status`)과 스트리밍(`_bridge_stream_snapshot`)이
      같은 `_bridge_phase` + 같은 `_announce_no_progress` 를 탄다(전송 방식이 화면을 바꾸지 않게).
- [x] 취소 통보의 점유자 대조를 **앞자리 비교**로(`SUBSTRING_INDEX(ClaimedClient,'#',1)`) —
      전량 일치로 두면 인스턴스를 신고하는 러너의 취소가 한 건도 매칭되지 않아, 취소를 눌러도
      러너가 계속 태우는 종전 결함이 되돌아온다. (`LIKE` 가 아닌 이유: `client_id` 에 `_`·`%`)
- [x] 계약 테스트 **21건** (`test_orphan_claim_reclaim.py`) — 합성·해석, 회수 SQL 경계
      (점유자·open·미제출·상태 불변), 빈 신고 no-op, 국면 전이 실구동, 임계 상·하한, 배선
- [x] 테스트 더블 서명 경화 — `heartbeat(self, timeout=…)` 더블이 실물 서명 확장에 죽어
      **다른 파일의 실패**로 나타났다(`*args/**kwargs` 로 교체)
- [x] **라이브 실측 (배포본 `9c04b52c`)** — 코드 도달 6축 · 배포본 함수 직접 구동 ·
      국면표 6케이스 **ALL PASS** · **실 MySQL 에서 점유자 술어 4형식 검증**(인스턴스 접미·
      구 러너·다른 세션·NULL → P1-1/P1-2 회귀 차단선) · 자산 스탬프 `da49561ff923`→`cd84170acd28` ·
      엣지 무중단 0건. **미검증 2건 명시**(러너 설치본이 구버전이라 회수 end-to-end 불가 ·
      `stalled` 말풍선은 라이브 조건 부재 + 병렬 세션 6곳 동시 작업으로 제품 경로 주입 회피).
      증적 `docs/test-runs.d/TASK-20260901T140000-orphan-claim-reclaim-postdeploy.md`
- [x] 별건(인젝션 오판)은 `ai/claude/feature-0043-bridge-injection-falsepositive` 가 이미 담당 —
      중복 cycle 열지 않음
## 20260901T1400-injection-false-positive — 브리지 프롬프트가 인젝션으로 오판되는 문제

**요청 (2026-09-01)**: 「assistant가 프롬프트 인젝션 시도로 처리하여 요청사항을 자가중단하는
현상이 확인되었습니다. 보안적으로 안정적이지만, 요구사항이 충족되지 않은 상태라 개선이
필요합니다」.

계획·근본원인·라이브 근거·AC 는 `TASK-20260901T140000-injection-false-positive.md`.
**위험도 Major** — 신뢰경계 표시(각인)의 의미 변경. 사용자 승인 2026-09-01(범위 "1+2").

<!-- PLAN-APPROVED by mckim on 2026-09-01 -->

- [x] S1~S4 — `session_guard`: principal 요청 구획 · 대화이력 구획 · 위조 제거 확대 ·
      인젝션-거부 탐지(양방향 오탐 계약)
- [x] S5~S8 — `ai_tools`: claim_request 각인 교체 · 거부턴 맥락 제외 · 출처 preamble ·
      submit_answer 탐지·안내
- [x] R1~R4 — `bridge_agent`: 운영자 지침을 `--append-system-prompt` 실채널로 · 토큰을
      `BRIDGE_TOKEN` 환경변수로 · 자식 CLI 중립 cwd · 역할변경 문형 제거
- [x] 단위 테스트 + 전량 pytest rc=0 (신규 35건 · 뮤테이션 3종 KILL) · ruff clean
- [x] 자체 적대 검토 P1 1건 적발·수정(새 sentinel 위조가 들어오는 쪽 판정에서 누락)
      — 독립 패널은 codex 사용량 한도로 미수행(`REV-20260901T150000 [SKIPPED:tool-quota:codex]`)
- [x] 배포 `afcd1a42` (scope=all · 엣지 무중단 0건) + **POST-DEPLOY 실측 서버축 6/6 ·
      러너 배포 도달 4/4** — ⭐ 오염됐던 그 대화(`20260901030637-95dc8844`)의 맥락 조립에서
      거부턴 2건이 실제로 빠지고 제외 고지가 실린다(고착 해제 실증)
- [ ] 사용자 왕복 1건 — 같은 대화 재질문이 거부문이 아닌 실제 리뷰인지(러너를 띄운 본인만 가능).
      러너측 효과는 화면 「연결 준비」 재실행 후 발효
## 20260901T1600-cli-failure-reason — 연결된 AI 의 실패 사유가 사용자에게 도달하지 않는다

**요청 (2026-09-01)**: 「프로젝트 내 서비스의 assistant 가 동작하지 않는 부분이 확인되어 수정이
필요합니다. 대화 제목은 "253서버 프리미엄 포인트 누적·사용로그 집계" 입니다」
(`/_dqa:conversation_audit` 대화 한정).

근본원인·라이브 근거·AC 는 `TASK-20260901T160000-cli-failure-reason.md`.
**위험도 Major** — 사용자 대면 실패 피드백 경로(단, 더하기만 하는 변경·성공 경로 불변).

- [x] 라이브 진단 — 전사 4턴 + `WebAiTasks` 2건(claim→submit 4초·8초) + 러너 로그 무기록 +
      **동일 명령 재현**(exit 1, 사유는 **stdout**, stderr 는 stdin 안내뿐)
- [x] `describe_cli_failure` — stderr 우선 · 잡음 제외 · stdout 폴백 · 없으면 「알 수 없습니다」
      명시(빈 콜론 금지)
- [x] `_FAILURE_HINTS` — 증상 어휘 기반 회복 안내(한도·미로그인·미지원 옵션·미설치),
      모르는 실패엔 안내 없음
- [x] `_redact_secrets` + 400자 상한 — 사유를 살리는 일이 유출·범람이 되지 않게
- [x] 러너 로그에 실패 첫 줄 기록(종전 무기록)
- [x] 배포본 사본 동기화 + 해시 잠금 테스트 PASS
- [x] 신규 11건 · **뮤테이션 3종 KILL** · ruff clean · 인접 feature 회귀 0(기준선 동일)
- [x] 인라인 적대 검토 3렌즈 — P1 1건(`401` 경계 없는 매칭) 적발·수정
      (`REV-20260901T160000`)
- [x] 배포 `4521a7e1` (scope=all · 7서비스 SHA 일치 · 엣지 무중단 0건 · surge 잔존 0 ·
      대화 스모크 PASS) + **POST-DEPLOY 실물 실증** — 서빙되는 러너 사본(md5 = 배포 SHA 블롭)을
      그대로 import 해 라이브 실측 입력을 넣으니 **사유 + 다음 행동을 갖춘 문장이 생성**된다
      (종전: 콜론 뒤 빈 문장)
- [ ] 사용자 왕복 1건 — 그 사용자의 **다음 실패**에서 사유가 실제로 보이는지.
      러너는 사용자 머신 파일이라 화면 「연결 준비」 재실행으로 갱신돼야 발효
## 20260901T1630-runner-log-structure — 러너 로그를 감사·에러핸들링 가능한 구조로

**요청 (2026-09-01)**: 「'내 AI 연결하기' 를 통해 러너가 실행될 때 기록하는 로그에서 보다
명확한 정보 기록을 위한 구조가 필요합니다. 충분한 감사 및 에러 핸들링이 가능하도록,
상세 정보를 포함할 수 있도록 구성해주세요.」

**위험도 Major** — 러너 전 경로의 관측 계층 교체(비파괴 가산). 사용자 머신에 새 파일 2종을
남기므로 이 파일의 **보안 계약 표**도 함께 갱신했다(계약과 사실이 갈리면 그 문서 전체가 죽는다).

### 무엇이 없었나 (착수 근거 — 전부 현 코드 실측)

- 형식이 `[bridge <시각>] <한국어 문장>` 하나뿐 → **심각도 없음**(참고와 제출 실패가 같은 모양,
  `grep` 로 오류만 볼 수 없다), **사건 코드 없음**(문장 매칭이 유일한 판별 수단이라 문구를
  다듬는 순간 조사 방법이 깨진다).
- `task_id` 는 있는 줄·없는 줄이 섞여 있고 **러너 인스턴스는 어디에도 없다** — 87분 고아 사고
  (`TASK-20260901T140000`)의 시간축을 파일 mtime·DB 하트비트로 짜맞춰야 했던 이유.
- **소요 시간 없음** — 두 줄의 시각 차로 구해야 하는데 동시 처리면 인터리브되어 그 뺄셈도 틀린다.
- `except Exception as e: _log(f"…: {e}")` **18곳** — 예외 형과 스택이 통째로 버려진다.
  `FileNotFoundError`(미설치)와 `PermissionError`(권한)가 같은 문장이 된다.
- `Api._post` 는 실패를 **반환만** 하고 로그를 남기지 않았다 — 호출측이 남기는 곳도, 안 남기는
  곳도 있어 서버 왕복 실패에 구멍이 있었다.
- 자식 AI CLI 의 stderr 는 답변에 실리는 **400자만** 남고 원문은 사라졌다(원인은 대개 뒷부분).
- **Windows 러너는 로그가 아예 없었다** — 설치본이 `Start-Process -WindowStyle Hidden` 로
  띄우며 stderr 를 아무 데도 잇지 않는다. 그 머신의 사고는 증거가 0이었다.
- 회전 없음 — 상주 프로세스가 몇 달을 도는데 `bridge.log` 상한이 없었다.

### 한 일

- [x] **두 sink** — 사람 줄(stderr·`bridge.log`)과 사건 원장(`bridge.events.jsonl`, 한 줄 = 한
      사건). 안정 계약은 **문장이 아니라 `ev` 코드와 필드 이름**이다(`_EV_*` 상수로 선언).
- [x] **상관관계 키** — 모든 원장 줄에 `ts`(오프셋 포함)·`lvl`·`ev`·`seq`·`run`(러너 인스턴스)·
      `pid`. `task` 는 질문 한 건의 일생을 묶고, 그 값은 서버 `BridgeTasks.TaskId`·웹 화면과
      같아 **3자 대조**가 된다.
- [x] **소요 계측을 한 자리에** — `Api._post`(모든 서버 왕복)·`_run_cli_cancelable`(AI 호출)·
      `handle_one`(전달→제출 전체). 호출부마다 재면 빠지는 곳이 생기고 그곳이 하필 느려진다.
- [x] **예외를 잃지 않는다** — `_log_exc` 가 형·표현을 두 sink 에, 스택(마지막 12프레임)을
      원장에. 자식 CLI 실패는 exit code + stderr 끝 2KB 를 원장에 남긴다.
- [x] **토큰 마스킹** — 값 등록(`register_secret`, `Api.__init__` 에서 즉시) + 형태 패턴 3종.
      이 파일은 사용자가 우리에게 **붙여 보내는** 물건이라 새면 그대로 유출이다.
- [x] **Windows 로그 복구** — 러너가 자기 로그 파일을 직접 쓴다. POSIX 설치본은 셸이 stderr 를
      `bridge.log` 로 잇고 있으므로 **inode 비교로 같은 파일이면 쓰지 않는다**(이중 기록 방지).
      설정으로 가르지 않는 이유: 대부분 틀린 쪽을 고르고, 틀린 것을 아는 시점이 사고 조사 중이다.
- [x] **회전** — 원장은 러너가(8MiB·3세대), `bridge.log` 는 **설치 스크립트가 기동 직전에**.
      후자를 러너가 못 하는 이유: 자기 stderr fd 가 옛 inode 를 붙들고 있어 옮겨도 옛 파일에 쓴다.
- [x] **종료 요약** — `run.stop` 한 줄에 uptime·처리·실패·오류 수 + 사건별 집계표.
      집계는 `log_event` 가 중앙에서 세므로 새 사건이 생겨도 요약에서 빠지지 않는다.
      종료 경로 셋(반환·Ctrl+C·SIGTERM→atexit)에 빗장을 걸어 **한 번만** 남긴다.
- [x] **하위호환** — `_log("문장")` 위치인자 계약 유지. 호출부 80여 곳을 건드리지 않았다
      (같은 파일을 동시 편집 중인 병렬 세션 3곳과의 충돌면을 좁히려는 의도이기도 하다).
- [x] 계약 테스트 **18건** (`test_bridge_log_structure.py`) — 두 sink·상관관계 키·오프셋·
      순번 단조·예외 형/스택·요약·빗장·토큰 2종·본문 미기록·하위호환·이중기록 방지(실
      서브프로세스)·Windows 경로·끄기·회전·권한 0600·사건 코드 상수·task 키 공유
- [x] 기존 테스트 3건 정합 — `test_bridge_agent_sync`(stdlib 허용목록에 `traceback`),
      `test_wsl_scheme_handler`(정규식으로 `_log` 를 오려 exec 하던 방식 → 모듈째 실행.
      검사하려던 성질(시각)과 무관한 이유로 깨지는 검사였다),
      `test_bridge_interrupt_stream`(`"WARN"` 글자 → 심각도 성질 + 사건 코드)
- [x] 러너 스위트 **1045 passed / 1 skipped** · ruff clean · `bash -n` · 배포본 동기화
## 20260901T1600-connect-os-default — 1단계 기본 OS 탭을 「마지막으로 연결됐던 OS」로

**요청 (2026-09-01)**: 「'내 AI 연결하기' 의 1단계에서 명령문이 처음 선택된 os가, 실행중인
os가 아니라 마지막으로 연결되었던 os를 기준으로 선택되도록 구성해주세요. 현재는 주로
linux(wsl) 내 명령문을 사용하고 있지만 windows가 항상 기본적으로 선택된 상태입니다. 이후
powershell 테스트를 진행하며 해당 명령문으로 다시 등록했을 때 windows로 선택되어야 합니다」.

**근본 원인**: 기본 탭을 `navigator.platform` 이 정했다 — 그것은 **브라우저가 도는 OS** 이고
러너는 다른 곳에서 돈다. WSL 사용자는 Windows 브라우저로 화면을 보므로 판정이 구조적으로 틀렸다
(운이 아니라 매번).

**위험도: Minor** (§12.3 — 비파괴적 컬럼 추가 + 화면 기본값. 인증·인가·데이터 파괴 없음.
실패 경로는 전부 「종전 동작으로 복귀」다). §7.1 계획 = 본 절.

**완료 판정 기준 (다의어 고지 §7.1)**: WSL 러너가 붙어 있는 계정으로 `/ai/connect` 를 열면
1단계 기본 탭이 **macOS·Linux** 이고 명령이 `curl … bridge_setup.sh` 로 보인다 (종전에는
Windows 탭 + PowerShell 명령). 같은 계정이 PowerShell 명령으로 다시 등록하면 그 다음 열람에서
**Windows** 가 먼저 뽑힌다.

- [x] 러너: `_self_os()` (= `os.name`) 신고를 하트비트에 추가 · 배포 사본 동기화
- [x] 서버: `WebOAuthTokens.RunnerOs` + `WebAccounts.BridgeLastOs` 컬럼(fast-path 멱등 ALTER) · `normalize_bridge_os`/
      `account_bridge_os`/`set_account_bridge_os` · 하트비트 기록(실패는 삼킨다)
- [x] API: `/api/ai/connect/status` · `/api/ai/connect/token` 응답에 `last_os`
- [x] 화면: 단독 페이지·대화 모달 둘 다 서버 값 우선 + 추측 폴백 + 사용자 선택 고정
- [x] 계약 테스트 28건 (`test_connect_os_default.py`) — 닫힌 집합 · 「모른다」가 안 지운다 ·
      연결-사건 가드 · 토큰 생존 술어 · 신선도 술어 부재 · 배선 · 두 화면 · 응답 경합
- [x] 적대 리뷰 (codex, effort=high) — **P1 3건 · P2 2건 전건 확인·수정·회귀 잠금**
      (`REV-20260901T163000`): 기존 DB 컬럼 미생성 · 두 러너 값 진동 · 모달 늦은 발급 응답 ·
      단독 페이지 응답 순서 · 폐기 토큰의 계정 쓰기
- [x] PB-0008 PRE-DEPLOY baseline — 라이브에서 결함 재현(Windows 탭 + PowerShell 명령 고정,
      `last_os` 키 부재). 증적 `test-runs.d/…-pb0008.md`
- [x] 라이브 재배포 `b50513e0` (scope=all · 엣지 무중단 0건 · 대화 스모크 PASS)
- [x] **PB-0008 POST-DEPLOY 양방향 실측** — ① `last_os=""` 면 종전 추측 폴백(회귀 없음)
      ② WSL 러너 연결 → `posix` → 두 화면 모두 **macOS·Linux** 를 먼저(브라우저는 `Win32`)
      ③ 실 Windows 파이썬으로 PowerShell 재등록 → `windows` → 화면도 Windows.
      ②가 곧 `BridgeLastOs` 컬럼이 **기존 운영 DB 에 실제로 생겼다**는 증거(codex P1-1 라이브 성립).
      증적 `docs/test-runs.d/TASK-20260901T160000-connect-os-default-postdeploy.md`
- [ ] 사용자 확인 1건 — 본인 계정·본인 러너에서 같은 동작(러너는 화면 「연결 준비」 재실행으로 갱신)
- [ ] PB-0008 POST-DEPLOY — 러너를 실제로 붙여 `posix` 신고 → 화면이 macOS·Linux 를 먼저
- [ ] 라이브 재배포 + POST-DEPLOY 실측

## 20260901T1700-runner-log-atexit-order — 종료 요약이 마지막 줄이 아니었다

**위험도 Minor** (한 줄 순서 + 회귀 테스트 2건). 직전 cycle(`TASK-20260901T163000`)이 심은
결함을 **그 cycle 의 POST-DEPLOY 라이브 실측이 잡았다**.

배포본 `a17b8f5ea7f6` 를 내려받아 `--check` 로 돌린 종료 로그가 `run.stop`(seq 4) →
`api.fail`(seq 5) 순이었다. `atexit` 는 나중에 등록한 것을 먼저 부르는데 요약을 자기 점유
해제 **뒤에** 등록해 둔 탓이다(주석에는 정반대로 적혀 있었다 — 근거 없이 쓴 문장이 코드를
검토에서 지켜 준 형태). 그러면 종료 요약의 두 쓸모가 동시에 죽는다: ① 해제 결과를 집계하지
못하고 ② 「여기서 끝났다」의 표지가 못 된다(뒤에 줄이 더 있으니 로그가 잘린 것과 구분되지 않음).

- [x] 등록 순서 교체 — 요약을 **먼저** 등록해 역순에서 **마지막에** 실행되게
- [x] 회귀 2건: 실 프로세스 종료로 마지막 줄 단정 + 소스 등록 순서 고정
- [x] ⭐ 첫 실동작 테스트가 **vacuous** 했던 것을 스스로 잡아 고침 — 스크립트가 두 핸들러를
      직접 `atexit.register` 해서 «제품의 등록 순서»가 아니라 «테스트 자신의 순서»를 검사했고,
      구코드에서도 통과했다. `_arm_exit_release` 를 거치도록 고친 뒤 **구코드에서 FAIL 재현**
      (`['run.stop','exit.release','log']`) → 신코드 PASS 를 양방향 확인
## 20260901T1730-stale-runner-yield — 낡은 러너가 최신 러너의 질문을 가로챈다 (사용자 재보고)

**요청 (2026-09-01)**: 「웹페이지 새로고침, 연결 준비를 통해 러너를 다시 연결한 후 요청을
보냈지만 같은 이슈가 확인되어 조치가 필요합니다」 + 「오래된 러너 측에서 … 다른 신규 러너에
연결되는 부분이 확인된다면 오래된 러너는 프로세스를 종료 처리 … 다만 계정이 다를 경우는 예외」.

근본원인·설계·AC 는 `TASK-20260901T173000-stale-runner-yield.md`.
**위험도 Major** — 점유 집행 경로(판정이 상대라 단독 러너 동작은 불변).

<!-- PLAN-APPROVED by mckim on 2026-09-01 (러너 자가 종료 · 계정 예외 명시) -->

- [x] 라이브 진단 — 같은 계정에 러너 2개(배포본 `d0ac1263d454` vs 옛 `0a4ba732366c`),
      옛 러너가 17:20:03 질문을 먼저 집어 옛 형식으로 답한 것을 `WebOAuthTokens` + 러너 로그로 확정
- [x] 즉시 조치 — 옛 러너 프로세스 SIGTERM 정상 종료(라이브 복구)
- [x] `stale_runner_must_yield` — **상대** 판정(같은 계정에 최신 러너가 실제로 들을 때만),
      fail-open, 인증과 같은 `_LIVE_TOKEN_PREDICATE`
- [x] 집행 `claim_request` 409 + 억제 `list_open_requests`·`wait_for_request`
      (busy-loop 금지 · 취소 통보는 유지)
- [x] 러너 자가 종료 — `runner_update.superseded`(`stale_build` 와 별개 필드) →
      `shutdown_after_drain` 로 하던 일 마치고 종료, 판정은 대기 호출 앞
- [x] 계정 경계 — 판정이 `AccountId` 스코프라 다른 계정 러너 병존 허용(사용자 예외 요구 충족)
- [x] 신규 20건 · **뮤테이션 5종 KILL** · 4 feature 전량 rc=0 · ruff clean
- [x] 인라인 적대 3렌즈 — P1 1건 자체 적발·수정(대기 즉시반환 → busy-loop) `REV-20260901T173000`
- [ ] 배포 후 라이브 실측 — 서버 축은 즉시 발효(옛 러너 재등장 시 관측), **자가 종료는 러너가
      새 사본으로 갱신된 뒤**에만 발효

## TASK-20260901T143000-selfreview-envelope — 자가 검증이 **한 건도 저장되지 않던** 결함 + 콘솔 경량 모델 (P0-AI)

**발견 경위**: 직전 cycle 배포 후 실 러너로 end-to-end 를 확인하다 드러났다. 러너는 "자가 검증
완료 — 제출에 동봉" 을 로그하는데 `redteam_reviews` 는 0 rows 였고, 서버 경고도 없었다.

**원인**: 러너가 보내는 것은 판정이 아니라 **봉투**(`{"raw": "<원문>", "latency_ms": …}`)인데
서버가 그것을 `parse_review_text` 에 그대로 넣었다. 그 함수는 dict 를 「이미 파싱된 판정」으로
보고 그대로 돌려주므로 `sanitize` 가 `None` 을 냈다 — **모든 검증이 조용히 버려졌다.**

**왜 테스트가 못 잡았나**: 양쪽을 각각만 검사했다(서버는 원문 문자열을 직접, 러너는 봉투 조립만).
**이음매**를 아무도 안 봤다 — 27건 green 인 채로 기능이 0% 동작했다.

- [x] `shared/self_review.from_runner_payload()` — 봉투 규약을 계약 모듈 한 곳에.
      관측 메타는 **봉투가 이긴다**(판정 본문의 같은 키는 AI 자기신고라 신뢰 등급이 다르다)
- [x] 버린 사실을 `info` 로 남긴다 — 이 결함이 오래 숨은 이유가 **침묵**이었다
- [x] **이음매 테스트 6건** — 봉투 모양을 러너 소스에서 읽어 재현(손으로 적으면 러너가 바꾸는
      날 이 테스트만 낡아 같은 형태로 다시 깨진다)
- [x] **역검증**: 수정 전(`origin/main`) 사본에서 **8건 FAIL** 실증 — 출하된 코드에서 죽는다
- [x] **실 러너 end-to-end PASS** — `id=397 source=external verdict=revise block_count=1`.
      검증이 **실제 결함을 잡았다**(답변 생성이 exit 1 로 실패해 안내문이 나간 것을
      `[BLOCK/completeness]` 로 정확히 지목). 설계대로 답변은 그대로 전달되고 판정만 남았다
- [x] 콘솔 3자리 표시 확인(KPI · 축별 표 · 브리지 작업 행 `BLOCK 1`)

### 콘솔 작업 경량 모델 (사용자 결정 2026-09-01)

> "관리 콘솔에서 이용될 모델은 모두 경량 모델로 구성해주세요. claude는 haiku, codex는 luna
>  모델과 같은 경량 모델로 작동해야 합니다."

- [x] `CONSOLE_JOB_LIGHT_MODELS` + `pick_console_job_model()` — **러너가 신고한 목록에서만**
      고른다. 대조 실패면 빈 값(러너 기본값) — 없는 이름을 지어 보내면 실행이 실패한다(P0-T)
- [x] 런타임 순서는 **러너 신고 순서**를 따른다 — 서버가 우열을 정하면 `--ai` 로 제한한
      사용자 의도를 넘어선다
- [x] 대화 축 **불변** — 사용자가 화면에서 고른 값이다
- [x] 회귀 6건 + **실측**: 콘솔 작업 `모델 haiku` · 대화 `모델 fable` (같은 러너, 같은 창)
- [x] `make test` 전량 green · ruff clean

#### 잔여

- [ ] codex `luna` 는 **단위로만** 확인(이 머신 codex 쿼터 소진). 선택 로직은 실 신고 형태
      (`gpt-5.6-luna` 접두)로 테스트했다
- [ ] 추론 등급은 낮추지 않았다 — 등급 어휘가 러너마다 달라(P0-Z3) 서버 추측은
      「고른 적 없는 값이 반영됐다」가 된다
## 20260901T1730-stale-runner-yield — 낡은 러너가 최신 러너의 질문을 가로챈다 (사용자 재보고)

**요청 (2026-09-01)**: 「웹페이지 새로고침, 연결 준비를 통해 러너를 다시 연결한 후 요청을
보냈지만 같은 이슈가 확인되어 조치가 필요합니다」 + 「오래된 러너 측에서 … 다른 신규 러너에
연결되는 부분이 확인된다면 오래된 러너는 프로세스를 종료 처리 … 다만 계정이 다를 경우는 예외」.

근본원인·설계·AC 는 `TASK-20260901T173000-stale-runner-yield.md`.
**위험도 Major** — 점유 집행 경로(판정이 상대라 단독 러너 동작은 불변).

<!-- PLAN-APPROVED by mckim on 2026-09-01 (러너 자가 종료 · 계정 예외 명시) -->

- [x] 라이브 진단 — 같은 계정에 러너 2개(배포본 `d0ac1263d454` vs 옛 `0a4ba732366c`),
      옛 러너가 17:20:03 질문을 먼저 집어 옛 형식으로 답한 것을 `WebOAuthTokens` + 러너 로그로 확정
- [x] 즉시 조치 — 옛 러너 프로세스 SIGTERM 정상 종료(라이브 복구)
- [x] `stale_runner_must_yield` — **상대** 판정(같은 계정에 최신 러너가 실제로 들을 때만),
      fail-open, 인증과 같은 `_LIVE_TOKEN_PREDICATE`
- [x] 집행 `claim_request` 409 + 억제 `list_open_requests`·`wait_for_request`
      (busy-loop 금지 · 취소 통보는 유지)
- [x] 러너 자가 종료 — `runner_update.superseded`(`stale_build` 와 별개 필드) →
      `shutdown_after_drain` 로 하던 일 마치고 종료, 판정은 대기 호출 앞
- [x] 계정 경계 — 판정이 `AccountId` 스코프라 다른 계정 러너 병존 허용(사용자 예외 요구 충족)
- [x] 신규 20건 · **뮤테이션 5종 KILL** · 4 feature 전량 rc=0 · ruff clean
- [x] 인라인 적대 3렌즈 — P1 1건 자체 적발·수정(대기 즉시반환 → busy-loop) `REV-20260901T173000`
- [ ] 배포 후 라이브 실측 — 서버 축은 즉시 발효(옛 러너 재등장 시 관측), **자가 종료는 러너가
      새 사본으로 갱신된 뒤**에만 발효

### POST-DEPLOY 실측 (배포본 `fe60866c`, 2026-09-01 18:15)

- [x] **자가 검증이 라이브 원장에 앉는다** — `id=399 source=external verdict=revise
      block_count=1 warn_count=1 latency_ms=15155`. **직전 배포에서는 같은 자리가 0 rows**
      였다 — 봉투 결함이 실제로 라이브를 막고 있었다는 실측
- [x] 검증이 또 실제 결함을 잡았다 — 답변 생성이 `ai.fail exit=1` 로 실패해 나간 안내문을
      지목. 설계대로 답변은 그대로 전달되고 판정만 남았다
- [x] **콘솔 작업 `haiku` · 대화 `fable`** — 한 러너·같은 창에서 두 축이 갈린다(대화 축
      불변 계약 실측)
- [x] 콘솔 3자리 표시 — KPI `자가 검증 3건 · BLOCK 2 · WARN 5` · 축별 표 4축 · 브리지 작업
      행(콘솔 작업 `—` / 대화 `BLOCK 1 WARN 1`)
- [x] 배포 게이트 전건 — 전 서비스 동일 SHA · 스모크 PASS · 503 0건 · surge 0 · 코드 도달
- [x] **테스트 위생**: 이 세션이 만든 검증 토큰 11개가 살아 있어 질문이 갈렸다 → 폐기해
      해소(사용자 `admin` 토큰 무접촉). 제품 축 개선(낡은 러너 양보)은 병렬 세션이 랜딩
## TASK-20260901T190000-ai-jobs-rewire — 남은 AI 기능 3종을 연결한 AI 로 배선 (P0-AK)

**요청 (2026-09-01)**: "'그래프 뷰' 내 'AI 능동 분석'에 대한 기능이 막혀있는것으로 확인되었습니다.
서비스 내 AI 관련 **모든 작동사항을 다시 활성화** 후, **연결한 AI를 통해 작동하도록 배선**해주세요."

**사용자 결정 (AskUserQuestion 3문)**:
1. 대량 분석 비용 가드 = **상한 없음**(기존 캡만 — 종전 서버 LLM 시절과 동일 사용감)
2. 배경 배치 = **배선 + 안내 표면화**, 그리고 **`--batch` 같은 CLI 접근성 문제는 웹 토글로 구성**
3. 검증 = **라이브 end-to-end 필수**

### 진단 (실측)

| 종류 | `wired` | 무엇이 막나 |
|---|---|---|
| `node_analysis` (그래프 능동 분석) | False | `enqueue_analysis`/`enqueue_schema_analysis` 가 게이트 확인 후 **적재 전에** 거절 |
| `insight_summary` (인사이트 배치) | False | 동일 계열 |
| `cluster_label` (클러스터 라벨링) | False | `modules/llm._get_llm_client` 단일 출구에서 차단 |

반영 함수 3종(`apply_external_*`)은 `_STORE_ROUTES` 에 **선언만 있고 구현이 없다**.

규모 실측: runs 89 · jobs 13,491 · **run 당 최대 2,594 노드** · 중앙값 16.

### 2.1 Implementation Plan

**위험도: Major** (§12.3 — 워커 구조·대기열·반영 경로 동시 변경. 파괴적 데이터 없음,
스키마 변경 없음, 인증/인가 무변경. 다만 **남의 계정 토큰을 태우는 축**이라 동의 모델이 핵심.)

#### 다의어 고지 — "연결한 AI 를 통해 작동" 이 무엇으로 판정되는가 (§7.1 · §16.7 G1)

> **입력**: 그래프 뷰에서 노드 하나를 골라 「AI 능동 분석」 실행 (러너 연결 상태).
> **기대**: (1) 202 로 run 시작 — 종전의 "제공되지 않습니다" 안내가 **뜨지 않는다**,
> (2) 러너 로그에 `task.dispatch … kind=job model=haiku`,
> (3) `node_analysis_jobs.status='done'` + `analysis` 채워짐, (4) 그래프 화면에 분석문 표시.
> **수치 1개**: 그 run 의 `node_analysis_jobs` 중 `error_kind='delegated'` 로 남은 것 = 0.

#### 설계 — 워커는 **기다리지 않는다**

`apply: store` + `_STORE_ROUTES` 가 이미 그 의도다. 워커가 응답을 기다리면 스레드가 분 단위로
묶이고, 개인 AI 가 느린 날 워커가 통째로 멎는다.

```
워커 _run_llm_inner
  └ 게이트 닫힘 + 위임 가능 → enqueue_console_job(payload={job_id,…}) → 센티넬 반환
      node job 은 status='running' 유지(updated_at 갱신) · error_kind='delegated'
                                   ↓ (러너가 답할 때)
submit_answer → apply_console_job_result → apply_external_node_analysis(conn, payload, result)
      payload.job_id 로 그 행을 찾아 analysis 기입 + status='done'
```

**스키마 변경이 없다**: 기존 stale-`running` 회수(lease)가 「러너가 끝내 답하지 않음」의
backstop 이다 — 회수되면 `pending` 으로 돌아가 다시 위임된다(자가 치유).

#### 배치 동의를 **웹 토글**로 (사용자 결정)

`--batch` 는 CLI 플래그라 접근성이 떨어진다. 동의의 주체는 그대로 계정 소유자로 두되,
**표현 수단을 웹으로** 옮긴다:

- 서버: 계정별 동의 값 저장 + **하트비트 응답**에 실어 보냄
- 러너: 하트비트 응답을 읽어 `features` 를 **동적 갱신**(`batch_jobs` 추가/제거).
  `--batch`/`--no-batch` 는 그 머신에서의 **명시 override** 로 남긴다(서버가 켜도 그 머신에서
  끌 수 있어야 한다 — 동의는 두 겹이지 이중 정의가 아니다)
- 웹: '내 AI 연결' 화면에 토글 + 무엇을 태우는지 1줄 고지

#### 영향받는 파일 · symbol

| 경로 | 변경 |
|---|---|
| `shared/bridge_tasks.py` | `node_analysis`·`insight_summary`·`cluster_label` → `wired: True` |
| `modules/node_analysis.py` | `enqueue_*` 게이트를 「위임 가능하면 통과」로 · `_run_llm_inner` 위임 분기 · `apply_external_node_analysis` |
| `modules/insight.py` | `apply_external_insight_summary` |
| `modules/semantic_cluster.py` | `apply_external_cluster_labels` |
| `shared/bridge_consent.py` | **신규** — 계정별 배치 동의 저장·조회 단일 정본 |
| `routers/ai_tools.py` | 하트비트 응답에 `batch_consent` · claim 시 동의 재확인 |
| `static/agent/bridge_agent.py` | 하트비트 응답으로 `features` 동적 갱신 + `--no-batch` |
| `static/ai-connect.js` · `admin/*.js` | 배치 동의 토글 + 고지 |

#### 완료 판정 기준

- `AC-20260901T190000-ai-jobs-rewire-1`: 러너 연결 상태에서 그래프 노드 분석이 **시작되고**
  (202) 종전 차단 안내가 뜨지 않는다.
- `-2`: 그 분석이 **연결된 AI 에서** 돌고(러너 로그 `kind=job`), 결과가 `node_analysis_jobs`
  에 `done` 으로 기입되어 화면에 뜬다.
- `-3`: 러너가 끝내 답하지 않으면 lease 회수로 `pending` 복귀 — 영구 고착되지 않는다.
- `-4`: 배치 동의를 **웹에서 토글**할 수 있고, 끄면 러너가 배치를 더 이상 신고하지 않는다.
- `-5`: 동의한 러너가 0명이면 콘솔이 그 사실을 말한다(배선만 하고 침묵하지 않는다).
- `-6`: 게이트를 되돌리면(`AGENT_SERVER_LLM_ENABLED=1`) 종전 서버 경로가 그대로 돈다.

<!-- PLAN-APPROVED by user on 2026-09-01 (AskUserQuestion 3문 응답) -->

### 2.2 구현 기록 (2026-09-01)

계획과 **다르게 간 곳**과 그 이유:

| 계획 | 실제 | 왜 |
|---|---|---|
| `_run_llm_inner` 에 위임 분기 | `_run_llm`(바깥) 에 센티넬 + `_persist` 가 적재 | `_run_llm_inner` 는 예산 슬롯 **안**이다. 거기서 위임하면 개인 AI 가 도는 동안 서버 LLM 예산 슬롯을 붙든다. 그리고 적재는 DB 를 쓰므로 「DB 미접근」 계약인 스레드 본체에서 할 수 없다 |
| `routers/ai_tools.py` claim 시 동의 재확인 | 재확인 **안 함** | 배급 자격은 러너 신고(`RunnerFeatures`) 하나가 정본이다. claim 자리에서 계정 동의를 또 보면 같은 질문에 두 개의 답이 생기고, 갈리는 순간 느슨한 쪽이 사실이 된다 |
| `insight_summary` = "인사이트 배치" | **"테이블 인사이트 배치"** 로 이름을 좁힘 | 배선된 것은 테이블 축이다. 스키마·계정 인사이트는 서버 경로뿐 — 넓은 이름에 `wired: True` 를 달면 그것들까지 배선됐다고 말하게 된다(레지스트리가 금지하는 부분 배선) |

계획에 **없었는데 필요했던 것**:

- **`shared/bridge_tasks` 로 승격 4종** — 러너 자격 질의(`runner_profile_for_account`)·생존
  술어(`LIVE_TOKEN_PREDICATE`)·버전 하한(`version_at_least`)·기능 정규화
  (`parse_runner_features`) + 프롬프트 편성(`messages_to_prompt`). 종전엔 전부 웹 프로세스
  안에 있었는데, 위임 판단을 **insight-worker** 가 하게 되면서 다른 컨테이너가 같은 질문에
  답해야 했다. 워커 쪽에 다시 적으면 로그아웃한 세션의 러너를 워커만 자격 있다고 보는 창이
  열리고, 그 창에서 적재된 작업은 아무도 집지 않는다.
- **`dedupe_key`** (`enqueue_console_job`) — 배경 배치는 결과가 오기 전까지 매 pass 「아직
  값이 없다」로 판단해 **같은 작업을 다시 적재**한다. 그 중복은 전부 실제로 처리되므로
  같은 답을 사용자 계정 토큰으로 여러 번 사는 것이 된다. 대기열 상한은 폭주만 막는다.
- **`apply_external_node_analysis` 안의 run 마감** — 워커의 마감 판정은 그 cycle 에 잡을 집은
  run 만 훑는다(`touched_runs`). 마지막 잡이 위임으로 끝난 run 은 워커가 다시 건드릴 일이
  없어, 여기서 닫지 않으면 영원히 `running` 이고 그 상태가 사용자의 재트리거까지 막는다.

낡은 계약 테스트 **3건을 행위 기반으로 재작성**(구조를 잠그고 있던 것):

- `test_node_analysis_refuses_before_enqueue` → `…_only_when_nowhere_to_delegate`.
  종전 계약(「닫혔으면 거절」)이 곧 사용자가 제보한 결함이었다. 지켜야 할 것(큐에 넣어 놓고
  한참 뒤 실패로 끝내지 않는다)은 그대로 두고 판정 대상만 바꿨다.
- `test_capability_read_shares_the_freshness_rule_with_listening` / `…_survives_corrupted_json`
  — 소스 문자열을 보던 검사라 질의가 shared 로 옮겨가자 계약은 그대로인데 FAIL 했다(같은
  검사가 이미 두 번 옮겨졌다는 주석이 남아 있었다). **실제로 나가는 SQL** 과 **반환값**을
  보도록 고쳐, 정의가 어디로 가든 술어가 진짜로 갈릴 때만 실패한다.
## 20260901T1830-newest-runner-wins — 판정축 정정: 빌드 지문 → 연결 순서 (사용자 재현)

**요청 (2026-09-01)**: 「'root' → 'claude-corp' 순서로 연속 연결했는데 더 오래된 연결에서
연결이 끊겼다는 로그가 남지 않았으며, 'claude-corp' 연결 이후에도 모달이 닫히지 않는(연결이
완수되지 않는) 현상」.

근본원인·설계·AC 는 `TASK-20260901T183000-newest-runner-wins.md`. **위험도 Major**.

- [x] 라이브 진단 — 두 러너 **지문이 동일**(`05d75225aded`)이라 직전 축(빌드)이 무판정.
      모달 미닫힘은 `account_runner_build` 의 하트비트 정렬이 만든 `runner_stale` 진동
- [x] 축 교체 — 같은 계정의 **더 나중에 발급된 토큰**(연결 순서)이 하트비트 중이면 양보
- [x] 등록형 MCP 클라이언트 보호 — 양쪽 모두 하트비트 이력 필요(당사자 한정)
- [x] 화면 정본 `ORDER BY t.Id DESC` — 화면과 점유가 같은 축(진동 소멸)
- [x] 안내 문구·러너 로그 축 정정 · 지문 판독 실패가 기능을 끄던 게이트 제거
- [x] 23건 · **뮤테이션 4종 KILL**(⚠ 최초 M1 생존 → 테스트 더블 판별력 보강 후 KILL) ·
      4 feature rc=0 · ruff clean
- [x] 인라인 적대 3렌즈 `REV-20260901T183000`
- [ ] 배포 후 라이브 실측 — ① 오래된 러너 프로세스가 실제 종료되는가 ② 연속 연결 시 모달이
      닫히는가

### 완료 체크리스트 — TASK-20260901T190000-ai-jobs-rewire (P0-AK)

- [x] 진단 — `enqueue_*` 가 적재 **전에** 거절(거절 자체는 옳고, **위임 경로가 없었다**) ·
      반영 함수 3종은 `_STORE_ROUTES` 에 **선언만** 있고 구현 부재
- [x] `shared/bridge_consent.py` 신설 — 진리표 · `normalize_consent` · 고지 문구 단일 정본
- [x] 러너 자격 판정을 `shared/bridge_tasks` 로 승격(질의·생존 술어·버전 하한·기능 정규화·
      프롬프트 편성) — 웹과 **insight-worker** 가 같은 판정을 읽는다
- [x] `node_analysis` — 게이트를 「둘 중 하나라도」로 · `_delegate_job`(워커는 기다리지 않는다) ·
      `apply_external_node_analysis`(늦은 답이 최신 값을 덮지 않음 + run 마감)
- [x] `cluster_label` — 라벨 배치 위임 + 기존 kv 캐시에 기입(다음 pass 캐시 적중)
- [x] `insight_summary` — 테이블 인사이트 위임 + KV 이음매(다음 cycle 상속 경로가 기존대로 발행).
      **이름을 "테이블 인사이트 배치" 로 좁혔다** — 스키마·계정 축은 아직 서버 경로뿐이다
- [x] `dedupe_key` — 결과 오기 전 재적재로 **같은 답을 여러 번 사는 것**을 막는다
- [x] 배치 동의 웹 토글 — `WebAccounts.BridgeBatchConsent` · 하트비트 응답 · 러너 동적 신고 ·
      `/api/ai/connect/batch-consent` · '내 AI 연결' 체크박스 + 고지 · 콘솔 `배경 작업 동의 N`
- [x] 신규 계약 21건(이음매 진리표 포함) · 역검증 13건 FAIL@`d1b2a688`
- [x] 낡은 계약 테스트 4파일 재작성(3건은 구조를 잠그고 있었고, 1건은 계약 자체가 제보된 결함)
- [x] `make test` green(컨테이너) · ruff clean · route 골든 +1/-0 · ROUTEMAP 재생성
- [x] 라이브 오염 확인 — 게이트 통과 테스트가 실제 PG 에 닿던 것을 고치고 `ds1` 잔재 0건 실측
- [ ] **배포 후 라이브 end-to-end**(사용자 요구) — AC-1~-5. 그래프에서 실제로 눌러 202 →
      러너 로그 `kind=job` → 원장 `done` → 화면 · 웹 토글 ≤30초 반영 · 동의 0명 표면화

## 20260902T1000-autolaunch-runner — 이미 연결해 본 사용자에게는 [내 AI 실행] 을 자동으로

**요청 (2026-09-02)**: 「이미 한 번 연결이 진행된 사용자들의 대상으로는 자동으로 '내 AI 실행'
이 진행될 수 있도록 (미연결 상태에서 '연결 필요' 버튼 클릭 시 / 로그인 진입 시). '업데이트
필요' 가 나타날 경우 클릭만으로도 러너가 재구성될 수 있도록」.

설계·AC·발효 범위는 `TASK-20260902T100000-autolaunch-runner.md`. **위험도 Major**.

<!-- PLAN-APPROVED by mckim on 2026-09-02 -->

- [x] 자격 판정 — 서버 `last_os`(러너 실연결 시에만 기록)를 이력 신호로. 브라우저 저장 금지
- [x] 실행 URL 프리페치 — 클릭이 **동기적으로** 이동해야 크롬이 거르지 않는다(이 기능의 급소)
- [x] 진입점 4개 — 칩·게이트(단일 `_connectEntry`)·로그인 진입(1회, 창 안 엶)·업데이트 필요
- [x] 대기·판정 단일화(`_awaitUsable`) — 자동/수동 공유, «무응답» ≠ «서비스 응답 없음»
- [x] 런처가 러너를 최신본으로 교체(양판) — **토큰 검증 뒤** · 실패는 기동을 막지 않음
- [x] 이력 없는 사용자 무회귀(네 경로 모두 종전대로 창)
- [x] 신규 19건 · **뮤테이션 4종 KILL** · 4 feature rc=0 · ruff clean · ps1 BOM 보존
- [x] 기존 계약 2건 갱신(리터럴 함수명 → 관계) — 개선을 되돌리라고 요구하던 게이트
- [x] **수정 전 실 브라우저 실측** — 칩 `업데이트 필요` 클릭 → 창만 열리고 러너 그대로
- [x] 인라인 적대 3렌즈 `REV-20260902T100000` (P1 1건 자체 적발: 갱신을 토큰 검증 앞에 두면
      임의 사이트가 러너 파일을 교체)
- [ ] **배포 후 라이브 실측** — ① 업데이트 필요 클릭이 실제 발사되는가 ② **로그인 진입 자동
      실행이 크롬 활성화 정책에 걸리는가**(추측하지 않고 잰다) ③ 이력 있는 미연결 계정 칩 클릭

## 20260902T1100-click-beats-entry — 진입 자동 시도가 클릭을 삼키던 회귀 (배포 후 실측 적발)

직전 cycle(`20260902T1000`) 배포 후 실 Windows 브라우저 왕복에서 적발. 상세는
`TASK-20260902T110000-click-beats-entry.md`.

- [x] 회귀 재현 — 칩 클릭 40초 뒤에도 실행·창 **둘 다 없음**(개선 이전보다 나쁨)
- [x] 클릭이 자동 시도를 대체 · 클릭끼리는 중복 방어 유지
- [x] 일련번호로 대체 판정 — 대체된 시도는 잠금·창·결과 어느 것도 건드리지 않음
- [x] 테스트 3건 추가(총 22) · 뮤테이션 KILL 2건
- [ ] 스킴 실행 → 러너 재기동 축은 **핸들러 등록**(별개 축)에 달려 있어 이월
