"""TASK-0277: 첨부 메타 MySQL agent_memory → PG agent_runtime dual-write + read cutover.

대화/메시지는 이미 PG 로 cutover 됐으나(AGENT_RUNTIME_READ_BACKEND=postgres) 첨부 메타는 MySQL 4 테이블이
정본이었다. 본 모듈은 그 첨부 메타를 PG agent_runtime.core_attachments(+부속)로 일원화하기 위한
**독립 플래그** 기반 dual-write 미러 + read 헬퍼를 제공한다(전역 AGENT_RUNTIME_READ_BACKEND 재사용 금지 —
이미 postgres 라 배포 즉시 강제 cutover 가 되어 단계적 롤아웃 불가).

플래그(둘 다 첨부 전용·독립):
  AGENT_RUNTIME_ATTACHMENTS_DUAL_WRITE  : "1/true/on" 이면 모든 첨부 write 가 PG 로 미러(기본 off).
  AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND: "postgres" 이면 사용자/LLM 대면 read 가 PG(기본 mysql).

설계 불변식:
  * MySQL 이 ID·UNIQUE 권위자(dual-write 기간). app.py 는 MySQL lastrowid 를 PG 에 *명시* INSERT 하고,
    버전 체인 UNIQUE 충돌은 MySQL UQ_WCA_VersionChain 가 1차로 막는다. PG 는 그 상태의 멱등 미러.
  * 미러는 동기·fail-soft(PG 실패해도 사용자 흐름 비차단 — MySQL 정본·reconcile 로 수렴).
    같은 요청 내 후속 read 가 PG 를 봐도 정합하도록 write commit *직후* 동기 미러한다.
  * **타입 정합**(라이브 PG 라운드트립으로만 잡히는 함정): MySQL connector 는 JSON 컬럼을 *문자열*로
    반환(app.py:9546 의 json.loads 가 그 증거)하므로 PG read 는 jsonb 를 `::text` 로 돌려주고,
    DATETIME(6)(naive UTC)와 정합하도록 timestamptz 를 `AT TIME ZONE 'UTC'`(naive UTC datetime)로 돌려준다.
    write 미러는 역방향으로 naive UTC datetime → `%(x)s::timestamptz`(UTC 명시), JSON str/dict → `::jsonb`.

write-트랜잭션 내부 read(버전 MAX·sandbox enum·fork source)는 자신의 MySQL write 와 원자적이라 본 모듈의
read 헬퍼 대상이 아니다(MySQL 유지 → 후속 decommission cycle 에서 전환). provider_files 는 라이브 writer 가
전무하고, sandbox_schemas 는 INSERT writer 가 없다(코드상 INSERT 0건). sandbox_schemas 의 UPDATE-only
writer(reconciliation `_mark_sandbox_dropped` 의 DroppedAt/DeletePending)는 미러를 배선하지 않는다 —
PG 테이블은 parity·backfill 용으로만 존재하고 어떤 PG read 헬퍼도 이 두 테이블을 소비하지 않으므로,
DroppedAt 의 미반영은 데이터 손실이 아닌 accepted staleness(decommission cycle 에서 정리). quota·노출
경로와 무관(REV-20260615-0279 MINOR-2).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import timezone
from typing import Any

LOG = logging.getLogger(__name__)


# ── 플래그 ──────────────────────────────────────────────────────────────────
def dual_write_enabled() -> bool:
    return os.environ.get("AGENT_RUNTIME_ATTACHMENTS_DUAL_WRITE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def read_pg_enabled() -> bool:
    return (
        os.environ.get("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", "mysql").strip().lower()
        == "postgres"
    )


# ── 컬럼 계약 ────────────────────────────────────────────────────────────────
# MySQL 행을 (PascalCase) 재읽기할 때 쓰는 SELECT 컬럼(=정본 컬럼 순서).
_MYSQL_ATTACH_COLS = (
    "Id, ConversationId, AccountId, ObjectKey, OriginalFilename, FilenameHmac, MimeType, "
    "SizeBytes, SizeBucket, Sha256, Kind, UploadStatus, AttachmentDerivedMessages, CreatedAt, "
    "DeletedAt, DeletePending, DeleteReason, MetaJson, RootAttachmentId, VersionNumber, "
    "CreatedByRole, SupersededAt"
)

# PG → MySQL(PascalCase) read alias. jsonb=::text, timestamptz=naive UTC (MySQL connector 정합).
_PG_ATTACH_SELECT = """
    id AS "Id",
    conversation_id AS "ConversationId",
    account_id AS "AccountId",
    object_key AS "ObjectKey",
    original_filename AS "OriginalFilename",
    filename_hmac AS "FilenameHmac",
    mime_type AS "MimeType",
    size_bytes AS "SizeBytes",
    size_bucket AS "SizeBucket",
    sha256 AS "Sha256",
    kind AS "Kind",
    upload_status AS "UploadStatus",
    attachment_derived_messages::text AS "AttachmentDerivedMessages",
    (created_at AT TIME ZONE 'UTC') AS "CreatedAt",
    (deleted_at AT TIME ZONE 'UTC') AS "DeletedAt",
    delete_pending AS "DeletePending",
    delete_reason AS "DeleteReason",
    meta_json::text AS "MetaJson",
    root_attachment_id AS "RootAttachmentId",
    version_number AS "VersionNumber",
    created_by_role AS "CreatedByRole",
    (superseded_at AT TIME ZONE 'UTC') AS "SupersededAt"
