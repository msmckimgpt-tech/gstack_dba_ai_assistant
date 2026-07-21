---
doc_type: DECISIONS
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: append
source_of_truth: true
---

# Decisions

## ADR-SCRATCH-0001 — 전용 DB `agent_scratch` + 전용 role 로 "완전 자율"을 격리 (2026-07-21)
- **결정**: assistant 의 PG 자율 작업공간을 기존 `agent_kb` 안 스키마가 아니라 **별도 database
  `agent_scratch` + 전용 login role `agent_scratch_rw`** 로 둔다.
- **근거**: 사용자가 "이 구조에 대한 접근 권한은 완전 자율"을 명시. 완전 자율 DDL/DML 을 안전하게
  담으려면 PG 의 **database-level 격리**가 가장 강한 경계다. 별 DB + CONNECT 를 그 DB 로만 부여 +
  다른 DB 에 무-grant → role grant 누출·search_path 사고에도 KB/runtime/web 에 도달 불가.
  ADR-0021/0024(KB 분리·별 DB) 패턴과 정합.
- **role 속성**: NOSUPERUSER·NOCREATEDB·NOCREATEROLE·NOREPLICATION·NOBYPASSRLS. `agent_scratch`
  안에서는 스키마/테이블 CREATE·DROP·CRUD 자유(완전 자율). `dblink`/`postgres_fdw`/파일 함수는
  superuser 부재로 자연 실패 + scratch guard 가 앱-레이어에서도 차단(defense-in-depth).
- **결과**: `agent_scratch` 는 alembic(agent_kb 대상) 밖 → 전용 `bin/scratch-pg-bootstrap.sh` 로 관리.

## ADR-SCRATCH-0002 — 대화별 스키마 격리 (2026-07-21)
- **결정**: 반입/생성 데이터는 대화별 스키마 `s_<sha1(conversation_id)[:24]>` 아래 둔다.
- **근거**: 반입은 datasource 의 read-only 게이트(allowlist·DB-단위·공유 [from,to] window RBAC)를
  통과한 데이터를 PG 로 옮긴다. 전역 공유 작업공간이면 대화 A 가 볼 수 없어야 할 데이터를 대화 B 가
  같은 테이블에서 읽어 **가시성 격리가 깨진다**. 대화별 스키마 + search_path pin + scratch guard 의
  cross-schema 차단으로 격리를 materialization 후에도 보존.
- **대안**: 전역 공유(단순하나 다중 사용자·공유 대화에서 누출) — 기각.
- **잔여 위험(적대 리뷰 반영, accepted with mitigation)**: 모든 `s_*` 스키마는 동일 role
  `agent_scratch_rw` 가 소유 → **PG 레벨 대화 격리는 없음**. 격리는 `scratch_guard`(allowlist)
  + search_path pin 이 강제한다. 초기 구현의 denylist guard 는 (a) `CREATE FUNCTION` 문자열
  본문에 cross-schema 참조 은닉 (b) `pg_catalog` 무자격 참조로 타 대화 메타데이터 열거 두 우회가
  발견돼(feature-0021 적대 리뷰 BLOCK/HIGH), guard 를 **allowlist 로 반전**(허용 root 명시 +
  CREATE/DROP 은 TABLE/INDEX kind 만 + 테이블명 `pg_` 접두·함수 `pg_` 접두 차단)해 봉인했다.
- **후속(권장)**: 대화별 전용 PG role + `s_*` 스키마 USAGE 를 그 role 에만 부여해 **PG 레벨**
  대화 격리로 승격(소프트웨어 guard 에 격리를 의존하지 않도록). TASK-0013 로 이월.

## ADR-SCRATCH-0003 — governed 반입(execute_sql 신뢰경계 재사용) (2026-07-21)
- **결정**: `scratch_import` 는 새 데이터 접근 경로를 만들지 않는다. 반입 SELECT 는 `execute_sql`
  과 **동일한** sql_guard(단일 SELECT/CTE·금지스키마·금지함수) + `_freeform_sql_access_error`
  (제품 allowlist·무자격·cross-DB) 게이트를 통과한 뒤에만 실행·적재된다.
- **근거**: "이미 SELECT 가능하던 데이터"만 반입 가능 → 데이터 유출 표면 증가 0. 반입 데이터는
  기존 execute_sql 결과와 동일하게 untrusted(프롬프트 인젝션 datamarking 계층 적용).

## ADR-SCRATCH-0004 — 시간기반 TTL reaper(기본 24h·기본 OFF 활성 게이트) (2026-07-21)
- **결정**: 삭제 주기는 `_scratch_admin.schema_registry.last_used_at` 기준 시간 TTL(런타임
  `AGENT_SCRATCH_TTL_HOURS`, 기본 24h)로, ask-worker 주기 reaper 가 `DROP SCHEMA CASCADE`.
  기능 자체는 `AGENT_SCRATCH_ENABLED` 기본 0(OFF) — bootstrap+enable 전엔 도구 미노출.
- **근거**: 사용자가 "설정된 임시데이터 삭제 주기에 따라 비워지도록"을 명시 → 런타임 조정 가능한
  TTL. feature-0021 agent-notes TTL reaper 선례 재사용(동일 ask-worker 훅). 기본 OFF 는 Critical
  쓰기 경로가 병합·배포만으로 활성화되지 않도록 하는 안전 기본값(feature-0010 scaffold 패턴).
- **대안**: 대화 종료 감지 시 즉시 삭제(감지 로직 추가 필요·idle 정의 모호) — 시간 TTL 우선, 필요 시
  후속으로 종료-트리거 추가.
