---
doc_type: TEST
feature_id: feature-0002-agent-core
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- `insight-worker` 가 `fingerprint` 만이 아니라 `Fact/Text/RagDocument/RagObject` 완전성까지 보고 후보를 다시 선정하는지 확인
- 기존 fact 가 남은 객체는 RAG/Text/Object 를 우선 복구하는지 확인
- 복구 불가 객체는 LLM 재생성 후 검증을 거친 뒤에만 fingerprint/refresh 마커를 갱신하는지 확인
- `insight_route.log` 에 실제 참조 schema/table/column 과 action/reason/result 가 남는지 확인
- 로그가 `/shared/logs/YYYY-MM-DD/` 로 기록되고 `7일 초과` 날짜 디렉토리가 `tar.gz` 로 압축되는지 확인
- no-op cycle 이 더 이상 요약/타이밍 로그를 누적하지 않는지 확인

## 2. Test Cases
- TEST-20260713-readonly-query-shapes: `pytest unit/feature-0002-agent-core/tests/test_readonly_query_shapes.py` — read-only shape 확장(FR-readonly-query-shapes-overblock). 허용: UNION/UNION ALL of SELECTs(SET_OP)·WITH+UNION·read-only SHOW(CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES). **보안 회귀 0**: UNION 분기 forbidden-schema/lock/into/금지함수 차단 · SHOW 대상 forbidden schema 차단 · 비-read-only SHOW(GRANTS/DATABASES/PROCESSLIST/PRIVILEGES) 차단 · SHOW CREATE PROCEDURE/FUNCTION 계속 거부(describe_routine 유도) · DELETE/UPDATE/multi-statement/INTO OUTFILE 차단 · collect_schema_refs 가 SHOW `.db` 수집(제품 allowlist 강제)·서버-전역 SHOW 는 스키마참조 0. 회귀 게이트: `test_gc_dialect_context.py`(UNION 교정 tip 제거 반영)·`test_query_guard`·`test_sql_trust_boundary`·`test_mssql_security_boundary`.
- TEST-20260713-describe-routine: `pytest unit/feature-0002-agent-core/tests/test_describe_routine_tool.py` (20건) — describe_routine 도구 + SHOW CREATE 유도(FR-show-create-routine-blocked). (a) **보안 불변식 보존**: `sql_guard.validate_sql_for_sandbox` 가 여전히 `SHOW CREATE PROCEDURE/FUNCTION` 거부(SELECT/CTE-only 미변경) 2건. (b) L2 유도 힌트: SHOW CREATE PROCEDURE/FUNCTION·SHOW (PROCEDURE|FUNCTION) STATUS → describe_routine 안내, SELECT·SHOW CREATE TABLE 은 미유도 4건. (c) execute_sql 거부 메시지에 유도 포함 1건. (d) 도구 등록: `_TOOL_HANDLERS` + **핵심 `TOOL_DEFINITIONS`(LLM 실노출)** 2건. (e) dialect SQL(MySQL ROUTINES/PARAMETERS·MSSQL OBJECT_DEFINITION) 3건. (f) `_tool_describe_routine` 동작: happy(정의 본문+파라미터)·not-found·무권한(정의 NULL→권한 안내)·필수인자·`agent_memory` 내부스키마 차단 5건. 회귀 게이트: `test_query_guard`/`test_sql_trust_boundary`/`test_mssql_security_boundary` 재통과(보안 회귀 0).
- TEST-0009: `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
- TEST-0010: `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
- TEST-0011: web 컨테이너 내부에서 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")`를 호출해 Role 공통 지침이 누적되는지 확인
- TEST-0012: `tests/test_compose_system_prompt.py`에서 Product → Role → Account 순서와 최종 user request 메시지 보존을 확인
- TEST-0001: `python3 -m py_compile unit/feature-0002-agent-core/src/modules/utils.py unit/feature-0002-agent-core/src/modules/insight.py`
- TEST-0002: 기준선으로 `table_fp:*`, `table_insight` fact/doc/object 수, fact 자체가 없는 incomplete 수를 기록
- TEST-0003: host override 환경에서 `run_insight_cycle('manual-insight-test')` 실행
- TEST-0004: cycle 후 `table_insight` fact/object 수가 증가하고 incomplete 수가 감소하는지 확인
- TEST-0005: `artifacts/shared/logs/YYYY-MM-DD/insight_route.log` 에 `artifact_missing`, `repair_from_fact`, `generate_insight`, `verify_persist`, `referenced_objects` 가 남는지 확인
- TEST-0006: `artifacts/shared/logs/YYYY-MM-DD/insight_worker.log` 가 실제 스캔 요약만 남기고 idle heartbeat 를 남기지 않는지 확인
- TEST-0007: `run_insight_cycle('manual-insight-noop')` 직후 같은 날짜 디렉토리에 no-op 전용 `timing_breakdown`/`insight_worker` 파일이 추가되지 않는지 확인
- TEST-0008: 오래된 샘플 디렉토리 생성 후 `append_log_line('archive_probe', ...)` 호출 시 `archive/YYYY-MM-DD.tar.gz` 가 생성되는지 확인
- TEST-20260710-auth-cooldown: `pytest tests/test_mssql_auth_cooldown.py` — MSSQL insight 순회 **로그인실패**(18456) 조기 skip + **datasource label 키** cooldown 검증(REV-20260710 흡수). (a) cooldown 헬퍼/prune 6건(set/active·만료 자동정리·clear·ttl=0 비활성·None key·`_prune_auth_cooldown` 삭제/rename 누수 차단), (b) `run_insight_cycle` 순회 통합 5건: 같은 datasource 10 DB 중 첫 18456 시 실제 connect 1회만(AC1), cooldown 중 다음 cycle connect 0회(AC2), `AGENT_INSIGHT_AUTH_COOLDOWN_SEC=0` 시 cycle 내 skip 유지·cycle 간 재시도(AC4), **HIGH-1 같은 host:port 다른 login 은 연쇄차단 안 됨**(`test_different_login_same_endpoint_not_chained`), **HIGH-2 916("Cannot open database")은 다른 DB 순회 계속**(`test_per_db_916_does_not_skip_other_dbs`).

