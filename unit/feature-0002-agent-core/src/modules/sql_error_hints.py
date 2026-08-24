"""SQL 실행 오류의 **표적** 진단 힌트 — 자가수정 루프(agent_core `_sql_reflection_nudge`)의 근거.

동기 (라이브 실측 2026-08-24, 대화 `20260824085807-a761f842` step 6·8):
  LLM 이 `SELECT NOW() as current_time, DATE_SUB(NOW(), INTERVAL 1 YEAR) as one_year_ago, ...`
  를 실행 → MySQL 1064. `current_time` 은 MySQL **예약어**라 인용 없이 별칭으로 쓸 수 없다.
  엔진은 `near 'current_time, ...'` 로 실패 지점을 **정확히 지목**했으나, 당시 자가수정 넛지는
  그 정보를 버리고 "SQL 구문(따옴표·괄호·예약어·방언)을 점검해 교정하라" 는 일반 문구만 줬다.
  모델은 두 번의 재시도에서 `@@time_zone` 제거·`as`→`AS` 같은 **무관한 부분만** 바꾸고 범인
  토큰을 유지해 같은 오류를 반복했고, 상한 소진 후 사용자에게
  "이 DB 연결에서 DATE_SUB(), UNIX_TIMESTAMP() 등의 날짜/시간 함수가 작동하지 않습니다"
  라는 **검증되지 않은 엔진 제약**을 사실로 단정하고 그 위에 삭제 방안 3종을 세웠다.

본 모듈은 그 세 결함을 각각 닫는다:
  (1) `extract_error_focus` — 엔진이 지목한 실패 지점(첫 토큰)을 추출해 넛지가 범인을 지목한다.
  (2) `reserved_identifier_note` — focus 가 예약어면 인용/개명 처방을 준다(1064 최빈 원인).
  (3) `error_signature` — 분류+focus 로 **동일 실패 반복**을 감지해 접근 전환을 요구한다.

순수 함수 모듈이다 — DB·LLM·config 의존이 없어 단위 테스트가 라이브 없이 성립한다.
"""
from __future__ import annotations

import re

__all__ = [
    "MYSQL_RESERVED",
    "TSQL_RESERVED",
    "classify_error",
    "error_signature",
    "extract_error_focus",
    "reserved_identifier_note",
    "reserved_words_for",
    "targeted_hint",
]

