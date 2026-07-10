"""SQL dialect 어댑터 (멀티 datasource Stage 2 P5).

MySQL / MSSQL 의 introspection·sampling SQL 을 엔진별로 산출한다. tools.py 의 스키마탐색·
샘플 SQL 이 본 모듈을 통해 dialect-aware 가 된다.

**골든 회귀 0**: `MySQLDialect` 는 P5 이전 tools.py 의 SQL 을 *글자 그대로* 산출한다(MySQL 동작
0 변경). `MSSQLDialect` 는 동일 **컬럼 순서**의 T-SQL 을 산출해 tools.py 의 결과 파싱(row[i])이
엔진 무관하게 유지된다.

**보안 주의 (P6 이월)**: 본 모듈은 *SQL 생성*만 담당한다. 식별자 인용은 dialect 별로 하지만,
allowlist(스키마 격리)·sql_guard(AST) 등 **보안 게이트의 dialect 화는 P6** 다. P5 단계에서
MSSQL datasource 를 실제 활성화하면 보안 게이트가 아직 MySQL 방언이라 위험하므로, flag OFF +
미바인딩 상태(shadow)에서만 의미를 갖는다.
"""
from __future__ import annotations

from shared import config as cfg


# ── 사전 부하추정 파서 (엔진별 결과 → 예상 처리 행수) ──────────────────────────
def _parse_explain_rows_product(result_sets) -> int | None:
    """MySQL EXPLAIN 결과 → 테이블별 (rows × filtered/100) 곱 = join 후 예상 카디널리티.

    `filtered`(옵티마이저 선택률 %)를 반영해 잘 인덱싱된 조인의 과대추정(false-positive 게이팅)을
    줄인다. **골든**: 이전 tools.py `_estimate_explain_rows` 의 산식 그대로 — MySQL 동작 0 변경.
    """
    for kind, columns, rows in result_sets:
        if kind != "rows" or not isinstance(columns, list) or not isinstance(rows, list):
            continue
        lcols = [str(c).lower() for c in columns]
        try:
            ridx = lcols.index("rows")
        except ValueError:
            continue
        fidx = lcols.index("filtered") if "filtered" in lcols else None
        product = 1
        seen = False
        for r in rows:
            try:
                v = int(r[ridx])
            except (ValueError, TypeError, IndexError):
                continue
            eff = float(v)
            if fidx is not None:
                try:
                    filt = float(r[fidx])
                    if 0.0 <= filt <= 100.0:
                        eff = v * (filt / 100.0)
                except (ValueError, TypeError, IndexError):
                    pass
            product *= max(1, int(round(eff)))
            seen = True
        if seen:
            return product
    return None


def _parse_showplan_estimate(result_sets) -> int | None:
    """MSSQL `SET SHOWPLAN_ALL` 결과 → 예상 처리 행수.

    추정 실행계획의 각 operator 행에서 `EstimateRows × EstimateExecutions`(중첩루프 inner side
    재실행 반영)를 구해 **최대값**을 "예상 처리 행수"로 산출. MySQL 의 rows×filtered 곱(join 후
    카디널리티)과 산식은 다르나 동일 임계값(AGENT_QUERY_EXPLAIN_ROWS_WARN)으로 무거운 쿼리를
    판정한다(=가장 무거운 단일 operator 가 처리하는 추정 행수). `EstimateRows` 컬럼 부재/전부
    파싱불가 시 None(추정 실패 → caller 가 엔진별 fail-open/closed 결정).

    **알려진 한계 (REV-20260617-0310 M1)**: `EstimateRows` 는 operator 의 *출력* 추정행수이지
    *스캔* 행수가 아니다 → 잔여 술어가 선택적인 비인덱스 풀스캔(많이 읽고 적게 출력)은 과소추정될
    수 있다(무거운 쿼리를 light 로 오판). 이 스캔-부하 공백은 게이트와 무관하게 항상 적용되는 런타임
    시간 cap(tools.py `_apply_query_cap`, `AGENT_QUERY_MAX_EXECUTION_MS`)이 2차 방어로 보완한다.
    더 정확한 비용 기반 게이트(`TotalSubtreeCost` 보조 임계)는 후속 cycle 이월.
    """
    for kind, columns, rows in result_sets:
        if kind != "rows" or not isinstance(columns, list) or not isinstance(rows, list):
            continue
        lcols = [str(c).strip().lower() for c in columns]  # m2: 컬럼명 패딩 견고화
        if "estimaterows" not in lcols:
            continue
        ridx = lcols.index("estimaterows")
        eidx = lcols.index("estimateexecutions") if "estimateexecutions" in lcols else None
        best: int | None = None
        for r in rows:
            try:
                er = float(r[ridx])
            except (ValueError, TypeError, IndexError):
                continue
            ex = 1.0
            if eidx is not None:
                try:
                    ex = float(r[eidx])
                except (ValueError, TypeError, IndexError):
                    ex = 1.0
            if ex < 1.0:
                ex = 1.0
            eff = int(round(er * ex))
            if best is None or eff > best:
                best = eff
        if best is not None:
            return max(0, best)
    return None


