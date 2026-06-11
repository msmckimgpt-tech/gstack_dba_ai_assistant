__all__ = [
    "_collect_cursor_result",
    "_pg_available",
    "_pg_connect",
    "_pg_connect_ro",
    "_pg_mark_kb_invalidation",
    "_pg_check_kb_invalidation",
    "_should_retry_db_error",
    "connect",
    "connect_with_retry",
    "execute_sql",
    "list_server_databases",
    "probe_datasource",
    "records_to_columns_rows",
    "summarize_mcp_result",
]


"""Database connection management and SQL execution."""
from .config import *
import logging
import threading
import time
from typing import Any
import mysql.connector
import mysql.connector.pooling  # MySQLConnectionPool (TASK-0144)
from mysql.connector.errors import PoolError  # 풀 소진 시그널 (TASK-0144)

# ─────────────────────────────────────────────────────────────────────────────
# TASK-0144: opt-in MySQL 커넥션 풀 (기본 OFF, 폴백 안전).
#
# 안전 계약:
#   - AGENT_DB_POOL_ENABLED 기본 False → connect() 가 기존 connect-per-request
#     경로 그대로 (mysql.connector.connect(**params)) → 동작 0 변경.
#   - True(canary 로만) 일 때만 (host,user,database) 시그니처별 풀에서 대여.
#   - 풀 소진(PoolError) / 풀 생성 실패 시 direct connect 로 폴백 (절대 raise 로
#     요청을 실패시키지 않음) + logger.warning. 즉 풀은 best-effort 최적화.
#   - 풀에서 꺼낸 커넥션은 호출측이 .close() 하면 mysql.connector 기본 동작으로
#     풀에 반환된다 (추가 반환 API 불필요). direct connect 폴백 커넥션도 .close()
#     로 정상 종료되므로 호출측 수명주기 코드는 풀/비풀 구분 없이 동일하다.
#
# 풀 키 설계: (host, port, user, database) 4-tuple 을 풀 이름으로 직렬화.
#   - mysql.connector 풀은 생성 시 user/password/database 가 고정되므로, connect()
#     의 3분기 라우팅(replica / RO data-plane(agent_ro) / memory primary(root)) 이
#     고른 (host,user) 조합과, database 값까지 키에 포함해야 cross-contamination 이
#     없다. database=None(서버 default) 와 특정 database 는 서로 다른 풀.
# ─────────────────────────────────────────────────────────────────────────────
_db_logger = logging.getLogger("agent_core.db")
_POOL_REGISTRY: dict[str, "mysql.connector.pooling.MySQLConnectionPool"] = {}
_POOL_LOCK = threading.Lock()


def _pool_key(params: dict[str, Any]) -> str:
    """풀 레지스트리 키 — (host, port, user, database) 시그니처를 직렬화.

    password 는 (host,user) 에 종속이므로 키에서 제외. database=None 은 빈 문자열로
    구분(서버 default DB 전용 풀). user 라우팅(root vs agent_ro) 과 replica host 분기는
    자연히 다른 키가 된다.
    """
    return "|".join(
        str(params.get(k, ""))
        for k in ("host", "port", "user", "database")
    )


def _get_or_create_pool(params: dict[str, Any]):
    """시그니처별 풀을 lazy 생성 후 반환. thread-safe.

    풀 생성 실패 시 None 을 반환하여 connect() 가 direct connect 로 폴백하게 한다
    (raise 하지 않음 — 풀은 best-effort).
    """
    key = _pool_key(params)
    pool = _POOL_REGISTRY.get(key)
    if pool is not None:
        return pool
    with _POOL_LOCK:
        # double-checked locking — 다른 스레드가 먼저 생성했을 수 있음.
        pool = _POOL_REGISTRY.get(key)
        if pool is not None:
            return pool
        try:
            pool_params = dict(params)
            pool_params["pool_name"] = f"agent_pool_{abs(hash(key)) & 0xFFFFFFFF:x}"
            pool_params["pool_size"] = AGENT_DB_POOL_SIZE
            pool_params["pool_reset_session"] = bool(AGENT_DB_POOL_RESET_SESSION)
            pool = mysql.connector.pooling.MySQLConnectionPool(**pool_params)
            _POOL_REGISTRY[key] = pool
            return pool
        except Exception as exc:
            _db_logger.warning(
                "db_pool_create_failed key=%s err=%r — direct connect 로 폴백", key, exc
            )
            return None


