"""feature-0012 P5b Final — attachments 도메인 APIRouter (첨부파일 조회/다운로드).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Any

import app

INCLUDE_ORDER = 150  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/attachments/{attachment_id}")
def get_attachment_metadata(attachment_id: int, request: Request) -> JSONResponse:
    """첨부 metadata + signed URL re-issue (사내망 다운로드 전용). D21 pending 은
    metadata 만, signed URL 미발급."""
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)

    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        row = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn,
            account,
            row,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)

        signed_url: str | None = None
        if not app._account_is_pending(account):
            try:
                signed_url = storage_minio.generate_presigned_get(
                    str(row.get("ObjectKey") or ""),
                    response_filename=str(row.get("OriginalFilename") or ""),
                )
            except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                signed_url = None

        payload = app._serialize_attachment_for_api(
            row,
            include_signed_url=bool(signed_url),
            signed_url=signed_url,
        )
        # D21 metadata-only 마커 — frontend 가 사용자에게 안내.
        if app._account_is_pending(account):
            payload["bytes_access_denied"] = True
            payload["bytes_access_denied_reason"] = "승인 대기 계정은 첨부 본문을 다운로드할 수 없습니다."
        return JSONResponse(payload)
    finally:
        conn.close()

@router.get("/api/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, request: Request):
    """TASK-0284: 첨부 본문을 web FastAPI 가 직접 프록시 스트리밍한다.

    배경: presigned(signed) URL 은 MinIO 내부 endpoint(`minio:9000`) 호스트가 박혀 외부 머신
    브라우저가 열 수 없었다(사용자 보고: 외부에서 다운로드 불가). ADR-0022 설계 의도("MinIO 는
    compose 내부망만 노출, 외부는 web 을 통해 다운로드")를 본 라우트가 구현한다 — 같은 출처(앱
    도메인)로 본문을 내려주므로 앱에 접근 가능한 외부 머신이면 다운로드된다.

    권한은 get_attachment_metadata 와 동형(`_account_can_access_attachment` own/any), 승인 대기
    계정은 본문 차단(D21). 보안: 원본 mime 대신 octet-stream + `Content-Disposition: attachment`
    + nosniff 로 inline 렌더/XSS 를 차단한다(이미지 서빙 12710 의 nosniff 선례 동형)."""
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)

    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        row = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn,
            account,
            row,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        if app._account_is_pending(account):
            return app._json_error("승인 대기 계정은 첨부 본문을 다운로드할 수 없습니다.", 403)
        object_key = str((row or {}).get("ObjectKey") or "")
        if not object_key:
            return app._json_error("첨부 본문을 찾을 수 없습니다.", 404)
        try:
            data = storage_minio.get_object_bytes(object_key)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            return app._json_error("첨부 본문을 가져올 수 없습니다.", 502)

        from starlette.responses import Response as _Resp
        from urllib.parse import quote as _quote
        filename = str((row or {}).get("OriginalFilename") or "download")
        # Content-Disposition: ASCII fallback + RFC5987 비-ASCII(UTF-8) filename*.
        # REV-20260616-0291 MINOR 흡수: 따옴표 + 모든 비출력 제어문자(CR/LF 포함)를 제거해 헤더
        # 인젝션을 차단(OriginalFilename 은 업로드 시 .strip() 만 거쳐 CRLF 가 남을 수 있음).
        # filename*(아래)는 percent-encoding 이라 이미 안전하나, ascii_fallback 도 방어적으로 정제한다.
        ascii_fallback = filename.encode("ascii", "ignore").decode("ascii").replace('"', "")
        ascii_fallback = "".join(c for c in ascii_fallback if c.isprintable()).strip() or "download"
        disposition = (
            f'attachment; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{_quote(filename, safe='')}"
        )
        return _Resp(
            content=data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": disposition,
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )
    finally:
        conn.close()

@router.get("/api/attachments/{attachment_id}/versions")
def get_attachment_versions(attachment_id: int, request: Request) -> JSONResponse:
    """TASK-0274: 첨부의 버전 체인 전체(구버전 포함) 조회.

    attachment_id 는 체인 내 어느 버전이든 가능 — 그 root 를 찾아 전체 체인을 반환한다.
    권한은 기준 첨부의 read.{own,any} 재사용(버전은 같은 conversation·account 귀속).
    각 버전에 signed_url(사내망 다운로드, pending 제외) 동봉. 응답은 VersionNumber ASC.
    """
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        base = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn, account, base,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)

        root_id = int(base.get("RootAttachmentId") or 0) or int(base.get("Id") or 0)
        # TASK-0277: read cutover — PG 우선(권한은 위 _account_can_access_attachment 로 이미 게이트),
        # PG read 실패 시 MySQL 폴백.
        rows = None
        try:
            from web.modules import attachment_pg_mirror as _apm
            if _apm.read_pg_enabled():
                rows = _apm.pg_get_attachment_versions(root_id)
        except Exception:
            rows = None
            logging.getLogger(__name__).warning(
                "get_attachment_versions: PG read failed → MySQL fallback (root=%s)", root_id, exc_info=True)
        if rows is None:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """
                    SELECT
                        Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                        FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                        UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                        DeletePending, DeleteReason, MetaJson,
                        RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
                    FROM WebConversationAttachments
                    WHERE (RootAttachmentId = %s OR Id = %s) AND DeletedAt IS NULL
                    ORDER BY VersionNumber ASC, Id ASC
                    """,
                    (root_id, root_id),
                )
                rows = cur.fetchall() or []
            finally:
                cur.close()

        is_pending = app._account_is_pending(account)
        versions: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            signed_url = None
            if not is_pending:
                try:
                    signed_url = storage_minio.generate_presigned_get(
                        str(d.get("ObjectKey") or ""),
                        response_filename=str(d.get("OriginalFilename") or ""),
                    )
                except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                    signed_url = None
            versions.append(app._serialize_attachment_for_api(
                d, include_signed_url=bool(signed_url), signed_url=signed_url))
        return JSONResponse({"root_attachment_id": root_id, "versions": versions})
    finally:
        conn.close()

@router.delete("/api/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """첨부 soft-delete (D6 user delete_reason). MinIO 객체 실삭제는 Phase 9
    reconciliation worker 가 retention 만료 후 처리. 권한: upload.{own,any}.

    BRIEFING D6 의 4 종 taxonomy 중 user delete 만 본 endpoint 가 trigger.
    admin_purge / legal erasure / conv_soft 는 별 endpoint (Phase 9 ship).
    """
    row = app._load_attachment_row(conn, attachment_id)
    # upload.{own,any} 가 soft-delete 권한 (uploader 가 자기 첨부 회수).
    if not app._account_can_access_attachment(
        conn,
        account,
        row,
        "conversation.attachment.upload.own",
        "conversation.attachment.upload.any",
    ):
        return app._json_error("첨부를 찾을 수 없거나 삭제 권한이 없습니다.", 404)

    # 이미 soft-deleted 면 idempotent 응답.
    if row.get("DeletePending"):
        return JSONResponse(
            {
                "ok": True,
                "delete_reason": str(row.get("DeleteReason") or "user"),
                "already_pending": True,
            }
        )

    before_snapshot = app._serialize_attachment_for_audit(row)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE WebConversationAttachments
            SET DeletePending = 1, DeleteReason = 'user', DeletedAt = UTC_TIMESTAMP(6)
            WHERE Id = %s AND DeletePending = 0
            """,
            (int(attachment_id),),
        )
        updated = int(cur.rowcount or 0)
    finally:
        cur.close()

    if updated <= 0:
        return app._json_error("삭제 처리 실패 (이미 처리됨)", 409)

    try:
        conn.commit()
    except Exception:
        pass

    # TASK-0277: dual-write — soft-delete(DeletePending/DeletedAt) 상태를 PG 로 미러(flag-gated, fail-soft).
    try:
        from web.modules import attachment_pg_mirror as _apm
        _apm.mirror_attachments(conn, [int(attachment_id)])
    except Exception:
        pass

    # audit dispatch.
    try:
        app._audit_user_action(
            conn,
            request,
            account,
            action="attachment.delete",
            resource_type="attachment",
            resource_id=str(attachment_id),
            request_ctx={**before_snapshot, "delete_reason": "user"},
        )
    except Exception:
        # fail-open: attachment.delete audit dispatch 실패는 삭제 응답을 막지 않으나 가시화.
        logging.getLogger(__name__).warning(
            "delete_attachment: delete audit dispatch failed (attachment_id=%s)",
            attachment_id, exc_info=True,
        )

    return JSONResponse({"ok": True, "delete_reason": "user"})
