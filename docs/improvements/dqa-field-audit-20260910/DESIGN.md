---
doc_type: DQA_ROADMAP
initiative: dqa-field-audit-20260910
created_at: 2026-09-10
source_research: ./EVIDENCE.md
source_request: 01_DQA_실무검증_개선요구서.md · 02_DQA_개발AI_전달프롬프트.md (사용자 첨부, 2026-09-10)
status: active
schema_version: 1
task_id: META-0076-dqa-field-audit
baseline_commit: 36c5940f
policy_sha256: 21286d42d52a987af6bed233fb5c050b429ddfa77d33b4979fea3acb4a17fdef
fit_review: REV-20260910-META-0076 (improve-fit-reviewer, PASS-with-fixes → 반영 완료)
---

# 설계 — DQA 실무 검증 개선 (DQA-01~09)

> 이 문서는 **다른 세션(구현 서브에이전트)이 대화 맥락 0 으로 읽고 착수**할 수 있도록 쓴다.
> 각 ITEM 은 `feature_id`(cycle-init `--feature` · `verify-completion <feature-id>` 동일 사용) · `entry_points`(file:line, base `36c5940f`) ·
> `acceptance`(요구서 완료 기준 매핑) · `guards` 를 자기완결로 갖는다. 근거는 [EVIDENCE.md](./EVIDENCE.md) 의 `E-xx` 를 인용한다.
> 경로는 모두 repo-상대(worktree root 기준). 인용한 line 은 base 시점 값이므로 착수 시 symbol 로 재확인한다.

## 0. 맥락 (context-free 진입)

- **대상 제품**: 사내 DBA AI Assistant(DQA). 웹(`feature-0003`)이 질문을 `WebAiTasks` 에 적재하고, 사용자 개인 머신의 러너(`feature-0043`, DQA Connect 앱 `feature-0046`)가 점유(claim)해 외부 도구 표면(`/api/ai/tools/*`, `feature-0041`)으로 DB 를 읽고 답을 제출한다. 코어 도구·가드는 `feature-0002`, 공통 원시함수는 `shared/`.
- **왜 존재하나**: 2026-09-09 실제 DBA 통계 업무(DK 하드코어 253, Product 91)에서 실행기 인수·권한·전수 결과 전달·상태 표시·집계 정의 관리에 마찰이 관측됐다(요구서 §1~§4). 요구서는 「관측」과 「제안」을 구분하며 **과거 기록만으로 현 코드 결함을 확정하지 말라**고 요구한다 → EVIDENCE 가 `[코드]` 로 확정한 것만 결함으로 다루고, `[관찰]` 은 해당 ITEM 첫 단계에서 재현부터 한다.
- **정본 진입**: `AGENTS.md`(§7.1·§12.3·§13.2·§16.3·§16.5.1·§17·§18.8) · `docs/PROJECT.md`(`primary_ui_surface: dqa-client`) · `docs/ARCHITECTURE.md` · `playbooks/PB-0009-dqa-client-verification.md` · `docs/SECURITY.md` §28·§34·§44.
- **측정 기반**: 요구서 §5 회귀 기준값(고정 복원본 한정, 코드 상수 금지) · `unit/feature-0041-external-ai-tool-surface/tests/test_execute_sql_surface.py`(외부 SQL 표면 계약) · `unit/feature-0043-external-llm-bridge/tests/test_bridge_attachment_write.py`(첨부 전달 계약) · `unit/feature-0002-agent-core/tests/test_query_guard*.py`(부하 게이트).
- **구현 위임 방식**: 본 세션(오케스트레이터)이 ITEM 별 worktree 를 `bin/cycle-init.sh --feature <feature_id> --agent claude-corp` 로 만들고 opus 서브에이전트에 ITEM 1개씩 위임한다. 서브에이전트는 자기 worktree 안에서만 편집하고 `verify-completion --pre-commit <feature_id>` PASS 후 commit·push 까지 하며, PR·머지·배포는 오케스트레이터가 §16.5.1 대로 수행한다.
- **공통 규칙(모든 ITEM)**: (1) `shared/**` 를 건드리면 `shared/docs/MODIFY.md` 교차 기록 + 혼합 commit 은 `--pre-commit <feature_id>`(§17). (2) 다른 feature 의 파일을 편집하면 그 feature 의 `docs/MODIFY.md` 에 교차 기록(문서 홈 = 파일 소유 feature). (3) alembic 신규 revision 번호는 **착수 시점 `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt` + 1** 로 정하고 `MAX_MIGRATION.txt` 를 갱신한다(본 문서의 번호는 예시). (4) `_bootstrap_schema.py` 신규 컬럼은 slow path(`_ensure_web_tables`, `:511` 부근)와 fast path(`_ensure_seed_catchup`, `:2987` 부근) **양쪽**에 등록한다(기존 운영 DB 에 컬럼이 생기지 않는 함정). (5) 러너(`unit/feature-0043-external-llm-bridge/src/agent/*.py`) 변경 후 단일 파일 빌드 `python3 unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py` 로 `bridge_agent.py` 와 `unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py` 를 재생성(`tests/test_bridge_agent_sync.py:33`).

## 1. 종속성 그래프 (DAG)

```
ITEM-02a(0002 도구결과 구조화: 가드판정·error·call_id) ─┬─▶ ITEM-02b(0003 상태계약·step 원자성·원장·heartbeat 확장) ─┬─▶ ITEM-02c(0043 러너 DQA 도구채널·승인상한·상태보고) ─▶ ITEM-09d(0043 시스템지침 채널)
                                                        │                                                          ├─▶ ITEM-01a(0003 인수 경계·대화 명시·중복방지) [Critical]
                                                        │                                                          └─▶ ITEM-04b(0003 내보내기 API·다운로드·UX)
                                                        ├─▶ ITEM-08 (0002 미리보기 무결성)
                                                        ├─▶ ITEM-04a(0002+shared 결과 저장소·청크 기록) ─────────────▶ ITEM-04b
                                                        └─▶ ITEM-07 (0002+shared 비용보호 4축·운영가시화·재사용) ◀── ITEM-05a
ITEM-05a(0002 Product 정의 레지스트리) ──▶ ITEM-05b(0003 정의 API·UI·외부 번들·데이터소스 tz)
ITEM-06a(0003+shared 첨부 per-file 결과·선택 재전달) ──▶ ITEM-06b(0043 러너 사전검증·재전달)
ITEM-03 (0003 Product 원자 생성·고립 복구·Description 길이) [Critical]   — 독립
ITEM-09a(0043/0046 연결 진단 데이터)  — 독립      ITEM-09c(0003 좁은 화면 드로어) — 독립      ITEM-01b(0046 클라이언트 계정 대조) [Critical] — 독립
ITEM-10 (통합검증: 실 복원본 회귀값) ◀── 04b·05b·08
```

ITEM-09b(설명 길이) 는 결번 — 같은 파일(`admin_products.py`) 이라 ITEM-03 에 흡수.

## 2. Wave 시퀀스 (핫스팟 동시 편집 ≤ 2 — AGENTS §13.2.5-A)

핫스팟: `routers/ai_tools.py` · `modules/tools.py` · `agent_core.py` · `routers/_conv_store.py` · `agent/handler.py` · `agent/invoke.py` · `static/app/messages.js` · `shared/db.py` · `routers/oauth_as.py`.

