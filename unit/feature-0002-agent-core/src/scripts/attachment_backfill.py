"""TASK-0277 — MySQL agent_memory 첨부 4 테이블 → PG agent_runtime backfill + reconcile.

대화/메시지 cutover 의 runtime_backfill.py(AR-M3) 와 동형. dual-write 시작 이전의 기존 첨부 행
(현재 운영 ~272행)을 PG agent_runtime.core_attachments(+부속)로 멱등 backfill 하고, count·SUM·id-diff
로 정합을 검증한다(read flip 前 게이트).

대상(FK 의존성 순서):
  WebConversationAttachments               → agent_runtime.core_attachments               (id 보존)
  WebConversationAttachmentsSandboxSchemas → agent_runtime.core_attachment_sandbox_schemas (id 보존)
  WebAttachmentDerivedMessages             → agent_runtime.core_attachment_derived_messages (id 보존)
  WebConversationAttachmentProviderFiles   → agent_runtime.core_attachment_provider_files   (id 보존)

특성:
- **멱등**: INSERT … ON CONFLICT (id) DO NOTHING. dual-write 로 이미 들어온 행은 보존(미덮어쓰기).
- **id 보존**: MySQL Id 를 PG id 로 명시 INSERT(GENERATED ALWAYS 미사용 — 참조 무결성).
- **타입 정합**: DATETIME(6) naive UTC → timestamptz(`%s::timestamptz`, UTC 명시), JSON 문자열 → jsonb.
- **orphan-safe**: core_attachments 는 conversation FK, 부속은 attachment FK — 대상 부모가 PG 에 없으면
  per-row 로 skip+로그(전체 backfill 중단 방지). PG 는 autocommit 으로 per-row 격리.
- **--dry-run**: SELECT/매핑만, INSERT 안 함.
- **--verify**: backfill 없이 MySQL↔PG count·SUM(size_bytes)·missing-id diff 만 출력(reconcile 게이트).
- **--table <name>**: 단일 테이블만.

Usage:
    docker exec repo-agent-1 python -m scripts.attachment_backfill --dry-run
    docker exec repo-agent-1 python -m scripts.attachment_backfill
    docker exec repo-agent-1 python -m scripts.attachment_backfill --verify
    docker exec repo-agent-1 python -m scripts.attachment_backfill --table core_attachments

Exit codes:
    0 — backfill 완료 / dry-run / verify 정합(diff 0)
    1 — 일부 행 실패(재실행 가능) 또는 verify 불일치(diff > 0)
    2 — invalid args / 환경 부재
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timezone
from pathlib import Path
from typing import Any


def open_mysql_conn():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from modules.db import connect_with_retry  # type: ignore
    from shared.config import MEMORY_DB  # type: ignore
    return connect_with_retry(database=MEMORY_DB, autocommit=False, attempts=2)


def open_pg_conn():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from modules.db import _pg_connect  # type: ignore
    return _pg_connect()  # autocommit=True (db.py 기본) — per-row 격리


# ── 값 정규화(attachment_pg_mirror 와 동일 계약) ─────────────────────────────
def _dt_to_pg(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            if getattr(value, "tzinfo", None) is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _json_to_pg(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return None
    text = value.decode("utf-8", "replace") if isinstance(value, (bytes, bytearray)) else str(value)
    text = text.strip()
    return text or None


_MYSQL_ATTACH_COLS = (
    "Id, ConversationId, AccountId, ObjectKey, OriginalFilename, FilenameHmac, MimeType, "
    "SizeBytes, SizeBucket, Sha256, Kind, UploadStatus, AttachmentDerivedMessages, CreatedAt, "
    "DeletedAt, DeletePending, DeleteReason, MetaJson, RootAttachmentId, VersionNumber, "
    "CreatedByRole, SupersededAt"
)

_PG_UPSERT_ATTACH = """
INSERT INTO agent_runtime.core_attachments (
    id, conversation_id, account_id, object_key, original_filename, filename_hmac,
    mime_type, size_bytes, size_bucket, sha256, kind, upload_status,
    attachment_derived_messages, created_at, deleted_at, delete_pending, delete_reason,
    meta_json, root_attachment_id, version_number, created_by_role, superseded_at
) VALUES (
    %(id)s, %(conversation_id)s, %(account_id)s, %(object_key)s, %(original_filename)s,
    %(filename_hmac)s, %(mime_type)s, %(size_bytes)s, %(size_bucket)s, %(sha256)s, %(kind)s,
    %(upload_status)s, %(attachment_derived_messages)s::jsonb, %(created_at)s::timestamptz,
    %(deleted_at)s::timestamptz, %(delete_pending)s, %(delete_reason)s, %(meta_json)s::jsonb,
    %(root_attachment_id)s, %(version_number)s, %(created_by_role)s, %(superseded_at)s::timestamptz
)
ON CONFLICT (id) DO NOTHING
"""

_PG_UPSERT_SANDBOX = """
INSERT INTO agent_runtime.core_attachment_sandbox_schemas
    (id, conversation_id, schema_name, created_at, dropped_at, delete_pending)
