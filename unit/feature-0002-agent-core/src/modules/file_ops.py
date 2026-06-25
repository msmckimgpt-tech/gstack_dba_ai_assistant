from datetime import datetime, timezone
import io
import json
import mysql.connector
import os
import re
import shutil
import stat
import statistics
import subprocess
import time
__all__ = [
    "BLOCKED_BINARY_EXTENSIONS",
    "RESTORE_ALLOWED_EXTENSIONS",
    "_analyze_local_infile_sql",
    "_binary_file_guard_message",
    "_contains_local_infile",
    "_extract_infile_path",
    "_file_ext",
    "_infer_database_from_sql_file",
    "_is_blocked_binary_data_file",
    "_is_restore_compatible_file",
    "_load_cached_file_read",
    "_load_sql_file",
    "_mysql_cli_restore",
    "_pick_csv_columns_for_request",
    "_resolve_root_path",
    "_resolve_shared_path",
    "_sql_has_db_directives",
    "_summarize_csv_numeric",
    "_summarize_csv_numeric_from_content",
    "convo_search",
    "file_read",
    "file_search",
    "restore_sql_file",
]


"""File operations: search, read, CSV, SQL file restore."""
from shared.config import *
import csv, io, json, os, re, shutil, stat, statistics, subprocess
from typing import Any

def _resolve_root_path(root: str) -> str | None:
    if not root:
        return None
    abs_root = os.path.abspath(root)
    if not (abs_root == "/shared" or abs_root.startswith("/shared/")):
        return None
    return abs_root


def _resolve_shared_path(path: str | None) -> str | None:
    if not path:
        return None
    raw = str(path).strip()
    if not raw:
        return None
    raw = raw.replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    if raw.startswith("shared/"):
        raw = "/" + raw
    if raw.startswith("/"):
        abs_path = os.path.abspath(raw)
    else:
        abs_path = os.path.abspath(os.path.join("/shared", raw))
    if not (abs_path == "/shared" or abs_path.startswith("/shared/")):
        return None
    return abs_path


BLOCKED_BINARY_EXTENSIONS = {
    ".ibd",
    ".ibdata",
    ".ib_logfile",
    ".frm",
    ".myd",
    ".myi",
    ".par",
    ".sdi",
}
RESTORE_ALLOWED_EXTENSIONS = {".sql", ".dump"}


def _file_ext(path: str | None) -> str:
    if not path:
        return ""
    return os.path.splitext(str(path).strip().lower())[1]


def _is_blocked_binary_data_file(path: str | None) -> bool:
    ext = _file_ext(path)
    if ext in BLOCKED_BINARY_EXTENSIONS:
        return True
    name = os.path.basename(str(path or "").strip().lower())
    if name in {"ibdata1", "ib_logfile0", "ib_logfile1"}:
        return True
    return False


def _is_restore_compatible_file(path: str | None) -> bool:
    ext = _file_ext(path)
    if ext in RESTORE_ALLOWED_EXTENSIONS:
        return True
    return False


def _binary_file_guard_message(path: str | None) -> str:
    ext = _file_ext(path) or "알 수 없음"
    return (
        f"직접 복원 불가 파일 형식({ext})입니다. "
        "`.ibd/.ibdata/.frm` 계열 파일은 텍스트 읽기/직접 복원이 불가하며, "
        "`mysqldump`로 생성한 `.sql`(또는 `.dump`) 백업 파일로 복원해야 합니다."
    )