## 3. Test Run History
- 2026-07-16 (TASK-20260716-redteam-axis-rederive — 자가검증 BLOCK 축 인지 재도출):
  - `python3 -m py_compile src/modules/redteam.py shared/runtime_settings.py src/agent_core.py` → 통과.
  - 로컬 `pytest -q unit/feature-0002-agent-core/tests/test_redteam.py`(PYTHONPATH=src:worktree) → **31 passed** (기존 21 + 신규 10: 축별 라우팅·completeness max 게이팅·evidence 재계산·rederive disabled/무산출 폴백·인젝션 sentinel·B1 sentinel breakout 차단).
  - 재사용 `mysql-ai-agent:current` 이미지 + worktree `/work` 마운트 + PYTHONPATH(pip install pytest) 로 `pytest unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests` **전체 스위트 → RC=0 (회귀 0, §18.8 적대 리뷰 B1/W1/W2 흡수 반영본)**. 리뷰 흡수 전 기준선 2145 passed/2 skipped → B1 테스트 1건 추가. `.env` 없는 worktree 라 `make test`(dc-build compose 변수 미해석 "invalid proto") 대신 이미지 직접 재사용 경로(project-pytest-worktree-pycache-gotcha).
  - 신규 테스트 검증 초점: (a) sql BLOCK→rederive 경로, grounding BLOCK→텍스트 재작성 경로 분리 (b) completeness 는 높음(2)에서 텍스트·매우높음(3)에서 rederive (c) rederive 새 도구 근거가 verify evidence 에 반영 (d) REDTEAM_REDERIVE_ENABLED=0/rederive 무산출 시 텍스트 폴백 (e) build_rederive_instruction 인젝션 sentinel 유지.
  - 백엔드(답변 파이프라인/설정/migration) 변경 — 웹/UI static·template 무변경 → PB-0008 Windows-browser N/A(visual_verification_scope 트리거 아님). 라이브 실증(redteam_reviews.rederive_applied/tool_rounds 관측)은 배포(web+worker 재빌드) 후 REPORT 분리분.
- 2026-07-13 (TASK-20260713T171821-readonly-query-shapes — conversation_audit FR-readonly-query-shapes-overblock):
  - `python3 -m py_compile src/modules/sql_guard.py src/modules/tools.py` → 통과. standalone sql_guard 스모크 19/19(UNION 허용·분기 보안차단·read-only SHOW 허용·forbidden/비-readonly SHOW 차단·기존 불변식).
  - 재사용 `repo-ask-worker:latest` + worktree `/work` 마운트 + PYTHONPATH(pip install pytest) 로 `pytest unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests` **전체 스위트 → RC=0(1896 passed)**. 1차 run 에서 `test_gc_dialect_context.py::test_dialect_hint_mysql_corrects_tsql` 1건 FAIL(stale UNION-불가 tip 단언) → UNION 허용 동작 반영해 단언 갱신 후 RC=0.
  - 백엔드(sql_guard/tools) 변경 — web surface 없음 → PB-0008 N/A. 배포 후 라이브 대화 실측(UNION·SHOW CREATE TABLE 정상 조회)은 Phase 11b 분리(REPORT/LEDGER 참조).
