# Run — TASK-20260909T000000-prompt-autogen-delivery

- 일시: 2026-09-09 (Asia/Seoul)
- 브랜치/worktree: `ai/claude/feature-0043-prompt-autogen-delivery` / `.worktrees/feature-0043-prompt-autogen-delivery`
- base: `cdd414e3`
- 요청(원문): "DQA 계정 프로필에서 '프롬프트 > 내 프롬프트' 의 자동 작성 기능이 동작하지 않아 수정이 필요합니다."
- 범위 확정(AskUserQuestion, 2026-09-09): ① 자동 작성 3진입점 모두 ② 폴링 권한 축 함께.

## 1. 진단 근거 (라이브 실측, 코드 변경 전)

| 축 | 관측 | 판정 |
|---|---|---|
| web 접근 로그 | `GET /api/auth/me/system-prompt/generate/stream HTTP/1.1" 200 OK` (repo-web-a-1, 최근 72h 중 1건) | 요청은 성공했다 |
| `WebAiTasks` | `j_LO28YKoH0ifGR5E7` · JobKind=`prompt_generate` · AccountId=10 · CreatedAt `2026-09-08 19:56:05` · SubmittedAt `19:56:08` · JobAppliedAt `19:56:08` · payload `{"scope":"account","scope_id":10}` | 위임 적재·제출·반영까지 서버는 정상 |
| `JobResult` (424자) | `AI 가 오류로 끝났습니다(exit 1). 연결된 AI 가 남긴 사유: You've hit your session limit · resets 8pm (Asia/Seoul)` + 러너 대체 꼬리표 | 그 시도는 **개인 AI 사용 한도**로 실패. 그 사실조차 화면에 전달되지 않았다 |
| `AnswerVerdict` / `JobApplyError` | `allow` / `NULL` | 서버는 이것을 실패로 알지 못한다(러너가 답변 본문으로 신고) |
| 프론트 grep | `bridge_pending` 처리는 `admin/metadata.js`·`app/composer.js` 뿐. 자동작성 3화면(app.js·admin.js)에 없음 | **화면이 위임 봉투를 읽지 않는다** = 근본 원인 |
| 권한 축 | `poll_url` = `/api/admin/ai-jobs/{task_id}` (=`console.access`) vs `JOB_SPECS['prompt_generate']['perms'] == ()` | 로그인만 요구하는 진입점에 관리자 전용 폴링 주소 |

계정 10 은 Admin 역할이라 폴링 권한 축은 이 사용자에게는 발현하지 않았다 — 화면 미처리 한
가지만으로도 무반응이 된다. 권한 축은 일반 사용자에게 발현할 **잠복** 결함이었다.

## 2. 기계 검증

| 항목 | 결과 |
|---|---|
| `pytest unit/feature-0043-external-llm-bridge/tests/test_prompt_autogen_delivery.py` | **21 passed** |
| `node unit/feature-0003-agent-web-ui/tests/verify_prompt_autogen_delivery.mjs` (jsdom@22) | **15 passed, 0 failed** |
| ES module 구문 (`node --check`) — console-job-poll.js · llm-state.js · app.js · admin.js · release-notes-data.js | 전건 OK |
| Python 구문 (`ast.parse`) — bridge_tasks.py · _console_jobs.py · admin_console.py · profile.py | 전건 OK |
| `make test` 전체 회귀 | 아래 §4 |

### 2.1 뮤턴트 역검증 (테스트가 실제로 결함을 잡는가)

「내가 만든 테스트가 내가 만든 결함만 죽인다」를 피하려고, **원래 결함 자체**를 재현해 baseline
RED 를 확인했다.

| 뮤턴트 | 적용 | 결과 |
|---|---|---|
| M1 — `console-job-poll.js` 의 `body.degraded === true` 가드 제거 | `if (false)` 로 치환 | **KILL** — S2 2건 FAIL (13/2) |
| M2 — `app.js` 의 위임 분기 통째 제거 (= 2026-09-08 라이브 상태 재현) | `if (looksDelegatedEnvelope…)` 블록 삭제 | **KILL** — S1 3건 FAIL (8/7) |
| 복구 후 | 원본 복원 | 15/15 PASS |

