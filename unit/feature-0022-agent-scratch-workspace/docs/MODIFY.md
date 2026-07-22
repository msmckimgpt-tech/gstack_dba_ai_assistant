---
doc_type: MODIFY
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: append
source_of_truth: true
---

# Modify — 변경 기록

## CHG-20260721-initial — 초기 구현 (cross-cut)
신규 파일:
- `bin/scratch-pg-bootstrap.sh` — agent_scratch DB/role bootstrap.
- `unit/feature-0002-agent-core/src/scripts/agent_scratch_schema.sql` — 레지스트리 스키마·권한.
- `unit/feature-0002-agent-core/src/modules/scratch.py` — 코어 모듈.
- `unit/feature-0002-agent-core/tests/test_scratch.py` — 단위 테스트 15건.

수정 파일:
- `shared/config.py` — `AGENT_SCRATCH_PG_*` env(+`__all__`) + `set/get_active_conversation_id` ContextVar.
- `shared/db.py` — `_pg_connect_scratch` / `_scratch_pg_available`(+`__all__`).
- `shared/runtime_settings.py` — `_SCRATCH_SPECS`(7종) + `list_specs()` 편입.
- `unit/feature-0002-agent-core/src/modules/tools.py` — scratch 도구 4종 schema·handler·레지스트리
  + `scratch_tool_defs`/`with_scratch_tools`.
- `unit/feature-0002-agent-core/src/agent_core.py` — 대화 ContextVar set/reset(2 finally) + scratch
  도구 노출(with_scratch_tools).
- `unit/feature-0002-agent-core/src/modules/ask.py` — reaper 훅에 `sweep_expired_schemas()`.

동작 영향: **기본 OFF** (AGENT_SCRATCH_ENABLED=0) — 병합·배포만으로 런타임 동작 불변.

## CHG-20260721-secfix — 적대적 보안 리뷰(§18.8) BLOCK/HIGH/MEDIUM 수정
- `scratch.py`: scratch_guard 를 denylist→**allowlist 반전**(허용 root 명시 + CREATE/DROP=
  TABLE/INDEX kind 한정) — CREATE FUNCTION 본문 우회(BLOCK) 봉인. 테이블명·함수명 `pg_` 접두
  차단(HIGH). dead code `_is_read_stmt` 제거. materialize pg_ 접두 테이블명 회피.
- `tools.py`: scratch_import 에 execute_sql parity heavy-query 게이트 + `confirm_heavy` 인자.
- `bin/scratch-pg-bootstrap.sh`: `--harden-kb-isolation` 을 sibling DB(agent_runtime/
  agent_memory/web) 로 확대(opt-in).
- 문서(scratch.py·schema.sql·FUNCTION·DECISIONS): CONNECT 격리 근거를 실제 메커니즘으로 정정 +
  단일-role 잔여 위험·후속(대화별 role) 명시.
- `test_scratch.py`: 하드닝 guard 회귀 5건 추가(총 20건).

## CHG-20260721-guidance — 사용 지침 주입 + bootstrap superuser 결함 수정 (follow-up)
- `agent_core.py`: `_SCRATCH_WORKSPACE_GUIDANCE` 상수 + scratch 활성 시 조건부 주입(mermaid 지침 뒤).
  assistant·ask-worker(동일 `_run_agent_core` 경로)가 cross-source JOIN 시 scratch 를 적극 사용하도록 유도.
- `bin/scratch-pg-bootstrap.sh`: superuser 를 `AGENT_KB_PG_USER`(운영=non-superuser agent_kb_rw) 대신
  전용 `AGENT_SCRATCH_PG_SUPERUSER`(기본 `postgres`)로 + unix 소켓 trust/peer 연결(`-h localhost` 제거)
  → 운영 환경 `createdb permission denied` 해소. 헤더/격리 근거 주석 정확화.
- `test_scratch.py`: guidance 상수 sanity 테스트 1건 추가(총 21건).

## CHG-20260721-runsql-fix — run_sql SET statement_timeout 파라미터화 버그 수정 (라이브 스모크 적발)
- `scratch.py`: `run_sql` 의 `SET statement_timeout = %s`(psycopg 파라미터) 는 PostgreSQL 이
  SET 값 바인딩을 불허해 **모든 scratch_sql 이 "syntax error at $1" 로 실패**하던 버그를 수정.
  `_statement_timeout_sql()` 헬퍼로 int 인라인(주입 불가). 라이브 end-to-end 스모크(반입→JOIN)가
  적발 — 유닛테스트는 PG 없이 guard 만 검증해 놓친 경로.
- `test_scratch.py`: `_statement_timeout_sql` placeholder-free 회귀 테스트 추가(총 22건).

## CHG-20260722-scratchsql-table — scratch_sql 결과셋 출력을 표 형식으로 통일 (사용자 피드백)
- `tools.py`: `_tool_scratch_sql` 이 결과셋을 plain-text(` | ` 나열) 대신 **execute_sql 과 동일한
  `_format_result_sets`**(Markdown 표: `| col |` + 구분선 + 행수 footer)로 출력하도록 변경. 죽은
  `_fmt_scratch_rows` 제거. 미리보기 캡·절단 안내는 execute_sql 파라미터(_TOOL_PREVIEW_*)와 동일.
- `test_scratch.py`: scratch_sql 출력이 Markdown 표(헤더·구분선·데이터행)인지 회귀 테스트 추가(총 23건).
