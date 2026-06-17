---
doc_type: DESIGN
feature_id: feature-0002-agent-core
scope: feature
status: proposed
edit_policy: rewrite
source_of_truth: false
title: DESIGN — 멀티 datasource (MySQL · MSSQL) 데이터평면
---

# DESIGN — 멀티 datasource (MySQL · MSSQL) 데이터평면

> **상태: 설계만 (proposed). 구현 안 됨.** 본 문서는 "assistant·insight_worker 가 단일
> MySQL 만 바라보는 현재 구조"를 **여러 datasource(엔진: MySQL·MSSQL) 동시 운용**으로
> 확장하는 구조적 설계다. 위험 등급 **Critical** (§12.3 — 데이터 접근 경계·자격증명·RBAC·
> SQL injection guard 를 모두 건드림). 구현은 자체 다중 cycle + `/plan-eng-review` +
> **RBAC outside-voice 리뷰**(Codex/subagent, [[feedback_outside_voice_for_rbac]]) 통과 후
> 단계 착수. 결정 근거는 [DECISIONS.md](DECISIONS.md) ADR-CORE-0002.

## 1. 문제 / 목표

현재 assistant(`execute_sql` 도구)와 insight_worker 는 **단일 MySQL** 만 분석한다. 이유는
"단일 MySQL" 가정이 세 계층에 하드코딩돼 있기 때문이다 (코드 근거 §2).

**목표**: 사용자가 **N 개의 데이터소스**(각각 MySQL 또는 MSSQL)를 등록하고, 대화/질의별로
어느 datasource 를 분석할지 선택할 수 있게 한다. assistant 의 SQL 실행·스키마 탐색·부하
게이트·CSV 미리보기와 insight_worker 의 인사이트 생성이 모두 **선택된 datasource 의 엔진
방언으로** 동작한다.

**비목표 (Out of scope)**:
- 크로스엔진 페더레이션 (단일 쿼리가 MySQL·MSSQL 을 JOIN) — 별도 페더레이션 엔진 필요, 본 설계 제외.
- 제어평면 store **엔진** 자체의 멀티엔진화 — 제어평면 store(agent_memory MySQL→PG, KB pgvector)는
  기존 엔진 유지. **단 "제어평면 untouched" 는 정확하지 않다 (Codex-8)**: 본 설계는 제어평면에 신규
  **스키마/데이터**(datasources 레지스트리, 대화↔datasource 바인딩 컬럼, datasource 접근권한 RBAC,
  시크릿 lifecycle)를 추가한다. 따라서 **마이그레이션 소유권·rollback·기존 대화 datasource_id 백필
  실패 정책**이 설계 필수 항목이다(§10 Codex-8). 데이터평면만 멀티엔진화한다는 것은 *분석 SQL 실행 경로*
  한정 — 제어평면 *변경 없음* 이 아니다.
- MySQL·MSSQL 외 엔진(PostgreSQL as target, SQLite, Oracle 등) — Dialect 인터페이스가 확장
  가능하도록 설계하되 본 cycle 범위는 MySQL·MSSQL 2종.

**유리한 전제 (이미 충족)**:
- **제어/데이터 평면 seam 이 이미 존재**한다 — [db.py](../src/modules/db.py) `connect()` 의
  `db_str != str(MEMORY_DB)` 분기(L118·L123)가 "memory(제어) vs data-plane(분석)" 라우팅을
  이미 가른다. 멀티엔진은 이 data-plane 분기만 확장하면 된다.
- **SQL guard 가 sqlglot AST 기반**이다 — [sql_guard.py](../src/modules/sql_guard.py) 는
  denylist regex 가 아니라 sqlglot 파싱 + AST shape allowlist(single SELECT/CTE). sqlglot 은
  멀티방언(`mysql`/`tsql`) 파싱을 지원하므로 dialect 인자 주입이 **출발점**은 된다. **단, 이것만으로는
  멀티엔진 가드가 완성되지 않는다** (REV-20260610-0182 B-1·B-3 — 아래 §3.4·§4 가 정본):
  진짜 테넌트 격리는 sql_guard 가 아니라 [tools.py](../src/modules/tools.py) 의 **정규식 기반**
  `_whitelist_violation(_extract_sql_schema_refs(...))` 와 **DB 계정 RO GRANT** 두 축이 담당하며,
  둘 다 MSSQL 에서 그대로는 깨진다. dialect 주입은 필요조건이지 충분조건이 아니다.
- **커넥션 풀 키가 이미 시그니처 기반**이다 — `_pool_key()`(L51) 가 `(host,port,user,database)`
  4-tuple. engine/datasource 차원만 추가하면 된다.
- **데이터평면 RO 유저 라우팅 패턴이 있다** — `AGENT_DATA_DB_USER`(L123-126) 최소권한 분기를
  datasource 별로 일반화하면 된다.

## 2. 현재 결합 지점 (3계층, 코드 근거)

### 2.1 드라이버 계층 — [db.py](../src/modules/db.py)
- `connect()`(L104) 가 데이터평면을 `mysql.connector.connect(**params)`(L145)로 직접 연결. replica /
  RO유저 / memory 라우팅 분기가 있으나 **전부 MySQL 드라이버** 한 종류.
- `execute_sql(conn, sql)`(L221) 는 `conn.cursor()` + `cur.execute(sql, multi=False)` — DBAPI 추상이라
  드라이버 교체에 비교적 관대하나, `multi=False` 등 mysql.connector 고유 인자에 묶임.
- `_pg_connect()`(L298)는 **내부 KB(pgvector)** 용이지 분석 대상이 아님 — 혼동 주의.

### 2.2 설정 계층 — [config.py](../src/modules/config.py)
- `DB_HOST/PORT/USER/PASSWORD`(L240-243), `DB_NAME`(L249), `AGENT_DATA_DB_USER/PASSWORD`(L247-248),
  `REPLICA_DB_*`(L256-260) 가 **단일 전역 env**. "여러 datasource" 레지스트리 개념 부재 → 타깃 항상 1개.

### 2.3 방언(dialect) 계층 — [tools.py](../src/modules/tools.py), [insight.py](../src/modules/insight.py)
스키마 탐색·미리보기·EXPLAIN 부하 게이트가 **MySQL SQL 직접 생성**:

| 항목 | MySQL (현재 코드) | MSSQL (T-SQL) 필요 |
|---|---|---|
| 식별자 인용 | `` `schema`.`table` `` 백틱 (tools.py L479·L521·L610) | `[schema].[table]` 대괄호 |
| 행 수 제한 | `LIMIT n` (L610) | `TOP n` / `OFFSET n ROWS FETCH NEXT m ROWS ONLY` |
| 스키마 목록 | `information_schema.SCHEMATA`(L404·L571) | `sys.schemas` 또는 `INFORMATION_SCHEMA.SCHEMATA` (DB 단위 차이) |
| 테이블/행추정 | `information_schema.TABLES.TABLE_ROWS`, `ENGINE` (L439·L447) | `sys.dm_db_partition_stats` / `sys.tables` (ENGINE 개념 없음) |
| 인덱스 | `SHOW INDEX FROM` (L479) | `sys.indexes` + `sys.index_columns` JOIN |
| 컬럼 | `information_schema.COLUMNS` (L472·L553) | 거의 호환되나 타입 표기·`COLUMN_TYPE` 차이 |
| 부하 게이트 | `EXPLAIN {sql}` → `rows`/`filtered` 파싱 (L638·tools.py `_estimate_*`) | 추정 실행계획 `SET SHOWPLAN_XML ON` 또는 `sys.dm_exec_*` (포맷 전혀 다름) |
| 차단 스키마 | `information_schema/mysql/performance_schema/sys` (`_FORBIDDEN_SCHEMAS`, BLOCKED_DEFAULT_SCHEMAS) | `sys`, `INFORMATION_SCHEMA`, 시스템 DB(`master/model/msdb/tempdb`), `xp_*` 확장프로시저 |
| 문자셋 | `charset=utf8mb4` (db.py L136) | N/A (pyodbc/pymssql 연결 옵션 다름) |

insight.py 도 동일 `information_schema` MySQL 쿼리로 테이블/컬럼 탐색(L33·L50·L73·L594·L803·L948).

**2.3.1 보안 게이트 계층 (정정 — REV-20260610-0182 B-1·B-2)**: `execute_sql` 의 실제 방어선은 3중이며
sql_guard 는 그중 하나일 뿐이다:
1. **계정-스코프 스키마 allowlist** — [tools.py](../src/modules/tools.py) `_tool_execute_sql`(L711) 의
   `_whitelist_violation(_extract_sql_schema_refs(sql))`. **정규식 텍스트 추출**이라 MSSQL 식별자
   (대괄호 `[s].[t]`, 3-part `db.schema.table`, ANSI 큰따옴표 `"s"."t"`)를 못 잡아 **allowlist 통째
   우회** — 교차 테넌트/교차 datasource 데이터 유출 경로. **진짜 격리 게이트이므로 P3 에서 AST 기반
   추출로 교체 필수** (§3.4).