- 2026-07-13 (TASK-20260713T140405-describe-routine-tool — conversation_audit FR-show-create-routine-blocked):
  - `python3 -m py_compile src/modules/dialects.py src/modules/tools.py` → 통과.
  - 재사용 `repo-ask-worker:latest` 이미지 + worktree `/work` 마운트 + PYTHONPATH(pip install pytest) 로 `pytest unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests` **전체 스위트 → RC=0**(실패/에러 0, skip 2). `.env` 없는 worktree 라 `make test`(compose 변수 미해석 "invalid proto") 대신 이미지 직접 재사용 경로 사용(project-pytest-worktree-pycache-gotcha).
  - 타깃 재확인: `test_describe_routine_tool.py`(신규 20) + `test_query_guard.py`+`test_sql_trust_boundary.py`+`test_mssql_security_boundary.py` → **123 PASS, RC=0**. 보안 가드 3파일 재통과 = sql_guard SELECT/CTE-only 불변식·allowlist 회귀 0.
  - 백엔드(도구/dialect) + 도구 정의 변경 — 웹 surface 는 narration 라벨(feature-0003 companion, graceful fallback)만이라 PB-0008 Windows-browser 는 배포 후 라이브 대화 실측분(Phase 11b, REPORT/LEDGER 참조).
- 2026-07-10 (TASK-20260710-mssql-auth-cooldown — codex 디스크 I/O 장애조사 트랙 B):
  - `python3 -m py_compile shared/config.py unit/feature-0002-agent-core/src/modules/insight.py` → 통과 (TEST-0001 계열).
  - 신규 `tests/test_mssql_auth_cooldown.py` (DB 없이 monkeypatch, connect 호출 카운트) → **11 passed**: cooldown 헬퍼/prune 6 + 순회 통합 5(AC1 connect 1회 / AC2 cooldown skip 0회 / AC4 ttl=0 재시도 / HIGH-1 다른 login 독립 / HIGH-2 916 다른 DB 계속). §18.8 적대 리뷰 REV-20260710T191159-mssql-auth-cooldown(HIGH2+MED2+LOW2 실증 전건 흡수)로 8→11 확장(HIGH-1 datasource-label 키·HIGH-2 `_is_login_failure` 18456 우선·LOW-5 prune 회귀 고정).
  - 회귀 확인: insight/mssql/datasource 관련 기존 테스트 8파일 → **87 passed** (test_task0255_insight_edge_log, test_task0305_insight_bottleneck, test_mssql_three_tier_insight, test_multi_datasource, test_insight_table_grouping/degraded_backoff/heartbeat_liveness/rel_cadence). 합계 **98 PASS 회귀 0**.
  - 재검증(resume, 2026-07-10 세션 재개): 재사용 `repo-ask-worker` 이미지 + worktree 마운트 + PYTHONPATH 로 `pytest unit/feature-0002-agent-core/tests` 전체 재실행 → **1054 passed, 2 skipped, 회귀 0**(auth-cooldown 11 포함). py_compile(config.py·insight.py·test) PASS.
  - 백엔드(insight-worker 순회 로직) 변경 — 웹/UI surface 없음 → PB-0008 Windows-browser N/A. 운영 조치(계정/GRANT/InsightEnabled)는 저장소 세션 범위 밖(REPORT 참조).
- 2026-06-08 (TASK-0160 중단 run 고아 tool_use 히스토리 정합화):
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py` → 통과.
  - 신규 `tests/test_history_tooluse_sanitize.py` (agent 이미지, `--no-deps`, DB 없이 순수 함수) → **6 passed**:
    - 고아 tool_use 턴 drop / 부분(2개 중 1개 결과) 턴 drop / EOF·윈도우 경계 고아 drop / 매칭 없는 고아 tool 행 drop / 유효 멀티턴 보존 / `_parsed_tool_calls` 마커 보존.
  - 비-web/UI 백엔드 변경(`agent_core._normalize_history_rows`) → PB-0008 Windows-browser N/A. 라이브 검증: 배포 후 대화 `20260608025216-3014b095` 재질의 200 + 신규 중단 시 query-time 자동 정합화 — STATUS/REPORT TASK-0160 참조.
- 2026-05-15:
  - 추가 검증:
    - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py`
      - 결과: 통과
    - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
      - 결과: 3건 통과
    - 확인: Product → Role → Account 순서, Account common+specific 누적, 최종 user request 메시지 보존
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
    - 결과: 통과
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
    - 결과: 2건 통과
  - web 컨테이너 내부 직접 조회
    - 결과: `HAS_PRODUCT_CONTEXT=True`, `HAS_ROLE_COMMON=True`, `HAS_SALES=True`
