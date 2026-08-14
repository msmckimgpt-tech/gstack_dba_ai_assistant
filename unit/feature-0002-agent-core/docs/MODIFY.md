---
doc_type: MODIFY
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

> 이전 기록(109건): [MODIFY-archive-20260711T120311.md](./_archive/MODIFY-archive-20260711T120311.md)

## CHG-20260807T160000-redteam-abortable-postdeploy (배포 실증 + 원장/학습 환류, doc-only)
- **POST-DEPLOY(2026-08-07)**: PR #1195 merge main `6b0f50c0` → `make deploy-web` 전체 스코프
  (soak 통과·롤백 0·gateway 드리프트 0). **5서비스 GIT_COMMIT=`6b0f50c0` running/healthy**
  (web-a·web-b·ask-worker·insight-worker·ops-scheduler).
  배포본 ask-worker 런타임 실증: 헬퍼 적재 · 출하 상수(poll 1.0/3.0 · tick 15.0→2배→120.0 ·
  grace 5.0/0.1 · abort_grace 0.5) · **양쪽 배선 2회** · `verify_incomplete` · `review_wait_giveup` ·
  `copy_context` 전부 True. web-a 서빙 `admin.js` 에 `review_wait_giveup` 3건 · `리뷰 미완료` 1건.
  web /healthz `status=ok · mysql_ok · pg_ok · git_commit=6b0f50c0`. **라이브 대화 실측 미수행**
  → 원장 `fixed:deployed:unverified-live`.
- `docs/improvements/conversation-audit/FRICTION_LEDGER.md`: `FR-redteam-first-pass-unabortable`
  status 갱신 + 배포 실증 기록.
- `docs/LEARNINGS.md`: `LRN-20260807-0001`(테스트가 상수를 낮추면 그 상수를 사고 값으로 되돌리는
  뮤테이션이 전부 생존한다) · `LRN-20260807-0002`(호출을 다른 스레드로 옮기면 그 호출이 읽던
  ContextVar 가 조용히 끊긴다 — 기능은 멀쩡하고 관측만 사라진다) 신설.
- 코드 변경 0.

## CHG-20260807T130000-redteam-abortable-review (자가 검증 대기의 사용자 탈출구 복구, Major)
- `src/modules/redteam.py`: `_await_review_interruptible()` 신설 — 리뷰어 1패스를 워커 스레드
  (`thread_name_prefix="redteam-review"`)에 맡기고 폴링하며 ① 중단 신호(`abort_fn`: '즉시 답변'·취소)
  ② 진행 표시 갱신을 처리한다. 반환 `(review, aborted, gave_up)`.
  - **ContextVar 복사**(`contextvars.copy_context().run`) — 아래 [정정 ②].
  - **중단 폴링 백오프**: 초반 10초 1초 → 이후 3초(`_REVIEW_ABORT_POLL_MAX_SEC`). `abort_fn`
    (=`agent_core._rt_abort`)이 호출마다 메모리 DB 를 최대 4회 읽어, 1초 고정이면 상한 300초 대기에
    **패스당 ~1,200 왕복** × 동시 ask 수가 된다.
  - **중단 유예**(`_REVIEW_ABORT_RESULT_GRACE_SEC` 0.5s) + `future.done()` 선확인: 이미 끝났거나
    유예 안에 도착한 판정은 절대 버리지 않고, 넘기면 버리고 초안을 즉시 전달(fail-open).
  - **진행 표시 백오프**: 15s → 2배 → 120s cap. `progress_fn` 은 `_emit_activity`→`save_memory_step`
    이라 tick 마다 DB step 행이 생기고 steps 는 폴링으로 반복 전송된다(고정 15초면 300초에 20행).
  - **대기 포기**: `timeout_sec + max(_REVIEW_WAIT_GRACE_SEC 5s, timeout_sec × 0.1)`. 비례 하한은
    `run_review` 자체 상한 밖의 미계측 구간(클라이언트 해소 전 / `_record_llm_usage` PG INSERT 후)이
    고정 5초를 넘을 때 정상 도착한 리뷰를 우리가 버리지 않기 위한 것. 포기는 `gave_up=True` 로
    리뷰어 실패와 구분해 `stop_reason="review_wait_giveup"` 으로 기록한다.
  - **fail-safe**: 콜백이 없으면 직접 호출(무회귀) · 신호 읽기 **연속** 3회 실패면 중단 판정만 포기
    (중간 성공 시 streak 초기화) · 워커 예외는 정상 실패로 매핑해 `review_error` 행을 보존 ·
    `progress_fn` 예외가 리뷰를 삼키지 않는다.
- `src/modules/redteam.py` `orchestrate_review`: 최초 검증 패스와 재검증 호출 **양쪽**을 이 헬퍼
  경유로 전환. 최초 패스 중단/포기 → `record_review(stop_reason=...)` 후 초안 반환. 재검증 중단/포기
  → 마지막 수정본 채택 + 같은 `stop_reason` + 회차 원장 `note`.
  **`verify_incomplete` 신설** — 재검증이 끝나지 않은 채 나가면 직전(수정 이전) 판정의 BLOCK 을
  `unresolved` 로 세지 않는다. 세면 검증하지도 않은 답변에 "지적 사항 미해소" 고지가 찍힌다
  (`REDTEAM_UNRESOLVED_NOTICE` 운영 기본 1). `unverified` 분기가 같은 이유로 이미 하던 처리의 확장.
- `unit/feature-0003-agent-web-ui/src/static/admin.js`(cross-ref): ② 단계가 `stop_reason` 을 읽어
  사용자 중단(`aborted`)·대기 포기(`review_wait_giveup`)를 "리뷰 수행 실패"가 아닌 `warn` 으로
  구분 표시 + `review_wait_giveup` 라벨 신설. 종전에는 `verdict="error"` 가 무조건 "리뷰 수행 실패"로
  렌더되고 `stop_reason` 라벨은 `unresolved>0` 분기에서만 그려져, 이 경로(`unresolved=0`)에서는
  "사용자 '즉시 답변'/취소" 라벨이 **구조적으로 도달 불가**였다.
- 왜 이 형태인가: `_openai_chat_completion_with_deadline`(llm.py 공용 경로)을 건드리지 않는다 —
  모든 LLM 호출자가 공유하는 함수라 blast radius 가 크고, 필요한 것은 red-team 오케스트레이션의
  대기 방식뿐이다.
- **정정 3건(정직)**:
  ① 첫 구현은 "진입 전 abort 면 리뷰 자체를 skip" 이었으나, 그러면 중단 시에도 '무엇이 남았는지'를
     기록하던 기존 관측 계약(`test_verify_findings_present_even_without_rounds`)이 깨진다 — 실제로 그
     회귀 테스트가 FAIL 로 잡았다. 중단의 의미를 "리뷰 금지"가 아니라 "리뷰 때문에 기다리게 하지
     않음"으로 재정의하고 유예 방식으로 대체했다.
  ② **스레드 이동이 ContextVar 전파를 끊었다** — `_record_llm_usage` 의 `get_active_datasource()`
     폴백이 워커에서 빈 값을 봐 `llm_usage.target_scope` 가 통째로 NULL 이 된다(라이브 14일 redteam
     **295건 중 218건**이 이 폴백 사용). `llm.py` 에 같은 함정 주석이 이미 있었다 —
     **스레드 경계를 옮기는 변경의 표준 점검 항목**. `contextvars.copy_context().run` 으로 수정.
  ③ 초판 문서가 "콘솔 라벨이 이미 있으니 그대로 쓴다"고 적었으나 **거짓이었다**(위 admin.js 항목).
- `tests/test_redteam_abort.py` 신규(**25**) — 출하 상수 계약 3 + 헬퍼 14 + orchestrate 배선 8.
  **상수 계약 테스트는 fixture 를 쓰지 않는다**: 대기 상수를 낮추는 autouse fixture 아래에서는
  `_REVIEW_ABORT_POLL_SEC=300`(= 원 인시던트) 뮤턴트조차 전 스위트를 통과했다(§18.8 qa 패널 실측,
  저장소의 `test-env-override-skip-vacuous-pass` 패턴). 배선 테스트를 둔 이유는 헬퍼 직접 호출만으로는
  orchestrate 가 실제로 그 경로를 타는지 증명하지 못하기 때문이다(게이트 뒤 호출 사각).
- 스키마·RBAC·엔드포인트·프롬프트 무변경. 보안 회귀 없음(리뷰 **강도·판정 기준**은 불변이며,
  중단은 종전에도 존재하던 fail-open 경로와 같은 손실 모델이다). built-in security-review 인라인
  수행 결과 보안 findings 0건.
- Cross-ref: TASK-20260807T130000-redteam-abortable-review ·
  `docs/improvements/conversation-audit/FRICTION_LEDGER.md` FR-redteam-first-pass-unabortable ·
  기능 소유 feature-0021-redteam-review(cross-ref only).

## CHG-20260804T063000-summary-bootstrap-deadlock (요약 미보유 대화의 PG 읽기 오판 교착 해소, Major)
- `src/modules/runtime_backend.py`: `PgRuntimeBackend.load_summary` 가 행 없음/NULL 을 `None` 이 아닌
  **`''`** 로 반환. `_read_runtime_pg` 의 `None` 은 **읽기 실패 전용 신호**라, 데이터 부재를 같은 값으로
  돌려주면 요약 없는 대화가 전부 실패로 오판돼 `load_memory_context` 가 conn=None 인 채 MySQL 폴백을
  타고 예외를 낸다(= 첫 요약을 영원히 못 쓰는 교착). 반환 타입도 `Optional[str]`→`str`.
- `src/modules/memory.py`: `load_memory_context` 의 세 read 검사에 계약 주석 추가(로직 무변경).
- `tests/test_summary_bootstrap_deadlock.py` 신규(5) — 역검증(구 동작 복원 시 2건 FAIL) 확인.
- 스키마·RBAC·엔드포인트 무변경. Cross-ref: TASK-20260804T0630-summary-bootstrap-deadlock ·
  선행 TASK-20260804T0454-summary-writer-wiring(라이브 실증에서 발견).

## CHG-20260804T045449-summary-writer-wiring (대화 요약 writer 배선 복구, Major)
- `src/modules/llm.py`: `_summary_deps()` 신설 — `log_timing`/`load_memory_context`/
  `save_memory_summary`/`_record_step_summary`/`sanitize_user_text`/`_near_run_deadline` 을
  함수-로컬 import 로 해소(본 모듈은 그중 어느 것도 import 하지 않아 `_refresh_summary_after_*`
  가 호출 즉시 NameError 였다). 레거시 두 진입점도 이 해소를 사용하도록 수정.
  `refresh_conversation_summary(conversation_id, *, last_step_summary)` 신설 + `__all__` 등재 —
  게이트 `AGENT_SUMMARY_REFRESH`, conn 불요(PG 런타임 백엔드가 자체 연결), 예외 흡수 후 bool 반환.
- `src/agent_core.py`: `refresh_conversation_summary` 를 `_refresh_conversation_summary` alias 로
  import + `run_post_answer_curation()` 말미에서 호출(topic/glossary/enum 큐레이션과 같은 자리).
  이 한 줄이 `agent_runtime.summary` 의 재연결점 — 이전까지 writer 가 없어 0행이었다.
- `tests/test_summary_writer_wiring.py` 신규(8) — happy/게이트/빈결과/fail-open/**배선 가드**/
  심볼 해소/레거시 진입점.
- 스키마·RBAC·엔드포인트 무변경. Cross-ref: TASK-20260804T0454-summary-writer-wiring ·
  feature-0003 TASK-20260804T0454-prompt-autogen-wiring · REV-20260804T045449-prompt-autogen-wiring.

## CHG-20260803T200000-precondition-postdeploy (POST-DEPLOY 기록, docs-only)
- Date: 2026-08-03. 코드 변경 **0**.
- **배포**: PR #1126 merge main `99d09137` → `make deploy-web` 전체 스코프, soak 통과, 4서비스 GIT_COMMIT=99d09137 healthy.
- **런타임 실증**: 계약 9요소 전부 LIVE(검증-또는-미확인·미확인 1급값·거부/스코프/미조회⇒미확인·0행 범위조건부·커버리지 명시 조건·첨부 IF NOT EXISTS≠증거·미확인 비-무료·조회 시도 의무·`verify > 미확인 > guess`). 라이브 composed 19,764자에 도달, 선행 seal 공존.
- **1차 배포 실패·재실행(정직)**: insight-worker 헬스 미도달 → 워커군 last-good 롤백 → **web 만 신코드** 부분 완료(`DEPLOY_RC=2`). 원인은 배포 창의 일시적 네트워크 버스트(전 datasource `probe-tcp timeout`; **롤백본에서도 동일** → 코드 무관, 이후 양 워커 직접 probe 정상). 자체 회복 후 재실행 RC=0. 교훈: 워커 롤백 = 프롬프트 수정 라이브 미도달이므로 `DEPLOY_RC` 뿐 아니라 **서비스별 GIT_COMMIT** 으로 완료를 판정해야 한다.
- **측정 스냅샷**: 47.8% / `미확인` 0개→**2개**(첫 사용). 90일 창은 과거 지배 → 재측정이 완료 판정.
- **Rollback**: 문서 되돌리기(코드 무변경).

## CHG-20260803T190000-precondition-verified-or-unknown (전제 절의 상태 단정을 '검증된 사실 또는 미확인' 으로 봉인 + 상시 감지기 — conversation_audit FR-review-precondition-assumed-not-verified)
- Date: 2026-08-03. worktree `ai/root/feature-0002-agent-core`(base main 3748c4fd). 범위 승인 **A+C**(AskUserQuestion 2026-08-03).
- **무엇을(A 계약)**: `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 의 `적용 전제` 절 규칙에서 **"stated as fact" 를 제거**하고 **"모든 행은 검증된 사실이거나 `미확인`"** 으로 대체. 5개 하위 규칙 — (1) 상태를 적으려면 **이 run 에 그 객체의 도구 결과**가 있어야 하고, 없으면 `미확인` + 무엇을 확인 못 했는지. `미확인` 은 실패가 아니라 **1급 값**(미검증 존재/미존재가 정직한 미확인보다 나쁘다 — 사용자가 그걸 믿고 행동한다). (2) 권한거부(`접근이 허용되지 않은 스키마`)·스코프 경고·미조회 ⇒ 미확인, 절대 "존재하지 않음" 아님(거부는 존재 여부를 말하지 않는다). (3) **0행은 범위 조건부** — 정확한 식별자 + 도구가 자기 커버리지를 명시한 경우에만 **그 범위 내** 부재로 말하고 범위를 함께 적는다("허용 DB 전체에서 미발견"); 추측 이름·필터 쿼리·커버리지 미명시 ⇒ 미확인. (4) 첨부의 `CREATE TABLE IF NOT EXISTS x` 는 x 의 **현재** 존재 여부 증거가 아님. (5) **미확인은 공짜가 아님** — 결정이 걸린 객체(변경 대상·기존 데이터가 막을 수 있는 것·스크립트 의존 대상)는 최소 1회 조회 시도 의무, `verify > 미확인 > guess`, 예산 아끼려 바로 미확인 금지. SYSTEM_PROMPT 미러도 동일 3요소로 정합(§18.8 R2 P2 — 미러만 열려 있으면 bootstrap 경로에서 결함 존속).
- **무엇을(C 감지기)**: `bin/measure-precondition-grounding.py` 신설. `.sql` 첨부 대화의 최장 답변에서 (백틱 식별자 + 상태 어휘) 줄을 뽑아 **객체 단위**로 집계하고, 그 대화 tool 결과 전체와 대조해 미검증 비율·`미확인` 객체 수·지목 대화를 낸다. **지표가 아니라 스크린**임을 docstring·CLI 양쪽에 명시하고 오탐(무관한 상태 어휘 동거·도구가 언급만 한 경우)과 누락(영어 표현·백틱 없는 이름·제약명)을 열거. RO 트랜잭션 + `statement_timeout` + `ON_ERROR_STOP=1` + 빈 결과 **fail-closed**(exit 3, 타임아웃/권한/무데이터 구분 불가 명시).
- **baseline 측정(90일)**: 대화 87건 · 상태 단정 90건 중 **43건(47.8%) 미검증** · `미확인` **0건**.
- **파일**: `src/agent_core.py`(전제 절 규칙 + 미러), `bin/measure-precondition-grounding.py`(신규), `tests/test_review_proposed_change_framing.py`(+5), `tests/test_precondition_grounding_detector.py`(신규 10).
- **왜**: PB-0008 라이브 검증에서 약 148만 행 실존 테이블을 "현재 미존재" 로 적고(조회 0건) 대용량 PK 추가 리스크를 놓친 사례를 발견. 측정해 보니 이 행동은 시간-방향 계약 이전부터 광범위(47.8%)했고 `미확인` 은 한 번도 쓰인 적이 없었다 — **오래된 구조적 공백**이며, 내 `적용 전제` 절은 그 단정에 표 형태의 자리를 준 **가중 요인**이다(앞선 "내가 만든 결함" 귀속은 정정).
- **호환/안전**: 프롬프트는 보간 없는 정적 상수. 가드·allowlist·RBAC·datamark 무변경. 감지기는 read-only 전용이며 쓰기 구문 부재를 테스트로 고정. 과교정 방지 장치 2종(0행 범위 예외·조회 시도 의무)을 함께 넣어 "미확인 남발" 을 막는다.
- **Rollback**: 계약 문단·미러 revert + 감지기·테스트 2파일 제거. 스키마/마이그레이션 변경 없음.

## CHG-20260803T172000-review-framing-pb0008-live (PB-0008 라이브 육안검증 결과 기록, docs-only)
- Date: 2026-08-03. 코드 변경 **0**. 사용자 지시("실제 웹브라우저 조작을 통해 육안검증까지 진행해주세요").
- **Environment: Windows-browser** — `bin/win-browser.py`(실제 Windows Chrome 150, relay 브리지)로 새 대화 생성·제품 119 선택·**원본 5파일 재업로드(sha256 5/5 일치)**·동일 요청문 입력·`#sendBtn` 실제 클릭. 배포본 main `954adc87`.
- **결과 PARTIAL PASS**: 프레이밍 축 **재현 실패(=수정 성공)** — 도입부가 "실제 DB 현황(BEFORE)과 비교" 로 시간 방향 명시, 미배포 상태가 `적용 전제` 단일 절에 ✅ 로만, 심각도 배지는 적용 후 결함에만, 배포 순서는 말미 Q&A 로 강등. `search_routines` 본문 매칭 스니펫도 라이브 정상(이름 매칭 행은 `(본문 외 매칭)`).
- **잔여 결함 발견**: 같은 답변의 `적용 전제` 표가 `ConcurrentUsers5Rocks_gunz … 현재 미존재` 라 적었으나 ground truth 는 **실존(약 148만 행·ServerID 없음)** 이고 그 테이블을 조회한 도구 호출은 0건 — 미검증 부재 단정. 원장 신규 항목 `FR-review-precondition-assumed-not-verified`(triaged).
- **파일**: `docs/test-runs.d/20260803T1720-review-framing-live-pb0008.md`(Run 기록) + `evidence/20260803-review-framing-after-{top,precondition}.png`(화면 증적) + FRICTION_LEDGER.
- **Rollback**: 문서 되돌리기(코드·스키마 무변경).

## CHG-20260731T040000-grounding-authority-postdeploy (POST-DEPLOY 기록 — 라이브 census 통과, docs-only)
- Date: 2026-07-31. 코드 변경 **0**.
- **배포**: PR #1114 merge main `954adc87` → `make deploy-web` 전체 스코프(web-a/web-b 무중단 롤링 + insight-worker/ask-worker 재생성 + gateway reconcile), soak 90s 통과, 4서비스 GIT_COMMIT=954adc87 running/healthy.
- **라이브 census 재측정(핵심 증거)**: 배포본 ask-worker 에서 실 `agent_memory` 연결로 `compose_system_prompt` 호출 → composed **13,604 → 17,830자**, 필수 seal **9종 전량 LIVE**. 수정 전 측정에서 **부재 확정이던 5종**(첨부↔실DB 양측조회·0행≠부재·절단통지·완전성 명시신호·식별자 대소문자, +check_table_coverage)이 전부 도달로 전환됐다. 억제/첨부우선 지시 0건(Lever B), carve-out(`IT OVERRIDES NOTHING ELSE.`)·"보안·프라이버시 규칙이 이긴다" LIVE, 운영자 마스킹 정책 보존, composed 가 계약으로 끝남(last-writer 실증).
- **원장**: `FR-operator-global-prompt-shadows-code-seals` → `fixed:deployed:verified`(측정으로만 done). `FR-review-frames-live-db-as-spec` 에 A/B 분기의 실제 기전 규명 cross-ref 추가.
- **Rollback**: 문서 되돌리기(코드·스키마 무변경).

## CHG-20260731T030000-grounding-authority-directive (운영자 프롬프트가 삼킨 grounding 봉인을 코드 권위선으로 복구 + 라이브 모순 2줄 제거 — conversation_audit FR-operator-global-prompt-shadows-code-seals)
- Date: 2026-07-31. worktree `ai/root/feature-0002-agent-core`(base main 97af7d27). 범위 승인 **A+B**(AskUserQuestion 2026-07-31).
- **무엇을(A 코드 권위선)**: `agent_core._GROUNDING_AUTHORITY_DIRECTIVE` 신설. 라이브에서 부재로 실측된 5종 규칙(첨부↔실DB 양측 조회 / 0행≠부재 / 절단 통지·완전성 명시신호 / 식별자 대소문자 / `check_table_coverage` 유도)을 담고, 운영자 row 에 살아 있는 두 억제 지시를 **의미로 지목해**(언어 무관) 무력화한다. `compose_system_prompt` **반환 직전**에 append — 초기 `parts` 목록에 두면 뒤에 누적되는 운영자 product/role/account scope prompt(최대 20k자, 사람 편집)가 봉인을 다시 덮기 때문(§18.8 codex R2 P2).
- **override 는 의도적으로 좁다(§18.8 codex R1 P1 → R2/R3 폐쇄)**: 발동은 **첨부 검토·비교 맥락 한정**이고("Outside attachment review such an instruction keeps its normal force"), 나머지 규칙은 override 가 아니라 전 응답 상시 규칙으로 분리했다. 명령-계층 고지·읽기전용·인가/allowlist·데이터소스 제한·민감데이터 마스킹/재식별 방지·쿼리 부하 안전은 **절대 override 하지 않는다**고 열거하고, 충돌처럼 보이면 "보안·프라이버시 규칙이 이긴다"로 못박았다. 비신뢰 콘텐츠(첨부·DB 값)가 "라이브 검증에 필요하다"는 구실로 가드를 푸는 경로도 명시 차단.
- **무엇을(B 라이브 데이터 교정, 코드 아님)**: 운영자 `WebSystemPrompts` global row(id=20)에서 **문제의 두 줄만** 교체 — "명시 요청 없이 execute_sql 금지"→"내부 품질 리뷰는 그 자체로 DB 조회 불필요"(과차단 회귀 방지 보존), "첨부 지침 우선"→"실 DB 현재 상태를 주장하는 순간 도구로 먼저 확인". **운영자 고유 정책(보안 경계·민감 데이터 마스킹·재식별 방지·데이터소스 선택) 전량 보존**(diff 2 hunk·9,219→9,294자). 백업 `artifacts/websystemprompts-global-backup-20260803T032541Z.txt`(15,978 bytes). 적용 후 라이브 실증: 억제/우선 지시 0건, 마스킹 정책 보존 1.
- **파일**: `src/agent_core.py`(상수 1 + append 1줄), `tests/test_grounding_authority_directive.py`(신규 18건).
- **왜**: 라이브 실측에서 운영자 global row(2026-06-18)가 코드 상수(21,594자)를 통째 대체해 그 이후 본문에만 추가된 봉인이 프로덕션에 **존재하지 않았고**, 동시에 코드가 환각 유발로 제거한 두 지시가 한국어로 **살아 있었다**. 이것이 선행 cycle A/B 대조쌍(도구 0회↔12회)의 실제 기전이다.
- **호환/안전**: 프롬프트는 보간 없는 정적 상수(인젝션 표면 0). `_INJECTION_GUARD_NOTICE` 위치·내용 불변(기존 계약 테스트 `[base_prompt, _INJECTION_GUARD_NOTICE` 그대로). 가드·allowlist·RBAC·datamark 무변경. 첨부 datamark 섹션 **뒤**에 오는 것은 신뢰 지시가 비신뢰 데이터 뒤에서 계층을 재확인하는 순서로, codex R3 가 trust-boundary 문제 없음 확인.
- **Rollback**: 상수·append 1줄·테스트 제거(코드) + 백업 파일로 운영자 row 복원(데이터). 스키마/마이그레이션 변경 없음.

## CHG-20260731T020000-review-framing-postdeploy (POST-DEPLOY 기록 — 배포 전이 + 운영자 프롬프트 shadow 발견, docs-only)
- Date: 2026-07-31. 코드 변경 **0** — `CHG-20260730T190000-review-proposed-change-framing` 의 배포 결과와 그 검증 중 드러난 별 트랙 발견을 원장·TASK 에 정직 기록.
- **배포 전이**: PR #1102 merge main `2ecfe4b5` → `make deploy-web` 전체 스코프(web-a/web-b 무중단 롤링 + insight-worker/ask-worker 재생성 + gateway reconcile, soak 90s 통과). 4서비스 GIT_COMMIT=2ecfe4b5 healthy, edge `/healthz` ok·mysql_ok·pg_ok. 원장 `FR-review-frames-live-db-as-spec` → `fixed:deployed:unverified-live`.
- **라이브 compose 실증**: 실 `agent_memory` 연결로 `compose_system_prompt` 를 호출해 결과(13,604자)에 `REVIEWING A PROPOSED CHANGE — TIME DIRECTION` 도달 확인 — 운영자 global row 가 base 를 대체하는 **실제 프로덕션 조건**에서 계약이 살아 있음(AUTH-1a 설계 검증).
- **부수 발견(needs-human, 원장 `FR-operator-global-prompt-shadows-code-seals`)**: 그 검증 중 운영자 `WebSystemPrompts` scope='global' row(**15,978자 / UpdatedAt 2026-06-18**)가 코드 상수 `SYSTEM_PROMPT`(**20,575자**)를 통째 대체해, 2026-06-18 이후 **SYSTEM_PROMPT 본문에만** 추가된 규칙이 라이브에 도달하지 않음을 배포본에서 실측. 부재 확정 7종: `ZERO ROWS IS NOT ABSENCE`·`COMPARING an attachment against the live DB`·`COMPLETENESS COMES FROM AN EXPLICIT COMPLETENESS SIGNAL`·`TRUNCATION NOTICES`·`IDENTIFIER CASE`·`check_table_coverage` 유도·`## ATTACHED FILES` 섹션(코드-append guidance 상수 16,825자에도 부재 = 보완 경로 없음). 도달하는 것은 `parts` always-append 4종뿐. **코드 결함이 아니라 운영 데이터 drift** 이며 수정 방향(운영자 row 재동기화 vs compose replace→merge)이 사람 결정이라 별 트랙으로 분리.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`(FR-review-frames 상태 전이 + FR-operator-global-prompt-shadows-code-seals 신규), `unit/feature-0002-agent-core/docs/TASK.md`(배포 체크 + 부수 발견 인지).
- **Rollback**: 문서 되돌리기(코드·스키마 무변경).

## CHG-20260730T190000-review-proposed-change-framing (쿼리 리뷰 시간 방향 계약 + 미발견 분류 교정 힌트 + 루틴 본문 매칭 스니펫 — conversation_audit FR-review-frames-live-db-as-spec)
- Date: 2026-07-30. worktree `ai/root/feature-0002-agent-core`(base main bb4be6e4). 출처: `/_dqa:conversation_audit "SQL 쿼리 코드 리뷰"` 사용자 명시 호출. 범위 승인(AskUserQuestion 2026-07-30) = **A+B+C 전부 + search_routines 매칭 스니펫**.
- **무엇을(A 시간 방향 계약)**: `agent_core._ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 신설 — 첨부가 **적용될 변경**(DDL/마이그레이션/신규·수정 루틴)이면 라이브 DB=**BEFORE**, 첨부 세트=**AFTER**. 변경이 스스로 도입하는 차이(아직 없는 객체, 바뀐 시그니처, 스크립트가 추가할 키/제약)는 **적용 전제이지 결함이 아니다** — 결함/문제/위험 어휘 금지, 🔴/🟡 배지 금지, "실행되지 않았다/실패했다" 단정 금지. `compose_system_prompt` 의 `parts` 에 always-append 해 **운영자 `WebSystemPrompts` global row 가 base 를 통째로 대체해도 살아남는다**(AUTH-1a 코드 권위선, `_ATTACHMENT_DELIVERY_DIRECTIVE` 와 대칭). SYSTEM_PROMPT §ATTACHED FILES 에 압축 미러 1줄 + 첨부 주입 INSTRUCTION 에 포인터.
- **무엇을(B 출력 구조 계약)**: 같은 상수 안에서 — 전제 항목은 "적용 전제 / 배포 순서" **한 절**에 사실로 기재, 심각도 배지·결함 목록은 **적용 후에도 남는** 문제에만. 리뷰 본문(논리·성능·키/인덱스·트랜잭션·보안·운영)은 적용 후 상태 기준으로 작성.
- **무엇을(C 도구 L2 짝)**: `tools._proposed_change_hint()` — 미발견 시그니처(`doesn't exist`/`Unknown column`/`Invalid object name`/1146·1054·1049 …)에만 붙는 **분류 교정** 3분기 힌트. ① 첨부가 만드는 객체면 적용 전제 ② 어느 첨부도 안 만들면 실제 선행 누락(결함) ③ 권한·스코프·대소문자/오타로도 미발견이 나므로 **교차확인 전에는 ①②로 단정 금지**(선행 0행≠부재 봉인 유지). 부착 3지점: `_tool_execute_sql` 오류 · `_tool_describe_table` 컬럼 0행 · `_tool_describe_routine` 정의 0행.
- **무엇을(scan 스니펫)**: `search_routines` 결과에 `MATCH_SNIPPET` 4번째 컬럼 — 본문 매칭 지점의 앞뒤 문맥(앞 40자~총 140자, 표 셀 120자 상한). MySQL `LOCATE/SUBSTRING/GREATEST`, MSSQL `CHARINDEX/SUBSTRING`. keyword 미지정(전체 열거)은 상수 `''`(LOCATE('')=1 무의미 머리말 회피). 종전에는 목록만 줘서 "왜 이 루틴이 걸렸는지" 알려면 후보마다 `describe_routine` 왕복이 필요했다.
- **파일**: `src/agent_core.py`(상수 1 + compose 주입 1줄 + SYSTEM_PROMPT 1줄 + 첨부 INSTRUCTION 1문장); `src/modules/tools.py`(힌트 3종 상수·`_proposed_change_hint`·`_routine_snippet_cell`·표 렌더 2경로·도구 설명); `src/modules/dialects.py`(MySQL/MSSQL search_routines + base docstring 계약); `tests/test_review_proposed_change_framing.py`(신규 27건).
- **왜**: 라이브 A/B 대조쌍 — 동일 5파일(sha256 일치)·동일 요청문이 3분 간격에 한쪽은 코드 리뷰(`…4348bc34`), 다른 쪽은 현재-DB 부재 지적 중심(`…a2efa955`)으로 갈렸다. 계약 부재로 프레임이 모델 재량이었다. `…b5f40d99` 는 미적용 마이그레이션을 "동적 ALTER 로직이 실행되지 않았거나 실패한 상태" 로 **허위 결함 단정**. corroboration structural(60일 SQL 첨부 96대화 중 12 distinct_conv).
- **호환/안전**: 프롬프트는 보간 없는 **정적 상수**(인젝션 표면 0), `_INJECTION_GUARD_NOTICE` 순서 불변. **라이브 대조 강제·부재 단정 금지 규칙은 그대로**(약화 0 — 회귀 테스트로 고정). 가드/allowlist/RBAC 경계 **무변경**: 스니펫은 `describe_routine` 이 이미 같은 채널로 반환하는 정의 본문의 **진부분집합**이고 같은 `_struct_schema_access_error` allowlist·RO GRANT 뒤에 있다. keyword 는 기존과 동일하게 `_safe_ident` 통과(codex 실측: 따옴표·백슬래시·대괄호 breakout 불성립). 표 컬럼은 스니펫이 전부 비면 종전 3컬럼 유지(열거 잡음 0·하위호환).
- **Rollback**: `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 상수·주입 1줄·미러 2곳 제거 + `tools.py` 힌트/스니펫 헬퍼·호출 3+2지점 제거 + `dialects.py` MATCH_SNIPPET 2곳 revert + 테스트 제거. 스키마/마이그레이션 변경 없음.

## CHG-20260729T141200-runtime-settings-test-env-agnostic (cross-unit — 정본 feature-0003 TASK-20260729T1412)
- `tests/test_runtime_settings.py::test_missing_snapshot_is_fail_open`: `monkeypatch.delenv("AGENT_TIMEOUT_SEC")`
  추가. override 부재 시 baseline 이 **배포 env 우선**인 것은 `_baseline_int` 의 설계된 동작인데
  (운영 `.env` 의 300 을 존중해야 config.py 와 byte-동치), 테스트는 env 를 둔 채 스펙 리터럴 60 을
  요구해 `.env` 를 상속하는 컨테이너 테스트 환경에서 상시 FAIL 이었다. 검증 의도("스냅샷 부재 →
  폴백")를 보존하면서 env 의존만 제거.
- 코드(제품) 변경 0. 상세 근거·라이브 검증은 feature-0003 REVIEW REV-20260729T141200-test-live-db-isolation.

## CHG-20260722-dqa-data-grounding-and-scratch-csv (데이터 의미 grounding 지침 신설 + scratch_sql 결과 CSV export — DQA 마찰 B-1/D-1/D-2/F-5)
- Date: 2026-07-22. worktree `ai/claude/dqa-grounding-scratch-csv`(base main 66a48870). 사용자 요청(/_template:entry): `DQA_assistant_마찰개선사항_20260722_v2.md` 마찰 검토·개선. 스코프 승인(AskUserQuestion) = B-1 타임존 + D-1 ENUM + F-5 scratch CSV(E-5 대화누출은 병렬 세션 `feature-0019-xconv-leak` 담당이라 중복 회피).
- **무엇을(1) 데이터 의미 grounding 지침**: `agent_core._DATA_GROUNDING_GUIDANCE` 신설 — `_run_agent_core` compose 에서 `_ACTIVE_INTERPRETATION_GUIDANCE` 직후 **무조건(그룹 if-블록 밖) 주입**(1:1·그룹 공통). 3블록: (a) **타임존(B-1)** — 서버 TZ 설정(`@@time_zone` 등)은 저장 datetime 값의 기준 TZ 를 알려주지 않음(MySQL DATETIME 은 TZ 미저장); 서버 TZ 만 보고 "저장값=로컬시각" 단정 금지, 불확실 시 알려진 기준점 데이터 교차검증 + 변환 가정 답변 명시, 미확정 시 임의 offset 금지. (b) **ENUM/코드(D-1)** — 코드 의미 지어내기 금지, GLOSSARY & ENUM VALUES·`get_sample_rows`/`GROUP BY` 분포 grounding 또는 미보유 고백. (c) **분리저장(D-2)** — "전체 X" 요청 시 여러 컬럼/테이블 분리저장 커버리지 명시. `guidance_registry.py` 에 `data-grounding` 항목 등록(관리 콘솔 작동지침 목록 노출).
- **무엇을(2) scratch_sql CSV export(F-5)**: 과거 `scratch.run_sql` 이 미리보기 상한(200행)까지만 fetch·CSV 미저장 → 대량 cross-DS 병합 결과 회수 불가(execute_sql 과 비대칭). 이제 `run_sql` 이 export 상한(`AGENT_SCRATCH_MAX_RESULT_ROWS`=100000)까지 전체 fetch(+`export_truncated`), `_tool_scratch_sql` 이 execute_sql parity 로 `save_csv("scratch_resultset1", …)` → "CSV 저장: <path>" emit + 미리보기(execute_sql 표 포매터 50/adaptive) 절단 + 미열람 행 단정 금지 안내. 웹 UI 는 기존 `CSV_PATH_RE` 로 그 경로를 파싱해 다운로드 링크 생성(**프론트 무변경**).
- **파일**: `src/agent_core.py`(`_DATA_GROUNDING_GUIDANCE` 상수 + 주입 1줄); `src/modules/guidance_registry.py`(`data-grounding` 등록); `src/modules/scratch.py`(`_DEFAULTS['AGENT_SCRATCH_MAX_RESULT_ROWS']`=100000, `run_sql` 전체 fetch + `export_truncated`); `src/modules/tools.py`(`_tool_scratch_sql` save_csv parity + preview stats); `tests/test_gc_dialect_context.py`(grounding 3건), `tests/test_scratch.py`(CSV export 3건); docs(feature-0002 TASK, feature-0022 TASK-0014, FRICTION_LEDGER 3항목).
- **왜**: B-1 은 assistant 가 서버 TZ 설정을 저장값 의미로 오판해 집계 기간 전체를 9h 어긋나게 한 ★최우선 correctness 결함(전 시트 오염 위험). D-1 은 ENUM 코드 환각("3=Stamina", 정본 4). D-2 는 분리저장 부분집계 누락. F-5 는 대량 scratch 결과 회수 불가. 셋 다 게임-무관 일반 개선.
- **호환/안전**: grounding 은 항상 주입되는 advisory 프롬프트(가드/권한/파이프라인 불변, base·product 프롬프트 뒤 last-writer). scratch CSV 는 execute_sql 이 이미 쓰는 `save_csv`/`CSV_PATH_RE` 경로 재사용(신규 유출 표면 0 — scratch_guard·대화격리 불변); save_csv 실패는 try/except 로 미리보기 결과를 막지 않음. export 상한 100000 은 기존 반입 상한과 정합(메모리 bounded). 검증: 변경-특화 로컬 테스트(scratch+guidance) 37 PASS; make test 전체 스위트는 기존 비결정 flake(postgres-replica `--no-deps` DNS + 순서-의존 runtime_settings/attachment)로 main 기준선에도 다른 실패셋 존재 → 내 변경-특화 테스트는 양쪽 실패셋에 부재(회귀 0 확증).
- **Rollback**: `_DATA_GROUNDING_GUIDANCE` 상수·주입 1줄·registry 항목 제거 + scratch/tools 변경 revert + 테스트 제거. 스키마/마이그레이션 변경 없음.

## CHG-20260716-redteam-axis-rederive (자가검증 BLOCK 축 인지 재도출 — 텍스트 다듬기만 하던 revise 를 sql/max-completeness 는 도구 재추론으로 승격, Major §12.3 — core 답변 파이프라인·LLM 비용/지연)
- Date: 2026-07-16. worktree `ai/claude-corp/feature-0002-redteam-rederive`(base main). 사용자 요청(/_template:entry): "자가 검증을 통한 BLOCK 이 확인되었지만 별도의 재추론을 진행하지 않고 이미 구성된 답변을 다듬는 행위만 진행 후 제출". 구성 승인 = 세 요소 모두 취하되 completeness 재도출은 매우높음(max)에서만.
- **무엇을**: red-team 자가검증 revise 경로를 축 인지로 분기. 기존엔 모든 BLOCK을 `_rt_revise`(도구 없는 단발 텍스트 재작성)로만 고쳐, `sql`(틀린 쿼리)처럼 새 근거 필요 결함은 못 고치고 다듬기만 했음. 이제 `sql`(항상)·`completeness`(매우높음)는 `_rt_rederive`(도구 허용 재추론)로 승격.
- **파일**: `src/modules/redteam.py`(`_REDERIVE_ALWAYS_AXES`/`_REDERIVE_LEVEL_GATED_AXES`·`_rederive_enabled`/`_rederive_eligible_axes`/`_block_rederive_axes`·`build_rederive_instruction`·`orchestrate_review(rederive_fn=)` 라우팅 루프+evidence 재계산·`record_review`/meta 확장); `src/agent_core.py`(`_rt_rederive` 상한 도구 루프 신규 — `_run_tool_defs`+`execute_tool` 재사용, `REDTEAM_REDERIVE_MAX_TOOL_ROUNDS` 상한, 마지막 라운드 tools=None, 라운드당 도구 3개 cap, 보안 `_datamark_untrusted`+4000자 truncation 미러, evidence 호환 step, fail-open + 배선); `shared/runtime_settings.py`(`REDTEAM_REDERIVE_ENABLED`1·`_MAX_TOOL_ROUNDS`3·`_COMPLETENESS_MIN_LEVEL`3 live); `alembic/.../20260716_0043_redteam_rederive_columns.py`+MAX_MIGRATION+`scripts/agent_runtime_schema.sql` 미러(redteam_reviews 3컬럼 additive).
- **왜**: `sql`/`completeness` BLOCK을 다듬기로 "고치면" 헤징 강등·BLOCK 미해소·근거없는 정정(새 grounding 위반 주입) 중 하나로 귀결. 실제 도구 재실행 재추론만 정정 가능.
- **호환/안전**: grounding/permission/honesty 는 기존 텍스트 재작성 유지(무회귀). 재추론 무산출/비활성(`REDTEAM_REDERIVE_ENABLED=0`)/예외는 텍스트 재작성으로 폴백(fail-open 불변). completeness 는 사용자 결정대로 max(ordinal 3)에서만 승격 — 모호축 비용/드리프트 위험을 최대사양 티어로 국한. migration additive expand-safe·GRANT 불필요(ADD COLUMN 상속). 검증: 전체 스위트(0002+0003) 2145 passed/2 skipped/RC=0 회귀 0.

## CHG-20260716-graph-search-content-match (그래프 뷰 검색 매칭 확장 — 컨텐츠 카테고리 + AI 능동 분석 본문, Minor §12.3; 교차 feature-0016 정본)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0016-graph-search-content`(base main). 사용자 요청(/_template:entry): "그래프 뷰 내부에서 검색을 진행할 때, '테이블, 컬럼, 용어' 뿐만 아니라, 컨텐츠 카테고리 및 AI 능동 분석을 통해 얻은 내용 또한 매칭될 수 있도록 구성해주세요."
- **컨텍스트**: 그래프 뷰 검색은 서버사이드 정본이다 — 프론트 `_metaGraphSearch`(feature-0003 `graph-ctxmenu.js`)는 `/api/admin/metadata/graph?q=` 를 호출하고 반환 노드를 그대로 렌더·글로우한다. 실제 매칭은 `search_nodes()` Cypher 가 담당하며 기존엔 `n.name`/`n.fqn` CONTAINS 만이었다. "컨텐츠 카테고리" = §78~81 컨텐츠 단위 그룹(= AGE 노드 `semantic_cluster_label`, sim-group LLM 라벨). "AI 능동 분석 내용" = `node_analysis_jobs.analysis`(feature-0016 §69/ADR-034 — agent_kb 관계형 테이블, AGE 정점 아님). 프론트가 임의 매칭 노드를 이미 처리하므로 **백엔드 단독 변경**으로 요청 충족(활성 세션 `graph-ctxmenu.js` 편집과 스코프 충돌 회피).
- **변경**: `src/modules/metadata_graph.py`
  - `search_nodes()`: Cypher WHERE 를 `((toLower(n.name) CONTAINS q OR toLower(n.fqn) CONTAINS q OR toLower(n.semantic_cluster_label) CONTAINS q){key_clause}){scope_clause}` 로 확장. (1) `semantic_cluster_label` CONTAINS = 컨텐츠 카테고리 매칭(AGE 노드 프로퍼티; `toLower(null)`=null 은 openCypher OR 에서 무시 → 비클러스터 노드 오포함 없음). (2) `key_clause` = 아래 분석 매칭 `node_key` 를 `n.key IN [ '<key>', ... ]`(`_cq` 인용, injection-safe) 로 합류. RETURN 9컬럼(+`semantic_cluster_label`), `_cypher(..., 9)`.
  - 신규 `_analysis_match_keys(cur, query, scope, limit)`: **동일 `_ro_conn` 커넥션**(AGE 그래프 `metadata_kb` 와 `node_analysis_jobs` 둘 다 agent_kb DB)으로 `SELECT DISTINCT node_key FROM node_analysis_jobs WHERE status='done' AND analysis IS NOT NULL AND position(%s in lower(analysis::text))>0 [AND scope_key=%s] LIMIT %s`. 전부 psycopg bind param(injection-safe), `position()`=LIKE 와일드카드/ESCAPE 없는 대소문자 무관 부분일치, `::text` 로 text/json/jsonb 저장형 무관, 1자 질의 스킵(노이즈·풀스캔 방지), 권한/컬럼 부재·실패 시 `[]`(graceful degrade → 이름/카테고리 매칭만 유지).
  - `_node_dict`: row[8] 존재 시 `cluster_label` 부여(len(row)>8 가드 — 다른 호출처 없음, search_nodes 전용).
  - 매칭 근거 `match_via`(name/category/analysis 다중) 노드에 부여 — 이름/카테고리는 반환값 재확인, 분석은 key 집합 판정. pg_trgm score 를 `GREATEST(similarity(name,q), similarity(fqn,q), similarity(cluster_label,q))` 로 확장(카테고리 매칭이 이름 매칭에 밀려 cap 절단되지 않도록 랭킹 보정; analysis-only 매칭은 score≈0 이나 결과·글로우 유지).
- Why: 사용자가 컨텐츠 카테고리·AI 분석에서 발견한 개념으로 노드를 찾을 수 있어야 하는데, 검색이 이름/FQN 만 봐서 그 축이 사각지대였다. 두 정보 모두 검색 응답 payload 에 없었으므로 매칭은 반드시 백엔드(Cypher/직렬화·분석테이블 조인) 확장이 선행돼야 한다.
- Impact: 검색 경로만 확장(neighborhood/scope_roots/schema_tables 등 다른 모드 무변경). name/fqn-only 매칭 동작 보존(회귀 0). 모든 검색이 `node_analysis_jobs` position() 스캔 1회 추가(admin 읽기·300ms 디바운스·`status='done'` 필터·1자 스킵 — 허용, 필요 시 후속 trigram GIN 인덱스). `_SEARCH_CAP`(80) 불변 — 매칭 소스 증가로 상한 도달 확률↑(UI '결과 상한' 안내 기존).
- Rollback: `search_nodes` Cypher/RETURN revert + `_analysis_match_keys`·`_node_dict` row[8] 제거 + 테스트 제거. 다른 경로 영향 0. 스키마/alembic 변경 없음.
- Deploy: web 재빌드(metadata_graph 는 web import). alembic/스키마 변경 없음.
- Cross-ref: feature-0016-metadata-graph(그래프 뷰 정본, §78~81 컨텐츠 카테고리 / §69 node_analysis) TASK/REPORT cross-ref · feature-0003 `graph-ctxmenu.js` `_metaGraphSearch`(프론트 소비, 무수정) · REV-20260716T010620-graph-search-content-match.

## CHG-20260715-llm-probe-thinking-budget (LLM provider 헬스 probe 오탐 — stale "요청량 한도/사용량 소진" 배너 고착 해소, Major §12.3 — LLM 라우팅·외부 비용)
- Date: 2026-07-15. 별도 worktree `ai/claude/feature-0002-llm-health-probe`(base main). 사용자 요청(/_template:entry): "assistant 가 내부 인사이트·답변 시 claude-corp 계정 사용량 소진 메시지가 뜨는데 실제로는 허용량이 남아있다 — 원인 파악·수정".
- **근본원인(재현 확정)**: `probe_provider`(active health probe, web `/api/llm/health` 60s 폴링)가 `OPENAI_MODEL`(운영값 `claude-haiku-4-interactive`)로 `max_tokens=1` ping 을 보낸다. 그러나 이 alias 는 litellm config(`feature-0007 litellm_config.yaml`)에서 `thinking.budget_tokens: 5000` 을 강제 → Anthropic 제약(`max_tokens > thinking.budget_tokens`) 위반 → **항상 400**. `classify_llm_provider_error` 는 이 400 을 **None** 으로 반환(실제 실행 검증: 대표 400 3종 모두 None) → probe 가 `record_provider_ok` 도 `record_provider_restricted` 도 못 남긴다. 결과: 배너를 끄는(clear) 유일한 자동 경로(probe)가 무력 → claude-corp 이 순간 429(burst)로 sticky `restricted` 를 한번 기록하면(정상), 계정 회복 후에도 성공 답변이 발생하기 전까지 **배너가 영영 stale 로 고착**. (auto-memory `llm-routing-interactive-split` "thinking budget > max_tokens 오진" 함정과 일치.)
- **변경**: `src/modules/llm_provider_health.py`
  - 모듈 상수 `_PROBE_THINKING_BUDGET = 1024`(Anthropic budget 하한) 추가.
  - `probe_provider`: `create` 인자를 `create_kwargs` 로 조립. `model_supports_thinking(model)`(claude-*)이면 `extra_body={"thinking":{"type":"enabled","budget_tokens":1024}}` + `max_tokens=1088`(>budget, 400 회귀 방지)로 **valid ping** → 성공 시 `record_provider_ok` 가 stale 배너를 실제 해소. 비-thinking 모델(로컬 gemma/edge)은 `max_tokens=1` 유지(최저 비용). thinking override 는 `_call_llm` 이 이미 쓰는 검증된 메커니즘(test_reasoning_effort) 재사용.
  - `probe_provider` **recovery-only gate**(적대 리뷰 CONCERN 흡수 REV-20260715): 비-force probe 는 `state=restricted`(복구 감지 필요)일 때만 실제 valid-ping; `ok/unknown` 은 실제 호출 없이 cached 반환. → idle 정상 폴링이 claude-corp 5h rolling 윈도우를 재고정하지 않게(refresh-claude-oauth-token.sh cron-probe 제거 원칙 정합). 정상 상태 새 제한은 reactive(agent_core) 가 잡고, force(사용자 재시도)는 gate 우회.
  - `tests/test_llm_provider_health.py`: `test_probe_thinking_model_sends_valid_max_tokens_over_budget`·`test_probe_non_thinking_model_uses_minimal_max_tokens` + recovery-only gate 4건(ok/unknown skip·restricted ping·force bypass). 파일 **37 passed**.
- Why: probe 는 배너 자동 복구 메커니즘인데 thinking-강제 alias 도입(interactive-split 2026-07-04) 이후 max_tokens=1 이 구조적으로 항상 400 이 되어 그 역할을 못 했다. 유효 요청으로 바꿔 자동 해소 복원 + recovery-only gate 로 정상 시 실호출 억제.
- Impact: classify/영속 스키마/HTTP/TTL·stampede 가드 무변경. probe 실제 claude 호출은 **restricted(outage) 창 또는 force 일 때만**(≤~1088 output) — 정상 idle 폴링은 실호출 0(윈도우 재고정 없음). 비-thinking·정상 경로 무회귀.
- Rollback: probe 의 create_kwargs 분기 revert(→ max_tokens=1) + 상수/테스트 제거. 다른 경로 영향 0.
- Deploy: web 재빌드(agent_core 모듈은 web import). alembic/스키마 변경 없음.
- Cross-ref: REV-20260715T120000-llm-probe-thinking-budget / feature-0007 litellm_config.yaml(thinking budget) / CHG-20260625T045450-limit-subject-msg(동일 배너 메시지 계보).

## CHG-20260625T012217-kb-pg-superuser-host (deploy infra fix, Minor §12.3)
- Date: 2026-06-25. **deploy/infra** — 코드·런타임 동작 무변경. 별도 worktree `ai/claude/kb-pg-superuser-host-fix`.
- Reason: `make up`(배포) 의 memory-init 단계가 `KB Postgres schema 적용 실패: FATAL: bouncer config error` 로 exit 1. 근본 원인 — `_ensure_pg_schema`(memory.py:854) 의 superuser DDL 연결이 `AGENT_KB_PG_SUPERUSER_HOST` 미설정 시 `AGENT_KB_PG_HOST(=pgbouncer)` 를 상속하는데, pgbouncer userlist 엔 DML role `agent_kb_rw` 만 등록(auth_query 없음)되어 superuser `postgres` 인증 불가.
- 진단(연결 실측): superuser `postgres` 직결(host=postgres)=OK / pgbouncer 경유=`bouncer config error` 재현 / 런타임 `agent_kb_rw`@pgbouncer=OK. KB 스키마는 이미 적용됨(15 tables, vector·pg_trgm) — 재적용 connect 만 실패하던 것.
- 변경: `.env.example` `AGENT_KB_PG_SUPERUSER_HOST=` → `=postgres` + 사유 주석(DDL 은 superuser 직결, pgbouncer 우회). 코드(memory.py)는 이미 본 변수를 1순위로 지원(line 854) — 설정만 누락이었음.
- 런타임 적용: 배포 환경 `.env`(gitignore, 본 PR 외)에 동일 라인 추가 후 `make up` **exit 0** 검증 완료(memory-init KB role/권한 검증 통과). `.env.example` 은 신규 배포 재발 방지용.
- Rollback: `.env.example` 1줄 revert. 코드·스키마 영향 0.
- Deploy: 없음(설정 문서). 런타임은 `.env` 수정 + `make up`(이미 수행).
## CHG-20260625T020410-gc-member-kick-ban (TASK-20260625T020410-gc-member-kick-ban — 멤버 차단 데이터 계층 cross-feature. feature-0003 주관, **Critical §12.3 — 접근제어**)
- Date: 2026-06-25. 주 변경·정본 changelog 은 feature-0003 CHG-20260625T020410-gc-member-kick-ban. 본 항목은 feature-0002-agent-core 교차변경(멤버십 차단 코어/스키마/마이그)만 교차 기록(§13.2.7).
- 변경(feature-0002):
  - `src/scripts/agent_runtime_schema.sql`: 신규 테이블 `agent_runtime.conversation_member_bans`(PK conversation_id+account_id, banned_at/banned_by_account_id/reason, FK core_conversations ON DELETE CASCADE) — 멱등 CREATE.
  - `alembic/versions/20260625_0018_conversation_member_bans.py`(revision `0018_conversation_member_bans`, down_revision `0017_table_column_descriptions`): 위 테이블 + **명시 GRANT**(agent_kb_rw SELECT/INSERT/UPDATE/DELETE, agent_kb_ro SELECT — superuser 적용 deploy-trap 회피, 0012 동형). downgrade=DROP TABLE.
  - `src/modules/group_members.py`: 신규 `ban_member`(INSERT ON CONFLICT DO UPDATE — 재차단 시 banned_at/by/reason 갱신, 멱등, reason 512cap)·`unban_member`(DELETE, rowcount)·`is_banned`(빈 cid/account 단락, row 유무)·`list_bans`(banned_at isoformat dict). 전 SQL `agent_runtime.conversation_member_bans` schema-qualified + `%(...)s`(ADR-0027). 기존 add/remove/role/list 함수 무변경.
  - `tests/test_member_kick_ban.py`: ban 함수 8 케이스(schema-qualified·upsert·reason cap·rowcount·빈인자 단락·isoformat·정렬).
- Why: feature-0003 의 owner 전용 차단(ban) 엔드포인트가 소비할 차단 목록 데이터 계층. 추방(kick)은 기존 `remove_member` 재사용이라 코어 변경 없음 — ban(영구 재참여 차단)만 신규 저장이 필요.
- Impact: 멤버십 read/add/remove·backfill·열람 게이트 무변경(순수 additive). ban 후 메시지/첨부 잔존(remove_member tombstone 동일). conversation 삭제 시 FK CASCADE 로 ban 정리.
- Rollback: alembic downgrade(DROP TABLE) + group_members 4함수·테스트 제거. 기존 멤버십 경로 무영향.
- Deploy: **alembic 0018 적용 필수**(superuser + GRANT). web 가 소비(별도 코어 데몬 재빌드 불요 — group_members 는 web import).

## CHG-20260625T045450-limit-subject-msg (요청량 한도 주체 구분 + 서비스 한도 메시지 provider명 제거 — cross-feature, feature-0002 주관, Minor §12.3)
- Date: 2026-06-25. 별도 worktree `ai/claude/limit-subject-msg`(base main). cross-feature(feature-0002 서비스 메시지·정본 / feature-0003 계정 메시지 cross-ref).
- 사용자 요청(/_template:entry): ① 요청량 한도 도달 주체 구분(계정 당 / 서비스 자체), ② 서비스 한도 메시지의 AWS Bedrock 언급 제거(서비스 자체 한도 명시).
- 변경(feature-0002):
  - `src/modules/llm_provider_health.py` `_build_restriction` KIND_THROTTLED 분기: `f"{plabel} 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."` → `"서비스 자체의 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."`. provider 라벨(AWS Bedrock/로컬 LLM/LLM 제공자) 비노출 + "서비스 자체" 주체 명시. 사유 주석 3줄. 나머지 kind(credential_expired/auth_invalid/unavailable/unknown)는 관리자 진단용 plabel 유지 — 범위 밖.
  - `tests/test_llm_provider_health.py`: `test_throttled_message_is_service_level_without_provider_name` 추가(message 에 "Bedrock" 부재 + "서비스" 포함). 기존 throttle 테스트는 kind/retryable 만 단언 → 무회귀.
- Why: 서비스 사용자에게 내부 backend(AWS Bedrock) 명칭 노출은 부적절하고, "요청량 한도"가 계정 한도인지 서비스 한도인지 모호. 주체를 명시해 사용자 혼선·문의 감소.
- Impact: 응답 dict shape(kind/provider/message/retryable/error_tag/confirmed)·HTTP 429·분류 로직 무변경. PG 영속(llm_provider_health.message)에 새 문구 저장(글로벌 banner — confirmed=True 인 ThrottlingException). 순수 사용자 노출 텍스트.
- Verification: py_compile + `pytest test_llm_provider_health.py` 19/19 PASS + 렌더 확인.
- Files: `src/modules/llm_provider_health.py`, `tests/test_llm_provider_health.py`, `docs/{TASK,MODIFY,REVIEW}.md`. (+ feature-0003 `src/app.py`·`docs/{TASK,MODIFY,REVIEW}.md` 계정 메시지)
- Rollback: 2파일 revert(메시지 문구·테스트). 로직·계약 영향 0.
- Deploy: web + ask-worker 재빌드·재시작(메시지는 web app.py probe 와 agent_core 양쪽에서 생성). 마이그/스키마 없음.
## CHG-20260625T035655-init-embedding-latency (init "준비" 4s→50s 회귀 해소, **Major §12.3** — LLM provider/인프라·성능, cross-feature 0002·0007)
- Date: 2026-06-25. 별도 브랜치 `ai/claude/fix-init-embedding-latency`(main 체크아웃 infra-integration — embed-ollama 가 라이브 `repo-` compose 프로젝트에 속해야 gateway 도달 가능 → §13.2.7 F0 carve-out, `--skip-repo-immutability`).
- Reason: 사용자 보고 — LLM 응답 "준비(init)" 단계만 4초→50초(대기·추론 정상). init="준비"=`_build_knowledge_context` grounding 임베딩 구간.
- 근본원인(라이브 실측 3축): ① 2026-06-23 `litellm_config.yaml` 이 `titan-embed` 를 Bedrock Titan→공유 Ollama bge-m3(`ollama-edge`)로 전환(chat 을 Anthropic-direct 로 옮기며 AWS 자격 제거 → 임베딩만 401 → 로컬 대체). ② 공유 Ollama(`local-llm-edge`, 별도 `local_llm` 프로젝트) `OLLAMA_MAX_LOADED_MODELS=1` → 타 서비스 chat 모델이 bge-m3 를 축출 → 매 임베딩 cold 재로딩 **실측 27~37초**(warm 0.13초). ③ init 이 동일 질문을 sample_queries(few-shot)+account_recall 에서 **2회 중복 임베딩**(run-level 캐싱 없음) → ~50초.
- 변경:
  - `docker-compose.yml`: 전용 `embed-ollama` 서비스(ollama/ollama, bge-m3 단독, `OLLAMA_MAX_LOADED_MODELS=1`+`KEEP_ALIVE=-1`, WSL `/dev/dxg`+wsl libs GPU 패스스루, 전용 named volume `embed_ollama_models`, dbnet) + `volumes:` 섹션.
  - `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`: `titan-embed` api_base `ollama-edge:11434`→`embed-ollama:11434`(차원 1024 동일 — 백필/검색 호환). Bedrock Titan 복구 시 토글 후 embed-ollama 비활성 가능.
  - `unit/feature-0007-bedrock-llm-provider/src/scripts/embed-ollama-init.sh`(신규): 데몬 기동 + bge-m3 부재 시 pull + /dev/tcp warm-up(영구 상주).
  - `shared/config.py`: `AGENT_KB_QUERY_EMBED_TIMEOUT_SEC=20`(상호작용 질의 임베딩 fast-fail) + `__all__`.
  - `src/modules/kb_retrieval.py`: `_embed_query_vector(text, timeout_sec=None)` — timeout_sec→`_get_llm_client(timeout_sec=)`. 미지정 시 기존 동작.
  - `src/agent_core.py` `_build_knowledge_context`: 질의 임베딩 **1회 계산(`_shared_qvec`)→sample_queries·account_recall 공유**(fast-fail timeout 적용). 두 기능 OFF 면 임베딩 skip. user_message whitespace-normalize 후 임베딩(cosine(raw,norm)=1.000000 — 품질 무변).
  - `src/modules/sample_queries.py`·`src/modules/account_recall.py`: `query_vector` 인자 + sentinel `_QVEC_UNSET`("미제공→자체임베딩" vs "None→skip" 구분, 백워드호환). sample 의 `_embed(timeout_sec=)` 전달.
  - `tests/test_sample_flywheel.py`·`tests/test_account_recall.py`: 임베딩 mock 시그니처 `**k` 수용(timeout_sec).
- Impact: 준비(init) 임베딩 **~50초→0.13초**(전용 warm). chat(추론)·DB·기타 grounding(schema/glossary/metadata/table_insight=substring·ILIKE) 무영향. few-shot·account recall 기능·ds-scope 격리 보존(임베딩=f(text)).
- 검증: GPU 실효성 실측(bge-m3 1.2GB·100% GPU·warm 0.13s) + 단위테스트(통과; attachment_idor 4건 사전존재·무관) + 적대 backend 패널 ACCEPT-WITH-NITS(REV-20260625T035655) + 라이브 e2e(titan-embed gateway 0.13s, chat 정상).
- Rollback: litellm api_base 를 `ollama-edge`(또는 Bedrock 토글)로 환원 + embed-ollama 서비스/volume 제거 + 코드 변경 revert(전부 backward-compatible — 인프라만 환원해도 동작).
- Deploy(라이브 수행됨): embed-ollama up + bge-m3 pull + bedrock-gateway 재시작 + ask-worker/insight-worker/web `--no-cache` 재빌드·재생성.

## CHG-20260625T164701-ds-conn-circuit-msg (datasource 회로차단 사용자 안내 문구 분리 — cross-feature, feature-0002 주관, Minor §12.3)
- Date: 2026-06-25. worktree `ai/claude/ds-conn-unstable-copy`(원본 세션 entry "WEB_QA 데이터소스 연결 불안정 메시지 개선" 이 검증 중 API Overloaded 로 중단 → resume 로 재개·완수). 재개 시 main drift(`df97f47`/TASK-0011-9 가 db import 를 `modules.db`→`shared.db` 마이그레이션·`modules/db.py` 삭제) 흡수 후 현재 main 기준 재적용.
- Reason: 사용자 보고(2026-06-25) — `DatasourceCircuitOpen` 회로차단(한 datasource 일시 지연을 격리하는 보호 동작·자동복구)이 "DB 연결 실패/불안정/차단" 프레이밍으로 노출돼 WEB_QA 사용자가 서비스 고장으로 오인. 사용자 결정: 톤=투명형(격리 이유 설명), 용어="데이터소스".
- 변경:
  - `shared/db.py` `DatasourceCircuitOpen.user_message()`(신규): 사용자 화면 전용 문구("현재 연결된 데이터소스의 응답이 일시적으로 지연…다른 작업에 영향이 가지 않도록 잠시 대기…약 N초 뒤 자동으로 재연결…잠시 후 다시 요청"). `int(retry_after)+1`초만 보간 — scope_key/좌표/비밀번호 비노출. 생성자 `str(e)`(기술/로그)는 **미변경**(주석만 추가 — insight.py scan_outcome 가 타입 분류하되 문자열을 로그로 읽으므로 안정 유지).
  - `unit/feature-0002-agent-core/src/agent_core.py`: `DatasourceCircuitOpen` import + 멀티 datasource primary except·단일 datasource fallback except 두 곳에서 `isinstance(e, DatasourceCircuitOpen)` 시 `e.user_message()`, 그 외만 "DB 연결 실패".
  - `unit/feature-0002-agent-core/src/modules/tools.py`: `DatasourceCircuitOpen` import + `execute_tool` `router.conn_for(label)` 에 `except DatasourceCircuitOpen` 선행 분기(label 접두어 생략, 안내 문구만 반환).
- 범위: circuit 외 모든 연결오류는 기존 문구 그대로. raise 거동·예외 타입·응답 dict shape·분류(kind) 무변경. eval datasource 경로(None-gated 테스트 전용·운영 미도달) 의도적 제외. 메모리/control-plane 경로는 `datasource=None`(게이트 미적용)이라 circuit 미발생.
- 검증: §18.8 적대 패널(general-purpose outside voice — e 바인딩·except 순서·누락 surface·비밀노출·str(e) 안정성·테스트 회귀 6축 REFUTE) **BLOCKING 0**(REV-20260625T164701-ds-conn-circuit-msg) + py_compile + ruff All passed + 회귀(conn_health 타입 단언·tool/insight/datasource 153 PASS).
- Rollback: 3파일 revert(순수 additive — `user_message()` 메서드·import·isinstance 분기 제거 시 기존 "DB 연결 실패" 거동으로 환원). 데이터/스키마/마이그 변경 0.
- Deploy: 코드만(스키마·마이그·env 0). ask-worker(agent_core/tools)·web 재빌드(surface 경로). deploy_scope: included.
- Cross-ref: REV-20260625T164701-ds-conn-circuit-msg / FUNCTION ds-conn-circuit-msg / TASK-20260625T164701-ds-conn-circuit-msg.

## CHG-20260629T114221-describe-table-overlay-mssql (cross-feature, feature-0003 주관 — metadata-bootstrap-mssql-db; describe_table 컬럼 오버레이 MSSQL read 축 정합, Major §12.3)
- Date: 2026-06-29. worktree `ai/claude/metadata-table-desc-fix`(feature-0003 `/_template:resume` cycle). feature-0003 §18.8 panel 이 적발한 MAJOR(+재검증 BLOCKING)의 read-축 수정.
- Reason: feature-0003 부트스트랩이 MSSQL 컬럼 설명을 `schema_name=database`(예 GunzGame, 사용자 결정)로 저장하도록 규약을 바꿨는데, describe_table 도구 오버레이(`_tool_describe_table`)는 SQL 스키마(dbo)로 조회 → 축 불일치로 부트스트랩 컬럼 설명이 describe_table 출력에 미주입.
- 변경:
  - `src/modules/tools.py` `_tool_describe_table`: KB 오버레이 조회 시 `_dialects.active().name=="mssql"` 이면 조회 schema 를 `_cfg.get_active_default_db()`(pin primary DB, `_mssql_pin_gate` 와 동일 좌표)로, None 시 도구 schema 인자(dbo) 폴백. SQL introspection(describe_columns)·MySQL 경로 무변경.
  - `src/modules/kb_metadata.py` `load_column_descriptions_for_table`: schema 매칭을 case-insensitive(`LOWER(schema_name)=LOWER(%s)`, ORDER BY 도 LOWER)로 — `get_active_default_db()`는 소문자 정규화(gunzgame)인데 저장값은 원본 케이스(GunzGame)라 PG `=`(case-sensitive)로 대문자 포함 DB명이 0행이 되던 회귀(panel 2차 BLOCKING) 해소. 이 함수는 describe_table 오버레이 전용(다른 호출처 0).
- 범위: MSSQL describe_table 오버레이 조회 키·매칭만. 질문-시점 grounding(`load_table_column_descriptions`, Path B)은 schema 무관(substring 매칭)이라 무영향. MySQL 정확매치 ⊂ LOWER매치(무회귀). graceful({}) 유지.
- 검증: py_compile(tools.py·kb_metadata.py) PASS · §18.8 panel(general-purpose 적대) Path A 정합 복구 재검증.
- Rollback: tools.py 오버레이 키 분기 1블록 + kb_metadata.py LOWER 매칭 revert(기존 case-sensitive·schema 인자 직접 사용으로 환원). 데이터/스키마/RBAC 0.
- Deploy: ask-worker(tools.py·kb_metadata.py) 재빌드(deploy_scope: included).
- Cross-ref: feature-0003 CHG/REV/TASK-20260629T114221-metadata-bootstrap-mssql-db / config.py `get_active_default_db`(소문자 정규화) / kb_metadata.py `load_column_descriptions_for_table`.

## CHG-20260701T163000-graphview-render (cross-cut — 관리콘솔 그래프 뷰 마커 렌더-타임 갱신 백엔드분, Major §12.3)
- 변경: `src/modules/node_analysis.py` — `get_scope_analysis_status(scope_key, node_keys=None)` 추가. `node_analysis_jobs` 를 node_key 로 group_by + `bool_or(status='done')`/`bool_or(status IN ('pending','running'))` 집계 → `{done_keys, running_keys}`. `node_keys` 지정 시 `ANY(%s)` 부분집합. PG 미가용/예외 → None(코어 비차단, sibling `get_node_analysis` 동형 연결/close). 스키마·마이그·기존 함수 무변경.
- 용도: feature-0003 관리콘솔 그래프 뷰가 그래프 로드/검색/확장 직후 `GET /api/admin/metadata/graph/analyze/status` 로 이 함수를 호출해 스코프의 분석완료/진행중 노드 마커를 **클릭 없이** 렌더-타임에 적용(항목①). 엔드포인트·프론트는 feature-0003.
- Verification: `py_compile` PASS. 실 KB PG 정합 실측(scope `mssql-06656002eda6`: done 335·active 183·distinct 826, `accountdb`/`accountdb.GMRIP` done=t). 적대 코드리뷰 SHIP(REV-20260701T163000-graphview-render, feature-0003).
- Deploy: web 이미지 재빌드(deploy_scope: included — node_analysis 는 web·insight-worker 공용 모듈).
- Cross-ref: feature-0003 CHG/TASK/FUNCTION/TEST/REV-20260701T163000-graphview-render / feature-0016-metadata-graph TASK T16.

## CHG-20260703T093000-insight-load-spread (insight/graph 부하 분산 — 실패 대상 격리·재시도 backoff·batched/incremental graph sync, Major §12.3, cross-feature 0002·0016)
- 변경: `relationships.py`(probe 실패 격리 — `unknown database` regex→negative 파단, `_backoff_validated` transient 재프로브 backoff, `fetch_probe_candidates` backoff-window 제외), `insight.py`(datasource 순회 circuit-open `should_fast_fail` skip), `metadata_graph.py`+`scripts/metadata_graph_sync.py`(`sync_graph` batched commit + `since` incremental + `get/set_sync_watermark`, CLI `--incremental`/`--full`), `bin/metadata-graph-sync.sh`(인자 pass-through), `bin/install-metadata-graph-sync-cron.sh`(30분 incremental + 04:17 full), `.env.example`(knob 3 + jitter 문서화).
- 근본원인: circuit-open/없는DB(dblog)/timeout edge 를 매 tick(8s)·cadence 반복 probe/scan(격리·backoff 부재) + graph sync 57,000+ 요소 autocommit 개별 MERGE(30분 cron 5.7만 WAL fsync). 결과 gemma 545%·postgres WALSync 대기·워커 unhealthy·swap 압박.
- 스키마·마이그 **무변경**(table_relationships 기존 컬럼 + agent_runtime.kv 재사용). env 신규 3(backoff/batch/incremental) — 기본값 안전(미설정 시 정상 동작).
- Verification: 신규 단위 10 + 회귀 0(test_relationships 57·metadata_graph units 10·insight datasource/health 66) + AST/`bash -n`. 적대 backend+qa 패널(REV-20260703T093000-insight-load-spread).
- Deploy(외부영향 — 사용자 confirm): agent 이미지 재빌드(insight-worker baked, 마이그 없음) + insight-worker/local-llm-edge 재기동 + `sudo bin/install-metadata-graph-sync-cron.sh` 재설치.
- Cross-ref: feature-0002 REPORT/TASK TASK-0308 · feature-0016 REPORT "graph sync 부하 분산" · ANCHOR 0002 §3 / 0016 §1 무충돌.

## CHG-20260703-insight-heartbeat-liveness (insight-worker healthcheck false-negative 해소 — 진행-중 heartbeat throttle 갱신, Minor §12.3)
- 변경: `insight.py` — 신규 `_touch_worker_heartbeat_progress(mem_conn, min_interval_sec=30)` + `_scan_instance_schema_insights` 의 스키마 순회(`for schema in candidates`)·테이블 순회(`for table in selected_tables`)에 호출 삽입. cycle 진행 중 `insight_worker_last_cycle_at` 을 30s throttle 로 갱신.
- 근본원인: healthcheck(healthcheck_insight_worker.py age≤180s)·_is_insight_worker_heartbeat_fresh(age≤30s)가 heartbeat 를 cycle **완료 시각**으로만 보던 탓에, TASK-0308 claude 전환 후 9.4분+ 긴 cycle 이 stale→unhealthy 오판(false-negative — worker 는 활발히 생산 중).
- 스키마·마이그·healthcheck 판정식 **무변경**(heartbeat 갱신 지점만 추가). status 미변경(cycle 완료 finally 확정). hang 탐지 의도 보존(생성 정지 시 호출 경로 멈춰 stale→unhealthy).
- Verification: 신규 test_insight_heartbeat_liveness.py 2 + insight 회귀 0(12 PASS) + AST OK. 경량 cycle(§18.4) — 적대 패널 SKIPPED.
- Deploy(외부영향 — 사용자 confirm): agent 이미지 재빌드(insight-worker baked) + insight-worker 재기동 → docker inspect healthy 확인.
- Cross-ref: feature-0002 REPORT/TASK insight-heartbeat-liveness · TASK-0308(원인 유발 claude 전환) · REV [SKIPPED:heartbeat-throttle-liveness].

## CHG-20260706T013532-reasoning-effort (대화 화면 사용자 지정 추론 강도 — agent-core 요청 단위 thinking 주입 배선, Major §12.3, cross-feature primary=feature-0003)
- 변경(cross-feature edit — 코드 거주 feature-0002, primary/문서 정본 = feature-0003-agent-web-ui): `agent_core.py` — `run_agent`/`_run_agent_core` 에 `reasoning_level` kwarg 추가(양쪽 kwonly 말미), `_call_llm` 에 `reasoning_level` 파라미터 + thinking 지원 모델(claude-*)일 때만 `kwargs["extra_body"]={"thinking":{"type":"enabled","budget_tokens":N}}` 주입. `modules/ask.py` `_payload_to_kwargs` 에 `reasoning_level` 복원(worker 경로 패리티).
- import: `shared.model_catalog` 에서 `model_supports_thinking`·`thinking_budget_for_level` 추가 import. budget=None(미지정/미상) 또는 비-claude 모델이면 주입 안 함(config 기본값 유지, 무해).
- 매핑(shared/model_catalog): 낮음=2000·높음=10000·매우높음=16000 override, **일반=override 없음**(모델 config 기본 유지, B1 회귀 방지). budget(≤16000) < agent max_tokens(20000, `_CLAUDE_MAX_TOKENS["agent"]`) — Anthropic 요구 만족(litellm 이 budget≥max_tokens 도 내부 보정하나 애초에 만족). thinking 활성 시 temperature 는 claude alias 에서 이미 미전달이라 정합. 주입은 메인 agent 경로(_call_llm)만 — 보조 호출(summary/topic/validate via `_openai_chat_completion_with_deadline`)은 무변경(의도).
- Verification: 신규 `tests/test_reasoning_effort.py` 12 PASS(매핑·정규화·B1 no-override 가드·주입 4분기·제약·worker parity) + 전체 스위트 회귀 0. B2 라이브 게이트웨이 프로브로 extra_body.thinking override 실증(budget 1024 vs 16000 → reasoning 2073자 vs 6914자, 동일 프롬프트).
- Files: `unit/feature-0002-agent-core/src/agent_core.py`, `unit/feature-0002-agent-core/src/modules/ask.py`
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260706T013532-reasoning-effort(정본) · shared/docs/MODIFY.md CHG-20260706T013532-reasoning-effort · feature-0003 REVIEW.md REV-20260706T013532-reasoning-effort

## CHG-20260707T100640-no-edge-conversation-answer (대화 답변 경로 edge(gemma) 폴백 완전 차단 — 명백한 실패처리, Major §12.3, conversation_audit FR-edge-fallback-conversation-context-loss)
- Date: 2026-07-07. `/_dqa:conversation_audit` 진단(conv …9e0883bb "DB 설계 및 JSON 데이터 구성 검토", owner admin, 1:1). 사용자 명시 불만("? 맥락을 잃어버렸나요?") + 데이터 삼각측량으로 근본 확정.
- 근본원인: turn2~4 가 요청 모델 `claude-haiku-4` 인데 실제 서빙(llm_usage.resolved_model)이 `gemma4:e2b`(로컬 edge-fallback, ctx 4096)로 silent 강등. prompt_tokens 세 턴 모두 정확히 **4096**(turn1=29K)로 ~30K 토큰 대화 히스토리가 잘려 맥락 완전 소실 → assistant 가 방금 자기가 쓴 리뷰(4339)조차 모른 채 무관한 일반론 환각 + "기억한다"고 거짓 부인(I-FALSE). 원인 체인 = litellm fallback `claude-haiku-4 → root → edge-fallback(gemma)`, 두 claude 계정 429(오늘 rate-limit 버스트) 시 gemma 우회. 2026-07-04 "대화 무중단 안전망" 결정의 산물이나, gemma 는 대화를 유지가 아니라 **silent 파괴**. 재발경로 = infra capacity → degradation 정책.
- 사용자 결정(2026-07-07, AskUserQuestion): "assistant 답변에 edge/gemma 는 전혀 고려 대상이 아니며 fallback 도 구성돼선 안 된다 — 명백한 실패처리로 구성. gemma 개입을 완전히 끊어라." → 2026-07-04 무중단(gemma keep-alive) 결정을 **대화 답변 경로에 한해 override**(insight 배치·분석은 유지).
- 변경(cross-feature edit; 코드 거주 primary=feature-0002, config=feature-0007, 헬퍼=shared):
  1. `agent_core.py` `_call_llm`(정의상 task='agent' 답변 경로): litellm 에 보내는 `model` 을 `conversation_answer_model(model)` 로 치환 — `claude-haiku-4` → edge-free 대화 전용 alias `claude-haiku-4-chat`. 표시·저장·usage `model` 컬럼·max_tokens·thinking·vision 판정은 **원본** `model` 유지(무회귀), 실제 서빙은 resolved_model 로 추적. import 1줄 추가.
  2. `shared/model_catalog.py`: `conversation_answer_model()` + `_CONVERSATION_ANSWER_ALIAS`(claude-haiku-4→chat) + `__all__` 등록. 순수 additive. 매핑 밖 model(claude-sonnet-4 — 애초에 fallbacks 목록에 없어 edge 강등 無)은 identity.
  3. `unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml`: deployment `claude-haiku-4-chat`(claude-corp)·`claude-haiku-4-chat-root`(root) 신설(haiku-4-5·thinking 5000, 동일 OAuth). fallback `{"claude-haiku-4-chat": ["claude-haiku-4-chat-root"]}` — **edge 없음**, chat-root 는 fallback 미등록 → 양 계정 401/429 시 그 에러를 raise. 기존 `claude-haiku-4`·`-interactive`·`edge-fallback` 체인 **무변경**(insight 배치·분석 gemma 강등 유지).
- 깨끗한 실패 경로(기존 재사용): 두 계정 실패 → litellm raise → `_run_agent_core` LLM-error 핸들러가 `classify_llm_provider_error`(429→KIND_THROTTLED)로 "서비스 자체의 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요." 로 치환 + provider health 기록 후 break. gemma 답변 원천 차단.
- Verification: 신규 `tests/test_conversation_answer_no_edge_alias.py` 4 PASS(헬퍼 매핑·identity·_call_llm→chat 라우팅·기록 원본 유지·sonnet 무변경) + feature-0002 전체 스위트 회귀 0(재사용 agent 이미지). py_compile·litellm YAML lint OK. ⚠ feature-0003 `test_route_parity_p5b` 는 재사용 이미지의 Starlette 버전 drift 로 실패하나 **clean main(repo/)에서도 동일 실패** 확인 → 환경 artifact(내 diff 에 웹 라우터·golden 무변경), 정본 `make test`(핀 deps) 에선 통과.
- 라이브 실측 필요분(§정직): 코드/테스트는 "대화 답변이 edge-free alias 로만 나가고 실패 시 깨끗이 안내" 증명. "실제 rate-limit 상황에서 gemma 미개입" 은 배포 후 corroboration 재측정(task='agent' resolved_model gemma 분포 0 유지)으로 확인.
- Files: `unit/feature-0002-agent-core/src/agent_core.py`, `unit/feature-0002-agent-core/tests/test_conversation_answer_no_edge_alias.py`
- Deploy(외부영향 — 사용자 confirm, Major override 불가): ask-worker + web 재빌드(baked 코드) + bedrock-gateway 재생성(litellm_config bind-mount 반영). deploy-stage 격리 확인.
- Rollback: litellm_config 의 -chat/-chat-root deployment·fallback 제거 + `conversation_answer_model` 매핑을 identity 로(또는 _call_llm 치환 제거). insight/분석 무영향이라 부분 롤백 안전.
- Cross-ref: shared/docs/MODIFY.md CHG-20260707T100640-no-edge-conversation-answer · feature-0007 MODIFY.md CHG-20260707T100640-no-edge-conversation-answer · feature-0002 REVIEW.md REV-20260707T100640-no-edge-conversation-answer · FRICTION_LEDGER FR-edge-fallback-conversation-context-loss · ANCHOR 0002 §1~§3 / 0007 §1~§2 무충돌(가드·자격 경계 불변, 폴백 경로 축소만).
## CHG-20260706T094937-runtime-settings (TASK-20260706T094937-runtime-settings — 런타임 설정 live 타임아웃 getter + 모델별 thinking budget 주입, cross-unit: 정본 feature-0003, Major §12.3)
- Date: 2026-07-06 (worktree ai/claude-corp/feature-0018-runtime-settings). 문서 정본/전체 맥락은 feature-0003/docs (관리 콘솔 `시스템 > 설정`).
- `src/modules/llm.py`: AGENT_TIMEOUT_SEC 을 `_get_llm_client`/`_openai_request_timeout` 내부에서 `runtime_settings.get_int("AGENT_TIMEOUT_SEC")` 로 읽어 관리 콘솔 저장값을 **즉시 반영**(live). `_openai_request_timeout(AGENT_TIMEOUT_SEC)` 호출부 5곳은 인자 생략(→ live fallback, 무override 시 동치). AGENT_INSIGHT_TIMEOUT_SEC 등 restart-mode 는 기존 상수 유지(config.py 가 기동 시 스냅샷 반영).
- `src/modules/mcp_client.py`: MCP 요청 timeout 을 `runtime_settings.get_int("MCP_TIMEOUT_SEC")` 로 read(live).
- `src/agent_core.py` `_call_llm`: 사용자 지정 추론강도(reasoning_level)가 없을 때 `runtime_settings.model_thinking_budget_override(model)` 로 관리자 설정 모델별 budget 을 요청 단위 `extra_body.thinking` 주입. override 미설정이면 미주입 → 모델 config 기본 thinking 유지(**B1 무회귀**, reasoning-effort 정합). budget 은 `min(budget, max_tokens-1024)` 로 clamp(Anthropic budget<max_tokens 안전; 기존 reasoning-effort 값은 no-op).
- 무override 시 전 경로 기존 동작 동치(회귀 0). 상세·검증은 feature-0003/docs/TEST.md·REVIEW.md.

## CHG-20260707T130000-reasoning-budgets (TASK-20260707T130000-reasoning-budgets — _call_llm 추론 강도별 budget override, cross-unit: 정본 feature-0003, Major §12.3)
- Date: 2026-07-07. `src/agent_core.py` `_call_llm`: 요청 thinking budget precedence 를 확장 — 명시 추론강도(low/high/max)면 `runtime_settings.reasoning_budget_override(level)` 우선(없으면 `thinking_budget_for_level` 기본), '일반(normal)'/미지정이면 `model_thinking_budget_override(model)`(기존). '일반'은 thinking_budget_for_level 이 None 이라 레벨 예산 분기 미진입 → 레벨 예산이 절대 주입되지 않음(**B1 무회귀**). budget<max_tokens clamp 유지. 신규 `test_reasoning_effort.py` +3(precedence). 워커(ask/insight) 경로 동일 함수라 자동 적용.
- Cross-ref: feature-0003·shared MODIFY/REVIEW 동일 slug.

## CHG-20260707T134500-bedrock-chat-alias-probe-artifact (investigation, no-op — feature-0002/0007 cross-ref, CHG-20260707T100640 후속)
- Date: 2026-07-07. `bedrock-gateway` 로그의 `claude-haiku-4-chat`/`-root` 1회성 `max_tokens must be greater than thinking.budget_tokens`(400, 10:37:18 KST) 오류를 조사. 배포 타이밍 재구성(PR #600 머지 10:28:41 → gateway 재생성 10:31:02 → ask-worker/insight-worker 이미지 재빌드 10:32:18) + 실패 시각의 실행 이미지를 직접 열어 이미 수정 코드 보유 확인(stale-image 가설 기각) + 정적 코드 추적(`_call_llm` 이 유일 caller, claude-* 모델엔 항상 `max_tokens=20000` 주입 — 충돌 코드 경로 없음) + 게이트웨이 라이브 재현(`max_tokens<5000` 일 때만 동일 오류 재현, `≥5000`/미지정은 정상) 으로 **코드 결함 아님** 확인. FRICTION_LEDGER 의 "live probe(claude-haiku-4-chat→claude 확인)" 절차가 `max_tokens` 를 충분히 싣지 않고 보낸 **1회성 프로브 아티팩트**로 결론(재발 0, 실 사용자 트래픽 영향 없음).
- Files: 코드 변경 없음. Docs: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`(FR-edge-fallback-conversation-context-loss addendum) · `unit/feature-0002-agent-core/docs/REPORT.md`(신규 절).
- Cross-ref: FR-edge-fallback-conversation-context-loss(CHG-20260707T100640) 후속 조사.

## CHG-20260710T232503-alembic-multihead-gate (parallel-work-structure ITEM-02 — 병렬 마이그레이션 번호 경합 머지 전 적발 + 해소 자동화)
- Date: 2026-07-10. 병렬 브랜치 동번호 마이그레이션(0036 실충돌, 6263e641 수동 re-parent)이 머지 후에야 발견되던 것을 3중 장치로 전환: ① `bin/migrate-lint.sh` 에 head 단일성/번호 중복/MAX 정합 정적 검사(`--heads` 신설 + 기존 diff/`--all` 모드 상시 편입 — versions/*.py AST 파싱, 라이브 DB 불필요) + self-test 4 케이스(총 10) ② `.github/workflows/ci.yml` test job "Migration gate" 스텝(머지 게이트) ③ `versions/MAX_MIGRATION.txt` 의도적 충돌 파일(최신 head 1줄 — 병렬 head 생성 시 git 머지에서 반드시 충돌 → CI 전 fail-fast, RESEARCH W-005 django-linear-migrations 패턴). 해소 자동화: `bin/alembic-reparent.sh <file> <새번호>`(파일명·revision·down_revision 3곳 원자 치환 + MAX 갱신 + lint 재검, guard: origin/main 미머지 파일만).
- Files: `bin/migrate-lint.sh`(+~180) · `bin/alembic-reparent.sh`(신설) · `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt`(신설, `0039_enum_feedback`) · `.github/workflows/ci.yml`(스텝 1) · `unit/feature-0002-agent-core/docs/MIGRATIONS.md`(규약 절).
- 검증: TEST.md §3 "alembic-multihead-gate" — self-test 10/10 · 현행 39체인 PASS · 중복 0040 재현 FAIL→reparent 1회 복원 · 병렬 브랜치 MAX 충돌 재현. DB 스키마 무변경(마이그레이션 0건 — 도구·게이트만).
- Cross-ref: `docs/improvements/parallel-work-structure/ROADMAP.md` ITEM-02 · REV-20260710T232503-alembic-multihead-gate.

## CHG-20260711T120311-docs-archive (MODIFY/REVIEW §5.5 아카이빙)
- Date: 2026-07-11. §5.5(20건 초과)·§5.6 임계 적용 — MODIFY 124건(109 이관)·REVIEW 109건(94 이관), verbatim·무손실 md5 증명·가역. feature-0003 선례 동일 스크립트.
- Files: docs/MODIFY.md·REVIEW.md·_archive/ 2파일·REPORT.md·TASK.md.

## CHG-20260713T140405-describe-routine-tool (저장 프로시저/함수 정의 조회 전용 도구 신설, Major §12.3, conversation_audit FR-show-create-routine-blocked)
- Date: 2026-07-13. `/_dqa:conversation_audit` (사용자 명시 호출). 대화 "재사용 쿼리의 PK 관리 문제 추가 리뷰" 에서 `SHOW CREATE PROCEDURE gunzgame.Game_AccountAttendence` 가 `execute_sql` sql_guard(SELECT/CTE-only)에 (의도대로) 차단돼 assistant 가 프로시저 로직 검토에 막힘.
- Reason(RC): **L2(거부 피드백 교정 힌트 부재) + capability gap** — 거부 메시지가 루틴 정의 조회 경로를 안내하지 않고, LLM 노출 도구(핵심 4개)에 루틴 본문 조회 수단이 없었다. sql_guard 의 SELECT/CTE-only 는 의도된 핵심 보안 기능(F4)이라 **불변 유지**; 정의 열람 접근 자체는 이미 `information_schema` always-allow 로 열려 있었으므로(막힌 것은 SHOW CREATE 구문형태) 신뢰경계 확장 없이 전용 도구로 봉인.
- 사용자 승인 방식: **Option 1**(전용 도구 + 유도) — AskUserQuestion(2026-07-13). Critical 취급 → 승인 후 구현.
- Changes:
  - `src/modules/dialects.py`: `Dialect.routine_definition/routine_parameters`(base) + MySQLDialect(information_schema.ROUTINES/PARAMETERS) + MSSQLDialect(INFORMATION_SCHEMA.ROUTINES + OBJECT_DEFINITION, 4000자 절단 회피). 엔진 무관 컬럼 계약. 파라미터 쿼리에 `ROUTINE_TYPE`(pr[4]) 포함(MySQL 동명 proc+func 파라미터 격리용·MSSQL NULL).
  - `src/modules/tools.py`: `_tool_describe_routine`(=`_safe_ident` 정제 + `_struct_schema_access_error` allowlist/내부스키마 게이트 + `_raw_execute_sql`, 다른 구조화 도구와 동일 신뢰경계, 다중 def_rows 시 ROUTINE_TYPE 로 파라미터 필터) · `_TOOL_HANDLERS["describe_routine"]` · **핵심 `TOOL_DEFINITIONS`(LLM 실노출) 에 도구 정의 추가(4→5)** · `_routine_introspection_redirect`(L2 힌트) + `_tool_execute_sql` 거부 메시지 append · `import re` · **`_safe_ident` 역슬래시(`\`) strip 추가**(§18.8 security 패널 MAJOR — pre-existing MySQL 리터럴 breakout 근본 봉인, 구조화 도구 전반 소급 방어).
  - `src/agent_core.py`: `_derive_step_work`/`_derive_step_reason` 에 describe_routine 케이스 추가(§18.8 qa 패널 MINOR — 런타임 narration fallback 일관성).
- Recurrence sealing: `model limit`(거부 피드백 교정 힌트) → 거부 시 describe_routine 유도 정형화 + capability gap → 전용 구조화 도구. sql_guard/allowlist/RBAC/PII 경계 불변(보안 회귀 0 — test_query_guard/test_sql_trust_boundary/test_mssql_security_boundary 재통과). 신뢰경계 방어선 강화: `_safe_ident` 역슬래시 봉인.
- §18.8 적대 패널(security+backend+qa) 결과: MAJOR 1(백슬래시 인젝션)·MINOR 2(파라미터 교차오염·narration fallback) 전건 **수정 완료**, 나머지 REFUTED(safe/correct). 상세 REV-20260713T140405-describe-routine-tool.
- 검증: `tests/test_describe_routine_tool.py`(신규, 백슬래시·파라미터격리 보강) + 보안 가드 3파일 재통과 + 전체 스위트 RC=0. py_compile clean.
- Cross-ref: feature-0003 `_conv_store.py` `_derive_step_work` narration 라벨(companion, graceful fallback) · FRICTION_LEDGER FR-show-create-routine-blocked · REVIEW REV-20260713T140405-describe-routine-tool · ANCHOR 0002 §1~§3(core/web-ui 분리·모듈 배치) 무충돌.

## CHG-20260713T151500-describe-routine-deploy (배포 완료 기록 + 원장 상태 정합, docs-only)
- Date: 2026-07-13. CHG-20260713T140405 후속 — PR #749 merge(main `6841eba2`) 후 배포 완료.
- 배포: `make deploy-web`(web-a/web-b 무중단 롤링 → 6841eba2, soak 90s 통과) + `docker compose build`(GIT_COMMIT=6841eba2)·`up -d --force-recreate` ask-worker/insight-worker. **4서비스 GIT_COMMIT=6841eba2**(ask-worker/web-a/web-b healthy). **런타임 실증**(ask-worker 컨테이너 Python import): `describe_routine`∈TOOL_DEFINITIONS·`_TOOL_HANDLERS`·`_safe_ident("x\\")=="x"` 전부 확인. web `/healthz` git_commit=6841eba2·mysql_ok·pg_ok.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `fixed:undeployed`→`fixed:deployed:unverified-live` + TASK 체크박스 정합. 라이브 대화 실측(프로시저 정의 요청 재현)은 미수행 → 다음 audit corroboration 재측정 시 `verified`.
- Cross-ref: FRICTION_LEDGER FR-show-create-routine-blocked · REV-20260713T151500-describe-routine-deploy.

## CHG-20260713T171821-readonly-query-shapes (read-only 쿼리 shape 과차단 보정: 최상위 UNION + 읽기전용 SHOW, Critical §12.3, conversation_audit FR-readonly-query-shapes-overblock)
- Date: 2026-07-13. `/_dqa:conversation_audit "동적 쿼리 및 테이블 변경사항 추가 리뷰"` — "여전히 유사한 이슈… '보안 정책상 차단된 SQL'". describe_routine(FR-show-create-routine-blocked)이 봉인 못 한 같은 클래스의 넓은 재발.
- Reason(RC): **L5 — sql_guard SELECT/CTE-only shape 게이트가 read-only 패턴 과차단**. 대상 대화(PG agent_runtime `20260713074503-5cef7aa2`) 차단 = SHOW CREATE TABLE(테이블 DDL 리뷰)·SHOW VARIABLES(config). corroboration **structural**(최근 30일 9 distinct conv·14건: UNION 8·Show 5·parse 12·multi 4). 실질 보안(쓰기·allowlist·금지함수·multi-statement)은 shape 와 무관 — 정확히 read-only 패턴만 넓힘.
- 사용자 승인: **UNION + 읽기전용 SHOW**(AskUserQuestion 2026-07-13). Critical → 승인 후 구현.
- Changes:
  - `src/modules/sql_guard.py`: `_READONLY_SHOW_KINDS`(CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES/STATUS — **PROCEDURE/FUNCTION 제외=describe_routine 담당**) + `_show_kind`/`_show_target_db`/`_validate_readonly_show`. `validate_sql_for_sandbox`: (a) `exp.Show`→read-only 화이트리스트 검증(+대상 `.db` forbidden 차단) (b) `exp.SetOperation`(UNION/INTERSECT/EXCEPT) shape 허용 (c) lock/into 를 **모든 SELECT 분기**(`root.find_all(Select)`)에 적용. 기존 4-part/forbidden-schema/forbidden-function 검사는 이미 find_all 로 union 분기 전수 순회(불변). `collect_schema_refs`: SHOW `.db` 수집(제품 allowlist 강제 경로).
  - `src/modules/tools.py`: `_dialect_correction_hint` 의 stale "최상위 UNION 불가" tip 제거(오정보 방지).
  - `src/modules/sql_guard.py`(§18.8 security 패널 MAJOR 흡수): `_WRITE_NODE_TYPES`+`_find_write_node` — accepted shape 트리 전체(CTE 본체·서브쿼리·union 분기)에서 write/DDL/command 노드 스캔 거부. **데이터 수정 CTE**(`WITH c AS (DELETE/INSERT/UPDATE … RETURNING) SELECT … c`)가 With→Select shape 로 통과하던 pre-existing 잠복(RO GRANT·엔진 미지원 backstop 이나 guard authoritative 원칙)을 봉인. read-only 트리 false-positive 0 실측.
- Recurrence sealing: guard shape 가정 오류 → read-only allowlist 정확 확장 + write-node defense-in-depth. **보안 회귀 0**: UNION 분기별 forbidden-schema/lock/into/금지함수 차단 유지, 비-read-only SHOW(GRANTS/DATABASES/PROCESSLIST)·SHOW forbidden schema·DELETE/DDL/multi-statement/INTO·데이터수정CTE 계속/신규 차단. 계속 차단(의도, F4): multi-statement·parse-fail(별도 RC 이연)·db_id/db_name(MSSQL enum).
- 검증: `tests/test_readonly_query_shapes.py`(신규) + `test_gc_dialect_context.py`(UNION 교정 tip 제거 반영) + 전체 회귀 pytest. §18.8 적대 패널 REV-20260713T171821-readonly-query-shapes.
- Cross-ref: FRICTION_LEDGER FR-readonly-query-shapes-overblock(+ FR-show-create-routine-blocked 후속) · REVIEW REV-20260713T171821 · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260713T173000-readonly-query-shapes-deploy (배포 완료 기록 + 원장 생성, docs-only)
- Date: 2026-07-13. CHG-20260713T171821 후속 — PR #761 merge(main `9892fc3b`) 후 배포 완료.
- 배포: worker 이미지 `docker compose build`(GIT_COMMIT=9892fc3b) + `up -d --force-recreate` ask-worker/insight-worker + `make deploy-web`(web-a/b 무중단 → 9892fc3b, soak 통과). **4서비스 GIT_COMMIT=9892fc3b** running/healthy. **런타임 가드 실증**(ask-worker `import modules.sql_guard`): UNION·SHOW CREATE TABLE·SHOW VARIABLES 허용 / 데이터수정CTE·UNION-agent_memory분기·SHOW GRANTS 차단 확인. web `/healthz`=9892fc3b·mysql_ok·pg_ok.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `FR-readonly-query-shapes-overblock` 엔트리 생성(fixed:deployed:unverified-live) + REPORT cross-ref + TASK 체크박스. 라이브 대화 실측은 다음 audit.
- Cross-ref: FRICTION_LEDGER FR-readonly-query-shapes-overblock · REV-20260713T173000-readonly-query-shapes-deploy.

## CHG-20260713T185846-attach-update-versioned (첨부 파일 갱신: 명시적 갱신요청 → 새 첨부 버전 전달 선호, Major §12.3, conversation_audit FR-attachment-update-pasted-not-versioned)
- Date: 2026-07-13. `/_dqa:conversation_audit "첨부파일 갱신"` — 사용자 지시: assistant 가 개선안 제안 후 명시적 갱신 요청이 있으면 쿼리를 답변으로 붙여넣지 말고 첨부 파일의 새 버전으로 전달하고, 갱신 파일명을 원본과 정합(버전 접미)하게.
- Reason(RC): **L1 프롬프트 (data/config drift + model limit)**. attachment-edit 전달 메커니즘(TASK-0275/0286, 2026-06-15/16 출하)은 이미 존재하나 프롬프트 지침이 (a) "corrected file back"으로 좁게 게이팅 (b) "brand-new SQL → ```sql 무방"([agent_core.py:152](../src/agent_core.py))·일반 SQL 출력 지침과 경쟁 (c) **코드 상수 안에** 있어 운영자 `WebSystemPrompts` global row 가 상수를 통째 대체할 때 프로덕션에서 약해짐. corroboration **structural**(PG core_messages/attachments 90일: text/csv 첨부 갱신요청 34대화 중 assistant 버전 생성 성공 3(~9%) vs ```sql 붙여넣기+버전無 27(~79%); assistant 버전 생성 전 기간 4건뿐; 기능 출하 후에도 7월 이후 7대화 지속 → F3 기각).
- 사용자 승인: **Scope A**(AskUserQuestion 2026-07-13). Major(코어 LLM 경로) → PLAN-APPROVED 후 구현.
- Changes(feature-0002 primary):
  - `src/agent_core.py` — SYSTEM_PROMPT "DELIVERING THE EDITED FILE" 섹션 강화(A1): 명시적 갱신요청(this turn OR earlier) → attachment-edit **필수**, "brand-new SQL" 예외가 편집을 삼키지 않음 명시, `filename` **생략** 유도(시스템 자동 버전명명), source 미첨부 시 재첨부 요청(붙여넣기 fallback 금지).
  - `src/agent_core.py` — `_ATTACHMENT_DELIVERY_DIRECTIVE` 신설 + `compose_system_prompt` `parts` 에 base 뒤 **항상 코드-주입**(A2, `_INJECTION_GUARD_NOTICE` 선례=AUTH-1a). 운영자 global row 가 코드 상수를 대체해도 강화 계약이 프로덕션 도달 → drift 봉인.
- Recurrence sealing: data/config drift → 코드 권위선(항상 주입) + model limit → 프롬프트 계약 정형화. 가드/RBAC/PII/데이터소스 불변(materialize 가드 미변경 — conv/account scope·ext 강제·size cap·text-only 그대로). **보안 회귀 0**.
- 검증: `tests/test_compose_system_prompt.py`(신규 케이스: directive 항상 주입·global override 시에도 존재) + 전체 회귀 pytest. §18.8 적대 패널 REV-20260713T185846-attach-update-versioned.
- Cross-ref: **feature-0003** `_conv_store.py` 파일명 코드-권위 정규화(secondary, CHG-20260713T185846-attach-filename-consistency) · FRICTION_LEDGER FR-attachment-update-pasted-not-versioned · REVIEW REV-20260713T185846 · ANCHOR 0002 §1~§3(core/web-ui 분리·모듈 배치) 무충돌.

## CHG-20260714T031500-attach-update-deploy (배포 완료 기록 + 원장 상태 정합, docs-only)
- Date: 2026-07-14. CHG-20260713T185846-attach-update-versioned 후속 — PR #771 merge(main `ee4f8de6`) 후 배포 완료.
- 배포: `make deploy-web`(web-a/web-b 무중단 롤링 → ee4f8de6, soak 90s 통과, 롤백 0) + `docker compose build`(GIT_COMMIT=ee4f8de6)·`up -d --no-deps --force-recreate` ask-worker/insight-worker. **4서비스 GIT_COMMIT=ee4f8de6**(전부 running/healthy). **런타임 실증**: ask-worker(A1 SYSTEM_PROMPT attachment-edit 강화·brand-new SQL 예외·filename 생략 True + A2 `_ATTACHMENT_DELIVERY_DIRECTIVE` FILE UPDATE REQUESTS True) / web-a(A3 `_next_version_filename('report_v2.csv',3)=='report_v3.csv'` 이중접미 방지·safe_ext×5·base_for_naming×3). web `/healthz` git_commit=ee4f8de6·mysql_ok·pg_ok.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `fixed:undeployed`→`fixed:deployed:unverified-live` + TASK 체크박스 정합. 라이브 대화 실측(갱신요청 대화 붙여넣기 감소·버전 생성 비율 상승)은 다음 audit corroboration 재측정 시 `verified`.
- Cross-ref: FRICTION_LEDGER FR-attachment-update-pasted-not-versioned · REV-20260714T031500-attach-update-deploy.
## CHG-20260714T153113-sysvar-select-guard (MySQL 시스템 변수 읽기 @@ denylist 과차단 해소, Critical §12.3, conversation_audit FR-sysvar-select-denylist-overblock)
- Date: 2026-07-14. `/_dqa:conversation_audit "초기화 쿼리 환경 옵션 검토"` — 사용자 보고: 쿼리 실행 중 "보안 정책상 차단..." 재발.
- Reason(RC): **L5 sql_guard 보조 denylist 가정 오류**. `_DENYLIST_PATTERNS`(MySQL)의 `@@` regex 가 read-only 시스템 변수 SELECT(`SELECT @@lower_case_table_names, @@version`)를 차단. CHG-20260713T171821 로 read-only `SHOW VARIABLES/STATUS`(동일 정보 클래스, 오히려 전체 변수 노출)가 사용자 승인 하에 허용된 뒤라 **태세 불일치 잔재**. 거부 힌트도 "단일 SELECT/CTE 만 허용"이라 오도(해당 쿼리는 단일 SELECT) — assistant 가 SHOW VARIABLES 재시도 없이 OS 기본값 추정으로 대체, 사용자의 "환경 옵션 직접 확인" 명시 요구 좌절.
- corroboration: 30일 차단 시그니처 집계(PG agent_runtime.core_messages) — `denylist:@@` 1건/1대화(2026-07-14, 어제 배포 후 유일한 차단). 빈도 idiosyncratic 이나 **근본이 코드 정본(file:line) confirmed(high) + 태세 불일치 명백 + 재발 경로 확실**(환경 옵션 점검은 초기화 쿼리 리뷰 workflow 의 상시 단계) → 명백한 구조결함 fix-now. Critical → 사용자 승인(AskUserQuestion 2026-07-14 "제거 진행").
- Changes:
  - `src/modules/sql_guard.py`: `_DENYLIST_PATTERNS`(MySQL)에서 `re.compile(r"@@")` 제거 + 사유 주석(read-only SHOW 화이트리스트와 동일 정보 클래스·쓰기는 SET @/:= + shape 게이트가 차단·T-SQL @@ 유지). MySQL 어휘 "골든: 무변경" 헤더 주석은 본 변경으로 무효화되어 문구 정리.
  - `tests/test_readonly_query_shapes.py` §5b: `SELECT @@x`/`@@GLOBAL.x`/`@@sql_mode` 허용 + `SET @@`/`SET @a`/`SELECT @a := 1` 차단 유지 + tsql `SELECT @@VERSION` 차단 유지.
- 보안 회귀 0 근거: (1) 노출 확대 0 — `SHOW VARIABLES/STATUS` 가 이미 전체 시스템 변수를 노출(승인된 태세), `SELECT @@x` 는 그 부분집합. (2) 쓰기/할당 전 경로 불변 — `SET`(shape 게이트: SELECT/CTE/SET_OP/SHOW 외 거부)·`SET @` denylist·`:=` denylist. (3) T-SQL(MSSQL) denylist `@@` 유지 — 메타 열거 차단 태세 불변(test_mssql_security_boundary.py:66 green). (4) 컨테이너 시뮬레이션 + 타깃 테스트 4파일(129 tests) PASS 실측.
- §13.1 동시수정 기록: feature-0002 표준 worktree 를 병렬 세션이 점유(FR-partial-evidence-false-verification, tools.py/agent_core.py) → 본 cycle 은 `ai/claude/feature-0002-sysvar-guard` worktree 로 격리(파일 교집합 0).
- Cross-ref: FRICTION_LEDGER FR-sysvar-select-denylist-overblock(머지·배포 후 docs-only 후속에서 생성) · 선행 CHG-20260713T171821-readonly-query-shapes · REVIEW REV(§18.8 패널, 본 cycle) · ANCHOR 0002 §1~§3 무충돌.
## CHG-20260714T161500-mssql-crossdb-structured-discovery (MSSQL 구조화 발견 도구 DB(catalog) 인지 — Critical §12.3)
- Date: 2026-07-14. **conversation_audit** 진단(FR-mssql-crossdb-structured-discovery). **증상**: SQL Server 제품에서 assistant 가 실제로 존재하는 객체(테이블/컬럼/루틴)를 "검색 결과 없음/빈 구조"로 오판하고 give-up(product 117 대화 20260714065456-d705e0c7 외 다수 — 사용자 "다시, 제대로 검토해주세요" 명시 불만).
- **근본원인(RC-1, L4↔L8 + L1/L2)**: SQL Server 의 `INFORMATION_SCHEMA`/`sys` 카탈로그 뷰는 **DB(catalog)별**이라(MySQL 의 인스턴스-전역 information_schema 와 비대칭), 구조화 발견 도구(`search_tables`/`describe_table`/`describe_schema`/`list_schemas`/`get_sample_rows`/`get_table_indexes`/`get_foreign_keys`/`describe_routine`)가 pin 된 primary DB(`allow_dbs[0]`, SortOrder 첫 DB)의 카탈로그 하나만 조회했다. 제품 데이터는 수십 개 DB(product 117 = `Shop`/`9DRAGONS_ITEM`/`CASHITEMDB`… 30여 개, 전부 allowlist 멤버·freeform 3-part 로 도달 가능)에 분산 → primary 밖 객체는 도구로 발견 불가. `schema_name` 파라미터가 DB 를 스키마로 오인하게 만듦(관측: describe_table 빈-헤더 schema 인자가 대부분 DB명 — Shop/dk_game_release_233/9dragons_community…). 빈 결과에 교정 힌트 부재로 give-up 유발. **삼각측량**: 코드(도구 SQL 스코프) + PG 대화집계(MSSQL 29대화 중 11 ~38% describe_table 빈-헤더, 오늘까지 structural) + **라이브 QA 서버 재현/수정검증**(mssql-web-qa: primary `_INDY_STATISTIC` 에서 `Shop.dbo.T_ItemInfo`(15컬럼)·`L_Item_Buy_Log` 미발견 → `[Shop].INFORMATION_SCHEMA` 3-part 로 발견 확인).
- **봉인(재발경로=capability gap → 도구를 실제 도달 가능하게)**: 구조화 발견 도구를 **DB(catalog) 인지**로 전환. (1) `dialects.py` MSSQLDialect 전 발견 메서드에 `db`(catalog) 파라미터 + `_cat(db)` 3-part 접두(`[db].sys.*`/`[db].INFORMATION_SCHEMA.*`, describe_columns 는 실스키마 미상 시 스키마 필터 생략·테이블명 매칭, routine_definition 은 OBJECT_ID 3-part). base/MySQL dialect 은 `db=""` 무시(information_schema 인스턴스-전역 — 골든 회귀 0). (2) `tools.py`: `_mssql_resolve_catalog`(schema_name↔DB 재해석·`database` 인자·`db.schema` 분해·허용DB 검증·시스템/내부 DB fail-closed), `_mssql_effective_allow_dbs`, `_mssql_resolve_table_schema`, `_mssql_struct_target`, `_mssql_crossdb_hint`(빈결과 L2 교정). `search_tables` 는 대상 DB 미지정 시 **허용 DB 전체 검색**(per-DB graceful, CAP 40·초과 명시) → DB-qualified 반환. describe/schema/sample/indexes/fk/routine/list_schemas catalog-aware. (3) TOOL_DEFINITIONS 에 `database` 파라미터 + 설명. (4) `agent_core.py` `_MSSQL_DIALECT_GUIDANCE` 에 다중 DB 발견 지침(L1 정합). **보안 경계 불변**: 유효 허용 DB(allowlist − 시스템 − 내부)만 도달(freeform 3-part 가 이미 도달하는 범위와 동일 — RO GRANT backstop), 시스템 DB/스키마·agent_memory 차단 유지, `_safe_ident`+allowlist 이중 방어.
- **검증**: 신규 `tests/test_mssql_crossdb_discovery.py`(33 test — dialect 3-part 생성·MySQL 골든 db-무시·resolver 재해석/거부·cross-DB 검색·교정힌트·describe_table 3-part) + 전체 회귀 **1967 passed/2 skipped/0 failed**. 라이브 QA(mssql-web-qa): `describe_columns([Shop],T_ItemInfo)`=15컬럼·`search_tables('Buy',Shop)`=`L_Item_Buy_Log`(사용자 작업 참조 테이블) 발견. **라이브 대화 실측**(실제 리뷰 대화에서 발견 성공)은 배포 후 다음 audit corroboration(MSSQL describe_table 빈-헤더율 감소) 재측정 시 `verified`.
- 위험등급 **Critical**(§12.3 데이터소스 접근 모델) — 사용자 AskUserQuestion 승인(2026-07-14, "완전 DB인지"). §18.8 적대 패널(security+backend+qa) 결과 REVIEW.md 기록.
- Cross-ref: FRICTION_LEDGER `FR-mssql-crossdb-structured-discovery` · REVIEW REV-20260714T161500-mssql-crossdb-discovery · ANCHOR 0002 §1~§3(core LLM tool 경로·모듈 배치) 무충돌.

## CHG-20260714T171000-mssql-crossdb-deploy (배포 완료 기록 + 원장 상태 정합, docs-only)
- Date: 2026-07-14. CHG-20260714T161500-mssql-crossdb-structured-discovery 후속 — PR #790 merge(main `b364e964`) 후 배포 완료.
- 배포: `sudo -E bin/deploy-web.sh`(=deploy-all) 무중단 롤아웃 — web-a/web-b 롤링(git_commit=b364e964, soak 90s 통과·롤백 0) + insight-worker/ask-worker 재빌드(mysql-ai-agent:b364e964) + gateway reconcile(드리프트 0). **4서비스 GIT_COMMIT=b364e964 healthy**. **배포 이미지 baked end-state 실증**(deployed `/app/modules/dialects.py` 직접 로드, mssql-web-qa): `describe_columns([Shop],T_ItemInfo)`=15컬럼 · `routine_definition(schema='',db='Shop')`=1345자(`[Shop].sys.sql_modules` cross-DB) · sys.sql_modules 사용 True.
- 코드 변경 0(docs-only) — FRICTION_LEDGER `fixed:undeployed`→`fixed:deployed:unverified-live` + TASK 체크박스 정합. 라이브 대화 실측(MSSQL 발견 빈결과율 감소)은 다음 audit corroboration 재측정 시 `verified`.
- Cross-ref: FRICTION_LEDGER FR-mssql-crossdb-structured-discovery · REV-20260714T171000-mssql-crossdb-deploy.
## CHG-20260714T063200-partial-evidence-grounding (부분 증거 전수 단정 환각 봉인: 절단 미리보기 epistemics + byte-bounded 확장 + grounding 계약, Major §12.3, conversation_audit FR-partial-evidence-false-verification)
- Date: 2026-07-14. `/_dqa:conversation_audit "첨부파일과 실제 DB 비교 검증"` — 사용자 보고: 첨부파일↔답변 간 환각 극심.
- Reason(RC, 코드+DB+전사 삼각측량 high): 진단 대화 …e6add7f1 에서 ① `execute_sql` 50행 미리보기 절단이 분석 과업에 비가시(안내문이 표시 지침 "CSV 링크 제공"뿐) → 183행 중 gunzlog 전량 미열람 상태로 "전수 검증" 서술 + 첨부에 실재(141행)하는 `TRUNCATE charactermakinglog` 를 "누락" 오진(ground truth sha256 대조 확증) ② 정정 턴도 61행/50행 절단으로 동일 기전 반복 ③ `@@lower_case_table_names` denylist 거부에 교정 힌트 부재 → 문서상 기본값(0) 추측 → 실측(1)과 반대 결론(대소문자 CRITICAL 오진). 재발경로 = model limit → **입력·거부 피드백 정형화(L2) + 표시 캡 구조 보정 + 프롬프트 grounding 계약(L1)**. corroboration: 30d tool 대화 46 중 절단 노출 8(17%) structural surface; '환각' 명시 불만은 90d 내 이 대화가 최초.
- 사용자 승인: **PLAN-APPROVED A+B+C+D 전부 + PR/배포 인가**(AskUserQuestion 2026-07-14). Major(코어 LLM 경로; sql_guard 허용범위·RBAC·PII 불변 → Critical 아님). **rebase 재평가로 D 는 출하 철회**(아래 dead-code 사유).
- Changes(feature-0002):
  - `src/modules/tools.py` — (A) execute_sql 절단 안내문을 epistemic 자기교정형으로 확장(실표시 행수 명시·미열람 행 단정 금지·WHERE/집계/NOT IN 재조회 유도·CSV 모델 비가독·기존 "답변에 전체 표 삽입 금지 + CSV 링크" 표시 계약 유지). `_format_result_sets` 절단 마커에 "미열람·단정 금지" 부기.
  - `src/modules/tools.py` — (B) `_format_result_sets(expand_rows, expand_char_budget, stats)` 확장: 소형 결과는 캡(50) 너머 char-budget(12,000자)·행수 상한(500) 내 전부 표시 — 목록 대조·누락 검증이 미리보기 안에서 종결. 광폭/대형은 기존 캡 유지(컨텍스트 보호 의도 불변). 다른 caller(get_sample_rows 등) 는 expand 미전달로 종전 동작.
  - `src/agent_core.py` — (C) SYSTEM_PROMPT "HANDLING RESULTS — NEVER FABRICATE" 4규칙 추가: PREVIEW-TRUNCATED(미열람 행 단정 금지·재조회)·ABSENCE/COMPLETENESS(완전 근거 없으면 "미확인" 명시)·COMPARING attachment↔DB(양측 조회 선행)·SERVER OPTIONS(문서 기본값 추측 금지 — `@@var`/SHOW VARIABLES 로 실제 값 조회).
  - **~~(D) `_server_variable_redirect`~~ — 출하 철회(정직)**: 애초 계획은 `@@` denylist 거부에 SHOW VARIABLES 유도 힌트였으나, 본 cycle rebase 시점에 병렬 세션 **CHG-20260714T153113-sysvar-select-guard (FR-sysvar-select-denylist-overblock)** 가 MySQL `@@` denylist 를 아예 제거해 `SELECT @@var` 가 sql_guard 를 통과(거부 안 됨) → "거부 시 힌트" 분기가 **dead 경로**. dead code 출하 대신 함수·호출·테스트 삭제. 애초 진단 ③번(@@lower_case_table_names 거부→기본값 추측)은 그 가드 허용 + 본 (C) "실제 값 조회" 계약으로 커버. 회귀 가드 `test_server_variable_redirect_removed`.
- Recurrence sealing: 부분 증거(절단)가 전수 단정의 입력이 되는 경로를 3면에서 봉인 — 구조(B: 소형 결과는 애초에 절단 없음) + 피드백(A: 절단이 자기교정 정보를 동봉) + 계약(C: 부재/전수 단정에 근거 요구·서버 옵션 실측). **보안 회귀 0**: sql_guard 허용범위·denylist·CSV 저장 경로·표시 계약 불변.
- 검증: `tests/test_partial_evidence_grounding.py` 신규 10 PASS(D 테스트 3 제거·회귀가드 1 추가) + 전체 회귀 pytest EXIT=0(feature-0002+0003, mysql-ai-agent 컨테이너). §18.8 적대 패널 → REV-20260714T063200-partial-evidence-grounding.
- Cross-ref: FRICTION_LEDGER FR-partial-evidence-false-verification · **FR-sysvar-select-denylist-overblock**(병렬 세션이 같은 대화 …e6add7f1 의 ③번 @@ 근본을 가드-허용으로 처리 — 본 D 철회의 근거) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260714T210000-attach-review-grounding (첨부-답변 정합성 실데이터 감사 후속: 첨부섹션 grounding 모순 제거 + LLM 오류 분류 2종 확장, Major §12.3)
- Date: 2026-07-14. 계기: 사용자 요청 "실제 파일첨부 대화에서 답변이 첨부 내용과 정합한지" 실데이터 감사(PG `agent_runtime.core_attachments` 411첨부/81대화 + MinIO 대조).
- Reason(RC, 코드+DB+대화 삼각측량): 감사 결과 **컨텍스트-초과 에러 0건**(전 첨부 소형 — text 최대 12.7KB / 대화 누적 최대 58KB ≈ 15K토큰 vs ~200K). 선행 "토큰-초과 대응방안(청킹/RAG/1M모델)"은 현 마찰 미해소(존재하지 않는 문제) — 지적 정직 전환. 실 정합성 실패의 진짜 축: ① ingest/kind 라우팅(최근 대체로 해소) ② 접근·세션창(보안 민감) ③ 환각(파일↔실DB 미검증 단언) ④ 모델 alias/오류 raw 표면화. 자율 우선순위로 ③(모순 제거분)·④ 착수.
- 사용자 승인: **PLAN-APPROVED** (사용자 "우선순위 자율 선정 + 개선 계획 수립 + cycle-finalize 까지 진행", 2026-07-14). Major(코어 LLM 프롬프트·오류 경로; sql_guard 허용범위·RBAC·PII 불변 → Critical 아님).
- Changes(feature-0002):
  - `src/agent_core.py` — (③) `_build_attachment_context_section` 첨부 리뷰 INSTRUCTION 에서 전역 SYSTEM_PROMPT grounding 규칙(L103 "COMPARING an attachment against the live DB: fetch BOTH sides ... Never narrate the current-DB side from assumption or memory", 병합 PR #793 CHG-20260714T063200)과 **직접 모순**되던 억제 문구("answer about it directly and do NOT run execute_sql against your own database unless the user explicitly asks")를 제거. 순수 코드리뷰=DB 불필요 유지, 실 DB 상태 주장=전역 규칙 위임(검증 선행·기억 단정 금지). **전역 grounding 을 중복 신설하지 않고** 첨부 섹션이 이를 무력화하던 latent 모순만 봉인.
  - `src/modules/llm_provider_health.py` — (④) `classify_llm_provider_error` 요청-레벨 400 버킷 2종 신설: `KIND_BAD_MODEL`(`_BAD_MODEL_PAT` — litellm "Invalid model name passed in model=auto/core/edge"·OpenAI model_not_found), `KIND_CONTEXT_LENGTH`(`_CONTEXT_LEN_PAT` — Anthropic "input length and max_tokens exceed context limit"·OpenAI "maximum context length"·Bedrock "input is too long" 통합). raw 400 덤프 → 친절 한국어 메시지(bad_model=관리자 라우팅 설정 안내, context_length=첨부 분량 축소 유도). 판정 순서 cred→bad_model→context_length→auth→throttle→unavail. provider 장애 아님 → `persist_health=False`(`_REQUEST_LEVEL_KINDS`) 로 글로벌 health 미오염(기존 confirmed=False skip 과 이중 안전망).
  - `src/agent_core.py` — (④ caller) ask 루프 오류 핸들러에 `if _restr.get("persist_health", True): record_provider_restricted(...)` 게이트 — 요청-레벨 오류가 글로벌 provider 배너를 오탐 점등하지 않게.
- Recurrence sealing: ③ 첨부 섹션이 전역 grounding 규칙을 무력화하던 모순 제거(파일↔실DB 미검증 단언 경로 봉인, FR-partial-evidence 전역 규칙과 상보). ④ raw provider 400 덤프가 사용자에 노출되던 경로를 분류-치환으로 봉인 + 요청-레벨 오류의 글로벌 health 오염 차단. **보안 회귀 0**: 첨부 datamark 센티널·RBAC·sql_guard·error_tag 비밀 비유출 불변(친절 메시지는 정적 한국어 상수).
- 검증: `tests/test_attach_grounding.py` 신규 5 + `tests/test_llm_provider_health.py` 확장 8 PASS. feature-0002 전체 회귀 로컬 EXIT=0(신규 실패 0). §18.8 적대 패널(security/prompt-injection + backend/correctness) → REV-20260714T210000-attach-review-grounding.
- Cross-ref: **CHG-20260714T063200-partial-evidence-grounding**(③ 전역 규칙 정본 — 본 변경은 그 규칙을 무력화하던 첨부 섹션 모순을 마감, 상보) · ANCHOR 0002 §1~§3 무충돌 · deferred(별도 cycle): ④근본 alias 누출 추적 · ① text-inline 회귀테스트 · ② share-window 접근·세션창.

## CHG-20260714T221500-attach-case-insensitive-grounding (라이브 실측 잔존 false-missing 봉인: 식별자 대소문자 정규화 비교, Major §12.3)
- Date: 2026-07-14. 계기: **라이브 실측(FR-partial-evidence 직접 재현)** — 원 마찰 입력(첨부 2개·conv …e6add7f1·P-119)을 배포본(ask-worker `GIT_COMMIT=244e6bec`, Cycle A grounding)의 실 `agent_core`+실 gunzgame/gunzlog DB 로 격리 재현. 원 증상(`charactermakinglog` "누락 ❌")은 소멸했으나 **잔존 false-missing 1건 발견**: `gunzlog.LoginEventLog`(첨부 162행 활성 `TRUNCATE` 실재)를 "초기화 쿼리에 없는 누락"으로 오판·중복 추가 권장.
- Reason(RC, 코드+첨부+DB 삼각측량): `LoginEventLog` 는 첨부 활성 131개 TRUNCATE 중 **유일한 CamelCase** 테이블(나머지 전부 소문자). 실 DB 는 `lower_case_table_names=1` 로 `logineventlog`(소문자) 반환 → 모델이 DB 소문자명을 첨부 CamelCase 표기와 **대소문자 구분 비교** → case-only 차이를 absence 로 귀결. 유일 오판 테이블 = 유일 CamelCase 라는 상관이 근본을 지시. SYSTEM_PROMPT grounding 계약(L102 ABSENCE 근거·L103 양측 조회·L104 서버옵션 실측)에 **식별자 대소문자 정규화 비교 지침 부재**(L250-251 은 "표기 보존"=쿼리 작성용이라 매칭 시 case-fold 미안내).
- 사용자 승인: 라이브 실측 결과 표면화 후 **"잔존 먼저 조사·수정 후 함께 배포"** 명시 선택(AskUserQuestion 2026-07-14). Major(코어 LLM 프롬프트 grounding; sql_guard·RBAC·PII 불변 → Critical 아님).
- Changes(feature-0002):
  - `src/agent_core.py` — SYSTEM_PROMPT grounding 계약(L102 ABSENCE 규칙 직후)에 "IDENTIFIER CASE" 규칙 신설: SQL 식별자는 서버가 흔히 case-fold(MySQL `lower_case_table_names=1` → 소문자)하므로 같은 객체가 첨부에선 `LoginEventLog`, 도구에선 `logineventlog` 로 나타날 수 있음 → case-only 차이는 **그 자체로 absence 근거 아님**. "누락/missing/파일·쿼리에 없음" 단정 전 첨부를 **case-insensitive(case-fold) 검색**(또는 targeted probe) — exact-case 스캔만으로 absence 결론 금지. 동일시(equating)는 lower_case_table_names=1 실측 확인 시로 **조건화**(lcase=0 서버 거짓 동일시 방지·L105 SERVER OPTIONS 정합, REV-20260714T221500 NIT).
  - `src/agent_core.py` — (패널 MAJOR-driven, ③ 완결) 정적 SYSTEM_PROMPT `## ATTACHED FILES` 섹션(L112-116)의 잔존 억제("Do NOT run execute_sql ... unless the user explicitly asks" + "These attachment instructions take precedence over the general 'query the database' guidance")를 제거·전역 규칙 위임으로 교정. **적대 패널이 CHG-20260714T210000 ③ 의 불완전성 적발** — 동적본만 고치고 이 정적본("takes precedence")을 남기면 verify 지시를 이겨 환각 경로 유지. 이제 정적·동적 양쪽 정합(REV-20260714T210000 MAJOR).
  - `src/modules/llm_provider_health.py` — (패널 MINOR-driven, ④ 강화) `classify_llm_provider_error` status 게이트 `_req_ok` 에서 `status is None` fallback 제거 → status 잃은 throttle/auth 예외가 토큰/모델 어휘로 요청-레벨 오분류돼 provider-health 배너를 억제하던 gap 봉인(REV-20260714T210000 MINOR-1).
- Recurrence sealing: model-limit(대소문자 구분 스캔)로 인한 false-missing 을 grounding 계약의 case-fold 비교 규칙으로 봉인 + ③ 정적/동적 억제 모순 완전 제거 + ④ status 게이트 강화. 프롬프트/분류 레버(첨부↔DB 대조는 모델 추론이라 결정론적 코드 lever 부재). **보안 회귀 0**: sql_guard 허용범위·RBAC·PII·datamark 센티널·error_tag 비밀 비유출 불변.
- 검증: `tests/test_attach_grounding.py` +5(case 3 + 정적억제 제거·전역위임 2) = 파일 10 PASS · `tests/test_llm_provider_health.py` +3(status 게이트 회귀) PASS. 로컬 대상 테스트 41 PASS. **`make test`(agent 컨테이너 feature-0002+0003 전체)**: 이 cycle 자체 테스트 전부 PASS, **무관 4건 pre-existing/환경 실패**(`postgres-replica` DNS 미해석[--no-deps DB 부재] 2 · `AGENT_TIMEOUT_SEC=300` 컨테이너 env vs 테스트 기대 60 2) — 이 cycle changeset 8파일에 해당 코드경로(config/node_analysis/runtime_settings) 무포함 → base 57f21121 byte-동일 실패로 연역 확정, **신규 회귀 0**. §18.8 적대 2렌즈 패널 → REV-20260714T221500 + REV-20260714T210000(MAJOR1·MINOR2 전건 수정).
- Cross-ref: **FR-partial-evidence-false-verification**(라이브 실측 결과 원장 기록 — 본 수정이 그 잔존 false-missing 계열을 봉인) · **CHG-20260714T210000**(같은 cycle·함께 배포) · ANCHOR 0002 §1~§3 무충돌.
## CHG-20260714T233000-attach-table-coverage (라이브 실측 잔존 false-missing 결정론적 코드 봉인: 첨부↔실DB 테이블 커버리지 도구, Major §12.3)
- Date: 2026-07-15. 계기: CHG-20260714T221500(case 프롬프트 레버) 배포 후 **라이브 재-재현(배포본 ee3424c3)** 에서 잔존 확인 — 모델이 case 를 인지하기 시작했으나(diff 에서 `LoginEventLog`↔`logineventlog` 언급) 여전히 요약표에 `LoginEventLog` 를 '누락'으로 오기재 + `lower_case_table_names` 미실측으로 불필요 정규화 제안. 프롬프트 레버는 확률적 완화에 그침(model-limit).
- Reason(RC): 첨부↔DB 테이블 집합 대조가 **모델 추론**으로 수행돼 대소문자 처리가 비결정적. 결정론적 코드 lever 부재가 근본. 사용자 결정 = **"코드로 결정론적 봉인"**(AskUserQuestion 2026-07-14) → 대조를 코드로 이관.
- Changes(feature-0002):
  - `src/modules/tools.py` — 신규 tool **`check_table_coverage(schema_name, attachment_id?)`**: 실 DB 테이블명(정본, `describe_schema_tables`+`_raw_execute_sql`, sql_guard-safe·이름만) 기준으로, 첨부 SQL 이 그 테이블을 **실제 조작(operate-on: TRUNCATE/DELETE FROM/DROP TABLE/INSERT INTO/UPDATE/ALTER/RENAME)** 하는지 대소문자 무시로 분류(`_operated_tables` — 조작 동사 뒤 식별자만; 단순 이름 등장≠조작). `_split_sql_active_comment` 로 블록`/* */`·라인/인라인 `--`·`#` 주석을 분리(주석 조작=의도적 보존 별도 집계). 첨부 `truncated` 플래그 감지 시 '미조작' authoritative 격하. USE/schema-qualifier 로 cross-schema 귀속. 첨부는 deferred import `agent_core._load_attachment_inline_texts()`(ContextVar-aware·순환 회피). 접근은 기존 `_struct_schema_access_error`(내부 스키마·미허용 DB 차단·`_safe_ident`) 재사용. TOOL_DEFINITIONS(LLM 노출 base)+`_TOOL_HANDLERS` 등록.
  - `src/agent_core.py` — SYSTEM_PROMPT 라우팅: 커버리지 비교는 `check_table_coverage` 사용, '조작' 결과를 눈으로 뒤집지 말되 **truncated 경고 시 미확인·원본 재요청**(COMPARING 규칙 직후) + reason/work narration 2곳 분기.
- Recurrence sealing: false-missing 의 핵심 대조를 모델 추론 → **코드 결정론**으로 이관. 대소문자만 다른 조작 대상(첨부 CamelCase ↔ DB 소문자)을 코드가 '조작'으로 정확 집계 → '누락' 오판 소멸. 프롬프트 레버(CHG-20260714T221500)와 상보(도구 호출 유도=프롬프트, 대조 로직=코드). **보안 회귀 0**: 테이블 **이름만** 노출(행/컬럼 데이터 없음)·`_struct_schema_access_error` 게이트 동일·`re.escape` ReDoS-safe·첨부는 현재 run scope 만.
- §18.8 적대 2렌즈 패널이 v1 순진설계 적발(REV-20260714T233000): **B1**(절단 미인지→false-missing authoritative 재도입)·**B2**(블록/인라인/# 주석 누출→false-coverage)·**M1**(이름 아무데나 등장→컬럼/함수 동명 오집계·실누락 은폐) BLOCKING/MAJOR → **조작-동사 추출 + 주석 분리 + 절단 캐비엇 + USE 스키마 귀속**으로 전면 재설계 봉인. 보안 5벡터 REFUTED.
- 검증: `tests/test_check_table_coverage.py` **12 PASS**(seal `LoginEventLog`↔`logineventlog`=조작 집계·미조작 아님 + B1 절단격하·B2 주석분리·M1 컬럼오탐방지·m1 cross-schema 회귀 + 헬퍼). feature-0002 전체 `make test` 신규 회귀 0. §18.8 적대 2렌즈 패널 → REV-20260714T233000-attach-table-coverage(BLOCKING2·MAJOR1·MINOR2 전건 수정).
- Cross-ref: **CHG-20260714T221500**(case 프롬프트 레버 — 본 도구가 그 잔존을 코드로 마감·상보) · **FR-partial-evidence-false-verification**(원장) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260715T104500-friction-ledger-reconcile (docs-only: FR-partial-evidence 원장 상태 arc 정합, 코드 변경 0)
- Date: 2026-07-15. 런타임 코드·테스트 무변경. `docs/improvements/conversation-audit/FRICTION_LEDGER.md` FR-partial-evidence-false-verification 엔트리의 잔존-결함 문구가 "별도 triage 대상"(PR #800 시점)에 머물러, 완료된 후속 봉인 arc(case 프롬프트 레버 CHG-20260714T221500 부분작동 → 결정론 도구 CHG-20260714T233000 배포 `3c8e78df`)를 반영하도록 정합 + status enum(`fixed:deployed:unverified-live`) 불변 명시.
- Recurrence sealing: N/A(문서 정합). 코드 봉인은 CHG-20260714T221500·CHG-20260714T233000, 적대검증은 REV-20260714T221500·REV-20260714T233000.
- 검증: docs-only(§18.4 META 인접) — verify-completion #9 = REV-20260715T104500 [SKIPPED:post-deploy-ledger-reconciliation].
- Cross-ref: FRICTION_LEDGER FR-partial-evidence-false-verification · CHG-20260714T233000 · REV-20260715T104500.
## CHG-20260715T050000-conv-alias-leak-guard (대화 답변 model alias 누출 Bedrock 400 봉인 — deferred ④ 근본, Major §12.3)
- Date: 2026-07-15. 계기: 첨부-답변 정합성 실데이터 감사의 deferred 축 ④(선행 CHG-20260714T210000 이 friendly-message bad_model 로 표면만 완화). 서브에이전트 근본 추적.
- Reason(RC): 대화 답변 경로 `_call_llm` 은 고정 Bedrock 클라이언트로 나가며 model 별 tier-resolve 를 하지 않는다(FR-edge-fallback: 대화는 gemma 강등 금지). `conversation_answer_model()`(shared/model_catalog.py)이 미매핑 alias 를 identity 로 통과시켜, 로컬 게이트웨이 alias(auto/edge/core/code)·미등록 bare 'claude' 가 Bedrock 프록시로 raw 전달 → `Invalid model name passed in model=...` 400(실측: 다수 대화 `LLM 호출 오류` + `__ask_worker__`). 운영 `.env` `OPENAI_MODEL=auto`(config.py:741-742 주석) 가 대표 트리거 — model 미지정 job → OPENAI_MODEL → auto → 400.
- 사용자 승인: **PLAN-APPROVED**(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Major(대화 답변 outbound model 라우팅; 인증·PII·파괴 불변 → Critical 아님). 변경은 **현재 400 나던 케이스만** 바꿈(정상 케이스 무회귀 = 순개선).
- Changes(shared + feature-0002; §13.2.2 F2 shared/ 단일-mutator = 본 cycle):
  - `shared/model_catalog.py` — `conversation_answer_model()`: 기존 `claude-haiku-4→claude-haiku-4-chat` 매핑 유지 + 로컬 alias(`is_local_llm_model`: auto/edge/core/code)·bare 'claude' 를 `_CONVERSATION_ANSWER_DEFAULT_CHAT`(`claude-haiku-4-chat`)로 fail-loud(warn log) 해소. 등록 Claude(claude-sonnet-4)·이미 해소된 chat alias·공백/None 은 identity(무회귀). `logging` import + `_log` 추가.
  - `src/agent_core.py` `_call_llm` — **(적대 패널 CONFIRMED-DEFECT#1 수정)** `budget_model = model if model_supports_thinking(model) else outbound_model` 도입: **max_tokens 산정만** outbound(-chat) 기준(`agent_max_output(claude-haiku-4-chat)=20000`). 초기 fix 는 outbound model 만 해소하고 max_tokens 를 원본(auto→local cap 2048 / bare claude→None) 기준으로 잡아, outbound `-chat` 의 config 고정 thinking budget(5000) 대비 `2048<5000` → Anthropic max_tokens>budget 위반 = **2차 400**(프로덕션 트리거 auto 에서 400→400)이던 결함 봉인. **thinking 주입 게이트는 원본 model 유지**(비-thinking 누출 alias 는 client thinking 미주입 → config 5000 적용, 20000>5000 안전). `model_supports_vision`·`_record_llm_usage` 는 원본 유지. 정상 claude-haiku-4/sonnet-4 경로 budget_model=원본 → 24000/40000 무회귀.
  - **거부한 대안**(중요): `_call_llm` 에 `_get_llm_client(model=...)` tier-resolve 미러링 — 대화 `model=auto` 를 로컬 gemma 게이트웨이(ctx 4096)로 라우팅해 FR-edge-fallback 이 금지한 silent context-truncation 강등을 재도입하므로 채택 안 함. tier-resolve 는 insight/aux 전용, 대화 답변엔 부적합.
- Recurrence sealing: 대화 outbound alias 를 choke-point(`conversation_answer_model`) 단일점에서 등록 chat 모델로 강제 해소 → raw alias 가 Bedrock 으로 새는 경로 봉인. G6 invariant(해소 대상이 litellm model_list 등록명)로 미래 기본모델 변경 시 재-누출 방지. **보안 회귀 0**: 대화는 Claude 유지(gemma 미도달, G5 체인 invariant 불변), 표시/저장/usage 는 원본 model 유지.
- 검증: `tests/test_conversation_answer_no_edge_alias.py` — 기존 `edge→edge` identity(옛 버그 인코딩) → 새 계약 갱신 + G2b(auto/edge/core/code/claude→chat 파라메트릭)·G6(등록명 invariant)·G7(`_call_llm` model='auto'→아웃바운드 chat, 기록은 원본)·**G8**(패널 회귀: 누출 alias 예산이 outbound=chat 기준·`max_tokens>5000`, agent_max_output 스파이) 추가. 파일 15 PASS. 회귀 `test_reasoning_effort.py`(edge→thinking 미주입) 재통과. **컨테이너 `make test`(feature-0002+0003 정본)**: cycle 자체 테스트 전부 PASS, **무관 4건 실패=신규 회귀 0**(실증) — 2 env(`test_runtime_settings::test_missing_snapshot_is_fail_open`·`test_runtime_settings_api::test_get_returns_registry`: base main 격리에서도 동일 실패=환경 pre-existing) + 2 순서오염(`test_routine_dbanalysis::…status_aggregation_failure`·`test_item11_batch8::test_auto_happy_200`: base·worktree **격리 실행에선 PASS**, 전체 스위트에서만 실패 → 테스트 순서 오염, 내 diff 미참조·model 라우팅 무관). §18.8 적대 패널(CONFIRMED-DEFECT#1 수정 + 5축 REFUTED + 2 PLAUSIBLE-RISK 수용) → REV-20260715T050000-conv-alias-leak-guard.
- Cross-ref: **CHG-20260714T210000-attach-review-grounding**(같은 축 ④ friendly-message 계층 — 본 CHG 는 그 근본 봉인) · feature-0007 MODIFY(litellm model_list source-of-truth) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260715T060000-attach-inline-honesty (text-inline 회귀테스트 + 첨부 cap-note 정직화 — deferred ①+②-backend, Minor §12.3)
- Date: 2026-07-15. 계기: 첨부-답정합 실데이터 감사의 deferred ①+②-backend. ② 서브에이전트 진단으로 share-window 는 라이브-ask 첨부 경로 밖(비보안)임을 확인 — 마찰은 프론트 라벨 비대칭(Cycle C)과 backend cap-note.
- Reason(RC): ① text kind 첨부(.sql 등)는 sandbox 아닌 raw content 직접 인라인이 정상 경로(TASK-0124)인데 이를 직접 검증하는 회귀 테스트가 없었다(과거 2026-05 다수 대화가 text SQL 을 "sandbox ingest 대기/실패"로 오인). ② 인라인 개수/크기 상한(_TEXT_INLINE_COUNT_CAP=20 + 64KB/file)을 넘겨 map 에 없는 text 파일에 붙던 노트 `(content unavailable — check MinIO connectivity)` 가 원인을 MinIO 로 오귀속 → 모델이 인프라 장애를 fabrication(관측 대화 20260615061233·FRICTION_LEDGER text-inline count cap).
- 사용자 승인: **PLAN-APPROVED**(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Minor(프롬프트 note 문구 + 회귀 테스트; 비파괴·행동개선).
- Changes(feature-0002):
  - `src/agent_core.py` `_build_attachment_context_section` — 인라인 map 부재 text 파일 노트를 정직화: MinIO 오귀속 제거. **적대 패널(REV-20260715T060000) 3정정 반영** — (a) "size cap" 삭제(크기초과 파일은 truncate 되어 여전히 인라인됨 → 부재 원인은 count cap 또는 판독실패만) (b) `len(map)`을 cap·"N most recent" 로 단정하지 않음(판독실패로 top-20 에 구멍 가능) (c) 회복경로 = **재첨부**(높은 Id → 최신 → 인라인; 선택은 `ORDER BY Id DESC LIMIT` 이라 "파일명 지정 우선순위" 메커니즘 부재 = 거짓약속이었음) (d) `len==0`(인프라 실패 가능성 最高)은 cap 귀속·downplay 금지("cause is not confirmed", 재첨부/재시도). `len>0`("currently N loaded" + "Do NOT claim a specific MinIO/system failure" + 재첨부) vs `len==0` 분기.
  - `tests/test_attach_inline_honesty.py` **신규** — ①(text content 인라인·sandbox 미라우팅·content_len) + ②(len==0/len>0 노트에 MinIO 오귀속 부재·count 보고). `_load_attachment_inline_texts` monkeypatch, DB 없이 fake conn.
- Recurrence sealing: ① 인라인 경로 회귀 봉인(text→sandbox 오라우팅 재발 시 테스트 적색). ② cap-omit 노트의 MinIO 오귀속 제거로 모델의 인프라-장애 fabrication 차단. **보안 회귀 0**: 노트는 code-authored 안내(datamark 밖·주입면 무변경), 접근/스코프 불변.
- 검증: 신규 4 PASS. 다른 테스트 옛 노트 참조 0(grep, CHECK#3 무회귀). feature-0002 전체 회귀 신규 실패 0. §18.8 적대 패널 → REV-20260715T060000-attach-inline-honesty.
- Cross-ref: ② 서브에이전트 진단(share-window 비관여) · Cycle C(②-frontend app.js 라벨 대칭, 후속) · FRICTION_LEDGER text-inline count cap · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260715T082345-schema-name-case-drift (스키마명 서버-실제-case 해소 — A 런타임 canonicalize + grounding, Critical §12.3 데이터소스 바인딩)
- Date: 2026-07-15. 계기: `/_dqa:conversation_audit` "테이블 구조 정합성 검토"(product 97 대화 20260715070720-c202bcf8) — assistant 가 데이터소스 참조 불가·유효 테이블 조회 0행 → 요청 수행 불가.
- Reason(RC, 3-source 삼각측량 high): allowlist `WebProductDatabases.SchemaName` 이 서버 실제 대소문자와 다르게 소문자 저장(서버 `DEV_1_1_1_20`, 63테이블 ↔ 저장 `dev_1_1_1_20`). case-sensitive MySQL(`lower_case_table_names=0`, Linux)에서 구조화 도구가 저장 case 를 literal 로 써 전부 0행/빈결과 → '테이블 없음' 오판·give-up. `_datasource_allow_schemas`(agent_core.py:3153)는 저장 case 를 **의도적 보존**(case-sensitive 대응)이라 코드는 옳으나 저장 데이터가 소문자 → grounding·쿼리 모두 잘못된 case. 이전 casing 프롬프트 lever(모델 소문자화 금지)로는 미해결(데이터 자체가 소문자). 재발경로 = **data/config drift**(allowlist casing ≠ 서버 casing) → 코드 권위선 봉인.
- corroboration: **structural** — allowlist 205 중 85 case mismatch; MySQL 실패확정 클래스(소문자 stored → 서버 대/혼합) ~18행·4 product(94/97/110/121)·다수 MySQL datasource. (MSSQL 67 은 case-insensitive → 무해 거짓양성 기각.)
- 사용자 승인: **Critical → attended AskUserQuestion(2026-07-15) = "A + B(ingestion)"**. A(런타임 resolution seal)+B(web-UI write 정규화).
- Changes(feature-0002 primary):
  - `src/modules/tools.py`:
    - `_mysql_schema_case_map(conn)` — 라이브 `SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA` 로 {소문자→서버실제case} 맵. conn 속성 캐시(dict 만 신뢰 — MagicMock/래퍼 auto-vivify 방어). 대소문자만 다른 동명 복수는 **모호→제외**(fail-safe). 조회 실패=빈 맵(no-op).
    - `_canonical_schema_name` / `_canonicalize_schema_args_mysql` — schema_name 을 서버 실제 case 로(유일 매칭 시만).
    - `execute_tool` — 라우터·비라우터 양 경로에서 handler dispatch **직전** schema_name 정규화(MySQL 한정, MSSQL/비-MySQL no-op). 라우터 경로는 `conn_for → refresh_case → activate` 순.
    - `_DatasourceRouter.refresh_case(label, conn)` — 그 datasource(MySQL) `_allow_schemas`(grounding·DISPLAY allowlist)를 서버 실제 case 로 정규화. idempotent(`_allow_schemas_case_fixed`). MSSQL no-op.
  - `src/agent_core.py` — 멀티-ds primary 연결 직후 `refresh_case(resolve_label(None), db_conn)` → run-start grounding 이 실제 case 노출.
- **보안 불변식(회귀 0)**: 접근 게이트 `_ACTIVE_SCHEMA_ALLOWLIST`(소문자 set)는 canonicalize 전후 판정 동일(`'DEV_1_1_1_20'.lower()=='dev_1_1_1_20'`) — 미허용 스키마 접근 확장 0, 내부(agent_memory)/시스템 스키마 차단 불변. canonicalize 는 이미 authorize 된 스키마의 *표기*만 서버 실제값으로 교정.
- 검증: 신규 `tests/test_schema_name_case_drift.py` 15 PASS(case-map·canonicalize·refresh_case·execute_tool choke·보안불변·MSSQL no-op). feature-0002+0003 전체 **2107 passed, 2 skipped**. §18.8 적대 패널 → REV-20260715T082345-schema-name-case-drift.
- 라이브 실측 필요분(§정직): 코드/유닛은 "정규화 로직 정확·게이트 불변" 증명. "실제 대화 마찰 소멸(describe/search 가 DEV_1_1_1_20 63테이블 반환·give-up 소멸)" 은 배포 후 원 입력 재현분(미수행) → 배포 후 `unverified-live`, 다음 audit corroboration 재측정.
- 적대 패널 후속(REV-20260715T082345): 초기 grounding(primary-only)·poison-cache·Part B(picker) 결함을 §18.8 3렌즈가 적발 → grounding graph 교정(전 datasource·live-fixed skip)·프로브 실패 재시도·**B write-path 정규화 재설계**로 봉인, 재검증 READY-TO-SHIP. 상세 REVIEW.md.
- Cross-ref: **B = feature-0003 admin_products.py write-path 서버-실제-case 정규화**(CHG-20260715T082345-picker-case-preserve, admin.js/수기 입력 무관 chokepoint) · FRICTION_LEDGER FR-schema-name-case-drift · 이전 FR-nl2sql casing 프롬프트 lever(모델 소문자화 금지 — 별개 축) · ANCHOR 0002 §1~§3 무충돌(allowlist 격리 불변식 유지).

## CHG-20260715T234757-probe-throttle-monotonic-flake (LLM 헬스 probe throttle 센티넬 — 갓-부팅 spurious throttle(CI flake + 잠복 버그) 해소)
- Date: 2026-07-15. 계기: 무관 PR #832(프론트 graph)의 CI 를 `test_probe_pings_when_restricted_for_recovery` 가 flaky 하게 red 화. 같은 base #831 green → flaky 확증.
- 근본원인: `probe_provider` throttle `now - _PROBE_STATE["ts"] < min_gap`(now=`time.monotonic()`, min_gap=5|TTL60). 미-probe 센티넬 `ts=0.0` + monotonic()<min_gap(갓-부팅 러너/워커) → `now - 0 < min_gap` → 첫 probe spurious throttle. 러너 uptime 의존 flake + 잠복 프로덕션 버그(첫 restricted-복구 probe 누락).
- Changes(feature-0002):
  - `src/modules/llm_provider_health.py` `probe_provider`: throttle 판정을 `last_ts = float(_PROBE_STATE["ts"]); if last_ts > 0.0 and now - last_ts < min_gap:` 로 — ts=0.0(미-probe)은 monotonic 무관 non-throttle(첫 probe 항상 허용), 실 스탬프 후에만 throttle. 정상 TTL/5s throttle·running 가드·M2 PG throttle·recovery gate 불변.
  - `tests/test_llm_provider_health.py`: `_run_probe` 에 `ts` 파라미터(기본 0.0) 추가 + `import time`; 회귀 잠금 2종(`test_probe_sentinel_ts_zero_not_throttled_regardless_of_monotonic`·`test_probe_recent_ts_within_ttl_throttles`).
- 비변경: 분류기·record/read health·recovery-only gate·thinking budget·RBAC/스키마/마이그레이션 0.
- 검증: `test_llm_provider_health.py` 39 PASS · flake 조건 재현(monotonic=10<60·ts=0.0·restricted → 수정 1 ping, 구 0) · §18.8 [SKIPPED] 적대 자가검토.
- Cross-ref: 원천 flake=무관 PR #832 CI · 선행 CHG(1c1889e4, TASK-20260715-llm-probe-thinking-budget, recovery-only gate 도입) · REV/TEST-20260715T234757-probe-throttle-monotonic-flake · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260722T050006-branch-chain-race (20260722T050006-branch-chain-race — 재답변 브랜치 체이닝 동시성 경합 수정, Major §12.3, PLAN-APPROVED)
- 계기: 사용자 신고 — 재답변 편집 후 보낸 메시지가 화면에서 사라지고 assistant 답변만 쌓임(라이브 대화 20260722015229-79da15cb).
- 근본원인: 브랜치 대화 새 메시지 parent 를 대화-공유 `active_leaf`/`active_display_leaf` 를 매 write 재-read 로 결정 → 동시 재답변 setup/overlap 으로 분기점(M.parent)/타 turn 값 리셋 시 답변이 user 형제로 붙어 active-path 에서 user 누락(read-modify-write race).
- 변경(`src/modules/runtime_backend.py`, +46): thread-local run-cursor API — `branch_run_begin(active)`/`branch_run_end()`/`branch_run_active()`/`branch_chain_get(store)`/`branch_chain_set(store,id)`. store∈{core,disp} 각 id-space 독립.
- 변경(`src/agent_core.py`): `_save_message`(core store) — 브랜치 run(`branch_run_active()`)이면 active_leaf 재-read 대신 run 커서(직전 write id)에 체인(첫 write 만 active_leaf 1회 read)·leaf 전진·커서 갱신, 반환 id 추가. `_run_agent_core` — user write 직전 `branch_run_begin(has_branches)`, teardown(스레드 재사용 stale 정리 지점)에 `branch_run_end()`.
- 변경(`src/modules/memory.py`): `save_memory_message`(display store) — 동일 커서 체인('disp').
- 비변경(회귀 0): 비분기 대화(has_branches=false, `branch_run_active()`=false)는 기존 auto append 경로 byte-identical(feature-0019 ANCHOR INV-1 보존). 엔드포인트 sibling 생성(명시 parent/edit_version>1)·비-run 호출자 무영향. 백엔드/RBAC/스키마/마이그레이션 0.
- Verification: `py_compile` 3파일 · 단위 `tests/test_branch_chain_race.py` 4 PASS · feature-0002 전체 pytest PASS(마운트, 0 fail) · §18.8 subagent 적대 리뷰(REVIEW). POST-DEPLOY 라이브 PB-0008 + 데이터 복구(오염 5행) 예정.
- Files: `src/agent_core.py`, `src/modules/memory.py`, `src/modules/runtime_backend.py`, `tests/test_branch_chain_race.py`, `docs/{TASK,MODIFY,FUNCTION,REPORT,TEST,REVIEW}.md`.
- landing/배포: verify-completion → commit → push → PR/머지=자동 동기화. 배포(deploy-all, 워커 코드 변경)=외부 영향 confirm. 데이터 복구=POST-DEPLOY.

## CHG-20260722T055000-branch-chain-race-postverify (branch-chain-race POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 배포·데이터 복구 실증 기록 + TASK 체크박스 완료. 코드/자산 0.
- 배포: PR #874 → main 5a32a480 → `deploy-web.sh` 전체(web 롤링 soak PASS + insight/ask-worker mysql-ai-agent:5a32a480 healthy + gateway 무드리프트).
- 데이터 복구: 대화 20260722015229-79da15cb 오염 5행 재링크(트랜잭션 UPDATE 1 display + UPDATE 4 core, dry-run 일치) → active-path 에 user 1299 복귀·오염 잔존 0·`/api/history` 에 "로그 흐름만…" 반환 확인.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/TEST.md`.
## CHG-20260722T033854-enum-schema-grounding (ENUM 자동등록 schema-grounding 게이트 — 환각 DB/테이블 차단, Major §12.3)
- 계기: 메타데이터 거버넌스 "ENUM 검토 큐"에 `scope: mysql-kr-an1-auth`(auth) 기준 없는 `dbLog` DB + 없는 `Currency` 테이블이 자동등록. RC=`_enum_autopropose` 가 LLM 추출 (schema,table,column) 을 실제 카탈로그 대조 없이 verbatim 등록(가드는 비어있음만 검사).
- Changes(feature-0002):
  - `src/agent_core.py` `_enum_known_table_index()` 신설: 활성 datasource 의 `table_insight` fact 카탈로그(`cfg.ds_fact_like` 한정)로 알려진 테이블 인덱스 구성(정규화는 kb_glossary 위임). `_enum_autopropose` 루프에 게이트 삽입 — `AGENT_ENUM_SCHEMA_GROUNDING` on 시 카탈로그 부재 (schema,table) 은 `auto_promote_or_queue_enum` 호출 전 skip + `enum_autopropose_skip_ungrounded` 로깅. 카탈로그 미가용/빈 → fail-open.
  - `src/modules/kb_glossary.py`: 순수 함수 `build_known_table_index`(MySQL/MSSQL 계층 전개·대소문자 무시)·`is_enum_grounded`(idx=None→fail-open) + `sweep_ungrounded_enum`(소급 정리 SQL: source='auto' DELETE + feedback pending/auto_promoted→rejected, manual 보존, scope_key 바인딩).
  - `shared/config.py`: `AGENT_ENUM_SCHEMA_GROUNDING`(기본 "1", `__all__` 등록).
  - `scripts/enum_grounding_sweep.py`: 운영자용 소급 정리(dry-run 기본·`--execute`·`--scope`, common scope=active None 정합).
  - `tests/test_kb_enum_grounding.py`(14: 정규화·판정·재현 시나리오·sweep) + `tests/test_enum_autopropose_gate.py`(3: wiring 환각 차단·flag off·fail-open).
- 자가수리(self-heal, 사용자 추가 요청):
  - `src/modules/insight.py` `_enum_self_heal(swept_scopes, *, engine, known_schemas, scanned)` 신설 + `run_insight_cycle` per-(scope,db) `else` 블록 배선(카탈로그 refresh 직후·scope 유효·`_ds_key is not None` 가드 앞→기본 MySQL 커버) + cycle-local dedup `_enum_swept_scopes`. 워커가 방금 로드한 **완전한** 실제 스키마 목록(`_scan_schemas`) 기준 '없는 DB' enum 회수. `scan_started` 게이트 + grounding flag 결합 + MSSQL 제외.
  - `src/modules/kb_glossary.py` `sweep_unknown_schema_enum(conn, scope_key, known_schemas, *, dry_run, confirm_lower)` 신설(schema_name ∉ 실제목록 제거·bare-schema 미터치·source='auto' DELETE·scope 바인딩·case-insensitive·`confirm_lower` catalog-shrink 가드=2회 연속 관측 시에만 삭제).
  - `shared/config.py` `AGENT_ENUM_SELF_HEAL`(기본 "1", `__all__` 등록).
  - `tests/test_enum_self_heal.py`(10) + `sweep_unknown_schema_enum`(4).
- 비변경: manual promote/create 경로·검토 큐 승인/거부(admin_metadata)·enum_dictionary/enum_feedback 스키마·마이그레이션·RBAC·ask-worker(예방 게이트로 이미 커버) 0. label 내용·column-레벨 검증 미포함(범위 밖).
- 검증: 신규 37 PASS(예방 20 + self-heal 계열 17) · 기존 enum/glossary 35 PASS · feature-0002 전체 회귀 신규 실패 0 · ruff clean.
- Cross-ref: REV/TASK/TEST-20260722T033854-enum-schema-grounding · 선행 CHG-20260629-glossary-conv-autoreg(대칭 용어사전 경로)·0039 enum autopropose · cross-ref feature-0003 admin_metadata(검토 큐 UI, 무편집) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260722T033854-enum-self-heal (ENUM 자가수리 — insight-worker 주기 소급 정리, 사용자 추가 요청, Major §12.3)
> 예방 게이트(CHG-20260722T033854-enum-schema-grounding)에 이은 후속(같은 cycle·같은 branch). 사용자 추가 요청 "재발해도 insight/ask-worker 동작에 따라 자가수리". 예방 게이트 commit(87b06a1f) 이후 self-heal 을 별도 change set 으로 추가.
- Changes(feature-0002):
  - `src/modules/insight.py` `_enum_self_heal(swept_scopes, *, mem_conn, engine, known_schemas, scanned)` 신설 + `run_insight_cycle` per-(scope,db) `else` 블록 배선(스캔 성공·scope 유효·`_ds_key is not None` 가드 앞→기본 MySQL 커버) + cycle-local dedup `_enum_swept_scopes`. 워커가 방금 로드한 **완전한** 실제 스키마 목록(`_scan_schemas`=load_known_schemas) 기준 '없는 DB' enum 회수.
  - `src/modules/kb_glossary.py` `sweep_unknown_schema_enum(conn, scope_key, known_schemas, *, dry_run, confirm_lower)` 신설.
  - `shared/config.py` `AGENT_ENUM_SELF_HEAL`(기본 "1", `__all__` 등록).
  - `tests/test_enum_self_heal.py`(13) + `tests/test_kb_enum_grounding.py` sweep_unknown_schema_enum(confirm/빈-schema).
- 안전(§18.8 적대 패널 2 라운드 — 파괴적 자동 DELETE): Round1 BLOCKER1(부분 카탈로그 오삭제)+MAJOR2(매8s·decoupling) → 재설계 Round2 RESOLVED — 완전 실제 스키마 목록 기준·MySQL allowlist·`scan_started` 게이트·grounding flag 결합. 잔여 MINOR-A(권한회수 축소) → catalog-shrink 가드(2회 연속 관측 KV persistence). NIT-C/D 정리.
- 비변경: ask-worker(예방 게이트로 이미 커버)·enum 스키마·마이그레이션·RBAC 0. table-레벨/bare-schema 자동 정리는 미포함(운영자 `scripts/enum_grounding_sweep.py`).
- 검증: 신규 self-heal 계열 17 PASS · feature-0002 전체 회귀 신규 실패 0 · ruff clean.
- Cross-ref: REV/TASK/TEST-20260722T033854-enum-schema-grounding(self-heal 라운드) · 선행 CHG-20260722T033854-enum-schema-grounding(예방 게이트) · insight-worker(§16.3)·0039 enum autopropose · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260724T123600-csv-download-wiring (cross-cut — cycle home = feature-0003)
- conv-audit(csv-inline-no-download): assistant 가 인라인 ```csv``` 블록으로 결과를 제시하며 "다운로드 가능"이라 안내하나 실제 다운로드 수단이 없던 마찰 수정의 백엔드 몫.
- `src/agent_core.py`: `_collapse_large_csv_blocks(answer, csv_paths)` 신설 — 답변 내 대형 ```csv``` 펜스 블록을 `_collapse_large_tables`(MD표) 와 동일하게 값-토큰 매칭으로 저장 CSV 찾아 미리보기+`/api/file` 링크 주입(매칭 실패 시 원문 유지). 초안·redteam 수정·redteam 최종 3경로에 `_collapse_large_tables` 뒤 체인. 기존 `_collapse_large_tables`/`_csv_signatures`/`_match_csv_for_table` 무변경(재사용).
- `src/modules/tools.py`: execute_sql·scratch_sql 툴 출력 가이던스 — "저장 CSV 는 다운로드 버튼으로 자동 제공(링크 직접 생성 불필요)·전체 데이터 붙여넣기 금지" 항상 안내로 정합(기존 "다운로드 링크를 제공하세요" 폐기).
- 프론트(app.js/share.js/styles.css)·docs·검증·배포 정본 = feature-0003 REPORT/MODIFY/TASK/REVIEW/TEST-20260724T123600-csv-download-wiring. 테스트: `tests/test_collapse_csv_block_download.py`(신규 6) + `test_partial_evidence_grounding.py`·`test_scratch.py` 가이던스 문구 정합. 전체 pytest 2303 passed/2 skipped.

## CHG-20260724T054326-timeout-console-sync (LLM upstream 타임아웃 ↔ 관리 콘솔 'AGENT_TIMEOUT_SEC'(live) 요청 단위 동기화 — cross-feature, primary=feature-0002+feature-0007)
> 사용자 요청(feature-0007 saga 6층): "`request_timeout` 또한 `설정 > 실행 타임아웃 > 에이전트/쿼리 실행 타임아웃` 설정값과 동기화되도록 구성". 선행 llm-timeout-align(CHG-20260724T141420, feature-0007)이 gateway `request_timeout` 을 정적 120→300 으로 올렸으나, gateway 는 앱과 **별도 프로세스**라 관리 콘솔에서 값을 바꿔도 정적 config 는 추종하지 못하는 drift 가 남아 있었다.
- 진단(라이브 결정 실험, bedrock-gateway 컨테이너): litellm 은 **요청 body 의 `timeout` 을 per-attempt upstream 타임아웃으로 존중**한다 — 동일 sonnet 호출에 body `timeout=5`→HTTP 408(컷), `timeout=200`→200 @11.7s(성공). 따라서 앱이 요청마다 live 값을 body 에 실으면 gateway 재기동·재배포 없이 즉시 동기화 가능(정적 config 로는 불가능한 실동기화 수단).
- Changes(feature-0002 `src/agent_core.py`):
  - `_call_llm`: extra_body 를 항상 `{"timeout": max(5, int(_rts.get_int("AGENT_TIMEOUT_SEC")))}`(live)로 초기화하고 thinking(budget)/output_config(effort)를 **병합**(이전엔 thinking/effort 있을 때만 extra_body 세팅). 모델·레벨 무관하게 매 호출 live 콘솔 타임아웃이 upstream 으로 전달됨.
  - ask() 진입 client 생성(`OpenAI(timeout=)`): 정적 `config.AGENT_TIMEOUT_SEC`(import 고정) → live `_rts.get_int("AGENT_TIMEOUT_SEC")`. 콘솔 상향 시 client 총-대기가 옛 값에서 조기 컷하던 gap 봉인(body timeout 과 동일 소스 정합).
  - run 예산 `run_timeout_sec`: `AGENT_TIMEOUT_SEC*3`(정적) → `max(5,int(_rts.get_int(...)))*3`(live). 루프 전체 예산도 콘솔 추종.
- Changes(feature-0007 `src/config/litellm_config.yaml`): `request_timeout: 300` 값 무변경 — **주석만** 갱신(앱이 요청마다 live body timeout 전달, config 는 body timeout 미전달 경로의 정적 fallback ceiling 임을 명문화). 정본 CHG = feature-0007 MODIFY.md CHG-20260724T054326-timeout-console-sync.
- Tests(feature-0002): `tests/test_reasoning_effort.py` — extra_body 항상-timeout 대응 위해 `_xb()`(timeout 제외 헬퍼) 도입 + 기존 thinking/effort 정확매칭 회귀 가드 전부 `_xb` 로 유지 + `_call` 에 body timeout 존재/유효(>=5) 상시검증 + 신규 `test_body_timeout_synced_with_console_agent_timeout`(스냅샷 450→body timeout 450, B1 무override 병존)·`test_body_timeout_default_when_no_console_override`. `tests/test_conversation_answer_no_edge_alias.py` G8b — adaptive sonnet '일반'이 이제 extra_body 에 timeout 은 싣되 thinking/output_config 는 미주입임을 확인(누출 가드 유지).
- 비변경: thinking/effort 주입 로직·budget clamp·CC identity·edge-free 라우팅·probe(짧은 8s 헬스 ping 유지)·RBAC·스키마·마이그레이션 0.
- 검증: feature-0002+0003 전체 pytest RC=0(신규 실패 0), 변경 3파일(reasoning_effort/conversation_answer/llm_provider_health) 타겟 전부 PASS. 배포 후 라이브: 콘솔 AGENT_TIMEOUT_SEC 변경→gateway 실행 로그/실제 요청 timeout 추종 확인 예정.
- Rollback: extra_body 를 조건부(thinking/effort 있을 때만) 로 되돌리고 client/run 예산을 정적 `AGENT_TIMEOUT_SEC` 로 복원(단 콘솔↔gateway drift 재발).
- Cross-ref: REV-20260724T054326-timeout-console-sync · feature-0007 MODIFY/REVIEW/TASK-20260724T054326-timeout-console-sync · 선행 CHG-20260724T141420-llm-timeout-align(feature-0007, 정적 300) · shared/config.py AGENT_TIMEOUT_SEC · runtime_settings AGENT_TIMEOUT_SEC(live, apply_mode) · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260724T155534-tool-result-cap-raise (도구 결과 4000자 하드캡 → 대형 설정 backstop; 프로시저 정의 절단 해소 — Major §12.3)
> 계기(사용자, /_dqa:conversation_audit): "assistant 가 추론·내부 도구로 프로시저를 분석할 때 텍스트가 길면 내용이 잘려 한 번에 탐색 불가 — 반환 문자열 길이 제한이 없도록". 마찰 = **FR-procedure-analysis-result-truncated**.
- **근본원인(L2 도구 피드백, 코드 file:line 확정)**: 에이전트 도구 루프가 **모든 도구 결과를 4000자로 하드캡**한 뒤 LLM 에 되먹임 — `agent_core.py` 메인 루프(구 4905)·재추론(rederive) 루프(구 4684)·저장 copy(구 4933). 프로시저 정의 전용 도구 `describe_routine`(CHG-20260713T140405)은 핸들러에서 정의 본문을 **전문 반환**하지만 이 루프 캡이 4000자 초과 본문을 다시 잘라 도구 목적을 무력화 → 나머지를 못 채운 assistant 가 반복 재조회/포기(타임아웃). 실무 프로시저 본문은 4000자 초과가 흔함. **describe_routine 개선의 직접 후속 갭.**
- **결정(사용자, 2026-07-24 AskUserQuestion)**: 세 선택지(정의 도구만 무제한 / 전 도구 무제한 / **전 도구 대형 캡**) 중 **전 도구 대형 캡** — 도구별 분기 없이 큰 유한 캡을 전 도구에 적용. 실무 프로시저는 사실상 무제한(전문 도달)이되, 병리적 대량 결과(넓은 표 대량 행 등)의 컨텍스트/토큰 폭주는 유한 backstop 이 계속 막는다.
- **무엇을**: (1) `shared/config.py` `AGENT_TOOL_RESULT_MAX_CHARS` 신설(env override, 기본 **100000**, `__all__` 등록). (2) `agent_core._cap_tool_result(text)` 헬퍼 신설 — cap 초과 시에만 `... (truncated)` note 부착(FR-partial-evidence epistemic 계약: 미열람분 존재/부재/개수 전수 단정 금지 보존), `cap<=0` 은 무제한 sentinel. (3) 세 캡 지점(메인 루프·rederive 루프·저장 copy)을 헬퍼/상수로 치환. 저장 copy 는 이미 캡된 `tool_result` 를 그대로 저장(PG `agent_runtime.core_messages.content`=text 무제한이라 컬럼 overflow 없음).
- **파일**: `shared/config.py`(상수+`__all__`); `unit/feature-0002-agent-core/src/agent_core.py`(`_cap_tool_result` 헬퍼 + 3지점 치환); `tests/test_tool_result_cap.py`(신규 6건).
- **왜**: 프로시저 등 길고 단일-권위 텍스트를 한 번에 못 봐 분석이 타임아웃되던 마찰의 근본 봉인. describe_routine 이 정의를 전문 반환해도 루프 캡이 재절단하던 모순 제거.
- **호환/안전**: sql_guard·RBAC·datasource 바인딩·PII 경로 **불변**(가드 표면 0 변경 — 순수 컨텍스트 사이징 정책). 절단이 실제 발생하는 경우(캡 초과)엔 기존 epistemic note 보존 → 완전성 오단정 회귀 없음. execute_sql/scratch 는 자체 bounding(미리보기 50행·확장 12000자·셀 100자) 유지 — 이 루프 캡은 그 위의 backstop. 스키마/마이그레이션 변경 0.
- **위험등급**: Major(§12.3 — 코어 LLM 루프·전 도구 결과 경로) → 사용자 결정(scope) 후 구현 + PR/deploy confirm.
- **Rollback**: 세 지점을 `[:4000]`/`> 4000` 하드코딩으로 복원 + 헬퍼·상수·테스트 제거(프로시저 재절단 재발).
- **Cross-ref**: FRICTION_LEDGER FR-procedure-analysis-result-truncated · 선행 FR-show-create-routine-blocked(describe_routine 신설) · FR-partial-evidence-false-verification(절단 epistemic 계약) · REV-20260724T155534-tool-result-cap-raise · ANCHOR 0002 §1~§3 무충돌.
## CHG-20260724T181106-attach-new-directive — 신규 스크립트 첨부 전달 프롬프트 지침 (Major §12.3, cross-ref feature-0003 primary)
- **What**: 사용자가 새로 생성한 스크립트/쿼리를 다운로드 첨부/파일로 요청 시 `attachment-new` 블록으로 전달하라는 지침을 base SYSTEM_PROMPT 섹션 + 코드-권위 `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE`(compose_system_prompt parts 항상 주입)로 추가. base "brand-new SQL → inline ```sql" 규칙(line 158)에 "파일/첨부 요청 시 attachment-new 예외" 명시.
- **Why**: FR-brandnew-script-attachment-delivery-gap(conversation_audit) — 마찰 정본·구현 primary 는 feature-0003(materialize 경로). 본 변경은 그 경로를 활성화하는 프롬프트(cross-ref). AUTH-1a 코드-권위 주입으로 운영자 WebSystemPrompts global row drift 봉인(`_ATTACHMENT_DELIVERY_DIRECTIVE` 선례).
- **Files**: `src/agent_core.py`(SYSTEM_PROMPT 섹션 + `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` + line 158 예외 + compose parts 주입).
- **Verification**: test_attachment_new.py PR1/PR2(drift-proof 주입: 운영자 base 가 지침 제거해도 코드-권위로 살아있음) + 전체 2369 PASS. 라이브=POST-DEPLOY(ask-worker 재빌드 후 실 LLM turn).
- **Cross-ref**: primary REVIEW/MODIFY/TASK/REPORT = feature-0003 CHG/REV-20260724T181106-brandnew-script-attachment · 원장 FRICTION_LEDGER FR-brandnew-script-attachment-delivery-gap.
## CHG-20260724T085937-sonnet-reasoning-budget-guide (test-only — sonnet adaptive 죽은 budget 스펙 제거에 따른 runtime_settings 테스트 갱신, 정본 feature-0003+shared)
- Date: 2026-07-24. shared/runtime_settings.py 가 adaptive(Sonnet 5)의 reasoning_budget/model_thinking_budget 스펙을 제거(effort 로 제어 — 죽은 컨트롤 봉인)함에 따라, feature-0002 소유 `tests/test_runtime_settings.py` 의 sonnet-budget 단정을 갱신한다(코드 로직 변경 0, 테스트만).
- Changes(feature-0002 `tests/test_runtime_settings.py`): sonnet budget/clamp 검증을 haiku(budget 계열, native−1024=62976)로 전환 + adaptive sonnet 은 override 항상 None(스펙 제거)·reasoning_budgets haiku-only 3행·`adaptive_models` 표면화 신규 단정. agent_max_output(①) sonnet 검증은 유지(adaptive 도 live).
- 비변경: agent_core 등 src 코드 0. effort/thinking style 매핑·budget 계열 동작 불변.
- Cross-ref(정본): feature-0003 MODIFY/FUNCTION/REVIEW/TASK-20260724T085937-sonnet-reasoning-budget-guide · shared MODIFY 동일 slug · REVIEW-20260724T085937(cross-ref).

## CHG-20260727T105326-worker-attachment-postprocess — 첨부 후처리 소유자를 ask-worker 로 이전 (Major §12.3)
- **What**: 답변의 `attachment-edit`/`attachment-new` 블록 후처리(첨부 materialize + 블록 strip)를 web 동기 핸들러에서 **ask-worker** 로 이전. 성공 경로의 KV terminal(done)을 후처리 뒤로 지연(`defer_terminal_status`)해 "terminal=모든 것이 끝난 시점" 계약 성립.
- **Why(RC)**: 후처리가 web `/api/ask` 에만 있어 worker 모드 장기 run(라이브 11분) 중 연결 단절 시 미실행 → 첨부 미생성 + raw 블록 노출(라이브 실측: attachment-new emit 됐으나 첨부 0건). 답변 완료 시점을 아는 워커가 올바른 소유자.
- **Files(feature-0002)**: `src/modules/ask.py`(`_postprocess_attachment_blocks`·`_record_attachment_step`·`_finalize_deferred_terminal`·`_warm_attachment_postprocess_deps`·`_slim_result` 키 추가·`_payload_to_kwargs` defer 요청·`_execute_job` 배선), `src/agent_core.py`(`defer_terminal_status` kwarg — 성공 경로 KV done 지연, error/cancel 은 즉시 유지).
- **Files(feature-0003 cross-ref)**: CHG-20260727T105326-web-postprocess-gate — `routers/conversations.py`(후처리 4곳 증거 기반 게이팅·worker 결과 forwarding·`_update_assistant_message_content` bool), `routers/_conv_store.py`(worker 결과 shape 첨부 키).
- **§18.8 반영**: BLOCKER1(web strip 미게이팅 → 블록 삭제 후 저장돼 첨부 영영 미생성·본문 소실) BLOCKER2(KV terminal 이 run_agent 내부라 순서계약 무효) MAJOR3(import 워밍업) MAJOR4(혼합 버전 배포 창 → 증거 기반 게이트 self-heal) MINOR(step 기록 패리티·error 경로 strip·update bool) LOW(terminal 유실 방지·pop 순서).
- **Verification**: pytest 2384 PASS(신규 12) · py_compile · 적대 패널 2라운드(2nd pass 에서 BLOCKER 전부 CLOSED 확인).
- **배포 주의**: web 이 worker 의 후처리를 전제하므로 **워커 포함 전체 스코프 배포**(`make deploy-web`, `--web-only` 금지). 증거 기반 게이트가 혼합 창을 self-heal 하지만 순서는 지킨다.

## CHG-20260727T175800-false-truncation-belief — 허위 절단 인식 봉인 + 루틴 정의 offset 이어읽기 (Major §12.3)
> 계기(사용자, `/_dqa:conversation_audit "문서 내부 조회 프로시저 탐색"`): "'도구 한계' 이슈가 나타나는 부분을 해소하고 싶다(`describe_routine`) — 프로시저 본문을 글자수 제한 없이 조회하도록". 마찰 = **FR-false-truncation-belief**.
- **진단 정직 표기**: 사용자가 지목한 "describe_routine 본문 절단" 은 라이브에서 **미발현**이었다. 대상 대화(`20260727081131-1dc26d26`)의 `describe_routine` 결과 11건은 **전부 절단 없이** 전문 반환(모두 ```` ``` ```` 종료, 최대 6,898자)됐고, PG `core_messages` 전 기간 describe_routine 결과 33건 중 100k 캡 초과 0건·`(truncated)` note 0건이다. 절단은 실제로 없었다.
- **근본원인(L2↔L1, 코드 file:line 확정)**: **어휘 충돌 + 신호 비대칭**. (1) `tools.py` execute_sql/scratch_sql 의 CSV 다운로드 안내문이 **절단 여부와 무관하게 항상** "핵심 **미리보기**(수 행)만" 을 담았고, (2) `agent_core.py` SYSTEM_PROMPT PREVIEW-TRUNCATED 규칙의 트리거가 `"... 행 중 N행만 표시" / "미리보기"` 라 **"미리보기" 단어 단독**으로 발동했다. → 완전한 결과를 절단으로 오인. (3) 게다가 절단 경고는 강한데 완전 표시에는 `(N 행)` 뿐이라 **완전성 확인 신호가 없어** 오귀속이 교정되지 않았다. 라이브 귀결: `execute_sql` 이 프로시저 목록 **181행을 전량 렌더**했는데 assistant 가 "총 181개가 발견되었으나 **도구 프리뷰 한계로 전체 목록 확인이 불가능**합니다"(msg 5619)라며 분석을 3건으로 축소(5611 도 "⚠️ 불완전한 결과"). 재발경로 = `model limit` + 도구 피드백 어휘 설계 결함. **FR-partial-evidence-false-verification(2026-07-14) 수정의 2차효과**(절단 epistemic 계약의 역방향 과발동).
- **결정(사용자, 2026-07-27 AskUserQuestion)**: 전역 캡 무제한화는 **범위에서 제외**. 대신 (a) 허위 절단 봉인만 진행하고 (b) 초대형 정의는 **문자열 offset 으로 여러 번 호출해 전량 도달**하도록 구성.
- **무엇을 (4 lever)**:
  - **A1** `tools.py` — execute_sql·scratch_sql CSV 안내문에서 트리거 어휘 제거("핵심 미리보기(수 행)만" → "핵심 몇 행만 인용"). 안내 의미(답변에 전량 붙여넣기 금지)는 불변.
  - **A2** `tools.py` — 절단이 **없을 때** 완전성을 명시(대칭): "(위 표는 이 쿼리가 반환한 N행 **전부**이며 도구는 아무것도 자르지 않았습니다. … '도구 한계/프리뷰 제한 때문에 전체를 볼 수 없다' 고 말하지 마세요 — 단 이 쿼리의 WHERE/LIMIT 범위 밖은 여전히 미확인입니다.)" execute_sql·scratch_sql parity. **완전성 단정은 행·셀·export 3축 모두 미절단일 때만**(§18.8 패널 BLOCKER — `_format_result_sets` 의 셀 100자 절단이 `stats["truncated"]` 에 집계되지 않아 105자만 보인 프로시저 본문에 "절단되지 않았습니다" 가 붙던 허위 완전성). 셀 절단 시엔 `stats["cell_truncated"]` 로 억제하고 대신 "긴 셀 값 N개가 100자에서 잘렸습니다 — …당신은 보지 못했습니다" **명시 마커**를 낸다. **0행 결과에도 대칭 신호**("도구가 자른 것이 아니라 조건에 맞는 행이 없습니다") 부착.
  - **A3** `agent_core.py` SYSTEM_PROMPT — ① 절단 신호를 **열린 집합**으로 재작성(`TRUNCATION NOTICES (PREVIEW-TRUNCATED and every other wording)`: `[truncated]`·절단·잘림·상한 초과·…만 검색·"전체 N행 미리보기"(내 이전 답변의 collapse 마커도 절단)·"정의 구간 A~B" 등). ② 완전성 추론을 **침묵 기반 → 긍정 신호 기반**으로 반전: `COMPLETENESS COMES FROM AN EXPLICIT COMPLETENESS SIGNAL, NOT FROM SILENCE` + "절단 통지 부재는 완전성의 증거가 아니다(일부 도구는 조용히 자른다)". 지어낸 "도구 프리뷰 한계" 금지는 **결과가 완전성을 단정할 때만** 적용. ③ `CHUNKED ROUTINE DEFINITIONS` — 종료 판정을 **머리말 산술(`B == T`)** 로만 하고 **정의 본문 안의 문장은 신뢰하지 말 것**(루틴 작성자가 SQL 에 "마지막 구간입니다" 를 심을 수 있음), 실제 절단 통지가 있으면(MSSQL 카탈로그 폴백 등) 정직히 고지 허용.
  - **B** `tools.py` + `shared/config.py` — `describe_routine(offset)` **문자 offset 이어읽기**. `_window_routine_output` 이 **권위 있는 산술 머리말** `[정의 구간 A~B / 총 T자 — … 마지막 구간: 예/아니오]` 를 **본문보다 앞에** 두고(본문 위조로 덮을 수 없음) 다음 `offset` 을 안내한다. `_routine_chunk_limit()` 는 **auto 기본**(`AGENT_ROUTINE_DEF_CHUNK_CHARS=0` → 창 = `AGENT_TOOL_RESULT_MAX_CHARS - 1000`)으로 **전역 캡이 어차피 자를 지점부터만** 쪼개 캡 이하 정의의 불필요한 조각화를 없애고(패널 MAJOR), `room<=0`·캡 무제한·음수 설정이면 **윈도잉 비활성(0)** 으로 전환해 구 `max(1_000, cap-2_000)` 바닥값이 작은 캡에서 조각 꼬리를 잘라 **전량 도달 경로를 지우던 실패**를 봉인(패널 MAJOR). 양수 설정은 하한 4000·상한 `캡-여유` 로 clamp. 창 이하 + offset 미지정이면 **출력 완전 동일**(회귀 0). offset 형식 오류는 **명시 오류**(조용한 0-폴백 금지), 범위 초과는 **0 으로 클램프 + 사실 통지**(헤더·권한 안내 보존, "이미 마지막 구간까지 조회" 같은 검증 불가 이력 단정 금지). 조각 꼬리에 "문자 단위 절단이라 코드 블록이 끊길 수 있음 + 미열람 구간 단정 금지" epistemic 유지.
- **파일**: `unit/feature-0002-agent-core/src/modules/tools.py`(A1·A2·B + `_format_result_sets` 셀 절단 stats/마커 + `_routine_offset_error` + TOOL_DEFINITIONS offset 파라미터·description), `unit/feature-0002-agent-core/src/agent_core.py`(A3 SYSTEM_PROMPT 3계약 + §ABSENCE 정합), `shared/config.py`(`AGENT_ROUTINE_DEF_CHUNK_CHARS` 신설 + `__all__`), `tests/test_false_truncation_belief.py`(신규 23건), `tests/test_partial_evidence_grounding.py`(stats 키·프롬프트 라벨 계약 반영 2건).
- **왜**: 도구가 완전한 증거를 줬는데 모델이 "도구 한계"를 지어내 분석을 축소하던 마찰의 근본(어휘 충돌·신호 비대칭) 봉인. 동시에 사용자 요구인 "길이 제한 없는 프로시저 본문 조회"를 **캡 완화가 아닌 페이징**으로 충족(컨텍스트 폭주 backstop 유지).
- **호환/안전**: sql_guard·RBAC·datasource 바인딩·PII·datamark 경계 **전부 불변**(순수 도구 피드백 문구 + 출력 윈도잉). §18.8 security 렌즈가 게이트 순서·SQLi·oracle·secret 5축을 실측 반증(윈도잉은 `_safe_ident`→접근게이트→카탈로그 조회→early-return **전부 뒤**의 최종 return 에만 적용, `agent_memory`/allowlist 밖은 DB 쿼리 실행 0회로 차단). 기존 절단 epistemic 계약(FR-partial-evidence)·`(N 행)` 표기·`_cap_tool_result` 동작 미변경. `offset` 은 선택 파라미터라 기존 호출 형태 100% 호환. 스키마/마이그레이션 0.
- **위험등급**: Major(§12.3 — 코어 LLM 프롬프트 + 도구 결과 피드백 경로) → 사용자 scope 결정(AskUserQuestion 2026-07-27) 후 구현 + §18.8 적대 3렌즈 패널 + PR/deploy confirm.
- **수용된 트레이드오프(by-design)**: 초대형 정의 페이징에 회차 예산이 없다(4MB 루틴 ≈ 42회 호출, 조각이 `role=tool` 히스토리로 이후 턴 재전송). **전량 도달이 사용자 명시 요구**라 강제 상한은 요구 위반 → auto 창(호출 수 ~절반)·머리말의 총 문자수 사전 고지·`AGENT_MAX_STEPS`(128) 유한성·음수 kill-switch 로 완화. 선행 CHG-20260724T155534-tool-result-cap-raise 의 동일 축 수용 전례와 정합.
- **Rollback**: `AGENT_ROUTINE_DEF_CHUNK_CHARS` 를 음수로 두면 윈도잉만 즉시 비활성(재빌드 불필요). 전면 롤백은 A1/A2 문구·A3 계약 3줄·`_window_routine_output`/`_routine_chunk_limit`/`_routine_offset_error`/offset 파라미터·`_format_result_sets` 셀 절단 stats·config 상수·테스트 제거(허위 절단 오귀속 + 허위 완전성 + 초대형 정의 도달 불가 재발).
- **Cross-ref**: FRICTION_LEDGER FR-false-truncation-belief · 선행 FR-partial-evidence-false-verification(절단 epistemic 계약 — 본 변경이 그 과발동을 좁힘) · FR-procedure-analysis-result-truncated(`AGENT_TOOL_RESULT_MAX_CHARS` 100k backstop — 유지) · FR-show-create-routine-blocked(describe_routine 신설) · REV-20260727T175800-false-truncation-belief · ANCHOR 0002 §1~§3 무충돌.

## CHG-20260727T185742-false-truncation-belief-deploy-status — 배포 결과 원장 전이 (doc-only, Minor §12.3)
> 선행 CHG-20260727T175800-false-truncation-belief 의 **배포 후 사실 전사**. 코드 변경 0.
- **무엇을**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md` FR-false-truncation-belief status `triaged` → `fixed:deployed:unverified-live` + 배포/런타임 실측 증거 기록. `TASK.md` 완료 체크리스트의 배포 항목 체크.
- **근거(측정)**: PR #963 merge main `ef24448c` → `make deploy-web` 전체 스코프 무중단 롤아웃(web-a/web-b + ask-worker/insight-worker + gateway reconcile), post-cutover soak 90s 통과, **4서비스 GIT_COMMIT=ef24448c**, web `/healthz`=ef24448c·mysql_ok·pg_ok. 배포본 ask-worker 런타임에서 신규 계약 실측: 열린 절단신호·"침묵 ≠ 완전"·구 `NO MARKER = COMPLETE` 제거·산술 종료조건·auto 창 99,000·250,000자 정의 머리말·캡 통과 후 `offset=` 안내 생존·60,000자 정의 미분할·셀 절단 stats 분리·offset 형식오류 명시.
- **왜 `verified` 가 아닌가**: 라이브 대화 실측(동일 입력 재현으로 assistant 가 없는 도구 한계를 더는 지어내지 않는지)은 미수행. 원장 규약상 status 는 측정으로만 닫힌다(거짓 done 금지).
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REVIEW}.md`
- **위험등급**: Minor(문서 전사 — 런타임 무영향). **Rollback**: status 문자열 원복.
- **Cross-ref**: CHG/TASK/REV-20260727T175800-false-truncation-belief · REV-20260727T185742-false-truncation-belief-deploy-status · PR #963.

## CHG-20260728T104438-false-truncation-belief-live-verified — 라이브 실측 결과 기록 + 원장 verified 전이 (doc-only, Minor §12.3)
> 선행 CHG-20260727T175800-false-truncation-belief 의 **라이브 실측 전사**. 코드 변경 0.
- **무엇을**: `FRICTION_LEDGER.md` FR-false-truncation-belief `fixed:deployed:unverified-live` → **`fixed:deployed:verified`** + 실측 7항 증거 기록. 실측 중 관측된 별개 축을 신규 항목 `FR-false-absence-zero-row-catalog-scope`(status `triaged`, **미수정**)로 분리 기록. `TASK.md` 라이브 실측 항목 체크.
- **실측 설계**: 배포본 `8db72012`(⊃ `ef24448c`)에서 원 대화와 **동일 조건**(product 117 WEB_QA / `mssql-web-qa`, model `claude-haiku-4`) 재현 대화 `20260728012534-a56ec98e` 3 turn + PG `agent_runtime.core_messages` 로 도구 결과 실물 대조.
- **결과**: ① 오귀속 시그니처 3 turn 전부 **0건**(원 시나리오 동형인 대량 완전 결과 turn 포함) ② 신규 신호 라이브 부착(완전성 4·0행 2·셀절단 3·신규 CSV 안내 9, **구 트리거 어휘 0**) ③ §18.8 BLOCKER 수정 실증(20행 완전 + 셀 13개 절단 → 완전성 **억제** + 마커) ④ 진짜 절단(루틴 482건 목록)엔 기존 경고 유지 — 3축 분기 정확 ⑤ 원 불만 대상 `MSP_SELECT_COMMENT_LIST` 2,386자 전문 수신(`END` 완결) ⑥ corroboration distinct_conv 1→0(**분모 23 assistant msg/4 conv 로 작음** — 결정 근거는 ①③④) ⑦ offset 페이징은 실데이터 미도달(정의 35건 max 7,732자 « 창 99,000, `[정의 구간` 0건) → 동작은 배포본 직접 호출로 검증.
- **정직 표기**: turn1 에서 모델이 2부분 명명 메타뷰 0행을 근거로 "프로시저 0개"라는 **허위 부재**를 단정(실제 482건). **본 변경이 유발한 것이 아님을 baseline 대조로 확인**(배포 전 0행 89건 중 부재 단정 5건 — 기존 base rate). 신규 0행 신호가 불충분했을 뿐이며, 수정은 별도 friction 으로 분리해 사람 결정에 맡긴다.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REVIEW}.md`
- **위험등급**: Minor(문서 전사 — 런타임 무영향, 배포 불필요). **Rollback**: status 문자열 원복 + 실측 절 제거.
- **Cross-ref**: CHG/TASK/REV-20260727T175800-false-truncation-belief · CHG-20260727T185742-…-deploy-status · REV-20260728T104438-…-live-verified · FR-false-absence-zero-row-catalog-scope · PR #963.

## CHG-20260728T114459-false-absence-catalog-scope — 0행→허위 부재 봉인: 루틴 열거 도구 + 카탈로그 스코프 인지 (Major §12.3, 보안 경계 완화 포함)
> 계기: FR-false-truncation-belief **라이브 실측(2026-07-28)** 중 관측된 별개 축. 모델이 `masangsoftweb` 에 "저장 프로시저가 전혀 없습니다 / 0개" 라고 단정했으나 ground truth 는 **472 PROCEDURE + 10 FUNCTION = 482건**. 사용자 지시로 근본원인 규명 후 수정(범위 결정: RC-B 포함).
- **근본원인 (ground truth 대조로 확정, 5층)**:
  - **표층**: 모델이 2-part `INFORMATION_SCHEMA.ROUTINES` + `WHERE ROUTINE_CATALOG='masangsoftweb'` 를 실행. product 117 의 접근 DB 를 `(SortOrder, SchemaName)` 로 정렬한 첫 항목이 `_INDY_STATISTIC`(SortOrder 10)이라 연결은 거기 auto-pin 되고, `masangsoftweb` 은 28개 허용 DB 중 하나다 → 그 메타뷰의 `ROUTINE_CATALOG` 는 항상 `_INDY_STATISTIC` 이므로 **정의상 매치 불가 = 구조적 항상 0행**. 0행은 부재가 아니라 스코프 불일치였다.
  - **RC-A(능력 공백)**: 도구 16종에 **루틴을 열거하는 도구가 없다**(`describe_routine` 은 정확한 이름 필요, `search_tables`/`describe_schema` 는 테이블 전용) → "어떤 프로시저가 있나" 에 답하려면 카탈로그 SQL 을 **손으로 써야** 했다.
  - **RC-B(가드가 정본 경로를 닫음)**: MSSQL 정석인 `sys.objects`·`OBJECT_DEFINITION()`·`db_name()` 이 전부 차단(라이브 msg 5675/5677/5679 실증) → 남는 길이 INFORMATION_SCHEMA 뿐.
  - **RC-C(grounding 공백)**: 프롬프트의 2-part/3-part 규칙이 **user table 기준**이라 메타뷰가 카탈로그 스코프라는 사실이 없었다 → 모델은 규칙을 지킨 쿼리를 썼다.
  - **RC-D(피드백 공백)**: 0행에 스코프 진단 없음. 코드베이스에 `_mssql_crossdb_hint` 관용구가 이미 있고 `describe_schema` 빈 결과엔 쓰는데 freeform 경로엔 미적용.
  - **RC-E(인식)**: 0행 → 부재 단정(배포 전 base rate 89건 중 5건 — 기존 실패 모드).
  - **계보**: 프로젝트는 **이미 같은 실패 모드를 봉인**한 적이 있다(`FR-mssql-crossdb-structured-discovery`, 2026-07-14 — "MSSQL 카탈로그 뷰는 DB별이라 pin 된 DB만 보고 다른 DB 객체를 없음으로 오판"). 그 수정이 **구조화 도구에만** 적용됐고 루틴 열거에는 애초에 도구가 없어 freeform 으로 샜다. 본 변경은 그 봉인의 **누락된 형제**다.
- **무엇을 (5 lever)**:
  - **A** 신규 도구 `search_routines` — `search_tables` 의 cross-DB 패턴 그대로(허용 DB 전체 sweep, `database`/`schema_name` 선택, DB-qualified 반환). MSSQL 은 4000자 절단되는 `INFORMATION_SCHEMA.ROUTINE_DEFINITION` 대신 `sys.sql_modules.definition` 으로 **본문까지** 검색(원 사용자 의도 "문서 조회 프로시저 탐색" 은 이름만으론 불가능). 루틴 타입은 CLR/확장/복제필터 포함(`P,PC,X,RF,FN,IF,TF,FS,FT,AF`). `keyword` **선택**(열거 질의 지원). per-DB 실패·상한 포화를 **항상 명시 고지**.
  - **B(보안 경계)** freeform 의 `sys` **전면 차단** → **DB 스코프 카탈로그 뷰 화이트리스트 21종**(`dialects.safe_sys_views()`)만 허용. 서버 스코프(`databases`/`dm_*`/로그인·주체), `synonyms`(linked server·타 DB 명 노출), `guest`/`db_*` 스키마, 메타데이터 **함수**(문자열 리터럴 인자라 AST catalog 게이트가 못 봄)는 계속 차단. 판정은 `sql_guard.collect_schema_object_refs` 의 `(schema, object)` all-or-nothing 대조.
  - **C** MSSQL 프롬프트에 `CATALOG VIEWS ARE PER-DATABASE` — "2-part 메타뷰 + 다른 카탈로그 필터는 **절대** 행을 반환할 수 없다", 빈 카탈로그 결과는 **스코프의 증거이지 존재의 증거가 아님**, 루틴 열거는 `search_routines`. `sys` 경계 문구는 화이트리스트 SSOT(`_safe_sys_views_phrase`)로 생성해 코드↔프롬프트 불일치를 구조적으로 차단.
  - **D** `_catalog_scope_hint` — 카탈로그 메타뷰를 **catalog 자격 없이** 조회하면 **행 수와 무관하게** 현재 pin DB·다른 허용 DB·대체 경로를 제시. AST 기반이라 `[sys].[objects]` 등 인용 변형을 잡고 문자열 리터럴·주석엔 오발화하지 않으며, 이미 3-part 인 쿼리엔 붙지 않는다. 진단이 붙는 결과엔 완전성 단정을 억제.
  - **E** 0행 문구를 "**0행은 '데이터가 없다'의 증거가 아닙니다**" 우선 프레이밍으로. SYSTEM_PROMPT `ZERO ROWS IS NOT ABSENCE` 는 **메타데이터/카탈로그 조회 또는 스코프 경고 동반 시**로 한정(정당한 업무 0행·표적 probe 는 기존 규칙 유지 — 과교정 방지).
- **파일**: `modules/tools.py`(도구 정의·핸들러·가드 판정·스코프 진단·0행 문구), `modules/dialects.py`(`search_routines` MySQL/MSSQL·`safe_sys_views`), `modules/sql_guard.py`(`collect_schema_object_refs`·`_collect_qualified_func_refs_named`·TSQL forbidden 함수/접두), `agent_core.py`(프롬프트 3곳·SSOT 헬퍼·step 서술 2곳), `feature-0003 routers/_conv_store.py`(step 서술 1곳), 테스트 3파일.
- **호환/안전**: MySQL 경로 **동작 무변경**(`safe_sys_views()` 빈 집합, RC-B 코드는 `engine=="mssql" and active_ds` 블록 안). M1 불변식(시스템 DB catalog 차단)·DB allowlist·pin gate·RBAC·`_safe_ident` 불변. 스키마/마이그레이션 0. 신규 도구는 additive.
- **위험등급**: Major(§12.3 — 코어 프롬프트 + 도구 표면 + **보안 경계 완화**) → 사용자 범위 결정 후 §18.8 적대 3렌즈 **2라운드** + PR/deploy confirm.
- **Rollback**: `safe_sys_views()` 를 빈 집합으로 되돌리면 RC-B 만 즉시 원복(나머지 lever 는 독립). 전면 롤백은 신규 도구·프롬프트 3곳·진단 헬퍼·수집기 확장 제거.
- **Cross-ref**: FRICTION_LEDGER FR-false-absence-zero-row-catalog-scope · 선행 FR-mssql-crossdb-structured-discovery(같은 실패 모드의 구조화-도구 판) · FR-false-truncation-belief(본 축을 실측으로 노출) · REV-20260728T114459-false-absence-catalog-scope.

## CHG-20260728T123229-false-absence-live-verified — 라이브 재실측 결과 기록 + 원장 verified 전이 (doc-only, Minor §12.3)
> 선행 CHG-20260728T114459-false-absence-catalog-scope 의 배포 후 사실 전사. 코드 변경 0.
- **무엇을**: `FRICTION_LEDGER.md` FR-false-absence-zero-row-catalog-scope `fixed:undeployed` → **`fixed:deployed:verified`** + 재실측 증거 기록. `TASK.md` 잔여 항목 체크.
- **근거(측정)**: PR #991 merge main `21b67ade` → `make deploy-web` 전체 스코프(4서비스 GIT_COMMIT=21b67ade, soak 통과, `/healthz` ok). 재현 대화 `20260728031510-16927f9b`(동일 product·모델·질문): 수정 전 "프로시저 0개 / 전혀 정의되지 않았습니다"(실제 482건) → 수정 후 "**총 421개**" + `MSP_SELECT_BOARD_CONTENT` 본문 제시. 오귀속·부재 단정 시그니처 **각 0건**. `search_routines` 루프 실사용 확인. 실행 중 MSSQL 연결 단절 시 **실패 고지가 실전 발동**(구 코드였다면 "검색 결과가 없습니다" 로 위장). 배포본 런타임에서 별칭 그림자·`sys.databases`·`master.sys` BLOCK / `sys.objects`·`sys.partitions`·사용자 UDF `dm_` ALLOW 확인.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REVIEW}.md`
- **위험등급**: Minor(문서 전사 — 런타임 무영향, 배포 불필요). **Rollback**: status 문자열 원복.
- **Cross-ref**: CHG/TASK/REV-20260728T114459-false-absence-catalog-scope · REV-20260728T123229-false-absence-live-verified · PR #991.
## CHG-20260728T133431-alias-shadowed-function-namespace — 별칭 그림자 함수 우회: 증명 가능한 축 봉인 + 열거 oracle 차단 (Major §12.3, 보안 경계)
> 계기: FR-false-absence-zero-row-catalog-scope 의 §18.8 패널이 **pre-existing 구멍**으로 분리 기록한 항목(HEAD 동일). 사용자 지시로 후속 수정.
- **근본원인(구조적)**: T-SQL 에서 `X.Y.f()` 는 **자격 함수호출**(`db.schema.func`)과 **UDT/XML 메서드**(`alias.column.method`)가 문법적으로 동일하다. 종전 수집기 3곳은 UDT 과차단을 피하려고 **leading 토큰이 별칭/테이블/CTE 명이면 무조건 면제**했고, 그래서 DB 명을 별칭으로 선언하는 것만으로 catalog allowlist·4-part 게이트가 무력화됐다. 같은 Dot 워커가 두 의미를 겸용하는 것이 문제의 본질이다.
- **실패한 두 차례 시도(정직 기록 — 왜 이 설계로 왔는지)**:
  1. **이름/토큰 목록 하드닝**: 스키마 슬롯 토큰 목록 + UDT 메서드명 목록. 둘 다 공격자에게 0비용이었다 — 스키마를 임의 사용자 스키마로, 함수명을 `value`/`query`/`st*` 로 바꾸면 통과(§18.8 1R BLOCKER, 20건 이상 실증). 동시에 열거식 목록이 정상 spatial/CLR 29건을 과차단하며 **별칭을 DB 로 오보**했다.
  2. **caller 측 "아는 DB 이름" 대조**: 논리가 뒤집혀 있었다 — `hard_forbidden` 은 애초에 면제 대상이 아니므로 `_bad ⊆ allow_set` 이 되어 **이미 허용된 DB 만 막고 미허용 DB 는 전부 통과**(§18.8 2R BLOCKER). 방어가 약한 쪽으로 기울어 정상 사용자만 막혔다.
- **무엇을 (최종 설계 — 각 계층이 증명 가능한 것만 판정)**:
  - **table-source 위치는 절대 면제 금지**(`_in_table_source`): `CROSS/OUTER APPLY db.schema.tvf(...)` 자리에는 UDT 인스턴스 메서드가 **문법적으로 올 수 없다**(서버는 반드시 `database.schema.TVF` 로 해석) → 면제는 모호성 해소가 아니라 **증명적으로 틀린 해석**이었고, 반환값이 **행 집합**이라 유출 규모가 가장 컸다.
  - **체인 정확히 2토큰만 면제** + **체인 전 토큰**을 보호 네임스페이스와 대조 → 4/5-part linked server 및 그 경유 `master`·`agent_memory`·`msdb` 우회 봉인(종전엔 head 만 검사해 중간 토큰이 무방비).
  - **미지 AST 노드 fail-closed**(`_UNKNOWN_NS` 센티널 + `Paren` 재귀): `(master.dbo).fnLeak()` 은 종전에 namespace 를 못 뽑아 **무판정 통과**였다. 이제 어떤 allowlist 에도 없는 센티널이 들어가 차단된다.
  - **존재 열거 oracle 차단**(`tools._sql_error_message`): 모호 경로로 서버까지 도달한 쿼리의 오류는 원문을 노출하지 않는다. `Msg 916`(DB 접근 불가) ↔ `Msg 4121`(함수 없음) 차이로 **allowlist 밖 DB·객체 존재를 무제한 열거**할 수 있었다(적대 검증이 "전제조건 0 즉시 착취" 로 지목). 모호 경로가 **아닌** 정상 쿼리의 오류는 자기교정에 필요하므로 원문 유지.
  - **오보 제거**: 차단 토큰이 이 문장의 테이블 별칭이면 "허용되지 않은 DB" 대신 별칭 충돌 사실과 해소법을 안내.
- **의도적으로 깨지 않은 계약**: `test_regate7_udt_method_not_overblocked` 는 re-gate(7차)가 **MAJOR 로 못박은 제품 계약**("UDT/CLR/spatial 인스턴스 메서드를 3-part 함수로 오판·차단하지 않는다")이다. 면제를 통째로 제거하면 이 계약이 깨지고, CLR 사용자 정의 타입의 메서드명은 **임의 사용자 코드라 열거가 원리적으로 불가**해 화이트리스트로도 복구할 수 없다. 따라서 계약을 유지했다.
- **미해결 잔여(정직 — 원장 기록)**: **스칼라 위치**의 `alias.col.method()` ↔ `db.schema.func()` 모호성은 SQL 텍스트만으로 해소 불가라 남는다(`SELECT hrdb.dbo.value('a','int') FROM dbo.Orders hrdb`). 다만 **데이터 접근의 권위적 경계는 앱 가드가 아니라 per-DB USER/GRANT** 이며, `bin/datasource-mssql-ro-bootstrap.sql` 이 ① **단일 TARGET_DB 에만** USER 생성 ② `db_datareader` 명시적 제거 ③ 허용 스키마에만 `GRANT SELECT`(EXECUTE 미부여) 로 구성되어 **미허용 DB 에는 로그인 principal 자체가 없다**. 즉 잔여의 데이터 유출 경로는 부트스트랩 준수 하에서 닫혀 있고, 정보 채널(열거 oracle)은 위에서 닫았다. **의존성 명시**: 이 결론은 부트스트랩 준수를 전제한다 — datasource 추가 시 해당 스크립트로만 프로비저닝해야 하고, 수동으로 `db_datareader`/전역 USER 를 부여하면 잔여가 실착취로 승격된다.
- **파일**: `modules/sql_guard.py`(`_in_table_source`·`_alias_exempt` 재설계·`_UNKNOWN_NS`·`Paren` 처리·`collect_alias_shadowed_heads`·`collect_table_alias_names`), `modules/tools.py`(별칭 인지 차단 메시지·`_sql_error_message`), `tests/test_false_absence_catalog_scope.py`(회귀 가드를 **유효 T-SQL exploit 형상**으로 — 종전 2회는 실패 변종(무효 T-SQL)을 assert 해 봉인을 오인증했다).
- **호환/안전**: MySQL 경로 무영향. M1·DB allowlist·`sys` 화이트리스트·서버 스코프 뷰·메타데이터 함수·TVF piggyback·`sys` 별칭 그림자 전부 불변(적대 검증 17건 전수 재측정). re-gate(3차) 4-part 계약·re-gate(7차) UDT 계약 both PASS. 스키마/마이그레이션 0.
- **위험등급**: Major(§12.3 — freeform SQL 보안 게이트) → §18.8 적대 security **2라운드** + PR/deploy confirm.
- **Rollback**: `_alias_exempt` 를 종전 무조건 면제로, `_sql_error_message` 를 원문 반환으로 되돌림(단 우회·oracle 재개통).
- **Cross-ref**: FRICTION_LEDGER FR-false-absence-zero-row-catalog-scope 후속 triage · CHG-20260728T114459-false-absence-catalog-scope · REV-20260728T133431-alias-shadowed-function-namespace · `bin/datasource-mssql-ro-bootstrap.sql`(권위적 경계).
## CHG-20260728T124500-llm-usage-target-scope (llm_usage.target_scope — 사용 기록 데이터소스 귀속 근본 해소)

TASK-20260728T124500-llm-usage-target-scope. branch `ai/claude/feature-0002-llm-usage-target-scope`.

- `alembic/versions/20260728_0047_llm_usage_target_scope.py` **신규** — `agent_runtime.llm_usage`
  에 `target_scope VARCHAR(96)` nullable 추가(`ADD COLUMN IF NOT EXISTS`, 멱등).
  소급 백필 **안 함**(과거 행의 정확한 스코프는 복원 불가 — 추측 백필은 잘못된 귀속 생성).
  `MAX_MIGRATION.txt` 갱신 · `src/scripts/agent_runtime_schema.sql` parity 반영.
- `src/modules/llm.py`
  - `_record_llm_usage(..., target_scope=None)` — 명시 인자 우선, 미전달 시
    `cfg.get_active_datasource()`(ContextVar) 폴백. 96자 클립.
  - INSERT 폴백을 **4단 사다리**(target_scope → step_gap → latency+target → latency)로 재구성.
    종전 3중 중첩 try 를 후보 리스트 루프로 평탄화 — 단계 추가 시 중첩이 늘지 않는다.
    공통 8컬럼 순서·인덱스는 계측 회귀 테스트 계약대로 보존.
  - `llm_schema_insight` · `llm_table_insight` · `llm_node_analysis` · `llm_product_classify` ·
    `llm_cluster_label` 에 keyword-only `scope_key` 추가 → `_record_llm_usage` 로 전달.
    **프롬프트 payload 는 건드리지 않았다** — 모델 입력·semantic_cluster 캐시 키 무영향(§12.3 2차-효과).
- `src/modules/node_analysis.py` — 병렬 `_run_llm` 에서 `scope_key=w.get("scope_key")` 전달.
- `src/modules/semantic_cluster.py` — 직렬·병렬 라벨 호출 모두 `scope_key=datasource_key` 전달.
- `src/modules/product_classify.py` — `scope_key=scope` 전달(`target` 은 표시용 ds 라벨과 별개).
  → 이 3곳은 **스레드 경계**라 ContextVar 가 전파되지 않아 명시 전달이 필수다.
- `unit/feature-0003-agent-web-ui/src/routers/admin_usage.py`
  - 집계 질의가 `COALESCE(u.target_scope,'')` 를 SELECT·GROUP BY. **컬럼 부재 시** rollback 후
    리터럴 `''` 로 같은 인덱스를 채우는 폴백 SQL 재조회(ai_ops `_query_activity` 패턴과 동형).
  - fold 키 `(task, target, actor)` → `(task, target, actor, scope)` — 같은 객체라도 데이터소스가
    다르면 별 행(이 컬럼의 존재 이유). legacy NULL 끼리는 종전대로 하나로 묶인다.
  - 기록된 scope 가 있으면 **역해소를 건너뛴다**(정확한 값을 추정으로 덮지 않음).
    응답에 `scope_source`(`"recorded"` | `None`) 추가 — 기록/추정 구분 관측용.
- 테스트: `test_usage_records_system.py` R1~R4 신규(기록값 우선·legacy 역해소·데이터소스별 행 분리·
  컬럼 부재 폴백) · `test_llm_usage_record.py` 0047 3케이스(명시·ContextVar·96 클립) +
  꼬리 인덱스 계약 갱신 · `test_ai_ops.py` 사다리 단수/인덱스 정합 ·
  테스트 더블 arity 7건 확장(`lambda payload` → `**_kw` 수용).

검증: pytest **2,719 PASS / 2 skipped** · ruff clean · `migrate-lint` expand-safe PASS.
배포 순서 안전(expand-only): 구 코드 INSERT·신 코드 컬럼부재 INSERT·신 웹 컬럼부재 SELECT 모두
자가치유. RBAC·인증 변경 0.

## CHG-20260728T124500-llm-usage-target-scope-postverify (0047 POST-DEPLOY 라이브 실증 종결 — docs-only)

TASK-20260728T124500-llm-usage-target-scope. branch `ai/claude/feature-0002-llm-usage-target-scope-verify`.
코드 변경 없음 — 배포본 `754263ab` 실측 결과를 정본에 반영.

- `docs/test-runs.d/20260728T124500-llm-usage-target-scope.md` — verdict PENDING → **PASS** +
  POST-DEPLOY 절 추가(마이그 적용 · 계측 e2e 양 경로 · API `scope_source`/행 분리 · 원장 위생 ·
  채움률 한계 정직 표기).
- `docs/REPORT.md` — 본 cycle 스냅샷 + POST-DEPLOY 결과.
- `docs/TASK.md` — POST-DEPLOY 체크박스 종결.

## CHG-20260728T150510-alias-shadow-server-resolution-verified — 잔여 착취 불가 확정 + 오류 원문 은폐 철회 (Minor §12.3)
> 선행 CHG-20260728T133431-alias-shadowed-function-namespace 의 잔여를 **라이브 실증으로 확정**. 사용자 결정: "라이브 해석 확인 우선" → 결과 반영.
- **실증(QA SQL Server 2017 / 14.0.3238.1 Web Edition, datasource `mssql-web-qa` / `masangsoftweb`)**:
  - ① 별칭 = **미존재** DB명 → `Msg 207 Invalid column name 'dbo'`
  - ② 별칭 = **실존** DB명(`Shop`·`Web_SR`) → `Msg 207 Invalid column name 'dbo'` — **①과 완전히 동일**
  - ③ 별칭 없음(동일 3-part) → `Msg 4121 Cannot find either column … or the user-defined function "zzz_notadb.dbo.whatever"`
  → SQL Server 는 `alias.col.method()` 를 **별칭 우선(컬럼)** 으로 해석한다. 테이블을 DB 명으로 별칭 지어 cross-DB 함수를 부르는 것이 **불가능**하고(잔여 착취 불가), 오류 문구가 **DB 존재 여부에 불변**이라 열거 oracle 도 성립하지 않는다.
- **무엇을**: 위 oracle 을 막으려 넣었던 `tools._sql_error_message`(모호 경로 서버 오류 원문 은폐)를 **철회**하고 원문 반환으로 되돌렸다. 근거가 반증된 방어이며, 유지하면 `Invalid column name 'dbo'` 처럼 **모델의 자기교정에 필요한 정보만** 가리는 순손실이다. 철회 근거는 코드 주석에 프로브 결과와 함께 남겨 재도입을 막고, 테스트가 그 주석·헬퍼 부재를 지킨다.
- **유지**: APPLY(table-source)·4/5-part·`Paren`/미지 노드 봉인은 그대로 — 그 위치들은 컬럼 해석이 **문법적으로 불가**해 서버가 반드시 `database.schema.함수/TVF` 로 해석하므로(프로브 ③ 경로) 게이트 판정이 서버 동작과 일치한다.
- **판단 정정**: 적대 검증 1R BLOCKER-1 은 **게이트 레벨 ALLOW 만** 근거로 한 판정이었고 서버 동작을 검증하지 않았다. 나 역시 검증 수단이 없어 "위험한 쪽으로 가정" 해 받아들였다. 이 실증이 그 전제를 반증한다 — 보안 판정에서 **가정을 실측으로 대체한 사례**로 기록한다.
- **파일**: `modules/tools.py`(은폐 철회 + 근거 주석), `tests/test_false_absence_catalog_scope.py`(문서화 가드로 교체), `docs/{FUNCTION,TASK}.md`, FRICTION_LEDGER.
- **위험등급**: Minor(정보 노출 **축소가 아니라 복원** — 실증으로 무해 확인). **Rollback**: 은폐 헬퍼 재도입(단 근거 없음).
- **Cross-ref**: CHG/REV-20260728T133431-alias-shadowed-function-namespace · REV-20260728T150510-alias-shadow-server-resolution-verified · FRICTION_LEDGER FR-false-absence-zero-row-catalog-scope.

## CHG-20260728T163000-graph-cypher-volume — 그래프 sync cypher 호출량 감축 (Major §12.3)
> feature-0026 계측이 지목한 최상위 PG 비용(`ag_catalog.cypher` 누적 32,072초 / 696만 호출)의 귀속을 실측하고 지배 항목 2개를 제거.
- **측정(라이브, 2026-07-28)**: 전량 sync 1회 = cypher **158,544 회 / PG 실행 867초**(wall 1,148초의 75%). `pg_stat_activity` 샘플링 프로파일에서 루틴 엣지 연산이 지배(74 샘플 중 62). 전량 sync 는 매일 04:17 cron.
- **W1 정점 중복 MERGE 제거**: Schema 정점이 테이블·루틴마다 재-MERGE 됐다(rag 16,367 + routines 23,053 → distinct ~370). 소속 Table 정점도 컬럼마다(3,135 → 389), 루틴 참조 앵커도 참조마다(28,034 → 7,331) 재-MERGE. feature-0029 의 anchor 캐시를 `sync_table`/`sync_column`/`sync_routine` 으로 확장하고 4단계가 **공유**한다.
  - 마크에 **속성을 포함**(`_vmark`) — 단계마다 Table 에 싣는 속성이 달라(rag=클러스터, tables=description, columns/routine=이름) 키만으로 dedup 하면 먼저 실행된 단계가 뒤 단계의 속성 투영을 영구히 삼킨다. 같은 fqn 을 다르게 분해하는 실제 충돌(`a.b.c` → columns 는 table='b.c', routine 앵커는 table='c')을 테스트로 잠갔다.
  - pending/committed 2단 규약은 feature-0029 그대로. 배치 커밋 실패(`_tick`)·step 롤백(`_run_step`) 양쪽에서 `anchor_cache_reset` — 확정 마크를 남기면 정점이 실제로 사라진 뒤 후속 MERGE 가 생략돼 `_merge_edge` 가 조용히 0행(엣지 소실)이 된다.
- **W2 ROUTINE_USES 조건부 재작성**: routine 마다 참조 엣지를 전량 DELETE 후 재-MERGE 했다(DELETE 23,053 + 엣지 MERGE 28,034 = **전체의 32%**). 실제로 참조가 바뀌는 routine 은 하루 수백 건. `routine_refs_signature`(fqn·kind·cross 정규화 sha1)를 Routine 정점 `refs_sig` 속성에 두고, step 진입 시 **cypher 1회로 전량 선조회**(라이브 23,057 행 / 3.2ms) → 서명 일치 시 재작성 생략.
  - 서명 SET 은 엣지 재작성 **뒤**에 별도로 기록한다. 정점 MERGE 에 함께 실으면 autocommit(비-owned) 모드에서 서명이 엣지보다 **먼저 커밋**돼 '서명은 최신, 엣지는 불완전'이 영구 고착된다(다음 sync 가 skip → 자가치유 상실). 비용은 참조가 바뀐 routine 1건당 1회.
  - 서명 부재(신규·배포 직후)·선조회 실패는 miss → 전량 재작성(종전 동작)으로 graceful.
- **§18.8 적대 패널 2렌즈가 잡은 결함 8건 흡수** (초안은 **최종 그래프 상태가 종전과 달라지는** 결함을 포함하고 있었다 — 초안 문서의 "불변: 그래프 최종 상태 동일" 주장은 그 시점엔 거짓이었고, 아래 수정으로 비로소 참이 되었다):
  - **MAJOR-1 (실행 입증)**: 정점 key `scope:schema.name()` 에 routine_type 이 없는데 SSOT 유일키는 (scope, schema, name, **type**) 이다 — MySQL 동명 FUNCTION/PROCEDURE 가 한 정점을 공유한다. `sig_cache` 는 step 진입 1회 스냅샷이라 두 번째 행이 stale 항목과 일치해 **재작성을 건너뛰고 첫 행의 엣지를 최종 상태로 남겼다**(종전은 마지막 행 우선). 게다가 sync 마다 승자가 뒤바뀌는 **영구 flip-flop**. → `_cache_once(cache, ("ROUTINE_REFS", rkey))` 첫 방문 게이트로 종전 semantics 복원.
  - **MAJOR-2**: 서명 SET 예외를 삼키면 PostgreSQL 이 tx 를 aborted 로 둔 채 `_sync_row_guard` 가 `RELEASE SAVEPOINT` 실패까지 삼키고 **성공(True)** 을 반환 → 다음 step 커밋이 조용히 ROLLBACK 으로 수렴해 **최대 500행 소실 + `ok:true` + 워터마크 전진**. 이 문이 routine 행의 마지막 문이라 오류를 드러낼 후속 문이 없다는 게 핵심. → 삼키지 않고 전파(행 SAVEPOINT 롤백 + errors 집계).
  - **B3/MAJOR-3**: 서명만 보면 `--full` 이 문서상 보장하던 **무조건 재조정**이 사라져, refs 변경을 동반하지 않은 엣지 소실(`_merge_edge` 는 끝점 정점 부재 시 오류 없이 0행)이 영구 고착되고 운영 탈출구가 없었다. → 선조회에 **실제 ROUTINE_USES 차수**(cypher 1회, 라이브 19,870행/74ms)를 추가해 서명이 같아도 차수가 기대치와 다르면 재작성. 안전망을 O(1) 로 복원하면서 전량 재작성 51,087회는 되살리지 않는다.
  - **M3**: autocommit(비-owned) 경로에서 DELETE 커밋 후 엣지 MERGE 중간 실패 시 정점에 **직전 서명이 남아** 있고, 참조 미변경 재작성이었다면 그 값이 현재 서명과 같아 이후 모든 sync 가 skip → 부분 엣지 영구 고착. → 재작성 진입 전 `REMOVE r.refs_sig` 선행(순서: REMOVE → DELETE → 엣지 MERGE → SET).
  - **M1 (교차 feature 회귀)**: 2열 선조회의 튜플 언패킹이 1-튜플을 돌려주는 하네스에서 `ValueError` → rollback → `feature-0016 test_metadata_graph_load_spread` 가 **실제로 깨졌다**(HEAD 1건 → 변경 후 2건). CI 게이트는 feature-0016 을 돌리지 않아 미검출. → 인덱스 기반 방어적 판독으로 수정, 해당 테스트 복구 확인.
  - **M2**: 선조회 실패가 완전 무음이라 최적화가 영구 0이 돼도 신호가 없었다. → `_err_samples` 기록.
  - **MINOR-1**: 중복 fqn 에서 엣지 루프는 마지막이 이기는데 서명은 정렬만 해 순서 무관 → 최종 엣지가 다른데 서명이 같아지는 경우 존재. → 서명도 fqn 기준 last-wins 로 접은 뒤 정렬.
  - **MINOR-2 / 실패지점 이동**: 선조회에 scope 필터 추가(전량 덤프 금지 규약), `routine_refs_signature` 를 JSON 문자열·비-dict 원소에 방어적으로 — 이 함수는 정점 MERGE **이전**에 호출되므로 여기서 raise 하면 종전에는 만들어지던 Routine 정점·HAS_ROUTINE 까지 잃는다.
- **테스트 강화 (QA 패널: 초안 28 변이 중 17 생존)**: 초안은 리프 함수만 문자열 매칭해 **`sync_graph` 배선이 0% 검증**이었고, fake 커서의 `fetchall` 이 항상 빈 리스트라 **선조회 루프가 한 번도 실행되지 않아** 쓰기/읽기 속성명 커플링이 안 잠겼다(prefix 매칭이라 `refs_sig2` 로 바꿔도 통과 — `psycopg.Cursor.__slots__` 선례와 같은 '라이브에서 100% 무효인데 초록' 결함면). → `sync_graph` 를 끝까지 구동하는 harness(`_SyncCur`/`_SyncConn`, `__slots__` 로 속성 부착 금지) 추가, 속성명은 정규식으로 뽑아 **동일성** 검증, 롤백된 행이 캐시를 오염시키지 않는지 end-to-end 확인. 최종 **31건**.
- **역검증**: 초안 4축 + 패널 지적 변이 12종을 각각 되돌려 해당 테스트가 실패함을 확인(생존 0). 첫 시도의 layering 테스트는 캐시 미보호 지점을 찔러 회귀를 못 잡았고, 역검증이 그 결함을 드러내 실제 충돌 형상으로 교체했다.
- **파일**: `modules/metadata_graph.py`, `tests/test_graph_cypher_volume.py`(신규 31건), `docs/{FUNCTION,TASK}.md`.
- **위험등급**: Major(그래프 쓰기 경로 · 잘못되면 엣지 조용한 소실). **Rollback**: 커밋 revert — 스키마 변경 없음, `refs_sig` 속성은 잔존해도 무해(다음 sync 가 재작성).
- **Cross-ref**: feature-0029 churn-e(anchor 캐시 원형 · B-4 규약) · ADR-016(ROUTINE_USES) · feature-0026 계측.

## CHG-20260728T175400-cyvol-scope-prefetch-fix — cyvol 차수 선조회 cypher 조립 결함 수정 (Minor §12.3, 최적화 복구)

`unit/feature-0002-agent-core/src/modules/metadata_graph.py` — cyvol 선조회(feature-0030 W2)의
scope 술어를 **쿼리별로 패턴 뒤에** 붙이도록 조립 변경.

- 종전: `_scope_pred`(` WHERE r.scope_key = '<scope>'`) 를 두 쿼리 모두 **노드 패턴 직후**에 고정
  보간 → 차수 쿼리는 그 뒤에 관계 패턴이 이어져
  `MATCH (r:Routine) WHERE r.scope_key = 'x'-[u:ROUTINE_USES]->() RETURN r.key, count(u)` 가 되고
  PG(AGE)가 `syntax error at or near ":"` 로 거부. `scope_key is None` 경로만 유효했으므로
  **모든 per-datasource sync** 의 차수 선조회가 도입 이래 항상 실패했다.
- 수정: 서명 쿼리는 `MATCH (r:Routine){_sp} RETURN …`, 차수 쿼리는
  `MATCH (r:Routine)-[u:ROUTINE_USES]->(){_sp} RETURN …` — openCypher 의 `WHERE` 는 패턴 전체 뒤에만
  올 수 있다는 규칙을 코드 형태로 고정하고, 발견 경로·영향·재발 방지 근거를 주석에 남겼다.
- **정합성 영향 없음(종전도 fail-safe)**: 실패 시 빈 차수 dict → `_routine_edges_intact` 가 차수
  0 ≠ 기대치로 판정해 전량 재작성으로 강등됐다. 복구되는 것은 ① 스코프 sync 의 cyvol W2 감축
  (실측 전체의 32%) ② B3 재조정 안전망의 차수 판정 ③ 매 스코프 sync 1회씩 돌던 불필요한
  `rollback()` + `anchor_cache_reset()`.

`unit/feature-0002-agent-core/tests/test_graph_cypher_volume.py` — 회귀 잠금 3건 + 하네스 보강:
- `_assert_cypher_parses` 를 `_SyncCur.execute` 에 배선 — mock 이 **PG 대신** malformed cypher 를
  거부한다(한 절의 `WHERE` 이후 `RETURN` 전 구간에 `-[` 가 있으면 문법 오류). 이 가드 없이는
  문자열 단정만 가능해 "그 문장이 라이브에서 죽는다"를 행위로 표현할 수 없었다.
- `test_scoped_degree_prefetch_cypher_is_wellformed` — 구조 단정(`'ds-x'-[` 부재 + `WHERE` 가
  관계 패턴보다 뒤).
- `test_scoped_prefetch_result_actually_skips_rewrite` — end-to-end: 스코프 경로에서도 선조회가
  소비돼 `DELETE u` 가 없고 rollback 이 0.
- `test_unscoped_prefetch_stays_wellformed` — 무-scope 경로 무회귀.

검증: 신규 3건을 **수정 전에 먼저 실행해 2 FAIL 재현**(기존 32건은 전부 통과 — 기존 스위트가 이
결함을 구조적으로 놓쳤음이 실증) → 수정 후 대상 3파일 **86 PASS** · feature-0002 전체 스위트를
main 기준선과 동일 하네스로 대조해 **실패 집합 차집합 양방향 0**(base 32 / fix 32, 전부 마운트
레이아웃 artifact) · **라이브 PG/AGE ground-truth** 로 수정 전 형태의 `syntax error at or near ":"`
재현 + 수정 후 형태의 실제 행 반환 확인. UI 표면 변경 0 · alembic 마이그 0 · RBAC/엔드포인트 무변경.

Cross-ref: REVIEW REV-20260728T175400-cyvol-scope-prefetch-fix ·
`docs/test-runs.d/20260728T175400-cyvol-scope-prefetch-fix.md` ·
선행 CHG-20260728T163000-graph-cypher-volume(도입 cycle) ·
발견 경로 `unit/feature-0016-metadata-graph/docs/REPORT.md` 의 routine-column-edges POST-DEPLOY 절.

## CHG-20260728T182000-cyvol-scope-prefetch-postdeploy (cyvol scope-prefetch 수정 POST-DEPLOY 재확인)

코드·자산 변경 **0**. PR #1022 머지(main `44fe939d`) + 전체 롤아웃(web 롤링 + 워커 + gateway
reconcile, soak 통과) 이후 라이브 배포본에서 결함 소실을 재확인한 기록.

- 배포: web-a/web-b/ask-worker/insight-worker 전부 `44fe939d`. `metadata_graph.py` 는 워커(sync)와
  web(그래프 조회 API) 양쪽이 쓰므로 전체 스코프 롤아웃(`--web-only` 아님).
- 오류 소실: 스코프 지정 backfill(`--scope mysql-ddae8975d793` — 결함이 항상 발동했던 경로)의
  sync_graph 리포트가 `errors=6`(routine_prefetch SyntaxError 포함) → **`errors: []`**,
  워커 로그의 `routine_prefetch`/`syntax error` **0회**.
- 데이터 무손상 + 멱등: mysql-local scope `ROUTINE_USES` 601 엣지 / `ref_columns` 370 ·
  스코프 backfill 연속 2회 `with_cols` 257 불변.
- 커버리지(귀속 분리): `cols` 보유 routine 5,807 → **7,377**, AGE `ref_columns` 엣지 2,725 → **9,269**,
  `cols` 보유 scope 5 → **8**. 같은 창에서 backfill 재실행·워커 cadence·본 수정이 함께 작용했으므로
  **본 수정 단독 효과로 주장하지 않는다**(기여 분리 미측정).

미해결 관측(§8.1 기록만): 1차 전체 backfill(수정 전 이미지) 이후 mysql-local `with_cols` 가 6 으로
불변이었는데 수정 후 스코프 실행에서 257 로 수렴했다. 파서(`routines.py`)는 두 이미지 간 바이트
동일이고, 본 결함의 rollback 은 그래프 커넥션에만 작용해 `routine_objects` 미persist 의 원인일 수
없다(코드 독해). 유력 후보는 `introspect_and_store` 의 예외 삼킴("0/부분 카운트 반환")으로 고부하
창에서 컬럼 인벤토리 실패가 **커버리지를 조용히 줄인 채 exit 0** 이 되는 경로다. 1차 리포트가
유실되어 확정하지 못했다. 개선 후보(미실행): 부분 실패를 반환값·리포트에 구분 신호로 남기고
per-schema `cols` 채움 수를 리포트에 포함.

Cross-ref: REVIEW REV-20260728T182000-cyvol-scope-prefetch-postdeploy ·
`docs/test-runs.d/20260728T182000-cyvol-scope-prefetch-postdeploy.md` ·
수정 cycle CHG/REV-20260728T175400-cyvol-scope-prefetch-fix.

## CHG-20260729T120000-inference-detail-metrics — inference_ms 내부 분해 계측 (Minor §12.3)
> 답변 지연의 최대 구간이자 **유일하게 남은 블랙박스**인 `inference_ms` 를 쪼갠다. 개선이 아니라 **다음 개선 대상을 고르기 위한 계측**이다.
- **측정 근거(2026-07-29, 7일 창)**: `inference_ms` 평균 **142.9초** 중 `llm_usage`(task='agent') 로 귀속되는 LLM 시간이 109.9초(4.3 호출), **33.0초(23%)가 미귀속**. feature-0026 이 `init_ms` 를 `init_detail` 로 쪼갠 뒤에도 가장 큰 단계만 통짜로 남아 있었다(`duration_breakdown` 키 실측: `init_detail` 20건 / `inference_detail` 0건).
- **배제된 후보(측정으로)**: ① red-team — wall 의 **95~98%가 실제 LLM 시간**(시간창 조인 귀속: 비-rederive 49.2s 중 48.4s, rederive 304.4s 중 290.5s)이라 제거할 오버헤드가 없다. ② 큐 대기 — p50 0.3s / p90 0.5s / max 876s 로 고정 지연이 아니라 꼬리이며, 최장 4건은 `claimed_by` 컨테이너가 매번 달라 **배포 실패로 워커가 부재**했던 창이었다(정상 롤아웃은 25초 실측). ③ PG — 40분 델타로 총 exec **8.0초**(0.3% 점유), cypher 는 0.37초. 정상 상태에서 PG 는 병목이 아니다.
- **구현**: `duration_breakdown.inference_detail` = `llm_ms`/`llm_calls`(메인 루프 성공 왕복), `tool_ms`/`tool_calls`(`execute_tool`, 실패 포함 — 실패한 SQL 도 시간을 쓴다), `tool_top`(도구명 → {ms, n}, ms 내림차순 상위 6), `other_ms`(**잔차**).
  - `other_ms = inference_ms − redteam_ms − llm_ms − tool_ms`. **redteam 을 빼는 것이 핵심** — red-team 은 inference 구간 안에서 돌아 `inference_ms` 에 포함돼 있고(feature-0026 M3 와 동일 전제), 빼지 않으면 그 LLM 시간이 통째로 잔차로 잡혀 "오케스트레이션이 느리다"는 **정반대 결론**이 나온다.
  - 음수 잔차는 0 클램프 + `residual_clamped=True` 플래그. 조용히 0 을 쓰면 '전부 설명됨'으로 오독된다.
  - 실패한 LLM 호출은 누산하지 않는다(llm_usage 에도 안 남아 대조가 어긋난다) — 그 시간은 `other_ms` 에 남지만 `llm_calls` vs `llm_usage` 건수 대조로 식별 가능.
  - 범위는 **메인 에이전트 루프만**. red-team 재추론(`_rt_rederive`)의 도구는 `redteam_ms` 소관이라 섞지 않는다.
- **관측 경로**: `bin/perf-snapshot.sh` §3b-2(분해 + `other_pct` + clamped 건수) · §3b-3(도구별 총소요·호출당 평균).
- **불변**: 기존 4키(queued/init/inference/total)와 `redteam_ms`·`init_detail` 무변경 — additive. 답변 동작·저장 스키마 무변경(meta_json 내 키 추가), alembic 무변경.
- **파일**: `src/agent_core.py`, `tests/test_inference_detail.py`(신규 16건), `bin/perf-snapshot.sh`, `docs/{FUNCTION,TASK}.md`.
- **§18.8 적대 패널이 잡은 결함 9건 흡수** (초안은 **문서가 주장한 기능이 존재하지 않았고**, 잔차가 체계적으로 과소평가되고 있었다):
  - **MAJOR-1(초안 주장 반증)**: "비정상 종료 경로에도 분해를 싣는다"는 **거짓**이었다 — `_slim_result` allowlist 가 `duration_breakdown` 을 떨어뜨리고 비정상 경로 mirror 는 meta 를 안 실어 **어디에도 영속되지 않는 죽은 코드**였다(perf-snapshot 은 `messages.meta_json` 을 본다). 주장을 철회하고 해당 부착을 제거했다.
  - **MAJOR-2**: 같은 자리는 `break` 로 나온 **정상 경로도** 지나는데, 그 시점 `now_perf` 는 메시지 저장·in-process 큐레이션(실측 25~35초) 뒤라 잔차가 red-team+쓰기+큐레이션 범벅이 된다 — 이 계측이 피하려던 바로 그 오도. 제거로 함께 해소(비정상 경로 가시성은 mirror meta 를 손대야 하는 별개 변경 — **미커버로 명시**).
  - **MAJOR-3(설계 결함)**: `llm_ms` 가 `_call_llm` **래퍼 전체**를 재고 있었다. 그 창 안에는 첨부 인라인 로드·`messages_for_provider` 재조립·`runtime_settings` DB 읽기(TTL 10초라 라운드마다 대개 miss)·`llm_usage` INSERT 가 들어 있어, **잔차가 찾으려던 오케스트레이션 시간이 llm_ms 로 청구**되고 기준선 109.9초(`llm_usage.latency_ms`)와도 비교 불가가 된다. → `_LLM_LAST_PROVIDER_MS` ContextVar 로 **순수 provider 왕복만** 집계하고 래퍼 오버헤드는 의도적으로 `other_ms` 에 남긴다(그게 오케스트레이션의 정의).
  - **MAJOR-4(산술 오류)**: perf-snapshot §3b-3 `avg_ms_per_call` 이 `avg(ms/n)`(답변별 평균의 평균)이라 느린 1건짜리 답변이 빠른 100건짜리를 압도 — 패널이 라이브 합성 데이터로 228ms 를 **9,025ms(40배)** 로 과대보고함을 실증. → `sum(ms)/sum(n)`.
  - **MAJOR-5(테스트 무력)**: 초안 테스트는 순수 빌더만 호출해 **누산 배선이 0% 검증**이었고 5개 변이(누산 호출 삭제·도구 계측 제거·키 상한 제거·redteam 미차감·영속 차단)가 전부 생존했다. 누산기를 모듈 함수로 승격해 직접 잠그고, 배선은 소스 계약 테스트로 고정(16건).
  - **MINOR-1**: 누산이 LLM 오류 `try` 본문 안에 있어, 거기서 난 예외가 `except` 로 잡혀 **성공한 라운드가 provider 오류로 둔갑하고 run 이 중단**될 수 있었다 → 성공 분기(`else`)로 이동 + 가드.
  - **MINOR-2**: `finally` 안 누산이 무가드라 raise 시 **원래 예외를 대체** → try/except 로 감쌈.
  - **MINOR-3(데이터 소실 경로)**: 도구명은 모델이 정하는 값이고 이 계측이 그것을 처음으로 `meta_json` 의 **JSON 키**로 싣는다. NUL 이 섞이면 PG jsonb 캐스트가 실패하는데 `_mirror_message` 가 예외를 삼켜 **답변 행 자체가 조용히 사라진다**(패널이 라이브 PG 로 재현) → 제어문자 제거 + 빈 키 placeholder.
  - **MINOR-5**: "llm_calls vs llm_usage 대조로 식별 가능" 이라 써놓고 그 쿼리를 안 넣었다 → §3b-4 교차검증 섹션 추가.
- **역검증**: 패널이 생존시킨 변이 6종(LLM 누산 삭제 · 도구 try/finally 해체 · 키 상한 제거 · redteam 미차감 · provider 창 확대 · 라운드 리셋 제거)을 각각 되돌려 해당 테스트 실패 확인 — **생존 0**.
- **위험등급**: Minor(계측 additive · fail-open try/except). **Rollback**: 커밋 revert — 소비처가 키 부재를 이미 견딘다.
- **Cross-ref**: feature-0026(init_detail 원형·perf 계측 인프라) · ADR-20260728T120000-redteam-gating-not-adopted(red-team 은 품질 우선으로 불채택 — 이번에도 대상 아님을 실측 재확인).
## CHG-20260729T110000-dataplane-conn-liveness (데이터플레인 연결 liveness + 같은 좌표 재연결)

**무엇을**: run-scoped 데이터플레인 연결을 tool 에 넘기기 직전 liveness 를 확인하고, 죽었으면
**같은 좌표로만** 재연결한다. 라우터 경로(`_DatasourceRouter.conn_for`)는 label 캐시를 갱신하고,
단일 datasource 경로는 새 소유자 `_DataplaneConn`(agent_core 가 등록)이 갱신을 보유한다.

**왜**: run 시작에 1회 수립한 연결이 그 run 의 모든 tool 호출에 재사용되는데 liveness 검사·재연결이
없어, 연결이 죽는 두 경로 어느 쪽이든 **남은 tool 전부**가 드라이버 문구로 실패했다.
- (a) 유휴 사망 — 첫 tool 까지 LLM 추론이 수 분(실측 232초). 라이브 실험에서 대상 datasource 는
  60~120초 유휴에 절단됐고(대조 datasource 는 생존), 사망 순간 `DBPROCESS is dead`,
  그 이후 모든 사용이 `Not connected to any MS SQL server` — 사고 전사와 같은 순서.
- (b) in-run 사망 — 쿼리 타임아웃이 세션을 죽인 뒤 4초 만에 온 다음 tool 부터 전부 실패.

**어느 RC**: `FR-dataplane-conn-stale-no-reconnect` (L4↔L8). 원장 정본은
`docs/improvements/conversation-audit/FRICTION_LEDGER.md`.

**재발 봉인 방식**: 재발 경로가 *infra idle-timeout drift* + *모델 지연 drift* 라 우리가 통제할 수
없다 → **코드가 권위선**. 데이터 row·설정 조정이 아니라 재사용 choke-point 에 liveness 계약을 둔다.

### 변경
- `shared/config.py` — `AGENT_DS_CONN_PING_IDLE_SEC`(기본 30초, ping 생략 임계. 0=항상 ping).
- `unit/feature-0002-agent-core/src/modules/tools.py`
  - `_ping_conn` / `_mark_conn_used` / `_mark_conn_suspect` / `_conn_needs_ping` / `_ensure_live_conn`
  - `_DataplaneConn` + `set/reset_active_dataplane_conn`(단일 경로 소유자, ContextVar)
  - `_DatasourceRouter.conn_for` — 캐시된 죽은 연결 교체
  - `execute_tool` 양 경로 — 사용 직전 확보 + 결과/예외로 연결 상태 갱신(`_note_conn_outcome`)
  - `is_dead_conn_error` / `_dataplane_error_text` — 끊김 문구 정직화
  - `_tool_execute_sql` 부하게이트 — 추정 실패 원인을 liveness 로 구분(연결 문제면 "쿼리를 좁혀라" 금지)
  - `_search_tables_mssql` — per-DB 실패 삼킴 제거(형제 `_search_routines_mssql` 과 대칭)
  - `_search_routines_mssql` — 끊김 시 suspect 표시 + 짧은 원인 문구
- `unit/feature-0002-agent-core/src/agent_core.py` — 단일/eval 경로에 재연결 클로저 + holder 등록·해제,
  종료 시 holder 를 통한 close(재연결됐으면 살아있는 쪽을 회수).

### 보안 불변식 (변경 없음)
- 재연결은 **호출측이 준 인자 없는 콜백 하나**로만 — 좌표를 여기서 재해석하지 않아 다른
  datasource/DB 로 새는 경로가 구조적으로 없다. 콜백은 `connect_with_retry(database=…, datasource=…)`
  라 회로차단기·`database=None`(schema-prefixed 강제, M-1)·allowlist 게이트가 그대로 유지된다.
- 재연결 실패는 삼키지 않고 전파(fail-closed) — 폴백 연결 없음.
- 부하게이트는 두 분기 모두 **실행하지 않고 차단**한다(fail-closed 강도 불변).
- 세션 스코프 상태(`SET SESSION max_execution_time`)는 `_apply_query_cap` 이 매 호출 재-SET 이라
  재연결 후에도 재적용된다.

### 실패한 문장은 재시도하지 않는다
(b) 는 서버에 도달했을 수 있어 자동 재실행이 부하를 2배로 만든다. 그 tool 만 정직히 실패시키고
**다음 tool 부터** 자동 복구한다 — 유휴 사망 (a) 는 애초에 문장이 서버에 닿지 않아 완전 봉인된다.

Cross-ref: TASK-20260729T110000-dataplane-conn-liveness ·
REVIEW REV-20260729T110000-dataplane-conn-liveness ·
원장 `FR-dataplane-conn-stale-no-reconnect`.

## CHG-20260729T160000-test-live-pg-isolation — 테스트 라이브 PG 격리 완결 + PG 연결 저하 계약 단일화

**동기**: `make test` 가 라이브 Postgres 를 실제로 읽어(운영 `.env` 상속 + compose 네트워크 도달)
attachment 계열 13건이 고정 실패하고, 반대로 라이브 PG 생존에 의존해 통과하던 테스트도 생겨
"main 기준선과 동일한 N건 실패" 가 세션마다 다른 N 으로 반복 관측됐다. 상세 = TASK 동명 섹션.

### 변경
- `Makefile` — `TEST_ISOLATION_ENV` 에 `AGENT_KB_PG_PORT=1` · `AGENT_KB_PG_PORT_RO=1`(PG 도달
  차단) + `AGENT_RUNTIME_READ_BACKEND` · `AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND` ·
  `AGENT_KB_READ_BACKEND` = `mysql`(운영 cutover 스위치 중립화). 유보 주석 갱신.
- `conftest.py` (신규, 저장소 루트) — 같은 격리를 하네스 밖에서도 강제하는 2중 방어. module-level
  적용(모듈이 import 시점에 `os.environ` 을 굳히므로 fixture 로는 늦다).
  escape = `AGENT_TEST_ALLOW_LIVE_BACKENDS=1`.
- `shared/db.py` — `_pg_conn_pair_ro` / `_pg_conn_pair_rw` 신설. `(conn, owned)` 페어의 정본.
  **RO 는 접속 실패도 `(None, False)` 로 저하**(warning 1줄, traceback 없이 사유만),
  **RW 는 설정 미비만 저하하고 접속 실패는 전파**(비대칭은 의도 — 아래 "동작 변경" 참조).
- `unit/feature-0002-agent-core/src/modules/{metadata_graph,node_analysis,relationships,routines,
  semantic_cluster,kb_metadata,kb_glossary,sample_queries}.py` — 각자 복제하던 `_ro_conn`/`_rw_conn`
  11곳을 위 정본으로 위임. 함수 자체는 남긴다(테스트가 모듈 속성을 monkeypatch 한다).

### 동작 변경 (프로덕션) — 읽기만, 쓰기는 불변
**RO(읽기)**: PG 접속 실패 시 예외 전파 → **빈 결과 저하**로 바뀐다. 읽기 호출부는 전부 이미
`if c is None:` 저하 분기를 갖고 있었으므로 코드 경로는 새로 생기지 않고, 그 분기가 비로소
의도대로 도달된다. docstring("실패/라벨 부재 시 [] 로 저하 — 비차단")과 실제 동작이 처음으로 일치.

**RW(쓰기)**: **동작 변경 없음**(설정 미비만 저하, 접속 실패는 전파 — 기존과 동일). 초안에서는
쓰기도 저하시켰으나 커밋 전 자체 검토에서 회귀를 발견해 되돌렸다: `sync_graph` 는 접속 실패 시
초기 리포트(`errors=0, step_failures=0`)를 그대로 반환하고 `scripts/metadata_graph_sync.py:55,64`
가 이를 `ok=True` → `return 0` 으로 해석하므로, **cron(`bin/metadata-graph-sync.sh`)이 PG 순단을
exit 0 으로 받아 그래프가 stale 해져도 아무도 모르게 된다.** 읽기 저하는 데이터 정합성을 훼손하지
않지만 쓰기 실패 은폐는 관측성 손실이라, 비대칭을 의도적으로 남겼다.

### 안전성
- 자격증명·SSRF allowlist·회로차단기 경로 불변 (`_pg_connect{,_ro}` 본문 무수정, 호출만 감쌈).
- RO 저하는 silent 아님 — `agent_core.db` 로거에 warning. 순단 시 로그 폭주 방지로 traceback 생략.
- 쓰기 경로(`_rw_conn`) 는 접속 실패를 계속 전파 — sync 실패가 성공으로 보고되는 경로 없음.
- 테스트가 운영 DB 에 쓰기를 시도하던 경로(product PATCH)가 구조적으로 차단됨.

Cross-ref: TASK-20260729T160000-test-live-pg-isolation ·
REVIEW REV-20260729T160000-test-live-pg-isolation.

## CHG-20260729T183000-test-live-pg-isolation-postdeploy — 배포 후 라이브 실증 기록 (문서만)

**실행 코드·정적 자산 변경 0줄.** 선행 CHG-20260729T160000-test-live-pg-isolation 이 바꾼 PG 연결
계약(RO 저하 / RW 전파)이 배포본 `c16e3a84` 에서 설계대로 동작함을 확인하고 기록한다.

### 변경
- `unit/feature-0002-agent-core/docs/TASK.md` — POST-DEPLOY 실증 섹션(실측 항목 + 검증 방법 함정).
- `unit/feature-0002-agent-core/docs/REVIEW.md` — REV-20260729T183000 항목.

### 실증 요지 (repo-web-a-1)
정상 경로 RO 연결·`SELECT 1`·그래프 읽기 3건 정상 / PG 도달 불가 시 RO 는 `(None, False)` + warning
1줄, RW 는 `OperationalError` 전파. 후자가 `sync_graph` 실패의 exit 0 위장을 막는 지점이다.

Cross-ref: TASK-20260729T183000-test-live-pg-isolation-postdeploy ·
REVIEW REV-20260729T183000-test-live-pg-isolation-postdeploy.

## CHG-20260730T160000-ask-redeploy-handoff — 재배포 인계: 고아 ask job dead-air 봉인

**무엇을**: 배포가 ask-worker 를 재생성할 때 진행 중이던 답변이 통째로 사라지고, 회수까지
수백 초가 비던 경로를 봉인한다. 사용자 체감으로는 "요청이 도중에 중단"으로 나타났다.

**왜**: `bin/deploy-web.sh` 는 워커를 `--force-recreate` 한다. 그런데 worker 소유자 id 가
`gethostname()`(=컨테이너 id) 기반이라 재생성 후 `reclaim_worker_jobs_on_boot` 의
`claimed_by = worker_id` 정확일치가 **항상 0행**이었다. 즉 "배포로 죽은 job" 은 자가회수가
구조적으로 불가능했고, 전역 stale sweeper 의 `AGENT_ASK_WORKER_STALE_SEC`(런타임 실측 450s)
창을 통째로 기다렸다. 60일 실측 8건/8대화, 생성→재시작 dead-air 142~1,649초, 3건 최종 error.
재실행은 사용자 메시지를 한 번 더 저장해 화면에 같은 말이 두 줄 보였다(9대화).

**어느 RC**: conv-audit `FR-ask-orphan-redeploy-dead-air` RC-1(회수 지연)·RC-2(중복 저장).

**재발 봉인 방식**: 재발경로는 `infra`(배포마다 재생성)이고 우리 통제 안이므로 **코드를
권위선**으로 둔다 — 죽기 전에 반납하고(A), 못 반납했으면 다음 인스턴스가 짧은 창으로
회수한다(B). 임계 추측이 아니라 소유권 인계 계약이다.

### 변경
- `shared/config.py` — `AGENT_ASK_WORKER_DRAIN_SEC`(기본 60, compose `stop_grace_period` 70s
  보다 작아야 반납이 SIGKILL 前에 끝난다) · `AGENT_ASK_WORKER_ROLE_STALE_SEC`(기본 60)
  신설, `__all__` 등록.
- `modules/ask_jobs.py` — `release_worker_jobs_on_shutdown()`(자기 소유 + `#slot` prefix
  매칭 requeue) · `reclaim_role_orphan_jobs()`(같은 role 의 **다른** 인스턴스 + 짧은 heartbeat
  창) · `_like_prefix()`(LIKE 와일드카드 이스케이프). 둘 다 기존 requeue 와 **동일한 상태
  전이**(pending + `lease_epoch++` fencing)를 쓴다 — 새 status 없음. `attempts` 미변경.
- `modules/ask.py` — `_worker_role()`/`_worker_role_prefix()`/`_worker_id()` 를 재생성 불변
  role 기반으로 분리(우선순위 `AGENT_WORKER_ROLE` > `AGENT_SESSION` > hostname —
  feature-0025 T0c 선례) · `_release_own_leases()` · SIGTERM 타이머
  `_arm_shutdown_lease_release()`(직렬 모드는 메인 스레드가 블록되므로 이것이 유일한 반납 창) ·
  drain deadline 을 하드코딩 65s → knob · 종료 경로/부팅/주기 유지보수에 회수 배선 ·
  재시도면 `dedup_user_message_since` 주입.
- `modules/runtime_backend.py` — `PgRuntimeBackend.user_message_persisted_since()` +
  core/display 2쿼리(`created_at >= since` 로 **job 수명 이후만** 판정).
- `agent_core.py` — `run_agent`/`_run_agent_core` 에 `dedup_user_message_since` 추가(기본
  None = 종전 동작) · `_user_message_already_persisted()` helper · 사용자 메시지 저장부가
  core/display 각각 판정 후 저장.
- `unit/feature-0002-agent-core/tests/test_ask_redeploy_handoff.py` — 신규 17건.

### 안전 경계
- 보안 경계 **불변** — RBAC·가드·allowlist·PII 경로 무변경. 큐 상태기계도 기존 전이만 쓴다.
- 오회수 방지: role 창은 자기 자신/자기 슬롯을 제외하고 `heartbeat_at` 이 `ROLE_STALE_SEC`
  이상 끊긴 행만 본다. heartbeat 는 시간 기반(10s 주기, step 무관)이라 이 창을 넘겼으면 그
  프로세스는 죽은 것이다. 전역 `STALE_SEC` 은 그대로 보수적으로 유지.
- 중복 억제는 **근거 기반 fail-open** — 조회 불가/PG 정본 아님이면 종전대로 저장한다(중복 1행이
  요청문 유실보다 안전).

Cross-ref: TASK-20260730T160000-ask-redeploy-handoff ·
REVIEW REV-20260730T160000-ask-redeploy-handoff ·
원장 `docs/improvements/conversation-audit/FRICTION_LEDGER.md` `FR-ask-orphan-redeploy-dead-air`.

## CHG-20260730T172000-dedup-param-cast — 중복 억제 판정 SQL 파라미터 캐스트 (봉인 C 활성화)

**무엇을**: `user_message_persisted_since` 의 두 판정 쿼리에 파라미터 타입 캐스트 추가.

**왜**: `%(mirror_sender)s IS NULL` 은 타입 컨텍스트가 없어 PostgreSQL 이 쿼리를 거부하고
(`could not determine data type of parameter $4`), `_read_runtime_pg` 가 그 예외를 흡수해
호출부가 fail-open 으로 저장한다 → **선행 CHG 의 봉인 C 가 배포본에서 통째로 무력**이었다.
배포 후 라이브 job 485 재시도에서 사용자 메시지가 다시 중복 저장되며 실증됐다(6301↔6322).

**어느 RC**: conv-audit `FR-ask-orphan-redeploy-dead-air` RC-2 (중복 저장) — 선행 수정의 결함 보정.

**재발 봉인 방식**: fail-open 자체는 유지가 옳다(중복 1행 < 요청문 유실). 대신 그 fail-open 이
**조용한 전면 무력화**로 번지지 않도록 캐스트를 회귀로 고정한다.

### 변경
- `modules/runtime_backend.py` — `_PG_USER_MESSAGE_EXISTS_DISPLAY` 의 `mirror_sender` 양쪽에
  `::text`, `_PG_USER_MESSAGE_EXISTS_CORE` 의 `sender_account_id` 에 `::bigint`. 캐스트가 왜
  필수인지 주석에 실측 근거 명시.
- `tests/test_ask_redeploy_handoff.py` — `test_dedup_sql_casts_bare_parameters` 신규.

### 검증 (실 PG 포함 — 선행 cycle 의 공백을 메움)
배포본 워커에서 RO 연결로 두 쿼리를 직접 실행: core hit/miss, display 그룹 hit/miss, display 1:1
NULL hit **5케이스 전부 계약대로**. 전체 회귀 `make test` EXIT=0 · ruff clean.

Cross-ref: TASK-20260730T172000-dedup-param-cast · REVIEW REV-20260730T172000-dedup-param-cast ·
선행 CHG-20260730T160000-ask-redeploy-handoff.

## CHG-20260730T190000-init-prologue-metrics — init_ms 프롤로그 계측 + 잔차 노출 (Minor §12.3)
> feature-0031 이 inference 블라인드스팟을 닫자 **init 이 최대 미귀속 구간**으로 드러났다. 같은 패턴(계측 → 데이터가 대상을 정함)을 반복한다.
- **선행 cycle 의 결론 정정**: feature-0031 계측이 "inference 미귀속 33초(23%)" 가설을 **반증**했다. 실측 `other_ms` = 235ms(**1.6%**). 그 33초는 숨은 오케스트레이션이 아니라 **red-team** 이었다 — 이전 분석이 `inference_ms` 를 `task='agent'` LLM 시간과만 대조했는데, red-team 은 inference 구간 안에서 돌면서 LLM 을 `task='redteam'` 으로 기록한다. 사용자가 품질 우선으로 유지하기로 결정한 부분이라 개선 대상이 아니다. **계측이 자기 가설을 깬 사례**로 기록한다.
- **측정(2026-07-30, 7일 63건)**: `init_ms` 평균 **4,921ms** 중 `init_detail` 설명분 **750ms** — **4,171ms(85%) 미귀속**. 원인은 feature-0026 의 `init_detail` 이 `history_load` **이후**만 담았고 함수 진입~그 지점 266 줄이 통짜였던 것. 워커 직접 계측: `_connect_memory` 12ms / `_resolve_product_datasource` 46ms / **데이터플레인 `connect_with_retry` 1,447ms**.
- **구현**: `_init_detail` 선언을 함수 진입부(`agent_entry_perf` 직후)로 올리고 프롤로그 3구간(`mem_setup_ms`·`ds_resolve_ms`·`dataplane_connect_ms`)을 추가. 신규 `_build_init_detail(init_ms, detail)` 이 **잔차 `init_other_ms`** 를 계산해 붙인다.
  - **잔차 노출이 설계 핵심**(feature-0031 교훈) — 노출하지 않으면 다음 블라인드스팟이 또 조용히 숨는다. 직전 cycle 에서 33초의 정체를 판정할 수 있었던 이유가 잔차를 명시했기 때문이다.
  - `knowledge_total_ms` 는 knowledge 하위 항목의 **롤업**이라 잔차 계산에서 제외한다(포함 시 이중 계상 → 잔차 음수). 표시용으로는 보존.
  - 음수 잔차는 0 클램프 + **수치** 키 `init_residual_neg_ms`(bool 금지 — §3b 가 모든 키를 `::float` 캐스트한다).
  - 데이터플레인 계측 종료점은 **폴백(`database=None` 재시도) 뒤**에 둔다 — try 안에 두면 폴백 시간이 잔차로 샌다. 멀티(라우터) 경로도 같은 키로 기록.
  - 기존 선언부(`history_load` 직전)는 **제거**했다 — 남겨두면 프롤로그 계측치가 빈 dict 로 덮여 통째로 사라진다.
- **관측**: `bin/perf-snapshot.sh` §3b-0(프롤로그 3구간 + `init_other_ms` + `other_pct` + clamped).
- **불변**: 기존 `init_detail` 키·`inference_detail`·나머지 breakdown 무변경(additive). 답변 동작·스키마·alembic 무변경, 조립은 fail-open.
- **파일**: `src/agent_core.py`, `tests/test_init_prologue_detail.py`(신규 17건), `bin/perf-snapshot.sh`, `docs/{FUNCTION,TASK}.md`.
- **§18.8 적대 패널 결함 8건 흡수** (초안은 "기존 `init_detail` 키 무변경" 을 주장했으나 **라이브에서 반증**됐다):
  - **MAJOR-1(라이브 재현)** 초안이 `init_detail` 에 넣은 bool `init_residual_clamped` 가 **기존 §3b 쿼리를 깬다** — §3b 는 `jsonb_each_text(init_detail)` 로 **모든** 키를 `::float` 캐스트하므로 `invalid input syntax for type double precision: "true"` 로 섹션 전체가 죽는다. 클램프가 뭔가 알리려는 순간에 관측이 꺼지는 최악의 실패. → 수치 키 `init_residual_neg_ms` 로 전환하고, 테스트가 **모든 값의 수치성**을 잠근다.
  - **MAJOR-2(라이브 실증)** §3b-0 이 `? 'init_detail'` 로 필터해 feature-0026 **구 행이 분모**에 들어가고 분자(신규 키)는 NULL → other_pct 가 실제보다 훨씬 좋게 나온다(패널 실증: 9구+1신 혼합에서 실제 100% 미귀속 행이 9개인데 "2%" 로 보고). → `init_detail ? 'init_other_ms'` 로 신규 행만.
  - **MAJOR-3** `knowledge_total_ms`(롤업)는 **무조건** 기록되지만 leaf 는 `_build_knowledge_context` 예외 시 하나도 안 온다. 롤업만 제외하면 knowledge 구간 전체(실측 최대 6,924ms — 평균 init_ms 보다 크다)가 잔차로 흘러 **'미귀속이 크다'는 거짓 신호**. → `max(Σleaf, 롤업)` 으로 계산.
  - **MAJOR-4** `ds_resolve_ms` 가 지배 경로(단일)에서 **엉뚱한 함수**를 쟀다 — 초안은 `_resolve_product_datasources`(복수)만 감쌌는데 바인딩 0~1 개면 즉시 `[]` 를 돌려주고 끝난다. 실제 resolve 인 `_resolve_product_datasource`(단수, WebProducts 조회+자격증명 복호, 실측 46ms)는 미계측이라 잔차로 샜다. **작고 그럴듯한 숫자가 나와 0 보다 나쁘다.** → 단수 호출에 누산.
  - **MAJOR-5(변이 실측)** 12 변이 중 **7 생존** — 배선 테스트가 전부 소스 문자열 검색이라 present-but-wrong 을 못 본다. 생존: 옛 자리 `_init_detail = {}` / `.clear()` 재추가(철자만 달라도 통과), `_dp_t0` 를 connect 뒤로(헤드라인 1,447ms 가 ~0 이 되고 폴백 경로는 UnboundLocalError 로 run 사망), 멀티 경로 기록 삭제, 부착 조건 `and False`, mem_setup 을 try 밖으로, 롤업 집합 오염. → 계약을 재바인딩 정규식·3분기 카운트·타이머 순서·들여쓰기·집합 동일성으로 강화, **7종 전부 재현해 실패 확인**.
  - **MINOR-1** eval 경로가 `dataplane_connect_ms` 미기록 — eval runner 도 같은 `messages` 에 답변을 남겨 §3b-0 평균을 '연결 0ms 행' 으로 왜곡. → 기록 추가(3분기 전부).
  - **MINOR-2** 멀티 경로 span 이 라우터 생성·`refresh_case` 를 제외해 단일 경로보다 좁았다(같은 키인데 범위 불일치). → span 확장.
  - **MINOR-3** 빌더가 멱등하지 않아 재적용 시 잔차 붕괴. → 파생 키를 leaf 집계에서 제외.
- **역검증**: 초안 5종 + 패널 생존 7종 = **12종 되돌림, 생존 0**. 테스트 10 → **17건**.
- **패널이 clean 판정한 축**: 선언 이동(9개 early-return 모두 `_compute_duration_breakdown` 이전이라 무해, 재진입 없음) · 롤업 전제(라이브 63행에서 롤업−Σleaf 가 -0.2~+0.3ms) · 6개 span 상호 배타·순차 · 영속 경로(직전 cycle 의 dead-code 결함 **미재발**, 63행이 이미 같은 경로로 저장됨) · 프론트 무영향.
- **위험등급**: Minor(계측 additive). **Rollback**: 커밋 revert — 소비처가 키 부재를 견딘다.
- **Cross-ref**: feature-0026(init_detail 원형) · feature-0031(inference_detail — 잔차 노출 패턴의 출처, 그 가설을 반증한 계측) · ADR-20260728T120000-redteam-gating-not-adopted.

## CHG-20260731T090000-query-embed-degrade-visibility — 질의 임베딩 강등 가시화 + 타임아웃 재조정 (Minor §12.3)
> feature-0034 계측이 init 의 87%가 `query_embed_ms` 임을 드러냈고, 추적해보니 **성공한 느린 임베딩이 아니라 타임아웃 후 무음 강등**이었다.
- **측정(라이브 2026-07-31)**: feature-0034 배포 후 답변 2건의 `init_detail` 이 `query_embed_ms` 20,587ms·20,022ms — init 의 87%, 전체 답변의 64%. 그런데 `AGENT_KB_QUERY_EMBED_TIMEOUT_SEC=20` 과 정확히 일치 → **타임아웃 만료 후 trigram 폴백**이었다. 직접 계측한 warm 은 p50 **206ms** / p90 215ms / max 429ms(47 표본, 4분 연속, 폴백 0건).
- **원인(환경)**: 병렬 세션이 오늘 돌린 시그니처 전수 재계산(48,226건)의 백필 스윕이 단일 CPU-bound 임베딩 백엔드를 포화시켰다(ollama CPU 109%, `/api/embed` 18~56s, 대기 8,371건). **조사 시점엔 이미 소진**(`pending=0`, CPU 0.03%)돼 급성 조건은 해소됐다.
- **왜 노브를 더 만지지 않았나**: 같은 노브(`BATCH_MAX_ROWS` 100→1000→600, `BATCH_SIZE` 25)를 병렬 세션이 **오늘만 두 번** 조정 중이다("embed-congestion-fix" 주석이 그 증거). 해소된 조건을 위해 조율 기능을 새로 만들거나 남의 처리량 튜닝과 경합하는 대신, **빠져 있던 것**을 채운다.
- **① 강등 가시화**: `init_detail.query_embed_ok`(1.0/0.0) 신설. 종전엔 임베딩 실패 → trigram 폴백이 **완전히 무음**이라 `query_embed_ms` 만 보고 '느린 성공'과 구분할 수 없었고, 그 상태가 2주간 드러나지 않았다. 값이 **수치**인 이유 — `bin/perf-snapshot.sh` §3b 가 `jsonb_each_text` 로 전 키를 `::float` 캐스트하므로 bool 은 섹션을 통째로 죽인다(feature-0034 패널 MAJOR-1 라이브 재현). 소요가 아니므로 `_INIT_DERIVED_KEYS` 에 등재해 잔차 leaf 에서 제외. 임베딩을 **시도조차 안 한** 경우(빈 질문·양 기능 OFF)는 강등이 아니므로 시도와 **동일 게이트**(`_SQ_EN or _AR_EN`)로만 기록 — 아니면 강등율이 과대보고된다.
- **② 타임아웃 20s → 12s**(초안 5s 는 패널이 반증 — 아래): 실측이 **두 개의 분리된 체제**만 보여준다 — warm p90 215ms, 포화 시 20s 를 다 쓰고도 미완료. 그 사이는 관측되지 않았다. 즉 20s 는 성공을 건지는 값이 아니라 **실패를 늦게 확인하는 값**이었고, 포화 창의 모든 답변이 15초를 순수 낭비한 뒤 어차피 강등됐다. 5s = warm p90 의 23배 여유. **남는 불확실성을 은폐하지 않는다** — '중간 정도 느린'(5~20s 에 성공) 체제는 실측된 적이 없고, 그 구간이 실재하면 불필요한 강등이 는다. 이제 ①이 강등율을 관측하므로 추측이 아니라 데이터로 재조정한다.
- **관측**: `bin/perf-snapshot.sh` §3b-1(강등 건수·비율·embed 평균/최대).
- **불변**: 기존 키·답변 동작·스키마 무변경(additive), fail-open. 강등 자체는 종전과 동일한 설계된 거동(trigram graceful degrade) — 이번 변경은 **그것을 보이게** 할 뿐이다.
- **파일**: `src/agent_core.py`, `shared/config.py`, `tests/test_query_embed_visibility.py`(신규 9건), `shared/runtime_settings.py`, `bin/perf-snapshot.sh`, `docs/{FUNCTION,TASK}.md`.
- **§18.8 적대 패널 결함 8건 흡수 — 초안은 BLOCKER 를 안고 있었다**:
  - **BLOCKER-1(런타임 실증)** 발행부 `_KNOWLEDGE_TIMINGS.set({k: v ... if v >= 0.1})` 의 **소요 잡음 필터에 상태 플래그 0.0 이 걸려 탈락**했다. 성공(1.0)만 통과 → 대시보드가 언제나 **"강등 0%"** 라는 거짓 안심을 보고한다(종전의 무음보다 **나쁘다** — 운영자가 신호가 있다고 믿는다). 키의 '존재' 가 성공을 뜻하게 돼 시도-안-함과 강등을 가르려던 게이트도 무효화됐다. → 플래그류(`_INIT_DERIVED_KEYS`)는 값 무관 통과.
  - **MAJOR-1(초안 근거 반증)** 5s 의 근거였던 "warm p90 215ms · 23배 여유" 는 **16자 질의 한 종류만** 잰 값이었다. 지연은 **입력 길이에 비례**한다(독립 재현: 5,712자 **4,172ms**; 패널 6KB 3.7~5.4s / 10KB 5.7~8.5s). 라이브 90일 최대 사용자 메시지가 5,996자라 5s 는 **경계**였고 패널이 6KB 3회 중 1회 폴백을 관측했다. 초안 주석의 "5~20s 중간 체제 미관측" 도 거짓 — 유휴 백엔드에서 길이만 바꿔도 나온다. → **12s**(관측 최대-실입력 지연의 2.2~2.9배, 20s 대비 8s 절감).
  - **MAJOR-2** `shared/runtime_settings.py` spec default 가 20 그대로라 **콘솔은 20 을 표시**하고 운영자가 '초기화' 를 누르면 20 이 override 로 기록돼 변경이 조용히 되돌아간다. 임베딩 강등을 조사하러 콘솔을 연 운영자가 타임아웃을 원인에서 배제하게 만드는 — 이 cycle 이 막으려던 바로 그 오진. → spec default 12 + minimum 5(`llm.py` 의 `max(5,…)` 바닥과 정합) + **parity 테스트**.
  - **MAJOR-3(변이 실측)** 7 중 2 생존 — 발행문을 플래그 기록 앞으로 옮기기(플래그가 영영 미도달), §3b-1 통째 삭제(유일 소비처 소멸). 종전 테스트가 전부 소스 문자열 검색이라 present-but-wrong 을 못 봤다. **직전 cycle 문서에 같은 교훈을 적어놓고 같은 계열 결함을 재생산했다.** → 발행 필터를 소스에서 추출해 **실제 평가**하는 테스트 + 3지점 순서 잠금 + 소비처 존재 확인.
  - **MINOR** §3b 에 플래그가 유령 stage 행으로 표시 → 제외 · "0 = 타임아웃" 과잉 주장 수정(모델 미설정·클라이언트 부재·게이트웨이 오류도 0) · 성공/강등 소요 분리 집계(타임아웃 캡 값이 평균을 끌어당김) · 소스 철자 대신 **JSON 왕복 타입** 검증.
- **역검증**: BLOCKER + 패널 생존 2 + MAJOR-1/2 = 5종 재현, **생존 0**. 테스트 6 → **9건**.
- **패널 clean**: 발행 순서(플래그 기록이 발행보다 앞) · 게이트 스코프(import 실패 시 UnboundLocalError → 그 경우 시도 자체가 없어 fail-safe) · 잔차 상호작용 · 타임아웃 blast radius(3 호출처 전부 대화형, 배치는 별도 노브) · 재시도 증폭 없음(`AGENT_OPENAI_MAX_RETRIES=0`) · §3b-1 SQL · §3b 비회귀 · 프론트 무영향.
- **위험등급**: Minor. **Rollback**: 커밋 revert(타임아웃은 env `AGENT_KB_QUERY_EMBED_TIMEOUT_SEC` 로 즉시 원복 가능).
- **Cross-ref**: feature-0034(init 계측 — 이 문제를 드러낸 계측) · feature-0031(잔차 노출 패턴) · CHG-20260625(타임아웃 도입 시 근거였던 warm 0.33s).

## CHG-20260731T184300-loadgate-blind-coaching — 부하게이트: 실행계획 진단 코칭 + 순수 LIMIT 상한 보정 (Major §12.3)
> TASK-0304 가 게이트를 "차단"에서 "재작성 코칭"으로 바꿨는데, 그 코칭이 **모델이 이미 한 일**을 반복해 말하고 있었다. 라이브 대화 한 건에서 6연속 차단.
- **마찰(conv-audit)**: conversation `20260731021152-36a7790b` — `execute_sql` 6연속 차단, 사용자 명시 불만("블로킹이 너무 심하게 나타난다"). 30일 corroboration **structural**: distinct_conv 10 / 대화 129 (7.8%), 차단 23 / `execute_sql` 386 (6.0%).
- **정직한 기각(표면 가설 반증)**: 사용자가 지목한 "`LIMIT 1` 인데 차단" 쿼리는 `COUNT(*)`·`AVG()` **집계**라 LIMIT 과 무관하게 전체 스캔이 맞다 — 게이트 판정 자체는 정당했다. 전체 차단 25건 중 **24건이 집계**. 따라서 "과차단" 프레임을 그대로 수용해 임계를 낮추거나 집계를 통과시키는 방향은 **부하 회귀**다. 결함을 거부 *자체* → 거부 *피드백*으로 **위치 재지정**(F4)했고, 그와 **별개로** 실재하는 오판(순수 LIMIT)만 좁게 되돌린다.
- **근본 RC-1 (L2 거부 피드백)**: EXPLAIN 은 "왜 무거운가"를 이미 안다(`type=ALL`, `key=None`, 스캔 파티션 26/26). 게이트는 그 정보를 **버리고** "필요 컬럼만·WHERE 한정·서버측 집계·LIMIT" 이라는 정적 일반론만 반환했다. 관측된 실패 모드: 모델이 그 넷을 이미 적용한 쿼리를 냈는데 같은 조언을 다시 받고 → 같은 형태 재제출 → 반복 차단. 특히 **전역 집계는 재작성으로 가벼워질 수 없는데** 계속 재작성을 요구받았다.
- **근본 RC-2 (L5 추정)**: MySQL `EXPLAIN.rows` 는 **LIMIT 을 반영하지 않는 스캔 상한**이다. 라이브 실측 — `SELECT * FROM tf_log_05_item LIMIT 5` → rows 13,903,018 → 차단(**실제 5행**). `LIMIT 3` 샘플도 30,493,594 로 차단.
- **① 진단 코칭(AC-0604)**: `_heavy_query_coach()` 신설 — 계획 사실(접근형태·사용/후보 인덱스·스캔 파티션 수)을 싣고 원인별 지시를 붙인다. 인덱스 미사용이면 `get_table_indexes`/`describe_table` 로 **선두 컬럼(로그성 테이블은 시각 컬럼=파티션 키)** 을 확인해 좁히도록, 전역 집계면 "컬럼 축소·LIMIT 으로는 스캔량이 안 준다"는 사실 + `search_tables` 의 `approx_rows` 대안을, 같은 run 2회 이상 차단이면 `confirm_heavy=true` 를 **최후수단에서 명시 선택지로 승격**(좁힐 수 없는 쿼리를 계속 재작성하는 것이 더 나쁘다). 계획 사실이 없는 엔진(MSSQL)은 **기존 문구 그대로 폴백** — 골든 유지.
- **② LIMIT 상한 보정(AC-0605)**: `MySQLDialect.estimate_load()` 가 **조기 종료가 보장되는 형태에만** `min(est, n+offset)` 적용. 게이트 4중 조건 — 단일 plan row + `SIMPLE` / 집계·WHERE·ORDER BY·GROUP BY·HAVING·DISTINCT·UNION·JOIN·서브쿼리·CTE 부재 / `Extra` 에 filesort·temporary 부재 / **문 끝** LIMIT 파싱 성공. 하나라도 어긋나면 **차단 유지**. 보정은 **하향 전용**(이미 가벼운 추정치를 LIMIT 값으로 올리지 않음).
- **계획 취득 1회 유지**: `estimate_load()` 가 (추정치, 계획사실) 쌍을 함께 반환 → EXPLAIN 을 두 번 뜨지 않는다(오버헤드 증가 0). `estimate_load_rows()` 는 `estimate_load()[0]` 위임으로 기존 호출부·테스트 계약 보존.
- **run 카운터 오염 봉인**: `_HEAVY_BLOCK_SEEN` 은 `cfg.CURRENT_RUN_ID` 스코프. **식별자가 없으면(콘솔·eval 경로) 누적하지 않고 항상 1** — 빈 키 하나에 모든 경로가 합산되면 무관한 실행이 남의 차단 횟수를 물려받아 escalation 문구가 잘못 뜬다. 키 수는 256 bound(run 종료 훅 부재).
- **불변**: 임계값·게이트 모드·`confirm_heavy` 신뢰 정책·MSSQL fail-closed·MySQL 추정실패 fail-open 전부 무변경. 정당한 무거운 쿼리는 **그대로 차단**되고 진단만 붙는다. off 경로 무변경. **warn 은 같은 추정기를 공유**하므로 순수 LIMIT 조회의 *허위* 경고가 함께 사라진다(의도 — 오판을 경고로 남기는 것이 목적이 아니다. 진짜 무거운 쿼리의 warn 경고는 유지).
- **프롬프트 shadow 무관(설계 검증)**: 이번 레버는 **도구 결과 문자열**이라 운영자 `WebSystemPrompts` global row 가 코드 `SYSTEM_PROMPT` 를 대체하는 경로(원장 `FR-operator-global-prompt-shadows-code-seals`)의 영향을 받지 않는다. TASK-0304 의 프롬프트 레버(ⓐ~ⓓ)는 그 shadow 아래 있을 수 있으나 이 코드 레버는 도달한다.
- **파일**: `src/modules/dialects.py`(`_parse_explain_plan_facts`·`_limit_scan_cap`·`Dialect.estimate_load`·`MySQLDialect.estimate_load`), `src/modules/tools.py`(`_estimate_explain_load`·`_heavy_query_coach`·`_heavy_block_seen`·gate 분기), `tests/test_query_guard_coaching.py`(신규 19건), `tests/test_query_guard.py`·`tests/test_mssql_load_estimate.py`(스텁 진입점 이동), `docs/{FUNCTION,TASK}.md`.
- **검증**: 신규 19 + 기존 35 PASS. **dogfood(라이브 계획 주입)** — 라이브 EXPLAIN 4건을 새 코드로 판정: 순수 LIMIT 2건(13.9M/30.5M) → **5/3 보정 PASS**, 집계·인덱스미사용 2건 **차단 유지 + 진단 부착**. 라이브 대화 소멸은 **배포 후 실측 필요**(정직 분리).
- **§18.8 적대 패널(codex 3렌즈 backend+security+qa) 결함 9건 흡수 — 초안은 출하 차단이었다**:
  - **[P1] 주석 속 가짜 LIMIT**: `SELECT * FROM huge -- LIMIT 5` 는 MySQL 에 LIMIT 없는 전체 스캔인데 raw 문자열 끝에는 `LIMIT 5` 가 보여 `cap=5` 가 됐다(재현 확인 `guard_ok=True, cap=5`). **내 봉인이 막으려던 부하 회귀를 내가 만들고 있었다.** → 상한은 주석 제거본에서만 인정. 단 주석 제거가 문자열 리터럴을 잘라 blocker(WHERE 등)를 지우는 **역방향** 위험이 있어 blocker·SELECT 개수는 **원본·제거본 양쪽** 검사.
  - **[P1] `SQL_CALC_FOUND_ROWS`**: LIMIT 행을 보낸 뒤에도 전체 결과 행수를 계산하므로 조기 종료가 없는데 blocker 에 없었다. 같은 계열로 `DISTINCTROW`·`STRAIGHT_JOIN` 은 `_` 가 word char 라 `\bdistinct\b`/`\bjoin\b` 에 **아예 매칭되지 않았다**. → 명시 추가(+`SQL_BIG_RESULT`/`SQL_SMALL_RESULT`/`SQL_BUFFER_RESULT`/`SQL_NO_CACHE`/`HIGH_PRIORITY`).
  - **[P2] worst 선택 오류**: raw `rows` 로 고르면 "1,000만행·filtered 0.01%(인덱스 range)" 가 "90만행·filtered 100%(풀스캔)" 을 이겨 **진짜 병목의 인덱스 부재를 숨긴다**. → 실효 행수(`_effective_rows`) 기준.
  - **[P2] 거짓 탈출구 안내**: `AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM=false` 인데 "confirm_heavy 로 호출하면 실행합니다" 라고 안내 → 통하지 않는 우회를 반복 시도. **이 cycle 이 없애려던 루프와 정확히 같은 형태**. → 정책을 coach 에 주입, false 면 안내 자체를 금지.
  - **[P2] 승격 카운터 과발동**: run 단위 카운트라 다른 테이블의 **첫** 쿼리가 남의 차단 횟수를 물려받아 즉시 confirm 권고. → 키를 `run_id|대상테이블` 로 분리.
  - **[P2] 골든 계약 잠식**: facts 없는 엔진(MSSQL)에서 **집계 쿼리면** 정적 폴백을 건너뛰고 새 문구를 반환했다(테스트는 비집계만 검사해 놓쳤다). → 진단·집계 안내를 `worst` 존재 시에만.
  - **[P2] 죽은 스텁**: 기존 MSSQL fail-closed·MySQL fail-open 테스트가 폐기된 `_estimate_explain_rows` 를 스텁해 주입값이 미사용이 됐고, MagicMock 이 우연히 None 을 내어 통과 중이었다. → 새 진입점 스텁 동반.
  - **[P3] `LIMIT 0`** → cap 1(무해한 빈 쿼리를 heavy 로 재차단 가능). → 0.
  - **[P3] warn 골든 — 근거 수용 후 방향 전환**: "warn 무변경" 이라는 **문서가 틀렸다**(코드가 아니라). warn 이 붙이던 그 경고가 곧 이번에 오판으로 판명된 값이므로, 문서를 정정하고 동작을 테스트로 고정했다.
  - **결함 없음 확인(축)**: 계획 정보 노출은 allowlist 검사가 EXPLAIN 보다 먼저라 권한 범위를 넓히지 않음 · 대소문자/개행/다중문 우회 없음(다중문은 상위 `sql_guard`).
- **역검증**: P1 2종 + P2 5종 + P3 2종 재현, **생존 0**. 테스트 19 → **31건**, feature 전체 **2360 passed / 30 skipped**.
- **위험등급**: Major(코어 LLM 도구 경로·거부 로직 — §12.3 2차효과). **Rollback**: 커밋 revert. 부분 무력화는 `AGENT_QUERY_GUARD_MODE=warn|off` 로 게이트 자체를 내리는 기존 노브로 가능.
- **미봉인(명시)**: `scratch_import` 병렬 게이트의 코칭 문구는 범위 밖(LIMIT 보정은 dialect 층이라 자동 적용) · 임계 1M 의 로그 도메인 적합성은 사람 결정(사용자 2026-07-31: 코드만 수정·임계 유지) → 둘 다 원장 기록.
- **Cross-ref**: TASK-0304(코칭 reframe — 이번 결함의 직전 작업) · TASK-0299(MSSQL SHOWPLAN 추정) · TASK-0172(게이트 도입) · 원장 `FR-loadgate-blind-coaching`.

## CHG-20260731T203000-loadgate-postdeploy — 배포 결과·배포본 실증 기록 (문서만)
> `CHG-20260731T184300-loadgate-blind-coaching` 의 배포 후 상태를 원장·TASK·REPORT 에 반영한다. 코드 변경 없음.
- **배포**: PR #1112 merge → main `97af7d27` → `make deploy-web` 전체 스코프. **4서비스 GIT_COMMIT=97af7d27 healthy**(web-a·web-b·ask-worker·insight-worker), post-cutover soak 통과.
- **1차 시도 부분 실패(정직 기록)**: insight-worker 가 300s 내 healthy 미도달 → **워커군 last-good 롤백** → web 만 신코드·워커는 구코드. 이번 수정의 실행 주체가 **ask-worker** 라 그 상태로는 마찰 수정이 라이브에 **미도달**이었다. 원인은 이번 변경이 아니라 기동 직후 외부 datasource 다수 도달 불가(`conn_health down … timeout|blocked_target`, MSSQL 로그인 실패)로 헬스체크가 늦게 붙은 것 — 안정 후 **멱등 재실행으로 성공**(insight-worker 20s 내 healthy). `make` 종료코드가 파이프에 가려 0 으로 보였다.
- **배포본 런타임 실증(ask-worker, 라이브 datasource EXPLAIN)**: 새 심볼 3종 적재 True · `guard_mode=gate`·임계 1,000,000 · ① `SELECT * FROM tf_log_05_item LIMIT 5` → est **13,891,780 → 5 보정 → PASS**(종전 차단) ② `COUNT(*)` → **차단 유지 + 진단**(전체 인덱스 스캔·`key=LogType`·파티션 26개) + 전역집계 사실 + `approx_rows` 대안 ③ `-- LIMIT 5` 주석 위장(§18.8 [P1]) → **차단 유지**(우회 없음).
- **미검증(정직)**: 실제 사용자 대화에서 차단 빈도가 줄고 재작성이 성공하는지 — 다음 audit 의 corroboration 재측정분. 원장 status = `fixed:deployed:unverified-live`.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REPORT,REVIEW}.md`, `docs/LEARNINGS.md`(LRN-20260731-0001).
- **위험등급**: Minor(문서만). **Cross-ref**: `CHG-20260731T184300-loadgate-blind-coaching` · 원장 `FR-loadgate-blind-coaching`.

## CHG-20260803T170000-loadgate-replay-verify — 라이브 재현 A/B 검증 결과 기록 (문서만)
> 부하게이트 봉인이 **실제 대화에서** 마찰을 해소했는지 재현으로 확인하고 원장 status 를 닫는다. 코드 변경 없음.
- **방법**: 배포본 ask-worker(`97af7d27`)에서 원 대화가 무산됐던 같은 조사를 재현. `account_id` 미지정(콘솔 경로)으로 돌려 **라이브 사용자 대화 테이블을 오염시키지 않았다**.
- **결과(BEFORE→AFTER)**: 차단 6→4 · 진단 문구 **0/6 → 4/4** · 전역집계 고지 0→3 · `approx_rows` 안내 0→2 · escalation 0→**2** · 차단 직후 또 차단 4→2 · **조사 목적 무산 → 완수**(17 steps, 6,078자 답변에 원인 + 대안 3종).
- **재작성 궤적(코칭 작동의 직접 증거)**: `접근형태=전체 행 스캔(인덱스 미사용)` 진단 수신 → 대상을 작은 `TF_ErrorLog` 로 전환 + `LIMIT 10` → 성공. 재차단 후 `SequenceID BETWEEN … LIMIT 20` 범위 축소 → 성공 → 실데이터 조회로 답변 완성. 원 대화는 같은 지점에서 형태만 바꾼 재제출이 6회 반복되고 끝났다.
- **한정(정직)**: RC-2(LIMIT 상한 보정) 이 재현에서 **미발동**(모델이 순수 LIMIT 조회를 내지 않음 — 배포본 직접 실측에서만 확인) · 콘솔 경로 부작용으로 `scratch_import` 1회 거부 · **모집단 빈도 감소 미측정**(다음 audit corroboration). `verified` 판정 근거는 **통제된 A/B 재현까지**로 한정한다.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`, `unit/feature-0002-agent-core/docs/{TASK,REVIEW}.md`.
- **위험등급**: Minor(문서만). **Cross-ref**: `CHG-20260731T184300-loadgate-blind-coaching` · `CHG-20260731T203000-loadgate-postdeploy` · 원장 `FR-loadgate-blind-coaching`.

## CHG-20260804T0610-msg-speaker-attribution 답변·질문 메시지에 발화자 귀속 각인 (feature-0003 cycle 교차 참조)
- `src/agent_core.py`: `_lookup_account_username`·`_answer_product_attribution` 신설.
  user 미러 meta 를 1:1 까지 확대(`sender_account_id`/`sender_username`), assistant 미러 4경로
  (정상 답변·max_steps 초과·중단 보존·오류)에 `product_mode/product_id/product_key/product_name` 각인.
- 사유: 발화자가 각인되지 않아 web 이 렌더 시점 대화 설정에서 파생 → 제품 전환·fork 로 과거 발화자가
  사후 변경되는 부정합(사용자 보고). 각인 계약·표시 규칙 정본은 feature-0003 `docs/FUNCTION.md`
  (msg-speaker-attribution) 참조.
- 기존 동작 무변경: `group_chat` 마커 게이트, dedup `mirror_sender_account_id` 전달 조건, 각인 실패
  fail-open. Tests: `tests/test_msg_speaker_attribution.py`(12).

## CHG-20260805T160000-attach-change-false-absence 첨부 변경 사실의 코드-권위 봉인 (A+C+B)
> conversation_audit 마찰 `FR-attachment-change-false-absence` — fork 된 대화에서 사용자가 첨부 8건을 v2 로
> 갱신·4건을 신규 첨부했는데 답변이 "새로 첨부되거나 변경된 파일이 없습니다" 라고 **정반대 단정**을 했다.
> 배포본 재현 결과 프롬프트에는 `★신규` 12·`🔄v2` 8·v1→v2 unified diff 8 이 **정상 주입**돼 있었다
> (실측 재구성 66,131 prompt tokens vs 실제 run 91,054 — 섹션 부재 시나리오와 불일치). 즉 데이터가 아니라
> **부재 단정을 막는 코드-권위 규칙과 리뷰어의 대조 근거가 없던 것**이 결함이다. 답변 직전 라이브 DB 프로브
> 3연속 0행이 있었고, 모델이 그 부재를 **첨부 축으로 일반화**했다.
- `src/agent_core.py`
  - `_ATTACHMENT_TURN_FACTS_CTX` 신설 — 이번 턴 첨부 변경 사실(신규/버전갱신/이월 + 파일명)을
    **한 번 계산해 세 소비자가 공유**하는 request-scoped 채널. 소비자가 각자 재계산하면 부분 실패 시
    서로 다른 수치를 말해 모순의 새 원천이 된다. `compose_system_prompt` **첫 문장**에서 항상 클리어해
    워커 스레드 재사용 시 이전 run 수치의 교차-대화 주입을 원천 차단한다.
  - `_build_attachment_context_section` — 목록 표식(`★신규`/`🔄vN`)과 **같은 판정식**으로 사실을 적재.
    성공 경로(목록 생성 후)에서만 채운다(조기 return 경로에서 채우면 목록 없는 프롬프트에 "N건 첨부됨"
    이 붙어 반대 방향 환각).
  - **(A)** `_build_attachment_authority_directive` — `compose_system_prompt` **말미**(운영자 product/role/
    account row·첨부 섹션·`_GROUNDING_AUTHORITY_DIRECTIVE` 뒤)에 붙는 코드-권위 사실 블록. 부재 단정 금지 +
    "0행은 **DB 축 증거일 뿐** 첨부 불변의 증거가 아니다" 명시 + 신규 0건일 때는 **대칭 진술**(반대 방향
    환각 차단). **평가의 자유는 유지** — "변경은 있으나 처리사항 N 미반영" 은 정당한 결론임을 명시.
  - `_flatten_untrusted_name` — 권위 블록에 들어가는 비신뢰 파일명 평탄화(개행/제어문자 접기 + datamark
    sentinel 제거 + 캡). 권위 블록은 "FACT … OVERRIDE" 문맥이라 개행이 살면 이름이 **새 지시문 줄**로
    읽힌다(§18.8 security 흡수).
  - **(C)** `_build_attachment_turn_manifest` — 사용자 턴 말미의 애플리케이션 계산 매니페스트 한 줄
    (생성 지점 최근접 자리). 그룹 발신자 라벨과 동일 계약 — **LLM 전달용 `_live_user_content` 에만** 붙고
    `_save_message(content=user_message)` 저장본은 원문 불변. 건수만 싣고 파일명은 싣지 않는다.
- `src/modules/redteam.py` **(B, 사용자 지정: "red-team review 가 능동 검출")**
  - `build_attachment_change_facts` + `run_review(attachment_facts=)` + `orchestrate_review(attachment_facts=)`
    — find/verify 두 패스 모두에 사실 블록을 **초안 앞**에 싣는다(초안을 읽기 전에 무엇이 들어왔는지
    확정해야 부재 단정을 모순으로 인식). fresh-context 불변식(feature-0021 ANCHOR §1) 준수 — 넘기는 것은
    assistant 의 추론 과정이 아니라 애플리케이션 계산 사실 몇 줄이다(CONVERSATION REQUEST 와 동급).
  - `REDTEAM_REVIEW_PROMPT` — 부재 단정 ↔ 사실 모순을 `grounding` **BLOCK** 으로 올리는 규칙. 반대 방향
    (없는 첨부를 주장)도 대칭 BLOCK. **평가(불충분·미반영 결론)는 오탐으로 보고 금지** 를 명시해
    리뷰어가 정당한 리뷰 결론을 깎지 않게 했다. 파일명은 `_flatten_untrusted` + 블록 캡.
- 기존 동작 무변경: `★신규`/`🔄vN` 표식·FILE UPDATES diff·인라인 상한·IDOR/sender 스코프 가드 전부 불변
  (dogfood 실측 표식 수 동일). 사실 미전달(bounded 발신자·기존 호출부)이면 블록 미주입.
  프롬프트 비용 +1,810자(+2.7%, 파일명 8건·건당 120자 캡으로 유계).
- Tests: `tests/test_attachment_change_false_absence.py`(24, 배선 seam 포함) +
  `tests/test_grounding_authority_directive.py` 에 허용 supersede 계약 1건 신설.
- **§18.8 패널(backend+qa) BLOCK 흡수 — 설계 변경분**:
  - **부정 단정 전면 제거**: 신규 0건이면 A·C·B 모두 **침묵**한다(변경 전 동작). 사실 원천
    `new_attachment_ids` 가 클라이언트 신호라 "비어 있음 ≠ 첨부 없음" 이고, 초판은 그 상태에서
    "이번 턴 첨부 없음" 을 코드-권위로 선언해 **봉인이 이 마찰을 스스로 생산**했다. 리뷰어의 대칭
    BLOCK 규칙도 제거하고 사실 목록을 **floor(하한)** 로 명시했다.
  - **diff 렌더 여부 분리**: `updated`(이번 턴 diff 실제 렌더) / `updated_no_delta`(버전만 상승) —
    후자는 FILE UPDATES 를 가리키지 않고 `read_attachment` 로 유도한다(xlsx 등 비-text 재업로드에서
    없는 증거를 찾게 만들던 fabrication forcing 제거).
  - **금지 범위 축소**: 금지는 "제공 사실의 부정" 하나. 내용 동일·불충분·미반영 결론은 명시 허용
    (동일 파일 재업로드 시 참인 답변을 막던 결함).
  - **무음 절단 제거**: 리뷰어 블록 캡을 join 후 슬라이스 → **건별 캡 + `외 N건 생략` 표기**.
  - **관측성**: 두 호출부 bare except → `logger.warning`. 사실은 compose 직후 **로컬 스냅샷**으로 들고
    가고(`_att_turn_facts`), contextvar 는 `run_agent` 토큰 튜플에 편입(형제 4종과 동일 수명).
  - 기타: assistant 생성본을 "사용자 제공" 에서 제외 · `carried`→`other` 라벨 정정 · 미사용 `total`
    제거 · 빈 파일명 placeholder · A/B 캡 동치 테스트.
- **위험등급**: Major(§12.3 — 코어 LLM 경로). 사용자 승인 **A+C+B**(AskUserQuestion 2026-08-05) +
  패널 호출 승인(동일 일자). **Cross-ref**: 리뷰 `REV-20260805T160000-attach-change-false-absence` · 원장
  `FR-attachment-change-false-absence` · 리뷰어 기능 소유 feature-0021-redteam-review(코드 거주는 본 feature).

## CHG-20260805T173000-attach-change-panel-absorb §18.8 backend+qa 패널 BLOCK 흡수 (P1 5 · P2 8)
> 선행 `CHG-20260805T160000-attach-change-false-absence` 의 적대 패널 판정 흡수. 패널은 **BLOCK** 을 냈고
> 그 근거가 전부 실재해 설계를 좁혔다. 요지: 초판 봉인은 *부재 단정을 막으려다 스스로 부재를 단정*했다.
- `src/agent_core.py`
  - **부정 분기 제거**: 신규 0건이면 `_build_attachment_authority_directive`·`_build_attachment_turn_manifest`
    모두 **빈 문자열**(변경 전 동작). 사실 원천 `new_attachment_ids` 는 클라이언트 신호라 "비어 있음"이
    "첨부 없음"이 아니다(대화 전환 후 복귀 시 pill 이 `source:"session"` 재수화 · 그룹 발신자 스코프 제외 ·
    비-브라우저 호출). 사실 목록에 **floor(하한, not exhaustive)** 명시.
  - **버킷 4종 분리**: `updated`(이번 턴 diff 실제 렌더) / `updated_no_delta`(버전만 상승 — 비-text
    재업로드 등) / `added` / `other`. 후자는 FILE UPDATES 를 가리키지 않고 `read_attachment` 로 유도한다.
    `created_by_role='assistant'` 는 "사용자 제공" 3버킷에서 제외. 빈 파일명은 id 로 식별.
  - **금지 범위 축소**: "제공 사실의 부정" 하나. 내용 동일·불충분·미반영 결론은 명시 허용.
  - `_format_attachment_fact_names`: 생략을 `외 N건 생략` 으로 **표기**.
  - `_att_turn_facts` 로컬 스냅샷(compose 직후) → C·B 가 원거리 contextvar 재조회를 하지 않는다.
    `_ATTACHMENT_TURN_FACTS_CTX` 를 `run_agent` set/reset 토큰 튜플에 편입. compose 실패 폴백 시 사실 폐기.
  - A/C 호출부 bare `except: pass` → `logger.warning`(봉인이 조용히 사라지면 유일 증상이 마찰 재발).
- `src/modules/redteam.py`
  - `build_attachment_change_facts`: 캡을 **건별**로(join 후 슬라이스 제거 — 파일명 중간 절단 + 뒷줄 소실),
    생략 표기, 신규 0건이면 빈 문자열, delta 유무 버킷 분리. `_ATTACH_FACTS_NAME_CHARS` 신설(A 와 동치).
  - `REDTEAM_REVIEW_PROMPT`: 대칭 BLOCK 규칙 제거, **floor-not-ceiling** 명시(목록 밖 파일 언급을 결함으로
    보고 금지), 내용 판단(동일·불충분)은 리뷰어 관할 밖임을 명시.
- Tests: `test_attachment_change_false_absence.py` 18 → **24**(배선 seam: compose 실측 위치·C 의 user 턴
  합류·B verify 패스·bounded 게이트·0행 경로) + `test_grounding_authority_directive.py` 에 허용 supersede
  계약 1건. **자체 뮤테이션 8종 전건 KILLED**(초판은 6종 생존).
- **위험등급**: Major(§12.3 동일 경로). **Cross-ref**: `REV-20260805T160000-attach-change-false-absence` ·
  원장 `FR-attachment-change-false-absence`.

## CHG-20260805T180000-attach-change-deploy 배포 완료 기록 (문서만)
- **배포**: PR #1155 merge main `70df13a3` → `make deploy-web` 전체 스코프(web 무중단 롤링 + 워커 재빌드
  + gateway reconcile). post-cutover soak 90s 통과, 롤백 0. last-good 은 web `5977f5f7` / agent `aa46e677`.
- **4서비스 running/healthy**: ask-worker·insight-worker `70df13a3`, web-a·web-b `8b46bdec`
  (배포 직후 병렬 세션이 PR #1156 머지·배포. `70df13a3` 이 `8b46bdec` 의 조상이라 4서비스 모두 본 변경 포함).
- **배포본 런타임 실증(ask-worker, 라이브 연결)**: 신규 심볼 6종 적재 · 실패 대화 데이터로 실행 →
  사실 updated 8 / no-delta 0 / added 4 / other 1 · 권위 블록 최종 위치 · 부정 단정 침묵 계약 True ·
  리뷰어 floor 규칙 True · 대칭 BLOCK 제거 True. web /healthz ok·mysql_ok·pg_ok.
- **미검증(정직)**: 실제 사용자 대화에서 부재 단정이 사라지는지 — 다음 audit corroboration 대상.
  원장 status = `fixed:deployed:unverified-live`.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`,
  `unit/feature-0002-agent-core/docs/{TASK,MODIFY}.md`, `docs/LEARNINGS.md`(LRN-20260805-0002/0003).
- **위험등급**: Minor(문서만). **Cross-ref**: `CHG-20260805T160000-attach-change-false-absence` ·
  `CHG-20260805T173000-attach-change-panel-absorb` · 원장 `FR-attachment-change-false-absence`.

## CHG-20260805T190000-read-attach-completeness `read_attachment` 완전성 계약 + 표시 발췌 명시
> conversation_audit 마찰 `FR-read-attachment-preview-looks-partial` — 라이브 실측 중 사용자가
> "assistant 가 첨부를 일부만 조회하는 것처럼 보인다" 고 보고. 진단 결과 **오인 + 실재 결함이 겹쳐** 있었다.
> 보고된 그 호출들(대화 `…843232a3` step 6~8)은 **전부 전문 수신**이었다(1~42/42 · 1~32/32 · 1~28/28,
> tool 메시지 1,485·692·1,213자, 절단 마커 0). 다만 (a) 헤더 문구가 전문인데도 범위 표기라 부분처럼 읽히고
> (b) 단계 보기 패널이 500자 발췌를 절단 표시 없이 렌더하며 (c) 라이브 41회 중 절단 2회는 **모두 모델의
> `max_lines` 자기 제한**이고 그중 1건(327줄 중 250줄)은 **이어 읽지 않고 판단**했다(기본 600줄 캡 발동 0회).
- `src/modules/tools.py`
  - `_tool_read_attachment` 헤더를 **전문/부분으로 분기**: `truncated=False ∧ start_line==1` 이면
    `전체 N줄 **전문**(처음부터 끝까지 아래에 있습니다)`. 그 외는 범위 표기 유지(`start_line>1` 은
    끝까지 읽었어도 앞부분 미열람이라 전문이 아니다).
  - 절단 시 **남은 줄 수**(`남은 N줄 미열람`) + **이어읽기 MUST 계약**: 그 파일 전체를 근거로 삼는
    판단(리뷰·검증·요약·정합성·'문제 없음' 결론) 전에 반드시 이어 읽고, 이어 읽지 않기로 했다면
    **어디까지 확인했는지 답변에 명시**. "방법만 알려주기" 로는 실측 미열람을 못 막았다.
  - 도구 description: `max_lines` 임의 축소 금지 + 절단 시 이어읽기 의무 명시.
- `src/agent_core.py`: `_build_step_result_summary` 가 500자 절단 시 `preview_truncated` +
  `preview_full_chars` 플래그를 붙인다(`_STEP_PREVIEW_CAP_CHARS` 상수화). **표시 상한은 그대로** —
  steps 는 모든 도구가 공유하는 저장 경로라 캡을 올리면 execute_sql 대량 결과까지 함께 커진다.
  해법은 캡 상향이 아니라 **발췌임을 명시**하는 것이다(무음 절단 금지).
- **§18.8 backend+qa 패널 BLOCK 흡수([P1] 2 · [P2] 9 · [P3] 6)** — 초판은 `read_attachment_content`
  를 통째로 stub 해 **실 슬라이싱 로직을 한 번도 태우지 않았고**, 그 사각에 P1 이 있었다:
  - **문자 상한(60,000자) 경로가 정량화된 허위를 냈다.** `end_line` 이 자르기 전 청크 길이라
    "남은 400줄" 이 실제로는 600줄이었고(1,000줄×150자 실측), 이어읽기 시작점이 전달분보다 앞서
    **중간 구간이 어떤 호출로도 오지 않는 구멍**이 됐다. 다른 형태는 `남은 0줄 미열람` +
    `반드시 이어 읽으십시오` 라는 자기모순. → `read_attachment_content` 가 **온전한 줄만** 전달분으로
    인정(조각줄 폐기)하고 `end_line`·`delivered_lines`·`char_capped`·`start_beyond_eof` 를 반환.
    헤더의 모든 수치는 그 값에서만 파생한다. 전달 0줄이면 **"전달된 줄 없음"** 을 명시.
  - **패널 주석이 모델 수신분을 단정했다.** `_cap_tool_result` 가 먼저 자르면 거짓이고, 모델이
    `max_lines` 를 줄인 단계에서는 **진짜 결함을 덮는다**. → 단정 삭제(화면 표시 한정 진술) +
    서버가 모델측 절단을 알릴 때만 반대로 경고(`result_capped_for_model`).
    `preview_full_chars` → `result_chars` 개명.
  - 부분 조회의 앞뒤 미열람 명시 · 이어읽기 탈출구 **조건부화** · 머리말 권위 조항 · EOF 초과 안내 ·
    주석을 표 분기 **바깥**으로(마크다운 표는 `truncated:false` 를 날조) · **길이 폴백**으로 기존
    저장 step 에도 주석 · 인자 전달/도구 게이트/저장→API seam 테스트 · CSS 토큰 정정.
- **정정 2건(§2.5, 초판 주장이 틀렸다)**: ① "CI 가 JS 를 검증하지 않는다" → 저장소에 **29개 headless
  JS 회귀 테스트** 관행이 있다. 관행대로 `tests/headless/test_step_preview_note.js`(17 assert) 신설,
  검증 가능하도록 주석 생성을 `_buildStepPreviewNote()` 로 분리. ② 표시 캡 유지 사유는 "공유 저장
  경로" 가 아니라(도구별 분기는 `tool_name` 으로 가능) **steps 가 폴링으로 반복 전송**되기 때문이다.
- Tests: `tests/test_read_attachment_completeness_contract.py`(**17**, 실 함수 경유) +
  `unit/feature-0003-agent-web-ui/tests/headless/test_step_preview_note.js`(17 assert).
  **구코드 대비 17건 중 12건 FAIL**(초판은 9건 중 5건 — 판별력 검증).
- **위험등급**: Major(§12.3 — 코어 LLM 도구 결과 계약). 사용자 승인 "이어읽기 계약까지 강화"
  (AskUserQuestion 2026-08-05). **Cross-ref**: 표시층은 feature-0003
  (`CHG-20260805T190000-step-preview-excerpt-note`) · 원장 `FR-read-attachment-preview-looks-partial`.
## CHG-20260806T104500-read-attach-deploy `read_attachment` 완전성 계약 배포 완료 기록 (문서만)
- **배포**: PR #1161 merge main `2cab05f3` → `make deploy-web` 전체 스코프. soak 90s 통과, 롤백 0.
  **4서비스 GIT_COMMIT=2cab05f3 running/healthy**. last-good(agent) = `e21606d2`.
- **배포본 런타임 실증(ask-worker)**: ① 전문 → `전체 42줄 **전문**` ② 문자상한(100줄×700자) →
  `1~85번째 줄 / 전체 100줄 (미열람: 뒤 15줄)` + 조각줄 폐기 명시 — **초판이 `남은 0줄 미열람`
  허위를 내던 입력** ③ EOF 초과 → `**전달된 줄 없음**` + 유효 범위 안내 ④ 단계 요약 플래그
  `preview_truncated`/`result_chars`, `result_capped_for_model` True. web-a 정적 자산 반영 확인.
- **배포 절차 기록(정직)**: 1차 시도는 로그 리다이렉트 경로가 사라져 `make` 가 **실행되지 않았다**
  (`PIPE_EXIT=1`). 서비스별 GIT_COMMIT 이 구 커밋에 머문 것으로 발견 — "파이프 exit ≠ 배포 완료"
  규칙이 실제 미배포를 잡은 사례. 재실행으로 성공.
- **미검증(정직)**: 절단 시 모델이 실제로 이어 읽는지(절단 자체가 드묾) · 패널 주석의 실 대화 화면
  배치. 원장 status = `fixed:deployed:unverified-live`.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`,
  `unit/feature-0002-agent-core/docs/{TASK,MODIFY}.md`.
- **위험등급**: Minor(문서만). **Cross-ref**: `CHG-20260805T190000-read-attach-completeness` ·
  원장 `FR-read-attachment-preview-looks-partial`.
## CHG-20260806T110000 도메인 합성 계측 도달 (Minor) — 클러스터 요약 recency 수정은 **적대 검증에서 반증되어 철회**

- **무엇:** `domain_synthesis` 에 `attempted` 카운터 추가 + insight payload allow-list 등재
  (`domain_synthesis_{ran,synthesized,attempted}`) + 기록 게이트를 `if _ds_rep:` 로 완화.
- **왜:** `scan_report["domain_synthesis"]` 는 dict 라 `_telemetry_sweep` 의 스칼라 필터가 통째로
  버린다. 이 워커에서 "계측을 만들고 payload 에 안 실어 무음"이 반복된 **네 번째** 사례다.
  lazy 생성이라 카운터가 0 인 tick 이 대부분이므로, 0 을 안 싣는 게이트는 "요청이 없어 조용함"과
  "배선이 죽어 조용함"을 같은 무음으로 만든다 — `ran=1` 이 그 둘을 가르는 유일한 증거다.

### 철회한 변경 — 클러스터 요약 "최신 1건" (반증 기록)

`cluster_context.fetch_summaries` 를 라벨당 최신 1건(`DISTINCT ON` + `created_at DESC`)으로 좁히려
했다. 근거는 "같은 라벨의 여러 행 = 클러스터 구성이 바뀐 **버전**이고, 소비가 recency 를 안 봐서
옛 버전이 뽑힌다(1,759 그룹 중 9건)" 였다. **적대 패널이 라이브 데이터로 그 전제를 반증했다**:

- 다중행 26 그룹을 현재 `rag_objects` 클러스터링과 대조하면 **5 그룹이 "버전"이 아니라 동시에
  살아있는 서로 다른 클러스터**(라벨 충돌)다. 선택이 바뀌는 9건 중 **4건이 그 경우**다.
- 예: `web_statistics · 활성 사용자 · stat_active` 의 두 행은 요약 **내용이 다르다** — 유지되는 쪽은
  "재계산 및 이력"(멤버 14), 버려지는 쪽은 "일일 활성 사용자 통계 2012~2023 스냅샷"(멤버 79).
  62초 먼저 적재됐다는 이유로 79-멤버 클러스터 설명이 답변 근거에서 영구히 사라진다.
  이것은 중복 제거가 아니라 **내용 손실**이다.
- 객관 지표(선택된 요약의 `member_count` vs 그 라벨의 현재 테이블 수) — 총 편차
  **339 → 645(1.9배 악화)**, 정확 일치 그룹은 6 → 6 으로 그대로. 개선 3 · 악화 5.
- 부수 반증: `created_at` 은 "현재 유효한 구성"의 대리변수가 아니다. `_summary_put` 의 조건부
  UPDATE(`l1_version`/`evidence_version`/`label` 중 하나라도 달라야 갱신) 때문에 구성이 그대로면
  시각이 안 바뀌고, 캐시 적중 시엔 writer 가 아예 호출되지 않는다. 실제로 44-멤버를 기술하는 행이
  5-멤버 행보다 **오래된** 그룹이 라이브에 있다.

**남은 진짜 문제(이번 범위 밖, 별도 판단 필요)**:
- 라벨 충돌 자체 — 같은 datasource 안에서 `메일 시스템`·`경매 시스템` 이 각 7개 스키마에 재사용되고,
  테이블명 하나가 24개 eff-schema 에 매칭된다. 중복 주입의 **지배적 벡터는 크로스-스키마**이고,
  `render` 가 `[label]` 만 출력해 스키마를 구분하지 않는다.
- 형제 소비자 `domain_synthesis.cluster_inputs` 에도 dedupe·recency 가 없어 이미 오염된 값이
  답변 프롬프트에 실린다(`gunzgame` 저장값 45/329 vs 라벨당 최신 기준 42/306).
- `_matched_clusters` 의 `LIMIT 200` 에 `ORDER BY` 가 없어 다중 스키마 팬아웃 시 어느 200개가
  오는지 비결정적(기존 결함).

이 셋은 "소비 시 최신 1건" 으로는 풀리지 않는다 — 라벨 네임스페이스 설계 문제이므로 별도 cycle 에서
다뤄야 한다. 잘못된 방향으로 한 줄 고치는 것보다 실측 반증을 남기는 편이 낫다고 판단했다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `src/modules/domain_synthesis.py` | `attempted` 카운터(LLM 콜 직후·저장 판정 앞) |
| `src/modules/insight.py` | payload `domain_synthesis_{ran,synthesized,attempted}` + 게이트 `if _ds_rep:` |
| `tests/test_domain_synthesis.py` | attempted 를 **동작으로** 단정(소스 순서 검사는 변이 M4 를 통과시켰다) · payload 도달 · 0-tick 기록 · insight 호출 예외흡수 AST 판정 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 0-tick 기록으로 로그 증가 | insight cycle 로그는 tick 당 1줄이고 키 3개 추가일 뿐 — 라인 수는 불변 |
| `ran=1` 이 sweep 병합에서 합산됨(datasource 순회) | int 합산 규약대로 "몇 번 돌았나"가 되어 의미가 보존된다 |
| 계측만 늘고 소비가 없음 | 이 값들은 cycle 로그 → `bin/perf-snapshot.sh` 수집 경로에 그대로 실린다 |

### 이번 cycle 제외 (사유 명시)

`shared/model_catalog.py` 의 유령 taxonomy 2건(`metadata_summary`·`metadata_prompt_gen` — 호출부 없음,
전체 기간 사용 0건) 정리는 **제외**한다. `shared/**` 는 §13.2.2 F2 단일 mutator 대상인데
`ai/claude/feature-0003-usage-records` 가 같은 파일을 편집 중이다(cycle-init 핫스팟 경고). 그 세션
머지 후 별도 처리한다 — 화면 영향은 없다(라이브 데이터가 없으면 표시되지 않음).

### 배포 scope
워커(insight). `make deploy-all`.
## CHG-20260806T170000 라벨 네임스페이스 — 죽은 클러스터 배제 · 스키마 표기 · 결정적 매칭 (Minor)

- **무엇:** ① L3 도메인 합성 입력을 **현재 살아있는 클러스터**로 제한(`live_cluster_labels` —
  `rag_objects` ∪ `routine_objects`) ② 답변 근거 렌더에 스키마 표기 ③ 매칭·요약 조회 결정적 정렬.
- **왜(라이브 실측 2026-08-06):** `cluster_summaries` 는 member_set_hash 별로 누적돼 클러스터가
  재구성돼도 옛 행이 남는다. 그 전부가 L3 재료가 되어 `cluster_count`/`member_count` 가 부풀려진 채
  `_domain_line` 을 통해 **사용자 답변 프롬프트에 그대로** 실린다("그룹 90개 · 멤버 887개 중 …").
  `atum2_db_1` 저장값 90행/887멤버 ↔ 실제 유효 **84행/770멤버**, `gunzgame` 45/329 ↔ **36/257**.

### ⚠ 실측 수치 정정 (적대 패널 반증)

초판은 사망 요약을 **933행(50.6%)**, `atum2_db_1` 을 **81% 사망**이라고 적었다. **틀렸다.**
`live_cluster_labels` 가 `rag_objects` 만 봤기 때문이다 — 클러스터링은 라벨을 멤버 종류에 따라
**다른 테이블에 역기록한다**(테이블→`rag_objects`, 루틴→`routine_objects`). 루틴으로만 이뤄진
클러스터는 `rag_objects` 에 아예 없다.

| | 초판(rag 만) | 정정(rag ∪ routine) |
|---|---|---|
| 사망 판정 | 933행 (50.6%) | **63행 (3.4%)** |
| `atum2_db_1` 유효 | 17행 / 196멤버 | **84행 / 770멤버** |
| `gunzgame` 유효 | 25행 / 147멤버 | **36행 / 257멤버** |

버려질 뻔한 933행 중 **870행(93%)이 살아있는 루틴 클러스터**였다. MSSQL 은 루틴이 압도적이라
(`atum2_db_1`: 라벨 달린 루틴 865 vs 테이블 115) 그대로 나갔으면 도메인 요약이 그 DB 의 프로시저
표면을 통째로 못 본 채 재합성됐을 것이다 — 직전 cycle 이 반증당한 **내용 손실·편차 악화를 그대로
재현**하는 결과였다.

교훈: 이 저장소의 "현재 유효성" 정본은 한 테이블이 아니다. 멤버 종류별로 저장처가 갈리는 구조에서는
**한쪽만 보는 유효성 판정이 다른 쪽을 전멸시킨다**.

### 설계 — 왜 "현재 유효성"이고 "최신"이 아닌가

직전 cycle 에서 같은 증상에 **"라벨당 최신 1건"** 을 적용하려다 반증됐다(다중행의 상당수가 버전이
아니라 **동시 생존하는 다른 클러스터**였고, 최신만 남기면 79-멤버 클러스터 설명이 사라지는 내용
손실). 이번에는 판정 축을 시간이 아니라 **현재 클러스터링에 존재하는가**로 둔다:

- 동시 생존 클러스터는 **둘 다 살아있으므로 둘 다 남는다** — 직전 반증이 적용되지 않는다.
- 정본은 `rag_objects` ∪ `routine_objects` 의 `semantic_cluster_label`(매 pass 역기록).
- `rag_objects` 쪽 조인 키는 반드시 `effective_schema` 를 거친다 — MSSQL 은 `schema_name` 이
  리터럴 'dbo' 라 그대로 비교하면 한 건도 매칭되지 않는다(이 함정으로 1차 실측이 orphan 을 74.2%
  로 잘못 셌다). `routine_objects.schema_name` 은 이미 eff-schema 라 변환이 필요 없다.
- 실패는 **fail-closed**(합성 skip, 다음 pass 재시도), 라벨 0 은 **로그를 남긴다** — 조용히 건너뛰면
  그 스키마가 pass cap 을 계속 물어 뒤의 요청까지 굶는다(head-of-line).

기존 부풀려진 `domain_summaries` 5건은 필터로 `cluster_set_hash` 입력이 달라져 **자동 재합성**된다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `src/modules/domain_synthesis.py` | `live_cluster_labels`(rag ∪ routine) + `cluster_inputs` 필터(실패=skip, 0=로그) |
| `src/modules/cluster_context.py` | 소비 쿼리에 `schema_name` 동반·`member_set_hash` tie-break · `render` 가 `[스키마] 라벨` · 매칭 조회 결정적 `ORDER BY` |
| `tests/test_domain_synthesis.py` | 죽은 클러스터 배제 · **루틴 전용 클러스터 생존** · 두 저장처 union · fail-closed · 0-라벨 로그 |
| `tests/test_cluster_grounding.py` | 스키마 표기 · **라벨이 구분자를 품는 경우** · 하위호환 · tie-break · 결정적 매칭 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 유효성 정본을 한쪽만 봐서 전멸 | rag ∪ routine union + **루틴 전용 클러스터 테스트**(픽스처가 저장처를 분리해 전제를 복제하지 않는다) |
| effective_schema 불일치 | 조인을 그 함수로 통일 + 테스트. 라이브로 후보 선별(5,911→115행)·유효행 수 확인 |
| 과잉 필터 | 정합 상태 무손실을 테스트로 단정. 라이브 재실측으로 84/770·36/257 확인 |
| 프롬프트 형식 변경 | 5번째 원소 부재 시 기존 형태(하위호환) + 라벨 내부 `" · "` 와 충돌하지 않는 구획 |

### 알려진 잔여 (이번 범위 밖)

- **답변 경로의 스키마 내 동명 다중행**: 같은 `(scope, schema, label)` 에 여러 행이 남아, 정렬이
  더 크고 오래된 죽은 행을 1등으로 뽑는 그룹이 라이브에 12건 있다. 스키마 표기로는 구분되지 않는다
  (head 가 동일한 두 줄이 나온다). 답변 경로에도 같은 유효성 필터를 적용하는 것이 자연스러운 다음
  수순이나, 직전 cycle 에서 이 경로를 건드렸다가 반증당했으므로 **①이 라이브에서 검증된 뒤** 별도
  cycle 로 다룬다.
- **케이스만 다른 스키마 공존**(`api`/`API`, `web_log`/`Web_log` 등 `mysql-42371f8d92bc`): 소문자
  쪽 요약 7건이 정확 일치 비교에서 죽은 것으로 판정된다.
- 매칭 상한(200)에 닿을 때 `object_key` 사전순 절단이라 뒤쪽 스키마가 계통적으로 배제된다
  (이전엔 무작위 배제 — 결정성은 개선, 편향은 신규).

### 배포 scope
워커(insight) + web. `make deploy-all`.
## CHG-20260806T160000-attach-delivery-tool 첨부 전달을 답변 예산에서 분리 — `update_attachment` 도구 + 패치 전달
> conversation_audit 마찰 `FR-attach-delivery-truncated-by-output-cap` — 답변이 "6개 파일을 전부
> 갱신했습니다" 라고 했으나 실제 생성된 새 버전은 **1건**(대화 `…1d8ed346`, run `…2fd932dc`).
> `completion_tokens = 100,000` = 출력 상한 정확히 도달. 모델이 요약을 먼저 쓰고 파일 전문 6개를
> 이어 붙이다 잘렸고, 완성된 `attachment-edit` 블록은 첫 파일 하나뿐이었다. 서두의 "전부 갱신" 은
> 잘리기 **전**에 쓰여 그대로 남았다. 부수 사실: `_ASSISTANT_EDIT_COUNT_CAP=5` 라 6건은 절단이
> 없었어도 하나는 못 갔다.
> **사용자 지시(2026-08-06)**: "첨부된 파일 수정은 completion_tokens 과 별개로 작동되어야 합니다.
> 가장 적절한 대안이나 구조개선을 검토해줄 수 있을까요?" → 증상 대응(감지·리뷰·순서) 대신 **전달
> payload 를 답변의 출력 예산에서 분리**하는 구조 개선으로 방향 전환. 승인 범위 = ①+②.
- **① 도구 기반 전달** `src/modules/tools.py` `update_attachment` + `src/agent_core.py`
  `update_attachment_content` — 파일마다 **독립 턴의 출력 창**을 쓰고, 성공/실패가 즉시 되돌아와
  모델이 **실제 성공분만** 주장할 수 있다(L2 자기교정). 권한 경계는 `read_attachment` 와 동일 스코프,
  생성은 **블록 경로와 같은 materialize** 를 태워 가드 전부 공유(도구만 느슨해지면 그게 취약점).
  run 당 `_ATTACHMENT_UPDATE_RUN_CAP=20`, 본문 1MB. 실패 사유는 materialize 의 skip 사유를 그대로
  모델에 전달(`skipped` out-param 신설).
- **② 패치 전달** `src/modules/patch_apply.py`(신규) — unified diff 를 서버가 적용. 이번 건의 실제
  변경은 몇 줄인데 8.5KB 전문을 재생성하고 있었다. **fail-closed**: 문맥 불일치·모호한 다중 일치·
  겹치는 hunk·알 수 없는 접두·**선언 길이 불일치**·**문맥 없는 hunk** 를 전부 거부하고, 하나라도
  실패하면 아무것도 적용하지 않는다. 원본의 지배적 줄바꿈(CRLF/LF)을 보존한다.
- **③ 절단 감지** `finish_reason` 은 종전 코드 **어디에서도 읽지 않았다**. 이제 포착해 초안 확정
  시점에 latch 하고, 잘렸으면 답변 말미에 사용자 경고를 붙이며 red-team 에 사실로 넘긴다.
- **red-team 포착** `src/modules/redteam.py` `build_delivery_facts` — 실제 생성 건수 + 절단 여부를
  초안 **앞**에 실어 "N개 갱신했다는데 delivered 가 적으면 `honesty` BLOCK". `delivered` 는
  **floor**(블록 경로는 리뷰 이후 materialize 라 미집계)임을 명시해 정직한 혼합 턴 오탐을 막는다.
- **프롬프트** 도구 우선 전달 + "성공 응답을 받은 파일만 갱신했다고 말하라" + "전달 먼저, 요약 나중".
  블록 경로는 **폴백으로 강등**하고 `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` 상호참조도 함께 갱신.
- **§18.8 security + backend/qa 패널 BLOCK 흡수([P1] 4 · [P2] 9 · [P3] 6)**:
  - **[P1] 도구로 만든 첨부가 다운로드 칩에 안 나온다.** materialize 는 `MetaJson.message_id` 로
    말풍선 칩을 붙이는데(`_load_assistant_attachments_by_message` 가 `mid<=0` 을 버린다) 도구 호출
    시점엔 답변이 저장 전이라 0 이 들어갔다. **파일은 만들어졌는데 사용자에겐 아무것도 안 보이고**,
    도구 결과·절단 경고가 하필 "칩으로 확인하세요" 라고 가리켰다 — 고치려던 claim/reality gap 의
    재생산. → 전달 id 를 run 채널에 모아 `result["tool_delivered_attachment_ids"]` 로 내보내고,
    답변 저장 후 `_bind_tool_delivered_attachments`(feature-0003 신설)가 message_id 에 바인딩한다
    (워커·web inproc 양쪽). 워커의 "블록 없으면 조기 반환" 도 도구 전달분을 고려하도록 수정.
  - **[P1] 패치 적용기 무음 오적용 3종**(패널이 실행으로 실증): `-N,0` 문맥 없는 삽입이 **한 줄 앞**
    (EOF append 가 마지막 줄 앞으로) · 선언 길이(`-l,c`)를 파싱만 하고 안 써서 **잘린 패치가 부분
    적용되고 성공 반환**(이 cycle 이 없애려는 실패의 재현) · 마지막 hunk 뒤 산문이 파일에 기록.
    → 선언 길이를 **본문 경계의 권위**로 삼고, 문맥 없는 hunk 는 거부한다.
  - **[P1] 절단 경고가 red-team revise 로 지워짐** — revise/rederive 도 `_call_llm` 을 타 finish_reason
    이 'stop' 으로 덮인다. 새 리뷰 규칙이 truncated 일 때 BLOCK 을 지시하므로 **경고가 필요할수록
    확실히 사라졌다**(자기무력화). → 초안 확정 시 latch, 수정본 채택 시에만 재판정.
  - **[P2]** execute_tool 라우팅/시그니처 계약/워커 배선 테스트 신설 · CRLF 보존 · 패치 후행 개행
    허용 · 예외 원문 비노출(CODE_REVIEW §2.7) · `web.app` import 실패 로그 · DELIVERY FACTS floor
    프레이밍 · 프롬프트 모순 해소.
- Tests: `tests/test_attachment_delivery_tool.py`(33) + `tests/test_patch_apply.py`(23).
  **뮤테이션 9/9 KILLED**(선언길이·zero-context·줄바꿈·라우팅·전달id·latch·워커바인딩·floor·예외노출).
- **위험등급**: Major(§12.3 — 코어 LLM 경로 + **모델이 첨부 저장소에 쓰는 첫 도구**).
  사용자 승인 "①+② 한번에"(AskUserQuestion 2026-08-06). **Cross-ref**: 표시/저장층 feature-0003
  (`CHG-20260806T160000-attach-tool-chip-binding`) · 원장 `FR-attach-delivery-truncated-by-output-cap`.

## CHG-20260806T173000-attach-delivery-deploy 첨부 전달 구조 개선 배포 완료 기록 (문서만)
- **배포**: PR #1178 merge main `d04ab2f2` → `make deploy-web` 전체 스코프. soak 통과, 롤백 0.
  **4서비스 GIT_COMMIT=d04ab2f2 running/healthy**. 병렬 세션 머지로 rebase 1회(FUNCTION.md 말미
  append 충돌 → 양쪽 union 보존), rebase 후 컨테이너 정본 회귀 재실행 실패 0.
- **배포본 런타임 실증(ask-worker)**: `update_attachment` 도구 노출·라우팅·datasource-free 전부 True ·
  `_bind_tool_delivered_attachments` 적재 True · 절단 감지 + latch True · 패치 정상 적용 ·
  **잘린 패치 거부**(패널 P1 재현 입력) · **문맥 없는 삽입 거부**(패널 P1 재현 입력) · DELIVERY FACTS
  floor 프레이밍 True.
- **미검증(정직)**: 모델이 실제로 도구를 채택하는지 · 다중 파일 전달 완주 · **다운로드 칩 실 렌더**
  (패널이 잡은 P1 이라 최우선) · 패치 적용 성공률. 원장 status = `fixed:deployed:unverified-live`.
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`,
  `unit/feature-0002-agent-core/docs/{TASK,MODIFY}.md`.
- **위험등급**: Minor(문서만). **Cross-ref**: `CHG-20260806T160000-attach-delivery-tool` ·
  원장 `FR-attach-delivery-truncated-by-output-cap`.

## CHG-20260807T130000-attach-delivery-live-measure 첨부 전달 라이브 실측 기록 (문서만)
- **실측**: 배포본(main `d04ab2f2`) web UI 를 PB-0008(실 Windows Chrome)로 조작해 4파일 동시
  갱신 1턴을 수행. **도구 채택 4/4 · 완주 4/4 · 다운로드 칩 4/4 렌더(패널 P1) · 패치 1회차
  4/4 · 답변↔실재 일치**. ★사용자 요구 구조 조건인 **completion_tokens 분리**를 수치로 확증
  (4×7KB 전달의 답변 completion 합 **1,973**).
- **원장**: `FR-attach-delivery-truncated-by-output-cap` → **`fixed:deployed:verified`**.
- **미실측(정직)**: `read_attachment` 완전성 계약(2턴 모두 모델이 미호출 → 관측 불가) ·
  DELIVERY FACTS 의 BLOCK 경로(happy path 라 조건 미발생). 두 항목은 `unverified-live` 유지.
- **부수 발견 2건 원장 신규 등재(수정 미착수)**:
  `FR-redteam-attach-excerpt-cap-false-grounding-block`(리뷰어 발췌 1,200자 head-only →
  캡 밖 근거가 무근거로 보임 → grounding 은 rederive 비적격 → `revise_failed` → 정확한 답변에
  경고 배너) · `FR-datasource-eager-connect-blocks-datasource-free-turn`(런 시작 primary
  datasource 선연결이 무조건 전제 → datasource-free 턴도 회로차단에 중단).
- **파일**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`,
  `unit/feature-0002-agent-core/docs/test-runs.d/REV-20260807T130000-attach-delivery-live.{md,png}`,
  `unit/feature-0002-agent-core/docs/{TASK,MODIFY}.md`.
- **위험등급**: Minor(문서만·코드 변경 0). **Cross-ref**: `CHG-20260806T173000-attach-delivery-deploy`.

## CHG-20260807T160000-redteam-attach-excerpt-anchoring 리뷰어 첨부 발췌를 초안 인용 구간에 앵커
- **문제**(FR-redteam-attach-excerpt-cap-false-grounding-block, 라이브 실측 run
  `20260807040816-3a3b6f52`): 리뷰어에게 주는 첨부 발췌가 `body[:1200]` **head-only** 라, 파일
  뒤쪽을 근거로 쓴 **정확한** 답변이 무근거로 보여 grounding BLOCK 을 맞았다. `grounding` 은
  rederive 적격 축이 아니어서(`_REDERIVE_ALWAYS_AXES=("sql",)`) 텍스트 재작성으로 해소가
  구조적으로 불가능 → `stop_reason=revise_failed` → **옳은 답변에 "자가 검증 미해소" 배너**.
- **수정 3축** (`modules/redteam.py`):
  1. `_draft_probes()` + `_select_excerpt_spans()` — 발췌를 **초안이 인용한 구간**에 앵커.
     예산은 동일(파일당 1,200자), 쓰는 위치만 변경. 앞머리 창은 항상 유지(파일 정체성).
     probe = 마크다운 장식 벗긴 24자+ 줄 + 식별자성 12자+ 토큰. `str.find` 만 사용(정규식 미생성).
  2. 절단 표기를 `[TRUNCATED]` → `[PARTIAL EXCERPT — SHOWN lines … of N; NOT SHOWN lines …
     (unknown to you, not absent)]` **구조적 사실**로. `[FULL FILE SHOWN]` 일 때만 부재 추론 허용.
     `_line_starts`/`_count_lines` 는 말미 개행이 유령 줄을 만들지 않도록 규약 통일 — 아니면
     coverage 가 **존재하지 않는 줄을 미표시로 보고**한다(구현 중 실제 발생, 즉시 교정).
  3. `REDTEAM_REVIEW_PROMPT` 규칙 — 기존 규칙은 본문 없는 "ALSO ATTACHED" 만 다뤄 본문이
     실린 파일의 부분 발췌엔 적용 안 되는 것으로 읽혔다. 그 구멍 + "no tool runs 를 첨부 근거
     부재로 읽지 말 것"(첨부는 도구가 아니라 프롬프트로 도달). **과교정 방지**: 보여준 줄과
     **모순되는** 주장은 여전히 BLOCK.
- **배선**: `build_evidence_digest(..., draft=)` 로 전달. `orchestrate_review` 3지점 —
  최초 `draft_answer`, rederive 근거 누적 후 `final_answer`, **수정본 채택 후 재앵커**
  `final_answer`. 재앵커가 없으면 verify 가 수정본의 인용 구간을 못 봐 같은 BLOCK 이 재발한다(비수렴).
- **검증**: 신규 27건 + 기존 계약 1건 강화 · **뮤테이션 12/12 KILLED** · 호스트 전량 회귀
  3,998 collected(실패는 선재 7건뿐, `git stash` 확인) · ruff clean · 배포본 컨테이너 재현
  (수정 전 마커 부재 → 수정 후 포함). 뮤테이션 1차 3건 생존 → 테스트 결함 3개 교정.
- **§18.8 적대 패널(backend+qa)이 초판을 반려 — BLOCKING 4 · MAJOR 4 · MINOR 7 전건 흡수**.
  패널 판정 요지: *초판은 원 버그를 세 경로로 재도입했다.*
  1. **예산 소멸(A)** — 앞머리 420자만 쓰고 나머지 780자를 probe 히트에만 배정, 히트 0이면
     **버렸다**. 한국어 답변 ↔ 영문 파일은 verbatim 매칭이 구조적으로 0건이라 전달량이
     1,200 → 420자로 줄었다. 실측: 117줄 파일의 28행 근거를 구 배포본은 보여줬고 초판은 감췄다
     (미탐 62% → 87%). 해소: **남은 예산 전액을 앞머리 연장에 소진** + 꼬리 창 예약 →
     `sum(span) == min(본문, 캡)` 불변식. 원 마찰(꼬리 인용)이 이제 **패러프레이즈·초안없음**
     에서도 도달한다(초판은 verbatim 일 때만).
  2. **char↔line 불일치(B)** — span 은 문자, coverage 는 줄이라 1줄 minified JSON 이
     `NOT SHOWN lines none`(=다 봤다)으로 보고됐다. 해소: **문자 기준이 권위**
     (`you were given N of M chars`), 줄 범위는 **완전히 보인 줄만**.
  3. **총예산 절단(C)** — 파일당 캡으로 `[FULL FILE SHOWN]` 을 붙인 뒤 전체 캡이 본문을 잘랐다
     (761자 첨부 3개로 재현). 해소: **블록 단위 적재**, 안 들어가면 `ALSO ATTACHED` 강등.
  4. **`ALSO ATTACHED` 날조 보호(D)** — "no tool runs 는 근거 부재가 아니다" 규칙이, 본문이
     프롬프트에 **없고** `read_attachment` 로만 도달하는 파일까지 덮어 **날조 탐지가 가장 확실한
     경우를 무력화**했다. 해소: 면책을 **발췌가 있는 파일 한정**으로 좁히고, ALSO ATTACHED 는
     "도구 0 + 구체적 주장 = grounding 결함" 을 명시.
  MAJOR: 상류 `truncated=True` 파일의 총량 단정(→ `M+` 하한 + `SOURCE ALSO TRUNCATED`) ·
  모순 규칙의 축 한정 부재(→ `grounding`/`honesty` 로 한정) · **본문의 coverage 마커 위조**
  (→ `_neutralize_digest_markers`) · sanitized/raw 문자수 혼재(→ sanitized 통일).
  MINOR: 죽은 digest 재계산 제거 · 대소문자 무시 폴백 · strip 후 빈 본문 manifest 라우팅 ·
  창 padding 양측 유지.
- **패널이 잡은 내 거짓 문서 주장 2건 정정**: FUNCTION.md "예산 불변 — 쓰는 위치만" ·
  "`draft=""` 는 기존과 동일(회귀 없음)", SECURITY.md §41 "노출량 동일". *캡*은 불변이었지만
  *전달량*은 1/3로 줄었다 — 노출 축만 보고 안전을 결론내면 **검출력 축**을 놓친다는 것을 §41 에 남겼다.
- **검증(패널 반영 후)**: 신규 39건 + 기존 계약 1건 강화 · **뮤테이션 24종 중 23 KILLED**
  (1건은 등가 뮤턴트로 테스트에 근거 기록) · 호스트 전량 회귀 3,998 collected(실패는 선재
  `test_share_redaction_invariant.py` 7건뿐) · ruff clean.
  뮤테이션이 테스트 결함을 5회 적발했다(모듈 grep 이 규칙 삭제를 가림 · probe 미매칭 fixture ·
  창 병합으로 상한 미발동 · 꼬리 창이 대소문자 폴백을 가림 · 예산 소진이 개수 상한을 가림).
- **위험등급**: Major(리뷰어 프롬프트 = 코어 LLM 경로). 신규 권한·스키마·엔드포인트 변경 0.
- **Cross-ref**: 원장 `FR-redteam-attach-excerpt-cap-false-grounding-block` ·
  `CHG-20260807T130000-attach-delivery-live-measure`(이 결함이 발견된 실측) · SECURITY §41.

## CHG-20260811T090000-redteam-attach-excerpt-deploy 발췌 앵커링 배포 완료 기록 (문서만)
- **배포**: PR #1196 merge main `4c7a8f27` → `make deploy-web` 전체 스코프. soak 통과, 롤백 0,
  4서비스 `GIT_COMMIT=4c7a8f27` running/healthy. 병렬 세션 머지로 rebase 1회(`redteam.py` import
  블록 union 해소) 후 **전량 회귀·뮤테이션 재실행**(23/23 KILLED, 실패는 선재 7건뿐).
- **배포본 런타임 실증(ask-worker)**: 원 마찰(꼬리 근거)이 verbatim·패러프레이즈·초안없음 셋 다
  도달 · 예산 소진 1,200/1,200 · 1줄 minified JSON 허위 완전성 주장 없음 · 761자 첨부 5개에서
  거짓 FULL 라벨 0 + 전 파일 고지 · 면책 경계 4종 탑재.
- **미검증(정직)**: 라이브 대화에서 **정확한 답변의 경고 배너가 실제로 사라지는지**. 원장
  status = `fixed:deployed:unverified-live`.
- **위험등급**: Minor(문서만). **Cross-ref**: `CHG-20260807T160000-redteam-attach-excerpt-anchoring`.

## CHG-20260811T110000-redteam-excerpt-budget 라이브 실측이 잡은 발췌 예산 결함 2건
- **발견 경로**: 앵커링 배포(`4c7a8f27`) 후 **원 대화에서 동일 시나리오를 반복**하는 라이브 실측.
  BEFORE(`20260807040816-3a3b6f52`) = `revise/1 block/revise_failed`. AFTER(`20260811025604-5386c583`)
  = **여전히 BLOCK**. 리뷰어 근거 "그 파일 내용이 제시되지 않았습니다" 는 **사실이었다** —
  코드로 재구성해 확인했다. 배포본 실증(합성 입력)만으로는 못 잡는 결함이었다.
- **결함 1 — 겹치는 인용 창의 예산 이중과금**: `budget` 을 창 단위로 차감해, 같은 영역을 가리키는
  probe 두 개(`USER-EDIT-V4-TAIL-MARKER`·`sigma-lynx-4471`)가 예산을 두 번 먹고 실제 전달은
  **862/1,200 자**에 그쳤다. "예산을 남기지 않는다" 계약이 조용히 깨진 것 — 패널이 잡은 결함(A)의
  다른 얼굴이다. 해소: 회계를 **병합된 union** 기준으로(`_used()`), head 연장은 병합 후 수렴 루프.
- **결함 2 — 조립 순서가 입력 순서(첨부 id) 고정**: 예산이 모자라면 **초안이 논하고 있는 바로 그
  파일**이 통째로 강등됐다. 라이브에서 probe_a(질문 대상·id 최신)가 ALSO ATTACHED 로 밀리고
  probe_b 만 본문이 실렸다. 강등 자체보다 **무엇을 강등하는가**가 문제였다. 해소: **관련성 정렬**
  (초안 probe 적중 수 내림차순) + 파일당 지분 **비례 축소**(floor `_ATTACH_MIN_PER_FILE_CHARS`,
  블록 헤더 오버헤드 선공제) — 통째 강등만 쓰면 뒤 파일들이 사라져 선행 봉인이 막으려던 false
  positive 가 되살아난다.
- **부수(수정 중 기존 테스트가 적발)**: 1-pass 적재는 강등이 루프 도중 발생해 매니페스트 예약이
  항상 과소였고, 마지막 파일이 강등되면 매니페스트가 최종 절단에 잘려 **그 파일이 digest 에서
  증발**했다. 해소: **2-pass 적재**(전량 가정 → 초과 시 관련성 낮은 순으로 강등하며 수렴).
- **검증**: 신규 5건(라이브 재현 입력 그대로) 포함 44건 · **뮤테이션 18/18 KILLED** ·
  호스트 전량 회귀 3,998 collected(실패는 선재 7건뿐) · ruff clean.
  실측 입력 재현: probe_a 본문 적재 True · v4 마커 digest 포함 True · 4파일 중 3파일 본문 +
  전 파일 고지 · 예산 1,200/1,200(draft 없음·서술·꼬리 인용 3형태 전부).
- **위험등급**: Major(리뷰어 evidence 조립). 신규 권한·스키마·엔드포인트 변경 0.
- **Cross-ref**: `CHG-20260807T160000-redteam-attach-excerpt-anchoring` ·
  원장 `FR-redteam-attach-excerpt-cap-false-grounding-block`.

## CHG-20260811T120000-excerpt-live-measure 발췌 앵커링 라이브 실측 기록 (문서만)
- **원 축 PASS**: 격리 조건(단일 첨부 8,827자, 꼬리 offset 8,811 인용 질의)에서 답변이 정확했고
  red-team `pass · 0 block · resolved` → **배너 없음**. 원 마찰 소멸.
  원장 `FR-redteam-attach-excerpt-cap-false-grounding-block` → `fixed:deployed:verified`(원 축 한정).
- **잔여(정직)**: 다중 첨부 + 버전 비교 시나리오는 여전히 BLOCK. 원인은 다른 둘이며 신규 등재 —
  `FR-redteam-digest-lacks-prior-attachment-version`(리뷰어는 현재 버전만 받는다) ·
  `FR-redteam-verify-pass-ignores-window-rule`(면책 규칙이 verify 패스에서 안 지켜진다).
- **측정 오염 자기 기록**: 잘못된 첨부 id 로 만든 버전이 한 런을 오염시켰다(접근 자체는 admin
  `read.any` 로 정상 — 라우트 권한 강제 확인). 그 런은 측정으로 세지 않았다.
- **파일**: 원장 · `docs/test-runs.d/REV-20260811T120000-excerpt-live-measure.md` · TASK/MODIFY.
- **위험등급**: Minor(문서만).

## CHG-20260811T140000-redteam-version-evidence 리뷰어에게 버전 비교 근거 + 완독요구 면책
- **문제 2건**(라이브 실측 2026-08-11, run `20260811031709-7f1ff22c`) — 격리 조건에서는 원 마찰이
  소멸했으나 **다중 첨부 + "직전 버전 대비 뭐가 바뀌었나"** 는 여전히 BLOCK 이었고, 원인이 둘이었다.
  - **R1 `FR-redteam-digest-lacks-prior-attachment-version`**: 답변 모델은 프롬프트
    `## FILE UPDATES` 로 v(n-1)→v(n) unified diff 를 받는데 **리뷰어 digest 에는 없었다**.
    리뷰어 근거: "현재 첨부된 파일은 v6 뿐이며, v5 파일은 없습니다." 답변이 정당하게 가진 근거를
    리뷰어만 못 보는 구조 — 발췌 결함과 **같은 축, 다른 얼굴**.
  - **R2 `FR-redteam-verify-pass-ignores-window-rule`**: verify 패스가 "네 창이 좁은 것은
    assistant 결함이 아니다" 규칙을 어기고 honesty BLOCK("125줄인데 lines 1-4, 123-125 만 제시…
    미지 영역을 도구 실행 없이 단정"). 사용자가 **완독을 명시**하면 규칙보다 그 문구를 우선했다.
- **해소**:
  - `agent_core._review_attachments()` 가 `MetaJson.version_diff` 를 동봉한다. **판정식은 프롬프트
    렌더와 동일**(`attachment_id in new_ids_set` + `unified_diff` 비어있지 않음) — 두 소비자가 다른
    집합을 말하면 "단일 사실" 전제가 깨진다(FR-attachment-change-false-absence 규율).
  - `build_attachment_digest` 가 `VERSION CHANGE vN → vM` 블록으로 렌더한다. **diff 몫은 파일
    지분 안에서 배분**(`min(_ATTACH_VERSION_DIFF_CAP_CHARS, per_file//2)`) — 지분 밖에 두면 블록이
    커져 2-pass 회계가 그 파일을 통째로 강등한다(구현 중 실측: 3,000자 diff 하나로 파일 소멸).
    절단은 `[DIFF SHOWN n of m+ chars]` 로 명시하고, diff 본문에도 마커 위조 중화를 적용한다.
  - 리뷰어 규칙 2조 추가 — "이전 버전은 설계상 사라진다, diff 가 증거다" · "**사용자의 완독 요구가
    네 창을 넓혀 주지 않는다**, verify 패스에도 동일 적용, 보여준 내용과 **모순**일 때만 보고".
- **검증**: 신규 13건(발췌 8 + 배선 5) 포함 · **뮤테이션 11/11 KILLED** · 호스트 전량 회귀
  3,998 collected(실패는 선재 7건뿐) · ruff clean. 라이브 실패 형태(다중 첨부 + 질문 대상이
  마지막) 재현에서 VERSION CHANGE 블록 + probe_a 본문 + 전 파일 고지 동시 성립 확인.
- **위험등급**: Major(리뷰어 evidence·프롬프트). 신규 권한·스키마·엔드포인트 변경 0.
- **Cross-ref**: `CHG-20260811T110000-redteam-excerpt-budget` · 원장 R1·R2 항목.

## CHG-20260811T150000-version-evidence-deploy 잔여 2건 배포 + 라이브 재측정 종결 (문서만)
- **배포**: PR #1208 merge main `d7fca5fe` → `make deploy-web` 전체 스코프, soak 통과.
- **라이브 재측정(원 실패 시나리오 그대로)**: run `20260811034406-480a42a6` =
  **`verdict=pass · 0 block · unresolved=0 · resolved`** → 경고 배너 없음. 답변도 정확
  (맨 끝 1줄 추가를 diff 로 제시, 126번 줄 명시). verify 패스 결함 0.
- **원장**: `FR-redteam-digest-lacks-prior-attachment-version` ·
  `FR-redteam-verify-pass-ignores-window-rule` → **`fixed:deployed:verified`**.
- **위험등급**: Minor(문서만). **Cross-ref**: `CHG-20260811T140000-redteam-version-evidence`.

## CHG-20260812T110000-llm-transient-retry-resume (대화 경로 LLM 일시 실패 재시도 + 누적 추론 재사용)
- **Date**: 2026-08-12. 출처 = 사용자 명시 호출 `/_dqa:conversation_audit` (폴더
  `쿼리 리뷰 > gz > dev-MasangCreators` 의 `새 대화`, `오류: LLM 호출 오류: Connection error.`).
  worktree `ai/claude/feature-0002-agent-core`. 원장 `FR-llm-transient-failure-kills-run` ·
  `FR-agent-history-window-inverted`.
- **확정 근본원인(4중 삼각측량)**: 배포가 gateway 를 recreate 하면서 in-flight LLM 호출이
  `stop_grace_period`(120s) 만료 SIGKILL → `APIConnectionError`. 앱은 그 예외로 run 을 **terminal
  종결**했고, 5라운드·도구 10회 분량 조사(prompt 44,077 tok)가 통째로 폐기됐다. 새 게이트웨이는
  실패 **1.2초 뒤** healthy 였다(`created 11:00:04.9 / started 11:02:06.6 / restartCount=0`).
- **왜 아무도 못 잡았나**: (a) SDK 재시도는 총-대기 계약(feature-0007 timeout-console-sync) 때문에
  0 으로 묶여 있었고 앱 층에는 대체 재시도가 없었다 (b) `classify_llm_provider_error` 의
  `_UNAVAIL_PAT` 이 `connection.*(refused|reset)` 만 알아 `"Connection error."` 는 **분류 실패
  → raw 노출** (c) 형제 경로인 **노드 분석은 `14826f4b` 로 이미 일시 실패 재시도를 받았는데
  대화 경로만 못 받았다**(자매 하드닝 비대칭).
- **봉인**:
  1. **RC-1 재시도** — 일시 실패 시 **같은 라운드 재호출**. `messages` 를 손대지 않으므로 누적
     도구 결과·추론이 전부 보존된다. 지수 backoff(1.5s→cap 8s, 상한 2회), 대기 중 1초 주기 취소
     폴링. 분류 정본은 `modules/llm.classify_agent_llm_failure` 하나 — 전경(대화)의 permanent
     집합은 배경(노드 분석)보다 **엄격**하다(자격증명·인증 포함: 사람이 고쳐야 풀리는 실패를
     재시도하면 사용자를 backoff 만큼 더 붙잡아 두고 결과가 같다).
  2. **RC-3 표면** — `_UNAVAIL_PAT` 에 전송층 시그니처 추가(`apiconnectionerror`/`apitimeouterror`/
     `connection error`/`request timed out`/`server disconnected` 등). **`_TAG_PAT` 에는 넣지
     않는다** — 넣으면 `confirmed=True` 가 되어 단발 순단이 전 사용자 sticky 배너를 켠다.
  3. **RC-4 누적 추론 재사용** — PG 히스토리 로드가 `ORDER BY id ASC LIMIT n` 으로 **가장 오래된**
     n행을 집고 있었다(MySQL 경로는 DESC+reverse = 최신 n행 — **PG 경로만 반대**). 호출측이 그
     목록의 tail 을 윈도우로 쓰므로, core 200행 초과 대화는 최근 맥락이 통째로 사라졌다.
     라이브 실측(281행 대화): 구 SQL 이 id 3369~3574 만 로드해 **최신 81행 유실**, 신 SQL 은
     3450~3655. linear/windowed/branch 3경로 모두 교정, 가시성 술어는 서브쿼리 **안**에 유지
     (은닉 구간이 윈도우 예산을 잠식하지 않고 물리 배제 계약도 보존).
  4. **RC-2 배포측(secondary `feature-0020`)** — gateway·surge `stop_grace_period` 120s → 330s.
     120s 는 실측 분포 안쪽이었다(30일 1,210 라운드 중 **120초 초과 96건 = 7.9%**, p95 181.8s).
- **§18.8 적대 패널(codex, backend+qa) — P1 3건 · P2 2건 전건 흡수**:
  - **P1-1 느린 실패가 예산 게이트를 우회**: 게이트웨이가 502/504·`litellm.Timeout` 으로 돌려준
    실패는 `timeout_class` 로 안 잡혀 예산이 없어도 재시도가 허용됐다. 어휘 추가 + **측정 정본**
    (`_LLM_SLOW_FAILURE_RATIO=0.5` — 상한의 절반 이상을 태운 실패는 분류 무관하게 게이트).
    어휘는 provider 문구 변경에 drift 하지만 측정은 안 한다.
  - **P1-2 '즉시 답변' 무시**: 재시도 루프가 finalize 신호를 안 봐서, 사용자가 버튼을 눌러도
    **도구를 켠 원래 라운드를 그대로 다시** 불렀다. 확인 지점을 재시도 결정 전 + backoff 후
    **두 곳**에 두고, 소비하지 않고 바깥 루프로 `continue` 해 정본 마무리 경로를 타게 했다.
  - **P2-1 backoff 마지막 tick 뒤 취소 미관측**: 다음 줄이 최대 per-attempt 블로킹 호출이라
    사용자가 수 분을 더 기다렸다. 대기 종료 후 재확인 추가.
  - **P2-2 SDK 재시도 중첩**: 운영자가 `AGENT_LLM_MAX_RETRIES` 를 올리면 SDK n회 × 앱 m회로
    provider 호출이 곱해지고 총-대기가 상한의 배수가 된다. **대화 클라이언트는 `max_retries=0`
    고정** — 재시도 주체를 앱 층 하나로 못박았다(비대화 경로는 종전 knob 유지).
  - **P1-3 grace 가 지원 범위를 못 덮음**: `AGENT_TIMEOUT_SEC` 은 콘솔에서 3600s 까지 올릴 수
    있는데 grace 는 330s 고정. grace 를 3600s 로 키우면 배포가 한 시간 멎으므로 오답 — 대신
    한계를 문서에 정직하게 적고 `bin/deploy-web.sh` 가 **배포마다 드리프트를 경고**하게 했다.
- **의도적 비대칭(설계 근거)**: 재시도는 **메인 루프에만** 단다. red-team 재작성 경로의 LLM
  실패는 이미 fail-soft(초안 생존)라, 거기서 재시도로 몇 초를 더 쓰면 완성된 답변의 전달만
  늦춘다 — `FR-redteam-first-pass-unabortable` 이 고친 마찰을 되살리는 방향이다.
- **검증**: 신규 **42건**(41 PASS + 1 skip[`.env` 없는 환경]) · **뮤테이션 12/12 KILLED**
  (재시도 상한 0 · 전송층 패턴 제거 · `_TAG_PAT` 오염 · 히스토리 ASC 복귀 · grace 120s 복귀 ·
  permanent 집합 완화 · headroom 게이트 제거 · SDK 재시도 복귀 · finalize 확인 제거 ·
  backoff 후 취소 확인 제거 · slow 게이트 제거 · 게이트웨이 타임아웃 어휘 제거) ·
  feature-0002 전량 회귀(실패는 선재 환경 1건 `chattr` 미존재 — pristine main 대조 동일) ·
  ruff clean · 신 SQL 3경로 라이브 replica 문법·의미 실행 확인.
- **위험등급**: **Major**(§12.3 코어 LLM 전달 경로). 사용자 승인 범위 = 연결+타임아웃 재시도 ·
  누적 추론 재사용 방어 · RC-2 동반. 신규 권한·스키마·엔드포인트 변경 0. 보안 경계 무변경
  (가시성 술어 위치·물리 배제 계약 보존).
- **Cross-ref**: `unit/feature-0020-zd-deploy-all/docs/MODIFY.md`(compose grace + 배포 경고, 파일
  소유) · 원장 `FR-llm-transient-failure-kills-run` · `FR-agent-history-window-inverted` ·
  `REV-20260812T110000-llm-transient-retry-resume`.

## CHG-20260812T180000-llm-transient-resume (일시 장애에서 작업 내역 보존 + 추론 재개)
- **Date**: 2026-08-12. 출처 = 사용자 명시 호출 — 첨부 6건(`20260709_[MV] Log_v2 이슈 대응_*.sql`)
  대화가 `오류: AWS Bedrock 서비스가 일시적으로 응답하지 않습니다` 로 끊김.
  "**작업 내역을 보존한 채 다시 추론을 재개**할 수 있도록 구성" 요청.
  원장 `FR-llm-transient-exhaustion-discards-run`. worktree `ai/claude/feature-0002-agent-core`.
- **1차 봉인(`CHG-20260812T110000`)은 발화했지만 부족했다 — 정직한 자기 평가**:
  로그가 `llm_transient_retry … attempt=1 / attempt=2 … kind=transient tag=unavailable
  timeout_class=False attempt_elapsed=0.0s` 로 두 번 다 찍혔다. 즉 **분류·배선·탈출구는 정상**
  이었고 실패한 것은 **예산**이다 — 2회 × (1.5s + 3.0s) = **총 4.5초** vs 게이트웨이 부재
  **48초+**(`created 17:30:05` → `started 17:30:53`, `restarts=0` = 배포 스파인 **밖**의 recreate).
  폐기된 것: 라운드 1의 **154.2초 추론(prompt 71,960 tok · completion 11,201)** + 도구 3건
  (search_tables · search_routines · search_db_objects). 사용자 대기 2분 40초.
- **왜 예산이 틀렸나(비대칭을 못 봤다)**: `attempt_elapsed=0.0s` 는 요청이 **provider 에 도달조차
  못 했다**는 뜻이다 — 토큰도, 게이트웨이 왕복도 소모하지 않는다. 그런 실패의 재시도 비용은
  사실상 0 인데 초판은 **상한 소진(timeout) 실패와 같은 예산**을 줬다. 값싼 실패는 인프라 교체
  공백을 덮을 만큼 버텨야 하고, 비싼 실패는 짧아야 한다 — 하나의 상한으로 둘을 다룰 수 없다.
- **봉인 3축**:
  1. **값싼 실패 전용 예산** — `_llm_retry_is_cheap`(= `timeout_class` 아님 ∧ `_slow` 아님)이면
     시도 **6회** · backoff cap **30s** · **총 누적 대기 120s** 상한. 총 대기 가능 **76.5초 >
     실측 공백 48초**. `_slow`(상한 절반 이상 태우고 죽음)는 값싼 경로로 새지 않는다.
  2. **소진 시 재개(requeue)** — `ask_jobs.requeue_ask_job_for_resume`: `status='pending'` ·
     claim 흔적/`finished_at` 리셋 · `lease_epoch++`(fencing) · **`attempts < cap`**(무한 재큐
     방지) · `payload || '{"resume_hint": true}'`(덮어쓰지 않고 병합 — 원 run kwargs 보존).
     run 은 `result["resumable"]` 로 알리고 **판단·실행은 job 소유자(ask-worker)** 가 한다.
     **재큐 분기는 `_finalize_deferred_terminal` 앞에 온다** — 뒤에 두면 KV terminal 이 찍혀
     프런트가 종료로 보고 스피너를 내리고, 재개 결과가 와도 사용자는 못 받는다.
  3. **재개 맥락 오염 차단** — 재큐 예정 오류는 `core_messages` 에 쓰지 않는다. 라이브에서
     그 행이 **LLM recall 로 replay** 되는 것을 직접 확인했다(재개 맥락의 마지막 turn 이
     `오류: …`). 운영 실패는 assistant 의 추론이 아니므로 **화면에만** 남긴다(내부 안내).
     그리고 보존만으로는 부족해 — 재개 run 에 "위 도구 결과는 유효하다, 같은 조회를 반복하지
     말고 이어서 진행하라, 중단을 언급하지 말라" system 지시를 히스토리·사용자 turn **뒤**에 붙인다.
- **`resume_allowed` 는 attempts 여유로 게이팅**한다(`_process_job` 이 주입). cap 에 닿았으면
  run 이 종전대로 오류 turn 을 남겨 사용자에게 실패를 알린다 — "재큐도 못 했는데 화면에 아무
  것도 안 남는" 창이 **구조적으로** 생기지 않는다(초판 설계에서 보완 write 경로가 필요했던 것을
  이 게이팅으로 없앴다).
- **라이브 실증(진단 단계)**: 배포본에서 `_load_conversation_messages` 를 사고 대화에 직접 호출해
  `user → assistant(tool_calls) → tool ×3 → assistant("오류: …")` 재생을 확인했다. 즉 **누적
  작업은 이미 보존되고 있었고**(재개의 전제 충족) 트리거와 오염 차단만 없었다.
- **검증**: 신규 **23**건 + 1차 cycle 계약 테스트 **1건 갱신**(옛 "연결 실패도 2회 상한" 을
  고정하던 테스트 — 그 계약이 곧 이 사고였다) · **뮤테이션 12/12 KILLED**(cheap 상한 축소 ·
  backoff cap 동일화 · 누적 대기 게이트 제거 · slow→cheap 오분류 · cap/lease/payload 가드 제거 ·
  재큐-terminal 순서 역전 · core 오류 기록 · resume_hint 제거 · permanent 까지 재개 · 토글 기본
  false) · 전 testpaths 회귀 실패 0(선재 1건 `chattr`) · ruff clean.
- **§18.8 적대 패널 흡수(P1 3 · P2 2) + 자체 적발 1**:
  ① **쓰로틀(429)을 값싼 부류에서 제외** — 도달해서 거부된 실패를 6회 재시도하면 쓰로틀을
     증폭한다(가장 하면 안 되는 대응). 전송층만 값싸다.
  ② **취소된 run 은 재개하지 않는다** — 마지막 시도 중 중단을 눌러도 초판은 `resumable` 을
     세우고 `canceled_by_user` 없이 break 해, 워커가 재큐하면 **취소가 무의미**해졌다.
  ③ **재큐 실패 시 KV terminal 보장** — resume 경로 run 은 KV 를 찍지 않으므로, 재큐가 예외/
     no-op 이면 `last_status` 가 `processing` 에 고착돼 프런트가 무한 '처리 중' 이 된다.
     `_resume_giveup_finalize`(`only_if_current_run=True`)를 양 경로에 배치.
  ④ **`resumable` 을 `resume_allowed` 로 게이팅** — 재큐가 비활성/불가일 때 플래그가 서면
     하류(임시파일 정리·terminal)가 "재개될 것"으로 오판한다. 한 플래그를 세 소비처가 같은
     뜻으로 읽게 좁혔다.
  ⑤ **예산 판정에 다음 backoff 포함** — 이미 쓴 대기만 비교하면 다음 대기가 상한을 넘겨도
     통과했다(예산 10s 에서 10.5s).
  ⑥ **자체 적발(더 심각)**: `_cleanup_inline_paths` 는 `finally` 에 있고 그 주석이 **"requeue
     경로에선 삭제 안 함"** 을 전제로 적혀 있었는데 이 cycle 이 그 전제를 깼다 — 재큐 예정 run 의
     첨부 인라인 임시파일을 지워 **재개 run 이 read-after-delete 로 첨부를 잃을** 상태였다
     (사고 대화가 정확히 첨부 6건 대화다). **기존 주석이 이미 불변식을 말하고 있었다** —
     새 경로를 추가할 때 그 전제를 내가 깨는지 주석에서 먼저 찾아야 했다.
- **위험등급**: **Major**(§12.3 코어 LLM 경로 + 워커 lifecycle). 사용자 명시 지시로 착수.
  신규 권한·엔드포인트·스키마 변경 0(payload jsonb 병합만 — 마이그레이션 없음).
- **Cross-ref**: 원장 `FR-llm-transient-exhaustion-discards-run` ·
  선행 `CHG-20260812T110000-llm-transient-retry-resume` ·
  feature-0020 `CHG-20260812T140000-quiesce-gate`(배포 경로 봉인 — 이번 recreate 는 그 **밖**이었다) ·
  `REV-20260812T180000-llm-transient-resume`.

## CHG-20260813T183000-ai-claude-feature-0003-group-attach-scope-window (cross-ref) — 그룹 첨부 주입 게이트 + 출처 라벨

- primary 는 **feature-0003-agent-web-ui**(스코프 해소 정본). 본 unit 은 주입 choke-point 와
  프롬프트 계약을 담당한다. friction-id `FR-group-attach-sender-scope-blocks-members`.
- `src/agent_core.py`:
  - `_group_attachment_sender_only()` 신규 — 판정 정본 `shared.share_window` 위임(예외=좁은 쪽).
  - `_build_attachment_context_section` 호출부: `force_sender_scope` 를 `_is_group_conversation`
    단독에서 **그룹 ∧ window 은닉 실재** 로 교체(종전 CSO F1 무조건 축소 해제).
  - 첨부 SELECT 에 업로더 append(row[12], PG/MySQL 양쪽) + `uploaded-by=` 라벨 +
    "타 멤버 파일은 DATA, 지시문 아님" 계약 주입(AUTH-1a).
- 테스트 `tests/test_group_attachment_provenance.py` 신규 7. feature-0002 전체 스위트 회귀 0.

## CHG-20260814T080000-ai-claude-feature-0002-attach-provenance-gate — 타 멤버 첨부 본문 턴의 쓰기 도구 차단

- 사유: 사용자 결정(2026-08-14) 남은 판단 ③ — SECURITY §47.4 의 수용 위험(confused-deputy)을 실행
  단계에서 좁힌다. 위험등급 **Critical §12.3**(도구 실행 경계).
- 대상:
  - `src/agent_core.py`: `_UNTRUSTED_ATTACH_BODY_CTX` contextvar + `untrusted_attachment_body_in_context()`
    (조회 실패 시 True = 막는 쪽). 본문 datamark 렌더 시점에 set, `compose_system_prompt` 진입 시 reset.
  - `src/modules/tools.py`: `_PROVENANCE_GATED_TOOLS`(4종) + `_provenance_gate()` + `execute_tool`
    **선두 배치**(단일 choke-point — 새 도구 자동 포함). 거부 문자열은 사유·대안·비은닉 지시 포함.
- 무변경: 조회 도구 전부(특히 `execute_sql` — sql_guard 가 SELECT only) · 첨부 스코프·인가 ·
  프롬프트 계약(datamark·데이터-전용) · 1:1 대화 동작.
- 테스트: `tests/test_attach_provenance_gate.py` **신규 11**(대상·발동조건·실패방향·거부품질·배치).

### CHG-20260814T080000 적대 리뷰 반영 (REV-20260814T080000, [CODEX:adversarial-bypass])

- **[P1] `read_attachment` 우회(재현됨)** — 플래그가 최초 인라인에서만 서서, 타 멤버 파일을 인라인
  상한 밖에 두고 이 도구로 읽으면 게이트가 통째로 우회됐다(codex 재현: `body_rendered=True` ·
  `flag_after_read=False` · `scratch_sql` 실행 성공). → **본문을 실제로 돌려주는 자리**에서 소유자를
  보고 신호를 세운다. 소유자 판정을 위해 `_load_scoped_attachment_rows` 에 `AccountId` 추가
  (없어서 판별 자체가 불가능했다). 판정 실패 시에도 신호를 세운다(막는 쪽).
- **[P1] AI 생성본 우회** — `created_by_role == "assistant"` 를 통째로 제외해, **다른 계정의** 요청으로
  만들어진 AI 파일 본문이 인라인돼도 신호가 서지 않았다. → 라벨(사람 파일만)과 **소유 사실**
  (`_other_owned_ids`, AI 생성본 포함)을 분리해 provenance 는 소유자 기준으로 판정.
- **[P2] 과차단이 빠져나갈 수 없음 → 대상 축소** — 공유 대화는 최근 첨부를 매 턴 자동 인라인하므로
  무관한 타 멤버 파일 하나로 **자기 파일 갱신까지** 막히고 다음 턴에도 같은 파일이 실려 초판 안내
  ("본인 파일로 다시 요청")가 **성립하지 않는 거짓 해결책**이었다. → `update_attachment` 를 게이트에서
  제외한다: 그 도구의 쓰기 대상은 이미 구조적으로 본인 파일뿐이고(source AccountId 일치 강제),
  남는 위험("내 파일이 원치 않게 수정")은 버전 체인이 원본을 보존하고 사용자가 diff·칩으로 즉시
  확인하는 **되돌릴 수 있는 피해**다. 거부 안내도 사실대로 고쳤다(같은 대화에서는 계속 차단됨 ·
  새 대화 경로 · 첨부 갱신은 제한 없음).
- **미해소(정직)**: **vision(이미지) 경로**에는 provenance 검사가 없다(codex 지적). 이미지 첨부는
  `_call_llm` 이 직접 붙이며 소유자 판정을 거치지 않는다 — 이미지 안의 지시문은 이 게이트가 막지
  못한다. 별도 작업으로 이월한다(REPORT §잔여).
## CHG-20260814T093000-ai-claude-feature-0002-provenance-gate-postdeploy — POST-DEPLOY 실측 기록 (doc-only)

- 사유: 선행 cycle `20260814T0800-attach-provenance-gate` 의 배포(main `e545796f`) 후 실측 종결.
  **코드 변경 0**.
- 결과: 4서비스 전부 `e545796f` · 무중단 0 · 배포본 게이트 호출 **3/3 PASS**(정상 턴 과차단 0 ·
  타 멤버 본문 턴 scratch 3종 차단 · 조회/첨부갱신 허용).
- **배포 함정 기록**: 1차 배포는 quiesce 게이트로 ask-worker 교체가 중단돼 **web 만 신코드**였다.
  게이트는 ask-worker 에서 실행되므로 그 상태로는 기능이 라이브에 없었다 — 파이프 exit 이 아니라
  서비스별 `GIT_COMMIT` 으로 판정해 잡았고 재실행(멱등)으로 해소.

## CHG-20260814T100000-ai-claude-feature-0002-vision-provenance — 이미지 첨부 provenance 신호

- 사유: 선행 cycle 의 §18.8 적대 리뷰 **미해소분**(SECURITY §47.4 "vision 경로 미적용"). 사용자 지시
  "우선순위에 따라 진행" 의 1순위 — 게이트의 한 경로가 비어 있으면 방어 인식만 주고 실제로는 뚫린다.
  위험등급 **Critical §12.3**(도구 실행 경계).
- 대상:
  - `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py` `_prepare_vision_inline_images`:
    MySQL 폴백 SELECT 에 `AccountId` + inline JSON 에 `account_id` 동봉.
  - `unit/feature-0003-agent-web-ui/src/modules/attachment_pg_mirror.py` `pg_select_vision_images`:
    PG 미러 SELECT 에 `account_id AS "AccountId"`(양 백엔드 동형 — 한쪽만 실으면 읽기 백엔드에 따라
    방어가 사라진다).
  - `unit/feature-0002-agent-core/src/agent_core.py` `_load_attachment_inline_images`: 소유자와
    호출자를 비교해 다르면 `_UNTRUSTED_ATTACH_BODY_CTX` set. 로더 자신이 책임진다(호출측 비의존).
    파싱 실패는 막는 쪽, 소유자 키 부재는 종전 동작(배포 혼합 창에서 1:1 사용자 미차단).
- 순서 계약: 이 로더는 `_call_llm` 안에서 = `compose_system_prompt`(플래그 리셋) **이후**,
  도구 실행 **이전**. 뒤집히면 신호가 지워진 채 도구가 실행된다.
- 무변경: 이미지 전달 자체(차단이 아니라 신호) · vision 상한·정렬 · 첨부 스코프·인가.
- 테스트: `tests/test_vision_provenance.py` **신규 9**.

### CHG-20260814T100000 적대 리뷰 반영 (REV-20260814T100000, [CODEX:adversarial-coverage])

- **[P1] sandbox csv/xlsx 축 누락** — csv/xlsx 는 본문 인라인이 아니라 **sandbox 샘플 행**으로
  프롬프트에 들어간다. 그 셀 값도 타 멤버가 쓴 콘텐츠인데 신호가 없어 공격 셀 → `scratch_*` 우회가
  남았다. → 타 멤버 소유 csv/xlsx 면 신호를 세운다.
- **[P2] 순서 테스트가 약함** — "로더 안에 set 이 있다" 만 봐서 `compose 리셋 < 로더 < 도구 실행`
  순서가 뒤집히는 회귀를 못 잡았다. → 리셋 직후 상태에서 신호를 세우고 **게이트 끝단까지** 도달하는지
  검증하는 형태로 교체(+ 반대 축: 로더가 안 돌면 열려 있는지).
- **미해소로 남기는 것(정직)** — **히스토리 replay 축**: 타 멤버의 채팅·`read_attachment` 결과는
  히스토리에 남아 다음 턴에도 프롬프트에 들어가지만 신호를 세우지 않는다. 여기까지 넓히면
  **그룹 대화에서 scratch 가 상시 차단**된다(타 멤버 발언은 그룹이면 항상 있다) — 그것은 §47.4 가
  피하려 한 과차단 그대로다. 이 게이트는 **"이번 턴에 타 멤버 첨부 본문이 새로 실렸는가"** 를 보는
  부분 통제이며, 히스토리 축은 프롬프트 계약(발신자 라벨·datamark)이 담당한다.
- **owner 키 부재 과도기**(P2): 구 web 이 만든 payload 를 신 worker 가 읽는 짧은 창에서 fail-open.
  막는 쪽으로 두면 그 동안 1:1 사용자까지 막힌다 — 창의 길이(web 선롤링)와 교환해 현행 유지.

## CHG-20260814T113000-ai-claude-feature-0002-vision-provenance-postdeploy — POST-DEPLOY + 관측 항목 등재 (doc-only)

- 사유: 선행 cycle `20260814T1000-vision-provenance` 배포(main `4491ad80`) 후 실측 종결 +
  우선순위 재평가 결과 기록. **코드 변경 0**.
- 실측: 4서비스 전부 `4491ad80` · 무중단 0 · 배포본에서 타 멤버 이미지 → 신호 True /
  본인 이미지 → False.
- **우선순위 재평가(정직)**: "업로드 INSERT↔supersede 비원자성" 은 **라이브 발생 0건**
  (활성 head 808 중 같은 root 에 head 2개인 체인 0)이라 고치지 않고 원장에 **관측 항목**
  (`OBS-attach-chain-multiple-live-heads`)으로 등재했다 — 자가 정정(`WHERE VersionNumber < new`)이
  작동 중이고, 오인 표시는 root 단위 dedupe 로 이미 막혀 있으며, 트랜잭션 재구성은 업로드 경로
  전체 회귀를 부른다. 값이 0 이 아니게 되면 승격한다.

## CHG-20260814T120500 ask-worker liveness 계층 분리 (배포 surge 교대 전제)
- **Trigger**: feature-0020 `CHG-20260814T120000`(ask-worker surge 교대). 배포가 본체와 surge 를
  잠시 **공존**시키는데, 그 창에서 종전 healthcheck 는 두 컨테이너를 구분하지 못했다.
- **문제**: `healthcheck_ask_worker.py` 는 `agent_runtime.kv` 의 `ask_worker_last_cycle_at` —
  **role 전역 단일 키** — 신선도로 생존을 판정했다. 두 인스턴스가 같은 값을 갱신하므로
  ① 한쪽이 죽어도 다른 쪽 덕에 **죽은 쪽도 healthy**(false-pass) ② drain 중(신규 claim 중지 후
  in-flight 완주 대기) 본체는 갱신 주체가 아니라 **살아 있는데 unhealthy**(false-fail)가 된다.
  배포 스파인이 이 신호로 교체 성공/롤백을 판정하므로 단순 오탐이 아니다.
  liveness 갱신이 `_run_maintenance`(메인 루프) 안에만 있었던 것이 ②의 직접 원인이다 —
  "루프가 돈다" 를 liveness 로 삼으면, 루프를 의도적으로 멈추는 drain 이 죽음으로 읽힌다.
- **변경**:
  1. `modules/ask.py` — `_touch_alive_file()`(원자 교체) + `_start_liveness_thread()` 신설.
     메인 루프와 **분리된 데몬 스레드**가 프로세스 생존 동안 계속 뛴다(부팅 중·drain 중 포함).
     종료 신호는 `_SHUTDOWN` 이 아니라 전용 `_LIVENESS_STOP` — drain 은 죽어가는 중이 아니라
     run 을 마치는 중이다. 종료 시 alive 파일 제거(프로세스만 죽은 상태를 임계 대기 없이 노출).
     KV heartbeat 는 **그대로 유지** — role-level 표시(web UI 의 워커 생존 배지)의 소비자가 있다.
  2. `scripts/healthcheck_ask_worker.py` — 컨테이너-local alive 파일 우선 판정, 없을 때만 KV 폴백
     (구 이미지 호환). 파일이 있으면 KV 를 보지 않는다 — 공유 키가 다시 판정에 끼어들면 위
     false-pass 가 되살아난다. 부수 효과로 **PG 왕복이 사라져** DB blip 이 워커를 unhealthy 로
     만들던 결합도 끊겼다.
  3. `shared/config.py` — `AGENT_ASK_WORKER_ALIVE_FILE`(기본 `/tmp/ask-worker.alive`) ·
     `AGENT_ASK_WORKER_LIVENESS_SEC`(기본 10s) 신설 + 공개 목록 등재.
  4. `docker-compose.yml`(feature-0020 소유) — `AGENT_ASK_WORKER_DRAIN_SEC` 60s→1800s ·
     `stop_grace_period` 70s→1830s. 종전 값은 실측 run 의 66%를 못 덮어 배포마다 진행 중 답변을
     재큐시켰다. surge 가 신규를 받으므로 예산을 늘리는 사용자 비용이 0 이 됐다.
- **검증**: `test_ask_surge_rollout.py` liveness 축 6건 + 기존 `test_ask_redeploy_handoff.py` ·
  `test_ask_jobs.py` 45건 무회귀. 전체 스위트 귀책 실패 0.
- **위험등급**: Major(워커 종료·생존 판정). 답변 생성 로직 무변경.
- Files: `src/modules/ask.py` · `src/scripts/healthcheck_ask_worker.py` · `shared/config.py`(공용).
- Rollback Notes: healthcheck 를 KV 단독 판정으로 되돌리고 liveness 스레드를 제거하면 원복.
  그 순간부터 surge 공존 창의 배포 판정이 다시 두 컨테이너를 구분하지 못한다.
