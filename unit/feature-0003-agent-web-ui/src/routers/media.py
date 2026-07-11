"""feature-0012 P5b Final — media 도메인 APIRouter (이미지 bytes 서빙: 아바타/제품·역할 아이콘).

DI 전환 완료 핸들러 3종(전부 Depends(get_current_account)+get_conn, 로그인 게이트). 공유 의존은
get_current_account/get_conn/_serve_image_object 뿐 — app 정본에서 import(순환 안전: app 이 모든
정의 후 맨 끝 include_router). 경로/메서드/응답 byte-동치(원본과 동일 SQL + _serve_image_object).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Depends

import app
from app import get_current_account, get_conn

INCLUDE_ORDER = 100  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/avatars/{account_id}")
def serve_avatar(account_id: int, request: Request, account=Depends(get_current_account), conn=Depends(get_conn)) -> Any:
    """계정 아바타 이미지 bytes 서빙(로그인 필요 — 같은 출처). 미설정/없음 404 → 프론트 Identicon."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (int(account_id),))
        row = cur.fetchone()
    finally:
        cur.close()
    return _serve_image_object(row[0] if row else None, fallback_404="아바타 없음")


@router.get("/api/products/{product_id}/icon")
def serve_product_icon(product_id: int, request: Request, account=Depends(get_current_account), conn=Depends(get_conn)) -> Any:
    """제품 아이콘 bytes 서빙(로그인 필요). 미설정/없음 404 → 프론트 Identicon/기본."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT IconObjectKey FROM WebProducts WHERE Id = %s", (int(product_id),))
        row = cur.fetchone()
    finally:
        cur.close()
    return _serve_image_object(row[0] if row else None, fallback_404="아이콘 없음")


@router.get("/api/roles/{role_id}/icon")
def serve_role_icon(role_id: int, request: Request, account=Depends(get_current_account), conn=Depends(get_conn)) -> Any:
    """역할 아이콘 bytes 서빙(로그인 필요 — 같은 출처). 미설정/없음 404 → 프론트 Identicon."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT IconObjectKey FROM WebRoles WHERE Id = %s", (int(role_id),))
        row = cur.fetchone()
    finally:
        cur.close()
    return _serve_image_object(row[0] if row else None, fallback_404="아이콘 없음")


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (2종). app 전역은 app.X 동적 참조. ====

def _sniff_image(body: bytes, mime_type: str) -> "tuple[str, str] | None":
    """매직바이트로 이미지 종류 판별(클라이언트 MIME 불신). 반환 (ext, content_type) 또는 None.

    png/jpeg/webp 만 허용. svg(XSS)·gif 등은 거부. mime_type 은 힌트일 뿐, 실제 바이트로 결정.
    """
    if not body or len(body) < 12:
        return None
    if body[:8] == b"\x89PNG\r\n\x1a\n":
        return ("png", "image/png")
    if body[:3] == b"\xff\xd8\xff":
        return ("jpg", "image/jpeg")
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return ("webp", "image/webp")
    return None

def _serve_image_object(object_key: "str | None", *, fallback_404: str = "이미지 없음"):
    """MinIO object_key 의 이미지 bytes 를 같은 출처로 서빙(StreamingResponse 대신 Response).

    캐시: 1일(immutable — URL 에 object key 해시 캐시버스터 동반). 미설정/실패 404.
    """
    if not object_key:
        return app._json_error(fallback_404, 404)
    try:
        from web.modules import storage_minio
        data = storage_minio.get_object_bytes(str(object_key))
    except Exception:
        return app._json_error(fallback_404, 404)
    # content type 은 확장자에서 역추론(저장 시 검증된 png/jpg/webp 만).
    ext = str(object_key).rsplit(".", 1)[-1].lower()
    ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "application/octet-stream")
    from starlette.responses import Response as _Resp
    # TASK-0268 보안: nosniff(MIME 스니핑 XSS 방어심층) + inline disposition. content-type 은
    # 저장 시 매직바이트로 검증된 image/* 만 — 브라우저가 HTML 로 스니핑하지 못하게 못박는다.
    return _Resp(content=data, media_type=ctype, headers={
        "Cache-Control": "private, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    })