2. **DB 계정 RO GRANT** — 에이전트 경로는 `_METADATA_SCHEMAS`(information_schema/mysql/sys/
   performance_schema)를 **의도적으로 허용**하고(카탈로그 조회 필요), 민감 테이블 차단을 MySQL RO
   계정 GRANT 에 위임([tools.py](../src/modules/tools.py) L112-115 명시). 즉 차단 스키마의 1차 방어는
   guard 가 아니라 **GRANT** 다. MSSQL 등가(`db_datareader` + 명시 DENY + system DB 차단 +
   `xp_cmdshell` off)가 없으면 방어선 자체가 부재 (§4).
3. **sql_guard AST** — single SELECT/CTE shape allowlist + denylist. dialect 화 필요하나 단독으로는
   1·2 를 대체 못 함.

## 3. 컴포넌트 (설계)

### 3.1 Datasource 레지스트리 + 시크릿
**신규 제어평면 테이블 `agent_runtime.datasources`** (PG; 제어평면이므로 분석 대상과 분리):

| 컬럼 | 설명 |
|---|---|
| `id` PK / `name` | 사람이 읽는 이름 (예: "운영 MySQL", "BI MSSQL") |
| `engine` | `mysql` \| `mssql` (확장 가능 enum) |
| `host` / `port` / `default_db` | 연결 좌표 |
| `secret_ref` | 자격증명 **참조**(아래) — 평문 저장 금지 |
| `ro_secret_ref` | 최소권한 RO 로그인 참조 (분석 경로 기본) |
| `tls_mode` / `options_json` | 엔진별 연결 옵션 (sslmode, ODBC driver, Encrypt 등) |
| `enabled` / `created_at` / `created_by` | 라이프사이클 |

**시크릿 관리 (신규 핵심 과제)**: 현재는 단일 `.env` 평문 자격증명. 멀티 datasource 는 datasource
별 비밀번호가 필요하므로:
- **MVP**: `.env` 기반 named credential — `DS_<id>_USER/PASSWORD` 패턴 + 레지스트리는 `secret_ref`
  로 env 키만 보관(평문 DB 저장 회피). 운영 단순, 회전은 재배포.
- **목표**: 애플리케이션 레벨 암호화(예: `cryptography.fernet`, 키는 `.env`/KMS) 또는 외부 시크릿
  스토어 참조. **이 선택은 RBAC outside-voice 리뷰에서 확정** (§4 open question).

### 3.2 연결 계층 — 드라이버 디스패치 ([db.py](../src/modules/db.py))
- `connect(datasource_id, database, ...)` 로 시그니처 확장. **단 라우팅 결정을 `database` 문자열
  휴리스틱에서 명시적 `plane`(control|data) + `datasource_id` 로 전환한다** (REV-20260610-0182 M-3):
  현재 data-plane 판정은 `db_str != str(MEMORY_DB)` + `is_sandbox`(`agent_attachment_` prefix) +
  `REPLICA_DB_ENABLED` 의 **문자열 조건 분기**(L113-128)다. datasource 의 `default_db` 가 우연히
  `agent_memory`/`agent_attachment_*` 와 겹치면 RO유저·replica 라우팅이 오작동하므로, "이 conn 이
  제어평면이냐 데이터평면이냐"를 datasource_id 로 결정해야 한다. **callers 전파 표면이 넓다** —
  `file_ops.py`(L570-588)·`insight.py`(L1553-1558)·`utils.py`(L397)·`kb_backend.py` 가 전부
  `database=` 만 넘기므로 datasource_id 인자 추가 + `__all__` export 갱신 필요 ("seam 이미 존재"는
  data/control 구분 *개념*이 있다는 뜻이지 datasource 전파가 공짜라는 뜻이 아님).
- engine 별 분기:
  - `mysql` → `mysql.connector.connect(**params)` (현행 유지)
  - `mssql` → `pyodbc.connect(...)` (ODBC Driver 18 for SQL Server) **또는** `pymssql.connect(...)`.
    드라이버 선택은 §4 open question. **이 결정이 P1 연결 PoC 의 전제이므로(Dockerfile 에 ODBC 패키지
    설치 여부가 빌드를 가른다) 롤아웃 P1 *진입 전*에 확정해야 함** (REV MISSING — 순서 모순 해소, §5).
- 풀 키(`_pool_key`)에 `engine`+`datasource_id` 차원 추가. **단 풀 계약이 MySQL 전용 (Codex-7 MAJOR)**:
  `pool_reset_session`([db.py](../src/modules/db.py) L83)은 mysql.connector 개념이다. MSSQL 세션상태
  (`SET SHOWPLAN_XML`·`LOCK_TIMEOUT`·database context 등)는 예외 경로에서 복구 안 되면 **pooled
  connection 이 다음 대화로 상태를 누출**한다. → Dialect 에 `execute()` 만 추가하지 말고 **checkout/checkin
  시 session reset + 예외 발생 connection 은 풀에 반환 않고 폐기(poison-connection discard) 계약**을 둔다.
- **`execute_sql` + `_collect_cursor_result` 둘 다 dialect 화** (REV-20260610-0182 M-1): `multi=False`
  (L230)·`cur.with_rows`(L211)·`rowcount==-1`(L216) 는 **mysql.connector 전용**이다. pyodbc 커서엔
  `with_rows` 없음, `execute()` 에 `multi` 인자 없음(→ TypeError 폴백 L236 으로 빠지면 multi-statement
  방어가 사라짐), 결과셋 판정은 `description is None`/`nextset()` 기반. 따라서 커서 결과 수집까지
  Dialect.`execute(conn, sql)` 산출로 흡수하고, **pyodbc 에서 `;` 분리 다중문 차단을 어떻게 보장할지
  명시**해야 한다 (드라이버가 배치 실행 허용).
- `connect_with_retry` 의 `_should_retry_db_error`(errno 2003/2006/2013/1205)는 MySQL errno —
  엔진별 retryable 분류를 Dialect 에 위임. **errno 충돌 주의**: MySQL 1205=lock wait timeout vs
  MSSQL 1205=deadlock victim (의미 다름) → SQLSTATE 매핑 표 필요.

### 3.3 Dialect 추상화 (가장 무거운 부분) — **신규 `modules/dialects/`**
`Dialect` ABC + `MySQLDialect`·`MSSQLDialect` 2종 구현. tools.py·insight.py 의 하드코딩 SQL 을
이 인터페이스 호출로 치환:

```
class Dialect(Protocol):
    name: str                                   # "mysql" | "mssql"
    sqlglot_dialect: str                        # "mysql" | "tsql"
    def quote_ident(self, *parts) -> str        # `a`.`b`  vs  [a].[b]
    def list_schemas_sql(self) -> str
    def list_tables_sql(self, schema) -> str    # name, approx_rows, comment
    def describe_columns_sql(self, schema, table) -> str
    def list_indexes_sql(self, schema, table) -> str
    def sample_sql(self, schema, table, limit) -> str   # LIMIT vs TOP
    def explain_sql(self, sql) -> str | None    # None 이면 부하게이트 best-effort skip
    def parse_explain(self, rows) -> CostEstimate
    def system_schemas(self) -> frozenset[str]  # forbidden_schemas 주입원
    def connect(self, params) -> Connection
    def execute(self, conn, sql) -> tuple[results, elapsed]
```

- **부하 게이트 degradation — fail-OPEN 을 반드시 뒤집어야 함** (REV-20260610-0182 M-4): 현재
  [tools.py](../src/modules/tools.py) `_estimate_explain_rows`(L638)는 EXPLAIN 실패 시 `None` 반환 →
  caller(L729 `est is not None`)가 **fail-open**(게이트 통과). MSSQL 은 `EXPLAIN` 구문이 없어 **항상
  예외 → 항상 None → 부하 게이트 영구 무력**. 따라서 `explain_sql → None` 일 때 caller 분기를
  **fail-closed(보수적 거부) 또는 강제 `TOP n` 주입 + 엔진별 timeout** 으로 정의한다. "강제 LIMIT"은
  MySQL `max_execution_time` 세션변수(L672 `_apply_query_cap`)에 의존하는데 MSSQL 은 `SET LOCK_TIMEOUT`/
  쿼리 hint 가 다르고, LLM SQL 에 `TOP` 주입은 **AST 재작성**을 의미(별도 설계) — 단순 문자열 cap 불가.