# MySQL 8.0 예약어 (공식 "Keywords and Reserved Words" 중 reserved). 별칭·컬럼명으로
# 인용 없이 쓰면 1064 를 낸다 — 라이브 실패의 최빈 원인이라 전량을 싣는다(정적 데이터).
MYSQL_RESERVED = frozenset("""
ACCESSIBLE ADD ALL ALTER ANALYZE AND AS ASC ASENSITIVE BEFORE BETWEEN BIGINT BINARY BLOB BOTH BY
CALL CASCADE CASE CHANGE CHAR CHARACTER CHECK COLLATE COLUMN CONDITION CONSTRAINT CONTINUE CONVERT
CREATE CROSS CUBE CUME_DIST CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER CURSOR
DATABASE DATABASES DAY_HOUR DAY_MICROSECOND DAY_MINUTE DAY_SECOND DEC DECIMAL DECLARE DEFAULT
DELAYED DELETE DENSE_RANK DESC DESCRIBE DETERMINISTIC DISTINCT DISTINCTROW DIV DOUBLE DROP DUAL
EACH ELSE ELSEIF EMPTY ENCLOSED ESCAPED EXCEPT EXISTS EXIT EXPLAIN FALSE FETCH FIRST_VALUE FLOAT
FLOAT4 FLOAT8 FOR FORCE FOREIGN FROM FULLTEXT FUNCTION GENERATED GET GRANT GROUP GROUPING GROUPS
HAVING HIGH_PRIORITY HOUR_MICROSECOND HOUR_MINUTE HOUR_SECOND IF IGNORE IN INDEX INFILE INNER INOUT
INSENSITIVE INSERT INT INT1 INT2 INT3 INT4 INT8 INTEGER INTERVAL INTO IO_AFTER_GTIDS IO_BEFORE_GTIDS
IS ITERATE JOIN JSON_TABLE KEY KEYS KILL LAG LAST_VALUE LATERAL LEAD LEADING LEAVE LEFT LIKE LIMIT
LINEAR LINES LOAD LOCALTIME LOCALTIMESTAMP LOCK LONG LONGBLOB LONGTEXT LOOP LOW_PRIORITY MASTER_BIND
MASTER_SSL_VERIFY_SERVER_CERT MATCH MAXVALUE MEDIUMBLOB MEDIUMINT MEDIUMTEXT MIDDLEINT
MINUTE_MICROSECOND MINUTE_SECOND MOD MODIFIES NATURAL NOT NO_WRITE_TO_BINLOG NTH_VALUE NTILE NULL
NUMERIC OF ON OPTIMIZE OPTIMIZER_COSTS OPTION OPTIONALLY OR ORDER OUT OUTER OUTFILE OVER PARTITION
PERCENT_RANK PRECISION PRIMARY PROCEDURE PURGE RANGE RANK READ READS READ_WRITE REAL RECURSIVE
REFERENCES REGEXP RELEASE RENAME REPEAT REPLACE REQUIRE RESIGNAL RESTRICT RETURN REVOKE RIGHT RLIKE
ROW ROWS ROW_NUMBER SCHEMA SCHEMAS SECOND_MICROSECOND SELECT SENSITIVE SEPARATOR SET SHOW SIGNAL
SMALLINT SPATIAL SPECIFIC SQL SQLEXCEPTION SQLSTATE SQLWARNING SQL_BIG_RESULT SQL_CALC_FOUND_ROWS
SQL_SMALL_RESULT SSL STARTING STORED STRAIGHT_JOIN SYSTEM TABLE TERMINATED THEN TINYBLOB TINYINT
TINYTEXT TO TRAILING TRIGGER TRUE UNDO UNION UNIQUE UNLOCK UNSIGNED UPDATE USAGE USE USING UTC_DATE
UTC_TIME UTC_TIMESTAMP VALUES VARBINARY VARCHAR VARCHARACTER VARYING VIRTUAL WHEN WHERE WHILE WINDOW
WITH WRITE XOR YEAR_MONTH ZEROFILL
""".split())

# SQL Server (T-SQL) 예약어. MSSQL datasource 에서는 대괄호 인용이 처방이다.
TSQL_RESERVED = frozenset("""
ADD ALL ALTER AND ANY AS ASC AUTHORIZATION BACKUP BEGIN BETWEEN BREAK BROWSE BULK BY CASCADE CASE
CHECK CHECKPOINT CLOSE CLUSTERED COALESCE COLLATE COLUMN COMMIT COMPUTE CONSTRAINT CONTAINS
CONTAINSTABLE CONTINUE CONVERT CREATE CROSS CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP
CURRENT_USER CURSOR DATABASE DBCC DEALLOCATE DECLARE DEFAULT DELETE DENY DESC DISK DISTINCT
DISTRIBUTED DOUBLE DROP DUMP ELSE END ERRLVL ESCAPE EXCEPT EXEC EXECUTE EXISTS EXIT EXTERNAL FETCH
FILE FILLFACTOR FOR FOREIGN FREETEXT FREETEXTTABLE FROM FULL FUNCTION GOTO GRANT GROUP HAVING
HOLDLOCK IDENTITY IDENTITYCOL IDENTITY_INSERT IF IN INDEX INNER INSERT INTERSECT INTO IS JOIN KEY
KILL LEFT LIKE LINENO LOAD MERGE NATIONAL NOCHECK NONCLUSTERED NOT NULL NULLIF OF OFF OFFSETS ON
OPEN OPENDATASOURCE OPENQUERY OPENROWSET OPENXML OPTION OR ORDER OUTER OVER PERCENT PIVOT PLAN
PRECISION PRIMARY PRINT PROC PROCEDURE PUBLIC RAISERROR READ READTEXT RECONFIGURE REFERENCES
REPLICATION RESTORE RESTRICT RETURN REVERT REVOKE RIGHT ROLLBACK ROWCOUNT ROWGUIDCOL RULE SAVE
SCHEMA SECURITYAUDIT SELECT SESSION_USER SET SETUSER SHUTDOWN SOME STATISTICS SYSTEM_USER TABLE
TABLESAMPLE TEXTSIZE THEN TO TOP TRAN TRANSACTION TRIGGER TRUNCATE TRY_CONVERT TSEQUAL UNION UNIQUE
UNPIVOT UPDATE UPDATETEXT USE USER VALUES VARYING VIEW WAITFOR WHEN WHERE WHILE WITH WRITETEXT
""".split())