- 2026-04-21:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/utils.py unit/feature-0002-agent-core/src/modules/insight.py`
    - 결과: 통과
  - 기준선 집계
    - `table_fp:*`: `154`
    - `table_insight` fact: `28`
    - `table_insight` rag document: `56`
    - `table_insight` rag object: `28`
    - fact 자체가 없는 incomplete table: `126`
  - 실제 cycle 실행
    - 명령: host override 환경에서 `run_insight_cycle('manual-insight-test')`
    - 결과: `duration_ms=149886.45`, `scan_triggered=1`, `schemas_evaluated=2`, `tables_selected=10`, `tables_generated=2`, `artifact_missing_selected=5`
    - cycle 후 집계:
      - `table_insight` fact: `28 -> 30`
      - `table_insight` rag object: `28 -> 30`
      - fact 자체가 없는 incomplete table: `126 -> 124`
  - 로그 구조 검증
    - 생성 파일:
      - `artifacts/shared/logs/2026-04-21/insight_route.log`
      - `artifacts/shared/logs/2026-04-21/insight_worker.log`
      - `artifacts/shared/logs/2026-04-21/timing_breakdown_manual-insight-test.json`
    - route log 예시:
      - `phase=publish`, `action=repair_from_fact`, `result=unavailable`
      - `phase=publish`, `action=generate_insight`, `result=ok`
      - `phase=verify`, `action=verify_persist`, `result=ok`
      - `referenced_objects` 에 실제 schema/table/column 목록 포함
  - no-op 억제 검증
    - 명령: host override 환경에서 `run_insight_cycle('manual-insight-noop')`
    - 결과: `duration_ms=139.64`, `scan_triggered=0`
    - 확인: 날짜 디렉토리에는 `timing_breakdown_manual-insight-test.json` 만 남았고, no-op 전용 `timing_breakdown`/`insight_worker` 추가 생성 없음
  - 보관 압축 검증
    - 샘플 디렉토리 `artifacts/shared/logs/2026-04-01/` 생성 후 `append_log_line('archive_probe', ...)`
    - 결과: `artifacts/shared/logs/archive/2026-04-01.tar.gz` 생성, 원본 `2026-04-01/` 디렉토리 제거

## TASK-0256e — 첨부 줄번호 → diff 헌크 헤더 라이브 검증 (2026-06-15)
- **배포 baked 확인**: ask-worker 컨테이너에서 `agent_core._number_file_lines('SELECT\n  AID\n  , UserID')` → `'1→SELECT\n2→  AID\n3→  , UserID'`, 지침("LINE NUMBERS & DIFFS")·헌크 포맷 grep=1.
- **라이브 LLM probe (배포 스택, claude-haiku-4 via Bedrock 게이트웨이)**: SYSTEM_PROMPT + 줄번호 첨부(7줄 SQL, 4번째 줄에 합쳐진 컬럼) + LINE NUMBERS 지침 → "4번째 줄 분리 개선안 diff" 요청. **모델 출력**: ```diff 블록 + **`@@ -4,2 +4,4 @@`**(실제 4번째 줄 기준 헌크), `→` prefix 코드 미포함(순수 SQL). 즉 모델이 첨부 파일 실제 줄번호를 추적해 헌크 헤더 작성.
- **폐루프**: 웹 buildDiffRows 가 `@@ -4` 파싱 → gutter old/new=4,5,6 표시(TASK-0256c node 검증). 줄번호 주입 → 모델 @@ → gutter 실제 줄번호 end-to-end.
- **Pass/Fail: PASS**. Residual: 실 첨부 업로드 UI e2e 는 사용자 워크플로에서 확인(deterministic+LLM probe 로 충분 검증).