def convo_search(
    conn,
    conversation_id: str,
    query: str | None = None,
    limit: int = 50,
    include_current: bool = False,
) -> list[dict[str, Any]]:
    pattern = str(query or "").strip()
    # TASK-0200 MINOR hardening: LIKE/ILIKE 메타문자(`%`, `_`, escape `!`)를 이스케이프해
    # "100%" / "table_name" 같은 질의가 와일드카드로 오작동하지 않도록 한다. 비어 있으면
    # 전체 매칭(`%`)이라 이스케이프·ESCAPE 절 불필요(like_escape = ""). MySQL·PG 양 분기 공유.
    if pattern:
        _esc = pattern.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        like_pattern = f"%{_esc}%"
        like_escape = " ESCAPE '!'"
    else:
        like_pattern = "%"
        like_escape = ""
    limit = max(1, int(limit or 50))
    results: list[dict[str, Any]] = []

    def _format_row(row) -> dict[str, Any]:
        conv_id, role, content, created_at, source = row
        return {
            "conversation_id": str(conv_id),
            "role": str(role),
            "content": str(content),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            "source": source,
        }

    # AR-M5 cutover: AgentMemoryMessages/AgentMemorySummary/AgentMemoryKv MySQL 테이블이
    # DROP 됨 → AGENT_RUNTIME_READ_BACKEND=postgres 일 때 PG agent_runtime.messages/summary/kv
    # 로 라우팅한다(미라우팅 시 convo_search 도구 호출이 삭제된 테이블 조회로 throw — 에이전트의
    # "다른 대화 검색" 기능 사망). ILIKE = MySQL utf8mb4_unicode_ci case-insensitive 패리티.
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                where = f"content ILIKE %s{like_escape}"
                params = [like_pattern]
                if not include_current:
                    where += " AND conversation_id != %s"
                    params.append(conversation_id)
                params.append(limit)
                pgcur.execute(
                    f"SELECT conversation_id, role, content, created_at, 'message' AS source "
                    f"FROM agent_runtime.messages WHERE {where} ORDER BY created_at DESC LIMIT %s",
                    tuple(params),
                )
                for row in pgcur.fetchall() or []:
                    results.append(_format_row(row))

                where = f"summary ILIKE %s{like_escape}"
                params = [like_pattern]
                if not include_current:
                    where += " AND conversation_id != %s"
                    params.append(conversation_id)
                params.append(limit)
                pgcur.execute(
                    f"SELECT conversation_id, 'summary' AS role, summary AS content, "
                    f"updated_at AS created_at, 'summary' AS source "
                    f"FROM agent_runtime.summary WHERE {where} ORDER BY updated_at DESC LIMIT %s",
                    tuple(params),
                )
                for row in pgcur.fetchall() or []:
                    results.append(_format_row(row))

                where = f"key = 'topic' AND value ILIKE %s{like_escape}"
                params = [like_pattern]
                if not include_current:
                    where += " AND conversation_id != %s"
                    params.append(conversation_id)
                params.append(limit)
                pgcur.execute(
                    f"SELECT conversation_id, 'topic' AS role, value AS content, "
                    f"updated_at AS created_at, 'topic' AS source "
                    f"FROM agent_runtime.kv WHERE {where} ORDER BY updated_at DESC LIMIT %s",
                    tuple(params),
                )
                for row in pgcur.fetchall() or []:
                    results.append(_format_row(row))
        finally:
            pg.close()
    else:
        cur = conn.cursor()
        try:
            where = f"Content LIKE %s{like_escape}"
            params = [like_pattern]
            if not include_current:
                where += " AND ConversationId != %s"
                params.append(conversation_id)
            params.append(limit)
            cur.execute(
                f"""
SELECT ConversationId, Role, Content, CreatedAt, 'message' AS source
FROM AgentMemoryMessages
WHERE {where}
ORDER BY CreatedAt DESC
LIMIT %s
                """,
                tuple(params),
            )
            for row in cur.fetchall() or []:
                results.append(_format_row(row))

            where = f"Summary LIKE %s{like_escape}"
            params = [like_pattern]
            if not include_current:
                where += " AND ConversationId != %s"
                params.append(conversation_id)
            params.append(limit)
            cur.execute(
                f"""
SELECT ConversationId, 'summary' AS Role, Summary AS Content, UpdatedAt AS CreatedAt, 'summary' AS source
FROM AgentMemorySummary
WHERE {where}
ORDER BY UpdatedAt DESC
LIMIT %s
                """,
                tuple(params),
            )
            for row in cur.fetchall() or []:
                results.append(_format_row(row))

            where = f"`Key` = 'topic' AND `Value` LIKE %s{like_escape}"
            params = [like_pattern]
            if not include_current:
                where += " AND ConversationId != %s"
                params.append(conversation_id)
            params.append(limit)
            cur.execute(
                f"""
SELECT ConversationId, 'topic' AS Role, `Value` AS Content, UpdatedAt AS CreatedAt, 'topic' AS source
FROM AgentMemoryKv
WHERE {where}
ORDER BY UpdatedAt DESC
LIMIT %s
                """,
                tuple(params),
            )
            for row in cur.fetchall() or []:
                results.append(_format_row(row))
        finally:
            cur.close()

    results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return results[:limit]