- **부하 게이트 자체의 우회·무제한 메모리 (Codex-6 MAJOR, 멀티엔진 무관 기존 결함이나 본 설계에 동반 처리)**:
  ① `confirm_heavy=true`([tools.py](../src/modules/tools.py) L721)는 사용자 승인이 아니라 **LLM tool
  인자** — 모델이 스스로 게이트를 해제할 수 있다. 진짜 부하 차단이면 사용자/정책 승인이어야 하고 LLM
  자기선언으로 풀려선 안 된다. ② 실행 후 `execute_sql` 이 `fetchall()`([db.py](../src/modules/db.py) L211)
  로 **전체 결과를 메모리에 적재** 후 CSV 저장 → `TOP`/`LIMIT` 은 출력 행만 제한하고 집계·정렬의 전체
  스캔/대용량 결과를 못 막는다. → row cap + streaming/`fetchmany` + 결과 바이트 상한 고려. 멀티엔진에서
  더 악화(엔진별 메모리 특성)되므로 본 설계 범위에 포함.
- 2 엔진뿐이므로 **hand-rolled 어댑터** 권장. SQLAlchemy Core 채택 여부는 §4 open question
  (reflection 편의 vs 대형 스키마 latency vs 의존성 증가) — 채택 시에도 보안 게이트는 네이티브 유지.

### 3.4 보안 게이트 멀티방언 — 세 축 모두 (REV-20260610-0182 B-1·B-2·B-3 반영)
> **정정**: 이전 초안은 "sql_guard 에 dialect 주입만으로 가드 완성, AST shape allowlist 무변경"이라
> 주장했으나 거짓이었다. 실제 격리 게이트는 §2.3.1 의 3축이며 셋 다 dialect 작업이 필요하다.

**(축1) 계정-스코프 allowlist 의 정규식 → AST 교체 (B-1, 진짜 격리 게이트)**:
[tools.py](../src/modules/tools.py) `_extract_sql_schema_refs` 는 정규식 텍스트 추출이라 MSSQL
식별자에서 깨진다. 실측 우회 케이스:
- `[master].[sys].[objects]`(대괄호) → 참조 0개 추출 → allowlist 통째 통과
- `master.dbo.sysobjects`(3-part) → `{master}` (DB명을 schema 로 오인, 실제 schema `dbo` 미검출)
- `"agent_memory"."x"`(ANSI 큰따옴표, MSSQL `QUOTED_IDENTIFIER ON` 기본) → 0개 → `agent_memory` 차단 우회

→ **`_extract_sql_schema_refs` 를 sqlglot AST 기반 table-ref 수집으로 교체**(이미 존재하는
`sql_guard._collect_table_refs` 재사용) + dialect 별 식별자 정규화(대괄호/큰따옴표 unquote,
3-part `db.schema.table` 분해). 정규식 경로 폐기. 위 우회 케이스를 골든 테스트에 박제.

**AST 만으로도 불충분 (Codex-1 BLOCKER)**: AST 는 명시된 이름만 본다. 다음은 AST 교체 후에도 남는 구멍:
- **무자격 이름** `SELECT * FROM users` → 서버가 기본 catalog/schema 로 암묵 해석 → allowlist 가 못 봄.
  → **무자격 table-ref 는 fail-closed 거부**(스키마 명시 강제) 또는 활성 datasource 의 default schema 로
  정규화 후 검사.
- **view/synonym 간접참조** — 허용 schema 의 view 가 금지 DB/schema/linked server 객체를 참조 →
  표면 이름만 보면 통과. **GRANT(축2)가 진짜 방어선**(view 가 못 읽는 객체는 RO role 도 못 읽음).
- 권한 식별자를 `datasource_id + schema` 가 아니라 **`datasource_id + catalog + schema + object`** 4-tuple
  로 정의(MSSQL 은 catalog=DB 차원이 실재). cross-DB 참조를 catalog 차원에서 차단.

**(축2) DB 계정 RO GRANT 의 MSSQL 등가 — §4 로 (B-2)**: 차단 스키마 1차 방어는 GRANT 다.
guard 의 `forbidden_schemas`(execute_sql 은 `{agent_memory}` 만 주입) 는 에이전트 경로의
메타-스키마 허용 정책상 실효가 제한적. MSSQL GRANT/DENY 매트릭스는 §4.

**(축3) sql_guard AST + denylist 의 dialect 분기 (B-3)**:
- `validate_sql_for_sandbox(sql, *, forbidden_schemas, dialect)` 로 dialect 인자 추가 →
  `sqlglot.parse(sql, read=dialect)`. **단 "AST shape allowlist 무변경" 주장 철회**: T-SQL `SELECT
  ... INTO newtbl` 은 **부수효과(테이블 생성)** 인데 shape 상 SELECT 로 보인다 → shape 검사를
  dialect 별로 분기해야 함.
- **T-SQL denylist 매트릭스를 명시 박제** (현재 `_DENYLIST_PATTERNS`/`_FORBIDDEN_FUNCTIONS` 는 전부
  MySQL 어휘 sleep/benchmark/load_file/`@@`/`SET @` — T-SQL 커버 0): `xp_cmdshell`(RCE),
  `OPENROWSET`/`OPENQUERY`(임의 파일/원격 읽기), `WAITFOR DELAY`(SLEEP 등가), `EXEC(...)`/`sp_executesql`,
  `SELECT ... INTO`, linked server `[srv].[db]..[t]`.
- **sqlglot 버전 pin**: [requirements.txt](../../../requirements.txt) 의 `sqlglot>=23.0.0` 는 상한 없는
  floor — T-SQL 파싱 정확도가 버전마다 변동하고 보안 게이트이므로 **상·하한 pin**. 파싱 실패 시
  fail-closed(deny)는 유지(sql_guard L188).
- **parser-differential — 원문 실행 구조 자체의 한계 (Codex-5 MAJOR)**: sqlglot 이 허용한 AST 와 SQL
  Server 가 **실제 실행하는 원문 SQL** 의 의미가 항상 같다는 보장이 없다(compatibility level·session 설정·
  신규 T-SQL 문법). 버전 pin+denylist 는 "알려진 구문"만 막는다. 더 견고한 자세: **검증된 AST 를 허용
  노드만으로 재직렬화(generate)해 그 결과만 실행**(원문 SQL 직접 실행 폐기) — sqlglot 의 transpile/generate
  로 정규화. 비용(LLM SQL 의도 보존·재직렬화 충실도)이 있어 P3 trade-off 로 평가하되, "원문 실행"은
  지속 취약하다는 점을 명시. 구조화 query builder 는 LLM freeform SQL 자유도와 충돌해 본 제품엔 부적합.

### 3.5 LLM grounding 방언 주입 (assistant 가 실제 작동하려면 필수)
- 스키마 grounding 프롬프트(TASK-0151 경로) + `execute_sql` 도구 설명([tools.py](../src/modules/tools.py)
  L145~)이 현재 "백틱·LIMIT" 등 MySQL 을 지시. **활성 datasource 의 engine 을 프롬프트/도구 설명에
  주입**해 LLM 이 올바른 방언(T-SQL: 대괄호·TOP)을 생성하게 한다.
- 잘못된 방언 생성 시 친절한 에러 회복 경로(이미 있는 `execute_sql` 실패 → describe 재시도 루프) 유지.

### 3.6 insight_worker per-datasource — [insight.py](../src/modules/insight.py)
- 테이블/컬럼 탐색(`information_schema` 직접 쿼리 L33·L50·L73 등)을 Dialect 호출로 치환.
- **스코핑 정책 신규**: 어느 datasource 들에 인사이트를 생성할지 — `datasources.enabled` +
  per-datasource `insight_enabled` 플래그. 워커 루프가 datasource 목록을 순회.
- **fingerprint/KV/CSV 키에 `datasource_id` 차원은 하드 요구사항** (REV-20260610-0182 M-2, "주의"에서
  승격): 현재 KV 키가 `schema_fp:{schema}`(L941)·`table_fp:{schema}.{table}`(L1145·1299) 로
  **datasource 무차원**이다. MySQL `appdb.users` 와 MSSQL `appdb.users` 가 같은 키 → fingerprint
  상호 덮어쓰기 → 매 tick missing/changed 오판 → [[project_insight_livelock_readback_mismatch]] 와
  동형 livelock + 머신 점유. CSV 파일명도 과거 충돌 이력([[project_task0154_csv_collision]]). 따라서
  **모든 KV 키·CSV 파일명·`_insight_readback_degraded` 판정에 `datasource_id` prefix 필수**. P4
  합격선 = "동명 스키마 2 datasource 동시 인사이트 무충돌 + livelock 부재".
