__all__ = [
    "_collect_cursor_result",
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

def connect(database: str | None = None, autocommit: bool = True):
    params = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
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
