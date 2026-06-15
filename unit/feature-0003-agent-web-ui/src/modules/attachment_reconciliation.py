"""Attachment reconciliation worker (TASK-0108).

D6 lifecycle taxonomy 의 retention 경과 후 실삭제 담당:
  - user / conv_soft 사유로 DeletePending=1 된 행을 30일(기본) 후 처리
  - 처리 순서: MinIO 객체 삭제 → sandbox schema DROP → DB hard-delete
  - admin_purge / legal 즉시 삭제 경로는 별도 endpoint (본 worker 미담당)

conv_soft cascade:
  - conversation hard-delete 시점에 해당 conversation 의 활성 attachment 를
    DeletePending=1 / DeleteReason='conv_soft' 로 일괄 마킹 (본 모듈의
    `cascade_conv_soft()` 호출).  이후 retention 경과 시 본 worker 가 실삭제.

실행 모델:
  - startup 백그라운드 스레드에서 ATTACHMENT_RECON_INTERVAL_SEC 간격으로 반복.
  - 배치 크기: ATTACHMENT_RECON_BATCH_SIZE (기본 20).
  - 한 배치 안에서 개별 row 실패는 skip — 다음 cycle 에서 재시도.
"""

from __future__ import annotations

import logging
import os
import time
import threading
from typing import Any

LOG = logging.getLogger(__name__)

# 환경 변수 (app.py 의 동일 env 와 공유).
_RETENTION_DAYS = max(1, int(os.getenv("ATTACHMENT_RECON_RETENTION_DAYS") or "30"))
_INTERVAL_SEC = max(60, int(os.getenv("ATTACHMENT_RECON_INTERVAL_SEC") or "600"))  # 기본 10분
_BATCH_SIZE = max(1, min(100, int(os.getenv("ATTACHMENT_RECON_BATCH_SIZE") or "20")))

# sandbox schema 이름 접두어 가드.
_SANDBOX_PREFIX = "agent_attachment_"

# worker 단일 실행 보장 (중복 기동 방지).
_worker_started = False
_worker_lock = threading.Lock()


# ──────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────

def cascade_conv_soft(conn, conversation_id: str) -> int:
    """conversation hard-delete 직전에 호출 — 활성 attachment 를 conv_soft 마킹.

    이미 DeletePending=1 인 행은 건드리지 않는다 (idempotent).
    Returns: 마킹된 행 수.
    """
    if not conversation_id:
        return 0
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE WebConversationAttachments
                SET DeletePending = 1,
                    DeleteReason  = 'conv_soft',
                    DeletedAt     = COALESCE(DeletedAt, UTC_TIMESTAMP(6))
                WHERE ConversationId = %s
                  AND DeletePending  = 0
                  AND DeletedAt IS NULL
                """,
                (conversation_id,),
            )
            count = int(cur.rowcount or 0)
        finally:
            cur.close()
        try:
            conn.commit()
        except Exception:
            pass
        # TASK-0277: dual-write — conv_soft 로 마킹된 첨부들을 PG 로 미러(flag-gated, fail-soft).
        if count:
            try:
                from web.modules import attachment_pg_mirror as _apm
                _apm.mirror_conversation_attachments(conn, conversation_id)
            except Exception:
                pass
        if count:
            LOG.info("cascade_conv_soft: conv=%s marked %d attachments", conversation_id, count)
        return count
    except Exception as exc:
        LOG.warning("cascade_conv_soft error conv=%s: %s", conversation_id, exc)
        return 0


def run_once(conn_factory) -> dict[str, Any]:
    """한 사이클 실행 — 만료된 DeletePending=1 행을 배치 처리.

    conn_factory: 인자 없이 호출하면 DB connection 을 반환하는 callable.
    Returns: {"processed": int, "errors": int, "skipped": int}
    """
    stats: dict[str, Any] = {"processed": 0, "errors": 0, "skipped": 0}
    try:
        conn = conn_factory()
    except Exception as exc:
        LOG.error("attachment_recon: db connect failed: %s", exc)
        stats["errors"] += 1
        return stats

    try:
        rows = _fetch_expired_batch(conn)
    except Exception as exc:
        LOG.error("attachment_recon: fetch failed: %s", exc)
        conn.close()
        stats["errors"] += 1
        return stats

    for row in rows:
        ok = _process_row(conn, row, conn_factory)
        if ok:
            stats["processed"] += 1
        else:
            stats["errors"] += 1

    conn.close()
    if stats["processed"] or stats["errors"]:
        LOG.info(
            "attachment_recon cycle: processed=%d errors=%d",
            stats["processed"],
            stats["errors"],
        )
    return stats


def start_background_worker(conn_factory) -> None:
    """startup 시 한 번만 호출 — 백그라운드 daemon 스레드 시작."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    t = threading.Thread(
        target=_worker_loop,
        args=(conn_factory,),
        name="attachment-recon-worker",
        daemon=True,
    )
    t.start()
    LOG.info(
        "attachment_recon worker started (interval=%ds retention=%dd batch=%d)",
        _INTERVAL_SEC,
        _RETENTION_DAYS,
        _BATCH_SIZE,
    )


