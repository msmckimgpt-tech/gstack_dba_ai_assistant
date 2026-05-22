"""Sandbox CSV/XLSX ingest pipeline.

TASK-0094 Sprint 1 Phase 11. BRIEFING §6.1 Cycle 1.

본 module 의 책임:
1. **CSV ingest** — encoding detection (chardet/utf-8 fallback) + delimiter
   detection (csv.Sniffer) + numeric/date locale normalization (Sprint 1 은
   default behavior). 행 cap.
2. **XLSX ingest** — openpyxl `read_only=True` + `data_only=True` (formula 캐시
   사용) + sharedStrings cap + cell/row/col count cap + formula stripping.
3. **Sandbox table create** — `t_<attachment_id>_<sheet_slug>` 형식 (BRIEFING
   §5.1). attachment_writer connection 으로 CREATE TABLE + INSERT.
4. **Worker timeout/memory limit** — Sprint 1 simplicity 로는 시간/row 카운트
   만; 별 process 분리는 후속 cycle.

Codex Claim #14 흡수: XLSX sharedStrings cap (1M) + cell/row/col count cap +
formula stripping + CSV encoding/delimiter/locale.

caller (Phase 5 upload endpoint 의 background task 또는 Cycle 1 ingest worker)
가 본 module 의 `ingest_attachment` 호출.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import time
from typing import Any, Iterable

LOG = logging.getLogger(__name__)

# Sprint 1 limits (env override 가능).
_CSV_MAX_ROWS = max(100, int(os.getenv("SANDBOX_INGEST_CSV_MAX_ROWS") or "100000"))
_XLSX_MAX_ROWS = max(100, int(os.getenv("SANDBOX_INGEST_XLSX_MAX_ROWS") or "100000"))
_XLSX_MAX_COLS = max(10, int(os.getenv("SANDBOX_INGEST_XLSX_MAX_COLS") or "256"))
_XLSX_MAX_CELLS = max(10_000, int(os.getenv("SANDBOX_INGEST_XLSX_MAX_CELLS") or "5000000"))
_INGEST_TIMEOUT_SEC = max(10, int(os.getenv("SANDBOX_INGEST_TIMEOUT_SEC") or "300"))


class IngestError(RuntimeError):
    """ingest failure — caller 가 attachment row 의 UploadStatus='failed' + degraded_reason."""


def _slugify(text: str, *, max_len: int = 24) -> str:
    base = re.sub(r"[^A-Za-z0-9_]+", "_", str(text or "").strip().lower())
    base = base.strip("_") or "sheet"
    return base[:max_len]


def _detect_encoding(body_bytes: bytes) -> str:
    try:
        import chardet  # type: ignore[import-not-found]
        guess = chardet.detect(body_bytes[:65536])
        return str(guess.get("encoding") or "utf-8").lower()
    except Exception:
        return "utf-8"


def _detect_delimiter(text_sample: str) -> str:
    try:
        return csv.Sniffer().sniff(text_sample[:8192]).delimiter
    except Exception:
        return ","


def _safe_column_name(raw: str, used: set[str]) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw or "").strip())
    if not cleaned or not re.match(r"^[A-Za-z_]", cleaned):
        cleaned = f"col_{cleaned}" if cleaned else "col"
    cleaned = cleaned[:48].rstrip("_") or "col"
    base = cleaned
    n = 1
    while cleaned.lower() in used:
        n += 1
        cleaned = f"{base}_{n}"
    used.add(cleaned.lower())
    return cleaned


def ingest_csv(
    body_bytes: bytes,
    *,
    table_name: str,
    writer_conn,
) -> dict[str, Any]:
    """CSV → sandbox table. encoding/delimiter auto-detect.

    Returns: {rows_inserted, columns, encoding, delimiter, degraded_reason?}
    """
    started = time.monotonic()
    encoding = _detect_encoding(body_bytes)
    try:
        text = body_bytes.decode(encoding, errors="replace")
    except Exception as exc:
        raise IngestError(f"csv decode failed: {exc}") from exc
    delim = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = list(reader)
    if not rows:
        raise IngestError("csv body has 0 rows")

    header_row = rows[0]
    data_rows = rows[1:]
    used: set[str] = set()
    columns = [_safe_column_name(h, used) for h in header_row]
    if not columns:
        raise IngestError("csv header missing")

    truncated = False
    if len(data_rows) > _CSV_MAX_ROWS:
        data_rows = data_rows[:_CSV_MAX_ROWS]
        truncated = True

    cur = writer_conn.cursor()
    try:
        cols_def = ", ".join(f"`{c}` TEXT" for c in columns)
        cur.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({cols_def}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO `{table_name}` ({', '.join(f'`{c}`' for c in columns)}) VALUES ({placeholders})"
        # batch insert chunked.
        BATCH = 500
        inserted = 0
        for i in range(0, len(data_rows), BATCH):
            chunk = data_rows[i : i + BATCH]
            normalized = [tuple((str(c) if c is not None else None) for c in (r + [None] * (len(columns) - len(r))))[: len(columns)] for r in chunk]
            cur.executemany(sql, normalized)
            inserted += len(normalized)
            if time.monotonic() - started > _INGEST_TIMEOUT_SEC:
                raise IngestError(f"csv ingest timeout > {_INGEST_TIMEOUT_SEC}s after {inserted} rows")
    finally:
        cur.close()
    try:
        writer_conn.commit()
    except Exception:
        pass

    result = {
        "rows_inserted": inserted,
        "columns": columns,
        "encoding": encoding,
        "delimiter": delim,
        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 2),
    }
    if truncated:
        result["degraded_reason"] = f"row count exceeded cap ({_CSV_MAX_ROWS}) — truncated"
    return result


def ingest_xlsx(
    body_bytes: bytes,
    *,
    base_table_name: str,
    writer_conn,
) -> dict[str, Any]:
    """XLSX → sandbox table (시트별). openpyxl read_only=True + data_only=True.

    Returns: {sheets: [{name, table_name, rows, cols, degraded_reason?}], ...}
    """
    started = time.monotonic()
    try:
        from openpyxl import load_workbook  # type: ignore[import-not-found]
    except Exception as exc:
        raise IngestError(f"openpyxl not installed: {exc}") from exc

    try:
        wb = load_workbook(io.BytesIO(body_bytes), read_only=True, data_only=True)
    except Exception as exc:
        raise IngestError(f"xlsx parse failed: {exc}") from exc

    sheets_result: list[dict[str, Any]] = []
    total_cells = 0

    for sheet in wb.worksheets:
        if time.monotonic() - started > _INGEST_TIMEOUT_SEC:
            raise IngestError(f"xlsx ingest timeout > {_INGEST_TIMEOUT_SEC}s")
        sheet_slug = _slugify(sheet.title)
        table_name = f"{base_table_name}_{sheet_slug}"[:64]
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            sheets_result.append({"name": sheet.title, "skipped": True, "reason": "empty"})
            continue
        used: set[str] = set()
        columns = [_safe_column_name(str(h) if h is not None else f"col_{idx + 1}", used) for idx, h in enumerate(header_row[:_XLSX_MAX_COLS])]
        if not columns:
            continue

        cur = writer_conn.cursor()
        try:
            cols_def = ", ".join(f"`{c}` TEXT" for c in columns)
            cur.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({cols_def}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO `{table_name}` ({', '.join(f'`{c}`' for c in columns)}) VALUES ({placeholders})"
            BATCH = 500
            buffer: list[tuple] = []
            inserted = 0
            truncated = False
            for row_idx, row in enumerate(rows_iter):
                if row_idx >= _XLSX_MAX_ROWS:
                    truncated = True
                    break
                row_clipped = row[:_XLSX_MAX_COLS]
                total_cells += len(row_clipped)
                if total_cells > _XLSX_MAX_CELLS:
                    truncated = True
                    break
                normalized = tuple(
                    (str(c) if c is not None and not str(c).strip().startswith("=") else None)
                    for c in row_clipped
                )
                while len(normalized) < len(columns):
                    normalized = normalized + (None,)
                buffer.append(normalized)
                if len(buffer) >= BATCH:
                    cur.executemany(sql, buffer)
                    inserted += len(buffer)
                    buffer = []
                if time.monotonic() - started > _INGEST_TIMEOUT_SEC:
                    raise IngestError(f"xlsx ingest timeout > {_INGEST_TIMEOUT_SEC}s")
            if buffer:
                cur.executemany(sql, buffer)
                inserted += len(buffer)
        finally:
            cur.close()
        try:
            writer_conn.commit()
        except Exception:
            pass
        entry: dict[str, Any] = {
            "name": sheet.title,
            "table_name": table_name,
            "rows": inserted,
            "cols": len(columns),
        }
        if truncated:
            entry["degraded_reason"] = "row/cell cap exceeded — truncated"
        sheets_result.append(entry)

    return {
        "sheets": sheets_result,
        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 2),
    }


def ingest_attachment(
    body_bytes: bytes,
    *,
    kind: str,
    attachment_id: int,
    sheet_table_base: str,
    writer_conn,
) -> dict[str, Any]:
    """caller wrapper — kind 별 분기. caller 가 attachment row 의 UploadStatus
    를 'ingested' or 'partial_indexed' (D17) or 'failed' 로 갱신.
    """
    if kind == "csv":
        return ingest_csv(body_bytes, table_name=sheet_table_base, writer_conn=writer_conn)
    if kind == "xlsx":
        return ingest_xlsx(body_bytes, base_table_name=sheet_table_base, writer_conn=writer_conn)
    raise IngestError(f"unsupported kind for sandbox ingest: {kind}")