# 엔진이 지목한 실패 지점. MySQL 1064: "... right syntax to use near 'current_time, ...' at line 1"
# MSSQL 102: "Incorrect syntax near 'current_time'." — 두 형태 모두 near 뒤 인용구가 **잔여 텍스트의
# 시작점**이라 그 첫 토큰이 범인이다.
_NEAR_RE = re.compile(r"near\s+['\"`]([^'\"`]{1,400})", re.IGNORECASE)
_LEADING_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*")
_UNKNOWN_COL_RE = re.compile(
    r"Unknown column\s+['\"`]([^'\"`]+)['\"`]|Invalid column name\s+['\"`]([^'\"`]+)['\"`]",
    re.IGNORECASE,
)
_UNKNOWN_TBL_RE = re.compile(
    r"Table\s+['\"`]([^'\"`]+)['\"`]\s+does(?:\s+not|n't)\s+exist"
    r"|Unknown table\s+['\"`]([^'\"`]+)['\"`]"
    r"|Invalid object name\s+['\"`]([^'\"`]+)['\"`]",
    re.IGNORECASE,
)

# focus 는 **비신뢰 경로**로 들어온다 — DB 오류 메시지의 식별자는 LLM 이 쓴 SQL(사용자 문구가
# 섞일 수 있다)에서 그대로 반사되고, 오류 원문은 `_datamark_untrusted` 로 구획되는 데이터다.
# 그런데 넛지는 그 구획 **밖**(코드-권위 영역)에 붙으므로, focus 를 정제하지 않으면 임의 문장이
# 코드-권위 텍스트로 승격된다 — 저장소의 신뢰경계(§`_INJECTION_GUARD_NOTICE`)를 우회하는 표면이다.
# 정제 규칙: 첫 공백 전까지 + 식별자 문자만 + 길이 상한. 식별자를 지목하는 데 필요한 정보는
# 모두 보존되고(공백 없는 토큰), 문장 삽입은 구조적으로 불가능해진다.
_FOCUS_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_$.\[\]]")
_FOCUS_MAX_CHARS = 64


def _sanitize_focus(token: str) -> str:
    """focus 후보를 코드-권위 영역에 실어도 안전한 형태로 정제한다."""
    text = str(token or "").strip()
    if not text:
        return ""
    head = text.split()[0] if text.split() else ""   # 첫 공백 전까지 — 문장 삽입 차단
    return _FOCUS_UNSAFE_RE.sub("", head)[:_FOCUS_MAX_CHARS]


def classify_error(result: "str | None") -> str:
    """오류 문자열의 대분류. agent_core `_classify_sql_error` 의 정본 구현."""
    r = (result or "").lower()
    if "syntax" in r or "구문" in r:  # syntax 우선(REV N2: 'near table' 오분류 방지)
        return "syntax"
    if "unknown column" in r or "invalid column name" in r or "컬럼" in r or "column" in r:
        return "unknown-column"
    if ("doesn't exist" in r or "unknown table" in r or "invalid object name" in r
            or "테이블" in r or "table" in r):
        return "unknown-table"
    return "execution"