| Wave | ITEM (병렬) | 핫스팟 점유(entry_points 기준) | 진입 조건 |
|---|---|---|---|
| W1 | **02a** · **03** · **09c** | tools.py/agent_core.py(02a) · admin_products.py(03) · css/index.html/sidebar.js(09c) | 설계 랜딩. 03 은 Critical 승인 필요 |
| W2 | **02b** · **05a** · **09a** | ai_tools.py/_conv_store.py/bridge_tasks.py(02b) · alembic+kb_definitions+agent_core knowledge ctx(05a) · agent/conf,api,lifecycle + client/core,gui,bridge + oauth_as.py(09a) — heartbeat 인입 필드는 02b 가 단독 소유 | 02a 머지·배포 |
| W3 | **01a** · **04a** · **06a** | ai_tools.py(01a,06a)=2 · _conv_store.py(01a,06a)=2 · bridge_tasks.py(01a) · shared/db.py+tools.py+render.py(04a) · attachment_write(06a) | 02b 머지. 01a 는 Critical 승인 필요 |
| W4 | **02c** · **04b** · **05b** | agent/runtimes,invoke,prompt,handler(02c) · ai_tools.py(04b,05b)=2 · messages.js(04b) · admin_metadata/datasources(05b) | 01a·04a·05a 머지 |
| W5 | **06b** · **08** · **01b** | agent/handler.py(06b) · agent_core.py/render.py+messages.js/app.js/share.js(08) · client/*(01b) | 06a·02c 머지. 01b 는 Critical 승인 필요 |
| W6 | **07** · **09d** · **10** | tools.py/dialects/shared config+runtime_settings(07) · agent/invoke.py(09d) · (읽기 전용 실측)(10) | 05a·02b·02c 머지 |

- 각 wave 는 「구현 → 컨테이너 `make test` 회귀 → §18.8 패널 → verify → PR → cycle-finalize 머지(한 번에 한 브랜치, flock) → `make deploy-web`(wave 당 1회) → POST-DEPLOY 확인」으로 닫는다. 다음 wave 는 직전 wave 의 머지·배포 후 최신 main 에서 cycle-init 한다.
- 병렬 3개를 초과하지 않는다(머지 트레드밀 실측 회피). 한 ITEM 이 막히면(blocked) 다른 두 개는 진행하고, 막힌 ITEM 은 wave 밖으로 이월한다.
- Critical ITEM(01a·01b·03)은 사용자 승인 전 착수하지 않는다(`needs-human-plan-approval`). 승인이 늦으면 그 자리를 다음 wave 의 독립 ITEM 으로 채운다.

## 3. 항목 (각 1 cycle)

### ITEM-02a · 도구 실행 결과의 구조화 — 가드 판정·오류·호출 ID (DQA-02·07·08 공통 기반)
- **status**: pending
- **feature_id**: `feature-0002-agent-core`
- **dimension**: structural
- **risk_grade**: Minor (비파괴 additive 스키마 + 내부 계약 확장; 인증·인가 무변경)
- **depends_on**: []
- **enables**: [02b, 04a, 07, 08]
- **why**: E-02c — heavy 차단 26건 전부 `error=''`(차단 사실이 preview 안내문에만 존재). E-08a — step 레코드에 호출 고유 ID 필드가 없어 병렬 호출을 결과·오류·첨부에 연결 불가. 요구서 DQA-02 「실제 DB 실행 여부와 결과 전달 완료 여부 분리」, DQA-07 「판단 근거 기록」, DQA-08 「호출별 고유 ID 와 화면 순번 분리」.
- **fit_verdict**: adopt
- **what**:
  1. `modules/tools.py::_tool_execute_sql` 의 가드 분기(`:3078-3160`)가 **문자열만** 돌려주던 것을, 기존 `_stats_out` 관례(`:3182-3186`, 밑줄 예약 인자 규칙 `routers/ai_tools.py:3922`)와 같은 **out-param `_guard_out`** 에 구조화 판정을 채운다: `{decision: executed|gated|warned|estimate_failed|denied|failed, db_executed: bool, estimate_rows, estimate_kind: explain_effective|showplan_output, threshold, mode, confirm_heavy, plan_facts, repeat_count, error_class}`. `failed` 는 실행 예외(DB 오류·타임아웃) 로 `db_executed` 는 시도 여부에 따라. 문자열 안내(`_heavy_query_coach`)는 그대로 유지(모델 대면 문구 불변).
  2. `agent_core.py::_build_step_payload(:4468-4520)` 는 이미 `error: str`(:4479) 인자를 가진다 — 결함은 내부 루프(`:9709-9740`)가 `error=` 를 **전달하지 않는 것**. 루프가 가드 판정에서 파생한 `error`(예: `"무거운 쿼리 추정 — 실행하지 않음(예상 ~N행 > 임계 M행)"`) 와 `call_id=tc.id`(`:9695/:9704`) 를 넘기도록 하고, `_build_step_payload` 에 `call_id: str | None`, `db_executed: bool | None` 인자를 **추가**해 `result_summary_json` 에 `guard`(위 dict)·`db_executed`·`call_id` 를 넣는다(주석 `:4492-4496` 의 「컬럼 추가 대신 dict 확장」 원칙).
  3. alembic `<MAX+1>_steps_call_id`(GRANT 가드 블록은 `20260812_0055_tool_call_usage.py:74-88` 복제): `agent_runtime.steps ADD COLUMN call_id varchar(64) NULL` + 부분 UNIQUE `(conversation_id, run_id, call_id) WHERE call_id IS NOT NULL`. expand-only(CONVENTIONS §12), `bin/migrate-lint.sh` 통과. 내부 루프의 INSERT 는 `ON CONFLICT (conversation_id, run_id, call_id) WHERE call_id IS NOT NULL DO NOTHING` 또는 충돌 시 `call_id=NULL` 폴백 + 경고 로그 — provider 가 id 를 재사용해도 run 이 중단되지 않는다.
  4. `runtime_backend.py:175-184` INSERT/`:240` SELECT 와 `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py::_load_steps_for_run(:2542-2600)` 이 `call_id`·`id` 를 함께 읽고 응답 step 객체에 `call_id`, `row_id`(=`steps.id`) 를 노출한다(화면 순번 `step_index` 와 분리). 0003 파일 편집은 feature-0003 MODIFY 교차 기록.
- **entry_points**: `unit/feature-0002-agent-core/src/modules/tools.py:3045(def), 3078-3160, 3182-3190, 2854-2941(_heavy_query_coach), 2810(_heavy_block_seen)` · `unit/feature-0002-agent-core/src/agent_core.py:4468-4520, 9695-9740` (`:5764-5786` 는 ITEM-08 영역 — 수정 금지) · `unit/feature-0002-agent-core/src/modules/runtime_backend.py:175-184, 240` · `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt`(현 `0059_attachment_relative_path`) · `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py:2542-2600`.
- **acceptance**:
  - AC-02a-1: 게이트 모드 `gate` 에서 임계 초과 SQL → step 의 `error` 비어 있지 않고 `result_summary.guard.decision == "gated"`, `db_executed == false`; 정상 실행 → `decision == "executed"`, `db_executed == true`; DB 예외 주입 → `decision == "failed"`, `error` 에 분류 문구. 예시: 임계 1,000,000 · 추정 2,593,294 → `error` 에 「실행하지 않았습니다」 포함.
  - AC-02a-2: 같은 run 안에서 병렬 2 호출의 step 이 서로 다른 `call_id` 를 갖는다; 같은 `call_id` 재삽입 시 두 번째 행은 생기지 않고(DO NOTHING 또는 NULL 폴백) run 은 계속된다(테스트 양쪽).
  - AC-02a-3: 기존 테스트 `test_query_guard*.py`·`test_mssql_load_estimate.py` 문구 계약 무변경으로 PASS; `test_read_attachment_completeness_contract.py:197-235` PASS.
  - AC-02a-4: `bin/migrate-lint.sh` PASS, 마이그레이션 up/down 왕복.
- **guards**: 임계·모드·fail-closed 불변(SECURITY §34). `_heavy_query_coach` 문구 변경 금지(다른 테스트가 고정). 스키마는 additive 만.
- **effort**: 中
- **notes**: 배포 시 alembic 자동 적용(deploy-web migrate gate). `call_id` 가 없는 구 러너 step 은 NULL 허용.

### ITEM-02b · 브리지 상태 계약 통합 · step_index 원자성 · 원장 보강 · heartbeat 확장 (DQA-02 · DQA-08 · DQA-07 일부 · UX-02)
- **status**: pending
- **feature_id**: `feature-0003-agent-web-ui`
- **dimension**: functional
- **risk_grade**: Major (사용자 대면 상태 계약·진행 API 응답 형태 변경; 인증·인가 무변경)
- **depends_on**: [02a]
- **enables**: [02c, 01a, 04b]
- **why**: E-02b — bridge `working` 인데 `/api/progress` 는 빈 상태(두 어휘·공유 계약 없음: `ai_tools.py:4244 _bridge_phase` vs `conversations.py:3973-4053`, 브리지 run 은 `_conv_store.py:4826` 에서 의도적으로 제외). E-08a — `_insert_bridge_step(:1729-1790)` 의 `pg_advisory_xact_lock(:1749)` 이 autocommit 연결(`_pg():564 → runtime_backend.py:1208 → shared/db.py:1073,1119`)에서 문장 종료 시 풀려 INSERT 를 덮지 못함 → `step_index` 중복. E-02d — 진행 안내(activity) 행이 도구 행과 같은 번호 공간을 공유. E-07a — 원장 `tool_call_usage.est_scanned_rows` 컬럼이 선언·조회(`:5543`)만 되고 **기록되지 않음**, heavy 차단은 원장 행 없음.
- **fit_verdict**: adopt-with-guard
- **what**:
  1. **공통 상태 enum** `shared/bridge_tasks.py` 에 `BRIDGE_PHASES = (not_connected, not_listening, waiting, claimed, investigating, awaiting_approval, policy_blocked, verifying, saving_attachments, done, failed, canceled, expired, stalled, deferred)` 와 각 값의 사용자 문구(업무 용어) 매핑을 정의한다. 기존 `_bridge_phase` 값(working/stalled/…)은 새 enum 의 **표시 매핑**으로 흡수(`working` → 세부 phase 가 있으면 그것, 없으면 `investigating`). 실제 DB 실행 여부는 phase 가 아니라 step 의 `db_executed`(02a) 로 표현하고, 「결과 전달 완료」는 `Delivered` 로 분리 유지. **영속 위치**: `WebAiTasks` 에 additive `Phase varchar(32) NULL`, `PhaseDetailJson TEXT NULL`, `LastActivityAt DATETIME NULL`(ALTER 목록 `_bootstrap_schema.py:2547-2560` + fast path) — heartbeat 가 갱신하고 종결 시 최종값 고정.
  2. `GET /api/ai/bridge_status`(`:5315`) · `_bridge_stream_snapshot`(`:4637`) · `GET /api/progress`(`conversations.py:3973`) · `/api/ask_result`(`:4055`) 가 **같은 `phase`·`last_activity_at`** 을 낸다. `/api/progress` 는 브리지 run 에 대해 `steps=[]` 대신 `_bridge_live_steps` 결과(`call_id`·`row_id` 포함)를 투영한다. 표시 순서는 `(step_index, row_id)` 고정, 증분 폴링 커서는 `step_index > %s` 대신 `row_id > %s`(`_load_steps_for_run:2558` — 늦게 커밋된 동번호 행이 영구 누락되지 않게). 근거 없는 진행률·예상 완료 시간은 만들지 않는다(UX-02).
  3. **heartbeat 확장(단독 소유)**: `POST /api/ai/bridge_heartbeat`(`:4922-5084`) 에 **선택 인자** `phase`, `phase_detail`(예: 승인 대기 도구명·재시도 횟수·`tool_channel`), `attempt`, `runner_host_kind`(WSL/Windows), `last_ok_at`, `configured_base_host`(호스트명만, 토큰·비밀 없음) 를 추가(구 러너 호환). `awaiting_approval`/`policy_blocked` 는 러너가 보내는 값이고 서버는 enum 검증만 한다(02c·09a 가 발신).
  4. **연결 왕복 검사 도구**: `/api/ai/tools/connect_check`(무해, 인증만 요구, DB 미접근) — `{ok, account_id, connection_session, server_time}` 반환. `get_tool_catalog`(`:3866`) 에 등재. 02c 의 러너 `--check` 가 이것을 호출한다.
  5. **step_index 원자성**: `_insert_bridge_step(:1740-1765)` 를 명시 트랜잭션(해당 연결만 `autocommit=False` 구간에서 `pg_advisory_xact_lock` → INSERT → COMMIT, 예외 시 ROLLBACK 후 autocommit 복원) 으로 고치거나 `pg_advisory_lock/unlock` 쌍으로 바꾼다. activity 행(`tool=''`)도 같은 함수를 통과하므로 함께 해소된다. 두 스레드 동시 삽입 테스트 추가(`unit/feature-0043-external-llm-bridge/tests/test_bridge_title_steps.py:190` 의 소스 grep 단언을 행위 테스트로 승격). `_bridge_live_steps(:4385)` 의 `omitted` 산출은 `row_id` 기준으로 정정.
  6. **가드 차단의 step·원장 반영**: `ai_tools.py:4016` 성공 경로가 02a 의 `_guard_out` 을 읽어 `decision != executed` 면 `_record_bridge_step(error=…, db_executed=False)`; `tool_ledger.record(:3995)` 에 `est_scanned_rows=` 전달; heavy 차단도 `outcome="gated"` 원장 행을 남긴다(요구서 DQA-02 「정책상 미실행은 성공으로 집계되지 않음」). 실행 예외는 `outcome="error"` + step `error`.
  7. **프론트**: `static/app/composer.js:763,857 _applyBridgePhase` · `static/app/progress.js` · `sidebar.js:1326,1375` · `conv-status.js` 가 새 phase 문구(조사 중/승인 필요/집계 중/결과 검증 중/파일 저장 중)와 `last_activity_at` 을 표시하고, 진행이 없으면 「대기 사유」와 재개·취소 동작을 같은 위치에 둔다. 영구 회전 표시·퍼센트·ETA 요소 금지(UX-02 완료 기준).
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:564(_pg), 1729-1790, 1861-1901, 3181-3211, 3866, 3995-4016, 4244, 4313-4420, 4637, 4922-5084, 5315, 5543` · `routers/conversations.py:3973-4053, 4055` · `routers/_conv_store.py:2542-2600, 4818-4830, 3877-3903` · `routers/_bootstrap_schema.py:2497-2560`(+fast path) · `shared/bridge_tasks.py:116-137, 203` · `src/tool_ledger.py:46-64` · `static/app/{composer,progress,sidebar,conv-status}.js` · 테스트(feature-0043 tests 디렉토리): `unit/feature-0043-external-llm-bridge/tests/test_bridge_title_steps.py:190`, `test_live_steps_structured.py`, `test_live_steps_progress_continuity.py`; (feature-0003) `tests/test_bridge_progress_fallback.py`, `tests/test_bridge_live_steps_window.py`, `tests/verify_bridge_live_step_progress.mjs`; (feature-0041) `tests/test_tool_ledger.py`.
- **acceptance**:
  - AC-02b-1: 같은 task 에 대해 `bridge_status.phase`, `/api/progress.phase`, `ask_result.phase`, `WebAiTasks.Phase`(종결 후) 가 일치 — 정상 완료·정책 차단(`policy_blocked`)·DB 예외(`failed`)·취소 4 케이스 각각 테스트.
  - AC-02b-2: 두 스레드가 같은 run 에 동시 `_insert_bridge_step` 100회 반복 → `step_index` 중복 0; 표시 순서가 `(step_index,row_id)` 로 안정(순서 역전 케이스 테스트).
  - AC-02b-3: heavy 차단 호출 → `tool_call_usage` 에 `outcome=gated, est_scanned_rows=<추정>` 행 1건; 성공 호출 → `outcome=ok, est_scanned_rows` 채움; DB 예외 → `outcome=error`.
  - AC-02b-4: `connect_check` 는 DB 커넥션을 열지 않고(데이터소스 접근 mock 미호출) 200 을 반환; 미인증 401.
  - AC-02b-5: 화면에서 `awaiting_approval` 수신 시 「승인 필요 — <도구> (재시도 n/N)」 문구와 재개·취소 버튼이 같은 카드에 렌더되고, 진행 UI 어디에도 `%`·「예상」 문자열 요소가 없다(jsdom `verify_*.mjs` 부정 단언) + PB-0009 실 DQA 앱 캡처 1회(요소 상태로 충분 — 기하 무관 사유 명시).
- **guards**: 승인 기능 비활성화·임의 셸 포괄 허용 금지. 기존 `test_bridge_progress_fallback.py`(끝난 브리지 원장을 processing 으로 부르지 않기) 유지. `_share_sanitize_step` 화이트리스트(`_conv_store.py:3877-3903`)에 새 필드 노출 여부를 명시 결정(기본: `phase`·`db_executed` 만 허용). heartbeat 의 `configured_base_host` 는 호스트명만(토큰·경로 금지).
- **effort**: 大
- **notes**: shared/ 편집 → `shared/docs/MODIFY.md` 교차 기록 + `--pre-commit feature-0003-agent-web-ui`(§17 혼합 commit). 0043 테스트 파일 개정은 feature-0043 MODIFY 교차 기록.

### ITEM-02c · 러너 DQA 도구 채널 · 승인 오류 상한 · 상태 보고 (DQA-02 · UX-02)
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Major (러너 실행 계약 변경 — 자식 CLI 에 도구 채널 연결; 서버 권한 검증 유지)
- **depends_on**: [02b]
- **enables**: [09d]
- **why**: E-02a — 승인 오류 9건은 러너 AI 가 **존재하지 않는 셸 스크립트**(`dqa_query.py`)로 조사를 시도한 결과. 원인은 `agent/prompt.py:69-101` 이 「HTTP 로 직접 호출」을 지시하고 `runtimes.py:64-97` 이 `--strict-mcp-config` 만 주어 MCP 도구 0개인 구조(코멘트 `:91`). 승인 실패는 `invoke.py:86-102 _FAILURE_HINTS` 에 패턴이 없고 `handler.py:188-190` 이 완료 답변에 주석만 붙인다 → 재시도 상한·재개 경로·`policy_blocked` 상태 없음.
- **fit_verdict**: adopt-with-guard
- **what**:
  1. **DQA 전용 도구 채널**: 러너가 자식 CLI 기동 시 **자기 토큰으로 인증되는 DQA 도구만** 노출하는 MCP 구성을 생성해 Claude 는 `--mcp-config <임시파일>` + 기존 `--strict-mcp-config`, Codex 는 이미 열거된 CLI override(`runtimes.py:46` 의 `-c mcp_servers=…`) 로 넘긴다(사용자 머신 `config.toml` 은 건드리지 않음). 서버 측 구현은 `feature-0041` 의 `external_tool_mcp_server.py:248-332`(`get_tool_catalog`/`run_read_tool`) 를 재사용하고, 러너에는 stdio 셈(`agent/mcp_shim.py`, 서버 catalog 를 확인한 뒤 전체 인자를 `/api/ai/tools/<tool>` 로 전달) 을 둔다. 권한 검증은 여전히 서버(`_authz.scoped_execution`) 가 한다.
  2. `agent/prompt.py:69-101` 의 「HTTP 직접 호출」 지시를 「제공된 DQA 도구를 사용, 셸·외부 스크립트 금지」로 바꾼다. 도구 채널 구성 실패 시(예: CLI 가 MCP 미지원) 기존 HTTP 안내로 **폴백**하되 heartbeat `phase_detail.tool_channel=http_fallback` 을 기록한다.
  3. **승인 오류 감지·상한**: `invoke.py::_FAILURE_HINTS` 에 `requires approval` / `This command requires approval` / `multiple operations … approval` 패턴 추가 → `handler.py` 가 같은 오류 N회(기본 3, `AGENT_BRIDGE_APPROVAL_RETRY_MAX`) 후 `policy_blocked` 로 종결하고 답변 본문에 「승인이 필요한 명령 N회 차단 — DQA 도구로 재시도하거나 운영자에게 문의」 + 재개 경로(다시 실행 버튼) 를 남긴다. 중간에는 heartbeat `phase=awaiting_approval, attempt=k`.
  4. `--check`(`lifecycle.py:692-731`) 가 02b 의 `connect_check` 로 왕복하고 결과에 `tool_channel` 가용 여부를 포함한다.
  5. 생성물 동기화(공통 규칙 5).
- **entry_points**: `unit/feature-0043-external-llm-bridge/src/agent/runtimes.py:46, 64-97, 163` · `agent/invoke.py:86-102, 259-296, 521, 577` · `agent/prompt.py:69-101, 207-213` · `agent/handler.py:92-116, 188-190` · `agent/lifecycle.py:692-731, 1402-1425` · `agent/api.py:45` · `unit/feature-0041-external-ai-tool-surface/src/external_tool_mcp_server.py:248-332` · 테스트: 현 「MCP 0」 계약을 고정하는 파일들 — `grep -l strict-mcp unit/feature-0043-external-llm-bridge/tests/` 결과 전부(8개, `tests/test_tool_permission_friction.py` 포함) 를 **의도적으로 개정**; `tests/test_cli_failure_reason.py` 확장.
- **acceptance**:
  - AC-02c-1: 기동 argv 에 `--strict-mcp-config` 유지 + DQA 전용 `--mcp-config` 만 존재, 사용자 전역 MCP 서버 이름이 자식에 노출되지 않음(테스트).
  - AC-02c-2: 승인 오류 문자열 3회 → 4회째 재시도 없이 `policy_blocked` 종결 + 답변에 재개 안내; heartbeat 에 `awaiting_approval attempt=1..3` 기록.
  - AC-02c-3: `--check` 결과가 `connect_check` 왕복 시간과 `tool_channel: mcp|http_fallback` 을 출력.
  - AC-02c-4: 실 Windows 머신(러너가 사는 환경)에서 Claude 런타임 1회 실제 질문 왕복 — 도구 호출이 셸 승인 없이 `execute_sql`/`describe_table` 을 수행(러너 로그 `task.dispatch` 에 `tool_channel=mcp`). 불가 시 `NOT-RUN` + 사유.
- **guards**: `--dangerously-skip-permissions`·`--allowedTools Bash(*)` 류 포괄 허용 금지. 서버 권한 검증 경로 무변경. 사용자 머신 파일(config.json·config.toml) 형식 호환 유지·무변경.
- **effort**: 大
- **notes**: Windows 검증은 memory 「결함이 사는 환경에서 수정·검증」 원칙. argv 32,767 상한(TASK-20260902T140000) 고려 — mcp-config 는 파일 경로라 안전.

### ITEM-01a · 인수(claim) 계정·인스턴스·대화·Product 경계 + 대화 명시 + 중복 방지 + 추적 ID (DQA-01 · UX-01) **[Critical]**
- **status**: pending — `blocked: needs-human-plan-approval` (§12.3 인가 코드 변경; 요구서 항목 기술은 설계 입력이며 승인 대체 아님)
- **feature_id**: `feature-0003-agent-web-ui`
- **dimension**: functional
- **risk_grade**: Critical (인가 판정 경로 변경 — 강화 방향)
- **depends_on**: [02b]
- **enables**: []
- **why**: E-01a·E-01c — claim 의 계정 대조는 `_dispatch_scope_sql(:380)` 의 `AccountId=%s` 에 **암묵**적으로만 있고, 본문 `runner_instance`(`:2754`) 는 검증 없이 기록되며 러너 인스턴스↔대화↔Product 결속은 검증되지 않고, 거절은 산문 404/409(기계 판독 reason 없음). E-01b — `/api/ask` 의 대화 재사용은 `lazy_create` 불리언 + `_repair_current_conversation` 폴백(`conversations.py:5533-5556`)으로 **암묵**. 중복 방지는 콘솔 잡(`bridge_tasks.open_job_exists:1179`)에만 있고 웹 채팅에는 없음. 30분 lease 외 인수 대기 제한·시도 횟수 없음.
- **fit_verdict**: adopt
- **what**:
  1. `claim_request(:2725-2800)` 에 **명시 검증 블록**: (a) task.AccountId == ctx.account.id (b) `runner_instance` 가 그 토큰의 heartbeat 인스턴스와 일치(`unit/feature-0003-agent-web-ui/src/oauth_store.py:644 token_runner_profile`, `ai_tools.py:3262 _account_is_heartbeating`) (c) task 의 conversation·product 가 그 계정 ACL 에서 접근 가능(기존 `_conversation_access_denied:3768`/`_kb_product_access_denied:3758` 재사용). 실패 시 **구조화 reason** `{"reason": "account_mismatch|instance_mismatch|conversation_denied|product_denied|already_claimed|expired", "expected": …, "actual": …}` 로 409/403 반환(비밀정보·상대 계정 토큰 제외, username 은 기존 노출 범위 내). 조용한 인수 금지.
  2. `shared/bridge_tasks.py` 에 `ClaimAttempts`·`ClaimDeadlineAt`(lease 와 별개, open 후 `BRIDGE_CLAIM_DEADLINE_MIN`) 컬럼과 `CLAIMABLE_SQL(:145)`/`claim_is_live(:1394)` 연동; `_bootstrap_schema.py:2547-2560` ALTER 목록 + fast path 에 additive 추가. deadline 초과 → `expired` + 사유.
  3. `_enqueue_web_bridge_task(:500-620)` 에 dedupe key(계정+대화+질문 sha256, 창 60초) — 중복 클릭은 기존 open task 를 반환(409 아님, 같은 task_id). 모든 task 에 `TraceId`(uuid) 를 두고 `[bridge]` 로그·claim 응답·step 에 싣는다(비밀 제외).
  4. `/api/ask(:4294-4482)`: 요청 본문 `conversation_mode: "new" | "reuse" | "explicit"` 를 도입(미지정 시 현행 동작 유지 + 응답에 `conversation_reused: true/false`, `conversation_resolution: "explicit|reused_current|created"` 명시). `unit/feature-0023-conversation-api-access/src/conversation_mcp_server.py:213` 호출자도 같은 응답 필드를 받는다.
  5. **UX-01**: `static/app/connect-modal.js` 와 컴포저 배너에 「로그인 계정 / 연결된 실행기 계정 / 실행 가능 여부」 3행을 같은 위치에 표시하고, claim reason 이 `account_mismatch` 면 「다른 계정(<username>)의 실행기가 연결되어 있습니다 — 그 계정으로 로그인하거나 이 계정으로 재연결」 + 재연결 버튼. 09a·02b 가 heartbeat 로 올린 `runner_host_kind`·`last_ok_at`·`configured_base_host` 가 `/api/ai/connect/status` 에 있으면 함께 렌더(없으면 생략).
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:380, 557, 2725-2835, 2754, 3262, 3758-3768` · `src/oauth_store.py:644, 1619` · `routers/conversations.py:500-620, 707, 4294-4482, 5533-5556` · `routers/_conv_store.py:4767-4793` · `shared/bridge_tasks.py:113-145, 203-257, 1179, 1394` · `routers/_bootstrap_schema.py:2497-2560`(+fast path) · `static/app/connect-modal.js`, `static/app/composer.js:4381`, `static/app/client-bridge.js:391`(런치 봉투 없을 때 로컬 앱 연결 채택 중단) · 테스트(feature-0043 tests): `unit/feature-0043-external-llm-bridge/tests/test_orphan_claim_reclaim.py`, `test_stale_runner_yield.py`, `test_console_job_scope.py`.
- **acceptance** (요구서 DQA-01 완료 기준 그대로):
  - AC-01a-1: admin 토큰 러너만 열린 상태에서 mckim 계정 task claim → 409 `account_mismatch`, task 는 open 유지, 웹 배너에 불일치 사유 표시.
  - AC-01a-2: 동일 계정 요청은 지정 대화·Product 에서 한 번만 실행 — 중복 클릭 2회 → task 1건.
  - AC-01a-3: 재연결·두 실행기 동시 인수·취소 후 재시도에서 유실 0·중복 실행 0 — 경합 테스트는 러너 2개 × 50회 반복.
  - AC-01a-4: `/api/ask` 응답에 `conversation_resolution` 이 항상 존재; `conversation_mode=new` 는 새 대화, `reuse` 는 현재 대화 재사용을 명시.
  - AC-01a-5: 로그에 TraceId 가 남고 토큰·비밀번호 문자열 0건(secret scan check #18).
- **guards**: 계정명(admin) 기반 우회 금지. 기존 stale-runner yield(연결 순서 축, 계정 다르면 예외) 규칙 보존(`test_stale_runner_yield.py`). 실패 응답에 상대 계정의 토큰·세션 값 미포함.
- **effort**: 大
- **notes**: **착수 전 사용자 승인 필요**(AskUserQuestion). 승인 후 W3. shared/ 편집 → `shared/docs/MODIFY.md` 교차 기록 + `--pre-commit feature-0003-agent-web-ui`. 0023·0043 파일·테스트 편집은 각 feature MODIFY 교차 기록.

### ITEM-01b · 클라이언트(DQA Connect) 상주 러너 재사용 시 계정 대조 (DQA-01 · UX-01) **[Critical]**
- **status**: pending — `blocked: needs-human-plan-approval`
- **feature_id**: `feature-0046-native-client`
- **dimension**: functional
- **risk_grade**: Critical (연결 인가 판정 — 강화 방향)
- **depends_on**: []
- **enables**: []
- **why**: E-01a·코드맵 — `client/bridge.py:481-520 _connect_one` 은 `connection_session`(부재 시 **토큰 동일성**)만으로 `same_session` 을 판정해 `already_connected` 로 상주 러너를 재사용하고, `core.py:1220-1235 connection_identity` 는 `account_id` 를 받아서(`:1233`) **버린다**. 다른 계정의 웹 요청이 상주 admin 러너에 흡수되는 클라이언트 측 경로.
- **fit_verdict**: adopt
- **what**: `connection_identity` 가 `account_id`(및 username 이 있으면) 를 반환하도록 하고, `_connect_one` 이 딥링크/런치 봉투의 계정과 상주 러너의 계정을 비교해 불일치면 재사용을 **거절**하고 `{ok:false, reason:"account_mismatch", resident_account:…}` 를 GUI/트레이(`gui.py:488-556`) 와 웹 콜백에 전달한다. 같은 계정이면 현행 재사용 유지. 자동으로 다른 계정 러너를 종료하지 않는다(사용자 선택: 「그 계정 연결 유지」/「이 계정으로 재연결」).
- **entry_points**: `unit/feature-0046-native-client/src/client/bridge.py:426-533` · `client/core.py:1220-1256` · `client/gui.py:488-556, 746-758` · 테스트 `tests/test_bridge_connect_credentials.py`, `tests/test_handoff_seam.py:451`, `tests/windows/README.md`(실 Windows 하네스).
- **acceptance**: AC-01b-1: 계정 A 러너 상주 + 계정 B 런치 → 재사용 거절·사유 표시·A 러너 무종료. AC-01b-2: 같은 계정 → 기존 `already_connected` 경로 회귀 없음. AC-01b-3: 실 Windows 설치본 1회 실측(PB-0009 창/트레이 표) 또는 `NOT-RUN` 사유.
- **guards**: 트레이 생존 seam·`webview.start()` 1회 등 실 Windows 하네스 함정(memory) 준수. 릴리스는 별도 출하(클라이언트 버전 bump 는 이 ITEM 범위 밖 — REPORT 에 후속 명시).
- **effort**: 中
- **notes**: 서버(01a) 없이도 독립 동작. **착수 전 사용자 승인 필요**.

### ITEM-03 · 비공개 Product 원자 생성 + 초기 관리 권한 · 고립 Product 진단/복구 · Description 길이 검증 (DQA-03 · DQA-09 설명 길이 · UX-06) **[Critical]**
- **status**: pending — `blocked: needs-human-plan-approval`
- **feature_id**: `feature-0003-agent-web-ui`
- **dimension**: functional
- **risk_grade**: Critical (인가 데이터 생성 경로 변경 — 생성자에게 자기 Product 접근 부여)
- **depends_on**: []
- **enables**: []
- **why**: E-03b — `admin_create_product(:1259-1325)` 는 `default_role_access=false` 면 동적 권한 코드 `product.access.<key>` 를 만들되 **누구에게도 grant 하지 않고 commit** → 고립. E-03c — 부여 경로 2곳(`_enforce_override_self_scope`, `_enforce_role_permission_self_scope`)은 「행위자가 보유한 코드만 부여」라 아무도 못 가진 코드는 **영구 403**(올바른 가드 — 유지). E-09b — Description 길이 미검증 + DB 예외 문자열 500 노출.
- **fit_verdict**: adopt-with-guard
- **what**:
  1. **원자 생성**: 같은 `autocommit=False` 트랜잭션 안에서 `WebProducts` INSERT → `WebPermissions` 동적 코드 INSERT → (`default_role_access=false` 일 때) **생성자 계정에 `WebAccountPermissionOverrides(allow)` 1행 INSERT** → 감사 행(:1327-1354) 도 같은 트랜잭션으로 이동 → 1회 commit. 헬퍼 `_grant_product_access_to_account(conn, account_id, permission_id)` 는 **INSERT 1행만** 수행한다 — `routers/admin_accounts.py:668-683 _set_account_overrides` 는 `DELETE … WHERE AccountId` 후 재삽입(전체 교체) 이므로 그 로직을 상속하면 생성자의 기존 override 가 지워진다(리뷰 지적). 어느 단계든 실패(영향 행 0 포함) 시 전체 rollback. `product.create` 게이트(:1230) 는 첫 단계로 유지.
  2. **자기 권한 초과 가드 무변경**: `_enforce_override_self_scope`·`_enforce_role_permission_self_scope` 는 손대지 않는다. 생성 시점 grant 가 그 필요를 없앤다. 관리자 계정명 우회 금지(SECURITY §28.6 정합, 새 ADR 로 「비공개 Product 초기 소유자 = 생성자」 결정 기록).
  3. **고립 진단/복구**: `unit/feature-0003-agent-web-ui/scripts/product_access_repair.py`(형제 `attach_chain_merge.py` 와 같은 디렉토리 — `src/` 아님) + `bin/product-access-repair.sh`(`bin/kb-backfill.sh` 관례, `--dry-run` 기본). 진단 쿼리: `WebProducts` ⟕ `WebPermissions(IsDynamic=1)` ⟕ `WebRolePermissions` / `WebAccountPermissionOverrides(allow)` 에서 유효 grantee 0 인 Product 목록·생성자(감사 로그의 create actor) 출력. 복구는 `--apply --product <id> --grant-account <id>` 로 **운영자가 지정한 계정 1개**에 allow 행 추가(자동 선택 금지). 요구서: 「기존 고립 데이터 진단·복구 방안은 별도 제시」 → 스크립트 + RUNBOOK 절.
  4. **Description 길이**: DDL 길이 상수를 `_bootstrap_schema.py:755` 옆에 `PRODUCT_DESCRIPTION_MAX = 255`, `PRODUCT_NAME_MAX = 128` 로 두고 create(:1241-1252)·patch(:1405-1412) 가 초과 시 400 `{"error": "설명은 255자 이내여야 합니다 (현재 N자)", "field": "description", "max": 255}`. 두 500 핸들러(:1313-1320, :1470-1476) 는 예외 문자열을 그대로 내지 않고 분류(중복 키→409, 길이→400, 그 외→500 「제품 저장 실패」 + 서버 로그에만 상세). `WebProductDatabases.Description`(:769) 도 동일.
  5. **프론트(UX-06)**: `static/admin/products.js:817-830` input 에 `maxlength=255` + 남은 글자 카운터; 생성 흐름(:2087-2109) 에 설명 입력·비공개 여부 선택 추가; `static/admin.js:3928-3931` 일괄 실패 토스트가 `failures[0].error` 를 표시(입력 보존).
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/admin_products.py:1216-1356, 1358-1483, 1543-1600` · `routers/admin_accounts.py:593-620, 625-644, 668-683` · `routers/admin_roles.py:464-495` · `routers/_bootstrap_schema.py:751-775, 967-1046, 1304-1370` · `src/web_context.py:3419-3510, 3631-3637, 2170-2181` · `static/admin/products.js:817-830, 857-859, 2087-2109` · `static/admin.js:534-547, 3729-3757, 3928-3931` · 테스트 `tests/test_product_list_rbac.py`, `tests/test_model_access_rbac.py:381-438`(길이 assert 템플릿) · `docs/SECURITY.md:1144-1170` §28.6 · `unit/feature-0003-agent-web-ui/docs/FUNCTION.md:875-876`(AC-0041/0042 개정).
- **acceptance** (요구서 DQA-03 완료 기준):
  - AC-03-1: 비공개 Product 생성 직후 생성자 계정으로 `GET /api/admin/products/{id}` 200 · 작업 화면 목록 포함 · PATCH 가능.
  - AC-03-2: grant INSERT 를 강제 실패시키면 `WebProducts`·`WebPermissions`·감사 행이 남지 않는다(트랜잭션 rollback 테스트); 생성자의 기존 override 행 수 불변.
  - AC-03-3: 무권한 계정의 조회·수정 403 유지; 다른 관리자가 자기 미보유 코드를 부여 시도 → 기존 403 문구 유지.
  - AC-03-4: Description 256자(한글)·255자 경계·이모지·따옴표/`--`/`;` 등 특수문자 포함 값 → 400/200 정확; 응답 본문에 `Data too long`·SQL 조각 0건.
  - AC-03-5: `bin/product-access-repair.sh --dry-run` 이 고립 Product 를 나열하고 `--apply` 없이는 무변경; 복구 후 재실행 시 0건.
  - AC-03-6: PB-0009 실 DQA 앱 관리 콘솔에서 생성·설명 초과 입력 흐름 캡처(입력 보존 확인).
- **guards**: 관리자 계정명 기반 접근 확대 금지. 고립 복구는 운영자 명시 계정에만. `_ensure_dynamic_permissions_schema` 의 `try/except: pass` ALTER 함정(E-03 코드맵) — 신규 컬럼 없음이므로 무관하나 재사용 시 주의.
- **effort**: 中
- **notes**: **착수 전 사용자 승인 필요**(AskUserQuestion). 승인 후 W1.

### ITEM-04a · SQL 결과 저장소 — 스트리밍 청크 기록·체크섬·재실행 없는 미리보기 (DQA-04)
- **status**: pending
- **feature_id**: `feature-0002-agent-core`
- **dimension**: structural
- **risk_grade**: Major (새 저장 경로·보존 정책 + **shared 원시함수 옆에 신규 함수** — 기존 `execute_sql` 시그니처·반환 불변; 인증·인가 무변경)
- **depends_on**: [02a]
- **enables**: [04b]
- **why**: E-04a·E-04d — 외부 표면은 `_suppress_csv=True`(`ai_tools.py:3935-3937`) 로 파일을 만들지 않고 10,000행 초과는 **메모리에 다 올린 뒤** 413(`:3973-3991`). `tools.py:20` 의 `_raw_execute_sql` 은 **`shared/db.py:996 execute_sql(conn, sql)` 의 alias** 이며 워커·웹·`metadata_stats`·`describe_table`(`tools.py:1962,1995,2079,2183…`) 전부가 쓰는 전량 적재 원시함수(리뷰 지적 — 폭발반경). `save_csv(render.py:62-74)` 는 전량 쓰기·체크섬·TTL 없음, `_stats_out(:3187-3190)` 은 `total_rows`·`csv_paths` 만.
- **fit_verdict**: adopt-with-guard
- **what**:
  1. **결과 저장소 레지스트리** alembic `<MAX+1>_sql_results`: `agent_runtime.sql_results(result_id varchar(32) PK, conversation_id, run_id, call_id, account_id, datasource_key, sql_sha256, total_rows bigint, byte_size bigint, sha256 char(64), chunk_count int, status ∈ writing|complete|partial|failed|expired, partial_reason text, retry_of varchar(32) NULL, expires_at timestamptz, created_at, completed_at)`. GRANT 가드 블록 복제.
  2. **스트리밍 원시함수 신설(기존 불변)**: `shared/db.py` 에 `execute_sql_stream(conn, sql, chunk_rows=5000)` — 커서 `fetchmany` 제너레이터(`(resultset_idx, columns, rows_chunk)`). 기존 `execute_sql(:996)` 의 시그니처·반환·호출자 무변경. `_tool_execute_sql` 만 스트리밍 함수로 갈아타고, (a) 첫 청크에서 미리보기(≤`_TOOL_PREVIEW_ROWS`) 를 만들며 (b) 모든 청크를 `render.py::ResultWriter` 로 결정적 순서(`(resultset_idx, offset)`) 의 CSV 청크 파일(`AGENT_OUT_DIR/exports/<conversation>/<result_id>/part-NNNN.csv`, 최종 `manifest.json`) 에 쓰고 sha256 누적 (c) 종료 시 레지스트리 `complete`. 한도(`AGENT_SQL_EXPORT_MAX_ROWS` 기본 500,000 · `AGENT_SQL_EXPORT_MAX_BYTES` 기본 256MB · 기존 `_apply_query_cap` 시간) 초과·취소·예외 시 `partial|failed` + `partial_reason`, **절대 complete 로 표기하지 않음**. 저장은 파일시스템(기존 `/api/file` 경로 자산 재사용)이며 MinIO 이관은 후속(§4 보류). `describe_table` 등 다른 호출자는 그대로 `execute_sql`.
  3. `_stats_out` 확장: `{total_rows, per_resultset_rows, result_id, sha256, byte_size, chunk_count, status, complete: bool}`. `_suppress_csv` 는 「모델에 경로 노출 금지」의미로 유지하되 저장소 기록은 항상 수행(호출자가 `_export_out` 를 넘긴 경우).
  4. **보존 정리**: `modules/ask.py::_run_maintenance(:1050-1076)` 의 reap 슬롯에 `sweep_expired_sql_results()`(TTL `AGENT_SQL_EXPORT_TTL_HOURS` 기본 72) 추가 — 파일 삭제 후 레지스트리 `expired`. `attachment_reconciliation.py:146-170` 의 `{action, stage, error}` 보고 형태 재사용.
  5. 미리보기와 저장소가 **같은 실행**에서 나오므로 「미리보기가 잘렸다는 이유로 같은 SQL 재실행」이 구조적으로 불필요. `partial|failed` 결과의 **재시도**만 재실행을 허용한다(04b 의 `retry` 엔드포인트가 새 `result_id` + `retry_of` 로 1회). 내부 경로(`agent_core.py:9767 result_csv_paths`) 도 동일 저장소를 쓰고 기존 `csv_paths` 는 첫 청크 경로로 호환 유지.
- **entry_points**: `shared/db.py:996`(execute_sql — 무변경, 옆에 신설) · `unit/feature-0002-agent-core/src/modules/tools.py:20(alias), 3161-3213, 3187-3190, 1817-1900, 2764-2770` · `modules/render.py:62-94` · `modules/ask.py:1050-1076` · `modules/ask_jobs.py:32-63, 280-317`(lease/terminal 관례 참고) · `modules/scratch.py:41, 632-645`(TTL 관례) · `modules/attachment_reconciliation.py:146-170` · `alembic/versions/MAX_MIGRATION.txt` · 테스트 `tests/test_save_csv_unique_path.py`, `tests/test_ask_kv_terminal_seal.py`.
- **acceptance**:
  - AC-04a-1: 합성 결과 0 / 10,000 / 10,001 / 89,623 행 각각 → `total_rows` 정확, `chunk_count = ceil(rows/5000)`(0행은 0 청크·`complete`), sha256 이 청크 연결 파일의 sha256 과 일치, 미리보기는 ≤50행 유지.
  - AC-04a-2: 행 상한·바이트 상한·취소(중간 예외) 각각에서 `status=partial|failed`, `partial_reason` 채움, `complete=false`.
  - AC-04a-3: TTL 경과 레코드 → 파일 삭제 + `expired`; 미경과 무변경.
  - AC-04a-4: 기존 `execute_sql` 호출자(worker·web·metadata_stats·describe_table) 회귀 0 — `grep -n "_raw_execute_sql\|execute_sql(" ` 호출부 전수 테스트 통과; `result_csv_paths`·`read_csv_preview` 회귀 0.
- **guards**: 미리보기 상한(50/500행, 12,000자) 불변. 결과 저장은 read-only 데이터소스 접근 위에서 이루어지며 데이터소스 권한·시간 상한 완화 없음. 원본 행 값을 로그에 남기지 않음. `shared/db.py` 기존 함수 무변경.
- **effort**: 大
- **notes**: MSSQL·MySQL 양쪽 커서 `fetchmany` 지원 확인. 파일 경로 노출은 04b 가 id 기반 다운로드로 대체. shared/ 편집 → `shared/docs/MODIFY.md` 교차 기록 + `--pre-commit feature-0002-agent-core`(§17 혼합 commit).

### ITEM-04b · 전수 내보내기 API·다운로드·재시도·요청 상태 표시 (DQA-04 · UX-03 · UX-05)
- **status**: pending
- **feature_id**: `feature-0003-agent-web-ui`
- **dimension**: functional
- **risk_grade**: Major (새 다운로드 엔드포인트 — **기존 권한 키 `conversation.file.read.own|any` 재사용, 신규 권한 코드·역할 grant 없음**; 인가 정책 무변경)
- **depends_on**: [04a, 02b]
- **enables**: [10]
- **why**: E-04a·E-04b — 전수 요청에 표본 50행만 첨부, 89,623행은 413. 다운로드 권한 축이 둘(`/api/file` 경로 기반 `conversation.file.read.*` vs 첨부 id 기반 `conversation.attachment.read.*`). SQL 결과 CSV 는 오늘도 `conversation.file.read.*` 로 내려받으므로 **같은 권한을 id 기반 엔드포인트에 재사용**한다(신규 키를 만들면 §12.3 Critical — 리뷰 지적으로 설계 변경).
- **fit_verdict**: adopt-with-guard
- **what**:
  1. `ai_tools.py:3935-3937` 에서 `_export_out` 를 넘겨 04a 저장소를 사용하고, `:3973-3991` 의 413 을 **200** `{result_id, total_rows, preview_rows, truncated: true, download_url: "/api/exports/<result_id>", export_status, sha256}` 로 바꾼다. 원장 `outcome="gated"`(모델 반환 상한 초과) 기록과 브리지 step 은 유지하되 `error` 대신 `withheld_from_model=true` 로 구분(02a `db_executed=true`). `_sanitize_sql_output(:468-486)` 의 「다운로드 없음」 문구를 「전체 N행 — 사용자는 결과 ID <id> 로 다운로드 가능」으로 바꾼다.
  2. **엔드포인트** `routers/exports.py`(신규): `GET /api/exports/{result_id}` 상태(`_console_jobs.build_job_status_payload` 형태 재사용 — 국면은 서버가 한 단어) · `GET /api/exports/{result_id}/download`(청크 순서대로 스트리밍, `Content-Disposition: attachment`, nosniff, `complete` 가 아니면 409 + 상태) · `GET /api/exports/{result_id}/manifest` · `POST /api/exports/{result_id}/retry`(`partial|failed` 에만 허용, 같은 SQL 을 1회 재실행해 새 `result_id`(`retry_of`) 반환; `complete` 에는 409). 권한: 로그인 세션 + 대화 접근 게이트(`_resolve_conversation_attachment_scope` 관례) + **기존** `conversation.file.read.own|any`(`routers/system.py:88-97` 과 동일 키). 공유 뷰 `_share_sanitize_step` 은 `result_id` 비노출(기본).
  3. **UX-05**: `static/app/messages.js:197, 355` 의 라벨을 「미리보기 50행 / 전체 89,623행」형태로, 옆에 [전체 다운로드] 버튼(상태 `partial` 이면 「부분 결과 — N행/사유」 + [재시도] 로 표기, 완료로 보이지 않게). 폴링은 `console-job-poll.js::awaitDelegatedResult` 재사용.
  4. **UX-03(요청별 완료 상태)**: `unit/feature-0002-agent-core/src/modules/guidance_registry.py:37` 에 「다항목 요청 답변 규약」 블록 추가 — 답변 말미에 `## 요청 항목 상태` 표(항목 · 상태 ∈ 완료|일부 완료|추가 확인 필요|결과 준비 중 · 근거 step/`call_id` · 전수/표본 · 결과 ID) 를 요구하고, **전수 요청에 표본만 있으면 「완료」로 쓰지 말라**는 규칙을 명문화. 프론트는 이 표를 일반 마크다운으로 렌더(파싱 강제 없음). 외부 번들(`external_tool_catalog.py`) 에도 같은 규약을 싣는다.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:441-486, 3935-3937, 3959-4010` · 신규 `routers/exports.py` + `app.py` include_router · `src/app.py:1378-1392`(scope resolver) · `routers/attachments.py:73-120, 907`(스트리밍·nosniff 관례) · `routers/system.py:85-110`(기존 `/api/file` — 유지·문서화, 같은 권한 키) · `static/app/messages.js:52-60, 84-135, 145-197, 316-360` · `static/console-job-poll.js:64-95` · `src/external_tool_catalog.py` · `unit/feature-0002-agent-core/src/modules/guidance_registry.py:37`(0002 MODIFY 교차) · 테스트 `unit/feature-0041-external-ai-tool-surface/tests/test_execute_sql_surface.py:237-286`(413·`_suppress_csv` 고정 — **의도적 개정**, 0041 MODIFY 교차).
- **acceptance** (요구서 DQA-04 완료 기준):
  - AC-04b-1: 0/10,000/10,001/89,623 행 합성 결과에서 미리보기 ≤50행 + `download_url` 로 전량 재조회 시 행수·sha256 일치.
  - AC-04b-2: `partial` 결과 다운로드 시도 → 409 + 상태 본문; `retry` → 새 `result_id`(`retry_of` 채움) 1회, `complete` 결과에 `retry` → 409; 화면은 「부분」표기.
  - AC-04b-3: `conversation.file.read.*` 미보유 계정 다운로드 403; 대화 접근 불가 403; TTL 만료 410. 권한 카탈로그(`web_context.py:730-757`)에 신규 코드 0건(테스트로 고정).
  - AC-04b-4: 러너 답변에 `## 요청 항목 상태` 표가 있고 전수 항목이 `결과 ID` 를 가리킴(프롬프트 테스트 + 실 왕복 1회).
  - AC-04b-5: PB-0009 실 DQA 앱에서 「미리보기 50행 / 전체 N행」 라벨과 다운로드 버튼 캡처(레이아웃 변경 → 픽셀-클래스 캡처).
- **guards**: 10,000행 모델 반환 상한·시간당 행/바이트 예산(`tool_ledger.py:26-27`) 불변. 신규 권한 코드·역할 grant 금지(생기면 §12.3 Critical 로 재분류·승인). 파일 경로를 응답에 노출하지 않음. `retry` 는 `partial|failed` 한정·1회.
- **effort**: 大
- **notes**: 요구서 §5 회귀값(89,623/18,524,408) 대조는 ITEM-10.

### ITEM-05a · Product 집계 정의 레지스트리 — 스키마·모듈·내부 주입 (DQA-05 · UX-04)
- **status**: pending
- **feature_id**: `feature-0002-agent-core`
- **dimension**: structural
- **risk_grade**: Major (프롬프트 주입 계약 변경 + 신규 테이블; 인증·인가 무변경)
- **depends_on**: []
- **enables**: [05b, 07]
- **why**: E-05a~d — 시간대·범위·코드 의미·계보를 매 실행 조사로 재확정. 현 구조에 Product 별 구조화 정의 저장이 없고(`WebProducts`/`WebSystemPrompts` 산문만), `_DATA_GROUNDING_GUIDANCE(agent_core.py:332-360)` 는 일반 정책 텍스트라 Product 사실을 담지 못한다. `metadata_column_stats.ts_min/ts_max`(alembic 0050) 는 관측 범위의 재료지만 시간대 귀속 없음·수집 정지 관측(`test_priority_stats_collection.py`).
- **fit_verdict**: adopt-with-guard
- **what**:
  1. alembic `<MAX+1>_product_definitions`: `product_definitions(scope_key varchar(96), definition_version int, kind ∈ timezone|data_range|reference_snapshot|code_dict|aggregation_unit|lineage|dedup_key|threshold, object_ref text, log_code text, field_name text, value_json jsonb, confidence ∈ observed|proposed|user_confirmed|unresolved, evidence_sql text, evidence_run_id text, evidence_call_id text, snapshot_at timestamptz, created_by text, created_at, PK(scope_key, definition_version, kind, object_ref, log_code, field_name))` + `product_definition_versions(scope_key, definition_version, note, created_at, active bool)`.
  2. `modules/kb_definitions.py`(`kb_metadata.py:52-295` 1:1 관례): list/upsert/propose/confirm/unresolve/new_version + `load_definition_context(scope_key, conn, user_message)` → 「PRODUCT DEFINITIONS v<N>」 블록(테이블별 저장 시간대·표시 시간대·실제 범위·참조 시점·코드별 필드 의미·집계 단위·계보(원본→Load/Error→정규)·중복 제거 키; 각 행에 `observed/proposed/user_confirmed/unresolved` 라벨). **기본값 없음** — 정의가 없으면 블록에 「미등록 — 조사 후 제안·확정 필요」만 남긴다(DK 규칙 고정 금지).
  3. `agent_core.py:3964 _build_knowledge_context` 에 정의 블록 레이어 추가(`:4049` 옆), `_DATA_GROUNDING_GUIDANCE` 를 「PRODUCT DEFINITIONS 를 먼저 따르고, 없으면 조사해 `propose_definition` 으로 제안하라」로 보강. `guidance_registry.py:37` 등록.
  4. **도구** `propose_definition`(내부·외부 표면 공용, `_tool_update_attachment` 관례): 모델이 `confidence=observed` 로만 기록(`proposed`/`user_confirmed` 는 도구에서 거절). 확정은 05b 의 관리 API 가 `kb.*.curate` 보유자에게만 허용. `describe_table` 응답에 해당 테이블의 등록 정의 요약 1줄을 덧붙인다.
- **entry_points**: `unit/feature-0002-agent-core/src/agent_core.py:332-360, 3964-4146, 8551-8556` · `modules/kb_metadata.py:52-295` · `modules/guidance_registry.py:37-95` · `modules/metadata_stats.py:579-650`(관측 범위 재료) · `modules/kb_write.py:162-210`(`user_confirm` 만 신뢰 — 선례) · `modules/tools.py:4424-4463`(도구 관례) · `shared/config.py:628-697`(scope key — 읽기만) · 테스트 `tests/test_gc_dialect_context.py:129-160`, `tests/test_kb_glossary_enum.py`.
- **acceptance** (요구서 DQA-05 완료 기준을 검증식으로):
  - AC-05a-1: `timezone=KST(user_confirmed)` 등록 Product 의 프롬프트에 「저장 시간대 KST」가 v<N> 헤더와 함께 정확히 1회 포함; 미등록 Product 는 「미등록」 문구만(DK 규칙 미유출).
  - AC-05a-2: `propose_definition` 은 `confidence=observed` 만 쓸 수 있고 `proposed`/`user_confirmed` 요청은 거절(테스트).
  - AC-05a-3: 정의 버전 bump 후 옛 버전 행은 보존·비활성, 컨텍스트는 활성 버전만.
  - AC-05a-4: `reference_snapshot`(DB 별 백업/참조 시점)·`lineage`(원본→Load/Error→정규 관계)·`dedup_key` 3종을 등록하면 블록에 각각 독립 절로 렌더되고, `lineage` 절은 「정규 로그와 대응한 Load 기록은 합산 제외」 문구를 포함한다(테스트 fixture).
  - AC-05a-5: alembic up/down 왕복 · migrate-lint PASS.
- **guards**: 정의는 근거(`evidence_*`) 없이 `user_confirmed` 가 될 수 없다. 모델은 확정 권한 없음. 기존 glossary/ENUM 레이어와 중복 확정 금지(정의 레지스트리는 시간대·범위·시점·코드 의미·계보·단위·중복키만).
- **effort**: 大
- **notes**: 요구서 §5 미확정 항목(시즌3 근거·상자 계보·복수 이름 귀속·잔액 차이 93,750) 은 `unresolved` 로 등록되는 것이 정상 — 제품 수정으로 확정하지 않는다.

### ITEM-05b · 정의 관리 API·UI · 외부 번들 주입 · 데이터소스 기본 시간대 (DQA-05 · UX-04)
- **status**: pending
- **feature_id**: `feature-0003-agent-web-ui`
- **dimension**: functional
- **risk_grade**: Major (관리 API·외부 AI 컨텍스트 계약; 쓰기 권한은 **기존 `kb.*.curate`** 재사용 — 신규 권한 코드 없음)
- **depends_on**: [05a]
- **enables**: [10]
- **why**: 외부 러너 번들(`ai_tools.py:745-805 _kb_grounding_sections/_PRODUCT_LAYERS`) 은 큐레이션 KB 만 담아 시간대·정의 계약을 받지 못한다. UX-04: SQL 을 읽지 않고 적용 기준·미확정 항목을 화면에서 확인해야 한다. **`user_confirmed` 정의는 그 Product 를 쓰는 모든 사용자의 시스템 프롬프트에 실리므로**, 확정 권한은 교차 사용자 주입면이다(리뷰 지적) → 확정은 큐레이션 권한자만.
- **fit_verdict**: adopt-with-guard
- **what**:
  1. `_PRODUCT_LAYERS` 에 정의 블록 레이어 1개 추가(헤더 텍스트 내부 경로와 일치, `:783` 주석 규칙) → `get_task_context` 가 외부 AI 에 같은 v<N> 블록을 준다.
  2. 관리 API(`admin_metadata.py:1571-1918` 패턴, 권한 `kb.*.curate` 재사용): 목록/등록/확정(`observed|proposed → user_confirmed`, 근거 필수)/미확정 처리/버전 bump — **전부 `kb.*.curate` 보유자만**. 대화 소유자(비큐레이터)는 대화 화면 「이 대화의 확정 사항」 카드에서 `propose_definition` 결과를 `observed → proposed` 로만 올릴 수 있고(승인 큐), `user_confirmed` 전환은 큐레이터가 한다. 프롬프트에는 `proposed` 도 라벨과 함께 실리되 「미확정」으로 취급하라는 문구를 붙인다.
  3. UI: `static/admin/metadata.js` 정의 서브탭(승인 큐 포함) + `static/admin/products.js` 활성 버전 표시. **UX-04 요약 카드**: 대화 상단(Product 핀 옆) 「서버·기간·저장 시간대·표시 시간대·집계 단위·확정 근거 / 미확정 N건 / 제안 M건」 접이식 카드(`static/app/` 신규 모듈, `[hidden]` 규약).
  4. `WebDatasources` 에 `ServerTimezone`, `StoredValueTimezone` additive 컬럼(fast/slow path 양쪽) + `shared/datasources.py:132 _row_to_ds` 통과 + 데이터소스 편집 UI 필드. 이 값은 **기본값**이며 테이블별 정의가 우선.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:745-805, 862-933` · `routers/admin_metadata.py:1571-1918, 2588-2745` · `routers/admin_datasources.py` · `routers/_bootstrap_schema.py:1392-1421, 511, 2987`(fast/slow path) · `shared/datasources.py:132` · `static/admin/metadata.js`, `static/admin/products.js`, `static/app/`(신규 카드) · 테스트 `tests/test_kb_external_reach.py:274`, `tests/test_kb_prompt_grounding.py:47-117`, `tests/test_metadata_phase2.py`.
- **acceptance**: AC-05b-1: 외부 `get_task_context` 응답에 내부와 동일 v<N> 정의 블록. AC-05b-2: 확정 API 는 `evidence_*` 없으면 400, `kb.*.curate` 미보유 계정은 403(대화 소유자여도), 소유자의 `proposed` 전환은 200. AC-05b-3: 기존 운영 DB 에 새 컬럼이 생김(fast path 테스트 — 컬럼 존재 assert). AC-05b-4: PB-0009 실 앱에서 요약 카드 렌더 캡처(신규 화면 → 픽셀-클래스). AC-05b-5: `timezone=KST(user_confirmed)` 등록 시 내부·외부 프롬프트 블록에 「LogTime 은 KST 저장 — UTC 변환(`DATEADD`/`CONVERT`) 금지」 문구가 정확히 1회 포함된다(프롬프트 문구 테스트; SQL 결과 정합 자체는 ITEM-10 이 실측).
- **guards**: 큐레이터만 확정·버전 bump. 대화 소유자는 제안까지. 정의 카드는 표시이지 집행이 아님(SQL 검증은 모델·리뷰 축). 신규 권한 코드 생기면 Critical 재분류.
- **effort**: 大
- **notes**: shared/ 편집 → `shared/docs/MODIFY.md` 교차 기록 + `--pre-commit feature-0003-agent-web-ui`.

### ITEM-06a · 첨부 per-file 결과·선택 재전달 서버 계약 (DQA-06 · UX-05)
- **status**: pending
- **feature_id**: `feature-0003-agent-web-ui`
- **dimension**: functional
- **risk_grade**: Major (shared 정본 `attachment_write.py` 계약 변경 — 워커·브리지·웹 3 호출자 공통)
- **depends_on**: []
- **enables**: [06b]
- **why**: E-06a — 「사유 미상 3건」 문구는 `shared/attachment_write.py:175-184` 가 `undelivered` **개수**만 알기 때문. 근본: `_materialize_assistant_attachment_new(_conv_store.py:2272-2281)` 에 `skipped` out-param 이 없어 빈 본문/크기/개수 상한(`blocks[:_cap]` :2326)/MinIO put/INSERT 실패가 전부 `continue`. `submit_answer(ai_tools.py:1090)` 응답은 생성·수정된 파일 목록을 러너에 돌려주지 않고(`_deliver_web_bridge_answer:2239` 내부 `:2334` 에서 materialize), 재제출은 답변 전체 재POST(409).
- **fit_verdict**: adopt
- **what**:
  1. `_materialize_assistant_attachment_new` 에 `results: list[dict]` out-param 추가 — 파일마다 `{filename, index, stage ∈ parse|count_cap|size_cap|permission|storage_put|db_insert|ok, error_code, error_detail(비밀 제외), retryable: bool, attachment_id|None, sha256}`. 편집 경로(`:1963-2059`) 의 `skipped: list[str]` 도 같은 구조로 통일.
  2. `shared/attachment_write.py::apply_assistant_attachment_blocks(:90-200)` 반환에 `files: list[...]` 추가; 본문 배너(:175-184) 는 **그 목록에서 생성**(파일명·단계·재시도 가능 여부 명시, 「사유 미상」은 실제로 분류 불가한 경우만). 저장 결과와 응답 첨부 목록이 같은 소스에서 나오므로 불일치 불가.
  3. `submit_answer`(`ai_tools.py:1090`) 응답에 `attachments: files[]` 에코(`_deliver_web_bridge_answer:2239-2334` 결과 전달). **첨부 전용 재제출** `POST /api/ai/tools/submit_attachments {task_id, blocks:[...]}` — `apply_assistant_attachment_blocks(blocks=…)` 직접 사용(`_conv_store.py:1971` 인자 존재), 답변 본문 무변경, 멱등키 = `sha256` + `UQ_WCA_VersionChain`(동일 sha256·동일 root 는 중복 생성 없이 기존 id 반환). SQL 재실행 없음(바이트가 블록 안에 있음).
  4. **UX-05**: `static/app/messages.js:371-450` 첨부 칩에 실패 상태(`composer.js:1437-1443 ATTACH_UPLOAD_RESULT` 재사용)·사유 툴팁·[실패 파일만 재시도] 버튼(러너에 `retry_attachments` 요청을 새 task 로 적재 — 06b 가 처리). 성공 파일 유지.
- **entry_points**: `shared/attachment_write.py:90-200` · `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py:1963-2059, 2272-2403(2326 count cap), 1909` · `routers/ai_tools.py:1090(submit_answer), 1372, 2083-2131, 2239-2334(_deliver_web_bridge_answer)` · `src/app.py:1486-1500`(상한 상수 — 러너와 공유하도록 `shared/attachment_write.py` 로 이동) · `static/app/messages.js:371-450` · `static/app/composer.js:1437-1443, 1649-1726`(재사용) · 테스트(의도적 개정, 각 소유 feature MODIFY 교차): `unit/feature-0043-external-llm-bridge/tests/test_bridge_attachment_write.py:207-276`, `unit/feature-0002-agent-core/tests/test_ask_worker_attachment_postprocess.py:401-466`, `unit/feature-0003-agent-web-ui/tests/test_attachment_new.py:255-328`(「사유 미상 1건」·silent skip 고정).
- **acceptance** (요구서 DQA-06):
  - AC-06a-1: 5개 블록 중 2개 실패(크기 초과·MinIO 실패 주입) → 응답 `attachments` 5건에 stage/error_code, 성공 3건 `attachment_id`; 배너에 실패 2건 파일명.
  - AC-06a-2: `submit_attachments` 로 실패 2건 재전달 → 성공, 기존 3건 무변경, 중복 첨부 0; 같은 요청 재전송 → 멱등(신규 행 0).
  - AC-06a-3: 개수 상한 초과 블록은 `stage=count_cap, retryable=true` 로 보고(무음 절단 금지).
  - AC-06a-4: 재시도 중 연결 단절 시뮬레이션(첫 요청 성공 후 응답 유실 → 재요청) → 중복 0.
- **guards**: 첨부 권한(`conversation.attachment.upload.*`) 경계 무변경. 상한 값 불변(5/1MB/확장자). 오류 상세에 MinIO 키·경로·토큰 미포함.
- **effort**: 大
- **notes**: shared/ 혼합 commit → `shared/docs/MODIFY.md` + `--pre-commit feature-0003-agent-web-ui`. 워커 경로(`modules/ask.py:299`) 회귀 필수.

### ITEM-06b · 러너 사전 검증·per-file 결과 처리·첨부 전용 재전달 (DQA-06)
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [06a]
- **enables**: []
- **why**: 코드맵 — `handler.py:210-269` 는 첨부를 답변 본문 fence 로만 싣고 사전 검증 0, 응답의 per-file 결과를 읽지 않으며(`_EV_TASK_SUBMIT_OK` 에 첨부 결과 없음), 실패 시 전체 payload 재POST.
- **fit_verdict**: adopt
- **what**: (1) 제출 전 fence 파싱 → 개수/크기/확장자 검증(06a 가 shared 로 옮긴 상수 사용), 초과분은 모델에 되돌려 분할 요청 또는 `attachment` 로 대체 안내. (2) `submit_answer` 응답 `attachments[]` 를 로그(`task.submit.attachments ok=N failed=M`) 와 다음 턴 컨텍스트에 반영, `retryable` 실패는 `submit_attachments` 로 자동 1회 재전달. (3) `retry_attachments` task 처리(06a UX 버튼) — 원 답변 재생성 없이 지정 파일 블록만 재구성·재제출. (4) 연결 단절 시 첨부 전용 재시도만 반복(답변 409 경로 무관). 빌드 생성물 동기화(공통 규칙 5).
- **entry_points**: `unit/feature-0043-external-llm-bridge/src/agent/handler.py:210-269` · `agent/prompt.py:151-154` · `src/bridge_runner.py:164, 211` · `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py` · 테스트 `tests/test_bridge_attachment_write.py`, `tests/test_bridge_agent_sync.py`.
- **acceptance**: AC-06b-1: 6개 첨부 시도 → 사전 검증이 6번째를 상한 초과로 보고(서버 미전송). AC-06b-2: 서버가 `retryable` 실패 1건 반환 → 자동 재전달 1회, 로그에 파일명. AC-06b-3: 실 Windows 러너 1회 왕복에서 첨부 3건 저장 확인 또는 `NOT-RUN`.
- **guards**: 자동 재전달은 1회. 모델 출력 원문을 로그에 남기지 않음.
- **effort**: 中

### ITEM-07 · 비용 보호 판단 4축 분리 · 운영 가시화 · 검증된 조사 결과 재사용 (DQA-07)
- **status**: pending
- **feature_id**: `feature-0002-agent-core`
- **dimension**: operational
- **risk_grade**: Major (가드 설정 노출·재사용 캐시 — 보호 완화 금지)
- **depends_on**: [02a, 02b, 05a]
- **enables**: []
- **why**: E-07a~c — 판정 근거·추정 종류가 기록되지 않고(02a/02b 가 기록 채널 확보), 추정 1축(`EstimateRows×EstimateExecutions` 최대 연산자 = 출력 행, `dialects.py:69-73`) 만 존재, 임계·모드는 `runtime_settings` 밖(재배포 필요), `_heavy_block_seen` 은 run 로컬 메모리, SQL 결과·계획 캐시 없음.
- **fit_verdict**: adopt-with-guard
- **what**:
  1. **4축 분리**(보고 전용, 게이트 불변): `_guard_out` 에 `estimate_rows(출력 추정)`, `estimate_scan_rows`(MySQL EXPLAIN `rows×filtered`, MSSQL `EstimateRows` 최하위 스캔 연산자 합), `total_subtree_cost`(MSSQL SHOWPLAN, 보고만), `returned_rows`, `elapsed_ms`, `logical_reads`(MSSQL `SET STATISTICS IO` 가 안전하게 가능한 경우만, 아니면 `null` + 사유). 거대 추정(예: 8.7e11) 은 `plan_facts` 원문 요약과 함께 기록해 사후 대조 가능.
  2. **운영 가시화**: `AGENT_QUERY_GUARD_MODE`·`AGENT_QUERY_EXPLAIN_ROWS_WARN` 을 `shared/runtime_settings.py`(restart scope, `test_live_setting_startup_drift_guard.py` 정합) 에 등록 → 관리 콘솔 표시(값 변경은 운영자, 기본값 불변). Product 별 임계 override 는 05a 레지스트리 `kind=threshold`(큐레이터 확정만).
  3. **cross-run 반복 판정**: `_heavy_block_seen` 을 `agent_runtime.steps.result_summary.guard` 조회로 보강 → 같은 대화의 같은 테이블 반복 차단 횟수를 근거로 안내 단계 승격.
  4. **검증된 조사 결과 재사용**: `sample_queries`(`:39-99`) 에 `definition_version`, `datasource_snapshot`(05a `reference_snapshot`), `plan_hash`, `verified_at`, `verified_result_id`(04a) 컬럼 additive; `describe_table`/`get_task_context` 가 「이 Product·정의 버전에서 검증된 조회 N건」을 요약 노출. 조건(정의 버전·스냅샷·스키마 지문) 이 다르면 재검증 요구 문구. 자동 실행 스킵 없음(모델 판단 근거만 제공).
- **entry_points**: `unit/feature-0002-agent-core/src/modules/tools.py:2773-2949, 3084-3160` · `modules/dialects.py:24, 60-73, 109-191, 673, 943-960, 1217` · `shared/config.py:1220-1260` · `shared/runtime_settings.py:~1311` · `modules/sample_queries.py:39-99, 194` · `modules/analysis_verify.py:294` · 테스트 `tests/test_query_guard.py`, `tests/test_query_guard_coaching.py:175-336`, `tests/test_mssql_load_estimate.py:174-238`, `tests/test_live_setting_startup_drift_guard.py`.
- **acceptance**: AC-07-1: 동일 SQL 의 step 기록에 4축 값이 분리 저장(추정 출력·추정 스캔·반환·시간, MSSQL 은 cost). AC-07-2: 임계·모드 변경 없이 기존 16/32/19 테스트 PASS. AC-07-3: 관리 콘솔 설정 화면에 게이트 모드·임계가 읽기 표시. AC-07-4: 정의 버전 bump 후 재사용 요약이 「재검증 필요」로 바뀐다. AC-07-5(문서 판정식): REPORT 의 개선 전후 비교 절은 ITEM-10 실측값만 인용하고 미실측 개선율(%) 문자열이 0건이다.
- **guards**: 보호 해제·임계 상향 금지(SECURITY §34). 과거 짧은 실행 시간을 안전 보장으로 쓰지 않음(재사용 요약에 「실행 시간은 참고값」 명시).
- **effort**: 大
- **notes**: shared/ 편집(`config.py`·`runtime_settings.py`) → `shared/docs/MODIFY.md` 교차 기록 + `--pre-commit feature-0002-agent-core`(§17 혼합 commit).

### ITEM-08 · 미리보기 무결성 — 행 경계 절단·잘림 플래그 정합·원본/표시 행수 (DQA-08)
- **status**: pending
- **feature_id**: `feature-0002-agent-core`
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [02a]
- **enables**: [10]
- **why**: E-08b + 코드맵 — `agent_core.py:5764-5786 _build_step_result_summary` 가 마크다운 500자(`_STEP_PREVIEW_CAP_CHARS:5761`) **문자 절단** → 반행(`| 12345 | 1`); `render.py:158-192 parse_result_preview_table` 이 `startswith("|")` 행을 빈 셀 패딩으로 정상 행으로 승격하고 `truncated` 를 잘려 나간 꼬리의 정규식으로 판정 → `preview_truncated=true` ∧ `preview_table.truncated=false`, 잘린 TID `1`. 프론트 `messages.js:313` 은 `truncated:false` 하드코딩, `:355` 는 표시 행수를 전체처럼 표기. 공유 뷰 화이트리스트(`app.py:2135`) 가 플래그를 버림.
- **fit_verdict**: adopt
- **what**: (1) 절단을 **행 경계**로(마지막 완전 행까지) 수행하고 `total_rows`/`shown_rows` 를 `_format_result_sets` 의 `stats` out-param(`tools.py:1821`) 에서 받아 `result_summary` 에 명시(`preview_rows_total`, `preview_rows_shown`, `preview_truncated`). (2) `parse_result_preview_table` 은 마지막 행이 열 수 불일치·미종료(`endsWith("|")` 아님) 면 **버리고 `partial_last_row=true`** 를 남기며, `truncated` 는 정규식이 아니라 stats 로 결정. (3) `messages.js:291-360` 은 서버 플래그·행수를 그대로 사용해 「N행 중 M행 표시」를 렌더, 반행 렌더 금지. (4) `app.py:2135 _SHARE_RESULT_SUMMARY_ALLOWED_KEYS` 에 `preview_truncated`·행수 키 허용(값 노출 아님). (5) 프론트 `STEP_PREVIEW_CAP` 중복 상수 제거(서버 값 사용).
- **entry_points**: `unit/feature-0002-agent-core/src/agent_core.py:5745-5793` · `modules/render.py:158-230` · `modules/tools.py:1817-1900` · (feature-0003 — MODIFY 교차 기록) `unit/feature-0003-agent-web-ui/src/app.py:2135` · `static/app/messages.js:291-360` · `static/app.js:3548-3581, 3667-3713` · `static/share.js:1369-1375, 1506` · 테스트 `tests/test_read_attachment_completeness_contract.py:197-235`, `unit/feature-0003-agent-web-ui/tests/headless/test_step_preview_note.js`, `tests/test_share_redaction_invariant.py:145-232`.
- **acceptance**: AC-08-1: 500자 경계가 행 중간에 오는 합성 결과 → preview 마지막 줄이 완전 행, `preview_table.truncated == preview_truncated == true`, 표 행수 == 완전 행수. AC-08-2: 필드 중간 절단 값(`1`) 이 표에 나타나지 않음. AC-08-3: UI/API/공유 뷰 세 곳의 원본·표시·잘림 값 동일(jsdom + 서버 테스트). AC-08-4: PB-0009 실 앱 캡처 1회(표 하단 「N행 중 M행」 표기 — 픽셀-클래스).
- **guards**: 미리보기 상한 불변. 공유 뷰에 셀 값 추가 노출 없음.
- **effort**: 中
- **notes**: 0003 파일 편집은 feature-0003 MODIFY 교차 기록; verify 는 `feature-0002-agent-core`.

### ITEM-09a · 연결 진단 — 실행 위치·주소 해석·마지막 성공·실패 분류 (DQA-09 연결 진단 · UX-01)
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: []
- **why**: E-09a + 코드맵 — 러너 `api.py:120-133` 은 비HTTP 실패를 한 버킷(`_failed`)으로, `lifecycle.py:692-731 --check` 는 401 만 구분; `conf.py:15-58 config.json`·`core.py:639-655 server.json` 에 마지막 성공 시각·해석 주소 없음; `/api/ai/connect/status(oauth_as.py:808-830)` 에 주소·마지막 성공 없음. 주소 자동 추정은 어디에도 없음(유지, `core.py:693 usable_base`·`:578 pin_server`).
- **fit_verdict**: adopt
- **what**: (1) 러너: 실패 분류 `address(DNS/refused/timeout/TLS)|auth(401)|permission(403)|server(5xx)` + `resolved_host/ip`, `--check` 출력에 「실행 위치(WSL·distro·user / Windows) · 설정 주소 · 해석 결과 · 마지막 성공 <시각·주소> · 실패 분류」 5행; `config.json` 에 `last_ok_at`, `last_ok_base` 저장(비밀 없음). heartbeat 로 `runner_host_kind`·`last_ok_at`·`configured_base_host` 를 **02b 가 정의한 선택 필드로 발신만** 한다(서버 인입 코드는 02b 소유 — 본 ITEM 은 `bridge_heartbeat` 핸들러를 편집하지 않음). (2) 클라이언트: `server.json` 에 `last_ok_at` 추가, `gui.py:488-556`·`bridge.py:522-533` 가 분류된 실패 문구 표시(원문 400자 대신). (3) 서버: `/api/ai/connect/status`(`oauth_as.py:808-830`) 에 heartbeat 저장값(`runner_location`, `last_ok_at`, `configured_base_host`) 노출(01a 의 모달이 렌더). **주소 자동 변경 없음**.
- **entry_points**: `unit/feature-0043-external-llm-bridge/src/agent/api.py:93-133` · `agent/lifecycle.py:692-731` · `agent/conf.py:15-64` · (feature-0046 — MODIFY 교차) `unit/feature-0046-native-client/src/client/core.py:114-210, 558-655, 693-755, 1248-1272` · `client/gui.py:488-556` · `client/bridge.py:522-533` · (feature-0003 — MODIFY 교차) `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:582-600, 808-830` · 테스트 `tests/test_connect_guidance.py:46-235`, `tests/test_connect_funnel.py:167-261`, `tests/test_cli_failure_reason.py`, `unit/feature-0046-native-client/tests/test_wsl_and_scheme.py`.
- **acceptance**: AC-09a-1: 잘못된 호스트(연결 거부)·만료 토큰(401)·권한 없는 계정(403) 세 fixture 가 서로 다른 분류·문구를 낸다. AC-09a-2: 성공 후 `config.json`/`server.json` 에 `last_ok_at` 기록, 다음 실패 시 「마지막 성공: <시각> @ <주소>」 표시. AC-09a-3: 어떤 경로에서도 base 를 추정 값으로 변경하지 않음(테스트: 실패 후 base 불변). AC-09a-4: 실 WSL→Windows 호스트 주소 변경 재현 1회(memory 레시피) 또는 `NOT-RUN`.
- **guards**: 비밀·토큰 미기록. 자동 재설정 금지. `ai_tools.py bridge_heartbeat` 핸들러 무편집(02b 와 충돌 방지).
- **effort**: 中

### ITEM-09c · 좁은 화면(≤680px) 사이드바 드로어·새 대화 접근 (DQA-09 좁은 화면 · UX-06)
- **status**: pending
- **feature_id**: `feature-0003-agent-web-ui`
- **dimension**: functional
- **risk_grade**: Minor (UI 추가, 서버 무변경)
- **depends_on**: []
- **enables**: []
- **why**: E-09c + 코드맵 — `static/css/profile.css:487-499` 의 `@media (max-width: 680px) { .sidebar { display: none } }` 가 대화 목록과 유일한 「새 대화」 진입(`index.html:113-117 #newConversationBtn`) 을 숨기고 토글이 없다. 680 은 CSS + `app.js:3815` + `profile.js:846` 세 곳 하드코딩. 미닫힘 `@media` 사고 이력(`test_conn_chip_css_scope.py`).
- **fit_verdict**: adopt
- **what**: (1) `display:none` → off-canvas 드로어(`.sidebar[data-drawer]`, transform 슬라이드, 배경 dim, ESC 닫기). (2) 헤더에 토글 버튼(`aria-label="대화 목록"`, `aria-expanded`, `aria-controls="sidebar"`) + 드로어 밖에도 「새 대화」 버튼(같은 `newConversationBtn` 핸들러 재사용) 노출. (3) 680 임계를 CSS 변수 `--bp-narrow` 와 JS 상수 1곳으로 통일(`shell.css` 로 규칙 이동 — 반응형 규칙이 `profile.css` 에 숨어 있던 문제 해소). (4) 검증: jsdom `tests/verify_sidebar_drawer.mjs`(574px 에서 토글·새 대화 접근·키보드 Tab/Enter/ESC·접근성 이름) + 정적 가드 `tests/test_sidebar_media_scope.py`(브레이스 균형·`@media` 범위, `test_conn_chip_css_scope.py` 모델) + `search-audit.css` 의 `{`747/`}`748 불균형 실측 확인(주석 안이면 기록만). (5) PB-0009 실 DQA 앱 창 폭 574px 캡처 + 데스크톱 폭 회귀 캡처(레이아웃 → 픽셀-클래스). 보조 PB-0008.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/static/css/profile.css:478-499` · `static/css/shell.css:4-6, 128-190` · `static/css/base.css:102` · `static/index.html:102-137, 167` · `static/app.js:3815-3817` · `static/app/profile.js:846-847` · `static/app/sidebar.js` · 테스트 `tests/verify_sidebar_resize.mjs`, `tests/test_conn_chip_css_scope.py`.
- **acceptance** (UX-06): 약 574px 과 일반 데스크톱 폭에서 대화 목록·새 대화 접근 가능(캡처 2장), 키보드만으로 열기·새 대화·닫기 가능, 접근성 트리에 이름 존재. 기존 리사이저 동작 회귀 0.
- **guards**: 실 렌더 캡처 없이 PASS 금지(memory: CSS 규칙 존재 ≠ 적용). 캐시버스터 수기 bump 금지(빌드 주입).
- **effort**: 中

### ITEM-09d · 시스템 지침 역할 보존 채널 (DQA-09 긴 지침)
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Major (모델에 지침이 도달하는 채널 변경 — 도구·안전 규약 영향)
- **depends_on**: [02c]
- **enables**: []
- **why**: E-09d + 코드맵 — `invoke.py:612-651 system_channel_supported` 는 Claude 만 지원, 길이 초과(`:653-678`) 시 본문 폴백(`prompt.py:38-50`) → `system_delivery=user_body`. `PROMPT_DELIVERY.md` 가 폴백을 설계로 기술하고 파일 전달은 「별도 검증 필요」로 남김.
- **fit_verdict**: adopt-with-guard
- **what**: (1) Claude: `--append-system-prompt-file <임시파일>`(설치 CLI 2.1.258 지원 확인) 을 길이 초과 시 1차 대안으로, 본문 폴백은 최후수단. (2) Codex: `developer_instructions` 를 **CLI override(`-c …`)** 로 전달 가능한지 검증 후 채택(사용자 `config.toml` 무변경), 미지원이면 본문 폴백 유지·기록. (3) `system_delivery` 값에 `system_file|system_arg|developer_config|user_body` 를 구분, `handler.py:114` 진단 유지. (4) 회귀: 길이(6만 자 한국어)·줄바꿈·특수문자(`⟦⟧`·따옴표·`$`) 가 최종 프로세스 경계까지 보존(`test_cmdline_length_limit.py`·`test_prompt_layer_delivery.py:234` 확장) + **실 Windows** 1회(argv 상한 재현 머신). 파일 임시 경로는 사용자 홈 아래·0600·종료 시 삭제.
- **entry_points**: `unit/feature-0043-external-llm-bridge/src/agent/invoke.py:143-174, 223-240, 612-694, 801` · `agent/prompt.py:15-50` · `agent/runtimes.py:72-125, 163` · `agent/handler.py:92-116` · `docs/PROMPT_DELIVERY.md` · 테스트 `tests/test_cmdline_length_limit.py:73-214`, `tests/test_prompt_layer_delivery.py:102-234`, `tests/test_child_io_encoding.py`.
- **acceptance**: AC-09d-1: 34,962자 지침 Windows → `system_delivery=system_file`, 여섯 계층 순서·전체 문자열 보존. AC-09d-2: 파일 채널 실패 주입 → `user_body` 폴백 + 경고 로그. AC-09d-3: 실 Windows 왕복 1회 또는 `NOT-RUN`.
- **guards**: 기존 도구·안전 규약 지침이 시스템 채널에서 빠지지 않음(전체 지침을 provider 기본 system 으로 교체하지 않음). 임시 파일에 비밀 없음 확인(지침엔 자격증명이 없어야 하며, 있으면 secret scan 이 잡는다). 사용자 머신 설정 파일 무변경.
- **effort**: 中

### ITEM-10 · 통합 검증 — 고정 복원본 회귀 기준값·계보 대조 (요구서 §5·§6)
- **status**: pending
- **feature_id**: `feature-0003-agent-web-ui`(Run 기록 홈; 코드 변경 없음)
- **dimension**: operational
- **risk_grade**: Minor (읽기 전용 실측)
- **depends_on**: [04b, 05b, 08]
- **why**: 요구서 §5 값은 fixture 가 아닌 실 복원본에서만 의미. 코드 상수 금지.
- **what**: Product 91·`mssql_local` 이 접근 가능하면 DQA 클라이언트/API 로 (a) 전수 사용 로그 → 결과 ID 다운로드 후 89,623행·18,524,408 대조 (b) 일별 사용 8값 (c) 플로린 합계 4,396,089,877 — 이때 **정규 로그와 대응한 Load 305행 미합산·원본 후속 236건 포함**(계보 정의 적용) 확인 (d) 이름 매칭 3분류(단일 2,756/복수 264/미매칭 92) 와 **복수 후보 금액 미합산** (e) KST 자정 경계 1건(08-27 00:00 직전/직후 행이 날짜 이동 없음) — 모두 **DQA 실행 + 다운로드 파일 재조회**. 개선 전후 execute_sql 호출 수·소요 시간을 같은 요청으로 1회 비교 기록(개선율 수치는 실측만). 접근 불가 시 `NOT-RUN` + 사유. Run 은 `unit/feature-0003-agent-web-ui/docs/test-runs.d/META-0076-integration.md`.
- **acceptance**: 5 대조 모두 일치 또는 불일치 원인 기록; 미확정 항목(93,750 차이 등) 은 그대로 미확정 유지.
- **guards**: 통계 DB 읽기 전용, 무거운 전수 조회 반복 금지(1회).
- **effort**: 中

## 4. 보류·기각 (재논의 방지)

| finding / 제안 | verdict | 사유 |
|---|---|---|
| 10,000행 모델 반환 상한 상향 | 기각 | 요구서 DQA-04 명시 금지. 미리보기/전수 분리(04a·04b)가 대체 |
| 승인 기능 비활성화·`--dangerously-skip-permissions`·`Bash(*)` 포괄 허용 | 기각 | 요구서 DQA-02 명시 금지. DQA 전용 도구 채널(02c)이 대체 |
| 관리자 계정명 기반 비공개 Product 전체 접근 | 기각 | 요구서 DQA-03·SECURITY §28.6. 생성 시 원자 grant(03)가 대체 |
| 내보내기용 신규 권한 코드 `conversation.export.read.*` + 역할 grant | 기각(설계 변경) | §12.3 인가 코드 변경 = Critical(fit review 지적). 기존 `conversation.file.read.*` 재사용으로 대체 — 같은 데이터(SQL 결과 CSV)·같은 권한 |
| 비큐레이터(대화 소유자)의 정의 `user_confirmed` 직접 확정 | 기각(설계 변경) | 확정 정의는 Product 전 사용자 프롬프트에 주입 → 교차 사용자 주입면(fit review). 소유자는 `proposed` 까지, 확정은 `kb.*.curate` |
| `shared/db.py execute_sql` 자체를 스트리밍으로 변경 | 기각(설계 변경) | 워커·웹·metadata_stats 전 호출자 폭발반경. 옆에 `execute_sql_stream` 신설, 기존 무변경 |
| 결과 저장소를 MinIO 로 즉시 이관 | 보류 | `storage_minio.py` 스트리밍 helper 부재(코드맵). 04a 는 파일시스템 + 레지스트리로 시작, MinIO 는 후속 ITEM 후보 |
| `agent_runtime.steps` 에 `UNIQUE(conversation_id, run_id, step_index)` | 보류 | 02b 의 트랜잭션 수정으로 경합 해소 후 관측. 제약 선행 시 구 러너 경합 INSERT 실패 창 발생 |
| 정의 레지스트리에 DK 규칙(KST·코드 사전) 기본 탑재 | 기각 | 요구서 DQA-05 「DK 전용 규칙을 모든 Product 기본값으로 고정 금지」. 운영자가 Product 91 에 등록 |
| 요구서 §5 미확정 항목(시즌3 근거·상자 계보·복수 이름 귀속·잔액 차이 93,750) 의 제품 코드 확정 | 기각 | 데이터·업무 정의 부재. `unresolved` 정의로 남김 |
| 사용성 개선율(%) 제시 | 기각 | 요구서 §3.1: 기준 측정 없는 비율 금지. ITEM-10 실측 비교만 |
| DBA 사용자 사용성 검증(시나리오 ①②③) | 사람 수행 | 자동 UI 검증과 구분해 보고. 각 ITEM 의 PB-0009 Run 은 AI 실측이며 사람 검증 대체 아님 |

## 5. 진행 현황 (오케스트레이터 갱신)

- 총 **18** ITEM(02a·02b·02c·01a·01b·03·04a·04b·05a·05b·06a·06b·07·08·09a·09c·09d·10; 09b 는 03 에 흡수된 결번) · done 0 · in-progress 0 · pending 15 · blocked 3 (01a·01b·03 — `needs-human-plan-approval`)
- 다음 ready: **W1 = ITEM-02a · ITEM-09c** (+ ITEM-03 은 승인 후)
- ITEM 별 worktree/branch/PR/검증 결과는 아래 표에 append 한다.

| ITEM | worktree / branch | PR | 검증 요지 | 상태 |
|---|---|---|---|---|

## 6. 요구서 §6 필수 검증 → ITEM 매핑

| 요구서 검증 항목 | ITEM (AC) |
|---|---|
| 다른 계정 요청·동일 계정 정상 인수·이중 인수·재연결·중복 클릭·취소 후 재시도 | 01a(AC-01a-1~3) · 01b |
| 승인 거절·정책 미실행·**DB 실패**·첨부 실패 시 웹/API/bridge/이력 상태 일치 | 02a(AC-02a-1 failed 포함) · 02b(AC-02b-1 4케이스, AC-02b-3) · 02c(AC-02c-2) · 06a |
| 비공개 Product 생성 성공·초기 멤버 저장 실패 원자성·무권한 거절 | 03(AC-03-1~3) |
| 전수 내보내기 0/10,000/10,001/89,623 경계·중단·취소·용량 초과·**재시도**·권한 철회 | 04a(AC-04a-1~3) · 04b(AC-04b-1~3, retry) |
| KST 자정 전후·부분일·참조 DB 시점 불일치·정규/Load/Error 중복·누락·복수 이름 금액 중복 방지 | 05a(AC-05a-1, AC-05a-4 reference_snapshot·lineage·dedup) · 05b(AC-05b-5) · 10(c·d·e) |
| 병렬 호출 **순서 역전**·미리보기 행/필드 중간 잘림·첨부 일부 실패 후 선택 재전달 | 02a(AC-02a-2) · 02b(AC-02b-2 순서 안정) · 08 · 06a(AC-06a-1~4) |
| 설명 길이 경계·한글·**특수문자**·긴 지침 역할 보존·좁은 화면 새 대화 접근 | 03(AC-03-4) · 09d · 09c |
| UX-02 근거 없는 진행률·ETA 금지 | 02b(AC-02b-5 부정 단언) |
| 사용 흐름 ① 연결 불일치 해결 | 01a·01b·09a (AI 실측) + 사람 검증(§4) |
| 사용 흐름 ② 여러 요청 진행·확인 질문 | 02b·04b(UX-03) |
| 사용 흐름 ③ 전수 다운로드·첨부 실패 복구 | 04b·06a·06b |
