-- feature-0022: agent PG scratch workspace — admin(registry) schema + role grants.
--
-- 본 스크립트는 bin/scratch-pg-bootstrap.sh 가 superuser 로 `agent_scratch` DB 에
-- 접속해 적용한다. 멱등 (IF NOT EXISTS / 반복 REVOKE·GRANT 안전).
--
-- 설계 근거 (feature-0022 DECISIONS ADR-SCRATCH-0001):
--   - assistant 는 `agent_scratch` DB 안에서 "완전 자율" (대화별 s_* 스키마를 만들고
--     테이블 CRUD/DDL 자유) 로 작동한다. 이 role 의 밖-도달 차단은 non-superuser + 코드의
--     dbname 고정(agent_scratch) + PG 단일세션 cross-DB 불가 + 다른 DB 무-grant 의 조합이다
--     (--harden-kb-isolation 으로 sibling DB PUBLIC CONNECT 회수 시 role 레벨까지 봉인).
--   - 대화별 스키마(s_<hash>)로 대화 간 반입 데이터 격리 (datasource 가시성/window 보존).
--     ⚠ 모든 s_* 는 이 role 이 소유 → PG 레벨 대화 격리는 없고, scratch_guard(allowlist)+
--     search_path pin 이 격리를 강제한다 (feature-0021 적대 리뷰 반영).
--   - _scratch_admin.schema_registry 로 스키마 TTL(마지막 사용 시각)을 추적 → ask-worker
--     주기 reaper 가 24h(런타임 설정) 초과 스키마를 DROP.
--
-- 신뢰경계: agent_scratch_rw 는 non-superuser · CONNECT 는 agent_scratch 에만 · public
-- 스키마 CREATE 회수 · dblink/postgres_fdw/파일 함수는 superuser 부재로 자연 실패.

-- ── 1. DB 수준 CONNECT 잠금 (신규 DB — 안전) ──────────────────────────────
-- PUBLIC 의 기본 CONNECT 를 회수하고 전용 role 에만 부여 (다른 role 이 이 낙서장을 못 봄).
REVOKE CONNECT ON DATABASE agent_scratch FROM PUBLIC;
GRANT  CONNECT ON DATABASE agent_scratch TO agent_scratch_rw;

-- 대화별 스키마를 자유로이 생성(완전 자율 DDL 의 진입점).
GRANT  CREATE  ON DATABASE agent_scratch TO agent_scratch_rw;

-- ── 2. 기본 public 스키마 봉인 (오용 방지 — 모든 작업은 s_* 대화 스키마 안에서만) ──
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL    ON SCHEMA public FROM agent_scratch_rw;

-- ── 3. 관리(레지스트리) 스키마 — TTL 추적. agent_scratch_rw 가 소유(자율 관리). ──
CREATE SCHEMA IF NOT EXISTS _scratch_admin AUTHORIZATION agent_scratch_rw;

CREATE TABLE IF NOT EXISTS _scratch_admin.schema_registry (
    schema_name     text        PRIMARY KEY,
    conversation_id text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_used_at    timestamptz NOT NULL DEFAULT now(),
    table_count     integer     NOT NULL DEFAULT 0,
    byte_estimate   bigint      NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_scratch_registry_last_used
    ON _scratch_admin.schema_registry (last_used_at);

-- superuser 가 만든 객체이므로 소유권을 rw role 로 이관 (완전 관리 권한 부여).
ALTER SCHEMA _scratch_admin           OWNER TO agent_scratch_rw;
ALTER TABLE  _scratch_admin.schema_registry OWNER TO agent_scratch_rw;