def file_search(root: str | None = None, pattern: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    search_root = _resolve_root_path(root or "/shared")
    if not search_root:
        raise RuntimeError("허용되지 않는 검색 경로입니다. `/shared` 하위 경로만 허용됩니다.")

    normalized_pattern = (pattern or "").strip().lower()
    results: list[dict[str, Any]] = []
    for current, _, files in os.walk(search_root):
        for name in files:
            if normalized_pattern:
                if normalized_pattern not in name.lower():
                    continue
            path = os.path.join(current, name)
            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            results.append(
                {
                    "path": path,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
                }
            )
            if len(results) >= limit:
                return results
    return results


def file_read(file_path: str, max_bytes: int = 65536) -> dict[str, Any]:
    if max_bytes is None or max_bytes <= 0:
        max_bytes = 65536
    max_limit = max(1024 * 1024, int(AGENT_CSV_ANALYZE_MAX_BYTES))
    max_bytes = min(int(max_bytes), max_limit)
    abs_path = _resolve_shared_path(file_path)
    if not abs_path:
        raise RuntimeError("허용되지 않는 파일 경로입니다. `/shared` 하위 경로만 허용됩니다.")
    if not os.path.exists(abs_path):
        raise RuntimeError(f"파일이 존재하지 않습니다: {abs_path}")
    try:
        st = os.stat(abs_path)
    except Exception as exc:
        raise RuntimeError(f"파일 정보를 읽을 수 없습니다: {abs_path}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise RuntimeError("읽을 수 없는 파일 유형입니다. 일반 파일만 허용됩니다.")
    if _is_blocked_binary_data_file(abs_path):
        raise RuntimeError(_binary_file_guard_message(abs_path))

    with open(abs_path, "rb") as f:
        data = f.read(max_bytes)
    text = data.decode("utf-8", errors="replace")
    truncated = st.st_size > len(data)
    return {
        "path": abs_path,
        "size": st.st_size,
        "read_bytes": len(data),
        "truncated": truncated,
        "content": text,
    }


def _load_cached_file_read(kv: dict[str, str], path: str) -> dict[str, Any] | None:
    if not kv or not path:
        return None
    raw = kv.get("last_file_read")
    if not raw:
        return None
    try:
        cached = json.loads(raw)
    except Exception:
        return None
    if not isinstance(cached, dict):
        return None
    cached_path = str(cached.get("path", "")).strip()
    if cached_path and cached_path == path:
        return cached
    return None


def _contains_local_infile(sql_text: str) -> bool:
    lowered = str(sql_text or "").lower()
    return "load data" in lowered and "infile" in lowered


def _extract_infile_path(sql_text: str) -> str:
    if not sql_text:
        return ""
    match = re.search(
        r"infile\\s+(?:'([^']+)'|\"([^\"]+)\"|([^\\s;]+))",
        sql_text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return (match.group(1) or match.group(2) or match.group(3) or "").strip()


def _pick_csv_columns_for_request(request: str, header: list[str]) -> list[str]:
    if not header:
        return []
    lowered = str(request or "").lower()
    candidates = []
    keyword_map = {
        "bytes": ("byte", "bytes", "size", "용량", "바이트"),
        "count": ("count", "cnt", "건수", "수", "개수", "총"),
        "price": ("price", "cost", "가격"),
        "time": ("time", "date", "일", "날짜"),
    }
    for key, tokens in keyword_map.items():
        if any(tok in lowered for tok in tokens):
            for col in header:
                if any(tok in col.lower() for tok in tokens):
                    candidates.append(col)
    if candidates:
        return list(dict.fromkeys(candidates))
    return header[: min(5, len(header))]


def _summarize_csv_numeric(
    path: str,
    request: str,
    max_rows: int = 200000,
) -> tuple[dict[str, Any], str]:
    if not os.path.exists(path):
        return {}, "CSV 파일을 찾을 수 없습니다."
    try:
        st = os.stat(path)
    except Exception:
        return {}, "CSV 파일을 읽는 중 오류가 발생했습니다."
    max_bytes = max(1024, int(AGENT_CSV_ANALYZE_MAX_BYTES))
    with open(path, "rb") as f:
        data = f.read(max_bytes)
    content = data.decode("utf-8", errors="replace")
    truncated = st.st_size > len(data)
    return _summarize_csv_numeric_from_content(
        path=path,
        request=request,
        content=content,
        max_rows=max_rows,
        truncated=truncated,
    )


def _summarize_csv_numeric_from_content(
    path: str,
    request: str,
    content: str | None,
    max_rows: int = 200000,
    truncated: bool = False,
) -> tuple[dict[str, Any], str]:
    result: dict[str, Any] = {}
    if content is None:
        if not os.path.exists(path):
            return result, "CSV 파일을 찾을 수 없습니다."
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return result, "CSV 파일을 읽는 중 오류가 발생했습니다."
    reader = csv.reader(io.StringIO(content))
    header = next(reader, None)
    if not header:
        return result, "CSV 헤더가 비어 있습니다."
    target_cols = _pick_csv_columns_for_request(request, header)
    idx_map = {col: header.index(col) for col in target_cols if col in header}
    if not idx_map:
        return result, "CSV에서 분석할 컬럼을 찾지 못했습니다."
    stats: dict[str, dict[str, Any]] = {}
    values_cache: dict[str, list[float]] = {col: [] for col in idx_map}
    total_rows = 0
    for row in reader:
        if total_rows >= max_rows:
            break
        total_rows += 1
        for col, idx in idx_map.items():
            if idx >= len(row):
                continue
            raw = row[idx]
            try:
                val = float(raw)
            except Exception:
                continue
            stat = stats.get(col)
            if not stat:
                stat = {"count": 0, "sum": 0.0, "min": val, "max": val}
                stats[col] = stat
            stat["count"] += 1
            stat["sum"] += val
            stat["min"] = min(stat["min"], val)
            stat["max"] = max(stat["max"], val)
            if len(values_cache[col]) < 10000:
                values_cache[col].append(val)
    for col, stat in stats.items():
        count = stat.get("count", 0) or 0
        if count:
            stat["avg"] = stat["sum"] / count
            if values_cache[col]:
                stat["median"] = statistics.median(values_cache[col])
    result = {
        "rows": total_rows,
        "cols": len(header),
        "col_names": header[: min(len(header), 10)],
        "metrics": stats,
        "path": path,
    }
    if truncated:
        result["analysis_truncated"] = True
    summary_lines = []
    for col, stat in stats.items():
        avg = stat.get("avg")
        total = stat.get("sum")
        med = stat.get("median")
        if avg is not None:
            summary_lines.append(f"{col} 평균={avg:.4f}")
        if med is not None:
            summary_lines.append(f"{col} 중앙값={med:.4f}")
        if total is not None:
            summary_lines.append(f"{col} 합계={total:.4f}")
    summary = "\n".join(summary_lines) if summary_lines else "CSV 수치 요약을 계산했습니다."
    if truncated:
        summary = f"{summary} (부분 분석)"
    return result, summary


def _analyze_local_infile_sql(
    mem_conn,
    conversation_id: str,
    sql_text: str,
    request: str,
) -> tuple[dict[str, Any] | None, list[str], dict[str, Any] | None, str]:
    csv_path = _extract_infile_path(sql_text)
    if not csv_path:
        return None, [], None, "CSV 파일 경로를 확인할 수 없습니다."
    resolved_path = _resolve_shared_path(csv_path)
    if not resolved_path:
        return None, [], None, "CSV 파일 경로는 `/shared` 하위만 허용됩니다."
    try:
        read_result = file_read(resolved_path, max_bytes=AGENT_CSV_ANALYZE_MAX_BYTES)
    except Exception as exc:
        return None, [], None, str(exc)
    if mem_conn and conversation_id:
        try:
            save_memory_kv(
                mem_conn,
                conversation_id,
                "last_file_read",
                json.dumps(read_result, ensure_ascii=False),
            )
            save_memory_kv(mem_conn, conversation_id, "last_file_read_path", resolved_path)
        except Exception:
            pass
    summary_data, summary_text = _summarize_csv_numeric_from_content(
        resolved_path,
        request=request,
        content=read_result.get("content"),
        max_rows=AGENT_CSV_ANALYZE_MAX_ROWS,
        truncated=bool(read_result.get("truncated")),
    )
    if summary_data:
        summary_data["summary"] = summary_text
    else:
        summary_data = {"summary": summary_text}
    csv_preview = read_csv_preview(resolved_path, AGENT_CSV_PREVIEW_ROWS)
    if csv_preview:
        if not summary_data.get("col_names"):
            cols = csv_preview.get("columns", [])
            summary_data["col_names"] = cols[: min(10, len(cols))]
        if not summary_data.get("samples") and csv_preview.get("rows"):
            summary_data["samples"] = csv_preview.get("rows", [])[:3]
    if mem_conn and conversation_id:
        try:
            save_memory_kv(mem_conn, conversation_id, "last_csv_path", resolved_path)
            if csv_preview:
                save_memory_kv(
                    mem_conn,
                    conversation_id,
                    "last_csv_preview",
                    json.dumps(csv_preview, ensure_ascii=False),
                )
        except Exception:
            pass
    return summary_data, [resolved_path], csv_preview, ""


def _load_sql_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Remove DELIMITER directives to avoid mysql-connector errors.
    lines = []
    for line in content.splitlines():
        if line.strip().lower().startswith("delimiter "):
            continue
        lines.append(line)
    return "\n".join(lines)


def _sql_has_db_directives(sql_text: str) -> bool:
    lowered = sql_text.lower()
    if re.search(r"\bcreate\s+database\b", lowered):
        return True
    if re.search(r"\buse\s+[`\"\\[]?\w+[`\"\\]]?\b", lowered):
        return True
    return False


def _infer_database_from_sql_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                lower = line.strip().lower()
                if lower.startswith("create database") or lower.startswith("create schema"):
                    m = re.search(r"\bcreate\s+(?:database|schema)\b\s+[`\"\\[]?(\w+)", lower)
                    if m:
                        return m.group(1)
                if lower.startswith("use "):
                    m = re.search(r"\buse\b\s+[`\"\\[]?(\w+)", lower)
                    if m:
                        return m.group(1)
    except Exception:
        return None
    return None


def _mysql_cli_restore(file_path: str, database: str | None) -> None:
    cmd = ["mysql", "-h", DB_HOST, "-P", str(DB_PORT), "-u", DB_USER, "--default-character-set=utf8mb4"]
    if database:
        cmd.extend(["-D", database])
    env = os.environ.copy()
    if DB_PASSWORD:
        env["MYSQL_PWD"] = DB_PASSWORD
    with open(file_path, "rb") as f:
        subprocess.run(cmd, stdin=f, check=True, env=env)


def restore_sql_file(file_path: str, database: str, overwrite: bool) -> dict[str, Any]:
    abs_path = _resolve_shared_path(file_path)
    if not abs_path:
        raise RuntimeError("복원 파일은 `/shared` 하위 경로만 허용됩니다.")
    if not os.path.exists(abs_path):
        raise RuntimeError(f"파일이 존재하지 않습니다: {abs_path}")
    if _is_blocked_binary_data_file(abs_path):
        raise RuntimeError(_binary_file_guard_message(abs_path))
    if not _is_restore_compatible_file(abs_path):
        raise RuntimeError(
            "직접 복원 가능한 파일은 `.sql`/`.dump` 형식입니다. "
            "현재 파일은 복원 대상이 아닙니다. SQL 덤프 파일을 선택하세요."
        )
    if database and database.strip().lower() in ("__use_db_name_in_file__", "__use_db_in_file__", "__use_file_db__"):
        database = ""

    inferred_db = None
    if not database:
        inferred_db = _infer_database_from_sql_file(abs_path)
        if inferred_db and overwrite:
            database = inferred_db

    sql_script = _load_sql_file(abs_path)

    if database:
        admin_conn = connect(database=None, autocommit=True)
        try:
            admin_cur = admin_conn.cursor()
            if overwrite:
                admin_cur.execute(f"DROP DATABASE IF EXISTS {_quote_ident(database)}")
            admin_cur.execute(
                f"CREATE DATABASE IF NOT EXISTS {_quote_ident(database)} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            admin_cur.close()
        finally:
            admin_conn.close()
        target_conn = connect(database=database, autocommit=True)
    else:
        if overwrite:
            raise RuntimeError("덮어쓰기(overwrite) 사용 시 대상 데이터베이스 이름이 필요합니다.")
        if not _sql_has_db_directives(sql_script):
            raise RuntimeError("SQL 파일에 CREATE DATABASE 또는 USE 문이 없어 대상 DB 지정이 필요합니다.")
        target_conn = connect(database=None, autocommit=True)

    use_cli = False
    if shutil.which("mysql"):
        try:
            if os.path.getsize(abs_path) >= 50 * 1024 * 1024:
                use_cli = True
        except Exception:
            use_cli = False

    if use_cli:
        _mysql_cli_restore(abs_path, database or None)
        return {
            "status": "ok",
            "statements": None,
            "database": database or inferred_db or "",
            "file": abs_path,
            "method": "mysql-cli",
        }

    try:
        cur = target_conn.cursor()
        statements = 0
        try:
            iterator = cur.execute(sql_script, multi=True)
        except TypeError:
            try:
                iterator = cur.execute(sql_script, None, True)
            except TypeError:
                iterator = None
                cur.execute(sql_script)
        if iterator is not None:
            for _ in iterator:
                statements += 1
        else:
            statements = 1
            try:
                while cur.nextset():
                    statements += 1
            except Exception:
                pass
        cur.close()
    finally:
        target_conn.close()

    return {
        "status": "ok",
        "statements": statements,
        "database": database or inferred_db or "",
        "file": abs_path,
        "method": "connector",
    }