- **fingerprint 키만으론 부족 — insight FACT 스코프까지 (Codex-3 BLOCKER)**: 실제 insight fact 는
  여전히 `schema_insight:{schema}`(L1272)·`table_insight:{schema}.{table}`(L1347)·`FACT_SCOPE_COMMON`
  으로 게시된다. fingerprint(재생성 판정)만 datasource 화하고 fact 스코프를 안 고치면, 두 datasource 의
  동명 객체가 공용 fact/RAG 에서 충돌하거나 **다른 datasource 대화에 grounding 으로 교차 노출**된다(정확성
  문제가 아니라 메타데이터 유출). → fact key·`FACT_SCOPE_COMMON`·RAG 게시·grounding 조회([[project_task0151_dbquery_ux_grounding]]
  의 `_load_relevant_table_insights` 경로) 전부 `datasource_id` 로 스코프. 합격선에 "datasource A 대화가
  datasource B 의 table_insight 를 grounding 으로 못 받음" 추가.
- **연결 실패 격리**: datasource 순회 중 한 datasource down 이 워커 루프 전체를 막지 않도록 per-datasource
  try/except + degraded 마킹 (전체 중단 금지) — REV MISSING.

### 3.7 대화 ↔ datasource 바인딩
- 대화/세션에 `datasource_id` 추가 (제어평면). 대화 생성 시 선택, 대화 중 전환 정책(전환 허용 시
  스키마 grounding 재빌드) 결정.
- `allowed_schemas`(현재 MySQL 스키마 화이트리스트) 의미를 datasource 범위로 한정.

### 3.8 Web UI — [feature-0003-agent-web-ui](../../feature-0003-agent-web-ui/)
- 대화 화면 **datasource 선택기**.
- 관리자 **datasource CRUD**(등록·연결테스트·시크릿 입력·enable/disable).
- datasource 별 스키마 브라우저.

## 4. 보안 / RBAC (최고 위험 — outside-voice 필수)

[[feedback_outside_voice_for_rbac]]: 권한 모델 변경은 정적 catalog blindspot 때문에 Codex/subagent
외부 시각 필수. 본 설계의 RBAC 신규 표면:

- **datasource 단위 접근권한**: 어떤 사용자/역할이 어떤 datasource 를 조회 가능한가 (권한 catalog
  확장). 기존 RBAC([[project_profile_tabs_restructure_cycle]] 류)와 정합 필요.
- **자격증명 저장·회전**: §3.1 시크릿 전략 확정 (env named vs app 암호화 vs 외부 스토어).
- **최소권한 RO 강제 + MSSQL GRANT 매트릭스를 산출물로 명시 (B-2, 핵심 — Codex-2 정정)**: 차단 스키마의
  1차 방어가 GRANT 이므로(§2.3.1 축2), datasource 별 MSSQL 최소권한 로그인 부트스트랩 스크립트를 **P5(보안
  먼저, §10 Codex-4)** 산출물로 둔다. **단 `db_datareader` 는 금지** — `db_datareader` 는 DB 내 모든
  사용자 테이블/뷰 읽기를 부여해 애플리케이션 allowlist 우회 시 계정이 못 막는다(allowlist=DB계정 양면
  방어 전제와 정면 충돌, Codex-2). 대신 **datasource 별 전용 role 에 `allowed_schemas`/허용 view·object
  에만 `GRANT SELECT`**(deny-by-default, allowlist 와 GRANT 가 같은 객체집합을 가리키도록). `xp_cmdshell
  off`·cross-DB ownership chaining off 같은 **서버 전역 설정은 datasource별 스크립트의 소유가 아니다** —
  서버 사전조건(prerequisite)으로 분리하고 부트스트랩은 검증만. MySQL RO(`AGENT_DATA_DB_USER`)도 동일
  원칙으로 일반화(스키마 화이트리스트 = GRANT 대상). RW 폴백은 멀티엔진에서 금지.
- **엔진별 위험 표면**: MSSQL `xp_cmdshell`(RCE)·`OPENROWSET`/`OPENQUERY`(파일/원격)·linked server·
  `EXEC`/`sp_executesql`·`WAITFOR` — **SQL guard denylist(§3.4 축3) + RO GRANT/DENY(축2) 양면 차단**.
  한 축만으로는 불충분(guard 우회 가능성 B-3 + GRANT 만으로는 SELECT INTO 류 못 막음).
- **차단 스키마 정합**: Dialect.`system_schemas()` 가 누락하면 시스템 카탈로그 유출 → 엔진별 정합
  테스트 필수.

### Open questions
**확정됨 (사용자 결정 2026-06-10, ADR-CORE-0003 → §5 롤아웃 재구성):**
- ✅ **Q6/Q8 첫 증분 = multi-MySQL 먼저** — P1~P3 은 MySQL 전용 멀티-datasource(레지스트리·바인딩·RBAC·
  insight). MSSQL 방언/보안 재작성은 별 cycle(P4~P7, RBAC outside-voice 재게이트). 플러밍과 MSSQL
  Critical 재작성의 실패 모드가 달라 분리(= Codex-9 더 싼 경로 채택). 대안 B(동시)·C(별 서비스) 기각.
- ✅ **Q7 보안경계 = 연결과 동시(security-first)** — datasource 접근 RBAC + datasource-스코프 allowlist +
  per-datasource RO 자격증명이 **연결 디스패치와 같은 증분(P1)** 에 든다. flag 는 권한검사가 아니므로
  (Codex-4) datasource_id 가 무검증 연결권한이 되는 창을 만들지 않는다. admin-only flag 우회안 기각.

**미확정 (MSSQL 확장 cycle 진입 시):**
1. MSSQL 드라이버: `pyodbc`(ODBC Driver 18, MS 패키지) vs `pymssql`(FreeTDS) — P4 진입 전.
2. 시크릿 전략: `.env` named credential(MVP) → app-level 암호화/외부 스토어(목표) 의 경계는?
3. SQLAlchemy Core 채택 여부 (connection/reflection 한정) vs 완전 hand-rolled?
4. MSSQL 부하 게이트: 추정 실행계획 파싱 즉시 구현 vs "강제 TOP+timeout" fail-safe 우선?
5. 대화 중 datasource 전환 허용 여부 (grounding 재빌드 비용·혼동 위험)?

## 5. 롤아웃 (단계 — 단일 PR 불가, ADR-CORE-0003 으로 재구성)

> **재구성 (2026-06-10 사용자 결정)**: multi-MySQL 먼저(Q6/Q8) + 보안경계 연결과 동시(Q7). 이전 P0
> (MSSQL 드라이버 선행)은 MSSQL 확장이 뒤로 빠지면서 P4 로 이동. P1~P3 은 **MySQL 전용**이라 방언/MSSQL
> 보안 재작성 위험이 0 이다.

### Stage 1 — multi-MySQL (방언/MSSQL 보안 재작성 없음)
1. **P1 — 레지스트리 + 연결 디스패치 + 보안경계 (security-first, 한 증분) — ✅ 구현됨 (TASK-0187)**:
   > **구현 시 설계 개선 (product-바인딩)**: 별도 `datasources` 테이블 + 대화↔datasource 바인딩 대신,
   > **이미 존재하는 `WebProducts` 추상화에 datasource 를 매달았다**(product = 스키마 묶음, 대화에
   > `product_id` 로 이미 바인딩). 이로써 설계가 P1 에 요구한 두 보안 항목이 **기존 product 머신러리로
   > 자동 충족**된다 — datasource-스코프 allowlist = `_product_allowed_schemas`(이미 product-scope),
   > datasource 접근 RBAC = `product.access.<key>`(이미 /api/ask 연결 *전* enforce). 대화는
   > 대화→product→datasource 로 datasource 를 얻는다(별도 conversation↔datasource 컬럼 불필요).
   - **레지스트리 = .env named credential** (`AGENT_DATASOURCE_KEYS` + `DS_<KEY>_HOST/PORT/USER/PASSWORD/
     DEFAULT_DB`, `config.DATASOURCES` 로 파싱). 좌표/비밀번호는 **DB·job payload 에 비저장** — 키만
     `WebProducts.DatasourceKey`(MySQL ALTER) 에 저장(security-first 시크릿 MVP). DB 테이블 레지스트리는
     P2(CRUD UI) 진화 대상.
   - **연결 디스패치**: `db.connect(datasource=<coords>)` 가 flag ON+datasource 시 좌표 라우팅(문자열
     휴리스틱 우회), flag OFF/None 시 기존 경로 0 변경. 단일 chokepoint `agent_core._resolve_product_datasource`
     (product_id→`WebProducts.DatasourceKey`→`config.DATASOURCES`)가 in-process·ask-worker 양 경로 커버.
   - **보안경계 동시(Q7/Codex-4)**: ① datasource 접근 = product.access 권한(연결 전 enforce, flag≠권한검사)
     ② allowlist = product 허용 스키마(자동 datasource-scope) ③ per-datasource RO 자격증명(`DS_<KEY>_USER` =
     product 허용 스키마에만 GRANT SELECT 한 RO 유저, 운영 책임; db_datareader 류 광권한 금지 Codex-2)
     ④ 관리 `PATCH /api/admin/products/{id}/datasource`(console.manage) audit + 미등록 키 거부.
   - flag `AGENT_MULTI_DATASOURCE_ENABLED` 기본 OFF. 합격선 "기존 단일 MySQL 동작 0 변경" — 회귀
     테스트(flag OFF / datasource 미바인딩 시 DB_HOST 그대로) PASS. **이월(P3)**: insight_worker 는 본
     P1 에서 미변경(기본 DB 분석 유지) — per-datasource insight 는 P3.
   - **outside-voice 보안 하드닝(REV-20260610-0187)**: ① (M-1) datasource 의 `default_db` 를 연결의
     암묵 기본 스키마로 적용하지 않는다(`database=None`) — 미접두 쿼리가 allowlist 를 우회해 default_db
     를 읽는 구멍 차단, schema-prefixed 쿼리만 허용해 allowlist 가 유일 게이트. ② (M-2) 명시 바인딩된
     product 의 datasource 키가 .env 미등록이면 운영 DB 로 silent 폴백하지 않고 **fail-closed**(run 중단,
     `DatasourceResolutionError`). ③ (N-2) `DS_<KEY>_USER` 는 필수 — 미설정 시 root(DB_USER) 폴백 금지
     (datasource=RO 원칙). make test 회귀 0.