# TASK-0015 §2.1.3 M0: psycopg3 import 는 optional. requirements.txt 에는 포함되어
# 있으나 M0~M1 단계에서는 코드가 호출되지 않을 수도 (postgres 컨테이너 미가동 환경).
# import 실패 시 _pg_connect() 가 fail-loud 하고, _pg_available() 가 False 를 반환.
try:
    import psycopg as _psycopg  # type: ignore[import-not-found]
    _PSYCOPG_IMPORT_ERR: Exception | None = None
except Exception as _e:  # pragma: no cover — env without psycopg
    _psycopg = None  # type: ignore[assignment]
    _PSYCOPG_IMPORT_ERR = _e

# 멀티 datasource Stage 2 (P4): MSSQL(pymssql) optional import. engine='mssql' datasource
# 분석에만 쓰인다. 미설치 환경(기본)에서는 None — mssql datasource 연결 시 fail-loud.
try:
    import pymssql as _pymssql  # type: ignore[import-not-found]
    _PYMSSQL_IMPORT_ERR: Exception | None = None
except Exception as _e:  # pragma: no cover — env without pymssql
    _pymssql = None  # type: ignore[assignment]
    _PYMSSQL_IMPORT_ERR = _e


def _connect_mssql(datasource: dict, database: str | None, autocommit: bool):
    """MSSQL(SQL Server) datasource 연결 (Stage 2 P4, pymssql).

    **DB 컨텍스트 고정 (P6, M-1 엔진별 정합)**: MSSQL 은 `database > schema > table` 3계층이라
    schema 격리(allowlist=dbo/sales)는 **특정 DATABASE 안에서** 의미를 가진다. 따라서 연결은
    datasource 의 `default_db` 로 고정하고(없으면 caller 명시값), 쿼리는 2-part `schema.table` 로
    한다. MySQL 의 M-1("database=None — 미접두 쿼리가 default_db 를 우회조회")과 달리 MSSQL 에서는
    **무자격 table-ref 를 P6 가 fail-closed 로 거부**(tools._freeform_sql_access_error)하고 3-part
    catalog(DB) cross-DB 참조도 차단하므로, DB 고정이 오히려 안전하다. (로그인 GRANT 도 해당 DB 의
    허용 스키마로 한정 — bin/datasource-mssql-ro-bootstrap.sql.) default_db 미설정 MSSQL datasource 는
    로그인 기본 DB(보통 master)로 붙어 2-part 쿼리가 깨지므로 DS_<KEY>_DEFAULT_DB 설정이 사실상 필수.
    포트 미설정 시 MSSQL 기본 1433.
    """
    if _pymssql is None:
        raise RuntimeError(
            f"pymssql 미설치 — mssql datasource 연결 불가. requirements.txt 의 pymssql 확인. "
            f"original error: {_PYMSSQL_IMPORT_ERR!r}"
        )
    port = int(datasource.get("port") or 1433)
    db_name = database or datasource.get("default_db") or ""
    conn = _pymssql.connect(
        server=datasource.get("host") or DB_HOST,
        port=str(port),
        user=datasource.get("user") or DB_USER,
        password=datasource.get("password", ""),
        database=db_name,  # P6: MSSQL 은 default_db 로 DB 컨텍스트 고정(빈 문자열=로그인 기본 DB)
        login_timeout=int(AGENT_TIMEOUT_SEC),
        timeout=int(AGENT_TIMEOUT_SEC),
        autocommit=bool(autocommit),
        charset="UTF-8",
    )
    return conn