"""

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
ON CONFLICT (id) DO UPDATE SET
    conversation_id = EXCLUDED.conversation_id,
    account_id = EXCLUDED.account_id,
    object_key = EXCLUDED.object_key,
    original_filename = EXCLUDED.original_filename,
    filename_hmac = EXCLUDED.filename_hmac,
    mime_type = EXCLUDED.mime_type,
    size_bytes = EXCLUDED.size_bytes,
    size_bucket = EXCLUDED.size_bucket,
    sha256 = EXCLUDED.sha256,
    kind = EXCLUDED.kind,
    upload_status = EXCLUDED.upload_status,
    attachment_derived_messages = EXCLUDED.attachment_derived_messages,
    deleted_at = EXCLUDED.deleted_at,
    delete_pending = EXCLUDED.delete_pending,
    delete_reason = EXCLUDED.delete_reason,
    meta_json = EXCLUDED.meta_json,
    root_attachment_id = EXCLUDED.root_attachment_id,
    version_number = EXCLUDED.version_number,
    created_by_role = EXCLUDED.created_by_role,
    superseded_at = EXCLUDED.superseded_at
"""
# created_at 은 ON CONFLICT 에서 갱신하지 않는다(최초 생성시각 보존).

_PG_UPSERT_DERIVED = """
INSERT INTO agent_runtime.core_attachment_derived_messages
    (id, attachment_id, message_id, derivation_type, created_at)
VALUES
    (%(id)s, %(attachment_id)s, %(message_id)s, %(derivation_type)s, %(created_at)s::timestamptz)
ON CONFLICT (id) DO UPDATE SET
    attachment_id = EXCLUDED.attachment_id,
    message_id = EXCLUDED.message_id,
    derivation_type = EXCLUDED.derivation_type
"""


# ── 값 정규화(타입 정합) ──────────────────────────────────────────────────────
def _dt_to_pg(value: Any) -> Any:
    """MySQL naive UTC datetime → PG timestamptz 바인딩용 ISO 문자열(UTC 명시). None 통과."""
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
    """MySQL JSON 컬럼(문자열 또는 dict/list) → PG jsonb 바인딩용 JSON 문자열. None 통과."""
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


