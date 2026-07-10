# MIGRATIONS — KB Postgres(`agent_kb`) Alembic 도입 (TASK-0143, #15)

## 배경

지금까지 KB Postgres(`agent_kb`) 스키마는 startup 부작용 raw DDL 로만 적용돼 왔다:

- 정본: `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql`
  (`CREATE TABLE IF NOT EXISTS …`, `CREATE INDEX IF NOT EXISTS …`, `ALTER … SET`,
  trigger/grant DO 블록).
- 적용 경로: `modules/memory.py` 의 `_ensure_pg_schema()` 가 boot 시 idempotent 적용.

이 방식은 버전드·가역 이력이 없다. 어떤 변경이 언제 들어갔는지, 특정 환경이 어느
스키마 버전인지 추적할 수 없고, 롤백 절차도 없다. **TASK-0143** 은 alembic 을
**additive**(신규 파일만 추가, 기존 스키마/코드 불변)로 도입해 "이제부터 신규
스키마 변경은 versioned migration 으로" 의 토대를 만든다.

- 1차 대상: **Postgres `agent_kb`** (런타임/KB 스키마가 PG).
- MySQL `agent_memory` 는 본 baseline 범위 **제외** — 후속 단계 검토(아래 "후속").

## 구성

```
unit/feature-0002-agent-core/
  alembic.ini                  # script_location 만 지정. sqlalchemy.url 은 두지 않음(자격증명 commit 금지).
  alembic/
    env.py                     # .env 의 AGENT_KB_PG_* 에서 URL 조립. offline(--sql) + online 둘 다.
    script.py.mako             # 신규 revision 템플릿
    versions/
      20260602_0001_baseline_agent_kb_schema.py   # baseline — 라이브 스키마 전체 재현(TASK-0149)
```

### env.py 의 URL 조립

`sqlalchemy.url` 은 `alembic.ini` 에 **두지 않는다**(자격증명 commit 금지). `env.py`
가 런타임에 `.env` 의 환경변수에서 조립하며, 이는 `modules/db.py` 의
`_pg_connect()` 와 **동일한 키**를 재사용한다(단일 정본):

- `AGENT_KB_PG_HOST` / `AGENT_KB_PG_PORT` / `AGENT_KB_PG_DB`
- `AGENT_KB_PG_USER` / `AGENT_KB_PG_PASSWORD` / `AGENT_KB_PG_SSLMODE`

드라이버는 psycopg v3 (`postgresql+psycopg://`) — 라이브 코드와 통일.
환경변수가 비어 있어도(검증/CI 컨테이너) placeholder 로 fallback 해
`alembic upgrade head --sql` 오프라인 렌더가 DB 연결 없이 동작한다.

## baseline 은 full-schema revision (TASK-0149)

> **변경(TASK-0149):** baseline 은 더 이상 빈(no-op) revision 이 아니다. 이제 라이브
> `agent_kb` 스키마 **전체를 재현**한다(2026-06-04 read-only `pg_dump --schema-only`
> 실측 기준). 따라서 fresh deploy 는 `alembic upgrade head` 하나만으로 빈 DB 에 KB
> 스키마 전체를 세울 수 있고, **alembic 이 스키마 source-of-truth** 가 된다.

`versions/20260602_0001_baseline_agent_kb_schema.py` 의 `upgrade()` 가 재현하는 객체:

- **확장 3**: `vector`(pgvector 0.8.2), `pg_trgm`, `pg_stat_statements` (모두 `public`).
- **스키마**: `agent_runtime` (+ 기본 `public`).
- **함수**: `public.set_updated_at()` (updated_at 자동 갱신 트리거 함수).
- **테이블 12**: `agent_runtime`(core_conversations, core_messages, kv, llm_usage,
  messages, steps, summary) + `public`(fact_entries, kb_invalidations, rag_documents,
  rag_objects, texts). PK/UNIQUE/FK 제약 인라인. fact_entries 의 autovacuum
  storage params 포함.
- **뷰 1**: `public.kb_slow_queries` (pg_stat_statements 기반 — 확장 생성 이후 정의).
- **인덱스**: btree 다수 + pg_trgm GIN(`ix_texts_content_trgm`,
  `ix_rag_objects_join_hints_gin`) + **pgvector HNSW**(`ix_texts_embedding_hnsw`,
  `USING hnsw (embedding vector_cosine_ops)`).
- **트리거 6**: 각 updated_at 테이블의 `BEFORE UPDATE` 트리거.