def connect(database: str | None = None, autocommit: bool = True, datasource: dict | None = None):
    # ── 멀티 datasource (P1, DESIGN Stage 1): 명시 datasource 좌표 우선 ──────────
    # datasource(dict: host/port/user/password/default_db) 가 주어지고 flag 가 켜져 있으면
    # 문자열 휴리스틱(MEMORY_DB/replica/AGENT_DATA_DB) 라우팅을 **건너뛰고** 그 좌표로 연결한다.
    # data-plane(분석 대상) 전용 경로 — 호출측(agent_core/insight)이 conversation 의 product 에
    # 바인딩된 datasource 를 해석해 넘긴다. flag OFF 또는 datasource=None 이면 아래 기존 라우팅이
    # 100% 그대로 — 기존 단일 MySQL 동작 0 변경(M-3: plane 은 호출측이 명시).
    if datasource and AGENT_MULTI_DATASOURCE_ENABLED:
        # Stage 2 (P4): engine 디스패치 — mssql 은 pymssql, 그 외(mysql)는 mysql.connector.
        if (datasource.get("engine") or "mysql").strip().lower() == "mssql":
            return _connect_mssql(datasource, database, autocommit)
        host = datasource.get("host") or DB_HOST
        port = int(datasource.get("port") or DB_PORT)
        user = datasource.get("user") or DB_USER
        password = datasource.get("password", "")
        # REV-20260610-0187 M-1: datasource 의 default_db 를 연결의 암묵 기본 스키마로 적용하지
        # 않는다. 적용하면 미접두 쿼리(`SELECT * FROM t`)가 schema-ref 0개로 allowlist 를 우회해
        # default_db 를 조회하게 된다. database 는 caller 가 명시한 값만 사용(agent_core 는 datasource
        # 경로에서 None 전달) → schema-prefixed 쿼리만 가능 → allowlist 가 유일 게이트.
        params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "autocommit": autocommit,
            "connection_timeout": AGENT_TIMEOUT_SEC,
            "charset": "utf8mb4",
            "use_unicode": True,
        }
        if database:
            params["database"] = database
        if not AGENT_DB_POOL_ENABLED:
            return mysql.connector.connect(**params)
        return _pooled_connect(params)

    # 복제 DB (TASK-0044): REPLICA_DB_HOST 가 설정되어 있고 요청된 database 가
    # memory DB(agent_memory) 가 아닌 경우(= data-plane 쿼리) 복제 인스턴스로 라우팅.
    # memory DB 연결은 항상 primary 로 유지된다 (대화·세션·권한 정본은 primary).
    #
    # TASK-0107: sandbox schema (agent_attachment_<sha256[:32]>) 도 primary 유지.
    # sandbox 는 사용자 첨부 ingest 로 primary 에 동적 생성되며 replica 복제 latency
    # 또는 미복제 환경에서도 즉시 SELECT 가능해야 한다. memory DB 와 같은 DB user
    # 로 접근하므로 별 grant 추가 불필요 (단일-user MVP).
    db_str = str(database) if database is not None else ""
    is_sandbox = db_str.startswith("agent_attachment_")
    use_replica = (
        bool(REPLICA_DB_ENABLED)
        and (database is not None)
        and db_str != str(MEMORY_DB)
        and not is_sandbox
    )
    if use_replica:
        host, port, user, password = REPLICA_DB_HOST, REPLICA_DB_PORT, REPLICA_DB_USER, REPLICA_DB_PASSWORD
    elif db_str != str(MEMORY_DB) and AGENT_DATA_DB_USER:
        # TASK-0128 (#2): data-plane(고객 데이터/sandbox 분석) 연결은 최소권한 RO 유저로 라우팅.
        # MEMORY_DB(제어) 연결은 root 유지. AGENT_DATA_DB_USER 미설정 시 아래 else(root) 로 폴백.
        host, port, user, password = DB_HOST, DB_PORT, AGENT_DATA_DB_USER, AGENT_DATA_DB_PASSWORD
    else:
        host, port, user, password = DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
    params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "autocommit": autocommit,
        "connection_timeout": AGENT_TIMEOUT_SEC,
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if database:
        params["database"] = database

    # TASK-0144: 기본 OFF — 풀 비활성 시 기존 connect-per-request 경로 그대로
    # (동작 0 변경). opt-in(canary) True 일 때만 풀 경로 + 폴백.
    if not AGENT_DB_POOL_ENABLED:
        return mysql.connector.connect(**params)
    return _pooled_connect(params)