def _attach_row_to_params(row: dict[str, Any]) -> dict[str, Any]:
    """MySQL WebConversationAttachments 행(dict) → PG upsert 바인딩 params."""
    return {
        "id": int(row["Id"]),
        "conversation_id": str(row.get("ConversationId") or ""),
        "account_id": int(row.get("AccountId") or 0),
        "object_key": str(row.get("ObjectKey") or ""),
        "original_filename": str(row.get("OriginalFilename") or ""),
        "filename_hmac": str(row.get("FilenameHmac") or ""),
        "mime_type": str(row.get("MimeType") or ""),
        "size_bytes": int(row.get("SizeBytes") or 0),
        "size_bucket": str(row.get("SizeBucket") or ""),
        "sha256": str(row.get("Sha256") or ""),
        "kind": str(row.get("Kind") or ""),
        "upload_status": str(row.get("UploadStatus") or "uploaded"),
        "attachment_derived_messages": _json_to_pg(row.get("AttachmentDerivedMessages")),
        "created_at": _dt_to_pg(row.get("CreatedAt")),
        "deleted_at": _dt_to_pg(row.get("DeletedAt")),
        "delete_pending": int(row.get("DeletePending") or 0),
        "delete_reason": (str(row["DeleteReason"]) if row.get("DeleteReason") else None),
        "meta_json": _json_to_pg(row.get("MetaJson")),
        "root_attachment_id": (int(row["RootAttachmentId"]) if row.get("RootAttachmentId") else None),
        "version_number": int(row.get("VersionNumber") or 1),
        "created_by_role": str(row.get("CreatedByRole") or "user"),
        "superseded_at": _dt_to_pg(row.get("SupersededAt")),
    }


# ── PG 연결(지연 import — 모듈 import 가 PG 를 요구하지 않도록) ──────────────────
def _pg():
    from modules.db import _pg_connect  # type: ignore[import-not-found]
    return _pg_connect()


def _dict_cursor(pg):
    """psycopg3 dict_row 커서. alias 컬럼명이 dict key 가 된다(PascalCase 정합)."""
    from psycopg.rows import dict_row  # type: ignore[import-not-found]
    return pg.cursor(row_factory=dict_row)


# ── write 미러 ────────────────────────────────────────────────────────────────
def mirror_attachments(mysql_conn, ids) -> None:
    """주어진 첨부 id 들의 현재 MySQL 상태를 PG core_attachments 로 멱등 upsert(dual-write). fail-soft.

    INSERT/UPDATE(status·meta·supersede·soft/hard-delete) 모두 동일 — 현재 MySQL 행 상태를 미러한다.
    """
    if not dual_write_enabled():
        return
    id_list = [int(i) for i in (ids or []) if i]
    if not id_list:
        return
    try:
        placeholders = ", ".join(["%s"] * len(id_list))
        mcur = mysql_conn.cursor(dictionary=True)
        try:
            mcur.execute(
                f"SELECT {_MYSQL_ATTACH_COLS} FROM WebConversationAttachments WHERE Id IN ({placeholders})",
                tuple(id_list),
            )
            rows = mcur.fetchall() or []
        finally:
            mcur.close()
        if not rows:
            return
        pg = _pg()
        try:
            with pg.cursor() as cur:
                for r in rows:
                    cur.execute(_PG_UPSERT_ATTACH, _attach_row_to_params(dict(r)))
            try:
                pg.commit()
            except Exception:
                pass
        finally:
            pg.close()
    except Exception as exc:
        LOG.warning("attachment_pg_mirror.mirror_attachments fail-soft ids=%s: %s", id_list[:8], exc)


def mirror_conversation_attachments(mysql_conn, conversation_id: str) -> None:
    """대화의 모든 첨부 id 를 재조회해 미러(reconciliation cascade 등 id 미보유 경로용). fail-soft."""
    if not dual_write_enabled() or not conversation_id:
        return
    try:
        mcur = mysql_conn.cursor()
        try:
            mcur.execute(
                "SELECT Id FROM WebConversationAttachments WHERE ConversationId = %s",
                (str(conversation_id),),
            )
            ids = [int(r[0]) for r in (mcur.fetchall() or []) if r and r[0] is not None]
        finally:
            mcur.close()
        mirror_attachments(mysql_conn, ids)
    except Exception as exc:
        LOG.warning(
            "attachment_pg_mirror.mirror_conversation_attachments fail-soft conv=%s: %s",
            conversation_id, exc,
        )


