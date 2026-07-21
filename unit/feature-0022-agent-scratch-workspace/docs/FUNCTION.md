---
doc_type: FUNCTION
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
서비스 내 assistant 가 더 나은 답변을 위해 **PostgreSQL 안에 자기 전용 낙서장 DB
(`agent_scratch`)를 자율적으로 다루는** 기능. assistant 는 대화별로 격리된 작업공간에서
테이블을 자유로이 만들고(완전 자율 DDL/DML), 여러 외부 데이터소스·DB 의 데이터를 이 PG
테이블로 **반입(materialize)** 한 뒤 PG 안에서 **cross-source JOIN** 을 수행한다. 작업공간
데이터는 임시이며 **설정된 삭제 주기(기본 24시간)** 마다 자동으로 비워진다. cross-cut —
코드 거주: feature-0002 (agent 코어·도구·워커 reaper·scratch 모듈·bootstrap), shared
(config·db 연결·runtime_settings).

## 2. Goal
- REQ-20260721-scratch-autonomy: assistant 가 PG 전용 DB `agent_scratch` 안에서 자기
  전용 테이블/스키마를 **자율적으로 CREATE·DROP·CRUD** 할 수 있다("완전 자율"). 이 자율성은
  전용 role `agent_scratch_rw` 로 실현되며, 해당 role 은 `agent_scratch` DB 안에서만 작동하고
  KB(`agent_kb`)·runtime·web·외부 datasource 에는 **물리적으로 도달 불가**하다(PG
  database-level 격리 + 무-grant, ADR-SCRATCH-0001).
- REQ-20260721-scratch-import-join: 다른 데이터소스·DB 에서 참조하는 데이터를 해당 PG
  테이블 내부로 **반입**한 뒤 별도의 **JOIN** 작업을 수행할 수 있다. 반입(`scratch_import`)은
  `execute_sql` 과 **동일한** 신뢰경계(sql_guard 단일 SELECT/CTE + 제품 allowlist·cross-DB
  게이트)를 통과한 데이터만 대상 — 새 데이터 유출 표면 0. JOIN 등 조작은 `scratch_sql` 로
  작업공간 안에서 수행한다.
- REQ-20260721-scratch-ttl: 작성된 데이터는 **설정된 임시데이터 삭제 주기**에 따라 비워진다.
  대화별 스키마의 last_used_at 기준으로 ask-worker 주기 reaper 가 TTL(런타임 설정
  `AGENT_SCRATCH_TTL_HOURS`, 기본 24h) 초과 스키마를 `DROP SCHEMA CASCADE` 한다.
- REQ-20260721-scratch-isolation: 반입/생성 데이터는 **대화별 스키마**(`s_<hash>`)로 격리돼,
  대화 A 가 대화 B 의 데이터를 볼 수 없다(datasource 가시성/공유 window RBAC 격리를
  materialization 후에도 보존).

## 3. In Scope
- 전용 PG DB(`agent_scratch`) + 전용 login role(`agent_scratch_rw`) bootstrap
  (`bin/scratch-pg-bootstrap.sh` + `agent_scratch_schema.sql`).
- 대화별 스키마 lifecycle(생성·last_used 갱신·전역 캡·reset) + `_scratch_admin.schema_registry`.
- assistant 도구 4종: `scratch_import`(governed read→materialize), `scratch_sql`(작업공간
  한정 자율 SQL — DDL/DML/JOIN), `scratch_list`, `scratch_reset`.
- scratch guard(역-태세: DDL/DML 허용, 대화 스키마 밖 참조·위험 구문·위험 함수 차단).
- TTL reaper(ask-worker 주기) + 런타임 설정 `AGENT_SCRATCH_*`(enabled·TTL·캡·timeout·preview).
- 반입 타입 추론(bigint/double/boolean/timestamptz/text) + 행수·테이블·스키마 캡.

## 4. Out of Scope
- 관리 콘솔 UI 관측(작업공간 현황 admin 화면) — 후속(deferred).
- 라이브 배포 + PB-0008 시각검증 — 본 기능은 백엔드/무-UI 이나, 활성화(bootstrap+enable)는
  운영자 결정 사항으로 별도 진행.
- scratch 데이터에 대한 임베딩/RAG 색인 — 범위 밖(임시 데이터).
- cross-DB 물리 federation(postgres_fdw/dblink) — 채택 안 함(반입→PG 내 JOIN 방식).

## 5. Inputs
- `scratch_import(sql, dest_table[, datasource])`: 반입 SELECT + 대상 테이블명(+멀티ds 시 소스).
- `scratch_sql(sql)`: 작업공간에서 실행할 단일 SQL.
- 활성 대화 id: `cfg.get_active_conversation_id()`(agent_core 가 run 시작 시 set).
- 런타임 설정: `AGENT_SCRATCH_ENABLED`(기본 0=OFF) 외 TTL/캡/timeout.
- 인프라: `.env` 의 `AGENT_SCRATCH_PG_*`(host/port 는 KB PG fallback) + psycopg.

## 6. Outputs
- `agent_scratch` DB 안 대화별 스키마 `s_<sha1[:24]>` 와 그 안의 반입/파생 테이블.
- 도구 결과 텍스트(반입 요약·쿼리 미리보기·목록·리셋 확인).
- `_scratch_admin.schema_registry` 의 TTL 추적 행.

## 7. Behavior / Invariants
- **기본 OFF**: `AGENT_SCRATCH_ENABLED` 기본 0 → 병합·배포만으로 런타임 동작 불변(도구 미노출).
  bootstrap(DB/role) + 런타임 enable + `.env` 자격이 모두 갖춰져야 활성.
- **완전 자율 within sandbox / zero outside**: `agent_scratch_rw` 는 `agent_scratch` 안에서
  자율. 밖-도달 차단 = non-superuser + 코드 dbname 고정 + PG 단일세션 cross-DB 불가 + 무-grant
  (선택: `--harden-kb-isolation` 로 sibling DB PUBLIC CONNECT 회수).
- **governed 반입**: 반입은 "이미 SELECT 가능하던 데이터"만(execute_sql 과 동일 게이트 + heavy-query 게이트).
- **대화 격리**: 스키마 per-conversation + search_path pin + **scratch guard(allowlist)**. ⚠ 모든
  s_* 는 동일 role 소유라 PG 레벨 격리는 없음 — guard 가 cross-schema·pg_catalog·함수생성을 차단해
  격리를 강제(feature-0021 적대 리뷰 BLOCK 대응). 향후 대화별 전용 role 승격 여지.
- **TTL 자동 삭제**: last_used 기준 TTL 초과 스키마 DROP(런타임 조정 가능).
- **폭주 방지 캡**: 반입 행수·대화당 테이블 수·전역 스키마 수·문당 timeout 캡.

## 8. 코드 거주 (cross-cut)
- feature-0002: `src/modules/scratch.py`(코어), `src/modules/tools.py`(도구 schema·handler),
  `src/agent_core.py`(대화 ContextVar·도구 노출), `src/modules/ask.py`(reaper 훅),
  `src/scripts/agent_scratch_schema.sql`.
- shared: `config.py`(AGENT_SCRATCH_* + active conversation ContextVar), `db.py`
  (`_pg_connect_scratch`), `runtime_settings.py`(AGENT_SCRATCH_* 스펙).
- repo-level: `bin/scratch-pg-bootstrap.sh`.