## TASK-0290 — conn-tristate TCP 선검사 timeout 2000→5000ms 라이브 검증 (2026-06-16)
- Environment: 라이브 배포 스택(repo-web-1), config baked `AGENT_CONN_TCP_TIMEOUT_MS=5000`(`docker exec` 확인).
- 배포: web+ask-worker+insight-worker 3 이미지 재빌드 + `docker compose up -d`(컨테이너 교체 = **콜드 스타트 재현**, 사용자 보고 시나리오).
- **진단(수정 전, 구 2000ms)**: web 재시작 콜드 스타트(07:47Z) thundering herd 로 mysql-mv-qa-*·kr-an2-* 다수가 `via=probe-tcp err=timeout`→fails=2→**down(회색)** 오판. 직접 TCP probe 는 mv-qa 193~195ms 100% 성공(15회 0 fail) → 모니터만 down 고착. kr-an2 elapsed 2003~2237ms(2000ms 임계 초과).
- **검증(수정 후, 5000ms) — 콜드 스타트 직후 HTTP `/api/admin/datasources` conn_status**:
  - `mysql-mv-qa-auth/game/tool`: **unstable**(1744~1793ms) — 콜드 스타트 thundering herd 에도 **처음부터 unstable(빨강, "연결 불안정") 확정**. 구 2000ms 의 일시 down 오판 제거. ✓ (사용자 보고 증상 해결)
  - `mysql-kr-an2-*`(7개): **down**(elapsed 5003~5007ms = TCP 5s timeout, DB `errno=2003` 도달불가) — 진짜 죽음이라 down(회색, "연결 끊김") **정확 유지**. ✓
  - `mysql-gz-qa-kr`: healthy(147ms) — 빠른 연결 초록 정확. ✓