def _pooled_connect(params: dict[str, Any]):
    """풀에서 커넥션 대여 — 풀 소진/생성 실패 시 direct connect 로 폴백 (TASK-0144).

    절대 raise 로 요청을 실패시키지 않는다. 풀이 없거나(생성 실패) 소진(PoolError)
    되면 logger.warning 후 mysql.connector.connect(**params) 로 direct connect 한다.
    direct connect 자체가 실패(DB down 등) 하면 그 예외는 평소처럼 전파(폴백 대상 아님).
    """
    pool = _get_or_create_pool(params)
    if pool is None:
        # 풀 생성 실패 — 이미 warning 로깅됨. direct connect 로 폴백.
        return mysql.connector.connect(**params)
    try:
        return pool.get_connection()
    except PoolError as exc:
        # 풀 소진 — overflow 허용(기본) 여부와 무관히 안전하게 direct connect 폴백.
        _db_logger.warning(
            "db_pool_exhausted key=%s overflow_allowed=%s err=%r — direct connect 로 폴백",
            _pool_key(params), bool(AGENT_DB_POOL_MAX_OVERFLOW), exc,
        )
        return mysql.connector.connect(**params)
    except Exception as exc:
        # 예기치 못한 풀 오류도 요청 실패로 번지지 않게 폴백.
        _db_logger.warning(
            "db_pool_get_failed key=%s err=%r — direct connect 로 폴백",
            _pool_key(params), exc,
        )
        return mysql.connector.connect(**params)


def _should_retry_db_error(err: Exception) -> bool:
    code = getattr(err, "errno", None)
    if code in (2003, 2006, 2013, 1205):
        return True
    msg = str(err).lower()
    if "can't connect" in msg or "lost connection" in msg or "timeout" in msg:
        return True
    return False


def connect_with_retry(
    database: str | None = None, autocommit: bool = True, attempts: int | None = None,
    datasource: dict | None = None,
):
    attempts = attempts if attempts is not None else AGENT_DB_CONNECT_RETRIES
    attempts = max(1, int(attempts))
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return connect(database=database, autocommit=autocommit, datasource=datasource)
        except Exception as exc:
            last_exc = exc
            if not _should_retry_db_error(exc):
                break
            if attempt < attempts:
                time.sleep(AGENT_DB_CONNECT_BACKOFF_SEC * attempt)
                continue
    if last_exc:
        raise last_exc
    raise RuntimeError("DB 연결 실패")