class Dialect:
    name = "mysql"
    sqlglot = "mysql"
    # 사전 부하추정 지원 여부. False 엔진은 gate 모드에서 무조건 fail-closed (M-4).
    supports_load_estimate = True
    # gate 모드에서 추정 실패(None) 시 동작. False=fail-open(허용 — MySQL 골든: EXPLAIN 실패는
    # 드물고 정상 작업을 막지 않음). True=fail-closed(차단 — MSSQL: SHOWPLAN 미권한/연결 실패 시
    # 무거운 쿼리 무방어를 막는 보수적 차단, M-4).
    gate_fail_closed_on_estimate_error = False

    # ── 보안: 시스템 스키마 소유권 (P6, DESIGN §3.4 m3 / §4 "차단 스키마 정합") ──
    def system_schemas(self) -> frozenset:
        """사용자 스키마 열거에서 **제외**할 엔진 시스템 스키마 (case-insensitive, lowercase).

        `_is_user_schema`·`search_tables` 의 sys_exclude 가 사용. 누락 시 시스템 카탈로그가
        사용자 스키마로 노출된다.
        """
        raise NotImplementedError

    def metadata_schemas(self) -> frozenset:
        """Product allowlist 와 무관하게 **항상 허용**하는 카탈로그 스키마 (lowercase).

        에이전트가 구조 탐색에 필요한 카탈로그(`information_schema`/`sys` 등) 만. DB 계정 GRANT 가
        2 차 방어. `system_schemas()` 의 부분집합이어야 한다(시스템이면서 카탈로그 조회용).
        """
        raise NotImplementedError

    def system_databases(self) -> frozenset:
        """**DB 단위** 접근모델(TASK-0206)에서 시스템 데이터베이스(catalog) 집합 (lowercase).

        DB allowlist 와 무관하게 항상 catalog 로 허용(완결성). MySQL=메타DB(=system_schemas, schema==database),
        MSSQL=master/model/msdb/tempdb. **주의(M1 보존)**: 시스템 DB 가 catalog 로 허용돼도 `sys`/`guest`/`db_*`
        **스키마**는 `system_schemas()` 로 계속 차단된다 → `master.sys.sql_logins` 는 여전히 거부.
        """
        raise NotImplementedError

    # ── insight 핑거프린트: 컬럼 메타데이터 projection (P7) ──
    def fingerprint_column_projection(self) -> str:
        """insight.py 의 컬럼 핑거프린트용 SELECT projection (information_schema.COLUMNS 기준).

        FROM/WHERE(`information_schema.COLUMNS`·`TABLE_SCHEMA`·`ORDINAL_POSITION`)는 ANSI 표준이라
        MySQL·MSSQL 공통 → insight.py 가 공유하고, **엔진 고유 컬럼만 본 projection 으로 분기**한다
        (MySQL `COLUMN_TYPE`/`COLUMN_KEY` 는 SQL Server INFORMATION_SCHEMA 에 없어 `Invalid column name`).
        반환 컬럼 수는 엔진 무관 5개(코드 대칭, 첫 컬럼=COLUMN_NAME). 핑거프린트는 datasource 별 스코프라
        엔진 간 값 비교를 안 함 — 엔진 내 안정성·변경검출만 필요.
        """
        raise NotImplementedError

    # ── 식별자 인용 ──
    def quote_qualified(self, schema: str, table: str) -> str:
        raise NotImplementedError

    # ── introspection / sampling SQL ──
    def list_schemas_with_counts(self) -> str:
        raise NotImplementedError

    def list_schema_names(self) -> str:
        raise NotImplementedError

    def describe_schema_tables(self, schema: str) -> str:
        raise NotImplementedError

    def describe_columns(self, schema: str, table: str) -> str:
        raise NotImplementedError

    def list_indexes(self, schema: str, table: str) -> str:
        raise NotImplementedError

    def sample(self, schema: str, table: str, limit: int) -> str:
        raise NotImplementedError

    def search_tables(self, keyword: str, sys_exclude: str, where_schema: str) -> str:
        raise NotImplementedError

    # ── 사전 부하추정 / 실행계획 (P6 부하게이트 — dialect 별 처리) ──
    def estimate_load_rows(self, run, sql: str) -> int | None:
        """사전 부하추정: 본 쿼리를 **실행하지 않고** 예상 처리 행수를 산출.

        `run(sql_str) -> result_sets` 는 caller(tools.py)가 주입하는 실행 콜백이다(dialects 가
        db/tools 를 import 하지 않도록 — 계층 보존). 추정 불가/실패 시 None → caller 가 엔진별
        fail-open/closed(`gate_fail_closed_on_estimate_error`)를 결정한다.
        """
        raise NotImplementedError

    def explain_plan(self, run, sql: str):
        """explain_query 도구용 실행계획 result_sets(본 쿼리 미실행). None=미지원/실패."""
        raise NotImplementedError

    # ── get_table_indexes / get_foreign_keys 전용 SQL (P6: 두 도구 dialect 화) ──
    def table_indexes(self, schema: str, table: str) -> str:
        raise NotImplementedError

    def foreign_keys_outgoing(self, schema: str, table: str) -> str:
        raise NotImplementedError

    def foreign_keys_incoming(self, schema: str, table: str) -> str:
        raise NotImplementedError


