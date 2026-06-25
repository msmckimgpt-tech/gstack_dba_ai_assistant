"""AR-M3 (TASK-0117) — MySQL → Postgres agent_runtime 초기 backfill ETL.

§2.2.3 M3 phase — M2 dual-write 시작 시점 이전의 MySQL agent_runtime 6 테이블 row 를
Postgres agent_runtime schema 로 backfill. 멱등 + resumable + progress 로그.

대상 테이블 (FK 의존성 순서대로):
  AgentCoreConversations  → agent_runtime.core_conversations  (upsert base, OFFSET paging)
  AgentCoreMessages       → agent_runtime.core_messages       (append-only, Id paging)
  AgentMemoryMessages     → agent_runtime.messages             (append-only, Id paging)
  AgentMemorySteps        → agent_runtime.steps                (append-only, Id paging)
  AgentMemorySummary      → agent_runtime.summary              (upsert, OFFSET paging)
  AgentMemoryKv           → agent_runtime.kv                   (upsert, OFFSET paging)

특성:
- **멱등 (idempotent)**: upsert 테이블(conversations/kv/summary)은
  INSERT … ON CONFLICT DO NOTHING. append-only 테이블(core_messages/messages/steps)은
  state file last_id checkpoint 기반 resume — 동일 row 재처리 방지.
- **Resumable**: `runtime-backfill-state.json` 에 table 별 last_id / offset checkpoint.
  실패 시 동일 state 로 재진입 — 처리된 row 재처리 회피.
- **Progress 로그**: batch 10개마다 (table, processed, elapsed, rate) stderr 출력.
- **--since filter (분모 정의)**: dual-write 시작 시점 이전 row 만 backfill.
  default: env AGENT_RUNTIME_DUAL_WRITE_START_TS.
- **--dry-run**: SELECT 만, INSERT 안 함.
- **--table <name>**: 단일 table backfill.

FK 주의:
  AgentMemoryKv 의 __global__ sentinel 은 core_conversations 에 FK 가 없으므로
  자동 포함됨 (Postgres DDL FK 의도적 미설정, ADR-0027 §3).
  AgentCoreMessages / AgentMemoryMessages / AgentMemorySteps / AgentMemorySummary 는
  core_conversations FK 가 있으므로 core_conversations 반드시 선행 backfill.

Usage:
    docker exec repo-agent-1 python -m scripts.runtime_backfill --dry-run
    docker exec repo-agent-1 python -m scripts.runtime_backfill --table core_conversations
    docker exec repo-agent-1 python -m scripts.runtime_backfill --since 2026-05-20T00:00:00
    docker exec repo-agent-1 python -m scripts.runtime_backfill --batch-size 500

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
# FK 의존성 순서 (core_conversations 선행 필수).
# offset_pk=True: auto-increment Id 없음 → OFFSET 방식 pagination.
# since_col: timestamp filter 에 쓰는 MySQL 컬럼명 (대소문자 테이블마다 상이).
# jsonb_indices: INSERT VALUES 리스트 내 jsonb cast 가 필요한 0-based index.
#   (MySQL row 에서 pg_insert_cols 에 매핑되는 위치 기준 — id skip 적용 후)
# ─────────────────────────────────────────────────────────────────────────────

TABLE_ORDER = [
    "core_conversations",
    "core_messages",
    "messages",
    "steps",
    "summary",
    "kv",
]

TABLE_MAPPING: dict[str, dict] = {
    "core_conversations": {
        "mysql_table": "AgentCoreConversations",
        "pg_table": "agent_runtime.core_conversations",
        "id_col": None,                # PK는 conversation_id(varchar) — no auto-inc
        "select_cols": ["conversation_id", "topic", "created_at", "updated_at"],
        "pg_insert_cols": ["conversation_id", "topic", "created_at", "updated_at"],
        "pg_conflict": "ON CONFLICT (conversation_id) DO NOTHING",
        "since_col": "created_at",
        "offset_pk": True,
    },
    "core_messages": {
        "mysql_table": "AgentCoreMessages",
        "pg_table": "agent_runtime.core_messages",
        "id_col": "id",                # BIGINT AUTO_INCREMENT
        "select_cols": [
            "id", "conversation_id", "role", "content",
            "tool_calls", "tool_call_id", "name", "created_at",
        ],
        # id는 PG에서 GENERATED ALWAYS AS IDENTITY → skip (row[1:] 전달)
        "pg_insert_cols": [
            "conversation_id", "role", "content",
            "tool_calls", "tool_call_id", "name", "created_at",
        ],
        "pg_conflict": "",             # append-only; state file 이 idempotency 보장
        "since_col": "created_at",
        # pg_insert_cols 기준 index=3 이 tool_calls → jsonb cast 필요
        "jsonb_indices": {3},
    },
    "messages": {
        "mysql_table": "AgentMemoryMessages",
        "pg_table": "agent_runtime.messages",
        "id_col": "Id",
        "select_cols": ["Id", "ConversationId", "Role", "Content", "MetaJson", "CreatedAt"],
        # Id skip (row[1:])
        "pg_insert_cols": [
            "conversation_id", "role", "content", "meta_json", "created_at",
        ],
        "pg_conflict": "",             # append-only
        "since_col": "CreatedAt",
        # pg_insert_cols 기준 index=3 이 meta_json → jsonb cast 필요
        "jsonb_indices": {3},
    },
    "steps": {
        "mysql_table": "AgentMemorySteps",
        "pg_table": "agent_runtime.steps",
        "id_col": "Id",
        "select_cols": [
            "Id", "ConversationId", "RunId", "StepIndex", "Action", "Tool", "Intent",
            "WorkText", "WorkSource", "ReasonText", "ReasonSource",
            "ArgsJson", "SqlText", "ResultSummaryJson", "ErrorText", "CreatedAt",
        ],
        # Id skip (row[1:])
        "pg_insert_cols": [
            "conversation_id", "run_id", "step_index", "action", "tool", "intent",
            "work_text", "work_source", "reason_text", "reason_source",
            "args_json", "sql_text", "result_summary_json", "error_text", "created_at",
        ],
        "pg_conflict": "",             # append-only
        "since_col": "CreatedAt",
    },
    "summary": {
        "mysql_table": "AgentMemorySummary",
        "pg_table": "agent_runtime.summary",
        "id_col": None,
        "select_cols": ["ConversationId", "Summary", "UpdatedAt"],
        "pg_insert_cols": ["conversation_id", "summary", "updated_at"],
        "pg_conflict": "ON CONFLICT (conversation_id) DO NOTHING",
        "since_col": "UpdatedAt",
        "offset_pk": True,
    },
    "kv": {
        "mysql_table": "AgentMemoryKv",
        "pg_table": "agent_runtime.kv",
        "id_col": None,
        "select_cols": ["ConversationId", "`Key`", "`Value`", "UpdatedAt"],
        "pg_insert_cols": ["conversation_id", "key", "value", "updated_at"],
        "pg_conflict": "ON CONFLICT (conversation_id, key) DO NOTHING",
        "since_col": "UpdatedAt",
        "offset_pk": True,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# State file — table 별 last_id / offset checkpoint.
# ─────────────────────────────────────────────────────────────────────────────


def _state_file_path() -> Path:
    state_dir = os.environ.get("AGENT_RUNTIME_BACKFILL_STATE_DIR", "/shared")
    return Path(state_dir) / "runtime-backfill-state.json"


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
        p.write_text(
            json.dumps(state, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[WARN] state file save 실패: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# Connection helpers — MySQL + Postgres.
# ─────────────────────────────────────────────────────────────────────────────


def open_mysql_conn():
    """기존 shared/db.py 의 connect_with_retry 사용 (agent_memory DB)."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from shared.db import connect_with_retry  # type: ignore
    from shared.config import MEMORY_DB  # type: ignore
    return connect_with_retry(database=MEMORY_DB, autocommit=False, attempts=2)