### 멱등(idempotent) 정규화

pgvector/HNSW/GIN 은 alembic `op.create_table`/`op.create_index` 로 정밀 표현이
어렵고 손실 위험이 있어 **raw SQL `op.execute(...)`** 로 라이브 실측 그대로 재현한다.
재실행 안전을 위해:

- 확장/스키마/테이블/인덱스 → `... IF NOT EXISTS`.
- PK/UNIQUE/FK → pg_dump 의 별도 `ALTER TABLE ADD CONSTRAINT`(비멱등) 대신
  `CREATE TABLE IF NOT EXISTS` 본문에 **인라인**.
- 함수/뷰 → `CREATE OR REPLACE`.
- 트리거 → PG14+ `CREATE OR REPLACE TRIGGER` (라이브 PG16).

이로써 **부트스트랩 DDL(`_ensure_pg_schema()`)과 공존**해도 충돌 없이 재적용 가능하다
(belt-and-suspenders).

### 인증 모델 — 왜 online alembic 을 app 유저로 못 돌리나 (TASK-0149 실측)

본 배포는 **privileged DDL 경로가 postgres 컨테이너의 로컬 trust 소켓 전용**이다:
- `postgres` superuser(스키마 owner) 는 컨테이너 로컬 소켓/127.0.0.1 trust 로만 접근
  가능하고, agent 컨테이너에서 **TCP scram 인증은 실패**한다(비밀번호 미공유).
- `agent_kb_rw`(앱 유저, env_file 로 주입)는 least-privilege 라 `public`/`agent_runtime`
  스키마에 **CREATE 권한이 없다**. 따라서 online alembic 을 agent_kb_rw 로 돌리면
  `alembic_version` 생성 단계에서 `permission denied for schema public` 으로 실패한다.

그래서 마이그레이션 적용은 **`bin/alembic-migrate.sh`** 가 담당한다: agent 컨테이너에서
alembic **offline `--sql`** 로 SQL 만 생성 → 그 SQL 을 `docker exec -i …-postgres-1
psql -U postgres`(로컬 소켓 superuser)로 적용한다. **DB 인증/비밀번호 변경 0.**

### 운영 절차 — 라이브 기존 DB (스키마 변경 0)

```
make migrate-current      # 라이브 현재 revision 조회
make migrate-stamp        # 기존 스키마를 head baseline 으로 마킹 (멱등, DDL 0)
```

라이브는 스키마가 **이미 존재**하므로 baseline upgrade 를 실행하면 안 된다. `stamp`
는 `alembic_version` 테이블만 생성/마킹하고 **DDL 한 줄도 실행하지 않는다**.
(TASK-0149 에서 라이브 `agent_kb` 는 `0001_baseline` 로 stamp 완료.)

### 운영 절차 — fresh deploy (빈 DB) / 신규 revision 적용

```
make migrate              # current:head 의 pending 마이그레이션만 적용 (current==head 면 no-op)
```

빈 DB 면 baseline 전체(확장/스키마/함수/테이블/뷰/인덱스/트리거/FK)를 구축하고, 기존
DB 면 `live current → head` 의 신규 revision DDL 만 생성·적용한다. 적용은 위 로컬 소켓
superuser 경로를 거친다(헬퍼가 자동 처리).

### 검증(라이브 무영향, scratch DB)

라이브 `agent_kb` 는 절대 건드리지 않는다. 임시 DB(`alembic_verify`)를 만들어
`alembic upgrade head` 후 라이브와 information_schema/pg_indexes 를 비교한다(차이 0).
TASK-0149 검증에서 컬럼/인덱스/테이블/뷰/트리거/FK 모두 라이브와 일치를 확인했고
(유일한 차이는 alembic 자체 `alembic_version` 테이블), downgrade→re-upgrade 사이클도
무오류였다.

## 신규 스키마 변경 워크플로

1. 새 revision 생성:
   ```
   make migrate-new name="add_foo_index"          # 빈 revision (수기 작성)
   make migrate-new name="add_foo_index" auto=1    # autogenerate (metadata 도입 후)
   ```
   → `alembic/versions/` 에 새 파일. `upgrade()`/`downgrade()` 를 작성하고 리뷰.
2. 적용:
   ```
   make migrate        # = alembic upgrade head
   ```

> autogenerate(`auto=1`)는 현재 `target_metadata = None` 이라 diff 를 생성하지
> 않는다(빈 revision 과 동일). ORM/Core metadata 를 도입하는 후속 단계에서 의미를
> 갖는다. 지금은 수기 `op.execute(...)`/`op.create_*` 작성이 기본.