def extract_error_focus(result: "str | None") -> str:
    """엔진이 지목한 **실패 지점의 첫 토큰**을 뽑는다 (없으면 "").

    `near '<잔여 SQL>'` 의 잔여 텍스트는 파서가 멈춘 지점부터이므로 그 선두 토큰이 범인이다.
    선두가 식별자가 아니면(`)` `,` 등) 그 기호 자체를 짧게 돌려준다 — 괄호·쉼표 오류도
    "어디를 볼 것인가" 를 지목해야 무관한 부분을 고치는 헛발질을 막는다.
    near 절이 없는 오류(unknown column/table)는 그 이름을 focus 로 쓴다.
    """
    text = str(result or "")
    m = _NEAR_RE.search(text)
    if m:
        frag = m.group(1).lstrip()
        if frag:
            im = _LEADING_IDENT_RE.match(frag)
            if im:
                return im.group(0)
            # 기호류(`)` `,` 등) — 공백 전까지만, 과도한 길이 방지. 정제는 적용하지 않는다:
            # 기호 자체가 지목 대상이라 식별자 필터로 지우면 정보가 사라진다. 대신 12자 상한과
            # 공백 없음이 문장 삽입을 막는다.
            return (frag.split()[0][:12] if frag.split() else frag[:12])
    for rx in (_UNKNOWN_COL_RE, _UNKNOWN_TBL_RE):
        m2 = rx.search(text)
        if m2:
            for g in m2.groups():
                if g:
                    # 이 경로의 캡처는 인용부호 사이 **임의 길이·공백 포함** 문자열이다 —
                    # 반드시 정제한다(위 `_sanitize_focus` 주석 참조).
                    return _sanitize_focus(g)
    return ""


def error_signature(result: "str | None") -> str:
    """**동일 실패 반복** 판정용 시그니처 (분류 + 실패 지점).

    실측 사례의 step 6·8 은 SQL 텍스트가 달랐지만(`@@time_zone` 유무, `as`/`AS`) 시그니처는
    둘 다 `syntax|current_time` 이다 — SQL 을 바꾼 것이 아니라 **범인을 안 바꾼** 상태이며,
    이 동일성이 곧 "무관한 부분만 고쳤다" 는 신호다.
    """
    if not (result or "").strip():
        return ""
    return f"{classify_error(result)}|{extract_error_focus(result).lower()}"


def reserved_words_for(dialect: "str | None") -> frozenset:
    """활성 방언의 예약어 집합. 미상이면 MySQL(본 프로젝트 기본 엔진)."""
    return TSQL_RESERVED if str(dialect or "").lower() in ("tsql", "mssql") else MYSQL_RESERVED


def reserved_identifier_note(focus: str, dialect: "str | None" = None) -> str:
    """focus 토큰이 예약어면 인용/개명 처방을 돌려준다 (아니면 "")."""
    token = str(focus or "").strip()
    if not token or not token[0].isalpha() and token[0] != "_":
        return ""
    if token.upper() not in reserved_words_for(dialect):
        return ""
    is_tsql = str(dialect or "").lower() in ("tsql", "mssql")
    engine = "SQL Server(T-SQL)" if is_tsql else "MySQL"
    quoted = f"[{token}]" if is_tsql else f"`{token}`"
    return (
        f"`{token}` 은(는) {engine} **예약어**다 — 별칭·컬럼명·테이블명으로 쓰려면 "
        f"{quoted} 로 인용하거나 예약어가 아닌 이름({token}_val 등)으로 바꿔라. "
        f"이것이 이 오류의 가장 흔한 원인이다."
    )


def targeted_hint(kind: str, focus: str, dialect: "str | None" = None) -> str:
    """분류 + 실패 지점을 결합한 표적 처방 1~2문장."""
    parts: list[str] = []
    if focus:
        parts.append(f"엔진이 지목한 실패 지점: `{focus}` — **이 지점부터** 파싱/해석이 깨졌다. 여기를 고쳐라.")
    reserved = reserved_identifier_note(focus, dialect)
    if reserved:
        parts.append(reserved)
    base = {
        "unknown-column": "describe_table 로 정확한 컬럼명을 확인한 뒤 컬럼을 교정하라.",
        "unknown-table": "search_tables/describe_table 로 정확한 테이블/스키마명을 확인한 뒤 교정하라.",
        "syntax": "SQL 구문(따옴표·괄호·예약어·방언)을 점검해 교정하라.",
        "execution": "에러 메시지를 읽고 원인을 교정하라.",
    }.get(kind, "에러 메시지를 읽고 원인을 교정하라.")
    if not reserved:
        parts.append(base)
    return " ".join(parts)
