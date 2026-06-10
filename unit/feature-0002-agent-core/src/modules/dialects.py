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

from . import config as cfg


class Dialect:
    name = "mysql"
    sqlglot = "mysql"

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

    def explain(self, sql: str) -> str | None:
        raise NotImplementedError


class MySQLDialect(Dialect):
    name = "mysql"
    sqlglot = "mysql"

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

    def explain(self, sql: str) -> str | None:
        return f"EXPLAIN {sql}"


class MSSQLDialect(Dialect):
    """MSSQL(T-SQL). 동일 컬럼 순서로 tools.py 결과 파싱(row[i]) 호환.

    식별자 인용 `[schema].[table]`. INFORMATION_SCHEMA 는 SQL Server 도 제공하나 일부 컬럼
    의미가 달라 컬럼 별칭/순서를 MySQL 산출과 동일하게 맞춘다. 행수 추정은 sys.dm_db_partition_stats.
    """
    name = "mssql"
    sqlglot = "tsql"

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
        LEFT JOIN sys.dm_db_partition_stats p
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
        LEFT JOIN sys.dm_db_partition_stats p
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

    def explain(self, sql: str) -> str | None:
        # MSSQL 은 EXPLAIN 구문 없음. P6 의 부하게이트가 dialect 별로 처리(SHOWPLAN 또는 fail-closed).
        # P5 단계에서는 None → caller(부하게이트)가 best-effort skip (보수화는 P6).
        return None


_MYSQL = MySQLDialect()
_MSSQL = MSSQLDialect()


def get(engine: str | None) -> Dialect:
    return _MSSQL if str(engine or "mysql").strip().lower() == "mssql" else _MYSQL


def active() -> Dialect:
    """현재 컨텍스트의 활성 datasource 엔진에 맞는 dialect (기본 mysql)."""
    return get(cfg.get_active_datasource_engine())
