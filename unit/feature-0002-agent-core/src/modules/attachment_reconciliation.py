# ⚠ 미배선(unwired) — 라이브에서 가동되지 않는 GDPR legal-erasure 설계 코드 (ADR-20260805T153000 · CODEBASE_MAP §7 Known Gaps #4)
#   라이브 reconciliation 은 feature-0003 판(web.modules.attachment_reconciliation)이며, 본 판은
#   TASK-0094 D6 4-state + legal pseudonym 사양의 보존본이다. 삭제·dedup-merge 금지(feature-0011 ANCHOR §3),
#   wiring 은 별도 compliance 결정 사항. env 키 정본은 라이브판 ATTACHMENT_RECON_INTERVAL_SEC —
#   본 판의 ATTACHMENT_RECON_POLL_SEC 는 wiring 시 정본 키로 통일한다.
"""Attachment delete reconciliation worker.

TASK-0094 Sprint 1 Phase 9 — BRIEFING D6 (lifecycle 4 종 taxonomy) + R-Claim6
(tombstone + nullable FK) + R-F1 (delete UX 4 state) + F12 (legal erasure
pseudonymous event id) 정합.

본 worker 는 별 process / scheduled task / cron 으로 호출되며, 또는 web 컨테이너의
백그라운드 thread 로 실행 가능. 10 분 주기 권장 (BRIEFING §6.1).

처리 대상: `WebConversationAttachments.DeletePending=1` 인 row.

D6 4 종 taxonomy 별 SLA (BRIEFING §6.1):
  - user (사용자 명시 delete):       MinIO retention 30 일 → DB row hard-delete
  - conv_soft (conversation cascade): user 와 동일 SLA
  - admin_purge (관리자 즉시 정리):    MinIO + DB + sandbox schema 즉시
  - legal (GDPR / 법적 erasure):       MinIO + DB + sandbox + audit pseudonym

R-Claim6 tombstone 정합: row 의 ConversationId 는 NOT NULL 유지하되, conversation
hard-delete 시 attachment row 는 cascade 가 아닌 별도 reconciliation pass 가
process. 본 cycle 의 attachment DELETE 는 conversation 의 DELETE 와 분리된 lifecycle.

F12 pseudonymous event id: legal erasure 시 audit row 의 attachment id / HMAC 등
PII 잔존 위험 필드를 `pseudonymous_event_id` (irreversible UUID4) 로 대체.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import sys
import time
import uuid as _uuid
from typing import Any

LOG = logging.getLogger(__name__)


# 본 worker 의 default polling 주기 (초). env override 가능.
_RECON_POLL_INTERVAL_SEC = max(60, int(os.getenv("ATTACHMENT_RECON_POLL_SEC") or "600"))

# user / conv_soft 의 retention (일). env override 가능. default 30 일.
_RECON_RETENTION_DAYS = max(1, int(os.getenv("ATTACHMENT_RECON_RETENTION_DAYS") or "30"))


def _utcnow() -> _dt.datetime:
    return _dt.datetime.utcnow()


def _list_pending_attachments(conn) -> list[dict[str, Any]]:
    """DeletePending=1 의 row 목록. DeleteReason 별 처리 path 분기."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT Id, ConversationId, AccountId, ObjectKey, FilenameHmac,
                   SizeBucket, Kind, DeleteReason, DeletedAt
            FROM WebConversationAttachments
            WHERE DeletePending = 1
            ORDER BY DeletedAt ASC, Id ASC
            LIMIT 500
            """
        )
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def _delete_minio_object(object_key: str) -> tuple[bool, str | None]:
    """MinIO 객체 삭제. (ok, error) 반환. boto3/storage_minio 가 미설치면 skip."""
    if not object_key:
        return True, None
    try:
        # feature-0003 의 storage_minio 를 사용.
        # 본 module 은 feature-0002-agent-core 이지만 storage_minio 는 web-ui feature
        # 의 module. agent 이미지가 web-ui src 도 포함하므로 (BRIEFING ANCHOR §1)
        # import 가능. docker container (`/app/web/modules`) 와 host dev 환경
        # (sibling path) 양쪽 모두 동작하도록 fallback 적용.
        try:
            from web.modules import storage_minio  # type: ignore[import-not-found]
        except ImportError:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "feature-0003-agent-web-ui", "src"))
            from modules import storage_minio  # type: ignore[import-not-found]
        if not storage_minio.BOTO3_AVAILABLE:
            return False, "boto3 not available"
        storage_minio.delete_object(object_key)
        return True, None
    except Exception as exc:  # noqa: BLE001 — defense
        return False, str(exc)


def _hard_delete_attachment_row(conn, attachment_id: int) -> bool:
    """attachment row 의 DB hard-delete. R-Claim6 tombstone 정합 — conversation
    의 cascade 가 아닌 본 worker 가 직접 DELETE. ConversationId NOT NULL 제약은
    유지 (R-Claim6 — nullable FK 옵션은 추후 cycle 의 선택지)."""
    if not attachment_id:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM WebConversationAttachments WHERE Id = %s AND DeletePending = 1",
            (int(attachment_id),),
        )
        return int(cur.rowcount or 0) > 0
    finally:
        cur.close()


def _drop_sandbox_schema_if_orphan(conn, conversation_id: str) -> None:
    """conversation 의 모든 attachment 가 hard-deleted 면 sandbox schema 도 DROP 후보.
    Phase 10 의 4 user 분리 (attachment_cleanup user) ship 후 활성. 본 phase 는 mark
    만 — DROP 실행은 Phase 10 의 별 helper 가 담당.
    """
    if not conversation_id:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE WebConversationAttachmentsSandboxSchemas
            SET DeletePending = 1
            WHERE ConversationId = %s
              AND DroppedAt IS NULL
              AND DeletePending = 0
              AND NOT EXISTS (
                  SELECT 1 FROM WebConversationAttachments
                  WHERE ConversationId = %s AND DeletePending = 0
              )
            """,
            (conversation_id, conversation_id),
        )
    finally:
        cur.close()


