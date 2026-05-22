"""Sandbox schema lifecycle helper (D15 maintenance path).

TASK-0094 Sprint 1 Phase 10. BRIEFING D2/D15 + R-Claim4 + R-F4 정합.

본 module 의 책임:
1. **schema name 결정** — `agent_attachment_<sha256(conversation_id)[:32]>` 형식
   (BRIEFING §5.1). `WebConversationAttachmentsSandboxSchemas` mapping table
   에 row 등록.
2. **maintenance path** — `attachment_maintainer` MySQL user 가 wildcard 없이
   exact schema 명으로 `CREATE SCHEMA` + `attachment_writer` 에게 per-schema
   `CREATE / ALTER / INSERT / SELECT` grant (R-Claim4 — GRANT ALL 금지),
   `attachment_reader` 에게 `SELECT only` grant.
3. **drift detection** — `WebConversationAttachmentsSandboxSchemas.expected_grants`
   와 실제 `information_schema.schema_privileges` 의 차이 검출 (R-F4 worker).
4. **DROP** — `attachment_cleanup` user 가 reconciliation 단계에서 호출.

본 module 은 SDK / convenience — caller (Phase 11 ingest worker) 가 호출.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

# attachment_writer 에게 부여하는 권한 set (R-Claim4 최소권한).
_WRITER_PRIVILEGES = ("CREATE", "ALTER", "INSERT", "SELECT")
# attachment_reader 의 권한 set.
_READER_PRIVILEGES = ("SELECT",)

# schema name regex — 안전 가드 (SQL injection 회피).
_SAFE_SCHEMA_RE = re.compile(r"^agent_attachment_[a-f0-9]{32}$")


def sandbox_schema_name_for(conversation_id: str) -> str:
    """BRIEFING §5.1 schema 명 결정 — sha256(conversation_id)[:32] 사용."""
    if not conversation_id:
        raise ValueError("conversation_id required")
    digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
    return f"agent_attachment_{digest[:32]}"


def _is_safe_schema_name(name: str) -> bool:
    """Maintenance path 가 사용하는 SQL 의 schema 명 검증."""
    return bool(name and _SAFE_SCHEMA_RE.match(name))


def _writer_grants_sql(schema_name: str, writer_user: str) -> list[str]:
    """R-Claim4 — exact schema GRANT (wildcard 금지)."""
    privs = ", ".join(_WRITER_PRIVILEGES)
    return [
        f"GRANT {privs} ON `{schema_name}`.* TO '{writer_user}'@'%'",
    ]


def _reader_grants_sql(schema_name: str, reader_user: str) -> list[str]:
    privs = ", ".join(_READER_PRIVILEGES)
    return [
        f"GRANT {privs} ON `{schema_name}`.* TO '{reader_user}'@'%'",
    ]


def _cleanup_grants_sql(schema_name: str, cleanup_user: str) -> list[str]:
    return [
        f"GRANT DROP ON `{schema_name}`.* TO '{cleanup_user}'@'%'",
    ]


def ensure_sandbox_schema_via_maintainer(
    maintainer_conn,
    conversation_id: str,
    *,
    writer_user: str | None = None,
    reader_user: str | None = None,
    cleanup_user: str | None = None,
) -> dict[str, Any]:
    """maintainer DB connection 으로 schema 생성 + per-schema grant 부여.

    R-Claim4 정합 — wildcard 없이 exact backtick schema 명으로만 grant. caller 는
    maintainer credential 의 connection 을 제공.

    Returns: {schema_name, created (bool), granted (list[str])}
    """
    schema_name = sandbox_schema_name_for(conversation_id)
    if not _is_safe_schema_name(schema_name):
        raise ValueError(f"unsafe schema name: {schema_name}")

    writer = writer_user or os.getenv("ATTACHMENT_WRITER_DB_USER") or "attachment_writer"
    reader = reader_user or os.getenv("ATTACHMENT_READER_DB_USER") or "attachment_reader"
    cleanup = cleanup_user or os.getenv("ATTACHMENT_CLEANUP_DB_USER") or "attachment_cleanup"

    created = False
    granted: list[str] = []
    cur = maintainer_conn.cursor()
    try:
        # CREATE SCHEMA IF NOT EXISTS (idempotent).
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS `{schema_name}` DEFAULT CHARSET=utf8mb4")
        created = bool(cur.rowcount and cur.rowcount > 0)
        for sql in _writer_grants_sql(schema_name, writer):
            cur.execute(sql)
            granted.append(sql)
        for sql in _reader_grants_sql(schema_name, reader):
            cur.execute(sql)
            granted.append(sql)
        for sql in _cleanup_grants_sql(schema_name, cleanup):
            cur.execute(sql)
            granted.append(sql)
        try:
            cur.execute("FLUSH PRIVILEGES")
        except Exception:
            pass
    finally:
        cur.close()
    try:
        maintainer_conn.commit()
    except Exception:
        pass
    return {"schema_name": schema_name, "created": created, "granted": granted}


def detect_grant_drift(
    web_conn,
    *,
    writer_user: str | None = None,
    reader_user: str | None = None,
) -> list[dict[str, Any]]:
    """R-F4 drift detection.

    WebConversationAttachmentsSandboxSchemas 의 SchemaName 별로 information_schema
    .schema_privileges 와 비교. 불일치 row 목록 반환. caller (health endpoint /
    scheduled worker) 가 admin alert.

    Returns: [{schema_name, missing: [grant_sql...], extra: [grant_sql...]}]
    """
    writer = writer_user or os.getenv("ATTACHMENT_WRITER_DB_USER") or "attachment_writer"
    reader = reader_user or os.getenv("ATTACHMENT_READER_DB_USER") or "attachment_reader"

    cur = web_conn.cursor(dictionary=True)
    drift: list[dict[str, Any]] = []
    try:
        cur.execute(
            """
            SELECT SchemaName, ConversationId
            FROM WebConversationAttachmentsSandboxSchemas
            WHERE DroppedAt IS NULL AND DeletePending = 0
            """
        )
        rows = cur.fetchall() or []
    finally:
        cur.close()

    for row in rows:
        schema = str(row.get("SchemaName") or "")
        if not _is_safe_schema_name(schema):
            continue
        # writer / reader 의 expected privileges 검사.
        expected_writer = set(_WRITER_PRIVILEGES)
        expected_reader = set(_READER_PRIVILEGES)
        actual_writer = _query_user_privs(web_conn, writer, schema)
        actual_reader = _query_user_privs(web_conn, reader, schema)
        missing: list[str] = []
        extra: list[str] = []
        if not expected_writer.issubset(actual_writer):
            missing.append(f"writer missing: {sorted(expected_writer - actual_writer)}")
        # extra 는 본 cycle 의 scope 외 (정책 강화 시 추가)
        if not expected_reader.issubset(actual_reader):
            missing.append(f"reader missing: {sorted(expected_reader - actual_reader)}")
        if missing:
            drift.append({"schema_name": schema, "missing": missing, "extra": extra})
    return drift


def _query_user_privs(conn, user: str, schema_name: str) -> set[str]:
    """information_schema.schema_privileges 에서 user × schema 의 privilege set."""
    if not user or not _is_safe_schema_name(schema_name):
        return set()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT PRIVILEGE_TYPE
            FROM information_schema.schema_privileges
            WHERE GRANTEE LIKE %s AND TABLE_SCHEMA = %s
            """,
            (f"'{user}'@%", schema_name),
        )
        rows = cur.fetchall() or []
        return {str(r[0]).upper() for r in rows if r and r[0]}
    finally:
        cur.close()


def drop_sandbox_schema_via_cleanup(
    cleanup_conn,
    conversation_id: str,
) -> bool:
    """cleanup user connection 으로 schema DROP. caller = reconciliation worker.

    cleanup user 는 schema 별 DROP 만 grant 받음 — wildcard DROP 권한 없음.
    """
    schema_name = sandbox_schema_name_for(conversation_id)
    if not _is_safe_schema_name(schema_name):
        return False
    cur = cleanup_conn.cursor()
    try:
        cur.execute(f"DROP SCHEMA IF EXISTS `{schema_name}`")
    finally:
        cur.close()
    try:
        cleanup_conn.commit()
    except Exception:
        pass
    return True
