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
      20260602_0001_baseline_agent_kb_schema.py   # baseline — 빈(no-op) upgrade/downgrade
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

## baseline 은 빈(empty) revision — stamp 전제

`versions/20260602_0001_baseline_agent_kb_schema.py` 의 `upgrade()`/`downgrade()`
는 의도적으로 **비어 있다(no-op)**. 라이브 `agent_kb` 스키마는 이미 부트스트랩
DDL 로 존재하므로, baseline 은 그것을 **다시 만들지 않고** "현행 상태가 alembic 의
시작점" 임을 표시할 뿐이다.

### 라이브 기존 DB 운영 절차 (스키마 변경 0)

```
make migrate-stamp        # = alembic stamp head
```

→ `alembic_version` 테이블만 생성하고 baseline revision 으로 마킹. **DDL 한 줄도
실행하지 않는다.** 라이브 스키마는 그대로다.

### 검증(라이브 무영향)

```
alembic upgrade head --sql    # 빈 baseline → BEGIN/COMMIT + alembic_version INSERT 만 렌더
```

online upgrade 는 baseline 에선 no-op 이지만, 운영 표준은 어디까지나
`make migrate-stamp` 다.

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

## 부트스트랩 DDL 과의 공존

본 도입은 additive 다. 기존 startup 부트스트랩 DDL(`_ensure_pg_schema()` +
`agent_kb_schema.sql`)은 **그대로 유지**되며 alembic 과 당분간 공존한다. 신규 변경만
versioned migration 으로 들어가고, 기존 DDL 의 alembic 이관은 위험을 분리하기 위해
후속 단계로 미룬다.

## 후속 작업 (이번 범위 밖)

- **부트스트랩 DDL 이관**: `_ensure_pg_schema()`/`agent_kb_schema.sql` 의 CREATE/ALTER
  를 점진적으로 versioned migration 으로 옮기고, 이관 완료분은 부트스트랩에서 제거.
  (제거는 위험 — 별도 단계.)
- **MySQL `agent_memory`**: 별도 alembic 환경 또는 동일 환경의 second config 로 도입
  검토. 본 baseline 범위 제외.
- **texts embedding 인덱스 drift (ivfflat → hnsw)**: `agent_kb_schema.sql` 은
  `ix_texts_embedding_ivfflat` 를 `ivfflat (... ) WITH (lists = 32)` 로 정의하고
  (line 82), 파일 헤더 주석은 `lists=100`(line 38)이라 **파일 내부부터 불일치**다.
  더 큰 drift: **라이브 `agent_kb`** 의 texts 테이블에는 ivfflat 인덱스가 아예 없고
  `ix_texts_embedding_hnsw`(`USING hnsw (embedding vector_cosine_ops)`)만 존재한다
  (2026-06-02 read-only 조회 확인). 즉 라이브는 이미 HNSW 로 전환됐는데 스키마
  파일은 ivfflat 정의를 유지 중. 정본(HNSW 파라미터 포함)을 확정한 뒤 명시적
  migration 으로 정렬하고 schema.sql 을 갱신 — 후속으로 기록.