## 부트스트랩 DDL 과의 공존 (idempotent backstop)

본 도입은 additive 다. 기존 startup 부트스트랩 DDL(`_ensure_pg_schema()` +
`agent_kb_schema.sql`)은 **그대로 유지**되며 alembic 과 공존한다(belt-and-suspenders).
baseline 이 이제 full-schema 라 두 경로가 같은 객체를 만들 수 있지만, 둘 다
`IF NOT EXISTS`/`CREATE OR REPLACE` 기반 idempotent 라 어느 쪽이 먼저 돌아도 안전하다.
부트스트랩 **완전 제거는 후속 위험 단계**로 미룬다(이번 범위 밖).

## 병렬 브랜치 번호 경합 게이트 (parallel-work-structure ITEM-02, 2026-07-10)

병렬 worktree 브랜치들이 같은 "다음 번호"(예: 0040)로 마이그레이션을 만들면 머지 후에야
multi-head 로 발각되던 문제(0036 실충돌 — `6263e641` 수동 re-parent)를 3중 장치로 막는다:

1. **정적 head 검사** — `bin/migrate-lint.sh --heads`: versions/*.py 의
   `revision`/`down_revision` 그래프를 AST 파싱해 (a) head 2개 이상 (b) 파일명 4자리
   번호 중복 (c) `MAX_MIGRATION.txt` ↔ 실제 head 불일치를 exit 1 로 적발. 라이브 DB
   불필요(폐쇄망 CI 안전). 기본 diff/`--all` 모드에서도 항상 함께 실행된다.
2. **CI 머지 게이트** — `.github/workflows/ci.yml` `test` job 의 "Migration gate" 스텝이
   PR 마다 `--self-test` + `--heads` 실행.
3. **의도적 충돌 파일** — `versions/MAX_MIGRATION.txt` 에 최신 head revision id 를 1줄
   기록(django-linear-migrations 의 `max_migration.txt` 패턴). **신규 마이그레이션 작성
   시 이 파일도 함께 갱신**해야 한다(lint (c) 가 강제). 병렬 두 브랜치가 각자 head 를
   만들면 git 머지 시점에 이 파일에서 반드시 텍스트 충돌 → CI 도달 전 fail-fast.

**경합 해소**: 나중에 머지되는 브랜치에서
`bin/alembic-reparent.sh <versions/파일.py> <새번호>` 1회 — 파일명 번호·`revision`·
`down_revision`(현 head 로) 3곳 원자 치환 + MAX_MIGRATION.txt 갱신 + lint 재실행.
**guard**: 아직 origin/main 에 머지되지 않은 자기 브랜치 파일만 대상(스크립트가 강제) —
머지된 revision 재번호는 라이브 `alembic_version` stamp 를 파손하므로 금지.

## 후속 작업 (이번 범위 밖)

- **부트스트랩 DDL 이관**: `_ensure_pg_schema()`/`agent_kb_schema.sql` 의 CREATE/ALTER
  를 점진적으로 versioned migration 으로 옮기고, 이관 완료분은 부트스트랩에서 제거.
  (제거는 위험 — 별도 단계.)
- **MySQL `agent_memory`**: 별도 alembic 환경 또는 동일 환경의 second config 로 도입
  검토. 본 baseline 범위 제외.
- **texts embedding 인덱스 drift (ivfflat vs hnsw) — baseline 에서 해소(TASK-0149)**:
  `agent_kb_schema.sql` 은 `ix_texts_embedding_ivfflat` 를 `ivfflat (...) WITH
  (lists = 32)` 로 정의했고 헤더 주석은 `lists=100` 이라 파일 내부부터 불일치였다.
  더 큰 drift 는 **라이브 `agent_kb`** 의 texts 에 ivfflat 인덱스가 없고
  `ix_texts_embedding_hnsw`(`USING hnsw (embedding vector_cosine_ops)`)만 존재한다는
  점이었다. **TASK-0149 baseline 은 라이브 실측(HNSW)을 정본으로 재현**하여 alembic
  쪽 drift 는 해소했다(scratch DB 검증에서 HNSW 인덱스 재현·일치 확인). 남은 정리:
  `agent_kb_schema.sql` 자체의 ivfflat 정의를 HNSW 로 갱신(부트스트랩 정합) — 부트스트랩
  DDL 제거/정렬 후속 단계에서 함께 처리.
