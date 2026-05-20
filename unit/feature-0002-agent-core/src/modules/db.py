__all__ = [
    "_collect_cursor_result",
    "_pg_available",
    "_pg_connect",
    "_should_retry_db_error",
    "connect",
    "connect_with_retry",
    "execute_sql",
    "records_to_columns_rows",
    "summarize_mcp_result",
]


"""Database connection management and SQL execution."""
from .config import *
import time
from typing import Any
import mysql.connector

# TASK-0015 §2.1.3 M0: psycopg3 import 는 optional. requirements.txt 에는 포함되어
# 있으나 M0~M1 단계에서는 코드가 호출되지 않을 수도 (postgres 컨테이너 미가동 환경).
# import 실패 시 _pg_connect() 가 fail-loud 하고, _pg_available() 가 False 를 반환.
try:
    import psycopg as _psycopg  # type: ignore[import-not-found]
    _PSYCOPG_IMPORT_ERR: Exception | None = None
except Exception as _e:  # pragma: no cover — env without psycopg
    _psycopg = None  # type: ignore[assignment]
    _PSYCOPG_IMPORT_ERR = _e

def connect(database: str | None = None, autocommit: bool = True):
    # 복제 DB (TASK-0044): REPLICA_DB_HOST 가 설정되어 있고 요청된 database 가
    # memory DB(agent_memory) 가 아닌 경우(= data-plane 쿼리) 복제 인스턴스로 라우팅.
    # memory DB 연결은 항상 primary 로 유지된다 (대화·세션·권한 정본은 primary).
    use_replica = bool(REPLICA_DB_ENABLED) and (database is not None) and (str(database) != str(MEMORY_DB))
    if use_replica:
        host, port, user, password = REPLICA_DB_HOST, REPLICA_DB_PORT, REPLICA_DB_USER, REPLICA_DB_PASSWORD
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
    database: str | None = None, autocommit: bool = True, attempts: int | None = None
):
    attempts = attempts if attempts is not None else AGENT_DB_CONNECT_RETRIES
    attempts = max(1, int(attempts))
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return connect(database=database, autocommit=autocommit)
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


def _collect_cursor_result(cur) -> list[tuple[str, Any, Any]]:
    result_sets = []
    if getattr(cur, "with_rows", False):
        rows = cur.fetchall()
        columns = [d[0] for d in (cur.description or [])]
        result_sets.append(("rows", columns, rows))
    else:
        if cur.rowcount is not None and cur.rowcount != -1:
            result_sets.append(("rowcount", cur.rowcount, None))
    return result_sets


def execute_sql(conn, sql: str) -> tuple[list[tuple[str, Any, Any]], float]:
    cur = conn.cursor()
    start = time.time()
    results: list[tuple[str, Any, Any]] = []
    try:
        try:
            iterator = cur.execute(sql, multi=True)
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
# `agent_kb_ro` role 분리 + ADR-0023 작성 후 본 함수의 user/password 가 rw role 로
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