2. **P2 — multi-MySQL Web UI**: datasource CRUD(등록·연결테스트·enable/disable) + 대화 datasource 선택기.
3. **P3 — insight_worker per-datasource (MySQL)**: fingerprint/KV/CSV **+ fact 스코프**(`schema_insight`/
   `FACT_SCOPE_COMMON`/RAG/grounding 전부 datasource_id, Codex-3) + stagger 스케줄(PF2) + 연결실패 격리.

> **--- Stage 2 게이트: RBAC outside-voice 재게이트 + §4 Q1~Q5 확정 후 진입 ---**

### Stage 2 — MSSQL 확장 (Critical, 별 cycle + outside-voice)
4. **P4 — MSSQL 드라이버 + 빌드 전제** (구 P0): pyodbc(`msodbcsql18`+`unixODBC`, linux/amd64·ARM 미지원,
   이미지↑) vs pymssql(FreeTDS) 결정 → Dockerfile. ARM/CI([[project_gha_ci_shared_permission]])·테스트
   컨테이너 라이선스(§7) 동반.
5. **P5 — Dialect 어댑터(MSSQL) + 단일 canonical AST**: `modules/dialects/` + tools.py·insight.py SQL 을
   Dialect 호출로 치환. MySQL 골든 회귀 0 변경 후 MSSQL. 게이트가 공유하는 단일 AST(A2/C1).
6. **P6 — MSSQL 보안경계**: AST allowlist(무자격 fail-closed + catalog 차원, Codex-1) + MSSQL 전용 role
   GRANT SELECT(Codex-2) + T-SQL denylist/shape(B-3) + 검증 AST 재직렬화 평가(Codex-5) + 부하게이트
   fail-closed(M-4) + 세션 reset/poison discard(Codex-7) + confirm_heavy 비-LLM 승인(Codex-6).
7. **P7 — MSSQL insight + UI 통합**.

각 단계는 flag 뒤 canary. Stage 1(P1~P3)은 "MySQL 동작 0 변경"이 합격선. Stage 2 진입은 RBAC
outside-voice 재게이트 필수([[feedback_outside_voice_for_rbac]]).

## 6. 핵심 위험 (why 자체 cycle + outside-voice)

- **데이터 접근 경계 회귀**: dialect 치환 중 차단 스키마/SQL guard 가 한 엔진에서 약해지면 즉시
  데이터 유출. 엔진별 보안 회귀 테스트 필수.
- **자격증명 표면 확대**: 단일 env → N datasource 시크릿. 저장·회전·로그 마스킹 전부 신규 위험.
- **MySQL 회귀**: 광범위한 tools.py·insight.py 치환이 기존 단일 MySQL 동작을 깨면 라이브 영향. 골든
  테스트 + flag 보호.
- **부하 게이트 약화**: MSSQL EXPLAIN 미구현 시 무거운 쿼리 방어 공백 → fail-safe(LIMIT+timeout) 보수화.
- **insight read-back 정합**: datasource 차원 추가가 fingerprint/KV 키 정합을 깨면
  [[project_insight_livelock_readback_mismatch]] 류 livelock 재발 가능.

## 7. 테스트 계획 (미래 cycle)

- **MySQL 골든 회귀**: P2 전/후 tools.py·insight.py 가 동일 SQL 산출 (dialect 치환 무해성).
- **MSSQL 통합**: 테스트용 MSSQL 컨테이너(`mcr.microsoft.com/mssql/server`) 띄워 connect/describe/
  sample/execute/guard end-to-end.
- **보안 회귀**: 엔진별 차단 스키마 우회 시도(시스템 카탈로그·`xp_cmdshell`·multi-statement·DDL/DML)
  전부 reject 단언. [sql_guard.py](../src/modules/sql_guard.py) 테스트를 dialect 매트릭스로 확장.
- **RBAC**: datasource 접근권한 enforce — 무권한 사용자/역할의 조회 차단 + 권한 catalog prune.
- **시크릿**: 평문 비저장·로그 마스킹·회전 시 무중단.
- **insight per-datasource**: 2개 datasource 동시 인사이트 생성, read-back 정합, livelock 부재.

## 8. 결정 기록

- ADR-CORE-0002 (제안 — A 채택 + 설계만) — [DECISIONS.md](DECISIONS.md).
- 본 설계는 ask-worker(ADR-WEB-0004, DESIGN-ask-worker → 구현 이월) 와 동일한
  "설계 먼저, 구현은 자체 cycle + outside-voice" 패턴을 따른다.

## 9. Outside-voice 적대적 리뷰 반영 (REV-20260610-0182)

설계 단계 outside-voice 적대적 리뷰(skeptical 시니어 DB/보안 엔지니어, 별 컨텍스트) **Verdict:
NEEDS-TWEAK** — BLOCKER 3 + MAJOR 4. 본 설계는 design-only 이므로 발견을 **설계 문서에 직접 반영**해
BLOCKER 를 설계 수준에서 해소했다(코드 mutation 0). 구현 cycle 진입 시 본 절을 합격선으로 사용.

| ID | 발견 | 반영 위치 |
|---|---|---|
| B-1 | 진짜 격리 게이트가 sql_guard 아닌 tools.py **정규식** allowlist — MSSQL 식별자(대괄호/3-part/큰따옴표)에서 통째 우회 | §2.3.1 축1, §3.4 축1 (AST 교체 필수 + 골든 우회 케이스) |
| B-2 | 차단 스키마 1차 방어가 실은 **MySQL RO GRANT** — MSSQL 등가 GRANT/DENY 매트릭스 미설계 | §2.3.1 축2, §4 (부트스트랩 스크립트 산출물화) |
| B-3 | sqlglot tsql 견고성 미검증 + T-SQL 위험구문(xp_cmdshell/OPENROWSET/WAITFOR/SELECT INTO) 커버 0 + "AST shape 무변경" 거짓 | §3.4 축3 (denylist 매트릭스 + shape dialect 분기 + 버전 pin) |
| M-1 | `execute_sql`/`_collect_cursor_result` 가 mysql.connector 고유 API 묶임 | §3.2 (커서 수집까지 dialect 화) |
| M-2 | insight fingerprint/CSV 키에 datasource 차원 부재 → livelock 재발 | §3.6 (하드 요구로 승격) |
| M-3 | `connect(datasource_id=None)=하위호환` 이 `database` 문자열 라우팅 현실과 어긋남 | §3.2 (plane+datasource_id 명시 라우팅 + caller 전파) |
| M-4 | EXPLAIN 부하게이트 fail-OPEN → MSSQL 에서 항상 통과 | §3.3 (fail-closed/강제 TOP 로 전환) |

**잔여 MISSING (구현 cycle 추적 — 본 설계가 명시적으로 남기는 follow-up)**:
- **테스트 MSSQL 컨테이너**: `mcr.microsoft.com/mssql/server` 는 `ACCEPT_EULA=Y`·최소 2GB RAM·
  linux/amd64 전용(ARM 개발기/CI 미지원). CI `/shared` 권한 이슈([[project_gha_ci_shared_permission]])와
  겹침 — CI 통합 전략 별도 결정.
