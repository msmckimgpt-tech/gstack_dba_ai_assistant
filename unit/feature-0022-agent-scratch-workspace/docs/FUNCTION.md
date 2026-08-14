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
- REQ-20260721-scratch-guidance: assistant·ask-worker 가 이 자율구조를 **파악하고 적극
  사용**하도록, scratch 활성 대화에 `_SCRATCH_WORKSPACE_GUIDANCE`(agent_core 시스템 프롬프트,
  4 도구 사용법 + cross-source JOIN 트리거 신호)를 조건부 주입한다. ask-worker 도 동일
  `_run_agent_core` 경로라 양쪽 모두 지침을 받는다. 비활성 시 미주입(프롬프트 무증가).
- REQ-20260814-scratch-fork-carryover: **대화를 분기해도 작업공간이 보존된다.** 분기 3 경로
  (사본 만들기·앵커 분기·공유 링크 복제)가 원본 대화의 작업공간 테이블을 분기본 스키마로 독립
  복사한다. 교차계정·부분 구간 분기도 이월한다(사용자 결정 — 공유 링크 생성 = 소유자의 능동적
  권한 위임, 이월 건수는 감사 기록). 이월과 무관하게 **작업공간의 실제 상태(실재 테이블 목록)를
  매 턴 프롬프트에 사실로 주입**해, 문맥에만 남은 유령 테이블 참조를 차단한다(TTL 만료로 작업공간이
  사라진 대화 재개에도 동일 적용). ADR-SCRATCH-0005.

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
- **분기 이월은 독립 사본**: 분기본은 원본 스키마를 공유하지 않는다 — 이후 원본의 변경·TTL DROP 에
  영향받지 않는다. 이월은 fail-soft(실패해도 분기 자체는 성공) + 캡(테이블 수·총 행수·시간 예산)
  적용, 초과·실패는 결과에 드러낸다(조용한 절단 금지).
- **작업공간 상태는 문맥보다 우선**: 매 턴 주입되는 실재 테이블 목록이 권위 있는 사실이다. 조회
  실패 시엔 상태를 주장하지 않는다(빈 문자열) — "모름" 을 "비어 있음" 으로 오도하지 않는다.

## 8. 코드 거주 (cross-cut)
- feature-0002: `src/modules/scratch.py`(코어 + `clone_workspace` 분기 이월),
  `src/modules/tools.py`(도구 schema·handler), `src/agent_core.py`(대화 ContextVar·도구 노출 +
  `_scratch_workspace_state_note` 상태 주입), `src/modules/ask.py`(reaper 훅),
  `src/scripts/agent_scratch_schema.sql`.
- feature-0003: `src/routers/_conv_store.py`(`_fork_conversation_impl` 이월 훅 — 분기 3 경로 공통),
  `src/routers/share.py`(교차계정 fork 이월 건수 감사 기록).
- shared: `config.py`(AGENT_SCRATCH_* + active conversation ContextVar), `db.py`
  (`_pg_connect_scratch`), `runtime_settings.py`(AGENT_SCRATCH_* 스펙).
- repo-level: `bin/scratch-pg-bootstrap.sh`.