VALUES
    (%(id)s, %(conversation_id)s, %(schema_name)s, %(created_at)s::timestamptz,
     %(dropped_at)s::timestamptz, %(delete_pending)s)
ON CONFLICT (id) DO NOTHING
"""

_PG_UPSERT_DERIVED = """
INSERT INTO agent_runtime.core_attachment_derived_messages
    (id, attachment_id, message_id, derivation_type, created_at)
VALUES
    (%(id)s, %(attachment_id)s, %(message_id)s, %(derivation_type)s, %(created_at)s::timestamptz)
ON CONFLICT (id) DO NOTHING
"""

_PG_UPSERT_PROVIDER = """
INSERT INTO agent_runtime.core_attachment_provider_files
    (id, attachment_id, provider, provider_file_id, uploaded_at, deleted_at,
     last_delete_attempt_at, delete_attempt_count, last_error)
VALUES
    (%(id)s, %(attachment_id)s, %(provider)s, %(provider_file_id)s, %(uploaded_at)s::timestamptz,
     %(deleted_at)s::timestamptz, %(last_delete_attempt_at)s::timestamptz, %(delete_attempt_count)s,
     %(last_error)s)
ON CONFLICT (id) DO NOTHING
"""


def _attach_params(r: dict) -> dict:
    return {
        "id": int(r["Id"]),
        "conversation_id": str(r.get("ConversationId") or ""),
        "account_id": int(r.get("AccountId") or 0),
        "object_key": str(r.get("ObjectKey") or ""),
        "original_filename": str(r.get("OriginalFilename") or ""),
        "filename_hmac": str(r.get("FilenameHmac") or ""),
        "mime_type": str(r.get("MimeType") or ""),
        "size_bytes": int(r.get("SizeBytes") or 0),
        "size_bucket": str(r.get("SizeBucket") or ""),
        "sha256": str(r.get("Sha256") or ""),
        "kind": str(r.get("Kind") or ""),
        "upload_status": str(r.get("UploadStatus") or "uploaded"),
        "attachment_derived_messages": _json_to_pg(r.get("AttachmentDerivedMessages")),
        "created_at": _dt_to_pg(r.get("CreatedAt")),
        "deleted_at": _dt_to_pg(r.get("DeletedAt")),
        "delete_pending": int(r.get("DeletePending") or 0),
        "delete_reason": (str(r["DeleteReason"]) if r.get("DeleteReason") else None),
        "meta_json": _json_to_pg(r.get("MetaJson")),
        "root_attachment_id": (int(r["RootAttachmentId"]) if r.get("RootAttachmentId") else None),
        "version_number": int(r.get("VersionNumber") or 1),
        "created_by_role": str(r.get("CreatedByRole") or "user"),
        "superseded_at": _dt_to_pg(r.get("SupersededAt")),
    }


_TABLES = {
    "core_attachments": {
        "mysql_select": f"SELECT {_MYSQL_ATTACH_COLS} FROM WebConversationAttachments ORDER BY Id",
        "pg_table": "agent_runtime.core_attachments",
        "upsert": _PG_UPSERT_ATTACH,
        "params": _attach_params,
    },
    "core_attachment_sandbox_schemas": {
        "mysql_select": (
            "SELECT Id, ConversationId, SchemaName, CreatedAt, DroppedAt, DeletePending "
            "FROM WebConversationAttachmentsSandboxSchemas ORDER BY Id"
        ),
        "pg_table": "agent_runtime.core_attachment_sandbox_schemas",
        "upsert": _PG_UPSERT_SANDBOX,
        "params": lambda r: {
            "id": int(r["Id"]),
            "conversation_id": str(r.get("ConversationId") or ""),
            "schema_name": str(r.get("SchemaName") or ""),
            "created_at": _dt_to_pg(r.get("CreatedAt")),
            "dropped_at": _dt_to_pg(r.get("DroppedAt")),
            "delete_pending": int(r.get("DeletePending") or 0),
        },
    },
    "core_attachment_derived_messages": {
        "mysql_select": (
            "SELECT Id, AttachmentId, MessageId, DerivationType, CreatedAt "
            "FROM WebAttachmentDerivedMessages ORDER BY Id"
        ),
        "pg_table": "agent_runtime.core_attachment_derived_messages",
        "upsert": _PG_UPSERT_DERIVED,
        "params": lambda r: {
            "id": int(r["Id"]),
            "attachment_id": int(r.get("AttachmentId") or 0),
            "message_id": int(r.get("MessageId") or 0),
            "derivation_type": str(r.get("DerivationType") or ""),
            "created_at": _dt_to_pg(r.get("CreatedAt")),
        },
    },
    "core_attachment_provider_files": {
        "mysql_select": (
            "SELECT Id, AttachmentId, Provider, ProviderFileId, UploadedAt, DeletedAt, "
            "LastDeleteAttemptAt, DeleteAttemptCount, LastError "
            "FROM WebConversationAttachmentProviderFiles ORDER BY Id"
        ),
        "pg_table": "agent_runtime.core_attachment_provider_files",
        "upsert": _PG_UPSERT_PROVIDER,
        "params": lambda r: {
            "id": int(r["Id"]),
            "attachment_id": int(r.get("AttachmentId") or 0),
            "provider": str(r.get("Provider") or ""),
            "provider_file_id": str(r.get("ProviderFileId") or ""),
            "uploaded_at": _dt_to_pg(r.get("UploadedAt")),
            "deleted_at": _dt_to_pg(r.get("DeletedAt")),
            "last_delete_attempt_at": _dt_to_pg(r.get("LastDeleteAttemptAt")),
            "delete_attempt_count": int(r.get("DeleteAttemptCount") or 0),
            "last_error": (str(r["LastError"]) if r.get("LastError") else None),
        },
    },
}

# FK 의존성: core_attachments 가 부속보다 선행해야 함.
_TABLE_ORDER = [
    "core_attachments",
    "core_attachment_sandbox_schemas",
    "core_attachment_derived_messages",
    "core_attachment_provider_files",
]


def _fetch_mysql_dicts(mysql_conn, sql: str) -> list[dict]:
    cur = mysql_conn.cursor(dictionary=True)
    try:
        cur.execute(sql)
        return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        cur.close()


def backfill_table(name: str, mysql_conn, pg_conn, dry_run: bool) -> tuple[int, int, int]:
    """(inserted, skipped_conflict, errors) 반환. orphan/오류는 per-row skip+로그."""
    meta = _TABLES[name]
    rows = _fetch_mysql_dicts(mysql_conn, meta["mysql_select"])
    inserted = skipped = errors = 0
    for r in rows:
        try:
            params = meta["params"](r)
        except Exception as exc:
            errors += 1
            print(f"[backfill:{name}] map error id={r.get('Id')}: {exc}", file=sys.stderr)
            continue
        if dry_run:
            continue
        try:
            with pg_conn.cursor() as cur:
                cur.execute(meta["upsert"], params)
                if int(cur.rowcount or 0) > 0:
                    inserted += 1
                else:
                    skipped += 1
        except Exception as exc:
            # FK orphan(부모 미존재) 등 — per-row skip(autocommit 으로 격리). 전체 중단 방지.
            errors += 1
            print(f"[backfill:{name}] insert error id={r.get('Id')}: {exc}", file=sys.stderr)
    print(
        f"[backfill:{name}] total={len(rows)} inserted={inserted} skipped={skipped} errors={errors}"
        f"{' (dry-run)' if dry_run else ''}",
        file=sys.stderr,
    )
    return inserted, skipped, errors


_VERIFY = {
    "core_attachments": (
        "WebConversationAttachments", "agent_runtime.core_attachments", "SizeBytes", "size_bytes",
    ),
    "core_attachment_sandbox_schemas": (
        "WebConversationAttachmentsSandboxSchemas", "agent_runtime.core_attachment_sandbox_schemas", None, None,
    ),
    "core_attachment_derived_messages": (
        "WebAttachmentDerivedMessages", "agent_runtime.core_attachment_derived_messages", None, None,
    ),
    "core_attachment_provider_files": (
        "WebConversationAttachmentProviderFiles", "agent_runtime.core_attachment_provider_files", None, None,
    ),
}


def verify_table(name: str, mysql_conn, pg_conn) -> bool:
    """MySQL↔PG count·SUM·missing-id diff. 정합이면 True."""
    mysql_tbl, pg_tbl, my_sum, pg_sum = _VERIFY[name]
    mcur = mysql_conn.cursor()
    mcur.execute(f"SELECT COUNT(*), COALESCE(SUM({my_sum}),0) FROM {mysql_tbl}" if my_sum
                 else f"SELECT COUNT(*), 0 FROM {mysql_tbl}")
    my_count, my_total = mcur.fetchone()
    mcur.execute(f"SELECT Id FROM {mysql_tbl}")
    my_ids = {int(r[0]) for r in (mcur.fetchall() or []) if r and r[0] is not None}
    mcur.close()

    with pg_conn.cursor() as pcur:
        pcur.execute(f"SELECT COUNT(*), COALESCE(SUM({pg_sum}),0) FROM {pg_tbl}" if pg_sum
                     else f"SELECT COUNT(*), 0 FROM {pg_tbl}")
        pg_count, pg_total = pcur.fetchone()
        pcur.execute(f"SELECT id FROM {pg_tbl}")
        pg_ids = {int(r[0]) for r in (pcur.fetchall() or []) if r and r[0] is not None}

    missing = sorted(my_ids - pg_ids)   # MySQL 에 있고 PG 에 없는 행
    extra = sorted(pg_ids - my_ids)     # PG 에만 있는 행
    ok = (int(my_count) == int(pg_count)) and (int(my_total or 0) == int(pg_total or 0)) and not missing
    print(
        f"[verify:{name}] mysql(count={my_count}, sum={my_total}) pg(count={pg_count}, sum={pg_total}) "
        f"missing_in_pg={len(missing)} extra_in_pg={len(extra)} -> {'OK' if ok else 'MISMATCH'}",
        file=sys.stderr,
    )
    if missing:
        print(f"[verify:{name}] missing ids (first 20): {missing[:20]}", file=sys.stderr)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="MySQL → PG agent_runtime 첨부 backfill/reconcile")
    parser.add_argument("--table", choices=_TABLE_ORDER, help="단일 테이블만")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true", help="backfill 없이 count/SUM/id-diff 검증만")
    args = parser.parse_args()

    tables = [args.table] if args.table else list(_TABLE_ORDER)
    try:
        mysql_conn = open_mysql_conn()
    except Exception as exc:
        print(f"MySQL 연결 실패: {exc}", file=sys.stderr)
        return 2
    try:
        pg_conn = open_pg_conn()
    except Exception as exc:
        print(f"PG 연결 실패: {exc}", file=sys.stderr)
        return 2

    rc = 0
    try:
        if args.verify:
            all_ok = True
            for t in tables:
                if not verify_table(t, mysql_conn, pg_conn):
                    all_ok = False
            rc = 0 if all_ok else 1
        else:
            total_errors = 0
            for t in tables:
                _, _, errors = backfill_table(t, mysql_conn, pg_conn, args.dry_run)
                total_errors += errors
            rc = 0 if total_errors == 0 else 1
    finally:
        try:
            mysql_conn.close()
        except Exception:
            pass
        try:
            pg_conn.close()
        except Exception:
            pass
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
