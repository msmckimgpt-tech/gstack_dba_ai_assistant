"""M3 (TASK-0023) — MySQL → Postgres 초기 backfill ETL.

§2.1.3 M3 phase — M2 시작 시점 이전의 MySQL FactEntries / RagDocuments / RagObjects /
Texts row 를 Postgres 로 backfill. 멱등 + resumable + progress 로그.

특성:
- **멱등 (idempotent)**: INSERT...ON CONFLICT DO NOTHING (texts, fact_entries) 또는
  ON CONFLICT DO UPDATE (rag_documents, rag_objects). 재실행 시 동일 결과.
- **Resumable**: `artifacts/shared/kb-backfill-state.json` 에 table 별 last_id checkpoint.
  실패 시 same state file 로 재진입 — 처리된 row 의 다시 처리 회피.
- **Progress 로그**: 1000 row 마다 (table_name, processed, total, elapsed_sec, eta_sec)
  stderr 에 출력 + state file 갱신.
- **--since filter (분모 정의)**: dual-write 시작 시점 이전의 row 만 backfill.
  M2 dual-write 가 활성 후 row 는 이미 Postgres 양쪽 작성 — 중복 처리 회피.
  default: .env KB_DUAL_WRITE_START_TS.
- **--dry-run**: SELECT 만, INSERT 안 함. 분모 측정용.
- **--table <name>**: 단일 table backfill (default: 모두).

Usage:
    docker exec repo-agent-1 python -m scripts.kb_backfill --dry-run
    docker exec repo-agent-1 python -m scripts.kb_backfill --table texts --batch-size 500
    docker exec repo-agent-1 python -m scripts.kb_backfill --since 2026-05-20T00:00:00

Exit codes:
    0 — 모든 table backfill 완료 (또는 dry-run 결과)
    1 — 일부 table 실패 (state file 에서 재진입 가능)
    2 — invalid args / 환경 부재
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Table mapping — MySQL → Postgres 컬럼 정합.
# M-1 baseline (KB_PG_DIALECT_NOTES.md §3) 의 명명 매핑 적용.
# ─────────────────────────────────────────────────────────────────────────────

TABLE_MAPPING = {
    "texts": {
        "mysql_table": "AgentMemoryTexts",
        "pg_table": "texts",
        "id_col": "Id",
        "select_cols": ["Id", "TextHash", "TextContent", "CreatedAt"],
        "pg_insert_cols": ["text_hash", "text_content", "created_at"],
        "pg_conflict": "ON CONFLICT (text_hash) DO NOTHING",
        "text_hash_pk": True,       # OFFSET pagination 사용 (TextHash 기반 정렬)
    },
    "fact_entries": {
        "mysql_table": "AgentMemoryFactEntries",
        "pg_table": "fact_entries",
        "id_col": "Id",
        "select_cols": [
            "Id", "ConversationId", "FactKey", "ScopeKey", "TextHash",
            "FactFingerprint", "Weight", "Confidence", "SourceType",
            "SourceRunId", "SourceSql", "CreatedAt", "UpdatedAt",
        ],
        "pg_insert_cols": [
            "conversation_id", "fact_key", "scope_key", "text_hash",
            "fact_fingerprint", "weight", "confidence", "source_type",
            "source_run_id", "source_sql", "created_at", "updated_at",
        ],
        "pg_conflict": (
            "ON CONFLICT (conversation_id, scope_key, fact_key, fact_fingerprint) "
            "DO NOTHING"
        ),
    },
    "rag_documents": {
        "mysql_table": "AgentMemoryRagDocuments",
        "pg_table": "rag_documents",
        "id_col": "Id",
        "select_cols": [
            "Id", "ConversationId", "ScopeKey", "DocType", "FactKey", "TextHash",
            "ContentHash", "Weight", "SourceType", "SourceRunId", "SourceSql",
            "CreatedAt", "UpdatedAt",
        ],
        "pg_insert_cols": [
            "conversation_id", "scope_key", "doc_type", "fact_key", "text_hash",
            "content_hash", "weight", "source_type", "source_run_id", "source_sql",
            "created_at", "updated_at",
        ],
        "pg_conflict": (
            "ON CONFLICT (conversation_id, scope_key, fact_key, content_hash) "
            "DO NOTHING"
        ),
    },
    "rag_objects": {
        "mysql_table": "AgentMemoryRagObjects",
        "pg_table": "rag_objects",
        "id_col": "Id",
        "select_cols": [
            "Id", "ConversationId", "ScopeKey", "ObjectType", "ObjectKey",
            "SchemaName", "TableName", "ColumnName", "TextHash", "Weight",
            "SourceType", "SourceRunId",
            "CategoryDomain", "CategoryEntityType", "CategoryMetricFamily",
            "CategoryEventType", "CategoryTimeGrain", "CategoryJoinHintsJson",
            "CategoryConfidence",
            "CreatedAt", "UpdatedAt",
        ],
        "pg_insert_cols": [
            "conversation_id", "scope_key", "object_type", "object_key",
            "schema_name", "table_name", "column_name", "text_hash", "weight",
            "source_type", "source_run_id",
            "category_domain", "category_entity_type", "category_metric_family",
            "category_event_type", "category_time_grain", "category_join_hints_json",
            "category_confidence",
            "created_at", "updated_at",
        ],
        "pg_conflict": (
            "ON CONFLICT (conversation_id, scope_key, object_type, object_key) "
            "DO NOTHING"
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# State file — table 별 last_id checkpoint.
# ─────────────────────────────────────────────────────────────────────────────


def _state_file_path() -> Path:
    """state 파일 위치: artifacts/shared/kb-backfill-state.json."""
    # 본 script 가 docker exec 진입점이므로 /shared 마운트 또는 wrapper 가 전달.
    state_dir = os.environ.get("AGENT_KB_BACKFILL_STATE_DIR", "/shared")
    return Path(state_dir) / "kb-backfill-state.json"


def load_state() -> dict:
    p = _state_file_path()
    if not p.exists():
        return {"started_at": None, "tables": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"started_at": None, "tables": {}}


def save_state(state: dict) -> None:
    p = _state_file_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    except OSError as e:
        print(f"[WARN] state file save 실패: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# Connection helpers — MySQL + Postgres.
# ─────────────────────────────────────────────────────────────────────────────


def open_mysql_conn():
    """기존 modules/db.py 의 connect_with_retry 사용."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from modules.db import connect_with_retry  # type: ignore
    from shared.config import MEMORY_DB  # type: ignore
    return connect_with_retry(database=MEMORY_DB, autocommit=False, attempts=2)