- **자격증명 로그 마스킹**: pyodbc 연결 문자열은 password 인라인 → 예외 메시지 평문 노출 위험.
  `connect()` 예외/`_pool_key` 로깅 경로의 마스킹을 P1 보안 합격선에.
- **마이그레이션 순서 vs 미완 cutover**: 신규 `agent_runtime.datasources`(PG)를 현재 KB/KV 쓰기
  미완 cutover 상태([[project_may27_cutover_broke_writes]])에서 추가하는 안전성 선검토.
- **datasource 차원 관측성**: per-datasource latency/실패율/비용 + "어느 datasource 가 어느 대화에서
  쓰였나" audit — [[project_llm_usage_dashboard]] 패턴 차용.
- **dbhub MCP 경로**: `mcp` 서비스 단일 `--dsn` — MCP 경로로 datasource 노출 시 멀티 DSN/인스턴스 필요.
  본 설계는 네이티브 경로 중심이라 MCP 경로는 범위 외로 명시.

> 강점(리뷰 확인): 데이터평면만 멀티엔진화하는 scope 절단·flag OFF 기본·"MySQL 동작 0 변경" 골든
> 회귀 합격선·자체 cycle + RBAC outside-voice 게이트는 위험 등급에 정합. 단 "보안 게이트 재작성
> 불필요" 중심 전제가 틀렸던 것을 §3.4 에서 철회·교정함.

## 10. plan-eng-review 2차 반영 (REV-20260610-0182-ENG + Codex cross-model)

`/plan-eng-review` (엔지니어링 매니저 렌즈) + **Codex cross-model outside voice** 2차 리뷰. 1차(REV-0182,
Claude subagent)·본 설계가 놓친 것을 추가 발굴. design-only 이라 전 발견을 본 문서에 직접 반영.

**Codex Verdict: REJECT** — BLOCKER 4 + MAJOR 5 (권한 경계 오모델링 + 보안경계 뒤늦은 구현).

| ID | 발견 | 반영 |
|---|---|---|
| Codex-1 (BLOCKER) | AST 추출도 불완전 — 무자격 이름/view·synonym 간접참조/ownership chaining. 권한식별자 `datasource_id+catalog+schema+object` | §3.4 축1 (무자격 fail-closed + catalog 차원 + view 는 GRANT 가 방어) |
| Codex-2 (BLOCKER) | `db_datareader+DENY` 가 allowlist 와 양립 불가(DB 전체 읽기) | §4 정정 (전용 role + 허용 view/object 만 `GRANT SELECT`, db_datareader 금지) |
| Codex-3 (BLOCKER) | insight 격리가 fingerprint 키에만 — fact 스코프(`schema_insight`/`FACT_SCOPE_COMMON`)는 교차노출 | §3.6 (fact key·RAG·grounding 까지 datasource_id 스코프) |
| Codex-4 (BLOCKER) | rollout 이 보안경계 뒤늦음 — P1~P4 동안 datasource_id 가 권한검증 없이 연결권한. flag≠권한검사 | §4 Q7·§5 (보안경계 P1 앞으로 재배치 — open question) |
| Codex-5 (MAJOR) | sqlglot AST ≠ SQL Server 실행 의미(parser-differential) | §3.4 축3 (검증 AST 재직렬화 실행 — 원문 실행 폐기 평가) |
| Codex-6 (MAJOR) | `confirm_heavy` 가 LLM tool 인자(모델 자기우회) + `fetchall()` 무제한 메모리 | §3.3 (사용자/정책 승인화 + row cap·streaming) |
| Codex-7 (MAJOR) | MSSQL 세션상태 pooling 누출 | §3.2 (session reset + poison-connection 폐기 계약) |
| Codex-8 (MAJOR) | "제어평면 untouched" 거짓 → 마이그레이션/rollback/백필 정책 누락 | §1 비목표 정정 (제어평면 스키마 추가 명시 + 백필 실패 정책) |
| Codex-9 (MAJOR) | scope 과대 — 검증 전 registry+dialect+insight+CRUD+RBAC+secret 일괄 | §4 Q8 (더 싼 경로 — open question) |

**엔지니어링 매니저(Claude) 발견 — 반영**:
- **A2/C1 [보안 하드닝]** sql_guard shape 체크와 schema-ref 추출이 **각각** sqlglot 파싱하면 dialect 해석
  차이로 우회 → **단일 canonical AST 를 두 게이트가 공유**, dialect 특이사항은 **Dialect 객체가 단일 소유**.
  (Codex-1·5 와 정합 — 같은 AST 가 격리 근거)
- **PF1 [pool]** N datasource × pool_size = 연결한도 소진 → per-datasource + total cap.
- **PF2 [insight]** 매 tick N datasource 전수 스캔 = 부하 N배 → **stagger 스케줄링**(전수 매틱 금지).

**Cross-model 합의(강신호)**: scope 축소·MySQL-first (Codex-9 ↔ Claude Step 0), insight 교차노출 (Codex-3 ↔
M-2 심화), pool 세션상태 (Codex-7 ↔ M-1/A 심화). → 구현 cycle 의 가장 큰 두 결정은 **(a) 보안경계를 P1
앞으로(Codex-4)** **(b) P1 을 MySQL-only 로 축소할지(Codex-9, 사용자 보류)** — 둘 다 §4 open question.

### NOT in scope (이번 리뷰가 명시적으로 미룬 것)
- P1 시퀀싱·보안경계·scope (§4 Q6/Q7/Q8): **확정됨 — ADR-CORE-0003**(multi-MySQL 먼저 + security-first).
  §5 Stage 1/2 로 재구성. 더 이상 미해결 아님.
- 크로스엔진 페더레이션 / MySQL·MSSQL 외 엔진 / 제어평면 store 엔진 교체 (§1 비목표 유지).
- 구현 코드: 본 cycle 은 설계만. Stage 1·2 단계는 자체 cycle.

### What already exists (재사용 — rebuild 금지)
- `bytebase/dbhub` MCP (멀티엔진, 게이트 우회 → 주경로 제외), `sql_guard._collect_table_refs`(AST 수집
  재사용), `_pool_key` 시그니처, `AGENT_DATA_DB_USER` RO 라우팅, `test_sql_trust_boundary.py`(보안경계
  테스트 → dialect 매트릭스로 확장), TASK-0151 grounding 경로(방언 주입점), TASK-0172 EXPLAIN 게이트.

### Failure modes (신규 코드경로별 — 1 현실적 실패 + 테스트/에러처리 유무)
| 경로 | 실패 | 테스트 | 에러처리 | critical? |
|---|---|---|---|---|
| AST allowlist (무자격/view) | 무자격 이름이 금지객체 읽음 | 골든 우회 케이스 | fail-closed 거부 | **critical gap until P3** |
| RO GRANT (db_datareader 오용) | 전체 테이블 노출 | RO 실연결 차단 테스트 | 전용 role GRANT | **critical gap until P5** |
| insight fact 스코프 | datasource 교차 grounding | 2-ds 무교차 테스트 | datasource_id 스코프 | **critical gap until P4** |
| pool 세션누출 | SHOWPLAN 상태 다음 대화 누출 | session-reset 테스트 | poison discard | high |
| EXPLAIN fail-open | MSSQL 무거운 쿼리 무방어 | fail-closed 테스트 | 강제 TOP+timeout | high |

### Worktree 병렬화
P0(드라이버/빌드)·보안경계(Codex-4) 선행 후: **Lane A** dialects/(P2 어댑터) → **Lane B** insight.py(P4,
dialects 의존) 순차; **Lane C** Web UI(P6, 독립). A·C 병렬 가능, B 는 A 뒤. 단 보안경계(allowlist AST·
GRANT)는 **단일 lane 직렬**(데이터 격리는 분할 금지).

### Implementation Tasks (구현 cycle 진입 시 — 본 cycle 은 설계만이라 미실행)
- [ ] **T1 (P1)** 보안경계 선구현 — datasource 접근권한 RBAC + AST allowlist(무자격 거부) + 전용 role GRANT (Codex-1/2/4). Verify: `test_sql_trust_boundary.py` dialect 매트릭스 + RO 실연결 차단.
- [ ] **T2 (P1)** datasource 레지스트리 + `connect(datasource_id)` 명시 plane 라우팅 + datasource_id=1 백필 (M-3, Codex-8).
- [ ] **T3 (P2)** `modules/dialects/` 단일 Dialect 소유 + 단일 canonical AST 공유 (A2/C1).
- [ ] **T4 (P3)** sql_guard dialect + T-SQL denylist + 검증 AST 재직렬화 평가 (B-3, Codex-5).
- [ ] **T5 (P4)** insight per-datasource — fingerprint + **fact 스코프** + stagger (M-2, Codex-3, PF2).
- [ ] **T6 (P3)** 부하 게이트 — confirm_heavy 비-LLM 승인화 + fetchall→streaming (Codex-6).

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open→folded | Arch 3 / Quality 2 / Perf 3, all folded to §10 |
| Outside Voice | Codex (cross-model) | Independent 2nd opinion | 1 | REJECT→folded | BLOCKER 4 + MAJOR 5, all folded to §10 |
| Outside Voice (1차) | Claude subagent | adversarial design | 1 | NEEDS-TWEAK→folded | BLOCKER 3 + MAJOR 4 (§9) |

