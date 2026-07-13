---
doc_type: TASK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## TASK-20260709-ask-timeout-nonblocking — 응답 지연 시 화면 전체를 덮던 타임아웃 복구 모달 제거(조용한 자동 재연결로 대체) (Minor §12.3 — feature-0003 프론트 단독. /_template:entry arg-given dispatch)
- 트리거(사용자): "작업 화면에서 서비스 assistant 에 요청 후 상대적으로 오래 걸리면 화면 전체를 가리는 답변-지연 경고창이 떠 불편 — 해당 화면을 삭제하거나 기존 작업을 방해하지 않는 UI로 구성." 후속 지시: "자동 재연결은 필수 동작이며 사용자는 그 작동을 알 필요 없음."
- 진단: `static/app.js sendPrompt()` 의 `/api/ask` 실패 + `/api/ask_status` `is_processing=true` 경로가 `showTimeoutRecoveryDialog`(fixed inset0·z-index 9999 backdrop + 3버튼 모달)를 `await` 로 띄워 화면 전체를 가리고 진행 강제 중단(TASK-0041 도입). 3액션(취소/즉시답변/계속대기)은 이미 컴포저 인라인 어포던스(전송→"중단" TASK-0157 / "즉시 답변" TASK-0158 / attach 기본동작)로 상시 존재 → 모달 중복. 재연결만 필수.
- 설계(모달 삭제 + 조용한 재연결): `is_processing` 분기를 모달·토스트 없이 `attachAndWaitForResult(askCid,{runId})` 직접 호출로 교체(답변 유실 방지·화면 미가림·재연결 미표면화). dead code `showTimeoutRecoveryDialog` 제거. DESIGN-entry-points.md 모달 예시 참조를 `.share-mgr-backdrop`/`.share-mgr-panel` 로 갱신. index.html app.js 캐시버스터 bump.
- Risk: **Minor** — frontend 표현계층 단일파일 동작 변경, 비파괴, 서버 계약(ask_status/ask_result/attach 루프)·RBAC·스키마 무변경. 되돌리기 쉬움.
- Completion Checklist:
  - [x] `is_processing` 분기 → 조용한 `attachAndWaitForResult` 직접 호출로 교체. `showTimeoutRecoveryDialog` 함수 제거(tombstone 주석). node --check app.js PASS.
  - [x] index.html app.js 캐시버스터 `?v=20260709-ask-timeout-nonblocking`.
  - [x] DESIGN-entry-points.md 모달 패턴 참조 2곳 갱신(제거 함수 stale 방지).
  - [x] §18.8 적대 서브에이전트 패널(2라운드) → R1 MAJOR(H1: earlyCid 흐름 인라인 취소 무동작, 모달이 가려온 `myAskInFlight` 키 비대칭) 적발 → 동반수정(sentinel→earlyCid 키 이관 + finally dual-delete + renderComposer) → R2 재검 SHIP. REV-20260709T130000-ask-timeout-nonblocking. node --check PASS(2회).
  - [x] verify-completion --pre-commit PASS → commit d87d582e → PR #638 머지(main 4b6919ec) → web 무중단 재배포(deploy-web, 4b6919ec, soak PASS). **POST-DEPLOY PB-0008 런타임 실측 PASS**(win-browser Chrome/149): 서빙 app.js 에서 `typeof showTimeoutRecoveryDialog==="undefined"`(모달 런타임 완전 제거 → 경고창 노출 불가)·attachAndWaitForResult 보존·composerFinalizeBtn/sendBtn DOM 존재·z-9999 backdrop 부재·pageerror 0. (TEST.md §3 POST-DEPLOY 갱신 참조.)

## TASK-20260709-reasoning-budget-per-model — 모델별 추론 예산 상한 확대(native) + 모델→추론강도 accordion + [추론↔본문] 비율 슬라이더 (Major §12.3 — shared + feature-0002 core + feature-0003 web/UI. /_template:entry arg-given dispatch)
<!-- PLAN-APPROVED by mckim on 2026-07-09 (ExitPlanMode 승인 — 동반 상향·모델별 native·종속 accordion·비율 슬라이더) -->
- 트리거(사용자): "`관리 콘솔 > 시스템 > 설정 > 모델별 추론 예산` 최대값 16000 상향 검토 — '매우 높음' default=max=16000 이라 조정 의미 없음." 후속 결정: 동반 상향 + 실제 Sonnet 128K/Haiku 64K 활용 + 모델별 추론 수준 분리 + 종속 accordion·dropdown + [추론↔본문] 비율 슬라이더.
- 근본원인: 16000 은 모델/API 한계가 아니라 정책 캡(`_MODEL_BUDGET_MAX`/`_REASONING_BUDGET_MAX`). 실제 병목은 `_CLAUDE_MAX_TOKENS["agent"]=20000` + `budget<max_tokens` 제약. '매우 높음' spec default=maximum=16000 이라 상향 여지 0.
- Completion Checklist:
  - [x] `shared/model_catalog.py`: `_CLAUDE_MODEL_MAX_OUTPUT`(sonnet 128000/haiku 64000) + `model_native_max_output`. `max_tokens_for_model` task cap **무변경**(plan 등 "agent" task 공유 소비자 무회귀). py_compile PASS.
  - [x] `shared/runtime_settings.py`: 신규 group `agent_max_output`(모델별 총 출력, default 40000/24000·max native) + per-model `reasoning_budget:{model}:{level}` 스킴 + `agent_max_output`/`reasoning_budget_override(model,level)` reader + `serialize_registry` `agent_max_outputs`. thinking budget 상한 = native−1024.
  - [x] `unit/feature-0002-agent-core/src/agent_core.py` `_call_llm`: token_limit = `_rts.agent_max_output(model)`(thinking 모델), reasoning override 에 model 인자. `min(budget, max_tokens−1024)` clamp 유지.
  - [x] `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css,release-notes-data.js}`: 모델별 `permission-group` accordion + 총 출력 입력 + 추론강도별 [추론↔본문] 비율 슬라이더(신규 `.rs-slider`/`.rs-split-bar`) + 커밋바 dirty(RS_AGENT_MAX_PREFIX). node --check PASS.
  - [x] 테스트: `test_runtime_settings.py`(agent_max_output 등록·override·native clamp·per-model 격리·backward-compat) + `test_reasoning_effort.py`(per-model 주입·총×예산 분리·clamp) 마이그레이션+신규, `test_prompt_gen_max_tokens.py` 무회귀. 컨테이너 `make test` feature 관련 전건 PASS(잔여 3건=env `AGENT_TIMEOUT_SEC=300`·`--no-deps` DB 아티팩트, unset 시 PASS 확인).
  - [x] §18.8 적대 패널(general 5축) → BLOCKING 0. Finding1(plan 경로 결합) fixed(대화 default 를 runtime_settings 로 분리) · Finding2(슬라이더 동적 상한 검증) fixed · Finding3(display staleness) 수용-NIT. REV-20260709T051642-reasoning-budget-per-model.
  - [x] verify-completion --pre-commit PASS → commit 0aabceb4 → PR #641(rebase 충돌 MODIFY/TASK 해소·force-push) → 머지(main fbf3b606) → `make deploy-web` 무중단 롤링(web-a/web-b fbf3b606, soak 90s PASS, `/healthz` git_commit=fbf3b606). **캐시버스터 누락 발견**(admin.js/styles.css 변경했으나 admin.html `?v=` 미bump) → 후속 CHG-20260709T055431-reasoning-budget-cachebuster 로 `?v=20260709-reasoning-budget` bump + 재배포.
  - [x] (후속, 사용자 검토) 다회차 정합성 확인 — max_tokens/budget 은 라운드당임을 확인(기능 충돌 없음). '총 출력' 표시를 '라운드(단계)당 · 총량≈×회차 · native 근처=회차 축소 주의'로 정밀화(로직 무변경). CHG/REV-20260709T090722-reasoning-budget-labels, PR/배포 진행.
  - [ ] **라이브 PB-0008(배포 후 잔여)**: 모델 카드 접기/펼치기·총 출력(라운드당) 상향(128000)·비율 슬라이더 드래그→추론/본문 갱신·'매우 높음' 16000 초과 저장. (앱 미기동 unattended 환경이라 사용자 육안/win-browser 필요.)

## TASK-20260703-aiops-ttft-latency — AI 운영 현황 지연 p95 단위 재정의: 호출 전체 왕복 → 단계 간 간격 (Major §12.3 — cross-unit feature-0002 core + feature-0003 web/UI. /_template:entry arg-given dispatch)
<!-- PLAN-APPROVED by mckim on 2026-07-03 (AskUserQuestion 정의 재확정=A 단계 간 간격) -->
- 트리거(사용자): "`관리 콘솔 > AI 운영 현황` 에서 에이전트 추론 p95 측정 단위를 검토 — 지연 기준은 답변 받는 총 시간이 아니라 각 추론이 진행되는 단계 간 나타나는 간격으로 구성되어야."
- 검토 결론: 현행 `latency_ms` = 에이전트 추론 호출 전체 왕복(생성 포함). 실제 라이브 기록 경로는 `agent_core._call_llm`(중앙 래퍼 `_openai_chat_completion_with_deadline` 는 dead — `llm_plan` 호출자 0). 왕복은 답변 길이 비례 → "답변 받는 시간" 쪽. 사용자 기준(단계 간 간격)과 불일치.
- **경로 정정 이력**: 1차 시도는 `_openai_chat_completion_with_deadline`(죽은 코드)를 TTFT 스트리밍 계측 → 적대 패널이 "라이브 경로 미계측·KPI 공백" BLOCKING 적발 → revert. 사용자 재확정 = 정의 **A(단계 간 간격)**, 실제 경로 `_call_llm` + 루프 계측으로 재구현.
- 설계(정의 A — 스트리밍 불요, 저위험):
  1. **[feature-0002] `agent_core._run_agent_core` 루프**: `_prev_llm_end_ns`(직전 라운드 LLM 종료 perf_counter) 추적. 다음 라운드 `_call_llm` 직전 gap = (now − prev_end) 계산해 `step_gap_ms` 로 전달, 호출 성공 후 prev_end 갱신. 첫 라운드/`_call_llm` 예외(→break)는 None.
  2. **[feature-0002] `_call_llm`**: `step_gap_ms` 파라미터 추가 → `_record_llm_usage(step_gap_ms=)` 전달.
  3. **[feature-0002] `_record_llm_usage`**: `step_gap_ms` 파라미터 + 3단 INSERT cascade(target+latency+step_gap → target+latency → latency 자가치유). `latency_ms`(왕복) 보존.
  4. **[feature-0002] 마이그 0033 + 부트스트랩 DDL parity**: `step_gap_ms INTEGER` additive nullable. down_revision=0032. 과거 행 NULL → KPI 자동 제외(cutover 오염 0).
  5. **[feature-0003] ai_ops.py**: KPI query#2(태스크별)·#3(전체) `percentile_cont … latency_ms` → `step_gap_ms`. F2: 다단계 요청 분모(multistep/agent_requests)도 노출(단발 위주 window 빈 tile 오인 방지).
  6. **[feature-0003] admin.js**: KPI "지연 p50/p95" → "단계 간 간격 p50/p95" + 서브 "추론 단계 사이(도구·오케스트레이션) · 다단계 요청 M/R · 간격 N건". per-task "간격 p95". activity 상세 latency_ms 는 "왕복" 라벨로 구분. cache-buster `?v=20260703-aiops-stepgap`.
- Risk: **Major** — 코어 에이전트 루프 계측 추가(additive, best-effort, 예외 무전파). 파괴적/인증/PII 무관. 완화: 적대 2렌즈×2라운드 SHIP + 배포 후 라이브 step_gap_ms 행 검증(F6).
- Completion Checklist:
  - [x] 마이그 0033 step_gap_ms + 부트스트랩 DDL parity (migrate-lint expand-safe).
  - [x] agent_core 루프 gap 추적 + `_call_llm(step_gap_ms=)` + `_record_llm_usage` cascade. py_compile PASS.
  - [x] ai_ops.py query#2/#3 → step_gap_ms + 다단계 분모. admin.js 라벨 + cache-buster. node --check PASS.
  - [x] 테스트: step_gap 기록/omit/음수, `_call_llm` forwarding, cascade 폴백(step_gap/target 부재). make test 1430 passed(회귀 0) + ruff.
  - [x] §18.8 적대 패널 2렌즈×2라운드 → SHIP. REV-20260703T094539-aiops-stepgap.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → 배포(마이그 0033 + web + agent/ask-worker 재빌드, deploy_scope: included) → **라이브 검증(F6): 다라운드 에이전트 구동 → step_gap_ms 행 생성 확인 + KPI "단계 간 간격" 실값 렌더 (PB-0008)**.

## TASK-20260703T085511-ds-avg-latency — 관리 콘솔 > 데이터소스 상세 패널에 평균 연결 응답 시간 표시 (Major §12.3 — feature-0003 web/UI·API + cross-unit shared/conn_health·config, migration 없음. /_template:entry arg-given dispatch)
- 트리거(사용자): "프로젝트 내 서비스의 `관리 콘솔 > 데이터소스` 에서, 각 항목을 선택했을 때 나타나는 상세 정보 패널에 평균적인 연결 응답 시간을 보여주세요."
- 설계(평균의 의미): `shared/conn_health.py` 백그라운드 모니터가 각 데이터소스를 주기적으로 probe(TCP 선검사 + 실제 DB connect + `SELECT 1`)하며 `last_elapsed_ms`(마지막 1회)만 보관하던 것을, **최근 성공 background DB probe elapsed 의 이동평균**(`avg_elapsed_ms`, window=AGENT_CONN_AVG_WINDOW 기본 20)으로 확장. 순간값보다 대표성이 높고, 추가 probe·연결테스트 없이(이미 측정 중인 값 재사용) 상시 표시. 실패 probe·foreground(elapsed 미측정 0.0)는 표본 제외, 느린 성공(unstable)은 응답시간 유효하므로 포함.
- 구성:
  1. **shared/config.py**: `AGENT_CONN_AVG_WINDOW`(기본 20, 1 클램프) 신규 + `__all__` 등록(`from .config import *` export 계약 — 누락 시 NameError).
  2. **shared/conn_health.py**: `_SAMPLES: dict[scope_key→deque(maxlen=window)]`(원시 표본, `_STATE` 와 분리 — 좌표/표본 비노출 불변식) + `_sample_avg_elapsed()`(산술평균, `_LOCK` 안) + `_apply_result` 성공 probe-db 분기에서 표본화 → `avg_elapsed_ms` 갱신 + `snapshot()` 에 `avg_elapsed_ms`/`sample_count` 노출 + `_prune_state`/`_reset_state` 에서 `_SAMPLES` 동기 정리.
  3. **routers/admin_datasources.py**: `/api/admin/datasources` 응답 `conn_status` 에 `avg_elapsed_ms`/`sample_count` additive(좌표 비노출 유지). `_attach_product_conn_status`(제품 경로)는 요청 범위 밖이라 무변경(3키 유지).
  4. **static/admin.js**: `_dsRenderDetail` 상세 패널에 "연결 상태" 섹션 신설 — 상태(`_dsConnStatusLabel`)·**연결 응답 시간(평균)**(`avg_elapsed_ms` + `최근 N회 평균`, 표본 없으면 "측정 중")·최근 응답 시간(순간값)·마지막 확인. cache-buster `admin.js?v=20260703-ds-avg-latency`.
- Completion Checklist:
  - [x] shared/config.py `AGENT_CONN_AVG_WINDOW` + `__all__`. py_compile PASS.
  - [x] shared/conn_health.py 이동평균(deque window·산술평균·표본 게이트·prune/reset 동기). py_compile PASS.
  - [x] routers/admin_datasources.py conn_status avg 필드 additive. py_compile PASS.
  - [x] static/admin.js "연결 상태" 섹션 + `_dsConnStatusLabel` + cache-buster bump. node --check PASS.
  - [x] 단위테스트: test_conn_health.py 갱신(snapshot 키셋) + 신규 5건(평균 누적·window bound·실패/foreground 제외·느린성공 포함·prune 표본정리). feature-0002+0003 전량 회귀 0(컨테이너 전용 test_share_redaction_invariant 제외 — `import web.app` 환경 아티팩트, 본 변경 무관).
  - [x] §18.8 적대 리뷰(백엔드 정확성·스레드안전·좌표 비노출 불변식·회귀) — REV-20260703T085511-ds-avg-latency.
  - [x] verify-completion --pre-commit PASS → commit(b8c386a2) → PR #575 merge(main 7ad4378b) → web 무중단 재배포(deploy_scope: included, web-a/web-b 7ad4378b soak 통과) → **PB-0008 Windows-browser 라이브 실측 PASS**(실 Windows Chrome/149 win-browser relay @ 172.26.144.1:9223, `https://localhost/admin` 로그인 세션): 데이터소스 상세 패널 "연결 상태" 섹션 렌더 + `mssql-dk-dev` **연결 응답 시간(평균) = "11.7 ms · 최근 6회 평균"**·`mssql-qa-idc` "133.4 ms · 최근 6회 평균"(healthy)·down 데이터소스(`mssql-web-qa`/`mssql_local`)는 "측정 중 (연결 성공 시 집계)"(성공 표본 없음, stale 값 미표시). 스크린샷 증적 확보. POST-DEPLOY 문서 기록 = TASK-20260703T085511-ds-avg-latency-postverify.

## TASK-20260702-aiops-conv-link-fix — AI 운영 현황 '최근 활동' 상세: 시스템 sentinel 대화 링크 깨짐 수정 (Minor §12.3 — feature-0003 프론트 단독, 백엔드/스키마/RBAC 무변경. TASK-20260702-audit-nav-ux 후속 — PB-0008 라이브 적발)
- 트리거(PB-0008 라이브 검증): audit-nav-ux 배포 후 실 브라우저 검증에서 발견 — '최근 활동' 행 클릭 시 상세의 '연결 대화' 가 insight/ask 워커·자율 호출(활동 대부분)에도 `/?conversation=__insight_worker__` 같은 **열 수 없는 링크**를 렌더. `__insight_worker__`·`__ask_worker__`·`__global__`·`__kb_manual__` 등은 실제 사용자 대화가 아닌 예약 sentinel(전부 `__` 접두)인데 `conversation_id != NULL` 이라 링크로 처리됨.
- 해법(frontend only): `aiOpsActivityRowsHtml` 에서 `conversation_id` 가 `__` 접두 sentinel 이면 링크 대신 "시스템·자율 호출 (`<sentinel>`) — 특정 대화에 귀속되지 않습니다" 정직 안내. 실제 사용자 대화(비-`__`)만 `/?conversation=<id>` 링크 유지. NULL 은 기존 일반 안내.
- Completion Checklist:
  - [x] `static/admin.js` `aiOpsActivityRowsHtml`: `isSysConv`(cid 가 `__` 접두) 가드 — sentinel=안내(+sentinel 표기), 실대화=링크, NULL=일반 안내. node --check PASS.
  - [x] `static/admin.html` cache-buster `admin.js?v=20260702-aiops-conv-link-fix`.
  - [x] make test 회귀(백엔드 무변경 확인, exit 0) + node --check PASS.
  - [x] §18.8 [SKIPPED:minor-frontend-guard] — REV-20260702T193000-aiops-conv-link-fix.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 재배포(deploy_scope: included) → PB-0008 재검증(sentinel 행=안내·링크 없음, 실대화 행=링크).

## TASK-20260702-audit-nav-ux — 감사 카테고리 순서 재구성 + 항목 툴팁 + AI 운영 현황 '최근 활동' 클릭 상세 확장 (Minor §12.3 — feature-0003 프론트 UI + 읽기전용 additive 백엔드, RBAC/스키마/인가/파괴적 변경 무. /_template:entry arg-given dispatch)
- 트리거(사용자): "`관리 콘솔 > AI 운영 현황` 에서 (1) `감사` 카테고리 순서를 재구성: 감사 로그, 보관 대화, LLM 사용량, AI 운영 현황 (2) 각 항목 mouse hover 시 상세설명 툴팁 (3) 운영 현황 내부 '최근 활동' 클릭 시 상세 내용 확장 — 구조는 `프로필 > 계정 > 사용 내역 > 차트` 및 `관리 콘솔 > LLM 사용량 > 차트` 의 그래프 클릭 → 대화 목록 드릴다운 참조."
- 설계:
  1. **순서 재구성**(Task 1): `admin.html` 감사 그룹에서 `보관 대화`(data-admin-tab=archives) 버튼 블록을 `LLM 사용량`(usage) 앞으로 이동. 권한 게이팅(ADMIN_TAB_PERMISSIONS)·서브탭 로직은 `data-admin-tab` 키 단위 독립이라 DOM 순서 변경만으로 불변(applyAdminTabVisibility 가 그룹 경계를 DOM 순서로 동적 계산).
  2. **툴팁**(Task 2): 감사 그룹 4개 탭 버튼에 네이티브 `title` 속성(상세설명) 추가 — 감사 로그/보관 대화/LLM 사용량/AI 운영 현황. admin.html 기존 `title` 관례(집계 기간·필터 등)와 정합, 접근성·무레이아웃리스크.
  3. **최근 활동 상세 확장**(Task 3): 참조 드릴다운 구조(요약→상세)를 인라인 아코디언으로 구현. 활동 행 클릭 시 하위 상세 패널 확장 — 작업(label+task), 요청→서빙 모델(model→resolved_model), 토큰(프롬프트/완료/합계), 추정 비용, 지연(latency_ms), run_id, **연결 대화**(conversation_id 있으면 `/?conversation=<id>` 새 탭 링크 — showUsageConvModal 대화 open 규약 재사용, 없으면 "시스템/자율 호출 — 특정 대화 미귀속" 안내). 백엔드는 신규 엔드포인트 없이 `_query_activity`(overview activity feed + /api/admin/ai-ops/activity 페이징 공용 헬퍼) SELECT/dict 에 `resolved_model·prompt_tokens·completion_tokens·run_id·conversation_id` **additive** 노출 → 페이징 append 도 자동 상속.
- Completion Checklist:
  - [x] `static/admin.html`: 감사 그룹 archives↔usage 순서 재배치 + 4개 탭 `title` 툴팁 + admin.js cache-buster bump(`?v=20260702-audit-nav-ux`).
  - [x] `routers/ai_ops.py` `_query_activity`: SELECT 컬럼 확장(model, resolved_model, run_id, conversation_id) + dict additive 필드(req_model/resolved_model/prompt_tokens/completion_tokens/run_id/conversation_id). 기존 필드(id/task/category/label/model(served)/total_tokens/cost_usd/latency_ms/created_at) byte-동치 보존.
  - [x] `static/admin.js` `aiOpsActivityRowsHtml`: 클릭 요약 행(role=button/tabindex/aria-expanded/caret) + 하위 숨김 상세 패널 + `_toggleAiOpsActRow`/`bindAiOpsActivityToggle`. `renderAiOps` 에 aiOpsActivityList 위임 click/keydown 토글 배선(페이징 append 상속).
  - [x] `tests/test_ai_ops.py`: `_act_rows` 11열 tuple + 신규 필드 assert(req_model/resolved_model/prompt/completion/run_id/conversation_id, served 우선순위, conv 유/무 경로). test_ai_ops.py 15/15 + make test exit 0(feature-0002+0003 전량, ruff PASS).
  - [x] py_compile(ai_ops.py) + node --check(admin.js) 구문 검증 PASS.
  - [x] §18.8 적대 패널(3-렌즈) VERDICT SHIP(BLOCKING/MAJOR/MINOR 0, NIT 3 비차단) → REV-20260702T190000-audit-nav-ux.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 라이브 실측(순서·툴팁·활동 클릭 상세 확장·대화 링크).

## TASK-20260702-aiops-activity-paging — AI 운영 현황 '최근 활동' 과거 기록 페이징 + main agent latency 계측 (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002 core)
- 트리거(사용자): "'최근 활동'을 페이징하여 과거기록도 조회할 수 있도록 구성해주세요." + "이전 작업에서 확인했던 남은 발견 사항도 진행" (finding #1 agent_core latency).
- 구성:
  1. **활동 페이징**(feature-0003): 기존 최근 활동 feed 는 최근 30건만 표시 → cursor(id) keyset 페이징 추가. 신규 `GET /api/admin/ai-ops/activity?cursor=<id>&limit=<1~100>`(console.aiops.read) 가 `WHERE id < cursor ORDER BY id DESC LIMIT n+1` 로 더 오래된 활동 조회(OFFSET 아닌 안정 keyset). overview 는 최신 페이지 + `activity_next_cursor` 반환. 프론트 '더 보기' 버튼이 append.
  2. **agent_core latency**(finding #1, feature-0002): main agent 경로(`agent_core._call_llm`, task='agent')는 LLM 볼륨 최대인데 중앙 래퍼를 안 거쳐 latency 가 비어 있던 gap 보완 — create 직후 latency_ms 를 `_record_llm_usage` 에 함께 전달(래퍼 경로와 동일 순수 왕복 규약, best-effort try/except).
  3. **finding #3**: 스크롤 PB-0008 라이브 PASS 결과를 TEST.md 에 기록. (finding #2 datasource circuit_open 은 환경 이슈 — 코드 무관, 미대상.)
- Completion Checklist:
  - [x] `routers/ai_ops.py`: `_query_activity`(cursor keyset 헬퍼, id DESC) + 신규 `/api/admin/ai-ops/activity` 엔드포인트(권한·부분 degrade) + overview `activity_next_cursor`.
  - [x] `agent_core.py`: `_call_llm` create 직전 perf_counter → `_record_llm_usage(latency_ms=...)`. (cross-unit feature-0002)
  - [x] `static/admin.js`: `aiOpsActivityRowsHtml`(공용 esc row) + `loadAiOpsMoreActivity`(cursor append) + renderAiOps '더 보기' 버튼 + 배선. `static/admin.html`: cache-buster `admin.js?v=20260702-aiops-activity-paging`.
  - [x] 단위테스트 `test_ai_ops.py` 15/15(신규 5: _query_activity cursor/next_cursor·엔드포인트 degrade·권한 403). 회귀 66 PASS. route-parity 골든 **194→195**(신규 activity 라우트). node --check(admin.js). py_compile 전체.
  - [x] §18.8 적대 패널(2-렌즈 AGENT-TEAM: backend BLOCKING 0/NIT 4 + frontend BLOCKING 1 흡수/NIT 2) → REV-20260702T180000-aiops-activity-paging.
  - [ ] PB-0008 Windows-browser: '더 보기' 클릭 → 과거 활동 append 실측 + agent latency 기록 확인 — 배포 후.
  - [ ] verify-completion PASS → commit → PR/merge → web 재배포(deploy_scope: included) → PB-0008.

## TASK-20260702-aiops-scroll — AI 운영 현황 pane 세로 스크롤 구성 (Minor §12.3 — feature-0003 프론트 CSS 단독, RBAC/스키마/백엔드/엔드포인트 무변경)
- 트리거(사용자): "내용이 화면 너머까지 출력되고 있지만 해당 화면을 볼 방법이 없습니다 — 화면 내 세로 스크롤을 구성해주세요." AI 운영 현황 패널(배너+축+KPI+Attention+카테고리표 13행+활동feed+커버리지)이 길어 admin-shell(overflow:hidden+100vh) 뷰포트 아래로 넘치는데 pane 에 세로 스크롤이 없어 하단(카테고리표·커버리지)에 도달 불가. PB-0008 스크린샷에서도 커버리지 잘림 관측.
- 근본원인: `styles.css` 의 pane 세로 스크롤 규칙(TASK-0167 — dashboard/usage/release-notes 처럼 list-detail 아닌 단순 세로 흐름 pane 에 `overflow-y:auto`)에 `ai-ops` pane 이 누락. (다른 pane 은 내부 admin-list 가 스크롤하거나 이 규칙에 포함돼 있어 정상.)
- Completion Checklist:
  - [x] `static/styles.css`: pane 세로 스크롤 셀렉터에 `.admin-pane[data-admin-pane="ai-ops"].is-active` 추가(dashboard/usage 와 동일 `overflow-y:auto; overflow-x:hidden`). brace balanced.
  - [x] `static/admin.html`: cache-buster `styles.css?v=20260702-aiops-scroll` bump(CSS 실변경).
  - [x] §18.8 패널 [SKIPPED:minor-css-scroll] — 2줄 CSS 셀렉터 추가(신규 로직 0, 기존 검증된 규칙에 pane 편입), 라이브 PB-0008 이 정본. REV-20260702T170000-aiops-scroll.
  - [ ] PB-0008 Windows-browser 실측(패널 세로 스크롤 동작 + 하단 커버리지 도달) — 배포 후 라이브.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 재배포(deploy_scope: included) → 배포 후 스크롤 실측.

## TASK-20260702-metadata-perm-hier — 메타데이터(지식베이스) 권한 종속관계 정합화 (Major §12.3 — feature-0003 프론트 단독, RBAC enforcement/스키마/백엔드/엔드포인트 무변경 · UI 표시 계층만)
- 트리거(사용자): "다른 권한 구성과 같이 종속적인 관계가 정합하도록 구성. `지식베이스 > 메타데이터` 권한이 다른 권한 포맷과 차이 확인."
- 진단: `admin.js` `PERMISSION_DEPENDENCIES`(UI progressive-disclosure 표시 계층, enforcement 아님)에서 다른 관리 그룹은 "그룹 게이트(read)→세부(manage)" 2단 계층인데 메타데이터(kb)만 평면(5개 metadata.* 전부 console.access 직속 + 묶음 kb.ingest.manual 은 맵 부재 고아). → kb 그룹만 flat 나열.
- 해법(B안 유지): 묶음 `kb.ingest.manual`을 그룹 게이트로 삼아 정합화. `kb.ingest.manual→console.access`, 세부 5개 `metadata.*→kb.ingest.manual`. 백엔드 함의(_METADATA_MANUAL_IMPLIES)와 의미 정합. enforcement 무변경.
- Completion Checklist:
  - [x] `static/admin.js` `PERMISSION_DEPENDENCIES` 정합화(kb.ingest.manual 게이트화 + metadata.* nest). `node --check` PASS.
  - [x] §18.8 NIT-1 흡수: `isGrantedForReach`(explicit + override 상속-부여)로 override 도달성 cue 회귀 복원. checkbox 모드 무영향.
  - [x] `static/admin.html` cache-buster `admin.js?v=20260702-metadata-perm-hier` bump.
  - [x] `tests/test_permission_dependency_map.py` t5(계층 pin)/t6(도달성) 추가 — 18개 전부 PASS.
  - [x] §18.8 SUBAGENT 적대 패널 VERDICT PASS(BLOCKING 0 — 개별부여·은닉·enforcement·implies 4축 refute + NIT 2 흡수). REV-20260702T010000-metadata-perm-hier.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 배포(deploy_scope: included) → 배포 후 라이브 그리드 2단 계층 실측.
## TASK-20260702-aiops-panel — AI 운영 관제 패널 (관리 콘솔 > 감사 > AI 운영 현황) + LLM 계측 확장 (Major §12.3 — feature-0003 web/UI + 인가, cross-unit feature-0002 core/alembic + shared. /_template:resume 재개, PLAN-APPROVED)
- 트리거(사용자, 원 세션 /_template:entry → /_template:resume 재개): "프로젝트 내부에서 동작 중인 AI 현황을 모니터링할 관제패널을 `관리 콘솔 > 감사 > (적절한 명칭)` 에 구성. insight-worker·요청수행 LLM·자동분석 LLM·메타데이터 능동분석 LLM 등 각 동작 카테고리를 세분화하고, 이후 추가될 기능에 확장성 있게." 4개 제품결정 확정: 배치=감사 그룹 유지(명칭 'AI 운영 현황') · v1 범위=**+계측 지금 포함** · 대시보드 KPI 타일 추가 · 권한=console.aiops.read admin 전용.
- 설계 근거: 14-에이전트 계획 + Workflow(ground 4 → design 3 판정 → 적대검증 6축 28-fix) grounding. 계측 범위 현실: chat 4경로만 계측 가능(임베딩 3경로·provider probe 는 embeddings/ping 응답에 usage 부재 → 구조적 계측 불가, '계측 커버리지'로 정직 노출). cost 는 단가표가 web app.py 전용이라 read-time 계산 유지(DB 컬럼 미추가), latency_ms 만 additive 컬럼.
- Completion Checklist:
  - [x] 마이그 `alembic/versions/20260702_0030_llm_usage_latency.py`: PG `agent_runtime.llm_usage` 에 `latency_ms INTEGER`(nullable, DEFAULT 없음=미측정 NULL) `ADD COLUMN IF NOT EXISTS`. `agent_runtime_schema.sql` bootstrap parity 반영. (cross-unit feature-0002)
  - [x] 계측 헬퍼 `modules/llm.py` `_record_llm_usage`: `latency_ms` 인자 + INSERT 컬럼 추가(agent-core 11경로 미전달=NULL byte-동치). 중앙 래퍼 `_openai_chat_completion_with_deadline` 순수 API 왕복 latency 측정. (cross-unit feature-0002)
  - [x] taxonomy 레지스트리 `shared/model_catalog.py`: `TASK_TAXONOMY`+`taxonomy_for()`+`ai_categories()` — 미등록 task self-surface(ai.other.unmapped). (cross-unit shared)
  - [x] web 4경로 계측 배선(app.py): 프롬프트 자동생성 비스트리밍(executor 람다 내부)·스트리밍(include_usage + choices 가드 앞 usage 선포착 + SENTINEL 1회)·자율 sweep(daemon thread, conv_id=None)·메타데이터 자동완성(executor 람다 내부, metadata_ 접두 task). 이벤트 루프 무블로킹.
  - [x] 권한 `console.aiops.read` 5곳 동시 sync: PERMISSION_DEFINITIONS + admin catchup(lockout 방지) + admin.js PERMISSION_DEPENDENCIES + ADMIN_TAB_PERMISSIONS(fail-open 방지 필수) + test v2 리스트.
  - [x] 라우터 `routers/ai_ops.py` GET `/api/admin/ai-ops`(console.aiops.read): 상태 축(provider/ask-worker/insight-worker/datasource) worst-of 배너 + inprocess N/A 롤업 제외 + KPI + Attention + 카테고리 드릴다운 + 활동 feed + 커버리지. PG 부분 degrade(200 유지, `_pg_connect_ro` least-priv). app.py include_router + `_ask_worker_age_sec` 헬퍼(3-state).
  - [x] 대시보드 KPI 타일: `_DASHBOARD_WIDGETS` ai_ops + `_dash_widget_ai_ops`(tab='ai-ops' deep-link) + admin_console `_isolate` dispatch.
  - [x] 프론트: admin.html 감사 그룹 탭 `data-admin-tab="ai-ops"` + pane + cache-buster(css/js `?v=20260702-ai-ops`). admin.js adminState.aiOps + switchTab lazy-load + loadAiOps/renderAiOps(배너·KPI·Attention·카테고리·활동·커버리지) + 새로고침 배선.
  - [x] 단위테스트 `tests/test_ai_ops.py` **10/10 PASS**(taxonomy self-surface·ask-worker age 밴드·datasource worst-of·inprocess N/A·PG degrade 200·PG empty·권한 403·latency NULL byte-동치·usage 스킵). 회귀 permission 16/dashboard 20/usage 28 PASS, 전체 collection 무오류.
  - [x] §18.8 적대 검증 패널(구현 diff, 3-렌즈 AGENT-TEAM) **BLOCKING 0** → REV-20260702T140000-aiops-panel. NIT 3 반영·2 수용.
  - [ ] PB-0008 Windows-browser 실측(패널 렌더 + 타일 deep-link + 탭 권한 게이팅) + TEST.md Windows Run — 배포 후 라이브(win-browser 브리지 doctor OK).
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 재배포(deploy_scope: included, 마이그 0030 자동적용) → healthz/smoke.

## TASK-20260701T100738-convswitch-opacity-guard — 좌측 대화 선택 시 대화창 미표시 방어 하드닝 (Minor §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경)
- 트리거(사용자 /_template:entry, 유저 admin): "작업 화면(메인 채팅)에서 좌측 대화 항목을 선택해도 대화창에 내용이 안 뜬다 — 선택이 아예 안 먹는 것처럼". 조사: 현재 배포본(b3175b6) 백엔드·프론트 모두 재현 안 됨(curl `/api/use_conversation`·`/api/history` 200+메시지, fresh 브라우저에서 admin 과 동일 role id3 계정 headless 10대화·race·PB-0008 Windows 정상, 캐시버스터 정합) → stale client(캐시된 구버전 app.js / 장시간 열어둔 탭) 유력. 사용자 결정: 재발 불가하도록 방어 하드닝 배포.
- 근본 취약점: `static/app.js` `selectConversation` conv-switch-fade 의 begin(opacity:0)↔commit(opacity:1) 사이 risk window(pendingNewConversation 리셋·pending 스냅샷·`stopProgressPolling`)가 try 밖 → 예외 시 opacity:0 잔류로 대화창 빈 화면 가능.
- Completion Checklist:
  - [x] `static/app.js`: risk window 를 try 안으로 + 성공/catch 중복 commit 을 단일 `finally` 로 이관(에러 전파·post-processing·렌더 순서 보존). `node --check` PASS.
  - [x] `static/index.html`: cache-buster `app.js?v=20260701-convswitch-opacity-guard` bump(stale 사용자에게 새 코드 강제).
  - [x] §18.8 적대 코드리뷰(SUBAGENT adversarial-correctness) VERDICT PASS(commit 보장·에러 전파·scoping·post-processing·double-commit 불가·reduced-motion 대칭 6점). REV-20260701T100738-convswitch-opacity-guard.
  - [x] PB-0008 **Windows-browser 실측**(프리뷰 인젝션 web-a/web-b): 대화 A op1·msg4 렌더·제목 갱신, A→B 전환 렌더, 스크린샷. + headless browse 5대화 전부 op1.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 배포(deploy_scope: included) → 배포 후 최종 확인.

## TASK-20260701T220000-graphview-webgl-labels — 스키마 클러스터명 오버레이 WebGL 렌더러 호환 수정 (Minor §12.3 — feature-0003 프론트 단독, graphview-render 후속)
- 트리거: `graphview-render`(§18 클러스터명 오버레이) 를 최신 main 에 병합하니, 병렬 머지된 **graph-webgl(§17, Cytoscape 3.30.2→3.34.0 + WebGL 렌더러)** 과 결합됐다. 배포 전 병합 번들 PB-0008 프리뷰 검증에서 **클러스터명 오버레이 미표시(labelDivs=0)** 발견.
- 근본원인(실측): 오버레이 위치 동기화가 `cy.on("render", …)` 에 바인딩됐는데, **WebGL 렌더러(cytoscape 3.31+ `webgl:true`)는 `render` 이벤트를 emit 하지 않는다**(실측 renderFires=0, canvas-2D 에선 fire). → 초기 로드·pan/zoom 시 sync 미호출 → 라벨 div 미생성/미추종. (`_metaGraphSyncClusterLabels` 함수 자체·`renderedBoundingBox` 는 WebGL 에서 정상 — 수동 호출 시 35 divs 정상 생성 확인.)
- 수정(admin.js): `render` 단일 바인딩 → **렌더러 무관 코어 이벤트**로 교체 — `cy.on("render viewport resize layoutstop add remove", sync)` + `cy.on("position drag free", "node", sync)`. viewport=pan+zoom(카메라 애니 per-frame), position/drag=노드 이동·레이아웃 애니 per-frame. `render` 도 포함해 canvas-2D 폴백(webgl 미지원 GPU) 호환 유지. rAF 스로틀 불변.
- Completion Checklist:
  - [x] admin.js: `_lblSync` 헬퍼 + 코어 이벤트 바인딩 교체. `node --check` PASS.
  - [x] admin.html: cache-buster 2건 bump `admin.js`·`styles.css?v=20260701-graphview-webgl-labels`(js==css lockstep).
  - [x] PB-0008 **Windows-browser 라이브 실측**(병합 번들 프리뷰, cytoscape 3.34.0 `webgl:true` 확인): 로드 시 오버레이 labelDivs=35 생성 · pan +120/+60 정확 추종(tracked) · 클러스터 tap 상세('테이블 130개') · 좌상단 좌정렬 무잘림 — 전부 WebGL 하 PASS.
  - [x] §18.8 패널: [SKIPPED:minor-scoped-fix] — 2줄 이벤트-바인딩 교체, 신규 로직 경로 0, 라이브 실측이 정본. REV-20260701T220000-graphview-webgl-labels.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 배포(deploy_scope: included — graph-webgl WebGL 과 동시 첫 배포) → 배포 후 최종 확인.
- Next Action: verify-completion → cycle-final → 배포.

## TASK-20260701T163000-graphview-render — 관리콘솔 메타데이터 그래프 뷰 출력 이슈 3건(마커 렌더-타임 갱신·클러스터 선택 상세·클러스터명 잘림) (Major §12.3 — feature-0003 프론트 + feature-0002 백엔드 cross-cut)
- 트리거: 사용자(`/_template:entry` arg-given) — "관리 콘솔 > 메타데이터 > 그래프 뷰 출력 이슈: ①각 노드 표식(AI 분석 중/분석됨)이 직접 클릭했을 때만 갱신 → 화면 출력 당시에도 렌더. ②DB(스키마 클러스터) 선택 시에도 상세 갱신. ③스키마 클러스터 명칭 잘림 → 좌정렬·좌여백(둥근 사각형 존중)·무잘림 확장."
- 근본원인(코드 근거):
  - ①: `_metaGraph.analyzed`/`running` 세트가 **세션 로컬**(현재 세션 폴 run 에서만 채워짐). `_metaGraphLoadRoots`/검색/확장은 DB 영속 분석상태를 조회하지 않아, 새로고침·재진입 시 노드를 개별 클릭(`_metaGraphLoadNodeAnalysis`)하기 전까지 마커 미표시. scope 단위 일괄 상태 조회 API 부재.
  - ②: tap 핸들러가 `if (t.isParent()) return` 으로 compound 컨테이너(스키마 클러스터) 클릭을 완전히 무시 → 상세 패널 미갱신.
  - ③: `node:parent` 스타일이 `node` 선택자의 `text-max-width:120px` + `text-wrap:ellipsis` 를 상속 + 중앙정렬 → 클러스터명이 120px 에서 ellipsis 로 잘림. cytoscape native 라벨은 가변폭에서 좌정렬·무잘림·좌여백을 동시에 보장 못 함.
- 설계:
  1. **백엔드(feature-0002 `node_analysis.py`)**: `get_scope_analysis_status(scope_key, node_keys=None)` — `node_analysis_jobs` 를 node_key 로 group_by 하여 `{done_keys, running_keys}`(bool_or 집계) 반환. **엔드포인트(feature-0003 `admin_metadata.py`)**: `GET /api/admin/metadata/graph/analyze/status?scope=` (권한 kb.ingest.manual, PG 미가용 시 빈 집합 graceful).
  2. **프론트 ①(admin.js)**: `_metaGraphSyncAnalysisMarkers(scope)` — 로드/검색/확장 직후 일괄 상태 조회 → `_metaGraphMarkAnalyzed`(보라)·aiRunning(주황) **additive** 적용(활성 폴 running set 미clobber). 404/실패 시 graceful skip.
  3. **프론트 ②(admin.js)**: tap 핸들러에서 스키마 클러스터(`label==='Schema'||isCat`) 클릭 시 `_metaGraphShowClusterDetail`(스키마명·포함 테이블 목록·개수 렌더, depth=1 HAS_TABLE 수집). Table ERD-카드 parent 는 일반 노드 상세/확장 경로로 흘려보냄(부수 개선).
  4. **프론트 ③(admin.js+css)**: 스키마 클러스터명을 캔버스 위 HTML 오버레이(`_metaGraphEnsureLabelLayer`/`_metaGraphSyncClusterLabels`, render 이벤트 rAF 동기화)로 렌더 — 박스 좌상단 + 좌여백 10px·상단 4px, `nowrap`·max-width 없음(무잘림·확장), zoom 따라 폰트 10~16px 클램프. native 스키마 라벨은 `node:parent[isCat=1]` 스타일 `label:""` 로 숨김. 클러스터는 스코프당 소수(≤수십)라 DOM 동기화 비용 무시 가능.
- Completion Checklist:
  - [x] 백엔드: `node_analysis.get_scope_analysis_status` + `GET .../graph/analyze/status` 엔드포인트. `py_compile` PASS.
  - [x] 프론트: `_metaGraphSyncAnalysisMarkers`(로드/검색/확장 3경로 wiring)·`_metaGraphShowClusterDetail`/`_metaGraphRenderClusterDetail`·`_metaGraphEnsureLabelLayer`/`_metaGraphSyncClusterLabels` + tap 핸들러 클러스터 분기 + `node:parent[isCat=1]` label 숨김. `node --check admin.js` PASS.
  - [x] admin.html cache-buster 2건 bump → `admin.js`·`styles.css?v=20260701-graphview-render`(js==css lockstep).
  - [x] PB-0008 **Windows-browser 라이브 실측**(프리뷰 인젝션 web-a/web-b, https://localhost/admin, mssql-qa-idc/250노드·클러스터 50): ②클러스터 클릭→상세 '테이블(58)' 렌더 PASS · ③클러스터명 좌상단(box+10/+4px)·좌정렬·무잘림(scrollWidth==clientWidth)·zoom 재배치/폰트 스케일 PASS. ①백엔드 집계 쿼리 실 KB PG 정합(scope done 335·active 183·`accountdb`/`GMRIP` done=t) + 프론트 배선·404 graceful 확인 — **마커 렌더 최종 확인은 실배포(백엔드 baked) 후**.
  - [x] §18.8 적대 코드리뷰 패널(correctness) — REV-20260701T163000-graphview-render.
  - [ ] verify-completion --pre-commit PASS → commit → PR/merge → web 재빌드·재배포(deploy_scope: included — 백엔드 포함이라 web 이미지 재빌드) → 배포 후 PB-0008 ①마커 렌더 최종 확인.
- Next Action: verify-completion → cycle-final → 배포 → 배포 후 ①마커 실측.

## TASK-20260630T174000-metadata-bs-prefill — 스키마 골격 가져오기 시 기존 저장된 테이블/컬럼 설명 prefill (Minor §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경, 비파괴)
- 트리거: 사용자 — "관리콘솔 > 메타데이터 > 테이블 설명, 컬럼 설명 에서 스키마 골격을 가져왔을 때, 기존에 입력된 정보가 확인되지 않아 수정 필요."
- 근본원인(코드 근거): 백엔드 `/api/admin/metadata/bootstrap`(app.py `admin_bootstrap`)은 **설계상 의도적으로 골격(테이블/컬럼 이름·타입)만** 반환하고 설명은 미영속(주석: "UI 가 설명 빈칸을 prefill"). 그러나 프론트 `_metaBootstrapRenderResult`(admin.js)가 입력란 생성 시 `adminState.metadata.items`(loadMetadata 가 현재 scope·서브탭 기준 적재한 저장 설명)와 매칭해 `inp.value` 를 채우는 **prefill 로직이 누락** → 골격을 가져오면 항상 빈칸으로 표시됨. (최근 metadata-bs-inline-desc/list-detail/paging 리팩터와 무관 — 애초 prefill 미구현.)
- 부수 회귀 차단: prefill 만 추가하면 `_metaBootstrapSave` 가 비어있지 않은 모든 행을 `source:"bootstrap"` 으로 재저장 → 기존 `source:"manual"` 설명까지 덮어쓰는 provenance 오염 발생. 따라서 prefill + **변경분만 저장**(dataset.original 비교)을 한 묶음으로 처리.
- 설계(frontend only, admin.js):
  1. `_metaBootstrapRenderResult`: `adminState.metadata.items` 를 `(schema,table[,column])`(JSON.stringify 키)로 색인한 `_descByKey` 구축 → 테이블/컬럼 입력란에 `inp.value` prefill + `inp.dataset.original` 원본 기록.
  2. `loadMetadata`: items 갱신 후 부트스트랩 모드(골격 존재)면 `_metaBootstrapRenderResult` 재호출 → 스코프/서브탭 전환·저장 후에도 prefill 정합.
  3. `_metaBootstrapSave`: `desc && desc !== dataset.original` 인 행만 POST(미변경 prefill 재저장 안 함 → source 보존). post-save 는 loadMetadata 재렌더로 저장분+기존 재표시(dataset.original 최신화 → 중복 저장 차단). 빈칸 비우기 루프 폐기.
  4. AI 일괄생성(`_metaBootstrapApplyDescriptions`)은 빈 입력란만 채우므로 prefill 보존 — 정합.
  5. save-info 안내문 갱신("기존 설명은 채워져 표시 / 변경·추가한 행만 저장").
- Completion Checklist:
  - [x] admin.js: 색인/조회 헬퍼(`_metaBootstrapBuildDescIndex`/`_metaBootstrapDescLookup`, schema 소문자+빈-schema 폴백=read 경로 정합) + `_metaBootstrapRenderResult` prefill·`dataset.original` + in-place 갱신 `_metaBootstrapRefreshPrefill`(검색/페이지/펼침 보존) + `loadMetadata` 재prefill + `_metaBootstrapSave` 변경분만 저장 + 안내문 갱신.
  - [x] admin.html: cache-buster lockstep 동반 bump `admin.js`·`styles.css?v=…20260630-metadata-bs-prefill`(js==css 불변식 — 정적 자산 전파 누락 방지 가드).
  - [x] §18.8 적대 frontend 패널(8-가설) → FIX-THEN-SHIP(BLOCKER 0·MAJOR 1·MINOR 2) → MAJOR-H2(post-save 전체 재렌더가 검색/페이지/펼침 리셋)·MINOR-H3(prefill 키 정확매치라 케이스/빈-schema 비대칭 누락) 수정 → 재검 SHIP. MINOR-H6(prefill 후 비움=삭제 불가) pre-existing 수용. REV-20260630T174000-metadata-bs-prefill.
  - [x] 회귀 가드 `tests/verify_metadata_bs_prefill.mjs`(44: 케이스 무관·빈-schema 폴백·정확 우선·dataset.original·in-place 검색보존·변경분만 저장·키 충돌 회피) green. 인접 inline-desc(30)·list-detail(33)·paging(32)·scope-single-ds(15) 회귀 0.
  - [x] `node --check` PASS · admin.js NUL 바이트 0 확인.
  - [ ] verify-completion --pre-commit PASS → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows 브라우저 시각검증(골격 가져오기 시 기존 테이블/컬럼 설명 prefill 표시·미변경 시 저장 0·수정행만 저장·source 보존·저장 후 검색/페이지 위치 보존).
- Next Action: verify-completion → cycle-final → 배포 → PB-0008 시각검증.

## TASK-20260630T160000-metadata-list-detail — 메타데이터 패널 list-detail 2단 재구성(좌측 목록 선택 → 우측 상세 편집) (Major §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경)
- 트리거: 사용자 — "메타데이터 UI 를 다른 카테고리처럼 한 항목 선택 후 우측 상세조정 형태로 재구성. 위/아래 스크롤이 잦다." 참조: 계정/역할·제품/데이터소스·감사로그/보관대화.
- 현황 파악(코드 근거): 메타데이터 pane 은 단일 컬럼 수직 스택(헤더→서브탭→부트스트랩→폼→목록). 행 '수정' 버튼이 `_metaStartEdit`→목록 **위**의 폼으로 `scrollIntoView({behavior:'smooth'})` 점프 → 위/아래 스크롤 마찰의 정체. 다른 카테고리는 `.admin-list-detail`(grid 2단: 좌측 .admin-list-col + 우측 .admin-detail-col, 각자 overflow-y:auto).
- 결정(사용자 Q&A): list-detail 채택. 부트스트랩 '스키마 골격 가져오기'(단일 항목 모델에 1:1 없음)=**우측 상세 모드**(좌측 툴바 버튼 진입). 거버넌스 안내문=우측 empty-state 로 이동(상단 압축).
- 설계: `detailMode(empty|form|bootstrap)` + `selectedId` + `search` 상태. 코디네이터 `_metaRenderDetail` 가 모드 유효성 보정 후 세 컨테이너 배타 가시성 결정. 행 클릭=선택→form. 기존 폼/목록/부트스트랩 렌더 함수 재사용(위치만 이동). 백엔드 무변경.
- Completion Checklist:
  - [x] admin.html: 메타데이터 pane 2단 list-detail 화. 좌측 검색/카운트/목록, 우측 empty-state/폼/부트스트랩. '+ 새 항목'·'스키마 골격 가져오기' 버튼. cache-buster bump.
  - [x] admin.js: detailMode/selectedId/search + `_metaRenderDetail`/`_metaSyncListActive`/`_metaSyncListToolbar`/`_metaItemMatchesSearch`. 행 클릭 선택(role=button·keydown target 게이트)·'수정'버튼·scrollIntoView 폐기·삭제/유사어 stopPropagation. 핸들러/init/submit/delete 코디네이터 경유.
  - [x] styles.css: pane 단일 스크롤 제외, 폼 카드 chrome 제거, 행 선택 스타일, 안내문/bs-open 활성.
  - [x] 회귀 가드 `verify_metadata_list_detail.mjs`(33) + scope-single-ds(15)·inline-desc(30)·paging(32) green. `node --check` PASS.
  - [x] §18.8 적대 frontend state-machine 패널(7가설) → SHIP(BLOCKING 0). MAJOR-2(keydown 이중발화) 수정+잠금, MAJOR-1(검색-편집 desync) 편집보존 의도 수용, NIT-1 정리. REV-20260630T160000-metadata-list-detail.
  - [ ] verify-completion → rebase onto origin/main(base drift 6) → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows 브라우저 시각검증(좌우 2단·행 선택→우측 편집·컬럼 독립 스크롤·스크롤 점프 해소·부트스트랩 우측 모드).
- Next Action: verify-completion → rebase → cycle-final → 배포 → PB-0008.

## TASK-20260630T110910-metadata-ds-single-ui — 메타데이터 패널 '데이터소스' 선택 UI 단일화(헤더 스코프 상속) + 공용 스코프 empty-state (Major §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경)
- 트리거: 사용자 — "관리 콘솔 > 메타데이터 > 테이블/컬럼 설명 구조에서 '데이터소스' UI 가 '스키마 골격 가져오기' 기능과 메타데이터 패널 자체에 동시에 있어 혼란. 각 UI 역할 파악 후 단일 UI 만 쓰도록 정리."
- 현황 파악(코드 근거): 데이터소스 selector 가 둘 — (1) 패널 헤더 `#metadataScopeSelect`("데이터소스") = 메타데이터 저장/조회 **스코프**(5서브탭 전체, 저장 target `_metaBootstrapSave`→scopeKey), (2) "스키마 골격 가져오기" 내부 `#metadataBootstrapDs`("데이터소스 *") = 스키마 introspection **소스**(테이블/컬럼 서브탭만). 둘은 완전 독립 → 헤더 스코프=A·부트스트랩 DS=B 로 어긋나게 고르면 "B 골격을 A 스코프로 저장"하는 조용한 불일치(footgun).
- 결정(사용자 2-step Q&A): 비활성 잔재·더미 selector 금지(디자인 부적합) → **중복 근원 제거** = 부트스트랩 전용 DS selector 폐기, 데이터소스는 헤더 스코프 상속. 공용(common)은 실제 스키마 없어 부트스트랩 불가 → 관리 콘솔 list-detail `.admin-detail-empty` 컨벤션 정합 **empty-state** 안내.
- 설계: `_metaScopeDatasourceKey()`(기존 스코프→DS 해소)를 부트스트랩 소스로 재사용. `_metaSyncBootstrapVisibility` 가 구체 DS 스코프=골격 컨트롤(토글+본문) 노출 + DS 상속, 공용/미매칭=empty-state 만 노출. 백엔드 무변경(POST /bootstrap {datasource,schema} 의 datasource 가 스코프에서 옴).
- Completion Checklist:
  - [x] admin.html: `#metadataBootstrapDs` label/select 제거 + `#metadataBootstrapEmpty`(.admin-detail-empty) + `#metadataBootstrapHead` + 노트에 `#metadataBootstrapDsName` 상속 DS 표기.
  - [x] admin.js: `_metaBootstrapPopulateDs`(드롭다운) → `_metaBootstrapSyncToScopeDs`(스코프 상속·DS 변경 시 골격/스키마 리셋·재로드) 교체. `_metaSyncBootstrapVisibility` 공용/구체 DS 분기. `_metaBindBootstrap` DS 바인딩 제거. 스코프 change 핸들러가 `_metaSyncBootstrapVisibility` 호출.
  - [x] styles.css: `.admin-meta-bootstrap-empty`(list-detail empty-state 정합) 보강. cache-buster admin.js·styles.css 동반 bump `20260630-metadata-ds-single-ui`.
  - [x] 회귀 가드 `tests/verify_metadata_scope_single_ds.mjs`(14 단언) + 기존 inline-desc(30: B1 수정+B4-common)·paging(32) 회귀 0. `node --check` PASS.
  - [x] §18.8 적대 frontend state-machine 패널(7가설) → 1차 FIX-THEN-SHIP(BLOCKING 1=깨진 회귀 테스트 B1) → 수정·재검증 → SHIP. N1(스키마 로드 stale-response 가드) 추가. REV-20260630T110910-metadata-ds-single-ui.
  - [ ] verify-completion --pre-commit PASS → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows 브라우저 시각검증(공용=empty-state, 구체 DS=골격 컨트롤·DS 상속 노트, 스코프 전환 시 골격 리셋·중복 selector 부재).
- Next Action: verify-completion → cycle-final → 배포 → PB-0008 시각검증.

## TASK-20260629T181648-point-scroll-easeoutexpo — 공유 대화 뷰 우측 스크롤바 대화 가이드 뱃지(point rail) 추가 + 가이드 뱃지 클릭 스크롤 단축(280ms)·EaseOutExpo (Minor §12.3 — frontend 표현계층, RBAC/스키마/백엔드 무변경, anonymous 공유 노출면)
- 트리거: 사용자 — "공유 기능을 통해 전달한 대화도, 우측 스크롤바에 각 대화 구간에 대한 가이드 뱃지 UI를 구성. 추가로 가이드 뱃지 클릭 시 소요 시간을 지금보다 짧게 + Easing 을 EaseOutExpo 로."
- 현황: 메인 UI(index.html+app.js)에는 우측 point rail(`renderMessagePointRail`, `#messagePointRail`, `.message-point-dot`)이 이미 존재하나 클릭은 native `scrollIntoView(behavior:smooth)`(가변·통상 ≥400ms). 공유 뷰(share.*)에는 rail 자체가 없었음.
- 설계: 메인=#messageLog 내부 스크롤(기존 flex rail 보존, 클릭만 EaseOutExpo `scrollTop` 보간으로 교체). 공유=window 스크롤이라 rail 은 position:fixed 미니맵 신규(dot top%=문서좌표 비율, 클릭=`window.scrollTo` EaseOutExpo). duration 280ms, easing `1-2^(-10t)`.
- Completion Checklist:
  - [x] app.js: rail dot 클릭 native scrollIntoView → `scrollMessagePointIntoCenter`(`_animatePointScroll`+`_easeOutExpo`, 280ms) 교체. 다른 scrollIntoView 무변경.
  - [x] share.js: 메시지 `share-msg-${idx}` anchor id + `setupSharePointRail`/`renderSharePointRail`/`layoutSharePointRail`/`highlightSharePoint` + `scrollShareMessageIntoCenter`(EaseOutExpo window) + scroll/resize/ResizeObserver/load 리스너.
  - [x] share.html: `<nav id="sharePointRail">` 추가 + share.js/share.css cache-buster bump(`20260629-share-scroll-guide`).
  - [x] share.css: `.share-point-rail`(fixed 미니맵)+`.share-point-dot`+reduced-motion+≤720px 숨김.
  - [x] index.html: app.js cache-buster bump(`20260629-point-scroll-easeoutexpo`).
  - [x] node --check(app.js·share.js) PASS · §18.8 적대 검증 패널(프론트 lens) → REVIEW REV 태그.
  - [x] verify-completion --pre-commit PASS(9/9) → commit f9954cf → origin/main rebase 3931fa3(cache-buster 충돌 결합 토큰 해소) → ff-merge + push origin main → web 재배포(deploy_scope: included, GIT_COMMIT 주입 재빌드·repo-web-1 recreate, healthz git_commit=8f0a025 — feature-0013 PR#468 머지로 내 3931fa3 위에 진행, 조상 포함) → 서빙본 검증 PASS(app.js EaseOutExpo·share.js rail·신규 cache-buster) → worktree/branch cleanup.
  - [ ] PB-0008 Windows 브라우저 시각검증(잔여): 메인 작업화면 rail dot 클릭 시 단축(280ms) EaseOutExpo 스크롤 · 공유 페이지 우측 가이드 뱃지 표시/클릭 점프/active 추적 · 1개 이하 미표시 · ≤720px 숨김 · reduced-motion 즉시점프.
- Next Action: PB-0008 Windows 브라우저 시각검증(배포본 라이브).

## TASK-20260629T170913-glossary-role-fieldname-fix — 용어사전 역할 드롭다운/배지/태그가 실제 역할(dba·admin·sales)을 표시하지 않던 버그 수정 (Minor §12.3 — 프런트 전용, RBAC/스키마/백엔드 무변경) — resume(glossary-role-single-ui 배포본 후속)
- 트리거: 사용자 — glossary-role-single-ui 배포·시각검증 후속. 메타데이터 > 용어사전 '역할' 드롭다운에 '전체 역할'·'공용만'만 보이고 실제 역할(dba/admin/sales 등)이 안 뜨는 현상이 "의도인지" 검토 요청.
- 판정: **버그(의도 아님)**. 권한 게이트(`role.read`)가 아니라 **필드명 불일치**. `/api/admin/roles` 정본 직렬화는 role 객체를 `{id,key,name,...}` 로 주는데(역할 관리·계정 화면 전부 `.key`/`.name` 사용) glossary 코드만 `adminState.roles` 를 `.role_key`/`.role_name`(미존재 필드)로 읽어 `_metaPopulateRoleFilter` 의 `if(!rk) continue` 에서 전 역할 스킵 → 드롭다운에 정적 옵션만, `_metaRoleLabel` 도 미매칭 raw key 표기. 라이브 실증(PB-0008): admin 계정 role.read 보유·`/api/admin/roles` 200·8역할, role 객체 키 `["id","key","name",…]`, `adminState.roles.length=8`인데 드롭다운 옵션 2개뿐.
- 수정(`src/static/admin.js`): `_metaRoleLabel`·`_metaPopulateRoleFilter` 의 role 객체 읽기 `role_key→key`·`role_name→name`(4 참조). 두 헬퍼가 역할 라벨 lookup·필터 옵션의 단일 진실원이라 배지·태그·유사어·관계 6 호출부 전부 정상화. admin.html cache-buster `20260629-glossary-role-single-ui → 20260629-glossary-role-fieldname-fix`.
- 비변경: 백엔드·RBAC·스키마/마이그·검토 큐·유사어 로직. glossary *용어* 객체의 `role_key`(term.role_key)·역할 생성 payload `role_key` 는 별개 정합 필드라 무변경.
- Completion Checklist:
  - [x] _metaRoleLabel·_metaPopulateRoleFilter 필드명 role_key/role_name → key/name (4 refs)
  - [x] admin.html cache-buster bump + node --check(admin.js) PASS
  - [x] verify-completion PASS(9) → commit 90ab783 → base drift(main 8383652) 흡수 병합 a5fea6f(REPORT union) → push → PR #466(CI test pass) 머지(main f021f3d) → worktree/branch cleanup
  - [x] web 재배포(deploy_scope: included, image 재빌드·repo-web-1 recreate, healthz git_commit=f021f3d) + **PB-0008 재검증 PASS**: 실 Windows Chrome 에서 새 admin.js(`?v=…-fieldname-fix`) 로드 후 메타데이터>용어사전 툴바 역할 드롭다운 옵션 **2→10**(전체 역할·공용만 + 실제 8역할: Pending·일반 사용자·Admin·DBA·관리자·서버·웹플랫폼·사업팀) 노출 확인(스크린샷 artifacts/pb0008-glossary-role-dropdown-after.png)
- 완료: cycle 종결. worktree `ai/claude/glossary-role-fieldname-fix`(base 54dbfe3). REV-20260629T170913-glossary-role-fieldname-fix.

## TASK-20260629-metadata-bs-flexclip — 메타데이터 부트스트랩 결과 패널 flex-shrink 클리핑 수정 (Minor §12.3 — 프런트 CSS 전용, feature-0003) — resume(테이블 설명 AI 자동완성 및 UI 버그 수정 PB-0008)
- 트리거: resume `테이블 설명 AI 자동완성 및 UI 버그 수정` — 원본 metadata-table-desc-fix(MSSQL database 차원/테이블명/AI 자동완성) + metadata-bs-collapse(접기·검색)는 머지·배포 완료(PR #461/#463). 사용자 요청 = PB-0008 실 Windows 브라우저 시각검증 진행 + 추가 UI 버그 수정.
- PB-0008 검증 결과(시각): ① MSSQL 골격 테이블명 정상 — `mssql-qa-idc`/`Account` DB 17개 실테이블(`tblAccount`·`tblAccountBlockLog`·`tblAccountChannel`…), tempdb #temp 테이블 0(시스템 DB/스키마 필터 정상). ② 라벨 엔진별 분기 정상(MSSQL='데이터베이스', MySQL='스키마'). ③ AI 자동완성 작동 — `tblAccount` 단건 suggest 가 grounding 된 한국어 설명 자동 생성. **④ 추가 버그 적발**: 부트스트랩 결과 패널이 다수 테이블 시 ~1행만 보이고 pane 스크롤 불가 → 나머지 테이블 확인 불가.
- 근본원인(④): `.admin-pane[data-admin-pane=metadata]`(flex column·고정 height·overflow-y:auto)의 flex 자식 `.admin-meta-bootstrap`(overflow:hidden) 이 flex `min-height:auto`=0 으로 무한 압축(flex-shrink:1) → 90px 클립 + pane scrollHeight==clientHeight 로 스크롤 미발생. max-height 제거(metadata-table-desc-fix)와 별개 경로. headless 가 놓친 것을 PB-0008 실브라우저가 적발.
- 수정: `.admin-meta-bootstrap { flex-shrink: 0 }` + styles.css cache-buster bump(admin.html·index.html → `20260629-metadata-bs-flexclip`). 백엔드/JS/스키마 무변경.
- Completion Checklist:
  - [x] PB-0008 실 Windows 브라우저 시각검증(MSSQL 테이블명·라벨·AI 자동완성·클리핑) 수행
  - [x] flex-shrink:0 fix 적용 + cache-buster bump + CSS brace 균형(1616/1616)
  - [x] 라이브 fix 주입 검증(paneScrollH 684→2364, 17테이블 전부 표시)
  - [x] §18.8 적대 리뷰(CSS 회귀) → REVIEW REV 태그 [SUBAGENT:adversarial-css-regression] VERDICT SAFE
  - [x] verify-completion --pre-commit PASS(9) → commit 54dbfe3(Task-Cycle) → push
  - [x] main ff-merge(dad75c3→54dbfe3) + push main → web 재배포(deploy_scope: included, build web + up -d --no-deps web, healthy/healthz OK) → 재배포본 PB-0008 재검증(serve cache-buster flexclip·baked flex-shrink:0·pane scrollH 2364>684·17테이블 표시)
  - [x] worktree cleanup
- Next Action: 없음 — cycle 완료.
- worktree `ai/claude/metadata-bootstrap-flex-clip-fix`(base dad75c3). REV-20260629T165743-metadata-bs-flexclip. **cycle 완료.**

## TASK-20260629T141637-glossary-role-single-ui — 메타데이터 용어사전 역할 선택 UI 단일화(단일 역할 컨텍스트) + 등록 mis-scope 가드 (Minor §12.3 — 프런트 전용, RBAC/스키마/백엔드 무변경) — resume(원본 glossary-conv-autoreg/review-nest 배포본 후속 결함)
- 트리거: 사용자 resume 요청 — "용어사전 자동 등록 기능"은 완료·배포됐으나 배포본에서 결함 2건 확인. ① 메타데이터 탭에 '역할' 선택 UI 가 2곳(툴바 역할 필터 + 등록 폼 역할 select)이라 각 동작 식별이 어려움 → 독립 UI 하나로. ② 역할 드롭다운에 '전체 역할'·'공용'만 보이고 실제 `계정 > 역할`이 안 보임.
- 결정(AskUserQuestion 2건): ① **단일 역할 컨텍스트** — 툴바 역할 선택 하나가 (목록 필터 + 신규 용어 등록 대상 role_key)를 함께 결정, 폼 역할 select 폐기. ② 결함②는 **권한 부여로 해결**(코드 변경 없음 — `role.read` 게이트, 별도 처리).
- 수정(결함①, 프런트): `_METADATA_FIELDS.glossary` 의 `role_key` roleselect 필드 제거 → 폼에 역할 선택 없음. 죽은 roleselect 렌더 블록·미사용 `_metaRoleOptions` 제거. 툴바 `metadataRoleFilter`(전체 역할 ""/공용 "*"/역할들)가 유일 역할 선택 UI. `_metaSubmitForm` 이 `_metaGlossaryTargetRole(editing)`(단일 진실원)로 role_key 주입 — 생성=현재 컨텍스트(전체→공용 '*'), 수정=대상 용어 기존 role_key 보존. 폼엔 읽기전용 '등록 대상 역할' 배지(선택 UI 아님). admin.html 라벨/aria/title 을 "목록 필터 + 신규 등록 대상"으로 명확화 + admin.js cache-buster `?v=20260629-glossary-role-single-ui`.
- §18.8 적대 패널 2건 BLOCKING 흡수: **F2(mis-scope)** 등록/수정 성공 토스트에 대상 역할 표기(`…했습니다 (역할: X / 공용)`) — 역할별 비중복 namespace 사후 인지 보장. **F5(배지 stale)** 툴바 역할 변경 시 폼 재렌더(입력 소실) 없이 `_metaUpdateGlossaryRoleBadge`(id 기반)로 배지·노트만 동기화. NIT 흡수: F1(‘전체 역할’ 보기 생성 시 공용 귀속 노트) · 로직 중복 헬퍼화.
- 비변경: 백엔드 라우트/검증(`admin_create_glossary`·`_metadata_check_role_key`), RBAC, DB 스키마/마이그, 목록 역할 배지·유사어 패널·검토 큐. **알려진 trade-off(F3, 의도적 수용·고지)**: 폼 역할 select 제거로 기존 용어의 역할 이동(공용↔역할) 직접 편집 UI 소실(백엔드 PUT 은 계속 지원) — 이동 필요 시 후속 전용 affordance 검토. 사용자에 표면화.
- 검증: node --check(admin.js) PASS · §18.8 적대 2-lens 패널 + BLOCKING 수정 후 재검증 · Windows 브라우저(PB-0008) 라이브 렌더 · web 재배포(deploy_scope: included) 후 cache-buster·healthz 확인.
- 잔여: REVIEW REV 태그 → verify-completion → commit(Task-Cycle) → push → PR 머지 → web 재배포 → 라이브 검증. 결함②는 코드 외 권한 부여 안내. worktree `ai/claude/glossary-role-single-ui`(base 3dfe81c). REV-20260629T141637-glossary-role-single-ui.
- Completion Checklist:
  - [x] 폼 역할 select 제거 + 죽은 roleselect 렌더/`_metaRoleOptions` 제거 → 툴바 단일 역할 UI
  - [x] `_metaGlossaryTargetRole` 단일 진실원으로 role_key 주입(생성=컨텍스트/전체→공용, 수정=기존 보존)
  - [x] 읽기전용 '등록 대상 역할' 배지/노트 + admin.html aria/title 명확화 + cache-buster bump
  - [x] §18.8 적대 패널(2-lens) → BLOCKING 2(F2 토스트·F5 배지 stale) 수정 → 재검증 클린
  - [x] FUNCTION.md 단일 역할 컨텍스트 반영 · TASK/MODIFY/REVIEW/REPORT/STATUS 갱신
  - [x] verify-completion PASS(9) → base drift(main 7-behind) 흡수 병합커밋 38da578 → push → PR #465(CI test success) 머지(main 4f3d22c) → worktree/branch cleanup(cycle-finalize)
  - [x] web 재배포(deploy_scope: included, image e045ef4 재빌드·repo-web-1 recreate) + 검증: healthz git_commit=4f3d22c·mysql/pg ok, baked+라이브 HTTPS serve `admin.js?v=20260629-glossary-role-single-ui`, baked admin.js `_metaGlossaryTargetRole` 존재
  - [ ] PB-0008 Windows 브라우저 라이브 렌더 검증(역할 UI 1곳·등록 토스트 역할 표기) — 배포·라이브 serve 검증 완료, 단 admin 인증 필요 화면이라 실 Windows 브라우저 시각검증은 **사용자 확인 권장**(precedent metadata-bootstrap 동일)
  - [ ] 결함② role.read 권한 부여 안내(코드 외) — 용어사전 관리 역할/계정에 `role.read` 부여 시 툴바 역할 선택에 실제 `계정 > 역할` 노출(사용자 조치)
## TASK-20260629-metadata-bs-collapse — 메타데이터 부트스트랩 결과 패널 접기+검색 재설계 + 잘림(cache-buster) 수정 (Major §12.3, feature-0003, 2026-06-29)
- 트리거: 사용자 보고(metadata-bootstrap-mssql-db 배포 후속) — 스키마 골격 펼침 시 패널 내부 잘림 잔존 + 다수 테이블 여백 과다.
- 결정(AskUserQuestion): 이슈2 재설계 방향 = **접기 + 검색/필터**(사용자 선택).
- [x] 진단: 잘림 = cache-buster 미bump 로 stale CSS(460px 캡 생존), 여백 = 전체 평면 렌더.
- [x] cache-buster bump(admin.html `styles.css`·`admin.js` + index.html `styles.css` → 20260629-metadata-bs-collapse).
- [x] admin.js 접기 렌더 + 검색/필터 + 모두펼치기 + 입력상태 힌트(시각 토글, 입력 DOM 보존, 저장·AI fill 전체 수집 불변).
- [x] admin.html 검색 필터바 + styles.css 접기/조밀 스타일.
- [x] node --check PASS · §18.8 적대 패널 BLOCKER 0(MINOR 라벨 desync 흡수).
- [ ] verify-completion → commit → PR → merge → web 재배포(cache-buster 반영) → PB-0008 Windows 브라우저 검증 → 임시 검증계정 정리.
- Next Action: 출하·배포·라이브 검증.
- 잔여/follow-up: tables↔columns 서브탭 전환 시 부트스트랩 재렌더(REV MAJOR, pre-existing) 별도 cycle 로 처리 권고.

## TASK-20260629T041724-doc-sync-rn-0629 — 06-29 머지분 릴리즈노트 정합(용어사전 대화 자율등록 · 용어 검토 큐 중첩 · 답변 평가 중복 정리) + cache-buster bump (doc_sync, 비-정책 doc, 2026-06-29)
- 트리거: `/_dqa:doc_sync`(스케줄 무인 실행, 전 타깃). 직전 릴리즈노트 sync(63874f2 @ 2026-06-29 08:35, "ask-dedup 06-26 블록 합류") 이후 main 병합된 06-29 user-facing 변경이 릴리즈노트 미반영(drift) → `release-notes-data.js` releases head 에 신규 '2026-06-29' 블록 prepend(generated 2026-06-29 유지).
- [x] 대상 머지(3, 평이화·내부 비노출): [new admin] 용어사전 대화 자율등록 — 대화 내용 바탕 업무 용어 자동 제안·검토 후 등록(역할별 구분·비슷한 용어 연결)(40c0de0); [improved admin] 용어 검토 큐를 용어사전 화면 안의 보기 탭으로 이동(284e75a); [fixed work] 답변 평가(좋아요/별로예요)가 새로고침·대화 전환 후에도 답변마다 한 번만 남도록 정리(평가 변경 가능)(31aa67a + 8c605b8 id_space 보강).
- [x] 적대 결정 — 첨부 wrong-bubble(ec39a60) **항목 제외**: REPORT·커밋이 "정상 display 경로 동작 동일"(스키마/마이그·프론트·cache-buster 무변경) 명시, 드문 fork/마이그 cross-space 엣지 하드닝이라 사용자 체감 변화 0 → 보수적으로 미추가.
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. 내부용어(role_key/검토 큐 엔드포인트/마이그 0021/0023/id_space/message_id/wrong-bubble/feature-id/테이블명) 누출 0.
- [x] 검증: `node --check release-notes-data.js` PASS + 항목 스키마(type/area/title/detail) 정합 + releases head '2026-06-29' 블록 신설(3항목).
- [x] 배포 전파: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260629-rn-0629`→`?v=20260629b-rn-0629` bump(정적 자산은 `?v=` 가 유일 전파 메커니즘). verify-completion(operational, feature-0003) → 로컬 commit. landing(push/PR/merge)·deploy 는 cron wrapper 소관.

## TASK-20260629T120711-attach-id-space — 첨부 영속 레이어에 message_id_space 추가 — H5(b) wrong-bubble 의 첨부 레이어 완결 (follow-up, Major §12.3 — feature-0003 단독, 스키마 마이그 없음) — done
- 출처: 사용자 요청 — "동일한 message.id 키를 쓰는 첨부 영속 레이어의 같은 이슈를 마저 처리해주세요." 선행 TASK-20260629T022055-feedback-id-space(REVIEW '잔여')가 별도 feature 로 미룬 첨부 레이어를 완수.
- 문제(H5(b) 첨부 레이어): `_load_assistant_attachments_by_message` 가 MetaJson.message_id 단일 키로 그룹핑, `_attach_assistant_attachments` 가 history 메시지 `id` 단일 키로 매칭. message.id 는 표시 store(`agent_runtime.messages.id`)·core fallback(`core_messages.id`) 두 독립 IDENTITY 공간서 와 숫자만 같아도 다른 답변 → core 공간 메시지가 같은 숫자의 display 첨부를 잘못 표시하는 wrong-bubble 가능(피드백 레이어와 동일 선재 특성).
- 수정: 첨부 식별에 **id_space** 차원 추가 → (message_id, message_id_space) 복합 키. 피드백 레이어(`_attach_user_feedback`)와 대칭.
  - [x] `_materialize_assistant_attachment_edits`: 새 버전 row 의 MetaJson 에 `"message_id_space": "display"` 추가(message_id 출처 `_load_latest_assistant_message` 가 표시 store 전용 → 항상 display, 불변식 영속).
  - [x] `_load_assistant_attachments_by_message`: 반환 키 `message_id` → `(message_id, message_id_space)`. MetaJson space 없으면 'display'(legacy 하위호환). 타입 dict[int]→dict[tuple].
  - [x] `_attach_assistant_attachments`: 메시지 `(id, id_space)`(미설정 시 'display') 복합 키로 매칭 → cross-space wrong-bubble 차단.
  - [x] 테스트 `test_task0285_attach_surfacing.py`: A1/A2/L1/L2 복합 키 갱신 + A3(cross-space wrong-bubble)·L4(core/display 분리 + legacy 'display') 신규. 헬퍼 `_att_row(space=)`.
- 비변경: 프론트(서버가 채운 `_attachments` 렌더)·share·cache-buster·DB 스키마/마이그 0. 정상 display 경로 동작 동일.
- [x] 검증: 대상 11/11, `make test` 전체 exit=0(두 feature 회귀 0)·ruff·py_compile.
- [x] 적대 self-review(H5(b) 첨부 레이어 closure) — REV-20260629T120711-attach-id-space. (선행 cycle 적대 리뷰 H1~H7 가 결함·설계 이미 도출.)
- Cross-ref: 선행 TASK/REV/CHG-20260629T022055-feedback-id-space(H5(b) 출처) / CHG·REV-20260629T120711-attach-id-space.
## TASK-20260629-glossary-review-nest — 용어 검토 큐 IA 중첩(메타데이터 > 용어사전 > 용어 검토 큐) (Minor §12.3, 프런트 전용)
- 출처: `/_template:entry` dispatch(2026-06-29). 요청: 검토 큐를 메타데이터 최상위 서브탭(전)에서 **용어사전 하위 2차 보기 탭**(후)으로 이동.
- 설계: 최상위 서브탭에서 glossary-review 제거 → 용어사전 하위에 2차 보기 탭(`용어 목록`/`용어 검토 큐`), 내부 상태 `glossaryView`. 권한 보존 — 용어사전 서브탭은 `kb.ingest.manual` OR `kb.glossary.curate`(중첩으로 인한 curate-only 접근 단절 방지), 보기별 권한 게이트(목록=ingest.manual, 검토 큐=glossary.curate) + 현재 보기 권한 없으면 첫 표시 보기로 전환. 백엔드/route/엔드포인트 무변경.
- [x] admin.html: glossary-review 서브탭 제거 + `#metadataGlossaryViews` 2차 보기 strip + 배지 이전.
- [x] admin.js: `glossaryView` 상태 + `_metaIsGlossaryReview`/`_metaSubtabVisible`/`_GLOSSARY_VIEW_PERM`/`_metaSyncGlossaryViews` + 2차탭 바인딩 + render/load/toolbar 분기를 새 보기 모델로 이전. node --check PASS.
- [x] styles.css: `.admin-meta-gview` 2차 보기 탭(필 형태) 스타일. FUNCTION.md IA 기술 갱신.
- [x] 적대 검증 워크플로(상태머신·권한·회귀 3 lens, BLOCKER 0): **MAJOR 1건(3 lens 동일근본)** — 부모 `ADMIN_TAB_PERMISSIONS.metadata` 가 `kb.glossary.curate` 누락 → curate-only 사용자가 메타데이터 탭 자체 진입 불가(내 OR 게이트가 dead path). **수정**: 탭 게이트에 `kb.glossary.curate` 추가(서버 403 이 실경계, 표시 확장 안전). + MINOR/NIT(재진입 strip/배지 sync·이중호출 제거·aria-selected) 전부 흡수. node --check PASS.
- [ ] verify-completion → commit → main 동기화 → web 재배포(deploy_scope: included).

## TASK-20260629T022055-feedback-id-space — 피드백 고유성 키에 id_space 추가 — 두 message-id 공간(표시 store vs core) 모호성 해소 (H5(b) follow-up, Major §12.3 — 스키마 마이그 0022 + cross-feature 0002+0003)
- 출처: 사용자 요청 — TASK-20260629T014345-feedback-unique-vote 의 적대 리뷰가 수용·문서화한 **H5(b)** 잔여 한계를 마저 완수. 사용자: "확인된 후속 권고사항도 마저 작업을 완수해주세요."
- 문제(H5(b)): `/api/history` 의 `message.id` 는 표시 store(`agent_runtime.messages.id`)와 core fallback(`core_messages.id`)의 **두 독립 IDENTITY 공간**서 올 수 있다(agent_core 가 "독립 시퀀스, 숫자 겹침" 명시). 0021 의 고유성 키 (created_by, message_id) 는 숫자만 같으면 서로 다른 답변을 같은 키로 봐, fork·마이그로 대화가 core-only→display 전환되는 드문 경우 (a) cross-space DB 충돌(다른 답변이 같은 키 → UPSERT 가 남의 투표 덮어씀) (b) wrong-bubble 복원(core-id 피드백이 같은 숫자의 display 메시지에 표시) 가능.
- 수정: 답변 식별에 **id_space** 차원 추가 → 키를 (created_by, message_id, **message_id_space**) 로 확장. 두 공간의 같은 숫자 id 가 이제 다른 키.
  - [x] `/api/history` 4개 메시지 빌더가 `m["id_space"]` 노출: `_get_agent_core_history`(PG·MySQL)="core", `_get_history`(PG·MySQL display)="display".
  - [x] `_load_user_feedback_by_message`/`_attach_user_feedback`: (message_id, id_space) 복합 키로 조회·매칭(wrong-bubble 복원 차단).
  - [x] `post_sample_feedback`: body `message_id_space`("display"|"core") 파싱·정규화·전달.
  - [x] 코어 `record_feedback`(feature-0002): `message_id_space` 인자 + INSERT/ON CONFLICT 3-col `(created_by, message_id, message_id_space)`.
  - [x] 마이그 0022 + 부트스트랩 `agent_kb_schema.sql`: `message_id_space varchar(16) NOT NULL DEFAULT 'display'` + 3-col 부분 UNIQUE **신규 이름** `ux_sample_feedback_user_msg_space_vote`(구 2-col `ux_sample_feedback_user_msg_vote` drop — same-name no-op trap 회피). 기존 행 default 'display'(라이브 적재분 전부 표시 store) 무손실.
  - [x] `_buildSampleFeedbackControls`: `message.id_space` 읽어 POST 에 `message_id_space` 포함. cache-buster `?v=20260629b-feedback-id-space`.
- 비변경: 재투표 변경 허용·"샘플 등록" 분리·rate-limit·RBAC·audit 0. id_space 기본 'display' 라 대다수 경로 동작 동일.
- [x] 테스트: `test_sample_flywheel.py`(masks_pii param 위치 보정 + 3-col ON CONFLICT + id_space 전달 단언)·`test_sample_feedback_curation.py`(message_id_space 전달 단언) → flywheel 13/13 · curation 15/15, 두 feature 전체 회귀 0. py_compile + node --check + alembic chain linear(0021→0022 단일 head).
- [ ] verify-completion → 머지·push → 배포(0022 스키마 적용 + web 재빌드).
- Cross-ref: feature-0002 TASK/CHG/REV-20260629T022055-feedback-id-space / 선행 TASK-20260629T014345-feedback-unique-vote(H5(b) 원 출처).

## TASK-20260629T014345-feedback-unique-vote — 답변당 사용자별 고유 피드백(👍/👎) 강제 — 새로고침·대화 전환 후 중복 부여 차단 (Major §12.3 — 스키마 마이그 + cross-feature 0002+0003)
- 출처: `/_template:entry` arg-given dispatch. 사용자 보고: "assistant 답변에 피드백(👍/👎) 부여 후, 다른 대화에서 전환하거나 새로고침하면 같은 답변에 다시 피드백 부여가 가능. 각 사용자는 답변당 고유한 피드백만 부여할 수 있어야 함."
- 결정(AskUserQuestion): 재투표 시 **변경 허용**(👍↔👎 전환 가능, 서버 UPSERT last-write-wins, 항상 답변당 1행).
- 진단(코드 교차): 중복 차단이 **두 계층 모두 부재**. ① 프론트 `_buildSampleFeedbackControls`(app.js)의 유일한 dedup 이 `wrap.dataset.done="1"`(in-session DOM 플래그) — `renderMessages()`가 새로고침·전환 시 DOM 재생성하며 소실 → 버튼 재활성. POST 가 답변 식별자 미전송. ② 코어 `record_feedback`(feature-0002 modules/sample_feedback.py)이 **무조건 INSERT** — `sample_feedback` 테이블에 message_id·UNIQUE 부재(마이그 0014) → 같은 (user,답변)에 무한 행 생성. 답변은 표시 store `agent_runtime.messages.id`(= 프론트 `message.id`, 첨부 영속과 동일 id 공간)로 안정 식별 가능 → 이를 키로 (created_by, message_id) 고유성 강제.
- 설계(5요소): **A** 마이그 0021(feature-0002) — `sample_feedback.message_id bigint` 추가 + 부분 UNIQUE `ux_sample_feedback_user_msg_vote (created_by, message_id) WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested=false`(과거 행·익명·"샘플 등록"은 제외 → 무손실·멱등). **B** `record_feedback`: message_id 인자 + INSERT→UPSERT(`ON CONFLICT … DO UPDATE`) + `RETURNING id`(lastval 미사용 — DO UPDATE 경로 부정확). **C** `post_sample_feedback`: body `message_id` 파싱·전달 + 반환 id 사용. **D** `/api/history`: assistant 메시지에 현재 사용자 투표 상태(`m["feedback"]`) 주입(`_load_user_feedback_by_message`/`_attach_user_feedback`, 첨부 attach 패턴 재사용) — 새로고침·전환 복원 데이터 원천. **E** `_buildSampleFeedbackControls`: POST 에 `message_id` 포함 + `message.feedback` 있으면 기존 투표 활성표시(변경 허용, busy 가드만). **F** CSS `.message-feedback-btn.is-active` + index.html cache-buster `?v=20260629-feedback-unique-vote`(app.js·styles.css).
- 가드: D+E 가 UX 증상(새로고침 후 재클릭)을 막고, A+B 가 어떤 경로(직접 API 포함)로든 중복을 DB 계층에서 권위적으로 차단. "샘플 등록"(suggested=true)은 검수 큐 제출이라 투표 고유성과 분리(부분 인덱스 술어 제외) — 기존 동작 보존.
- [x] A 마이그 0021 작성(linear chain, 0020→0021 단일 head 검증). B/C/D/E/F 구현.
- [x] 테스트: `test_sample_flywheel.py` 갱신(param 위치 + ON CONFLICT 단언) + 신규 1건(vote UPSERT 키), `test_sample_feedback_curation.py` 갱신(record 반환 id + message_id 전달 단언) → flywheel 15/15 · curation 15/15 PASS, 두 feature 전체 스위트 회귀 0(`test_share_redaction_invariant`는 컨테이너 전용 `web.app` import 라 로컬 한정 환경 실패, 본 변경 무관). `py_compile`(sample_feedback.py·app.py·0021) + `node --check`(app.js) PASS.
- [ ] verify-completion --pre-commit → commit → main 병합·push → 배포(deploy_scope 판정).
- Cross-ref: feature-0002 record_feedback UPSERT + alembic 0021 + MODIFY/REVIEW/MIGRATIONS 2026-06-29.
## TASK-20260629-glossary-conv-autoreg — 용어사전 대화 자율등록 + 역할 분리 + 유사어 참조 (Major §12.3, cross-feature 0002+0003, ADR-20260629T101500)
- 출처: `/_template:entry` dispatch(2026-06-29). 요청: 「관리 콘솔 > 메타데이터 > 용어사전」이 사용자 대화로부터 assistant 판단 하에 자율 등록되도록 + ① 역할별 용어 비중복 ② 유사 의미 시 참조 가능.
- 결정(AskUserQuestion): **하이브리드 자동승급**(고신뢰도 자동 등록·되돌리기 가능, 저신뢰도 검토 큐) + **기본 역할 귀속 = 공용('*')**. 위험 Major(DB 마이그레이션 + core/web/UI/tests 다중 파일). 거버넌스 충돌(기존 "자동학습 없음")은 검토 큐·되돌리기로 해소 → ADR-20260629T101500.
- [x] **web 엔드포인트(app.py)**: glossary CRUD 에 role_key 검증(`_metadata_check_role_key`, WebRoles.RoleKey ∪ '*') + list ?role_key= 필터; 검토 큐 3종 `GET /api/admin/metadata/glossary-feedback`·`POST …/{id}/promote`·`POST …/{id}/reject`(권한 kb.glossary.curate); 유사어 3종 `GET/POST …/glossary/{id}/relations`·`DELETE …/glossary/relations/{id}`(권한 kb.ingest.manual). 신규 권한 `kb.glossary.curate`(group=kb, admin seed). audit: glossary.feedback.promote/reject·glossary.relation.create/delete.
- [x] **관리 UI(admin.html/admin.js/styles.css)**: glossary 폼 역할 select(roleselect) + 목록 역할/출처 배지 + 툴바 역할 필터; 검토 큐 서브탭(`glossary-review`, pending 배지·상태필터·승급/되돌리기); 용어별 유사어 패널(목록/추가/삭제). XSS = textContent/value 만.
- [x] **코어/마이그/hook = feature-0002**(cross-cut): TASK-20260629-glossary-conv-autoreg 참조.
- [x] 테스트: 코어 `test_kb_glossary_enum.py` 19건(역할 read·record/auto-promote/reject/promote/relation SQL) + 웹 신규 `test_metadata_glossary_autoreg.py` 13건(권한·role 검증·큐·관계) + 기존 metadata 회귀(glossary_enum/autocomplete/phase2) 갱신 PASS + route_snapshot_p5b.json 6 신규 라우트 갱신. 전체 **1222 passed**(잔여 7 fail = `web.app` 컨테이너 레이아웃 의존, 본 변경 무관). ruff·py_compile·node --check·단일 alembic head PASS.
- [ ] verify-completion --pre-commit → commit → main 동기화 (deploy_scope: included).

## TASK-20260626-ask-dedup-idempotency — assistant 요청이 2번 중복 전송/처리되는 결함 수정 (worker-mode enqueue 멱등화, Major §12.3 — /api/ask send/concurrency, cross-feature 0002+0003)
- 출처: `/_template:entry` dispatch. 사용자 보고: "프로젝트 내 서비스에서 assistant 에게 요청을 보낼 때 2번 중복되어 전송." 명료화(AskUserQuestion): **요청도 2번·답변도 2번 처리 / 항상(첫 요청부터)**.
- 진단(코드+라이브 DB/로그 교차): 프론트 `/api/ask` 는 sendPrompt(app.js:8320) 단일 POST(이벤트 이중바인딩 없음·apiFetch 재시도 없음·resume 재전송 경로 없음), 백엔드 enqueue 도 `_dispatch_ask_run_worker`(app.py:11321) 1곳뿐. 그러나 `agent_runtime.ask_jobs` 실측 — 동일 페이로드(conv+account+user_message) **job 2개**(94b96f5f #148/#149 Δ460ms, cbb5bde0 #153/#154 Δ20s; 둘 다 attempts=1·done = requeue 아님). 단일 워커 직렬 처리로 두 번째 run 이 user 메시지를 ~1분 뒤 재삽입 → "요청·답변 2회". 근본원인: 워커 모드 `/api/ask` 가 run 종료까지 연결을 수십 초~분 잡는데(long-poll attach), **web 컨테이너 재생성(배포/자동화)** 시 그 연결이 502 EOF 로 끊김(Caddy 로그: 24~109s 후 502, connection refused, 공인 IP 112.185.196.95 오해석 dial) → 복구용 `/api/ask_status` 도 실패 → 프론트가 in-flight run 미포착 → 사용자 재전송 → 두 번째 job. 첫 job 은 out-of-process 워커에서 생존·완료 → 답변 2개. **워커 enqueue 에 멱등성(dedup) 부재**가 핵심 결함.
- 결정(AskUserQuestion): **A+B+C 전체**.
- [x] **A (정본, `unit/feature-0002-agent-core/src/modules/ask_jobs.py`)**: `enqueue_ask_job(dedup_message=...)` — INSERT WHERE 에 `NOT EXISTS(같은 conv+account+user_message 의 pending/running)` 가드(INSERT 동일 statement = commit 된 중복에 atomic) + 신규 `find_active_dup_ask_job`. `unit/feature-0003-agent-web-ui/src/app.py` `_dispatch_ask_run_worker._enqueue`: 사전 dedup 검사(있으면 기존 run KV/run_id 보존·sentinel 미덮어쓰기 후 기존 job_id 반환=attach) → 없으면 `enqueue_ask_job(dedup_message=user_message)` → INSERT 억제 시 `find_active_dup_ask_job` 재조회로 슬롯가득(429) vs 중복(attach) 구분.
- [x] **B (`unit/feature-0003-agent-web-ui/src/static/app.js`)**: 기존 대화 `/api/ask` 실패 catch 의 복구 status 조회를 0.7s×3 재시도(첫 조회 null 시) — web 일시 불안정에 in-flight run 을 안정 포착해 불필요 재전송 억제.
- [x] **C (web 불안정 트리거)**: 원인 확정(크래시 루프 아님 — RestartCount=0, 배포 재생성이 트리거; docker DNS 갭→ISP NXDOMAIN 공인 IP 폴백). 라이브 프록시/배포 인프라 blind 변경 위험 → 원인·권고 문서화로 처리(A 가 트리거 하에서도 중복 근절). 권고(후속): web 배포 graceful drain · Caddy upstream 재해석/health.
- [x] 테스트: `test_ask_jobs.py` 신규 5건(dedup NOT EXISTS 절·param·suppressed None·find helper 반환/부재) 포함 **21/21 PASS** + `py_compile`(ask_jobs.py·app.py) + `node --check`(app.js) PASS. 스키마/RBAC/마이그 0(런타임 멱등).
- [x] verify-completion --pre-commit PASS(9) → commit 721519b → main rebase(483c4c0)+ff-merge(0818b0a)+push → **web+ask-worker 재빌드·재기동**(deploy_scope: included, 둘 다 Up healthy, baked dedup+buster+healthz 확인).
- [x] **HOTFIX(배포 검증 중 라이브 PG 회귀)**: dedup NOT EXISTS 의 `%(cid)s`/`%(account_id)s` 재사용 → `AmbiguousParameter(text vs varchar)` → 워커 모드 신규 /api/ask 500. 전용 파라미터 `%(dcid)s`/`%(daccount)s`+alias `d` 분리, 라이브 PG SQL 직접 실행 재검증 + 회귀 테스트 단언 추가 → 재빌드·재배포. (단위 FakeConn 이 SQL-shape 만 봐 미포착 — 라이브 enqueue 직접 실행으로 적발.)
- Cross-ref: feature-0002 CHG-20260626-ask-dedup-idempotency / REV-20260626T134920-ask-dedup-idempotency / REPORT 2026-06-26.

## TASK-20260626T025055-product-chip-always-enabled — 제품 선택 chip 을 요청 처리 중에도 항상 활성화 (Minor §12.3 — frontend + backend PATCH 가드, TASK-0047 race 가드 완화, RBAC 무변경)
- 출처: `/_template:entry` dispatch. 사용자 보고: "assistant 에게 요청을 보낼 때(요청 처리 중) 제품 목록을 선택하는 버튼(composer 의 `#productChip`, 예: 'KR_QA')이 비활성화됨 — 이제는 항상 활성화 상태여야 함."
- 진단: 차단이 **세 계층**(전부 TASK-0047 "turn 단위 immutability"). ① `renderProductChip()`(app.js) busy→`chipEl.disabled`+`is-disabled`+안내 title(시각/상호작용 차단, `openProductDropup` `if(chip.disabled)return` 가드로 드롭업 차단). ② `setActiveProduct()`(app.js) busy→토스트 후 변경 거부(프론트 기능 차단). ③ **백엔드 `PATCH /api/conversations/{cid}/product`(app.py:12370) `_conversation_is_processing`→409**. ③ 때문에 ①②만 풀면 owner 가 클릭 시 409 에러 토스트로 실패(활성처럼 보이나 동작 안 함) — 적대 검증 subagent 가 적발. 셋 다 풀어야 "항상 활성+사용 가능" 실효.
- 안전성 분석(적대 검증 SUBAGENT VERDICT SAFE — 반증 실패): 제품(`product_id`/`product_mode`)은 `/api/ask` 슬롯 획득 후 1회 read(app.py:11676-11704)→`run_kwargs` baked(11995-12013)→worker payload(11293~) 로 캡처. worker `_payload_to_kwargs`(modules/ask.py:85-104)·`run_agent`(agent_core.py) 모두 conversation 제품을 **재조회 안 함**. PATCH 는 단일 row UPDATE(12407~), in-flight run 취소·KV·캐시 부수효과 0 → 데드락/오염 불가. 변경은 다음 `/api/ask` 부터 `_load_conversation_product`(11521) 로만 반영 — `setActiveProduct` 토스트("다음 답변/메시지부터 적용됩니다")와 정합. 409 가드는 데이터 정합성 아닌 보수적 UX 가드(손상 위험 0).
- [x] `static/app.js` `renderProductChip()`: busy 분기 제거 → `chipEl.disabled=false`+`aria-disabled=false`+`is-disabled` 제거+정상 title 상수화.
- [x] `static/app.js` `setActiveProduct()`: `isCurrentConvBusy()` reject 가드 블록 제거(처리 중에도 변경 허용). 토스트·optimistic·PATCH·participant override 경로 무변경.
- [x] `src/app.py` `update_conversation_product`(PATCH): `if _conversation_is_processing(conn, cid): return 409` turn-immutability 가드 제거 + docstring 갱신. 권한 게이트(conversation.ask·소유권·`_account_has_product_access`·IsActive)·UPDATE·pref 저장 전부 무변경 → **RBAC/스키마/엔드포인트 shape 0 변경**. helper `_conversation_is_processing`(3669)는 타 호출처 없으나 재사용 가능 query util 이라 보존(ruff clean).
- [x] `static/index.html`: app.js cache-buster `?v=20260625-conv-switch-fade` → `?v=20260626-product-chip-always-enabled`(변경 전파).
- [x] 검증: `node --check app.js` PASS · `python3 -m py_compile app.py` PASS · `ruff check app.py` All checks passed · 잔여 chip disable 신호 grep 0(1389 가드는 chip.disabled 항상 false 라 무해) · `isCurrentConvBusy` 타 용도(composer send/stop 5072 등) 무영향.
- [x] **리뷰(REV-20260626T025055-product-chip-always-enabled [SUBAGENT:adversarial-product-race]):** 적대 검증(general-purpose, 5축 — ask 캡처 시점·worker 재조회·PATCH 부수효과·동시성 데드락·participant override) **VERDICT SAFE**, in-flight 오염·백엔드 race 반증 실패. 발견(watch item): 409 제거 전엔 프론트 가드만 풀면 owner 클릭이 409 로 실패 → 본 cycle 에서 백엔드 가드도 제거해 해소.
- [x] verify-completion --pre-commit PASS(9) → commit f049fee → main ff-merge(c11cc27..f049fee) → origin push → **web 재배포(deploy_scope: included, sudo docker compose build web && up -d --no-deps web)**. 배포 검증: `repo-web-1` Up healthy + baked `index.html` 서빙 `app.js?v=20260626-product-chip-always-enabled` + baked `app.py` 409 제거(grep 0) + web healthz OK. ask-worker 미재빌드(web-only). **cycle 완료.**

## TASK-20260625T192007-doc-sync-rn-0625b — 06-25 잔여 머지분 릴리즈노트 정합 + cache-buster bump (doc_sync maintenance, Minor §12.3 — 정적 콘텐츠)
- 출처: `/_dqa:doc_sync` (no-arg 전 타깃 정합). 직전 doc_sync(doc-sync-20260625-163929, PR#420~#436 기준 16:55~17:01 콘텐츠 작성)가 그 **이후** main 병합된 06-25 user-facing 변경 5종을 미반영(브랜치 stale 잔여 drift) → 기존 `2026-06-25` 블록에 항목 추가(append — 신규 일자 블록 아님, 같은 날 머지분).
- 대상 머지(5): PR#440(908fade) 참가자 per-message 제품 선택·발화 · PR#438(1f370c4)+PR#444(334c858 R1) 처리 중 입력창 비잠금/동시 run 고착·채팅 블로킹 해소 · PR#444(R3/R2) 1:1 인터럽트 재요청 + 그룹 @assistant 중복차단 · PR#437(1a69f70) @assistant 발신자 귀속 표시 정정 · PR#439(c8637f2) datasource 회로차단 사용자 안내 문구 분리.
- 범위: **릴리즈노트 콘텐츠 데이터만** — 렌더 로직·백엔드·스키마·RBAC 무변경. 사용자 평이화(내부 구현/feature-id/테이블명/엔드포인트 비노출). PR#442(unread baseline 보정)는 06-25 안 읽음 배지 항목에 흡수(별도 항목 불요), 17:24 chore(개발용 LLM 호출주체 임시전환 CHG-20260625T171844)는 비-user-facing 제외.
- [x] `release-notes-data.js`: 기존 `2026-06-25` 블록 items 9→14(work +4: per-message 제품 선택 · 처리 중 입력/전송 안정화 · 인터럽트 재요청 · 발신자 표시 정정 / common +1: 회로차단 안내) + summary 갱신. `generated` 2026-06-25 유지.
- [x] cache-buster: `index.html`·`admin.html` release-notes-data.js `?v=20260625b-rn-0625` → `?v=20260625c-rn-0625` bump.
- [x] 검증: `node --check release-notes-data.js` PASS + 스키마(type/area/title/detail) 정합 + 머지 5건 1:1 대조. 적대 사실검증(평이화·내부 비노출·과장 0).
- [x] **리뷰(REV-20260625T192007-doc-sync-rn-0625b [SKIPPED]):** 정적 사용자노출 콘텐츠 큐레이션 — 제품 로직·인가·스키마 무변경, 적대 패널 불요(§18.4 비-정책 doc 경량 cycle).
- [ ] verify-completion(operational, feature-0003) → 머지 → web 재배포(static baked, deploy_scope: included) → 마감.

## TASK-20260625T165205-doc-sync-rn-0625 — 06-25 머지분 릴리즈노트 정합 + cache-buster bump (doc_sync maintenance, Minor §12.3 — 정적 콘텐츠)
- 출처: `/_dqa:doc_sync` (resume from doc-sync-20260625-160433, session-limit 중단 재개). `src/static/release-notes-data.js`(사용자 노출 릴리즈노트, 정적 큐레이션 데이터)가 직전 릴리즈노트(06-24 블록, 600f2b5) 이후 main 병합된 06-25 user-facing 변경 9종을 미반영(doc/reality drift) → 새 `2026-06-25` 블록 prepend.
- 범위: **릴리즈노트 콘텐츠 데이터만** — 렌더 로직(release-notes.js)·백엔드·스키마·RBAC 무변경. 사용자 평이화(내부 구현/feature-id/테이블명/엔드포인트 비노출).
- [x] `release-notes-data.js`: `releases` head 에 `date: "2026-06-25"` 블록 prepend(9항목 — [new work] 안 읽음/@멘션 배지 · 멤버 추방/차단/해제 · [improved work] 메시지 좌우 정렬 · [new admin] 역할/제품 프롬프트 AI 자동작성 · 제품 분석률 95% 자동완성 · [improved admin] 규칙 추가 DB 커버리지 · 지식베이스 메뉴 재편 · [improved common] 한도 메시지 주체 구분 · AI 준비 속도). `generated` 는 `2026-06-25` 유지.
- [x] cache-buster: `index.html`·`admin.html` release-notes-data.js `?v=20260625-rn-0625` → `?v=20260625b-rn-0625` bump(06-25 블록 캐시 무효화).
- [x] 검증: `node --check release-notes-data.js` PASS + 스키마(type/area/title/detail) 정합 + 머지 커밋 10건 1:1 대조(09114ed·cc62773·1d83d94·29d1bbf·5c525db·4cd26e7·23b7175·874f15e·70c57f6·23fa679; hover 29d1bbf 는 추방/차단 항목 합산). 내부 리팩터(shared P5a Step4/5·codebase-map·template v3.35.1·spec-anchor)는 의도적 제외. 적대 사실검증(general-purpose, 5축) VERDICT CLEAN.
- [x] **리뷰(REV-20260625T165205-doc-sync-rn-0625 [SKIPPED]):** 정적 사용자노출 콘텐츠 큐레이션 — 제품 로직·인가·스키마 무변경, 적대 패널 불요(§18.4 비-정책 doc 경량 cycle).
- [ ] verify-completion → 머지 → web 재배포(static baked, deploy_scope: included) → 마감.

## TASK-20260625T163424-gc-participant-product-select — 공유 대화 참가자(비-owner)의 per-message 제품 선택·발화 (feature-0009 cross-cut, 코드 거주=feature-0003, Major §12.3 — authz 경계: 참가자 발화 RBAC) — 중단 세션 resume
- 맥락: 원본 작성 세션(372f8779)이 코드(B1 ask override·B2 session view-only·F1 드롭업 2그룹·F2 setActiveProduct/sendPrompt) 작성 직후 docs 직전 중단 → resume 으로 칩 fallback 확인·캐시버스터 bump·검증·docs·배포 마무리.
- 결정(ANCHOR §1 / REQ-GC-R7 보존): 참가자는 대화 공통 고정 제품 접근권이 없어도 **본인 권한 제품**으로 per-message 질의 가능. 권한 상속 아님(발신자 본인 RBAC `_account_has_product_access` 게이트). 대화 공통 바인딩 비파괴(PATCH 는 owner 전용 유지). 생성자 제품은 드롭업 '열람 전용' 회색 그룹으로 분리 표시.
- [x] B1 백엔드: `_parse_participant_product_override` + `/api/ask` member 분기 override 적용 + run-product 재게이트(L11571) + backfill skip(L11582)
- [x] B2 백엔드: `_conversation_view_only_products_for` + `/api/session` `conversation_view_only_products` 반환(fail-closed)
- [x] F1 프론트: 드롭업 2그룹 분리("내 제품" + "생성자 제품 열람전용" 회색·비활성) + `buildProductDropupItem` viewOnly 옵션
- [x] F2 프론트: `isParticipantInSharedConversation` + setActiveProduct 로컬-only(PATCH 미호출) + sendPrompt per-message 동봉 + 칩 라벨 fallback(기존 renderProductChip graceful) + `state.conversationViewOnlyProducts` 초기화
- [x] 캐시버스터 bump `20260625-gc-participant-product-select` (app.js·styles.css)
- [x] 검증: node --check + py_compile + CSS brace 1577=1577 + §18.8 적대 authz 패널 6가설 REFUTED SHIP(REV-20260625T163424)
- [x] docs: feature-0003 {TASK,MODIFY,FUNCTION,REVIEW} + feature-0009 {TASK,REPORT,MODIFY,REVIEW,FUNCTION} cross-ref
- [ ] verify-completion → commit → push → PR → 머지 → 배포(included) → PB-0008 실측(배포 후)

## TASK-20260625-role-account-prompt-autogen — 역할 '전체 제품 프롬프트' + 프로필 '제품별 개인 프롬프트' 자동 작성 (Major §12.3 — 외부 LLM dispatch 2개 scope 확장 + 역할 scope 교차사용자 대화 집계)
- 사용자 요청(/_template:entry): "`관리 콘솔 > 역할 > [각 항목] > 제품 사용 > 전체 제품 프롬프트` 와 `작업 화면 > 프로필 > 프롬프트 > [각 제품]` 의 프롬프트 자동 완성 기능 구성. 각 역할의 성격·소속 사용자 대화 내역을 점검해 모범 동작하도록. 각 프로필 프롬프트도 역할·선택 제품·대화 패턴에 따라 모범 작성되도록."
- 결정(AskUserQuestion 2026-06-25): ① 트리거 = **on-demand 버튼만**(자율 sweep 미도입 — 개인 프롬프트 무동의 자동작성·LLM 비용 누수 회피). ② 범위 = **기능만 구성**(엔드포인트·UI·컨텍스트 조립; 실제 seed 역할/프로필 생성·저장은 운영자 라이브 수행).
- 설계: 기존 제품 프롬프트 자동작성(TASK-0309/0237, `scope='product'`)을 role/account 두 scope 로 확장. 컨텍스트 grounding 은 scope 별 차등 — role=역할 성격(정의·권한 특성)+소속 사용자 대화 패턴(집계), account=사용자 역할+선택 제품 용도+본인 대화 패턴(집계). privacy: 원문 메시지가 아닌 **집계 메타(대화 제목·요약)** 만 사용(제품 경로와 동일 house style). role 은 `owner_account_id` 필터(admin `system_prompt.manage.role.any` 게이트), account 는 본인 계정만(self-service). 개인 프롬프트는 제품/역할 프롬프트 위 **선호 레이어**라 스키마 세부 미중복. 스키마/RBAC 카탈로그 변경 0.
- [x] 백엔드(`src/app.py`): `_collect_conversation_signals_pg`(product_id/account_ids 필터 일반화, 빈 account_ids→PG 미접근 누출 가드) · `_describe_role_character`(권한코드→성격 서술) · `_assemble_role_prompt_llm_request` · `_assemble_account_prompt_llm_request`(둘 다 (error,ctx) 동형 계약, prompt_gen cap·temp 0.3).
- [x] 백엔드 엔드포인트 4종: `POST|GET /api/admin/roles/{id}/prompt/generate[/stream]`(role, `system_prompt.manage.role.any`) · `POST|GET /api/auth/me/system-prompt/generate[/stream]`(account, self+product access). 공유 응답 헬퍼 `_prompt_generate_json_response`/`_prompt_generate_stream_response` 추출 — 제품 2개 엔드포인트도 동일 헬퍼로 리팩터(SSE 브릿지 중복 제거, 회귀 0).
- [x] admin.js: `buildSystemPromptEditor` 에 `autoGenerateRoleId` 파라미터 추가 + 역할 '전체 제품 프롬프트' 카드에 '자동 작성' 버튼 + scope-aware meta 렌더(역할 = 소속 사용자·대화주제 기준).
- [x] app.js + index.html: 프로필 프롬프트 탭에 '자동 작성' 버튼(`#generatePromptBtn`) + `generateAccountPrompt()` SSE 핸들러(선택 제품 기준 스트리밍, 생성 후 검토→'저장'; 자동 저장 안 함).
- [x] §18.8 적대 검증 패널(2렌즈: 백엔드+보안/프라이버시, 프론트/UX) — SHIP-WITH-FIXES ×2. **MAJOR 2 흡수**(account 자동작성 quota 게이트 `_check_account_token_quota`=429 · 프로필 에디터 dirty 가드로 자동작성 본문 제품전환 소실 방지) + MINOR 2(재진입 가드 `===controller` app.js·admin.js · `.helper-text-warn` 강조) + NIT(done 스크롤 보존). REVIEW REV-20260625T173000-role-account-prompt-autogen.
- [x] 정적 캐시버스터 bump(`?v=20260625-role-account-prompt-autogen`): index.html styles.css·app.js + admin.html styles.css·admin.js.
- [x] 검증: `tests/test_auto_role_prompt.py`(7) + `tests/test_auto_account_prompt.py`(5) 신규 + 회귀(`test_auto_product_prompt` 12·`test_prompt_generate_stream` 3·`test_prompt_generate_truncation` 4) = **33/33 PASS**(agent 이미지). `py_compile app.py` + ruff(app.py) + `node --check` admin.js/app.js + CSS brace(1572/1572) PASS.
- [ ] **남은 마감(배포)**: verify-completion --pre-commit → commit/push → PR·머지 → web 재배포(deploy_scope: included, static baked + 캐시버스터) → PB-0008 Windows-browser 실렌더(역할 카드·프로필 자동작성 버튼·SSE 스트리밍 — worktree=WSL 미실측, WARN-only).

## TASK-20260625T030242-gc-member-actions-hover — 공유 팝업 참여자 추방/차단 버튼 hover 펼침 + 그리드 컴팩트화 (feature-0009 cross-cut, 코드 거주=feature-0003, Minor §12.3 — frontend CSS-only)
- 사용자 요청(`/_template:entry`, gc-member-kick-ban 후속): ① 추방/차단 버튼을 해당 사용자 hover 시 자연스러운 애니메이션과 함께 펼치기, 단 다른 사용자 UI 위치 불변. ② (1차 세로 스택 제안에 대해) 여백 낭비가 커지니 대안.
- 결정/설계: 참여자/차단 목록을 **반응형 그리드**(`grid-template-columns: repeat(auto-fill, minmax(200px,1fr))`)로 — 셀이 그리드 트랙에 고정돼 한 셀에서 hover 로 버튼이 펼쳐져도(셀 내부에서 이름이 자리 양보) **다른 셀의 위치·구성은 불변**. 평소엔 이름 `flex:1` 으로 셀 폭을 채워 **여백 낭비 0**, 다열이라 세로 길이도 짧음. 액션은 `max-width:0→120px`+`opacity`+`transform` 트랜지션으로 부드럽게 펼침.
- [x] `styles.css` `.share-participants`/`.share-bans` flex-wrap → `display:grid`(auto-fill minmax) + `.share-participant` flex(셀 채움)·`.share-participant-name` `flex:1; min-width:0`(이름 셀 폭 채움+ellipsis) + `.share-participant-acts` 기본 접힘(`max-width:0;opacity:0;pointer-events:none`)→`:hover>`/`:focus-within>` 펼침 + `@media (hover:none)` 터치 폴백.
- [x] `index.html` styles.css 캐시버스터 `20260625-member-actions-hover`(CSS-only — app.js 무변경 미bump).
- [x] 검증: CSS brace 1571=1571 + 신규 `tests/verify_member_actions_hover.mjs` **15/15 PASS**(grid·다열·접힘 기본값·hover/focus 펼침·트랜지션·터치 폴백·캐시버스터). 기존 `verify_member_kick_ban.mjs` 무회귀(구조 무변경 — JS·DOM 불변, CSS만).
- [x] 문서: feature-0003 `{TASK,MODIFY,FUNCTION,REVIEW}.md`(신규 timestamp AC 형식 첫 적용) + feature-0009 `{TASK,MODIFY}.md` cross-ref.
- [ ] **남은 마감(배포)**: verify-completion --pre-commit → commit/push → PR·머지 → web 재배포(deploy_scope: included, static baked + 캐시버스터) → PB-0008 Windows-browser 실렌더(hover 펼침 애니메이션·셀 고정·여백 — worktree=WSL 미실측, WARN-only).

## TASK-20260625T065430-gc-other-msg-left — 그룹대화에서 상대방·assistant 메시지 좌측 정렬, 내 메시지 우측 유지 (feature-0009 cross-cut, 코드 거주=feature-0003, Minor §12.3 — frontend CSS-only)
- 사용자 요청(`/_template:entry`): "그룹대화 시, 자신의 메세지 버블은 똑같이 우측에 출력하고 assistant와 상대방의 대화는 좌측에 출력하도록 구성해주세요."
- 설계/판정: app.js `renderMessages()` 가 이미 발신자 귀속으로 메시지에 `is-own-message`(내 메시지)/`is-other-message`(타 참여자)/`is-assistant` class 를 정확히 부여하고 있음 → **JS 무변경**, styles.css 의 정렬 규칙만 분기. 기존 `.message.is-user`(0,2,0)가 own/other 무관 `align-self:flex-end`(우측)이던 것을 `.message.is-user.is-other-message`(0,3,0) override 로 other 만 `flex-start`(좌측)로. 그룹채팅 관례(내=우측/타인=좌측)와 정합, assistant 와 좌측 기준선 통일.
- [x] `styles.css` 신규 `.message.is-user.is-other-message { align-self: flex-start; align-items: flex-start; }` (상대방 메시지 좌측) + `.message.is-user.is-other-message .message-bubble` 에 `border-bottom-right-radius:14px; border-bottom-left-radius:var(--r-xs)`(꼬리 좌측 하단화). `is-own-message`·`is-assistant`·멘션 하이라이트 규칙 무변경.
- [x] `index.html` styles.css 캐시버스터 `20260625-gc-other-msg-left`(CSS-only — app.js 무변경 미bump).
- [x] 검증: `node --check static/app.js` PASS(JS 무변경 확인) + CSS brace 균형(1573=1573) + **충실한 mock 렌더**(실 styles.css 링크 + `renderMessages()` DOM 구조 5 row 재현, Chromium headless): 버블 좌/우 여백 측정 — own=rightGap 25(우측), other·assistant=leftGap 25(좌측 동일 기준선), 멘션 상대방 좌측+주황 강조선. 증거 `artifacts/pb0008-gc-other-msg-left/bubble-align-result.png`.
- [x] 문서: feature-0003 `{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md` + feature-0009 `{TASK,MODIFY,REPORT}.md` cross-ref.
- [ ] **남은 마감(배포)**: verify-completion --pre-commit → commit/push → PR·머지 → web 재배포(deploy_scope: included, static baked + 캐시버스터) → PB-0008 Windows-browser 실렌더(실 그룹대화 다수 참여자 — worktree=WSL 미실측, WARN-only).

## TASK-20260625T020249-admin-metadata-relocate — 관리 콘솔 사이드바 IA: '메타데이터' 탭을 '감사' 그룹에서 신설 '지식베이스' 그룹으로 재배치 (+ '샘플 검수' 동반 이동) (Minor §12.3 — 정적 DOM 재배치, JS/CSS/RBAC/스키마 무변경)
- 사용자 요청(`/_template:entry`): `관리 콘솔`의 '메타데이터' 탭이 '감사'에 위치하는 게 어색 — `시스템 > 설정 > 메타데이터` 로 이동 검토·적용 + 더 좋은 구조도 검토. **IA 결정(AskUserQuestion)**: 사용자 원안('시스템' 그룹 이동) 대신 신설 '지식베이스' 그룹으로 메타데이터+샘플 검수를 묶음(둘 다 KB 거버넌스·kb.* 권한, '감사'=읽기전용 모니터링과 성격 상이). 결과 순서: [감사: 감사 로그·LLM 사용량·보관 대화] → [지식베이스: 메타데이터·샘플 검수] → [시스템: 설정·릴리즈 노트].
- [x] `src/static/admin.html`: '감사' 그룹에서 `data-admin-tab="metadata"`/`"sample-review"` 버튼 제거 → 신설 `<div class="admin-tab-group-divider">`+`<div class="admin-tab-group-label">지식베이스</div>` 아래로 메타데이터→샘플 검수 순 재배치. 버튼 `data-admin-tab`/`id`/`style="display:none"` 속성 보존.
- [x] 회귀 분석: `admin.js` `applyAdminTabVisibility()`(그룹 경계=DOM순서 동적계산)·`ADMIN_TAB_PERMISSIONS`(키 기반)·`switchTab()`(`data-admin-pane` 매칭)·클릭 바인딩(`data-admin-tab`) 전부 그룹 위치 비의존 확인 → admin.js/styles.css/백엔드/RBAC/스키마/pane 본문 **무변경**. 권한 게이팅(metadata=kb.ingest.manual∪kb.sample.curate, sample-review=kb.sample.curate)·그룹 자동숨김 불변.
- [x] **§18.8 적대적 3-렌즈(권한게이팅 회귀·IA정합·접근성) 서브에이전트 리뷰 — BLOCKER/MAJOR 0, SHIP**. MINOR 1(사이드바 '지식베이스' vs 권한그리드 admin.js:167 `kb:"지식베이스(KB) 검수"` 용어 미세 불일치 — ship 차단 아님, 후속 용어통일 추적). REV-20260625T020249-admin-metadata-relocate.
- [ ] **남은 마감**: verify-completion --pre-commit → commit/push → PR·머지 → web 재배포(deploy_scope: included, static baked) → PB-0008 Windows-browser UI 실렌더 검증(worktree=WSL 미실측, WARN-only — 지식베이스 그룹 위치·권한별 가시성).
## TASK-20260625T020410-gc-member-kick-ban — 공유 팝업: 소유자가 참여자 추방(kick)/차단(ban)/해제(unban) (feature-0009 cross-cut, 코드 거주=feature-0003+0002, Critical §12.3 — 접근제어)
- 사용자 요청(`/_template:entry`, share-participants 후속): `작업 화면 > 대화 탭 > ··· > 공유` 팝업에서 소유자가 특정 참여자를 kick/ban 처리하는 구조.
- 사용자 결정(AskUserQuestion): ① 권한 주체 = **엄격 owner 전용**(conversation.member.manage 보유자도 불가) ② unban + '차단된 사용자' 목록 UI **포함**(가역 설계).
- 설계: 추방(kick)=기존 `DELETE /members/{id}`(owner 의 타인 제거 경로) 재사용(재참여 가능). 차단(ban)=멤버 제거 + 신규 `conversation_member_bans` 등재 → `POST /share/{token}/join` 의 is_banned 게이트로 재참여 영구 차단. 해제(unban)=ban 목록에서 제거.
- [x] 스키마: `agent_runtime.conversation_member_bans`(PK conversation_id+account_id, banned_at/by/reason, FK CASCADE) — schema.sql + alembic `0018`(down `0017`, **GRANT rw/ro 명시** deploy-trap 회피). (feature-0002)
- [x] 코어 `group_members.py`: `ban_member`(ON CONFLICT 멱등, reason 512cap)·`unban_member`(rowcount)·`is_banned`(빈인자 단락)·`list_bans`(isoformat 직렬화). 전 SQL `%(...)s` 파라미터화. (feature-0002)
- [x] 백엔드(app.py) 신규 엔드포인트 — **엄격 owner 전용**(`_conversation_owned_by_account`, manage 분기 없음): `POST /members/{id}/ban`(remove+ban+audit `conversation.member.ban`, owner/self/<=0 가드, ban 먼저→remove 나중 fail-safe), `DELETE /members/{id}/ban`(unban+audit), `GET /conversations/{cid}/bans`(차단목록 + username join). `POST /share/{token}/join` 에 is_banned 게이트(403 + audit `join_blocked`, fail-closed).
- [x] 프론트(app.js·styles.css·index.html): 공유 팝업 참여자 칩에 owner viewer 전용 '추방'/'차단' 버튼(대상이 소유자 아닐 때만) + '차단된 사용자' 섹션(owner 전용 노출 + '차단 해제'). viewer=owner 판정 = `state.user.id === owner_account_id`. confirm + 토스트 + roster/bans 갱신. 캐시버스터 `20260625-member-kick-ban`.
- [x] **§18.8 적대적 보안/authz 패널 — BLOCKER 1 적발·수정**: `public_share_fork` 가 차단된 account 의 fork(콘텐츠 exfiltrate)를 안 막던 우회 → fork 에 is_banned 게이트(403 + audit `fork_blocked`, fail-closed) 추가. MINOR 3(비원자 커밋 순서 역전·target<=0 가드·join fail-closed)·NIT 흡수. 재검증 **잔여 결함 0**(다른 fork 경로 2곳은 `_account_can_access_conversation`로 차단 비-멤버 404 — 우회 없음). REV-20260625T020410-gc-member-kick-ban.
- [x] 테스트: `test_member_kick_ban.py`(feature-0002, ban 함수 8) + `test_member_ban_endpoints.py`(feature-0003, ast 계약 5 — owner-only·가드·fork BLOCKER·join 순서) + `verify_member_kick_ban.mjs`(프론트 정적 19) + 회귀(group_members 10·share-participants 17·settings-archive-leave 22). py_compile + node --check + CSS brace 1561=1561.
- [x] 문서: feature-0003 `{TASK,MODIFY,FUNCTION,REVIEW}.md` + feature-0002 `{MODIFY,FUNCTION}.md` + feature-0009 `{TASK,MODIFY}.md` + docs/SECURITY.md 멤버 차단 접근제어.
- [ ] **남은 마감(배포)**: verify-completion --pre-commit → commit/push → PR·머지 → web 재배포(deploy_scope: included) + **alembic 0018 적용**(superuser + GRANT) → PB-0008 Windows-browser 실렌더(추방/차단/해제/재참여 거부 — worktree=WSL 미실측, WARN-only).

## TASK-20260624-metadata-ai-autocomplete — 관리 콘솔 메타데이터 5 서브뷰 AI 자동완성(단건+골격 일괄) + pane 스크롤 수정 (중단 세션 resume, Major §12.3 — 외부 LLM dispatch + 서브뷰별 RBAC)
- 출처: 사용자 요청(entry persona) "관리 콘솔 > 메타데이터를 실제 관리자가 처음 쓰기 까다롭다 — 모든 탭에 AI 자동완성" + "창이 길어지면 스크롤이 없어 하단 항목을 못 본다". 원본 세션이 session limit 으로 프론트 일괄 함수 삽입 직후 중단 → 본 cycle 이 resume 으로 잔여(CSS·테스트·docs·panel·게이트) 완수.
- 범위: feature-0003 web only. 마이그 없음, agent-core·gateway·credential·ROADMAP 무변경. 기존 metadata 거버넌스(ITEM-11) 폼/부트스트랩에 AI 채움 버튼 추가.
- [x] 백엔드(기 작성, 미커밋): suggest(단건 5 서브뷰)·bootstrap/describe(골격 일괄) 엔드포인트 + 헬퍼(grounding/프롬프트/JSON parse/shape/LLM). RBAC 서브뷰별(samples=kb.sample.curate, 나머지=kb.ingest.manual). 영속 안 함.
- [x] 프론트(기 작성, 미커밋): `_metaSuggestFill`·`_metaBootstrapAiFill`·`_metaBootstrapApplyDescriptions` + 버튼 2개. XSS input.value. dataset.bound 가드.
- [x] CSS: metadata pane `overflow-y:auto`(스크롤 수정 — dashboard 동형, 타 pane 무영향) + `.admin-meta-ai-btn` 강조. cache-buster bump(`?v=20260624-metadata-ai-autocomplete`).
- [x] 테스트(신규 18): RBAC·라우팅·입력검증·정상(definition/nl_question)·cap·LLM오류·bootstrap 정형·parse 단위 + sql cap·rate-limit 429. 18/18 PASS.
- [x] §18.8 panel(2-lens 적대): backend BLOCKING 2건(sql cap·rate-limit) 적발→수정+회귀가드, frontend SHIP. REV-20260624T170757.
- [ ] verify-completion → commit(Task-Cycle trailer) → push → PR → 머지 → web 재배포(deploy_scope: included) → PB-0008(5 서브뷰 AI 버튼 동작 + 스크롤) → 마감.
## TASK-20260624T075458-gc-share-participants — 공유 팝업에 '참여 중인 사용자' roster 표시 (feature-0009 cross-cut cycle, 코드 거주=feature-0003, Minor §12.3)
- 사용자 요청(`/_template:entry`): `작업 화면 > 대화 탭 > '···' > 공유` 팝업에서, 해당 공유대화에 참석 중인 사용자 목록도 같이 UI에 출력. cycle owner=feature-0009(group-conversation), 코드/정본 문서=feature-0003.
- 해석: "참석 중인 사용자" = feature-0009 멤버십 모델의 그룹 대화 멤버(roster). live-presence(현재 접속) 개념은 제품 미구현(추가 시 Redis/세션 추적 필요 — out of scope). → 기존 멤버 roster 재사용이 정합.
- [x] `app.js` `openShareDialog`: 팝업 골격에 '참여 중인 사용자' subhead + `.share-participants` 컨테이너 추가 + 신규 `loadParticipants()` 헬퍼. 기존 게이트된 `GET /api/conversations/{cid}/members`(conversation.read.own/.any + 멤버십) **재사용 — 신규 백엔드/엔드포인트/스키마/RBAC 0**.
- [x] roster 렌더: owner 우선 정렬 + '소유자' 배지, 아바타는 기존 `_msgAvatarEl`(아바타→Identicon 폴백) 재사용, 사용자명 `textContent`(XSS 안전), 빈/로딩/에러 상태 처리. 초기 로드 + joinable 링크 생성 직후(`_ensure_owner_membership` 로 owner 멤버십 보장) roster 갱신.
- [x] `styles.css` `.share-participant*` 칩 스타일(`max-height:132px; overflow-y:auto` 스크롤 cap) + `index.html` app.js/styles.css 캐시버스터 `20260624-share-participants`.
- [x] `node --check app.js` PASS + CSS brace 균형(1549=1549) + 신규 `tests/verify_share_participants.mjs` **17/17 PASS**(섹션·헬퍼·엔드포인트 재사용·owner 정렬·XSS textContent·빈/에러 상태·갱신 배선·CSS·캐시버스터).
- [x] **§18.8 적대적 3-렌즈(security·authz / correctness / UX) 서브에이전트 리뷰 — BLOCKER/MAJOR 0**. 반영: ① 주석 정정(공유 메뉴 게이트=share.create vs members=read 비대칭 명시, read 불가 actor 는 members 404→catch 우아 처리, privacy 신규 노출 없음) ② `.share-participants` 스크롤 cap(참여자 多 시 패널 압박) ③ 빈상태 문구 정정("다른 사용자"). XSS·use-after-close·race·owner null·빈 username 모두 방어 확인. REVIEW REV-20260624T075458-gc-share-participants.
- [x] 문서: feature-0003 `{TASK,MODIFY,FUNCTION,REVIEW}.md` + feature-0009 `{TASK,MODIFY}.md` cross-ref.
- [ ] **남은 마감(배포 후)**: verify-completion --pre-commit → commit/push → PR·머지 → web 재배포(deploy_scope: included, static baked + 캐시버스터) → PB-0008 Windows-browser UI 실렌더 검증(worktree=WSL 미실측, WARN-only).

## TASK-20260624-scope-key-unify — 메타데이터/샘플 admin scope_key 축을 read 축으로 통일 (ds-scoped 死data 수정 + RISK/NIT) (REQ-20260624-scope-key-unify, AC-0618~0619, Major §12.3 — scope 경계, ITEM-10/11/03 공유 admin 경로)
- [x] 死data 확정: `/_template:resume` ITEM-11 Phase 2 작동검증 중 구조 감사(4 dim)가 scope-key 축 불일치 적발 → 라이브 재현(라벨 'mysql-local' 저장 → 질의시점 해시 'mysql-ddae8975d793' 읽기 MISS). 배포 DS 20+ 전부 WebDatasources(.env 0개), KB 테이블 전부 0행(손실 데이터 없는 잠복).
- [x] fix: app.py `_metadata_valid_scope_keys`(라벨→`ds.get('scope_key') or ds.get('key')` read축) + `/api/admin/datasources` 응답 scope_key(read축) 노출 / admin.js scope 드롭다운 value=read축·표시=라벨. read(feature-0002 agent_core/kb_metadata/insight) 무변경(이미 해시) — write 를 read 에 맞춤.
- [x] RISK 해소: 메타데이터 탭 게이트 `kb.ingest.manual` → `+kb.sample.curate` OR. NIT 해소: bootstrap 저장 payload `source:'bootstrap'`. cache-buster `20260624-scope-key-unify`.
- [x] **§18.8 적대 패널 2-lens — 첫 fix(`_dsr.scope_key`)의 .env 축 반전 BLOCKER 적발** → 교정(read 동일식 미러링) → 재확인 agent RESOLVED(7항목 PASS, BLOCKER/MAJOR 0). REV-20260624T160000-scope-key-unify [SUBAGENT:scope-key-unify-review] SHIP.
- [x] 테스트: phase2 29(scope 양방향 회귀 2 신규: DB=해시·.env=라벨) + glossary/enum 13(_allow_scopes fake 갱신) + flywheel 12 PASS. py_compile + node --check.
- [ ] **남은 마감**: verify-completion --pre-commit → commit/push → PR·머지 → web 재배포(deploy_scope: included) → 死data 수정 라이브 재검증.

## TASK-20260624-item11-phase2 — 메타데이터 거버넌스 포탈 Phase 2 (테이블/컬럼 설명+주입+부트스트랩 / 샘플 admin) (REQ-20260624-item11-phase2, AC-0614~0617, ROADMAP dba-ai-nl2sql ITEM-11 Phase 2 → ITEM-11 done, Major §12.3 — 보안 경계, PLAN-APPROVED 2a+2b)
- [x] backend(feature-0002 cross-feature): 신규 테이블 `table_descriptions`/`column_descriptions`(agent_kb_schema.sql + alembic 0017, 멱등·단일 head·GRANT rw/ro) + `modules/kb_metadata.py`(read `load_table_column_descriptions` / overlay `load_column_descriptions_for_table` / admin CRUD 6함수, id+scope_key 가드·ON CONFLICT) + `sample_queries.py`(list/update/delete admin, 하이브리드 C) + `agent_core.py` 설명 datamark 주입 + `tools.py` describe_table overlay(빈 comment 충전).
- [x] frontend(feature-0003): `/api/admin/metadata/{tables,columns}`(kb.ingest.manual) + `/samples`(kb.sample.curate, POST 없음) + `/bootstrap/schemas`·`/bootstrap`(kb.ingest.manual) 엔드포인트 + admin "메타데이터" 탭 테이블/컬럼/샘플 3 서브뷰 + 부트스트랩 UI(DS→schema→골격→prefill→저장). XSS textContent. cache-buster `?v=20260624-item11-phase2`.
- [x] 테스트 `tests/test_metadata_phase2.py` 27케이스(RBAC 403·scope 400/격리·affected 404·멱등·audit·입력 cap·샘플 weight clamp·nl 중복 409·임베딩 3분기·부트스트랩 RBAC/DS/**SQLi 거부**·주입 datamark) → **27/27 PASS**. MVP-1 회귀 13/13 + sample_flywheel 회귀 12/12 PASS.
- [x] **§18.8 적대적 검증 패널 2회 — REV-20260624T133000-item11-phase2 [SUBAGENT:item11-phase2-backend+security+injection] SHIP**: 1차(구현 세션) BLOCKER B1(부트스트랩 SQLi)+MAJOR M2(alembic 위치) 적발→본 cycle 흡수, 2차(resume 재검증, 최종 staged) 3-lens 전원 SHIP·BLOCKER 0. 회귀 0.
- [x] 정본 docs(MODIFY/REVIEW/FUNCTION/TASK/REPORT + feature-0002 cross-ref MODIFY) + ROADMAP ITEM-11→done 갱신.
- [ ] **남은 마감**: verify-completion --pre-commit PASS → commit/push(auto-sync) → PR 생성·머지 → web+ask-worker 재배포(deploy_scope: included, 마이그 0017 적용) → PB-0008 Windows-browser UI 시각검증(배포 후, WARN-only).

## TASK-20260624T031337-gc-settings-archive-leave — 대화 ··· 메뉴 '보관' → 설정 팝업 이동 + 그룹 참여자 '나가기' (feature-0009 cross-cut cycle, 코드 거주=feature-0003, Minor §12.3)
- 사용자 요청: `대화 탭 > ··· > [탭 목록]` 의 '보관'을 '설정' 팝업 내부로 구성 + 보관 권한 없는 그룹 대화 참여자는 보관 대신 '나가기' 버튼. cycle owner=feature-0009(group-conversation), 코드/정본 문서=feature-0003.
- [x] `app.js` `openConversationItemMenu`: ··· 메뉴에서 '보관'(danger) 제거 → [공유 · 설정].
- [x] `app.js` `openConversationSettings`: 하단 '대화 관리'(`.conv-settings-sec-danger`) 섹션 — `canDeleteConversation`(보유자/admin)→'보관'(`deleteConversation`), 아니면서 `isGroupConversation`→'나가기'(신규 `leaveConversation`), 둘 다 아니면 미렌더.
- [x] `app.js` 신규 `leaveConversation(cid)`: `DELETE /api/conversations/{cid}/members/{state.user.id}` self-leave(백엔드 `remove_conversation_member` 기존·무변경) + confirm + 토스트 + `refreshWorkspace("")`.
- [x] `styles.css` `.conv-settings-sec-danger`/`.conv-settings-danger-btn` + `index.html` 캐시버스터 `archive-leave`.
- [x] `node --check app.js` PASS + 신규 `tests/verify_settings_archive_leave.mjs` **22/22 PASS** + 적대적 3-렌즈(security/authz·correctness·UX) 서브에이전트 리뷰 **실질 결함 0**(REVIEW REV-20260624T031337).
- [x] 문서: feature-0003 `{MODIFY,FUNCTION,REVIEW,TEST}.md` + feature-0009 `{TASK,MODIFY,REVIEW}.md` cross-ref.
- [ ] **남은 마감(메인 세션/배포 후)**: PB-0008(Windows-browser UI 실렌더 — worktree=WSL 미실측) · PR 생성·머지·web 재배포(static baked + 캐시버스터).

## TASK-20260623T090440-sample-feedback-curation (current cycle) — 답변 피드백 → 샘플쿼리 KB 환류 flywheel (web 층, ROADMAP dba-ai-nl2sql ITEM-03, REQ-20260623-0333, AC-0612·0613, Major §12.3 — 보안 경계)
- **PLAN-APPROVED** (사용자, 2026-06-23). 임무: ROADMAP dba-ai-nl2sql ITEM-03(피드백→KB 환류 flywheel 의 web 층)을 feature-0003 worktree 에 구현. 코어(feature-0002 `modules.sample_feedback`)는 재사용(재구현 금지) — web 은 RBAC/audit/scope/cross-DB conn 분리 경계만.
- 등급: **Major §12.3 — 보안 경계(신규 RBAC `kb.sample.curate`)**. 신규 RBAC = 보안 표면 → 메인 세션이 적대적 security 리뷰 후 마감(본 cycle 은 구현+단위검증+verify+commit/push 까지).
- [x] 신규 RBAC `kb.sample.curate`(group kb, label "샘플 검수/승급") — PERMISSION_DEFINITIONS 추가. admin seed 자동 보유 / operator·sales·pending 미부여. 종속성 console.access.
- [x] 사용자 피드백 endpoint POST `/api/conversations/{cid}/sample-feedback`(대화 접근 검증 + ds-scope 도출(`_conversation_scope_key`: pinned product→_resolve_product_insight_scope.scope, 폴백 'common') + PG `record_feedback` + best-effort audit `sample.feedback.submit`). body {vote,suggested,nl_question,generated_sql?}.
- [x] 검수 큐 admin endpoints 3종(RBAC kb.sample.curate): GET `/api/admin/sample-feedback`(list_pending_feedback, RO PG) · POST `/api/admin/sample-feedback/{id}/approve`(promote_feedback, audit `sample.feedback.approve`, sample_id=None→409) · POST `/api/admin/sample-feedback/{id}/reject`(reject_feedback, audit `sample.feedback.reject`). PG(작업)+memory(auth/audit) conn 분리, PG write autocommit=False(원자성). 승급=명시 호출만(자동학습 금지).
- [x] UI: `app.js` 답변 말풍선 👍/👎/"샘플 등록" 버튼(클릭→적재 POST, 성공 시 비활성). `admin.js`+`admin.html` "샘플 검수" 탭(ADMIN_TAB_PERMISSIONS["sample-review"]=["kb.sample.curate"] + 큐 + 승인/거부). kb 그룹 메타(GROUP_ORDER/LABELS·ADMIN_PERMISSION_SECTIONS·PERMISSION_DEPENDENCIES). cache-buster 갱신.
- [x] 테스트 `tests/test_sample_feedback_curation.py` 15케이스(R1·R2 카탈로그/seed · S1~S3 미보유 403+코어 미호출 · U1 404 · U2 적재+audit · A1~A3 승급/409/거부+audit · L1 직렬화 · SC1 scope). 라이브 DB 불요(FakeConn/monkeypatch — test_insight_reset.py mock 패턴 답습). 15/15 PASS.
- [x] 회귀: test_permission_dependency_map.py(신규 deps 자동검증)·test_insight_reset.py·test_audit_rbac.py·test_admin_me_rbac.py PASS. full feature-0003+0002 suite 회귀 0(사전존재 실패 9건=product-delete·share-redaction 은 baseline stash 비교로 무관 확인). node --check + CSS brace balanced + py_compile.
- [x] unit 문서(TASK/MODIFY/FUNCTION/ANCHOR/REVIEW) → verify-completion --pre-commit PASS → commit + push(auto-sync).
- [x] **적대적 security 리뷰(신규 RBAC 경계) — REV-20260623-0334 SHIP-WITH-FIXES**: MAJOR-1(피드백 rate-limit)·MAJOR-2(promote FOR UPDATE, feature-0002 cross-ref)·MINOR-1(nl_question PII)·NIT-1 흡수. 회귀 0(27 통과).
- [ ] **남은 마감(메인 세션)**: PB-0008(Windows-browser UI 실렌더 — WARN-only) · PR 생성·머지·배포. titan-embed(bge-m3 1024) 복구됨 → 적재·승급·주입 e2e 가능.

## TASK-20260623T031910-ai-claude-ds-conn-bg-decouple — 관리 콘솔 > 제품: 데이터소스 연결확인을 동기 render 경로에서 백그라운드로 분리 (REQ-20260623-ds-conn-bg-decouple, Major §12.3)
- 보고(사용자, /_template:entry, 2026-06-23): `관리 콘솔 > 제품 > [각 항목]` 진입 시 연결이 불안정한 데이터소스 항목에 접근하면, 해당 데이터소스 연결이 timeout 될 때까지 나머지 UI 갱신이 진행되지 않음. → 모든 연결 확인을 백그라운드로 처리하고, 내부 UI 갱신 중 서비스 내부로 작동하는 부분과 분리.
- 등급: **Major §12.3** — 관리 콘솔 동작 변경 + async 리팩터(다중 파일). read-side 조회(DB 목록 열거)라 인증/데이터/스키마 영향 0 → Critical 아님.
- 범위 결정(AskUserQuestion, 사용자 2026-06-23): **전체 분리(Layer 1+2)** — 이벤트 루프 차단 해소 + 백그라운드 conn_health 캐시 게이트 + 프론트 비차단 렌더/캐시 배지.
- 진단: ① `app.py admin_datasource_databases`(GET `/api/admin/datasources/{key}/databases`, 제품 항목 진입 시 `_refreshAccessibleDbs` 가 호출)가 **`async def` 안에서 동기 `_db.list_server_databases_classified()`**(live connect, db.py 기본 8s timeout)를 `asyncio.to_thread` 없이 호출 → **FastAPI 이벤트 루프 전체를 8s 블록** = 그동안 모든 요청 정지("나머지 UI 갱신 멈춤"의 정체). ② 같은 동기-블록이 `admin_preview_product_db_rule`(preview) + rule create/update 의 `_reconcile_one_db_rule`(둘 다 `async def` 에서 동기 호출)에도 존재. ③ 백그라운드 `conn_health` 모니터(TASK-0250, 캐시 3-state)가 이미 있는데 이 경로가 안 쓰고 매번 live connect + circuit breaker `should_fast_fail` 은 `down` 만 즉시실패·`unstable` 은 8s 대기.
- 수정: (a) backend `app.py` — `admin_datasource_databases`: SSRF 후 `conn_health.status_for(ds)` 캐시 먼저 읽어 `unstable`/`down` 이면 live connect 생략·`{degraded:true, conn_status}` 즉시 반환(`?force=1` 시에만 실제 열거), 실제 열거는 `await asyncio.to_thread(...)` 로 오프로드 + 실패 시 `record_foreground_result(False)` 피드백. preview + rule create/update 의 reconcile 호출을 `await asyncio.to_thread(...)` 로 오프로드. (b) frontend `admin.js` — `_refreshAccessibleDbs(key, {force})` 가 `degraded` 응답 처리(빈 목록 + `_setAccessDbDegraded` 배너 "연결 불안정/끊김 — DB 목록 보류 + [새로고침]" → `?force=1` 재시도), 제품 상세는 기존대로 즉시 렌더(fire-and-forget). (c) `styles.css` `.admin-db-degraded-note`/`.admin-db-degraded-refresh`. **비변경**: `_reconcile_one_db_rule` 내부 로직(M3/M4/M5)·RBAC·스키마·엔드포인트 shape·conn_health 모듈·`/db-insights`(sync def → 이미 threadpool) 0.

### §2.1 Implementation Plan (PLAN)
- 영향 파일: `unit/feature-0003-agent-web-ui/src/app.py`(3 async 경로) · `src/static/admin.js`(`_refreshAccessibleDbs`+`_setAccessDbDegraded`) · `src/static/styles.css`(배너).
- 변경 symbol: `admin_datasource_databases`, `admin_preview_product_db_rule`, `admin_create_product_db_rule`, `admin_update_product_db_rule`(app.py); `_refreshAccessibleDbs`/신규 `_setAccessDbDegraded`(admin.js).
- 접근: 동기 live-connect 를 `asyncio.to_thread` 로 이벤트 루프 밖으로 + 렌더 경로(#1)는 백그라운드 `conn_health` 캐시 게이트로 불안정/끊김 시 connect 생략.
- 완료 판정(acceptance):
  1. 불안정/끊김 데이터소스 제품 항목 진입 시 다른 UI 갱신/요청이 8s 멈추지 않는다(이벤트 루프 비차단).
  2. 불안정/끊김 데이터소스의 DB 목록 호출이 live connect 없이 캐시 상태로 즉시(<100ms) 반환된다(`degraded:true`).
  3. `?force=1`(새로고침) 시에만 실제 열거를 시도하고, 그 connect 도 이벤트 루프 밖에서 수행된다.
  4. 정상 데이터소스의 DB 목록 동작·기존 응답 shape(`databases`/`databases_classified`)는 무회귀(필드 추가만).
- 위험도: Major §12.3.
- 검증: `py_compile app.py` PASS · `node --check admin.js` PASS · CSS brace balance · conn_health 모니터 web startup 와이어링 + scope_key 정합 확인. (PB-0008 Windows-browser 시각검증은 배포 후.)
- [x] 구현(backend `app.py` 3 async 경로 to_thread + `admin_datasource_databases` conn_health 캐시 게이트 + `?force=1`; frontend `admin.js` degraded 배너 + force 재시도; `styles.css` 배너; `admin.html` 캐시버스터) + `py_compile app.py`·`node --check admin.js`·CSS brace balance PASS.
- [x] §18.8 적대적 검증 패널 → **SHIP**(REV-20260623T031910 [SUBAGENT:frontend-degraded-banner + AI-inline:backend-async-correctness]; frontend NO REAL ISSUES, backend inline 7축[conn 핸드오프·scope_key·startup·shape·foreground feedback·게이트·잔여 connect] 무결; minor a11y `role="status"` 반영).
- [x] verify-completion --pre-commit PASS(9) → 머지(PR #374, main `b2236fe`; base-behind rebase 충돌해소 admin.html 캐시버스터·FUNCTION.md append keep-both) → web 재배포(deploy_scope: included, `docker compose build web`+`up -d --no-deps web`, repo-web-1 Up healthy, 서빙 `admin.js?v=20260623-ds-conn-bg-decouple`·conn_health 게이트·to_thread baked) → **PB-0008 Windows-browser PASS**(실 Chrome/149: ①이벤트 루프 비차단 — down `?force=1` 8024ms 블록 중 동시 healthy 44ms 완료 ②degraded fast-path 38ms `degraded:true` ③healthy 무회귀 db14 ④시각 배너 "연결 끊김 — DB 목록 보류 + 새로고침"(`role=status`, 제품95 건즈국내QA) ⑤force 버튼 disabled→확인중→재활성). evidence `artifacts/pb0008-ds-conn-bg-decouple/{degraded-banner-down-ds,healthy-product-no-banner}.png`. **cycle 완료.**

## TASK-20260619T120000-ai-claude-db-rule-pending-batch — 정규식 자동 규칙 편집을 pending → "모두 적용" 으로 재배선 (REQ-20260619-0331, AC-0609, Major §12.3 — 보안 경계)
- 보고(사용자, /_template:entry, 2026-06-19): "관리 콘솔 내에서 작업되는 모든 변경은 pending 후 일괄적용으로 구성되도록 정책에 검증과정 명시 + 프로젝트 메모리 기억." + `관리 콘솔 > 제품 > [각 제품] > '데이터 소스 & 접근 가능 데이터베이스' > 정규식 자동 규칙` 수정 시 **별도 Pending 없이 즉시 반영**됨을 확인.
- 등급: **Major §12.3** — 접근 가능 DB allowlist(보안 경계) 변경 경로 + 의도된 "안전 하이브리드(outside-voice B1)" 설계를 시정. 비파괴(스테이징 모델 추가, 엔드포인트/스키마 무변경).
- 범위 결정(AskUserQuestion, 사용자 2026-06-19): **범위 A** — 규칙 *편집 동작*(추가/수정/삭제/승인)만 pending 화하고, 확정된 규칙의 *백그라운드 자동 동기화*(잦은 DB 변경 자동 반영, 과거 요청 기능)는 보존. (범위 B = allowlist 변경 전부 pending·자율성 제거 는 미채택.)
- 진단: ① `admin.js` 규칙 에디터(`cov-db-rule`, TASK-20260618T044318)의 add/edit/delete/approve 핸들러가 클릭 즉시 `apiFetch(POST/PUT/DELETE/approve-pending)` → 즉시 reconcile → allowlist 즉변. ② `app.py` GET `/db-rules` 가 `trigger="view"` lazy reconcile → **조회만으로 GRANT**. 둘 다 전역 pending → "모두 적용" 모델(admin.js "pending changes + bulk commit", TASK-0029/0239) 우회.
- 수정: (a) frontend `admin.js` — `adminState.pending.productDbRules`(키 `productId::dsKey`, ops creates/updates/deletes/approves) + helpers(`_ensureDbRulePending`/`_settleDbRulePending`/`productDbRuleDirtyCount`/`_getDbRulePending`) + `pendingChangeCount`·`refreshPendingUI`·`buildPendingWidgetBody`·`cancelAllPending`·stale GC 통합 + 규칙 에디터 핸들러를 스테이징으로 재배선 + 카드 optimistic 오버레이(추가/수정/삭제/승인 대기 배지·취소) + `applyAllPending` replay(creates→updates→approves→deletes). (b) `styles.css` staged 배지 스타일. (c) `admin.html` 캐시버스터 `?v=20260619-db-rule-pending`. (d) backend `app.py` — GET `/db-rules` 의 view-trigger reconcile 블록 제거(조회=무변경). **비변경**: rule reconcile/preview 로직·백그라운드 루프·RBAC·스키마·엔드포인트 shape 0.
- 정책: `docs/CONVENTIONS.md §10.7`(변경 적용 모델 — Pending → 일괄 적용 강제 + 검증 체크리스트 + 자율 동기화 carve-out) 신설. 프로젝트 메모리 `project_admin_pending_batch_apply.md`.
- 검증: `node --check admin.js` + `py_compile app.py` + CSS brace balance + 신규 `tests/verify_db_rule_pending.mjs` **jsdom 18/18 PASS**(스테이징 시 쓰기 0 / "모두 적용"만 쓰기 / 엔드포인트·body·순서·정리) + make test(컨테이너). worktree `ai/claude/db-rule-pending-batch`(base 28e76d6).
- 완료 체크리스트:
  - [x] frontend staging(`productDbRules`) + helpers + `applyAllPending` replay + optimistic 렌더
  - [x] backend GET `/db-rules` view-reconcile 제거(조회=무변경)
  - [x] CSS staged 배지 + 캐시버스터(admin.js·styles.css) bump
  - [x] 단위 테스트: `verify_db_rule_pending.mjs` 18/18 + `verify_db_rule_ui.mjs` 19/19 + `verify_db_rule_logic.py` 30/30 + node --check + py_compile + CSS brace
  - [x] §18.8 적대적 검증 패널(서브에이전트) → SHIP, REVIEW.md `[SUBAGENT:db-rule-pending-security]` 기록
  - [x] CONVENTIONS.md §10.7 + 프로젝트 메모리 + feature 문서 6종
  - [ ] 머지 전 main(+21 commit) rebase
  - [ ] 머지 → web 재배포(deploy_scope: included)
  - [ ] PB-0008 Windows-browser 시각검증(규칙 편집 대기 배지 + "모두 적용" 일괄 반영 + 조회만으로 미반영)

## TASK-20260618T061520-ai-claude-release-notes-scope-scroll — 릴리즈 노트: 작업 화면서 관리 콘솔 영역 숨김 + 관리 콘솔 pane 스크롤 (REQ-20260618-0323, AC-0582·0583, Minor §12.3)
- 보고(사용자, 2026-06-18): ① 작업 화면에서는 관리 콘솔에 대한 릴리즈 노트를 숨겨 달라. ② 관리 콘솔에서 릴리즈 노트 스크롤이 없어 하단 항목을 볼 수 없다.
- 등급: **Minor §12.3** — frontend-only(렌더러 옵션 + 호출 1 + CSS 1규칙 + 캐시버스터). 백엔드·RBAC·스키마·데이터 0. 비파괴.
- 수정:
  - `src/static/release-notes.js`: `render(container, opts)` 에 `opts.areas` 화이트리스트 신설 — items 를 allowed area 로 선필터+빈 일자 그룹 제거, 필터 칩도 allowed 영역만(전체 + 해당 영역). 기본=전체(work/admin/common, 관리 콘솔 무회귀).
  - `src/static/app.js`: 작업 화면 `switchProfileTab` 의 release-notes 렌더에 `{areas:["work","common"]}` 전달 → area=admin 노트·'관리 콘솔' 칩 숨김.
  - `src/static/styles.css`: `.admin-pane[data-admin-pane="release-notes"].is-active` 를 dashboard/usage 스크롤 규칙(TASK-0167)에 추가 → `overflow-y:auto; overflow-x:hidden`.
  - index.html/admin.html: 변경 자산(styles.css·app.js·release-notes.js) `?v=20260618-rn-scope-scroll` bump(기존 사용자 stale 방지; admin.js 미변경 유지).
- 완료 기준(AC): AC-0582(작업 화면 admin 숨김·칩3·관리콘솔 무회귀), AC-0583(관리 콘솔 pane 스크롤).
- [x] 구현 + `node --check` PASS.
- [x] `verify_release_notes.mjs` **34/34 PASS**(작업화면 admin 0건·표시=work+common 43·칩 3개·그룹 11·관리콘솔 회귀 없음·스크롤 규칙 소스 단언 + 기존 27건).
- [x] verify-completion --pre-commit PASS(9) → 머지(PR #345, main `e812c9d`) → web 재배포(deploy_scope: included, repo-web-1 healthy, `?v=20260618-rn-scope-scroll` baked) → **PB-0008 PASS**: 작업 화면 칩=[전체/작업/공통]·admin 항목 0건(AC-0582) + 관리 콘솔 pane overflow-y:auto·scrollH 1418>clientH 801·하단 도달·admin 23건 무회귀(AC-0583). evidence CHG/REV-20260618T062406. **cycle 완료.**

## TASK-20260618T044611-ai-claude-release-notes — 릴리즈 노트 (작업 화면 프로필 탭 + 관리 콘솔 카테고리) (REQ-20260618-0321, AC-0578·0579, Major §12.3)
- 보고(사용자, 2026-06-18): 각 작업의 내역·개선 사항을 사용자도 파악할 수 있도록 릴리즈 노트를 구성. 진입점 2개(`작업 화면 > 사용자 프로필 > 릴리즈 노트(탭)`, `관리 콘솔 > 릴리즈 노트(카테고리)`) — 역할/권한별 분리. 일자별 정리 + 접기/탐색. 일반 사용자가 알 수 있는 단순·명시적 정보로 풀어서, 내부 정보(로직·네트워크·보안 처리 방법)는 숨기거나 간략화.
- 사용자 결정(2026-06-18, AskUserQuestion): 콘텐츠 관리 방식 = **정적 큐레이션(읽기 전용)**. (관리자 편집형 CRUD 는 미채택 — 추후 얹기 가능.)
- 등급: **Major §12.3** — 다중 파일(7) 변경이나 전부 **비파괴 additive frontend**. 백엔드·RBAC·스키마·엔드포인트·DB·신규 권한·인증/인가·데이터 **0**. rollback = 파일 제거(무손실).

### §2.1 Implementation Plan (PLAN)
- 신규 정적 파일 2종(데이터/로직 분리):
  - `src/static/release-notes-data.js` — `window.RELEASE_NOTES = { generated, releases:[{date,label?,summary,items:[{type:new|improved|fixed, area:work|admin|common, title, detail?}]}] }`. 콘텐츠는 git 출시 이력(2026-06-04~06-18 상세 + "그 이전" 마일스톤)을 사용자 친화 문장으로 큐레이션, 내부 정보 비노출.
  - `src/static/release-notes.js` — IIFE 로 `window.ReleaseNotes.render(container)` 노출. 일자별 그룹 접기(기본 최신 1개 펼침)·영역 필터 칩·모두 펼치기/접기. 전 텍스트 `textContent`(XSS-safe). jsdom layout 비의존.
- 작업 화면: `index.html` drawer-tab `data-profile-tab="release-notes"` + pane `#releaseNotesBody` + 스크립트 2종(`?v=20260618-release-notes`); `app.js` `switchProfileTab` 에 `release-notes` lazy 렌더 디스패치.
- 관리 콘솔: `admin.html` 시스템 그룹에 `data-admin-tab="release-notes"` + pane `#adminReleaseNotesBody` + 스크립트 2종; `admin.js` `switchTab` 에 렌더 디스패치. `ADMIN_TAB_PERMISSIONS` 미등록 → `canSeeTab` 항상 true(콘솔 진입자 모두 노출).
- `styles.css`: `.release-notes`/`.rn-*` 스타일(디자인 토큰 var(--*) 재사용, 종류·영역 배지 색).
- 검증: `tests/verify_release_notes.mjs`(jsdom) + 양 화면 PB-0008 Windows-browser.
- 완료 기준(AC): AC-0578(양 진입점 동일 콘텐츠·접기·탐색), AC-0579(내부 정보 비노출).
- [x] 구현(신규 2파일 + index/app/admin html·js + styles.css) + `node --check` 4파일 PASS.
- [x] `verify_release_notes.mjs` **26/26 PASS**(그룹 수·기본 접힘·카운트·토글·일자 포맷·영역 필터·모두 펼치기·XSS·빈 데이터).
- [x] verify-completion --pre-commit PASS(9) → 머지(PR #338, main `8b8fe53`) → web 재배포(deploy_scope: included, `docker compose build web`+`up -d --no-deps web`, repo-web-1 Up healthy·mysql_ok·pg_ok, 서빙 `release-notes(-data).js`·index/admin 탭·누출어 0 baked).
- [x] **PB-0008 1차 적발**: 작업 화면 릴리즈 노트 탭 실측 — 접힌 그룹 computed `display:flex`(접힘 무력화). `.rn-group-body{display:flex}` 가 UA `[hidden]{display:none}` override(권한 grid 트랩 동류). → CSS hotfix(`.rn-group-body[hidden]{display:none}`) + `styles.css?v=` bump(기존 사용자 stale CSS 방지) + jsdom 가드(27/27). CHG/REV-20260618T050409.
- [x] hotfix 재배포(PR #339, main `091280e`) → **PB-0008 재실측 PASS**: 작업 화면+관리 콘솔 양쪽 접힌 그룹 computed `display:none`(높이 0px)·첫 그룹 펼침·토글·영역 필터(작업 40/관리 23)·모두 펼치기·누출어 0 서빙 확정. evidence `artifacts/pb0008-release-notes/{work-screen,admin}-release-notes.png`. CHG/REV-20260618T051005-evidence. **cycle 완료.**

## TASK-20260618T025220-ai-claude-ds-acc-collapsed-default — 관리 콘솔 > 제품: 제품 선택 시 접근 가능 DB 목록 기본 접힘 (REQ-20260618-0316, AC-0573, Minor §12.3)
- 보고(사용자, 2026-06-18): 기본적으로 제품 항목을 선택했을 경우 데이터베이스 목록이 접혀 있도록 구성해 달라. (TASK-20260618T022150 접기 토글 후속 — 토글은 됐으나 기본은 펼침이었음.)
- 등급: **Minor §12.3** — frontend-only 기본값 1줄 변경. 백엔드·RBAC·스키마·엔드포인트·데이터·CSS 무변경. 비파괴(토글로 펼침 가능, 다른 datasource 전환 시 자동 펼침 유지).
- 진단: TASK-20260618T022150 이 `_renderDsAccordion` 의 접힘 상태(`_dsBodyCollapsed`)와 머리 클릭 토글을 도입했으나 초기값이 `false`(펼침)라 제품 선택 시 편집 대상 datasource 의 DB 편집기가 펼친 채 시작했다. 사용자는 기본 접힘을 원함.
- 수정: `src/static/admin.js` — `let _dsBodyCollapsed = false` → `true`(렌더 함수 클로저 초기값). 제품 상세를 열면(`renderProductDetail`) DB 편집기 body 가 접힌 채 시작, 데이터소스 행 머리 클릭으로 펼침 토글. `_switchEditDs`(전환)·`_afterBindChange`(편집대상 제거)의 `false` 리셋은 유지(다른 datasource 로 명시 전환 시 자동 펼침 — "전환=편집 시작" 의도 보존). 주석 갱신. admin.html 캐시버스터 `?v=20260618-ds-acc-collapsed-default`.
- 검증: `tests/verify_ds_accordion_collapse.mjs`(기본 접힘으로 단언 반전 — 초기 접힘→클릭 펼침→재클릭 접힘) + `node -c admin.js` + PB-0008 Windows-browser(제품 선택 직후 DB 목록 접힘 실측).
- 완료 기준(AC): AC-0573.
- [x] 구현(admin.js 기본값 true + 주석, admin.html 캐시버스터) + `node -c admin.js` PASS.
- [x] `verify_ds_accordion_collapse.mjs` **19/19 PASS**(초기 접힘·클릭 펼침·재클릭 접힘·하단 버튼 도달).
- [x] verify-completion --pre-commit PASS(9 checks) → 머지(PR #328 merge, main `1ad1519`) → web 재배포(deploy_scope: included, `docker compose build web`+`up -d --no-deps web`, repo-web-1 Up·mysql_ok·pg_ok, 서빙 `admin.js?v=20260618-ds-acc-collapsed-default`·`let _dsBodyCollapsed = true` baked) → **PB-0008 Windows-browser PASS**(실 Chrome/149, 단일 datasource 제품 KR `mysql-local`: 선택 직후 클릭 없이 DB 목록 접힘[body 미생성·caret ▸·aria false·하단 '+ 데이터소스 추가' 도달] + 머리 클릭 토글 펼침/접힘 무회귀; evidence `artifacts/pb0008-ds-acc-collapsed-default/default-collapsed-on-select.png`). CHG/REV-20260618T025848-ai-claude-ds-acc-collapsed-default-evidence.

## TASK-20260618T022150-ai-claude-ds-acc-collapsible — 관리 콘솔 > 제품: 펼쳐진 데이터소스의 접근 가능 DB 목록 접기 가능하게 (REQ-20260618-0314, AC-0571, Minor §12.3)
- 보고(사용자, 2026-06-18): `관리 콘솔 > 제품` 탭에서 펼쳐진 데이터소스의 접근 가능 데이터베이스 목록을 접을 수 있게 해 달라. 현재는 데이터소스가 하나만 있을 경우 그 DB 목록이 접히지 않아 하단의 UI(데이터소스 추가·제품 프롬프트·삭제)에 접근하기 번거롭다.
- 등급: **Minor §12.3** — frontend-only UI 동작 추가. 백엔드·RBAC·스키마·엔드포인트·데이터·CSS 무변경. 비파괴(기존 펼침 기본값 보존, 토글만 신설).
- 진단: 제품 상세의 "데이터 소스 & 접근 가능 데이터베이스" accordion(TASK-0238, admin.js `_renderDsAccordion`)은 편집 대상(`_editDsKey`) 행만 펼쳐 `dbEditorWrap`(접근 DB 편집기)을 `.ds-acc-body` 로 그린다. 행 머리(`.ds-acc-head`) 클릭은 `_switchEditDs(key)` 호출인데, `_switchEditDs` 가 `nk === _editDsKey` 이면 **early-return**(admin.js:6526~6538) → 이미 펼쳐진(편집 대상) 행 머리를 다시 눌러도 무반응 = 접기 불가. 데이터소스가 하나면 그 하나가 항상 편집 대상이라 DB 목록이 영구 펼침 → 하단 UI 가 멀어짐.

### §2.1 Implementation Plan (PLAN)
- `src/static/admin.js`: ① 모듈 스코프(렌더 함수 클로저) `let _dsBodyCollapsed = false` 신설 — 편집 대상 행의 body 접힘 여부(기본 펼침=기존 동작 보존). ② `_renderDsAccordion` 의 행 렌더에서 `isActive` → `isEditTarget`(키 일치) + `isExpanded`(= isEditTarget && !_dsBodyCollapsed) 분리. is-active 클래스·aria-expanded·caret(▾/▸)·body 렌더 모두 `isExpanded` 기준. head `title` = 펼침 시 "클릭하면 접기" / 접힘 시 "클릭하면 펼쳐서 DB 편집". ③ head 클릭 핸들러: 이미 편집 대상이면 `_dsBodyCollapsed` 토글 + `_renderDsAccordion()`, 아니면 `_switchEditDs(key)`(전환). ④ `_switchEditDs` 와 `_afterBindChange`(편집 대상 제거 분기)에서 `_dsBodyCollapsed = false` 리셋 — 다른 datasource 로 전환/이동 시 자동 펼침.
- `src/static/admin.html`: admin.js 캐시버스터 `?v=20260618-ds-acc-collapsible`.
- CSS 무변경: 접힌 행은 기존 비활성(non-active) 행과 동일 렌더(멀티 datasource 에서 이미 존재하는 스타일). `.ds-acc-head:only-child` / 비-active border-radius 가 그대로 적용.
- 검증: `tests/verify_ds_accordion_collapse.mjs`(jsdom — body 노드 생성/제거·is-active·aria-expanded·caret, layout 비의존) + PB-0008 Windows-browser(실 화면 클릭 접기/펼치기 + 하단 UI 도달).
- 완료 기준(AC): AC-0571.
- [x] 구현(admin.js 접힘 상태 + 토글 + 전환 리셋, admin.html 캐시버스터) + `node -c admin.js` PASS.
- [x] `verify_ds_accordion_collapse.mjs` **19/19 PASS**(초기 펼침 회귀 없음·토글1 접힘·토글2 재펼침·하단 버튼 도달).
- [x] verify-completion --post-commit PASS(9 checks) → 머지(PR #323 merge, main `9069518`) → web 재배포(deploy_scope: included, `docker compose build web`+`up -d --no-deps web`, repo-web-1 Up·mysql_ok·pg_ok, 서빙 `admin.js?v=20260618-ds-acc-collapsible`·`_dsBodyCollapsed` baked) → **PB-0008 Windows-browser PASS**(실 Chrome/149, 단일 datasource 제품 KR `mysql-local`: 초기 펼침→머리 클릭 접힘[body 제거·행 유지·caret ▸·aria false]→'+ 데이터소스 추가' 912→685px viewport 내 진입→재펼침 토글 복원; evidence `artifacts/pb0008-ds-acc-collapsible/ds-acc-collapsed.png`). 식별자 충돌(타 세션 021526 가 REQ-0313/AC-0570 선점)→REQ-0314/AC-0571 재번호·rebase. CHG/REV-20260618T024209-ai-claude-ds-acc-collapsible-evidence.

## TASK-20260618T021526-ai-claude-admin-status-filter — 관리 콘솔 역할·제품 탭에 활성/비활성 필터 추가 (REQ-20260618-0313, AC-0570, Minor §12.3)
- 보고(사용자, 2026-06-18): `관리 콘솔 > 역할`, `관리 콘솔 > 제품` 탭에서 활성/비활성 필터를 적용해 달라. 기존의 `계정` 탭을 참조.
- 등급: **Minor §12.3** — frontend-only(admin.html 2 toolbar + admin.js 필터 상태/술어/배선). 백엔드·RBAC·스키마·엔드포인트·데이터 0. 비파괴(기본 "전체" → 기존 동작 보존).
- 진단: `계정` 탭은 이미 `admin-filter-group`(전체/활성/비활성/삭제됨, `data-account-filter`)을 가지며 `filteredAccounts()` 가 `adminState.accountFilter` 로 게이트한다. 반면 `역할`·`제품` 탭 toolbar 는 검색창만 있고 상태 필터 UI·상태·술어가 모두 부재(`filteredRoles()`/`filteredProducts()` 는 검색어만 필터). 역할·제품은 soft-delete(`deleted_at`)가 없고 hard-delete 라 "삭제됨" 분기는 제외 → 3버튼(전체/활성/비활성).

### §2.1 Implementation Plan (PLAN)
- `src/static/admin.js`: ① `adminState` 에 `roleFilter:"all"`·`productFilter:"all"` 추가(계정 `accountFilter` 동형). ② `filteredRoles()`/`filteredProducts()` 에 상태 필터를 검색어 매칭 *앞* 단계로 삽입(active→`!is_active` 제외, inactive→`is_active` 제외). `filteredProducts()` 의 `if (!q) return slice()` 단축을 제거해 빈 검색에도 상태 필터가 적용되게 재구조화. ③ 이벤트 배선: `[data-role-filter]`·`[data-product-filter]` 버튼에 계정 필터(`[data-account-filter]`)와 동형 핸들러(`is-active` 토글 + 상태 갱신 + 재렌더).
- `src/static/admin.html`: 역할·제품 toolbar 의 검색창 뒤에 계정 탭과 동일한 `admin-filter-group`(전체/활성/비활성 3버튼) 추가. CSS(`.admin-filter-group`/`.admin-filter-btn`)는 이미 존재 → 재사용(신규 CSS 0).
- 검증: `scripts/verify_admin_status_filter.mjs`(순수 node — admin.js 실 `filteredRoles`/`filteredProducts` 본문 추출 + mock adminState 클로저 실행, 상태×검색 교집합 검증) + node --check + PB-0008 Windows-browser(역할·제품 탭에서 비활성 클릭 시 비활성 행만 렌더, computed `is-active` 버튼 상태).
- 완료 기준(AC): AC-0570.
- [x] 구현(admin.js 상태/술어/배선 + admin.html 2 toolbar) + node --check PASS.
- [x] `scripts/verify_admin_status_filter.mjs` **11/11 PASS**(역할·제품 각 all/active/inactive + 상태×검색 교집합 + 빈검색 회귀).
- [x] verify-completion --pre-commit PASS(9 checks) → 머지(PR #321 squash, main `6da40dc`) → web 재배포(`make dc-build SERVICE=web` + `docker compose up -d --no-deps web`, repo-web-1 healthy, 서빙 `admin.js?v=20260618-admin-status-filter`·역할/제품 `data-*-filter` 3버튼·필터 술어 baked) → **PB-0008 Windows-browser PASS**(실 Chrome/149, 제품 탭 13행=비활성 6+활성 7 정확 분할·`is-disabled` 6 전부 inactive 배지·버튼 `is-active` 단독 토글; 역할 탭 6행 active=6/inactive=0). evidence `artifacts/pb0008-admin-status-filter/{products-inactive-filter,roles-active-filter}.png`. CHG/REV-20260618T022846-ai-claude-admin-status-filter-evidence.

## TASK-20260618T010417-ai-claude-date-group-collapse — 작업 화면 좌측 대화목록 첫 진입 시 최근 일자 그룹만 펼침 (REQ-20260618-0288, AC-0569, Minor §12.3)
- 보고(사용자, 2026-06-18): 서비스를 처음 진입할 때 `작업 화면 > 좌측 대화목록` 에서, 가장 최근의 일자에 대한 대화그룹을 제외한 나머지 오래된 일자들은 접힌 상태로 나타내 달라.
- 등급: **Minor §12.3** — frontend-only UI 기본값 추가. 백엔드·RBAC·스키마·엔드포인트·데이터 0. 비파괴(접힘 기본값 + 사용자 토글 존중).
- 사용자 결정(AskUserQuestion, 2026-06-18): "처음 진입" = 매 페이지 진입(reload)마다 재적용. 날짜 키가 상대적(`__today__`/`__yesterday__`)이라 영구 1회 seed(타 계정 그룹 `_seedOthersCollapsedOnce` 패턴)는 다음 날 무의미 → 매 로드 1회 seed, 세션 내 사용자 펼침 토글은 존중.
- 진단: 내 대화 날짜 그룹 접힘은 `state.collapsedDateGroups`(localStorage `mad.collapsedGroups.v1`)로 결정되는데, 첫 진입 시 오래된 그룹 키가 set 에 없어 전부 펼침이 기본(app.js `renderConversationList` ~L1993, `sortedDateKeys` = today→yesterday→YYYY-MM-DD desc→`__other__`). "가장 최근 일자 그룹만 펼침" 기본값 부재.

### §2.1 Implementation Plan (PLAN)
- `src/static/app.js`: ① 모듈 스코프 `let _dateGroupsSeededThisLoad`(스크립트 재실행=페이지 로드당 리셋) + `_seedDateGroupsCollapsedOnce(sortedDateKeys)` 신설 — `sortedDateKeys[0]`(최근)은 `delete`(펼침 보장, 직전 영속 접힘 해제), 나머지는 `add`(접힘). 빈 키면 플래그 미설정(대화 미로드 시 다음 렌더 재시도). localStorage 영속 안 함(세션 단위, reload 재적용). ② `renderConversationList` 의 `sortedDateKeys` 정렬 직후·`forEach` 렌더 전에 1회 호출. 타 계정/owner 그룹은 별 seed(`_seedOthersCollapsedOnce`)라 무관.
- `src/static/index.html`: app.js 캐시버스터 `?v=20260618-date-group-collapse`.
- 검증: `tests/verify_date_group_collapse.mjs`(순수 node, set 조작 로직 — jsdom 불필요) + 기존 `verify_conv_entry_defaults.mjs` 무회귀 + PB-0008 Windows-browser(최근 외 날짜 그룹 `is-collapsed` computed).
- 완료 기준(AC): AC-0569.
- [x] 구현(app.js seed + 배선, index.html 캐시버스터) + node --check.
- [x] `verify_date_group_collapse.mjs` **22/22 PASS** + 기존 `verify_conv_entry_defaults.mjs` **20/20 무회귀**.
- [x] verify-completion --pre-commit PASS(9 checks) → 머지(PR #319 squash, main `32b5e8f`) → web 재배포(deploy_scope: included, `docker compose build web`+`up -d --no-deps web`, repo-web-1 Up·mysql_ok·pg_ok, 서빙 `app.js?v=20260618-date-group-collapse`·`_seedDateGroupsCollapsedOnce` baked) → **PB-0008 Windows-browser PASS**(실 Chrome/148, 첫 진입 6개 날짜 그룹 중 "6월 10일"만 펼침·나머지 5개 접힘; clean-room `localStorage.clear()`→reload seed 재발화 + 날짜키 비영속(`mad.collapsedGroups.v1`=`["__others__"]`만) 실증; 세션 토글 존중 1회-게이트). evidence `artifacts/pb0008-date-group-collapse/entry-recent-only-expanded.png`. CHG/REV-20260618T011645-ai-claude-date-group-collapse-evidence.

## TASK-0295 — 작업 화면 제품 목록을 역할 제품 접근 권한으로 게이트 (REQ-20260617-0293, AC-0548, Major §12.3)
- 보고(사용자, 2026-06-17): `관리 콘솔 > 역할` 에서 각 제품에 대한 권한이 없다면, 작업 화면 내 대화창 제품 목록 내부에서도 출력되지 않도록 구성.
- 등급: **Major §12.3** — 인가 표시 게이트(노출 축소 = 보안 강화 방향). 데이터 파괴 0·rollback 용이(필터 추가/제거). RBAC 인접 → outside-voice 필수([[feedback_outside_voice_for_rbac]]).
- 진단: 작업 화면 제품 목록은 `/api/session`(app.py:8871)·`/api/auth/me`(app.py:15548)가 `_list_products(include_inactive=False)` 로 반환하는데 **RBAC 필터가 없어** `IsActive=1` 전 제품을 노출. 반면 mutation 경로 8곳(`/api/ask` 9650/9758·`/api/new_conversation` 10301·pin 10421·fork 11099·prompt 18691/18731·pref 2779)은 이미 `_account_has_product_access`(제품별 `product.access.<key>`)로 403 게이트 → "요청은 막히는데 목록엔 보이는" 표시-enforcement 불일치. 관리 콘솔 4곳(`_list_products(include_inactive=True)` 16388/16765/17031/17202)은 product.read/manage 축(TASK-0288 2축 분리)이라 무관.

### §2.1 Implementation Plan (PLAN)
- Backend(`src/app.py`): ① 신규 `_filter_products_for_account_access(account, products)` — product_key 기반 `_account_has_product_access` lookup(conn 불필요), 권한 보유 제품만 반환. ② 신규 `_coerce_default_product_id(default_pid, products)` — default 가 접근 목록 밖이면 첫 접근 가능 제품으로 보정(빈 목록=0). ③ 작업 화면 2곳(`/api/session`·`/api/auth/me`)에서 `_list_products` 직후 필터 적용 + default 보정(`_attach_product_conn_status` 전 → 권한 없는 제품 연결 probe 회피). admin 4곳 무변경.
- Frontend(`src/static/app.js`·`styles.css`): 제품 목록은 모두 `state.products` 순회라 백엔드 필터로 자동 정합. 추가로 작업 화면 드롭업 메뉴(`renderProductDropupMenu`)에 접근 가능 제품 0건 안내(`.product-dropup-empty`) — auto(제품 무관) 항목은 유지.
- 검증: `tests/test_product_list_rbac.py`(순수 9건, `import app`·DB 불필요) + §18.8 outside-voice RBAC 패널 + PB-0008 Windows-browser(권한 회수 역할 로그인 → picker 미표시 실측).
- 완료 기준(AC): AC-0548.
- [x] Backend 구현 + py_compile PASS + 필터 호출 정확히 2곳(작업화면 전용) 정적 검증.
- [x] Frontend 구현 + 빈목록 안내(`.product-dropup-empty`) + CSS.
- [x] 단위 테스트 `test_product_list_rbac.py` **9/9 PASS**(agent 이미지, `import app`, DB 없이).
- [x] §18.8 outside-voice RBAC 패널 → **SHIP**(REV-20260617T054423-ai-claude-task0295-product-list-rbac [SUBAGENT:product-list-rbac-review], BLOCKER 0/MAJOR 0; 6축 적대 검토 admin over-block·누출·우회·회귀·fail-closed·default 보정 전부 OK).
- [x] verify-completion PASS(9 checks) → 머지(PR #303, main `3fa87e8`) → web 재배포(deploy_scope: included, `docker compose build web`+`up -d --no-deps web`, repo-web-1 healthy, 서빙 app.py `_filter_products_for_account_access` baked) → **PB-0008 Windows-browser PASS**(admin role `product.access.mv` 회수 시 `/api/session` products 8→7·MV 제거·MV_QA 유지·드롭업 DOM 7개; 전체 회수 시 빈목록 안내 "접근 가능한 제품이 없습니다" 렌더; 권한 복원). CHG/REV-20260617T060740 evidence.

## TASK-0293 — 프로필 아이콘 전 구간 조회·수정 (관리 콘솔 계정·역할) (REQ-20260617-0291, AC-0542~0545, Major §12.3)
- 보고(사용자): 작업화면에서 바꾼 계정 프로필 아이콘이 `관리 콘솔` 프로필 아이콘에 반영 안 됨. 확인 결과 관리 콘솔 계정·역할에는 프로필 아이콘 관련 작업이 전무. 아이콘을 쓰는 모든 구간에 이미지(기본=패턴) 조회·수정 가능화 요청.
- 등급: **Major §12.3** — 신규 admin 엔드포인트 4 + 서빙 1 + 비파괴 스키마 1컬럼. 권한은 기존 재사용(신규 권한 0). 사용자 결정: D1=관리 계정·역할 한정(작업화면·제품은 TASK-0268 완료, 메시지 말풍선 등 미사용 구간은 별 cycle), D2=역할 아이콘 이미지 업로드+패턴.
- 진단: TASK-0268 이 인프라(MinIO `_store_image_upload`/`_serve_image_object`·Identicon `applyAvatar`)와 작업화면 아바타·제품 아이콘만 구현. 관리 콘솔 계정은 `avatar.textContent=username.slice(0,2)`(이니셜 텍스트)라 백엔드가 내려주는 `avatar_url`(app.py:1340 이미 직렬화)을 소비 안 함=조회 버그. 역할은 `WebRoles` 에 아이콘 컬럼 자체가 부재.

### §2.1 Implementation Plan (PLAN)
- Backend(`src/app.py`): ① `_role_icon_url_for`(캐시버스터, `_product_icon_url_for` 동형) ② `_ensure_avatar_icon_schema` 에 `WebRoles ADD COLUMN IconObjectKey`(fast-path) + WebRoles CREATE 에 컬럼(slow-path) ③ `_list_roles`/`_load_role_by_id` 에 `icon_url` 직렬화(SELECT+GROUP BY) ④ 신규 `PUT/DELETE /api/admin/accounts/{id}/avatar`(console.manage+account.update) ⑤ 신규 `PUT/DELETE /api/admin/roles/{id}/icon`(console.manage+role.update) + `GET /api/roles/{id}/icon`(로그인 서빙).
- Frontend(`src/static/admin.js` + `admin.html` 캐시버스터): 계정 목록/상세·역할 목록/상세 4곳 이니셜 텍스트 → `applyAvatar`(계정=username 시드, 역할=role_key 시드). 계정 상세·역할 상세에 제품 아이콘과 동일 ✎ 오버레이(`.profile-avatar-edit`) 편집 UI(신규 역할은 차단). CSS 무변경(제품 아이콘이 쓰는 `.admin-avatar` 클래스 재사용).
- 검증: `make test`(pytest+ruff) + 신규 `tests/verify_profile_icon_admin_surfaces.mjs`(jsdom 17건) + 기존 `verify_profile_icon_consistency.mjs` 회귀(23건) + Python `test_avatar_icon_upload.py` 신규 4건(role URL 헬퍼·RBAC 403) + §18.8 외부 패널 + PB-0008 Windows-browser 시각검증.
- 완료 기준(AC): AC-0542(계정 조회 버그) / AC-0543(관리자 계정 아바타 편집) / AC-0544(역할 아이콘 도입·조회) / AC-0545(역할 아이콘 편집·신규역할 가드).
- [x] Backend 구현 + py_compile + 라우트 충돌 0(`/api/roles/{id}/icon` 단일).
- [x] Frontend 구현 + node --check admin.js PASS.
- [x] 단위 테스트: `make test` PASS(pytest exit 0 + ruff all-clear), verify_profile_icon_admin_surfaces.mjs 17/17, verify_profile_icon_consistency.mjs 23/23(회귀 0).
- [x] §18.8 외부 패널 → SHIP(REV-20260617T034455 [SUBAGENT], BLOCKER 0/MAJOR 0/MINOR 1 accepted).
- [x] verify-completion PASS → 머지(PR #300, main 7a52a66) → web 재배포(deploy_scope: included, `make dc-build SERVICE=web`+`up -d --no-deps web`, repo-web-1 healthy, healthz git_commit=7a52a66) → **PB-0008 Windows-browser PASS**(AC-0542 계정 img 1+Identicon 14·이니셜 0, AC-0544 역할 Identicon 5, AC-0543 타계정 아바타 업로드 200, AC-0545 역할 아이콘 업로드 200 — 실측). TEST.md §3 evidence Run 기록.

## TASK-0292 — 관리 콘솔 좌측 사이드패널 수직 스크롤 (REQ-20260616-0290, AC-0541, Minor §12.3, frontend-only)
- 보고(사용자): 화면 높이가 매우 작을 경우 `관리 콘솔` 좌측 사이드패널을 조작할 수 없음(하단 탭 클릭 불가). 수직 스크롤 구성 요청.
- 진단: `aside.admin-sidebar`(flex column, `overflow:hidden`) 안에서 `.admin-tabs`(`flex:1`)에 `min-height:0`·`overflow-y` 가 없어, viewport 높이가 brand+탭+foot 합보다 작으면 flex 항목 기본 `min-height:auto` 가 콘텐츠 미만 축소를 막고 `.admin-sidebar` 의 `overflow:hidden` 이 넘친 탭을 스크롤 없이 잘라냈다(설정 등 하단 탭 클릭 불가). 작업 화면 `.conv-list`(styles.css:500-503)는 이미 동일 idiom(`min-height:0; overflow-y:auto`)으로 스크롤됨 — admin 만 누락.
- 수정(frontend-only, styles.css 2곳): `.admin-tabs` 에 `min-height:0; overflow-y:auto;` 추가(작업 화면 `.conv-list` 패턴 정합) + `.admin-sidebar-foot` 에 `flex-shrink:0`(탭 스크롤 시 pending 요약 풋 하단 고정). 브랜드는 공유 `.sidebar-brand`(flex-shrink:0)로 이미 상단 고정. 캐시버스터 admin.html `?v=20260616-task0292-admin-sidebar-vscroll`.
- 비변경: HTML 구조/JS/백엔드/RBAC/스키마 0. 사이드바 미노출 모바일(≤680, `.admin-sidebar{display:none}`) 무영향.
- [x] CSS brace 균형(1243=1243) + node 무관(JS 무변경) + verify-completion PASS.
- [x] 머지(PR #289 → main be3a775) → web 재배포(deploy_scope: included, `docker compose build web` + `up -d --no-deps web`, repo-web-1 healthy, 서빙 `admin.html ?v=20260616-task0292-admin-sidebar-vscroll`·baked styles.css `.admin-tabs{min-height:0;overflow-y:auto}`) → **PB-0008 Windows-browser PASS**(win-browser eval 실측: computed `overflowY=auto`·`minHeight=0px`·foot `flexShrink=0`; 짧은 viewport(240px) tabsScrollH=572>clientH=134 **scrollable**·scrollTop=438 도달·하단 '설정' 탭 `settingsReachable=true`·foot 하단 고정. evidence `artifacts/pb0008-task0292/admin-sidebar-vscroll-short-vp.png`). CHG/REV-20260616-0304 evidence.


## TASK-20260616T100304-conv-entry-defaults — 작업 화면 첫 진입 기본값: 타 계정 대화 접힘 + 빈 대화 화면 (REQ-20260616-0289, AC-0539/0540, Major §12.3, frontend-only)
- 보고(사용자): ① 작업 화면을 처음 진입 시 타 계정 대화는 접혀있도록 구성, ② 대화 화면 또한 비어있는 상태여야 함.
- 등급: **Major §12.3** — bootstrap 진입 동작 변경(2개 동작). RBAC/스키마/엔드포인트/백엔드 무변경 → frontend-only.

### §2.1 Implementation Plan (PLAN)
- 영향 파일: `src/static/app.js`(로직), `src/static/index.html`(캐시버스터), 신규 `tests/verify_conv_entry_defaults.mjs`.
- 변경 symbol:
  - (요구1) 신규 `_seedOthersCollapsedOnce()` + 상수 `OTHERS_GROUP_KEY`/`OTHERS_COLLAPSED_SEED_LS_KEY`; `renderConversationList` 의 `othersKey` 를 상수로 통일.
  - (요구2) `loadConversations(preferredConversationId, {allowCurrentFallback=true})` 폴백 게이트; `refreshWorkspace(_, opts)` 전달; `initializeWorkspace` 의 `_preferCid` 기본값 ""/`_allowCurrentFallback=false` + deep-link/resume 예외.
- 접근: ① seed 플래그가 없을 때만 1회 `__others__` 를 `collapsedDateGroups`(localStorage)에 추가·영속 → 첫 진입 접힘, 이후 사용자 토글 존중. ② 첫 진입은 `allowCurrentFallback:false` 로 `payload.current` 자동선택 차단(빈 화면); deep-link(TASK-0263) 와 진행중 resume(TASK-0041)만 예외로 대화 활성화.
- 완료 기준(AC):
  - AC-0539: localStorage seed 플래그 부재(첫 진입) 시 "타 계정 대화" 그룹이 접힌 채 렌더된다. 사용자가 펼치면 그 선호가 영속되어 다음 진입에도 유지된다(재접힘 강제 없음).
  - AC-0540: 첫 진입 시 어떤 대화도 자동 선택되지 않아 대화 화면이 "대화를 선택하세요" 빈 상태로 표시된다. 단 `?conversation=<id>` deep-link 와 진행 중 요청이 있는 직전 대화는 예외로 활성화된다.
- 위험도: Major(비파괴 UI 동작 변경, rollback=캐시버스터 환원). 인증/인가/데이터 무관.
- [x] node --check PASS + `verify_conv_entry_defaults.mjs` 20/20 PASS.
- [x] PR #293 squash 머지(main b5f2434) → web 재배포(`?v=20260616-conv-entry-defaults`, healthz b5f2434) → **PB-0008 Windows-browser PASS**(요구1 타 계정 대화 접힘·요구2 빈 대화 화면, clean-room 재현 + 선호 존중). evidence `artifacts/pb0008-conv-entry-defaults/entry-others-collapsed-empty-chat.png`. CHG/REV-20260616T163634-ai-claude-conv-entry-defaults-pb0008.

## TASK-0291 (이전 cycle) — 관리 콘솔 계정 탭 배지 개수 활성 계정만 집계 (REQ-0282, AC-0538, Minor §12.3, frontend-only)
- 보고(사용자): `관리 콘솔 > 계정` 항목에 표시되는 개수를 활성화된 계정 대상으로만 집계하도록 수정. 비활성·삭제된 대상은 해당 목록 내부(필터)에서 이미 확인 가능하므로, 배지에는 실제 중요한 정보(활성 계정 수)만 노출.
- 진단: 사이드바 계정 탭 배지 `#tabCountAccounts`(admin.js `refreshPendingUI`)가 `adminState.accounts.length`(전체 = 활성 + 비활성 + 삭제)를 그대로 표시. 반면 목록 내부 카운트 `#accountListCount`(`renderAccountList`)는 `filteredAccounts()` 기반이라 이미 filter-aware(활성/비활성/삭제 필터 선택 시 해당 수 반영) — 사용자가 말한 "목록 내부에서 확인 가능"이 이것.
- 수정(frontend-only, admin.js 1곳): `refreshPendingUI` 의 `tabCountAccounts` 집계를 `adminState.accounts.filter((a) => a.is_active && !a.deleted_at).length`(활성 정의 = `filteredAccounts()` 의 `'active'` 분기와 동일: `is_active && !deleted_at`)로 변경. 캐시버스터 `admin.html ?v=20260616-task0291-account-active-count`.
- 비변경: 백엔드/RBAC/스키마/엔드포인트 0. `#accountListCount`(filter-aware) 비변경. 역할/제품/데이터소스 탭 배지 비변경(요청 범위 = 계정 한정).
- [x] node --check PASS, 백엔드 무변경(make test 회귀 자명 0).
- [x] 머지(PR #287 squash → main 9bdb9f8) → web 재배포(서빙 `?v=20260616-task0291-account-active-count`·`activeAccountCount` baked) → **PB-0008 Windows-browser PASS**(win-browser 실측: 계정 탭 배지 `#tabCountAccounts`=7 = 활성 필터 목록 `#accountListCount`=7명 일치, 전체 28명[7활성+1비활성+20삭제]과 분리). evidence `artifacts/pb0008-task0291/account-tab-active-count.png`. CHG/REV-20260616-0300, evidence CHG/REV-20260616-0301.

## TASK-0289 (current cycle) — 대화 수행시간 정직 표시 + 내부 동작 투명화 + 즉각 반응 + 큐 병목 완화 (REQ-20260616-0288, AC-0532~0534, Major §12.3)
- 사용자 보고: assistant 대화 요청 시 ①내부 동작(단계별 DB동작 외)이 표현 안 됨 ②실측 45초인데 화면엔 25초로 표시(내부 동작 집계가 숨겨져 제외) → 낮은 신뢰감·실제보다 "느리다" 체감. 모든 동작 투명 공개 + 즉각 반응(스트리밍 검토) + 성능 병목 확인 요청.
- 사용자 결정(AskUserQuestion): **P1~P4 진행, SSE 토큰 스트리밍(P3b)은 후속 cycle**(체감 개선 대부분 확보·저위험).
- 근본원인: 표시 `duration_ms` 가 `agent_core run_start`(모든 초기화 이후) 기준이라 LLM 루프(≈25s)만 집계 — 큐 대기(worker tick 1~2s)·웹 처리·DB 연결·grounding/prompt 조립(≈20s)이 전부 제외. step 으로 기록되는 건 tool(DB 동작)뿐이라 LLM 추론·연결·큐 대기는 화면에 "처리 중"만.
- [x] (P1, feature-0002) `_compute_duration_breakdown` + `agent_entry_perf`/`queued_ms_seed` → 표시값 total(end-to-end), meta `duration_breakdown` 동봉. worker 가 `claim` created_at 로 큐 대기 seed 주입(ask_jobs RETURNING + created_at)
- [x] (P2, feature-0002) `_emit_activity` non-tool activity step(맥락/준비/추론 라운드/정리) + `emit_index` 통합 step_index
- [x] (P4, feature-0002) `AGENT_ASK_WORKER_IDLE_POLL_SEC`(0.5) 유휴 claim 폴링 sub-second
- [x] (P1/P2/P3a, feature-0003) app.js `formatDurationBreakdown`+인라인/tooltip, activity step 구분 렌더, 처리중 ACTIVE 폴링; styles.css `.message-meta-breakdown`/`.step-detail-activity`/`.step-activity-badge`/`.has-breakdown`
- [x] 테스트: test_duration_breakdown.py 3 + test_ask_jobs.py created_at 2 + verify_runtime_transparency.mjs 16 + feature-0002 전체 회귀 0(2 skip) + py_compile + node --check
- [x] outside-voice 적대 코드리뷰(타이밍/run-status clobber/emit_index) 흡수(REV-20260616-0302) — 8개 위험가설 전부 코드대조 confirmed-correct, **SHIP(BLOCKER 0)**.
- [x] 머지(PR #288 → main 4178cf7) → 배포(web + ask-worker 재빌드, repo-web-1·repo-ask-worker-1 Up) → 배포 검증(서빙 `?v=20260616-task0289-runtime-transparency` + ask-worker baked `_compute_duration_breakdown`/`IDLE_POLL=0.5`) → **PB-0008 Windows-browser PASS**.
- [x] **PB-0008 render-injection PASS**(실 Chrome/148, win-browser computed 실측): `formatDurationBreakdown`="대기 2.1초 · 준비 4.3초 · 추론 39초"(null→""·250ms미만 생략→"추론 25초"); activity step `.step-detail-activity` border `dotted 2px`+"내부 동작" 배지+muted 제목 rgb(128,125,114); tool(execute_sql) activity 클래스 false·배지 0·"SQL 실행"(DB동작=주); breakdown `underline dotted`·cursor:help·opacity 0.55. evidence `artifacts/pb0008-task0289/runtime-transparency-evidence.png`. (실 45초 대화 e2e=LLM 의존이라 render-injection 으로 computed 실증 — 실사용 시 자연 재현.) CHG/REV-20260616-0302.
- 후속(P3b): SSE 토큰 스트리밍은 별도 cycle(사용자 결정).

## TASK-0287 — 말풍선 첨부 칩 다운로드 실패 수정 (REQ-20260616-0287, AC-0531, Minor §12.3, frontend-only)
- 보고(사용자): 첨부파일 목록에서 다운로드는 되지만, 말풍선 안에서 제공되는 첨부파일(칩)은 다운로드 실패.
- 진단: 목록 다운로드는 `_downloadAttachmentById`(raw fetch + blob, TASK-0284)인데, 말풍선 칩(`_buildMessageAttachChip`, TASK-0285)은 여전히 `<a href download>` **navigation** 방식. TASK-0284 가 octet-stream 프록시(`/api/attachments/{id}/download`)에서 navigation 다운로드 실패 때문에 목록을 fetch+blob 으로 전환했으나, 말풍선 칩에는 그 전환이 적용되지 않았다.
- 수정(frontend-only): `_buildMessageAttachChip` 의 click 핸들러를 `att.id` 가 있으면 `_downloadAttachmentById(att.id, attName)`(목록과 동일 fetch+blob) 호출로 통일. signed_url 만 있는 드문 폴백은 기존 navigation 유지. 캐시버스터 `?v=20260616-task0287-bubble-chip-dl`.
- 비변경: 백엔드/RBAC/스키마/엔드포인트/`_downloadAttachmentById` 자체 0.
- [x] node --check PASS, 백엔드 무변경(make test 회귀 자명 0).
- [x] 머지(PR #281 → main c5b4823) → web 재배포(baked+서빙 `?v=task0287`) → **PB-0008 PASS**(win-browser 실측: 말풍선 칩 click → `chipUsesFetch=true`[fetch `/api/attachments/{id}/download` 호출, navigation `<a>` 아님]·credentials=same-origin·has-download. 목록과 동일 `_downloadAttachmentById` 경로). CHG/REV-20260616-0298.

## TASK-0286 — 첨부 수정본 전달: 전체 본문 노출 제거 + 변경점만(diff) + 파일 명시 전달 (REQ-20260616-0286, AC-0528~0530, Major §12.3)
- 보고(사용자): assistant 가 파일(첨부)을 전달하지 않고 첨부 본문 전체를 채팅에 텍스트로 출력. ① 본문 전달이 필수면 변경점만 전달, ② 수정된 파일을 명시적으로 전달하도록.
- 등급: **Major §12.3** — LLM 동작(시스템 프롬프트) + 백엔드 답변/메시지 content 변조 + 프론트. RBAC 무변경.
- 진단: attachment-edit(파일화) 인프라(TASK-0275)는 있으나 ⓐ 시스템 프롬프트에 사용법이 없어 assistant 가 전체 본문을 그냥 출력, ⓑ materialize 후에도 블록이 답변에 남아 노출, ⓒ 프론트도 미처리.
- 구현:
  - [x] A. agent_core `SYSTEM_PROMPT` 에 "DELIVERING THE EDITED FILE — attachment-edit" 섹션(diff=변경점 + attachment-edit=전체 본문 숨김·첨부화, 전체 본문 코드블록 금지).
  - [x] B. app.py `_strip_attachment_edit_blocks`(라인 기반 `_attachment_edit_block_spans` 공유) + `_update_assistant_message_content`(PG·MySQL) + ask 후처리 render_output/DB content strip + "📎 수정본 전달" 명시 치환.
  - [x] C. app.js/share.js `enhanceAttachmentEditBlocks`(블록→안내 note) + `.attachment-edit-note` CSS(메인·share). 캐시버스터 `?v=20260616-task0286-attach-edit-diff`.
  - [x] 단위 테스트 `test_task0286_attach_edit_strip.py` 10 PASS(embedded-fence 누출/절단 회귀 포함) + make test 컨테이너 전체 회귀 0 + 정적검증.
  - [x] outside-voice 적대 보안 리뷰 SHIP-WITH-FIXES(REV-20260616-0295, MAJOR=본문 내 ``` 절단 누출 → 라인 기반 파서 흡수; IDOR/XSS/멱등/재컨텍스트 refute).
- [x] 머지(PR #278 → main b884b67) → web+ask-worker 재빌드(baked 확인) + **라이브 WebSystemPrompts global row 멱등 append**(6837→8536, SHOWING CHANGES 다음 삽입, 백업) → **PB-0008 PASS**(render-injection: fullBodyHidden·diff 유지·📎 note rgb(37,99,235)). 실 e2e(첨부 업로드→assistant 수정→strip)는 LLM 의존이라 합성 render-injection + 백엔드 pytest 10 PASS 로 검증, 실사용 시 자연 재현. evidence `artifacts/pb0008-task0286/attach-edit-diff-only.png`. CHG/REV-20260616-0296.

## TASK-0285 — 첨부 버전 현황 표면화 ②③④ (REQ-20260616-0285, AC-0525~0527, Major §12.3)
- 보고(사용자): TASK-0275(assistant 첨부 수정→버전 관리) 배포 후 보완 — ② `'+' > 첨부파일 목록`의 각 파일 버전 현황 표시, ③ assistant 말풍선 안에 첨부 명시 표시(사용자 말풍선처럼), ④ assistant 요청 시 진행 단계에 첨부 수정 명시 출력. (쿼리 리뷰 워크플로① 는 사용자 결정으로 후속 cycle.)
- 등급: **Major §12.3** — frontend 중심 + 백엔드 노출. history 첨부 직렬화는 IDOR 표면이라 outside-voice 게이트.
- 진단: TASK-0275 인프라(materialize·버전 체인·`/versions`·`_serialize_attachment_for_api` 버전 필드)는 이미 존재하나 "노출·연결"이 빠짐 — ② 목록 렌더가 버전 필드 무시, ③ assistant `edited_attachments` 가 토스트만(칩 없음)·history 미직렬화, ④ materialize 가 ask 후처리(run 밖)라 step 미기록.
- 구현:
  - [x] ② backend: `list_conversation_attachments` 에 version_count/ai_version_count `GROUP BY COALESCE(RootAttachmentId, Id)` 집계(N+1 회피·fail-soft). frontend: `_loadConversationAttachmentList` 항목에 버전 배지 + "버전 N개" 펼침 토글 + `_renderAttachmentVersionsBox`(/versions lazy) + `_downloadAttachmentById` 공통 헬퍼.
  - [x] ③ backend: `_load_assistant_attachments_by_message`(MetaJson.message_id 그룹핑) + `_attach_assistant_attachments` 신규 + `_get_history`(PG·MySQL) 주입. frontend: `_buildMessageAttachChip`(user/assistant 공통, 형식 유연화 + 버전 배지) + renderMessages 칩 조건 assistant 포함 + assistant 말풍선 칩 CSS.
  - [x] ④ backend: ask materialize 후처리에서 `save_memory_step`(action=attachment_edit, tool=materialize_attachment, work/reason 직접 저장) + 응답 render_steps 즉시 반영.
  - [x] 단위 테스트 `test_task0285_attach_surfacing.py` 9 PASS + make test 컨테이너 전체 회귀 0 + py_compile + node --check + CSS brace(1242) + 캐시버스터 `?v=20260616-task0285-attach-surfacing`.
  - [x] outside-voice 적대 보안 리뷰 SHIP (REV-20260616-0293, BLOCKER 0; IDOR/signed_url/SQLi/MetaJson조작/fail-soft 전부 refute).
- [x] 머지(PR #275 → main 1c4737d) → web 재배포(baked+서빙 `?v=task0285` 확인) → **PB-0008 Windows-browser PASS**(실 Chrome/148 render-injection computed 실측: ③ assistant 칩 `v2 · AI 수정` color rgb(37,99,235)·bg rgb(232,240,255)·assistant 말풍선 칩 배경 rgb(255,255,255), ② 버전 박스 2행+버전별 다운로드). 라이브 assistant 수정본 0건이라 합성 render-injection 으로 검증(실사용 시 자연 재현). evidence `artifacts/pb0008-task0285/attach-version-surfacing.png`. CHG/REV-20260616-0294.

## TASK-20260616T022652-ai-claude-sidebar-resize — 대화창 좌측 사이드바 너비 드래그 조절 (REQ-20260616-0284, AC-0523, Minor §12.3)
- 보고(사용자): `작업 화면` 좌측 대화 사이드바(대화 목록 패널)의 너비를 사용자가 조절할 수 있도록 구성. (스크린샷: 사이드바 전체 영역 강조.)
- 등급: **Minor §12.3** (frontend-only, `src/static/{index.html,styles.css,app.js}`. RBAC/스키마/엔드포인트/백엔드 0. 비파괴 추가.)
- 진단: 좌측 사이드바(`<aside class="sidebar">`)는 `.app-shell` CSS Grid 의 첫 컬럼(`grid-template-columns: var(--sidebar-w) minmax(0,1fr)`, `--sidebar-w: 252px` 고정)으로 너비 조절 수단이 없었다. 반면 우측 패널 3종(`#stepSidePanelResizer`/`#profileDrawerResizer`/`#attachSidePanelResizer`)에는 이미 drag-resize + `localStorage` 영속 패턴이 존재 → 동일 패턴을 좌측에 미러링.
- 접근: 우측은 절대배치 패널이라 왼쪽 가장자리(`innerWidth − clientX`)를 끌지만, 좌측은 in-flow grid 컬럼이라 **`--sidebar-w` CSS 변수를 JS 가 조절**하고, 핸들은 `.app-shell` 자식으로 두어 `left: var(--sidebar-w)` 로 경계를 추종(사이드바 `overflow:hidden` 클리핑 회피). 우변 드래그 = `clientX`.
- [x] index.html: `</aside>` 뒤 `.app-shell` 자식으로 `#sidebarResizer`(role=separator, aria-label) 핸들 추가. styles.css/app.js 캐시버스터 `?v=20260616-sidebar-resize`.
- [x] styles.css: `.app-shell{position:relative}` + `.sidebar-resizer`(left:var(--sidebar-w)·8px·ew-resize·hover/active 시 `--primary` 2px 라인) + `.app-shell.is-sidebar-resizing{user-select:none}` + 모바일(≤680) `.sidebar-resizer{display:none}`.
- [x] app.js: `setupSidebarResize`/`_applySidebarWidth`(우측 패널 패턴 동형) — drag 가 `--sidebar-w` 를 [180, min(640, 50%vw)] clamp + mouseup 이 `localStorage["web.sidebar.width"]` 영속 + 더블클릭 reset + 모바일(≤680)에선 override 제거. `initialize()` 1회 배선 + resize 리스너에 `_applySidebarWidth()` 추가.
- [x] 검증: node --check app.js PASS + CSS brace(1222=1222) + **jsdom 23/23 PASS**(`tests/verify_sidebar_resize.mjs`: 마크업/CSS 규칙/배선/clamp/영속/모바일 제거/더블클릭) + make test 컨테이너 **전체 회귀 0**(REAL_MAKE_EXIT=0, ruff clean).
- [x] verify-completion PASS → 커밋 7e43b51 → PR #267 squash 머지(main 6f1242b) → web 재배포(deploy_scope: included, healthz git_commit=6f1242b, 서빙 자산 baked) 완료.
- [x] **PB-0008 Windows-browser 시각검증 PASS**(실 Chrome/148.0.7778.217, win-browser relay, innerWidth 1249): 핸들 computed `display:block·cursor:ew-resize·position:absolute·8px·visible`; 드래그 252→380px 시 **사이드바 폭 실제 380 + chat-column 좌변 380 으로 레이아웃 reflow**(jsdom 불가 영역); clamp 하한 180·상한 624(=min(640, 50%vw)) 정확; mouseup localStorage `web.sidebar.width` 영속; **새로고침 후 340px 복원**(`_applySidebarWidth`); 더블클릭 시 252px·localStorage 제거 reset. evidence `artifacts/pb0008-sidebar-resize/sidebar-resized-340.png`. CHG/REV-20260616T024150-ai-claude-sidebar-resize-pb0008.

## TASK-0283 — 관리 콘솔 제품 아이콘 편집 UI 를 유저 프로필과 동일한 ✎ 오버레이로 통일
- 보고(사용자): `관리 콘솔 > 제품 > [각 항목] > 프로필 아이콘` 의 수정버튼 UI 를 유저 프로필과 동일하도록 구성. 현재 "아이콘" 텍스트박스가 제품 아이콘(36px) 영역을 크게 침범.
- 등급: **Minor §12.3** (frontend-only, `src/static/admin.js` 1곳 + `styles.css` dead-rule 제거 + 정적자산 cache-buster. RBAC/스키마/엔드포인트/백엔드 0).
- 진단: 제품 상세 헤더(admin.js `renderProductDetail`)의 아이콘 편집이 `.admin-avatar-edit`(absolute, `bottom:-22px`, `left:0 right:0`) 안에 **"아이콘"·"제거" 텍스트 pill** 2개를 중앙 배치 → 텍스트 버튼 폭이 36px 아바타보다 넓어 좌우로 spill, 아이콘 영역 침범. 유저 프로필(index.html `.profile-avatar-edit`)은 ✎ 펜슬 버튼을 아바타 우하단에 **원형 오버레이**(`.profile-avatar-change`, `right:-4px bottom:-4px 22px`)하고 "사진 제거"는 텍스트 링크(`.profile-avatar-remove`)로 분리 — 동일 패턴 미적용 상태였다.
- [x] 수정(admin.js `renderProductDetail`): 텍스트 pill 폐기 → 유저 프로필과 동일하게 아바타를 `.profile-avatar-edit` 래퍼로 감싸고 `.profile-avatar-change`(✎) 오버레이 버튼 + 숨김 file input, "아이콘 제거"는 `.profile-avatar-remove` 텍스트 링크로 idText 하단 배치. 기존 PUT/DELETE 엔드포인트·5MB 가드·toast·renderProductDetail 재렌더 로직 무변경.
- [x] 수정(styles.css): dead `.admin-avatar-edit`/`.admin-avatar-change`/`.admin-avatar-remove` 규칙 제거(사용처 0건 — admin.js 5798/5802/5820 한정이었음). 프로필 클래스 재사용이라 신규 CSS 0.
- [x] cache-buster: index.html(styles.css) + admin.html(styles.css·admin.js) `?v=20260616-product-icon-edit`.
- [x] 검증: node --check admin.js PASS.
- [x] verify-completion PASS → PR #265 머지(main 245446f) → web 재배포(deploy_scope: included, repo-web-1 healthy, 서빙 `admin.js/styles.css?v=20260616-product-icon-edit`·`profile-avatar-change` baked) → **PB-0008 Windows-browser PASS**(제품 상세 아이콘 우하단 ✎ 원형 오버레이 `.profile-avatar-change`[computed: position absolute·right:-4px·bottom:-4px·22×22·border-radius:50%·visibility visible·opacity 1]·구 텍스트 pill `.admin-avatar-change/edit` 부재(oldPillPresent=false)·텍스트 침범 0·유저 프로필 동일 클래스 재사용으로 시각 동형; CHG/REV-20260616-0292 evidence). evidence `artifacts/pb0008-task0283/product-icon-edit-overlay.png`.

## 0zz. TASK-20260615T182907-product-list-row-icon-layout-fix (current cycle) — 제품 관리 목록 행 UI 뒤틀림 핫픽스 (TASK-...-product-icon-chip-list 후속)
- 보고(사용자): 제품 관리 목록의 UI 가 뒤틀림. (직전 cycle PR #249 가 목록 행에 아이콘 추가하면서 발생.)
- 등급: **Minor §12.3** (frontend-only 단일 파일 레이아웃 버그 수정, admin.js. RBAC/스키마/엔드포인트/백엔드 0).
- 진단: `.admin-list-row` 는 `display:grid; grid-template-columns: auto 1fr auto`(3열). PR #249 가 `row.append(cb, avatar, meta)` 로 avatar 를 **row 최상위 2번째 칸**에 넣어, avatar 가 `1fr` 칸을 차지하고 meta 가 `auto` 칸으로 밀려 행 정렬이 깨졌다(원래는 `[cb, meta]` 2자식 = `auto 1fr`). 계정 목록 행은 avatar 를 `main>title` 안에 중첩해 `[cb, main, chips]` 3자식이라 정상이었는데, 제품 행은 그 패턴을 안 따랐다.
- [x] 수정(admin.js `renderProductList`): avatar 를 row 최상위가 아니라 **meta(`admin-list-main`) 첫 줄 `titleRow`(`admin-list-row-title`, flex) 안에 name 과 함께** 묶음(계정 목록 행과 동형). `row.append(cb, meta)` 2자식 복원 → grid `auto 1fr auto` 정상.
- [x] 검증: node --check admin.js + **jsdom 19/19 PASS**([3] 행 레이아웃 회귀 5건 추가) + make test 회귀 0.
- [ ] (잔여) PR 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 재검증(목록 행 정렬 정상).

## 0. TASK-0278 (직전 cycle, 머지됨 #251) — 관리 콘솔 데이터소스 목록 행별 네트워크 상태 배지 (leading 도트)
- 요청: `관리 콘솔 > 데이터소스` 의 각 목록 앞에 네트워크 상태를 배지 아이콘으로 표시.
- 등급: **Minor §12.3** (frontend-only — RBAC/스키마/엔드포인트/백엔드/데이터 0. 기존 `GET /api/admin/datasources` `conn_status` + `POST .../{key}/test` 재사용).
- 진단: 데이터소스 목록 행(`_dsRenderList`, `.admin-list-row--nav`)은 이름·엔진·`.env`·비번없음 배지만 있고 연결 상태 표면이 없었다. picker(REQ-0244)·상세 패널엔 연결/insight 상태가 있으나 목록 자체엔 부재. 백엔드는 이미 목록 응답에 `conn_status` 를 사전계산해 첨부(`loadAdminData` 가 `datasourceConnStatus` 캐시에 반영) → 추가 백엔드 0. (§13.1: #250 이 TASK-0277 선점 → TASK-0278 재번호)
- 구현(frontend-only):
  - [x] `admin.js` `_dsRenderList()`: 각 행 leading 에 `.ds-conn-dot` span 을 main **앞** 첫 자식으로 추가. 캐시 hit→동기 즉시 색칠, miss→is-checking 후 `_probeDatasourceConn`(force=false, 4-cap 세마포어/in-flight dedup) lazy probe → `dot.isConnected` 가드로 detach 노드 갱신 skip.
  - [x] `admin.js` 신규 헬퍼 `_paintDsConnDot(el, entry)`: 상태(ok/fail/checking)→클래스 + `title`/`role=img`/`aria-label`("네트워크 상태: …") 색맹 대응. picker 텍스트 배지 `_paintDsConnBadge` 와 독립.
  - [x] `styles.css`: `.ds-conn-dot`(9px 원형, currentColor 점+halo, is-ok=success/is-fail=danger/is-checking=muted+covPickerPulse, prefers-reduced-motion 정지) + `#datasourceList .admin-list-row--nav { grid-template-columns: auto 1fr }`(컨테이너 스코프 — `#settingsList` 등 타 nav 1fr 유지).
  - [x] 캐시버스터 `admin.html` styles.css·admin.js `?v=20260615-task0278-ds-conn-badge`.
- 검증:
  - [x] node --check admin.js + CSS brace 균형.
  - [x] 적대적 코드리뷰(general-purpose outside voice, REV-0282) **SHIP** — grid 스코프 회귀 0(ID 특이성 1,0,3,0 > base 0,0,2,0, `#settingsList` 미매칭)·leading 배치·async detach 가드·캐시우선·중복 probe 0 전부 확인. cosmetic MINOR 2 흡수.
  - [x] 머지(#251 main 73d65b8) → web 재배포(dc-build SERVICE=web + up -d) → **PB-0008 Windows-browser PASS** — 14행 전부 leading 도트·left=270 단일정렬·is-ok 초록(22,163,74)/is-fail 빨강(220,38,38)·title/aria-label·grid 9px 274px·#settingsList 무회귀(308px). TEST.md §4, evidence artifacts/pb0008-task0278/.
- 비변경: 백엔드·`/api/admin/datasources` 응답 계약·RBAC(`console.access`/`console.manage`)·picker/상세 패널 연결배지 0.
- 배포: web 재빌드(정적자산). migrate 불필(스키마 무변경).

## 0x. TASK-0277 (직전 cycle, 머지됨 #250) — 관리 콘솔 "보관 대화" 탭 UI 정합 다듬기 (TASK-0276 list-detail 위 후속)
- 요청: 보관 대화 탭 UI 정합 2건(frontend-only — 백엔드/RBAC/엔드포인트 무변경).
  - [문제1] header↔filter 사이 `<p class="admin-pane-note">` 안내가 다른 탭(계정·역할·제품·감사 로그)에 없는 큰 여백을 만들어 밀도 불일치 → 다른 탭과 동일 밀도로 처리.
  - [문제2] `#archiveList` 의 각 `.admin-archive-row` 가 topic·소유자·보관자 문자열 길이에 따라 줄바꿈되어 구성이 뒤틀림 → 2줄 고정 + ellipsis 절단(감사 로그 row 견고함 기준).
- 등급: **Minor §12.3** (frontend-only — RBAC/스키마/엔드포인트/백엔드/데이터 0).
- 진단: [문제1] `admin-pane-note` 는 admin.html 전체에서 보관 대화 pane 에만 단 1회 존재(다른 탭은 header→filter 직결) — 밀도 불일치의 유일 원인. 우측 상세 pane 은 이미 `admin-archive-detail-note`(선택 시) 로 동일 설명을 보유. [문제2] `.admin-archive-row-line { flex-wrap: wrap }` + owner/by span 에 nowrap/ellipsis/`min-width:0` 부재가 근본 원인(topic 은 ellipsis 있으나 `min-width:0` 없음).
- 구현(frontend-only):
  - [x] `admin.html`: [문제1] pane-note `<p>` 제거 + `#archiveDetail` 빈 상태(`admin-detail-empty`)에 `admin-archive-detail-note` 안내 carry. 캐시버스터 admin.js·styles.css `?v=20260615-task0277-archives-ui-align`.
  - [x] `admin.js`: [문제1] `renderArchiveDetail` 빈 분기도 동일 안내 carry(static 정합).
  - [x] `styles.css`: [문제2] `.admin-archive-row-line` flex-wrap 제거 + align-items:baseline/min-width:0; topic min-width:0; owner/by nowrap+ellipsis+overflow:hidden+min-width:0+flex:0 1 auto; ts flex:0 0 auto+nowrap. [문제1] 사용처 0건 `.admin-pane-note` 규칙 제거.
- 검증:
  - [x] node --check admin.js + CSS brace 균형 + jsdom 25 PASS(`tests/verify_archive_tab_ui.mjs` — 안내 이동·밀도·row 2줄 고정·CSS anti-wrap 계약) + make test 컨테이너 **전체 회귀 0**(백엔드 무변경).
- 비변경: 백엔드·`/api/admin/conversations/archived` 응답 계약·RBAC·탭 가시성·row 템플릿 로직·escape 0.
- 배포: web 재빌드(정적자산). migrate 불필.
- [x] (TASK-0277 본 변경) PR #250 머지(main `61e0151`) → web 재배포 → PB-0008. **PB-0008 에서 [문제2] ellipsis 미작동 적발** → 0277b 핫픽스로 후속.
- **TASK-0277b (후속 핫픽스, CHG/REV-0283)** — 보관 대화 row ellipsis 실작동 수정:
  - 발견: PR #250 배포 후 PB-0008 실 브라우저 실측 — 줄바꿈은 막혔으나(rowH 56 고정) ellipsis 가 발동 안 함(line 이 콘텐츠 폭 2858px 로 팽창, span clipped:false).
  - 원인: `.admin-archive-row` 가 `.admin-list-row`(grid, `align-items:center`)와 함께 선언 → flex 컬럼 줄이 row 폭으로 stretch 안 됨 → span shrink 불가. jsdom 은 cascade/layout 미계산이라 미검출.
  - [x] `styles.css`: `.admin-archive-row` 에 `align-items: stretch` 추가(line→row 폭 stretch → span ellipsis 절단). 라이브 실험 사전확인: line 2858→308px, topic clipped:true, rowH 56 유지.
  - [x] 캐시버스터 `?v=20260615-task0277b-archive-row-ellipsis`. jsdom 계약 단언 추가(26 PASS). node --check + CSS brace(1210) + make test 회귀 0.
  - [x] **완료**: PR #252 머지(main `d6123d3`) → web 재배포 → **PB-0008 재검증 PASS**(main `d6123d3`, `?v=...task0277b`): `rowAlignItems:stretch`·`paneNotePresent:false`·2줄 고정(rowH 56)·line0W 308·topic/owner/by `clipped:true`(ellipsis 발동). evidence `artifacts/pb0008-task0277/{01_archive_long_ellipsis,02_archive_clean_density}.png`. TEST.md §4 기록(CHG/REV-0284 docs-only). **TASK-0277 전체(문제1·2) 완료.**

## 0y. TASK-20260615T180923-product-icon-chip-list (직전 cycle, 머지됨 #249) — 제품 프로필 아이콘을 대화창 chip + 제품 관리 목록 행에도 표시
## 0. TASK-0277-ds-id-fk-migration (current cycle) — 데이터소스 라벨/키 분리: 제품↔데이터소스 바인딩을 stable Id surrogate 로 이전
- 요청(사용자, 2026-06-15): `관리 콘솔 > 데이터소스` 라벨 수정 시, 그 데이터소스를 연결한 제품에서 변경이 갱신되지 않음. "내부적으로 해시값으로 매칭되는 줄 알았는데, 라벨을 키값으로 쓰지 않아야 하는 구조와 상이." → 라벨을 키로 쓰지 않는 구조로 수정.
- 등급: **Critical §12.3** (제품↔데이터소스 바인딩 = 데이터 접근 경계[TASK-0206 미바인딩=접근 0]. 접근제어 3개 테이블 스키마 변경 + 마이그레이션 + RBAC 인접). 사용자 승인 경로: Option A(cascade)/B(분리) 제시 → B 선택 → B1(DisplayLabel)/B2(순수 Id) 제시 → **B2 선택**.
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-15 (AskUserQuestion: "B2 순수 Id 재배선" 명시 선택) -->
- 근본원인: `DatasourceKey`(생성 시 엔드포인트 해시 자동생성, 이후 admin rename 가능)가 모든 제품 바인딩 테이블의 FK 문자열로 직접 사용됨. rename 핸들러(`admin_update_datasource` `key_changed` 블록, app.py)는 `WebProducts.DatasourceKey` 만 cascade 하고 **`WebProductDatasources`·`WebProductDatabases` 는 누락** → 멀티 datasource 도입(TASK-0228/0230) 후 바인딩 본체가 join 테이블로 이동했는데 cascade 미확장 → orphan. 대조: 삭제 경로는 3 테이블 모두 정리하나 rename 은 1개만.

### §2.1 Implementation Plan (B2 — Id surrogate 를 canonical 식별 anchor 로)
- **설계 핵심**: `WebDatasources.Id`(BIGINT AUTO_INCREMENT, 기존 PK·불변)를 제품 바인딩의 canonical 식별자로 도입. rename(라벨=`DatasourceKey`)은 자유 변경 + 바인딩은 Id anchor 라 불변. `DatasourceKey` 는 WebDatasources 의 renameable 라벨 + PasswordEnc AAD 로 잔존(re-encrypt 기존 로직 유지). insight/RAG 는 이미 `compute_scope_key`(엔드포인트 해시) 스코핑 — 무영향.
- **마이그레이션(추가형·PK 무변경·역방향 안전)** — `_ensure_web_product_datasources_schema` (app.py) 확장:
  - `WebProducts` ADD `DatasourceId BIGINT NULL` + backfill(`JOIN WebDatasources d ON d.DatasourceKey=LOWER(WebProducts.DatasourceKey) SET DatasourceId=d.Id`) + INDEX.
  - `WebProductDatasources` ADD `DatasourceId BIGINT NULL` + backfill + 단일컬럼 INDEX `IX_WebProductDatasources_DsId (DatasourceId)`. 기존 PK `(ProductId, DatasourceKey)` 유지(dual-write 로 키 잔존).
  - `WebProductDatabases` ADD `DatasourceId BIGINT NULL` + backfill + 단일컬럼 INDEX `IX_WebProductDatabases_DsId`. 기존 PK 유지.
  - 멱등 가드(information_schema COLUMN 존재 확인) + 실패 loud 로깅(`_ensure_web_product_datasources_schema` 패턴 재사용).
  - **★ `_runtime_tables_available` probe 에 3 테이블 `DatasourceId` 컬럼 검증 추가(TASK-0047 함정)** — 미등록 시 기존 배포가 fast-path 로 마이그레이션을 영구 skip → 컬럼 미생성 → cascade 무력. 1054 시 full 마이그레이션 트리거.
- **외부음성(RBAC 적대적) 1차 NOT-SHIP → 흡수**: BLOCKER1(probe 미등록+cascade 하드의존)·BLOCKER2(autocommit 비원자)·BLOCKER3(PK 충돌) + MINOR(DELETE force DatasourceId·테스트 column-absent). 수정: probe 등록 + cascade 컬럼부재 시 key-only 완전동작 + 명시 트랜잭션(rollback) + new_k 고아 사전제거 + DELETE force Id 동기화 + R4 회귀테스트.
- **rename 핸들러(app.py `admin_update_datasource`)**: 버그성 부분 cascade 제거 → **Id 구동 완전 cascade**(`WHERE DatasourceId=(SELECT Id FROM WebDatasources WHERE DatasourceKey=new_k)` 로 3 테이블 SET DatasourceKey=new_k). Id anchor 라 stale 키여도 robust·완전. password re-encrypt(AAD) 기존 로직 유지.
- **바인딩 write(dual-write Id+Key)**: `admin_add_product_datasource`·`admin_remove_product_datasource`·`PATCH .../datasource`(primary 설정)·db-insights write — key→Id resolve 후 `DatasourceId` 동시 기록. INSERT/UPDATE 에 DatasourceId 추가.
- **단일 포인터 read(Id-JOIN 우선+키 폴백, 선택)**: `_list_product_datasources`·`_product_datasource_keys`(agent_core) 등은 cascade 가 키 신선도를 보장하므로 무변경으로도 정합 — Id-JOIN 재배선은 방어적 강화로만(회귀 위험 낮은 단일 read 우선).
- **무변경 확인**: insight `_ds_scan_databases`(scope_key 해시 스코핑), `_datasources.resolve`(키 기반 — cascade 가 신선도 보장), 다운스트림 allowlist/registry(resolved 키 문자열 소비).
- **이월(차기 cycle, 문서화)**: 바인딩 테이블 `DatasourceKey` 컬럼 drop + 멀티라우터(`_resolve_product_datasources`/`_datasource_allow_schemas`) Id 전면 threading + PK 를 `(ProductId, DatasourceId[, SchemaName])` 로 이전 — 멀티이미지(web/ask-worker/insight-worker) 배포 안전 확인 후.
- **Acceptance Criteria**:
  - AC-1: 라벨 rename 후 그 데이터소스를 바인딩한 제품의 (a) 바인딩 목록·(b) primary·(c) 접근가능 DB 가 모두 유지(orphan 0). 회귀테스트로 검증.
  - AC-2: rename 후 제품 데이터 접근(allowed schemas) 불변 — `_product_has_datasource`·`_datasource_allow_schemas` 가 새 라벨로 동일 결과.
  - AC-3: 신규 바인딩 add/remove/set-primary 시 `DatasourceId` 정확히 기록 + 기존 키 경로 무회귀.
  - AC-4: 기존 데이터(backfill) — 모든 기존 바인딩 행의 DatasourceId 가 매칭 WebDatasources.Id 로 채워짐(NULL 0, 단 미등록 키 제외).
  - AC-5: make test 컨테이너 회귀 0 + outside-voice(RBAC) SHIP + PB-0008 Windows 시각검증(라벨 변경 후 제품 상세 갱신).
- 위험·롤백: 추가형 컬럼(PK 무변경)이라 코드 롤백만으로 회귀 — 컬럼은 무해 잔존. cascade 는 명시 트랜잭션 내 atomic(rollback).
- 영향 파일: `unit/feature-0003-agent-web-ui/src/app.py`(스키마·probe·rename·바인딩 write), 신규 테스트 `tests/test_datasource_rename_binding_stable.py`, docs(TASK/MODIFY/REVIEW/FUNCTION). 배포: web 재빌드(스키마는 부팅 `_ensure_web_tables`). agent_core/insight 무변경(read 는 cascade 신선도 보장 — 이월).
- 완료 체크리스트:
  - [x] 스키마: 3 테이블 `DatasourceId` 멱등 ADD + backfill + 인덱스
  - [x] `_runtime_tables_available` probe 에 DatasourceId 등록(TASK-0047 함정 회피)
  - [x] rename Id 구동 완전 cascade(3 테이블) + new_k 고아 사전제거 + 명시 트랜잭션
  - [x] 바인딩 write dual-write(add/remove/set-primary/databases) + DELETE-force Id 동기화 + seed cascade 보강
  - [x] 회귀테스트 R1~R4 + make test 컨테이너 회귀 0 + ruff clean
  - [x] 외부음성 2-pass(RBAC 적대적) NOT-SHIP→SHIP-WITH-FIXES (BLOCKER 4 흡수)
  - [ ] web 재배포 + 라이브 검증(라벨 rename→제품 바인딩·접근DB 유지)
  - [ ] (이월) 바인딩 테이블 DatasourceKey 컬럼 drop + read Id-JOIN 전면화 + PK 이전

## 0z. TASK-20260615T180923-product-icon-chip-list (current cycle, timestamp ID — §13.1 순번충돌 회피) — 제품 프로필 아이콘을 대화창 chip + 제품 관리 목록 행에도 표시
- 요청(사용자, profile-icon-consistency 후속): 제품 프로필 아이콘(Identicon)을 (1) 대화창(채팅창) 제품 chip 과 (2) 제품 관리 탭 목록 행의 **뱃지 아이콘으로도** 표현. 직전 cycle 은 드롭업·관리 상세에만 적용했음.
- 등급: **Minor §12.3** (frontend-only 비파괴 UI 추가 — 직전 cycle 의 `applyAvatar`/`identiconSvg` 헬퍼·CSS 재사용. RBAC/스키마/엔드포인트/백엔드 0).
- 구현(frontend-only, 4 src):
  - [x] `index.html`: chip 에 `<span class="composer-product-chip-icon hidden" id="productChipIcon">` 추가(dot 과 label 사이).
  - [x] `app.js` `renderProductChip`: pinned 제품이면 아이콘 표시(설정 이미지 or Identicon[product_key 시드] 폴백), auto 모드면 hidden + 내용 비움. dot·label·conn 색 로직 무변경.
  - [x] `admin.js` `renderProductList`: 각 행에 `applyAvatar(avatar, {url:icon_url, seed:product_key})` 아이콘(`admin-avatar admin-avatar-sm`) 추가 — checkbox 다음, meta 앞. 계정 목록 행과 동형.
  - [x] `styles.css`: `.composer-product-chip-icon`(16px 원형 클립 + `.hidden` + img/svg 규칙) 신설, chip `max-width` 180→200(아이콘 추가분). 행 아이콘은 직전 cycle `.admin-avatar .avatar-img,.admin-avatar > svg` 원형 클립 규칙 재사용.
  - [x] 캐시버스터 통일 `?v=20260615-product-icon-chip-list`(index/admin html 의 app.js·admin.js·styles.css).
- [x] 검증: node --check app.js·admin.js PASS + CSS brace 균형(1211=1211) + **jsdom 격리 14/14 PASS**(`tests/verify_product_icon_chip_list.mjs` — chip pinned Identicon/img·auto hidden·행 아이콘·동일 product_key 동일 Identicon 정합).
- [x] **완료**: make test 회귀 0 → PR #249 squash 머지(main `aea4d15`) → web 재배포(repo-web-1 healthy, 캐시버스터 서빙 확인) → PB-0008 Windows-browser PASS(chip Identicon·목록 행 8개 Identicon·제품별 동일 아이콘 정합). evidence: TEST.md §4 + `artifacts/pb0008-profile-icon/41_chip_zoom.png`·`42_admin_list_icons.png`.
- [!] **후속 핫픽스**(위 TASK-20260615T182907): 사용자 보고로 **제품 관리 목록 행 UI 뒤틀림** 발견 — 행 아이콘을 `row` 최상위 칸에 넣어 `.admin-list-row` 3열 grid(`auto 1fr auto`)가 깨짐. 해당 핫픽스 cycle 에서 수정.

## 0a. TASK-0276 (직전 cycle, 머지됨 #247) — 관리 콘솔 "보관 대화" 탭 UI 정합화 (audits/계정/역할/제품 동형 list-detail)
- 요청: `관리 콘솔 > 보관 대화` 를 다른 탭(계정·역할·제품·감사 로그)과 정합하게 구성.
- 등급: **Minor §12.3** (frontend-only — RBAC/스키마/엔드포인트/백엔드/데이터 0. 기존 `GET /api/admin/conversations/archived` 응답 그대로 사용).
- 진단: 기존 보관 대화 pane 은 단일 `<div id="archivesContent">` 에 `admin-usage-table` 로 렌더 → 다른 탭의 검증된 **list-detail 2단 구조**(좌측 `admin-list` row 목록 + count/scope head, 우측 `admin-detail-col` 선택 상세)와 구조·시각 이질. 감사 로그(`admin-audit-row`/`admin-audit-detail`/`admin-audit-filter`) 패턴이 가장 근접한 read-only 목록 탭이라 verbatim 동형 이식.
- 구현(frontend-only):
  - [x] `admin.html`: archives pane 을 `admin-archive-filter`(검색 input + 적용/초기화 버튼) + `admin-list-detail`(좌측 `#archiveList` + `#archiveListCount`/`#archiveListScope`, 우측 `#archiveDetail`)로 교체. 헤더 actions 의 인라인 검색 input 제거(필터 행으로 이동), 새로고침 버튼 유지.
  - [x] `admin.js`: `adminState.archives = {items, selectedId, q, truncated, loading}` + `renderArchiveList`(row 클릭 → selectedId + 상세 렌더 + is-selected) + `renderArchiveDetail`(dl 메타: 대화 ID/소유자/보관 시각/보관 수행자/생성 시각 + 안내). `loadArchivedConversations` 가 목록·상세 분리 렌더 + 선택 유지. 검색 적용/초기화 버튼 바인딩 추가. 기존 table 렌더(`renderArchivedConversations`) 대체.
  - [x] `styles.css`: 기존 `.admin-archives-table` 류 제거 → `.admin-archive-filter/.admin-archive-row/.admin-archive-row-*/.admin-archive-detail/.admin-archive-detail-fields` 추가(각각 `.admin-audit-*` 동형 — 동일 padding/색/grid).
  - [x] 캐시버스터 `admin.html` admin.js·styles.css `?v=20260615-task0276-archives-ui`.
- 검증:
  - [x] node --check admin.js + CSS brace(1206=1206).
  - [x] **jsdom 13 PASS**(빈 목록 empty·row 2개 audits 동형 클래스·count·row 클릭→selectedId+상세 렌더+is-selected·미존재 선택 empty·topic XSS escape 목록/상세·truncated scope 안내) + make test 컨테이너 **전체 회귀 0**(백엔드 무변경).
  - [x] 라이브: 정적자산 web 적용 후 admin.js 새 함수 14건·admin.html list-detail 마크업 12건 서빙 확인.
- 비변경: 백엔드·`/api/admin/conversations/archived` 응답 계약·RBAC(`conversation.archive.read.any` 게이트 그대로)·탭 가시성 로직 0.
- 배포: web 재빌드(정적자산). migrate 불필.
- [ ] (잔여) 머지 → web 재배포 → PB-0008 Windows-browser(보관 대화 탭 list-detail 렌더·row 클릭 상세).

## 0a. TASK-20260615T172210-profile-icon-consistency (직전 cycle, 머지됨 #246) — 제품 프로필 아이콘 정합화 + 대화 드롭업 항목 레이아웃·너비 + 제품 명칭 표기 순서
- 요청(사용자): (1) `관리 콘솔 > 제품 > [각 항목]` 의 제품 프로필 아이콘 UI 를 `작업 화면 > 프로필` 과 정합하게 구성. (2) 대화 화면 요청 텍스트박스의 제품 선택 목록/선택 항목에 [네트워크 상태 배지·프로필 아이콘·제품 명칭·데이터 소스] 가 적절히 위치하도록 + 목록 너비가 좁아 명칭이 잘리는 이슈 해소(너비 확대). (3) 제품 명칭 표기를 `제품 명칭 (제품 약어)` → `(제품 약어) 제품 명칭` 으로 변경.
- 등급: **Major §12.3** (frontend-only 다파일 외부 표시 정합화 — RBAC/스키마/엔드포인트/백엔드 0). 비파괴 UI.
- 진단: 작업화면 프로필(`app.js` applyAvatar/identiconSvg)은 이미지 미설정 시 **결정론적 Identicon SVG** 로 폴백하나, 관리 콘솔 제품 아이콘(`admin.js` renderProductDetail)·대화 드롭업 아이콘은 **이니셜 텍스트** 또는 **아예 미표시**라 정합하지 않았음. 드롭업 항목 순서는 [아이콘(설정 시만)→dot→명칭→ds] 였고 메뉴 max-width 280px 로 `(약어) 명칭` 길이 시 잘림.
- 구현(frontend-only, 5 src):
  - [x] `admin.js`: app.js 의 `_identiconHash`/`identiconSvg`/`applyAvatar` **byte-identical 이식**. 제품 상세 헤더 아이콘을 `applyAvatar(avatar, {url: icon_url, seed: product_key})` 로 교체 — 미설정 시 이니셜 대신 Identicon 폴백(작업화면 프로필과 정합). 아이콘 편집(변경/제거) 컨트롤 보존.
  - [x] `app.js` `buildProductDropupItem`: 항목 자식 순서를 **① 상태 배지(dot) → ② 프로필 아이콘 → ③ 명칭 → ④ 데이터소스** 로 재배열(사용자 요청 순서). pinned 제품은 아이콘 **항상 표시**(설정 이미지 or Identicon 폴백, 과거엔 icon_url 설정 시에만). auto 항목은 아이콘 없이 dot 만.
  - [x] `styles.css`: 드롭업 메뉴 너비 `min 220→300 / max 280→min(420px,92vw)` 확대(명칭 잘림 해소). `.product-dropup-item-icon` 16→18px·원형 + `> svg` 규칙(Identicon). `.admin-avatar.has-avatar-img`/`.avatar-img`/`> svg` 원형 클립(edit 컨트롤은 컨테이너 밖이라 overflow visible 유지, 이미지·SVG 만 50% 클립).
  - [x] 제품 명칭 조합 `${name} (${product_key})` → `(${product_key}) ${name}` **7곳**: app.js(promptSelect / chip fullLabel / dropup label / promptProductSelect), admin.js(목록행 / 상세헤더 / role-product select).
  - [x] 캐시버스터 통일: index.html app.js+styles.css·admin.html admin.js+styles.css `?v=20260615-profile-icon-consistency`. [[project_static_asset_cache_busting]]
- [x] 검증: node --check app.js·admin.js PASS + CSS brace 균형(1198=1198) + **jsdom 격리 23/23 PASS**(`tests/verify_profile_icon_consistency.mjs` — identicon app↔admin byte-identical·결정론·드롭업 순서·Identicon 폴백·명칭 7곳) + **make test 컨테이너 전체 회귀 0**(pytest PASS, 2 skip, ruff clean, MAKE_EXIT=0).
- [x] **완료**: origin/main rebase(TASK-0275 위) + REV 0276→0277·AC 0493~0498→0497~0502 재번호 → PR #246 squash 머지(main `bb1a991`) → web 재배포(`sudo docker compose build web && up -d --no-deps web`, repo-web-1 Up healthy, HTTPS /healthz 200, 캐시버스터 서빙 확인) → **PB-0008 Windows-browser 시각검증 PASS**(실 Chrome/148 relay): ① 드롭업 8제품 항목 순서 [dot→icon→label→ds] ② 전 제품 Identicon(작업화면 프로필 정합, KR 동일 십자가 교차확인) ③ 명칭 `(약어) 명칭`(드롭업·관리목록·상세) ④ 메뉴 너비 max 420px 명칭 미잘림 ⑤ 관리 콘솔 제품 상세 Identicon. evidence: TEST.md §4 2026-06-15 profile-icon Run + `artifacts/pb0008-profile-icon/35_dropup_large.png`·`20_admin_detail_identicon.png`. (REV-0277 은 동시세션 TASK-0276 이 0278 로 재번호해 충돌 자연 해소.)

## 0b. TASK-0275 (직전 cycle, 머지됨) — assistant 첨부 수정 → 새 버전 materialize + 대화 진행에 따른 버전 관리
- 요청(Task⑥): assistant 가 전달받은 첨부파일을 수정해 사용자에게 제공 + 대화 진행에 따른 버전 관리.
- 등급: **Critical §12.3** (LLM 자동 데이터 변형·저장 표면 신규 + MinIO 쓰기 + 스키마 변경). PLAN-APPROVED(사용자 2개 설계 결정 확정).
- 사용자 결정(AskUserQuestion): 수정 범위=**텍스트 계열 MVP**(csv/text, 바이너리 제외), 확정 방식=**assistant 자동 materialize**(사용자 클릭 불요).
- 구현:
  - [x] 스키마(MySQL 전용 — 첨부는 PG/alembic 무관): `WebConversationAttachments` 에 `RootAttachmentId`/`VersionNumber`/`CreatedByRole`/`SupersededAt` + UNIQUE `UQ_WCA_VersionChain(RootAttachmentId,VersionNumber)`. 멱등 ALTER `_ensure_attachment_version_schema` 를 fast-path(`_ensure_seed_catchup`)·slow-path(`_ensure_web_tables`) 양쪽 호출(avatar 선례 동형 — fast-path 미보정 시 'Unknown column' 회귀 방지).
  - [x] materialize: `_parse_attachment_edit_blocks`(답변 내 ```attachment-edit``` fenced block 파싱) + `_materialize_assistant_attachment_edits`(가드 적용 후 새 버전 생성). ask 흐름에서 render_output 확정 후 호출 → 응답 `edited_attachments`.
  - [x] 신뢰 경계 가드: ① 텍스트 계열 kind(csv/text)만 — 바이너리 거부. ② source 첨부 같은 conversation+account scope(IDOR 차단). ③ size cap(per_file/conv/account) 재사용. ④ turn 당 개수 cap(5)+내용 size cap(1MB). ⑤ 새 파일명 source 확장자 강제(.exe 등 차단)+safe_filename(traversal 차단).
  - [x] 버전 체인: root=source 의 root(없으면 source), VersionNumber+1, CreatedByRole='assistant'. MinIO put 선행→INSERT→직전버전 supersede(VersionNumber< 기반 self-heal). 목록(`list_conversation_attachments`)은 최신만(`SupersededAt IS NULL`). `GET /api/attachments/{id}/versions`(체인 전체, read.{own,any} 권한, pending signed_url 미발급).
  - [x] 프론트(app.js/styles.css): 첨부 pill 버전 배지(`v2 · AI 수정`) + `edited_attachments` 토스트. 캐시버스터 `?v=20260615-task0275-attachment-version`.
- 검증:
  - [x] py_compile + node --check app.js + CSS brace.
  - [x] 신규 `test_attachment_versioning.py` **11 PASS**(파서 2·materialize 가드 6·직렬화 1·파일명 1·목록필터 1) + make test 컨테이너 **전체 회귀 0** + ruff clean. (테스트 sys.modules 오염 → monkeypatch.setitem 자동원복으로 해소.)
  - [x] **라이브 라운드트립**(임시 web 적용 + MySQL ALTER): materialize→새버전(v2, role=assistant)·MinIO 바이트(sha256 일치)·부모 supersede·목록 최신만·`/versions` 체인 2개. IDOR 가드 2종(cross-account/conv) 라이브 거부 확인. V3 traversal/.exe 라이브 차단(`.._.._.._etc_passwd.sql`·object_key `../` 없음). V6 UNIQUE 충돌 IntegrityError 거부.
  - [x] **outside-voice 적대적 보안 리뷰**(REV-20260615-0276): 외부 침투형(IDOR·traversal·kind우회·권한상승·DoS cap·SQLi·/versions 권한) BLOCKER 0. 데이터 정합 BLOCKER1(원자성)+MAJOR2(UNIQUE race·audit 부재)+MINOR1(확장자) **전부 수정 후 SHIP**: put-before-insert+self-heal supersede, UNIQUE 인덱스, `attachment.version.create` audit, 확장자 고정.
- 배포: web 재빌드(app.py+정적자산). **migrate 불필**(첨부는 MySQL DML-only 테이블 — 멱등 ALTER 가 재기동 시 자동 적용, alembic/PG 무관). `deploy_scope: included`.
- [ ] (잔여) 머지 → web 재배포 → PB-0008(첨부 버전 배지·AI 수정본·`/versions` 시각검증).

## 0a. TASK-0274 (직전 cycle, 머지됨) — 첨부파일 목록 사이드 패널(#attachSidePanel) 너비 조절(리사이즈) 가능화
- 요청: `작업 화면 > '+' > 첨부파일 목록` 으로 나타나는 사이드바 UI 의 크기 조절(resize) 가능화.
- 등급: **Minor §12.3** (비파괴 프론트엔드 UI 추가 — 기존 step-side-panel/profileDrawer 의 검증된 resize 패턴 verbatim 이식. RBAC/스키마/엔드포인트/데이터 0).
- 근거: `#stepSidePanel`(`setupStepSidePanelResize`)·`#profileDrawer`(`setupProfileDrawerResize`)는 이미 좌측 가장자리 드래그 핸들 + localStorage 너비 영속화 패턴을 운영 중. `#attachSidePanel` 만 고정 `width:280px` 로 resize 미구현이었음 → 동일 패턴 이식.
- 구현:
  - [x] `index.html`: `#attachSidePanel` 에 `<div class="attach-side-panel-resizer" id="attachSidePanelResizer" role="separator" …>` 핸들 추가(step-side-panel 마크업 동형).
  - [x] `styles.css`: `.attach-side-panel` 에 `min-width:240px`/`max-width:92vw` + `.is-resizing`(transition 제거·user-select 차단) + `.attach-side-panel-resizer`(좌측 가장자리 ew-resize 핸들 + hover/dragging 시 `--primary` 가이드라인) 스타일 추가.
  - [x] `app.js`: `setupAttachSidePanelResize()` + `_applyAttachSidePanelWidth()` 추가(키 `web.attachSidePanel.width`, min 240px, max 92vw, mouse+touch). 패널 open 경로(`composerActionsListItem` 클릭)에서 `setupAttachSidePanelResize()` + `_applyAttachSidePanelWidth()` 호출 후 표시.
  - [x] 캐시버스터: `index.html` styles.css·app.js `?v=20260615-attach-panel-resize`. [[project_static_asset_cache_busting]]
  - [x] node --check app.js PASS.
- [x] 완료: verify-completion --pre-commit PASS → PR #241 squash 머지(main `bb06ddf`) → web 재배포(`sudo docker compose build web && up -d --no-deps web`, repo-web-1 Up healthy) → **PB-0008 Windows-browser 시각검증 PASS**(핸들 hit-test=attachSidePanelResizer·드래그 280→458px·localStorage 저장·새로고침 후 458px 복원·min240/max92vw clamp 실측). evidence: TEST.md §4 2026-06-15 TASK-0274 Run + `artifacts/pb0008-task0274/attach-panel-resized-458.png`.

## 0b. TASK-0272 (직전 cycle, 머지됨) — 대화 화면 프로필 첫 진입 시 "프롬프트 > 제품 범위" 목록 비어있는 버그 수정
- 증상: 대화 화면에서 프로필 드로어를 처음 열면(새로고침 후) `프롬프트` 탭의 **제품 범위**(`#promptProductSelect`) 셀렉트가 비어 있음. 다른 탭을 눌렀다가 `프롬프트` 탭을 다시 클릭해야 채워짐.
- 등급: **Minor §12.3** (비파괴 프론트엔드 단일 파일 버그 수정, RBAC/스키마/엔드포인트/데이터 0).
- 근본원인: lazy 콘텐츠 적재(`initAccountPromptEditor()`)가 탭 **클릭 리스너**(`initialize()` 내)에만 배선됨. `openProfile("prompt")`→`switchProfileTab("prompt")`(첫 진입 시 prompt 가 기본 활성 탭, 클릭 이벤트 없음) 경로에는 디스패치가 없어 셀렉트가 미적재 상태로 노출. `state.products` 는 부트스트랩(`initializeWorkspace`→`/api/session`)에서 이미 적재되어 데이터 문제 아님.
- [x] 수정(app.js): lazy 디스패치를 `switchProfileTab(tab)` 내부로 이동(prompt→`initAccountPromptEditor`, usage→`loadProfileUsage`). `openProfile` 와 탭 클릭 양쪽 경로가 `switchProfileTab` 을 거치므로 단일 디스패치로 일원화. 탭 클릭 리스너의 중복 디스패치 제거.
- [x] 캐시버스터 bump: index.html app.js `?v=20260615-task0269-conv-split` → `?v=20260615-task0272-prompt-scope` (styles.css 미변경 유지). [[project_static_asset_cache_busting]]
- [x] node --check app.js PASS.
- [ ] (잔여) verify-completion --pre-commit PASS → commit/push/main 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 시각검증(프로필 첫 진입 시 제품 범위 채워짐).

## 0a. TASK-0273 (current cycle, 동시세션 TASK-0272[prompt-scope] 선점으로 0272→0273 재번호) — 대화 삭제 → soft-archive(보관) + admin 조회 + 맥락 참조
- 목표: 대화 "삭제" 를 hard-delete → 해당 계정에서 안 보이는 **보관(archive)** 으로 전환. (1) 보관 대화를 대화 맥락에 참조(fork) 가능 + (2) 오용 방지 admin 조회 가능.
- 등급: **Critical §12.3** (파괴적 삭제 동작 의미 변경 + 신규 admin 데이터 접근 표면 + 스키마 마이그레이션). PLAN-APPROVED(사용자 3개 설계 결정 확정).
- 사용자 결정(AskUserQuestion): 보관 동작=**진행 차단(동결)**, admin 조회 권한=**신규 보관전용**(conversation.archive.read.any), 맥락 참조=**fork 게이트 완화(최소)**.
- 구현:
  - [x] 스키마(3중 멱등, TASK-0248 동형): `core_conversations.archived_at`/`archived_by_account_id` — alembic `0007_core_conv_archived`(down=0006) + `agent_runtime_schema.sql`(CREATE+ALTER+index) + app.py MySQL 폴백 ALTER.
  - [x] 삭제→archive: `_delete_conversation_impl` 가 `delete_conversation_records`(hard-delete) 대신 `_archive_conversation`(UPDATE archived_at, archived_at IS NULL 가드) 호출 → status `archived`/`archived_pending`. 데이터·MinIO 첨부 **보존**(cascade soft-delete 안 함). 응답 키는 기존 deleted/deleted_pending 유지(프론트 호환).
  - [x] 목록 숨김: `_list_conversations_pg`(PG)·`_list_conversations`(MySQL) 둘 다 `archived_at IS NULL` (소유자·admin 브라우징 공통, 검색/날짜 경로 포함).
  - [x] 진행 차단: `_conversation_block_info` 가 blocked_at **또는** archived_at set 이면 차단(보관 사유). /api/ask 가 이 게이트로 보관 대화 진행 403.
  - [x] 신규 권한 `conversation.archive.read.any`(catalog + admin seed 자동 + admin catchup 명시 목록 추가) + `GET /api/admin/conversations/archived`(권한 게이트, 메타만, q 검색 bound param, PG/MySQL).
  - [x] admin 콘솔 "보관 대화" 탭(권한 없으면 숨김) + loadArchivedConversations/렌더 + 새로고침/검색.
  - [x] fork 게이트 완화: 접근/fork 경로에 archived 필터 없음(보관 대화 참조·복제 가능, 사본은 정상 대화). 삭제 UI 라벨 "보관" 으로(메뉴/confirm/toast/bulk).
- 검증:
  - [x] py_compile + node --check app.js/admin.js + CSS brace.
  - [x] 신규 `test_conversation_archive.py` **7 PASS**(archive UPDATE 가드·hard-delete 미호출·forbidden·block_info archived·목록 필터 정적·admin 권한 403·권한 catalog) + 기존 `test_product_delete_block_conv.py` block_info SQL 3-tuple 갱신 + make test 컨테이너 **전체 회귀 0**(ALL=0) + ruff clean.
  - [x] **라이브 라운드트립**(임시 web 적용 + PG superuser ALTER): 대화 archive→목록에서 사라짐·PG archived_at/by 기록·/api/ask 403(진행 차단)·admin 보관 조회 count=2(권한 catchup 후). **라이브 검증이 2개 실 버그 포착·수정**: ① PG 컬럼 미적용(web DML-only) ② admin 권한 catchup 누락(신규 권한이 admin 역할에 자동 grant 안 됨).
  - [x] **outside-voice 적대적 보안 리뷰 SHIP**(REV-20260615-0273, BLOCKER 0 — 데이터 보존 의도적·목록 숨김 전 경로·진행 차단·admin only·멱등 스키마 PASS; MINOR[deploy-order robustness·count 드리프트] 비차단).
- 배포: **migrate-first 필수**(web=DML-only role → alembic 0007 superuser 선행 적용 후 web 재빌드). `deploy_scope: included`.
- [ ] (잔여) 머지 → `make migrate`(alembic 0007) → web 재배포 → PB-0008(보관·admin 조회·진행 차단 시각검증).

## 0z. TASK-0268 (직전 cycle, 머지됨) — 사용자 프로필 / 제품 아이콘 이미지 + Identicon 기본
- 목표: 사용자 프로필 이미지·제품별 아이콘 이미지를 설정 가능하게. 기본(미설정) 프로필 이미지는 Identicon. (사용자 결정: Gravatar 미사용[email 컬럼 없음·외부의존 0], Identicon=프론트 생성.)
- 등급: **Major §12.3** (신규 스키마 컬럼 + 이미지 업로드/서빙 엔드포인트 표면).
- 구현(백엔드 app.py):
  - [x] WebAccounts.AvatarObjectKey + WebProducts.IconObjectKey 멱등 ALTER — slow path(`_ensure_web_tables`) **및** fast-path(`_ensure_seed_catchup`→신규 `_ensure_avatar_icon_schema`) 양쪽(운영 재기동은 fast-path 만 타 'Unknown column' 회귀 방지 — 라이브 검증서 포착·수정).
  - [x] `_serialize_account`→`avatar_url`, `_list_products`→`icon_url`(object key 해시 캐시버스터). 계정 SELECT chokepoint 에 `AvatarObjectKey` 추가.
  - [x] `PUT/DELETE /api/auth/me/avatar`(본인 self-service, 로그인만) + `GET /api/avatars/{id}`(로그인). `PUT/DELETE /api/admin/products/{id}/icon`(product.manage) + `GET /api/products/{id}/icon`. MinIO prefix `avatars/<id>/`·`product-icons/<id>/`(uuid+ext, 파일명 미사용→traversal 0).
  - [x] 이미지 검증 `_sniff_image`(매직바이트 png/jpg/webp만, 클라 MIME 불신, SVG/GIF 거부=XSS 차단) + 크기 cap(아바타 2MB/아이콘 5MB). 서빙 `_serve_image_object`(content-type 역추론 + `X-Content-Type-Options: nosniff` + `Content-Disposition: inline`).
- 구현(프론트):
  - [x] app.js `identiconSvg(seed)`(해시 기반 5x5 대칭 SVG, 외부의존 0·결정론적) + `applyAvatar(el,{url,seed,initials})`(이미지 or Identicon, onerror 폴백). 사이드바·드로어 아바타 적용 + 드로어 업로드/제거 UI.
  - [x] 제품 드롭업(`buildProductDropupItem`)에 아이콘 이미지(설정 시) + admin 제품 상세 아바타 이미지·아이콘 업로드/제거(product.manage). styles.css 아바타/아이콘 + Identicon 스타일.
  - [x] 캐시버스터 `?v=20260615-task0268-avatar`(index.html·admin.html).
- 검증:
  - [x] node --check app.js/admin.js + py_compile + CSS brace(1175=1175).
  - [x] 신규 `test_avatar_icon_upload.py` **8 PASS**(매직바이트 판별·SVG/GIF/거짓MIME 거부·빈/초과/미지원 거부·정상 PNG object key·URL 헬퍼·캐시버스터·서빙 content-type·아이콘 권한 403) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff clean.
  - [x] Playwright 격리(Identicon 결정론적·seed별 구분·SVG 렌더).
  - [x] **라이브 라운드트립**(임시 web 적용): 스키마 ALTER 적용 확인·avatar_url 직렬화, PNG 업로드→avatar_url→서빙 200(image/png)·nosniff 헤더, SVG 업로드 거부, 삭제→null. 라이브 검증이 fast-path 스키마 누락 버그 포착.
  - [x] **outside-voice 적대적 보안 리뷰 SHIP**(BLOCKER 0; MAJOR[nosniff] 흡수, SVG차단·MIME불신·traversal 0·본인강제·권한게이트·멱등스키마 PASS).
- 비변경: 기존 RBAC 카탈로그(product.manage 재사용, 신규 권한 0)·기존 엔드포인트·메시지 경로 0. email/Gravatar 미도입.
- [ ] (잔여) 배포(web 재빌드) + PB-0008 Windows 시각검증(아바타/아이콘 업로드·Identicon 표시).

## 0z. TASK-0266 (직전, 머지됨) — TASK-0263 핫픽스: usage/conversations 의 interval 파라미터 PG 문법 오류
- 증상: TASK-0263 배포 후 `GET /api/admin/usage/conversations` 가 **HTTP 500**(`psycopg.errors.SyntaxError: syntax error at or near "$1"`). 단위 테스트(fake cursor)는 SQL 미실행이라 통과시켰고 **라이브 엔드포인트 검증에서 포착**.
- 등급: **Minor §12.3** (핫픽스, 1줄 SQL 문법 수정).
- 원인: `_query_usage_conversations` 의 `win = "now() - interval %s"` — PG 는 `interval` 키워드 뒤 파라미터 placeholder(`interval $1`)를 불허(문자열 리터럴 문법만). admin_llm_usage 는 `interval '{days} days'`(int 보간)라 무관했으나, 파라미터화하려다 문법 위반.
- [x] **수정**(app.py 1줄): `now() - interval %s` → `now() - %s::interval`(캐스트 문법은 파라미터 허용, days 바인드 유지). 다른 win 패턴(int 보간)은 무변경.
- [x] **회귀 가드**(test): `test_q2b_interval_cast_not_bare_param` — 생성 SQL 에 `%s::interval` 존재 + bare `interval %s` 부재 정적 검증(fake cursor 가 못 잡던 클래스). test_usage_conversations.py **12 PASS**(기존 11 + 가드 1).
- [x] **라이브 검증**(worktree app.py 임시 적용): admin 전체 34건 200·좌표/본문 누출 0, 일자 차원 필터(2026-06-15) 1건·차트 by_day 정합, profile 200.
- 교훈: SQL 빌더 변경은 fake cursor 단위테스트로 불충분 — **라이브 엔드포인트(실 PG) 검증을 게이트화**([[feedback_frontend_real_browser_gate]] 의 백엔드 판). 회귀 가드는 SQL 문자열 정적 검증으로 보완.
- [ ] (잔여) 정식 배포(web 재빌드 — 현재 임시 복사본 실행 중) + PB-0008.

## 0z. TASK-0262 (직전 cycle, 머지됨) — 선택 제품 chip dot 도 네트워크 상태색 (TASK-0261 후속)
- 사용자 보고: 드롭업 **목록** 항목 dot 은 상태색 정상이나, **선택된 제품(composer chip 트리거)** 은 상태 무관 **파란색**(pinned 모드색). "선택 제품도 색상을 상태값과 동일하게."
- 원인: TASK-0261 은 `buildProductDropupItem`(드롭업 목록 항목)에만 conn 색 적용. `renderProductChip`(트리거 chip)은 `dataset.mode` 만 설정 → `#productChipDot` 이 모드색(`[data-mode=pinned]`=`--primary` 파랑)만 표시.
- [x] **프론트 전용 수정** (`app.js renderProductChip`): pinned 제품의 `conn_status_overall`(TASK-0261 백엔드가 이미 `state.products` 에 첨부, 추가 변경 0)을 chip dot 에 `.composer-product-chip-dot--conn` + `connStatusMeta` 클래스(is-ok/is-fail/is-unknown) 적용. dot 은 aria-hidden 이라 상태를 chip `aria-label` 에 병기. 매 렌더 conn 클래스 reset(auto/미바인딩 전이 시 모드색 복귀).
- [x] **CSS** (`styles.css`): `.composer-product-chip .composer-product-chip-dot--conn.{is-ok,is-fail,is-unknown}` 색 규칙 — 드롭업 conn 규칙과 동형(specificity 0,3,0, 모드색 규칙보다 소스 뒤 → override). 캐시버스터 `?v=20260615-task0262-chip-conn-color`(index.html styles.css·app.js).
- [x] 검증: `node --check`(app.js) PASS + CSS brace 1131=1131 + `make test` 회귀 0(frontend-only)·ruff clean.
- [x] 배포(web, main `eb7be30`) + PB-0008 Windows-browser 시각검증 **PASS**(TASK-0262b) — 선택 제품 94(unstable)=빨강 rgb(220,38,38)/is-fail, 95(healthy)=초록 rgb(22,163,74)/is-ok, auto=회색(conn 클래스 reset). aria-label 상태 병기. TEST.md §4 2026-06-15 Run.

## 0a. TASK-0263 (current cycle) — LLM 사용량 차트 hover 비용 + 클릭→집계 기여 대화목록 모달
- 목표: 사용량 차트에서 (a) hover 시 모델별 비용 표시, (b) 차트 요소 클릭 시 그 집계(모델/역할/계정/일자)에 기여한 대화목록을 모달로 표시. 적용 면: 작업 화면 프로필(본인) + 관리 콘솔 LLM 사용량(admin).
- 등급: **Major §12.3** (신규 read 엔드포인트 2개 + admin 이 타 사용자 대화 메타 조회하는 인가 표면).
- 사용자 결정(AskUserQuestion): 대화목록 표시=**모달/드로어 패널**, admin 접근 범위=**기존 권한 재사용**(신규 RBAC 0).
- 구현(백엔드, app.py):
  - [x] `GET /api/admin/usage/conversations`(console.usage.read + conversation.list.any AND 게이트) + `GET /api/profile/usage/conversations`(로그인, owner=self 강제).
  - [x] `_query_usage_conversations`: llm_usage ⋈ core_conversations(INNER + conversation_id NOT NULL — insight/시스템 비대화 제외) 차원 필터(model=COALESCE(resolved,model) / account_ids / day=to_char(date_trunc(gran)) / owner) → 대화별 호출·토큰·비용·models[] fold. 차원 SQL 은 admin_llm_usage 집계와 동일 규칙(차트↔목록 정합). 좌표/비번/본문 비노출, _USAGE_CONV_LIMIT=200 + truncated.
  - [x] `_usage_account_ids_for_role`(역할→계정 집합 역매핑: 시스템→None, 역할없음/역할명), `_parse_usage_conv_params`, `_enrich_usage_conv_owner_meta`(admin 만 owner 사용자명/역할).
  - [x] by_day_model·by_model 에 cost_usd 추가(admin·profile 둘 다 hover 비용용), profile totals.cost_usd 추가.
- 구현(프론트):
  - [x] admin.js: renderStacked(일별)·renderStackedHBar(역할/계정) tooltip 에 모델별 비용 병기. 차트 요소에 data-usage-model/day 후크 + `bindUsageDrill`(위임 클릭)·`openUsageConversations`(fetch)·`showUsageConvModal`(모달 렌더, deep-link `/?conversation=`). 계정 drill-down 행 클릭→대화 모달.
  - [x] app.js(프로필): renderProfileUsageStacked/Donut `<title>`에 비용 병기 + 클릭 후크 + `bindProfileUsageDrill`·`openProfileUsageConversations`·`showProfileUsageConvModal`. 추정 비용 카드 추가. `initializeWorkspace` 가 `?conversation=` deep-link 선호 활성화(URL 정리).
  - [x] styles.css: usage-conv 모달(admin 넓은 판 + profile 독립 판) + clickable 커서. 캐시버스터 `?v=20260615-task0263-usage-drill`(index/admin html).
- 검증:
  - [x] node --check app.js/admin.js + py_compile + CSS brace(1156=1156).
  - [x] 신규 `test_usage_conversations.py` **11 PASS**(fold·INNER JOIN·차원 필터 WHERE/params·좌표 비노출·빈 account 단락·admin AND 게이트 403×2·시스템역할 빈목록·profile 권한상승 차단·역할→계정 역매핑) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff clean.
  - [x] Playwright 격리(차트 막대 클릭→model/day 차원 추출→모달 opener 호출).
  - [x] **outside-voice 적대적 보안 리뷰 SHIP**(REV-20260615-0262, BLOCKER/MAJOR 0 — 파라미터화 SQL+화이트리스트 gran/fmt·AND-게이트·profile self-scope·메타only·NULL 가드·차트정합 전부 통과).
- [ ] (잔여) 배포(web 재빌드) + 라이브 엔드포인트 검증 + PB-0008 Windows 시각검증(차트 hover 비용·클릭 모달·대화 deep-link) — CHECK#13 WARN-only.

## 0b. TASK-0261 (직전 cycle, 머지됨) — 대화 화면 제품 드롭업 datasource 네트워크 상태 배지
- 목표: 대화 화면 제품 선택 드롭업의 각 제품 dot 이 지금까지 **모드색(auto 회색/pinned 파랑)만** 표시 → datasource 연결(네트워크) 상태(healthy/unstable/unknown)를 색으로 반영. (사용자: "현재는 회색, 파란색만 표시 중".)
- 등급: **Minor §12.3** (비파괴 추가 — 좌표/비밀번호 비노출, status/elapsed/checked_at 만).
- 데이터 소스: conn-health-monitor(TASK-0250)가 백그라운드로 미리 계산한 per-datasource 상태(`conn_health.snapshot()`). admin_list_datasources 와 동일 — 추가 probe 없음.
- 구현:
  - [x] 백엔드 `_attach_product_conn_status(conn, products)`(app.py): 각 product 의 `datasources[]` 항목에 `conn_status`{status,elapsed_ms,checked_at} 첨부 + product 레벨 `conn_status_overall`(바인딩 최악 상태: unstable>unknown>healthy). `datasources.resolve(key)→scope_key` 로 snapshot 매핑(admin 의 all_datasources→scope_key 와 동일 키). conn_health 미가용/resolve 실패 graceful(unknown). 바인딩 없는 기본 단일 MySQL 제품은 overall=None.
  - [x] `/api/session`(get_session)·`/api/auth/me`(auth_me) 두 대화 부트스트랩 호출 직후 enrich(다른 _list_products 호출처[admin]는 무영향).
  - [x] frontend `buildProductDropupItem`(app.js): `connStatusOverall` 받아 dot 에 `.product-dropup-item-dot--conn`+`.is-ok/.is-fail/.is-unknown` + title/aria-label. `connStatusMeta(status)` 헬퍼. datasource 배지 tooltip 에 각 datasource 상태 라벨 병기.
  - [x] CSS(styles.css): conn 상태 dot 색(specificity 0,3,0 > 모드 0,2,0 override) — is-ok=success(초록)/is-fail=danger(빨강)/is-unknown=중립.
  - [x] 캐시버스터 bump: index.html styles.css·app.js → `?v=20260615-task0261-conn-badge`.
  - [x] node --check app.js PASS + CSS brace(1128=1128) + py_compile app.py PASS.
  - [x] 신규 `test_product_conn_status.py` 8 PASS(C1 단일 healthy / C2 멀티 최악 unstable / C3 unknown 우선순위 / C4 바인딩없음 None / C5 좌표 비노출 / C6·C6b graceful / C7 빈목록) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff clean.
  - [x] Playwright headless chromium 격리: healthy=초록/unstable=빨강/unknown=중립/바인딩없음=모드색 파랑 유지 — CSS override 실증.
- 비변경: 백엔드 RBAC·스키마·엔드포인트 shape(응답 필드 추가만)·conn_health 모니터 0. admin 경로 _list_products 무영향.
- [ ] (잔여) 배포(web 재빌드) + PB-0008 Windows-browser 시각검증(드롭업 dot 색이 연결 상태 반영; 라이브 mysql-kr-an2-*=unstable[빨강], mysql-local/mssql-*=healthy[초록]) — CHECK#13 WARN-only.

## 0b. TASK-0260 (직전 cycle, 머지됨) — 결과셋 ◀▶ 전환 시 확장 높이 보존(스크롤 점프 제거)
- 목표: assistant 답변 안에서 결과셋을 ◀▶ 버튼으로 전환할 때, 결과셋마다 높이가 달라 panels 컨테이너가 줄었다 늘었다 하며 아래 콘텐츠/스크롤이 jump 한다. 지금까지 본 **최대 패널 높이를 floor 로 보존**해 점프 제거.
- 등급: **Minor §12.3** (frontend-only, 비파괴 — 표시 UX 전용).
- 근본 원인: `.sql-nav-panels` 가 min-height 없이 display 토글만 함 → 활성 패널 높이로 컨테이너가 매번 재조정. `.result-table-wrap` 의 `max-height: min(60vh,460px)` 때문에 결과셋별 높이 편차가 큼.
- 수정 (frontend-only, 4파일):
  - [x] `app.js` `buildSqlNavigator`: `maxPanelHeight` 추적 + `preserveHeight()`(panels.scrollHeight floor) — `update()` 전환 전·후 2회 측정(나가는/들어오는 패널 모두 반영, 축소만 방지·확장 허용).
  - [x] `share.js` `buildSqlNavigator`: 동일 로직 parity(공유 뷰도 동일 navigator).
  - [x] 캐시버스터 bump: index.html(app.js)·share.html(share.js) → `?v=20260615-task0260-sqlnav-height`.
  - [x] `node --check` app.js/share.js PASS.
  - [x] Playwright headless chromium 격리 검증: 큰(1000px)→작은(2행) 전환 시 panels.h 불변(minHeight floor)·아래콘텐츠 점프 **0px**. 수정 전 대조 = **960px 점프** 재현.
- 비변경: CSS(styles.css/share.css) 0 — min-height 는 JS inline 으로 동적 설정. 백엔드/스키마/RBAC/엔드포인트 0.
- [ ] (잔여) 배포(web 만 — frontend) + PB-0008 Windows-browser 시각검증(다중 결과셋 대화에서 ◀▶ 전환 시 스크롤 점프 없음, CHECK#13 WARN-only).

## 0b. TASK-0255 (cross-feature, current cycle) — insight datasource health 관리콘솔 표면화
- [x] web `admin_list_datasources` 에 `insight_health` 첨부(`_read_insight_datasource_health`, RO·graceful·console.access) + admin.js `datasourceInsightHealth`/배지 enrich/`_dsInsightHealthLabel`/상세 "인사이트 스캔 상태" 행 — **연결 불안정 vs 권한 실패 구분**. 주 변경=agent-core R2(REV-20260615-0255). 자격증명 비노출.
- [x] 배포 후 PB-0008 Windows-browser 시각검증("인사이트 스캔 상태" 행, CHECK#13) — **PASS**(불안정=⚠연결 불안정 / 정상=분석됨 구분 실증, main `a410986`). TEST.md §4 2026-06-15 Run.

## 1. Current Status
- State: in_progress
- Owner: AI
- Priority: minor (TASK-0124 RBAC 권한 정합 + TASK-0125 UX 2차 보완 — ux-compact-redesign 병합)
- Last Updated: 2026-06-15 (TASK-0270 계정 override 편집기 게이트 — '허용' 외에 '상속(허용)'(override 상속 + 역할이 부여)에도 자식 펼침; `_applyPermissionDisclosure`/`renderPermissionGrid` 에 inheritedGrants(역할 permission_codes=상속 baseline) 전파, override gateSatisfied=allow||(inherit&&inheritedGrants.has); 역할 모드·enforcement·저장 경로 무변경; perm test 16 PASS(V7)+jsdom 8/8+make test 회귀 0; frontend-only; REV-20260615-0270. // TASK-0269 운영 권한 대화 그룹 분리 — `내 대화 권한`(conversation_own 13)/`전체 대화 권한`(conversation_any 10) 2그룹 + `.any→.own` 1:1 종속을 "목록 조회 게이트 > 동작" 카테고리로(create/list.own/list.any 루트, 내 동작→list.own·전체 동작→list.any); app.py group 분리(code·enforce 불변)+admin.js/app.js 섹션/라벨/permissionGroupOf; outside-voice [SUBAGENT] SHIP(enforcement byte-identical); perm test 15 PASS(M4/V2/T2) + jsdom 20/20 + make test 회귀 0; frontend-only; REV-20260615-0269. // TASK-0267 권한 grid 트리(tree) UI 재구성 — `.permission-grid-list` 2열 grid→단일 열 flex column + `_orderItemsAsTree` 트리 DFS(부모→자식 들여쓰기, `data-perm-depth`) → 행 숨김 시 가로 reflow 뒤틀림 0·"더 보기 부여됨" 빨강 가시성 회복; disclosure/게이트/저장/RBAC 무변경; perm test 15 PASS(T1~T4 트리) + jsdom 14/14 + make test 회귀 0; frontend-only; REV-20260615-0267. // TASK-0264 권한 disclosure 추가 단순화 — 게이트 미충족 시 부여된 세부 권한도 "더 보기" 뒤로 숨김(forceVisible 제거); 부여 항목 그룹은 유지+"더 보기 · N개 부여됨"으로 도달성 보존; 적대 리뷰 SHIP-WITH-FIXES[override-grid `[hidden]` 미적용 → CSS unscope]; perm test 11 PASS + jsdom 17/17 + make test 회귀 0; frontend-only; REV-20260615-0264. // TASK-0258 TASK-0257 핫픽스 — disclosure hidden row 가 실브라우저에서 안 숨겨지던 `[hidden]` CSS override 버그(`.permission-toggle-card{display:flex}` 가 UA `[hidden]{display:none}` override → `el.hidden=true` 무력화, jsdom 미검출·PB-0008 검출). styles.css 에 `.permission-section/group[hidden] + [data-perm-code][hidden] { display:none !important }` 강제; 신규 회귀 가드 test_c1 포함 11 PASS + 실브라우저 computed display 재확인; frontend-only; REV-20260615-0258. // TASK-0257 관리 콘솔 계정·역할 권한 편집기 점진적 세분화 — 종속성 맵 `PERMISSION_DEPENDENCIES`(31엔트리, 마스터 게이트 console.access + 그룹 base 게이트 + 운영 .any→.own) 기반 row 단위 progressive disclosure; 비파괴(부여 권한+조상 항상 표시·저장 누락 0)·"세부 권한 더 보기" 탈출구·orphan 경고칩; 적대 리뷰 SHIP-WITH-FIXES 흡수[override 모드 그룹 도달불가 trap → 그룹 vanish=checkbox 한정·override 비숨김]; 신규 10 테스트 + jsdom 30/30 + make test 회귀 0; §10.6 disclosure 계층 명문화; frontend-only; REV-20260615-0257. // TASK-0253 관리 콘솔 head-of-line blocking 2건 제거 — [A] datasource /test 연결테스트가 async 핸들러에서 동기 probe 직접 호출로 이벤트루프 블로킹 → `asyncio.to_thread` 이관 + 프론트 ↻ refresh 중복 probe 제거; [B] 제품 분석 완료율이 전체 1회 fetch+전역 로딩플래그라 가장 느린 제품 대기 → 제품별 `?product_id=` 단건 병렬[cap 4]+제품별 로딩상태로 개별 즉시표시; outside-voice SHIP-WITH-FIXES 흡수[MAJOR-2 fan-out cap·MINOR-2 force dedup·MINOR-3 fake 시그니처]; 신규 8 테스트 + 전체 회귀 0; 동시세션 share-navigator 가 TASK-0251 선점→재번호 0253; REV-20260612-0253. // TASK-0250 연결 health 모니터 — 관리 콘솔 datasource 연결상태를 백그라운드 모니터 사전계산값으로 즉시 표시[lazy probe 세마포어 자동경로 폐기]; 코어=feature-0002 conn_health.py, web 측은 startup 훅+conn_status 첨부; REV-20260612-0250 [동시세션 머지, base 위 rebase]. // TASK-0249 제품 insight 완료율 멀티 datasource(1:N) + 대소문자 매칭 수정 — 킹스레이드(KR_QA id 94) 7 접근 DB 가 각각 다른 datasource(서버)에 바인딩된 진성 1:N 인데 coverage 가 primary datasource 하나로 전부 질의해 0/0 + Linux MySQL lower_case_table_names=0 대소문자 미스매치 복합 → `_compute_product_insight_coverage` datasource_key 별 그룹핑 + db.py `LOWER(TABLE_SCHEMA)` 매칭; 신규 5 테스트 + 전체 599 passed 회귀 0; REV-20260612-0249. // TASK-0243 MSSQL db-insights catalog 귀속 수정 — TASK-0242 의 by_db 가 schema_name 으로 묶여 MSSQL[schema_name=dbo]에서 등록 DB[catalog]와 차원 불일치로 "역할 미파악" → object_key 에서 engine·object_type별 catalog 파싱(`_db_catalog_from_object_key`)으로 그룹핑. MySQL 무회귀(catalog==schema_name), 단일 함수 격리(coverage/reset 무영향), 17 테스트 + 전체 회귀 0; REV-20260612-0243. // TASK-0242 관리 콘솔 제품 데이터소스 — 각 DB 행에 insight-worker 파악 내용[역할/도메인] 한 줄 인라인 표시 + `+ 데이터베이스 추가` picker 에 도메인 힌트·분석상태 3-state[미분석/분석중/분석됨]; 신규 read 엔드포인트 `GET /api/admin/products/{id}/db-insights`[console.access·바인딩 datasource 검증] + `_compute_product_db_insights`[rag_objects ⋈ texts DB별 묶음] + worker heartbeat liveness; frontend `buildDbRoleCell`/`buildPickerInsightMeta`·.cov-db-row 7컬럼; RBAC·스키마·coverage 계산 0; 신규 14 테스트 + make test 회귀 0; REV-20260612-0242. // TASK-0240 datasource picker 클리핑 수정 + 데이터소스 추가 체크박스 토글 통일 — ① `+ 데이터베이스 추가` 드롭다운이 패널 내부에서 잘림: `.ds-acc-body{overflow:hidden}`(TASK-0239 펼침 애니메이션 때 도입)이 가장 가까운 클립 조상 + `.admin-detail-col{overflow-y:auto}` 스크롤 컨테이너가 2차 경계 → absolute 드롭다운을 **inline 정상 흐름**으로 전환(클리핑 원천 제거, body overflow 도 제거); ② `+ 데이터소스 추가` select → DB picker 와 동일한 **inline 체크박스 토글 드롭다운**으로 통일(체크=추가 스테이징/해제=제거 스테이징, 바인딩된 것도 체크 상태로 표시). Playwright clip 조상 재현(ds-acc-body·admin-detail-col·admin-workspace 3중) → 4-test(DB picker 무클리핑·ds picker 체크박스 무클리핑·체크 추가 스테이징[서버 불변]·⋯ 메뉴 정상) + 토글 양방향(체크+1→해제 baseline 복귀) PASS, 콘솔 0; TASK-0239 datasource accordion 후속 3건 — ① ⋯ 행 메뉴가 안 열림: `.ds-acc-row{overflow:hidden}` 가 행 아래로 드롭되는 absolute 메뉴를 클리핑(hit-test 가 메뉴 대신 뒤 요소를 맞힘) → overflow 제거 + head 모서리 라운딩으로 시각 유지[Playwright hit-test 재현·수정·재검증]; ② datasource 추가/제거/기본지정이 즉시 API 라 다른 콘솔 편집과 달리 "모두 적용" 일괄 흐름 밖 → `pending.productDatasources`(baseline↔desired) 스테이징 + applyAllPending 에서 diff(제거→추가→primary) 일괄 호출, 제거된 datasource 의 접근DB PUT skip(서버가 함께 삭제); ③ 행 클릭 시 깜빡임 → 전환을 전체 renderProductDetail() 대신 accordion 로컬 재렌더 + redrawChips 동기 호출(빈 화면 flash 제거) + body 펼침 애니메이션(prefers-reduced-motion 존중). **Playwright 실브라우저 4-test(⋯ 클릭가능·추가 스테이징[서버 불변]·전환 무깜빡임·일괄적용 서버반영) + 제거 일괄적용 PASS, 콘솔 0**; TASK-0238 datasource 패널 통합 재설계 — datasource 정보 3중 중복(칩+편집대상 select+헤더배지)·3가지 모양(pill/점선pill/둥근행) 제거하고 datasource=펼침 accordion 행(선택기=상태표시=바인딩관리) + 행별 ⋯ 메뉴(연결테스트/기본지정/제거)로 통일. gstack /design-review + codex outside-voice 감사 → Playwright 실브라우저 재설계 검증(펼침/전환/추가 + 단일/멀티/MSSQL); TASK-0236 datasource UI 바인딩 변경 후 미갱신 근본수정 — 바인딩 add/remove/set-primary 후 부분 갱신이 아닌 renderProductDetail() 전체 재렌더로 편집대상 select·헤더 배지·접근DB 목록 일관 재구축 + _editDsKey TDZ 잠복버그 수정[≥2 바인딩 제품 렌더 시 ReferenceError→패널 blank]; **Playwright 실제 헤드리스 브라우저로 재현·수정·재검증**; TASK-0234 datasource UI 사용성 버그 2건 — ① 연결 테스트 버튼: 바인딩 존재 시 드롭다운 value='' 라 테스트 불가 → 각 datasource 칩에 per-chip ⟳ 연결테스트 추가, ② 선택 DB↔datasource 소속 불명 → "접근 가능 데이터베이스" 헤더에 편집 대상 datasource 배지; TASK-0233 datasource multi-bind UI 접근성 보강 — ★/× 칩 버튼 aria-label + 비동기 disabled 중복요청 차단 + 두 select aria-label + 24px 터치타깃 + focus-visible + 빈 상태 CTA [gstack /design-review 감사 H1~H3·M1~M4 흡수]; TASK-0230 멀티 datasource 1:N — 제품 ↔ 여러 datasource 참조: WebProductDatasources join 테이블 + admin add/remove/list 엔드포인트 + 접근DB datasource 차원화 + admin UI 칩 multi-bind/편집대상 선택기 + 제품 프롬프트 다중 datasource DB 인지 + 대화화면 다중 배지; TASK-0229 관리 콘솔 제품 상세 `접근 가능 데이터베이스` UI 통합 — DB chip↔insight 완료율 1:1 중복 제거 + 시스템 DB 단일 묶음 칩(hover/focus 툴팁); TASK-0228 datasource SSRF 사설망 경계 env 토글; TASK-0223 제품 프롬프트 자동작성 실데이터 정합 재작성 + MSSQL database-aware 3계층 인사이트 + ask-worker grounding 검증 + _log F821 hotfix; TASK-0218 관리 콘솔 대시보드 CloudWatch 스타일 재구성 — 주/보조 위계+추세 sparkline+새로고침/auto-refresh+fail-loud+drill-down+drag+접근성; TASK-0216 제품 프롬프트 자동 작성 품질 강화 — topic 집계/fact_entries 타입 확장/summary 샘플; TASK-0210 관리 콘솔 대시보드 보강 — 카테고리별 위젯 그리드 + per-account 커스터마이즈/영속; TASK-0198 LLM 사용량 모델별 필터/선택 + 모델별 요약 카드 + 가로 스크롤 제거; TASK-0188 공유 대화 markdown 미적용 수정 + 수신자 가독성 디자인; TASK-0184 계정 drill-down + 프로필 사용내역 차트 + 내 활동기록 제거; TASK-0181 역할/계정 모델 stacked + 요청 수; TASK-0180 카테고리별 행 레이아웃; TASK-0179 차트 grid; TASK-0178 여백 컴팩트화; TASK-0177 상세표 비용컬럼+디자인 정렬; TASK-0176 역할/계정별 비용 차트; TASK-0167 작은화면 잘림)

## 2. Task Queue

### TASK-0270 계정 override 편집기 게이트 — 허용/상속(허용) 시 펼침 (2026-06-15)
- [x] **Minor §12.3** — 사용자 요청(역할 트리 후속): 계정 override 편집기에도 동일 tree(공유 적용) + 게이트가 '허용' 또는 '상속(허용)'(상속+역할 부여) 시 펼침. **진단**: 기존 override gateSatisfied=allow 만 → 상속 게이트 역할 부여해도 안 펼침. **수정(admin.js)**: `_applyPermissionDisclosure(.., inheritedGrants)` + override gateSatisfied = allow OR (inherit AND inheritedGrants.has(code)); renderPermissionGrid opts.inheritedGrants; 계정 호출부가 역할 `permission_codes`(상속 baseline=백엔드 effective 동일 출처)로 구성. **비변경**: 역할 모드·enforcement·override 저장 경로·트리/가시성·RBAC 0. **검증**: perm test 16 PASS(V7) + make test 회귀 0 + node --check + jsdom 8/8. REV-20260615-0270 [SKIPPED:ui-disclosure-gate]. **완료**: 배포 + **PB-0008 PASS**(계정 override 상속(허용) 게이트 펼침 computed display 실측; TEST.md §4 2026-06-15). worktree `ai/claude/account-override-inherit-gate`(base 73755e9=main).

### TASK-0269 운영 권한 대화 그룹 분리(내 대화/전체 대화) + 목록 조회 게이트 트리 (2026-06-15)
- [x] **Minor §12.3** — 사용자 요청(역할 트리 후속): 운영 권한 대화를 `내 대화 권한`/`전체 대화 권한` 2그룹 분리 + `.any→.own` 1:1 종속을 `생성·조회(기반) > 동작` 카테고리로. 사용자 AskUserQuestion 확정: 게이트=목록 조회. **수정(frontend-only)**: ① app.py conversation group 코드 기반 분리(.any→conversation_any 10, 그외→conversation_own 13; code·enforce 불변). ② admin.js+app.js group order/labels(내 대화 권한/전체 대화 권한)/operate 섹션/permissionGroupOf. ③ PERMISSION_DEPENDENCIES: create/list.own/list.any 루트, 내 동작→list.own·전체 동작→list.any. **적대 리뷰 SHIP**(REV-20260615-0269 [SUBAGENT:rbac-adversarial]): enforcement byte-identical·group 소비자 graceful·dep 무순환·GroupName 무절단·멱등 전부 refute. **검증**: perm test 15 PASS(M4/V2/T2 갱신) + make test 회귀 0(백엔드 RBAC 무회귀) + node --check + jsdom 20/20. **완료**: 배포 + **PB-0008 PASS**(내 대화/전체 대화 2그룹 분리·목록 조회 게이트 트리 실측; TEST.md §4 2026-06-15). worktree `ai/claude/conv-perm-own-any-split`(base c34f0f9=main).

### TASK-0267 권한 grid 트리(tree) UI 재구성 — 2열 grid 뒤틀림 해소 + 빨강 가시성 (2026-06-15)
- [x] **Minor §12.3** — 사용자 보고(관리 권한 정상 후 운영 권한 테스트 중): ① "더 보기 · N개 부여됨" 빨강이 운영 권한서 안 보임 ② 항목 숨김 시 기존 항목 뒤틀림 → 상위 권한 tree UI 요청. **진단**: `.permission-grid-list` 2열 grid → 행 숨김 시 가로 reflow 뒤틀림 + "더 보기" 빨강 묻힘(badge 로직·CSS 는 라이브 정상 rgb(180,35,31)). **수정(frontend-only)**: ① admin.js `_orderItemsAsTree` — 그룹 내 권한 PERMISSION_DEPENDENCIES 트리 DFS(부모→자식 들여쓰기) + `data-perm-depth`(루트0/자식+1), 누락 안전망. ② styles.css **2열 grid → 단일 열 flex column** + depth 들여쓰기·좌측 가이드·tick 연결선 → 자식 숨김 시 부모 제자리·가로 reflow 0. `.permission-group-more` flex화, row-dependent accent 제거. **비변경**: disclosure 가시성·게이트·도달성·저장 경로·has-granted 빨강·RBAC 0. **검증**: perm test 15 PASS(기존 11 + T1~T4 트리/depth/단일열 CSS) + make test 회귀 0 + node --check + CSS brace(1167) + jsdom 14/14. **완료**: 배포 + **PB-0008 PASS**(단일 열 트리·자식 24px 들여쓰기·운영 권한 "부여됨" 빨강 rgb(180,35,31) 가시·뒤틀림 0 실측; TEST.md §4 2026-06-15). REV-20260615-0267 [SKIPPED:ui-tree-layout]. worktree `ai/claude/perm-tree-ui`(base f0279c3=main).

### TASK-0264 권한 disclosure 추가 단순화 — 게이트 미충족 시 부여 항목도 숨김 (2026-06-15)
- [x] **Minor §12.3** — 사용자 보고: "`세부 권한 N개 더 보기` 클릭 전인데 항목이 노출되는 버그 — 최대한 단순화하여 숨김". **원인**: TASK-0257 의 비파괴 `forceVisible`(부여 권한+조상을 게이트 OFF 라도 항상 표시)이 게이트 OFF·부분부여 역할서 부여 항목 노출(이전 AskUserQuestion "비파괴" 선택을 실사용 후 "최대한 숨김"으로 전환). **수정(admin.js)**: `forceVisible` 제거 → row 는 게이트 체인 충족 시에만 노출(부여 무관); 게이트 reveal·마스터 게이트·own→any 불변. **도달성 보존**(적대 리뷰 안전속성): 부여 항목 있는 그룹 vanish 안 함 + "더 보기 · N개 부여됨"(`.has-granted`) + 그룹 헤더 `N/M 선택` 카운트, 저장 누락 0. orphan 칩 제거. **적대 리뷰 SHIP-WITH-FIXES→흡수**(REV-20260615-0264 [SUBAGENT]): 안전 전부 refute; MINOR — 계정 override 편집기 컨테이너 `.override-grid`≠`.permission-grid` 라 TASK-0258 `[hidden]` 강제 미적용 → CSS 셀렉터 컨테이너 무관 unscope(test_c1 강화). **검증**: perm test 11 PASS(V1/V4/V5/V6 새 동작 + C1 unscoped) + make test 회귀 0 + node --check + CSS brace(1130) + jsdom 17/17. 캐시버스터 `?v=20260615-perm-collapse-granted`. **완료**: 배포 + **PB-0008 PASS**(checkbox/override 두 편집기 부여 항목 게이트OFF computed display:none 실측; TEST.md §4 2026-06-15). worktree `ai/claude/perm-disclosure-collapse-granted`(base 033ec9d=main).

### TASK-0258 TASK-0257 핫픽스 — disclosure hidden row CSS override 버그 (2026-06-15)
- [x] **Minor §12.3** — TASK-0257 배포 후 PB-0008 시각검증 중 발견: within-group 행 게이팅이 실브라우저에서 무력(`관리 콘솔 접근` 체크 후 `계정 조회`만 보여야 하는데 계정 권한 7개 다 보임). **원인**: `.permission-toggle-card{display:flex}`(author, 0,1,0) 가 UA `[hidden]{display:none}`(0,1,0) 를 동일 specificity·후순위로 override → `el.hidden=true` 무력(computed display:flex). jsdom 은 CSS 캐스케이드/렌더링 없어 30/30 통과시킴 → **실브라우저(PB-0008)만 검출**([[feedback_visual_verify_on_design_change]]·TASK-0236 교훈 입증). **수정(styles.css 1규칙)**: `.permission-section[hidden], .permission-group[hidden], .permission-grid [data-perm-code][hidden] { display:none !important }`(기존 `.search-modal-overlay[hidden]` 선례 동형). 캐시버스터 `?v=...-hidefix`. **검증**: 신규 회귀 가드 `test_c1_hidden_rows_force_display_none` 포함 **11 PASS** + make test 회귀 0 + CSS brace(1125=1125) + 실브라우저 수정 CSS 주입 후 computed display 재확인(account.read=flex, 나머지 6개=none). 동작 strictly safer(hidden 행을 *실제로* 숨김 — 권한 드러내지 않음). REV-20260615-0258 [SKIPPED:css-display-hotfix]. **완료**: 배포 + **최종 PB-0008 PASS**(배포 CSS 로 계정 6개 행 computed display:none 실측; TEST.md §4 2026-06-15). worktree `ai/claude/perm-disclosure-hidden-css`(base 4782fd3=main).

### TASK-0257 관리 콘솔 계정·역할 권한 편집기 점진적 세분화 (2026-06-15)
- [x] **Major §12.3** (권한 편집 surface) — `관리 콘솔 > 계정, 역할 > [각 항목]` 의 카테고리별 권한 grid 가 전 권한을 평면 노출해 핵심 게이트가 묻히던 것을, 종속성 기반 row 단위 progressive disclosure 로 점진 세분화. **설계(frontend-only `src/static/admin.js`)**: 선언적 `PERMISSION_DEPENDENCIES`(child→선행 parent, 31엔트리) — 관리 권한 마스터 게이트 `console.access`(account.read/role.read/audit.read.own/system_prompt.global.read 부모=console.access → OFF 시 계정·역할·감사·설정 그룹 vanish), 그룹 base 가 세부 게이트; 운영 권한 `.any`→`.own`. **비파괴(사용자 AskUserQuestion 확정)**: 부여 권한+조상 항상 표시(forceVisible), disclosure 는 접을 뿐 제거 안 함, 저장 경로가 hidden row 도 읽어 누락 0; "세부 권한 더 보기" 강제 노출 + orphan 경고칩. §10.6 정렬·DOM 불변(row 단위 hidden 토글, 레이아웃 뒤틀림 0). **적대 리뷰 SHIP-WITH-FIXES→흡수**(REV-20260615-0257): #1 안전속성(부여 권한 미숨김·저장 누락 0) 400k fuzz refute; MAJOR(override 모드 그룹 도달불가 trap) 흡수 → 그룹/섹션 vanish=checkbox 모드 한정·override 비숨김(§10.6 "전체 표시" 정합); MINOR(dead branch) 흡수. **비변경**: 백엔드 RBAC enforce·권한 code·persistence·엔드포인트·스키마 0. **검증**: 신규 `test_permission_dependency_map.py` 10 PASS(M1~M4 맵정합 + V1~V6 가시성 불변식) + make test 컨테이너 회귀 0 + ruff clean + node --check + CSS brace(1113=1113) + jsdom 실 DOM 30/30 + verify-completion(CHECK#13 WARN=PB-0008 후속). **완료**: 배포 + **PB-0008 Windows-browser PASS**(관리 콘솔 접근 체크→그룹 등장·계정 조회 게이팅; TEST.md §4 2026-06-15). worktree `ai/claude/perm-progressive-disclosure`(base f8845cc=main). 동시세션 번호충돌 대비 머지 직전 origin/main 재확인(origin max=0256(diff 작업 선점)→0257).

### TASK-0254 제품 프롬프트 '자동 작성' 스트리밍 스크롤 stick-to-bottom (2026-06-15)
- [x] **PB-0008 Windows-browser 시각검증 PASS** (2026-06-15, 배포 main `f8845cc` 후) — 제품1(KR) 제품 프롬프트 '자동 작성' SSE 스트리밍 중 eval 자동 계측: ① HOLD 위로 스크롤(top=60) 후 토큰 8샘플 전부 top=60 고정(오버플로 748→852 증가) = 위치 유지 실증, ② FOLLOW 하단 이동 후 토큰 73샘플 전부 dist=0 = 최하단 추종 실증. 스크린샷 `artifacts/pb0008-task0254/{01,02}*.png`. TEST.md §4 Run 기록. CHECK#13 충족.
- [x] **Minor §12.3** — `관리 콘솔 > 제품 > [항목] > 제품 프롬프트` 의 '자동 작성'(TASK-0237 SSE 토큰 스트리밍)이 매 토큰마다 무조건 textarea 를 최하단으로 강제 이동시켜, 사용자가 작성 중인 본문 상단을 읽으려 위로 스크롤해도 다음 토큰에서 즉시 최하단으로 끌려가던 이슈. **수정(프론트 전용, `src/static/admin.js`)**: `handleFrame` 의 `token` 분기에서 append **직전** `atBottom = scrollHeight - scrollTop - clientHeight <= 8` 판정 → append 후 `atBottom` 일 때만 `scrollTop = scrollHeight`(무조건 강제이동 제거). 위로 스크롤한 상태면 위치 유지, 최하단이면 갱신을 따라감. 첫 토큰은 `value=""` 직후 빈 상태 → atBottom=true → 정상 추종. `done` 분기는 서버가 `.strip()` 된 prompt(app.py:16519)를 보내 누적(un-stripped)과 길이가 달라질 수 있으므로, 동일하면 재할당 생략 + 새 높이 `maxTop` 으로 clamp(최하단이었으면 새 최하단, 아니면 읽던 위치 유지)해 재할당發 상단 리셋·하단 점프 흡수. 캐시버스터 `?v=20260615-task0254-prompt-stream-scroll`. **outside-voice 적대 리뷰 SHIP-WITH-FIXES→흡수**(REV-20260615-0254): token 로직·8px 임계·첫토큰·비-오버플로 무회귀 전부 반박, LOW 1건(done 의 strip 길이차 점프) 흡수. **검증**: `node --check`(admin.js) PASS + 서버 `.strip()` 사실 확인(app.py:16519) + make test 컨테이너 **회귀 0 PASS**(진행 100%·skip 2·fail 0·make exit=0)+ruff clean + verify-completion 9 checks PASS(CHECK#13 WARN=PB-0008 후속). **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008 Windows-browser 시각검증(스트리밍 중 위로 스크롤 유지 / 최하단일 때만 추종). worktree `ai/claude/task0254-prompt-stream-scroll`(base 9c9a5b3=main).

### TASK-0253 관리 콘솔 head-of-line blocking 2건 제거 (2026-06-12)
- [x] **Minor §12.3** — TASK-0250 배포 후 PB-0008 시각검증 중 사용자 발견 2건. **(A) datasource ↻ 새로고침 지연**: 제품 상세 "+ 데이터소스 추가" 드롭다운 ↻ 클릭 시 N개 배지가 "확인 중…"에 9초+ 묶임(개별 /test 45~194ms, 동시 11개 시 8~18s). 원인: `admin_test_datasource`(async def)가 동기 블로킹 `_db.probe_datasource()`(도달불가 시 connection_timeout 8s 점유)를 await/executor 없이 직접 호출 → **이벤트 루프 블로킹** → 동시 /test 직렬화 + 프론트 refresh 가 같은 key 를 force:false(rebuild)+force:true(Promise.all) **2벌** probe(4-cap 세마포어 2배 점유). **(B) 제품 분석 완료율 일괄 대기**: 진입 시 좌측 목록·우측 상세 전부 "분석 측정 중…"이 가장 느린 제품까지 끝나야 한꺼번에 갱신. 원인: `admin_products_insight_coverage`(동기 def, Starlette 스레드풀 병렬 가능)인데 **프론트가 전체 제품 1회 fetch + 전역 `productCoverageLoading` 플래그**로 묶음. **수정(2 src + 2 test)**: (A) probe 를 `await asyncio.to_thread(_db.probe_datasource, …)` 스레드풀 이관(`/api/ask` `asyncio.to_thread(run_agent)` 패턴) → 이벤트 루프 비블로킹 → N개 /test 가 가장 느린 1건(≤timeout) 안에 완료. 프론트 refresh 는 `_rebuildDsAddList(true)` 단일 경로(중복 Promise.all 제거, `_kickDsConn(force)` 전파). (B) `loadProductInsightCoverage` 를 **제품별 `?product_id=N` 단건 병렬 호출**(동시성 cap `_COV_FETCH_MAX=4` via `_runWithConcurrency`) + 전역 플래그 → **제품별 `productCoverageLoadingIds` Set** + 끝나는 제품만 즉시 렌더(`_isProductCoverageLoading`). 백엔드 단건은 대상 제품만 계산 후 break. 캐시버스터 `?v=20260612-task0253-headofline`. **outside-voice 적대적 리뷰 SHIP-WITH-FIXES→흡수**(REV-20260612-0253): BLOCKER 0(SSRF pinned-IP/DNS-rebinding 유지·커넥션 누수 없음·break 안전·로딩 stuck 없음 — 전부 반박). 흡수: **MAJOR-2**(N-fan-out 이 공용 anyio 스레드풀[40] 고갈 → 한 레이어 위 head-of-line 재발 우려 → 프론트 `_COV_FETCH_MAX=4` cap 추가), **MINOR-2**(force 경로가 in-flight dedup 우회 → ↻ 연타 시 중복 probe → force 무관 dedup 합류), **MINOR-3**(테스트 fake 시그니처를 실제 `*, timeout=None` keyword-only 정합). MAJOR-1(신규 테스트 agent 이미지 밖 미실행)은 `make test`(agent 이미지) green 으로 충족. **확장 방향**(REPORT/REVIEW): 제품 수십~수백 시 background 사전계산 worker(TASK-0250 conn_health 패턴) + **Redis 등 외부 캐시서버** 완료율 스냅샷(현 인메모리 `_insight_cov_cache` TTL 은 프로세스 로컬 — 다중 인스턴스 미공유). **검증**: 신규 `test_datasource_test_nonblocking.py`(3: to_thread passthrough/errno 비유출/**동시 probe 비블로킹** 0.3s×5 직렬 1.5s→병렬 ~0.3s) + `test_insight_coverage_endpoint.py`(5: 단건 대상만/**무관 제품 미계산**/전체 무회귀/403/400) **8 PASS** + make test 컨테이너 **전체 회귀 0** + ruff clean + node --check + py_compile. worktree `ai/claude/head-of-line-fix`(base 3a97b86=main 12f5c5e). **잔여**: 배포(`deploy_scope: included` — web 만 재빌드, ask/insight-worker 코드 무변경) + PB-0008 Windows 시각검증(A ↻ 빠른 settle / B 제품별 개별 갱신).

### TASK-0251 공유 페이지 SQL "쿼리 열고닫기" 토글 → "실행 쿼리 전환" navigator 교정 + 백엔드 steps 공급 + 익명 sanitize (2026-06-12)
- [x] **Major §12.3 — 익명 공유뷰 데이터 노출 경계** — 사용자 보고: `/share/{token}` 에 "쿼리 열기"(열고닫기) 버튼이 의도와 다름; 실제로는 "결과셋에 따라 실행된 쿼리 전환" 구조를 원함. **진단(라이브)**: ① share.js `collapseSqlCodeBlocks` 가 본문 ```sql``` 블록을 "쿼리 보기/닫기" 토글로 감쌈(사용자 토큰 id=554 가 정확히 이 케이스 — meta={run_id,duration_ms}+본문 sql 블록). ② 메인 UI 의 `meta.steps` navigator 데이터를 **share API 가 전혀 공급 안 함**(저장 meta_json 에 steps 0건 — steps 는 일반 로드 경로가 agent_runtime.steps 에서 동적 조립). **수정**: (share.js) 토글 제거→본문 SQL 항상 펼침 + `renderAssistantDetails` 가 meta.steps 를 메인 UI 와 동일 렌더(1개=panel, 2+=`buildSqlNavigator` ◀▶ 전환); helper 이식(buildSqlStepPanel/buildSqlNavigator/buildPreviewTable/formatSqlForDisplay/extractFirstTableRef). (share.css) toggle css 제거 + navigator 스타일. (app.py 핵심) `_share_load_messages` 가 assistant 메시지에 `_load_steps_for_message` 로 steps 동적 조립 → navigator 라이브 동작. (app.py 보안) `_share_sanitize_step` 화이트리스트 — 익명 노출이므로 csv_paths(서버경로)/preview(전문)/args/error 제거, attachment_derived 는 steps 자체 제거. **outside-voice 적대적 보안 리뷰 NOT-SHIP→흡수→PASS**(REV-20260612-0251): BLOCKER(steps 경유 raw payload 익명 누출)→sanitize 흡수, MINOR(sentinel)→오탐 기각. **검증**: 신규/보강 4 테스트 + make test 컨테이너 **599 PASS(회귀 0)** + ruff + node --check + CSS brace + py_compile. **Playwright 실 헤드리스 2종(mock + 라이브 sanitized id=128 8 steps) ALL PASS**(navigator·"쿼리 N/M" 전환·토글 부재·본문 SQL 펼침·step 경유 /shared 누출 0·콘솔 0). 캐시버스터 `?v=20260612-share-sql-nav`. RBAC/스키마/암호화/신규 엔드포인트 0. worktree `ai/claude/share-query-navigator`(base f2a390b). 최신 TASK-0250 다음 번호(동시세션 0248·0249 점유 회피). **잔여**: 머지 → web 재배포(`deploy_scope: included`) → 사용자 공유 토큰 PB-0008 Windows 시각검증.

#### 완료 판정 기준
- [x] AC1: 공유 페이지에 "쿼리 보기/닫기" 열고닫기 토글이 더 이상 없다(본문 SQL 항상 펼침).
- [x] AC2: 한 답변에 execute_sql 단계가 2개+면 ◀▶ navigator 로 결과셋(실행 쿼리)을 전환한다(라이브 데이터로 동작).
- [x] AC3: 익명 공유 API 응답에 step 경유 csv_paths(서버 경로)·preview(결과 전문)·args·error 가 노출되지 않는다(라이브 검증).
- [x] AC4: steps 없는 구형 메시지는 기존 final_sql/result_rows 폴백 유지.
- [x] AC5: web 재배포(PR #202 머지 main `9cee54a` → `build web` + `up -d --no-deps web`) + PB-0008 Windows 시각검증 PASS(사용자 토큰 토글 0·본문 SQL 펼침 / steps 토큰 navigator "쿼리 1/8"↔"8/8" ▶◀ 전환). TEST.md §4 / 후속 doc TASK-0252.

### TASK-0248 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환 (2026-06-12)
- [x] **Major §12.3** (파괴적 삭제 + 접근 차단 + cross-store) — 사용자 요청: "관리 콘솔 > 제품에서 각 제품을 삭제할 때, 참조되는 대화가 있더라도 삭제가 가능하도록. 기존의 대화는 막힌 상태(더 이상 대화를 진행할 수 없도록) 전환." + 명확화: "대화 공유는 가능하지만, 대화 자체는 차단으로 진행." → 차단된 대화도 **공유(읽기전용)·이력 열람은 가능, 새 메시지 진행만 불가**. 설계 승인(AskUserQuestion): **영속 플래그 방식**(파생 추론 X). **구현**: ① (스키마, feature-0002) `agent_runtime.core_conversations` 에 `blocked_at timestamptz`/`blocked_reason varchar(256)` 추가 — alembic `0005_core_conv_blocked`(down_revision=0004_rag_objects_datasource, ADD COLUMN IF NOT EXISTS) 정본 + 부트스트랩 SQL 멱등 ALTER + app.py MySQL `_ensure` 폴백 parity. ② (백엔드, app.py) 신규 `_BLOCKED_PRODUCT_DELETED_REASON` + `_conversation_block_info(cid)`(차단 상태 조회, 조회실패 fail-open) + `_block_conversations_for_product(pid, reason)`(`UPDATE ... SET blocked_at=now() WHERE product_id=%s AND blocked_at IS NULL`, backend-aware, 재차단 방지). `admin_delete_product`: in_use>0 거부(400) 제거 → 미차단 참조 COUNT 산출 → 기존 cascade 삭제 commit → **commit 후** 차단 호출(cross-store 라 "삭제 먼저, 차단 나중") → 응답 `{ok, product_id, blocked_conversations}` + audit `referencing_conversations`. `/api/ask` 기존대화 분기: 소유권 체크 직후 `_conversation_block_info` → blocked 면 403(slot 획득 前). `_list_conversations_pg`/MySQL parity 에 blocked/blocked_at/blocked_reason 노출. ③ (프런트) `canAskInConversation`(blocked→false), `sendPrompt` 차단 가드, `renderComposer`(입력창 disabled + 전송버튼 aria-disabled + "차단된 대화" 안내), `renderConversationHeader`(🚫 차단됨), 대화목록 행(`.is-blocked` + "차단" 배지), admin 삭제 confirm/토스트(차단 건수). 캐시버스터 `?v=20260612-task0248-blocked-conv`. **설계 보존**: fork 는 차단 전파 안 함(접근불가 제품을 auto 강등 → "원본 차단·사본 새 일반대화" 정합); share-create 는 차단 대화도 허용(읽기전용). **검증**: 신규 `test_product_delete_block_conv.py` **7 PASS** + make test 컨테이너 **전체 회귀 0**(600 passed/2 skip) + node --check + py_compile + CSS brace 1108=1108. **outside-voice 적대적 2-agent 리뷰(REV-20260612-0248) SHIP-WITH-FIXES→흡수→SHIP**: 백엔드 BLOCKER 0(③ cross-store fail-closed 백스톱 실재 확인 — 제품 cascade 삭제가 `_account_has_product_access` False 유도 → ask 403), probe ⑥(PG 컬럼 부재 시 list/COUNT 500)은 **migrate-first 배포 계약으로 흡수**(코드 무변경, E 단계 `make migrate` 선행 + F 단계 컬럼 실측 게이트); 프런트 SHIP(우회 경로 0, 공유/이력/fork 충족), M-2(admin.js 혼입 의혹)=stale base 오탐(rebase 로 해소). **동시세션 충돌**: conn-health-monitor(TASK-0250, PR #196 f2a390b)·coverage-multi-ds(0249) 동시 active. 머지 직전 origin/main 재확인 후 **f2a390b 위로 rebase**(admin.html 캐시버스터 충돌 1건 해결, app.py/admin.js conn-health+TASK-0248 자동 병합 양립 재검증). 0248 번호 유지(origin max=0247). worktree `ai/claude/task0248-product-delete-blocked-conv`(base ff59f8f→f2a390b 재적용). **잔여**: 배포(make migrate 先 → web 재빌드) + 라이브 검증 + PB-0008 Windows 시각검증.

### TASK-0250 연결 health 모니터 — 관리 콘솔 연결상태 사전계산 표시 (2026-06-12, web 측; 코어=feature-0002)
- [x] **Major §12.3** — 관리 콘솔 datasource 연결상태를 백그라운드 모니터가 사전계산한 값으로 즉시 표시(per-item lazy `/test` probe + 4-cap 세마포어 자동경로 폐기 → 한 연결 불안정이 정상 연결 배지를 뒤에서 대기시키던 head-of-line 제거). `app.py` startup/shutdown 훅으로 web 프로세스 conn_health 모니터 기동 + `admin_list_datasources` 가 `conn_status`(좌표 비노출) 첨부. admin.js 가 캐시 hit 즉시 표시·unknown/force 만 lazy 폴백. 캐시버스터 `?v=20260612-conn-health-status`. **검증**: node --check + make test 컨테이너 회귀 0. outside-voice 2-pass(코어 feature-0002 REV-20260612-0250) SHIP-WITH-FIXES. worktree `ai/claude/conn-health-monitor`. 동시세션 0248·0249 선점→재번호 0250. **잔여**: 배포 + PB-0008 admin 연결상태 시각검증.

### TASK-0249 제품 insight 완료율 멀티 datasource(1:N) + 대소문자 매칭 수정 (2026-06-12)
- [x] **배포·라이브·PB-0008 완료 (2026-06-12)** — main `12f5c5e`(PR #198) → web 재배포(healthz `git_commit=12f5c5e`, mysql/pg ok, 베이킹 `seen_dbs`·`LOWER(TABLE_SCHEMA)` 확인). 라이브: 제품94 0/0 → **571/571(100%)** 7 DB 전부 conn(연결 안정 시), 제품1 = 100% 무회귀. **PB-0008 Windows Chrome/148 시각검증 PASS**: 요약 "insight 분석 완료율 100% · 571/571 객체" + datasource accordion 펼쳐 dbgame(player) 99/99·dbcommon(common, 타 서버) 111/111·dbauth(auth, 타 서버) 10/10 각 마이크로바 100%·DB✓ 실증(수정 전 단일 primary 질의로 0/0이던 케이스). 시나리오 `tests/win-browser-task0249-coverage.scenario.json`, 스크린샷 `/tmp/win-browser-shots/task0249/{10,11,12}*.png`. **별개 선존 이슈(flag)**: 페이지 첫 진입 시 프런트 일괄 coverage 로드 초기 렌더 타이밍으로 좌측 목록·요약 일시 "측정 중…" → 새로고침/재렌더 시 정상(state·loading 정상). 백엔드(본 TASK) 무관 프런트 `loadProductInsightCoverage` 초기 렌더 경로.
- [x] **Minor §12.3** — 사용자 보고: `관리 콘솔 > 제품 > 킹스레이드(KR_QA, id 94) > 데이터 소스 & 접근 가능 데이터베이스` 에서 DB객체 분석은 진행되는데 **테이블 분석 현황이 0/0**. **근본 원인 2(복합)**: KR_QA 는 7개 접근 DB 가 각각 **다른 datasource(다른 서버)** 에 바인딩(dbauth→auth·dbcommon→common·dbgame→player·dblog→log·dbranking→globalrank·dbgms→gms·dbmail→mail)된 진성 1:N. **Bug A(멀티 datasource 미지원)**: `_compute_product_insight_coverage` 가 `_resolve_product_insight_scope` 로 제품 primary datasource(auth) 하나만 해석해 7 DB 전부를 그 단일 서버에 질의 → 타 서버 DB 0 테이블(db-insights 는 datasource별이라 정상 → "DB객체는 분석 진행"으로 보임). **Bug B(대소문자 민감)**: Linux MySQL `@@lower_case_table_names=0` → DB명 대소문자 구분, 등록 `dbcommon`↔실제 `dbCommon` → `TABLE_SCHEMA IN ('dbcommon')` 0행. 두 결함 모두 있어야 정확히 0/0. **수정**: ① (db.py, agent-core) `list_information_schema_tables` MySQL 분기 `WHERE TABLE_SCHEMA IN(...)` → **`WHERE LOWER(TABLE_SCHEMA) IN(...)`** + 파라미터 소문자화(반환은 실제 케이스 유지). ② (app.py, web-ui) `_compute_product_insight_coverage` 전면 리팩터 — 접근 DB rows 를 effective `datasource_key`(row.datasource_key or product.primary) 별 그룹핑 → 그룹마다 scope 해석·SSRF·자기 좌표 라이브 카탈로그 질의·그룹 scope rag_objects 분자 조회 → 원래 노출 순서 합산(per_db 1:1). PG 연결 그룹 간 1회 재사용 + finally close. `measurable=connected_count>0`(한 datasource 실패→그 DB만 부분측정 note, 전부 실패→측정 불가 badge). `_resolve_product_insight_scope`(reset/db-insights 공유) 의도적 무변경, 응답 키 계약 불변. **검증**: 신규 `test_insight_coverage.py` 5(C1 멀티 per-DB 집계·C2 단일 레거시 무회귀·C3 mixed-case·C4 부분측정·C5 measurable=False) + make test 컨테이너 **전체 599 passed/2 skipped 회귀 0** + ruff clean + py_compile. 라이브 시뮬레이션: 제품94 ≈ 42.6%(243/571), 제품1 = 100%(무회귀). REV-20260612-0249. worktree `ai/claude/task0249-coverage-multi-ds`(base ff59f8f). **잔여**: 머지 → web 재배포(`deploy_scope: included`) → 라이브 검증 → PB-0008 Windows 시각검증.

### TASK-0243 TASK-0242 후속 — MSSQL db-insights catalog 귀속 수정 (2026-06-12)
- [x] **Minor §12.3** — 사용자 지적("mssql 에 대한 항목도 검증") + 키 수정 side-effect 면밀 검증 요청. **진단**: TASK-0242 의 `_compute_product_db_insights` 가 by_db 를 `rag_objects.schema_name` 으로 묶었는데 **MSSQL 은 schema_name=SQL스키마(`dbo`)** 라 등록 DB(catalog, GameLog_100 등)와 차원이 달라, MSSQL 통찰이 `dbo`/`dev50` 한두 바구니로 뭉쳐 프런트 `insByDb[등록DB명]` 조회가 전부 빗나가 **MSSQL 등록 DB 행 전부 "역할 미파악"**(라이브 제품91 by_db=['dbo','dev50'] vs 등록=GameLog_100/dk_data_release/… 무교집합). MySQL 은 db==schema 라 우연히 정상. **수정**: 신규 `_db_catalog_from_object_key(object_key, engine, object_type)` — `rag_objects.object_key`(`{scope}:{path}`)에서 catalog 파싱(MySQL=첫 segment; MSSQL schema=`catalog.dbo`(2)·table=`catalog.dbo.tbl`(3)→첫 segment, bare default_db→None skip). 그룹핑 키 schema_name→catalog. SELECT 에 object_key 추가, 그 외 무수정. **side-effect 격리 검증(사용자 요청)**: `_db_catalog_from_object_key`/`_compute_product_db_insights` 각 호출처 **1곳뿐**, app.py 의 다른 object_key 사용처는 MinIO 첨부 ObjectKey·coverage/reset(주석+코드상 schema_name/table_name 컬럼 전용, object_key 미사용)으로 **무관**; insight-worker write 경로(feature-0002) 무수정; MySQL catalog==schema_name 이라 by_db 키 byte-identical. **검증**: db_insights 17 PASS(파서 2 + MSSQL 귀속 1 신규) + make test 컨테이너 **전체 회귀 0**(coverage/reset 등 전 스위트) + ruff clean + py_compile + 적대적 subagent 리뷰. REV-20260612-0243. worktree `ai/claude/task0243-mssql-db-insights-catalog`(base f624367). **배포·라이브·PB-0008 완료**: main ed09a53(PR #184) → 라이브 제품1(MySQL) by_db 키 20개 배포 전후 **diff 0**(무회귀), 제품91(MSSQL) by_db=catalog 5키 등록 DB 매칭 + **PB-0008 MSSQL(DK온라인) 시각검증 PASS**(등록 DB 5행 전부 역할 한 줄 인라인 37/37·123/123·1/1·7/7 + picker 3-state 실증 분석중/분석됨; scenario win-browser-task0243-mssql-db-insights). **전 항목 완료**.

### TASK-0242 관리 콘솔 제품 데이터소스 — DB별 insight-worker 파악 내용 표면화 + 추가 picker 분석상태 (2026-06-12)
- [x] **Major §12.3** — 사용자 요청: `관리 콘솔 > 제품 > [각 항목] > 데이터소스 & 접근 가능 데이터베이스` 에서 각 DB 항목에 insight-worker 가 파악한 내용을 같이 출력(역할 명시) + `+ 데이터베이스 추가` 목록에도 파악 내용/분석 상태 표시. **배경**: 각 DB 행은 완료율 마이크로바(TASK-0223/0229)만 보이고 insight-worker 가 파악한 *역할/도메인*(`texts.text_content`)은 UI 부재. **사용자 확정(AskUserQuestion + 후속 메시지)**: 등록 DB 행은 **펼침 없이 한 줄 인라인**(DB명·insight 설명·분석률·객체 N/N·동일), picker 는 **도메인 힌트 + 분석상태 3-state(미분석/분석중/분석됨)**. **구현**: ① (백엔드) 신규 read 엔드포인트 `GET /api/admin/products/{id}/db-insights?datasource=<key>`(console.access, 바인딩 datasource 검증 400/미존재 404) + `_compute_product_db_insights`(coverage 와 동일 `_resolve_product_insight_scope` scope 로 `rag_objects ⋈ texts` DB별 묶음: domain/description/detail_text/analyzed_objects) + `_clean_insight_segment`/`_compose_db_insight_text`(한 줄 설명 합성) + `_insight_worker_liveness`(heartbeat KV 로 '분석중' 판정). ② (프런트) `loadProductDbInsights` 지연로드 + `buildDbRoleCell`(행 한 줄 설명·전문 hover) + `buildPickerInsightMeta`(도메인 힌트+상태칩). `.cov-db-row` 그리드 6→7컬럼. ③ (CSS) `.cov-db-role*`/`.admin-db-picker-status`(분석중 pulse·prefers-reduced-motion 존중). **비변경**: RBAC(console.access 재사용)·스키마·암호화·기존 엔드포인트·coverage 계산·insight-worker 런타임 0. **검증**: 신규 14 테스트 PASS + make test 컨테이너 회귀 0 + ruff clean + node --check + CSS brace balance(1090/1090) + py_compile. REV-20260612-0242. worktree `ai/claude/task0242-db-insight-surface`(base 4319220=main). **배포·라이브검증·PB-0008 완료**: main f815335(PR #182) web 재배포(healthz git_commit·mysql/pg ok·insight_age 7s) + 라이브 API 실측(제품1/8 MySQL account_db 13객체, 제품91 MSSQL dbo 373객체) + **PB-0008 Windows Chrome/148 시각검증 PASS**(dbauth/dbgame/dblog 3행 한 줄 인라인 설명 9/9·98/98·279/279 + picker 13항목 도메인힌트·분석됨; scenario win-browser-task0242-db-insights). **전 항목 완료**.

### TASK-0240 datasource picker 클리핑 수정 + 데이터소스 추가 체크박스 토글 통일 (2026-06-12)
- [x] **Minor §12.3** — 사용자 보고 2건(연속). **① `+ 데이터베이스 추가` 리스트가 패널 내부로 잘림**: Playwright clip 조상 재현으로 3중 클립 확정 — `.ds-acc-body{overflow:hidden}`(내가 TASK-0239 펼침 애니메이션 때 도입, 가장 가까운 조상, 드롭다운 top=492 인데 504 에서 잘라 220px 중 12px만 노출) + `.admin-detail-col{overflow-y:auto}`(패널 스크롤 컨테이너, 제거 불가) + `.admin-workspace{overflow:hidden}`. `position:absolute` 드롭다운인 한 스크롤 컨테이너가 계속 자름. **수정**: `.admin-db-picker-list` 를 absolute 플로팅 → **inline 정상 흐름**(margin-top + width:100% + 자체 max-height:220px·overflow-y:auto)으로 전환 → 어떤 overflow 조상도 자르지 못함(이 박스 자신만 스크롤). `.ds-acc-body` 의 overflow:hidden 도 제거(금지 주석). **② `+ 데이터소스 추가` 를 체크박스 토글로**(사용자: "`+ 데이터베이스 추가` 리스트와 같이 체크박스 토글 형식으로"): 기존 `<select>` 단일선택 → DB picker 와 동일한 inline 체크박스 토글 드롭다운(`.ds-acc-add-btn` + `.admin-db-picker-list`). 체크=`stageAddDatasource`(추가 스테이징), 해제=`stageRemoveDatasource`(제거 스테이징), 바인딩된(desired) datasource 는 체크 상태로 표시 → 한 목록에서 여러 개를 켜고 끄며 토글. 즉시 API 아니라 desired 스테이징 유지(TASK-0239) → "모두 적용" 일괄. **검증(Playwright 실 헤드리스, 라이브 admin pid=92)**: clip 조상 재현(3중) → 4-test(DB picker 무클리핑·hitInside / ds picker 체크박스 3항목 무클리핑·바인딩된 것 체크됨 / 체크 토글 시 pending+1·행 2개·**서버 1개 불변** / ⋯ 메뉴 정상) + 토글 양방향(체크 +1 → 같은 항목 해제 시 desired==baseline 복귀 pending 0·행 1개) PASS, 콘솔/pageerror 0. make test(컨테이너 pytest+ruff) 회귀 0. **frontend only**(admin.js·styles.css·admin.html 캐시버스터 `?v=20260612-ds-picker-inline`) — 백엔드/스키마/RBAC/엔드포인트 0. REV-20260612-0240 [SKIPPED:frontend-no-backend-no-rbac]. worktree `ai/claude-corp/feature-0003-agent-web-ui`(base 02f7c76). **잔여**: web 재배포 + PB-0008 Windows 시각검증.

### TASK-0241 요청 취소 즉시 처리 + 취소 직후 채팅창 재사용/재요청 (2026-06-12)
- [x] **Major §12.3** (cross-cutting feature-0002+0003). 사용자 보고: "중단을 눌러도 응답이 끝날 때까지 기다린다 — 취소 직후 채팅창 사용·재요청 가능하게, 부작용 모두 고려." **진단**: 백엔드 취소 로직은 정상, 진짜 결함은 프런트 `sendPrompt` 가 `/api/ask` long-poll 을 `await` 하고 busy 해제를 `finally` 에서만 함 → worker mode 동기응답 계약상 run 종료까지 입력창 잠김. **수정**: ① 프런트(app.js) optimistic 취소(busy/입력창 즉시 해제 + in-flight fetch abort[`askAbortControllers`] + pending 말풍선/폴링 정리 + `/api/cancel` 백그라운드 + `userCanceledKeys` 로 catch 사용자취소 식별·에러토스트 억제 + early-cid 키 이중성[`cancelKeys`/`askKey`/발사전 재확인]). ② 백엔드(app.py) `/api/cancel` pending/running 즉시 KV canceled(only_if_current_run) + attach 루프 `is_disconnected`+job-aware 종료(웹 슬롯 누수 차단) + **enqueue 선기록 sentinel run_id**(orphan clobber 차단). ③ agent_core.py+memory.py `set_run_status(only_if_current_run=True)` supersede 가드(취소 orphan 이 새 run 상태 클로버 방지) — terminal write 3곳. **3중 정합**: sentinel(enqueue)+only_if_current_run(terminal/cancel)+무조건 takeover(claim). orphan 은 현 LLM step 종료 후 답변 기록 없이 종료(동기 LLM 인터럽트 불가). **검증**: 신규 `test_set_run_status_supersede.py` 5건 + 전체 pytest 회귀0(F/E 0, 2 skip) + ruff clean + node --check + py_compile. REV-20260612-0241 [SUBAGENT:concurrency-adversarial] 2-pass(1차 BLOCKER 2·HIGH 2·MEDIUM 2 흡수 → 2차 SHIP). worktree `ai/claude/task0241-cancel-immediate`(base 9fbb185). **잔여**: 머지 → web+ask-worker 재배포 → PB-0008 Windows-browser 시각검증. **follow-up(별 cycle, LOW)**: never-claimed pending job TTL reaper 부재(본 변경 이전 class, 악화 아님).

### TASK-0239 datasource accordion 후속 버그/UX 3건 (⋯ 메뉴 클릭불가 + 추가 즉시반영 + 클릭 깜빡임) (2026-06-12)
- [x] **Minor §12.3** — TASK-0238 재설계 직후 사용자 실사용 보고 3건. **① ⋯ 행 메뉴 클릭 불가(기능 버그)**: Playwright hit-test 로 재현 — `.ds-acc-menu-btn` 클릭 시 JS 토글은 정상(`display:flex`)이나 `.ds-acc-row{overflow:hidden}`(TASK-0238 도입) 이 행 경계 밖으로 드롭되는 `position:absolute` 메뉴를 **클리핑**해 메뉴 픽셀이 안 보이고 `elementFromPoint` 가 메뉴 항목 대신 뒤의 `.cov-db-editor` 를 맞힘. → row 의 overflow 제거(주석으로 금지 명시) + 둥근 모서리는 `.ds-acc-head` 에 직접 부여(`:only-child`/`.is-active` 분기). **② datasource 추가/제거/기본지정이 "모두 적용" 일괄 흐름 밖**(사용자: "aws 일괄 적용 형식에 포함 안 됨 — 추가 시 즉시 반영"): 콘솔의 다른 모든 편집(제품 DB·정보·프롬프트)은 `pending` 스테이징 후 "모두 적용" 인데 바인딩만 즉시 API 라 anomaly. → 신규 `pending.productDatasources`(productId → {baseline, desired}) desired-state 스테이징. 추가=`stageAddDatasource`, 제거=`stageRemoveDatasource`(primary 제거 시 첫째 승격), 기본지정=`stageSetPrimaryDatasource`. accordion 은 `effectiveProductDatasources`(desired 우선)로 렌더해 즉시 시각 반영하되 **저장은 일괄**. `applyAllPending` 에 diff-apply 추가(제거→추가[0개→PATCH, 이후 POST]→primary 재지정 순), 제거된 datasource 의 접근DB draft 는 PUT skip(서버가 바인딩과 함께 삭제 — 고아 차단). dirty 카운트/취소/GC/재진입 펼침 대상 모두 desired 반영. 사용자 선택: **추가/제거/기본지정 전부 일괄**(AskUserQuestion). **③ 행 클릭 깜빡임**: 전환(`_switchEditDs`)이 전체 `renderProductDetail()` + 비동기 DB 재조회(칩 비웠다 채움)로 flash. → 전환·바인딩변경을 accordion **로컬** 재렌더로 한정 + `redrawChips()` 동기 선호출(구 내용 잔상 제거) + `.ds-acc-body` 펼침 애니메이션(`@keyframes`, `prefers-reduced-motion:reduce` 존중). **검증(Playwright 실 헤드리스, 라이브 admin pid=92)**: 4-test(⋯ 클릭→"연결 테스트" hit / 추가 시 pending+1·행 2개·**서버 1개 불변** / 전환 직후 동기 시점 DB리스트 렌더(무 flash) / "모두 적용" 후 서버 2개·pending 0) + 별도 제거 일괄적용(스테이징 시 서버 불변→적용 후 제거) 모두 PASS, 콘솔/pageerror 0. make test(컨테이너 pytest+ruff) 회귀 0. **frontend only**(admin.js +281/styles.css +28/admin.html 캐시버스터 `?v=20260612-ds-bulk-apply`) — 백엔드/스키마/RBAC/엔드포인트 0(기존 datasource/datasources/test/databases 재사용). REV-20260612-0239 [SKIPPED:frontend-no-backend-no-rbac]. worktree `ai/claude-corp/feature-0003-agent-web-ui`(base 5e6f167). **잔여**: web 재배포 + PB-0008 Windows 시각검증(펼침 애니메이션·메뉴 위치).

### TASK-0238 datasource 패널 통합 재설계 (중복 분류 제거 + 통일감, gstack /design-review) (2026-06-12)
- [x] **Minor §12.3** — 사용자 보고: "디자인적으로 중복되는 분류가 많고 통일감이 없다". 멀티 datasource(TASK-0228~0236)를 여러 동시세션이 증분 수정해 누적된 시각 부채. **gstack `/design-review` + codex outside-voice 소스 감사**로 진단: ① datasource 정보가 **3곳 중복**(데이터 소스 섹션 칩 + "편집 대상 데이터소스" select + "접근 가능 데이터베이스" 헤더 배지), ② **3가지 모양 혼재**(파란 pill 칩 / 점선 pill 시스템칩 / 둥근 사각 DB행), ③ 칩 액션 아이콘 불일치(★/⟳/× 칩마다 다름), ④ DB행 텍스트버튼(초기화)+아이콘(×) 혼재, ⑤ 헤더 배지가 제목에 공백없이 붙음 + 대소문자 불일치, ⑥ 하드코딩 rgba 토큰 미사용. **재설계(전체)**: 두 섹션("데이터 소스" + "접근 가능 데이터베이스")을 **단일 섹션 "데이터 소스 & 접근 가능 데이터베이스"** 로 통합. datasource = **펼침 accordion 행**(= 선택기 = 상태표시 = 바인딩 관리, 3중 중복→1곳). 행 = `▸/▾ 이름 · 엔진 · 기본배지 · ⋯메뉴`. 펼친 행 아래로 그 datasource 의 DB 편집기(시스템칩+DB리스트+추가 picker) 인라인. 행별 **⋯ 메뉴로 액션 통일**(연결 테스트/기본 지정/바인딩 제거 — 흩어진 ★/⟳/× + 공용 연결테스트 버튼 + 별도 select 전부 흡수). 디자인 토큰(`--primary`/`--r-md`/`--border`/`color-mix`) 일관 적용, 단일 시각 패턴(둥근 행). **편집 로직(draft/_refreshAccessibleDbs/redrawChips/buildPicker/_switchEditDs) 보존** — 표현 계층만 교체(회귀 최소화). **검증(Playwright 실 헤드리스 브라우저, 라이브 admin)**: 단일(pid=92)·멀티(추가 후 2행)·MSSQL 캡처 + 펼침/접힘/전환(active 이동·DB목록 datasource 반영)/추가 동작 PASS, 콘솔 에러 0 + make test 컨테이너 회귀 0. admin.js(datasource 영역 재작성) + styles.css(`.ds-acc*` 토큰 기반, `.admin-db-ds-badge` 제거) + admin.html(캐시버스터 `?v=20260612-ds-accordion`). 권한/스키마/엔드포인트/백엔드 0. REV-20260612-0238 [SKIPPED:frontend-redesign-no-backend-no-rbac]. worktree `ai/claude/ds-panel-redesign`(base 8be6487). **잔여**: web 재배포 + PB-0008 Windows 시각검증.

### TASK-0235 새 대화 첫 메시지 — 작업 단계 진행상황 실시간 표시 (2026-06-12)
- [x] **PB-0008 Windows-browser 시각검증 완료 (2026-06-12, 후속 cycle)** — 라이브 배포(web 재빌드 + healthz 200 mysql_ok/pg_ok) 후 실제 Windows Chrome/148 로 새 대화 첫 요청 시나리오 PASS(23/23). pending bubble 이 "시작 중…"→"SQL 실행 · INFORMATION_SCHEMA.TABLES…" 실시간 전환 + "단계 보기" 클릭 → `#stepSidePanel` 사이드바 열림(1단계 배지+SQL/근거/결과 상세) 확인. 사이드바에 "새 대화" optimistic entry 즉시 등재 = early-cid+polling 작동 입증. TEST.md §4 2026-06-12 Run PASS + 시나리오 `tests/win-browser-task0235-newconv-progress.scenario.json` + 스크린샷 6장(`/tmp/win-browser-shots/task0235/`).
- [x] **Major §12.3** — (동시세션 insight-reset·prompt-autogen·ds-a11y·ds-label cycle 이 TASK-0231/0232/0233/0234 선점 → §13.1 재번호 0232→0235) 사용자 보고: "새 대화를 생성 후 assistant 에게 첫 요청을 보냈을 때 작업 단계 진행상황이 안 나타나고 '시작 중' 출력만 확인됨. 각 단계와 클릭 시 사이드바로 상세 확인 가능하게 구성." **진단**: step 표시(`renderPendingAssistantBubble`)·"N단계 보기"→사이드바(`openStepSidePanel`/`#stepSidePanel`) UI 는 TASK-0061 에서 **이미 구현**됨 — 진짜 결함은 **데이터 공급 비대칭**. 기존 대화는 send 직전 `startProgressPolling()` 시작(app.js:5476)하지만, 새 대화(lazy_create)는 `conversation_id` 가 `/api/ask` 응답 전까지 없어 폴링을 못 켜고(`renderProgress` 만), `/api/ask` 가 **블로킹 완료된 뒤에야** 폴링 시작 → run 이 끝난 시점이라 처리 내내 "시작 중…" 만 노출.
- **수정(frontend-only, app.js+index.html)**: lazy_create 시 staged 첨부 전용이던 early-cid 발급 분기(TASK-0106, 첨부 있을 때만 `/api/new_conversation` 선호출)를 **첨부 유무와 무관하게 일반화**. cid 확정 직후 ① `state.activeConversationId` 전환 + optimistic conversation entry 선등재 + ② `startProgressPolling({reset:true})` 즉시 시작 → 새 대화 첫 메시지에서도 step 이 실시간 누적되어 pending bubble 한줄 단계 표시 + "N단계 보기" 버튼/사이드바 활성화. 후처리 블록은 `state.pendingSentinel === busyKey` 가드가 early 전환으로 false 가 되어 중복 폴링/전환 없음(기존 non-lazy lifecycle 로 수렴).
- **고아 대화 방지(적대적 리뷰 CONCERN #3)**: `earlyCidActivated` 플래그 도입 — early-cid 활성 후 `/api/ask` 실패 시 lazy 오류 경로 대신 non-lazy 복구 경로(`fetchAskStatus`→`is_processing` 시 대기/취소/즉시답변)로 분기. worker 모드 살아있는 run 회수 + 발급된 빈 대화가 실 run 컨테이너가 되어 고아 누적 0.
- **graceful fallback**: early-cid 발급 실패(네트워크 등) 시 기존 `lazy_create=true` 단일 호출 경로 유지(TASK-0048 정신) — step 실시간 표시만 누락되고 send 동작 자체는 무영향. staged 첨부 동반 실패만 toast 안내.
- **race 안전**: 새 conv 생성 직후 첫 poll 이 `/api/ask` 의 `set_run_status("processing")` 선기록(worker enqueue: app.py:8346 / inproc: agent_core:2472) 전에 도달하면 `status=""` 반환 → 프런트 `pollProgress` 는 빈 status 를 중단 조건으로 보지 않아(`payload.status && !=="processing"` 만 stop) 다음 tick 에서 processing+step 포착. 배포 모드 worker 확인(`.env: AGENT_ASK_EXECUTION_MODE=worker`).
- **비변경**: 백엔드 app.py·스키마·RBAC·엔드포인트 0(병렬 worktree 가 app.py 점유 중 — 의도적 회피). 캐시버스터 `app.js?v=20260611-newconv-progress-steps`.
- **검증**: node --check app.js PASS + verify-completion PASS(9/9). 적대적 동시성 리뷰 REV-20260612-0235 [SUBAGENT] CONCERN→흡수. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증(새 대화 첫 요청 → 단계 실시간 표시 + 사이드바 열림). worktree `ai/claude/newconv-progress-steps`(base c77111d → origin/main rebase).

### TASK-0236 datasource UI 바인딩 변경 후 미갱신 근본수정 (Playwright 실브라우저 검증) (2026-06-12)
- [x] **Minor §12.3** — 사용자 보고 3건(TASK-0234 후속, "구현이 매우 미흡"): ① 드롭다운으로 datasource 추가 시 첫 항목으로 되돌아가 연결 테스트 무의미, ② 접근 가능 DB 목록에 datasource 단서 없음·갱신 안 됨, ③ "데이터베이스 선택"으로 추가해도 primary datasource 로 갱신 안 됨. **근본 원인(실제 헤드리스 브라우저 Playwright 로 재현)**: 제품 상세 datasource UI 가 전부 `renderProductDetail()` **단일 호출 시점의 클로저**(`_renderDsChips`/`_refreshAccessibleDbs`/`_editDsSelect`/`_editDsKey`)로 구성되는데, 바인딩 변경 후 `_reloadProductDatasources` 가 **칩만 부분 갱신**하고 "편집 대상 데이터소스" select·헤더 배지·접근DB 목록은 초기 클로저에 묶여 갱신 안 됨. 특히 바인딩 0↔1↔N 전환 시 select 가 생성/제거돼야 하는데 부분 갱신으론 불가. **추가 발견(잠복 버그)**: "편집 대상 select" 블록(`length>=2`)이 `_editDsKey` 를 **선언(let) 전에** 참조 → **≥2 바인딩 제품을 렌더하면 `ReferenceError: Cannot access '_editDsKey' before initialization` 로 productDetail 패널이 통째 blank**(TDZ). 단일 바인딩 초기 렌더에선 블록이 skip 돼 잠복. **수정(frontend-only, 2파일)**: ① `_reloadProductDatasources` + 첫-바인딩 PATCH 경로가 부분 갱신 대신 `adminState.products` 정본 동기화 후 **`renderProductDetail()` 전체 재렌더** — 칩·두 select·편집대상·배지·접근DB 목록이 fresh state 로 일관 재구축. ② `_editDsKey` 선언을 "편집 대상 select" 블록 **앞으로 이동**(TDZ 해소). admin.js + admin.html(캐시버스터 `?v=20260612-ds-detail-rerender`). styles.css 무변경. **검증(Playwright 실 헤드리스 브라우저, 라이브 admin 콘솔)**: 수정 전 add 후 패널 blank(badge=null/chips=[]/select 없음) 재현 → 수정 후 add→칩 추가·편집대상 select 가 모든 datasource 옵션 재구축·배지 표시 PASS, edit-target switch→배지·DB목록 전환 datasource 반영 PASS, 콘솔 에러 0. + make test 컨테이너 회귀 0. 권한/스키마/엔드포인트/백엔드 0. REV-20260612-0236 [SKIPPED:frontend-bugfix-no-backend-no-rbac]. worktree `ai/claude/ds-detail-rerender-fix`(base ab20289). **잔여**: 정식 web 재배포 + PB-0008 Windows 시각검증.

### TASK-0234 datasource UI 사용성 버그 2건 (연결 테스트 + DB↔datasource 소속) (2026-06-12)
- [x] **Minor §12.3** — 사용자 보고 2건(멀티 datasource 1:N 배포 후). **이슈① 연결 테스트 버튼 무동작**: 제품 상세 "데이터 소스" 섹션의 공용 "연결 테스트" 버튼이 `dsSelect.value` 를 읽는데, 제품에 바인딩이 ≥1 있으면 그 드롭다운은 **"데이터소스 추가" 모드(value='')** 로 바뀌어(TASK-0230) 항상 "테스트할 datasource 를 먼저 선택하세요" 만 떴다 — 즉 **바인딩된 datasource 를 테스트할 수단이 없었다**. (백엔드 `/api/admin/datasources/{key}/test` 는 정상 — 라이브 3/3 ok 확인.) **수정**: 각 datasource 칩에 **per-chip ⟳ 연결 테스트 버튼**(그 칩의 datasource_key 로 직접 호출, 성공 ✓/실패 ✗ + toast + 2초 후 복원). 공용 버튼은 "새로 추가할 datasource 선택 시 테스트" 용도로 명확화(빈 값+바인딩 존재 시 칩 ⟳ 안내). **이슈② 선택 DB↔datasource 소속 불명**: "접근 가능 데이터베이스" 목록이 어느 datasource 것인지 표시 없음(멀티 바인딩 시 모호). **수정**: 섹션 헤더에 **편집 대상 datasource 배지**(`.admin-db-ds-badge`) 추가 — 단일/미바인딩이면 "기본 단일 MySQL", 바인딩이면 datasource 라벨. "편집 대상 데이터소스" select 전환·바인딩 add/remove 시 배지 갱신(`_updateDbSectionLabel`). 제거된 datasource 를 편집 중이었으면 primary 로 자동 환원. **수정(frontend-only, 3파일)**: admin.js(per-chip ⟳ + 헤더 배지 + reload 동기화) / styles.css(`.admin-chip-action--ok/--fail`·`.admin-db-ds-badge`) / admin.html(캐시버스터 `?v=20260612-ds-test-label`). **검증**: node --check + CSS brace balance + make test 컨테이너 회귀 0 + 라이브 연결테스트 API 3/3 ok. 권한/스키마/엔드포인트/백엔드 0. REV-20260612-0234 [SKIPPED:frontend-bugfix-no-backend-no-rbac]. worktree `ai/claude/ds-test-and-label-fix`(base 62d7a06). **잔여**: web 재배포 + PB-0008 Windows 시각검증(칩 ⟳ 동작 + 헤더 배지 표시).

### TASK-0233 datasource multi-bind UI 접근성 보강 (gstack /design-review 감사) (2026-06-11)
- [x] **Minor §12.3** — TASK-0230 으로 추가한 제품 상세 datasource multi-bind UI 를 gstack `/design-review`(소스 디자인·접근성 outside-voice subagent)로 감사 → 발견 HIGH 3 + MEDIUM 4 흡수. **수정(frontend-only, 3파일)**: ① (H1) 아이콘 전용 ★(기본지정)/×(제거) 칩 버튼에 `aria-label` 부여(글리프만으론 SR 불투명). ② (H2) "편집 대상 데이터소스" select + datasource 추가/설정 select 양쪽에 `aria-label`(가시 라벨 미연결 combobox). ③ (H3) ★/× 클릭 핸들러에 `disabled` 가드 — 비동기 POST/DELETE 중 중복 요청 차단(in-flight 재진입 방지, 실패 시 재활성). ④ (M1) `.admin-chip-action`/`.admin-chip-remove` 를 `min 24×24px` inline-flex 로(WCAG 2.5.8, 이전 padding:0 2px≈12px). ⑤ (M2) `:focus-visible` outline 추가(borderless 버튼 키보드 포커스 불가시 해소). ⑥ (M3) ★ resting opacity 0.7→0.85(hover-only 가시성은 키보드/터치 미노출). ⑦ (M4) 빈 바인딩 상태를 수동적 status→행동유도 CTA. 캐시버스터 `?v=20260611-ds-multibind-a11y`. **검증**: node --check admin.js PASS + CSS brace balance(1035/1035) + make test 컨테이너 회귀 0(frontend-only). **라이브 기능 회귀 16/16 PASS**(별도 검증: auth/datasources/add/list/remove/연결테스트/차원격리/insight heartbeat — 프로덕션 상태 원복 확인). REV-20260611-0233 [SKIPPED:frontend-a11y-no-backend-no-rbac]. 권한/스키마/엔드포인트/백엔드 0. worktree `ai/claude/ds-multibind-a11y`(base 997d9ec=TASK-0230 머지본). **잔여**: web 재배포 + PB-0008 Windows 시각·키보드 검증. P2(coverage UI 와 remove 버튼 시각 통일)·P4(대화 드롭업 배지 tooltip 키보드 미접근)는 동시세션 머지 코드(sibling) 영역이라 flag-only.

### TASK-0231 insight 분석 초기화 (접근 가능 DB 단위 삭제) (2026-06-11)
- [x] **Critical §12.3** — (동시세션 SSRF·UI-통합 cycle 이 TASK-0228/0229 선점 → §13.1 재번호 0228→0230) 사용자 요청: `관리 콘솔 > 제품 > 접근 가능 데이터베이스 > insight 분석 완료율`에서 분석 내용을 초기화하는 수단. 잘못 분석된 내용을 되돌릴 방법이 없던 gap 해소. 사용자 결정: **개별 DB 단위** 초기화 + **삭제만**(worker 자동 재분석).
- **신규 RBAC `insight.reset`**(console 그룹, admin 한정 — audit.purge 동급 파괴적). `PERMISSION_DEFINITIONS` + admin seed catchup(operator/sales/pending 미부여).
- **공용 헬퍼 `_resolve_product_insight_scope`** — 완료율 계산(`_compute_product_insight_coverage`)과 초기화가 **동일 scope/allow_null/engine** 식별자를 쓰도록 datasource scope 해석 로직 분리 + scope alias 집합(hash/.env label/NULL) 반환(키 불일치로 인한 "지웠는데 완료율 그대로"/"엉뚱한 DB 삭제" 방지).
- **신규 엔드포인트 `POST /api/admin/products/{pid}/insight-reset`** (body `{db, dry_run}`):
  - 라이브 카탈로그 조회로 해당 DB 의 `(schema, table)` 쌍 + schema 집합 확보(reset 이 datasource RO 좌표 직결, SSRF 가드+pin).
  - **rag_objects 삭제 = 완료율 분자와 동일한 `(schema_name, table_name)` 교집합 + schema 노드**(M1 흡수) — object_key LIKE 방식이 MSSQL 2-tier 레거시(catalog-less)를 놓쳐 완료율 divergence 를 유발하던 것을 해소. 2-tier/3-tier object_key 형식 무관하게 완료율 0 보장.
  - fact_entries/rag_documents/kv 삭제 키 패턴(`_insight_reset_fact_key_patterns`/`_insight_reset_kv_key_patterns`/`_like_escape`): scope alias 전체(M2) + 라이브 schema(MSSQL 2-tier 레거시 catalog-less) 커버. LIKE ESCAPE '\\'(underscore DB명 오매칭 차단). **fingerprint(schema_fp/table_fp)+refresh_at 동반 삭제가 핵심** — 안 지우면 worker 가 "변경 없음" 오판해 재분석 skip.
  - `dry_run=true`: 건수만(삭제 0). `false`: **audit start-event 먼저 commit(실패 시 삭제 중단, M3 흡수)** → 단일 PG tx DELETE + rollback 안전망 → complete-event + 완료율 캐시 무효화.
  - 보안: `insight.reset` 권한 게이트(403), 요청 db 가 제품 WebProductDatabases 바인딩인지 검증(임의 DB 주입 400), db 누락 400, 카탈로그 조회 실패 시 502(대상 산정 불가 안전 중단).
- **프런트(admin.js/html/css)**: TASK-0229 통합 DB 리스트(`redrawChips` 의 `cov-db-row` grid) 위로 rebase — per-DB 행에 "초기화" 버튼(`insight.reset` 권한자만) → `resetProductDbInsight`(dry-run 미리보기 → DB명 typed-confirm + 공유 제품 영향 경고 → 실제 삭제 → 완료율 새로고침). 위험색 버튼 CSS + grid 6컬럼. 캐시버스터 `?v=20260611-db-coverage-insight-reset`.

#### 완료 판정 기준
- AC1: insight.reset 권한자가 per-DB "초기화" 버튼으로 해당 DB insight(fact/rag/fingerprint)를 삭제 → 완료율 0% 반영(MSSQL 2-tier 레거시 포함).
- AC2: 삭제 후 insight-worker 가 다음 cycle 에 fingerprint 부재 감지해 자동 재분석.
- AC3: 권한 미보유 403, 제품 비바인딩 DB 주입 400(임의 삭제 차단), underscore DB명 오매칭/cross-scope 과삭제 0, 카탈로그 조회 실패 502.
- AC4: 삭제 전 audit start-event 선행(fail-safe). dry-run + typed-confirm. make test 회귀 0 + 신규 테스트 PASS + py_compile + node --check + ruff. 라이브 dry-run/실삭제 검증 + PB-0008 시각검증.

#### 작업 항목
- [x] RBAC insight.reset 정의 + admin seed catchup
- [x] _resolve_product_insight_scope 헬퍼 추출 (완료율 ↔ reset 정합 + scope alias)
- [x] insight-reset 엔드포인트 (라이브 카탈로그 (schema,table) 교집합 + audit fail-safe + 단일 tx + 캐시 무효화)
- [x] 프런트 per-DB 초기화 버튼 (TASK-0229 통합 리스트 위로 rebase) + dry-run + typed-confirm + 캐시버스터
- [x] pytest 신규 14건 PASS + make test 505 passed/2 skipped(회귀 0) + ruff clean + py_compile + node --check
- [x] outside-voice 적대적 보안 리뷰 — MAJOR 3(M1 MSSQL rag_objects/M2 scope alias/M3 audit fail-safe) 흡수
- [ ] verify-completion → 머지 → web 재배포 → 라이브 dry-run/실삭제 검증 + PB-0008 시각검증

### TASK-0230 멀티 datasource 1:N — 제품 ↔ 여러 datasource 참조 (2026-06-11)
- [x] **Critical §12.3** — (동시세션 TASK-0228 SSRF·0229 db-coverage 선점→0230 재번호) 사용자 요청: "assistant 가 답변하려면 여러 데이터소스·DB 에 접근해야 하나 단일 datasource 만 가능 → `관리 콘솔 > 제품 > [각 항목] > 데이터소스` 에서 여러 데이터소스도 참조하도록". 기존 멀티 datasource(TASK-0185~0226)는 product↔datasource **1:1**(`WebProducts.DatasourceKey` 단일 컬럼). **사용자 추가 요청**: 제품 프롬프트 자동작성이 접근 가능 모든 datasource 의 DB 를 인지. **사용자 결정(AskUserQuestion 2회)**: 범위=**전체 구현**, 런타임 노출=**LLM 이 tool 인자로 datasource 선택**. **구현(feature-0003 측, 6파일)**: ① `_ensure_web_product_datasources_schema` — `WebProductDatasources(ProductId, DatasourceKey, IsPrimary, SortOrder)` join 테이블 멱등 신설 + 레거시 `DatasourceKey`→join(primary) 이전 + `WebProductDatabases.DatasourceKey` 차원 컬럼 추가 + 레거시 행 backfill + PK `(ProductId,SchemaName)`→`(ProductId,DatasourceKey,SchemaName)` 멱등 이전(REV-0230 MAJOR-1: 컬럼 선확인 + 단계별 loud 로깅). ② admin 엔드포인트 `GET/POST/DELETE /api/admin/products/{id}/datasources`(console.access[+manage], 미등록 키 거부, audit, primary 동기화) + 기존 PATCH 는 primary 설정 wrapper 로 join 동기화. `GET /api/admin/datasources`·`_list_products` 응답에 `datasources[]` 추가. ③ `PUT /api/admin/products/{id}/databases` 가 `datasource_key` 차원 수용(그 datasource 행만 교체, 바인딩 검증) + DELETE datasource 가 join·접근DB 고아 정리. ④ 제품 프롬프트 자동작성(`admin_generate_product_prompt`)이 모든 바인딩 datasource 의 ds-키 집합으로 fact 매칭 + datasource 별 접근DB 그룹 표시(`WebDataSources` 오타도 정정). ⑤ admin.js — 제품 상세에 datasource 칩 multi-bind(추가/제거/기본지정) + 접근DB 편집의 "편집 대상 데이터소스" 선택기(차원별 draft·pending) + 대화화면(app.js) 다중 datasource 배지. styles.css `.admin-chip--primary`/`.admin-chip-action`. 캐시버스터 `?v=20260611-product-multi-ds`. **검증**: 신규 `test_product_multi_datasource_api.py` 7 + node --check(admin.js/app.js) + make test 컨테이너 회귀 0. **outside-voice 적대적 보안 리뷰 BLOCKER 0**(REV-20260611-0230, agent-core REVIEW 정본 — 격리 HOLD + MAJOR-1/2/3 흡수). flag `AGENT_MULTI_DATASOURCE_ENABLED` OFF + 단일 바인딩 = 동작 0 변경. cross-feature(agent-core 런타임 라우터 + 본 feature 관리/UI). worktree `ai/claude/product-multi-datasource`(base e93b181, main 머지 후 origin/main rebase·동시세션 0228/0229 충돌 해소). **잔여**: 라이브 배포(web+insight-worker+ask-worker 재빌드) + 멀티 바인딩 제품 PB-0008 Windows 시각검증.

### TASK-0229 관리 콘솔 제품 상세 "접근 가능 데이터베이스" UI 통합 (gstack 디자인 리뷰) (2026-06-11)
- [x] **Minor §12.3** — (동시세션 SSRF cycle 이 TASK-0228 선점 → §13.1 재번호 0228→0229) 사용자 보고 2 IA 문제: (1) 제품 상세 `접근 가능 데이터베이스` 섹션에서 위쪽 "insight 분석 완료율" per-DB breakdown 리스트와 아래쪽 사용자 등록 DB chip 목록이 **같은 DB 집합을 1:1 중복 표시** → 분리 의미 없으니 하나로 통합. (2) 시스템/메타데이터 DB(MySQL 4종/MSSQL 3종)가 각각 별도 locked chip 으로 나열돼 산만 → 단일 묶음 칩 + mouse hover 시 상세 출력. **gstack `/design-review` 메서드론**(general-purpose design subagent)으로 통합 IA 스펙 도출 → "분석 대상(사용자 DB)=단일 리스트 행(진척+제거), 비-분석 대상(시스템 DB)=접근성 묶음 칩". **데이터 정합 검증**: 백엔드 `_compute_product_insight_coverage` 의 `accessible=_list_product_databases(conn,pid)` → `per_db` 집합 = 사용자 등록 DB(draft chip)와 동일, 시스템 DB(metadata_schemas)는 per_db 미포함 → `per_db.db ↔ draft.schema_name`(소문자) 조인 자연 정합. **수정(admin.js+styles.css+admin.html, 3파일)**: ① `buildProductCoverageDetail` → 요약 헤더(제목+전체% 배지+새로고침)+전체 진행 바로 축소(per-DB breakdown 제거→각 행 흡수). ② `buildDbCoverageCells(covRow,measuring)` 신설(마이크로바+통계 m/n+상태칩: DB✓/연결불가/측정대기/대상없음). ③ `buildSystemDbChip(lockedChips)` 신설(`시스템 DB N개·고정` + title/aria-label/tabindex=0 + hover·focus·focus-within 커스텀 툴팁 = 키보드·터치 접근성 병행). ④ `redrawChips` 재작성(시스템 묶음 칩 상단 + 사용자 DB 통합 리스트 `cov-db-row` grid 5컬럼 + 빈 상태). ⑤ 컨테이너 `admin-chip-wrap`→`cov-db-wrap`(flex column). **CSS**: `.cov-db-wrap`/`.cov-db-row`(grid)/`.cov-microbar(-fill)`/`.cov-db-status*`/`.cov-db-remove`/`.sysdb-chip(-tip*)` — 기존 디자인 토큰만(신규 hex 0), 8px 그리드·11~13px 위계. 캐시버스터 `?v=20260611-db-coverage-unified`. **권한/스키마/암호화/엔드포인트/백엔드(app.py)/coverage 응답 shape 0** — frontend-only IA 재구성. **검증**: node --check admin.js PASS + CSS brace balance(1031/1031) + verify-completion PASS. REV-20260611-0229 [SKIPPED:frontend-ia-merge-no-backend]. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증. worktree `ai/claude/product-db-coverage-merge`(base e93b181).

### TASK-0223 제품 프롬프트 자동작성 실데이터 정합 + MSSQL database-aware 3계층 인사이트 (2026-06-11)
- [x] **Major §12.3** — 사용자 지적: 자동 생성 프롬프트가 실제 데이터와 불일치(LLM 이 `play_log`·`user_status` 등 없는 테이블 날조). **근본원인 2** — ① `fact_entries.source_type` 이 전부 `schema_insight` 로 들어가 신뢰 불가(실제 종류는 `fact_key` 접두로 판별), ② `scope_key` 가 전부 `common` 이라 기존 `scope_key ILIKE '%dbgame%'` 매칭 0건 → 인사이트 통째 누락. **+ MSSQL 미지원** — MSSQL 은 database.schema.table 3계층인데 insight-worker 가 `dbo` 단일 DB 만 스캔 + fact_key 에 database 누락 → 제품 등록 DB(`dk_data_release` 등)와 매칭 불가. **구현(7파일, 2 feature 교차)**: ① `app.py` 엔드포인트 재작성 — fact_key 접두로 종류 구분 + `regexp_replace` 로 ds 접두 정규화 후 제품 접근 스키마/DB명으로 **정확 매칭**(substring ILIKE 아님), schema/table 인사이트를 스키마별 구조화, LLM 지시문에 "제공된 실제 인사이트만 사용·테이블/컬럼 날조 금지" 명시, 응답 meta(schema_insight_count/table_insight_count/topic_count/grounded). MSSQL 3계층 렌더 분기(segment 개수). datasource 교차노출 차단(제품 DatasourceKey→scope_key 필터). ② `config.py` — `_ACTIVE_DATABASE` ContextVar + `set_active_database`/`get_active_database` + `ds_object_suffix`(MySQL 2계층/MSSQL 3계층 suffix; `ds_fact_key` 시그니처 불변=3자 정합 보존). ③ `insight.py` — MSSQL multi-database 스캔(`_discover_mssql_databases` 제품 등록 DB 기반, DB별 재연결+`set_active_database`, 권한밖 DB 연결실패 격리) + suffix 조립부 전수 `ds_object_suffix` 치환(table_insight/schema_insight/table_fp/schema_fp/*_refresh_at) + read-back 맵을 `object_key` 키로(cross-DB livelock 방지). ④ `utils.py` `_infer_rag_object_from_fact` — 3계층(database.schema.table) 파싱 + object_key 에 database 접두(유일성). ⑤ `schema.py` bootstrap 2곳 `ds_object_suffix` 치환(누락분). ⑥ `agent_core.py` `_insight_object_group` — grounding(_load_schema_list) grouping 을 MySQL=schema/MSSQL=database.schema 로 정합(table_insight↔schema_insight desc 매칭). ⑦ `admin.js` meta 충실도 표시. **사용자 추가요청 검증**: ask-worker(`_build_knowledge_context`→`_load_schema_list`/`_load_relevant_table_insights`→PG `fact_entries`)가 시스템 프롬프트 `KNOWN SCHEMAS`/`RELEVANT TABLES` 섹션에 insight 주입 → LLM 이 신뢰해 execute_sql 직행 확인(ask_jobs done + 실 컬럼 답변). **적대적 리뷰 4결함 수정**(REV-20260611-0223): MSSQL DB명 대소문자 불일치(렌더 lookup 소문자 통일), read-back 맵 cross-DB 충돌 livelock(object_key 키), bootstrap 2계층 누락(schema.py), 엔드포인트 ds 필터 부재(교차노출). **+ `_log` F821 hotfix**(TASK-0216 머지본 잠복 — `_log.getLogger`→`logging.getLogger(__name__)`). **검증**: pytest 444 passed/2 skipped(신규 `test_mssql_three_tier_insight.py` 13, 회귀 0) + py_compile + 라이브 end-to-end(MySQL 킹스레이드 138 테이블 grounded·MSSQL 제품 60 테이블 grounded·교차노출 0·ask-worker grounding 정상). worktree `ai/claude/feature-0003-agent-web-ui`(base c769612). 배포: web+insight-worker+ask-worker 재빌드/재시작 완료. **잔재**: 구형식 2계층 fact_key(키 마이그레이션 진행 중 — 궁극 완료 시 정리, 엔드포인트는 키 무관 동작). **이월**: MSSQL RO GRANT 확대 시 추가 DB(GameLog_*) 자동 인사이트(현재 권한밖 격리).

### TASK-0218 관리 콘솔 대시보드 CloudWatch 스타일 사람-친화 재구성 (2026-06-11)
- [x] **Major §12.3** — 사용자 요청: TASK-0210 으로 데이터·확장성은 확보됐으나 "실제 사람이 편하고 접근성 있게" 쓰는 구조 부족 → AWS CloudWatch 류 친숙한 운영 대시보드로 재구성(gstack 디자인 스킬 참조). **gstack `/design-review` 메서드론 + cross-model(Codex + Claude subagent) 디자인 감사**(REV-20260611-0218, APP UI 분류) 강한 합의 반영. **구현**: ① **위계** — 9개 동일 비중 → 주 metric 크게(primary 플래그) + 보조 작게, 카탈로그 활동-우선(대화·LLM사용량·감사 상단). ② **시간/신선도** — `days` 윈도우를 audits/conversations/accounts 에도 전파(거짓 컨트롤 정직화) + 수동 새로고침 + auto-refresh(off/30/60s) + "마지막 갱신 HH:MM:SS". ③ **추세** — 시계열 위젯에 전기간 대비 ▲▼% 델타 배지(의미별 색: 비용↑=적색, 활동=중립) + 순수 SVG sparkline(외부 lib 0, admin.js 기존 SVG 패턴). ④ **fail-loud** — overview/위젯 실패를 빈 화면이 아닌 오류 배너 + 재시도. ⑤ **drill-down** — 위젯 헤더 "열기 →" 가 해당 관리 탭으로(switchTab). ⑥ **편집** — native HTML5 drag reorder + ↑↓ 키보드 폴백 + 표시 토글. ⑦ **접근성** — 포커스 링(:focus-visible), aria-live(위젯 영역·마지막갱신), aria-label(이동/표시/열기), aria-pressed. ⑧ **polish** — Top-N 인라인 비율막대, widget radius --r-md, 8px 그리드, 소형 라벨 대비(--text-2). **백엔드**: `_dash_widget_*` window/primary/delta/spark/tab + helper `_dash_pct_delta`/`_dash_fill_daily`. **권한 카탈로그/스키마/시크릿/신규 엔드포인트 0** — overview/preferences 응답 shape 확장(추가 필드) + 비파괴 read(시계열). **검증**: make test MAKE_EXIT=0(신규 6 → `test_dashboard_overview.py` 17, 회귀 0) + node --check + py_compile + 내 코드 ruff 클린. 캐시버스터 `?v=20260611-dashboard-cloudwatch`. worktree `ai/claude/dashboard-cloudwatch-ux`(base 1c98a16). 배포 + PB-0008 시각검증. **이월**: drill row-level 필터·"위젯 추가 라이브러리"(편집모드가 숨김 위젯 노출로 add 충족). **flag(내 코드 아님)**: app.py:14133 `_log` F821(TASK-0216 머지본 잠복 버그).

### TASK-0216 제품 프롬프트 자동 작성 품질 강화 (2026-06-11)
- [x] **Minor §12.3** — 사용자 요청: 제품 시스템 프롬프트 자동 작성 기능의 품질 최대화 — insight-worker 및 사용자 대화 내역에서 확인된 교훈을 LLM 컨텍스트로 추가. **구현**: ① `agent_runtime.core_conversations.topic` 집계(최신 50개) — 이 제품의 사용자 대화 주제 패턴 수집. ② `public.fact_entries` source_type 확장(`schema_insight`/`table_insight`에서 `search_pref`/`insight` 추가) — 검색 선호도 및 인사이트 워커 팩트 포함. ③ `agent_runtime.summary` 샘플(최신 5개) — 실제 사용 사례 요약 포함. **엔드포인트**: `POST /api/admin/products/{product_id}/prompt/generate` 신규 추가(app.py). **프런트**: `buildSystemPromptEditor`에 `autoGenerateProductId` 파라미터 + "자동 작성" 버튼 추가(admin.js), `renderProductDetail`에서 `autoGenerateProductId: Number(product.id)` 전달, 불필요 hint 문자열 제거. **권한**: `product.manage` 기존 권한 재사용(신규 RBAC 0). **LLM**: `_resolve_session_default_model()` + `_get_openai_client(model=...)` + `max_tokens_for_model`/`model_supports_temperature` 적용. **검증**: py_compile PASS + curl 실제 호출 LLM 생성 성공(킹스레이드 제품 503자 시스템 프롬프트 정상 생성). worktree `ai/claude/admin-prompt-enrich`(base main). 배포: web 재빌드 + up -d 완료.

### TASK-0210 관리 콘솔 대시보드 보강 — 카테고리별 위젯 그리드 + per-account 커스터마이즈/영속 (2026-06-11)
- [x] **Major §12.3** — 사용자 요청: `관리 콘솔` 대시보드("운영 현황")가 빈약(계정 metric 6개 + 권한 drift + pending 만, 전부 클라이언트 `adminState.accounts` 배열 필터 계산)하니 **각 카테고리별로 풍부하게 + 사용자별로 확장성 있게** 보충. AskUserQuestion 으로 "사용자별로 확장성 있게" 를 **종합(3축: RBAC 뷰어 스코프 + 계정별 분해 + 서버 집계) + 각 사용자별 커스텀 구성/수정 가능 + 영속성 유지** 로 확정. **구현**: ① (신규 테이블) `WebDashboardPreferences(AccountId PK, Content JSON-text MEDIUMTEXT, ...)` — `_ensure_web_tables()` 멱등 부트스트랩(MySQL, 웹테이블군 정합, alembic 무). per-account 위젯 표시/순서 영속. ② (신규 엔드포인트) `GET /api/admin/overview` — **RBAC-스코프 카테고리 집계**. 위젯 카탈로그(`_DASHBOARD_WIDGETS`) 각 항목이 표시 권한을 가지며, overview 는 actor 가 그 권한을 보유한 위젯의 데이터만 만들어 반환 → **권한 경계 = 데이터 노출 경계**(usage 권한 없는 operator 는 응답에 토큰/비용 자체가 없음). 위젯: accounts(활성/비활성/삭제/최근로그인/역할분포)·roles(역할수/역할별 권한수)·products(활성/바인딩)·datasources(엔진분포)·conversations(전체/24h/7d/소유자, PG core_conversations)·audits(24h/7d/액션·actor Top-N, `audit.read.any`)·usage(토큰/요청/비용/모델별, PG llm_usage, `console.usage.read`). 각 위젯 독립 try/except 격리(부분 실패가 전체 안 깨뜨림). ③ (신규 엔드포인트) `GET/PUT /api/admin/dashboard/preferences` — 본인 계정(actor.id) 한정 self-service(신규 RBAC 권한 0, `console.access` 게이트). PUT 은 `_sanitize_dashboard_prefs` 로 알려진 위젯 키·bool·int 만 정규화(미지 키/중복/과대 입력 거부). ④ (프런트) admin.js `renderDashboard` 재작성 → 서버 overview+prefs fetch 후 **위젯 그리드** 렌더 + **편집 모드**(위젯 표시/숨김 토글 + ↑↓ 순서 이동, 외부 DnD 라이브러리 없이 — baked-assets 정책) + 저장(PUT 영속)/기본값 복원. 기존 grant_health(별도 엔드포인트)·pending(클라 상태)은 client 위젯으로 흡수. admin.html 위젯 그리드 마크업 + 집계기간 select + 편집 toolbar. styles.css `.dashboard-widgets/.dashboard-widget/.dashboard-metric/...`(기존 토큰 재사용). 캐시버스터 `?v=20260611-dashboard-widgets`. **권한 카탈로그/스키마(웹 외)/시크릿 변경 0** — 기존 권한 재사용 + prefs 는 self-service. **SQL 인젝션 차단**: usage `days` 는 `max(1,min(365,int()))` clamp 후 interval 삽입(사용자 문자열 미흐름). **검증**: make test(컨테이너 pytest+ruff) **MAKE_EXIT=0 전체 PASS**(신규 `test_dashboard_overview.py` 11 PASS: overview RBAC 스코프 operator/admin·403·sanitize·기본값·영속 round-trip, 회귀 0) + node --check admin.js PASS + py_compile PASS. REV-20260611-0210(outside-voice 적대적 보안리뷰 — 위젯 권한 경계/IDOR/인젝션). worktree `ai/claude/admin-dashboard-enrich`(base f2054b5). 배포: web 재빌드 + up -d, PB-0008 Windows 시각검증.

### TASK-0198 LLM 사용량 — 모델별 분리/선택 차트 + 모델별 요약 카드 + 좌우 스크롤 제거 (2026-06-10)
- [x] **Minor §12.3** — 사용자 요청: `관리 콘솔 > 감사 > LLM 사용량` 상단 대시보드가 종합(aggregate)만 보이고 모델별 분리/선택이 불가 + 화면 좌우 스크롤 불편. **A 모델 필터·분리(프런트 전용)**: 상단에 모델 칩 바(`#usageModelFilter` — 전체/모델별 토글, 다중 선택)를 추가하고 선택 모델 기준으로 요약·일별 stacked·도넛·역할별·계정별 차트와 상세 표를 모두 좁힌다. 백엔드 `/api/admin/usage` 는 이미 `by_model`/`by_day_model`/역할·계정 `models[]` 를 내려주므로 **백엔드/API/스키마/RBAC/시크릿 무변경** — `loadUsage` 가 응답을 캐시(`_lastRaw`, days|gran 키)하고 `buildView(data, selectedModels)` 로 클라이언트 재계산(요약 totals=by_model 합, 역할·계정=선택 모델 기여분 재합산). 칩 토글은 재조회 없이 캐시 재렌더(`loadUsage({refetch:false})`). 모델 키는 전 차트 공통인 `COALESCE(resolved_model, model)`. 부분 선택 시 역할·계정 표의 요청(distinct run_id)·호출은 모델 횡단이라 분해 불가 → `—` 표시(토큰·비용은 정확 재계산). **B 모델별 요약 카드**: 종합 합계 카드(선택 스코프 라벨) + 모델별 분리 카드(모델당 토큰/요청/호출/추정 비용, 칩 색 accent, 클릭 시 그 모델 단독 선택 토글). **C 좌우 스크롤 제거**: usage pane `overflow-x:hidden`, flex 카드 `min-width:min(Npx,100%)`(420/300/240), 넓은 상세 표는 카드 내부 `overflow-x:auto` 로 흡수. `color-mix`/`--accent` 미사용(프로젝트 토큰 `--primary`/`--primary-soft` 로 통일 — 구버전 브라우저 회귀 회피). 프런트 3파일(admin.js·admin.html 캐시버스터·styles.css) + 시나리오. node --check PASS. 캐시버스터 `?v=20260610-usage-model-filter2`. REV-20260610-0198. **Windows-browser(PB-0008) 검증 완료** (TEST.md §3 2026-06-10 TASK-0198 Run: 칩 6·모델카드 4·선택 필터·`userCanScrollHorizontally:false` 확정, scenario ok). worktree `ai/claude/0003`.

### TASK-0197 assistant 말풍선 타임스탬프 옆 소요시간 표시 (2026-06-10)
- [x] **Minor §12.3** — 사용자 요청: assistant 응답 완료 시 각 대화 bubble 의 타임스탬프 옆에 소요시간 표시. `message.meta.duration_ms`(agent_core 가 `_mirror_message` 에 mirror_meta 로 저장)가 있는 assistant 말풍선에 한해, 기존 `formatElapsed()` 재사용, `.message-meta-duration` span 추가. 백엔드/API/스키마/RBAC/시크릿 무변경 — 프런트 3파일(app.js·styles.css·index.html 캐시버스터) 만. node --check PASS. REV-20260610-0197 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]. worktree `ai/claude/response-duration-display`.

### TASK-0188 공유 대화 페이지 markdown 미적용 수정 + 수신자 가독성 디자인 (2026-06-10)
- [x] **Minor §12.3** — 사용자 보고: 공유 링크로 전달받은 대화가 markdown 미적용 raw 텍스트로 보임(수신자 입장 가독성 저하). **근본 원인**: `share.html` 이 marked+purify 미로드 + `share.js` 가 `content.textContent` 평문 렌더(메인 채팅은 `markdownToHtml()` marked+DOMPurify). **수정(3파일, 백엔드/API/스키마/RBAC/시크릿 무변경)**: ① `share.html` marked+purify 로드(순서 share.js 앞) + 캐시버스터 `?v=20260610-share-md` + 브랜드 라벨 + 링크복사 버튼. ② `share.js` `renderMarkdownContent`(marked.parse→DOMPurify.sanitize, 라이브러리 부재 평문 폴백) + sql 코드블록 "쿼리 보기" 토글 + 외부링크 `target=_blank rel=noopener` + 역할 배지 + 링크복사. ③ `share.css` 렌더 markdown 요소 스타일(제목·리스트·인용·코드·GFM 표·hr·img·링크) + 역할 배지·좌측 accent border + 반응형 + 인쇄/PDF 스타일시트. **보안**: 익명 페이지 XSS 는 메인과 동일 DOMPurify.sanitize 차단, 데이터 redaction 무변경. node --check PASS. REV-20260610-0188 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]. Windows-browser(PB-0008) 검증 배포 후. 동시세션 0182~0186 선점→0188. worktree `ai/claude/share-md-render`.

### TASK-0181 LLM 사용량 역할/계정 차트 모델별 stacked + 상세 표 요청(메시지) 수 (2026-06-10)
- [x] **Minor §12.3** — 사용자 요청. **A**: 역할별·계정별 [토큰|비용] 막대를 모델별 누적(stacked)으로 분해. 백엔드 by_account 에 `models:[{model,total_tokens,cost_usd}]` 보존 + `_aggregate_usage_by_role` 가 역할별 models 합산. 프론트 전역 `modelColor`(일별/도넛/stacked 색 일관) + `renderStackedHBar`. **B**: 요청 수=`count(distinct run_id)`(run=conversation 단위, NULL 제외) 를 totals/by_model/by_account/by_role 에 `requests` 추가. 요약 '요청' 카드 + 상세 표 '요청' 컬럼(호출=LLM 호출, 요청=사용자 메시지). 권한/스키마 신규 0. 캐시버스터 `?v=20260610-usage-stacked`. node --check/py_compile + make test 282 passed/5 skipped(회귀 0). REV-20260610-0181 [SKIPPED:read-agg]. 동시세션→0181. worktree `ai/claude/usage-model-stacked`.

### TASK-0180 LLM 사용량 차트 카테고리별 행 레이아웃 + 일별 폭 채움 + 상세 표 여백 (2026-06-10)
- [x] **Minor §12.3** — 사용자 피드백(몰아넣기 불쾌 + 상세 표 여백). 명시적 행 구조: ① 시간별 토큰(flex4):모델별 비중(flex1)=4:1, ② 역할별[토큰|비용], ③ 계정별[토큰|비용](`.admin-usage-row` 1:1, wrap). grid(charts/span2) 폐기. 일별 차트 SVG viewBox W=`el.clientWidth`(폴백 760)·H 200 고정 → 넓은 카드 가로 채움(막대 cap 64). 상세 표 카드화(`.admin-usage-table-card`, max-width:none width:100%) + 모델별 full·역할별|계정별 2열. 권한/스키마/백엔드 무변경. 캐시버스터 `?v=20260610-usage-rows`. node --check PASS. REV-20260610-0180 [SKIPPED:css-layout]. 동시세션→0180. worktree `ai/claude/usage-row-layout`.

### TASK-0179 LLM 사용량 차트 넓은 화면 가로 여백 해소 (CSS grid) (2026-06-10)
- [x] **Minor §12.3** — 사용자 보고(넓은 모니터 가로 여백 과다). 차트 6개를 `.admin-usage-charts` grid(`auto-fill minmax(400px,1fr)`)로 다열 배치 — 넓은 화면 채움·좁으면 wrap(860px↓ 1열). 일별=`.admin-usage-span2`(2칸)+SVG max-width 1000. 도넛/역할별/계정별/비용2 각 1칸. h3/h4 카드 내부로. 권한/스키마/백엔드 무변경(순수 레이아웃). 캐시버스터 `?v=20260610-usage-grid`. node --check PASS. REV-20260610-0179 [SKIPPED:css-layout]. 동시세션→0179. worktree `ai/claude/usage-grid-layout`.

### TASK-0178 LLM 사용량 화면 여백 컴팩트화 (CSS/SVG) (2026-06-10)
- [x] **Minor §12.3** — 사용자 보고(불필요한 여백 과다). TASK-0177 디자인 정렬에서 카드·섹션·차트 패딩이 누적된 것을 축소. styles.css: `.admin-usage-card` 16/18→12/14, `.admin-usage-section` mt 20→12, `.admin-usage-metric` 패딩 11/14·strong 19·span mb 4, usage `.summary-metrics` gap 10·mt 0, row gap 12. admin.js: 일별 차트 H 252→196(pT 10·pB 26), HBar margin 6. 권한/스키마/백엔드 무변경(순수 spacing). 캐시버스터 `?v=20260610-usage-compact`. node --check PASS. REV-20260610-0178 [SKIPPED:css-spacing]. 동시세션 다수→0178. worktree `ai/claude/usage-spacing-compact`.

### TASK-0177 LLM 사용량 상세 표 추정 비용 컬럼 + gstack 디자인 관점 정렬 (2026-06-10)
- [x] **Minor §12.3** — 사용자 요청(차트·상세 표 비용 일치 + gstack 디자인 리뷰 자율 적용). **A**: 역할별·계정별 상세 표에 추정 비용 컬럼 추가(by_role/by_account 의 cost_usd=TASK-0176, 백엔드 무변경) + tbl 헬퍼 `align:'right'` → 숫자 컬럼 우측정렬·tabular-nums. **B(디자인)**: general-purpose subagent 의 gstack `/design-review` 적대적 리뷰 수령 후 적용 — 요약 `.metric-card`/`.summary-metrics` 통일, 임의 hex→디자인 토큰(`--text*`/`--border*`), 차트 `.admin-usage-card` surface 구획, 8px spacing 클래스(`.admin-usage-section/h3/h4`), h2→h3→h4 위계, `.admin-usage-table`(hover·우측정렬·토큰 border), 툴팁 `.admin-usage-tooltip`(토큰화). 차트 팔레트는 유지. styles.css(admin-usage-* 신규) + admin.html(클래스化) + admin.js(요약/표/툴팁/SVG fill 토큰). 캐시버스터 `?v=20260610-usage-design`. 권한/엔드포인트/스키마/백엔드 신규 0. node --check PASS. REV-20260610-0177 [SKIPPED:frontend-design] + design subagent 리뷰 반영(High3+Med4+Low). Windows-browser(PB-0008) 검증 배포 후. worktree `ai/claude/usage-cost-tables-design`. 동시세션 다수→0177.

### TASK-0176 LLM 사용량 역할별·계정별 추정 비용 차트 (2026-06-09)
- [x] **Minor §12.3** — 사용자 요청. 토큰 가로 막대(역할별/계정별) 외에 **추정 비용** 가로 막대 추가. **백엔드**: `admin_llm_usage` by_account 를 `owner_account_id` 단일 GROUP BY → 계정 × `COALESCE(resolved_model,model)` 분해로 변경(비용은 모델별 단가라 모델 분해 필수) + Python 계정별 fold(`_estimate_llm_cost_usd` 모델별 합=`cost_usd`). `_aggregate_usage_by_role` 가 enrich 된 by_account 의 cost_usd 를 역할별 재합산 → `by_role[].cost_usd`. **프론트(의존성 0 SVG)**: `renderHBar(el, rows, valueFmt)` 에 valueFmt 인자 추가(usd) + 역할별/계정별 추정 비용 차트(`#usageRoleCostChart`/`#usageAccountCostChart`, 비용 0 행 제외, hover usd 툴팁). admin.html "추정 비용" 섹션(2열). 캐시버스터 `?v=20260609-usage-cost`. 권한/엔드포인트/스키마/시크릿 신규 0(기존 컬럼 read + TASK-0166 단가 상수 재사용). node --check/py_compile + make test 269 passed/5 skipped(회귀 0). REV-20260609-0176 [SKIPPED:frontend-viz]. 동시세션 0168~0175 선점→0176 재번호. worktree `ai/claude/usage-cost-by-role-account`.

### TASK-0167 관리 콘솔 작은 화면 세로 잘림 수정 (CSS) (2026-06-09)
- [x] **Minor §12.3** — 사용자 보고: 웹브라우저 화면이 작을 때 화면 전체가 안 나오고 잘림. **근본 원인**: `.admin-shell`·`.admin-workspace` 가 `height:100vh; overflow:hidden` 인데 `.admin-pane` 중 dashboard 만 `overflow-y:auto` 보유, usage pane 누락 → 차트(0165/0166)·표로 길어진 usage pane 이 작은 화면에서 세로 스크롤 불가로 하단 잘림(다른 pane 은 내부 `admin-list` 스크롤이라 무관). **수정**: `styles.css` dashboard overflow 규칙에 `[data-admin-pane="usage"].is-active` 셀렉터 추가(dashboard 와 동일 패턴) + admin.html styles.css 캐시버스터 `?v=20260609-usage-overflow`. 권한/엔드포인트/스키마/JS/HTML 구조 무변경 — CSS 셀렉터 1개. REV-20260609-0167 [SKIPPED:css-only]. worktree `ai/claude/usage-overflow-fix`(base main).

### TASK-0166 LLM 사용량 차트 고도화 — 계정별 차트·hover 툴팁·막대 값·시간단위·추가지표 (2026-06-09)
- [x] **Minor §12.3** — TASK-0165 후속(사용자 지적 누락 항목). **백엔드 `admin_llm_usage`**: ① `granularity`(hour/day/week/month) — `date_trunc` 단위 화이트리스트(`_USAGE_GRAN`)로만 삽입(인젝션 차단), bucket 포맷 + 막대 상한. by_day/by_day_model bucket 집계(서브쿼리로 동일 버킷 집합 보장). ② by_model/by_day prompt/completion 분해. ③ `_estimate_llm_cost_usd`+`_LLM_PRICE_USD_PER_1M`(claude 근사, 로컬=0) 모델별·총 추정 비용. 응답 `granularity`/`cost_usd` 추가. **프론트(의존성 0 SVG)**: ① 계정별 가로 막대(`#usageAccountChart`) 신규(역할별 대칭). ② 커스텀 hover 툴팁(`data-tip`+`bindTip`, `<title>` 대체) 전 차트 — 값/비중/호출/비용. ③ 막대 위 총합 값 라벨. ④ 집계단위 드롭다운(`#usageGranSel`) + 기간(1일/1년 추가). ⑤ 요약 추정비용 카드 + 모델별 표 prompt/completion·비용 컬럼. 권한/엔드포인트/스키마/시크릿 신규 0. 캐시버스터 `?v=20260609-usage-charts2`. node --check/py_compile + make test 218 passed/5 skipped(회귀 0). REV-20260609-0166 [SKIPPED:frontend-viz]. **한계**: 비용은 공시가 근사 추정(로컬=$0). Windows-browser(PB-0008) 검증 배포 후. worktree `ai/claude/usage-charts-v2`(base main).

### TASK-0165 LLM 사용량 화면 차트화 (상용 AI 사용량 대시보드 참조) (2026-06-09)
- [x] **Minor §12.3** — TASK-0163 후속(사용자 요청: "상용 ai 제공 서비스의 구조를 참조하여 차트 형식으로"). 표 위주 화면을 Anthropic Console / OpenAI Usage 류로 시각화. **백엔드**: `admin_llm_usage` 에 `by_day_model`(일별 × `COALESCE(resolved_model, model)` 토큰 합) 집계 추가 — 기존 컬럼만(비파괴 read, 스키마 0). **프론트(의존성 0 순수 SVG)**: admin.js ① `renderStacked`(일별 토큰 모델별 누적 세로 막대 + 날짜축 + 범례), ② `renderDonut`(모델별 비중 도넛 + % 범례, 실제 서빙 모델 라벨), ③ `renderHBar`(역할별 가로 막대). 색상 팔레트 `colorMapFor`(로컬/시스템=회색). admin.html usage pane 에 차트 컨테이너(#usageDayChart/#usageModelChart/#usageRoleChart) + 기존 표는 `<details>` 접이식 보존. CDN 미사용(정적자산 baked·WSL 내부 — Chart.js 등 외부 의존 회피). 캐시버스터 `?v=20260609-usage-charts`. 권한/엔드포인트/스키마/시크릿 신규 0. node --check/py_compile PASS. REV-20260609-0165 [SKIPPED:frontend-viz]. Windows-browser(PB-0008) 라이브 screenshot 검증 완료(배포 후). 동시 세션이 TASK-0164(SIGTERM)를 먼저 머지(a207bb4)해 번호 충돌 → 0164→0165 재부여 + main 위로 rebase. worktree `ai/claude/llm-usage-metering`(TASK-0163 연장).

### TASK-0164 이월 처리 — SIGTERM graceful finalizer + RBAC catalog prune + out-of-process 설계 (2026-06-09)

- [x] TASK-0169 (REQ-20260609-0168, **Critical §12.3** — out-of-process ask-worker 실행모델 / ADR-WEB-0004 B). TASK-0159/0160/0164 의 이월 B 구현. `/api/ask` 의 in-process(`asyncio.to_thread`) 실행을 전용 `ask-worker` 로 분리(ask_jobs 큐 claim·실행) → web 재배포/SIGTERM 이 in-flight run 을 죽이지 않음(orphan 구조 제거). **flag `AGENT_ASK_EXECUTION_MODE`(기본 inprocess) 라 본 배포 자체로는 동작 무변경(shadow)**, cutover 는 env 전환. **web 측(app.py)**: `_dispatch_ask_run`(inprocess|worker 분기) + readiness gate(503) + 단일문 slot enforce + 내부 attach loop + `result_json` 응답 shape 패리티 + backstop ownership-aware(B1, 0159/0164 가 worker run skip) + cancel-pending(2g) + 첨부 temp `/shared`(M6). **agent-core 측(feature-0002 CHG-0168)**: `ask_jobs` 마이그레이션·`ask_jobs.py`(atomic claim/lease fencing/sweep)·`ask.py`(worker loop·시간기반 heartbeat·reaper)·`--ask-worker`·healthcheck·config·`set_run_status` 순서(M4). docker-compose `ask-worker` 서비스(stop_grace 70s). **outside-voice 적대적 리뷰 2회(설계 전 + diff) — BLOCKER 3 + MAJOR 4 흡수, 구현 BL-1/MJ-1/MJ-2 추가 수정**(REV-20260609-0168). make test 244 pass(회귀 0)·신규 테스트 3파일·py_compile·ruff clean. PLAN-APPROVED(§2.1, 2026-06-09). worktree `ai/claude/ask-worker`(base 2ad6d03, 동시세션 0166/0167 점유로 0168 재배정). **이월(cutover 게이트)**: 마이그레이션 라이브 적용 → worker=on shadow → 점진 cutover, PB-0008 Windows-browser + 부하·web 재배포 중 run 생존 실측, on_event→lifespan 마이그레이션.
- [x] TASK-0164 (REQ-20260609-0164, **Major §12.3** — run 생명주기 + RBAC catalog delete). in-process(`asyncio.to_thread`) ask 실행이 web 재배포로 orphan("처리중" 고착)을 만드는 근본을 종료 시점에 차단(A) + cosmetic 정리 + 구조적 정답 설계(B, 이월). **A1**: `@app.on_event("shutdown")` finalizer 가 이 프로세스 in-flight run(`>= _PROCESS_BOOT_UTC`)을 error 로 마킹(부팅 reconciliation 의 대칭 역, race 가드 + 8s 소프트캡 + 단일 connect)(AC-0322). **A2**: `_prune_orphaned_permission_catalog` 가 완전 폐기 권한(suggestions.read·execute_sql_on.*)의 고아 WebPermissions 행을 0-참조 가드 하에 DELETE(AC-0323). **A3**: 빈 attachment 그룹 키 = LEAVE(forward-compat). **B**: `DESIGN-ask-worker.md`(ask-worker + ask_jobs 큐 + 롤아웃 플래그) 설계만, 구현 이월(AC-0324, ADR-WEB-0004). 신규 단위테스트 3(`test_shutdown_finalizer.py`) + 전체 pytest 통과(회귀 0) + py_compile. **outside-voice 적대적 리뷰 PASS-WITH-NITS, BLOCKER 0**(REV-20260609-0164, NIT 2건 흡수). 동시 세션 TASK-0162/0163 점유로 0164 재배정, base bf0a61f. **이월**: out-of-process 구현(B), set_run_status 4-conn(기존 helper), on_event→lifespan 마이그레이션.

### TASK-0163 LLM 사용량 admin 계정별/역할별 집계 + 모델 해소 표시 (2026-06-09, cross-feature — 주관 feature-0002)
- [x] **Major §12.3** — 관리 콘솔 > 감사 > LLM 사용량의 모델별/계정별/역할별 집계 복구. 본 feature 면은 **엔드포인트 + 프론트**: `admin_llm_usage`(GET /api/admin/usage) 가 by_model 을 `COALESCE(resolved_model, model)` 로 집계(요청 별칭+실제 모델 둘 다 노출), by_account 를 이미 열린 MySQL conn 으로 `WebAccounts LEFT JOIN WebRoles ON r.Id=a.RoleId` 로 username·role enrich(추가 conn 개방 0), 신규 순수 헬퍼 `_aggregate_usage_by_role`(account None→`(시스템)`, role None→`(역할 없음)`, total_tokens desc) Python 폴딩 후 응답에 `by_role` 추가. 프론트 `admin.html` 역할별 표(#usageByRole) + `admin.js loadUsage` 가 `tbl(rows,cols)` fmt 에 row 전달, by_role 렌더·계정 username·역할 컬럼·모델 `별칭 → 해소` 표시, 캐시버스터 `?v=20260609-usage-roles`. 권한 `console.usage.read`(admin) **무변경 — RBAC 카탈로그/엔드포인트 신규 0**. 계측·마이그레이션(`resolved_model` 컬럼)·RC1 race 수정은 feature-0002 주관([[feature-0002-agent-core/docs/TASK.md]] TASK-0163, REV-20260609-0163). 검증: make test 215 passed/5 skipped + node --check + outside-voice 적대적 diff 리뷰 PASS(BLOCKER 1 흡수).

### TASK-0162 진행중("작업 중") 말풍선 생명주기 수정 — 대화 전환 누출 + 새로고침 경과시간 초기화 (2026-06-08)

- [x] TASK-0162 (REQ-20260608-0162, **Minor §12.3** — frontend SPA + thin read-only backend 필드). 사용자 보고 2건: (A) 요청 처리 중 다른 대화로 전환하면 직전 작업의 "작업 중" 말풍선이 전환한 대화에 나타남. (B) 새로고침 시 말풍선 경과시간이 0 으로 초기화됨.
  - **근본 원인 A**: `selectConversation` 이 직전 대화의 `state.pendingBubble` 을 `_savedPendingBubbles` 에 스냅샷 저장만 하고 `state.pendingBubble` 을 비우지 않아, 전환 후 `loadHistory→renderMessages` 가 잔존 말풍선을 새 대화 하단에 렌더. (이미 `beginPendingConversation` 은 `stopProgressPolling({reset:true})` 로 분리하는데 `selectConversation` 만 누락.)
  - **근본 원인 B**: 새로고침 시 `loadHistory`(및 `initializeWorkspace` resume 경로)가 말풍선을 `startedAt: Date.now()` 로 재생성 → 실제 run 시작이 아니라 새로고침 시각 기준이라 elapsed 리셋. 서버는 KV `last_status_at`(processing 전이 시 1회만 기록 = run 시작 시각)을 갖고 있으나 `/api/history` 가 반환하지 않아 클라가 알 수 없었음.
  - **수정**: (1) `selectConversation` 스냅샷 저장 직후 `stopProgressPolling({reset:true})` 로 진행 상태(말풍선+polling+elapsed timer) 분리. (2) 백엔드 `/api/history` 가 processing 시 `last_run_started_at`(=KV `last_status_at`) 반환. (3) 프론트 `loadHistory` + `initializeWorkspace` resume 경로가 `Date.now()` 대신 서버 시각(`last_run_started_at` / `ask_status.status_at`)을 `startedAt` 기준점으로 사용(파싱 불가 시 `Date.now()` 폴백). (4) 인접 엣지(리뷰 Nit): loadHistory 가 비-processing 확정 시 `_savedPendingBubbles[cid]` 폐기 → 전환 후 완료된 대화로 복귀 시 stale 말풍선 부활 차단. (5) 정적자산 `?v=` 캐시버스터 task-0156→task-0162 bump(app.js·styles.css).
  - **tz 안전**: 클라 elapsed 는 `new Date("…+00:00").getTime()` 절대 epoch − `Date.now()` 절대 epoch 이라 브라우저 타임존 무관. TASK-0159 의 server-side PG `timestamptz` naive 변환 버그와 무관(이 경로는 `_parse_kv_timestamp` 미사용).
  - **검증**: node --check PASS / py_compile PASS. 적대적 subagent diff 리뷰 REV-20260608-0162 **APPROVE-WITH-NITS, BLOCKER 0** (Nit 2건 본 cycle 반영, Nit 3 실질 window 0 note-only). PB-0008 Windows-browser 라이브 게이트는 배포 후 수행.

### TASK-0161 RBAC 카탈로그 정리 + 죽은 코드 제거 (TASK-0158 Tier 3 종결) (2026-06-08)

- [x] TASK-0161 (REQ-20260608-0161, **Major §12.3** — RBAC 권한 모델 변경 + 죽은 코드). TASK-0158 Tier 3 결정 항목을 권장 방향대로 처리. (1) **거짓 컨트롤 권한 제거** `attachment.execute_sql_on.own/.any`(enforce 0, 관리 그리드 무동작 체크박스) — 정의·시드·catchup 제거 + `_cleanup_deprecated_role_permissions` removals 로 DB 행 멱등 정리 + app.js map 제거. 실제 게이트(allowlist+attachment_reader+sql_guard) 무변경, 런타임 동작 0(교차계정 이미 차단)(AC-0315). (2) **죽은 중복 제거** — `POST /api/list_conversations`(호출자 0, 내부 PG 메서드명과 무관) + `#composerAttachments`/`Pills` DOM·잔여참조·고아 `_toggleAttachmentPill` + `#tabCountAudits` stale 뱃지(AC-0316). (3) **`upload.any` 유지+문서화**(실제 enforce, 의도적 UI 미노출)(AC-0317). **outside-voice 적대적 RBAC 리뷰 PASS-WITH-NITS, BLOCKER 0**(REV-20260608-0161, NIT 2건 본 cycle 흡수). py_compile/node --check PASS. 동시 세션 TASK-0160(agent_core tool_use fix) 점유로 0160→0161 재배정, base a4a2d28 rebase. **이월(별 cycle)**: in-process(to_thread) 실행모델 구조적 재설계(TASK-0159 이월과 동일), attachment 빈 그룹 키 정리(무해).

### TASK-0159 고아 run 무한 폴링 수정 — PG timestamptz stale 회귀 + 부팅 reconciliation (2026-06-08)

- [x] TASK-0159 (REQ-20260608-0159, **Major §12.3** — 런타임 run 생명주기/데이터 경로). 사용자 보고: 웹 DBA 챗 요청이 "오랜 시간 안 끝남". 진단: `/api/ask` 는 agent 를 `asyncio.to_thread` 로 web 프로세스 안에서 in-process 실행 → web 재배포(14:37 컨테이너 재생성 — 병행 TASK-0158 세션의 배포로 추정)가 in-flight run(`f47482aa`)을 죽여 `set_run_status("done")` 미도달 → KV `last_status='processing'` 영구 고착 → 프런트엔드 `/api/ask_result`·`/api/progress` 무한 폴링(+ 신규 질의 409 차단), 최종 답변 미합성. **추가 결함**: 20분 stale 자동복구가 안 터짐 — `_last_step_at_for_run`(PG 경로)이 `timestamptz`(KST aware)를 UTC 변환 없이 `replace(tzinfo=None)` 해 KST wall-clock 을 UTC 로 오인 → `_compute_display_status` 의 `datetime.utcnow()` 비교에서 elapsed 음수 → stale 영구 거짓 (CHG-20260527-0001 cutover 회귀). **수정(app.py 단일 파일)**: (1) `_last_step_at_for_run` aware→`astimezone(timezone.utc).replace(tzinfo=None)` 변환(naive 통과), (2) `@app.on_event("startup")` `_reconcile_orphaned_runs_on_startup` — in-process 모델상 새 프로세스엔 살아있는 run 이 없으므로 부팅 전 시각의 `last_status='processing'` 고아를 `error` 로 일괄 정리(daemon thread + `last_status_at >= _PROCESS_BOOT_UTC` race 가드, boot 시각 초 절삭), (3) `set_run_status` import. **즉시 해소**: 라이브 PG KV 의 고아 run f47482aa 를 `error` 로 표시(스피너 해제 + 409 해제). **회귀 테스트**: `tests/test_orphan_run_stale_recovery.py` 6 case (tz 변환·stale 판정·boot-guard) PASS. **이월(후속 TASK)**: SIGTERM graceful finalizer + in-process→out-of-process 실행모델 재설계. 검증: py_compile PASS / pytest 6 passed / verify-completion PASS / REV-20260608-0159 APPROVE-WITH-NITS(BLOCKER 0). **병행 충돌 메모**: 본 cycle 중 다른 세션이 TASK-0158(진입점 Tier1·2, frontend-only)을 main 에 연속 병합 → 본 작업을 0159 로 재배정, app.py 무충돌(그쪽은 app.js/admin.js/index.html/styles.css)로 rebase.

### TASK-0158 "진입점 없는 기능" 전수조사 후 진입점 구성 (2026-06-08, 완료 — Tier1·2 + PB-0008 검증)

- [x] TASK-0158 (REQ-20260608-0158, **Minor §12.3** — frontend-only). 사용자 요청: TASK-0157 과 동일 클래스(구현 완료·진입점 부재) 기능 전수조사 후 순서대로 진입점 구성. design.md 9섹션 형식 적용(`docs/DESIGN-entry-points.md`). repo-level 전수조사 결과는 `TODOS.md` 에 기록.
  - **Tier 1 (완료)**: [x] 즉시답변 — `#finalizeBtn` 고아 제거 + composer `#composerFinalizeBtn` 신설(AC-0308). [x] 공유 링크 관리 — ··· 메뉴 "공유 관리" + `openShareManager` 모달(목록+취소, `GET shares`/`DELETE share`)(AC-0309). [x] scopeAll — attach 패널 `#composerAttachmentsScopeAll` 체크박스(핸들러·백엔드 기존, 마크업만 신설)(AC-0310). node --check PASS. REV-20260608-0158 [SKIPPED:frontend-only-no-new-rbac-no-schema-no-secret].
  - **Tier 2 (완료)**: [x] audit.purge 버튼(dry-run 미리보기+typed-confirm, `#auditPurgeBtn`/`openAuditPurgeModal`)(AC-0311). [x] 내 활동기록 profile 탭(`data-profile-tab="audits"`/`loadProfileAudits`, `/api/profile/audits`)(AC-0312). [x] 감사 필터 facet 드롭다운(datalist+`loadAuditFacets`)(AC-0313). [x] attachment-grants 대시보드 카드(`#dashboardGrantHealth`/`loadGrantHealth`)(AC-0314). admin.html/admin.js + index.html/app.js + styles.css. node --check PASS(app.js·admin.js).
  - **Tier 3 (진입점 아님 — 결정/정리)**: [ ] `attachment.execute_sql_on.*` 미적용 권한(enforce or remove, RBAC 변경→outside-voice) [ ] `conversation.attachment.upload.any`(product 결정) [ ] 죽은 중복 정리.
  - **PB-0008 Windows-browser 완료 게이트**: [x] 실제 Windows Chrome 검증 **PASS(39/39 step)** — 7개 진입점 전부 live 동작 확인(finalize morph·공유관리 모달·scopeAll·내활동기록·grant카드·audit.purge 모달·facet `{res:9,actor:5}`). 시나리오 `tests/win-browser-task0158.scenario.json`, 증거 스크린샷 10장(`/tmp/win-browser-shots/task0158/`), 상세 TEST.md §4.

### TASK-0157 요청 중단(interrupt) 진입점 복구 (2026-06-08)

- [x] TASK-0157 (REQ-20260608-0157, **Minor §12.3** — frontend-only). 사용자 보고: 요청 후 "중단" 기능이 UI에 안 나타나고 진입 경로가 없음. /investigate 근본 원인: 중단/즉시 답변 버튼이 커밋 `4ba71f5` 의 영구 숨김(`style="display:none"`) `#progressCard` 안에 고아로 남아 `renderProgress()` 의 `classList.remove("hidden")` 가 인라인 style 에 가려 무효 → 정상 동작 중 취소 진입점 0개. 백엔드 `/api/cancel`·에이전트 루프 폴링·RBAC 는 정상. **수정(ChatGPT 패턴)**: `renderComposer()` 가 처리 중 `#sendBtn` 을 "중단" 버튼으로 모핑(stop 아이콘 + `.is-stop` 위험색 + native disabled 해제) + click 핸들러 busy→`cancelCurrentRun()` 분기 + hover 툴팁 숨김 + 중단 권한 access-blocked 반영(AC-0306/0307). 변경 2파일(app.js/styles.css). node --check PASS. **이월**: finalize 진입점 미노출(동일 근본 원인, 사용자가 단일-버튼 send-morph 선택으로 본 cycle 범위 밖). REV-20260608-0157 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret].

### TASK-0151 첨부 text inline cap 정렬 버그 수정 (2026-06-05)

- [x] TASK-0151 (REQ-20260605-0151, **Major §12.3** — DB 조회 UX 개선의 web 면). `_prepare_text_inline_attachments` 의 SELECT 정렬 `ORDER BY Id ASC LIMIT %s` → `ORDER BY Id DESC LIMIT %s` + 선별 후 `inline_entries.reverse()`. text 첨부가 count cap(20) 초과 시 이전엔 가장 오래된 20개만 inline 주입되고 방금 첨부한 최신 파일이 조용히 누락됐던 것을, 최신 cap개 보존 후 표시 순서를 시간순으로 복원하도록 수정. AccountId IDOR 스코프·size cap 무변경. agent_core 의 첨부 리뷰 우선순위 prompt 개편(feature-0002 TASK-0151)과 한 쌍. outside-voice 적대적 diff 리뷰 ACCEPTED (REV-20260605-0151, BLOCKER 0).

### TASK-0124 관리 콘솔 RBAC 권한 정합 및 폐기 권한 정리 (2026-05-28)

- [x] TASK-0124 (REQ-20260528-0124, **Minor** §12.3 — RBAC 시드 롤 정합 + 폐기 권한 DB 정리). 사용자 직접 요청: (1) `sales` 롤이 `conversation.create` + `conversation.ask` 를 보유하면서 `conversation.delete.own` 이 없어 자신의 대화를 삭제할 수 없는 구조적 비정합. (2) `conversation.suggestions.read` 가 `conversation.ask` 와 항상 함께 부여되는 종속 권한 — 단독 실효성 없는 zombie 권한. (3) `pending` 롤의 `conversation.file.read.own` — "승인 전 조회 전용" 의미와 파일 다운로드 혼재. **수정**: (a) `SEED_ROLE_DEFINITIONS` 의 `sales` 에 `conversation.delete.own` 추가. (b) `conversation.suggestions.read` 를 `PERMISSION_DEFINITIONS` + 모든 시드 롤에서 제거, suggestions endpoint 게이트를 `conversation.ask` 로 변경, `_legacy_permission_codes_from_row` 에서 제거. (c) `pending` 의 `conversation.file.read.own` 제거. (d) `_ensure_seed_roles()` 의 catchup_codes 에 `conversation.delete.own` 추가 (sales 기존 계정 반영). (e) `_cleanup_deprecated_role_permissions(conn)` 신규 함수 — `DELETE FROM WebRolePermissions` 로 폐기 권한을 기존 롤 rows 에서 멱등 제거. (f) `docs/STATUS.md` 변경 이력 2건 추가. 신규 RBAC 권한 코드 추가 없음 / DB 스키마 변경 없음 / secret handling 없음 → outside-voice review SKIPPED.

### TASK-0108 Sprint 3 — Admin-only manual KB ingest (B: DDL/KB 보강) (2026-05-26) — ⚠ 제거됨 (2026-05-27)

> **REQ-20260527-0001 — 설계 결함으로 제거**: (1) KB 등록 목록이 대화 첨부(`WebConversationAttachments`)에 의존 — 관리 영역이 사용자 대화에 기생하는 구조로 독립성 원칙 위반. (2) Weight=90 manual fact 가 DB 스키마 변경 시 오래된 정보를 자동 수집(Weight=1)보다 우선 참조 — 스키마 오염 위험. 재설계 시 별 cycle 로 진행.
> **제거 범위**: `admin.html` KB 등록 탭/pane, `admin.js` kbIngest 상태·함수 221 LOC, `app.py` `attachment.kb.write.any` RBAC 정의 + admin seed grant + `GET /api/admin/attachments` + `POST /api/admin/attachments/kb-ingest` 두 endpoint. `kb_ingest.py` 모듈 + `test_kb_ingest*.py` 는 보존 (재설계 시 재활용 가능).

- [x] TASK-0108 (REQ-20260526-0108, **Major** §12.3 — RBAC 신규 코드 1개 + 신규 admin endpoint + AgentMemoryFactEntries manual ingest path 신설). **2026-05-27 UI/endpoint 제거 (REQ-20260527-0001).** BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3 Cycle 3 (B: DDL/KB 보강, Major, ~1주). TASK-0094 PLAN-APPROVED (2026-05-21) 의 multi-cycle plan 안 sprint 3 implementation. **본 cycle 산출 (예정)**: (a) `app.py` PERMISSION_DEFINITIONS 에 `attachment.kb.write.any` (admin only) 1 코드 + role grants 4 catchup (admin/dba 만), (b) `unit/feature-0002-agent-core/src/modules/kb_ingest.py` 신규 — 첨부 본문 → AgentMemoryTexts INSERT + AgentMemoryFactEntries INSERT 의 멱등 path. ConversationId='__kb_manual__' reserved sentinel + FactKey=ScopeKey 자체 + Weight=90 (BRIEFING D 의 0.9 scale, manual fact 우선) + SourceType='manual' + FactFingerprint=SHA1(normalized body). 동일 (conv, scope, key) 기존 active row (Weight>0) UPDATE Weight=0 으로 logical supersede (Status 컬럼 추가 회피, 회귀 0), (c) `app.py` `POST /api/admin/attachments/kb-ingest` 신규 endpoint — RBAC gate `attachment.kb.write.any` + body `{attachment_id, scope_key, source_type='manual', weight=90}` validation + storage_minio 본문 fetch + kb_ingest.ingest_manual() 호출 + audit `attachment.kb.ingest` dispatch + 응답 `{fact_entry_id, scope_key, text_hash, superseded_count}`, (d) `admin.html` "스키마 정의서 KB 등록" pane (kind=text/markdown 또는 .sql ext 표기 첨부 list + ScopeKey 입력 + preview + ingest 버튼), (e) `admin.js` pane 이벤트 핸들러, (f) `repo/AGENTS.md` §11.3 확장 — "manual ingest fact 의 SourceType='manual', Weight=90 (= BRIEFING 의 0.9 scale, 자동 수집 Weight=1 대비 우선)", (g) tests — `unit/feature-0003-agent-web-ui/tests/test_kb_ingest_rbac.py` (RBAC matrix 4 case + ScopeKey 충돌 superseded + audit dispatch) + `unit/feature-0002-agent-core/tests/test_kb_ingest.py` (module unit test). **outside-voice review (Codex) 호출** — RBAC 신규 코드 + audit + ScopeKey supersede semantics = 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합. **본 turn 의 deliverable 은 backend (a~c) + frontend (d~e) + AGENTS.md (f) + tests (g) + docs + Codex review + commit/PR/merge**. base = main HEAD (5448611 — KB Postgres bootstrap fix 흡수 후, `_pg_available()` true 환경 자연).

### TASK-0107 첨부 내용 LLM 직접 인지 + drag&drop UX 확장 (2026-05-22)

- [x] TASK-0107 (REQ-20260522-0107, **Major** §12.3 — LLM 동작 변경 + sandbox SQL 동선 + UI 진입점 확장). 사용자 직접 보고 2건. **(1) 파일 첨부 후 LLM 이 "실제 내용을 직접 볼 수 없습니다" 응답** — TASK-0094 의 sandbox ingest 파이프라인 (`sandbox_ingest.ingest_attachment` + `agent_attachment_<sha256>` schema + WebConversationAttachments.MetaJson `sandbox_table_name`) 정의는 있었으나 **caller 가 ship 안 됨** (REVIEW.md 1465 의 미해결 항목). 결과: MetaJson 에 sandbox_table_name 미기록 → `_build_attachment_context_section` 의 ATTACHED FILES 영역이 schema 명을 noindict → LLM 의 SQL tool 이 SELECT 시도하지 않고 사용자에게 텍스트 복붙 요청. **수정 (3-phase)**: Phase A (활성화) — `app.py` 의 upload endpoint (`POST /api/conversations/{cid}/attachments`) 의 audit dispatch 직후 `threading.Thread(target=_ingest_attachment_background, daemon=True)` spawn (kind=csv|xlsx 한정). 신규 helper `_ingest_attachment_background` 가 storage_minio 로 bytes 받기 → `CREATE SCHEMA IF NOT EXISTS agent_attachment_<sha256(cid)[:32]>` (root user 단일-user MVP — 4-user 분리 grant 는 후속 cycle) → `_open_memory_connection(database=schema_name)` 으로 sandbox conn → `sandbox_ingest.ingest_attachment` 호출 → MetaJson 에 `sandbox_schema_name` + `sandbox_table_name` (csv) 또는 `sheets[]` (xlsx) 기록 + UploadStatus='ingested'. 실패 시 `_mark_ingest_failed` 가 UploadStatus='failed' + MetaJson.degraded_reason 기록. `db.py` 의 `connect()` 에 `agent_attachment_*` schema 패턴 매칭 → **primary 라우팅 강제** (replica latency / 미배포 환경에서도 즉시 SELECT 가능). Phase B (LLM 인지) — `agent_core.py` 의 `_build_attachment_context_section` 전면 강화: metadata + sandbox_table_specs 수집 + each table 의 `information_schema.columns` SELECT (column 명 + data_type) + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows 출력 (markdown 표, 80자 cell truncate, pipe escape, table cap 20). 명시 INSTRUCTION 추가 — "When the user asks about an attached file's contents, first try to answer from the sample rows above. If more data is needed, call execute_sql against the sandbox table … Do NOT ask the user to paste the file contents — the data is already accessible." UploadStatus='uploaded' (ingest 미완 또는 'failed') 분기는 별도 안내. **(2) drag&drop UX + 새 대화 시 첨부 차단** — composer-wrap 만 drop zone 이라 chat 영역 대부분에서 drop 미발동 + 사용자가 새 대화 진입 직후 (pendingSentinel 미발급 시점) 첨부 시도 시 "대화 컨텍스트 미정" toast 로 차단. **수정**: index.html 에 chat-pane 자식으로 `#chatDropOverlay` (점선 border + 아이콘 카드) 추가, styles.css 에 `.chat-drop-overlay` (absolute inset 0 + backdrop-filter blur + fade-in animation) + `.chat-pane { position: relative }` 추가. app.js `_bindComposerAttachmentEvents` 에 chat-pane scope drag/drop 핸들러 + `_isFileDrag()` types Files guard + dragCounter 중첩 추적 + window dragend / drop 시 reset (drop miss 방어) + chat-pane 밖 drop 시 브라우저 기본 동작 (파일 새 탭 열기) preventDefault. `_uploadComposerAttachment` 진입 시 컨텍스트 미정 (activeConversationId 없음 + pendingSentinel 없음) 검출 시 `conversation.create` 권한 검증 후 자동으로 pendingNewConversation=true + `_newPendingSentinel()` 발급 + 모든 render 호출 — 기존 lazy-create path 재사용. py_compile + node --check PASS. backend RBAC / DB schema / endpoint contract / D11 consent / D13 server-side bytes 전 무변경. 4-user 분리 grant model (BRIEFING D2/D15) 은 후속 cycle (.env 비밀번호 미설정 → 단일-user MVP 채택). 본 cycle worktree `ai/claude/0107-attachment-content`.

### TASK-0106 첨부 모듈 import 경로 + lazy-create 첨부 staging (2026-05-22)

- [x] TASK-0106 (REQ-20260522-0106, **Major** §12.3 — 외부 storage 통합 + 사용자 노출 첨부 동선 회복). 사용자 직접 보고 2건: (1) 웹 첨부 업로드 시 `Error: storage 모듈 import 실패: cannot import name 'storage_minio' from 'modules' (/app/modules/__init__.py)` toast — backend `/app/modules` 는 feature-0002-agent-core 의 unified namespace (14 module cross-injection) 인 반면 `storage_minio.py` 는 feature-0003-agent-web-ui 의 module 로 Dockerfile 이 `/app/web/modules/` 로 copy. `app.py` 의 `from modules import storage_minio` (3 callsite: vision inline `_prepare_vision_inline_images` L6044, upload endpoint L7555, metadata endpoint L7771) + `from modules import sandbox_schema` (L11862) 가 잘못된 namespace 검색 → `from web.modules import …` 으로 교체. feature-0002-agent-core/src/modules/attachment_reconciliation.py 의 `_delete_minio_object()` (worker 환경 host dev sibling path fallback 보존) 에는 `from web.modules import storage_minio` 우선 시도 + ImportError 시 기존 sys.path 삽입 fallback 의 dual-mode 보강. (2) "+ 새 대화" 클릭 후 첫 메시지 전송 전엔 첨부 불가 — `_uploadComposerAttachment` 의 `if (isLazy)` 조기 차단 toast. lazy-create 패턴 (TASK-0048) 의 부수 효과로 cid 미발급 = `/api/conversations/{cid}/attachments` 호출 불가. **수정 (Option A — client-side staging)**: lazy 분기에서 즉시 차단 대신 pendingSentinel bucket 에 status=`staged` + `_localFile=File` 로 보관, `sendPrompt()` 의 lazy-create path 가 staged 첨부 ≥1 감지 시 `/api/new_conversation` 으로 cid 즉시 발급 → `_flushStagedAttachmentsToCid(earlyCid, pendingKey)` 신규 helper 가 staged 일괄 업로드 → askBody 를 `lazy_create=true` (legacy) 에서 `conversation_id=earlyCid` (즉시-cid 모드) 로 전환 + `attachment_ids` 에 union. staged 가 0 인 lazy-create 는 기존 lazy_create=true 단일 호출 보존 (TASK-0048 정신). pill rendering 에 `data-staged="true"` 속성 + "(첫 메시지와 함께 업로드)" tooltip 추가. `_toggleAttachmentPill` 에 staged 토글 = remove (실수 클릭 시 재선택 부자연스러움 회피). py_compile + node --check PASS. backend / RBAC / DB schema / endpoint contract 무변경. 본 cycle worktree `ai/claude/0106-attachment-fix`. cache-bust 갱신 필요 (live deploy 후 별 commit).

### TASK-0105 Profile Drawer '내 감사 로그' 탭 제거 (2026-05-22)

- [x] TASK-0105 (REQ-20260522-0008, **Minor** §12.3 — UI 노출 범위 축소). 사용자 직접 요청 — 일반 사용자에게 Profile Drawer 내 '내 감사 로그' 탭이 노출되어선 안 됨. TASK-0089 가 추가한 탭 버튼 (`profileAuditTab`, `data-profile-tab="audit"`) + drawer 패널 (`data-profile-pane="audit"`) + JS 로직 일체 (`_profileAuditEscapeHtml` / `_profileAuditFormatDt` / `_profileAuditHasReadPermission` / `updateProfileAuditTabVisibility` / `_profileAuditReadFilters` / `_profileAuditClearFilters` / `loadProfileAuditList` / `renderProfileAuditList` / `renderProfileAuditDetail` / `attachProfileAuditHandlers` + state.profileAudit 초기값) + CSS (`profile-audit-*` 전체 블록) 를 index.html / app.js / styles.css 에서 제거. backend `/api/profile/audits` endpoint 및 admin 콘솔 '감사 로그' 탭 무변경. node --check + py_compile PASS. cache-bust: 기존 `v=20260522-task-0098-perms` 유지 (frontend 파일 재배포 시 갱신 권장). 본 cycle worktree `ai/claude/0105/remove-audit-tab`.

### TASK-0104 외부 노출 web 컨테이너 HTTPS 종단 활성화 (2026-05-22)

- [x] TASK-0104 (REQ-20260522-0007, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선의 secure-channel 요건 충족). 외부 사용자가 `https://112.185.196.20:18080/` 로 접속할 수 없던 이슈 수정. **근본 원인**: `repo/.env` 는 `ENABLE_WEB_TLS=1` 로 설정되었고 `docker-compose.yml` 의 web entrypoint 에는 TLS 분기가 있으나, `docker-compose.override.yml` (gitignored, dev 용 template) 가 entrypoint 를 평문 HTTP uvicorn 으로 강제 override 하고 있었음 — TASK-0103 에서 secure-context guard 는 추가했지만 secure channel 자체가 비활성. **수정**: `docker-compose.override.yml` 의 web entrypoint 를 `--ssl-keyfile /certs/mysql-ai.company.local/privkey.pem --ssl-certfile /certs/mysql-ai.company.local/fullchain.pem` 포함한 HTTPS 종단으로 교체. 기존 인증서 (`../artifacts/certs/mysql-ai.company.local/`) 는 SAN 에 `IP Address:112.185.196.20` 이미 포함되어 있어 재발급 불필요. `docker-compose.override.yml.example` 에는 Variant A (local dev plain HTTP) / Variant B (외부 노출 HTTPS, 본 cycle default) 두 형태를 주석으로 명시. 호스트 포트 18080 매핑 그대로 — same-port HTTPS 전환. **외부 영향**: 기존 HTTP 18080 사용자는 모두 HTTPS 로 전환 필요 (TLS 종단 교체이므로 동일 포트의 HTTP 동시 제공 안 됨). **검증**: `sudo docker compose up -d web` 후 `curl -sk https://112.185.196.20:18080/` → HTTP 200 + `<title>DQA — Database Query Assistant</title>` 응답. 컨테이너 로그 `Uvicorn running on https://0.0.0.0:8000`. backend / RBAC / endpoint contract / DB schema / WebCrypto 클라이언트 코드 무변경. 근본 해결 완료로 TASK-0103 의 "blocked banner" 는 외부 IP HTTP 접속자에게도 자동 안내됨 (HTTP 18080 자체가 끊겨 사용자는 즉시 HTTPS 로 이전).

### TASK-0103 API Vault secure context 사전 차단 + UX 안내 (2026-05-22)

- [x] TASK-0103 (REQ-20260522-0006, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선). 외부 사용자가 `http://112.185.196.20:18080/` 로 접속하여 OpenAI API Key 입력 시 모호한 toast 만 출력되며 저장 안 되던 이슈 수정. **근본 원인**: WebCrypto SubtleCrypto (`window.crypto.subtle`) 는 secure context (HTTPS / localhost) 에서만 정의됨. 외부 IP 의 HTTP 접속 시 `undefined` → `encryptPlainApiKey()` 의 `crypto.subtle.importKey(...)` 가 `Cannot read properties of undefined (reading 'importKey')` throw → catch 블록에서 noisy toast 만 출력, 저장 실패. 서버는 `requires_secure_context: True` 를 내려줬지만 클라이언트가 활용 안 함. **수정**: (1) `isVaultCryptoAvailable()` helper (`window.isSecureContext && window.crypto?.subtle`). (2) `updateVaultReadiness()` `blocked` 신규 상태 — 빨간 banner + 한국어 사유 안내 (`public_url` 이 https 면 보안 주소 표기). (3) `syncVaultSteps()` 가 `cryptoOk = false` 시 모든 step disable + saveVaultBtn 차단. (4) `encryptPlainApiKey()` 진입 시점에 명시적 throw — UI 우회 시도도 안전 차단. (5) styles.css 에 `vault-banner[data-state="blocked"]` 빨간 톤 추가. cache-bust `v=20260522-vault-secure-context`. backend / RBAC / endpoint contract / DB schema / 암호화 알고리즘 (PBKDF2 + AES-GCM) 무변경. `docker compose build web` + `up -d --no-deps web` 으로 배포. 근본 해결 (HTTPS 종단점 추가) 은 후속 인프라 cycle 로 분리.

### TASK-0102 topbar 관리 콘솔 버튼 role fallback gate (2026-05-22)

- [ ] TASK-0102 (REQ-20260522-0005, **Minor** §12.3 — topbar `관리 콘솔` 버튼 role 기반 fallback gate). 테스트 결과 `sales` 역할 사용자에게 topbar 관리 콘솔 버튼이 노출되는 현상 확인. **근본 원인**: TASK-0100 에서 추가한 `console_access` 플래그가 구버전 서버(미재시작) 또는 캐시된 응답에서 `undefined` 로 오는 경우, 기존 `Boolean(undefined)` = `false` 는 정상이나, 서버가 TASK-0100 이전 코드를 실행 중이면 `canOpenAdminConsole() → can("console.access") → Boolean(state.user)` 경로로 항상 `true`. **수정**: `console_access` 가 서버 응답에 포함된 경우 그것을 사용, 없으면 `role.key === "admin"` 으로 fallback — role 필드는 TASK-0098 이전부터 항상 직렬화되므로 버전 무관하게 존재. app.js, index.html(cache-bust) 변경. backend / RBAC / DB / endpoint 무변경.

### TASK-0100 관리 콘솔 버튼 RBAC gate 수정 (2026-05-22)

- [x] TASK-0100 (REQ-20260522-0004, **Minor** §12.3 — `관리 콘솔` 버튼 노출 조건 수정). "admin" 역할 이외의 사용자에게 `관리 콘솔` 버튼이 노출되는 이슈 수정. **근본 원인**: TASK-0098 에서 frontend `can()` 함수를 `Boolean(state.user)` 로 단순화하면서, `canOpenAdminConsole()` 도 로그인한 모든 사용자에게 `true` 반환 → 버튼 노출. **수정**: `_serialize_account()` 에 `console_access: bool` 최소 플래그 추가 (`_account_has_permission(account, "console.access")` 기반). `canOpenAdminConsole()` 이 `Boolean(state.user?.console_access)` 을 검사하도록 변경. TASK-0098 의 "permissions 전체 노출 차단" 설계를 유지하면서 UI gate 에 필요한 최소 정보만 전달. backend / RBAC catalog / DB schema / endpoint contract 무변경. py_compile + node --check PASS. cache-bust `v=20260522-console-access-gate`.

### TASK-0099 Audit subsystem followup backlog 사후 tracker hygiene (2026-05-22)

- [x] TASK-0099 (REQ-20260522-0003, **Minor** §12.3 — docs-only tracker hygiene). TASK-0073 audit subsystem followup backlog 8 entries (TASK-0086~0093) 8/8 완료 후 정리 cycle. TASK.md 의 stale `[ ]` 체크박스 2건 close: (1) line 152 TASK-0072 (main 통합 `f298f90` + hotfix bundle TASK-0074~0080 모두 deployed but 상태 `outside-voice-review` 미갱신), (2) TASK-0073 line 2767 `AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod` startup fail-closed acceptance (TASK-0092 V1-V3 fail-closed scenario 가 정확히 검증 → close). 추가로 STATUS.md feature-0003 row 에 audit followup backlog 8/8 완료 marker append. docs-only — 코드 / RBAC / 스키마 / endpoint 변경 0. outside voice trigger 미해당 (audit/RBAC 표면 변경 없음). 본 cycle CHG-20260522-0003, REV-20260522-0003 [SKIPPED:doc-only-tracker-hygiene] on `ai/claude/feature-0003-agent-web-ui` worktree.

### TASK-0073 Audit subsystem followup backlog (2026-05-20)

본 worktree (`ai/claude/0086/audit-followup`) 는 TASK-0073 의 후속 cycle 들을 등재한다. 본 cycle 작업자는 아래 6 entries 중 하나 이상을 선택해 plan-eng-review / plan-ceo-review / outside voice 후 진행. 각 entry 는 별 cycle (별 PLAN-APPROVED marker + 별 CHG/REV) 로 분리한다.

- [x] TASK-0086 (REQ-20260520-0001, **Major** §12.3 — `WebAccountActivity` legacy table DROP + dual write 종료). **DROP 완료 (2026-05-20)**. backup `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes, 74 row, digest `a09e7898d1ce88711f7a850ab5fbcc91`) + scratch restore rehearsal PASS + 1:1 정합 (legacy=74, mirror=74) + 사용자 명시 ack. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign (helper Option B 명시 제거 / dispatcher-only smoke / mysqldump 옵션 보강 / scratch restore / rollback 2 시나리오). 코드: `_log_search_activity()` legacy INSERT 제거 + `_ensure_web_account_activity_schema()` 호출×2+정의 제거 + `_migrate_web_account_activity_to_audit()` rollback window 보존 + test_audit_migration.py M3 제거. 본 cycle CHG-20260520-0005, REV-20260520-0005 on `ai/claude/0086/legacy-drop` worktree.
- [x] TASK-0087 (REQ-20260520-0002, **Major** §12.3 — 외부 LAN trust 강화, feature-0006 + feature-0003 협업). Caddy `header_up X-Forwarded-For {client_ip}` 정규화 + `_get_client_ip()` 조건부 trust (env `WEB_TRUSTED_PROXIES`) + malformed XFF token IP 검증 + mode-aware fail-loud (prod/staging `RuntimeError`, dev/test stderr WARNING) + proxy mode + empty env regression 경고. Codex outside voice review 5 Major + 1 Minor 흡수 후 v2 redesign (RFC1918 default 사용자 명시 결정 유지 + Caddy XFF 정규화로 multi-hop 차단). `docs/SECURITY.md §9.7` 갱신. 본 cycle CHG-20260520-0010, REV-20260520-0010 on `ai/claude/0087-lan-trust-hardening` worktree.
- [x] TASK-0088 (REQ-20260520-0003, Minor §12.3 — `slow_query_log` 통합 **ADR-0020 Decoupled 채택**). TASK-0073 Codex C1 lock-in 의 별 cycle 분리 → 최종 ADR. **Option C — Decoupled** 채택, slow_query_log 와 WebAuditEvents 통합 안 함. 주 근거 = raw SQL text PII 차단 (PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt literal). 운영 성능 관측 = `performance_schema`/`sys` digest views (1차) + slow_query_log incident enable (2차). Codex outside voice 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign (current state framing 정정 + Option A/B reject 재작성 + PS digest-first 권유 + SaaS trigger 명확화). 본 cycle CHG-20260520-0007, REV-20260520-0007 on `ai/claude/0088/slow-query-log-adr` worktree. docs only.
- [x] TASK-0089 (REQ-20260520-0004, Minor §12.3 — 작업 화면 audit drawer UX). profile drawer 5번째 탭 "내 감사 로그" 신설 + 신규 backend endpoint `/api/profile/audits` + `/api/profile/audits/{event_id}` (scope=own 강제). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign: (1) `/admin/` endpoint 의미 mismatch → 별 `/api/profile/audits` 신설 (Codex C1), (2) backend scope="own" 강제 — `.any` 보유자도 본인 row만 (Codex C2), (3) CSV export/purge drawer 미노출 (Codex C3 — admin 한정), (4) drawer 폭 390px 1-column + inline detail expand + ChangeJson 수평 스크롤 (Codex C4), (5) tab visibility = audit.read.own || audit.read.any + 403 graceful (Codex C5). 본 cycle CHG-20260520-0009, REV-20260520-0009 on `ai/claude/0089-audit-drawer-ux` worktree.
- [x] TASK-0090 (REQ-20260520-0005, Minor §12.3 — CSV streaming export). `/api/admin/audits/export.csv` 의 hard cap 50k row 제거 + `StreamingResponse` + keyset cursor pagination 전환. Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign: (1) sync generator + streaming-only conn (Codex C1 — async event loop blocking 회피), (2) max_id high-water mark (Codex C2 — long transaction 회피), (3) chunk_size 500 + 64KiB byte-threshold flush (Codex minimum-fix), (4) try/finally cleanup (Codex C5 — client disconnect cursor/conn 누설 차단), (5) export self-audit start + complete/aborted (Codex C4 — DoS 운영 제어), (6) hard cap 50k 제거 + SECURITY.md §9.5 갱신. 본 cycle CHG-20260520-0008, REV-20260520-0008 on `ai/claude/0090-csv-streaming-export` worktree.
- [x] TASK-0091 (REQ-20260520-0006, ~~Minor~~ **Major** §12.3 — PATCH admin/products audit before-state full snapshot + audit integrity fix). TASK-0073 Phase A5 의 `admin.product.update` audit 의 before-state 가 `{id, product_key}` 만 → full snapshot 으로 확장 + Codex outside voice 5 findings 흡수. **scope 확장 (Minor→Major)**: Codex C2 가 `admin_update_product()` 의 `autocommit=True` default + UPDATE 즉시 commit + audit 실패 시 rollback 가능 0 인 **audit integrity 결함** 노출. 본 cycle 일괄 fix: (1) `_audit_product_snapshot()` 신규 helper (single-row + SELECT FOR UPDATE + system_prompt summary only, SECURITY §9.2 정합), (2) endpoint 명시 transaction (autocommit=False + commit + finally autocommit=True), (3) `_AUDIT_BUILDER_PRODUCT_FIELDS` 확장 (`+is_default`, `+sort_order`, `+system_prompt_summary` / `-databases`, `-system_prompt` full), (4) `default_cleared_product_ids` side effect 기록, (5) sentinel smoke PASS (SENTINEL `TASK-0091-SENTINEL` ChangeJson 부재 확인, system_prompt content drop). 본 cycle CHG-20260520-0006, REV-20260520-0006 on `ai/claude/0091/product-audit-snapshot` worktree.
- [x] TASK-0092 (REQ-20260520-0007, Minor §12.3 — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 검증). TASK-0073 Phase E 의 사용자 위임 항목 1 건. **7 vector matrix PASS (7/7)** — V1~V3 fail-closed + V4 dev bypass + V5 positive control + V6 strict-string-equality (Codex C3) + V7 default. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용 (`docker run --entrypoint python --no-deps` + `import web.app` + stderr 3 substring 검증 + TEST.md **§4** append). 본 cycle CHG-20260520-0004, REV-20260520-0004 on `ai/claude/0092/audit-prod-fail-closed` worktree.
- [x] TASK-0093 (REQ-20260520-0008, Minor §12.3 — `bin/verify-completion.sh check_12` audit endpoint routing 정적 검사). TASK-0073 Phase E hotfix (CHG-20260520-0001) 의 routing 회귀 fragility 보강. Codex outside voice review 5 findings 흡수 후 plan v2 redesign (SKIP→FAIL structural / inline 4-path→auto-discovery static GET / `/purge` method-aware 제외 / helper split + fixture test / `9 checks`→`10 checks` footer). Phase A~D 모두 검증 PASS (production positive + 5 fixture negative + 5 other-feature SKIP). 본 cycle CHG-20260520-0003, REV-20260520-0003 on `ai/claude/0086/audit-followup` worktree.
- [x] TASK-0098 (REQ-20260522-0002, **Critical** §12.3 — Profile Drawer 탭 재구성 + 권한 정보 API 단위 차단). 사용자 직접 요청 (2026-05-21). Profile Drawer 탭 5 → 4 = `[프롬프트, 보안 및 계정, API Vault, 내 감사 로그(gated)]` (보안+계정 통합 + "활동 정보" 최상단). "권한 현황" 패널 = 운영자 전용 정보 분류 → UI + `/api/auth/me` 양쪽 차단. `/api/admin/me` 신규 endpoint 분리 (console.access gate, Codex F1 blocker fix). `_serialize_account(account, *, include_permissions: bool = False)` 시그너처 + 7 self callsite 자동 permissions 제거 + admin 3 callsite 명시 보존. frontend `can()` = `Boolean(state.user)` 단순화 ("표시 허용 + 실행은 backend 403 fallback" 패턴, Codex F5). `apiFetch` 403 공통 toast. backend 일반 사용자 경로 403 메시지 5 패턴 9 callsite normalize. admin.js `/api/auth/me` → `/api/admin/me` 전환. TASK-0089 audit 탭 보존. tests/test_admin_me_rbac.py 4 + tests/test_auth_me_rbac.py 5 시나리오 신규. Codex outside voice 6 findings 흡수. **PR #49 multi-race rebase**: 본 cycle 원래 4 commit (base 8888130) 가 main stale 진행 (#45/#47/#48/#50/#52/#61 + DQA 브랜딩 + TASK-0095/0096 v2) 흡수 후 main HEAD 20f0344 위 단일 squash commit. ID reassign: TASK-0094→TASK-0098 / REQ-20260521-0001→REQ-20260522-0002 / AC-0199~0207→AC-0226~0234 / CHG·REV-0001~0004→CHG·REV-20260522-0002 / cache-bust `v=20260522-task-0098-perms`. backup branch `backup/profile-tabs-restructure-pre-rebase`. worktree `ai/claude/profile-tabs-restructure`.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0098 ex-0094/0096, Critical §12.3 — Profile Drawer + permission API 차단 + Codex outside voice 6 findings 흡수. multi-race rebase 시점 ID reassign + squash 재적용.) -->

- [x] TASK-0095 (REQ-20260521-0003, **Major** §12.3 — GLOBAL system prompt layer + 신규 `설정` 탭). 사용자 직접 요청 — "현재 서비스 사용자의 시스템 프롬프트 누적 구조에서, 최상위 전역 프롬프트도 구성해주세요." 4 layer (BASE → Product → Role → Account) 의 BASE 가 코드 상수 hard-code 라 운영자 수정 불가하던 구조를 5 layer (GLOBAL → Product → Role → Account, BASE = code constant fallback) 로 확장. WebSystemPrompts schema 무변경 (Scope VARCHAR(16) 가 이미 'global' 수용). RBAC 2 권한 신설 (`system_prompt.global.read/.write`, group=`settings`, admin auto-grant). 관리 콘솔 sidebar 에 신규 `설정` 탭 + 확장 가능한 `admin-settings-section` sub-section 패턴 도입 — 차후 운영 항목 추가 시 동일 패턴으로 sub-section 누적. AC-0011 갱신 + AC-0199 ~ AC-0204 신설. 본 cycle CHG-20260521-0003, REV-20260521-0003 on `ai/claude/global-system-prompt` worktree. **Follow-up** (CHG-20260521-0004, REV-20260521-0004): live deploy 후 사용자 검증 진행 중 발견 — `_ensure_seed_catchup` (fast path) 에 `_ensure_seed_global_system_prompt` 호출 누락. 1줄 hot-fix.
- [x] TASK-0097 (REQ-20260522-0001, **Minor** §12.3 — DQA 브랜딩 적용). 사용자 요청: 웹브라우저 출력 시 'MySQL AI' 제거, DQA (Database Query Assistant) 로 명명, 로고 신설. `index.html` · `admin.html` title/brand-name/auth-title → DQA 전면 교체. `logo-dqa.svg` 신설 (48×48 primary #2563eb, DB 실린더+돋보기 조합). `.auth-logo` / `.brand-icon` CSS background → transparent (SVG 배경 직접 표시). Minor §12.3 — 정적 자산 변경만, backend/RBAC/DB/endpoint 무영향. AC-0219~AC-0222 FUNCTION.md 등재. CHG-20260522-0001, REV-20260522-0001 on `issue/58-dqa-rebrand` branch.
- [x] TASK-0096 (REQ-20260521-0004, **Minor** §12.3 — `설정` pane 을 계정/역할/제품 과 동일한 list-detail 패턴으로 정렬). 사용자 직접 요청 v1 — "`설정` 탭 내부 화면을 `계정`, `역할`, `제품` 과 같이 패널을 분리해줄 수 있을까요?" → 1차로 좌측 sub-sidebar + 우측 panel 의 2-column 패턴으로 전환 (CHG-20260521-0005). 사용자 v2 후속 피드백 — "계정, 역할, 제품 탭과 일관된 디자인이 아닌것으로 확인되었습니다. 검색창을 포함하여, 해당 탭들과 일관된 디자인으로 구성해주세요." → 기존 sub-sidebar 클래스 (`admin-settings-shell/-nav/-nav-*`) 제거, 계정/역할/제품 의 5단 구조 (`admin-list-detail` + `admin-list-col` (검색창 + section-label + `admin-list` rows) + `admin-detail-col` (panel)) 채택. nav row 는 `.admin-list-row.admin-list-row--nav` 변형 (체크박스 슬롯 hidden). 검색 필터는 row 의 `data-settings-keywords` + `data-settings-group` + textContent 합치기 substring 매칭. 새 항목 추가 절차 = `<button class="admin-list-row admin-list-row--nav" data-settings-tab="X" data-settings-group="..." data-settings-keywords="...">` + `<article class="admin-settings-panel" data-settings-panel="X">` + `SETTINGS_PANEL_MOUNTERS` 등록 3 단계. UI restructure only — 데이터/API/권한 무영향. AC-0210 갱신. 본 cycle CHG-20260521-0005 (v1) + CHG-20260521-0006 (v2) , REV-20260521-0005 + REV-20260521-0006 on `ai/claude/global-system-prompt` worktree.

### TASK-0094 (REQ-20260521-0001, **Critical** §12.3 — 첨부 multi-cycle A+B+C+D) (2026-05-21)

본 cycle 의 정본 BRIEFING 은 [BRIEFING-attachment-multi-cycle.md](./BRIEFING-attachment-multi-cycle.md) (Revision 2). Codex outside-voice review 2 회 (REV-20260520-0001 1차 + REV-20260521-0002 2차) 흡수 후 결정 D1~D21 21 건 확정. 본 worktree (`ai/claude/0087/attachment-briefing` — git worktree 이름이 0087 로 박혀 있지만 본 cycle 의 작업 번호는 TASK-0094) 의 commit 으로 lock-in. Sprint 1 implementation 은 별 worktree `ai/claude/0094/sprint-1-foundation-csv` (또는 호환을 위해 `ai/claude/0087/sprint-1-foundation-csv` 도 허용 — §15 cleanup 조건 R-F10 준수) 에서 진행.

**Sprint 분할** (BRIEFING §6):

- [x] **Sprint 0 (cycle cleanup)** — BRIEFING Revision 2 lock-in (PR #40 merged) + AGENTS.md §16.5 Step 6 사후 동기화 결과 REPORT.md 기록 (CHG-20260521-0002). 본 cycle 종료 후 worktree cleanup (§15 R-F10).
- **Sprint 1** — Cycle 0 (Foundation: MinIO compose, multipart upload, `WebConversationAttachments`, RBAC 4 codes, D11 consent infra) + Cycle 1 (A: CSV/Excel ingest, sandbox schema, attachment_maintainer/writer/reader/cleanup MySQL users, **D14 SQL allowlist guard ship 조건**) — Critical, 3~3.5 주. D18 단일 통합 gate. worktree `ai/claude/0094/sprint-1-foundation-csv`.
  - [x] **Phase 1 (Pre-flight)** — ADR-0022 (MinIO 도입) + ADR-0023 (sandbox schema + D15 maintenance path 분리) + ADR-0025 (PGVector 사전 선언, Sprint 4 prerequisite) `docs/DECISIONS.md` 등재. docker-compose.yml `minio` + `minio-init` service 추가. `.env.example` 16 변수 (MINIO_ROOT_USER/PW + MINIO_APP_ACCESS_KEY/SECRET + endpoint/bucket/TTL + 호스트 port 2 + browser redirect + ATTACHMENT_MAX_BYTES_* 3 + ATTACHMENT_AUDIT_HMAC_KEY + SANDBOX_SQL_* 2). `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` 부트스트랩 (idempotent bucket + bucket-scoped policy + app key). feature-0001-platform-runtime ANCHOR §1 갱신 (MinIO/Postgres 같은 비-MySQL service 의 platform 책임 명시). 2026-05-21.
  - [x] **Phase 2 (Cycle 0 schema)** — `WebConversationAttachments` + `WebAccountConsents` + `WebAttachmentDerivedMessages` (D19) + `WebConversationAttachmentProviderFiles` (D13) + `WebShareLinks.PolicyVersion` (R-F7) + `WebConversationAttachmentsSandboxSchemas` mapping table. 6 `_ensure_*_schema` / `_ensure_*_column` helper 신설. `_ensure_seed_catchup` (fast path) + `_ensure_web_tables` (slow path) 양쪽 호출 등록. py_compile PASS. 2026-05-21.
  - [x] **Phase 3 (Cycle 0 RBAC)** — `conversation.attachment.upload/read.{own,any}` 4 코드 (group=conversation) `PERMISSION_DEFINITIONS` 추가 + `SEED_ROLE_DEFINITIONS` admin/operator/sales/pending 갱신 (admin=all, operator/sales=upload+read own, pending=read.own만 — D21/R-F14) + `_ensure_seed_roles` admin/operator/sales/dba/pending 5 catchup 갱신 (§5.2 6 checklist 1~5) + app.js label/description map (checklist 6) — backend group=conversation 이므로 attachment group 신설은 Phase 12 SQL guard 의 attachment.execute_sql_on.* 시점에. admin.js 는 backend `/api/admin/permissions` label 직접 사용 — 별 map 없음. py_compile PASS. 2026-05-21.
  - [x] **Phase 4 (Cycle 0 storage)** — `storage_minio.py` wrapper (boto3 + retry + signed URL + smoke test) + D20 dual-key rotation runbook (`RUNBOOK-minio-key-rotation.md`). boto3>=1.34.0 / botocore>=1.34.0 requirements 추가. modules/__init__.py + storage_minio.py 약 350 lines (idempotent client cache + get_storage_config + safe_filename + make_object_key + put/get/delete/signed URL + bucket_exists + run_smoke_test + reset_client_cache + CLI smoke entry). py_compile PASS + 모듈 import smoke 통과. D13 (외부 LLM signed URL 송신 금지) 정합 — `generate_presigned_get()` docstring 에 사내망 다운로드 전용 명시 + `get_object_bytes()` 의 외부 provider 송신 경로 권장. 2026-05-21.
  - [x] **Phase 5 (Cycle 0 upload API)** — 6 endpoint (POST/GET/GET-by-id/DELETE attachment + POST/DELETE consent) + audit 4 ActionCode (`attachment.upload`/`.delete`/`.consent.grant`/`.consent.revoke`) + `build_audit_change_json` case 4 추가 + D7 MIME allowlist + D8 size cap (per_file/conv/account env-driven) + D12 HMAC/extension/size bucket helper + D13 외부 LLM signed URL 송신 금지 정합 (`_serialize_attachment_for_api` 의 signed_url 옵션) + D21 pending bytes deny enforcement (`_account_is_pending` + bytes_access_denied 마커) + RBAC 검증 (`_account_can_access_attachment` 신규 helper). FastAPI UploadFile/File/Form import. py_compile PASS. 2026-05-22.
  - [x] **Phase 6 (Cycle 0 composer UI)** — paperclip + hidden file input + drag-drop overlay (composer-wrap) + attachment pills (status badges: uploading / ready / failed / deselected) + selected toggle + "이 대화의 모든 첨부 사용" scope-all checkbox + D16 attachment selection snapshot (`_composerAttachmentSnapshot` 가 sendPrompt 시점 추출 → askBody.attachment_ids/scope_all 명시 전송) + R-F5 lazy-create 분리 (snapshot key = pending sentinel or conv id) + selectConversation 진입 시 `_loadConversationAttachments(cid)` ground truth 동기화. state.composerAttachments 신규 (byConv / uploadingCount / nextLocalId). app.js JS syntax PASS (node Function check). styles.css 약 130 lines (pill / drop-overlay / paperclip btn). index.html 약 25 lines (composer-attachments + composer-drop-overlay + attach-btn + file input). 2026-05-22.
  - [x] **Phase 7 (Cycle 0 consent)** — D11 + R-F2 grouped batch modal (provider × 3 group: 텍스트/이미지/인덱싱) + revoke flow + GET /api/account/consents 신규 + Profile Drawer "보안 및 계정" 탭 안 consent section. 2026-05-22.
  - [x] **Phase 8 (Cycle 0 share)** — D9 share redact + R-F7 기존 token 자동 redact + PolicyVersion 활성 + share.policy.redact_applied audit case + INSERT PolicyVersion=CURRENT 명시. SHARE_POLICY_VERSION_CURRENT=2 상수. 2026-05-22.
  - [x] **Phase 9 (Cycle 0 lifecycle)** — feature-0002-agent-core/src/modules/attachment_reconciliation.py 신규 (run_once + get_attachment_lifecycle_state + 4 종 SLA 처리). F1 4 state (active/delete_pending+restorable_until/purge_in_progress/erased) _serialize_attachment_for_api 갱신. R-Claim6 tombstone (NOT NULL ConversationId 유지) + F12 pseudonymous event id. 2026-05-22.
  - [x] **Phase 10 (Cycle 1 sandbox)** — .env.example 에 4 MySQL user credentials (maintainer/writer/reader/cleanup) + sandbox_schema.py (sandbox_schema_name_for + ensure_sandbox_schema_via_maintainer R-Claim4 최소권한 (CREATE/ALTER/INSERT/SELECT) + detect_grant_drift + drop_sandbox_schema_via_cleanup) + GET /api/admin/health/attachment-grants R-F4 endpoint. 2026-05-22.
  - [x] **Phase 11 (Cycle 1 ingest)** — feature-0002-agent-core/src/modules/sandbox_ingest.py 신규 (ingest_csv + ingest_xlsx + ingest_attachment, chardet/openpyxl 사용, encoding detect + delimiter detect + sharedStrings/cell/row/col cap + formula stripping + timeout). agent_core.compose_system_prompt 에 _build_attachment_context_section append (env ATTACHMENT_IDS 통해). /api/ask 가 attachment_ids 를 env 로 전달. requirements.txt chardet/openpyxl 추가. 2026-05-22.
  - [x] **Phase 12 (Cycle 1 SQL guard + Sprint 1 Ship)** — sql_guard.py (sqlglot AST shape allowlist, single SELECT/CTE, FOR UPDATE/LOCK/EXPLAIN ANALYZE/SLEEP/BENCHMARK/INTO OUTFILE/LOAD_FILE/information_schema/mysql/performance_schema/sys 거부 + 보조 denylist). attachment.execute_sql_on.{own,any} 2 RBAC (group=attachment) + sales/operator/admin catchup. audit ActionCode 3 (attachment.sandbox.sql_exec/.sql_denied/.scope.all) + build_audit_change_json case. PERMISSION_GROUP_ORDER + WORK_SCREEN/ADMIN_PERMISSION_SECTIONS attachment 그룹 추가. CONVENTIONS.md §10.6 9 group 갱신. **Sprint 1 Ship 완료**. 2026-05-22.
- [x] **Sprint 2 (Cycle 2 Vision Ship — 2026-05-22)** — claude-sonnet-4 / claude-haiku-4 vision flag (`supports_vision`) + `messages_for_provider()` transient content-array (DB string contract 유지) + agent_core image loader (env `ATTACHMENT_IMAGE_INLINE_PATH` 기반, cross-feature import 회피) + `/api/ask` 의 `_prepare_vision_inline_images()` (D11 consent gate, size cap 5MB / count cap 5, 임시 file lifecycle) + `attachment.vision.invoke` audit ActionCode (D12 정합 — raw filename/bytes/object_key 미노출) + D9 share redact 자동 cover (`MetaJson.attachment_derived=true` + `derivation_type="vision_analysis"`) + D19 `WebAttachmentDerivedMessages` join INSERT. feature-0007 (bedrock) 머지 위에서 LiteLLM proxy auto-normalize 활용 — backend 는 OpenAI Chat Completions `image_url` content-array 만 작성, proxy 가 Anthropic Vision spec 으로 변환. **R-F13 provider Files API lifecycle 은 SKIPPED** — 본 cycle 은 base64 inline only (provider 측 잔존 0, Files API 미사용). 14 unit test pass (S2.2 8 + S2.3 6). codex review SKIPPED (사용자 결정 2026-05-22). AC-0280~0285. CHG-20260522-0007. REV-20260522-0014/0015.
- [ ] **Sprint 3** — Cycle 3 (B: DDL/KB 보강, admin-only KB ingest, AgentMemory FactEntries pipe, `attachment.kb.write.any`) — Major, 1 주.
- [ ] **Sprint 4** — Cycle 4 (D: PDF/MD RAG, PGVector dev 단계 도입, chunking + retrieval, **D17 + R-F6 partial_indexed retrieval policy**) — Critical, 3~4 주.

**핵심 결정 21 건** (BRIEFING §2.1 + §2.2 + §17):

D1 S3-compat MinIO / D2 동일 cluster + 별 schema / D3 PGVector / D4 A+B+C+D 전부 4 sprint / D5 Codex review 동반 / D6 lifecycle 4 종 + tombstone + 4 state UX + pseudonymous event id / D7 MIME allowlist / D8 size cap / D9 share derived redact + 기존 token 자동 redact + policy version / D10 PGVector 단계적 / D11 consent provider×class×purpose + grouped modal + provider files lifecycle / D12 audit HMAC + 카테고리 + pseudonym / D13 외부 LLM bytes 서버 read + Files API lifecycle / **D14 sandbox SQL AST allowlist** / D15 wildcard grant 금지 + writer 최소권한 + drift health endpoint / D16 attachment_ids selected-only + lazy-create snapshot / D17 UploadStatus 7 값 + retrieval policy / **D18 단일 통합 PLAN gate 유지** / **D19 `WebAttachmentDerivedMessages` join table** / **D20 MinIO dual-key rotation runbook** / **D21 pending role metadata-only**.

본 cycle 은 PLAN-APPROVED marker 부여 후 Sprint 1 worktree 분리 + implementation 진입. 외부 영향 (PR / 외부 시스템 알림) 은 별도 confirm.

본 backlog 는 본 worktree 의 commit 으로 lock-in. 신규 세션이 본 worktree 에서 진입 (`/_template:entry`) 후 task 선택 + `/plan-eng-review` / `/autoplan` 등 호출.

### TASK-0095 (REQ-20260521-0002, **Major** §12.3 — GLOBAL system prompt layer + 신규 `설정` 탭) (2026-05-21)

본 worktree (`ai/claude/global-system-prompt`) 의 cycle. 사용자 직접 요청 — "현재 서비스 사용자의 시스템 프롬프트 누적 구조에서, 최상위 전역 프롬프트도 구성해주세요. Product / Role / Account 에 기본적으로 처음 누적되어 요청사항에 적용될 부분입니다." `agent_core.py` 의 `SYSTEM_PROMPT` 상수 본문을 DB 화 (BASE 자체를 운영자가 재배포 없이 수정 가능) + 신규 `설정` 탭 신설 (확장성 — 차후 다른 운영 항목 추가 대비) + 그 안에 sub-section "전역 시스템 프롬프트" 마운트.

**누적 순서** (최종): GLOBAL → PRODUCT → ROLE(공통+Product별) → ACCOUNT(공통+Product별).

**핵심 결정** (사용자 in-cycle):
- D1 — BASE 본문을 DB row (`scope='global'`, ProductId/RoleId/AccountId 모두 NULL) 1행으로 이전. 코드 상수 `SYSTEM_PROMPT` 는 bootstrap fallback 으로 유지 (DB row 부재 / mem_conn None / SQL exception 시 안전망).
- D2 — RBAC 신규 2건: `system_prompt.global.read`, `system_prompt.global.write`. admin only auto-grant (다른 role 은 admin override).
- D3 — admin endpoint scope allowlist 에 `'global'` 추가. global scope 는 product_id/role_id/account_id 무시 (force NULL).
- D4 — 신규 admin UI 탭 `설정` (data-admin-tab="settings") + 내부 sub-section 패턴 (`admin-settings-section` data-settings-section). 첫 sub-section = 전역 시스템 프롬프트 (`buildSystemPromptEditor({scope:'global'})`). product/role/account select 미표시.
- D5 — Bootstrap seed: 신규 deploy 시 `_ensure_web_system_prompts_schema()` 다음에 `_seed_global_system_prompt()` 가 idempotent INSERT (row 부재 시에만, SYSTEM_PROMPT 코드 상수 본문). 이후 admin 수정이 우선 — UPDATE 안 함.
- D6 — Audit: `admin.system_prompt.update` builder 의 기존 `request_ctx['scope']` reference 자연 흡수, resource_id pattern `global:0:0:0`.

**Phase 분할**:
- Phase A — `agent_core.py compose_system_prompt()` 첫 부분 GLOBAL fetch + fallback 추가.
- Phase B — `app.py` WebSystemPrompts schema (Scope enum 확장 — VARCHAR 라 추가 변경 0, 단 _seed_global helper 신설), `_load_system_prompt`/`_upsert_system_prompt` 는 scope str 만 받으므로 무변경.
- Phase C — RBAC 2건 추가 (PERMISSION_DEFINITIONS) + admin role catchup 2 codes.
- Phase D — admin endpoint scope allowlist 확장 (GET/PUT 양쪽) + 권한 검사 분기 (`system_prompt.global.read/write`).
- Phase E — admin.html 에 `<button data-admin-tab="settings">설정</button>` + `<section data-admin-pane="settings">` + admin.js 의 settings pane 핸들러 + `buildSystemPromptEditor({scope:'global'})` 마운트. `buildSystemPromptEditor` 가 scope='global' 일 때 product select hide.
- Phase F — docs (FUNCTION.md system prompt assembly 5 layer 갱신, MODIFY.md CHG-20260521-0003, REVIEW.md REV-20260521-0003, REPORT.md §1 sticky note).
- Phase G — verify-completion.sh `--pre-commit feature-0003-agent-web-ui` + commit + main fast-forward.

**Affected files** (estimate 8): agent_core.py / app.py / admin.html / admin.js / FUNCTION.md / MODIFY.md / REVIEW.md / REPORT.md.

**Risk**: Major §12.3 — 모든 LLM 응답에 영향 (GLOBAL 이 모든 conversation 의 첫 system message). DB row 비정상 시 fallback 상수 보존으로 zero-data state 방지. Audit hook 자연 흡수 (builder 변경 0).

본 cycle 은 PLAN-APPROVED marker 부여 후 즉시 Phase A 진입. 외부 영향 (PR / 배포) 은 별도 confirm.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0095, Major §12.3 — GLOBAL system prompt layer 신설. agent_core.py SYSTEM_PROMPT 상수 본문 → WebSystemPrompts scope='global' 1 row DB 화 + 코드 상수 fallback 유지. RBAC 2건 (`system_prompt.global.read/.write`) admin only. 신규 `설정` 탭 + 내부 sub-section 확장성 패턴. compose_system_prompt() 가 GLOBAL 을 가장 먼저 누적. worktree ai/claude/global-system-prompt 에서 진행, 별도 commit 후 main fast-forward.) -->

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0094, Critical §12.3 — 첨부 multi-cycle A CSV ingest + B DDL/KB + C Vision + D PDF RAG 4 sprint 분리. D1~D21 21 결정 확정 (D14 SQL allowlist guard 통과를 Sprint 1 ship 조건). Codex outside-voice review 2 회 흡수 (REV-20260520-0001 1차 17 Valid + REV-20260521-0002 2차 Critical 3 / Major 11 / Minor 2 → F8 만 사용자 명시 거부, 위험 격리는 D14 + R-Claim4 + R-F4 + D20 조합으로 충족). BRIEFING-attachment-multi-cycle.md Revision 2. worktree ai/claude/0087/attachment-briefing (git worktree 명 유지, 본 cycle TASK-0094) 별도 commit. Sprint 1 implementation 은 별 worktree 분리.) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0085, Minor §12.3 — lazy-create 사이드바 optimistic pending entry (multi-pending sentinel-keyed Map + click swap to sentinel context), "+ 새 대화 송신 직후 다른 대화 전환 시 새 대화 entry 가 사이드바에서 잠시 사라지는" UX 회귀 fix + 사용자 의도 "작업 step 현황의 출력" 지원. worktree ai/claude/0083/pending-list-entry 별도 commit) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0084, Minor §12.3 — D2Coding 우선 monospace stack 으로 전역 통일 재시도. 사용자 후속 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion 응답 "본문 + 코드 모두 (전역 monospace 통일 부활)". CHG-0013 monospace 시도 → CHG-0014 sans-serif 환원 → CHG-0015 D2Coding 우선 부활. worktree ai/claude/task-0084-d2coding 별도 commit) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0083, Minor §12.3 — :root 의 --font 토큰을 한글 가독성 우선 system-ui sans-serif stack 으로 갱신, --mono 는 원래 stack 유지. 사용자 첫 요청 (monospace 통일, CHG-0013 — a7b7ded 흡수) 후 가독성 피드백 받고 sans-serif 환원. worktree ai/claude/task-0083 별도 commit) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0082, Minor §12.3 — lazy-create unique sentinel design (state.pendingSentinel + _newPendingSentinel + closure-aware cleanup), 첫 in-flight 중 + 새 대화 클릭 시 input 비활성 회귀 fix + TASK-0081 stale 가드 자연 흡수) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0081, Minor §12.3 — beginPendingConversation stale flag 회복 가드 + sendPrompt catch 분기 pendingNewConversation cleanup, 두 번째 새 대화 send 차단 회귀 fix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0080, Minor §12.3 — _collect_matched_excerpts AgentMemoryMessages UNION AgentCoreMessages, snippet 부재 회귀 차단) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0079, Minor §12.3 — .chat-pane flex 1 1 auto + min-height 0 layout hotfix, TASK-0066 cascade 잔여 결함) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0078, Minor §12.3 — search modal 3 항목 추가 hotfix of TASK-0077: mouseup race 보강 + preset 텍스트 축약 + snippet line-based clip) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0077, Minor §12.3 — search modal 5 항목 hotfix bundle of TASK-0072/0076: min 2 char + 소유자 facet 제거 + 기간 preset + mouseup race + snippet 본문 excerpt) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0076, Minor §12.3 — search modal UX 3 결함 hotfix bundle of TASK-0072: facet 동작 + 키보드 scroll + 매칭 message jump) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0075, Minor §12.3 — TASK-0072 + TASK-0074 HTTP smoke 실행 결과 §4 기록, append-only) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0074, Minor §12.3 — search modal 색상 가독성 hotfix of TASK-0072, light theme 토큰 정합) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0073, Critical §12.3 — 모든 계정 행위 audit 기능 + 관리 콘솔 조회, CEO review 9 + Codex outside voice 14 findings + redesign 흡수) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0072, Critical §12.3 — 타 계정 대화 검색·필터 + outside voice 보강) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0071, Minor §12.3 — shell grid row hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0070, Minor §12.3 — admin list-detail grid row hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0069, Minor §12.3 — admin workspace flex hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0068, Minor §12.3 — admin layout 정합) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0067, Minor §12.3 — 제품 칩 composer 이전) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0066, Minor §12.3 — UI layout 재구조화) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0065, Minor §12.3 — UI 정리 follow-up) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0063, Major §12.3) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-15 -->
- [x] TASK-0085 (REQ-20260519-0014, Minor §12.3 — lazy-create 사이드바 optimistic pending entry) 사용자 직접 요청 — "+ 새 대화 에서 요청을 보내면, 해당 대화가 사용자 입장에서(웹브라우저에서) 즉시 활성화된 대화 객체로 받아들이도록 구성" + "현재는 + 새 대화 에서 요청 후 다른 대화로 전환할 때, 이전에 요청한 신규 대화가 잠시동안 목록에서 사라지는 이슈" + click UX 결정 "대화 내부 진입도 가능하도록 구성해주세요. 작업 step 현황의 출력을 위해서입니다". 원인: TASK-0048 lazy-create 패턴에서 frontend 가 backend `/api/ask` 응답 도착 전까지 conversation_id 미발급 → `state.conversations` (사이드바 list) 에 신규 entry 없음 → 사용자가 다른 대화로 전환 시 `appendPendingItem` placeholder + backend list 둘 다 새 entry 없음 → 사이드바 완전 소실 구간 발생. Design: multi-pending sentinel-keyed `state.pendingConversationEntries` Map 추가. lazy-create 진입 시 entry add + 사이드바 즉시 표시. closure-aware cleanup (성공·실패 모두 자기 sentinel entry 만 remove — TASK-0082 unique sentinel design 정합). 신규 `appendInFlightPendingItems()` + `_switchToPendingConversationContext(entry)` helper. 응답 도착 + refreshWorkspace 시점에 실 cid entry 등재 → optimistic entry 자연 swap. 클릭 시 sentinel 컨텍스트로 swap + pendingBubble 복원 → 응답 도착 시 closure 일치로 자동 cid binding + startProgressPolling 시작. multi-pending 동시 진행 시 각 sentinel 분리 보존. 변경 5 영역 (state field line 120 추가, sendPrompt 진입 line 3596 + success line 3685 + catch line 3705, renderConversationList line 1209~1450 의 hasPending split + appendInFlightPendingItems + combinedPrepend, `_switchToPendingConversationContext` helper line 3100~). cache-bust `v=20260519-unique-sentinel` → `v=20260519-pending-entries`. backend / RBAC / endpoint / audit / DB 무변경. node --check PASS. 회귀 시나리오 5 종 (송신 직후 다른 대화 전환 → entry 사이드바 지속 표시 / 응답 도착 → 자동 cleanup + 실 cid 등재 / catch → "전송 실패" 3 s 후 cleanup / pending entry click → 컨텍스트 swap + pendingBubble 복원 + 자동 cid binding / multi-pending 분리 보존). worktree `ai/claude/0083/pending-list-entry` 격리 → main ff-merge.
- [x] TASK-0084 (REQ-20260519-0013, Minor §12.3 — D2Coding 우선 monospace stack 으로 전역 통일 재시도) 사용자 후속 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion 응답 "본문 + 코드 모두 (전역 monospace 통일 부활)". 흐름: CHG-0013 monospace 시도 → CHG-0014 한글 가독성 호소로 sans-serif 환원 → CHG-0015 D2Coding (NAVER 한글 monospace 가독성 검증) 우선으로 monospace 통일 부활. `:root` 의 `--font` / `--mono` 두 토큰을 단일 D2Coding 우선 monospace stack 으로 통합 (`"D2Coding", "D2Coding ligature", "Cascadia Code", "SFMono-Regular", Consolas, "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace`) + `--font: var(--mono)` 참조. admin.html cache-bust `v=20260519-cjk-readable` → `v=20260519-d2coding-mono`. index.html cache-bust 미갱신 (TASK-0083 과 동일 — 사용자 main wt revert 의도 존중). CHG-0015 / REV-0011 / AC-0187 등록. main wt 가 다른 AI 작업자의 merge conflict (UU) 상태로 멈춰 있어 worktree `ai/claude/task-0084-d2coding` 별도 commit + main fast-forward push.
- [x] TASK-0083 (REQ-20260519-0011 + REQ-20260519-0012, Minor §12.3 — web UI typography stack 갱신: 한글 가독성 우선 system-ui sans-serif) 사용자 두 번 요청 — (1) 첫 요청 "프로젝트로 실행되는 웹브라우저 내에서 출력되는 폰트를 monospace로 변경하여 문자열 길이와 실제 표현되는 위치가 정합" → 본 cycle 의 첫 시도로 `:root` 의 `--font` / `--mono` 를 monospace stack 으로 통합 (CHG-0013 — 다른 AI 작업자의 a7b7ded commit 에 docs 변경만 흡수됨, src 변경은 본 worktree 로 분리). (2) 사용자 후속 보고 "한글 기준으로 눈이 아픕니다… 한글 기준으로 가장 범용성있는 폰트로 다시 설정해주세요" → 본 cycle 의 최종 결정으로 monospace 통합 방향 폐기 + `--font` 를 한글 친화 sans-serif stack 으로 변경 (`system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "맑은 고딕", "Helvetica Neue", Arial, sans-serif`). `--mono` 는 원래 stack 복원 (`"Cascadia Code", "SFMono-Regular", Consolas, monospace`), `var(--mono)` 명시 사용처 (코드/로그 영역) 는 monospace 유지. admin.html cache-bust `v=20260518-shell-grid-rows` → `v=20260519-cjk-readable`. index.html cache-bust 미갱신 (사용자 main wt revert 의도 존중 — 사용자 hard refresh 권장). CHG-0014 / REV-0010 동시 기록. 다른 AI 작업자의 main wt 영역과 격리된 worktree `ai/claude/task-0083` 에서 commit + main fast-forward push.
- [x] TASK-0082 (REQ-20260519-0010, Minor §12.3 — lazy-create unique sentinel design) 사용자 직접 보고 followup of TASK-0081 — "대화 요청을 보낸 후, + 새 대화 버튼을 클릭한 후에도 요청 텍스트 입력칸이 활성화되지 않는 이슈". 원인 (TASK-0081 보다 근본): 글로벌 단일 `PENDING_CONV_SENTINEL = "__pending__"` 토큰이 첫 lazy-create in-flight 시 busyConversations 에 점유 → 두 번째 + 새 대화 진입 후에도 `isCurrentConvBusy()` 가 same sentinel 검사로 true 반환 → `renderComposer()` 가 `promptInputEl.disabled = true` 그대로 → input 활성화 안 됨. 추가로 TASK-0081 의 guard 분기는 첫 대화 in-flight 중 + 새 대화 클릭 시 early return + renderComposer 미호출이라 input.disabled state 가 갱신되지 않는 부수 결함도 발생. Design: 각 lazy-create 진입마다 unique sentinel 부여 (`state.pendingSentinel` + `_newPendingSentinel()` helper). closure 로 각 sendPrompt 가 자기 sentinel 만 cleanup → 두 번째 대화 컨텍스트의 state 보존. TASK-0081 의 stale flag 회복 가드는 본 design 에서 자동 흡수 (각 호출이 새 sentinel reset). 변경 5 군데 (state 정의 line 115, helper line 156 부근, isCurrentConvBusy line 333~339, beginPendingConversation line 2993~3014, sendPrompt busyKey line 3458~3475 + success cleanup line 3522~3539 + catch cleanup line 3537~3551). cache-bust `v=20260519-pending-recovery` → `v=20260519-unique-sentinel`. backend / RBAC / endpoint / audit / DB 무변경. node --check PASS. 회귀 시나리오 4 종 (in-flight 중 + 새 대화 → input 활성화 + 두 번째 send 정상 / catch 후 + 새 대화 → 정상 / 응답 후 + 새 대화 → 정상 / pending bubble error 표시 보존).
- [x] TASK-0081 (REQ-20260519-0009, Minor §12.3 — `beginPendingConversation` stale flag 회복 가드 + `sendPrompt` catch 분기 `pendingNewConversation` cleanup) 사용자 직접 보고 — 웹 UI 에서 새 conversation 만들고 첫 요청 송신 후, 다시 "+ 새 대화" 로 별개 conversation 진입해 send 시도하면 두 번째 send (요청 UI 버튼, Ctrl+Enter) 가 무동작. 원인: `app.js` 의 (a) `beginPendingConversation()` 의 early return 가드가 `state.pendingNewConversation === true` 만 검사 — 첫 lazy-create send 가 catch 분기 (network/timeout) 로 종료된 경우 flag cleanup 누락 → stale state → 두 번째 "+ 새 대화" 클릭이 입력란 포커스만 잡고 return → `state.activeConversationId = ""` reset 도 안 됨 → `sendPrompt()` 의 `isCurrentConvBusy()` 가 `pendingNewConversation=true && busyConversations.has(sentinel)` 검사에서 sentinel 잔존 여부와 무관하게 새 대화 진입 가드에 막힘. (b) catch 분기 (line 3536 부근) 가 `state.pendingNewConversation` 을 cleanup 하지 않음. Fix 2 군데 — (a) `beginPendingConversation()` 의 가드 조건을 `pendingNewConversation && busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘 → 첫 send 가 실제 in-flight 일 때만 진입 보류, stale state 면 통과해 정상 reset 흐름으로 진입. (b) `sendPrompt()` catch 의 isLazyCreate 분기 진입 시점에 `state.pendingNewConversation = false` 명시 cleanup. backend / RBAC / endpoint / audit / DB 무변경. node --check PASS. cache-bust `v=20260519-chat-pane-flex` → `v=20260519-pending-recovery`. 회귀 시나리오 5 종: ①정상 첫 송신 후 두 번째 새 대화 진입 + send → 통과 (sentinel 잔존 0, guard 통과), ②첫 송신 timeout 에러 후 두 번째 새 대화 → catch 의 `pendingNewConversation=false` cleanup + 새 진입 정상, ③첫 송신 in-flight 중 사용자가 "+ 새 대화" 클릭 → guard 가 sentinel 존재 검사로 진입 보류 (의도적 — 같은 sentinel 중복 race 방지), ④AC-0077 의 pending bubble error 표시는 cleanup 과 무관 (`state.pendingBubble` 별도 state), ⑤AC-0072~0077 lazy-create 정상 흐름 무영향 (success path 의 line 3522 `pendingNewConversation = false` 그대로 유지).
- [x] TASK-0080 (REQ-20260519-0008, Minor §12.3 — `_collect_matched_excerpts` 의 AgentMemoryMessages + AgentCoreMessages UNION) TASK-0077 의 followup. 사용자 직접 확인 — `excerpt 의 AgentCoreMessages 포함 (UNION)` 미해결. TASK-0072 `_list_conversations` search EXISTS subquery 는 두 table 모두 검사하나 TASK-0077 의 excerpt 추출은 `AgentMemoryMessages` 한정이라 *core 에만 message 있는 conv* 는 search 결과 list 에 포함되어도 snippet 비어 있던 회귀. Fix: backend `_collect_matched_excerpts` 의 SELECT 를 UNION ALL 로 두 table 모두 매칭 message 후보 모음 → `ROW_NUMBER() OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. msg_id 의 두 table namespace 차이는 더 큰 id = 더 최근 (시간 monotonic) 가정. `ConversationId` 의 collation mismatch 회피 위해 `COLLATE utf8mb4_unicode_ci` 통일. cache-bust `v=20260519-snippet-line` → `v=20260519-chat-pane-flex`. RBAC / audit / endpoint contract / line-based clip 로직 무변경.
- [x] TASK-0079 (REQ-20260519-0007, Minor §12.3 — `.chat-pane` flex layout hotfix, TASK-0066 cascade 잔여 결함) 사용자 screenshot 보고 — 짧은 대화 + 큰 viewport 조합에서 composer 아래로 viewport bottom 까지 회색 빈 영역 노출. 원인: `.chat-pane { display: flex; flex-direction: column; overflow: hidden; background: var(--bg); }` 만 정의 + `flex: 1` 누락 → `.chat-column` flex container 안에서 자식 max-content 만 차지. `.messages-wrap { flex: 1 }` 이 chat-pane 안에서 grow 하려면 chat-pane 자체가 column 의 남은 영역 차지 필요. TASK-0066 ChatGPT 패턴 layout 재구조화 시점 누락 (TASK-0068~0071 cascade hotfix chain 은 admin 영역만 다뤘고 작업 화면의 chat-pane 은 미적용). Fix: `.chat-pane` 에 `flex: 1 1 auto; min-height: 0` 추가 (CSS 2 line). 다른 속성 무변경. backend / RBAC / endpoint / JS 무변경. node --check / py_compile 대상 변경 없음.
- [x] TASK-0078 (REQ-20260519-0006, Minor §12.3 — search modal 3 항목 추가 hotfix of TASK-0077) 사용자 직접 테스트 보고 3 항목: (1) **mouseup race 보강** — TASK-0077 의 mousedown-only 추적이 부족한 edge case 발견. modal 바깥 mousedown → modal 안 mouseup 일 때도 close 됨 (click 의 target 이 mousedown + mouseup 의 공통 ancestor 인 overlay 가 되는 경우). Fix: `state.searchModal.mouseupOnOverlay` 도 추가 추적, `overlay.click` 시 `mousedownOnOverlay + mouseupOnOverlay + ev.target === overlay` 3 개 모두 true 일 때만 close. 즉 의도적인 backdrop click (양 끝점 모두 backdrop) 만 close 트리거. (2) **preset 텍스트 "부터" 제거** — "1시간 전부터" → "1시간 전" 5 버튼 모두. 사용자 결정 (버튼 크기 간소화 / 접근성). data-preset-hours 데이터 속성 무변경. (3) **snippet 본문 발췌 line 출력** — TASK-0077 의 `_collect_matched_excerpts` 가 매칭 위치 ±40 char clip 으로 multi-line 의 일부만 cut 됐었음. Fix: 매칭 위치의 line 경계 (`\n` 직후 ~ `\n` 직전) 를 찾아 *line 전체* 를 excerpt 로 반환. line 이 매우 길 경우 (>220 char) 만 매칭 위치 ±60 char clip + "…". `.search-snippet` CSS 의 `-webkit-line-clamp` 2 → 3 + `line-height: 1.45` + `max-height: 4.6em` 으로 시각 line clip 도 완화. backend / RBAC / audit / endpoint contract 무변경. cache-bust `v=20260519-search-presets` → `v=20260519-snippet-line` (styles.css + app.js). py_compile + node --check PASS + make web 재배포.
- [x] TASK-0077 (REQ-20260519-0005, Minor §12.3 — search modal 5 항목 hotfix bundle of TASK-0072/0076) 사용자 직접 테스트 보고 5 항목 모두 반영: (1) **min char 3 → 2** — backend `_normalize_search_query` 의 raw-len gate 3 → 2 (한국어 grapheme 2 char 도 의미 있는 검색어). frontend `runSearchQuery` / `_searchHighlight` / `renderSearchModalResults` empty state / `_jumpToSearchMatchedMessage` 모두 정합 갱신. (2) **소유자 facet 제거** — DOM (`#searchFacetOwner`, `#searchOwnerPopover`, `#searchOwnerList`) + JS (`_loadOwnerAccountsForSearch` / `_openOwnerPopover` / `state.searchModal.owner_id` / `owner_username` / `ownerAccountsCache`) 전부 제거. backend `_list_conversations` 의 `owner_id` 파라미터 자체는 호환 위해 유지 (다른 caller 영향 0) — frontend 가 쿼리에 안 보냄. (3) **기간 preset 5 종** — popover 안 preset row 신설 (1시간/1일/1주/1개월/1년 전부터 지금까지). click 시 from/to 자동 채움 + popover input sync + 적용 + runSearchQuery. preset hours 는 `data-preset-hours` 데이터 속성 (1/24/168/720/8760). (4) **mouseup race fix** — backdrop close 가 사용자 modal 안 text drag → backdrop 위 mouseup 시 trigger 되던 문제. `overlay.mousedown` 시 `state.searchModal.mousedownOnOverlay = (ev.target === overlay)` 기록, `overlay.click` 시 `mousedownOnOverlay && ev.target === overlay` 둘 다 true 일 때만 close. (5) **snippet 본문 excerpt** — backend `_collect_matched_excerpts(conn, conv_ids, q)` helper 신설 (MySQL 8.0 `ROW_NUMBER() OVER (PARTITION BY ConversationId ORDER BY Id DESC)` 으로 conv 별 최근 매칭 message 1건, content 의 매칭 위치 ±40 char clip + "…" prefix/suffix). endpoint 가 `matched_excerpts: {conv_id: "...본문..."}` 응답에 첨부. frontend `runSearchQuery` 가 state 에 캐시, `renderSearchModalResults` 의 snippet 영역이 topic 대신 excerpt + `_searchHighlight` highlight. cache-bust `v=20260519-search-facets` → `v=20260519-search-presets`. backend matched_excerpts 는 본 cycle 의 신규 PII 표면 *아님* — TASK-0072 의 snippet opt-in chip + WebAccountActivity audit 정책 그대로. py_compile + node --check PASS + make web 재배포 OK.
- [x] TASK-0076 (REQ-20260519-0004, Minor §12.3 — search modal UX 3 결함 hotfix bundle of TASK-0072) 사용자 직접 테스트 보고 3 항목: (1) facet click 무동작 (소유자/제품/기간) — 본 cycle: 제품 facet 은 사용자 명시 결정 ("대화 중 product 변경 가능 → 필터 대상 부적합") 으로 DOM 제거, 소유자 facet 은 `/api/admin/accounts` 캐시 + popover (.any 한정), 기간 facet 은 `<input type="date">` from~to popover + 적용/지우기. backend `_list_conversations` 가 `owner_id`/`date_from`/`date_to` 파라미터 이미 지원 (Phase A1) — frontend popover 만 신설. (2) ArrowUp/Down 시 화면 범위 초과 시 scroll 미동작 — active row 의 `scrollIntoView({block:'nearest'})` ArrowDown/ArrowUp 핸들러 + Enter 동일 적용. (3) 검색 결과 click 시 conv 전환은 OK 이나 매칭 message bubble 로 jump 안 함 — result click / Enter 시 `state.searchModal.pendingJumpQuery = q` + `pendingJumpConvId` 저장, `selectConversation` 끝 (loadHistory + renderMessages 직후) 에 `_jumpToSearchMatchedMessage()` 호출, `messageLogEl` 의 `.message` 중 textContent.toLowerCase().includes(needle) 첫 매칭 row 로 `scrollIntoView({behavior:'smooth', block:'center'})` + `is-search-matched` class 1.8 s pulse animation. backend / RBAC / audit / endpoint 무변경. cache-bust `v=20260519-modal-contrast` → `v=20260519-search-facets`.
- [x] TASK-0075 (REQ-20260519-0003, Minor §12.3 — TASK-0072 + TASK-0074 HTTP smoke 실행 결과 기록) `bootstrap_admin` 1 토큰만 사용한 ad-hoc curl 실행 결과 6/8 PASS (S2 .any cross-account, S4 cursor disjoint, S5 invalid q→400, S6 rate limit 11th→429, S7 DDL idempotent, S8 audit SHA-256 INSERT). S1 (.own no leak) / S3 (byte-equal owner_id) 는 operator (`review_user01`) pw 미보유로 skip — `_list_conversations` 의 has_any 분기 + endpoint 의 effective_owner_id 강제 overwrite 코드 review 로 검증됨. `docs/TEST.md §4 Test Run History` 에 append. backend / RBAC / endpoint / audit 무변경.
- [x] TASK-0074 (REQ-20260519-0002, Minor §12.3 — search modal 색상 가독성 hotfix of TASK-0072) 사용자 screenshot 보고: TASK-0072 의 Spotlight modal 이 light theme (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 환경에서 어두운 배경 + 검은 텍스트로 노출 — "사용자가 이용할 수 없을 정도의 색상 구성". 원인: modal CSS 가 미정의 var (`--text-primary`, `--bg-elev`) 의 hardcode dark fallback (`#1f2429`) 으로 배경을 잡았고, 텍스트는 site 의 `--text` (zinc-900) inherit → 어두운 배경 위 검은 텍스트 = 가독성 0. Fix: modal block ~100 줄을 site 의 기존 토큰 (`--surface`, `--text`, `--text-2`, `--text-muted`, `--border`, `--primary`, `--primary-soft`, `--bg`) 으로 일관 적용. backdrop 의 dark overlay (`rgba(15, 23, 42, 0.48)`) 는 modal pop 강조 유지. snippet 배경 = `--bg`, result row hover/active = `--primary-soft`, owner badge = bg + border + color triple, highlight bg `#fde68a` + bold (light theme contrast). RBAC / endpoint / audit / backend 무변경. cache-bust `v=20260518-conv-search` → `v=20260519-modal-contrast` (styles.css + app.js 양쪽). 검증: make web 재배포 + 컨테이너 12 초 후 healthy. node --check / py_compile 대상 변경 없음.
- [x] TASK-0073 (REQ-20260519-0001, **Critical** §12.3 — 모든 계정 행위 audit + 관리 콘솔 조회) 본 cycle Phase A1~D 완료, Phase E 외부 영향 검증은 사용자 위임 (sandbox SSH 인증 차단). CHG-20260519-0017~0025, REV-20260519-0013~0021. 8 commit (`bf21886` A1 / `88d6fa4` A2 / `2e45cb4` A3 / `e21ab15` A4 / `4ed5f0d` A5 / `5f42ba6` A6 / `c801104` B / `2ddf9b5` C / `58c32e9` D) on `ai/claude/0073/agent-audit` worktree. sub-progress:
  - [x] Phase A0 — DDL + bootstrap (`_ensure_web_audit_events_schema` + WebAuditEvents 14 columns + 5 indexes + fast/slow path hook). CHG-20260519-0003. 2026-05-19. py_compile PASS.
  - [x] Phase A1 — dispatcher + `AGENT_AUDIT_ENABLED` gate (CHG-20260519-0017, 2026-05-19, py_compile + bash -n PASS; verify-completion check_11_audit_dispatcher 신설)
  - [x] Phase A2 — WebAccountActivity 흡수 + migration helper (CHG-20260519-0018, 2026-05-19, py_compile PASS; idempotent SQL marker `RequestId='account-activity:<id>'` + dual write `_log_search_activity`)
  - [x] Phase A3 — RBAC catalog +4 + dba seed + permission group `audit` (CHG-20260519-0019, 2026-05-19, py_compile PASS; SEED + 4 catchup loop admin/operator/sales/dba/pending 자동 backfill)
  - [x] Phase A4 — 5 audit endpoint + chunked purge (CHG-20260519-0020, 2026-05-19, py_compile PASS; .own SQL filter Actor OR Target + 50k CSV hard cap + 1000-row chunked purge w/ idempotency_key 30s deadline)
  - [x] Phase A5 — admin 11 endpoint hook (Same tx) + ActionCode 별 build_audit_change_json builder (CHG-20260519-0021, 2026-05-19, py_compile PASS; 11 endpoint = update/delete/password-reset/role CRUD/product CRUD/databases.update/system_prompt.update — plan 의 "13" elastic 표현, 11 이 admin mutation 전부; E5 product delete cascade lock 순서 정합)
  - [x] Phase A6 — user 5 endpoint hook (fail-open) + anonymous share view (CHG-20260519-0022, 2026-05-19, py_compile PASS; _audit_user_action helper + ActorType='anonymous' for public share view + token_prefix 8 char redact)
  - [x] Phase B — 3 test 파일 신설 (CHG-20260519-0023, 2026-05-19, py_compile PASS; test_audit_dispatcher 7 시나리오 + test_audit_rbac 10 시나리오 + test_audit_migration 3 시나리오; 실 실행은 컨테이너 환경 + admin/operator 자격 필요, Phase E 위임)
  - [x] Phase C — Frontend (admin 탭 + filter + detail pane + CSV) (CHG-20260519-0024, 2026-05-19, node --check PASS; admin.html 새 탭 + filter row 7항목 + list-detail / admin.js loadAuditList + render + escape HTML / styles.css 10+ class / app.js + admin.js PERMISSION_GROUP_ORDER 'audit' + cache-bust v=20260519-audit-tab 4 곳)
  - [x] Phase D — 프로젝트 수준 docs (SECURITY §9 + DECISIONS ADR-0019 + ARCHITECTURE §4·§6 + CONVENTIONS §10.6 + STATUS feature-0003 row + REPORT §1 + TEST §2.1) (CHG-20260519-0025, 2026-05-19; SECURITY §8 은 TASK-0072 점유 → §9 신설로 정합 + plan 본문 의도 보존)
  - [x] Phase E — verify-completion + Completion Checklist + 최종 commit (CHG-20260519-0026, 2026-05-19; 본 cycle TASK-0073 [x] 마킹). 외부 영향 (make web 재배포 + browser headless smoke + AGENT_AUDIT_ENABLED=0/prod startup fail 검증 + WebAccountActivity migration SQL count 검증) 은 sandbox SSH 인증 차단으로 사용자 위임 — 8 commit 모두 `ai/claude/0073/agent-audit` worktree 의 local 누적.

  사용자 in-cycle 결정 (CEO review 9 항목 + Codex outside voice 14 findings 흡수 후 Major redesign): Mode=HOLD SCOPE, Scope=Approach B (admin + 대화·SQL·share·search), Storage=DB-only (`WebAuditEvents` 365일 retention + chunked PK purge), Hook=Web-ui split (admin 13 endpoint = direct dispatcher + Same tx / user 4 endpoint = best-effort delegate + fail-open, TASK-0072 패턴 답습), MySQL log=별 cycle 분리 (slow_query_log 본 cycle 제외), RBAC=`audit.read.own` + `audit.read.any` + `audit.export` + `audit.purge` 4건 (.own 은 dba 포함 모든 role 자동 grant, .any 는 admin/dba) + permission group `audit` 신규 + CONVENTIONS.md §10.6 동시 갱신, Tx=split (admin Same tx fail-safe / user fail-open), Masking=Action-specific allowlist builder (raw request 검증 X, ActionCode 별 명시 화이트리스트, free-text PII explicit redact/hash), Flag=`AGENT_AUDIT_ENABLED` prod (`AGENT_MODE!=dev/test`) startup fail-closed + dev/test toggle, WebAccountActivity 흡수 (TASK-0072 PIPA §29 1년 retention inherit, ActionCode `conversation.search.any` / `conversation.snippet.any` mapping, `_log_search_activity` 는 새 dispatcher 의 user best-effort path 로 wrap). 상세 plan 은 §2.1 Implementation Plan (TASK-0073). **상태**: `approved-after-outside-voice` — CEO review 9 decision 확정 → Codex outside voice 14 findings + 6 minimum-fix dispatch → 9 decision 중 5 reset (Storage·MySQL log·Hook·Tx·Masking) → redesign 사용자 확정 (2026-05-19). **사용자 메모리**: `feedback_outside_voice_for_rbac` 정책 강제 적용 (Critical RBAC + audit 표면 신설).
- [x] TASK-0072 (REQ-20260518-0010, **Critical** §12.3 — 타 계정 대화 검색·필터) **DEPLOYED**. 사용자 in-cycle 결정 3 항목 ((1) 권한 = 기존 `conversation.list.any` 재활용, (2) 검색 범위 = 제목 + 계정명 + 메시지 본문, (3) UI = Spotlight modal Cmd/Ctrl+K) 합의 후 outside voice 3 review (security FIX-FIRST / adversarial Blocker + 3 sub-spec + 6 risk / ux NEEDS-TWEAK) 모두 흡수. 3 sub-spec (SQL composition order strict / hidden_ids SQL push / Python re-sort 삭제 + SQL ORDER BY 단일화) + 안전망 (LIKE ESCAPE '!' + min 3 char + LIMIT 50 + rate 10/min + max_execution_time 3s + DeletedAt + collation audit + owner.Username .any 한정) + audit (SHA-256 hash, 평문 X, PIPA §29) + cursor pagination 적용. 상세 plan-review 는 §2.1 Implementation Plan (TASK-0072) PLAN-APPROVED 마커. **Main 통합 commits**: `f298f90` (feat TASK-0072 본체) + Post-deploy hotfix bundle `e7fd926` (TASK-0074 light theme) / `c803134` (TASK-0076 search modal UX 3) / `cfbb8c5` (TASK-0077 5 hotfix) / `1e2e52d` (TASK-0078 3 hotfix) / `e7b9805` (TASK-0079+0080 flex + UNION). 본 closure 는 TASK-0099 (audit followup backlog tracker hygiene) cycle 에서 수행 (2026-05-22).
- [x] TASK-0071 (REQ-20260518-0009, Minor §12.3 — shell grid row hotfix, cascade root of TASK-0068~0070) 사용자 3 차 screenshot 보고: dashboard pane 처럼 list-detail 사용 안 하는 화면에서 큰 viewport + 짧은 content 조합 시 sidebar / commit-bar 가 viewport 의 약 70% 위치까지만 차지 + 그 아래 회색 빈 영역. 원인: `.app-shell` / `.admin-shell` 의 `display: grid; height: 100vh` 만 정의 + `grid-template-rows` 미정의 → default `auto` → row track height = 자식 max-content. grid container 100vh 와 track height 의 mismatch 시 track 아래 빈 영역. 이전 cycle 의 fix 들은 column 안의 stretch chain 만 해결, column 의 height 결정 layer (grid track) 미처리 = cascade 의 root. Fix: `.app-shell` 과 `.admin-shell` 양쪽에 `grid-template-rows: minmax(0, 1fr)` 추가 (2 줄, 동일 패턴 일관성). 검증: 1320x900 viewport 에서 admin-shell h=900, column h=900, commit-bar bottom=900 (viewport bottom 정확히 sticky). screenshot 첨부. cache-bust `v=20260518-shell-grid-rows` (admin.html / index.html 양쪽 동일).
- [x] TASK-0070 (REQ-20260518-0008, Minor §12.3 — admin list-detail grid row hotfix of TASK-0069) 사용자 2 차 screenshot 보고: `역할` / `제품` 등 항목이 적은 pane 에서 큰 viewport (height 800+) 의 경우 list-col / detail-col box 가 viewport 의 일부만 차지하고 그 아래 회색 빈 영역. 항목이 많은 `계정` (26 row) 또는 좁은 화면에서는 content 가 row 채워 정상. 원인: `.admin-list-detail` 의 grid-template-rows 미정의 → default auto → row height = content. align-items: stretch 는 row 내부 column 분배만 담당 — row 자체 height 결정 X. Fix: `grid-template-rows: minmax(0, 1fr)` 추가 (1 줄). 검증: 큰 viewport (1320x900) 에서 listDetail h=682, listCol/detailCol h=682 (이전 ~200), cbar viewport bottom sticky. screenshot 첨부. cache-bust `v=20260518-admin-list-rows`.
- [x] TASK-0069 (REQ-20260518-0007, Minor §12.3 — admin workspace flex hotfix of TASK-0068) 사용자 screenshot 보고: admin `역할 관리` (및 다른 list-detail pane) 에서 commit-bar 가 workspace content 바로 아래에 좁게 위치하고 그 아래로 큰 회색 빈 영역. 원인: TASK-0068 에서 commit-bar 를 admin-shell grid → admin-column flex column item 으로 이전한 후 `.admin-workspace` 의 `flex: 1` 명시 누락 → flex column 안에서 workspace 가 자기 content 만큼만 차지. Fix: `.admin-workspace` 에 `flex: 1 1 auto` 추가 (1 줄). 다른 속성 무변경. 검증: DOM `wsBottom=659 / cbarTop=659 / commitBarAtBottom=true / workspaceTouchesCommitBar=true` → list-detail 이 column 의 남은 height 전부 차지 + commit-bar viewport bottom sticky. screenshot 첨부. cache-bust `v=20260518-admin-workspace-flex`.
- [x] TASK-0068 (REQ-20260518-0006, Minor §12.3 — 관리 콘솔 layout 정합 + 미사용 버튼 정리) TASK-0066 / 0067 follow-up. 사용자 명시 — 관리 콘솔의 사이드바 구성을 작업 화면과 동일하게 (ChatGPT 패턴, sidebar 전체 height + admin-column) 정렬. 사용자 직접 테스트에서 거의 사용 안 되는 `새로고침` / `로그아웃` 버튼 제거. `.admin-shell` grid 가 2-row → 2-column (sidebar 220 | admin-column 1fr). `.admin-body` wrapper 폐기. `.sidebar-brand` (작업 화면과 동일 brand "MySQL AI") 가 `.admin-sidebar` 의 첫 영역. `.admin-column` (flex column) 안에 topbar (관리 콘솔 제목 좌측 정렬 + 부제 + "작업 화면" 버튼 우측) + workspace + commit-bar. `#refreshAdminBtn` / `#adminLogoutBtn` element + JS click handler 모두 제거 — 로그아웃은 작업 화면 프로필 drawer 에서 가능 (기능 손실 없음). 검증: DOM `refreshBtnPresent=false / logoutBtnPresent=false / backBtnPresent=true / brandInSidebar=true / adminColumnPresent=true / gridCols="220px 1060px"`. backend / RBAC / endpoint / 데이터 무변경. cache-bust `v=20260518-admin-layout`.
- [x] TASK-0067 (REQ-20260518-0005, Minor §12.3 — 제품 칩 composer 이전 + native select → custom drop-up dropdown) TASK-0066 follow-up. 사용자 명시 — ChatGPT 의 모델 선택 UI 패턴으로 제품 칩을 사이드바 → composer 의 textarea 우측 (sendBtn 직전) 으로 이전. 클릭 시 drop-up dropdown 으로 옵션 표시. 사이드바도 채팅 영역처럼 확장 효과. `.sidebar-head .product-chip-wrap` 제거, `.composer-box` 안에 `.composer-product-chip-wrap` (button#productChip + #productDropupMenu) 신설. 기존 native `<select id="productSelect">` 제거 → custom button + custom menu (drop-up 보장 위해). renderProductChip 재작성 + renderProductDropupMenu / buildProductDropupItem / openProductDropup / closeProductDropup 신설. backend endpoint `PATCH /api/conversations/{cid}/product` 호출 / setActiveProduct 본체 / RBAC / 데이터 영역 무변경. 검증: DOM `chipInComposer=true`, 기존 native select 부재, sidebar-head 가 "새 대화" 만, chip click → menu 4 items (auto + KR + MV + GZ_KR) 표시 + `dropUp=true` (menuY < chipY), KR item click → chip label "KR" + toast "제품을 킹스레이드로 바꿨어요" 정상. cache-bust `v=20260518-product-composer`.
- [x] TASK-0066 (REQ-20260518-0004, Minor §12.3 — ChatGPT 패턴 layout 재구조화) TASK-0065 follow-up. 헤더 4 버튼 제거로 비어 보이던 `.chat-header` 와 `.topbar` (관리 콘솔) 영역을 통합. 사용자 결정 (in-cycle 명시): topbar 에 대화 제목 통합 + 좌측 정렬 (중앙 정렬 금지) + brand `[MA] MySQL AI` 를 sidebar 영역으로 이전 (ChatGPT UI 패턴). `.app-shell` grid 를 row 2개 → column 2개 (sidebar | chat-column) 로 단순화. `.app-body` wrapper 폐기. `.sidebar-brand` 신설 (sidebar 첫 영역, height = topbar-h 로 baseline 정렬). `.chat-column` 신설 (topbar + chat-pane wrapper). `.chat-header` 폐기 — 채팅 영역 확장. `.topbar-info` (제목/부제 좌측 정렬) + `.topbar-tools` (loadMoreBtn) + `.topbar-end` (관리 콘솔 우측). 반응형 mobile (max-width: 680px) 분기도 정렬. JS 변경 0 — 모든 element ID 보존. backend / RBAC / endpoint / 데이터 영역 무변경. 검증: DOM `.app-shell.gridTemplateColumns = "252px 1028px"`, `.sidebar-brand` mount, `.topbar.height = 52px`, 기존 `.chat-header` DOM 부재. browser screenshot 으로 ChatGPT 패턴 정확 구현 확인.
- [x] TASK-0065 (REQ-20260518-0003, Minor §12.3 — UI 정리 follow-up of TASK-0063) 사용자 직접 테스트 피드백 3 항목: (1) 헤더의 "대화 복사 / 공유 / 제목 변경 / 삭제" 4 버튼이 좌측 conv-item "···" menu 와 중복 → 헤더에서 제거 (cancel/finalize 만 유지). (2) "···" trigger 우측 상단 위치가 conv-item 의 "내/sales" badge 와 시각 충돌 → 우측 하단 (`bottom: 6px; right: 6px`) 으로 이전, `.conv-item` 에 `padding-right: 32px` 보정. (3) 캘린더 시간 이동 trigger 가 분기선 click 인데 사용자가 분기선까지 미리 scroll 해야 하는 불편 → Slack 패턴으로 분기선에 `position: sticky; top: 0` 적용 — 현재 시야의 날짜 그룹 헤더가 항상 messageLog 상단에 stick. hover affordance 는 기존 색상 변경 유지 + box-shadow 로 elevation 강화. backend / RBAC / endpoint 변경 0. 검증: node --check + make web 재배포 + browser headless smoke (헤더 4 버튼 부재 / trigger DOM position 확인 / `scrollTop = 600` 시 sticky 분기선 viewport 상단 stay screenshot).
- [x] TASK-0063 (REQ-20260518-0001, **Major** §12.3 — RBAC catalog 확장 2 + 신규 endpoint 1 + 파괴적 액션 menu 통합) 작업 화면 대화 항목별 "···" menu (복사 / 공유 / 제목 변경 / 삭제) + 캘린더 시간 이동을 채팅 로그 날짜 분기선 click trigger 로 이전. ChatGPT / Slack UX 패턴. 사용자 in-cycle 결정 4 항목: (1) 복사 = full self-fork (`_fork_conversation_impl` 재활용), (2) 신규 권한 `conversation.duplicate.own/.any` 분리 추가, (3) 헤더 share 유지 (dual entry), (4) 헤더 calendar 제거 + 분기선 단일 trigger + popover header ‹ › « » nav (« » 는 데이터 1년 이상일 때만). Codex outside voice review 10 risk 보강 (catchup loop 일반화, share-token bypass 차단 = read-gate 명시, 404 metadata leak 차단, .any superset semantics, frontend hide-vs-disable = rename/delete pattern 채택, PERMISSION_LABELS/DESCRIPTIONS/requiredPermissionsFor 3 곳 갱신, grapheme-safe 사본 제목). Catchup 순서 fix — `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출을 `_ensure_seed_roles` 앞으로 이동 (기존 순서는 _permission_id_map 이 신규 권한 id=0 받아 admin/operator/sales catchup skip). 검증: py_compile + node --check + make web 재배포 + DB 직접 grant 확인 (admin .any+.own / operator .own / sales .own) + browser headless smoke (menu 4 항목 + 분기선 click → popover anchored + 월 nav 동작).
- [x] TASK-0062 (REQ-20260515-0011 / REQ-20260515-0012, Minor §12.3) GOAL 2026-05-15 후속: (1) 내 대화 다중선택 UX 개선 — `.conv-item-checkbox` DOM 제거, Ctrl/Shift modifier 만 다중 선택 허용, 2 개 이상 선택 시에만 bulk bar 표시, 일반 click 은 단일 선택 + `state.conversationSelected.clear()`. (2) Point rail dot 위치를 `messageLog.scrollHeight` 기준 비례 분포로 재배치 — `.message-point-rail` 이 `position: relative`, dot 이 `position: absolute; top: <pct>%; transform: translate(-50%, -50%)`. `layoutMessagePointRail()` 헬퍼가 `renderMessagePointRail` + resize 에서 재계산. 검증: node --check 통과, make web 재배포, browser smoke (single click → 다중 선택 해제 / Ctrl click 2개 → bulk bar 표시 / point rail dot 의 top% 가 message scrollHeight 비례). cache-bust `v=20260515-task-0062`.
- [x] TASK-0061 (REQ-20260515-0003 ~ REQ-20260515-0010, **Major** §12.3 — UI 상태 / auth(비밀번호 초기화) / 파괴적 데이터(bulk delete) 일괄 변경) GOAL.md 8 항목 합본 cycle. **/qa round 2 심층 검증 완료 (2026-05-15, CHG-20260515-0004)** — Phase 4 Point rail dot click smooth scroll + active dot id 갱신, Phase 5 캘린더 월 이동 + day click → 시각 list 모두 정상. Phase 3/6/8 destructive endpoints 는 운영 환경 사용자 명시 시점에 실 호출 검증 권고. round 2 신규 이슈 0 건. 답변 버블 내부 실시간 step 진행 (Phase 1) + 신규 대화 첫 요청 polling 즉시 연결 (Phase 2) + processing 만료 감지 + 붉은 badge (Phase 3) + 우측 Point rail (Phase 4) + 캘린더/시각 이동 (Phase 5) + 관리자 비밀번호 초기화 (Phase 6) + admin select-all 현재 페이지 fix (Phase 7) + 내 대화 Ctrl/Shift bulk delete (Phase 8). 상세 plan-review 는 §2.1 Implementation Plan (TASK-0061). **사용자 승인 요청 시점**: §2.1 Plan 확정 후 Phase 6 (Critical 분면 — 비밀번호 초기화, 인증 모델 영향) 진입 전. Phase 1~5, 7, 8 (Major) 는 plan-review 통과 후 Execute.
- [x] TASK-0060 (REQ-20260515-0002, Minor §12.3) Product별 접근 가능 DB의 실제 스키마/데이터를 분석해 Product scope 시스템 프롬프트를 작성하고, Role detail 의 `전 Product 공통` 프롬프트를 역할명에 맞게 채움. 분석 대상: `KR(킹스레이드)` 접근 DB `dbgame,dblog,dbauth`, `MV(마이크로볼츠)` 접근 DB `account_db,dev_1_1_1_20,have_00,log_v2,global_db`. `log_v2`는 DB는 존재하지만 테이블 0개로 확인. 실제 DB에는 product prompt 2건 + role 공통 prompt 5건(`pending/operator/admin/sales/dba`) upsert 완료. runtime 의 누적 적용은 feature-0002 `compose_system_prompt()` 수정으로 보장.
- [x] TASK-0059 (REQ-20260515-0001, **Major** §12.3 — 사용자 대화 routing 데이터 영역, 인증/인가 모델 무변경) "새 대화" 버튼 누른 후 첫 메시지를 보내도 backend 가 직전 active 대화에 메시지를 추가하는 lazy-create routing 결함 수정. 사용자가 신규 대화 의도로 보낸 첫 메시지가 잘못된 대화 컨텍스트로 귀속되어 발견. **근본 원인**: frontend `beginPendingConversation()` 이 `state.activeConversationId=""` 로 두고 backend row 를 lazy 생성 위임하나 (TASK-0048 정책), `/api/ask` 의 빈 `conversation_id` 경로가 `_resolve_conversation_for_account` → `_repair_current_conversation` 으로 폴백해 `account.last_conversation_id` (직전 대화) 를 반환. frontend 의 "pending = 신규 의도" 가 backend 로 전달되지 않아 "session 초기화 후 직전 대화 이어받기" 와 구분 불가. **Fix Phase A**: frontend `sendPrompt()` 가 `isLazyCreate=true` 일 때 `askBody.lazy_create = true` 를 추가. **Phase B**: backend `_resolve_conversation_for_account(..., force_new=False)` kwarg 추가, `_repair_current_conversation` 의 기존 `force_new` 파라미터로 위임. `/api/ask` 의 빈 `request_conversation_id` 경로에서 `data.get("lazy_create")` 가 truthy 이면 `force_new=True` 호출. **Phase C**: frontend `loadConversations()` 의 `state.activeConversationId` 덮어쓰기에 `!state.pendingNewConversation` 가드 추가 — pending 모드 race 시 직전 대화로 복귀 차단. **Phase D**: MODIFY.md CHG-20260515-0001 + REVIEW.md REV-20260515-0001 기록.

### 2.1 Implementation Plan (TASK-0169)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Critical** 등급 (agent 실행 경계·동시성·크래시 시맨틱 변경) 변경 계획이다. **상태**: `approved-after-outside-voice`. DESIGN-ask-worker.md (ADR-WEB-0004 의 B) 를 정본으로, out-of-process `ask-worker` 실행모델을 구현해 web 재배포/SIGTERM 이 in-flight run 을 죽이는 구조적 한계(TASK-0159/0160/0164 의 양끝 backstop 으로만 완화됐던)를 제거한다. feature-0003(web) + feature-0002(agent-core) 양면. 전 경로 `AGENT_ASK_EXECUTION_MODE` flag 기본 `inprocess` 로 격리 — 기본 동작 무변경.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-06-09 (TASK-0169 ask-worker out-of-process 실행모델, Critical 등급, outside-voice 적대적 리뷰 8건(BLOCKER 3 + MAJOR 4 + MINOR n) 흡수, flag 기본 inprocess shadow→cutover) -->

#### outside-voice 적대적 리뷰가 흡수한 8건 (DESIGN §4 → 하드닝)

DESIGN-ask-worker.md 는 위험을 §4 에 나열했으나 hard 한 것을 해결하지 않음 → 적대적 리뷰(general-purpose subagent, RBAC/런타임 경계 — feedback_outside_voice_for_rbac 정책)가 "as written 구현 불가" 판정. 흡수 결정:

| # | 발견 (severity) | 하드닝 결정 |
|---|---|---|
| B1 | TASK-0159/0164 backstop 이 ownership-blind → 매 web 재배포마다 live worker run 을 error 오염. DESIGN §2.7 의 "no-op 격하" 는 실제로 active corruptor (BLOCKER) | 두 hook 을 **ownership-aware**: worker mode 일 때 `ask_jobs` 가 claimed/running 인 conversation skip |
| B2 | `_pg_connect` autocommit=True 에서 `SELECT FOR UPDATE SKIP LOCKED`+별도 `UPDATE` → 락 미유지, double-claim (BLOCKER) | **단일문 atomic claim**: `UPDATE … WHERE id=(SELECT … FOR UPDATE SKIP LOCKED ORDER BY created_at LIMIT 1) RETURNING` |
| B3 | heartbeat-stale requeue 가 살아있는 느린 worker 와 경합 → 같은 run_id 동시 double-run, steps/core_messages 오염(TASK-0160 류 Bedrock 400) (BLOCKER) | **lease_epoch fencing**(재claim 시 ++; worker 가 주기적 재확인해 빼앗겼으면 중단) + stale 임계 ≥ run_timeout+margin + 긴 LLM step **내부** heartbeat |
| M4 | `set_run_status` 가 3~5 독립 autocommit tx → torn state, 2-writer 시 Frankenstein (MAJOR) | run_id→status 기록 순서 보장 + `ask_jobs.status` ops 권위 / KV terminal mirror + lease fencing 으로 2-writer 차단 |
| M5 | slot COUNT TOCTOU + stuck-running 영구 계정 DoS (MAJOR) | **단일문 enforce** (`INSERT…SELECT…WHERE count<limit RETURNING`, rowcount=0→429) + **stale-aware count**(heartbeat-stale running 제외) |
| M6 | temp 파일 GC 주인 없음 + requeue 시 read-after-delete + `/tmp`→`/shared` + replica 파일명 충돌(TASK-0154 류) (MAJOR) | `/shared` + **uuid 파일명** + **terminal 시에만** cleanup + 고아 reaper(worker tick) + inline reader `/tmp` 가정 감사 |
| M7 | 60s long-poll cap 이 180~1200s run 못 덮음 + error shape drift + no-worker 무한 hang (MAJOR) | 내부 attach 를 run_timeout 까지 loop(영속 conn) + **`result_json` 영속화로 응답 shape 패리티** + **worker readiness gate**(heartbeat 신선 검사, 부재 시 503/fallback) |
| 기타 | pending job cancel 유실, heartbeat conn churn, attempts-cap→무한 requeue, worker SIGTERM/stop_grace 부재 (MINOR) | cancel 을 `ask_jobs.status='canceled'` 도 set / worker 영속 conn / cap 도달 시 terminal error / worker SIGTERM handler(claimed job clean requeue) + compose `stop_grace_period: 70s` |

#### 검증된 payload 계약 (grounding 정정)

호출 함수는 `agent_core.run_agent` (app.py:7586 `from agent_core import run_agent as _run_agent_core` — inner `_run_agent_core` 아님). enqueue payload(jsonb) = run_agent kwargs 12개: `user_message, conversation_id, model, product_id, role_id, account_id, allowed_schemas, product_mode, attachment_ids, new_attachment_ids, image_inline_path, text_inline_path`. (`conv_file`=account_id 에서 재계산, `temperature`=내부 재계산, `api_key`=무시, `output_mode`="json" 고정.)

#### 컴포넌트

1. **`agent_runtime.ask_jobs` 테이블** — alembic `0003_ask_jobs`(권위) + `_ensure_ask_jobs()` IF NOT EXISTS fast-path(동일 DDL). 컬럼: `id, conversation_id, run_id, account_id, status(pending/claimed/running/done/error/canceled), claimed_by, claimed_at, started_at, finished_at, attempts, lease_epoch, heartbeat_at, created_at, payload jsonb, result_json jsonb`. 인덱스 `(status,created_at)`,`(account_id,status)`,`(heartbeat_at)`. mode=worker 인데 table 부재면 fail-loud.
2. **`ask-worker` 서비스** (insight-worker 템플릿) — `<<: *agent-common`, `entrypoint: --ask-worker`, `restart: unless-stopped`, `stop_grace_period: 70s`, heartbeat KV `ask_worker_last_cycle_at` + `scripts/healthcheck_ask_worker.py`(`ASK_WORKER_HEARTBEAT_MAX_AGE_SEC`). agent_core.py main() `--ask-worker` → `modules/ask.py::run_ask_worker_loop()`. SIGTERM handler: claimed job clean requeue(lease++).
3. **claim/실행 루프** — 단일문 atomic claim(B2) → `run_agent(**payload)` → terminal 시 `result_json`+`set_run_status` → temp cleanup(terminal only). 매 step+긴 LLM call 내부 heartbeat(영속 conn). lease 주기 재확인.
4. **stale sweeper** — `status='running' AND heartbeat_at < now-임계(≥run_timeout+margin)` → requeue(lease++,attempts++) 또는 cap 도달 시 terminal error+set_run_status('error').
5. **`/api/ask` worker mode** — 검증/conversation·product·role 해석 무변경 → readiness gate → 단일문 slot enforce → enqueue → 내부 ask_result attach loop(run_timeout 까지) → `result_json` 으로 기존 응답 shape 반환. inprocess mode 는 현행 to_thread(+0164 finalizer) 보존.
6. **backstop ownership-aware(B1)** — TASK-0159 boot reconcile + 0164 SIGTERM finalizer 가 worker mode 에서 `ask_jobs` claimed/running conversation skip.
7. **cancel/finalize** — KV 플래그 폴링 무변경 + cancel 은 pending/claimed `ask_jobs.status='canceled'` 도 set.

#### 롤아웃
`AGENT_ASK_EXECUTION_MODE=inprocess(기본)|worker`. shadow(worker 가동) → 점진 cutover → env 한 번에 rollback. inprocess 경로 + 0164 finalizer 는 worker 프로덕션 검증까지 보존.

#### 검증
- 단위: atomic claim race(동시 N worker 중 1), lease fencing(빼앗긴 worker write no-op), stale sweeper requeue/error/cap, slot 단일문 429 TOCTOU, payload round-trip, readiness gate, cancel-pending.
- 통합: enqueue→worker→KV/steps→attach shape 패리티; **web 재배포 중 worker run 생존**(핵심 B1); worker 크래시→requeue 1회만; cancel/finalize.
- 게이트: `make test`(컨테이너 pytest 회귀 0) + py_compile + **outside-voice /codex diff 리뷰**(merge 전).
- 라이브: PB-0008 Windows-browser(ask 전체 흐름) + 부하(백프레셔) + worker=on 재배포 실측(0164 finalizer 거의 미발동 확인).

#### 영향 파일
- feature-0002: `agent_core.py`(--ask-worker dispatch + run_agent heartbeat/lease), `modules/ask.py`(신규 worker loop/claim/sweeper/reaper/cancel-pending), `modules/memory.py`(set_run_status 순서 M4, ask_jobs 헬퍼), `alembic/versions/0003_ask_jobs*.py`(신규), `scripts/healthcheck_ask_worker.py`(신규), docs(FUNCTION/TASK/MODIFY/REVIEW/MIGRATIONS).
- feature-0003: `src/app.py`(/api/ask worker 경로 + readiness gate + slot 단일문 + 내부 attach + _ensure_ask_jobs + backstop ownership-aware + temp /shared/uuid/terminal cleanup), docs(FUNCTION/TASK/MODIFY/REVIEW).
- repo: `docker-compose.yml`(ask-worker 서비스), `.env*`(AGENT_ASK_EXECUTION_MODE 등 신규 env 문서화).

---

### 2.1 Implementation Plan (TASK-0073)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Critical 등급 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-19 에 CEO review 9 trade-off 결정 → Codex outside voice 14 findings + 6 minimum-fix → 9 decision 중 5 reset (Major redesign) → redesign 최종 확정. CEO review · outside voice · redesign 의 결정을 모두 plan 에 흡수.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0073 Phase A0~F 일괄, Critical 등급 audit 표면 신설 + WebAccountActivity 흡수 + RBAC 4건 .own/.any + Tx split + Allowlist builder + AGENT_AUDIT_ENABLED prod fail-closed) -->

#### 사용자 in-cycle 결정 (CEO review 9 항목, redesign 후)

| 결정 | 채택안 | 근거 |
|---|---|---|
| Mode | HOLD SCOPE | 단일 cycle bulletproof. 추가 expansion 다음 cycle |
| Scope (Approach) | B (Balanced) + WebAccountActivity 흡수 | admin + 대화·SQL·share·search 행위 추적. PIPA §29 1년 retention inherit |
| Storage | DB-only — `WebAuditEvents` (365일 retention + chunked PK purge) | mysql 단일 layer · 트랜잭션 정합 · admin UI filter 즉시 활용 |
| Hook 위치 | Web-ui split — admin endpoint = direct dispatcher (Same tx), user endpoint = best-effort delegate (fail-open) | TASK-0072 fail-open 패턴 답습 + `/api/ask` long-running deadlock 회피 |
| MySQL log | 별 cycle 분리 (slow_query_log 본 cycle 제외) | `slow_query_log` = mysql server log (file) — DB-only 와 모순 / retention·RBAC 미적용 (Codex C1) |
| RBAC | `audit.read.own` (모든 role dba 포함 auto-grant) + `audit.read.any` (admin/dba .any superset) + `audit.export` + `audit.purge` 4건 + permission group `audit` 신규 + CONVENTIONS.md §10.6 동시 갱신 | 기존 `.own/.any` 패턴 정합 (Codex C8) · dba seed 누락 차단 (Codex C9) · misc fallback 차단 (Codex C10) |
| Tx 정책 | Tx split — admin Same tx (정합성 우선 fail-safe) / user fail-open best-effort | `/api/ask` 별 thread/connection + LLM long-running lock contention 회피 (Codex C3, C4) |
| Masking | Action-specific allowlist builder | dispatcher 가 raw request 검증 X. ActionCode 별 명시 `build_change_json(action, actor_ctx, request_ctx, response_ctx)` 화이트리스트 only insert. free-text PII (sql/description/system_prompt/message/result) explicit redact/hash. DoS 차단 (Codex C6) |
| Feature flag | `AGENT_AUDIT_ENABLED` prod (`AGENT_MODE!=dev/test`) startup fail-closed + dev/test toggle | flag bypass surface 차단 (Codex C5) · prod 에서 audit off = 시작 차단 |

#### outside voice 종합 결정 (Codex)

Codex outside voice (read-only sandbox, model_reasoning_effort=high, 5분 timeout) 가 14 findings + 6 minimum-fix requirements + 5 deadlock scenarios 도출. 본 plan 의 9 CEO decision 중 5 개 (Storage·MySQL log·Hook·Tx·Masking 의 5 domain) 가 직접 reset 됨.

| # | finding | 처리 |
|---|---|---|
| C1 | DB-only + slow_query_log 통합 모순 | slow_query_log 별 cycle 분리 |
| C2 | `WebAccountActivity` (TASK-0072) 이미 존재 | 흡수: ActionCode mapping + 기존 row migration + `_log_search_activity` wrap |
| C3 | Same tx + autocommit=True + agent_core 별 connection | Tx split — admin = Same tx / user = fail-open |
| C4 | `/api/ask` Same tx deadlock (LLM 실행 동안 lock hold) | user endpoint Same tx 제외 |
| C5 | `AGENT_AUDIT_ENABLED=0` bypass surface | prod startup fail-closed + dev/test only toggle |
| C6 | Hybrid masking unknown raise = DoS + free-text PII 미차단 | Action-specific allowlist builder (raw 검증 X) |
| C7 | `.self` 정의 미결 (Actor vs Target vs Resource owner) | eng review lock-in (SECURITY.md §8) |
| C8 | RBAC `.self/.read` vs 기존 `.own/.any` 불일치 | `.own/.any` 로 재정렬 |
| C9 | dba role seed/catchup 누락 | dba 명시 auto-grant + `_ensure_seed_catchup` hydrate 보강 |
| C10 | permission group `audit` 추가 시 misc fallback | CONVENTIONS.md §10.6 동시 갱신 |
| C11 | TASK-0058 share anonymous path 누락 가능 | eng review lock-in (`/api/public/share/{token}` view + fork audit) |
| C12 | `_get_client_ip` (app.py:560) X-Forwarded-For trust 약함 | eng review lock-in (Caddy XFF strip/set 검증) |
| C13 | purge self-audit idempotency / rollback / 재시도 | eng review lock-in |
| C14 | 365일 retention + Phase 2 partitioning deferrable + range delete 충돌 | chunked PK purge 본 cycle 필수 |

#### Must-fix 5 (Codex minimum-fix, 본 cycle 강제)

1. **WebAccountActivity 흡수** — Phase A2 migration. 기존 row → `WebAuditEvents` 의 ActionCode `conversation.search.any` / `conversation.snippet.any` 변환 + RemoteAddr/UserAgent NULL (TASK-0072 schema 에는 부재). `_log_search_activity` 는 새 dispatcher 의 user best-effort path 로 wrap (signature transparent 보존). 기존 `WebAccountActivity` DROP 은 별 cycle (data 보존 backup 후).
2. **`.own/.any` RBAC + .own SQL filter** — `audit.read.own` (dba 포함 모든 role auto-grant), `audit.read.any` (admin/dba .any superset), `audit.export` (admin/dba), `audit.purge` (admin only). `.own` SQL filter: `WHERE ActorAccountId = :session_account_id` 강제. TASK-0058 share read-gate 패턴 답습 (read-gate 먼저 = 404 metadata leak 차단 + `.any` superset semantics).
3. **Action-specific allowlist builder** — dispatcher 는 raw request 검증 X. 각 ActionCode 별 `build_change_json(action: str, actor: dict, request_ctx: dict, response_ctx: dict) -> dict` 명시 화이트리스트. unknown action / field 는 builder 단계에서 raise (dispatcher 단계 X). free-text PII (sql/description/system_prompt/message/result/temporary_password/Token/SessionTokenHash/PasswordHash/API key cipher) explicit redact/hash. SECURITY.md §8 의 sensitive field catalog 가 builder source-of-truth.
4. **`AGENT_AUDIT_ENABLED` prod fail-closed** — startup 시 `AGENT_MODE` 와 `AGENT_AUDIT_ENABLED` 동시 check. prod (`AGENT_MODE` 가 `dev` / `test` 가 아닐 때) 에서 `AGENT_AUDIT_ENABLED!=1` 이면 시스템 시작 차단 + stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1`. dev/test 만 toggle 허용. flag state changes 는 audit row 불가 (env 변경은 DB mutation 아님) → startup stderr log 만.
5. **Tx split — admin Same tx + user fail-open** — admin 13 endpoint (account update / role create-update-delete / permission grant / product CRUD / password-reset / account delete) = dispatcher direct call, business tx 에 audit INSERT 포함 (audit fail = rollback). user 4 endpoint (`/api/ask`, `/api/conversations/{cid}/share` POST·DELETE, `/api/public/share/{token}/fork` POST, `/api/conversations` search snippet) = best-effort delegate (TASK-0072 `_log_search_activity` 패턴), audit fail = stderr only, main flow 진행. dispatcher SPOF mitigation: verify-completion.sh check + 100% test coverage on dispatcher.

#### Additional risk 9 (Codex C7-C14, eng review lock-in)

1. `audit.read.own` 의 self 정의 (ActorAccountId vs TargetAccountId) — SECURITY.md §8 명시 (admin 의 password-reset target=user 이벤트가 user 자기 audit 에 보이는지)
2. ChangeJson HTML escape on admin UI detail pane (TASK-0058 share.html `<pre>` 패턴 답습)
3. `_get_client_ip` (app.py:560) trust 패턴 검토 + Caddy XFF strip/set 설정 확인 (feature-0006-lan-proxy-access)
4. purge self-audit + idempotency key + chunked PK cursor 재시작 가능
5. chunked purge `ORDER BY Id LIMIT N` 본 cycle 필수 (Phase 2 deferrable 아님)
6. ChangeJson schema hybrid (indexed columns `ActionCode`/`ResourceType`/`ResourceId`/`OccurredAt` + JSON column `ChangeJson`/`MaskedFields`)
7. dispatcher SPOF — verify-completion.sh check + 100% test coverage
8. decorator pattern `@audit_action("admin.account.update")` for hook site DRY (선택)
9. test infra (`feature-0003-agent-web-ui/tests/`) 보강 — masking builder + RBAC .own enforcement + WebAccountActivity migration smoke

#### 영향 파일 (최종, slow_query_log 제외 + WebAccountActivity migration 추가 = 13 파일)

Backend:
- [src/app.py](../src/app.py) —
  - Phase A0: `_ensure_web_audit_events_schema(conn)` 신설 (DDL: `Id BIGINT PK, ActorAccountId, ActorRoleId, SessionId, ActionCode VARCHAR(64), ResourceType VARCHAR(32), ResourceId VARCHAR(64), ChangeJson JSON, MaskedFields JSON, RemoteAddr VARCHAR(64), UserAgent VARCHAR(255), RequestId VARCHAR(64), OccurredAt TIMESTAMP(3); INDEX (ActorAccountId, OccurredAt) / (ActionCode, OccurredAt) / (ResourceType, ResourceId)`). `_ensure_seed_catchup` hydrate.
  - Phase A1: `record_audit_event(conn, actor, action, resource_type, resource_id, change_json, masked_fields)` dispatcher + `AGENT_AUDIT_ENABLED` startup fail-closed gate (`AGENT_MODE` check) + `_get_client_ip` 재사용.
  - Phase A2: WebAccountActivity migration helper — 기존 row → WebAuditEvents transform (ActionCode `conversation.search.any` / `conversation.snippet.any`, ActorAccountId=AccountId, ResourceType=`conversation`, ResourceId=TargetOwnerId, ChangeJson=`{query_hash, matched_count}`, OccurredAt=CreatedAt, RemoteAddr/UserAgent NULL). `_log_search_activity` 는 새 dispatcher 의 user best-effort path 로 wrap (transparent signature 보존, 호출처 변경 X).
  - Phase A3: `PERMISSION_DEFINITIONS` +4 (`audit.read.own` / `audit.read.any` / `audit.export` / `audit.purge`) + dba role 자동 grant + `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출 순서 강제 (TASK-0063 회귀 fix 패턴 답습).
  - Phase A4: 5 endpoint 신설 (`GET /api/admin/audits` filter/cursor, `GET /api/admin/audits/{id}`, `GET /api/admin/audits/export.csv`, `GET /api/admin/audits/actors`, `GET /api/admin/audits/resources`) + `_require_permission` + `.own` SQL filter (`WHERE ActorAccountId=session_account_id`) 강제 + chunked purge `POST /api/admin/audits/purge` (`audit.purge` gate, `ORDER BY Id LIMIT N` cursor, idempotency key, self-audit row).
  - Phase A5: admin 13 mutation endpoint hook (direct dispatcher call, Same tx). ActionCode 별 `build_change_json` allowlist (`admin.account.update`, `admin.account.delete`, `admin.account.password-reset`, `admin.role.create/update/delete`, `admin.role.permission.grant/revoke`, `admin.account.permission.override`, `admin.product.create/update/delete` 등 13).
  - Phase A6: user 4 endpoint hook (best-effort delegate, fail-open). `/api/ask` (ActionCode `conversation.ask`), `/api/conversations/{cid}/share` POST/DELETE (`conversation.share.create` / `conversation.share.revoke`), `/api/public/share/{token}/fork` (`share.fork`), `/api/conversations` search snippet (TASK-0072 `_log_search_activity` wrap 통한 통합).

Frontend:
- [src/static/admin.html](../src/static/admin.html) — 신규 탭 "감사 로그" (Roles 다음 / Products 사이) + filter row (기간 datepicker / 액션 dropdown / actor search / resource search / action group chip) + list-detail pane + ChangeJson diff viewer (`<pre>` HTML escape). `.admin-shell` grid TASK-0071 패턴 (`grid-template-rows: minmax(0, 1fr)`) 답습.
- [src/static/admin.js](../src/static/admin.js) — `ADMIN_AUDIT_*` state + `renderAuditList()` + `renderAuditDetail()` (ChangeJson HTML escape via `<pre>`) + filter handlers + CSV export button (`audit.export` gate, hide-vs-disable=hide TASK-0052 패턴) + Section permission `audit` group rendering (CONVENTIONS.md §10.6 신규 group 의 admin section "관리" 우선 노출).
- [src/static/styles.css](../src/static/styles.css) — `.admin-audit-*` ~10 클래스 + `.admin-audit-diff` token + `.admin-audit-masked` placeholder style + cache-bust `v=20260519-audit-tab`. `.admin-list-detail` 의 grid row contract 답습.
- [src/static/app.js](../src/static/app.js) — `PERMISSION_GROUP_ORDER` 에 `audit` 추가 + `WORK_SCREEN_PERMISSION_SECTIONS` 의 management section 에 `audit.read.own` 만 placeholder 노출 (작업 화면에 self-audit 진입점 본 cycle scope 외, placeholder only).

문서:
- `docs/FUNCTION.md` — REQ-20260519-0001 + AC 12~15개 (audit dispatcher / RBAC 4 / .own filter / masking allowlist / `AGENT_AUDIT_ENABLED` prod gate / WebAccountActivity migration / chunked purge / slow_query_log Phase 2 분리).
- `docs/TASK.md` — 본 §2.1 + Task Queue entry + Completion Checklist.
- `docs/MODIFY.md` — Phase A0~F 별 CHG-20260519-0001 entry.
- `docs/REVIEW.md` — CEO review 9 decision 결정 근거 + Codex 14 findings 흡수 이력 + Must-fix 5 + Additional risk 9 + redesign trace.
- `docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과 (§16.5 Step 6).
- `docs/TEST.md` — TEST 케이스 정의 (§2 rewrite): dispatcher unit + masking allowlist + RBAC `.own` enforcement + WebAccountActivity migration smoke + `AGENT_AUDIT_ENABLED` prod fail-closed + chunked purge + admin UI smoke.

프로젝트 수준:
- `repo/docs/SECURITY.md` §8 신설 — Audit subsystem 정책: Sensitive field catalog (source-of-truth) + Action-specific allowlist policy + `.own/.any` self 정의 + `audit.purge` self-audit + chunked PK 정책 + `AGENT_AUDIT_ENABLED` prod fail-closed gate. TASK-0072 PIPA §29 1년 retention inherit 명시.
- `repo/docs/DECISIONS.md` ADR-0019 신설 — Audit subsystem 도입 결정 근거: Approach B 선택 / WebAccountActivity 흡수 / Tx split / Allowlist builder / CEO review + Codex outside voice 흡수.
- `repo/docs/ARCHITECTURE.md` §4 (기능 맵 — 책임 영역) + §6 (의존성 맵) — dispatcher cross-feature dependency 표시.
- `repo/docs/CONVENTIONS.md` §10.6 — permission group `audit` 신규 + 작업 화면 / admin 콘솔 section 배치 갱신 (admin 콘솔 management section 의 audit.read.any/.export/.purge 우선 / 작업 화면 management section 의 audit.read.own placeholder).
- `repo/docs/STATUS.md` — feature-0003-agent-web-ui row 갱신 (TASK-0073 entry).

#### Phase 순서 (최종)

1. **Phase A0 — WebAuditEvents DDL** — `_ensure_web_audit_events_schema` + `_ensure_seed_catchup` hydrate. py_compile + 컨테이너 재시작으로 DDL 적용 확인.
2. **Phase A1 — dispatcher + `AGENT_AUDIT_ENABLED` gate** — `record_audit_event(...)` + startup fail-closed gate. py_compile.
3. **Phase A2 — WebAccountActivity 흡수 + migration helper** — 기존 row transform + `_log_search_activity` wrap. data 보존 (기존 table drop 은 별 cycle).
4. **Phase A3 — RBAC catalog +4 + permission group `audit` + CONVENTIONS.md §10.6** — `PERMISSION_DEFINITIONS` +4 + dba 명시 auto-grant + hydrate 순서 강제 + admin.js + app.js section rendering. py_compile + node --check.
5. **Phase A4 — 5 audit endpoint + chunked purge** — `_require_permission` + `.own` SQL filter + chunked PK cursor + self-audit row. py_compile.
6. **Phase A5 — admin 13 endpoint hook (Same tx)** — direct dispatcher + ActionCode 별 `build_change_json` allowlist. py_compile + HTTP smoke.
7. **Phase A6 — user 4 endpoint hook (fail-open)** — `/api/ask` + share + search 의 4 hook. py_compile.
8. **Phase B — HTTP smoke 8 시나리오** — `tests/test_audit_dispatcher.py` + `tests/test_audit_rbac.py`: (1) admin update → audit row + Same tx rollback, (2) `/api/ask` → user fail-open silent, (3) `.own` actor=self → 본인 row 만, (4) `.own` actor=other → 403 byte-equal, (5) `.any` actor=any → 전체, (6) `.export` CSV + masked, (7) `.purge` chunked + self-audit row, (8) `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` → startup fail.
9. **Phase C — Frontend** — admin.html 탭 + admin.js 렌더 + styles.css + cache-bust. node --check.
10. **Phase D — 프로젝트 수준 docs** — SECURITY §8 + DECISIONS ADR-0019 + ARCHITECTURE §4 + CONVENTIONS §10.6 + STATUS 일괄.
11. **Phase E — verify-completion + commit** — `make web` 재배포 + browser smoke (admin 탭 진입 / filter / detail pane / CSV export gated / 새 admin action audit 검증) + `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` + 사용자 명시 commit confirm.
12. **Phase F — /plan-eng-review 후속 lock-in** — Additional risk 9 (Codex C7-C14) lock-in. Phase F 결과 적용은 별 commit (필요 시 follow-up TASK).

#### 위험도 평가 (최종)

| 영역 | 위험도 | 보강 |
|---|---|---|
| RBAC bypass (.own ↔ .any) | Critical | TASK-0058 share read-gate 패턴 + Phase B smoke 8 시나리오 + 404/403 byte-equal |
| PII leak (ChangeJson masking) | Critical | Action-specific allowlist builder (raw 검증 X) + SECURITY.md §8 sensitive field catalog + admin UI HTML escape |
| Tx atomicity (admin Same tx) | Major | dispatcher SPOF = verify-completion.sh check + 100% test coverage + builder explicit raise on unknown action |
| `/api/ask` deadlock | Critical | user endpoint fail-open + TASK-0072 `_log_search_activity` 패턴 답습 + Same tx 제외 |
| Feature flag bypass | Major | `AGENT_AUDIT_ENABLED` prod startup fail-closed + dev/test only toggle |
| WebAccountActivity 흡수 | Major | migration data 보존 (기존 table drop 별 cycle backup 후) + dual source 일시 공존 → 단일 source 전환 |
| RBAC hydrate 순서 | Major | TASK-0063 회귀 fix 패턴 답습 (`_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞) |
| 365일 chunked purge | Major | `ORDER BY Id LIMIT N` cursor 재시작 가능 + idempotency key + `audit.purge` self-audit |
| 회귀 (TASK-0072 search) | Minor | `_log_search_activity` wrap 시 호출처 signature 보존 (transparent wrap) |
| 회귀 (admin layout) | Minor | `.admin-shell` / `.admin-list-detail` grid row contract TASK-0071 패턴 답습 |

**전체 등급**: Critical (audit 표면 신설 + RBAC 4 catalog 확장 + Tx split + PII masking allowlist + dispatcher SPOF + WebAccountActivity 흡수).

#### 검증 계획

각 Phase 종료 후:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/{admin,app}.js`

전체 완료 후:
- (c) Phase B 의 HTTP smoke 8 시나리오 (`tests/test_audit_*.py`)
- (d) `make web` 재배포 + browser smoke (admin 탭 / filter / detail pane / CSV export gated / 새 admin action 발생 시 audit row 검증)
- (e) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`
- (f) `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` 시작 시 fail-closed 검증
- (g) WebAccountActivity 기존 row 가 WebAuditEvents 에 migration 됐는지 SQL count 확인

#### outside voice 결과 요약 (REVIEW.md 정본)

Codex outside voice (read-only sandbox, model_reasoning_effort=high, 5분 timeout):
- 14 findings + 6 minimum-fix requirements + 5 deadlock scenarios 도출
- 본 plan 의 9 CEO decision 중 5 reset (Storage·MySQL log·Hook·Tx·Masking 의 5 domain)
- TASK-0072 `WebAccountActivity` 발견 — 직전 검토 보고가 놓친 결손, 본 plan 의 WebAuditEvents 가 superset 으로 흡수
- 5 minimum-fix 모두 redesign 에 흡수
- 9 additional risk 는 eng review lock-in (Phase F)

REVIEW.md REV-20260519-0001 에 각 finding + minimum-fix + redesign 흡수 이력 + 결정 근거 기록 예정 (Phase D).

#### Eng review lock-in (E1-E9, 2026-05-19)

본 plan 의 Additional risk 9 (Codex C7-C14) + 5 deadlock scenarios + 추가 eng items 를 architecture-level 로 lock-in. `/plan-eng-review` 호출 결과. 사용자 결정 2 항목 (E1, E4) + 나머지 7 항목 prose lock-in.

**E1 — `audit.read.own` self 정의 (사용자 결정: B — Actor OR Target)**
- `WebAuditEvents` 에 `TargetAccountId BIGINT NULL` indexed column 추가. SQL filter: `WHERE ActorAccountId = :self OR TargetAccountId = :self`.
- self-audit valid use case 충족: "내 비밀번호 누가 reset / 내 권한 누가 grant / 내 대화 누가 공유" 등 admin actor + user target 이벤트가 user 본인 audit 에 노출. 보안 가시성 정합.

**E2 — ChangeJson schema hybrid 확정**
- Schema: `Id BIGINT PK AUTO_INCREMENT, ActorAccountId BIGINT NULL, ActorRoleId BIGINT NULL, ActorType VARCHAR(16) NOT NULL DEFAULT 'account', TargetAccountId BIGINT NULL, SessionId VARCHAR(64) NULL, ActionCode VARCHAR(64) NOT NULL, ResourceType VARCHAR(32) NOT NULL, ResourceId VARCHAR(64) NULL, ChangeJson JSON NULL, MaskedFields JSON NULL, RemoteAddr VARCHAR(64) NULL, UserAgent VARCHAR(255) NULL, RequestId VARCHAR(64) NULL, OccurredAt TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3)`.
- 5 secondary indexes: `(ActorAccountId, OccurredAt)`, `(TargetAccountId, OccurredAt)`, `(ActionCode, OccurredAt)`, `(ResourceType, ResourceId)`, `(ActorType, OccurredAt)`.
- MySQL 8.0 generated column 본 case 불필요 (위 indexed columns 으로 모든 filter 충분).

**E3 — RemoteAddr spoof risk (`_get_client_ip` app.py:560)**
- 본 cycle 변경 없음. 기존 `_get_client_ip` reuse (사내 LAN + Caddy reverse proxy 전제).
- `docs/SECURITY.md §8` 에 명시: "외부 LAN 노출 시 Caddy `trust_forwarded_for` 또는 별 trusted_proxies 설정 후속 cycle 필요. feature-0006-lan-proxy-access 위임".
- TASK-0058 share 의 사내 IP 가정과 동일 trade-off.

**E4 — Anonymous share path audit (사용자 결정: B — 포함 + `ActorType` column)**
- `ActorType VARCHAR(16) NOT NULL DEFAULT 'account'` 컬럼 enum: `"account"` / `"anonymous"` / `"system"`.
- anonymous view (`GET /api/public/share/{token}`): ActorType="anonymous", ActorAccountId NULL, ResourceType="share", ResourceId=share_id, ChangeJson `{"share_token_prefix": "abc...8자", "view_count_after": N, "remote_addr": "x.x.x.x"}` (token 전체 X — fragment 만, PII 차단).
- anonymous fork (`POST /api/public/share/{token}/fork`): TASK-0058 의 fork 가 이미 `_require_account` 필수이므로 ActorType="account" + ChangeJson 에 fork source share_token_prefix 명시.
- `(ActorType, OccurredAt)` index 로 외부 access 만 filter 가능.

**E5 — Same tx admin endpoint deadlock 시나리오 (Codex 5 lock 순서)**
- 본 mutation row lock 먼저 → audit INSERT (PK auto-increment + secondary index update, contention 작음).
- product delete cascade: WebSystemPrompts → WebProductDatabases → WebRolePermissions → WebAccountPermissionOverrides → WebPermissions → WebProducts 순서. audit builder 도 같은 순서로 조회 (역순 X). cascade 끝 → audit INSERT.
- role/account permission 변경: `_ensure_permission_catalog` snapshot 읽기 + audit INSERT 같은 tx (READ COMMITTED isolation, snapshot drift 허용).
- share revoke: TASK-0058 의 race-free UPDATE 패턴 + audit INSERT 같은 tx.
- bulk delete: 입력 PK 정렬 후 처리 → 두 동시 요청이 같은 PK 순서로 lock → deadlock 회피.

**E6 — Decorator vs explicit dispatcher call: explicit 확정**
- decorator 는 magic hiding (actor capture / ChangeJson builder / masked_fields 가 endpoint 마다 다름).
- 17 endpoint (admin 13 + user 4) 마다 explicit `record_audit_event(conn, actor, action, ...)` 호출 + builder.
- ChangeJson builders 는 `src/audit_builders.py` (별 module) 또는 `app.py` 내 helper 섹션. 각 builder 가 `docs/SECURITY.md §8` sensitive field catalog 참조.

**E7 — Dispatcher SPOF 차단**
- `bin/verify-completion.sh` 의 check 에 `from app import record_audit_event` import 가능성 + ENV `AGENT_AUDIT_ENABLED` validation 추가 (Phase A1 의 verify-completion 보강).
- 100% test coverage on dispatcher (Phase B 의 `tests/test_audit_dispatcher.py`).
- startup gate: `AGENT_AUDIT_ENABLED=1` + `AGENT_MODE` check.

**E8 — Purge atomicity + chunked PK loop**

```python
def purge_audit_events(conn, cutoff_dt, actor, chunk_size=1000):
    total_deleted = 0
    first_iter = True
    started_at = now()
    idempotency_key = hash((cutoff_dt, started_at.replace(second=0, microsecond=0)))
    while True:
        with conn.begin_transaction():  # each chunk = separate tx
            rows = SELECT Id FROM WebAuditEvents WHERE OccurredAt < cutoff ORDER BY Id LIMIT chunk_size
            if not rows: break
            DELETE FROM WebAuditEvents WHERE Id IN rows
            if first_iter:
                record_audit_event(conn, actor=actor, action="audit.purge.start",
                                   resource_type="audit_range", resource_id=None,
                                   change_json={"cutoff": cutoff_dt, "chunk_size": chunk_size,
                                                "started_at": started_at,
                                                "idempotency_key": idempotency_key})
                first_iter = False
            total_deleted += len(rows)
    record_audit_event(conn, actor=actor, action="audit.purge.complete",
                       resource_type="audit_range", resource_id=None,
                       change_json={"cutoff": cutoff_dt, "total_deleted": total_deleted,
                                    "idempotency_key": idempotency_key})
```

- 각 chunk = 별 tx (Long Running Transaction 회피). `audit.purge.start` + `audit.purge.complete` 두 self-audit event. `idempotency_key = hash(cutoff, started_at_minute)` (1 분 내 중복 purge 차단).

**E9 — dba role seed/catchup 보강**
- `SEED_ROLE_DEFINITIONS` (app.py:356) 의 모든 role (pending/operator/sales/admin/dba) 의 `permissions` set 에 `audit.read.own` 추가.
- `_ensure_seed_catchup` (app.py:2516) 의 backfill loop 가 dba 도 포함. 현재 admin/operator/sales catchup 만 한다면 dba 추가 (Phase A3 실행 시 `_ensure_seed_roles` 본문 확인 + 보강).

#### Phase B 시나리오 확장 8 → 10 (E1 B + E4 B 결정 반영)

추가 시나리오:
- **(3a)** admin 의 password-reset 후 user 가 `/api/admin/audits` 본인 audit 조회 → admin event (actor=admin, target=user) 가 본인 audit 에 보임 (E1 B 의 핵심 검증).
- **(9)** anonymous share view → audit row 생성 (ActorType="anonymous", ActorAccountId NULL, share_token_prefix 만 — token 전체 X).
- **(10)** `/api/admin/audits?actor_type=anonymous` filter → anonymous 만 조회 가능 (audit.read.any 필요).

#### Test infra 보강

- `unit/feature-0003-agent-web-ui/tests/test_audit_dispatcher.py` — `record_audit_event` + `AGENT_AUDIT_ENABLED` gate + ChangeJson builders unit tests (TASK-0072 `test_search_rbac.py` 패턴 답습).
- `unit/feature-0003-agent-web-ui/tests/test_audit_rbac.py` — 10 HTTP smoke 시나리오 (urllib + 직접 DB seed).
- `unit/feature-0003-agent-web-ui/tests/test_audit_migration.py` — `WebAccountActivity` → `WebAuditEvents` migration smoke.

#### Acceptance criteria (Phase A0 ready to start)

Phase A0 실행 직전 다음이 모두 명확:
- [x] `WebAuditEvents` DDL 완전 명세 (14 columns + 5 indexes, ActorType + TargetAccountId 포함)
- [x] Dispatcher signature 확정 (`record_audit_event(conn, actor, action, resource_type, resource_id, change_json, masked_fields)`)
- [x] ChangeJson builder 명세 위치 (`audit_builders.py` 또는 app.py 내 섹션, sensitive field catalog 참조)
- [x] `AGENT_AUDIT_ENABLED` gate logic (prod startup fail-closed + dev/test toggle)
- [x] Action-specific allowlist masking 정책 (raw 검증 X, builder 화이트리스트)
- [x] Same tx (admin) / fail-open (user) 분기 + Same tx lock 순서 (E5)
- [x] Purge chunked PK loop logic (E8 의 Python 의사코드)
- [x] RBAC catalog 4건 + dba 포함 모든 role auto-grant + permission group `audit`
- [x] `WebAccountActivity` → `WebAuditEvents` migration logic
- [x] Test scenarios 13+ (Phase B 10 HTTP + dispatcher unit + migration + builders)
- [x] CONVENTIONS.md §10.6 audit group 추가 정책
- [x] SECURITY.md §8 sensitive field catalog 구조 + RemoteAddr spoof note

**0 모호성**. Phase A0 (DDL) → A6 (user endpoint hook) → B (tests) → C (frontend) → D (project docs) → E (verify + commit) 순서대로 구현 가능.

#### Eng review 결과 요약 (REVIEW.md REV-20260519-0002 정본)

`/plan-eng-review` cycle:
- 9 architectural findings (E1-E9) lock-in: E1, E4 사용자 결정 / E2, E3, E5-E9 prose lock-in
- 30 test paths coverage diagram (Phase B 10 + dispatcher unit + migration + builders)
- 5 deadlock scenarios (Codex) lock 순서 명세
- 0 critical 미해결 — Phase A0 진입 가능

REVIEW.md REV-20260519-0002 에 각 finding + decision + 근거 기록 예정 (Phase D).

---

### 2.2 Implementation Plan (TASK-0093)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Minor 등급 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high) → 5 findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행. TASK-0073 Phase E hotfix (CHG-20260520-0001) 의 routing 회귀 fragility 를 정적 검사로 영구 차단.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0093 Phase A~F 일괄, Minor 등급 verify-completion check_12 신설 + outside voice 5 findings 흡수 + helper split + fixture-based negative test) -->

#### 요지

`bin/verify-completion.sh` 에 `check_12_audit_endpoint_routing()` 신설 + helper `_check_audit_routing_order()` 분리. feature-0003-agent-web-ui 의 `src/app.py` 내 `@app.get("/api/admin/audits/{event_id}")` line number 가 정적 GET sibling endpoint (auto-discovery 패턴 — `@app.get("/api/admin/audits/<non-{>")`) 의 max line number 보다 **뒤** 인지 정적 grep 검증. FAIL 시 actionable hint 출력. `/purge` 는 method-aware POST 라 GET path collision 위험 0 — sibling list 자동 제외.

#### 현 상태 (검증)

production app.py line 9356 list / 9410 export.csv / 9482 actors / 9522 resources / 9560 purge (POST) / **9732 `/{event_id}`** — hotfix 적용 완료, 정적 GET sibling max=9522 < 9732. positive PASS 조건 충족.

#### Codex outside voice review 흡수 (5 findings + 2 minimum-fix)

| # | finding | 흡수 결정 |
|---|---|---|
| C1 | SKIP 정책 오류 — event_id 또는 sibling 부재 시 silent PASS 는 회귀 방지 게이트 의도 모순. APIRouter 분리·prefix 변경·route 삭제가 silent pass | ACCEPT → SKIP 정책 변경 (feature_id != feature-0003 만 SKIP, 나머지 분기 FAIL "manual review required") |
| C2 | grep 패턴 fragility (multi-line decorator / single quote / @router.get / prefix router / trailing slash) | ACCEPT (C1 과 통합) — structural change 미검출 시 FAIL 처리로 보강. AST 파서까지는 안 감 (Minor scope) |
| C3 | `/purge` 의 method-aware mismatch — POST 라 GET `/{event_id}` 와 collision 0. FAIL hint 의 "purge would route" 표현 부정확 | ACCEPT → `/purge` 는 sibling list 에서 자동 제외 (auto-discovery 패턴이 `@app.get(...)` 만 매치) |
| C4 | Inline 4 hardcoded sibling list 는 new static GET (e.g., `/stats`) 추가 시 stale | ACCEPT → auto-discovery (`@app.get("/api/admin/audits/<non-{>")` 패턴 자동 수집) |
| C5 | Negative test 의 production app.py 임시 이동 위험 — dirty worktree / hook / 중간 실패 | ACCEPT → temp fixture 5 scenario + helper split (`_check_audit_routing_order(app_path)` pure helper). production app.py 절대 미수정 |

추가:
- footer line "9 checks" → "10 checks: 7 pilot + worktree binding + repo immutability + audit endpoint routing" 명시화 (Codex 직접 권장).
- META mode footer ("checks #10, #11 always run") 갱신 불필요 — check_12 는 feature-specific 라 META mode 에서 의도적으로 skip.

#### 영향 파일 (1 code + 5 docs)

Backend (정책 인프라):
- `bin/verify-completion.sh` — `check_12_audit_endpoint_routing()` 함수 신설 + `_check_audit_routing_order()` pure helper split + main() 호출 추가 + footer 2 라인 갱신 (line 1126·1129). META mode footer (line 1084·1091·1094) 는 그대로.

문서:
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — 본 §2.2 + TASK-0093 [ ]→[x]
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0003 entry (head prepend)
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0003 entry (head prepend, outside voice 흡수 이력)
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과
- `unit/feature-0003-agent-web-ui/docs/TEST.md` — TEST 케이스 정의 (positive / 5 negative fixture / SKIP other-feature)

#### check_12 spec (v2, 본 cycle 채택)

```bash
check_12_audit_endpoint_routing() {
  local fdir="$1"
  local feature_id="$2"
  local app_path="${fdir}/src/app.py"

  [ "$feature_id" = "feature-0003-agent-web-ui" ] || return 0  # SKIP — non-target

  if [ ! -f "$app_path" ]; then
    log_check 12 FAIL "audit endpoint routing order" \
      "expected app.py at ${app_path} but file is missing — audit feature removed or restructured"
    return 1
  fi

  _check_audit_routing_order "$app_path"
}
```

`_check_audit_routing_order()` pure helper 가 file path 받아 routing order 검사. Phase C fixture 테스트 진입점. production app.py 외에도 임의 fixture 파일로 호출 가능. `set -euo pipefail` 환경이라 grep no-match (exit 1) 시 `|| true` fallback 처리.

#### Phase 순서

1. **Phase A** — check_12 + helper split + main() 호출 + footer 2 라인 갱신. `bash -n` syntax check PASS.
2. **Phase B** — production positive: helper wrapper 로 production app.py 호출 → `CHECK#12 PASS audit endpoint routing order` PASS. (verify-completion.sh main mode 는 META mode 분기에서 check_12 skip — 정합).
3. **Phase C** — 5 fixture negative test:
   - `valid.py` (정합 ordering) → **PASS**
   - `wrong_order.py` (event_id BEFORE static siblings) → FAIL ordering + line-number hint
   - `no_detail.py` (detail endpoint 부재) → FAIL "detail endpoint missing — possible route removal or refactor"
   - `no_siblings.py` (정적 GET sibling 부재) → FAIL "no static GET siblings — audit route layout changed"
   - `refactored.py` (APIRouter prefix) → FAIL "routes not found in expected form — manual review required"
4. **Phase D** — 5 other-feature SKIP: feature-0001 / 0002 / 0004 / 0005 / 0006 호출 → silent return 0 (rc=0, no output). 회귀 없음.
5. **Phase E** — docs 5 갱신 (본 §2.2 + MODIFY + REVIEW + REPORT + TEST).
6. **Phase F** — 최종 verify-completion 호출 (META mode 가정 PASS) + git status + 권장 commit 메시지 + 사용자 명시 commit confirm.

#### 위험도 평가 (§12.3) — Minor

| 영역 | 위험도 | 보강 |
|---|---|---|
| verify-completion.sh 정책 인프라 변경 | Minor | `bash -n` syntax + production positive + 5 fixture negative + 5 other-feature SKIP 양방향 검증 |
| feature-0003 hardcode | Minor | `feature_id` 검사 SKIP 분기. 일반화는 별 cycle (다른 feature 에 동일 패턴 발견 시) |
| structural change false-pass | **차단 (v1→v2)** | C1 흡수: SKIP→FAIL "manual review required" 로 강제. APIRouter 분리·prefix 변경·route 삭제 모두 LOUD FAIL |
| sibling list staleness | **차단 (v1→v2)** | C4 흡수: auto-discovery 패턴 (`@app.get("/api/admin/audits/<non-{>")` 자동 수집). new static GET 자동 catch |
| method-aware accuracy | **정확 (v1→v2)** | C3 흡수: GET-only sibling 자동 검출. POST (`/purge`) 자연 제외, hint 정확 |
| negative test 안전성 | **안전 (v1→v2)** | C5 흡수: temp fixture + helper split. production app.py 절대 미수정 |
| set -euo pipefail + grep no-match | **차단 (in-cycle fix)** | helper 내 `grep ... || true` fallback. log_check 호출 보장 |

**전체 등급**: Minor — verify-completion.sh 의 read-only 정적 grep 검사 신설. 영향 범위: 정책 인프라 단일 파일 + 정책 인프라가 잡는 회귀 1건. runtime side-effect 0.

#### 검증 계획

각 Phase 종료 후:
- (a) `bash -n bin/verify-completion.sh` syntax check
- (b) helper wrapper 호출 (production positive)
- (c) 5 fixture (negative)
- (d) 5 other-feature (SKIP)

전체 완료 후:
- (e) META mode `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS (META mode 라 check_12 자동 skip, 다른 check 정합 검증)
- (f) git status 정합 + 권장 commit 메시지 표시 + 사용자 명시 commit confirm

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0003 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분 실행, 132,668 tokens):
- 5 findings + 2 minimum-fix recommendations 도출
- 본 plan 의 5 finding 모두 ACCEPT → v2 redesign 흡수
- footer line 표현 수정 권장 흡수 (`9 checks` → `10 checks`)
- 본 사용자 정책 (`feedback_outside_voice_for_rbac`) 적용 — RBAC catalog 변경 없음에도 audit 표면 회귀 방어 정책으로 outside voice 호출. Minor 등급이지만 보안 표면 자체 점검 가치 인정.

REVIEW.md REV-20260520-0003 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.3 Implementation Plan (TASK-0092)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Minor 등급 검증 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 490,891 tokens) → 5 findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행. TASK-0073 Phase E 의 사용자 위임 항목 1 건 해소 — sandbox SSH 인증 차단 환경 해소 + docker/compose 가용 확인 (Docker 29.3.1 + Compose v5.1.1).

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0092 Phase A0~E 일괄, Minor 등급 audit prod gate fail-closed 7 vector matrix 검증 + Codex outside voice 5 findings 흡수) -->

#### 요지

`_enforce_audit_prod_gate()` (app.py:76-94) 의 startup fail-closed 정합성을 **7 vector matrix** 로 live container spawn 검증. `docker run --rm --entrypoint python repo-web:latest -c "import web.app"` 형태로 module load 시점에 gate trigger. exit code + stderr 3 substring 검증 + Traceback 부재 확인.

#### Codex outside voice review 흡수 (5 findings + 2 minimum-fix)

| # | finding | 흡수 결정 |
|---|---|---|
| C1 | 테스트 명령 오류 — Dockerfile 이 web UI 를 `/app/web/` 에 복사 (line 23). `python -c "import app"` 는 `ModuleNotFoundError`. uvicorn entrypoint 우회도 불명확 | **ACCEPT** → `--entrypoint python` + `import web.app` 으로 정정 |
| C2 | `depends_on: mysql` + `.env` + shared volume + 다른 worktree compose project 와 엮일 위험 | **ACCEPT** → `--no-deps` + `docker run` 직접 호출 (compose 우회). `.env` 부재라 inline `-e` 만 사용 |
| C3 | flag parsing 계약 비어있음 — `"true"`/`"yes"`/`"01"` 모두 disabled. 운영자 trap 가능 | **ACCEPT** → V6 추가 (`AGENT_AUDIT_ENABLED=true` + prod → exit 1 negative 검증). SECURITY.md §8 strict-string-equality 계약 명시 별 cycle 후속 권고 |
| C4 | stderr 검증 강화 — prefix-only 약함, full byte-equal 너무 strict | **ACCEPT** → 3 substring (`[FATAL] AUDIT REQUIRED IN PROD` + `set AGENT_AUDIT_ENABLED=1` + `TASK-0073 Phase A1`) + Traceback 부재 검증 |
| C5 | 문서 append 위치 오류 — TEST.md §3 = Test Cases 정의, §4 = Test Run History | **ACCEPT** → **§4** 에 append (기존 format 답습) |

추가 흡수: `repo-web:latest` image 이미 build 됨 — build 부담 0. compose 우회로 multi-worktree 충돌 회피.

#### 7 vector matrix v2

| # | AGENT_AUDIT_ENABLED | AGENT_MODE | 기대 결과 |
|---|---|---|---|
| V1 | `0` | `prod` | exit 1 + stderr `[FATAL] ... AGENT_MODE=prod` (target fail-closed) |
| V2 | `0` | unset | exit 1 + stderr `[FATAL] ... AGENT_MODE=(unset → prod)` (default prod 정합) |
| V3 | `0` | `staging` | exit 1 + stderr `[FATAL] ... AGENT_MODE=staging` (non-dev/test 정합) |
| V4 | `0` | `dev` | exit 0 + stdout `IMPORTED OK` (dev/test bypass 허용) |
| V5 | `1` | `prod` | exit 0 + stdout `IMPORTED OK` (positive control) |
| **V6** (Codex C3) | `true` | `prod` | exit 1 + stderr `[FATAL] ... AGENT_MODE=prod` (strict-string-equality 계약) |
| **V7** | unset | unset | exit 0 + stdout `IMPORTED OK` (default `1` + default prod 정상) |

#### 영향 파일 (docs only, 5 파일)

- `unit/feature-0003-agent-web-ui/docs/TEST.md` — **§4** Test Run History 에 본 cycle 7 vector 결과 append
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0092 [ ]→[x] + 본 §2.3 plan
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0004 entry
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0004 [AGENT-TEAM:codex-outside-voice]
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary 갱신

#### Phase 순서

1. **Phase A0** — `.env` / image 가용성 확인. `repo-web:latest` 존재 확인 (435MB). `.env` 부재 — inline `-e` 만 사용 (compose 우회).
2. **Phase A** — 7 vector spawn (`docker run --rm --entrypoint python repo-web:latest -c "import web.app"`). 각 vector 의 stderr + rc capture.
3. **Phase B** — rc match + stderr 3 substring 모두 포함 + Traceback 부재 검증. PASS vector 는 `[FATAL]` 부재 + `IMPORTED OK` 정합.
4. **Phase C** — TEST.md §4 + 4 docs 갱신.
5. **Phase D** — verify-completion PASS + commit.
6. **Phase E** — issue + push + PR + merge + cleanup (cycle-finalize 패턴, TASK-0093 cycle 답습).

#### 위험도 평가 (§12.3) — **Minor**

| 영역 | 위험도 | 보강 |
|---|---|---|
| docker spawn 부수효과 | Minor | `--rm` 즉시 cleanup, image 이미 build, `--no-deps` mysql 우회 |
| 7 vector 결과 unexpected | Minor | 본 PR 의 핵심 가치 — fail-closed 가정과 실제 동작 일치 검증 |
| `.env` 부재 → compose fail | **차단 (in-cycle fix)** | docker run 직접 호출 (compose 우회). inline `-e` 만 사용 |
| Code 변경 0 | **N/A** | docs append only |
| multi-worktree 충돌 | Minor | `docker run` 직접 호출 (compose project 격리 불필요) |
| 운영자 trap (`"true"` fail-closed) | Minor | V6 검증으로 명시화. SECURITY.md §8 계약 별 cycle 후속 |

**전체 등급**: Minor — 비파괴 검증 작업, code 변경 0, docs append only. audit subsystem 보안 표면 자체 검증 → outside voice review 가치 (`feedback_outside_voice_for_rbac` user policy 정합).

#### 검증 결과 (Phase A~B 실행 후)

**7 vector PASS (7/7)**. 모든 FAIL vector 가 rc=1 + stderr 3 substring + Traceback 부재. PASS vector 는 stdout `IMPORTED OK` + stderr `[FATAL]` 부재. live container spawn 으로 코드 path 정합성 + 메시지 정확성 + dev/test bypass 정합성 모두 확인. TEST.md §4 의 본 cycle entry (2026-05-20) 참조.

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0004 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분 실행, 490,891 tokens):
- 5 critical findings + 2 minimum-fix recommendations 도출
- 본 plan 의 5 finding 모두 ACCEPT → v2 redesign 흡수
- 7 vector matrix (v1 5 → v2 7 vectors) 로 확장
- 본 사용자 정책 (`feedback_outside_voice_for_rbac`) 적용 — RBAC catalog 변경 없음에도 audit subsystem 보안 표면 자체 검증 가치로 outside voice 호출.

REVIEW.md REV-20260520-0004 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.4 Implementation Plan (TASK-0086)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Major 등급 파괴적 DROP** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 398,567 tokens) → 5 findings + 2 minimum-fix → v2 redesign → 사용자 confirm → backup 검증 → DROP ack 진행. TASK-0073 Phase A2 의 dual write 종료 + 일시 공존된 `WebAccountActivity` legacy table 제거.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0086 Phase A0~J 일괄, Major 등급 WebAccountActivity DROP + dual write 종료 + Codex outside voice 5 findings 흡수) -->

#### 요지

`_log_search_activity()` 의 dual write 패턴 (legacy WebAccountActivity INSERT + dispatcher mirror) 을 dispatcher only 로 단일화 + legacy table DROP. backup + scratch restore rehearsal + 1:1 정합 (legacy=74, mirror=74) + 사용자 명시 ack 후 진행. rollback 1~2 cycle window 위해 `_migrate_web_account_activity_to_audit()` helper 만 보존 (table-absent silent skip).

#### baseline 검증 (Phase A 완료)

| 항목 | 값 |
|---|---|
| WebAccountActivity row count | 74 (id 1~74, MatchedCount sum=502) |
| WebAuditEvents `conversation.search.body` mirror count | 74 (1:1 정합) |
| 초기 흡수 (RequestId='account-activity:<id>') | 68 row (TASK-0073 Phase A2 의 1회 호출) |
| dual write 추가 (RequestId=NULL, `_legacy_source="WebAccountActivity"`) | 6 row (id 132~137 in WebAuditEvents) |
| Backup file | `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes) |
| Row digest | `a09e7898d1ce88711f7a850ab5fbcc91` |
| File digest (md5) | `f4163df9dc1b7ac81ae4c463a0f35e98` |
| Scratch restore rehearsal | PASS (별 schema import → digest match ✓) |
| mysqldump options | `--single-transaction --quick --set-charset --create-options --add-drop-table --triggers --hex-blob --no-tablespaces` (Codex C4) |

#### Codex outside voice review 흡수 (5 findings + 2 minimum-fix)

| # | finding | 흡수 결정 |
|---|---|---|
| **C1** | Option A (graceful skip) 불가능 — `_ensure_web_account_activity_schema()` 가 line 2979 + 3130 에서 계속 호출. DROP 후 재기동 시 table 다시 생성 | **ACCEPT** → helper Option B 채택 — 호출 + 정의 모두 명시 제거. migration helper 만 rollback window 보존 |
| **C2** | dispatcher-only 전환 = mirror 실패가 곧 감사 누락. record_audit_event 는 fail-open. legacy INSERT 제거 후 mirror = primary | **ACCEPT** → Phase D+E lightweight smoke (host-mounted code + docker run import). 이전 6 row (id 69~74) 가 mirror 와 1:1 정합 입증 → mirror 작동성 확인. tests/test_audit_migration.py M3 제거 |
| **C3** | "single tx DROP" 표현 잘못됨 — MySQL DDL 은 implicit commit | **ACCEPT** → "DROP TABLE single statement" 표현으로 정정 |
| **C4** | Backup 검증 약함 — row count 부족. mysqldump 옵션 보강 + scratch restore rehearsal 필수 | **ACCEPT** → mysqldump 8 옵션 명시 + scratch restore + canonical digest |
| **C5** | Rollback 정의 불완전 — backup restore = legacy table 만. code revert 필요 | **ACCEPT** → rollback runbook 2 시나리오 분리 (DB restore only / code revert + DB restore) |

추가 흡수:
- function rename `_log_search_activity()` → 보류 (caller 안정성 우위, 별 cycle).
- PR title: `chore(feature-0003): retire WebAccountActivity legacy audit table` (refactor 아닌 운영 DB DROP).

#### 영향 파일 (code 1 + tests 1 + docs 5 + artifacts 1 backup)

Backend:
- `unit/feature-0003-agent-web-ui/src/app.py`:
  - `_log_search_activity()` (line 2566~): legacy INSERT 블록 제거 (이전 line 2589-2615). dispatcher mirror 만 primary path. docstring 갱신 (TASK-0086 marker).
  - `_ensure_web_account_activity_schema()` (이전 line 2537-2563): 함수 정의 제거 (dead code).
  - `_ensure_web_account_activity_schema()` 호출 2 사이트 (line ~2978, ~3128) 제거.
  - `_migrate_web_account_activity_to_audit()`: 함수 본체 + table-absent skip check 보존. docstring 갱신 (TASK-0086 rollback window 명시).

Tests:
- `unit/feature-0003-agent-web-ui/tests/test_audit_migration.py`:
  - 모듈 docstring 갱신 (3→2 시나리오, TASK-0086 marker).
  - `m3_log_search_activity_dual_write()` 함수 제거 (Codex C2 minimum-fix).
  - `main()` 의 M3 호출 제거.

문서:
- `docs/SECURITY.md` §9.8 — "별 cycle DROP" → "DROP 완료 (2026-05-20)" 갱신 + 8 step 절차 명시 + backup file + rollback 2 시나리오 cross-reference.
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0086 [ ]→[x] + 본 §2.4 plan + Completion Checklist.
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0005 entry.
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0005 [AGENT-TEAM:codex-outside-voice].
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary 갱신 + 1.archived TASK-0092 보존.
- `unit/feature-0003-agent-web-ui/docs/TEST.md` — §4 본 cycle backup + DROP 검증 결과 prepend.

Backup:
- `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes).

#### Phase 순서 (Codex 7 step 정합)

1. **Phase A** — mysqldump backup (8 옵션) + scratch restore rehearsal (별 schema import + digest match) + 1:1 정합 검증 (74=74). **완료**.
2. **Phase B** — 사용자 명시 ack (DROP 실행 직전). **완료**.
3. **Phase C** — code 변경 3:
   - `_log_search_activity()` 의 legacy INSERT 블록 제거 (line 2589-2615 → 함수 docstring 갱신 + dispatcher mirror 만 유지).
   - `_ensure_web_account_activity_schema()` 호출 제거 (이전 line 2979 + 3130, 2 사이트) + 함수 정의 제거.
   - `_migrate_web_account_activity_to_audit()` 보존 (table-absent skip + docstring rollback window 명시).
   - py_compile PASS. **완료**.
4. **Phase D+E** — lightweight smoke: `docker run --rm --entrypoint python -v <wt-src>:/app/web repo-web:latest -c "import web.app"`. import OK + `_ensure_web_account_activity_schema` 부재 확인 + `_migrate_web_account_activity_to_audit` 존재 확인. **완료**.
5. **Phase F** — `docker exec repo-mysql-1 mysql ... -e "DROP TABLE IF EXISTS WebAccountActivity"`. **완료**.
6. **Phase G** — `SHOW TABLES LIKE 'WebAccountActivity'` = 0 + mirror row 74 보존 확인. **완료**.
7. **Phase H** — docs 5 + tests 1 갱신. **완료** (본 §2.4 + SECURITY §9.8 + MODIFY + REVIEW + REPORT + TEST + test_audit_migration.py M3 제거).
8. **Phase I** — verify-completion PASS + commit. **본 단계 진행 중**.
9. **Phase J** — issue + push + PR + merge + cleanup (cycle-finalize 패턴, TASK-0093/0092 cycle 답습).

#### 위험도 평가 (§12.3) — **Major** (파괴적 DROP, backup + ack 가 mitigation)

| 영역 | 위험도 | 보강 |
|---|---|---|
| WebAccountActivity 데이터 영구 손실 | **Critical → Major (backup 후)** | mysqldump 8 옵션 + scratch restore rehearsal + digest match + 사용자 명시 ack (Phase B) |
| dual write 제거 후 회귀 | Major | 이전 6 row (id 69~74) 의 mirror 1:1 정합 입증 (dual_write_only=NULL marker + ChangeJson._legacy_source) + Phase D+E lightweight smoke |
| helper Option B 명시 제거 | Major (v1→v2) | C1 분석으로 Option A 불가능 확정. helper 호출 + 정의 모두 제거. migration helper 만 보존 (rollback window) |
| MySQL DDL atomicity 오해 | Minor (v1→v2 정정) | "single tx" → "single statement" 표현 정정. DDL implicit commit 명시 |
| Backup 검증 약함 | **차단 (v1→v2)** | C4 흡수 — mysqldump 8 옵션 + scratch restore rehearsal + canonical digest. 단 row count 만 의존 X |
| Rollback 시나리오 모호 | **차단 (v1→v2)** | C5 흡수 — 2 시나리오 분리 (DB restore only / code revert + DB restore). 본 plan + SECURITY §9.8 cross-reference |

**전체 등급**: Major (파괴적 DROP + dual write 제거 + helper 처리 + 5 step 일괄). backup + 사용자 ack + scratch restore 가 핵심 risk mitigation. rollback 가능성 확보.

#### Rollback runbook (2 시나리오)

**시나리오 1 — DB restore only**:
- 코드는 그대로 (TASK-0086 후 상태), table 만 복구.
- `docker exec -i repo-mysql-1 mysql -uroot -p<PWD> agent_memory < /root/download/docker/mysql_ai_delegated_dev/artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql`.
- 결과: WebAccountActivity 가 다시 존재. `_migrate_web_account_activity_to_audit()` 의 SHOW TABLES check 가 true 됨 → 다음 fast-path catchup 시 idempotent skip (이미 마이그레이션된 row 는 RequestId marker 로 NOT EXISTS).
- **한계**: 새 search 호출은 dispatcher only (코드 변경 안 됨) → table 이 다시 비어가는 상태로 회귀. read-only 보존용.

**시나리오 2 — code revert + DB restore** (완전 rollback):
- `git revert <CHG-20260520-0005 commit>` + `docker compose restart web` + DB restore.
- dual write 부활 + WebAccountActivity 새 row 도 들어감 + mirror 도 들어감.
- 완전 회복 시 사용.

#### 검증 결과 (Phase A~G 실행 후, 2026-05-20)

- backup integrity: scratch restore digest match (`a09e7898d1ce88711f7a850ab5fbcc91`) ✓
- 1:1 정합: legacy 74 = mirror 74 ✓
- DROP 결과: `tables_remaining` = 0 (정합) ✓
- mirror 보존: WebAuditEvents `conversation.search.body` = 74 row 변동 없음 ✓
- py_compile: PASS ✓
- lightweight import smoke: PASS (helper 함수 정의 제거 + migration helper 보존 확인) ✓

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0005 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분, 398,567 tokens):
- 5 critical findings + 2 minimum-fix recommendations 도출
- 본 plan 의 5 finding 모두 ACCEPT → v2 redesign 흡수
- Major + 파괴적 DROP 의무 outside voice (`feedback_outside_voice_for_rbac` user policy)

REVIEW.md REV-20260520-0005 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.5 Implementation Plan (TASK-0091)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **~~Minor~~→Major 등급 audit integrity fix** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 687,409 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign (scope 확장 — audit integrity fix 포함) → 사용자 confirm 진행. TASK-0073 Phase A5 의 admin.product.update audit 정합성 강화 + autocommit/transaction 결함 fix.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0091 Phase A~F 일괄, ~~Minor~~→Major audit integrity fix + before/after full snapshot + Codex outside voice 5 findings 흡수) -->

#### 요지

`admin.product.update` audit 의 before/after = `{id, product_key}` 만 (2 field) → full row snapshot 으로 확장. Codex outside voice 가 추가로 **audit integrity 결함** (autocommit=True default + UPDATE 즉시 commit + audit 실패 시 rollback 가능 0) 발견 — 본 cycle 일괄 fix.

#### Codex outside voice review 흡수 (5 findings)

| # | Codex Finding | 흡수 |
|---|---|---|
| **C1** | `system_prompt.content` full 저장 = SECURITY.md §9.2 위반 (full content 금지, `content_len_*` + preview 만). 기존 `admin.system_prompt.update` builder 가 이미 정합 패턴 (`content_full` masked) | **ACCEPT** → snapshot 에 `system_prompt_summary = {present, content_len, updated_at}` 만, content 본문 제외 |
| **C2** | `admin_update_product()` 가 **same tx audit 아님** — autocommit=True default + UPDATE 즉시 commit + audit fail 시 rollback 가능 0. **Minor 아닌 audit integrity 결함** | **ACCEPT (scope 확장)** → `conn.autocommit=False` + `SELECT FOR UPDATE` + commit + finally autocommit=True |
| **C3** | `_list_products()` 기반 snapshot 과잉 (전체 list scan + FOR UPDATE 불가). databases/system_prompt 별 endpoint = 별 audit | **ACCEPT** → single-row `SELECT FOR UPDATE`. `databases` 제외 (별 endpoint `admin.product.databases.update` 의 audit 으로 분리) |
| **C4** | `sort_order` / `is_default` 누락 = **현재 결함**. endpoint 가 갱신하는데 allowlist 빠짐. `is_default=true` side effect 도 기록 권장 | **ACCEPT** → allowlist 에 `sort_order` + `is_default` 추가 + `default_cleared_product_ids` extra_change_json |
| **C5** | Rollback 설명 낙관적 — full prompt 가 ChangeJson 들어가면 code revert 만으로 복구 안 됨 | **자동 해소** (C1 ACCEPT 로 system_prompt content 가 애초에 안 들어감) |

#### 영향 파일 (code 1 + docs 6)

Backend:
- `unit/feature-0003-agent-web-ui/src/app.py`:
  - **신규 helper `_audit_product_snapshot(conn, product_id)`** (~line 2127): single-row WebProducts snapshot + `SELECT ... FOR UPDATE` + `system_prompt_summary` (content 제외). `databases` 제외 (Codex C3).
  - **`admin_update_product()` endpoint 갱신** (line 8328~): `conn.autocommit=False` + before snapshot + UPDATE + `default_cleared_product_ids` 캡처 + after snapshot + audit + commit + `finally autocommit=True` (Codex C2).
  - **`_AUDIT_BUILDER_PRODUCT_FIELDS` 확장** (line 8862): 7 → 8 field. `+is_default`, `+sort_order`, `+system_prompt_summary` / `-databases`, `-system_prompt`.
  - **builder branch `admin.product.update` 갱신** (line 8966~): `default_cleared_product_ids` 키 명시 처리.

문서:
- `unit/feature-0003-agent-web-ui/docs/TASK.md` §2.5 본 plan + TASK-0091 [x]
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` CHG-20260520-0006
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` REV-20260520-0006
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` §1 Summary
- `unit/feature-0003-agent-web-ui/docs/TEST.md` §4 sentinel + delta smoke 결과
- `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` AC-0192

#### Phase 순서

1. **Phase A** — `_audit_product_snapshot()` helper 신설. **완료**.
2. **Phase B** — endpoint 명시 transaction + before/after snapshot. **완료**.
3. **Phase B-2** — `_AUDIT_BUILDER_PRODUCT_FIELDS` 확장 + builder branch `default_cleared_product_ids` 처리. **완료**.
4. **Phase C** — py_compile + sentinel smoke. **PASS** — SENTINEL `TASK-0091-SENTINEL-...` ChangeJson 부재 ✓ / `should_not_leak` (databases) 부재 ✓ / sort_order 100→50 ✓ / is_default False→True ✓ / `default_cleared_product_ids: [5,9]` ✓ / `system_prompt_summary` 정합 ✓.
5. **Phase D** — docs 6 갱신. **본 단계 진행 중**.
6. **Phase E** — verify-completion PASS + commit.
7. **Phase F** — cycle-finalize (issue + push + PR + merge + cleanup).

#### 위험도 (§12.3) — **Major** (Minor→Major scope 확장)

| 영역 | 위험도 | 보강 |
|---|---|---|
| `system_prompt.content` PII 노출 | **차단 (Codex C1)** | `system_prompt_summary` only (present/content_len/updated_at). full content drop sentinel test PASS |
| `admin_update_product()` autocommit integrity | **차단 (Codex C2)** | 명시 transaction (autocommit=False + commit + finally autocommit=True). audit 실패 시 UPDATE rollback 가능 |
| Concurrent PATCH race | **차단 (Codex C2)** | `SELECT ... FOR UPDATE` row lock |
| allowlist 누락 (sort_order/is_default) | **차단 (Codex C4)** | allowlist 확장. before/after delta 정합 |
| `is_default=true` side effect 추적 | **차단 (Codex C4)** | `default_cleared_product_ids` extra ChangeJson |
| `databases` audit noise | **차단 (Codex C3)** | allowlist 제외. 별 endpoint audit 으로 분리 |
| Rollback risk | **자동 해소** | C1 ACCEPT 로 content full drop — 별 redact SQL 불필요 |

**전체 등급**: ~~Minor~~ → **Major** (audit integrity fix scope 확장). 단 사용자 영향 0 (audit row 정확성만), DB schema 변경 0.

#### 검증 결과 (Phase C 실행 후)

- `python3 -m py_compile app.py` → PASS
- sentinel smoke (`docker run --rm --entrypoint python -v <src>:/app/web repo-web:latest -c "..."`):
  - `'TASK-0091-SENTINEL' in body: False` ✓ (system_prompt full content drop)
  - `'should_not_leak' in body: False` ✓ (databases drop)
  - `sort_order before=100 after=50` ✓
  - `is_default before=False after=True` ✓
  - `default_cleared_product_ids: [5, 9]` ✓
  - `system_prompt_summary: {present: True, content_len: 1234/2000, updated_at: '2026-05-20'}` ✓

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0006 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분, 687,409 tokens):
- 5 critical findings 도출, 2 minimum-fix 권고
- 본 plan 의 5 findings 모두 ACCEPT → v2 redesign (scope Minor→Major 확장)
- `feedback_outside_voice_for_rbac` user policy 적용 — audit 표면 직접 변경

REVIEW.md REV-20260520-0006 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.6 Implementation Plan (TASK-0088)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Minor 등급 docs-only ADR 결정** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 390,785 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행. ADR-0019 의 Codex C1 lock-in 최종 결론.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0088 docs-only, ADR-0020 Decoupled 채택 + Codex outside voice 5 findings 흡수) -->

#### 요지

`slow_query_log` 와 `WebAuditEvents` 의 통합 가능성 — ADR-0019 (audit subsystem) 의 별 cycle 분리 lock-in 최종 결론. **Option C — Decoupled 채택**. 주 근거 = raw SQL text PII 차단.

#### Codex outside voice review 흡수 (5 findings)

| # | Finding | 흡수 |
|---|---|---|
| C1 | 현재 mysql conf 에 `slow_query_log` 설정 부재 (MySQL 8.0 default disabled). framing "현재 통합" → "**향후** 통합 여부" 정정 | **ACCEPT** → Context 에 current state 명시 |
| C2 | Option C 의 **주 근거가 PII 차단** (raw SQL = PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt literal) 이어야. "의도 mismatch" 추상적 | **ACCEPT** → Decision 1순위 근거 = raw SQL text PII 차단 |
| C3 | Option A reject 사유 부정확 — retention/RBAC 정합 trivial. 진짜 사유 = semantic pollution + raw SQL PII + ChangeJson 비대화 + actor/target 의미 부재 + 고빈도 audit table 오염 | **ACCEPT** → Option A reject 재작성 (4 구체 사유) |
| C4 | Option B reject 약함. 구체 사유 = raw SQL exfiltration 표면 + mount/rotation/race + 대용량 파일 DoS + `audit.read.any` 권한 의미 오염 + MySQL `TABLE` log destination 우회 | **ACCEPT** → Option B reject 재작성 (5 구체 사유) |
| C5 | performance_schema 빠짐. MySQL 8.0 의 `events_statements_summary_by_digest` digest 집계 1차 도구 | **ACCEPT** → Consequences 에 PS digest-first 권유 (1차), slow_query_log incident enable (2차) |

#### 영향 파일 (docs only, 7 파일)

- `docs/DECISIONS.md` — ADR-0020 신설 (ADR-0019 Consequences 다음). ADR-0019 의 "별 cycle 분리" 라인 cross-reference 추가.
- `docs/SECURITY.md §9.9` — ADR-0020 cross-reference (slow_query_log = 민감 로그, admin UI/ChangeJson 복제 금지).
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0088 [x] + 본 §2.6 plan.
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0007.
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0007.
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary.
- `unit/feature-0003-agent-web-ui/docs/TEST.md` — §4 본 cycle 결과 (docs only, ADR review trace).

#### Phase 순서

1. **Phase A** — `docs/DECISIONS.md` ADR-0020 작성. **완료**.
2. **Phase B** — `docs/SECURITY.md §9.9` cross-reference + docs 5 갱신. **완료**.
3. **Phase C** — verify-completion + commit.
4. **Phase D** — cycle-finalize (issue + push + PR + merge + cleanup).

#### 위험도 (§12.3) — **Minor**

docs only, code 변경 0, DB schema 변경 0, runtime side-effect 0. ADR 자체가 future trigger condition 만 명시 — 현재 운영 영향 0.

#### Decision 핵심 (Option C — Decoupled)

- **slow_query_log 와 WebAuditEvents 통합 안 함**.
- **운영 성능 관측**: `performance_schema` / `sys` digest views (1차) + slow_query_log incident enable (2차).
- **slow_query_log raw SQL = 민감 로그**. WebAuditEvents / ChangeJson / admin UI 에 복제 금지.
- **외부 SaaS / multi-tenant trigger**: `performance-log.read` permission 신설 + raw SQL redaction/sampling + threat model ADR 선행.

#### outside voice 결과 (REVIEW.md REV-20260520-0007 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 390,785 tokens):
- 5 critical findings 도출, 2 minimum-fix 권고
- 본 ADR 의 5 findings 모두 ACCEPT → v2 redesign
- `feedback_outside_voice_for_rbac` user policy 적용 — ADR 자체가 audit 정책 표면 영향

---

### 2.7 Implementation Plan (TASK-0090)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Minor 등급 backend code 변경** 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 550,870 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0090 Phase A~D 일괄, Minor backend code + Codex outside voice 5 findings 흡수) -->

#### 요지

`/api/admin/audits/export.csv` 의 hard cap 50k row + `cur.fetchall()` buffer + `io.StringIO()` 전체 메모리 로드를 **StreamingResponse + sync generator + keyset cursor pagination** 으로 전환. large fleet (100k+) memory footprint 안전 + export self-audit + try/finally cleanup.

#### Codex outside voice review 흡수 (5 findings)

| # | Finding | 흡수 |
|---|---|---|
| **C1** | async generator + sync mysql.connector = event loop blocking. StreamingResponse 는 sync iterator 도 받음 (iterate_in_threadpool). endpoint conn close 가 generator 보다 먼저 실행 → streaming-only conn 필요 | **ACCEPT** → `def csv_iter()` sync generator + 별 streaming conn (generator 내부 finally cleanup) |
| **C2** | consistent snapshot 은 long transaction 부담. audit append-only → `MAX(Id)` high-water mark 권장 | **ACCEPT** → 시작 시 `SELECT MAX(Id) FROM WebAuditEvents{where}` 잡고 모든 page `Id <= max_id AND Id < cursor_id` |
| **C3** | keyset + filter 정합 OK, 단 query plan 미보장. EXPLAIN FORMAT=JSON 권장 | **ACCEPT** → TEST.md 에 representative filters EXPLAIN 기록 (live mysql 실행 가능 시 future cycle, 본 cycle 은 코드 변경만) |
| **C4** | 50k cap 제거 = DoS/계약 변경. SECURITY 갱신 + export self-audit + 동시 실행 제한 | **ACCEPT (부분)** → cap 제거 + SECURITY §9.5 갱신 + export self-audit (start + complete/aborted). 동시 실행 제한은 multi-worker semaphore 정합 → 별 cycle followup |
| **C5** | cleanup generator try/finally — client disconnect / timeout 시 cursor/conn 누설 | **ACCEPT** → generator 내부 try/finally (cursor.close + conn.close + complete audit) |

추가 흡수 (minimum-fix 2):
- chunk_size **1000→500** (안전 마진)
- 1 row yield 대신 **64KiB byte-threshold flush**
- CRLF 유지, BOM 추가 안 함

#### 영향 파일 (code 1 + docs 6)

- `unit/feature-0003-agent-web-ui/src/app.py`:
  - `StreamingResponse` import 추가 (line 28).
  - 신규 helper `_audit_export_filter_hash(params)` (~line 9466) — filter PII 회피용 sha256[:16] hash.
  - 신규 const `_AUDIT_EXPORT_CHUNK_SIZE = 500`, `_AUDIT_EXPORT_FLUSH_BYTES = 65536`.
  - `export_audit_events_csv` endpoint 전면 재작성 (line 9476~9683): 2-phase (짧은 auth conn + max_id capture + start audit → sync generator with streaming-only conn + chunked SELECT + byte-threshold flush + try/finally + complete audit).
- 문서:
  - `docs/SECURITY.md §9.5`: `audit.export` permission 설명 갱신 (hard cap 50k 제거 + StreamingResponse + max_id high-water + self-audit).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: §2.7 본 plan + TASK-0090 [x].
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: CHG-20260520-0008.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0008.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0193.

#### Phase 순서

1. **Phase A** — endpoint 재작성 + StreamingResponse import. **완료**.
2. **Phase B** — py_compile PASS + lightweight smoke (host-mounted code + docker run): `_AUDIT_EXPORT_CHUNK_SIZE=500`, `_AUDIT_EXPORT_FLUSH_BYTES=65536`, helper 존재, `StreamingResponse` import, filter_hash deterministic. **완료**.
3. **Phase C** — docs 6 갱신. **본 단계 진행 중**.
4. **Phase D** — verify-completion + commit + cycle-finalize (issue + push + PR + merge + cleanup).

#### 위험도 (§12.3) — **Minor**

backend code 1 endpoint, runtime 영향 audit subsystem only, contract 변경 = hard cap 50k 제거 (응답 형식 CSV 동일). live PATCH runtime smoke = PR merge 후 사용자 위임.

#### Recommended future cycle (Codex C4 followup)

- 동시 export 제한 (multi-worker semaphore 정합 검토)
- representative filters EXPLAIN FORMAT=JSON 분석 (live mysql)

#### outside voice 결과 (REVIEW.md REV-20260520-0008 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 550,870 tokens):
- 5 critical findings + 2 minimum-fix recommendations
- 5 findings 모두 ACCEPT → v2 redesign
- C4 부분 흡수 — 동시 실행 제한은 별 cycle (multi-worker semaphore)

---

### 2.8 Implementation Plan (TASK-0089)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Minor 등급 frontend + backend 2 endpoint 추가** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 829,505 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign (scope 확장 — backend endpoint 2 신설) → 사용자 confirm 진행.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0089 Phase A~G, Minor backend 2 endpoint + frontend 3 + Codex 5 findings 흡수) -->

#### 요지

profile drawer 5번째 탭 "내 감사 로그" 신설. 본인 audit row (Actor or Target = self) 표시. backend 신규 endpoint 2 — `/api/profile/audits` + `/api/profile/audits/{event_id}` — `scope="own"` 강제 (Codex C2). CSV export / purge 는 admin 한정 미노출.

#### Codex outside voice 5 findings 흡수

| # | Finding | 흡수 |
|---|---|---|
| **C1** | `/api/admin/audits` URL 의미 mismatch — `.own` 호출 가능하나 `/admin/` 이 drawer 와 부합 안 함 | **ACCEPT** → 신규 `/api/profile/audits` + `/api/profile/audits/{id}` |
| **C2** | `_audit_resolve_read_scope()` `.any` > `.own` 우선 — frontend `scope=own` 만으로 부족, backend 강제 필요 | **ACCEPT** → backend `scope="own"` 강제 (`_audit_compose_where(scope="own", ...)`). `.any` 보유자도 본인만 |
| **C3** | CSV export drawer 제외 — export endpoint `scope="any"` 고정, drawer 노출 시 전체 CSV 유출 | **ACCEPT** → drawer 에 export/purge 미노출 |
| **C4** | drawer 폭 390px 에 2-column 안 맞음 + ChangeJson 가독성 | **ACCEPT** → 1-column list + inline detail expand + `<pre>` overflow:auto 수평 스크롤 |
| **C5** | 권한 race — backend OK, frontend 처리 필요 (403 → "권한 없음", tab gate) | **ACCEPT** → `updateProfileAuditTabVisibility()` + 403 graceful state.profileAudit.forbidden |

추가: mini filter = `action_code` + `from_at` + `to_at` (3 필드). actor_id / actor_type 제거 (본인 한정 무의미).

#### 영향 파일 (code 4 + docs 6)

Backend:
- `unit/feature-0003-agent-web-ui/src/app.py`: 신규 endpoint 2 (`list_profile_audit_events`, `get_profile_audit_event`) — 기존 helper (`_audit_parse_filter_params`, `_audit_compose_where`, `_audit_row_to_dict`, `_audit_build_self_filter_sql`) 재사용.

Frontend:
- `unit/feature-0003-agent-web-ui/src/static/index.html`: drawer-tab "내 감사 로그" + drawer-pane (filter row mini + 1-column list + pagination + inline detail). cache-bust `v=20260520-profile-audit`.
- `unit/feature-0003-agent-web-ui/src/static/app.js`: `state.profileAudit` + helper (`_profileAuditEscapeHtml`, `_profileAuditFormatDt`, `_profileAuditHasReadPermission`, `updateProfileAuditTabVisibility`, `_profileAuditReadFilters`, `_profileAuditClearFilters`) + loader (`loadProfileAuditList`) + renderer (`renderProfileAuditList`, `renderProfileAuditDetail`) + handlers (`attachProfileAuditHandlers`). tab click handler 의 audit branch + `renderProfile()` 의 tab visibility wire.
- `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.profile-audit-*` ~15 클래스 (filter / row / detail / `<pre>` 수평 스크롤).

문서: TASK §2.8 + MODIFY CHG-20260520-0009 + REVIEW REV-20260520-0009 + REPORT §1 + TEST §4 + FUNCTION AC-0194.

#### Phase 순서

1. **Phase A** — backend endpoint 2 신설. **완료**.
2. **Phase B** — index.html drawer-tab + drawer-pane. **완료**.
3. **Phase C** — app.js state + helper + loader + renderer + handlers + tab wire. **완료**.
4. **Phase D** — styles.css. **완료**.
5. **Phase E** — py_compile + node --check + routing smoke. **PASS** (`/api/profile/audits` + `/api/profile/audits/{event_id}` 등록 확인). **완료**.
6. **Phase F** — docs 6 + FUNCTION AC-0194. **본 단계 진행 중**.
7. **Phase G** — verify-completion + commit + cycle-finalize.

#### 위험도 (§12.3) — **Minor**

backend code 2 endpoint (helper 재사용) + frontend 3 + docs 6. runtime 영향 audit subsystem only. live browser smoke = PR merge 후 사용자.

#### outside voice 결과 (REVIEW.md REV-20260520-0009 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 829,505 tokens):
- 5 critical findings + 2 minimum-fix recommendations
- 5 findings 모두 ACCEPT → v2 redesign (frontend only → backend endpoint 2 추가)

---

### 2.9 Implementation Plan (TASK-0087)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 (보안 표면 + multi-feature) 변경 계획이다. **상태**: `approved-after-outside-voice`. TASK-0073 Eng review E3 의 deferred 항목 (TASK-0058 share 사내 IP 가정과 동일 trade-off) 을 명시적 정책 + 코드로 lock-in. Plan v1 (RFC1918 trust + silent skip) → Codex outside voice review 6 findings (Major 5 + Minor 1) → Plan v2 (Caddy XFF 정규화 + mode-aware fail-loud + XFF IP 검증) 흡수.

#### 사용자 in-cycle 결정 (3 항목)

| 결정 | 채택안 | 근거 |
|---|---|---|
| Plan v2 흡수 범위 | 전부 흡수 + docker-compose port mapping 변경은 별 cycle | 본 worktree 컨테이너는 테스트 후 정리. 외부 접속 경로 유지 필요. Codex 권고 "port mapping 변경" 은 사용자 환경 외 별 사이클에서 검토 |
| `WEB_TRUSTED_PROXIES` default 권장값 | RFC1918 전체 (`10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`) | 사내 LAN dev/staging 전제. Codex 가 "RFC1918 전체 = 사내 클라이언트 spoof 위험" Major 지적했으나 사용자 명시 결정으로 채택. SECURITY.md §9.7 에 trade-off 명시 |
| malformed env 동작 | prod/staging fail-loud (`RuntimeError`) + dev/test stderr WARNING | Codex 권고 그대로. mode-aware — 운영자 인지 보장 + dev/test fixture/CI 부담 완화 |

#### Phase 분해 (A → E)

- **Phase A** — Caddy XFF 정규화 (feature-0006-lan-proxy-access)
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가. Caddy 가 받은 임의 XFF 를 본인이 본 TCP peer IP 로 덮어쓴다. 단일 hop 정규화 → multi-hop / spoof 차단.
- **Phase B** — `_get_client_ip()` 조건부 trust (feature-0003-agent-web-ui)
  - `app.py` 의 imports 에 `ipaddress`, `sys` 추가
  - `_parse_trusted_proxies(raw)` helper: 콤마 분리 + `ipaddress.ip_network(token, strict=False)` 파싱. invalid 토큰은 `AGENT_MODE in {prod, staging}` 에서는 `RuntimeError` startup, dev/test 에서는 stderr WARNING + skip
  - module-level `WEB_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("WEB_TRUSTED_PROXIES", ""))`
  - `ENABLE_WEB_TLS_PROXY=1` + `WEB_TRUSTED_PROXIES` empty → prod/staging RuntimeError, dev/test stderr WARNING (PIPA §29 audit 품질 회귀 경고)
  - `_is_trusted_proxy(host)` helper: host 가 `WEB_TRUSTED_PROXIES` CIDR 화이트리스트 안인지 검증
  - `_get_client_ip(request)` 재작성: direct_ip 가 trusted proxy 일 때만 XFF 첫 토큰 사용 + `ipaddress.ip_address(first)` 파싱 실패 시 direct_ip fallback. 그 외 모두 direct_ip 반환
- **Phase C** — `docs/SECURITY.md §9.7` 갱신
  - 기존 "deferred to feature-0006" 마커를 8 bullet (Caddy XFF 정규화 / 조건부 trust / XFF token 검증 / RFC1918 사용자 명시 결정 trade-off / mode-aware fail-loud / proxy mode + empty / schema 호환 / share token 미래 결합) 정책으로 교체
- **Phase D** — docs (양 feature)
  - feature-0003: TASK.md TASK-0087 checkbox close + §2.9 (본 plan), MODIFY CHG-20260520-0010, REVIEW REV-20260520-0010, REPORT §1 cycle entry, TEST §4 8 시나리오, FUNCTION AC-0205~0207
  - feature-0006: TASK.md TASK-0006 신규 entry + Task Queue, MODIFY CHG-20260520-0010 (Caddy XFF 정규화 dual ownership), REVIEW REV-20260520-0010, REPORT §1 entry, TEST §2 Caddyfile validate 시나리오, FUNCTION AC-0004
- **Phase E** — verify-completion + commit + cycle-finalize
  - `bin/verify-completion.sh` 10 checks PASS (특히 #6 ANCHOR + #7 audit endpoint routing + #10 worktree binding)
  - commit + push + PR + main merge + worktree cleanup

#### Test 시나리오 (Codex 권장 8건)

TEST.md §4 에 추가:
1. trusted_proxy + valid XFF → XFF 첫 토큰 반환
2. trusted_proxy + invalid XFF (`garbage`) → direct_ip fallback
3. trusted_proxy + XFF 첫 항목 빈 문자열 → direct_ip fallback
4. untrusted direct_ip + XFF → direct_ip 반환 (spoof 차단)
5. IPv6 direct_ip (trusted) + IPv6 XFF → XFF 첫 토큰
6. invalid env CIDR + `AGENT_MODE=prod` → `RuntimeError` startup
7. empty env + `ENABLE_WEB_TLS_PROXY=1` + `AGENT_MODE=prod` → `RuntimeError` startup
8. `caddy validate` 가 Caddyfile 통과 + `header_up X-Forwarded-For {client_ip}` 인식

#### outside voice 결과 (REVIEW.md REV-20260520-0010 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 228,107 tokens):
- 6 findings (Major 5 + Minor 1) — Verdict: **NEEDS_REVISION**
- Major 1 (RFC1918 전체 trust 위험): **사용자 명시 거부** — RFC1918 default 유지. trade-off 는 SECURITY.md §9.7 에 명시
- Major 2 (Caddy 문법 부정확) → 흡수: `reverse_proxy` 안의 `trusted_proxies` 대신 `header_up X-Forwarded-For {client_ip}` 로 단일 hop 정규화 (더 안전한 대안)
- Major 3 (Caddy `private_ranges` global trust 위험) → 흡수: global trusted_proxies 추가 안 함 (Major 2 와 동일 결정)
- Major 4 (malformed XFF IP 검증 누락) → 흡수: `ipaddress.ip_address(first)` 검증 후 반환, 실패 시 direct_ip fallback
- Major 5 (malformed env silent skip) → 흡수: mode-aware (prod/staging RuntimeError + dev/test WARNING)
- Minor 1 (silent regression warning) → 흡수: proxy mode + empty env 조합에 RuntimeError + WARNING

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0087 Phase A~E 일괄, Major 등급 보안 표면 + multi-feature, Codex outside voice 5 Major + 1 Minor 흡수) -->

---

### 2.1 Implementation Plan (TASK-0072)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Critical 등급 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-18 에 Plan 구조 + 권장안 3 항목 (권한·검색 범위·UI 위치) 일괄 승인 → outside voice 3 개 (adversarial / security / ux) dispatch → 종합 후 사용자 추가 결정 3 항목 (UI 위치 재결정·D1·본문 열람 정책) 반영. D1/D2/D3 + 4 must-fix + 3 sub-spec + 6 risk 모두 plan 에 흡수.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0072 Phase A0~E 일괄, Critical 등급 PII 표면 신설 + WebAccountActivity DDL 포함) -->

#### 사용자 in-cycle 결정 (5 항목)

| 결정 | 채택안 | 근거 |
|---|---|---|
| 권한 모델 | 기존 `conversation.list.any` 재활용 | 신규 catalog 없이 빠르게 진입. `.own` only 는 본인 대화 내 검색만 |
| 검색 범위 | 제목 + 계정명 + 메시지 본문 | SQL/결과셋은 list 단계 제외 — PII 노출 면적 최소 |
| UI 위치 (재결정) | **Spotlight modal pattern (Cmd/Ctrl+K)** | UX BLOCKER — 252px 사이드바에 chip 4개 fit 불가. 사용자 명시 변형: brand 가 아니라 "+ 새 대화" 영역 우측 같은 높이에 돋보기 icon. modal overlay 로 full search UI |
| D1 본문 search index | **A: LIKE + 강한 안전망** | 한국어 FULLTEXT 는 `ngram` parser + `innodb_ft_min_token_size` 튜닝 필수 → Critical migration. 신규 PII 표면과 interleave 회피. FULLTEXT 는 별 cycle 분리. min 3 char + LIMIT 50 + per-account rate 10/min + max_execution_time 3s |
| 본문 열람 정책 | **`.any` 보유자 = 검색 매칭 + snippet 모두 허용, audit log 수반** | admin/operator 의 감사 needs 우선. `WebAccountActivity` 신설로 PIPA §29 준거 (접근기록 보관) |

#### outside voice 종합 결정 (D2 / D3 — 의견 일치)

| # | 결정 | 근거 |
|---|---|---|
| D2 | **A: snippet 항상 OFF + chip opt-in** | security + adversarial 일치 — `.any` 보유자 기본 ON 시 user interaction 전에 snippet leak. opt-in chip 클릭 자체도 audit log 대상 (의도 추적 가능) |
| D3 | **B: cursor `(updated_at DESC, conversation_id DESC)`** | offset 은 기존 `app.py:2849` LIMIT 200 + `2967-2971` Python re-sort 와 incoherent — page 2 가 stale subset 반환. cursor 가 안전 |

#### adversarial 3 sub-spec (Phase A 진입 차단 → 반영 후 진입)

기존 `_list_conversations` 의 코드 패턴이 search 와 호환되지 않으므로 다음 3 sub-spec 을 Phase A 에서 반드시 동시 적용:

1. **SQL composition order** — `owner_id = self` 가 q / owner_id / product_id 보다 **항상 먼저** AND. `.any` 미보유자 코드패스 에서도 owner_id WHERE 가 q 매칭보다 우선 (q 의 결과가 owner_id 매칭 *교집합* 으로 strict 적용). 응답 byte-equal (404 vs 403 metadata leak 차단).
2. **`hidden_ids` SQL push** — Python post-filter (`app.py:2855-2866`) 폐기, `c.conversation_id NOT IN (…)` 으로 SQL 내 이전. LIMIT 50 과 호환.
3. **Python re-sort 삭제** (`app.py:2967-2971`) — SQL `ORDER BY c.updated_at DESC, c.conversation_id DESC` 단일화. cursor pagination 정합.

#### Must-fix 4 (security + adversarial)

1. **Audit log 신설** — `WebAccountActivity` 테이블 (`id, account_id, action, target_owner_id, query_hash, matched_count, ts`). `.any` 보유자가 본문 search 실행 / snippet chip 활성화 시 INSERT. query 평문 X — SHA-256 hash 만.
2. **SQL escape 명시** — `LIKE %s ESCAPE '!'` 형식. `%`, `_`, `!` 3 문자 escape (default `\\` ESCAPE 의 NO_BACKSLASH_ESCAPES sql_mode 회귀 차단).
3. **Per-account rate limit** — in-process token bucket 10 req/min for body-search requests. `max_execution_time=3000ms` 동시 적용.
4. **본문 검색 min 3 char + length cap 200** — escape 후 의미 literal char ≥ 2 추가 gate (`q="%%"` post-escape 0 char 차단). 한글 grapheme 기준 `len(q.strip())`.

#### Additional risk 6 (adversarial)

1. **`WebAccounts.DeletedAt` 필터 누락** — 현재 `app.py:2842` LEFT JOIN 이 DeletedAt 미체크. 삭제 user 본문 search 시 username verbatim leak. `AND owner.DeletedAt IS NULL` 추가 (또는 `(deleted user)` 명시 렌더).
2. **Collation 일치 audit** — `AgentMemoryMessages.Content` + `AgentCoreMessages.content` 가 `utf8mb4_unicode_ci` 인지 Phase A 시작 시 확인. mismatch 시 풀스캔.
3. **Account-name search `.any` 한정** — `.own` 사용자 q="kim" 의 경우 owner.Username 매칭은 본인 conv 만 (owner_id WHERE 이미 강제). 정상.
4. **`q="%%"` post-escape 0 char 차단** — must-fix #4 와 통합.
5. **404 vs 403 byte-equal response** — must-fix #1 의 SQL composition order + 동일 empty result shape 보장.
6. **`share.js` 회귀 가드** — `share.html` / `share.js` (TASK-0058 Phase D) 가 신규 searchbar/modal 코드 import 안 함. modal element 는 `index.html` 에만 mount.

#### 영향 파일 (최종)

Backend:
- [src/app.py](../src/app.py) — Phase A0 (`WebAccountActivity` 테이블 신설 + `_ensure_web_tables` 추가), Phase A1 (`_list_conversations()` 확장 + 3 sub-spec 적용 + cursor pagination + ESCAPE 절 + min 3 char gate + rate limit + audit insert), Phase A2 (`/api/conversations` query param 수신 + `_log_search_activity` helper + `max_execution_time` SET SESSION).

Frontend:
- [src/static/app.js](../src/static/app.js) — Phase C1 (`state.searchModal: {open, q, owner_id, product_id, date_from, date_to, snippet_opt_in, cursor}` + `openSearchModal()` / `closeSearchModal()` + Cmd/Ctrl+K 단축키 + Esc handler + 300ms 디바운스 + cursor pagination), Phase C2 (`loadConversations()` 가 `search` mode 시 modal 결과 영역에 렌더, sidebar conv-list 는 unchanged).
- [src/static/index.html](../src/static/index.html) — `.sidebar-head` 의 "+ 새 대화" button 우측에 같은 높이 `#openSearchBtn` (돋보기 icon, aria-label="대화 검색 (Ctrl+K)"). `#searchModalOverlay` modal element (input + 4 facet + result list).
- [src/static/styles.css](../src/static/styles.css) — `.sidebar-head` flex 조정 (new + search 2 button row, gap), `.search-modal-overlay` / `.search-modal` / `.search-modal-input` / `.search-modal-facets` / `.search-modal-result-list` / `.search-snippet` / `.search-snippet-hl` / `--search-highlight-bg` 토큰 ~12 개. cache-bust `v=20260518-conv-search`.

문서:
- `docs/FUNCTION.md` — REQ-20260518-0010 + AC 8~10 개 (audit log + RBAC gate + cursor + Cmd/Ctrl+K + Esc 정책 포함).
- `docs/TASK.md` — 본 §2.1 + Task Queue entry + Completion Checklist.
- `docs/MODIFY.md` — Phase 별 CHG entry (6 phase).
- `docs/REVIEW.md` — outside voice 3 개 verdict 요약 + D1~D3 결정 근거 + 사용자 in-cycle 결정 5 항목 + Adversarial 3 sub-spec 흡수 이력 + Must-fix 4 + Additional risk 6 + 본 plan 의 변경 이력.
- `docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과.
- `docs/TEST.md` — TEST 케이스 정의 (§2 rewrite) — Phase B 의 4 토큰 cross-account smoke + audit log assert + ESCAPE 절 SQL injection probe + cursor pagination 정합 + min 3 char gate + rate limit 11번째 요청 429.
- 프로젝트 수준: `repo/docs/SECURITY.md` §7 (anonymous endpoint allowlist) 아래 §8 cross-account search policy 신설 + `WebAccountActivity` audit 정책, `repo/docs/STATUS.md` feature-0003 row 갱신.

#### Phase 순서 (최종)

1. **Phase A0 — WebAccountActivity DDL** — `_ensure_web_tables` 에 `CREATE TABLE IF NOT EXISTS WebAccountActivity` 추가 + `_log_search_activity(conn, account_id, action, target_owner_id, query, matched_count)` helper. py_compile + 컨테이너 재시작으로 DDL 적용 확인.
2. **Phase A1 — `_list_conversations` 확장** — 3 sub-spec 적용 (SQL composition order / hidden_ids SQL push / Python re-sort 삭제) + 새 파라미터 `q, owner_id, product_id, date_from, date_to, cursor` + ESCAPE 절 + min 3 char gate + DeletedAt 필터 + collation audit. py_compile.
3. **Phase A2 — `/api/conversations` query param + rate limit** — endpoint 가 query param 수신, body search 시 rate limit 확인 후 `_log_search_activity` 호출. `max_execution_time` SET SESSION. py_compile + HTTP curl smoke.
4. **Phase B — HTTP smoke 6 시나리오** — `tests/test_search_rbac.py` 신설: (1) `.own` only + q=상대 키워드 → 본인 매칭만, (2) `.any` + 동일 q → 전체 매칭, (3) `.own` + owner_id=상대 → response byte-equal with owner_id=999999, (4) cursor 페이지 2 가 페이지 1 과 disjoint, (5) `q="%%"` → 400 reject, (6) rate limit 11번째 → 429.
5. **Phase C — Frontend** — Spotlight modal + 돋보기 icon + Cmd/Ctrl+K + Esc + 300ms 디바운스 + cursor pagination + snippet opt-in chip + a11y (aria-live, focus trap, Tab order). node --check.
6. **Phase D — 문서 + SECURITY policy + STATUS** — FUNCTION / MODIFY / REVIEW / REPORT / TEST 일괄.
7. **Phase E — verify-completion + commit** — `make web` 재배포 + browser smoke (Cmd+K open / q="test" 입력 / Esc close / snippet chip toggle) + `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` + 사용자 명시 commit confirm 후 진행.

#### 위험도 평가 (재평가)

| 영역 | 위험도 | 보강 |
|---|---|---|
| RBAC bypass | Critical | 3 sub-spec 강제 (SQL composition order / hidden_ids SQL push / re-sort 삭제) + Phase B 6 시나리오 smoke + 404/403 byte-equal |
| PII leak (snippet + cross-account body) | Critical | snippet opt-in 기본 OFF + WebAccountActivity audit + SHA-256 hash + `.any` 한정 |
| SQL injection | Major | bound param + `ESCAPE '!'` 명시 + escape 후 의미 char ≥ 2 추가 gate |
| 성능 회귀 (LIKE full scan) | Major | LIMIT 50 + min 3 char + per-account rate 10/min + max_execution_time 3s + collation audit + FULLTEXT 별 cycle |
| 회귀 (기존 `.own` 사용자) | Minor | 빈 query 일 때 기존 동작 100% 유지 (early return) |
| WebAccountActivity DDL | Major | `_ensure_web_tables` idempotent + `CREATE TABLE IF NOT EXISTS` + index `(account_id, ts)` 만 |
| share-link 회귀 | Minor | `share.js` 신규 import 없음 (Phase C 가드) |

**전체 등급**: Critical (PII 표면 신설 + DDL 1 + RBAC scope 확장 효과).

#### 검증 계획

각 Phase 종료 후:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`

전체 완료 후:
- (c) Phase B 의 HTTP smoke 6 시나리오 (`tests/test_search_rbac.py`)
- (d) `make web` — 컨테이너 재배포 + browser smoke (Cmd+K / Esc / snippet toggle / cursor 페이지 / 0 match empty state)
- (e) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

#### outside voice 결과 요약 (REVIEW.md 정본)

3 review verdict:
- **Security**: FIX-FIRST → 4 must-fix (audit log / ESCAPE / FULLTEXT or LIKE 안전망 / rate limit) 흡수
- **Adversarial**: Blocker (3 sub-spec) + D1 A + D2 A + D3 B + 6 risk → 모두 흡수
- **UX**: NEEDS-TWEAK (사이드바 fit 불가) → Spotlight modal 패턴으로 UI 위치 재결정 → 사용자 변형 채택 ("+ 새 대화" 우측 돋보기 icon)

REVIEW.md REV-20260518-0010 에 각 review 의 전체 verdict + plan 흡수 이력 + 결정 근거 기록.

---

### 2.1 Implementation Plan (TASK-0061)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 변경 계획이다. **상태**: `approved`. 사용자가 2026-05-15 에 Phase 1~8 일괄 승인 + 비밀번호 초기화 권장안 (MustChangePassword + 임시비번 1회 표시 + 세션 revoke + self-reset 금지) 채택을 명시했다. 사용자의 명료화: "관리자 계정의 비밀번호 초기화가 아닌, 관리자 주관으로 특정 계정의 비밀번호를 초기화 하는 기능" — AC-0093 (self-reset 거부) 의도와 정합.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-15 (TASK-0061 Phase 1~8 일괄, Phase 6 Critical 분면 포함) -->

#### 영향 파일 요약

Backend:
- [src/app.py](../src/app.py) — Phase 3 (`_compute_display_status` + WEB_PROGRESS_STALE_TIMEOUT_SECONDS env + `/api/progress` / `/api/ask_status` / `/api/ask_result` / `_list_conversations` 일관 반영), Phase 5 (`/api/history_dates` 가 `AgentMemoryMessages` 기준으로 SELECT 변경), Phase 6 (`WebAccounts.MustChangePassword` ALTER + `_ensure_web_tables` / `_ensure_seed_catchup` idempotent helper + `POST /api/admin/accounts/{account_id}/password-reset` endpoint + `/api/auth/login` 응답에 `must_change_password` 추가 + `/api/auth/me` PATCH 가 비밀번호 변경 성공 시 `MustChangePassword=0`), Phase 8 (`_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` endpoint).

Frontend:
- [src/static/app.js](../src/static/app.js) — Phase 1 (`state.pendingBubble` + `renderPendingAssistantBubble()` + `applyProgressPayload()` 가 pending bubble 동시 갱신 + elapsed timer interval + `renderMessages()` 가 pending state 가 있으면 사용자 message + pending bubble 즉시 prepend), Phase 2 (`sendPrompt()` lazy-create 분기에서 pending bubble 진입 + `/api/ask` 응답 직후 polling start), Phase 3 (`renderConversationList()` 가 `display_status === "stale_error"` 시 `.is-stale-error` dot 사용 + tooltip), Phase 4 (`#messagePointRail` 컨테이너 + `renderMessagePointRail()` + scroll/click handler), Phase 5 (`historyCalendarBtn` + popover + `/api/history_dates` 호출 + `/api/history_anchor` jump), Phase 6 (`/api/auth/login` 응답에서 `must_change_password` 처리 — 강제 modal), Phase 8 (`state.conversationSelected: Set<string>` + `state.conversationLastClickIdx` + `conv-item-checkbox` 추가 + Ctrl/Shift click handler + `.conv-bulk-bar`).
- [src/static/admin.js](../src/static/admin.js) — Phase 6 (Account detail 에 `adminPasswordResetBtn` + modal 표시 + 임시 비밀번호 복사 액션), Phase 7 (accountSelectAll change handler 가 `filteredAccounts()` 의 `accountPage` slice 만 대상으로 변경 + `updateAccountSelectAllCheckbox()` 도 동일 helper 사용 + Roles/Products select-all 도 동일 정책 정합화).
- [src/static/index.html](../src/static/index.html) — Phase 4 (`#messagePointRail` 컨테이너), Phase 5 (`historyCalendarBtn` + popover container), 그 외 ID 추가.
- [src/static/admin.html](../src/static/admin.html) — Phase 6 (Account detail 의 `adminPasswordResetBtn` slot — `renderAccountDetail()` 에서 동적 mount 도 가능하지만 cache-bust 위치 정의).
- [src/static/styles.css](../src/static/styles.css) — Phase 1 (`.message.is-pending` + spinner + elapsed + step list 토큰), Phase 3 (`.conv-dot.is-stale-error` red 토큰), Phase 4 (`.message-point-rail` + `.message-point-dot`), Phase 5 (`.history-calendar-popover` + grid), Phase 6 (`.admin-password-reset-modal` + `.temp-password-display`), Phase 8 (`.conv-item-checkbox` + `.conv-bulk-bar`).

문서:
- `docs/FUNCTION.md` — 본 commit 에 REQ-20260515-0003 ~ 0010 + AC-0070 ~ AC-0107 이미 추가됨.
- `docs/TASK.md` — 본 §2.1 + Task Queue entry + Completion Checklist.
- `docs/MODIFY.md` — Phase 별 CHG entry (8 phase).
- `docs/REVIEW.md` — Phase 1 (호환 차원에서 `#progressCard` 유지 결정), Phase 3 (env 기본값 20 분 결정 근거 — 장시간 SQL/LLM 작업 고려), Phase 6 (1 회 표시 / 평문 저장 금지 / MustChangePassword 강제 / 세션 revoke / self-reset 금지 보안 정책 결정), Phase 7 (bulk delete partial success + ≥10 typed-confirm 결정), Phase 8 (bulk delete partial success 채택, rollback 미선택 사유).
- `docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과 (§16.5 Step 6).
- `docs/TEST.md` — TEST 케이스 정의 (§2) rewrite + 실행 결과 (§3) append.
- 프로젝트 수준: `repo/.env.example` — `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` 추가, `repo/docs/STATUS.md` feature-0003 row 갱신, `repo/docs/SECURITY.md` 비밀번호 초기화 정책 1 줄 추가.

#### 접근 방법 (Phase 순서)

순서는 의존성 최소화 + 빠른 검증 가능성 기준으로 정렬했다. 각 Phase 끝마다 python compile + node --check 가능하도록 분할.

1. **Phase 3 (backend stale 감지) 먼저** — 가장 자족적인 backend 변경. helper + env 추가 + 3 endpoint 응답 + conversation list status. 검증: `/api/progress` HTTP 응답에 stale 가 정확히 들어가는지.
2. **Phase 1 (답변 버블 live progress)** — frontend 핵심. `state.pendingBubble` 자료구조 + render + applyProgressPayload 갱신 + elapsed timer + `renderMessages()` 분기. Phase 3 의 status 가 stale 일 때 pending bubble 에서도 오류 영역 노출.
3. **Phase 2 (신규 대화 첫 polling)** — Phase 1 의존. lazy-create 분기에서 pending bubble 진입 + `/api/ask` 응답 직후 polling start. 회귀: 기존 대화 ask 흐름은 변경 없음.
4. **Phase 4 (Point rail)** — Phase 1 의 message rendering 위에 build. scroll observer + click handler.
5. **Phase 5 (캘린더)** — Phase 4 와 무관. backend `/api/history_dates` 의 source table 변경 + frontend popover. timezone 은 server 의 DATE() 그대로 (UTC).
6. **Phase 7 (admin select-all fix)** — 자족적인 frontend bug fix. 그 다음 Phase 6 (Critical) 직전에 끊어서 사용자 confirm 요청.
7. **Phase 8 (bulk delete)** — backend helper + endpoint + frontend selection state + UI. 단건 endpoint 와 동일 가드 재사용.
8. **🛑 Phase 6 (비밀번호 초기화 — Critical confirm) 직전 STOP** — DB schema 변경 (`MustChangePassword`) + 인증 응답 contract 변경 + 임시 비밀번호 노출. 사용자 명시 confirm 받은 후 Execute.

#### 위험도 평가 (§12.3)

| Phase | 변경 영역 | 위험도 | 사전 승인 |
|------|-----------|--------|----------|
| Phase 1 | frontend UI 상태 추가 | Minor | plan-review 만 |
| Phase 2 | frontend lazy-create UX | Minor | plan-review 만 |
| Phase 3 | backend status helper + env | Major (운영 환경변수 + 표시 정책) | plan-review |
| Phase 4 | frontend UI 추가 | Minor | plan-review 만 |
| Phase 5 | backend SELECT source 변경 | Minor | plan-review (회귀 가능성) |
| Phase 6 | **인증 모델 + 비밀번호 + 세션 revoke** | **Critical** | **사용자 명시 confirm** |
| Phase 7 | frontend bug fix | Minor | plan-review 만 |
| Phase 8 | **파괴적 데이터 일괄 삭제 + 신규 endpoint** | **Major** | plan-review (cross-account leak 위험 없음 — owner 가드 보존) |

**전체 등급**: Major (Phase 1~5, 7, 8 은 plan-review 마커 부여로 Execute. Phase 6 는 별도 Critical confirm).

#### 검증 계획

각 Phase 종료 후:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- (c) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`

전체 완료 후:
- (d) `make web` — 컨테이너 재배포
- (e) browser 검증 (gstack `/browse` 또는 make browser-*) — 8 시나리오 (GOAL.md §5 필수 브라우저 확인 8 항목) 실측 + screenshot 첨부.
- (f) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

#### 미결정 사항의 결정 (GOAL.md §7)

| 항목 | 결정 | 사유 |
|------|------|------|
| 비밀번호 초기화: MustChangePassword vs 임시비번+revoke only | **MustChangePassword 채택** | GOAL.md 권장 + 보안 우위. 1 회 임시 비밀번호 + 세션 revoke + 다음 로그인 시 강제 변경 |
| `#progressCard` 유지 vs 축소 | **유지** | 호환성. 사용자별 collapsed 상태는 localStorage 보존 |
| bulk delete partial vs rollback | **partial success + 결과 요약** | admin bulk UX 일관성 (AC-0035 와 정합) |
| stale 만료시간 기본값 | **1200 sec (20 분)** | 장시간 SQL/LLM 작업 고려한 보수적 기본값. env 로 override 가능 |

#### 사용자 승인 마커

Phase 1~5, 7, 8 (Major) 진행 승인 시 본 plan 의 PLAN-APPROVED 마커는 §2 Task Queue 의 기존 마커를 재사용한다 (사용자가 이미 GOAL.md 의 진행 의도를 명시함). Phase 6 (Critical) 진입 직전 별도 마커:
```md
<!-- PLAN-APPROVED-PHASE-6 by <user> on YYYY-MM-DD -->
```

### 2.1 Implementation Plan (TASK-0060)

영향 파일 / 데이터:
- `agent_memory.WebSystemPrompts` — Product prompt 2건, Role 공통 prompt 5건 upsert
- `../feature-0002-agent-core/src/agent_core.py` — Role 공통 prompt 누적 적용
- `../feature-0002-agent-core/tests/test_compose_system_prompt.py` — 누적 적용 회귀 테스트
- `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md` 및 feature-0002 문서

접근 방법:
1. `WebProducts`와 `WebProductDatabases`에서 Product별 접근 DB 목록을 확인한다.
2. 각 접근 DB에 대해 `information_schema.TABLES/COLUMNS`와 제한적 집계 쿼리로 테이블 수, 주요 테이블, 시간 범위, 민감 컬럼 성격을 확인한다.
3. 확인한 사실만 Product scope 시스템 프롬프트에 반영한다. 비밀번호/토큰/기기 식별자 등 민감 컬럼은 원문 노출 금지 지침으로 명시한다.
4. Role `pending/operator/admin/sales/dba`의 `ProductId IS NULL` prompt 를 역할명에 맞게 작성한다.
5. runtime 조립은 feature-0002에서 `전 Product 공통` Role prompt 누적 방식으로 수정하고 테스트한다.

위험도: Minor — 비파괴 데이터 upsert + LLM 입력 패키징 수정. 인증/인가 catalog, DB schema, 삭제/파괴 작업 없음.

### 2.1 Implementation Plan (TASK-0059)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 변경 계획이다. 사용자 승인 (2026-05-15) 으로 진행.

**영향 파일**:
- [src/static/app.js](../src/static/app.js) — `sendPrompt()` askBody 에 `lazy_create` hint (lazy 경로 한정), `loadConversations()` 의 active id 덮어쓰기에 pending 가드
- [src/app.py](../src/app.py) — `_resolve_conversation_for_account` 시그니처에 `force_new=False` kwarg 추가, `/api/ask` 의 빈 `request_conversation_id` 경로가 `lazy_create` body hint 를 `force_new=True` 로 위임

**접근 방법**:
1. Frontend `sendPrompt()` 의 askBody 구성 시 `isLazyCreate` 일 때만 `lazy_create: true` 를 추가 (기존 대화 ask 에는 추가 안 함 — 의미 변경 0).
2. Frontend `loadConversations()` 가 `state.pendingNewConversation` true 일 때는 `state.activeConversationId` 를 덮어쓰지 않음 — 사이드바 리스트와 backend `current` 는 갱신하되 active id 보존.
3. Backend `_resolve_conversation_for_account` 에 `force_new=False` kwarg 추가. requested_id 가 truthy 이면 기존 동작 (force_new 무시), 빈 문자열이면 `_repair_current_conversation(..., force_new=force_new)` 로 위임. `_repair_current_conversation` 은 기존에 `force_new=True` 시 visible fallback 차단 + 새 cid 생성 로직을 이미 가짐 — body 변경 없음.
4. `/api/ask` 의 빈 `request_conversation_id` 경로에서 `lazy_create_requested = bool(data.get("lazy_create"))` 추출 후 `_resolve_conversation_for_account(..., create_if_missing=True, force_new=lazy_create_requested)` 호출. hint 없는 legacy client (예: 첫 로그인 후 직전 대화 자동 이어받기 흐름) 는 force_new=False → 기존 동작 유지.

**위험도**: **Major** §12.3 — 사용자 대화 routing 데이터 영역. 인증/인가 catalog·endpoint guard·owner check 무변경. `_account_can_access_conversation` / `_conversation_owned_by_account` 검사는 기존 그대로 유지되며 force_new 경로는 새 cid 를 생성하므로 owner 가 즉시 본 계정으로 assign 됨 (`_assign_conversation_owner(force=True)`). cross-account leak 가능성 없음.

**검증**:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- (c) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

- [x] TASK-0058 (REQ-20260514-0001, **Critical** §12.3 — 인증/인가·개인정보·외부 공개 범위 변경) 대화 공유 링크 기능 도입. anonymous 접근 가능한 read-only view + 로그인 viewer 의 fork. 사용자 결정 6 항목 (외부 anonymous 허용 / 무기한 + revoke / read+fork / full+anchored / `conversation.share.create` 신설 / 메시지+SQL+결과셋 노출) 와 codex outside voice review 의 blindspot 보강 (B1 메시지 테이블 이중성 — AnchorMessageId 는 `AgentMemoryMessages.Id` 기준 inclusive `Id <= anchor`, B2 `_optional_account` 헬퍼 신설, R4 `_fork_conversation_impl` 추출로 share-grant 가 read-gate 우회, R6 revoke+view race-free 단일 UPDATE, R7 file attachment 자동 hide, R8 token 충돌 retry, R10 share.html FileResponse mount) 반영. **Phase A**: `PERMISSION_DEFINITIONS` 에 `conversation.share.create` 추가 (catalog 33→34, group=conversation), `SEED_ROLE_DEFINITIONS` operator/sales 에 grant + admin 보정 list 에 추가, `WebConversationShares` 테이블 신설, `_ensure_web_conversation_shares_schema(conn)` helper 가 slow path + fast path 양쪽 idempotent 호출, fast path catchup 에 `_ensure_permission_catalog(conn)` 추가로 신규 권한 hydrate. **Phase B**: `_optional_account` + `_fork_conversation_impl` 헬퍼 + 5 endpoint (POST/GET share[s], DELETE share, GET/POST public/share/{token}[/fork]). Token = `secrets.token_urlsafe(32)`. `/share/{token}` FileResponse route. **Phase C**: 헤더 `shareConversationBtn` (gated by `conversation.share.create`) + 메시지 hover "여기까지 공유" + `createConversationShare` 함수 (clipboard copy + toast). 권한 label/description 매핑 추가 → CONVENTIONS.md §10.6 conversation section 에 자동 합류. **Phase D**: `share.html` / `share.css` / `share.js` 신규 정적 파일 — anonymous accessible read-only view (메시지 + SQL `<pre>` + 결과셋 `<table>`), 로그인 + can_fork 시 "내 계정에서 fork" 버튼. **Phase E**: 본 entry + FUNCTION.md REQ-20260514-0001 (AC-0053~AC-0060), MODIFY.md / REVIEW.md, project-level [`docs/SECURITY.md`](../../../docs/SECURITY.md) 에 anonymous endpoint 2 곳 명시 + 외부 배포 시 IP 제한/비밀번호 보호 후속 cycle 권장, STATUS.md feature-0003 row 갱신.

### 2.1 Implementation Plan (TASK-0058)

영향 파일:
- `unit/feature-0003-agent-web-ui/src/app.py` (RBAC catalog + 부트스트랩 schema helpers + 5 endpoint + helper refactor)
- `unit/feature-0003-agent-web-ui/src/static/app.js` (헤더 share 버튼 + 메시지 hover share + `createConversationShare` + 권한 매핑)
- `unit/feature-0003-agent-web-ui/src/static/index.html` (헤더 share 버튼 1줄)
- `unit/feature-0003-agent-web-ui/src/static/share.html` / `share.css` / `share.js` (신규 anonymous view)
- `unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW}.md` + `docs/{STATUS,SECURITY}.md`

접근 방법: A=infra/RBAC catalog, B=Backend 5 endpoint + helper refactor, C=Frontend logged-in, D=Anonymous view, E=Docs. Phase 별 비파괴 추가이므로 각자 verify 가능. Token = 256-bit URL-safe, UNIQUE 충돌 retry loop. revoke + view 카운터는 동일 UPDATE 로 race-free.

위험도 평가: **Critical** §12.3 — 인증/인가 catalog 확장 + anonymous public endpoint 2 곳 신설 + SQL 결과셋 외부 노출. SECURITY.md §3 의 3 항목 동시 변경. 사용자가 사내 IP 가정으로 anonymous 허용 결정. 외부 배포 전 IP 제한/비밀번호 보호 후속 cycle 필요.

- [x] TASK-0056 (REQ-20260512-0002, **Major** §12.3 — frontend 권한 정렬 + project-level 컨벤션 1 절) 작업 화면·관리 콘솔 권한 정렬을 화면 맥락별로 분리. 두 화면이 같은 `console→account→role→conversation→[product]→misc` 순서를 공유해 admin 메타권한이 두 곳 모두 위에 노출되던 UX 회귀 fix. (1) [docs/CONVENTIONS.md §10.6](../../../docs/CONVENTIONS.md) 화면별 권한 섹션·정렬 정책 신설 — 작업 화면 = "운영→관리→기타", 관리 콘솔 = "관리→운영→기타" 2단 section. (2) **admin.js**: `ADMIN_PERMISSION_SECTIONS` 상수 + `sectionedGroupedPermissions` 함수 + `renderPermissionGrid` 가 outer section header (`.permission-section`) 로 inner group `<details>` 들을 감싸도록 수정. (3) **app.js**: `PERMISSION_GROUP_ORDER` 에 `product` 추가 (누락 fix), `PERMISSION_GROUP_LABELS.product`, `WORK_SCREEN_PERMISSION_SECTIONS` 상수, `permissionGroupOf()` 가 `system_prompt.` 를 product 로 매핑, `PERMISSION_LABELS/_DESCRIPTIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가, `buildPermissionPills` 가 2단 묶음 (`.perm-section-meta`) 으로 렌더 + 빈 section 자동 hide. (4) **styles.css**: `.perm-section-meta*` 5 클래스 + `.permission-section*` 5 클래스 + section 간 gap 중첩 제거. (5) cache-bust `v=20260512-perm-sections`. DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 0 — 인가 모델 무영향. node --check 양 파일 통과.
- [x] TASK-0055 (REQ-20260512-0001, **Major** §12.3 — admin console UI 정합 컨벤션 정립 + 코드 통일, 사용자 명시 AI 자율 commit/push) 관리 콘솔 카테고리별 다중선택 UX 정합 컨벤션 도입. 사용자 보고: "계정=우상단 / 역할=좌하단 / 제품=다중선택 부재" 의 카테고리 간 일관성 결여. 본 cycle = **정책 + gstack design 외부 시각 + Core+keyboard+advanced 코드 통일 합본**. (1) [docs/CONVENTIONS.md §10](../../../docs/CONVENTIONS.md) 프로젝트 수준 정책 신설 — 다중선택 적용 룰, DOM anchor 표준, 자료구조 invariant, 단위 어휘, 신규 카테고리 체크리스트. (2) [DESIGN.md](./DESIGN.md) 신규 — feature-local 상세 명세 (HTML 구조, CSS 토큰, Set/invariant, runtime assertion, §5 컴포넌트 set, §6 cross-page banner, §7 typed-confirm, §8 RBAC partial-fail UI, §9 keyboard map, §10 a11y, §11 렌더 cycle, §12 Products 마이그레이션). (3) **admin.html / styles.css / admin.js 코드 통일**: Accounts bulk bar 헤더 우상단 → list 직하단 sticky 이전 (DOM anchor 표준), Products multi-select 신설 (`productSelected: Set<number>`, row checkbox, select-all, bulk bar, cross-page banner), keyboard 단축키 (shift-click range + Esc 선택 해제), cross-page banner (Stripe pattern), confirm typed-confirmation (≥10 건 danger), RBAC partial-fail toast (skipped count chip), runtime assertion (`assertBulkBarContract`), a11y 강화 (`role="toolbar"`, `aria-live="polite"`, `role="grid"`, `aria-multiselectable`, checkbox `aria-label`). 외부 design 시각 (general-purpose subagent + worker-design 차용 framework) 으로 v0.1 → v0.2 흡수 (5 gap + a11y + token + keyboard map + 모던 레퍼런스 거부 근거).
- [x] TASK-0054 (REQ-20260508-0001) PR 흐름으로 main 동기화 — feat/adopt-external-anchor-v3.2.0-rc → main (PR #2, merge `eafe4c2`, 72 commits, conflict 10 files §3.2/§16.6 자율 해결) + issue/1-github-bootstrap → main (PR #3, merge `3fd4272`, self-hosted runner + 로컬 claude CLI 전환). 머지 후 main 의 ai-* 워크플로 self-hosted 정렬 확인.
- [x] TASK-0053 (REQ-20260506-0006, **Major** §12.3 — UX + 정책 토글, AI 자율 commit/push) 신규 제품 default 정책 토글 + 권한 grid 의 product sub-catalog + Role/Account detail 의 product-카드 통합 — TASK-0052 완료 직후 사용자 follow-up. **Phase A** (사용자 in-cycle 설계 전환 2026-05-06: 정책 주체 Role → Product): `WebProducts.DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 컬럼 신설 (이전 시도였던 `WebRoles.DefaultProductAccess` 는 deprecated). POST/PATCH `/api/admin/products` 가 `default_role_access` body 수용, true=모든 role 자동 grant, false=명시 grant 만. admin UI 토글은 Product detail 에 위치 — Role detail 에서는 제거. **Phase B**: admin.js 의 권한 grid 가 `groupedPermissions({excludeDynamic: true})` 로 dynamic `product.access.*` 를 grid 에서 분리, 정적 `product.manage` 등만 남기고 동적은 product subcatalog 카드로 이전. **Phase C**: Role detail 의 system prompt editor 가 product 별 collapsible card list 로 재구성 — 각 카드에 access 토글 + role-scope prompt textarea + 마지막에 "전 Product 공통" generic card. Account detail 에는 product 별 override (allow/deny/inherit) flat card list.
- [x] TASK-0052 (REQ-20260506-0005, **Critical** 등급 §12.3 — 인증/인가 구조 변경) 계정·역할 → 제품 권한 상속/override 모델 도입 — TASK-0051 분리분 C5. `/plan-eng-review` + Codex outside voice 통합 plan 은 [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). **Phase 1A** (RBAC engine catalog 인자화 — commit 4dd1d0a) → **Phase 1B** (catalog DB-driven + product 권한 backfill + 명시적 트랜잭션 + caller-update — 본 cycle) → **Phase 1C** (G1-G8 8 endpoint guards + admin_update_account RoleId 보존 pre-existing 버그 fix) → **Phase 1D** (admin UI PERMISSION_GROUP_ORDER 'product' 그룹 추가) → **Phase 2** (HTTP smoke 6/6 P0 직접 검증 + lifecycle T13/T16 + cascade 검증). 사용자 명시 AI 자율 commit/push 권한 (2026-05-06).
- [x] TASK-0051 (REQ-20260506-0004) 관리 콘솔 일괄 저장 정책 회복 + 메타데이터 4 스키마 항상 노출 + DB 목록 라이브 enum — `프롬프트 저장` / `제품 정보 저장` / `DB 목록 저장` 3 버튼 제거 후 footer `모두 적용` 단일 commit 흐름으로 통합, 메타데이터 4 종(`information_schema`/`mysql`/`sys`/`performance_schema`) 을 회색 disabled chip 으로 강제 노출(REV-20260422-0006 정책 시각화), 자유 텍스트 chip 입력을 `GET /api/admin/databases/available` 라이브 enum 기반 picker 로 교체. C5 (제품 권한 상속/override) 는 다음 cycle 로 분리(plan-eng-review 후 진행).
- [x] TASK-0050 (REQ-20260506-0003) `make web` 의 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 우회 — Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃 추가, `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리. race 한정 무시 (image 빌드 OK + 로그에 `compose-build-metadataFile` 포함 시에만 EXIT=0 정규화).
- [x] TASK-0049 (REQ-20260506-0002) 누적된 빈 대화 일괄 정리 — `bin/cleanup-empty-conversations.sh` (dry-run 기본 + `--execute`, processing 보호 + 최근 N분 보호 + owner-account 옵션) 추가, 운영 데이터에 1회 적용 (88 → 46 conversations, 42개 정리).
- [x] TASK-0048 (REQ-20260506-0001) "새 대화" 생성 시점 lazy 화 — 버튼 클릭 시 client-side pending state 만 표시하고, 첫 메시지 전송 시 `/api/ask` 의 lazy creation path 가 실제 row 를 만들도록 전환. 신규 빈 대화 누적 방지. **CHG-20260506-0024 후속 fix**: backend `_repair_current_conversation` 의 `create_if_missing=_account_has_permission(...)` 자동 생성 분기 5 곳 (`_build_conversations_payload`, `/api/session`, `/api/history`, `/api/delete_conversation` 의 pending/일반 두 케이스) 을 모두 비활성화. 사용자 보고 회귀 "대화 삭제 시 새 대화가 그대로 남는 이슈" 의 근본 원인을 fix — delete 응답 `current` 가 backend 에서 자동 생성된 새 cid 였던 것을 빈 문자열로 정정.
- [x] TASK-0047 Product Selector + Auto 모드 진입 UX (사이드바 chip, `product_mode` 컬럼, `PATCH /api/conversations/{cid}/product`, "상품"→"제품" 일괄 치환) — agent team 4 + Codex CLI 교차검증 합의안
- [x] TASK-0046 API Vault 패널 Linear Wizard 재설계 + 단일 진입점 destructive (REQ-20260425-0001)
- [x] TASK-0045 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)
- [x] TASK-0044 사업팀(Sales) role + role-scope system prompt + 복제 DB 접속 envelope + Product whitelist 사업팀 접근 runbook — Approach A wedge pilot infrastructure
- [x] TASK-0041 클라이언트 타임아웃 시 대화 지속(Attach/Resume) — `/api/ask_status` + `/api/ask_result` long-poll + 브라우저 UX 다이얼로그 + runner attach 분기
- [x] TASK-0040 schema whitelist 정규식 context-aware 수정 (TASK-0036 회귀 — alias.column 오탐으로 합법 SQL 이 차단되는 블로커 제거)
- [ ] TASK-0034 복잡 QA 성능 테스트 (local LLM 5 직렬 + 상용 API gpt-5.4-mini 5 병렬, 최대 20턴, 실제 DB 결과 대조 검증)
- [x] TASK-0039 메타데이터 스키마(sys/mysql/information_schema/performance_schema) Product whitelist bypass 정책 도입
- [x] TASK-0038 agent_core OpenAI 호출 무제한 대기 방지 + test runner/서버 타임아웃 정렬 (TASK-0034 Q4/Q5 실패 원인 1+2 대응)
- [x] TASK-0037 진행 상황 폴링 루프 중복/축적 방지 리팩터 리뷰 및 문서화 (TASK-0036 부수 변경)
- [x] TASK-0036 시스템 프롬프트 Depth (Product/Role/Account) + Product 단위 DB 접근 관리
- [x] TASK-0035 대화 탭 내 계정 구분 하이라이트/정렬 + 대화/말풍선 fork 기능
- [x] TASK-0033 결과셋 말풍선 단일 스크롤 + RowCount + 첫 행/열 freeze
- [x] TASK-0032 권한 안내 UX (툴팁 서술화 + 차단 시 필요 권한 안내)
- [x] TASK-0001 Web UI 코드 이관
- [x] TASK-0002 정적 자산 이관
- [x] TASK-0003 agent 이미지 복사 경로 반영
- [x] TASK-0004 엄격한 Web UI 검증 시나리오 정의
- [x] TASK-0005 모던 UI/UX 전면 리디자인
- [x] TASK-0006 기존 사용자 식별 UI 추가
- [x] TASK-0007 키워드 학습 구조 추가
- [x] TASK-0008 로그인 버튼 브라우저 호환성 버그 수정
- [x] TASK-0009 작업 중심 콘솔 UI 재개편
- [x] TASK-0010 계정/비밀번호 기반 인증 모델 도입
- [x] TASK-0011 pending/operator/admin 권한 체계와 관리자 화면 도입
- [x] TASK-0012 대화 소유권을 계정 기준으로 전환
- [x] TASK-0013 상단 상태/키워드 관리/시간 이동 등 불필요한 UI 제거
- [x] TASK-0014 로컬 LLM false-ready 방지
- [x] TASK-0015 성공 사례 기반 UI/UX 전면 개편 (App-Shell 레이아웃)
- [x] TASK-0016 AI 작업자용 UI/UX 정책 지침 문서화
- [x] TASK-0017 프로필 드로어, 병렬 대화 지원, Admin 콘솔 개편
- [x] TASK-0018 프로필 드로어 탭 구조화, API Vault 통합, 버그 수정, 탑바 정리
- [x] TASK-0019 로컬 LLM 런타임 복구 및 alias 모델 준비
- [x] TASK-0020 내장 Local LLM 제거 및 외부 provider 참조 전환
- [x] TASK-0021 쿼리 결과셋 인라인 표시 복원
- [x] TASK-0022 Progress Strip 드롭다운 구조화 (단계 누적에 따른 채팅 영역 축소 해소)
- [x] TASK-0023 Planner 자율성 개선 (휴리스틱 없이 불필요 탐색 축소)
- [x] TASK-0024 Role/권한 구조를 RBAC + account override 모델로 재설계
- [x] TASK-0025 SQL 결과셋 Navigator(말풍선 내 스텝 탐색) 도입
- [x] TASK-0026 긴 SQL 쿼리 수평 확장 방지 (SQL 포매팅 + wrap)
- [x] TASK-0027 RBAC 세분화 반영 — Profile 권한 그룹화 + 관리 콘솔 UX 재설계
- [x] TASK-0028 Insight 시스템 및 agent-core 내부 설계 문서화
- [x] TASK-0029 관리 콘솔 재구조화 (탭 + 마스터-디테일 + 일괄 commit)
- [x] TASK-0030 assistant 말풍선 고정 폭 + 결과셋 내부 스크롤 + 펼침 스크롤 앵커
- [x] TASK-0031 관리 콘솔 내부 스크롤 정리 (페이지네이션·액션 버튼 상시 노출)

## 2.1 Implementation Plan (TASK-0228 — datasource SSRF 사설망 경계 토글)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Major(보안 수준 저하)** 변경이다. 사용자가 AskUserQuestion 답변(2026-06-11)에서 "구축된 SSRF 방어 구성을 태그로 기억해두고 이후 요청 시 복원, 현재는 경계 의도적 비활성화" 를 명시 승인 → plan 승인으로 간주.

<!-- PLAN-APPROVED by user on 2026-06-11 -->

- **영향 파일·symbol**:
  - `unit/feature-0003-agent-web-ui/src/app.py` — `_ssrf_private_guard_enabled()`(신규), `_ssrf_check_host()`(토글 분기 + IPv4-mapped 메타데이터 + loopback/link-local 상시 차단), `admin_list_datasources`(응답 필드).
  - `static/admin.js`, `static/admin.html` — 안내 문구 분기 + 캐시버스터.
  - `docs/DECISIONS.md`(ADR-0030), `docs/SECURITY.md`(§11), `.env.secret.example` — 정본 + 복원 절차.
  - `tests/test_ssrf_private_guard_toggle.py`(신규).
- **접근**: SSRF 방어 로직을 삭제하지 않고 env 토글(`AGENT_DATASOURCE_SSRF_GUARD_ENABLED`, 기본 활성) 뒤로 분기. 운영 `.env.secret` 에서만 `=0` 으로 비활성화 → 복원 가능. 메타데이터/loopback/link-local/DNS pin 은 토글 무관 유지.
- **완료 판정 기준**: (AC1) host=10.200.50.80 데이터소스 생성 성공(토글 OFF). (AC2) 토글 OFF 여도 메타데이터 IP(IPv4-mapped 포함)·loopback·link-local 차단. (AC3) 토글 ON(기본) 시 기존 동작 보존. (AC4) 신규 테스트 + datasource 회귀 0. (AC5) 복원 절차가 ADR-0030 에 기록.
- **위험도**: Major(§12.3 보안 다운그레이드) — 사용자 명시 승인 + outside-voice 적대적 보안 리뷰(REV-20260611-0228 BLOCK→흡수→PASS)로 잔여 위험을 승인 범위(RFC1918)로 한정.
- **작업 항목**:
  - [x] `_ssrf_private_guard_enabled` + `_ssrf_check_host` 토글 분기 + BLOCK-fix(IPv4-mapped 메타데이터 + loopback/link-local 상시 차단)
  - [x] `GET /api/admin/datasources` 응답 필드 + admin.js/html 안내 분기 + 캐시버스터
  - [x] ADR-0030 + SECURITY §11 + .env.secret.example + 자동 메모리
  - [x] 신규 테스트 31 PASS + datasource 회귀 0 + py_compile + node --check
  - [x] 적대적 security 패널(REV-20260611-0228 BLOCK→흡수→PASS)
  - [ ] 운영 `.env.secret` 토글=0 설정 + verify-completion → 머지 → web 재배포 → PB-0008 시각검증

## 2.1.archived Implementation Plan (TASK-0052)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Critical 등급 (인증/인가 구조 변경) 변경 계획이다. `/plan-eng-review` (Section 1~4) + Codex outside voice (gpt-5.5, reasoning=high) 통합 후 사용자 승인 (2026-05-06) 으로 진행. 4 phase 분할 → **본 turn 은 Phase 1A 만**.

<!-- PLAN-APPROVED by user on 2026-05-06 -->

전체 plan: [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). 본 §2.1 은 그 briefing 의 Phase 1A 슬라이스만 record.

### Phase 1A — RBAC engine catalog 인자화 (본 turn)

**목표**: Codex Claim 1 이 지적한 정적 PERMISSION_CODES 가정 (5 hot path hardwired) 을 catalog 인자 받는 형태로 refactor. **동작 변경 0**, deploy 안전성 극대화.

**영향 파일**:
- [src/app.py](../src/app.py) — `Iterable` import 추가, `_resolve_permission_catalog(conn=None)` 헬퍼 신설, 5 함수 (`_empty_permission_map`, `_apply_permission_overrides`, `_validate_permission_codes`, `_normalize_override_payload`, `_permission_catalog_payload`) 시그니처 확장 (catalog_codes/catalog_map/catalog kwarg 추가, 기본값 None = 정적 PERMISSION_CODES 사용 → 기존 동작 유지). `/api/admin/permissions` 엔드포인트가 plumbing 검증 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)`) 를 거치도록 단일 위치 전환.

**접근 방법**:
1. `_resolve_permission_catalog(conn=None)` 추가 — Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 그대로 반환. Phase 1B 가 conn 으로 WebPermissions union 하도록 body 만 교체.
2. 5 함수의 시그니처에 `*` 강제 keyword + catalog 인자 추가. `None` 이면 기존 정적 사용 (모든 기존 callsite 가 None 인자로 호출되어 회귀 0).
3. `/api/admin/permissions` 1 곳만 새 plumbing 으로 전환 — 정적 결과와 동일함을 HTTP smoke 로 검증.
4. 다른 callsite (account list, role detail 의 `_apply_permission_overrides` 등) 는 Phase 1B 에서 동적 catalog 도입 시 caller-update.

**위험도**: Low — 모든 기본값이 backward-compat. 단일 deploy.

**검증 (완료)**:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과
- (b) `make web` 컨테이너 재배포 성공 (`repo-web-1 Recreated/Started`)
- (c) 컨테이너 in-place 코드 검사: `_resolve_permission_catalog` / `catalog_codes` 키워드 17 hits — 신규 헬퍼 deploy 확인
- (d) bootstrap_admin 로그인 + `/api/admin/permissions` HTTP 200 + 33 codes 정상 (이전 catalog 와 동일)

**Phase 1A 종료 후 후속 phase (별 cycle)**:
- Phase 1B: WebPermissions IsDynamic/ProductId 컬럼 추가 + product 권한 backfill SQL + `_resolve_permission_catalog(conn)` body 를 DB query 로 교체 + 다른 callsite caller-update
- Phase 1C: 8 endpoint guard 도입 (G1-G8 — briefing §3.4)
- Phase 1D: admin UI PERMISSION_GROUP_ORDER 'product' 추가
- Phase 2: 운영 검증

## 2.1.archived Implementation Plan (TASK-0051)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute 프로토콜에 따른 **Major** 등급 변경 계획이다. 사용자가 2026-05-06 직접 진행 지시(§3.1 우선순위 1) + `[A → B → C → D]` 범위 한정으로 인계됐다. C5 (제품 권한 상속/override) 는 분리되어 다음 cycle 의 plan-eng-review 후 진행한다.

<!-- PLAN-APPROVED by user on 2026-05-06 -->

### 영향 파일
- [src/static/admin.js](../src/static/admin.js) — 핵심. 3 개 인라인 save 버튼 제거 + pending 상태 4 종 추가(`productMeta`, `productDatabases`, `systemPrompts`) + `applyAllPending()` 6 단계로 확장 + `pendingChangeCount()` / `refreshPendingUI()` / dashboard pending 카드 갱신. `renderProductDetail()` 의 chip wrap 에 메타데이터 4 종 locked chip 강제 prepend(× 버튼 없음, `is-locked` 클래스). chip 자유 텍스트 입력을 `<select>` picker 로 교체 — `loadAdminData` 에서 `/api/admin/databases/available` 동시 호출, 메타데이터 4 종 / 이미 등록된 chip / 내부 차단 (`agent_memory`) 은 옵션에서 제외. `buildSystemPromptEditor` 의 saveBtn/clearBtn 제거 + textarea 변경 핸들러로 pending 등록 + 안내 메시지 ("변경사항은 하단 '모두 적용' 으로 저장됩니다").
- [src/static/admin.html](../src/static/admin.html) — markup 변경 없음. cache-bust query string `v=20260506-batch-commit` 로 갱신 (admin.js / styles.css 양쪽).
- [src/static/styles.css](../src/static/styles.css) — `.admin-chip.is-locked` (회색 + cursor:not-allowed + opacity 0.55), `.admin-chip-locked-hint` 토큰 사용, `.admin-db-picker-row` (select + 추가 버튼 정렬) 추가. 토큰만 사용하고 hardcoded 색상 금지.
- [src/app.py](../src/app.py) — `GET /api/admin/databases/available` 신규 엔드포인트 추가. `_open_memory_connection(database=None)` 으로 `SHOW DATABASES` 실행, 결과를 `metadata_schemas`(고정 4 종 + 실제 존재 여부 marker) 와 `user_schemas`(메타 4 + `agent_memory` + `MEMORY_DB` 제외) 로 분리. 권한: `console.access`. 검증: schema name regex `^[a-z_][a-z0-9_]{0,63}$` 매칭 만 반환.

### 접근 방법
1. **Backend `/api/admin/databases/available`** 추가 — read-only enumeration. 권한이 약하면 (`console.access` 만) Product 관리자가 아니어도 목록 조회는 가능 (옵션 채우기 용도). 실제 등록은 `product.manage` 권한이 필요한 `PUT /api/admin/products/{id}/databases` 로만.
2. **Frontend pending 흐름 통합**:
   - `adminState.pending` 에 `productMeta: Map<productId, patch>`, `productDatabases: Map<productId, draft[]>`, `systemPrompts: Map<key, {scope, productId, roleId, accountId, content}>` (key = `${scope}:${productId||0}:${roleId||0}:${accountId||0}`) 추가.
   - `setProductMetaPending(id, patch)`, `setProductDatabasesPending(id, draft)`, `setSystemPromptPending(args)` 헬퍼 추가. 모두 immediate API 호출 안 함.
   - `pendingChangeCount()` 에 신규 3 buckets 합산.
   - `applyAllPending()` 에 6 번째~8 번째 단계 추가: 제품 메타 PATCH → 제품 DB PUT → 시스템 프롬프트 PUT (productMeta → productDatabases 순서, 둘 다 같은 product 면 메타 먼저).
   - `cancelAllPending()` 에 신규 buckets clear 추가. `loadAdminData()` 에 stale entry GC 추가 (제품 삭제 시 정리).
   - `refreshPendingUI()` 의 `commitBarDetail` 에 신규 카테고리 항목 추가.
   - Dashboard pending 카드(`renderDashboard` / `dashboardPendingList`) 에도 신규 카테고리 노출.
3. **renderProductDetail (제품 정보 저장 버튼 제거)** — name/desc/active/default/sort 입력 변경 핸들러를 `setProductMetaPending(productId, {field: value})` 로 변경. `saveMetaBtn` 삭제. 입력 disabled 는 `!canManage` 그대로 유지.
4. **renderProductDetail (DB 목록 저장 버튼 제거 + metadata locked chip + picker)**:
   - `redrawChips()` 시작 부분에 메타데이터 4 종을 `<span class="admin-chip is-locked"><span>information_schema</span> <small>항상 접근</small></span>` 형태로 forEach 강제 prepend. × 버튼 없음. `draft` 배열에는 메타 4 종이 들어있더라도 화면 상 user chip 영역에서 제외하여 중복 노출 방지 (단, draft 정합성 유지를 위해 user chip 만 표시).
   - 자유 텍스트 input + 추가 버튼을 `<select>` picker + `+ 추가` 버튼으로 교체. `<select>` 옵션은 `adminState.availableDatabases` (loadAdminData 에서 채움) 에서 메타 4 종 / 이미 draft 에 있는 schema / `agent_memory` / `MEMORY_DB` 제외. 옵션 0개면 "(추가 가능한 DB 없음)" 빈 옵션 표시.
   - `+ 추가` 버튼 클릭 시 draft 에 push + `setProductDatabasesPending(productId, draft)` + `redrawChips()` + picker 옵션 갱신.
   - chip × 버튼 클릭 시도 동일하게 `setProductDatabasesPending` 으로 pending 등록.
   - `saveDbBtn` 삭제. 안내 텍스트(dbHint) 마지막에 "메타데이터 4 종은 정책상 항상 접근 가능하며 변경할 수 없습니다." 한 줄 추가.
5. **buildSystemPromptEditor**:
   - `saveBtn` / `clearBtn` 제거 후, textarea `input` 이벤트로 `setSystemPromptPending({scope, productId: resolveProductId(), roleId, accountId, content: textarea.value})` 호출.
   - 빈 문자열 입력은 그대로 pending 으로 들어가고 apply 시 `PUT /api/admin/system-prompts` body content="" 가 삭제 경로로 처리됨 (기존 backend 동작 활용).
   - textarea 위에 안내 한 줄 ("변경사항은 하단 '모두 적용' 버튼으로 일괄 저장됩니다") 추가.
   - `productSelect` 변경 시 pending 의 key 가 바뀌므로, change 이벤트에서 `refresh()` 만 하고 textarea 값은 비우지 않는다 (사용자 의도 보존). Pending 에 같은 key 가 이미 있으면 textarea 에 그 content 를 채움.
6. **app.py `GET /api/admin/databases/available`** — `_account_has_permission(account, "console.access")` 검사 후 `_open_memory_connection(database=None)` → `SHOW DATABASES` → 결과를 `_METADATA_SCHEMAS = {"information_schema","mysql","sys","performance_schema"}` 와 `_INTERNAL_SCHEMAS = {MEMORY_DB.lower(), "agent_memory"}` 로 분류. user_schemas 에는 메타·내부·정규식 위반 제외 후 정렬해 반환. metadata_schemas 는 항상 고정 4 종 (실제 존재 여부 `present: bool` 표기).
7. **Cache-bust** — admin.html 의 `styles.css?v=…` 와 `admin.js?v=…` 두 줄을 `v=20260506-batch-commit` 으로 갱신.

### 위험도
- **Major** (§12.3) — 다파일 변경(FE 3 + BE 1), 권한 모델 변경 없음, 외부 계약·비용 영향 없음, 기존 정책(REV-20260422-0006 메타 bypass) 의 시각화일 뿐 동작 변경 아님. `agent_memory` 차단 정책 그대로 유지. 회귀 위험 영역: applyAllPending 6 → 8 단계 확장, dashboard pending 카드 새 카테고리.
- **C5 (계정·역할 → 제품 권한 상속/override)** 는 본 cycle 에서 분리. 사유: 신규 테이블(`WebRoleProductAccess`, `WebAccountProductAccessOverrides`) 마이그레이션 + `compose_system_prompt` 의 product 조회 경로 영향 + RBAC override 모델 (TASK-0024) 과의 충돌 검토 필요. 다음 cycle 진입 전 `/plan-eng-review` 권고.

### 검증 계획 (D 단계)
- a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` — syntax
- b) `make web` 재빌드 + `docker logs web` healthy 확인
- c) UX 회귀: `/admin` 진입 → 제품 탭 → 메타 4 chip 회색 표시 / × 없음 확인 / picker 옵션에 메타 4 미포함 확인 / 사용자 schema 추가·제거 시 footer 카운트 증감 / `모두 적용` 클릭 시 PATCH + PUT 순차 호출. 역할 탭 → 권한 grid 변경 + 시스템 프롬프트 textarea 변경 → footer 일괄 적용 동작.
- d) `GET /api/admin/databases/available` 직접 호출로 metadata 4 종 + user_schemas 정렬 + agent_memory 제외 확인.
- e) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS.

### 후속
- C5 분리 권고를 본 plan + `docs/REPORT.md §후속 작업` 에 기록.
- ANCHOR.md §3 의 "Role/Product 권한 부여" 시나리오 묘사가 본 변경으로 시각화되어 강화됨 — §3 본문 보강 여부는 §4 (cycle 종료 시 human 검증) 에서 판단.

## 2.1.archived Implementation Plan (TASK-0048)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute 프로토콜에 따른 Major 등급 변경 계획이다. 사용자가 2026-05-06 직접 진행 지시 (§3.1 우선순위 1) 를 한 상태에서 `<!-- PLAN-APPROVED by user on 2026-05-06 -->` 마커로 인계된다.

### 영향 파일
- [src/app.py](../src/app.py) — `/api/ask` body 에 optional `product_mode` / `product_id` hint 수용. 기존 `request_conversation_id` 이 비어 있어 `_resolve_conversation_for_account(create_if_missing=True)` 로 lazy 생성되는 분기에서, 새 cid 직후 `AgentCoreConversations.product_id/product_mode` 를 hint 값으로 셋업하고 `_save_account_product_pref` 도 호출. `request_conversation_id` 가 명시된 경로(기존 대화에 ask) 에서는 hint 를 무시한다 (대화의 product 변경은 `PATCH /api/conversations/{cid}/product` 가 단독 진실 — TASK-0047 의 race guard 와 충돌 방지).
- [src/static/app.js](../src/static/app.js) — `state.pendingNewConversation: boolean` 도입. `createConversation()` 의 동작은 보존(다른 호출처에서 직접 호출 가능) 하되, `newConversationBtn` 핸들러는 새 함수 `beginPendingConversation()` 으로 교체. `sendPrompt()` 가 pending 상태일 때 `/api/ask` body 에 `product_mode` / `product_id` 를 첨부하고 응답의 `conversation_id` 를 채택. `renderConversationList()` 에 pending placeholder (`is-pending` 클래스, 클릭 비활성, "내 대화" 그룹 상단) 추가. `selectConversation()` 은 pending 모드를 자동 종료. `isCurrentConvBusy()` / progress polling 은 pending 동안 cid sentinel `__pending__` 를 사용해 빈 cid 와 충돌하지 않도록 한다.
- [src/static/index.html](../src/static/index.html) — markup 변경 없음. cache-bust query string `v=20260506-pending-conv` 로 갱신.
- [src/static/styles.css](../src/static/styles.css) — `.conv-item.is-pending` 1 selector 추가 (border-dashed + faded text + cursor:default). 토큰만 사용.

### 접근 방법
1. **Frontend pending state 도입** — `state.pendingNewConversation` 플래그와 sentinel cid `__pending__` 도입. 새 대화 버튼 클릭 시 `beginPendingConversation()` 호출:
   - `state.activeConversationId = ""`, `state.pendingNewConversation = true`, `state.messages = []`
   - `renderConversationList()` (placeholder 표시), `renderConversationHeader()` ("새 대화" 표기), `renderComposer()` (활성), `stopProgressPolling({reset:true})`
   - product chip 은 `state.productMode/pinnedProductId` 를 그대로 유지 (cid 가 없어도 localStorage 미러로 의도 보존, `setActiveProduct` 의 cid-없음 분기 활용)
2. **사이드바 placeholder** — `renderConversationList()` 의 "내 대화" 섹션 렌더 직전에 pending 모드면 가상 항목을 prepend. 클래스: `conv-item is-own is-active is-pending`. 텍스트: "새 대화 (작성 중)" + 부제 "첫 메시지를 입력하세요". 클릭 핸들러 없음.
3. **sendPrompt() 변경** — pending 모드면:
   - body 에 `conversation_id: ""` + `product_mode: state.productMode` + `product_id: state.pinnedProductId || null` 첨부
   - `targetConvId` sentinel 로 `__pending__` 사용하여 `state.busyConversations.add("__pending__")` 처리
   - `progress polling 시작 시 cid 가 비어있으므로 startProgressPolling 호출은 ask 응답으로 cid 를 받은 후로 미룸
   - ask 응답에서 `payload.conversation_id` 받으면 `state.activeConversationId = payload.conversation_id`, `state.pendingNewConversation = false`, busy sentinel 해제, `refreshWorkspace(payload.conversation_id)`
   - ask 가 timeout/네트워크 오류로 실패 — 이 경우 backend 가 이미 cid 를 만들었을 수 있으나 client 가 cid 를 모름 → 사용자에게 "다시 시도하거나 사이드바 새로고침으로 복구" 안내 토스트. attach/resume 다이얼로그는 cid 가 있을 때만 의미가 있어 pending 모드에서는 비활성. 복구 경로: 사용자가 사이드바 새로고침(또는 `loadConversations` 재호출) 으로 새 대화를 보고 그 cid 로 ask 를 다시 보낸다.
4. **Backend `/api/ask` 보강** — `data.get("product_mode")` / `data.get("product_id")` 를 normalize. lazy 생성 분기에서 cid 만든 직후:
   ```python
   if hint_mode in ("auto", "pinned"):
       cur = conn.cursor()
       cur.execute(
           "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
           "WHERE conversation_id = %s",
           (hint_pid, hint_mode, conv_id),
       )
       cur.close()
       _save_account_product_pref(conn, int(account["id"]), mode=hint_mode, pinned_id=hint_pid)
   ```
   기존 대화 경로 (`request_conversation_id` 명시) 는 hint 무시. lazy 분기 이후 line 3886~ 의 `if conv_id:` block 이 새 row 의 `product_mode` 를 다시 읽어 정상 동작한다.

### 위험도 평가 (§12.3)
- **Major** — backend API contract 확장 + frontend state 흐름 변경. 단:
  - Schema/auth/마이그레이션 변경 없음 → Critical 아님
  - 외부 비용 영향 없음
  - 기존 호출자(테스트 러너, 직접 `/api/new_conversation` 사용) 는 backward-compatible 동작 유지
  - 회귀 surface: TASK-0041 attach/resume (cid 가 있을 때만 attach 가능), TASK-0047 product chip race guard (pending 동안 cid 없으니 PATCH 미동작 — `setActiveProduct` 의 cid-없음 분기 활용), 사이드바 그룹 렌더링.

### 사람 승인
<!-- PLAN-APPROVED by user on 2026-05-06 -->

## 3. In Progress
- TASK-0034 복잡 QA 성능 테스트 — 현재 구성된 assistant(agent-core + web UI)의 복잡 질의 대응력을 측정해 이후 개선 포인트를 도출한다. Q1/Q2/Q3 검증 완료, **Q4/Q5 재수행 완료 (2026-04-22: Q4 7 턴 stopped-by-heuristic 1171s / Q5 5 턴 stopped-by-heuristic 251s, 전 턴 HTTP 200)** — TASK-0040/0041 선행 완료 후 블로커 해제. 현재 남은 일은 turn-by-turn 실제 답변과 truth query 대조 검증 + `TASK-0034-REPORT.md` / LEARNINGS 추가 정리.

## 3.1 Recently Done
- TASK-0228 (2026-06-11 마감, REQ-20260611-0228, **Major §12.3** — 보안 다운그레이드, 사용자 명시 승인): datasource SSRF 사설망 경계 env 토글 + 의도적 비활성화. 사용자 보고(`관리 콘솔 > 데이터소스` 에서 host=`10.200.50.80` 생성 시 "호스트 차단(SSRF): 사설/링크로컬 IP 차단" 에러)의 근본 원인 = `_ssrf_check_host` 의 RFC1918 차단(설계 의도, TASK-0205/0214). 사용자 결정 = SSRF 방어 구성을 복원 가능한 형태로 보존(태그)하고 현재는 사설 경계 비활성화(사내 사설망 전면 운영). **산출**: ① `_ssrf_private_guard_enabled()` 신규(env `AGENT_DATASOURCE_SSRF_GUARD_ENABLED`, 기본 `1`=활성 secure-by-default). ② `_ssrf_check_host()` 토글 분기 — `private_guard` 비활성 시 RFC1918(`is_private`)만 완화. ③ `GET /api/admin/datasources` 에 `ssrf_private_guard_enabled` + admin.js 안내 분기. ④ ADR-0030 + SECURITY §11 + .env.secret.example(복원 절차/태그). ⑤ 신규 테스트 31 PASS. **outside-voice 적대적 보안 리뷰 BLOCK→흡수→PASS**(REV-20260611-0228): (A/B) 토글 OFF 시 IPv4-mapped IPv6 메타데이터 IP(`::ffff:169.254.169.254`)가 `str(ip).endswith` 정규화 빗나감으로 통과 → `ip.ipv4_mapped` 언래핑 비교로 수정. (C) 토글이 loopback/link-local 까지 개방 → `is_private` 에만 적용하고 loopback/link-local/reserved/multicast 상시 차단으로 수정. **불변식(토글 무관)**: 메타데이터 IP(IPv4-mapped 포함)·loopback/link-local·DNS rebinding pin·fail-closed 에러 경로. 검증: py_compile + node --check PASS, 신규 31 + datasource 회귀 0. 운영 `.env.secret` 토글=0 설정 + web 재배포는 배포 단계. worktree `ai/claude/ssrf-host-guard-toggle`(base e93b181).

- TASK-0061 (2026-05-15 마감, REQ-20260515-0003~0010, **Major** §12.3 — Phase 6 Critical 분면 포함, 사용자 일괄 승인): GOAL.md 8 항목 합본 cycle. (Phase 1+2) 답변 버블 내부 실시간 step 진행 + 신규 대화 첫 요청 즉시 polling 연결 — `state.pendingBubble` + `renderPendingAssistantBubble` + elapsed timer + `applyProgressPayload` 동기화 + `sendPrompt` lazy-create 분기에서 cid 발급 즉시 `startProgressPolling`. (Phase 3) `_compute_display_status` + `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` + 일관 stale 반영 (/api/progress, ask_status, ask_result, list_conversations) + frontend `.conv-dot.is-stale-error` + toast. (Phase 4) `#messagePointRail` + scroll observer + click jump. (Phase 5) `/api/history_dates` AgentMemoryMessages 정본 + 캘린더 popover. (Phase 6 Critical) `WebAccounts.MustChangePassword` ALTER + `POST /api/admin/accounts/{id}/password-reset` (self-reset 거부) + 임시 비번 1회 표시 + 세션 revoke + 강제 변경 modal. (Phase 7) `currentPageAccounts()` helper 로 select-all 현재 페이지만 토글. (Phase 8) Ctrl/Shift 다중 선택 + `_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` partial success + ≥10 typed-confirm. 변경 파일: `app.py`, `app.js`, `admin.js`, `index.html`, `admin.html`, `styles.css`, `.env.example`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`. cache-bust `v=20260515-task-0061`. 검증: python compile / node --check / make web / browser smoke (DOM 5 신규 element + login + bulk bar + 캘린더 popover + display_status + history_dates + delete_conversations + pending bubble + admin currentPageAccounts/select-all + reset btn) 모두 통과.

- TASK-0050 (2026-05-06 마감): `make web` 이 docker compose v5.1.1 + buildx v0.31.1 의 provenance metadata file race 로 EXIT=1 종료되던 문제 우회. 환경 진단으로 `#15 exporting to image` 까지 정상 빌드 후 `#16 resolving provenance for metadata file` 직후 `open /tmp/.tmp-compose-build-metadataFile-<UUID>.json<NNNN>: no such file or directory` 메시지로 종료되는 패턴을 확인 (random suffix mismatch — compose 본체 회귀). `--provenance=false`, `BUILDX_NO_DEFAULT_ATTESTATIONS=1`, `COMPOSE_BAKE=true/false` 모두 효과 없음. Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃을 추가하고 `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리. 가드는 build 명령 로그를 임시파일에 캡처해 EXIT≠0 + 로그에 `compose-build-metadataFile` 문자열 포함 시에만 EXIT=0 으로 정규화 (다른 빌드 오류는 그대로 전파). 향후 compose 또는 buildx 가 fix 되면 가드는 자연스럽게 일반 build 경로로 흐름. 검증: `make web` EXIT=0, `[make] note: ...provenance metadata file race 우회...` 로그, `Container repo-web-1 Recreate/Recreated/Started`, `docker exec repo-web-1 grep -n PENDING_CONV_SENTINEL /app/web/static/app.js` 으로 새 코드 반영 확인. 학습 기록: `docs/LEARNINGS.md` LRN-20260506-0001 quirk.

- TASK-0049 (2026-05-06 마감, REQ-20260506-0002): TASK-0048 lazy 화 이전에 누적된 빈 대화 row 들을 일회성으로 정리. `bin/cleanup-empty-conversations.sh` 추가 — dry-run 기본 + `--execute` 명시 시에만 DELETE, `AgentMemoryKv.last_status='processing'` 인 대화 보호 (실행 중 ask race), `c.created_at < NOW() - INTERVAL <keep-recent-min> MINUTE` (default 5분) 으로 방금 만들어진 placeholder 폴백/in-flight 보호, `--owner-account-id <N>` 으로 계정 한정 가능. SQL 주입 방지를 위해 owner_id/keep_recent_min 모두 정수 정규식 검증 후 인터폴레이션, AgentCoreConversations 와 AgentMemoryMessages 의 collation 차이를 `COLLATE utf8mb4_unicode_ci` 명시 변환으로 해결. 운영 데이터에 적용: 88 conversations / 42 empty / 46 non-empty → 46 conversations / 0 empty / 46 non-empty (5분 보호로 방금 만든 backward-compat 검증 row 1개 포함 정리). 정리된 빈 대화 42개의 owner 분포는 admin (id=1) 다수, 그 외 일부 사용자. 본 TASK 는 destructive 변경(§12.1) 이지만 사용자 2026-05-06 명시 진행 지시에 따라 §3.1 우선순위 1 적용. 추후 정리는 동일 스크립트 재실행으로 idempotent 하게 가능.

- TASK-0048 (2026-05-06 마감, REQ-20260506-0001): "새 대화" 버튼이 즉시 `POST /api/new_conversation` 을 호출하지 않도록 client-side pending state 로 전환했다. 사이드바 "내 대화" 그룹 상단에 `conv-item is-own is-active is-pending` placeholder ("새 대화 (작성 중)" / 부제 "첫 메시지를 입력하세요") 가 표시되고 헤더 + composer 가 활성화. 첫 메시지 전송 시 `sendPrompt()` 가 `/api/ask` body 에 `conversation_id: ""` + `product_mode` + `product_id` (사용자 직전 의도) 를 첨부해 호출하면 backend `/api/ask` 의 `_resolve_conversation_for_account(create_if_missing=True)` 직후 hint 를 `AgentCoreConversations.product_id/product_mode` 에 셋업 + `_save_account_product_pref` 호출로 `WebAccounts.ProductPref*` 미러까지 갱신한다. 응답의 `conversation_id` 를 client 가 채택하고 placeholder 가 사라진다. 빈 대화 누적이 신규 row 측에서 차단된다. PATCH race 가드(TASK-0047 AC-0013) 와 attach/resume(TASK-0041 AC-0018) 는 cid 가 있을 때만 의미가 있어 lazy 분기에서 의도적으로 비활성화 — pending 단계 ask 실패는 "다시 시도하거나 사이드바 새로고침" 안내 토스트로 fallback. 변경 파일: `src/app.py` (lazy 분기에 hint 적용 + `_save_account_product_pref`), `src/static/app.js` (`state.pendingNewConversation`, `PENDING_CONV_SENTINEL`, `beginPendingConversation`, `renderConversationList` placeholder + `prependFn`, `renderConversationHeader` pending 표시, `selectConversation` 자동 종료, `sendPrompt` lazy create 분기, `handleLogout` cleanup, 새 대화 버튼 핸들러 교체), `src/static/index.html` (cache-bust `v=20260506-pending-conv`), `src/static/styles.css` (`.conv-item.is-pending` 1 selector 그룹). 검증: `python3 -m py_compile`, `node --check` 모두 통과, `make web` 으로 컨테이너 재기동 후 새 코드 반영 확인 (`docker exec` grep), `/api/new_conversation` backward-compat 정상 (delta=1 정상 row), `/api/ask` invalid (no API key) 시 lazy create 발생 0건 (input validation 후 lazy create 가 일어나므로 안전). 학습 기록: `docs/LEARNINGS.md` LRN-20260506-0014 pattern.

- TASK-0047 (2026-04-29 마감, agent team 4 합의 + Codex CLI 교차검증 — 사람 검토 없이 진행됨):
  사용자가 진입(로그인 직후) 또는 진행 중 대화에서 대상 **제품(Product)** 을 명시 선택할 수 있도록
  사이드바 헤더에 제품 칩(`#productChip` + `<select id="productSelect">`) 을 도입했다. 칩에는
  caption "이 대화의 제품" 을 함께 두어 대화 단위 상태(전역 계정 설정이 아님) 임을 명시한다 (Codex
  R-06 가드). `auto` 옵션은 일반 대화 모드로, 본 MVP 에서는 LLM resolver 가 들어가기 전이므로
  `[AUTO MODE]` 한 줄을 시스템 프롬프트에 inject 하고 product 한정 PRODUCT/role/account prompt 와
  `allowed_schemas` 를 모두 끈다(빈 리스트로 메타 4 스키마만 허용). 데이터 모델은 새 컬럼 2 개로
  분리: `AgentCoreConversations.product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'` + `WebAccounts.ProductPrefMode`/`WebAccounts.ProductPrefPinnedId`. NULL=auto 의미 변경을
  피하기 위해 명시 컬럼을 신설했다 (Backend Engineer 합의). 신규 API
  `PATCH /api/conversations/{cid}/product { mode, product_id }` 는 (1) 권한
  (`conversation.ask` + 소유자), (2) 진행 중 ask race 가드(`AgentMemoryKv.last_status='processing'`
  이면 409), (3) pinned 모드는 활성 product 검증 후 `WebAccounts` 의 직전 선호도 동시 갱신.
  `/api/session` 응답에 `product_pref` (mode, pinned_id, fallback_reason) +
  `conversation_product` (product_id, product_mode, product_key, product_name) 추가. Frontend 는
  `state.productMode` / `state.pinnedProductId` / `state.activeProductId` 3-필드 분리(의도/핀/서버 결과)
  로 race 회피, optimistic update + PATCH + localStorage 미러 (`mad.productPref.v1`), 진행 중 ask
  동안 `<select>` disabled + tooltip. 코드 중복 방지를 위해 `renderProductOptions(selectEl, {includeAuto, selected})`
  factory 를 추출해 drawer 의 `promptProductSelect` 도 같은 옵션 모델을 공유하게 했다 (FE
  Architect 합의). pinned product 가 비활성/제거된 경우 `_load_account_product_pref` 가 자동으로
  auto 로 강등하고 `pref.fallback_reason='pinned_inactive'` 를 클라이언트에 알려 토스트로 안내한다
  (Codex R-04 가드). 사용자 가시 한글 라벨 "상품" → "제품" 일괄 치환 (`app.py`, `index.html`, `app.js`,
  `admin.html`, `admin.js`); 코드 식별자 `Product`/`product_id`/`WebProducts`/`ProductKey` 는 그대로.
  검증: (1) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과,
  (2) `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py` 통과,
  (3) `node --check src/static/app.js` 통과, (4) in-process `compose_system_prompt(None,...)` /
  fake-conn `compose_system_prompt(...,product_mode='auto')` 검증 — auto 분기는 `[AUTO MODE]` 라인을
  포함하고 pinned 분기는 포함하지 않음. 후속 검증 항목(LLM resolver, PATCH race 강화, Playwright 4 specs,
  BroadcastChannel, mobile bottomsheet, 다국어, 운영 모니터링)은 별도 브리핑 [`docs/BRIEFING-product-selector-v1.md`](./BRIEFING-product-selector-v1.md)
  에 16 개 위험 항목(R-01..R-16) + 5 개 사람 확인 결정 사항(D-01..D-05) 으로 정리. **본 turn 은
  사용자 검토 없이 agent team(UX/FE Architect/BE Engineer/QA-Flow Validator) 4 인 합의 + Codex CLI
  교차검증으로 진행됐다 — 운영 반영 전 D-01..D-05 사람 결정과 R-01..R-16 검증이 필요하다.**

- TASK-0044 (2026-04-23 마감): Approach A wedge (office-hours 2026-04-23 세션에서 승인 — 사업팀 통계/단순 데이터 자가서비스) pilot 인프라 추가. (1) `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 를 추가해 부트스트랩 시 자동 생성되고, 권한은 대화 생성/질의/조회/파일조회/이름변경/취소/즉시답변(own 범위) 9 개로 operator 에서 `conversation.delete.own` 을 제거한 subset — 사업팀 pilot 은 자기 대화 흐름은 조작할 수 있지만 과거 요청 기록의 삭제는 불가. (2) 신규 `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 부트스트랩 단계를 추가해 sales role 에 역할 범위(`WebSystemPrompts.Scope='role', RoleKey=sales, ProductId=NULL`) system prompt 를 1 회 upsert 한다 — 관리 콘솔에서 덮어쓴 값은 존중(존재 시 skip). prompt 본문은 "단순 조회 → 문장 / 집계 → 결과셋 표 / ad-hoc 분석 → DBA 팀 이관 안내 후 대화 종료 / DB 쓰기 쿼리는 항상 거부" 4 지침. `compose_system_prompt` (agent_core) 가 기존 로직대로 `## ROLE GUIDANCE (sales)` 블록으로 주입한다. (3) `modules/config.py` 에 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` / `REPLICA_DB_ENABLED` env 5 개 추가 + `modules/db.py::connect()` 에 라우팅 — `REPLICA_DB_HOST` 가 세팅되어 있고 요청된 `database` 가 `MEMORY_DB`(=agent_memory) 가 아니면 복제 인스턴스로 접속, 아니면 기존 primary. memory DB 연결은 항상 primary 로 남아 대화/세션/권한 정본이 보존된다. `.env.example` 에 4 개 placeholder 추가, 실제 값은 `.env` 또는 docker-compose secret 으로만 주입한다(commit 금지). (4) Product 단위 접근 DB 화이트리스트 조정은 **런타임 체크가 아닌 관리 콘솔 runbook** 으로 정리 — 사업팀 pilot 에게 서빙할 Product 는 KR 의 기본값(`dbgame`/`dblog`/`dbauth`) 을 admin 이 관리 콘솔 `상품 (Products)` 탭에서 `dbauth` 를 제거하거나, 별도 Product(예: `KR-Sales`={dbgame,dblog}) 를 신규 생성해 사업팀 대화를 routing 하는 방식 중 조직 정책에 맞게 선택한다. 현재 seed 는 호환성을 위해 변경하지 않음(기존 KR 을 그대로 쓰는 DBA 워크플로우 영향 없음). (5) 사업팀 pilot 계정 자체는 코드가 자동 생성하지 않고 admin 이 관리 콘솔에서 수동 발급 — `.env.example` 에 `WEB_PILOT_SALES_USERNAMES=` placeholder 주석으로 치환 예시(`sales_lee,sales_kim,sales_park`) 기록. 검증: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/db.py` 통과, (b) `docker compose up -d --build web` 후 `/api/session` HTTP 200 OK, (c) `/api/admin/roles` 응답에 `{"role_key":"sales","name":"사업팀", permissions:[9 codes] }` 포함, (d) `WebSystemPrompts.Scope='role' AND RoleId=<sales_role_id> AND ProductId IS NULL` 1 row 존재하고 content 가 4 지침 문자열로 저장됨. 범위: 애플리케이션 코드 3 파일 약 70 줄, `.env.example` 6 줄, 문서 4 파일. `agent_core` 경로 재빌드(`depends_on` 체인) 는 모두 `modules/db.py` 변경 때문에 필요하다.
- TASK-0041 (2026-04-22 마감): 클라이언트 타임아웃 시 대화 지속(Attach/Resume) 경로를 구축. 에이전트 작업자 스레드는 `asyncio.to_thread` 로 HTTP 연결과 독립 실행되므로 클라이언트(httpx/브라우저/프록시) 가 ReadTimeout 으로 끊겨도 서버는 완료까지 계속 진행한다. 이 결과를 회수할 read-only 경로가 없어 결과가 유실되던 문제를 해결. 서버에는 `_ASK_TERMINAL_STATUSES={done,error,canceled}` 상수와 `_load_run_meta_kv` + `_build_ask_status_snapshot` 헬퍼, 그리고 `GET /api/ask_status` (1-shot 스냅샷, `conversation.read.own/any` gated) 와 `GET /api/ask_result?wait<=60` (long-poll, `deadline/0.5s` interval, terminal 시 assistant 전문 반환) 2 엔드포인트를 추가. 브라우저에는 `ASK_ATTACH_POLL_WAIT_SEC=45`/`ASK_ATTACH_MAX_TOTAL_SEC=1800` 상수와 `fetchAskStatus` / `showTimeoutRecoveryDialog`(3 버튼 모달 + Escape dismiss, 인라인 스타일) / `attachAndWaitForResult` long-poll 루프를 추가하고, `sendPrompt()` 의 `/api/ask` 호출 실패 시 is_processing=true 이면 다이얼로그 → 선택에 따라 `/api/cancel`·`/api/finalize` + attach, `initializeWorkspace()` 말미에는 페이지 로드 시 auto-attach. 테스트 러너에는 `ATTACH_TIMEOUT_SEC=960.0`/`ATTACH_POLL_WAIT_SEC=45` 상수와 `_attach_run(client,cid,message,t0)` 함수를 추가해 기존 `httpx.ReadTimeout` 분기를 `{"error":"client-read-timeout"}` 반환 대신 ask_status → ask_result long-poll 로 정상 복구하고 turn dict 에 `attached_after_timeout=True` + `attach_verdict` 기록. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새 실행을 시작시키지 않는 안전 속성을 보장한다. 검증: py_compile 3 파일 + `node --check app.js` 통과, `make web` 재빌드 후 새 이미지 반영, 엔드포인트 401 라우팅 확인, terminal 상태 스냅샷 38ms, Q4 7 턴 + Q5 5 턴 전부 HTTP 200 으로 완료 (단일 턴이 960s 를 넘지 않아 attach 는 실제 발동되지 않았지만 safety net 인프라는 검증됨).
- TASK-0040 (2026-04-22 마감): SQL schema whitelist 정규식을 context-aware 2 단계 스캐너로 재작성해 `alias.column` 오탐 회귀를 제거했다. 기존 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 는 SQL 문맥 구분 없이 전체에서 `x.y` 를 찾았고, SELECT/WHERE/ON 절의 alias.column 토큰이 schema 후보로 수집되어 Q4 재수행이 모든 턴 `BLOCKED_SCHEMAS=bb,be` 로 실패했다. `_TABLE_LIST_RE` (FROM/JOIN 뒤 다음 절 키워드 직전까지의 테이블 리스트 구간을 slice, IGNORECASE|DOTALL) + `_INNER_REF_RE` (그 slice 내부에서만 `schema.table` 추출) 2 단계로 재작성. SELECT 절의 alias.column 은 FROM/JOIN slice 바깥이라 더 이상 매칭되지 않는다. 검증: in-process 15 테스트 케이스(단일 FROM / FROM+WHERE alias.col / FROM+JOIN+alias.col ON / 혼합 / 백틱 / subquery / 비허용 schema 차단 / SELECT alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / dedup) 전부 expected 일치, Q4-like SQL 이 `{dblog}` 만 추출되고 `_whitelist_violation` 이 `{dbauth,dbgame,dblog}` whitelist 에서 None 반환, 비허용 `dbstat.foo` 는 계속 차단. 후속 TASK-0034 Q4/Q5 재수행이 전 턴 HTTP 200 으로 완료됨.
- TASK-0039 (2026-04-22 마감): Product 단위 DB whitelist 를 적용하면서 **메타데이터 4 스키마**(`information_schema`, `sys`, `mysql`, `performance_schema`) 만은 Product 접근 DB 목록에 등록 여부와 무관하게 agent tools 가 **항상 조회 가능** 하도록 정책을 재정의했다. 사용자 지시 2026-04-22: "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지". 이는 TASK-0036 의 REV-20260421-0005 결정(메타데이터도 기본 차단) 을 일부 완화하는 방향이며, **`agent_memory` 는 여전히 whitelist 로 차단 유지**(에이전트 자신의 메모리/세션/계정 데이터 노출 방지). 변경: [tools.py:24-28](../../feature-0002-agent-core/src/modules/tools.py#L24-L28) 의 `_SYSTEM_SCHEMAS` frozenset 을 `_METADATA_SCHEMAS`(4 종) 와 `_INTERNAL_SCHEMAS`(1 종, `agent_memory`) 두 frozenset 으로 분리하고 `_SYSTEM_SCHEMAS` 는 union 으로 유지(기존 `_is_user_schema`/`search_tables` 의 UX-레벨 필터 동작 보존). [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94) 의 `_whitelist_violation` 은 기존 `{information_schema}` bypass 대신 `_METADATA_SCHEMAS` 전체(4 종) 를 bypass 하고, `agent_memory` 는 여전히 `blocked` 로 떨어지도록 했다. 에러 메시지에 "메타데이터 스키마는 항상 접근 가능" 안내 한 줄을 추가해 agent 가 잘못된 참조를 메타데이터로 리디렉션하지 않도록 유도. 검증: (a) `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` 통과, (b) 컨테이너 재빌드 후 `docker compose exec web python -c "..."` in-process 호출로 `set_active_schema_allowlist(['dbgame'])` 설정 상태에서 `_whitelist_violation({'mysql'})` / `{'sys'}` / `{'performance_schema'}` / `{'information_schema'}` 가 모두 `None` 반환, `{'agent_memory'}` 는 `오류:` 문자열 반환, `{'dbstat'}` (임의의 비허용 user schema) 은 차단. (c) 실사용 스모크: Product=KR 로그인 + 새 대화 + `/api/ask` 로 "dbgame 스키마에 있는 테이블 수를 information_schema 로 세어봐" → whitelist bypass 로 information_schema 접근 허용, tool step 정상 완료. 범위: 본 TASK 는 whitelist 정책 bypass 목록 조정에 국한. `list_schemas` 결과에 메타데이터 스키마를 노출할지는 UX 결정이라 현 상태(숨김) 유지.

- TASK-0038 (2026-04-22 마감): TASK-0034 Q4/Q5 실패 원인 분석([TASK-0038 상세 설계](#task-0038-상세-설계-2026-04-22) 참조)에서 확인된 근본 원인 1(agent_core 의 `OpenAI(**client_kwargs)` 가 `timeout`/`max_retries` 파라미터 없이 초기화돼 LLM 호출이 무한 대기할 수 있음) 과 근본 원인 2(러너 `ASK_TIMEOUT_SEC=600s` < 서버 `run_timeout_sec=900s` 로 클라이언트가 서버보다 먼저 포기해 좀비 에이전트 스레드가 발생) 를 대응했다. (1) [agent_core.py:1134](../../feature-0002-agent-core/src/agent_core.py#L1134) 의 `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장하고 import 에 `AGENT_OPENAI_MAX_RETRIES` 를 추가. OpenAI Python SDK v1.x 의 client-level `timeout` 은 내부 httpx 에 그대로 적용되므로 `chat.completions.create` 개별 호출마다 wall-clock 상한이 보장된다. `max_retries` 는 이미 `AGENT_OPENAI_MAX_RETRIES=0` (config 기본값) 이므로 SDK 내부 재시도로 budget 이 배수로 늘어나지 않는다. (2) `task0034_runner.py:52` `ASK_TIMEOUT_SEC=600.0` 을 `960.0` 으로 인상(서버 `run_timeout_sec=max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=max(900,180)=900` 보다 60s 여유). 이제 서버가 먼저 자기-타임아웃으로 실패 응답을 돌려주고, 클라이언트는 그 응답을 받은 뒤 다음 턴으로 넘어간다 — 좀비 스레드 창이 사라진다. 검증: (a) `python3 -m py_compile src/agent_core.py tests/task0034_runner.py` 통과, (b) `docker compose up -d --build web` 후 bootstrap_admin 로그인 + `/api/session` 200 OK + `/api/new_conversation` 후 간단 질의가 정상 응답, (c) agent_core 내부 LLM 호출이 AGENT_TIMEOUT_SEC(=.env 값 300s) 초과 시 `openai.APITimeoutError` 를 던지고 `_call_llm` caller 에서 step error 로 흡수되는 경로를 `grep` 으로 재확인. 범위: 본 TASK 는 근본 원인 1+2 만 다루고, 3(질문 follow_up 강화) 과 4(러너 격리/쿨다운) 는 TASK-0034 재실행 단계에서 별도 처리한다.
- TASK-0037 (2026-04-22 마감): `/api/progress` 폴링 루프를 `setInterval` 고정 주기에서 **순번(progressPollSeq) 기반 `setTimeout` 체인 + AbortController + 적응형 주기** 로 전환한 TASK-0036 부수 변경을 사후 리뷰/검증/문서화한다. 문제: `/api/ask` 한 턴이 수분까지 걸리는 실사용 워크로드(TASK-0034 에서 평균 ~3분/턴 관측) 에서 1500ms 고정 `setInterval` 폴링은 (1) 이전 요청이 끝나기 전에 다음 요청이 발행돼 **in-flight 요청 쌓임**, (2) 탭 전환/대화 변경/로그아웃 시 발행된 요청을 취소할 경로가 없어 서버에 **스텁 요청이 계속 도착**, (3) 서버는 `_load_steps_for_run` 이 전체 step 을 파이썬으로 로드해 `after_step` 필터를 코드로 걸던 경로였고, (4) 탭이 배경화되어도 그대로 1500ms 주기로 폴링을 지속해 배터리/네트워크를 불필요하게 소모했다. 조치 (이미 27127b9 커밋에 반영됨): 서버는 `_load_progress_status(conn, cid)` 단일 커서로 `(status, status_at, run_id)` 를 반환하도록 분리하고, `_load_steps_for_run(after_step=0)` 으로 SQL 레이어 필터를 밀어넣었으며, `/api/progress` 에 `client_run_id` 쿼리 파라미터를 추가해 클라이언트가 들고 있는 run_id 가 서버 최신 run_id 와 불일치하면 `after_step` 을 0 으로 리셋해 새 run 전체를 다시 흘려보내도록 했다. 클라이언트는 상수 `PROGRESS_FETCH_TIMEOUT_MS=4000`, `PROGRESS_POLL_ACTIVE_MS=1200`, `PROGRESS_POLL_IDLE_MS=3000`, `PROGRESS_POLL_HIDDEN_MS=10000`, `PROGRESS_POLL_ERROR_MS=8000` 5개를 도입하고, state 에 `progressPollInFlight`/`progressPollSeq`/`progressAbortController`/`progressErrorCount` 을 추가했다. `setInterval` → `setTimeout` 단일 체인(`scheduleProgressPolling(delayMs, seq)`) 으로 전환해 각 poll 이 응답하고 나서 다음 poll 을 예약하는 구조가 되었고, `pollProgress(seq)` 은 `seq !== state.progressPollSeq || progressPollInFlight` 이면 즉시 return 해 중복 실행을 차단한다. 매 요청마다 `AbortController` 를 생성해 `state.progressAbortController` 에 보관하고 `stopProgressPolling({abort:true})` 이나 `controller.abort()` 타임아웃(4초) 에서 in-flight 요청을 즉시 취소한다. 적응형 주기: 응답에 step 이 있으면 1.2s(ACTIVE), 없으면 3s(IDLE), `document.hidden` 이면 최소 10s(HIDDEN), 연속 오류 3회 미만까지는 8s(ERROR) 간격으로 재시도하되 3회 이상은 아예 재스케줄링하지 않는다. 검증: (1) `grep -c "setInterval" src/static/app.js` = 0 으로 기존 폴링 루프가 모두 제거됨, (2) 적응형 상수 5개 모두 `scheduleProgressPolling`/`pollProgress` 에서 실제 참조됨, (3) 서버 `/api/progress` 는 `client_run_id` 가 없거나 불일치 시 `after_step` 을 0 으로 리셋하는 조건을 실제로 가진다(`app.py:4405`), (4) 브라우저에서 `/api/progress` 응답 status 가 `processing` 이외 값이 되면 `stopProgressPolling({abort:false})` + `refreshWorkspace(cid)` 호출로 폴링이 즉시 멈추고 최종 workspace 가 재로드된다. 영향: TASK-0034 복잡 QA 테스트 중 상용 API 응답이 5분 이상 걸리는 상황에서도 브라우저 열린 탭에서 요청이 쌓이지 않고, 탭 전환 시 자동으로 저속 모드로 내려간다.
- TASK-0036 (2026-04-21 마감): System Prompt Depth 가 Product → Role → Account 3 계층 체인으로 동작하고, Product 단위 접근 DB 화이트리스트가 agent tools 레벨에서 강제된다. `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 3 신규 테이블 + `AgentCoreConversations.product_id` 컬럼을 추가했고, `product.manage` / `system_prompt.manage.role.any` 2 개 permission 을 `admin` 역할에 기본 부여했다. seed 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) 가 자동 생성된다. `agent_core.compose_system_prompt(mem_conn, product_id, role_id, account_id)` 가 base prompt 뒤로 `## PRODUCT CONTEXT` / `## ROLE GUIDANCE` / `## ACCOUNT PREFERENCES` 블록을 순차 append 하고, `tools.set_active_schema_allowlist()` 가 execute_sql/describe_schema 등 모든 도구의 스키마 참조를 검사한다. 관리 콘솔은 `상품 카테고리` 구분 그룹 아래 `상품 (Products)` 탭이 추가되어 Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집을, Roles detail 은 Role scope prompt 편집기(Product 드롭다운 포함) 를, 프로필 드로우의 새 `프롬프트` 탭은 Account scope prompt 편집기를 각각 제공한다. 검증: (1) `docker compose up -d --build web` → bootstrap_admin 로그인 → `/api/admin/products` → KR seed 확인, (2) `PUT /api/admin/products/1/databases` 로 dblog 제거/복원 왕복 OK, (3) `PUT /api/admin/system-prompts` (product scope) → `compose_system_prompt(conn, product_id=1, role_id=3, account_id=1)` 출력에 `## PRODUCT CONTEXT (KR)` 블록이 추가됨을 in-container 직접 확인, (4) whitelist=`{dbgame,dblog,dbauth}` 설정 후 `execute_sql("SELECT 1 FROM mysql.user")` 및 `describe_schema("mysql")` 이 `오류: 접근이 허용되지 않은 스키마 참조: mysql` 반환, `describe_schema("dbgame")` 은 정상 동작. 부수 수정: `_runtime_tables_available` 의 probe list 에 신규 3 테이블을 포함해 기존 배포에서 schema 마이그레이션이 자동 트리거되게 했고, `_whitelist_violation` 이 `_SYSTEM_SCHEMAS` 를 예외 처리하던 우회 경로를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 가 더 이상 whitelist 를 건너뛰지 않게 했다 (security hardening).

### TASK-0040 상세 설계 (2026-04-22)
- 문제/목적 (TASK-0034 Q4 재수행 중 2026-04-22 관찰): Q4 재수행 3 턴이 모두 `오류: 접근이 허용되지 않은 스키마 참조: bb, be. 현재 Product 에 허용된 스키마: dbauth, dbgame, dblog` 에러로 종료됐다. 실제 SQL 은 `SELECT ... FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo ... WHERE bb.BattleType = 'CROSSROUTE' AND be.Star >= 3 ...` 형태로 `dblog` 만 참조하고 `bb`/`be` 는 테이블 별칭(alias) 이었다. 원인은 TASK-0036 에서 도입한 [tools.py:65-80](../../feature-0002-agent-core/src/modules/tools.py#L65-L80) 의 `_extract_sql_schema_refs` 정규식 `r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?"` 이 WHERE/SELECT 절의 `alias.column` 토큰까지 `schema.table` 로 수집한 뒤 [tools.py:83-105](../../feature-0002-agent-core/src/modules/tools.py#L83-L105) `_whitelist_violation` 이 allowlist(`{dbauth,dbgame,dblog}` + 메타데이터 4 종) 에 없다는 이유로 `bb`/`be` 를 차단하는 회귀다.
- 현황/환경 분석 (코드 기준):
  1. [tools.py:65-80](../../feature-0002-agent-core/src/modules/tools.py#L65-L80) `_extract_sql_schema_refs` — module-level lazy compile, finditer 로 전체 SQL 을 훑는다. 컨텍스트 구분이 없어 `WHERE bb.BattleType = 'X'` / `SELECT be.Star, be.Time` / `ORDER BY bb.StartTime` 등 alias.column 이 모두 매칭된다.
  2. 이 함수의 소비자는 [tools.py `_tool_execute_sql` / `_tool_explain_query`](../../feature-0002-agent-core/src/modules/tools.py#L83-L105) 의 `_whitelist_violation(refs)` 단일 경로. `describe_schema` / `describe_table` / `search_tables` / `get_sample_rows` / `get_table_indexes` / `get_foreign_keys` / `list_schemas` 는 이미 `{ schema_arg }` 1 건만 전달하므로 영향이 없다.
  3. MySQL 문법상 `schema.table` 을 쓸 수 있는 위치는 **FROM 절 / JOIN 절 / DELETE FROM / INSERT INTO / UPDATE / CREATE TABLE `s`.`t` / ALTER TABLE / TRUNCATE / INDEX reference** 등 DDL/DML 대상 지정 구간이다. agent 는 `execute_sql` 이 read-only SELECT 전용이므로 실사용 범위는 **FROM {schema}.{table} [alias]**, **JOIN {schema}.{table} [alias]**, **FROM/JOIN 연속 comma list `{s1}.{t1}, {s2}.{t2}`** 3 가지로 좁혀진다.
  4. WHERE/SELECT/GROUP BY/ORDER BY/ON 조건에 나오는 `x.y` 는 반드시 alias 또는 unqualified table → column 참조로, schema 의미가 없다. 따라서 "`FROM`/`JOIN`/`,` 직후에 위치한 `x.y`" 만 `schema.table` 로 간주하면 오탐이 제거된다.
  5. Edge case:
     - 중첩 서브쿼리 `FROM (SELECT ... ) t1 JOIN dblog.battlebegin bb ...` — `JOIN dblog.battlebegin` 은 여전히 매칭. 서브쿼리 내부의 `FROM dbgame.items` 도 독립적으로 매칭. 이상 없음.
     - `INSERT INTO` / `UPDATE` / `DELETE FROM` — read-only 전제라 발생하지 않지만, 보수적으로 `FROM|JOIN|,` 만 보되 향후 필요 시 확장 가능하게 둔다.
     - 백틱 `` FROM `dblog`.`battlebegin` `` — 공백/백틱 허용.
     - 대소문자 `from`/`From`/`FROM` — `IGNORECASE` 필요.
     - 주석 `/* ... */`, 문자열 리터럴 `'dblog.table'` 내부 — 현재 구현도 별도 처리 없음(기존 과탐/과누락 동등). 범위 외.
  6. test runner 의 기존 실패 아티팩트는 `tests/task0034_runs/api-Q4.failed.whitelist_regex.20260422.json` 으로 보관 중 (2026-04-22 세션 내 이동).
- 설계 (실구현 기준):
  1. **1 차안의 한계** — `FROM|JOIN|,` 세 가지 prefix 만 정규식으로 요구하는 방안은 `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON ...` 같은 SQL 에서 SELECT 절의 `, be.Star` 를 comma-join 으로 오탐해 `be` 가 schema 로 추출되는 새 회귀를 만든다(실제 테스트 2026-04-22 에서 확인). SELECT 절 쉼표와 FROM 절 쉼표를 단일 정규식만으로는 구분할 수 없다.
  2. **2 단계 스캐너로 확정** — [tools.py:65-99](../../feature-0002-agent-core/src/modules/tools.py#L65-L99) 를 table-list 구간 슬라이스 + 내부 schema.table 추출 2 단계로 재구현.
     ```python
     _TABLE_LIST_RE = _re.compile(
         r"\b(?:FROM|JOIN)\b(.*?)"
         r"(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b"
         r"|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)",
         _re.IGNORECASE | _re.DOTALL,
     )
     _INNER_REF_RE = _re.compile(
         r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
     )
     # 1) FROM|JOIN 키워드 뒤 table-list 구간을 모두 잘라낸 뒤
     # 2) 그 내부에서만 schema.table 을 반복 추출
     ```
     - 바깥 정규식이 `FROM`/`JOIN` 뒤 table-list 구간을 lookahead terminator 로 경계 설정: `ON` / `WHERE` / `GROUP BY` / `ORDER BY` / `HAVING` / `LIMIT` / `UNION` / 다음 `FROM`·`JOIN` / `;` / `)` / EOS.
     - 안쪽 정규식은 그 구간 안에서만 동작하므로 SELECT/WHERE/ON/ORDER/GROUP 절의 `alias.column` 은 애초에 스캔 영역 밖.
     - FROM 뒤 comma join(`FROM a.x, b.y`) 은 자연스럽게 수용됨 — 콤마가 같은 FROM 슬라이스 내부이므로 두 스키마 모두 `_INNER_REF_RE` 에 매칭.
     - 대소문자 무시(`IGNORECASE`), 다중 라인 쿼리(`DOTALL`) 수용.
  3. **테스트 매트릭스 (15 케이스)** — in-process 호출로 다음 기대치를 모두 확인한다. (TASK-0040 구현 직후 실제 실행 결과 포함)
     - `SELECT bb.BattleType FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo` → `{dblog}` ✓ (기존 오탐: `{dblog, bb, be}`)
     - `SELECT * FROM dbgame.items i WHERE i.type='x'` → `{dbgame}` ✓
     - `SELECT * FROM dblog.battlebegin bb, dblog.battleend be WHERE bb.Id = be.Id` (comma join) → `{dblog}` ✓
     - `` SELECT * FROM `dblog`.`battlebegin` bb `` (백틱) → `{dblog}` ✓
     - `SELECT * FROM (SELECT 1 AS x) t JOIN dbgame.items i ON i.id=t.x` (서브쿼리) → `{dbgame}` ✓
     - `select * from dblog.t` (lower) → `{dblog}` ✓
     - `SELECT 1` (no FROM) → `∅` ✓
     - `SELECT bb.x FROM bb` (alias only) → `∅` ✓
     - `SELECT * FROM dbstat.foo` (비허용 스키마) → `{dbstat}` → 차단 ✓
     - `SELECT bb.BattleType, be.Star FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo WHERE bb.BattleType = 'CROSSROUTE' AND be.Star >= 3` (Q4-like) → `{dblog}` ✓
     - `SELECT * FROM dbgame.t INNER JOIN dblog.u ON t.a=u.a LEFT JOIN dbauth.v ON v.a=t.a` (3-way JOIN) → `{dbgame, dblog, dbauth}` ✓
     - `SELECT * FROM a.x, b.y WHERE 1=1` (2-way comma join) → `{a, b}` ✓
     - `SELECT * FROM dblog.orders o GROUP BY o.user ORDER BY o.date` (GROUP/ORDER terminators) → `{dblog}` ✓
     - `SELECT col1, col2, tbl.col3 FROM sch.tbl tbl WHERE tbl.x > 5 ORDER BY tbl.y` (SELECT 절 쉼표 + alias 함정) → `{sch}` ✓
     - `WITH x AS (SELECT * FROM a.b) SELECT * FROM x` (CTE) → `{a}` ✓
     - 보안 비회귀: `SELECT * FROM dblog.t LEFT JOIN dbstat.u ON t.a=u.a` → `{dblog, dbstat}` → whitelist 차단 ✓
  3. **범위 제한** — 코드 변경은 `unit/feature-0002-agent-core/src/modules/tools.py` 1 파일 약 5 줄. tool 시그니처·호출처·기타 모듈 수정 없음. `execute_sql` 외 tool 은 호출 인자 레벨에서 schema 가 이미 들어오므로 정규식과 독립이다.
  4. **회귀 방어** — 기존 TASK-0036 원안(REV-20260421-0004) 의 "모듈 전역 + finally" 패턴은 변경하지 않는다. Product whitelist 로 차단해야 하는 비허용 user schema (예: `SELECT * FROM dbstat.foo`) 는 새 정규식에서도 `FROM dbstat.foo` 매칭으로 포착되어 여전히 차단된다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` 문법.
  2. `docker compose up -d --build --force-recreate web` 후 위 테스트 매트릭스 8 케이스 in-process 호출 통과.
  3. `_whitelist_violation({'dblog', 'bb'})` → 기존 블로킹 메시지 반환, `_whitelist_violation({'dblog'})` + `set_active_schema_allowlist(['dbauth','dbgame','dblog'])` → `None`. 즉 정규식 출력이 올바르면 `_whitelist_violation` 은 변경 없이 통과/차단 판정이 정상.
  4. `python3 tests/task0034_runner.py --target api --only Q4,Q5` — TASK-0041 완료 후 최종 재수행. 이 시점에서는 whitelist regression 가 제거된 상태에서 Q4/Q5 가 전 턴 정상 응답/도구 호출을 수행하는지를 1 차 smoke 로 본다 (정답 내용 검증은 TASK-0034 보고서 업데이트 단계에서).
- 완료 조건:
  - TASK.md §2 / §3 업데이트 + TASK-0040 상세 설계 블록
  - tools.py 정규식 교체 + in-process 8 케이스 테스트 통과
  - Q4 재수행에서 whitelist 위반이 더 이상 발생하지 않음 확인 (최소 1 턴 정상 tool 호출 성공)
  - MODIFY.md 에 CHG-20260422-0013 append
  - REVIEW.md 는 추가 불필요(REV-20260421-0004 의 결정 틀 유지, 정규식 세부는 코드 주석 + 본 설계 블록으로 충분)
  - LEARNINGS.md 에 `LRN-20260422-0012 SQL 텍스트 스캔은 컨텍스트 조건(FROM|JOIN|,) 없이는 alias.column 과 schema.table 을 구분할 수 없다` append
  - REPORT.md §3 에 TASK-0040 한 줄 추가

### TASK-0041 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22): 상용 API `gpt-5.4-mini` 가 복잡 질의에 응답하는 데 최대 15 분 이상 소요되는 실사용 워크로드에서, 서버 `run_timeout_sec=900s` 이전이라도 **(a) 브라우저 탭 닫힘/새로고침**, **(b) 테스트 러너 httpx `ReadTimeout` (960s)**, **(c) 네트워크 일시 단절** 같은 사유로 클라이언트 연결이 끊겨도 agent 스레드는 `asyncio.to_thread(_run_agent_core, ...)` 의 worker 에서 계속 실행된다. 그러나 현재 웹 UI 와 test runner 는 끊어진 요청에 대해 "실패" 상태만 보이고 `AgentMemoryKv.last_status` / `AgentMemoryMessages.assistant` 에 뒤늦게 기록되는 결과를 회수할 공식 경로가 없다. 사용자 입장에서는 "이미 시작된 턴을 계속 기다릴지 / 즉시 포기할지" 를 다시 선택할 수 있어야 하고, 테스트 러너 입장에서는 timeout 직후 동일 대화의 결과를 폴링해 최종 응답이 도착하면 이후 턴을 정상 진행해야 한다.
- 현황/환경 분석 (코드 기준):
  1. [app.py `/api/ask`](../src/app.py#L3520) 는 `asyncio.to_thread(_run_agent_core, ...)` 로 agent 를 돌리고, 완료되면 `AgentMemoryKv.set_run_status('done'|'error'|'canceled', run_id=...)` + `AgentMemorySteps` + `AgentMemoryMessages` 에 persistence 가 이뤄진다(실제 상태값 참조: [agent_core.py:1542](../../feature-0002-agent-core/src/agent_core.py#L1542) `done` / L1537 `error` / L1524 `canceled`, `processing` 이 running). HTTP 응답이 나가기 전에 client 가 끊겨도 to_thread 는 cancel 되지 않으므로 최종 결과는 DB 에 저장된다(검증: `finally` 블록 + `set_run_status('done', ...)` 순서).
  2. [app.py `/api/progress`](../src/app.py#L4381) 는 이미 `(status, status_at, run_id, steps, step_count)` 를 반환한다. 그러나 `steps` 만 내려가고, 최종 `assistant` 메시지(`_load_latest_assistant_message`) 나 `last_error` / `last_duration_ms` 는 별도 응답에 없어 브라우저는 `/api/history` 를 재-GET 해 메시지 목록을 다시 당겨야 한다. Test runner 에는 이 경로가 구성돼 있지 않다.
  3. [app.py `/api/cancel`](../src/app.py#L4296), [app.py `/api/finalize`](../src/app.py#L4338) 는 `AgentMemoryKv.mark_cancel_requested` / `mark_finalize_requested` 로 **KV 플래그만 세팅** 하고 agent loop 가 step 경계마다 플래그를 체크해 self-terminate 하는 패턴이다. 본 TASK 는 이 기존 신호 경로를 유지·활용한다(새 플래그 없음).
  4. [memory.py `set_run_status`](../../feature-0002-agent-core/src/modules/memory.py#L920~L1030) 에 `last_status` / `last_status_run_id` / `last_status_at` / `last_duration_ms` / `last_error` 5 키가 이미 persist 된다. `is_processing_conversation(cid)` 헬퍼도 존재. 새 테이블/컬럼 추가 없이 status 를 읽을 재료가 전부 있다.
  5. [task0034_runner.py:186-204](../tests/task0034_runner.py#L186-L204) 의 httpx.ReadTimeout 브랜치는 현재 `{"error": "client-read-timeout"}` 턴을 추가하고 즉시 다음 턴으로 넘어간다 — 실행 중이던 agent 는 서버에서 계속 돌고, 완료 후에도 runner 는 조회하지 않는다.
  6. [app.py WEB_PARALLEL_LIMIT=6](../src/app.py) — 계정당 동시 `/api/ask` 슬롯은 6. attach/resume 엔드포인트는 read-only 이므로 이 슬롯을 점유하지 않아야 한다(중요 설계 제약).
- 설계:
  1. **신규 엔드포인트 `GET /api/ask_status`** — read-only 스냅샷. Query: `conversation_id`. 응답:
     ```json
     {
       "conversation_id": "20260422-...",
       "is_processing": true|false,
       "status": "processing|done|error|canceled|(empty)",
       "status_at": "2026-04-22T01:23:45Z",
       "run_id": "...",
       "step_count": 7,
       "duration_ms": 123456,
       "error": null | "...",
       "has_answer": true|false,    // latest assistant message at or after run_id 존재 여부
       "answer_preview": null | "첫 160자 미리보기 ..."
     }
     ```
     내부 구현은 기존 `_load_progress_status(conn, cid)` + `_load_step_count_for_run` + `_load_latest_assistant_message(conn, cid, role='assistant')` 헬퍼를 재사용하며, 슬롯 카운터는 건드리지 않는다. 권한: 해당 대화에 대한 `conversation.read.own/any`.
  2. **신규 엔드포인트 `GET /api/ask_result`** — long-poll. Query: `conversation_id`, `run_id`(optional — 특정 run 지정), `wait`(초, 기본 30, 최대 60). 로직:
     - `t0 = time.monotonic()` 시점의 status 를 `_load_progress_status` 로 읽는다.
     - `run_id` 가 명시된 경우: 서버의 `last_status_run_id` 가 그 run_id 이고 status ∈ {done, error, canceled} 이면 즉시 200 반환.
     - `run_id` 미지정: 현재 status 가 terminal 이면 즉시 반환.
     - 그 외에는 `await asyncio.sleep(0.5)` 루프를 돌며 최대 `wait` 초 동안 polling. 매 반복마다 status 재조회. Terminal 상태 진입 시 즉시 반환.
     - 타임아웃까지 terminal 도달 안 하면 `{"timeout": true, "status": "processing", "run_id": "...", "step_count": N}` 반환.
     - Terminal 도달 시 응답에 `{"status": "...", "run_id": "...", "duration_ms": ..., "error": ..., "assistant": {"message_id": 123, "content": "...", "meta": {...}, "steps_count": N}}` 포함. `assistant.content` 는 full. 권한은 위와 동일.
     - 슬롯 카운터 미점유 확인: `/api/ask` 의 `async with _acquire_account_slot(...)` 블록 외부에서 실행.
     - 내부 구현은 `asyncio.sleep` 기반 polling 이라 background task 추가 없음 → 복잡도 최소.
  3. **브라우저 UX (`src/static/app.js`)** —
     - `sendPrompt()` 내부에서 `fetch('/api/ask', ...)` 의 AbortController `timeoutMs = PROGRESS_MAX_SESSION_MS (예: 900_000ms)` 로 기본값 조정. 기존보다 길게.
     - `fetch` 가 `AbortError` / `TypeError: Failed to fetch` / HTTP 504/502 로 떨어지면 `/api/ask_status?conversation_id=CID` 를 호출해 `is_processing=true` 가 돌아올 때 **다이얼로그 `showTimeoutRecoveryDialog(conversation_id, run_id)`** 를 띄운다. 버튼: `[ 계속 기다리기 ]` / `[ 즉시 답변 ]` / `[ 요청 취소 ]`.
       - **계속 기다리기**: `/api/ask_result?conversation_id=...&run_id=...&wait=60` 을 background 에서 polling. terminal 반환 시 `refreshWorkspace(cid)` + 토스트. UI 에는 기존 progress polling 루프가 계속 동작(TASK-0037 의 `scheduleProgressPolling`).
       - **즉시 답변**: `POST /api/finalize` (기존 기능) → 이후 terminal 도달까지 `/api/ask_result` long-poll.
       - **요청 취소**: `POST /api/cancel` (기존) → 이후 terminal 도달까지 `/api/ask_result` long-poll 후 cancelled 결과 반영.
     - 페이지 로드(bootstrap) 또는 대화 전환 시, 선택된 대화의 `/api/ask_status` 를 1 회 호출해 `is_processing=true` 면 자동으로 attach mode 에 들어간다(브라우저를 껐다 켜도 이전 턴을 이어서 관찰).
     - 기존 `PROGRESS_POLL_*` 상수와 충돌하지 않도록 `/api/ask_result` 호출은 **별도 single-flight in-flight 플래그** (`state.resultWaitInFlight` Set by conversation_id) 로 관리.
  4. **Test runner (`tests/task0034_runner.py`) attach/resume** —
     - 현재 `httpx.ReadTimeout` 브랜치를 `{"error": "client-read-timeout", "attached": true}` 기록으로 남기되, 즉시 다음 턴으로 넘어가지 않고 아래 루프로 전환:
       - `attach_deadline = time.monotonic() + ATTACH_TIMEOUT_SEC` (기본 900.0, .env override `TASK0034_ATTACH_TIMEOUT_SEC`).
       - 루프: `resp = await client.get('/api/ask_result', params={'conversation_id': cid, 'run_id': rid, 'wait': 45})`. terminal 응답이면 기록 후 루프 종료. `{timeout: true}` 면 계속. `attach_deadline` 초과 또는 HTTP 오류 2 회 연속 시 fallback 으로 `{"error": "attach-timeout"}` 기록 후 다음 턴 진행.
       - `run_id` 는 timeout 직후 `/api/ask_status` 1 회 호출로 획득해 고정. 그래야 같은 대화의 "다음 run" 이 아니라 현재 돌던 run 의 결과만 기다린다.
     - 성공적으로 attach 된 경우 turn 객체에 `status="succeeded-via-attach"` + `attached_after_timeout=true` + 원본 steps/assistant 를 삽입해 이후 truth 대조 단계가 일반 턴과 동일하게 동작하도록 한다.
  5. **에러/보안 고려**:
     - `/api/ask_status`, `/api/ask_result` 모두 **read-only**. write 경로 없음. `mark_cancel_requested` / `mark_finalize_requested` 는 기존 `/api/cancel` / `/api/finalize` 를 그대로 사용 — 본 TASK 에서 새 side-effect 경로 도입 금지.
     - 슬롯 카운터 비점유: attach/resume 은 별도 계정에서도 호출 가능하지만 `conversation.read.*` 권한 만으로 충분. `/api/ask` 는 여전히 `conversation.ask` 소유자 제한 유지.
     - long-poll `wait` 상한 60 초로 한정해 느린 로드밸런서/ingress 타임아웃과 충돌 방지.
  6. **범위 제한**:
     - 서버 변경은 `src/app.py` 에 2 개 엔드포인트 + 기존 헬퍼 재사용(새 SQL/테이블/마이그레이션 없음).
     - 브라우저 변경은 `src/static/app.js` + `src/static/index.html` 의 다이얼로그 마크업 + `src/static/styles.css` 의 다이얼로그 스타일.
     - Test runner 변경은 `tests/task0034_runner.py` 의 ReadTimeout 브랜치 확장 + `ATTACH_TIMEOUT_SEC` 상수 추가.
     - 기존 `/api/cancel` / `/api/finalize` / `/api/progress` / `/api/ask` 시그니처는 변경하지 않는다.
- 검증:
  1. **문법**: `python3 -m py_compile src/app.py tests/task0034_runner.py`, `node --check src/static/app.js`.
  2. **컨테이너 재빌드**: `docker compose up -d --build --force-recreate web`.
  3. **단순 동작**: bootstrap_admin 로그인 → 새 대화 → 빠른 질의(`/api/ask`, 5초 완료) 실행 중에 `curl .../api/ask_status?conversation_id=...` 가 `is_processing=true|false` 및 terminal `status` 를 반환.
  4. **long-poll**: `curl .../api/ask_result?conversation_id=...&wait=5` 가 이미 terminal 이면 즉시 200, processing 이면 5 초 `{timeout:true}` 반환.
  5. **브라우저**: 일부러 `/api/ask` 를 AbortController 로 2 초 뒤 중단 → 다이얼로그 출현 → `계속 기다리기` 클릭 → agent 완료 후 메시지가 UI 에 주입.
  6. **Runner attach**: `ASK_TIMEOUT_SEC=10.0` 로 일시 축소한 후 `--only Q4` 로 돌려 runner 가 timeout → attach → 최종 turn 기록까지 이동하는지 확인. 정상 확인 후 960s 로 원복.
  7. **TASK-0034 재수행**: TASK-0040 선 완료 + 본 TASK 완료 상태에서 `python3 tests/task0034_runner.py --target api --only Q4,Q5` 를 돌려 whitelist regression + timeout attach 두 경로 모두 정상 동작함을 입증.
- 완료 조건:
  - TASK.md §2 / §3 / TASK-0041 상세 설계
  - app.py `/api/ask_status` + `/api/ask_result` 추가, 문법·컨테이너 재빌드 통과
  - app.js 다이얼로그 + attach polling + bootstrap attach 연결
  - index.html / styles.css 다이얼로그 마크업·스타일
  - task0034_runner.py attach 분기
  - 검증 항목 1-7 모두 통과
  - MODIFY.md 에 CHG-20260422-0014 append
  - REVIEW.md 에 REV-20260422-0007 append (장기 실행 에이전트에 대한 read-only attach/resume 패턴 채택 이유)
  - FUNCTION.md 의 API 목록에 `/api/ask_status`, `/api/ask_result` 추가
  - REPORT.md §3 에 TASK-0041 한 줄 추가
  - LEARNINGS.md 에 `LRN-20260422-0013 장기 실행 worker 는 client disconnect 과 agent finalize 경로가 독립적이어야 한다` append

### TASK-0039 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22): TASK-0036 이 `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` 통째 bypass 를 제거하면서 `mysql` / `performance_schema` / `sys` 를 기본 차단했지만, 실사용 중 "assistant 가 Product DB 의 테이블 구조를 찾지 못하는" 문제가 발견됐다. 원인: agent 가 본능적으로 `information_schema.TABLES` 외에 `sys.schema_table_statistics`, `performance_schema.tables`, 드물게 `mysql.*` 을 함께 조회해 교차 검증하려 하는데 이들이 전부 차단되면 재시도 루프에 빠지거나 `describe_schema` 만 반복하게 된다. 사용자는 메타데이터 4 종을 **Product 설정에 명시하지 않아도 항상 접근 가능** 하게 해달라고 요청했다. **`agent_memory` 는 예외** — 여기엔 다른 계정의 대화 내용, 세션, 권한 override 가 담겨 있어 여전히 차단 유지.
- 현황/환경 분석 (코드 기준):
  1. [tools.py:25-28](../../feature-0002-agent-core/src/modules/tools.py#L25-L28) `_SYSTEM_SCHEMAS` 는 `{information_schema, mysql, performance_schema, sys, agent_memory}` 5 종 frozenset. 이 집합은 두 용도로 쓰인다:
     - [tools.py:51-57](../../feature-0002-agent-core/src/modules/tools.py#L51-L57) `_is_user_schema(name)` — `list_schemas` 결과 post-filter 와 `search_tables` 의 `sys_exclude` 조건에서 "사용자 스키마가 아님" 판정. UX 용도.
     - [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94) `_whitelist_violation(refs)` — agent tool 레벨 접근 차단 결정. Security 용도.
  2. 현재 `_whitelist_violation` 은 `allowed = _ACTIVE_SCHEMA_ALLOWLIST | {information_schema}` 로 **information_schema 1 종만** bypass. 나머지 `sys`/`mysql`/`performance_schema`/`agent_memory` 는 whitelist 에 명시적으로 등록하지 않으면 차단.
  3. `_is_user_schema` 는 `_SYSTEM_SCHEMAS` 에 포함된 스키마를 전부 "사용자 스키마 아님" 으로 판정해 `list_schemas` 결과에서 숨기는 UX 동작을 한다. 이건 사용자의 요청 의도("목록 내 유무와 관계없이 **접근** 가능") 와 무관하게 유지해도 된다 — agent 는 `describe_schema('information_schema')` / `execute_sql("SELECT ... FROM information_schema...")` 로 명시 호출이 가능하고, `list_schemas` 결과에 카탈로그 스키마를 섞어 보여주는 건 오히려 탐색 노이즈.
  4. [tools.py:451](../../feature-0002-agent-core/src/modules/tools.py#L451) `search_tables` 의 `sys_exclude` 도 `_SYSTEM_SCHEMAS` 전체를 WHERE NOT IN 으로 제외 — 키워드 검색이 메타데이터 테이블을 섞어 반환하면 결과가 지저분해지므로 이 동작도 유지.
- 설계:
  1. **스키마 상수를 두 카테고리로 분리** — [tools.py:24-28](../../feature-0002-agent-core/src/modules/tools.py#L24-L28):
     ```python
     # 메타데이터 스키마 — Product whitelist 와 무관하게 agent tools 가 항상 접근 가능.
     # DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요해 기본 허용한다.
     _METADATA_SCHEMAS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})
     # 에이전트 내부 스키마 — whitelist 로 차단 유지. 타 계정 대화/세션/권한 데이터 보호.
     _INTERNAL_SCHEMAS = frozenset({"agent_memory"})
     # 기존 호환: list_schemas/search_tables 의 "사용자 스키마 아님" 판정에 사용.
     _SYSTEM_SCHEMAS = _METADATA_SCHEMAS | _INTERNAL_SCHEMAS
     ```
  2. **`_whitelist_violation` bypass 집합 교체** — [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94):
     - `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | {"information_schema"}` → `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | _METADATA_SCHEMAS`
     - 결과: agent 가 `execute_sql("SELECT ... FROM mysql.user")`, `describe_schema("sys")`, `describe_table("performance_schema", "tables")` 류 호출을 시도하면 Product 설정과 무관하게 통과.
     - `agent_memory` 는 `_METADATA_SCHEMAS` 에 없으므로 기존처럼 차단.
     - 비허용 user schema (예: 임의의 `dbstat`) 도 기존처럼 차단.
     - 에러 메시지에 "메타데이터 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 는 항상 접근 가능" 한 줄을 덧붙여, LLM 이 차단된 user schema 를 메타데이터 쿼리로 리디렉션할 수 있는 힌트 제공.
  3. **`_is_user_schema` / `search_tables` 는 그대로 유지** — `list_schemas` 결과에 메타데이터 4 종 노출 여부는 UX 결정 영역이고 현재는 숨김이 더 자연스럽다. agent 는 시스템 프롬프트의 KNOWN SCHEMAS 힌트 없이도 `execute_sql` 로 `information_schema.TABLES` 를 직접 조회할 수 있어 구조 탐색에 문제가 없다.
- 보안 고려 (REV-20260422-0006 으로 문서화):
  1. `mysql.user` 등이 bypass 경로를 타게 되지만, **DB 커넥터가 사용하는 MySQL 계정에 `mysql.*` SELECT 권한이 없으면 실행 단계에서 차단** 된다. whitelist 는 tool-레벨 1 차 방어이고 MySQL GRANT 가 2 차 방어로 남는다.
  2. `performance_schema` / `sys` 는 민감도 낮음(런타임 stat + 뷰).
  3. `information_schema` 는 원래부터 허용돼 있었다.
  4. 이 완화는 **현 리포의 agent read-only SQL 특성** 을 전제로 한다. write 가능 계정을 agent 가 쓰게 된다면 이 결정을 재검토해야 한다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` → 문법.
  2. `docker compose up -d --build web` 후 컨테이너 내부에서 직접 호출:
     ```python
     from modules.tools import set_active_schema_allowlist, _whitelist_violation
     set_active_schema_allowlist(["dbgame"])
     assert _whitelist_violation({"mysql"}) is None
     assert _whitelist_violation({"sys"}) is None
     assert _whitelist_violation({"performance_schema"}) is None
     assert _whitelist_violation({"information_schema"}) is None
     assert _whitelist_violation({"dbgame"}) is None
     assert "agent_memory" in (_whitelist_violation({"agent_memory"}) or "")
     assert "dbstat" in (_whitelist_violation({"dbstat"}) or "")
     ```
  3. 실사용 스모크: bootstrap_admin 로그인 → 새 대화(Product=KR) → `/api/ask` 로 "information_schema 에서 dbgame 의 테이블 개수" → 성공 응답.
  4. 회귀 방어: whitelist 미설정 상태(`_ACTIVE_SCHEMA_ALLOWLIST is None`) 에서는 `_whitelist_violation` 이 즉시 `None` 반환하는 경로가 유지됨(코드 L80-L81).
- 범위 제한:
  - 코드 변경은 `unit/feature-0002-agent-core/src/modules/tools.py` 한 파일(약 10 줄).
  - `_is_user_schema` / `search_tables` / `list_schemas` UX 동작은 손대지 않는다.
  - 시스템 프롬프트의 "KNOWN SCHEMAS" 블록 포맷도 손대지 않는다 — agent 가 이미 information_schema 경로를 잘 찾는다.
- 완료 조건:
  - TASK.md §2 / §3.1 / 상세 설계 블록 추가
  - tools.py 반영 + in-process 테스트 통과
  - MODIFY.md 에 `CHG-20260422-0012` append
  - REVIEW.md 에 `REV-20260422-0006` append (REV-20260421-0005 supersede 관계 명시)
  - FUNCTION.md AC-0010 보강
  - REPORT.md §3 에 TASK-0039 한 줄 추가
  - git commit + push

### TASK-0038 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22, TASK-0034 Q4/Q5 원인 분석 후): Q4 conversation `20260421084441-6b71b1b1` 은 대화 생성(17:44:41) → step 1 `execute_sql` 실패(17:44:46) → step 2/3 `describe_table` 완료(17:44:48) 후 10분 공백 후 클라이언트 600s read-timeout 으로 종료됐다. DB 에는 `assistant` 메시지가 0 건, run_id 가 1 개만 존재해 **turn 1 의 agent 가 LLM 호출 단계에서 무한 대기** 한 것으로 판정됐다. 그 사이 클라이언트는 먼저 포기했지만 서버 thread pool 은 해당 스레드를 계속 물고 있어 Q4 turn 2 는 persist 이전에 풀 경쟁에 막혔고, Q5 는 60s 안에 `/api/auth/login` ConnectTimeout 으로 실패했다.
- 현황/환경 분석 (코드 기준):
  1. `agent_core.py:1134` `client = OpenAI(**client_kwargs)` — OpenAI Python SDK v1 은 `timeout` 인자가 없으면 내부 httpx 기본(연결당 10 분 수준) 을 쓰되, 실제로는 서버가 SSE 스트림을 끊지 않는 한 무한 대기한다. `chat.completions.create(...)` 호출([L999](../../feature-0002-agent-core/src/agent_core.py#L999)) 도 per-request timeout 을 지정하지 않는다.
  2. `modules/llm.py` 는 이미 `_get_openai_client(timeout_sec=...)` 헬퍼에서 `timeout + max_retries + ThreadPoolExecutor wall-clock deadline` 패턴을 구현해 뒀다([llm.py:482~529](../../feature-0002-agent-core/src/modules/llm.py#L482)) — 동일한 상한 개념을 `agent_core.py` 의 메인 루프 클라이언트에도 적용하기만 하면 된다. 최소 변경 원칙으로 `modules/llm.py` 를 통째 재사용하는 대신 `OpenAI(...)` 초기화에 `timeout`/`max_retries` 만 얹는 것으로 제한한다.
  3. `modules/config.py:283` `AGENT_OPENAI_MAX_RETRIES=int(os.getenv("AGENT_OPENAI_MAX_RETRIES","0"))` 는 이미 존재하므로 환경변수 계약을 깨지 않는다. `.env` 에는 기본값 미설정 → 0 (재시도 비활성).
  4. `agent_core.py:1255~1258` `run_timeout_sec = max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)`. `.env` 에는 `AGENT_TIMEOUT_SEC=300, AGENT_EARLY_FINALIZE_MS=180000` 이므로 `run_timeout_sec = max(900, 180) = 900s` 고정.
  5. 러너 `task0034_runner.py:52` `ASK_TIMEOUT_SEC=600.0` → httpx client 의 per-request timeout. 600 < 900 이므로 클라이언트가 항상 서버보다 먼저 포기한다.
- 설계:
  1. **agent_core `OpenAI` 초기화에 timeout/max_retries 반영** — [`agent_core.py:26~32`](../../feature-0002-agent-core/src/agent_core.py#L26) 의 `from modules.config import` 에 `AGENT_OPENAI_MAX_RETRIES` 를 추가. [L1134](../../feature-0002-agent-core/src/agent_core.py#L1134) `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5, int(AGENT_TIMEOUT_SEC)), max_retries=max(0, int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. 개별 `chat.completions.create` 호출은 그대로 두되, client-level timeout 이 httpx transport 에 상속되므로 모든 호출에 wall-clock 상한이 걸린다.
  2. **test runner ASK_TIMEOUT_SEC 인상** — `tests/task0034_runner.py:52` `ASK_TIMEOUT_SEC = 600.0` 을 `ASK_TIMEOUT_SEC = 960.0` 으로 변경. 주석으로 "`> run_timeout_sec=900`" 근거를 명시. 다른 타임아웃(`httpx.AsyncClient(timeout=60.0)` 기본값) 은 fast endpoint 전용이므로 손대지 않는다.
  3. **환경변수 override 경로는 유지** — `AGENT_TIMEOUT_SEC` / `AGENT_OPENAI_MAX_RETRIES` 모두 `os.getenv` 로 오버라이드 가능. 운영에서 더 짧게(예: 90s) 조이고 싶으면 .env 만 바꾸면 된다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/tests/task0034_runner.py` → 문법 체크.
  2. `grep -nE "OpenAI\(.*timeout" unit/feature-0002-agent-core/src/agent_core.py` 가 L1134 를 반환하는지 확인.
  3. `grep -n "ASK_TIMEOUT_SEC" unit/feature-0003-agent-web-ui/tests/task0034_runner.py` 에서 960.0 확인.
  4. `docker compose up -d --build web` → 신규 이미지 기동, `/api/session` 200 OK, bootstrap_admin 로그인 성공, `/api/new_conversation` + `/api/ask` 로 짧은 질의("SHOW DATABASES;" 수준) 가 정상 응답하는지 in-host curl 로 확인.
  5. 의도적 timeout 유발: 로컬 환경에서 AGENT_TIMEOUT_SEC=3 + 긴 질의로 `openai.APITimeoutError` 가 step error 로 흡수되는지 (기존 `try/except Exception` 경로가 삼키는지) 확인 — 단, prod .env 에 영향이 없도록 임시 override 만 사용.
- 범위 제한:
  - 코드 변경은 `agent_core.py`(2줄: import + OpenAI() 확장) 와 `task0034_runner.py`(1줄) 로 제한.
  - 원인 분석 3(질문 follow_up trigger 확장) / 4(러너 격리/쿨다운) 는 본 TASK 범위 외. TASK-0034 재실행 단계에서 별도 처리.
  - `modules/llm.py` 의 `_openai_chat_completion_with_deadline` 패턴 통합 리팩터는 위험도/변경폭이 커 별도 TASK 로 분리.
- 완료 조건:
  - TASK.md §2 / §3.1 / 상세 설계 블록 추가
  - agent_core.py + task0034_runner.py 반영
  - `docker compose up -d --build web` 후 `/api/session` probe 통과
  - MODIFY.md 에 `CHG-20260422-0011` append
  - REPORT.md §3 에 TASK-0038 한 줄 추가
  - git commit + push

### TASK-0037 상세 설계 (2026-04-22)
- 문제/목적 (사용자 보고 2026-04-22 01:07 KST): TASK-0034 복잡 QA 성능 테스트(상용 API gpt-5.4-mini, 대화당 ~3분/턴) 를 돌리면서 브라우저 탭을 열어두면 `/api/progress` 요청이 지속적으로 쌓이는 현상이 관찰됐다. 이 "폴링이 끝없이 요구되는" 증상은 다른 작업자 AI 가 TASK-0036 PR 에 같이 묶어 해결(27127b9)한 상태라, 본 세션에서는 **수정 내용을 리뷰하고 설계·학습 문서에 반영**하는 것이 목표다.
- 현황/환경 분석 (수정 전 코드 기준):
  1. `src/static/app.js` 의 폴링 루프는 `setInterval(pollProgress, 1500)` 단일 `state.progressPoller` 핸들로 동작했다. `pollProgress()` 는 fetch 후 await 하는데, `/api/progress` 응답이 느리면 다음 `setInterval` tick 이 먼저 발화해 **동시 in-flight 요청이 1 을 넘길 수 있는 구조**.
  2. 대화 전환/로그아웃 시 `stopProgressPolling()` 이 `clearInterval` 만 호출하고 이미 발행된 fetch 를 취소하지 않아, 서버 측에는 **스텁 요청이 뒤늦게 계속 도착**.
  3. `/api/progress` 핸들러는 `_load_steps_for_run(conn, cid, run_id)` 로 **해당 run 의 전체 step 을 매번 파이썬 메모리로 로드**하고 `[s for s in all_steps if step_index > after_step]` 로 필터링했다. 서버 `AgentMemorySteps` 가 쌓이는 장기 대화일수록 폴링 비용이 O(N) 으로 증가.
  4. 서버는 `after_step` 만 받고 `client_run_id` 는 없어서, **클라이언트가 들고 있는 run_id 가 서버 최신 run_id 와 달라도** 서버가 그것을 감지할 수 없었다. 결과: 새 run 이 시작됐는데 클라이언트는 과거 run 의 `after_step` 을 계속 들고 와 **신규 step 0..K 를 놓침**.
  5. `document.hidden` 상태(탭 전환) 에서도 1500ms 주기가 그대로 유지 — 탭이 백그라운드여도 매초 한 번 네트워크/CPU 를 쓴다.
- 설계 (TASK-0036 시점에 실제 적용된 구조, 본 TASK-0037 은 이를 검토·문서화):
  1. **클라이언트 상태 모델 확장** — `state` 에 `progressPollInFlight:boolean`, `progressPollSeq:number`, `progressAbortController:AbortController`, `progressErrorCount:number` 추가. 기존 `progressPoller`(timer handle), `progressSteps`(누적 step 캐시), `progressRunId`(현재 추적 중인 run), `progressAfterStep`(다음 폴링의 after_step 값) 와 결합해 **폴링 생명주기** 를 정확히 모델링.
  2. **`setInterval` → 순번 기반 `setTimeout` 체인** — `scheduleProgressPolling(delayMs, seq)` 는 `clearProgressPollTimer()` 후 `setTimeout(() => pollProgress(seq).catch(()=>{}), nextDelay)` 단 하나만 예약. `pollProgress(seq)` 는 실행 시작 때 `seq !== state.progressPollSeq || progressPollInFlight` 이면 즉시 return, 끝날 때 다시 `scheduleProgressPolling(nextDelay, seq)` 로 다음 한 번을 예약한다. 즉 타임라인 상 항상 `[fetch] → [응답] → [다음 fetch 예약]` 순차 체인 구조가 보장되어 **in-flight 요청 수 ≤ 1** 가 코드로 강제됨.
  3. **AbortController 기반 취소 경로** — 매 poll 마다 `new AbortController()` 를 `state.progressAbortController` 에 저장하고 fetch 에 signal 로 전달. `stopProgressPolling({abort:true})` 는 이를 `.abort()` 호출해 in-flight fetch 를 즉시 끊는다. 추가로 `setTimeout(() => controller.abort(), PROGRESS_FETCH_TIMEOUT_MS=4000)` 로 서버 응답 지연 상한도 보장.
  4. **적응형 폴링 주기** — `PROGRESS_POLL_ACTIVE_MS=1200ms`(신규 step 스트리밍 중), `PROGRESS_POLL_IDLE_MS=3000ms`(기본), `PROGRESS_POLL_HIDDEN_MS=10000ms`(탭 배경화), `PROGRESS_POLL_ERROR_MS=8000ms`(에러 후). `scheduleProgressPolling(delayMs)` 진입부에서 `document.hidden` 이면 `Math.max(delayMs, PROGRESS_POLL_HIDDEN_MS)` 로 하한을 올려, 어떤 경로로 빠른 delay 가 들어와도 탭이 숨겨져 있으면 자동 감속.
  5. **에러 백오프 + 포기 조건** — `progressErrorCount` 를 각 예외 경로(fetch 에러/timeout) 마다 증가시키고, 3회 미만이면 `PROGRESS_POLL_ERROR_MS=8000` 으로 재시도하되 3회 이상이면 아예 재스케줄링하지 않는다(`shouldSchedule = errorCount < 3`).
  6. **서버 `/api/progress` 최적화** — `_load_progress_status(conn, cid)` 로 `(status, status_at, run_id)` 를 단일 커서에서 반환. `_load_steps_for_run(..., after_step=0)` 은 `after_step > 0` 이면 SQL `WHERE step_index > %s` 조건을 직접 걸어 **DB 에서 바로 필터링** (python 측 list comprehension 제거). 핸들러는 async → sync 로 바뀌고(블로킹 mysql 호출과 단순 수식 뿐이라 이벤트 루프 점유 이득 없음), `client_run_id` 가 없거나 서버 최신 run_id 와 다르면 `next_after_step = 0` 으로 리셋해 응답에 해당 run 의 모든 step 을 담아 되돌려준다 — 클라이언트가 `applyProgressPayload` 에서 `runId !== state.progressRunId` 를 감지해 캐시를 새 run 으로 교체.
  7. **라이프사이클 API 일관화** — `startProgressPolling({reset=false, runId=""})` 은 이전 체인을 `stopProgressPolling({reset:false, abort:true})` 로 끊고 `progressPollSeq` 를 한 칸 올린 뒤 `scheduleProgressPolling(0, seq)` 로 즉시 첫 poll 을 예약한다. `stopProgressPolling({reset, abort})` 은 `reset=true` 일 때 `resetProgressTracking()` 을 호출해 캐시/run_id/after_step 을 0으로 복원 — 대화 전환/로그아웃/새 대화 생성 등 "새로 시작해야 하는" 경로에서 명시적으로 reset 을 지정.
- 검증 (코드 리뷰 + 정적 확인 — 이미 커밋된 변경이므로 신규 runtime 배포 불필요):
  1. `grep -c "setInterval" src/static/app.js` = 0. 기존 고정 주기 루프가 폴링 경로에 남아있지 않음.
  2. `grep -nE "PROGRESS_POLL_(ACTIVE|IDLE|HIDDEN|ERROR)_MS|PROGRESS_FETCH_TIMEOUT_MS" src/static/app.js` 로 5 개 상수(lines 67-71) 모두 선언 확인, `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조.
  3. `progressPollSeq` 증가 지점(3곳): `stopProgressPolling()`, `startProgressPolling()`, `applyProgressPayload()` 계열 콜러에서 새 run 감지 시. 각 poll 은 `seq !== state.progressPollSeq` 로 자신이 구버전인지 체크.
  4. `AbortController` 배치: `pollProgress` 는 `controller = new AbortController()`, `timeoutId = setTimeout(controller.abort, 4000)`, `fetch(url, {signal: controller.signal})`, `finally` 에서 `clearTimeout(timeoutId)` + `state.progressAbortController = null if matches controller`.
  5. 서버 측 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 선언하고 `if not run_id or str(client_run_id or "").strip() != run_id: next_after_step = 0` 조건을 가진다 (line 4405-4406).
  6. 사용자 수신 상태 플로우: `status != 'processing'` 이면 `stopProgressPolling({abort:false})` + `refreshWorkspace(cid)` 호출 — 즉 서버가 done/failed 를 돌려주는 순간 클라이언트 폴링이 종료되고 workspace 가 최종 상태로 refresh 된다.
- 영향/후속:
  1. TASK-0034 같이 턴당 수분 걸리는 워크로드에서도 브라우저에서 `/api/progress` 요청이 쌓이지 않는다. 서버 측 로그/DB/네트워크 부하가 선형에서 상수 시간대로 감소.
  2. 현재는 LEARNINGS.md 에 폴링 패턴 학습 기록이 없다. 본 TASK 로 `LRN-20260422-0011 장시간 작업 폴링은 setInterval 이 아니라 순번 기반 setTimeout 체인 + AbortController + document.hidden 감지가 기본` 을 추가.
  3. TASK-0036 MODIFY 항목(CHG-20260421-0009) 에는 폴링 리팩터가 언급되지 않았다. 본 TASK 에서 별도 CHG 로 분리하지 않고 CHG-20260421-0009 Notes 에 한 줄을 보강하는 대신, 문서화 목적이므로 `CHG-20260422-0010` 으로 따로 기록하는 것이 다른 feature/에이전트 가 "폴링 개선" 키워드로 검색할 때 발견 가능성이 높다 — 따라서 별도 CHG 로 분리.
- 범위 제한:
  - 신규 코드 변경 없음(이미 27127b9 에 반영됨).
  - 문서 갱신만 수행: `docs/TASK.md`(본 항목 + 체크리스트), `docs/MODIFY.md`(CHG-20260422-0010), `docs/LEARNINGS.md`(LRN 추가), `docs/REPORT.md`(검증 결과 한 줄).
- 완료 조건:
  - TASK.md §2 Task Queue 에 TASK-0037 `[x]` 가 올라가고 §3.1 Recently Done 에 본 요약이 들어간다.
  - LEARNINGS.md 에 폴링 패턴 LRN 항목이 추가된다.
  - MODIFY.md 에 CHG-20260422-0010 문서화 전용 엔트리가 append 된다.
  - git commit + push 가 완료된다.

### TASK-0036 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 현재 `SYSTEM_PROMPT` 는 `agent_core.py:70` 에 하드코딩되어 있고, 조직/도메인/사용자별 맞춤 지침을 주입할 방법이 없다. 운영 중 "이 Role 은 이렇게 답하게 해달라", "특정 계정은 본인 전용 스타일 지침을 추가하고 싶다" 같은 요구가 반복된다.
  2. 현재 agent 는 `DB_CONNECT_DB` 로 default schema 만 고정되어 있고 `_SYSTEM_SCHEMAS` 외의 모든 user schema 에 무차별로 접근한다. 실제로는 서비스 경계(국가/팀/도메인) 단위로 "이 Product 는 이 DB 세트만 본다" 로 묶어야 한다.
  3. 현재는 Product 가 하나지만(초기 값으로 `KR` 부여, 접근 DB: `dbgame`/`dblog`/`dbauth`), 이후 다른 Product 가 추가될 것이므로 **Role/Account 와 대등한 위상의 정본 테이블** 로 관리해야 한다.
- 현황/환경 분석 (출발점 근거):
  1. `SYSTEM_PROMPT` ([agent_core.py:70](../../feature-0002-agent-core/src/agent_core.py#L70)) 는 `run_agent` ([agent_core.py:935](../../feature-0002-agent-core/src/agent_core.py#L935)) 안 `system_content = SYSTEM_PROMPT` ([L1090](../../feature-0002-agent-core/src/agent_core.py#L1090)) 에서 origin_request/thread_goal/knowledge_ctx 와 합쳐진다. `run_agent` 호출은 web 측 `app.py` 가 in-process 로 수행 ([app.py:3260](../src/app.py#L3260)) 하므로 kwarg 추가가 쉽다.
  2. RBAC 정본은 `WebPermissions` / `WebRoles` / `WebRolePermissions` / `WebAccountPermissionOverrides` 이고 account ↔ role 은 `WebAccounts.RoleId` 이다 ([app.py:1477~1570](../src/app.py#L1477)). Product 는 이 구조와 대등하게 `WebProducts` / `WebProductDatabases` (+ 계정/대화별 Product 참조) 를 추가하면 자연스럽다.
  3. 도구 구현 `tools.py` ([feature-0002-agent-core/src/modules/tools.py:23](../../feature-0002-agent-core/src/modules/tools.py#L23)) 의 `_SYSTEM_SCHEMAS` + `_is_user_schema` 만으로 스키마 필터가 결정된다. 여기에 **실행 시점 whitelist** 를 추가하고 execute_sql 에서 `schema`.`table` 참조를 검사하면 접근 제한이 가능하다.
  4. admin console 은 "대시보드/계정/역할" 3 탭 ([admin.html:24~36](../src/static/admin.html#L24)) 이고, 4 번째 탭 "상품" 추가가 자연스럽다. 프로필 드로우는 "계정/보안/API Vault" 3 탭 ([index.html:187~189](../src/static/index.html#L187)) 이고 여기에 "프롬프트" 탭 추가.
  5. 대화의 Product 결정: `AgentCoreConversations` 에 `product_id` 컬럼 추가. 새 대화는 계정의 default product (추후 account-level 선택 가능) 로 고정. fork 시 원본 product_id 를 그대로 상속.

- 설계 (Plan-Review-Execute, 위험도: Moderate — 신규 테이블 3개 + permission 2개 + admin/prompt API + UI 2곳 + agent_core signature 확장):

  A. DB 스키마 (`_ensure_web_tables` 확장)
     ```
     WebProducts (
       Id BIGINT AUTO_INCREMENT PK,
       ProductKey VARCHAR(32) UNIQUE NOT NULL,   -- 'KR', 'JP', ...
       Name VARCHAR(128) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       IsActive TINYINT(1) DEFAULT 1,
       IsDefault TINYINT(1) DEFAULT 0,           -- 대화 생성 시 기본 product
       SortOrder INT DEFAULT 100,
       CreatedAt/UpdatedAt
     )
     WebProductDatabases (
       ProductId BIGINT NOT NULL,
       SchemaName VARCHAR(64) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       SortOrder INT DEFAULT 100,
       CreatedAt,
       PRIMARY KEY (ProductId, SchemaName)
     )
     WebSystemPrompts (
       Id BIGINT AUTO_INCREMENT PK,
       Scope ENUM('product','role','account') NOT NULL,
       ProductId BIGINT NULL,                    -- scope=product: 필수, role/account: nullable(=범용)
       RoleId BIGINT NULL,                       -- scope=role 만 사용
       AccountId BIGINT NULL,                    -- scope=account 만 사용
       Content MEDIUMTEXT NOT NULL,
       UpdatedAt, UpdatedByAccountId,
       UNIQUE KEY UX_Scope (Scope, ProductId, RoleId, AccountId)
     )
     AgentCoreConversations.product_id BIGINT NULL   -- 대화가 속한 Product
     ```
     - seed (`_ensure_seed_products`): ProductKey=`KR`, Name=`Korea`, IsDefault=1, IsActive=1. 연결 DB: `dbgame`, `dblog`, `dbauth`.

  B. Permission 추가 (PERMISSION_DEFINITIONS)
     - `product.manage` (그룹: `관리`) — Product/ProductDatabases CRUD + Product scope prompt 쓰기. 기본으로 admin role 에 부여.
     - `system_prompt.manage.role.any` (그룹: `관리`) — Role scope prompt 쓰기. admin role 에 부여.
     - Account scope prompt 는 본인 자신은 언제나 읽기/쓰기 가능 (별도 permission 불요). 다른 계정의 account scope prompt 는 `system_prompt.manage.role.any` 가 있어야 관리 가능 (감사성 측면).
     - Product 자체 조회(`products.read`)는 "로그인한 모든 계정"에 기본 허용 — 대화 생성 시 product 선택/표시를 위해 필요. 따라서 세션 payload 에 products 목록만 내려주고 별도 permission 체크는 생략한다. CUD 는 `product.manage` 로만 가드.

  C. 시스템 프롬프트 조립 함수 (`agent_core.py`)
     - 신규 함수 `compose_system_prompt(mem_conn, *, product_id, role_id, account_id) -> str`:
       ```
       [BASE SYSTEM_PROMPT]
       (product prompt 있으면) "\n\n## PRODUCT CONTEXT ({product_key})\n{content}"
       (role prompt 있으면)    "\n\n## ROLE GUIDANCE ({role_key})\n{content}"
       (account prompt 있으면) "\n\n## ACCOUNT PREFERENCES\n{content}"
       ```
     - role/account scope prompt 는 `ProductId=NULL`(전 Product 공통) 과 `ProductId=X`(해당 product 전용) 둘 다 가능. product-specific 이 있으면 그걸 쓰고 없으면 generic fallback.
     - Product 가 없거나 prompt 가 비어 있으면 기존 동작(base prompt 만) 과 동일.
     - `run_agent` 는 신규 kwargs `product_id: int | None = None`, `role_id: int | None = None`, `account_id: int | None = None` 을 받아 `system_content = compose_system_prompt(...)` 을 사용. 이어서 기존 `CONVERSATION CONTEXT` + `knowledge_ctx` 를 현재 순서 그대로 뒤에 붙인다.

  D. DB 접근 whitelist (tools.py)
     - 모듈 전역 `_ACTIVE_SCHEMA_ALLOWLIST: set[str] | None = None` 추가. `None` 이면 기존 동작(모든 user schema), set 이면 whitelist 필터 적용.
     - `_is_user_schema` 는 유지하고, whitelist 가 set 이면 그 추가 조건으로 AND 필터. `_tool_list_schemas` / `_tool_describe_schema` / `_tool_describe_table` / `_tool_search_tables` / `_tool_execute_sql` 모두 반영.
     - execute_sql 은 SQL 에서 ``\`schema\`.\`table\``` 또는 `schema.table` 패턴을 정규식으로 추출해 whitelist 밖 스키마가 있으면 즉시 에러(`"접근이 허용되지 않은 스키마: X"`).
     - `run_agent` 는 `allowed_schemas: list[str] | None` kwarg 를 추가로 받아, 실행 시작 시 `tools.set_active_schema_allowlist(...)` 로 세팅하고 종료 시 `None` 으로 복원(try/finally).

  E. app.py 계약
     - 신규 헬퍼: `_get_product_for_conversation(conn, conversation_id)` — `AgentCoreConversations.product_id` 를 읽어 없으면 default product 로 fallback.
     - 새 대화 생성 (`/api/new_conversation`, `/api/fork_conversation`, 자동 생성): `product_id` = request body 의 `product_id` (optional) → fallback 으로 `account` 의 해당 Product (향후) → fallback 으로 default product.
     - `/api/ask` 는 대화의 product_id 를 조회 → 해당 product 의 DB schema 리스트 조회 → `run_agent(..., product_id=pid, role_id=rid, account_id=aid, allowed_schemas=schemas)` 로 전달.
     - 신규 admin API:
       - `GET /api/admin/products` — 목록 (`product.manage` 없이도 읽기 허용 = 공용 카탈로그)
       - `POST /api/admin/products` body: `{product_key, name, description?, is_active?, is_default?, sort_order?}` (`product.manage`)
       - `PATCH /api/admin/products/{id}` — 같은 필드 (`product.manage`)
       - `DELETE /api/admin/products/{id}` — 해당 product 를 쓰는 대화가 있으면 거부 (`product.manage`)
       - `GET /api/admin/products/{id}/databases` — 스키마 목록
       - `PUT /api/admin/products/{id}/databases` body: `{databases: [{schema_name, description?, sort_order?}, ...]}` — 전체 교체 (`product.manage`)
       - `GET /api/admin/system-prompts?scope=product|role|account&product_id=&role_id=&account_id=` — 해당 스코프 리스트
       - `PUT /api/admin/system-prompts` body: `{scope, product_id?, role_id?, account_id?, content}` — upsert. scope=role 은 `system_prompt.manage.role.any`, scope=account 는 본인이 아니면 `system_prompt.manage.role.any` 필요.
       - `DELETE /api/admin/system-prompts/{id}` — 같은 권한 규칙.
     - 신규 self API:
       - `GET /api/auth/me/system-prompts` — 본인의 account scope prompt 목록 (product_id 별)
       - `PUT /api/auth/me/system-prompt` body: `{product_id?, content}` — 본인 upsert (본인 계정 대상은 권한 불요).
     - 세션 응답 (`/api/auth/me`) 에 `products: [{id, product_key, name, is_default}]` 를 추가해 프론트가 드롭다운/라벨에 사용.

  F. UI — admin console
     - 탭 추가 `상품` (admin.html): 대시보드/계정/역할 다음에 배치. 좌측 list + 우측 detail 패턴으로 구성 (기존 Role 관리와 같은 layout 재사용).
     - Detail 구성:
       1. 기본 정보 섹션 (ProductKey/Name/Description/IsActive/IsDefault/SortOrder)
       2. **접근 DB** 섹션 — "계정 카테고리와 별개" 라는 사용자 요구에 따라 구분선 + 명시적 헤더 (`접근 가능 DB 스키마`) 로 그룹화. 해당 product 에 등록된 schema 를 chip 으로 보여주고, 텍스트 입력 + `추가` 버튼 + 각 chip 옆 `×` 삭제.
       3. **시스템 프롬프트** 섹션 (Product scope) — textarea + 저장. scope=product, ProductId=현재 product 로 upsert.
     - Role detail 에도 **시스템 프롬프트** 섹션 추가:
       - Product 드롭다운 (첫 항목 `(전 Product 공통)`, 그 아래 구분선 후 Product 목록) + textarea + 저장. 저장 시 scope=role, RoleId=현재 role, ProductId=(선택값 or NULL).
     - Products 탭은 `product.manage` 가 없으면 read-only 상태(수정/삭제 버튼 disable + 저장시 에러 토스트)로 보인다. 어떤 계정도 product 목록 자체는 볼 수 있어야 profile 화면에서 product 별 prompt 를 지정할 수 있다.

  G. UI — 프로필 드로우
     - 드로우 탭에 `프롬프트` 추가 (계정/보안/API Vault/프롬프트).
     - 내부: Product 드롭다운 (`(전 Product 공통)` 기본값 + 각 Product) + textarea + 저장 + 초기화. 저장 시 `PUT /api/auth/me/system-prompt`.
     - 프로필 탭에서 product 선택을 바꾸면 해당 product scope 의 현재 prompt 를 다시 불러온다.

  H. 대화/Agent 연결
     - `/api/new_conversation` 과 `/api/fork_conversation` 은 생성/복제 시 `AgentCoreConversations.product_id` 에 값을 기록. 기본값은 (body.product_id || account.default_product_id || global default product).
     - `/api/ask` 는 conversation.product_id 를 조회해 `product_id` + `allowed_schemas` + `role_id` + `account_id` 를 `run_agent` 에 넘긴다.
     - `run_agent` 는 `allowed_schemas` 를 tools 전역에 set/clear 하고, `compose_system_prompt` 결과로 system message 를 만든 뒤 기존 흐름대로 진행.

- 검증 계획:
  1. `python3 -m py_compile` 로 agent_core.py / app.py / tools.py 문법 확인.
  2. 컨테이너 재빌드 (`make web`, `make agent`) 후 bootstrap_admin 로그인 → `/api/admin/products` GET → KR seed 확인 → `/api/admin/products/{kr_id}/databases` GET → `dbgame,dblog,dbauth` 3건 확인.
  3. `PUT /api/admin/system-prompts` 로 Product scope prompt 생성 → Role scope prompt 생성 → 본인 account scope prompt 생성.
  4. `/api/ask` 로 질의 → agent 가 받은 system message 에 `## PRODUCT CONTEXT (KR)` / `## ROLE GUIDANCE (admin)` / `## ACCOUNT PREFERENCES` 가 순서대로 주입되었는지 agent 응답의 steps 로그에서 확인.
  5. whitelist 밖 schema (e.g. `mysql.user`) 를 execute_sql 로 호출했을 때 거부되는지 확인.
  6. 브라우저 수동: admin 의 Products 탭 + Roles detail 의 prompt 영역 + 프로필의 프롬프트 탭이 모두 렌더되는지 확인.

- 비-목적 (Out of Scope):
  - Product 별 계정 멤버십 ACL (`WebAccountProducts`). 이번은 모든 계정이 모든 active product 접근 가능한 MVP.
  - Product 별 RBAC override 매트릭스. 현재 permission 체계는 RBAC 만 쓰고, "이 Role 이 이 Product 에서만 유효" 같은 scoping 은 별 과제로 둠.
  - `_tool_execute_sql` SQL parsing 정확도: quoted identifier 가 아닌 서브쿼리 내부 복잡 참조는 표면적 regex 로만 검사. full sqlparse 도입은 후속 과제.

- TASK-0035 (2026-04-21 마감): 사이드바가 `내 대화` / `타 계정 대화 (N)` 섹션으로 분할 노출되고 내 대화는 좌측 primary 컬러 바 + 틴트, 타 계정 대화는 owner 뱃지 강조로 구분된다. 말풍선의 user 메시지도 `is-own-message` / `is-other-message` 로 톤이 분리되며, meta 라벨은 `나 (<username>)` 또는 `<owner_username>` 을 표시한다. `POST /api/fork_conversation` 이 `conversation.create` + `read.own/any` 권한에 맞춰 원본 topic 과 메시지(internal 제외)를 새 대화로 복제하며, 복제본 topic 에는 `[Fork]` 접두사를 붙인다. 헤더 `대화 복사` 버튼은 전체 복제, 말풍선 hover 액션 `여기서 분기` 는 부분 복제(`from_message_id` 지정) 를 수행한다. 검증: `docker compose run --rm -T web python -m py_compile src/app.py` OK, 브라우저 스크립트 `curl -sk ... /api/fork_conversation` 로 전체 복제 6건/부분 복제 3건(source 20260421075518-571abdb6) 모두 HTTP 200 반환, 새 conversation_id 20260421082459-c039abbd / 20260421082523-d9fbb21b 에 topic `[Fork] ...` 접두어와 MetaJson 내 `forked_from_message_id` 저장 확인.

### TASK-0035 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 사이드바 대화 목록에서 자신의 대화인지, 타 계정 대화인지 **한눈에 구분이 안 된다**. 현재는 `conv-item-meta` 마지막에 작은 회색 글자로 `owner_username` 만 표시되어, admin 으로 로그인해 전체 대화를 볼 때 본인 대화가 파묻힌다.
  2. 타 계정 대화는 조회만 가능하고 composer 가 잠겨 있어(`renderComposer` 의 `!isOwnConversation(...)` 분기), **타 계정 대화를 그대로 이어서 질의할 수 없다**. 따라서 "이 대화의 지금까지 맥락을 가져와서 내 대화로 이어서 질문" 하는 경로가 필요하다.
  3. 동일한 요구가 자기 대화 내에서도 발생 — 특정 중간 응답(가설/분기점)에서부터 다른 방향으로 실험해 보고 싶을 때 **현재 대화를 오염시키지 않고** 그 지점까지 복제한 새 대화가 있으면 안전하다.
- 현황/환경 분석 (출발점 근거):
  1. `_list_conversations` ([app.py:1629](../src/app.py#L1629)) 는 `owner_account_id`, `owner_username`, `last_activity_at` 을 모두 반환하지만, 프론트엔드 `renderConversationList` ([static/app.js:588](../src/static/app.js#L588)) 는 단일 리스트로 `owner_username` 만 소극적으로 덧붙인다.
  2. `isOwnConversation` ([static/app.js:319](../src/static/app.js#L319)) 이 `Number(conversation.owner_account_id) === Number(state.user.id)` 기준으로 소유 판정 로직을 이미 갖고 있어, 하이라이트/정렬 로직에서 재사용 가능하다.
  3. `renderMessages` ([static/app.js:1153](../src/static/app.js#L1153)) 는 role 만으로 "사용자 / Assistant" 를 표시한다. `user` 메시지는 현재 대화 소유자가 보낸 것이므로, 대화 소유자가 현재 계정이면 "나 (<username>)", 아니면 `owner_username` 으로 라벨링하면 정보량이 크게 올라간다.
  4. `/api/new_conversation` ([app.py:3171](../src/app.py#L3171)) 는 빈 대화만 만든다. 메시지 복사는 별도 API 가 필요하다.
  5. `AgentMemoryMessages` 는 `(ConversationId, Role, Content, CreatedAt, MetaJson)` 스키마이고, `memory.py` 의 insert 문 ([memory.py:867](../../feature-0002-agent-core/src/modules/memory.py#L867)) 은 CreatedAt 을 DEFAULT CURRENT_TIMESTAMP 에 의존한다. fork 시에는 **원본 CreatedAt 을 보존** 해야 원본과 동일한 시계열로 재생된다 → 별도 insert 쿼리(CreatedAt 포함) 를 API 레벨에서 직접 발행.
  6. `_get_history` ([app.py:2343](../src/app.py#L2343)) 와 `_is_internal_message` 는 internal 플래그가 붙은 시스템 메시지를 표시에서 제거한다. fork 에서는 **표시되는 메시지만** 복사해 새 대화를 "깨끗하게" 시작할 수 있도록 한다.
- 설계 (Plan-Review-Execute, 위험도: Minor — UI 레이어 추가 + 신규 API 1개, 기존 스키마/권한 체계 변경 없음):
  A. 사이드바 구분/정렬 (프론트엔드)
     - `renderConversationList` 를 **own-first 그룹핑** 으로 재구성: `state.conversations` 을 `isOwnConversation(item)` 으로 파티션 → `own` 블록 + `others` 블록. 각 블록은 기존 ORDER(`updated_at DESC`) 를 그대로 따른다.
     - 각 블록 앞에 `.conv-group-title` (섹션 헤더) 을 삽입: "내 대화" / "타 계정 대화 (<count>)". 타 계정 블록은 item 이 1건 이상일 때만 노출.
     - `conv-item` 에 `is-own` / `is-other` 클래스 추가. 활성 하이라이트(`is-active`) 와 독립적.
     - CSS (`styles.css`):
       * `.conv-item.is-own` → `border-left: 3px solid var(--primary)`(내 대화 좌측 컬러 바) + 약한 `background` 틴트.
       * `.conv-item.is-other` → `border-left: 3px solid transparent` + `.conv-item-meta` 의 owner_username 을 bold/색 강조(`var(--text-2)`) 처리.
       * `.conv-item.is-own .conv-owner` 는 "나" 로 라벨, `.conv-item.is-other .conv-owner` 는 `owner_username` 을 그대로 노출.
       * `.conv-group-title` → 11px, uppercase, letter-spacing 0.06em, muted 톤.
  B. 말풍선 소유자 라벨/하이라이트 (프론트엔드)
     - `renderMessages` 에서 현재 대화를 `currentConversation()` 로 잡아 `isOwn = isOwnConversation(conversation)`, `ownerLabel = conversation.owner_username || "사용자"` 를 계산.
     - user 메시지 meta 라인: `isOwn ? "나 (" + state.user.username + ")" : ownerLabel` → 기존 "사용자" 라벨 교체.
     - user 메시지 row 에 `is-own-message` 또는 `is-other-message` 클래스 부여.
     - CSS: `is-own-message .message-bubble` → 기존 primary 톤 유지(현 상태), `is-other-message .message-bubble` → 중성 grey 톤(`--bg`, border `var(--border)`) 으로 색상 분리해 "내가 보낸 글" 과 혼동 방지. assistant 말풍선은 계정과 무관하므로 변경 없음.
  C. 대화 fork API (백엔드)
     - 신규 엔드포인트 `POST /api/fork_conversation` ([app.py:3171](../src/app.py#L3171) 근처, `new_conversation` 바로 아래 배치):
       ```
       request body: {
         source_conversation_id: str (required),
         from_message_id: int | null   // 이 ID 까지(포함) 복사. null/누락 시 전체 복사.
       }
       response: { conversation_id: str, copied: int, source: str }
       ```
     - 권한:
       * 현재 계정이 `conversation.create` 를 가져야 한다 (not owned).
       * 원본 대화에 대해 `_account_can_access_conversation(conn, account, source, "conversation.read.own", "conversation.read.any")` 가 True 이어야 한다.
     - 절차:
       1. 원본 존재/권한 검증. 실패 시 404/403.
       2. `agent_core.create_new_conversation(conv_file=_account_conv_file(id))` 로 새 cid 발급 + `_assign_conversation_owner(conn, cid, account_id, force=True)`.
       3. topic 복사: 원본 topic 조회 후 `_set_conversation_topic(conn, cid, "[Fork] " + original_topic)`. (기존 `rename_conversation_title` 의 topic 쓰기 경로를 재사용한다.)
       4. `AgentMemoryMessages` 에서 `ConversationId = source` AND (`from_message_id` 있으면 `Id <= from_message_id`) 조건으로 Role/Content/CreatedAt/MetaJson 을 ORDER BY Id ASC 로 가져와, 새 cid 로 **원본 CreatedAt 을 그대로 유지한 채** 재삽입. `_is_internal_message` 가 True 인 row 는 skip (internal=True 인 시스템 메모는 fork 대상 아님).
       5. MetaJson 에 `forked_from_conversation_id`, `forked_from_message_id`(또는 null) 를 추가해 추적성 보존.
       6. `_set_account_current_conversation(conn, account_id, cid)` 로 새 대화를 활성화 후 JSON 응답.
     - 실패/롤백: 중간 예외 시 이미 생성된 새 대화는 `delete_conversation_records(conn, cid)` 로 정리 후 500.
  D. 대화 fork UI (프론트엔드)
     - 헤더 버튼: `index.html` `chat-header-tools` 에 `<button id="forkConversationBtn">대화 복사</button>` 추가. 활성 대화가 있고 `conversation.create` 권한이 있으면 visible, 없으면 `is-access-blocked`.
     - 말풍선 단위 fork: `renderMessages` 에서 각 message row 에 `message-actions` 액션 바를 생성하고 `여기서 새 대화로 분기` 버튼을 둔다. 호버 시 opacity 가 올라오는 pattern (기존 hover 스타일 참고). click → `forkConversation(from_message_id=message.id)`.
     - 공통 함수:
       ```js
       async function forkConversation({ fromMessageId = null } = {}) {
         const src = state.activeConversationId;
         if (!src) return;
         if (!can("conversation.create")) { showPermissionDeniedToast("conversation.create"); return; }
         const payload = await apiFetch("/api/fork_conversation", {
           method: "POST",
           body: JSON.stringify({ source_conversation_id: src, from_message_id: fromMessageId }),
         });
         showToast(fromMessageId ? "선택한 지점까지 새 대화로 복제했습니다." : "대화를 새 대화로 복제했습니다.");
         await refreshWorkspace(payload.conversation_id || "");
       }
       ```
     - 비-own 대화에서도 `conversation.create` 만 있으면 fork 가 허용되므로, 기존 "읽기 전용 대화" 문구 아래에 "대화 복사" 버튼을 강조 노출한다 (read-only UX 의 탈출구 제공).
- 테스트/검증:
  1. `python3 -m py_compile repo/unit/feature-0003-agent-web-ui/src/app.py` 로 문법/import 점검.
  2. 브라우저 수동 검증: 로그인 → 내 대화/타 계정 대화가 섹션 분리 + 하이라이트로 구분되는지 확인. admin 계정에서 본인 대화가 상단으로 정렬되는지 확인.
  3. fork 수동 검증:
     - 자기 대화에서 "대화 복사" → 새 대화 cid 반환 + 사이드바 "내 대화" 블록에 추가됨.
     - 타 계정 대화에서 특정 assistant 말풍선의 "여기서 분기" → 해당 말풍선 id 까지 복사된 새 대화가 나에게 생성됨.
     - 새 대화의 topic 이 `[Fork] ...` 로 표시되는지 확인.
     - 새 대화에서 composer 가 열려 추가 ask 가 가능한지 확인.
  4. 권한 분기 검증: `conversation.create` 가 없는 viewer 계정에서 fork 버튼이 `is-access-blocked` 로 표시되고 클릭 시 토스트만 뜨는지.
- 비-목적(Out of Scope):
  - 메시지 meta 의 steps/csv/sql 아티팩트 복제. (MetaJson 은 그대로 복제되지만, `/shared/...` 에 있는 CSV 파일은 그대로 원본 경로를 참조한다. 파일 접근은 `conversation.file.read.*` 권한과 `_account_can_access_conversation` 으로 여전히 통제되므로 fork 소유자가 원본 파일에 대한 접근 권한을 갖고 있지 않으면 링크 클릭 시 403 을 받는다. 이 범위는 현 작업에서 변경하지 않는다.)
  - 실시간 동기화(원본 대화가 뒤에 더 쌓여도 fork 된 대화에는 반영되지 않음 — snapshot 시맨틱 유지).
  - agent-core 내부 `ConversationState` 마이그레이션(대화별 run state 는 새 대화에서 깨끗하게 시작).

### TASK-0034 상세 설계
- 문제/목적 (사용자 요청 2026-04-21):
  - 현재 구성된 assistant (RBAC/SQL agent/Insight/Local+API LLM) 가 실제로 **복잡한 도메인 질의** 에서 얼마나 정확한 답을 내놓는지 체계적으로 확인하고, 이후 개선 이슈의 근거로 쓰고자 함.
  - 정확한 답변을 위해 **한 대화 안에서 최대 20회 까지 질의를 이어간다** (= 사용자 역할을 하는 테스트 러너가 추가 질문/구체화 요청으로 agent 를 보조) 는 가정으로 진행.
  - 구성: **local LLM 5 대화 (성능 한계 → 직렬)** + **상용 API 5 대화 (모델 = gpt-5 mini → 이 저장소의 `gpt-5.4-mini`, 병렬 가능)**.
  - API 키는 `.env` 의 `OPENAI_API_KEY` 재사용 승인됨.
  - **실제 DB 데이터와 정확히 일치하는지 별도 검증**: 같은 질문을 사람이 직접 MySQL 쿼리로 풀어서 그 결과를 assistant 의 최종 답변과 1:1 대조한다.
  - 기본 예시 3 개는 주어졌고, 더 복잡한 변주도 가능하면 포함한다.
- 기준 예시 질문 (사용자 제공):
  1. dblog 에서 **영웅스킬 업그레이드의 가장 대중적인 테크트리** 를 영웅별 및 테크트리별로 집계.
  2. dblog 에서 **전투시작 관련 테이블 통계** — 전투시작 구성 영웅 중 가장 많이 사용된 50종의 참여 횟수/채택률.
  3. 한정가챠 — **유저가 특정 상품일 때만 시도하고 나머지는 만료** 시키는 패턴을 근거로, "가치가 높은 상품" 이 무엇인지 집계 (이진 플래그 기반).
- 원인/환경 분석 (본 작업의 출발점):
  1. `/api/ask` 가 commercial 모델 사용 시 클라이언트 측에서 **PBKDF2-HMAC-SHA256(100000 iter, 32byte) + AES-GCM, `v1:<salt_b64>:<iv_b64>:<ct_b64>`** 포맷으로 암호화된 API key 를 요구 ([app.py:1003](../src/app.py#L1003) `_decrypt_api_key`). 즉 브라우저 없이 curl 로만 commercial 테스트를 하려면 동일 포맷의 암호 헬퍼가 별도로 필요하다.
  2. Local LLM 경로는 `model ∈ {"auto","edge","core","code"}` 이고 API key 를 요구하지 않는다 ([model_catalog.py](../../feature-0002-agent-core/src/modules/model_catalog.py)). Local LLM 은 `local-llm-gateway:8080/v1` 단일 프로세스라 병렬 대화가 큐 경합으로 느려지므로 **직렬** 지시가 적절하다.
  3. 기본 인증은 HttpOnly 세션 쿠키이므로 `/api/auth/login` → 쿠키 jar 저장 → `/api/ask` 재사용 흐름을 그대로 쓸 수 있다. `bootstrap_admin` 은 RoleId=3 (admin) 으로 `conversation.ask`/`conversation.create`/`conversation.read.any`/`conversation.file.read.any` 등 필요한 권한을 모두 보유(확인됨 `SELECT ... webrolepermissions WHERE RoleId=3 AND Code LIKE 'conversation%'`).
  4. DB 스키마 사전 조사:
     - `dblog.battlebegin` (533k rows). `MyHeroInfo` 컬럼이 JSON 배열 `[{Index, Level, Star, Skill:[5 levels], Equip..., Transcend...}, ...]` — **질문 1 (영웅스킬 테크트리) + 질문 2 (영웅 사용 빈도) 의 공통 자원**.
     - `dblog.battleend` (555k rows). `Win/Star/PlayTime` 포함 — BattleType 별 성과 지표 확장 가능.
     - `dblog.equipoptionupgrade` (8.7k rows). `OptionIndex, OptionStep` — "장비 옵션 업그레이드 테크트리" 로 해석할 여지 있으나 질문 1 의 본질은 MyHeroInfo.Skill[] 분포.
     - `dblog.equipgacharecord` (165 rows). `HighGachaCategory` 는 comma-separated 카테고리(`"25,71,13,2"`) 와 클래스명(`"NewHero"`, `"Wizard"` 등) 이 섞여 저장되어 있음. 행 수가 매우 적지만 질문 3 이 요구하는 "이진 플래그 기반 한정가챠 가치 판별" 의 뚜렷한 resource — assistant 의 희소 데이터 해석력 테스트에 오히려 적합.
     - 추가 대형 테이블: `dblog.currency` (2.84M), `dblog.equipget` (1.8M), `dblog.equipremove` (1.6M), `dblog.gold` (899k), `dblog.battlebeginaffixv2` (562k), `dblog.battleendaffixv2` (511k), `dblog.gemv2` (308k). 이들은 추가 복잡 질의(재화 유출입/장비 수명주기/전투 affix 영향) 에 쓸 수 있음.
- 5 개 복잡 질문 설계 (local LLM 5 대화 × 상용 API 5 대화 공통, 동일 질문 쌍으로 두 경로를 비교):
  1. **Q1 영웅스킬 업그레이드 테크트리 랭킹** — dblog 기준, 영웅(Index)별로 [Skill1, Skill2, Skill3, Skill4, Skill5] 레벨 조합(= "테크트리") 의 등장 빈도를 집계해 영웅별 상위 5 테크트리(+테크트리별 전체 상위 20) 를 리스트업. 데이터 소스: `battlebegin.MyHeroInfo` 배열을 JSON 풀어서 집계. (battlebegin 한 row 당 여러 hero 가 들어 있음에 주의 — assistant 가 스스로 풀어내는지 관찰 포인트.)
  2. **Q2 전투시작 영웅 사용 Top 50** — `battlebegin.MyHeroInfo` 를 펼쳐 hero Index 별 등장 수(= 참여 횟수) 와 채택률(= 등장 수 / 전체 battlebegin 행 수) 을 계산. 전체 영웅 종 수와 rank, 채택률 소수점 2자리 보고.
  3. **Q3 한정가챠 가치 품목 판별** — `equipgacharecord` 에서 (a) 유저가 실제로 **가챠를 진행한 행위** 와 (b) 만료/미진행 으로 보이는 **카테고리 노출 기록** 을 구분하고, 진행 행위가 많았던 카테고리(또는 코드) ↔ 일반 노출뿐이었던 카테고리 간 차이를 도출. 카테고리가 comma-separated 이므로 "이진 플래그" 해석을 assistant 가 잡아내는지가 관건.
  4. **Q4 BattleType 별 승률 × 평균 플레이타임** — `battlebegin` ↔ `battleend` 를 (AccountId, Time window) 로 매칭하여 BattleType 별 전투 수 / 승률 (`SUM(Win) / COUNT(*)`) / 평균 PlayTime / 평균 Star 를 도출, 상위 10 BattleType 랭킹. JOIN 정의가 애매하므로 assistant 의 스키마 탐색/LIMIT 프로빙 능력 관찰.
  5. **Q5 영웅 레벨/스타 분포로 본 "육성 된 메타 영웅" Top 20** — 각 영웅 Index 에 대해, 전투에 투입된 **최고 Level**, **평균 Level**, **Star ≥ 2 비율**, **총 등장 수** 를 계산해 "많이 나오면서 평균 레벨/스타도 높은" 영웅 Top 20. rank 산식은 assistant 가 합리적으로 제시하게 두고 검증 시 동일 산식을 사람 쿼리로 재현해 비교.
  - 모든 5 질문은 두 모델 경로에서 동일하게 사용 → 같은 질문에 대한 local vs API 응답 품질 비교 가능.
- 대화 프로토콜 (1 질문 → 1 "대화" 단위, 최대 20 turn):
  - **turn 1**: 주 질문을 그대로 던진다.
  - **turn 2~N**: assistant 가 부분 답/진행 중/스키마 탐색 중이면 러너가 보조 프롬프트 ("스키마를 먼저 확인해주세요", "JSON 안의 Skill 배열을 풀어서 집계해주세요", "가능하면 영웅별 Top 5 로 잘라주세요", "각 수치에 대해 어떤 쿼리를 썼는지 같이 보여주세요") 를 순차 제공.
  - 종료 조건 (다음 중 하나):
    a. assistant 가 명확한 최종 답 (표/CSV + 요약) 을 내고 러너가 "이제 충분합니다" 판단.
    b. 20 turn 도달.
    c. `/api/ask` 가 인증 만료/서버 500 반환 → turn 간격 유지를 위해 재로그인 1 회 시도 후 실패하면 종료.
  - 대화 1 건당 메타: `{model, conversation_id, turns: [{user, assistant_answer, sql_list, csv_preview, elapsed_s}], final_verdict}`.
- 테스트 하니스 설계:
  - 위치: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runner.py` (신규, 테스트 전용). 실제 배포 코드가 아님.
  - 의존: `httpx`, `cryptography` (PBKDF2 + AESGCM). 두 라이브러리는 repo web 이미지에 이미 포함됨 — host 의 `python3 -m pip` 대신 `docker compose run --rm -T web python` 으로 실행해도 되고, host 에 이미 설치되어 있으면 host 에서 바로 실행 가능 (둘 다 시도 가능하도록 설계).
  - 주요 함수:
    ```python
    def encrypt_api_key(plain: str, passphrase: str) -> str:
        # salt(16B rand) + iv(12B rand) + PBKDF2HMAC-SHA256(iter=100_000, len=32)
        # → AESGCM encrypt → "v1:<b64 salt>:<b64 iv>:<b64 ct>"
    def login(client, username, password) -> None                 # POST /api/auth/login
    def new_conversation(client, model) -> dict                   # POST /api/new_conversation
    def ask(client, message, model, conversation_id,
            api_key_cipher=None, api_key_passphrase=None,
            timeout=600) -> dict                                   # POST /api/ask
    def run_conversation(question, model, api_key, max_turns=20) -> dict
    ```
  - 상용 API 경로: `ask()` 호출 시 매 턴마다 암호화된 cipher + 새 passphrase 같이 전송 (서버 측 복호화 → upstream OpenAI 호출).
  - Local LLM 경로: `api_key_cipher=None`, `model ∈ {"core","edge","auto"}`. 본 테스트는 `core` 고정 (agent 기본 권장).
  - 실행 전략:
    - 상용 5 대화: `asyncio.gather` 5 병렬 (`gpt-5.4-mini`).
    - Local 5 대화: `for` 루프 직렬 (`core`).
  - 결과 저장: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runs/{local|api}-{qid}.json` — 각 대화의 전체 turn 로그 + 최종 답변 + 모든 SQL + CSV preview path 포함.
- DB 대조 검증 설계:
  - 질문별 **사람 정답 쿼리** 를 별도 파일 `tests/task0034_truth.sql` 에 기록 (Q1~Q5). 예:
    ```sql
    -- Q2 (참고): hero 사용 Top 50
    SELECT h.hero_index, COUNT(*) AS appearances,
           ROUND(COUNT(*) / (SELECT COUNT(*) FROM dblog.battlebegin WHERE MyHeroInfo IS NOT NULL) * 100, 2) AS adoption_pct
    FROM dblog.battlebegin b,
         JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero_index INT PATH '$.Index')) h
    WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
    GROUP BY h.hero_index
    ORDER BY appearances DESC
    LIMIT 50;
    ```
  - 검증 스크립트 `tests/task0034_verify.py`: assistant 가 낸 최종 Top-N 리스트 vs truth 쿼리 결과를 **(key, count) tuple set 비교 + rank 순서 비교** 로 확인. 일치율 % 와 불일치 항목 diff 출력.
  - 모호한 질문(Q3, Q5) 은 "논리적으로 맞는 범위" 를 기준으로 판정 기록 (완전 일치 가능 여부를 리포트에 명시).
- 결과 리포트:
  - `tests/TASK-0034-REPORT.md` — 질문별로 (a) assistant 최종 답변 요약, (b) 사람 truth 결과, (c) 일치/불일치, (d) 몇 턴 만에 수렴, (e) 관찰된 개선 포인트.
  - LEARNINGS 는 (**LRN-20260421-0010**) "복잡 QA 에서 agent 가 어디에서 막히거나 무한 재시도하는지, 어떤 휴리스틱을 추가하면 턴 수를 줄일 수 있는지" 한 줄 패턴으로 정리.
- 범위 제한:
  - 프로덕션 UI/백엔드 코드 변경 **금지**. 오직 테스트 하니스 신규 파일 추가 + 결과 문서만.
  - 결과 저장 CSV 원본 (agent 가 `/data/artifacts` 에 남기는 실제 파일) 은 repo 에 체크인하지 않음 — 로그 JSON 의 `preview` 10 행만 커밋.
  - `.env` 의 실제 API key 는 **절대 로그에 남기지 않는다**. 러너가 키를 메모리에 로드해서 암호화·전송 후 즉시 해제.
  - 본 테스트 실행 중 agent 가 만든 대화/메타데이터(webaccounts/conversations) 는 정리하지 않고 남겨 둠 — 사용자가 이후 UI 로 참고 가능.
- 검증 기준 (본 TASK 자체의 완료 조건):
  1. local 5 + API 5 총 10 대화가 실제로 실행되어 JSON 로그로 남았다.
  2. 각 대화의 turn 수 / 최종 답변 / SQL 목록 / 경과 시간이 로그에서 읽힌다.
  3. 5 질문 각각에 대해 DB truth 쿼리를 사람이 돌려본 결과와 assistant 답변을 비교한 diff 가 REPORT.md 에 기록되었다.
  4. LEARNINGS.md 에 이번 실험에서 발견된 구조적 개선점(LRN 항목 신규) 이 추가되었다.
  5. 커밋/푸시까지 완료.

### TASK-0033 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 말풍선 안의 `실행 단계 및 쿼리 결과 보기` 를 펼치면 **바깥 채팅 로그(`.messages`) 스크롤 + 말풍선 상세 본문(`.message-details-body`) 스크롤** 두 개가 중첩되어, 사용자가 대화 전체를 마우스 휠로 훑을 때 경계에서 "턱턱" 끊기는 느낌이 난다.
  - 사용자 요청: **바깥 스크롤(= 말풍선 body cap)은 최대한 나타나지 않도록** 본문을 확장해달라.
  - 결과셋의 행/열이 많을 때 (특히 열이 10개 이상) 어느 행/열을 보고 있는지 **위치 파악이 어렵다**. 기본적으로 RowCount(행 번호) 컬럼이 있어야 하고, 1행(헤더)/1열(번호)은 스크롤해도 **틀 고정(freeze)** 되어야 한다.
- 원인:
  1. [styles.css:849-859](../src/static/styles.css#L849-L859) `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px; }` — TASK-0030 에서 말풍선 폭/스크롤 격리 목적으로 넣었지만, 내부의 `.sql-block`/`.result-table-wrap` 가 이미 각자 cap 을 가지므로 바깥 body cap 은 **중복 방어**. 중복된 cap 때문에 같은 콘텐츠에 대해 스크롤 컨테이너가 2개 생기고, 마우스 휠이 경계를 넘을 때마다 어느 컨테이너가 휠을 소비할지 바뀌어 "턱턱" 멈춤이 발생.
  2. [styles.css:913-920](../src/static/styles.css#L913-L920) `.result-table-wrap { ...; overscroll-behavior: contain; max-height: 320px; }` + [styles.css:907-909](../src/static/styles.css#L907-L909) `.sql-block { ...; overscroll-behavior: contain; max-height: 240px; }` — `overscroll-behavior: contain` 은 자식이 경계에 도달해도 휠을 부모로 **전파하지 않는다**. 그래서 테이블/SQL 내부 스크롤이 바닥/천장에 닿으면 `.messages` 로 올라가지 못하고 그대로 멈춤 — 이것도 "턱턱" 느낌의 큰 원인.
  3. [app.js:734-781](../src/static/app.js#L734-L781) `buildResultTable()` — 데이터 컬럼만 그대로 th/td 로 렌더. RowCount 컬럼 없음. thead th / 첫 컬럼 td 모두 `position: static` 이라 내부 스크롤 시 헤더/첫 열이 함께 밀려 보이지 않게 됨.
  4. [app.js:801-825](../src/static/app.js#L801-L825) `loadFullCsvIntoTable()` — 전체 데이터 로드 시에도 `header.forEach` / `body.forEach` 만 사용, RowCount 를 따로 추가하지 않음.
- 목표:
  1. 말풍선 상세 본문(`.message-details-body`) 의 수직 스크롤 컨테이너를 **제거** — 본문이 콘텐츠 높이만큼 자연스럽게 자라고, 전역 세로 스크롤은 채팅 로그(`.messages`) 하나로 통일. 같은 말풍선 안에 스크롤바 2개가 동시에 뜨는 상황을 근본 제거.
  2. 결과 테이블/SQL 블록은 여전히 **자체 내부 스크롤**을 가지지만, 내부가 경계에 닿으면 `.messages` 로 휠이 **전파**되어 끊김 없이 상하 흐름이 이어져야 한다.
  3. 모든 결과 테이블에 **RowCount 컬럼**(첫 컬럼 `#`) 이 항상 포함되어, 스크롤 중에도 몇 번째 행인지 바로 알 수 있다.
  4. 결과 테이블의 **첫 행(헤더) + 첫 열(#)** 은 내부 스크롤 동안 고정되어 보인다(Excel 의 `Freeze first row + first column` 과 동일한 개념).
  5. "전체 데이터 보기" 로 CSV 전체를 로드해도 동일하게 RowCount + freeze 가 유지된다.
- 접근:
  1. **`.message-details-body` 단일화** — `max-height`, `overflow`, `overscroll-behavior`, `padding-right` 제거. 말풍선 본문은 자연스럽게 자라고, 채팅 로그(`.messages`) 가 유일한 세로 스크롤 컨테이너가 된다. TASK-0030 의 scroll anchor(summary 클릭 시 `messageLogEl.scrollTop` 보정) 은 그대로 동작 — 애초에 `messageLogEl` 기준으로 측정하므로 inner cap 유무와 무관.
  2. **내부 컨테이너 휠 전파 허용** — `.result-table-wrap`, `.sql-block` 의 `overscroll-behavior: contain` 제거. 스크롤 자체는 남기되 경계에서 부모(.messages)로 휠이 넘어가게 한다. 내부 max-height 은 조금 넉넉히 — `.result-table-wrap { max-height: min(60vh, 460px) }`, `.sql-block { max-height: min(40vh, 320px) }` 로 상향(사용자의 "최대한 바깥 스크롤이 나타나지 않도록 확장" 요청 반영).
  3. **`buildResultTable()` 에 RowCount 삽입** — thead 에 `<th class="col-rownum">#</th>` prepend, tbody 의 각 tr 에 `<td class="col-rownum">{i+1}</td>` prepend. 데이터 컬럼 카운트는 그대로 `columns.length` 로 유지(meta 의 `N열` 문구 영향 없음).
  4. **sticky freeze CSS**:
     ```css
     .result-table { border-collapse: separate; border-spacing: 0; }
     .result-table thead th {
       position: sticky; top: 0; z-index: 2;
       background: var(--bg);
       box-shadow: inset 0 -1px 0 var(--border);
     }
     .result-table th.col-rownum,
     .result-table td.col-rownum {
       position: sticky; left: 0; z-index: 1;
       background: var(--bg);
       color: var(--text-muted);
       font-variant-numeric: tabular-nums;
       text-align: right;
       min-width: 40px;
       width: 40px;
       box-shadow: inset -1px 0 0 var(--border);
     }
     .result-table thead th.col-rownum { z-index: 3; }  /* corner: 두 축 모두 최상위 */
     ```
     `border-collapse: separate` 는 sticky 셀에 border 가 제대로 그려지도록 필요 — box-shadow 로 border 대체.
  5. **`loadFullCsvIntoTable()` 동일 패턴 적용** — thead 재구성 시 `#` 먼저, tbody 재구성 시 각 tr 에 `i+1` 먼저.
  6. 기존 `result-table th:last-child, td:last-child { border-right: none }` 는 유지(마지막 데이터 컬럼의 우측 border 제거). sticky 코너가 배경색과 일치해 content 가 뒤쪽으로 비치지 않도록 `background: var(--bg)` 확인.
- 범위 제한:
  - backend API / `preview_table` 응답 스키마 변경 없음. RowCount 는 순수 클라이언트 가상 컬럼.
  - Navigator(`sql-navigator`) 구조/키보드 로직 변경 없음.
  - 말풍선 폭 정책(TASK-0030) 변경 없음.
  - SQL 블록 구조(pre tag) 변경 없음 — 기존 `formatSqlForDisplay()` / pre-wrap 유지.
- 검증 기준:
  1. 쿼리 결과 ≥ 20행을 포함한 말풍선을 펼쳤을 때 `.message-details-body` 에 scrollbar 가 나타나지 않는다(`overflow` 제거 확인).
  2. 결과 테이블 영역에서 세로 스크롤 시 헤더 row 가 상단에 고정되어 보인다 (`getComputedStyle(thead th).position === 'sticky'`).
  3. 가로 스크롤 시 `#` 컬럼이 좌측에 고정되어 보인다 (`getComputedStyle(td.col-rownum).position === 'sticky'`).
  4. 결과 테이블 내부에서 세로로 스크롤하다 바닥/천장에 닿으면 `.messages` 로 휠이 전파되어 채팅 전체 스크롤이 이어진다(overscroll-behavior 제거 효과).
  5. "전체 데이터 보기" 클릭 후에도 #/sticky 동작 유지.
  6. 단일 말풍선 내부에 세로 스크롤바는 최대 1개(= 결과 테이블)만 동시 존재. `.message-details-body` / `.sql-block` (SQL 이 짧을 때) 에는 스크롤바 없음.
  7. 브라우저 자동화로 위 2/3/6 을 `eval` 로 확인 + 스크린샷 캡처.

### TASK-0032 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 작업 화면에서 사용자가 특정 동작(대화 생성/제목 변경/삭제/중단/즉시답변/요청 전송)을 시도했을 때 권한이 없으면 버튼이 **아예 숨겨지거나 조용히 무시되어** 사용자는 "어떤 권한"이 필요한지 알 수 없다. 결과적으로 관리자에게 "그냥 권한 다 줘 주세요" 같은 불필요·과도한 요청이 반복된다.
  - Profile > 계정 탭의 권한 pill 에 마우스를 올리면 툴팁에 **영문 권한 id 만 노출**([app.js:387](../src/static/app.js#L387) `item.title = code`)되어, `conversation.rename.own` 같은 코드를 일반 사용자가 해석할 수 없다.
  - 원인:
    1. [app.js:340-393](../src/static/app.js#L340-L393) `buildPermissionPills()` — `item.title = code` 한 줄. 서술 맵 부재.
    2. [app.js:1102-1105](../src/static/app.js#L1102-L1105) `renderComposer()` 에서 cancel/finalize/rename/delete 버튼을 `classList.toggle("hidden", !canX)` 로 처리 — 권한이 없으면 버튼 자체가 사라져 "이 동작이 있다"는 정보조차 사라짐.
    3. [app.js:1250](../src/static/app.js#L1250), [app.js:1258](../src/static/app.js#L1258), [app.js:1272](../src/static/app.js#L1272), [app.js:1304](../src/static/app.js#L1304), [app.js:1313](../src/static/app.js#L1313), [app.js:1323](../src/static/app.js#L1323) — 각 action 함수가 `if (!canX(...)) return;` 로 **조용히** 리턴. 사용자 피드백 없음.
    4. [app.js:548](../src/static/app.js#L548), [app.js:1088](../src/static/app.js#L1088) `renderAccessNotice()` / `renderComposer()` 안내 문구가 "대화 요청 실행 권한이 없습니다" 까지만 말하고 **어떤 permission code 를 요청해야 하는지 명시하지 않는다**.
- 목표:
  1. Profile > 계정 권한 pill hover 툴팁이 "이 권한이 실제로 어떤 동작을 허용하는지" 한국어 서술 문장 + 권한 코드를 모두 보여준다.
  2. 사용자가 차단된 동작을 시도했을 때(버튼 클릭 / 전송 / 단축키), **필요 권한 이름 + 관리자 요청 문구** 가 포함된 토스트가 즉시 노출된다.
  3. 버튼 가림 정책 변경: context 상 의미있는 상태(대화 선택됨 / 처리 중)에서는 **권한이 없어도 버튼을 유지**하되 `aria-disabled="true"` + 희미한 스타일로 "존재는 하지만 현재 계정으로는 실행 불가"임을 암시. 툴팁에도 필요 권한을 명시.
  4. 조회 전용 / 복구 가능 상태 안내 문구(`accessNoticeEl`, `composerHintEl`)에도 필요한 권한 코드를 명시.
  5. 기존에 자연스레 숨겨야 할 경우(대화 미선택 상태의 제목 변경 버튼 등)는 그대로 숨김 유지 — context 상 의미가 없기 때문.
- 접근:
  1. **권한 서술 맵 추가 ([app.js:97](../src/static/app.js#L97) 부근)**:
     ```js
     const PERMISSION_DESCRIPTIONS = {
       "console.access": "관리 콘솔에 접속할 수 있는 권한입니다.",
       "console.manage": "관리 콘솔에서 계정/역할/권한을 저장 커밋할 수 있는 권한입니다.",
       "account.read": "계정 목록과 상세 정보를 조회할 수 있는 권한입니다.",
       // ... 33개 모두 서술 ...
       "conversation.rename.own": "내가 소유한 대화의 제목을 변경할 수 있는 권한입니다.",
       "conversation.rename.any": "모든 사용자의 대화 제목을 변경할 수 있는 권한입니다.",
       // ...
     };
     function describePermission(code = "") {
       return PERMISSION_DESCRIPTIONS[code] || "권한 설명이 등록되어 있지 않습니다.";
     }
     ```
  2. **필요 권한 반환 헬퍼**:
     ```js
     // 현재 대화에서 action 을 실행하기 위해 필요한 "대안 권한 코드들"을 반환.
     // 예: conversation.rename → ["conversation.rename.any"] 또는 own 대화면 ["conversation.rename.any", "conversation.rename.own"].
     // 이 중 하나라도 granted 면 허용.
     function requiredPermissionsFor(action, conversation = currentConversation()) {
       const own = conversation ? isOwnConversation(conversation) : false;
       switch (action) {
         case "conversation.ask":     return { label: "대화 요청 실행", codes: ["conversation.ask"] };
         case "conversation.create":  return { label: "새 대화 생성", codes: ["conversation.create"] };
         case "conversation.rename":  return { label: "대화 제목 변경", codes: own ? ["conversation.rename.any", "conversation.rename.own"] : ["conversation.rename.any"] };
         case "conversation.delete":  return { label: "대화 삭제",     codes: own ? ["conversation.delete.any", "conversation.delete.own"] : ["conversation.delete.any"] };
         case "conversation.cancel":  return { label: "대화 중단",     codes: own ? ["conversation.cancel.any", "conversation.cancel.own"] : ["conversation.cancel.any"] };
         case "conversation.finalize":return { label: "즉시 답변",     codes: own ? ["conversation.finalize.any","conversation.finalize.own"] : ["conversation.finalize.any"] };
         default:                     return { label: action, codes: [] };
       }
     }
     function hasAnyPermission(codes = []) { return codes.some((c) => can(c)); }
     ```
  3. **차단 토스트 헬퍼**:
     ```js
     function showPermissionDeniedToast(action, conversation = currentConversation()) {
       const req = requiredPermissionsFor(action, conversation);
       if (!req.codes.length) { showToast(`'${req.label}' 을(를) 실행할 수 없습니다.`, true); return; }
       const missing = req.codes.filter((c) => !can(c));
       const primary = missing[0] || req.codes[0];
       const desc = describePermission(primary);
       const alt = req.codes.length > 1 ? `(또는 ${req.codes.slice(1).join(", ")})` : "";
       showToast(`'${req.label}' 권한이 필요합니다. 관리자에게 \`${primary}\`${alt ? " " + alt : ""} 권한 부여를 요청하세요.\n${desc}`, true);
     }
     ```
  4. **buildPermissionPills 툴팁 서술화**:
     ```js
     item.title = `${describePermission(code)}\n(${code})`;
     ```
     (short label 은 pill 의 `textContent`로 유지, 서술 문장은 hover 툴팁에만 노출 — 레이아웃 변경 없음)
  5. **버튼 visibility 정책 전환** ([app.js:1102-1105](../src/static/app.js#L1102-L1105)):
     - `cancelBtn` / `finalizeBtn`: "처리 중" 컨텍스트에서만 의미가 있으므로 `hidden` 토글은 `processing` 여부에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked` 로 표현.
     - `renameConversationBtn` / `deleteConversationBtn`: 대화가 선택되었을 때만 의미가 있으므로 `hidden` 토글은 `state.activeConversationId` 에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked`.
     - 헬퍼:
       ```js
       function markAccessBlocked(btn, action, conversation) {
         const req = requiredPermissionsFor(action, conversation);
         const blocked = !hasAnyPermission(req.codes);
         btn.classList.toggle("is-access-blocked", blocked);
         if (blocked) {
           btn.setAttribute("aria-disabled", "true");
           btn.dataset.blockedAction = action;
           const missing = req.codes.filter((c) => !can(c))[0] || req.codes[0];
           btn.title = `'${req.label}' 권한이 없습니다. 필요 권한: \`${missing}\``;
         } else {
           btn.removeAttribute("aria-disabled");
           delete btn.dataset.blockedAction;
           btn.title = "";
         }
       }
       ```
  6. **클릭 핸들러 보강** ([app.js:1534-1580](../src/static/app.js#L1534-L1580)):
     - 각 핸들러 본문 맨 앞에 `if (btn.getAttribute("aria-disabled") === "true") { showPermissionDeniedToast(action, currentConversation()); return; }` 추가.
     - `createConversation()`, `renameCurrentConversation()`, `deleteConversation()`, `cancelCurrentRun()`, `finalizeCurrentRun()`, `sendPrompt()` 내부의 조용한 `if (!canX) return` 도 `if (!hasAnyPermission(req.codes)) { showPermissionDeniedToast(action); return; }` 패턴으로 교체 — 단축키(Ctrl+Enter) 경로에서도 토스트가 나오도록.
  7. **안내 문구 보강** (`renderAccessNotice()`, `renderComposer()`):
     - `accessNoticeEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 권한을 요청하세요.";`
     - `composerHintEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 요청하세요.";`
     - Profile 의 "사용 가능한 권한이 없습니다" 문구는 그대로 (별도 추가 작업 불필요).
  8. **CSS** (`styles.css`):
     - `.tool-btn.is-access-blocked` + `.tool-btn[aria-disabled="true"]` 에 `opacity: .38; cursor: help; color: var(--text-muted);` 지정 — 기존 `:disabled` 스타일 재사용하되 click 은 계속 통과.
     - `button.is-access-blocked` hover 시 네이티브 `title` 툴팁이 뜨도록 `pointer-events: auto` 유지 (기본값이라 별도 선언 불필요).
- 범위 제한:
  - 백엔드 API 변경 없음. 권한 정의 테이블(WebPermissions) 그대로 사용.
  - admin 콘솔 쪽 UX 는 TASK-0031 이 마무리되었으므로 이번 범위에서 제외.
  - Profile 드로어의 "활성 권한" 섹션 외관은 유지 (그룹핑/카운트 배지 TASK-0027 그대로).
  - "부족한 권한 전체 목록" 같은 별도 UI 섹션은 추가하지 않는다 — 동작 시도 시점에 안내되므로 과설계.
- 검증 기준:
  1. Profile > 계정 탭에서 임의의 권한 pill 에 hover → 툴팁에 한국어 서술 문장 + `(code)` 가 표시된다(단순 `code` 가 아님).
  2. operator 계정(= `conversation.delete.own` 미보유) 로그인 → 본인 대화 선택 시 "삭제" 버튼이 보이고 `aria-disabled="true"` + 희미한 색. 클릭하면 토스트 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요.` 노출.
  3. 동일 계정에서 대화 미선택 상태에서는 "삭제" 버튼이 (권한과 무관하게) 숨김 — context 상 의미 없음.
  4. pending 계정(= `conversation.ask` 미보유) 로그인 → access notice / composer hint 에 `conversation.ask` 권한 코드 명시. 전송 시도 시 토스트 출현.
  5. admin 계정(모든 권한) 로그인 → 버튼 모두 정상 클릭 가능. `aria-disabled` 없음. 툴팁에도 빈 문자열.
  6. Ctrl+Enter 로 빈 권한 상태 전송 시도해도 동일 토스트 확인 (단축키 경로).
  7. 브라우저 자동화로 위 2번/4번을 재현해 스크린샷 or DOM 상태 증빙.

### TASK-0031 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 관리 콘솔에서 계정/권한 목록이나 디테일 편집 항목이 많아지면 화면 아래 있어야 할 버튼(예: 페이지 버튼, 저장/취소/삭제 액션)이 외부 스크롤에 의해 뷰포트 밖으로 밀려 **이용자가 존재 자체를 인지하지 못한다**.
  - 원인:
    1. [styles.css:1378-1383](../src/static/styles.css#L1378-L1383) `.admin-workspace { overflow-y: auto }` — workspace 전체가 단일 스크롤 컨테이너. 디테일 pane 이 커지면 그 높이가 workspace 스크롤을 지배하여 리스트 하단 페이지네이션이 **외부 스크롤 아래로 숨음**.
    2. [styles.css:1509-1516](../src/static/styles.css#L1509-L1516) `.admin-list { max-height: calc(100vh - 320px) }` 는 고정 pixel 계산인데다 외부 workspace 스크롤에 의해 의도치 않게 무력화됨.
    3. [admin.html:113-114](../src/static/admin.html#L113-L114) 페이지네이션(`#accountPagination`)이 `.admin-list` 바깥(동일 `.admin-list-col` 자식)으로 위치해, 리스트 내부 스크롤이 아니라 바깥 workspace 스크롤에 종속됨.
    4. [admin.js:854-855](../src/static/admin.js#L854-L855) `.admin-detail-actions`(저장/취소/삭제 버튼 영역)도 detail pane 내용 맨 아래에 append 될 뿐 위치 고정 처리가 없어 detail 이 길어지면 외부 스크롤로만 접근 가능.
- 목표:
  - 관리 콘솔 2열 레이아웃(리스트 / 디테일) 각 컬럼이 **자체 내부 스크롤**을 가지며, 컬럼 하단의 페이지네이션·일괄 액션·detail 저장 버튼은 **항상 뷰포트 내에 노출**된다.
  - 외부(페이지 전체) 스크롤은 발생하지 않는다. 모든 스크롤은 각 pane / 컬럼 내부로 한정.
  - 하단 commit bar, topbar, sidebar 는 기존대로 고정(이미 grid 로 고정되어 있음 — 그대로 유지).
- 접근:
  1. **`.admin-workspace` 를 스크롤 컨테이너에서 flex 컨테이너로 전환**:
     ```css
     .admin-workspace { overflow: hidden; display: flex; flex-direction: column; padding: 20px 24px 24px; min-height: 0; }
     ```
     (`min-height: 0` 은 부모 grid row 에서 flex children 이 overflow 하지 않게 하는 안전장치)
  2. **`.admin-pane.is-active` 가 workspace 를 수직으로 채우도록**:
     ```css
     .admin-pane { display: none; flex-direction: column; gap: 16px; min-height: 0; flex: 1 1 auto; }
     .admin-pane.is-active { display: flex; }
     ```
  3. **`.admin-pane-head` 는 고정**(shrink 없음):
     ```css
     .admin-pane-head { flex-shrink: 0; }
     ```
  4. **리스트-디테일 컨테이너가 남은 공간을 채우고, 자식 컬럼이 동일 높이를 가지도록**:
     ```css
     .admin-list-detail { flex: 1 1 auto; min-height: 0; align-items: stretch; }
     ```
     (기존 `align-items: start` 는 제거 — start 로는 두 컬럼이 콘텐츠 길이에 따라 다르게 자라므로)
  5. **리스트 컬럼 = 고정 헤더(툴바/리스트-헤드) + 내부 스크롤 본문 + 고정 푸터(페이지네이션/일괄 액션)**:
     ```css
     .admin-list-col { min-height: 0; max-height: 100%; }
     .admin-list-toolbar, .admin-list-head { flex-shrink: 0; }
     .admin-list { flex: 1 1 auto; min-height: 0; max-height: none; overflow-y: auto; }
     .admin-list-pagination, .admin-bulk-actions { flex-shrink: 0; border-top: 1px solid var(--border-subtle); margin-top: 4px; padding-top: 8px; }
     ```
     기존 하드코딩 `max-height: calc(100vh - 320px)` 제거.
  6. **디테일 컬럼 = 내부 스크롤 본문 + 하단 sticky 액션 바**:
     - CSS 만으로 마지막 자식 `.admin-detail-actions` 를 sticky 하게 만들면, 내부 구조 변경 없이 저장/취소/삭제 버튼이 detail pane 하단에 항상 노출된다:
     ```css
     .admin-detail-col { min-height: 0; max-height: 100%; overflow-y: auto; padding-bottom: 0; }
     .admin-detail-actions {
       position: sticky;
       bottom: 0;
       background: var(--surface);
       margin: 0 -22px -18px;   /* detail-col padding(18 22)을 상쇄해 전폭 바 */
       padding: 10px 22px;
       border-top: 1px solid var(--border);
       z-index: 1;
     }
     ```
  7. **대시보드 pane** 은 카드 + pending 미리보기만 있으므로 내부 스크롤이 필요한 경우에만 대비:
     ```css
     .admin-pane[data-admin-pane="dashboard"] { overflow-y: auto; }
     ```
  8. **뷰포트가 좁을 때 보호**: 기존 반응형 쿼리가 있다면 그대로 유지. 모바일(viewport < 960px) 대응은 이번 범위 아님(이용자는 데스크탑에서 사용).
- 범위 제한:
  - JS(admin.js) 변경 불필요. CSS 만으로 해결.
  - admin.html DOM 구조 변경 불필요(페이지네이션·액션 바가 각각 올바른 컬럼의 마지막 자식에 이미 위치).
  - 채팅 쪽, backend 변경 없음.
- 검증 기준:
  1. 브라우저로 `/admin` 열어 계정 탭 진입 → 페이지를 스크롤하지 않고도 페이지네이션 버튼이 리스트 하단에 보인다.
  2. 계정을 선택해 디테일에 많은 권한 그룹을 펼친 상태에서도 리스트 컬럼의 페이지네이션은 그대로 보이며, 디테일 하단 저장/취소 버튼도 sticky 로 노출된다.
  3. 리스트 컬럼에서 스크롤해도 페이지네이션은 리스트 아래에 고정 위치. 디테일 컬럼에서 스크롤해도 액션 바는 하단에 고정.
  4. `document.documentElement.scrollHeight === document.documentElement.clientHeight` 인지 확인(외부 스크롤 없음).
  5. 역할 탭에서도 동일 동작(역할 일괄 액션 바/detail 저장 버튼).
  6. 브라우저 자동화로 위 동작을 재현·수치 검증.

### TASK-0030 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - assistant 답변의 "실행 단계 및 쿼리 결과 보기" `<details>` 블록을 펼칠 경우, 결과셋 구성(쿼리 수/행 수/컬럼 수/SQL 길이)에 따라 말풍선의 높이와 폭이 비결정적으로 커져 **채팅 스크롤 위치가 움직이고**, 사용자가 방금 보던 문장을 놓친다.
  - 원인 1: [styles.css:721-725](../src/static/styles.css#L721-L725) `.message { max-width: 82% }`가 user/assistant 양쪽에 동일 적용되어, assistant 말풍선이 기본적으로 좁고, 내용이 커지면 높이로 비대해진다.
  - 원인 2: [styles.css:838-843](../src/static/styles.css#L838-L843) `.message-details-body`에 max-height/overflow 제약이 없어서 내부 SQL · 테이블 · 긴 `<pre>` 가 수직으로 끝없이 누적된다.
  - 원인 3: [styles.css:894-898](../src/static/styles.css#L894-L898) `.result-table-wrap` 기본형은 `overflow-x: auto`만 있고 수직 cap이 없다 ("is-full-data" 변형만 360px 로 제한). 결과 preview가 많이 잘리지 않은 상태면 높이가 무제한.
  - 원인 4: [styles.css:877-891](../src/static/styles.css#L877-L891) `.sql-block`은 `pre-wrap`이지만 초장문 SQL 은 여전히 화면 높이를 밀어낸다.
  - 원인 5: [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()`는 `<details>` 펼침/접힘 시 스크롤 앵커 로직이 없어, `<summary>` 위치가 뷰포트 내에서 통째로 이동한다.
- 목표:
  1. assistant 말풍선은 기본적으로 **넓은 폭으로 고정**(우측 사용자 질문 영역과 구분할 수 있는 소량 여백만 유지). 펼친 내용의 크기에 따라 말풍선 폭이 흔들리지 않는다.
  2. 말풍선 내부가 너무 길어지면 **말풍선 내부에서 수직/수평 스크롤**로 처리한다. 말풍선 바깥 레이아웃(채팅 스크롤, 사이드바, 메시지 간격)은 변형되지 않는다.
  3. `<details>` 펼침/접힘 시 **`<summary>`가 뷰포트 내 동일 위치에 유지**되도록 스크롤을 보정한다(scroll anchor).
  4. user 말풍선은 우측 정렬 좁은 형태를 유지해 assistant와 시각적으로 확실히 구분된다.
- 검토한 대안:
  - Option A (사용자 제안 원형): 말풍선 전폭 + 내부 수평 스크롤. 단순하고 직접적.
  - Option B (Claude artifact 사이드 패널): 결과셋을 별도 right-panel에 띄워 채팅 흐름과 분리. 현재 이슈 해결에는 과설계이며 Navigator/CSV 링크/progress strip 과의 통합 비용이 큼.
  - Option C (채택): **말풍선 고정 폭 + `<details>` 본문 max-height 캡 + 중첩 스크롤 + summary 클릭 스크롤 앵커**. Option A의 직접성에 scroll anchor를 더해 "펼칠 때 위치가 튀는" 부작용까지 해소. 기존 Navigator/CSV 흐름 그대로 재사용.
- 접근:
  1. **말풍선 폭 분기 (styles.css)**:
     - 기존 `.message { max-width: 82% }` 를 제거하고 역할별로 분리:
       ```css
       .message.is-user      { max-width: 72%; }
       .message.is-assistant { max-width: calc(100% - 48px); }
       ```
       (assistant 는 우측으로만 약 48px 여백, 나머지는 전부 사용 — 사용자 질문 영역과 구분은 이 여백으로 확보)
     - `.message-bubble` 에 `width: 100%; min-width: 0;` 추가해 말풍선 자체가 자식 내용에 의해 팽창하지 않도록 고정한다.
  2. **펼침 본문 내부 스크롤 (styles.css)**:
     - `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; }` — 펼침 시 본문 전체가 내부 세로 스크롤. `overscroll-behavior: contain`으로 내부 끝에 도달해도 상위 채팅 스크롤이 이어서 움직이지 않게 격리.
     - `.message-details[open] .message-details-body { padding-right: 4px; }` 로 스크롤바가 생길 때 콘텐츠가 숨지 않게 여유.
  3. **결과 테이블 기본 스크롤 (styles.css)**:
     - `.result-table-wrap { max-height: 320px; overflow: auto; }` 기본 캡 (기존에는 수평 스크롤만). "전체 데이터 보기"로 CSV 를 로드한 경우(`is-full-data`)는 기존 360px 를 유지.
  4. **초장문 SQL 캡 (styles.css)**:
     - `.sql-block { max-height: 240px; overflow: auto; }` — 수백 줄 SQL이 말풍선을 뚫고 들어오는 걸 방지. 기존 pre-wrap/word-break 은 유지.
  5. **Navigator 패널 min-width (styles.css)**:
     - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 에 `min-width: 0` 재확인(이미 있는 곳도 있으나 누락된 곳 보강)해 flex/grid shrink 허용.
  6. **스크롤 앵커 (app.js)**:
     - [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()` 에서 `<summary>` 에 `click` 리스너를 추가:
       - 클릭 직전에 `summary.getBoundingClientRect().top - messageLogEl.getBoundingClientRect().top` 을 기록(=`prevOffset`).
       - `requestAnimationFrame` 2회 후(`<details>` open 상태 토글 + 레이아웃 반영 이후) 같은 값을 다시 계산해 `delta = newOffset - prevOffset` 만큼 `messageLogEl.scrollTop` 을 더한다.
     - 결과: `<summary>` 라인은 사용자 뷰포트에서 동일한 y좌표에 고정되고, 펼침으로 생긴 공간은 `<summary>` 아래로만 밀려난다.
     - 접힘 시에도 같은 로직이 대칭으로 작동 (summary 위치 유지).
- 범위 제한:
  - 백엔드/agent-core 변경 없음.
  - 기존 SQL Navigator, CSV 다운로드, "전체 데이터 보기", Progress Strip `<details>` 는 그대로 유지. Progress Strip 은 이번 이슈의 범주가 아님 (이미 TASK-0022 에서 max-height 처리됨).
  - admin 콘솔 쪽 CSS 변경 없음.
- 검증 기준:
  1. assistant 말풍선이 기본적으로 채팅 pane 의 오른쪽 약간(≈48px)만 남기고 좌측부터 넓게 차지한다. user 말풍선은 우측 정렬 좁은 형태로 구분된다.
  2. `<details>` 접힌 상태의 말풍선 크기가, `<details>` 를 펼쳐도 **폭이 변하지 않는다**. 내부에 긴 SQL · 큰 결과 테이블 · 여러 쿼리 Navigator 가 있어도 말풍선의 폭/높이 outline 은 결과셋 구성에 무관하게 일정(max-height 내부 스크롤로 흡수).
  3. `<summary>` 클릭으로 펼칠 때 해당 `<summary>` 라인이 뷰포트 내 동일 좌표에 유지된다. 접을 때도 동일. 채팅 로그 다른 메시지들의 뷰포트 위치가 튀지 않는다.
  4. 결과 테이블 내부에서 세로/가로 스크롤이 작동하고, 채팅 로그 스크롤과 독립적(`overscroll-behavior: contain`)이다.
  5. 단일 SQL step / 다중 SQL Navigator / CSV 전체 데이터 로드 / `meta.sql` 폴백 네 경로 모두에서 위 동작이 일관된다.
  6. 브라우저 자동화(또는 수동) 스크린샷으로 "펼침 전/후 말풍선 bounding box 동일" 과 "summary 좌표 불변"을 확인.

### TASK-0029 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  1. OVERVIEW / ACCOUNTS / ROLES 3개 섹션이 한 화면에 스택되어 있어 ([admin.html:22-111](../src/static/admin.html#L22-L111)) 현황을 한눈에 파악하기 어렵다.
  2. 페이지 좌우 여백 때문에 정보 표현 공간이 낭비된다. (채팅 "작업 화면"은 `100vw` app-shell 레이아웃을 쓰는 반면, admin은 좁은 surface-card 3개를 세로로 쌓은 구조)
  3. ACCOUNTS 섹션의 `#adminSearch`("사용자 ID 검색…") 플레이스홀더를 보고 ROLES 요소를 찾으려다 실패하는 사용자 동선이 확인됨. 한 화면에 두 섹션이 동시에 보여 검색 범위에 대한 혼동을 유발.
  4. 각 계정/역할이 모든 필드를 펼친 채로 나열되어 있어 목록 탐색이 어렵다. 요약 라인 + 클릭 시 상세 펼침이 필요.
  5. 계정 "관리"는 **일괄 작업**이 전제되어야 한다. (여러 계정에 권한 추가/수정/제거, 일괄 삭제 등)
  6. **크리티컬 버그**: 여러 계정을 동시에 수정한 뒤 특정 계정 하나에서 "저장" 누르면 나머지 계정의 pending 변경사항이 모두 소실됨. 원인: [admin.js:463-483](../src/static/admin.js#L463-L483)에서 저장 성공 후 `loadAdminData()`가 전체 DOM을 re-render하면서 다른 form의 pending edit가 지워진다. 역할 편집도 동일 패턴([admin.js:641-662](../src/static/admin.js#L641-L662)). AWS IAM 콘솔처럼 **pending changes 누적 + 일괄 commit** 구조로 전환 필요.
  7. Admin 화면이 "작업 화면"과 구성/레이아웃이 달라 위화감이 있다.
- 목표:
  - 관리 콘솔을 **탭 기반 네비게이션** + **마스터-디테일 리스트** + **AWS 스타일 일괄 commit 바** 구조로 전환.
  - 여러 계정/역할을 동시에 수정해도 각각의 pending 상태가 유지되며, 화면 하단의 "변경사항 N건 · 적용 / 취소" 바에서 일괄 커밋.
  - 채팅 작업 화면의 `app-shell` 스타일(전폭 + 좌측 사이드 + 상단 topbar)과 톤을 맞춘다.
- 접근:
  1. **레이아웃 재구성 (admin.html)**:
     - 현재 `<main class="admin-main admin-section-stack">` 3 section 스택 구조를 제거하고, 채팅 `app-shell`과 유사한 3영역 레이아웃으로 전환:
       ```
       <body class="admin-shell">
         <header class="topbar"> (브랜드 / 탭 네비 / 로그아웃)
         <aside class="admin-sidebar"> (대시보드 / 계정 / 역할 탭 버튼, 각 탭에 배지: 계정 N, 역할 M, pending 변경 K)
         <main class="admin-workspace"> (선택된 탭의 패널만 표시)
         <footer class="admin-commit-bar"> (pending 변경 N건 · 취소 · 모두 적용)
       ```
     - 각 탭 패널은 `<section data-admin-pane="dashboard|accounts|roles">`로 구성하고 비활성 탭은 `display:none`.
  2. **대시보드 탭 (신규)**:
     - 현재 4개 metric card(Active/Inactive/Deleted/Roles)를 유지하되 카드를 더 크게 배치하고 보조 정보 추가:
       - 최근 7일 로그인한 계정 수
       - 권한이 할당된 역할 수 / 전체 역할 수
       - pending 변경사항 미리보기 리스트 (있을 때만)
     - 전폭을 활용해 grid-template-columns를 반응형으로 (`repeat(auto-fit, minmax(220px, 1fr))`).
  3. **계정 탭 — 마스터/디테일 구조**:
     - 레이아웃: 좌측 account list (username, role, 상태 뱃지, pending 마크) + 우측 detail pane (선택된 계정의 편집 폼).
     - 리스트 각 row: checkbox + username + role 이름 + 상태 chip + pending 표시(`•`). 클릭 시 detail pane에 해당 계정 로드.
     - 리스트 상단 툴바: **scoped search** ("계정/사용자 검색…"으로 플레이스홀더 변경), 상태 필터(전체/활성/비활성/삭제), 선택된 row 수 + 일괄 액션 드롭다운(활성화/비활성화/삭제/역할 변경/권한 추가/권한 제거).
     - detail pane: 기존 per-form submit 제거. form의 value change event → `adminState.pending.accounts.set(id, patch)` 에 기록만 하고 서버 호출 없음. 저장 버튼은 detail pane 내부에 "이 변경을 pending에 추가" 같은 로컬 확정 버튼으로 둔다(혹은 inputs 가 변하면 자동으로 pending 에 들어가는 방식, 이쪽이 더 AWS 스타일).
     - pending patch가 있는 계정은 리스트/detail 모두에서 `•` 마커로 표시.
  4. **역할 탭 — 마스터/디테일 구조**:
     - 동일 패턴. 리스트(role name + key + 멤버 수 + 활성 뱃지 + pending 마크) + detail pane(name/description/permission grid/활성/기본 가입).
     - 역할 생성 폼은 리스트 상단 "+ 새 역할" 버튼 → detail pane에 빈 폼 로드 (별도 페이지/모달 없이 동일 pane 재사용).
     - 역할 일괄 작업: 선택된 역할들을 활성/비활성 토글, 삭제.
  5. **Pending / Commit 상태 모델 (admin.js)**:
     ```js
     adminState.pending = {
       accounts: new Map(),  // id -> { role_id?, is_active?, permission_overrides?, _delete?: true }
       roles: new Map(),     // id -> { name?, description?, is_active?, is_default_signup?, permission_codes?, _delete?: true, _create?: { role_key, ... } }
       createRoles: [],      // 임시 생성한 역할들 (tempId 관리)
     };
     ```
     - `adminState.pending`의 변경마다 commit bar 카운트/내용 업데이트.
     - commit bar `모두 적용`: pending의 각 entry에 대해 PATCH/DELETE/POST 순차 호출(또는 `Promise.all`, 에러 시 실패한 항목만 pending에 남김). 전체 완료 후 `loadAdminData()` 1회.
     - commit bar `취소`: `pending`을 비우고 detail pane 을 현재 서버 값으로 다시 렌더.
     - **핵심**: `loadAdminData()` 는 "모두 적용" 이후에만 호출. 단일 저장으로 전체 DOM 초기화 경로를 제거한다.
  6. **Per-tab scoped search**:
     - `#adminSearch`를 제거하고, 각 탭 리스트 상단에 전용 search input을 배치. 계정 탭: "username 검색", 역할 탭: "역할 이름/키 검색". 대시보드 탭: 검색 없음.
  7. **bulk 작업**:
     - 리스트 row 체크박스 + 헤더 "전체 선택" 체크박스. 선택된 row 수가 1 이상이면 일괄 액션 바 노출.
     - 일괄 액션은 즉시 API 호출하지 않고 pending에 반영(동일 모델).
     - 일괄 권한 추가/제거: 모달 대신 선택 후 드롭다운 → 권한 코드 선택 → 선택된 모든 계정의 `permission_overrides[code]` 를 allow/deny/inherit 로 일괄 세팅.
  8. **CSS (styles.css 추가/수정)**:
     - `.admin-shell` grid: `grid-template-columns: 240px 1fr; grid-template-rows: 60px 1fr 56px;` (topbar + sidebar + main + commit-bar).
     - `.admin-sidebar`: 탭 버튼, 각 버튼에 pending 배지 (`.tab-badge`).
     - `.admin-workspace`: 패널 컨테이너, 전폭 활용.
     - `.admin-list-detail`: `grid-template-columns: minmax(260px, 360px) 1fr; gap: 16px;` — 좌측 리스트 + 우측 디테일.
     - `.admin-list-row`: 선택 상태(`.is-active`), pending 상태(`.has-pending`) 표시.
     - `.admin-commit-bar`: `position: sticky; bottom: 0; background: ...; box-shadow: top;` — 변경사항 N건 · 취소 / 모두 적용.
     - 반응형: viewport width 1024px 미만이면 `.admin-list-detail` 가 1열로 스택, 리스트 클릭 시 detail pane 이 리스트 위로 올라오는 모바일 친화 모드.
- 범위 제한:
  - 백엔드 API 변경 없음. 기존 PATCH/DELETE/POST 엔드포인트 그대로 사용.
  - 실제 서버 호출 시점만 변경(개별 → 일괄).
  - 권한 정의(33개 permission, 그룹 라벨)와 `renderPermissionGrid()` 자체는 기존 그대로 재사용 (detail pane 안에서만 호출).
  - 로컬 LLM, chat UI 쪽은 수정하지 않는다.
- 검증 기준:
  1. 관리자 계정 로그인 → `/admin` → 좌측 사이드바에 "대시보드 / 계정 / 역할" 탭 버튼이 보이고, 초기 표시는 대시보드.
  2. 계정 탭 클릭 → 리스트/디테일 2분할 레이아웃. 리스트 검색 플레이스홀더가 "사용자 검색…" 등 계정 전용 문구.
  3. **다중 편집 보존 시나리오**: 계정 A 선택 → role 변경 → 계정 B 선택 → permission override 변경 → 계정 C 선택 → is_active 토글. 하단 commit bar가 "변경사항 3건"을 표시. 계정 A 다시 선택 시 role 변경이 그대로 유지. "모두 적용" 클릭 후 서버 반영 확인.
  4. "취소" 클릭 시 pending 이 비워지고 detail pane 이 서버 값으로 복원된다.
  5. 일괄 선택 시나리오: 계정 3개 체크 → 일괄 비활성화 → commit bar 변경사항 3건 → 적용.
  6. 역할 탭에서도 동일한 pending/commit 모델 동작.
  7. 페이지 좌우 여백이 chat 작업 화면 수준으로 확장되어 있고 (full viewport width), topbar/sidebar 톤이 chat `app-shell` 과 맞춰져 있다.
  8. 브라우저 자동화 스크립트로 위 6번까지 시나리오를 재현해 증빙한다.

### TASK-0027 상세 설계
- 문제:
  - 다른 AI 작업자가 RBAC 권한을 33개(5그룹: console/account/role/conversation + misc)로 세분화했으나, Profile 드로어의 권한 현황 영역은 `buildPermissionPills()`([app.js:326-345](../src/static/app.js#L326-L345))이 활성 권한을 **알파벳순 플랫 리스트**로 렌더링하기만 해서 한눈에 파악 불가.
  - 관리 콘솔의 계정 편집은 `renderPermissionGrid(..., mode="override")`([admin.js:84-146](../src/static/admin.js#L84-L146))에서 33개 permission 각각이 inherit/allow/deny select dropdown으로 렌더링되어 계정 1건당 33개 select가 쌓이고, 페이지당 10개 계정이 나오면 330개 select가 한 화면에 쌓여 실사용 불가 수준이 됨.
  - 역할 편집 권한 그리드([admin.js:384-559](../src/static/admin.js#L384-L559))는 그룹화는 되어 있으나 접기/펼치기가 없어 역할 1건당 5개 그룹 33개 체크박스가 전부 펼쳐져 스크롤 지옥.
- 목표:
  - Profile 드로어: 활성 권한을 그룹(console/account/role/conversation)별로 묶어 섹션 헤더 + pill chip으로 렌더. 그룹 내 권한이 없으면 그룹 자체 숨김.
  - 관리 콘솔 계정 override: `<details>`/`<summary>` 기반 collapsible 그룹으로 전환. summary에 `그룹명 · (N allowed / M denied / 나머지 inherit)` 상태 배지를 표시해 접힌 상태에서도 override 현황이 보이게 함. 기본 접힘.
  - 역할 편집 권한 그리드: 동일한 collapsible 그룹 구조. summary에 `그룹명 · (N/M 선택됨)` 카운트. 기본 접힘(단 선택된 항목이 있는 그룹은 열림).
  - 각 그룹에 "모두 허용 / 모두 거부 / 모두 상속" 배치 액션 버튼(권한 있을 때만). 일괄 조작 가능.
- 접근:
  - `PERMISSION_LABELS`에 그룹 라벨 맵 추가 (`console` → "관리 콘솔", `account` → "계정", `role` → "역할", `conversation` → "대화", `misc` → "기타").
  - app.js `buildPermissionPills()`를 `buildPermissionSections()`로 재작성. 입력: `state.user.permissions` + 서버가 반환한 permission 정의(그룹 정보 포함). 없으면 코드의 앞쪽 토큰(`console.*`, `account.*` 등)으로 폴백 그룹화.
  - admin.js의 `renderPermissionGrid()`에 `collapsible: true` 옵션 추가. 각 그룹을 `<details>`로 감싸고 summary에 실시간 카운트 배지. 배치 액션 버튼 포함.
  - CSS: `.permission-section`, `.permission-section-head`, `.permission-section-counts`, `.permission-bulk-actions` 스타일 추가. 기존 `.permission-group*`/`.permission-grid*` 스타일은 유지하고 `<details>` 내부에서 재사용.
- 검증 기준:
  - Profile 드로어에서 활성 권한이 그룹별 헤더 아래로 묶여 표시된다.
  - 관리 콘솔 계정 1건을 펼쳤을 때 override 섹션이 기본 접힘 상태로 보이고, summary에 그룹별 allow/deny 카운트가 표시된다.
  - 역할 편집 그리드도 동일한 collapsible 그룹 구조로 동작한다.
  - 배치 액션 버튼(모두 허용/거부/상속)이 동일 그룹 내 모든 select/checkbox에 반영된다.
  - 권한이 없는 사용자는 액션 버튼/체크박스가 disabled로 표시된다.
  - 브라우저 자동화로 admin.html을 열어 section 개수, collapsed 상태, 카운트 정확성을 확인한다.

### TASK-0028 상세 설계
- 문제:
  - Insights(스키마/테이블 메타데이터 자동 분석) 기능이 `insight.py`에 660줄로 구현되어 있으나 **어느 문서에도 명시되어 있지 않음**. 사용자 입장에서는 백그라운드 worker가 돌고 있는 것을 "서비스 오류"로 오해함.
  - Insights 외에도 코드에만 있고 문서에 없는 주요 기능들: SYSTEM_PROMPT 설계 의도, TOOL_DEFINITIONS 우선순위 근거, Step Loop/Timeout/Cancel 메커니즘, Knowledge Injection(KNOWN SCHEMAS 자동 주입), CSV 저장(preview_table + csv_paths 2단계 반환), Fingerprint 변경 감지, Advisory Lock 등.
- 목표:
  - feature-0002-agent-core 문서를 "코드만 보면 알 수 없는 기능/설계 의도"가 모두 드러나도록 보강.
  - 신규 문서 2종 추가 + 기존 FUNCTION.md 확장.
  - 각 기능이 "어디서 왜 이렇게 동작하는지"를 실제 코드 경로/줄 번호와 함께 설명.
  - 검증: 문서를 작성하면서 실제 insight worker가 현재 런타임에서 정상 동작하는지(heartbeat, last_cycle_at, last_status) MEMORY DB로 직접 확인.
- 접근:
  1. **`docs/INSIGHTS.md` 신규 작성**: Insight 시스템 아키텍처 전용 문서.
     - 목적과 사용자 영향 (질의 응답 품질 향상 / 탐색 단계 감소)
     - 3단계 데이터 생성: bootstrap → instance scan → on-demand refresh
     - Worker 구조: `run_insight_worker_loop()` → `run_insight_cycle()` → `_bootstrap_schema_insights()` + `_scan_instance_schema_insights()`
     - Fingerprint 변경 감지 (`_compute_schema_fingerprint`, `_compute_table_fingerprint`, batch 최적화)
     - Advisory Lock (MySQL GET_LOCK 기반, `AGENT_INSIGHT_WORKER_LOCK_NAME`)
     - Heartbeat & Stale 감지 (`_is_insight_worker_heartbeat_fresh` + `AGENT_INSIGHT_WORKER_STALE_SEC`)
     - Inline fallback (`_should_run_inline_insight_scan`, worker 부재 시 ask 시점에 인라인 실행)
     - 메모리 DB 저장 키(`schema_insight:*`, `table_insight:*`, `insight_worker_last_*`)
     - 환경변수 표 (`AGENT_SCHEMA_INSIGHT`, `AGENT_INSIGHT_WORKER_*`, `AGENT_INLINE_INSIGHT_ON_ASK` 등)
     - "오류 아님 신호" 표 — 사용자/운영자가 "이건 오류 같다"고 오해하기 쉬운 로그 라인과 실제 의미.
     - 헬스 체크 SQL snippet (worker heartbeat, last_status, last_error 조회용)
  2. **`docs/AGENT_CORE_INTERNALS.md` 신규 작성**: agent_core + 주변 모듈의 숨은 계약 문서.
     - SYSTEM_PROMPT 구조 설명: CRITICAL DIRECTIVE → CORE RULES → STRATEGY → IDEAL FLOW → ANTI-PATTERNS → SQL PATTERNS → OUTPUT (코드 파일/줄 참조)
     - TOOL_DEFINITIONS 우선순위: execute_sql 최우선 배치 근거 (LRN-20260416-0001와 연결)
     - Knowledge Injection 흐름: `_build_knowledge_context()` → KNOWN SCHEMAS + RELEVANT TABLES 자동 주입
     - Step Loop & Budget: max_steps, timeout, finalize_now 신호, cancel 요청
     - CSV 저장 2단계: preview_table(LLM에 전달, 기본 5행) + csv_paths(전체 결과, 별도 파일)
     - Planner fast path (`_build_insight_object_fast_plan`): 인사이트 기반 빠른 실행 계획 (있을 때)
  3. **`docs/FUNCTION.md` 보강**:
     - "Main Flow" 섹션을 실제 호출 경로로 확장 (knowledge injection → step loop → tool call → memory write).
     - "Dependencies" 섹션에 MEMORY_DB 스키마 의존성 명시 (`AgentMemoryFactEntries`, `AgentMemoryTexts`, insight KV 키 패턴).
     - "Observability" 섹션에 insight_worker 로그 파일과 healthcheck 방법 추가.
  4. **검증**: 실제 MEMORY DB에 접속해 `insight_worker_last_cycle_at`, `insight_worker_last_status`, `schema_insight:*` 몇 개를 조회하고, 문서에 예시 출력으로 넣어 "현재 실제로 이렇게 돌고 있다"는 증빙을 남긴다.
- 범위 제한:
  - 코드 변경 없음. 문서만 추가/갱신.
  - 기존 인사이트 로직/설정값은 그대로 유지.
  - 신규 문서는 `unit/feature-0002-agent-core/docs/` 하위에 배치.
- 검증 기준:
  - 신규 문서 2종이 존재하고, 각 문서에서 언급된 함수/상수/환경변수가 실제 코드에 존재한다.
  - Insight worker 헬스 체크 SQL snippet이 실제 MEMORY DB에 대해 실행 가능하다(검증 과정에서 직접 실행 결과를 문서에 남김).
  - FUNCTION.md Main Flow 내 각 단계가 실제 코드 경로와 일치한다.

### TASK-0026 상세 설계
- 문제: assistant 말풍선에 한 줄로 길게 들어온 SQL(예: `SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...`)이 `<pre class="sql-block">`의 `white-space: pre` + `overflow-x: auto` 특성상 줄바꿈 없이 길게 그려지며, flex/grid 자식의 `min-width` 계산으로 인해 말풍선 전체가 수평으로 확장되는 UX 이슈가 있다.
- 목표:
  - SQL 쿼리가 한 줄로 길게 들어와도 말풍선 폭이 부모(채팅 영역) 폭 이상으로 확장되지 않는다.
  - 쿼리 가독성을 유지하기 위해 주요 키워드 경계에서 줄바꿈을 적용한다. 이미 여러 줄인 쿼리는 원형을 유지한다.
  - 기존 Navigator 헤더/버튼/컨텍스트 레이아웃은 그대로 유지한다.
- 접근:
  - 표시 전용 포매터 `formatSqlForDisplay(sql)` 추가 (저장/실행 SQL에는 영향 없음, `<pre>.textContent`에만 적용):
    - 입력에 이미 `\n`이 있으면 그대로 반환 (LLM이 포맷팅한 경우 존중).
    - 단일 라인일 경우 주요 키워드 경계에서 줄바꿈을 삽입한다. 대상 키워드:
      `SELECT`, `FROM`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`,
      `LEFT JOIN`, `RIGHT JOIN`, `INNER JOIN`, `OUTER JOIN`, `FULL JOIN`, `CROSS JOIN`, `JOIN`,
      `ON`, `AND`(AND만 분리 시 너무 잦아지므로 `WHERE/ON` 뒤의 AND만), `UNION`, `UNION ALL`, `INSERT INTO`, `UPDATE`, `SET`, `VALUES`, `DELETE FROM`.
    - 정규식 기반으로 구현하되 **따옴표 안의 키워드는 분리하지 않는다**(단순 토크나이저로 문자열 리터럴 내부 스킵).
    - 중첩 괄호(서브쿼리) 깊이는 유지하고 별도 들여쓰기는 하지 않는다(단순화·안정성 우선).
  - CSS 수정:
    - `.sql-block`을 `white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere;` 로 변경(포매터가 못 잡는 초장문 토큰·식별자도 wrap되도록 안전망).
    - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 등 컨테이너에 `min-width: 0`을 보장해 flex/grid 자식 shrink를 허용한다.
  - 기존 단일 step 블록과 Navigator 패널 양쪽 모두 `buildSqlStepPanel()`을 경유하므로 한 곳만 수정하면 된다.
- 범위 제한:
  - 포매터는 표시용(`pre.textContent`) 전용. 서버로 전송되는 SQL, 복사(copy) 시나리오에는 영향을 주지 않는다(복사 시 줄바꿈 포함 허용 — 사용자가 다시 한 줄로 정리하면 되므로).
  - 새 백엔드 API 없음. agent_core / tools 변경 없음.
  - 기존 Navigator/키보드/CSV 전체 보기 로직은 변경하지 않는다.
- 검증 기준:
  - 긴 한 줄 SQL을 주입했을 때 말풍선 폭이 chat pane 폭 이상으로 확장되지 않는다.
  - `SELECT`/`FROM`/`WHERE`/`JOIN`/`GROUP BY`/`ORDER BY` 경계에서 줄바꿈이 삽입된다.
  - 이미 여러 줄로 포맷된 쿼리는 원형이 유지된다.
  - 따옴표 내부 문자열의 키워드(예: `'SELECT one, ...'`)는 분리되지 않는다.
  - 기존 Navigator 키보드 조작(`←/→/Home/End`)과 "전체 데이터 보기"가 그대로 동작한다.

### TASK-0025 상세 설계
- 문제: assistant 말풍선 내 `<details>`(실행 단계 및 쿼리 결과 보기)를 펼치면, execute_sql step이 여러 개인 경우 각 SQL + 결과 테이블이 수직으로 누적되어 말풍선 길이가 과도하게 증가한다. UI 개편 이전에 있었던 별도 팝업(`CSV 미리보기`) 방식은 창 크기가 레코드 수에 따라 흔들리는 UX 이슈가 있었다.
- 목표:
  - 말풍선 내 `<details>` 안에서 다수 SQL step을 수직 누적 없이 탐색 가능한 Navigator로 압축한다.
  - 각 말풍선의 탐색 범위는 해당 말풍선으로만 한정된다(격리된 스코프). 현재 선택된 결과셋이 어떤 SQL에 대응하는지 화면에서 상시 확인 가능해야 한다.
  - preview 레코드 제한을 넘어 전체 데이터도 조회 가능해야 한다(CSV 기반).
  - 키보드 조작 가능, 단 조작법은 화면에 상시 노출하지 않고 버튼의 `title` 툴팁(마우스 hover)으로만 힌트 제공.
- 접근:
  - `buildStepBlocks()`를 분해. execute_sql step이 2개 이상이면 Navigator 형태로 렌더링, 1개면 기존 단일 블록 유지.
  - Navigator 구조:
    - 헤더(1행): `◀` 이전 버튼 + `쿼리 n/N` 인디케이터 + `▶` 다음 버튼 + 현재 쿼리의 첫 테이블 참조(작업 대상) 라벨.
    - 본문: 현재 인덱스의 SQL `<pre>` + 결과 테이블 + 액션 영역(전체 데이터 보기, CSV 다운로드).
  - 키보드 조작:
    - Navigator 컨테이너에 `tabindex="0"` 부여 → 포커스 시 `←`/`→`로 prev/next, `Home`/`End`로 처음/끝 이동.
    - 각 버튼의 `title`에 단축키 힌트 포함(예: `이전 쿼리 (←)`).
  - 전체 데이터 조회:
    - preview_table이 truncated이고 csv_paths가 있을 때 "전체 N행 보기" 버튼 노출.
    - 클릭 시 `/api/file?path=...` 로 CSV fetch → 클라이언트 측 CSV 파서로 파싱 → 기존 테이블의 tbody를 전체 행으로 교체.
    - 대량 행(>500) 렌더 시 테이블 컨테이너 `max-height` + `overflow:auto`로 말풍선 영역 보호.
  - 스코프 격리:
    - Navigator 인스턴스마다 내부 상태(현재 인덱스)를 가지며, 말풍선 별로 완전 격리.
    - 헤더 상단에 "쿼리 1/3 · `schema.table`" 형태로 현재 선택 컨텍스트 상시 노출.
  - 접근성:
    - 버튼에 `aria-label`, 인디케이터에 `aria-live="polite"` 부여.
    - 키보드 포커스 시 outline 스타일 유지(제거하지 않음).
- 범위 제한:
  - 새로운 백엔드 API 추가 없음. 기존 `/api/file`만 재사용.
  - 기존 `<details>` 드롭다운 구조는 유지(그 안의 렌더링만 교체).
  - 단일 SQL step 케이스는 Navigator를 쓰지 않고 기존 블록 유지(불필요한 chrome 방지).
- 검증 기준:
  - operator 계정으로 2개 이상 execute_sql step을 발생시키는 질의 전송 후, Navigator로 단계 탐색이 정상 동작한다.
  - 키보드 `←/→/Home/End`로 step 이동 가능.
  - "전체 데이터 보기" 클릭 시 preview 이상의 행이 테이블에 렌더링된다.
  - 말풍선 총 높이가 step 수와 무관하게 한 화면 내로 유지된다.

## 4. Blocked
- 없음

## 5. Done
- TASK-0010 (2026-04-15): `WebAccounts`, `WebAuthSessions`, 회원가입/로그인/로그아웃 API, 부트스트랩 관리자 계정 추가
- TASK-0011 (2026-04-15): `/admin` 화면과 계정 승인/비활성/세부 권한 제어 API/UI 추가
- TASK-0012 (2026-04-15): `AgentCoreConversations.owner_account_id` 기반 계정 소유권 도입, 기존 대화 관리자 귀속 처리
- TASK-0013 (2026-04-15): 표시 이름/역할/사용 목적 입력 제거, Keyword Management 제거, Domain/Strategy/Session/Calendar 등 불필요한 UI 제거
- TASK-0014 (2026-04-15): 세션 응답의 `local_llm_enabled`를 실제 연결 가능 여부 기준으로 보정
- TASK-0015 (2026-04-15): 외부 스크롤 제거 · 마케팅 패널 제거 · App-Shell 레이아웃 적용. 로그인: 단일 카드, 메인: Topbar+Sidebar+ChatPane 3단 고정 구조
- TASK-0016 (2026-04-15): feature AGENTS.md §8에 UI/UX 설계 원칙, 버튼 클래스 규칙, 브라우저 검증 정책, 금지사항 문서화. LEARNINGS.md에 3개 항목 추가
- TASK-0017 (2026-04-15): 사이드바 하단 프로필 트리거(ChatGPT 패턴) + 프로필 드로어(권한/활동정보/비밀번호 변경/로그아웃). state.busyConversations Set으로 병렬 대화 지원. Admin 콘솔에 검색/필터/페이지네이션 추가
- TASK-0018 (2026-04-15): 프로필 드로어를 계정/보안/API Vault 3탭으로 재구성. 기존 설정 드로어 제거 및 API Vault 흡수. 탑바 API Vault 버튼 제거. 로그아웃 시 드로어 미닫힘 버그·회원가입 폼 잔류 버그 수정.
- TASK-0019 (2026-04-15): `llm-shared` 외부 네트워크에 Ollama 기반 `local-llm-gateway`를 복구하고 `auto/edge/core/code` alias 모델을 준비해 API 키 없는 `model=auto` 실행 경로를 복원
- TASK-0020 (2026-04-15): 현재 repo 내부 Local LLM runtime을 제거하고, 외부 `/root/download/docker/local_llm` provider를 `LOCAL_LLM_API_BASE=http://local-llm-gateway:8080/v1` 계약으로 소비하도록 전환
- TASK-0021 (2026-04-15): UI 개편 과정에서 누락된 `execute_sql` step 결과셋 인라인 표시 복원. `result_summary.preview_table`을 HTML 테이블로 렌더링, SQL 쿼리+결과+CSV를 step 단위로 묶어 표시. 구형 메시지는 `meta.sql`/`meta.csv_paths` 폴백.
- TASK-0022 (2026-04-16): Progress Strip을 `<details>`/`<summary>` 드롭다운으로 전환. step 수가 늘어도 기본 1행 고정, 펼침 시 `max-height:40vh` 내부 스크롤. summary에 `n단계 · 최근 작업` 표시.
- TASK-0023 (2026-04-16): Planner 자율성 개선 — TOOL_DEFINITIONS 순서를 execute_sql 최우선으로 재배치, 각 도구 description에 사용 조건 명시, SYSTEM_PROMPT에 CRITICAL DIRECTIVE·IDEAL FLOW EXAMPLE·강화 ANTI-PATTERNS 추가. 휴리스틱 없이 프롬프트/도구 제시 순서만으로 불필요 탐색을 억제.
- TASK-0024 (2026-04-16): `WebRoles`/`WebPermissions`/`WebRolePermissions`/`WebAccountPermissionOverrides` 기반 RBAC로 cutover. role명 특수 처리 없이 permission + ownership 로만 권한 판정. 계정 soft delete, role CRUD, tri-state override, own/any 대화 권한, 제목 변경 API, Accounts/Roles 2영역 관리자 콘솔, `/api/clear_memory` 제거 완료.
- TASK-0025 (2026-04-16): assistant 말풍선 내 다중 execute_sql step을 수직 누적 없이 SQL Navigator(단일 패널 + `←/→/Home/End` 키보드 조작 + `쿼리 n/N · 대상 테이블` 상시 컨텍스트 + "전체 데이터 보기" CSV 로드)로 압축. 단일 step은 기존 블록 유지. 새 백엔드 API 없이 `/api/file`만 재사용. 브라우저 자동화로 탐색/키보드/단일 step 분기/CSV 파서 모두 검증 완료.
- TASK-0026 (2026-04-21): 한 줄 긴 SQL이 말풍선을 수평 확장하는 이슈 해소. 표시 전용 `formatSqlForDisplay()` 추가(주요 키워드 경계 줄바꿈, 복합 JOIN 보존, 문자열 리터럴 보호, 기존 여러 줄 쿼리 원형 유지). `.sql-block` CSS를 `pre-wrap` + `word-break` + `overflow-wrap`으로 변경, 컨테이너 `min-width:0` 안전망 추가.
- TASK-0027 (2026-04-21): 33개 RBAC 권한의 UX 정리. Profile 드로어의 `buildPermissionPills()`를 그룹별 `<section class="perm-section">` + 카운트 배지 구조로 재작성. Admin 콘솔 권한 그리드 `renderPermissionGrid()`를 `<details>` 기반 collapsible + summary 카운트 배지(허용/거부/상속 또는 N/M 선택) + 그룹별 배치 액션 버튼(모두 허용/거부/상속 또는 모두 선택/해제)으로 개편. `PERMISSION_GROUP_ORDER/LABELS` 상수와 `permissionGroupOf()` 헬퍼 추가. CSS: `.perm-sections`, `.perm-section*`, `.permission-group-head`, `.permission-group-counts`, `.permission-bulk-actions` 스타일 추가.
- TASK-0031 (2026-04-21): 관리 콘솔 내부 스크롤 정리. `.admin-workspace` 의 외부 스크롤(`overflow-y: auto`) 제거 → `overflow: hidden` + flex column 으로 전환하고, `.admin-pane.is-active` / `.admin-list-detail` 가 남은 공간을 `flex: 1 1 auto + min-height: 0` 으로 채우도록 변경. `.admin-list-col` / `.admin-detail-col` 각각 자체 내부 스크롤 소유 — list 컬럼은 toolbar/list-head(shrink 고정) + `.admin-list`(`flex: 1; overflow-y: auto`, 기존 `max-height: calc(100vh-320px)` 제거) + 페이지네이션/일괄 액션(`flex-shrink: 0; border-top`) 구조. detail 컬럼은 `overflow-y: auto` + `.admin-detail-actions { position: sticky; bottom: -18px; margin: 4px -22px -18px; padding: 12px 22px; background: var(--surface); border-top }` 로 저장/취소/삭제 버튼을 detail 높이와 무관하게 상시 하단 노출. 대시보드 pane 은 `overflow-y: auto` 단일 스크롤로 별도 처리. 검증: detailColScroll=1866, listScroll=807 각각 내부 스크롤 활성, docScrollDelta=0(외부 스크롤 0), paginationVisible/actionsVisible=true, 양 컬럼 끝까지 스크롤해도 두 하단 요소 모두 뷰포트 내 유지. JS/HTML 변경 없이 CSS 만으로 해결.
- TASK-0030 (2026-04-21): assistant 말풍선 고정 폭 + `<details>` 펼침 시 내부 스크롤/스크롤 앵커. `.message`의 role별 max-width 분기(user 72% / assistant `max-width:none` + `margin-right:48px` + `align-self:stretch`)로 assistant 는 채팅 pane 전폭에 가깝게, user 는 좁은 우측 정렬로 분리. `.message-details-body`에 `max-height:min(60vh,520px); overflow:auto; overscroll-behavior:contain` 캡으로 펼친 본문을 말풍선 내부에서 수직 스크롤 처리. `.result-table-wrap` 기본 `max-height:320px`, `.sql-block` `max-height:240px` 로 결과 테이블/초장문 SQL 도 내부 스크롤로 격리. `app.js` `renderMessageDetails()`의 `<summary>` 클릭 핸들러에 `messageLogEl` 기준 `summary.getBoundingClientRect().top` 측정 → 2-frame `requestAnimationFrame` 후 delta 만큼 `messageLogEl.scrollTop` 보정하는 scroll anchor 추가. 브라우저 검증: summaryDelta=0/scrollDelta=0, Navigator 이동 시 bubble width 705→705 불변, bodyMaxH=432px(60vh), details body overflow-y=auto 확인.
- TASK-0029 (2026-04-21): 관리 콘솔 재구조화. `admin.html` 을 `topbar + sidebar(tabs) + workspace + commit-bar` 4영역 grid 로 재작성(탭: 대시보드/계정/역할). `admin.js` 전면 재작성 — `adminState.pending = { accounts, roles, newRoles }` Map 기반 pending changes 모델 + 서버 값과 일치하면 auto-drop 로직(`setAccountPending`/`setRolePending`). 계정/역할 편집은 form submit 없이 input/select change 이벤트에서 pending 에 적재만 하고, 하단 commit bar 의 "모두 적용" 클릭 시 전체 pending entry 를 순차 PATCH/DELETE/POST 후 1회만 `loadAdminData()`. 리스트-디테일 레이아웃 + 탭별 scoped search + 리스트 row 체크박스 기반 일괄 작업(활성/비활성/삭제 pending 반영). 신규 역할은 tempId(`new:N`)로 pending.newRoles 에 넣고 POST 로 일괄 커밋. `styles.css` 에 `.admin-shell` grid/`.admin-sidebar`/`.admin-tab`/`.admin-list-detail`/`.admin-list-row`/`.admin-detail-*`/`.admin-commit-bar`(.has-pending 노란 강조) 스타일 추가. 사용자 테스트에서 확인된 "여러 계정 동시 수정 시 특정 계정 저장하면 타 계정 변경 소실" 버그는 pending 모델 + 단일 commit 경로로 근본 해소.
- TASK-0033 (2026-04-21): 결과셋 말풍선의 이중 스크롤 제거 + RowCount + Excel-like freeze. `styles.css` 의 `.message-details-body` 에서 `max-height: min(60vh,520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px` 일괄 제거 → 말풍선 body 는 자연스럽게 자라고 세로 스크롤은 `.messages` 하나로 통일. `.result-table-wrap` 은 `max-height: 320px → min(60vh, 460px)` + `overscroll-behavior: contain` 제거(= auto 로 복원 → 경계에서 `.messages` 로 휠 전파). `.sql-block` 도 `max-height: 240px → min(40vh, 320px)` + overscroll 제거. `.result-table` 을 `border-collapse: separate; border-spacing: 0` 으로 전환하고 border 는 `box-shadow: inset` 으로 대체(sticky 셀에서 border 누락 방지). `.result-table thead th { position: sticky; top: 0; z-index: 2 }` 로 헤더 freeze, `.result-table th.col-rownum, td.col-rownum { position: sticky; left: 0; z-index: 1 }` 로 첫 열(#) freeze, 코너 `thead th.col-rownum { z-index: 3 }` 로 교차점 최상위. `app.js` 에 `appendRowNumCell(tr, tag, value)` 헬퍼 추가, `buildResultTable()` thead/tbody 렌더 시 `<th class="col-rownum">#</th>` + `<td class="col-rownum">{i+1}</td>` 항상 prepend. `loadFullCsvIntoTable()` 도 동일 패턴으로 재구성 → "전체 데이터 보기" 이후에도 #/freeze 유지. 검증: 기존 대화의 33행 결과 테이블에서 `theadThPosition='sticky'`, `col-rownum td position='sticky'`, corner `zIndex=3`, wrap `max-height=432px`, `overscroll-behavior='auto'`, `.message-details-body { max-height: none; overflow: visible }`, `hasInnerDetailScroll=false`, 수직 스크롤 200px 시 각 th 개별 top 변동 없음(`firstTh_delta=0`), 가로 스크롤 60px 시 `col-rownum` 좌측 고정(`rnStayed=true`, `dataMoved=true`). 스크린샷 `artifacts/shared/out/browser/task0033_01_result_tables.png` · `task0033_02_sticky_header_mid_scroll.png`.
- TASK-0032 (2026-04-21): 권한 안내 UX 개편. `app.js` 에 `PERMISSION_DESCRIPTIONS`(33개 권한 서술 문장 맵), `describePermission()`, `requiredPermissionsFor(action, conversation)`(any/own 이원화된 권한 자동 확장), `hasAnyPermission()`, `showPermissionDeniedToast()`(필요 권한 코드 + 서술 + 관리자 요청 문구), `markAccessBlocked(btn, action, conversation)`(aria-disabled + is-access-blocked + 서술 title) 추가. `buildPermissionPills()` 의 `item.title = code` 를 `서술 문장\n(code)` 로 교체. `renderComposer()` 에서 `cancel/finalize/rename/delete` 버튼을 context 신호(processing / activeConversationId) 로만 hidden 토글하고, 권한 부재는 `markAccessBlocked()` 로 별도 표현. `sendBtn`/`newConversationBtn` 도 native disabled 대신 aria-disabled 사용해 클릭이 통과하도록 전환. 각 action 함수 (`createConversation`, `renameCurrentConversation`, `deleteConversation`, `cancelCurrentRun`, `finalizeCurrentRun`, `sendPrompt`) 의 silent `return` 을 `showPermissionDeniedToast()` 호출로 교체. `renderAccessNotice()` / `renderComposer()` 안내 문구에 `conversation.ask` 코드 명시. `styles.css` 에 `.is-access-blocked { opacity: .42; cursor: help; color: var(--text-muted) }` 추가. 검증 (admin / pending 계정): pill tooltip=한국어 서술 문장+`(code)`, pending 계정 composerHint=`현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다...`, sendBtn/newConvBtn/renameBtn/deleteBtn 모두 `is-access-blocked` + aria-disabled + 서술 title, 클릭 시 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요. — 타 사용자가 소유한 대화까지 삭제할 수 있는 권한입니다.` 형식 토스트 노출. 스크린샷 `artifacts/shared/out/browser/task0032_{01,02,03}_*.png` 증빙.
- TASK-0028 (2026-04-21): agent-core 문서 보강. `docs/INSIGHTS.md` 신규 작성(워커 루프/사이클/fingerprint/인라인 fallback/KV 스키마/환경변수 14종/해석 가이드/헬스 체크 SQL + 2026-04-21 실제 런타임 출력). `docs/AGENT_CORE_INTERNALS.md` 신규 작성(run_agent 흐름도, SYSTEM_PROMPT 7블록 구조, TOOL_DEFINITIONS 우선순위 근거, Knowledge Injection, Step 예산/타임아웃/cancel/finalize 신호, CSV 2단계(preview 50행 + 전체 파일), Planner insight fast path, 3-state 대화 맥락). `FUNCTION.md` Main Flow/Dependencies/Observability 확장(MEMORY_DB 스키마 표, insight_worker 로그 관측성). 코드 변경 없음.

## 6. Next Action
- 신규 권한/계정 정책 변경이 필요하면 별도 TASK로 분리한다

## 7. Completion Checklist
- [x] Web UI 코드 이관이 완료되었다
- [x] 루트 실행 경로가 새 구조를 참조한다
- [x] 문서가 현재 구조를 반영한다
- [x] 계정/비밀번호 기반 인증이 동작한다
- [x] pending/read-only 흐름이 동작한다
- [x] 관리자 승인 및 세부 권한 조정이 가능하다
- [x] 대화 소유권이 계정 기준으로 분리되었다
- [x] 불필요한 상단 상태 정보와 Keyword Management가 제거되었다
- [x] 브라우저 기반 렌더링 증빙이 남아 있다
- [x] 상용 AI 앱 수준의 App-Shell 레이아웃이 적용되었다 (외부 스크롤 없음)
- [x] UI/UX 정책 지침이 feature AGENTS.md §8에 문서화되었다
- [x] 사이드바 하단 프로필 버튼이 ChatGPT/Claude 패턴으로 배치되었다
- [x] 프로필 드로어가 계정/보안/API Vault 탭으로 구조화되어 있다
- [x] 병렬 대화가 다른 대화의 요청 처리 중에도 차단되지 않는다
- [x] Admin 콘솔에 검색·역할 필터·페이지네이션이 동작한다
- [x] 계정별 설정(API Vault)이 탑바가 아닌 프로필 드로어 안에 배치되어 있다
- [x] 로그아웃 시 열린 드로어가 닫히고 인증 폼이 초기화된다
- [x] 현재 repo가 Local LLM runtime을 직접 소유하지 않는다
- [x] execute_sql 단계의 쿼리 결과가 인라인 HTML 테이블로 표시된다
- [x] SQL 쿼리 블록과 결과 테이블, CSV 링크가 step 단위로 묶여 표시된다
- [x] Progress Strip이 `<details>` 드롭다운으로 동작하며 step 증가 시 채팅 영역이 축소되지 않는다
- [x] Planner가 execute_sql을 우선 시도하도록 도구 순서와 프롬프트가 구성되어 있다
- [x] 계정이 `Role 기본 권한 + account override` 구조로 계산된다
- [x] `pending/operator/admin` 문자열 비교 없이 permission + ownership 만으로 권한이 판정된다
- [x] 관리 콘솔에서 role 생성/수정/삭제와 기본 가입 역할 변경이 가능하다
- [x] 관리 콘솔에서 계정 role 부여와 tri-state override 편집이 가능하다
- [x] 계정 soft delete 후 로그인 차단과 세션 폐기가 동작한다
- [x] 대화 조회/제목 변경/삭제/중단/즉시답변이 own/any 권한으로 분기된다
- [x] `/api/clear_memory` 및 legacy `Can*` 계약이 런타임에서 제거되었다
- [x] 다중 execute_sql step 말풍선이 Navigator로 압축되어 수직 누적되지 않는다
- [x] Navigator에서 `←/→/Home/End` 키보드로 step 탐색이 가능하다
- [x] 현재 선택된 쿼리의 인덱스와 대상 테이블이 Navigator 헤더에 상시 노출된다
- [x] "전체 데이터 보기" 로 preview 이상의 행을 CSV 기반으로 로드할 수 있다
- [x] 한 줄 긴 SQL 쿼리가 키워드 경계에서 줄바꿈되어 말풍선이 수평 확장되지 않는다
- [x] 이미 여러 줄로 포맷된 쿼리와 따옴표 내 키워드가 원형 유지된다
- [x] Profile 드로어의 권한 현황이 console/account/role/conversation/misc 그룹 단위 섹션으로 묶여 표시된다
- [x] Admin 콘솔의 계정/역할 권한 편집이 `<details>` collapsible 그룹 구조로 동작하고 summary에 카운트 배지가 표시된다
- [x] 각 권한 그룹에 배치 액션(모두 허용/거부/상속 또는 모두 선택/해제) 버튼이 동작한다
- [x] Insight 시스템(백그라운드 스키마/테이블 분석 워커)의 구조와 헬스 체크 방법이 `docs/INSIGHTS.md`에 명시되어 있다
- [x] agent-core 내부 동작(SYSTEM_PROMPT 구조, TOOL_DEFINITIONS 우선순위, Knowledge Injection, Step 예산, CSV 2단계, Planner fast path)이 `docs/AGENT_CORE_INTERNALS.md`에 명시되어 있다
- [x] 관리 콘솔이 대시보드/계정/역할 탭 기반 네비게이션으로 분리되어 있다
- [x] 계정/역할 편집이 pending changes 모델로 관리되며, 하단 commit bar 의 "모두 적용" 시에만 서버에 반영된다
- [x] 여러 계정을 동시에 편집해도 각 편집 내용이 유지되며 단일 계정 저장으로 소실되지 않는다
- [x] assistant 말풍선이 기본적으로 채팅 pane 의 우측 약간(48px)만 남기고 넓게 고정되며, `<details>` 펼침/접힘이나 결과셋 구성 변화에 말풍선 폭이 흔들리지 않는다
- [x] `<details>` 펼침 시 내부 SQL/테이블/Navigator 가 말풍선 내부 수직 스크롤로 격리되어 채팅 로그 스크롤 위치와 전체 레이아웃이 변형되지 않는다
- [x] `<summary>` 클릭 시 해당 라인이 뷰포트 내 동일 y좌표를 유지(scroll anchor)
- [x] 관리 콘솔이 외부 페이지 스크롤 없이 viewport 에 고정되며, 리스트 컬럼과 디테일 컬럼이 각각 내부 스크롤을 가진다
- [x] 리스트 하단 페이지네이션/일괄 액션 바와 디테일 하단 저장/삭제 액션 바가 컬럼 스크롤과 무관하게 항상 뷰포트 내에 노출된다
- [x] 리스트 row 체크박스 + 일괄 작업(활성/비활성/삭제 pending)이 동작한다
- [x] 계정 탭/역할 탭 각각이 독립된 scoped search 를 가진다
- [x] Profile > 계정 탭 권한 pill 에 마우스를 올리면 한국어 서술 문장과 권한 코드가 툴팁으로 표시된다
- [x] 권한이 부족한 계정에서 차단된 동작을 시도(클릭/단축키)하면 필요 권한 코드 + 서술 문장 + 관리자 요청 문구가 토스트로 노출된다
- [x] cancel/finalize/rename/delete 버튼은 context 상 의미있을 때는 항상 보이고, 권한이 없을 때는 `is-access-blocked` 로 표시되며 클릭은 토스트로 안내된다
- [x] assistant 말풍선의 `실행 단계 및 쿼리 결과 보기` 내부에 세로 스크롤바가 중첩되지 않는다 (본문은 콘텐츠 크기만큼 확장되고 세로 스크롤은 `.messages` 하나)
- [x] 쿼리 결과 테이블에 첫 컬럼 `#` (RowCount) 이 자동 삽입되어 행 번호가 1부터 표시된다
- [x] 결과 테이블 내부 세로 스크롤 시 헤더 행이 상단 고정, 가로 스크롤 시 `#` 컬럼이 좌측 고정된다
- [x] 결과 테이블 내부 스크롤이 경계에 닿으면 채팅 로그(`.messages`) 로 휠이 전파된다 (`overscroll-behavior` 제거)
- [x] "전체 데이터 보기" 로 CSV 로드 후에도 RowCount 와 sticky freeze 가 유지된다
- [ ] TASK-0034: 복잡 QA 성능 테스트가 local LLM 5 (직렬) + 상용 API gpt-5.4-mini 5 (병렬) 총 10 대화로 실행되어 turn-by-turn 로그가 JSON 으로 저장된다
- [ ] TASK-0034: 5 개 복잡 질문에 대해 사람 truth 쿼리와 assistant 최종 답변이 비교 가능한 diff 형태로 `TASK-0034-REPORT.md` 에 기록된다
- [ ] TASK-0034: 관찰된 개선 포인트가 `docs/LEARNINGS.md` 에 신규 LRN 항목으로 추가된다
- [x] TASK-0040: `_extract_sql_schema_refs` 가 `WHERE bb.BattleType = 'X'` 등 alias.column 토큰에서 schema 를 추출하지 않는다 (FROM/JOIN 구간의 테이블 리스트로 범위 제한)
- [x] TASK-0040: `FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a` 형식 SQL 이 Product whitelist=`{dbauth,dbgame,dblog}` 상태에서 정상 통과한다
- [x] TASK-0040: 비허용 스키마(`FROM dbstat.foo`) 는 여전히 차단된다 (15 테스트 케이스 통과)
- [x] TASK-0041: `GET /api/ask_status?conversation_id=...` 이 `{is_processing, status, run_id, step_count, duration_ms, has_answer, answer_preview}` 스냅샷을 반환한다
- [x] TASK-0041: `GET /api/ask_result?conversation_id=...&run_id=...&wait=N(<=60)` 이 terminal 도달 시 `{status, run_id, assistant.{message_id,content,meta,steps_count}}` 를 반환하고, 시간 초과 시 `{timeout:true}` 를 반환한다
- [x] TASK-0041: 브라우저에서 `/api/ask` 요청이 끊겨도 `is_processing=true` 인 경우 `[계속 기다리기/즉시 답변/요청 취소]` 다이얼로그가 노출되고 선택한 동작 이후 최종 메시지가 UI 에 주입된다
- [x] TASK-0041: `task0034_runner.py` 의 `httpx.ReadTimeout` 분기가 `/api/ask_status` + `/api/ask_result` long-poll 로 attach 해 최종 응답을 해당 턴에 기록한다
- [x] TASK-0037: `/api/progress` 폴링이 `setInterval` 고정 주기가 아니라 순번 기반 `setTimeout` 체인으로 동작하고 in-flight 요청이 1 을 넘지 않는다
- [x] TASK-0037: 대화 전환/로그아웃/새 대화 생성 시 AbortController 로 진행 중인 `/api/progress` 요청이 즉시 취소된다
- [x] TASK-0037: 탭 전환(`document.hidden`) 시 폴링 주기가 최소 10초로 감속되고, 연속 오류 3회 이상이면 재스케줄링되지 않는다
- [x] TASK-0037: 서버 `/api/progress` 가 `client_run_id` 불일치 시 `after_step` 을 0 으로 리셋해 새 run 의 모든 step 을 되돌려준다
- [x] TASK-0037: 폴링 패턴 학습 내용이 `docs/LEARNINGS.md` 의 LRN 항목(LRN-20260422-0011) 로 기록된다
- [x] TASK-0044: `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 가 있고, 부트스트랩 후 `WebRoles` 에 해당 row + `conversation.create` / `conversation.ask` 등 9 개 권한이 `WebRolePermissions` 로 연결된다 (admin 콘솔 `/api/admin/roles` 조회로 확인)
- [x] TASK-0044: `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 이 sales role 에 대해 `WebSystemPrompts(Scope='role', RoleId=<sales>, ProductId=NULL)` prompt 1 row 를 1 회만 upsert 하고, 이미 존재하면 덮어쓰지 않는다 (관리 콘솔 수정 존중)
- [x] TASK-0044: sales role prompt 본문이 "단순 조회 → 문장 응답 / 집계 → 결과셋 표 응답 / ad-hoc 심층 분석 요청 → DBA 팀 이관 안내 후 대화 종료 / DB 쓰기 쿼리(INSERT/UPDATE/DELETE/DDL) 거부" 4 지침을 포함한다
- [x] TASK-0044: `modules/config.py` 가 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` / `REPLICA_DB_ENABLED` 5 개 심볼을 export 하고, `.env.example` 에 4 개 placeholder 가 등록되어 있다 (실제 접속 정보는 commit 금지)
- [x] TASK-0044: `modules/db.py::connect()` 이 `REPLICA_DB_HOST` 가 설정되어 있고 요청 `database` 가 `MEMORY_DB` 가 아닐 때 복제 인스턴스의 host/port/user/password 로 라우팅하고, 그 외에는 primary (DB_HOST/...) 로 라우팅한다
- [x] TASK-0044: `REPLICA_DB_HOST` 가 비어있는 기존 배포에서 동작이 변하지 않는다 (`connect(database=None)` / `connect(database=MEMORY_DB)` / `connect(database="dbgame")` 모두 primary 접속)
- [x] TASK-0073: `WebAuditEvents` 테이블 (14 columns + 5 indexes) 이 slow/fast path 모두에서 idempotent 생성 (`_ensure_web_audit_events_schema`, Phase A0)
- [x] TASK-0073: `record_audit_event(conn, *, actor, action, resource_type, resource_id, change_json, masked_fields, target_account_id)` dispatcher 가 동작 + `AGENT_AUDIT_ENABLED=0` 시 silent no-op (Phase A1)
- [x] TASK-0073: prod (`AGENT_MODE != dev/test`) 에서 `AGENT_AUDIT_ENABLED=1` 아닐 시 module load 시점 `sys.exit(1)` + stderr `[FATAL]` (Phase A1, Codex C5)
- [x] TASK-0073: `bin/verify-completion.sh check_11_audit_dispatcher` 가 `record_audit_event` / `AGENT_AUDIT_ENABLED` / `_enforce_audit_prod_gate` 3 symbol 강제 (Phase A1, Eng E7 SPOF guard)
- [x] TASK-0073: `WebAccountActivity` (TASK-0072) → `WebAuditEvents` migration helper idempotent (`RequestId='account-activity:<id>'` marker, Phase A2)
- [x] TASK-0073: `_log_search_activity()` 의 signature transparent + dual write (legacy + new dispatcher mirror, Phase A2)
- [x] TASK-0073: `PERMISSION_DEFINITIONS` 에 `audit.read.own` / `audit.read.any` / `audit.export` / `audit.purge` 4 코드 추가 + permission group `audit` (Phase A3)
- [x] TASK-0073: admin/operator/sales/dba/pending 5 role 의 audit 권한 catchup loop (Phase A3, Eng E9 dba 보강)
- [x] TASK-0073: 5 audit read endpoint 동작 (`GET /api/admin/audits` + detail + export.csv + actors facet + resources facet) — `.own` SQL filter Actor OR Target (Phase A4, Eng E1 B)
- [x] TASK-0073: `POST /api/admin/audits/purge` chunked PK loop + idempotency_key + 30s deadline + start/complete self-audit row (Phase A4, Eng E8)
- [x] TASK-0073: `build_audit_change_json(action, ...)` 16 ActionCode builder allowlist + unknown action raise (Phase A5, Codex C6)
- [x] TASK-0073: admin 11 mutation endpoint Same tx audit hook (PATCH/DELETE accounts + password-reset + roles CRUD + products CRUD + databases.update + system-prompts) + audit 실패 = caller rollback + 500 (Phase A5)
- [x] TASK-0073: user 5 endpoint fail-open audit (`/api/ask`, share create / revoke / public view (anonymous) / fork) + audit 실패 = stderr only, main flow 진행 (Phase A6)
- [x] TASK-0073: anonymous share view audit (`ActorType="anonymous"` + ActorAccountId NULL + token_prefix 8 char, Phase A6, Eng E4)
- [x] TASK-0073: `tests/test_audit_dispatcher.py` 7 시나리오 + `test_audit_rbac.py` 10 시나리오 + `test_audit_migration.py` 3 시나리오 신설 (Phase B). 실 실행은 컨테이너 가동 후 사용자 위임
- [x] TASK-0073: Frontend admin "감사 로그" 탭 + filter row 7 항목 + list-detail + CSV export gated + admin.js renderAuditList/Detail + HTML escape + cache-bust `v=20260519-audit-tab` (Phase C)
- [x] TASK-0073: app.js + admin.js `PERMISSION_GROUP_ORDER` 에 'audit' 그룹 추가 + ADMIN/WORK_SCREEN_PERMISSION_SECTIONS manage section 합류 (Phase C)
- [x] TASK-0073: `docs/SECURITY.md §9` (Audit subsystem 정책 + Sensitive field catalog source-of-truth) + `docs/DECISIONS.md ADR-0019` + `docs/ARCHITECTURE.md §4·§6` + `docs/CONVENTIONS.md §10.6` audit group + `docs/STATUS.md` feature-0003 row + REPORT.md §1 + TEST.md §2.1 (Phase D)
- [x] TASK-0073: `make web` 재배포 후 audit endpoint 8 시나리오 smoke 검증 PASS (Phase E 본 cycle 2026-05-20). admin.role.create → audit row delta=1 / ChangeJson allowlist 정합 / detail / export.csv (Content-Type text/csv + Content-Disposition) / actors facet (bootstrap_admin) / resources facet (conversation + role) / purge dry_run / anonymous share view ActorType='anonymous' (token_prefix `Wp45TbFK`, view_count_after=2, masked share.token_full) 모두 PASS. routing 회귀 1 건 (`/{event_id}` 가 정적 sibling 가로채기) 발견 + 동일 cycle hotfix (CHG-20260520-0001).
- [x] TASK-0073: WebAccountActivity → WebAuditEvents migration 검증 PASS — `SELECT COUNT(*) FROM WebAuditEvents WHERE RequestId LIKE 'account-activity:%'` = 68 row (legacy 전부 transform, idempotent marker).
- [x] TASK-0073: `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` 환경에서 컨테이너 시작 시 process 종료 + stderr `[FATAL]` 검증 — **TASK-0092 (REQ-20260520-0007, Minor §12.3) 에서 완료**. 7 vector matrix (V1~V7) 의 V1-V3 fail-closed scenario 가 정확히 본 acceptance 충족. `docker run --entrypoint python --no-deps` + `import web.app` + stderr `[FATAL]` 3 substring 검증 PASS. 본 closure 는 TASK-0099 (audit followup backlog tracker hygiene) cycle 에서 수행 (2026-05-22).
- [ ] TASK-0044: 사업팀 pilot 계정(placeholder `<< pilot_username_1..N >>`) 이 admin 콘솔에서 발급된다 — 코드 auto-create 없음, 발급 절차는 본 TASK 기술부 마지막 runbook 문단 참조
- [ ] TASK-0044: 사업팀 pilot 계정으로 로그인해 단순 조회 prompt(예: "대표 아이템 X 가 몬스터 Y 에 연결돼 있나요?") 에 문장형 응답을 받는다
- [ ] TASK-0044: 사업팀 pilot 계정으로 집계 prompt(예: "최근 7 일 레벨별 유저 수") 에 결과셋 표 응답을 받는다
- [ ] TASK-0044: 사업팀 pilot 계정으로 ad-hoc 분석 prompt(예: "유저가 왜 이탈하는지 분석해줘") 에 "DBA 팀으로 요청 이관이 필요합니다" 안내가 응답되고 대화가 그 턴에서 종료된다

### TASK-0044 pilot onboarding runbook (2026-04-23)
사업팀 pilot 발급·서빙을 위한 관리자 운용 절차. 본 TASK 의 코드 변경은 infra 만 제공하며, 실제 account/Product 매핑은 admin 이 수동 수행한다.

1. **사업팀 pilot 계정 발급** (`.env.example` 의 `WEB_PILOT_SALES_USERNAMES` placeholder 참조)
   1. admin 계정으로 로그인 → 관리 콘솔 `계정 (Accounts)` 탭 → `신규 계정` 으로 3~5 명 발급.
   2. 각 계정의 Role 드롭다운에서 `사업팀 (sales)` 을 선택하고 commit bar 의 `모두 적용` 을 누른다.
   3. 초기 비밀번호는 pilot 에게 안전한 채널(사내 1:1 메신저 등) 로 공유하고 본인이 첫 로그인 시 교체하도록 안내한다.

2. **사업팀 전용 Product whitelist 구성 (권장안 2 가지 중 조직 정책에 맞춰 선택)**
   - **옵션 A — KR Product 에서 `dbauth` 를 제외**: 관리 콘솔 `상품 (Products)` 탭 → KR 선택 → 접근 DB chip 에서 `dbauth` 제거 → 저장. 주의: DBA 운영 계정도 KR 을 쓰면 영향. DBA 가 `dbauth` 직접 조회 필요 시 별도 Product 로 분리해야 한다.
   - **옵션 B — 사업팀 전용 Product `KR-Sales` 신규 생성** (권장): 관리 콘솔 `상품 (Products)` 탭 → `신규 상품` 으로 ProductKey=`KR-Sales` / Name=`Korea Sales` 를 생성 → 접근 DB chip 을 `dbgame,dblog` 로 지정. 사업팀 pilot 은 새 대화 시 이 Product 를 명시적으로 선택하거나, `/api/new_conversation` body 의 `product_id` 로 기본값을 지정한다.

3. **복제 DB 접속 정보 등록**
   1. 복제 인스턴스가 이미 가동 중이면 `.env` 에 `REPLICA_DB_HOST=<host>` / `REPLICA_DB_PORT=<port>` / `REPLICA_DB_USER=<user>` / `REPLICA_DB_PASSWORD=<password>` 를 기입 (quote 는 mysql.connector 인자이므로 bash-safe 처리 필요).
   2. `docker compose up -d --force-recreate agent web insight-worker` 로 재기동하면 data-plane 쿼리가 복제로 라우팅된다. memory DB 는 계속 primary.
   3. 수동 sanity check: `docker compose exec agent python -c "from modules.db import connect; c=connect(database='dbgame'); cur=c.cursor(); cur.execute('SELECT 1'); print(cur.fetchall())"` → `[(1,)]` 출력 + 필요시 `mysql -h $REPLICA_DB_HOST -P $REPLICA_DB_PORT -u $REPLICA_DB_USER -p -e 'SELECT 1'` 으로 직접 접속.
   4. 복제 인스턴스가 아직 없으면 3.1~3.3 은 후속 작업이며, `.env` 의 REPLICA_DB_* 를 비워 두면 기존 primary 경로가 그대로 동작한다 (사업팀 pilot 테스트 자체는 복제 없이 가능).

4. **사업팀 prompt 튜닝 (선택)**: 관리 콘솔 `역할 (Roles)` 탭 → `사업팀` 선택 → Role scope prompt 편집기 → Product 드롭다운(`(전 Product 공통)` 또는 특정 Product) 선택 후 초안을 수정. 저장 시 `WebSystemPrompts` 의 해당 scope row 가 업데이트되고 다음 `/api/ask` 부터 새 가이던스가 즉시 적용된다.

### Phase Composer Model Selector (feature-0008, 2026-05-22)
- [x] DOM: composer-box 의 attach-btn → `+` (composer-actions-btn) + primary
      popup (#composerActionsMenu) + secondary popup (#composerModelMenu).
- [x] JS: state.modelCatalog + state.selectedModel 신규. dead vault code 161
      줄 일괄 정리. `+` dropdown handlers (binding / open/close / model item
      render / sendPrompt fallback chain).
- [x] CSS: .composer-actions-btn / .composer-actions-menu / .composer-actions-item
      / .composer-model-menu / .composer-model-item* + 반응형 fallback.
- [x] cache-bust: v=20260522-composer-model-selector.

### AR-M5-impl web hotfix — PG cutover MySQL 잔존 쿼리 차단 (2026-05-27)
- [x] `_last_step_at_for_run()`: `AGENT_RUNTIME_READ_BACKEND=postgres` 시 `agent_runtime.steps` 쿼리로 전환 — MySQL `AgentMemorySteps` 직접 의존 제거 (CHG-20260527-0001).

### TASK-0121 — AR-M5 PG cutover 잔존 MySQL 쿼리 차단 (2026-05-27)
- [x] `_load_latest_assistant_message`: PG `agent_runtime.messages` 경로 추가 + MySQL fallback 유지
- [x] commit + push + main ff-merge

### TASK-0122 — 외부 LLM 수신 동의 UI·권한·로직 제거 (2026-05-28)
- [x] REQ-20260528-0122 (**Minor** §12.3 — 사용자 프로필 > 보안 및 계정 > 외부 LLM 수신 동의 섹션 전면 제거. 서비스 사용 = 묵시 동의로 간주). `index.html` `profileConsentSection` DOM 제거. `app.js` `_CONSENT_PROVIDERS` / `_CONSENT_GROUPS` / `_consentRowsCache` / `_isConsentGroupGranted` / `_loadConsentRows` / `_renderConsentSectionMarkup` / `_renderConsentSection` / `_handleConsentToggle` / `_bindConsentSectionEvents` 함수·변수 전체 제거 + `openProfile` 내 렌더링 호출 + 이벤트 바인딩 제거. `styles.css` `.consent-providers` / `.consent-provider-block` 등 consent CSS 블록 제거. `app.py` `_ensure_web_account_consents_schema` 함수·호출 2곳 제거 / `_has_active_consent` 함수 제거 / `_prepare_vision_inline_images` D11 consent gate 분기 + 409 응답 제거 (vision pre-fetch D13 로직 보존, 반환 4-tuple → 3-tuple) / `GET|POST /api/account/consents`, `DELETE /api/account/consents/{id}` 3 엔드포인트 제거 / `attachment.consent.grant|revoke` audit 핸들러 제거 / `_model_to_consent_provider` → `_model_to_llm_provider` 이름 변경 (audit 용도 유지). py_compile + node --check PASS. DB schema (`WebAccountConsents`) 는 기존 데이터 보존 목적으로 DROP 안 함 — 신규 row 추가만 없어지는 것.
- [x] commit + push + main merge

### TASK-0123 — UX 2차 보완 7개 항목 구현 (2026-05-28)
- [x] REQ-20260528-0123 (**Minor** §12.3 — frontend-only UX 보완, backend / RBAC / DB schema / endpoint contract 무변경). 7개 항목 일괄 구현: **(1) 입력창 높이 일치** — `.composer-box` padding `9px→7px` 로 축소 (프로필 버튼 48px = composer textarea 34px + padding 7×2, 정렬 맞춤). **(2) 파일 즉시 업로드 + ingest 병렬** — `_uploadComposerAttachment()` lazy 분기 완전 재작성: staged 방식 대신 파일 선택 즉시 `/api/new_conversation` 호출로 cid 발급 + 업로드 실행 + `state.composerAttachments.lazyConvCreating` 경쟁 방지 플래그 추가. 대화 목록에 임시 "(파일 첨부 중)" 항목 추가 + 렌더 갱신. **(3) 말풍선 첨부파일 표시** — 업로드 응답의 `signed_url` 을 bucket item 에 보존 + `_sendAttachmentSnapshot` 에 `signed_url` 포함 + `refreshWorkspace()` 후 `lastUserMsg._attachments = _sendAttachmentSnapshot` 재주입 (loadHistory 로 attachments 필드 소실 방지). **(4) 첨부파일 다운로드** — 말풍선 attach chip 에 `signed_url` 존재 시 `has-download` class + click 핸들러 (presigned GET 다운로드). styles.css 에 `.attach-chip-dl` + hover 효과 추가. **(5) 공유뷰 CSV 다운로드** — `share.js` 에 `downloadRowsAsCsv()` helper (BOM UTF-8, RFC4180 escape) + `renderAssistantDetails()` 내 SQL 결과표 하단에 "CSV 다운로드" 버튼 추가. `share.css` 에 `.share-csv-download-btn` 스타일. (공유뷰 file attachment 는 backend 가 permission-gated 로 숨김 — SQL 결과 CSV 로 대체). **(6) LLM step/thinking 표시** — `renderProgress()` 내 `progressCardEl.open = true` + `renderPendingAssistantBubble()` 의 `<details>` step 항목 `detailsEl.open = true` (step 도착 즉시 자동 펼침). **(7) 첫 대화 상태 dot 갱신** — `sendPrompt()` 의 lazy-create 성공 path 에서 `startProgressPolling` 직전 `state.conversations` 에 신규 conv 최소 항목 추가 + `renderConversationList()` 호출 → polling 첫 tick 에서 DOM 요소가 존재해 dot 갱신 가능. node --check PASS. worktree `ux-compact-redesign` (branch `ai/root/ux-compact-redesign`), commit `095f9b1`.
- [x] docker cp 배포 (repo-web-1:/app/web/static/ — app.js, share.js, share.css, styles.css)

### TASK-0167 — 대화 분기·공유 cutover 회귀 수정 (2026-06-09)
- [x] **Major §12.3** — fork/share/duplicate/public-share-view 가 2026-05-27 MySQL→PG cutover 후 DROP 된 `AgentCoreConversations`/`AgentMemoryMessages`/`AgentMemoryKv` 를 raw MySQL 로 조회해 HTTP 500 (`Table 'agent_memory.agentmemorymessages' doesn't exist`). `/api/history`(`_list_conversations_pg`) 등 정상 endpoint 와 동일하게 `AGENT_RUNTIME_READ_BACKEND=postgres` 분기 + `_pg_connect()` 로 PG(`agent_runtime.*`) 라우팅. (CHG-20260609-FORK-SHARE-PG-CUTOVER) — CHG-20260527-ASK-STATUS-PG 의 형제 회귀.
- [x] backend-aware helper 10종 신설: `_runtime_backend_is_pg` / `_meta_json_to_dict` / `_conv_load_topic` / `_conv_load_product` / `_conv_load_messages_raw` / `_conv_message_exists` / `_conv_update_topic_product` / `_conv_update_topic` / `_conv_copy_messages` / `_conv_load_share_meta`.
- [x] `_fork_conversation_impl` / `_share_anchor_belongs_to_conversation` / `_share_load_messages` / `public_share_view`(cross-DB merge: core_conversations PG + WebProducts/WebAccounts MySQL) / `duplicate_conversation` 라우팅.
- [x] jsonb meta_json: PG read=dict 정규화, insert=`%s::jsonb` 캐스트. MySQL else 분기는 비-postgres 배포용 legacy fallback 보존.
- [x] 회귀 e2e `tests/test_fork_share_cutover.py` (T1~T5 — fork/share(full)/public-view(anon)/duplicate/share(anchored), 500 미발생 단언) + py_compile PASS.
- [x] outside-voice panel(SUBAGENT SHIP, REV-20260609-0001) → REVIEW.md / PR #126 → main 머지(2e89ac3) → web 재배포 → 라이브 e2e 5/5 PASS

### TASK-0168 — 공유뷰 follow-up: error contract + redaction 회귀 가드 (2026-06-09)
- [x] **Minor §12.3** — TASK-0167 outside-voice(REV-20260609-0001) 권고 F1·F2 처리. 성공경로·RBAC·스키마·계약 무변경(방어적 에러처리 + 테스트). (CHG-20260609-SHARE-ERRCONTRACT)
- [x] **F1** `public_share_view`: 데이터 로드(`_conv_load_share_meta`/`_share_load_messages` PG read) 실패 시 bare 500 대신 graceful JSON 500(`"공유 대화를 불러오지 못했습니다."`) — fork 의 명시 500 래핑과 대칭. ViewCount++(revoke race 가드 겸용)는 보존, 실패 시 1 과대카운트는 허용 soft-metric 오차로 주석화.
- [x] **F2** `tests/test_share_redaction_invariant.py`: `_pg_connect` mock 으로 **PG dict-meta 경로**를 결정적 재현 → attachment_derived redact(stale/null token) + internal 메시지 필터 + 정상 본문 보존 + 정책 version gate(CURRENT=비redact) 단언. 컨테이너 in-process 3/3 PASS.
- [ ] py_compile / verify-completion / PR → main 머지 → 재배포 → 라이브 e2e(양 테스트 green)

### TASK-0170 — Fork 문맥 복원: core_messages 복사 (하이브리드 Phase 1) (2026-06-09)
- [x] **Major §12.3** — fork/duplicate/공유-fork 본에서 어시스턴트가 이전 문맥을 인지 못 하던 버그. 원인: LLM 문맥은 `agent_runtime.core_messages`(agent_core `_load_conversation_messages`)에서 읽는데 fork 는 표시 메시지(`messages`)만 복사하고 `core_messages` 미복사 → 복사본 core_messages 가 비어 문맥 0. (CHG-20260609-FORK-CORE-CONTEXT)
- [x] 설계: git식 reference 아키텍처 검토(`DESIGN-fork-reference.md`) → outside-voice(REV-20260609-0003) BLOCKER 2 + 보안 안티패턴 3 발견 → **하이브리드 확정**(ADR-WEB-0005). 사용자 결정.
- [x] **Phase 1 구현**: `_conv_load_core_messages_raw`/`_conv_copy_core_messages`(PG 전용, tool_calls jsonb 보존) 추가 + `_fork_conversation_impl` 에 배선. anchored fork=앵커 created_at 까지, full/duplicate=전체. 교차계정 공유 fork 도 snapshot(상시 cross-tenant 흐름 0). core 복사 실패 시 fork 통째 cleanup(fail-loud, 반쪽 fork 금지). 응답에 `core_copied` 노출.
- [x] 회귀 테스트 `tests/test_fork_share_cutover.py` T1b 추가(copied>0 이면 core_copied>0 — 문맥 복사 단언). py_compile PASS.
- [ ] **Phase 2 (후속 cycle)**: 첨부 — 행 복사(동일 ObjectKey)+로컬 sandbox 스키마 복제+동일소유자 blob 참조. IDOR 게이트 변경 시 outside-voice.
- [ ] verify-completion / PR → main 머지 → 재배포 → 라이브 e2e(T1b green)

### TASK-0171 — Fork 첨부 복사 (하이브리드 Phase 2) (2026-06-09)
- [x] **Major §12.3** — fork 본에서 사용자가 원본 첨부 파일을 볼 수 없던 문제(TASK-0167/0170 은 messages/core_messages 만 복사). ADR-WEB-0005 Phase 2. (CHG-20260609-FORK-ATTACHMENTS)
- [x] **구현**: `_copy_conversation_attachments`(WebConversationAttachments 행을 새 ConversationId+fork AccountId 로 복사 + blob **독립 복사**(get+put 새 ObjectKey — refcount 위험 회피, server-side copy 부재)) + `_fork_conversation_impl` 배선. CSV/XLSX 는 `_ingest_attachment_background` 로 **fork 전용 sandbox 재적재**(조상 스키마 공유 금지). per-attachment fail-open. 응답 `attachments_copied`. IDOR 게이트 무변경(fork 가 자기 행 소유).
- [x] **outside-voice(REV-20260609-0004) FIX-FIRST 반영**: #2 orphan blob → **INSERT 먼저→put→실패 시 행 보상삭제**(업로드 패턴). #6 quota 우회 → 복사 전 `_check_attachment_size_caps`(per-file/conv/account) 검사·초과분 skip. #5 audit → `share.fork` ctx 에 `attachments_copied`/`core_messages_copied` 추가(교차계정 forensics). #7 → 테스트 robust 화(⊆+count).
- [x] 라이브 검증 테스트 `tests/test_fork_attachments.py`(A1~A4: copied 수·시그니처⊆·독립 id·signed_url). py_compile PASS.
- [ ] verify-completion / PR → main 머지 → 재배포 → 라이브 e2e(A1~A4 green)

### TASK-0173 — 실행 단계 "근거(reason)" 사용자 노출 (frontend-only) (2026-06-09)
- [x] **Minor §12.3** — assistant 답변 시 각 실행 단계의 수행 근거가 화면에 안 나와 사용자가 작업의 합리성을 확인 불가. `reason` 데이터는 end-to-end 정상(LLM tool_notes → `agent_runtime.steps.reason_text` → `/api/progress`)인데 프런트가 과거 "TMI 개선"으로 step 사이드 패널에서 reason 을 hover 툴팁(`item.title`)에만 넣고 `.step-reason{display:none}` 으로 숨긴 게 근본. (CHG-20260609-0173)
- [x] `buildStepDetailEl` 에 `.step-reason`(라벨 "근거" pill + 텍스트) 인라인 렌더링 추가 — step 사이드 패널 전 단계가 근거 표시.
- [x] `_renderStepSidePanelBody` 중복 `item.title` 제거 + `buildSqlStepPanel`(완료 상세 SQL 단계)에 동일 reason 추가(일관성 — non-SQL 단계는 `buildStepBlocks` 가 이미 `work — reason` 표시 중이었음). styles.css `.step-reason` 가시 스타일 복원 + 캐시버스터 bump.
- [x] node --check app.js PASS. RBAC/스키마/엔드포인트/시크릿/백엔드 무변경. outside-voice [SKIPPED:frontend-only] (REV-20260609-0173).
- [ ] verify-completion / PR → main 머지 → 재배포 → Windows-browser(PB-0008) 시각 검증

### TASK-0174 — 미리보기 인라인 로더 방어 가드 (2026-06-09)
- [x] `loadCsvAsInlineTable` 값 기반 방어 가드 + `distinctiveValueTokens` 헬퍼 (CHG-20260609-PREVIEW-CSV-GUARD)
- [x] §18.8 패널 JS 오탐 지적 반영 (previewTokens≥2 임계)
- [x] verify-completion → main ff-merge(2b4da2a) → 재배포(web) → PB-0008 Windows-browser 무회귀 확인 (TEST.md §4 2026-06-09 TASK-0174 항목)

### TASK-0184 — LLM 사용량 계정 drill-down + 프로필 사용 내역 차트 + 내 활동기록 제거 (2026-06-10)
- [x] **Minor §12.3** (조회 UI 전용, RBAC·스키마 무변경) — 3건: (A) 관리 콘솔 LLM 사용량의 **계정별 차트가 계정 증가 시 과다 길이/탐색난** → 역할 drill-down(역할 막대 클릭 시 그 역할 계정만 검색·Top-N 페이징으로 펼침, 기본 접힘)으로 대체. (B) 프로필에 **'사용 내역' 탭**(본인 LLM 토큰/모델/요청 간소 차트) 신설. (C) 의도치 않게 노출된 **'내 활동 기록' 탭 제거**. (CHG-20260610-0184)
- [x] **(A)** admin.html 계정별 독립 차트(usageAccountChart/CostChart) → drill 패널(계정 검색 input + page size select + 이전/다음). admin.js `renderStackedHBar` 에 `onRowClick` 추가(역할 토큰/비용 막대 클릭) + `toggleAccountDrill`/`renderAccountDrill`(loadUsage 클로저, byAccount 캐시·역할 키 매칭은 백엔드 `_aggregate_usage_by_role` 와 동일) + 컨트롤 바인딩. 역할별 차트는 불변(종류 적어 무관).
- [x] **(B)** 신규 `GET /api/profile/usage`(app.py `profile_llm_usage`) — `admin_llm_usage`(console.usage.read, admin) 의 본인-범위 축소판(owner_account_id=로그인 계정 강제, INNER JOIN, 추정 비용·역할 enrich 제외). **별도 RBAC 권한 없이 로그인만**(본인 소유 대화 usage 한정 → 권한 카탈로그 무변경). index.html '사용 내역' 탭 + app.js `loadProfileUsage`/미니 SVG 차트(모델별 stacked 세로막대·donut, `<title>` 툴팁) + profile-usage 스타일.
- [x] **(C)** index.html audits 탭/패널 제거, app.js `loadProfileAudits`·renderProfile 권한 게이트·탭 핸들러 제거. 엔드포인트 `/api/profile/audits` 는 호출처 없이 잔존(UI 비노출, 백엔드 게이트 유지).
- [x] make test(컨테이너 pytest+ruff) exit=0 / node --check(app.js·admin.js) / py_compile(app.py) PASS. outside-voice [SKIPPED:RBAC·스키마 무변경, 조회 UI 전용].
- [x] verify-completion PASS → main ff-merge(0181301) → 재배포(web, healthz `git_commit=0181301`) → PB-0008 Windows-browser 시각 검증 **PASS**(drill-down · 프로필 차트 · 활동기록 비노출, TEST.md §4 2026-06-10)
- [x] (후속 보강) 사용자 지적 "계정별 비용 차트 누락" — drill 패널을 [토큰 | 비용] 2열로 재구성(`usageDrillCostChart` 추가), 역할별 차트와 일관. 백엔드 무변경(by_account 의 `cost_usd` 재사용). CHG-20260610-0184-COSTCHART, REV-20260610-0185. 재배포 + PB-0008 재검증.

### TASK-0186 — 단계 사이드 패널: 결과 표 렌더링 + 패널 리사이즈 (frontend-only) (2026-06-10)
- [x] **Minor §12.3** — 사용자 지적: `단계 보기(N)` 사이드 패널 확장 시 결과가 표가 아닌 raw 마크다운 텍스트로 나옴 + 패널 크기 조절 불가. (CHG-20260610-0186)
- [x] 표: `buildStepDetailEl` 결과 블록이 `result_summary.preview_table`(이미 step 데이터에 포함) 있으면 기존 `buildResultTable` 로 HTML 표 렌더, 없으면 `<pre>` 폴백. 백엔드 무변경.
- [x] 리사이즈: 좌측 드래그 핸들(`#stepSidePanelResizer`) + `setupStepSidePanelResize`(너비=innerWidth−clientX, clamp[300,92vw], localStorage 영속, mouse+touch) + open 시 저장 너비 복원. styles.css min/max-width·핸들·is-resizing.
- [x] node --check app.js PASS. RBAC/스키마/엔드포인트/백엔드 무변경. outside-voice [SKIPPED:frontend-only] (REV-20260610-0186).
- [x] verify-completion → main ff-merge(76b64a2) → web 재배포(healthz `git_commit=76b64a2`, 3종 PASS) → 데이터 경로 확인(`/api/progress` step11 execute_sql `preview_table` 존재)
- [x] **후속(CHG-0186-MDTABLE)**: `execute_sql` 만 `preview_table` 보유, `get_sample_rows`/`describe_table` 등은 markdown 표 **문자열**만 가져 여전히 raw 노출(사용자 스크린샷 케이스). `parseMarkdownTablePreview` 추가 + buildStepDetailEl 우선순위 ②로 배선 → 전 도구 표 렌더. node --check + 파서 자가 테스트 PASS. REV-20260610-0187.
- [ ] (후속) verify-completion → main ff-merge → web 재배포 → PB-0008 Windows-browser 시각 검증(전 도구 표 렌더 · 리사이즈)

### TASK-0189 — 날짜기준표 캘린더 "대화 구간 이동" 기능 복구 (AR-M5 cutover 라우팅 누락) (2026-06-10)
- [x] **Minor §12.3** (백엔드 읽기경로 라우팅, RBAC·스키마·파괴 0) — 메시지 날짜 분기선 클릭 시 열리는 캘린더에서 날짜/시각을 골라 해당 대화 구간으로 점프하는 기능이 동작하지 않음(누락). (CHG-20260610-0189)
- [x] **근본 원인**: AR-M5 cutover 로 메시지 정본이 MySQL `AgentMemoryMessages` → PG `agent_runtime.messages` 로 이전되며 MySQL 테이블이 DROP. 메시지 목록 경로(`_get_history`)·`_load_latest_assistant_message` 는 `AGENT_RUNTIME_READ_BACKEND` 로 PG 라우팅되도록 이전됐지만, **캘린더를 떠받치는 두 엔드포인트(`/api/history_dates`, `/api/history_anchor`)만 이전에서 누락**돼 삭제된 MySQL 테이블을 직접 조회 → `history_dates` 는 except 폴백으로 항상 빈 `dates`(=클릭 가능한 날짜 없음), `history_anchor` 는 500/미스. 프런트(app.js) 캘린더 로직은 정상이었음.
- [x] **수정** ([src/app.py](../src/app.py)): 두 엔드포인트에 `_get_history` 와 동일한 `AGENT_RUNTIME_READ_BACKEND == "postgres"` 게이트로 PG `agent_runtime.messages` 조회 분기 추가(legacy MySQL 경로는 else 로 유지). `history_anchor` 가 반환하는 `message_id` 는 `_get_history` 가 DOM 에 부여한 PG id(`message-<id>`)와 동일 id-space 라 점프 타겟 매칭. 두 엔드포인트 모두 `to_char(created_at, …)`(세션 tz) wall-clock 기준으로 통일 → 시각 라벨과 점프 매칭이 상호 일관(원본 MySQL wall-clock 비교 의미 보존, timestamptz cast tz 모호성 회피).
- [x] **회귀 테스트** `tests/test_history_calendar_pg_routing.py`(T1 history_dates PG 라우팅 + 삭제된 MySQL 테이블 미접촉 가드, T2 history_anchor PG id 반환, T3 legacy MySQL back-compat). make test(컨테이너 pytest+ruff) exit=0(feature-0002+0003 전체 회귀 0), ruff app.py clean.
- [x] outside-voice 적대적 백엔드/QA 검토(cutover 영역 취약성) — REV-20260610-0189.
- [x] verify-completion PASS → main rebase(동시세션 TASK-0188 40f75ba 위)·ff-merge → web 재배포(healthz `git_commit` 확인) → **라이브 인증 API 검증**: `/api/history_dates` 실제 날짜/시각 반환(이전 빈 `{}`), `/api/history_anchor` 유효 PG id 반환.
- [x] **후속 정밀화(CHG-0189 분 단위)**: 라이브 검증 중 anchor 가 초 단위 `<=`(`HH24:MI:SS <= ...:00`)라 클릭한 분의 메시지(초>0)가 제외돼 직전 메시지로 점프하는 결함 발견(원본 MySQL 결함 계승). `to_char(...,'YYYY-MM-DD HH24:MI') <= left(at,16)` 분 단위 비교로 교체 → 클릭한 분의 메시지에 정확 착지. 사용자 "정상적으로 작동" 요청 충족. 재배포·라이브 재검증.
- [x] **근본원인 형제 인스턴스 스윕·수정(CHG-0189-SUGGESTIONS)**: 같은 결함 class(엔드포인트가 게이트 없이 삭제된 MySQL 테이블 직접 조회) 자동 스윕 결과 `/api/suggestions`(입력 추천) 1건 추가 발견 — 라이브 **HTTP 500**(`SELECT Content FROM AgentMemoryMessages …` try/except 없음). 동일 패턴으로 PG `agent_runtime.messages` 라우팅 + fail-soft(예외→빈 items) 수정. 회귀 테스트 T4. 사용자 "누락 원인 파악" 요청에 대한 근본원인(미이전 엔드포인트) 포괄 대응. 재배포·라이브 200 검증.
- [ ] (잔존) Windows-browser(PB-0008) 시각 검증(분기선→캘린더→날짜/시각 클릭→해당 메시지로 스크롤·하이라이트) — CHECK#13 WARN, 사용자 확인용.

### TASK-0196 — AR-M5 cutover 잔존 라우팅 누락 일괄 복구 (web 3건) (2026-06-10)
- [x] **Minor §12.3** (백엔드 읽기/쓰기경로 라우팅, RBAC·스키마·파괴 0) — 사용자 요청("mysql→PG 이관 미완으로 작동 안 하는 부분 검토"). TASK-0189 와 동일 결함 class 를 전 서비스 프로그램적 스윕(삭제 확정 테이블을 게이트 없이 조회하는 함수 추출) + 정적·라이브 검증으로 4건 확정, web 3건을 본 TASK 에서 복구. (CHG-20260610-0196)
- [x] **#1 대화 제목 변경** `PATCH /api/conversations/{id}/title` — `rename_conversation_title` 가 `UPDATE AgentCoreConversations` 직접 → 삭제된 테이블이라 **라이브 500**(재현 확인). 이미 PG 라우팅된 게이트 헬퍼 `_conv_update_topic`(PG `agent_runtime.core_conversations`) 재사용으로 교체 + try/except→500.
- [x] **#2 관리자 제품 삭제** `DELETE /api/admin/products/{id}` — `admin_delete_product` 의 참조 가드 `SELECT COUNT(*) FROM AgentCoreConversations WHERE product_id` → **라이브 500**(재현 확인). `_runtime_backend_is_pg()` 분기로 PG `agent_runtime.core_conversations` COUNT 라우팅(legacy MySQL else). 후속 Web* 삭제 트랜잭션 영향 없음.
- [x] **#3 검색 결과 발췌문** — `_collect_matched_excerpts` 가 `AgentMemoryMessages UNION AgentCoreMessages` → except→{} 로 검색 스니펫(본문 미리보기) **항상 빈칸**. PG `agent_runtime.messages` UNION `core_messages`(ROW_NUMBER, ILIKE ESCAPE — MySQL case-insensitive 패리티) 분기 추가. 후처리(발췌 클리핑)는 DB 무관.
- [x] **오탐 확인**: `_load_schema_list`/`_load_relevant_table_insights`(AGENT_KB_READ_BACKEND=postgres 게이트, MySQL 죽은 폴백), `agent_core._list_conversations`(caller `_read_runtime_pg` 우선), docstring 언급·information_schema 진단.
- [x] 회귀 테스트 `tests/test_cutover_routing_gaps.py`(T1 excerpts PG 라우팅+삭제 테이블 미접촉, T2 `_conv_update_topic`(rename 위임) PG UPDATE). make test(컨테이너 pytest+ruff) exit=0(0002+0003 전체 회귀 0).
- [x] outside-voice 적대적 백엔드/QA 검토 — REV-20260610-0196.
- [ ] verify-completion → main ff-merge → web 재배포(healthz `git_commit`) → 라이브 재검증(#1·#2 200, #3 발췌 비어있지 않음). (#4 convo_search 는 agent-core, feature-0002 TASK-0196 참조.)

### TASK-0200 — cutover 복구 MINOR 하드닝: 검색 발췌 정렬 교정 (2026-06-10)
- [x] **Minor §12.3** (읽기경로 정렬, RBAC·스키마·계약 무변경) — REV-20260610-0196 이 지적한 MINOR 잔존(수용 항목)의 실행. `_collect_matched_excerpts` 의 conv 별 "가장 최근 매칭" 선택이 `ORDER BY msg_id DESC` 였는데, `agent_runtime.messages.id` 와 `core_messages.id` 가 독립 IDENTITY 시퀀스라 cross-table 비교가 시간순과 어긋날 수 있었다(발췌 스니펫만 영향). 두 table 공통 `created_at` 기준 `ORDER BY created_at DESC` 로 교정(PG+MySQL legacy 양 분기 + docstring). (CHG-20260610-0200) (#1 convo_search escaping 은 agent-core, feature-0002 TASK-0200.)
- [x] 회귀 가드: `tests/test_cutover_routing_gaps.py` T1 에 `ORDER BY created_at DESC` 존재 + `msg_id` 정렬 부재 단언 추가. make test exit=0(0002+0003 전체 회귀 0), ruff clean.
- [x] outside-voice [SKIPPED:minor-ordering-implements-REV-0196] (REV-20260610-0200).
- [ ] verify-completion → main ff-merge → web 재배포 → 라이브 발췌 정렬 확인.

### TASK-0202 — LLM 사용량 "모델별" 카드 전환 애니메이션 + 비선택 dim/접힘 (frontend-only) (2026-06-10)
- [x] **Minor §12.3** (조회 UI 전용 — RBAC·스키마·엔드포인트·백엔드 0) — 사용자 요청: `관리 콘솔 > 감사 > LLM 사용량` "모델별"에서 모델 전환 시 선택 모델 외 카드가 즉시 사라져 불편. 모델 전환에 부드러운 애니메이션 + 비선택은 흐리게 유지하다 마우스가 영역을 벗어나면 부드럽게 사라지게. (CHG-20260610-0202)
- [x] **근본 원인**: 모델별 카드(`.admin-usage-mcards`)를 **필터된 `view.by_model`** 로 렌더 → solo 선택 시 비선택 모델이 view 에서 빠져 카드가 DOM 에서 제거(즉시 사라짐). 상단 칩 바(`#usageModelFilter`)는 `_ms` 전체 기준이라 사라지지 않음(사용자가 "문제없다"고 한 부분).
- [x] **수정** ([admin.js](../src/static/admin.js)): 카드를 항상 전체 `data.by_model` 로 렌더(수치는 각 모델 고유값, 선택 무관) + 선택=`is-active`·비선택=`is-dimmed`, 영역에 `is-filtering`. hover 시 비선택 흐리게(opacity .4), 영역 이탈(`:not(:hover)`)시 fade-out → `transitionend(opacity)`로 `display:none` 회수, 재진입(mouseenter)시 reflow fade-in 복구. 칩 바로 필터링(마우스 영역 밖)한 경로는 초기값 opacity:0 라 transition 미발동 → 재렌더 시 hover 아니면 **동기 `display:none`** 회수(REV B1).
- [x] **수정** ([styles.css](../src/static/styles.css)): `.admin-usage-mcard` 에 opacity/transform 트랜지션 + `.is-filtering .is-dimmed{opacity:.4}` + `.is-filtering:not(:hover) .is-dimmed{opacity:0;transform:scale(.92);pointer-events:none}` + `prefers-reduced-motion` 가드.
- [x] outside-voice frontend 적대적 리뷰(REV-20260610-0202) — **B1 BLOCKER(유령 카드)·M1(fade-in pop) 흡수**, M2(grid focused-view 점프)는 "선택 카드만 남기는" 의도로 수용.
- [x] node --check admin.js PASS, styles.css 중괄호 균형. 기존 TASK-0198(칩 바·`buildView`·도넛/일별/역할/계정 차트·상세 표) 회귀 0(전부 `view.*` 유지, 카드만 분리).
- [ ] verify-completion → **base=`ai/claude/0003`(TASK-0198 미병합)** → 0003 main 병합 후 본 브랜치 rebase → ff-merge → web 재배포 → PB-0008 Windows-browser 시각 검증(모델 전환 애니메이션·dim·영역 이탈 시 사라짐·재진입 복구)

### TASK-0204 — LLM 사용량 '모델별' 카드 제거 + 모델 칩 토큰수 제거 (frontend-only) (2026-06-11)
- [x] **Minor §12.3** (조회 UI 전용 — RBAC·스키마·엔드포인트·백엔드 0) — 사용자 피드백: TASK-0202 모델 카드 hover dim/접힘이 실사용 시 시각적으로 불편 + 의도치 않은 동작(클릭 즉시 비선택 카드 사라짐·빈 공간·레이아웃 점프). 사용자 제안대로 '모델별' 카드 그리드를 제거(상단 '모델' 칩 바 + '전체' 가 모델별 분리/선택을 이미 대신) + 칩에서 토큰 개수 제거(모델명만 깔끔). (CHG-20260611-0204)
- [x] **근본 원인(0202 결함)**: 카드 클릭→요약 re-render→새 노드에 `:hover` 미부여→TASK-0202 의 "영역 밖이면 즉시 회수" 로직이 클릭 순간에도 발동→비선택 카드 dim 없이 즉시 `display:none`(원래 불편 그대로 재현). + grid `auto-fill` 빈 트랙→선택 카드 옆 휑한 공백. **라이브 win-browser 재현으로 확인**(02_solo_hover.png: edge 외 3카드 즉시 소실+빈공간).
- [x] **수정** ([admin.js](../src/static/admin.js)): `loadUsage` 요약 렌더에서 `.admin-usage-mcards` 카드 그리드 빌드 + 카드 클릭/hover(transitionend·mouseenter·동기회수) 핸들러 **전부 제거** → `summaryEl.innerHTML = totalsHtml`(합계 카드만). `renderModelFilter` 칩에서 토큰수(`admin-usage-chip-tok`)·`전체` 토큰수 제거(모델명만), 미사용 `tokByKey`/`t` 파라미터 정리.
- [x] **수정** ([styles.css](../src/static/styles.css)): `.admin-usage-mcards*`(TASK-0198 카드 + TASK-0202 dim/접힘/reduced-motion) + `.admin-usage-chip-tok` 규칙 제거(dead). 칩/도넛/차트/표·스코프 라벨·`.admin-usage-empty`(타 차트 사용) CSS 유지.
- [x] node --check admin.js PASS, styles.css 중괄호 균형. 칩 바·`buildView`·도넛/일별/역할/계정 차트·상세 표(모델별 데이터 테이블 포함) 유지=회귀 0. 캐시버스터 `?v=20260611-usage-no-mcards`.
- [x] outside-voice [SKIPPED:frontend-removal-readonly-ui] (REV-20260611-0204) — UI 제거·라벨 정리, 권한·스키마·엔드포인트·백엔드 0.
- [ ] verify-completion → main rebase·ff-merge → web 재배포 → PB-0008 Windows-browser 시각검증(모델별 카드 부재·칩 모델명만·칩 토글 정상)

### TASK-0206 — 답변 내 쿼리 문자열 항상 표시 + 실행결과셋 기본 숨김 토글 (frontend-only) (2026-06-11)
- [x] **Minor §12.3** (프론트엔드 렌더링 전용 — RBAC·스키마·엔드포인트·백엔드 0) — 사용자 피드백: `쿼리 보기` 토글이 실행결과셋이 아닌 쿼리 문자열을 가리는 것은 의도와 반대. 쿼리 문자열은 항상 출력하고, 쿼리 실행결과셋(테이블/미리보기 데이터)을 `결과 보기` 버튼으로 기본 숨김·클릭 시 토글. (CHG-20260611-0206)
- [x] **수정** ([app.js](../src/static/app.js)): ① `collapseSqlCodeBlocksInContent()` — ` ```sql ``` ` 코드블록 숨김 로직 제거(항상 표시). ② `buildSqlStepPanel()` — SQL 블록 항상 표시, 결과 테이블+CSV 액션 영역을 `sql-result-toggle-wrap` + `resultBody(hidden=true)`로 감싸고 `결과 보기/닫기` 토글 적용. ③ `renderMessageDetails()` 구형 fallback — SQL 토글 제거(항상 표시). ④ `buildStepDetailEl()` 사이드 패널 — 결과셋(표/preview)을 `sql-result-toggle-wrap` + `resultBody(hidden=true)`로 감싸고 `결과 보기/닫기` 토글 적용.
- [x] **수정** ([styles.css](../src/static/styles.css)): `.sql-result-toggle-wrap`, `.sql-result-body` 규칙 추가(flex column, gap 6px). 기존 `.sql-toggle-wrap`·`.sql-toggle-btn`·`.sql-result-actions` 유지.
- [x] outside-voice [SKIPPED:frontend-only-rendering-toggle] (REV-20260611-0206) — 렌더링 표시 방향 교정, 권한·스키마·엔드포인트·백엔드 0.
- [x] node --check app.js PASS, verify-completion PASS, PR #142 ff-merge → main 반영. web 재배포 + 라이브 확인(쿼리 항상 표시·결과 보기 토글)은 배포 후 수행.

### TASK-0205 — composer 텍스트박스 Shift+Enter 줄바꿈 지원 (frontend-only) (2026-06-11)
- [x] **Minor §12.3** (keydown 핸들러 1줄, RBAC·스키마·엔드포인트·백엔드 0) — 사용자 요청: 입력 텍스트박스에서 Shift+Enter 를 누르면 줄바꿈이 되도록. sendMode("Enter 전송"/"Ctrl+Enter 전송") 와 무관하게 Shift+Enter 는 항상 줄바꿈. (CHG-20260611-0205)
- [x] **수정** ([app.js](../src/static/app.js)): `promptInputEl keydown` 핸들러에 `if (event.shiftKey) return;` 추가 — Shift+Enter 시 `event.preventDefault()`/`sendPrompt()` 진입 없이 브라우저 기본 줄바꿈 동작 유지.
- [x] outside-voice [SKIPPED:frontend-only-single-line] (REV-20260611-0205)
- [ ] verify-completion → main ff-merge → web 재배포 → 라이브 확인(Shift+Enter 줄바꿈, Enter/Ctrl+Enter 전송 무변경)

### TASK-0207 — 관리 콘솔 '데이터소스' pane UI 표준화(list-detail) + 수정/삭제 UI 노출 (frontend-only) (2026-06-11)
- [x] **Minor §12.3** (프런트 3파일, RBAC·스키마·엔드포인트·백엔드·시크릿 0) — 사용자 요청: `관리 콘솔 > 데이터소스` UI 를 다른 카테고리(계정·역할·제품·설정)처럼 예쁘게 구성 + 데이터소스 수정/삭제를 UI 내에서 가능하게. **근본 원인**: 데이터소스 pane 만 표준 5단 `admin-list-detail` 구조(DESIGN.md §2)를 안 따르고 `h3` + 평면 `admin-ds-list` 로 렌더 + 미스타일 클래스(`admin-badge`/`admin-field`/`admin-row-actions`)라 이질적. 수정/삭제 핸들러(PATCH/DELETE+force)는 TASK-0205 에서 이미 작동했으나 평면 행에 묻혀 잘 안 보임. (CHG-20260611-0207)
- [x] **재구성** ([admin.html](../src/static/admin.html)): 데이터소스 `section` 을 설정(settings) pane 과 동일한 list-detail nav 구조로 — `drawer-label`+`h2`+`admin-pane-head-right`(+새 데이터소스) 헤더, 좌측 `admin-list-col`(검색 `#datasourceSearch`+카운트 `#datasourceListCount`+`#datasourceList`), 우측 `admin-detail-col`(`#datasourceDetail`). 캐시버스터 `?v=20260611-ds-admin-ui`.
- [x] **재작성** ([admin.js](../src/static/admin.js) `renderDatasourcesPane` 등): 목록=클릭 가능 `admin-list-row--nav`(키·엔진뱃지·.env/비번없음 뱃지·host:port/db meta, 검색 필터, aria listbox/option). 상세=선택 datasource 의 연결좌표·출처·보안 kv + 상태안내 + 액션(연결 테스트 / 수정 / 삭제). 수정·삭제는 상세 패널 하단 sticky 액션바에 노출(`ds.editable && console.manage` 일 때만 — env 출처는 테스트만 + 읽기전용 사유 안내). 생성/편집 폼도 상세 컬럼에 인라인. `#tabCountDatasources` 카운트 배지 wiring(refreshPendingUI). RBAC 게이트(console.manage·ds.editable·encryption-ready) 전부 보존 — 백엔드 무변경.
- [x] **CSS** ([styles.css](../src/static/styles.css)): 미스타일이던 `admin-badge`(+muted/warn)·`admin-kv`·`admin-detail-title`·`admin-field`·`admin-row-actions` 를 표준 토큰(`--primary`/`--primary-soft`/`--border`/`--danger` 등)으로 정렬. (기존 `admin-detail-head`·`admin-detail-actions`·`admin-list-row--nav` 재사용.)
- [x] outside-voice [SUBAGENT:design-correctness] (REV-20260611-0207) — 패널 SHIP-WITH-FIXES: BLOCKER(`admin-detail-head` 중복정의로 타 pane 헤더 회귀) + 생성→키정규화(소문자) 자동선택 누락 + 읽기전용 안내가 sticky 액션바 아래 배치 + readonly tint no-op + aria-selected 누락 — 5건 전부 수용·수정.
- [x] node --check admin.js PASS, `.admin-detail-head` 단일정의 회복 확인.
- [x] verify-completion PASS → PR #144 머지(main `20a826d`) → `make dc-build SERVICE=web`+`up -d --no-build web` 배포(healthz git_commit:20a826d) → Windows-browser(PB-0008) 시각검증 PASS(목록·상세·읽기전용 게이트·생성/편집 폼, artifacts/ds-admin-ui-*.png) (TEST.md §3 2026-06-11)

### TASK-0208 — 프로필 사이드바(drawer) 너비 조절 + 사용 내역 집계 단위(시간별/일별/월별) (frontend-only) (2026-06-11)
- [x] **Minor §12.3** (프런트 3파일, RBAC·스키마·엔드포인트·백엔드·시크릿 0) — 사용자 요청 2건: ① 프로필 사이드바(`#profileDrawer`)를 assistant 답변의 `단계 보기` 패널처럼 너비 드래그 조절 가능하게. ② `사용 내역` 탭 집계 단위를 시간별/일별/월별로 조절 가능하게. (CHG-20260611-0208)
- [x] **Task 1 (drawer 리사이즈)** ([app.js](../src/static/app.js)·[styles.css](../src/static/styles.css)·[index.html](../src/static/index.html)): 단계 보기 패널(`setupStepSidePanelResize`/`_applyStepSidePanelWidth`/`STEP_PANEL_*`) 패턴을 그대로 미러링 — `#profileDrawer` 좌측 가장자리에 `#profileDrawerResizer` 핸들 추가, 너비 = `innerWidth − clientX` 클램프(min 320 / max 92vw), localStorage `web.profileDrawer.width` 영속, `.drawer.is-resizing` 으로 드래그 중 transition·선택 차단. `openProfile` 가 `setupProfileDrawerResize()`+`_applyProfileDrawerWidth()` 호출.
- [x] **Task 2 (집계 단위)** ([index.html](../src/static/index.html)·[app.js](../src/static/app.js)): 백엔드 `GET /api/profile/usage` 가 이미 `gran`(hour/day/week/month 화이트리스트, 기본 day) 지원 → **프런트 전용**. `사용 내역` 헤더에 `#profileUsageGran` 셀렉터(시간별/일별/월별) 추가, `loadProfileUsage` 가 셀렉터 값을 `GRAN_LABEL` 화이트리스트 검증 후 `&gran=` 으로 전달 + `#profileUsageTrendTitle` 텍스트 동기화, change 리스너 배선(기간 셀렉터와 동일).
- [x] **outside-voice 적대적 리뷰 반영** (REV-20260611-0208, [SUBAGENT:design-correctness] SHIP-WITH-FIXES): **MAJOR 흡수** — drawer 가 패널 전체 스크롤(`overflow-y:auto`)이라 absolute 리사이저가 긴 탭에서 콘텐츠와 함께 스크롤돼 핸들이 시야 밖으로 밀리는 문제 → 단계 패널처럼 내부 스크롤 래퍼(`.drawer-scroll`)로 분리하고 핸들은 비스크롤 shell 에 고정. **MINOR 흡수** — 모바일(≤680px)에선 저장 너비 inline 적용을 건너뛰고 미디어쿼리가 폭 소유(`_applyProfileDrawerWidth` 가드). MINOR(초협소 뷰포트 min-width 오버플로)는 단계 패널 상속 동작이라 수용. `left:0`/XSS-safe(textContent+화이트리스트)/리스너 균형 등 비이슈 확인.
- [x] node --check app.js PASS, styles.css 중괄호 균형(911/911), drawer aside div 균형(30/30). 캐시버스터 `?v=20260611-profile-resize-gran`. 기존 단계 보기 패널 코드 무수정(회귀 0).
- [ ] verify-completion → main rebase·ff-merge → web 재배포(`make dc-build SERVICE=web`+`up -d --no-build web`) → PB-0008 Windows-browser 시각검증(drawer 드래그 리사이즈·너비 영속·집계 단위 전환·추세 제목 동기화)

### TASK-0209 — 관리 콘솔 LLM 사용량 집계기준↔집계범위 드롭다운 순서 정렬 (frontend-only) (2026-06-11)
- [x] **Minor §12.3** (admin.html DOM 재배치 1건, RBAC·스키마·엔드포인트·백엔드·JS·CSS 0) — 사용자 요청: 프로필 `사용 내역`(TASK-0208)의 집계기준→집계범위 드롭다운 순서에 맞추어, `관리 콘솔 > LLM 사용량`의 집계범위(`#usageDaysSel`)↔집계기준(`#usageGranSel`) 위치를 서로 바꿔 동일 순서(집계기준 먼저)로 통일. (CHG-20260611-0209)
- [x] **수정** ([admin.html](../src/static/admin.html)): `.admin-pane-actions` 안에서 `#usageGranSel`(시간별/일별/주별/월별)을 `#usageDaysSel`(최근 N일) **앞**으로 이동. JS(`admin.js`)는 두 select 를 id 로 참조하므로 순서 무관 — 동작·회귀 0. 캐시버스터 `?v=20260611-ds-admin-ui` → `?v=20260611-usage-dropdown-order`.
- [x] outside-voice [SKIPPED:frontend-trivial-reorder] (REV-20260611-0209) — DOM 형제 2개 순서 교체, 로직/권한/스키마/엔드포인트 0.
- [x] admin.html select 태그 균형(4/4). 프로필 사용 내역(TASK-0208)과 순서 일치 확인.
- [ ] verify-completion → main rebase·ff-merge → web 재배포 → PB-0008 Windows-browser 시각검증(집계기준 먼저, 프로필과 동일 순서)

### TASK-0213 — 접근 가능 데이터베이스 선택 UI 개선: 드롭다운 + 체크박스 연속 토글 (2026-06-11)
- [x] **Minor §12.3** (프런트 2파일 + 백엔드 2파일, RBAC·스키마·엔드포인트 신규 0) — 사용자 요청: `관리 콘솔 > 제품` 의 접근 가능 데이터베이스 선택 시 드롭다운에서 하나씩 추가하는 방식이 불편 → 드롭다운 + 체크박스로 연속 토글 가능하게. (CHG-20260611-0213)
- [x] **수정 (프런트)** ([admin.js](../src/static/admin.js)·[styles.css](../src/static/styles.css)·[admin.html](../src/static/admin.html)): `buildPicker()` 를 체크박스 드롭다운 패널 방식으로 교체 — `pickerSelect`+`pickerAddBtn` → `pickerDropBtn`(+ 데이터베이스 선택) + `pickerDropList`(체크박스 항목들). 항목 체크 시 즉시 draft 추가, 언체크 시 즉시 제거. 패널 바깥 클릭 시 자동 닫힘. CSS `.admin-db-picker-wrap/.admin-db-picker-btn/.admin-db-picker-list/.admin-db-picker-item/.admin-db-picker-empty` 신규. 캐시버스터 `?v=20260611-db-picker-checkbox`.
- [x] **수정 (백엔드)** ([db.py](../../../feature-0002-agent-core/src/modules/db.py)·[app.py](../src/app.py)·[test_multi_datasource.py](../../../feature-0002-agent-core/tests/test_multi_datasource.py)): MSSQL 연결 시 `default_db` 미설정 폴백을 로그인 기본 DB → **중립 `tempdb`** 로 변경 (업무 데이터 0, 3-part 쿼리 강제). `admin_create_datasource`·`admin_update_datasource` 에서 `default_db` 필드 갱신 제거(NULL 고정). 테스트 기대값 수정(`"" → "tempdb"`).
- [x] outside-voice [SKIPPED:frontend-picker-ui-no-rbac-schema-change] (REV-20260611-0213) — 프런트 UX 교체 + tempdb 폴백 보안 하향(업무 누출 차단). RBAC·API 계약·스키마 무변경.
- [x] node --check admin.js PASS
- [x] verify-completion PASS → PR ff-merge → docker build + up 배포 → PB-0008 Windows-browser 시각검증(체크박스 드롭다운 토글·즉시 반영)

### TASK-0216 — 데이터소스 키 자동 생성: 엔진+호스트+포트 해시 (2026-06-11)
- [x] **Minor §12.3** (백엔드 1파일 + 프런트 1파일, RBAC·스키마·외부 엔드포인트 신규 0) — 사용자 요청: `관리 콘솔 > 데이터소스` 의 각 항목 키를 식별자 문자열 대신 `엔진+호스트+포트` 해시로 구성(용도 변경 시 대응 용이). 기존 `main_mysql` 레거시 키 및 해당 식별자를 참조하는 항목도 마이그레이션 포함. (CHG-20260611-0216)
- [x] **신규 함수 추가** ([app.py](../src/app.py) `_generate_datasource_key`): `엔진:호스트:포트` 의 SHA-256 해시 앞 12자 + 엔진 태그(`{engine}-{hash12}` 형식). 동일 엔드포인트 → 항상 동일 키(멱등), 엔드포인트 변경 → 자동으로 다른 키.
- [x] **변경 (백엔드)** ([app.py](../src/app.py) `admin_create_datasource`): body 의 `key` 수신 제거 → `_generate_datasource_key(engine, host, port)` 자동 생성으로 교체. 409 에러 메시지에 "동일 엔드포인트가 이미 등록되어 있습니다" 추가. 응답 `default_db` 미정의 버그 → `None` 수정.
- [x] **변경 (백엔드)** ([app.py](../src/app.py) `_seed_main_mysql_datasource`): `key = "main_mysql"` 하드코딩 → `_generate_datasource_key("mysql", DB_HOST, int(DB_PORT))` 자동 생성. 레거시 `main_mysql` 키가 DB에 존재하면 해시 키로 rename + `WebProducts.DatasourceKey` 참조 일괄 업데이트(운영 연속성 보장).
- [x] **변경 (프런트)** ([admin.js](../src/static/admin.js) `_dsRenderForm`): 신규 생성 시 key 입력 필드 제거 → 자동 생성 안내 힌트 표시. 수정 시는 기존대로 키 readonly 표시. body 전송 시 `key` 필드 제외(서버 자동 생성). 생성 완료 토스트 "키 자동 생성" 메시지 추가.
- [x] **미변경** (`_migrate_env_datasources_to_db`): `.env` 키 이름 그대로 사용하는 레거시 경로 — 의도적 유지.
- [x] outside-voice [SKIPPED:auto-key-no-rbac-no-schema-no-secret] (REV-20260611-0216) — 키 생성 방식 변경(해시화)이며 RBAC·API 계약·WebDatasources 스키마·암호화 경로 무변경. 레거시 마이그레이션은 멱등 UPDATE 2개.
- [x] py_compile app.py PASS, node --check admin.js PASS
- [ ] verify-completion → main rebase·ff-merge → web 재배포 → PB-0008(관리 콘솔 > 데이터소스 신규 등록 + 키 자동 생성 확인)

### TASK-0217 — 데이터소스 해시 키 버그 수정 2건: 마이그레이션 패스워드 재암호화 + 수정 시 키 재생성 (2026-06-11)
- [x] **Minor §12.3** (백엔드 1파일 + 프런트 1파일, RBAC·스키마·신규 엔드포인트 0) — TASK-0216 후속 버그 2건 수정. (CHG-20260611-0217)
- [x] **버그 1 수정** ([app.py](../src/app.py) `_seed_main_mysql_datasource`): `main_mysql` → 해시 키 rename 시 `PasswordEnc`를 새 키 AAD로 재암호화하지 않아 `InvalidTag` 복호 실패로 데이터소스 전체가 skip되던 문제. 해결: rename 전 레거시 PasswordEnc+EncryptionVersion 조회 → DEK 로드 → 복호 → 새 키 AAD로 재암호화 → `UPDATE DatasourceKey, PasswordEnc, EncryptionVersion` 한 번에 처리.
- [x] **버그 2 수정** ([app.py](../src/app.py) `admin_update_datasource`): 수정 폼에서 host/port 변경 시 키(해시)가 바뀌어야 하나 `DatasourceKey`가 그대로 유지되어 엔드포인트와 키가 불일치하던 문제. 해결: PATCH 처리 시 기존 engine/host/port 읽기 → 변경 후 새 해시 키 계산 → 키가 바뀌면 패스워드 AAD 재암호화 + `DatasourceKey` 업데이트 + `WebProducts.DatasourceKey` 참조 업데이트.
- [x] **프런트 수정** ([admin.js](../src/static/admin.js) `_dsRenderForm` save 핸들러): PATCH 응답의 `key` 로 `_dsSelectedKey` 동기화(키 변경 시 목록 선택 미싱 방지).
- [x] outside-voice [SKIPPED:bugfix-aad-reencrypt-no-new-surface] (REV-20260611-0217) — 암호화 경로 변경 없음(기존 DEK/AESGCM 재사용), RBAC·스키마·엔드포인트 신규 0. 재암호화 실패는 기존 패스워드 유지(연결 테스트 실패로 가시화).
- [x] py_compile app.py PASS, node --check admin.js PASS
- [x] verify-completion → main rebase·ff-merge → web 재배포 → 컨테이너 로그 `datasource_decrypt_failed` 소거 확인 (TASK-0218에서 자가수복 포함 완결)

### TASK-0218 — 데이터소스 키 명시적 rename 지원 + AAD 자가수복 (2026-06-11)
- [x] **Minor §12.3** (백엔드 1파일 + 프런트 1파일, RBAC·스키마·신규 엔드포인트 0) — TASK-0217 이후 잔여 버그 2건: ① `main_mysql` 이미 rename된 환경에서 AAD 불일치 자가수복, ② 수정 폼에서 키 직접 편집 불가. (CHG-20260611-0218)
- [x] **버그 1 수정** ([app.py](../src/app.py) `_seed_main_mysql_datasource`): `main_mysql` 레거시 행이 DB에 없을 때(이미 이전 배포에서 rename됨) 해시 키 행의 `PasswordEnc` AAD를 검증 → 현재 키 AAD로 복호 실패 시 구 AAD(`main_mysql`)로 복호 → 새 키 AAD로 재암호화하는 자가수복 `else` 브랜치 추가.
- [x] **버그 2 수정** ([app.py](../src/app.py) `admin_update_datasource`): PATCH body `key` 필드가 존재하면 명시적 키 rename으로 처리. 패스워드 AAD 재암호화 + `WebProducts.DatasourceKey` 참조 업데이트 포함. 엔진+호스트+포트 변경 시 해시 재계산과 병합(명시 키 우선).
- [x] **버그 2 수정** ([admin.js](../src/static/admin.js) `_dsRenderForm`): 수정 폼의 key 필드 `readonly` → 편집 가능으로 변경. 값이 원래 키와 다를 때만 `body.key` 로 전송.
- [x] outside-voice [SKIPPED:bugfix-aad-fix2-no-new-surface] (REV-20260611-0218) — 자가수복·명시 rename 모두 기존 DEK/AESGCM 재사용, RBAC·스키마·엔드포인트 신규 0.
- [x] py_compile app.py PASS, node --check admin.js PASS
- [x] verify-completion PASS → PR #155 머지 → web 재배포 → 서버 기동 정상(`datasource_decrypt_failed` 미발생)

### TASK-0223 — 제품별 insight-worker 분석 완료율 UI (관리 콘솔 > 제품) (2026-06-11)

**Major §12.3** (백엔드 app.py 신규 엔드포인트 1 + 헬퍼 + 프런트 admin.js/admin.html — read-only 통계, RBAC·스키마 변경 0, 외부 영향 0). (CHG-20260611-0223)

#### 2.1 Implementation Plan

**요구**: `관리 콘솔 > 제품` 에서 각 제품별로 insight-worker 의 객체 분석 완료율(%)을 표시. 비율 모수 = 그 제품의 `접근 가능 데이터베이스`(WebProductDatabases) 에 선택된 DB; 분자 = PG 내 해당 DB/테이블에 대한 통찰값(rag_objects) 존재 개수.

**핵심 데이터 흐름 (검증 완료)**:
- 접근 가능 DB = `WebProductDatabases.SchemaName` (제품별). `_list_product_databases(conn, pid)`.
- 제품→데이터소스 = `WebProducts.DatasourceKey`(라벨, NULL=레거시 기본 MySQL). `_list_products`.
- rag_objects 의 datasource 스코핑 = **엔드포인트 해시** `compute_scope_key(engine,host,port)` (라벨 아님; insight.py:1605). 기본 MySQL(ds=None) 스캔 행은 `datasource_key IS NULL`.
- insight 객체 행: `public.rag_objects` (conversation_id=`__insight_worker__`, scope_key=`common`), `object_type IN ('schema','table')`, `schema_name`/`table_name`.
- 분모(전체 객체) = 라이브 카탈로그 `SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA IN (접근DB)` (ANSI, MySQL/MSSQL 공용). 객체 = {접근 DB 노드(schema)} ∪ {그 안의 table}.

**dialect 처리**:
- 기본/MySQL 데이터소스: 접근 DB == 스키마. `TABLE_SCHEMA IN (dbs)` 직접 매칭. rag 매칭 `schema_name IN (dbs)`.
- MSSQL 데이터소스: 접근 DB == 데이터베이스명. insight-worker 는 datasource 의 **default_db 만** 스캔(insight.py:1614). 접근 DB 가 default_db 면 그 DB 에 연결(default_db 고정)해 전체 user 스키마의 table 열거 → rag (schema,table) 매칭. 접근 DB ≠ default_db 면 insight-worker 미스캔 → analyzed=0, UI 에 "워커 미스캔" flag 명시(truthful).

**파일/심볼 변경**:
1. [app.py](../src/app.py) 신규 헬퍼 `_compute_product_insight_coverage(conn, product, *, cache)`:
   - scope_key 해석(datasource_key→`_dsr.resolve`→`scope_key`; NULL→NULL 매칭).
   - 접근 DB 열거 → 라이브 table 카탈로그(분모) + rag_objects 매칭(분자).
   - SSRF 가드(`_ssrf_check_host`) 데이터소스 host, 짧은 timeout(5s), per-datasource 실패 격리(→ `measurable:false`).
   - 반환: `{product_id, pct, analyzed_objects, total_objects, per_db:[{db, schema_analyzed, tables_analyzed, tables_total, scannable, note}], measurable, reason}`.
2. [app.py](../src/app.py) 신규 엔드포인트 `@app.get("/api/admin/products/insight-coverage")` → `admin_products_insight_coverage(request)`:
   - 권한 `console.access` (제품 목록과 동일 gate).
   - `?product_id=` 단건 또는 전체. **인메모리 TTL 캐시**(90s, key=product_id+scope+db-set) — 라이브 DB 반복 조회 차단.
3. [admin.js](../src/static/admin.js):
   - `loadAdminData` 후 `loadProductInsightCoverage()` async 호출 → `adminState.productCoverage` Map 채움 → `renderProductList` 재렌더.
   - `renderProductList`: 각 row 에 coverage 미니바/배지("분석 N%") 추가.
   - `renderProductDetail`: "접근 가능 데이터베이스" 섹션에 coverage 요약(전체 %) + per-DB breakdown + 새로고침 버튼.
4. [admin.html](../src/static/admin.html): 정적 자산 캐시버스터 `?v=` bump.

**완료 판정 기준 (acceptance criteria)**:
- AC1: 제품 목록에서 각 제품 row 에 분석 완료율(%) 배지가 표시된다.
- AC2: 제품 상세의 접근 가능 DB 섹션에 전체 % + DB별(테이블 analyzed/total, schema insight 유무) breakdown 이 표시된다.
- AC3: 비율 = (rag_objects 통찰 보유 객체 수) / (접근 DB 의 라이브 카탈로그 객체 수). scope_key=엔드포인트 해시 매칭(또는 NULL).
- AC4: 데이터소스 연결 실패/미바인딩 제품은 500 없이 "측정 불가"/"접근 0" 으로 graceful 표시.
- AC5: MSSQL 데이터소스의 비-default_db 접근 DB 는 "워커 미스캔" 으로 명시(0% 오해 방지).
- AC6: py_compile/node --check/make test PASS, PB-0008 Windows-browser 시각검증 PASS.

**위험도 Major 근거**: 다중 파일(백엔드 신규 엔드포인트 + 프런트 목록/상세) + 라이브 DB 연결(분모) + PG 조회(분자) + 캐시. 단 RBAC·스키마·암호화·외부계약 변경 0(읽기 전용 통계). 접근모델 인접 → outside-voice 설계 리뷰 경유(매칭 의미론·dialect·SSRF/캐시 안전성).

#### 작업 항목
- [x] outside-voice 설계 리뷰 (REV-20260611-0223 [SUBAGENT]) — NOT-SHIP 5건이 catalog-driven 구현으로 전부 해소 확인
- [x] 백엔드: `_compute_product_insight_coverage` + `/api/admin/products/insight-coverage` + TTL 캐시 (+ db.py `list_information_schema_tables`)
- [x] 프런트: 목록 배지 + 상세 breakdown + loader + CSS + 캐시버스터
- [x] py_compile app.py+db.py PASS + node --check admin.js PASS
- [x] verify-completion PASS → PR #161 머지(main b46cbd4) + hotfix(cde2610 `_log`→logging, 0e37b8e conversation_id `__global__`) → web 재배포(healthz git_commit=0e37b8e) → 라이브 실측(MySQL 제품 1/7/8=100%, MSSQL graceful 측정불가) + PB-0008 Windows-browser 시각검증 PASS(목록 배지 3×100%+1×측정불가, 상세 389/389 breakdown)

### TASK-0225 — textarea 우측 하단 핸들 더블클릭 시 내용 높이로 자동 확장 (Minor §12.3)

긴 문자열을 담는 textarea 들의 크기 조절 마찰 해소. 우측 하단 native resize 핸들을 **더블클릭** 하면 입력된 텍스트의 수직 크기만큼 자동 확장한다. 본문 더블클릭(단어 선택)은 그대로 유지.

- AC1: `resize: vertical|both` 인 textarea(예: `.field textarea`, `.admin-prompt-textarea`)의 우측 하단 핸들 영역(~18px) 더블클릭 시 내용 높이로 확장된다.
- AC2: 본문 영역 더블클릭은 단어 선택 등 기존 동작을 그대로 유지(자동 확장 미발동).
- AC3: index / admin / share 세 페이지 모두 적용(공통 위임 스크립트 1개 로드).
- AC4: 동적 생성 textarea(admin.js `.admin-prompt-textarea`)도 document capture 위임으로 자동 커버.
- AC5: 상한(600px)으로 무한 확장 방지. node --check PASS.

**위험도 Minor 근거**: 비파괴 프런트 추가(신규 JS 1파일 + HTML 3파일 script 태그). RBAC·스키마·암호화·신규 엔드포인트·백엔드 변경 0. 순수 클라이언트 UX.

#### 작업 항목
- [x] 신규 `src/static/textarea-autogrow.js`: document `dblclick` capture 위임 — 핸들 영역 좌표 판정 + `scrollHeight` 기반 확장(border-box 보정 + 600px 상한).
- [x] `index.html` / `admin.html` / `share.html` 에 `textarea-autogrow.js` script 태그 추가(캐시버스터 `?v=20260611-dblclick-autogrow`).
- [x] node --check textarea-autogrow.js PASS.
- [ ] verify-completion → main rebase·ff-merge → web 재배포 → PB-0008(핸들 더블클릭 자동 확장 시각검증)

### TASK-0226 — MSSQL 제품 분석 완료율 미표시(연결) 수정: per-DB 연결 격리 (2026-06-11)

> 동시세션 TASK 번호 충돌(§13.1): 본 작업은 처음 TASK-0225 로 시작했으나 다른 세션의 TASK-0225(textarea-autogrow, PR #162 main 선머지)와 충돌 → **TASK-0226 으로 재번호**(branch slug `task0225-…`는 cosmetic 유지). CHG/REV/AC 도 0226 으로 정합.

**Minor §12.3** (TASK-0223 후속 버그수정, app.py 1 + admin.js 1, RBAC·스키마·신규 엔드포인트 0). (CHG-20260611-0226)

#### 진단 (라이브)
사용자 보고: MSSQL 제품(DK온라인, `mssql_local`)이 "측정 불가". 근본 원인:
- 자격증명은 정상 — `probe_datasource`=True, `list_server_databases_classified` OK. RO 로그인 `agent_ro` 는 **`dk_data_release` 만 GRANT**(123 테이블, rag 와 123/123 overlap=100%), 나머지 4개 DB(`dk_server_info`/`GameLog_100/151`/`GameLogManager`)는 권한 없음(SQL Server 18456).
- **bug1**: MSSQL 분모 열거가 accessible DB 전체를 **단일 try/except** 로 감싸 → 한 DB(권한없음) 연결 실패가 전체 제품을 measurable=False 로 오염.
- **bug2**: `scannable = bool(default_db) and db==default_db` 게이트가 `default_db=None` 이라 연결·분석된 dk_data_release 마저 미스캔(analyzed 0) 처리.

#### 수정
- [app.py](../src/app.py) `_compute_product_insight_coverage`: MSSQL 분기를 **per-DB try/except 격리** 로 — DB별 연결 실패는 `connected=False`+note 로만 표기하고 나머지 DB 정상 집계. `scannable`(default_db 게이트) 폐기 → `connected`(연결 성공 여부)로 대체. 비연결 DB 는 객체 열거 불가라 분모에서 제외(측정 가능 DB 기준 정직 표기). 전부 실패 시 reason 설정.
- [admin.js](../src/static/admin.js): per-DB 렌더 `scannable`→`connected`, 비연결 DB="연결 불가"(cov-low) 표시. 배지/요약 "연결 불가" vs "대상 없음" 구분. total=0 도 per-DB 목록 노출. MSSQL 안내 문구 갱신.
- [admin.html](../src/static/admin.html): 캐시버스터 `?v=20260611-mssql-coverage-perdb`.

#### 완료 판정 기준
- AC1: MSSQL 제품이 "측정 불가" 대신 **완료율(%)을 표시**(dk_data_release 100% 반영).
- AC2: 권한 없는 DB(`dk_server_info` 등)는 per-DB breakdown 에 "연결 불가"로 명시, 전체 % 집계에서 제외(다른 DB 오염 없음).
- AC3: MySQL 경로 회귀 0(단일 연결 try 유지).
- AC4: py_compile/node --check/make test PASS, 라이브 실측(product 91 = dk_data_release 123/123 + 4 연결불가) + PB-0008 시각검증.

#### 작업 항목
- [x] 백엔드 per-DB 연결 격리 + default_db 게이트 폐기 + connected/note
- [x] 프런트 connected 렌더링 + 연결불가 표시 + MSSQL 안내 갱신 + 캐시버스터
- [x] py_compile + node --check PASS
- [ ] verify-completion → 머지 → web 재배포 → 라이브 실측 + PB-0008 시각검증

### TASK-0227 — 실행 단계 사이드 패널 갱신 시 "결과 보기" 펼침 상태 유지 (frontend-only) (2026-06-11)

**Minor §12.3** (app.js 1 + index.html 1, RBAC·스키마·신규 엔드포인트·백엔드·CSS 0). (CHG-20260611-0227)

#### 진단
사용자 보고: assistant 답변의 `실행 단계`를 사이드바에 펼쳐놓고 특정 단계의 `결과 보기`로 결과셋을 확인 중일 때, 실행 단계가 갱신(폴링으로 새 단계 추가)되면 보던 결과셋이 닫혀버린다.

근본 원인: 폴링으로 새 단계가 도착할 때마다 `applyProgressPayload`가 `refreshStepSidePanel` → `_renderStepSidePanelBody`를 호출하는데, 이 함수가 `body.innerHTML = ""`로 패널 DOM 전체를 비우고 모든 단계를 재생성한다. 그런데 각 단계의 "결과 보기" 펼침 여부는 순전히 DOM 로컬 변수(`resultBody.hidden`, `buildStepDetailEl` 내부)로만 존재 → 재렌더 시 전부 기본값(닫힘)으로 리셋. 스크롤 위치는 이미 스냅샷/복원(`wasAtBottom`)하면서 펼침 상태는 보존하지 않던 비대칭.

#### 수정
- [app.js](../src/static/app.js):
  - `state.stepResultExpanded`(Set) 신설 — 펼친 단계의 안정 키를 기억.
  - `_stepResultKey(step, idx)` 헬퍼 — `progressSteps` dedup과 동일한 `step_index:created_at` 조합(둘 다 없으면 `idx` fallback)으로 같은 단계가 재렌더를 거쳐도 동일 키 유지.
  - `buildStepDetailEl`의 결과 토글: 초기 `hidden`/버튼 라벨/`aria-expanded`를 `state.stepResultExpanded`에서 복원, 토글 클릭 시 Set에 add/delete.
  - run 전환 시(`resetProgressTracking` + `applyProgressPayload`의 runId 변경 분기) Set `clear()` — 다른 run의 동일 step 키 혼동 방지.
- [index.html](../src/static/index.html): 캐시버스터 `?v=20260611-step-result-persist`.

#### 완료 판정 기준
- AC1: 실행 단계 사이드 패널에서 한 단계의 "결과 보기"를 펼친 뒤 새 단계가 폴링으로 추가돼도 해당 결과셋이 계속 펼쳐진 상태로 유지된다.
- AC2: 여러 단계를 동시에 펼쳐두면 각각 독립적으로 유지된다.
- AC3: 다른 대화/run으로 전환하면 펼침 상태가 누적되지 않고 초기화된다.
- AC4: node --check PASS, PB-0008 Windows-browser 시각검증.

#### 작업 항목
- [x] state.stepResultExpanded + _stepResultKey + 토글 복원/저장 배선
- [x] run 전환 시 Set clear (resetProgressTracking + applyProgressPayload)
- [x] node --check PASS + 캐시버스터 bump
- [ ] verify-completion → 머지 → web 재배포 → PB-0008 시각검증

### TASK-0232 — 제품 프롬프트 "자동 작성" 결과 중간 잘림 해소 (2026-06-11)

**Major §12.3** (외부 LLM 비용 영향 — 출력 토큰 cap 상향; feature-0002 model_catalog + feature-0003 app.py/admin.js/styles.css 교차). (CHG-20260611-0232) — 동시세션 insight-reset cycle 이 TASK-0231 선점→§13.1 재번호 0231→0232.

#### 진단
사용자 보고: `관리 콘솔 > 제품 > [각 제품] > 제품 프롬프트 > 자동작성` 으로 받은 텍스트가 글자 수 제한으로 중간에 잘린다.

근본 원인: 저장 컬럼(`WebSystemPrompts.Content` = MEDIUMTEXT)·프론트 textarea(maxlength 없음) 둘 다 제약 아님. 진짜 원인은 `admin_generate_product_prompt`([app.py](../src/app.py) 14877)가 출력 토큰 상한을 `max_tokens_for_model(llm_model, "summary")` 로 잡은 것. `"summary"` 는 짧은 요약/토픽용 프로파일(Claude 7000 / 로컬 512)이라 "완성된 시스템 프롬프트 본문"을 담기엔 부족. 웹 기본 모델 `claude-haiku-4` 기준 7000 cap 에서 extended-thinking budget(≤5000)을 빼면 실본문 ~2000 토큰 → 중간 잘림. 게다가 `finish_reason` 미검사로 잘린 채 조용히 반환(사용자가 잘린 줄 모름).

#### 수정
- [model_catalog.py](../../feature-0002-agent-core/src/modules/model_catalog.py): 긴 본문 전용 `"prompt_gen"` cap 신설 — Claude 20000(thinking 차감 후 ≥4000 본문 여유) / 로컬 LLM 3072(4K 컨텍스트 내 최대). 비용 통제 위해 무제한 아닌 명시 cap 유지.
- [app.py](../src/app.py): ① 자동작성 호출부 `"summary"`→`"prompt_gen"`, timeout 55→90s. ② `finish_reason == "length"` 잘림 검출 → `meta.truncated` 플래그 + warning 로그.
- [admin.js](../src/static/admin.js) + [styles.css](../src/static/styles.css): `truncated` 시 "출력 길이 제한 도달, 잘렸을 수 있음 — 재생성 권장" 경고 표시(`.admin-meta-warn`, `--warning` 색).

#### 완료 판정 기준
- AC1: 인사이트가 풍부한 제품에서 자동작성 시 시스템 프롬프트 본문이 중간에 끊기지 않고 완결된다.
- AC2: 출력이 그래도 cap 에 도달하면 admin UI 가 "잘렸을 수 있음" 경고를 표시(조용한 잘림 없음).
- AC3: 토큰 cap 외 권한/스키마/엔드포인트 shape 변경 0.
- AC4: 신규 테스트 PASS(prompt_gen cap 단조성 + truncated 검출) + node --check + PB-0008 시각검증.

#### 작업 항목
- [x] model_catalog.py prompt_gen cap 신설 (Claude 20000 / 로컬 3072)
- [x] app.py 호출부 summary→prompt_gen + finish_reason 잘림 가드 + meta.truncated
- [x] admin.js + styles.css truncated 경고 표시
- [x] 신규 테스트 9 PASS + node --check admin.js PASS
- [ ] verify-completion → 머지 → web 재배포 → PB-0008 시각검증

### TASK-0237 — 제품 프롬프트 "자동 작성" LLM 토큰 스트리밍(SSE) + OpenAI legacy 명명 정리 (2026-06-12)

**Major §12.3** (단일 이벤트 루프 블로킹 위험 + 운영 env 호환; feature-0002 llm/config/model_catalog + feature-0003 app.py/admin.js 교차). (CHG-20260612-0237) — 동시세션 cycle 이 TASK-0231~0236 선점→§13.1 재번호 0233→0237. PLAN-APPROVED(plan groovy-hugging-clarke).

#### 배경
자동작성(TASK-0232 에서 잘림 해소)이 최대 90초 LLM 호출 동안 "생성 중…" spinner 뿐이라 진행을 알 수 없음. 토큰 스트리밍으로 실시간 표시 + OpenAI legacy 명명 정리(SDK 유지)를 한 cycle 로 묶음(사용자 확정).

#### 수정 (커밋 5분리)
- 커밋1 (legacy): `_get_openai_client`→`_get_llm_client` rename + alias + 호출처 전부, `OPENAI_API_BASE` dead env 제거, model_catalog 죽은 분기 주석 정정, 앵커 tripwire 갱신.
- 커밋2 (env): `LLM_MODEL`/`AGENT_LLM_MAX_RETRIES` 우선 + 구이름 fallback(운영 .env 무중단), `_resolve_session_default_model` 동반, .env.example.
- 커밋3 (SSE 백엔드): `_collect_product_prompt_context` 헬퍼 + 신규 GET `.../stream`(별 스레드+asyncio.Queue 브릿지, SSE progress→token→done|error).
- 커밋4 (SSE 프론트): autoBtn fetch+ReadableStream+TextDecoder 재작성, applyAutoGenMeta, AbortController, 캐시버스터.
- 커밋5 (docs): 본 항목 + MODIFY/REVIEW/FUNCTION/STATUS.

#### 완료 판정 기준
- AC1: 인사이트가 풍부한 제품에서 자동작성 시 토큰이 textarea 에 실시간으로 차오른다(한꺼번에 X).
- AC2: 단일 이벤트 루프 블로킹 없음(별 스레드+Queue 브릿지) — 스트림 중 타 요청 정상.
- AC3: 인증/권한/스키마/엔드포인트 무변경(신규 stream GET + product.manage 게이트 재사용). rename·env 무중단(alias+fallback).
- AC4: 신규 테스트 PASS(SSE 6 + env 6) + 기존 회귀 0 + node --check + PB-0008 시각검증.

#### 작업 항목
- [x] 커밋1 legacy 정리 (_get_llm_client + alias + dead env + 앵커)
- [x] 커밋2 env backward-compat (LLM_MODEL/AGENT_LLM_MAX_RETRIES)
- [x] 커밋3 SSE 백엔드 (헬퍼 추출 + stream GET + Queue 브릿지) + 단위 6 PASS
- [x] 커밋4 SSE 프론트 (fetch+ReadableStream) + node --check
- [x] env compat 테스트 6 PASS + agent-core 회귀 0
- [ ] verify-completion → 머지 → web 재배포 → PB-0008 시각검증(토큰 실시간 흐름)

### TASK-0244 — 관리 콘솔 제품 "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화 (2026-06-12)

**Major §12.3** (frontend-only 다중 파일[admin.js+styles.css] + 네트워크 probe 추가; RBAC·스키마·백엔드 엔드포인트 0 — 기존 `/datasources/{key}/test` 재사용). (CHG-20260612-0244) — 동시세션 cycle 이 0234(ds-label-stable)·0243 까지 선점→§13.1 다음 번호 0244. REV-20260612-0244[SUBAGENT] SHIP.

#### 배경 (사용자 요청 2건)
관리 콘솔 > 제품 > [항목] > 데이터소스 탭의 `+ 데이터소스 추가` 버튼이 출력하는 목록이:
1. **폰트/시각 이질**: 각 항목이 `key — engine @ host:port` 단일 raw 문자열(`<span>` 무클래스)이라 같은 화면의 accordion 행(굵은 이름 + engine pill + 배지)·`+ 데이터베이스 추가` picker(`.admin-db-picker-name` 구조)와 시각 문법이 어긋남.
2. **연결 상태 부재**: 연결 여부를 `⋯ > 연결 테스트`(일회성 토스트)로만 확인 가능, 목록엔 표시 없음.

#### 수정 (frontend-only, 단일 커밋)
- `admin.js`: `_probeDatasourceConn`/`_paintDsConnBadge` 헬퍼 신설 — `/api/admin/datasources/{key}/test` POST probe → `adminState.datasourceConnStatus` Map 캐시(매 토글/재오픈 재probe 방지) + in-flight dedup + **동시 probe 4개 cap 세마포어**(unreachable 다수 시 8s×N web 스레드 점유 방지). `_rebuildDsAddList` 항목을 `[체크박스 · 이름(.admin-db-picker-name 재사용) · 엔진 pill · 좌표(muted) · 연결상태 배지]` 구조로 재구성 + 헤더 `↻ 새로고침`(캐시 무효화 후 재probe). 드롭다운 열림 시 lazy probe.
- `styles.css`: `.admin-ds-picker-head`/`.admin-ds-picker-engine`(= `.ds-acc-engine` 토큰 1:1)/`.admin-ds-picker-coord`/`.admin-ds-conn`(.is-ok/.is-fail/.is-checking, ● 점 + 한글 라벨 병행 — 색-단독 비의존) 추가.
- `admin.html`: 캐시버스터 `?v=20260612-ds-picker-status`.

#### 완료 판정 기준
- AC1: 드롭다운 목록 각 항목이 accordion 행/DB picker 와 동일 폰트·pill·정렬로 보인다(이질감 해소).
- AC2: 각 데이터소스의 연결 상태가 배지로 표시된다(확인 중 → 연결됨·ms / 연결 실패[원인 tooltip]), ↻ 로 재확인 가능.
- AC3: RBAC·스키마·백엔드 엔드포인트 무변경(test 엔드포인트 재사용, console.access·canDs 게이트 보존).
- AC4: node --check admin.js PASS + verify-completion + PB-0008 Windows-browser 시각검증.

#### 작업 항목
- [x] adminState.datasourceConnStatus 캐시 + _probeDatasourceConn/_paintDsConnBadge + 동시성 cap 세마포어
- [x] _rebuildDsAddList 정합 구조 재구성(이름+엔진pill+좌표+연결상태 배지) + 헤더 ↻ 새로고침
- [x] styles.css picker 정합 스타일 + 연결상태 배지(색맹 대응 ● + 라벨)
- [x] node --check admin.js PASS + CSS brace 균형 + 캐시버스터 bump
- [x] outside-voice subagent 디자인/정합 리뷰 SHIP(REV-20260612-0244)
- [ ] verify-completion → 머지 → web 재배포 → PB-0008 시각검증
### TASK-0245 — 제품 상세 접근가능 DB 리스트 행 컬럼 폭 정합 (문자열 길이 무관 정렬) (frontend-only) (2026-06-12)
- [x] **Minor §12.3** (CSS 1파일, RBAC·스키마·엔드포인트·백엔드·시크릿 0) — 사용자 보고: 관리 콘솔 제품 상세 `접근 가능 데이터베이스` 리스트에서 각 행(DB명·역할설명·진척바·통계·상태칩·초기화·제거)의 텍스트/UI 폭이 문자열 길이에 따라 들쭉날쭉. **근본 원인**: `.cov-db-row` 가 행 단위 grid 인데 통계(`37/37`↔`123/123`)·상태칩(`DB✓`↔`연결 불가`↔`대상 없음`)·초기화 컬럼이 `auto`(콘텐츠폭)라 행마다 트랙폭이 달라짐 → 남는 폭을 가져가는 name/role(`fr`) 컬럼이 행마다 어긋나 역할설명·진척바 시작 x 가 불일치. (CHG-20260612-0245)
- [x] **수정** ([styles.css](../src/static/styles.css) `.cov-db-row`): `grid-template-columns` 의 통계·상태·초기화 `auto` 3컬럼을 고정폭(54px·76px·60px)으로 못박아 전 행 트랙 동일화. name `minmax(96px,0.9fr)`·role `minmax(0,1.7fr)` 비율 컬럼은 트랙이 동일해져 행 간 정렬 일치. 상태칩(`.cov-db-status`)·초기화(`.cov-db-reset`)에 `justify-self: start` 추가(고정폭 컬럼에서 pill/button 이 stretch 로 늘어나지 않고 자연폭 유지). 통계(`.cov-db-stat`)는 stretch+`text-align:right` 유지(N/N 우측 정렬). 캐시버스터 `?v=20260612-db-row-align`.
- [x] outside-voice [SKIPPED:css-grid-alignment] (REV-20260612-0245) — 순수 CSS grid 트랙 고정(로직·상태·DOM·권한 0, 전례 TASK-0178/0179/0180 css-layout SKIP 과 동일 경량).
- [x] verify-completion PASS → PR #189 머지(main `2bc2067`) → web 재배포(healthz git_commit:2bc2067) → PB-0008 Windows-browser 시각검증 PASS(제품 92 cov-db-row 8행 전 컬럼 left spread=0px, artifacts/db-row-align-after.png) (TEST.md §3 2026-06-12)

### TASK-0246 — "+ 데이터소스 추가" 드롭다운 항목 열 정렬(고정 열 폭 grid) (2026-06-12)

**Minor §12.3** (CSS-only 단일 규칙 블록; admin.js·백엔드·RBAC 0). (CHG-20260612-0246) — TASK-0244 직후 follow-up. 동시세션 db-row-align 이 TASK-0245(별 요소 `.cov-db-row` 의 동종 정렬 수정) 선점→§13.1 재번호 0245→0246, AC→0460. REV-20260612-0246 [SKIPPED:trivial-grid-align].

#### 배경
사용자: "`+ 데이터소스 추가` 목록의 폭이 문자열 길이에 따라 일정하도록. 현재 들쭉날쭉." 라이브 측정: 항목 폭(542px)은 일정하나 **내부 열 미정렬** — 이름 `flex:1 1 auto` 라 엔진 pill·좌표·연결배지의 시작 x 가 행마다 어긋남(엔진 x961/936/967, 좌표 x1011/986/1018, 배지 x1105/1080/1080).

#### 수정 (styles.css 단일 블록)
- `.admin-db-picker-item.admin-ds-picker-item` `display:flex` → **`display:grid`** + `grid-template-columns: auto minmax(0,1fr) 56px 124px 104px`. 모든 행 동일 고정 트랙 → 이름만 가변 흡수, 나머지 열 세로 정렬(justify-self start/start/end). 긴 좌표/이름 ellipsis+title.
- `admin.html` 캐시버스터 `?v=20260612-ds-picker-col-align`.

#### 완료 판정 기준
- AC1: 모든 행에서 엔진 pill·좌표·연결배지 좌/우 경계 세로 정렬(문자열 길이 무관).
- AC2: 긴 값 ellipsis+title 흡수, 레이아웃 무파손.
- AC3: admin.js·백엔드·RBAC·연결 probe·`.cov-db-row`(0245) 무변경.
- AC4: CSS brace 균형 + PB-0008 시각검증.

#### 작업 항목
- [x] `.admin-ds-picker-item` grid 전환 + 고정 열 폭 + justify-self 정렬
- [x] 캐시버스터 bump + CSS brace 균형(1105/1105)
- [x] origin/main(14a296f) 위로 재적용 + TASK-0245→0246 재번호(동시세션 충돌)
- [x] PR #192 머지(main 6756522)·배포 후 PB-0008 측정: name/engine/coord left spread=0
- [x] 정련(CHG-0246b): 연결배지 justify-self end→start(left spread=0 통일, sibling .cov-db-row 컨벤션)
- [ ] v2 배포 → PB-0008 재측정(전 열 left spread=0) → 마감

### TASK-0256 — assistant 답변 diff 블록: 웹 UI ```diff 렌더 (2026-06-15)
- 목표: 답변 내 ```diff 코드블록을 라인별 +/- 색으로 구분 렌더 (메인 채팅 + 공유 뷰).
- [x] app.js markdownToHtml: enhanceDiffBlocks(parse→enhance→sanitize) — language-diff 블록을 라인별 span 재구성 (textContent 기반, XSS 무첨가)
- [x] share.js renderMarkdownContent 동일 파이프라인 parity
- [x] styles.css/share.css .diff-block/.diff-add/.diff-del/.diff-hunk/.diff-meta (다크 코드배경 팔레트)
- [x] 캐시버스터 bump: index.html(styles/app), share.html(share.css/share.js) → ?v=20260615-task0256-diff
- [x] node --check app.js/share.js PASS
- [x] web 재배포(main 2befd37) + 새 app.js(enhanceDiffBlocks)·캐시버스터(?v=20260615-task0256-diff) 서빙 검증
- [x] PB-0008 Windows-browser 시각검증 PASS — diff +초록(rgb(158,206,106))/-빨강(rgb(247,118,142)) 색 구분 실측(2026-06-15, TEST.md §4)

### TASK-0256b — diff 블록 라인 이중 줄바꿈 수정 (2026-06-15)
- 사용자 보고: 답변 diff 블록의 각 줄마다 빈 줄이 추가됨(이중 줄바꿈).
- 원인: enhanceDiffBlocks 가 `.diff-line`(display:block) span 사이에 `"\n"` 텍스트 노드를 삽입 → `<pre>` 컨텍스트에서 블록 줄바꿈 + 리터럴 줄바꿈이 겹쳐 줄마다 빈 줄.
- [x] app.js/share.js: span 사이 `"\n"` 텍스트 노드 삽입 제거(block span 이 줄 구분 담당) + 미사용 `i` 파라미터 정리
- [x] 캐시버스터 bump(app.js/share.js → `?v=20260615-task0256b-spacing`, 미변경 CSS 는 유지), node --check PASS
- [x] web 재배포(main 1cd19de) + PB-0008 Windows-browser 재검증 PASS — 8줄 diff gap=lineHeight(20px) 단일 줄 간격 실측(2026-06-15, TEST.md §4)

### TASK-0256c — diff 블록 줄 번호(old|new) + 복사 시 마커·번호 제외 (2026-06-15)
- 사용자 요청: ① diff 각 줄에 줄 번호 표시, ② 블록 복사 시 `+`/`-` 마커·줄번호 제외하고 순수 코드만.
- 결정(AskUserQuestion): 줄 번호 스타일 = 양쪽(old | new) GitHub 식.
- 메커니즘: 줄번호+마커는 `data-gutter` 속성 → CSS `::before content`(의사요소=복사 비포함, user-select:none 이중). 코드는 맨 앞 마커 제거 후 textContent → 복사 시 순수 코드.
- [x] enhanceDiffBlocks 재작성(app.js/share.js): buildDiffRows(분류+마커분리+old/new 번호), parseDiffHunkHeader(@@ seed), stripDiffMarker
- [x] CSS(styles.css/share.css): `.diff-line::before` gutter(줄번호+마커, user-select:none) + `--diff-gutter-ch` 폭(2w+3, var fallback 7)
- [x] node 로직 검증(줄번호·마커제거·hunk seed) + node --check, 캐시버스터 bump(app.js/share.js/styles.css/share.css)
- [x] make test + verify-completion PASS + web 재배포(main f0279c3) + PB-0008 PASS — 줄번호 gutter 표시 + getSelection 복사 시 마커·번호 제외 순수 코드 실측(2026-06-15, TEST.md §4)

### TASK-0256d — 캐시버스터 무력화 수정: HTML 엔트리포인트 no-cache (2026-06-15)
- 사용자 보고: 줄번호·복사 형식(0256c)이 적용 안 됨 — 라이브 자산엔 새 코드 baked + PB-0008 통과했으나 브라우저가 옛 app.js 캐시(diff 색은 적용·gutter 없음 = 옛 enhanceDiffBlocks 실행).
- 근본원인: index/admin/share.html 이 FileResponse(ETag/Last-Modified만, Cache-Control 부재) → 브라우저 휴리스틱 캐싱이 옛 HTML 재사용 → 옛 `?v=` 참조 → 캐시버스터 무력화.
- [x] 3 HTML route 에 `Cache-Control: no-cache`(_HTML_NO_CACHE) — 매 로드 조건부 재검증(변경 시 200, 동일 시 304)
- [x] test_html_no_cache(FileResponse monkeypatch 로 3 route no-cache + 올바른 파일 검증) + make test PASS
- [x] web 재배포(main 1c184f8) + 라이브 헤더 검증(3 route no-cache, curl) + 브라우저 새 app.js 로드+gutter 실증(win-browser) — TEST.md §4. 사용자 1회 하드리프레시 안내

### TASK-20260615T183409-ds-list-multiselect — 관리 콘솔 데이터소스 목록 다중 선택 구조 (2026-06-15)
- 목표: `관리 콘솔 > 데이터소스` 목록을 계정·역할·제품과 동일한 다중 선택 구조(행 체크박스 + 전체선택 + 일괄 작업 툴바 + cross-page 배너 + shift-click)로 통일. REQ-20260615-0281 / AC-0512~0514. **Major §12.3**(일괄 파괴적 삭제 포함). 동시세션 PR#251(ds-conn-badge) 선점 → §13.1 rebase·재번호(0280→0281, 0509→0512, REV/CHG-0282→0286).
- 위험/범위: frontend-only(admin.js + admin.html + styles.css grid override 1줄). RBAC(console.manage 재사용)·스키마·엔드포인트(PATCH/DELETE 재사용)·백엔드 무변경. PR#251 leading 네트워크 도트와 행 통합(children=체크박스+도트+main). 동시세션 번호 경합 → timestamp TASK id.
- [x] adminState `datasourceSelected`/`datasourceLastClickIdx` + bulk 어휘(datasources/insight_on/off)
- [x] `_dsRenderList` 재작성(div+체크박스+shift-range) + `_dsFiltered` + stale prune
- [x] `updateDatasourceSelectAllCheckbox`/`renderDatasourceBulkBar`/`renderDatasourceCrossPageBanner`/`_dsBulkTargetable`
- [x] `_runDatasourceBulkAsync`(async partial-fail) + `bulkDatasourceSetInsight` + `bulkDatasourceDelete`
- [x] initialize: select-all 리스너 + Esc 분기 + `assertBulkBarContract` 루프에 datasources 추가
- [x] admin.html: 전체선택 label + cross-page 배너 + role=grid + datasourcesBulkBar(role=toolbar) + 캐시버스터
- [x] styles.css: `#datasourceList .admin-list-row` grid `auto auto 1fr`(체크박스·도트·main, PR#251 --nav override 대체)
- [x] node --check admin.js PASS + 적대적 subagent 코드리뷰 SHIP(BLOCKER 0/MAJOR 0, REV-20260615-0286)
- [x] rebase origin/main + PR#251 충돌 해소(_dsRenderList 도트 통합·docs 재번호) + PR #254
- [x] 머지(PR #254, main 3605443) → web 재배포(repo-web-1 healthy, healthz git_commit=3605443) → **PB-0008 Windows-browser PASS**(CHG/REV-0289 evidence): 14행 [체크박스·연결도트·main] grid `13px 9px 251px`, 전체선택 indeterminate(13/14), bulkBar [인사이트 켜기·끄기·삭제·선택해제] — 마감
### TASK-0279 — 첨부 메타데이터 MySQL agent_memory → PG agent_runtime 통합 cutover (Critical §12.3, 2026-06-15)
- 사용자 결정(AskUserQuestion): 이번 cycle 은 읽기 전환까지 — MySQL 쓰기는 롤백 안전망 유지, MySQL 폐기는 후속 decommission cycle. (동시세션 0277·0278 선점 → 0279 재번호)
- [x] M1 스키마: alembic `0008_core_attachments`(4 PG 테이블, id 보존 bigint PK, version-chain UNIQUE, FK, 명시 GRANT) + `agent_runtime_schema.sql` §6d bootstrap
- [x] 신규 `web.modules.attachment_pg_mirror`(독립 플래그·write 미러·MySQL-shape read 헬퍼; jsonb=::text / timestamptz=AT TIME ZONE UTC 타입 정합)
- [x] M2 dual-write 미러 9 지점(upload/ingest/materialize+supersede/soft-delete/fork/vision-derived/recon-hard-delete/recon-cascade/ingest-degraded) commit 직후 fail-soft
- [x] M3 read cutover 게이트(load_row/list/versions/text_inline/vision_images/sandbox-allowlist + agent_core context) IDOR account_id 가드 동형 + MySQL 폴백
- [x] M4 `scripts/attachment_backfill.py`(4테이블 ON CONFLICT DO NOTHING 멱등 + orphan skip + `--verify` count/SUM/id-diff 게이트)
- [x] M5 신규 `test_attachment_pg_cutover.py` 14 PASS + make test 컨테이너 전체 회귀 0 + ruff + py_compile
- [x] outside-voice 적대 리뷰 2인(데이터 이전 SHIP-WITH-FIXES→흡수 / 인가 표면 SHIP) — REV-20260615-0287. MAJOR-1(size-cap quota max 보수계산)·MINOR-1(derived 부모 선미러)·MINOR-2(docstring) 흡수
- [ ] 라이브 rollout: migrate-first(alembic 0008 superuser) → web+ask-worker 재배포 → dual-write ON → backfill → `--verify` diff=0 게이트 → read flip → 라이브 라운드트립
  - [x] (라이브 backfill 발견) conversation FK 가 orphan 첨부 126/272 이전 차단(05-27 cutover 로 대화 소실, MySQL 원래 no-FK) → alembic 0009 로 conversation FK 제거(conversation_id 컬럼+인덱스 JOIN 유지, 서브테이블 attachment FK 유지). 신규 test E3/E4 + make test 회귀 0. CHG/REV-20260615-0288
- [ ] PB-0008 Windows-browser 시각검증(업로드·목록·버전 체인·삭제가 read=postgres 에서 동작) → merge
- [ ] (decommission 후속 cycle) MySQL 쓰기 제거 + 멱등 ALTER 헬퍼 정리 + write-내부 read PG 전환 + id sequence/identity 부착

### TASK-0282 — datasource 연결 상태 3단계(정상/불안정/끊김) 분류 + 느린(타 리전) 연결 완화 (Major §12.3, 2026-06-16)
- 사용자 보고: `관리 콘솔 > 데이터소스` mysql-mv-qa-* 가 다른 리전이라 느림(연결 테스트 1745ms). 연결은 되는데 네트워크 배지·`작업 화면` 채팅창 제품목록에서 "연결 불안정". 완화 + 회색(끊김)/빨강(불안정)/초록(정상) 3단계 구분 요청.
- 사용자 결정(AskUserQuestion): (Q1) 느린-연결=🔴불안정(빨강), 끊김(회색)과 구분, 정상(초록)은 빠른 연결만. (Q2) 작업화면은 연결되면 허용(fast-fail 은 down 일 때만 — 느려도 사용 가능).
- 근본원인: conn_health.py TCP 선검사 timeout 100ms 고정(`AGENT_CONN_PROBE_TIMEOUT_MS_BASE`)이 다른 리전 핸드셰이크 RTT 를 못 견뎌, 연결 가능한 느린 서버를 1단 TCP 에서 unstable 로 오판(2단 DB probe 까지 못 감). 상태도 2단계뿐(healthy/unstable+unknown) — 끊김/불안정 미분리.
- [x] config.py: `AGENT_CONN_TCP_TIMEOUT_MS`(2000)·`AGENT_CONN_SLOW_MS`(1000)·`AGENT_CONN_DOWN_AFTER_FAILS`(2) + __all__
- [x] conn_health.py: `DOWN` 상태 + `classify()` 단일분류 + `_tcp_timeout_sec`(새 env) + `_driver_timeout_sec` base=SLOW×3 + `_apply_result`(SLOW/연속실패 분기) + `should_fast_fail`(down 한정)
- [x] db.py: foreground connect 소요(ms) 측정 → `_record_health(elapsed_ms=…)` 전달(느린 연결 foreground 도 unstable 일관 — 배지 flapping 방지, 적대리뷰 흡수)
- [x] app.py: `_attach_product_conn_status` _RANK down(최악집계) + `/test` 응답 status 분류
- [x] admin.js: conn_status→state(unstable/down 분리) + `_paintDsConnBadge`/`_paintDsConnDot` 3색 + `_probeDatasourceConn` status 사용
- [x] app.js `connStatusMeta`(down) + styles.css 4셀렉터 `is-unstable`(빨강)/`is-down`(회색) + 캐시버스터 `?v=20260616-conn-tristate`
- [x] 테스트: test_conn_health 재작성(27) + test_product_conn_status(down 최악 2) + test_datasource_test_nonblocking(/test status 2) + make test 컨테이너 전체 회귀 0 + ruff + node --check + CSS brace(1221)
- [x] outside-voice 적대 리뷰 SHIP-WITH-FIXES (REV-20260616-0290) — foreground elapsed flapping + rebase 흡수
- [ ] origin/main rebase(base 4030640 < PR#261 TASK-0277 DatasourceId — silent-revert 방지) → 머지 → web+ask-worker+insight-worker 재배포 → PB-0008 Windows-browser 시각검증(3색 배지·느린연결=빨강·작업화면 사용가능) → 마감

### TASK-0284 — 첨부 3개 이슈: cross-account LLM 주입 / 외부 머신 다운로드 / 파일명 지칭 (Critical §12.3, 2026-06-16)
- 사용자 보고 3건: ①대화에 첨부한 파일을 다른 계정이 그 대화를 조회/이어받아 질문하면 LLM 요청 텍스트에 첨부 미포함(`'+' > 첨부파일 목록` 조회는 됨). ②외부 머신에서 올린 첨부 다운로드 불가. ③assistant 가 파일명이 아닌 첨부 일련번호(attachment_id)로 답변해 혼란.
- 사용자 결정(AskUserQuestion): 이슈1=대화 접근 권한 기준 주입, 이슈2=앱(web FastAPI) 프록시 스트리밍.
- 근본원인(이슈1): 첨부 목록·다운로드는 ConversationId + `_account_can_access_conversation`(own/any) 게이트인데 LLM 주입 3경로(+pending ingest+sandbox allowlist)는 `AND AccountId = %s`(요청자 본인) → fork/이어받기 cross-account 시 목록엔 보이나 주입 SQL 0행.
- [x] (이슈1) app.py `_prepare_text_inline_attachments`·`_prepare_vision_inline_images`·pending ingest·sandbox allowlist 를 conversation_id 우선 스코프(account 폴백)로 전환
- [x] (이슈1) attachment_pg_mirror `_attach_scope_clause` 헬퍼 + `pg_select_text_inline/vision_images/ingested_meta` 시그니처 `(conversation_id, account_id, ...)` + WHERE conversation 스코프
- [x] (이슈2) 신규 `GET /api/attachments/{id}/download` web 프록시 스트리밍(권한 `_account_can_access_attachment` own/any + pending 차단 + octet-stream + `Content-Disposition: attachment` + nosniff) + app.js 다운로드 2지점(메시지 칩·첨부목록) 프록시 경로(same-origin 쿠키) + 캐시버스터
- [x] 테스트: test_task0284_attachment_access.py 9(scope clause·pg_select 3 conversation 스코프·account 폴백·다운로드 라우트 등록/보안계약) + make test 컨테이너 전체 회귀 0 + py_compile + node --check
- [ ] outside-voice 적대 보안 리뷰(RBAC/IDOR) 흡수(REV-20260616-0291)
- [ ] 머지 → 배포(web + ask-worker 재빌드 — agent_core 변경) → 라이브 검증(cross-account 주입·외부 다운로드·파일명 답변) → PB-0008

### TASK-0288 — 권한 회수 미반영 RBAC 결함 4종 수정 + '제품' 권한 2축 분리 (Critical §12.3, 2026-06-16)
- 사용자 보고: 특정 계정에게 권한을 회수해도 여전히 UI·정보 접근 가능 — ① 관리 콘솔 탭(계정·역할·제품·데이터소스·설정)이 권한과 무관하게 모두 노출 ② 감사 로그가 다른 계정 것도 보임 ③ 제품 관리 권한 없이 제품 조회 가능 ④ 데이터소스는 전용 권한 자체가 부재해 항상 노출(치명).
- 사용자 추가 결정(2026-06-16, AskUserQuestion): (a) 데이터소스 권한 read/manage 2단 분리. (b) '제품' 권한을 작업 화면 사용(product.access.*) ↔ 관리 콘솔 구성(product.read/manage) 2축 분리 + read/manage 쪼개기.
- 라이브 재현(테스트 계정 id=29, console.access+audit.read.own 보유): `GET /api/admin/products`→200(8건, ③ 결함), `/api/admin/datasources`→200(148건, ④ 결함), `/accounts`·`/roles`·`/system-prompts`→403(정상). 감사로그 scope=own·본인 target row만·facet=self만(② 백엔드 정상 — "다른 계정 로그"는 테스트 계정이 audit.read.any[admin/dba 자동부여] 실보유 시).
- [x] 백엔드 카탈로그: `datasource.read`/`datasource.manage`(group='datasource') + `product.read`(group='product') 신설. 동적 `product.access.*` group 'product'→'product_access' 신규등록+멱등 마이그레이션 UPDATE.
- [x] 백엔드 게이팅: datasource GET=`_account_has_any_permission(read,manage)` + databases GET=read|manage + test=manage + `_ds_write_common` need 에 datasource.manage. product GET(list/insight-coverage/db-insights/datasources)=read|manage.
- [x] 백엔드 catchup: admin 역할에 datasource.read/manage·product.read backfill(lockout 방지, TASK-0047 류).
- [x] 프론트 admin.js: `applyAdminTabVisibility()` 전 탭 게이팅(ADMIN_TAB_PERMISSIONS) + 그룹 라벨/구분선 숨김 + 활성탭 fallback. 권한 편집기 그룹 재배선(datasource·product 관리권 section, product_access 운영권 section) + 종속성 + 동적카드 product_access 재타겟. datasource 탭 관리버튼 datasource.manage 게이트. 캐시버스터 `?v=20260616-task0288-rbac-gating`.
- [x] 테스트: jsdom `verify_admin_tab_gating.mjs` 34 PASS + make test 컨테이너 전체 회귀 0(영향 테스트 4개 신규 계약 갱신: test_datasource_delete·test_db_insights·test_insight_coverage·test_permission_dependency_map) + node --check + py ast.parse.
- [x] outside-voice 적대 보안 리뷰 SHIP(REV-20260616-0299) — bypass·lockout·superset·group 마이그레이션 enforce-무관·override 회수·IDOR 7항목 코드대조 안전. MINOR 2(datasource 탭 버튼 게이트 정합[흡수]·product-datasource 바인딩 console.manage 유지[accepted])+NIT 1(docstring[흡수]).
- [ ] 머지 → 배포(web 재빌드, deploy_scope: included) → 라이브 재검증(테스트계정 products/datasources 403 전환·탭 숨김) → PB-0008 Windows-browser 시각검증 → 마감.

### TASK-0293 — 감사 로그 `.own` Actor-only + 대시보드 위젯 데이터 권한 게이팅 (Critical §12.3, 2026-06-16)
- 사용자 보고(TASK-0288 후속): ① 감사 로그에 Actor 가 아닌 **TargetAccount 가 자신**일 경우의 타인 행위(관리자 조치)도 노출됨. ② 대시보드에서 권한 없는 항목의 정보가 그대로 전달됨 — UI 접근뿐 아니라 데이터 전달에 권한검증 필요.
- 사용자 결정(2026-06-16): 감사 `.own` = **Actor-only**(내가 수행한 행위만; target=self 제외). 기존 TASK-0073 E1 '사용자 결정 B'(admin→user 투명성) 반전.
- [x] Part A: `_audit_build_self_filter_sql` → `WHERE ActorAccountId = :self`(OR TargetAccountId 제거). resources facet `.own` raw inline 도 Actor-only. list/single/profile×2/facet 전 경로 정합(공유 헬퍼). docstring/주석/SECURITY.md §9.1 갱신.
- [x] Part B: `_DASHBOARD_WIDGETS` coarse console.access → 리소스별 권한(accounts→account.read, roles→role.read, products→[product.read|manage], datasources→[datasource.read|manage], conversations→conversation.list.any). 신규 `_actor_can_see_widget`(OR superset). overview catalog + `_isolate` 데이터 양쪽 게이팅. usage/audits/grant_health/pending 유지.
- [x] 테스트: test_dashboard_overview.py 갱신(console-only→리소스 위젯 부재·신규 superset 게이팅·admin 전위젯·default_prefs·window propagation 5케이스) + test_audit_rbac.py smoke(s3 Actor-only·s3a target-hidden 반전) + make test 컨테이너 회귀 0.
- [x] outside-voice 적대 보안 리뷰 SHIP(REV-20260616-0305) — audit 6경로 OR-Target 잔존 0·under-exposure 무·`.any` 무영향·위젯 catalog/widgets/프런트 3중 정합·prefs 우회 불가 8항목 코드대조. MINOR=profile docstring(흡수).
- [ ] 머지 → 배포(web 재빌드, deploy_scope: included) → 라이브 재검증(테스트계정 .own target row 부재·console.access-only 대시보드 리소스 위젯 데이터 0) → 마감.

### TASK-0294 — 대시보드 위젯 데이터 `.own`/`.any` 세분화 스코핑 (Critical §12.3, 2026-06-17)
- 사용자 보고(TASK-0293 후속): 제한 권한(내 감사 조회만) 보유자인데 대시보드에서 다른 계정 정보가 모두 보임. 권한별로 종속적인 부분을 각 보유 권한마다 세분화해 출력 제한 필요 — 감사뿐 아니라 모든 권한 검토.
- 조사 결론(Explore ×2): 데이터 **엔드포인트**는 전부 `.own`/`.any` 정상 스코핑(TASK-0072/0293). 누출은 **대시보드 위젯**뿐 — 위젯 함수가 actor/scope 인자를 안 받아 all-or-nothing. 특히 `_dash_widget_audits` 의 by_actor(`JOIN WebAccounts GROUP BY ActorAccountId`)가 타 계정 username 노출, `audit.read.any` 로만 게이팅(.own 보유자는 self-scoped 버전 부재).
- [x] `_widget_data_scope(actor, any_perm)` 신설(any 보유→'any', else 'own').
- [x] `_dash_widget_audits(scope, account_id)`: `.own` → 전 쿼리 `AND ActorAccountId=:self` + by_actor 생략 + "(내 활동)". `.any` → 기존. fail-closed(account_id None→-1).
- [x] `_dash_widget_conversations(scope, account_id)`: `.own` → 전 쿼리 `WHERE owner_account_id=:self`(`_w` 헬퍼 parameterized) + '활성 소유자' metric 생략 + "(내 대화)". `.any` → 기존.
- [x] `_DASHBOARD_WIDGETS`: audits→[audit.read.own, audit.read.any], conversations→[conversation.list.own, conversation.list.any]. admin_overview 가 scope+account_id(=인증 actor.id) 전달.
- [x] 테스트: test_dashboard_overview.py(window propagation scope kwargs + 신규 `.own` self-scope 가시성·scope='own'·account_id 전달 검증) + make test 컨테이너 회귀 0.
- [x] outside-voice 적대 보안 리뷰 SHIP(REV-20260617-0306) — SQL injection 0(parameterized)·`.own` self-scope 완전(5쿼리 누락 0·by_actor/활성소유자 생략)·scope 결정 정확·가시성↔데이터 정합·account_id 인증값·`.any` byte-identical 무회귀·accounts/usage 개별 PII 미노출 7항목. D1(fail-open) 흡수.
- [ ] 머지 → 배포(web 재빌드, deploy_scope: included) → 라이브 재검증(`.own` 계정 audits/conversations 위젯 self-scoped·by_actor/활성소유자 부재) + PB-0008 → 마감.

### TASK-0300 — 관리 콘솔 계정/역할 권한 편집 self-scope (privilege escalation 방지, Critical §12.3, 2026-06-17)
- 사용자 보고/요청: `관리 콘솔 > 계정` 에서 자기 자신이 보유한 권한을 넘어서는 권한은 숨김 처리 + 설정 불가하도록 구성.
- 사용자 결정(2026-06-17, /_template:entry Critical 계획 승인): ① 미보유 권한 = **allow·deny 모두 불가(완전 숨김·차단)**("숨김 처리" 문구 충실). ② 적용 범위 = **계정 + 역할 둘 다**(역할 경유 우회 차단).
- 발견 리스크(데이터 손실): `admin_update_account`/`admin_update_role` 은 override 맵/permission_codes 를 **전체 교체** 후 delete-all-then-insert. 프론트가 행을 숨기면 숨긴 권한의 기존 값이 payload 에서 누락→삭제됨 → 백엔드·프론트 모두 **범위 밖 기존 값 보존(merge)** 필수.
- [x] 백엔드 정본: 신규 `_actor_editable_permission_codes` + `_enforce_override_self_scope`(계정) + `_enforce_role_permission_self_scope`(역할). 미보유 권한 allow/deny 시 403, 범위 밖 기존 값 merge 보존. `admin_update_account`(normalize 직후)·`admin_update_role`(validate 직후·survivor 직전) wiring. 기존 `*.override.manage`/`role.permission.manage` 게이트와 직교(추가).
- [x] 프론트 admin.js: `renderPermissionGrid(opts.allowedCodes)` 필터(미보유 행 미생성·빈 그룹/section 제거·product_access 컨테이너 보존). `renderAccountDetail`/`renderRoleDetail` 이 `adminState.me.permissions` 보유 code 로 allowedCodes 구성+전달+안내문구. 제품카드 `buildAccountProductOverrideList`/`buildRoleProductCardList` 미보유 `product.access.*` 숨김. onChange 숨긴 값 보존. 캐시버스터 `?v=20260617-task0300-perm-self-scope`.
- [x] 테스트: `test_perm_self_scope.py`(ast 추출 실 helper 12 PASS — escalation 403·deny 차단·merge 보존·역할 add/remove) + jsdom `verify_perm_self_scope.mjs`(실 `renderPermissionGrid` 13 PASS — 미보유 행 숨김·빈 그룹 제거·컨테이너 보존·하위호환) + node --check + py ast.parse.
- [x] 백엔드 추가(외부리뷰 우회경로 전수): `admin_create_role`(역할 생성 경유) 가드 + `_role_grant_excess_for_actor` 신설 — `admin_update_account` 역할 *배정* escalation 차단(외부리뷰 MAJOR-1, 사용자 결정 '배정도 차단'). 프론트 역할 드롭다운 배정불가 역할 숨김.
- [x] outside-voice 적대 보안 리뷰(RBAC 필수, [[feedback_outside_voice_for_rbac]]) SHIP-WITH-FIXES(REV-20260617-0307) — 직접 우회 0(10/10 적대케이스)·merge/lockout/editable 안전. MAJOR-1(역할 배정 우회)→배정 가드 추가(사용자 결정). MINOR-1(product.access self-scope)→포함 유지(사용자 결정). MINOR-2(비대칭 주석)→흡수.
- [x] 머지(main a9effd6, PR #313) → 배포(web 재빌드, deploy_scope: included) → 라이브 403 검증 PASS(pgpark/usermanager: 미보유 audit.purge allow·deny 403·보유 account.read 200·admin 역할배정 403) → PB-0008 Windows-browser PASS(미보유 행 숨김·실 Chrome 가시성) → 마감. evidence CHG/REV-20260617-0308, `artifacts/pb0008-task0300/perm-self-scope-hidden.png`.

### TASK-0301 — 관리 콘솔 제품 목록 항목 글꼴 크기 정합 (Minor §12.3, 2026-06-17)
- 사용자 보고: `관리 콘솔 > 제품 > [각 항목]` 의 글꼴 크기가 계정·역할·데이터소스 목록 항목보다 너무 큼.
- 근본원인: `renderProductList()` 의 제품명 요소가 `admin-account-name`(15px, 700) 을 사용 — 다른 목록(계정·역할·데이터소스)은 `admin-list-row-name`(13px, 600) 사용. 컨테이너도 `admin-list-main`(CSS 미정의) vs `admin-list-row-main`(flex column, gap 2px, min-width 0) 불일치.
- [x] admin.js `renderProductList()`: 이름 요소 `div.admin-account-name` → `span.admin-list-row-name`, 컨테이너 `admin-list-main` → `admin-list-row-main`. 2줄 변경, frontend-only.
- [x] 배포(web 재빌드, deploy_scope: included) → 라이브 확인(제품 탭 항목 글꼴이 계정/역할과 동일 크기) → 마감. PB-0008 render-injection PASS(productFontSize=13px/600=accountFontSize, match=true). 스크린샷 `artifacts/pb0008-task0301/products_font_fix.png`. CHG-20260617-0311 / REV-20260617-0311[SKIPPED].

### TASK-0302 — 관리 콘솔 제품 일괄 삭제 미적용 (다중선택 pending→"마지막만 적용") + bulk staging 목록 즉시 반영 (Major §12.3, 2026-06-17)
- 사용자 보고(/_template:entry): 관리 콘솔에서 다중선택(체크박스)의 변경점이 pending 돼도 "모두 적용" 시 마지막으로 수정한 사항만 적용됨.
- 전수 조사(코드 + 백엔드 실측 + 라이브 브라우저): 계정·역할·제품 일괄 활성/비활성, 권한 grid, 제품 상세, 시스템 프롬프트, 대시보드 위젯, 신규 역할 다중 생성, **단일 제품 삭제(직접 DELETE)** 는 전부 정상. 배포본 admin.js md5 = 소스 동일. 깨진 것은 **제품 일괄 삭제**뿐.
- 근본 원인: `applyAllPending` 의 productMeta 루프가 `_delete` 플래그 미처리(account/role 루프와 비대칭) → bulk "삭제 pending" 이 빈 body→요청 0건→pending 만 조용히 비워짐(삭제 0건). 혼합 편집(제품 메타 수정 + 다중 삭제) 시 수정한 제품만 PATCH 반영 → "마지막으로 수정한 것만 적용"으로 보임.
- [x] `applyAllPending` productMeta `_delete` → `DELETE /api/admin/products/{id}`(단일 삭제와 동일 엔드포인트, account/role 정합).
- [x] bulkProductDelete/bulkProductSetActive/bulkAccount*/bulkRole*: staging 후 `renderXList()` — pending 점(•)/삭제대기 즉시 반영.
- [x] 제품 행 pending 마커(`has-pending`/`is-to-delete` + dot) 신설 — `renderProductList` 재렌더가 실제 표시(외부리뷰 MINOR 흡수).
- [x] 백엔드 `admin_delete_product`: 기본 제품(IsDefault) 삭제 **409** 차단 + 미존재 **404**(외부리뷰 MAJOR 흡수 — bulk DELETE 경로가 서버 도달, client-trust 가드 보강; 단일 삭제도 보호).
- [x] 라이브 검증(실 running stack + 브라우저): 수정 전 제품 3개 일괄 삭제 → 0건 삭제, 수정 후 → 3건 전부 삭제. is-to-delete rows=2·pendingDots=2. 회귀(역할 일괄 비활성 2/2) 정상. node --check + py ast.parse.
- [x] outside-voice 적대 리뷰 SHIP-WITH-FIXES(REV-20260617-0312) — 의도외 삭제 0(refuted)·partial-fail 안전·기본제품 backend 가드(MAJOR 흡수)·제품 행 마커(MINOR 흡수).
- [ ] 머지 → 배포(web 재빌드, deploy_scope: included) → 라이브 재검증(기본 제품 삭제 409·일괄 삭제 N건 전부·pending 마커) + PB-0008 Windows-browser → 마감.

### TASK-20260618T022006 — 관리 콘솔 데이터소스 '새 항목' 엔진 선택 = 아이콘 드롭다운 (REQ-20260618-0315, AC-0572, Minor §12.3, 2026-06-18)
- 사용자 보고(/_template:entry): `관리 콘솔 > 데이터소스` 의 새 항목 추가 시 엔진을 **드롭다운**으로 선택하게 하고, **식별하기 쉽도록 각 엔진의 서비스 아이콘**을 웹에서 탐색해 적절히 구성.
- 근본: `_dsRenderForm` 의 엔진 입력이 자유 텍스트 input("엔진 (mysql|mssql)")이라 오타 가능 + 식별 보조 없음. 백엔드는 이미 engine ∈ {mysql, mssql} 만 허용(app.py POST/PATCH `/api/admin/datasources`) — FE 가드·식별 부재였던 것.
- [x] admin.js: `ENGINE_CATALOG`(mysql|mssql — 라벨·기본포트·브랜드색·아이콘) + `engineMeta()` 폴백(미지원/공백/null→mysql, 백엔드 기본값 정합) + `_dsBuildEngineField` 커스텀 드롭다운(아이콘+라벨 트리거, role=listbox/option·aria-selected·↓↑/Enter/Esc, hidden `valueHolder` 로 기존 텍스트 input 의 `.value` 계약 유지) 신설.
- [x] admin.js `_dsRenderForm`: 엔진 자유 텍스트 → `_dsBuildEngineField` 드롭다운 교체. save 핸들러는 `inputs.engine.value`(hidden) 를 그대로 읽어 POST/PATCH `body.engine` 무변경(계약 보존). 엔진 변경 시 포트 placeholder=엔진 기본포트(mysql 3306/mssql 1433, **값 강제변경 안 함** — 사용자 입력 보존).
- [x] 아이콘 = 공식 서비스 브랜드 마크 **inline SVG baking**(외부 CDN 핫링크 0 — dashboard sparkline·프로필 identicon 과 동일 "외부 의존 0" baked 정책). MySQL=simple-icons 돌고래(teal #00758F) · MSSQL=devicon 공식 SQL Server 마크(red #EE352C). 단색 path `fill=currentColor` + `.engine-icon` color 로 브랜드색.
- [x] styles.css: `.engine-picker*`/`.engine-option*`/`.engine-icon` 신설. 목록은 admin-db-picker 처럼 **inline-flow(position:absolute 금지)** — `.admin-detail-col`(overflow-y:auto)이 absolute 드롭다운을 잘라내던 TASK-0240 문제 답습 회피. admin.html 캐시버스터 `?v=20260618-engine-dropdown`.
- [x] 검증: jsdom `verify_engine_dropdown.mjs` 36 PASS(드롭다운 구조·옵션별 브랜드 svg·hidden 값 계약·선택→repaint/aria/onChange·engineMeta 폴백·CSS inline-flow) + node --check. frontend-only(백엔드·RBAC·스키마·엔드포인트·데이터 0).
- [x] outside-voice 적대 리뷰(general-purpose, REFUTE 지향) **SHIP**(REV-20260618-0315) — 8가설 전부 REFUTED: 저장 계약 보존·XSS 0(아이콘=하드코딩 상수)·편집 prefill 정상·리스너 패턴 기존 정합(회귀 아님)·클리핑 0(inline-flow)·a11y 정상·포트 placeholder-only(데이터손실 0)·폴백 무해. BLOCKER/MAJOR 0.
- [x] 머지(main da227eb, PR #325) → 배포(web 재빌드 + 컨테이너 재생성, deploy_scope: included) → PB-0008 1차 실 Windows Chrome: 데이터소스 탭 → '+ 새 데이터소스' → 엔진 드롭다운 렌더·트리거 라벨 "MySQL"·SVG 아이콘·**색 rgb(0,117,143)=#00758F 정확**. 단 `.engine-icon` CSS 미적용(width auto·아이콘 52px·버튼 border/padding 0) 발견.
- [x] **PB-0008 발견 버그 fix(후속 cycle)**: styles.css 에 엔진 규칙을 추가했으나 admin.html 의 `styles.css?v=` cache-buster 를 안 올려, 캐시된 브라우저가 옛 CSS(엔진 규칙 0)를 수신 → 미스타일. admin.html + index.html(공유 styles.css) cache-buster 를 `?v=20260618-engine-dropdown` 으로 bump. CHG-20260618-0316. (교훈: styles.css 변경 시 이를 링크하는 모든 페이지의 cache-buster 를 bump.)
- [x] 재배포(web, fix main `071020c` PR #326) → PB-0008 재검증 PASS: `.engine-icon` width 18px·버튼 border 1px/padding 10px·드롭다운 열림·옵션 2개(MySQL #00758F / Microsoft SQL Server #EE352C 브랜드 아이콘·색)·선택 시 트리거·포트 placeholder 1433 갱신. evidence `artifacts/pb0008-engine-dropdown/{engine-dropdown-open,engine-mssql-selected}.png`. **마감**(CHG/REV-20260618T030014 evidence).

### TASK-20260618T024517-ai-claude-product-picker-search — 작업 화면 제품 선택 드롭업 명칭 검색 필터 (Minor §12.3, 2026-06-18)
- 사용자 보고(/_template:entry): 서비스 내 요청문 텍스트박스에서 제품을 선택하는 목록 팝업의 제품들이 많아질수록 탐색이 번거로움. 제품 명칭 검색 필터 구성 요청.
- 근본/설계: 제품 선택 드롭업(`#productDropupMenu`)은 `renderProductDropupMenu`(app.js)가 JS 로 동적 렌더하며 검색 수단이 없었음. 제품 수가 임계 이상일 때만 드롭업 상단에 명칭 검색 입력칸을 노출하고, 입력에 따라 항목을 클라이언트측에서 실시간 필터링. frontend-only(app.js/styles.css/index.html) — 백엔드·RBAC·스키마·엔드포인트·데이터 0. 검색은 백엔드가 권한 게이트(`state.products`, TASK-0295)한 목록 위에서만 동작 → 접근 제어 우회 불가.
- [x] app.js: `PRODUCT_DROPUP_SEARCH_MIN`(=6) 상수 + `renderProductDropupMenu` 리팩토링(pinned ≥ 임계 시 검색 입력 삽입, no-result 동적 안내) + 신규 `buildProductDropupSearch()`(sticky input, input→필터) + 신규 `filterProductDropupItems(query)`(`.hidden` 토글, 재렌더 없이 포커스/IME 유지) + `buildProductDropupItem` `data-search`(소문자 라벨) + `openProductDropup` 검색 입력 자동 focus.
- [x] styles.css: `.product-dropup-search-wrap`(sticky top:0) + `.product-dropup-search`(+:focus/::placeholder) + `.product-dropup-no-result`.
- [x] index.html: styles.css/app.js 캐시버스터 `?v=20260618-product-picker-search`.
- [x] 검증(정적): `tests/verify_product_picker_search.mjs` 27/27 PASS(jsdom — 입력 노출 조건·data-search·product_key/한글명/부분일치 다건/0건 no-result/복원/auto 포함·focus 코드) + `node --check app.js`.
- [x] REV-20260618T024517-ai-claude-product-picker-search [SKIPPED:frontend-ui-search-filter-no-backend-no-rbac] — Minor frontend 비파괴, RBAC/백엔드 무변경(자체 점검 6항목 REVIEW.md).
- [x] 식별자: 고병렬 동시세션 rebase(2회) 충돌(REQ-0288/AC-0572·0573 타 세션 선점) → grep max 재번호 REQ-20260618-0317/AC-0574·0575, docs --ours+재삽입 keep-both([[feedback_feature_doc_id_grep_max]]).
- [x] 머지(main ebd2849, PR #327 squash; 고병렬 rebase 2회) → 배포(web 재빌드, deploy_scope: included, /healthz git_commit=ebd2849·서빙자산 baked) → 라이브 PB-0008 Windows-browser **PASS**(pinned 10개≥6 → 검색박스 노출·placeholder·sticky top:0·자동 focus·`dk_`→2건·미매칭→"검색 결과가 없습니다"·비움→복원) → **마감**. evidence CHG/REV-20260618T031450, `artifacts/pb0008-product-picker-search/search-filter-dk.png`.
- [ ] 재배포(web) → PB-0008 재검증(`.engine-icon` width 18px·버튼 border/padding·드롭다운 열림·옵션 2개 아이콘·MySQL/SQL Server 브랜드색) PASS → 마감.

### TASK-20260618T025755 — '+ 데이터베이스 추가' picker 검색 필터 + 정규식 일괄 선택 (REQ-20260618-0317, AC-0574·0575, Major §12.3, 2026-06-18)
- 사용자 보고(/_template:entry): 사내 데이터소스는 DB 추가/삭제가 잦아 제품의 DB 구성을 매번 바꾸기 번거롭다. `관리 콘솔 > 제품 > '데이터 소스 & 접근 가능 데이터베이스' > '+ 데이터베이스 추가'` 항목에 **검색 필터** 추가 + **정규식으로 임의 DB 들을 미리 선택**(선택 목록 조회 가능). 그 외 잦은 DB 변경에 대한 모범 대응책 제안.
- 근본: `buildPicker()`(admin.js) 의 후보 DB 목록은 체크박스 리스트만 있어, 데이터소스에 DB 가 많으면 원하는 것을 찾아 하나씩 토글해야 했다(검색·패턴 선택 부재). 후보 DB(`availableUserDbs`)·선택(draft)·쓰기 경로(pending→모두 적용)는 이미 존재 — 탐색/선택 UX 만 부재.
- [x] admin.js 모듈 helper 4종 신설(순수/DOM, jsdom 검증 대상): `DB_PICKER_SEARCH_MIN`(=6), `dbPickerFilterNames`(부분일치 필터), `dbPickerRegexMatches`(정규식 `i` 매칭 `{ok,matches,error}`), `applyDbPickerSearch`(항목 `.hidden` 토글+표시수), `applyDbPickerRegexHighlight`(일치 `.is-regex-match`+count).
- [x] admin.js `buildPicker()`: 후보 ≥ `DB_PICKER_SEARCH_MIN` 일 때 sticky toolbar 삽입 — 검색 입력(라이브 부분일치) + 정규식 입력(라이브 카운트·하이라이트) + "일치 선택" 버튼(Enter 지원) + "선택됨 N개" 요약 + 검색결과없음/정규식오류 안내. 항목에 `dataset.search`/`dataset.dbname` 부여. 검색·정규식 입력값은 렌더 함수 클로저(`_dbPickerQuery`/`_dbPickerRegex`)에 보존해 재렌더(비동기 insight)에도 유지.
- [x] 정규식 일괄 선택 = **additive**(`draft.push` 만, 기존 선택 해제 없음) + 체크박스 단일 추가와 동일 검증(시스템/내부 스키마 제외·비-MSSQL 이름 형식·MSSQL 대소문자 보존) 통과분만. 선택 후 redrawChips+buildPicker 재반영 + toast(M개 중 K개 추가). 선택 목록은 기존 `cov-db-list` 에 행 단위 표시("조회 가능" 충족).
- [x] styles.css: `.admin-db-picker-toolbar`(sticky) + `.admin-db-picker-search`/`.admin-db-picker-regex`(+focus/placeholder) + `.admin-db-picker-regex-row`/`-count`/`-btn`/`-err` + `.admin-db-picker-selected-count` + `.admin-db-picker-item.is-regex-match` 하이라이트 + `.admin-db-picker-no-result`. admin.html(styles.css+admin.js)·index.html(styles.css) cache-buster `?v=20260618-dbpicker-search-regex`.
- [x] 검증: jsdom `tests/verify_dbpicker_search_regex.mjs` **33/33 PASS**(순수 검색 5·정규식 6·DOM 검색 4·DOM 하이라이트 3·wiring 7·CSS/cache-buster 8) + `node --check admin.js`. frontend-only(백엔드·RBAC·스키마·엔드포인트·데이터 0).
- [x] 잦은 DB 구성 변경 모범 대응책 제안서 작성: `docs/PROPOSAL-frequent-db-config-changes.md`.
- [x] outside-voice/panel: §18.8 — frontend-only·RBAC/스키마/엔드포인트 0·기존 검증/쓰기 경로 재사용이라 패널 생략(REV-20260618T025755 [SKIPPED] 기록). 보안 경계 변화 없음.
- [x] 머지(main, PR #331) → 배포(web 재빌드 main 14c3280, deploy_scope: included; #327 충돌 rebase keep-both) → **PB-0008 Windows-browser PASS**(render-injection: sticky toolbar·검색 3/8·결과없음·정규식 count 3·하이라이트 primary@12%·hidden display:none·additive; 시각 evidence picker-search-regex.png). CHG/REV-20260618T025755 evidence. 마감.
### TASK-20260618T030534 — 데이터소스 목록 행에 엔진 서비스 아이콘(연결 도트 우측) (REQ-20260618-0318, AC-0576, Minor §12.3, 2026-06-18)
- 사용자 보고(/_template:entry 후속): TASK-20260618T022006(엔진 드롭다운) 에 이어, `관리 콘솔 > 데이터소스` **목록에서도 식별하기 쉽도록** 네트워크 연결 뱃지(도트) **우측에** 엔진 서비스 아이콘을 구성.
- 근본: `_dsRenderList` 의 목록 행은 `row.append(cb, dot, main)`(체크박스·연결도트·main[이름+엔진 텍스트배지+host:port]) 3열 grid 였고, 엔진은 텍스트 배지(`.admin-badge` "mysql"/"mssql")로만 식별. 브랜드 아이콘 식별 보조 부재.
- [x] admin.js `_dsRenderList`: 연결 도트 우측에 `engineMeta(ds.engine)` 의 브랜드 아이콘을 `.ds-list-engine-icon`(role=img·`aria-label/title="엔진: <label>"`·브랜드색)으로 만들어 `row.append(cb, dot, engIcon, main)` — 드롭다운(`_dsBuildEngineField`)과 동일한 engineMeta 재사용(아이콘+색 단일 출처). 기존 텍스트 배지는 유지(additive, 식별성↑).
- [x] styles.css: `#datasourceList .admin-list-row` grid `auto auto 1fr` → `auto auto auto 1fr`(children cb·dot·engIcon·main 1:1, 고정폭 컬럼이라 행 간 정렬 안정 — 행 목록 컬럼 정합 정책) + `.ds-list-engine-icon`(16px·align center·flex none). admin.html admin.js+styles.css 캐시버스터 `?v=20260618-ds-list-engine-icon`(공유 styles.css 변경 — 직전 cache-buster 교훈 적용).
- [x] 검증: jsdom `verify_ds_list_engine_icon.mjs` 17 PASS(아이콘 빌드 mysql/mssql/폴백·브랜드색·aria·도트 우측 배선·이전 3-append 잔존 0·4열 grid·아이콘 CSS) + node --check. frontend-only(백엔드·RBAC·스키마·엔드포인트·데이터 0).
- [x] outside-voice 패널 SKIP — Minor 추가 변경 + 이미 적대 검증된 engineMeta/아이콘 재사용(TASK-20260618T022006 REV-20260618-0315). REV-20260618T030534 [SKIPPED:frontend-ui-list-icon-no-backend-no-rbac]. 화면 정본 = PB-0008.
- [x] 머지(main `8a2c886`, PR #332) → 배포(web 재빌드 + 컨테이너 재생성, deploy_scope: included) → PB-0008 Windows-browser PASS: `#datasourceList` 18행 children `[cb, dot, engIcon, main]`(엔진 아이콘 도트 우측)·grid `13px 9px 16px 225px`(4열)·MySQL #00758F·Microsoft SQL Server #EE352C·아이콘 컬럼 leftAlignSpread=0px(정렬 무붕괴). evidence `artifacts/pb0008-ds-list-engine-icon/ds-list-engine-icons.png`. **마감**(CHG/REV-20260618T031747 evidence).
- [ ] 머지 → 배포(web 재빌드, deploy_scope: included) → 라이브 PB-0008 Windows-browser(제품 13개 → 검색박스 노출·명칭 입력→필터·sticky·focus·결과없음) → 마감.

### TASK-0303 — 역할/계정 '제품 사용(product_access)' 다중선택 무효 + 그룹 카운트 "0/0" 수정 (Major §12.3, 2026-06-18)
- 사용자 보고: ① `역할 > [항목] > 운영 권한 > 제품 사용` 의 제품별 접근 다중선택·적용이 제대로 안 됨. ② `제품 사용 (작업 화면)` 권한이 항상 "0/0" 으로 출력됨.
- 근본 원인: ① 제품 카드 토글 핸들러(`buildRoleProductCardList` onToggle·`buildAccountProductOverrideList` onChange)가 **렌더 시점 스냅샷**(`role.permission_codes`/`account.permission_overrides`)을 읽음 → 매 토글이 서버 스냅샷+단건으로 전체 교체 → 직전 토글의 pending 을 잃어 **마지막 1개만 남음**(다중선택 무효). 역할 메인 grid onChange 의 `existingDynamic`/`preservedHidden` 도 스냅샷 기반이라 정적↔제품 상호 클로버. ② product_access 그룹은 빈 컨테이너로 렌더되고 카드는 **그 후** 임베드되는데, `_updateCheckboxGroupSummary` 가 임베드 전(체크박스 0개)에 1회만 실행 → 배지가 "0/0" 고정.
- [x] 제품 카드 onToggle/onChange: 라이브 `mergedRole`/`mergedAccount`(pending 오버레이) 읽기로 전환 → 단건만 가감, 다중선택 누적.
- [x] 역할 메인 grid onChange: `existingDynamic`/`preservedHidden` 를 라이브 `mergedRole` 에서 읽어 정적↔제품 상호 클로버 방지(TASK-0300 self-scope hidden 보존 정합 유지).
- [x] 카드 임베드 직후 `_updateCheckboxGroupSummary`/`_updateOverrideGroupSummary` 재집계(역할 N/M·계정 허용/거부/상속) + 부여 있으면 그룹 펼침. 토글 시에도 `wrap.closest('details.permission-group')` 로 배지 라이브 갱신.
- [x] 검증: `tests/verify_product_access_multiselect.mjs` 6 PASS(실 추출 mergedRole/setRolePending/mergedAccount/setAccountPending/_updateCheckboxGroupSummary — 역할·계정 다중선택 누적·OLD 스냅샷 버그 대조군·정적↔제품 클로버 방지·카운트 0/0→3/16) + node --check.
- [x] outside-voice 적대 리뷰(RBAC-인접, [[feedback_outside_voice_for_rbac]]) **SHIP** — 권한 손실 0·self-scope(TASK-0300) 무회귀·escalation 0(백엔드 `_enforce_*_self_scope` 정본)·역할 divergence 0·카운트 inflation 0·신규역할 안전, 6항목 전부 refuted. M1(그룹 모두선택 버튼)·M2(계정 메인 비대칭)=기존·범위외.
- [ ] 머지 → 배포(web 재빌드, deploy_scope: included) → 라이브 재검증(역할 제품 3개 토글→3개 staged·배지 N/M·적용 후 영속) + PB-0008 Windows-browser → 마감.

### TASK-20260618T044318 — 제품 DB allowlist 정규식 규칙 자동 동기화 (REQ-20260618-0322, AC-0580·0581, Critical §12.3, 2026-06-18)
- 사용자 요청: 정규식 선택(TASK-20260618T025755)을 "한 번 구성해두면 데이터소스 변화 시 제품에 자동 반영"되게 확장.
- 사용자 결정(AskUserQuestion): ①자동 즉시 적용 → ②outside-voice NOT-SHIP → **안전 하이브리드** → ③**풀스코프(백그라운드 포함)**.
- [x] outside-voice 설계 리뷰: 순수 자동적용 NOT-SHIP(allowlist=에이전트 접근 경계, "DB 이름 지을 수 있는 누구나 → AI 즉시 노출"). BLOCKER B1~B5·M2~M6 도출 → 안전 하이브리드로 전환.
- [x] 스키마(멱등·비파괴): `WebProductDatasourceDbRules` + `WebProductDatabasePending` + `WebProductDatabases.Source/RuleId`(기존행 manual backfill). probe 에 Source 컬럼 등록(TASK-0047 trap 회피) + slow-path 호출.
- [x] reconcile + 헬퍼: `_validate_db_rule_pattern`(ReDoS)·`_db_rule_excluded_lower`(M2)·`_match_db_rule`(B5)·`_reconcile_product_db_rule`(cap이하+can_manage=자동/else pending=B1, add-only no-op=M4, SortOrder 말미=M5, 생성자 귀속 감사=B3).
- [x] 엔드포인트 5종(GET/PUT/DELETE/preview/approve-pending) — `_db_rule_gate`(product.manage+바인딩, M6) + 파라미터화 SQL.
- [x] B4: 수동 PUT `admin_update_product_databases` 가 manual 행만 교체(rule 행 보존) + 프론트 PUT body `source==='rule'` 제외 + `_list_product_databases` source 반환.
- [x] 백그라운드 `_start_db_rule_reconcile_loop`(env AGENT_DB_RULE_RECONCILE_SEC=300) — creator 활성·비삭제+product.manage 재검증(M3).
- [x] UI: 규칙 에디터(`_renderRuleEditor`)·preview 라이브·pending 1클릭 승인·rule 배지·picker rule 체크박스 비활성·CSS·cache-buster.
- [x] outside-voice 구현 코드 재리뷰: **SHIP-WITH-FIXES**. B1·B3·B4·B5·M2·M4·M6 충족 확인. BLOCKER(ReDoS alternation `(a|a)*`/`(.*a){20}` 우회) → 검증 강화(그룹수량자 `)[*+?{]` 금지·무한수량자≤8·match 방어심층) — catastrophic 0.000s 즉시 [] 실측. MAJOR#1(creator 활성 확인)·#2(rule 체크박스 비활성) 반영. MAJOR#3(approve 패턴 재매칭) 문서화.
- [x] 검증: `tests/verify_db_rule_logic.py` 25/25 + `tests/verify_db_rule_ui.mjs` 17/17 + ast.parse + node --check.
- [x] 머지(PR #341, main) → 배포(web) → **PB-0008 적발 버그**: audit action(admin.product.db_rule.set 등) 미등록 → PUT 500. fix=build_audit_change_json 에 5 action 등록(CHG-20260618T052403-audit-fix). 라이브 preview round-trip OK(실 datasource '11개 일치·신규 0개'). 규칙 에디터 실 렌더 OK(border 1px·저장버튼 primary). 재배포 후 PUT/GET/DELETE round-trip 재검증 → 마감.

### TASK-20260618T061703 — DB allowlist 정규식 규칙 다중 + 종속 UI (REQ-20260618-0323, AC-0582·0583, Major §12.3, 2026-06-18)
- 사용자 요청: 규칙을 여러 개 설정 + 각 규칙에 DB 목록이 종속돼 보이게 UI 구성. TASK-20260618T044318 확장.
- [x] 스키마: UNIQUE 제거 + SortOrder(멱등 마이그레이션, probe 등록, fast-path catchup 등록).
- [x] 백엔드: `_get_product_db_rules`/`_get_db_rule_by_id` + `_reconcile_one_db_rule`/`_reconcile_product_db_rules`(순차·cross-rule dedup) + 복수형 엔드포인트(by-id, IDOR 재검증) + `_list_product_databases` rule_id.
- [x] UI: 규칙 카드(`_buildRuleCard`)+추가/수정 폼(`_buildRuleForm`)+"+ 규칙 추가" + DB 중첩 표시 + redrawChips manual 분리 + CSS.
- [x] outside-voice(다중규칙 격리) SHIP-WITH-FIXES — A~G 확인, BLOCKER 0. MAJOR#1(INSERT IGNORE 중복방지)·#2(fast-path catchup 등록) 반영. MINOR(pending phantom) 무해 문서화.
- [x] 검증: verify_db_rule_logic.py 30/30 + verify_db_rule_ui.mjs 18/18 + ast/node.
- [ ] 머지 → 배포(web, deploy_scope: included) → PB-0008(규칙 2개 추가·각 카드에 DB 중첩·삭제 격리) → 마감.

### TASK-20260619T012028-share-link-expiry — 대화 공유 링크 시간 기반 만료 (설정 가능) (REQ-20260619-0324, AC-0584~0587, Major §12.3, 2026-06-19)
- 사용자 요청(보안 보강 6종 중 ①): 대화공유 링크 만료처리(설정 가능하도록). SECURITY.md §7.2 의 명시 TODO(시간 기반 만료) 구현.
- 사용자 결정: 6개 보안 항목을 1 TASK=1 worktree=1 PR 로 순차 진행, 추천 순서(① 공유링크 만료부터) — AskUserQuestion 2026-06-19.
- [x] 스키마(멱등·비파괴): `WebConversationShares.ExpiresAt DATETIME NULL`(`_ensure_web_share_links_expiry_column`, PolicyVersion 헬퍼 idiom 동형) + `IX_WCS_ExpiresAt` — fast-path(`_ensure_seed_catchup`)+slow-path(`_ensure_web_tables`) 양쪽 등록(기존행 NULL=무기한, 무회귀).
- [x] create(`POST /api/conversations/{cid}/share`): `expires_in_seconds` 옵션(누락/0/음수=무기한, 상한 365일 초과 400). INSERT 가 `ExpiresAt = DATE_ADD(NOW(), INTERVAL %s SECOND)`(DB 시계 도메인, f-string=코드상수만·값은 파라미터화). 응답 + audit(`expires_in_seconds`) 노출.
- [x] 집행(DB NOW() 기준, clock skew 차단): public view 의 ViewCount UPDATE predicate `(ExpiresAt IS NULL OR ExpiresAt > NOW())`(만료뷰 카운트 인플레 차단) + 만료 시 취소와 구분된 410("만료되었습니다") + `_share_row_expired` 헬퍼 재확인. fork 도 만료 410 차단. **410 이 대화 본문/메타 로드보다 먼저**(누출 0).
- [x] list(`GET .../shares`): `IsExpired`(DB NOW()) SELECT + `expires_at`/`is_expired`/`is_revoked` 노출, `is_active = 미취소 ∧ 미만료`.
- [x] 프론트: app.js `promptShareExpiry` 모달(무기한/1일/7일/30일, 취소 시 생성 중단) + body `expires_in_seconds` + 공유 관리 만료일/만료됨 배지. share.html `#shareExpiry` + share.js 만료 렌더 + 410 `body.error` 로 만료/취소 구분. styles.css `.is-expired`/`.share-expiry-*` + index/share cache-buster `?v=20260619-share-expiry`.
- [x] 검증: `tests/test_task20260619_share_expiry.py` 12/12(B1~B9 백엔드 + F1~F3 프론트) + make test 전체 회귀 0(사전존재 `test_product_delete_block_conv` 2건 제외 — main 81185d4 에서도 동일 실패, 본 변경 무관) + py_compile + node --check + CSS brace 1372=1372.
- [x] outside-voice 적대 보안 리뷰(공유=익명 접근경계, [[feedback_outside_voice_for_rbac]]) **SHIP** — 9 probe 전부 refute(만료우회·clock skew/TOCTOU·SQLi·입력검증·무회귀·취소vs만료·audit·프론트XSS·IDOR). BLOCKER/MAJOR 0, MINOR 1(취소-race 라벨, 무해)·NIT 2(probe 자기문서화·boundary 더블카운트, 무해).
- [ ] 머지 → 배포(web 재빌드, deploy_scope 확인) → 라이브 재검증(만료 링크 410·무기한 무회귀) + PB-0008 Windows-browser(만료 모달·관리 배지·뷰 만료 표시) → 마감.
### TASK-20260619T014034 — LLM provider 외부요인 제한 명시 표면화 (web 면, Major §12.3, 2026-06-19)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-19 -->
- 목표: 외부 provider 장애(AWS Bedrock 키 만료 등)로 LLM 이 막힐 때 서비스 사용자가 4 surface 로 명시 확인. 분류·영속·probe 는 agent-core 면(feature-0002 TASK-20260619T014034). 본 면은 web 노출 + UI.
- [x] app.py: `_read_llm_provider_status`(PG read graceful) + `GET /api/llm/health`(인증 게이트·hybrid probe·force=1) + `/api/session`·`_build_ask_status_snapshot` 에 `llm_provider_status` 동봉.
- [x] index.html: 컴포저 상단 배너(`#llmRestrictionBanner`)+'다시 확인' + footer 상태점(`#llmStatusDot`, 툴팁) + 실행단계 패널 노트(`#llmRestrictionPanelNote`). styles.css 4 surface 클래스 + footer 상태점 유지 `:has`. 캐시버스터 bump(styles/app `?v=20260619-llm-restriction`).
- [x] app.js: `applyLlmProviderStatus`(배너/점/패널/send title 일괄) + `renderLlmRestrictionInlineNotice`(대화 인라인, textContent XSS-safe, dedup) + `pollLlmHealth`/`startLlmHealthPolling`(60s + 로드 직후 probe + retry force). `/api/session`·`/api/ask_result` 소비 시 적용; restricted+error 일 때만 인라인 notice.
- [x] 검증: `verify_llm_restriction_surface.mjs` 35(정적 7+CSS 5+wiring 6+jsdom 4-surface 토글 17) + node --check + py_compile(app.py).
- [x] 적대 코드리뷰 → REV-20260619T014034-ai-claude-llm-restriction-notice.
- [ ] 머지 → 배포(web+ask-worker, deploy_scope: included) + 마이그 0011 → PB-0008(restricted 주입 4-surface computed 실측, jsdom 불가 영역) → 마감.

### TASK-20260619T021356-login-attempt-limit — 잘못된 로그인 시도 제한 (계정 잠금 + IP throttle) (REQ-20260619-0325, AC-0588~0591, Critical §12.3, 2026-06-19)
- 사용자 요청(보안 보강 6종 중 ②): 잘못된 로그인 시도 제한. 사용자 결정(AskUserQuestion 2026-06-19): **계정+IP 둘 다(심층방어)**, **보수적 프로파일**(계정 5회→15분 자동해제, IP 20회/10분), 전부 env 설정 가능.
- [x] 스키마(멱등·비파괴): `WebAccounts` 에 `FailedLoginAttempts`/`LockedUntilAt`/`LastFailedLoginAt` + `IX_WebAccounts_LockedUntil`(`_ensure_login_lockout_schema`, must_change_password idiom). fast(`_ensure_seed_catchup`)+slow(`_ensure_web_tables`) 양 경로. 기존 행 DEFAULT 0/NULL=무회귀.
- [x] config: `WEB_LOGIN_MAX_FAILED_ATTEMPTS`(5)/`WEB_LOGIN_LOCKOUT_MINUTES`(15)/`WEB_LOGIN_IP_MAX_ATTEMPTS`(20)/`WEB_LOGIN_IP_WINDOW_SEC`(600).
- [x] IP throttle: in-process token bucket(`_login_ip_throttled`/`_record_failure`/`_clear`, `_search_rate_limit_check` 패턴) + 메모리 가드(공격자 영향 IP 키 무한증가 → 4096 초과 시 만료 버킷 sweep, outside-voice MINOR 흡수).
- [x] 계정 잠금: `_login_record_failure`(실패 누적, 임계 도달 시 `DATE_ADD(NOW(), INTERVAL %s MINUTE)` 잠금+카운터 리셋)·`_login_reset_lockout`(성공/해제 시 초기화). 잠금 판정=`_fetch_account_rows` 의 DB NOW() 평가 `is_locked`(clock skew 무관).
- [x] login 흐름: IP throttle(DB 전, 429) → 미존재/비활성(일반 401+IP기록, 계정열거 방지) → is_locked(429) → 비번 검증 실패 시 누적+IP기록, 잠금 발생 시 audit `auth.lockout`(anonymous actor, fail-open)+429 → 성공 시 카운터/잠금/IP 초기화. conn try/finally.
- [x] admin: `POST /api/admin/accounts/{id}/unlock`(비번 변경 없이 잠금만 해제, 표적 DoS 회복; 권한=password-reset 동일 `console.access`+`console.manage`+`account.update`, 신규 RBAC 0)+audit `auth.unlock`. password-reset 도 잠금 해제(FailedLoginAttempts=0/LockedUntilAt=NULL). 계정 직렬화 `is_locked`/`locked_until`(failed_login_attempts 는 admin-context만 — NIT 흡수). admin.js 잠금 배지(amber)+해제 버튼+`triggerAccountUnlockFlow`. 로그인 잠금 메시지=`error` 필드 자동 표시(프론트 변경 0).
- [x] 검증: `tests/test_login_attempt_limit.py` 11/11(B1~B10 + F1, IP throttle 실 동작 + 나머지 inspect.getsource) + make test 전체 회귀 0(사전존재 `test_product_delete_block_conv` 2건 제외, 본 변경 무관) + py_compile + node --check + CSS brace 1373=1373.
- [x] outside-voice 적대 보안 리뷰(Critical 인증, [[feedback_outside_voice_for_rbac]]) **SHIP-WITH-FIXES**(BLOCKER 0). **흡수**: MINOR(IP 버킷 메모리 가드)·NIT(/api/auth/me 실패횟수 비노출). **accept+문서화**: MAJOR(동시요청 soft-threshold — is_locked 가 느린 PBKDF2 직전 스냅샷이라 버스트가 임계 초과 가능; LOGIN_MAX=연속 한도. 1차 DB잠금·2차 IP throttle+느린해시, 분산 botnet 은 사내 LAN 위협모델 외, 외부 노출 시 별 cycle FOR UPDATE/per-account pre-gate)·MINOR(429vs401 계정열거 오라클=잠금 본질·수용·내부LAN, schema-catchup 선행 의존=must_change idiom 동일, unlock audit-fail 500-after-commit=password-reset 동일 패턴, locked_until naive tz=cosmetic).
- [ ] 머지 → 배포(web) → 라이브 재검증(5회 실패→잠금→429·관리자 해제) + PB-0008(잠금 배지/해제 버튼) → 마감.

### TASK-20260619T022449 — 릴리즈 노트: LLM 사용 제한 안내 항목 추가 (content-only, Minor §12.3, 2026-06-19)
- 사용자 정책(2026-06-19): `/_template:entry` 완료 시 릴리즈 노트에도 개발사항 명시 + 기존 노트로 양식·문체 파악 후 정합 구성. TASK-20260619T014034(LLM provider 외부요인 제한) 의 사용자-대상 릴리즈 노트.
- [x] `release-notes-data.js` `releases[]` 맨 앞 2026-06-19 블록 추가(`generated` 동기) — `{type:new, area:work}` "AI 사용이 일시적으로 제한될 때 화면에서 바로 확인". 기존 문체 정합(사용자 결과 중심·존댓말 detail·내부동작 비노출="외부 요인" 추상화, AC-0579).
- [x] index.html/admin.html `release-notes-data.js?v=` 캐시버스터 bump(20260619-llm-restriction) + `verify_release_notes.mjs` 34/34 + node --check.
- [ ] 머지 → 배포(web) → PB-0008(양 진입점 노출) → 마감.

### TASK-20260619T023922-audit-tamper-evidence — 감사 기록 변조방지 (해시 체인 + 검증 + 로그 앵커) (REQ-20260619-0326, AC-0592~0595, Critical §12.3, 2026-06-19)
- 사용자 요청(보안 보강 6종 중 ③): 감사 기록 변조방지. 기존 `WebAuditEvents`(TASK-0073) append-only 의도였으나 변조(수정/삭제/삽입/재정렬) 탐지 수단 부재.
- [x] 스키마(멱등·비파괴): `WebAuditEvents.EventHash/PrevHash CHAR(64)` ALTER + `WebAuditChainCheckpoint`(purge 경계 재앵커) 신설(`_ensure_web_audit_chain_schema`, fast+slow 양 경로). 기존 행 NULL=미봉인→backfill.
- [x] 해시 체인: `EventHash = SHA256(PrevHash | 정규화행)`. 정규화=`_audit_canonical_string`(\x1f 구분, JSON 컬럼 `CAST(... AS CHAR)` 결정성, EventHash/PrevHash 제외). 봉인 `_seal_audit_chain`=GET_LOCK 직렬+미봉인 커밋행 Id ASC 일괄+`EventHash IS NULL` 가드(fork 방지).
- [x] 훅: record_audit_event INSERT 후 **fresh autocommit 연결**로 동기 봉인(best-effort) + 백그라운드 sealer(`AGENT_AUDIT_SEAL_SEC`=30, drain) + verify 시 봉인.
- [x] verify 엔드포인트 `GET /api/admin/audits/verify`(audit.read.any): drain 봉인 후 Id 순 keyset walk·재계산·링크/내용 검사 → first_break 보고. purge 경계는 최신 checkpoint 재앵커.
- [x] purge 정합: 삭제 전 drain 봉인 + 경계 행 EventHash 를 checkpoint INSERT(실패 시 purge 중단=체인 단절 방지).
- [x] 프론트: 감사 탭 "무결성 검증" 버튼(audit.read.any)+`triggerAuditChainVerify`+결과 배지(정상 green/위반 red), styles `.admin-audit-verify-result`, cache-buster `?v=20260619-audit-chain`.
- [x] 검증: `tests/test_audit_tamper_evidence.py` 11/11(B1/B2 해시 tamper-detection 실 동작 + 나머지 inspect.getsource) + make test 회귀 0(사전존재 product-delete 2건 제외) + py_compile + node --check + CSS brace.
- [x] outside-voice 적대 보안 리뷰(Critical 감사 무결성) **SHIP-WITH-FIXES**(BLOCKER 0). **흡수**: MAJOR-1(RR 스냅샷 fork→fresh-conn 봉인+`EventHash IS NULL` 가드)·MAJOR-4(verify/purge 거대 batch lock starvation→1000-batch drain bound)·MAJOR-2(in-DB 체인 단독 한계 정직화: 위협모델 docstring/SECURITY.md §13 명시 + 백그라운드 sealer **off-DB 로그 앵커** `[audit-chain-anchor]` head 해시). **수용**: MINOR(CAST(JSON) 서버버전 의존 upgrade 위험·ThroughEventId 검증 미사용·DB 통합테스트 부재[게이트 DB-less]·\x1f 구분자 embeddable=chosen-prefix only).
- [ ] 머지 → 배포(web) → 라이브 verify round-trip(정상 ok + 인위 변조→break) + PB-0008(검증 버튼/배지) → 마감.

### TASK-20260619T030500-llm-usage-quota — LLM 사용량 한도 (역할 기본 + 계정 특수) (REQ-20260619-0327, AC-0596~0599, Major §12.3, 2026-06-19)
- 사용자 요청(보안 보강 6종 중 ④): LLM 사용량 한도 처리 — 역할별 기본, 계정별 특수(override).
- [x] 인프라 재사용: 토큰 계량(`agent_runtime.llm_usage`)·대시보드(TASK-0136)는 기존 → 한도 설정 + 사전 게이트만 신설.
- [x] 스키마(멱등): `WebRoleTokenQuotas`(역할 기본)·`WebAccountTokenQuotas`(계정 특수), QuotaType=daily|monthly, TokenLimit(0=무제한 명시). RBAC override 패턴 미러. fast+slow 양 경로.
- [x] 유효 한도 `_account_effective_quota`(계정 override→역할 기본→None 무제한) + 사용량 `_account_period_usage_tokens`(PG date_trunc day/month·owner_account_id join·fail-open 0).
- [x] 사전 게이트 `_check_account_token_quota`(/api/ask 조기, slot 전): 무제한/미설정/인프라장애=통과(fail-open), 초과 시 429. 킬스위치 `AGENT_LLM_QUOTA_ENFORCE`. **안전 기본=미설정 무제한**(배포만으로 누구도 차단 안 함).
- [x] admin: `GET /api/admin/quotas`·`PUT .../role/{id}`·`PUT .../account/{id}`(console.manage)+audit `quota.role/account.update`. UI=LLM 사용량 탭 "사용 한도 설정"(역할 행 편집+계정 특수 추가/해제), cache-buster `?v=20260619-llm-quota`.
- [x] 검증: `tests/test_llm_usage_quota.py` 10/10(B3 parse·B4 fail-open 실 동작 + inspect.getsource) + make test 회귀 0(사전존재 product-delete 2건 제외) + py_compile + node --check + CSS brace.
- [x] outside-voice 적대 리뷰 **SHIP-WITH-FIXES**(BLOCKER/MAJOR 0). **흡수**: MINOR(parse_limit BIGINT clamp overflow 500 방지)·MINOR(0=무제한 footgun→캡션 "전면 차단=1" 명시). **수용**: 동시요청 race(parallel limit 6 bound)·aux-call 미집계(under-count=가용성 우선·evasion 아님)·admin prompt/generate 미게이트(admin-only)·daily/monthly tz(PG UTC, 대시보드 정합)·계정 free-text id(404 가드).
- [ ] 머지 → 배포(web) → 라이브(한도 설정→초과 429·해제) + PB-0008(한도 패널) → 마감.
### TASK-20260619T034522-oauth-google-foundation — Google 계정(OAuth) 로그인 토대 (REQ-20260619-0328, AC-0600~0601, Critical §12.3, 2026-06-19)
- 사용자 요청: "이후 google 계정을 통한 로그인이 가능할까요? 사내 웹서비스에 편입하기 위한 기반작업을 진행해두고 싶습니다. 검토를 우선하여 진행해주세요." → 검토 후 사용자 결정(AskUserQuestion 2026-06-19): **① 비파괴 토대 구축**(flag OFF, credential 주입 시 활성) ② **모든 Google 계정 허용**(도메인 무제한) ③ **자동 생성+pending 승인 대기** + email 일치 시 link ④ **기존 비번 로그인 공존**.

#### §2.1 Implementation Plan (Critical §12.3 — 인증 경로, 비파괴 토대)
- **위험도 = Critical** (SECURITY.md §3 인증 변경). 비파괴 보장: 신규 엔드포인트 flag OFF 시 404, DB 컬럼 NULL, 프론트 버튼 hidden, 기존 login/signup/세션/RBAC 무변경 → 런타임 인증 경로 무영향. 배포 보류(토대만).
- 영향 파일/심볼:
  - `unit/feature-0003-agent-web-ui/src/app.py`: config 블록(`OAUTH_GOOGLE_*`/`OAUTH_NO_PASSWORD_SENTINEL`), `_ensure_oauth_identity_schema`(fast+slow 등록), `_fetch_account_rows` SELECT(email/auth_provider/oauth_subject), `_serialize_account`(email/auth_provider 노출), OAuth helper 9종(`_oauth_google_configured`/`_oauth_b64url(_decode)`/`_oauth_pkce_pair`/`_oauth_state_encode(decode)`/`_oauth_google_exchange_code`/`_oauth_decode_id_token_claims`/`_oauth_validate_claims`/`_oauth_provision_username`/`_oauth_resolve_or_provision_account`), 엔드포인트 3종(`auth_oauth_config`/`auth_oauth_google_start`/`auth_oauth_google_callback`), import `RedirectResponse`.
  - 프론트: `static/index.html`(#oauthSection 버튼 hidden + Google SVG), `static/app.js`(`refreshOAuthLoginButtons`/`showOAuthErrorIfPresent`/showAuthOverlay 훅), `static/styles.css`(`.auth-oauth`/`.auth-divider`/`.btn-oauth`), index.html+admin.html cache-buster `?v=20260619-oauth-foundation`.
  - 인프라: `docker-compose.yml`(agent-common env_file `.env.oauth` optional), `.env.oauth.example` 신설, `.gitignore`(`.env.oauth`).
  - 문서: `docs/SECURITY.md §15`, `FUNCTION.md AC-0600~0601`, `docs/TEST.md §4`, `REVIEW.md`, `REPORT.md`.
  - 테스트: `tests/test_oauth_google_foundation.py`(29 케이스).
- 완료 판정(acceptance): AC-0600~0601(FUNCTION.md). 핵심 = flag OFF 시 엔드포인트 404 + 기존 인증 무회귀 + PKCE/state/claim 검증/계정매핑 단위 통과.
- 구현/검증 결과:
- [x] DB: `_ensure_oauth_identity_schema` 멱등 ALTER(Email/AuthProvider/OAuthSubject + 2 UNIQUE index), fast(`_ensure_seed_catchup`)+slow(`_ensure_web_tables`) 양 경로. 기존 행 NULL=로컬 계정 무회귀.
- [x] Config: `OAUTH_GOOGLE_ENABLED`(기본 0) 외 client/secret/redirect/allowed-domains/state-secret/ttl. `_oauth_google_configured()` AND 게이트.
- [x] Backend: Authorization Code + PKCE(S256) + 서명 state(CSRF/TTL) + claim 검증(iss/aud/exp/nonce/email_verified/도메인) + 계정 매핑(subject/email-link/pending-create) + 기존 `_issue_auth_session` 재사용. 외부 의존 0(stdlib urllib). flag OFF 시 /start·/callback 404.
- [x] Frontend: 로그인 화면 Google 버튼(기본 hidden → `/api/auth/oauth/config` enabled 시 노출) + `?oauth_error=` 안내 매핑 + CSS + 캐시버스터 bump(index+admin).
- [x] 인프라: `.env.oauth`(gitignored, optional env_file) + `.env.oauth.example`(발급/활성 절차 문서화).
- [x] 검증: `test_oauth_google_foundation.py` **29/29 통과**(agent 이미지 컨테이너, PYTHONPATH feature-0002 src). 전체 회귀 = 사전존재 `test_product_delete_block_conv` 2건(base 동일 실패, product-delete RBAC — 본 변경과 무관)만 실패, **신규 회귀 0**. `py_compile` OK.
- [x] 보안 한계 정직 기록(SECURITY.md §15.3/14.4): ID token **JWKS RS256 서명 검증=활성화/배포 전 TODO**(현재 백채널 TLS+claim 검증) · 모든-도메인 허용의 pending abuse(외부 노출 시 도메인 한정/사전등록 전환) · env web-only scoping · state-secret 멀티워커.
- [ ] (활성화 cycle, 사용자 후속 결정) Google Cloud Console OAuth Client 등록 → `.env.oauth` 주입 + `WEB_OAUTH_GOOGLE_ENABLED=1` → JWKS 서명 검증 추가 → 배포(web) → 라이브 e2e + PB-0008(버튼 노출/로그인) → outside-voice 적대 보안 리뷰.

### TASK-20260619T040000-two-factor-auth — 2단계 인증 (TOTP, self-service + 관리자 해제) (REQ-20260619-0329, AC-0604~0607, Critical §12.3, 2026-06-19)
- 사용자 요청(보안 보강 6종 중 ⑥, 마지막): 2단계 인증 과정. 사용자 결정(AskUserQuestion): **사용자 opt-in self-service** + 관리자 강제 해제(역할 강제는 후속 cycle).
- [x] TOTP: stdlib RFC 6238(HMAC-SHA1·6자리·30s·±1 step drift, pyotp 없이). secret 은 `cred_crypto`(DEK/KEK AESGCM, AAD=`totp:{account_id}`) 암호화 저장. `WebAccountTotp` 신규(멱등, fast+slow). 기본 미설정=2FA off(무회귀).
- [x] 등록 self-service: `POST /api/auth/totp/setup`(secret+otpauth QR, Enabled=0)·`confirm`(첫 코드 검증→Enabled=1+백업코드 10개 1회 노출)·`disable`(비밀번호 재확인).
- [x] 로그인 2단계: auth_login 비번 통과+TOTP 활성 시 `{totp_required, totp_token}`(세션 미발급) → `POST /api/auth/login/totp`(pending token=DEK-HMAC 5분 + TOTP/백업코드) → 세션. 백업코드 row-lock 1회용.
- [x] admin: `POST /api/admin/accounts/{id}/totp/disable`(분실 복구, console.manage+account.update 재사용·신규 RBAC 0). serialize `totp_enabled`(`_fetch_account_rows` 서브쿼리). audit `auth.totp.enable/disable/admin_disable`+`auth.login.totp`.
- [x] 프론트: 로그인 TOTP 프롬프트(app.js `showTotpLoginPrompt`)·프로필 "보안 및 계정" 2FA 켜기/끄기(`renderProfileTotp`·QR·백업코드)·admin "2FA" 배지(blue)+해제. cache-buster `?v=20260619-2fa`.
- [x] 검증: `tests/test_two_factor_auth.py` 10/10(B1 TOTP roundtrip+drift·B3 백업코드 실 동작 + inspect.getsource) + make test 회귀 0(사전존재 product-delete 2건 제외) + py_compile + node --check + CSS brace 1402.
- [x] outside-voice 적대 보안 리뷰(Critical 인증, 2FA bypass/brute-force 집중) **SHIP-WITH-FIXES**(BLOCKER 0, 클린 bypass 없음·crypto core RFC6238 정확). **흡수 MAJOR**: TOTP brute-force 증폭(비번 통과 시 IP/잠금 리셋이 TOTP 분기 전 → 비번 보유 공격자 step1 반복으로 throttle 무한리셋) → **2FA 분기는 리셋 미룸(2단계 완료 시에만)** + **TOTP 실패 시 계정 잠금(② 인프라)+IP 기록 + step-2 잠금 차단**. **흡수 MINOR**: 백업코드 소비 `SELECT FOR UPDATE` 원자화. **수용**: pending token TTL 내 재사용(코드 필요+이중 throttle bound)·30s 내 코드 재사용(표준)·KEK 부재 시 2FA 계정 fail-closed(admin 복구).
- [ ] 머지 → 배포(web) → 라이브(설정→로그인 2단계→백업코드→admin 해제) + PB-0008(2FA UI) → 마감. **6종 전체 완료.**

### TASK-20260619T084227-release-notes-security-6 — 보안 보강 6종 릴리즈 노트 기록 (REQ-20260619-0330, AC-0608, Minor §12.3, frontend-only, 2026-06-19)
- 사용자 요청: 보안 보강 6종(①~⑥) 중 릴리즈 노트 적용 사항 기록 후 배포.
- [x] `release-notes-data.js` 2026-06-19 블록에 보안 6종 사용자 향 항목 6개 추가(기존 그룹대화·AI제한 2항목 유지, summary 보강). 양식·문체=기존 노트 정합([[feedback_template_entry_release_notes]]).
- [x] 내부 동작 비노출(AC-0579): 암호화/해시체인/TOTP secret/인젝션/RBAC/PG/quota 등 금지 용어 0(자가 스캔 clean). 사용자 보이는 결과 중심(2FA 켜기·공유 만료·로그인 잠금·사용 한도·무결성 검증 버튼·보안 처리 강화 추상화).
- [x] index/admin cache-buster `release-notes-data.js?v=20260619-security-6`. node --check valid.
- [ ] 머지 → 배포(web) → PB-0008(양 화면 노트 렌더) → 마감.

### TASK-20260623T014626-quota-ui-relocate — LLM 사용 한도 UI 를 역할·계정 상세로 이전 (REQ-20260623-0331, AC-0609, Minor §12.3, 2026-06-23)
- 사용자 보고: ④ LLM 한도가 `관리 콘솔 > 감사 > LLM 사용량`(감사·조회 목적 화면)에 추가돼 한도 설정 위치로 부적절. `계정`·`역할` 상세에서 각 항목 속성으로 구성하도록 수정 요청.
- [x] 백엔드(직렬화만, 엔드포인트/RBAC 무변경): `_list_roles` 에 역할 기본 한도(`quota_daily`/`quota_monthly`) 노출, `_fetch_account_rows`+`_serialize_account`(admin-context) 에 계정 override 노출. 기존 PUT `/api/admin/quotas/role|account/{id}` 재사용.
- [x] 프론트: usage 탭 한도 패널(loadQuotas·usageQuotaDetails·계정ID free-text 폼) 제거. 공용 `buildQuotaEditor({scope,id,daily,monthly,inheritNote,onSaved})` 신설 → 역할 상세("LLM 사용 한도(역할 기본)") + 계정 상세("LLM 사용 한도(계정 개별 지정)", 역할 상속 안내 표시) 에 섹션 추가. 권한 게이트 console.manage(+account.update).
- [x] 검증: `tests/test_llm_usage_quota.py` 11/11(B10 직렬화 노출 + F1 이전·구 패널 제거 가드 갱신) + make test 회귀 0(사전존재 product-delete·db_query_ux[feature-0009 병렬] 2건 무관) + py_compile + node --check + CSS brace 1438. cache-buster `?v=20260619-quota-relocate`.
- [x] 머지 → 배포(web) → PB-0008(역할·계정 상세 한도 섹션 + usage 탭 패널 제거) → 마감. (배포 fe81973)

### TASK-20260623T021500-quota-editor-escapehtml-fix — buildQuotaEditor escapeHtml ReferenceError 수정 (잠복 버그, 2026-06-23)
- **PB-0008 적발**: `buildQuotaEditor` 가 `escapeHtml(...)` 보간 → admin 페이지에서 `ReferenceError: escapeHtml is not defined` → 역할·계정 상세의 "LLM 사용 한도" 섹션이 렌더되지 않음. 원인: `escapeHtml` 은 `app.js:495` 에만 정의되는데 `admin.html`(<script> 633-637)은 `app.js` 를 로드하지 않음(admin.js·textarea-autogrow.js·release-notes만 로드).
- **잠복 버그 확인(적대 리뷰)**: 이 결함은 ④ LLM 한도 도입(05d58d1) 이래 존재 — 제거된 구 `loadQuotas` 도 동일하게 admin 페이지에서 escapeHtml 5곳 보간 → usage 탭 한도 패널도 production 에서 한 번도 정상 렌더된 적 없음(latent, relocate 가 만든 회귀 아님). relocate 가 escapeHtml 의존을 그대로 옮겨와 노출됨.
- [x] 수정: 비신뢰 값(한도 숫자·inheritNote)을 innerHTML 보간 대신 DOM 프로퍼티로 주입 — `input.value = fmtVal(...)`, `note.textContent = opts.inheritNote`. placeholder/힌트는 정적 문자열(scope 파생)이라 innerHTML 유지. escapeHtml 의존 0(실사용·주석 외 제거). XSS 안전성은 오히려 강화(동적 값이 innerHTML 경로를 전혀 타지 않음).
- [x] 검증: `test_llm_usage_quota.py` F1 에 회귀 가드 추가(buildQuotaEditor 본문 슬라이스에 `escapeHtml(` 부재 + DOM 주입 패턴 존재) → 11/11. node --check OK. 사전존재 실패 2건(product-delete·db_query_ux) 무관 재확인.
- [x] 적대 리뷰(outside-voice): **SHIP**. XSS-safe 확인, escapeHtml 미가용 crux 확인(app.js 미로드), admin.js 잔여 escapeHtml call-site 0(스코프 완전), 콜러(renderRoleDetail/renderAccountDetail) throw 제거로 상세 pane 전체 깨짐 위험 해소.
- [x] 머지 → 배포(web) → PB-0008(역할·계정 상세 "LLM 사용 한도" 섹션 실렌더 + 저장 동작) → 마감. (main 9e7ec24, PB-0008 d6a3ccd)

### TASK-20260623T030418-quota-rbac-permission — 계정별·역할별 LLM 사용 한도 조회/조절 전용 권한 (REQ-20260623-0332, AC-0610·0611, Major §12.3 — 보안 경계, 2026-06-23)
- 사용자 요청: 계정별·역할별 LLM 사용 한도의 "조회 및 조절" 권한을 구성. 조절은 조회에 종속(조회 없으면 조절 불가). 조회 권한 없으면 UI 표시도 미노출.
- 결정: quota 를 `console.manage` 에서 **분리**해 전용 권한 2종 신설 — `quota.read`(조회, 그룹 게이트=console.access 하위)·`quota.manage`(조절, quota.read 선행). admin seed(=set(PERMISSION_CODES)) 자동 보유 → 무lockout. console.manage 만 가진 커스텀 역할은 명시 부여 전까지 한도 접근 불가(least-privilege, datasource.read/product.read 도입 선례 동형).
- [x] 백엔드: `PERMISSION_DEFINITIONS` 에 quota.read/quota.manage(group=quota) 추가. GET `/api/admin/quotas` console.manage→**quota.read**, PUT `/api/admin/quotas/role|account/{id}` console.manage→**quota.manage**. 직렬화 strip 헬퍼 `_strip_quota_fields_if_unpermitted`(actor quota.read 미보유 시 quota_daily/monthly 제거) — `admin_me`·`admin_accounts`·`admin_roles` 적용(defense-in-depth, 노출 차단).
- [x] 프론트: `PERMISSION_DEPENDENCIES` quota.read→console.access·quota.manage→quota.read. 그룹 메타(`PERMISSION_GROUP_ORDER`/`PERMISSION_GROUP_LABELS` "LLM 사용 한도"/`ADMIN_PERMISSION_SECTIONS` manage). 역할/계정 상세 한도 섹션 게이트 console.manage(+account.update)→**can("quota.read")**, 편집=**readOnly:!can("quota.manage")**. `buildQuotaEditor` `readOnly` 옵션 신설(입력 disable + 저장 버튼 미렌더 + "조회 전용" 안내). cache-buster `?v=20260623-quota-rbac-permission`.
- [x] 검증: `test_llm_usage_quota.py` B8 게이트 갱신 + B11(권한 등재·admin seed·least-privilege)·B12(strip 헬퍼 실동작 list/dict)·F2(UI 게이트 read=표시/manage=readOnly)·F3(권한 정합) 신설 → 16/16. `test_permission_dependency_map.py` 가 신규 deps 자동 검증 통과. make test 회귀 0(사전존재 product-delete·db_query_ux 3건 무관). node --check + py_compile OK.
- [x] 적대 리뷰(outside-voice, 보안 경계 필수): **SHIP-WITH-FIXES** → 2 MAJOR 흡수. **MAJOR-1**(PATCH `/api/admin/accounts/{id}` 응답이 strip 미적용 → account.update 만으로 한도 열람 우회) → `admin_update_account` 응답에 `_strip_quota_fields_if_unpermitted` 추가. **MAJOR-2**("조절은 조회 종속"이 UI-only — PUT 이 quota.manage 만 검사해 blind-write 가능) → PUT role/account 게이트에 quota.read **동시 요구**(서버 집행). MINOR(console.manage 분리=접근 확대)=의도된 설계, 문서화. 재검증 31/31.
- [x] verify-completion → 머지 → 배포(web) → PB-0008(quota.read만=readOnly / quota.manage=편집 / 무권한=미표시 3-tier) → 마감. (main cede0a4 머지·배포)

### TASK-20260623T030418-quota-rbac-permission follow-up — admin catchup 누락 lockout 수정 (PB-0008 적발, 2026-06-23)
- **PB-0008 적발**: 배포 후 실 Windows 브라우저에서 `bootstrap_admin`(role=admin, console.manage 보유) 의 `adminState.me.permissions["quota.read"]`=**false** → 한도 게이트를 console.manage→quota.read/manage 로 전환한 탓에 admin 포함 전원이 한도 섹션 접근 불가. DB 확인: WebRolePermissions(RoleId=3) quota.read=0/quota.manage=0.
- **근본**: 신규 권한은 role 생성 시 seed(=set(PERMISSION_CODES))로만 부여 → **기존 배포 admin row 에는 retroactive 미적용**. `_ensure_seed_roles` 의 admin catchup 리스트(TASK-0288 datasource.read 등 선례)에 quota.read/manage 미등록이 원인.
- [x] 수정: `_ensure_seed_roles` admin catchup 에 `quota.read`/`quota.manage` 추가(INSERT IGNORE 멱등, 재시작 시 기존 admin 역할 backfill). 회귀 가드 B13(catchup 소스에 quota.read/manage 단언).
- [x] 검증: test 16/16(B13 신설) + make test 회귀 0 + py_compile. 배포 후 재PB-0008(admin=quota.read/manage 보유→편집 가능 + 3-tier 게이트).
- [ ] verify → 머지 → 배포 → 재PB-0008 → 마감.

### TASK-20260624T105228-item08-fix-with-ai — "AI 로 고치기" 표적 재수정 버튼 (ROADMAP dba-ai-nl2sql ITEM-08, 2026-06-24)
- 출처: ROADMAP dba-ai-nl2sql ITEM-08. 사용자가 실패한 SQL 결과 카드에서 "AI 로 고치기" 를 누르면, 원본 NL 질문을 통째로 재질문하지 않고 **서버가 구성한 정정 지시문**(실패 SQL·DB 오류를 데이터 인용 블록으로만 삽입)을 **동일 conversation_id 로 기존 `/api/ask` 파이프라인에 1회 dispatch** → ITEM-07 self-reflection(agent_core 무변경)이 표적 정정을 수행. 범위: feature-0003 web 만(agent_core·ask-worker·gateway·credential·ROADMAP 무변경).
- Acceptance: (1) 실패한 execute_sql step(`tool==='execute_sql'` && `error` 존재)을 가진 assistant 답변에만 버튼 노출. (2) 클릭 → POST `/api/conversations/{cid}/fix-with-ai {executed_sql, error_message}` → 응답(= `/api/ask` 와 동일 result dict)으로 대화 reload(수정 결과가 같은 cid 에 새 assistant message 로 추가). (3) 가드 = `post_sample_feedback` 동형(접근 404 / rate-limit 429 / 발화 권한 403) + audit. (4) 프롬프트 인젝션 방어(서버 고정 지시문 + 데이터 블록 + 백틱 무력화 + 길이 cap). (5) 1회 dispatch(추가 루프 없음 — 재실패는 self-reflection 내부 cap 이 처리).
- [x] 백엔드: `POST /api/conversations/{cid}/fix-with-ai`(app.py `post_fix_with_ai`) + 헬퍼 `_sanitize_fix_with_ai_fragment`·`_build_fix_with_ai_message`·`_make_internal_ask_request`. 가드 순서 = `_require_account` → `_account_can_access_conversation`(404) → `_search_rate_limit_check(max_per_min=5)`(429) → `_account_has_permission("conversation.ask")`(403) → `record_audit_event(conversation.fix_with_ai)`. 입력 검증: 빈 값/과대(cap×4) → 400.
- [x] 재dispatch: 서버 구성 정정 메시지 + 동일 cid 를 담은 내부 Starlette Request(`_make_internal_ask_request` — 원본 scope 복제로 인증 쿠키/UA/IP 보존, body 만 교체)로 `await ask(...)` 1회 호출. product/role/allowed_schemas 해석·동시성 슬롯·worker 분기·self-reflection 모두 ask 재사용(중복 구현 0). worker mode attach 루프의 `is_disconnected` 가 조기 종료되지 않도록 `_receive` 가 body 1회 공급 후 원본 `request._receive` 로 위임.
- [x] 프론트(app.js): `_failedSqlStepFromMessage`(실패 execute_sql step 탐지, durable=meta.steps 재로드 안전)·`_buildFixWithAiControl`(버튼+상태) 신설. `renderMessages` 액션 영역에 `canFixHere` 게이트(assistant + 활성 대화 + `can("conversation.ask")` + 실패 step 존재)로 sample feedback 컨트롤 인근 렌더. 더블클릭 가드(`dataset.busy`)·요청 중 disable+로딩 라벨·성공 시 `refreshWorkspace` reload·실패 toast. XSS: SQL/error 를 DOM 에 textContent 로만 전달(innerHTML 무사용), 서버로는 JSON body.
- [x] CSS: `.message-fix-with-ai`/`.message-fix-status`/`.message-fix-btn:disabled`(message-feedback 동형). index.html cache-buster `?v=20260624-item08-fix-with-ai`(app.js+styles.css).
- [x] 검증: `tests/test_fix_with_ai.py` 10/10(G1 404·G2 403·G3 429·V1/V2 400·P1 봉인블록·P2 백틱무력화+cap·**M1 회귀: 개행/가짜마커 탈출 차단**·D1 정정문 1회 dispatch+원본NL 미전송+audit·내부request 빌더) — PYTHONPATH=feature-0002:feature-0003 로 실측 통과 + py_compile(app.py) + node --check(app.js). (전체 suite 는 `make test` agent 이미지 — modules.memory 병합. 사전존재 실패 product-delete·share-redaction = DB/컨테이너 경로 의존, 본 변경 무관.)
- [x] **적대 backend+security 리뷰(REV-20260624T105228, SHIP-WITH-FIXES) — M1 흡수**: 인젝션 방어가 백틱(미사용 코드펜스)만 막고 실제 구분자(개행/라벨)는 탈출 가능 → **nonce-봉인 데이터 블록**으로 교체(서버 매요청 `secrets.token_hex(8)` nonce 로 `«SQL-{nonce}»`…`«/SQL-{nonce}»` 봉인, sanitizer 가 입력에서 `«·»`+nonce 제거 → client 가 닫는 마커 위조 불가, 개행/가짜마감문/가짜라벨이 봉인 블록 안에 갇힘). MINOR(rate-bucket 공유·검증순서·이중 audit)는 sample-feedback 동형 기존 패턴 + cost 관점 더 보수적이라 house-consistent 수용. `_make_internal_ask_request`(private `_receive`)는 리뷰 실측상 body 1회 공급·worker `is_disconnected`·cross-account·슬롯 모두 안전 확인.
- [ ] (메인) verify-completion → 머지 → 배포(web) → PB-0008(실패 SQL 답변에 버튼 노출 + 클릭 시 정정 결과 추가) → 마감.

### TASK-0308 — 제품 탭에 데이터소스 인사이트 탐색 상태 표시 (Minor §12.3, 2026-06-24)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-24 (목업 디자인 확인) -->
- 사용자 보고: 제품 > '데이터 소스 & 접근 가능 데이터베이스' 만 보고 insight 탐색 토글(InsightEnabled) 상태를 못 봐 mssql-qa-idc 가 비활성인 걸 놓침(별도 데이터소스 관리 탭에만 표시됐음). 재발 방지로 제품 탭에 상태를 단순 UI(텍스트 아님)로.
- [x] **frontend only**(`admin.js`+`styles.css`, 백엔드 0 — `insight_enabled` 는 이미 datasources API 가 내려줌): `_renderDsAccordion` 행 헤더에 `.ds-acc-insight` 아이콘. 켜짐=은은한 눈, **꺼짐=amber 칩+빗금 눈(두드러지게 — 놓치던 OFF 강조)**. 색 단독 의존 회피(아이콘 형태 차이 + title/aria-label).
- [x] **사용자 조정 반영**: 조건부 '기본' 텍스트 배지가 인사이트 아이콘 위치를 행마다 흔드는 문제 → '기본' 텍스트 제거, primary 는 **엔진 배지를 primary 색(`.ds-acc-engine.is-primary`)** 으로 표기(엔진 배지는 항상 존재 → 아이콘 위치 일관) + title "기본(primary) 데이터소스".
- [x] 검증: admin.js `node --check` + Artifact 목업(실 CSS·아이콘 렌더, BEFORE/AFTER) 사용자 디자인 승인. UI 실렌더 정본=PB-0008(Windows-browser).
- [x] verify → 머지(PR #396) → web 재배포(main `6606b8e`, static baked + cache-buster `v=20260624-product-insight-badge`) → **PB-0008 Windows-browser 시각 검증 PASS**(사용자 직접 확인, 2026-06-24 — 제품 탭 '데이터 소스 & 접근 가능 데이터베이스' 행에 인사이트 탐색 상태 아이콘 + primary 엔진색 정상 표시) → **마감**. (TEST.md §4 기록.)

### TASK-0309 — 제품 insight 분석률 95% 도달 시 제품 프롬프트 무인 자동완성 (1회성, Major §12.3 — 자율 LLM dispatch + 자율 DB write, 2026-06-25)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-25 (/_template:entry — worktree + background sweep 결정) -->
- 사용자 요청(/_template:entry): "`관리 콘솔 > 제품`의 각 제품에서 '제품 프롬프트'가 아직 입력되지 않은 항목을 대상으로, 분석률이 95%가 넘어가는 순간 자체적으로 제품 프롬프트 자동완성·저장을 진행. 단, 임의적 insight 분석 초기화로 95% 초과 수치가 다시 내려갔다 재상승해도 별도 분석을 진행하지 않도록(1회성으로 분석)."
- 해석: "제품 프롬프트" = `WebSystemPrompts(Scope='product')`. "분석률" = `_compute_product_insight_coverage` 의 `pct`(insight-worker 분석 schema/table 객체 / 라이브 카탈로그 객체). "자동완성" = 기존 수동 '자동작성' 버튼이 쓰던 LLM 생성 파이프라인(`_collect_product_prompt_context`)을 인증 없이 무인 호출. "1회성" = 제품당 1회 — insight reset 후 재상승 무시.
- 등급: **Major §12.3** — 자율 외부 LLM(Bedrock) 호출 + 자율 DB write(시스템 프롬프트). 인증·개인정보·파괴적 데이터 아님(Critical 아님). 수동 '자동작성' 버튼은 무변경 보존 → 관리자 재생성 경로 유지.
- 결정(AskUserQuestion): ① 전용 worktree(`ai/claude/auto-product-prompt`, base 262a065) ② 트리거 = **백그라운드 주기 sweep**(관리자 미접속에도 무인 동작 — '자체적으로').
- [x] **1회성 마커**(`app.py` `_ensure_web_tables`): `WebProducts.AutoPromptGeneratedAt DATETIME NULL` 멱등 ALTER. 자동완성 1회 성공 시 `UTC_TIMESTAMP()` 기록. insight reset(`admin_product_insight_reset`)은 PG insight 만 삭제·본 MySQL 컬럼 보존 → reset→재상승해도 마커 보유 시 재실행 안 함(1회성 핵심 게이트 = 후보 쿼리 `WHERE AutoPromptGeneratedAt IS NULL`).
- [x] **리팩터**: `_collect_product_prompt_context`(인증 게이트, 시그니처·반환계약 불변)에서 request-less 조립 코어 `_assemble_product_prompt_llm_request(product_id)` 분리. 인증 경로·무인 경로가 동일 ①제품/스키마 조회 ②PG 인사이트 ③knowledge_block ④create_kwargs 공유(중복 제거). 비스트리밍/스트리밍 엔드포인트 await 무변경.
- [x] **자율 코어**(`_autonomous_generate_product_prompt`): 조립→동기 LLM 호출(sweep=daemon thread 라 이벤트 루프 블로킹 없음)→저장 직전 마커 행 `SELECT ... FOR UPDATE` 잠금 + 재검사(마커 미설정+프롬프트 미입력, TOCTOU/경합 보호)→`_upsert_system_prompt`(updated_by=NULL system)+마커 UPDATE+`record_audit_event`(actor system, action `admin.product.prompt.autogenerate`). 실패/LLM 부재 시 마커 미설정→재시도. truncation 은 log 후 그대로 저장.
- [x] **sweep**(`_auto_prompt_sweep_once`): 후보=마커 미설정 제품. 프롬프트 미입력 검사(싼 MySQL)를 분석률(라이브 카탈로그, 비쌈)보다 먼저 → 이미 프롬프트 있는 제품 coverage 계산 회피. coverage 캐시(coverage API 와 공용) 재사용. `pct >= AGENT_AUTO_PROMPT_COVERAGE_THRESHOLD`(기본 95.0) 시 자율 코어 호출.
- [x] **startup 훅**(`_start_auto_prompt_sweep_loop`, daemon thread): 간격 `AGENT_AUTO_PROMPT_SWEEP_SEC`(기본 180, 0=비활성). 부팅 jitter min(45,interval). 기존 `_start_db_rule_reconcile_loop` 패턴 답습.
- [x] **적대 리뷰(REV-20260625T161500-auto-product-prompt) BLOCKER 1 + MAJOR 2 흡수**: **B1** `_connect_memory` autocommit=True 라 "단일 tx" 거짓 → 저장 동안 `conn.autocommit=False` 명시 tx + FOR UPDATE + finally 복원(부분실패 rollback → 1회성 불변식 보호). **M1** 실패 경로 마커 미설정 매-cycle LLM 재호출 비용 누수 → 실패 backoff(`AGENT_AUTO_PROMPT_FAIL_BACKOFF_SEC` 기본 3600). **M2** cycle 생성 버스트 → 상한 `AGENT_AUTO_PROMPT_MAX_PER_CYCLE`(기본 3, 0=무제한). MINOR(m1 `_record_llm_usage` 우회=수동경로 동일 기존갭/m2 lost-update 잔여창/m3 float 경계)는 수용. 반증실패=안전: 1회성 reset 생존·SQLi·인증분리 누수·연결누수·system audit.
- [x] **테스트**(`tests/test_auto_product_prompt.py` 12건 PASS): T1 분석률<임계 무생성 / T2 >=임계+미입력 1회 생성·재sweep scanned 0 / **T3 reset 후 재상승 무재생성(1회성 핵심)** / T4 프롬프트 존재 skip / T5 pct None skip / T6 pct==95.0 경계 / T7 다제품 적격만 / T8 인증 게이트 위임 / **T9 명시 tx(autocommit False→복원)+commit** / **T10 마커 UPDATE 실패 rollback→미저장·마커 NULL(B1)** / **T11 LLM 실패 backoff(M1)** / **T12 cycle 상한(M2)**. 기존 `test_insight_coverage.py` 5건 무회귀. ruff PASS.
- [ ] verify-completion → commit/push → PR·머지 → web 재배포(deploy_scope: included) → 라이브 확인(95% 제품 자동완성 1회 + reset 후 무재생성) → 마감. (운영 옵션: `AGENT_AUTO_PROMPT_SWEEP_SEC`/`AGENT_AUTO_PROMPT_COVERAGE_THRESHOLD`/`AGENT_AUTO_PROMPT_MAX_PER_CYCLE`/`AGENT_AUTO_PROMPT_FAIL_BACKOFF_SEC`.)

### TASK-20260624-item11-metadata-glossary-enum — 메타데이터 거버넌스 MVP-1: 용어/ENUM CRUD (ROADMAP dba-ai-nl2sql ITEM-11, Major §12.3 — 보안 경계)
<!-- PLAN-APPROVED (사용자) — 범위: 용어/ENUM CRUD 만. Phase 2(테이블/컬럼 설명·describe_table 부트스트랩·샘플 admin 편집)는 연기. -->
- **PLAN-APPROVED**. 임무: ROADMAP dba-ai-nl2sql ITEM-11(메타데이터 거버넌스)의 **MVP-1(용어/ENUM CRUD)** 을 feature-0003 worktree 에 구현. 기존 PG 테이블 `kb_glossary`·`enum_dictionary` 재사용 → **마이그레이션 없음**. 코어(feature-0002 `modules.kb_glossary`)는 기존 upsert/read 재사용 + admin-list/update/delete 신규(secondary 변경, MODIFY 에 cross-ref). web 은 RBAC/audit/scope/입력검증/cross-DB conn 분리 경계만.
- 등급: **Major §12.3 — 보안 경계(신규 RBAC `kb.ingest.manual`)**. 신규 RBAC + KB 적재(검색/답변 정확도 직접 영향, poisoning 면) = 보안 표면 → 메인 세션이 적대적 security 리뷰 후 마감(본 worktree 는 구현+단위검증까지, commit/push/PR/merge/deploy 금지).
- Acceptance: (1) admin 콘솔 "메타데이터" 탭(kb.ingest.manual 없으면 숨김) + 용어/ENUM 2 서브뷰. (2) 각 서브뷰 = scope 드롭다운(활성 datasource 목록 + 공용 common) + 목록 + 생성/수정 폼 + 삭제(confirm). (3) 백엔드 8 엔드포인트(glossary·enums 각 GET/POST/PUT/DELETE) 전부 RBAC `kb.ingest.manual` 게이트(미보유 403, 코어 미호출) + scope_key 검증(빈값/미허용 400) + 입력검증(필수누락/길이cap 400) + audit + commit. (4) 수정/삭제 by id + scope 가드(타-scope 행 비변경, 비존재 404, 삭제 멱등). (5) scope_key = datasource key(소문자) 또는 'common' — **요청 body/쿼리 명시**(CURRENT_FACT_SCOPE_KEY 미사용, BLOCKER). (6) XSS: 모든 사용자 데이터 DOM 삽입은 textContent/escape(innerHTML 금지).
- [x] 코어(`unit/feature-0002-agent-core/src/modules/kb_glossary.py`, secondary): `list_glossary_admin`·`list_enum_admin`(id 포함, 단일 scope, LIMIT 1000), `update_glossary_term`·`update_enum_entry`(by id+scope 가드, rowcount 반환), `delete_glossary_term`·`delete_enum_entry`(by id+scope 가드, 멱등). create 는 기존 `upsert_glossary_term`/`upsert_enum_entry` 재사용. 전부 `%s` 파라미터. read 캐스케이드(common+'')와 달리 admin CRUD 는 **단일 scope** 만(편집/삭제 정확도). MODIFY CHG-…item11 에 cross-ref.
- [x] 백엔드(`app.py`): 신규 권한 `kb.ingest.manual`(group kb, label "메타데이터 수동 등록/편집", PERMISSION_DEFINITIONS) + admin seed catchup(retroactive). 8 엔드포인트(`/api/admin/metadata/glossary`·`/enums` 각 GET 목록·POST 생성·PUT/{id} 수정·DELETE/{id} 삭제). 공용 헬퍼: `_metadata_resolve_account`(RBAC), `_metadata_valid_scope_keys`(datasources.all_datasources 키 ∪ common — best-effort, 실패 시 common 만 보수), `_metadata_check_scope`(빈값/미허용/길이 400), `_metadata_str_field`(trim+cap), `_metadata_audit`(memory conn, resource_type kb_metadata). PG write autocommit=False(원자성)+rollback, RO list 는 `_pg_connect_ro`. audit action: glossary.term.create/update/delete · enum.entry.create/update/delete. ENUM update UNIQUE 충돌 → 409. 삭제 멱등(affected=0 → 200, audit 미기록).
- [x] 프론트(`admin.html`·`admin.js`·`styles.css`·`index.html`): "메타데이터" 탭 버튼(display:none 게이트)+pane(scope select·2 서브탭·생성/수정 폼·목록). `admin.js` ADMIN_TAB_PERMISSIONS["metadata"]=["kb.ingest.manual"] + 탭 진입 `initMetadataTab` + `adminState.metadata`{subTab,scopeKey,items,editing}. scope 드롭다운 = `adminState.datasources`(기존 fetch 재사용) + 공용(common). 필드 정의(`_METADATA_FIELDS`) 기반 폼 렌더(서브탭별), 생성/수정 공용 폼, 삭제 confirm. **XSS: 전 사용자 데이터 textContent/DOM API(`createElement`/`replaceChildren`/`_metaEsc`) — innerHTML 무사용**. cache-buster `?v=20260624-item11-metadata`(admin.html styles+admin.js, index.html styles).
- [x] 검증: `tests/test_metadata_glossary_enum.py` 13/13(R1/R2 권한 카탈로그·seed·least-privilege · G403/E403 8 엔드포인트 권한 게이트(코어 미호출) · GC/GU/GD glossary create/update(404)/delete(멱등·audit) · EC/EU enum create(schema 선택)/update(404) · SV scope 미허용·빈값 400 · IV 필수누락·cap 400 · LST list 직렬화 id 포함). 회귀: sample-feedback 15/15·permission-dependency-map 16/16 무영향. py_compile(app.py·kb_glossary.py) + node --check(admin.js) OK.
- **Phase 2 연기(본 cycle 미구현 — ROADMAP ITEM-11 잔여)**: (a) 테이블/컬럼 설명(table/column description) CRUD, (b) `describe_table` 부트스트랩(스키마 introspection → 메타데이터 초기 시드), (c) 샘플 쿼리 admin 편집(샘플 검수 탭과 별개의 직접 편집). 본 MVP-1 은 용어/ENUM 만. ROADMAP 갱신은 메인이 수행(본 worktree 무변경).
- [x] **적대 backend+security 리뷰(REV-20260624T130000, SHIP)**: BLOCKER/MAJOR 0 — RBAC(8/8 게이트·코어 미호출·least-priv)·scope 누수/IDOR(`WHERE id+scope_key` 격리·allowlist fail-safe·scope 미재배정)·SQLi(`%s` 전수)·XSS(textContent)·원자성 모두 REFUTE 실패=안전. **MINOR-2 흡수**: scope 드롭다운 init race → 탭 재진입 시 재채움(선택 보존). **MINOR-1 수용**: audit cross-DB best-effort(동기 롤백 불가, 기존 admin mutation 동일 한계, warning 유지). 흡수 후 test 13/13.
- [ ] (메인) verify-completion → 머지 → 배포(web) → PB-0008(탭 노출/CRUD/scope 격리/권한 게이트) → 마감.

### CI green 복구 (ci-pytest-green-fix, 별도 worktree, Minor §12.3 — CI/test maintenance)
- [x] `.github/workflows/ci.yml` pytest PYTHONPATH 에 repo 루트(`.`) 추가(`import shared` collection 해소) + `web→feature-0003 src` 심링크(컨테이너 `import web.app` 가정 테스트 해소) + `test_product_delete_block_conv` fake 에 TASK-0302 `SELECT IsDefault` 분기. CI 동일 환경 전체 suite **green(exit 0)**, main CI 장기 red 해소. (CHG/REV-20260624T090534-ci-pytest-green)

### TASK-20260625-doc-sync-release-notes — 직전 릴리즈노트(0fd4ca9, 06-23 16:52) 이후 머지분 릴리즈노트 정합 (doc_sync maintenance, Minor §12.3 — 정적 콘텐츠)
- 출처: `/_dqa:doc_sync` 정기 정합. `src/static/release-notes-data.js`(사용자 노출 릴리즈노트, 정적 큐레이션 데이터)가 직전 sync(0fd4ca9, 2026-06-23 16:52) 의 06-23 블록에 멈춰 있어, 그 이후 main 병합된 user-facing 변경 14건(late 06-23 + 06-24)이 릴리즈노트에 미반영(doc/reality drift). **윈도 정의 = 직전 릴리즈노트 commit(0fd4ca9) 이후 전체 — 단순 '06-24' 가 아님(적대 검증 Lens B 가 late-06-23 16:52~19:16 머지 누락 적발 → 정정 반영).**
- 범위: **릴리즈노트 콘텐츠 데이터만** — 렌더 로직(release-notes.js)·백엔드·스키마·RBAC 무변경. 사용자 평이화 문구(내부 구현/테이블명/feature-id/엔드포인트 비노출).
- [x] `release-notes-data.js`: `releases` head 에 `date: "2026-06-24"` 블록 prepend(admin 5 · work 9 · 총 14 항목 — [new admin] 메타데이터 등록 / AI 자동작성 / 샘플 검수 / 인사이트 탐색 상태(관리 콘솔 제품 관리) · [new work] AI로고치기 / 공유 참여자 / 답변 피드백+샘플등록 / 멘션·데스크톱 알림 제어+음소거 · [improved work] 보관 이동+나가기(owner) / 참여허용 게이트 / 사이드바 그룹 구분 · [fixed admin] 미반영 fix · [fixed work] 알림 표기 / 공유 직후) + `generated` `2026-06-23`→`2026-06-25` 갱신.
- [x] 검증: 사용자 평이화 원칙 준수(스키마 type/area/title/detail 정합) + `node --check release-notes-data.js`(JS 구문). 머지된 커밋 14건 대조(윈도=직전 릴리즈노트 0fd4ca9 이후 — late-06-23 e5acb43(답변 피드백)·43687e9(사이드바 구분) + 06-24 eb459e4(알림 제어) 포함) — 내부/비-user-facing(shared 추출·SSOT·CI·발표자료·doc_sync)은 의도적 제외.
- [x] **리뷰(REVIEW REV-20260625T092403-doc-sync-release-notes [SKIPPED]):** 정적 사용자노출 콘텐츠 큐레이션 — 제품 로직·인가·스키마 무변경, 적대 패널 불요(§18.4 비-정책 doc 경량 cycle).
- [ ] verify-completion → 머지 → web 재배포(static baked) → 마감.

### TASK-20260625T021924-rule-db-coverage — 정규식 자동 규칙(rule)으로 추가된 DB 도 insight 분석 여부·완료율 UI 표시 (Minor §12.3 — frontend-only 비파괴 표시)
- 사용자 요청(/_template:entry): "`관리 콘솔 > 제품 > [각 항목] > '데이터 소스 & 접근 가능 데이터베이스' > 정규식 자동 규칙` 기능을 통해 추가된 DB에 대해서도 insight 분석 여부 및 분석 완료율이 UI로 출력되도록 구성."
- 진단(Explore + 코드 검증): 백엔드 `_compute_product_insight_coverage`(app.py)는 이미 `_list_product_databases` 전체 행(Source=manual/rule 무관)으로 coverage 를 계산해 `per_db[]` 에 **rule DB 도 포함**한다. gap 은 **frontend 전용** — (1) 메인 DB 목록(`redrawChips`)이 rule 행을 제외(`if (_isRuleRow) return`)하고, (2) 규칙 카드의 종속 DB 항목(`_buildRuleCard`)은 이름만 표시하고 `buildDbCoverageCells` 를 호출하지 않아 분석 여부·완료율이 누락.
- 등급: **Minor §12.3** — 비파괴 UI 표시 추가(신규 백엔드/스키마/RBAC/엔드포인트 0, 기존 `productCoverage.per_db` 재사용). frontend-only.
- [x] **admin.js `_buildRuleCard`**: 규칙 종속 DB 루프에 coverage cell 추가 — `adminState.productCoverage.get(product.id).per_db` 를 db명(소문자) 키 Map 으로 만들어 `buildDbCoverageCells(covRow, _isProductCoverageLoading(product.id))` 호출. 연결 불가 행 `is-offline`. 메인 목록 행과 동일 helper 재사용(분석 여부 DB✓/✗ · 완료율 ta/tt 마이크로바 · 측정 대기/중).
- [x] **styles.css**: `.cov-db-rule-dbitem`(flex)용 coverage cell 폭/우측정렬 CSS(`.cov-microbar{width:52px;flex:0 0 auto;margin-left:auto}` 등) — grid 셀이 폭을 주는 메인 행(`.cov-db-row`)과 달리 flex 에선 마이크로바가 0 으로 접히므로 명시.
- [x] **admin.html cache-buster**: `?v=20260624-metadata-ai-autocomplete` → `?v=20260625-rule-db-coverage`(styles.css + admin.js).
- [x] **적대 리뷰(REV-20260625T021924-rule-db-coverage [SUBAGENT:adversarial-frontend] — SHIP) MAJOR 1 흡수**: **M1** — 규칙 카드(`_renderRuleEditor`)는 `if (canManage)` 게이트라 read-only 뷰어(product.read 만, product.manage 없음)는 카드를 못 보는데 메인 목록은 rule 행을 무조건 제외 → 규칙 DB 가 **어디에도 안 보임**(요청 불변식 위반). → 메인 목록 skip 을 `if (_isRuleRow && canManage) return;` 로 조건부화(read-only 뷰어는 규칙 DB 를 메인 목록에 coverage 와 함께 노출). 흡수 후 SHIP. MINOR(다중 datasource 동명 DB 이름키 lookup — 메인 목록과 동일 기존 한계 / 규칙 DB 초기화 버튼 의도적 미노출)는 수용.
- [x] **검증**: `node --check admin.js` PASS + 신규 `tests/verify_rule_db_coverage.mjs` **20/20 PASS**(jsdom 으로 buildDbCoverageCells 분석여부·완료율 렌더 + 규칙 카드 wiring + M1 조건부 skip + CSS + cache-buster). 인접 회귀 `verify_dbpicker_search_regex.mjs` 영향 없음(기존 cache-buster 단언 1건은 본 cycle 이전부터 stale — pre-existing).
- [ ] verify-completion → commit/push → PR·머지 → web 재배포(deploy_scope: included, static baked) → **PB-0008 Windows-browser 시각 검증**(제품 상세 '데이터 소스 & 접근 가능 데이터베이스' > 규칙 카드의 '이 규칙으로 추가된 DB' 항목에 분석 여부·완료율 표시) → 마감. (WSL worktree 라 PB-0008 미실행 — 배포 후 사용자 확인.)

### limit-subject-msg — 계정 당 토큰 한도 초과 메시지 주체 명시 (cross-feature, feature-0002 주관, Minor §12.3, 2026-06-25)
- 사용자 요청(/_template:entry): 요청량 한도 도달 시 주체 구분(계정 당 / 서비스 자체). 본 feature 는 **계정 당** 한도 메시지 담당(서비스 메시지·정본 = feature-0002).
- 등급: **Minor §12.3** — 사용자 노출 메시지 문구만(429 게이트 로직·RBAC·스키마 무변경).
- [x] **`src/app.py` `_check_account_token_quota`**: 토큰 한도 초과 메시지 `f"{일일/월간} LLM 토큰 한도(N)를 초과했습니다..."` → `f"계정의 {일일/월간} LLM 토큰 사용 한도(N)를 초과했습니다..."`. "계정의" 주체 명시로 서비스 자체 요청량 한도(feature-0002 KIND_THROTTLED)와 구분. 사유 주석 2줄.
- [x] 검증: py_compile(app.py) PASS. 메시지 텍스트 단언 테스트 부재(test_llm_usage_quota L82=allowed 케이스 msg=="" / test_auto_account_prompt=stub) → 무회귀.
- [x] 리뷰(REVIEW REV-20260625T045450-limit-subject-msg [SKIPPED]): 메시지 문구만 → 적대 패널 불요.
- [ ] verify-completion → commit/push → (PR·머지·배포는 사용자 confirm) → 마감.

### steps-btn-pending-persist — 새 요청 진행 중 이전 답변 "단계 보기" 버튼 소실 수정 (Minor §12.3, frontend-only, 2026-06-25)
- 사용자 요청(/_template:entry): 대화 중 새 요청을 보내면 이전 assistant 답변의 "단계 보기 (N)" 버튼이 일시적으로 사라지고, 답변 완료+새로고침 후 다시 보이는 버그 수정. (REQ-20260625-steps-btn-pending-persist, TASK-20260625T103503-steps-btn-pending-persist)
- 근본원인: `renderMessages()` 가 새 요청 시작(`sendPrompt` → `state.pendingBubble` 세팅 직후 재호출)될 때, 이전 답변의 "단계 보기" 버튼 부착 조건이 `&& !state.pendingBubble` 가드에 막혀 렌더되지 않음. 영속 step 데이터(`message.meta.steps`)는 pending 상태와 무관하게 유효하므로 가드가 오작동.
- 등급: **Minor §12.3** — frontend `static/app.js` 단일 파일, 렌더 조건 로직만(비파괴·인가/스키마/백엔드 무변경).
- [x] **수정① app.js `renderMessages()`**: meta.steps 버튼 부착 조건 `if (msgMetaSteps.length && !state.pendingBubble)` → `if (msgMetaSteps.length)`. 이전 답변의 영속 step 버튼은 진행 중에도 항상 표시.
- [x] **수정② app.js `renderMessages()`**: `lastCompletedRunSteps` fallback 블록의 `if (!state.pendingBubble)` → bare block(가드 제거, `cr` 스코프 유지). `:not(.is-pending)` 선택자 + `.bubble-steps-btn` 존재검사가 중복/오부착 차단하므로 안전.
- [x] **수정③④ app.js step side panel**: `state.stepSidePanelLive` 필드 신설. `openStepSidePanel` 이 `pending === state.pendingBubble` 일 때만 live=true 로 표시, `refreshStepSidePanel` 은 live 일 때만 폴링 갱신 → 가드 제거로 생길 수 있는 새 엣지(진행 중 이전 답변 단계 패널을 열어둔 채 라이브 폴링이 덮어쓰기)를 차단. `closeStepSidePanel` 닫을 때 false 리셋(방어적).
- [x] **검증**: `node --check app.js` PASS + 적대적 frontend 리뷰(REV-20260625T103503-steps-btn-pending-persist [SUBAGENT:adversarial-frontend-8hypothesis-PASS] — SHIP) BLOCKER/MAJOR/MINOR 0, NIT 2(NIT-1 흡수, NIT-2 pre-existing 보류). H1~H8 전부 반증 실패.
- [x] verify-completion PASS → commit/push → PR #446 머지(main drift 충돌 해결: doc-sync PR#445 와 docs tail 양측 보존 머지, app.js 는 비겹침 자동머지) → web 재배포(`sudo make web`, repo-web-1 healthy). 단 **app.js cache-buster bump 누락** 발견 → 아래 후속 cycle.

### steps-btn-cachebust — app.js cache-buster bump (steps-btn-pending-persist 전파 보강, Minor §12.3, frontend-only, 2026-06-25)
- 배경: steps-btn-pending-persist 가 `static/app.js` 내용을 바꿨으나 index.html 의 `app.js?v=` 캐시버스터를 bump 하지 않아, 같은 `?v=20260625-gc-unread-read-fix` 로 app.js 를 이미 캐시한 사용자에게 수정이 전파되지 않을 수 있었음(app.py:10582 TASK-0256d: 정적 자산은 `?v=` 가 유일 전파 메커니즘, HTML 만 no-cache).
- 등급: **Minor §12.3** — index.html script src 쿼리 문자열 1줄. 로직·백엔드·스키마 무변경.
- [x] **index.html**: `app.js?v=20260625-gc-unread-read-fix` → `?v=20260625-steps-btn-pending-persist`. (app.js 는 index.html 에서만 로드 — admin/share 무관)
- [x] 검증: 새 `?v=` 가 강제 재요청 유발 → 모든 사용자가 수정된 app.js 수신. REVIEW [SKIPPED:cache-buster-only-no-logic].
- [ ] verify-completion → commit/push → PR·머지 → web 재배포 → 마감.

### TASK-20260625T204254-conv-switch-fade — 작업 화면 좌측 대화 전환 크로스페이드(fade-out/in + 가속) (Minor §12.3, frontend-only, 2026-06-25)
- 사용자 요청(/_template:entry): 좌측 사이드 대화 전환 시 클릭 후 약간의 텀 뒤 대화가 곧바로 나타남(동작 정상·일반 메신저 동작이나 "딜레이+무전환"이 성능 이슈로 인식될 수 있음). 개선: ① 전환 시 기존 화면 즉시 부드러운 fade-out, ② 목표 대화도 부드러운 효과로 등장, ③ 목표가 fade 효과보다 빨리 로딩되면 이전 효과를 가속해 자연스럽게 전환.
- 진단(Read+코드 검증): `selectConversation`(static/app.js)이 `/api/use_conversation`→`loadHistory`(`/api/history`)→`renderMessages`(messageLog.innerHTML 재구성)의 두 await 동안 직전 대화를 화면에 남겼다가 갑자기 교체 → 전환 효과 부재가 체감 성능 저하로 인식. 등급 **Minor §12.3**(frontend `static/{app.js,styles.css,index.html}` 비파괴 — 백엔드/스키마/RBAC/엔드포인트 0).
- [x] **app.js 코디네이터 신설**: `_beginConversationCrossfade`(클릭 즉시 현재 messageLog 를 cloneNode 한 "고스트"를 messages-wrap 위 absolute 오버레이로 띄워 fade-out 시작 + 실제 messageLog 즉시 opacity 0 → 목표 대화 invisible 재구성), `_commitConversationCrossfade`(콘텐츠 준비 후 목표 fade-in + 남은 고스트 fade-out 가속), `_removeSwitchGhost`(transitionend/fallback 타이머 정리), `_prefersReducedMotion`. 상수 `MSG_FADE_OUT_MS=150 / IN=200 / ACCEL=90`.
- [x] **app.js selectConversation 배선**: 같은-대화 재클릭 가드 직후 begin 호출(클릭 즉시 fade-out), use_conversation+loadHistory+pending 복원을 try/catch 로 감싸 정상/에러 양쪽에서 commit(가시성 복원) — 네트워크 실패 시 빈 화면(opacity 0 stuck) 방지 후 에러 전파.
- [x] **styles.css**: `.messages-switch-ghost`(position absolute · box-sizing border-box · overflow hidden · z-index 3 · pointer-events none · will-change opacity) + `@media (prefers-reduced-motion: reduce)` display:none. `.message-point-rail` 에 `z-index:4`(고스트 위 — rail dot 비가림 보강, 적대 리뷰 MAJOR 흡수).
- [x] **index.html cache-buster**: `styles.css?v=…gc-participant-product-select`·`app.js?v=…composer-clear-input` → 둘 다 `?v=20260625-conv-switch-fade`(정적 자산 전파 — app.py TASK-0256d: `?v=` 가 유일 전파 경로).
- [x] **reduced-motion 보존**: prefers-reduced-motion 사용자에게는 begin/commit no-op → 기존(즉시 교체) 동작 그대로 유지.
- [x] **적대 리뷰(REV-20260625T204254-conv-switch-fade [SUBAGENT:adversarial-frontend-8hypothesis] — SHIP-WITH-FIXES → 흡수 후 SHIP)**: H4 결함 적발 — **MAJOR(방어)** 고스트 z-index 가 point-rail(z-index auto) 가릴 fragility → rail z-index:4 흡수. **MINOR** fade-in 후 messageLog 인라인 opacity/transition 잔류 → transitionend 에서 정리 흡수. H1(연속전환 누수)·H2(가속 transitionend 어긋남)·H3(에러/empty/pending stuck)·H5(중복 id getElementById, 고스트가 DOM 후순위라 real 노드 우선)·H6(비전환 renderMessages 부작용)·H7·H8 전부 반증 실패=안전.
- [x] **검증**: `node --check app.js` PASS + CSS brace balance 1585/1585 + 적대 리뷰 SHIP. (전환은 CSS transition/transitionend·timer 기반이라 jsdom 단위테스트 부적합 — 정적검사+적대리뷰로 대체, steps-btn-pending-persist cycle 선례 동일.)
- [x] verify-completion PASS(9/9) → commit 1da8b07 → main drift(#452 dialect, 무충돌) 위로 rebase 8728ade → main ff-merge(`2c348f0..8728ade` origin push) → web 재배포(`sudo make web`, repo-web-1 healthy, baked GIT_COMMIT 8728ade, 서빙 index.html cache-buster `conv-switch-fade`·app.js 크로스페이드 함수 baked 확인). PR 미생성(global 정책: main 병합 auto / PR 생성 confirm — 로컬 ff 병합).
- [ ] **PB-0008 Windows-browser 시각 검증**(대화 전환 시 fade-out/in 크로스페이드 + 빠른 로딩 시 가속) — WSL worktree 라 미실행, **배포 후 사용자 확인 필요**.

### TASK-20260626T080501-doc-sync-rn-0626 — 릴리즈노트 06-25 후속 머지분(6건) 정합 + cache-buster bump (doc_sync, 비-정책 doc, 2026-06-26)
- 트리거: `/_dqa:doc_sync`(스케줄 무인 실행, 전 타깃). 릴리즈노트 마지막 sync(a29a2f0 @ 2026-06-25 19:36) 이후 main 병합된 06-25 user-facing 변경을 기존 '2026-06-25' 블록에 추가(items 14→20) + `index.html`·`admin.html` cache-buster `?v=20260625c-rn-0625`→`?v=20260626-rn-0626` + generated 2026-06-25→2026-06-26.
- [x] 대상 머지(6, 평이화·내부 비노출): [fixed work] 단계 보기 버튼 소실 수정(998376b) · [improved work] 좌측 대화 전환 크로스페이드(8728ade) · [fixed work] 공유 링크 대화 참여 불가(92753ab) · [fixed work] 읽은 그룹 대화 안 읽음 배지 미감소/되살아남(9b1dc16·36ad138·d90e1e2 통합) · [fixed work] @assistant 전송 후 입력창 미클리어(bec35bd) · [improved work] 그룹 대화 AI 답변 정확도 — 데이터 종류 맞춤 조회+대화 맥락(feca44f).
- [x] 콘텐츠 데이터만 — 렌더 로직·백엔드·스키마·RBAC 무변경. ULTRACODE 3축 워크플로(분석→적대검증→완전성 비평) VERDICT pass/go-with-fixes, 머지 6건 1:1 대조 CLEAN. 비-user-facing(c2ed580 캐시버스터·7c89b7d META skill 정책·3a7da05 cycle 마감) 제외 확인.
- [x] 검증: `node --check release-notes-data.js` PASS + 항목 스키마(type/area/title/detail) 정합 + 06-25 블록 14→20.
- [x] META(STATUS·wiki) 별도 commit 분리. verify-completion(operational, feature-0003) → 로컬 commit. landing(push/PR/merge)·deploy 는 cron wrapper 소관.

### TASK-20260626T130501-doc-sync-rn-0626b — product-chip(처리 중 제품 선택 가능) 릴리즈노트 06-26 블록 + cache-buster bump (doc_sync, 비-정책 doc, 2026-06-26)
- 트리거: `/_dqa:doc_sync`(스케줄 무인 실행, 전 타깃, ULTRACODE). 릴리즈노트 마지막 sync(cd05fa1 @ 2026-06-26 08:35) 이후 main 병합된 user-facing 변경(f049fee, 12:05)이 릴리즈노트 미반영(drift). 신규 '2026-06-26' 블록(1항목) prepend + `index.html`·`admin.html` cache-buster `?v=20260626-rn-0626`→`?v=20260626b-rn-0626`. generated 메타는 이미 2026-06-26(무변경).
- [x] 대상 머지(1, 평이화·내부 비노출): [improved work] 답변 처리 중에도 제품 선택 변경 가능 — 처리 중 제품 선택 잠금 해제, 변경은 다음 질문부터 반영(f049fee TASK-0047 race 가드 3계층 완화, ADR-WEB-0006).
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. ULTRACODE 워크플로(3타깃 read-only 분석→타깃별 적대 검증) window 독립 재확인: cd05fa1..HEAD user-facing 단일(f049fee), late-merge 누락 0. 내부용어("칩"/PATCH 409/run_kwargs/race guard/feature-id) 누출 0.
- [x] 검증: `node --check release-notes-data.js` PASS + 항목 스키마(type/area/title/detail) 정합 + releases head '2026-06-26' 블록 신설.
- [x] META(STATUS·wiki) 무변경(이번 run delta 0 — STATUS feature-0003 행은 f049fee가 이미 반영, wiki는 minor timing-guard 완화라 카드/Log 무변경). 따라서 operational 단일 commit. verify-completion(operational, feature-0003) → 로컬 commit. landing(push/PR/merge)·deploy 는 cron wrapper 소관.

### TASK-20260629T080501-doc-sync-rn-0629 — assistant 요청 2번 중복 처리 차단(ask-dedup) 릴리즈노트 06-26 블록 합류 + cache-buster bump (doc_sync, 비-정책 doc, 2026-06-29)
- 트리거: `/_dqa:doc_sync`(스케줄 무인 실행, 전 타깃, ULTRACODE). 릴리즈노트 마지막 sync(483c4c0 @ 2026-06-26 13:25) 이후 main 병합된 user-facing 변경(ask-dedup-idempotency 0818b0a 13:51·3595ea3 14:00)이 릴리즈노트 미반영(drift). 기존 '2026-06-26' 블록(product-chip)에 [fixed/work] 1항목 합류 + summary 보강 + generated 06-26→06-29 + `index.html`·`admin.html` cache-buster `?v=20260626b-rn-0626`→`?v=20260629-rn-0629`.
- [x] 대상 머지(1, 평이화·내부 비노출): [fixed work] 같은 질문이 드물게 두 번 처리되던 문제 수정 — 답변 대기 중 연결이 잠깐 끊겨 같은 질문을 다시 보냈을 때 드물게 두 번 처리·답변되던 것을 한 번만 처리되도록 수정(0818b0a 워커모드 enqueue 멱등화 + 3595ea3 AmbiguousParameter 회귀 격리).
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. ULTRACODE 워크플로(완전성 비평 + 타깃별 적대 검증 + 릴리즈노트 비노출 반증) window 독립 재확인: 483c4c0..HEAD user-facing 단일(ask-dedup 0818b0a/3595ea3), late-merge 누락 0. 내부용어(enqueue/dedup/NOT EXISTS/AmbiguousParameter/long-poll/502/ask_jobs/feature-id) 누출 0(refuted:false·leaksInternals:false).
- [x] 검증: `node --check release-notes-data.js` PASS + 항목 스키마(type/area/title/detail) 정합 + 06-26 블록 items 1→2(fixed 항목 추가).
- [x] META(STATUS·wiki) 별도 commit 분리(STATUS feature-0003 행 ask-dedup 1줄 + wiki hot/overview/Log product-chip·ask-dedup backfill). verify-completion(operational, feature-0003) → 로컬 commit. landing(push/PR/merge)·deploy 는 cron wrapper 소관.

### TASK-20260629T114221-metadata-bootstrap-mssql-db — 관리 콘솔 > 메타데이터 > 테이블/컬럼 설명: MSSQL database 차원 미처리로 인한 "테이블 명칭 모두 오류" + 패널 내부 잘림 수정, AI 자동완성 정상화 (Major §12.3 — cross-engine 골격 introspection, 2026-06-29)
- 트리거: `/_template:entry` arg-given. 사용자 보고: "메타데이터 > 테이블 설명에서 (1) 각 데이터소스·스키마 테이블 설명도 AI 자동완성 구성, (2) 테이블 명칭이 모두 올바르지 않은 값, (3) 패널 내부 공간이 확장 안 돼 UI 내부 잘림(컬럼 설명 탭 동일)".
- REQ: REQ-20260629T114221-metadata-bootstrap-mssql-db (FUNCTION.md). AC: AC-…-1(MSSQL 골격이 tempdb 임시테이블이 아닌 선택 DB 실테이블) · AC-…-2(테이블/컬럼 서브뷰 부트스트랩 패널 내부 잘림 없음) · AC-…-3(테이블 설명 단건·일괄 AI 자동완성이 선택 DB+테이블에 grounding).
- **진단(라이브 introspection 직접 재현, app 내부 함수 직호출)**: AI 자동완성(단건 `/api/admin/metadata/tables/suggest` + 일괄 `bootstrap/describe`)은 **이미 구현돼 있었음** → 요청 (1) 은 신규 아님. "테이블 명칭 모두 오류"의 정체 = **MSSQL 데이터소스 골격**: `admin_bootstrap`/`_bootstrap_collect_skeleton` 이 `database=None` 으로 연결 → shared/db.py `_connect_mssql` 의 설계상(보안: 무자격 2-part 쿼리 차단) **중립 `tempdb` 고정** → `tempdb.dbo` 의 임시테이블(`#A0A50030`…)이 골격으로 노출. + "스키마" 드롭다운이 `load_known_schemas`(sys.schemas) raw 라 SQL Server 고정 역할 스키마(`db_datareader`·`db_owner`…)로 오염. MySQL 은 schema==database 라 원래 정상(`account_db`→`account`·`billing_history`). `table_descriptions`/`column_descriptions` DB 0행 확인 → 저장목록 아닌 골격 경로 확정.
- **설계(사용자 AskUserQuestion 확정)**: MSSQL 은 server>database>schema>table 4계층인데 테이블 설명 모델은 (scope_key=datasource, schema_name, table_name) 3-키 → **schema_name = database 명** 으로 매핑(MySQL 도 이미 schema==DB 라 일관). 부트스트랩 unit = MySQL:schema / MSSQL:database.
- [x] **백엔드(app.py)**: `admin_bootstrap_schemas` 엔진분기 — MSSQL=`list_server_databases`(시스템 DB master/model/msdb/tempdb 제외), MySQL=`load_known_schemas`(시스템 스키마+`__invalid_default_db__` 센티넬 제외); 응답에 `engine`·`unit_kind` 추가. `admin_bootstrap` — MSSQL 은 schema 파라미터=database, 시스템 DB 제외 allowlist 검증 후 해당 DB 로 연결 + 신규 `_bootstrap_collect_skeleton_mssql`(비시스템 SQL 스키마 평탄수집, 저장 schema_name=DB, 동명테이블 dedupe). `_metadata_introspect_table`(단건 suggest grounding) 동일 엔진분기 — MSSQL schema_name=DB 로 grounding(이전엔 tempdb 검증 실패→ungrounded). `_BOOTSTRAP_MYSQL_SYS_SCHEMAS` 상수 추가.
- [x] **프론트(admin.js/admin.html)**: `_metaBootstrapLoadSchemas` 가 `unit_kind` 로 라벨/플레이스홀더/상태문구 분기(MySQL='스키마', MSSQL='데이터베이스'); `_metaBootstrapUnitWord`/`_metaBootstrapSetUnitLabel` 헬퍼; `metadataBootstrapSchemaLabel` id 부여. `_metaBootstrapFetch` 안내문구 엔진인지.
- [x] **CSS(styles.css)**: `.admin-meta-bootstrap-result` 의 `max-height:460px;overflow:auto` 제거 — metadata pane 이 이미 `overflow-y:auto` 라 이중 스크롤(내부 460px 갇힘)이 "패널 내부 미확장 잘림"의 원인. 캡 제거로 자연 확장, 스크롤은 pane 담당(테이블/컬럼 서브뷰 공통).
- [x] **라이브 검증(전부 통과)**: ① app 내부 introspection 직호출 — MSSQL `GunzGame` 88 실테이블·schema_name=GunzGame·임시테이블 0 / MySQL 센티넬 제외. ② 실 HTTPS API(curl, admin 세션) — `bootstrap/schemas` MSSQL engine=mssql·unit_kind=database·129 DB(tempdb 없음)·MySQL unit_kind=schema·센티넬 제거 / `bootstrap` GunzGame 88테이블 all schema_name=GunzGame·temp 0 / `tables/suggest` grounded=true(29컬럼)·정확 설명 생성(claude-haiku-4). ③ Playwright 브라우저 서비스(repo-browser-1, WSL-headless) eval — 메타데이터 탭 노출·tables 서브뷰·부트스트랩 패널 visibleOnPage=true·`.admin-meta-bootstrap-result` computed maxHeight='none'·라벨 '데이터베이스 *'·129 DB·GunzGame 88테이블 렌더·스크린샷(`artifacts/shared/out/browser/claude_verify_dbdropdown.png`).
- [x] **§18.8 적대 verification panel (general-purpose 2-lens)** — lens1 보안 VERDICT SAFE(SQLi·allowlist·의존함수·시스템객체·RBAC·dialect·자원누수 7항목 반증 실패). lens2 정합성: 1차 **MAJOR**(Path A — describe_table 컬럼 오버레이 read 축이 schema_name=DB 규약과 불일치, 부트스트랩 컬럼 설명이 describe_table 도구 출력에 미주입; 질문-시점 grounding Path B 는 정상) 적발.
- [x] **Path A 포함 결정(사용자 AskUserQuestion: "지금 포함")** → cross-feature feature-0002 read 축 정합 수정: (a) `tools.py` `_tool_describe_table` 오버레이 조회 키 MSSQL=`get_active_default_db()`(pin DB명) (b) panel 2차 재검증이 **BLOCKING**(pin DB명 소문자 정규화 vs 저장값 원본 케이스 → PG `=` case-sensitive 0행, 대문자 포함 DB명 전부 미적중) 적발 → `kb_metadata.py` `load_column_descriptions_for_table` schema 매칭 case-insensitive(`LOWER`) → 3차 재검증 **VERDICT SAFE**(NIT 2 선재·비회귀 수용).
- [x] **문서 갱신**: FUNCTION(REQ+AC) · TASK · REPORT · REVIEW([SUBAGENT:adversarial-2lens] check#9 + panel 수렴 기록) · MODIFY(feature-0003 본진 + feature-0002 cross-feature) · TEST · STATUS · wiki(Log/hot). (원본 세션이 문서 갱신 중 중단 → `/_template:resume` 로 완수.)
- [ ] **PB-0008 Windows-browser 시각 검증**(테이블/컬럼 설명 부트스트랩 DB선택→실테이블 골격·패널 비잘림·AI 일괄생성·describe_table 컬럼 설명 노출) — WSL worktree 라 미실행, **배포 후 사용자 확인 권장**(선례 동일).
- [ ] verify-completion --pre-commit PASS → commit(Task-Cycle trailer) → push → main merge → web+ask-worker 재빌드·재배포(deploy_scope: included) → healthz/smoke.

### TASK-20260629T143914-share-mermaid-responsive — 공유 대화 뷰 mermaid(flowchart) 렌더 + 공유 페이지 전체 폭 반응형 (Minor §12.3, frontend-only, feature-0013 후속, 2026-06-29)
- [x] mermaid 헬퍼 4종(enhance/init/render/fallback)을 app.js→신규 `mermaid-render.js` 추출(메인/공유 단일 소스, `securityLevel:'strict'` 일원화) + app.js 호출부 2곳 `typeof` 가드(NIT-1).
- [x] index.html·share.html 에 `mermaid.min.js`+`mermaid-render.js` 로드(순서: mermaid→render→app/share) + cache-buster bump(app.js `20260629c`, share `20260629-share-mermaid`).
- [x] share.js `renderMarkdownContent`: `enhanceMermaidBlocks`(sanitize 이전)+`renderMermaidDiagrams`(innerHTML 이후) 연결, 미로드 시 typeof 가드 폴백.
- [x] share.css: `.share-container` 960px 고정폭→`max-width:100%` 전체 폭 반응형(clamp 패딩) + `.share-message-content .mermaid-*` 규칙(overflow-x:auto).
- [x] §18.8 적대 패널(SUBAGENT security+correctness): **no BLOCKING** — XSS posture 동일·추출 byte-identical·로드순서·fallback·반응형·회귀 전부 SAFE. NIT-1 적용 / NIT-2(다이어그램 없어도 mermaid 로드) defer.
- [x] 검증: node --check(mermaid-render.js·app.js·share.js) PASS · app.js 추출 잔여참조 0 · DOMPurify 설정 무변경.
- [x] verify-completion PASS(9/9) → commit cbd54f4 → main 통합(머지, 충돌 0) → PR #464 머지(main 37d58cc) → web 재빌드·재기동(deploy_scope: included, healthz ok).
- [x] PB-0008 Windows-browser 시각 검증(실 Chrome 149) — **① 메인 뷰 무회귀**: markdownToHtml→renderMermaidDiagrams flowchart SVG(7501) error 0. **② 공유 뷰**: share 렌더 경로 flowchart SVG(7637) error 0 + `.share-container` maxWidth=100%·실폭 1249=viewport(전체 폭). 증적 `artifacts/pb0008-share-mermaid-responsive.png`.
- [x] 배포-기록 REVIEW 엔트리(REV-20260629T144600-share-mermaid-responsive-deploy [SKIPPED:deploy-record]) 추가 — verify-completion check#9 정합.

### TASK-20260629T080500-new-conv-dedup — "새 대화" 첫 전송 시 사이드바 대화 중복('현재 대화' + 별도 '새 대화') 제거 (Minor §12.3, frontend-only, 2026-06-29)
- 트리거: `/_template:entry` arg-given. 사용자 보고: "프로젝트 내 서비스로 assistant 에게 새 대화에서 요청을 보내면, 좌측 사이드바(대화 목록)에 현재 대화 항목과 더불어 '새 대화' 가 추가로 생성됨(진입점 완전히 동일한 중복 대화)."
- REQ: REQ-20260629T080500-new-conv-dedup (FUNCTION.md). AC: AC-…-1(early-cid 등재 시 placeholder 원자적 제거→중복 0) · AC-…-2(optimistic 항목 topic 키→메시지 제목 표시) · AC-…-3(첨부 lazy-create 경로 동일).
- **진단(Explore + 코드 정독)**: `sendPrompt`(app.js) lazy-create early-cid 성공 블록이 실 cid 대화 항목을 `state.conversations` 에 unshift+render 하면서도, in-flight placeholder(`pendingConversationEntries[busyKey]`)는 `/api/ask` 응답(8421)까지 제거하지 않음 → early-cid 발급~응답 도착(실 LLM 응답 시간) 동안 ① placeholder(메시지 제목)와 ② optimistic 항목이 사이드바에 동시 렌더. 게다가 optimistic 항목이 `buildCompactItem` 미인식 `title` 키로 등재돼(읽는 키=`topic`) 폴백 "새 대화" 로 표시 → 중복의 '새 대화' 라벨 출처. 다른 정리 경로(fallback 8421·422-fallback·취소·실패)는 placeholder 를 delete 하나 early-cid 성공 경로만 누락.
- [x] **수정(app.js 3곳)**: early-cid 블록 — optimistic 등재 전 `pendingConversationEntries.delete(busyKey)` + `title`→`topic` + render 를 find-guard 밖으로(항상 재렌더). `/api/ask` fallback 블록 — 동일 정합(8421 delete 멱등 보존). 파일 첨부 lazy-create(~7337) optimistic 등재 `title: "(파일 첨부 중)"`→`topic:`.
- [x] **cache-buster**: `index.html` app.js `?v=20260629c-share-mermaid`→`?v=20260629d-new-conv-dedup`.
- [x] **단위 검증**: `node --check app.js` PASS. 신규 `tests/verify_new_conv_dedup.mjs` **18/18 PASS**(Node18+jsdom@22) — [A] 정적 불변식(두 optimistic 등재 직전 placeholder delete·직후 render·topic 키·title 잔존 0·cache-buster), [B] 실 `renderConversationList` jsdom: 수정 후=실 항목 1·placeholder 0·제목=메시지 / 회귀 재현=placeholder 1 + '새 대화' 항목 1(동시 2개). 기존 `verify_conv_entry_defaults.mjs` 20/20·`verify_date_group_collapse.mjs` 22/22 무회귀.
- [x] **§18.8 적대 패널(SUBAGENT correctness)**: 5개 회귀 가설(catch/cancel/lazy-fail·delete 충돌·render 이동·title→topic 소비처·mismatch 오염) **전부 REFUTED, no BLOCKING**. 패널이 `title`→`topic` 이 backend payload 키(`"topic"`, app.py 7145/7511)와 일치시키는 기존 버그 수정임을 독립 확인. REV-20260629T080500-new-conv-dedup.
- [ ] **PB-0008 Windows-browser 시각 검증**(새 대화 첫 전송→사이드바 항목 1개·진행 중 placeholder 비중복) — WSL worktree 라 미실행, **배포 후 사용자 확인 권장**(frontend-only render, 선례 동일).
- [x] verify-completion --pre-commit **PASS(9/9 + #12)** → commit → 최신 main(8a35eee) 재rebase(doc tail 충돌 해소) → ff-merge main(92751b4) → push origin main → **web 이미지 재빌드·재기동(deploy_scope: included)**. 라이브 검증: healthz HTTP 200 · 서빙 index.html `app.js?v=20260629d-new-conv-dedup` · 서빙 app.js 에 fix 반영(new-conv-dedup 주석 5·`topic: message.slice` 2). repo-web-1 healthy.

### TASK-20260629T172122-diff-lineno-prefix-leak — ```diff 답변의 누출된 `<N>→` 줄번호 prefix 정규화 (Minor §12.3, frontend render-only, 2026-06-29)
- 트리거: `/_dqa:conversation_audit "계정 연동 및 보상 일괄 수령 쿼리 구성"`. 사용자 보고: "diff 포맷을 통해 답변할 때, 정상적이지 않은 line 표현이 확인되어 수정이 필요". 진단 대화 `…356708b8`, assistant msg id 4058. 마찰 = `FR-diff-lineno-prefix-leak`(FRICTION_LEDGER).
- **진단(코드+DB+전사 삼각측량, rootcause_confidence high)**: agent_core `_number_file_lines`(feature-0002, TASK-0256e)가 첨부 본문 각 줄에 `<N>→` 줄번호 prefix 주입. 프롬프트(agent_core.py:770-778)가 diff 안 `<N>→` 금지를 지시하나 **모델이 context 줄에 `45→\t…` 그대로 누출**(변경줄만 표준 `+`/`-`). 웹 렌더러 `buildDiffRows`(app.js·share.js)가 누출 prefix 미정규화 → diff-ctx 코드 본문으로 렌더돼 줄 표현 깨짐(gutter 는 1-based 별도 계산). 레이어 L1↔L6→L7. 재발경로 model limit → 렌더러를 결정론적 최후 방어선으로 봉인.
- **corroboration**: 전체 기간 ```diff 사용 대화 20건 중 누출 1건(이 대화) → 빈도상 idiosyncratic. 그러나 사용자 명시요청 + RC 코드 확정 + 결정론적 저위험 봉인 → fix-now(전역 프롬프트 행동 재작성 아닌 자기-주입 artifact 의 결정론적 정규화 — 과적합 아님).
- [x] **수정(2곳, feature-0003)**: `src/static/app.js`·`src/static/share.js` `buildDiffRows` context 분기에 `/^\s*(\d+)→/` 누출 정규화(prefix 제거 + 실제 줄번호로 gutter 동기화).
- [x] **단위 검증**: 신규 `tests/verify_diff_lineno_leak.mjs` **30/30 PASS**(Node18 순수) — 실 누출 블록 정규화·실 줄번호(45/46/50) 복원·clean diff(@@ 헌크·1-based) 무변경(회귀 0)·app.js↔share.js 정합.
- [ ] **PB-0008 Windows-browser 시각 검증**(누출 diff 가 든 메시지가 깨끗하게 렌더되는지) — WSL worktree 라 미실행, **배포 후 사용자/실측 확인 권장**(frontend render-only, 선례 동일).
- [x] verify-completion --pre-commit PASS(원본 세션) → commit `d75152f` → push → **PR #467 머지(main 5942a25)** → cycle-finalize(worktree/브랜치 정리) → **web 이미지 재빌드·재기동(deploy_scope: included)**. 라이브 검증: `GET /healthz` git_commit=`5942a25`(live)·repo-web-1 healthy · 서빙 `index.html` `app.js?v=20260629e-diff-lineno-leak` · 서빙 `app.js` **byte-identical** to main(fix live). (원본 세션 session-limit 중단 → `/_template:resume` 로 landing+배포 완수.)
- Deferred(cross-ref): agent_core 프롬프트 강화(feature-0002, Major)는 별도 — 렌더러 봉인이 누출 비가시화하므로 우선순위 낮음.

### TASK-20260629T184726-metadata-bs-paging — 스키마 골격 가져오기 결과 페이지네이션 + 여백 압축 (Minor §12.3, frontend-only, metadata-bs-collapse 후속, 2026-06-29)
- 트리거: `/_template:entry` arg-given. 사용자 보고(테이블 설명 AI 자동완성 및 UI 버그 수정 작업 중): 관리 콘솔 > 메타데이터 > 테이블 설명 > "스키마 골격 가져오기" — ① 탐색된 테이블이 많을 경우 세로 스크롤이 과도하게 늘어남(페이징 필요) ② 사용되지 않는 여백 과다.
- 근본원인: 직전 `metadata-bs-collapse`(접힘 헤더+검색 필터+모두 펼치기/접기) + `metadata-table-desc-fix`(내부 max-height 스크롤 박스 제거, pane `overflow-y:auto` 에 위임)로 결과가 **테이블 수에 비례해 무한 세로 확장**. 접힌 한 줄 헤더라도 수백 개면 pane 스크롤이 과길어짐 — 페이징 레이어 부재가 근본.
- [x] **admin.js — 페이징을 "가시성 윈도우" 레이어로 추가**: 상수 `META_BS_PAGE_SIZE=30`, `bootstrap.page` 상태. `_metaBootstrapApplyFilter` 를 필터+페이징 결합으로 재작성(매칭 부분집합 위에서 현재 페이지 윈도우만 `display` 노출). `_metaBootstrapGoPage`(이전/다음+scrollIntoView)·`_metaBootstrapRenderPager`(라벨/disabled, 1페이지뿐이면 숨김) 신설. fetch·검색 변경 시 page=0 리셋, pager 이동 시 클램프.
- [x] **불변식 보존(핵심)**: 가시성은 순수 `display` 토글 — 모든 블록은 DOM 유지. 저장(`_metaBootstrapSave`)·AI 일괄(`_metaBootstrapAiFill`/`_metaBootstrapApplyDescriptions`)의 `querySelectorAll(".admin-meta-bs-table")` 전체 수집 무변경 → off-page/비매칭 블록 입력값도 저장·AI채움.
- [x] **styles.css — 여백 압축**: 컨트롤 영역(note `12px→8px 0 10px`·controls/status margin 축소), 결과 gap `4px→3px`, 헤더 padding `8px 12px→6px 10px`, 본문 `0 12px 10px→0 10px 8px`, 컬럼 행 `4px→3px`. 페이저 스타일(`.admin-meta-bs-pager/-page-btn/-page-label`) 신설.
- [x] **admin.html**: 결과↔저장액션 사이 페이저 바(`metadataBootstrapPager`+prev/label/next) 추가 + cache-buster 2건 bump(`styles.css?v=`·`admin.js?v=` → `20260629-metadata-bs-paging`).
- [x] **단위 검증**: `node --check admin.js` PASS · JS↔HTML id 정합(4 id)·CSS↔HTML 클래스 정합·cache-buster 양쪽 bump 확인. §18.8 적대 패널(SUBAGENT correctness) — 페이징이 DOM 전체 수집 불변식·필터 합성·클램프·toggle 충돌·stale 상태 5가설.
- [ ] **PB-0008 Windows-browser 시각 검증**(대규모 스키마 fetch→페이저 노출·이전/다음·검색 합성·≤30개 시 페이저 숨김·여백 축소·저장/AI일괄 전체 수집) — WSL worktree 라 미실행, **배포 후 사용자 확인 권장**(frontend render-only, 선례 동일).
- [ ] verify-completion --pre-commit PASS → commit → main merge → web 재빌드·재배포(deploy_scope: included, frontend-only → web 이미지만) → healthz.

### TASK-20260630T005923-share-joinable-confirm-persist — 공유 '링크 생성' 참여 허용 확인 모달 + '참여 허용' 체크박스 대화별 영속(회귀 수정) (Critical 인접 §12.3 인가/프라이버시 UX, frontend-only, feature-0009 cross-cut, 2026-06-30)
- 트리거: `/_template:entry` arg-given. 사용자 요청: (1) '대화 공유'에서 '링크 생성' 버튼을 누른 후 해당 대화 참여 허용 여부를 먼저 확인하는 구조 구성. (2) '공유' 화면에서 '이 링크로 대화 참여 허용' 체크박스를 조절한 후 다시 진입 시 상태가 회귀하는 버그 수정.
- 설계 결정(AskUserQuestion): Q1=**항상 확인 모달**(생성 클릭 시 참여 허용/미허용 명시 확정). Q2=**대화별 localStorage 영속**(cid 키).
- 위험: 기존 `test_share_joinable_owner_guard.py` 가 Critical §12.3 인가로 명시한 영역. 본 변경은 프론트 UX(확인 게이트+영속)만 — owner-only joinable + 백엔드 403 불변식 무변경. 격리: 신규 worktree(rebase 후 main 4359be5 기반).
- [x] **localStorage 영속 헬퍼**: `SHARE_JOINABLE_PREFS_LS_KEY="mad.shareJoinablePrefs.v1"` + `_loadShareJoinablePrefs`/`getShareJoinablePref(cid)`/`setShareJoinablePref(cid,joinable)`. cid→bool 맵, 미설정 대화는 기본 ON(`!== false`). muted/notify 패턴 미러.
- [x] **확인 모달 `confirmShareJoinable({initial,canAllow})`**: '참여 허용 확인' 모달. owner(canAllow=true)=[취소][참여 없이 생성][참여 허용하고 생성], 비소유자(canAllow=false)=[취소][생성](허용 버튼 부재). resolve({cancelled, joinable}). 취소/Escape/backdrop/× 모두 cancelled, settled 이중 resolve 가드, cleanup 에서 keydown 리스너 제거.
- [x] **openShareDialog '링크 생성' 게이트**: 클릭 시 `confirmShareJoinable` await → 취소면 발급 중단 → 최종 joinable 을 체크박스·영속값에 반영 → `_issueConversationShare`. 비소유자 최종 joinable 강제 false 보존.
- [x] **회귀 수정(요청2)**: openShareDialog·promptShareExpiry 체크박스 초기값을 `getShareJoinablePref(cid)` 에서 복원(하드코딩 `checked` 제거) + change 즉시 영속. createConversationShare 가 cid 전달.
- [x] **CSS/cache-buster**: `.share-confirm-panel/-desc/-actions` 추가. index.html app.js `20260629f-point-scroll-easeoutexpo`→`20260629g-share-joinable-confirm`, styles.css `20260629-metadata-bs-flexclip`→`20260629-share-joinable-confirm`.
- [x] **스코프 명문화(패널 NIT)**: 앵커 경로(createConversationShare)는 confirm 모달 의도적 미적용 — 주석으로 명시(요청1 = openShareDialog '링크 생성' 한정).
- [x] **테스트**: 기존 `test_share_joinable_owner_guard.py` 3 assertion 을 불변식 보존하며 갱신(intended/최종 joinable 분리·cid 파라미터·cid 전달) + 신규 `test_share_joinable_confirm_persist.py`(P1~3 영속·C1~4 확인 게이트, 7 케이스). agent 이미지 pytest: 공유 테스트 13/13 + feature-0003 전체 548 PASS(회귀 0). `node --check app.js` PASS.
- [x] **§18.8 적대 패널 2렌즈**(security/authz + ux/regression) — 각 5가설 전부 REFUTED. 보안 VERDICT SAFE(backend gate intact·triple-clamp·XSS 0), UX VERDICT SOUND(종료경로·회귀수정·일관성). BLOCKING 0.
- [x] **릴리즈노트**: `release-notes-data.js` 2026-06-29 블록에 2건(참여 허용 확인 improved · 체크박스 상태 유지 fixed) + summary 갱신.
- [ ] **PB-0008 Windows-browser 시각 검증**(링크 생성→확인 모달·취소 시 발급 중단·체크박스 토글 후 재진입 상태 유지) — WSL worktree 미실행, **배포 후 사용자 확인 권장**(frontend render-only, 선례 동일).
- [x] verify-completion --pre-commit PASS → commit `2167cd0` → **PR #470 머지(main 557c3c9, FF)** → cycle-finalize(worktree/브랜치 정리; worktree remove 는 sudo pytest pycache root소유로 1차 실패→sudo rm+prune) → **web 이미지만 재빌드·재기동(deploy_scope: included)**. 라이브: `GET /healthz` git_commit=`557c3c9`(live, `4359be5`→`557c3c9`)·repo-web-1 healthy · 서빙 `index.html` `app.js?v=20260629g-share-joinable-confirm`·`styles.css?v=20260629-share-joinable-confirm` · 서빙 `app.js` **byte-identical** to main(fix live)·styles.css `.share-confirm` 반영.

### TASK-20260630T100802-metadata-bs-inline-desc — 테이블 설명 모드 결과 행 평면화 + 설명 입력 인라인(중앙 여백 효용화) (Minor §12.3, frontend-only, metadata-bs-paging 후속, 2026-06-30)
- 트리거: `/_template:entry` arg-given(직전 페이지네이션 배포 후 사용자 후속 보고 + 스크린샷). 사용자 보고: 페이징·세로 여백은 해소됐으나 "테이블 설명 모드 각 행의 **중간(이름↔'○ 비어있음' 사이) 가로 여백이 너무 많이 차지** — 정리하거나 효용성있게 사용 가능한지".
- 결정: 가장 효용성 있는 해법 = 빈 중앙에 설명 입력란을 인라인 배치(여백을 입력란으로 전환 + 펼침 없이 바로 입력 → 테이블 설명 모드 클릭 절감). columns 모드는 테이블당 컬럼 다수라 접힘 구조 유지.
- [x] **admin.js — render tables 분기 평면화**: `_metaBootstrapRenderResult` 의 tables 모드를 `<button>` 접힘 헤더 → 비클릭 `<div class="admin-meta-bs-row">`(`.is-flat`)로 변경. 행 = 이름(ellipsis) + **인라인 설명 입력(`.admin-meta-bs-desc-inline`, flex:1, `data-kind='table'`)** + 상태 힌트. caret/toggle/본문 없음. columns 분기는 caret + `.is-collapsed` + 컬럼 본문 트리 그대로 유지.
- [x] **수집 불변식 보존**: 인라인 입력이 여전히 `.admin-meta-bs-desc[data-kind='table']` 로 블록 내 존재 → `_metaBootstrapSave`·`_metaBootstrapApplyDescriptions`·`_metaBootstrapUpdateHint` 셀렉터 무변경 매칭. 페이징(`.admin-meta-bs-table` display 토글)도 평면 블록에 동일 적용.
- [x] **expand-all 모드별 가시성**: tables 모드는 펼칠 게 없어 "모두 펼치기/접기" 숨김(columns 전용). 저장 안내문구도 모드별 분기.
- [x] **styles.css**: `.admin-meta-bs-row`(flex 비클릭 행) + `.is-flat .admin-meta-bs-table-name`(ellipsis·max-width 38%) + `.admin-meta-bs-desc-inline`(flex:1, min 120px). **admin.html**: cache-buster 2건 bump → `20260630-metadata-bs-inline-desc`.
- [x] **검증**: `node --check admin.js` PASS. 신규 `tests/verify_metadata_bs_inline_desc.mjs` 21/21(정적: tables 평면·인라인·caret 미생성·columns 접힘 유지·expand-all columns 전용 + jsdom 행위: save 셀렉터 인라인 입력 탐지·힌트). `tests/verify_metadata_bs_paging.mjs` 32/32 무회귀(cache-buster 단언을 literal→동반-bump 불변식으로 견고화). §18.8 적대 패널(SUBAGENT correctness) 6가설.
- [ ] **PB-0008 Windows-browser 시각 검증**(테이블 설명 모드 행에 인라인 입력 노출·중앙 여백 해소·바로 입력→저장·columns 모드 접힘 무회귀·서브탭 전환) — WSL worktree 라 미실행, **배포 후 사용자 확인 권장**.
- [ ] verify-completion --pre-commit PASS → commit → main merge → web 재빌드·재배포(deploy_scope: included, frontend-only → web 이미지만) → healthz.
### TASK-20260630T100000-doc-sync-rn-0630 — 06-29 머지분 릴리즈노트 정합(관계 다이어그램 신규 외 6항목) + cache-buster bump (doc_sync, 비-정책 doc, 2026-06-30)
- 트리거: `/_dqa:doc_sync`(전 타깃, 자동 기준일). 직전 릴리즈노트 sync(a644fcb @ 2026-06-29 13:36, "06-29 블록 3항목") 이후 main 병합된 06-29 user-facing 변경 — feature-0013 관계 다이어그램(PR#462/#469) + metadata-bs-collapse/flexclip/paging · share-mermaid-responsive · point-scroll · glossary-role-single-ui/fieldname-fix · new-conv-dedup · diff-lineno-leak — 이 릴리즈노트 미반영(drift) → `release-notes-data.js` 기존 '2026-06-29' 블록에 doc_sync 6항목 추가(landing 중 origin/main 의 공유 2항목(share-joinable) 합류분 보존 → 최종 11항목) + `generated` 2026-06-29→2026-06-30.
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. 내부용어(feature-id/테이블·함수명/마이그 번호/엔드포인트/cache-buster 내부 슬러그/role_key) 누출 0. 메타데이터·공유 다수 fix 는 사용자 체감 단위로 consolidate(over-listing 회피 — 메타데이터 3건→1항목, 공유 2건→1항목).
- [x] 검증: `node --check release-notes-data.js` PASS + vm 로드 generated=2026-06-30·06-29 블록 11항목(2 new·5 improved·4 fixed) + 항목 스키마(type/area/title/detail) 정합.
- [x] 배포 전파: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260629b-rn-0629`→`?v=20260630-rn-0630` bump(정적 자산은 `?v=` 가 유일 전파 메커니즘). verify-completion(operational, feature-0003) → commit → landing(PR/merge) → web 재배포(deploy_scope: included).

### TASK-20260630T103235-metadata-bs-inline-align — 테이블 설명 인라인 입력란 행간 정렬(고정 폭 칸) (Minor §12.3, frontend-only CSS, metadata-bs-inline-desc 후속, 2026-06-30)
- 트리거: `/_template:entry` arg-given(인라인 입력 배포 후 사용자 후속 보고). 사용자 보고: `<DB명>.<테이블명>` 길이가 제각각이라 이름 칸이 내용 너비를 먹어 **입력란 시작 x·너비가 행마다 들쭉날쭉** — 입력란 UI 정합 요청.
- [x] **styles.css(정렬)**: `.is-flat .admin-meta-bs-table-name` `flex: 0 1 auto; max-width:38%`→**`flex: 0 0 clamp(180px,32%,340px)`**(고정 폭 칸 — 평면 행은 모두 동일 폭 컨테이너라 32% 가 행마다 동일 px → 입력란 시작 정렬, 긴 이름 ellipsis+title). `.admin-meta-bs-desc-inline` `min-width:120px`→**`min-width:0`**(좁은 화면에서도 정렬 유지). `.is-flat .admin-meta-bs-hint` **`flex: 0 0 5.5rem; text-align:right`** 신설(입력란 우측 끝 정렬 + ○→● 입력 시 너비 불변).
- [x] **admin.html**: cache-buster 2건 bump → `20260630-metadata-bs-inline-align`(동반).
- [x] **검증**: 회귀 가드 `tests/verify_metadata_bs_inline_desc.mjs` 27/27(정렬 단언 [A6-align] 이름/힌트 고정 폭 + cache-buster 동반-bump 불변식 견고화 + 기존 평면행·수집·H4) · `verify_metadata_bs_paging.mjs` 32/32 무회귀. CSS-lens 적대 패널(6가설: 정렬·columns 회귀·좁은화면 overflow·초장문·힌트폭·기타).
- [ ] **PB-0008 Windows-browser 시각 검증**(여러 길이 테이블명에서 입력란 좌/우 끝이 행마다 정렬·긴 이름 ellipsis·columns 무회귀) — WSL worktree 미실행, **배포 후 사용자 확인 권장**.
- [ ] verify-completion --pre-commit PASS → commit → main merge → web 재빌드·재배포(deploy_scope: included, frontend-only → web 이미지만) → healthz.
### TASK-20260630T230501-doc-sync-rn-2305 — 06-30 머지분 릴리즈노트 정합(메타데이터 그래프 뷰 신규 외 9항목) + cache-buster bump (doc_sync, 비-정책 doc, 2026-06-30)
- 트리거: `/_dqa:doc_sync ultracode`(전 타깃, 무인). 직전 릴리즈노트 sync(9093763 @ 06-30 10:30, "06-29 블록 11항목") 이후 main 병합된 06-30 user-facing 변경 — feature-0016 메타데이터 지식그래프·그래프 뷰(PR#477/#480/#482/#484) + feature-0003 메타데이터 관리 화면 정리(list-detail/ds-single/inline-desc·align/prefill) + feature-0002 능동 해석 일반화 + 무중단 배포(feature-0014/0015/0016-zd/0017) — 이 릴리즈노트 미반영(drift) → `release-notes-data.js` 신규 '2026-06-30' 블록 10항목 prepend(06-29 블록 보존).
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. 내부용어(feature-id/테이블명/AGE/Cypher/Cytoscape/pgbouncer/Caddy/alembic/마이그번호/스크립트명/함수명) 누출 0. ULTRACODE 5-stream 적대 패널 MAJOR 흡수: 그래프 뷰 항목이 관계 엣지=0(게임 DB FK 미선언)인데 '테이블 연결 따라가기' 과대표현 → 가시 사실(스키마/DB 그룹핑·검색·노드 설명·컬럼)로 완화; 무중단 항목 '주요 기능 멈추지 않음'이 스트리밍 예외 초과 → '채팅 등 주요 작업 이어짐 + 일부 진행 중 작업 드물게 재시도'로 완화.
- [x] 검증: `node --check release-notes-data.js` PASS + vm 로드 generated=2026-06-30·06-30 블록 10항목(1 new·8 improved·1 fixed) + 항목 스키마(type/area/title/detail) 정합.
- [x] 배포 전파: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260630-rn-0630`→`?v=20260630b-rn-0630` bump(정적 자산은 `?v=` 가 유일 전파 메커니즘). verify-completion(operational, feature-0003) → 로컬 commit → landing/배포는 cron wrapper 소관(deploy_scope: included). META(STATUS·wiki·SECURITY·RELEASE_NOTES)는 별도 commit.

### TASK-20260702-graphview-webgl-polish — 그래프 뷰 WebGL 외곽선 선명화 + 테이블 단일클릭 컬럼 인라인 토글 (Minor §12.3, frontend-only, graph-webgl/graph-perf2 후속, /_template:resume 재개, 2026-07-02)
- 트리거: `/_template:resume "관리 콘솔 그래프 뷰 노드 렌더링 및 표시 개선"`. 원본 세션(cfbede21)이 WebGL 배포 후 육안 후속 2건(줌인 외곽선 뭉개짐·컬럼 단독 토글 부재)을 구현·라이브 검증했으나 계정 session-limit 로 (a) 접힘→재펼침 버그 미수정 (b) 리뷰/docs/랜딩 미완 중단 → 재개 완수. command-args 의 원 3건(노드 표식/클러스터 상세/명칭 잘림)은 별개 PR #514 로 이미 병합됨(재개 대상 아님).
- [x] **WebGL 외곽선 선명화**(AC-1): renderer `webglTexSize:4096`(atlas 셀 ~113→227px) + `pixelRatio:2` **WebGL 경로 한정**. GPU 합성이라 FPS 이득 유지. canvas-2D 폴백은 pixelRatio 키 생략(device DPR 보존).
- [x] **단일클릭 컬럼 인라인 토글**(AC-2): 신규 `_metaGraphToggleColumns` + tap 핸들러 300ms `_colTimer`(단일=컬럼, 더블=이웃확장 `_metaGraphExpand`). 펼침=그래프 HAS_COLUMN→없으면 information_schema introspect, 접힘=Column 제거.
- [x] **접힘→재펼침 컬럼 미출현 버그 수정**: collapse 분기에 `_metaGraph.introspected.delete(key)` — introspect 컬럼(HAS_COLUMN 부재)이 재펼침 시 Set 잔류로 재조회 skip 되던 문제 해소(원본 세션이 적발·선언했으나 미적용분).
- [x] **#519(graph-perf2) base drift 정합**: origin/main(042613eb) ff 병합 → stash pop 재적용. admin.html 캐시버스터 충돌·admin.js 자동병합 해소(실 충돌 마커 0). 토글 컬럼 seed 를 옛 3-wide grid→**부모 중심 세로 스택**(#519 `_META_COL_PITCH`)으로 재정합 — 최종 배치는 layoutstop `_metaGraphPlaceColumns` 결정론 배치가 보장. 역할분리 주석 정직화.
- [x] **캐시버스터**: `admin.html` `admin.js`/`styles.css` → `?v=20260702-graphview-webgl-polish`(lockstep).
- [x] **검증**: `node --check admin.js` PASS. §18.8 적대 패널 REV-20260702T000000-graphview-webgl-polish (VERDICT PASS, BLOCKING 0, 축1~6 안전, NIT1 canvas-2D 폴백 pixelRatio 회귀 즉시 수정). MODIFY/FUNCTION/REVIEW/REPORT 갱신.
- [ ] **PB-0008 Windows-browser 시각 검증**(단일클릭 컬럼 펼침/접힘·**접었다 재펼침 시 컬럼 재출현**·줌인 외곽선/텍스트 선명·더블클릭 이웃확장 무회귀) — WSL worktree + 그래프 canvas 인터랙션 자동화 PB-0008 회귀 이력이라 미실행, **배포 후 사용자 실화면 확인 권장**.
- [ ] verify-completion --pre-commit PASS → commit(Task-Cycle) → push → PR → main merge → cycle-finalize → web 재빌드·재배포(deploy_scope: included, frontend-only → web 이미지만) → /healthz.

### TASK-20260702-graph-panel-perms — 메타데이터 그래프 뷰 UX 3건 + 메타데이터 탭 권한 세분화(B안) (Major+Critical §12.3, feature-0016 그래프 UX + feature-0003 인가, /_template:entry arg-given, PLAN-APPROVED 2026-07-01, 2026-07-02)
<!-- PLAN-APPROVED by mckim on 2026-07-01 (AskUserQuestion: task4=B안 기능별 manage, 진행=1개 cycle 전체) -->
- 트리거: `/_template:entry` arg-given — 사용자 요청 4건(관리 콘솔 > 메타데이터 > 그래프 뷰 3 + 메타데이터 탭 권한 세분화). 초고병렬 feature-0016 영역이라 전용 worktree(ai/claude/feature-0016-graph-panel-perms) + 착수 후 origin/main 2커밋(#521/#522) 전진 감지 → rebase(stash→ff→pop, admin.js/admin.html 자동병합·충돌 마커 0).
- [x] **Task1 상세 패널 드래그 리사이즈**(Minor): `admin.html` 캔버스↔패널 사이 `#metadataGraphResizer`(role=separator, tabindex) + `styles.css` 3-col grid(`minmax(0,1fr) 8px var(--meta-graph-detail-w,340px)`)·리사이저 grip·hover/드래그 강조·≤900px 숨김 + `admin.js` `_metaGraphInitResizer()`(pointer 드래그로 CSS var 갱신·clamp[패널 240/캔버스 360]·localStorage 영속·←/→ 키보드·놓을 때 cy.resize+fit).
- [x] **Task2 확장 테이블 접기 버튼**(Major): `admin.js` `_metaGraphSyncCollapseButtons()`(스키마 라벨 오버레이 레이어에 컬럼 자식 보유 Table 박스 우측하단 HTML 버튼 얹음, `renderedBoundingBox` 좌표, `_lblSync` rAF 연동, 줌아웃<26px 생략, orphan 정리) + `_metaGraphCollapse(key)`(컬럼 자식+연결엣지 제거→박스가 dot 노드로 환원, `introspected` Set 삭제로 재확장 재조회) + `styles.css` `.admin-meta-graph-collapse-btn`(pointer-events:auto, z-index:4).
- [x] **Task3 첫 컬럼명 미표시 버그 수정**(Minor): `admin.js` Cytoscape `node:parent[label='Table']` 스타일 `text-margin-y: 2`→`-13` + text-background halo(캔버스색 chip) — 박스 안쪽 최상단 타이틀이 최상단 컬럼 dot·라벨과 겹쳐 첫 컬럼명이 가려지던 원인 제거(타이틀을 박스 위로 띄움, 박스 크기·fcose 간격 불변).
- [x] **Task4 메타데이터 탭 권한 세분화(B안)**(Critical, 인가): 단일 묶음 `kb.ingest.manual` → 기능별 5권한 분리 `metadata.{glossary,enum,table,column}.manage` + `metadata.graph.read`.
  - `app.py`: PERMISSION_DEFINITIONS 5개 추가(group=kb) + `kb.ingest.manual` 라벨 "메타데이터 관리(전체 묶음)" 재정의(catalog 유지) + `_METADATA_MANUAL_IMPLIES` + `_apply_permission_overrides` 함의(effective map 에서 묶음→5권한 자동 True, 개별 DENY 존중 — **비파괴·가역 하위호환**, DB 마이그 불필요, 역할 grant+계정 override 전 principal 커버) + admin catchup 5개 추가 + `_METADATA_SUBTAB_PERM_SERVER` 갱신.
  - `routers/admin_metadata.py`: 28 핸들러 require_permission 전환(glossary→glossary.manage / enum→enum.manage / table·bootstrap→table.manage / column→column.manage / graph·analyze→graph.read).
  - `admin.js`: PERMISSION_DEPENDENCIES 5개(→console.access) + `_METADATA_SUBTAB_PERM`·`_GLOSSARY_VIEW_PERM`·`_metaSubtabVisible`·canSeeTab.metadata·부트스트랩 게이트(table.manage) 갱신.
- [x] **캐시버스터**: `admin.html` `admin.js`/`styles.css` `?v=20260702-graphview-webgl-polish`→`?v=20260702-graph-panel-perms`(lockstep).
- [x] **단위 검증**: `node --check admin.js` PASS · `py_compile` app.py/admin_metadata.py PASS · 신규 `tests/test_metadata_perm_split.py` 9/9 PASS(카탈로그·admin seed·함의·DENY 우선·granular 격리·umbrella 유지·FE/BE 맵) · `test_metadata_ai_autocomplete.py` fixture 세부권한 갱신 후 PASS · feature-0003 전체 suite green(단, `test_route_parity_p5b` 192→193 route drift 는 **origin/main 344a5a80 기존 결함** — #520/#522 신규 route 의 golden 미갱신, 본 변경은 route 무추가로 무관).
- [x] **적대 검증 패널**(§18.8): authz(인가 상승·접근 회귀·enforcement 누락·FE/BE 불일치) + 그래프 프론트(리사이즈 경계·접기버튼 이벤트/좌표·컬럼 수정 겹침·#522 병합 정합) 2 렌즈.
- [ ] **PB-0008 Windows-browser 시각 검증**: 그래프 canvas 인터랙션(드래그 리사이즈·접기 버튼 클릭·첫 컬럼명 표시)은 자동화 PB-0008 회귀 이력 → **배포 후 사용자 실화면 확인 권장**. 권한 세분화는 백엔드 로직(단위테스트 커버)+프론트 게이트(비파괴 함의).
- [ ] verify-completion --pre-commit PASS → commit → push → PR → main merge → cycle-finalize → web 재빌드·재배포(deploy_scope: included, frontend+backend → web 이미지) → /healthz.

### TASK-20260701T230501-doc-sync-rn-0701 — 07-01 머지분 릴리즈노트 정합(그래프 뷰 진화·권한 세분화·convswitch 외) + cache-buster bump (doc_sync, 비-정책 콘텐츠 doc, 2026-07-01)
- 트리거: `/_dqa:doc_sync ultracode`(전 타깃, 무인 cron). 직전 릴리즈노트 sync(fc35932f @ 06-30 23:51, "06-30 블록 10항목") 이후 main 병합된 07-01 user-facing 변경 — feature-0016 그래프 뷰 진화(WebGL 렌더러·암묵 관계 추론·AI 능동 분석 진행/게이팅·ERD 컬럼 ordinal·다수 렌더 수정) + 메타데이터 탭 권한 5분할(feature-0003) + 좌측 대화 전환 방어(convswitch) — 릴리즈노트 미반영(drift) → `release-notes-data.js` 신규 '2026-07-01' 블록 7항목 prepend(06-30 블록 10항목 보존). feature-0012 라우터 모듈화는 behavior-neutral 내부 리팩터라 user-facing 릴리즈노트 제외(META RELEASE_NOTES 만 반영).
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. 내부용어(feature-id/테이블명/WebGL/Cytoscape/AGE/Cypher/alembic 번호/함수명/권한키 `metadata.*.manage`) 누출 0. 사용자향 평이화: 추정 관계는 '점선·추정→맞으면 실선/틀리면 사라짐'으로 정직 서술(과대표현 회피), 권한 세분화는 탭 이름(용어사전·코드값·표·컬럼·관계도)로만 서술(내부 키 비노출)·기존 권한 무손실 명시.
- [x] 검증: `node --check release-notes-data.js` PASS + vm 로드 generated=2026-07-01·07-01 블록 7항목(2 improved/admin·3 new/admin·1 fixed/admin·1 fixed/work) + 스키마(type/area/title/detail) 정합. 06-30 블록 10항목 보존.
- [x] 배포 전파: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260630b-rn-0630`→`?v=20260701-rn-0701` bump(정적 자산은 `?v=` 가 유일 전파 메커니즘). verify-completion(operational, feature-0003) → 로컬 commit. landing(push/PR/merge)·배포는 cron wrapper 소관(deploy_scope: included). META(STATUS·wiki·SECURITY·ARCHITECTURE·RELEASE_NOTES)는 별도 commit.
- [ ] PB-0008 Windows-browser 시각검증: 릴리즈노트는 콘텐츠 데이터/캐시버스터 변경만(렌더 로직 불변) — 본 무인 cycle 은 인터랙티브 Windows-browser 브리지 미가동, 배포는 wrapper 소관(post-merge). 원천 UI 변경(그래프 뷰·convswitch)은 각 feature cycle 이 07-01 PB-0008 PASS 기록(graphview-render·graphview-webgl-labels·convswitch-opacity-guard). 사유는 TEST.md §3 Windows-browser Run 에 기록(CHECK#13).

### TASK-20260702T021700-attach-count-scope — "+" 메뉴 "첨부파일 목록" 개수 배지 대화 전환 후 stale 수정 (Minor §12.3, frontend-only, /_template:entry arg-given, 2026-07-02)
- 트리거: 사용자 보고 — assistant 에 첨부 파일을 전달한 뒤 다른 대화창으로 전환해도 "+" 메뉴 "첨부파일 목록" 우측 개수 배지가 이전 대화의 첨부 개수를 그대로 표시(오른쪽 첨부 패널은 "첨부 파일이 없습니다" 로 정상 — 배지만 stale). 근본원인: 배지 setter 는 `_renderAttachmentPills()` 유일인데 switchConversation 외 컨텍스트 진입/전환/삭제-랜딩 경로가 재렌더 훅 누락.
- [x] **근본원인 특정**: `#composerAttachCountBadge` setter = `_renderAttachmentPills`(app.js:7344/:7349) 유일 확인(grep). `_loadConversationAttachments` 호출 site = switchConversation(:5883) 단 1곳 → 비-switch 진입 경로 stale.
- [x] **pending 진입 2경로 수정**: `beginPendingConversation`(:5907, "새 대화")·`_switchToPendingConversationContext`(:5939, pending 항목 클릭) 의 `renderComposer()` 뒤 `_renderAttachmentPills()` 추가.
- [x] **삭제/보관/나가기 랜딩 갭 수정**(적대검증 MAJOR 적발): `loadHistory` 두 exit(빈 early-return·정상 종료)에 `_renderAttachmentPills()` 추가 → `refreshWorkspace`→`loadConversations`→`loadHistory` 로 랜딩하는 `deleteConversation`/`bulkDeleteConversations`/`leaveConversation` 전량 커버(loadHistory = switchConversation·refreshWorkspace 공통 sink, switchConversation 은 직후 `_loadConversationAttachments` 재확정).
- [x] **캐시버스터**: `index.html` `app.js?v=20260701-convswitch-opacity-guard`→`?v=20260702-attach-count-scope`(정적 자산 유일 전파 메커니즘).
- [x] **정적 검증**: `node --check app.js` PASS. §18.8 적대검증 REV-20260702T021700-attach-count-scope — 초기 FAIL(MAJOR 1: delete/leave 갭 + MINOR 1: logout 비가시) → loadHistory 수정 반영 후 정합(BLOCKING 0), logout 은 재로그인 자동정정이라 무수정 확인. MODIFY/REVIEW/TEST/REPORT 갱신.
- [ ] **PB-0008 Windows-browser 시각 검증**: client-JS baked(재배포 전 라이브 미서빙) + relay 라이브검증은 사용자 실 Chrome 점유 필요 → **배포 후 사용자 실화면 확인**(① 첨부 후 새 대화 클릭 시 배지 비움 ② 다른 대화 전환 시 그 대화 개수/비움 ③ 첨부 대화 보관·나가기 후 배지 잔류 안 함). 사유는 TEST.md §3 Windows-browser Run 기록(CHECK#13).
- [ ] verify-completion --pre-commit PASS → commit → push → PR → main merge → cycle-finalize → web 재빌드·재배포(deploy_scope: included, frontend-only → web 이미지) → /healthz.

### TASK-20260702T230501-doc-sync-rn-0702 — 07-02 머지분 릴리즈노트 정합(그래프 뷰 상호작용/가시성 진화·AI 운영 관제 패널 외) + cache-buster bump (doc_sync, 비-정책 콘텐츠 doc, 2026-07-02)
- 트리거: `/_dqa:doc_sync ultracode`(전 타깃, 무인 cron, 적대 워크플로 wf_61d9648b). 직전 릴리즈노트 sync(97004c49 @ 07-01 23:44, "07-01 블록 7항목") 이후 main 병합된 07-02 user-facing 변경 — feature-0016 그래프 뷰 후속 진화(G6 v5 렌더러 교체·우클릭 상세 상호작용·초기 진입 가시성·검색 badge·프리즈 해소·추정관계 자기교정 근본수정·더블클릭 카메라 팬) + feature-0003 AI 운영 관제 패널·감사 UX·권한 계층화·conv-link/attach fix — 릴리즈노트 미반영(drift) → `release-notes-data.js` 신규 '2026-07-02' 블록 8항목 prepend(07-01 블록 7항목 보존). feature-0012/0017 내부 리팩터·배포 게이트는 behavior-neutral 이라 user-facing 릴리즈노트 제외(META RELEASE_NOTES 만 반영).
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. 내부용어(feature-id/테이블명/G6/Cytoscape/WebGL/config `__all__`/NameError/alembic/함수명/권한키 `console.aiops.read`·`metadata.*`/엔드포인트 `/api/admin/ai-ops`/모델명 claude-haiku/ADR 번호) 누출 0. 사용자향 평이화: 추정관계 자기교정은 '자동으로 다듬는 기능이 제대로 동작하도록 수정'(정직 결함 공개, 재발표 아님), AI 운영 현황은 '현재 상태 요약·주요 지표·최근 활동' 수준.
- [x] 검증: `node --check release-notes-data.js` PASS + jsdom DOM 테스트 33 PASS(관리 55→62·작업 84→85·그룹 19→20 카운트 동적 recompute·XSS 제목/summary esc·07-02 그룹 head 펼침/07-01 접힘) / 1 FAIL 은 pre-existing admin pane `overflow-y:auto` CSS 규칙(data-only 변경 무관·baseline 동일). 07-01 블록 7항목 보존.
- [x] 배포 전파: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260701-rn-0701`→`?v=20260702-rn-0702` bump(정적 자산 `?v=` 가 유일 전파 메커니즘). verify-completion(operational, feature-0003) → 로컬 commit. landing(push/PR/merge)·배포는 cron wrapper 소관(deploy_scope: included). META(STATUS·wiki·SECURITY·ARCHITECTURE·RELEASE_NOTES)는 별도 commit.
- [ ] PB-0008 Windows-browser 시각검증: 릴리즈노트는 콘텐츠 데이터/캐시버스터 변경만(렌더 로직 불변) — 본 무인 cycle 은 인터랙티브 Windows-browser 브리지 미가동, 배포는 wrapper 소관(post-merge). 원천 UI 변경(그래프 뷰·AI 운영 패널)은 각 feature cycle 이 07-02 PB-0008 기록(graph-ctxmenu·initview·search-badge PASS; G6 교체·rel-selfheal·카메라팬은 배포 후 잔여). 사유는 TEST.md §3 Windows-browser Run 기록(CHECK#13).

### TASK-20260706T013532-reasoning-effort — 대화 화면 사용자 지정 추론 강도(낮음/일반/높음/매우 높음) 선택기 (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002·shared, /_template:resume 재개, 2026-07-06)
- 재개 맥락: 세션 `insight-worker gemma fallback 처리 구성`(PR #592 완료·머지) 말미에 제기됐다가 아키텍처 조사 착수 직후 세션 한도로 중단된 요청을 `/_template:resume` 로 재개. 결정 확정(2026-07-04): 매핑="끄기 없이 4단계"·저장="대화별 영구 저장"·UI="composer '+' 액션 메뉴".
- [x] 백엔드 매핑: `shared/model_catalog.py` — 낮음2000·높음10000·매우높음16000 override(`_REASONING_BUDGETS`), **일반=override 없음**(모델 config 기본 유지 — B1 적대검증 회귀 방지)·`normalize_reasoning_level`·`thinking_budget_for_level`('normal'→None)·`model_supports_thinking`(claude-* 만) + `__all__`. override 값 Anthropic 제약(1024≤budget<agent max_tokens 20000) 만족.
- [x] 백엔드 주입: `agent_core.py` `_call_llm` 이 thinking 지원 모델일 때만 요청 단위 `extra_body={"thinking":{...}}` 주입. `run_agent`/`_run_agent_core` 에 `reasoning_level` 배선. 보조 호출(summary/topic/validate)은 무변경(메인 agent 경로만).
- [x] 저장·hydration: `/api/ask` 파싱(normalize)+conv_id 확정 후 KV `reasoning_level` 저장(best-effort)+run_kwargs 캡처. `/api/history` KV→payload hydration. worker 경로(app.py payload + ask.py `_payload_to_kwargs`) 패리티.
- [x] 프론트: composer '+' 메뉴에 "추론 강도" 항목 + secondary 팝업(모델 선택자 미러). `state.reasoningLevel`·localStorage 미러·`askBody.reasoning_level`·대화 전환 hydration·thinking 미지원 모델 시 비활성. `styles.css` `.is-disabled`. cache-buster `?v=20260706-reasoning-effort`(app.js·styles.css).
- [x] 검증: `py_compile` 5파일 + `node --check app.js` PASS. 신규 `test_reasoning_effort.py` 12 PASS(B1 no-override 가드 포함). 전체 스위트 회귀 0(worktree 코드 대조 확인). §18.8 적대 패널 REV-20260706T013532-reasoning-effort — BLOCKING 2(B1 매핑 회귀·B2 override 미검증) 적발 → B1 수정(일반=no-override)·B2 라이브 게이트웨이 프로브로 override 실증·N1 hydration 가드 수정 후 재확정.
- [x] PB-0008 Windows-browser 시각검증 **POST-DEPLOY PASS** (2026-07-06, 배포 adad0a5e, 실 Windows Chrome relay @172.26.144.1:9223): '+' 메뉴 "추론 강도: 일반" 렌더 → 클릭 4단계 팝업(낮음/일반/높음/매우 높음, values low/normal/high/max, claude 모델 활성) → 높음 선택 시 라벨 "추론 강도: 높음"·✓·팝업 닫힘·localStorage=high → 새로고침 후 "높음" 복원 → 레이아웃 무붕괴·pageerror 0. 증적 pb0008_reasoning.png. (TEST.md §3 POST-DEPLOY Run)
- [x] verify-completion PASS → commit(21d842d4) → push → PR #594 → main merge(adad0a5e) → cycle-finalize → **web 무중단 롤링 재배포 + ask/insight-worker 재빌드**(deploy_scope: included, frontend+backend) → /healthz(git_commit=adad0a5e·mysql/pg ok) + B2 게이트웨이 override 라이브 smoke PASS(budget 1024 vs 16000 → reasoning 2073자 vs 6914자).

### TASK-20260706T094937-runtime-settings — 관리 콘솔 `시스템 > 설정` 운영 값(실행 타임아웃·모델별 thinking budget) 조정·저장·사용 (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002 agent-core·shared, /_template:entry arg-given, 2026-07-06)
- 요청: assistant 작동 참조 값을 `관리 콘솔 > 시스템 > 설정` 에 추가해 조정·저장·사용. ① TIME_OUT(쿼리 실행 외 서비스 전체 timeout) — 현재 구성된 값만, 억지 추가 금지 ② 실행 LLM 모델별 thinking budget_tokens(모델 추가 시 자연 확장) ③ 각 항목 우측 패널은 차후 확장용 전용 UI, 레거시 형태 정합. 반영 방식 결정=**하이브리드**(안전 live·저수준 restart, AskUserQuestion 확정).
- [x] shared/runtime_settings.py 신규 — 레지스트리(현행 `*_TIMEOUT*` 22종 + 카탈로그 순회 모델 예산 자동생성) + resolver(live TTL 캐시 / restart frozen 스냅샷) + `/shared` 스냅샷 원자적 I/O + 스펙 [min,max] 검증. shared.config 미import(순환 없음), kill-switch·fail-open.
- [x] shared/config.py — restart-mode 22 상수 `_startup_int()` 스냅샷 적용(방어적 import, override 없으면 env 기본값 **byte-동치**; CONN_PROBE `max()` 불변식 보존). 서브프로세스 테스트로 import-시 restart-apply 실증.
- [x] live-mode getter 배선 — llm.py AGENT_TIMEOUT_SEC(LLM 요청 경로 헬퍼 2곳 + 호출부 5곳 인자 생략) + mcp_client.py MCP_TIMEOUT_SEC. 무override 시 동치.
- [x] agent_core.py `_call_llm` — 명시 추론강도 미지정 시 모델별 budget override 주입(설정된 모델만; 미설정=미주입→모델 config 기본 thinking 유지, **B1 무회귀**) + `budget < max_tokens` 안전 clamp(기존 reasoning-effort 경로 no-op).
- [x] app.py — WebRuntimeSettings in-code DDL(MySQL KV) + load/save/delete/reconcile helper + `system.runtime.read/write` 권한 2건(settings 그룹) + admin seed catchup + 기동 시 DB→`/shared` 스냅샷 reconcile.
- [x] routers/admin_settings.py 신규 — GET registry / PUT value / DELETE reset (RBAC read+write 조회 종속, 동일-tx audit, 스펙 검증) + app.py include_router 등록.
- [x] 프론트: admin.html 설정 pane **2행+2패널**(전용 UI — 실행 타임아웃=카테고리 그룹+즉시/재배포 배지, 모델 예산=카탈로그 자동확장 목록), admin.js **2 mounter**(direct-save + 초기화 + `apiFetch`/`showToast`/`can` 레거시 패턴). cache-buster admin.js/admin.html `?v=`.
- [x] 검증(pre-commit): 신규 `test_runtime_settings.py` 22 PASS + `test_runtime_settings_api.py`(RBAC/검증) 12 PASS + config 서브프로세스 restart-apply PASS. `node --check admin.js` PASS. 전체 스위트 회귀 0.
- [ ] §18.8 적대 패널(backend/security/qa 렌즈) → REVIEW.md REV 기록.
- [ ] PB-0008 Windows-browser 시각검증: 정적 자산 baked → merge+재배포 선행. **POST-DEPLOY** 수행(설정 pane 2항목 렌더·타임아웃 저장/초기화·모델 예산 저장·즉시/재배포 배지·권한 게이트·pageerror 0). 사유는 TEST.md §3 Windows-browser Run 기록(CHECK#13).
- [ ] verify-completion --pre-commit PASS → commit → push → PR → main merge → cycle-finalize → web 재빌드·재배포(deploy_scope: included, frontend+backend — config/runtime_settings 는 web·worker 공통) → /healthz.

### TASK-20260707T110000-runtime-settings-auditfix — 런타임 설정 audit action 등록 (PB-0008 라이브 적발 hotfix, Minor §12.3, feature-0003 backend-only)
- 발견: feature-0018 배포 후 PB-0008 실 Windows 브라우저 write-path 검증에서 "실행 타임아웃" 저장 시 toast "저장 실패: … unknown audit action". 근본: `build_audit_change_json`(ActionCode allowlist)이 `system.runtime.update`/`system.runtime.reset` 미등록 → autocommit=False write 경로가 audit 단계에서 fail-closed(rollback→500). autocommit 원자화(security#1 수정)가 미감사 변경을 정확히 차단(status "기본값 사용 중" 유지 — DB 무변경)했으나 기능 자체가 막힘.
- [x] `app.py build_audit_change_json`: `system.runtime.update`(setting_key+value)·`system.runtime.reset`(setting_key) 2 action 등록(masked_fields 없음 — 운영 튜닝 파라미터 비민감). raise 前 삽입.
- [x] 회귀 가드: `test_runtime_settings_api.py` +2(build_audit_change_json 2 action 반환 shape). 유닛 갭(TestClient PUT 이 conn=None 로 audit 도달 前 500) 보완. 14 PASS.
- [ ] §18.8 security 렌즈 적대 리뷰 → REVIEW REV.
- [ ] verify-completion → commit → PR → merge → cycle-finalize → web 재빌드·재배포(backend-only, admin 자산 무변경) → PB-0008 write-path 재검증(저장/초기화 toast·has_override·audit row).

### TASK-20260707T111500-runtime-settings-postverify — feature-0018 + audit hotfix POST-DEPLOY PB-0008 기록 (doc-only, 2026-07-07)
- [x] feature-0018(PR #602→a7dcc436) + audit hotfix(PR #604→8d0a4723) 배포 완료 — web-a/b 무중단 롤링 soak ×2, /healthz 8d0a4723 mysql/pg ok, WebRuntimeSettings 테이블·admin 권한·/shared 스냅샷 초기화, 워커 a7dcc436(내 워커 코드 포함, audit 핫픽스는 web-only).
- [x] PB-0008 실 Windows 브라우저(Chrome/149 relay) POST-DEPLOY **PASS** — 설정 pane 3항목·타임아웃 22입력/6카테고리/22배지·env-fallback 300/600/180 실증·모델패널 2행 input 비움·write-path e2e(저장/초기화 toast·DB override roundtrip·audit)·pageerror 0. 증적 png. TEST.md §3 POST-DEPLOY Run 기록.
- [x] doc-only 기록 cycle (TEST/TASK/MODIFY/REVIEW) — 코드·자산 무변경.

### TASK-20260707T110534-doc-sync-rn-0707 — 07-02→07-07 머지분 릴리즈노트 정합(그래프 뷰 07-03~07 진화·추론 강도·데이터소스 지표·공유 참여/범위·런타임 설정·안정성) + cache-buster bump (doc_sync, 비-정책 콘텐츠 doc, 2026-07-07)
- 트리거: `/_dqa:doc_sync`(수동·attended). 직전 landed 릴리즈노트 sync(5b1481bb @ 07-02 23:05, "07-02 블록 8항목") 이후 main 병합된 07-03~07-07 user-facing 변경이 릴리즈노트 미반영(drift — 07-03·07-06 두 doc_sync 가 미landed) → `release-notes-data.js` 에 신규 '2026-07-03'(8항목)·'2026-07-04'(12항목)·'2026-07-06'(4항목)·'2026-07-07'(5항목) 블록 prepend(07-02 블록 이하 보존). `generated` 2026-07-02→2026-07-07.
- [x] 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경. 내부용어(feature-id/테이블명/G6/AGE/alembic/함수명/권한키/엔드포인트/모델명/ADR 번호/step_gap_ms/conn_health/xschema/WebRuntimeSettings) 누출 0. 사용자향 평이화. 역할 8종 중 매핑 포함(07-03 블록).
- [x] aiops-ttft(지연 KPI 재정의)는 관리자 지표라 07-03 블록 사용자 문구에서 제외(기술 RELEASE_NOTES.md·STATUS 에만). insight/edge-fallback 순수 백엔드는 '속도·안정성 개선' common 항목으로 번들. share-visibility-window·reasoning-effort·runtime-settings·category-refine 는 각 원천 cycle 이 PB-0008 기록 — 본 cycle 은 콘텐츠 데이터만.
- [x] 검증: `node --check release-notes-data.js` PASS. jsdom DOM 테스트(`verify_release_notes.mjs`)는 이 실행 env 미설치(컨테이너 전용) — 문법+스키마(type/area/title/detail)+블록 순서(07-07>06>04>03>02) + 07-02 이하 보존으로 갈음.
- [x] 배포 전파: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260702-rn-0702`→`?v=20260707-rn-0707` bump. verify-completion(operational, feature-0003) → 로컬 commit. landing(push/PR/merge)·배포는 본 attended run 이 사용자 정책(2026-06-25) 하에 자동 수행. META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260707T110534-META-0020-doc-sync-0707).
- [ ] PB-0008 Windows-browser 시각검증: 릴리즈노트는 콘텐츠 데이터/캐시버스터 변경만(렌더 로직 불변) — 본 doc_sync cycle 은 새로 시각검증할 렌더 델타 없음. 원천 UI 변경(그래프 뷰·추론 강도·런타임 설정·공유 범위)은 각 feature cycle 이 07-03~07-07 PB-0008 기록. 사유는 TEST.md §3 Windows-browser Run 기록(CHECK#13).
### TASK-20260707T120000-runtime-settings-ux — 런타임 설정 pane UI 재설계 (세련도 개선, web/UI CSS+JS-only, Major §12.3, feature-0003)
- 트리거(사용자): "UI가 세련되지 못함 — 내부 디자인 리뷰 진행하며 사람이 만족할 UI로 재구성." 현재 `.admin-quota-editor` 재사용이 부적합(입력창 라벨과 미정렬·우상단 부유, 설명 잘림, 행마다 저장/초기화 버튼 난립, 세로 반복 과다).
- [x] 디자인 시스템 매핑(subagent): 토큰(`:root`), 정돈된 패턴(admin-kv grid dl·admin-usage-table·admin-badge·admin-detail-section-title·admin-field focus-ring), commit-bar pending 6 touch point, 참조 pane(계정 권한 그리드) 라이브 캡처.
- [x] CSS 신규 `.rs-*`: rs-panel/group/group-title/list + **rs-row(2×2 grid: 라벨+배지 / 설명 / 입력+단위 / 상태·기본값)** + rs-input(canonical focus-ring·mono·우정렬)·rs-unit·rs-status(override/pending/invalid)·rs-reset·rs-readonly-note. --border-subtle 구분선·--primary-soft dirty·8px 그리드·반응형(≤560px).
- [x] JS 재작성: `buildRuntimeSettingRow`(행별 버튼 제거)·`setRuntimeSettingPending`(pending 예약)·`rerenderRuntimeSettingsPanels`·render* 를 rs-* 마크업으로. 설명 ellipsis+title(잘림 해소). 범위 밖 인라인 경고. 모델 no-override input 비움 유지.
- [x] **commit-bar 통합**(계정·프롬프트 정합): `adminState.pending.runtimeSettings` + pendingChangeCount + refreshPendingUI(detail "설정 N" + 좌측 nav row `.has-pending`) + applyAllPending(PUT/RESET DELETE 루프 + 재렌더) + cancelAllPending(clear + 재렌더). 편집→pending→"모두 적용" 배치 저장.
- [x] cache-buster admin.js/styles.css `?v=20260707-runtime-settings-ux`. node --check PASS, 잔여 dead-ref 0.
- [ ] §18.8 적대 디자인/UX 렌즈 리뷰 → REVIEW REV.
- [ ] verify-completion → commit → PR → merge → web 재배포 → **PB-0008 재설계 UI 시각검증(before/after)**.

### TASK-20260707T121500-runtime-settings-ux-postverify — 런타임 설정 UI 재설계 POST-DEPLOY PB-0008 기록 (doc-only, 2026-07-07)
- [x] UX 재설계(PR #607→da3f57db) 배포 후 실 Windows 브라우저 PB-0008 **PASS**: 정렬 grid 렌더(rs-row 22·6그룹·배지·구 quota-editor 0)·설명 잘림 해소·commit-bar 편집→pending→모두적용(DB override)→기본값복원(DB clean) e2e·모델 no-override input 비움·pageerror 0. before/after 증적.
- [x] doc-only 기록(TEST/TASK/MODIFY/REVIEW) — 코드·자산 무변경.

### TASK-20260707T130000-reasoning-budgets — 설정 > 모델별 추론 예산에 '추론 강도별 예산' 추가 + UI 교훈 기록 (Major §12.3 — feature-0003 web/UI + cross-unit feature-0002·shared, 2026-07-07)
- 트리거(사용자): "① 가시성 개선 교훈 기록 ② `설정 > 모델별 추론 예산` 에서 각 추론 강도별 예산 토큰값도 설정 가능하게."
- [x] 교훈: `docs/LEARNINGS.md` LRN-20260707-0001(pattern, verified) — quota-editor 재사용 안티패턴 → 정렬 grid+commit-bar, PB-0008 시각검증이 유닛/코드리뷰 놓친 결함(audit write-path·시각완성도) 포착.
- [x] shared/runtime_settings.py: `reasoning_budget:{low,high,max}` 스펙(카탈로그 REASONING_LEVELS 순회, normal 제외=B1) + `reasoning_budget_override` resolver + serialize `reasoning_budgets` 버킷 + `__all__`. 기본값=`thinking_budget_for_level`(2000/10000/16000), min1024 max16000, live.
- [x] agent_core.py `_call_llm`: precedence — 명시 레벨(low/high/max)이면 그 레벨 admin override(없으면 기본), '일반'이면 모델 override(B1: 레벨 예산 미적용). budget<max_tokens clamp 유지.
- [x] admin.js: `renderModelThinkingBudgets` 가 2 섹션(모델별 + 추론 강도별) 렌더(rs-* 정렬 행, 추론은 pre-fill). nav-dirty 분류에 RS_REASONING_PREFIX. cache-buster admin.js `?v=20260707-reasoning-budgets`.
- [x] 테스트: test_runtime_settings.py +4(스펙/override/clamp/validate) · test_reasoning_effort.py +3(_call_llm precedence: override>기본, no-override 기본, normal 무시+모델 override). 전체 로컬 회귀 0.
- [ ] §18.8 적대 리뷰(backend/UX) → REVIEW REV.
- [ ] verify-completion → commit → PR → merge → web 재배포 + **ask/insight-worker 재빌드**(_call_llm=워커 경로) → PB-0008 시각검증(추론 강도별 예산 섹션 렌더·편집/적용).

### TASK-20260707T131500-reasoning-budgets-postverify — 추론 강도별 예산 POST-DEPLOY PB-0008 기록 (doc-only, 2026-07-07)
- [x] 추론 강도별 예산(PR #609→767ca387) 배포(web + ask/insight-worker 재빌드) 후 PB-0008 **PASS**: 2 섹션 렌더(추론 강도별=낮음/높음/매우 높음 pre-fill·'일반' 없음 B1)·reasoning-key write-path e2e(적용 DB override→복원)·사용자 사전설정(MCP_TIMEOUT_SEC=60) 보존·pageerror 0.
- [x] doc-only 기록(TEST/TASK/MODIFY/REVIEW) — 코드·자산 무변경.
### TASK-20260707-kb-candidate-adoption — 지식베이스 메타데이터 채택 인박스: 대화 자율수집(용어사전+ENUM) + 통합 채택 UI (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002·shared, worktree ai/claude/feature-0018-kb-candidate-adoption, 2026-07-07)
- 요청: 서비스 assistant 대화가 진행되며 「관리 콘솔 > 지식베이스 > 메타데이터」의 '용어사전'·'ENUM 코드사전'에 추가될 후보를 수집하고, 관리 콘솔에서 사용자가 각 후보를 **채택**하도록 UI 재구성(현재는 채택 구조 없이 단순 목록이라 한눈에 파악 어려움). 사용자 결정(2026-07-07): 범위=**전체 한 사이클**, UI=**통합 채택 인박스**(단, 웹 서비스 내 유사 구조 리서치 후 적용).
- 조사 결론: **용어사전은 대화 후보수집(`_glossary_autopropose`)·검토큐(`glossary_feedback`, 0021/0023)·승급/거부 API 가 이미 구현됨**(기본 ON). **ENUM 코드사전은 CRUD만 있고 후보수집·채택 파이프라인 전무** → 절반 gap. 리서치(Explore agent): 가장 근접 패턴=용어 검토 큐(`renderGlossaryFeedback`), 그룹 카드 껍데기=대시보드 그리드(`.dashboard-widgets`) → IA 권고=지식베이스 하위 **별도 "채택 인박스" 탭 승격**(ENUM 후보는 용어사전 하위에 못 들어감).
- [x] **ENUM 후보수집 백엔드(용어사전 0021/0023 대칭)**: 마이그 `0039_enum_feedback`(`enum_feedback` 검토큐 + `enum_dictionary.source` 컬럼 + GRANT, 비파괴·멱등, HEAD 0038 체인) · `kb_glossary.py`(record/`auto_promote_or_queue_enum`/list/count/promote/reject/`_enum_feedback_status`/`_insert_enum_auto`/`infer_enum_suggestions` + enum CRUD `source` 반영) · `llm.py`(`ENUM_SUGGEST_PROMPT`+`llm_enum_suggest`) · `config.py`(`AGENT_ENUM_AUTOPROPOSE`=1·`AGENT_ENUM_AUTOPROMOTE_THRESHOLD`=0.9 보수적·`AGENT_ENUM_SUGGEST_MODEL/MAX` + `__all__`) · `agent_core.py`(`_enum_autopropose` + 답변 직후 호출, best-effort soft-fail) · `app.py`(권한 `kb.enum.curate` 카탈로그 추가 — 마이그 불필요, admin 자동 시드) · `admin_metadata.py`(`enum-feedback` list/promote/reject API + `admin_list_enums` source 노출).
- [x] **통합 채택 인박스 UI**: `admin.html`(지식베이스 그룹 신규 탭 `data-admin-tab="adoption"` + pane — 필터 툴바[종류/상태] + 카드 그리드 컨테이너) · `admin.js`(`ADMIN_TAB_PERMISSIONS.adoption`=glossary/enum curate OR · switchTab first-entry 훅 · `loadAdoptionInbox`/`renderAdoptionInbox`/신뢰도·상태별 그룹 카드/`_adoptionRow`/개별 채택·거부·되돌리기/`_adoptionBulk` 일괄 채택/`_primeAdoptionBadge` 사이드바 pending 배지/`_wireAdoptionControls` — 용어+ENUM 통합, 보유 권한 종류만 fetch·조작, XSS textContent-only) · `styles.css`(`.admin-meta-tag-kind` 종류 배지 + `.admin-adoption-*` — 기존 `.admin-meta-row`/`.dashboard-widget` 어휘 재사용).
- [x] **검증**: `py_compile` 7 파일 + `node --check admin.js` PASS. 신규 `test_kb_enum_feedback.py`(코어 14, 하이브리드 자동승급·poisoning 방어·되돌리기·infer 필터) + `test_metadata_enum_feedback.py`(web 경계 9, 권한·직렬화·audit·source) 전부 PASS. 기존 `test_metadata_glossary_enum.py::test_enum_list_serializes` 를 source 컬럼(10-tuple) 계약 변경에 맞춰 갱신. route 골든 `route_snapshot_p5b.json` 197→200(enum-feedback 3 라우트) 갱신. **호스트 전체 스위트 1581 passed**(share_redaction 7·route_parity 1 = 사전존재 host-env 아티팩트, 후자 골든 갱신으로 해소). 컨테이너 `make test`: ruff PASS + 유일 실패 `test_routine_dbanalysis::test_schema_analysis_fail_loud`(psycopg `postgres-replica` 미해석)는 **main(repo/)에서도 동일 재현 → 사전존재 env 실패, 본 변경 무관**.
- [ ] **PB-0008 Windows-browser 시각검증**: 정적 자산(admin.html/admin.js/styles.css)이 web 이미지에 baked — 라이브 반영은 merge + `make deploy-web` 재배포 선행 필요(§51 graphux7 등 동일 패턴). **POST-DEPLOY 에서 PB-0008 수행 후 TEST.md §3 라이브 Run append 예정** — ① 지식베이스 > "채택 인박스" 탭 노출(사이드바 pending 배지) ② 신뢰도/상태별 그룹 카드 렌더(용어/ENUM 종류 배지·신뢰도·scope 태그) ③ 개별 채택→해당 사전 반영·큐 갱신 ④ 거부/되돌리기 ⑤ 그룹 일괄 채택 ⑥ 종류/상태 필터 ⑦ pageerror 0. 사유는 TEST.md §3 Windows-browser Run 기록(CHECK#13).
- [ ] verify-completion --pre-commit PASS → commit → push → PR → main merge → cycle-finalize → **web 재빌드·재배포(deploy_scope: included, frontend+backend[ask/insight-worker])** → 배포 자동 마이그레이션으로 `0039` 적용 → `alembic_version` 직접 검증(stale agent 이미지 마이그 누락 방어) → /healthz.

### TASK-20260707-metadata-console-redesign — 메타데이터 콘솔 IA 통합(2차 보기 일반화) + 5서브뷰 디자인 폴리시 (Major §12.3 — feature-0003 web/UI 단독, worktree ai/claude/metadata-console-redesign, 2026-07-07)
- 요청(직전 채택 인박스 배포 후 실사용 피드백): ① `채택 인박스` 최상위 탭이 `용어사전 > 용어 검토 큐`와 겹치고 실질 종속 → 밖으로 튀어나온 탭 제거 ② `샘플 검수` 최상위 탭도 `샘플쿼리` 하위 2차 보기로 동일 편입 ③ 용어사전·ENUM·테이블·컬럼·샘플쿼리 5서브뷰 디자인이 저급 → 이전 교훈 참고해 세련되게. 사용자 결정(2026-07-07): 구조 통합 확정 + 디자인 = **전체 폴리시(감사 Top 10)**.
- 이해(Workflow #1, 5 병렬 리더): glossary 2차 보기(`subTab==="glossary"` 하드코딩) 메커니즘·샘플검수 편입면·채택인박스 제거면·5서브뷰 적대 디자인 감사·이전 교훈(LEARNINGS/CONVENTIONS/worker-design) 매핑.
- [x] **구조(IA 통합)**: 2차 보기를 **서브탭 파라미터화**(`_METADATA_REVIEW` config·`viewBySub` 상태·`_metaSyncViews` 가 `#metadataViews` 에 버튼 동적 생성·`_metaIsReview`) → 채택 인박스 탭/pane/JS/CSS 전량 제거(백엔드·enum-feedback API·`kb.enum.curate` 유지) + ENUM 후보를 `ENUM 코드사전 > {목록|검토 큐}` 로 이동 + 샘플 검수를 `샘플쿼리 > {목록|검수 큐}` 로 편입(`loadSampleReview`/`renderSampleReview` 를 `#metadataList` 재타깃) + 최상위 `샘플 검수` 탭 제거. glossary+enum 검토 큐는 `loadFeedbackQueue(kind)`/`renderFeedbackQueue(kind)` 로 통합.
- [x] **디자인 폴리시(감사 Top 10)**: `--surface-2` 토큰 정의(hover≠active 복구)·`.admin-list-empty` rich empty+skeleton·enums/columns 테이블 단위 `.dashboard-widget` 카드 그룹핑·행 기하 카드형(border-bottom 제거)·title↔body 위계·폼 실제 grid+인라인 검증·samples SQL 프리뷰 클램프·필터 바·배지 semantic 토큰화(자동등록=neutral/미승인=warn/rejected=danger)·이모지 제거+서브뷰 KPI. 기존 세련된 어휘(대시보드 카드·drawer eyebrow·rich empty·focus-ring) 이식(신규 디자인 언어 없음). cache-buster `?v=20260707-metadata-console-redesign`(admin.html: styles.css·admin.js).
- [x] **§18.8 3렌즈 패널 + 수정**: 정합/XSS/디자인 적대 리뷰 → **B1[BLOCKING]** `kb.enum.curate` metadata 탭 게이트 누락(enum-curate 단독 접근 상실) FIXED · **M1[MAJOR]** ENUM 그룹핑 column 드롭 → schema.table.column 그룹+헤더 table.column FIXED · **H1[HIGH]** light-only 콘솔에 다크 토큰 override 회귀 → 제거 FIXED · M2/M3/M4(스켈레톤 shimmer·샘플행 카드 기하·싱글턴 카드 스팸) + L5~L9(KPI 중복·focus-visible·role≠provenance 색·vote 이모지·글리프/color-mix) FIXED. XSS = CLEAN(createElement+textContent 전환). m2(샘플 배지 백엔드 limit 캡)만 accept.
- [x] **검증**: `node --check` OK · 제거 심볼 grep-0(adoption/sample-review/glossaryView/_metaIsGlossaryReview) · `--surface-2` 라이트 정의·다크 override 제거 · CSS 균형(1897/1897) · route 골든 불변(UI-only) · **호스트 전체 1637 passed**(회귀 0; share_redaction 7 = 사전존재 컨테이너경로).
- [ ] **PB-0008 Windows-browser 시각검증**: 정적 자산 baked — merge+deploy-web 후 수행. **POST-DEPLOY** TEST.md §3 라이브 Run — ① 채택 인박스·샘플 검수 최상위 탭 부재 ② ENUM 코드사전·샘플쿼리 하위 {목록|검토/검수 큐} 2차 보기 동작 ③ enum-curate 단독 사용자 메타데이터 탭·ENUM 검토 큐 도달 ④ enums/columns 테이블 카드 그룹핑·행 선택/편집/삭제 ⑤ hover≠active·rich empty·폼 grid+인라인검증·KPI·배지 색 ⑥ pageerror 0.
- [ ] verify-completion --pre-commit PASS → commit → push → PR → main merge → cycle-finalize → **web 무중단 롤링 재배포(deploy_scope: included, UI-only → web 이미지만·worker/마이그 불필요)** → /healthz.

### TASK-20260707T230501-doc-sync-rn-2305 — 07-07 후속(11:34 이후) 머지분 릴리즈노트 정합(코드값 후보 대화 자율수집·채택 + 추론 강도별 예산) + cache-buster bump (doc_sync 2차, 비-정책 콘텐츠 doc, 2026-07-07)
- 트리거: `/_dqa:doc_sync ultracode`(스케줄·무인). 직전 릴리즈노트 sync(dfc64728 @ 07-07 11:34 "07-03~07-07 블록")가 07-07 오전까지 반영 → 그 이후(11:37~19:33) main 병합된 user-facing 델타를 정합. 기존 '2026-07-07' 블록에 2항목 append(같은 날이라 새 일자 블록 생성 안 함)·`generated` 유지(2026-07-07).
- [x] append 2항목(모두 admin): ① "대화에서 모은 코드값(상태 코드 등) 뜻풀이 후보를 검토해 채택"(0beb02e3 — 코드값(ENUM) 대화 자율수집 후보의 검토·채택·거부·되돌리기 + pending 개수 배지) ② "AI 추론 예산을 강도(낮음·높음·매우 높음)별로도 설정"(d9516aee — 기존 '모델별 예산'과 구분되는 강도별 축의 신규 컨트롤).
- [x] **중복 회피(적대 검증 반영)**: 업무 용어(glossary) 대화 자율수집·검토 큐는 **2026-06-29 블록에 이미 announce**(release-notes-data.js 라인 408·414) → 재announce 금지. 07-07 델타 신규분은 **코드값(ENUM) 측**뿐이라 item① 을 코드값으로 rescope('용어사전' 표현 전량 제거). 콘솔 IA 통합(47a63b1a)은 UI 재배치(신규 사용자 능력 0)라 item① 최종 IA(각 사전 하위 검토 큐)에 흡수·별도 항목 미생성.
- [x] 사용자향 평이화 — 내부용어(feature-id·테이블명 enum_feedback/kb_glossary·함수명 _enum_autopropose·권한키 kb.enum.curate·마이그 0039·reasoning_budget·ADR) 누출 0. 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경.
- [x] skip(비-사용자): 메타 콘솔 IA 통합(UI-only reorg)·그래프 화살표/툴팁(b0d9deb6 폴리시)·런타임 pane 재설계(a2fe4103)·OAuth cron 정적화(058fec05)·§56 그래프 sync 견고화(fe05d6f8·94e2e411 내부 데이터 위생).
- [x] 검증: `node --check release-notes-data.js` PASS · 블록 순서(07-07>06>04>03>02) + 07-06 이하 보존 · 스키마(type/area/title/detail) 정합. jsdom DOM 테스트(`verify_release_notes.mjs`)는 이 실행 env 미설치(컨테이너 전용) — 문법+스키마+블록 순서로 갈음.
- [x] 배포 전파: `index.html`·`admin.html` `release-notes-data.js?v=20260707-rn-0707`→`?v=20260707b-rn-0707` bump. verify-completion(operational, feature-0003) → 로컬 commit. **landing(push/PR/merge)·배포는 cron wrapper 소관**(본 run 은 로컬 commit 까지). META(STATUS·wiki·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260707T230501-META-0021-doc-sync-0707-2305).
- [ ] PB-0008 Windows-browser 시각검증: 릴리즈노트 콘텐츠 데이터/캐시버스터만(렌더 로직 불변) — 새로 시각검증할 렌더 델타 없음. 원천 UI(코드값 채택 큐·추론 강도별 예산)는 원천 cycle(0beb02e3·d9516aee)이 검증. 사유는 TEST.md §3(CHECK#13).

### TASK-20260708-metadata-console-polish — 메타데이터 콘솔 잔여 디자인 폴리시 5건 (Minor §12.3 — feature-0003 web/UI 단독, worktree ai/claude/metadata-console-polish, 2026-07-08)
- 트리거: metadata-console-redesign(35e8cb14) 배포 후 **실 Windows 브라우저(PB-0008) 적대적 미적 검증**에서 잡은 잔여 미세 폴리시 5건. 사용자 결정(2026-07-08): 전부 적용 + 재배포.
- [x] **#1 nav 위계**: 2차 보기 필(`.admin-meta-view`)이 border+틴트라 밑줄 1차 서브탭보다 무거워 위계 역전 → border 제거·비활성 투명·활성만 borderless light chip 으로 종속.
- [x] **#2 list-detail 균형**: 넓은 우측 미선택 상세가 좁은 목록을 지배 → 메타 전용 스코프(`.admin-list-detail.admin-meta-list-detail`)로 목록 컬럼 300~400px + `#metadataDetailEmpty` 중앙·max-width 560px(타 pane 무영향).
- [x] **#3 그룹 카드 nesting**: 그룹 내부 행이 자체 카드 테두리를 또 가짐 → `.admin-meta-group .admin-meta-row` divider 평탄화(border-bottom subtle·radius 0·gap 0·hover/active 만 강조).
- [x] **#4 timestamp 노이즈**: 반복 수정 timestamp → `.admin-meta-row-meta` 경량화(10.5px·opacity .72) + 그룹 카드 내부는 숨김(컬럼 1030행 반복 제거).
- [x] **#5 신뢰도 배지**: 검토 큐 배지 4개 전부 회색이라 핵심 신호(신뢰도)가 안 튐 → `.admin-meta-tag-conf`(은은한 primary accent)로 분리(JS `-neutral`→`-conf`).
- [x] 검증: `node --check` OK · CSS 균형(1905/1905) · route 골든 불변 · 호스트 전체 1662 passed(회귀 0). cache-buster `?v=20260707-metadata-console-redesign`→`?v=20260707-metadata-console-polish`.
- [ ] PB-0008 POST-DEPLOY 라이브 재확인(2차 보기 필 경량·그룹 행 divider·신뢰도 accent) → verify-completion → commit → PR → 병합 → web 무중단 배포 → /healthz.

### TASK-20260708-metadata-console-ux2 — 메타데이터 콘솔 UX 이슈 4건 (Major §12.3 — feature-0003 web/UI 단독, worktree ai/claude/metadata-console-ux2, 2026-07-08)
- 트리거: metadata-console-polish 배포 후 사용자 실사용 피드백 4건.
- [x] **#1 밀집/가시성**: 메타 list 컬럼 max 400px 캡 → `minmax(360px,1fr) minmax(0,1.05fr)` 확대 + 행 line-height(제목1.35/본문1.5)·padding 개선.
- [x] **#2 선택 불가**: 검토/검수 큐 후보 행(용어·ENUM feedback + 샘플)을 `role=button`+클릭 → 우측 `#metadataReviewDetail` read-only 상세(전체 정의/라벨·질문·SQL/다이어그램·신뢰도/scope/status + 승급/거부·승인/거부). `_metaRenderReviewDetail`·`reviewSelected` 상태·`_metaRenderDetail` coordination(review view+선택 시 상세, 아니면 empty/폼)·서브탭/보기/스코프 전환·큐 리로드 시 초기화.
- [x] **#3 ENUM 열거값 추가**: ENUM 그룹 카드에 "+ 코드 추가" → `_metaStartCreatePrefilled` 로 생성 폼을 그 schema/table/column pre-fill(code+label 만 입력). 단일/다항목 그룹 양쪽.
- [x] **#4 샘플 mermaid**: `generated_sql` 이 mermaid 면 공용 `mermaid-render.js`(strict)로 다이어그램 렌더, SQL 이면 코드블록. admin.html 에 vendor/mermaid + mermaid-render.js 로드(admin.js 이전). 행 프리뷰는 "다이어그램(클릭해 상세)" 표기.
- [x] 검증: `node --check` OK · CSS 균형(1924/1924) · route 골든 불변 · 호스트 1662 passed(회귀 0). cache-buster `?v=20260708-metadata-console-ux2`.
- [ ] §18.8 패널(서브에이전트) 사용량 한도로 미실행 → **메인 루프 적대 자기검증**(coordination·XSS·mermaid API·액션 정합 확인, 블로킹 0)로 대체 + **PB-0008 라이브가 1차 행동 실증**. verify-completion → 배포 → PB-0008.

### TASK-20260708T230501-doc-sync-rn-0708 — 07-08 머지분 릴리즈노트 정합(분석 기반 제품 분류 AI 제안·그래프 접힘 카드 시각화·메타데이터 콘솔 UX) + cache-buster bump (doc_sync, 비-정책 콘텐츠 doc, 2026-07-08)
- 트리거: `/_dqa:doc_sync ultracode`(스케줄·무인). 직전 릴리즈노트 sync(ed42a378 @ 07-07 23:51)·직전 doc_sync(5aac2b28 @ 07-07 23:52) 이후 07-08 main 병합 user-facing 델타를 정합. `date:"2026-07-08"` 새 블록 prepend(releases[0])·`generated` 2026-07-08.
- [x] append 3항목(전부 admin): ① new "아직 분류되지 않은 데이터베이스의 제품 분류를 AI가 분석해 제안"(§59 — AI 제안→제품 관리 승인 대기→근거 확인 후 승인/거부) ② improved "관계도에서 카드를 펼치지 않아도 연결이 보이고, 관련 항목 강조·확대 수준별 정리"(§57 — 접힘 스키마 카드 연결선·상대 하이라이트·크로스 관계 색 구분·줌아웃 축약) ③ improved "관리 콘솔 검토 화면 개선 — 항목 상세 보기·코드값 직접 추가·다이어그램 표시·가독성"(콘솔 ux2 4건+폴리시 5건 통합).
- [x] **사용자향 평이화**: feature-id·§번호·테이블명(WebProductDatabases/Pending)·함수명·권한키·ADR·마이그레이션·엔드포인트 누출 0. 보안 설계(allowlist 자동기록 금지·Pending 스테이징)는 "곧바로 반영되지 않고 승인 대기로 모임"으로 의미만 전달. 노출 용어('AI 분류 제안'·'코드값(ENUM)')는 실제 온스크린 라벨. 콘텐츠 데이터만 — 렌더 로직(`release-notes.js`)·백엔드·스키마·RBAC 무변경.
- [x] **제외(비-사용자/이미커버)**: §58 스키마 라벨 케이스 정합·AccountDB rekey(Minor 내부 정합)·gateway mem_limit(인프라)·§56 T56.9 PB-0008(07-07 기출시 QA)·병합 충돌/POST-DEPLOY 내부 기록·/daily-report·report_deck·발표자료(META 도구). 07-07 블록 기커버(실행시간·추론예산·카테고리 밴드·관계 확인/해제·DB 단위 분석·코드값 채택·강도별 예산·응답 안정성)과 중복 없음.
- [x] 검증: `node --check release-notes-data.js` PASS · 블록 순서(07-08>07>06>04>03>02) + 07-07 이하 보존 · 스키마(type/area/title/detail) 정합. jsdom `verify_release_notes.mjs` 33/34 PASS(유일 FAIL 은 styles.css pre-existing 취약성·HEAD 동일·본 변경 무관).
- [x] 배포 전파: `index.html`·`admin.html` `release-notes-data.js?v=20260707b-rn-0707`→`?v=20260708-rn-0708` bump. verify-completion(operational, feature-0003) → 로컬 commit. **landing(push/PR/merge)·배포는 cron wrapper 소관**(본 run 은 로컬 commit 까지). META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260708T230501-META-0022-doc-sync-0708).
- [ ] PB-0008 Windows-browser 시각검증: 릴리즈노트 콘텐츠 데이터/캐시버스터만(렌더 로직 불변) — 새로 시각검증할 렌더 델타 없음. 원천 UI(§57 그래프·§59 승인 UI·콘솔 ux2)는 각 원천 cycle 이 검증(§57 PB-0008 PASS·§59 POST-DEPLOY 실증). 사유는 TEST.md §3(CHECK#13).

### TASK-20260709-graph-toolbar-consolidate — 그래프 뷰 상단 툴바 통합 + 우측 상태 텍스트 reflow 제거 (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016)
- 트리거: 사용자 요청(`/_template:entry`) — `관리 콘솔 > 지식베이스 > 그래프 뷰` 상단 버튼 지저분 → 모범 디자인 통합 · 우측 상태 텍스트가 길이에 따라 아래 UI 를 계속 변형(불쾌) → 제거/변형 방지. AskUserQuestion 확정: **팝오버 + 줌 오버레이 · 캔버스 오버레이 알림**.
- [x] 툴바 13컨트롤 → **4존**(검색 · `보기 옵션 ▾` 팝오버 · 초기화 · 상세 ⇆). 팝오버 = 이웃 깊이·노드 종류 필터·스키마 이동·제품 카테고리. 숨긴 종류 수 배지(`_metaGraphSyncViewOptsBadge`) 로 팝오버 내부 필터 상태를 상단에서 인지.
- [x] 줌 4버튼 → 캔버스 좌하단 플로팅 오버레이(`.admin-meta-graph-canvas-wrap` 안, `position:absolute`). 미니맵(우하단 168×112) 무충돌.
- [x] 상태 텍스트 → 캔버스 좌상단 오버레이 pill(`position:absolute` → 레이아웃 흐름 밖, 2줄 클램프+ellipsis, 6s auto-fade `is-idle`, `pointer-events:none`). 내용 길이 무관 툴바·캔버스 높이 불변 = **reflow 원천 제거**. LOD 마커(innerText 직접조작)는 `is-idle` 해제로 표시 유지.
- [x] 컨트롤 id 전량 보존(behavior-neutral) — admin.js `getElementById` 바인딩 불변. 접근성: 오버레이는 `role="img"` 캔버스 밖 형제(팝오버 `role=group`·`aria-expanded`·Esc·바깥클릭 닫힘).
- [x] 캐시버스터 bump: styles.css `20260708-metadata-console-ux2`→`20260709-graph-toolbar`, admin.js `20260709-highlight-ux`→`20260709-graph-toolbar`.
- [x] 검증: `node --check admin.js` OK · 실 Windows Chrome 149(win-browser relay) 격리 harness 렌더 실측(toolbar 자식 4·zoom/status `position:absolute`·status 2줄클램프 494px·팝오버 4행·종류 3버튼 단일행·배지). 스크린샷 harness-closed/open2.
- [x] §18.8 디자인·correctness 적대 패널(SHIP-WITH-FIXES, MINOR 2+NIT 1 FIXED) → REVIEW.md · verify-completion PASS → commit faf1fb2f → PR#635(rebase 로 병렬 §57.6/§57.7 충돌 해소) → 병합 → web 무중단 롤링 배포 ee54b1ff(soak PASS) → **POST-DEPLOY PB-0008 라이브 PASS**(상단 4컨트롤·팝오버 no-clip·줌 오버레이·**상태 pill reflow0=true**·pageerror 0 — TEST.md §3 POST-DEPLOY 갱신).

## 20260711T1150-docs-archive — MODIFY/REVIEW §5.5 아카이빙 (사용자 지시 2026-07-11 "정책문서 분리/세분화")

- [x] MODIFY.md 423건 → 최근 15 유지 + 408 이관(`_archive/MODIFY-archive-20260711T115053.md`) · REVIEW.md 404건 → 최근 15 유지 + 389 이관
- [x] 무손실 증명: head+archive+kept 재구성 md5 == 원본 md5 (양 문서)
- [x] 상단 아카이브 참조 링크 + REPORT.md 압축 정보(§5.5) + 아카이브 파일명 timestamp 규약(ITEM-01) 첫 실적용
- [ ] 후속(별 사이클): feature-0002(124/109건)·feature-0016(117/117건)·feature-0012(46/45건) 동일 아카이빙

## 20260712T0730-item09-graph-split — admin.js 그래프 모듈 분리 (parallel-work-structure ITEM-09)
- [x] 그래프 블록 admin.js 3618~9024(5,407줄·141함수)를 static/graph/graph.js 로 pure mechanical move. admin.js 17,923→12,520(-5,407, acceptance b ≥3,000 충족). admin.js type=module 전환(window 노출 0+bare 전역 mermaid20/G6 47 bridge 로 안전). import surface(adminState/apiFetch/can/showToast/_metaSubmitForm+window.G6)·export surface(_metaShowGraph/_metaGraphLoadRoots/_metaRoleLegendTips/_metaGraph)·순환 import ES live-binding. 자동검증 GREEN: node --check module 문법·정적분석 undefined 0(census 놓친 _metaSubmitForm 포착). graph/MAPPING.md(외부 브랜치 재적용).
- [x] **브라우저 QA(acceptance a/c, PB-0008 실 Windows: 로드·클릭·우클릭·드래그·줌 LOD·검색·패널)** — 2026-07-12 통과(에러 0, test-runs.d/20260712T190500 fragment) → PR #738 머지 + deploy-web 정식 배포(soak 통과). 잔여 후속은 아래 batch23 §.

## 20260712T1905-item09-batch23-stamp — 그래프 CSS/JS 세분화 + 캐시버스터 자동화 (ITEM-09 종결)
- [x] batch2: styles.css 그래프 밴드 **8246~8682**(census 실측 — 구 계획의 8142 는 비그래프 scope-select 베이스라 정정)→graph/graph.css(437줄, admin.html 전용 link). 공유 예외 2(: .admin-meta-ai-btn 크기 규칙·scope-select 베이스) styles.css 잔류. byte-eq·brace 균형 검증.
- [x] batch3: graph.js 5,416줄→7 ES 모듈 섹션-연속 분할(state/roleviz/util/rellayout/simgroups/core/ctxmenu)+barrel(공개 4심볼 re-export, admin.js 경로 불변). 의미 클러스터 분할은 27-run 교차 실측으로 기각(순수이동 검증가능성 우선) — core/ctxmenu 내부 세분화는 충돌 실측 시 재검토(C-12 동형). import/export 표면은 census 마스킹 참조 기계 산출(주석-전용 참조 결합 차단), 죽은 _metaSubmitForm import 제거. 검증: node --check 8/8·verbatim 7/7·미해결참조 0.
- [x] what#3: ?v= 캐시버스터 자동화(§13.1 v3.35.1 1순위) — 소스 ?v=dev placeholder 고정 + scripts/inject_asset_stamp.py(static 트리 content-hash, vendor pin 보존·vendor 내부 우연매치 12건 제외) + Dockerfile RUN + deploy-web asset_stamp_verify 하드게이트. **ES import specifier 도 스탬프** — admin.html(?v=X) vs import(무버전)의 admin.js 이중 인스턴스화 잠복 버그 해소 + 모듈 서브트리 캐시버스터 전파.
- [x] 브라우저 QA(PB-0008): 렌더 baseline 픽셀 동일·graph.css 적용·스코프/검색/줌/클릭/우클릭 — 콘솔 에러 0 (test-runs.d/20260712T190500-item09-batch23-graph-qa.md).


### TASK-20260713T102249-doc-sync-rn-0713 — 07-09~10 머지분 릴리즈노트 정합(관계도 성능·정리·상세 이동·강조 안정화·상단 툴바 / 응답 지연 타임아웃 모달 제거 / AI 능동 분석 '주의' 실질화(§69) / AI 분석 접속거부 연결 조기 skip) (doc_sync, 비-정책 콘텐츠 doc, 2026-07-13)
- 트리거: `/_dqa:doc_sync`(수동·attended). 직전 릴리즈노트 블록(8480a14a @ 07-09 — 모델별 추론 예산) 이후 07-09~10 main 병합 user-facing 델타를 정합. 직전 07-10 스케줄 doc_sync 가 미landed(wrapper landing 실패·stale worktree)라 콘텐츠 harvest 후 supersede — origin/main(c02d81e0) 기준 fresh. `date:"2026-07-10"` 새 블록 prepend(releases[0])·`generated` 2026-07-10.
- [x] append 7항목: ① fixed/work "응답이 오래 걸릴 때 화면을 가리던 대기 안내창 제거"(feature-0003 d87d582e) ② improved/admin "대규모 관계도 성능·정리"(feature-0016 §60~76 뷰포트 컬링·세로폭주 해소·미니맵 재사용) ③ new/admin "상세에서 관련 항목 이동+사용 관계 읽기/쓰기 분리"(§68~72·§75) ④ improved/admin "관계 강조 표시·관계선 위 화면 이동 안정화"(§57.4~9·§62·§64·§66) ⑤ improved/admin "상단 도구 모음 정리"(graph-toolbar) ⑥ improved/admin "AI 능동 분석 '주의' 실질화 — 형식적 자기-불평 제거·실위험만"(§69/ADR-034) ⑦ improved/common "AI 분석 안정성 — 접속 거부 연결 조기 skip"(feature-0002 10da986e).
- [x] **§69 재편입(07-10 run 대비 차이)**: 07-10 run 은 §69 를 T69.5 미완(라이브 미관측)으로 REJECT 했으나, **07-13 PR #744 로 T69.5 POST-DEPLOY 완수**(cc_data_main 재생성 715/715·0 failed, 표본 재확인 시 옛 자기-불평 사실상 0·사용자 원 리포트 '대부분 노드 주의가 불명확' 해소) → 이번 run 은 사용자 릴리즈노트에 편입.
- [x] **사용자향 평이화**: feature-id·§번호·ADR·테이블/함수명·오류코드(18456)·MSSQL·cooldown·모달/long-poll 등 내부표현 누출 0(사용자 언어).
- [x] **cache-buster**: 소스는 `?v=dev` 고정 placeholder 유지 — `index.html`·`admin.html` 수기 bump **안 함**(07-10 run 의 수기 bump 은 ITEM-09 what#3 `inject_asset_stamp.py` content-hash 빌드주입 도입 이전 방식이라 재현 안 함). 배포 시 Dockerfile inject 가 content-hash 주입, deploy-web `asset_stamp_verify` 가 baked placeholder 잔존 하드 차단.
- [x] 검증: `node --check release-notes-data.js` PASS · vm 파서 구조검증(블록순서 07-10>07-09>… 정합·항목 스키마 type/area/title/detail·누출 스캔 0).
- [x] 배포: verify-completion(operational, feature-0003) → 로컬 commit(META STATUS·wiki·RELEASE_NOTES·meta/REVIEW 는 별도 commit). **landing(push/PR/merge)·배포(make deploy-web 무중단)는 본 attended run 소유** → PR→merge→deploy-web→end-state 검증(라이브 `?v=` 해시 갱신·generated 07-10 서빙 확인).
- [ ] PB-0008 Windows-browser 시각검증: 릴리즈노트 콘텐츠 데이터만(렌더 로직 `release-notes.js` 불변) — 신규 렌더 델타 없음. 원천 UI(그래프 §60~76·타임아웃 모달·§69 caveats)는 각 원천 cycle POST-DEPLOY PB-0008 이 검증(다수 PASS). 사유 TEST.md §CHECK#13.