M2 는 이 cycle 이 고친 결함 그 자체다 — 하네스가 «고치기 전 상태» 에서 실제로 붉어진다.

## 3. AC 대조 (TASK.md §2.1)

| AC | 결과 | 근거 |
|---|---|---|
| AC-1 위임 결과가 textarea 에 도달 | PASS | 하네스 S1 (`{"bridge_pending":true}` → 폴링 done → textarea = result) |
| AC-2 `console.access` 없는 계정도 성립 | PASS(구조) | `poll_url_for` → `/api/profile/ai-jobs/…` · 신규 라우트는 `get_current_account` 만 요구 · pytest 4건. **라이브 일반계정 왕복은 §5 이월** |
| AC-3 관리 콘솔 역할·제품도 동일 | PASS(배선) | pytest 배선 2건(분기 순서·import) · admin.js 는 하네스 미대상(§5) |
| AC-4 러너 실패 시 본문 미덮음 | PASS | 하네스 S2 + pytest degraded 3건 |
| AC-5 게이트 열린 배포의 SSE 무회귀 | PASS | 하네스 S3 |
| AC-6 기존 계약 회귀 0 | §4 | 정적 스탬프 census·라우트 스냅샷 포함 |

## 4. 전체 회귀 · 완료 게이트

| 항목 | 결과 |
|---|---|
| 컨테이너 `make test` (2026-09-09 11:50 종료) | **exit 0 · `FAILED` 0건 · 진행률 100%** · `ruff: All checks passed!` |
| `bash bin/verify-completion.sh --pre-commit feature-0043-external-llm-bridge` | **PASS** — #2·#3·#4·#6·#7·#8·#9·#10·#11·#12·#14·#15·#16·#17·#18 PASS, #13 WARN(아래) |
| check #13 visual verification | WARN — DQA-client 실측 PASS 미확인(§5 이월). NOT-RUN + Reason 기록으로 게이트는 통과 |
| `python3 bin/gen-routemap.py` | 269 routes / 30 modules 재생성 — `GET /api/profile/ai-jobs/{task_id}` · `DI:get_current_account` · 권한 `—` 로 등재(권한 축의 기계적 증거) |
| `bash bin/codenav-lint.sh` | OK — CODE_NAVIGATION/CODE_TASKS 앵커 전부 resolve |
| `codex review --uncommitted` (codex-cli 0.153.4) | **ACCEPTED · P1 0건**. 리뷰 도중 reviewer 가 행위 하네스를 직접 구동해 15/15 PASS 재확인 |

> ⚠ pytest 의 최종 요약 줄(`N passed, …`)은 `-q` 출력이 warnings 뒤에서 잘려 로그에 남지 않았다.
> 판정 근거는 **`make` 종료코드 0 · `FAILED` 0건 · 진행률 100%** 세 축이며, 건수는 적지 않는다
> (재지 않은 수치를 기록하지 않는다).

### 1차 실행에서 드러난 것 (수정 전)

1차 `make test` 는 5건 FAIL 이었고 그중 **3건이 내 리팩터가 깬 기존 계약**이었다 —
`test_console_job_delegation` 이 `admin/llm-state.js` 소스에서 `awaitDelegatedResult` 본문을 찾는데
구현을 옮겼기 때문이다. **계약은 그대로 두고 검사 대상 파일만** `console-job-poll.js` 로 옮겼고,
「구현을 옮겨도 기존 import 경로는 살아 있어야 한다」는 단정을 하나 더했다(관리 콘솔의 메타데이터
자동완성이 그 경로를 쓴다).

### base 에 이미 있던 적색 2건 (내 변경이 만든 것이 아니다)

base `cdd414e3` 에서 이미 붉었다 — 다른 cycle 이 라우트 2개를 추가하며 두 계약을 갱신하지 않았다.