- **CROSS-MODEL:** 합의 — scope 축소/MySQL-first, insight 교차노출, pool 세션상태. Codex 가 보안경계 시퀀싱(Codex-4)·db_datareader 오류(Codex-2)를 추가 포착(Claude 리뷰·1차 미포착).
- **UNRESOLVED:** ~~P1 시퀀싱·보안경계·scope~~ → **확정됨**(사용자 2026-06-10, ADR-CORE-0003): multi-MySQL
  먼저 + 보안경계 연결과 동시. §5 Stage 1/2 재구성. 잔여: MSSQL 확장(Stage 2) 진입 시 §4 Q1~Q5.
- **VERDICT:** ENG CLEARED (design-only) — 전 발견 설계 반영 완료 + 롤아웃 시퀀싱 확정(ADR-CORE-0003).
  Stage 1(multi-MySQL) 구현 cycle 진입 가능, Stage 2(MSSQL) 진입 전 RBAC outside-voice 재게이트. 코드 mutation 0.

## 11. P6 구현 보고 (MSSQL 보안경계 + 실 인스턴스 검증 — TASK-0201)

Stage 2 P6 구현 완료. flag OFF shadow 유지(MSSQL datasource 미바인딩 시 동작 0 변경 — 활성 dialect
기본 mysql 이라 모든 경로가 골든). 합격선 = "보안경계 dialect 매트릭스 reject 단언 + MySQL 골든 회귀 0".

**구현 (§5 P6 정의 대조):**
- **축1 — AST allowlist (Codex-1):** [tools.py](../src/modules/tools.py) `_extract_sql_schema_refs` 정규식 →
  [sql_guard.py](../src/modules/sql_guard.py) `collect_schema_refs` (활성 dialect 파싱) 로 교체. `_collect_table_refs`
  가 `.catalog/.db/.name`(unquoted) 접근자 사용 → 대괄호 `[s].[t]`·3-part `c.s.t`·ANSI `"s"."t"`·백틱 우회(B-1)
  봉쇄. **무자격 table-ref 는 datasource 활성 시 fail-closed** + **catalog(DB) 차원 cross-DB 차단**(default_db
  외 거부) — `_freeform_sql_access_error`. 레거시 단일 MySQL(active_ds None)은 무자격 허용(골든).
- **축3 — sql_guard dialect 분기 (B-3):** `validate_sql_for_sandbox(..., dialect=)` + `sqlglot.parse(dialect=)`.
  T-SQL denylist 매트릭스 박제(`xp_cmdshell`·`OPENROWSET`/`OPENQUERY`/`OPENDATASOURCE`·`WAITFOR`·`EXEC(UTE)`·
  `sp_executesql`·`SELECT … INTO`·`@@`) + dialect 별 금지함수. `SELECT INTO` 는 denylist + AST `into`-arg 이중
  차단. 파싱 실패 fail-closed 유지. sqlglot 상·하한 pin(P4, `>=23,<28`; 실측 27.29).
- **m3 — dialect 시스템/메타데이터 스키마:** Dialect 객체가 단일 소유(A2/C1). MSSQL `system_schemas()`=
  sys/INFORMATION_SCHEMA/guest/db_*(역할) 제외, **dbo 는 사용자 스키마로 유지**(기본 거처). `metadata_schemas()`
  항상-허용은 sys/INFORMATION_SCHEMA 만(db_datareader 등 역할 스키마는 allowlist 통과 필요).
- **M-4 — 부하게이트 fail-closed:** `Dialect.supports_load_estimate`. (P6 초기) MSSQL=False → gate 모드 일괄
  사전 차단(fail-open 뒤집음). MySQL 은 종전 fail-open 유지(골든).
  - **→ TASK-0299 (2026-06-17) 후속 구현:** MSSQL=True 로 전환 — `SET SHOWPLAN_ALL ON` 으로 본 쿼리 미실행
    추정 실행계획을 받아 `EstimateRows×EstimateExecutions` 최대 operator 를 예상 처리 행수로 산출(MySQL EXPLAIN
    등가). 일괄 차단 대신 *추정* 기반 게이팅. `gate_fail_closed_on_estimate_error=True` 로 **추정 실패**(SHOWPLAN
    미권한/연결)는 gate 에서 차단(M-4 안전 보존), confirm_heavy 로도 우회 불가(Codex-6). 세션 poison 은 `OFF`
    finally 보장(Codex-7). RO 부트스트랩에 `GRANT SHOWPLAN` 추가(데이터 비노출). 상세: FUNCTION.md (TASK-0299),
    CHG-20260617-0310.
- **Codex-6 — confirm_heavy 비-LLM:** `AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM`(기본 true=현행). false 면 LLM 의
  confirm_heavy 무시(모델 자기우회 차단). **사용자/UI 승인 라운드트립은 P7 이월** — 그 전 hardened 모드는 무거운
  쿼리 차단.
- **Codex-2 — MSSQL GRANT 모델:** [bin/datasource-mssql-ro-bootstrap.sql](../../../bin/datasource-mssql-ro-bootstrap.sql)
  운영자 템플릿. **db_datareader 금지**, 전용 role 에 허용 스키마만 `GRANT SELECT`(deny-by-default, allowlist=
  GRANT 대상). 0단계에서 서버 prerequisite(xp_cmdshell/cross-DB ownership chaining/Ad Hoc Distributed
  Queries OFF) 검증 — 어긋나면 RAISERROR 실패.

**평가/결정 (구현 대신 명시 판정):**
- **Codex-5 — 검증 AST 재직렬화: 미채택(원문 실행 유지).** sqlglot generate 로 정규화 후 실행하면 LLM freeform
  SQL 의 의도(엔진 고유 함수·힌트·문법)가 손실돼 본 제품의 분석 자유도와 충돌한다. 대신 dialect 파싱 + denylist
  매트릭스 + 버전 pin + 파싱실패 fail-closed 로 "알려진 위험구문"을 차단한다. **잔존 위험 명시**: sqlglot 이 허용한
  AST 와 SQL Server 실제 실행 의미가 compat level·session 설정·신규 문법에서 어긋날 수 있다 → MSSQL 활성은
  flag + RO GRANT(축2, 최종 backstop) 전제. 재직렬화는 향후 위험도 상승 시 재평가.
- **Codex-7 — 세션 reset/poison discard: 아키텍처로 해소.** MSSQL 은 [db.py](../src/modules/db.py) `_connect_mssql`
  가 풀 없이 **매 연결 fresh**(pymssql direct) — 대화 간 세션상태 누출 경로 부재. MySQL 은 기존 pool
  `pool_reset_session`(AGENT_DB_POOL_RESET_SESSION) 가 처리. 본 코드는 SHOWPLAN/LOCK_TIMEOUT 등 세션상태를
  설정하지 않는다(부하게이트는 MSSQL 에서 fail-closed — SHOWPLAN 미사용). 추가 코드 불요.

**테스트:** [test_mssql_security_boundary.py](../tests/test_mssql_security_boundary.py) — dialect 매트릭스(T-SQL 위험구문
reject + MySQL 골든 allow/block + 백틱 agent_memory 봉쇄), B-1 우회 3종 박제(bracket/3-part/ANSI), 무자격·cross-DB
정책, dialect 시스템스키마, M-4 fail-closed, Codex-6 플래그. 전체 스위트 회귀 0.

### 11.1 실 MSSQL 인스턴스 검증 (사용자 요청 — assistant·insight 작동 확인)

SQL Server 2022 실 인스턴스(사용자 Windows 호스트 `172.28.64.1:14330`, DB `dk_data_release` 123테이블)에 P6
코드를 연결해 **engine/tool 계층 + 보안경계**를 실측. **최소권한 RO 로그인을 부트스트랩으로 생성**(GRANT SELECT
on dbo, db_datareader 아님)해 사용. 결과:
- **도구 전부 동작**: list_schemas(123테이블)·describe_schema·describe_table·get_sample_rows·search_tables·
  get_table_indexes·execute_sql(GROUP BY/JOIN/COUNT) — 실데이터 정상 반환.