# ──────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────

def _worker_loop(conn_factory) -> None:
    while True:
        try:
            run_once(conn_factory)
        except Exception as exc:
            LOG.error("attachment_recon worker unhandled: %s", exc)
        time.sleep(_INTERVAL_SEC)


def _fetch_expired_batch(conn) -> list[dict]:
    """retention 경과 + DeletePending=1 인 행 최대 BATCH_SIZE 건."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT Id, ConversationId, ObjectKey, Kind, DeleteReason, MetaJson
            FROM WebConversationAttachments
            WHERE DeletePending = 1
              AND DeletedAt IS NOT NULL
              AND DeletedAt <= UTC_TIMESTAMP(6) - INTERVAL %s DAY
              AND UploadStatus != 'deleted'
            ORDER BY DeletedAt ASC
            LIMIT %s
            """,
            (_RETENTION_DAYS, _BATCH_SIZE),
        )
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def _process_row(conn, row: dict, conn_factory) -> bool:
    """단일 attachment 행 실삭제. 실패 시 False 반환 (skip — 다음 cycle 재시도)."""
    att_id = int(row.get("Id") or 0)
    object_key = str(row.get("ObjectKey") or "").strip()
    conv_id = str(row.get("ConversationId") or "").strip()
    meta_raw = row.get("MetaJson") or ""

    # 1) MinIO 객체 삭제.
    if object_key:
        ok = _delete_minio_object(object_key, att_id)
        if not ok:
            return False

    # 2) sandbox schema DROP (csv/xlsx 만).
    kind = str(row.get("Kind") or "").lower()
    if kind in ("csv", "xlsx") and conv_id:
        _drop_sandbox_schema(conv_id, att_id, conn_factory)

    # 3) DB hard-delete (UploadStatus='deleted' + DeletePending=0).
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE WebConversationAttachments
                SET UploadStatus = 'deleted',
                    DeletePending = 0
                WHERE Id = %s AND DeletePending = 1
                """,
                (att_id,),
            )
        finally:
            cur.close()
        try:
            conn.commit()
        except Exception:
            pass
        # TASK-0277: dual-write — hard-delete(UploadStatus='deleted') 상태를 PG 로 미러(flag-gated, fail-soft).
        try:
            from web.modules import attachment_pg_mirror as _apm
            _apm.mirror_attachments(conn, [att_id])
        except Exception:
            pass
        LOG.debug("attachment_recon: processed id=%d key=%s", att_id, object_key)
        return True
    except Exception as exc:
        LOG.warning("attachment_recon: db update failed id=%d: %s", att_id, exc)
        return False


def _delete_minio_object(object_key: str, att_id: int) -> bool:
    """MinIO 객체 삭제. 객체 미존재(404)는 성공으로 처리."""
    try:
        from web.modules import storage_minio
        storage_minio.delete_object(object_key)
        LOG.debug("attachment_recon: minio deleted id=%d key=%s", att_id, object_key)
        return True
    except Exception as exc:
        err_str = str(exc)
        # 객체가 이미 없으면 idempotent 성공.
        if "NoSuchKey" in err_str or "404" in err_str or "Not Found" in err_str:
            LOG.debug("attachment_recon: minio object already gone id=%d key=%s", att_id, object_key)
            return True
        LOG.warning("attachment_recon: minio delete failed id=%d key=%s: %s", att_id, object_key, exc)
        return False


def _drop_sandbox_schema(conv_id: str, att_id: int, conn_factory) -> None:
    """sandbox schema DROP — cleanup user connection 필요. root 로 fallback."""
    cleanup_user = os.getenv("ATTACHMENT_CLEANUP_DB_USER") or ""
    cleanup_pass = os.getenv("ATTACHMENT_CLEANUP_DB_PASSWORD") or ""

    try:
        from web.modules import sandbox_schema as ss

        if cleanup_user:
            # D15 cleanup-user 전용 connection 사용 시도.
            try:
                import mysql.connector
                import os as _os
                cleanup_conn = mysql.connector.connect(
                    host=_os.getenv("DB_HOST", "mysql"),
                    port=int(_os.getenv("DB_PORT", "3306")),
                    user=cleanup_user,
                    password=cleanup_pass,
                    autocommit=True,
                    connection_timeout=10,
                )
                try:
                    ss.drop_sandbox_schema_via_cleanup(cleanup_conn, conv_id)
                    LOG.debug("attachment_recon: sandbox dropped conv=%s id=%d via cleanup_user", conv_id, att_id)
                finally:
                    cleanup_conn.close()
                _mark_sandbox_dropped(conn_factory, conv_id)
                return
            except Exception as exc:
                LOG.warning(
                    "attachment_recon: cleanup_user drop failed conv=%s id=%d: %s — fallback to root",
                    conv_id, att_id, exc,
                )

        # cleanup user 없거나 실패 시 root connection 으로 직접 DROP.
        _drop_sandbox_schema_via_root(ss, conv_id, att_id)
        _mark_sandbox_dropped(conn_factory, conv_id)
    except Exception as exc:
        LOG.warning("attachment_recon: sandbox drop error conv=%s id=%d: %s", conv_id, att_id, exc)


def _drop_sandbox_schema_via_root(ss, conv_id: str, att_id: int) -> None:
    """root credential 로 sandbox schema DROP."""
    import mysql.connector
    import os as _os
    conn = mysql.connector.connect(
        host=_os.getenv("DB_HOST", "mysql"),
        port=int(_os.getenv("DB_PORT", "3306")),
        user=_os.getenv("DB_USER", "root"),
        password=_os.getenv("DB_PASSWORD", ""),
        autocommit=True,
        connection_timeout=10,
    )
    try:
        ss.drop_sandbox_schema_via_cleanup(conn, conv_id)
        LOG.debug("attachment_recon: sandbox dropped conv=%s id=%d via root", conv_id, att_id)
    finally:
        conn.close()


def _mark_sandbox_dropped(conn_factory, conv_id: str) -> None:
    """WebConversationAttachmentsSandboxSchemas.DroppedAt 갱신."""
    try:
        import hashlib
        digest = hashlib.sha256(conv_id.encode()).hexdigest()
        schema_name = f"agent_attachment_{digest[:32]}"
        conn = conn_factory()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    UPDATE WebConversationAttachmentsSandboxSchemas
                    SET DroppedAt = UTC_TIMESTAMP(6), DeletePending = 0
                    WHERE SchemaName = %s AND DroppedAt IS NULL
                    """,
                    (schema_name,),
                )
            finally:
                cur.close()
            try:
                conn.commit()
            except Exception:
                pass
        finally:
            conn.close()
    except Exception as exc:
        LOG.warning("attachment_recon: mark sandbox dropped failed conv=%s: %s", conv_id, exc)