def probe_datasource(datasource: dict, *, timeout: int | None = None) -> tuple[bool, float, str]:
    """datasource 좌표로 직접 연결 + `SELECT 1` (관리자 명시 연결테스트, P2).

    **flag(AGENT_MULTI_DATASOURCE_ENABLED) 무관**으로 좌표에 연결한다 — 운영자가 flag 활성화
    *전*에 자격증명·연결성을 검증하는 용도. authz 는 호출측(web admin 권한)이 담당한다.
    database(default_db) 는 설정하지 않는다 — host/port/user/password 연결성만 검증(에이전트가
    schema-prefixed 로 동작하므로 특정 DB 기본 선택 불요, M-1 정합).

    password 유출 방지: 예외 전문(host/user 포함 가능)을 반환하지 않고 errno/예외타입만 반환한다.
    Returns: (ok, elapsed_ms, error_message).
    """
    engine = (datasource.get("engine") or "mysql").strip().lower()
    start = time.time()
    conn = None
    try:
        if engine == "mssql":
            # Stage 2 (P4): MSSQL probe (pymssql, flag 무관 명시 테스트).
            if _pymssql is None:
                return False, 0.0, "pymssql_not_installed"
            conn = _pymssql.connect(
                server=datasource.get("host") or DB_HOST,
                port=str(int(datasource.get("port") or 1433)),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                login_timeout=int(timeout or 8),
                timeout=int(timeout or 8),
            )
        else:
            conn = mysql.connector.connect(
                host=datasource.get("host") or DB_HOST,
                port=int(datasource.get("port") or DB_PORT),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                connection_timeout=int(timeout or 8),
                charset="utf8mb4",
                use_unicode=True,
            )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchall()
        cur.close()
        return True, (time.time() - start) * 1000.0, ""
    except Exception as exc:
        errno = getattr(exc, "errno", None)
        # errno/예외타입만 노출 (host/user/pw 비유출).
        msg = f"errno={errno}" if errno else type(exc).__name__
        return False, (time.time() - start) * 1000.0, msg
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def list_server_databases(datasource: dict, *, timeout: int | None = None) -> "list[str]":
    """datasource 서버의 DB 목록 (TASK-0205 §2.4 제품별 참조 DB 선택용). flag 무관 직결.

    MSSQL=`sys.databases`(시스템 DB 1-4 제외), MySQL=`SHOW DATABASES`(시스템 스키마 제외).
    예외는 그대로 raise(호출 endpoint 가 generic 메시지로 일반화 — host/pw 비유출). SSRF 검사는
    호출측(_ssrf_check_host)이 선행한다.
    """
    engine = (datasource.get("engine") or "mysql").strip().lower()
    conn = None
    try:
        if engine == "mssql":
            if _pymssql is None:
                raise RuntimeError("pymssql_not_installed")
            conn = _pymssql.connect(
                server=datasource.get("host") or DB_HOST,
                port=str(int(datasource.get("port") or 1433)),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                login_timeout=int(timeout or 8), timeout=int(timeout or 8),
            )
            cur = conn.cursor()
            cur.execute("SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name")
        else:
            conn = mysql.connector.connect(
                host=datasource.get("host") or DB_HOST,
                port=int(datasource.get("port") or DB_PORT),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                connection_timeout=int(timeout or 8), charset="utf8mb4", use_unicode=True,
            )
            cur = conn.cursor()
            cur.execute("SHOW DATABASES")
        _sys = {"information_schema", "mysql", "performance_schema", "sys", "agent_memory"}
        out = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0] and str(r[0]).lower() not in _sys]
        cur.close()
        return out
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def list_server_databases_classified(datasource: dict, *, timeout: int | None = None) -> "list[dict]":
    """TASK-0206 §3.4: DB 목록을 시스템/사용자 구분해 반환(`[{name, system}]`).

    DB-단위 접근 모델에서 UI 는 시스템 DB(MSSQL master/model/msdb/tempdb)를 고정칩(메타,
    항상 접근)으로, 사용자 DB 를 다중선택 allowlist 로 렌더한다. MSSQL 만 시스템 DB 를 포함
    (catalog 차원 — `sys`/`guest` 스키마는 dialect 가 차단). MySQL 은 DB==스키마라 시스템 스키마
    (information_schema/mysql/...) 는 메타데이터 경계로 계속 숨김(기존 동작 유지).
    예외는 그대로 raise(endpoint 가 일반화). SSRF 검사는 호출측 선행.
    """
    engine = (datasource.get("engine") or "mysql").strip().lower()
    conn = None
    try:
        if engine == "mssql":
            if _pymssql is None:
                raise RuntimeError("pymssql_not_installed")
            conn = _pymssql.connect(
                server=datasource.get("host") or DB_HOST,
                port=str(int(datasource.get("port") or 1433)),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                login_timeout=int(timeout or 8), timeout=int(timeout or 8),
            )
            cur = conn.cursor()
            # database_id 1-4 = master/tempdb/model/msdb (시스템). 그 외 = 사용자 DB.
            cur.execute(
                "SELECT name, CASE WHEN database_id <= 4 THEN 1 ELSE 0 END AS is_sys "
                "FROM sys.databases ORDER BY is_sys DESC, name"
            )
            out = []
            for r in (cur.fetchall() or []):
                if not r or not r[0]:
                    continue
                # tempdb 은 휘발성 — allowlist 의미 없음, 숨김.
                if str(r[0]).lower() == "tempdb":
                    continue
                out.append({"name": str(r[0]), "system": bool(int(r[1] or 0))})
            cur.close()
            return out
        else:
            conn = mysql.connector.connect(
                host=datasource.get("host") or DB_HOST,
                port=int(datasource.get("port") or DB_PORT),
                user=datasource.get("user") or DB_USER,
                password=datasource.get("password", ""),
                connection_timeout=int(timeout or 8), charset="utf8mb4", use_unicode=True,
            )
            cur = conn.cursor()
            cur.execute("SHOW DATABASES")
            _sys = {"information_schema", "mysql", "performance_schema", "sys", "agent_memory"}
            out = [
                {"name": str(r[0]), "system": False}
                for r in (cur.fetchall() or [])
                if r and r[0] and str(r[0]).lower() not in _sys
            ]
            cur.close()
            return out
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _collect_cursor_result(cur) -> list[tuple[str, Any, Any]]:
    # Stage 2 (P4): 크로스엔진 결과 수집. mysql.connector 전용 `cur.with_rows` 대신 DBAPI 표준
    # `cur.description`(result set 있으면 not None)으로 판정 → mysql.connector·pymssql 공통.
    # mysql.connector 도 SELECT 후 description 이 set 되고 비-row 문에서 None 이라 등가(회귀 0).
    result_sets = []
    has_rows = getattr(cur, "description", None) is not None
    if has_rows:
        rows = cur.fetchall()
        columns = [d[0] for d in (cur.description or [])]
        result_sets.append(("rows", columns, rows))
    else:
        rc = getattr(cur, "rowcount", None)
        if rc is not None and rc != -1:
            result_sets.append(("rowcount", rc, None))
    return result_sets