class MySQLDialect(Dialect):
    name = "mysql"
    sqlglot = "mysql"

    # 골든: tools.py `_METADATA_SCHEMAS` 와 동일 집합(시스템=메타데이터). MySQL 동작 0 변경.
    _SYS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})

    def system_schemas(self) -> frozenset:
        return self._SYS

    def metadata_schemas(self) -> frozenset:
        return self._SYS

    def system_databases(self) -> frozenset:
        # MySQL: schema==database → 시스템 DB = 시스템 스키마.
        return self._SYS

    def fingerprint_column_projection(self) -> str:
        # 골든: insight.py 의 기존 컬럼 목록 그대로(COLUMN_TYPE/COLUMN_KEY 포함).
        return "COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY"

    def quote_qualified(self, schema: str, table: str) -> str:
        return f"`{schema}`.`{table}`"

    def list_schemas_with_counts(self) -> str:
        return """
        SELECT
            s.SCHEMA_NAME,
            COUNT(t.TABLE_NAME) AS table_count,
            COALESCE(SUM(t.TABLE_ROWS), 0) AS approx_total_rows
        FROM information_schema.SCHEMATA s
        LEFT JOIN information_schema.TABLES t
            ON s.SCHEMA_NAME = t.TABLE_SCHEMA
        GROUP BY s.SCHEMA_NAME
        ORDER BY s.SCHEMA_NAME
    """

    def list_schema_names(self) -> str:
        return "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME"

    def describe_schema_tables(self, schema: str) -> str:
        return f"""
        SELECT
            TABLE_NAME,
            TABLE_ROWS AS approx_rows,
            ENGINE,
            TABLE_COMMENT,
            CREATE_TIME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = '{schema}'
        ORDER BY TABLE_NAME
    """

    def describe_columns(self, schema: str, table: str) -> str:
        return f"""
        SELECT
            COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY,
            COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
        ORDER BY ORDINAL_POSITION
    """

    def list_indexes(self, schema: str, table: str) -> str:
        return f"SHOW INDEX FROM `{schema}`.`{table}`"

    def sample(self, schema: str, table: str, limit: int) -> str:
        return f"SELECT * FROM `{schema}`.`{table}` LIMIT {limit}"

    def search_tables(self, keyword: str, sys_exclude: str, where_schema: str) -> str:
        return f"""
        SELECT DISTINCT
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.TABLE_ROWS AS approx_rows,
            t.TABLE_COMMENT
        FROM information_schema.TABLES t
        LEFT JOIN information_schema.COLUMNS c
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        WHERE ({sys_exclude})
            {where_schema}
            AND (
                t.TABLE_NAME LIKE '%{keyword}%'
                OR c.COLUMN_NAME LIKE '%{keyword}%'
                OR t.TABLE_COMMENT LIKE '%{keyword}%'
            )
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        LIMIT 50
    """

    def estimate_load_rows(self, run, sql: str) -> int | None:
        # 골든: EXPLAIN 실행 후 (rows × filtered/100) 곱. 실패(구문/권한/플랜불가)는 None(fail-open).
        try:
            result_sets = run(f"EXPLAIN {sql}")
        except Exception:
            return None
        return _parse_explain_rows_product(result_sets)

    def explain_plan(self, run, sql: str):
        try:
            return run(f"EXPLAIN {sql}")
        except Exception:
            return None

    def table_indexes(self, schema: str, table: str) -> str:
        # 골든: _tool_get_table_indexes 의 기존 SQL 그대로.
        return f"""
        SELECT
            INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX,
            CARDINALITY, INDEX_TYPE, NULLABLE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
        ORDER BY INDEX_NAME, SEQ_IN_INDEX
    """

    def foreign_keys_outgoing(self, schema: str, table: str) -> str:
        return f"""
        SELECT
            CONSTRAINT_NAME, COLUMN_NAME,
            REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '{schema}'
            AND TABLE_NAME = '{table}'
            AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
    """

    def foreign_keys_incoming(self, schema: str, table: str) -> str:
        return f"""
        SELECT
            CONSTRAINT_NAME, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME,
            REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_SCHEMA = '{schema}'
            AND REFERENCED_TABLE_NAME = '{table}'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """

    def probe_relationship_overlap(self, src_schema, src_table, src_col,
                                   tgt_schema, tgt_table, tgt_col, sample, timeout_ms=0):
        """암묵 관계 검증(feature-0016): src 컬럼 표본이 tgt 컬럼에 존재하는 비율.

        반환 SQL 결과 = (sampled, matched) 1행. read-only. 식별자는 백틱 이스케이프(DB-sourced).
        timeout_ms>0 이면 `MAX_EXECUTION_TIME` 옵티마이저 힌트로 statement 시간 상한(운영 DB 폭주 차단).
        """
        def q(x):
            return "`" + str(x).replace("`", "``") + "`"
        n = max(1, min(int(sample), 200))
        src = f"{q(src_schema)}.{q(src_table)}" if src_schema else q(src_table)
        tgt = f"{q(tgt_schema)}.{q(tgt_table)}" if tgt_schema else q(tgt_table)
        hint = f"/*+ MAX_EXECUTION_TIME({int(timeout_ms)}) */ " if int(timeout_ms or 0) > 0 else ""
        return (
            f"SELECT {hint}COUNT(*) AS sampled, "
            f"SUM(CASE WHEN EXISTS (SELECT 1 FROM {tgt} t WHERE t.{q(tgt_col)} = s.v) "
            f"THEN 1 ELSE 0 END) AS matched "
            f"FROM (SELECT {q(src_col)} AS v FROM {src} "
            f"WHERE {q(src_col)} IS NOT NULL LIMIT {n}) s"
        )