- **보안경계 차단 실증**: xp_cmdshell·OPENROWSET·cross-DB(`GameLog_151.*`)·무자격·allowlist밖·write(INSERT) 전부
  reject. **2축 방어 실증**: cross-DB 는 앱 catalog 체크 + DB GRANT 양쪽에서 차단(RO 가 타 DB 접근 시 SQL Server
  `916 not able to access database`).
- **서버 hardening 갭 발견**: 대상 서버는 `xp_cmdshell` 이 **ON**(부트스트랩 0단계 prereq 가 검출). 앱 denylist +
  RO GRANT 로 agent 는 호출 불가하나, 운영자에게 서버측 OFF 권고. → 부트스트랩 usage 에 **`sqlcmd -b` 필수**
  명시(prereq RAISERROR 가 `-b` 없이는 중단 못 하던 결함 보완).

**실 인스턴스에서 드러난 P5 dialect 버그 4건 수정(P5 는 shadow 라 미실측)**:
1. **`sys.dm_db_partition_stats` 권한**: 행수 집계 DMV 는 `VIEW DATABASE STATE` 권한 필요 → 최소권한 RO 에서
   `(297) permission denied`. **`sys.partitions`(metadata-visibility)** 로 교체 — db_datareader 금지/스키마
   GRANT-only RO 와 양립. (이 버그는 최소권한 RO 로만 드러남 — sa/db_datareader 면 가려짐.)
2. **MSSQL 연결 DB 미고정**: `_connect_mssql` 이 `database=''` 라 로그인 기본 DB(master)로 붙어 `dbo.t`(2-part)가
   "Invalid object name". → MSSQL 은 `default_db` 로 DB 컨텍스트 고정(M-1 엔진별 정합 — 무자격 fail-closed +
   cross-DB 차단이 격리를 담당하므로 DB 고정이 안전). DS_<KEY>_DEFAULT_DB 사실상 필수.
3. **`row_count` vs `rows`**: sys.partitions 컬럼은 `rows`.
4. **`get_table_indexes`/`get_foreign_keys` dialect 미적용**: MySQL `information_schema.STATISTICS`/`KEY_COLUMN_USAGE`
   하드코딩 → Dialect.`table_indexes()`/`foreign_keys_outgoing/incoming()` 추가(MySQL 골든 그대로, MSSQL `sys.*`).

**§3.5 grounding 방언 주입(assistant 가 T-SQL 생성하도록)**: base SYSTEM_PROMPT 는 MySQL(백틱·LIMIT) 가정 →
활성 엔진 mssql 이면 [agent_core.py](../src/agent_core.py) `_MSSQL_DIALECT_GUIDANCE`(TOP/대괄호/스키마 명시 강제/
cross-DB 금지/T-SQL 함수) 를 system prompt 에 주입. (§3.5 는 원래 P7 였으나 assistant 의 실 작동에 필수라 P6 동반.)

**라이브 서비스 검증(deploy 후)**: repo_dbnet 컨테이너가 `172.28.64.1:14330` 도달 가능(실측) → ask-worker/
insight-worker 가 Windows 인스턴스에 붙을 수 있음. P6 배포 + winsql datasource 등록 + product 바인딩 후 web/API
assistant + insight-worker 라이브 검증.

### 11.2 Outside-voice 적대적 보안 재게이트 (REV-20260610-0201, MANDATORY)

[[feedback_outside_voice_for_rbac]] 에 따라 보안경계 변경은 outside-voice 필수. 1차 **REJECT** — 실 인스턴스에서
데이터 탈취 재현. 3 발견 모두 수정 후 2차 **SHIP**.
- **B1 (BLOCKER) — 구조화 도구 2차 SQLi**: `_safe_ident` 가 `]` 미제거 → MSSQL `[schema].[table]` f-string 에서
  `table] UNION SELECT ... FROM sys.sql_logins --` 로 인용 닫고 주입, AST 게이트(allowlist/cross-DB/무자격) 전부
  우회(라이브 데이터+로그인명+cross-DB 탈취 실증). **수정**: `_safe_ident` 가 `[`·`]` 도 제거(단일 chokepoint) →
  주입이 단일 식별자에 갇혀 무력(Invalid object name). 회귀테스트 2종 + 라이브 재검증.
- **M1 (MAJOR) — `sys` 항상-허용 정보유출**: MSSQL `sys` 카탈로그 뷰는 metadata-visibility 라 GRANT 로 안 막힘
  → 최소권한 RO 도 freeform 으로 `sys.sql_logins`(로그인 enumeration)·`sys.server_principals`·`sys.tables`(타스키마
  인벤토리) 조회 가능(설계가 믿은 GRANT backstop 이 sys 엔 부재 — 라이브 실증). **수정**: `MSSQLDialect.metadata_schemas()`
  에서 `sys` 제외(INFORMATION_SCHEMA 만). 구조화 도구는 내부 sys.* 사용하되 결과를 allowlist 필터(무회귀). 잔여:
  INFORMATION_SCHEMA 스키마명 인벤토리는 기존 MySQL 동등 tradeoff(데이터/로그인 아님) — 향후 선택적 하드닝.
- **M2 (MAJOR) — gate fail-closed 가 confirm_heavy 로 자기우회**: MSSQL 하드차단이 `not confirm_heavy` 조건 안에
  있어 LLM 이 `confirm_heavy=true` 로 우회 + 메시지가 우회법 광고. **수정**: 하드차단을 confirm_heavy 조건 밖으로
  이동(추정치 없는 맹목 confirm 은 무력) + 메시지에서 confirm_heavy 안내 제거. MySQL est-기반 게이트는 보존(골든).

## 12. P7 구현 보고 (insight-worker MSSQL — TASK-0203)

Stage 2 P7. insight-worker 가 MSSQL datasource 에서도 인사이트를 생성하도록 introspection 을 dialect-화.

**구현 (핵심은 작았음 — insight.py 8개 introspection 중 2개만 MySQL 전용)**:
- **컬럼 핑거프린트 dialect projection**: insight.py 의 `_compute_table_fingerprint`/`_compute_table_fingerprints_batch`
  가 `COLUMN_TYPE`/`COLUMN_KEY`(SQL Server INFORMATION_SCHEMA 에 부재 → `Invalid column name`) 를 직접 SELECT 했다.
  → `Dialect.fingerprint_column_projection()` 추가(MySQL=골든 그대로, MSSQL=`CHARACTER_MAXIMUM_LENGTH` 로 타입
  상세 대체·KEY 자리 상수). FROM/WHERE(`information_schema.COLUMNS`·`TABLE_SCHEMA`·`ORDINAL_POSITION`)는 ANSI 표준이라
  양 엔진 공통 → insight.py 가 유지(parameterized %s). 나머지 6개 사이트(TABLE_NAME/COLUMN_NAME/DATA_TYPE)는 ANSI
  표준 컬럼만 써 MSSQL 에서 그대로 동작.
- **engine-passing 버그 수정**: `run_insight_cycle` 의 datasource 순회가 `set_active_datasource(_ds_key)` 로 **engine 을
  안 넘겨** `dialects.active()` 가 mysql 로 오인하던 것 → `engine=_ds_coords.get("engine")` 전달.

**livelock 방지(과거 이력)**: write(핑거프린트 생성·저장)·read-back(저장값 비교) 둘 다 datasource 루프의 동일
`set_active_datasource(engine=)` 컨텍스트 안에서 일어나 **동일 projection/engine** 보장 → mismatch·무한재생성 없음.
라이브 단일≡배치 핑거프린트 해시 동일·결정성 STABLE 실증. fact-key 는 P3 의 `ds_fact_key` 로 이미 ds-스코프.

**검증**: 실 SQL Server 2022(`dk_data_release`, CI collation) — 컬럼/스키마/배치 핑거프린트 전부 동작(이전 `COLUMN_TYPE`
실패 해소). MySQL 골든 projection byte-identical. 회귀테스트 3종(`test_multi_datasource.py`). 전체 스위트 RC=0.

**outside-voice 적대적 리뷰(REV-20260611-0202, livelock 중심)**: **SHIP**(BLOCKER 0·MAJOR 0). write·read-back
동일 engine/projection 컨텍스트 + 결정성 + single≡batch 라이브 입증. MINOR 3(후속, 비차단): ① CS/binary collation
서버에서 소문자 `information_schema` 실패 가능(현 대상 CI 무영향) — insight 공유쿼리도 대문자 통일 권고, ② dead code
`_compute_table_fingerprint`(호출 0) 정리, ③ ds scan 실패가 cycle status=ok 라 관측 사각.

**미구현(P7 잔여, 후속)**: ① UI engine 표시(admin datasource 옆 엔진 배지) — 기능 아닌 cosmetic, ② MINOR-1 CS-collation
대문자 통일.