def mirror_derived_messages(mysql_conn, ids) -> None:
    """WebAttachmentDerivedMessages 행을 PG core_attachment_derived_messages 로 멱등 미러. fail-soft."""
    if not dual_write_enabled():
        return
    id_list = [int(i) for i in (ids or []) if i]
    if not id_list:
        return
    try:
        placeholders = ", ".join(["%s"] * len(id_list))
        mcur = mysql_conn.cursor(dictionary=True)
        try:
            mcur.execute(
                "SELECT Id, AttachmentId, MessageId, DerivationType, CreatedAt "
                f"FROM WebAttachmentDerivedMessages WHERE Id IN ({placeholders})",
                tuple(id_list),
            )
            rows = mcur.fetchall() or []
        finally:
            mcur.close()
        if not rows:
            return
        # REV-20260615-0279 MINOR-1: derived 는 attachment_id FK(core_attachments). 부모 첨부가 PG 에
        # 아직 없으면(dual-write 활성 이전 업로드분 등) FK 위반으로 누락된다 → 부모를 먼저 미러.
        parent_ids = {int(dict(r).get("AttachmentId") or 0) for r in rows}
        parent_ids.discard(0)
        if parent_ids:
            mirror_attachments(mysql_conn, list(parent_ids))
        pg = _pg()
        try:
            with pg.cursor() as cur:
                for r in rows:
                    r = dict(r)
                    cur.execute(_PG_UPSERT_DERIVED, {
                        "id": int(r["Id"]),
                        "attachment_id": int(r.get("AttachmentId") or 0),
                        "message_id": int(r.get("MessageId") or 0),
                        "derivation_type": str(r.get("DerivationType") or ""),
                        "created_at": _dt_to_pg(r.get("CreatedAt")),
                    })
            try:
                pg.commit()
            except Exception:
                pass
        finally:
            pg.close()
    except Exception as exc:
        LOG.warning("attachment_pg_mirror.mirror_derived_messages fail-soft ids=%s: %s", id_list[:8], exc)


# ── PG read 헬퍼(MySQL-shape dict 반환) ──────────────────────────────────────
def pg_load_attachment_row(attachment_id: int) -> dict[str, Any] | None:
    """_load_attachment_row 의 PG 판. 없으면 None. 예외는 caller 가 MySQL 폴백하도록 raise 하지 않고 None."""
    if not attachment_id:
        return None
    try:
        pg = _pg()
        try:
            with _dict_cursor(pg) as cur:
                cur.execute(
                    f"SELECT {_PG_ATTACH_SELECT} FROM agent_runtime.core_attachments WHERE id = %s LIMIT 1",
                    (int(attachment_id),),
                )
                row = cur.fetchone()
        finally:
            pg.close()
        return dict(row) if row else None
    except Exception as exc:
        LOG.warning("attachment_pg_mirror.pg_load_attachment_row id=%s: %s", attachment_id, exc)
        raise