| 테스트 | base 상태 | 처리 |
|---|---|---|
| `test_route_parity_p5b` | golden 269 vs 실제 271 | 컨테이너에서 golden 재생성(272/271). 흡수된 base drift = `POST /api/ai/connect/identity` · `POST /api/ai/tools/get_tool_catalog` |
| `test_cancel_channel_adds_no_new_tool` | 명시 도구 7 기대 vs 실제 8 | `get_tool_catalog` 의 **4곳 정합을 확인한 뒤**(매니페스트/OpenAPI `routers/ai_discovery.py` · MCP 어댑터 2벌 · `test_ux_parity` 초록) 숫자만 7→8. 계약은 그대로 — 또 늘면 여전히 잡는다 |

### 출하 중 정정 1건 (post-commit 게이트가 잡았다)

첫 커밋 `424e20ff` 의 `Task-Cycle:` trailer 에 **worktree slug**(`feature-0043-prompt-autogen-delivery`)
를 적었는데, post-commit verify 는 그 값을 **feature 디렉토리 id** 로 해석한다
(`ERROR: feature directory not found`). 정본 id 는 `feature-0043-external-llm-bridge` 다.
amend 는 §16.3 이 금지하므로 후속 커밋에서 올바른 trailer 로 정정했다. 첫 커밋의 잘못된 값은
이력에 남으며, 이 문단이 그 대응 기록이다.

## 4b. 출하 · 배포 · 라이브 도달 (POST-DEPLOY)

| 단계 | 결과 |
|---|---|
| PR | **#1644** — `ai/claude/feature-0043-prompt-autogen-delivery` → `main` |
| 머지 충돌 | main 이 21 commit 앞서 CONFLICTING → §16.4 자율 해결(4파일). 결과 검증: **양쪽 부모 대비 삭제 파일 0건** · 내 고유 심볼 5종 생존 · main 고유 산출물 표본 4종 생존 · `node --check` OK. 머지 커밋 `0be2b954` |
| 머지 후 재검증 | 핵심 pytest 85건 PASS · jsdom 15/15 PASS · 컨테이너 라우트/스탬프/캐시 계약 **30건 PASS** |
| main 반영 | `dfc5717e` → **`00981307`** (`bin/cycle-finalize.sh --pr 1644`, worktree·로컬/원격 branch·REGISTRY 정리 완료) |
| 배포 | `sudo -E bin/deploy-web.sh --web-only` **exit 0** — web-a/web-b 롤링(`git_commit=00981307`) · 엣지 후보 복귀 확인 · **90초 soak 통과** · Caddyfile 무변경(blip 0) · 브리지 연속성 끊김 0 |

### 라이브 도달 확인 (배포됨 ≠ 브라우저에 도달함)

`?v=` 스탬프가 붙은 **실제 서빙 URL** 로 받아 내용을 검사했다. 세 축 모두 통과.

| 축 | 확인 | 결과 |
|---|---|---|
| 작업 화면 | `GET /static/app.js?v=3f19ce1d878b` (505,813 B) | `looksDelegatedEnvelope` 2 · `bridge_pending` 3 · `console-job-poll.js` import 1 |
| 신규 모듈 | `GET /static/console-job-poll.js?v=3f19ce1d878b` | **HTTP 200 · 9,445 B** — `awaitDelegatedResult` · `api/profile/ai-jobs` · `body.degraded === true` 각 1 |
| 관리 콘솔 | `GET /static/admin.js?v=3f19ce1d878b` + `admin/llm-state.js?v=…` | `looksDelegatedEnvelope` 3 · re-export 2건 · llm-state HTTP 200 |
| 신규 라우트 | `GET /api/profile/ai-jobs/j_LIVEPROBE` (비로그인) | **401** `{"error":"로그인이 필요합니다."}` — 라우트 등록됨 + 로그인만 요구 |
| 대조군 | `GET /api/profile/no-such-route-xyz/1` | **404** — 위 401 이 「없는 경로도 401」이 아님을 확인 |
| 호환 경로 | `GET /api/admin/ai-jobs/j_LIVEPROBE` | 401 — 종전 경로 유지 |

> 스탬프가 두 자산에서 동일(`3f19ce1d878b`)하다는 것은 `inject_asset_stamp.py` 가 이번 배포
> 산출물에 적용됐다는 뜻이다. 스탬프 없는 참조가 있으면 브라우저가 옛 사본을 계속 쓰는데,
> 그 축은 `test_static_module_stamp_census` 가 별도로 잠근다(위 30건에 포함).

