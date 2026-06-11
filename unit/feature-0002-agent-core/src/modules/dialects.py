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
    # 사전 부하추정(EXPLAIN rows) 지원 여부. False 엔진(MSSQL)은 gate 모드에서 fail-closed (M-4).
    supports_load_estimate = True

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

    def explain(self, sql: str) -> str | None:
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

    def explain(self, sql: str) -> str | None:
        return f"EXPLAIN {sql}"

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


class MSSQLDialect(Dialect):
    """MSSQL(T-SQL). 동일 컬럼 순서로 tools.py 결과 파싱(row[i]) 호환.

    식별자 인용 `[schema].[table]`. INFORMATION_SCHEMA 는 SQL Server 도 제공하나 일부 컬럼
    의미가 달라 컬럼 별칭/순서를 MySQL 산출과 동일하게 맞춘다. 행수 추정은 **sys.partitions.rows**
    (P6: 최소권한 RO 가 metadata-visibility 로 접근 — sys.dm_db_partition_stats DMV 는 VIEW DATABASE
    STATE 권한이 필요해 db_datareader 금지/스키마 GRANT-only RO 에서 거부됨).
    """
    name = "mssql"
    sqlglot = "tsql"
    # EXPLAIN 구문이 없어 사전 부하추정 불가 → gate 모드에서 fail-closed (M-4).
    supports_load_estimate = False

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

    def system_schemas(self) -> frozenset:
        return self._SYS

    def metadata_schemas(self) -> frozenset:
        return self._META

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

    def explain(self, sql: str) -> str | None:
        # MSSQL 은 EXPLAIN 구문 없음. P6 의 부하게이트가 dialect 별로 처리(SHOWPLAN 또는 fail-closed).
        # P5 단계에서는 None → caller(부하게이트)가 best-effort skip (보수화는 P6).
        return None

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


_MYSQL = MySQLDialect()
_MSSQL = MSSQLDialect()


def get(engine: str | None) -> Dialect:
    return _MSSQL if str(engine or "mysql").strip().lower() == "mssql" else _MYSQL


def active() -> Dialect:
    """현재 컨텍스트의 활성 datasource 엔진에 맞는 dialect (기본 mysql)."""
    return get(cfg.get_active_datasource_engine())
