"""feature-0012 P5b Final — media 도메인 APIRouter (이미지 bytes 서빙: 아바타/제품·역할 아이콘).

DI 전환 완료 핸들러 3종(전부 Depends(get_current_account)+get_conn, 로그인 게이트). 공유 의존은
get_current_account/get_conn/_serve_image_object 뿐 — app 정본에서 import(순환 안전: app 이 모든
정의 후 맨 끝 include_router). 경로/메서드/응답 byte-동치(원본과 동일 SQL + _serve_image_object).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Depends

from app import get_current_account, get_conn, _serve_image_object

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