def open_pg_conn():
    """기존 shared/db.py 의 _pg_connect 사용."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from shared.db import _pg_connect  # type: ignore
    return _pg_connect()


# ─────────────────────────────────────────────────────────────────────────────
# Backfill core — table 별 paginate + INSERT.
# ─────────────────────────────────────────────────────────────────────────────


def _iter_mysql_rows(
    mysql_conn,
    table_meta: dict,
    since: Optional[str],
    batch_size: int,
    last_checkpoint: int,
) -> Iterator[list]:
    """MySQL 에서 paginate.

    offset_pk=True 테이블: OFFSET pagination (PK가 varchar 혹은 composite).
    그 외: `id_col > last_id ORDER BY id_col` 방식.

    [주의] OFFSET pagination 은 백필 실행 중 해당 테이블이 변경될 경우 row 를
    skip 하거나 중복할 수 있다. M3 backfill 은 dual-write 시작 시점 이전 row 에
    한정(`--since` argument 가 cutoff 역할)하므로, 운영 중 INSERT 는 `--since`
    이후 타임스탬프를 가져 자동 제외. 안전 가정: since 이전 row 는 변경되지 않음.
    """
    cur = mysql_conn.cursor()
    # backtick-quoted 컬럼이 포함될 수 있으므로 그대로 join
    cols = ", ".join(table_meta["select_cols"])
    table = table_meta["mysql_table"]
    since_col = table_meta["since_col"]
    offset_pk = table_meta.get("offset_pk", False)

    if offset_pk:
        offset = int(last_checkpoint)
        while True:
            params: list = []
            sql = f"SELECT {cols} FROM {table}"
            if since:
                sql += f" WHERE {since_col} < %s"
                params.append(since)
            sql += f" ORDER BY {since_col} ASC LIMIT %s OFFSET %s"
            params.extend([batch_size, offset])
            cur.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                break
            yield rows
            offset += len(rows)
    else:
        id_col = table_meta["id_col"]
        last_id = int(last_checkpoint)
        while True:
            params = [last_id]
            sql = f"SELECT {cols} FROM {table} WHERE {id_col} > %s"
            if since:
                sql += f" AND {since_col} < %s"
                params.append(since)
            sql += f" ORDER BY {id_col} ASC LIMIT %s"
            params.append(batch_size)
            cur.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                break
            yield rows
            last_id = rows[-1][0]  # id_col 은 select_cols[0]
    cur.close()


def _build_insert_sql(table_meta: dict) -> str:
    """psycopg3 용 INSERT SQL 생성. jsonb 컬럼에 ::jsonb cast 적용."""
    pg_table = table_meta["pg_table"]
    pg_cols = table_meta["pg_insert_cols"]
    pg_conflict = table_meta.get("pg_conflict", "")
    jsonb_indices: set[int] = table_meta.get("jsonb_indices", set())

    placeholders = []
    for i in range(len(pg_cols)):
        if i in jsonb_indices:
            placeholders.append("%s::jsonb")
        else:
            placeholders.append("%s")

    cols_sql = ", ".join(pg_cols)
    vals_sql = ", ".join(placeholders)
    sql = f"INSERT INTO {pg_table} ({cols_sql}) VALUES ({vals_sql})"
    if pg_conflict:
        sql += f" {pg_conflict}"
    return sql


def _insert_pg_batch(
    pg_conn,
    table_meta: dict,
    insert_sql: str,
    rows: list,
    dry_run: bool,
) -> int:
    """Postgres 측 INSERT batch. 처리된 row count 반환."""
    if not rows:
        return 0
    if dry_run:
        return len(rows)

    has_id = table_meta["id_col"] is not None
    # offset_pk=True 테이블은 id 컬럼이 없으므로 row 전체 전달.
    # id 컬럼이 있는 테이블(append-only)은 row[0]=MySQL_Id → skip (row[1:]).

    with pg_conn.cursor() as cur:
        for row in rows:
            values = list(row[1:] if has_id else row)
            cur.execute(insert_sql, values)
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

    tbl_state = state["tables"].setdefault(
        table_name,
        {"last_checkpoint": 0, "processed": 0, "started_at": None, "completed_at": None},
    )
    if tbl_state["started_at"] is None:
        tbl_state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    last_checkpoint = int(tbl_state.get("last_checkpoint", 0))

    print(
        f"[INFO] backfill {table_name} — since={since} batch={batch_size} "
        f"dry-run={dry_run} resume-checkpoint={last_checkpoint}",
        file=sys.stderr,
    )

    mysql_conn = open_mysql_conn()
    pg_conn = None
    if not dry_run:
        pg_conn = open_pg_conn()

    insert_sql = _build_insert_sql(table_meta)
    offset_pk = table_meta.get("offset_pk", False)

    total_inserted = 0
    total_seen = 0
    start_ts = time.monotonic()
    try:
        for batch in _iter_mysql_rows(mysql_conn, table_meta, since, batch_size, last_checkpoint):
            total_seen += len(batch)
            if pg_conn:
                inserted = _insert_pg_batch(pg_conn, table_meta, insert_sql, batch, dry_run)
            else:
                inserted = len(batch)  # dry_run
            total_inserted += inserted

            # checkpoint 갱신
            if offset_pk:
                last_checkpoint += len(batch)
            else:
                last_checkpoint = int(batch[-1][0])  # last MySQL Id
            tbl_state["last_checkpoint"] = last_checkpoint
            tbl_state["processed"] = total_seen

            if total_seen % (batch_size * 10) == 0:
                elapsed = time.monotonic() - start_ts
                rate = total_seen / max(elapsed, 0.001)
                print(
                    f"[PROGRESS] {table_name} processed={total_seen} "
                    f"checkpoint={last_checkpoint} elapsed={elapsed:.1f}s rate={rate:.0f}/s",
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
    parser = argparse.ArgumentParser(description="MySQL → Postgres agent_runtime backfill ETL")
    parser.add_argument(
        "--table",
        choices=TABLE_ORDER + ["all"],
        default="all",
        help="backfill 대상 table (default: 모두, FK 순서대로)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help=(
            "ISO 8601 timestamp — 분모 정의. row.since_col < since 만 backfill "
            "(M2 dual-write 시작 이전). default: env AGENT_RUNTIME_DUAL_WRITE_START_TS."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help=(
            "state file 초기화 후 처음부터 backfill. "
            "[주의] append-only 테이블(core_messages/messages/steps)은 중복 row 발생 가능."
        ),
    )
    args = parser.parse_args()

    since = args.since or os.environ.get("AGENT_RUNTIME_DUAL_WRITE_START_TS")
    if not since:
        print(
            "[WARN] --since 또는 AGENT_RUNTIME_DUAL_WRITE_START_TS 미지정 — 전체 row backfill",
            file=sys.stderr,
        )

    state = {"started_at": None, "tables": {}} if args.reset_state else load_state()
    if state.get("started_at") is None:
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    tables = TABLE_ORDER if args.table == "all" else [args.table]
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
    print("\n=== Backfill summary ===", file=sys.stderr)
    for t in tables:
        s = state["tables"].get(t, {})
        if t in failed:
            status = "FAILED"
        elif s.get("completed_at"):
            status = "COMPLETED"
        else:
            status = "IN_PROGRESS"
        print(
            f"  {t}: status={status} processed={s.get('processed', 0)} "
            f"checkpoint={s.get('last_checkpoint', 0)}",
            file=sys.stderr,
        )
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