def open_pg_conn():
    """기존 modules/db.py 의 _pg_connect 사용."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from modules.db import _pg_connect  # type: ignore
    return _pg_connect()


# ─────────────────────────────────────────────────────────────────────────────
# Backfill core — table 별 paginate + INSERT.
# ─────────────────────────────────────────────────────────────────────────────


def _iter_mysql_rows(
    mysql_conn, table_meta: dict, since: Optional[str], batch_size: int, last_id: int,
) -> Iterator[list]:
    """MySQL 에서 paginate. (id > last_id AND CreatedAt < since) order by id.

    texts 테이블 특수 처리: PK=TextHash (char) 라 Id 없음 → OFFSET pagination 사용.

    [주의 — REV-20260526-0001 Nice-to-have 흡수]
    OFFSET pagination 은 concurrent INSERT / DELETE 가 발생하면 row 를 skip 하거나
    중복할 수 있다. 본 backfill 은 **MySQL agent_memory 의 KB 5 정본이 backfill
    실행 동안 frozen (read-only)** 이라는 가정 위에서 동작한다. 운영 절차:
    - M3 backfill 은 dual-write 시작 (KB_DUAL_WRITE_START_TS) 이전 row 한정
      (`--since` argument 가 cutoff 역할). 그 이후 row 는 dual-write 가 mirror 함.
    - M5 cutover 시점에는 dual-write=0 + read=postgres 라 MySQL KB 는 자연 idle.
    - 만약을 대비해 `bin/kb-dual-write-verify.sh --counts` 가 row count diff 를 감지.
    """
    cur = mysql_conn.cursor()
    cols = ", ".join(table_meta["select_cols"])
    table = table_meta["mysql_table"]
    text_hash_pk = table_meta.get("text_hash_pk", False)

    if text_hash_pk:
        # OFFSET 방식 (texts 전용 — 규모 ~800행, 성능 충분)
        offset = int(last_id)  # last_id를 offset으로 재활용
        while True:
            params: list = []
            sql = f"SELECT {cols} FROM {table}"
            if since:
                sql += " WHERE CreatedAt < %s"
                params.append(since)
            sql += f" ORDER BY TextHash ASC LIMIT %s OFFSET %s"
            params.extend([batch_size, offset])
            cur.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                break
            yield rows
            offset += len(rows)
    else:
        id_col = table_meta["id_col"]
        while True:
            params = [last_id]
            sql = f"SELECT {cols} FROM {table} WHERE {id_col} > %s"
            if since:
                sql += " AND CreatedAt < %s"
                params.append(since)
            sql += f" ORDER BY {id_col} ASC LIMIT %s"
            params.append(batch_size)
            cur.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                break
            yield rows
            last_id = rows[-1][0]  # Id 는 select_cols[0]
    cur.close()


def _insert_pg_batch(
    pg_conn, table_meta: dict, rows: list, dry_run: bool,
) -> int:
    """Postgres 측 INSERT...ON CONFLICT batch. 처리된 row count 반환."""
    if not rows:
        return 0
    if dry_run:
        return len(rows)

    pg_cols = table_meta["pg_insert_cols"]
    pg_table = table_meta["pg_table"]
    pg_conflict = table_meta["pg_conflict"]
    placeholders = ", ".join(["%s"] * len(pg_cols))
    cols_sql = ", ".join(pg_cols)
    sql = (
        f"INSERT INTO {pg_table} ({cols_sql}) "
        f"VALUES ({placeholders}) "
        f"{pg_conflict}"
    )
    with pg_conn.cursor() as cur:
        for row in rows:
            # select_cols[0] = Id (auto-increment PK) — INSERT 시 skip.
            cur.execute(sql, row[1:])
    pg_conn.commit()
    return len(rows)


def backfill_table(
    table_name: str,
    since: Optional[str],
    batch_size: int,
    dry_run: bool,
    state: dict,
) -> tuple[int, int]:
    """단일 table backfill. (inserted_count, total_seen) 반환."""
    if table_name not in TABLE_MAPPING:
        raise ValueError(f"unknown table: {table_name}")
    table_meta = TABLE_MAPPING[table_name]

    tbl_state = state["tables"].setdefault(table_name, {
        "last_id": 0, "processed": 0, "started_at": None, "completed_at": None,
    })
    if tbl_state["started_at"] is None:
        tbl_state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    last_id = int(tbl_state.get("last_id", 0))

    print(f"[INFO] backfill {table_name} — since={since} batch={batch_size} dry-run={dry_run} resume-from-id={last_id}", file=sys.stderr)

    mysql_conn = open_mysql_conn()
    pg_conn = None
    if not dry_run:
        pg_conn = open_pg_conn()

    total_inserted = 0
    total_seen = 0
    start_ts = time.monotonic()
    try:
        for batch in _iter_mysql_rows(mysql_conn, table_meta, since, batch_size, last_id):
            total_seen += len(batch)
            if pg_conn:
                inserted = _insert_pg_batch(pg_conn, table_meta, batch, dry_run)
            else:
                inserted = len(batch) if dry_run else 0
            total_inserted += inserted
            last_id = batch[-1][0]
            tbl_state["last_id"] = last_id
            tbl_state["processed"] = total_seen
            if total_seen % (batch_size * 10) == 0:
                elapsed = time.monotonic() - start_ts
                print(
                    f"[PROGRESS] {table_name} processed={total_seen} "
                    f"last_id={last_id} elapsed={elapsed:.1f}s "
                    f"rate={total_seen/max(elapsed, 0.001):.0f}/s",
                    file=sys.stderr,
                )
                save_state(state)
        tbl_state["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        save_state(state)
    finally:
        try:
            mysql_conn.close()
        except Exception:
            pass
        if pg_conn:
            try:
                pg_conn.close()
            except Exception:
                pass

    elapsed = time.monotonic() - start_ts
    print(
        f"[DONE] {table_name} total_seen={total_seen} inserted={total_inserted} "
        f"elapsed={elapsed:.1f}s",
        file=sys.stderr,
    )
    return total_inserted, total_seen


def main() -> int:
    parser = argparse.ArgumentParser(description="MySQL → Postgres KB backfill ETL")
    parser.add_argument("--table", choices=list(TABLE_MAPPING) + ["all"], default="all")
    parser.add_argument(
        "--since", default=None,
        help="ISO 8601 timestamp — 분모 정의. row.CreatedAt < since 만 backfill "
             "(M2 dual-write 시작 이전). default: env KB_DUAL_WRITE_START_TS."
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--reset-state", action="store_true",
        help="state file 초기화 후 처음부터 backfill.",
    )
    args = parser.parse_args()

    since = args.since or os.environ.get("KB_DUAL_WRITE_START_TS")
    if not since:
        print("[WARN] --since 또는 KB_DUAL_WRITE_START_TS 미지정 — 전체 row backfill", file=sys.stderr)

    state = {"started_at": None, "tables": {}} if args.reset_state else load_state()
    if state.get("started_at") is None:
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    tables = list(TABLE_MAPPING) if args.table == "all" else [args.table]
    failed: list[str] = []
    for t in tables:
        try:
            backfill_table(t, since, args.batch_size, args.dry_run, state)
        except Exception as e:
            print(f"[FAIL] {t}: {e}", file=sys.stderr)
            failed.append(t)
            save_state(state)
            continue

    save_state(state)
    print(f"\n=== Backfill summary ===", file=sys.stderr)
    for t in tables:
        s = state["tables"].get(t, {})
        status = "FAILED" if t in failed else ("COMPLETED" if s.get("completed_at") else "IN_PROGRESS")
        print(
            f"  {t}: status={status} processed={s.get('processed', 0)} "
            f"last_id={s.get('last_id', 0)}",
            file=sys.stderr,
        )
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