def _build_pseudonym_for_legal_audit() -> str:
    """F12: legal erasure 의 audit 마커. attachment id / HMAC 대체용."""
    return f"erased-{_uuid.uuid4().hex}"


def _process_user_or_conv_soft(conn, row: dict[str, Any], now: _dt.datetime) -> dict[str, Any]:
    """user / conv_soft 의 30 일 retention SLA. retention 만료 시 MinIO 삭제 + DB hard-delete.
    이전엔 restorable_until 안내 상태로 유지.
    """
    deleted_at = row.get("DeletedAt")
    if not deleted_at:
        return {"action": "skip", "reason": "DeletedAt missing"}
    if hasattr(deleted_at, "tzinfo") and deleted_at.tzinfo is not None:
        deleted_at = deleted_at.replace(tzinfo=None)
    age_days = (now - deleted_at).total_seconds() / 86400.0
    if age_days < _RECON_RETENTION_DAYS:
        return {
            "action": "wait",
            "restorable_until": (deleted_at + _dt.timedelta(days=_RECON_RETENTION_DAYS)).isoformat(),
            "age_days": round(age_days, 2),
        }
    # retention 만료 — MinIO + DB hard-delete.
    object_key = str(row.get("ObjectKey") or "")
    ok, err = _delete_minio_object(object_key)
    if not ok:
        return {"action": "error", "stage": "minio_delete", "error": err}
    if not _hard_delete_attachment_row(conn, int(row.get("Id") or 0)):
        return {"action": "error", "stage": "db_hard_delete", "error": "rowcount=0"}
    _drop_sandbox_schema_if_orphan(conn, str(row.get("ConversationId") or ""))
    return {"action": "hard_delete", "stage": "retention_expired"}


def _process_admin_purge_or_legal(conn, row: dict[str, Any], reason: str) -> dict[str, Any]:
    """admin_purge / legal: MinIO + DB + sandbox 즉시. legal 은 audit pseudonym."""
    object_key = str(row.get("ObjectKey") or "")
    ok, err = _delete_minio_object(object_key)
    if not ok:
        return {"action": "error", "stage": "minio_delete", "error": err}
    pseudonym = _build_pseudonym_for_legal_audit() if reason == "legal" else None
    if not _hard_delete_attachment_row(conn, int(row.get("Id") or 0)):
        return {"action": "error", "stage": "db_hard_delete", "error": "rowcount=0"}
    _drop_sandbox_schema_if_orphan(conn, str(row.get("ConversationId") or ""))
    out = {"action": "hard_delete", "stage": "immediate", "reason": reason}
    if pseudonym:
        out["pseudonymous_event_id"] = pseudonym
    return out


def run_once(conn) -> dict[str, Any]:
    """단일 reconciliation pass. caller (cron / thread) 가 polling.

    Returns: 처리 통계 dict.
    """
    started = time.monotonic()
    now = _utcnow()
    rows = _list_pending_attachments(conn)
    stats: dict[str, Any] = {
        "scanned": len(rows),
        "hard_deleted": 0,
        "waiting": 0,
        "errors": 0,
        "elapsed_ms": 0.0,
    }
    for row in rows:
        reason = str(row.get("DeleteReason") or "user").lower()
        try:
            if reason in ("user", "conv_soft"):
                result = _process_user_or_conv_soft(conn, row, now)
            elif reason in ("admin_purge", "legal"):
                result = _process_admin_purge_or_legal(conn, row, reason)
            else:
                result = {"action": "skip", "reason": f"unknown DeleteReason: {reason}"}
            action = str(result.get("action") or "")
            if action == "hard_delete":
                stats["hard_deleted"] += 1
            elif action == "wait":
                stats["waiting"] += 1
            elif action == "error":
                stats["errors"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"] += 1
            LOG.warning("attachment_reconciliation row=%s exc=%s", row.get("Id"), exc)
    try:
        conn.commit()
    except Exception:
        pass
    stats["elapsed_ms"] = round((time.monotonic() - started) * 1000.0, 2)
    return stats


def get_attachment_lifecycle_state(row: dict[str, Any]) -> str:
    """F1 delete UX 4 state — frontend 표시용. row dict 에 DeletePending /
    DeleteReason / DeletedAt 가 있어야 함."""
    if not row:
        return "active"
    if not row.get("DeletePending") and not row.get("DeletedAt"):
        return "active"
    reason = str(row.get("DeleteReason") or "").lower()
    if reason in ("admin_purge", "legal"):
        return "purge_in_progress" if row.get("DeletePending") else "erased"
    if reason in ("user", "conv_soft"):
        return "delete_pending"
    return "delete_pending"
