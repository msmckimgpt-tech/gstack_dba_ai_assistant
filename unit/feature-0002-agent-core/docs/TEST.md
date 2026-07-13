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