def execute_sql(conn, sql: str) -> tuple[list[tuple[str, Any, Any]], float]:
    cur = conn.cursor()
    start = time.time()
    results: list[tuple[str, Any, Any]] = []
    try:
        try:
            # TASK-0128 (#2): multi=False — 다중문 실행 차단(SQL injection 방어 심층).
            # LLM freeform SQL 은 sql_guard 가 이미 다중문 reject 하고, 구조화 도구는
            # 단일 statement 만 생성하므로 multi 비활성이 안전하다.
            iterator = cur.execute(sql, multi=False)
            if iterator is not None:
                for item in iterator:
                    results.extend(_collect_cursor_result(item))
            else:
                results.extend(_collect_cursor_result(cur))
        except TypeError:
            cur.execute(sql)
            results.extend(_collect_cursor_result(cur))
    finally:
        cur.close()
    return results, time.time() - start


def records_to_columns_rows(records: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    if not records:
        return [], []
    first = records[0]
    columns = [str(c) for c in first.keys()]
    rows = []
    for record in records:
        rows.append([record.get(c) for c in columns])
    return columns, rows


def summarize_mcp_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        if isinstance(result.get("data"), dict):
            data = result["data"]
            if isinstance(data.get("rows"), list):
                rows = data["rows"]
                return {"rows": len(rows), "sample": rows[:3]}
            if isinstance(data.get("results"), list):
                rows = data["results"]
                return {"rows": len(rows), "sample": rows[:3]}
            if isinstance(data.get("count"), int):
                return {"count": data["count"]}
        if "records" in result and isinstance(result["records"], list):
            records = result["records"]
            return {"records": len(records), "sample": records[:3]}
        if "results" in result and isinstance(result["results"], list):
            return {"result_sets": len(result["results"])}
        if "rowcount" in result:
            return {"rowcount": result["rowcount"]}
        if "status" in result:
            return {"status": result["status"]}
    return {"result": result}


# ─────────────────────────────────────────────────────────────────────────────
# TASK-0015 §2.1.3 M0: KB Postgres pgvector connection helper.
#
# M0 단계의 진입점. mysql.connector 와 공존하며 기존 코드 경로는 무영향.
# M2 dual-write phase 부터 `_pg_connect()` 가 write path 에 호출되고, M4 cutover
# 시점에 read path 도 본 helper 를 사용한다. M1 cycle 에서 `agent_kb_rw` /
# `agent_kb_ro` role 분리 + ADR-0021 작성 후 본 함수의 user/password 가 rw role 로
# 전환된다 (config.AGENT_KB_PG_USER 환경변수 갱신만으로 적용).
# ─────────────────────────────────────────────────────────────────────────────

def _pg_available() -> bool:
    """psycopg import + AGENT_KB_PG_* 환경변수 둘 다 갖춰져 있으면 True.

    M0 단계의 standalone 운영에서 호출자가 postgres backend 호출 가능 여부를
    싸게 확인하기 위한 helper. 본 함수는 connection 시도 안 함 (network 부담 0).
    """
    return (_psycopg is not None) and AGENT_KB_PG_ENABLED


def _pg_connect(database: str | None = None, autocommit: bool = True):
    """KB Postgres (pgvector/pgvector:pg16) 에 connection 을 연다.

    M0 단계: 호출자가 standalone 테스트 또는 `bin/kb-pg-healthcheck.sh` 에서 사용.
    실 KB read/write 는 M2+ phase 에서 본 함수를 통해 routing.

    Args:
        database: 대상 database. None 이면 AGENT_KB_PG_DB (default `agent_kb`) 사용.
        autocommit: psycopg3 default 는 autocommit=False. 본 helper 는 mysql.connector
                    의 default 동작 (autocommit=True) 과 일치시키기 위해 명시.

    Raises:
        RuntimeError: psycopg import 실패 또는 AGENT_KB_PG_* 환경변수 미설정 시.
                      M0 의 standalone 운영에서 본 RuntimeError 는 caller 가
                      mysql.connector path 로 fallback 하도록 신호. M4 cutover
                      이후 본 RuntimeError 는 KB 접근 차단을 의미하므로 healthcheck
                      에서 fail-loud.
        psycopg.OperationalError: connection 실패 (host unreachable, auth 실패 등).
    """
    if _psycopg is None:
        raise RuntimeError(
            f"psycopg not importable (M0 prerequisite missing). "
            f"requirements.txt 에 psycopg[binary] 가 설치되었는지 확인. "
            f"original error: {_PSYCOPG_IMPORT_ERR!r}"
        )
    if not AGENT_KB_PG_ENABLED:
        raise RuntimeError(
            "AGENT_KB_PG_HOST / AGENT_KB_PG_USER 미설정 (M0 prerequisite missing). "
            ".env 의 AGENT_KB_PG_* 변수가 채워졌는지 확인."
        )
    target_db = (database or AGENT_KB_PG_DB or "agent_kb")
    conninfo_parts = [
        f"host={AGENT_KB_PG_HOST}",
        f"port={AGENT_KB_PG_PORT}",
        f"dbname={target_db}",
        f"user={AGENT_KB_PG_USER}",
        f"password={AGENT_KB_PG_PASSWORD}",
        f"sslmode={AGENT_KB_PG_SSLMODE}",
        f"connect_timeout={AGENT_TIMEOUT_SEC}",
        "application_name=agent_core_kb",
    ]
    conninfo = " ".join(conninfo_parts)
    conn = _psycopg.connect(conninfo)
    if autocommit:
        conn.autocommit = True
    return conn


def _pg_connect_ro(database: str | None = None, autocommit: bool = True):
    """REV-20260522-0012 B3 흡수 (M4 TASK-0024): read path least-privilege connection.

    `agent_kb_ro` role 로 connection 을 연다. ADR-0021 의 2-layer hybrid RBAC 정합 —
    read 는 read-only role 로, write 는 rw role 로 분리.

    AGENT_KB_PG_USER_RO / AGENT_KB_PG_PASSWORD_RO 가 미설정 시 RW 로 fallback (warning
    log) — backward-compat 보장 + 운영 환경에서 RO role 미배포 시 cutover 진행 가능.

    Raises:
        RuntimeError: AGENT_KB_PG_ENABLED 가 False 또는 psycopg 미설치.
    """
    if _psycopg is None:
        raise RuntimeError(
            f"psycopg not importable. original error: {_PSYCOPG_IMPORT_ERR!r}"
        )
    if not AGENT_KB_PG_ENABLED:
        raise RuntimeError("AGENT_KB_PG_HOST / AGENT_KB_PG_USER 미설정")

    ro_user = AGENT_KB_PG_USER_RO or AGENT_KB_PG_USER
    ro_pw = AGENT_KB_PG_PASSWORD_RO or AGENT_KB_PG_PASSWORD
    if not AGENT_KB_PG_USER_RO:
        import logging
        logging.getLogger("agent_core.db").warning(
            "kb_pg_ro_fallback_to_rw — AGENT_KB_PG_USER_RO 미설정, RW role 로 read path 진행. "
            "운영 환경에서는 .env 의 AGENT_KB_PG_USER_RO/AGENT_KB_PG_PASSWORD_RO 설정 권장 (ADR-0021)."
        )
    # T5-14: AGENT_KB_PG_HOST_RO 설정 시 replica 로 라우팅 (미설정=primary fallback).
    ro_host = AGENT_KB_PG_HOST_RO or AGENT_KB_PG_HOST
    ro_port = AGENT_KB_PG_PORT_RO or AGENT_KB_PG_PORT
    target_db = (database or AGENT_KB_PG_DB or "agent_kb")
    conninfo_parts = [
        f"host={ro_host}",
        f"port={ro_port}",
        f"dbname={target_db}",
        f"user={ro_user}",
        f"password={ro_pw}",
        f"sslmode={AGENT_KB_PG_SSLMODE}",
        f"connect_timeout={AGENT_TIMEOUT_SEC}",
        "application_name=agent_core_kb_ro",
    ]
    conninfo = " ".join(conninfo_parts)
    conn = _psycopg.connect(conninfo)
    if autocommit:
        conn.autocommit = True
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# T4-12: KB 무효화 플래그 — LISTEN/NOTIFY 대용 공유 시계.
#
# 에이전트가 per-call 방식으로 connection 을 열어 LISTEN 을 유지할 수 없는 구조이므로,
# `kb_invalidations` 테이블에 channel 별 최신 write 시각을 기록한다.
#   - 쓰기 완료 시: _pg_mark_kb_invalidation(conn, "kb_global") 호출.
#   - 캐시 유효성 판단 시: _pg_check_kb_invalidation(channel) 으로 last epoch 반환.
# _is_refresh_due 에서 TTL 판단에 추가로 이 시각을 활용한다.
# ─────────────────────────────────────────────────────────────────────────────


def _pg_mark_kb_invalidation(conn, channel: str = "kb_global") -> None:
    """fact 쓰기 완료 후 kb_invalidations 에 invalidated_at 갱신."""
    channel = str(channel or "kb_global").strip()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
INSERT INTO kb_invalidations (channel, invalidated_at)
VALUES (%s, now())
ON CONFLICT (channel) DO UPDATE SET invalidated_at = now()
                """,
                (channel,),
            )
        # NOTIFY 도 함께 발행 — 미래 persistent-listener 구현을 위한 groundwork.
        with conn.cursor() as cur:
            cur.execute("SELECT pg_notify(%s, %s)", (channel, "write"))
    except Exception:
        pass


def _pg_check_kb_invalidation(channel: str = "kb_global") -> float | None:
    """kb_invalidations 에서 해당 channel 의 invalidated_at (Unix timestamp) 반환.

    Returns: float epoch or None (table absent / channel not found / PG unavailable).
    """
    if not _pg_available():
        return None
    channel = str(channel or "kb_global").strip()
    conn = None
    try:
        conn = _pg_connect_ro()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXTRACT(EPOCH FROM invalidated_at) FROM kb_invalidations WHERE channel = %s",
                (channel,),
            )
            row = cur.fetchone()
            return float(row[0]) if row else None
    except Exception:
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