def pg_list_conversation_attachments(conversation_id: str) -> list[dict[str, Any]]:
    """list_conversation_attachments 의 PG 판(최신 버전·미삭제만)."""
    pg = _pg()
    try:
        with _dict_cursor(pg) as cur:
            cur.execute(
                f"SELECT {_PG_ATTACH_SELECT} FROM agent_runtime.core_attachments "
                "WHERE conversation_id = %s AND deleted_at IS NULL AND superseded_at IS NULL "
                "ORDER BY id ASC",
                (str(conversation_id),),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        pg.close()


def pg_get_attachment_versions(root_id: int) -> list[dict[str, Any]]:
    """get_attachment_versions 의 PG 판(체인 전체, VersionNumber ASC)."""
    pg = _pg()
    try:
        with _dict_cursor(pg) as cur:
            cur.execute(
                f"SELECT {_PG_ATTACH_SELECT} FROM agent_runtime.core_attachments "
                "WHERE (root_attachment_id = %s OR id = %s) AND deleted_at IS NULL "
                "ORDER BY version_number ASC, id ASC",
                (int(root_id), int(root_id)),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        pg.close()


def pg_sum_size_bytes(*, conversation_id: str | None = None, account_id: int | None = None) -> int:
    """_check_attachment_size_caps 의 SUM(SizeBytes) PG 판(미삭제·미pending). scope 1개만 지정."""
    pg = _pg()
    try:
        with pg.cursor() as cur:
            if conversation_id is not None:
                cur.execute(
                    "SELECT COALESCE(SUM(size_bytes), 0) FROM agent_runtime.core_attachments "
                    "WHERE conversation_id = %s AND deleted_at IS NULL AND delete_pending = 0",
                    (str(conversation_id),),
                )
            else:
                cur.execute(
                    "SELECT COALESCE(SUM(size_bytes), 0) FROM agent_runtime.core_attachments "
                    "WHERE account_id = %s AND deleted_at IS NULL AND delete_pending = 0",
                    (int(account_id or 0),),
                )
            row = cur.fetchone()
            return int((row[0] if row else 0) or 0)
    finally:
        pg.close()


def pg_select_text_inline(account_id: int, ids, limit: int) -> list[dict[str, Any]]:
    """_prepare_text_inline_attachments 의 PG 판. IDOR 가드(AccountId) 동형. 컬럼은 MySQL 판과 동일."""
    id_list = [int(i) for i in (ids or []) if i]
    if not id_list:
        return []
    placeholders = ", ".join(["%s"] * len(id_list))
    pg = _pg()
    try:
        with _dict_cursor(pg) as cur:
            cur.execute(
                "SELECT id AS \"Id\", original_filename AS \"OriginalFilename\", "
                "object_key AS \"ObjectKey\", kind AS \"Kind\", size_bytes AS \"SizeBytes\", "
                "account_id AS \"AccountId\" "
                f"FROM agent_runtime.core_attachments WHERE id IN ({placeholders}) "
                "AND account_id = %s AND kind = 'text' AND upload_status = 'uploaded' "
                "AND deleted_at IS NULL AND delete_pending = 0 ORDER BY id DESC LIMIT %s",
                tuple(id_list) + (int(account_id), int(limit)),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        pg.close()


def pg_select_vision_images(account_id: int, ids, cap: int) -> list[dict[str, Any]]:
    """_prepare_vision_inline_images 의 image 첨부 선별 PG 판. IDOR 가드(AccountId) 동형."""
    id_list = [int(i) for i in (ids or []) if i]
    if not id_list:
        return []
    placeholders = ", ".join(["%s"] * len(id_list))
    pg = _pg()
    try:
        with _dict_cursor(pg) as cur:
            cur.execute(
                "SELECT id AS \"Id\", object_key AS \"ObjectKey\", mime_type AS \"MimeType\", "
                "original_filename AS \"OriginalFilename\", size_bytes AS \"SizeBytes\", "
                "size_bucket AS \"SizeBucket\" "
                f"FROM agent_runtime.core_attachments WHERE id IN ({placeholders}) "
                "AND account_id = %s AND kind = 'image' AND deleted_at IS NULL AND delete_pending = 0 "
                "ORDER BY id ASC LIMIT %s",
                tuple(id_list) + (int(account_id), int(cap)),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        pg.close()


def pg_select_ingested_meta(account_id: int, ids) -> list[str]:
    """sandbox allowlist 보충용 MetaJson(문자열) 목록 PG 판(ingested csv/xlsx). IDOR 가드(AccountId) 동형."""
    id_list = [int(i) for i in (ids or []) if i]
    if not id_list:
        return []
    placeholders = ", ".join(["%s"] * len(id_list))
    pg = _pg()
    try:
        with pg.cursor() as cur:
            cur.execute(
                f"SELECT meta_json::text FROM agent_runtime.core_attachments WHERE id IN ({placeholders}) "
                "AND account_id = %s AND upload_status = 'ingested' "
                "AND kind IN ('csv','xlsx') AND deleted_at IS NULL",
                tuple(id_list) + (int(account_id),),
            )
            return [str(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None]
    finally:
        pg.close()