## 4c. 라이브 실측 (사용자 요청 "실측까지 진행", 2026-09-09 12:22~12:27 KST)

§5 에서 「러너 자격 때문에 이월」로 남겼던 것을 **검증용 러너를 직접 띄워** 해소했다.

| 축 | 관측 | 결과 |
|---|---|---|
| 러너 기동 | 정본 `python3 -m agent.lifecycle --no-batch --no-self-review` (`BRIDGE_AI=codex`, 사설 CA) | `run.ready runtime=codex` · 하트비트 도달 |
| 자동작성 호출 | `GET /api/auth/me/system-prompt/generate/stream` | **200 · `application/json`** · `bridge_pending` 봉투 · `poll_url=/api/profile/ai-jobs/…`(신설 경로) |
| 폴링 | 화면과 같은 순서로 6회 | `working` ×5 → **`done`** · `degraded=false` · result **655자**(실제 프롬프트) |
| 화면 | 실제 브라우저에서 [자동 작성] 클릭 | 「…연결된 본인 AI 에 맡겼습니다」 → 「연결된 AI 가 처리 중…」 → **「연결된 AI 가 작성했습니다 (559자)」 + 입력란 559자** |
| 러너 반대편 | `task.dispatch runtime=codex model=gpt-5.6-luna` → `task.submit.ok dur_ms=24438 answer_chars=559` | 왕복 일치 |

⚠ **단일 파일 러너(`bridge_runner.py`)로는 이 검증이 성립하지 않는다** — 하트비트 전송 코드가
없어(`grep heartbeat` → 0) `listening=False` 가 되고 위임 자체가 일어나지 않는다. 정본은
`src/agent/` 모듈군이다. 이 사실을 모르고 단일 파일로 재려다 한 번 헛돌았다.

시각 증거: `feature-0003 test-runs.d/evidence/20260909-prompt-autogen-live.png`.
원상복구: 미저장 입력란 비움 + 드로어 닫음(저장 안 눌러 DB 쓰기 0) · 검증 러너 종료 ·
검증 세션 로그아웃(결합 토큰 동시 무효) · 로컬 토큰/쿠키 파일 삭제. 사용자 앱·세션 미종료.

## 5. 미검증 · 이월 (정직 표기)

- **jsdom 하네스는 CI 에서 돌지 않을 수 있다.** `make test` 컨테이너는 node 를 설치하지만
  jsdom 은 설치하지 않는다 → `verify_prompt_autogen_delivery.mjs` 는 exit 2(미설치)로 강등되고,
  pytest 는 그 사실이 이 원장에 기록돼 있는지만 확인한다. **이 문단이 그 기록이다.** 로컬
  실측(위 §2)은 `npm i jsdom@22 --prefix /tmp` 후 수행했다.
- **admin.js 는 행위 하네스 대상이 아니다.** `buildSystemPromptEditor` 는 관리 콘솔 상태에
  깊게 묶여 있어 함수 단위 추출 구동이 어렵다. 배선(분기 위치·import·pending 반영)은 pytest 가
  잠그지만, «실제로 채워지는가» 는 라이브 관리 콘솔에서 확인해야 한다.
- ~~**라이브 왕복은 러너 자격에 달려 있다.**~~ → **§4c 에서 해소**(검증용 러너 기동 후 실측 PASS). 아래는 그 시점의 기록이다. 위임이 실제로 일어나려면 그 계정의 개인 AI 러너가
  연결돼 있어야 하고, 재기동에는 사람이 웹에서 발급하는 `mat_` 토큰이 필요하다. 배포 후
  도달 확인(서빙 자산에 새 모듈·새 분기가 실려 있는가)은 러너 없이 가능하므로 그것을 수행한다.
- **러너 실패 판정은 문구 의존이다.** `submit_answer` 에 실패 신고 채널이 없어 러너의 고정
  꼬리표로 판정한다. `test_runner_degraded_notice_matches_the_runner_source` 가 러너 정본과의
  동기를 잠그지만, 근본 해소(제출 API 에 실패 플래그 + 구 러너 폴백)는 별도 작업으로 남긴다.