class MSSQLDialect(Dialect):
    """MSSQL(T-SQL). 동일 컬럼 순서로 tools.py 결과 파싱(row[i]) 호환.

    식별자 인용 `[schema].[table]`. INFORMATION_SCHEMA 는 SQL Server 도 제공하나 일부 컬럼
    의미가 달라 컬럼 별칭/순서를 MySQL 산출과 동일하게 맞춘다. 행수 추정은 **sys.partitions.rows**
    (P6: 최소권한 RO 가 metadata-visibility 로 접근 — sys.dm_db_partition_stats DMV 는 VIEW DATABASE
    STATE 권한이 필요해 db_datareader 금지/스키마 GRANT-only RO 에서 거부됨).

    **사전 부하추정 (TASK-0299)**: EXPLAIN 구문은 없으나 `SET SHOWPLAN_ALL ON` 으로 본 쿼리를
    실행하지 않고 추정 실행계획을 받아 예상 처리 행수를 산출한다(MySQL EXPLAIN 등가). RO role 에
    `GRANT SHOWPLAN` 필요(데이터 읽기 권한 아님 — 최소권한과 양립; bin/datasource-mssql-ro-bootstrap*.sql).
    SHOWPLAN 미권한/연결 실패 시 추정 불가 → gate 모드 fail-closed(`gate_fail_closed_on_estimate_error`).
    """
    name = "mssql"
    sqlglot = "tsql"
    # SET SHOWPLAN_ALL 로 사전 부하추정 지원(TASK-0299). 추정 실패 시 gate 모드 fail-closed.
    supports_load_estimate = True
    gate_fail_closed_on_estimate_error = True

    # 사용자 스키마 열거에서 제외: sys/INFORMATION_SCHEMA(카탈로그) + guest + 고정 db_* 역할 스키마.
    # **dbo 는 제외하지 않는다** — MSSQL 의 기본 사용자 스키마(대부분의 사용자 테이블 거처)라
    # 제외하면 정상 테이블이 통째로 차단된다.
    _SYS = frozenset({
        "sys", "information_schema", "guest",
        "db_owner", "db_accessadmin", "db_securityadmin", "db_ddladmin",
        "db_backupoperator", "db_datareader", "db_datawriter",
        "db_denydatareader", "db_denydatawriter",
    })
    # 항상 허용(LLM freeform execute_sql 의 카탈로그 조회)은 **INFORMATION_SCHEMA 만**.
    # **`sys` 는 항상-허용에서 제외** (REV-0201 M1): MSSQL `sys` 카탈로그 뷰는 metadata-visibility 라
    # GRANT 로 막히지 않아, 최소권한 RO 도 `sys.sql_logins`(로그인 enumeration)·`sys.server_principals`·
    # `sys.database_principals`·`sys.tables`(allowlist 밖 스키마 인벤토리) 를 freeform 으로 읽을 수 있다
    # (라이브 실증 — 설계가 믿은 "GRANT backstop" 이 sys 영역엔 부재). 구조 탐색은 list_schemas/
    # describe_* 구조화 도구(내부적으로 sys.* 를 쓰되 결과를 allowlist 로 필터)가 담당하므로, freeform
    # 의 sys.* 직접 조회는 차단해도 기능 손실이 없다. db_* 역할 스키마도 metadata 아님.
    _META = frozenset({"information_schema"})

    # MSSQL 시스템 데이터베이스(catalog 차원). DB allowlist 무관 항상 catalog 허용(완결성). 단 그 안의
    # `sys`/`guest`/`db_*` 스키마는 `_SYS`(system_schemas)로 계속 차단 → master.sys.sql_logins 거부(M1 보존).
    _SYS_DB = frozenset({"master", "model", "msdb", "tempdb"})

    def system_schemas(self) -> frozenset:
        return self._SYS

    def metadata_schemas(self) -> frozenset:
        return self._META

    def system_databases(self) -> frozenset:
        return self._SYS_DB

    def fingerprint_column_projection(self) -> str:
        # MSSQL INFORMATION_SCHEMA.COLUMNS 에는 COLUMN_TYPE/COLUMN_KEY 가 없다 → DATA_TYPE +
        # CHARACTER_MAXIMUM_LENGTH 로 타입 상세를 대체하고, KEY 자리는 상수(핑거프린트는 컬럼 추가/삭제/
        # 타입변경 검출이 주목적이라 PK 표식 생략 무해). 컬럼 수 5개로 MySQL 과 대칭(insight 가 위치로 읽음).
        return (
            "COLUMN_NAME, DATA_TYPE, "
            "CAST(ISNULL(CHARACTER_MAXIMUM_LENGTH, -1) AS NVARCHAR(20)) AS COLUMN_TYPE, "
            "IS_NULLABLE, CAST('' AS NVARCHAR(1)) AS COLUMN_KEY"
        )

    def quote_qualified(self, schema: str, table: str) -> str:
        return f"[{schema}].[{table}]"

    def list_schemas_with_counts(self) -> str:
        # 컬럼 순서: schema_name, table_count, approx_total_rows (MySQL 과 동일)
        return """
        SELECT
            s.name AS SCHEMA_NAME,
            COUNT(t.object_id) AS table_count,
            COALESCE(SUM(CAST(p.rows AS BIGINT)), 0) AS approx_total_rows
        FROM sys.schemas s
        LEFT JOIN sys.tables t ON t.schema_id = s.schema_id
        LEFT JOIN sys.partitions p
            ON p.object_id = t.object_id AND p.index_id IN (0, 1)
        GROUP BY s.name
        ORDER BY s.name
    """

    def list_schema_names(self) -> str:
        return "SELECT name AS SCHEMA_NAME FROM sys.schemas ORDER BY name"

    def describe_schema_tables(self, schema: str) -> str:
        # 컬럼: table_name, approx_rows, engine, comment, create_time (MySQL 순서)
        return f"""
        SELECT
            t.name AS TABLE_NAME,
            COALESCE(SUM(CAST(p.rows AS BIGINT)), 0) AS approx_rows,
            'mssql' AS ENGINE,
            CAST(ep.value AS NVARCHAR(200)) AS TABLE_COMMENT,
            t.create_date AS CREATE_TIME
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        LEFT JOIN sys.partitions p
            ON p.object_id = t.object_id AND p.index_id IN (0, 1)
        LEFT JOIN sys.extended_properties ep
            ON ep.major_id = t.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
        WHERE s.name = '{schema}'
        GROUP BY t.name, t.create_date, CAST(ep.value AS NVARCHAR(200))
        ORDER BY t.name
    """

    def describe_columns(self, schema: str, table: str) -> str:
        # 컬럼: COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
        # MSSQL 에 COLUMN_KEY/EXTRA/COMMENT 직접 동치 없음 → 가용 정보만, 나머지 빈 문자열(순서 유지).
        return f"""
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE + COALESCE('(' + CAST(c.CHARACTER_MAXIMUM_LENGTH AS NVARCHAR(20)) + ')', '') AS COLUMN_TYPE,
            c.IS_NULLABLE,
            '' AS COLUMN_KEY,
            CAST(c.COLUMN_DEFAULT AS NVARCHAR(200)) AS COLUMN_DEFAULT,
            '' AS EXTRA,
            '' AS COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_SCHEMA = '{schema}' AND c.TABLE_NAME = '{table}'
        ORDER BY c.ORDINAL_POSITION
    """

    def list_indexes(self, schema: str, table: str) -> str:
        # SHOW INDEX 가 소비하는 위치(row[1]=non_unique, [2]=key_name, [3]=seq, [4]=column, [6]=cardinality)
        # 에 맞춰 7 컬럼을 정렬: (NULL, non_unique, index_name, seq, column, NULL, NULL).
        return f"""
        SELECT
            NULL AS Table_,
            CASE WHEN i.is_unique = 1 THEN 0 ELSE 1 END AS Non_unique,
            i.name AS Key_name,
            ic.key_ordinal AS Seq_in_index,
            col.name AS Column_name,
            NULL AS Collation,
            NULL AS Cardinality
        FROM sys.indexes i
        JOIN sys.tables t ON t.object_id = i.object_id
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns col ON col.object_id = ic.object_id AND col.column_id = ic.column_id
        WHERE s.name = '{schema}' AND t.name = '{table}' AND i.type > 0
        ORDER BY i.name, ic.key_ordinal
    """

    def sample(self, schema: str, table: str, limit: int) -> str:
        return f"SELECT TOP {int(limit)} * FROM [{schema}].[{table}]"

    def search_tables(self, keyword: str, sys_exclude: str, where_schema: str) -> str:
        # sys_exclude/where_schema 는 MySQL 의 `t.TABLE_SCHEMA` 별칭 기준 문자열이라 그대로 호환
        # (INFORMATION_SCHEMA.TABLES 의 TABLE_SCHEMA 컬럼 동일). TOP 50 으로 LIMIT 대체.
        return f"""
        SELECT DISTINCT TOP 50
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            CAST(NULL AS BIGINT) AS approx_rows,
            CAST('' AS NVARCHAR(200)) AS TABLE_COMMENT
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN INFORMATION_SCHEMA.COLUMNS c
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        WHERE ({sys_exclude})
            {where_schema}
            AND (
                t.TABLE_NAME LIKE '%{keyword}%'
                OR c.COLUMN_NAME LIKE '%{keyword}%'
            )
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
    """

    def _showplan(self, run, sql: str):
        """`SET SHOWPLAN_ALL ON` → sql(미실행, 추정 실행계획 반환) → `OFF`. result_sets | None.

        **단일 result-set 의존 (REV-20260617-0310 m1)**: SHOWPLAN_ALL 은 본 SELECT 에 대해 operator
        당 1행을 가진 *단일* result set 을 반환하므로, `nextset()` 미호출(db.execute_sql)인 현 수집기와
        호환된다. 다른 result-set 형태가 오면 estimaterows 컬럼 부재로 None(추정 실패 → MSSQL gate
        fail-closed=안전 방향). sql_guard 가 단일 SELECT/CTE 만 허용해 다중 result-set SQL 은 도달 불가.

        **세션 poison 방지 (Codex-7, DESIGN §"pool 세션누출")**: conn 은 run 전체 공유라 SHOWPLAN_ALL
        이 켜진 채 남으면 *이후 실쿼리가 데이터 대신 plan 을 반환하는 조용한 오염*이 된다. ON 이 성공한
        경우 OFF 를 `finally` 로 항상 보장한다(조회가 예외로 끝나도 복구). OFF 자체가 실패하면 conn 이
        끊긴 것 — 이후 실쿼리도 loud 하게 실패하므로 silent plan-as-data 는 발생하지 않는다.
        ON 실패(SHOWPLAN 미권한 등)·조회 실패 시 None(추정 불가).
        """
        showplan_on = False
        try:
            run("SET SHOWPLAN_ALL ON")
            showplan_on = True
            return run(sql)
        except Exception:
            return None
        finally:
            if showplan_on:
                try:
                    run("SET SHOWPLAN_ALL OFF")
                except Exception:
                    # conn 세션 복구 실패(끊긴 conn 추정). 이후 실쿼리가 loud 실패 → silent 오염 없음.
                    pass

    def estimate_load_rows(self, run, sql: str) -> int | None:
        result_sets = self._showplan(run, sql)
        if result_sets is None:
            return None
        return _parse_showplan_estimate(result_sets)

    def explain_plan(self, run, sql: str):
        return self._showplan(run, sql)

    def table_indexes(self, schema: str, table: str) -> str:
        # 컬럼 순서/이름을 MySQL 산출과 동일하게(INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX,
        # CARDINALITY, INDEX_TYPE, NULLABLE). CARDINALITY 직접 동치 없음 → NULL.
        return f"""
        SELECT
            i.name AS INDEX_NAME,
            CASE WHEN i.is_unique = 1 THEN 0 ELSE 1 END AS NON_UNIQUE,
            col.name AS COLUMN_NAME,
            ic.key_ordinal AS SEQ_IN_INDEX,
            CAST(NULL AS BIGINT) AS CARDINALITY,
            i.type_desc AS INDEX_TYPE,
            CASE WHEN col.is_nullable = 1 THEN 'YES' ELSE 'NO' END AS NULLABLE
        FROM sys.indexes i
        JOIN sys.tables t ON t.object_id = i.object_id
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns col ON col.object_id = ic.object_id AND col.column_id = ic.column_id
        WHERE s.name = '{schema}' AND t.name = '{table}' AND i.type > 0
        ORDER BY i.name, ic.key_ordinal
    """

    def foreign_keys_outgoing(self, schema: str, table: str) -> str:
        # 컬럼: CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        return f"""
        SELECT
            fk.name AS CONSTRAINT_NAME,
            pc.name AS COLUMN_NAME,
            rs.name AS REFERENCED_TABLE_SCHEMA,
            rt.name AS REFERENCED_TABLE_NAME,
            rc.name AS REFERENCED_COLUMN_NAME
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.tables pt ON pt.object_id = fk.parent_object_id
        JOIN sys.schemas ps ON ps.schema_id = pt.schema_id
        JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
        JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id
        JOIN sys.schemas rs ON rs.schema_id = rt.schema_id
        JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
        WHERE ps.name = '{schema}' AND pt.name = '{table}'
        ORDER BY fk.name, fkc.constraint_column_id
    """

    def foreign_keys_incoming(self, schema: str, table: str) -> str:
        # 컬럼: CONSTRAINT_NAME, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, REFERENCED_COLUMN_NAME
        return f"""
        SELECT
            fk.name AS CONSTRAINT_NAME,
            ps.name AS TABLE_SCHEMA,
            pt.name AS TABLE_NAME,
            pc.name AS COLUMN_NAME,
            rc.name AS REFERENCED_COLUMN_NAME
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.tables pt ON pt.object_id = fk.parent_object_id
        JOIN sys.schemas ps ON ps.schema_id = pt.schema_id
        JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
        JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id
        JOIN sys.schemas rs ON rs.schema_id = rt.schema_id
        JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
        WHERE rs.name = '{schema}' AND rt.name = '{table}'
        ORDER BY ps.name, pt.name
    """

    def probe_relationship_overlap(self, src_schema, src_table, src_col,
                                   tgt_schema, tgt_table, tgt_col, sample, timeout_ms=0):
        """암묵 관계 검증(feature-0016): src 컬럼 표본이 tgt 컬럼에 존재하는 비율.

        반환 SQL 결과 = (sampled, matched) 1행. read-only. 식별자는 대괄호 이스케이프(']' 이중화).
        timeout_ms>0 이면 `SET LOCK_TIMEOUT` 로 락 대기 상한(운영 DB blocking hang 차단 — MSSQL 은
        per-statement CPU timeout 구문이 없어 락 대기를 상한. 표본 상한 TOP {n} 이 CPU 폭주를 2차 제한).

        §55(REQ-20260706 ②) 스키마-slot 해석: 본 플랫폼의 MSSQL 관계 row 스키마-slot 은 **DB(catalog)명**
        (ADR-007 규약 — effective schema=DB명, 실제 스키마는 dbo 가정). 따라서 qualifier 는 3-part
        `[db].[dbo].[table]` 로 조립해 **같은 서버의 다른 DB 간(cross-DB) 프로브**를 한 연결에서 실행
        가능하게 한다(기존 2-part `[db].[table]` 은 db 를 스키마로 오해석 — probe_and_reinforce 가
        qualifier 를 벗겨 회피하던 제약의 근본 해소). slot 비면 연결 DB 기본 스키마 해석(불변).
        예외: slot 이 'dbo'(레거시 대화학습 행 — 2-part `dbo.T` 파싱 유래)면 실 스키마로 보고 2-part
        유지 — `[dbo].[dbo].[T]` 오조립이 "Database 'dbo'" missing-object → 실관계 오파단을 막는다.
        한계: dbo 외 실스키마 테이블은 관계 파이프라인 전반이 미추적(플랫폼 가정)."""
        def q(x):
            return "[" + str(x).replace("]", "]]") + "]"
        def qual(sch, tbl):
            s = str(sch or "").strip()
            if not s:
                return q(tbl)
            if s.lower() == "dbo":
                return f"{q(s)}.{q(tbl)}"          # 실 스키마(레거시 slot) — 2-part 유지
            return f"{q(s)}.[dbo].{q(tbl)}"        # 스키마-slot=DB명(ADR-007) — 3-part cross-DB
        n = max(1, min(int(sample), 200))
        src = qual(src_schema, src_table)
        tgt = qual(tgt_schema, tgt_table)
        prefix = f"SET LOCK_TIMEOUT {int(timeout_ms)}; " if int(timeout_ms or 0) > 0 else ""
        # rel-selfheal 라이브 후속(probe-mssqlfix): MSSQL 은 집계식이 서브쿼리를 포함할 수 없다
        # (오류 130 "Cannot perform an aggregate function on an expression containing an
        # aggregate or a subquery") — SUM(CASE WHEN EXISTS ...) 가 라이브에서 전면 실패했다
        # (파이프라인 정지 동안 미노출이던 잠복 결함). CASE/EXISTS 를 파생 테이블 안으로
        # 내리고 바깥에서 SUM(단순 컬럼) 집계로 재작성 — 의미(표본 n 중 겹침 수) 동일.
        return (
            f"{prefix}SELECT COUNT(*) AS sampled, SUM(s.m) AS matched FROM ("
            f"SELECT TOP {n} CASE WHEN EXISTS "
            f"(SELECT 1 FROM {tgt} t WHERE t.{q(tgt_col)} = s0.{q(src_col)}) "
            f"THEN 1 ELSE 0 END AS m "
            f"FROM {src} s0 WHERE s0.{q(src_col)} IS NOT NULL) s"
        )


_MYSQL = MySQLDialect()
_MSSQL = MSSQLDialect()


def get(engine: str | None) -> Dialect:
    return _MSSQL if str(engine or "mysql").strip().lower() == "mssql" else _MYSQL


def active() -> Dialect:
    """현재 컨텍스트의 활성 datasource 엔진에 맞는 dialect (기본 mysql)."""
    return get(cfg.get_active_datasource_engine())