- **Pass/Fail: PASS**. mv-qa 빨강(불안정, ~1750ms) + kr-an2 회색(끊김, 진짜 도달불가) + gz 초록. 콜드 스타트 down 오판 제거 실증.
- 게이트: verify-completion 9/9 PASS, make test EXIT=0(회귀 0), ruff PASS.
- Residual(PB-0008): 관리 콘솔 도트 색상은 백엔드 conn_status 가 결정 — unstable→admin.js `_paintDsConnDot` `is-unstable`(빨강) 매핑(코드 기검증). 백엔드 conn_status=unstable 확정으로 도트 빨강 보장. UI 코드 변경 0(config 만)이라 Windows-browser 시각검증은 informational(CHECK#13 WARN-only).

## no-edge-conversation-answer (CHG-20260707T100640, conversation_audit FR-edge-fallback-conversation-context-loss)
- 신규 `tests/test_conversation_answer_no_edge_alias.py` **4 PASS**:
  - G1 `conversation_answer_model("claude-haiku-4") == "claude-haiku-4-chat"` (edge-free 치환).
  - G2 identity — claude-sonnet-4(애초 fallbacks 無)·edge·""·None 무회귀.
  - G3 `_call_llm` 이 litellm(create)에 보내는 `model` kwarg = `claude-haiku-4-chat`(gemma 폴백 원천 차단).
  - G4 `_record_llm_usage` 로는 **원본** `claude-haiku-4` 기록(표시/집계 정합) + sonnet 은 litellm·기록 모두 원본.
- 회귀: feature-0002 전체 스위트 회귀 0(재사용 `repo-ask-worker` 이미지 + worktree 마운트 + PYTHONPATH, DB 없이 monkeypatch). py_compile(agent_core·model_catalog)·litellm YAML lint OK.
- ⚠ **정직 기록** — feature-0003 `test_route_parity_p5b::test_route_table_matches_golden_snapshot` 는 재사용 이미지의 Starlette/FastAPI 버전이 golden 스냅샷 생성 시점과 drift 해 실패한다. **clean main(repo/) 체크아웃에서 동일 명령·동일 이미지로도 동일 실패** 확인(A/B) → 본 변경과 무관한 **환경 artifact**(내 diff 에 웹 라우터·route_snapshot 무변경). 정본 `make test`(agent 이미지 핀 deps 재빌드)에선 통과하나, worktree 에는 런타임 `.env` 부재로 compose 파싱(`invalid proto:`)이 막혀 이번 cycle 은 재사용-이미지 경로로 검증(메모리 project-pytest-worktree-pycache-gotcha 지침).
- 라이브 실측 필요분: 코드/테스트는 "대화 답변이 edge-free alias 로만 나가고 실패 시 정직 안내" 증명 → "실제 rate-limit 시 gemma 미개입" 은 배포 후 corroboration(task='agent' resolved_model gemma 분포 0 유지) 재측정.

## alembic-multihead-gate (CHG-20260710T232503, parallel-work-structure ITEM-02, 2026-07-10, session ai/claude-corp/feature-0002-agent-core)
- `bash bin/migrate-lint.sh --self-test` **10/10 PASS** (기존 destructive 6 + 신규 head 4: 선형 체인+MAX 일치→PASS / 번호 중복 0040×2→적발 / multi-head→적발 / MAX 불일치→적발).
- acceptance (c): 현행 0001~0039 체인 `--heads` **PASS** (head=`0039_enum_feedback` 단일 · revision 39건 · 번호 중복 0 · MAX_MIGRATION 일치).
- acceptance (a): worktree 에 더미 `20260710_0040_dup_x/y.py` 생성 → `--heads` **FAIL rc=1** (번호 중복 + multi-head 동시 적발, reparent 안내 출력).
- acceptance (b): `bash bin/alembic-reparent.sh 20260710_0040_dup_y.py 0041` 1회 → 파일명/revision/down_revision(→0040_dup_x)/MAX 4곳 갱신 → `--heads` **PASS 복원** 확인 후 더미 제거·MAX 원복.
- acceptance (e): tmp 브랜치 A/B 가 같은 base 에서 각자 0040 마이그레이션 추가+MAX 갱신 → `git merge` 시 `MAX_MIGRATION.txt` **CONFLICT(UU) 재현**(fail-fast 실증) → merge --abort·브랜치 폐기.
- acceptance (d): CI "Migration gate" 스텝 실행은 본 cycle PR checks 로그로 확인(머지 게이트 편입).
- guard 검증: 머지된 revision(예: 0039)에 reparent 시도 시 origin/main 존재 검사로 die — 코드 경로 확인(스크립트 guard 절).
- TEST-20260715-schema-name-case-drift: `pytest unit/feature-0002-agent-core/tests/test_schema_name_case_drift.py` (15) — 스키마명 서버-실제-case 해소(FR-schema-name-case-drift). (a) case-map: 소문자→실제case·모호(대소문자만 다른 동명 복수) 제외·conn 캐시·조회실패 빈맵 4. (b) canonicalize: 유일매칭 실제case·미발견/빈값 원본·args in-place 3. (c) **보안 불변식**: canonicalize 소문자-equivalence 보존·미허용 스키마(global_db) 게이트 여전히 거부(경계 무변) 2. (d) refresh_case: `_allow_schemas` 실제case rewrite·idempotent·MSSQL no-op 3. (e) execute_tool choke: 라우터/비라우터 canonicalize·MSSQL 라우터 no-op 3. 회귀 게이트: `test_sql_trust_boundary`·`test_mssql_security_boundary`·`test_multi_datasource`·`test_product_multi_datasource`·`test_mssql_crossdb_discovery` 재통과(보안·격리 회귀 0). 전체 feature-0002+0003 2107 passed/2 skipped.

### Run (2026-07-22) — branch-chain-race: 재답변 브랜치 체이닝 동시성 경합 수정 (Major §12.3 — feature-0002 코어 write 경로, PLAN-APPROVED) — Environment: unit + full-suite (backend, no web/UI asset → CHECK#13 skip)

- **단위(`tests/test_branch_chain_race.py`, 4 PASS)**: mock display backend 로 ① run 도중 active_leaf 가 분기점으로 리셋돼도 답변이 user(커서)에 체인(분기점 아님) ② user→step→step→답변 run 내 순차 체인 ③ 비분기(active=False) → parent None·leaf 미전진(INV-1) ④ branch_run_end 후 커서/active 해제.
- **회귀**: `py_compile` agent_core.py·memory.py·runtime_backend.py OK · **feature-0002 전체 pytest PASS**(mysql-ai-agent:current 이미지 마운트+PYTHONPATH, 2 skip·0 fail). `make test` 는 이 환경 `dc-build` 인프라 실패(`invalid proto:`)로 미실행 → 마운트 우회(메모리 gotcha 답습).
- **Pass/Fail: PASS(단위+전체 회귀)**. 백엔드 변경이라 CHECK#13(웹/UI 자산) 미해당. 사용자 체감(재답변 후 user 메시지 표시)은 POST-DEPLOY 라이브 PB-0008 로 실측 예정.
- **POST-DEPLOY(append 예정)**: deploy-all 후 라이브 재답변 → user 메시지 active-path 표시 확인 + 데이터 복구 5행 적용 후 대화 20260722015229-79da15cb active-path 에 user 복귀 확인.

- **[POST-DEPLOY 2026-07-22] branch-chain-race 배포 + 데이터 복구 실증 (PASS)**: PR #874 → main 5a32a480 → `deploy-web.sh` 전체(web-a/b 롤링 soak 90s PASS·insight/ask-worker mysql-ai-agent:5a32a480 healthy·gateway 무드리프트). `/healthz` git_commit=5a32a480. **데이터 복구**: 대화 20260722015229-79da15cb 오염 5행 트랜잭션 재링크(UPDATE 1 display[1300→1299] + UPDATE 4 core[5188→5187·5190→5189·5198→5197·5243→5242], dry-run count 일치) → 복구 후 active-path=1269→1270→1299→1300→1311→1312(사라졌던 user 1299 복귀)·양 store 오염 잔존 0·**`/api/history`(read.any) 6 메시지에 "로그 흐름만 따로 답변해주세요." 포함**(UI 렌더 데이터 경로 실검증, win-browser eval fetch). 오염 전수 탐지=이 대화 1건뿐. 코드 수정의 race 봉인 정본 검증은 단위 6 PASS(REV-20260722T050006).

### 20260727T105326-worker-attachment-postprocess 첨부 후처리 worker 이전 (Major §12.3, 2026-07-27, primary feature-0002 + cross-ref feature-0003) — **Environment: Windows-browser (첨부 생성 end-to-end 는 배포된 ask-worker + web + 실 LLM turn + MinIO 가 필요해 pre-deploy 재현 불가 — de-risk=pytest 2384 PASS(신규 12: 순서계약·defer terminal·fail-soft·cap·RBAC·web 게이팅 계약) + §18.8 2라운드 적대 패널(BLOCKER 2건 발견·수정·CLOSED) + 라이브 DB 실측으로 RC 확정, visual_verification_scope: always)**
- **자동 검증 — PASS**: pytest **2384 passed / 2 skipped / 0 failed**. 신규 `test_ask_worker_attachment_postprocess.py`(W1~W12): materialize+strip 수행·블록 없으면 조기반환·error 시 materialize skip+strip 수행·fail-soft·개수 cap 합산·account 미해소 skip·**후처리→KV done→job terminal 순서 계약**·defer 요청·후처리 예외에도 terminal 기록·마커 pop·result_json 키 보존. `test_attachment_new.py` a2: web 후처리 4곳 증거 기반 게이팅 계약.
- **라이브 RC 실측(2026-07-27, 배포본 cdee8f74)**: PG `agent_runtime.messages` msg 1389 에 `attachment-new` 블록 잔존(파서로 well-formed 확인: open L18/close L328) + MySQL `agent_memory.WebConversationAttachments` 이 대화 첨부 0건 + 전체 assistant root(v1) 첨부 0건(편집 chain 12건은 정상) + msg 1388→1389 소요 11분 → "web 동기 핸들러 미도달" RC 확정.
- **Environment: Windows-browser — PRE-COMMIT 미수행 사유**: worker 후처리는 배포된 ask-worker 프로세스에서만 발화(실 LLM turn + MinIO + MySQL 필요). 코드는 이미지 baked → merge + 전체 스코프 배포 후에만 실측 가능.
- **POST-DEPLOY 라이브 append 예정**: (a) 원 마찰 입력("전체 스크립트 개선안을 첨부파일로 전달") 재현 → 첨부 생성·다운로드 칩·본문 미노출, (b) ask-worker 로그 "첨부 후처리 완료 … new=1", (c) DB assistant root(v1) 첨부 ≥1 확인, (d) 장기 run(수 분) 후 브라우저 새로고침 시나리오에서도 첨부 생성 확인, (e) 단계 보기에 첨부 step 표시.

### 20260812T110000-llm-transient-retry-resume 대화 경로 LLM 일시 실패 재시도 + 히스토리 창 교정 (Major §12.3, 2026-08-12, primary feature-0002 + cross-ref feature-0020) — **Environment: unit + 라이브 replica 대조 (백엔드 전용, 웹/UI 자산 변경 0 → CHECK#13 미해당)**
- **자동 검증 — PASS**: `tests/test_llm_transient_retry.py` **41 passed / 1 skipped**(skip = `.env` 없는 worktree 에서 출하 타임아웃↔grace 대조 불가 — 환경 의존을 숨기지 않고 명시 skip). 축: ①실패 분류(transient/permanent/`timeout_class`) 11 ②사용자 표면(전송층 한국어 치환 · 글로벌 배너 비오염 · 역검증 confirmed 는 여전히 켬 · 401/403/429/400 버킷 비탈취) 6 ③재시도 판정(상한·backoff 단조·연결계열 무게이트·타임아웃 headroom·연장 run 무제한) 6 ④출하 상수 계약 3 ⑤패널 흡수(게이트웨이 타임아웃 3 · 느린 실패 측정 게이트 · finalize 확인 2곳+순서 · backoff 후 취소 재확인 · SDK 재시도 0 고정) 7 ⑥히스토리 창(3경로 DESC-LIMIT · 3경로 ASC 반환 · MySQL 방향 일치 · 가시성 술어 서브쿼리 내 유지) 8 ⑦배포 드리프트 경고(발화·역검증 무발화·출하 구성 대조) 3.
- **뮤테이션 12/12 KILLED**: 재시도 상한 0 · 전송층 패턴 제거 · `_TAG_PAT` 오염(배너 켜기) · 히스토리 `ORDER BY id ASC LIMIT` 복귀 · compose grace 120s 복귀 · permanent 집합을 노드분석 수준으로 완화 · headroom 게이트 제거 · SDK 재시도 knob 복귀 · finalize 확인 제거 · backoff 후 취소 확인 제거 · slow-failure 게이트 제거 · 게이트웨이 타임아웃 어휘 제거. **초판은 m9(finalize 확인 1곳 삭제)가 생존** — 확인 지점 개수·순서를 세는 테스트로 교체해 KILLED.
- **회귀**: feature-0002 전량 pytest — 실패 **선재 1건뿐**(`test_oauth_exhaustion_gate::test_write_failure_...` = 컨테이너에 `chattr` 바이너리 부재). **pristine main 대조에서 동일 실패** 확인 → 회귀 0. ruff clean. `bash -n bin/deploy-web.sh` OK. `python3 -m py_compile` 전 변경 모듈 OK. compose YAML parse OK.
- **라이브 replica 대조(읽기 전용)**: 신 히스토리 SQL 3경로를 `postgres-replica` 에서 실행 — linear 은 281행 대화에서 **구 SQL id 3369~3574 vs 신 SQL 3450~3655**(최신 81행 유실 → 해소)를 수치로 대조, windowed/branch 는 문법·NULL 파라미터 캐스팅 실행 확인.
- **Pass/Fail: PASS**(단위 + 뮤테이션 + 회귀 + 라이브 SQL 대조).
- **라이브 실측 필요분(POST-DEPLOY, append 예정)**: ① 다음 배포 창에서 in-flight 대화가 실제로 살아남는지(ask-worker 로그 `llm_transient_retry`) ② 재시도 대기 중 '중단'·'즉시 답변' 이 즉시 듣는지 ③ 진행 표시("재연결하는 중 … 조사한 내용은 그대로 유지됩니다")가 실제로 보이는지 ④ 원장 corroboration 재측정(`Connection error.`/`Request timed out.` distinct_conv 추이).

- **[POST-DEPLOY 2026-08-12] llm-transient-retry-resume 배포 + 런타임 실증 (PASS)** — PR #1217 merge
  main `65baf50b` → (병렬 세션 배포 `be6e8e1a` 로 1차 롤아웃, 이후 `7c2918a8` 로 재롤아웃).
  **5서비스 `GIT_COMMIT=7c2918a8` 전부 healthy**, edge `/healthz` `status=ok·mysql_ok·pg_ok`.
  - **배포본 ask-worker 실증**: `_llm_retry_allowed`/`_llm_retry_backoff_sec` 적재 True ·
    출하 상수 `RETRY_MAX=2 · BASE=1.5s · CAP=8.0s · SLOW_RATIO=0.5 · CANCEL_POLL=1.0s` ·
    `classify_agent_llm_failure` 적재 True.
  - **원 마찰의 예외가 실제로 분류된다**: `Connection error.` → `kind=transient ·
    timeout_class=False · 한국어 안내(“다시 시도”) · confirmed=False`(= 사용자에겐 친절 메시지,
    글로벌 provider 배너는 **켜지지 않음**). 사고 당시엔 이 예외가 분류 실패로 SDK 원문이 그대로
    노출됐다 — **그 경로가 배포본에서 닫힌 것을 직접 확인**.
  - `Request timed out.` → `transient · timeout_class=True` · 401 auth → `permanent`(재시도 안 함,
    사용자를 backoff 만큼 더 붙잡지 않음) · 504 `Gateway timeout` → `timeout_class=True`(패널 P1-1
    흡수분) · 느린 실패 게이트 `attempt_elapsed=280s, remaining=10s → False`.
  - **히스토리 창 교정 실증**: 배포본 `runtime_backend` 의 linear·windowed·branch **3경로 모두**
    `LIMIT` 을 받는 정렬이 `DESC`, 반환 정렬은 `ASC` — 최신 N행을 싣는다.
  - **아직 남은 것(정직)**: 위는 전부 "봉인이 배포본에 실려 의도대로 동작한다" 까지다.
    **"실제 사용자 대화에서 그 마찰이 사라졌는지" 는 미측정** — 다음 배포 창에서 in-flight 대화가
    살아남는지(ask-worker 로그 `llm_transient_retry`), 재시도 대기 중 '중단'·'즉시 답변' 이 즉시
    듣는지, 진행 표시가 보이는지, 그리고 원장 corroboration(`Connection error.`/`Request timed
    out.` distinct_conv 추이) 재측정이 남았다.
